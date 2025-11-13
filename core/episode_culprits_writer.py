"""
ACM Episode Culprits Writer

Writes episode-level fault attribution to ACM_EpisodeCulprits table for:
- Root cause analysis
- Sensor-level contribution tracking
- Detector performance analysis
- Operator diagnostics

Called after episodes are detected and written to ACM_Episodes.
"""

import re
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from utils.logger import Console


def parse_culprits_string(culprits_str: str) -> List[Dict[str, Any]]:
    """
    Parse culprits string into structured records.
    
    Format examples:
    - "pca_spe_z"  -> [{"detector": "pca_spe_z", "sensor": None}]
    - "pca_spe_z(Sensor123)"  -> [{"detector": "pca_spe_z", "sensor": "Sensor123"}]
    - "pca_spe_z(S1),ar1_z(S2)"  -> Multiple entries
    
    Args:
        culprits_str: Culprits string from episodes.culprits column
    
    Returns:
        List of parsed culprit records with detector and sensor
    """
    if not culprits_str or pd.isna(culprits_str):
        return []
    
    culprits_str = str(culprits_str).strip()
    if not culprits_str or culprits_str == "unknown":
        return []
    
    records = []
    
    # Split by comma if multiple culprits
    parts = [p.strip() for p in culprits_str.split(',')]
    
    for i, part in enumerate(parts):
        # Pattern: detector_name or detector_name(sensor)
        match = re.match(r'^([a-zA-Z0-9_]+)(?:\(([^)]+)\))?$', part)
        if match:
            detector = match.group(1)
            sensor = match.group(2) if match.group(2) else None
            records.append({
                "detector": detector,
                "sensor": sensor,
                "rank": i + 1  # 1-indexed ranking
            })
        else:
            # Fallback: treat entire string as detector name
            records.append({
                "detector": part,
                "sensor": None,
                "rank": i + 1
            })
    
    return records


def write_episode_culprits(
    sql_client,
    run_id: str,
    episodes: pd.DataFrame
) -> bool:
    """
    Write episode culprits to ACM_EpisodeCulprits table.
    
    Args:
        sql_client: SQL connection client
        run_id: Unique run identifier (UUID)
        episodes: Episodes dataframe with episode_id and culprits columns
    
    Returns:
        bool: True if write succeeded, False otherwise
    """
    
    if sql_client is None:
        Console.warn("[CULPRITS] No SQL client provided, skipping ACM_EpisodeCulprits write")
        return False
    
    if episodes is None or len(episodes) == 0:
        Console.info("[CULPRITS] No episodes to process for culprits")
        return True
    
    if "culprits" not in episodes.columns:
        Console.warn("[CULPRITS] Episodes dataframe missing 'culprits' column")
        return False
    
    try:
        # Build culprit records
        records = []
        
        for _, episode_row in episodes.iterrows():
            episode_id = episode_row.get("episode_id")
            if pd.isna(episode_id):
                continue
            
            episode_id = int(episode_id)
            culprits_str = episode_row.get("culprits", "")
            
            # Parse culprits string
            culprit_list = parse_culprits_string(culprits_str)
            
            if not culprit_list:
                # No culprits found - write a single "unknown" record
                records.append((
                    run_id,
                    episode_id,
                    "unknown",
                    None,
                    None,
                    1
                ))
                continue
            
            # Write each parsed culprit as a separate record
            for culprit in culprit_list:
                detector_type = culprit["detector"]
                sensor_name = culprit["sensor"]
                rank = culprit["rank"]
                
                # Contribution percentage not available from culprits string
                # Would need to be computed from scores dataframe in future enhancement
                contribution_pct = None
                
                records.append((
                    run_id,
                    episode_id,
                    detector_type,
                    sensor_name,
                    contribution_pct,
                    rank
                ))
        
        if not records:
            Console.info("[CULPRITS] No culprit records to write")
            return True
        
        # Build bulk insert statement
        insert_sql = """
        INSERT INTO dbo.ACM_EpisodeCulprits (
            RunID, EpisodeID, DetectorType, SensorName, ContributionPct, Rank
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        
        # Execute bulk insert
        with sql_client.cursor() as cur:
            cur.fast_executemany = True
            cur.executemany(insert_sql, records)
        
        # Commit
        sql_client.conn.commit()
        
        Console.info(f"[CULPRITS] Wrote {len(records)} culprit records to ACM_EpisodeCulprits for {len(episodes)} episodes")
        return True
        
    except Exception as e:
        Console.error(f"[CULPRITS] Failed to write ACM_EpisodeCulprits: {e}")
        try:
            sql_client.conn.rollback()
        except:
            pass
        return False


def compute_detector_contributions(
    scores_df: pd.DataFrame,
    episodes: pd.DataFrame
) -> pd.DataFrame:
    """
    Compute detector contribution percentages for each episode.
    
    This is an enhanced version that calculates actual contribution percentages
    from the scores dataframe during the episode time windows.
    
    Args:
        scores_df: Scores dataframe with detector z-scores
        episodes: Episodes dataframe with start_ts, end_ts, episode_id
    
    Returns:
        DataFrame with episode_id, detector, sensor, contribution_pct, rank
    """
    detector_cols = [c for c in scores_df.columns if c.endswith('_z')]
    
    if not detector_cols:
        Console.warn("[CULPRITS] No detector z-score columns found for contribution calculation")
        return pd.DataFrame()
    
    records = []
    
    try:
        for _, episode in episodes.iterrows():
            episode_id = episode.get("episode_id")
            start_ts = pd.to_datetime(episode.get("start_ts"))
            end_ts = pd.to_datetime(episode.get("end_ts"))
            
            if pd.isna(episode_id) or pd.isna(start_ts) or pd.isna(end_ts):
                continue
            
            # Get scores during episode window
            mask = (scores_df.index >= start_ts) & (scores_df.index <= end_ts)
            episode_scores = scores_df.loc[mask, detector_cols]
            
            if len(episode_scores) == 0:
                continue
            
            # Compute mean absolute z-score for each detector
            mean_abs_z = episode_scores.abs().mean()
            
            # Compute total absolute z-score sum
            total_abs_z = mean_abs_z.sum()
            
            if total_abs_z == 0:
                continue
            
            # Compute contribution percentages
            contributions = (mean_abs_z / total_abs_z * 100.0).sort_values(ascending=False)
            
            # Write top N contributors (detectors with >1% contribution)
            for rank, (detector, contrib_pct) in enumerate(contributions.items(), start=1):
                if contrib_pct < 1.0:  # Skip negligible contributors
                    break
                
                # Extract sensor name from detector column if available
                # (Future enhancement: link detector to specific sensor)
                sensor_name = None
                
                records.append({
                    "episode_id": int(episode_id),
                    "detector": detector,
                    "sensor": sensor_name,
                    "contribution_pct": float(contrib_pct),
                    "rank": rank
                })
    
    except Exception as e:
        Console.warn(f"[CULPRITS] Contribution calculation failed: {e}")
    
    return pd.DataFrame(records)


def write_episode_culprits_enhanced(
    sql_client,
    run_id: str,
    episodes: pd.DataFrame,
    scores_df: pd.DataFrame
) -> bool:
    """
    Enhanced version that computes detector contributions from scores.
    
    Args:
        sql_client: SQL connection client
        run_id: Unique run identifier (UUID)
        episodes: Episodes dataframe
        scores_df: Scores dataframe with detector z-scores
    
    Returns:
        bool: True if write succeeded, False otherwise
    """
    
    if sql_client is None:
        Console.warn("[CULPRITS] No SQL client provided, skipping ACM_EpisodeCulprits write")
        return False
    
    if episodes is None or len(episodes) == 0:
        Console.info("[CULPRITS] No episodes to process for culprits")
        return True
    
    try:
        # Compute detector contributions from scores
        culprits_df = compute_detector_contributions(scores_df, episodes)
        
        if len(culprits_df) == 0:
            Console.warn("[CULPRITS] No culprit contributions computed, falling back to string parsing")
            return write_episode_culprits(sql_client, run_id, episodes)
        
        # Build records for bulk insert
        records = []
        for _, row in culprits_df.iterrows():
            records.append((
                run_id,
                int(row["episode_id"]),
                str(row["detector"]),
                str(row["sensor"]) if pd.notna(row["sensor"]) else None,
                float(row["contribution_pct"]) if pd.notna(row["contribution_pct"]) else None,
                int(row["rank"])
            ))
        
        if not records:
            Console.info("[CULPRITS] No culprit records to write")
            return True
        
        # Build bulk insert statement
        insert_sql = """
        INSERT INTO dbo.ACM_EpisodeCulprits (
            RunID, EpisodeID, DetectorType, SensorName, ContributionPct, Rank
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        
        # Execute bulk insert
        with sql_client.cursor() as cur:
            cur.fast_executemany = True
            cur.executemany(insert_sql, records)
        
        # Commit
        sql_client.conn.commit()
        
        Console.info(f"[CULPRITS] Wrote {len(records)} enhanced culprit records to ACM_EpisodeCulprits")
        return True
        
    except Exception as e:
        Console.error(f"[CULPRITS] Failed to write enhanced ACM_EpisodeCulprits: {e}")
        try:
            sql_client.conn.rollback()
        except:
            pass
        return False


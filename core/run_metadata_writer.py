"""
ACM Run Metadata Writer

Writes comprehensive run-level metadata to ACM_Runs table for:
- Run tracking and auditing
- Performance monitoring
- Quality assessment
- Refit scheduling

Called at the end of every ACM run (success or failure).
"""

from datetime import datetime, timezone
from typing import Optional
import pandas as pd
from utils.logger import Console


def write_run_metadata(
    sql_client,
    run_id: str,
    equip_id: int,
    equip_name: str,
    started_at: datetime,
    completed_at: datetime,
    config_signature: str,
    train_row_count: int,
    score_row_count: int,
    episode_count: int,
    health_status: str,
    avg_health_index: float,
    min_health_index: float,
    max_fused_z: float,
    data_quality_score: float,
    refit_requested: bool,
    kept_columns: str,
    error_message: Optional[str] = None
) -> bool:
    """
    Write run metadata to ACM_Runs table.
    
    Args:
        sql_client: SQL connection client
        run_id: Unique run identifier (UUID)
        equip_id: Equipment ID
        equip_name: Equipment name
        started_at: Run start timestamp (UTC)
        completed_at: Run completion timestamp (UTC)
        config_signature: MD5 hash of config for change detection
        train_row_count: Number of training rows processed
        score_row_count: Number of scoring rows processed
        episode_count: Number of anomaly episodes detected
        health_status: Overall health status (HEALTHY, CAUTION, ALERT)
        avg_health_index: Average health index (0-100)
        min_health_index: Minimum health index (0-100)
        max_fused_z: Maximum fused z-score
        data_quality_score: Data quality metric (0-100)
        refit_requested: Whether model refit was requested
        kept_columns: Comma-separated list of sensor columns used
        error_message: Error message if run failed (optional)
    
    Returns:
        bool: True if write succeeded, False otherwise
    """
    
    if sql_client is None:
        Console.warn("[RUN_META] No SQL client provided, skipping ACM_Runs write")
        return False
    
    try:
        # Calculate duration
        duration_seconds = int((completed_at - started_at).total_seconds())
        
        # Ensure timestamps are UTC naive (SQL datetime2 requirement)
        if started_at.tzinfo is not None:
            started_at = started_at.replace(tzinfo=None)
        if completed_at.tzinfo is not None:
            completed_at = completed_at.replace(tzinfo=None)
        
        # Build insert statement
        insert_sql = """
        INSERT INTO dbo.ACM_Runs (
            RunID, EquipID, EquipName, StartedAt, CompletedAt, DurationSeconds,
            ConfigSignature, TrainRowCount, ScoreRowCount, EpisodeCount,
            HealthStatus, AvgHealthIndex, MinHealthIndex, MaxFusedZ,
            DataQualityScore, RefitRequested, KeptColumns, ErrorMessage, CreatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        # Prepare record
        record = (
            run_id,
            equip_id,
            equip_name,
            started_at,
            completed_at,
            duration_seconds,
            config_signature,
            train_row_count,
            score_row_count,
            episode_count,
            health_status,
            float(avg_health_index) if avg_health_index is not None else None,
            float(min_health_index) if min_health_index is not None else None,
            float(max_fused_z) if max_fused_z is not None else None,
            float(data_quality_score) if data_quality_score is not None else None,
            refit_requested,
            kept_columns,
            error_message,
            datetime.now(timezone.utc).replace(tzinfo=None)
        )
        
        # Execute insert
        with sql_client.cursor() as cur:
            cur.execute(insert_sql, record)
        
        # Commit
        sql_client.conn.commit()
        
        Console.info(f"[RUN_META] Wrote run metadata to ACM_Runs: {run_id}")
        return True
        
    except Exception as e:
        Console.error(f"[RUN_META] Failed to write ACM_Runs: {e}")
        try:
            sql_client.conn.rollback()
        except:
            pass
        return False


def compute_run_health_status(avg_health: float, min_health: float) -> str:
    """
    Determine overall run health status based on health metrics.
    
    Args:
        avg_health: Average health index (0-100)
        min_health: Minimum health index (0-100)
    
    Returns:
        str: "HEALTHY", "CAUTION", or "ALERT"
    """
    # Alert if minimum health is critically low
    if min_health < 50:
        return "ALERT"
    
    # Alert if average health is low
    if avg_health < 70:
        return "ALERT"
    
    # Caution if minimum health is borderline
    if min_health < 70:
        return "CAUTION"
    
    # Caution if average health is moderate
    if avg_health < 90:
        return "CAUTION"
    
    # Healthy
    return "HEALTHY"


def extract_run_metadata_from_scores(scores: pd.DataFrame, per_regime_enabled: bool = False, regime_count: int = 0) -> dict:
    """
    Extract health and quality metrics from scores dataframe.
    
    Args:
        scores: Scores dataframe with fused z-scores and precomputed health
        per_regime_enabled: Whether per-regime calibration was enabled (DET-07)
        regime_count: Number of regimes detected
    
    Returns:
        dict: Metadata including health metrics and calibration info
    """
    metadata = {}
    
    try:
        # Use precomputed health if available
        if "__health" in scores.columns:
            health = scores["__health"]
        else:
            # Fallback to computing from fused
            health = 100.0 / (1.0 + scores["fused"] ** 2)
        
        metadata["avg_health_index"] = float(health.mean())
        metadata["min_health_index"] = float(health.min())
        metadata["max_fused_z"] = float(scores["fused"].abs().max())
        
        # Health status
        metadata["health_status"] = compute_run_health_status(
            metadata["avg_health_index"],
            metadata["min_health_index"]
        )
        
        # DET-07: Add per-regime calibration info
        metadata["per_regime_enabled"] = per_regime_enabled
        metadata["regime_count"] = regime_count
        
    except Exception as e:
        Console.warn(f"[RUN_META] Failed to extract health metrics: {e}")
        metadata["avg_health_index"] = None
        metadata["min_health_index"] = None
        metadata["max_fused_z"] = None
        metadata["health_status"] = "UNKNOWN"
        metadata["per_regime_enabled"] = False
        metadata["regime_count"] = 0
    
    return metadata


def extract_data_quality_score(data_quality_path) -> float:
    """
    Extract overall data quality score from data_quality.csv.
    
    Args:
        data_quality_path: Path to data_quality.csv file
    
    Returns:
        float: Quality score (0-100), or 100.0 if file not found
    """
    try:
        import pandas as pd
        from pathlib import Path
        
        if not Path(data_quality_path).exists():
            return 100.0
        
        df = pd.read_csv(data_quality_path)
        
        # Calculate quality score based on null rates
        if "null_rate" in df.columns:
            # 100 - (average null rate across sensors)
            avg_null_rate = df["null_rate"].mean()
            quality_score = 100.0 * (1.0 - avg_null_rate / 100.0)
            return float(quality_score)
        
        return 100.0
        
    except Exception as e:
        Console.warn(f"[RUN_META] Failed to extract data quality score: {e}")
        return 100.0

#!/usr/bin/env python
"""
Regime Detection Test Script
=============================
Runs ONLY the regime detection/creation phase of ACM for faster iteration.

This script:
1. Loads raw data from SQL (historian table)
2. Builds regime basis features (operating variables only)
3. Runs regime clustering (HDBSCAN or GMM)
4. Reports regime detection results

Usage:
    python scripts/test_regime_detection.py --equip FD_FAN
    python scripts/test_regime_detection.py --equip GAS_TURBINE --days 30
    python scripts/test_regime_detection.py --equip FD_FAN --force-refit
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd

from core.sql_client import SQLClient
from core.observability import Console
from core import regimes


def load_config_from_sql(sql_client: SQLClient, equip: str) -> dict:
    """Load config from ACM_Config table."""
    # Get equipment ID
    with sql_client.cursor() as cur:
        cur.execute("SELECT EquipID FROM Equipment WHERE EquipCode = ?", (equip,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Equipment '{equip}' not found")
        equip_id = row[0]
    
    # Load config
    with sql_client.cursor() as cur:
        cur.execute("""
            SELECT ParamPath, ParamValue, ValueType
            FROM ACM_Config
            WHERE EquipID = ?
            ORDER BY ParamPath ASC
        """, (equip_id,))
        
        rows = cur.fetchall()
        if not rows:
            Console.warn(f"No config found for {equip}, using defaults", component="REGIME_TEST")
            return {}
        
        cfg_dict = {}
        for param_path, param_value, value_type in rows:
            if value_type == 'int':
                value = int(param_value)
            elif value_type == 'float':
                value = float(param_value)
            elif value_type == 'bool':
                value = param_value.lower() in ('true', '1', 'yes')
            else:
                value = param_value
            
            parts = param_path.split('.')
            d = cfg_dict
            for part in parts[:-1]:
                if part not in d:
                    d[part] = {}
                d = d[part]
            d[parts[-1]] = value
        
        return cfg_dict


def get_equipment_id(sql_client: SQLClient, equip: str) -> int:
    """Get equipment ID from Equipment table."""
    with sql_client.cursor() as cur:
        cur.execute("SELECT EquipID FROM Equipment WHERE EquipCode = ?", (equip,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Equipment '{equip}' not found in Equipment table")
        return row[0]


def load_raw_data(sql_client: SQLClient, equip: str, days: int = 30, use_all: bool = False) -> pd.DataFrame:
    """Load raw historian data for regime detection.
    
    Args:
        sql_client: SQL connection
        equip: Equipment code
        days: Number of days of data to load (from end of available data)
        use_all: If True, load all available data ignoring days parameter
    """
    equip_id = get_equipment_id(sql_client, equip)
    Console.info(f"Loading data for {equip} (EquipID={equip_id})", component="REGIME_TEST")
    
    # Determine table name - try equipment-specific table first
    table_name = f"{equip}_Data"
    with sql_client.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?",
            (table_name,)
        )
        table_exists = cur.fetchone()[0] > 0
    
    if not table_exists:
        # Fall back to historian data via stored procedure
        Console.info(f"No table {table_name}, using stored procedure", component="REGIME_TEST")
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        with sql_client.cursor() as cur:
            cur.execute(
                "EXEC dbo.usp_ACM_GetHistorianData_TEMP @StartTime=?, @EndTime=?, @EquipmentName=?",
                (start_time, end_time, equip)
            )
            
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            if not rows:
                raise ValueError(f"No data returned from stored procedure for {equip}")
            
            df = pd.DataFrame([list(r) for r in rows], columns=columns)
            Console.info(f"Loaded {len(df)} rows from stored procedure", component="REGIME_TEST")
            return df
    
    # Check available data range
    with sql_client.cursor() as cur:
        cur.execute(f"SELECT MIN(EntryDateTime), MAX(EntryDateTime), COUNT(*) FROM [{table_name}]")
        min_date, max_date, total_rows = cur.fetchone()
        Console.info(f"Data range: {min_date} to {max_date} ({total_rows} rows)", component="REGIME_TEST")
    
    if use_all:
        # Load all data
        start_time = min_date
        end_time = max_date
    else:
        # Load last N days from the END of available data (not from today)
        end_time = max_date
        start_time = max_date - timedelta(days=days)
    
    Console.info(f"Loading data from {start_time} to {end_time}", component="REGIME_TEST")
    
    with sql_client.cursor() as cur:
        cur.execute(
            f"SELECT * FROM [{table_name}] WHERE EntryDateTime BETWEEN ? AND ? ORDER BY EntryDateTime",
            (start_time, end_time)
        )
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        
    if not rows:
        raise ValueError(f"No data in {table_name} for specified range")
    
    df = pd.DataFrame([list(r) for r in rows], columns=columns)
    Console.info(f"Loaded {len(df)} rows from {table_name}", component="REGIME_TEST")
    return df


def build_regime_basis(df: pd.DataFrame, cfg: dict) -> tuple:
    """
    Build regime basis from raw data.
    Uses a tag-agnostic numeric surface selected from the observed data.
    """
    # Find timestamp column
    ts_col = None
    for col in ['EntryDateTime', 'Timestamp', 'timestamp', 'Time', 'time']:
        if col in df.columns:
            ts_col = col
            break
    
    if ts_col:
        df = df.set_index(pd.to_datetime(df[ts_col]))
        df = df.drop(columns=[ts_col], errors='ignore')
    
    selected_cols, train_numeric, _, surface_meta = regimes.select_tag_agnostic_numeric_surface(df, df, cfg=cfg)
    Console.info(
        f"Selected {len(selected_cols)} tag-agnostic numeric columns from "
        f"{surface_meta.get('candidate_count', 0)} candidates",
        component="REGIME_TEST"
    )

    if len(selected_cols) < 2:
        raise ValueError("Need at least 2 tag-agnostic numeric columns for regime test basis")

    basis = train_numeric.ffill().bfill().fillna(train_numeric.median(axis=0, numeric_only=True)).fillna(0.0)

    Console.info(f"Regime basis: {basis.shape[0]} rows x {basis.shape[1]} features", component="REGIME_TEST")
    Console.info(f"Features: {list(basis.columns)[:10]}{'...' if len(basis.columns) > 10 else ''}", component="REGIME_TEST")
    
    # Split 60/40 for train/score (matching ACM coldstart behavior)
    split_idx = int(len(basis) * 0.6)
    basis_train = basis.iloc[:split_idx]
    basis_score = basis.iloc[split_idx:]
    
    return basis_train, basis_score, selected_cols


def run_regime_detection(equip: str, days: int = 30, force_refit: bool = False, use_all: bool = False):
    """Run regime detection and report results."""
    Console.header(f"REGIME DETECTION TEST: {equip}")
    Console.info(f"Days: {days} | Force refit: {force_refit} | Use all data: {use_all}", component="REGIME_TEST")
    
    # Connect to SQL using INI file
    sql_client = SQLClient.from_ini('acm')
    sql_client.connect()
    
    # Load config from SQL
    cfg = load_config_from_sql(sql_client, equip)
    
    # Load raw data
    try:
        raw_df = load_raw_data(sql_client, equip, days, use_all)
    except Exception as e:
        Console.error(f"Failed to load data: {e}", component="REGIME_TEST")
        return 1
    
    # Build regime basis
    try:
        basis_train, basis_score, feature_cols = build_regime_basis(raw_df, cfg)
    except Exception as e:
        Console.error(f"Failed to build regime basis: {e}", component="REGIME_TEST")
        return 1
    
    Console.section("REGIME CLUSTERING")
    
    # Get equipment ID for model persistence
    equip_id = get_equipment_id(sql_client, equip)
    
    # Check for existing regime model (unless force refit)
    regime_model = None
    if not force_refit:
        try:
            from core.model_persistence import load_regime_state
            regime_state = load_regime_state(equip=equip, equip_id=equip_id, sql_client=sql_client)
            if regime_state is not None:
                Console.info(f"Found existing regime state v{regime_state.state_version}", component="REGIME_TEST")
                regime_model = regimes.regime_state_to_model(
                    state=regime_state,
                    feature_columns=list(basis_train.columns),
                    raw_tags=list(raw_df.columns),
                    train_hash=None
                )
                Console.ok(f"Loaded regime model with K={regime_state.n_clusters}", component="REGIME_TEST")
        except Exception as e:
            Console.warn(f"No existing model or load failed: {e}", component="REGIME_TEST")
    
    # Fit new model if needed
    if regime_model is None:
        Console.info("Fitting new regime model...", component="REGIME_TEST")
        try:
            basis_meta = {
                'feature_columns': list(basis_train.columns),
                'raw_tags': list(raw_df.columns),
            }
            # Correct function signature: train_basis, basis_meta, cfg, train_hash
            regime_model = regimes.fit_regime_model(
                train_basis=basis_train,
                basis_meta=basis_meta,
                cfg=cfg,
                train_hash=None
            )
            Console.ok(f"Fitted new regime model", component="REGIME_TEST")
        except Exception as e:
            Console.error(f"Failed to fit regime model: {e}", component="REGIME_TEST")
            import traceback
            traceback.print_exc()
            return 1
    
    # Report model details
    Console.section("REGIME MODEL DETAILS")
    
    n_clusters = regime_model.meta.get('n_clusters', 'unknown')
    quality_ok = regime_model.meta.get('quality_ok', 'unknown')
    silhouette = regime_model.meta.get('silhouette_score', 'unknown')
    method = regime_model.meta.get('clustering_method', 'unknown')
    
    Console.info(f"Clustering method: {method}", component="REGIME_TEST")
    Console.info(f"Number of clusters (K): {n_clusters}", component="REGIME_TEST")
    Console.info(f"Quality OK: {quality_ok}", component="REGIME_TEST")
    Console.info(f"Silhouette score: {silhouette}", component="REGIME_TEST")
    
    # Predict on score data
    Console.section("REGIME PREDICTIONS")
    
    try:
        train_labels = regimes.predict_regime(regime_model, basis_train)
        score_labels, score_confidence = regimes.predict_regime_with_confidence(
            regime_model, basis_score, cfg
        )
        
        # Report label distribution
        unique_train, counts_train = np.unique(train_labels, return_counts=True)
        unique_score, counts_score = np.unique(score_labels, return_counts=True)
        
        Console.info("Train data regime distribution:", component="REGIME_TEST")
        for label, count in zip(unique_train, counts_train):
            pct = 100 * count / len(train_labels)
            label_name = f"Regime {label}" if label >= 0 else "UNKNOWN"
            Console.status(f"  {label_name}: {count} ({pct:.1f}%)")
        
        Console.info("Score data regime distribution:", component="REGIME_TEST")
        for label, count in zip(unique_score, counts_score):
            pct = 100 * count / len(score_labels)
            label_name = f"Regime {label}" if label >= 0 else "UNKNOWN"
            Console.status(f"  {label_name}: {count} ({pct:.1f}%)")
        
        # Report confidence stats
        if score_confidence is not None:
            Console.info(f"Confidence stats: min={np.min(score_confidence):.3f}, "
                        f"mean={np.mean(score_confidence):.3f}, max={np.max(score_confidence):.3f}",
                        component="REGIME_TEST")
            unknown_count = np.sum(score_labels == regimes.UNKNOWN_REGIME_LABEL)
            Console.info(f"UNKNOWN assignments: {unknown_count} ({100*unknown_count/len(score_labels):.1f}%)",
                        component="REGIME_TEST")
        
    except Exception as e:
        Console.error(f"Failed to predict regimes: {e}", component="REGIME_TEST")
        import traceback
        traceback.print_exc()
        return 1
    
    Console.section("SUCCESS")
    Console.ok(f"Regime detection completed for {equip}", component="REGIME_TEST")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Test regime detection in isolation",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--equip", required=True, help="Equipment name (e.g., FD_FAN)")
    parser.add_argument("--days", type=int, default=30, help="Days of data to load (default: 30)")
    parser.add_argument("--force-refit", action="store_true", help="Force regime model refit")
    parser.add_argument("--use-all", action="store_true", help="Use all available data")
    
    args = parser.parse_args()
    
    return run_regime_detection(args.equip, args.days, args.force_refit, args.use_all)


if __name__ == "__main__":
    sys.exit(main())

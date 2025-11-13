"""
Test script for SQL-44: Verify SQL historian data loading
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
from core.sql_client import SQLClient
from core.output_manager import OutputManager

# Configuration
EQUIPMENT = "FD_FAN"
START_TIME = "2012-01-06 00:00:00"  # Use full date range from SQL table
END_TIME = "2012-03-01 00:00:00"    # ~2 months should give us plenty of data

print("="*70)
print("SQL-44: Testing SQL Historian Data Loading")
print("="*70)
print()

# Connect to SQL
print("[SQL] Connecting to ACM database...")
try:
    sql_client = SQLClient.from_ini('acm')
    sql_client.connect()
    print("  [OK] Connected successfully")
except Exception as e:
    print(f"  [ERROR] Failed to connect: {e}")
    sys.exit(1)

# Create OutputManager
print()
print("[INIT] Creating OutputManager...")
output_mgr = OutputManager(
    sql_client=sql_client,
    run_id="test-sql-44",
    equip_id=1  # FD_FAN
)
print("  [OK] OutputManager created")

# Minimal config for data loading
cfg = {
    "data": {
        "timestamp_col": "EntryDateTime",
        "sampling_secs": None,  # Auto-detect
        "allow_resample": True,
        "resample_strict": False,
        "interp_method": "linear",
        "max_fill_ratio": 0.20,
        "cold_start_split_ratio": 0.6,  # 60% train, 40% score
        "min_train_samples": 100,
    },
    "runtime": {
        "max_fill_ratio": 0.20,
    }
}

# Test SQL historian data loading
print()
print(f"[LOAD] Loading data for {EQUIPMENT} from {START_TIME} to {END_TIME}...")
try:
    start_utc = pd.Timestamp(START_TIME)
    end_utc = pd.Timestamp(END_TIME)
    
    train, score, meta = output_mgr.load_data(
        cfg=cfg,
        start_utc=start_utc,
        end_utc=end_utc,
        equipment_name=EQUIPMENT,
        sql_mode=True
    )
    
    print()
    print("="*70)
    print("SUCCESS! Data loaded from SQL historian")
    print("="*70)
    print()
    print(f"[RESULT] Train shape: {train.shape}")
    print(f"[RESULT] Score shape: {score.shape}")
    print(f"[RESULT] Total rows: {len(train) + len(score)}")
    print()
    print(f"[META] Timestamp column: {meta.timestamp_col}")
    print(f"[META] Cadence OK: {meta.cadence_ok}")
    print(f"[META] Kept columns: {len(meta.kept_cols)}")
    print(f"[META] Dropped columns: {len(meta.dropped_cols)}")
    print(f"[META] Sampling seconds: {meta.sampling_seconds}")
    print()
    print("Train columns:", list(train.columns[:5]), "..." if len(train.columns) > 5 else "")
    print("Score columns:", list(score.columns[:5]), "..." if len(score.columns) > 5 else "")
    print()
    print("Train index range:", train.index.min(), "to", train.index.max())
    print("Score index range:", score.index.min(), "to", score.index.max())
    print()
    print("="*70)
    print("✓ SQL-44 implementation validated!")
    print("="*70)
    
except Exception as e:
    print()
    print("="*70)
    print(f"[ERROR] Failed to load data: {e}")
    print("="*70)
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    sql_client.close()

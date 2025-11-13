#!/usr/bin/env python3
"""
Script: load_equipment_data_to_sql.py
Purpose: Load CSV data into FD_FAN_Data and GAS_TURBINE_Data tables
Context: SQL-43 - Migrate training and scoring CSVs to SQL

This script:
1. Reads training/scoring CSVs for FD_FAN and GAS_TURBINE
2. Adds DataSource column ('TRAINING' or 'SCORING')
3. Bulk inserts into equipment data tables
4. Reports row counts and timing

Usage:
    python scripts/sql/load_equipment_data_to_sql.py
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import pyodbc

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from core.sql_client import SQLClient
from utils.logger import Console

def load_csv_to_table(
    sql_client: SQLClient,
    csv_path: Path,
    table_name: str,
    timestamp_col: str
) -> int:
    """
    Load a CSV file into an equipment data table using MERGE (upsert) logic.
    
    Args:
        sql_client: SQL connection client
        csv_path: Path to CSV file
        table_name: Target table name (FD_FAN_Data or GAS_TURBINE_Data)
        timestamp_col: Name of timestamp column in CSV ('TS' or 'Ts')
    
    Returns:
        Number of rows upserted
    """
    Console.info(f"[LOAD] Reading {csv_path.name}...")
    
    try:
        # Read CSV
        df = pd.read_csv(csv_path)
        Console.info(f"  Loaded {len(df)} rows, {len(df.columns)} columns")
        
        # Parse timestamp with flexible format handling before renaming
        # Try standard parsing first
        df['EntryDateTime'] = pd.to_datetime(df[timestamp_col], errors='coerce')
        
        # For any remaining NaT values, try with dayfirst=True to handle DD-MM-YYYY format
        mask = df['EntryDateTime'].isna()
        if mask.any():
            original_ts = df[timestamp_col].copy()
            df.loc[mask, 'EntryDateTime'] = pd.to_datetime(
                original_ts[mask], 
                dayfirst=True, 
                errors='coerce'
            )
        
        # Drop the original timestamp column
        df = df.drop(columns=[timestamp_col])
        
        # Drop rows with still-invalid timestamps
        invalid_count = df['EntryDateTime'].isna().sum()
        if invalid_count > 0:
            Console.warn(f"  Dropping {invalid_count} rows with invalid timestamps")
            df = df.dropna(subset=['EntryDateTime'])
        
        # Ensure all sensor columns are FLOAT
        sensor_cols = [col for col in df.columns if col not in ['EntryDateTime', 'LoadedAt']]
        for col in sensor_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Get insertable columns from SQL table
        cursor = sql_client.cursor()
        try:
            cursor.execute(f"""
                SELECT c.name
                FROM sys.columns c
                WHERE c.object_id = OBJECT_ID('dbo.{table_name}')
                AND c.is_identity = 0
                AND c.name NOT IN ('LoadedAt')
                ORDER BY c.column_id
            """)
            sql_columns = [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
        
        # Reorder DataFrame columns to match SQL table
        df_columns = [col for col in sql_columns if col in df.columns]
        df = df[df_columns]
        
        Console.info(f"  Upserting into {table_name} (MERGE on EntryDateTime)...")
        start_time = datetime.now()
        
        # Use MERGE for upsert logic
        cursor = sql_client.cursor()
        try:
            # Build MERGE statement (UPDATE if exists, INSERT if not)
            update_cols = [col for col in df_columns if col != 'EntryDateTime']
            update_set = ', '.join([f"TARGET.[{col}] = SOURCE.[{col}]" for col in update_cols])
            insert_cols = ', '.join([f'[{col}]' for col in df_columns])
            insert_vals = ', '.join([f"SOURCE.[{col}]" for col in df_columns])
            
            merge_sql = f"""
            MERGE dbo.{table_name} AS TARGET
            USING (SELECT ? AS EntryDateTime, {', '.join(['?' for _ in update_cols])}) AS SOURCE ({insert_cols})
            ON TARGET.EntryDateTime = SOURCE.EntryDateTime
            WHEN MATCHED THEN
                UPDATE SET {update_set}
            WHEN NOT MATCHED THEN
                INSERT ({insert_cols}) VALUES ({insert_vals});
            """
            
            # Convert DataFrame to list of tuples
            data_tuples = [tuple(row) for row in df.values]
            
            # Execute batch upsert
            cursor.fast_executemany = True
            cursor.executemany(merge_sql, data_tuples)
            cursor.commit()
        finally:
            cursor.close()
        
        duration = (datetime.now() - start_time).total_seconds()
        rows_per_sec = len(df) / duration if duration > 0 else 0
        
        Console.info(f"  [OK] Upserted {len(df)} rows in {duration:.2f}s ({rows_per_sec:.0f} rows/s)")
        return len(df)
        
    except Exception as e:
        Console.error(f"  ✗ Failed to load {csv_path.name}: {e}")
        raise


def main():
    """Main execution function."""
    Console.info("="*70)
    Console.info("CSV to SQL Equipment Data Migration")
    Console.info("="*70)
    Console.info("")
    
    # Connect to SQL Server
    try:
        Console.info("[SQL] Connecting to ACM database...")
        sql_client = SQLClient.from_ini('acm')
        sql_client.connect()
        Console.info("  [OK] Connected successfully")
        Console.info("")
    except Exception as e:
        Console.error(f"[SQL] Connection failed: {e}")
        return 1
    
    data_dir = project_root / "data"
    total_rows = 0
    start_time = datetime.now()
    
    # =====================================================================
    # Load FD_FAN data
    # =====================================================================
    Console.info("[FD_FAN] Loading data...")
    Console.info("")
    
    try:
        # Training data
        rows = load_csv_to_table(
            sql_client,
            data_dir / "FD_FAN_BASELINE_DATA.csv",
            "FD_FAN_Data",
            "TS"
        )
        total_rows += rows
        Console.info("")
        
        # Scoring data
        rows = load_csv_to_table(
            sql_client,
            data_dir / "FD_FAN_BATCH_DATA.csv",
            "FD_FAN_Data",
            "TS"
        )
        total_rows += rows
        Console.info("")
        
        Console.info("[FD_FAN] [OK] Completed")
        Console.info("")
        
    except Exception as e:
        Console.error(f"[FD_FAN] ✗ Failed: {e}")
        return 1
    
    # =====================================================================
    # Load GAS_TURBINE data
    # =====================================================================
    Console.info("[GAS_TURBINE] Loading data...")
    Console.info("")
    
    try:
        # Training data
        rows = load_csv_to_table(
            sql_client,
            data_dir / "GAS_TURBINE_BASELINE_DATA.csv",
            "GAS_TURBINE_Data",
            "Ts"
        )
        total_rows += rows
        Console.info("")
        
        # Scoring data
        rows = load_csv_to_table(
            sql_client,
            data_dir / "GAS_TURBINE_BATCH_DATA.csv",
            "GAS_TURBINE_Data",
            "Ts"
        )
        total_rows += rows
        Console.info("")
        
        Console.info("[GAS_TURBINE] [OK] Completed")
        Console.info("")
        
    except Exception as e:
        Console.error(f"[GAS_TURBINE] ✗ Failed: {e}")
        return 1
    
    # =====================================================================
    # Summary
    # =====================================================================
    duration = (datetime.now() - start_time).total_seconds()
    
    Console.info("="*70)
    Console.info("Migration Complete!")
    Console.info("="*70)
    Console.info("")
    Console.info(f"Total rows inserted: {total_rows:,}")
    Console.info(f"Total duration: {duration:.2f}s")
    Console.info(f"Average throughput: {total_rows/duration:.0f} rows/s")
    Console.info("")
    
    # Verify row counts
    Console.info("Verifying data in SQL tables...")
    Console.info("")
    
    cursor = sql_client.cursor()
    try:
        cursor.execute("""
            SELECT 
                'FD_FAN_Data' AS TableName,
                MIN(EntryDateTime) AS MinTime,
                MAX(EntryDateTime) AS MaxTime,
                COUNT(*) AS TotalRows
            FROM dbo.FD_FAN_Data
            UNION ALL
            SELECT 
                'GAS_TURBINE_Data',
                MIN(EntryDateTime),
                MAX(EntryDateTime),
                COUNT(*)
            FROM dbo.GAS_TURBINE_Data
            ORDER BY TableName
        """)
        
        Console.info("Table Summary:")
        Console.info("-" * 70)
        for row in cursor.fetchall():
            Console.info(f"  {row[0]:20} {row[1]} to {row[2]} ({row[3]:,} rows)")
    finally:
        cursor.close()
    
    Console.info("")
    Console.info("[OK] All data loaded successfully!")
    Console.info("")
    Console.info("Next steps:")
    Console.info("  1. Test SP: scripts/sql/test_historian_sp.sql")
    Console.info("  2. SQL-44: Modify pipeline to use SP")
    Console.info("  3. SQL-45: Remove CSV file writes")
    Console.info("")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

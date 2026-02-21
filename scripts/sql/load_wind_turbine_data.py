#!/usr/bin/env python3
"""
Script: load_wind_turbine_data.py
Purpose: Load Wind Turbine SCADA CSV into ACM database

This script:
1. Creates WIND_TURBINE_Data table with appropriate schema
2. Adds WIND_TURBINE to Equipments master table
3. Loads CSV data with proper timestamp parsing
4. Verifies global parameters work for all equipment

Usage:
    python scripts/sql/load_wind_turbine_data.py
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
from core.observability import Console


def create_equipment_entry(sql_client: SQLClient, equip_code: str) -> int:
    """
    Add equipment to Equipments master table if not exists.
    
    Returns:
        EquipID of the equipment (existing or newly created)
    """
    cursor = sql_client.cursor()
    try:
        # Check if equipment already exists
        cursor.execute(
            "SELECT EquipID FROM dbo.Equipment WHERE EquipCode = ?",
            (equip_code,)
        )
        row = cursor.fetchone()
        
        if row:
            equip_id = row[0]
            Console.info(f"  Equipment '{equip_code}' already exists (EquipID={equip_id})")
            return equip_id
        
        # Insert new equipment
        cursor.execute("""
            INSERT INTO dbo.Equipment (EquipCode, EquipName, Area, Unit, Status)
            OUTPUT INSERTED.EquipID
            VALUES (?, ?, ?, ?, 1)
        """, (equip_code, 'Wind Turbine SCADA', 'Renewable Energy', 'Wind Farm'))
        
        equip_id = cursor.fetchone()[0]
        cursor.commit()
        
        Console.info(f"  [OK] Created equipment '{equip_code}' (EquipID={equip_id})")
        return equip_id
        
    finally:
        cursor.close()


def create_wind_turbine_table(sql_client: SQLClient) -> None:
    """Create WIND_TURBINE_Data table with appropriate schema."""
    
    create_sql = """
    IF OBJECT_ID('dbo.WIND_TURBINE_Data', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.WIND_TURBINE_Data (
            EntryDateTime DATETIME2(0) NOT NULL,  -- Timestamp column (renamed from Date/Time)
            
            -- 4 sensor tag columns (cleaned names for SQL compatibility)
            [LV_ActivePower_kW] FLOAT NULL,
            [Wind_Speed_ms] FLOAT NULL,
            [Theoretical_Power_Curve_KWh] FLOAT NULL,
            [Wind_Direction_deg] FLOAT NULL,
            
            -- Audit columns
            LoadedAt DATETIME2 DEFAULT GETUTCDATE(),
            
            CONSTRAINT PK_WIND_TURBINE_Data PRIMARY KEY CLUSTERED (EntryDateTime)
        );
        
        -- Index for time-range queries (used by SP)
        CREATE NONCLUSTERED INDEX IX_WIND_TURBINE_Data_TimeRange 
            ON dbo.WIND_TURBINE_Data(EntryDateTime ASC);
            
        PRINT 'Created WIND_TURBINE_Data table';
    END
    ELSE
    BEGIN
        PRINT 'WIND_TURBINE_Data table already exists';
    END
    """
    
    cursor = sql_client.cursor()
    try:
        cursor.execute(create_sql)
        cursor.commit()
        Console.info("  [OK] WIND_TURBINE_Data table ready")
    finally:
        cursor.close()


def load_csv_to_table(
    sql_client: SQLClient,
    csv_path: Path,
    table_name: str
) -> int:
    """
    Load Wind Turbine SCADA CSV into the database.
    
    Returns:
        Number of rows loaded
    """
    Console.info(f"Reading {csv_path.name}...", component="LOAD")
    
    # Read CSV
    df = pd.read_csv(csv_path)
    Console.info(f"  Loaded {len(df)} rows, {len(df.columns)} columns")
    Console.info(f"  Original columns: {list(df.columns)}")
    
    # Rename columns for SQL compatibility
    column_mapping = {
        'Date/Time': 'TS',  # Will be converted to EntryDateTime
        'LV ActivePower (kW)': 'LV_ActivePower_kW',
        'Wind Speed (m/s)': 'Wind_Speed_ms',
        'Theoretical_Power_Curve (KWh)': 'Theoretical_Power_Curve_KWh',
        'Wind Direction (°)': 'Wind_Direction_deg'
    }
    
    df = df.rename(columns=column_mapping)
    Console.info(f"  Renamed columns: {list(df.columns)}")
    
    # Parse timestamp - the format is "DD MM YYYY HH:MM"
    # Example: "01 01 2018 00:00"
    df['EntryDateTime'] = pd.to_datetime(df['TS'], format='%d %m %Y %H:%M', errors='coerce')
    
    # Check for parsing errors
    invalid_count = df['EntryDateTime'].isna().sum()
    if invalid_count > 0:
        Console.warn(f"  {invalid_count} rows with invalid timestamps")
        # Try alternative parsing
        mask = df['EntryDateTime'].isna()
        df.loc[mask, 'EntryDateTime'] = pd.to_datetime(df.loc[mask, 'TS'], errors='coerce')
        
        # Final check
        remaining_invalid = df['EntryDateTime'].isna().sum()
        if remaining_invalid > 0:
            Console.warn(f"  Dropping {remaining_invalid} rows with unparseable timestamps")
            df = df.dropna(subset=['EntryDateTime'])
    
    # Drop the original TS column
    df = df.drop(columns=['TS'])
    
    # Ensure all sensor columns are FLOAT
    sensor_cols = [col for col in df.columns if col != 'EntryDateTime']
    for col in sensor_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    Console.info(f"  Date range: {df['EntryDateTime'].min()} to {df['EntryDateTime'].max()}")
    Console.info(f"  Final columns: {list(df.columns)}")
    
    # Bulk insert using fast_executemany
    Console.info(f"  Inserting into {table_name}...")
    start_time = datetime.now()
    
    cursor = sql_client.cursor()
    try:
        # Clear existing data (if any)
        cursor.execute(f"DELETE FROM dbo.{table_name}")
        deleted = cursor.rowcount
        if deleted > 0:
            Console.info(f"  Cleared {deleted} existing rows")
        
        # Prepare insert statement
        columns = ['EntryDateTime'] + sensor_cols
        placeholders = ', '.join(['?' for _ in columns])
        col_names = ', '.join([f'[{col}]' for col in columns])
        
        insert_sql = f"""
        INSERT INTO dbo.{table_name} ({col_names})
        VALUES ({placeholders})
        """
        
        # Convert DataFrame to list of tuples
        df_ordered = df[columns]
        data_tuples = [tuple(row) for row in df_ordered.values]
        
        # Execute batch insert
        cursor.fast_executemany = True
        cursor.executemany(insert_sql, data_tuples)
        cursor.commit()
        
    finally:
        cursor.close()
    
    duration = (datetime.now() - start_time).total_seconds()
    rows_per_sec = len(df) / duration if duration > 0 else 0
    
    Console.info(f"  [OK] Inserted {len(df)} rows in {duration:.2f}s ({rows_per_sec:.0f} rows/s)")
    return len(df)


def verify_global_config(sql_client: SQLClient) -> None:
    """Verify that global parameters (EquipID=0) work for all equipment."""
    
    Console.info("")
    Console.info("Checking global configuration coverage...", component="VERIFY")
    
    cursor = sql_client.cursor()
    try:
        # Get all equipment
        cursor.execute("SELECT EquipID, EquipCode FROM dbo.Equipments WHERE Active = 1")
        equipment_list = cursor.fetchall()
        
        Console.info(f"  Active equipment: {[row[1] for row in equipment_list]}")
        
        # Check global config count
        cursor.execute("""
            SELECT COUNT(*) FROM dbo.ACM_Config WHERE EquipID = 0
        """)
        global_count = cursor.fetchone()[0]
        Console.info(f"  Global config parameters (EquipID=0): {global_count}")
        
        # Check equipment-specific overrides
        for equip_id, equip_code in equipment_list:
            cursor.execute("""
                SELECT COUNT(*) FROM dbo.ACM_Config WHERE EquipID = ?
            """, (equip_id,))
            specific_count = cursor.fetchone()[0]
            if specific_count > 0:
                Console.info(f"  {equip_code} (EquipID={equip_id}): {specific_count} equipment-specific overrides")
            else:
                Console.info(f"  {equip_code} (EquipID={equip_id}): Uses all global defaults")
        
        Console.info("")
        Console.info("  [OK] Global parameters will apply to all equipment without specific overrides")
        
    finally:
        cursor.close()


def main():
    """Main execution function."""
    Console.info("="*70)
    Console.info("Wind Turbine SCADA Data Import")
    Console.info("="*70)
    Console.info("")
    
    # Connect to SQL Server
    try:
        Console.info("Connecting to ACM database...", component="SQL")
        sql_client = SQLClient.from_ini('acm')
        sql_client.connect()
        Console.info("  [OK] Connected successfully")
        Console.info("")
    except Exception as e:
        Console.error(f"Connection failed: {e}", component="SQL")
        return 1
    
    equip_code = "WIND_TURBINE"
    data_dir = project_root / "data"
    csv_path = data_dir / "Wind Turbine Scada Dataset.csv"
    
    try:
        # Step 1: Create equipment entry
        Console.info("Adding to Equipments master table...", component="EQUIPMENT")
        equip_id = create_equipment_entry(sql_client, equip_code)
        Console.info("")
        
        # Step 2: Create data table
        Console.info("Creating WIND_TURBINE_Data table...", component="TABLE")
        create_wind_turbine_table(sql_client)
        Console.info("")
        
        # Step 3: Load CSV data
        Console.info("Loading Wind Turbine SCADA data...", component="DATA")
        rows = load_csv_to_table(sql_client, csv_path, "WIND_TURBINE_Data")
        Console.info("")
        
        # Step 4: Verify global config
        verify_global_config(sql_client)
        
        Console.info("")
        Console.info("="*70)
        Console.info("SUMMARY")
        Console.info("="*70)
        Console.info(f"  Equipment: {equip_code} (EquipID={equip_id})")
        Console.info(f"  Table: WIND_TURBINE_Data")
        Console.info(f"  Rows loaded: {rows:,}")
        Console.info(f"  Timestamp column: EntryDateTime (renamed from Date/Time)")
        Console.info("")
        Console.info("  To run ACM on this equipment:")
        Console.info(f"    python -m core.acm --equip {equip_code}")
        Console.info("")
        Console.info("Wind Turbine data import completed successfully!", component="OK")
        
        return 0
        
    except Exception as e:
        Console.error(f"Failed: {e}", component="ERROR")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

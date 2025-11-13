"""
Populate ACM_Config table from config_table.csv

This script loads the configuration from configs/config_table.csv
and writes it to the ACM_Config table in SQL Server for centralized
configuration management.

Usage:
    python scripts/sql/populate_acm_config.py
"""

import sys
from pathlib import Path
import pandas as pd

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from core.sql_client import SQLClient
from utils.logger import Console
from utils.config_dict import ConfigDict


def parse_value_type(value: str) -> tuple[str, str]:
    """
    Parse value string and determine its type.
    
    Returns:
        (value, type) where type is 'int', 'float', 'bool', 'str', 'list', 'dict'
    """
    value = str(value).strip()
    
    # Boolean
    if value.lower() in ('true', 'false'):
        return (value.lower(), 'bool')
    
    # Try int
    try:
        int(value)
        return (value, 'int')
    except ValueError:
        pass
    
    # Try float
    try:
        float(value)
        return (value, 'float')
    except ValueError:
        pass
    
    # List (simple comma-separated detection)
    if ',' in value and not value.startswith('{'):
        return (value, 'list')
    
    # Dict (JSON-like)
    if value.startswith('{') and value.endswith('}'):
        return (value, 'dict')
    
    # Default to string
    return (value, 'str')


def flatten_config_to_param_paths(config_dict: dict, prefix: str = "") -> list[tuple[str, str, str]]:
    """
    Flatten nested config dictionary to (ParamPath, ParamValue, ValueType) tuples.
    
    Example:
        {'fusion': {'weights': {'ar1_z': 0.2}}} 
        -> [('fusion.weights.ar1_z', '0.2', 'float')]
    """
    rows = []
    
    for key, value in config_dict.items():
        path = f"{prefix}.{key}" if prefix else key
        
        if isinstance(value, dict):
            # Recurse into nested dict
            rows.extend(flatten_config_to_param_paths(value, path))
        else:
            # Leaf value - add to rows
            value_str, value_type = parse_value_type(str(value))
            rows.append((path, value_str, value_type))
    
    return rows


def get_equipment_mapping(client: SQLClient) -> dict[str, int]:
    """Get EquipCode -> EquipID mapping from Equipment table."""
    cursor = client.cursor()
    try:
        cursor.execute("SELECT EquipID, EquipCode FROM Equipment")
        return {row[1]: row[0] for row in cursor.fetchall()}
    finally:
        cursor.close()


def populate_config(csv_path: Path):
    """
    Load config from CSV and populate ACM_Config table.
    CSV format: EquipID,Category,ParamPath,ParamValue,ValueType,LastUpdated,UpdatedBy,ChangeReason,UpdatedDateTime
    """
    Console.info(f"[CFG-MIGRATE] Loading config from {csv_path}")
    
    # Load CSV
    if not csv_path.exists():
        raise FileNotFoundError(f"Config file not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    Console.info(f"[CFG-MIGRATE] Loaded {len(df)} rows from CSV")
    
    # Validate required columns
    required_cols = ['EquipID', 'ParamPath', 'ParamValue', 'ValueType']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Connect to SQL
    Console.info("[CFG-MIGRATE] Connecting to ACM database...")
    client = SQLClient.from_ini('acm')
    client.connect()
    
    # Batch insert with MERGE (upsert)
    insert_count = 0
    update_count = 0
    error_count = 0
    
    cursor = client.cursor()
    try:
        for _, row in df.iterrows():
            equip_id = int(row['EquipID']) if pd.notna(row['EquipID']) else 0
            param_path = str(row['ParamPath']).strip()
            param_value = str(row['ParamValue']).strip() if pd.notna(row['ParamValue']) else ''
            value_type = str(row['ValueType']).strip() if pd.notna(row['ValueType']) else 'string'
            
            if not param_path:
                Console.warn(f"[CFG-MIGRATE] Skipping empty ParamPath for EquipID={equip_id}")
                error_count += 1
                continue
            
            try:
                # Use MERGE for upsert behavior
                result = cursor.execute("""
                    MERGE INTO ACM_Config AS target
                    USING (SELECT ? AS EquipID, ? AS ParamPath, ? AS ParamValue, ? AS ValueType) AS source
                    ON target.EquipID = source.EquipID AND target.ParamPath = source.ParamPath
                    WHEN MATCHED THEN
                        UPDATE SET ParamValue = source.ParamValue, ValueType = source.ValueType, UpdatedAt = GETUTCDATE()
                    WHEN NOT MATCHED THEN
                        INSERT (EquipID, ParamPath, ParamValue, ValueType)
                        VALUES (source.EquipID, source.ParamPath, source.ParamValue, source.ValueType);
                """, (equip_id, param_path, param_value, value_type))
                
                # Note: pyodbc doesn't return rowcount for MERGE, so we'll just count attempts
                insert_count += 1
                
            except Exception as e:
                Console.warn(f"[CFG-MIGRATE] Failed to insert {param_path} (EquipID={equip_id}): {e}")
                error_count += 1
        
        client.conn.commit()
        Console.info(f"[CFG-MIGRATE] Committed {insert_count} config parameters")
    finally:
        cursor.close()
    
    client.close()
    
    Console.info(f"[CFG-MIGRATE] Migration complete: {insert_count} processed, {error_count} errors")


if __name__ == "__main__":
    config_csv = project_root / "configs" / "config_table.csv"
    populate_config(config_csv)

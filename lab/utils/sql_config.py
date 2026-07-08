# utils/sql_config.py
# === ACM SQL Edition ===
# Purpose: Read equipment configuration from SQL database with CSV fallback
#
# Usage:
#   from utils.sql_config import get_equipment_config
#   
#   # For specific equipment
#   cfg = get_equipment_config(equipment_code='FD_FAN_001')
#   
#   # For global defaults (or when equipment doesn't exist)
#   cfg = get_equipment_config()  # Uses EquipID=0
#
# Returns standard config dict structure

from __future__ import annotations
import json
from typing import Any, Dict, Optional
from pathlib import Path

from core.observability import Console


def get_equipment_config(
    equipment_code: Optional[str] = None,
    use_sql: bool = True,
    fallback_to_csv: bool = True
) -> Dict[str, Any]:
    """
    Get equipment configuration from SQL database, with CSV fallback.
    
    Priority:
    1. If use_sql=True and SQL connection available:
       - Load equipment-specific config (EquipID > 0) merged with global defaults (EquipID=0)
    2. If SQL fails or use_sql=False:
       - Load from configs/config_table.csv (if fallback_to_csv=True)
    
    Args:
        equipment_code: Equipment identifier (e.g., 'FD_FAN_001'). If None, returns global defaults.
        use_sql: Whether to attempt SQL database read (default: True)
        fallback_to_csv: Whether to fall back to CSV if SQL unavailable (default: True)
    
    Returns:
        Config dictionary with nested structure:
        {
            'data': {...},
            'features': {...},
            'models': {'pca': {...}, 'ar1': {...}, ...},
            'detectors': {...},
            'fusion': {...},
            'thresholds': {...},
            'river': {...},
            'regimes': {...}
        }
    """
    
    # Try SQL first if enabled
    if use_sql:
        try:
            cfg = _load_config_from_sql(equipment_code)
            if cfg:
                Console.info(f"Loaded config from SQL for equipment: {equipment_code or 'GLOBAL'}", component="CONFIG")
                return cfg
        except Exception as e:
            Console.warn(f"Failed to load config from SQL: {e}", component="CONFIG")
            if not fallback_to_csv:
                raise
    
    # Fallback to CSV
    if fallback_to_csv:
        Console.info(f"Loading config from CSV (fallback)", component="CONFIG")
        from utils.config_dict import ConfigDict
        csv_path = Path("configs") / "config_table.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Config file not found: {csv_path}")
        return ConfigDict.from_csv(csv_path).to_dict()
    else:
        raise RuntimeError("SQL config load failed and CSV fallback disabled")


def _load_config_from_sql(equipment_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Load config from ACM_Config table.
    
    Merges global defaults (EquipID=0) with equipment-specific overrides.
    """
    from core.sql_client import SQLClient
    
    # Connect to ACM database
    try:
        client = SQLClient.from_ini('acm')
        client.connect()
    except Exception as e:
        Console.warn(f"Cannot connect to ACM database: {e}", component="CONFIG")
        return None
    
    try:
        # Get EquipID if equipment_code provided
        equip_id = None
        if equipment_code:
            equip_id = _get_equipment_id(client, equipment_code)
            if equip_id is None:
                Console.warn(f"Equipment {equipment_code} not found in Equipment table. Using global defaults.", component="CONFIG")
        
        # Query config: global defaults + equipment overrides
        cursor = client.cursor()
        
        if equip_id is None:
            # Only global defaults
            sql = """
                SELECT ParamPath, ParamValue, ValueType
                FROM ACM_Config
                WHERE EquipID = 0
                ORDER BY ParamPath
            """
            cursor.execute(sql)
        else:
            # Merge: equipment-specific overrides + global defaults
            sql = """
                SELECT ParamPath, ParamValue, ValueType
                FROM (
                    -- Equipment-specific overrides
                    SELECT ParamPath, ParamValue, ValueType, 1 AS Priority
                    FROM ACM_Config
                    WHERE EquipID = ?
                    
                    UNION ALL
                    
                    -- Global defaults (only if not overridden)
                    SELECT ParamPath, ParamValue, ValueType, 2 AS Priority
                    FROM ACM_Config
                    WHERE EquipID = 0
                      AND ParamPath NOT IN (
                          SELECT ParamPath FROM ACM_Config WHERE EquipID = ?
                      )
                ) AS Merged
                ORDER BY Priority, ParamPath
            """
            cursor.execute(sql, (equip_id, equip_id))
        
        rows = cursor.fetchall()
        cursor.close()
        
        if not rows:
            Console.warn("No config found in ACM_Config table", component="CONFIG")
            return None
        
        # Convert flat param paths to nested dict
        config = _build_nested_config(rows)
        return config
    
    finally:
        client.close()


def _get_equipment_id(client, equipment_code: str) -> Optional[int]:
    """Look up EquipID from Equipment table."""
    cursor = client.cursor()
    try:
        cursor.execute(
            "SELECT EquipID FROM Equipment WHERE EquipCode = ?",
            (equipment_code,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        cursor.close()


def _build_nested_config(rows) -> Dict[str, Any]:
    """
    Convert flat ParamPath rows to nested config dict.
    
    Input rows: [(ParamPath, ParamValue, ValueType), ...]
    Example: ('fusion.weights.ar1_z', '0.2', 'float')
    
    Output: {'fusion': {'weights': {'ar1_z': 0.2}}}
    """
    config = {}
    
    for row in rows:
        param_path, param_value, value_type = row[0], row[1], row[2]
        
        # Parse value by type
        parsed_value = _parse_param_value(param_value, value_type)
        
        # Split path and create nested structure
        parts = param_path.split('.')
        current = config
        
        # Navigate/create nested dicts
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Set leaf value
        current[parts[-1]] = parsed_value
    
    return config


def _parse_param_value(value: Optional[str], value_type: Optional[str]) -> Any:
    """Convert string value to appropriate Python type."""
    if value is None:
        return None
    
    if value_type is None or value_type == 'string':
        return value
    
    value_type = value_type.lower()
    
    if value_type == 'int':
        return int(value)
    elif value_type == 'float':
        return float(value)
    elif value_type == 'bool':
        return value.lower() in ('true', '1', 'yes', 'y')
    elif value_type == 'json':
        return json.loads(value)
    else:
        # Unknown type, return as string
        return value


def update_equipment_config(
    param_path: str,
    param_value: Any,
    equipment_code: Optional[str] = None,
    updated_by: str = 'SYSTEM',
    change_reason: str = 'Configuration update'
) -> None:
    """
    Update a single config parameter in SQL database.
    
    Creates history record automatically via trigger or application logic.
    
    Args:
        param_path: Dot-notation path (e.g., 'fusion.weights.ar1_z')
        param_value: New value (will be serialized to string)
        equipment_code: Equipment identifier. If None, updates global defaults (EquipID=0)
        updated_by: User/system identifier for audit trail
        change_reason: Description of why config changed
    
    Example:
        # Update global threshold
        update_equipment_config('thresholds.q', 0.95, change_reason='Reduced false positives')
        
        # Update equipment-specific weight
        update_equipment_config('fusion.weights.ar1_z', 0.3, 
                               equipment_code='FD_FAN_001',
                               updated_by='OPERATOR',
                               change_reason='Increased sensitivity for critical equipment')
    """
    from core.sql_client import SQLClient
    
    client = SQLClient.from_ini('acm')
    client.connect()
    
    try:
        # Get EquipID
        equip_id = 0
        if equipment_code:
            equip_id = _get_equipment_id(client, equipment_code)
            if equip_id is None:
                raise ValueError(f"Equipment {equipment_code} not found")
        
        # Determine value type and serialize
        value_type, value_str = _serialize_param_value(param_value)
        
        # Determine category from path (first part)
        category = param_path.split('.')[0]
        
        # Save old value to history before update
        cursor = client.cursor()
        
        # Get current value
        cursor.execute(
            "SELECT ParamValue FROM ACM_Config WHERE EquipID = ? AND ParamPath = ?",
            (equip_id, param_path)
        )
        row = cursor.fetchone()
        old_value = row[0] if row else None
        
        # Insert/update config
        if row:
            # Update existing
            cursor.execute("""
                UPDATE ACM_Config
                SET ParamValue = ?, 
                    ValueType = ?,
                    LastUpdated = SYSUTCDATETIME(),
                    UpdatedBy = ?,
                    ChangeReason = ?,
                    Version = Version + 1
                WHERE EquipID = ? AND ParamPath = ?
            """, (value_str, value_type, updated_by, change_reason, equip_id, param_path))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (equip_id, category, param_path, value_str, value_type, updated_by, change_reason))
        
        # Record change in history
        cursor.execute("""
            INSERT INTO ACM_ConfigHistory (EquipID, ParamPath, OldValue, NewValue, ValueType, ChangedBy, ChangeReason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (equip_id, param_path, old_value, value_str, value_type, updated_by, change_reason))
        
        client.conn.commit()
        cursor.close()
        
        Console.info(f"Updated config: {param_path} = {value_str} for {equipment_code or 'GLOBAL'}", component="CONFIG")
    
    finally:
        client.close()


def _serialize_param_value(value: Any) -> tuple[str, str]:
    """
    Convert Python value to (value_type, value_string) for SQL storage.
    
    Returns:
        (value_type, value_str): e.g., ('float', '0.95') or ('json', '[1,2,3]')
    """
    if value is None:
        return ('string', None)
    elif isinstance(value, bool):
        return ('bool', 'true' if value else 'false')
    elif isinstance(value, int):
        return ('int', str(value))
    elif isinstance(value, float):
        return ('float', str(value))
    elif isinstance(value, (list, dict)):
        return ('json', json.dumps(value))
    else:
        return ('string', str(value))

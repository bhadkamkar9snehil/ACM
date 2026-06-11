# utils/config_dict.py
"""
ConfigDict: Backward-compatible dict wrapper for SQL/CSV config.

Usage:
    # CSV mode (recommended):
    cfg = ConfigDict.from_csv("configs/config_table.csv", equip_id=1)
    n_components = cfg["models"]["pca"]["n_components"]  # ✅ Works
    
    # SQL mode (asset-specific config):
    cfg = ConfigDict.from_sql(equip_id=123, sql_client=cli)
    n_components = cfg["models"]["pca"]["n_components"]  # ✅ Works (loads from SQL)
    
    # Update config (writes to CSV/SQL + history):
    cfg.update_param("thresholds.q", 0.99, reason="auto_tune_fp", run_id="RUN123")
"""
from __future__ import annotations

import json
import hashlib
import copy
import csv
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING
from collections.abc import MutableMapping

if TYPE_CHECKING:
    from core.sql_client import SQLClient

from core.observability import Console


class ConfigDict(MutableMapping):
    """
    Dict-like wrapper that loads config from SQL or YAML.
    Fully backward-compatible with existing cfg['section']['key'] syntax.
    """
    
    def __init__(self, data: Dict[str, Any], mode: str = "yaml", 
                 equip_id: Optional[int] = None, sql_client: Optional[SQLClient] = None):
        self._data = data
        self._mode = mode  # 'yaml', 'csv', or 'sql'
        self._equip_id = equip_id
        self._sql_client = sql_client
        self._csv_path: Optional[Path] = None  # Set by from_csv()
        self._update_callback = None  # Hook for triggering cache invalidation
        
    @classmethod
    def from_yaml(cls, path: Path | str) -> ConfigDict:
        """Load from YAML file (file mode - legacy)."""
        from utils.config import load_config
        data = load_config(path)
        return cls(data, mode="yaml")
    
    @classmethod
    def from_csv(cls, path: Path | str, equip_id: int = 0) -> ConfigDict:
        """
        Load from CSV table (file mode with tabular config).
        
        CSV Schema: EquipID,Category,ParamPath,ParamValue,ValueType,LastUpdated,UpdatedBy,ChangeReason
        
        Params:
            path: Path to config_table.csv
            equip_id: Filter by equipment ID. 0 = global defaults, >0 = asset-specific.
                      Merges global (EquipID=0) with asset-specific overrides.
        """
        data = cls._load_from_csv(Path(path), equip_id)
        cfg = cls(data, mode="csv", equip_id=equip_id)
        cfg._csv_path = Path(path)  # Store for updates
        
        # Compute and store config signature
        signature = cfg.compute_signature()
        cfg._data["_signature"] = signature
        Console.info(f"Config signature: {signature}", component="CONFIG")
        
        return cfg
    
    @staticmethod
    def _load_from_csv(path: Path, equip_id: int) -> Dict[str, Any]:
        """
        Load config from CSV table. Merges global defaults (EquipID=0) 
        with asset-specific overrides (EquipID=equip_id).
        """
        from core.ml_defaults import ML_DEFAULTS
        import copy
        # ML behaviour is code, not configuration: start from the canonical
        # ML defaults; the CSV contributes only human-operable settings
        # (data sources, SQL, runtime, reporting) plus any explicit override.
        base = copy.deepcopy(ML_DEFAULTS)
        if not path.exists():
            Console.warn(f"CSV config not found: {path}", component="CONFIG")
            return base

        try:
            config = base
            with path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                # Collect rows for global (0) and asset-specific (equip_id)
                rows_to_apply = []
                for row in reader:
                    row_equip_id = int(row["EquipID"])
                    if row_equip_id == 0 or row_equip_id == equip_id:
                        rows_to_apply.append(row)
                
                # Apply global first, then asset-specific (override)
                rows_to_apply.sort(key=lambda r: int(r["EquipID"]))
                
                for row in rows_to_apply:
                    category = row["Category"]
                    param_path = row["ParamPath"]
                    param_value = row["ParamValue"]
                    value_type = row["ValueType"]
                    
                    # Parse value based on type
                    if value_type == "list" or value_type == "dict":
                        value = json.loads(param_value) if param_value else ([] if value_type == "list" else {})
                    elif value_type == "bool":
                        value = param_value.lower() in ("true", "1", "yes")
                    elif value_type == "int":
                        value = int(param_value) if param_value else 0
                    elif value_type == "float":
                        value = float(param_value) if param_value else 0.0
                    elif value_type == "string":
                        value = param_value if param_value else None
                    else:
                        value = param_value
                    
                    # Build nested dict structure
                    if category not in config or not isinstance(config.get(category), dict):
                        # If a previous root-level value (e.g. bool) occupied this category, promote it to a dict
                        # Root scalar gets discarded (no clear merge semantics); mixed representations are unsupported.
                        config[category] = {}
                    
                    # Handle nested paths: "pca.n_components" -> config['models']['pca']['n_components']
                    if param_path:
                        keys = param_path.split(".")
                        target = config[category]
                        for k in keys[:-1]:
                            if k not in target or not isinstance(target[k], dict):
                                target[k] = {}
                            target = target[k]
                        target[keys[-1]] = value
                    else:
                        # Root level value (rare)
                        config[category] = value
            
            return config
        
        except Exception as e:
            Console.error(f"Failed to load CSV config from {path}: {e}", component="CONFIG")
            return {}
    
    @classmethod
    def from_sql(cls, equip_id: int, sql_client: SQLClient, csv_fallback: Optional[Path] = None) -> ConfigDict:
        """
        Load from SQL table (SQL mode). Falls back to CSV defaults if SQL empty.
        
        Params:
            equip_id: Asset-specific config (>0). Use 0 for global defaults.
            sql_client: Active SQLClient connection.
            csv_fallback: Optional CSV path for defaults if SQL table empty (configs/config_table.csv).
        """
        data = cls._load_from_sql(equip_id, sql_client)
        
        # If SQL config is empty, seed from CSV defaults
        if not data and csv_fallback:
            Console.warn(f"No SQL config found for equip_id={equip_id}, loading CSV defaults", component="CONFIG")
            temp_cfg = cls.from_csv(csv_fallback, equip_id=equip_id)
            data = temp_cfg.to_dict()
            # Optionally: seed SQL table from CSV here
        
        return cls(data, mode="sql", equip_id=equip_id, sql_client=sql_client)
    
    @staticmethod
    def _load_from_sql(equip_id: int, sql_client: SQLClient) -> Dict[str, Any]:
        """
        Load config from ACM_Config table. Merges global defaults (equip_id=0) 
        with asset-specific overrides (equip_id=N).
        """
        try:
            # Call stored procedure: usp_GetEquipConfig
            params = {"EquipID": equip_id}
            rows = sql_client.call_proc("dbo.usp_GetEquipConfig", params, fetch=True)
            
            config = {}
            for row in rows:
                category = row["Category"]
                param_path = row["ParamPath"]  # e.g., "pca.n_components"
                param_value = row["ParamValue"]  # JSON string
                value_type = row["ValueType"]
                
                # Parse JSON value
                value = json.loads(param_value) if value_type in ("dict", "list") else param_value
                if value_type == "int":
                    value = int(value)
                elif value_type == "float":
                    value = float(value)
                elif value_type == "bool":
                    value = value.lower() in ("true", "1", "yes")
                
                # Build nested dict structure
                if category not in config or not isinstance(config.get(category), dict):
                    # Promote any prior root-level scalar to dict to allow nested params
                    config[category] = {}
                
                # Handle nested paths: "pca.n_components" -> config['models']['pca']['n_components']
                keys = param_path.split(".") if param_path else []
                if not keys:
                    # Root-level value (rare) replaces entire category
                    config[category] = value
                else:
                    target = config[category]
                    for k in keys[:-1]:
                        # CFG-01: Handle non-dict values gracefully (e.g., bool, int)
                        # If target[k] exists but isn't a dict, we can't nest - overwrite it
                        if k not in target:
                            target[k] = {}
                        elif not isinstance(target[k], dict):
                            # Overwrite scalar with dict to support nested paths
                            target[k] = {}
                        target = target[k]
                    target[keys[-1]] = value
            
            return config
        
        except Exception as e:
            Console.error(f"Failed to load SQL config for equip_id={equip_id}: {e}", component="CONFIG")
            return {}
    
    def update_param(self, key_path: str, value: Any, reason: str, run_id: Optional[str] = None, updated_by: str = "SYSTEM") -> None:
        """
        Update a config parameter and persist to SQL (if in SQL mode).
        
        Args:
            key_path: Dot-separated path like "thresholds.q" or "models.pca.n_components"
            value: New value (int/float/bool/str/dict/list)
            reason: Human-readable reason for change (logged to ACM_ConfigHistory)
            run_id: Optional RunID that triggered this change
            updated_by: Who/what updated (default: SYSTEM)
        
        Example:
            cfg.update_param("thresholds.q", 0.99, reason="auto_tune_fp_rate", run_id="RUN123")
        """
        # Update in-memory data first
        keys = key_path.split(".")
        category = keys[0]
        param_path = ".".join(keys[1:])
        
        # Navigate nested dict
        target = self._data
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            elif not isinstance(target[k], dict):
                # Overwrite non-dict values with dict to support nested paths
                target[k] = {}
            target = target[k]
        
        old_value = target.get(keys[-1])
        target[keys[-1]] = value
        
        # Recompute signature since config changed
        new_signature = self.compute_signature()
        self._data["_signature"] = new_signature
        
        # Persist to backend (CSV or SQL)
        if self._mode == "csv" and self._csv_path and self._equip_id is not None:
            try:
                self._write_to_csv(category, param_path, value, updated_by, reason, run_id)
                Console.info(f"Updated {key_path}={value} (reason: {reason}, persisted to CSV)", component="CONFIG")
                Console.info(f"Config signature updated to {new_signature}", component="CONFIG")
                
                # Trigger cache invalidation callback if registered
                if self._update_callback:
                    self._update_callback(key_path, value)
                
            except Exception as e:
                Console.error(f"Failed to persist config update to CSV: {e}", component="CONFIG")
                raise
        
        elif self._mode == "sql" and self._sql_client and self._equip_id is not None:
            try:
                # Determine value type
                if isinstance(value, bool):
                    value_type = "bool"
                    param_value = str(value)
                elif isinstance(value, int):
                    value_type = "int"
                    param_value = str(value)
                elif isinstance(value, float):
                    value_type = "float"
                    param_value = str(value)
                elif isinstance(value, (dict, list)):
                    value_type = "dict" if isinstance(value, dict) else "list"
                    param_value = json.dumps(value)
                else:
                    value_type = "string"
                    param_value = str(value)
                
                # Call stored procedure: usp_UpdateConfigParam
                params = {
                    "EquipID": self._equip_id,
                    "Category": category,
                    "ParamPath": param_path,
                    "ParamValue": param_value,
                    "ValueType": value_type,
                    "UpdatedBy": updated_by,
                    "ChangeReason": reason,
                    "RunID": run_id,
                    "OldValue": json.dumps(old_value) if old_value is not None else None
                }
                self._sql_client.call_proc("dbo.usp_UpdateConfigParam", params)
                Console.info(f"Updated {key_path}={value} (reason: {reason})", component="CONFIG")
                Console.info(f"Config signature updated to {new_signature}", component="CONFIG")
                
                # Trigger cache invalidation callback if registered
                if self._update_callback:
                    self._update_callback(key_path, value)
                
            except Exception as e:
                Console.error(f"Failed to persist config update to SQL: {e}", component="CONFIG")
                raise
        else:
            Console.warn(f"Updated {key_path}={value} in-memory only (not persisted)", component="CONFIG")
    
    def compute_signature(self) -> str:
        """
        Compute SHA-256 hash of config for cache validation.
        Matches _compute_config_signature() in acm_main.py.
        
        DEBT-05: Expanded to include all sections that affect model behavior:
        - models: Model hyperparameters (PCA, iForest, GMM, OMR, etc.)
        - features: Feature engineering (window, FFT, etc.)
        - preprocessing: Data preprocessing settings
        - detectors: Detector-specific parameters (AR1, HST, etc.)
        - thresholds: Calibration thresholds (q, self_tune, clip_z)
        - fusion: Fusion weights and auto-tuning settings
        - regimes: Regime clustering parameters (k, auto_k, etc.)
        - episodes: Episode detection thresholds (CPD k_sigma, h_sigma)
        - drift: Drift detection parameters (p95_threshold, multi_feature)
        """
        # Hash ALL sections that affect model training, calibration, and detection
        sig_sections = ["models", "features", "preprocessing", "detectors", "thresholds", "fusion", "regimes", "episodes", "drift"]
        sig_data = {k: self._data.get(k) for k in sig_sections if k in self._data}
        sig_json = json.dumps(sig_data, sort_keys=True)
        return hashlib.sha256(sig_json.encode("utf-8")).hexdigest()[:16]
    
    def _write_to_csv(self, category: str, param_path: str, value: Any, 
                      updated_by: str, reason: str, run_id: Optional[str]) -> None:
        """
        Write config update to CSV file. Updates existing row or appends new.
        """
        if not self._csv_path:
            raise RuntimeError("[CFG] CSV path not set")
        
        # Determine value type and string representation
        if isinstance(value, bool):
            value_type = "bool"
            param_value = str(value)
        elif isinstance(value, int):
            value_type = "int"
            param_value = str(value)
        elif isinstance(value, float):
            value_type = "float"
            param_value = str(value)
        elif isinstance(value, (dict, list)):
            value_type = "dict" if isinstance(value, dict) else "list"
            param_value = json.dumps(value)
        else:
            value_type = "string"
            param_value = str(value) if value is not None else ""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Read all rows
        rows = []
        header = ["EquipID", "Category", "ParamPath", "ParamValue", "ValueType", "LastUpdated", "UpdatedBy", "ChangeReason"]
        updated = False
        
        with self._csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Update existing row if matches
                if (int(row["EquipID"]) == self._equip_id and 
                    row["Category"] == category and 
                    row["ParamPath"] == param_path):
                    row["ParamValue"] = param_value
                    row["ValueType"] = value_type
                    row["LastUpdated"] = timestamp
                    row["UpdatedBy"] = updated_by
                    row["ChangeReason"] = reason
                    updated = True
                rows.append(row)
        
        # If not found, append new row
        if not updated:
            rows.append({
                "EquipID": str(self._equip_id),
                "Category": category,
                "ParamPath": param_path,
                "ParamValue": param_value,
                "ValueType": value_type,
                "LastUpdated": timestamp,
                "UpdatedBy": updated_by,
                "ChangeReason": reason
            })
        
        # Write back
        with self._csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
    
    def set_update_callback(self, callback):
        """Register callback to trigger when config updated (for cache invalidation)."""
        self._update_callback = callback
    
    # ===== Dict interface (makes cfg['section']['key'] work) =====
    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        self._data[key] = value
    
    def __delitem__(self, key):
        del self._data[key]
    
    def __iter__(self):
        return iter(self._data)
    
    def __len__(self):
        return len(self._data)
    
    def __repr__(self):
        return f"ConfigDict(mode={self._mode}, equip_id={self._equip_id}, keys={list(self._data.keys())})"
    
    def get(self, key, default=None):
        """Dict-compatible get() method."""
        return self._data.get(key, default)
    
    def copy(self):
        """Return deep copy of underlying data."""
        return copy.deepcopy(self._data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export as plain dict."""
        return copy.deepcopy(self._data)


# ========================================================================
# Module-level config utilities (moved from acm_main.py)
# ========================================================================

def compute_config_signature(cfg: Dict[str, Any]) -> str:
    """
    Compute a deterministic hash of config sections that affect model fitting.
    
    DEBT-05: Expanded to include all sections that affect model behavior:
    - models: Model hyperparameters (PCA, iForest, GMM, OMR, etc.)
    - features: Feature engineering (window, FFT, etc.)
    - preprocessing: Data preprocessing settings
    - detectors: Detector-specific parameters (AR1, etc.)
    - thresholds: Calibration thresholds (q, self_tune, clip_z)
    - fusion: Fusion weights and auto-tuning settings
    - regimes: Regime clustering parameters (k, auto_k, etc.)
    - episodes: Episode detection thresholds (CPD k_sigma, h_sigma)
    - drift: Drift detection parameters (p95_threshold, multi_feature)
    
    Args:
        cfg: Config dict or ConfigDict instance
        
    Returns:
        Hex string (16 chars) for cache validation.
    """
    relevant_keys = [
        "models", "features", "preprocessing", "detectors",
        "thresholds", "fusion", "regimes", "episodes", "drift"
    ]
    config_subset = {k: cfg.get(k) for k in relevant_keys if k in cfg}
    # Sort keys for determinism
    config_str = json.dumps(config_subset, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(config_str.encode("utf-8")).hexdigest()[:16]


def cfg_get(cfg: Dict[str, Any], path: str, default: Any) -> Any:
    """
    Read nested config value by dot path.
    """
    keys = path.split(".")
    current: Any = cfg or {}
    for key in keys:
        if hasattr(current, "get") and key in current:
            current = current[key]
        else:
            return default
    value = current
    if default is None:
        return value
    expected_type = type(default)
    if expected_type in (int, float, bool, str) and not isinstance(value, expected_type):
        try:
            if expected_type is int:
                return int(value)
            if expected_type is float:
                return float(value)
            if expected_type is bool:
                return bool(value)
            if expected_type is str:
                return str(value)
        except Exception:
            return default
    return value


def future_cutoff_ts(cfg: Dict[str, Any]) -> Any:
    """
    Return timestamp cutoff with optional future grace minutes from config.
    """
    import pandas as pd

    raw_value = cfg_get(cfg, "runtime.future_grace_minutes", 0) or 0
    try:
        minutes = int(raw_value)
    except (TypeError, ValueError):
        minutes = 0
    minutes = max(0, minutes)
    return pd.Timestamp.now() + pd.Timedelta(minutes=minutes)


def load_config(
    path: Optional[Path] = None,
    equipment_name: Optional[str] = None,
    get_equipment_id_fn: Optional[Any] = None,
) -> ConfigDict:
    """
    Load config from SQL (preferred) or CSV table.
    Returns ConfigDict that acts like a dict but supports updates.
    
    Priority:
    1. SQL database (ACM_Config table) - if available
    2. CSV table (config_table.csv) - required fallback in configs/
    
    Args:
        path: Optional path to CSV config file (for explicit override)
        equipment_name: Name of equipment (e.g., "FD_FAN", "GAS_TURBINE")
                       If provided, loads asset-specific config overrides
        get_equipment_id_fn: Optional function to get equipment ID from name
    
    Returns:
        ConfigDict instance
    """
    from utils.sql_config import get_equipment_config
    
    # Determine equipment ID
    equip_id = 0
    if equipment_name and get_equipment_id_fn:
        equip_id = get_equipment_id_fn(equipment_name)
    elif equipment_name:
        # Fallback: use hash-based ID if no function provided
        hash_val = int(hashlib.md5(equipment_name.encode()).hexdigest(), 16)
        equip_id = (hash_val % 9999) + 1
    
    # Auto-discover config directory if no explicit path provided
    if path is None:
        config_dir = Path("configs")
        csv_path = config_dir / "config_table.csv"
    else:
        config_dir = path.parent
        csv_path = path if path.suffix == '.csv' else config_dir / "config_table.csv"
    
    # Try SQL first (new production mode)
    try:
        cfg_dict = get_equipment_config(
            equipment_code=equipment_name,
            use_sql=True,
            fallback_to_csv=False  # We'll handle fallback manually
        )
        if cfg_dict:
            equip_label = f"{equipment_name} (EquipID={equip_id})" if equip_id > 0 else "global defaults"
            Console.info(f"Loaded config from SQL for {equip_label}", component="CONFIG")
            return ConfigDict(cfg_dict, mode="sql", equip_id=equip_id)
    except Exception as e:
        Console.warn(
            f"Could not load config from SQL: {e}",
            component="CONFIG",
            equipment=equipment_name,
            equip_id=equip_id,
            error=str(e)
        )
    
    # Fallback to CSV table (required)
    if csv_path.exists():
        source = "csv"
        cfg_result = ConfigDict.from_csv(csv_path, equip_id=equip_id)
        Console.info(
            f"Config loaded: source={source} | equip={equipment_name} (EquipID={equip_id})",
            component="CONFIG"
        )
        return cfg_result
    
    # No config found - fail fast
    raise FileNotFoundError(
        f"Config file not found: {csv_path}\n"
        f"Please ensure config_table.csv exists in configs/ directory"
    )


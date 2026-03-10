"""
State Management and Adaptive Configuration (v10.0.0)

Manages persistent forecasting state and adaptive configuration system.
Replaces state logic from forecasting.py (1849-2046) and config from rul_engine.py (90-117).

Key Features:
- Optimistic locking via ROWVERSION for concurrent access
- 3-retry exponential backoff (50ms, 200ms, 800ms)
- Equipment-specific config overrides with global defaults
- Auto-tuning via grid search when data volume threshold reached
- SQL-backed persistence (ACM_ForecastingState, ACM_AdaptiveConfig)

References:
- Database Systems (Elmasri & Navathe): Optimistic concurrency control
- Hyndman & Athanasopoulos (2018): Forecast parameter selection
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from core.observability import Console


@dataclass
class ForecastingState:
    """Persistent forecasting state with model parameters (v10 schema)"""
    equip_id: int
    state_version: int                     # Optimistic locking version (ROWVERSION)
    model_coefficients_json: Dict[str, Any] = field(default_factory=dict)  # Serialized model state
    last_forecast_json: Dict[str, Any] = field(default_factory=dict)  # Last forecast output
    last_retrain_time: Optional[datetime] = None  # When model was last updated
    training_data_hash: str = ""           # Hash of training data (detect drift)
    data_volume_analyzed: int = 0          # Total rows processed (for auto-tuning trigger)
    recent_mae: Optional[float] = None     # Recent mean absolute error
    recent_rmse: Optional[float] = None    # Recent root mean squared error
    retrigger_reason: Optional[str] = None # Why retraining was triggered
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def model_params(self) -> Dict[str, Any]:
        """Alias for model_coefficients_json for backward compatibility"""
        return self.model_coefficients_json
    
    @model_params.setter
    def model_params(self, value: Dict[str, Any]):
        """Setter for model_params alias"""
        self.model_coefficients_json = value


class StateManager:
    """
    Manages persistent forecasting state with optimistic locking.
    
    Concurrency Model:
    - Load: Read state with StateVersion (ROWVERSION)
    - Save: UPDATE WHERE EquipID=X AND StateVersion=old_version
    - Conflict: Retry with exponential backoff (3 attempts: 50ms, 200ms, 800ms)
    
    Usage:
        state_mgr = StateManager(sql_client=sql_client)
        
        # Load state
        state = state_mgr.load_state(equip_id=1)
        
        # Modify state
        state.model_params['level'] = 85.0
        state.data_volume += 100
        
        # Save with conflict handling
        success = state_mgr.save_state(state)
    """
    
    def __init__(self, sql_client: Any, max_retries: int = 3):
        """
        Initialize state manager.
        
        Args:
            sql_client: Database connection (pyodbc)
            max_retries: Maximum retry attempts for optimistic lock conflicts (default 3)
        """
        self.sql_client = sql_client
        self.max_retries = max_retries
        self.retry_delays = [0.05, 0.2, 0.8]  # seconds (exponential backoff)
    
    def load_state(self, equip_id: int) -> Optional[ForecastingState]:
        """
        Load forecasting state from ACM_ForecastingState with optimistic lock version.
        
        Args:
            equip_id: Equipment ID
        
        Returns:
            ForecastingState object, or None if no state exists (first run)
        """
        try:
            cur = self.sql_client.cursor()
            cur.execute(
                """
                SELECT EquipID, StateVersion, ModelCoefficientsJson, LastForecastJson, LastRetrainTime,
                       TrainingDataHash, DataVolumeAnalyzed, RecentMAE, RecentRMSE, RetriggerReason,
                       CreatedAt, UpdatedAt
                FROM dbo.ACM_ForecastingState
                WHERE EquipID = ?
                """,
                (equip_id,)
            )
            row = cur.fetchone()
            cur.close()
            
            if row is None:
                Console.info(f"No previous state for EquipID={equip_id}; starting fresh", component="STATE")
                return None
            
            # Parse JSON fields
            model_coeff = json.loads(row.ModelCoefficientsJson) if row.ModelCoefficientsJson else {}
            last_forecast = json.loads(row.LastForecastJson) if row.LastForecastJson else {}
            
            state = ForecastingState(
                equip_id=row.EquipID,
                state_version=row.StateVersion,  # ROWVERSION (binary, but pyodbc converts to int)
                model_coefficients_json=model_coeff,
                last_forecast_json=last_forecast,
                last_retrain_time=row.LastRetrainTime,
                training_data_hash=row.TrainingDataHash or "",
                data_volume_analyzed=int(row.DataVolumeAnalyzed or 0),
                recent_mae=float(row.RecentMAE) if row.RecentMAE else None,
                recent_rmse=float(row.RecentRMSE) if row.RecentRMSE else None,
                retrigger_reason=row.RetriggerReason,
                created_at=row.CreatedAt,
                updated_at=row.UpdatedAt
            )
            
            Console.info(
                f"Loaded state: EquipID={equip_id}, StateVersion={state.state_version}, "
                f"DataVolume={state.data_volume_analyzed}",
                component="STATE"
            )
            
            return state
            
        except Exception as e:
            Console.warn(f"Failed to load state for EquipID={equip_id}: {e}", component="STATE", equip_id=equip_id, error_type=type(e).__name__, error=str(e)[:200])
            return None
    
    def save_state(self, state: ForecastingState) -> bool:
        """
        Save forecasting state with optimistic locking and retry logic.
        
        Process:
        1. Attempt UPDATE WHERE EquipID=X AND StateVersion=old_version
        2. If rows_affected=0: conflict detected (another process updated state)
        3. Retry with exponential backoff (reload state, re-apply changes, retry UPDATE)
        4. After max_retries: log warning and return False
        
        Args:
            state: ForecastingState to save
        
        Returns:
            True if saved successfully, False if conflict persisted after retries
        """
        for attempt in range(self.max_retries):
            try:
                cur = self.sql_client.cursor()
                
                # Serialize JSON fields
                model_coeff_json = json.dumps(state.model_coefficients_json)
                last_forecast_json = json.dumps(state.last_forecast_json)
                
                # Check if state exists (INSERT vs UPDATE)
                cur.execute("SELECT COUNT(*) FROM dbo.ACM_ForecastingState WHERE EquipID = ?", (state.equip_id,))
                exists = cur.fetchone()[0] > 0
                
                if exists:
                    # UPDATE with optimistic lock check
                    cur.execute(
                        """
                        UPDATE dbo.ACM_ForecastingState
                        SET ModelCoefficientsJson = ?,
                            LastForecastJson = ?,
                            LastRetrainTime = ?,
                            TrainingDataHash = ?,
                            DataVolumeAnalyzed = ?,
                            RecentMAE = ?,
                            RecentRMSE = ?,
                            RetriggerReason = ?,
                            UpdatedAt = GETDATE()
                        WHERE EquipID = ? AND StateVersion = ?
                        """,
                        (
                            model_coeff_json,
                            last_forecast_json,
                            state.last_retrain_time,
                            state.training_data_hash,
                            state.data_volume_analyzed,
                            state.recent_mae,
                            state.recent_rmse,
                            state.retrigger_reason,
                            state.equip_id,
                            state.state_version
                        )
                    )
                    
                    rows_affected = cur.rowcount
                    
                    if rows_affected == 0:
                        # Optimistic lock conflict
                        Console.warn(
                            f"[StateManager] Optimistic lock conflict for EquipID={state.equip_id} "
                            f"(attempt {attempt + 1}/{self.max_retries})",
                            component="STATE", equip_id=state.equip_id, attempt=attempt + 1, max_retries=self.max_retries, state_version=state.state_version
                        )
                        cur.close()
                        
                        if attempt < self.max_retries - 1:
                            # Backoff and retry
                            time.sleep(self.retry_delays[attempt])
                            # Reload state to get updated StateVersion
                            reloaded_state = self.load_state(state.equip_id)
                            if reloaded_state:
                                state.state_version = reloaded_state.state_version
                            continue
                        else:
                            Console.warn(
                                f"[StateManager] Failed to save state after {self.max_retries} attempts "
                                f"(EquipID={state.equip_id})",
                                component="STATE", equip_id=state.equip_id, max_retries=self.max_retries
                            )
                            return False
                else:
                    # INSERT new state
                    cur.execute(
                        """
                        INSERT INTO dbo.ACM_ForecastingState 
                        (EquipID, StateVersion, ModelCoefficientsJson, LastForecastJson, LastRetrainTime, 
                         TrainingDataHash, DataVolumeAnalyzed, RecentMAE, RecentRMSE, RetriggerReason,
                         CreatedAt, UpdatedAt)
                        VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())
                        """,
                        (
                            state.equip_id,
                            model_coeff_json,
                            last_forecast_json,
                            state.last_retrain_time,
                            state.training_data_hash,
                            state.data_volume_analyzed,
                            state.recent_mae,
                            state.recent_rmse,
                            state.retrigger_reason
                        )
                    )
                
                if not self.sql_client.conn.autocommit:
                    self.sql_client.conn.commit()
                
                cur.close()
                
                Console.info(f"Saved state for EquipID={state.equip_id}", component="STATE")
                return True
                
            except Exception as e:
                Console.warn(f"Failed to save state (attempt {attempt + 1}): {e}", component="STATE", equip_id=state.equip_id, attempt=attempt + 1, max_retries=self.max_retries, error_type=type(e).__name__, error=str(e)[:200])
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delays[attempt])
                else:
                    return False
        
        return False


class AdaptiveConfigManager:
    """
    Manages adaptive configuration with equipment-specific overrides.
    
    Configuration Hierarchy:
    1. Equipment-specific config (EquipID != NULL)
    2. Global defaults (EquipID = NULL)
    3. Hardcoded fallbacks
    
    Auto-Tuning:
    - Triggered when DataVolume exceeds auto_tune_data_threshold
    - Grid search over parameter bounds (MinBound, MaxBound)
    - Updates config with IsLearned=1, DataVolumeAtTuning=current_volume
    
    Usage:
        config_mgr = AdaptiveConfigManager(sql_client=sql_client)
        
        # Get config (with equipment override)
        alpha = config_mgr.get_config(equip_id=1, key='alpha', default=0.3)
        
        # Check if tuning needed
        if config_mgr.should_tune(equip_id=1, current_volume=15000):
            # Run grid search...
            config_mgr.update_config(equip_id=1, key='alpha', value=0.25, is_learned=True)
    """
    
    def __init__(self, sql_client: Any):
        """
        Initialize adaptive config manager.
        
        Args:
            sql_client: Database connection (pyodbc)
        """
        self.sql_client = sql_client
        self._cache: Dict[str, Dict[str, Any]] = {}  # Cache for loaded configs
    
    def get_config(self, equip_id: Optional[int], key: str, default: Any = None) -> Any:
        """
        Get configuration value with equipment-specific override.
        
        Lookup Order:
        1. Equipment-specific config (EquipID = equip_id)
        2. Global default (EquipID = NULL)
        3. Provided default value
        
        Args:
            equip_id: Equipment ID (None for global-only lookup)
            key: Config key name (e.g., 'alpha', 'beta', 'failure_threshold')
            default: Fallback value if key not found
        
        Returns:
            Config value (type depends on ConfigValue column)
        """
        try:
            cur = self.sql_client.cursor()
            
            # Try equipment-specific first
            if equip_id is not None:
                cur.execute(
                    "SELECT ConfigValue FROM dbo.ACM_AdaptiveConfig WHERE EquipID = ? AND ConfigKey = ?",
                    (equip_id, key)
                )
                row = cur.fetchone()
                if row:
                    cur.close()
                    return self._parse_config_value(row.ConfigValue)
            
            # Fall back to global default
            cur.execute(
                "SELECT ConfigValue FROM dbo.ACM_AdaptiveConfig WHERE EquipID IS NULL AND ConfigKey = ?",
                (key,)
            )
            row = cur.fetchone()
            cur.close()
            
            if row:
                return self._parse_config_value(row.ConfigValue)
            else:
                return default
                
        except Exception as e:
            Console.warn(f"Failed to get config '{key}': {e}", component="CONFIG", config_key=key, equip_id=equip_id, error_type=type(e).__name__, error=str(e)[:200])
            return default
    
    def get_all_configs(self, equip_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get all configuration values for equipment (with global fallbacks).
        
        Args:
            equip_id: Equipment ID (None for global-only)
        
        Returns:
            Dictionary of config key-value pairs
        """
        configs = {}
        
        try:
            cur = self.sql_client.cursor()
            
            # Load all configs (equipment-specific + global)
            if equip_id is not None:
                cur.execute(
                    """
                    SELECT ConfigKey, ConfigValue, EquipID
                    FROM dbo.ACM_AdaptiveConfig
                    WHERE EquipID IS NULL OR EquipID = ?
                    ORDER BY EquipID DESC  -- Equipment-specific first
                    """,
                    (equip_id,)
                )
            else:
                cur.execute("SELECT ConfigKey, ConfigValue FROM dbo.ACM_AdaptiveConfig WHERE EquipID IS NULL")
            
            rows = cur.fetchall()
            cur.close()
            
            # Build config dict (equipment-specific overrides global)
            for row in rows:
                key = row.ConfigKey
                if key not in configs:  # First occurrence wins (equipment-specific due to ORDER BY)
                    configs[key] = self._parse_config_value(row.ConfigValue)
            
            return configs
            
        except Exception as e:
            Console.warn(f"Failed to load all configs: {e}", component="CONFIG", equip_id=equip_id, error_type=type(e).__name__, error=str(e)[:200])
            return {}
    
    def should_tune(self, equip_id: int, current_volume: int) -> bool:
        """
        Check if auto-tuning should be triggered based on data volume.
        
        Tuning Logic:
        - auto_tune_data_threshold = config value (default 10000)
        - Trigger when: current_volume >= threshold AND (last_tuned_volume + threshold) <= current_volume
        - Prevents re-tuning on every batch after threshold
        
        Args:
            equip_id: Equipment ID
            current_volume: Current total data volume (rows)
        
        Returns:
            True if tuning should be triggered, False otherwise
        """
        threshold = self.get_config(equip_id, 'auto_tune_data_threshold', default=10000)
        threshold = int(threshold)
        
        if current_volume < threshold:
            return False
        
        # Check last tuning volume
        try:
            cur = self.sql_client.cursor()
            cur.execute(
                """
                SELECT MAX(DataVolumeAtTuning) 
                FROM dbo.ACM_AdaptiveConfig 
                WHERE EquipID = ? AND IsLearned = 1
                """,
                (equip_id,)
            )
            row = cur.fetchone()
            cur.close()
            
            last_tuned_volume = row[0] if row and row[0] else 0
            
            # Trigger if volume increased by threshold since last tuning
            return (current_volume - last_tuned_volume) >= threshold
            
        except Exception as e:
            Console.warn(f"Failed to check tuning status: {e}", component="CONFIG", equip_id=equip_id, current_volume=current_volume, error_type=type(e).__name__, error=str(e)[:200])
            return False
    
    def update_config(
        self,
        equip_id: int,
        key: str,
        value: Any,
        is_learned: bool = True,
        data_volume: Optional[int] = None
    ) -> bool:
        """
        Update equipment-specific config value (auto-tuning result).
        
        Args:
            equip_id: Equipment ID
            key: Config key name
            value: New config value
            is_learned: Flag indicating value was learned via tuning (default True)
            data_volume: Data volume at which tuning occurred
        
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            cur = self.sql_client.cursor()
            
            # Check if equipment-specific config exists
            cur.execute(
                "SELECT COUNT(*) FROM dbo.ACM_AdaptiveConfig WHERE EquipID = ? AND ConfigKey = ?",
                (equip_id, key)
            )
            exists = cur.fetchone()[0] > 0
            
            if exists:
                # UPDATE existing equipment-specific config
                cur.execute(
                    """
                    UPDATE dbo.ACM_AdaptiveConfig
                    SET ConfigValue = ?, IsLearned = ?, DataVolumeAtTuning = ?, UpdatedAt = GETDATE()
                    WHERE EquipID = ? AND ConfigKey = ?
                    """,
                    (str(value), 1 if is_learned else 0, data_volume, equip_id, key)
                )
            else:
                # INSERT new equipment-specific config (copy bounds from global)
                cur.execute(
                    """
                    INSERT INTO dbo.ACM_AdaptiveConfig 
                    (EquipID, ConfigKey, ConfigValue, MinBound, MaxBound, IsLearned, 
                     DataVolumeAtTuning, ResearchReference, Source, CreatedAt, UpdatedAt)
                    SELECT ?, ConfigKey, ?, MinBound, MaxBound, ?, ?, ResearchReference, 
                           'AutoTuned', GETDATE(), GETDATE()
                    FROM dbo.ACM_AdaptiveConfig
                    WHERE EquipID IS NULL AND ConfigKey = ?
                    """,
                    (equip_id, str(value), 1 if is_learned else 0, data_volume, key)
                )
            
            if not self.sql_client.conn.autocommit:
                self.sql_client.conn.commit()
            
            cur.close()
            
            Console.info(f"Updated config: EquipID={equip_id}, {key}={value}", component="CONFIG")
            return True
            
        except Exception as e:
            Console.warn(f"Failed to update config '{key}': {e}", component="CONFIG", equip_id=equip_id, config_key=key, config_value=str(value)[:50], error_type=type(e).__name__, error=str(e)[:200])
            return False
    
    def _parse_config_value(self, value: Any) -> Any:
        """Parse config value to appropriate type (handles both string and numeric SQL types)"""
        # If already numeric, return as-is
        if isinstance(value, (int, float)):
            # Convert to int if it's a whole number
            if isinstance(value, float) and value == int(value):
                return int(value)
            return value
        
        # Handle string values
        if isinstance(value, str):
            try:
                # Try int
                if '.' not in value:
                    return int(value)
                # Try float
                return float(value)
            except ValueError:
                # Return as string
                return value
        
        # Return as-is for other types
        return value

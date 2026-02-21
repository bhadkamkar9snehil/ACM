"""
Unified Output Manager for ACM
==============================

Consolidates all scattered output generation into a single, efficient system:
- Batched file writes with intelligent buffering
- Smart SQL/file dual-write coordination with caching
- Single point of control for all CSV, JSON, and model outputs
- Performance optimizations: vectorized operations, reduced I/O
- Unified error handling and logging

This replaces scattered to_csv() calls throughout the codebase and provides
consistent behavior for all output operations.
"""

from __future__ import annotations
# pyright: reportGeneralTypeIssues=false

import json
import time
import math
import gc
import threading
from pathlib import Path
from contextlib import contextmanager, nullcontext
from typing import Dict, Any, List, Optional, Union, Tuple, TypeVar, Callable, cast, Set
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np
import warnings 
from datetime import datetime, timezone

# FOR-DQ-02: Use centralized timestamp normalization
from utils.timestamp_utils import (
    normalize_timestamp_scalar,
    normalize_timestamp_series,
    normalize_timestamps,
    normalize_index
)

from utils.detector_labels import get_detector_label, format_culprit_label

from core.observability import Console

# Phase 2 Extraction: Data loading moved to core/data_loader.py
from core.data_loader import (
    DataLoader,
    DataMeta,  # Re-exported for backward compatibility
    parse_ts_index as _parse_ts_index,
    coerce_local_and_filter_future as _coerce_local_and_filter_future,
    infer_numeric_cols as _infer_numeric_cols,
    native_cadence_secs as _native_cadence_secs,
    check_cadence as _check_cadence,
    resample_df as _resample,
)

# Phase 3 Extraction: Analytics generation moved to core/analytics_builder.py
from core.analytics_builder import (
    AnalyticsBuilder,
    AnalyticsConstants as _AnalyticsConstants,  # Re-exported for backward compat
    health_index as _health_index_impl,
)

# V11: Confidence model for health and episode confidence
try:
    from core.confidence import compute_health_confidence, compute_episode_confidence
    _CONFIDENCE_AVAILABLE = True
except ImportError:
    _CONFIDENCE_AVAILABLE = False
    compute_health_confidence = None
    compute_episode_confidence = None

# V11: Model lifecycle for maturity state
try:
    from core.model_lifecycle import load_model_state_from_sql, MaturityState
    _LIFECYCLE_AVAILABLE = True
except ImportError:
    _LIFECYCLE_AVAILABLE = False
    load_model_state_from_sql = None
    MaturityState = None

# Optional observability integration (P0 SQL ops tracking)
try:
    from core.observability import record_sql_op, Span
    _OBSERVABILITY_AVAILABLE = True
except ImportError:
    _OBSERVABILITY_AVAILABLE = False
    record_sql_op = None
    Span = None

# =============================================================================
# ALLOWED_TABLES - v11.0.0 Functionality-Based Table Set
# =============================================================================
# DESIGN PRINCIPLE: Tables chosen based on ACM's core mission:
#   1. What is current health? (HealthTimeline, Scores, Episodes)
#   2. If not healthy, what's the reason? (SensorDefects, Hotspots, Culprits)
#   3. What will future health look like? (RUL, Forecasts)
#   4. What will cause future degradation? (SensorForecast, Drift, Contributions)
#
# Additional tables support: data persistence, model evolution, diagnostics
#
# See docs/ACM_OUTPUT_TABLES_REFINED.md for complete rationale.
#
# TIER 1 - CURRENT STATE (What's happening NOW?)
# TIER 2 - FUTURE STATE (What will happen?)
# TIER 3 - ROOT CAUSE (WHY is this happening/will happen?)
# TIER 4 - DATA & MODEL MANAGEMENT (Long-term storage, model building)
# TIER 5 - OPERATIONS & AUDIT (Is ACM working? What changed?)
# TIER 6 - ADVANCED ANALYTICS (Deep patterns and trends)
# TIER 7 - V11 NEW FEATURES (Typed contracts, maturity lifecycle, seasonality)
# =============================================================================

ALLOWED_TABLES = {
    # TIER 1: CURRENT STATE (6 tables) - Answers "What is current health?"
    'ACM_HealthTimeline',        # Health history + current state
    'ACM_Scores_Wide',           # All 6 detector scores per timestamp
    'ACM_Episodes',              # Active and historical anomaly events
    'ACM_RegimeTimeline',        # Operating mode context
    'ACM_SensorDefects',         # Which sensors are problematic NOW
    'ACM_SensorHotspots',        # Top culprit sensors ranked
    
    # TIER 2: FUTURE STATE (5 tables) - Answers "What will future health look like?"
    'ACM_RUL',                   # When will it fail? (Remaining Useful Life)
    'ACM_HealthForecast',        # Projected health trajectory with confidence bounds
    'ACM_FailureForecast',       # Failure probability over time
    'ACM_SensorForecast',        # Physical sensor value predictions
    'ACM_MultivariateForecast',  # Multivariate sensor forecast with correlations
    
    # TIER 3: ROOT CAUSE (6 tables) - Answers "Why?" (current + future)
    'ACM_EpisodeCulprits',       # What caused each episode
    'ACM_EpisodeDiagnostics',    # Episode details and severity
    'ACM_DetectorCorrelation',   # How detectors relate (model quality)
    'ACM_DriftSeries',           # Behavior changes that lead to degradation
    'ACM_SensorCorrelations',    # Multivariate sensor relationships (correlation matrix)
    'ACM_FeatureDropLog',        # Why features were dropped (quality issues)
    'ACM_OMR_Diagnostics',       # OMR detector diagnostics
    
    # TIER 4: DATA & MODEL MANAGEMENT (10 tables) - Long-term storage, enables progressive learning
    'ACM_BaselineBuffer',        # Raw sensor data accumulation for training
    'ACM_HistorianData',         # Cached historian data for efficiency
    'ACM_SensorNormalized_TS',   # Normalized sensor time series
    'ACM_DataQuality',           # Input data health metrics
    'ACM_ForecastingState',      # Forecast model state persistence
    'ACM_CalibrationSummary',    # Model quality tracking over time
    'ACM_AdaptiveConfig',        # Auto-tuned configuration
    'ACM_RefitRequests',         # Model retraining requests and acknowledgements
    'ACM_PCA_Metrics',           # PCA component metrics and explained variance
    'ACM_RunMetadata',           # Detailed run context (batch info, data ranges)
    
    # TIER 5: OPERATIONS & AUDIT (6 tables) - Is ACM working? What changed?
    'ACM_Runs',                  # Execution tracking and status
    'ACM_RunLogs',               # Detailed logs for troubleshooting
    # Observability stack (Tempo/Prometheus/Loki) handles timing metrics
    'ACM_RunMetrics',            # Fusion quality metrics (EAV format)
    'ACM_Run_Stats',             # Run-level statistics
    'ACM_Config',                # Current configuration
    'ACM_ConfigHistory',         # Configuration change audit trail
    
    # TIER 6: ADVANCED ANALYTICS (5 tables) - Deep insights and patterns
    'ACM_RegimeOccupancy',       # Operating mode utilization
    'ACM_RegimeTransitions',     # Mode switching patterns
    'ACM_Regime_Episodes',       # Regime episode tracking
    'ACM_RegimePromotionLog',    # Regime maturity evolution tracking
    'ACM_RegimeState',           # Regime model state persistence (KMeans params, scaler, PCA)
    'ACM_ContributionTimeline',  # Historical sensor attribution for pattern analysis
    'ACM_DriftController',       # Drift detection control and thresholds
    'ACM_PCA_Models',            # PCA model metadata
    'ACM_PCA_Loadings',          # PCA component loadings per sensor
    'ACM_Anomaly_Events',        # Anomaly event records
    
    # TIER 7: V11 NEW FEATURES (4 tables) - Advanced capabilities from v11.0.0
    'ACM_RegimeDefinitions',     # Regime centroids and metadata (MaturityState lifecycle)
    'ACM_ActiveModels',          # Active model versions per equipment
    'ACM_DataContractValidation',# Data quality validation at pipeline entry
    'ACM_SeasonalPatterns',      # Detected seasonal patterns (diurnal, weekly)
}

# ============================================================================
# DATETIME COLUMN REGISTRY (Phase 1 Schema Fix)
# ============================================================================
# Centralized constant for all columns requiring datetime handling.
# This replaces heuristic detection like "'timestamp' in c.lower()" which
# missed columns like StartTime, EndTime, LastUpdate, CreatedAt, etc.
DATETIME_COLUMNS: Set[str] = {
    # Standard timestamps
    'Timestamp', 'timestamp', 'Date', 'date', 'EntryDateTime',
    # Window/range columns
    'StartTime', 'EndTime', 'start_ts', 'end_ts', 'WindowStart', 'WindowEnd',
    # Audit columns
    'CreatedAt', 'UpdatedAt', 'ModifiedAt', 'CompletedAt', 'StartedAt', 'LoggedAt', 'DetectedAt',
    # Forecast columns
    'ForecastTime', 'EarliestMaintenance', 'LatestMaintenance', 'FailureTime',
    # Validity columns
    'LastUpdate', 'ValidFrom', 'ValidTo',
}

def _table_exists(cursor_factory: Callable[[], Any], name: str) -> bool:
    cur = None
    try:
        cur = cursor_factory()
        cur.execute(f"SELECT TOP 0 * FROM dbo.[{name}]")
        return True
    except Exception:
        return False
    finally:
        try:
            if cur is not None:
                cur.close()
        except Exception:
            pass

def _get_table_columns(cursor_factory: Callable[[], Any], name: str) -> List[str]:
    """Return the list of column names for a table by probing TOP 0."""
    cur = cursor_factory()
    try:
        cur.execute(f"SELECT TOP 0 * FROM dbo.[{name}]")
        return [d[0] for d in (cur.description or [])]
    finally:
        try:
            cur.close()
        except Exception:
            pass

def _get_insertable_columns(cursor_factory: Callable[[], Any], name: str) -> List[str]:
    """Return columns excluding identity columns for safe INSERT.
    Uses sys.columns joined via OBJECT_ID('schema.table') without square brackets.
    """
    cur = cursor_factory()
    try:
        # OBJECT_ID expects a schema-qualified name without brackets
        cur.execute(
            "SELECT c.name, c.is_identity FROM sys.columns c WHERE c.object_id = OBJECT_ID(?)",
            (f"dbo.{name}",)
        )
        rows = cur.fetchall() or []
        return [r[0] for r in rows if not getattr(r, 'is_identity', r[1])]
    finally:
        try:
            cur.close()
        except Exception:
            pass

# constants for analytics & guardrails (re-exported from analytics_builder for backward compat)
AnalyticsConstants = _AnalyticsConstants

# CHART-12: Centralized severity color palette
SEVERITY_COLORS = {
    "CRITICAL": "#dc2626",  # Red - immediate action required
    "HIGH": "#f97316",      # Orange - urgent attention
    "MEDIUM": "#f59e0b",    # Amber - monitor closely
    "LOW": "#10b981",       # Green - informational
    "INFO": "#10b981",      # Alias for LOW
    "WARNING": "#f59e0b",   # Alias for MEDIUM
}

# Tables that require UPSERT instead of INSERT (to handle duplicate key conflicts)
# Maps table name -> upsert method name (method must exist on OutputManager)
UPSERT_TABLES: Dict[str, str] = {
    "ACM_HealthForecast": "_upsert_health_forecast",
    "ACM_FailureForecast": "_upsert_failure_forecast",
    "ACM_SensorForecast": "_upsert_sensor_forecast",
    "ACM_DetectorForecast_TS": "_upsert_detector_forecast_ts",
    "ACM_PCA_Metrics": "_upsert_pca_metrics",
}

# Enhanced config getter with typing
T = TypeVar("T")

def _cfg_get(cfg: Dict[str, Any], path: str, default: T) -> T:
    """Get config value by dot path with type preservation."""
    keys = path.split('.')
    current: Any = cfg
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current  # type: ignore[return-value]


def _future_cutoff_ts(cfg: Dict[str, Any]) -> pd.Timestamp:
    """Return timestamp cutoff that optionally allows future data via config."""
    raw_value = _cfg_get(cfg, "runtime.future_grace_minutes", 0) or 0
    try:
        minutes = int(raw_value)
    except (TypeError, ValueError):
        minutes = 0
    minutes = max(0, minutes)
    return pd.Timestamp.now() + pd.Timedelta(minutes=minutes)

# ==================== DATA LOADING ====================
# Data loading functions extracted to core/data_loader.py (Phase 2)
# DataMeta, _parse_ts_index, _coerce_local_and_filter_future, _infer_numeric_cols,
# _native_cadence_secs, _check_cadence, _resample are all imported from data_loader
# and re-exported for backward compatibility.

# Phase 3: _health_index delegated to analytics_builder.health_index
def _health_index(fused_z, z_threshold: float = 5.0, steepness: float = 1.5):
    """Backward compat wrapper - delegates to core.analytics_builder.health_index."""
    return _health_index_impl(fused_z, z_threshold, steepness)


# ==================== MAIN OUTPUT MANAGER CLASS ====================


@dataclass
class OutputBatch:
    """Represents a batch of outputs to be written together."""
    sql_operations: List[Tuple[str, pd.DataFrame, Dict[str, Any]]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # OUT-18: Batch tracking for flush triggers
    created_at: float = field(default_factory=time.time)
    total_rows: int = 0


class OutputManager:
    """
    Unified output manager that consolidates all scattered output generation.
    
    Features:
    - Batched writes for improved I/O performance
    - Smart SQL health checking with caching
    - Automatic file/SQL dual-write coordination
    - Thread-safe operations with connection pooling
    - Intelligent error handling and fallback strategies
    """
    
    def __init__(self, 
                 sql_client=None, 
                 run_id: Optional[str] = None,
                 equip_id: Optional[int] = None,
                 batch_size: int = 5000,
                 enable_batching: bool = True,
                 sql_health_cache_seconds: float = 60.0,
                 max_io_workers: int = 8,
                 batch_flush_rows: int = 1000,
                 batch_flush_seconds: float = 30.0,
                 max_in_flight_futures: int = 50,
                 maturity_state: Optional[str] = None):
        """Initialize OutputManager.
        
        V11 CRITICAL: maturity_state must be passed from acm_main.py run context.
        This eliminates the race condition where writers query ACM_ActiveModels
        independently and get stale/inconsistent state.
        """
        self.sql_client = sql_client
        self.run_id = run_id
        
        # PHASE-1 FIX: Fail-fast for invalid EquipID in SQL mode
        # Writing EquipID=0 or NULL corrupts multi-asset queries and is unrecoverable.
        if sql_client is not None and (equip_id is None or equip_id == 0):
            raise ValueError(
                f"OutputManager requires valid equip_id (>0) in SQL mode. "
                f"Received equip_id={equip_id}. This prevents catastrophic "
                f"data corruption in multi-asset deployments."
            )
        self.equip_id = equip_id
        self.equipment = ""  # Will be set by set_equipment() or inferred from equip_id
        self.maturity_state = maturity_state or 'COLDSTART'  # V11: Cached maturity
        self.batch_size = batch_size
        self._batched_transaction_active = False
        self.enable_batching = enable_batching
        self.max_io_workers = max_io_workers
        
        # OUT-18: Batch flush triggers and backpressure
        self.batch_flush_rows = batch_flush_rows  # Flush after N rows
        self.batch_flush_seconds = batch_flush_seconds  # Flush after N seconds
        self.max_in_flight_futures = max_in_flight_futures  # Max concurrent operations

        self.stats = {
            'sql_writes': 0,
            'total_rows': 0,
            'sql_health_checks': 0,
            'sql_failures': 0,
            'write_time': 0.0
        }

        self._sql_health_cache: Tuple[float, bool] = (0.0, False)
        self._sql_health_cache_duration = sql_health_cache_seconds

        self._current_batch = OutputBatch()
        self._batch_lock = threading.Lock()
        
        # OUT-18: Track in-flight operations for backpressure
        self._in_flight_futures: List[Any] = []  # List of active futures
        self._futures_lock = threading.Lock()

        # lightweight caches for table probes
        self._table_exists_cache: Dict[str, bool] = {}
        self._table_columns_cache: Dict[str, set] = {}
        self._table_insertable_cache: Dict[str, set] = {}
        
        # PERF-OPT: Track tables that have been bulk pre-deleted (skip individual DELETE)
        self._bulk_predeleted_tables: set = set()
        
        # FCST-15: Artifact cache for SQL-only mode
        # Stores DataFrames written to files/SQL so they can be consumed by downstream modules
        # without file system dependencies
        self._artifact_cache: Dict[str, pd.DataFrame] = {}

        Console.info(f"Manager initialized (batch_size={batch_size}, batching={'ON' if enable_batching else 'OFF'}, sql_cache={sql_health_cache_seconds}s, io_workers={max_io_workers}, flush={batch_flush_rows} rows/{batch_flush_seconds}s, max_futures={max_in_flight_futures})", component="OUTPUT")
    
    def set_maturity_state(self, maturity_state: str) -> None:
        """V11 CRITICAL: Update maturity state after model lifecycle is computed.
        
        This MUST be called from acm_main.py after model_state is determined.
        Eliminates the race condition where writers query ACM_ActiveModels independently.
        
        Args:
            maturity_state: One of 'COLDSTART', 'LEARNING', 'CONVERGED', 'DEPRECATED'
        """
        self.maturity_state = maturity_state
        Console.info(f"OutputManager maturity_state set to {maturity_state}", component="OUTPUT")
    
    @contextmanager
    def batched_transaction(self):
        """
        Context manager for writing multiple tables in a single transaction.
        Improves performance by reducing commit overhead when writing many tables.
        
        Usage:
            with output_mgr.batched_transaction():
                output_mgr.write_table("Table1", df1, "sql")
                output_mgr.write_table("Table2", df2, "sql")
                # Single commit after all writes
        """
        if self._batched_transaction_active:
            # Nested transaction - just pass through
            yield
            return
        
        if self.sql_client is None:
            # No SQL client - just pass through
            yield
            return
        
        # Check SQL health ONCE at transaction entry
        if not self._check_sql_health():
            Console.error("SQL unhealthy at transaction start - aborting", component="OUTPUT", equip_id=self.equip_id)
            yield
            return
        
        self._batched_transaction_active = True
        start_time = time.time()
        
        try:
            yield
            # Commit at end of transaction
            self.sql_client.commit()
            elapsed = time.time() - start_time
            Console.info(f"Batched transaction committed ({elapsed:.2f}s)", component="OUTPUT")
        except Exception as e:
            # Rollback on error
            try:
                self.sql_client.rollback()
            except Exception:
                pass  # Rollback failed, original exception more important
            Console.error(f"Batched transaction rolled back: {e}", component="OUTPUT", equip_id=self.equip_id, run_id=self.run_id, error_type=type(e).__name__)
            raise
        finally:
            self._batched_transaction_active = False
    
    def _load_data_from_sql(self, cfg: Dict[str, Any], equipment_name: str, start_utc: Optional[pd.Timestamp], end_utc: Optional[pd.Timestamp], is_coldstart: bool = False):
        """
        Load training and scoring data from SQL historian using stored procedure.
        
        Delegates to DataLoader class (extracted in Phase 2 debloating).
        
        Args:
            cfg: Configuration dictionary
            equipment_name: Equipment name (e.g., 'FD_FAN', 'GAS_TURBINE')
            start_utc: Start time for query window
            end_utc: End time for query window
            is_coldstart: If True, split data for coldstart training. If False, use all data for scoring.
        
        Returns:
            Tuple of (train_df, score_df, DataMeta)
        """
        loader = DataLoader(self.sql_client)
        return loader.load_from_sql(cfg, equipment_name, start_utc, end_utc, is_coldstart)
    
    def _check_sql_health(self) -> bool:
        """Check SQL availability with caching for performance.
        
        Optimization: Skip check entirely during batched transactions.
        If we entered the transaction successfully, SQL is healthy.
        """
        if self.sql_client is None:
            return False
        
        # PERF: Inside batched transaction, trust SQL is healthy (checked once at entry)
        if self._batched_transaction_active:
            return True
        
        now = time.time()
        last_check, last_result = self._sql_health_cache
        
        # Use cached result if fresh
        if now - last_check < self._sql_health_cache_duration:
            return last_result
        
        # Perform health check
        try:
            cur = self.sql_client.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            self._sql_health_cache = (now, True)
            self.stats['sql_health_checks'] += 1
            return True
        except Exception as e:
            self._sql_health_cache = (now, False)
            self.stats['sql_health_checks'] += 1
            self.stats['sql_failures'] += 1
            Console.error(f"SQL health check failed: {e}", component="OUTPUT", equip_id=self.equip_id, error_type=type(e).__name__, error=str(e)[:200])
            return False
        finally:
            try:
                if 'cur' in locals():
                    cur.close()
            except Exception:
                pass
    
    def _prepare_dataframe_for_sql(self, df: pd.DataFrame, non_numeric_cols: Optional[set] = None) -> pd.DataFrame:
        """Prepare DataFrame for SQL insertion with robust type coercion (SQL Server safe)."""
        if df.empty:
            return df

        out = df.copy()
        non_numeric_cols = set(non_numeric_cols or set())

        # Helper: name-based timestamp detection to handle object/string timestamp columns too
        def _looks_like_ts(col_name: str) -> bool:
            c = (col_name or "").lower()
            return c in {"timestamp", "time", "ts", "datetime"} or c.endswith("_ts") or c.endswith("_time") or c.endswith("_timestamp")

        # 1) Normalize datetime columns (dtype-based) + timestamp-like object columns (name-based)
        for col in out.columns:
            is_dt = pd.api.types.is_datetime64_any_dtype(out[col])
            is_obj_ts = (not is_dt) and _looks_like_ts(col) and out[col].dtype == object

            if is_dt or is_obj_ts:
                ts_series = pd.to_datetime(out[col], errors="coerce")
                # drop timezone if present, keep UTC-naive convention
                try:
                    ts_series = ts_series.dt.tz_localize(None)
                except Exception:
                    pass
                ts_series = ts_series.dt.floor("s")

                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=".*to_pydatetime.*", category=FutureWarning)
                    out[col] = np.array(ts_series.dt.to_pydatetime())

        # 2) Replace Inf/-Inf and NaNs to None (SQL-friendly)
        # Use float types only for isinf check - nullable integers (Int64) don't support isinf
        float_only = out.select_dtypes(include=[np.floating])
        inf_count = 0
        if not float_only.empty:
            try:
                inf_count = int(np.isinf(float_only.values).sum())
            except TypeError:
                # Fallback: check column-by-column for mixed types
                for col in float_only.columns:
                    col_vals = float_only[col].dropna()
                    if len(col_vals) > 0:
                        try:
                            inf_count += int(np.isinf(col_vals.values).sum())
                        except TypeError:
                            pass
        if inf_count > 0:
            Console.warn(
                f"Replaced {inf_count} Inf/-Inf values with None for SQL compatibility",
                component="OUTPUT",
                inf_count=inf_count,
                columns=len(float_only.columns),
            )

        out = out.replace({np.inf: None, -np.inf: None})
        # Note: do NOT blanket-coerce everything to object early; keep types until after numeric handling

        # 3) Preserve integer types for known ID-like columns (case-insensitive)
        integer_columns_ci = {c.lower() for c in {"EquipID", "equip_id", "episode_id", "EpisodeID", "RegimeLabel", "regime_label"}}

        for col in out.columns:
            col_l = col.lower()

            # Skip caller-marked non-numeric columns for numeric coercion only
            # (but do NOT skip boolean normalization; booleans must become int for SQL)
            if pd.api.types.is_bool_dtype(out[col]):
                out[col] = out[col].astype(object).where(pd.isna(out[col]), out[col].astype(int))
                continue

            if col_l in integer_columns_ci and pd.api.types.is_numeric_dtype(out[col]):
                out[col] = out[col].astype("Int64")  # nullable integer
                continue

            if col in non_numeric_cols:
                continue

            if pd.api.types.is_numeric_dtype(out[col]):
                out[col] = out[col].astype(float)

        # 4) Finally, normalize NaN/NaT to None for pyodbc binding
        out = out.where(pd.notnull(out), None)

        return out
    
    
    def _should_auto_flush(self) -> bool:
        """OUT-18: Check if batch should be automatically flushed based on triggers."""
        with self._batch_lock:
            # Size-based trigger
            if self._current_batch.total_rows >= self.batch_flush_rows:
                return True
            
            # Time-based trigger
            batch_age = time.time() - self._current_batch.created_at
            if batch_age >= self.batch_flush_seconds:
                return True
            
            return False
    
    def _wait_for_futures_capacity(self) -> None:
        """OUT-18: Block if too many in-flight operations (backpressure)."""
        while True:
            with self._futures_lock:
                # Clean up completed futures
                self._in_flight_futures = [f for f in self._in_flight_futures if not f.done()]
                
                # If we have capacity, proceed
                if len(self._in_flight_futures) < self.max_in_flight_futures:
                    break
            
            # Wait a bit before checking again
            time.sleep(0.1)
    
    def write_dataframe(
        self,
        df: pd.DataFrame,
        artifact_name: str,
        sql_table: Optional[str] = None,
        sql_columns: Optional[Dict[str, str]] = None,
        non_numeric_cols: Optional[set] = None,
        add_created_at: bool = False,
        required: bool = False,
    ) -> Dict[str, Any]:
        """
        Write DataFrame to SQL (SQL-only; file output removed).

        Args:
            df: DataFrame to write
            artifact_name: Logical name for the artifact (used for caching/logging)
            sql_table: Optional SQL table name. If None, no SQL write is attempted.
            sql_columns: Optional column mapping for SQL (df_col -> sql_col)
            non_numeric_cols: Set of columns to treat as non-numeric for SQL preparation
            add_created_at: Whether to add CreatedAt timestamp column for SQL
            required: If True, raise on write failure; if False, log warning and continue (default False for backwards-compat)

        Returns:
            Dict with SQL write results and metadata.
        """
        start_time = time.time()

        result: Dict[str, Any] = {
            "sql_written": False,
            "rows": int(len(df)),
            "inserted": 0,
            "error": None,
            "sql_table": sql_table,
            "artifact": artifact_name,
        }

        # OUT-18: auto-flush before write if needed
        if self._should_auto_flush():
            Console.info(
                f"Auto-flushing batch (rows={self._current_batch.total_rows}, age={time.time() - self._current_batch.created_at:.1f}s)",
                component="OUTPUT",
            )
            self.flush()

        # OUT-18: backpressure
        self._wait_for_futures_capacity()

        # Track rows in current batch regardless of whether we write to SQL
        with self._batch_lock:
            self._current_batch.total_rows += len(df)

        sql_df: Optional[pd.DataFrame] = None

        try:
            # If no sql_table requested, skip SQL quietly
            if not sql_table:
                return result

            # Guard: Only write to ALLOWED_TABLES (contract enforcement)
            if sql_table not in ALLOWED_TABLES:
                Console.warn(
                    f"Table '{sql_table}' not in ALLOWED_TABLES; skipping write",
                    component="OUTPUT",
                    table=sql_table,
                    rows=len(df),
                )
                result["error"] = f"Table '{sql_table}' not in ALLOWED_TABLES"
                return result

            # Skip empty DataFrames (no-op)
            if df.empty:
                return result

            # If SQL unhealthy, fail appropriately based on required flag
            if not self._check_sql_health():
                msg = f"SQL health check failed; cannot write to {sql_table}"
                result["error"] = msg
                if required:
                    Console.error(msg, component="OUTPUT", table=sql_table, rows=len(df), equip_id=self.equip_id)
                    raise RuntimeError(msg)
                else:
                    Console.warn(msg, component="OUTPUT", table=sql_table, rows=len(df), equip_id=self.equip_id)
                    return result

            # Prepare data for SQL
            sql_df = self._prepare_dataframe_for_sql(df, non_numeric_cols or set())

            # Apply column mapping (df_col -> sql_col)
            if sql_columns:
                mapped_source_cols = [c for c in sql_columns.keys() if c in sql_df.columns]
                sql_df = sql_df[mapped_source_cols].rename(columns=sql_columns)

            # Required metadata columns (all SQL tables)
            # Note: equip_id validated in __init__, run_id should be set by caller
            if "RunID" not in sql_df.columns:
                if not self.run_id:
                    raise ValueError("RunID is required but not set on OutputManager")
                sql_df["RunID"] = self.run_id
            if "EquipID" not in sql_df.columns:
                sql_df["EquipID"] = self.equip_id  # Already validated in __init__

            # CreatedAt is optional and explicitly requested
            if add_created_at and "CreatedAt" not in sql_df.columns:
                sql_df["CreatedAt"] = pd.Timestamp.now().tz_localize(None)

            # Special-case: avoid PK collisions for maintenance recommendation (keep as-is)
            if sql_table == "ACM_MaintenanceRecommendation" and self.sql_client is not None:
                try:
                    with self.sql_client.cursor() as cur:
                        cur.execute(
                            "DELETE FROM dbo.[ACM_MaintenanceRecommendation] WHERE RunID = ? AND EquipID = ?",
                            (self.run_id, int(self.equip_id or 0)),
                        )
                    # Commit semantics: support both patterns
                    if hasattr(self.sql_client, "commit"):
                        self.sql_client.commit()
                    elif hasattr(self.sql_client, "conn") and hasattr(self.sql_client.conn, "commit"):
                        if not getattr(self.sql_client.conn, "autocommit", True):
                            self.sql_client.conn.commit()
                except Exception as del_ex:
                    Console.warn(
                        f"Pre-delete failed for {sql_table}: {del_ex}",
                        component="OUTPUT",
                        table=sql_table,
                        equip_id=self.equip_id,
                        run_id=self.run_id,
                        error_type=type(del_ex).__name__,
                    )

            # Route upsert tables via UPSERT_TABLES dict, else bulk insert
            upsert_method = UPSERT_TABLES.get(sql_table)
            if upsert_method:
                inserted = int(getattr(self, upsert_method)(sql_df))
            else:
                inserted = int(self._bulk_insert_sql(sql_table, sql_df))

            result["inserted"] = inserted
            result["sql_written"] = inserted > 0

            if result["sql_written"]:
                self.stats["sql_writes"] += 1

            return result

        except Exception as e:
            # Ensure we never reference sql_df if it wasn't built
            rows_for_log = len(sql_df) if isinstance(sql_df, pd.DataFrame) else len(df)
            
            error_msg = f"SQL write failed for {sql_table}: {str(e)[:500]}"
            
            if required:
                # For required tables, escalate to error and re-raise
                Console.error(
                    f"[CRITICAL] Required table {sql_table} write failed: {error_msg}",
                    component="OUTPUT",
                    table=sql_table,
                    rows=rows_for_log,
                    equip_id=self.equip_id,
                    run_id=self.run_id,
                    error_type=type(e).__name__,
                )
                result["error"] = error_msg
                raise RuntimeError(f"Required table write failed: {error_msg}") from e
            else:
                # For optional tables, warn and continue (backwards-compatible behavior)
                Console.warn(
                    f"SQL write failed for {sql_table}: {error_msg}",
                    component="OUTPUT",
                    table=sql_table,
                    rows=rows_for_log,
                    equip_id=self.equip_id,
                    run_id=self.run_id,
                    error_type=type(e).__name__,
                )
                result["error"] = error_msg
            result["error"] = str(e)
            self.stats["sql_failures"] += 1
            return result

        finally:
            elapsed = time.time() - start_time
            self.stats["write_time"] += elapsed
            # FCST-15: cache for downstream modules
            self._artifact_cache[artifact_name] = df

    def write_table(self, table_name: str, df: pd.DataFrame, delete_existing: bool = False) -> int:
        """Generic SQL table writer with RunID/EquipID injection and upsert routing."""
        with Span("persist.write", table=table_name, delete_existing=delete_existing) if _OBSERVABILITY_AVAILABLE and Span else nullcontext() as span:
            try:
                if not self._check_sql_health() or df is None or df.empty:
                    return 0

                sql_df = df.copy()

                # Inject standard metadata columns
                if 'RunID' not in sql_df.columns:
                    if not self.run_id:
                        raise ValueError("RunID is required but not set on OutputManager")
                    sql_df['RunID'] = self.run_id
                if 'EquipID' not in sql_df.columns:
                    sql_df['EquipID'] = self.equip_id

                sql_df = self._prepare_dataframe_for_sql(sql_df)

                # Optional delete-existing by RunID (+EquipID when available)
                if delete_existing and self.sql_client is not None and self.run_id:
                    try:
                        with self.sql_client.cursor() as cur:
                            if 'EquipID' in sql_df.columns and self.equip_id is not None:
                                cur.execute(f"DELETE FROM dbo.[{table_name}] WHERE RunID = ? AND EquipID = ?", (self.run_id, self.equip_id))
                            else:
                                cur.execute(f"DELETE FROM dbo.[{table_name}] WHERE RunID = ?", (self.run_id,))
                            self.sql_client.commit()
                    except Exception as del_ex:
                        Console.warn(f"delete_existing failed for {table_name}: {del_ex}", component="OUTPUT", table=table_name)

                # Route upsert tables via UPSERT_TABLES dict, else bulk insert
                upsert_method = UPSERT_TABLES.get(table_name)
                rows_written = getattr(self, upsert_method)(sql_df) if upsert_method else self._bulk_insert_sql(table_name, sql_df)

                if span:
                    span._span.set_attribute("acm.rows_written", rows_written)
                return rows_written

            except Exception as e:
                Console.warn(f"write_table failed for {table_name}: {e}", component="OUTPUT", table=table_name, error=str(e)[:200])
                if span:
                    span._span.set_attribute("acm.error", True)
                return 0

    def _bulk_insert_sql(self, table_name: str, df: pd.DataFrame) -> int:
        """Perform bulk SQL insert with optimized batching and robust commit."""
        _sql_start_time = time.perf_counter()  # Track for observability
        
        if df.empty:
            return 0
        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Invalid table name: {table_name}")
        if self.sql_client is None:
            return 0

        inserted = 0
        if self.sql_client is None:
            return 0
        cursor_factory = lambda: cast(Any, self.sql_client).cursor()

        # Optional: skip if the table doesn't exist (avoids noisy logs on dev DBs)
        exists = self._table_exists_cache.get(table_name)
        if exists is None:
            exists = _table_exists(cursor_factory, table_name)
            self._table_exists_cache[table_name] = bool(exists)
        if not exists:
            Console.warn(f"Skipping write: table dbo.[{table_name}] not found", component="OUTPUT", table=table_name, equip_id=self.equip_id, run_id=self.run_id)
            return 0

        cur = cursor_factory()
        try:
            try:
                cur.fast_executemany = True
            except Exception:
                pass

            # discover table columns and scope delete by RunID only when present
            # determine insertable columns (exclude identity)
            table_cols: set
            try:
                if table_name in self._table_insertable_cache:
                    table_cols = self._table_insertable_cache[table_name]
                else:
                    cols = set(_get_insertable_columns(cursor_factory, table_name))
                    if not cols:
                        cols = set(_get_table_columns(cursor_factory, table_name))
                    self._table_insertable_cache[table_name] = cols
                    table_cols = cols
            except Exception:
                if table_name in self._table_columns_cache:
                    table_cols = self._table_columns_cache[table_name]
                else:
                    cols_all = set(_get_table_columns(cursor_factory, table_name))
                    self._table_columns_cache[table_name] = cols_all
                    table_cols = cols_all
            # CRIT-01/HIGH-02: Standardize DELETE-before-INSERT for tables keyed by RunID
            # Apply for all tables with RunID in schema, scoped by EquipID when available.
            # PERF-OPT: Skip if table was already bulk pre-deleted
            if table_name in self._bulk_predeleted_tables:
                pass  # Already deleted in bulk operation
            else:
                try:
                    if "RunID" in table_cols and self.run_id:
                        if "EquipID" in table_cols and self.equip_id is not None:
                            rows_deleted = cur.execute(
                                f"DELETE FROM dbo.[{table_name}] WHERE RunID = ? AND EquipID = ?",
                                (self.run_id, int(self.equip_id or 0))
                            ).rowcount
                        else:
                            rows_deleted = cur.execute(
                                f"DELETE FROM dbo.[{table_name}] WHERE RunID = ?",
                                (self.run_id,)
                            ).rowcount
                        if rows_deleted and rows_deleted > 0:
                            Console.info(f"SQL delete from {table_name}: {rows_deleted} rows", component="OUTPUT")
                except Exception as del_ex:
                    Console.warn(f"Standard pre-delete for {table_name} failed: {del_ex}", component="OUTPUT", table=table_name, equip_id=self.equip_id, run_id=self.run_id, error_type=type(del_ex).__name__)

            # Note: RUL tables are already covered by standardized pre-delete above.

            # only insert columns that actually exist in the table
            columns = [c for c in df.columns if c in table_cols]
            cols_str = ", ".join(f"[{c}]" for c in columns)
            placeholders = ", ".join(["?"] * len(columns))
            insert_sql = f"INSERT INTO dbo.[{table_name}] ({cols_str}) VALUES ({placeholders})"

            # Clean NaN/Inf values for SQL Server compatibility (pyodbc cannot handle these).
            # Fast path: avoid repeated DataFrame.replace() calls which iterate block-by-block.
            import numpy as np
            df_clean = df[columns].copy()

            # Replace 'N/A' strings with None using per-column mask (avoids block replace).
            # Only scan object/string columns where these tokens can appear.
            _NA_STRINGS = {'N/A', 'n/a', 'NA', 'na', '#N/A'}
            for col in df_clean.select_dtypes(include='object').columns:
                mask = df_clean[col].isin(_NA_STRINGS)
                if mask.any():
                    df_clean.loc[mask, col] = None

            # Convert timestamp columns to datetime objects (vectorized)
            ts_cols = [c for c in df_clean.columns if c in DATETIME_COLUMNS or 'timestamp' in c.lower()]
            for col in ts_cols:
                try:
                    df_clean[col] = pd.to_datetime(df_clean[col], format='mixed', errors='coerce')
                    try:
                        df_clean[col] = df_clean[col].dt.tz_localize(None)
                    except Exception:
                        pass
                    null_count = df_clean[col].isna().sum()
                    if null_count > 0:
                        Console.warn(f"{null_count} timestamps failed to parse in column {col}", component="OUTPUT", table=table_name, column=col, failed_count=null_count)
                except Exception as ex:
                    Console.warn(f"Timestamp conversion failed for {col}: {ex}", component="OUTPUT", table=table_name, column=col, error_type=type(ex).__name__)

            # Vectorised float sanitisation: clamp extremes and convert Inf/NaN → None.
            # Convert the whole frame to object dtype once, then apply numpy masks per column.
            float_cols = df_clean.select_dtypes(include=[np.float64, np.float32]).columns
            if len(float_cols):
                float_arr = df_clean[float_cols].to_numpy(dtype=float)
                # Clamp values outside SQL float range to NaN
                extreme = np.abs(float_arr) > 1e38
                if extreme.any():
                    n_extreme = int(extreme.sum())
                    Console.warn(f"Clamping {n_extreme} extreme float values in {table_name}", component="OUTPUT", table=table_name, extreme_count=n_extreme)
                    float_arr[extreme] = np.nan
                # Replace Inf with NaN (in-place)
                np.copyto(float_arr, np.nan, where=~np.isfinite(float_arr))
                df_clean[float_cols] = float_arr

            # Final: convert to object dtype and replace any remaining NaN with None.
            df_clean = df_clean.astype(object).where(pd.notnull(df_clean), None)
            
            records = [tuple(row) for row in df_clean.itertuples(index=False, name=None)]
            for i in range(0, len(records), self.batch_size):
                batch = records[i:i+self.batch_size]
                try:
                    cur.executemany(insert_sql, batch)
                    inserted += len(batch)
                except Exception as batch_error:
                    # Log failed batch with first few records for debugging
                    sample = batch[:3] if len(batch) > 3 else batch
                    Console.error(f"Batch insert failed for {table_name} (sample: {sample}): {batch_error}", component="OUTPUT", table=table_name, batch_size=len(batch), equip_id=self.equip_id, run_id=self.run_id, error_type=type(batch_error).__name__, error=str(batch_error)[:200])
                    raise
        except Exception as e:
            Console.error(f"SQL insert failed for {table_name}: {e}", component="OUTPUT", table=table_name, rows=len(df), equip_id=self.equip_id, run_id=self.run_id, error_type=type(e).__name__, error=str(e)[:200])
            raise
        finally:
            try:
                cur.close()
            except Exception:
                pass

        # Only commit if not in batched transaction mode
        if not self._batched_transaction_active:
            try:
                if hasattr(self.sql_client, "commit"):
                    self.sql_client.commit()
                elif hasattr(self.sql_client, "conn") and hasattr(self.sql_client.conn, "commit"):
                    # some wrappers expose .conn
                    if not getattr(self.sql_client.conn, "autocommit", True):
                        self.sql_client.conn.commit()
            except Exception as e:
                Console.error(f"SQL commit failed for {table_name}: {e}", component="OUTPUT", table=table_name, equip_id=self.equip_id, run_id=self.run_id, error_type=type(e).__name__, error=str(e)[:200])
                raise

        Console.info(f"SQL insert to {table_name}: {inserted} rows", component="OUTPUT")
        
        # P1: Track SQL ops for observability metrics
        if _OBSERVABILITY_AVAILABLE and record_sql_op:
            try:
                duration_ms = (time.perf_counter() - _sql_start_time) * 1000
                record_sql_op(
                    equipment=getattr(self, 'equipment', ''),
                    table=table_name,
                    operation='insert',
                    rows=inserted,
                    duration_ms=duration_ms,
                )
            except Exception:
                pass  # Non-critical tracking
        
        return inserted

    
    # ==================== ARTIFACT CACHE METHODS (FCST-15) ====================
    
    def get_cached_table(self, table_name: str) -> Optional[pd.DataFrame]:
        """
        Retrieve a cached DataFrame from the artifact cache.
        
        This enables SQL-only mode by allowing downstream modules (forecast, RUL)
        to access previously written tables without file system dependencies.
        
        Args:
            table_name: Name of the table/file to retrieve (e.g., "scores.csv")
            
        Returns:
            DataFrame if found in cache, None otherwise
            
        Example:
            >>> scores = output_manager.get_cached_table("scores.csv")
            >>> if scores is not None:
            ...     # Use scores for forecasting
        """
        cached = self._artifact_cache.get(table_name)
        if cached is not None:
            Console.info(f"SQL cache hit {table_name}: {len(cached)} rows", component="OUTPUT")
            return cached.copy()  # Return copy to prevent mutation
        else:
            Console.warn(f"Table {table_name} not found in artifact cache", component="OUTPUT", table=table_name, available_tables=list(self._artifact_cache.keys())[:5])
            return None
    
    def write_pca_metrics(self, pca_detector=None, df=None, run_id=None, train=None) -> int:
        """Write PCA fit metrics to ACM_PCA_Metrics table (SQL-only).

        Two calling conventions:

        1. ``pca_detector=<PCASubspaceDetector>`` — called immediately after model fitting
           (detector_orchestrator.py).  Extracts all metrics directly from the fitted object.
           Pass ``train=<DataFrame>`` to populate TrainSamples/TrainFeatures.

        2. ``df=<DataFrame>`` — called by write_pca_artifacts after scoring.  The DataFrame
           must already be in new-format (NComponents, ExplainedVariance, ComponentsJson,
           MetricType, TrainSamples, TrainFeatures).  Score statistics (SPE/T2 percentiles)
           are appended to ComponentsJson before this call, so the second write supersedes
           the first.

        Args:
            pca_detector: PCASubspaceDetector instance.
            df: Pre-built new-format DataFrame.
            run_id: Run ID override (falls back to self.run_id).
            train: Training DataFrame used to fit the detector.  Provides TrainSamples and
                TrainFeatures when pca_detector is supplied.
        """
        if not self._check_sql_health():
            return 0

        try:
            if pca_detector is not None:
                # PCA may be None if insufficient samples (< 2) during fit - expected, not an error
                if not hasattr(pca_detector, 'pca') or pca_detector.pca is None:
                    return 0

                pca = pca_detector.pca
                run_id_val = run_id or self.run_id
                var_ratio = getattr(pca, 'explained_variance_ratio_', None)

                # Build per-component JSON matching the write_pca_artifacts format
                components_json = None
                if var_ratio is not None and len(var_ratio) > 0:
                    cum = np.cumsum(var_ratio)
                    components_json = json.dumps([
                        {
                            'name': f'PC{i + 1}',
                            'type': 'variance_ratio',
                            'value': float(r),
                            'cumulative': float(cum[i]),
                        }
                        for i, r in enumerate(var_ratio)
                    ])

                sql_df = pd.DataFrame([{
                    'RunID': run_id_val,
                    'EquipID': self.equip_id,
                    'NComponents': int(pca.n_components_),
                    'ExplainedVariance': float(var_ratio.sum()) if var_ratio is not None else None,
                    'ComponentsJson': components_json,
                    'MetricType': 'pca_fit',
                    'TrainSamples': int(len(train)) if train is not None else None,
                    'TrainFeatures': len(pca_detector.keep_cols) if hasattr(pca_detector, 'keep_cols') else None,
                }])

            elif df is not None:
                if df.empty:
                    return 0
                sql_df = df.copy()
                if 'RunID' not in sql_df.columns:
                    sql_df['RunID'] = run_id or self.run_id
                if 'EquipID' not in sql_df.columns:
                    sql_df['EquipID'] = self.equip_id

            else:
                Console.warn(
                    "write_pca_metrics called without pca_detector or df",
                    component="OUTPUT", equip_id=self.equip_id, run_id=self.run_id,
                )
                return 0

            return self._upsert_pca_metrics(sql_df)

        except Exception as e:
            Console.warn(
                f"write_pca_metrics failed: {e}",
                component="OUTPUT", equip_id=self.equip_id,
                error_type=type(e).__name__, error=str(e)[:200],
            )
            return 0

    def write_pca_loadings(self, df: pd.DataFrame, run_id: str = None) -> int:
        """Write PCA loadings to ACM_PCA_Loadings table.
        
        Actual Table Schema (verified from INFORMATION_SCHEMA):
            ID BIGINT IDENTITY (auto)
            RunID UNIQUEIDENTIFIER NOT NULL
            EquipID INT NOT NULL
            ComponentIndex INT (nullable)
            SensorName NVARCHAR (nullable)
            Loading FLOAT NOT NULL
            AbsLoading FLOAT NOT NULL
            CreatedAt DATETIME2 NOT NULL
        
        Args:
            df: DataFrame with columns for PCA loadings data
            run_id: Run ID (optional, can come from df)
        
        Returns:
            Number of rows written
        """
        if df is None or df.empty:
            return 0
        if not self._check_sql_health():
            return 0
        
        try:
            sql_df = df.copy()
            
            # Map source columns to actual table schema
            # Source may have: ComponentNo/ComponentID -> ComponentIndex
            # Source may have: Sensor/FeatureName -> SensorName
            if 'ComponentIndex' not in sql_df.columns:
                if 'ComponentNo' in sql_df.columns:
                    sql_df['ComponentIndex'] = sql_df['ComponentNo']
                elif 'ComponentID' in sql_df.columns:
                    sql_df['ComponentIndex'] = sql_df['ComponentID']
                else:
                    sql_df['ComponentIndex'] = 0  # Default
                    
            if 'SensorName' not in sql_df.columns:
                if 'Sensor' in sql_df.columns:
                    sql_df['SensorName'] = sql_df['Sensor']
                elif 'FeatureName' in sql_df.columns:
                    sql_df['SensorName'] = sql_df['FeatureName']
                else:
                    sql_df['SensorName'] = 'unknown'  # Default
            
            # Ensure required columns
            if 'EquipID' not in sql_df.columns:
                sql_df['EquipID'] = self.equip_id
            if 'RunID' not in sql_df.columns:
                if not (run_id or self.run_id):
                    raise ValueError("RunID is required but not set")
                sql_df['RunID'] = run_id or self.run_id
            
            # Calculate AbsLoading from Loading (required NOT NULL column)
            if 'AbsLoading' not in sql_df.columns:
                if 'Loading' in sql_df.columns:
                    sql_df['AbsLoading'] = sql_df['Loading'].abs()
                else:
                    Console.warn("write_pca_loadings: Missing 'Loading' column, cannot compute AbsLoading",
                                component="OUTPUT", equip_id=self.equip_id)
                    return 0
            
            # Handle NaN values in AbsLoading - replace with 0.0 since NOT NULL
            sql_df['AbsLoading'] = sql_df['AbsLoading'].fillna(0.0)
            sql_df['Loading'] = sql_df['Loading'].fillna(0.0)
            
            if 'CreatedAt' not in sql_df.columns:
                sql_df['CreatedAt'] = datetime.now()
            
            # Select only the columns the table expects (matching actual schema)
            keep_cols = ['RunID', 'EquipID', 'ComponentIndex', 'SensorName', 'Loading', 'AbsLoading', 'CreatedAt']
            sql_df = sql_df[[c for c in keep_cols if c in sql_df.columns]]
            
            return self._bulk_insert_sql('ACM_PCA_Loadings', sql_df)
            
        except Exception as e:
            Console.warn(f"write_pca_loadings failed: {e}", component="OUTPUT",
                        equip_id=self.equip_id, run_id=run_id, error=str(e)[:200])
            return 0

    def _upsert_pca_metrics(self, df: pd.DataFrame) -> int:
        """Upsert PCA metrics using DELETE + INSERT pattern.

        Expects a new-format DataFrame with columns matching ACM_PCA_Metrics:
          - RunID           (required, UNIQUEIDENTIFIER)
          - EquipID         (required, INT)
          - NComponents     (nullable, INT)
          - ExplainedVariance (nullable, FLOAT — cumulative variance ratio)
          - ComponentsJson  (nullable, NVARCHAR — JSON array of per-component entries)
          - MetricType      (nullable, e.g. 'pca_fit')
          - TrainSamples    (nullable, INT)
          - TrainFeatures   (nullable, INT)
          - CreatedAt       (server default)
        """
        if df.empty or self.sql_client is None:
            return 0

        try:
            conn = self.sql_client.conn
            cursor = conn.cursor()

            # Ensure RunID and EquipID are present
            if 'RunID' not in df.columns:
                df = df.copy()
                df['RunID'] = self.run_id
            if 'EquipID' not in df.columns:
                df = df.copy()
                df['EquipID'] = self.equip_id

            # DELETE existing rows for this RunID+EquipID before re-inserting
            run_equip_pairs = df[['RunID', 'EquipID']].drop_duplicates()
            for run_id, equip_id in run_equip_pairs.values:
                if equip_id is None:
                    continue
                cursor.execute(
                    "DELETE FROM ACM_PCA_Metrics WHERE RunID = ? AND EquipID = ?",
                    (str(run_id), int(equip_id))
                )

            insert_sql = """
            INSERT INTO ACM_PCA_Metrics
                (RunID, EquipID, NComponents, ExplainedVariance, ComponentsJson, MetricType, TrainSamples, TrainFeatures)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

            valid_records = [r for r in df.to_dict('records') if r.get('EquipID') is not None]
            rows_to_insert = [
                (
                    str(row['RunID']),
                    int(row['EquipID']),
                    int(row['NComponents']) if pd.notna(row.get('NComponents')) else None,
                    float(row['ExplainedVariance']) if pd.notna(row.get('ExplainedVariance')) else None,
                    str(row['ComponentsJson']) if pd.notna(row.get('ComponentsJson')) else None,
                    str(row.get('MetricType', 'pca_fit')) if pd.notna(row.get('MetricType')) else 'pca_fit',
                    int(row['TrainSamples']) if pd.notna(row.get('TrainSamples')) else None,
                    int(row['TrainFeatures']) if pd.notna(row.get('TrainFeatures')) else None,
                )
                for row in valid_records
            ]

            if rows_to_insert:
                cursor.fast_executemany = True
                cursor.executemany(insert_sql, rows_to_insert)

            conn.commit()
            return len(rows_to_insert)

        except Exception as e:
            Console.warn(
                f"_upsert_pca_metrics failed: {e}",
                component="OUTPUT", table="ACM_PCA_Metrics", rows=len(df),
                equip_id=self.equip_id, error_type=type(e).__name__, error=str(e)[:200],
            )
            if self.sql_client and self.sql_client.conn:
                try:
                    self.sql_client.conn.rollback()
                except Exception:
                    pass
            return 0
    
    def _upsert_health_forecast(self, df: pd.DataFrame) -> int:
        """
        FORECAST-WRITE-01: Write health forecast using bulk insert.
        v10 schema: ACM_HealthForecast has (RunID, EquipID, Timestamp, ForecastHealth, CI_Lower, CI_Upper, Method, CreatedAt)
        """
        if df.empty or self.sql_client is None:
            return 0
        
        try:
            # Bulk insert is standard for forecast tables in v10
            return self._bulk_insert_sql('ACM_HealthForecast', df)
        except Exception as e:
            Console.warn(f"_upsert_health_forecast failed: {e}", component="OUTPUT", table="ACM_HealthForecast", rows=len(df), equip_id=self.equip_id, error_type=type(e).__name__, error=str(e)[:200])
            return 0
    
    def _upsert_failure_forecast(self, df: pd.DataFrame) -> int:
        """
        FORECAST-WRITE-02: Write failure forecast using bulk insert.
        v10 schema: ACM_FailureForecast has (RunID, EquipID, Timestamp, FailureProb, ThresholdUsed, Method, CreatedAt)
        """
        if df.empty or self.sql_client is None:
            return 0
        
        try:
            return self._bulk_insert_sql('ACM_FailureForecast', df)
        except Exception as e:
            Console.warn(f"_upsert_failure_forecast failed: {e}", component="OUTPUT", table="ACM_FailureForecast", rows=len(df), equip_id=self.equip_id, error_type=type(e).__name__, error=str(e)[:200])
            return 0
    
    def _upsert_detector_forecast_ts(self, df: pd.DataFrame) -> int:
        """
        FORECAST-UPSERT-03: Upsert detector forecast time series using MERGE.
        
        Primary key is (RunID, EquipID, DetectorName, Timestamp), so update if exists.
        Schema: RunID, EquipID, DetectorName, Timestamp, ForecastValue, CiLower, CiUpper, ForecastStd, Method, CreatedAt
        """
        if df.empty or self.sql_client is None:
            return 0
        
        # Ensure all required columns exist with defaults before upsert
        df = df.copy()
        if 'Method' not in df.columns:
            df['Method'] = 'AR1'
        if 'ForecastStd' not in df.columns:
            df['ForecastStd'] = 0.0
        
        # Fill any NaN values in critical columns
        df['Method'] = df['Method'].fillna('AR1')
        # Avoid FutureWarning for silent downcasting by ensuring float dtype before fillna
        df['ForecastStd'] = pd.to_numeric(df['ForecastStd'], errors='coerce').astype(float).fillna(0.0)
        if 'DetectorName' in df.columns:
            df['DetectorName'] = df['DetectorName'].fillna('UNKNOWN')
        
        try:
            # PERFORMANCE FIX: Replace row-by-row MERGE with DELETE + bulk INSERT
            # The MERGE pattern was doing N individual SQL round-trips (catastrophic)
            
            # First, delete existing records for this RunID/EquipID
            conn = self.sql_client.conn
            cursor = conn.cursor()
            
            # Get unique RunID/EquipID pairs
            run_id = df['RunID'].iloc[0] if 'RunID' in df.columns else self.run_id
            equip_id = df['EquipID'].iloc[0] if 'EquipID' in df.columns else self.equip_id
            
            if equip_id is None:
                Console.warn("_upsert_detector_forecast_ts: equip_id is None, skipping", component="OUTPUT")
                return 0
            
            cursor.execute(
                "DELETE FROM ACM_DetectorForecast_TS WHERE RunID = ? AND EquipID = ?",
                (run_id, equip_id)
            )
            
            # Clean NaN values vectorized (not row-by-row)
            df = df.copy()
            df['ForecastValue'] = pd.to_numeric(df['ForecastValue'], errors='coerce').fillna(0.0)
            df['CiLower'] = pd.to_numeric(df['CiLower'], errors='coerce').fillna(0.0)
            df['CiUpper'] = pd.to_numeric(df['CiUpper'], errors='coerce').fillna(0.0)
            df['ForecastStd'] = pd.to_numeric(df['ForecastStd'], errors='coerce').fillna(0.0)
            df['Method'] = df['Method'].fillna('AR1')
            df['DetectorName'] = df['DetectorName'].fillna('UNKNOWN')
            if 'CreatedAt' not in df.columns:
                df['CreatedAt'] = datetime.now()
            
            # Bulk insert with fast_executemany
            cursor.fast_executemany = True
            
            insert_sql = """
            INSERT INTO ACM_DetectorForecast_TS 
            (RunID, EquipID, DetectorName, Timestamp, ForecastValue, CiLower, CiUpper, ForecastStd, Method, CreatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # Build tuples for executemany (vectorized)
            records = list(df[['RunID', 'EquipID', 'DetectorName', 'Timestamp', 
                              'ForecastValue', 'CiLower', 'CiUpper', 'ForecastStd', 
                              'Method', 'CreatedAt']].itertuples(index=False, name=None))
            
            cursor.executemany(insert_sql, records)
            conn.commit()
            return len(records)
            
        except Exception as e:
            Console.warn(f"_upsert_detector_forecast_ts failed: {e}", component="OUTPUT", table="ACM_DetectorForecast_TS", rows=len(df), equip_id=self.equip_id, error_type=type(e).__name__, error=str(e)[:200])
            return 0
    
    def _upsert_sensor_forecast(self, df: pd.DataFrame) -> int:
        """
        FORECAST-WRITE-04: Write sensor forecast using bulk insert.
        v10 schema: ACM_SensorForecast has (RunID, EquipID, SensorName, Timestamp, ForecastValue, CiLower, CiUpper, ForecastStd, Method, RegimeLabel, CreatedAt)
        """
        if df.empty or self.sql_client is None:
            return 0
        
        try:
            return self._bulk_insert_sql('ACM_SensorForecast', df)
        except Exception as e:
            Console.warn(f"_upsert_sensor_forecast failed: {e}", component="OUTPUT", table="ACM_SensorForecast", rows=len(df), equip_id=self.equip_id, error_type=type(e).__name__, error=str(e)[:200])
            return 0
    
    def write_run_stats(self, stats_data: Dict[str, Any]) -> int:
        """Write run statistics to ACM_Run_Stats table."""
        if not self._check_sql_health():
            return 0
        try:
            row = dict(stats_data)
            # Normalize key variants
            if 'StartTime' not in row and 'WindowStartEntryDateTime' in row:
                row['StartTime'] = normalize_timestamp_scalar(row.get('WindowStartEntryDateTime'))
            if 'EndTime' not in row and 'WindowEndEntryDateTime' in row:
                row['EndTime'] = normalize_timestamp_scalar(row.get('WindowEndEntryDateTime'))
            row.setdefault('RunID', self.run_id)
            if self.equip_id is None:
                Console.warn("write_run_stats: equip_id is None, skipping", component="OUTPUT")
                return 0
            row.setdefault('EquipID', self.equip_id)
            sql_df = pd.DataFrame([row])
            return self._bulk_insert_sql('ACM_Run_Stats', sql_df)
        except Exception as e:
            Console.error(f"write_run_stats failed: {e}", component="OUTPUT", equip_id=self.equip_id, run_id=self.run_id, error_type=type(e).__name__, error=str(e)[:200])
            return 0
    
    def write_scores(self, scores_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Write scores (SQL-only) to dbo.ACM_Scores_Wide.

        Normalizes index to tz-naive seconds and writes a Timestamp column.
        Timestamp normalization is deterministic and always applied.
        
        v11.1.5 FIX: Deletes existing rows for the same EquipID + timestamp range
        before inserting to prevent duplicate data from overlapping batch runs.
        """
        scores_for_output = scores_df.copy()
        scores_for_output.index.name = "timestamp"

        if len(scores_for_output.index):
            ts = pd.to_datetime(scores_for_output.index, errors="coerce")
            # Deterministic normalization: always tz-naive, floored to seconds
            # This ensures consistent SQL Server insertion regardless of input timezone
            if ts.tz is not None:
                ts = ts.tz_localize(None)
            ts = ts.floor("s")
            scores_for_output.index = ts

        # v11.1.5 FIX: Delete overlapping data BEFORE insert to prevent duplicates
        # This handles the case where multiple batch runs cover overlapping time ranges
        if len(scores_for_output.index) > 0 and self.sql_client is not None and self.equip_id:
            min_ts = scores_for_output.index.min()
            max_ts = scores_for_output.index.max()
            if pd.notna(min_ts) and pd.notna(max_ts):
                try:
                    with self.sql_client.cursor() as cur:
                        cur.execute(
                            "DELETE FROM dbo.[ACM_Scores_Wide] "
                            "WHERE EquipID = ? AND Timestamp BETWEEN ? AND ?",
                            (int(self.equip_id), min_ts, max_ts)
                        )
                        deleted = cur.rowcount
                        if deleted > 0:
                            Console.info(
                                f"Deleted {deleted} overlapping rows from ACM_Scores_Wide",
                                component="OUTPUT", table="ACM_Scores_Wide",
                                equip_id=self.equip_id, min_ts=str(min_ts), max_ts=str(max_ts)
                            )
                    if hasattr(self.sql_client, "commit"):
                        self.sql_client.commit()
                    elif hasattr(self.sql_client, "conn") and hasattr(self.sql_client.conn, "commit"):
                        if not getattr(self.sql_client.conn, "autocommit", True):
                            self.sql_client.conn.commit()
                except Exception as del_ex:
                    Console.warn(
                        f"Failed to delete overlapping scores: {del_ex}",
                        component="OUTPUT", table="ACM_Scores_Wide",
                        equip_id=self.equip_id, error_type=type(del_ex).__name__
                    )

        score_columns = {
            "timestamp": "Timestamp",
            "ar1_z": "ar1_z",
            "pca_spe_z": "pca_spe_z",
            "pca_t2_z": "pca_t2_z",
            "iforest_z": "iforest_z",
            "gmm_z": "gmm_z",
            "omr_z": "omr_z",
            "cusum_z": "cusum_z",
            "drift_z": "drift_z",
            "hst_z": "hst_z",
            "fused": "fused",
            "regime_label": "regime_label",
            "transient_state": "transient_state",
        }

        # non_numeric_cols must refer to *pre-mapping* column names because prepare() runs first.
        return self.write_dataframe(
            df=scores_for_output.reset_index(),
            artifact_name="scores",
            sql_table="ACM_Scores_Wide",
            sql_columns=score_columns,
            non_numeric_cols={"timestamp", "regime_label", "transient_state"},
            add_created_at=False,
        )
    
    def write_episodes(self, episodes_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Write episodes to SQL (SQL-only).
        
        Individual episodes go to ACM_EpisodeDiagnostics.
        Run-level summary goes to ACM_Episodes.
        """
        if episodes_df.empty:
            return {"sql_written": False, "rows": 0, "inserted": 0, "error": None}
        
        # Prepare episodes for output
        episodes_for_output = episodes_df.copy().reset_index(drop=True)
        
        # Track which repairs are applied for explicit schema drift reporting
        repairs_applied = []
        
        episode_columns = {
            'episode_id': 'EpisodeID',
            'start_ts': 'StartTime',
            'end_ts': 'EndTime',
            'peak_fused_z': 'PeakZ',
            'peak_timestamp': 'peak_timestamp', 
            'duration_hours': 'DurationHours',
            'dominant_sensor': 'TopSensor1',
            'severity': 'Severity',
            'avg_fused_z': 'AvgZ',
            'min_health_index': 'min_health_index',
            'culprits': 'Culprits'
        }
        
        # Add episode_id if missing (sequential)
        if 'episode_id' not in episodes_for_output.columns:
            episodes_for_output['episode_id'] = range(1, len(episodes_for_output) + 1)
            repairs_applied.append("episode_id_added")
        
        # Calculate duration_hours from duration_s if needed
        if 'duration_hours' not in episodes_for_output.columns and 'duration_s' in episodes_for_output.columns:
            episodes_for_output['duration_hours'] = episodes_for_output['duration_s'] / 3600.0
            repairs_applied.append("duration_hours_derived")
        
        # Extract peak_timestamp from start_ts if missing
        if 'peak_timestamp' not in episodes_for_output.columns and 'start_ts' in episodes_for_output.columns:
            episodes_for_output['peak_timestamp'] = episodes_for_output['start_ts']
            repairs_applied.append("peak_timestamp_fallback_used")
        
        # Map regime_label to MaxRegimeLabel
        if 'regime_label' in episodes_for_output.columns:
            episodes_for_output['MaxRegimeLabel'] = episodes_for_output['regime_label']
            repairs_applied.append("regime_label_mapped")
        elif 'regime' in episodes_for_output.columns:
            episodes_for_output['MaxRegimeLabel'] = episodes_for_output['regime']
            repairs_applied.append("regime_mapped_fallback")
        
        # Extract dominant sensor from culprits field
        # PERF-OPT: Vectorized dominant sensor extraction from culprits field
        # culprits format: "Detector (Sensor Name)" or "Detector"
        if 'culprits' in episodes_for_output.columns:
            culprits_col = episodes_for_output['culprits'].fillna('').astype(str)
            # Split on arrow separator and take first part (handle encoding variants)
            # Use unicode arrow character (U+2192)
            arrow = ' ' + chr(8594) + ' '  # Unicode arrow with spaces
            has_arrow = culprits_col.str.contains(arrow, na=False, regex=False)
            split_result = culprits_col.str.split(arrow).str[0].str.strip()
            episodes_for_output['dominant_sensor'] = np.where(
                culprits_col == '',
                'UNKNOWN',
                np.where(has_arrow, split_result, culprits_col.str.strip())
            )
            repairs_applied.append("dominant_sensor_extracted")
        else:
            episodes_for_output['dominant_sensor'] = 'UNKNOWN'
            repairs_applied.append("dominant_sensor_defaulted")
        
        # PERF-OPT: Vectorized severity calculation from peak_fused_z using np.select
        # FIX: Use ABSOLUTE VALUE of z-scores - negative z-scores (below-normal) are equally anomalous
        if 'peak_fused_z' in episodes_for_output.columns:
            peak_z = episodes_for_output['peak_fused_z']
            abs_peak_z = np.abs(peak_z)  # FIX: Both +17.9 and -17.9 should be CRITICAL
            conditions = [
                peak_z.isna(),
                abs_peak_z >= 6,
                abs_peak_z >= 4,
                abs_peak_z >= 2,
            ]
            choices = ['UNKNOWN', 'CRITICAL', 'HIGH', 'MEDIUM']
            episodes_for_output['severity'] = np.select(conditions, choices, default='LOW')
            repairs_applied.append("severity_calculated")
        elif 'severity' not in episodes_for_output.columns:
            episodes_for_output['severity'] = 'UNKNOWN'
            repairs_applied.append("severity_defaulted")
        
        # Add status default
        if 'status' not in episodes_for_output.columns:
            episodes_for_output['status'] = 'CLOSED'
            repairs_applied.append("status_defaulted")
        
        # Log all repairs for explicit schema drift tracking
        if repairs_applied:
            Console.info(f"Applied {len(repairs_applied)} schema repairs to episodes: {', '.join(repairs_applied)}", 
                        component="EPISODES", equip_id=self.equip_id, episode_count=len(episodes_for_output))
        
        result = self.write_dataframe(
            episodes_for_output,
            "episodes",
            sql_table="ACM_EpisodeDiagnostics",
            sql_columns=episode_columns,
            non_numeric_cols={
                "RunID", "EquipID", "episode_id", "peak_timestamp",
                "dominant_sensor", "severity", "min_health_index", "culprits"
            },
            required=True
        )
        
        # Also write individual episodes to ACM_Episodes (actual table schema)
        # ACM_Episodes stores per-episode data, NOT run summaries
        if not episodes_df.empty:
            try:
                # Build episode records matching actual table schema
                episode_records = []
                for idx, row in episodes_df.iterrows():
                    episode_records.append({
                        'RunID': self.run_id,
                        'EquipID': self.equip_id or 0,
                        'EpisodeID': int(row.get('episode_id', idx + 1)),
                        'StartTime': row.get('start_ts', datetime.now()),
                        'EndTime': row.get('end_ts', None),
                        'DurationSeconds': float(row.get('duration_s', 0)) if pd.notna(row.get('duration_s')) else None,
                        'DurationHours': float(row.get('duration_s', 0)) / 3600.0 if pd.notna(row.get('duration_s')) else None,
                        'RecordCount': int(row.get('n_samples', 1)) if pd.notna(row.get('n_samples')) else 1,
                        'Culprits': str(row.get('culprits', ''))[:500] if pd.notna(row.get('culprits')) else None,
                        'PrimaryDetector': str(row.get('dominant_sensor', 'UNKNOWN'))[:100] if pd.notna(row.get('dominant_sensor')) else 'UNKNOWN',
                        'Severity': str(row.get('severity', 'UNKNOWN'))[:50],
                        'RegimeLabel': int(row.get('regime_label', 0)) if pd.notna(row.get('regime_label')) else None,
                        'RegimeState': str(row.get('regime_state', ''))[:50] if pd.notna(row.get('regime_state')) else None,
                    })
                if episode_records:
                    summary_df = pd.DataFrame(episode_records)
                    self._bulk_insert_sql('ACM_Episodes', summary_df)
            except Exception as summary_err:
                Console.warn(f"Failed to write to ACM_Episodes: {summary_err}", component="EPISODES", equip_id=self.equip_id, run_id=self.run_id, episode_count=len(episodes_df), error_type=type(summary_err).__name__)
        
        return result
    
    def write_threshold_metadata(
        self,
        equip_id: int,
        threshold_type: str,
        threshold_value: float,
        calculation_method: str,
        sample_count: int,
        train_start: Optional[datetime] = None,
        train_end: Optional[datetime] = None,
        config_signature: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """Write adaptive threshold metadata to ACM_AdaptiveConfig.
        
        Maps to actual table schema:
        - ConfigKey: threshold_type (e.g., 'fused_alert_z')
        - ConfigValue: threshold_value as string
        - MinBound/MaxBound: 0.0/infinity for thresholds
        - IsLearned: True (since computed from data)
        - DataVolumeAtTuning: sample_count
        - PerformanceMetric: calculation_method
        - Source: 'adaptive_threshold_calculator'
        - ResearchReference: notes
        
        Args:
            equip_id: Equipment ID
            threshold_type: Type of threshold (e.g., 'fused_alert_z', 'fused_warn_z')
            threshold_value: Calculated threshold value
            calculation_method: Method used (e.g., 'quantile_0.997')
            sample_count: Number of samples used in calculation
            train_start: Start of training window (unused - table doesn't have this)
            train_end: End of training window (unused - table doesn't have this)
            config_signature: Hash of config used (unused - table doesn't have this)
            notes: Optional notes about calculation
        
        Returns:
            Number of rows written (1 on success, 0 on failure)
        """
        if not self._check_sql_health():
            return 0
        try:
            # Handle dict values (per-regime thresholds) - store first value only
            if isinstance(threshold_value, dict):
                # Take first value for storage, or average
                threshold_float = float(list(threshold_value.values())[0]) if threshold_value else 0.0
            else:
                threshold_float = float(threshold_value)
            
            row = {
                'EquipID': int(equip_id),
                'ConfigKey': threshold_type,
                'ConfigValue': threshold_float,  # Float column
                'MinBound': 0.0,
                'MaxBound': 999999.0,  # Effectively no upper bound
                'IsLearned': 1,  # BIT column
                'DataVolumeAtTuning': int(sample_count),
                'PerformanceMetric': 0.0,  # Float column - store 0 for now
                'ResearchReference': f"{calculation_method}: {notes}" if notes else calculation_method,
                'Source': 'adaptive_threshold_calculator',
            }
            # Use MERGE to handle existing records (UNIQUE constraint on EquipID+ConfigKey)
            return self._upsert_adaptive_config(row)
        except Exception as e:
            Console.warn(f"write_threshold_metadata failed: {e}", component="THRESHOLD", error=str(e)[:200])
            return 0
    
    def _upsert_adaptive_config(self, row: dict) -> int:
        """Upsert single row into ACM_AdaptiveConfig using MERGE.
        
        Table has UNIQUE constraint on (EquipID, ConfigKey).
        """
        if self.sql_client is None:
            return 0
        try:
            conn = self.sql_client.conn
            cursor = conn.cursor()
            merge_sql = """
            MERGE INTO ACM_AdaptiveConfig AS target
            USING (SELECT ? AS EquipID, ? AS ConfigKey) AS source (EquipID, ConfigKey)
            ON target.EquipID = source.EquipID AND target.ConfigKey = source.ConfigKey
            WHEN MATCHED THEN
                UPDATE SET 
                    ConfigValue = ?,
                    MinBound = ?,
                    MaxBound = ?,
                    IsLearned = ?,
                    DataVolumeAtTuning = ?,
                    PerformanceMetric = ?,
                    ResearchReference = ?,
                    Source = ?,
                    UpdatedAt = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (EquipID, ConfigKey, ConfigValue, MinBound, MaxBound, IsLearned, 
                        DataVolumeAtTuning, PerformanceMetric, ResearchReference, Source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """
            cursor.execute(merge_sql, (
                # Match keys
                row['EquipID'], row['ConfigKey'],
                # Update values
                row['ConfigValue'], row['MinBound'], row['MaxBound'], row['IsLearned'],
                row['DataVolumeAtTuning'], row['PerformanceMetric'], row['ResearchReference'], row['Source'],
                # Insert values
                row['EquipID'], row['ConfigKey'], row['ConfigValue'], row['MinBound'], row['MaxBound'],
                row['IsLearned'], row['DataVolumeAtTuning'], row['PerformanceMetric'], 
                row['ResearchReference'], row['Source']
            ))
            conn.commit()
            return 1
        except Exception as e:
            Console.warn(f"_upsert_adaptive_config failed: {e}", component="OUTPUT",
                        equip_id=row.get('EquipID'), config_key=row.get('ConfigKey'), error=str(e)[:200])
            if self.sql_client and self.sql_client.conn:
                try:
                    self.sql_client.conn.rollback()
                except:
                    pass
            return 0
    
    def load_omr_drift_context(self, equip_id: int, lookback_hours: int = 24) -> dict:
        """Load OMR and drift context from recent data for forecasting.
        
        Queries ACM_Scores_Wide for recent OMR/drift values and ACM_DriftSeries for trend.
        
        Args:
            equip_id: Equipment ID
            lookback_hours: How many hours of history to consider
            
        Returns:
            Dict with keys:
                - omr_z: Most recent OMR z-score (or None)
                - omr_trend: 'increasing', 'decreasing', 'stable', or 'unknown'
                - top_contributors: List of top contributing sensors
                - drift_z: Most recent drift z-score (or None)
                - drift_trend: 'increasing', 'decreasing', 'stable', or 'unknown'
        """
        result = {
            'omr_z': None,
            'omr_trend': 'unknown',
            'top_contributors': [],
            'drift_z': None,
            'drift_trend': 'unknown'
        }
        
        if not self._check_sql_health():
            return result
        
        try:
            conn = self.sql_client.conn
            cursor = conn.cursor()
            
            # Get most recent fused score (Overall Model Residual is computed from fused scores)
            # ACM_Scores_Wide has 'fused' column, not 'omr_z'
            cursor.execute("""
                SELECT TOP 1 fused
                FROM ACM_Scores_Wide
                WHERE EquipID = ? AND fused IS NOT NULL
                ORDER BY Timestamp DESC
            """, (equip_id,))
            row = cursor.fetchone()
            if row:
                result['omr_z'] = float(row[0]) if row[0] is not None else None
            
            # Get OMR/fused trend from recent values
            cursor.execute("""
                SELECT fused
                FROM (
                    SELECT TOP 10 fused, Timestamp
                    FROM ACM_Scores_Wide
                    WHERE EquipID = ? AND fused IS NOT NULL
                    ORDER BY Timestamp DESC
                ) sub
                ORDER BY Timestamp ASC
            """, (equip_id,))
            omr_values = [float(r[0]) for r in cursor.fetchall() if r[0] is not None]
            if len(omr_values) >= 3:
                # Simple trend: compare first half avg to second half avg
                mid = len(omr_values) // 2
                first_avg = sum(omr_values[:mid]) / mid
                second_avg = sum(omr_values[mid:]) / (len(omr_values) - mid)
                if second_avg > first_avg * 1.1:
                    result['omr_trend'] = 'increasing'
                elif second_avg < first_avg * 0.9:
                    result['omr_trend'] = 'decreasing'
                else:
                    result['omr_trend'] = 'stable'
            
            # Get top contributors from SensorHotspots (most recent by max z-score)
            cursor.execute("""
                SELECT TOP 3 SensorName
                FROM ACM_SensorHotspots
                WHERE EquipID = ?
                ORDER BY MaxAbsZ DESC
            """, (equip_id,))
            result['top_contributors'] = [r[0] for r in cursor.fetchall() if r[0]]
            
            # Get drift from DriftSeries
            cursor.execute("""
                SELECT TOP 1 DriftValue
                FROM ACM_DriftSeries
                WHERE EquipID = ?
                ORDER BY Timestamp DESC
            """, (equip_id,))
            row = cursor.fetchone()
            if row:
                result['drift_z'] = float(row[0]) if row[0] is not None else None
            
            # Get drift trend
            cursor.execute("""
                SELECT DriftValue
                FROM (
                    SELECT TOP 10 DriftValue, Timestamp
                    FROM ACM_DriftSeries
                    WHERE EquipID = ?
                    ORDER BY Timestamp DESC
                ) sub
                ORDER BY Timestamp ASC
            """, (equip_id,))
            drift_values = [float(r[0]) for r in cursor.fetchall() if r[0] is not None]
            if len(drift_values) >= 3:
                mid = len(drift_values) // 2
                first_avg = sum(drift_values[:mid]) / mid
                second_avg = sum(drift_values[mid:]) / (len(drift_values) - mid)
                if second_avg > first_avg * 1.1:
                    result['drift_trend'] = 'increasing'
                elif second_avg < first_avg * 0.9:
                    result['drift_trend'] = 'decreasing'
                else:
                    result['drift_trend'] = 'stable'
            
            cursor.close()
        except Exception as e:
            Console.debug(f"load_omr_drift_context failed: {e}", component="OUTPUT", error=str(e)[:200])
        
        return result
    
    # =========================================================================
    # DataFrame Builder Methods (moved from acm_main.py in v11.2)
    # =========================================================================
    # These methods build DataFrames for SQL persistence. They encapsulate the
    # data transformation logic that was previously scattered in acm_main.py.
    # =========================================================================
    
    @staticmethod
    def _build_data_quality_records(
        train_numeric: pd.DataFrame,
        score_numeric: pd.DataFrame,
        cfg: Dict[str, Any],
        low_var_threshold: float = 1e-4,
    ) -> List[Dict[str, Any]]:
        """Build a SINGLE summary data quality record (not per-sensor).
        
        v11.3.3: Changed from 81 rows (per-sensor) to 1 summary row per run.
        This dramatically reduces SQL writes while keeping aggregate diagnostics.
        
        Computes aggregate metrics across all sensors:
        - Total sensors count
        - Avg/max null percentages
        - Low-variance sensor count
        - Flatline sensor count
        - Time ranges
        
        Args:
            train_numeric: Training data DataFrame
            score_numeric: Score data DataFrame
            cfg: Config dictionary with data settings
            low_var_threshold: Threshold for low-variance detection
            
        Returns:
            List containing ONE summary record (for compatibility with existing write logic)
        """
        interp_method = str((cfg.get("data", {}) or {}).get("interp_method", "linear"))
        sampling_secs_raw = (cfg.get("data", {}) or {}).get("sampling_secs", None)
        # v11.5.0: sampling_secs can be "auto" (string) - convert to None for SQL float column
        try:
            sampling_secs = float(sampling_secs_raw) if sampling_secs_raw not in (None, "auto", "") else None
        except (ValueError, TypeError):
            sampling_secs = None
        
        # Find common columns
        common_cols = []
        if hasattr(train_numeric, "columns") and hasattr(score_numeric, "columns"):
            common_cols = [c for c in train_numeric.columns if c in score_numeric.columns]
        
        if not common_cols:
            return []
        
        # Aggregate metrics across all sensors
        total_sensors = len(common_cols)
        tr_total_rows = len(train_numeric)
        sc_total_rows = len(score_numeric)
        
        # Per-sensor stats for aggregation
        low_var_count = 0
        flatline_count = 0
        all_null_train_count = 0
        all_null_score_count = 0
        tr_null_pcts = []
        sc_null_pcts = []
        
        for col in common_cols:
            tr_series = train_numeric[col]
            sc_series = score_numeric[col]
            tr_nulls = int(tr_series.isna().sum())
            sc_nulls = int(sc_series.isna().sum())
            
            # Null percentages
            tr_null_pct = (100.0 * tr_nulls / tr_total_rows) if tr_total_rows else 0.0
            sc_null_pct = (100.0 * sc_nulls / sc_total_rows) if sc_total_rows else 0.0
            tr_null_pcts.append(tr_null_pct)
            sc_null_pcts.append(sc_null_pct)
            
            # Low variance check
            tr_std = pd.to_numeric(tr_series, errors="coerce").std()
            if tr_total_rows > 0 and (pd.isna(tr_std) or tr_std < low_var_threshold):
                low_var_count += 1
            
            # All-null check
            if tr_total_rows > 0 and tr_nulls == tr_total_rows:
                all_null_train_count += 1
            if sc_total_rows > 0 and sc_nulls == sc_total_rows:
                all_null_score_count += 1
            
            # Flatline check (simplified: std < threshold on score data)
            sc_std = pd.to_numeric(sc_series, errors="coerce").std()
            if sc_total_rows > 10 and (pd.isna(sc_std) or sc_std < low_var_threshold):
                flatline_count += 1
        
        # Aggregate null percentages
        avg_train_null_pct = float(np.mean(tr_null_pcts)) if tr_null_pcts else 0.0
        max_train_null_pct = float(np.max(tr_null_pcts)) if tr_null_pcts else 0.0
        avg_score_null_pct = float(np.mean(sc_null_pcts)) if sc_null_pcts else 0.0
        max_score_null_pct = float(np.max(sc_null_pcts)) if sc_null_pcts else 0.0
        
        # Time range
        tr_min_ts = pd.Timestamp(train_numeric.index.min()).strftime('%Y-%m-%d %H:%M:%S') if tr_total_rows > 0 else None
        tr_max_ts = pd.Timestamp(train_numeric.index.max()).strftime('%Y-%m-%d %H:%M:%S') if tr_total_rows > 0 else None
        sc_min_ts = pd.Timestamp(score_numeric.index.min()).strftime('%Y-%m-%d %H:%M:%S') if sc_total_rows > 0 else None
        sc_max_ts = pd.Timestamp(score_numeric.index.max()).strftime('%Y-%m-%d %H:%M:%S') if sc_total_rows > 0 else None
        
        # Build summary notes
        note_bits = []
        if low_var_count > 0:
            note_bits.append(f"low_var:{low_var_count}")
        if all_null_train_count > 0:
            note_bits.append(f"null_train:{all_null_train_count}")
        if all_null_score_count > 0:
            note_bits.append(f"null_score:{all_null_score_count}")
        if flatline_count > 0:
            note_bits.append(f"flatline:{flatline_count}")
        
        # Return single summary record
        return [{
            "sensor": f"_SUMMARY_{total_sensors}_SENSORS",
            "train_count": tr_total_rows,
            "train_nulls": int(avg_train_null_pct * tr_total_rows / 100) if tr_total_rows else 0,  # Approx total nulls
            "train_null_pct": avg_train_null_pct,
            "train_std": max_train_null_pct,  # Repurpose: store max null pct for worst sensor
            "train_longest_gap": low_var_count,  # Repurpose: store low-var sensor count
            "train_flatline_span": all_null_train_count,  # Repurpose: store all-null sensor count
            "train_min_ts": tr_min_ts,
            "train_max_ts": tr_max_ts,
            "score_count": sc_total_rows,
            "score_nulls": int(avg_score_null_pct * sc_total_rows / 100) if sc_total_rows else 0,
            "score_null_pct": avg_score_null_pct,
            "score_std": max_score_null_pct,  # Repurpose: store max null pct
            "score_longest_gap": flatline_count,  # Repurpose: store flatline sensor count
            "score_flatline_span": all_null_score_count,  # Repurpose: store all-null sensor count
            "score_min_ts": sc_min_ts,
            "score_max_ts": sc_max_ts,
            "interp_method": interp_method,
            "sampling_secs": sampling_secs,
            "notes": ",".join(note_bits) if note_bits else f"sensors:{total_sensors}"
        }]

    def write_anomaly_events(self, df_events: pd.DataFrame, run_id: str) -> int:
        """Write anomaly events to ACM_Anomaly_Events table.
        
        V11: Adds Confidence column based on episode duration and maturity state.
        
        Args:
            df_events: DataFrame with event data (EquipID, start_ts, end_ts, severity, etc.)
            run_id: Current run ID
        
        Returns:
            Number of rows written
        """
        if not self._check_sql_health() or df_events is None or df_events.empty:
            return 0
        try:
            df = df_events.copy()
            df['RunID'] = run_id
            # Rename columns to match table schema
            col_map = {
                'start_ts': 'StartTime',
                'end_ts': 'EndTime',
                'severity': 'Severity',
                'Detector': 'DetectorType',
                'Score': 'PeakScore',
                'ContributorsJSON': 'ContributorsJSON'
            }
            for old, new in col_map.items():
                if old in df.columns and new not in df.columns:
                    df[new] = df[old]
            
            # V11: Add confidence for each episode - VECTORIZED for performance
            if _CONFIDENCE_AVAILABLE and compute_episode_confidence is not None:
                try:
                    maturity_state = getattr(self, 'maturity_state', 'COLDSTART')
                    
                    # PERFORMANCE FIX: Vectorized episode confidence computation
                    import numpy as np
                    
                    # Determine column names
                    start_col = 'StartTime' if 'StartTime' in df.columns else 'start_ts'
                    end_col = 'EndTime' if 'EndTime' in df.columns else 'end_ts'
                    
                    # Calculate durations vectorized
                    if start_col in df.columns and end_col in df.columns:
                        start_times = pd.to_datetime(df[start_col], errors='coerce')
                        end_times = pd.to_datetime(df[end_col], errors='coerce')
                        duration_seconds = (end_times - start_times).dt.total_seconds().fillna(3600).values
                    else:
                        duration_seconds = np.full(len(df), 3600.0)
                    
                    # Get peak scores vectorized
                    if 'PeakScore' in df.columns:
                        peak_z = pd.to_numeric(df['PeakScore'], errors='coerce').fillna(3.0).values
                    elif 'Score' in df.columns:
                        peak_z = pd.to_numeric(df['Score'], errors='coerce').fillna(3.0).values
                    else:
                        peak_z = np.full(len(df), 3.0)
                    
                    # Vectorized confidence calculation
                    maturity_base = {'COLDSTART': 0.4, 'LEARNING': 0.6, 'CONVERGED': 0.8, 'DEPRECATED': 0.65}.get(maturity_state, 0.5)
                    
                    # Duration confidence: longer episodes more reliable (up to 1 hour = full weight)
                    duration_conf = np.minimum(duration_seconds / 3600.0, 1.0) * 0.2
                    
                    # Peak Z confidence: higher peaks more confident
                    peak_conf = np.minimum(np.abs(peak_z) / 8.0, 1.0) * 0.3
                    
                    # Combined (vectorized)
                    raw_conf = maturity_base * 0.5 + duration_conf + peak_conf
                    df['Confidence'] = np.round(np.clip(raw_conf, 0.2, 0.95), 3)
                    
                except Exception as e:
                    Console.warn(f"Failed to compute episode confidence: {e}", component="EPISODES")
            
            return self.write_table('ACM_Anomaly_Events', df, delete_existing=True)
        except Exception as e:
            Console.warn(f"write_anomaly_events failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_regime_episodes(self, df_reg: pd.DataFrame, run_id: str) -> int:
        """Write regime episodes to ACM_RegimeEpisodes table.
        
        Args:
            df_reg: DataFrame with regime episode data
            run_id: Current run ID
            
        Returns:
            Number of rows written
        """
        if not self._check_sql_health() or df_reg is None or df_reg.empty:
            return 0
        try:
            df = df_reg.copy()
            df['RunID'] = run_id
            return self.write_table('ACM_Regime_Episodes', df, delete_existing=True)
        except Exception as e:
            Console.warn(f"write_regime_episodes failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_pca_model(self, model_row: Dict[str, Any]) -> int:
        """Write PCA model metadata to ACM_PCA_Models table.
        
        v11.1.5: Maps legacy model_row keys to current ACM_PCA_Models schema.
        
        Args:
            model_row: Dict with model metadata (legacy keys from write_pca_outputs)
            
        Returns:
            Number of rows written
        """
        if not self._check_sql_health() or not model_row:
            return 0
        try:
            # v11.1.5: Map legacy model_row keys to ACM_PCA_Models schema
            # Legacy keys: RunID, EquipID, EntryDateTime, NComponents, TargetVar, VarExplainedJSON, 
            #              ScalingSpecJSON, ModelVersion, TrainStartEntryDateTime, TrainEndEntryDateTime
            # Schema: RunID, EquipID, ModelVersion, NComponents, ExplainedVarianceRatio, TrainSamples,
            #         TrainFeatures, ScalerMeanJson, ScalerScaleJson, ComponentsJson, CreatedAt
            
            # Extract ModelVersion as integer (strip 'v' prefix and parse major version)
            model_version_str = str(model_row.get('ModelVersion', '1'))
            if model_version_str.startswith('v'):
                # Parse version string like 'v10.1.0' -> extract major version 10
                try:
                    model_version = int(model_version_str.lstrip('v').split('.')[0])
                except ValueError:
                    model_version = 1
            else:
                try:
                    model_version = int(model_version_str)
                except ValueError:
                    model_version = 1
            
            # Parse VarExplainedJSON to get explained variance ratio
            var_json_str = model_row.get('VarExplainedJSON', '[]')
            try:
                import json
                var_list = json.loads(var_json_str) if isinstance(var_json_str, str) else var_json_str
                explained_var_ratio = float(sum(var_list)) if var_list else None
            except (json.JSONDecodeError, TypeError):
                explained_var_ratio = None
            
            row = {
                'RunID': self.run_id,
                'EquipID': self.equip_id or 0,
                'ModelVersion': model_version,
                'NComponents': int(model_row.get('NComponents', 0)),
                'ExplainedVarianceRatio': explained_var_ratio,
                'TrainSamples': None,  # Not in legacy model_row
                'TrainFeatures': None,  # Not in legacy model_row
                'ScalerMeanJson': None,  # Not in legacy model_row
                'ScalerScaleJson': model_row.get('ScalingSpecJSON'),
                'ComponentsJson': None,  # Not in legacy model_row
                'CreatedAt': datetime.now()
            }
            return self.write_table('ACM_PCA_Models', pd.DataFrame([row]), delete_existing=True)
        except Exception as e:
            Console.warn(f"write_pca_model failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_detector_correlation(self, detector_correlations: Dict[str, Dict[str, float]]) -> int:
        """Write detector correlation matrix to ACM_DetectorCorrelation.
        
        PERFORMANCE: Uses list comprehension instead of nested loops.
        
        Args:
            detector_correlations: Nested dict {detector1: {detector2: correlation}}
        """
        if not self._check_sql_health() or not detector_correlations:
            return 0
        try:
            # PERFORMANCE FIX: Single list comprehension instead of nested append loops
            run_id = self.run_id
            equip_id = self.equip_id or 0
            
            rows = [
                {
                    'RunID': run_id,
                    'EquipID': equip_id,
                    'Detector1': d1,
                    'Detector2': d2,
                    'Correlation': float(corr) if not pd.isna(corr) else 0.0
                }
                for d1, correlations in detector_correlations.items()
                for d2, corr in correlations.items()
            ]
            
            if not rows:
                return 0
            return self.write_table('ACM_DetectorCorrelation', pd.DataFrame(rows), delete_existing=True)
        except Exception as e:
            Console.warn(f"write_detector_correlation failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0

    def write_detector_correlation_from_scores(self, scores_df: pd.DataFrame) -> int:
        """
        Build detector correlation matrix from score frame and persist it.
        """
        if scores_df is None or scores_df.empty:
            return 0
        try:
            z_cols = [c for c in scores_df.columns if c.endswith("_z") and c not in ["drift_z"]]
            if len(z_cols) < 2:
                return 0

            z_df = scores_df[z_cols].dropna(how="all")
            if len(z_df) <= 10:
                return 0

            z_variances = z_df.var()
            z_cols_with_variance = z_variances[z_variances > 1e-10].index.tolist()
            if len(z_cols_with_variance) < 2:
                return 0

            corr_matrix = z_df[z_cols_with_variance].corr(method="pearson")
            det_corr = {
                d1: {d2: corr_matrix.loc[d1, d2] for d2 in corr_matrix.columns}
                for d1 in corr_matrix.index
            }
            return self.write_detector_correlation(det_corr)
        except Exception:
            return 0  # Optional artifact write
    
    def write_drift_series(self, drift_df: pd.DataFrame) -> int:
        """Write drift detection time series to ACM_DriftSeries.
        
        Args:
            drift_df: DataFrame with Timestamp, DriftValue, optionally DriftState
        """
        if not self._check_sql_health() or drift_df is None or drift_df.empty:
            return 0
        try:
            df = drift_df.copy()
            df['RunID'] = self.run_id
            df['EquipID'] = self.equip_id or 0
            # Map column names if needed
            if 'DriftZ' in df.columns and 'DriftValue' not in df.columns:
                df['DriftValue'] = df['DriftZ']
            return self.write_table('ACM_DriftSeries', df, delete_existing=True)
        except Exception as e:
            Console.warn(f"write_drift_series failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_sensor_normalized_ts(self, scores_df: pd.DataFrame, sensor_cols: List[str] = None) -> int:
        """Write normalized sensor z-scores to ACM_SensorNormalized_TS.
        
        Transforms wide-format scores DataFrame (one column per sensor) to long format
        (one row per timestamp/sensor pair) for time-series analysis.
        
        PERFORMANCE: Uses vectorized pd.melt() instead of row-by-row loops.
        
        Schema: ID, RunID, EquipID, Timestamp, SensorName, RawValue, NormalizedValue, CreatedAt
        
        Args:
            scores_df: DataFrame with Timestamp index/column and sensor z-score columns
            sensor_cols: List of sensor column names to extract (if None, uses all float columns)
            
        Returns:
            Number of rows written
        """
        if not self._check_sql_health() or scores_df is None or scores_df.empty:
            return 0
        
        try:
            df = scores_df.copy()
            
            # Ensure Timestamp is a column, not index
            if 'Timestamp' not in df.columns:
                if isinstance(df.index, pd.DatetimeIndex) or df.index.name in ('Timestamp', 'EntryDateTime'):
                    df = df.reset_index()
                    if 'EntryDateTime' in df.columns:
                        df['Timestamp'] = df['EntryDateTime']
                    elif df.columns[0] != 'Timestamp' and pd.api.types.is_datetime64_any_dtype(df[df.columns[0]]):
                        df['Timestamp'] = df.iloc[:, 0]
                elif 'EntryDateTime' in df.columns:
                    df['Timestamp'] = df['EntryDateTime']
                else:
                    dt_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
                    if dt_cols:
                        df['Timestamp'] = df[dt_cols[0]]
                    else:
                        Console.warn("write_sensor_normalized_ts: No Timestamp column found", component="OUTPUT")
                        return 0
            
            # Determine sensor columns
            if sensor_cols is None:
                exclude = {'Timestamp', 'RunID', 'EquipID', 'regime_label', 'fused', 'health', 
                          'ar1_z', 'pca_spe_z', 'pca_t2_z', 'iforest_z', 'gmm_z', 'omr_z',
                          'mhal_z', 'cusum_z', 'drift_z', 'hst_z', 'river_hst_z'}
                sensor_cols = [c for c in df.columns if c not in exclude 
                              and df[c].dtype in ['float64', 'float32', 'int64', 'int32']
                              and not c.endswith('_z')]
            
            # Filter to only columns that exist
            sensor_cols = [c for c in sensor_cols if c in df.columns]
            
            if not sensor_cols:
                Console.debug("write_sensor_normalized_ts: No sensor columns found", component="OUTPUT")
                return 0
            
            # PERFORMANCE FIX: Use vectorized pd.melt() instead of row-by-row loops
            # This is 100-1000x faster than the previous nested loop approach
            long_df = df[['Timestamp'] + sensor_cols].melt(
                id_vars=['Timestamp'],
                value_vars=sensor_cols,
                var_name='SensorName',
                value_name='NormalizedValue'
            )
            
            # Drop NaN values (vectorized)
            long_df = long_df.dropna(subset=['NormalizedValue'])
            
            if long_df.empty:
                return 0
            
            # Add required columns (vectorized assignment)
            long_df['RunID'] = self.run_id or ''
            long_df['EquipID'] = self.equip_id or 0
            long_df['RawValue'] = None
            
            # Reorder columns for consistency
            long_df = long_df[['RunID', 'EquipID', 'Timestamp', 'SensorName', 'RawValue', 'NormalizedValue']]
            
            # v11.1.5 FIX: Delete by TIMESTAMP RANGE instead of just RunID
            # This prevents duplicates when overlapping batch runs cover same time periods
            min_ts = long_df['Timestamp'].min()
            max_ts = long_df['Timestamp'].max()
            if pd.notna(min_ts) and pd.notna(max_ts) and self.sql_client and self.equip_id:
                try:
                    with self.sql_client.cursor() as cur:
                        cur.execute(
                            "DELETE FROM dbo.[ACM_SensorNormalized_TS] "
                            "WHERE EquipID = ? AND Timestamp BETWEEN ? AND ?",
                            (int(self.equip_id), min_ts, max_ts)
                        )
                        deleted = cur.rowcount
                        if deleted > 0:
                            Console.info(
                                f"Deleted {deleted} overlapping rows from ACM_SensorNormalized_TS",
                                component="OUTPUT", table="ACM_SensorNormalized_TS",
                                equip_id=self.equip_id, min_ts=str(min_ts), max_ts=str(max_ts)
                            )
                    if hasattr(self.sql_client, "commit"):
                        self.sql_client.commit()
                    elif hasattr(self.sql_client, "conn") and hasattr(self.sql_client.conn, "commit"):
                        if not getattr(self.sql_client.conn, "autocommit", True):
                            self.sql_client.conn.commit()
                except Exception as del_ex:
                    Console.warn(
                        f"Failed to delete overlapping sensor data: {del_ex}",
                        component="OUTPUT", table="ACM_SensorNormalized_TS",
                        equip_id=self.equip_id, error_type=type(del_ex).__name__
                    )
            
            # Now insert new data (delete_existing=False since we handled it above)
            return self.write_table('ACM_SensorNormalized_TS', long_df, delete_existing=False)
            
        except Exception as e:
            Console.warn(f"write_sensor_normalized_ts failed: {e}", component="OUTPUT", 
                        error=str(e)[:200], sensor_count=len(sensor_cols) if sensor_cols else 0)
            return 0
    
    def write_sensor_correlations(self, corr_matrix: pd.DataFrame, corr_type: str = 'pearson') -> int:
        """Write sensor correlation matrix to ACM_SensorCorrelations.
        
        PERFORMANCE: Uses vectorized numpy operations instead of nested loops.
        NOTE: Keeps only latest run's correlations per equipment (deletes all prior).
        
        Args:
            corr_matrix: Pandas correlation matrix (sensors x sensors)
            corr_type: 'pearson' or 'spearman'
        """
        if not self._check_sql_health() or corr_matrix is None or corr_matrix.empty:
            return 0
        try:
            import numpy as np
            
            # PERFORMANCE FIX: Vectorized upper triangle extraction
            # Get upper triangle indices (including diagonal)
            sensors = list(corr_matrix.columns)
            n = len(sensors)
            
            # Use numpy to get upper triangle mask
            mask = np.triu(np.ones((n, n), dtype=bool))
            
            # Stack to create all (i, j) pairs efficiently
            rows_idx, cols_idx = np.where(mask)
            
            # Extract correlation values at those positions
            corr_values = corr_matrix.values[rows_idx, cols_idx]
            
            # Build DataFrame directly (vectorized)
            df = pd.DataFrame({
                'RunID': self.run_id,
                'EquipID': self.equip_id or 0,
                'Sensor1': [sensors[i] for i in rows_idx],
                'Sensor2': [sensors[j] for j in cols_idx],
                'Correlation': corr_values,
                'CorrelationType': corr_type
            })
            
            # Drop NaN correlations (vectorized)
            df = df.dropna(subset=['Correlation'])
            
            if df.empty:
                return 0
            
            # Delete ALL prior correlations for this equipment (not just this run)
            # We only need the latest correlation matrix per equipment
            try:
                with self.sql_client.cursor() as cur:
                    cur.execute("DELETE FROM dbo.[ACM_SensorCorrelations] WHERE EquipID = ?", 
                               (int(self.equip_id or 0),))
                    if hasattr(self.sql_client, "commit"):
                        self.sql_client.commit()
            except Exception as del_ex:
                Console.debug(f"ACM_SensorCorrelations cleanup skipped: {del_ex}", component="OUTPUT")
            
            return self.write_table('ACM_SensorCorrelations', df, delete_existing=False)
        except Exception as e:
            Console.warn(f"write_sensor_correlations failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0

    def write_sensor_correlations_from_raw(self, raw_score: Optional[pd.DataFrame]) -> int:
        """
        Build sensor correlation matrix from raw sensor frame and persist it.
        """
        if raw_score is None or not hasattr(raw_score, "corr") or raw_score.shape[1] < 2:
            return 0
        try:
            sensor_cols = [
                c for c in raw_score.columns
                if raw_score[c].dtype in ["float64", "float32", "int64", "int32"]
            ]
            if len(sensor_cols) < 2:
                return 0

            sensor_variances = raw_score[sensor_cols].var()
            sensor_cols_with_variance = sensor_variances[sensor_variances > 1e-10].index.tolist()
            if len(sensor_cols_with_variance) < 2:
                return 0

            sensor_corr = raw_score[sensor_cols_with_variance].corr(method="pearson")
            return self.write_sensor_correlations(sensor_corr, corr_type="pearson")
        except Exception:
            return 0  # Optional artifact write
    
    def write_feature_drop_log(self, dropped_features: List[Dict[str, Any]]) -> int:
        """Write dropped features log to ACM_FeatureDropLog.
        
        Args:
            dropped_features: List of dicts with keys: FeatureName, DropReason, DropValue, Threshold
        """
        if not self._check_sql_health() or not dropped_features:
            return 0
        try:
            df = pd.DataFrame(dropped_features)
            df['RunID'] = self.run_id
            df['EquipID'] = self.equip_id or 0
            return self.write_table('ACM_FeatureDropLog', df, delete_existing=True)
        except Exception as e:
            Console.warn(f"write_feature_drop_log failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_calibration_summary(self, calibration_data: List[Dict[str, Any]]) -> int:
        """Write detector calibration summary to ACM_CalibrationSummary.
        
        Args:
            calibration_data: List of dicts with DetectorType, CalibrationScore, etc.
        """
        if not self._check_sql_health() or not calibration_data:
            return 0
        try:
            df = pd.DataFrame(calibration_data)
            df['RunID'] = self.run_id
            df['EquipID'] = self.equip_id or 0
            return self.write_table('ACM_CalibrationSummary', df, delete_existing=True)
        except Exception as e:
            Console.warn(f"write_calibration_summary failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_regime_occupancy(self, occupancy_data: List[Dict[str, Any]]) -> int:
        """Write regime occupancy stats to ACM_RegimeOccupancy.
        
        Args:
            occupancy_data: List of dicts with RegimeLabel, DwellTimeHours, DwellFraction, etc.
        """
        if not self._check_sql_health() or not occupancy_data:
            return 0
        try:
            df = pd.DataFrame(occupancy_data)
            df['RunID'] = self.run_id
            df['EquipID'] = self.equip_id or 0
            return self.write_table('ACM_RegimeOccupancy', df, delete_existing=True)
        except Exception as e:
            Console.warn(f"write_regime_occupancy failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_regime_transitions(self, transition_matrix: Dict[str, Dict[str, int]]) -> int:
        """Write regime transition matrix to ACM_RegimeTransitions.
        
        PERFORMANCE: Uses list comprehension instead of nested loops.
        
        Args:
            transition_matrix: Nested dict {from_regime: {to_regime: count}}
        """
        if not self._check_sql_health() or not transition_matrix:
            return 0
        try:
            run_id = self.run_id
            equip_id = self.equip_id or 0
            
            # PERFORMANCE FIX: List comprehension with precomputed totals
            rows = [
                {
                    'RunID': run_id,
                    'EquipID': equip_id,
                    'FromRegime': str(from_r),
                    'ToRegime': str(to_r),
                    'TransitionCount': int(count),
                    'TransitionProbability': float(count) / sum(transitions.values()) if sum(transitions.values()) > 0 else 0.0
                }
                for from_r, transitions in transition_matrix.items()
                for to_r, count in transitions.items()
            ]
            
            if not rows:
                return 0
            return self.write_table('ACM_RegimeTransitions', pd.DataFrame(rows), delete_existing=True)
        except Exception as e:
            Console.warn(f"write_regime_transitions failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_contribution_timeline(self, contributions_df: pd.DataFrame) -> int:
        """Write detector contribution timeline to ACM_ContributionTimeline.
        
        Args:
            contributions_df: DataFrame with Timestamp, DetectorType, ContributionPct
        """
        if not self._check_sql_health() or contributions_df is None or contributions_df.empty:
            return 0
        try:
            df = contributions_df.copy()
            df['RunID'] = self.run_id
            df['EquipID'] = self.equip_id or 0
            return self.write_table('ACM_ContributionTimeline', df, delete_existing=True)
        except Exception as e:
            Console.warn(f"write_contribution_timeline failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_regime_promotion_log(self, promotions: List[Dict[str, Any]]) -> int:
        """Write regime maturity promotions to ACM_RegimePromotionLog.
        
        Args:
            promotions: List of dicts with RegimeLabel, FromState, ToState, Reason, etc.
        """
        if not self._check_sql_health() or not promotions:
            return 0
        try:
            df = pd.DataFrame(promotions)
            df['RunID'] = self.run_id
            df['EquipID'] = self.equip_id or 0
            return self.write_table('ACM_RegimePromotionLog', df, delete_existing=False)  # Append, don't delete
        except Exception as e:
            Console.warn(f"write_regime_promotion_log failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_refit_request(
        self, 
        reasons: List[str],
        anomaly_rate: Optional[float] = None,
        drift_score: Optional[float] = None,
        regime_quality: Optional[float] = None
    ) -> int:
        """Write refit request to ACM_RefitRequests table.
        
        Creates the table if it doesn't exist and inserts a refit request record.
        This is used by auto-tuning when model quality degrades.
        
        Args:
            reasons: List of reasons triggering the refit request
            anomaly_rate: Current anomaly rate (if triggered by high anomaly rate)
            drift_score: Drift score (if triggered by drift)
            regime_quality: Regime silhouette score (if triggered by regime quality)
            
        Returns:
            1 if request written successfully, 0 otherwise
        """
        if not self._check_sql_health():
            return 0
        
        try:
            with self.sql_client.cursor() as cur:
                # Ensure table exists (idempotent DDL)
                cur.execute("""
                    IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[ACM_RefitRequests]') AND type in (N'U'))
                    BEGIN
                        CREATE TABLE [dbo].[ACM_RefitRequests] (
                            [RequestID] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                            [EquipID] INT NOT NULL,
                            [RequestedAt] DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                            [Reason] NVARCHAR(MAX) NULL,
                            [AnomalyRate] FLOAT NULL,
                            [DriftScore] FLOAT NULL,
                            [ModelAgeHours] FLOAT NULL,
                            [RegimeQuality] FLOAT NULL,
                            [Acknowledged] BIT NOT NULL DEFAULT 0,
                            [AcknowledgedAt] DATETIME2 NULL
                        );
                        CREATE INDEX [IX_RefitRequests_EquipID_Ack] ON [dbo].[ACM_RefitRequests]([EquipID], [Acknowledged]);
                    END
                """)
                
                # Insert request - use datetime.now() so RequestedAt matches log timestamps (both local time)
                cur.execute("""
                    INSERT INTO [dbo].[ACM_RefitRequests]
                        (EquipID, RequestedAt, Reason, AnomalyRate, DriftScore, RegimeQuality)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    int(self.equip_id or 0),
                    datetime.now(),
                    "; ".join(reasons) if reasons else None,
                    float(anomaly_rate) if anomaly_rate is not None else None,
                    float(drift_score) if drift_score is not None else None,
                    float(regime_quality) if regime_quality is not None else None,
                ))
                
            Console.info("SQL insert to ACM_RefitRequests: 1 rows", component="OUTPUT")
            return 1
        except Exception as e:
            Console.warn(f"write_refit_request failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_fusion_metrics(
        self, 
        fusion_weights: Dict[str, float], 
        tuning_diagnostics: Dict[str, Any],
        previous_weights: Optional[Dict[str, float]] = None
    ) -> int:
        """Write fusion tuning diagnostics and metrics to ACM_RunMetrics (EAV format).
        
        Writes fusion weight metrics, quality scores, and sample counts to ACM_RunMetrics
        table in Entity-Attribute-Value format for flexibility.
        
        Args:
            fusion_weights: Dict mapping detector names to their fusion weights
            tuning_diagnostics: Dict with detector_metrics, method, etc.
            previous_weights: Optional dict of weights from previous run (for warm start tracking)
            
        Returns:
            Number of records written (0 if failed or disabled)
        """
        if not self._check_sql_health() or not tuning_diagnostics:
            return 0
            
        try:
            # Add timestamp and metadata
            tuning_diagnostics["timestamp"] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            tuning_diagnostics["warm_started"] = previous_weights is not None
            if previous_weights:
                tuning_diagnostics["previous_weights"] = previous_weights
            
            # Build metrics rows for CSV output
            metrics_rows = []
            for detector_name, weight in fusion_weights.items():
                det_metrics = tuning_diagnostics.get("detector_metrics", {}).get(detector_name, {})
                metrics_rows.append({
                    "detector_name": detector_name,
                    "weight": weight,
                    "n_samples": det_metrics.get("n_samples", 0),
                    "quality_score": det_metrics.get("quality_score", 0.0),
                    "tuning_method": tuning_diagnostics.get("method", "unknown"),
                    "timestamp": tuning_diagnostics["timestamp"]
                })
            
            if not metrics_rows:
                return 0
            
            # SQL mode: Write to ACM_RunMetrics in EAV format
            if not self.sql_client:
                return 0
                
            timestamp_now = pd.Timestamp.now()
            insert_records = [
                (self.run_id, int(self.equip_id), f"fusion.weight.{row['detector_name']}", 
                 float(row['weight']), timestamp_now)
                for row in metrics_rows
            ] + [
                (self.run_id, int(self.equip_id), f"fusion.quality.{row['detector_name']}", 
                 float(row['quality_score']), timestamp_now)
                for row in metrics_rows
            ] + [
                (self.run_id, int(self.equip_id), f"fusion.n_samples.{row['detector_name']}", 
                 float(row['n_samples']), timestamp_now)
                for row in metrics_rows
            ]
            
            insert_sql = """
                INSERT INTO dbo.ACM_RunMetrics 
                (RunID, EquipID, MetricName, MetricValue, CreatedAt)
                VALUES (?, ?, ?, ?, ?)
            """
            
            with self.sql_client.cursor() as cur:
                cur.fast_executemany = True
                cur.executemany(insert_sql, insert_records)
            self.sql_client.conn.commit()
            
            Console.info(f"SQL insert to ACM_RunMetrics: {len(insert_records)} rows", component="OUTPUT")
            return len(insert_records)
            
        except Exception as e:
            Console.warn(f"write_fusion_metrics failed: {e}", component="OUTPUT",
                         equip=self.equipment, error=str(e)[:200])
            return 0
    
    def check_refit_request(self) -> bool:
        """Check for pending refit requests in ACM_RefitRequests table.
        
        If a pending request exists, acknowledges it so it won't be processed again
        on the next run.
        
        Returns:
            True if a pending refit request was found and acknowledged, False otherwise
        """
        if not self._check_sql_health():
            return False
            
        try:
            with self.sql_client.cursor() as cur:
                cur.execute(
                    """
                    IF OBJECT_ID(N'[dbo].[ACM_RefitRequests]', N'U') IS NOT NULL
                    BEGIN
                        SELECT TOP 1 RequestID, RequestedAt, Reason
                        FROM [dbo].[ACM_RefitRequests]
                        WHERE EquipID = ? AND Acknowledged = 0
                        ORDER BY RequestedAt DESC
                    END
                    """,
                    (int(self.equip_id),),
                )
                row = cur.fetchone()
                if row:
                    Console.warn(f"SQL refit request found: id={row[0]} at {row[1]}", component="MODEL",
                                 equip=self.equipment, refit_request_id=row[0])
                    # Acknowledge refit so it is not re-used next run
                    cur.execute(
                        "UPDATE [dbo].[ACM_RefitRequests] SET Acknowledged = 1, AcknowledgedAt = SYSDATETIME() WHERE RequestID = ?",
                        (int(row[0]),),
                    )
                    self.sql_client.conn.commit()
                    return True
        except Exception as rf_err:
            Console.warn(f"Refit check failed: {rf_err}", component="MODEL",
                         equip=self.equipment, error_type=type(rf_err).__name__, error=str(rf_err)[:200])
        
        return False
    
    def update_baseline_buffer(
        self, 
        score_numeric: pd.DataFrame,
        cfg: Dict[str, Any],
        coldstart_complete: bool
    ) -> bool:
        """Update the ACM_BaselineBuffer table with latest raw score data.
        
        Uses smart refresh logic to avoid writing on every batch:
        - Always write during coldstart
        - Write periodically (every N batches) after coldstart
        - Uses vectorized pandas melt for 100x speedup over loops
        
        Args:
            score_numeric: Raw score DataFrame with sensor columns
            cfg: Configuration dictionary
            coldstart_complete: Whether coldstart phase is complete
        
        Returns:
            True if buffer was written, False if skipped
        """
        if not self._check_sql_health():
            return False
            
        baseline_cfg = (cfg.get("runtime", {}) or {}).get("baseline", {}) or {}
        window_hours = float(baseline_cfg.get("window_hours", 72))
        max_points = int(baseline_cfg.get("max_points", 100000))
        refresh_interval = int(baseline_cfg.get("refresh_interval_batches", 10))
        
        # Determine if we should write baseline buffer this run
        should_write_buffer = False
        write_reason = ""
        recent_run_count = 0
        
        if not coldstart_complete:
            # Coldstart in progress - always write to build baseline
            should_write_buffer = True
            write_reason = "coldstart"
        else:
            # Models exist - check periodic refresh
            try:
                with self.sql_client.cursor() as cur:
                    run_count_result = cur.execute(
                        "SELECT COUNT(*) FROM ACM_Runs WHERE EquipID = ? AND CreatedAt > DATEADD(DAY, -7, GETDATE())",
                        (int(self.equip_id),)
                    ).fetchone()
                    recent_run_count = run_count_result[0] if run_count_result else 0
                    if recent_run_count == 0 or (recent_run_count % refresh_interval == 0):
                        should_write_buffer = True
                        write_reason = f"periodic_refresh (batch {recent_run_count})"
            except Exception:
                should_write_buffer = True
                write_reason = "fallback"
        
        if not should_write_buffer:
            batches_until_refresh = refresh_interval - (recent_run_count % refresh_interval) if refresh_interval > 0 else 0
            Console.info(f"Skipping buffer write (models exist, next refresh in {batches_until_refresh} batches)", component="BASELINE")
            return False
        
        # Skip if no data to write
        if len(score_numeric) == 0:
            return False
        
        # Normalize index to local naive timestamps
        to_append = score_numeric.copy()
        to_append = self._ensure_local_index(to_append)
        
        # OPTIMIZATION v10.2.1: Vectorized pandas melt (100x faster than Python loops)
        try:
            to_append_reset = to_append.reset_index()
            ts_col = to_append_reset.columns[0]
            
            long_df = to_append_reset.melt(
                id_vars=[ts_col],
                var_name='SensorName',
                value_name='SensorValue'
            )
            
            long_df = long_df.dropna(subset=['SensorValue'])
            long_df['EquipID'] = int(self.equip_id)
            long_df['DataQuality'] = None
            # Normalize timestamp column to local naive
            long_df = long_df.set_index(ts_col)
            long_df = self._ensure_local_index(long_df)
            long_df = long_df.reset_index().rename(columns={ts_col: 'Timestamp'})
            long_df = long_df[['EquipID', 'Timestamp', 'SensorName', 'SensorValue', 'DataQuality']]
            
            if len(long_df) > 0:
                baseline_records = list(long_df.itertuples(index=False, name=None))
                
                insert_sql = """
                INSERT INTO dbo.ACM_BaselineBuffer (EquipID, Timestamp, SensorName, SensorValue, DataQuality)
                VALUES (?, ?, ?, ?, ?)
                """
                with self.sql_client.cursor() as cur:
                    cur.fast_executemany = True
                    cur.executemany(insert_sql, baseline_records)
                self.sql_client.conn.commit()
                Console.info(f"SQL insert to ACM_BaselineBuffer: {len(baseline_records)} rows ({write_reason})", component="OUTPUT")
                
                # Run cleanup procedure
                try:
                    with self.sql_client.cursor() as cur:
                        cur.execute("EXEC dbo.usp_CleanupBaselineBuffer @EquipID=?, @RetentionHours=?, @MaxRowsPerEquip=?",
                                  (int(self.equip_id), int(window_hours), max_points))
                    self.sql_client.conn.commit()
                except Exception as cleanup_err:
                    Console.warn(f"Cleanup procedure failed: {cleanup_err}", component="BASELINE",
                                 equip=self.equipment, equip_id=self.equip_id, error=str(cleanup_err)[:200])
                
                return True
                
        except Exception as sql_err:
            Console.warn(f"SQL write to ACM_BaselineBuffer failed: {sql_err}", component="BASELINE",
                         equip=self.equipment, equip_id=self.equip_id, error=str(sql_err)[:200])
            try:
                self.sql_client.conn.rollback()
            except:
                pass
        
        return False
    
    def _ensure_local_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure the DataFrame index is a timezone-naive local DatetimeIndex.

        Simplified policy: treat all timestamps as local time and drop any tz info.
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, errors="coerce")
        else:
            # If timezone-aware, strip tz information and keep local wall-clock times
            try:
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
            except Exception:
                # Fallback: coerce to naive datetimes
                df.index = pd.to_datetime(df.index, errors="coerce")
        return df
    
    def write_drift_controller(self, controller_state: Dict[str, Any]) -> int:
        """Write drift controller state to ACM_DriftController.
        
        Args:
            controller_state: Dict with ControllerState, Threshold, Sensitivity, etc.
        """
        if not self._check_sql_health() or not controller_state:
            return 0
        try:
            row = dict(controller_state)
            row['RunID'] = self.run_id
            row['EquipID'] = self.equip_id or 0
            return self.write_table('ACM_DriftController', pd.DataFrame([row]), delete_existing=True)
        except Exception as e:
            Console.warn(f"write_drift_controller failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_regime_definitions(self, regime_defs: List[Dict[str, Any]], version: int) -> int:
        """Write regime definitions to ACM_RegimeDefinitions (v11).
        
        Args:
            regime_defs: List of dicts with RegimeID, RegimeName, CentroidJSON, etc.
            version: Regime model version number
        """
        if not self._check_sql_health() or not regime_defs:
            return 0
        try:
            df = pd.DataFrame(regime_defs)
            df['EquipID'] = self.equip_id or 0
            df['RegimeVersion'] = version
            df['RunID'] = self.run_id
            return self.write_table('ACM_RegimeDefinitions', df, delete_existing=False)  # Keep history
        except Exception as e:
            Console.warn(f"write_regime_definitions failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_active_models(self, model_state: Dict[str, Any]) -> int:
        """Write/update active model versions to ACM_ActiveModels (v11).
        
        Args:
            model_state: Dict with ActiveRegimeVersion, RegimeMaturityState, etc.
        
        Note: ACM_ActiveModels has EquipID only (no RunID), so we delete by EquipID before insert.
        """
        if not self._check_sql_health() or not model_state:
            return 0
        try:
            row = dict(model_state)
            row['EquipID'] = self.equip_id or 0
            row['LastUpdatedAt'] = datetime.now()
            row['LastUpdatedBy'] = self.run_id
            
            # Manual delete by EquipID (table has no RunID column)
            try:
                with self.sql_client.cursor() as cur:
                    cur.execute("DELETE FROM dbo.[ACM_ActiveModels] WHERE EquipID = ?", (int(self.equip_id or 0),))
                    if hasattr(self.sql_client, "commit"):
                        self.sql_client.commit()
            except Exception as del_ex:
                Console.debug(f"ACM_ActiveModels delete skipped: {del_ex}", component="OUTPUT")
            
            # Insert new row (delete_existing=False since we manually deleted)
            return self.write_table('ACM_ActiveModels', pd.DataFrame([row]), delete_existing=False)
        except Exception as e:
            Console.warn(f"write_active_models failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_data_contract_validation(self, validation_result: Dict[str, Any]) -> int:
        """Write data contract validation result to ACM_DataContractValidation (v11).
        
        Args:
            validation_result: Dict with Passed, RowsValidated, ColumnsValidated, IssuesJSON, etc.
        """
        if not self._check_sql_health() or not validation_result:
            return 0
        try:
            row = dict(validation_result)
            row['RunID'] = self.run_id
            row['EquipID'] = self.equip_id or 0
            row['ValidatedAt'] = datetime.now()
            return self.write_table('ACM_DataContractValidation', pd.DataFrame([row]), delete_existing=True)
        except Exception as e:
            Console.warn(f"write_data_contract_validation failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_seasonal_patterns(self, patterns: List[Dict[str, Any]]) -> int:
        """Write detected seasonal patterns to ACM_SeasonalPatterns (v11).
        
        Args:
            patterns: List of dicts with SensorName, PatternType, PeriodHours, Amplitude, etc.
        """
        if not self._check_sql_health() or not patterns:
            return 0
        try:
            df = pd.DataFrame(patterns)
            df['EquipID'] = self.equip_id or 0
            df['DetectedAt'] = datetime.now()
            df['RunID'] = self.run_id
            return self.write_table('ACM_SeasonalPatterns', df, delete_existing=True)
        except Exception as e:
            Console.warn(f"write_seasonal_patterns failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0

    def write_sensor_normalized_ts_from_raw(self, raw_score: Optional[pd.DataFrame], max_total_rows: int = 10000) -> int:
        """
        Sample raw sensor frame and persist normalized sensor time series rows.
        """
        if raw_score is None or len(raw_score) == 0:
            return 0
        try:
            sensor_cols = [
                c for c in raw_score.columns
                if raw_score[c].dtype in ["float64", "float32", "int64", "int32"]
            ]
            if not sensor_cols:
                return 0

            max_timestamps = max(100, int(max_total_rows) // len(sensor_cols))
            sample_frame = raw_score
            if len(raw_score) > max_timestamps:
                step = max(1, len(raw_score) // max_timestamps)
                sample_frame = raw_score.iloc[::step]

            return self.write_sensor_normalized_ts(sample_frame, sensor_cols)
        except Exception as e:
            Console.warn(
                f"Sensor normalized TS write failed: {e}",
                component="PERSIST",
                error_type=type(e).__name__,
                error=str(e)[:200],
            )
            return 0

    def write_seasonal_patterns_from_detected(self, seasonal_patterns: Optional[Dict[str, List[Any]]]) -> int:
        """
        Flatten detected seasonal patterns and persist them to SQL.
        """
        if not seasonal_patterns:
            return 0
        try:
            pattern_list: List[Dict[str, Any]] = []
            for sensor_name, patterns in seasonal_patterns.items():
                for pattern in patterns:
                    pattern_dict = pattern.to_dict()
                    pattern_dict["SensorName"] = sensor_name
                    pattern_dict["PatternType"] = pattern_dict.pop("period_type", "DAILY")
                    pattern_dict["PeriodHours"] = pattern_dict.pop("period_hours", 24.0)
                    pattern_dict["Amplitude"] = pattern_dict.pop("amplitude", 0.0)
                    pattern_dict["PhaseShift"] = pattern_dict.pop("phase_shift", 0.0)
                    pattern_dict["Confidence"] = pattern_dict.pop("confidence", 0.5)
                    pattern_dict.pop("sensor", None)
                    pattern_list.append(pattern_dict)
            if not pattern_list:
                return 0
            return self.write_seasonal_patterns(pattern_list)
        except Exception as e:
            Console.warn(
                f"Seasonal patterns write failed: {e}",
                component="PERSIST",
                error_type=type(e).__name__,
                error=str(e)[:200],
            )
            return 0

    def release_persist_memory(
        self,
        raw_train: Optional[pd.DataFrame],
        raw_score: Optional[pd.DataFrame],
        iforest_detector: Optional[Any] = None,
        omr_detector: Optional[Any] = None,
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """
        Free large persist-phase objects after SQL writes are complete.

        Returns:
            Tuple of cleared (raw_train, raw_score) placeholders.
        """
        raw_train = None
        raw_score = None

        if iforest_detector is not None and hasattr(iforest_detector, "model"):
            iforest_detector.model = None

        if omr_detector is not None and hasattr(omr_detector, "model"):
            omr_detector.model = None

        gc.collect()
        return raw_train, raw_score
    
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            **self.stats,
            'avg_write_time': self.stats['write_time'] / max(1, self.stats['sql_writes']),
            'sql_success_rate': 1.0 - (self.stats['sql_failures'] / max(1, self.stats['sql_health_checks']))
        }
    
    def flush(self) -> None:
        """OUT-18: Flush current batch without finalizing (for auto-flush triggers)."""
        with self._batch_lock:
            # Reset batch for next accumulation
            self._current_batch = OutputBatch()
    
    def flush_and_finalize(self) -> Dict[str, Any]:
        """Flush any pending operations and return final statistics."""
        self.flush()  # OUT-18: Use flush() for DRY
        
        stats = self.get_stats()
        # Note: sql_writes only tracks writes via write_dataframe() method
        # Many tables are written via direct SQL, batched transactions, etc.
        # This is intentionally low-level debug info, not a complete count
        Console.debug(f"OutputManager stats: {stats['sql_writes']} write_dataframe calls, "
                f"{stats['total_rows']} batch rows, "
                f"{stats['avg_write_time']:.3f}s avg write time", component="OUTPUT")
        
        return stats

    def close(self) -> None:
        """Gracefully finalize outstanding work. Compatible with acm_main finally block."""
        try:
            self.flush_and_finalize()
        except Exception:
            pass

    # ==================== BULK DELETE OPTIMIZATION ====================

    def _delete_timeline_overlaps(self, tables: List[str], min_ts: pd.Timestamp, max_ts: pd.Timestamp) -> int:
        """
        v11.1.5 FIX: Delete overlapping rows from timeline tables by TIMESTAMP RANGE.
        
        Unlike _bulk_delete_analytics_tables which deletes by RunID, this method
        deletes by EquipID + Timestamp range to prevent duplicate data when
        overlapping batch runs cover the same time periods.
        
        Args:
            tables: List of table names to clean (must have Timestamp column)
            min_ts: Minimum timestamp in the data being written
            max_ts: Maximum timestamp in the data being written
            
        Returns:
            Total rows deleted across all tables
        """
        if not self.sql_client or not self.equip_id:
            return 0
        if pd.isna(min_ts) or pd.isna(max_ts):
            return 0
            
        total_deleted = 0
        cursor_factory = lambda: cast(Any, self.sql_client).cursor()
        
        for table_name in tables:
            if table_name not in ALLOWED_TABLES:
                continue
                
            try:
                with self.sql_client.cursor() as cur:
                    cur.execute(
                        f"DELETE FROM dbo.[{table_name}] "
                        f"WHERE EquipID = ? AND Timestamp BETWEEN ? AND ?",
                        (int(self.equip_id), min_ts, max_ts)
                    )
                    deleted = cur.rowcount
                    if deleted > 0:
                        total_deleted += deleted
                        Console.info(
                            f"Deleted {deleted} overlapping rows from {table_name}",
                            component="OUTPUT", table=table_name,
                            equip_id=self.equip_id, min_ts=str(min_ts), max_ts=str(max_ts)
                        )
                        
                # Commit after each table
                if hasattr(self.sql_client, "commit"):
                    self.sql_client.commit()
                elif hasattr(self.sql_client, "conn") and hasattr(self.sql_client.conn, "commit"):
                    if not getattr(self.sql_client.conn, "autocommit", True):
                        self.sql_client.conn.commit()
                        
            except Exception as del_ex:
                Console.warn(
                    f"Failed to delete overlapping data from {table_name}: {del_ex}",
                    component="OUTPUT", table=table_name,
                    equip_id=self.equip_id, error_type=type(del_ex).__name__
                )
                
        return total_deleted

    def _bulk_delete_analytics_tables(self, tables: List[str]) -> int:
        """
        PERF-OPT v11: Delete existing rows for current RunID/EquipID from multiple tables in ONE SQL batch.

        - Filters to ALLOWED_TABLES only.
        - Skips non-existent tables (cached).
        - Chooses predicate based on presence of RunID / EquipID columns.
        - Executes a single SQL batch to avoid N round-trips.

        Returns:
            Number of tables for which a DELETE statement was included in the batch.
            (Rowcount not tracked in this batched approach.)
        """
        if not self.sql_client or not self.run_id:
            return 0

        start_time = time.perf_counter()
        tables_targeted = 0

        # Local cursor factory for helper functions that expect a callable
        cursor_factory = lambda: cast(Any, self.sql_client).cursor()

        try:
            # Normalize candidate tables: allowed + unique, preserve input order
            seen = set()
            candidate_tables: List[str] = []
            for t in tables:
                if not t or t in seen:
                    continue
                seen.add(t)
                if t in ALLOWED_TABLES:
                    candidate_tables.append(t)

            if not candidate_tables:
                return 0

            delete_statements: List[str] = []

            for table_name in candidate_tables:
                # Table existence (cached)
                exists = self._table_exists_cache.get(table_name)
                if exists is None:
                    try:
                        exists = bool(_table_exists(cursor_factory, table_name))
                    except Exception:
                        exists = False
                    self._table_exists_cache[table_name] = exists

                if not exists:
                    continue

                # Column presence (prefer cached insertable/columns; avoid repeated metadata calls)
                table_cols = (
                    self._table_insertable_cache.get(table_name)
                    or self._table_columns_cache.get(table_name)
                )

                if table_cols is None:
                    try:
                        cols = set(_get_insertable_columns(cursor_factory, table_name) or [])
                        if not cols:
                            cols = set(_get_table_columns(cursor_factory, table_name) or [])
                        table_cols = cols
                        # Cache in insertable cache since we use it as "known columns" anyway
                        self._table_insertable_cache[table_name] = table_cols
                    except Exception:
                        # If we cannot introspect columns, skip (safe default)
                        continue

                # Build the WHERE predicate
                has_runid = "RunID" in table_cols
                has_equipid = "EquipID" in table_cols and (self.equip_id is not None)

                if not has_runid:
                    continue  # no RunID => cannot safely scope delete to current run

                if has_equipid:
                    delete_statements.append(
                        f"DELETE FROM dbo.[{table_name}] WHERE RunID = @RunID AND EquipID = @EquipID"
                    )
                else:
                    delete_statements.append(
                        f"DELETE FROM dbo.[{table_name}] WHERE RunID = @RunID"
                    )

                # Mark as pre-deleted so _bulk_insert_sql can skip its own per-table pre-delete logic
                self._bulk_predeleted_tables.add(table_name)
                tables_targeted += 1

            if not delete_statements:
                return 0

            # One network round-trip
            batch_sql = ";\n".join(delete_statements)

            cur = cursor_factory()
            try:
                # Parameter binding via pyodbc placeholders within DECLARE assignment is OK.
                # We declare parameters once and reuse them in all statements.
                sql = f"""
DECLARE @RunID NVARCHAR(36) = ?;
DECLARE @EquipID INT = ?;
{batch_sql};
"""
                cur.execute(sql, (self.run_id, int(self.equip_id or 0)))

                # Commit behavior: follow your existing pattern (depends on autocommit / wrapper)
                if hasattr(self.sql_client, "commit"):
                    self.sql_client.commit()
                elif hasattr(self.sql_client, "conn") and hasattr(self.sql_client.conn, "commit"):
                    if not getattr(self.sql_client.conn, "autocommit", True):
                        self.sql_client.conn.commit()

            finally:
                try:
                    cur.close()
                except Exception:
                    pass

            elapsed = time.perf_counter() - start_time
            Console.info(
                f"Bulk pre-delete: {tables_targeted} tables targeted, {len(delete_statements)} DELETE statements in {elapsed:.2f}s (batched)",
                component="OUTPUT",
                tables_targeted=tables_targeted,
                delete_count=len(delete_statements)
            )
            return tables_targeted

        except Exception as e:
            Console.warn(
                f"Bulk pre-delete failed (non-fatal): {e}",
                component="OUTPUT",
                tables=len(tables),
                equip_id=self.equip_id,
                run_id=self.run_id,
                error_type=type(e).__name__,
            )
            return 0

    # ==================== COMPREHENSIVE ANALYTICS TABLES ====================

    def generate_all_analytics_tables(
        self,
        scores_df: pd.DataFrame,
        cfg: Dict[str, Any],
        sensor_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """
        Generate essential analytics tables (v11 - SQL-only).
        
        Phase 3: Delegates to AnalyticsBuilder for core logic.
        
        Writes only the tables in ALLOWED_TABLES:
          - ACM_HealthTimeline: Health % over time (required for RUL forecasting)
          - ACM_RegimeTimeline: Operating regime assignments
          - ACM_SensorDefects: Sensor-level anomaly flags
          - ACM_SensorHotspots: Top anomalous sensors (RUL attribution)
          - ACM_DataQuality: Data quality per sensor
        """
        builder = AnalyticsBuilder(self)
        return builder.generate_all(scores_df, cfg, sensor_context)

    def _generate_health_timeline(self, scores_df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
        """Backward compat wrapper - delegates to AnalyticsBuilder."""
        builder = AnalyticsBuilder(self)
        return builder.generate_health_timeline(scores_df, cfg)
    
    def _generate_regime_timeline(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Backward compat wrapper - delegates to AnalyticsBuilder."""
        builder = AnalyticsBuilder(self)
        return builder.generate_regime_timeline(scores_df)
    
    def _generate_sensor_defects(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Backward compat wrapper - delegates to AnalyticsBuilder."""
        builder = AnalyticsBuilder(self)
        return builder.generate_sensor_defects(scores_df)
    
    def _generate_sensor_hotspots_table(
        self,
        sensor_zscores: pd.DataFrame,
        sensor_values: pd.DataFrame,
        train_mean: Optional[pd.Series],
        train_std: Optional[pd.Series],
        warn_z: float,
        alert_z: float,
        top_n: int
    ) -> pd.DataFrame:
        """Backward compat wrapper - delegates to AnalyticsBuilder."""
        builder = AnalyticsBuilder(self)
        return builder.generate_sensor_hotspots(
            sensor_zscores, sensor_values, train_mean, train_std,
            warn_z, alert_z, top_n
        )


# ============================================================================
# Artifact Write Helpers (moved from acm_main.py v11.2)
# ============================================================================

def write_pca_artifacts(
    output_manager: "OutputManager",
    pca_detector: Any,
    frame: pd.DataFrame,
    train: pd.DataFrame,
    run_id: Optional[str],
    equip_id: int,
    equip: str,
    spe_p95_train: float,
    t2_p95_train: float,
    cfg: Dict[str, Any],
) -> Tuple[int, int, int]:
    """Write PCA model, loadings, and metrics to SQL tables.
    
    This helper consolidates all PCA-related SQL writes:
    - ACM_PCAModel: Model metadata, thresholds, scaler config
    - ACM_PCALoadings: Component loadings per sensor
    - ACM_PCAMetrics: P95 SPE/T2 score stats, variance explained
    
    Args:
        output_manager: OutputManager instance for SQL writes
        pca_detector: PCA detector instance with pca and scaler attributes
        frame: Scored frame DataFrame with pca_spe and pca_t2 columns
        train: Training DataFrame with sensor columns
        run_id: Current run UUID
        equip_id: Equipment ID
        equip: Equipment name for logging
        spe_p95_train: P95 SPE threshold from training data
        t2_p95_train: P95 T2 threshold from training data
        cfg: Config dictionary with runtime settings
        
    Returns:
        Tuple of (rows_pca_model, rows_pca_load, rows_pca_metrics)
    """
    import json
    rows_pca_model = rows_pca_load = rows_pca_metrics = 0
    
    try:
        now_utc = pd.Timestamp.now()
        pca_model = getattr(pca_detector, "pca", None)

        # PCA Model row (TRAIN window used)
        var_ratio = getattr(pca_model, "explained_variance_ratio_", None)
        var_json = json.dumps(var_ratio.tolist()) if var_ratio is not None else "[]"

        # Capture actual scaler type from PCA detector
        scaler_name = pca_detector.scaler.__class__.__name__ if hasattr(pca_detector, 'scaler') else "StandardScaler"
        scaler_params = {}
        if hasattr(pca_detector, 'scaler'):
            scaler_params["with_mean"] = getattr(pca_detector.scaler, 'with_mean', True)
            scaler_params["with_std"] = getattr(pca_detector.scaler, 'with_std', True)
        else:
            scaler_params = {"with_mean": True, "with_std": True}
        
        scaling_spec = json.dumps({"scaler": scaler_name, **scaler_params})
        model_row = {
            "RunID": run_id or "",
            "EquipID": int(equip_id),
            "EntryDateTime": now_utc,
            "NComponents": int(getattr(pca_model, "n_components_", getattr(pca_model, "n_components", 0))),
            "TargetVar": json.dumps({"SPE_P95_train": spe_p95_train, "T2_P95_train": t2_p95_train}),
            "VarExplainedJSON": var_json,
            "ScalingSpecJSON": scaling_spec,
            "ModelVersion": cfg.get("runtime", {}).get("version", "v5.0.0"),
            "TrainStartEntryDateTime": train.index.min() if len(train.index) else None,
            "TrainEndEntryDateTime": train.index.max() if len(train.index) else None
        }
        rows_pca_model = output_manager.write_pca_model(model_row)

        # PCA Loadings
        comps = getattr(pca_model, "components_", None)
        if comps is not None and hasattr(train, "columns"):
            load_rows = []
            for k in range(comps.shape[0]):
                for j, sensor in enumerate(train.columns):
                    load_rows.append({
                        "RunID": run_id or "",
                        "EntryDateTime": now_utc,
                        "ComponentNo": int(k + 1),
                        "Sensor": str(sensor),
                        "Loading": float(comps[k, j])
                    })
            df_load = pd.DataFrame(load_rows)
            rows_pca_load = output_manager.write_pca_loadings(df_load, run_id or "")

        # PCA Metrics
        spe_p95 = float(np.nanpercentile(frame["pca_spe"].to_numpy(dtype=np.float32), 95)) if "pca_spe" in frame.columns else None
        t2_p95 = float(np.nanpercentile(frame["pca_t2"].to_numpy(dtype=np.float32), 95)) if "pca_t2" in frame.columns else None

        var90_n = None
        if var_ratio is not None:
            csum = np.cumsum(var_ratio)
            var90_n = int(np.searchsorted(csum, 0.90) + 1)
        components_json = []
        if var_ratio is not None:
            cum = np.cumsum(var_ratio)
            for i, ratio in enumerate(var_ratio):
                components_json.append({
                    "name": f"PC{i + 1}",
                    "type": "variance_ratio",
                    "value": float(ratio),
                    "cumulative": float(cum[i])
                })

        # Include score stats alongside component variance details
        if var90_n is not None:
            components_json.append({"name": "PCA", "type": "var90_n", "value": float(var90_n)})
        if spe_p95 is not None:
            components_json.append({"name": "PCA", "type": "spe_p95_score", "value": float(spe_p95)})
        if t2_p95 is not None:
            components_json.append({"name": "PCA", "type": "t2_p95_score", "value": float(t2_p95)})

        # Calculate total explained variance as Python float
        explained_var_val = None
        if var_ratio is not None and len(var_ratio) > 0:
            explained_var_val = float(np.sum(var_ratio))
            
        df_metrics = pd.DataFrame([{
            "RunID": run_id or "",
            "EquipID": int(equip_id),
            "NComponents": int(getattr(pca_model, "n_components_", getattr(pca_model, "n_components", 0))),
            "ExplainedVariance": explained_var_val,
            "ComponentsJson": json.dumps(components_json) if components_json else None,
            "MetricType": "pca_fit",
            "TrainSamples": int(len(train)) if train is not None else None,
            "TrainFeatures": int(train.shape[1]) if train is not None else None
        }])
        rows_pca_metrics = output_manager.write_pca_metrics(df=df_metrics, run_id=run_id or "")
    except Exception as e:
        Console.warn(f"PCA artifacts write skipped: {e}", component="SQL",
                     equip=equip, run_id=run_id, error=str(e)[:200])
    
    return rows_pca_model, rows_pca_load, rows_pca_metrics


def write_sql_artifacts(
    output_manager: "OutputManager",
    frame: pd.DataFrame,
    episodes: pd.DataFrame,
    train: pd.DataFrame,
    pca_detector: Optional[Any],
    sql_client: Optional[Any],
    run_id: Optional[str],
    equip_id: int,
    equip: str,
    cfg: Dict[str, Any],
    meta: Any,
    win_start: Optional[pd.Timestamp],
    win_end: Optional[pd.Timestamp],
    rows_read: int,
    spe_p95_train: float,
    t2_p95_train: float,
    anomaly_count: int,
    T: Any,
    culprit_writer_func: Optional[Callable] = None,
) -> int:
    """
    Write SQL-specific artifacts: DriftTS, AnomalyEvents, RegimeEpisodes, PCA, RunStats, Culprits.
    
    Args:
        output_manager: OutputManager instance for SQL writes
        frame: Scored DataFrame with detector columns
        episodes: Episodes DataFrame from fusion
        train: Training DataFrame with sensor columns
        pca_detector: PCA detector instance (or None)
        sql_client: SQLClient instance (or None)
        run_id: Current run UUID
        equip_id: Equipment ID
        equip: Equipment name for logging
        cfg: Config dictionary
        meta: DataMeta instance with kept_cols, cadence_ok, etc.
        win_start: Window start timestamp
        win_end: Window end timestamp
        rows_read: Number of rows read
        spe_p95_train: P95 SPE threshold from training
        t2_p95_train: P95 T2 threshold from training
        anomaly_count: Number of anomalies detected
        T: Timer/section manager for profiling
        culprit_writer_func: Optional function to write episode culprits
    
    Returns:
        Total rows written across all artifact tables.
    """
    rows_written = 0
    
    # DriftSeries [TODO v11.2.4: Implement drift time series writing]
    # with T.section("sql.drift_series"):
    #     try:
    #         df_drift = output_manager._build_drift_ts(frame, equip_id, run_id, cfg)
    #         if df_drift is not None:
    #             rows_written += output_manager.write_drift_series(df_drift)
    #     except Exception as e:
    #         Console.warn(f"DriftSeries write skipped: {e}", component="SQL",
    #                      equip=equip, run_id=run_id, error=str(e)[:200])

    # AnomalyEvents [TODO v11.2.4: Implement anomaly events writing]
    # with T.section("sql.events"):
    #     try:
    #         df_events = output_manager._build_anomaly_events(episodes, equip_id, run_id)
    #         if df_events is not None:
    #             rows_written += output_manager.write_anomaly_events(df_events, run_id or "")
    #     except Exception as e:
    #         Console.warn(f"AnomalyEvents write skipped: {e}", component="SQL",
    #                      equip=equip, run_id=run_id, error=str(e)[:200])

    # RegimeEpisodes [TODO v11.2.4: Implement regime episodes writing]
    # with T.section("sql.regimes"):
    #     try:
    #         df_reg = output_manager._build_regime_episodes(episodes, equip_id, run_id)
    #         if df_reg is not None:
    #             rows_written += output_manager.write_regime_episodes(df_reg, run_id or "")
    #     except Exception as e:
    #         Console.warn(f"RegimeEpisodes write skipped: {e}", component="SQL",
    #                      equip=equip, run_id=run_id, error=str(e)[:200])

    # PCA artifacts
    with T.section("sql.pca"):
        rows_pca_model, rows_pca_load, rows_pca_metrics = write_pca_artifacts(
            output_manager=output_manager,
            pca_detector=pca_detector,
            frame=frame,
            train=train,
            run_id=run_id,
            equip_id=equip_id,
            equip=equip,
            spe_p95_train=spe_p95_train,
            t2_p95_train=t2_p95_train,
            cfg=cfg,
        )
        rows_written += int(rows_pca_model + rows_pca_load + rows_pca_metrics)

    # RunStats
    with T.section("sql.run_stats"):
        try:
            if sql_client and run_id and win_start is not None and win_end is not None:
                drift_p95 = None
                if "drift_z" in frame.columns:
                    drift_p95 = float(np.nanpercentile(frame["drift_z"].to_numpy(dtype=np.float32), 95))
                sensors_kept = len(getattr(meta, "kept_cols", []))
                cadence_ok_pct = float(getattr(meta, "cadence_ok", 1.0)) * 100.0 if hasattr(meta, "cadence_ok") else None

                output_manager.write_run_stats({
                    "RunID": run_id,
                    "EquipID": int(equip_id),
                    "WindowStartEntryDateTime": win_start,
                    "WindowEndEntryDateTime": win_end,
                    "SamplesIn": rows_read,
                    "SamplesKept": rows_read,
                    "SensorsKept": sensors_kept,
                    "CadenceOKPct": cadence_ok_pct,
                    "DriftP95": drift_p95,
                    "ReconRMSE": None,
                    "AnomalyCount": anomaly_count
                })
        except Exception as e:
            Console.warn(f"RunStats not recorded: {e}", component="RUN",
                         equip=equip, run_id=run_id, error=str(e)[:200])

    # Episode culprits
    with T.section("sql.culprits"):
        try:
            if culprit_writer_func and sql_client and run_id and len(episodes) > 0:
                culprit_writer_func(
                    sql_client=sql_client,
                    run_id=run_id,
                    episodes=episodes,
                    scores_df=frame,
                    equip_id=equip_id
                )
        except Exception as e:
            Console.warn(f"Failed to write ACM_EpisodeCulprits: {e}", component="CULPRITS",
                         equip=equip, run_id=run_id, error=str(e))
    
    return rows_written

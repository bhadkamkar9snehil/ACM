# core/acm_main.py
from __future__ import annotations

# =============================================================================
# ACM Main Pipeline
# =============================================================================
# Changelog
# - 2026-01-17: Refreshed and clarified inline comments and added an overview
#   of the pipeline structure for easier navigation and maintenance.
#
# Overview
# - Entrypoint: `main()` orchestrates the full SQL-only pipeline for one run.
# - Stages: SQL connect → config load → data load → features → models → scoring
#   → regimes → calibration → fusion → drift → persistence → analytics → forecast.
# - Output: Writes run artifacts and metrics to SQL via `OutputManager` and
#   emits observability signals when available.
# - Modes: OFFLINE (full discovery) and ONLINE (scoring only) are enforced
#   through `PipelineMode` and model cache validation.
# =============================================================================

# ============================
# Standard library imports
# ============================
import argparse
import gc
import hashlib
import json
import os
import sys
import threading
import time
import uuid
import warnings
from datetime import datetime
from pathlib import Path
# NOTE: Parallel fitting via ThreadPoolExecutor was removed due to BLAS/OpenMP
# deadlocks; model fitting is intentionally single-threaded here.
from typing import Any, Callable, Dict, List, Tuple, Optional, Sequence

# NOTE: Overflow warnings are not suppressed globally. If they appear, treat
# them as a signal of scaling/unit issues and handle them locally where safe.

# ============================
# Third-party imports
# ============================
import joblib
import numpy as np
import pandas as pd

# --- import guard to support module and script execution modes
try:
    # import ONLY core modules relatively
    from . import regimes, drift, fuse
    from . import correlation, outliers
    from .ar1_detector import AR1Detector  # Split out of forecasting for clarity
    from . import fast_features
    from .forecast_engine import ForecastEngine  # Unified forecasting orchestrator
except ImportError:
    import pathlib
    sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
    from core import regimes, drift, fuse
    from core import correlation, outliers
    from core.ar1_detector import AR1Detector
    from core.forecast_engine import ForecastEngine  # Unified forecasting orchestrator
    from core import fast_features

from core.omr import OMRDetector  # Overall Model Residual detector
from core.config_history_writer import log_auto_tune_changes
from core.output_manager import OutputManager, write_sql_artifacts
from core.run_metadata_writer import write_run_metadata, extract_run_metadata_from_scores, extract_data_quality_score
from core.episode_culprits_writer import write_episode_culprits_enhanced
from core.pipeline_types import DataContract, ValidationResult, PipelineMode
from core.seasonality import SeasonalPattern  # detect_and_adjust imported inline
from core.sensor_attribution import build_contribution_timeline
from core.adaptive_thresholds import calculate_and_persist_thresholds
from core.smart_coldstart import seed_baseline
from core.detector_orchestrator import (
    score_all_detectors,
    calibrate_all_detectors,
    fit_all_detectors,
    get_detector_enable_flags,
    rebuild_detectors_from_cache,
    compute_stable_feature_hash,
    reconcile_detector_flags_with_loaded_models,
)
from core.model_persistence import (
    load_cached_models_with_validation,
    save_trained_models,
)
from core.model_evaluation import auto_tune_parameters

# Observability: OpenTelemetry + structured logging. Falls back to no-op stubs
# when observability dependencies are unavailable.
try:
    from core.observability import (
        init as init_observability,
        shutdown as shutdown_observability,
        log as obs_log,
        get_tracer, 
        get_meter,
        set_context as set_acm_context,
        traced,
        Span,
        Console,
        OTEL_AVAILABLE,
        record_batch,
        record_batch_processed,
        record_health,
        record_health_score,
        record_rul,
        record_active_defects,
        record_episode,
        record_error,
        record_coldstart,
        record_run,
        record_sql_op,
        record_detector_scores,
        record_regime,
        record_data_quality,
        record_model_refit,
        log_timer,
        start_profiling,
        stop_profiling,
    )
    _OBSERVABILITY_AVAILABLE = True
except ImportError:
    _OBSERVABILITY_AVAILABLE = False
    OTEL_AVAILABLE = False
    obs_log = None
    def init_observability(*args, **kwargs): pass
    def get_tracer(): return None
    def get_meter(): return None
    def set_acm_context(*args, **kwargs): pass
    def traced(name: str, track_resources: bool = True):
        def decorator(func: Callable) -> Callable:
            return func
        return decorator
    class _FallbackSpan:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def set_attribute(self, *a): pass
    class _FallbackConsole:
        @staticmethod
        def info(msg, **k): print(msg)
        @staticmethod
        def warn(msg, **k): print(msg)
        @staticmethod
        def error(msg, **k): print(msg)
    Span = _FallbackSpan
    Console = _FallbackConsole
    def record_batch(*args, **kwargs): pass
    def record_batch_processed(*args, **kwargs): pass
    def record_health(*args, **kwargs): pass
    def record_health_score(*args, **kwargs): pass
    def record_rul(*args, **kwargs): pass
    def record_active_defects(*args, **kwargs): pass
    def record_episode(*args, **kwargs): pass
    def record_error(*args, **kwargs): pass
    def record_coldstart(*args, **kwargs): pass
    def record_run(*args, **kwargs): pass
    def record_sql_op(*args, **kwargs): pass
    def record_detector_scores(*args, **kwargs): pass
    def record_regime(*args, **kwargs): pass
    def record_data_quality(*args, **kwargs): pass
    def record_model_refit(*args, **kwargs): pass
    def log_timer(*args, **kwargs): pass
    def start_profiling(): pass
    def stop_profiling(): pass
    def shutdown_observability(): pass

# SQL client: required at runtime (SQL-only pipeline). Guarded import keeps
# module importable in environments without SQL drivers.
try:
    from core.sql_client import SQLClient, execute_with_deadlock_retry  # type: ignore
except Exception:
    SQLClient = None  # type: ignore
    execute_with_deadlock_retry = None  # type: ignore

# Data utilities: index hygiene and deduplication helpers.
from core.fast_features import ensure_local_index, deduplicate_index

# Config utilities: signature and loader helpers.
from utils.config_dict import ConfigDict, compute_config_signature, load_config as load_config_from_source

# Timer helper with a safe fallback for environments without `utils.timer`.
try:
    from utils.timer import Timer  # type: ignore
except Exception:
    class Timer:
        def __init__(self, enable: bool = True): pass
        def section(self, *_a, **_k):
            class _C:
                def __enter__(self): return self
                def __exit__(self, *x): return False
            return _C()
        def log(self, *a, **k): pass

# Version constant for logging and run metadata.
try:
    from utils.version import __version__ as ACM_VERSION
except ImportError:
    ACM_VERSION = "unknown"


# Console from observability (backwards compatible). Do not reimport here to
# preserve the fallback mechanism when observability is unavailable.

# Model lifecycle management (maturity, promotion, and active model tracking).
from core.model_lifecycle import (
    MaturityState,
    ModelState,
    PromotionCriteria,
    check_promotion_eligibility,
    promote_model,
    create_new_model_state,
    update_model_state_from_run,
    get_active_model_dict,
    load_model_state_from_sql,
)

# =============================================================================
# Pipeline Context Classes
# Structured data carriers between pipeline phases
# =============================================================================
from dataclasses import dataclass, field
from enum import Enum


class RunOutcome(Enum):
    """Outcome states for ACM pipeline runs.
    
    OK: All phases completed successfully.
    DEGRADED: Non-critical phases failed, but core outputs were produced.
    NOOP: No data to process (insufficient rows or empty window).
    FAIL: Critical failure; run cannot be completed.
    """
    OK = "OK"
    DEGRADED = "DEGRADED"
    NOOP = "NOOP"
    FAIL = "FAIL"


@dataclass
class RuntimeContext:
    """Context from initialization phase - passed to all subsequent phases."""
    equip: str
    equip_id: int
    run_id: Optional[str]
    sql_client: Optional[Any]
    output_manager: Any  # OutputManager
    cfg: Dict[str, Any]
    args: argparse.Namespace
    CONTINUOUS_LEARNING: bool
    config_signature: str
    run_start_time: datetime
    pipeline_mode: PipelineMode = PipelineMode.OFFLINE  # Online/offline pipeline mode.
    tracer: Optional[Any] = None
    root_span: Optional[Any] = None
    
    @property
    def allows_model_refit(self) -> bool:
        """Return True when the current mode allows model fitting/retraining."""
        return self.pipeline_mode == PipelineMode.OFFLINE
    
    @property
    def allows_regime_discovery(self) -> bool:
        """Return True when the current mode allows new regime discovery."""
        return self.pipeline_mode == PipelineMode.OFFLINE


@dataclass
class FeatureContext:
    """Context from feature construction phase."""
    train: pd.DataFrame
    score: pd.DataFrame
    train_feature_hash: Optional[str] = None
    current_train_columns: Optional[List[str]] = None


@dataclass
class ModelContext:
    """Context from model training/loading phase."""
    ar1_detector: Optional[Any] = None
    pca_detector: Optional[Any] = None
    iforest_detector: Optional[Any] = None
    gmm_detector: Optional[Any] = None
    omr_detector: Optional[Any] = None
    regime_model: Optional[Any] = None
    models_fitted: bool = False
    refit_requested: bool = False
    detector_cache: Optional[Dict[str, Any]] = None
    # Cached PCA train scores to eliminate double computation in calibration
    pca_train_spe: Optional[np.ndarray] = None
    pca_train_t2: Optional[np.ndarray] = None


@dataclass
class ScoreContext:
    """Context from scoring phase."""
    frame: pd.DataFrame  # Contains all z-scores
    train_frame: pd.DataFrame
    calibrators: Dict[str, Any] = field(default_factory=dict)


@dataclass  
class FusionContext:
    """Context from fusion phase."""
    frame: pd.DataFrame  # With fused scores, health, episodes
    episodes: pd.DataFrame
    fusion_weights: Dict[str, float] = field(default_factory=dict)
    health_stats: Dict[str, Any] = field(default_factory=dict)


def _configure_logging(logging_cfg, args):
    """Apply CLI/config logging overrides and return effective flags."""
    enable_sql_logging_cfg = (logging_cfg or {}).get("enable_sql_sink")
    if enable_sql_logging_cfg is False:
        Console.warn("SQL sink disable flag in config is ignored; SQL logging is always enabled in SQL mode.", component="LOG",
                     config_flag=enable_sql_logging_cfg)
    enable_sql_logging = True

    # ACMLog does not support dynamic level/format yet; keep placeholders for future work.

    log_file = args.log_file or (logging_cfg or {}).get("file")
    if log_file:
        Console.warn(f"File logging disabled in SQL-only mode (ignoring --log-file={log_file})", component="CONFIG",
                     log_file=str(log_file))

    # Module-specific levels are not supported yet.
    return {"enable_sql_logging": enable_sql_logging}


def _get_equipment_id(equipment_name: str, sql_client: Any) -> int:
    """
    Get equipment ID from database. Equipment MUST exist in Equipment table.
    
    Args:
        equipment_name: Equipment code (e.g., "FD_FAN", "GAS_TURBINE")
        sql_client: Active SQL connection
    
    Returns:
        Equipment ID (always > 0)
    
    Raises:
        RuntimeError: If equipment not found in database
    """
    if not equipment_name:
        raise RuntimeError("Equipment name is required")
    
    if sql_client is None:
        raise RuntimeError("SQL client is required to look up equipment ID")
    
    # Look up equipment ID from database
    if hasattr(sql_client, 'get_equipment_id'):
        equip_id = sql_client.get_equipment_id(equipment_name)
    else:
        cursor = sql_client.cursor()
        cursor.execute("SELECT EquipID FROM Equipment WHERE EquipCode = ?", (equipment_name,))
        row = cursor.fetchone()
        equip_id = row[0] if row else None
    
    if not equip_id or equip_id == 0:
        raise RuntimeError(
            f"Equipment '{equipment_name}' not found in database.\n"
            f"Add it to the Equipment table first:\n"
            f"  INSERT INTO Equipment (EquipCode, EquipName) VALUES ('{equipment_name}', '{equipment_name}')"
        )
    
    return equip_id


def _load_config(sql_client: Any, equipment_name: str) -> ConfigDict:
    """
    Load config from SQL database (ACM_Config table).
    
    SQL-only mode: No CSV fallback. Config must be present in ACM_Config.
    Loads global defaults (EquipID=0) and applies equipment-specific overrides.
    
    Args:
        sql_client: Active SQL connection (already validated)
        equipment_name: Name of equipment (e.g., "FD_FAN", "GAS_TURBINE")
    
    Returns:
        ConfigDict with equipment-specific configuration
    
    Raises:
        RuntimeError: If equipment config not found in SQL
    """
    # Equipment name is required
    if not equipment_name:
        raise RuntimeError("Equipment name is required to load config")
    
    equip_id = _get_equipment_id(equipment_name, sql_client)
    
    try:
        cursor = sql_client.cursor()
        
        # Cascading load: global defaults (EquipID=0) then equipment overrides.
        # Equipment-specific values override matching ParamPath entries.
        cursor.execute("""
            SELECT ParamPath, ParamValue, ValueType
            FROM ACM_Config
            WHERE EquipID IN (0, ?)
            ORDER BY EquipID ASC, ParamPath ASC
        """, (equip_id,))
        
        rows = cursor.fetchall()
        if not rows:
            raise RuntimeError(
                f"No config found in ACM_Config for equipment '{equipment_name}' (EquipID={equip_id}).\n"
                f"Populate ACM_Config with global (EquipID=0) and/or equipment-specific settings before running ACM."
            )
        
        # Build a nested config dict. Later rows override earlier rows.
        cfg_dict: Dict[str, Any] = {}
        for param_path, param_value, value_type in rows:
            # Parse value based on type
            if value_type == 'int':
                value = int(param_value)
            elif value_type == 'float':
                value = float(param_value)
            elif value_type == 'bool':
                value = param_value.lower() in ('true', '1', 'yes')
            elif value_type in ('list', 'json'):
                import json
                value = json.loads(param_value)
            else:
                value = param_value
            
            # Handle dotted paths (e.g., "models.pca.n_components" -> nested dict).
            parts = param_path.split('.')
            d = cfg_dict
            for part in parts[:-1]:
                if part not in d:
                    d[part] = {}
                d = d[part]
            d[parts[-1]] = value
        
        Console.info(f"Config loaded from SQL for {equipment_name} (EquipID={equip_id}, {len(rows)} params)", component="CONFIG")
        return ConfigDict(cfg_dict, mode="sql", equip_id=equip_id)
        
    except Exception as e:
        Console.error(f"Failed to load config from SQL: {e}", component="CONFIG",
                      equipment=equipment_name, equip_id=equip_id, error=str(e))
        raise RuntimeError(f"Config loading failed: {e}. Ensure ACM_Config table is populated for EquipID={equip_id}.")


# Backwards-compat breadcrumbs for helpers extracted from this module.
# _compute_config_signature -> utils/config_dict.py::compute_config_signature()
# _ensure_local_index -> core/fast_features.py::ensure_local_index()


# =======================
# SQL helpers (local)
# Kept here for tight integration with run orchestration.
# =======================
def _continuous_learning_enabled(cfg: Dict[str, Any]) -> bool:
    """Return True if continuous learning is enabled in config."""
    return cfg.get("continuous_learning", {}).get("enabled", False)

def _sql_connect(cfg: Dict[str, Any]) -> Optional[Any]:
    if not SQLClient:
        raise RuntimeError("SQLClient not available. Ensure core/sql_client.py exists and pyodbc is installed.")
    # Prefer INI-based connection (Windows authentication if configured).
    try:
        cli = SQLClient.from_ini('acm')
        cli.connect()
        return cli
    except Exception as ini_err:
        # Fallback to config dict (legacy behavior).
        Console.warn(f"Failed to connect via INI, trying config dict: {ini_err}", component="SQL",
                     error_type=type(ini_err).__name__, error=str(ini_err)[:200])
        sql_cfg = cfg.get("sql", {}) or {}
        cli = SQLClient(sql_cfg)
        cli.connect()
        return cli

def _sql_start_run(cli: Any, cfg: Dict[str, Any], equip_code: str) -> Tuple[str, pd.Timestamp, pd.Timestamp, int]:
    """
    Start a run by inserting into ACM_Runs and returning the window bounds.
    Delegates to sql_client.start_run().
    """
    tick_minutes = cfg.get("runtime", {}).get("tick_minutes", 30)
    
    run_id, window_start, window_end, equip_id = cli.start_run(
        cfg=cfg,
        equip_code=equip_code,
        deadlock_retry_func=execute_with_deadlock_retry
    )
    
    Console.info(
        f"Run started: {equip_code} (ID={equip_id}) | RunID={run_id[:8]} | window=[{window_start},{window_end}) | tick={tick_minutes}m",
        component="RUN",
    )
    return run_id, window_start, window_end, equip_id


def _build_features(
    train: pd.DataFrame,
    score: pd.DataFrame,
    cfg: Dict[str, Any],
    equip: str = "",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build engineered features from raw sensor data.

    Transforms raw sensor time series into statistical features using
    fast_features.compute_basic_features(). Handles:
    - Fill value computation from TRAIN only (prevents data leakage)
    - Polars/pandas conversion (handled internally by fast_features)
    - Index preservation
    - Numeric type enforcement

    Args:
        train: Training/baseline DataFrame (raw sensors)
        score: Scoring/batch DataFrame (raw sensors)
        cfg: Config dict with features.window setting
        equip: Equipment name for logging

    Returns:
        Tuple of (train_features, score_features) DataFrames
    """
    if fast_features is None:
        Console.warn("fast_features not available; returning raw inputs", component="FEAT", equip=equip)
        return train, score

    if not cfg.get("runtime", {}).get("phases", {}).get("features", True):
        Console.info("Feature building disabled in config", component="FEAT", equip=equip)
        return train, score

    feat_win = int((cfg.get("features", {}) or {}).get("window", 3))
    Console.info(f"Building features with window={feat_win}", component="FEAT", equip=equip)

    # Preserve indices
    idx_train = train.index
    idx_score = score.index

    # Compute fill values from TRAIN only (prevents data leakage to SCORE)
    train_fill_values = train.select_dtypes(include=[np.number]).median().to_dict()
    Console.info(f"Computed {len(train_fill_values)} fill values from training data", component="FEAT")

    # Build features - fast_features handles Polars/pandas internally
    train_feat = fast_features.compute_basic_features(train, window=feat_win)
    score_feat = fast_features.compute_basic_features(score, window=feat_win, fill_values=train_fill_values)

    # Normalize to pandas, restore indices, enforce numeric
    if not isinstance(train_feat, pd.DataFrame):
        train_feat = train_feat.to_pandas() if hasattr(train_feat, "to_pandas") else pd.DataFrame(train_feat)
    if not isinstance(score_feat, pd.DataFrame):
        score_feat = score_feat.to_pandas() if hasattr(score_feat, "to_pandas") else pd.DataFrame(score_feat)

    train_feat.index = idx_train
    score_feat.index = idx_score
    train_feat = train_feat.apply(pd.to_numeric, errors="coerce")
    score_feat = score_feat.apply(pd.to_numeric, errors="coerce")

    Console.info(f"Features built: train={train_feat.shape}, score={score_feat.shape}", component="FEAT")
    return train_feat, score_feat


# ========================================================================
# Extracted helpers (now owned by dedicated modules)
# ========================================================================
# _sql_finalize_run -> sql_client.py::SQLClient.finalize_run()
# _execute_with_deadlock_retry -> sql_client.py::execute_with_deadlock_retry()
# _deduplicate_index -> fast_features.py::deduplicate_index()
# _ensure_local_index -> fast_features.py::ensure_local_index()
# _compute_config_signature -> config_dict.py::compute_config_signature()
# _score_all_detectors -> detector_orchestrator.py
# _calibrate_all_detectors -> detector_orchestrator.py
# _fit_all_detectors -> detector_orchestrator.py
# _get_detector_enable_flags -> detector_orchestrator.py

# NOTE: safe_step() was removed. Critical phases now fail naturally without
# try/except wrappers. See docs/GhostBusters_1.md for rationale.

"""
-------------------------------------------------------------------------------------------
"""

def main() -> None:
    ap = argparse.ArgumentParser(
        prog="python -m core.acm_main",
        description="ACM - Automated Condition Monitoring pipeline for equipment health analysis.",
        epilog="""
Examples:
  python -m core.acm_main --equip FD_FAN --start-time "2023-10-15T00:00:00" --end-time "2023-11-15T00:00:00"
  python -m core.acm_main --equip GAS_TURBINE --log-level DEBUG

Note: For automated batch processing, use sql_batch_runner.py instead:
  python scripts/sql_batch_runner.py --equip FD_FAN --start-from-beginning
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--equip", required=True, help="Equipment name (e.g., FD_FAN, GAS_TURBINE)")
    ap.add_argument("--mode", choices=["online", "offline"], default="offline",
                    help="Pipeline mode: online (scoring only, requires model), offline (full discovery)")
    ap.add_argument("--clear-cache", action="store_true", help="Force re-training by deleting the cached model for this equipment.")
    ap.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Override global log level.")
    ap.add_argument("--log-format", choices=["text", "json"], help="Override log output format.")
    ap.add_argument("--log-file", help="Write logs to the specified file.")
    ap.add_argument("--log-module-level", action="append", default=[], metavar="MODULE=LEVEL",
                    help="Set per-module log level overrides (repeatable).")
    ap.add_argument("--start-time", help="Start time for analysis window (ISO format: 2023-10-15T00:00:00)")
    ap.add_argument("--end-time", help="End time for analysis window (ISO format: 2023-11-15T00:00:00)")
    args = ap.parse_args()

    equip = args.equip
    
    # ========================================================================
    # Observability bootstrap: initialize logging before SQL so connection
    # failures are captured. Use equip_id=0 until SQL is available.
    # ========================================================================
    
    if _OBSERVABILITY_AVAILABLE:
        try:
            init_observability(
                equipment=equip,
                equip_id=0,  # Will be updated after SQL connects
                service_name="acm-pipeline",
                otlp_endpoint="http://localhost:4318",
                loki_endpoint="http://localhost:3100",
                enable_tracing=True,
                enable_metrics=True,
                enable_loki=True,
                enable_profiling=True,
            )
            start_profiling()
        except Exception as e:
            Console.warn(f"Observability init failed (non-fatal): {e}", component="OTEL",
                         error_type=type(e).__name__, error=str(e)[:200])

    T = Timer(enable=True)
    
    # Enable OTEL metrics for Timer and ResourceMonitor (optional integration).
    try:
        from utils.timer import enable_timer_metrics, set_timer_equipment
        from core.resource_monitor import enable_resource_metrics, set_resource_equipment
        enable_timer_metrics(equip)
        enable_resource_metrics(equip)
    except ImportError:
        pass  # Optional integration

    # ========================================================================
    # Fail-fast SQL connect: ACM is SQL-only and must abort if SQL is down.
    # ========================================================================
    Console.info("Connecting to SQL Server...", component="SQL")
    try:
        if not SQLClient:
            raise RuntimeError("SQLClient not available. Ensure core/sql_client.py exists and pyodbc is installed.")
        sql_client = SQLClient.from_ini('acm')
        sql_client.connect()
        # Quick health check.
        _cur = sql_client.cursor()
        _cur.execute("SELECT 1")
        _cur.fetchone()
        Console.ok("SQL connection established", component="SQL")
    except Exception as e:
        Console.error(f"SQL connection failed: {e}", component="SQL",
                      error_type=type(e).__name__, error=str(e)[:500])
        Console.error("Check configs/sql_connection.ini and ensure SQL Server is running.", component="SQL")
        raise SystemExit(1)

    with T.section("startup"):
        # Load config from SQL (no CSV fallback; SQL is the source of truth).
        cfg = _load_config(sql_client, equipment_name=equip)
        
        # Deep copy config to prevent accidental mutation across phases.
        import copy
        cfg = copy.deepcopy(cfg)
        
        logging_cfg = (cfg.get("logging") or {})
    logging_settings = _configure_logging(logging_cfg, args)
    enable_sql_logging = logging_settings.get("enable_sql_logging", True)
    
    # Get equipment ID from SQL (already resolved during config loading)
    equip_id = _get_equipment_id(equip, sql_client)
    if not hasattr(cfg, '_equip_id') or cfg._equip_id == 0:
        cfg._equip_id = equip_id
    
    # Compute and store config signature for cache validation.
    config_signature = compute_config_signature(cfg)
    cfg["_signature"] = config_signature

    # Pipeline mode from CLI (online=scoring only, offline=full discovery).
    pipeline_mode_str = getattr(args, "mode", "offline")
    PIPELINE_MODE = PipelineMode.ONLINE if pipeline_mode_str == "online" else PipelineMode.OFFLINE
    ALLOWS_MODEL_REFIT = PIPELINE_MODE == PipelineMode.OFFLINE
    ALLOWS_REGIME_DISCOVERY = PIPELINE_MODE == PipelineMode.OFFLINE
    
    # Continuous learning is controlled exclusively by config.
    CONTINUOUS_LEARNING = _continuous_learning_enabled(cfg)
    
    # Continuous learning settings.
    cl_cfg = cfg.get("continuous_learning", {})
    model_update_interval = int(cl_cfg.get("model_update_interval", 1))  # Default: update every batch
    threshold_update_interval = int(cl_cfg.get("threshold_update_interval", 1))  # Default: update every batch
    force_retraining = CONTINUOUS_LEARNING  # Force retraining when continuous learning enabled
    
    # Validate interval settings to avoid zero/negative values in production.
    invalid_intervals = []
    if model_update_interval <= 0:
        invalid_intervals.append(f"model_update_interval={model_update_interval}")
        model_update_interval = 1
    if threshold_update_interval <= 0:
        invalid_intervals.append(f"threshold_update_interval={threshold_update_interval}")
        threshold_update_interval = 1
    if invalid_intervals:
        Console.warn(f"Invalid intervals defaulted to 1: {', '.join(invalid_intervals)}", component="CONFIG")
    
    # Set observability context (equipment metadata only).
    set_acm_context(
        equipment=equip,
        equip_id=equip_id
    )
    
    # Get run count from SQL for interval calculations (completed runs only).
    run_count = 0
    try:
        cur = sql_client.get_cursor()
        cur.execute("SELECT COUNT(*) FROM ACM_Runs WHERE EquipID = ?", (equip_id,))
        row = cur.fetchone()
        run_count = row[0] if row else 0
    except Exception:
        run_count = 0  # First run or error - will trigger threshold calc
    
    # Store run count in config for downstream access.
    if "runtime" not in cfg:
        cfg["runtime"] = {}
    cfg["runtime"]["run_count"] = run_count

    # Consolidated startup log.
    pipeline_info = f"mode={pipeline_mode_str.upper()} | refit={ALLOWS_MODEL_REFIT} | discovery={ALLOWS_REGIME_DISCOVERY}"
    intervals_info = f" | intervals=model:{model_update_interval},thresh:{threshold_update_interval}" if CONTINUOUS_LEARNING else ""
    Console.info(f"Run #{run_count + 1} | {equip} | {pipeline_info}{intervals_info}", component="RUN")

    # Initialize cross-phase state variables.
    detector_cache: Optional[Dict[str, Any]] = None
    train_feature_hash: Optional[str] = None
    current_train_columns: Optional[List[str]] = None
    regime_model: Optional[regimes.RegimeModel] = None
    regime_basis_train: Optional[pd.DataFrame] = None
    regime_basis_score: Optional[pd.DataFrame] = None
    regime_basis_meta: Dict[str, Any] = {}
    regime_basis_hash: Optional[int] = None
    raw_train: Optional[pd.DataFrame] = None
    raw_score: Optional[pd.DataFrame] = None
    cache_payload: Optional[Dict[str, Any]] = None
    regime_quality_ok: bool = True
    refit_requested: bool = False
    sql_log_sink: Optional[Any] = None  # SQL log sink for cleanup in finally block

    # Heuristic ETAs (configurable).
    eta_load = float((cfg.get("hints") or {}).get("eta_load_sec", 30))
    eta_fit  = float((cfg.get("hints") or {}).get("eta_fit_sec", 8))
    eta_score = float((cfg.get("hints") or {}).get("eta_score_sec", 6))

    # ===== SQL: Start run (window discovery) =====
    # SQL client is already connected at this point.
    run_id: Optional[str] = None
    win_start: Optional[pd.Timestamp] = None
    win_end: Optional[pd.Timestamp] = None
    
    # Track CLI overrides for consolidated logging.
    cli_overrides = []

    # Start the run in SQL.
    run_id, win_start, win_end, equip_id = _sql_start_run(sql_client, cfg, equip)
    
    # Fail-fast: ensure EquipID is valid immediately after SQL lookup.
    if equip_id <= 0:
        raise RuntimeError(
            f"EquipID is required and must be a positive integer. "
            f"Current value: {equip_id}. Equipment '{equip}' not found in Equipment table."
        )
    
    # Update observability context with run_id for trace/metric/log tagging.
    set_acm_context(run_id=run_id, equip_id=equip_id)
    
    # Override window if CLI args provided (e.g., backfill).
    if args.start_time:
        try:
            win_start = pd.Timestamp(args.start_time)
            cli_overrides.append(f"start={win_start}")
        except Exception as e:
            Console.warn(f"Failed to parse --start-time: {e}", component="RUN")
    
    if args.end_time:
        try:
            win_end = pd.Timestamp(args.end_time)
            cli_overrides.append(f"end={win_end}")
        except Exception as e:
            Console.warn(f"Failed to parse --end-time: {e}", component="RUN")
    
    if cli_overrides:
        Console.info(f"CLI overrides: {', '.join(cli_overrides)}", component="RUN")

    # Create OutputManager early; it is used by data loading and all outputs.
    output_manager = OutputManager(
        sql_client=sql_client,
        run_id=run_id,
        equip_id=equip_id
    )
    output_manager.equipment = equip  # Set equipment name for logging

    # ---------- Finalization state ----------
    outcome = "OK"
    err_json: Optional[str] = None
    rows_read = 0
    rows_written = 0
    errors = []
    degradations: List[str] = []  # Track partial failures for DEGRADED outcome.
    
    # Track run timing for ACM_Runs metadata.
    from datetime import datetime
    run_start_time = datetime.now()

    # Initialize tracing span for the run (equipment name in span for Tempo).
    tracer = get_tracer() if _OBSERVABILITY_AVAILABLE else None
    _span_ctx = None
    root_span = None
    
    # v11.1.6: Removed custom TRACEPARENT env propagation. Correlation is now
    # done via acm.run_id/acm.run_count/acm.equipment attributes in Tempo/Loki.
    
    if tracer and hasattr(tracer, 'start_as_current_span'):
        span_name = f"acm.run:{equip}" if equip else "acm.run"
        _span_ctx = tracer.start_as_current_span(
            span_name,
            attributes={
                "acm.phase": "startup",
                "acm.equipment": equip,
                "acm.equip_id": equip_id,
                "acm.run_id": run_id,
                "acm.run_count": run_count,
            }
        )
        root_span = _span_ctx.__enter__()

    # Initialize variables at function scope to avoid NameError in conditional paths.
    train_start: Optional[datetime] = None
    train_end: Optional[datetime] = None
    model_state = None  # Single source of truth for model lifecycle state.
    
    # Initialize detector-related variables at function scope to avoid fragile
    # 'in dir()' checks throughout the pipeline.
    train: Optional[pd.DataFrame] = None
    col_meds: Optional[pd.Series] = None
    # NOTE: regime_model is declared earlier; avoid redefinition here.

    try:
        # ===== Phase 1: Load data from SQL =====
        with T.section("load_data"):
            from core.smart_coldstart import SmartColdstart
            
            coldstart_manager = SmartColdstart(
                sql_client=sql_client,
                equip_id=equip_id,
                equip_name=equip,
                stage='score'
            )
            
            # Historical replay: expand windows forward when start_time is explicit.
            historical_replay = bool(args.start_time)
            
            train, score, meta, coldstart_complete = coldstart_manager.load_with_retry(
                output_manager=output_manager,
                cfg=cfg,
                initial_start=win_start,
                initial_end=win_end,
                max_attempts=3,
                historical_replay=historical_replay
            )
            
            if not coldstart_complete:
                Console.info("Coldstart deferred - insufficient data, will retry next run", component="COLDSTART")
                if sql_client and run_id:
                    sql_client.finalize_run(run_id=run_id, outcome="NOOP", 
                                    rows_read=0, rows_written=0, err_json=None)
                return
            
            record_coldstart(equip)
            train = ensure_local_index(train)
            score = ensure_local_index(score)
            
            # Deduplicate indices early to prevent O(n^2) hotspots and silent data loss.
            train, train_dups = deduplicate_index(train, "TRAIN", equip)
            score, score_dups = deduplicate_index(score, "SCORE", equip)
            meta.dup_timestamps_removed = int(train_dups + score_dups)

            # DataContract validation at pipeline entry.
            with T.section("data.contract"):
                is_initial_coldstart = len(train) > 0
                min_rows_threshold = 10 if is_initial_coldstart else 100
                contract = DataContract(
                    required_sensors=[],
                    optional_sensors=list(meta.kept_cols) if hasattr(meta, 'kept_cols') else [],
                    timestamp_col=meta.timestamp_col if hasattr(meta, 'timestamp_col') else 'Timestamp',
                    min_rows=min_rows_threshold,
                    max_null_fraction=0.5,
                    equip_id=equip_id,
                    equip_code=equip,
                )
                validation = contract.validate(score)
                
                # Write validation result to SQL (success or failure).
                if output_manager:
                    try:
                        sig = contract.signature() if hasattr(contract, 'signature') and callable(contract.signature) else None
                        output_manager.write_data_contract_validation({
                            'Passed': validation.passed,
                            'RowsValidated': len(score),
                            'ColumnsValidated': len(score.columns),
                            'IssuesJSON': json.dumps(validation.issues) if validation.issues else None,
                            'WarningsJSON': json.dumps(validation.warnings) if validation.warnings else None,
                            'ContractSignature': sig,
                        })
                    except Exception as e:
                        if validation.passed:
                            Console.warn(f"Failed to write DataContract validation: {e}", component="DATA")
                
                if not validation.passed:
                    error_msg = f"DataContract validation FAILED: {validation.issues}"
                    Console.error(error_msg, component="DATA", equip=equip, run_id=run_id, issues=validation.issues)
                    raise ValueError(error_msg)
                    
                if validation.warnings:
                    Console.warn(f"DataContract: {len(validation.warnings)} warnings | {validation.warnings[0] if validation.warnings else ''}", component="DATA")

            if len(score) == 0:
                Console.warn("SCORE window empty after cleaning; marking run as NOOP", component="DATA",
                             equip=equip, run_id=run_id)
                outcome = "NOOP"
                rows_read = 0
                rows_written = 0
                if sql_client and run_id:
                    sql_client.finalize_run(
                        run_id=run_id,
                        outcome=outcome,
                        rows_read=rows_read,
                        rows_written=rows_written,
                        err_json=None
                    )
                return
        
        Console.info(
            f"[DATA] timestamp={meta.timestamp_col} cadence_ok={meta.cadence_ok} "
            f"kept={len(meta.kept_cols)} drop={len(meta.dropped_cols)} "
            f"tz_stripped={getattr(meta, 'tz_stripped', 0)} "
            f"future_drop={getattr(meta, 'future_rows_dropped', 0)} "
            f"dup_removed={getattr(meta, 'dup_timestamps_removed', 0)}"
        )
        T.log("data_split_complete", train_rows=train.shape[0], train_cols=train.shape[1], score_rows=score.shape[0], score_cols=score.shape[1])
        
        # Debug checkpoint: confirms data load completed before baseline seeding.
        Console.status("CHECKPOINT 1: Data loading complete, about to start baseline seeding")
        import sys
        sys.stdout.flush()

        # ===== Adaptive rolling baseline (cold-start helper) =====
        with T.section("baseline.seed"):
            Console.status(f"CHECKPOINT 2: Entering baseline.seed section for {equip}...")
            sys.stdout.flush()
            try:
                Console.status(f"CHECKPOINT 3: About to call seed_baseline() function")
                sys.stdout.flush()
                train, score, baseline_source = seed_baseline(
                    train.copy(), 
                    score.copy(), 
                    sql_client,
                    equip_id,
                    cfg,
                    equip=equip,
                    is_coldstart=coldstart_complete,
                    ensure_local_index_fn=ensure_local_index,
                )
            except Exception as be:
                Console.warn(f"Cold-start baseline setup failed: {be}", component="BASELINE",
                             equip=equip, train_rows=len(train) if train is not None else 0,
                             error=str(be))

        # ===== Seasonality detection and adjustment =====
        # Detect daily/weekly cycles and optionally adjust data to reduce
        # false positives from predictable seasonality.
        seasonal_patterns: Dict[str, List[SeasonalPattern]] = {}
        seasonal_adjusted = False
        with T.section("seasonality.detect"):
            try:
                from core.seasonality import detect_and_adjust as detect_seasonality
                train, score, seasonal_patterns, seasonal_adjusted = detect_seasonality(train, score, cfg)
                if seasonal_patterns:
                    pattern_count = sum(len(ps) for ps in seasonal_patterns.values())
                    Console.info(f"Seasonal: {pattern_count} patterns in {len(seasonal_patterns)} sensors | adjusted={seasonal_adjusted}", component="SEASON")
            except Exception as se:
                Console.warn(f"Seasonality detection skipped: {se}", component="SEASON")

        # ===== Data quality guardrails =====
        low_var_threshold = 1e-4  # Used by feature imputation
        with T.section("data.guardrails"):
            try:
                from core.pipeline_types import run_data_guardrails
                guardrail_result = run_data_guardrails(
                    train=train,
                    score=score,
                    meta=meta,
                    cfg=cfg,
                    output_manager=output_manager,
                    run_id=run_id,
                    equip_id=equip_id,
                    equip=equip,
                )
                low_var_threshold = guardrail_result.low_var_threshold
            except Exception as g_e:
                Console.warn(f"Guardrail checks skipped: {g_e}", component="DATA",
                             equip=equip, error_type=type(g_e).__name__, error=str(g_e)[:200])

        # Preserve raw sensor data before feature engineering (needed for regime basis).
        raw_train = train.copy()
        raw_score = score.copy()

        # ===== Feature construction (detectors require engineered features) =====
        with T.section("features.build"):
            train, score = _build_features(train, score, cfg, equip)
            Console.info(f"Features built: train={train.shape}, score={score.shape}", component="FEAT")

        # ===== Impute missing values in feature space (detectors require clean data) =====
        with T.section("features.impute"):
            train, score, _ = fast_features.impute_features(
                train, score, low_var_threshold, output_manager, run_id, equip_id, equip
            )

        current_train_columns = list(train.columns)
        with T.section("features.hash"):
            train_feature_hash = compute_stable_feature_hash(train, equip)

        # Respect refit requests captured in SQL.
        with T.section("models.refit_flag"):
            refit_requested = output_manager.check_refit_request()

        # ===== Phase 2: Load or fit detectors =====
        ar1_detector = pca_detector = iforest_detector = gmm_detector = omr_detector = None
        pca_train_spe = pca_train_t2 = None
        regime_model = None
        regime_state = None
        regime_state_version = 0
        regime_loaded_from_state = False  # Boolean flag replaces legacy string sentinel.
        col_meds = None
        cached_models = None  # Initialize to avoid UnboundLocalError.
        cached_manifest = None
        previous_weights = None  # Initialize for fusion pipeline.
        reuse_models = False  # File-based caching disabled; models persist to SQL.
        det_flags = get_detector_enable_flags(cfg)
        # Extract detector enable flags for use throughout the pipeline.
        ar1_enabled = det_flags["ar1_enabled"]
        pca_enabled = det_flags["pca_enabled"]
        iforest_enabled = det_flags["iforest_enabled"]
        gmm_enabled = det_flags["gmm_enabled"]
        omr_enabled = det_flags["omr_enabled"]
        use_cache = cfg.get("models", {}).get("use_cache", True) and not refit_requested and not force_retraining
        
        with T.section("models.load"):
            if use_cache and detector_cache is None:
                current_sensors = list(train.columns) if hasattr(train, 'columns') else []
                cached_models, cached_manifest = load_cached_models_with_validation(
                    equip=equip, sql_client=sql_client, equip_id=equip_id,
                    cfg=cfg, train_columns=current_sensors,
                )
                if cached_models:
                    rebuild_result = rebuild_detectors_from_cache(
                        cached_models=cached_models, cached_manifest=cached_manifest,
                        cfg=cfg, equip=equip, current_columns=current_sensors
                    )
                    ar1_detector = rebuild_result["ar1_detector"]
                    pca_detector = rebuild_result["pca_detector"]
                    iforest_detector = rebuild_result["iforest_detector"]
                    gmm_detector = rebuild_result["gmm_detector"]
                    omr_detector = rebuild_result["omr_detector"]
                    regime_model = rebuild_result.get("regime_model")
                    col_meds = rebuild_result.get("feature_medians")
                    
                    # AUDIT FIX: Log validation warnings if any
                    if rebuild_result.get("validation_warnings"):
                        for warn in rebuild_result["validation_warnings"]:
                            Console.info(f"Model validation: {warn}", component="MODEL", equip=equip)
                        
            elif detector_cache:
                ar1_detector = detector_cache.get("ar1")
                pca_detector = detector_cache.get("pca")
                iforest_detector = detector_cache.get("iforest")
                gmm_detector = detector_cache.get("gmm")
                regime_model = detector_cache.get("regime_model")
                
                if regime_model is not None:
                    regime_model.meta["quality_ok"] = bool(detector_cache.get("regime_quality_ok", True))
                    if detector_cache.get("regime_basis_hash"):
                        regime_model.train_hash = detector_cache["regime_basis_hash"]
                
                if not all([ar1_detector, pca_detector, iforest_detector]):
                    Console.warn("Cached detectors incomplete; will re-fit", component="MODEL")
                    ar1_detector = pca_detector = iforest_detector = gmm_detector = omr_detector = None
                    regime_model = None
            
            # Load regime state from SQL if no regime model is loaded.
            if regime_model is None:
                try:
                    from core.model_persistence import load_regime_state
                    regime_state = load_regime_state(equip=equip, equip_id=equip_id, sql_client=sql_client)
                    if regime_state is not None and regime_state.quality_ok:
                        regime_state_version = regime_state.state_version
                        regime_loaded_from_state = True  # Boolean flag replaces string sentinel.
                        Console.info(f"Regime loaded from state_v{regime_state_version} | K={regime_state.n_clusters}", component="REGIME")
                except Exception as e:
                    Console.warn(f"Failed to load regime state: {e}", component="REGIME")

        # Check if we need to fit detectors using ORIGINAL config-based flags.
        # NOTE: Reconciliation happens AFTER fitting, not before - otherwise we skip training!
        detectors_missing = not all([
            ar1_detector or not ar1_enabled,
            pca_detector or not pca_enabled,
            iforest_detector or not iforest_enabled,
        ])
        
        if detectors_missing and not ALLOWS_MODEL_REFIT:
            Console.error(
                "ONLINE mode requires pre-trained models but none found in cache",
                component="MODEL", equip=equip, mode="ONLINE",
                hint="Run in OFFLINE mode first, or check ModelRegistry"
            )
            raise RuntimeError(f"Required detector models not found in cache for {equip}")
        
        if detectors_missing:
            with T.section("train.detector_fit"):
                fit_result = fit_all_detectors(
                    train=train, cfg=cfg, **det_flags,
                    output_manager=output_manager, sql_client=sql_client,
                    run_id=run_id, equip_id=equip_id, equip=equip,
                )
                ar1_detector = fit_result["ar1_detector"]
                pca_detector = fit_result["pca_detector"]
                iforest_detector = fit_result["iforest_detector"]
                gmm_detector = fit_result["gmm_detector"]
                omr_detector = fit_result["omr_detector"]
                pca_train_spe = fit_result["pca_train_spe"]
                pca_train_t2 = fit_result["pca_train_t2"]

        # AUDIT FIX: Reconcile enable flags with actually loaded/fitted detectors
        # This ensures consistency between config-based flags and runtime detector availability
        # NOTE: This MUST happen AFTER fitting, not before - otherwise we skip training!
        reconciled_flags = reconcile_detector_flags_with_loaded_models(
            enable_flags=det_flags,
            ar1_detector=ar1_detector,
            pca_detector=pca_detector,
            iforest_detector=iforest_detector,
            gmm_detector=gmm_detector,
            omr_detector=omr_detector,
            equip=equip,
        )
        # Update local enable flags with reconciled values for downstream scoring
        ar1_enabled = reconciled_flags["ar1_enabled"]
        pca_enabled = reconciled_flags["pca_enabled"]
        iforest_enabled = reconciled_flags["iforest_enabled"]
        gmm_enabled = reconciled_flags["gmm_enabled"]
        omr_enabled = reconciled_flags["omr_enabled"]

        # Validate all enabled detectors are present.
        missing = []
        if ar1_enabled and not ar1_detector: missing.append("ar1")
        if pca_enabled and not pca_detector: missing.append("pca")
        if iforest_enabled and not iforest_detector: missing.append("iforest")
        if gmm_enabled and not gmm_detector: missing.append("gmm")
        if omr_enabled and not omr_detector: missing.append("omr")
        
        if missing:
            Console.error(f"Detector initialization failed: {missing}", component="MODEL", equip=equip)
            raise RuntimeError(f"Required detector initialization failed: {missing}")

        # ===== Phase 3: Build regime feature basis (required for labeling) =====
        # Build regime basis inline; failures should degrade the run, not abort it.
        regime_basis_train = None
        regime_basis_score = None
        regime_basis_meta = {}
        regime_basis_hash = None
        
        try:
            basis_train, basis_score, basis_meta = regimes.build_feature_basis(
                train_features=train, score_features=score,
                raw_train=raw_train, raw_score=raw_score,
                pca_detector=pca_detector, cfg=cfg,
            )
            
            # Add health-state features for regime clustering so pre/post-fault
            # behavior can be separated into distinct regimes.
            try:
                if basis_train is not None and basis_score is not None:
                    # v11.3.x: Health-state features are OPTIONAL (config: regimes.health_state_features.enabled)
                    # WARNING: Adding health variables causes regime drift as equipment degrades
                    # Recommendation: Keep disabled (default: False) for stable operating regimes
                    health_state_enabled = cfg_dict.get("regimes.health_state_features.enabled", False)
                    
                    if health_state_enabled:
                        # Prepare detector scores for health-state computation.
                        detector_cols = {}
                        if 'ar1_z' in train.columns:
                            detector_cols['ar1_z'] = train['ar1_z'].values
                        if 'pca_spe_z' in train.columns:
                            detector_cols['pca_spe_z'] = train['pca_spe_z'].values
                        if 'pca_t2_z' in train.columns:
                            detector_cols['pca_t2_z'] = train['pca_t2_z'].values
                        
                        # Only add health features if detector scores are available.
                        if detector_cols:
                            basis_train = regimes._add_health_state_features(basis_train, detector_cols)
                            basis_score = regimes._add_health_state_features(basis_score, detector_cols)
                            basis_meta["health_state_features_added"] = True
                            Console.warn(
                                "Health-state features enabled in regime clustering. "
                                "This may cause regime drift as equipment degrades. "
                                "Consider disabling (regimes.health_state_features.enabled=False) for stable regimes.",
                                component="REGIME"
                            )
                        else:
                            basis_meta["health_state_features_added"] = False
                    else:
                        basis_meta["health_state_features_added"] = False
                        Console.info(
                            "Health-state features disabled (regimes.health_state_features.enabled=False). "
                            "Regimes based on operating variables only for stability.",
                            component="REGIME"
                        )
            except Exception as health_e:
                Console.warn(f"Health-state features failed (continuing with operating-only basis): {health_e}", 
                           component="REGIME", error=str(health_e)[:100])
                basis_meta["health_state_features_added"] = False
            
            # Schema hash keeps regimes stable once discovered unless inputs change.
            regime_cfg_str = str(cfg.get("regimes", {}))
            schema_str = ",".join(sorted(basis_train.columns)) + "|" + regime_cfg_str
            regime_basis_hash = int(hashlib.sha256(schema_str.encode()).hexdigest()[:15], 16)
            regime_basis_train = basis_train
            regime_basis_score = basis_score
            regime_basis_meta = basis_meta
        except Exception as e:
            Console.warn(f"Regime basis build failed (regimes will be unavailable): {e}", 
                        component="REGIME", equip=equip, error=str(e)[:200])
            degradations.append("regime_feature_basis")

        if regime_model is not None:
            # Only refit if feature columns changed or regime config changed.
            # 1. Feature columns changed (new sensors added/removed)
            # 2. Regime config changed (schema hash includes config)
            if (
                regime_basis_train is None
                or regime_model.feature_columns != list(regime_basis_train.columns)
            ):
                Console.warn("Cached regime model has different feature columns; will refit.", component="REGIME",
                             equip=equip,
                             cached_cols=regime_model.feature_columns[:5] if regime_model.feature_columns else [],
                             current_cols=list(regime_basis_train.columns)[:5] if regime_basis_train is not None else [])
                regime_model = None

        # ===== Phase 4: Score on SCORE window =====
        # Scoring is delegated to detector_orchestrator.score_all_detectors().
        with T.section("score.detector_score"):
            score_start_time = time.perf_counter()
            
            frame, omr_contributions_data = score_all_detectors(
                data=score,
                ar1_detector=ar1_detector,
                pca_detector=pca_detector,
                iforest_detector=iforest_detector,
                gmm_detector=gmm_detector,
                omr_detector=omr_detector,
                **det_flags,
            )

        # ===== Phase 5: Regimes (before calibration for regime-aware thresholds) =====
        train_regime_labels = None
        score_regime_labels = None
        regime_model_was_trained = False
        
        with T.section("regimes.label"):
            # Reconstruct model from loaded state when available.
            regime_state_action = "none"
            if regime_loaded_from_state and regime_state is not None and regime_basis_train is not None:
                try:
                    regime_model = regimes.regime_state_to_model(
                        state=regime_state,
                        feature_columns=list(regime_basis_train.columns),
                        raw_tags=list(raw_train.columns) if raw_train is not None else [],
                        train_hash=regime_basis_hash
                    )
                    regime_state_action = f"reconstructed_v{regime_state.state_version}"
                except Exception as e:
                    Console.warn(f"Failed to reconstruct model from state: {e}", component="REGIME_STATE",
                                 equip=equip, state_version=regime_state.state_version, error=str(e)[:200])
                    regime_model = None
                    regime_loaded_from_state = False  # Reset flag on reconstruction failure
            
            regime_ctx: Dict[str, Any] = {
                "regime_basis_train": regime_basis_train,
                "regime_basis_score": regime_basis_score,
                "basis_meta": regime_basis_meta,
                "regime_model": regime_model,  # Pass through; no sentinel checks.
                "regime_basis_hash": regime_basis_hash,
                "X_train": train,
                "allow_discovery": ALLOWS_REGIME_DISCOVERY,  # ONLINE mode disables discovery.
            }
            regime_out = regimes.label(score, regime_ctx, {"frame": frame}, cfg)
            frame = regime_out.get("frame", frame)
            new_regime_model = regime_out.get("regime_model", regime_model)
            
            # Detect whether a new regime model was trained.
            if new_regime_model is not regime_model and new_regime_model is not None:
                regime_model_was_trained = True
                regime_model = new_regime_model
            
            score_regime_labels = regime_out.get("regime_labels")
            train_regime_labels = regime_out.get("regime_labels_train")
            regime_quality_ok = bool(regime_out.get("regime_quality_ok", True))
            if train_regime_labels is None and regime_model is not None and regime_basis_train is not None:
                train_regime_labels = regimes.predict_regime(regime_model, regime_basis_train)
            if score_regime_labels is None and regime_model is not None and regime_basis_score is not None:
                score_regime_labels = regimes.predict_regime(regime_model, regime_basis_score)
            
            # Record regime for Prometheus/Grafana observability.
            if score_regime_labels is not None and len(score_regime_labels) > 0:
                # Use the most recent regime (last value in score window).
                current_regime_id = int(score_regime_labels[-1]) if hasattr(score_regime_labels[-1], '__int__') else 0
                # Try to resolve a human-friendly label from the model.
                regime_label = ""
                if regime_model is not None and hasattr(regime_model, 'cluster_labels_'):
                    try:
                        regime_label = regime_model.cluster_labels_.get(current_regime_id, f"regime_{current_regime_id}")
                    except Exception:
                        regime_label = f"regime_{current_regime_id}"
                record_regime(equip, current_regime_id, regime_label)
            
            # Save regime state if a model was trained.
            if regime_model_was_trained and regime_model is not None:
                try:
                    from core.model_persistence import save_regime_state
                    
                    # Generate config hash for change detection
                    regime_cfg_str = str(cfg.get("regimes", {}))
                    config_hash = hashlib.sha256(regime_cfg_str.encode()).hexdigest()[:16]
                    
                    # Convert model to state
                    new_state = regimes.regime_model_to_state(
                        model=regime_model,
                        equip_id=equip_id,
                        state_version=regime_state_version + 1,
                        config_hash=config_hash,
                        regime_basis_hash=str(regime_basis_hash) if regime_basis_hash else ""
                    )
                    
                    # Save state
                    save_regime_state(
                        state=new_state,
                        equip=equip,
                        sql_client=sql_client
                    )
                    
                    regime_state_version = new_state.state_version
                    regime_defs_count = 0
                    
                    # Write regime definitions to ACM_RegimeDefinitions (HDBSCAN/GMM).
                    if output_manager and regime_model is not None and regime_model.model is not None:
                        try:
                            import json as _json
                            regime_defs = []
                            # Property handles HDBSCAN and GMM model variants.
                            centroids = regime_model.cluster_centers_  # Property handles all model types
                            # Get labels - different models store labels differently
                            if hasattr(regime_model.model, 'labels_'):
                                labels = regime_model.model.labels_  # HDBSCAN (GMM doesn't have labels_)
                            else:
                                labels = []  # GMM doesn't store labels_
                            # For HDBSCAN, filter out noise labels (-1)
                            unique_labels = np.unique(labels)
                            valid_labels = unique_labels[unique_labels >= 0]
                            for i, centroid in enumerate(centroids):
                                # Map centroid index to actual regime label (important for HDBSCAN)
                                regime_id = int(valid_labels[i]) if i < len(valid_labels) else i
                                regime_defs.append({
                                    'RegimeID': regime_id,
                                    'RegimeName': f'Regime_{regime_id}',
                                    'CentroidJSON': _json.dumps(centroid.tolist()),
                                    'FeatureColumns': _json.dumps(regime_model.feature_cols if hasattr(regime_model, 'feature_cols') else []),
                                    'DataPointCount': int(np.sum(np.array(labels) == regime_id)) if len(labels) > 0 else 0,
                                    'MaturityState': new_state.maturity_state if hasattr(new_state, 'maturity_state') else 'LEARNING',
                                })
                            output_manager.write_regime_definitions(regime_defs, version=regime_state_version)
                            regime_defs_count = len(regime_defs)
                        except Exception as e:
                            Console.warn(f"Failed to write regime definitions: {e}", component="REGIME")
                    
                    Console.info(f"Regime state: saved_v{regime_state_version} | K={new_state.n_clusters} | defs={regime_defs_count}", component="REGIME_STATE")
                except Exception as e:
                    Console.warn(f"Failed to save regime state: {e}", component="REGIME_STATE",
                                 equip=equip, error_type=type(e).__name__, error=str(e)[:200])
        
        score_out = regime_out
        regime_quality_ok = bool(regime_out.get("regime_quality_ok", True))

        # ===== Regime occupancy and transitions =====
        with T.section("regimes.occupancy"):
            occupancy_count = 0
            transition_count = 0
            try:
                if score_regime_labels is not None and len(score_regime_labels) > 0 and output_manager:
                    # Compute regime occupancy (time spent in each regime).
                    regime_series = pd.Series(score_regime_labels)
                    regime_counts = regime_series.value_counts()
                    total_points = len(score_regime_labels)
                    # Estimate sampling interval from score data.
                    sampling_interval_h = 1.0  # Default 1 hour
                    if 'Timestamp' in frame.columns and len(frame) > 1:
                        try:
                            ts_diff = pd.to_datetime(frame['Timestamp']).diff().dropna()
                            if len(ts_diff) > 0:
                                sampling_interval_h = ts_diff.median().total_seconds() / 3600.0
                        except Exception:
                            pass
                    
                    occupancy_data = []
                    for regime_id, count in regime_counts.items():
                        occupancy_data.append({
                            'RegimeLabel': str(regime_id),
                            'DwellTimeHours': float(count * sampling_interval_h),
                            'DwellFraction': float(count / total_points) if total_points > 0 else 0.0,
                            'PointCount': int(count),
                        })
                    if occupancy_data:
                        occupancy_count = output_manager.write_regime_occupancy(occupancy_data)
                    
                    # Compute regime transitions (how often regime changes).
                    if len(score_regime_labels) > 1:
                        transitions: Dict[str, Dict[str, int]] = {}
                        for i in range(1, len(score_regime_labels)):
                            from_r = str(score_regime_labels[i-1])
                            to_r = str(score_regime_labels[i])
                            if from_r != to_r:  # Only count actual transitions
                                if from_r not in transitions:
                                    transitions[from_r] = {}
                                transitions[from_r][to_r] = transitions[from_r].get(to_r, 0) + 1
                        if transitions:
                            transition_count = output_manager.write_regime_transitions(transitions)
                    
                    if occupancy_count > 0 or transition_count > 0:
                        Console.info(f"Regime analysis: occupancy={occupancy_count} | transitions={transition_count}", component="REGIME")
            except Exception as e:
                Console.warn(f"Regime occupancy/transitions write failed: {e}", component="REGIME",
                             equip=equip, error=str(e)[:200])

        # ===== Model quality assessment: check if retraining is needed =====
        # Runs after first scoring so cached model performance can be evaluated.
        force_retrain = False
        quality_report = None
        
        if cached_models and cfg.get("models", {}).get("auto_retrain", True):
            with T.section("models.quality_check"):
                try:
                    from core.model_evaluation import assess_model_quality
                    
                    # Build temporary episodes for quality check (before fusion/episodes).
                    temp_episodes = pd.DataFrame()  # Will be populated after fusion
                    
                    # Regime quality metrics.
                    regime_quality_metrics = {
                        "silhouette": score_out.get("silhouette", 0.0),
                        "quality_ok": regime_quality_ok
                    }
                    
                    # Assess quality (full assessment happens after fusion; check config now).
                    config_changed = False
                    if cached_manifest:
                        cached_sig = cached_manifest.get("config_signature", "")
                        current_sig = cfg.get("_signature", "unknown")
                        config_changed = (cached_sig != current_sig)
                    
                    # Auto-retrain config for SQL-mode data-driven triggers.
                    auto_retrain_cfg = cfg.get("models", {}).get("auto_retrain", {})
                    if isinstance(auto_retrain_cfg, bool):
                        auto_retrain_cfg = {}  # Convert legacy boolean to dict
                    
                    # Check model age (temporal validation).
                    model_age_trigger = False
                    model_age_hours = 0.0
                    max_age_hours = 720  # default
                    if cached_manifest:
                        created_at_str = cached_manifest.get("created_at")
                        if created_at_str:
                            try:
                                from datetime import datetime
                                created_at = datetime.fromisoformat(created_at_str)
                                model_age_hours = (datetime.now() - created_at).total_seconds() / 3600
                                max_age_hours = auto_retrain_cfg.get("max_model_age_hours", 720)  # 30 days default
                                if model_age_hours > max_age_hours:
                                    model_age_trigger = True
                            except Exception:
                                pass
                    
                    # Check regime quality (data-driven trigger).
                    regime_quality_trigger = False
                    min_silhouette = auto_retrain_cfg.get("min_regime_quality", 0.3)
                    current_silhouette = regime_quality_metrics.get("silhouette", 0.0)
                    if not regime_quality_ok or current_silhouette < min_silhouette:
                        regime_quality_trigger = True
                    
                    # Aggregate triggers and log a consolidated retraining reason.
                    if config_changed or model_age_trigger or regime_quality_trigger:
                        reasons = []
                        if config_changed:
                            reasons.append("config_changed")
                        if model_age_trigger:
                            reasons.append(f"age={model_age_hours:.0f}h>{max_age_hours}h")
                        if regime_quality_trigger:
                            reasons.append(f"silhouette={current_silhouette:.3f}<{min_silhouette}")
                        Console.warn(f"Forcing retraining: {' | '.join(reasons)}", component="MODEL", equip=equip)
                        force_retrain = True
                    
                    # Invalidate cached models if retraining is required.
                    if force_retrain:
                        cached_models = None
                        ar1_detector = pca_detector = iforest_detector = gmm_detector = None
                        
                        # Determine retrain reason for observability.
                        retrain_reason = "config_changed" if config_changed else (
                            "model_age" if model_age_trigger else (
                                "regime_quality" if regime_quality_trigger else "forced"
                            )
                        )
                        record_model_refit(equip, reason=retrain_reason, detector="all")
                        
                        # Fit detectors via detector_orchestrator.fit_all_detectors().
                        retrain_result = fit_all_detectors(
                            train=train, cfg=cfg, **det_flags,
                            output_manager=output_manager, sql_client=sql_client,
                            run_id=run_id, equip_id=equip_id, equip=equip,
                        )
                        ar1_detector = retrain_result["ar1_detector"]
                        pca_detector = retrain_result["pca_detector"]
                        iforest_detector = retrain_result["iforest_detector"]
                        gmm_detector = retrain_result["gmm_detector"]
                        omr_detector = retrain_result["omr_detector"]
                        pca_train_spe = retrain_result["pca_train_spe"]
                        pca_train_t2 = retrain_result["pca_train_t2"]
                        
                except Exception as e:
                    Console.warn(f"Quality assessment failed: {e}", component="MODEL",
                                 equip=equip, error_type=type(e).__name__, error=str(e)[:200])

        # ===== Model persistence: save trained models with versioning =====
        # `detectors_fitted_this_run` reflects actual fitting activity.
        detectors_fitted_this_run = (not cached_models and detector_cache is None) or force_retrain
        models_were_trained = detectors_fitted_this_run  # Clearer: save only if fitted this run
        if models_were_trained:
            with T.section("models.persistence.save"):
                col_meds_value = col_meds  # Initialized at function scope.
                save_trained_models(
                    equip=equip,
                    sql_client=sql_client,
                    equip_id=equip_id,
                    cfg=cfg,
                    train=train,
                    ar1_detector=ar1_detector,
                    pca_detector=pca_detector,
                    iforest_detector=iforest_detector,
                    gmm_detector=gmm_detector,
                    omr_detector=omr_detector,
                    regime_model=regime_model,
                    col_meds=col_meds_value,
                    regime_quality_ok=regime_quality_ok,
                    timing_sections=T.timings if hasattr(T, 'timings') else None,
                    run_id=run_id,
                )
                
                # Model lifecycle management: track maturity and check promotion.
                # Set train_start/train_end from actual data in this run.
                if hasattr(train.index, 'min') and len(train.index) > 0:
                    train_start = pd.to_datetime(train.index.min())
                    train_end = pd.to_datetime(train.index.max())
                else:
                    train_start = datetime.now()
                    train_end = datetime.now()
                
                if output_manager and sql_client:
                    try:
                        # Get silhouette score from regime model if available.
                        silhouette = None
                        if regime_model is not None and hasattr(regime_model, 'meta'):
                            silhouette = regime_model.meta.get('fit_score')
                        
                        # Load existing state or create new.
                        model_state = load_model_state_from_sql(sql_client, equip_id)
                        
                        if model_state is None:
                            # First time: create new state in LEARNING.
                            version = regime_state_version
                            model_state = create_new_model_state(
                                equip_id=int(equip_id),
                                version=version,
                                training_rows=len(train),
                                training_start=train_start,
                                training_end=train_end,
                                silhouette_score=silhouette,
                                run_id=run_id,
                            )
                        else:
                            # Update existing state.
                            training_days = (train_end - train_start).total_seconds() / 86400.0
                            model_state = update_model_state_from_run(
                                state=model_state,
                                run_id=run_id,
                                run_success=True,
                                silhouette_score=silhouette,
                                stability_ratio=1.0 if regime_quality_ok else 0.5,  # Simplified for now
                                additional_rows=len(train),
                                additional_days=training_days,
                            )
                            
                            # Check promotion eligibility if still LEARNING.
                            promotion_happened = False
                            if model_state.maturity == MaturityState.LEARNING:
                                eligible, unmet = check_promotion_eligibility(model_state)
                                if eligible:
                                    old_maturity = model_state.maturity.value
                                    model_state = promote_model(model_state)
                                    promotion_happened = True
                                    
                                    # Write regime promotion log.
                                    try:
                                        promotion_record = [{
                                            'RegimeLabel': 'ALL',  # Model-level promotion
                                            'FromState': old_maturity,
                                            'ToState': model_state.maturity.value,
                                            'Reason': 'met_promotion_criteria',
                                            'PromotedAt': datetime.now(),
                                            'Version': model_state.version,
                                            'ConsecutiveRuns': model_state.consecutive_runs,
                                            'TotalDays': model_state.total_days,
                                        }]
                                        output_manager.write_regime_promotion_log(promotion_record)
                                    except Exception:
                                        pass  # Promotion log is best-effort.
                                    
                                    Console.ok(f"Model promoted: LEARNING->CONVERGED (runs={model_state.consecutive_runs}, days={model_state.total_days:.1f})", component="LIFECYCLE")
                        
                        # Write updated state.
                        output_manager.write_active_models(get_active_model_dict(
                            model_state,
                            regime_version=regime_state_version,
                        ))
                        
                        # Propagate maturity_state to OutputManager to avoid race conditions.
                        if model_state is not None:
                            output_manager.set_maturity_state(str(model_state.maturity.value))
                        
                        Console.info(f"Model state: {model_state.maturity.value}", component="LIFECYCLE",
                                     version=model_state.version, consecutive_runs=model_state.consecutive_runs)
                    except Exception as e:
                        Console.warn(f"Failed to update model lifecycle: {e}", component="LIFECYCLE",
                                     error=str(e)[:200])

        # ===== Phase 6: Calibration (z-score normalization) =====
        # Fit calibrators on TRAIN data, transform SCORE data.
        # v11.3.3: Now includes contamination filtering for robust calibration.
        with T.section("calibrate"):
            cal_q = float((cfg or {}).get("thresholds", {}).get("q", 0.98))
            self_tune_cfg = (cfg or {}).get("thresholds", {}).get("self_tune", {})
            use_per_regime = (cfg.get("fusion", {}) or {}).get("per_regime", False)
            quality_ok = bool(use_per_regime and regime_quality_ok and train_regime_labels is not None and score_regime_labels is not None)
            
            # v11.3.3: Add contamination filter config to self_tune_cfg for ScoreCalibrator
            # This addresses Analytics Audit Finding #6: contaminated training windows
            contam_filter_cfg = (cfg or {}).get("thresholds", {}).get("contamination_filter", {})
            if contam_filter_cfg:
                self_tune_cfg["contamination_filter"] = {
                    "enabled": contam_filter_cfg.get("enabled", True),
                    "method": contam_filter_cfg.get("method", "iterative_mad"),
                    "z_threshold": float(contam_filter_cfg.get("z_threshold", 4.0)),
                    "max_iterations": int(contam_filter_cfg.get("max_iterations", 10)),
                    "min_retained_ratio": float(contam_filter_cfg.get("min_retained_ratio", 0.70)),
                }
            else:
                # Default: enable contamination filtering with iterative MAD
                self_tune_cfg["contamination_filter"] = {
                    "enabled": True,
                    "method": "iterative_mad",
                    "z_threshold": 4.0,
                    "max_iterations": 10,
                    "min_retained_ratio": 0.70,
                }
            
            # Score TRAIN data with all fitted detectors.
            pca_cached = (pca_train_spe, pca_train_t2) if pca_train_spe is not None else None
            train_frame, _ = score_all_detectors(
                data=train,
                ar1_detector=ar1_detector,
                pca_detector=pca_detector,
                iforest_detector=iforest_detector,
                gmm_detector=gmm_detector,
                omr_detector=omr_detector,
                ar1_enabled=ar1_enabled,
                pca_enabled=pca_enabled,
                iforest_enabled=iforest_enabled,
                gmm_enabled=gmm_enabled,
                omr_enabled=omr_enabled,
                pca_cached=pca_cached,
                return_omr_contributions=False,
            )
            
            # Compute adaptive z-clip directly from TRAIN raw scores (no temp calibrators).
            # This avoids redundant temporary fits and uses inline P99 z-scores.
            default_clip = float(self_tune_cfg.get("clip_z", 8.0))
            train_z_p99 = {}
            
            # Detector raw columns to analyze.
            det_raw_cols = [("ar1", "ar1_raw"), ("pca_spe", "pca_spe"), ("pca_t2", "pca_t2"),
                           ("iforest", "iforest_raw"), ("gmm", "gmm_raw")]
            if omr_enabled:
                det_raw_cols.append(("omr", "omr_raw"))
            
            for det_name, raw_col in det_raw_cols:
                if raw_col in train_frame.columns:
                    raw_vals = train_frame[raw_col].to_numpy(copy=False)
                    finite_vals = raw_vals[np.isfinite(raw_vals)]
                    if len(finite_vals) > 10:
                        # Compute median/MAD/scale inline (same formula as ScoreCalibrator.fit).
                        med = float(np.median(finite_vals))
                        mad = float(np.median(np.abs(finite_vals - med)))
                        scale = mad * 1.4826 if mad > 1e-9 else float(np.nanstd(finite_vals))
                        scale = max(scale, 1e-3)  # Minimum scale
                        # Compute z-scores and P99
                        z_vals = (finite_vals - med) / scale
                        p99 = float(np.percentile(z_vals, 99))
                        if 0 < p99 < 100:  # Sanity check
                            train_z_p99[det_name] = p99
            
            # Set adaptive clip: max(default, 1.5 * max_train_p99), capped at 50.
            adaptive_clip = default_clip
            if train_z_p99:
                max_train_p99 = max(train_z_p99.values())
                adaptive_clip = max(default_clip, min(max_train_p99 * 1.5, 50.0))
                self_tune_cfg["clip_z"] = adaptive_clip
            
            fit_regimes = train_regime_labels if quality_ok else None
            transform_regimes = score_regime_labels if quality_ok else None

            # Surface per-regime calibration activity.
            frame["per_regime_active"] = 1 if quality_ok else 0
            
            # Delegate to detector_orchestrator.calibrate_all_detectors().
            frame, calibrators_dict = calibrate_all_detectors(
                train_frame=train_frame,
                score_frame=frame,
                cal_q=cal_q,
                self_tune_cfg=self_tune_cfg,
                fit_regimes=fit_regimes,
                transform_regimes=transform_regimes,
                omr_enabled=omr_enabled,
            )
            
            # Extract calibrators for later use.
            cal_ar = calibrators_dict.get("ar1_z")
            cal_pca_spe = calibrators_dict.get("pca_spe_z")
            cal_pca_t2 = calibrators_dict.get("pca_t2_z")
            cal_if = calibrators_dict.get("iforest_z")
            cal_gmm = calibrators_dict.get("gmm_z")
            cal_omr = calibrators_dict.get("omr_z")

            # Compute TRAIN z-scores for PCA metrics (needed for SQL metadata).
            # Only compute if PCA is enabled and calibrators exist.
            spe_p95_train = 0.0
            t2_p95_train = 0.0
            if pca_enabled and cal_pca_spe is not None and "pca_spe" in train_frame.columns:
                pca_train_spe_z = cal_pca_spe.transform(
                    train_frame["pca_spe"].to_numpy(dtype=np.float32), regime_labels=fit_regimes
                )
                spe_p95_train = float(np.nanpercentile(pca_train_spe_z, 95))
            if pca_enabled and cal_pca_t2 is not None and "pca_t2" in train_frame.columns:
                pca_train_t2_z = cal_pca_t2.transform(
                    train_frame["pca_t2"].to_numpy(dtype=np.float32), regime_labels=fit_regimes
                )
                t2_p95_train = float(np.nanpercentile(pca_train_t2_z, 95))
            
            # Build calibrators list, filtering out None entries
            calibrators: List[Tuple[str, fuse.ScoreCalibrator]] = []
            if ar1_enabled and cal_ar is not None:
                calibrators.append(("ar1_z", cal_ar))
            if pca_enabled and cal_pca_spe is not None:
                calibrators.append(("pca_spe_z", cal_pca_spe))
            if pca_enabled and cal_pca_t2 is not None:
                calibrators.append(("pca_t2_z", cal_pca_t2))
            if iforest_enabled and cal_if is not None:
                calibrators.append(("iforest_z", cal_if))
            if gmm_enabled and cal_gmm is not None:
                calibrators.append(("gmm_z", cal_gmm))
            if omr_enabled and cal_omr is not None and "omr_raw" in frame.columns:
                calibrators.append(("omr_z", cal_omr))

            # Generate per-regime threshold transparency table.
            per_regime_count = 0
            if quality_ok and use_per_regime:
                per_regime_rows = []
                for detector_name, calibrator in calibrators:
                    for regime_id in sorted(calibrator.regime_thresh_.keys()):
                        med_r, scale_r = calibrator.regime_params_[regime_id]
                        thresh_z = calibrator.regime_thresh_[regime_id]
                        per_regime_rows.append({
                            "detector": detector_name,
                            "regime": int(regime_id),
                            "median": float(med_r),
                            "scale": float(scale_r),
                            "z_threshold": float(thresh_z),
                            "global_median": float(calibrator.med),
                            "global_scale": float(calibrator.scale),
                        })
                
                if per_regime_rows:
                    # Convert to pandas DataFrame.
                    per_regime_df = pd.DataFrame(per_regime_rows)
                    # Pass logical artifact name instead of file path.
                    output_manager.write_dataframe(per_regime_df, "per_regime_thresholds")
                    per_regime_count = len(per_regime_rows)

            # Always write thresholds table with global fallback.
            threshold_rows: List[Dict[str, Any]] = []
            for detector_name, calibrator in calibrators:
                threshold_rows.append({
                    "detector": detector_name,
                    "regime": "GLOBAL",
                    "median": float(calibrator.med),
                    "scale": float(calibrator.scale),
                    "z_threshold": float(calibrator.q_z),
                    "raw_threshold": float(calibrator.q_thresh),
                })
                for regime_id, regime_thresh in calibrator.regime_thresh_.items():
                    med_r, scale_r = calibrator.regime_params_.get(regime_id, (calibrator.med, calibrator.scale))
                    threshold_rows.append({
                        "detector": detector_name,
                        "regime": int(regime_id),
                        "median": float(med_r),
                        "scale": float(scale_r),
                        "z_threshold": float(regime_thresh),
                        "raw_threshold": float(med_r + regime_thresh * max(scale_r, 1e-9)),
                    })

            if threshold_rows:
                thresholds_df = pd.DataFrame(threshold_rows)
                # Pass logical artifact name instead of file path.
                output_manager.write_dataframe(thresholds_df, "acm_thresholds")

            # ===== Calibration summary =====
            cal_summary_count = 0
            try:
                if output_manager and calibrators:
                    calibration_summary = []
                    for detector_name, calibrator in calibrators:
                        calibration_summary.append({
                            'DetectorType': detector_name,
                            'CalibrationScore': float(calibrator.q_z) if hasattr(calibrator, 'q_z') else 0.0,
                            'Median': float(calibrator.med) if hasattr(calibrator, 'med') else 0.0,
                            'Scale': float(calibrator.scale) if hasattr(calibrator, 'scale') else 0.0,
                            'NumRegimes': len(calibrator.regime_thresh_) if hasattr(calibrator, 'regime_thresh_') else 0,
                        })
                    if calibration_summary:
                        cal_summary_count = output_manager.write_calibration_summary(calibration_summary)
            except Exception as e:
                Console.warn(f"Calibration summary write failed: {e}", component="CAL",
                             equip=equip, error=str(e)[:200])
            
            # Consolidated calibration log.
            Console.info(f"Calibration complete: q={cal_q} | clip_z={adaptive_clip:.2f} | detectors={len(calibrators)} | thresholds={len(threshold_rows)} | per_regime={per_regime_count} | summary={cal_summary_count}", component="CAL")

        # ===== Phase 7: Fusion + episodes =====
        with T.section("fusion"):
            from core.fuse import run_fusion_pipeline, FusionResult
            
            fusion_result: FusionResult = run_fusion_pipeline(
                frame=frame,
                train_frame=train_frame,
                score_data=score,
                train_data=train,
                cfg=cfg,
                score_regime_labels=score_regime_labels,
                train_regime_labels=train_regime_labels,
                output_manager=output_manager,
                previous_weights=previous_weights,
                equip=equip,
            )
            
            # Unpack results
            frame["fused"] = fusion_result.fused_scores
            episodes = fusion_result.episodes
            fusion_weights_used = fusion_result.weights_used
            
            if fusion_result.train_fused is not None:
                train_frame["fused"] = fusion_result.train_fused
            
            # Record observability metrics.
            detector_scores = {"fused_z": float(fusion_result.fused_scores[-1]) if len(fusion_result.fused_scores) > 0 else 0.0}
            for det in ["ar1_z", "pca_spe_z", "pca_t2_z", "iforest_z", "gmm_z", "omr_z"]:
                if det in frame.columns:
                    detector_scores[det] = float(frame[det].iloc[-1])
            record_detector_scores(equip, detector_scores)
            
            if len(episodes) > 0:
                record_episode(equip, count=len(episodes), severity="warning")

        # ===== Adaptive thresholds =====
        with T.section("thresholds.adaptive"):
            # Determine whether to update thresholds this run.
            run_count = cfg.get("runtime", {}).get("run_count", 0)
            interval_reached = (run_count % threshold_update_interval == 0) if threshold_update_interval > 0 else True
            should_update = (
                (coldstart_complete and not hasattr(cfg, '_thresholds_calculated')) or
                (CONTINUOUS_LEARNING and interval_reached)
            )
            
            if should_update and "fused" in train_frame.columns:
                train_fused_np = train_frame["fused"].to_numpy(copy=False)
                regime_labels_for_thresh = train["regime_label"].to_numpy(copy=False) if "regime_label" in train.columns else None
                
                calculate_and_persist_thresholds(
                    fused_scores=train_fused_np,
                    cfg=cfg,
                    equip_id=equip_id,
                    output_manager=output_manager,
                    train_index=train.index,
                    regime_labels=regime_labels_for_thresh,
                    regime_quality_ok=regime_quality_ok
                )
                cfg._thresholds_calculated = True
                Console.info(f"Threshold: updated at run {run_count}", component="THRESHOLD")

        # Regime health labeling and transient detection.
        regime_stats: Dict[int, Dict[str, float]] = {}
        transient_counts: Dict[str, int] = {}
        if not regime_quality_ok and "regime_label" in frame.columns:
            frame["regime_state"] = "unknown"
        if regime_model is not None and regime_quality_ok and "regime_label" in frame.columns and "fused" in frame.columns:
            try:
                regime_stats = regimes.update_health_labels(regime_model, frame["regime_label"].to_numpy(copy=False), frame["fused"], cfg)
                frame["regime_state"] = frame["regime_label"].map(lambda x: regime_model.health_labels.get(int(x), "unknown"))
                summary_df = regimes.build_summary_dataframe(regime_model)
                if not summary_df.empty:
                    # Use OutputManager for efficient writing (logical name)
                    output_manager.write_dataframe(summary_df, "regime_summary")
            except Exception as e:
                Console.warn(f"Health labelling skipped: {e}", component="REGIME")
        if "regime_label" in frame.columns and "regime_state" not in frame.columns:
            # Map regime labels to descriptive state names.
            # -1 = UNKNOWN (low confidence), 0+ = named regimes.
            frame["regime_state"] = frame["regime_label"].map(
                lambda lbl: "unknown" if lbl == -1 else f"regime_{lbl}"
            )
        
        # Transient state detection.
        if "regime_label" in frame.columns:
            with T.section("regimes.transient_detection"):
                try:
                    transient_states = regimes.detect_transient_states(
                        data=score,  # Use original score data for ROC calculation.
                        regime_labels=frame["regime_label"].to_numpy(copy=False),
                        cfg=cfg
                    )
                    frame["transient_state"] = transient_states
                    transient_counts = frame["transient_state"].value_counts().to_dict() if "transient_state" in frame.columns else {}
                except Exception as trans_e:
                    Console.warn(f"Transient detection failed: {trans_e}", component="TRANSIENT")
                    frame["transient_state"] = "unknown"
        
        # Consolidated regime/transient log.
        state_counts = frame["regime_state"].value_counts().to_dict() if "regime_state" in frame.columns else {}
        Console.info(f"Regime: quality_ok={regime_quality_ok} | states={state_counts} | transient={transient_counts}", component="REGIME")

        # ===== Autonomous parameter tuning =====
        # Delegated to model_evaluation.auto_tune_parameters().
        auto_tune_parameters(
            frame=frame,
            episodes=episodes,
            score_out=score_out,
            regime_quality_ok=regime_quality_ok,
            cfg=cfg,
            sql_client=sql_client,
            run_id=run_id,
            equip_id=equip_id,
            equip=equip,
            output_manager=output_manager,
            cached_manifest=cached_manifest if 'cached_manifest' in locals() else None,
        )

        if reuse_models:
                cache_payload = {
                    "ar1": ar1_detector,
                    "pca": pca_detector,
                    "iforest": iforest_detector,
                    "gmm": gmm_detector,
                    "omr": omr_detector,
                    "train_columns": current_train_columns,
                    "train_hash": train_feature_hash,
                    "config_signature": config_signature,
                    "regime_model": regime_model,
                    "regime_basis_hash": regime_basis_hash,
                    "regime_quality_ok": regime_quality_ok,
                }

        # ===== Phase 8: Drift =====
        with T.section("drift"):
            score_out["frame"] = frame # type: ignore
            score_out = drift.compute(score, score_out, cfg)
            frame = score_out["frame"]

        # Multi-feature drift detection (drift.compute_drift_alert_mode()).
        frame = drift.compute_drift_alert_mode(
            frame=frame,
            cfg=cfg,
            regime_quality_ok=regime_quality_ok,
            equip=equip,
        )

        # ===== Drift controller state =====
        with T.section("drift.controller"):
            try:
                if output_manager:
                    drift_state = score_out.get('drift_state', {})
                    if not drift_state:
                        # Build drift state from frame if available
                        drift_mode = frame.get('drift_mode', ['STABLE'])[-1] if 'drift_mode' in frame.columns else 'STABLE'
                        drift_z = frame.get('drift_z', [0.0])
                        drift_state = {
                            'ControllerState': str(drift_mode) if isinstance(drift_mode, str) else 'STABLE',
                            'CurrentDriftZ': float(drift_z.iloc[-1]) if hasattr(drift_z, 'iloc') else 0.0,
                            'Threshold': float(cfg.get('drift', {}).get('threshold', 3.0)),
                            'Sensitivity': float(cfg.get('drift', {}).get('sensitivity', 1.0)),
                        }
                    if drift_state:
                        rows = output_manager.write_drift_controller(drift_state)
            except Exception as e:
                Console.warn(f"Drift controller write failed: {e}", component="DRIFT",
                             equip=equip, error=str(e)[:200])

        # Normalize episodes schema for report/export.
        episodes, frame = fuse.normalize_episodes_schema(
            episodes=episodes,
            frame=frame,
            equip=equip,
        )

        # ===== Rolling baseline buffer: update with latest raw SCORE =====
        with T.section("baseline.buffer_write"):
            try:
                if sql_client:
                    output_manager.update_baseline_buffer(
                        score_numeric=raw_score,
                        cfg=cfg,
                        coldstart_complete=coldstart_complete
                    )
            except Exception as be:
                Console.warn(f"Baseline buffer update failed: {be}", component="BASELINE",
                             equip=equip, error_type=type(be).__name__, error=str(be)[:200])

        sensor_context: Optional[Dict[str, Any]] = None
        with T.section("sensor.context"):
            try:
                if len(raw_train) and len(raw_score):
                    common_cols = [col for col in raw_score.columns if col in raw_train.columns]
                    if common_cols:
                        train_baseline = raw_train[common_cols]
                        score_baseline = raw_score[common_cols]
                        # ROBUST: Use median instead of mean for baseline
                        train_median = train_baseline.median()
                        # ROBUST: Use MAD instead of std for scale
                        train_mad = (train_baseline - train_median).abs().median()
                        train_std = (train_mad * 1.4826).replace(0.0, np.nan).fillna(1e-10)  # MAD to std-equivalent
                        valid_cols = train_std[train_std > 1e-10].index.tolist()  # Only truly valid columns
                        if valid_cols:
                            train_median = train_median[valid_cols]
                            train_std = train_std[valid_cols]
                            score_baseline = score_baseline[valid_cols]
                            score_aligned = score_baseline.reindex(frame.index)
                            score_aligned = score_aligned.apply(pd.to_numeric, errors="coerce")
                            sensor_z = (score_aligned - train_median) / train_std
                            sensor_z = sensor_z.replace([np.inf, -np.inf], np.nan)
                            # Ensure alignment with scoring frame for downstream joins
                            sensor_context = {
                                "values": score_aligned,
                                "z_scores": sensor_z,
                                "train_mean": train_median,  # Median stored under legacy key for compatibility.
                                "train_std": train_std,
                                "train_p95": train_baseline[valid_cols].quantile(0.95),
                                "train_p05": train_baseline[valid_cols].quantile(0.05),
                                "omr_contributions": omr_contributions_data,  # Add OMR contributions for visualization
                                "regime_meta": regime_model.meta if regime_model else {}  # Add regime model metadata for chart subtitles
                            }
            except Exception as sensor_ctx_err:
                Console.warn(f"Failed to build sensor analytics context: {sensor_ctx_err}", component="SENSOR",
                             equip=equip, error_type=type(sensor_ctx_err).__name__, error=str(sensor_ctx_err)[:200])
                sensor_context = None

        # ===== Contribution timeline =====
        with T.section("contribution.timeline"):
            try:
                if output_manager and fusion_weights_used:
                    contrib_df = build_contribution_timeline(frame, fusion_weights_used)
                    if contrib_df is not None and len(contrib_df) > 0:
                        rows = output_manager.write_contribution_timeline(contrib_df)
            except Exception as e:
                Console.warn(f"Contribution timeline write failed: {e}", component="CONTRIB",
                             equip=equip, error=str(e)[:200])

        # ===== Phase 9: Persist artifacts / finalize (SQL-only) =====
        rows_read = int(score.shape[0])
        anomaly_count = int(len(episodes))
        
        # `degradations` is tracked throughout the pipeline for final outcome.
        
        # SQL-only persistence.
        with T.section("persist"):
            # Core outputs must succeed; failures here abort the run.
            with T.section("persist.write_scores"):
                rows_written = output_manager.write_scores(frame)
                Console.info(f"Scores written: {rows_written} rows", component="IO")

            with T.section("persist.write_episodes"):
                episode_rows = output_manager.write_episodes(episodes)
                if episodes is not None and len(episodes) > 0:
                    record_episode(equip, count=len(episodes), severity="info")
                    Console.info(f"Episodes written: {episode_rows} rows", component="IO")

            # Culprits are written via OutputManager.
            
            # === Additional table writes ===
            # Detector correlation matrix (correlation between detector z-scores).
            with T.section("persist.detector_correlation"):
                try:
                    z_cols = [c for c in frame.columns if c.endswith('_z') and c not in ['drift_z']]
                    if len(z_cols) >= 2:
                        z_df = frame[z_cols].dropna(how='all')
                        if len(z_df) > 10:  # Need enough data for correlation
                            # Filter out zero-variance columns to avoid divide-by-zero in correlation
                            z_variances = z_df.var()
                            z_cols_with_variance = z_variances[z_variances > 1e-10].index.tolist()
                            if len(z_cols_with_variance) >= 2:
                                corr_matrix = z_df[z_cols_with_variance].corr(method='pearson')
                                # Convert to nested dict format
                                det_corr = {d1: {d2: corr_matrix.loc[d1, d2] for d2 in corr_matrix.columns} for d1 in corr_matrix.index}
                                output_manager.write_detector_correlation(det_corr)
                except Exception:
                    pass  # Detector correlation is optional
            
            # Sensor correlation matrix (from raw sensor data, not feature matrix).
            with T.section("persist.sensor_correlation"):
                try:
                    if raw_score is not None and hasattr(raw_score, 'corr') and raw_score.shape[1] >= 2:
                        # Only compute correlation for actual numeric sensor columns
                        sensor_cols = [c for c in raw_score.columns 
                                      if raw_score[c].dtype in ['float64', 'float32', 'int64', 'int32']]
                        if len(sensor_cols) >= 2:
                            # Filter out zero-variance columns to avoid divide-by-zero in correlation
                            sensor_variances = raw_score[sensor_cols].var()
                            sensor_cols_with_variance = sensor_variances[sensor_variances > 1e-10].index.tolist()
                            if len(sensor_cols_with_variance) >= 2:
                                sensor_corr = raw_score[sensor_cols_with_variance].corr(method='pearson')
                                output_manager.write_sensor_correlations(sensor_corr, corr_type='pearson')
                except Exception:
                    pass  # Sensor correlation is optional

            # Sensor normalized time series (for sensor forecasting).
            with T.section("persist.sensor_normalized_ts"):
                try:
                    if raw_score is not None and len(raw_score) > 0:
                        # All numeric columns in raw data are sensors
                        sensor_cols = [c for c in raw_score.columns 
                                      if raw_score[c].dtype in ['float64', 'float32', 'int64', 'int32']]
                        if sensor_cols:
                            # Target max rows: 10K total (not 10K timestamps x N sensors).
                            # With N sensors, allow at most 10000/N timestamps.
                            max_total_rows = 10000
                            max_timestamps = max(100, max_total_rows // len(sensor_cols))
                            
                            sample_frame = raw_score
                            if len(raw_score) > max_timestamps:
                                step = max(1, len(raw_score) // max_timestamps)
                                sample_frame = raw_score.iloc[::step]
                            
                            rows_written = output_manager.write_sensor_normalized_ts(sample_frame, sensor_cols)
                except Exception as e:
                    Console.warn(f"Sensor normalized TS write failed: {e}", component="PERSIST",
                                 equip=equip, error_type=type(e).__name__, error=str(e)[:200])

            # === Seasonal patterns write ===
            with T.section("persist.seasonal_patterns"):
                try:
                    if seasonal_patterns and output_manager:
                        # Flatten patterns dict to list of dicts for SQL write
                        pattern_list = []
                        for sensor_name, patterns in seasonal_patterns.items():
                            for pattern in patterns:
                                pattern_dict = pattern.to_dict()
                                pattern_dict['SensorName'] = sensor_name
                                pattern_dict['PatternType'] = pattern_dict.pop('period_type', 'DAILY')
                                pattern_dict['PeriodHours'] = pattern_dict.pop('period_hours', 24.0)
                                pattern_dict['Amplitude'] = pattern_dict.pop('amplitude', 0.0)
                                pattern_dict['PhaseShift'] = pattern_dict.pop('phase_shift', 0.0)
                                pattern_dict['Confidence'] = pattern_dict.pop('confidence', 0.5)
                                # Remove sensor key if present (already have SensorName)
                                pattern_dict.pop('sensor', None)
                                pattern_list.append(pattern_dict)
                        if pattern_list:
                            rows = output_manager.write_seasonal_patterns(pattern_list)
                except Exception as e:
                    Console.warn(f"Seasonal patterns write failed: {e}", component="PERSIST",
                                 equip=equip, error_type=type(e).__name__, error=str(e)[:200])

            # ===== Memory cleanup: free large objects no longer needed =====
            # After persist, raw sensor data and training matrices are no longer needed.
            try:
                del raw_train, raw_score
            except NameError:
                pass  # Already deleted or never created
            try:
                # Free detector model internals (keep thin wrappers for reference).
                # Do not set detectors to None; they are still used by write_sql_artifacts.
                if iforest_detector is not None and hasattr(iforest_detector, 'model'):
                    iforest_detector.model = None  # IForest models are large (100+ trees)
                if omr_detector is not None and hasattr(omr_detector, 'model'):
                    omr_detector.model = None  # OMR models can be large
                # Keep pca_detector intact; it's needed for PCA loadings.
            except Exception:
                pass
            gc.collect()

            # === Analytics generation ===
            with T.section("outputs.comprehensive_analytics"):
                # Inject tuned fusion weights into cfg for dashboard reporting.
                if fusion_weights_used:
                    cfg.setdefault('fusion', {})['weights'] = dict(fusion_weights_used)
                
                analytics_result = output_manager.generate_all_analytics_tables(
                    scores_df=frame, cfg=cfg, sensor_context=sensor_context
                )
                table_count = analytics_result.get("sql_tables", 0)
                Console.info(f"Analytics: tables={table_count}", component="OUTPUTS")

            # === RUL + forecasting ===
            with T.section("outputs.forecasting"):
                forecast_engine = ForecastEngine(
                    sql_client=getattr(output_manager, "sql_client", None),
                    output_manager=output_manager,
                    equip_id=int(equip_id),
                    run_id=str(run_id) if run_id is not None else None,
                    config=cfg,
                    model_state=model_state,
                )
                forecast_results = forecast_engine.run_forecast()
                
                if forecast_results.get('success'):
                    Console.info(
                        f"Forecast: RUL P10/50/90={forecast_results['rul_p10']:.0f}/{forecast_results['rul_p50']:.0f}/{forecast_results['rul_p90']:.0f}h | tables={len(forecast_results['tables_written'])} | top_sensors={forecast_results['top_sensors'][:3]}",
                        component="FORECAST",
                    )
                    # Record RUL metrics for Prometheus.
                    try:
                        record_rul(
                            equip,
                            rul_hours=float(forecast_results['rul_p50']),
                            p10=float(forecast_results['rul_p10']),
                            p50=float(forecast_results['rul_p50']),
                            p90=float(forecast_results['rul_p90']),
                        )
                        if 'active_defects' in forecast_results:
                            record_active_defects(equip, int(forecast_results['active_defects']))
                    except Exception:
                        pass  # OTEL metrics are optional.
                else:
                    Console.warn(
                        f"Forecast failed: {forecast_results.get('error', 'Unknown')}",
                        component="FORECAST", equip=equip, run_id=run_id,
                    )
                    degradations.append("forecast_failed")

            # Memory cleanup: free sensor context after forecasting.
            sensor_context = None
            gc.collect()

            run_completion_time = datetime.now()

        # === SQL-specific artifact writing ===
        # Delegated to output_manager.write_sql_artifacts().
        rows_written = write_sql_artifacts(
            output_manager=output_manager,
            frame=frame,
            episodes=episodes,
            train=train,
            pca_detector=pca_detector,
            sql_client=sql_client,
            run_id=run_id,
            equip_id=equip_id,
            equip=equip,
            cfg=cfg,
            meta=meta,
            win_start=win_start,
            win_end=win_end,
            rows_read=rows_read,
            spe_p95_train=spe_p95_train,
            t2_p95_train=t2_p95_train,
            anomaly_count=anomaly_count,
            T=T,
            culprit_writer_func=write_episode_culprits_enhanced,
        )

        if reuse_models and cache_payload:
            with T.section("sql.cache_detectors"):
                try:
                    joblib.dump(cache_payload, model_cache_path)
                except Exception as e:
                    Console.warn(f"Failed to cache detectors: {e}", component="MODEL",
                                 equip=equip, cache_path=str(model_cache_path), error=str(e))

        # Determine outcome based on degradations.
        if degradations:
            outcome = "DEGRADED"
            err_json = json.dumps({"degraded_steps": degradations[:20]}, ensure_ascii=False)
            Console.warn(f"Run completed with {len(degradations)} degraded step(s): {degradations[:5]}", 
                        component="RUN", equip=equip, run_id=run_id)
        else:
            outcome = "OK"

    except Exception as e:
        # Capture error for finalization (must be 'FAIL' to match Runs table constraint).
        outcome = "FAIL"
        try:
            err_json = json.dumps({"type": e.__class__.__name__, "message": str(e)}, ensure_ascii=False)
        except Exception:
            err_json = '{"type":"Exception","message":"<serialization failed>"}'
        
        # ACM_Runs metadata is written in finally block (includes error_message).
        Console.error(f"Exception: {e}", component="RUN",
                      equip=equip, run_id=run_id, error_type=type(e).__name__, error=str(e)[:500])
        # Re-raise to keep stderr useful for orchestrators.
        raise

    finally:
        # === Perf: log timer stats ===
        # Note: Timer class uses `totals`, not `timings`.
        if 'T' in locals() and hasattr(T, 'totals') and T.totals:
            try:
                # Log a summary of all timed sections (console-only, not to Loki).
                Console.section("Performance Summary")
                total_time = T.totals.get("total_run", 0.0)
                for section, duration in T.totals.items():
                    Console.status(f"{section}: {duration:.4f}s")
                    # Also emit to Loki for Grafana timer panel.
                    pct = (duration / total_time * 100) if total_time > 0 else 0
                    log_timer(section=section, duration_s=duration, pct=pct, total_s=total_time)

            except Exception:
                pass

        if sql_log_sink:
            try:
                Console.remove_sink(sql_log_sink)
                sql_log_sink.close()
            except Exception:
                pass
            sql_log_sink = None
        
        # === Finalize run in SQL ===
        if sql_client and run_id:
            try:
                run_completion_time = datetime.now()
                
                # 1) Extract run metadata from scores.
                if 'frame' in locals() and isinstance(frame, pd.DataFrame) and len(frame) > 0:
                    per_regime_enabled = bool(quality_ok and use_per_regime) if 'quality_ok' in locals() and 'use_per_regime' in locals() else False
                    regime_count = len(set(score_regime_labels)) if 'score_regime_labels' in locals() and score_regime_labels is not None else 0
                    run_metadata = extract_run_metadata_from_scores(frame, per_regime_enabled=per_regime_enabled, regime_count=regime_count)
                    data_quality_score = extract_data_quality_score(
                        data_quality_path=None,
                        sql_client=sql_client,
                        run_id=run_id,
                        equip_id=equip_id if 'equip_id' in locals() else 0,
                    )
                    record_data_quality(equip, float(data_quality_score) if data_quality_score else 0.0)
                else:
                    run_metadata = {"health_status": "UNKNOWN", "avg_health_index": None, "min_health_index": None, "max_fused_z": None}
                    data_quality_score = 0.0
                
                # 2) Write run metadata to ACM_Runs.
                write_run_metadata(
                    sql_client=sql_client,
                    run_id=run_id,
                    equip_id=int(equip_id) if 'equip_id' in locals() else 0,
                    equip_name=equip,
                    started_at=run_start_time,
                    completed_at=run_completion_time,
                    config_signature=config_signature if 'config_signature' in locals() else "UNKNOWN",
                    train_row_count=len(train) if 'train' in locals() and isinstance(train, pd.DataFrame) else 0,
                    score_row_count=len(frame) if 'frame' in locals() and isinstance(frame, pd.DataFrame) else rows_read,
                    episode_count=len(episodes) if 'episodes' in locals() and isinstance(episodes, pd.DataFrame) else 0,
                    health_status=run_metadata.get("health_status", "UNKNOWN"),
                    avg_health_index=run_metadata.get("avg_health_index"),
                    min_health_index=run_metadata.get("min_health_index"),
                    max_fused_z=run_metadata.get("max_fused_z"),
                    data_quality_score=data_quality_score,
                    refit_requested=refit_requested if 'refit_requested' in locals() else False,
                    kept_columns=",".join(getattr(meta, "kept_cols", [])) if 'meta' in locals() else "",
                    error_message=err_json if outcome in ("FAIL", "DEGRADED") else None,
                )
                
                # 3) Finalize run status.
                sql_client.finalize_run(
                    run_id=run_id,
                    outcome=outcome,
                    rows_read=rows_read,
                    rows_written=rows_written,
                    err_json=err_json,
                )
                Console.info(f"Finalized RunID={run_id} outcome={outcome} rows_in={rows_read} rows_out={rows_written}", component="RUN")
                
                # 4) Record OTEL metrics.
                if _OBSERVABILITY_AVAILABLE and run_start_time:
                    duration_seconds = (run_completion_time - run_start_time).total_seconds()
                    record_run(equip, outcome or "OK", duration_seconds)
                    record_batch_processed(equip, rows=rows_read, duration_seconds=duration_seconds, outcome=(outcome or "ok").lower())
                    if run_metadata.get("avg_health_index") is not None:
                        record_health_score(equip, float(run_metadata["avg_health_index"]))
                    if outcome == "FAIL":
                        record_error(equip, str(err_json) if err_json else "Run failed", "RunFailure")
                        
            except Exception as fe:
                Console.error(f"Run finalization failed: {fe}", component="RUN", equip=equip, run_id=run_id)
            finally:
                # Close connections.
                try:
                    if 'output_manager' in locals():
                        output_manager.close()
                except Exception:
                    pass
                try:
                    sql_client.close()
                except Exception:
                    pass
        
        # Close OpenTelemetry root span.
        if _span_ctx is not None:
            try:
                if root_span is not None:
                    root_span.set_attribute("acm.outcome", outcome)
                    root_span.set_attribute("acm.rows_read", rows_read)
                    root_span.set_attribute("acm.rows_written", rows_written)
                _span_ctx.__exit__(None, None, None)
            except Exception:
                pass
        
        # Stop profiling and flush observability.
        if _OBSERVABILITY_AVAILABLE:
            try:
                stop_profiling()
                shutdown_observability()
            except Exception:
                pass

    return


if __name__ == "__main__":
    main()

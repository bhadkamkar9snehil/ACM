# core/acm.py
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
# - Stages: SQL connect   config load   data load   features   models   scoring
#     regimes calibration  fusion  drift  persistence   analytics   forecast.
# - FORECASTING_DISABLED: The forecast/RUL stage is currently commented out.
#   Search for FORECASTING_DISABLED to find all related changes.
# - Output: Writes run artifacts and metrics to SQL via `OutputManager` and
#   emits observability signals when available.
# - Adaptive: Quality-driven model retraining replaces manual ONLINE/OFFLINE modes.
# =============================================================================

# ============================
# Standard library imports
# ============================
import argparse
import time
from datetime import datetime
# NOTE: Parallel fitting via ThreadPoolExecutor was removed due to BLAS/OpenMP
# deadlocks; model fitting is intentionally single-threaded here.
from typing import Any, Callable, Dict, List, Optional

# NOTE: Overflow warnings are not suppressed globally. If they appear, treat
# them as a signal of scaling/unit issues and handle them locally where safe.

# ============================
# Third-party imports
# ============================
import numpy as np
import pandas as pd

from core import regimes, drift, fuse, fast_features

# FORECASTING_DISABLED: Stub so pipeline can import without ForecastEngine.
# Remove this stub when re-enabling forecasting.
ForecastEngine = None

from core.output_manager import OutputManager
from core.run_metadata_writer import (
    finalize_noop_run,
    finalize_pipeline_teardown,
    resolve_run_outcome_from_degradations,
    serialize_run_exception,
)
from core.episode_culprits_writer import write_episode_culprits_enhanced
from core.pipeline_types import (
    run_data_guardrails_safe,
    validate_data_contract_at_entry,
)
from core.seasonality import SeasonalPattern, detect_and_adjust_safe
from core.sensor_attribution import build_sensor_analytics_context
from core.adaptive_thresholds import maybe_update_adaptive_thresholds
from core.smart_coldstart import seed_baseline, load_and_validate_data_stage
from core.detector_orchestrator import (
    score_all_detectors,
    calibrate_all_detectors,
    fit_all_detectors,
    initialize_detectors_for_run,
    compute_stable_feature_hash,
    load_and_rebuild_detectors_from_sql_cache,
    reconcile_detector_flags_with_loaded_models,
)
from core.model_persistence import (
    persist_calibration_params_safe,
    load_manifest_protected_columns,
    restore_detectors_from_runtime_cache,
    load_quality_regime_state_if_needed,
    run_model_persistence_and_lifecycle_stage,
)
from core.model_evaluation import auto_tune_parameters, run_auto_retrain_stage

# Observability: OpenTelemetry + structured logging. Falls back to no-op stubs
# when observability dependencies are unavailable.
try:
    from core.observability import (
        init as init_observability,
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
        close_run_span,
        shutdown_run_observability,
        start_profiling,
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
    def close_run_span(*args, **kwargs): pass
    def shutdown_run_observability(*args, **kwargs): pass
    def start_profiling(): pass

from core.sql_client import (
    SQLClient,
    execute_with_deadlock_retry,
    resolve_equipment_id_required,
    load_config_required_from_sql,
    start_acm_run,
)

# Data utilities: index hygiene and deduplication helpers.
from core.fast_features import ensure_local_index, deduplicate_index, build_features_for_pipeline

# Config utilities: signature and loader helpers.
from utils.config_dict import compute_config_signature

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
    BOOLEAN_ONLY_METRICS,
    load_model_state_safe,
    load_model_state_from_sql,
    update_and_persist_model_lifecycle_safe,
)


def _configure_logging(logging_cfg, args):
    """Apply CLI/config logging overrides and return effective flags."""
    log_file = args.log_file or (logging_cfg or {}).get("file")
    if log_file:
        Console.warn(f"File logging disabled in SQL-only mode (ignoring --log-file={log_file})", component="CONFIG",
                     log_file=str(log_file))


# Backwards-compat breadcrumbs for helpers extracted from this module.
# _compute_config_signature -> utils/config_dict.py::compute_config_signature()
# _ensure_local_index -> core/fast_features.py::ensure_local_index()
# _get_equipment_id -> core/sql_client.py::resolve_equipment_id_required()
# _load_config -> core/sql_client.py::load_config_required_from_sql()
# _sql_start_run -> core/sql_client.py::start_acm_run()


# =======================
# SQL helpers (local)
# Kept here for tight integration with run orchestration.
# =======================
def _continuous_learning_enabled(cfg: Dict[str, Any]) -> bool:
    """Return True if continuous learning is enabled in config."""
    return cfg.get("continuous_learning", {}).get("enabled", False)

def _detect_mode(cfg: Optional[Dict[str, Any]] = None) -> str:
    """
    Backward-compatible runtime mode marker.

    ACM operates in adaptive mode; legacy ONLINE/OFFLINE branches were removed.
    """
    return "adaptive"

# ========================================================================
# Extracted helpers (now owned by dedicated modules)
# ========================================================================
# _sql_finalize_run -> sql_client.py::SQLClient.finalize_run()
# _execute_with_deadlock_retry -> sql_client.py::execute_with_deadlock_retry()
# _get_equipment_id -> sql_client.py::resolve_equipment_id_required()
# _load_config -> sql_client.py::load_config_required_from_sql()
# _sql_start_run -> sql_client.py::start_acm_run()
# _deduplicate_index -> fast_features.py::deduplicate_index()
# _ensure_local_index -> fast_features.py::ensure_local_index()
# _compute_config_signature -> config_dict.py::compute_config_signature()
# _score_all_detectors -> detector_orchestrator.py
# _calibrate_all_detectors -> detector_orchestrator.py
# _fit_all_detectors -> detector_orchestrator.py
# _get_detector_enable_flags -> detector_orchestrator.py
# sensor analytics context -> sensor_attribution.py::build_sensor_analytics_context()
# contribution timeline write -> output_manager.py::write_contribution_timeline_from_frame()
# regime definitions audit write -> regimes.py::write_regime_definitions_for_audit()
# persist.detector_correlation -> output_manager.py::write_detector_correlation_from_scores()
# persist.sensor_correlation -> output_manager.py::write_sensor_correlations_from_raw()
# persist.sensor_normalized_ts -> output_manager.py::write_sensor_normalized_ts_from_raw()
# persist.seasonal_patterns -> output_manager.py::write_seasonal_patterns_from_detected()
# batch summary emit -> run_metadata_writer.py::emit_batch_summary()
# run finalize metadata/status -> run_metadata_writer.py::finalize_run_with_metadata()

# NOTE: safe_step() was removed. Critical phases now fail naturally without
# try/except wrappers. See docs/GhostBusters_1.md for rationale.

"""
-------------------------------------------------------------------------------------------
"""

def build_arg_parser() -> argparse.ArgumentParser:
    """Build ACM CLI argument parser."""
    ap = argparse.ArgumentParser(
        prog="python -m core.acm",
        description="ACM - Automated Condition Monitoring pipeline for equipment health analysis.",
        epilog="""
Examples:
  python -m core.acm --equip FD_FAN --start-time "2023-10-15T00:00:00" --end-time "2023-11-15T00:00:00"
  python -m core.acm --equip GAS_TURBINE --log-level DEBUG

Note: For automated batch processing, use sql_batch_runner.py instead:
  python scripts/sql_batch_runner.py --equip FD_FAN --start-from-beginning
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--equip", required=True, help="Equipment name (e.g., FD_FAN, GAS_TURBINE)")
    ap.add_argument("--force-retrain", action="store_true", help="Force model retraining regardless of quality (for testing/reset)")
    ap.add_argument("--clear-cache", action="store_true", help="Force re-training by deleting the cached model for this equipment.")
    ap.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Override global log level.")
    ap.add_argument("--log-format", choices=["text", "json"], help="Override log output format.")
    ap.add_argument("--log-file", help="Write logs to the specified file.")
    ap.add_argument("--log-module-level", action="append", default=[], metavar="MODULE=LEVEL",
                    help="Set per-module log level overrides (repeatable).")
    ap.add_argument("--start-time", help="Start time for analysis window (ISO format: 2023-10-15T00:00:00)")
    ap.add_argument("--end-time", help="End time for analysis window (ISO format: 2023-11-15T00:00:00)")
    return ap


def run_pipeline(args: argparse.Namespace) -> int:
    """
    Internal callable API for running ACM from a parsed argparse Namespace.

    `core.acm` owns parsing and calls execution directly with Namespace args.
    """
    try:
        main(args)
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1


def main(args: Optional[argparse.Namespace] = None) -> None:
    if args is None:
        ap = build_arg_parser()
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
        cfg = load_config_required_from_sql(sql_client, equipment_name=equip, logger=Console)
        
        # Deep copy config to prevent accidental mutation across phases.
        import copy
        cfg = copy.deepcopy(cfg)
        
        logging_cfg = (cfg.get("logging") or {})
    _configure_logging(logging_cfg, args)

    # Get equipment ID from SQL (already resolved during config loading)
    equip_id = resolve_equipment_id_required(equip, sql_client)
    if not hasattr(cfg, '_equip_id') or cfg._equip_id == 0:
        cfg._equip_id = equip_id
    
    # Compute and store config signature for cache validation.
    config_signature = compute_config_signature(cfg)
    cfg["_signature"] = config_signature

    # Continuous learning is controlled exclusively by config.
    CONTINUOUS_LEARNING = _continuous_learning_enabled(cfg)

    # Continuous learning settings.
    cl_cfg = cfg.get("continuous_learning", {})
    model_update_interval = int(cl_cfg.get("model_update_interval", 1))  # Default: update every batch
    threshold_update_interval = int(cl_cfg.get("threshold_update_interval", 1))  # Default: update every batch

    # v11.8.0: Force retraining only via explicit CLI flag.
    # CONTINUOUS_LEARNING controls quality-based retraining evaluation downstream,
    # not forced retraining every batch.
    force_retraining = bool(getattr(args, "force_retrain", False))
    
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
        with sql_client.get_cursor() as cur:
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
    adaptive_info = f"adaptive | continuous_learning={CONTINUOUS_LEARNING} | force_retrain={force_retraining}"
    intervals_info = f" | intervals=model:{model_update_interval},thresh:{threshold_update_interval}" if CONTINUOUS_LEARNING else ""
    Console.info(f"Run #{run_count + 1} | {equip} | {adaptive_info}{intervals_info}", component="RUN")

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
    regime_quality_ok: bool = True
    refit_requested: bool = False

    # ===== SQL: Start run (window discovery) =====
    # SQL client is already connected at this point.
    run_id: Optional[str] = None
    win_start: Optional[pd.Timestamp] = None
    win_end: Optional[pd.Timestamp] = None
    
    # Track CLI overrides for consolidated logging.
    cli_overrides = []

    # Start the run in SQL.
    run_id, win_start, win_end, equip_id = start_acm_run(
        cli=sql_client,
        cfg=cfg,
        equip_code=equip,
        deadlock_retry_func=execute_with_deadlock_retry,
        logger=Console,
    )
    
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

    model_state = None  # Single source of truth for model lifecycle state.
    
    # Initialize detector-related variables at function scope to avoid fragile
    # 'in dir()' checks throughout the pipeline.
    train: Optional[pd.DataFrame] = None
    col_meds: Optional[pd.Series] = None
    # NOTE: regime_model is declared earlier; avoid redefinition here.
    meta: Optional[Any] = None
    frame: Optional[pd.DataFrame] = None
    episodes: Optional[pd.DataFrame] = None
    score_out: Optional[Dict[str, Any]] = None
    quality_ok: bool = False
    use_per_regime: bool = False
    score_regime_labels: Optional[np.ndarray] = None

    try:
        # ===== Phase 1: Load data from SQL =====
        with T.section("load_data"):
            load_stage = load_and_validate_data_stage(
                sql_client=sql_client,
                equip=equip,
                equip_id=equip_id,
                cfg=cfg,
                args=args,
                output_manager=output_manager,
                win_start=win_start,
                win_end=win_end,
                ensure_local_index_fn=ensure_local_index,
                deduplicate_index_fn=deduplicate_index,
                validate_data_contract_fn=validate_data_contract_at_entry,
                finalize_noop_run_fn=finalize_noop_run,
                record_coldstart_fn=record_coldstart,
                refit_requested=refit_requested,
                run_id=run_id,
                logger=Console,
            )
            if not load_stage.should_continue:
                outcome = "NOOP"
                rows_read = 0
                rows_written = 0
                return
            train = load_stage.train
            score = load_stage.score
            meta = load_stage.meta
            coldstart_complete = load_stage.coldstart_complete

        T.log("data_split_complete", train_rows=train.shape[0], train_cols=train.shape[1], score_rows=score.shape[0], score_cols=score.shape[1])
        
        # ===== Adaptive rolling baseline (cold-start helper) =====
        with T.section("baseline.seed"):
            try:
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
            train, score, seasonal_patterns, seasonal_adjusted = detect_and_adjust_safe(
                train=train,
                score=score,
                cfg=cfg,
                logger=Console,
                equip=equip,
            )

        # ===== Data quality guardrails =====
        low_var_threshold = 1e-4  # Used by feature imputation
        with T.section("data.guardrails"):
            guardrail_result = run_data_guardrails_safe(
                train=train,
                score=score,
                meta=meta,
                cfg=cfg,
                output_manager=output_manager,
                run_id=run_id,
                equip_id=equip_id,
                equip=equip,
                logger=Console,
            )
            low_var_threshold = guardrail_result.low_var_threshold

        # Preserve raw sensor data before feature engineering (needed for regime basis).
        raw_train = train.copy()
        raw_score = score.copy()

        # ===== Feature construction (detectors require engineered features) =====
        with T.section("features.build"):
            train, score = build_features_for_pipeline(train=train, score=score, cfg=cfg, equip=equip)

        # ===== Resolve protected feature columns from cached model manifest =====
        # Do a lightweight SQL manifest-only fetch (no model blobs) so that we
        # know which feature columns the currently-saved detectors were trained on.
        # These columns must survive the low-variance filter below - the
        # baseline-derived train split used in scoring batches can temporarily
        # have near-zero variance for features that were fine at training time,
        # causing a spurious 632 630 mismatch that forces a full retrain every
        # scoring batch.  Full model objects are still loaded later in
        # models.load as normal.
        _manifest_protected_columns = load_manifest_protected_columns(
            sql_client=sql_client,
            equip=equip,
            equip_id=equip_id,
            cfg=cfg,
            is_coldstart_run=bool(
                meta.get("is_coldstart_run", False)
                if isinstance(meta, dict)
                else getattr(meta, "is_coldstart_run", False)
            ),
            logger=Console,
        )

        # ===== Impute missing values in feature space (detectors require clean data) =====
        with T.section("features.impute"):
            train, score, _ = fast_features.impute_features(
                train, score, low_var_threshold, output_manager, run_id, equip_id, equip,
                protected_columns=_manifest_protected_columns,
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
        regime_loaded_from_state = False
        col_meds = None
        cached_models = None
        cached_manifest = None
        previous_weights = None  # Initialize for fusion pipeline.
        cached_calibration_params = None

        def _fit_all_detectors_with_timer(**kwargs: Any) -> Dict[str, Any]:
            with T.section("train.detector_fit"):
                return fit_all_detectors(**kwargs)

        with T.section("models.load"):
            detector_init = initialize_detectors_for_run(
                train=train,
                score=score,
                cfg=cfg,
                meta=meta,
                detector_cache=detector_cache,
                output_manager=output_manager,
                sql_client=sql_client,
                run_id=run_id,
                equip_id=equip_id,
                equip=equip,
                load_and_rebuild_detectors_fn=load_and_rebuild_detectors_from_sql_cache,
                restore_detectors_from_runtime_cache_fn=restore_detectors_from_runtime_cache,
                load_quality_regime_state_if_needed_fn=load_quality_regime_state_if_needed,
                fit_all_detectors_fn=_fit_all_detectors_with_timer,
                reconcile_detector_flags_fn=reconcile_detector_flags_with_loaded_models,
                logger=Console,
            )

        train = detector_init["train"]
        score = detector_init["score"]
        det_flags = detector_init["det_flags"]
        ar1_enabled = detector_init["ar1_enabled"]
        pca_enabled = detector_init["pca_enabled"]
        iforest_enabled = detector_init["iforest_enabled"]
        gmm_enabled = detector_init["gmm_enabled"]
        omr_enabled = detector_init["omr_enabled"]
        ar1_detector = detector_init["ar1_detector"]
        pca_detector = detector_init["pca_detector"]
        iforest_detector = detector_init["iforest_detector"]
        gmm_detector = detector_init["gmm_detector"]
        omr_detector = detector_init["omr_detector"]
        pca_train_spe = detector_init["pca_train_spe"]
        pca_train_t2 = detector_init["pca_train_t2"]
        regime_model = detector_init["regime_model"]
        regime_state = detector_init["regime_state"]
        regime_state_version = detector_init["regime_state_version"]
        regime_loaded_from_state = detector_init["regime_loaded_from_state"]
        col_meds = detector_init["col_meds"]
        cached_models = detector_init["cached_models"]
        cached_manifest = detector_init["cached_manifest"]
        cached_calibration_params = detector_init["cached_calibration_params"]
        detectors_just_trained = detector_init["detectors_just_trained"]
        use_cache = detector_init["use_cache"]

        # ===== Phase 3: Build regime feature basis (required for labeling) =====
        regime_basis_result = regimes.build_regime_feature_basis_stage(
            train_features=train,
            score_features=score,
            raw_train=raw_train,
            raw_score=raw_score,
            pca_detector=pca_detector,
            cfg=cfg,
            regime_model=regime_model,
            equip=equip,
            logger=Console,
        )
        regime_basis_train = regime_basis_result.regime_basis_train
        regime_basis_score = regime_basis_result.regime_basis_score
        regime_basis_meta = regime_basis_result.regime_basis_meta
        regime_basis_hash = regime_basis_result.regime_basis_hash
        regime_model = regime_basis_result.regime_model
        if regime_basis_result.degraded:
            degradations.append("regime_feature_basis")

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
        
        # v11.4.0: Load model maturity state BEFORE regimes to control discovery
        # v11.5.0: Override maturity to LEARNING if refit was requested (models just retrained)
        current_model_maturity: Optional[str] = None
        if sql_client and equip_id:
            early_model_state = load_model_state_from_sql(sql_client, equip_id)
            if early_model_state is not None:
                current_model_maturity = early_model_state.maturity.value
                Console.info(f"Model maturity: {current_model_maturity}", component="LIFECYCLE")
        
        # v11.5.0 FIX: If refit was requested, detectors were retrained - must allow regime rediscovery
        # Otherwise CONVERGED state blocks regime discovery but cached regime model is stale/missing
        if refit_requested and current_model_maturity == "CONVERGED":
            Console.info(
                "Refit requested with CONVERGED state - overriding to LEARNING to allow regime rediscovery",
                component="LIFECYCLE"
            )
            current_model_maturity = "LEARNING"
        
        with T.section("regimes.label"):
            regime_labeling_result = regimes.run_regime_labeling_stage(
                score_df=score,
                frame=frame,
                train_df=train,
                cfg=cfg,
                regime_basis_train=regime_basis_train,
                regime_basis_score=regime_basis_score,
                regime_basis_meta=regime_basis_meta,
                regime_basis_hash=regime_basis_hash,
                regime_model=regime_model,
                regime_loaded_from_state=regime_loaded_from_state,
                regime_state=regime_state,
                regime_state_version=regime_state_version,
                raw_train=raw_train,
                output_manager=output_manager,
                current_model_maturity=current_model_maturity,
                equip=equip,
                equip_id=equip_id,
                sql_client=sql_client,
                logger=Console,
                record_regime_fn=record_regime,
            )

            frame = regime_labeling_result.frame
            regime_out = regime_labeling_result.score_out
            regime_model = regime_labeling_result.regime_model
            train_regime_labels = regime_labeling_result.train_regime_labels
            score_regime_labels = regime_labeling_result.score_regime_labels
            regime_quality_ok = regime_labeling_result.regime_quality_ok
            regime_state_version = regime_labeling_result.regime_state_version
            regime_loaded_from_state = regime_labeling_result.regime_loaded_from_state
        
        score_out = regime_out
        regime_quality_ok = bool(regime_out.get("regime_quality_ok", True))

        # ===== Regime occupancy and transitions =====
        with T.section("regimes.occupancy"):
            occupancy_count, transition_count = regimes.write_regime_occupancy_and_transitions(
                score_regime_labels=score_regime_labels,
                frame=frame,
                output_manager=output_manager,
                logger=Console,
                equip=equip,
            )

        # ===== Model quality assessment: check if retraining is needed =====
        # Runs after first scoring so cached model performance can be evaluated.
        # v11.7.0 ADAPTIVE LEARNING: Always assess quality (no mode guard)
        # Quality-driven retraining happens automatically when triggers fire
        force_retrain = False
        with T.section("models.auto_retrain"):
            retrain_out = run_auto_retrain_stage(
                cfg=cfg,
                cached_models=cached_models,
                cached_manifest=cached_manifest,
                detectors_just_trained=detectors_just_trained,
                score_out=score_out if isinstance(score_out, dict) else {},
                regime_quality_ok=regime_quality_ok,
                current_model_maturity=current_model_maturity,
                boolean_only_metrics=list(BOOLEAN_ONLY_METRICS),
                equip=equip,
                logger=Console,
                record_model_refit_fn=record_model_refit,
                fit_all_detectors_fn=fit_all_detectors,
                train=train,
                det_flags=det_flags,
                output_manager=output_manager,
                sql_client=sql_client,
                run_id=run_id,
                equip_id=equip_id,
                regime_model=regime_model,
                detectors={
                    "ar1_detector": ar1_detector,
                    "pca_detector": pca_detector,
                    "iforest_detector": iforest_detector,
                    "gmm_detector": gmm_detector,
                    "omr_detector": omr_detector,
                    "pca_train_spe": pca_train_spe,
                    "pca_train_t2": pca_train_t2,
                },
            )
            force_retrain = bool(retrain_out["force_retrain"])
            cached_models = retrain_out["cached_models"]
            regime_model = retrain_out["regime_model"]
            detectors_after_retrain = retrain_out["detectors"]
            ar1_detector = detectors_after_retrain["ar1_detector"]
            pca_detector = detectors_after_retrain["pca_detector"]
            iforest_detector = detectors_after_retrain["iforest_detector"]
            gmm_detector = detectors_after_retrain["gmm_detector"]
            omr_detector = detectors_after_retrain["omr_detector"]
            pca_train_spe = detectors_after_retrain["pca_train_spe"]
            pca_train_t2 = detectors_after_retrain["pca_train_t2"]

        # ===== Model persistence: save trained models with versioning =====
        with T.section("models.persistence.save"):
            persistence_out = run_model_persistence_and_lifecycle_stage(
                cached_models=cached_models,
                detector_cache=detector_cache,
                force_retrain=force_retrain,
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
                col_meds=col_meds,
                regime_quality_ok=regime_quality_ok,
                timing_sections=T.timings if hasattr(T, "timings") else None,
                run_id=run_id,
                model_state=model_state,
                output_manager=output_manager,
                regime_state_version=regime_state_version,
                score_out=score_out if isinstance(score_out, dict) else {},
                update_and_persist_model_lifecycle_fn=update_and_persist_model_lifecycle_safe,
                load_model_state_safe_fn=load_model_state_safe,
                logger=Console,
            )
        detectors_fitted_this_run = persistence_out["detectors_fitted_this_run"]
        models_were_trained = persistence_out["models_were_trained"]
        saved_model_version = persistence_out["saved_model_version"]
        model_state = persistence_out["model_state"]

        # ===== Phase 6: Calibration (z-score normalization) =====
        # Fit calibrators on TRAIN data, transform SCORE data.
        # v11.3.3: Now includes contamination filtering for robust calibration.
        with T.section("calibrate"):
            calibration_result = fuse.run_calibration_stage(
                train=train,
                frame=frame,
                cfg=cfg,
                regime_quality_ok=regime_quality_ok,
                train_regime_labels=train_regime_labels,
                score_regime_labels=score_regime_labels,
                pca_train_spe=pca_train_spe,
                pca_train_t2=pca_train_t2,
                detectors={
                    "ar1_detector": ar1_detector,
                    "pca_detector": pca_detector,
                    "iforest_detector": iforest_detector,
                    "gmm_detector": gmm_detector,
                    "omr_detector": omr_detector,
                },
                detector_flags={
                    "ar1_enabled": ar1_enabled,
                    "pca_enabled": pca_enabled,
                    "iforest_enabled": iforest_enabled,
                    "gmm_enabled": gmm_enabled,
                    "omr_enabled": omr_enabled,
                },
                cached_calibration_params=cached_calibration_params,
                saved_model_version=saved_model_version,
                score_all_detectors_fn=score_all_detectors,
                calibrate_all_detectors_fn=calibrate_all_detectors,
                persist_calibration_params_fn=lambda version, calibrators_dict: persist_calibration_params_safe(
                    equip=equip,
                    sql_client=sql_client,
                    equip_id=equip_id,
                    saved_model_version=version,
                    calibrators_dict=calibrators_dict,
                    logger=Console,
                ),
                output_manager=output_manager,
                logger=Console,
                equip=equip,
            )
            frame = calibration_result.frame
            train_frame = calibration_result.train_frame
            spe_p95_train = calibration_result.spe_p95_train
            t2_p95_train = calibration_result.t2_p95_train
            quality_ok = calibration_result.quality_ok
            use_per_regime = calibration_result.use_per_regime

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
                omr_contributions=omr_contributions_data,
                equip=equip,
            )

            frame, train_frame, episodes, fusion_weights_used = fuse.apply_fusion_result_and_record_metrics(
                frame=frame,
                train_frame=train_frame,
                fusion_result=fusion_result,
                equip=equip,
                record_detector_scores_fn=record_detector_scores,
                record_episode_fn=record_episode,
            )

        # ===== Adaptive thresholds =====
        with T.section("thresholds.adaptive"):
            maybe_update_adaptive_thresholds(
                train_frame=train_frame,
                train_data=train,
                cfg=cfg,
                equip_id=equip_id,
                output_manager=output_manager,
                coldstart_complete=coldstart_complete,
                continuous_learning=CONTINUOUS_LEARNING,
                threshold_update_interval=threshold_update_interval,
                regime_quality_ok=regime_quality_ok,
                logger=Console,
            )

        # Regime health labeling and transient detection.
        regime_stats: Dict[int, Dict[str, float]] = {}
        transient_counts: Dict[str, int] = {}
        frame, regime_stats = regimes.apply_regime_health_labels(
            frame=frame,
            regime_model=regime_model,
            regime_quality_ok=regime_quality_ok,
            cfg=cfg,
            output_manager=output_manager,
            logger=Console,
        )
        
        # Transient state detection.
        with T.section("regimes.transient_detection"):
            frame, transient_counts = regimes.apply_transient_state_labels(
                frame=frame,
                score_data=score,  # Use original score data for ROC calculation.
                cfg=cfg,
                logger=Console,
            )
        
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
            cached_manifest=cached_manifest,
        )

        # ===== Phase 8: Drift =====
        with T.section("drift"):
            drift_out = drift.run_drift_pipeline(
                score_data=score,
                frame=frame,
                score_out=score_out,
                cfg=cfg,
                regime_quality_ok=regime_quality_ok,
                equip=equip,
                sql_client=sql_client,
                equip_id=equip_id,
                output_manager=output_manager,
                logger=Console,
            )
            frame = drift_out["frame"]
            score_out = drift_out["score_out"]

        # Normalize episodes schema for report/export.
        episodes, frame = fuse.normalize_episodes_schema(
            episodes=episodes,
            frame=frame,
            equip=equip,
        )

        # ===== Rolling baseline buffer: update with latest raw SCORE =====
        with T.section("baseline.buffer_write"):
            if raw_score is not None:
                output_manager.update_baseline_buffer(
                    score_numeric=raw_score,
                    cfg=cfg,
                    coldstart_complete=coldstart_complete,
                )

        sensor_context: Optional[Dict[str, Any]] = None
        with T.section("sensor.context"):
            sensor_context = build_sensor_analytics_context(
                raw_train=raw_train,
                raw_score=raw_score,
                frame=frame,
                omr_contributions_data=omr_contributions_data,
                regime_model=regime_model,
                logger=Console,
                equip=equip,
            )

        # ===== Contribution timeline =====
        with T.section("contribution.timeline"):
            output_manager.write_contribution_timeline_from_frame(
                frame=frame,
                fusion_weights=fusion_weights_used,
                equip=equip,
            )

        # ===== Phase 9: Persist artifacts / finalize (SQL-only) =====
        rows_read = int(score.shape[0])
        anomaly_count = int(len(episodes))
        
        # `degradations` is tracked throughout the pipeline for final outcome.
        
        # SQL-only persistence.
        with T.section("persist"):
          with output_manager.batched_transaction():
            # Core + optional outputs, memory release, and analytics generation.
            with T.section("persist.pipeline_outputs"):
                persist_result = output_manager.persist_pipeline_outputs(
                    scores_df=frame,
                    episodes_df=episodes,
                    raw_train=raw_train,
                    raw_score=raw_score,
                    iforest_detector=iforest_detector,
                    omr_detector=omr_detector,
                    seasonal_patterns=seasonal_patterns,
                    cfg=cfg,
                    sensor_context=sensor_context,
                    fusion_weights_used=fusion_weights_used,
                    record_episode_fn=record_episode,
                    equip=equip,
                    max_total_rows=10000,
                )
                rows_written += persist_result.rows_written_delta
                raw_train = persist_result.raw_train
                raw_score = persist_result.raw_score
                sensor_context = persist_result.sensor_context
                Console.info(
                    f"Analytics: tables={persist_result.analytics_table_count}",
                    component="OUTPUTS",
                )

            # FORECASTING_DISABLED:
            # Forecast and RUL pipeline is intentionally disabled in current runtime.
            # Re-enable by restoring ForecastEngine import/stub wiring and forecasting stage.

            Console.info("Forecasting/RUL is disabled (FORECASTING_DISABLED).", component="FORECAST")

            run_completion_time = datetime.now()

        # === SQL-specific artifact writing ===
        rows_written = output_manager.write_sql_artifacts_for_run(
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

        # Determine outcome based on degradations.
        outcome, degraded_err_json = resolve_run_outcome_from_degradations(degradations)
        if outcome == "DEGRADED":
            err_json = degraded_err_json
            Console.warn(
                f"Run completed with {len(degradations)} degraded step(s): {degradations[:5]}",
                component="RUN",
                equip=equip,
                run_id=run_id,
            )

    except Exception as e:
        # Capture error for finalization (must be 'FAIL' to match Runs table constraint).
        outcome = "FAIL"
        err_json = serialize_run_exception(e)
        
        # ACM_Runs metadata is written in finally block (includes error_message).
        Console.error(f"Exception: {e}", component="RUN",
                      equip=equip, run_id=run_id, error_type=type(e).__name__, error=str(e)[:500])
        # Re-raise to keep stderr useful for orchestrators.
        raise

    finally:
        finalize_pipeline_teardown(
            console=Console,
            equip=equip,
            run_id=run_id,
            win_start=win_start,
            win_end=win_end,
            outcome=outcome,
            frame=frame if isinstance(frame, pd.DataFrame) else None,
            episodes=episodes if isinstance(episodes, pd.DataFrame) else None,
            score_out=score_out if isinstance(score_out, dict) else None,
            regime_quality_ok=regime_quality_ok,
            model_state=model_state,
            rows_read=rows_read,
            train=train if isinstance(train, pd.DataFrame) else None,
            degradations=degradations,
            refit_requested=refit_requested,
            timer=T,
            sql_client=sql_client,
            output_manager=output_manager,
            equip_id=int(equip_id),
            equip_name=equip,
            started_at=run_start_time,
            rows_written=rows_written,
            err_json=err_json,
            meta=meta,
            config_signature=config_signature,
            per_regime_enabled=bool(quality_ok and use_per_regime),
            regime_count=len(set(score_regime_labels)) if score_regime_labels is not None else 0,
            observability_enabled=_OBSERVABILITY_AVAILABLE,
            record_data_quality_fn=record_data_quality,
            record_run_fn=record_run,
            record_batch_processed_fn=record_batch_processed,
            record_health_score_fn=record_health_score,
            record_error_fn=record_error,
            span_ctx=_span_ctx,
            root_span=root_span,
            close_run_span_fn=close_run_span,
            shutdown_run_observability_fn=shutdown_run_observability,
        )

    return


if __name__ == "__main__":
    main()



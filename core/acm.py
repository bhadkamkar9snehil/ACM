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
from datetime import datetime
# NOTE: Parallel fitting via ThreadPoolExecutor was removed due to BLAS/OpenMP
# deadlocks; model fitting is intentionally single-threaded here.
from typing import Any, Dict, List, Optional

# NOTE: Overflow warnings are not suppressed globally. If they appear, treat
# them as a signal of scaling/unit issues and handle them locally where safe.

# ============================
# Third-party imports
# ============================
import numpy as np
import pandas as pd

from core import regimes, drift, fuse, fast_features

from core.output_manager import OutputManager
from core.run_metadata_writer import (
    PipelineTeardownState,
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
from core.seasonality import detect_and_adjust_safe
from core.sensor_attribution import build_sensor_analytics_context
from core.adaptive_thresholds import maybe_update_adaptive_thresholds
from core.smart_coldstart import seed_baseline_safe, load_and_validate_data_stage
from core.detector_orchestrator import (
    score_all_detectors,
    calibrate_all_detectors,
    fit_all_detectors,
    initialize_detectors_for_run,
    load_and_rebuild_detectors_from_sql_cache,
    reconcile_detector_flags_with_loaded_models,
)
from core.model_persistence import (
    persist_calibration_params_safe,
    load_manifest_protected_columns,
    restore_detectors_from_runtime_cache,
    load_quality_regime_state_if_needed,
    run_model_adaptation_and_persistence_stage,
    run_model_persistence_and_lifecycle_stage,
)
from core.model_evaluation import auto_tune_parameters, run_auto_retrain_stage

from core.observability import (
    init as init_observability,
    get_tracer,
    set_context as set_acm_context,
    Console,
    record_batch_processed,
    record_health_score,
    record_episode,
    record_error,
    record_coldstart,
    record_run,
    record_detector_scores,
    record_regime,
    record_data_quality,
    record_model_refit,
    close_run_span,
    shutdown_run_observability,
    start_profiling,
)
_OBSERVABILITY_AVAILABLE = True

from core.sql_client import (
    execute_with_deadlock_retry,
    connect_acm_sql,
    bootstrap_acm_run_state,
)

# Data utilities: index hygiene and deduplication helpers.
from core.fast_features import ensure_local_index, deduplicate_index

from utils.timer import Timer, enable_timer_metrics  # type: ignore
from core.resource_monitor import enable_resource_metrics


# Console from observability (backwards compatible). Do not reimport here to
# preserve the fallback mechanism when observability is unavailable.

# Model lifecycle management (maturity, promotion, and active model tracking).
from core.model_lifecycle import (
    BOOLEAN_ONLY_METRICS,
    load_model_state_safe,
    resolve_maturity_for_regime_stage,
    update_and_persist_model_lifecycle_safe,
)


def _configure_logging(logging_cfg, args):
    """Apply CLI/config logging overrides and return effective flags."""
    log_file = args.log_file or (logging_cfg or {}).get("file")
    if log_file:
        Console.warn(f"File logging disabled in SQL-only mode (ignoring --log-file={log_file})", component="CONFIG",
                     log_file=str(log_file))


# Backwards-compat breadcrumbs for helpers extracted from this module.
# _ensure_local_index -> core/fast_features.py::ensure_local_index()
# bootstrap run state -> core/sql_client.py::bootstrap_acm_run_state()


# ========================================================================
# Extracted helpers (now owned by dedicated modules)
# ========================================================================
# _sql_finalize_run -> sql_client.py::SQLClient.finalize_run()
# _execute_with_deadlock_retry -> sql_client.py::execute_with_deadlock_retry()
# _deduplicate_index -> fast_features.py::deduplicate_index()
# _ensure_local_index -> fast_features.py::ensure_local_index()
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

    # Enable OTEL metrics for Timer and ResourceMonitor.
    enable_timer_metrics(equip)
    enable_resource_metrics(equip)

    # ========================================================================
    # Fail-fast SQL connect: ACM is SQL-only and must abort if SQL is down.
    # ========================================================================
    Console.info("Connecting to SQL Server...", component="SQL")
    try:
        sql_client = connect_acm_sql(cfg={}, logger=Console)
        Console.ok("SQL connection established", component="SQL")
    except Exception as e:
        Console.error(f"SQL connection failed: {e}", component="SQL",
                      error_type=type(e).__name__, error=str(e)[:500])
        Console.error("Check configs/sql_connection.ini and ensure SQL Server is running.", component="SQL")
        raise SystemExit(1)

    with T.section("startup"):
        bootstrap = bootstrap_acm_run_state(
            sql_client=sql_client,
            equip=equip,
            args=args,
            deadlock_retry_func=execute_with_deadlock_retry,
            logger=Console,
        )
    cfg = bootstrap.cfg
    equip_id = bootstrap.equip_id
    config_signature = bootstrap.config_signature
    run_count = bootstrap.run_count
    run_id = bootstrap.run_id
    win_start = bootstrap.win_start
    win_end = bootstrap.win_end
    cli_overrides = bootstrap.cli_overrides

    logging_cfg = cfg.get("logging") or {}
    _configure_logging(logging_cfg, args)

    # Continuous learning is a core ACM capability and always enabled.
    CONTINUOUS_LEARNING = True

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
    
    # Consolidated startup log.
    continuous_learning_str = "true" if CONTINUOUS_LEARNING else "false"
    force_retrain_str = "true" if force_retraining else "false"
    intervals_info = f"model:{model_update_interval},thresh:{threshold_update_interval}"
    Console.info(
        f"Run #{run_count + 1} | equip={equip} mode=adaptive "
        f"continuous_learning={continuous_learning_str} force_retrain={force_retrain_str} "
        f"intervals={intervals_info}",
        component="RUN",
    )

    # Initialize cross-phase state variables.
    detector_cache: Optional[Dict[str, Any]] = None
    regime_model: Optional[regimes.RegimeModel] = None
    raw_train: Optional[pd.DataFrame] = None
    raw_score: Optional[pd.DataFrame] = None
    regime_quality_ok: bool = True
    refit_requested: bool = False

    # Update observability context with run_id for trace/metric/log tagging.
    set_acm_context(run_id=run_id, equip_id=equip_id)

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

        if train is None or score is None:
            raise RuntimeError("Load stage returned no train/score data with should_continue=True")
        T.log("data_split_complete", train_rows=train.shape[0], train_cols=train.shape[1], score_rows=score.shape[0], score_cols=score.shape[1])
        
        # ===== Adaptive rolling baseline (cold-start helper) =====
        with T.section("baseline.seed"):
            train, score, _ = seed_baseline_safe(
                train=train.copy(),
                score=score.copy(),
                sql_client=sql_client,
                equip_id=equip_id,
                cfg=cfg,
                equip=equip,
                is_coldstart=coldstart_complete,
                ensure_local_index_fn=ensure_local_index,
                logger=Console,
            )

        # ===== Feature preparation =====
        feature_stage = fast_features.run_feature_preparation_stage(
            train=train,
            score=score,
            cfg=cfg,
            meta=meta,
            output_manager=output_manager,
            sql_client=sql_client,
            run_id=run_id,
            equip_id=equip_id,
            equip=equip,
            section_fn=T.section,
            detect_and_adjust_fn=detect_and_adjust_safe,
            run_data_guardrails_fn=run_data_guardrails_safe,
            load_manifest_protected_columns_fn=load_manifest_protected_columns,
        )
        train = feature_stage.train
        score = feature_stage.score
        raw_train = feature_stage.raw_train
        raw_score = feature_stage.raw_score
        seasonal_patterns = feature_stage.seasonal_patterns
        refit_requested = feature_stage.refit_requested

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

        train = detector_init.train
        score = detector_init.score
        det_flags = detector_init.det_flags
        ar1_enabled = detector_init.ar1_enabled
        pca_enabled = detector_init.pca_enabled
        iforest_enabled = detector_init.iforest_enabled
        gmm_enabled = detector_init.gmm_enabled
        omr_enabled = detector_init.omr_enabled
        ar1_detector = detector_init.ar1_detector
        pca_detector = detector_init.pca_detector
        iforest_detector = detector_init.iforest_detector
        gmm_detector = detector_init.gmm_detector
        omr_detector = detector_init.omr_detector
        pca_train_spe = detector_init.pca_train_spe
        pca_train_t2 = detector_init.pca_train_t2
        regime_model = detector_init.regime_model
        regime_state = detector_init.regime_state
        regime_state_version = detector_init.regime_state_version
        regime_loaded_from_state = detector_init.regime_loaded_from_state
        col_meds = detector_init.col_meds
        cached_models = detector_init.cached_models
        cached_manifest = detector_init.cached_manifest
        cached_calibration_params = detector_init.cached_calibration_params
        detectors_just_trained = detector_init.detectors_just_trained

        # ===== Phase 3-5: Regime basis + detector scoring + regime labeling =====
        scoring_regime_stage = regimes.run_scoring_regime_stage(
            train_df=train,
            score_df=score,
            raw_train=raw_train,
            raw_score=raw_score,
            cfg=cfg,
            pca_detector=pca_detector,
            regime_model=regime_model,
            regime_state=regime_state,
            regime_state_version=regime_state_version,
            regime_loaded_from_state=regime_loaded_from_state,
            det_flags=det_flags,
            detectors={
                "ar1_detector": ar1_detector,
                "pca_detector": pca_detector,
                "iforest_detector": iforest_detector,
                "gmm_detector": gmm_detector,
                "omr_detector": omr_detector,
            },
            equip=equip,
            equip_id=equip_id,
            sql_client=sql_client,
            output_manager=output_manager,
            refit_requested=refit_requested,
            section_fn=T.section,
            score_all_detectors_fn=score_all_detectors,
            resolve_maturity_for_regime_stage_fn=resolve_maturity_for_regime_stage,
            record_regime_fn=record_regime,
            logger=Console,
        )
        frame = scoring_regime_stage.frame
        omr_contributions_data = scoring_regime_stage.omr_contributions_data
        score_out = scoring_regime_stage.score_out
        regime_model = scoring_regime_stage.regime_model
        train_regime_labels = scoring_regime_stage.train_regime_labels
        score_regime_labels = scoring_regime_stage.score_regime_labels
        regime_quality_ok = scoring_regime_stage.regime_quality_ok
        regime_state_version = scoring_regime_stage.regime_state_version
        regime_loaded_from_state = scoring_regime_stage.regime_loaded_from_state
        current_model_maturity = scoring_regime_stage.current_model_maturity
        if scoring_regime_stage.degraded_regime_basis:
            degradations.append("regime_feature_basis")

        # ===== Model adaptation + persistence =====
        model_stage = run_model_adaptation_and_persistence_stage(
            section_fn=T.section,
            run_auto_retrain_stage_fn=run_auto_retrain_stage,
            run_model_persistence_and_lifecycle_stage_fn=run_model_persistence_and_lifecycle_stage,
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
            detector_cache=detector_cache,
            col_meds=col_meds,
            timing_sections=T.timings if hasattr(T, "timings") else None,
            model_state=model_state,
            regime_state_version=regime_state_version,
            update_and_persist_model_lifecycle_fn=update_and_persist_model_lifecycle_safe,
            load_model_state_safe_fn=load_model_state_safe,
        )
        cached_models = model_stage.cached_models
        regime_model = model_stage.regime_model
        detectors_after_stage = model_stage.detectors
        ar1_detector = detectors_after_stage["ar1_detector"]
        pca_detector = detectors_after_stage["pca_detector"]
        iforest_detector = detectors_after_stage["iforest_detector"]
        gmm_detector = detectors_after_stage["gmm_detector"]
        omr_detector = detectors_after_stage["omr_detector"]
        pca_train_spe = detectors_after_stage["pca_train_spe"]
        pca_train_t2 = detectors_after_stage["pca_train_t2"]
        saved_model_version = model_stage.saved_model_version
        model_state = model_stage.model_state

        # ===== Phase 6-7 + adaptive postprocess =====
        health_stage = fuse.run_health_stage(
            section_fn=T.section,
            train=train,
            score=score,
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
            previous_weights=previous_weights,
            omr_contributions_data=omr_contributions_data,
            record_detector_scores_fn=record_detector_scores,
            record_episode_fn=record_episode,
            maybe_update_adaptive_thresholds_fn=maybe_update_adaptive_thresholds,
            coldstart_complete=coldstart_complete,
            continuous_learning=CONTINUOUS_LEARNING,
            threshold_update_interval=threshold_update_interval,
            equip_id=equip_id,
            run_regime_postprocess_stage_fn=regimes.run_regime_postprocess_stage,
            regime_model=regime_model,
            auto_tune_parameters_fn=auto_tune_parameters,
            score_out=score_out,
            sql_client=sql_client,
            run_id=run_id,
            cached_manifest=cached_manifest,
        )
        frame = health_stage.frame
        train_frame = health_stage.train_frame
        episodes = health_stage.episodes
        fusion_weights_used = health_stage.fusion_weights_used
        spe_p95_train = health_stage.spe_p95_train
        t2_p95_train = health_stage.t2_p95_train
        quality_ok = health_stage.quality_ok
        use_per_regime = health_stage.use_per_regime

        # ===== Phase 8: Drift + episode schema normalization =====
        drift_stage = drift.run_drift_postprocess_stage(
            section_fn=T.section,
            score_data=score,
            frame=frame,
            score_out=score_out,
            episodes=episodes,
            cfg=cfg,
            regime_quality_ok=regime_quality_ok,
            equip=equip,
            sql_client=sql_client,
            equip_id=equip_id,
            output_manager=output_manager,
            logger=Console,
            normalize_episodes_schema_fn=fuse.normalize_episodes_schema,
        )
        frame = drift_stage.frame
        score_out = drift_stage.score_out
        episodes = drift_stage.episodes

        prep_inputs = output_manager.prepare_persistence_inputs(
            section_fn=T.section,
            raw_train=raw_train,
            raw_score=raw_score,
            frame=frame,
            omr_contributions_data=omr_contributions_data,
            regime_model=regime_model,
            cfg=cfg,
            coldstart_complete=coldstart_complete,
            build_sensor_analytics_context_fn=build_sensor_analytics_context,
            logger=Console,
            equip=equip,
        )
        sensor_context: Optional[Dict[str, Any]] = prep_inputs.sensor_context

        # ===== Phase 9: Persist artifacts / finalize (SQL-only) =====
        rows_read = int(score.shape[0])
        anomaly_count = int(len(episodes))

        persist_stage = output_manager.run_persistence_stage(
            section_fn=T.section,
            logger=Console,
            scores_df=frame,
            episodes_df=episodes,
            train_df=train,
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
            pca_detector=pca_detector,
            sql_client=sql_client,
            run_id=run_id,
            equip_id=equip_id,
            meta=meta,
            win_start=win_start,
            win_end=win_end,
            rows_read=rows_read,
            spe_p95_train=spe_p95_train,
            t2_p95_train=t2_p95_train,
            anomaly_count=anomaly_count,
            timer=T,
            culprit_writer_func=write_episode_culprits_enhanced,
            max_total_rows=10000,
        )
        rows_written = persist_stage.rows_written
        raw_train = persist_stage.raw_train
        raw_score = persist_stage.raw_score
        sensor_context = persist_stage.sensor_context

        # FORECASTING_DISABLED:
        # Forecast and RUL pipeline is intentionally disabled in current runtime.
        # Re-enable by restoring ForecastEngine import/stub wiring and forecasting stage.
        Console.info("Forecasting/RUL is disabled (FORECASTING_DISABLED).", component="FORECAST")

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
            PipelineTeardownState(
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
        )

    return


if __name__ == "__main__":
    main()



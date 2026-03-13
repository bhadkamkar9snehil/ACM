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
from dataclasses import dataclass
from functools import partial
from datetime import datetime
# NOTE: Parallel fitting via ThreadPoolExecutor was removed due to BLAS/OpenMP
# deadlocks; model fitting is intentionally single-threaded here.
from typing import Any, Dict, List, Optional, Tuple

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
    build_representation_run_status,
    build_zero_day_run_status,
    finalize_noop_run,
    finalize_pipeline_teardown,
    resolve_run_outcome_from_degradations,
    serialize_run_exception,
    zero_day_status_from_noop_reason,
)
from core.episode_culprits_writer import write_episode_culprits_enhanced
from core.pipeline_types import (
    run_data_guardrails_safe,
    validate_data_contract_at_entry,
)
from core.seasonality import detect_and_adjust_safe
from core.sensor_attribution import build_sensor_analytics_context
from core.adaptive_thresholds import maybe_update_adaptive_thresholds
from core.smart_coldstart import load_and_validate_data_stage
from core.baseline_governor import seed_baseline_safe
from core.ewm_baseline import EWMBaselineManager
from core.regime_binner import OnlinePCABinner
from core.detector_orchestrator import (
    load_cached_regime_preview_from_sql_cache,
    score_all_detectors,
    fit_all_detectors,
    run_detector_initialization_stage,
)
from core.model_persistence import (
    ModelAdaptationPersistenceResult,
    load_cached_feature_medians,
    load_cached_raw_signal_medians,
    load_quality_regime_state_if_needed,
    persist_calibration_params_safe,
    load_manifest_protected_columns,
    run_model_adaptation_and_persistence_stage,
)

from core.observability import (
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
    start_run_span,
    shutdown_run_observability,
    init_run_observability,
    set_sql_log_client,
)

from core.sql_client import (
    bootstrap_acm_run_state,
    connect_acm_sql_failfast,
    resolve_runtime_policy,
)
from core.representation_pipeline import (
    apply_representation_authority,
    refresh_representation_runtime_authority,
    resolve_representation_authority_policy,
    run_representation_pipeline,
)
from core.time_normalizer import deduplicate_index, ensure_local_index
from core.structure_encoder import select_ewm_monitoring_surface

from utils.timer import Timer, enable_timer_metrics  # type: ignore
from core.resource_monitor import enable_resource_metrics


# Console from observability (backwards compatible). Do not reimport here to
# preserve the fallback mechanism when observability is unavailable.

# Model lifecycle management (maturity, promotion, and active model tracking).
from core.model_lifecycle import (
    BOOLEAN_ONLY_METRICS,
    resolve_maturity_for_regime_stage,
)


def _configure_logging(logging_cfg, args):
    """Apply CLI/config logging overrides and return effective flags."""
    log_file = args.log_file or (logging_cfg or {}).get("file")
    if log_file:
        Console.warn(
            f"--log-file={log_file} ignored: ACM writes all logs to SQL (ACM_RunLogs) and the "
            f"observability stack (Loki). File-based logging is not supported.",
            component="CONFIG",
            log_file=str(log_file),
        )


def _maybe_log_zero_day_scoring_status(
    *,
    logger: Any,
    lifecycle_state: Optional[Any],
    selected_channels: int,
) -> bool:
    """
    Emit a one-line operator hint when zero-day scoring is active before convergence.

    Lifecycle labels now describe legacy-model maturity, not whether anomaly scoring
    exists. Make that explicit when EWM is active in `COLDSTART` or `LEARNING`.
    """
    state = str(lifecycle_state or "").strip().upper()
    if selected_channels <= 0 or state not in {"COLDSTART", "LEARNING"}:
        return False

    logger.info(
        f"Zero-day scoring active while lifecycle={state}; lifecycle tracks legacy model maturity, not anomaly-output availability",
        component="EWM_BASELINE",
        lifecycle_state=state,
        selected_channels=int(selected_channels),
    )
    return True


_ZERO_DAY_PRECHECK_BLOCKERS = {
    "runtime_mode_not_ready",
    "baseline_formation_scoring_disabled",
    "schema_break_requalification_required",
    "no_score_rows",
    "insufficient_coverage",
    "stale_inputs",
    "insufficient_effective_signals",
    "poor_missingness",
    "schema_incompatible",
    "basis_incompatible",
    "baseline_incompatible",
    "baseline_not_ready",
    "baseline_contaminated",
}
_PRE_FEATURE_FAST_FAIL_BLOCKERS = {
    "runtime_mode_not_ready",
    "schema_break_requalification_required",
    "no_score_rows",
    "insufficient_coverage",
    "stale_inputs",
    "insufficient_effective_signals",
    "poor_missingness",
    "baseline_not_ready",
    "baseline_contaminated",
}
_PRE_FEATURE_FAST_FAIL_IGNORED = {
    "baseline_formation_scoring_disabled",
    "context_unknown",
    "context_unassessed",
}

_POST_REGIME_PRECHECK_BLOCKERS = _ZERO_DAY_PRECHECK_BLOCKERS.union(
    {
        "context_unknown",
        "context_unassessed",
        "context_novel",
        "context_ambiguous",
        "context_transition_active",
        "context_low_confidence",
    }
)
_POST_REGIME_PRETRANSIENT_BLOCKERS = _POST_REGIME_PRECHECK_BLOCKERS.difference(
    {"context_transition_active"}
)


def _representation_learning_blocked(representation_result: Optional[Any]) -> bool:
    """Return True when authoritative representation has disabled learning."""
    if representation_result is None or not getattr(representation_result, "authoritative", False):
        return False
    eligibility = getattr(representation_result, "eligibility", None)
    return bool(
        eligibility is not None
        and getattr(eligibility, "learn_allowed", None) is False
    )


def _representation_blocks_zero_day_scoring(representation_result: Optional[Any]) -> bool:
    """Return True when authoritative representation already knows zero-day scoring should not run."""
    if representation_result is None or not getattr(representation_result, "authoritative", False):
        return False
    eligibility = getattr(representation_result, "eligibility", None)
    if eligibility is None or getattr(eligibility, "score_allowed", None) is not False:
        return False

    reasons = {
        str(reason).strip()
        for reason in (getattr(eligibility, "suppressed_reason_codes", ()) or ())
        if str(reason).strip()
    }
    return bool(reasons.intersection(_ZERO_DAY_PRECHECK_BLOCKERS))


def _representation_blocks_pre_feature_runtime(
    representation_result: Optional[Any],
) -> bool:
    """Return True when authoritative structural blockers already make the batch non-scoreable before feature prep."""
    if representation_result is None or not getattr(representation_result, "authoritative", False):
        return False
    eligibility = getattr(representation_result, "eligibility", None)
    if eligibility is None:
        return False
    if getattr(eligibility, "score_allowed", None) is not False:
        return False
    if getattr(eligibility, "learn_allowed", None) is not False:
        return False

    reasons = {
        str(reason).strip()
        for reason in (getattr(eligibility, "suppressed_reason_codes", ()) or ())
        if str(reason).strip()
    }
    effective_reasons = reasons.difference(_PRE_FEATURE_FAST_FAIL_IGNORED)
    return bool(effective_reasons) and effective_reasons.issubset(_PRE_FEATURE_FAST_FAIL_BLOCKERS)


def _baseline_seed_blocks_pre_feature_runtime(
    baseline_seed: Optional[Any],
    representation_result: Optional[Any],
) -> bool:
    """Return True when a score-derived baseline candidate is explicitly shadow-only."""
    if baseline_seed is None:
        return False
    if getattr(baseline_seed, "authoritative", True):
        return False
    if getattr(baseline_seed, "applied_to_runtime", True):
        return False
    if representation_result is None or not getattr(representation_result, "authoritative", False):
        return False
    eligibility = getattr(representation_result, "eligibility", None)
    if eligibility is None:
        return False
    return getattr(eligibility, "score_allowed", None) is False


def _representation_blocks_post_regime_runtime(representation_result: Optional[Any]) -> bool:
    """Return True when authoritative representation has enough post-regime context to stop downstream runtime."""
    if representation_result is None or not getattr(representation_result, "authoritative", False):
        return False
    eligibility = getattr(representation_result, "eligibility", None)
    if eligibility is None or getattr(eligibility, "score_allowed", None) is not False:
        return False

    reasons = {
        str(reason).strip()
        for reason in (getattr(eligibility, "suppressed_reason_codes", ()) or ())
        if str(reason).strip()
    }
    return bool(reasons.intersection(_POST_REGIME_PRECHECK_BLOCKERS))


def _representation_blocks_pre_detector_runtime(
    representation_result: Optional[Any],
) -> bool:
    """Return True when authoritative pre-score context already blocks both scoring and learning."""
    if representation_result is None or not getattr(representation_result, "authoritative", False):
        return False
    eligibility = getattr(representation_result, "eligibility", None)
    if eligibility is None or getattr(eligibility, "score_allowed", None) is not False:
        return False
    if getattr(eligibility, "learn_allowed", None) is not False:
        return False

    reasons = {
        str(reason).strip()
        for reason in (getattr(eligibility, "suppressed_reason_codes", ()) or ())
        if str(reason).strip()
    }
    return bool(reasons.intersection(_POST_REGIME_PRETRANSIENT_BLOCKERS))


def _representation_blocks_post_regime_pretransient(
    representation_result: Optional[Any],
) -> bool:
    """Return True when authoritative representation can stop runtime before transient detection runs."""
    if representation_result is None or not getattr(representation_result, "authoritative", False):
        return False
    eligibility = getattr(representation_result, "eligibility", None)
    if eligibility is None or getattr(eligibility, "score_allowed", None) is not False:
        return False

    reasons = {
        str(reason).strip()
        for reason in (getattr(eligibility, "suppressed_reason_codes", ()) or ())
        if str(reason).strip()
    }
    return bool(reasons.intersection(_POST_REGIME_PRETRANSIENT_BLOCKERS))


def _evaluate_representation_pre_feature(
    *,
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    meta: Any,
    cfg: Dict[str, Any],
    equip_id: int,
    run_id: str,
    policy: RepresentationAuthorityPolicy,
    logger: Any,
    block_message: str,
    failure_message: str,
    fallback_result: Optional[Any] = None,
) -> Tuple[Optional[Any], bool]:
    """Run the structural representation precheck and report whether it blocks pre-feature runtime."""
    try:
        representation_result = run_representation_pipeline(
            train_df=train_df,
            score_df=score_df,
            meta=meta,
            cfg=cfg,
            equip_id=equip_id,
            run_id=run_id,
            logger=logger,
        )
        if policy.active and representation_result is not None:
            representation_result = apply_representation_authority(
                representation_result,
                policy=policy,
                logger=logger,
            )
            if _representation_blocks_pre_feature_runtime(representation_result):
                logger.info(
                    block_message,
                    component="REPRESENTATION",
                    equip_id=equip_id,
                    run_id=run_id,
                )
                return representation_result, True
        return representation_result, False
    except Exception as representation_exc:
        logger.warn(
            failure_message,
            component="REPRESENTATION",
            equip_id=equip_id,
            run_id=run_id,
            error_type=type(representation_exc).__name__,
            error=str(representation_exc)[:200],
        )
        return fallback_result, False


def _finalize_pre_feature_representation_short_circuit(
    *,
    representation_result: Optional[Any],
    output_manager: Optional[Any],
    score_df: pd.DataFrame,
    degradations: List[str],
    run_start_time: Optional[datetime],
    equip: str,
    equip_id: int,
    run_id: str,
    rows_written: int,
    section_fn: Any,
    logger: Any,
) -> Tuple[str, Optional[str]]:
    """Persist control-plane artifacts and close out a pre-feature authoritative no-score run."""
    with section_fn("representation.shadow.persist"):
        if representation_result is not None and output_manager is not None:
            try:
                output_manager.write_representation_artifacts(
                    representation_result=representation_result,
                    signal_source_df=score_df,
                )
            except Exception as representation_exc:
                logger.warn(
                    "Representation shadow persistence failed; continuing with legacy runtime authority",
                    component="REPRESENTATION",
                    equip_id=equip_id,
                    run_id=run_id,
                    error_type=type(representation_exc).__name__,
                    error=str(representation_exc)[:200],
                )

    outcome, degraded_err_json = resolve_run_outcome_from_degradations(degradations)
    err_json = None
    if outcome == "DEGRADED":
        err_json = degraded_err_json
        logger.warn(
            f"Run completed with {len(degradations)} degraded step(s): {degradations[:5]}",
            component="RUN",
            equip=equip,
            run_id=run_id,
        )

    _elapsed_s = (datetime.now() - run_start_time).total_seconds() if run_start_time else 0
    logger.info(
        f"RUN END: outcome={outcome} elapsed={_elapsed_s:.0f}s "
        f"max_fused_z=? episodes=0 rows_written={rows_written}",
        component="RUN",
    )
    return outcome, err_json


@dataclass(frozen=True)
class RepresentationRawPreviewPrecheckResult:
    """Outcome of the validation-mode raw regime-context preview before full feature prep."""

    representation_result: Optional[Any]
    seasonality_stage: Optional[Any]
    blocked: bool = False
    zero_day_status: Optional[Any] = None


@dataclass(frozen=True)
class RepresentationFeaturePreviewPrecheckResult:
    """Outcome of the cached feature-frame regime-context preview before detector load."""

    representation_result: Optional[Any]
    train_df: pd.DataFrame
    score_df: pd.DataFrame
    schema_drift_decision: Optional[Any] = None
    basis_result: Optional[Any] = None
    context_preview: Optional[Any] = None
    regime_model: Optional[Any] = None
    regime_state: Optional[Any] = None
    regime_state_version: int = 0
    regime_loaded_from_state: bool = False
    preview_used: bool = False
    blocked: bool = False
    zero_day_status: Optional[Any] = None


def _run_representation_raw_preview_precheck(
    *,
    representation_result: Optional[Any],
    policy: RepresentationAuthorityPolicy,
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    cfg: Dict[str, Any],
    equip: str,
    equip_id: int,
    run_id: str,
    sql_client: Any,
    meta: Any,
    refit_requested: bool,
    section_fn: Any,
    logger: Any,
) -> RepresentationRawPreviewPrecheckResult:
    """Run the earlier raw regime preview and decide whether it blocks pre-detector runtime."""
    if representation_result is None or not policy.active:
        return RepresentationRawPreviewPrecheckResult(
            representation_result=representation_result,
            seasonality_stage=None,
        )

    try:
        with section_fn("representation.preview.raw.seasonality"):
            seasonality_stage = fast_features.run_seasonality_preparation_stage(
                train=train_df,
                score=score_df,
                cfg=cfg,
                equip=equip,
                section_fn=section_fn,
                detect_and_adjust_fn=detect_and_adjust_safe,
            )

        with section_fn("representation.preview.raw"):
            preview_regime_state, preview_regime_state_version, preview_regime_loaded_from_state = (
                load_quality_regime_state_if_needed(
                    regime_model=None,
                    equip=equip,
                    equip_id=equip_id,
                    sql_client=sql_client,
                    logger=logger,
                )
            )
            raw_preview = regimes.preview_regime_context_from_raw_stage(
                train_df=seasonality_stage.train,
                score_df=seasonality_stage.score,
                cfg=cfg,
                regime_model=None,
                regime_state=preview_regime_state,
                regime_loaded_from_state=preview_regime_loaded_from_state,
                regime_state_version=preview_regime_state_version,
                raw_train=seasonality_stage.train,
                raw_score=seasonality_stage.score,
                equip=equip,
                logger=logger,
            )
            if raw_preview.available:
                basis_drift_decision = raw_preview.basis_result.basis_drift_decision
                representation_result = refresh_representation_runtime_authority(
                    representation_result,
                    cfg=cfg,
                    policy=policy,
                    context=raw_preview.context_preview.context_assignment,
                    meta=meta,
                    basis_drift=basis_drift_decision,
                    refit_requested=refit_requested,
                    logger=logger,
                )
                if _representation_blocks_pre_detector_runtime(representation_result):
                    logger.info(
                        "Representation authority short-circuited feature, detector, regime, zero-day, and health stages from raw regime-context preview",
                        component="REPRESENTATION",
                        equip_id=equip_id,
                        run_id=run_id,
                    )
                    return RepresentationRawPreviewPrecheckResult(
                        representation_result=representation_result,
                        seasonality_stage=seasonality_stage,
                        blocked=True,
                        zero_day_status=build_zero_day_run_status(
                            scoring_active=False,
                            status="inactive_representation_blocked",
                            surface_type="none",
                            channel_count=0,
                        ),
                    )
    except Exception as representation_exc:
        logger.warn(
            "Representation authority raw regime-context preview failed; continuing with feature-prep runtime path",
            component="REPRESENTATION",
            equip_id=equip_id,
            run_id=run_id,
            error_type=type(representation_exc).__name__,
            error=str(representation_exc)[:200],
        )
        return RepresentationRawPreviewPrecheckResult(
            representation_result=representation_result,
            seasonality_stage=None,
        )

    return RepresentationRawPreviewPrecheckResult(
        representation_result=representation_result,
        seasonality_stage=seasonality_stage,
    )


def _run_representation_feature_preview_precheck(
    *,
    representation_result: Optional[Any],
    policy: RepresentationAuthorityPolicy,
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    raw_train: pd.DataFrame,
    raw_score: pd.DataFrame,
    cfg: Dict[str, Any],
    equip: str,
    equip_id: int,
    run_id: str,
    sql_client: Any,
    meta: Any,
    refit_requested: bool,
    section_fn: Any,
    logger: Any,
) -> RepresentationFeaturePreviewPrecheckResult:
    """Run cached regime preview on feature frames before full detector initialization."""
    if representation_result is None or not policy.active:
        return RepresentationFeaturePreviewPrecheckResult(
            representation_result=representation_result,
            train_df=train_df,
            score_df=score_df,
        )

    with section_fn("representation.preview.feature.cache"):
        preview_state = load_cached_regime_preview_from_sql_cache(
            train=train_df,
            score=score_df,
            equip=equip,
            sql_client=sql_client,
            equip_id=equip_id,
            cfg=cfg,
            logger=logger,
        )

    preview_train = preview_state["train"]
    preview_score = preview_state["score"]
    preview_regime_model = preview_state["regime_model"]
    preview_regime_state = preview_state["regime_state"]
    preview_regime_state_version = preview_state["regime_state_version"]
    preview_regime_loaded_from_state = preview_state["regime_loaded_from_state"]
    schema_drift_decision = preview_state["schema_drift_decision"]

    if preview_regime_model is None and not preview_regime_loaded_from_state:
        return RepresentationFeaturePreviewPrecheckResult(
            representation_result=representation_result,
            train_df=preview_train,
            score_df=preview_score,
            schema_drift_decision=schema_drift_decision,
        )

    with section_fn("representation.preview.feature"):
        basis_result = regimes.build_regime_feature_basis_stage(
            train_features=preview_train,
            score_features=preview_score,
            raw_train=raw_train,
            raw_score=raw_score,
            pca_detector=None,
            cfg=cfg,
            regime_model=preview_regime_model,
            equip=equip,
            logger=logger,
        )
        context_preview = regimes.preview_regime_context_stage(
            score_df=preview_score,
            train_df=preview_train,
            cfg=cfg,
            regime_basis_train=basis_result.regime_basis_train,
            regime_basis_score=basis_result.regime_basis_score,
            regime_basis_meta=basis_result.regime_basis_meta,
            regime_basis_hash=basis_result.regime_basis_hash,
            regime_model=basis_result.regime_model,
            regime_loaded_from_state=preview_regime_loaded_from_state,
            regime_state=preview_regime_state,
            regime_state_version=preview_regime_state_version,
            raw_train=raw_train,
        )

    if not context_preview.available:
        return RepresentationFeaturePreviewPrecheckResult(
            representation_result=representation_result,
            train_df=preview_train,
            score_df=preview_score,
            schema_drift_decision=schema_drift_decision,
            basis_result=basis_result,
            regime_model=basis_result.regime_model,
            regime_state=preview_regime_state,
            regime_state_version=preview_regime_state_version,
            regime_loaded_from_state=preview_regime_loaded_from_state,
        )

    representation_result = refresh_representation_runtime_authority(
        representation_result,
        cfg=cfg,
        policy=policy,
        context=context_preview.context_assignment,
        meta=meta,
        feature_schema_drift=schema_drift_decision,
        basis_drift=basis_result.basis_drift_decision,
        refit_requested=refit_requested,
        logger=logger,
    )
    blocked = _representation_blocks_pre_detector_runtime(representation_result)
    zero_day_status = None
    if blocked:
        logger.info(
            "Representation authority short-circuited detector scoring, zero-day, and health stages from cached feature-frame regime preview",
            component="REPRESENTATION",
            equip_id=equip_id,
            run_id=run_id,
        )
        zero_day_status = build_zero_day_run_status(
            scoring_active=False,
            status="inactive_representation_blocked",
            surface_type="none",
            channel_count=0,
        )

    return RepresentationFeaturePreviewPrecheckResult(
        representation_result=representation_result,
        train_df=preview_train,
        score_df=preview_score,
        schema_drift_decision=schema_drift_decision,
        basis_result=basis_result,
        context_preview=context_preview,
        regime_model=context_preview.regime_model,
        regime_state=preview_regime_state,
        regime_state_version=preview_regime_state_version,
        regime_loaded_from_state=preview_regime_loaded_from_state,
        preview_used=True,
        blocked=blocked,
        zero_day_status=zero_day_status,
    )


def _initialize_zero_day_runtime(
    *,
    ewm_cfg: Dict[str, Any],
    sql_client: Any,
    equip_id: int,
    enable_binner: bool = True,
) -> tuple[EWMBaselineManager, Optional[OnlinePCABinner]]:
    """Lazily load zero-day runtime state only when the path is actually needed."""
    ewm_manager = EWMBaselineManager(
        equip_id=equip_id,
        alpha_fast=float(ewm_cfg.get("alpha_fast", 0.05)),
        alpha_slow=float(ewm_cfg.get("alpha_slow", 0.005)),
        anomaly_z=float(ewm_cfg.get("anomaly_z", 3.0)),
    )
    ewm_manager.load_from_sql(sql_client)

    binner: Optional[OnlinePCABinner] = None
    if enable_binner:
        binner = OnlinePCABinner(
            n_bins=int(ewm_cfg.get("n_bins", 3)),
            min_rows_for_assignment=int(ewm_cfg.get("min_rows_for_assignment", 20)),
            alpha=float(ewm_cfg.get("proxy_alpha", 0.05)),
            history_limit=int(ewm_cfg.get("proxy_history_limit", 512)),
        )
        binner.load_from_sql(sql_client, equip_id)

    return ewm_manager, binner


# Backwards-compat breadcrumbs for helpers extracted from this module.
# _ensure_local_index -> core/time_normalizer.py::ensure_local_index()
# bootstrap run state -> core/sql_client.py::bootstrap_acm_run_state()


# ========================================================================
# Extracted helpers (now owned by dedicated modules)
# ========================================================================
# _sql_finalize_run -> sql_client.py::SQLClient.finalize_run()
# _execute_with_deadlock_retry -> sql_client.py::execute_with_deadlock_retry()
# _deduplicate_index -> time_normalizer.py::deduplicate_index()
# _ensure_local_index -> time_normalizer.py::ensure_local_index()
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
    ap.add_argument(
        "--representation-authority",
        choices=["shadow", "validation"],
        help="Authority mode for the representation layer. Validation mode only activates on replay unless explicitly allowed in config.",
    )
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
    
    init_run_observability(
        equip=equip,
        equip_id=0,  # Will be updated after SQL connects
        logger=Console,
    )

    T = Timer(enable=True)

    # Enable OTEL metrics for Timer and ResourceMonitor.
    enable_timer_metrics(equip)
    enable_resource_metrics(equip)

    # ========================================================================
    # Fail-fast SQL connect: ACM is SQL-only and must abort if SQL is down.
    # ========================================================================
    sql_client = connect_acm_sql_failfast(cfg={}, logger=Console)
    set_sql_log_client(sql_client)

    with T.section("startup"):
        bootstrap = bootstrap_acm_run_state(
            sql_client=sql_client,
            equip=equip,
            args=args,
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

    Console.info(
        f"RUN START: run_id={run_id} equip={equip} equip_id={equip_id} "
        f"batch={run_count} tick={getattr(args, 'tick_minutes', '?')}min "
        f"range={win_start} to {win_end}",
        component="RUN",
    )

    runtime_policy = resolve_runtime_policy(args=args)
    force_retraining = runtime_policy.force_retraining
    representation_authority_policy = resolve_representation_authority_policy(cfg=cfg, args=args)
    Console.info(
        "Representation authority policy resolved",
        component="REPRESENTATION",
        mode=representation_authority_policy.mode,
        active=representation_authority_policy.active,
        reason=representation_authority_policy.reason,
    )
    
    # Set observability context (equipment metadata only).
    set_acm_context(
        equipment=equip,
        equip_id=equip_id
    )
    
    # Consolidated startup log.
    force_retrain_str = "true" if force_retraining else "false"
    Console.info(
        f"Run #{run_count + 1} | equip={equip} mode=adaptive force_retrain={force_retrain_str}",
        component="RUN",
    )

    # Initialize cross-phase state variables.
    regime_model: Optional[regimes.RegimeModel] = None
    raw_train: Optional[pd.DataFrame] = None
    raw_score: Optional[pd.DataFrame] = None
    regime_quality_ok: bool = True
    refit_requested: bool = False

    # ===== EWM Zero-Day Baseline: load persisted state =====
    _ewm_cfg = cfg.get("models", {}).get("ewm_baseline", {}) or {}
    _ewm_enabled = bool(_ewm_cfg.get("enabled", True))
    zero_day_status = build_zero_day_run_status(
        scoring_active=False,
        status="inactive_disabled" if not _ewm_enabled else "inactive_not_evaluated",
        surface_type="none",
        channel_count=0,
    )
    ewm_manager: Optional[EWMBaselineManager] = None

    # ===== Online day-0 regime proxy =====
    # Asset-agnostic fallback regime source used before mature HDBSCAN labels exist.
    _binner: Optional[OnlinePCABinner] = None

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
    run_start_time = datetime.now()

    # Initialize tracing span for the run (equipment name in span for Tempo).
    tracer = get_tracer()
    # v11.1.6: Correlation uses acm.run_id/acm.run_count/acm.equipment attributes.
    _span_ctx, root_span = start_run_span(
        tracer=tracer,
        equip=equip,
        equip_id=equip_id,
        run_id=run_id,
        run_count=run_count,
    )

    model_state = None  # Single source of truth for model lifecycle state.
    
    # Initialize detector-related variables at function scope to avoid fragile
    # 'in dir()' checks throughout the pipeline.
    train: Optional[pd.DataFrame] = None
    col_meds: Optional[pd.Series] = None
    raw_signal_medians: Optional[Dict[str, float]] = None
    # NOTE: regime_model is declared earlier; avoid redefinition here.
    meta: Optional[Any] = None
    frame: Optional[pd.DataFrame] = None
    train_frame: Optional[pd.DataFrame] = None
    episodes: Optional[pd.DataFrame] = None
    score_out: Optional[Dict[str, Any]] = None
    omr_contributions_data: Optional[pd.DataFrame] = None
    quality_ok: bool = False
    use_per_regime: bool = False
    fusion_weights_used: Optional[Dict[str, float]] = None
    spe_p95_train: Optional[float] = None
    t2_p95_train: Optional[float] = None
    score_regime_labels: Optional[np.ndarray] = None
    train_regime_labels: Optional[np.ndarray] = None
    current_model_maturity: Optional[str] = None
    regime_model_was_trained: bool = False
    saved_model_version: Optional[int] = None
    representation_shadow = None
    representation_score_suppressed = False
    ewm_freeze_changes: Optional[Dict[Any, str]] = None
    schema_drift_decision = None
    basis_drift_decision = None
    pre_score_basis_result = None
    feature_preview_context_evaluated = False
    skip_post_regime_runtime = False
    skip_prefeature_runtime = False
    seasonality_stage = None
    det_flags = {
        "ar1_enabled": False,
        "pca_enabled": False,
        "iforest_enabled": False,
        "gmm_enabled": False,
        "omr_enabled": False,
    }
    detector_flags = dict(det_flags)
    detectors = {
        "ar1_detector": None,
        "pca_detector": None,
        "iforest_detector": None,
        "gmm_detector": None,
        "omr_detector": None,
        "pca_train_spe": None,
        "pca_train_t2": None,
    }
    regime_state = None
    regime_state_version = 0
    regime_loaded_from_state = False
    cached_models = None
    cached_manifest = None
    cached_calibration_params = None
    detectors_just_trained = False
    baseline_contamination_verdict = "unknown"
    baseline_contamination_rate = 0.0

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
                zero_day_status = zero_day_status_from_noop_reason(
                    load_stage.noop_reason or "UNKNOWN_NOOP"
                )
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

        with T.section("representation.shadow"):
            representation_shadow, skip_prefeature_runtime = _evaluate_representation_pre_feature(
                train_df=train,
                score_df=score,
                meta=meta,
                cfg=cfg,
                equip_id=equip_id,
                run_id=run_id,
                policy=representation_authority_policy,
                logger=Console,
                block_message="Representation authority short-circuited feature, detector, regime, zero-day, and health stages from load-time structural precheck",
                failure_message="Representation shadow pipeline failed; continuing with legacy runtime authority",
                fallback_result=representation_shadow,
            )
            if skip_prefeature_runtime:
                representation_score_suppressed = True
                quality_ok = False
                degradations.append("representation_score_suppressed")
                zero_day_status = build_zero_day_run_status(
                    scoring_active=False,
                    status="inactive_representation_blocked",
                    surface_type="none",
                    channel_count=0,
                )

        T.log("data_split_complete", train_rows=train.shape[0], train_cols=train.shape[1], score_rows=score.shape[0], score_cols=score.shape[1])

        if skip_prefeature_runtime:
            rows_read = int(score.shape[0])
            outcome, err_json = _finalize_pre_feature_representation_short_circuit(
                representation_result=representation_shadow,
                output_manager=output_manager,
                score_df=score,
                degradations=degradations,
                run_start_time=run_start_time,
                equip=equip,
                equip_id=equip_id,
                run_id=run_id,
                rows_written=rows_written,
                section_fn=T.section,
                logger=Console,
            )
            return
        
        # ===== Adaptive rolling baseline (cold-start helper) =====
        # B1 fix: coldstart_complete means "can_proceed" (True on scoring batches too).
        # is_coldstart_run is True only when this batch IS the coldstart training run.
        is_coldstart_run = (
            meta.get("is_coldstart_run", False)
            if isinstance(meta, dict)
            else getattr(meta, "is_coldstart_run", False)
        )
        with T.section("baseline.seed"):
            baseline_seed = seed_baseline_safe(
                train=train.copy(),
                score=score.copy(),
                sql_client=sql_client,
                equip_id=equip_id,
                cfg=cfg,
                equip=equip,
                is_coldstart=is_coldstart_run,
                ensure_local_index_fn=ensure_local_index,
                apply_non_authoritative_seed=not representation_authority_policy.active,
                logger=Console,
            )
            train = baseline_seed.train_df
            score = baseline_seed.score_df
            if isinstance(meta, dict):
                meta["baseline_seed_source"] = baseline_seed.source_code
                meta["baseline_seed_authoritative"] = baseline_seed.authoritative
                meta["baseline_seed_applied_to_runtime"] = baseline_seed.applied_to_runtime
            else:
                setattr(meta, "baseline_seed_source", baseline_seed.source_code)
                setattr(meta, "baseline_seed_authoritative", baseline_seed.authoritative)
                setattr(meta, "baseline_seed_applied_to_runtime", baseline_seed.applied_to_runtime)

        if representation_shadow is not None and representation_authority_policy.active:
            with T.section("representation.shadow.baseline"):
                representation_shadow, skip_prefeature_runtime = _evaluate_representation_pre_feature(
                    train_df=train,
                    score_df=score,
                    meta=meta,
                    cfg=cfg,
                    equip_id=equip_id,
                    run_id=run_id,
                    policy=representation_authority_policy,
                    logger=Console,
                    block_message="Representation authority short-circuited feature, detector, regime, zero-day, and health stages after baseline seeding",
                    failure_message="Representation post-baseline structural recheck failed; continuing with later runtime authority",
                    fallback_result=representation_shadow,
                )
                if (
                    not skip_prefeature_runtime
                    and _baseline_seed_blocks_pre_feature_runtime(baseline_seed, representation_shadow)
                ):
                    Console.info(
                        "Representation authority short-circuited feature, detector, regime, zero-day, and health stages because no authoritative trusted baseline window is available yet",
                        component="REPRESENTATION",
                        equip_id=equip_id,
                        run_id=run_id,
                    )
                    skip_prefeature_runtime = True
                if skip_prefeature_runtime:
                    representation_score_suppressed = True
                    quality_ok = False
                    degradations.append("representation_score_suppressed")
                    zero_day_status = build_zero_day_run_status(
                        scoring_active=False,
                        status="inactive_representation_blocked",
                        surface_type="none",
                        channel_count=0,
                    )

        if skip_prefeature_runtime:
            rows_read = int(score.shape[0])
            outcome, err_json = _finalize_pre_feature_representation_short_circuit(
                representation_result=representation_shadow,
                output_manager=output_manager,
                score_df=score,
                degradations=degradations,
                run_start_time=run_start_time,
                equip=equip,
                equip_id=equip_id,
                run_id=run_id,
                rows_written=rows_written,
                section_fn=T.section,
                logger=Console,
            )
            return

        if representation_shadow is not None and representation_authority_policy.active:
            raw_preview_precheck = _run_representation_raw_preview_precheck(
                representation_result=representation_shadow,
                policy=representation_authority_policy,
                train_df=train,
                score_df=score,
                cfg=cfg,
                equip=equip,
                equip_id=equip_id,
                run_id=run_id,
                sql_client=sql_client,
                meta=meta,
                refit_requested=refit_requested,
                section_fn=T.section,
                logger=Console,
            )
            representation_shadow = raw_preview_precheck.representation_result
            seasonality_stage = raw_preview_precheck.seasonality_stage
            if raw_preview_precheck.blocked:
                representation_score_suppressed = True
                quality_ok = False
                degradations.append("representation_score_suppressed")
                zero_day_status = raw_preview_precheck.zero_day_status

        if representation_score_suppressed and skip_post_regime_runtime is False:
            rows_read = int(score.shape[0])
            outcome, err_json = _finalize_pre_feature_representation_short_circuit(
                representation_result=representation_shadow,
                output_manager=output_manager,
                score_df=score,
                degradations=degradations,
                run_start_time=run_start_time,
                equip=equip,
                equip_id=equip_id,
                run_id=run_id,
                rows_written=rows_written,
                section_fn=T.section,
                logger=Console,
            )
            return

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
            load_cached_raw_signal_medians_fn=load_cached_raw_signal_medians,
            load_cached_feature_medians_fn=load_cached_feature_medians,
            seasonality_result=seasonality_stage,
        )
        train = feature_stage.train
        score = feature_stage.score
        raw_train = feature_stage.raw_train
        raw_score = feature_stage.raw_score
        seasonal_patterns = feature_stage.seasonal_patterns
        refit_requested = feature_stage.refit_requested
        raw_signal_medians = (
            raw_train.select_dtypes(include=[np.number]).median().to_dict()
            if raw_train is not None and not raw_train.empty
            else None
        )

        if representation_shadow is not None and representation_authority_policy.active:
            feature_preview_precheck = _run_representation_feature_preview_precheck(
                representation_result=representation_shadow,
                policy=representation_authority_policy,
                train_df=train,
                score_df=score,
                raw_train=raw_train,
                raw_score=raw_score,
                cfg=cfg,
                equip=equip,
                equip_id=equip_id,
                run_id=run_id,
                sql_client=sql_client,
                meta=meta,
                refit_requested=refit_requested,
                section_fn=T.section,
                logger=Console,
            )
            representation_shadow = feature_preview_precheck.representation_result
            train = feature_preview_precheck.train_df
            score = feature_preview_precheck.score_df
            if feature_preview_precheck.schema_drift_decision is not None:
                schema_drift_decision = feature_preview_precheck.schema_drift_decision
            if feature_preview_precheck.preview_used:
                feature_preview_context_evaluated = True
                pre_score_basis_result = feature_preview_precheck.basis_result
                regime_model = feature_preview_precheck.regime_model
                regime_state = feature_preview_precheck.regime_state
                regime_state_version = feature_preview_precheck.regime_state_version
                regime_loaded_from_state = feature_preview_precheck.regime_loaded_from_state
            if feature_preview_precheck.blocked and feature_preview_precheck.context_preview is not None:
                frame = feature_preview_precheck.context_preview.frame
                episodes = pd.DataFrame()
                score_out = feature_preview_precheck.context_preview.score_out
                regime_model = feature_preview_precheck.context_preview.regime_model
                train_regime_labels = feature_preview_precheck.context_preview.train_regime_labels
                score_regime_labels = feature_preview_precheck.context_preview.score_regime_labels
                regime_quality_ok = feature_preview_precheck.context_preview.regime_quality_ok
                representation_score_suppressed = True
                skip_post_regime_runtime = True
                quality_ok = False
                degradations.append("representation_score_suppressed")
                zero_day_status = feature_preview_precheck.zero_day_status

        # ===== Phase 2: Load or fit detectors =====
        if not skip_post_regime_runtime:
            detector_init = run_detector_initialization_stage(
                section_fn=T.section,
                train=train,
                score=score,
                cfg=cfg,
                meta=meta,
                detector_cache=None,
                output_manager=output_manager,
                sql_client=sql_client,
                run_id=run_id,
                equip_id=equip_id,
                equip=equip,
                logger=Console,
            )

            train = detector_init.train
            score = detector_init.score
            det_flags = detector_init.det_flags
            detector_flags = detector_init.enabled_flags()
            detectors = detector_init.detector_payload()
            regime_model = detector_init.regime_model
            regime_state = detector_init.regime_state
            regime_state_version = detector_init.regime_state_version
            regime_loaded_from_state = detector_init.regime_loaded_from_state
            col_meds = detector_init.col_meds
            cached_models = detector_init.cached_models
            cached_manifest = detector_init.cached_manifest
            cached_calibration_params = detector_init.cached_calibration_params
            detectors_just_trained = detector_init.detectors_just_trained
            baseline_contamination_verdict = detector_init.baseline_contamination_verdict
            baseline_contamination_rate = detector_init.baseline_contamination_rate
            schema_drift_decision = detector_init.schema_drift_decision

        if (
            representation_shadow is not None
            and representation_authority_policy.active
            and not skip_post_regime_runtime
            and not feature_preview_context_evaluated
        ):
            try:
                pre_score_basis_result = regimes.build_regime_feature_basis_stage(
                    train_features=train,
                    score_features=score,
                    raw_train=raw_train,
                    raw_score=raw_score,
                    pca_detector=detectors["pca_detector"],
                    cfg=cfg,
                    regime_model=regime_model,
                    equip=equip,
                    logger=Console,
                )
                basis_drift_decision = pre_score_basis_result.basis_drift_decision

                context_preview = regimes.preview_regime_context_stage(
                    score_df=score,
                    train_df=train,
                    cfg=cfg,
                    regime_basis_train=pre_score_basis_result.regime_basis_train,
                    regime_basis_score=pre_score_basis_result.regime_basis_score,
                    regime_basis_meta=pre_score_basis_result.regime_basis_meta,
                    regime_basis_hash=pre_score_basis_result.regime_basis_hash,
                    regime_model=pre_score_basis_result.regime_model,
                    regime_loaded_from_state=regime_loaded_from_state,
                    regime_state=regime_state,
                    regime_state_version=regime_state_version,
                    raw_train=raw_train,
                )

                if context_preview.available:
                    representation_shadow = refresh_representation_runtime_authority(
                        representation_shadow,
                        cfg=cfg,
                        policy=representation_authority_policy,
                        context=context_preview.context_assignment,
                        meta=meta,
                        feature_schema_drift=schema_drift_decision,
                        basis_drift=basis_drift_decision,
                        baseline_contamination_verdict=baseline_contamination_verdict,
                        refit_requested=refit_requested,
                        logger=Console,
                    )

                    if _representation_blocks_pre_detector_runtime(representation_shadow):
                        frame = context_preview.frame
                        episodes = pd.DataFrame()
                        score_out = context_preview.score_out
                        regime_model = context_preview.regime_model
                        train_regime_labels = context_preview.train_regime_labels
                        score_regime_labels = context_preview.score_regime_labels
                        regime_quality_ok = context_preview.regime_quality_ok
                        representation_score_suppressed = True
                        skip_post_regime_runtime = True
                        quality_ok = False
                        degradations.append("representation_score_suppressed")
                        zero_day_status = build_zero_day_run_status(
                            scoring_active=False,
                            status="inactive_representation_blocked",
                            surface_type="none",
                            channel_count=0,
                        )
                        Console.info(
                            "Representation authority short-circuited detector scoring, zero-day, and health stages from pre-score regime-context preview",
                            component="REPRESENTATION",
                            equip_id=equip_id,
                            run_id=run_id,
                        )
            except Exception as representation_exc:
                Console.warn(
                    "Representation authority pre-score context preview failed; continuing with full runtime authority path",
                    component="REPRESENTATION",
                    equip_id=equip_id,
                    run_id=run_id,
                    error_type=type(representation_exc).__name__,
                    error=str(representation_exc)[:200],
                )

        # ===== Phase 3-5: Regime basis + detector scoring + regime labeling =====
        if not skip_post_regime_runtime:
            scoring_regime_stage = regimes.run_scoring_regime_stage(
                train_df=train,
                score_df=score,
                raw_train=raw_train,
                raw_score=raw_score,
                cfg=cfg,
                pca_detector=detectors["pca_detector"],
                regime_model=regime_model,
                regime_state=regime_state,
                regime_state_version=regime_state_version,
                regime_loaded_from_state=regime_loaded_from_state,
                det_flags=det_flags,
                detectors=detectors,
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
                basis_result_override=pre_score_basis_result,
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
            regime_model_was_trained = scoring_regime_stage.regime_model_was_trained
            basis_drift_decision = scoring_regime_stage.basis_drift_decision
            if scoring_regime_stage.degraded_regime_basis:
                degradations.append("regime_feature_basis")

        if (
            not skip_post_regime_runtime
            and representation_shadow is not None
            and representation_authority_policy.active
        ):
            try:
                representation_shadow = refresh_representation_runtime_authority(
                    representation_shadow,
                    cfg=cfg,
                    policy=representation_authority_policy,
                    context=regimes.build_context_assignment(frame),
                    meta=meta,
                    feature_schema_drift=schema_drift_decision,
                    basis_drift=basis_drift_decision,
                    baseline_contamination_verdict=baseline_contamination_verdict,
                    refit_requested=refit_requested,
                    logger=Console,
                )

                if _representation_blocks_post_regime_pretransient(representation_shadow):
                    frame, episodes, representation_score_suppressed = fuse.suppress_representation_scoring(
                        frame=frame,
                        episodes=pd.DataFrame(),
                        representation_result=representation_shadow,
                        logger=Console,
                    )
                    if representation_score_suppressed:
                        degradations.append("representation_score_suppressed")
                        quality_ok = False
                        skip_post_regime_runtime = True
                        zero_day_status = build_zero_day_run_status(
                            scoring_active=False,
                            status="inactive_representation_blocked",
                            surface_type="none",
                            channel_count=0,
                        )
                        Console.info(
                            "Representation authority short-circuited transient, zero-day, and health stages after regime-context precheck",
                            component="REPRESENTATION",
                            equip_id=equip_id,
                            run_id=run_id,
                        )
                elif frame is not None:
                    frame, _ = regimes.apply_transient_state_labels(
                        frame=frame,
                        score_data=score,
                        cfg=cfg,
                        logger=Console,
                    )
                    representation_shadow = refresh_representation_runtime_authority(
                        representation_shadow,
                        cfg=cfg,
                        policy=representation_authority_policy,
                        context=regimes.build_context_assignment(frame),
                        meta=meta,
                        feature_schema_drift=schema_drift_decision,
                        basis_drift=basis_drift_decision,
                        baseline_contamination_verdict=baseline_contamination_verdict,
                        refit_requested=refit_requested,
                        logger=Console,
                    )
                    if _representation_blocks_post_regime_runtime(representation_shadow):
                        frame, episodes, representation_score_suppressed = fuse.suppress_representation_scoring(
                            frame=frame,
                            episodes=pd.DataFrame(),
                            representation_result=representation_shadow,
                            logger=Console,
                        )
                        if representation_score_suppressed:
                            degradations.append("representation_score_suppressed")
                            quality_ok = False
                            skip_post_regime_runtime = True
                            zero_day_status = build_zero_day_run_status(
                                scoring_active=False,
                                status="inactive_representation_blocked",
                                surface_type="none",
                                channel_count=0,
                            )
                            Console.info(
                                "Representation authority short-circuited zero-day and health stages after post-regime context gating",
                                component="REPRESENTATION",
                                equip_id=equip_id,
                                run_id=run_id,
                            )
            except Exception as representation_exc:
                Console.warn(
                    "Representation authority precheck failed; continuing with legacy runtime authority",
                    component="REPRESENTATION",
                    equip_id=equip_id,
                    run_id=run_id,
                    error_type=type(representation_exc).__name__,
                    error=str(representation_exc)[:200],
                )

        # ===== EWM Zero-Day Scoring =====
        # Scores score data against EWM dual-rate baselines and appends ewm_z to frame.
        # ewm_z = mean z_slow per row (long-term character deviation = genuine fault signal).
        # Feature-flagged: models.ewm_baseline.enabled (default True).
        zero_day_learning_blocked = _representation_learning_blocked(representation_shadow)
        zero_day_scoring_blocked = (
            skip_post_regime_runtime
            or _representation_blocks_zero_day_scoring(representation_shadow)
        )

        if _ewm_enabled and zero_day_scoring_blocked:
            zero_day_status = build_zero_day_run_status(
                scoring_active=False,
                status="inactive_representation_blocked",
                surface_type="none",
                channel_count=0,
            )
            Console.info(
                "Representation authority skipped zero-day scoring path",
                component="REPRESENTATION",
                equip_id=equip_id,
                run_id=run_id,
            )
        elif _ewm_enabled:
            if ewm_manager is None:
                ewm_manager, _binner = _initialize_zero_day_runtime(
                    ewm_cfg=_ewm_cfg,
                    sql_client=sql_client,
                    equip_id=equip_id,
                    enable_binner=True,
                )

            if raw_train is None or raw_score is None:
                zero_day_status = build_zero_day_run_status(
                    scoring_active=False,
                    status="inactive_raw_unavailable",
                    surface_type="none",
                    channel_count=0,
                )
                Console.warn(
                    "EWM disabled for this run: raw_train/raw_score are unavailable, so the "
                    "explicit day-0 monitoring surface cannot be constructed.",
                    component="EWM_BASELINE",
                )
                degradations.append("ewm_monitoring_surface")
            else:
                _ewm_cols, _ewm_train_numeric, _ewm_score_numeric, _ewm_surface_meta = (
                    select_ewm_monitoring_surface(
                        raw_train.reindex(train.index),
                        raw_score.reindex(score.index),
                        cfg=cfg,
                    )
                )

                if not _ewm_cols:
                    zero_day_status = build_zero_day_run_status(
                        scoring_active=False,
                        status="inactive_surface_unavailable",
                        surface_type=str(_ewm_surface_meta.get("surface_type", "none")),
                        channel_count=0,
                    )
                    Console.warn(
                        "EWM disabled for this run: no adequate explicit day-0 monitoring "
                        "surface was found in raw data.",
                        component="EWM_BASELINE",
                        candidate_count=_ewm_surface_meta.get("candidate_count", 0),
                        dropped_low_valid_count=_ewm_surface_meta.get("dropped_low_valid_count", 0),
                        dropped_low_iqr_count=_ewm_surface_meta.get("dropped_low_iqr_count", 0),
                    )
                    degradations.append("ewm_monitoring_surface")
                else:
                    _zero_day_surface_type = str(_ewm_surface_meta.get("surface_type", "none"))
                    Console.info(
                        f"EWM using explicit raw monitoring surface with {len(_ewm_cols)} channels",
                        component="EWM_BASELINE",
                        selected_count=len(_ewm_cols),
                    )
                    _maybe_log_zero_day_scoring_status(
                        logger=Console,
                        lifecycle_state=current_model_maturity,
                        selected_channels=len(_ewm_cols),
                    )
                    if _binner is not None:
                        _surface_state_kept = _binner.align_to_surface(_ewm_cols)
                        if not _surface_state_kept:
                            Console.info(
                                "Online regime proxy restarted on the active monitoring surface",
                                component="REGIME_BINNER",
                            )

                    # --- Phase 3: HDBSCAN as regime refiner ---
                    # When HDBSCAN first produces a stable model AND binner was the regime source
                    # up to this point, remap binner regime IDs → HDBSCAN cluster IDs in EWM state
                    # so coldstart history is not orphaned.
                    if (
                        not zero_day_learning_blocked
                        and regime_model_was_trained
                        and _binner is not None
                        and _binner.can_assign_fallback
                        and train_regime_labels is not None
                    ):
                        _binner_train_ids = _binner.assign_batch(_ewm_train_numeric)
                        if ewm_manager is not None and ewm_manager.has_binner_regime_ids(_binner_train_ids):
                            _hdbscan_train_ids = np.asarray(train_regime_labels, dtype=int)
                            _remap: Dict[int, int] = {}
                            for _bid in np.unique(_binner_train_ids):
                                if _bid < 0:
                                    continue
                                _mask = _binner_train_ids == _bid
                                _hdb_subset = _hdbscan_train_ids[_mask]
                                _valid = _hdb_subset[_hdb_subset >= 0]
                                if len(_valid) == 0:
                                    continue
                                # Modal HDBSCAN cluster for this binner bin
                                _modal = int(np.bincount(_valid).argmax())
                                _remap[int(_bid)] = _modal
                            if _remap:
                                ewm_manager.remap_regime_ids(_remap)
                                _binner.mark_remapped()
                                _binner.save_to_sql(sql_client, equip_id)
                                ewm_manager.save_to_sql(sql_client)

                    # Determine regime IDs for each score row.
                    # Preference: HDBSCAN labels when available and non-trivial.
                    # Fallback 1: OnlinePCABinner (zero-day, asset-agnostic context proxy).
                    # Fallback 2: global regime -1.
                    _hdbscan_valid = (
                        score_regime_labels is not None
                        and len(score_regime_labels) == len(score)
                        and np.any(score_regime_labels >= 0)
                    )
                    if _hdbscan_valid and score_regime_labels is not None:
                        _ewm_rids = score_regime_labels.astype(int)
                        zero_day_status = build_zero_day_run_status(
                            scoring_active=True,
                            status="active_hdbscan",
                            surface_type=_zero_day_surface_type,
                            channel_count=len(_ewm_cols),
                        )
                        Console.info("EWM using HDBSCAN regimes", component="EWM_BASELINE")
                        if _binner is not None and not zero_day_learning_blocked:
                            _binner.observe_batch(_ewm_score_numeric)
                            _binner.save_to_sql(sql_client, equip_id)
                    elif _binner is not None and _binner.can_assign_fallback:
                        # Feed binner with the explicit day-0 monitoring surface so edges refine over time.
                        if not zero_day_learning_blocked:
                            _binner.observe_batch(_ewm_score_numeric)
                        _ewm_rids = _binner.assign_batch(_ewm_score_numeric)
                        if not zero_day_learning_blocked:
                            _binner.save_to_sql(sql_client, equip_id)
                        if np.any(_ewm_rids >= 0):
                            zero_day_status = build_zero_day_run_status(
                                scoring_active=True,
                                status="active_online_pca_binner",
                                surface_type=_zero_day_surface_type,
                                channel_count=len(_ewm_cols),
                            )
                            Console.info(
                                f"EWM using PCA-binner regimes (HDBSCAN not ready): "
                                f"unique={np.unique(_ewm_rids[_ewm_rids >= 0]).tolist()}",
                                component="EWM_BASELINE",
                            )
                        else:
                            zero_day_status = build_zero_day_run_status(
                                scoring_active=True,
                                status="active_global_fallback",
                                surface_type=_zero_day_surface_type,
                                channel_count=len(_ewm_cols),
                            )
                            Console.info(
                                "EWM using global fallback regime (online proxy warming up)",
                                component="EWM_BASELINE",
                            )
                    else:
                        _ewm_rids = np.full(len(score), -1, dtype=int)
                        zero_day_status = build_zero_day_run_status(
                            scoring_active=True,
                            status="active_global_fallback",
                            surface_type=_zero_day_surface_type,
                            channel_count=len(_ewm_cols),
                        )
                        Console.info("EWM using global fallback regime", component="EWM_BASELINE")

                    # Score: vectorised, returns pd.Series of fused z_slow per row.
                    assert ewm_manager is not None
                    _ewm_series = ewm_manager.score_batch(_ewm_rids, _ewm_score_numeric)
                    if frame is not None and len(_ewm_series) == len(frame):
                        frame["ewm_z"] = _ewm_series.values

                    # Update EWM state only when representation authority allows learning.
                    if zero_day_learning_blocked:
                        Console.info(
                            "Representation authority skipped EWM baseline mutation",
                            component="REPRESENTATION",
                            equip_id=equip_id,
                            run_id=run_id,
                        )
                    else:
                        ewm_manager.update_batch(_ewm_rids, _ewm_score_numeric)
                        ewm_freeze_changes = ewm_manager.check_and_apply_freeze()
                        ewm_manager.save_to_sql(sql_client)

        # ===== Model adaptation + persistence =====
        if _representation_learning_blocked(representation_shadow):
            Console.info(
                "Representation authority skipped model adaptation and lifecycle persistence",
                component="REPRESENTATION",
                equip_id=equip_id,
                run_id=run_id,
            )
            model_stage = ModelAdaptationPersistenceResult(
                force_retrain=False,
                cached_models=cached_models,
                regime_model=regime_model,
                detectors=detectors,
                saved_model_version=None,
                model_state=model_state,
            )
        else:
            model_stage = run_model_adaptation_and_persistence_stage(
                section_fn=T.section,
                cfg=cfg,
                cached_models=cached_models,
                cached_manifest=cached_manifest,
                detectors_just_trained=detectors_just_trained,
                score_out=score_out,
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
                detectors=detectors,
                detector_cache=None,
                col_meds=col_meds,
                raw_signal_medians=raw_signal_medians,
                timing_sections=T.timings if hasattr(T, "timings") else None,
                model_state=model_state,
                regime_state_version=regime_state_version,
                force_retrain_requested=force_retraining,
                baseline_contamination_verdict=baseline_contamination_verdict,
            )
        cached_models = model_stage.cached_models
        regime_model = model_stage.regime_model
        detectors = model_stage.detectors
        saved_model_version = model_stage.saved_model_version
        model_state = model_stage.model_state

        # ===== Phase 6-7 + adaptive postprocess =====
        if skip_post_regime_runtime:
            Console.info(
                "Representation authority skipped calibration, fusion, and adaptive postprocess after post-regime context gating",
                component="REPRESENTATION",
                equip_id=equip_id,
                run_id=run_id,
            )
        else:
            persist_calibration = partial(
                persist_calibration_params_safe,
                equip=equip,
                sql_client=sql_client,
                equip_id=equip_id,
                logger=Console,
            )
            health_stage = fuse.run_health_stage(
                section_fn=T.section,
                train=train,
                score=score,
                frame=frame,
                cfg=cfg,
                regime_quality_ok=regime_quality_ok,
                train_regime_labels=train_regime_labels,
                score_regime_labels=score_regime_labels,
                pca_train_spe=detectors["pca_train_spe"],
                pca_train_t2=detectors["pca_train_t2"],
                detectors=detectors,
                detector_flags=detector_flags,
                cached_calibration_params=cached_calibration_params,
                saved_model_version=saved_model_version,
                persist_calibration_params_fn=persist_calibration,
                output_manager=output_manager,
                logger=Console,
                equip=equip,
                previous_weights=None,
                omr_contributions_data=omr_contributions_data,
                record_detector_scores_fn=record_detector_scores,
                record_episode_fn=record_episode,
                maybe_update_adaptive_thresholds_fn=maybe_update_adaptive_thresholds,
                equip_id=equip_id,
                regime_model=regime_model,
                score_out=score_out,
                sql_client=sql_client,
                run_id=run_id,
                cached_manifest=cached_manifest,
                baseline_contamination_verdict=baseline_contamination_verdict,
                representation_result=representation_shadow,
                representation_authority_active=representation_authority_policy.active,
            )
            frame = health_stage.frame
            train_frame = health_stage.train_frame
            episodes = health_stage.episodes
            fusion_weights_used = health_stage.fusion_weights_used
            spe_p95_train = health_stage.spe_p95_train
            t2_p95_train = health_stage.t2_p95_train
            quality_ok = health_stage.quality_ok
            use_per_regime = health_stage.use_per_regime

            with T.section("representation.shadow.comparability"):
                if representation_shadow is not None:
                    try:
                        representation_shadow = refresh_representation_runtime_authority(
                            representation_shadow,
                            cfg=cfg,
                            policy=representation_authority_policy,
                            context=getattr(health_stage, "context_assignment", None),
                            meta=meta,
                            feature_schema_drift=schema_drift_decision,
                            basis_drift=basis_drift_decision,
                            baseline_contamination_verdict=baseline_contamination_verdict,
                            freeze_changes=ewm_freeze_changes,
                            refit_requested=refit_requested,
                            logger=Console,
                        )
                        frame, episodes, representation_score_suppressed = fuse.suppress_representation_scoring(
                            frame=frame,
                            episodes=episodes,
                            representation_result=representation_shadow,
                            logger=Console,
                        )
                        if representation_score_suppressed:
                            degradations.append("representation_score_suppressed")
                            quality_ok = False
                    except Exception as representation_exc:
                        Console.warn(
                            "Representation shadow comparability failed; continuing with legacy runtime authority",
                            component="REPRESENTATION",
                            equip_id=equip_id,
                            run_id=run_id,
                            error_type=type(representation_exc).__name__,
                            error=str(representation_exc)[:200],
                        )
        with T.section("representation.shadow.persist"):
            if representation_shadow is not None and output_manager is not None:
                try:
                    output_manager.write_representation_artifacts(
                        representation_result=representation_shadow,
                        signal_source_df=raw_score if raw_score is not None else score,
                    )
                except Exception as representation_exc:
                    Console.warn(
                        "Representation shadow persistence failed; continuing with legacy runtime authority",
                        component="REPRESENTATION",
                        equip_id=equip_id,
                        run_id=run_id,
                        error_type=type(representation_exc).__name__,
                        error=str(representation_exc)[:200],
                    )

        # ===== Phase 8: Drift + episode schema normalization =====
        if representation_score_suppressed:
            Console.warn(
                "Representation authority skipped drift postprocess because scoring was suppressed",
                component="REPRESENTATION",
                equip_id=equip_id,
                run_id=run_id,
            )
        else:
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
            meta=meta,
            build_sensor_analytics_context_fn=build_sensor_analytics_context,
            logger=Console,
            equip=equip,
            representation_result=representation_shadow,
            representation_authority_active=representation_authority_policy.active,
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
            iforest_detector=detectors["iforest_detector"],
            omr_detector=detectors["omr_detector"],
            seasonal_patterns=seasonal_patterns,
            cfg=cfg,
            sensor_context=sensor_context,
            fusion_weights_used=fusion_weights_used,
            record_episode_fn=record_episode,
            equip=equip,
            pca_detector=detectors["pca_detector"],
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
            representation_result=representation_shadow,
            representation_authority_active=representation_authority_policy.active,
            max_total_rows=10000,
        )
        rows_written = persist_stage.rows_written
        raw_train = persist_stage.raw_train
        raw_score = persist_stage.raw_score
        sensor_context = persist_stage.sensor_context

        # FORECASTING_DISABLED:
        # Forecast and RUL pipeline is intentionally disabled in current runtime.
        # Re-enable by restoring ForecastEngine import/stub wiring and forecasting stage.
        Console.info(
            "Forecasting and RUL estimation are disabled for this run "
            "(runtime.phases.forecast=False in ACM_Config). "
            "Set runtime.phases.forecast=True to enable.",
            component="FORECAST",
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

        _elapsed_s = (datetime.now() - run_start_time).total_seconds() if run_start_time else 0
        _max_z = f"{float(frame['fused'].abs().max()):.2f}" if frame is not None and "fused" in frame.columns and len(frame) > 0 else "?"
        _ep_count = len(episodes) if episodes is not None else 0
        Console.info(
            f"RUN END: outcome={outcome} elapsed={_elapsed_s:.0f}s "
            f"max_fused_z={_max_z} episodes={_ep_count} rows_written={rows_written}",
            component="RUN",
        )

    except Exception as e:
        # Capture error for finalization (must be 'FAIL' to match Runs table constraint).
        outcome = "FAIL"
        err_json = serialize_run_exception(e)
        
        # ACM_Runs metadata is written in finally block (includes error_message).
        Console.error(
            f"Pipeline failed with unhandled exception ({type(e).__name__}): {e}. "
            f"This run will be marked FAIL in ACM_Runs. Check ACM_RunLogs for full trace.",
            component="RUN",
            equip=equip,
            run_id=run_id,
            error_type=type(e).__name__,
            error=str(e)[:500],
        )
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
                frame=frame,
                episodes=episodes,
                score_out=score_out,
                regime_quality_ok=regime_quality_ok,
                model_state=model_state,
                rows_read=rows_read,
                train=train,
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
                observability_enabled=True,
                record_data_quality_fn=record_data_quality,
                record_run_fn=record_run,
                record_batch_processed_fn=record_batch_processed,
                record_health_score_fn=record_health_score,
                record_error_fn=record_error,
                zero_day_status=zero_day_status,
                representation_status=build_representation_run_status(representation_shadow),
                span_ctx=_span_ctx,
                root_span=root_span,
                close_run_span_fn=close_run_span,
                shutdown_run_observability_fn=shutdown_run_observability,
            )
        )

    return


if __name__ == "__main__":
    main()

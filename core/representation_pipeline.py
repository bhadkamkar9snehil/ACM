from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd

from core.observability import Console
from core.representation_contracts import (
    BaselineGovernanceDecision,
    CompatibilityStatus,
    ContextAssignment,
    EligibilityDecision,
    ObservationIntegrity,
    OperationalGrades,
    RepresentationPipelineResult,
    RepresentationRefs,
    RuntimeMode,
    StateSnapshot,
)
from core.signal_profiler import build_signal_profile_summary


def _meta_get(meta: Any, key: str, default: Any = None) -> Any:
    if isinstance(meta, dict):
        return meta.get(key, default)
    return getattr(meta, key, default)


def _coerce_dt(value: Any) -> Optional[datetime]:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, datetime):
        return value
    try:
        return pd.Timestamp(value).to_pydatetime()
    except Exception:
        return None


def _infer_sampling_seconds(df: pd.DataFrame, meta: Any) -> Optional[float]:
    meta_sampling = _meta_get(meta, "sampling_seconds", None)
    if meta_sampling not in (None, 0):
        try:
            return float(meta_sampling)
        except Exception:
            pass
    if len(df.index) < 2 or not isinstance(df.index, pd.DatetimeIndex):
        return None
    diffs = df.index.to_series().diff().dropna().dt.total_seconds()
    if diffs.empty:
        return None
    med = float(diffs.median())
    if not np.isfinite(med) or med <= 0:
        return None
    return med


def _expected_rows(df: pd.DataFrame, sampling_seconds: Optional[float]) -> int:
    if df.empty:
        return 0
    if sampling_seconds is None or sampling_seconds <= 0:
        return int(len(df))
    if not isinstance(df.index, pd.DatetimeIndex):
        return int(len(df))
    span_seconds = max(0.0, (df.index.max() - df.index.min()).total_seconds())
    return max(1, int(round(span_seconds / sampling_seconds)) + 1)


def _missingness_grade(missing_ratio: float) -> str:
    if missing_ratio <= 0.05:
        return "GOOD"
    if missing_ratio <= 0.20:
        return "FAIR"
    return "POOR"


def _integrity_grade(integrity: ObservationIntegrity) -> str:
    if integrity.coverage_ratio >= 0.95 and integrity.missingness_grade == "GOOD":
        return "GOOD"
    if integrity.coverage_ratio >= 0.80 and integrity.missingness_grade in {"GOOD", "FAIR"}:
        return "FAIR"
    return "POOR"


def _build_observation_integrity(df: pd.DataFrame, meta: Any) -> ObservationIntegrity:
    observed_rows = int(len(df))
    numeric = df.select_dtypes(include=[np.number]) if not df.empty else pd.DataFrame(index=df.index)
    expected_rows = _expected_rows(df, _infer_sampling_seconds(df, meta))
    coverage_ratio = float(observed_rows / expected_rows) if expected_rows > 0 else 0.0
    coverage_ratio = max(0.0, min(1.0, coverage_ratio))

    if numeric.shape[1] > 0 and observed_rows > 0:
        missing_ratio = float(numeric.isna().mean().mean())
        effective_signal_count = int((numeric.notna().any(axis=0)).sum())
    else:
        missing_ratio = 1.0 if observed_rows else 0.0
        effective_signal_count = 0

    return ObservationIntegrity(
        coverage_ratio=coverage_ratio,
        stale_ratio=0.0,
        missingness_grade=_missingness_grade(missing_ratio),
        effective_signal_count=effective_signal_count,
        expected_rows=expected_rows,
        observed_rows=observed_rows,
        duplicate_rows_removed=int(_meta_get(meta, "dup_timestamps_removed", 0) or 0),
        future_rows_dropped=int(_meta_get(meta, "future_rows_dropped", 0) or 0),
    )


def _build_state_snapshot(
    *,
    df: pd.DataFrame,
    meta: Any,
    equip_id: int,
    run_id: str,
    window_label: str,
) -> Optional[StateSnapshot]:
    if df is None or df.empty:
        return None
    if isinstance(df.index, pd.DatetimeIndex):
        source_start = _coerce_dt(df.index.min())
        source_end = _coerce_dt(df.index.max())
    else:
        source_start = _coerce_dt(_meta_get(meta, "start_ts", None))
        source_end = _coerce_dt(_meta_get(meta, "end_ts", None))

    return StateSnapshot(
        asset_id=int(equip_id),
        batch_end_time=source_end,
        run_id=str(run_id),
        source_window_start=source_start,
        source_window_end=source_end,
        window_label=window_label,
        integrity=_build_observation_integrity(df, meta),
    )


def _resolve_runtime_mode(meta: Any) -> RuntimeMode:
    if bool(_meta_get(meta, "is_coldstart_run", False)):
        return RuntimeMode.BASELINE_FORMATION
    return RuntimeMode.ONLINE_SCORING


def _baseline_governance_for_mode(runtime_mode: RuntimeMode) -> BaselineGovernanceDecision:
    readiness_state = "READY" if runtime_mode == RuntimeMode.ONLINE_SCORING else "FORMING"
    return BaselineGovernanceDecision(
        runtime_mode=runtime_mode,
        readiness_state=readiness_state,
        baseline_candidate_state="UNASSESSED",
        contamination_verdict="UNASSESSED",
        freeze_state="UNASSESSED",
        shadow_refresh_state="UNASSESSED",
        reason_codes=("shadow_mode_not_authoritative",),
    )


def run_representation_pipeline(
    *,
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    meta: Any,
    cfg: dict[str, Any],
    equip_id: int,
    run_id: str,
    logger: Any = Console,
) -> RepresentationPipelineResult:
    _ = cfg
    train_state = _build_state_snapshot(
        df=train_df,
        meta=meta,
        equip_id=equip_id,
        run_id=run_id,
        window_label="train",
    )
    score_state = _build_state_snapshot(
        df=score_df,
        meta=meta,
        equip_id=equip_id,
        run_id=run_id,
        window_label="score",
    )
    runtime_mode = _resolve_runtime_mode(meta)
    baseline_governance = _baseline_governance_for_mode(runtime_mode)
    signal_summary = build_signal_profile_summary(
        score_df if score_df is not None and not score_df.empty else train_df
    )
    context = ContextAssignment()
    compatibility = CompatibilityStatus()
    eligibility = EligibilityDecision(
        authoritative=False,
        score_allowed=bool(score_state),
        learn_allowed=False,
        suppressed_reason_codes=("shadow_mode_not_authoritative",) if score_state else ("no_score_rows",),
    )
    refs = RepresentationRefs()

    integrity_reference = score_state.integrity if score_state is not None else None
    confidence = 0.0 if integrity_reference is None else float(integrity_reference.coverage_ratio)
    grades = OperationalGrades(
        representation_confidence=confidence,
        input_integrity_grade="UNASSESSED"
        if integrity_reference is None
        else _integrity_grade(integrity_reference),
        context_stability_grade=context.context_stability,
    )

    result = RepresentationPipelineResult(
        enabled=True,
        authoritative=False,
        run_id=str(run_id),
        equip_id=int(equip_id),
        train_state=train_state,
        score_state=score_state,
        signal_summary=signal_summary,
        context=context,
        compatibility=compatibility,
        eligibility=eligibility,
        baseline_governance=baseline_governance,
        refs=refs,
        grades=grades,
        notes=("shadow_mode_not_authoritative", "contracts_slice"),
    )

    logger.info(
        "Representation shadow pipeline completed",
        component="REPRESENTATION",
        equip_id=int(equip_id),
        run_id=str(run_id),
        runtime_mode=result.baseline_governance.runtime_mode.value,
        score_rows=result.score_state_rows(),
        authoritative=False,
    )
    return result

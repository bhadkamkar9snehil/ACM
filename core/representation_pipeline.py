from __future__ import annotations

from typing import Any

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
)
from core.signal_profiler import build_signal_profile_summary
from core.state_builder import build_state_snapshot


def _meta_get(meta: Any, key: str, default: Any = None) -> Any:
    if isinstance(meta, dict):
        return meta.get(key, default)
    return getattr(meta, key, default)


def _integrity_grade(integrity: ObservationIntegrity) -> str:
    if integrity.coverage_ratio >= 0.95 and integrity.missingness_grade == "GOOD":
        return "GOOD"
    if integrity.coverage_ratio >= 0.80 and integrity.missingness_grade in {"GOOD", "FAIR"}:
        return "FAIR"
    return "POOR"


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
    train_state = build_state_snapshot(
        df=train_df,
        meta=meta,
        equip_id=equip_id,
        run_id=run_id,
        window_label="train",
    )
    score_state = build_state_snapshot(
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

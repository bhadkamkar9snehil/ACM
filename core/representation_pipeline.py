from __future__ import annotations

from dataclasses import replace
from typing import Any

import pandas as pd

from core.baseline_governor import build_shadow_baseline_governance
from core.comparability_engine import evaluate_eligibility
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


def _integrity_grade(integrity: ObservationIntegrity) -> str:
    if integrity.coverage_ratio >= 0.95 and integrity.missingness_grade == "GOOD":
        return "GOOD"
    if integrity.coverage_ratio >= 0.80 and integrity.missingness_grade in {"GOOD", "FAIR"}:
        return "FAIR"
    return "POOR"


def _score_or_train_integrity(result: RepresentationPipelineResult) -> ObservationIntegrity | None:
    if result.score_state is not None:
        return result.score_state.integrity
    if result.train_state is not None:
        return result.train_state.integrity
    return None


def _eligibility_integrity(result: RepresentationPipelineResult) -> ObservationIntegrity | None:
    if (
        result.baseline_governance.runtime_mode == RuntimeMode.BASELINE_FORMATION
        and result.train_state is not None
    ):
        return result.train_state.integrity
    if result.score_state is not None:
        return result.score_state.integrity
    if (
        result.baseline_governance.runtime_mode == RuntimeMode.CONTROLLED_ADAPTATION
        and result.train_state is not None
    ):
        return result.train_state.integrity
    return None


def _representation_confidence(
    integrity: ObservationIntegrity | None,
    context: ContextAssignment,
) -> float:
    if integrity is None:
        return 0.0
    confidence = float(integrity.coverage_ratio)
    if context.context_label != "UNKNOWN":
        confidence = min(confidence, max(0.0, min(1.0, float(context.context_confidence))))
    return confidence


def _build_grades(
    integrity: ObservationIntegrity | None,
    context: ContextAssignment,
) -> OperationalGrades:
    return OperationalGrades(
        representation_confidence=_representation_confidence(integrity, context),
        input_integrity_grade="UNASSESSED"
        if integrity is None
        else _integrity_grade(integrity),
        context_stability_grade=context.context_stability,
    )


def _merge_notes(existing: tuple[str, ...], *new_notes: str) -> tuple[str, ...]:
    merged = list(existing)
    seen = set(existing)
    for note in new_notes:
        note_value = str(note).strip()
        if not note_value or note_value in seen:
            continue
        merged.append(note_value)
        seen.add(note_value)
    return tuple(merged)


def enrich_representation_shadow(
    result: RepresentationPipelineResult,
    *,
    cfg: dict[str, Any],
    context: ContextAssignment | None = None,
    compatibility: CompatibilityStatus | None = None,
    baseline_governance: BaselineGovernanceDecision | None = None,
    logger: Any = Console,
) -> RepresentationPipelineResult:
    """Re-evaluate shadow comparability after later stages produce more context."""
    if not result.enabled:
        return result

    next_context = context or result.context
    next_compatibility = compatibility or result.compatibility
    next_baseline_governance = baseline_governance or result.baseline_governance
    integrity = _eligibility_integrity(result)

    if integrity is None:
        eligibility = EligibilityDecision(
            authoritative=False,
            score_allowed=False,
            learn_allowed=False,
            suppressed_reason_codes=("no_score_rows",),
        )
    else:
        eligibility = evaluate_eligibility(
            integrity=integrity,
            context=next_context,
            compatibility=next_compatibility,
            baseline_governance=next_baseline_governance,
            cfg=cfg,
            authoritative=False,
        )

    updated = replace(
        result,
        context=next_context,
        compatibility=next_compatibility,
        eligibility=eligibility,
        baseline_governance=next_baseline_governance,
        grades=_build_grades(_score_or_train_integrity(result), next_context),
        notes=_merge_notes(
            result.notes,
            "comparability_shadow_evaluated",
        ),
    )

    logger.info(
        "Representation shadow comparability evaluated",
        component="REPRESENTATION",
        equip_id=updated.equip_id,
        run_id=updated.run_id,
        score_allowed=updated.eligibility.score_allowed,
        learn_allowed=updated.eligibility.learn_allowed,
        suppressed=len(updated.eligibility.suppressed_reason_codes),
        degraded=len(updated.eligibility.degraded_reason_codes),
        authoritative=False,
    )
    return updated


def run_representation_pipeline(
    *,
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    meta: Any,
    cfg: dict[str, Any],
    equip_id: int,
    run_id: str,
    coldstart_complete: bool | None = None,
    logger: Any = Console,
) -> RepresentationPipelineResult:
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
    baseline_governance = build_shadow_baseline_governance(
        meta=meta,
        coldstart_complete=coldstart_complete,
    )
    signal_summary = build_signal_profile_summary(
        score_df if score_df is not None and not score_df.empty else train_df
    )
    context = ContextAssignment()
    compatibility = CompatibilityStatus()
    refs = RepresentationRefs()
    integrity = score_state.integrity if score_state is not None else (
        train_state.integrity if train_state is not None else None
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
        eligibility=EligibilityDecision(),
        baseline_governance=baseline_governance,
        refs=refs,
        grades=_build_grades(integrity, context),
        notes=("shadow_mode_not_authoritative", "contracts_slice"),
    )
    result = enrich_representation_shadow(result, cfg=cfg, logger=logger)

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


__all__ = ["enrich_representation_shadow", "run_representation_pipeline"]

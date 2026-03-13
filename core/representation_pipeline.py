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
    RepresentationAuthorityPolicy,
    RepresentationPipelineResult,
    RepresentationRefs,
    RuntimeMode,
)
from core.schema_drift_manager import compatibility_status_from_drift
from core.signal_profiler import profile_signal_frame, summarize_signal_profiles
from core.state_builder import build_state_snapshot
from utils.config_dict import cfg_get as _cfg_get


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


def _normalize_authority_mode(raw_mode: Any) -> str:
    mode = str(raw_mode or "shadow").strip().lower()
    if mode not in {"shadow", "validation"}:
        return "shadow"
    return mode


def resolve_representation_authority_policy(
    *,
    cfg: dict[str, Any],
    args: Any | None = None,
) -> RepresentationAuthorityPolicy:
    authority_cfg = _cfg_get(cfg or {}, "representation.authority", {}) or {}
    cli_mode = getattr(args, "representation_authority", None)
    mode = _normalize_authority_mode(cli_mode or authority_cfg.get("mode", "shadow"))
    historical_replay = bool(getattr(args, "start_time", None))
    allow_live_validation = bool(authority_cfg.get("allow_live_validation", False))

    if mode == "validation":
        if historical_replay:
            return RepresentationAuthorityPolicy(
                mode=mode,
                active=True,
                reason="historical_replay_validation",
                historical_replay=True,
            )
        if allow_live_validation:
            return RepresentationAuthorityPolicy(
                mode=mode,
                active=True,
                reason="live_validation_enabled",
                historical_replay=False,
            )
        return RepresentationAuthorityPolicy(
            mode=mode,
            active=False,
            reason="validation_requires_replay_or_allow_live_validation",
            historical_replay=False,
        )

    return RepresentationAuthorityPolicy(
        mode="shadow",
        active=False,
        reason="shadow_default",
        historical_replay=historical_replay,
    )


def apply_representation_authority(
    result: RepresentationPipelineResult,
    *,
    policy: RepresentationAuthorityPolicy,
    logger: Any = Console,
) -> RepresentationPipelineResult:
    if not result.enabled:
        return result
    if not policy.active:
        return result
    if result.authoritative and result.eligibility.authoritative:
        return result

    updated = replace(
        result,
        authoritative=True,
        eligibility=replace(result.eligibility, authoritative=True),
        notes=_merge_notes(
            result.notes,
            "validation_authority_active",
            f"authority_policy:{policy.mode}",
            f"authority_reason:{policy.reason}",
        ),
    )
    logger.info(
        "Representation validation authority activated",
        component="REPRESENTATION",
        equip_id=updated.equip_id,
        run_id=updated.run_id,
        mode=policy.mode,
        reason=policy.reason,
    )
    return updated


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


def refresh_representation_runtime_authority(
    result: RepresentationPipelineResult,
    *,
    cfg: dict[str, Any],
    policy: RepresentationAuthorityPolicy | None = None,
    context: ContextAssignment | None = None,
    meta: Any | None = None,
    feature_schema_drift: Any | None = None,
    basis_drift: Any | None = None,
    baseline_contamination_verdict: str = "unknown",
    freeze_changes: Any | None = None,
    refit_requested: bool = False,
    logger: Any = Console,
) -> RepresentationPipelineResult:
    """Refresh runtime comparability and, when active, reapply representation authority.

    This keeps `core.acm` from repeating the same compatibility/baseline-governance
    assembly every time later runtime stages produce new context or drift evidence.
    """
    compatibility = compatibility_status_from_drift(
        feature_schema_drift=feature_schema_drift,
        basis_drift=basis_drift,
    )
    baseline_governance = build_shadow_baseline_governance(
        meta=meta,
        baseline_contamination_verdict=baseline_contamination_verdict,
        freeze_changes=freeze_changes,
        refit_requested=refit_requested,
    )
    updated = enrich_representation_shadow(
        result,
        cfg=cfg,
        context=context,
        compatibility=compatibility,
        baseline_governance=baseline_governance,
        logger=logger,
    )
    if policy is None:
        return updated
    return apply_representation_authority(
        updated,
        policy=policy,
        logger=logger,
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
    )
    profile_source_df = score_df if score_df is not None and not score_df.empty else train_df
    signal_profiles = tuple(profile_signal_frame(profile_source_df))
    signal_summary = summarize_signal_profiles(signal_profiles)
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
        signal_profiles=signal_profiles,
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


__all__ = [
    "apply_representation_authority",
    "enrich_representation_shadow",
    "refresh_representation_runtime_authority",
    "resolve_representation_authority_policy",
    "run_representation_pipeline",
]

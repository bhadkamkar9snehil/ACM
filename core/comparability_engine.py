"""
Shadow comparability policy for governed ACM representation.

This module owns the typed `score_allowed` / `learn_allowed` decision contract.
The current implementation is intentionally shadow-only: it evaluates the
representation state and emits explicit reason codes without changing runtime
score authority.
"""

from __future__ import annotations

from typing import Any, Iterable, Tuple

from core.representation_contracts import (
    BaselineGovernanceDecision,
    CompatibilityStatus,
    ContextAssignment,
    EligibilityDecision,
    ObservationIntegrity,
    RuntimeMode,
)
from utils.config_dict import cfg_get as _cfg_get


_DEFAULT_MIN_COVERAGE_RATIO = 0.80
_DEFAULT_MAX_STALE_RATIO = 0.25
_DEFAULT_MIN_EFFECTIVE_SIGNAL_COUNT = 1
_DEFAULT_MIN_CONTEXT_CONFIDENCE = 0.50
_TRANSITION_BLOCKERS = {"TRANSIENT", "TRIP", "STARTUP", "SHUTDOWN"}
_BLOCKING_COMPATIBILITY = {
    "ADDITIVE_GROWTH",
    "BLOCKED",
    "BASIS_UNAVAILABLE",
    "BROKEN",
    "INCOMPATIBLE",
    "ORDER_MISMATCH",
    "PERMANENT_TAG_LOSS",
    "REPRESENTATION_BREAK",
    "REQUALIFICATION_REQUIRED",
    "REQUALIFY_REQUIRED",
    "SCHEMA_BREAK",
    "TEMPORARY_TAG_LOSS",
}
_PENDING_COMPATIBILITY = {"PENDING", "UNASSESSED", "UNKNOWN", "UNBOUND"}
_READY_BASELINE_STATES = {"ACTIVE", "READY"}
_CLEAR_CONTAMINATION_STATES = {"CLEAR", "NONE"}
_ADAPTATION_REFRESH_ALLOWED = {"ALLOWED", "ENABLED", "READY", "SHADOW_REFRESH_ALLOWED"}


def _policy(cfg: dict[str, Any], key: str, default: Any) -> Any:
    policy = _cfg_get(cfg or {}, "representation.comparability", {}) or {}
    return policy.get(key, default)


def _unique_reasons(reasons: Iterable[str]) -> Tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        reason_value = str(reason).strip()
        if not reason_value or reason_value in seen:
            continue
        ordered.append(reason_value)
        seen.add(reason_value)
    return tuple(ordered)


def _is_blocking_compatibility(status: str) -> bool:
    return str(status).strip().upper() in _BLOCKING_COMPATIBILITY


def _is_pending_compatibility(status: str) -> bool:
    return str(status).strip().upper() in _PENDING_COMPATIBILITY


def evaluate_eligibility(
    *,
    integrity: ObservationIntegrity,
    context: ContextAssignment,
    compatibility: CompatibilityStatus,
    baseline_governance: BaselineGovernanceDecision,
    cfg: dict[str, Any],
    authoritative: bool = False,
) -> EligibilityDecision:
    """
    Evaluate shadow comparability for one governed batch state.

    The output is explicit even when not authoritative so replay can compare
    current ACM scoring against the future representation-governed contract.
    """
    suppressed: list[str] = []
    degraded: list[str] = []

    min_coverage_ratio = float(_policy(cfg, "min_coverage_ratio", _DEFAULT_MIN_COVERAGE_RATIO))
    max_stale_ratio = float(_policy(cfg, "max_stale_ratio", _DEFAULT_MAX_STALE_RATIO))
    min_effective_signal_count = int(
        _policy(cfg, "min_effective_signal_count", _DEFAULT_MIN_EFFECTIVE_SIGNAL_COUNT)
    )
    min_context_confidence = float(
        _policy(cfg, "min_context_confidence", _DEFAULT_MIN_CONTEXT_CONFIDENCE)
    )
    suppress_on_ambiguous_context = bool(_policy(cfg, "suppress_on_ambiguous_context", True))
    suppress_on_transition = bool(_policy(cfg, "suppress_on_transition", True))
    suppress_on_novel_context = bool(_policy(cfg, "suppress_on_novel_context", True))

    runtime_mode = baseline_governance.runtime_mode
    readiness_state = str(baseline_governance.readiness_state).strip().upper()
    contamination_verdict = str(baseline_governance.contamination_verdict).strip().upper()
    shadow_refresh_state = str(baseline_governance.shadow_refresh_state).strip().upper()

    if runtime_mode == RuntimeMode.BOOTSTRAP_NOT_READY:
        suppressed.append("runtime_mode_not_ready")
    elif runtime_mode == RuntimeMode.BASELINE_FORMATION:
        suppressed.append("baseline_formation_scoring_disabled")
    elif runtime_mode == RuntimeMode.SCHEMA_BREAK_REQUALIFICATION:
        suppressed.append("schema_break_requalification_required")

    integrity_blocked = False
    if integrity.observed_rows <= 0:
        suppressed.append("no_score_rows")
        integrity_blocked = True
    if integrity.coverage_ratio < min_coverage_ratio:
        suppressed.append("insufficient_coverage")
        integrity_blocked = True
    if integrity.stale_ratio > max_stale_ratio:
        suppressed.append("stale_inputs")
        integrity_blocked = True
    if integrity.effective_signal_count < min_effective_signal_count:
        suppressed.append("insufficient_effective_signals")
        integrity_blocked = True
    if str(integrity.missingness_grade).strip().upper() == "POOR":
        suppressed.append("poor_missingness")
        integrity_blocked = True

    compatibility_blocked = False
    if _is_blocking_compatibility(compatibility.schema_compatibility):
        suppressed.append("schema_incompatible")
        compatibility_blocked = True
    elif _is_pending_compatibility(compatibility.schema_compatibility):
        degraded.append("schema_compatibility_pending")

    if _is_blocking_compatibility(compatibility.basis_compatibility):
        suppressed.append("basis_incompatible")
        compatibility_blocked = True
    elif _is_pending_compatibility(compatibility.basis_compatibility):
        degraded.append("basis_compatibility_pending")

    if _is_blocking_compatibility(compatibility.baseline_compatibility):
        suppressed.append("baseline_incompatible")
        compatibility_blocked = True
    elif _is_pending_compatibility(compatibility.baseline_compatibility):
        degraded.append("baseline_compatibility_pending")

    if compatibility.invalidated_features:
        degraded.append("invalidated_features_present")

    if runtime_mode == RuntimeMode.ONLINE_SCORING:
        if readiness_state not in _READY_BASELINE_STATES:
            suppressed.append("baseline_not_ready")
        if contamination_verdict and contamination_verdict not in _CLEAR_CONTAMINATION_STATES:
            if contamination_verdict in {"CONTAMINATED", "FAILED"}:
                suppressed.append("baseline_contaminated")
            elif contamination_verdict == "SUSPECT":
                degraded.append("baseline_contamination_suspect")
            else:
                degraded.append("baseline_contamination_unassessed")

        if context.context_label == "UNKNOWN":
            suppressed.append("context_unknown")
        if str(context.context_stability).strip().upper() == "UNASSESSED":
            suppressed.append("context_unassessed")
        if suppress_on_novel_context and bool(context.is_novel):
            suppressed.append("context_novel")
        if suppress_on_ambiguous_context and bool(context.is_ambiguous):
            suppressed.append("context_ambiguous")
        if suppress_on_transition and str(context.transition_status).strip().upper() in _TRANSITION_BLOCKERS:
            suppressed.append("context_transition_active")
        if (
            context.context_label != "UNKNOWN"
            and context.context_confidence < min_context_confidence
            and str(context.context_stability).strip().upper() != "UNASSESSED"
        ):
            suppressed.append("context_low_confidence")

    learn_allowed = False
    if runtime_mode == RuntimeMode.BASELINE_FORMATION:
        learn_allowed = not (integrity_blocked or compatibility_blocked)
    elif runtime_mode == RuntimeMode.CONTROLLED_ADAPTATION:
        learn_allowed = (
            shadow_refresh_state in _ADAPTATION_REFRESH_ALLOWED
            and not (integrity_blocked or compatibility_blocked)
        )

    score_allowed = (
        runtime_mode == RuntimeMode.ONLINE_SCORING
        and not suppressed
    )

    return EligibilityDecision(
        authoritative=bool(authoritative),
        score_allowed=bool(score_allowed),
        learn_allowed=bool(learn_allowed),
        degraded_reason_codes=_unique_reasons(degraded),
        suppressed_reason_codes=_unique_reasons(suppressed),
    )


__all__ = ["evaluate_eligibility"]

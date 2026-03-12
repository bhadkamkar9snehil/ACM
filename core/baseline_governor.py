"""
Shadow baseline-governance owner for representation mode decisions.

This module centralizes runtime-mode, readiness, contamination, freeze, and
shadow-refresh semantics without taking production authority away from the
existing coldstart, lifecycle, retrain, or EWM owners.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from core.representation_contracts import BaselineGovernanceDecision, RuntimeMode


def _meta_get(meta: Any, key: str, default: Any = None) -> Any:
    if isinstance(meta, dict):
        return meta.get(key, default)
    return getattr(meta, key, default)


def _normalize_verdict(value: Any, default: str = "UNASSESSED") -> str:
    text = str(value).strip().upper()
    return text or default


def resolve_runtime_mode(
    *,
    meta: Any,
    coldstart_complete: Optional[bool] = None,
    refit_requested: bool = False,
) -> RuntimeMode:
    """Resolve the intended runtime mode from existing ACM runtime signals."""
    if coldstart_complete is False:
        return RuntimeMode.BOOTSTRAP_NOT_READY

    if bool(_meta_get(meta, "schema_break_requalification", False)):
        return RuntimeMode.SCHEMA_BREAK_REQUALIFICATION

    if bool(_meta_get(meta, "is_coldstart_run", False)):
        return RuntimeMode.BASELINE_FORMATION

    if bool(refit_requested):
        return RuntimeMode.CONTROLLED_ADAPTATION

    return RuntimeMode.ONLINE_SCORING


def _readiness_state(runtime_mode: RuntimeMode) -> str:
    if runtime_mode == RuntimeMode.BOOTSTRAP_NOT_READY:
        return "NOT_READY"
    if runtime_mode == RuntimeMode.BASELINE_FORMATION:
        return "FORMING"
    if runtime_mode == RuntimeMode.SCHEMA_BREAK_REQUALIFICATION:
        return "REQUALIFY_REQUIRED"
    return "READY"


def _baseline_candidate_state(runtime_mode: RuntimeMode) -> str:
    if runtime_mode == RuntimeMode.BOOTSTRAP_NOT_READY:
        return "NOT_READY"
    if runtime_mode == RuntimeMode.BASELINE_FORMATION:
        return "COLLECTING_TRUSTED_WINDOW"
    if runtime_mode == RuntimeMode.CONTROLLED_ADAPTATION:
        return "SHADOW_REFRESH_CANDIDATE"
    if runtime_mode == RuntimeMode.SCHEMA_BREAK_REQUALIFICATION:
        return "REQUALIFICATION_REQUIRED"
    return "ACTIVE_PACKAGE"


def _freeze_state(freeze_changes: Optional[Mapping[Any, str]]) -> str:
    if freeze_changes is None:
        return "UNASSESSED"
    if not freeze_changes:
        return "OK"

    normalized = {_normalize_verdict(value) for value in freeze_changes.values()}
    if "FROZEN" in normalized:
        return "FROZEN"
    if "RESUMED" in normalized:
        return "RESUMED"
    return "OK"


def _shadow_refresh_state(runtime_mode: RuntimeMode, refit_requested: bool) -> str:
    if runtime_mode == RuntimeMode.BASELINE_FORMATION:
        return "LEARNING_ALLOWED"
    if runtime_mode == RuntimeMode.CONTROLLED_ADAPTATION or refit_requested:
        return "REQUESTED"
    return "UNASSESSED"


def build_shadow_baseline_governance(
    *,
    meta: Any,
    coldstart_complete: Optional[bool] = None,
    baseline_contamination_verdict: str = "unknown",
    freeze_changes: Optional[Mapping[Any, str]] = None,
    refit_requested: bool = False,
) -> BaselineGovernanceDecision:
    """Build the current shadow baseline-governance contract."""
    runtime_mode = resolve_runtime_mode(
        meta=meta,
        coldstart_complete=coldstart_complete,
        refit_requested=refit_requested,
    )
    contamination_verdict = _normalize_verdict(baseline_contamination_verdict, default="UNASSESSED")
    freeze_state = _freeze_state(freeze_changes)
    shadow_refresh_state = _shadow_refresh_state(runtime_mode, refit_requested)

    reason_codes: list[str] = []
    if runtime_mode == RuntimeMode.BOOTSTRAP_NOT_READY:
        reason_codes.append("coldstart_not_complete")
    if runtime_mode == RuntimeMode.BASELINE_FORMATION:
        reason_codes.append("coldstart_run_forming_baseline")
    if runtime_mode == RuntimeMode.CONTROLLED_ADAPTATION:
        reason_codes.append("controlled_adaptation_requested")
    if runtime_mode == RuntimeMode.SCHEMA_BREAK_REQUALIFICATION:
        reason_codes.append("schema_requalification_requested")
    if contamination_verdict != "UNASSESSED":
        reason_codes.append(f"baseline_contamination_{contamination_verdict.lower()}")
    if freeze_state == "FROZEN":
        reason_codes.append("ewm_freeze_active")
    elif freeze_state == "RESUMED":
        reason_codes.append("ewm_freeze_resumed")
    if shadow_refresh_state == "REQUESTED":
        reason_codes.append("shadow_refresh_requested")

    return BaselineGovernanceDecision(
        runtime_mode=runtime_mode,
        readiness_state=_readiness_state(runtime_mode),
        baseline_candidate_state=_baseline_candidate_state(runtime_mode),
        contamination_verdict=contamination_verdict,
        freeze_state=freeze_state,
        shadow_refresh_state=shadow_refresh_state,
        promoted_package_version=None,
        reason_codes=tuple(reason_codes),
    )


__all__ = ["build_shadow_baseline_governance", "resolve_runtime_mode"]

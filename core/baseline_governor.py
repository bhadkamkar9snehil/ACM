"""
Shadow baseline-governance owner for representation mode decisions.

This module centralizes runtime-mode, readiness, contamination, freeze, and
shadow-refresh semantics without taking production authority away from the
existing coldstart, lifecycle, retrain, or EWM owners.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

import pandas as pd

from core.representation_contracts import BaselineGovernanceDecision, RuntimeMode
from core.observability import Console

_BASELINE_READY_RUNTIME_MODES = {
    RuntimeMode.ONLINE_SCORING,
    RuntimeMode.CONTROLLED_ADAPTATION,
}
_PENDING_TRUSTED_WINDOW_SOURCES = {"TRUSTED_WINDOW_PENDING"}


@dataclass(frozen=True)
class BaselineSeedDecision:
    train_df: pd.DataFrame
    score_df: pd.DataFrame
    source_code: str
    source_detail: str
    authoritative: bool
    extended: bool = False
    applied_to_runtime: bool = True


@dataclass(frozen=True)
class ColdstartLoadDecision:
    use_existing_models: bool
    reason_code: str


def _meta_get(meta: Any, key: str, default: Any = None) -> Any:
    if isinstance(meta, dict):
        return meta.get(key, default)
    return getattr(meta, key, default)


def _normalize_verdict(value: Any, default: str = "UNASSESSED") -> str:
    text = str(value).strip().upper()
    return text or default


def _meta_set(meta: Any, key: str, value: Any) -> Any:
    if meta is None:
        meta = {}
    if isinstance(meta, dict):
        meta[key] = value
    else:
        setattr(meta, key, value)
    return meta


def legacy_regime_maturity_requires_coldstart(regime_maturity_state: Any) -> bool:
    """
    Transitional interpretation of legacy model lifecycle state.

    This keeps the old `ACM_ActiveModels.RegimeMaturityState` hint in one place
    while runtime-mode and readiness authority migrate into the governed
    baseline contract.
    """
    state = str(regime_maturity_state or "").strip().upper()
    return state in {"", "INITIALIZING", "NONE", "NULL"}


def resolve_coldstart_load_decision(
    *,
    runtime_mode_hint: Any = None,
    regime_maturity_state: Any = None,
) -> ColdstartLoadDecision:
    """
    Resolve whether ACM should use existing models or continue baseline formation.

    Governed runtime mode is authoritative when available. Legacy lifecycle state
    remains only as a fallback while coldstart ownership finishes converging on
    baseline-governor semantics.
    """
    runtime_mode = str(runtime_mode_hint or "").strip().upper()
    if runtime_mode in {
        RuntimeMode.ONLINE_SCORING.value,
        RuntimeMode.CONTROLLED_ADAPTATION.value,
        RuntimeMode.SCHEMA_BREAK_REQUALIFICATION.value,
    }:
        return ColdstartLoadDecision(
            use_existing_models=True,
            reason_code="governed_runtime_ready_for_scoring",
        )
    if runtime_mode in {
        RuntimeMode.BOOTSTRAP_NOT_READY.value,
        RuntimeMode.BASELINE_FORMATION.value,
    }:
        return ColdstartLoadDecision(
            use_existing_models=False,
            reason_code="governed_runtime_requires_baseline_formation",
        )
    return resolve_legacy_coldstart_load_decision(regime_maturity_state)


def resolve_legacy_coldstart_load_decision(regime_maturity_state: Any) -> ColdstartLoadDecision:
    """
    Transitional load-stage owner for whether ACM still needs coldstart batching.

    SmartColdstart may continue to fetch the legacy lifecycle hint from SQL, but
    the meaning of that hint lives here so readiness semantics keep converging
    on baseline-governor ownership.
    """
    if legacy_regime_maturity_requires_coldstart(regime_maturity_state):
        return ColdstartLoadDecision(
            use_existing_models=False,
            reason_code="legacy_maturity_requires_coldstart",
        )
    return ColdstartLoadDecision(
        use_existing_models=True,
        reason_code="legacy_maturity_ready_for_scoring",
    )


def annotate_load_stage_governance_meta(
    meta: Any,
    *,
    can_proceed: bool,
    is_coldstart_run: bool,
    gate_reason: str = "",
) -> Any:
    """
    Stamp explicit governed load-stage readiness hints onto meta.

    This lets downstream runtime resolve mode/readiness from a typed hint
    instead of relying only on the overloaded legacy `coldstart_complete`
    boolean.
    """
    if not can_proceed:
        runtime_mode = RuntimeMode.BOOTSTRAP_NOT_READY.value
        enough_history_to_proceed = False
        baseline_ready = False
    elif is_coldstart_run:
        runtime_mode = RuntimeMode.BASELINE_FORMATION.value
        enough_history_to_proceed = True
        baseline_ready = False
    else:
        runtime_mode = RuntimeMode.ONLINE_SCORING.value
        enough_history_to_proceed = True
        baseline_ready = True

    meta = _meta_set(meta, "baseline_runtime_mode", runtime_mode)
    meta = _meta_set(meta, "enough_history_to_proceed", enough_history_to_proceed)
    meta = _meta_set(meta, "baseline_ready", baseline_ready)
    meta = _meta_set(meta, "coldstart_gate_reason", str(gate_reason or "").strip())
    return meta


def resolve_baseline_seed_decision(
    *,
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    min_points: int,
    is_coldstart: bool,
) -> BaselineSeedDecision:
    """
    Resolve the transitional baseline-seeding plan.

    Coldstart/train-owned baseline sources remain authoritative for now.
    When no authoritative train-owned baseline can be formed, the runtime
    stays in an explicit trusted-window-pending state instead of inventing a
    score-derived baseline slice.
    """
    train_rows = len(train_df)
    if is_coldstart:
        return BaselineSeedDecision(
            train_df=train_df,
            score_df=score_df,
            source_code="coldstart_split",
            source_detail=f"coldstart_split ({train_rows} rows)",
            authoritative=True,
            extended=False,
            applied_to_runtime=True,
        )

    if train_rows >= int(min_points):
        return BaselineSeedDecision(
            train_df=train_df,
            score_df=score_df,
            source_code="existing_train",
            source_detail=f"existing_train ({train_rows} rows)",
            authoritative=True,
            extended=False,
            applied_to_runtime=True,
        )

    if score_df is None or len(score_df) == 0:
        return BaselineSeedDecision(
            train_df=train_df,
            score_df=score_df,
            source_code="none",
            source_detail="no_baseline_seed",
            authoritative=False,
            extended=False,
            applied_to_runtime=False,
        )

    return BaselineSeedDecision(
        train_df=train_df,
        score_df=score_df,
        source_code="trusted_window_pending",
        source_detail=(
            f"trusted window pending (train={train_rows}, "
            f"min_points={int(min_points)}, score_rows={len(score_df)})"
        ),
        authoritative=False,
        extended=False,
        applied_to_runtime=False,
    )


def resolve_runtime_mode(
    *,
    meta: Any,
    refit_requested: bool = False,
) -> RuntimeMode:
    """Resolve the intended runtime mode from existing ACM runtime signals."""
    explicit_runtime_mode = str(_meta_get(meta, "baseline_runtime_mode", "")).strip().upper()
    if explicit_runtime_mode:
        try:
            explicit_mode = RuntimeMode[explicit_runtime_mode]
        except KeyError:
            explicit_mode = None
        else:
            if explicit_mode in {
                RuntimeMode.BOOTSTRAP_NOT_READY,
                RuntimeMode.BASELINE_FORMATION,
            }:
                return explicit_mode

    if bool(_meta_get(meta, "schema_break_requalification", False)):
        return RuntimeMode.SCHEMA_BREAK_REQUALIFICATION

    if bool(_meta_get(meta, "is_coldstart_run", False)):
        return RuntimeMode.BASELINE_FORMATION

    if bool(refit_requested):
        return RuntimeMode.CONTROLLED_ADAPTATION

    if explicit_runtime_mode:
        try:
            return RuntimeMode[explicit_runtime_mode]
        except KeyError:
            pass

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


def _enough_history_to_proceed(runtime_mode: RuntimeMode) -> bool:
    return runtime_mode != RuntimeMode.BOOTSTRAP_NOT_READY


def _baseline_ready(runtime_mode: RuntimeMode) -> bool:
    return runtime_mode in _BASELINE_READY_RUNTIME_MODES


def _normalized_baseline_seed_source(meta: Any) -> str:
    return str(_meta_get(meta, "baseline_seed_source", "")).strip().upper()


def build_shadow_baseline_governance(
    *,
    meta: Any,
    baseline_contamination_verdict: str = "unknown",
    freeze_changes: Optional[Mapping[Any, str]] = None,
    refit_requested: bool = False,
) -> BaselineGovernanceDecision:
    """Build the current shadow baseline-governance contract."""
    runtime_mode = resolve_runtime_mode(
        meta=meta,
        refit_requested=refit_requested,
    )
    contamination_verdict = _normalize_verdict(baseline_contamination_verdict, default="UNASSESSED")
    freeze_state = _freeze_state(freeze_changes)
    shadow_refresh_state = _shadow_refresh_state(runtime_mode, refit_requested)
    baseline_seed_source = _normalized_baseline_seed_source(meta)
    baseline_seed_authoritative = _meta_get(meta, "baseline_seed_authoritative", None)
    baseline_candidate_state = _baseline_candidate_state(runtime_mode)
    baseline_ready = _baseline_ready(runtime_mode)

    reason_codes: list[str] = []
    if runtime_mode == RuntimeMode.BOOTSTRAP_NOT_READY:
        reason_codes.append("coldstart_not_complete")
    if runtime_mode == RuntimeMode.BASELINE_FORMATION:
        reason_codes.append("coldstart_run_forming_baseline")
    if runtime_mode == RuntimeMode.CONTROLLED_ADAPTATION:
        reason_codes.append("controlled_adaptation_requested")
    if runtime_mode == RuntimeMode.SCHEMA_BREAK_REQUALIFICATION:
        reason_codes.append("schema_requalification_requested")
    if baseline_seed_source:
        reason_codes.append(f"baseline_seed_{baseline_seed_source.lower()}")
    if (
        baseline_seed_source in _PENDING_TRUSTED_WINDOW_SOURCES
        and baseline_seed_authoritative is False
    ):
        if runtime_mode == RuntimeMode.ONLINE_SCORING:
            runtime_mode = RuntimeMode.BASELINE_FORMATION
            shadow_refresh_state = "WAITING_FOR_TRUSTED_WINDOW"
        baseline_ready = False
        baseline_candidate_state = "TRUSTED_WINDOW_PENDING"
        reason_codes.append("baseline_trusted_window_pending")
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
        enough_history_to_proceed=_enough_history_to_proceed(runtime_mode),
        baseline_ready=baseline_ready,
        readiness_state=_readiness_state(runtime_mode),
        baseline_candidate_state=baseline_candidate_state,
        contamination_verdict=contamination_verdict,
        freeze_state=freeze_state,
        shadow_refresh_state=shadow_refresh_state,
        promoted_package_version=None,
        reason_codes=tuple(reason_codes),
    )


def seed_baseline(
    train: pd.DataFrame,
    score: pd.DataFrame,
    sql_client: Optional[Any],
    equip_id: int,
    cfg: Mapping[str, Any],
    equip: str = "",
    is_coldstart: bool = False,
    ensure_local_index_fn: Optional[Any] = None,
    apply_non_authoritative_seed: bool = True,
) -> BaselineSeedDecision:
    """
    Resolve and apply the transitional baseline-seeding plan.

    Long-term ownership for baseline-seeding policy lives here.

    If no authoritative train-owned baseline can be formed, the runtime
    receives an explicit trusted-window-pending result and the input frames are
    left untouched.
    """
    del sql_client, equip_id, ensure_local_index_fn  # kept for compatibility

    baseline_cfg = (cfg.get("runtime", {}) or {}).get("baseline", {}) or {}
    min_points = int(baseline_cfg.get("min_points", 300))

    decision = resolve_baseline_seed_decision(
        train_df=train,
        score_df=score,
        min_points=min_points,
        is_coldstart=is_coldstart,
    )
    if not decision.authoritative and not apply_non_authoritative_seed:
        Console.info(
            f"Baseline candidate retained as shadow-only: {decision.source_detail} | applied_to_runtime=False",
            component="BASELINE",
        )
        return BaselineSeedDecision(
            train_df=train,
            score_df=score,
            source_code=decision.source_code,
            source_detail=decision.source_detail,
            authoritative=False,
            extended=decision.extended,
            applied_to_runtime=False,
        )
    if decision.source_code != "none":
        Console.info(
            f"Baseline: {decision.source_detail} | extended={decision.extended}",
            component="BASELINE",
        )
    return decision


def seed_baseline_safe(
    train: pd.DataFrame,
    score: pd.DataFrame,
    sql_client: Optional[Any],
    equip_id: int,
    cfg: Mapping[str, Any],
    equip: str = "",
    is_coldstart: bool = False,
    ensure_local_index_fn: Optional[Any] = None,
    apply_non_authoritative_seed: bool = True,
    logger: Any = Console,
) -> BaselineSeedDecision:
    """Safe wrapper for governed baseline seeding."""
    try:
        return seed_baseline(
            train=train,
            score=score,
            sql_client=sql_client,
            equip_id=equip_id,
            cfg=cfg,
            equip=equip,
            is_coldstart=is_coldstart,
            ensure_local_index_fn=ensure_local_index_fn,
            apply_non_authoritative_seed=apply_non_authoritative_seed,
        )
    except Exception as e:
        logger.warn(
            f"Cold-start baseline setup failed: {e}",
            component="BASELINE",
            equip=equip,
            train_rows=len(train) if train is not None else 0,
            error=str(e)[:200],
        )
        return BaselineSeedDecision(
            train_df=train,
            score_df=score,
            source_code="seed_failed",
            source_detail="seed_failed",
            authoritative=False,
            extended=False,
            applied_to_runtime=False,
        )


__all__ = [
    "annotate_load_stage_governance_meta",
    "ColdstartLoadDecision",
    "BaselineSeedDecision",
    "build_shadow_baseline_governance",
    "legacy_regime_maturity_requires_coldstart",
    "resolve_legacy_coldstart_load_decision",
    "seed_baseline",
    "seed_baseline_safe",
    "resolve_baseline_seed_decision",
    "resolve_runtime_mode",
]

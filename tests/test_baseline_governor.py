from core.baseline_governor import (
    annotate_load_stage_governance_meta,
    BaselineSeedDecision,
    build_shadow_baseline_governance,
    legacy_regime_maturity_requires_coldstart,
    resolve_legacy_coldstart_load_decision,
    seed_baseline,
    resolve_baseline_seed_decision,
    resolve_runtime_mode,
)
from core.representation_contracts import RuntimeMode
import pandas as pd


def test_resolve_runtime_mode_respects_coldstart_completion_first() -> None:
    mode = resolve_runtime_mode(
        meta={"baseline_runtime_mode": "BOOTSTRAP_NOT_READY", "is_coldstart_run": True},
        refit_requested=False,
    )

    assert mode == RuntimeMode.BOOTSTRAP_NOT_READY


def test_resolve_runtime_mode_prefers_explicit_load_stage_bootstrap_hint() -> None:
    mode = resolve_runtime_mode(
        meta={"baseline_runtime_mode": "BOOTSTRAP_NOT_READY"},
        refit_requested=False,
    )

    assert mode == RuntimeMode.BOOTSTRAP_NOT_READY


def test_resolve_runtime_mode_detects_controlled_adaptation() -> None:
    mode = resolve_runtime_mode(
        meta={"is_coldstart_run": False},
        refit_requested=True,
    )

    assert mode == RuntimeMode.CONTROLLED_ADAPTATION


def test_legacy_regime_maturity_requires_coldstart_handles_initializing_and_ready_states() -> None:
    assert legacy_regime_maturity_requires_coldstart(None) is True
    assert legacy_regime_maturity_requires_coldstart("INITIALIZING") is True
    assert legacy_regime_maturity_requires_coldstart("  ") is True
    assert legacy_regime_maturity_requires_coldstart("LEARNING") is False
    assert legacy_regime_maturity_requires_coldstart("CONVERGED") is False


def test_resolve_legacy_coldstart_load_decision_maps_legacy_lifecycle_hint() -> None:
    baseline_window_path = resolve_legacy_coldstart_load_decision("INITIALIZING")
    ready_for_scoring = resolve_legacy_coldstart_load_decision("LEARNING")

    assert baseline_window_path.use_existing_models is False
    assert baseline_window_path.runtime_mode_hint == RuntimeMode.BASELINE_FORMATION
    assert baseline_window_path.reason_code == "legacy_maturity_requires_coldstart"
    assert ready_for_scoring.use_existing_models is True
    assert ready_for_scoring.runtime_mode_hint == RuntimeMode.ONLINE_SCORING
    assert ready_for_scoring.reason_code == "legacy_maturity_ready_for_scoring"


def test_annotate_load_stage_governance_meta_sets_explicit_bootstrap_fields() -> None:
    meta = annotate_load_stage_governance_meta(
        {},
        can_proceed=False,
        is_coldstart_run=True,
        gate_reason="legacy_maturity_requires_coldstart",
    )

    assert meta["baseline_runtime_mode"] == "BOOTSTRAP_NOT_READY"
    assert meta["enough_history_to_proceed"] is False
    assert meta["baseline_ready"] is False
    assert meta["coldstart_gate_reason"] == "legacy_maturity_requires_coldstart"


def test_annotate_load_stage_governance_meta_sets_scoring_fields() -> None:
    meta = annotate_load_stage_governance_meta(
        {},
        can_proceed=True,
        is_coldstart_run=False,
        gate_reason="legacy_maturity_ready_for_scoring",
    )

    assert meta["baseline_runtime_mode"] == "ONLINE_SCORING"
    assert meta["enough_history_to_proceed"] is True
    assert meta["baseline_ready"] is True


def test_build_shadow_baseline_governance_maps_baseline_formation() -> None:
    decision = build_shadow_baseline_governance(
        meta={"is_coldstart_run": True},
    )

    assert decision.runtime_mode == RuntimeMode.BASELINE_FORMATION
    assert decision.enough_history_to_proceed is True
    assert decision.baseline_ready is False
    assert decision.readiness_state == "FORMING"
    assert decision.baseline_candidate_state == "COLLECTING_TRUSTED_WINDOW"
    assert decision.shadow_refresh_state == "LEARNING_ALLOWED"
    assert "coldstart_run_forming_baseline" in decision.reason_codes


def test_build_shadow_baseline_governance_maps_contamination_and_freeze() -> None:
    decision = build_shadow_baseline_governance(
        meta={"is_coldstart_run": False},
        baseline_contamination_verdict="suspect",
        freeze_changes={(1, "sensor_a"): "frozen"},
        refit_requested=True,
    )

    assert decision.runtime_mode == RuntimeMode.CONTROLLED_ADAPTATION
    assert decision.enough_history_to_proceed is True
    assert decision.baseline_ready is True
    assert decision.contamination_verdict == "SUSPECT"
    assert decision.freeze_state == "FROZEN"
    assert decision.shadow_refresh_state == "REQUESTED"
    assert "baseline_contamination_suspect" in decision.reason_codes
    assert "ewm_freeze_active" in decision.reason_codes
    assert "shadow_refresh_requested" in decision.reason_codes


def test_build_shadow_baseline_governance_marks_bootstrap_as_not_ready() -> None:
    decision = build_shadow_baseline_governance(
        meta={"baseline_runtime_mode": "BOOTSTRAP_NOT_READY", "is_coldstart_run": False},
    )

    assert decision.runtime_mode == RuntimeMode.BOOTSTRAP_NOT_READY
    assert decision.enough_history_to_proceed is False
    assert decision.baseline_ready is False


def test_build_shadow_baseline_governance_marks_trusted_window_pending_as_non_authoritative() -> None:
    decision = build_shadow_baseline_governance(
        meta={
            "is_coldstart_run": False,
            "baseline_seed_source": "trusted_window_pending",
            "baseline_seed_authoritative": False,
        },
    )

    assert decision.runtime_mode == RuntimeMode.BASELINE_FORMATION
    assert decision.baseline_ready is False
    assert decision.readiness_state == "FORMING"
    assert decision.baseline_candidate_state == "TRUSTED_WINDOW_PENDING"
    assert "baseline_seed_trusted_window_pending" in decision.reason_codes
    assert "baseline_trusted_window_pending" in decision.reason_codes


def test_resolve_baseline_seed_decision_marks_coldstart_split_authoritative() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="h", name="EntryDateTime")
    train = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0]}, index=idx)
    score = pd.DataFrame({"a": [5.0, 6.0]}, index=pd.date_range("2024-01-01T04:00:00", periods=2, freq="h", name="EntryDateTime"))

    decision = resolve_baseline_seed_decision(
        train_df=train,
        score_df=score,
        min_points=3,
        is_coldstart=True,
    )

    assert isinstance(decision, BaselineSeedDecision)
    assert decision.source_code == "coldstart_split"
    assert decision.authoritative is True


def test_resolve_baseline_seed_decision_marks_trusted_window_pending_without_mutating_runtime_frames() -> None:
    score = pd.DataFrame(
        {"a": list(range(12))},
        index=pd.date_range("2024-01-01", periods=12, freq="h", name="EntryDateTime"),
    )
    train = pd.DataFrame(index=pd.DatetimeIndex([], name="EntryDateTime"))

    decision = resolve_baseline_seed_decision(
        train_df=train,
        score_df=score,
        min_points=5,
        is_coldstart=False,
    )

    assert decision.source_code == "trusted_window_pending"
    assert decision.authoritative is False
    assert decision.applied_to_runtime is False
    assert decision.train_df.empty
    assert len(decision.score_df) == len(score)


def test_seed_baseline_keeps_trusted_window_pending_state_without_runtime_mutation() -> None:
    score = pd.DataFrame(
        {"a": list(range(12))},
        index=pd.date_range("2024-01-01", periods=12, freq="h", name="EntryDateTime"),
    )
    train = pd.DataFrame(index=pd.DatetimeIndex([], name="EntryDateTime"))

    decision = seed_baseline(
        train=train,
        score=score,
        sql_client=None,
        equip_id=1,
        cfg={"runtime": {"baseline": {"min_points": 5}}},
        apply_non_authoritative_seed=True,
    )

    assert decision.source_code == "trusted_window_pending"
    assert decision.authoritative is False
    assert decision.applied_to_runtime is False
    assert decision.train_df.empty
    assert len(decision.score_df) == len(score)

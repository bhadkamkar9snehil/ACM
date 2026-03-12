from core.baseline_governor import (
    build_shadow_baseline_governance,
    resolve_runtime_mode,
)
from core.representation_contracts import RuntimeMode


def test_resolve_runtime_mode_respects_coldstart_completion_first() -> None:
    mode = resolve_runtime_mode(
        meta={"is_coldstart_run": True},
        coldstart_complete=False,
        refit_requested=False,
    )

    assert mode == RuntimeMode.BOOTSTRAP_NOT_READY


def test_resolve_runtime_mode_detects_controlled_adaptation() -> None:
    mode = resolve_runtime_mode(
        meta={"is_coldstart_run": False},
        coldstart_complete=True,
        refit_requested=True,
    )

    assert mode == RuntimeMode.CONTROLLED_ADAPTATION


def test_build_shadow_baseline_governance_maps_baseline_formation() -> None:
    decision = build_shadow_baseline_governance(
        meta={"is_coldstart_run": True},
        coldstart_complete=True,
    )

    assert decision.runtime_mode == RuntimeMode.BASELINE_FORMATION
    assert decision.readiness_state == "FORMING"
    assert decision.baseline_candidate_state == "COLLECTING_TRUSTED_WINDOW"
    assert decision.shadow_refresh_state == "LEARNING_ALLOWED"
    assert "coldstart_run_forming_baseline" in decision.reason_codes


def test_build_shadow_baseline_governance_maps_contamination_and_freeze() -> None:
    decision = build_shadow_baseline_governance(
        meta={"is_coldstart_run": False},
        coldstart_complete=True,
        baseline_contamination_verdict="suspect",
        freeze_changes={(1, "sensor_a"): "frozen"},
        refit_requested=True,
    )

    assert decision.runtime_mode == RuntimeMode.CONTROLLED_ADAPTATION
    assert decision.contamination_verdict == "SUSPECT"
    assert decision.freeze_state == "FROZEN"
    assert decision.shadow_refresh_state == "REQUESTED"
    assert "baseline_contamination_suspect" in decision.reason_codes
    assert "ewm_freeze_active" in decision.reason_codes
    assert "shadow_refresh_requested" in decision.reason_codes

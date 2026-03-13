from core.comparability_engine import evaluate_eligibility
from core.representation_contracts import (
    BaselineGovernanceDecision,
    CompatibilityStatus,
    ContextAssignment,
    ObservationIntegrity,
    RuntimeMode,
)


def _integrity(
    *,
    coverage_ratio: float = 1.0,
    stale_ratio: float = 0.0,
    missingness_grade: str = "GOOD",
    effective_signal_count: int = 3,
    observed_rows: int = 12,
) -> ObservationIntegrity:
    return ObservationIntegrity(
        coverage_ratio=coverage_ratio,
        stale_ratio=stale_ratio,
        missingness_grade=missingness_grade,
        effective_signal_count=effective_signal_count,
        expected_rows=max(observed_rows, 1),
        observed_rows=observed_rows,
    )


def _baseline(
    *,
    runtime_mode: RuntimeMode = RuntimeMode.ONLINE_SCORING,
    enough_history_to_proceed: bool = True,
    baseline_ready: bool = True,
    readiness_state: str = "READY",
    baseline_candidate_state: str = "UNASSESSED",
    contamination_verdict: str = "CLEAR",
    shadow_refresh_state: str = "UNASSESSED",
) -> BaselineGovernanceDecision:
    return BaselineGovernanceDecision(
        runtime_mode=runtime_mode,
        enough_history_to_proceed=enough_history_to_proceed,
        baseline_ready=baseline_ready,
        readiness_state=readiness_state,
        baseline_candidate_state=baseline_candidate_state,
        contamination_verdict=contamination_verdict,
        freeze_state="UNASSESSED",
        shadow_refresh_state=shadow_refresh_state,
    )


def _context(
    *,
    label: str = "REGIME_1",
    confidence: float = 0.9,
    stability: str = "STABLE",
    transition_status: str = "STEADY",
    is_novel: bool = False,
    is_ambiguous: bool = False,
) -> ContextAssignment:
    return ContextAssignment(
        context_id="regime:1" if label != "UNKNOWN" else "unknown",
        context_label=label,
        context_confidence=confidence,
        context_stability=stability,
        transition_status=transition_status,
        is_novel=is_novel,
        is_ambiguous=is_ambiguous,
    )


def test_evaluate_eligibility_allows_good_online_scoring_in_shadow() -> None:
    decision = evaluate_eligibility(
        integrity=_integrity(),
        context=_context(),
        compatibility=CompatibilityStatus(),
        baseline_governance=_baseline(),
        cfg={},
    )

    assert decision.authoritative is False
    assert decision.score_allowed is True
    assert decision.learn_allowed is False
    assert "schema_compatibility_pending" in decision.degraded_reason_codes


def test_evaluate_eligibility_blocks_online_scoring_without_context() -> None:
    decision = evaluate_eligibility(
        integrity=_integrity(),
        context=ContextAssignment(),
        compatibility=CompatibilityStatus(),
        baseline_governance=_baseline(),
        cfg={},
    )

    assert decision.score_allowed is False
    assert "context_unknown" in decision.suppressed_reason_codes
    assert "context_unassessed" in decision.suppressed_reason_codes


def test_evaluate_eligibility_allows_baseline_formation_learning() -> None:
    decision = evaluate_eligibility(
        integrity=_integrity(),
        context=ContextAssignment(),
        compatibility=CompatibilityStatus(),
        baseline_governance=_baseline(runtime_mode=RuntimeMode.BASELINE_FORMATION, readiness_state="FORMING"),
        cfg={},
    )

    assert decision.score_allowed is False
    assert decision.learn_allowed is True
    assert "baseline_formation_scoring_disabled" in decision.suppressed_reason_codes


def test_evaluate_eligibility_blocks_learning_while_trusted_window_is_pending() -> None:
    decision = evaluate_eligibility(
        integrity=_integrity(),
        context=ContextAssignment(),
        compatibility=CompatibilityStatus(),
        baseline_governance=_baseline(
            runtime_mode=RuntimeMode.BASELINE_FORMATION,
            readiness_state="FORMING",
            baseline_ready=False,
            baseline_candidate_state="TRUSTED_WINDOW_PENDING",
        ),
        cfg={},
    )

    assert decision.score_allowed is False
    assert decision.learn_allowed is False
    assert "baseline_formation_scoring_disabled" in decision.suppressed_reason_codes
    assert "baseline_trusted_window_pending" in decision.degraded_reason_codes


def test_evaluate_eligibility_blocks_schema_incompatibility() -> None:
    decision = evaluate_eligibility(
        integrity=_integrity(),
        context=_context(),
        compatibility=CompatibilityStatus(schema_compatibility="INCOMPATIBLE"),
        baseline_governance=_baseline(),
        cfg={},
    )

    assert decision.score_allowed is False
    assert "schema_incompatible" in decision.suppressed_reason_codes


def test_evaluate_eligibility_degrades_suspect_baseline_without_suppressing() -> None:
    decision = evaluate_eligibility(
        integrity=_integrity(),
        context=_context(),
        compatibility=CompatibilityStatus(),
        baseline_governance=_baseline(contamination_verdict="SUSPECT"),
        cfg={},
    )

    assert decision.score_allowed is True
    assert "baseline_contamination_suspect" in decision.degraded_reason_codes
    assert "baseline_contaminated" not in decision.suppressed_reason_codes


def test_evaluate_eligibility_blocks_poor_integrity() -> None:
    decision = evaluate_eligibility(
        integrity=_integrity(coverage_ratio=0.40, missingness_grade="POOR", effective_signal_count=0),
        context=_context(),
        compatibility=CompatibilityStatus(),
        baseline_governance=_baseline(),
        cfg={},
    )

    assert decision.score_allowed is False
    assert "insufficient_coverage" in decision.suppressed_reason_codes
    assert "poor_missingness" in decision.suppressed_reason_codes
    assert "insufficient_effective_signals" in decision.suppressed_reason_codes


def test_evaluate_eligibility_uses_explicit_bootstrap_history_flag() -> None:
    decision = evaluate_eligibility(
        integrity=_integrity(),
        context=_context(),
        compatibility=CompatibilityStatus(),
        baseline_governance=_baseline(
            runtime_mode=RuntimeMode.BOOTSTRAP_NOT_READY,
            enough_history_to_proceed=False,
            baseline_ready=False,
            readiness_state="NOT_READY",
        ),
        cfg={},
    )

    assert decision.score_allowed is False
    assert "runtime_mode_not_ready" in decision.suppressed_reason_codes
    assert "insufficient_history_to_proceed" in decision.degraded_reason_codes

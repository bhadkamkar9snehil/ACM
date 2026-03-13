from core.representation_contracts import (
    REPRESENTATION_VERSION,
    ContextAssignment,
    EligibilityDecision,
    RepresentationPipelineResult,
    RepresentationRefs,
    RuntimeMode,
    SignalProfileSummary,
)


def test_runtime_mode_enum_contains_expected_values() -> None:
    assert RuntimeMode.BOOTSTRAP_NOT_READY.value == "BOOTSTRAP_NOT_READY"
    assert RuntimeMode.BASELINE_FORMATION.value == "BASELINE_FORMATION"
    assert RuntimeMode.ONLINE_SCORING.value == "ONLINE_SCORING"


def test_representation_refs_defaults_are_stable() -> None:
    refs = RepresentationRefs()

    assert refs.representation_version == REPRESENTATION_VERSION
    assert refs.schema_version == "unbound"
    assert refs.basis_signature == "pending"


def test_context_assignment_defaults_to_unknown_and_ambiguous() -> None:
    context = ContextAssignment()

    assert context.context_label == "UNKNOWN"
    assert context.context_confidence == 0.0
    assert context.is_ambiguous is True


def test_eligibility_decision_can_be_shadow_only() -> None:
    decision = EligibilityDecision(
        authoritative=False,
        score_allowed=True,
        learn_allowed=False,
        suppressed_reason_codes=("shadow_mode_not_authoritative",),
    )

    assert decision.authoritative is False
    assert decision.score_allowed is True
    assert decision.learn_allowed is False
    assert decision.suppressed_reason_codes == ("shadow_mode_not_authoritative",)


def test_representation_pipeline_result_score_state_rows_handles_none() -> None:
    result = RepresentationPipelineResult(
        enabled=True,
        authoritative=False,
        run_id="run-1",
        equip_id=7,
        train_state=None,
        score_state=None,
        signal_profiles=(),
        signal_summary=SignalProfileSummary(monitorable_signal_count=0),
        context=ContextAssignment(),
        compatibility=None,  # type: ignore[arg-type]
        eligibility=EligibilityDecision(),
        baseline_governance=None,  # type: ignore[arg-type]
        refs=RepresentationRefs(),
        grades=None,  # type: ignore[arg-type]
    )

    assert result.score_state_rows() == 0

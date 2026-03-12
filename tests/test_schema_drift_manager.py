import pandas as pd

from core.representation_contracts import CompatibilityStatus
from core.schema_drift_manager import (
    apply_feature_schema_alignment,
    classify_feature_schema_drift,
    classify_regime_basis_drift,
    compatibility_status_from_drift,
    validate_cached_model_schema_drift,
)


def test_classify_feature_schema_drift_detects_exact_match() -> None:
    decision = classify_feature_schema_drift(
        ["a", "b"],
        {"train_sensors": ["a", "b"]},
    )

    assert decision.schema_compatibility == "COMPATIBLE"
    assert decision.cache_compatible is True
    assert decision.aligned_columns == ("a", "b")


def test_classify_feature_schema_drift_detects_additive_growth() -> None:
    decision = classify_feature_schema_drift(
        ["a", "b", "c"],
        {"train_sensors": ["a", "b"]},
    )

    assert decision.schema_compatibility == "ADDITIVE_GROWTH"
    assert decision.cache_compatible is False
    assert decision.should_refit is True
    assert decision.new_signals == ("c",)


def test_classify_feature_schema_drift_detects_temporary_tag_loss_and_intersection() -> None:
    decision = classify_feature_schema_drift(
        ["a"],
        {"train_sensors": ["a", "b"]},
    )

    assert decision.schema_compatibility == "TEMPORARY_TAG_LOSS"
    assert decision.cache_compatible is True
    assert decision.use_intersection is True
    assert decision.aligned_columns == ("a",)
    assert decision.missing_signals == ("b",)


def test_classify_feature_schema_drift_can_mark_persistent_loss() -> None:
    decision = classify_feature_schema_drift(
        ["a"],
        {"train_sensors": ["a", "b"]},
        persistent_missing_signals=["b"],
    )

    assert decision.schema_compatibility == "PERMANENT_TAG_LOSS"
    assert decision.cache_compatible is False
    assert decision.should_refit is True


def test_apply_feature_schema_alignment_preserves_current_runtime_reject_on_growth() -> None:
    train = pd.DataFrame({"a": [1.0], "b": [2.0]})
    score = pd.DataFrame({"a": [1.5], "b": [2.5]})
    decision = classify_feature_schema_drift(
        ["a", "b"],
        {"train_sensors": ["a"]},
    )

    train_out, score_out, aligned, cache_ok = apply_feature_schema_alignment(train, score, decision)

    assert aligned == ["a", "b"]
    assert cache_ok is False
    assert list(train_out.columns) == ["a", "b"]
    assert list(score_out.columns) == ["a", "b"]


def test_validate_cached_model_schema_drift_reports_order_mismatch() -> None:
    ok, reason, decision = validate_cached_model_schema_drift(
        model=object(),
        model_name="pca",
        current_columns=["b", "a"],
        cached_manifest={"train_sensors": ["a", "b"]},
    )

    assert ok is False
    assert "Column order mismatch" in str(reason)
    assert decision.schema_compatibility == "ORDER_MISMATCH"


def test_classify_regime_basis_drift_detects_incompatible_basis() -> None:
    basis = pd.DataFrame({"r_a": [0.1, 0.2]})
    regime_model = type("M", (), {"feature_columns": ["r_b"]})()

    decision = classify_regime_basis_drift(
        regime_model=regime_model,
        regime_basis_train=basis,
        cached_model_version="4.0",
        current_model_version="5.0",
    )

    assert decision.basis_compatibility == "INCOMPATIBLE"
    assert decision.should_refit is True
    assert "basis_column_mismatch" in decision.reason_codes
    assert "basis_version_mismatch" in decision.reason_codes


def test_classify_regime_basis_drift_detects_signature_mismatch() -> None:
    basis = pd.DataFrame({"r_a": [0.1, 0.2]})
    regime_model = type("M", (), {"feature_columns": ["r_a"]})()

    decision = classify_regime_basis_drift(
        regime_model=regime_model,
        regime_basis_train=basis,
        cached_model_version="5.0",
        current_model_version="5.0",
        cached_basis_signature="cached_sig",
        current_basis_signature="current_sig",
    )

    assert decision.basis_compatibility == "INCOMPATIBLE"
    assert decision.should_refit is True
    assert "basis_signature_mismatch" in decision.reason_codes


def test_compatibility_status_from_drift_aggregates_fields() -> None:
    feature_decision = classify_feature_schema_drift(
        ["a"],
        {"train_sensors": ["a", "b"]},
    )
    basis_decision = classify_regime_basis_drift(
        regime_model=None,
        regime_basis_train=pd.DataFrame({"r_a": [0.1]}),
        cached_model_version=None,
        current_model_version="5.0",
    )

    status = compatibility_status_from_drift(
        feature_schema_drift=feature_decision,
        basis_drift=basis_decision,
        baseline_compatibility="COMPATIBLE",
    )

    assert isinstance(status, CompatibilityStatus)
    assert status.schema_compatibility == "TEMPORARY_TAG_LOSS"
    assert status.basis_compatibility == "UNASSESSED"
    assert status.baseline_compatibility == "COMPATIBLE"
    assert status.missing_signals == ("b",)

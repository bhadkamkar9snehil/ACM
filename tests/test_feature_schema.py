from __future__ import annotations

import pandas as pd

from core.detector_orchestrator import validate_model_feature_compatibility
from core.feature_schema import (
    align_current_features_to_schema,
    compare_feature_schema,
    derive_basic_feature_columns_from_raw_columns,
    schema_from_manifest,
    validate_cached_model_schema,
)
from core.model_persistence import align_current_features_to_cached_manifest


def test_schema_from_manifest_builds_versioned_schema() -> None:
    schema = schema_from_manifest({"train_sensors": ["a", "b"]})

    assert schema is not None
    assert schema.feature_columns == ("a", "b")
    assert schema.schema_version.startswith("2026.2")
    assert schema.source == "cached_manifest"


def test_compare_feature_schema_tracks_missing_extra_and_order() -> None:
    comparison = compare_feature_schema(
        ["b", "a"],
        ["a", "c"],
        order_sensitive=True,
    )

    assert comparison.common_columns == ("a",)
    assert comparison.missing_in_current == ("c",)
    assert comparison.extra_in_current == ("b",)
    assert comparison.order_matches is False
    assert comparison.overlap_ratio == 0.5


def test_derive_basic_feature_columns_from_raw_columns_matches_expected_order() -> None:
    derived = derive_basic_feature_columns_from_raw_columns(["a", "b"])

    assert derived[:6] == (
        "a_med",
        "b_med",
        "a_mad",
        "b_mad",
        "a_mean",
        "b_mean",
    )
    assert derived[-4:] == ("a_energy_2", "b_energy_2", "a_rz", "b_rz")
    assert len(derived) == 22


def test_align_current_features_to_schema_rejects_current_extra_features() -> None:
    train = pd.DataFrame({"a": [1.0], "b": [2.0]})
    score = pd.DataFrame({"a": [1.5], "b": [2.5]})

    train_out, score_out, current_sensors, cache_ok = align_current_features_to_schema(
        train,
        score,
        {"train_sensors": ["a"]},
    )

    assert cache_ok is False
    assert list(train_out.columns) == ["a", "b"]
    assert list(score_out.columns) == ["a", "b"]
    assert current_sensors == ["a", "b"]


def test_align_current_features_to_schema_allows_missing_cached_subset() -> None:
    train = pd.DataFrame({"a": [1.0]})
    score = pd.DataFrame({"a": [1.5]})

    train_out, score_out, current_sensors, cache_ok = align_current_features_to_schema(
        train,
        score,
        {"train_sensors": ["a", "b"]},
    )

    assert cache_ok is True
    assert list(train_out.columns) == ["a"]
    assert list(score_out.columns) == ["a"]
    assert current_sensors == ["a"]


def test_model_persistence_wrapper_delegates_to_feature_schema_owner() -> None:
    train = pd.DataFrame({"a": [1.0]})
    score = pd.DataFrame({"a": [1.5]})

    train_out, score_out, current_sensors, cache_ok = align_current_features_to_cached_manifest(
        train,
        score,
        {"train_sensors": ["a"]},
    )

    assert cache_ok is True
    assert list(train_out.columns) == ["a"]
    assert list(score_out.columns) == ["a"]
    assert current_sensors == ["a"]


def test_validate_cached_model_schema_detects_order_sensitive_mismatch() -> None:
    ok, reason = validate_cached_model_schema(
        model=object(),
        model_name="pca",
        current_columns=["b", "a"],
        cached_manifest={"train_sensors": ["a", "b"]},
    )

    assert ok is False
    assert reason == "Column order mismatch at position 0: cached='a', current='b'"


def test_detector_orchestrator_wrapper_uses_feature_schema_owner() -> None:
    ok, reason = validate_model_feature_compatibility(
        model=object(),
        model_name="iforest",
        current_columns=["a", "c"],
        cached_manifest={"train_sensors": ["a", "b"]},
        equip="FD_FAN",
    )

    assert ok is False
    assert reason == "Column mismatch - missing: ['b']...; new: ['c']..."

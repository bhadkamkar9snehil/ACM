from __future__ import annotations

import pandas as pd

from core import regimes
from core.structure_encoder import (
    build_feature_basis,
    select_ewm_monitoring_surface,
    select_tag_agnostic_numeric_surface,
)


def test_structure_encoder_selects_tag_agnostic_numeric_surface() -> None:
    idx = pd.date_range("2026-01-01", periods=4, freq="h")
    train = pd.DataFrame(
        {
            "sensor_1_avg": [1.0, 2.0, 3.0, 4.0],
            "sensor_2_avg": [0.0, 10.0, 0.0, 10.0],
            "sensor_3_avg": [5.0, 5.0, 5.0, 5.0],
            "text_tag": ["a", "b", "c", "d"],
        },
        index=idx,
    )
    score = pd.DataFrame(
        {
            "sensor_1_avg": [1.5, 2.5],
            "sensor_2_avg": [5.0, 7.5],
            "sensor_3_avg": [5.0, 5.0],
            "text_tag": ["x", "y"],
        },
        index=idx[:2],
    )

    cols, train_numeric, score_numeric, meta = select_tag_agnostic_numeric_surface(train, score, cfg={})

    assert cols == ["sensor_2_avg", "sensor_1_avg"]
    assert list(train_numeric.columns) == cols
    assert list(score_numeric.columns) == cols
    assert meta["surface_type"] == "tag_agnostic_numeric"
    assert meta["selected_count"] == 2


def test_structure_encoder_builds_tag_agnostic_basis_with_scaler_metadata() -> None:
    idx = pd.date_range("2026-01-01", periods=4, freq="h")
    train_features = pd.DataFrame({"feat": [0.1, 0.2, 0.3, 0.4]}, index=idx)
    score_features = pd.DataFrame({"feat": [0.15, 0.25]}, index=idx[:2])
    raw_train = pd.DataFrame(
        {
            "sensor_1_avg": [1.0, 2.0, 3.0, 4.0],
            "sensor_2_avg": [0.0, 10.0, 0.0, 10.0],
            "sensor_3_avg": [5.0, 5.0, 5.0, 5.0],
        },
        index=idx,
    )
    raw_score = pd.DataFrame(
        {
            "sensor_1_avg": [1.5, 2.5],
            "sensor_2_avg": [6.0, 8.0],
            "sensor_3_avg": [5.0, 5.0],
        },
        index=idx[:2],
    )

    basis_train, basis_score, meta = build_feature_basis(
        train_features=train_features,
        score_features=score_features,
        raw_train=raw_train,
        raw_score=raw_score,
        pca_detector=None,
        cfg={},
    )

    assert list(basis_train.columns) == ["sensor_2_avg", "sensor_1_avg"]
    assert list(basis_score.columns) == ["sensor_2_avg", "sensor_1_avg"]
    assert meta["basis_normalized"] is True
    assert meta["feature_surface_type"] == "tag_agnostic_numeric"
    assert isinstance(meta["basis_signature"], str)
    assert meta["basis_scaler_cols"] == ["sensor_2_avg", "sensor_1_avg"]


def test_structure_encoder_selects_raw_monitoring_surface_for_ewm() -> None:
    idx = pd.date_range("2026-01-01", periods=4, freq="h")
    train = pd.DataFrame(
        {
            "sensor_1_avg": [1.0, 2.0, 3.0, 4.0],
            "sensor_2_avg": [0.0, 10.0, 0.0, 10.0],
            "sensor_3_avg": [5.0, 5.0, 5.0, 5.0],
        },
        index=idx,
    )
    score = pd.DataFrame(
        {
            "sensor_1_avg": [1.5, 2.5],
            "sensor_2_avg": [5.0, 7.5],
            "sensor_3_avg": [5.0, 5.0],
        },
        index=idx[:2],
    )

    cols, train_numeric, score_numeric, meta = select_ewm_monitoring_surface(train, score, cfg={})

    assert cols == ["sensor_2_avg", "sensor_1_avg"]
    assert list(train_numeric.columns) == cols
    assert list(score_numeric.columns) == cols
    assert meta["surface_type"] == "ewm_monitoring_raw_numeric"
    assert meta["channel_semantics"] == "raw_numeric"
    assert meta["max_cols"] == 0


def test_regimes_wrappers_delegate_to_structure_encoder() -> None:
    idx = pd.date_range("2026-01-01", periods=4, freq="h")
    train = pd.DataFrame({"sensor_1_avg": [1.0, 2.0, 3.0, 4.0]}, index=idx)
    score = pd.DataFrame({"sensor_1_avg": [1.5, 2.5]}, index=idx[:2])

    cols_from_encoder, _, _, _ = select_tag_agnostic_numeric_surface(train, score, cfg={})
    cols_from_regimes, _, _, _ = regimes.select_tag_agnostic_numeric_surface(train, score, cfg={})

    assert cols_from_regimes == cols_from_encoder

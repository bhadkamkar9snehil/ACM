from __future__ import annotations

import pandas as pd

from core.state_builder import build_observation_integrity, build_state_snapshot


def test_build_observation_integrity_uses_sampling_and_missingness() -> None:
    idx = pd.date_range("2026-01-01 00:00:00", periods=3, freq="h", name="EntryDateTime")
    df = pd.DataFrame(
        {
            "sensor_a": [1.0, 2.0, 3.0],
            "sensor_b": [10.0, None, 30.0],
        },
        index=idx,
    )

    integrity = build_observation_integrity(
        df,
        {
            "sampling_seconds": 3600.0,
            "dup_timestamps_removed": 2,
            "future_rows_dropped": 1,
        },
    )

    assert integrity.coverage_ratio == 1.0
    assert integrity.expected_rows == 3
    assert integrity.observed_rows == 3
    assert integrity.effective_signal_count == 2
    assert integrity.missingness_grade == "FAIR"
    assert integrity.duplicate_rows_removed == 2
    assert integrity.future_rows_dropped == 1


def test_build_state_snapshot_uses_index_bounds_for_window_identity() -> None:
    idx = pd.date_range("2026-01-01 00:00:00", periods=2, freq="h", name="EntryDateTime")
    df = pd.DataFrame({"sensor_a": [1.0, 2.0]}, index=idx)

    snapshot = build_state_snapshot(
        df=df,
        meta={"sampling_seconds": 3600.0},
        equip_id=42,
        run_id="run-42",
        window_label="score",
    )

    assert snapshot is not None
    assert snapshot.asset_id == 42
    assert snapshot.run_id == "run-42"
    assert snapshot.window_label == "score"
    assert snapshot.source_window_start == idx.min().to_pydatetime()
    assert snapshot.source_window_end == idx.max().to_pydatetime()
    assert snapshot.batch_end_time == idx.max().to_pydatetime()


def test_build_state_snapshot_returns_none_for_empty_frame() -> None:
    snapshot = build_state_snapshot(
        df=pd.DataFrame(index=pd.DatetimeIndex([], name="EntryDateTime")),
        meta={},
        equip_id=1,
        run_id="run-empty",
        window_label="score",
    )

    assert snapshot is None

from datetime import datetime

import pandas as pd

from core.data_loader import DataMeta
from core.representation_contracts import RuntimeMode
from core.representation_pipeline import run_representation_pipeline


def _frame(start: str, periods: int, freq: str = "1h") -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=periods, freq=freq, name="EntryDateTime")
    return pd.DataFrame(
        {
            "sensor_a": [1.0, 2.0, 3.0][:periods],
            "sensor_b": [10.0, None, 30.0][:periods],
        },
        index=idx,
    )


def test_representation_pipeline_builds_shadow_states_from_datameta() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = _frame("2024-01-01T03:00:00", 2)
    meta = DataMeta(
        timestamp_col="EntryDateTime",
        cadence_ok=True,
        kept_cols=["sensor_a", "sensor_b"],
        dropped_cols=[],
        start_ts=train.index.min(),
        end_ts=score.index.max(),
        n_rows=5,
        sampling_seconds=3600.0,
        dup_timestamps_removed=2,
        future_rows_dropped=1,
    )

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta=meta,
        cfg={},
        equip_id=42,
        run_id="run-42",
    )

    assert result.enabled is True
    assert result.authoritative is False
    assert result.score_state is not None
    assert result.train_state is not None
    assert result.score_state.integrity.expected_rows == 2
    assert result.score_state.integrity.observed_rows == 2
    assert result.score_state.integrity.duplicate_rows_removed == 2
    assert result.score_state.integrity.future_rows_dropped == 1
    assert result.eligibility.score_allowed is True
    assert result.baseline_governance.runtime_mode == RuntimeMode.ONLINE_SCORING
    assert result.notes == ("shadow_mode_not_authoritative", "contracts_slice")


def test_representation_pipeline_uses_coldstart_meta_for_runtime_mode() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = _frame("2024-01-01T03:00:00", 2)
    meta = {
        "is_coldstart_run": True,
        "sampling_seconds": 3600.0,
        "dup_timestamps_removed": 0,
        "future_rows_dropped": 0,
    }

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta=meta,
        cfg={},
        equip_id=7,
        run_id="run-coldstart",
    )

    assert result.baseline_governance.runtime_mode == RuntimeMode.BASELINE_FORMATION
    assert result.baseline_governance.readiness_state == "FORMING"
    assert result.signal_summary.monitorable_signal_count == 2


def test_representation_pipeline_handles_empty_score_window() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = pd.DataFrame(index=pd.DatetimeIndex([], name="EntryDateTime"))

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta={"sampling_seconds": 3600.0},
        cfg={},
        equip_id=9,
        run_id="run-empty-score",
    )

    assert result.score_state is None
    assert result.eligibility.score_allowed is False
    assert result.eligibility.suppressed_reason_codes == ("no_score_rows",)

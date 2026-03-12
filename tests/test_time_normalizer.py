from __future__ import annotations

import pandas as pd
import pytest

from core import data_loader
from core.fast_features import deduplicate_index as ff_deduplicate_index
from core.fast_features import ensure_local_index as ff_ensure_local_index
from core.output_manager import OutputManager
from core.time_normalizer import (
    check_cadence,
    coerce_local_and_filter_future,
    deduplicate_index,
    ensure_local_index,
    native_cadence_secs,
    parse_ts_index,
    resample_df,
)


def test_parse_ts_index_sets_sorted_datetime_index() -> None:
    df = pd.DataFrame(
        {
            "EntryDateTime": ["2026-01-01 01:00:00", "2026-01-01 00:00:00"],
            "sensor_a": [2.0, 1.0],
        }
    )

    out = parse_ts_index(df, "EntryDateTime")

    assert isinstance(out.index, pd.DatetimeIndex)
    assert list(out.index) == list(pd.to_datetime(["2026-01-01 00:00:00", "2026-01-01 01:00:00"]))
    assert list(out["sensor_a"]) == [1.0, 2.0]


def test_data_loader_reexports_time_normalizer_helpers() -> None:
    assert data_loader.parse_ts_index is parse_ts_index
    assert data_loader.coerce_local_and_filter_future is coerce_local_and_filter_future
    assert data_loader.native_cadence_secs is native_cadence_secs
    assert data_loader.check_cadence is check_cadence
    assert data_loader.resample_df is resample_df


def test_ensure_local_index_strips_timezone_and_fast_features_wrapper_matches() -> None:
    idx = pd.date_range("2026-01-01 00:00:00", periods=2, freq="h", tz="UTC")
    df = pd.DataFrame({"sensor_a": [1.0, 2.0]}, index=idx)

    direct = ensure_local_index(df.copy())
    wrapped = ff_ensure_local_index(df.copy())

    assert isinstance(direct.index, pd.DatetimeIndex)
    assert direct.index.tz is None
    assert wrapped.index.tz is None
    assert direct.index.equals(wrapped.index)


def test_output_manager_ensure_local_index_delegates_to_shared_owner() -> None:
    idx = pd.date_range("2026-01-01 00:00:00", periods=2, freq="h", tz="UTC")
    df = pd.DataFrame({"sensor_a": [1.0, 2.0]}, index=idx)
    out_mgr = OutputManager.__new__(OutputManager)

    out = out_mgr._ensure_local_index(df.copy())

    assert isinstance(out.index, pd.DatetimeIndex)
    assert out.index.tz is None


def test_deduplicate_index_keeps_last_value_and_wrapper_matches() -> None:
    idx = pd.to_datetime(
        [
            "2026-01-01 00:00:00",
            "2026-01-01 00:00:00",
            "2026-01-01 01:00:00",
        ]
    )
    df = pd.DataFrame({"sensor_a": [1.0, 9.0, 2.0]}, index=idx)

    direct, direct_dups = deduplicate_index(df.copy(), "TRAIN", "FD_FAN")
    wrapped, wrapped_dups = ff_deduplicate_index(df.copy(), "TRAIN", "FD_FAN")

    assert direct_dups == 1
    assert wrapped_dups == 1
    assert list(direct["sensor_a"]) == [9.0, 2.0]
    assert direct.equals(wrapped)


def test_coerce_local_and_filter_future_drops_invalid_and_future_rows() -> None:
    idx = pd.Index(
        [
            pd.Timestamp("2026-01-01 00:00:00", tz="UTC"),
            "not-a-timestamp",
            pd.Timestamp("2026-01-03 00:00:00", tz="UTC"),
        ]
    )
    df = pd.DataFrame({"sensor_a": [1.0, 2.0, 3.0]}, index=idx)

    out, tz_stripped, future_rows = coerce_local_and_filter_future(
        df,
        "SCORE",
        pd.Timestamp("2026-01-02 00:00:00"),
    )

    assert tz_stripped == 3
    assert future_rows == 1
    assert len(out) == 1
    assert out.index[0] == pd.Timestamp("2026-01-01 00:00:00")


def test_check_cadence_distinguishes_regular_and_irregular_index() -> None:
    regular = pd.date_range("2026-01-01 00:00:00", periods=5, freq="5min")
    irregular = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-01-01 00:00:00"),
            pd.Timestamp("2026-01-01 00:05:00"),
            pd.Timestamp("2026-01-01 00:19:00"),
            pd.Timestamp("2026-01-01 00:24:00"),
        ]
    )

    assert check_cadence(regular, 300) is True
    assert check_cadence(irregular, 300) is False


def test_native_cadence_secs_uses_median_delta() -> None:
    idx = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-01-01 00:00:00"),
            pd.Timestamp("2026-01-01 00:05:00"),
            pd.Timestamp("2026-01-01 00:10:00"),
            pd.Timestamp("2026-01-01 00:20:00"),
        ]
    )

    assert native_cadence_secs(idx) == pytest.approx(300.0)


def test_resample_df_interpolates_regular_grid() -> None:
    idx = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-01-01 00:00:00"),
            pd.Timestamp("2026-01-01 00:10:00"),
        ]
    )
    df = pd.DataFrame({"sensor_a": [0.0, 10.0]}, index=idx)

    out = resample_df(df, sampling_secs=300, interp_method="linear")

    assert list(out.index) == list(pd.date_range("2026-01-01 00:00:00", periods=3, freq="5min"))
    assert list(out["sensor_a"]) == [0.0, 5.0, 10.0]


def test_resample_df_strict_mode_rejects_large_fill_ratio() -> None:
    idx = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-01-01 00:00:00"),
            pd.Timestamp("2026-01-01 00:20:00"),
        ]
    )
    df = pd.DataFrame({"sensor_a": [1.0, 2.0]}, index=idx)

    with pytest.raises(ValueError, match="Too much missing data after resample"):
        resample_df(
            df,
            sampling_secs=300,
            interp_method="none",
            strict=True,
            max_fill_ratio=0.1,
        )

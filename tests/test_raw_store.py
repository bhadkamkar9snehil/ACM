"""Acceptance tests for the immortal raw store (brief S0.2).

Covers: roundtrip, idempotent replay, multi-month partitioning, timezone
strictness, range reads, kill-mid-write survival, stale temp sweep, and a
randomized dedupe/ordering property.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acm.store.raw import TIMESTAMP_COL, RawStore

UTC = timezone.utc


def frame_of(timestamps, value_start=0.0):
    return pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(timestamps, dtype=pl.Datetime("us", "UTC")),
            "sensor_a": [value_start + i for i in range(len(timestamps))],
            "sensor_b": [1.5] * len(timestamps),
        }
    )


def hourly(start, n):
    return [start + timedelta(hours=i) for i in range(n)]


@pytest.fixture()
def store(tmp_path):
    return RawStore(tmp_path / "raw")


def test_roundtrip_sorted(store):
    ts = hourly(datetime(2026, 1, 10, tzinfo=UTC), 48)
    shuffled = list(reversed(ts))
    added = store.append("care/A/40", frame_of(shuffled))
    assert added == 48
    out = store.read("care/A/40")
    assert out.height == 48
    col = out.get_column(TIMESTAMP_COL).to_list()
    assert col == sorted(col)
    assert store.span("care/A/40") == (min(ts), max(ts))


def test_idempotent_replay(store):
    ts = hourly(datetime(2026, 2, 1, tzinfo=UTC), 24)
    assert store.append("a1", frame_of(ts)) == 24
    assert store.append("a1", frame_of(ts)) == 0
    assert store.row_count("a1") == 24


def test_partial_overlap_appends_only_new(store):
    ts = hourly(datetime(2026, 2, 1, tzinfo=UTC), 24)
    store.append("a1", frame_of(ts))
    extended = hourly(datetime(2026, 2, 1, tzinfo=UTC), 36)
    assert store.append("a1", frame_of(extended)) == 12
    assert store.row_count("a1") == 36


def test_multi_month_partitions(store, tmp_path):
    ts = hourly(datetime(2026, 1, 31, 12, tzinfo=UTC), 48)  # spans Jan+Feb
    store.append("a1", frame_of(ts))
    parts = sorted(p.name for p in (tmp_path / "raw" / "a1").glob("*.parquet"))
    assert parts == ["2026-01.parquet", "2026-02.parquet"]
    assert store.read("a1").height == 48


def test_range_read_half_open(store):
    start = datetime(2026, 3, 1, tzinfo=UTC)
    store.append("a1", frame_of(hourly(start, 10)))
    out = store.read("a1", start=start + timedelta(hours=2), end=start + timedelta(hours=5))
    assert out.height == 3


def test_naive_timestamps_rejected(store):
    naive = pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(
                [datetime(2026, 1, 1)], dtype=pl.Datetime("us")
            ),
            "v": [1.0],
        }
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        store.append("a1", naive)


def test_missing_timestamp_column_rejected(store):
    with pytest.raises(ValueError, match=TIMESTAMP_COL):
        store.append("a1", pl.DataFrame({"v": [1.0]}))


def test_empty_frame_is_noop(store):
    assert store.append("a1", pl.DataFrame()) == 0
    assert store.read("a1").is_empty()


def test_asset_key_with_path_separators(store):
    ts = hourly(datetime(2026, 1, 1, tzinfo=UTC), 3)
    store.append("care/A/40", frame_of(ts))
    store.append(r"plant\unit:7", frame_of(ts))
    assert store.assets() == ["care/A/40", "plant\\unit:7"]


def test_kill_mid_write_preserves_previous_partition(store, monkeypatch):
    """A writer killed between temp-write and replace must not corrupt the
    partition; the previous content stays fully readable."""
    ts = hourly(datetime(2026, 4, 1, tzinfo=UTC), 24)
    store.append("a1", frame_of(ts))

    real_replace = os.replace

    def crash(src, dst):
        raise OSError("simulated kill mid-write")

    monkeypatch.setattr(os, "replace", crash)
    more = hourly(datetime(2026, 4, 2, tzinfo=UTC), 24)
    with pytest.raises(OSError, match="simulated kill"):
        store.append("a1", frame_of(more))
    monkeypatch.setattr(os, "replace", real_replace)

    # previous content intact, new rows absent
    assert store.row_count("a1") == 24
    out = store.read("a1")
    assert out.get_column(TIMESTAMP_COL).max() == ts[-1]

    # replaying the failed append converges to the full state
    assert store.append("a1", frame_of(more)) == 24
    assert store.row_count("a1") == 48


def test_stale_tmp_files_swept(store, tmp_path):
    ts = hourly(datetime(2026, 5, 1, tzinfo=UTC), 2)
    store.append("a1", frame_of(ts))
    asset_dir = tmp_path / "raw" / "a1"
    stale = asset_dir / "2026-05.parquet.tmp-999-deadbeef"
    stale.write_bytes(b"garbage")
    old = datetime.now().timestamp() - 7200
    os.utime(stale, (old, old))
    store.append("a1", frame_of(hourly(datetime(2026, 5, 2, tzinfo=UTC), 2)))
    assert not stale.exists()


@settings(max_examples=25, deadline=None)
@given(
    offsets=st.lists(
        st.integers(min_value=0, max_value=2000), min_size=1, max_size=80
    )
)
def test_property_unique_sorted_after_any_replay(tmp_path_factory, offsets):
    """Whatever duplicated/unordered hours arrive, in however many batches,
    the store converges to unique, sorted rows."""
    root = tmp_path_factory.mktemp("prop")
    store = RawStore(root)
    base = datetime(2026, 6, 1, tzinfo=UTC)
    ts = [base + timedelta(hours=o) for o in offsets]
    mid = len(ts) // 2
    store.append("p1", frame_of(ts[:mid] or ts))
    store.append("p1", frame_of(ts))
    out = store.read("p1")
    col = out.get_column(TIMESTAMP_COL).to_list()
    assert col == sorted(set(ts))


def test_append_is_column_order_insensitive(tmp_path):
    """Live bridge payloads carry keys in arbitrary order; an append with
    a different column order than the stored partition must merge, not
    crash (found by the #90 soak: the first drained buffer batch killed
    the tick). Channels missing from a batch land as nulls."""
    import numpy as np

    from acm.store.raw import TIMESTAMP_COL, RawStore

    store = RawStore(tmp_path / "raw")
    ts = pl.Series(
        TIMESTAMP_COL,
        [datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i)
         for i in range(10)],
        dtype=pl.Datetime("us", "UTC"),
    )
    # timestamp LAST on first append
    store.append("o/1", pl.DataFrame({"a": np.arange(10.0), "b": np.ones(10)}).with_columns(ts))
    # timestamp FIRST + shuffled channels + one channel missing
    ts2 = pl.Series(
        TIMESTAMP_COL,
        [datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=10 + i)
         for i in range(5)],
        dtype=pl.Datetime("us", "UTC"),
    )
    n = store.append(
        "o/1", pl.DataFrame({TIMESTAMP_COL: ts2, "b": np.zeros(5), "a": np.arange(5.0)})
    )
    assert n == 5
    back = store.read("o/1")
    assert back.height == 15
    assert set(back.columns) == {"a", "b", TIMESTAMP_COL}

    # cross-partition: a NEW month written from a differently-ordered
    # source must still read as one frame (read is also name-matched)
    ts3 = pl.Series(
        TIMESTAMP_COL,
        [datetime(2025, 2, 1, tzinfo=timezone.utc) + timedelta(minutes=i)
         for i in range(5)],
        dtype=pl.Datetime("us", "UTC"),
    )
    store.append(
        "o/1", pl.DataFrame({TIMESTAMP_COL: ts3, "b": np.ones(5), "a": np.zeros(5)})
    )
    all_rows = store.read("o/1")
    assert all_rows.height == 20
    assert set(all_rows.columns) == {"a", "b", TIMESTAMP_COL}

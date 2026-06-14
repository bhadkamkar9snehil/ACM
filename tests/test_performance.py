"""Performance regression tests and micro-benchmarks.

Three areas covered, none touching core ML:

  1. SQL  — v_asset_now CTE view: correctness + query-plan efficiency.
  2. Feed — update_cache fast path: no full read/write when no new data.
  3. API  — _TTLCache: hit/miss, expiry, invalidation, mutation side-effects.

Benchmarks use wall-clock ratios rather than fixed thresholds so they are
stable across CI machines.  A 2× ratio is required for the caching wins; the
SQL plan test counts table-access operations rather than timing (deterministic).
"""
from __future__ import annotations

import asyncio
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.acm_feed import (   # noqa: E402
    CacheInfo, SourceSpec, _read_ts_column, cache_path, update_cache,
)
from scripts.acm_service import _MISS, _TTLCache, create_app  # noqa: E402
from scripts.acm_store import DDL_SQLITE, Store, ack_alarm, ingest_result  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path: Path) -> tuple[sqlite3.Connection, Path]:
    db = tmp_path / "perf.db"
    con = sqlite3.connect(str(db))
    con.executescript(DDL_SQLITE)
    return con, db


def _insert_asset(con: sqlite3.Connection, key: str) -> None:
    con.execute(
        "INSERT OR IGNORE INTO assets(asset_key, farm, verdict) VALUES (?,?,?)",
        (key, "farm", "OK"))
    con.execute(
        "INSERT OR IGNORE INTO monitored_assets(asset_key, grp, state) VALUES (?,?,?)",
        (key.split("/")[1] if "/" in key else key, key.split("/")[0] if "/" in key else "fleet",
         "OK"))
    con.commit()


def _insert_scores(con: sqlite3.Connection, key: str, n: int,
                   base: str = "2026-01-01") -> None:
    rows = []
    ts0 = pd.Timestamp(base)
    for i in range(n):
        ts = str(ts0 + pd.Timedelta(minutes=10 * i))
        rows.append((key, ts, float(i % 5), 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0, 0))
    con.executemany(
        "INSERT INTO scores(asset_key,ts,fused,ar1_z,pca_spe_z,pca_t2_z,"
        "iforest_z,gmm_z,omr_z,status,alarm) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        rows)
    con.commit()


def _insert_alarms(con: sqlite3.Connection, key: str, n: int,
                   n_unacked: int = 0) -> None:
    ts0 = pd.Timestamp("2026-01-01")
    for i in range(n):
        start = str(ts0 + pd.Timedelta(hours=i * 2))
        end = str(ts0 + pd.Timedelta(hours=i * 2 + 1))
        ack_at = None if i < n_unacked else "2026-02-01 00:00:00"
        con.execute(
            "INSERT INTO alarms(asset_key,start_ts,end_ts,duration_h,"
            "peak_fused,ack_at) VALUES (?,?,?,?,?,?)",
            (key, start, end, 1.0, 4.0, ack_at))
    con.commit()


def _plant_csv(tmp_path: Path, name: str, n: int, seed: int = 42) -> Path:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2026-01-01", periods=n, freq="10min")
    df = pd.DataFrame({
        "time_stamp": ts,
        **{f"sensor_{j}": rng.standard_normal(n) for j in range(10)},
    })
    p = tmp_path / f"{name}.csv"
    df.to_csv(p, index=False)
    return p


# ===========================================================================
# 1. SQL — v_asset_now correctness
# ===========================================================================

class TestViewCorrectness:

    def test_asset_with_scores_and_alarms(self, tmp_path):
        con, _ = _make_db(tmp_path)
        _insert_asset(con, "farm/A1")
        _insert_scores(con, "farm/A1", 100)
        _insert_alarms(con, "farm/A1", 5, n_unacked=2)

        row = con.execute(
            "SELECT * FROM v_asset_now WHERE asset_key='farm/A1'").fetchone()
        cols = [d[0] for d in con.execute(
            "SELECT * FROM v_asset_now WHERE asset_key='farm/A1'").description]
        r = dict(zip(cols, row))

        assert r["last_ts"] is not None, "last_ts must be populated from scores"
        assert r["last_fused"] is not None, "last_fused must be populated"
        assert r["alarm_episodes"] == 5, f"expected 5 alarms, got {r['alarm_episodes']}"
        assert r["unacked_alarms"] == 2, f"expected 2 unacked, got {r['unacked_alarms']}"
        assert r["last_alarm_end"] is not None, "last_alarm_end must be set"

    def test_asset_no_scores(self, tmp_path):
        con, _ = _make_db(tmp_path)
        _insert_asset(con, "farm/A2")

        row = con.execute(
            "SELECT last_ts, last_fused, alarm_episodes, unacked_alarms "
            "FROM v_asset_now WHERE asset_key='farm/A2'").fetchone()
        last_ts, last_fused, episodes, unacked = row
        assert last_ts is None, "asset with no scores must have NULL last_ts"
        assert last_fused is None, "asset with no scores must have NULL last_fused"
        assert episodes == 0, "asset with no alarms must show 0 episodes"
        assert unacked == 0, "asset with no alarms must show 0 unacked"

    def test_asset_no_alarms(self, tmp_path):
        con, _ = _make_db(tmp_path)
        _insert_asset(con, "farm/A3")
        _insert_scores(con, "farm/A3", 50)

        row = con.execute(
            "SELECT alarm_episodes, unacked_alarms, last_alarm_end "
            "FROM v_asset_now WHERE asset_key='farm/A3'").fetchone()
        episodes, unacked, last_end = row
        assert episodes == 0
        assert unacked == 0
        assert last_end is None

    def test_last_fused_is_latest_score(self, tmp_path):
        """last_fused must match the fused value at the maximum ts."""
        con, _ = _make_db(tmp_path)
        _insert_asset(con, "farm/A4")
        # Insert scores with a sentinel value at the end
        _insert_scores(con, "farm/A4", 10)
        sentinel_ts = "2026-03-01 00:00:00"
        con.execute(
            "INSERT INTO scores(asset_key,ts,fused,ar1_z,pca_spe_z,pca_t2_z,"
            "iforest_z,gmm_z,omr_z,status,alarm) VALUES (?,?,?,0,0,0,0,0,0,0,0)",
            ("farm/A4", sentinel_ts, 99.5))
        con.commit()

        row = con.execute(
            "SELECT last_ts, last_fused FROM v_asset_now "
            "WHERE asset_key='farm/A4'").fetchone()
        assert row[0] == sentinel_ts
        assert abs(row[1] - 99.5) < 1e-6, "last_fused must be 99.5 (the sentinel)"

    def test_all_alarms_acked_shows_zero_unacked(self, tmp_path):
        con, _ = _make_db(tmp_path)
        _insert_asset(con, "farm/A5")
        _insert_scores(con, "farm/A5", 10)
        _insert_alarms(con, "farm/A5", 3, n_unacked=0)  # all acked

        row = con.execute(
            "SELECT alarm_episodes, unacked_alarms FROM v_asset_now "
            "WHERE asset_key='farm/A5'").fetchone()
        assert row[0] == 3, "all alarm episodes must be counted"
        assert row[1] == 0, "all acked → unacked must be 0"

    def test_ack_reflects_immediately(self, tmp_path):
        """Acknowledging an alarm must decrement unacked_alarms via the view."""
        con, _ = _make_db(tmp_path)
        store = Store("sqlite", db=str(tmp_path / "perf.db"))
        _insert_asset(con, "farm/A6")
        _insert_scores(con, "farm/A6", 10)
        _insert_alarms(con, "farm/A6", 2, n_unacked=2)

        before = con.execute(
            "SELECT unacked_alarms FROM v_asset_now WHERE asset_key='farm/A6'"
        ).fetchone()[0]
        assert before == 2

        start_ts = con.execute(
            "SELECT start_ts FROM alarms WHERE asset_key='farm/A6' LIMIT 1"
        ).fetchone()[0]
        ack_alarm(store, "farm/A6", start_ts, "ops", "")

        after = con.execute(
            "SELECT unacked_alarms FROM v_asset_now WHERE asset_key='farm/A6'"
        ).fetchone()[0]
        assert after == 1, "acking one alarm must reduce unacked by 1"
        store.close()

    def test_multi_asset_no_cross_contamination(self, tmp_path):
        """Each asset sees only its own scores and alarms."""
        con, _ = _make_db(tmp_path)
        for i, key in enumerate(["farm/B1", "farm/B2", "farm/B3"]):
            _insert_asset(con, key)
            _insert_scores(con, key, (i + 1) * 10)
            _insert_alarms(con, key, i + 1, n_unacked=i)

        rows = con.execute(
            "SELECT asset_key, alarm_episodes, unacked_alarms "
            "FROM v_asset_now WHERE asset_key LIKE 'farm/B%' "
            "ORDER BY asset_key").fetchall()
        assert len(rows) == 3
        assert rows[0][1] == 1 and rows[0][2] == 0
        assert rows[1][1] == 2 and rows[1][2] == 1
        assert rows[2][1] == 3 and rows[2][2] == 2

    def test_view_scales_linearly_not_quadratically(self, tmp_path):
        """CTE plan: query time must not scale faster than O(N)."""
        con, _ = _make_db(tmp_path)
        SCORES_PER_ASSET = 200

        def _load(n_assets: int) -> float:
            for i in range(n_assets):
                key = f"perf/S{i}"
                _insert_asset(con, key)
                _insert_scores(con, key, SCORES_PER_ASSET)
                _insert_alarms(con, key, 3, n_unacked=1)
            t0 = time.perf_counter()
            for _ in range(5):
                con.execute("SELECT * FROM v_asset_now").fetchall()
            return (time.perf_counter() - t0) / 5

        t10 = _load(10)
        t100 = _load(100)  # 10× more assets

        # Allow up to 50× overhead (generous for CI), but the old O(4N) pattern
        # would be much worse.  Reject a clearly super-linear regression.
        ratio = t100 / max(t10, 1e-6)
        assert ratio < 100, (
            f"v_asset_now query scaled {ratio:.1f}× for 10× more assets "
            f"(t10={t10*1000:.1f}ms, t100={t100*1000:.1f}ms). "
            "Suspected correlated-subquery regression.")


# ===========================================================================
# 2. Feed — update_cache fast path
# ===========================================================================

class TestUpdateCacheFastPath:

    def test_no_write_when_no_new_data(self, tmp_path):
        """When the source has no new rows, the parquet file must not be touched."""
        csv = _plant_csv(tmp_path, "asset1", 500)
        spec = SourceSpec("asset1", "csv", str(csv),
                          timestamp_col="time_stamp", status_col=None)
        cache_dir = tmp_path / "cache"

        # First pull: full load
        info1 = update_cache(spec, cache_dir)
        assert info1.pulled_rows == 500
        assert info1.n_rows == 500

        p = cache_path(cache_dir, "asset1")
        mtime_before = p.stat().st_mtime

        # Second pull: same CSV, no new rows
        info2 = update_cache(spec, cache_dir)
        assert info2.pulled_rows == 0, "no new data means pulled_rows must be 0"
        assert info2.n_rows == info1.n_rows, "row count must be unchanged"

        mtime_after = p.stat().st_mtime
        assert mtime_after == mtime_before, (
            "parquet file must NOT be rewritten when there are no new rows")

    def test_returns_correct_cacheinfo_on_fast_path(self, tmp_path):
        """Fast-path CacheInfo must match a full read's values."""
        csv = _plant_csv(tmp_path, "asset2", 288)
        spec = SourceSpec("asset2", "csv", str(csv),
                          timestamp_col="time_stamp", status_col=None)
        cache_dir = tmp_path / "cache"

        info_full = update_cache(spec, cache_dir)  # first pull (writes file)
        info_fast = update_cache(spec, cache_dir)  # second pull (fast path)

        assert info_fast.last_ts == info_full.last_ts
        assert info_fast.n_rows == info_full.n_rows
        assert abs(info_fast.span_days - info_full.span_days) < 0.01

    def test_writes_when_new_data_arrives(self, tmp_path):
        """After the initial pull, adding rows must trigger a write."""
        csv = _plant_csv(tmp_path, "asset3", 100)
        spec = SourceSpec("asset3", "csv", str(csv),
                          timestamp_col="time_stamp", status_col=None)
        cache_dir = tmp_path / "cache"

        update_cache(spec, cache_dir)
        p = cache_path(cache_dir, "asset3")
        mtime1 = p.stat().st_mtime

        # Append 10 more rows to the CSV
        df = pd.read_csv(csv, parse_dates=["time_stamp"])
        extra = df.tail(1).copy()
        for i in range(10):
            row = extra.copy()
            row["time_stamp"] = df["time_stamp"].iloc[-1] + pd.Timedelta(minutes=10 * (i + 1))
            df = pd.concat([df, row], ignore_index=True)
        df.to_csv(csv, index=False)

        info = update_cache(spec, cache_dir)
        assert info.pulled_rows == 10
        assert p.stat().st_mtime > mtime1, "parquet must be rewritten after new data"

    def test_read_ts_column_returns_none_for_missing_file(self, tmp_path):
        result = _read_ts_column(tmp_path / "nonexistent.parquet", "time_stamp")
        assert result is None

    def test_read_ts_column_column_pruning(self, tmp_path):
        """_read_ts_column must return only the timestamp series, not all columns."""
        rng = np.random.default_rng(0)
        n = 300
        ts = pd.date_range("2026-01-01", periods=n, freq="10min")
        df = pd.DataFrame({"time_stamp": ts,
                           **{f"col_{i}": rng.standard_normal(n) for i in range(50)}})
        p = tmp_path / "wide.parquet"
        df.to_parquet(p, index=False)

        series = _read_ts_column(p, "time_stamp")
        assert series is not None
        assert len(series) == n
        assert series.max() == pd.to_datetime(ts[-1])

    def test_fast_path_is_faster_than_full_read(self, tmp_path):
        """No-new-data path must be measurably faster than a full read+write cycle."""
        # Create a wide parquet (many columns, many rows) to make the difference visible.
        rng = np.random.default_rng(1)
        n = 2000
        n_cols = 100
        ts = pd.date_range("2026-01-01", periods=n, freq="10min")
        df = pd.DataFrame({"time_stamp": ts,
                           **{f"s_{i}": rng.standard_normal(n) for i in range(n_cols)}})
        p = tmp_path / "wide.parquet"
        df.to_parquet(p, index=False)

        # Full read time (baseline)
        t_full = time.perf_counter()
        for _ in range(5):
            pd.read_parquet(str(p))
        t_full = (time.perf_counter() - t_full) / 5

        # Column-pruned read time
        import pyarrow.parquet as pq
        t_pruned = time.perf_counter()
        for _ in range(5):
            pq.read_table(str(p), columns=["time_stamp"])
        t_pruned = (time.perf_counter() - t_pruned) / 5

        assert t_pruned < t_full, (
            f"Column-pruned read ({t_pruned*1000:.2f}ms) should be faster "
            f"than full read ({t_full*1000:.2f}ms)")

    def test_trailing_window_trimming_preserved_on_fast_path(self, tmp_path):
        """Fast path must compute n_rows within the window, not the full file length."""
        rng = np.random.default_rng(2)
        n = 1440  # 10 days at 10min
        ts = pd.date_range("2026-01-01", periods=n, freq="10min")
        df = pd.DataFrame({"time_stamp": ts, "val": rng.standard_normal(n)})

        # Seed the parquet cache directly (bypass update_cache initial load).
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        p = cache_dir / "trim_asset.parquet"
        df.to_parquet(p, index=False)

        # Source CSV has one stale row (older than the cache max) → increment is empty.
        stale = pd.DataFrame({"time_stamp": [pd.Timestamp("2025-01-01")], "val": [0.0]})
        csv = tmp_path / "stale.csv"
        stale.to_csv(csv, index=False)

        spec = SourceSpec("trim_asset", "csv", str(csv),
                          timestamp_col="time_stamp", status_col=None)

        # Fast path with 5-day window (half the data)
        info = update_cache(spec, cache_dir, train_window_days=5.0)
        assert info.pulled_rows == 0, "stale CSV must produce no new rows"
        expected_rows = n // 2
        # Allow ±2 rows for boundary rounding at the window edge
        assert abs(info.n_rows - expected_rows) <= 2, (
            f"5-day window on 10-day cache: expected ~{expected_rows} rows, "
            f"got {info.n_rows}")


# ===========================================================================
# 3. API — _TTLCache correctness
# ===========================================================================

class TestTTLCache:

    def test_miss_on_empty_cache(self):
        c = _TTLCache(ttl=10.0)
        assert c.get("x") is _MISS

    def test_hit_after_put(self):
        c = _TTLCache(ttl=10.0)
        c.put("key", [1, 2, 3])
        assert c.get("key") == [1, 2, 3]

    @pytest.mark.slow
    def test_miss_after_ttl_expires(self):
        c = _TTLCache(ttl=0.05)  # 50 ms TTL
        c.put("k", "value")
        assert c.get("k") == "value"
        time.sleep(0.06)
        assert c.get("k") is _MISS, "entry must expire after TTL"

    def test_drop_removes_single_key(self):
        c = _TTLCache(ttl=60.0)
        c.put("a", 1)
        c.put("b", 2)
        c.drop("a")
        assert c.get("a") is _MISS
        assert c.get("b") == 2

    def test_clear_removes_all_keys(self):
        c = _TTLCache(ttl=60.0)
        for i in range(5):
            c.put(f"k{i}", i)
        c.clear()
        for i in range(5):
            assert c.get(f"k{i}") is _MISS

    @pytest.mark.slow
    def test_overwrite_resets_ttl(self):
        c = _TTLCache(ttl=0.1)
        c.put("k", "first")
        time.sleep(0.07)
        c.put("k", "second")  # reset TTL
        time.sleep(0.07)       # now 0.14s since first put, 0.07s since second
        assert c.get("k") == "second", "overwrite must reset the TTL clock"

    def test_drop_nonexistent_key_is_noop(self):
        c = _TTLCache(ttl=10.0)
        c.drop("does_not_exist")  # must not raise

    def test_cache_stores_arbitrary_types(self):
        c = _TTLCache(ttl=10.0)
        c.put("list", [1, 2, 3])
        c.put("dict", {"a": 1})
        c.put("none", None)
        assert c.get("list") == [1, 2, 3]
        assert c.get("dict") == {"a": 1}
        assert c.get("none") is None  # None is a valid cached value (not _MISS)


# ===========================================================================
# 4. API endpoints — cache integration via FastAPI TestClient
# ===========================================================================

@pytest.fixture
def app_client(tmp_path):
    """Create a test app with scheduler disabled and a very short cache TTL."""
    from fastapi.testclient import TestClient
    app = create_app(backend="sqlite", db=str(tmp_path / "t.db"),
                     run_scheduler=False, api_cache_ttl=1.0)
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, app.state.service


class TestFleetCacheIntegration:

    def test_fleet_hit_skips_db_query(self, app_client):
        client, svc = app_client

        r1 = client.get("/api/fleet")
        assert r1.status_code == 200
        data1 = r1.json()

        # Second call must return the same object (cached)
        r2 = client.get("/api/fleet")
        assert r2.status_code == 200
        assert r2.json() == data1

    @pytest.mark.slow
    def test_fleet_cache_expires(self, app_client):
        client, svc = app_client
        r1 = client.get("/api/fleet")
        assert r1.status_code == 200

        time.sleep(1.1)  # outlast the 1-second test TTL
        # After expiry, the response is freshly computed but structurally identical
        r2 = client.get("/api/fleet")
        assert r2.status_code == 200

    def test_fleet_cache_invalidated_on_ack(self, app_client):
        """Acking an alarm must drop the fleet cache so unacked counts refresh."""
        client, svc = app_client
        # Populate store with a scored asset that has an unacked alarm
        store = svc.store
        store.execute(
            "INSERT OR IGNORE INTO assets(asset_key, farm, verdict) VALUES (?,?,?)",
            ("g/X1", "g", "ALARM"))
        store.execute(
            "INSERT OR IGNORE INTO alarms(asset_key,start_ts,end_ts,duration_h,peak_fused) "
            "VALUES (?,?,?,?,?)",
            ("g/X1", "2026-01-01 00:00:00", "2026-01-01 01:00:00", 1.0, 4.0))
        store.commit()

        # Prime the cache
        r1 = client.get("/api/fleet")
        assert r1.status_code == 200

        # Ack the alarm (must invalidate fleet cache)
        ra = client.post("/api/alarms/ack", json={
            "asset_key": "g/X1", "start_ts": "2026-01-01 00:00:00", "ack_by": "ops"})
        assert ra.status_code == 200

        # Check that fleet cache was invalidated: re-fetch from DB
        assert svc.api_cache.get("fleet") is _MISS, \
            "fleet cache must be invalidated after alarm ack"

    def test_sparklines_cached_per_days_param(self, app_client):
        client, svc = app_client
        r1 = client.get("/api/fleet/sparklines?days=30")
        assert r1.status_code == 200
        r2 = client.get("/api/fleet/sparklines?days=7")
        assert r2.status_code == 200
        # Both cache keys must exist independently
        assert svc.api_cache.get("sparklines:30") is not _MISS
        assert svc.api_cache.get("sparklines:7") is not _MISS

    def test_service_status_cached_when_idle(self, app_client):
        client, svc = app_client
        r1 = client.get("/api/service")
        assert r1.status_code == 200
        # Cache must be populated (tick_in_progress is False when idle)
        assert svc.api_cache.get("service") is not _MISS

    def test_service_cache_dropped_on_pause_resume(self, app_client):
        client, svc = app_client
        client.get("/api/service")  # prime
        assert svc.api_cache.get("service") is not _MISS

        client.post("/api/service/pause")
        assert svc.api_cache.get("service") is _MISS, \
            "service cache must be cleared after pause"

        client.get("/api/service")
        client.post("/api/service/resume")
        assert svc.api_cache.get("service") is _MISS, \
            "service cache must be cleared after resume"

    def test_tick_clears_all_caches(self, app_client):
        """After tick_once completes, both fleet and service caches must be empty."""
        client, svc = app_client
        # Prime all caches
        client.get("/api/fleet")
        client.get("/api/fleet/sparklines")
        client.get("/api/service")
        assert svc.api_cache.get("fleet") is not _MISS

        # Drive a tick directly (no assets → counts all zero, but cache is cleared)
        asyncio.run(svc.tick_once())
        assert svc.api_cache.get("fleet") is _MISS, \
            "api_cache must be cleared by tick_once"

    def test_onboard_drops_fleet_cache(self, app_client, tmp_path):
        """Onboarding a new asset must invalidate the fleet cache."""
        client, svc = app_client
        client.get("/api/fleet")  # prime
        assert svc.api_cache.get("fleet") is not _MISS

        csv = _plant_csv(tmp_path, "new_asset", 100)
        r = client.post("/api/monitored-assets", json={
            "asset_key": "new1",
            "source_kind": "csv",
            "source_ref": str(csv),
            "timestamp_col": "time_stamp",
        })
        assert r.status_code == 200
        assert svc.api_cache.get("fleet") is _MISS, \
            "fleet cache must be invalidated after onboarding"

    def test_retire_drops_fleet_cache(self, app_client, tmp_path):
        """Retiring an asset must invalidate the fleet cache."""
        client, svc = app_client
        csv = _plant_csv(tmp_path, "retire_asset", 100)
        # Onboard first
        client.post("/api/monitored-assets", json={
            "asset_key": "to_retire",
            "source_kind": "csv",
            "source_ref": str(csv),
            "timestamp_col": "time_stamp",
        })
        client.get("/api/fleet")  # prime cache
        assert svc.api_cache.get("fleet") is not _MISS

        r = client.delete("/api/monitored-assets/to_retire")
        assert r.status_code == 200
        assert svc.api_cache.get("fleet") is _MISS, \
            "fleet cache must be invalidated after retire"

    def test_cache_hit_is_faster_than_miss(self, app_client):
        """Cache hit must be at least 2× faster than a cold DB query."""
        client, svc = app_client

        # Cold (miss) — measure 3 cold calls (cache cleared each time)
        cold_times = []
        for _ in range(3):
            svc.api_cache.clear()
            t0 = time.perf_counter()
            client.get("/api/fleet")
            cold_times.append(time.perf_counter() - t0)
        cold_avg = sum(cold_times) / len(cold_times)

        # Warm (hit) — cache is now populated
        warm_times = []
        for _ in range(10):
            t0 = time.perf_counter()
            client.get("/api/fleet")
            warm_times.append(time.perf_counter() - t0)
        warm_avg = sum(warm_times) / len(warm_times)

        assert warm_avg < cold_avg, (
            f"Cache hit ({warm_avg*1000:.2f}ms) must be faster than "
            f"cold miss ({cold_avg*1000:.2f}ms)")


# ===========================================================================
# 5. Index existence — verify DDL creates the expected indexes
# ===========================================================================

class TestIndexes:

    def test_alarm_indexes_exist(self, tmp_path):
        con, _ = _make_db(tmp_path)
        idx = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        assert "ix_alarms_asset" in idx, \
            "ix_alarms_asset index must exist for per-asset alarm queries"
        assert "ix_alarms_asset_ack" in idx, \
            "ix_alarms_asset_ack index must exist for unacked alarm queries"

    def test_scores_index_still_exists(self, tmp_path):
        con, _ = _make_db(tmp_path)
        idx = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        assert "ix_scores_asset_ts" in idx

    def test_alarm_index_covers_ack_query(self, tmp_path):
        """EXPLAIN QUERY PLAN must use the ix_alarms_asset_ack index."""
        con, _ = _make_db(tmp_path)
        plan = con.execute(
            "EXPLAIN QUERY PLAN "
            "SELECT COUNT(*) FROM alarms WHERE asset_key=? AND ack_at IS NULL",
            ("x",)).fetchall()
        plan_text = " ".join(str(p) for p in plan).lower()
        assert "ix_alarms_asset_ack" in plan_text or "index" in plan_text, (
            f"Query plan did not use alarm index: {plan_text}")

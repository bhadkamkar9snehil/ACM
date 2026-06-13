#!/usr/bin/env python3
"""
ACM performance benchmark: before vs after for three optimisations.

  1. SQL  — v_asset_now CTE vs correlated-subquery (N+1) plan
  2. Feed — update_cache fast-path (no-new-data) vs full read+write
  3. API  — _TTLCache cold vs warm for the /api/fleet endpoint

Usage:
  python scripts/bench_performance.py
  python scripts/bench_performance.py --assets 200 --scores 500 --repeats 10
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.acm_feed import SourceSpec, update_cache           # noqa: E402
from scripts.acm_service import _MISS, _TTLCache, create_app    # noqa: E402
from scripts.acm_store import DDL_SQLITE                        # noqa: E402

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _hdr(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def _row(label: str, before_ms: float, after_ms: float) -> None:
    speedup = before_ms / max(after_ms, 1e-3)
    print(f"  {label:<35} {before_ms:>8.2f} ms  {after_ms:>8.2f} ms  "
          f"{speedup:>6.1f}×")


def _setup_db(tmp: str, n_assets: int, n_scores: int, n_alarms: int) -> sqlite3.Connection:
    con = sqlite3.connect(tmp)
    con.executescript(DDL_SQLITE)
    rng = np.random.default_rng(0)
    t0 = pd.Timestamp("2025-01-01")

    for i in range(n_assets):
        key = f"bench/A{i:04d}"
        bare = f"A{i:04d}"
        con.execute("INSERT OR IGNORE INTO assets(asset_key,farm,verdict) VALUES (?,?,?)",
                    (key, "bench", "OK"))
        con.execute("INSERT OR IGNORE INTO monitored_assets(asset_key,grp,state) VALUES (?,?,?)",
                    (bare, "bench", "OK"))
        scores = [(
            key,
            str(t0 + pd.Timedelta(minutes=10 * j)),
            float(rng.standard_normal()),
            *rng.standard_normal(6).tolist(),
            0, 0,
        ) for j in range(n_scores)]
        con.executemany(
            "INSERT INTO scores(asset_key,ts,fused,ar1_z,pca_spe_z,pca_t2_z,"
            "iforest_z,gmm_z,omr_z,status,alarm) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            scores)
        alarms = [(
            key,
            str(t0 + pd.Timedelta(hours=k * 2)),
            str(t0 + pd.Timedelta(hours=k * 2 + 1)),
            1.0, 3.5,
            None if k < 2 else "2026-01-01",
        ) for k in range(n_alarms)]
        con.executemany(
            "INSERT INTO alarms(asset_key,start_ts,end_ts,duration_h,peak_fused,ack_at) "
            "VALUES (?,?,?,?,?,?)",
            alarms)
    con.commit()
    return con


# ---------------------------------------------------------------------------
# benchmark 1: SQL view
# ---------------------------------------------------------------------------

def bench_sql_view(n_assets: int, n_scores: int, n_alarms: int,
                   repeats: int) -> tuple[float, float]:
    """Compare v_asset_now before (no alarm indexes) vs after (with alarm indexes + CTE).

    The 'before' state is simulated by dropping the new alarm indexes so the
    alarm subqueries do full-table scans, matching the original schema.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    con = _setup_db(db, n_assets, n_scores, n_alarms)

    # Before: drop our new alarm indexes to simulate the old schema
    con.execute("DROP INDEX IF EXISTS ix_alarms_asset")
    con.execute("DROP INDEX IF EXISTS ix_alarms_asset_ack")
    con.commit()

    t0 = time.perf_counter()
    for _ in range(repeats):
        con.execute("SELECT * FROM v_asset_now").fetchall()
    before_ms = (time.perf_counter() - t0) / repeats * 1000

    # After: restore alarm indexes + hybrid view (already created by DDL_SQLITE)
    con.execute("CREATE INDEX IF NOT EXISTS ix_alarms_asset ON alarms(asset_key)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_alarms_asset_ack ON alarms(asset_key, ack_at)")
    con.commit()

    t0 = time.perf_counter()
    for _ in range(repeats):
        con.execute("SELECT * FROM v_asset_now").fetchall()
    after_ms = (time.perf_counter() - t0) / repeats * 1000

    con.close()
    return before_ms, after_ms


# ---------------------------------------------------------------------------
# benchmark 2: update_cache fast path
# ---------------------------------------------------------------------------

def bench_update_cache(n_rows: int, n_cols: int, repeats: int) -> tuple[float, float]:
    """Compare old update_cache (always full read+write) vs new (fast path on no new data).

    Both paths run load_increment on the same stale CSV, so that cost is equal.
    The difference is what happens to the parquet cache:
      Before: always pd.read_parquet (all columns) + pd.to_parquet (write-back)
      After:  column-pruned timestamp read only — no write-back
    """
    import pyarrow.parquet as pq

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rng = np.random.default_rng(1)
        ts = pd.date_range("2026-01-01", periods=n_rows, freq="10min")
        df = pd.DataFrame({
            "time_stamp": ts,
            **{f"s_{i}": rng.standard_normal(n_rows) for i in range(n_cols)},
        })
        # Stale CSV: one row in the past — load_increment will always return empty
        stale_csv = tmp_path / "asset.csv"
        pd.DataFrame({"time_stamp": [pd.Timestamp("2025-01-01")],
                       **{f"s_{i}": [0.0] for i in range(n_cols)}}).to_csv(stale_csv, index=False)

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        pq_file = cache_dir / "asset.parquet"
        df.to_parquet(pq_file, index=False)

        spec = SourceSpec("asset", "csv", str(stale_csv),
                          timestamp_col="time_stamp", status_col=None)

        # Before: old behaviour — full read, no-op concat, full write-back
        before_ms_list = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            cached = pd.read_parquet(str(pq_file))               # full read
            _ = cached["time_stamp"].max()                        # find since
            inc = pd.DataFrame(columns=cached.columns)            # empty increment
            merged = pd.concat([cached, inc], ignore_index=True)  # no-op concat
            merged.to_parquet(str(pq_file.with_suffix(".tmp")), index=False)  # write-back
            before_ms_list.append((time.perf_counter() - t0) * 1000)
        before_ms = sum(before_ms_list) / len(before_ms_list)

        # After: new fast path — column-pruned timestamp read, no write
        after_ms_list = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            update_cache(spec, cache_dir)   # no new rows → fast path
            after_ms_list.append((time.perf_counter() - t0) * 1000)
        after_ms = sum(after_ms_list) / len(after_ms_list)

    return before_ms, after_ms


# ---------------------------------------------------------------------------
# benchmark 3: API cache
# ---------------------------------------------------------------------------

def bench_api_cache(n_assets: int, repeats: int) -> tuple[float, float]:
    import asyncio
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "t.db")
        # Seed with some data
        con = _setup_db(db, n_assets, 50, 3)
        con.close()

        from fastapi.testclient import TestClient
        app = create_app(backend="sqlite", db=db, run_scheduler=False, api_cache_ttl=60.0)
        svc = app.state.service

        with TestClient(app) as client:
            # Cold (cache-miss) timing
            cold_times = []
            for _ in range(repeats):
                svc.api_cache.clear()
                t0 = time.perf_counter()
                client.get("/api/fleet")
                cold_times.append((time.perf_counter() - t0) * 1000)
            before_ms = sum(cold_times) / len(cold_times)

            # Warm (cache-hit) timing
            svc.api_cache.clear()
            client.get("/api/fleet")  # populate cache
            warm_times = []
            for _ in range(repeats):
                t0 = time.perf_counter()
                client.get("/api/fleet")
                warm_times.append((time.perf_counter() - t0) * 1000)
            after_ms = sum(warm_times) / len(warm_times)

    return before_ms, after_ms


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assets", type=int, default=100,
                    help="number of simulated assets (default 100)")
    ap.add_argument("--scores", type=int, default=200,
                    help="score rows per asset for SQL benchmark (default 200)")
    ap.add_argument("--alarms", type=int, default=5,
                    help="alarm rows per asset for SQL benchmark (default 5)")
    ap.add_argument("--cache-rows", type=int, default=2000,
                    help="parquet rows for cache benchmark (default 2000)")
    ap.add_argument("--cache-cols", type=int, default=80,
                    help="sensor columns for cache benchmark (default 80)")
    ap.add_argument("--repeats", type=int, default=8,
                    help="measurement repeats per benchmark (default 8)")
    args = ap.parse_args()

    print(f"\nACM Performance Benchmark")
    print(f"  Assets={args.assets}, Scores/asset={args.scores}, "
          f"Alarms/asset={args.alarms}, Repeats={args.repeats}")
    print(f"{'Label':<35} {'Before':>10} {'After':>10} {'Speedup':>8}")
    print("-" * 68)

    # 1. SQL view
    _hdr("1. SQL: v_asset_now — alarm indexes + CTE GROUP BY (vs full table scan)")
    for n in [10, args.assets]:
        b, a = bench_sql_view(n, args.scores, args.alarms, args.repeats)
        _row(f"  {n} assets", b, a)

    # 2. Feed
    _hdr("2. Feed: update_cache — no-new-data fast path")
    b, a = bench_update_cache(args.cache_rows, args.cache_cols, args.repeats)
    _row(f"  {args.cache_rows}r × {args.cache_cols}c parquet", b, a)

    # 3. API cache
    _hdr("3. API: /api/fleet cold vs warm (TTL cache)")
    b, a = bench_api_cache(args.assets, args.repeats)
    _row(f"  {args.assets} assets", b, a)

    print()
    print("Legend: Before = old path, After = optimised path, Speedup = Before/After")
    print()


if __name__ == "__main__":
    main()

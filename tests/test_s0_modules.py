"""Acceptance tests for S0.3 (ingestion), S0.4 (hardware), S0.5 (constants),
S0.6 (scheduler stub)."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl
import pytest

from acm import constants
from acm.hardware import (
    TIER_T0,
    TIER_T1,
    TIER_T2,
    TIER_T2S,
    Governor,
    Probe,
    select_tier,
    set_thread_caps,
)
from acm.ingest import ingest_csv
from acm.scheduler import FleetScheduler
from acm.store.raw import TIMESTAMP_COL, RawStore

UTC = timezone.utc


# ---------------------------------------------------------------- S0.5
def test_every_constant_has_rationale():
    assert constants.REGISTRY, "registry must not be empty"
    for name, c in constants.REGISTRY.items():
        assert c.rationale.strip(), f"{name} has no rationale"
        assert c.name == name


def test_alpha_is_the_dial():
    assert constants.get("ALPHA_PER_ASSET_YEAR") == 1.0


# ---------------------------------------------------------------- S0.4
def test_tier_selection_matrix():
    dev_box = Probe(cpu_count=6, ram_gb=16.0, gpu_name="RTX 4060", gpu_vram_gb=8.0)
    assert select_tier(dev_box) == TIER_T2S
    ci_runner = Probe(cpu_count=4, ram_gb=16.0, gpu_name=None, gpu_vram_gb=0.0)
    assert select_tier(ci_runner) == TIER_T0
    workstation = Probe(cpu_count=16, ram_gb=64.0, gpu_name=None, gpu_vram_gb=0.0)
    assert select_tier(workstation) == TIER_T1
    dgx = Probe(cpu_count=32, ram_gb=256.0, gpu_name="A100", gpu_vram_gb=40.0)
    assert select_tier(dgx) == TIER_T2


def test_governor_caps_workers_on_low_ram():
    dev_box = Probe(cpu_count=6, ram_gb=16.0, gpu_name="RTX 4060", gpu_vram_gb=8.0)
    gov = Governor.from_probe(dev_box)
    assert gov.evidence_workers == 2
    assert gov.blas_threads == 1
    assert gov.tier == TIER_T2S


def test_thread_caps_set(monkeypatch):
    monkeypatch.delenv("OMP_NUM_THREADS", raising=False)
    set_thread_caps(1)
    import os

    assert os.environ["OMP_NUM_THREADS"] == "1"


# ---------------------------------------------------------------- S0.3
def test_ingest_csv_drops_labels_and_is_idempotent(tmp_path):
    csv = tmp_path / "pilot.csv"
    csv.write_text(
        "time_stamp,sensor_a,sensor_b,state\n"
        "2026-01-01T00:00:00Z,1.0,2.0,NORMAL\n"
        "2026-01-01T00:10:00Z,1.1,2.1,NORMAL\n"
        "2026-01-01T00:20:00Z,1.2,2.2,bearing_fault\n"
    )
    store = RawStore(tmp_path / "raw")
    report = ingest_csv(store, "pilot/one", csv)
    assert report.rows_read == 3
    assert report.rows_stored == 3
    assert report.channels == 2
    assert "state" in report.dropped_columns  # labels never enter the store
    again = ingest_csv(store, "pilot/one", csv)
    assert again.rows_stored == 0  # idempotent replay


def test_ingest_naive_timestamps_rejected(tmp_path):
    csv = tmp_path / "naive.csv"
    csv.write_text("timestamp,v\n2026-01-01 00:00:00,1.0\n")
    store = RawStore(tmp_path / "raw")
    with pytest.raises(Exception):
        ingest_csv(store, "bad", csv)


# ---------------------------------------------------------------- S0.6
def test_scheduler_staggers_and_sees_only_new_rows(tmp_path):
    store = RawStore(tmp_path / "raw")
    base = datetime(2026, 1, 1, tzinfo=UTC)

    def rows(n, start_offset=0):
        ts = [base + timedelta(minutes=10 * (start_offset + i)) for i in range(n)]
        return pl.DataFrame(
            {
                TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
                "v": [float(i) for i in range(n)],
            }
        )

    assets = ["a1", "a2", "a3"]
    for a in assets:
        store.append(a, rows(5))

    seen: dict[str, int] = {}

    async def hook(asset_key: str, frame: pl.DataFrame) -> None:
        seen[asset_key] = seen.get(asset_key, 0) + frame.height

    async def scenario():
        sched = FleetScheduler(store, assets, hook, interval_s=0.05)
        run = asyncio.create_task(sched.run())
        await asyncio.sleep(0.30)  # several rounds
        store.append("a1", rows(3, start_offset=5))  # new data arrives
        await asyncio.sleep(0.30)
        sched.stop()
        await run

    asyncio.run(scenario())

    assert seen["a1"] == 8 and seen["a2"] == 5 and seen["a3"] == 5
    ticked = {t.asset_key for t in []}  # placate linters
    del ticked


def test_scheduler_records_costs(tmp_path):
    from acm.hardware import MEASURED_COSTS

    store = RawStore(tmp_path / "raw")
    base = datetime(2026, 1, 1, tzinfo=UTC)
    store.append(
        "c1",
        pl.DataFrame(
            {
                TIMESTAMP_COL: pl.Series([base], dtype=pl.Datetime("us", "UTC")),
                "v": [1.0],
            }
        ),
    )

    async def hook(asset_key, frame):
        return None

    async def scenario():
        sched = FleetScheduler(store, ["c1"], hook, interval_s=0.05)
        run = asyncio.create_task(sched.run())
        await asyncio.sleep(0.15)
        sched.stop()
        await run

    asyncio.run(scenario())
    assert "c1" in MEASURED_COSTS


# ------------------------------------------- availability stream (R4 job)
def test_availability_standstill_alarms():
    """A parked machine (flat telemetry) must alarm via the availability
    stream with attribution 'availability' - even though its magnitude
    surprise is quiet."""
    import numpy as np

    from acm.monitor import AssetMonitor

    rng = np.random.default_rng(21)
    base = datetime(2026, 1, 1, tzinfo=UTC)

    def live(n, off=0):
        ts = [base + timedelta(minutes=10 * (off + i)) for i in range(n)]
        t = rng.normal(size=n)
        return pl.DataFrame(
            {
                TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
                "temp": t,
                "vib": 0.8 * t + 0.3 * rng.normal(size=n),
                "press": rng.normal(size=n),
                "flow": rng.normal(size=n),
            }
        )

    mon = AssetMonitor("av/1")
    assert mon.calibrate(live(5000))
    v = mon.process(live(1200, off=6000))
    assert v.state != "alarm"

    # standstill: every channel freezes at its last value
    frozen = live(1, off=8000)
    n = 1500
    ts = [base + timedelta(minutes=10 * (8001 + i)) for i in range(n)]
    flat = pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "temp": [float(frozen["temp"][0])] * n,
            "vib": [float(frozen["vib"][0])] * n,
            "press": [float(frozen["press"][0])] * n,
            "flow": [float(frozen["flow"][0])] * n,
        }
    )
    v = mon.process(flat)
    assert v.state == "alarm", v.state
    assert v.attribution == ("availability",)
    assert v.evidence_trail.get("domain") == "availability"

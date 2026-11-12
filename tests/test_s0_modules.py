"""Acceptance tests for S0.3 ingestion, S0.4 hardware, and S0.5 constants."""

from datetime import datetime, timedelta, timezone

import polars as pl
import pytest

import constants
import verdict as V
from hardware import (
    TIER_T0,
    TIER_T1,
    TIER_T2,
    TIER_T2S,
    Governor,
    Probe,
    select_tier,
    set_thread_caps,
)
from ingest import ingest_csv
from store.raw import TIMESTAMP_COL, RawStore

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


# ------------------------------------------- availability stream (R4 job)
def test_availability_standstill_alarms():
    """A parked machine must alarm via availability even if magnitude is quiet."""
    import numpy as np

    from monitor import AssetMonitor

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
    assert v.state != V.STATE_ALARM

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
    assert v.state == V.STATE_ALARM, v.state
    assert v.attribution == ("availability",)
    assert v.evidence_trail.get("domain") == "availability"

"""S1 end-to-end acceptance: synthetic pilot through the full spine
(store -> scorer -> e-process bank -> verdict), CI-hermetic."""

import asyncio
from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl

from acm import verdict as V
from acm.monitor import AssetMonitor, render_report
from acm.scheduler import FleetScheduler
from acm.store.raw import TIMESTAMP_COL, RawStore

UTC = timezone.utc


def synth_frame(n, start, rng, shift=0.0, drift_to=0.0):
    ts = [start + timedelta(minutes=10 * i) for i in range(n)]
    base = rng.normal(size=(n, 4))
    if shift:
        base[:, 0] += shift  # single-channel fault
    if drift_to:
        base[:, 1] += np.linspace(0, drift_to, n)
    return pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "temp": base[:, 0],
            "vib": base[:, 1],
            "press": base[:, 2],
            "flow": base[:, 3],
        }
    )


def test_e2e_healthy_stays_healthy_and_fault_alarms():
    rng = np.random.default_rng(11)
    start = datetime(2026, 1, 1, tzinfo=UTC)

    mon = AssetMonitor("synt/a")
    assert mon.calibrate(synth_frame(4000, start, rng))

    healthy = mon.process(synth_frame(1500, start + timedelta(days=40), rng))
    assert healthy.state in (V.STATE_HEALTHY, V.STATE_WATCH)
    assert healthy.state != V.STATE_ALARM

    faulty = mon.process(
        synth_frame(2500, start + timedelta(days=60), rng, shift=3.0)
    )
    assert faulty.state == V.STATE_ALARM
    assert faulty.evidence >= 1.0
    assert "temp" in faulty.attribution[:2]  # right channel blamed
    assert faulty.model_epoch.startswith("s4-condsurprise")
    assert faulty.falsifiable_by


def test_e2e_slow_drift_detected():
    rng = np.random.default_rng(12)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    mon = AssetMonitor("synt/drift")
    assert mon.calibrate(synth_frame(4000, start, rng))
    v = mon.process(
        synth_frame(4000, start + timedelta(days=40), rng, drift_to=2.5)
    )
    assert v.state == V.STATE_ALARM
    assert "vib" in v.attribution[:2]


def test_insufficient_history_verdict():
    rng = np.random.default_rng(13)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    mon = AssetMonitor("synt/new")
    assert not mon.calibrate(synth_frame(20, start, rng))
    v = mon.process(synth_frame(10, start + timedelta(days=1), rng))
    assert v.state == V.STATE_INSUFFICIENT
    assert v.confidence == 0.0


def test_spine_through_scheduler(tmp_path):
    """Store -> scheduler -> monitor hook -> verdicts, as deployed."""
    rng = np.random.default_rng(14)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    store = RawStore(tmp_path / "raw")
    store.append("s/1", synth_frame(4000, start, rng))

    mon = AssetMonitor("s/1")
    assert mon.calibrate(store.read("s/1"))
    verdicts = []

    async def hook(asset_key, frame):
        verdicts.append(mon.process(frame))

    async def scenario():
        sched = FleetScheduler(store, ["s/1"], hook, interval_s=0.05)
        run = asyncio.create_task(sched.run())
        await asyncio.sleep(0.15)
        store.append(
            "s/1", synth_frame(2500, start + timedelta(days=40), rng, shift=3.0)
        )
        await asyncio.sleep(0.25)
        sched.stop()
        await run

    asyncio.run(scenario())
    states = [v.state for v in verdicts]
    assert states[-1] == V.STATE_ALARM, states


def test_report_renders():
    rng = np.random.default_rng(15)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    mon = AssetMonitor("r/1")
    mon.calibrate(synth_frame(4000, start, rng))
    v = mon.process(synth_frame(500, start + timedelta(days=40), rng))
    text = render_report([v])
    assert "r/1" in text and v.state in text and v.model_epoch in text

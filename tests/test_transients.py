"""C7 acceptance: healthy transients recur near their siblings; a degraded
transient response is far from every sibling; the 401st start-up is judged
against the previous 400."""

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from acm.scoring.transients import TransientCatalogue

from acm.store.raw import TIMESTAMP_COL

UTC = timezone.utc
pytestmark = pytest.mark.statistical


def machine_with_starts(n_cycles, seed=0, degraded_last=0, slow_factor=3.0):
    """Steady operation punctuated by start-up ramps. Degraded starts ramp
    slower with overshoot - the classic worn-machine signature."""
    rng = np.random.default_rng(seed)
    rows = []
    for c in range(n_cycles):
        steady = rng.normal(size=(300, 3)) * 0.3
        ramp_len = 20
        t = np.linspace(0, 1, ramp_len)
        degraded = c >= n_cycles - degraded_last
        if degraded:
            shape = 1 - np.exp(-t * (3.0 / slow_factor))
            shape = shape / shape.max()
            shape = shape + 0.35 * np.sin(t * 9)  # overshoot/ring
        else:
            shape = 1 - np.exp(-t * 3.0)
            shape = shape / shape.max()
        ramp = np.column_stack([shape * 5, shape * 4, shape * 3])
        ramp += rng.normal(size=(ramp_len, 3)) * 0.15
        rows.append(np.vstack([ramp, steady]))
    x = np.vstack(rows)
    ts = [
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=10 * i)
        for i in range(x.shape[0])
    ]
    return pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "speed": x[:, 0],
            "load": x[:, 1],
            "temp": x[:, 2],
        }
    )


def test_catalogue_finds_healthy_transients():
    cat = TransientCatalogue().fit(machine_with_starts(30, seed=1))
    assert cat.fingerprints.shape[0] >= 20  # most starts catalogued
    calib = cat.calibration_scores()
    assert abs(float(np.median(calib))) < 1.0


def test_healthy_new_starts_score_low_degraded_score_high():
    cat = TransientCatalogue().fit(machine_with_starts(40, seed=2))
    fresh_ok = cat.score_new(machine_with_starts(6, seed=3))
    assert fresh_ok.size >= 4
    assert float(np.median(fresh_ok)) < 3.0, fresh_ok

    worn = cat.score_new(
        machine_with_starts(6, seed=4, degraded_last=6)
    )
    assert worn.size >= 4
    assert float(np.median(worn)) > 3 * max(float(np.median(fresh_ok)), 0.5), (
        fresh_ok, worn,
    )


def test_no_transients_means_no_evidence():
    cat = TransientCatalogue().fit(machine_with_starts(30, seed=5))
    rng = np.random.default_rng(6)
    n = 500
    ts = [
        datetime(2026, 6, 1, tzinfo=UTC) + timedelta(minutes=10 * i)
        for i in range(n)
    ]
    steady_only = pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "speed": rng.normal(size=n) * 0.3,
            "load": rng.normal(size=n) * 0.3,
            "temp": rng.normal(size=n) * 0.3,
        }
    )
    assert cat.score_new(steady_only).size == 0


def test_thin_catalogue_refuses():
    with pytest.raises(ValueError, match="catalogue"):
        TransientCatalogue().fit(machine_with_starts(3, seed=7))


def test_monitor_alarms_on_degraded_starts_end_to_end():
    """The 41st..46th start-ups ramp slow with overshoot: the monitor
    alarms via the transient-response domain."""
    from acm.monitor import AssetMonitor

    mon = AssetMonitor("tr/1")
    assert mon.calibrate(machine_with_starts(40, seed=10))
    assert mon.trans_bank is not None, "catalogue must have been built"
    ok = mon.process(machine_with_starts(6, seed=11))
    assert ok.state != "alarm"
    v = mon.process(machine_with_starts(8, seed=12, degraded_last=8))
    assert v.state == "alarm", v.state
    assert v.attribution == ("transient-response",)

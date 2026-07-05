"""C9 acceptance: the horizon gap sees slow drift before short-horizon
surprise does, and the predictability band is two-sided."""

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from acm2.scoring.horizons import MultiHorizonScorer
from acm2.store.raw import TIMESTAMP_COL

UTC = timezone.utc
pytestmark = pytest.mark.statistical


def ar_frame(n, seed=0, drift_to=0.0, damp=1.0):
    """AR(1)-ish coupled channels; optional slow drift; optional damping
    (damp < 1 makes the machine TOO predictable - variance collapse)."""
    rng = np.random.default_rng(seed)
    ts = [
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=10 * i)
        for i in range(n)
    ]
    x = np.zeros((n, 3))
    for t in range(1, n):
        x[t] = 0.9 * x[t - 1] + damp * 0.4 * rng.normal(size=3)
    if drift_to:
        x[:, 0] += np.linspace(0, drift_to, n)
    return pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "a": x[:, 0],
            "b": x[:, 1],
            "c": x[:, 2],
        }
    )


def test_healthy_gap_near_zero():
    frame = ar_frame(8000, seed=1)
    sc = MultiHorizonScorer().fit(frame.head(5000))
    gap = sc.gap_stream(frame.slice(5000))
    assert abs(float(np.median(gap))) < 1.0, float(np.median(gap))


def test_gap_sees_slow_drift_before_short_horizon():
    """THE C9 CLAIM: under slow drift, the long-horizon surprise elevates
    while the short-horizon (tracking) surprise barely moves."""
    healthy = ar_frame(6000, seed=2)
    sc = MultiHorizonScorer().fit(healthy)
    drifted = ar_frame(4000, seed=3, drift_to=3.0)
    s = sc.surprise(drifted)
    h_s, h_l = min(sc.horizons), max(sc.horizons)
    short_elev = (np.mean(s[h_s]) - sc.healthy_center[h_s]) / sc.healthy_spread[h_s]
    long_elev = (np.mean(s[h_l]) - sc.healthy_center[h_l]) / sc.healthy_spread[h_l]
    assert long_elev > 2 * short_elev, (short_elev, long_elev)
    gap = sc.gap_stream(drifted)
    assert float(np.median(gap)) > 1.0  # the early-warning statistic fires


def test_bilateral_band_catches_too_predictable():
    """A damped (dying-dynamics) machine is BELOW the healthy band - the
    one-sided surprise never sees it; the bilateral stream does."""
    healthy = ar_frame(6000, seed=4)
    sc = MultiHorizonScorer().fit(healthy)
    ok = sc.bilateral_stream(ar_frame(3000, seed=5))
    dead = sc.bilateral_stream(ar_frame(3000, seed=6, damp=0.05))
    assert float(np.median(dead)) > 3 * float(np.median(ok)), (
        float(np.median(ok)), float(np.median(dead)),
    )
    # and the raw one-sided surprise indeed does NOT see it (documents why
    # the band must be two-sided)
    s_dead = sc.surprise(ar_frame(3000, seed=6, damp=0.05))
    h = min(sc.horizons)
    assert np.mean(s_dead[h]) < sc.healthy_center[h] + sc.healthy_spread[h]


def test_thin_data_refuses():
    with pytest.raises(ValueError):
        MultiHorizonScorer().fit(ar_frame(200))


def test_monitor_alarms_via_predictability_band_end_to_end():
    """A machine whose dynamics die (damped, too predictable) alarms via
    the band domain even though magnitude surprise stays quiet."""
    from acm2.monitor import AssetMonitor

    healthy = ar_frame(9000, seed=7)
    mon = AssetMonitor("hz/1")
    assert mon.calibrate(healthy)
    ok = mon.process(ar_frame(2500, seed=8))
    assert ok.state != "alarm"
    v = mon.process(ar_frame(4000, seed=9, damp=0.05))
    assert v.state == "alarm", v.state
    assert v.attribution[0] in ("predictability-band", "horizon-gap")
    assert v.evidence_trail.get("domain") in (
        "predictability-band",
        "horizon-gap",
    )

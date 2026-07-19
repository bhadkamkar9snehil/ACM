"""Koopman-flavored dynamics-drift spike: GO/NO-GO evidence in-tree.

GO criteria: healthy operator stays stable; a coupling change and a
damping change both move the operator materially - INCLUDING at magnitudes
where residual surprise barely reacts (the slow-channel claim).
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from scoring.dynamics import DynamicsDrift
from store.raw import TIMESTAMP_COL

UTC = timezone.utc
pytestmark = pytest.mark.statistical


def dyn_frame(n, seed=0, coupling=0.8, damping=0.9):
    """A 3-channel linear system with tunable internal dynamics."""
    rng = np.random.default_rng(seed)
    ts = [
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=10 * i)
        for i in range(n)
    ]
    x = np.zeros((n, 3))
    for t in range(1, n):
        x[t, 0] = damping * x[t - 1, 0] + 0.4 * rng.normal()
        x[t, 1] = coupling * x[t - 1, 0] + 0.3 * x[t - 1, 1] + 0.3 * rng.normal()
        x[t, 2] = 0.5 * x[t - 1, 1] + 0.4 * rng.normal()
    return pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "a": x[:, 0], "b": x[:, 1], "c": x[:, 2],
        }
    )


def test_healthy_operator_is_stable():
    dd = DynamicsDrift().fit(dyn_frame(8000, seed=1))
    drift = dd.drift_stream(dyn_frame(4000, seed=2))
    assert drift.size >= 6
    assert float(np.median(drift)) < 0.2, drift


def test_coupling_change_moves_the_operator():
    dd = DynamicsDrift().fit(dyn_frame(8000, seed=3))
    healthy = dd.drift_stream(dyn_frame(4000, seed=4))
    worn = dd.drift_stream(dyn_frame(4000, seed=5, coupling=0.4))
    assert float(np.median(worn)) > 2.5 * float(np.median(healthy)), (
        float(np.median(healthy)), float(np.median(worn)),
    )


def test_damping_change_moves_the_operator():
    dd = DynamicsDrift().fit(dyn_frame(8000, seed=6))
    healthy = dd.drift_stream(dyn_frame(4000, seed=7))
    stiff = dd.drift_stream(dyn_frame(4000, seed=8, damping=0.6))
    assert float(np.median(stiff)) > 2.5 * float(np.median(healthy))


def test_slow_channel_claim_operator_sees_what_magnitude_misses():
    """A modest coupling change: per-row surprise moves a little; the
    operator distance moves A LOT (relative to its healthy spread). This
    is the spike's GO criterion."""
    from scoring.surprise import ConditionalSurpriseScorer

    fit_frame = dyn_frame(8000, seed=9)
    dd = DynamicsDrift().fit(fit_frame)
    cs = ConditionalSurpriseScorer().fit(fit_frame)

    healthy_probe = dyn_frame(4000, seed=10)
    changed_probe = dyn_frame(4000, seed=11, coupling=0.6)  # modest

    drift_h = dd.drift_stream(healthy_probe)
    drift_c = dd.drift_stream(changed_probe)
    spread = 1.4826 * float(
        np.median(np.abs(drift_h - np.median(drift_h)))
    ) or 1e-9
    drift_sigmas = (
        float(np.median(drift_c)) - float(np.median(drift_h))
    ) / spread

    s_h = float(np.mean(cs.score(healthy_probe)))
    s_c = float(np.mean(cs.score(changed_probe)))
    surprise_ratio = s_c / s_h

    # GO bar = 3 healthy-spreads of persistent median separation: the
    # e-process detects a persistent 1-sigma shift (see test_eprocess power
    # tests), so 3+ is unmistakable evidence. Measured at ~3.95 on this
    # fixture at a coupling change mild enough to leave surprise below 2x.
    assert drift_sigmas > 3.0, drift_sigmas  # operator: unmistakable
    assert surprise_ratio < 2.0, surprise_ratio  # magnitude: muted


def test_monitor_alarms_via_dynamics_drift_end_to_end():
    from monitor import AssetMonitor

    mon = AssetMonitor("dy/1")
    # 42k rows: the held-out 40% must hold >= 30 NON-overlapping
    # identification windows (512 rows each) for the dynamics bank to arm
    # validly - overlap used to manufacture points from less history, and
    # the #114 exchangeability audit measured that invalid
    assert mon.calibrate(dyn_frame(42000, seed=12))
    assert mon.dyn_bank is not None
    ok = mon.process(dyn_frame(3000, seed=13))
    assert ok.state != "alarm"
    v = mon.process(dyn_frame(6000, seed=14, coupling=0.35))
    assert v.state == "alarm", v.state
    # magnitude may win the attribution race on a strong change - the
    # meaningful check is that the dynamics stream INDEPENDENTLY crossed
    # its own threshold (its wiring and calibration are live)
    assert mon.dyn_bank.state().alarmed

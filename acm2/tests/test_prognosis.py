"""S8 acceptance: failure-time distributions that cover the truth, and a
self-gate that never shows an uncalibrated date (D8 is absolute)."""

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from acm2 import verdict as V
from acm2.episodes import EpisodicMonitor
from acm2.memory.ledger import EpisodeLedger
from acm2.monitor import AssetMonitor
from acm2.prognosis import horizon
from acm2.store.raw import TIMESTAMP_COL

UTC = timezone.utc
pytestmark = pytest.mark.statistical


# ------------------------------------------------------------ the math
def test_horizon_covers_true_crossing():
    """Known Wiener drift -> the IG credible interval must cover the true
    first-passage time (constructed, so the truth is known)."""
    rng = np.random.default_rng(1)
    mu_true, sigma_true, start_level = 0.05, 0.1, 1.0
    crit = 9.0  # comfortably ahead of the observed stretch
    # observe the first 100 steps of the degradation (ends near 6.0)
    inc = mu_true + sigma_true * rng.normal(size=100)
    index = start_level + np.cumsum(inc)
    h = horizon(index, healthy_center=1.0, healthy_spread=0.2,
                ledger_onset_levels=[crit])
    assert h.gated and h.reason == "drift-calibrated"
    assert not h.provisional_level
    true_remaining_steps = (crit - index[-1]) / mu_true
    assert h.p10_steps < true_remaining_steps < h.p90_steps, (
        h.p10_steps, true_remaining_steps, h.p90_steps,
    )
    # median in the right ballpark (factor-2 band)
    assert 0.5 * true_remaining_steps < h.median_steps < 2.0 * true_remaining_steps


def test_gate_refuses_without_trend():
    rng = np.random.default_rng(2)
    flat = 1.0 + 0.1 * rng.normal(size=300)  # stationary healthy index
    h = horizon(flat, 1.0, 0.1)
    assert not h.gated
    assert "trend" in h.reason


def test_gate_refuses_thin_trajectory():
    h = horizon(np.linspace(1, 2, 10), 1.0, 0.1)
    assert not h.gated
    assert "insufficient" in h.reason


def test_provisional_level_flagged():
    rng = np.random.default_rng(3)
    index = 1.0 + np.cumsum(0.05 + 0.05 * rng.normal(size=200))
    h = horizon(index, 1.0, 0.2)  # no ledger levels
    assert h.gated
    assert h.provisional_level  # honesty: the level is a default, say so


# ------------------------------------------------ end-to-end escalating
def coupled(n, start, rng, fault=0.0):
    ts = [start + timedelta(minutes=10 * i) for i in range(n)]
    temp = rng.normal(size=n)
    vib = 0.8 * temp + 0.3 * rng.normal(size=n) + fault * np.linspace(0, 1, n)
    press = rng.normal(size=n)
    flow = rng.normal(size=n)
    load = 0.6 * temp + 0.4 * flow + 0.3 * rng.normal(size=n)
    return pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "temp": temp, "vib": vib, "press": press,
            "flow": flow, "load": load,
        }
    )


def test_escalating_verdict_carries_horizon(tmp_path):
    rng = np.random.default_rng(4)
    start = datetime(2025, 1, 1, tzinfo=UTC)
    ledger = EpisodeLedger(tmp_path / "ledger.json")
    em = EpisodicMonitor(AssetMonitor("pg/1"), ledger)
    assert em.monitor.calibrate(coupled(6000, start, rng))
    # healthy stretch builds the index baseline
    em.process(coupled(2000, start + timedelta(days=50), rng))
    # slow developing fault
    v = em.process(
        coupled(6000, start + timedelta(days=60), rng, fault=5.0)
    )
    assert v.state == V.STATE_ESCALATING
    hz = v.evidence_trail.get("horizon")
    assert hz is not None
    # either a calibrated horizon or an honest gated refusal - but the
    # field must exist and be explicit either way
    assert "gated" in hz and "reason" in hz
    if hz["gated"]:
        assert hz["median_steps"] is not None
        assert hz["p10_steps"] <= hz["median_steps"] <= hz["p90_steps"]

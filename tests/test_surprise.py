"""S4 acceptance: the conditional surprise substrate.

The headline is THE FLIP: the correlation-break blindness pinned at S2
must be gone under the new default scorer.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from immune import sensitivity_profile
from monitor import AssetMonitor
from scoring.surprise import (
    ConditionalSurpriseScorer,
    classify_pit_distortion,
    ks_uniform,
)
from store.raw import TIMESTAMP_COL
from tests.marginal_scorer import MarginalRobustZScorer

UTC = timezone.utc
pytestmark = pytest.mark.statistical


def correlated_frame(n=8000, seed=1, break_from=None, fault_channel="vib"):
    """Physically-coupled channels: vib and load follow temp; press follows
    flow. Optionally break one channel's coupling from index break_from."""
    rng = np.random.default_rng(seed)
    ts = [
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=10 * i)
        for i in range(n)
    ]
    temp = rng.normal(size=n)
    flow = rng.normal(size=n)
    vib = 0.8 * temp + 0.3 * rng.normal(size=n)
    load = 0.6 * temp + 0.4 * flow + 0.3 * rng.normal(size=n)
    press = 0.9 * flow + 0.3 * rng.normal(size=n)
    data = {"temp": temp, "vib": vib, "load": load, "press": press, "flow": flow}
    if break_from is not None:
        x = data[fault_channel].copy()
        x[break_from:] = rng.permutation(x[break_from:])
        data[fault_channel] = x
    return pl.DataFrame(
        {TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")), **data}
    )


# ------------------------------------------------------------ THE FLIP
def test_s4_flip_correlation_break_detected():
    """The S2-pinned blindness is gone under the production scorer."""
    report = sensitivity_profile("synt/flip", correlated_frame())
    assert report.conformance_ok
    assert report.floors["correlation_break"] is not None, (
        "conditional scorer must detect correlation breaks"
    )


def test_break_detected_and_attributed_end_to_end():
    frame = correlated_frame(n=10000)
    mon = AssetMonitor("synt/corr")
    assert mon.calibrate(frame.head(6000))
    clean = mon.process(frame.slice(6000, 1500))
    assert clean.state != "alarm"
    broken = correlated_frame(n=10000, seed=1, break_from=7500)
    v = mon.process(broken.slice(7500))
    assert v.state == "alarm"
    assert "vib" in v.attribution[:2], v.attribution


# ---------------------------------------------------------------- PIT
def test_pit_uniform_on_healthy():
    frame = correlated_frame()
    scorer = ConditionalSurpriseScorer().fit(frame.head(5000))
    pits = scorer.pit(frame.slice(5000))
    verdict, ks = classify_pit_distortion(pits, scorer.channels)
    assert verdict == "ok", ks
    assert all(d < 0.1 for d in ks.values())


def test_pit_classifies_channel_fault():
    frame = correlated_frame()
    scorer = ConditionalSurpriseScorer().fit(frame.head(5000))
    faulty = correlated_frame(seed=1, break_from=5000)
    pits = scorer.pit(faulty.slice(5000))
    verdict, ks = classify_pit_distortion(pits, scorer.channels)
    assert verdict == "channels", ks
    assert ks["vib"] > 0.1


def test_pit_classifies_sick_model():
    """A model fit on the wrong asset distorts most channels at once."""
    scorer = ConditionalSurpriseScorer().fit(correlated_frame(seed=1).head(5000))
    other_machine = correlated_frame(seed=99)
    other_machine = other_machine.with_columns(
        (pl.col("vib") * 0.1 + 3.0).alias("vib"),
        (pl.col("load") * 5.0 - 2.0).alias("load"),
        (pl.col("press") * 2.5).alias("press"),
    )
    pits = scorer.pit(other_machine.slice(5000))
    verdict, _ks = classify_pit_distortion(pits, scorer.channels)
    assert verdict == "model"


def test_ks_uniform_sane():
    rng = np.random.default_rng(0)
    assert ks_uniform(rng.uniform(size=5000)) < 0.03
    assert ks_uniform(np.full(1000, 0.5)) > 0.4


# ------------------------------------------------- power vs the marginal
def test_conditional_beats_marginal_on_coupled_drift():
    """Conditional surprise gains power by subtracting explained variance."""
    frame = correlated_frame(n=12000, seed=3)
    fit, rest = frame.head(6000), frame.slice(6000)
    drift = np.linspace(0, 1.2, rest.height)
    drifted = rest.with_columns(
        (pl.col("vib") + pl.Series(drift)).alias("vib")
    )
    cond = ConditionalSurpriseScorer().fit(fit)
    marg = MarginalRobustZScorer().fit(fit)
    tail = drifted.tail(2000)
    cond_ratio = float(
        np.mean(cond.score(tail)) / np.mean(cond.score(rest.head(2000)))
    )
    marg_ratio = float(
        np.mean(marg.score(tail)) / np.mean(marg.score(rest.head(2000)))
    )
    assert cond_ratio > marg_ratio, (cond_ratio, marg_ratio)


def test_fit_survives_null_rows():
    """Fit-side NaN handling must match score-side."""
    frame = correlated_frame(n=4000, seed=7)
    vib = frame.get_column("vib").to_numpy().copy()
    vib[100] = np.nan
    vib[2000] = np.nan
    vib[3500] = np.nan
    frame = frame.with_columns(pl.Series("vib", vib))
    scorer = ConditionalSurpriseScorer().fit(frame.head(2400))
    scores = scorer.score(frame.tail(1600))
    assert np.isfinite(scores).all(), "scores must stay finite"
    assert float(scores.std()) > 0, "scorer must be alive, not degenerate"

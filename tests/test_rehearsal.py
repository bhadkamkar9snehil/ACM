"""C8 acceptance: the rehearsed manifold yields a measured sensitivity
floor; coherent (propagated) faults are harder than naive ones; a dead
pipeline rehearses to an all-miss map."""

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from acm.immune.rehearsal import rehearse
from acm.scoring.surprise import ConditionalSurpriseScorer
from acm.store.raw import TIMESTAMP_COL

UTC = timezone.utc
pytestmark = pytest.mark.statistical


def coupled(n, seed=0):
    rng = np.random.default_rng(seed)
    ts = [
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=10 * i)
        for i in range(n)
    ]
    temp = rng.normal(size=n)
    flow = rng.normal(size=n)
    return pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "temp": temp,
            "vib": 0.8 * temp + 0.3 * rng.normal(size=n),
            "load": 0.6 * temp + 0.4 * flow + 0.3 * rng.normal(size=n),
            "flow": flow,
            "press": 0.9 * flow + 0.25 * rng.normal(size=n),
        }
    )


@pytest.fixture(scope="module")
def fitted():
    frame = coupled(9000, seed=1)
    fit, held = frame.head(5000), frame.slice(5000, 2500)
    scorer = ConditionalSurpriseScorer().fit(fit)
    calib = scorer.score(frame.slice(7500))
    return scorer, held, calib


def test_rehearsal_produces_measured_floors(fitted):
    scorer, held, calib = fitted
    rmap = rehearse(scorer, held, calib, seed=1)
    assert rmap.overall_floor is not None
    assert rmap.overall_floor <= 2.0, rmap.floors  # coupled channels: visible
    assert 0.2 < rmap.detected_fraction <= 1.0
    assert rmap.scope  # honesty: the map states what it covers


def test_coherent_propagation_is_harder_or_equal(fitted):
    """The gem-plan claim behind coherent synthesis: a propagated fault
    explains part of itself away, so per-cell detections at p=0.5 never
    exceed those at p=0 for the same channel/shape."""
    scorer, held, calib = fitted
    rmap = rehearse(scorer, held, calib, seed=2)
    for ch_shape in {k.rsplit("|", 1)[0] for k in rmap.cells}:
        naive = set(rmap.cells.get(f"{ch_shape}|p0.0", {}).get("detected_at", []))
        coherent = set(rmap.cells.get(f"{ch_shape}|p0.5", {}).get("detected_at", []))
        assert coherent <= naive or min(coherent, default=99) >= min(
            naive, default=99
        ), (ch_shape, naive, coherent)


def test_dead_pipeline_rehearses_to_all_miss(fitted):
    scorer, held, calib = fitted

    class DeadScorer:
        channels = scorer.channels
        betas = scorer.betas
        scales = scorer.scales
        _aligned_matrix = scorer._aligned_matrix

        def score(self, frame):
            return np.zeros(frame.height)

    rmap = rehearse(DeadScorer(), held, np.zeros(500), seed=3)
    assert rmap.overall_floor is None
    assert all(f is None for f in rmap.floors.values())

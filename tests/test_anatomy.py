"""C6 acceptance: organs discovered from data alone, no spurious
cross-organ edges (stability selection), and propagation-order root cause."""

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from acm2.anatomy import Anatomy
from acm2.scoring.surprise import ConditionalSurpriseScorer
from acm2.store.raw import TIMESTAMP_COL

UTC = timezone.utc
pytestmark = pytest.mark.statistical


def two_organ_machine(n, seed=0, fault_from=None):
    """Organ A: temp drives vib and load. Organ B: flow drives press and
    power. No cross-coupling. Optional fault: vib decouples, then (200
    rows later) load follows - propagation inside organ A."""
    rng = np.random.default_rng(seed)
    ts = [
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=10 * i)
        for i in range(n)
    ]
    temp = rng.normal(size=n)
    flow = rng.normal(size=n)
    vib = 0.9 * temp + 0.25 * rng.normal(size=n)
    load = 0.8 * temp + 0.3 * rng.normal(size=n)
    press = 0.9 * flow + 0.25 * rng.normal(size=n)
    power = 0.8 * flow + 0.3 * rng.normal(size=n)
    if fault_from is not None:
        ramp = np.zeros(n)
        ramp[fault_from:] = np.linspace(0, 6, n - fault_from)
        vib = vib + ramp
        lag = min(fault_from + 200, n)
        ramp2 = np.zeros(n)
        ramp2[lag:] = np.linspace(0, 4, n - lag)
        load = load + ramp2
    return pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "temp": temp, "vib": vib, "load": load,
            "flow": flow, "press": press, "power": power,
        }
    )


def test_organs_discovered():
    anatomy = Anatomy.learn(two_organ_machine(6000, seed=1), seed=1)
    organ_sets = [set(o) for o in anatomy.organs if len(o) > 1]
    assert {"temp", "vib", "load"} in organ_sets
    assert {"flow", "press", "power"} in organ_sets
    # stability selection: the two organs are never merged
    assert len(organ_sets) == 2


def test_per_organ_surprise_localizes():
    healthy = two_organ_machine(6000, seed=2)
    anatomy = Anatomy.learn(healthy, seed=2)
    scorer = ConditionalSurpriseScorer().fit(healthy)
    faulty = two_organ_machine(2000, seed=3, fault_from=200)
    org_s = anatomy.organ_surprise(scorer, faulty)
    a = next(v for o, v in org_s.items() if "vib" in o)
    b = next(v for o, v in org_s.items() if "press" in o)
    assert a > 3 * b, (a, b)


def test_origin_is_the_earliest_organ():
    healthy = two_organ_machine(8000, seed=4)
    anatomy = Anatomy.learn(healthy, seed=4)
    scorer = ConditionalSurpriseScorer().fit(healthy)
    episode = two_organ_machine(3000, seed=5, fault_from=300)
    result = anatomy.origin(scorer, episode)
    assert result["origin"] is not None
    assert "vib" in result["origin"], result


def test_alarm_verdict_carries_anatomical_root_cause():
    from acm2.episodes import EpisodicMonitor
    from acm2.memory.ledger import EpisodeLedger
    from acm2.monitor import AssetMonitor
    import tempfile
    from pathlib import Path

    d = Path(tempfile.mkdtemp())
    em = EpisodicMonitor(
        AssetMonitor("an/1"), EpisodeLedger(d / "l.json")
    )
    assert em.monitor.calibrate(two_organ_machine(8000, seed=6))
    assert em.monitor.anatomy is not None
    v = em.process(two_organ_machine(3000, seed=7, fault_from=300))
    assert v.state in ("alarm", "escalating")
    anat = v.evidence_trail.get("anatomy")
    assert anat is not None
    assert anat["origin"] and "vib" in anat["origin"]

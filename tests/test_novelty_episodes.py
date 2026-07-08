"""S5 acceptance: MASS correctness, novelty semantics, shape
discrimination, and the full episode loop (alarm -> ledger -> reanchor ->
healthy again)."""

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from acm2 import verdict as V
from acm2.episodes import EpisodicMonitor
from acm2.memory.ledger import EpisodeLedger
from acm2.monitor import AssetMonitor
from acm2.novelty import (
    NoveltyEngine,
    classify_shape,
    kendall_tau,
    mass_distance_profile,
)
from acm2.store.raw import TIMESTAMP_COL, RawStore

UTC = timezone.utc
pytestmark = pytest.mark.statistical


# ------------------------------------------------------------ MASS
def test_mass_matches_brute_force():
    rng = np.random.default_rng(1)
    t = rng.normal(size=500)
    q = rng.normal(size=32)
    fast = mass_distance_profile(q, t)

    def znorm(x):
        s = x.std()
        return (x - x.mean()) / s if s > 1e-12 else x * 0

    brute = np.array(
        [
            np.linalg.norm(znorm(q) - znorm(t[i : i + 32]))
            for i in range(500 - 32 + 1)
        ]
    )
    np.testing.assert_allclose(fast, brute, atol=1e-6)


def test_mass_finds_planted_match():
    rng = np.random.default_rng(2)
    t = rng.normal(size=2000)
    q = t[700:764].copy()
    profile = mass_distance_profile(q, t)
    assert int(np.argmin(profile)) == 700
    assert profile[700] < 1e-6


# --------------------------------------------------------- novelty
def test_recurring_pattern_is_not_novel():
    rng = np.random.default_rng(3)
    day = np.sin(np.linspace(0, 2 * np.pi, 144))
    eng = NoveltyEngine(window=64)
    for _ in range(30):  # a month of daily cycles
        eng.extend(day + 0.1 * rng.normal(size=144))
    assert eng.novelty(day + 0.1 * rng.normal(size=144)) < 0.25


def test_unprecedented_shape_is_novel():
    rng = np.random.default_rng(4)
    eng = NoveltyEngine(window=64)
    for _ in range(30):
        eng.extend(np.sin(np.linspace(0, 2 * np.pi, 144)) + 0.1 * rng.normal(size=144))
    spike_ramp = np.concatenate([np.zeros(40), np.exp(np.linspace(0, 3, 60)), np.zeros(44)])
    assert eng.novelty(spike_ramp) > 0.5


def test_novelty_never_alarms_on_ignorance():
    eng = NoveltyEngine(window=64)
    eng.extend(np.random.default_rng(0).normal(size=70))
    assert eng.novelty(np.ones(64)) == 0.0  # thin history -> no novelty claim


# ----------------------------------------------------------- shape
def test_shape_classification():
    rng = np.random.default_rng(5)
    drift = np.linspace(0, 4, 600) + 0.3 * rng.normal(size=600)
    step = np.concatenate([np.full(300, 3.0), np.full(300, 3.1)]) + 0.3 * rng.normal(size=600)
    assert classify_shape(drift) == "drift"
    assert classify_shape(step) == "step"
    assert kendall_tau(np.arange(50.0)) == 1.0


# ------------------------------------------------- the episode loop
def coupled_frame(n, start, rng, fault=0.0, setpoint=0.0):
    """Six coupled channels. A setpoint change is a COORDINATED move (all
    drivers shift, followers follow); a fault is LOCAL to vib."""
    ts = [start + timedelta(minutes=10 * i) for i in range(n)]
    temp = rng.normal(size=n) + setpoint
    flow = rng.normal(size=n) + setpoint
    press = rng.normal(size=n) + setpoint
    vib = 0.8 * temp + 0.3 * rng.normal(size=n) + fault * np.linspace(0, 1, n)
    load = 0.6 * temp + 0.4 * flow + 0.3 * rng.normal(size=n)
    power = 0.7 * flow + 0.3 * press + 0.3 * rng.normal(size=n)
    return pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "temp": temp,
            "vib": vib,
            "press": press,
            "flow": flow,
            "load": load,
            "power": power,
        }
    )


def test_full_episode_loop(tmp_path):
    """alarm (escalating drift) -> episode in ledger -> reanchor ->
    ledger-masked recalibration -> healthy on clean data again."""
    rng = np.random.default_rng(6)
    start = datetime(2025, 1, 1, tzinfo=UTC)
    store = RawStore(tmp_path / "raw")
    # 6 healthy months in the store
    for m in range(6):
        store.append(
            "ep/1",
            coupled_frame(1200, start + timedelta(days=30 * m), rng),
        )

    ledger = EpisodeLedger(tmp_path / "ledger.json")
    em = EpisodicMonitor(AssetMonitor("ep/1"), ledger)
    assert em.monitor.calibrate_from_lifetime(store, ledger=ledger)

    # healthy traffic feeds recurrence memory
    v = em.process(coupled_frame(800, start + timedelta(days=200), rng))
    assert v.state == V.STATE_HEALTHY

    # a developing fault arrives (and is also stored - life goes on)
    fault_frame = coupled_frame(
        2000, start + timedelta(days=210), rng, fault=4.0
    )
    store.append("ep/1", fault_frame)
    v = em.process(fault_frame)
    assert v.state in (V.STATE_ESCALATING, V.STATE_ALARM)
    assert em.open_episode_start
    assert "vib" in v.attribution[:2]
    assert v.evidence_trail["shape"] == "drift"

    # repair happens; reanchor closes the episode and recalibrates
    assert em.reanchor(store, v)
    assert len(ledger.episodes) == 1
    assert ledger.episodes[0].state == "alarm"

    # post-repair healthy data scores healthy again - the loop is closed
    v = em.process(coupled_frame(800, start + timedelta(days=240), rng))
    assert v.state == V.STATE_HEALTHY


def test_setpoint_change_proposes_change_not_fault(tmp_path):
    """A coordinated step to a new stable operating point -> the verdict
    word is change-not-fault with a re-baseline proposal, not alarm."""
    rng = np.random.default_rng(7)
    start = datetime(2025, 1, 1, tzinfo=UTC)
    store = RawStore(tmp_path / "raw")
    for m in range(6):
        store.append(
            "ep/2",
            coupled_frame(1200, start + timedelta(days=30 * m), rng),
        )
    ledger = EpisodeLedger(tmp_path / "ledger.json")
    em = EpisodicMonitor(AssetMonitor("ep/2"), ledger)
    assert em.monitor.calibrate_from_lifetime(store, ledger=ledger)

    changed = coupled_frame(
        2500, start + timedelta(days=200), rng, setpoint=2.5
    )
    v = em.process(changed)
    assert v.state == V.STATE_CHANGE, v.state
    assert "re-baseline" in v.falsifiable_by


def test_signature_match_recognizes_repeat_fault(tmp_path):
    rng = np.random.default_rng(8)
    start = datetime(2025, 1, 1, tzinfo=UTC)
    store = RawStore(tmp_path / "raw")
    for m in range(6):
        store.append(
            "ep/3",
            coupled_frame(1200, start + timedelta(days=30 * m), rng),
        )
    ledger = EpisodeLedger(tmp_path / "ledger.json")
    em = EpisodicMonitor(AssetMonitor("ep/3"), ledger)
    assert em.monitor.calibrate_from_lifetime(store, ledger=ledger)

    # first occurrence -> episode recorded
    f1 = coupled_frame(2000, start + timedelta(days=200), rng, fault=4.0)
    store.append("ep/3", f1)
    v1 = em.process(f1)
    em.reanchor(store, v1)

    # same fault a year later -> recognized
    f2 = coupled_frame(2000, start + timedelta(days=420), rng, fault=4.0)
    store.append("ep/3", f2)
    v2 = em.process(f2)
    match = v2.evidence_trail.get("signature_match")
    assert match is not None, "repeat fault must be recognized"
    assert match["confidence"] >= 0.34


# ------------------------------------- governed auto-absorption (#89)
def _absorb_runtime(tmp_path, key, rng):
    """6 healthy months in the store, onboarded runtime, history ticked."""
    from acm2.runtime import Runtime

    start = datetime(2025, 1, 1, tzinfo=UTC)
    store = RawStore(tmp_path / "raw")
    for m in range(6):
        store.append(
            key, coupled_frame(1200, start + timedelta(days=30 * m), rng)
        )
    rt = Runtime(store=store, data_root=tmp_path)
    assert rt.onboard(key)
    rt.tick(key)  # consume history; healthy data opens no episode
    assert rt.monitors[key].open_episode_start == ""
    return rt, store, start


def test_change_not_fault_not_absorbed_before_the_period(tmp_path, monkeypatch):
    """The trigger is TIME-gated: with the period raised, a declared
    change stays an open episode (no silent early re-anchor)."""
    from acm2.constants import REGISTRY, Constant

    monkeypatch.setitem(
        REGISTRY,
        "CHANGE_ABSORB_ANCHOR_PERIODS",
        Constant("CHANGE_ABSORB_ANCHOR_PERIODS", 100.0, "test gate"),
    )
    rng = np.random.default_rng(11)
    rt, store, start = _absorb_runtime(tmp_path, "ab/0", rng)
    em = rt.monitors["ab/0"]
    store.append(
        "ab/0",
        coupled_frame(2500, start + timedelta(days=200), rng, setpoint=2.5),
    )
    v = rt.tick("ab/0")
    assert v.state == V.STATE_CHANGE, v.state
    assert em.open_episode_start != "", "episode stays open"
    assert len(rt.ledger.episodes) == 0, "nothing absorbed early"


def test_change_not_fault_auto_absorbs_after_anchor_period(tmp_path):
    """Unattended operation (#89): a coordinated setpoint change that has
    held past one anchor period (17 days of plateau here) is absorbed
    automatically - episode ledgered as change-not-fault, baseline
    recalibrated, the plateau is the new normal, and a later LOCAL fault
    on that plateau still raises evidence (the falsifiability promise)."""
    rng = np.random.default_rng(11)
    rt, store, start = _absorb_runtime(tmp_path, "ab/1", rng)
    em = rt.monitors["ab/1"]

    epoch_before = em.monitor.model_epoch
    store.append(
        "ab/1",
        coupled_frame(2500, start + timedelta(days=200), rng, setpoint=2.5),
    )
    rt.tick("ab/1")
    assert em.open_episode_start == "", "episode must be closed"
    assert len(rt.ledger.episodes) == 1
    assert rt.ledger.episodes[0].state == "change-not-fault"
    assert em.monitor.model_epoch != epoch_before, "recalibrated"

    # the absorbed plateau is the new normal
    store.append(
        "ab/1",
        coupled_frame(800, start + timedelta(days=220), rng, setpoint=2.5),
    )
    v = rt.tick("ab/1")
    assert v.state == V.STATE_HEALTHY, v.state

    # falsifiability promise is real: a LOCAL fault on the new plateau
    # still alarms (absorption did not blind the monitor)
    store.append(
        "ab/1",
        coupled_frame(
            2000,
            start + timedelta(days=230),
            rng,
            setpoint=2.5,
            fault=4.0,
        ),
    )
    v = rt.tick("ab/1")
    assert v.state in (V.STATE_ALARM, V.STATE_ESCALATING, V.STATE_CHANGE)
    assert v.state != V.STATE_HEALTHY


def test_drift_episode_never_auto_absorbs(tmp_path):
    """The guard: accumulating degradation (drift shape -> escalating)
    must NOT move the definition of normal, no matter how long it runs."""
    rng = np.random.default_rng(12)
    rt, store, start = _absorb_runtime(tmp_path, "ab/2", rng)
    em = rt.monitors["ab/2"]

    # 17+ days of developing LOCAL fault - far past the anchor period
    store.append(
        "ab/2",
        coupled_frame(2500, start + timedelta(days=200), rng, fault=4.0),
    )
    v = rt.tick("ab/2")
    assert v.state in (V.STATE_ALARM, V.STATE_ESCALATING), v.state
    assert em.open_episode_start != "", "episode stays open"
    assert len(rt.ledger.episodes) == 0, "nothing absorbed"

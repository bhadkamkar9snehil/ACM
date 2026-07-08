"""S7 spike, in-tree: the world model must beat the ridge conditioner
where nonlinearity exists, with calibrated PIT - the GO criteria from the
board brief, executable evidence instead of a memo."""

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

torch = pytest.importorskip("torch")

from acm.scoring.surprise import ConditionalSurpriseScorer, ks_uniform
from acm.scoring.worldmodel import TorchWorldModel
from acm.store.raw import TIMESTAMP_COL

UTC = timezone.utc
pytestmark = pytest.mark.statistical


def nonlinear_machine(n, seed=0, fault=0.0):
    """vib depends NONLINEARLY on temp and flow (sin coupling x product).
    The FAULT is a distortion of the nonlinear relationship itself (phase
    shift + gain change in the coupling), NOT an additive drift: additive
    faults are visible to any reconstructor, but a relationship change is
    only visible to a model that actually learned the relationship - the
    honest claim separating the world model from the ridge conditioner."""
    rng = np.random.default_rng(seed)
    ts = [
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=10 * i)
        for i in range(n)
    ]
    temp = np.zeros(n)
    flow = np.zeros(n)
    for t in range(1, n):
        temp[t] = 0.9 * temp[t - 1] + 0.3 * rng.normal()
        flow[t] = 0.85 * flow[t - 1] + 0.3 * rng.normal()
    severity = fault * np.linspace(0, 1, n) if fault else np.zeros(n)
    vib = (
        np.sin(1.5 * temp + severity) * (1 + (0.5 - 0.3 * severity) * flow)
        + 0.15 * rng.normal(size=n)
    )
    press = 0.7 * flow + 0.2 * rng.normal(size=n)
    return pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "temp": temp, "vib": vib, "flow": flow, "press": press,
        }
    )


@pytest.fixture(scope="module")
def fitted_pair():
    frame = nonlinear_machine(8000, seed=1)
    fit = frame.head(6000)
    wm = TorchWorldModel().fit(fit)
    ridge = ConditionalSurpriseScorer().fit(fit)
    return wm, ridge, frame


def test_spike_go_pit_calibrated_on_healthy(fitted_pair):
    wm, _ridge, frame = fitted_pair
    pits = wm.pit(frame.slice(6000))
    ks = [ks_uniform(pits[:, j]) for j in range(pits.shape[1])]
    assert max(ks) < 0.15, ks  # calibrated predictive distributions


def test_spike_go_beats_ridge_on_nonlinear_coupling(fitted_pair):
    """GO criterion: separation (fault surprise / healthy surprise) must be
    materially better for the world model on the nonlinear fixture."""
    wm, ridge, frame = fitted_pair
    healthy_tail = frame.slice(6000)
    faulty = nonlinear_machine(2500, seed=2, fault=1.0)  # coupling distortion

    def separation(scorer):
        """Elevation in healthy-spread units: how many MADs of its own
        healthy score distribution the fault lifts the mean - the scale
        the decision layer actually operates on."""
        h = scorer.score(healthy_tail)
        f = scorer.score(faulty)
        med = float(np.median(h))
        mad = 1.4826 * float(np.median(np.abs(h - med))) or 1e-9
        return (float(np.mean(f)) - med) / mad

    sep_wm = separation(wm)
    sep_ridge = separation(ridge)
    assert sep_wm > 1.2 * sep_ridge, (sep_wm, sep_ridge)


def test_world_model_drops_into_the_monitor(fitted_pair):
    """Interface parity: the world model is a drop-in scorer_cls - same
    spine, same banks, same verdicts (D6/D7: the swap is architectural)."""
    from acm.monitor import AssetMonitor

    mon = AssetMonitor("wm/1", scorer_cls=TorchWorldModel)
    assert mon.calibrate(nonlinear_machine(6000, seed=3))
    ok = mon.process(nonlinear_machine(1500, seed=4))
    assert ok.state != "alarm"
    v = mon.process(nonlinear_machine(2500, seed=5, fault=1.5))
    assert v.state == "alarm", v.state
    assert "vib" in v.attribution[:2]
    assert "operating_point_familiarity" in v.coverage


def test_concentration_cross_tier_parity():
    """#92: change-not-fault was structurally unreachable at Tier 2 -
    the world model had no concentration(), so the corroboration
    defaulted to 1.0 (channel-local) for every step episode. Both
    scorers must agree on the DIRECTION: a coordinated move (all
    channels shifted) reads low, a channel-local fault reads high."""
    from datetime import datetime, timedelta, timezone

    UTC2 = timezone.utc
    rng = np.random.default_rng(5)
    n = 3000

    def frame(shift_all=0.0, vib_fault=0.0, start_i=0):
        ts = [
            datetime(2026, 1, 1, tzinfo=UTC2)
            + timedelta(minutes=10 * (start_i + i))
            for i in range(n)
        ]
        temp = rng.normal(size=n) + shift_all
        flow = rng.normal(size=n) + shift_all
        press = rng.normal(size=n) + shift_all
        vib = 0.8 * temp + 0.3 * rng.normal(size=n) + vib_fault
        load = 0.6 * temp + 0.4 * flow + 0.3 * rng.normal(size=n)
        return pl.DataFrame(
            {
                TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
                "temp": temp,
                "vib": vib,
                "press": press,
                "flow": flow,
                "load": load,
            }
        )

    healthy = frame()
    coordinated = frame(shift_all=2.5, start_i=n)
    local = frame(vib_fault=4.0, start_i=2 * n)

    for scorer_cls in (ConditionalSurpriseScorer, TorchWorldModel):
        scorer = scorer_cls().fit(healthy)
        assert hasattr(scorer, "concentration"), scorer_cls.__name__
        c_coord = scorer.concentration(coordinated)
        c_local = scorer.concentration(local)
        assert c_local > c_coord, (
            f"{scorer_cls.__name__}: local fault must read MORE "
            f"concentrated than a coordinated move "
            f"(local={c_local:.3f}, coord={c_coord:.3f})"
        )

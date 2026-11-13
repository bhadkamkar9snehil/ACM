"""The online monitor: what it must do on a small asset it has never seen."""

from __future__ import annotations

import numpy as np

import online
from online import DATA, MACHINE, MEMORY_COPIES, SENSOR, OnlineMonitor

COLS = ("a", "b", "c", "d", "e", "f")
GAIN = np.array([10.0, 6.0, -4.0, 8.0, 3.0, 5.0])


def asset(n: int, seed: int = 0) -> np.ndarray:
    """Six channels driven by one wandering load, each with its own noise."""
    rng = np.random.default_rng(seed)
    load = np.cumsum(rng.normal(0, 0.01, n))
    load = 2 * np.abs((load % 2.0) - 1.0)
    return load[:, None] * GAIN + rng.normal(0, 0.1, (n, 6))


def run(x: np.ndarray, chunk: int = 60):
    m = OnlineMonitor(COLS, 60.0)
    adv = []
    for s in range(0, x.shape[0], chunk):
        adv.extend(m.step(x[s:s + chunk]))
    return m, adv


def test_channel_never_predicts_itself():
    x = asset(4000)
    m, _ = run(x)
    X = x[-500:].copy()
    F, _ = m._features(X, np.repeat(X[:1], MEMORY_COPIES, axis=0))
    X[-100:, 2] += 50.0
    F2, _ = m._features(X, np.repeat(X[:1], MEMORY_COPIES, axis=0))
    assert np.allclose(m._predict(F)[0][:, 2], m._predict(F2)[0][:, 2])
    assert not np.allclose(m._predict(F)[0][:, 0], m._predict(F2)[0][:, 0])


def test_healthy_life_raises_no_fault_advisory():
    _, adv = run(asset(20000, seed=1))
    assert [a for a in adv if a.kind in (MACHINE, SENSOR, DATA)] == []


def test_sensor_offset_is_detected_and_named():
    x = asset(20000, seed=2)
    x[15000:, 3] += 1.0  # ten noise widths on one channel
    _, adv = run(x)
    faults = [a for a in adv if a.kind in (MACHINE, SENSOR)]
    assert len(faults) == 1
    assert faults[0].kind == SENSOR and faults[0].channels == ("d",)
    assert 15000 <= faults[0].row < 17000


def test_coupled_break_is_a_machine_fault():
    x = asset(20000, seed=3)
    x[15000:, [0, 1, 4]] += np.array([1.5, -1.0, 1.0])
    _, adv = run(x)
    faults = [a for a in adv if a.kind in (MACHINE, SENSOR)]
    assert faults and faults[0].kind == MACHINE
    assert 15000 <= faults[0].row < 17000


def test_intake_names_missing_stuck_and_frozen_data():
    x = asset(6000, seed=4)
    x[3000:3100, 1] = np.nan
    x[4000:4100, 4] = x[3999, 4]
    x[5000:5030] = x[4999]
    _, adv = run(x)
    got = {(a.kind, a.channels) for a in adv if a.row >= 3000}
    assert (DATA, ("b",)) in got
    assert (SENSOR, ("e",)) in got
    assert any(k == DATA and len(ch) == 6 for k, ch in got)


def test_young_monitor_cannot_alarm():
    """With n earlier scores the smallest rank probability is 1/(n+1),
    so the first hours of life cannot reach the alarm line whatever the
    data does (maturity is graded by the mathematics, not by a gate)."""
    x = asset(240, seed=5)
    x[120:, 0] += 100.0
    _, adv = run(x)
    assert [a for a in adv if a.kind in (MACHINE, SENSOR)] == []


def test_structural_constants_are_declared_for_sensitivity():
    assert set(online.STRUCTURAL) == {
        "memory_span", "learn_delay_fraction", "learn_delay_cap_days",
        "refresh_growth", "leave_out_periods"}

"""Operating map (prototype): the properties the design depends on.

Synthetic assets with exact ground truth; see evidence.opmap_eval
for the wider evaluation including a real turbine.
"""

import numpy as np

from evidence.opmap_eval import make_batch, make_motor, nmi, replay
from opmap import OperatingMap


def _fit(x):
    m = OperatingMap()
    replay(m, x)
    return m


def test_cycle_phases_are_found_as_separate_states():
    x, truth = make_batch(15000, np.random.default_rng(1))
    m = _fit(x)
    region = m.regions()[m.update(x, learn=False).state]
    assert nmi(truth, region) > 0.8


def test_off_is_separated_from_a_continuous_load_range():
    x, truth = make_motor(20000, np.random.default_rng(2))
    m = _fit(x)
    region = m.regions()[m.update(x, learn=False).state]
    off, on = region[truth == 0], region[(truth == 1)]
    off_home = np.bincount(off[off >= 0]).argmax()
    on_home = np.bincount(on[on >= 0]).argmax()
    assert off_home != on_home
    assert (off == off_home).mean() > 0.9
    assert (on == off_home).mean() < 0.02


def test_sensor_fault_does_not_create_a_new_place():
    x, _ = make_motor(20000, np.random.default_rng(3))
    cut = 12000
    m = _fit(x[:cut])
    base = m.update(x[cut:], learn=False)
    xf = x[cut:].copy()
    j = 1  # motor current: responds at once to load
    xf[:, j] += 8.0 * np.median(np.abs(np.diff(x[:cut, j]))) / 0.6745
    f = m.update(xf, learn=False)
    assert (f.map_distance > 1).mean() <= (base.map_distance > 1).mean() + 0.02
    assert np.median(np.abs(f.residual[:, j])) > 2 * np.median(
        np.abs(base.residual[:, j])
    )


def test_unseen_operating_level_is_reported_off_map():
    x, _ = make_motor(20000, np.random.default_rng(4))
    m = _fit(x)
    span = x.max(axis=0) - x.min(axis=0)
    lead = np.abs(m.W[0]) > 0.5 * np.abs(m.W[0]).max()
    top = np.argsort(-m._project(x)[0][:, 0])[:300]
    xn = x[top] + 0.35 * span * np.sign(m.W[0]) * lead
    assert (m.update(xn, learn=False).map_distance > 1).mean() > 0.9


def test_missing_values_do_not_break_the_map():
    x, _ = make_motor(8000, np.random.default_rng(5))
    x[np.random.default_rng(6).random(x.shape) < 0.02] = np.nan
    x[3000:3400, 2] = np.nan
    m = _fit(x)
    r = m.update(x, learn=False)
    assert np.isfinite(r.map_distance).all()

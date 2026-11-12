"""Evaluate the operating map on assets of different types.

Run: uv run python -m evidence.opmap_eval [care_csv ...]

Synthetic assets carry exact ground-truth operating states. A CARE
turbine file carries the operator's own status codes, which the map
never sees. For each asset the script reports:
- how well discovered regions match the true states (NMI, 1 = perfect);
- whether conditioning on the map tightens the healthy residual
  compared with one global model (ratio < 1 = tighter);
- whether a sensor fault stays on the map (it must not create a state);
- whether a never-seen operating level is reported as a new place.
"""

from __future__ import annotations

import sys

import numpy as np

from opmap import OperatingMap


def nmi(a: np.ndarray, b: np.ndarray) -> float:
    ua, ia = np.unique(a, return_inverse=True)
    ub, ib = np.unique(b, return_inverse=True)
    c = np.zeros((ua.size, ub.size))
    np.add.at(c, (ia, ib), 1.0)
    p = c / c.sum()
    pa, pb = p.sum(1, keepdims=True), p.sum(0, keepdims=True)
    nz = p > 0
    mi = float((p[nz] * np.log(p[nz] / (pa @ pb)[nz])).sum())
    ha = -float((pa[pa > 0] * np.log(pa[pa > 0])).sum())
    hb = -float((pb[pb > 0] * np.log(pb[pb > 0])).sum())
    return mi / max(np.sqrt(ha * hb), 1e-12)


def _lag(x: np.ndarray, tau: float) -> np.ndarray:
    out = np.empty_like(x, dtype=np.float64)
    acc = float(x[0])
    a = 1.0 / tau
    for i, v in enumerate(x):
        acc += a * (v - acc)
        out[i] = acc
    return out


def make_pump(n: int, rng):
    """Fixed-speed levels: off / low / high, with ramps between."""
    level = np.zeros(n)
    i = 0
    while i < n:
        dur = int(rng.integers(300, 3000))
        level[i:i + dur] = rng.choice([0.0, 0.6, 1.0], p=[0.25, 0.35, 0.4])
        i += dur
    speed = _lag(level, 30.0)
    truth = np.where(
        np.abs(speed - level) > 0.03, 3,
        np.select([level == 0.0, level == 0.6], [0, 1], 2),
    )
    amb = 20 + 8 * np.sin(np.arange(n) * 2 * np.pi / 1440)
    power = 90 * speed**3
    cols = [
        2950 * speed + rng.normal(0, 3, n),
        120 * speed + rng.normal(0, 0.8, n),
        9 * speed**2 + rng.normal(0, 0.05, n),
        power + rng.normal(0, 0.6, n),
        4 * (speed > 0.02) + 160 * speed**3 + rng.normal(0, 0.5, n),
        amb + _lag(0.35 * power, 120.0) + rng.normal(0, 0.2, n),
        amb + _lag(0.6 * power, 240.0) + rng.normal(0, 0.3, n),
        0.2 + 2.5 * speed + rng.normal(0, 1.0, n) * (0.05 + 0.25 * speed),
        amb + rng.normal(0, 0.2, n),
    ]
    return np.column_stack(cols), truth


def make_motor(n: int, rng):
    """Continuously varying load: one state that is a range, plus off."""
    walk = np.cumsum(rng.normal(0, 0.004, n))
    load = 0.2 + 0.8 * np.abs(((walk % 2.0) - 1.0))
    on = np.ones(n)
    i = 0
    while i < n:
        i += int(rng.integers(4000, 9000))
        on[i:i + int(rng.integers(300, 900))] = 0.0
    load = _lag(load * on, 20.0)
    truth = np.where(load < 0.05, 0, 1)
    amb = 25 + 6 * np.sin(np.arange(n) * 2 * np.pi / 1440)
    run = (load > 0.02).astype(np.float64)
    cols = [
        400 * load + rng.normal(0, 3, n),
        5 * run + 80 * load + rng.normal(0, 0.6, n),
        75 * load + rng.normal(0, 0.5, n),
        1480 * run - 30 * load + rng.normal(0, 1.5, n),
        amb + _lag(55 * load**2, 200.0) + rng.normal(0, 0.3, n),
        amb + _lag(20 * load, 150.0) + rng.normal(0, 0.2, n),
        amb + _lag(17 * load, 150.0) + rng.normal(0, 0.2, n),
        0.5 + 1.2 * load + rng.normal(0, 0.08, n),
        amb + rng.normal(0, 0.2, n),
    ]
    return np.column_stack(cols), truth


def make_batch(n: int, rng):
    """A repeating cycle: idle / heat / hold / discharge."""
    phase = np.zeros(n, dtype=np.int64)
    i = 0
    while i < n:
        for ph, lo, hi in (
            (0, 60, 200), (1, 200, 300), (2, 300, 500), (3, 40, 80)
        ):
            dur = int(rng.integers(lo, hi))
            phase[i:i + dur] = ph
            i += dur
    heat = np.select([phase == 1, phase == 2], [1.0, 0.35], 0.0)
    target = np.where((phase == 1) | (phase == 2), 1600.0, 0.0)
    temp = 30 + _lag(target, 80.0)
    cols = [
        60 * heat + rng.normal(0, 0.6, n),
        45 * heat + rng.normal(0, 0.5, n),
        temp + rng.normal(0, 4, n),
        80 + 0.5 * _lag(temp, 20.0) + rng.normal(0, 3, n),
        2 + 12 * heat + rng.normal(0, 0.3, n),
        20.0 * (phase == 1) + rng.normal(0, 0.4, n),
        35.0 * (phase == 3) + rng.normal(0, 0.3, n),
    ]
    return np.column_stack(cols), phase


def load_care(path: str):
    import polars as pl

    d = pl.read_csv(path, separator=";", infer_schema_length=5000)
    meta = {"time_stamp", "asset_id", "id", "train_test", "status_type_id"}
    cols = [c for c, t in d.schema.items() if c not in meta and t.is_numeric()]
    return (
        d.select(cols).to_numpy().astype(np.float64),
        d.get_column("status_type_id").to_numpy(),
    )


def replay(model: OperatingMap, x: np.ndarray, chunk: int = 500) -> None:
    for s in range(0, x.shape[0], chunk):
        model.update(x[s:s + chunk])


def run(name: str, x: np.ndarray, truth: np.ndarray):
    n = x.shape[0]
    cut = int(n * 0.6)

    omap = OperatingMap()
    replay(omap, x)
    reg = omap.regions()
    final = omap.update(x, learn=False)
    region = reg[final.state]

    # tightness: learn on the first 60%, score the rest in raw units,
    # against a single global model (max_states=1)
    def holdout_spread(max_states: int) -> np.ndarray:
        m = OperatingMap(max_states=max_states)
        replay(m, x[:cut])
        r = m.update(x[cut:], learn=False)
        scales = np.stack([m._scale(j) for j in range(m.p_n.size)])
        raw = r.residual * scales[r.state] * m.std
        return np.nanmean(np.abs(raw), axis=0)

    local, glob = holdout_spread(128), holdout_spread(1)
    tight = float(np.nanmedian(local / np.maximum(glob, 1e-12)))

    m2 = OperatingMap()
    replay(m2, x[:cut])
    base = m2.update(x[cut:], learn=False)
    # sensor fault: offset one channel by 8 of its own noise widths
    j = x.shape[1] // 2
    width = np.nanmedian(np.abs(np.diff(x[:cut, j]))) / 0.6745
    xf = x[cut:].copy()
    xf[:, j] += 8.0 * max(width, 1e-9)
    f = m2.update(xf, learn=False)
    # new operating level: push the channels that carry the lead
    # operating direction 35% of their range beyond anything seen
    hi = np.nanpercentile(x[:cut], 99.9, axis=0)
    lo = np.nanpercentile(x[:cut], 0.1, axis=0)
    w0 = m2.W[0]
    lead = np.abs(w0) > 0.5 * np.abs(w0).max()
    z0 = np.nan_to_num(m2._project(x[cut:])[0][:, 0])
    top = np.argsort(-z0)[:500]
    xn = x[cut:][top] + 0.35 * (hi - lo) * np.sign(w0) * lead
    nw = m2.update(xn, learn=False)

    def med(a):
        return round(float(np.nanmedian(np.abs(a))), 2)

    out = {
        "rows": n, "channels": x.shape[1],
        "operating_dims": int(omap.W.shape[0]),
        "prototypes": int(omap.p_n.size),
        "regions_found": int(reg.max() + 1),
        "true_states": int(np.unique(truth).size),
        "nmi_vs_truth": round(nmi(truth, region), 3),
        "passing_share": round(float((region == -1).mean()), 3),
        "spread_vs_global": round(tight, 3),
        "healthy_offmap": round(float((base.map_distance > 1).mean()), 3),
        "sensorfault_offmap": round(float((f.map_distance > 1).mean()), 3),
        "sensorfault_resid": f"{med(base.residual[:, j])} -> {med(f.residual[:, j])}",
        "newlevel_offmap": round(float((nw.map_distance > 1).mean()), 3),
    }
    return out, region


def main(argv: list[str]) -> None:
    rng = np.random.default_rng(7)
    n = 60000
    assets = [
        ("pump (3 fixed levels + ramps)", *make_pump(n, rng)),
        ("motor (continuous load + off)", *make_motor(n, rng)),
        ("batch furnace (4-phase cycle)", *make_batch(n, rng)),
    ]
    for p in argv:
        assets.append((f"turbine {p[-12:]}", *load_care(p)))
    for name, x, t in assets:
        res, region = run(name, x, t)
        print("\n== " + name)
        for k, v in res.items():
            print(f"  {k:20s} {v}")
        print("  rows per (region, true state); region -1 = passing through")
        states = np.unique(t)
        print("      true:", [int(s) for s in states])
        for r in np.unique(region):
            counts = [int(((region == r) & (t == s)).sum()) for s in states]
            print(f"    {int(r):4d}: {counts}")


if __name__ == "__main__":
    main(sys.argv[1:])

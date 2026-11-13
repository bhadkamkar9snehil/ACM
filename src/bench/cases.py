"""Benchmark cases: raw-rate synthetic assets with exact ground truth.

Every case is one asset's life from its first sample. A case is either
healthy for its whole length or carries exactly one event, so a result
never depends on how two events interact.

Asset types are split in two groups and the split is the point:
- DEV types may be looked at while a method is being built;
- JUDGE types are run only at a gate, and a claim that a method works
  is made only from them (rules of evidence, goals document section 10).
The two groups also use disjoint seed ranges.

A generator is told nothing a real deployment would not provide. It
returns numeric channels on a fixed cadence. Three drivers exist so the
harness can place events:
- wear (n,) in [0, 1]: a physical degradation that changes several
  coupled channels through the asset's own physics (a machine fault);
- novel (n,) bool: the asset is operated at a level it has never been
  at before (a legitimate new operating state, not a fault);
- sensor and data faults are applied afterwards to the produced
  readings, because they are faults of the measurement, not the asset.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

CADENCE_S = 60.0
DAY = int(86400 / CADENCE_S)
HOUR = int(3600 / CADENCE_S)

# Event kinds the harness scores against.
MACHINE, SENSOR, DATA, NEW_STATE = "machine", "sensor", "data", "new_state"

# Ages at onset, one per cold-start stage of the design (section 5).
ONSET_AGES = {"hours": 6 * HOUR, "days": 3 * DAY, "weeks": 14 * DAY,
              "months": 45 * DAY}
POST_ROWS = 5 * DAY  # life observed after onset
HEALTHY_ROWS = 60 * DAY

DEV_SEEDS = (0, 1)
JUDGE_SEEDS = (1000, 1001)


@dataclass
class Event:
    kind: str
    shape: str
    start: int
    end: int  # exclusive; the fault is present on [start, end)
    channels: tuple[str, ...]


@dataclass
class Case:
    name: str
    asset_type: str
    split: str  # "dev" or "judge"
    seed: int
    columns: tuple[str, ...]
    x: np.ndarray  # (n, d), NaN = missing
    event: Event | None = None
    stage: str = ""
    noise_sd: np.ndarray = field(default_factory=lambda: np.zeros(0))

    @property
    def n(self) -> int:
        return self.x.shape[0]

    def timestamps(self) -> np.ndarray:
        t0 = np.datetime64("2026-01-01T00:00:00", "us")
        step = np.timedelta64(int(CADENCE_S * 1e6), "us")
        return t0 + np.arange(self.n) * step


def _lag(x: np.ndarray, tau: float) -> np.ndarray:
    out = np.empty(x.size)
    acc = float(x[0])
    a = 1.0 / tau
    for i in range(x.size):
        acc += a * (x[i] - acc)
        out[i] = acc
    return out


def _ambient(n: int, rng, base: float) -> np.ndarray:
    t = np.arange(n)
    return (base + 6 * np.sin(2 * np.pi * t / DAY + rng.uniform(0, 6.28))
            + 4 * np.sin(2 * np.pi * t / (120 * DAY))
            + _lag(rng.normal(0, 6, n), 6 * HOUR))


def _levels(n: int, rng, choices, probs, lo: int, hi: int) -> np.ndarray:
    out = np.zeros(n)
    i = 0
    while i < n:
        dur = int(rng.integers(lo, hi))
        out[i:i + dur] = rng.choice(choices, p=probs)
        i += dur
    return out


def _assemble(rng, n, spec):
    """spec: list of (name, clean signal, noise sd)."""
    names = tuple(s[0] for s in spec)
    sd = np.array([s[2] for s in spec], dtype=np.float64)
    x = np.column_stack([s[1] + rng.normal(0, s[2], n) for s in spec])
    return names, x, sd


# ------------------------------------------------------------ dev types
def pump(n, rng, wear, novel):
    """Fixed-speed levels (off / low / high) with ramps between."""
    level = _levels(n, rng, [0.0, 0.6, 1.0], [0.2, 0.4, 0.4], 300, 3000)
    level = np.where(novel, 0.8, level)
    speed = _lag(level, 30.0)
    amb = _ambient(n, rng, 20.0)
    power = 90 * speed**3 * (1 + 0.5 * wear)
    return _assemble(rng, n, [
        ("speed", 2950 * speed, 3.0),
        ("flow", 120 * speed * (1 - 0.4 * wear), 0.8),
        ("head", 9 * speed**2 * (1 - 0.3 * wear), 0.05),
        ("power", power, 0.6),
        ("current", 4 * (speed > 0.02) + 160 * speed**3 * (1 + 0.5 * wear), 0.5),
        ("brg_temp_de", amb + _lag(0.35 * power, 120.0), 0.2),
        ("brg_temp_nde", amb + _lag(0.6 * power, 240.0), 0.3),
        ("vibration", (0.2 + 2.5 * speed) * (1 + 3 * wear), 0.08),
        ("ambient", amb, 0.2),
    ])


def motor(n, rng, wear, novel):
    """Continuously varying load, with stops."""
    walk = np.cumsum(rng.normal(0, 0.004, n))
    load = 0.2 + 0.6 * np.abs((walk % 2.0) - 1.0)
    on = np.ones(n)
    i = 0
    while i < n:
        i += int(rng.integers(4000, 9000))
        on[i:i + int(rng.integers(300, 900))] = 0.0
    load = _lag(np.where(novel, 1.0, load * on), 20.0)
    amb = _ambient(n, rng, 25.0)
    run = (load > 0.02).astype(np.float64)
    return _assemble(rng, n, [
        ("torque", 400 * load, 3.0),
        ("current", 5 * run + 80 * load * (1 + 0.3 * wear), 0.6),
        ("power", 75 * load * (1 + 0.3 * wear), 0.5),
        ("speed", 1480 * run - 30 * load, 1.5),
        ("winding_temp", amb + _lag(55 * load**2 * (1 + 2 * wear), 200.0), 0.3),
        ("brg_temp_de", amb + _lag(20 * load * (1 + wear), 150.0), 0.2),
        ("brg_temp_nde", amb + _lag(17 * load * (1 + wear), 150.0), 0.2),
        ("vibration", (0.5 + 1.2 * load) * (1 + 2 * wear), 0.08),
        ("ambient", amb, 0.2),
    ])


def batch(n, rng, wear, novel):
    """A repeating cycle: idle / heat / hold / discharge."""
    phase = np.zeros(n, dtype=np.int64)
    i = 0
    while i < n:
        for ph, lo, hi in ((0, 60, 200), (1, 200, 300), (2, 300, 500),
                           (3, 40, 80)):
            dur = int(rng.integers(lo, hi))
            phase[i:i + dur] = ph
            i += dur
    heat = np.select([phase == 1, phase == 2], [1.0, 0.35], 0.0)
    heat = np.where(novel & (phase == 2), 0.6, heat)
    target = np.where((phase == 1) | (phase == 2), 1600.0, 0.0)
    target = np.where(novel & (target > 0), 1900.0, target)
    temp = 30 + _lag(target * (1 - 0.25 * wear), 80.0)
    return _assemble(rng, n, [
        ("heater_a_kw", 60 * heat * (1 + 0.3 * wear), 0.6),
        ("heater_b_kw", 45 * heat * (1 + 0.3 * wear), 0.5),
        ("core_temp", temp, 4.0),
        ("shell_temp", 80 + 0.5 * _lag(temp, 20.0) * (1 + 0.4 * wear), 3.0),
        ("gas_flow", 2 + 12 * heat, 0.3),
        ("charge_feed", 20.0 * (phase == 1), 0.4),
        ("discharge_rate", 35.0 * (phase == 3), 0.3),
    ])


# ---------------------------------------------------------- judge types
def compressor(n, rng, wear, novel):
    """Load/unload compressor: a two-position unloader, three phase
    currents, pressures and lagging temperatures."""
    demand = np.clip(0.55 + _lag(rng.normal(0, 2.5, n), 400.0), 0.1, 0.9)
    demand = np.where(novel, 1.25, demand)
    loaded = np.zeros(n)
    p = np.zeros(n)
    pr, ld = 7.0, 1.0
    for i in range(n):  # pressure band control
        pr += 0.02 * (ld * 1.4 - demand[i])
        if pr > 8.0:
            ld = 0.0
        elif pr < 6.5:
            ld = 1.0
        loaded[i], p[i] = ld, pr
    amb = _ambient(n, rng, 22.0)
    amps = 18 + 62 * loaded * (1 + 0.25 * wear) + 2.0 * (p - 7)
    t_dis = amb + _lag(60 * loaded * (1 + 0.8 * wear) + 8, 25.0)
    return _assemble(rng, n, [
        ("unloader", loaded, 0.0),
        ("discharge_bar", p, 0.03),
        ("suction_bar", 1.0 - 0.05 * loaded, 0.004),
        ("amps_l1", amps, 0.5),
        ("amps_l2", amps * 1.01, 0.5),
        ("amps_l3", amps * 0.99, 0.5),
        ("discharge_temp", t_dis, 0.4),
        ("oil_temp", amb + _lag(0.5 * (t_dis - amb), 180.0) + 15, 0.3),
        ("oil_bar", 3.0 + 0.4 * loaded - 0.01 * (amb - 22), 0.02),
        ("vibration", (1.0 + 1.5 * loaded) * (1 + 2.5 * wear), 0.06),
        ("ambient", amb, 0.2),
    ])


def exchanger(n, rng, wear, novel):
    """Shell-and-tube heat exchanger; wear is fouling."""
    f_hot = _levels(n, rng, [40.0, 60.0, 80.0], [0.3, 0.4, 0.3], 600, 5000)
    f_hot = _lag(np.where(novel, 110.0, f_hot), 15.0)
    f_cold = 70 + _lag(rng.normal(0, 60, n), 300.0)
    t_hot_in = 140 + _lag(rng.normal(0, 80, n), 900.0)
    t_cold_in = _ambient(n, rng, 18.0)
    eff = 0.75 * (1 - 0.5 * wear) * f_cold / (f_cold + 0.6 * f_hot)
    duty = eff * (t_hot_in - t_cold_in)
    t_hot_out = _lag(t_hot_in - duty, 40.0)
    t_cold_out = _lag(t_cold_in + duty * f_hot / np.maximum(f_cold, 1.0), 40.0)
    return _assemble(rng, n, [
        ("flow_hot", f_hot, 0.5),
        ("flow_cold", f_cold, 0.5),
        ("t_hot_in", t_hot_in, 0.3),
        ("t_hot_out", t_hot_out, 0.3),
        ("t_cold_in", t_cold_in, 0.2),
        ("t_cold_out_a", t_cold_out, 0.2),
        ("t_cold_out_b", t_cold_out, 0.2),
        ("dp_hot", 0.00012 * f_hot**2 * (1 + 1.5 * wear), 0.01),
        ("dp_cold", 0.0001 * f_cold**2 * (1 + 0.8 * wear), 0.01),
    ])


GENERATORS = {
    "pump": (pump, "dev"), "motor": (motor, "dev"), "batch": (batch, "dev"),
    "compressor": (compressor, "judge"), "exchanger": (exchanger, "judge"),
}

# (kind, shape). Magnitudes are in units of the channel's own noise sd
# or of the wear driver, fixed here and never varied per asset type.
SCENARIOS = (
    (MACHINE, "step"), (MACHINE, "ramp"),
    (SENSOR, "offset"), (SENSOR, "drift"), (SENSOR, "stuck"),
    (DATA, "nan_block"), (DATA, "spikes"), (DATA, "freeze_all"),
    (NEW_STATE, "level"),
)
SENSOR_OFFSET_SD = 8.0
WEAR_STEP = 0.2
WEAR_RAMP_END = 0.4
SPIKE_SD = 30.0


def _pick_channel(names, x, rng) -> int:
    """A channel that varies (not a constant or a two-level switch)."""
    ok = [j for j in range(x.shape[1])
          if np.unique(np.round(x[:2000, j], 6)).size > 50]
    return int(rng.choice(ok))


def make_case(asset_type: str, seed: int, kind: str | None = None,
              shape: str = "", stage: str = "",
              healthy_rows: int = HEALTHY_ROWS) -> Case:
    gen, split = GENERATORS[asset_type]
    rng = np.random.default_rng([seed, sum(map(ord, asset_type))])
    if kind is None:
        n, start = healthy_rows, None
    else:
        start = ONSET_AGES[stage]
        n = start + POST_ROWS
    wear = np.zeros(n)
    novel = np.zeros(n, dtype=bool)
    if kind == MACHINE:
        if shape == "step":
            wear[start:] = WEAR_STEP
        else:
            wear[start:] = np.linspace(0, WEAR_RAMP_END, n - start)
    if kind == NEW_STATE:
        novel[start:start + DAY] = True
    names, x, sd = gen(n, rng, wear, novel)
    name = f"{asset_type}/s{seed}/" + (f"{kind}-{shape}@{stage}" if kind else "healthy")
    case = Case(name, asset_type, split, seed, names, x, None, stage, sd)
    if kind is None:
        return case
    frng = np.random.default_rng([seed, 7, start])
    end, chans = n, names
    if kind == SENSOR:
        j = _pick_channel(names, x, frng)
        chans = (names[j],)
        scale = max(sd[j], 1e-9)
        if shape == "offset":
            x[start:, j] += SENSOR_OFFSET_SD * scale
        elif shape == "drift":
            x[start:, j] += np.linspace(0, 2 * SENSOR_OFFSET_SD * scale, n - start)
        else:
            x[start:, j] = x[start - 1, j]
    elif kind == DATA:
        if shape == "nan_block":
            j = _pick_channel(names, x, frng)
            chans, end = (names[j],), start + 2 * HOUR
            x[start:end, j] = np.nan
        elif shape == "spikes":
            j = _pick_channel(names, x, frng)
            chans, end = (names[j],), start + DAY
            at = start + frng.choice(DAY, size=10, replace=False)
            x[at, j] += SPIKE_SD * max(sd[j], 1e-9) * frng.choice([-1, 1], 10)
        else:
            end = start + HOUR // 2
            x[start:end] = x[start - 1]
    elif kind == NEW_STATE:
        end = start + DAY
    elif kind == MACHINE:
        chans = ()
    case.event = Event(kind, shape, start, end, tuple(chans))
    return case


def suite(split: str, stages=tuple(ONSET_AGES), seeds=None,
          healthy_rows: int = HEALTHY_ROWS, types=None):
    """Yield every case of a split: one healthy life per (type, seed),
    then each scenario at each onset age."""
    if seeds is None:
        seeds = DEV_SEEDS if split == "dev" else JUDGE_SEEDS
    for t, (_, s) in GENERATORS.items():
        if s != split or (types and t not in types):
            continue
        for seed in seeds:
            yield make_case(t, seed, healthy_rows=healthy_rows)
            for kind, shape in SCENARIOS:
                for stage in stages:
                    yield make_case(t, seed, kind, shape, stage)

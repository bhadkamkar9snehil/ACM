"""Methods the harness can replay a case through.

A method sees what a deployment sees: channel names, then rows in time
order from the first sample. It returns the advisories it opens. It is
never told the asset type, the timing of faults or the truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

from bench.cases import CADENCE_S, NEW_STATE
from constants import ALPHA_PER_ASSET_YEAR

ROWS_PER_YEAR = 365.25 * 86400 / CADENCE_S


@dataclass
class Advisory:
    row: int  # index of the row at which the advisory was raised
    kind: str | None  # one of the case kinds, or None = not classified
    channels: tuple[str, ...] = ()


class Method:
    name = "method"
    chunk_rows = 60  # rows handed over per step (one hour at 1 minute)
    constants: dict[str, float] = {}

    def start(self, columns: tuple[str, ...], workdir) -> None:
        raise NotImplementedError

    def step(self, row0: int, ts: np.ndarray, x: np.ndarray) -> list[Advisory]:
        raise NotImplementedError

    def close(self) -> None:
        pass


class RunningZ(Method):
    """The plain baseline: each channel against its own running mean and
    spread. The threshold is the Gaussian tail that spends the yearly
    budget evenly over rows and channels. Nothing else is modelled."""

    name = "running-z"
    constants = {"quiet_rows_to_close": 1440.0}

    def __init__(self, **overrides: float) -> None:
        self.constants = {**type(self).constants, **overrides}

    def start(self, columns, workdir) -> None:
        d = len(columns)
        self.columns = columns
        self.n = np.zeros(d)
        self.s1 = np.zeros(d)
        self.s2 = np.zeros(d)
        p = ALPHA_PER_ASSET_YEAR / (ROWS_PER_YEAR * d)
        self.thr = NormalDist().inv_cdf(1 - p / 2)
        self.open = False
        self.quiet = 0

    def step(self, row0, ts, x):
        out: list[Advisory] = []
        ok = np.isfinite(x)
        ready = self.n > 30
        mean = self.s1 / np.maximum(self.n, 1)
        var = self.s2 / np.maximum(self.n, 1) - mean**2
        sd = np.sqrt(np.clip(var, 0, None))
        live = ok & ready & (sd > 0)
        z = np.where(live, np.abs(np.where(ok, x, 0.0) - mean)
                     / np.where(sd > 0, sd, 1.0), 0.0)
        hit = z > self.thr
        rows = np.where(hit.any(axis=1))[0]
        if rows.size and not self.open:
            r = int(rows[0])
            ch = tuple(self.columns[j] for j in np.where(hit[r])[0])
            out.append(Advisory(row0 + r, None, ch))
            self.open = True
        if rows.size:
            self.quiet = x.shape[0] - 1 - int(rows[-1])
        else:
            self.quiet += x.shape[0]
        if self.open and self.quiet >= self.constants["quiet_rows_to_close"]:
            self.open = False
        if not self.open:
            xf = np.where(ok, x, 0.0)
            self.n += ok.sum(axis=0)
            self.s1 += xf.sum(axis=0)
            self.s2 += (xf**2).sum(axis=0)
        return out


class CurrentBuild(Method):
    """The build in src/ today, through its production runtime path, on
    the Tier-0 scorer. It runs here as the reference to beat."""

    name = "current-tier0"

    def start(self, columns, workdir) -> None:
        from runtime import Runtime
        from scoring.surprise import ConditionalSurpriseScorer
        from store.raw import RawStore

        self.columns = columns
        self.key = "bench/asset"
        self.store = RawStore(workdir / "raw")
        self.rt = Runtime(store=self.store, data_root=workdir,
                          scorer_cls_override=ConditionalSurpriseScorer)
        self.onboarded = False
        self.prev = ""

    def step(self, row0, ts, x):
        import polars as pl

        import verdict as V
        from store.raw import TIMESTAMP_COL

        frame = pl.DataFrame(
            {TIMESTAMP_COL: pl.Series(ts).dt.replace_time_zone("UTC"),
             **{c: x[:, j] for j, c in enumerate(self.columns)}}
        ).fill_nan(None)
        self.store.append(self.key, frame)
        if not self.onboarded:
            self.rt.onboard(self.key)
            self.onboarded = True
        v = self.rt.tick(self.key)
        if v is None:
            return []
        out = []
        alarming = (V.STATE_ALARM, V.STATE_ESCALATING)
        last = row0 + x.shape[0] - 1
        if v.state in alarming and self.prev not in alarming:
            out.append(Advisory(last, None, tuple(v.attribution)))
        if v.state == V.STATE_CHANGE and self.prev != V.STATE_CHANGE:
            out.append(Advisory(last, NEW_STATE, tuple(v.attribution)))
        self.prev = v.state
        return out

    def close(self) -> None:
        closer = getattr(self.rt.state, "close", None)
        if closer:
            closer()


class Online(Method):
    """The online monitor of src/online.py (the design being built)."""

    name = "online"
    from online import STRUCTURAL as constants

    def __init__(self, **overrides: float) -> None:
        self.overrides = overrides

    def start(self, columns, workdir) -> None:
        from online import OnlineMonitor

        self.m = OnlineMonitor(columns, CADENCE_S, **self.overrides)

    def step(self, row0, ts, x):
        return [Advisory(a.row, a.kind, a.channels) for a in self.m.step(x)]


METHODS = {m.name: m for m in (RunningZ, CurrentBuild, Online)}

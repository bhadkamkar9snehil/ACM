"""Online monitor: learns one asset from its first sample (design parts 1-7).

One object per asset. It is given channel names and then rows in time
order. It keeps running sums only, so cost per row does not grow with
the asset's age, and it needs no history, no calibration pass and no
configuration.

Pipeline for each chunk of rows:

1. Intake. A value is invalid when it is missing, or when the channel
   has repeated one value for longer than it ever has and longer than
   its own repeat rate makes plausible. Invalid values are replaced by
   what the other channels imply and are never evidence about the
   machine.
2. Expectation. Every channel is predicted from the OTHER channels and
   from smoothed copies of them (memory coordinates), by ridge
   regression solved from one running second-moment matrix. A channel
   never helps predict itself, so a fault on it cannot hide in its own
   expectation. The predictive spread widens where the asset has
   little experience.
3. Familiarity. Distance, in the directions several channels move
   along together, to the nearest state the asset has been in. Evidence
   counts for less the less familiar the state is.
4. Evidence. Residuals are averaged over blocks of 1, 2, 4, ... rows.
   Each block is compared with reference blocks from similar operating
   states: their habitual residual is subtracted and the block is
   ranked against their spread. The reference is clean past life,
   scored by a model as far behind it as the live model is behind the
   present, so no calibration pass exists and a young monitor is judged
   as a young monitor. Ranks feed a detector that restarts itself.
   Evidence at a scale is discounted by how long disturbances of that
   residual last, measured across scales.
5. Episodes. An alarm is classified by what explains it: missing or
   frozen values (data), a state never visited or a life too short to
   judge a run of that length (new state), one channel whose
   replacement by its expectation clears everything (sensor),
   otherwise the machine.
6. Learning. Rows are learned at once. When a fault episode opens,
   every row from its onset is taken back out of the running sums,
   exactly. An episode that stops growing is accepted and learned; one
   that keeps growing is not, within a limit set by the asset's age.

Not built: detection of isolated single-row spikes (a rank cannot
certify a handful of them), timestamp checks, persistence across
restarts, and the wiring into runtime.py.

Numbers: the false-advisory budget comes from constants.py. The
structural constants below each carry a reason and are exposed for the
halve-and-double test.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from constants import ALPHA_PER_ASSET_YEAR

MACHINE, SENSOR, DATA, NEW_STATE = "machine", "sensor", "data", "new_state"

STRUCTURAL = {
    # Smoothing spans (rows) of the memory coordinates. Three spans a
    # factor of eight apart let a linear model reproduce any lag
    # between a few rows and a few thousand.
    "memory_span": 8.0,
    # Patience, as a fraction of the asset's age: how long an episode
    # must be quiet before it closes, and how long it may stay open
    # without growing before it is accepted as the new normal.
    "learn_delay_fraction": 0.25,
    # ... capped at this many days (the longest routine operating
    # cycle most plants have is a week). Learned rows are also kept
    # this long so they can be un-learned when an episode opens.
    "learn_delay_cap_days": 7.0,
    # The model is re-solved when the learned data grew by this
    # factor. Between two solves it does not move, so this is also
    # how far behind the present the model can be, and the reference
    # is scored with the same lag.
    "refresh_growth": 1.1,
    # Life is cut into this many (up to twice this many) consecutive
    # periods. A reference row is scored by a model built only from
    # the periods before its own, as a live row's score is.
    "leave_out_periods": 8.0,
}
MEMORY_COPIES = 3
MAX_LEVEL = 12  # resource limit: longest evidence block is 4096 rows
REFERENCE_CAP = 512  # resource limit: reference scores kept per cell
STATE_CAP = 512  # resource limit: remembered operating states
MAX_OPERATING_DIMS = 6  # resource limit on the familiarity search
MAX_SUSPECTS = 16  # resource limit: channels tried as the suspect sensor


@dataclass
class Advisory:
    row: int
    kind: str
    channels: tuple[str, ...]
    onset_row: int
    scale_rows: int = 0


def _bet(p: np.ndarray) -> np.ndarray:
    """Evidence from a rank probability. Integrates to one over (0, 1),
    so under healthy behaviour it does not grow on average."""
    p = np.clip(p, 1e-12, 1 - 1e-12)
    lp = np.log(p)
    return (1 - p + p * lp) / (p * lp * lp)


class _Reservoir:
    """Uniform sample of everything offered, for ranking and recall."""

    def __init__(self, cap: int, width: int, rng) -> None:
        self.data = np.full((cap, width), np.nan)
        self.seen = 0
        self.rng = rng

    @property
    def size(self) -> int:
        return min(self.seen, self.data.shape[0])

    def add(self, rows: np.ndarray) -> list[int]:
        """Returns the slot each row landed in (-1 = not kept)."""
        cap = self.data.shape[0]
        slots = []
        for r in rows:
            j = self.seen if self.seen < cap else int(self.rng.integers(self.seen + 1))
            if j < cap:
                self.data[j] = r
            slots.append(j if j < cap else -1)
            self.seen += 1
        return slots

    def view(self) -> np.ndarray:
        return self.data[: self.size]


class OnlineMonitor:
    def __init__(self, columns, cadence_s: float = 60.0, seed: int = 0,
                 **overrides: float) -> None:
        self.c = {**STRUCTURAL, **overrides}
        self.columns = tuple(columns)
        d = self.d = len(self.columns)
        self.D = d + 1  # residual channels plus the familiarity score
        self.rng = np.random.default_rng(seed)
        self.rows_per_year = 365.25 * 86400 / cadence_s
        self.rows_per_day = 86400 / cadence_s
        self.taus = [self.c["memory_span"] * 8.0**i for i in range(MEMORY_COPIES)]
        self.p = d * (1 + MEMORY_COPIES)
        self.T = 0  # rows seen
        # intake
        self.last_val = np.full(d, np.nan)
        self.hold = np.zeros(d)
        self.run = np.zeros((2, d))  # current run: [repeat, missing]
        self.run_max = np.zeros((2, d))
        self.run_hits = np.zeros((2, d))
        self.n_valid = np.zeros((2, d))
        self.flag = np.zeros((2, d), dtype=bool)
        # learner
        self.smooth = None  # (copies, d)
        self.n = 0.0
        self.s1 = np.zeros(self.p)
        self.s2 = np.zeros((self.p, self.p))
        self.n_model = 0.0
        self.model = None
        self.states = _Reservoir(STATE_CAP, self.p, self.rng)
        self.state_row = np.zeros(STATE_CAP, dtype=np.int64)
        self.periods: list[dict] = []
        self.rest_until = 0.0  # no evidence while an accepted change is learned
        self.pending: deque = deque()
        self.recent: deque = deque()  # learned lately; can be un-learned
        # evidence
        L = MAX_LEVEL + 1
        self.tail = np.zeros((0, self.p))  # recent feature rows
        self.tail_ok = np.zeros((0, d), dtype=bool)
        # reference per scale: block-mean feature rows of clean life,
        # re-scored whenever the model changes
        self.ref = [_Reservoir(REFERENCE_CAP, self.p, self.rng) for _ in range(L)]
        self.ref_score = np.full((L, REFERENCE_CAP, self.D), np.nan)
        self.ref_row = np.zeros((L, REFERENCE_CAP), dtype=np.int64)
        self.R = np.zeros((L, self.D))
        self.run_start = np.zeros((L, self.D), dtype=np.int64)
        self.ac = np.zeros((L, 3, self.D))  # n, sum, sumsq of block scores
        self.ac_new = np.zeros((L, 3, self.D))  # same, since the last solve
        self.cusum = np.zeros((L, self.D))  # locates the onset of a run
        cells = self.D * L + 2 * d
        self.n_cells = cells
        self.A = np.array([cells * self.rows_per_year / 2**lv / ALPHA_PER_ASSET_YEAR
                           for lv in range(L)])
        self.alpha_row = ALPHA_PER_ASSET_YEAR / (self.rows_per_year * cells)
        self.buf = np.zeros((0, d))  # recent filled rows, for isolation
        self.buf_valid = np.zeros((0, d), dtype=bool)
        self.spacing, self.gaps = 1.0, np.zeros(0)
        # episodes
        self.episode = None  # dict(kind, onset, last_alarm)
        self.masked: list[list[int]] = []  # [start, end) rows never learned

    # ------------------------------------------------------------ intake
    def _intake(self, x: np.ndarray):
        """Returns (valid mask, newly flagged [repeat, missing] per channel)."""
        c, d = x.shape
        valid = np.isfinite(x)
        new_flag = np.zeros((2, d), dtype=bool)
        for i in range(c):
            ok = valid[i]
            same = ok & (x[i] == self.last_val)
            for which, cond, base in ((0, same, ok), (1, ~ok, np.ones(d, bool))):
                ended = ~cond & (self.run[which] > 0)
                self.run_max[which] = np.where(
                    ended & ~self.flag[which],
                    np.maximum(self.run_max[which], self.run[which]),
                    self.run_max[which])
                self.flag[which] &= cond
                self.run[which] = np.where(cond, self.run[which] + 1, 0)
                rate = (self.run_hits[which] + 1) / (self.n_valid[which] + 2)
                extra = self.run[which] - self.run_max[which]
                with np.errstate(divide="ignore"):
                    improbable = extra * np.log(rate) <= np.log(self.alpha_row)
                hit = cond & (extra > 0) & improbable & ~self.flag[which]
                new_flag[which] |= hit
                self.flag[which] |= hit
                quiet = base & ~self.flag[which]
                self.run_hits[which] += cond & quiet
                self.n_valid[which] += quiet
            self.last_val = np.where(ok, x[i], self.last_val)
            valid[i] &= ~self.flag[0]
        return valid, new_flag

    # ----------------------------------------------------------- learner
    def _features(self, xf: np.ndarray, smooth0: np.ndarray):
        """Filled rows -> feature rows [x, smoothed copies], end state."""
        c = xf.shape[0]
        parts = [xf]
        end = np.empty_like(smooth0)
        for k, tau in enumerate(self.taus):
            a = 1.0 / tau
            w = (1 - a) ** np.arange(1, c + 1)
            s = w[:, None] * (smooth0[k] + a * np.cumsum(xf / w[:, None], axis=0))
            parts.append(s)
            end[k] = s[-1]
        return np.concatenate(parts, axis=1), end

    def _build(self, n: float, s1: np.ndarray, s2: np.ndarray) -> dict:
        """Running sums -> every channel's regression on the others."""
        d, m1 = self.d, 1 + MEMORY_COPIES
        mean = s1 / n
        cov = s2 / n - np.outer(mean, mean)
        sd = np.sqrt(np.clip(np.diag(cov), 0, None))
        live = sd > 1e-9 * (np.abs(mean) + 1e-9)
        sds = np.where(live, sd, 1.0)
        corr = cov / np.outer(sds, sds)
        corr[~live] = 0.0
        corr[:, ~live] = 0.0
        # ridge of one pseudo-row pulls every relation toward "unrelated"
        P = np.linalg.inv(corr + np.eye(self.p) * (1.0 / n + 1e-9))
        idx = np.arange(d)[:, None] + d * np.arange(m1)[None, :]  # (d, m1)
        Pgg = P[idx[:, :, None], idx[:, None, :]]
        Pgg_inv = np.linalg.inv(Pgg + 1e-12 * np.eye(m1))
        return dict(mean=mean, sd=sds, live=live, P=P, idx=idx, Pgg=Pgg,
                    Pgg_inv=Pgg_inv, n=n, corr=corr,
                    cvar=np.clip(Pgg_inv[:, 0, 0], 1e-12, None))

    def _refresh(self) -> None:
        m = self._build(self.n, self.s1, self.s2)
        # Operating coordinates: the directions several channels move
        # along together (load, speed, ambient), each also seen through
        # the memory copies so that rising and falling through one
        # point are different states. A direction carried by a single
        # channel is not an operating coordinate: a fault on one
        # channel must not be able to look like a new operating state.
        d, m1 = self.d, 1 + MEMORY_COPIES
        cx = m["corr"][:d, :d]
        lam, vec = np.linalg.eigh(cx)
        lam, vec = lam[::-1], vec[:, ::-1]
        dl = int(m["live"][:d].sum())
        edge = (1 + np.sqrt(dl / max(self.n, dl + 1.0))) ** 2
        shared = 1.0 / np.maximum((vec**4).sum(axis=0), 1e-12)  # channels involved
        pick = np.where((lam > edge) & (shared >= 1.5))[0][:MAX_OPERATING_DIMS]
        if pick.size == 0:
            pick = np.array([0])
        W = np.zeros((self.p, pick.size * m1))
        for b in range(m1):
            blk = slice(b * d, (b + 1) * d)
            cb = m["corr"][blk, blk]
            for i, j in enumerate(pick):
                v = vec[:, j]
                W[blk, b * pick.size + i] = v / np.sqrt(max(float(v @ cb @ v), 1e-12))
        m["W"] = W
        self.model = m
        self.n_model = self.n
        # typical spacing between remembered states, for familiarity
        live_s = np.isfinite(self.states.view()[:, 0])
        zs = self._coords(self.states.view()[live_s])
        self.spacing, self.gaps = 1.0, np.zeros(0)
        if zs.shape[0] > 2:
            # How far a remembered state was from everything remembered
            # well before it. A live row is in that position: the
            # states around it in time are not learned yet. Only the
            # recent half of life is used, as for the reference scores.
            rows = self.state_row[: live_s.size][live_s].astype(np.float64)
            d2 = ((zs[:, None, :] - zs[None, :, :]) ** 2).sum(-1)
            earlier = rows[None, :] <= rows[:, None] / self.c["refresh_growth"]
            d2 = np.where(earlier, d2, np.inf)
            nn = np.sqrt(d2.min(axis=1))
            nn = nn[(rows >= np.median(rows)) & np.isfinite(nn)]
            if nn.size:
                self.spacing = max(float(np.median(nn)), 1e-9)
                self.gaps = np.sort(nn / self.spacing)
        # The reference: the recent half of clean life, each period
        # scored by a model as far behind it as the live model can be
        # behind the present. That is exactly the position a live row is
        # in, so reference and live scores are comparable at any age,
        # including how far a young model wanders.
        keep = int(self.c["leave_out_periods"])
        while len(self.periods) > 2 * keep:  # join the two smallest neighbours
            sizes = [a["n"] + b["n"] for a, b in zip(self.periods, self.periods[1:])]
            i = int(np.argmin(sizes))
            a, b = self.periods[i], self.periods[i + 1]
            self.periods[i: i + 2] = [dict(
                n=a["n"] + b["n"], s1=a["s1"] + b["s1"], s2=a["s2"] + b["s2"],
                lo=a["lo"], hi=b["hi"])]
        # what was learned since the last solve now counts as clean life
        self.ac += self.ac_new
        self.ac_new[:] = 0.0
        self.ref_score[:] = np.nan
        gap = 1.0 / self.c["refresh_growth"]
        prefix, n0 = [], 0.0
        a1, a2 = np.zeros(self.p), np.zeros((self.p, self.p))
        for per in self.periods:
            # the model a live row at this period's start would have had:
            # everything learned up to one learning delay before it
            seen = [q for q in prefix if q[0] <= gap * per["lo"]]
            if seen and n0 >= self.n / 2 - 1 and seen[-1][1] >= 2:
                _, nk, k1, k2 = seen[-1]
                mk = self._build(nk, k1, k2)
                span = (gap * per["lo"], np.iinfo(np.int64).max)
                self._score_reference(mk, per, span)
            n0, a1, a2 = n0 + per["n"], a1 + per["s1"], a2 + per["s2"]
            prefix.append((per["hi"], n0, a1.copy(), a2.copy()))

    def _score_reference(self, mk: dict, per: dict, span) -> None:
        if True:
            for lv, r in enumerate(self.ref):
                rows = self.ref_row[lv, : r.size]
                sel = (rows >= per["lo"]) & (rows < per["hi"])
                if sel.any():
                    self.ref_score[lv, : r.size][sel] = self._score(
                        r.view()[sel], mk, span)

    def _coords(self, F: np.ndarray) -> np.ndarray:
        m = self.model
        return ((F - m["mean"]) / m["sd"] * m["live"]) @ m["W"]

    def _predict(self, F: np.ndarray, model: dict | None = None):
        """Feature rows -> (prediction in raw units, standardized residual
        of the channel values in F, leverage). No channel uses itself."""
        m = model or self.model
        d = self.d
        Z = (F - m["mean"]) / m["sd"] * m["live"]
        U = Z @ m["P"]
        Zg, Ug = Z[:, m["idx"]], U[:, m["idx"]]  # (c, d, m1)
        PZ = np.einsum("dab,cdb->cda", m["Pgg"], Zg)
        V = Ug - PZ
        Wv = np.einsum("dab,cdb->cda", m["Pgg_inv"], V)
        pred_z = -Wv[:, :, 0]
        quad = ((Z * U).sum(axis=1)[:, None] - 2 * (Zg * Ug).sum(axis=2)
                + (Zg * PZ).sum(axis=2) - (V * Wv).sum(axis=2))
        lev = np.clip(quad, 0, None) / m["n"]
        resid = (Z[:, :d] - pred_z) / np.sqrt(m["cvar"] * (1 + lev))
        pred = m["mean"][:d] + m["sd"][:d] * pred_z
        return pred, np.where(m["live"][:d], resid, np.nan), lev

    def _delay_rows(self) -> float:
        return min(self.c["learn_delay_fraction"] * self.T,
                   self.c["learn_delay_cap_days"] * self.rows_per_day)

    def _novelty(self, F: np.ndarray, without=None) -> np.ndarray:
        """Distance to the nearest remembered state, in units of the
        typical spacing between remembered states. without=(lo, hi)
        ignores states remembered from that span of rows."""
        S = self.states.view()
        if without is not None:
            rows = self.state_row[: S.shape[0]]
            S = S[(rows < without[0]) | (rows >= without[1])]
        S = S[np.isfinite(S[:, 0])]
        if S.shape[0] < 2:
            return np.full(F.shape[0], np.nan)
        za, zs = self._coords(F), self._coords(S)
        d2 = ((za[:, None, :] - zs[None, :, :]) ** 2).sum(-1)
        return np.sqrt(d2.min(axis=1)) / self.spacing

    def _familiar(self, nov: np.ndarray) -> np.ndarray:
        """Share of remembered states that sit at least this far from
        their own nearest neighbour: near 1 inside the region the asset
        has lived in, at its floor outside it. It is an absolute
        measure, so a young asset that is somewhere new every hour is
        told so."""
        n = self.gaps.size
        far = n - np.searchsorted(self.gaps, np.nan_to_num(nov, nan=np.inf), side="left")
        return np.where(np.isfinite(nov), (far + 1.0) / (n + 1.0), np.nan)

    def _score(self, F: np.ndarray, model=None, without=None) -> np.ndarray:
        """Feature rows -> (rows, D): signed standardized residual per
        channel, then the familiarity distance."""
        out = np.empty((F.shape[0], self.D))
        out[:, : self.d] = self._predict(F, model)[1]
        out[:, self.d] = self._novelty(F, without)
        return out

    def _commit(self) -> None:
        """Learn the rows just seen, unless a fault episode covers them.
        What is learned is kept for a while so that it can be taken
        back out, exactly, if an episode later turns out to have
        started inside it."""
        while self.pending:
            item = self.pending.popleft()
            lo, hi = item["end"] - item["F"].shape[0], item["end"]
            if any(lo < e and hi > s for s, e in self.masked):
                continue
            F = item["F"]
            self.n += F.shape[0]
            self.s1 += F.sum(axis=0)
            self.s2 += F.T @ F
            self.periods.append(dict(n=F.shape[0], s1=F.sum(axis=0),
                                     s2=F.T @ F, lo=lo, hi=hi))
            for j in self.states.add(F[:: max(1, F.shape[0] // 8)]):
                if j >= 0:
                    self.state_row[j] = hi - 1
            for lv, Fm, sc in item["blocks"]:
                slots = self.ref[lv].add(Fm)
                if sc is not None:
                    # sc is the score the block got when it was live.
                    # Dependence is measured on clean, learned life
                    # only, so a fault cannot silence its own evidence
                    g = np.isfinite(sc)
                    z = np.where(g, sc, 0.0)
                    self.ac_new[lv] += np.stack(
                        [g.sum(axis=0), z.sum(axis=0), (z * z).sum(axis=0)])
                for i, j in enumerate(slots):
                    if j >= 0:
                        # no score until the next solve: a row has to
                        # survive that long without an episode before
                        # anything is ranked against it
                        self.ref_row[lv, j] = hi - 1
                        self.ref_score[lv, j] = np.nan
            self.recent.append((lo, hi, F))
        keep = self.T - self.c["learn_delay_cap_days"] * self.rows_per_day
        while self.recent and self.recent[0][1] <= keep:
            self.recent.popleft()
        if self.episode is None:
            self.masked = [m for m in self.masked if m[1] > keep]
        if self.n >= 2 and self.n >= self.c["refresh_growth"] * self.n_model:
            self._refresh()

    def _unlearn(self, onset: int) -> None:
        """Take every row from onset on back out of the running sums,
        the remembered states and the reference. Sums are additive, so
        the model returns exactly to what it was before those rows."""
        took = False
        while self.recent and self.recent[-1][1] > onset:
            lo, hi, F = self.recent.pop()
            f1, f2 = F.sum(axis=0), F.T @ F
            self.n -= F.shape[0]
            self.s1 -= f1
            self.s2 -= f2
            for per in self.periods:
                if per["lo"] <= lo < per["hi"]:
                    per["n"] -= F.shape[0]
                    per["s1"] = per["s1"] - f1
                    per["s2"] = per["s2"] - f2
            took = True
        if not took:
            return
        self.ac_new[:] = 0.0
        self.periods = [q for q in self.periods if q["n"] > 0]
        cut = self.recent[-1][1] if self.recent else onset
        self.states.data[: self.states.size][self.state_row[: self.states.size] >= cut] = np.nan
        for lv, r in enumerate(self.ref):
            gone = self.ref_row[lv, : r.size] >= cut
            self.ref_score[lv, : r.size][gone] = np.nan
            self.ref_row[lv, : r.size][gone] = -1
        if self.n >= 2:
            self._refresh()

    # ---------------------------------------------------------- evidence
    def _rank(self, lv: int, sc: np.ndarray, Fm: np.ndarray):
        """Signed block scores -> (probability of a healthy block being
        at least this far off, the scores after local correction).

        A block is compared with the reference blocks recorded in the
        most similar operating states: a ramp against earlier ramps,
        idling against idling. Their average residual is what the
        global model habitually gets wrong in that state, so it is
        subtracted (this is "normal at a place" of the design), and
        the block is ranked against how far those neighbours sit from
        that average. The number of neighbours grows with the
        reference but more slowly than it, the standard condition for
        a nearest-neighbour estimate to converge."""
        d = self.d
        n = self.ref[lv].size
        ref = self.ref_score[lv, :n]
        p = np.full(sc.shape, np.nan)
        adj = sc.copy()
        p[:, d] = self._familiar(sc[:, d])
        scored = np.isfinite(ref[:, :d]).any(axis=1) if n else np.zeros(0, bool)
        ns = int(scored.sum())
        if ns < 2:
            p[:, :d] = 1.0
            return np.where(np.isfinite(sc), p, np.nan), adj
        k = max(2, min(ns, int(np.ceil(ns ** (2.0 / 3.0)))))
        za, zr = self._coords(Fm), self._coords(self.ref[lv].view())
        d2 = ((za[:, None, :] - zr[None, :, :]) ** 2).sum(-1)
        d2[:, ~scored] = np.inf
        near = np.argpartition(d2, k - 1, axis=1)[:, :k]  # (m, k)
        loc = ref[near][:, :, :d]  # (m, k, d) signed
        ok = np.isfinite(loc)
        cnt = ok.sum(axis=1)
        mu = np.where(ok, loc, 0.0).sum(axis=1) / np.maximum(cnt, 1)
        adj[:, :d] = sc[:, :d] - mu
        # each neighbour against the average of the others
        loo = np.abs(loc - mu[:, None, :]) * (cnt / np.maximum(cnt - 1, 1))[:, None, :]
        with np.errstate(invalid="ignore"):
            gt = (loo > np.abs(adj[:, None, :d])).sum(axis=1)
        # The rank is not randomized: with n reference scores it can
        # never fall below 1/(n+1). That floor is what stops a young
        # monitor from alarming; it lifts as the reference grows.
        p[:, :d] = (gt + 1.0) / (cnt + 1.0)
        return np.where(np.isfinite(sc), p, np.nan), adj

    def _independence(self) -> np.ndarray:
        """Per scale and channel, the share of a block's evidence that
        is new information: one over the number of blocks a disturbance
        of the residual typically lasts. Measured from how much more
        the block means vary at longer scales than independent blocks
        would. Short blocks of a slowly wandering residual count for
        little; blocks longer than the wander count in full."""
        n = self.ac[:, 0]
        mean = self.ac[:, 1] / np.maximum(n, 1)
        var = self.ac[:, 2] / np.maximum(n, 1) - mean**2
        ok = (n >= 8) & (var > 0)
        L = var.shape[0]
        safe = np.where(var > 0, var, 1.0)
        tau = np.ones_like(var)
        top = np.where(ok.any(axis=0), L - 1 - np.argmax(ok[::-1], axis=0), -1)
        cols = np.arange(var.shape[1])
        for lv in range(L):
            for up in range(lv + 1, L):
                ratio = 2.0 ** (up - lv) * var[up] / safe[lv]
                tau[lv] = np.where(ok[lv] & ok[up], np.maximum(tau[lv], ratio), tau[lv])
            # Is the dependence resolved? Going one scale up, the ratio
            # doubles while blocks are still fully dependent and stays
            # flat once they are independent. If it is still growing
            # faster than halfway between the two at the longest scale
            # measured so far, nothing shows the disturbance ending,
            # and it is assumed to last through every scale not yet
            # measured. This is what keeps a young monitor from
            # trusting short blocks of a residual it has not watched
            # for long.
            t = np.maximum(top, lv)
            r_top = 2.0 ** (t - lv) * var[t, cols] / safe[lv]
            tp = np.maximum(t - 1, lv)
            r_prev = 2.0 ** (tp - lv) * var[tp, cols] / safe[lv]
            open_ended = (top > lv) & (top < L - 1) & (r_top > np.sqrt(2.0) * r_prev)
            tau[lv] = np.where(open_ended,
                               np.maximum(tau[lv], r_top * 2.0 ** (L - 1 - top)), tau[lv])
        # a scale with too few blocks to measure counts as fully dependent
        return np.where(ok, 1.0 / tau, 0.0)

    def _cascade(self, F: np.ndarray, valid: np.ndarray):
        """Feature rows -> alarms [(level, channel, end row)] and the
        block-mean feature rows to learn later."""
        c = F.shape[0]
        comb = np.vstack([self.tail, F])
        comb_ok = np.vstack([self.tail_ok, valid])
        off = self.T - self.tail.shape[0]
        alarms, learn = [], []
        power = self._independence()
        for lv in range(MAX_LEVEL + 1):
            b = 2**lv
            first = (self.T // b + 1) * b
            if first > self.T + c or first - b < off:
                continue
            m = (self.T + c - first) // b + 1
            sl = slice(first - b - off, first + (m - 1) * b - off)
            Fm = comb[sl].reshape(m, b, self.p).mean(axis=1)
            if self.model is None:
                learn.append((lv, Fm, None))
                continue
            enough = comb_ok[sl].reshape(m, b, self.d).sum(axis=1) * 2 >= b
            sc = self._score(Fm)
            sc[:, : self.d] = np.where(enough, sc[:, : self.d], np.nan)
            p, adj = self._rank(lv, sc, Fm)
            learn.append((lv, Fm, adj))
            # familiarity: a block more novel than the median of the
            # asset's life counts for less, down to nothing where the
            # asset has never been
            gate = np.clip(2 * np.nan_to_num(p[:, self.d], nan=1.0), 0.0, 1.0)
            expo = power[lv][None, :] * gate[:, None]
            expo[:, self.d] = power[lv, self.d]
            e = np.where(np.isfinite(p), _bet(np.nan_to_num(p, nan=0.5)), 1.0) ** expo
            R = self.R[lv]
            for i in range(m):
                end = first + b * i
                cs = self.cusum[lv]
                self.run_start[lv] = np.where(cs <= 0.0, end - b, self.run_start[lv])
                self.cusum[lv] = np.maximum(0.0, cs + np.log(e[i]))
                R = (R + 1.0) * e[i]
                for ch in np.where(R >= self.A[lv])[0]:
                    alarms.append((lv, int(ch), int(end)))
                    R[ch] = 0.0
            self.R[lv] = R
        self.tail = comb[-(2**MAX_LEVEL):]
        self.tail_ok = comb_ok[-(2**MAX_LEVEL):]
        return alarms, learn

    # ---------------------------------------------------------- episodes
    def _healthy_max(self, w: int):
        """Largest block score clean life has produced at about this
        window length; None while there is no reference."""
        lv = int(np.clip(np.floor(np.log2(max(w, 1))), 0, MAX_LEVEL))
        while lv > 0 and self.ref[lv].size < 8:
            lv -= 1
        if self.ref[lv].size == 0:
            return None
        with np.errstate(all="ignore"):
            return np.nanmax(np.abs(self.ref_score[lv, : self.ref[lv].size]), axis=0)

    def _window(self, X: np.ndarray, w: int):
        """Filled rows -> (mean feature row of the last w rows, the
        prediction of every row)."""
        F, _ = self._features(X, np.repeat(X[:1], MEMORY_COPIES, axis=0))
        return F[-w:].mean(axis=0)[None], self._predict(F)[0]

    def _classify(self, lv: int, ch: int, end: int):
        """Returns (kind, channel indices, onset row)."""
        onset = int(min(self.run_start[lv, ch], end - 2**lv))
        w = int(np.clip(end - onset, 2**lv, self.buf.shape[0]))
        if ch == self.d:
            return NEW_STATE, (), onset
        hmax = self._healthy_max(w)
        if hmax is None:
            return MACHINE, (ch,), onset
        # Has the asset lived through enough stretches as long as this
        # run to call it a fault? A run of w rows is one event at the
        # scale of w rows. If clean life holds fewer scored blocks of
        # that length than the monitor uses to judge a single block,
        # all it can honestly say is that this is behaviour it has not
        # seen before. Sudden faults are short runs and pass this test
        # within hours; slow ones need weeks. This is the learning
        # stage of the design, computed from counts.
        run_lv = int(np.clip(np.ceil(np.log2(max(end - onset, 1))), 0, MAX_LEVEL))

        def scored(level: int) -> int:
            r = self.ref_score[level, : self.ref[level].size, : self.d]
            return int(np.isfinite(r).any(axis=1).sum())

        if scored(run_lv) < np.ceil(max(scored(lv), 1) ** (2.0 / 3.0)):
            return NEW_STATE, (), onset
        Fw, pred = self._window(self.buf, w)
        sc = np.abs(self._score(Fw)[0])
        if self._familiar(sc[self.d: self.d + 1])[0] <= 1.0 / (self.gaps.size + 1.0):
            return NEW_STATE, (), onset  # further out than any remembered gap
        wm = np.where(self.buf_valid[-w:].mean(axis=0) >= 0.5, sc[: self.d], 0.0)
        ratio = np.nan_to_num(wm / np.maximum(hmax[: self.d], 1e-12))
        # Sensor or machine: replace one channel by what the others
        # imply. If that clears every other channel, the channel is the
        # suspect; the channel that leaves the least behind is named.
        order = [ch] + [int(j) for j in np.argsort(-ratio) if j != ch]
        best, left = ch, np.inf
        for k in order[:MAX_SUSPECTS]:
            X2 = self.buf.copy()
            X2[-w:, k] = pred[-w:, k]
            m2 = np.abs(self._score(self._window(X2, w)[0])[0, : self.d])
            r2 = np.nan_to_num(m2 / np.maximum(hmax[: self.d], 1e-12))
            r2[k] = 0.0
            if r2.max() < left:
                best, left = k, float(r2.max())
        if left <= 1.0:
            return SENSOR, (best,), onset
        moved = tuple(int(j) for j in np.where(ratio > 1)[0]) or (ch,)
        return MACHINE, moved, onset

    def _accept_if_stable(self, ep: dict) -> None:
        """An episode that has not grown over a whole learning delay is
        accepted: the advisory stands, its rows are learned as the new
        normal, and evidence rests while that happens. An episode that
        keeps growing is never accepted."""
        w = int(min(self.T - ep["onset"], self.buf.shape[0]))
        hmax = self._healthy_max(w // 2)
        if w < 4 or hmax is None:
            return
        F, _ = self._features(self.buf, np.repeat(self.buf[:1], MEMORY_COPIES, axis=0))
        halves = np.stack([F[-w: -(w // 2)].mean(axis=0), F[-(w // 2):].mean(axis=0)])
        sc = np.nan_to_num(np.abs(self._score(halves)[:, : self.d]))
        moved = sc[1] > hmax[: self.d]
        # How long an episode may keep the monitor from learning is
        # graded by maturity: never longer than the same fraction of
        # the life lived before it that sets the learning delay. A
        # young monitor cannot tell a fault from its own ignorance, so
        # it must not stop learning for long; an old one can afford to.
        outlived = self.T - ep["onset"] >= self.c["learn_delay_fraction"] * max(
            ep["onset"], 1) and self.T - ep["onset"] >= self._delay_rows()
        if np.any(sc[1][moved] > sc[0][moved]) and not outlived:
            return  # still growing
        self.masked.pop()
        self.episode = None
        self.R[:] = 0.0
        # rest until the accepted rows are a share of the model
        self.rest_until = self.T + (self.c["refresh_growth"] - 1) * max(self.n, 1)

    # -------------------------------------------------------------- step
    def step(self, x: np.ndarray) -> list[Advisory]:
        x = np.asarray(x, dtype=np.float64)
        c, d = x.shape
        out: list[Advisory] = []
        valid, new_flag = self._intake(x)

        # fill invalid values: hold, then replace by the expectation
        xf = x.copy()
        for i in range(c):
            self.hold = np.where(valid[i], x[i], self.hold)
            xf[i] = np.where(valid[i], x[i], self.hold)
        if self.smooth is None:
            self.smooth = np.repeat(xf[:1], MEMORY_COPIES, axis=0)
        F, end = self._features(xf, self.smooth)
        if self.model is not None and not valid.all():
            xf = np.where(valid, xf, self._predict(F)[0])
            F, end = self._features(xf, self.smooth)
        self.smooth = end
        self.buf = np.vstack([self.buf, xf])[-(2**MAX_LEVEL):]
        self.buf_valid = np.vstack([self.buf_valid, valid])[-(2**MAX_LEVEL):]

        alarms, learn = self._cascade(F, valid)
        if self.T < self.rest_until:
            alarms = []
            self.R[:] = 0.0
        self.T += c
        self.pending.append({"end": self.T, "F": F, "blocks": learn})

        # intake advisories
        stuck = np.where(new_flag[0])[0]
        varying = max(2, int(np.ceil(0.5 * (self.run_max[0] < self.T / 2).sum())))
        if stuck.size >= varying:
            out.append(Advisory(self.T - 1, DATA, tuple(self.columns[j] for j in stuck),
                                self.T - c))
        else:
            for j in stuck:
                out.append(Advisory(self.T - 1, SENSOR, (self.columns[j],), self.T - c))
        miss = np.where(new_flag[1])[0]
        if miss.size:
            out.append(Advisory(self.T - 1, DATA, tuple(self.columns[j] for j in miss),
                                self.T - c))

        # evidence advisories: one episode at a time
        ep = self.episode
        if ep is not None and (
                self.T - ep["last_alarm"] > max(self._delay_rows(), 1)):
            if ep["kind"] != NEW_STATE:
                self.masked[-1][1] = ep["last_alarm"]
            self.episode = ep = None
            self.R[:] = 0.0
        if ep is not None and ep["kind"] != NEW_STATE and (
                self.T - ep["onset"] >= max(self._delay_rows(), 2)):
            self._accept_if_stable(ep)
            if self.episode is None:
                alarms = []  # evidence rests from this row on
        for lv, ch, end_row in alarms:
            if self.episode is not None:
                self.episode["last_alarm"] = self.T
                if self.episode["kind"] != NEW_STATE:
                    continue
            kind, chans, onset = self._classify(lv, ch, end_row)
            if self.episode is not None and kind == NEW_STATE:
                continue
            self.episode = {"kind": kind, "onset": onset, "last_alarm": self.T}
            if kind != NEW_STATE:
                self.masked.append([onset, self.T + 1])
                self._unlearn(onset)
            out.append(Advisory(end_row - 1, kind,
                                tuple(self.columns[j] for j in chans), onset, 2**lv))
        if self.episode is not None and self.episode["kind"] != NEW_STATE:
            self.masked[-1][1] = self.T + 1
        self._commit()
        return out

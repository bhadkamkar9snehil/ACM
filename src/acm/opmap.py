"""Operating map: asset-type-agnostic operating-state discovery (prototype).

Design: docs/acm-design.md, section "Operating states".

The question this module answers for any asset, with no configuration:
"where is the asset operating right now, has it been there before, and
what do its channels normally read there?"

Method, in order:
1. Running sums of the channels give a correlation matrix. Its leading
   directions are the few ways the whole asset moves together (load,
   speed, ambient). Those directions are the OPERATING COORDINATES. A
   fault on one channel barely moves them, because they are shared
   variation; that is what keeps a fault from defining its own state.
2. Each row is placed in operating coordinates by a weighted fit that
   ignores missing values and down-weights channels that disagree with
   the rest.
3. Visited places are remembered as PROTOTYPES (a bounded codebook that
   coarsens itself when it is full). Each prototype keeps the mean
   reading and the residual spread of every channel at that place.
4. Expected reading = blend of nearby prototype means plus a local
   linear correction. Residual spread is local, so a noisy state and a
   quiet state are judged by their own noise.
5. Two distances come out, and they mean different things:
   - map distance: far from every prototype, but still along the
     operating coordinates = an operating state not seen before;
   - residual: channels disagree with the expected reading at a known
     place = fault-like.
6. Prototypes where the asset dwells, joined when the asset drifts
   slowly between them, form REGIONS: the operating states shown to
   people. A continuous range of load is one region. Separate modes,
   reached only through fast transients, are separate regions.

Everything is derived from the asset's own data. The structural
constants below carry their reasons.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MAX_STATES = 128  # compute budget for the codebook, not a tuning knob
MAX_DIMS = 6  # operating variation of a machine is low-dimensional
WARMUP_ROWS = 200  # rows needed before scales and directions mean anything
RADIUS_NOISE_UNITS = 3.0  # a place = within 3 widths of the coordinate uncertainty
HUBER_C = 3.0  # channels beyond 3 residual widths lose weight in the fit
TRANSIENT_SPEED_RATIO = 3.0  # moving 3x faster than the asset's median pace
CORE_MASS_FRACTION = 0.002  # a state the asset spent >= 0.2% of life in
HOP_LINK_FRACTION = 0.01  # slow moves on >= 1% of visits join two places
SCALE_PRIOR_ROWS = 20.0  # local spread borrows from the global one until
# a prototype has about this many rows of its own
BASIS_REFRESH_GROWTH = 1.1  # re-derive directions when data grew by 10%


@dataclass
class RowResult:
    state: np.ndarray  # nearest prototype index per row
    map_distance: np.ndarray  # distance to it, in radius units (>1 = new place)
    residual: np.ndarray  # (n, d) standardized residual per channel
    transient: np.ndarray  # bool per row


class OperatingMap:
    def __init__(
        self,
        max_states: int = MAX_STATES,
        max_dims: int = MAX_DIMS,
        warmup: int = WARMUP_ROWS,
    ) -> None:
        self.max_states = max_states
        self.max_dims = max_dims
        self.warmup = warmup
        self.n = 0.0
        self.s1: np.ndarray | None = None
        self.s2: np.ndarray | None = None
        self._buffer: list[np.ndarray] = []
        self._basis_n = 0.0
        self.W: np.ndarray | None = None  # (k, d) operating directions
        self.mean: np.ndarray | None = None
        self.std: np.ndarray | None = None
        self.resid_std: np.ndarray | None = None  # global, standardized units
        self.noise: np.ndarray | None = None  # (k,) coordinate uncertainty
        self.radius = 0.0
        self.rho = 0.0  # lag-1 autocorrelation of the lead coordinate
        # prototypes (raw channel units)
        self.p_n = np.zeros(0)
        self.p_sum = np.zeros((0, 0))
        self.p_cnt = np.zeros((0, 0))
        self.p_r2 = np.zeros((0, 0))
        self.p_trans = np.zeros(0)
        self.p_hops = np.zeros((0, 0))  # slow moves between places
        self._last_state: int | None = None
        self._speeds: list[float] = []
        self._last_zs: np.ndarray | None = None

    # ------------------------------------------------------------ sums
    def _fold(self, x: np.ndarray) -> None:
        if self.s1 is None:
            d = x.shape[1]
            self.s1 = np.zeros(d)
            self.s2 = np.zeros((d, d))
        fill = self.s1 / self.n if self.n > 0 else np.nanmean(x, axis=0)
        fill = np.where(np.isfinite(fill), fill, 0.0)
        xf = np.where(np.isfinite(x), x, fill)
        self.n += xf.shape[0]
        self.s1 += xf.sum(axis=0)
        self.s2 += xf.T @ xf

    def _refresh_basis(self) -> None:
        mean = self.s1 / self.n
        cov = self.s2 / self.n - np.outer(mean, mean)
        var = np.clip(np.diag(cov), 0.0, None)
        std = np.sqrt(var)
        live = std > 1e-9 * (np.abs(mean) + 1.0)
        std = np.where(live, std, 1.0)
        corr = cov / np.outer(std, std)
        corr[~live, :] = 0.0
        corr[:, ~live] = 0.0
        lam, vec = np.linalg.eigh(corr)
        lam, vec = lam[::-1], vec[:, ::-1]
        d_live = int(live.sum())
        # keep directions above the noise edge of a random correlation
        # matrix (Marchenko-Pastur), using the effective sample size
        tau = (1.0 + self.rho) / max(1.0 - self.rho, 1e-2)
        n_eff = max(self.n / tau, d_live + 1.0)
        edge = (1.0 + np.sqrt(d_live / n_eff)) ** 2
        k = int(np.sum(lam > edge))
        k = max(1, min(k, self.max_dims, max(1, d_live - 1)))
        self.W = vec[:, :k].T.copy()
        self.mean, self.std = mean, std
        explained = (self.W**2 * lam[:k, None]).sum(axis=0)
        self.resid_std = np.sqrt(np.clip(1.0 - explained, 1e-4, None))
        self.resid_std[~live] = 1.0
        self._live = live
        self._basis_n = self.n
        self.noise = None  # directions changed: re-measure the noise width
        self._last_zs = None

    # ---------------------------------------------------------- project
    def _project(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Rows -> (operating coordinates, standardized rows). Missing
        values get no weight; disagreeing channels get reduced weight."""
        xs = (x - self.mean) / self.std
        ok = np.isfinite(xs) & self._live
        xs0 = np.where(ok, xs, 0.0)
        w = ok.astype(np.float64)
        W = self.W
        z = np.zeros((x.shape[0], W.shape[0]))
        for _ in range(2):
            A = np.einsum("kd,nd,jd->nkj", W, w, W)
            A += 1e-6 * np.eye(W.shape[0])
            b = np.einsum("kd,nd->nk", W, w * xs0)
            z = np.linalg.solve(A, b[..., None])[..., 0]
            r = np.abs(xs0 - z @ W) / self.resid_std
            w = ok * np.minimum(1.0, HUBER_C / np.maximum(r, 1e-12))
        return z, np.where(ok, xs, np.nan)

    def _proto_means(self) -> np.ndarray:
        cnt = np.maximum(self.p_cnt, 1.0)
        m = self.p_sum / cnt
        return np.where(self.p_cnt > 0, m, self.mean)

    def _proto_coords(self) -> np.ndarray:
        z, _ = self._project(self._proto_means())
        return z / self.noise

    # ----------------------------------------------------------- update
    def update(self, x: np.ndarray, learn: bool = True) -> RowResult | None:
        """Feed rows (n, d), NaN allowed. Returns None during warmup."""
        x = np.asarray(x, dtype=np.float64)
        if self.W is None:
            if not learn:
                return None
            self._buffer.append(x)
            self._fold(x)
            if self.n < self.warmup:
                return None
            self._refresh_basis()
            x = np.concatenate(self._buffer)
            self._buffer = []
        elif learn:
            self._fold(x)
            if self.n >= BASIS_REFRESH_GROWTH * self._basis_n:
                self._refresh_basis()

        z, xs = self._project(x)
        if self.noise is None:
            # Resolution of the map = how precisely one row pins down its
            # operating coordinates, given each channel's own residual
            # noise. This does not depend on the sampling rate, so raw
            # 1 Hz data and 10-minute averages are treated alike.
            D = np.where(self._live, 1.0 / self.resid_std**2, 0.0)
            C = np.linalg.inv((self.W * D) @ self.W.T
                              + 1e-9 * np.eye(self.W.shape[0]))
            self.noise = np.sqrt(np.clip(np.diag(C), 1e-12, None))
            self.radius = max(
                self.radius, RADIUS_NOISE_UNITS * np.sqrt(z.shape[1])
            )
        zs = z / self.noise
        k = zs.shape[1]
        if zs.shape[0] > 2:
            a, b = zs[:-1, 0], zs[1:, 0]
            den = float(np.std(a) * np.std(b))
            if den > 0:
                self.rho = float(
                    np.clip(np.mean((a - a.mean()) * (b - b.mean())) / den,
                            0.0, 0.99)
                )

        # pace of movement through operating space -> transient flag
        prev = self._last_zs if self._last_zs is not None else zs[:1]
        step = np.linalg.norm(
            np.diff(np.vstack([prev[-1:], zs]), axis=0), axis=1
        ) / np.sqrt(k)
        if learn:
            self._speeds.extend(step[:: max(1, step.size // 200)].tolist())
            self._speeds = self._speeds[-5000:]
            self._last_zs = zs[-1:].copy()
        pace = float(np.median(self._speeds)) if self._speeds else 1.0
        smooth = np.convolve(step, np.ones(5) / 5.0, mode="same")
        transient = smooth > TRANSIENT_SPEED_RATIO * max(pace, 1e-9)

        n = x.shape[0]
        state = np.zeros(n, dtype=np.int64)
        dist = np.full(n, np.inf)
        if self.p_n.size:
            P = self._proto_coords()
            d2 = ((zs[:, None, :] - P[None, :, :]) ** 2).sum(-1)
            state = d2.argmin(axis=1)
            dist = np.sqrt(d2[np.arange(n), state])
        if learn:
            far = np.where(dist > self.radius)[0]
            new_c = np.zeros((0, k))
            for i in far:  # leader step: only rows with no home yet
                if new_c.shape[0] and (
                    np.linalg.norm(new_c - zs[i], axis=1).min() <= self.radius
                ):
                    continue
                self._add_proto(x.shape[1])
                self._absorb(self.p_n.size - 1, x[i:i + 1], None, None)
                new_c = np.vstack([new_c, zs[i:i + 1]])
            if new_c.shape[0]:
                P = self._proto_coords()
                d2 = ((zs[:, None, :] - P[None, :, :]) ** 2).sum(-1)
                state = d2.argmin(axis=1)
                dist = np.sqrt(d2[np.arange(n), state])

        resid = self._residual(zs, xs, state, dist)
        if learn:
            for j in np.unique(state):
                m = state == j
                self._absorb(j, x[m], resid[m] * self._scale(j), transient[m])
            # slow moves: consecutive rows in different places with
            # neither row in a transient. Fast jumps are not counted.
            seq = state if self._last_state is None else np.concatenate(
                [[self._last_state], state])
            calm = ~transient if self._last_state is None else np.concatenate(
                [[True], ~transient])
            hop = (seq[1:] != seq[:-1]) & calm[1:] & calm[:-1]
            np.add.at(self.p_hops, (seq[:-1][hop], seq[1:][hop]), 1.0)
            self._last_state = int(state[-1])
            if self.p_n.size > self.max_states:
                self._coarsen()
                P = self._proto_coords()
                d2 = ((zs[:, None, :] - P[None, :, :]) ** 2).sum(-1)
                state = d2.argmin(axis=1)
                dist = np.sqrt(d2[np.arange(n), state])
        return RowResult(state, dist / self.radius, resid, transient)

    def _add_proto(self, d: int) -> None:
        if self.p_sum.shape[1] != d:
            self.p_sum = np.zeros((0, d))
            self.p_cnt = np.zeros((0, d))
            self.p_r2 = np.zeros((0, d))
        self.p_n = np.append(self.p_n, 0.0)
        self.p_hops = np.pad(self.p_hops, ((0, 1), (0, 1)))
        self.p_trans = np.append(self.p_trans, 0.0)
        self.p_sum = np.vstack([self.p_sum, np.zeros((1, d))])
        self.p_cnt = np.vstack([self.p_cnt, np.zeros((1, d))])
        self.p_r2 = np.vstack([self.p_r2, np.zeros((1, d))])

    def _absorb(self, j, x, raw_resid, transient) -> None:
        ok = np.isfinite(x)
        if raw_resid is None:  # seeding only: mean, no mass yet
            if self.p_cnt[j].sum() == 0:
                self.p_sum[j] += np.where(ok, x, 0.0).sum(axis=0)
                self.p_cnt[j] += ok.sum(axis=0)
            return
        if self.p_n[j] == 0:  # drop the seed, real rows follow
            self.p_sum[j] = 0.0
            self.p_cnt[j] = 0.0
        self.p_n[j] += x.shape[0]
        self.p_trans[j] += float(transient.sum())
        self.p_sum[j] += np.where(ok, x, 0.0).sum(axis=0)
        self.p_cnt[j] += ok.sum(axis=0)
        r2 = np.where(np.isfinite(raw_resid), raw_resid**2, 0.0)
        self.p_r2[j] += r2.sum(axis=0)

    def _scale(self, j) -> np.ndarray:
        """Local residual spread, borrowing from the global one while the
        prototype is young (cold start at the level of one state)."""
        cnt = self.p_cnt[j]
        return np.sqrt(
            (self.p_r2[j] + SCALE_PRIOR_ROWS * self.resid_std**2)
            / (cnt + SCALE_PRIOR_ROWS)
        )

    def _residual(self, zs, xs, state, dist) -> np.ndarray:
        if not self.p_n.size:
            return np.zeros_like(xs)
        P = self._proto_coords()
        M = (self._proto_means() - self.mean) / self.std
        d2 = ((zs[:, None, :] - P[None, :, :]) ** 2).sum(-1)
        wgt = np.exp(-0.5 * (d2 - d2.min(axis=1, keepdims=True))
                     / self.radius**2)
        wgt *= (self.p_n[None, :] + 1.0)
        wgt /= wgt.sum(axis=1, keepdims=True)
        m_bar = wgt @ M
        z_bar = (wgt @ P) * self.noise
        expected = m_bar + (zs * self.noise - z_bar) @ self.W
        scales = np.stack([self._scale(j) for j in range(self.p_n.size)])
        s_bar = np.sqrt(wgt @ scales**2)
        return (xs - expected) / s_bar

    def _coarsen(self) -> None:
        """Codebook full: widen what counts as one place and merge."""
        while self.p_n.size > self.max_states:
            self.radius *= 1.3
            P = self._proto_coords()
            order = np.argsort(-self.p_n)
            alive = np.ones(self.p_n.size, dtype=bool)
            for a in order:
                if not alive[a]:
                    continue
                dd = np.linalg.norm(P - P[a], axis=1)
                for b in np.where((dd < self.radius) & alive)[0]:
                    if b == a:
                        continue
                    self.p_n[a] += self.p_n[b]
                    self.p_trans[a] += self.p_trans[b]
                    self.p_sum[a] += self.p_sum[b]
                    self.p_cnt[a] += self.p_cnt[b]
                    self.p_r2[a] += self.p_r2[b]
                    self.p_hops[a, :] += self.p_hops[b, :]
                    self.p_hops[:, a] += self.p_hops[:, b]
                    alive[b] = False
            self.p_n, self.p_trans = self.p_n[alive], self.p_trans[alive]
            self.p_sum, self.p_cnt = self.p_sum[alive], self.p_cnt[alive]
            self.p_r2 = self.p_r2[alive]
            self.p_hops = self.p_hops[np.ix_(alive, alive)]
            np.fill_diagonal(self.p_hops, 0.0)
            self._last_state = None

    # ---------------------------------------------------------- regions
    def regions(self) -> np.ndarray:
        """Region id per prototype. -1 = passing through (transition or
        rarely visited). Regions are groups of adjacent dwell places."""
        m = self.p_n.size
        out = np.full(m, -1, dtype=np.int64)
        if m == 0:
            return out
        total = self.p_n.sum()
        core = (self.p_n >= CORE_MASS_FRACTION * total) & (
            self.p_trans < 0.5 * np.maximum(self.p_n, 1.0)
        )
        parent = np.arange(m)

        def find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        # Two dwell places are the same operating state when the asset
        # drifts between them slowly and often. Separate modes are only
        # reached through fast transients, so they stay separate. This
        # uses how the asset moves, not how far apart the places are.
        idx = np.where(core)[0]
        hops = self.p_hops + self.p_hops.T
        for i, a in enumerate(idx):
            for b in idx[i + 1:]:
                need = max(3.0, HOP_LINK_FRACTION * min(self.p_n[a], self.p_n[b]))
                if hops[a, b] >= need:
                    parent[find(a)] = find(b)
        roots = {}
        mass = {}
        for a in idx:
            mass[find(a)] = mass.get(find(a), 0.0) + self.p_n[a]
        for rank, r in enumerate(sorted(mass, key=lambda r: -mass[r])):
            roots[r] = rank
        for a in idx:
            out[a] = roots[find(a)]
        return out

"""Multi-horizon surprise (gem C9, Tier 0 form).

Two flaws of single-step surprise, both fixed here:

1. A TRACKING MODEL HIDES SLOW DRIFT: one-step prediction stays good while
   the machine decays, because each step is conditioned on the recent
   (already degraded) past. Predicting at several horizons splits this
   open - the long-horizon prediction is anchored in what the machine used
   to be, the short-horizon one in what it is becoming. The GAP between
   long- and short-horizon surprise is itself an early-warning statistic:
   near zero when healthy, positive and growing under slow drift.

2. PATHOLOGY IS TWO-SIDED: surprise detects the machine becoming LESS
   predictable; a machine becoming TOO predictable (dead control loop,
   stuck actuator regulating nothing) is equally sick. Health is a BAND of
   predictability at every horizon; both exits are evidence. The bilateral
   score is |windowed surprise - healthy center| in healthy-spread units.

Tier 0 mechanics: per horizon h, a ridge map from the full channel vector
at t-h to the channel vector at t (same standardization discipline as the
conditional scorer); per-horizon surprise = mean |residual z| per row.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from acm2.store.raw import TIMESTAMP_COL

HORIZONS = (1, 32, 128)  # short / medium / long, in rows
RIDGE_LAMBDA = 1e-2
BILATERAL_WINDOW = 64


@dataclass
class MultiHorizonScorer:
    horizons: tuple[int, ...] = HORIZONS
    channels: list[str] = field(default_factory=list)
    centers: np.ndarray | None = None
    scales: np.ndarray | None = None
    betas: dict[int, np.ndarray] = field(default_factory=dict)
    resid_scales: dict[int, np.ndarray] = field(default_factory=dict)
    healthy_center: dict[int, float] = field(default_factory=dict)
    healthy_spread: dict[int, float] = field(default_factory=dict)

    def fit(self, frame: pl.DataFrame) -> "MultiHorizonScorer":
        cols = [
            c
            for c, dt in frame.schema.items()
            if c != TIMESTAMP_COL and dt.is_numeric()
        ]
        x = frame.select(cols).to_numpy().astype(np.float64)
        keep, centers, scales = [], [], []
        for i in range(x.shape[1]):
            xi = x[:, i][np.isfinite(x[:, i])]
            if xi.size < 30:
                continue
            med = float(np.median(xi))
            mad = 1.4826 * float(np.median(np.abs(xi - med)))
            scale = mad if mad > 1e-12 else float(np.std(xi))
            if scale > 1e-12:
                keep.append(i)
                centers.append(med)
                scales.append(scale)
        if len(keep) < 2:
            raise ValueError("multi-horizon scorer needs >= 2 usable channels")
        self.channels = [cols[i] for i in keep]
        self.centers = np.array(centers)
        self.scales = np.array(scales)
        z = np.nan_to_num((x[:, keep] - self.centers) / self.scales)
        n, d = z.shape
        if n < 4 * max(self.horizons):
            raise ValueError(
                f"need >= {4 * max(self.horizons)} rows to fit horizons "
                f"{self.horizons}, got {n}"
            )
        for h in self.horizons:
            past, future = z[:-h], z[h:]
            gram = past.T @ past + RIDGE_LAMBDA * len(past) * np.eye(d)
            beta = np.linalg.solve(gram, past.T @ future)  # (d, d)
            resid = future - past @ beta
            med = np.median(resid, axis=0)
            mad = 1.4826 * np.median(np.abs(resid - med), axis=0)
            self.betas[h] = beta
            self.resid_scales[h] = np.maximum(mad, 1e-9)
            per_row = np.mean(np.abs(resid / self.resid_scales[h]), axis=1)
            c = float(np.median(per_row))
            s = 1.4826 * float(np.median(np.abs(per_row - c)))
            self.healthy_center[h] = c
            self.healthy_spread[h] = max(s, 1e-9)
        return self

    def _z(self, frame: pl.DataFrame) -> np.ndarray:
        out = np.full((frame.height, len(self.channels)), np.nan)
        for i, col in enumerate(self.channels):
            if col in frame.columns:
                out[:, i] = frame.get_column(col).to_numpy().astype(np.float64)
        return np.nan_to_num((out - self.centers) / self.scales)

    def surprise(self, frame: pl.DataFrame) -> dict[int, np.ndarray]:
        """Per-horizon per-row mean |residual z| (rows before the horizon
        offset are not scoreable and are omitted)."""
        z = self._z(frame)
        out = {}
        for h in self.horizons:
            if z.shape[0] <= h:
                out[h] = np.array([])
                continue
            resid = z[h:] - z[:-h] @ self.betas[h]
            out[h] = np.mean(np.abs(resid / self.resid_scales[h]), axis=1)
        return out

    def gap_stream(self, frame: pl.DataFrame) -> np.ndarray:
        """The early-warning statistic: long-horizon surprise minus
        short-horizon surprise, each normalized by its own healthy band.
        Healthy: ~0. Slow drift: positive and growing (the long horizon
        sees the departure from what the machine USED to be first)."""
        s = self.surprise(frame)
        h_short, h_long = min(self.horizons), max(self.horizons)
        a, b = s[h_short], s[h_long]
        if a.size == 0 or b.size == 0:
            return np.array([])
        m = min(a.size, b.size)
        a_n = (a[-m:] - self.healthy_center[h_short]) / self.healthy_spread[h_short]
        b_n = (b[-m:] - self.healthy_center[h_long]) / self.healthy_spread[h_long]
        return b_n - a_n

    def bilateral_stream(self, frame: pl.DataFrame) -> np.ndarray:
        """Two-sided predictability: |windowed short-horizon surprise -
        healthy center| in spread units. Both band exits (erratic AND
        too-predictable) score high."""
        s = self.surprise(frame)[min(self.horizons)]
        if s.size < BILATERAL_WINDOW:
            return np.array([])
        k = s.size // BILATERAL_WINDOW
        wm = s[: k * BILATERAL_WINDOW].reshape(k, BILATERAL_WINDOW).mean(axis=1)
        h = min(self.horizons)
        return np.abs(wm - self.healthy_center[h]) / self.healthy_spread[h]

"""Transient fingerprinting (gem C7, Tier 0 form).

An asset performs experiments on itself constantly: every start-up is a
step-response test, every shutdown a free-decay, every ramp a sweep.
Transients excite dynamics that steady state hides, and degradation shows
in transient RESPONSE (rise shape, overshoot, settle) long before
steady-state symptoms.

Mechanics (all derived from the asset's own data, no tuning):
- A transient is a contiguous run where the cross-channel rate of change
  (mean |dz| per row) exceeds its own robust threshold (median + 4 MAD of
  the calibration rate trace), minimum length 3 rows.
- Each transient's fingerprint is its rate profile resampled to a fixed
  length plus its duration - comparable across occurrences.
- The lifetime CATALOGUE holds every healthy transient's fingerprint. A
  new transient's score is its distance to the nearest catalogued sibling,
  normalized by the catalogue's own leave-one-out distance spread. The
  leave-one-out distances ARE the e-process calibration: 'how far do
  healthy transients sit from their nearest sibling?' answered from the
  catalogue itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from acm2.store.raw import TIMESTAMP_COL

PROFILE_LEN = 32
MIN_TRANSIENT_ROWS = 3
RATE_MADS = 4.0
MIN_CATALOGUE = 8  # fewer healthy transients than this -> stream disabled


SMOOTH_WINDOW = 8


def _rate_trace(z: np.ndarray) -> np.ndarray:
    """Cross-channel mean |d(smoothed z)| per row.

    Smoothing first is load-bearing: raw white noise has HIGHER
    sample-to-sample rate than a coherent ramp (found by test - the
    unsmoothed detector scored steady noise above real start-ups). A
    transient is coherent LEVEL MOVEMENT; the rolling mean isolates it.
    """
    n = z.shape[0]
    r = np.zeros(n)
    if n <= SMOOTH_WINDOW + 1:
        return r
    cs = np.cumsum(z, axis=0)
    smoothed = (cs[SMOOTH_WINDOW:] - cs[:-SMOOTH_WINDOW]) / SMOOTH_WINDOW
    dr = np.mean(np.abs(np.diff(smoothed, axis=0)), axis=1)
    r[SMOOTH_WINDOW + 1 :] = dr
    return r


def _extract(rate: np.ndarray, threshold: float) -> list[tuple[int, int]]:
    hot = rate > threshold
    regions, start = [], None
    for i, h in enumerate(hot):
        if h and start is None:
            start = i
        elif not h and start is not None:
            if i - start >= MIN_TRANSIENT_ROWS:
                regions.append((start, i))
            start = None
    if start is not None and len(hot) - start >= MIN_TRANSIENT_ROWS:
        regions.append((start, len(hot)))
    return regions


def _fingerprint(rate: np.ndarray, a: int, b: int) -> np.ndarray:
    seg = rate[a:b]
    prof = np.interp(
        np.linspace(0, seg.size - 1, PROFILE_LEN),
        np.arange(seg.size),
        seg,
    )
    scale = prof.max() or 1.0
    return np.concatenate([prof / scale, [np.log1p(seg.size), scale]])


@dataclass
class TransientCatalogue:
    channels: list[str] = field(default_factory=list)
    centers: np.ndarray | None = None
    scales: np.ndarray | None = None
    rate_threshold: float = 0.0
    fingerprints: np.ndarray | None = None  # (K, PROFILE_LEN + 2)
    loo_center: float = 0.0
    loo_spread: float = 1.0

    def fit(self, calib_frame: pl.DataFrame) -> "TransientCatalogue":
        cols = [
            c
            for c, dt in calib_frame.schema.items()
            if c != TIMESTAMP_COL and dt.is_numeric()
        ]
        x = calib_frame.select(cols).to_numpy().astype(np.float64)
        keep, centers, scales = [], [], []
        for i in range(x.shape[1]):
            xi = x[:, i][np.isfinite(x[:, i])]
            if xi.size < 30:
                continue
            med = float(np.median(xi))
            mad = 1.4826 * float(np.median(np.abs(xi - med)))
            s = mad if mad > 1e-12 else float(np.std(xi))
            if s > 1e-12:
                keep.append(i)
                centers.append(med)
                scales.append(s)
        if len(keep) < 2:
            raise ValueError("transient catalogue needs >= 2 usable channels")
        self.channels = [cols[i] for i in keep]
        self.centers, self.scales = np.array(centers), np.array(scales)

        z = np.nan_to_num((x[:, keep] - self.centers) / self.scales)
        rate = _rate_trace(z)
        med = float(np.median(rate))
        mad = 1.4826 * float(np.median(np.abs(rate - med)))
        self.rate_threshold = med + RATE_MADS * max(mad, 1e-9)

        regions = _extract(rate, self.rate_threshold)
        if len(regions) < MIN_CATALOGUE:
            raise ValueError(
                f"only {len(regions)} healthy transients found; catalogue "
                f"needs >= {MIN_CATALOGUE}"
            )
        self.fingerprints = np.vstack(
            [_fingerprint(rate, a, b) for a, b in regions]
        )
        # leave-one-out nearest-sibling distances = the healthy reference
        loo = []
        for i in range(len(self.fingerprints)):
            others = np.delete(self.fingerprints, i, axis=0)
            d = np.linalg.norm(others - self.fingerprints[i], axis=1)
            loo.append(float(d.min()))
        loo = np.array(loo)
        self.loo_center = float(np.median(loo))
        self.loo_spread = max(
            1.4826 * float(np.median(np.abs(loo - self.loo_center))), 1e-9
        )
        self._loo = loo
        return self

    def calibration_scores(self) -> np.ndarray:
        """Normalized leave-one-out distances (the healthy distribution of
        'distance to nearest sibling')."""
        return (self._loo - self.loo_center) / self.loo_spread

    def score_new(self, frame: pl.DataFrame) -> np.ndarray:
        """One score per transient found in the frame: normalized distance
        to the nearest catalogued healthy sibling. No transients -> empty
        (no evidence, no penalty - absence of experiments is not health
        NOR fault; availability covers outages)."""
        out = np.full((frame.height, len(self.channels)), np.nan)
        for i, col in enumerate(self.channels):
            if col in frame.columns:
                out[:, i] = frame.get_column(col).to_numpy().astype(np.float64)
        z = np.nan_to_num((out - self.centers) / self.scales)
        rate = _rate_trace(z)
        scores = []
        for a, b in _extract(rate, self.rate_threshold):
            fp = _fingerprint(rate, a, b)
            d = float(
                np.linalg.norm(self.fingerprints - fp, axis=1).min()
            )
            scores.append((d - self.loo_center) / self.loo_spread)
        return np.array(scores)

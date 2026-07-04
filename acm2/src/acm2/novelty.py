"""Novelty engine (S5, gem C4): left-discords over the surprise stream.

'Has this machine ever done this before?' answered exactly: the MASS
algorithm (Mueen's FFT-based z-normalized distance profile) computes the
distance from a query window to EVERY window in the asset's past surprise
stream in O(n log n) - matrix-profile machinery without the dependency,
per D13 (the surprise stream is low-dimensional by construction, so the
957-channel question never arises).

Left-only: novelty is always measured against the PAST. Distances are
normalized to [0,1] (z-normalized Euclidean has a hard ceiling of
2*sqrt(m)), so novelty thresholds are window-length-independent.

Shape discrimination (gem C5 refinement): once evidence accumulates, the
SHAPE of the surprise segment separates fault-like from change-like:
- monotone growth that never stabilizes -> drift (fault-like, escalating)
- jump to a new stable plateau -> step (operating change candidate)
"""

from __future__ import annotations

import numpy as np

NOVELTY_WINDOW = 64  # subsequence length on the surprise stream
DRIFT_TAU = 0.3  # Kendall tau above this = monotone drift
SHAPE_SUBSAMPLE = 800  # tau is O(n^2); segments are subsampled to this


def mass_distance_profile(query: np.ndarray, series: np.ndarray) -> np.ndarray:
    """Z-normalized Euclidean distance from query to every window of series."""
    q = np.asarray(query, dtype=np.float64)
    t = np.asarray(series, dtype=np.float64)
    m, n = q.size, t.size
    if n < m:
        return np.array([])
    sig_q = q.std()
    if sig_q < 1e-12:
        return np.full(n - m + 1, 2.0 * np.sqrt(m))  # flat query: max distance
    q = (q - q.mean()) / sig_q

    # rolling mean/std of series via cumulative sums
    cs = np.concatenate([[0.0], np.cumsum(t)])
    cs2 = np.concatenate([[0.0], np.cumsum(t * t)])
    mu_t = (cs[m:] - cs[:-m]) / m
    var_t = (cs2[m:] - cs2[:-m]) / m - mu_t**2
    sig_t = np.sqrt(np.maximum(var_t, 0.0))

    # sliding dot product via FFT convolution
    nf = 1 << int(np.ceil(np.log2(n + m)))
    conv = np.fft.irfft(
        np.fft.rfft(t, nf) * np.fft.rfft(q[::-1], nf), nf
    )[m - 1 : n]

    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.where(sig_t > 1e-12, conv / (m * sig_t), 0.0)
        d2 = 2.0 * m * (1.0 - corr)
    return np.sqrt(np.maximum(d2, 0.0))


class NoveltyEngine:
    """Streaming left-discord over an asset's surprise history."""

    def __init__(self, window: int = NOVELTY_WINDOW) -> None:
        self.window = window
        self._history: list[np.ndarray] = []
        self._n = 0

    def extend(self, scores: np.ndarray) -> None:
        s = np.asarray(scores, dtype=np.float64)
        s = s[np.isfinite(s)]
        if s.size:
            self._history.append(s)
            self._n += s.size

    @property
    def history(self) -> np.ndarray:
        return (
            np.concatenate(self._history) if self._history else np.array([])
        )

    def novelty(self, query: np.ndarray) -> float:
        """0 = seen before; 1 = unprecedented. Two components, max taken:

        - SHAPE novelty: z-normalized MASS distance (amplitude-blind by
          construction) - catches unprecedented temporal patterns.
        - LEVEL novelty: how far the query's mean sits above every past
          window's mean, in history-spread units - because on a surprise
          stream AMPLITUDE IS MEANING (scores are already standardized);
          a novel high excursion is novel even when its z-normalized shape
          resembles a past low-amplitude wiggle. Found empirically: shape
          alone scored an unprecedented exponential excursion 0.32 against
          a sine-cycle history.

        Query is compared against history EXCLUDING itself (append after).
        """
        q = np.asarray(query, dtype=np.float64)
        if q.size < self.window:
            return 0.0  # too short to judge; never alarm on ignorance
        q = q[-self.window :]
        hist = self.history
        if hist.size < 2 * self.window:
            return 0.0  # not enough past to claim novelty
        profile = mass_distance_profile(q, hist)
        if profile.size == 0:
            return 0.0
        shape_nov = float(profile.min() / (2.0 * np.sqrt(self.window)))

        m = self.window
        cs = np.concatenate([[0.0], np.cumsum(hist)])
        mu_h = (cs[m:] - cs[:-m]) / m
        spread = 1.4826 * float(np.median(np.abs(mu_h - np.median(mu_h))))
        spread = max(spread, 1e-9)
        excess = (float(q.mean()) - float(mu_h.max())) / spread
        level_nov = 1.0 - np.exp(-max(0.0, excess))

        return float(max(shape_nov, level_nov))


def kendall_tau(x: np.ndarray) -> float:
    """Kendall tau of a sequence against time (monotone-trend statistic,
    nonparametric, label-free). O(n^2); callers subsample."""
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    if n < 8:
        return 0.0
    i, j = np.triu_indices(n, k=1)
    diff = x[j] - x[i]
    return float((np.sign(diff)).sum() / (n * (n - 1) / 2))


def classify_shape(segment: np.ndarray) -> str:
    """'drift' | 'step' | 'noisy' over a post-onset surprise segment."""
    s = np.asarray(segment, dtype=np.float64)
    s = s[np.isfinite(s)]
    if s.size < 16:
        return "noisy"
    if s.size > SHAPE_SUBSAMPLE:
        s = s[:: s.size // SHAPE_SUBSAMPLE]
    tau = kendall_tau(s)
    if tau > DRIFT_TAU:
        return "drift"
    # step-to-stable: elevated but stationary - halves agree in level and
    # the trend is flat
    h1, h2 = s[: s.size // 2], s[s.size // 2 :]
    spread = s.std() or 1e-9
    if abs(h2.mean() - h1.mean()) < 0.5 * spread and abs(tau) < DRIFT_TAU:
        return "step"
    return "noisy"

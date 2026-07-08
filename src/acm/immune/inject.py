"""Canonical fault injectors (S2): perturb REAL healthy data.

Injection into the asset's own held-out healthy telemetry - not synthetic
data - so the sensitivity profile reflects this asset's noise, cadence, and
channel structure. Magnitudes are expressed in per-channel robust sigmas so
profiles are comparable across channels and assets.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from acm.store.raw import TIMESTAMP_COL

FAULT_CLASSES = ("drift", "step", "variance", "correlation_break")


def _robust_sigma(x: np.ndarray) -> float:
    med = np.median(x)
    mad = 1.4826 * np.median(np.abs(x - med))
    return float(mad) if mad > 1e-12 else float(np.std(x)) or 1.0


def _target_channel(frame: pl.DataFrame, channel: str | None) -> str:
    if channel is not None:
        return channel
    # default: the channel with the most structure (highest variance)
    best, best_var = None, -1.0
    for col in frame.columns:
        if col == TIMESTAMP_COL:
            continue
        v = float(np.nanvar(frame.get_column(col).to_numpy()))
        if v > best_var:
            best, best_var = col, v
    assert best is not None
    return best


def inject(
    frame: pl.DataFrame,
    fault_class: str,
    magnitude: float = 2.0,
    channel: str | None = None,
    seed: int = 0,
) -> tuple[pl.DataFrame, str]:
    """Return (perturbed copy, channel injected). Onset at 20% of the frame
    so every injection has a clean prefix (detection must not fire before
    onset - that check rides along for free in the harness)."""
    if fault_class not in FAULT_CLASSES:
        raise ValueError(f"unknown fault class {fault_class!r}")
    col = _target_channel(frame, channel)
    x = frame.get_column(col).to_numpy().astype(np.float64).copy()
    n = x.size
    onset = int(n * 0.2)
    sigma = _robust_sigma(x[np.isfinite(x)])
    rng = np.random.default_rng(seed)

    if fault_class == "drift":
        x[onset:] += np.linspace(0.0, magnitude * sigma, n - onset)
    elif fault_class == "step":
        x[onset:] += magnitude * sigma
    elif fault_class == "variance":
        centered = x[onset:] - np.mean(x[onset:])
        x[onset:] = np.mean(x[onset:]) + centered * (1.0 + magnitude)
    elif fault_class == "correlation_break":
        # preserve the marginal distribution exactly, destroy the temporal
        # and cross-channel relationships: permute the post-onset segment
        x[onset:] = rng.permutation(x[onset:])

    return frame.with_columns(pl.Series(col, x)), col

"""Availability evidence stream: standstill is a different domain than
score magnitude (the surviving JOB of legacy R4, as its own stream).

A parked/starved machine produces telemetry that is FLAT, not anomalous in
magnitude - the surprise stream can even go quiet. Availability is scored
directly: per row, the fraction of channels whose trailing window has
collapsed to (near-)zero variance relative to the channel's LIVE scale,
plus a cadence-gap indicator.

The live scale is FITTED on calibration data and stored - it must never be
derived from the frame being scored (a fully parked machine's channels are
all constant, which the first implementation skipped as 'no signal',
scoring a dead machine 0.0 everywhere; found by test). The stream feeds
its own e-process bank with its own alpha share; alarms attribute to
'availability', never mixed into magnitude.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from acm.store.raw import TIMESTAMP_COL

FLAT_WINDOW = 32  # rows; trailing window for variance collapse
FLAT_REL_STD = 0.01  # trailing std below this fraction of live scale = flat
GAP_FACTOR = 6.0  # timestamp delta above this multiple of median cadence = gap


@dataclass
class AvailabilityScorer:
    scales: dict[str, float] = field(default_factory=dict)
    median_cadence_us: float = 0.0

    def fit(self, calib_frame: pl.DataFrame) -> "AvailabilityScorer":
        for c, dt in calib_frame.schema.items():
            if c == TIMESTAMP_COL or not dt.is_numeric():
                continue
            x = calib_frame.get_column(c).to_numpy().astype(np.float64)
            x = x[np.isfinite(x)]
            if x.size < 30:
                continue
            scale = 1.4826 * float(np.median(np.abs(x - np.median(x))))
            if scale > 1e-12:
                self.scales[c] = scale
        if not self.scales:
            raise ValueError("no live channels to fit availability scales")
        ts = calib_frame.get_column(TIMESTAMP_COL).cast(pl.Int64).to_numpy()
        deltas = np.diff(ts).astype(np.float64)
        pos = deltas[deltas > 0]
        self.median_cadence_us = float(np.median(pos)) if pos.size else 0.0
        return self

    def score(self, frame: pl.DataFrame) -> np.ndarray:
        """Per-row availability score: flat-channel fraction (against the
        FITTED live scales) plus a cadence-gap indicator."""
        n = frame.height
        if n == 0:
            return np.array([])
        flat = np.zeros(n, dtype=np.float64)
        used = 0
        for c, live_scale in self.scales.items():
            if c not in frame.columns:
                continue
            used += 1
            x = frame.get_column(c).cast(pl.Float64)
            s = x.rolling_std(FLAT_WINDOW).to_numpy()
            with np.errstate(invalid="ignore"):
                flat += (s < FLAT_REL_STD * live_scale).astype(np.float64)
        flat /= max(1, used)

        gaps = np.zeros(n, dtype=np.float64)
        if self.median_cadence_us > 0 and n > 1:
            ts = frame.get_column(TIMESTAMP_COL).cast(pl.Int64).to_numpy()
            deltas = np.diff(ts).astype(np.float64)
            gaps[1:] = (
                deltas > GAP_FACTOR * self.median_cadence_us
            ).astype(np.float64)
        return flat + gaps

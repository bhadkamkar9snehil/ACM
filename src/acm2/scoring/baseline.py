"""Placeholder scorer (S1, D10): robust per-channel z against a baseline.

INTERIM by design - replaced by the probabilistic surprise substrate at S4.
Exists so the spine runs end-to-end from day one. The e-process wrapper is
scorer-agnostic: a weak scorer costs power, never validity.

Lab lessons carried in (copied knowledge, not code):
- MAD can collapse on point-mass channels (the GMM IQR-collapse incident):
  scale falls back to std, then the channel is excluded rather than allowed
  to divide by ~zero and dominate everything.
- No clipping anywhere: bounding influence is the calibrator's job
  downstream, and no mechanism may read another's artifact (R7).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from acm2.store.raw import TIMESTAMP_COL


@dataclass
class RobustZScorer:
    """Fit on a healthy frame; score() emits one surprise value per row."""

    medians: dict[str, float] | None = None
    scales: dict[str, float] | None = None

    def fit(self, frame: pl.DataFrame) -> "RobustZScorer":
        self.medians, self.scales = {}, {}
        for col in frame.columns:
            if col == TIMESTAMP_COL:
                continue
            x = frame.get_column(col).to_numpy().astype(np.float64)
            x = x[np.isfinite(x)]
            if x.size < 10:
                continue
            med = float(np.median(x))
            scale = 1.4826 * float(np.median(np.abs(x - med)))
            if scale < 1e-12:
                scale = float(np.std(x))  # MAD collapse fallback
            if scale < 1e-12:
                continue  # constant channel: excluded, not divided by
            self.medians[col] = med
            self.scales[col] = scale
        if not self.medians:
            raise ValueError("no usable channels after fit")
        return self

    def score(self, frame: pl.DataFrame) -> np.ndarray:
        """Per-row surprise: mean |z| across usable channels."""
        assert self.medians is not None and self.scales is not None
        zs = []
        for col, med in self.medians.items():
            if col not in frame.columns:
                continue
            x = frame.get_column(col).to_numpy().astype(np.float64)
            zs.append(np.abs((x - med) / self.scales[col]))
        if not zs:
            raise ValueError("no fitted channels present in frame")
        return np.nanmean(np.vstack(zs), axis=0)

    def attribution(self, frame: pl.DataFrame, top_k: int = 5) -> list[str]:
        """Channels carrying the most recent surprise (verdict attribution)."""
        assert self.medians is not None and self.scales is not None
        tail = frame.tail(min(frame.height, 256))
        contrib: dict[str, float] = {}
        for col, med in self.medians.items():
            if col not in tail.columns:
                continue
            x = tail.get_column(col).to_numpy().astype(np.float64)
            z = np.abs((x - med) / self.scales[col])
            contrib[col] = float(np.nanmean(z))
        ranked = sorted(contrib, key=contrib.get, reverse=True)
        return ranked[:top_k]

"""Marginal robust-z scorer used only as a statistical negative control."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from store.raw import TIMESTAMP_COL


@dataclass
class MarginalRobustZScorer:
    medians: dict[str, float] | None = None
    scales: dict[str, float] | None = None

    def fit(self, frame: pl.DataFrame) -> "MarginalRobustZScorer":
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
                scale = float(np.std(x))
            if scale < 1e-12:
                continue
            self.medians[col] = med
            self.scales[col] = scale
        if not self.medians:
            raise ValueError("no usable channels after fit")
        return self

    def score(self, frame: pl.DataFrame) -> np.ndarray:
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
        assert self.medians is not None and self.scales is not None
        tail = frame.tail(min(frame.height, 256))
        contrib = {}
        for col, med in self.medians.items():
            if col not in tail.columns:
                continue
            x = tail.get_column(col).to_numpy().astype(np.float64)
            z = np.abs((x - med) / self.scales[col])
            contrib[col] = float(np.nanmean(z))
        return sorted(contrib, key=contrib.get, reverse=True)[:top_k]

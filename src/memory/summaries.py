"""Mergeable per-period channel summaries (S3, rethink plan Layer 1).

THE HARD INVARIANT: everything here is MERGEABLE - two periods' summaries
combine into one without touching raw data, with preserved semantics:
counts/means/M2 merge exactly (Chan et al. parallel variance); min/max merge
exactly; quantiles are an equi-depth grid (QGRID_K points), merged by
count-weighted interpolation with error bounded by the grid resolution
(documented, not hidden). A stored median would NOT be mergeable - that is
why it is not stored.

Summaries are a CACHE (P1 derivability): closed periods are summarized once
and reused at every rebuild; only the open period is recomputed. That is the
amortization that keeps rebuild cost flat as the asset's life grows.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from store.raw import TIMESTAMP_COL

QGRID_K = 257  # equi-depth quantile grid points per channel per period


@dataclass
class ChannelSummary:
    count: int
    mean: float
    m2: float  # sum of squared deviations (Welford)
    minimum: float
    maximum: float
    qgrid: np.ndarray  # QGRID_K equi-depth quantiles

    @property
    def variance(self) -> float:
        return self.m2 / self.count if self.count > 1 else 0.0

    def quantile(self, q: float) -> float:
        return float(np.interp(q, np.linspace(0, 1, self.qgrid.size), self.qgrid))


@dataclass
class PeriodSummary:
    period: str  # "YYYY-MM"
    channels: dict[str, ChannelSummary] = field(default_factory=dict)

    @property
    def rows(self) -> int:
        return max((c.count for c in self.channels.values()), default=0)


def _summarize_channel(x: np.ndarray) -> ChannelSummary | None:
    x = x[np.isfinite(x)]
    if x.size < 2:
        return None
    qs = np.quantile(x, np.linspace(0, 1, QGRID_K))
    mean = float(np.mean(x))
    return ChannelSummary(
        count=int(x.size),
        mean=mean,
        m2=float(np.sum((x - mean) ** 2)),
        minimum=float(x.min()),
        maximum=float(x.max()),
        qgrid=qs,
    )


def build_period_summary(period: str, frame: pl.DataFrame) -> PeriodSummary:
    summary = PeriodSummary(period=period)
    for col in frame.columns:
        if col == TIMESTAMP_COL:
            continue
        cs = _summarize_channel(
            frame.get_column(col).to_numpy().astype(np.float64)
        )
        if cs is not None:
            summary.channels[col] = cs
    return summary


def _merge_channel(
    parts: list[ChannelSummary], weights: list[float] | None = None
) -> ChannelSummary:
    if weights is None:
        weights = [1.0] * len(parts)
    counts = np.array([p.count * w for p, w in zip(parts, weights)])
    total = counts.sum()
    means = np.array([p.mean for p in parts])
    mean = float(np.dot(counts, means) / total)
    # Chan et al. pairwise-generalized M2 merge
    m2 = float(
        sum(
            w * p.m2 + c * (p.mean - mean) ** 2
            for p, w, c in zip(parts, weights, counts)
        )
    )
    # count-weighted equi-depth quantile merge: sample each grid in
    # proportion to its (weighted) count, then re-grid
    pooled = np.concatenate(
        [
            np.interp(
                np.linspace(0, 1, max(9, int(QGRID_K * c / total))),
                np.linspace(0, 1, p.qgrid.size),
                p.qgrid,
            )
            for p, c in zip(parts, counts)
        ]
    )
    qgrid = np.quantile(pooled, np.linspace(0, 1, QGRID_K))
    return ChannelSummary(
        count=int(round(total)),
        mean=mean,
        m2=m2,
        minimum=min(p.minimum for p in parts),
        maximum=max(p.maximum for p in parts),
        qgrid=qgrid,
    )


def merge_summaries(
    parts: list[PeriodSummary],
    weights: list[float] | None = None,
    label: str = "merged",
) -> PeriodSummary:
    if not parts:
        return PeriodSummary(period=label)
    if weights is None:
        weights = [1.0] * len(parts)
    merged = PeriodSummary(period=label)
    channels = set().union(*(p.channels.keys() for p in parts))
    for col in channels:
        present = [
            (p.channels[col], w)
            for p, w in zip(parts, weights)
            if col in p.channels
        ]
        merged.channels[col] = _merge_channel(
            [c for c, _ in present], [w for _, w in present]
        )
    return merged

"""Lifetime baseline (S3): the boiling frog dies here.

The definition of normal is built from the asset's ENTIRE ledger-masked
life via cached per-period summaries, with the recent window's influence
capped at RECENCY_CAP (D2). A slowly developing, not-yet-detected fault in
the recent months can therefore never own more than a bounded fraction of
"normal" - the arithmetic guarantee the 180-day window never had.

Amortization (P3): closed periods are summarized once into a cache
directory and merged thereafter; only the open (current) period is
re-summarized from raw at rebuild time.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

from acm2.constants import get as const
from acm2.memory.ledger import EpisodeLedger
from acm2.memory.summaries import (
    PeriodSummary,
    build_period_summary,
    merge_summaries,
)
from acm2.store.raw import TIMESTAMP_COL, RawStore, _safe_key

RECENT_PERIODS = 2  # the open month + the one before it count as "recent"


@dataclass
class LifetimeBaseline:
    asset_key: str
    medians: dict[str, float]
    scales: dict[str, float]
    periods_used: list[str]
    rows_total: int

    @classmethod
    def build(
        cls,
        store: RawStore,
        asset_key: str,
        ledger: EpisodeLedger | None = None,
        cache_root: Path | str | None = None,
    ) -> "LifetimeBaseline":
        cache_dir = (
            Path(cache_root) / _safe_key(asset_key)
            if cache_root is not None
            else None
        )
        asset_dir = store.root / _safe_key(asset_key)
        part_files = sorted(asset_dir.glob("*.parquet"))
        if not part_files:
            raise ValueError(f"no stored history for {asset_key}")
        periods = [p.stem for p in part_files]

        # Cache entries are keyed by the LEDGER STATE for this asset: a
        # summary is computed from ledger-masked rows, so a ledger that
        # grows later (bootstrap passes, new episodes) must invalidate the
        # cache - found while wiring the detect->mask->re-detect loop.
        if ledger is not None:
            lhash = f"{abs(hash(tuple(ledger.windows(asset_key)))):x}"[:12]
        else:
            lhash = "nl"

        summaries: list[PeriodSummary] = []
        for path, period in zip(part_files, periods):
            is_open = period == periods[-1]
            cached = (
                cache_dir / f"{period}-{lhash}.pkl"
                if cache_dir is not None
                else None
            )
            if not is_open and cached is not None and cached.exists():
                summaries.append(pickle.loads(cached.read_bytes()))
                continue
            frame = pl.read_parquet(path)
            if ledger is not None:
                frame = ledger.mask(asset_key, frame)
            summary = build_period_summary(period, frame)
            summaries.append(summary)
            if not is_open and cached is not None:
                cached.parent.mkdir(parents=True, exist_ok=True)
                tmp = cached.with_suffix(".tmp")
                tmp.write_bytes(pickle.dumps(summary))
                tmp.replace(cached)

        # Recency cap (D2): the recent periods' TOTAL weight is capped at
        # RECENCY_CAP of the merged whole; older life holds the rest.
        recency_cap = float(const("RECENCY_CAP"))
        n_recent = min(RECENT_PERIODS, len(summaries))
        old, recent = summaries[:-n_recent], summaries[-n_recent:]
        if old:
            rows_old = sum(s.rows for s in old) or 1
            rows_recent = sum(s.rows for s in recent) or 1
            # weight per recent row so that recent/(recent+old) <= cap
            w_recent = min(
                1.0,
                (recency_cap / (1.0 - recency_cap)) * (rows_old / rows_recent),
            )
            weights = [1.0] * len(old) + [w_recent] * len(recent)
        else:
            weights = [1.0] * len(recent)

        merged = merge_summaries(summaries, weights=weights, label="lifetime")

        medians: dict[str, float] = {}
        scales: dict[str, float] = {}
        for col, cs in merged.channels.items():
            med = cs.quantile(0.5)
            iqr_scale = (cs.quantile(0.75) - cs.quantile(0.25)) / 1.349
            scale = iqr_scale if iqr_scale > 1e-12 else float(np.sqrt(cs.variance))
            if scale > 1e-12:
                medians[col] = med
                scales[col] = scale
        if not medians:
            raise ValueError(f"no usable channels in lifetime baseline for {asset_key}")
        return cls(
            asset_key=asset_key,
            medians=medians,
            scales=scales,
            periods_used=periods,
            rows_total=sum(s.rows for s in summaries),
        )

    def calibration_sample(
        self,
        store: RawStore,
        ledger: EpisodeLedger | None = None,
        max_rows: int = 20000,
        exclude_recent: int = RECENT_PERIODS,
    ) -> pl.DataFrame:
        """Healthy rows for e-process calibration: stride-sampled across the
        OLDER life (recent periods excluded so a developing fault cannot sit
        inside its own calibration reference), ledger-masked."""
        asset_dir = store.root / _safe_key(self.asset_key)
        part_files = sorted(asset_dir.glob("*.parquet"))
        use = part_files[:-exclude_recent] if len(part_files) > exclude_recent else part_files
        frames = []
        for path in use:
            f = pl.read_parquet(path)
            if ledger is not None:
                f = ledger.mask(self.asset_key, f)
            frames.append(f)
        full = pl.concat(frames, how="vertical_relaxed").sort(TIMESTAMP_COL)
        if full.height > max_rows:
            stride = full.height // max_rows
            full = full.gather_every(stride)
        return full

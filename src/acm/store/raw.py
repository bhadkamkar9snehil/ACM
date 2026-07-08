"""Immortal raw history store: per-asset, per-month, append-only parquet.

Design contract (docs/acm-implementation-plan.md, S0.2):

- APPEND-ONLY. There is no trim, no retention window, no delete API. The
  definition of an asset's normal behavior is anchored in its entire life;
  removing history is not a capability this module offers (rethink plan R1).
- ATOMIC. Every partition write goes to a temporary file in the same
  directory followed by os.replace(). A process killed mid-write leaves the
  previous partition content intact; stale temp files are swept on the next
  append.
- IDEMPOTENT. Rows are deduplicated by timestamp within each partition, so
  replaying the same input (crash-recovery, repeated ingestion) converges to
  the same stored state instead of growing it.
- TIMEZONE-STRICT. The canonical time column is "timestamp", timezone-aware
  UTC. Naive timestamps are rejected, not guessed (the lab's day-first /
  naive-timestamp corruption lessons are inherited as a hard rule).

Historian backfill interface slot (D16, deferred): a future backfill path
calls append() in period-sized batches pulled from a bundled historian
source. Because append() is idempotent and atomic, backfill needs no special
mode - it is just append at scale, resumable by construction. Nothing else
is built for it now, deliberately.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote

import polars as pl

TIMESTAMP_COL = "timestamp"
_TMP_MARKER = ".tmp-"


def _safe_key(asset_key: str) -> str:
    """Encode an asset key into a filesystem-safe directory name.

    Percent-encoding with no safe characters is deterministic, reversible,
    and collision-free on Windows and POSIX alike (keys like "care/A/40"
    contain path separators).
    """
    return quote(asset_key, safe="")


def _unsafe_key(dir_name: str) -> str:
    return unquote(dir_name)


class RawStore:
    """Append-only parquet store partitioned per asset per calendar month."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def append(self, asset_key: str, frame: pl.DataFrame) -> int:
        """Append rows for one asset. Returns the number of NEW rows stored.

        Rows whose timestamp already exists in the target partition are
        dropped (idempotent replay). Input may span any number of months.
        """
        if frame.is_empty():
            return 0
        frame = self._validate(frame)

        asset_dir = self.root / _safe_key(asset_key)
        asset_dir.mkdir(parents=True, exist_ok=True)
        self._sweep_stale_tmp(asset_dir)

        new_rows = 0
        parts = frame.with_columns(
            pl.col(TIMESTAMP_COL).dt.strftime("%Y-%m").alias("_period")
        ).partition_by("_period", as_dict=True)

        for (period,), part in sorted(parts.items()):
            part = part.drop("_period")
            path = asset_dir / f"{period}.parquet"
            existing = pl.read_parquet(path) if path.exists() else None
            if existing is not None:
                # diagonal = match columns by NAME: live payloads (bridge
                # JSON) carry keys in arbitrary order, and vertical concat
                # is order-sensitive - one differently-ordered batch would
                # kill the append (found by the #90 soak within minutes).
                # Missing channels land as null, new channels are added.
                merged = pl.concat([existing, part], how="diagonal_relaxed")
            else:
                merged = part
            merged = merged.unique(subset=TIMESTAMP_COL, keep="first").sort(
                TIMESTAMP_COL
            )
            before = 0 if existing is None else existing.height
            if existing is not None and merged.height == before:
                continue  # nothing new in this partition
            self._atomic_write(merged, path)
            new_rows += merged.height - before
        return new_rows

    def _atomic_write(self, frame: pl.DataFrame, path: Path) -> None:
        tmp = path.with_name(
            f"{path.name}{_TMP_MARKER}{os.getpid()}-{uuid.uuid4().hex[:8]}"
        )
        frame.write_parquet(tmp)
        os.replace(tmp, path)

    @staticmethod
    def _sweep_stale_tmp(asset_dir: Path, max_age_s: float = 3600.0) -> None:
        """Remove temp files abandoned by killed writers.

        Only files older than max_age_s are swept so a concurrent writer's
        in-flight temp file is never deleted from under it.
        """
        now = time.time()
        for tmp in asset_dir.glob(f"*{_TMP_MARKER}*"):
            try:
                if now - tmp.stat().st_mtime > max_age_s:
                    tmp.unlink()
            except OSError:
                pass  # another process may have swept it first

    @staticmethod
    def _validate(frame: pl.DataFrame) -> pl.DataFrame:
        if TIMESTAMP_COL not in frame.columns:
            raise ValueError(
                f"frame must contain a '{TIMESTAMP_COL}' column; "
                f"got columns {frame.columns}"
            )
        dtype = frame.schema[TIMESTAMP_COL]
        if not isinstance(dtype, pl.Datetime):
            raise ValueError(
                f"'{TIMESTAMP_COL}' must be a datetime column, got {dtype}"
            )
        if dtype.time_zone is None:
            raise ValueError(
                f"'{TIMESTAMP_COL}' must be timezone-aware (UTC); naive "
                "timestamps are rejected, not guessed"
            )
        if dtype.time_zone != "UTC":
            frame = frame.with_columns(
                pl.col(TIMESTAMP_COL).dt.convert_time_zone("UTC")
            )
        return frame

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def read(
        self,
        asset_key: str,
        start: Optional[object] = None,
        end: Optional[object] = None,
    ) -> pl.DataFrame:
        """Read one asset's rows, optionally restricted to [start, end)."""
        asset_dir = self.root / _safe_key(asset_key)
        paths = sorted(asset_dir.glob("*.parquet")) if asset_dir.exists() else []
        if not paths:
            return pl.DataFrame()
        # diagonal = match by name: partitions written from differently-
        # ordered sources (seed vs live buffer) must still read as one
        frame = pl.concat(
            [pl.read_parquet(p) for p in paths], how="diagonal_relaxed"
        ).sort(TIMESTAMP_COL)
        if start is not None:
            frame = frame.filter(pl.col(TIMESTAMP_COL) >= start)
        if end is not None:
            frame = frame.filter(pl.col(TIMESTAMP_COL) < end)
        return frame

    def assets(self) -> list[str]:
        return sorted(
            _unsafe_key(p.name) for p in self.root.iterdir() if p.is_dir()
        )

    def row_count(self, asset_key: str) -> int:
        asset_dir = self.root / _safe_key(asset_key)
        if not asset_dir.exists():
            return 0
        total = 0
        for p in asset_dir.glob("*.parquet"):
            total += pl.scan_parquet(p).select(pl.len()).collect().item()
        return total

    def span(self, asset_key: str) -> Optional[tuple[object, object]]:
        """(min_ts, max_ts) over the asset's stored life, or None if empty."""
        frame = self.read(asset_key)
        if frame.is_empty():
            return None
        col = frame.get_column(TIMESTAMP_COL)
        return (col.min(), col.max())

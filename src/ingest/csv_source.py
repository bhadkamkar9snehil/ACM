"""CSV ingestion into the raw store (S0.3).

Pattern salvaged (copied, per D9) from the lab's acm_feed lessons:
- timestamps parse as ISO8601 and must carry an offset (UTC 'Z' included);
  naive timestamps are REJECTED, never guessed (lab mistake #10 and the
  day-first corruption incident made this a hard rule).
- Non-numeric columns are dropped: labels and state strings must never
  enter model input (standing rule from the validation-dataset work).

Historian ingestion (D16) will reuse this module's normalize() path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from store.raw import TIMESTAMP_COL, RawStore

_TS_CANDIDATES = ("timestamp", "time_stamp", "ts", "published_at", "datetime")


@dataclass(frozen=True)
class IngestReport:
    asset_key: str
    rows_read: int
    rows_stored: int
    channels: int
    dropped_columns: tuple[str, ...]


def _find_ts_column(columns: list[str]) -> str:
    lower = {c.lower(): c for c in columns}
    for cand in _TS_CANDIDATES:
        if cand in lower:
            return lower[cand]
    for c in columns:
        if "time" in c.lower() or "date" in c.lower():
            return c
    raise ValueError(f"no timestamp column found among {columns}")


def normalize(frame: pl.DataFrame, ts_col: str | None = None) -> tuple[pl.DataFrame, tuple[str, ...]]:
    """Rename the time column to canonical, parse UTC, keep numeric channels."""
    ts = ts_col or _find_ts_column(frame.columns)
    frame = frame.rename({ts: TIMESTAMP_COL})
    if frame.schema[TIMESTAMP_COL] == pl.String:
        sample = frame.get_column(TIMESTAMP_COL).drop_nulls().head(1)
        if sample.is_empty() or not re.search(
            r"(Z|[+-]\d{2}:?\d{2})\s*$", sample.item()
        ):
            raise ValueError(
                "timestamp strings carry no UTC offset; naive timestamps "
                "are rejected, not guessed (lab rule)"
            )
        frame = frame.with_columns(
            pl.col(TIMESTAMP_COL).str.to_datetime(time_unit="us", time_zone="UTC")
        )
    dropped = tuple(
        c
        for c, dtype in frame.schema.items()
        if c != TIMESTAMP_COL and not dtype.is_numeric()
    )
    return frame.drop(dropped), dropped


def ingest_csv(
    store: RawStore,
    asset_key: str,
    path: Path | str,
    ts_col: str | None = None,
) -> IngestReport:
    raw = pl.read_csv(path, infer_schema_length=2000)
    frame, dropped = normalize(raw, ts_col=ts_col)
    stored = store.append(asset_key, frame)
    return IngestReport(
        asset_key=asset_key,
        rows_read=raw.height,
        rows_stored=stored,
        channels=frame.width - 1,
        dropped_columns=dropped,
    )


def ingest_rows(
    store: RawStore,
    asset_key: str,
    rows: list[dict],
    ts_col: str | None = None,
) -> IngestReport:
    """Manual row ingestion (#138): a list of {ts, ch1, ch2, ...} dicts,
    e.g. a POST /api/ingest body. Same normalize()/append() law as CSV."""
    if not rows:
        return IngestReport(asset_key, 0, 0, 0, ())
    raw = pl.DataFrame(rows, infer_schema_length=len(rows))
    frame, dropped = normalize(raw, ts_col=ts_col)
    stored = store.append(asset_key, frame)
    return IngestReport(
        asset_key=asset_key,
        rows_read=raw.height,
        rows_stored=stored,
        channels=frame.width - 1,
        dropped_columns=dropped,
    )

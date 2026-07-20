"""Ingestion sources (#138): pull data from where it lives into the
immortal raw store, on a cadence.

The seam (unchanged since S0.3): every path funnels through
`ingest.csv_source.normalize()` -> `RawStore.append(asset_key, frame)`.
`normalize()` is the law (canonical UTC timestamp, naive rejected,
numeric channels only, labels dropped); `append()` is idempotent +
atomic + column-order-insensitive. So a Source's only job is to produce
`(asset_key, a raw polars frame)` for rows it has not ingested yet.

All sources are WATERMARK-INCREMENTAL: they remember the max timestamp
they have ingested and ask the upstream only for rows past it. The store
dedups anyway, so a watermark is an efficiency + politeness measure (do
not re-pull or re-hammer), not a correctness one.

Sources share one duck-typed method - `drain(store) -> int` (rows newly
stored) - exactly like the pre-existing BufferSource, so the runtime's
tick loop drains any of them identically. A silent/failing source is an
availability question, never a crash: drain() returns 0 and records the
error, never raises into the tick.

Backends here are stdlib-only (files, sqlite, http via urllib) so the
default install has zero extra dependencies. A SQL-historian source
(Postgres/MSSQL via a driver) is the SAME shape as SqliteTableSource
with a different connect() - added when a deployment needs it, behind an
optional dependency, per #134 Phase 2.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import polars as pl

from ingest.csv_source import normalize
from store.raw import TIMESTAMP_COL, RawStore


def _store_frame(store: RawStore, asset_key: str, frame: pl.DataFrame,
                 last_ts: str, ts_col: Optional[str]) -> tuple[int, str]:
    """Shared tail of every source: normalize, keep only rows strictly
    after the watermark, append, and return (rows_stored, new_watermark)."""
    if frame.is_empty():
        return 0, last_ts
    frame, _dropped = normalize(frame, ts_col=ts_col)
    if last_ts:
        frame = frame.filter(
            pl.col(TIMESTAMP_COL)
            > pl.lit(last_ts).str.to_datetime(time_zone="UTC")
        )
    if frame.is_empty():
        return 0, last_ts
    stored = store.append(asset_key, frame)
    new_ts = str(frame.get_column(TIMESTAMP_COL).max())
    return stored, new_ts


@dataclass
class FileSource:
    """A CSV or parquet file re-read incrementally (a file an external
    process appends to, or a periodically-replaced export)."""

    asset_key: str
    path: str
    ts_col: Optional[str] = None
    _last_ts: str = ""
    last_error: str = ""
    last_drain_rows: int = 0

    def drain(self, store: RawStore) -> int:
        p = Path(self.path)
        if not p.exists():
            return 0
        try:
            if p.suffix == ".parquet":
                frame = pl.read_parquet(p)
            else:
                frame = pl.read_csv(p, infer_schema_length=2000)
            stored, self._last_ts = _store_frame(
                store, self.asset_key, frame, self._last_ts, self.ts_col
            )
            self.last_error = ""
            self.last_drain_rows = stored
            return stored
        except Exception as exc:  # noqa: BLE001 - availability, not a crash
            self.last_error = str(exc)
            return 0


@dataclass
class SqliteTableSource:
    """A real historian table in a SQLite file (NOT the (ts, payload_json)
    buffer shape - that is BufferSource). Reads rows with a timestamp
    column past the watermark."""

    asset_key: str
    db_path: str
    table: str
    ts_col: str = "ts"
    _last_ts: str = ""
    last_error: str = ""
    last_drain_rows: int = 0

    def drain(self, store: RawStore) -> int:
        if not Path(self.db_path).exists():
            return 0
        try:
            con = sqlite3.connect(self.db_path)
            con.row_factory = sqlite3.Row
            try:
                rows = con.execute(
                    f"SELECT * FROM {self.table} WHERE {self.ts_col} > ? "
                    f"ORDER BY {self.ts_col}",
                    (self._last_ts or "",),
                ).fetchall()
            finally:
                con.close()
            if not rows:
                return 0
            frame = pl.DataFrame([dict(r) for r in rows])
            stored, self._last_ts = _store_frame(
                store, self.asset_key, frame, self._last_ts, self.ts_col
            )
            self.last_error = ""
            self.last_drain_rows = stored
            return stored
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            return 0


@dataclass
class HttpSource:
    """Poll a JSON HTTP endpoint. Expects a JSON array of row objects (or
    an object with a `rows` array). A `since` query param carrying the
    watermark is appended so a cooperating API can serve incrementally;
    the store dedups regardless."""

    asset_key: str
    url: str
    ts_col: Optional[str] = None
    since_param: str = "since"
    rows_key: Optional[str] = None
    timeout_s: float = 10.0
    _last_ts: str = ""
    last_error: str = ""
    last_drain_rows: int = 0

    def drain(self, store: RawStore) -> int:
        url = self.url
        if self._last_ts:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{self.since_param}={self._last_ts}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            rows = data[self.rows_key] if self.rows_key else data
            if isinstance(rows, dict):
                rows = rows.get("rows", [])
            if not rows:
                return 0
            frame = pl.DataFrame(rows)
            stored, self._last_ts = _store_frame(
                store, self.asset_key, frame, self._last_ts, self.ts_col
            )
            self.last_error = ""
            self.last_drain_rows = stored
            return stored
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            return 0


def build_source(asset_key: str, config: dict):
    """Construct a Source from a registry source_config dict. Returns None
    for kinds that are push/manual (no pull step): manual, buffer (its own
    BufferSource path), folder (a fleet-level scan, not per-asset)."""
    kind = (config or {}).get("kind", "manual")
    if kind == "file":
        return FileSource(asset_key, config["path"], config.get("ts_col"))
    if kind == "sqlite":
        return SqliteTableSource(
            asset_key, config["db_path"], config["table"],
            config.get("ts_col", "ts"),
        )
    if kind == "http":
        return HttpSource(
            asset_key, config["url"], config.get("ts_col"),
            config.get("since_param", "since"), config.get("rows_key"),
        )
    return None

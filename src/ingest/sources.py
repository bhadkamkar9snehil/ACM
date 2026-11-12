"""Pull data sources feeding the canonical raw-store boundary.

Every source exposes `drain(store) -> int`. Frames pass through
`ingest.csv_source.normalize()` before `RawStore.append()`, so UTC timestamp,
numeric-channel, idempotence and label-exclusion rules stay centralized.
Watermarks are an efficiency mechanism only; the raw store remains the
correctness boundary and de-duplicates repeated rows.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import polars as pl

from ingest.csv_source import normalize
from store.raw import TIMESTAMP_COL, RawStore


def _store_frame(
    store: RawStore,
    asset_key: str,
    frame: pl.DataFrame,
    last_ts: str,
    ts_col: Optional[str],
) -> tuple[int, str]:
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
    return stored, str(frame.get_column(TIMESTAMP_COL).max())


def _sqlite_identifier(name: str) -> str:
    """Quote a SQLite identifier; values remain parameterized separately."""
    if not isinstance(name, str) or not name or "\x00" in name:
        raise ValueError("SQLite table/column name must be a non-empty string")
    return '"' + name.replace('"', '""') + '"'


def _with_query_param(url: str, name: str, value: str) -> str:
    """Set one query parameter without corrupting timestamps or existing args."""
    if not name:
        raise ValueError("HTTP watermark parameter name must not be empty")
    parts = urllib.parse.urlsplit(url)
    query = [
        pair
        for pair in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if pair[0] != name
    ]
    query.append((name, value))
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), parts.fragment)
    )


@dataclass
class FileSource:
    """A CSV/parquet file re-read incrementally as an external process updates it."""

    asset_key: str
    path: str
    ts_col: Optional[str] = None
    _last_ts: str = ""
    last_error: str = ""
    last_drain_rows: int = 0

    def drain(self, store: RawStore) -> int:
        path = Path(self.path)
        if not path.exists():
            return 0
        try:
            frame = (
                pl.read_parquet(path)
                if path.suffix.lower() == ".parquet"
                else pl.read_csv(path, infer_schema_length=2000)
            )
            stored, self._last_ts = _store_frame(
                store, self.asset_key, frame, self._last_ts, self.ts_col
            )
            self.last_error = ""
            self.last_drain_rows = stored
            return stored
        except Exception as exc:  # availability failure, never a tick crash
            self.last_error = str(exc)
            self.last_drain_rows = 0
            return 0


@dataclass
class SqliteTableSource:
    """Incremental reader for a conventional SQLite historian table."""

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
            table = _sqlite_identifier(self.table)
            ts_col = _sqlite_identifier(self.ts_col)
            con = sqlite3.connect(self.db_path)
            con.row_factory = sqlite3.Row
            try:
                rows = con.execute(
                    f"SELECT * FROM {table} WHERE {ts_col} > ? ORDER BY {ts_col}",
                    (self._last_ts or "",),
                ).fetchall()
            finally:
                con.close()
            if not rows:
                self.last_drain_rows = 0
                return 0
            frame = pl.DataFrame([dict(row) for row in rows])
            stored, self._last_ts = _store_frame(
                store, self.asset_key, frame, self._last_ts, self.ts_col
            )
            self.last_error = ""
            self.last_drain_rows = stored
            return stored
        except Exception as exc:  # availability failure, never a tick crash
            self.last_error = str(exc)
            self.last_drain_rows = 0
            return 0


@dataclass
class HttpSource:
    """Incremental JSON HTTP source using a watermark query parameter."""

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
        url = (
            _with_query_param(self.url, self.since_param, self._last_ts)
            if self._last_ts
            else self.url
        )
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_s) as response:
                data = json.loads(response.read().decode("utf-8"))
            rows = data[self.rows_key] if self.rows_key else data
            if isinstance(rows, dict):
                rows = rows.get("rows", [])
            if not rows:
                self.last_drain_rows = 0
                return 0
            frame = pl.DataFrame(rows)
            stored, self._last_ts = _store_frame(
                store, self.asset_key, frame, self._last_ts, self.ts_col
            )
            self.last_error = ""
            self.last_drain_rows = stored
            return stored
        except Exception as exc:  # availability failure, never a tick crash
            self.last_error = str(exc)
            self.last_drain_rows = 0
            return 0


def build_source(asset_key: str, config: dict):
    """Construct a configured pull source; push/manual/folder need no object."""
    kind = (config or {}).get("kind", "manual")
    if kind == "file":
        return FileSource(asset_key, config["path"], config.get("ts_col"))
    if kind == "sqlite":
        return SqliteTableSource(
            asset_key,
            config["db_path"],
            config["table"],
            config.get("ts_col", "ts"),
        )
    if kind == "http":
        return HttpSource(
            asset_key,
            config["url"],
            config.get("ts_col"),
            config.get("since_param", "since"),
            config.get("rows_key"),
        )
    return None

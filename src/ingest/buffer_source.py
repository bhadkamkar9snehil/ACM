"""Live-source ingestion via the SQLite buffer pattern (salvaged design).

The lab's proven decoupling mechanism, copied per D9 (never imported):
network bridges (OPC UA poller, MQTT subscriber, the simulator's in-process
BufferPublisher) write rows into a small SQLite buffer -
(ts TEXT, payload_json TEXT) - and the scoring side reads the buffer.
Network I/O never happens in the scoring path; a dead broker cannot stall
a tick; workers never hold sockets.

This module is the ACM-side reader: it drains new buffer rows, normalizes
them (timezone-strict UTC, labels/non-numerics dropped - same laws as CSV
ingestion), and appends to the immortal store. Idempotent by the store's
own dedupe; resumable via the last-seen timestamp.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from ingest.csv_source import normalize
from store.raw import RawStore

BUFFER_TABLES = ("mqtt_buffer", "opcua_buffer", "buffer")


@dataclass
class BufferSource:
    """One buffer database feeding one asset."""

    db_path: Path
    asset_key: str
    _last_ts: str = ""

    def _table(self, con: sqlite3.Connection) -> str | None:
        names = {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        for t in BUFFER_TABLES:
            if t in names:
                return t
        return None

    def drain(self, store: RawStore) -> int:
        """Pull rows newer than the last drain into the store. Returns the
        number of new rows stored. Missing/empty buffer = 0, never raises
        (a silent bridge is an availability question, not a crash)."""
        if not Path(self.db_path).exists():
            return 0
        con = sqlite3.connect(self.db_path)
        try:
            table = self._table(con)
            if table is None:
                return 0
            rows = con.execute(
                f"SELECT ts, payload_json FROM {table} WHERE ts > ? "
                f"ORDER BY ts",
                (self._last_ts,),
            ).fetchall()
        finally:
            con.close()
        if not rows:
            return 0
        records = []
        dropped = 0
        for ts, payload in rows:
            try:
                rec = json.loads(payload)
            except json.JSONDecodeError:
                dropped += 1  # corrupt rows counted, never silently passed
                continue
            rec.setdefault("published_at", ts)
            records.append(rec)
        if not records:
            return 0
        frame = pl.DataFrame(records, infer_schema_length=len(records))
        frame, _dropped_cols = normalize(frame)
        stored = store.append(self.asset_key, frame)
        self._last_ts = rows[-1][0]
        return stored

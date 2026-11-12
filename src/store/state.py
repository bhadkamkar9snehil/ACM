"""Relational state store (#135): durable SQLite state for everything the
service must remember.

Two kinds of state live here:
- SYSTEM-OF-RECORD, not derivable from raw history: the asset registry
  (what is monitored + where its data comes from) and the runtime journal
  (last_seen/tick_count - losing last_seen double-counts evidence on
  restart, #120). These MUST be durable and backed up.
- DERIVED but expensive to recompute, or operator-facing output: the
  episode ledger (a cache, re-derivable via bootstrap), and the decision
  output tiers (verdict history, activity log, immune results) that the
  UI reads.

Design:
- One embedded SQLite database in the data root, WAL mode: many concurrent
  readers + one writer, matching the single-service, many-threads runtime.
  The parent process is the only writer; parallel workers return diffs and
  never write shared state.
- A single connection guarded by a re-entrant lock. SQLite serializes
  writers anyway; the lock keeps Python-side multi-statement operations
  atomic and avoids "database is locked" churn under thread contention.
- Schema is versioned (schema_version table) and migrated forward in-code
  on open.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS assets (
    asset_key       TEXT PRIMARY KEY,
    display_name    TEXT,
    grp             TEXT,
    enabled         INTEGER NOT NULL DEFAULT 1,
    added_at        TEXT,
    retired_at      TEXT,
    source_kind     TEXT,
    source_config   TEXT,
    last_seen       TEXT,
    tick_count      INTEGER NOT NULL DEFAULT 0,
    bootstrapped_at TEXT
);

CREATE TABLE IF NOT EXISTS episodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_key   TEXT NOT NULL,
    start       TEXT NOT NULL,
    end         TEXT NOT NULL DEFAULT '',
    state       TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_episodes_asset ON episodes(asset_key);

CREATE TABLE IF NOT EXISTS verdict_history (
    asset_key   TEXT NOT NULL,
    at          TEXT NOT NULL,
    state       TEXT,
    evidence    REAL,
    confidence  REAL,
    attribution TEXT,
    model_epoch INTEGER,
    payload     TEXT
);
CREATE INDEX IF NOT EXISTS idx_verdict_asset_at ON verdict_history(asset_key, at);

CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT,
    asset_key   TEXT,
    kind        TEXT,
    msg         TEXT
);
CREATE INDEX IF NOT EXISTS idx_activity_at ON activity_log(id);

CREATE TABLE IF NOT EXISTS immune_results (
    asset_key   TEXT PRIMARY KEY,
    at          TEXT,
    payload     TEXT
);

CREATE TABLE IF NOT EXISTS monitor_wealth (
    asset_key   TEXT PRIMARY KEY,
    at          TEXT,
    state       TEXT
);
"""


@dataclass
class AssetRow:
    asset_key: str
    display_name: Optional[str] = None
    grp: Optional[str] = None
    enabled: bool = True
    added_at: Optional[str] = None
    retired_at: Optional[str] = None
    source_kind: Optional[str] = None
    source_config: Optional[dict] = None
    last_seen: Optional[str] = None
    tick_count: int = 0
    bootstrapped_at: Optional[str] = None


class SqliteStateStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._con = sqlite3.connect(
            str(self.path), check_same_thread=False, isolation_level=None
        )
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA synchronous=NORMAL")
        self._con.execute("PRAGMA busy_timeout=5000")
        self._con.execute("PRAGMA foreign_keys=ON")
        with self._lock:
            self._con.executescript(_SCHEMA)
            row = self._con.execute(
                "SELECT version FROM schema_version"
            ).fetchone()
            if row is None:
                self._con.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )

    def close(self) -> None:
        with self._lock:
            self._con.close()

    def list_episodes(self) -> list[dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT asset_key, start, end, state, note FROM episodes "
                "ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def add_episode(self, ep: dict) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO episodes (asset_key, start, end, state, note, "
                "created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
                (
                    ep["asset_key"], ep["start"], ep.get("end", ""),
                    ep["state"], ep.get("note", ""),
                ),
            )

    def remove_episode(self, ep: dict) -> None:
        """Delete one value-identical episode, preserving list.remove semantics."""
        with self._lock:
            row = self._con.execute(
                "SELECT id FROM episodes WHERE asset_key=? AND start=? AND "
                "end=? AND state=? AND note=? ORDER BY id LIMIT 1",
                (
                    ep["asset_key"], ep["start"], ep.get("end", ""),
                    ep["state"], ep.get("note", ""),
                ),
            ).fetchone()
            if row is not None:
                self._con.execute(
                    "DELETE FROM episodes WHERE id=?", (row["id"],)
                )

    def upsert_asset(self, row: AssetRow) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO assets (asset_key, display_name, grp, enabled, "
                "added_at, retired_at, source_kind, source_config, "
                "last_seen, tick_count, bootstrapped_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(asset_key) DO UPDATE SET "
                "display_name=excluded.display_name, grp=excluded.grp, "
                "enabled=excluded.enabled, retired_at=excluded.retired_at, "
                "source_kind=excluded.source_kind, "
                "source_config=excluded.source_config",
                (
                    row.asset_key, row.display_name, row.grp,
                    1 if row.enabled else 0, row.added_at, row.retired_at,
                    row.source_kind,
                    json.dumps(row.source_config) if row.source_config else None,
                    row.last_seen, row.tick_count, row.bootstrapped_at,
                ),
            )

    def get_asset(self, asset_key: str) -> Optional[AssetRow]:
        with self._lock:
            r = self._con.execute(
                "SELECT * FROM assets WHERE asset_key=?", (asset_key,)
            ).fetchone()
        return self._to_asset_row(r) if r is not None else None

    def list_assets(self, include_retired: bool = False) -> list[AssetRow]:
        q = "SELECT * FROM assets"
        if not include_retired:
            q += " WHERE retired_at IS NULL"
        q += " ORDER BY asset_key"
        with self._lock:
            rows = self._con.execute(q).fetchall()
        return [self._to_asset_row(r) for r in rows]

    def retire_asset(self, asset_key: str, at: str) -> None:
        with self._lock:
            self._con.execute(
                "UPDATE assets SET retired_at=?, enabled=0 WHERE asset_key=?",
                (at, asset_key),
            )

    def delete_asset(self, asset_key: str) -> None:
        """Purge state for an asset; raw history belongs to RawStore."""
        with self._lock:
            self._con.execute(
                "DELETE FROM assets WHERE asset_key=?", (asset_key,)
            )
            self._con.execute(
                "DELETE FROM episodes WHERE asset_key=?", (asset_key,)
            )
            self._con.execute(
                "DELETE FROM verdict_history WHERE asset_key=?", (asset_key,)
            )
            self._con.execute(
                "DELETE FROM immune_results WHERE asset_key=?", (asset_key,)
            )
            self._con.execute(
                "DELETE FROM monitor_wealth WHERE asset_key=?", (asset_key,)
            )

    @staticmethod
    def _to_asset_row(r: sqlite3.Row) -> AssetRow:
        return AssetRow(
            asset_key=r["asset_key"],
            display_name=r["display_name"],
            grp=r["grp"],
            enabled=bool(r["enabled"]),
            added_at=r["added_at"],
            retired_at=r["retired_at"],
            source_kind=r["source_kind"],
            source_config=(
                json.loads(r["source_config"]) if r["source_config"] else None
            ),
            last_seen=r["last_seen"],
            tick_count=r["tick_count"],
            bootstrapped_at=r["bootstrapped_at"],
        )

    def ensure_asset(self, asset_key: str, added_at: str) -> None:
        with self._lock:
            self._con.execute(
                "INSERT OR IGNORE INTO assets (asset_key, added_at) "
                "VALUES (?, ?)",
                (asset_key, added_at),
            )

    def get_last_seen(self, asset_key: str) -> Optional[str]:
        with self._lock:
            r = self._con.execute(
                "SELECT last_seen FROM assets WHERE asset_key=?", (asset_key,)
            ).fetchone()
        return r["last_seen"] if r is not None else None

    def set_last_seen(self, asset_key: str, last_seen: Optional[str]) -> None:
        with self._lock:
            self._con.execute(
                "UPDATE assets SET last_seen=? WHERE asset_key=?",
                (last_seen, asset_key),
            )

    def get_tick_count(self, asset_key: str) -> int:
        with self._lock:
            r = self._con.execute(
                "SELECT tick_count FROM assets WHERE asset_key=?", (asset_key,)
            ).fetchone()
        return int(r["tick_count"]) if r is not None else 0

    def set_tick_count(self, asset_key: str, n: int) -> None:
        with self._lock:
            self._con.execute(
                "UPDATE assets SET tick_count=? WHERE asset_key=?",
                (n, asset_key),
            )

    def get_bootstrapped(self) -> dict[str, str]:
        with self._lock:
            rows = self._con.execute(
                "SELECT asset_key, bootstrapped_at FROM assets "
                "WHERE bootstrapped_at IS NOT NULL"
            ).fetchall()
        return {r["asset_key"]: r["bootstrapped_at"] for r in rows}

    def set_bootstrapped(self, asset_key: str, at: str) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO assets (asset_key, bootstrapped_at) VALUES (?, ?)"
                " ON CONFLICT(asset_key) DO UPDATE SET bootstrapped_at=?",
                (asset_key, at, at),
            )

    def append_verdict(self, rec: dict) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO verdict_history (asset_key, at, state, evidence, "
                "confidence, attribution, model_epoch, payload) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    rec["asset_key"], rec["at"], rec.get("state"),
                    rec.get("evidence"), rec.get("confidence"),
                    json.dumps(rec.get("attribution")),
                    rec.get("model_epoch"),
                    json.dumps(rec.get("payload")) if rec.get("payload") else None,
                ),
            )

    def latest_verdicts(self) -> dict[str, dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT v.* FROM verdict_history v JOIN (SELECT asset_key, "
                "MAX(rowid) AS mr FROM verdict_history GROUP BY asset_key) m "
                "ON v.rowid = m.mr"
            ).fetchall()
        return {r["asset_key"]: dict(r) for r in rows}

    def evidence_series(self, asset_key: str, limit: int = 2000) -> list[dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT at, state, evidence, payload FROM verdict_history "
                "WHERE asset_key=? ORDER BY rowid DESC LIMIT ?",
                (asset_key, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def append_activity(self, event: dict) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO activity_log (at, asset_key, kind, msg) "
                "VALUES (?,?,?,?)",
                (
                    event.get("at"), event.get("asset_key"),
                    event.get("kind"), event.get("msg"),
                ),
            )

    def recent_activity(self, limit: int = 500) -> list[dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT at, asset_key, kind, msg FROM activity_log "
                "ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def upsert_immune(self, asset_key: str, at: str, payload: dict) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO immune_results (asset_key, at, payload) "
                "VALUES (?,?,?) ON CONFLICT(asset_key) DO UPDATE SET "
                "at=excluded.at, payload=excluded.payload",
                (asset_key, at, json.dumps(payload)),
            )

    def all_immune(self) -> dict[str, dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT asset_key, payload FROM immune_results"
            ).fetchall()
        return {r["asset_key"]: json.loads(r["payload"]) for r in rows}

    def save_wealth(self, asset_key: str, at: str, state: dict) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO monitor_wealth (asset_key, at, state) "
                "VALUES (?,?,?) ON CONFLICT(asset_key) DO UPDATE SET "
                "at=excluded.at, state=excluded.state",
                (asset_key, at, json.dumps(state)),
            )

    def get_wealth(self, asset_key: str) -> Optional[dict]:
        with self._lock:
            r = self._con.execute(
                "SELECT state FROM monitor_wealth WHERE asset_key=?",
                (asset_key,),
            ).fetchone()
        return json.loads(r["state"]) if r is not None else None

    def table_counts(self) -> dict[str, int]:
        out = {}
        with self._lock:
            for table in (
                "assets", "episodes", "verdict_history", "activity_log",
                "immune_results",
            ):
                out[table] = self._con.execute(
                    f"SELECT COUNT(*) AS n FROM {table}"
                ).fetchone()["n"]
        return out


def migrate_json_files(store: SqliteStateStore, data_root: Path) -> dict:
    """One-time import of pre-#135 JSON state into SQLite.

    The source files are renamed aside after a successful import, making the
    migration idempotent while preserving a downgrade copy.
    """
    data_root = Path(data_root)
    report = {"episodes": 0, "bootstrapped": 0}

    ledger_json = data_root / "ledger.json"
    if ledger_json.exists() and not store.list_episodes():
        episodes = json.loads(ledger_json.read_text(encoding="utf-8"))
        for episode in episodes:
            store.add_episode(episode)
        report["episodes"] = len(episodes)
        ledger_json.rename(ledger_json.with_suffix(".json.migrated"))

    boot_json = data_root / "bootstrapped.json"
    if boot_json.exists() and not store.get_bootstrapped():
        marks = json.loads(boot_json.read_text(encoding="utf-8"))
        for key, at in marks.items():
            store.set_bootstrapped(key, at)
        report["bootstrapped"] = len(marks)
        boot_json.rename(boot_json.with_suffix(".json.migrated"))

    return report

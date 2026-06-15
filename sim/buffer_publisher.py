from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class BufferPublisher:
    """Writes replay data directly into ACM's mqtt_buffer.db — no network hop.
    
    ACM's acm_feed._load_mqtt_increment() reads from this same SQLite table,
    so data written here appears in ACM's next ingestion tick automatically.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (ROOT / "data_cache" / "mqtt_buffer.db")
        self._tag_names: dict[str, str] = {}
        self._ensure_table()

    def _ensure_table(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path)
        try:
            with con:
                con.execute(
                    "CREATE TABLE IF NOT EXISTS mqtt_buffer(ts TEXT, payload_json TEXT)"
                )
        finally:
            con.close()

    async def configure_tags(self, config: Any) -> None:
        self._tag_names = {}
        for tag in config.tags:
            if tag.enabled:
                self._tag_names[tag.node_id] = tag.tag_name
        self._ensure_table()

    async def start(self) -> None:
        self._ensure_table()

    async def stop(self) -> None:
        pass

    async def update_values(
        self,
        values: dict[str, tuple[Any, str]],
        timestamp: str | None = None,
        current_values: Any = None,
        mqtt_metadata: Any = None,
    ) -> None:
        ts = timestamp or _utcnow()
        payload: dict[str, Any] = {"published_at": ts}
        for node_id, (value, _dtype) in values.items():
            col_name = self._tag_names.get(node_id) or node_id.split(".")[-1]
            payload[col_name] = value
        con = sqlite3.connect(self.db_path)
        try:
            with con:
                con.execute(
                    "INSERT INTO mqtt_buffer (ts, payload_json) VALUES (?, ?)",
                    (ts, json.dumps(payload, default=str)),
                )
        finally:
            con.close()

    def get_endpoint(self) -> str:
        return f"acm://buffer:{self.db_path}"

    def get_status(self) -> dict[str, Any]:
        count = 0
        con = sqlite3.connect(self.db_path)
        try:
            row = con.execute("SELECT COUNT(*) FROM mqtt_buffer").fetchone()
            count = row[0] if row else 0
        except Exception:
            pass
        finally:
            con.close()
        return {"connected": True, "buffer_rows": count, "db_path": str(self.db_path)}

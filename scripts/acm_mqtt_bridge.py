#!/usr/bin/env python3
"""
ACM MQTT bridge — singleton subscriber that buffers Simulator flat-topic
payloads into a local SQLite file so acm_feed.load_increment can read them
like any other incremental source.

The bridge runs as a daemon thread inside acm_service.  Worker processes
(ProcessPoolExecutor) never touch the broker; they only read the SQLite
buffer, so the bridge stays safely in the parent.

Topic consumed:  industrial-tag-simulator/flat
Payload shape:   {"published_at": "...", "tag1": 1.23, "tag2": 4.56, ...}
Buffer schema:   mqtt_buffer(ts TEXT, payload_json TEXT)
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

_instance: Optional["MqttBridge"] = None
_lock = threading.Lock()

DEFAULT_TOPIC = "industrial-tag-simulator/flat"
DEFAULT_DB_NAME = "mqtt_buffer.db"


class MqttBridge:
    def __init__(self, host: str, port: int, topic: str, db_path: Path) -> None:
        self.host = host
        self.port = port
        self.topic = topic
        self.db_path = Path(db_path)
        self.connected = False
        self.last_error: Optional[str] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS mqtt_buffer "
                "(ts TEXT NOT NULL, payload_json TEXT NOT NULL)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_mqtt_ts ON mqtt_buffer(ts)"
            )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="acm-mqtt-bridge"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        try:
            import paho.mqtt.client as mqtt  # type: ignore
        except ImportError:
            self.last_error = "paho-mqtt not installed; MQTT source unavailable."
            return

        try:
            client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2, client_id="acm-mqtt-bridge"
            )
        except AttributeError:
            client = mqtt.Client(client_id="acm-mqtt-bridge")  # paho 1.x

        def on_connect(c, userdata, flags, rc, properties=None) -> None:
            if int(rc) == 0:
                self.connected = True
                c.subscribe(self.topic, qos=0)
            else:
                self.last_error = f"MQTT connect failed rc={rc}"

        def on_disconnect(c, userdata, flags=None, rc=None, properties=None) -> None:
            self.connected = False

        def on_message(c, userdata, msg) -> None:
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                ts = (
                    str(payload.get("published_at") or "")
                    or datetime.now(timezone.utc).isoformat()
                )
                with sqlite3.connect(str(self.db_path)) as con:
                    con.execute(
                        "INSERT INTO mqtt_buffer(ts, payload_json) VALUES (?, ?)",
                        (ts, json.dumps(payload)),
                    )
            except Exception as exc:
                self.last_error = str(exc)

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message

        try:
            client.connect(self.host, self.port, keepalive=60)
        except Exception as exc:
            self.last_error = f"Cannot connect to MQTT broker at {self.host}:{self.port}: {exc}"
            return

        while not self._stop.is_set():
            client.loop(timeout=0.5)

        try:
            client.disconnect()
        except Exception:
            pass

    def prune(self, keep_hours: float = 200.0) -> None:
        """Drop buffer rows older than keep_hours to bound DB size."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=keep_hours)).isoformat()
        with sqlite3.connect(str(self.db_path)) as con:
            con.execute("DELETE FROM mqtt_buffer WHERE ts < ?", (cutoff,))

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "broker": f"{self.host}:{self.port}",
            "topic": self.topic,
            "db": str(self.db_path),
            "last_error": self.last_error,
        }


def get_or_start(
    host: str = "localhost",
    port: int = 1883,
    topic: str = DEFAULT_TOPIC,
    db_path: Optional[Path] = None,
) -> MqttBridge:
    """Return the process-singleton bridge, starting it on first call."""
    global _instance
    with _lock:
        if _instance is None:
            if db_path is None:
                db_path = (
                    Path(__file__).resolve().parents[1] / "data_cache" / DEFAULT_DB_NAME
                )
            _instance = MqttBridge(host=host, port=port, topic=topic, db_path=db_path)
            _instance.start()
    return _instance

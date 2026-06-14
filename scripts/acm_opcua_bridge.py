#!/usr/bin/env python3
"""
ACM OPC UA bridge — polls the Simulator's OPC UA server, buffers tag rows
into a local SQLite file so acm_feed.load_increment can consume them like
any other incremental historian source.

Node layout expected (Simulator default):
    Objects / TagSimulator / <tag variables>

The bridge runs as an asyncio background task inside acm_service.  Worker
processes (ProcessPoolExecutor) never touch the OPC UA server; they only
read the SQLite buffer file — the same pattern as acm_mqtt_bridge.

Configuration (via SourceSpec fields):
    source_kind  = "opcua"
    source_ref   = OPC UA endpoint URL
                   e.g. "opc.tcp://localhost:4840/simulator"
    conn_ref     = path to SQLite buffer DB
                   (falls back to data_cache/opcua_buffer.db)
    timestamp_col  used as the timestamp field name in the buffer rows
                   (falls back to "published_at")
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

DEFAULT_ENDPOINT = "opc.tcp://localhost:4840/simulator"
DEFAULT_NS_URI = "http://local/industrial-tag-simulator"
DEFAULT_ROOT_FOLDER = "TagSimulator"
DEFAULT_DB_NAME = "opcua_buffer.db"
DEFAULT_POLL_SECONDS = 1.0

_instance: Optional["OpcUaBridge"] = None
_instance_lock: Optional[asyncio.Lock] = None


def _get_lock() -> asyncio.Lock:
    global _instance_lock
    if _instance_lock is None:
        _instance_lock = asyncio.Lock()
    return _instance_lock


class OpcUaBridge:
    """Async OPC UA polling bridge — singleton per process, asyncio-native."""

    def __init__(
        self,
        endpoint: str,
        ns_uri: str,
        root_folder: str,
        db_path: Path,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
    ) -> None:
        self.endpoint = endpoint
        self.ns_uri = ns_uri
        self.root_folder = root_folder
        self.db_path = Path(db_path)
        self.poll_seconds = poll_seconds
        self.connected = False
        self.last_error: Optional[str] = None
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS opcua_buffer "
                "(ts TEXT NOT NULL, payload_json TEXT NOT NULL)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_opcua_ts ON opcua_buffer(ts)"
            )

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="acm-opcua-bridge")

    async def stop(self) -> None:
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self.connected = False

    async def _run(self) -> None:
        try:
            from asyncua import Client  # type: ignore
        except ImportError:
            self.last_error = "asyncua not installed; OPC UA source unavailable."
            return

        while not self._stop.is_set():
            try:
                async with Client(url=self.endpoint) as client:
                    self.connected = True
                    self.last_error = None

                    # Resolve namespace index
                    try:
                        ns_idx = await client.get_namespace_index(self.ns_uri)
                    except Exception:
                        ns_idx = 2  # common fallback index

                    # Locate root folder: Objects/<ns_idx>:<root_folder>
                    try:
                        root = await client.nodes.objects.get_child(
                            f"{ns_idx}:{self.root_folder}"
                        )
                    except Exception as exc:
                        self.last_error = (
                            f"Cannot find node '{self.root_folder}' under Objects: {exc}"
                        )
                        await asyncio.sleep(5)
                        continue

                    children = await root.get_children()
                    if not children:
                        await asyncio.sleep(self.poll_seconds)
                        continue

                    # Build browse-name map (stable as long as server runs)
                    node_names: Dict[str, str] = {}
                    for child in children:
                        try:
                            bn = await child.read_browse_name()
                            node_names[child.nodeid.to_string()] = bn.Name
                        except Exception:
                            node_names[child.nodeid.to_string()] = child.nodeid.to_string()

                    # Poll loop
                    while not self._stop.is_set():
                        try:
                            values = await asyncio.gather(
                                *[c.read_value() for c in children],
                                return_exceptions=True,
                            )
                            ts = datetime.now(timezone.utc).isoformat()
                            row: dict = {"published_at": ts}
                            for child, val in zip(children, values):
                                if isinstance(val, Exception):
                                    continue
                                name = node_names.get(
                                    child.nodeid.to_string(),
                                    child.nodeid.to_string(),
                                )
                                try:
                                    # OPC UA Variant wrapping — unwrap to Python scalar
                                    row[name] = float(val) if isinstance(val, (int, float)) else str(val)
                                except Exception:
                                    row[name] = str(val)

                            with sqlite3.connect(str(self.db_path)) as con:
                                con.execute(
                                    "INSERT INTO opcua_buffer(ts, payload_json) VALUES (?, ?)",
                                    (ts, json.dumps(row, default=str)),
                                )
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            self.last_error = str(exc)

                        try:
                            await asyncio.wait_for(
                                asyncio.shield(self._stop.wait()),
                                timeout=self.poll_seconds,
                            )
                            break  # stop was set
                        except asyncio.TimeoutError:
                            pass  # normal — keep polling

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.last_error = str(exc)
                self.connected = False
                try:
                    await asyncio.wait_for(
                        asyncio.shield(self._stop.wait()), timeout=5.0
                    )
                    break
                except asyncio.TimeoutError:
                    pass

    def prune(self, keep_hours: float = 200.0) -> None:
        """Drop buffer rows older than keep_hours to bound DB size."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=keep_hours)).isoformat()
        with sqlite3.connect(str(self.db_path)) as con:
            con.execute("DELETE FROM opcua_buffer WHERE ts < ?", (cutoff,))

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "endpoint": self.endpoint,
            "db": str(self.db_path),
            "poll_seconds": self.poll_seconds,
            "last_error": self.last_error,
        }


async def get_or_start(
    endpoint: str = DEFAULT_ENDPOINT,
    ns_uri: str = DEFAULT_NS_URI,
    root_folder: str = DEFAULT_ROOT_FOLDER,
    db_path: Optional[Path] = None,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
) -> OpcUaBridge:
    """Return the process-singleton bridge, starting it on first call."""
    global _instance
    async with _get_lock():
        if _instance is None:
            if db_path is None:
                db_path = (
                    Path(__file__).resolve().parents[1]
                    / "data_cache"
                    / DEFAULT_DB_NAME
                )
            _instance = OpcUaBridge(
                endpoint=endpoint,
                ns_uri=ns_uri,
                root_folder=root_folder,
                db_path=db_path,
                poll_seconds=poll_seconds,
            )
            await _instance.start()
    return _instance

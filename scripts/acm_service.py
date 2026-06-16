#!/usr/bin/env python3
"""
ACM service — the always-on condition monitor: scheduler + control panel.

One process does both jobs:
  scheduler   every tick (default 15 min): incremental historian pull into
              the per-asset raw cache, time-aware readiness gate, parallel
              stateless re-learn + score (core.pipeline), results into the
              canonical SQL store
  web panel   single-page UI at http://host:port with three persona screens
              (Operator / Reliability Engineer / Admin) over a JSON API

Everything controllable by a human is controllable here: run-now, pause/
resume, tick interval, asset onboarding/retirement, human-ops config with an
audit trail, alarm acknowledgement. ML parameters are code (core/ml_defaults
and the self-tuned rules) and are deliberately NOT exposed.

Usage:
  python scripts/acm_service.py [--backend sqlite|mssql] [--db acm_results.db]
      [--conn "..."] [--host 127.0.0.1] [--port 8765]
"""
from __future__ import annotations

import argparse
import asyncio
import multiprocessing as mp
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

import warnings
warnings.filterwarnings("ignore", category=Warning, module="requests")
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM_DATA_DIR = ROOT / "sim_data"
sys.path.insert(0, str(ROOT))


_SEP  = "  " + "─" * 53   # ─────...
_CHK  = "✓"                # ✓
_TRI  = "▸"                # ▸
_DOT  = "·"                # ·
_CYN  = "\x1b[36m"
_GRN  = "\x1b[32m"
_DIM  = "\x1b[2m"
_RST  = "\x1b[0m"


def _startup_banner(host: str, port: int, backend: str, db: Optional[str]) -> None:
    db_label = db or "default"
    store_label = f"SQL Server  {_DOT}  {db_label}" if backend == "mssql" else f"SQLite  {_DOT}  {db_label}"
    print(flush=True)
    print(f"{_CYN}  ACM  {_DOT}  Asset Condition Monitor{_RST}", flush=True)
    print(f"{_DIM}{_SEP}{_RST}", flush=True)
    print(f"  {_TRI}  {_CYN}http://{host}:{port}{_RST}", flush=True)
    print(f"{_DIM}  {_TRI}  Store  {_DOT}  {store_label}{_RST}", flush=True)
    print(f"{_DIM}{_SEP}{_RST}", flush=True)
    print(f"{_DIM}  Scheduler active  {_DOT}  Ctrl-C to stop{_RST}", flush=True)
    print(flush=True)

from fastapi import FastAPI, HTTPException                    # noqa: E402
from fastapi.responses import FileResponse                    # noqa: E402
from fastapi.staticfiles import StaticFiles                   # noqa: E402

from scripts import acm_store as st                           # noqa: E402
from scripts.acm_feed import (                                # noqa: E402
    SourceSpec, cache_path, load_increment, readiness, score_cached, update_cache,
)
from utils.config_dict import ConfigDict, cfg_get             # noqa: E402

CONFIG_CSV = ROOT / "configs" / "config_table.csv"
STATIC_DIR = ROOT / "static"
# Human-ops categories editable from the panel. ML sections (models,
# thresholds, fusion, features, ...) live in code and are rejected.
EDITABLE_CATEGORIES = {"data", "sql", "runtime", "report", "maintenance"}

_MISS = object()  # sentinel: cache miss


class _TTLCache:
    """Thread-safe-for-asyncio in-memory TTL cache.

    All FastAPI handlers and the scheduler tick run on the same event-loop
    thread, so plain dict access is safe without locks.
    """
    __slots__ = ("_ttl", "_store")

    def __init__(self, ttl: float) -> None:
        self._ttl = ttl
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any:
        entry = self._store.get(key)
        if entry is not None and time.monotonic() - entry[0] < self._ttl:
            return entry[1]
        return _MISS

    def put(self, key: str, val: Any) -> None:
        self._store[key] = (time.monotonic(), val)

    def drop(self, *keys: str) -> None:
        for k in keys:
            self._store.pop(k, None)

    def clear(self) -> None:
        self._store.clear()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")


def _cfg() -> ConfigDict:
    return ConfigDict.from_csv(CONFIG_CSV, equip_id=0)


class Service:
    """Scheduler + store access for the API routes."""

    def __init__(self, backend: str, db: Optional[str], conn_str: Optional[str],
                 api_cache_ttl: float = 30.0):
        self.backend, self.db, self.conn_str = backend, db, conn_str
        self.store = st.Store(backend, db=db, conn_str=conn_str)
        cfg = _cfg()
        self._host = str(cfg_get(cfg, "runtime.service.host", "127.0.0.1"))
        self._port = int(cfg_get(cfg, "runtime.service.port", 8765))
        self.cache_dir = ROOT / str(cfg_get(cfg, "runtime.cache_dir", "data_cache"))
        self.workers = int(cfg_get(cfg, "runtime.workers", 2))
        self.train_window_days = float(cfg_get(cfg, "runtime.train_window_days", 180.0))
        self.min_train_days = float(cfg_get(cfg, "runtime.min_train_days", 14.0))
        self.stale_after_hours = float(cfg_get(cfg, "runtime.stale_after_hours", 24.0))
        self.retention_days = float(cfg_get(cfg, "runtime.retention_days", 90.0))
        self.score_days = float(cfg_get(cfg, "data.score_days", 30.0))
        default_tick = int(cfg_get(cfg, "runtime.tick_minutes", 15))
        state = st.get_service_state(self.store, default_tick_minutes=default_tick)
        # Migrate old databases (paused=0 from before the paused-by-default change):
        # reset to paused=1 unless there's recent activity indicating an intentional resume.
        if state["paused"] == 0 and not state["last_tick_at"]:
            state["paused"] = 1
        st.set_service_state(self.store, paused=state["paused"], started_at=_now())
        st.sync_config(self.store, CONFIG_CSV)
        self.run_now_event = asyncio.Event()
        self.run_now_assets: Optional[List[str]] = None
        self.tick_lock = asyncio.Lock()
        self.tick_in_progress = False
        # API response cache: avoids hitting v_asset_now on every 5-second browser poll.
        self.api_cache = _TTLCache(ttl=api_cache_ttl)
        # Simulator integration — lazy import so ACM starts even if sim deps are missing
        try:
            from sim.sim_adapter import SimAdapter
            from scripts.acm_sim_routes import set_adapter, set_store as _set_sim_store
            self.sim = SimAdapter()
            set_adapter(self.sim)
            _svc = self
            def _run_now_cb(asset_key: str) -> None:
                _svc.run_now_assets = [asset_key]
                _svc.run_now_event.set()
            _set_sim_store(self.store, _run_now_cb)
        except Exception as _sim_err:
            print(f"[sim] Simulator module unavailable: {_sim_err}", flush=True)
            self.sim = None
        # Migrate: add fast_track column if not present
        try:
            self.store.execute(
                f"ALTER TABLE {self.store.t('monitored_assets')} "
                f"ADD COLUMN fast_track INTEGER DEFAULT 0"
            )
            self.store.commit()
        except Exception:
            pass  # Column already exists

    # ----------------------------------------------------------- registry --
    def monitored(self, include_retired: bool = False) -> List[dict]:
        sql = f"SELECT * FROM {self.store.t('monitored_assets')}"
        if not include_retired:
            sql += " WHERE retired_at IS NULL"
        return self.store.fetch(sql)

    def set_asset_state(self, asset_key: str, state: str, detail: str = "") -> None:
        self.store.execute(
            f"UPDATE {self.store.t('monitored_assets')} SET state = ?, state_detail = ? "
            f"WHERE asset_key = ?", (state, detail[:250], asset_key))
        self.store.commit()

    # ---------------------------------------------------------------- tick --
    async def tick_once(self, asset_keys: Optional[List[str]] = None) -> dict:
        """One tick: ingest -> gate -> score -> store. Never overlaps itself."""
        async with self.tick_lock:
            self.tick_in_progress = True
            try:
                return await self._tick_body(asset_keys)
            finally:
                self.tick_in_progress = False

    async def _tick_body(self, asset_keys: Optional[List[str]]) -> dict:
        t0 = time.time()
        rows = [r for r in self.monitored() if r["enabled"]]
        if asset_keys is not None:
            rows = [r for r in rows if r["asset_key"] in asset_keys]
        specs = {
            r["asset_key"]: SourceSpec(
                asset_key=r["asset_key"], source_kind=r["source_kind"],
                source_ref=r["source_ref"], conn_ref=r["conn_ref"],
                timestamp_col=r["timestamp_col"] or "time_stamp",
                status_col=r["status_col"]) for r in rows
        }
        groups = {r["asset_key"]: r["grp"] or "fleet" for r in rows}
        fast_track_map = {r["asset_key"]: bool(r.get("fast_track", 0)) for r in rows}
        counts = {"ingested": 0, "scored": 0, "skipped": 0, "errors": 0}

        # Ensure OPC UA bridge is running when any asset uses it
        opcua_specs = [s for s in specs.values() if s.source_kind == "opcua"]
        if opcua_specs:
            try:
                from scripts.acm_opcua_bridge import get_or_start as _opcua_start
                s = opcua_specs[0]
                endpoint = s.source_ref or "opc.tcp://localhost:4840/simulator"
                await _opcua_start(
                    endpoint=endpoint,
                    db_path=Path(s.conn_ref) if s.conn_ref else None,
                )
            except Exception:
                pass  # bridge startup failure is non-fatal; feed returns empty until connected

        # Ensure MQTT bridge is running when any asset uses it
        mqtt_specs = [s for s in specs.values() if s.source_kind == "mqtt"]
        if mqtt_specs:
            try:
                from scripts.acm_mqtt_bridge import get_or_start as _mqtt_start
                s = mqtt_specs[0]
                host, _, port_str = (s.source_ref or "localhost:1883").partition(":")
                _mqtt_start(
                    host=host or "localhost",
                    port=int(port_str or 1883),
                    db_path=Path(s.conn_ref) if s.conn_ref else None,
                )
            except Exception:
                pass  # bridge startup failure is non-fatal; feed will return empty

        # Phase A+B: incremental pull (thread-parallel I/O) + readiness gate
        keys_list = list(specs)
        infos = await asyncio.gather(
            *(asyncio.to_thread(update_cache, specs[k], self.cache_dir,
                                self.train_window_days) for k in keys_list),
            return_exceptions=True)
        ready: List[str] = []
        now = pd.Timestamp.now(tz="UTC")
        for key, info in zip(keys_list, infos):
            if isinstance(info, BaseException):
                msg = f"ingest: {type(info).__name__}: {info}"
                self.set_asset_state(key, "ERROR", msg)
                st.record_run_error(self.store, f"{groups[key]}/{key}", msg)
                counts["errors"] += 1
                continue
            counts["ingested"] += 1
            # CSV assets are static files — the staleness clock is meaningless
            # for historical data (CARE timestamps are years old). Only live
            # sources (opcua / mqtt) need the staleness gate.
            stale_hrs = (float("inf") if specs[key].source_kind == "csv"
                         else self.stale_after_hours)
            state = readiness(info.span_days, info.last_ts, now,
                              self.min_train_days, stale_hrs,
                              fast_track=fast_track_map.get(key, False))
            if state == "READY":
                ready.append(key)
            else:
                detail = (f"history span {info.span_days:.1f} d, need "
                          f"{self.min_train_days:.0f} d" if state == "MATURING"
                          else f"no data since {info.last_ts}")
                self.set_asset_state(key, state, detail)
                counts["skipped"] += 1

        # Phase C: parallel stateless re-learn + score. Spawn, not fork:
        # the parent runs Polars/BLAS thread pools, and forking a threaded
        # process deadlocks children on inherited mutexes. Spawn is also
        # exactly what Windows does — one behaviour everywhere.
        outputs: List[dict] = []
        if ready:
            loop = asyncio.get_running_loop()
            with ProcessPoolExecutor(max_workers=self.workers,
                                     mp_context=mp.get_context("spawn")) as pool:
                futs = [loop.run_in_executor(
                            pool, score_cached,
                            str(cache_path(self.cache_dir, k)),
                            specs[k].to_dict(), self.score_days)
                        for k in ready]
                outputs = list(await asyncio.gather(*futs))

        # Phase D: serial ingest in the parent (single store writer)
        for o in outputs:
            key = o["asset_key"]
            store_key = f"{groups[key]}/{key}"
            if "error" in o:
                self.set_asset_state(key, "ERROR", o["error"])
                st.record_run_error(self.store, store_key, o["error"])
                counts["errors"] += 1
                continue
            res = o["result"]
            st.ingest_result(self.store, groups[key], key, res, keep_history=True)
            alarm = bool(res.decision.alarm.any())
            self.set_asset_state(key, "ALARM" if alarm else "OK",
                                 res.decision.rule_fired or "")
            self.store.execute(
                f"UPDATE {self.store.t('monitored_assets')} "
                f"SET last_run_at = ?, last_score_ts = ?, last_runtime_s = ? "
                f"WHERE asset_key = ?",
                (_now(), str(res.ts[-1]), float(res.runtime_s), key))
            self.store.commit()
            counts["scored"] += 1

        st.set_service_state(self.store, last_tick_at=_now(),
                             last_tick_duration_s=round(time.time() - t0, 1))
        st.prune_history(self.store, self.retention_days)
        # Asset states changed — flush all cached API responses.
        self.api_cache.clear()
        return counts

    async def loop(self) -> None:
        """The service heartbeat. Tick interval and pause state are re-read
        from the store every cycle so panel changes apply immediately."""
        while True:
            state = st.get_service_state(self.store)
            if not state["paused"]:
                keys, self.run_now_assets = self.run_now_assets, None
                try:
                    counts = await self.tick_once(keys)
                    print(f"[tick] {_now()} {counts}", flush=True)
                except Exception as e:
                    print(f"[tick] {_now()} FAILED: {type(e).__name__}: {e}", flush=True)
            try:
                await asyncio.wait_for(self.run_now_event.wait(),
                                       timeout=state["tick_minutes"] * 60.0)
            except asyncio.TimeoutError:
                pass
            self.run_now_event.clear()


# ------------------------------------------------------------------- app --
def create_app(backend: str = "sqlite", db: Optional[str] = "acm_results.db",
               conn_str: Optional[str] = None, run_scheduler: bool = True,
               api_cache_ttl: float = 30.0) -> FastAPI:
    svc = Service(backend, db, conn_str, api_cache_ttl=api_cache_ttl)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if svc.sim:
            await svc.sim.start()
        task = asyncio.create_task(svc.loop()) if run_scheduler else None
        yield
        if task:
            task.cancel()
        if svc.sim:
            await svc.sim.stop()
        svc.store.close()

    app = FastAPI(title="ACM — Asset Condition Monitor", lifespan=lifespan)
    app.state.service = svc
    s = svc.store

    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/docs", StaticFiles(directory=str(ROOT / "docs")), name="docs")
    try:
        from scripts.acm_sim_routes import router as sim_router
        app.include_router(sim_router)
    except Exception as _sim_err:
        print(f"[sim] Simulator routes unavailable: {_sim_err}", flush=True)

    # ------------------------------------------------------------- fleet --
    @app.get("/api/fleet/sparklines")
    async def sparklines(days: int = 30):
        """Per-asset daily fused_max — compact sparkline material."""
        cache_key = f"sparklines:{days}"
        hit = svc.api_cache.get(cache_key)
        if hit is not _MISS:
            return hit
        rows = s.fetch(f"SELECT asset_key, day, fused_max FROM {s.t('v_daily_stats')} "
                       f"ORDER BY asset_key, day")
        out: dict = {}
        for r in rows:
            out.setdefault(r["asset_key"], []).append(
                [str(r["day"]), float(r["fused_max"]) if r["fused_max"] is not None else None])
        result = {k: v[-days:] for k, v in out.items()}
        svc.api_cache.put(cache_key, result)
        return result

    @app.get("/api/fleet")
    async def fleet():
        hit = svc.api_cache.get("fleet")
        if hit is not _MISS:
            return hit
        scored = s.fetch(f"SELECT * FROM {s.t('v_asset_now')}")
        have = {r["asset_key"] for r in scored}
        # Monitored assets with no results yet (NEW/MATURING/ERROR) still
        # belong on the operator's board.
        for m in svc.monitored():
            key = f"{m['grp'] or 'fleet'}/{m['asset_key']}"
            if key not in have:
                scored.append({"asset_key": key, "farm": m["grp"], "asset_id": None,
                               "verdict": None, "rules_fired": None,
                               "state": m["state"], "enabled": m["enabled"],
                               "last_run_at": m["last_run_at"], "last_ts": None,
                               "last_fused": None, "alarm_episodes": 0,
                               "unacked_alarms": 0, "last_alarm_end": None,
                               "state_detail": m["state_detail"]})
        svc.api_cache.put("fleet", scored)
        return scored

    # ------------------------------------------------------------- asset --
    def _asset_or_404(key: str) -> dict:
        rows = s.fetch(f"SELECT * FROM {s.t('assets')} WHERE asset_key = ?", (key,))
        if not rows:
            raise HTTPException(404, f"unknown asset '{key}'")
        return rows[0]

    @app.get("/api/assets/{key:path}/series")
    async def series(key: str, days: float = 30.0, max_points: int = 4000):
        _asset_or_404(key)
        rows = s.fetch(f"SELECT * FROM {s.t('scores')} WHERE asset_key = ? "
                       f"ORDER BY ts", (key,))
        if days > 0 and rows:
            cutoff = str(pd.Timestamp(rows[-1]["ts"]) - pd.Timedelta(days=days))
            rows = [r for r in rows if str(r["ts"]) >= cutoff]
        stride = max(1, len(rows) // max(max_points, 100))
        rows = rows[::stride]
        cols = ["ts", "fused", *st.Z_COLS, "status", "alarm"]
        return {"asset_key": key, "stride": stride,
                "columns": cols,
                "rows": [[str(r["ts"])] + [r[c] for c in cols[1:]] for r in rows]}

    @app.get("/api/assets/{key:path}/alarms")
    async def alarms(key: str):
        return s.fetch(f"SELECT * FROM {s.t('alarms')} WHERE asset_key = ? "
                       f"ORDER BY start_ts DESC", (key,))

    @app.get("/api/assets/{key:path}/daily")
    async def daily(key: str):
        return s.fetch(f"SELECT * FROM {s.t('v_daily_stats')} WHERE asset_key = ? "
                       f"ORDER BY day DESC", (key,))

    @app.get("/api/assets/{key:path}/runs")
    async def runs(key: str, limit: int = 50):
        rows = s.fetch(f"SELECT * FROM {s.t('runs')} WHERE asset_key = ? "
                       f"ORDER BY started_at DESC", (key,))
        return rows[:limit]

    @app.get("/api/assets/{key:path}/runlog")
    async def runlog(key: str, level: Optional[str] = None, limit: int = 500):
        rows = s.fetch(f"SELECT * FROM {s.t('run_log')} WHERE asset_key = ? "
                       f"ORDER BY ts DESC", (key,))
        if level:
            rows = [r for r in rows if r["level"] == level]
        return rows[:limit]

    @app.get("/api/assets/{key:path}")
    async def asset(key: str):
        a = _asset_or_404(key)
        bare = key.split("/", 1)[-1]
        m = s.fetch(f"SELECT * FROM {s.t('monitored_assets')} WHERE asset_key = ?", (bare,))
        return {"asset": a, "monitored": m[0] if m else None}

    # ------------------------------------------------------------- alarms --
    @app.get("/api/alarms")
    async def all_alarms(unacked: bool = False, limit: int = 200):
        sql = f"SELECT * FROM {s.t('alarms')}"
        if unacked:
            sql += " WHERE ack_at IS NULL"
        sql += " ORDER BY start_ts DESC"
        return s.fetch(sql)[:limit]

    @app.post("/api/alarms/ack")
    async def ack(body: dict):
        for f in ("asset_key", "start_ts", "ack_by"):
            if not body.get(f):
                raise HTTPException(422, f"'{f}' is required")
        n = st.ack_alarm(s, body["asset_key"], body["start_ts"],
                         body["ack_by"], body.get("note", ""))
        if n == 0:
            raise HTTPException(404, "no matching alarm episode")
        svc.api_cache.drop("fleet")  # unacked count changed
        return {"acked": n}

    # ----------------------------------------------------------- registry --
    @app.get("/api/monitored-assets")
    async def monitored(include_retired: bool = False):
        return svc.monitored(include_retired)

    @app.post("/api/monitored-assets")
    async def onboard(body: dict):
        for f in ("asset_key", "source_kind", "source_ref"):
            if not body.get(f):
                raise HTTPException(422, f"'{f}' is required")
        spec = SourceSpec(
            asset_key=body["asset_key"], source_kind=body["source_kind"],
            source_ref=body["source_ref"], conn_ref=body.get("conn_ref"),
            timestamp_col=body.get("timestamp_col", "time_stamp"),
            status_col=body.get("status_col"))
        # Validate the source NOW with a real read — a bad source must fail
        # onboarding, not the next tick.
        try:
            probe = await asyncio.to_thread(load_increment, spec, None)
        except Exception as e:
            raise HTTPException(422, f"source validation failed: {e}")
        if not len(probe):
            raise HTTPException(422, "source validation failed: no rows")
        existing = s.fetch(f"SELECT asset_key FROM {s.t('monitored_assets')} "
                           f"WHERE asset_key = ?", (spec.asset_key,))
        if existing:
            raise HTTPException(409, f"asset '{spec.asset_key}' already exists")
        s.execute(
            f"INSERT INTO {s.t('monitored_assets')} "
            f"(asset_key, grp, enabled, source_kind, source_ref, conn_ref, "
            f" timestamp_col, status_col, added_at, state, fast_track) "
            f"VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (spec.asset_key, body.get("grp", "fleet"), 1, spec.source_kind,
             spec.source_ref, spec.conn_ref, spec.timestamp_col, spec.status_col,
             _now(), "NEW", 1 if body.get("fast_track") else 0))
        s.commit()
        svc.api_cache.drop("fleet")
        return {"asset_key": spec.asset_key, "state": "NEW", "probe_rows": len(probe)}

    @app.patch("/api/monitored-assets/{key:path}")
    async def edit_asset(key: str, body: dict):
        allowed = {"enabled", "source_kind", "source_ref", "conn_ref",
                   "timestamp_col", "status_col", "grp", "state_detail"}
        fields = {k: v for k, v in body.items() if k in allowed}
        if not fields:
            raise HTTPException(422, f"nothing to update (allowed: {sorted(allowed)})")
        if "enabled" in fields:
            fields["enabled"] = 1 if fields["enabled"] else 0
        sets = ", ".join(f"{k} = ?" for k in fields)
        cur = s.con.cursor()
        cur.execute(f"UPDATE {s.t('monitored_assets')} SET {sets} WHERE asset_key = ?",
                    (*fields.values(), key))
        if cur.rowcount == 0:
            raise HTTPException(404, f"unknown asset '{key}'")
        if fields.get("enabled") == 0:
            svc.set_asset_state(key, "PAUSED", "monitoring disabled")
        s.commit()
        svc.api_cache.drop("fleet")
        return {"updated": sorted(fields)}

    @app.delete("/api/monitored-assets/{key:path}")
    async def retire(key: str):
        cur = s.con.cursor()
        cur.execute(f"UPDATE {s.t('monitored_assets')} SET retired_at = ?, enabled = 0 "
                    f"WHERE asset_key = ?", (_now(), key))
        if cur.rowcount == 0:
            raise HTTPException(404, f"unknown asset '{key}'")
        s.commit()
        svc.api_cache.drop("fleet")
        return {"retired": key}

    # ------------------------------------------------------------- config --
    @app.get("/api/config")
    async def config():
        return s.fetch(f"SELECT * FROM {s.t('config')} ORDER BY category, param_path")

    @app.put("/api/config")
    async def put_config(body: dict):
        for f in ("category", "param_path", "value", "changed_by"):
            if body.get(f) in (None, ""):
                raise HTTPException(422, f"'{f}' is required")
        cat = body["category"]
        if cat not in EDITABLE_CATEGORIES:
            raise HTTPException(
                422, f"category '{cat}' is not editable: ML behaviour is code, "
                     f"not configuration (editable: {sorted(EDITABLE_CATEGORIES)})")
        rows = s.fetch(f"SELECT param_value, value_type FROM {s.t('config')} "
                       f"WHERE category = ? AND param_path = ?", (cat, body["param_path"]))
        if not rows:
            raise HTTPException(404, f"unknown param {cat}.{body['param_path']}")
        old_value, value_type = rows[0]["param_value"], rows[0]["value_type"]
        value = body["value"]
        try:
            if value_type == "int":
                value = int(value)
            elif value_type == "float":
                value = float(value)
            elif value_type == "bool":
                value = str(value).lower() in ("true", "1", "yes")
        except (TypeError, ValueError):
            raise HTTPException(422, f"value '{value}' is not a valid {value_type}")
        cfg = _cfg()
        note = body.get("note", "")
        cfg.update_param(f"{cat}.{body['param_path']}", value,
                         reason=note or "panel edit", updated_by=body["changed_by"])
        st.sync_config(s, CONFIG_CSV)
        s.execute(f"INSERT INTO {s.t('config_audit')} VALUES (?,?,?,?,?,?,?)",
                  (_now(), body["changed_by"], cat, body["param_path"],
                   str(old_value), str(value), note))
        s.commit()
        return {"updated": f"{cat}.{body['param_path']}", "old": old_value,
                "new": str(value)}

    @app.get("/api/config/audit")
    async def config_audit(limit: int = 200):
        rows = s.fetch(f"SELECT * FROM {s.t('config_audit')} ORDER BY changed_at DESC")
        return rows[:limit]

    # ------------------------------------------------------------ service --
    @app.get("/api/service")
    async def service_status():
        # Service status is polled frequently; cache it but with a short TTL
        # because tick_in_progress changes within a tick cycle.
        hit = svc.api_cache.get("service")
        if hit is not _MISS and not svc.tick_in_progress:
            return hit
        state = st.get_service_state(s)
        errors = s.fetch(f"SELECT asset_key, state, state_detail FROM "
                         f"{s.t('monitored_assets')} WHERE state IN ('ERROR','STALE') "
                         f"AND retired_at IS NULL")
        runtimes = s.fetch(f"SELECT asset_key, last_run_at, last_runtime_s FROM "
                           f"{s.t('monitored_assets')} WHERE retired_at IS NULL "
                           f"AND last_runtime_s IS NOT NULL")
        next_eta = None
        if state["last_tick_at"] and not state["paused"]:
            next_eta = str(pd.Timestamp(state["last_tick_at"])
                           + pd.Timedelta(minutes=state["tick_minutes"]))
        result = {**state, "tick_in_progress": svc.tick_in_progress,
                  "next_tick_eta": next_eta, "attention": errors,
                  "runtimes": runtimes, "workers": svc.workers,
                  "cache_dir": str(svc.cache_dir), "backend": svc.backend}
        if not svc.tick_in_progress:
            svc.api_cache.put("service", result)
        return result

    @app.post("/api/service/pause")
    async def pause():
        st.set_service_state(s, paused=1)
        svc.api_cache.drop("service")
        return {"paused": True}

    @app.post("/api/service/resume")
    async def resume():
        st.set_service_state(s, paused=0)
        svc.api_cache.drop("service")
        svc.run_now_event.set()
        return {"paused": False}

    @app.put("/api/service/tick")
    async def set_tick(body: dict):
        try:
            minutes = int(body.get("tick_minutes"))
        except (TypeError, ValueError):
            raise HTTPException(422, "tick_minutes must be an integer")
        if minutes < 1:
            raise HTTPException(422, "tick_minutes must be >= 1")
        st.set_service_state(s, tick_minutes=minutes)
        svc.api_cache.drop("service")
        return {"tick_minutes": minutes}

    @app.post("/api/service/run-now")
    async def run_now(body: Optional[dict] = None):
        keys = (body or {}).get("assets")
        if keys:
            known = {r["asset_key"] for r in svc.monitored()}
            bad = [k for k in keys if k not in known]
            if bad:
                raise HTTPException(404, f"unknown assets: {bad}")
        svc.run_now_assets = keys
        svc.run_now_event.set()
        return {"triggered": keys or "all"}

    @app.post("/api/service/update")
    async def update_acm():
        """Pull latest code and refresh asset registrations without restarting."""
        import subprocess
        lines: list[str] = []

        async def _run(cmd: list[str], label: str) -> bool:
            try:
                result = await asyncio.to_thread(
                    subprocess.run, cmd,
                    capture_output=True, text=True, cwd=str(ROOT), timeout=120,
                )
                for ln in (result.stdout + result.stderr).splitlines():
                    if ln.strip():
                        lines.append(ln)
                return result.returncode == 0
            except Exception as exc:
                lines.append(f"{label} failed: {exc}")
                return False

        lines.append("── Pulling latest code ──────────────────")
        await _run(["git", "pull", "--ff-only"], "git pull")

        lines.append("── Refreshing asset registrations ───────")
        care_dir = ROOT / "sim_data" / "sample"
        if any(care_dir.glob("care_farm[ABC]_*.csv")):
            await _run([sys.executable, "scripts/acm_seed_demo.py",
                        "--care-dir", str(care_dir), "--db", svc.db or "acm_results.db"],
                       "seed")
        else:
            lines.append("No CARE CSVs found in sim_data/sample/ — skipping seed")

        lines.append("── Done — restart the service to apply code changes ──")
        return {"lines": lines, "restart_required": True}

    return app


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=["sqlite", "mssql"], default="sqlite")
    ap.add_argument("--db", default="acm_results.db")
    ap.add_argument("--conn", default=None, help="pyodbc connection string (mssql)")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    args = ap.parse_args()

    import uvicorn
    app = create_app(args.backend, db=args.db, conn_str=args.conn)
    svc = app.state.service
    host = args.host or svc._host
    port = args.port or svc._port
    _startup_banner(host, port, args.backend, args.db)
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

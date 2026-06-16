#!/usr/bin/env python3
"""Simulator API routes — /api/sim/* — mounted into ACM's FastAPI app."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException, UploadFile, File

from sim.generator_registry import get_generator, list_generators
from sim.models import GenerateRequest, ReplayConfig
import sim.csv_manager as csv_mgr

router = APIRouter(prefix="/api/sim", tags=["simulator"])

_adapter: Any = None
_store: Any = None
_run_now_cb = None


def set_adapter(adapter: Any) -> None:
    global _adapter
    _adapter = adapter


def set_store(store: Any, run_now_cb=None) -> None:
    global _store, _run_now_cb
    _store = store
    _run_now_cb = run_now_cb


def _require_adapter():
    if _adapter is None:
        raise HTTPException(503, "Simulator not initialised")
    return _adapter


def _register_opcua_in_acm() -> None:
    """UPSERT simulator/opc_ua into monitored_assets and trigger a run-now tick."""
    if _store is None:
        return
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    _store.execute(
        "INSERT INTO monitored_assets "
        "(asset_key, grp, enabled, source_kind, source_ref, conn_ref, "
        "timestamp_col, status_col, added_at, state, fast_track) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(asset_key) DO UPDATE SET "
        "  source_ref = excluded.source_ref, "
        "  enabled    = 1, "
        "  state      = CASE WHEN state IN ('ERROR','STALE') THEN 'NEW' ELSE state END",
        (
            "simulator/opc_ua", "simulator", 1, "opcua",
            "opc.tcp://localhost:4840/simulator",
            None, "published_at", None, now, "NEW", 1,
        ),
    )
    _store.commit()
    if _run_now_cb is not None:
        _run_now_cb("simulator/opc_ua")


@router.get("/generators")
async def list_gens():
    return [g.model_dump() for g in list_generators()]


@router.get("/generators/{domain_id}/spec")
async def gen_spec(domain_id: str):
    try:
        g = get_generator(domain_id)
    except KeyError:
        raise HTTPException(404, f"Unknown generator: {domain_id}")
    return g.get_spec().model_dump()


@router.post("/generators/{domain_id}/generate")
async def generate(domain_id: str, body: dict):
    try:
        get_generator(domain_id)
    except KeyError:
        raise HTTPException(404, f"Unknown generator: {domain_id}")
    backdate = body.pop("backdate", True)
    backdate_days = int(body.pop("backdate_days", 45))
    try:
        req = GenerateRequest(**{k: v for k, v in body.items()
                                  if k in GenerateRequest.model_fields})
    except Exception as e:
        raise HTTPException(422, str(e))
    adp = _require_adapter()
    try:
        resp = await adp.generate(domain_id, req, backdate=backdate, backdate_days=backdate_days)
    except Exception as e:
        raise HTTPException(422, str(e))
    return resp.model_dump()


@router.get("/files")
async def list_files():
    try:
        return [f.model_dump() for f in csv_mgr.list_files()]
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/files/{filename}/metadata")
async def file_metadata(filename: str, source: str = "generated"):
    try:
        return csv_mgr.metadata(filename, source).model_dump()
    except FileNotFoundError:
        raise HTTPException(404, f"File not found: {filename}")
    except Exception as e:
        raise HTTPException(422, str(e))


@router.delete("/files/{filename}")
async def delete_file(filename: str, source: str = "generated"):
    try:
        return csv_mgr.delete_file(filename, source)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except FileNotFoundError:
        raise HTTPException(404, f"File not found: {filename}")


def _detect_timestamp_col(columns: list[str]) -> str:
    """Pick the most likely timestamp column from a list of column names."""
    for p in ("timestamp", "time_stamp", "ts"):
        if p in columns:
            return p
    for c in columns:
        if "time" in c.lower() or "date" in c.lower():
            return c
    return columns[0] if columns else "timestamp"


@router.post("/files/{filename}/register")
async def register_file_as_acm_asset(filename: str, source: str, body: dict):
    """Register an existing SIM CSV/XLSX file as an ACM monitored asset.

    The backend resolves the absolute path and auto-detects the timestamp
    column so the frontend doesn't need to know either.
    """
    if _store is None:
        raise HTTPException(503, "ACM store not initialised")

    try:
        path = csv_mgr.resolve_csv_path(filename, source)
    except FileNotFoundError:
        raise HTTPException(404, f"File not found: {filename}")
    except ValueError as e:
        raise HTTPException(422, str(e))

    try:
        meta = csv_mgr.metadata(filename, source, preview_rows=1)
    except Exception as e:
        raise HTTPException(422, f"Could not read file metadata: {e}")

    ts_col = _detect_timestamp_col(meta.columns)

    asset_key = (body.get("asset_key") or "").strip()
    if not asset_key:
        raise HTTPException(422, "'asset_key' is required")

    grp = body.get("grp") or "sim"
    fast_track = bool(body.get("fast_track", True))

    existing = _store.fetch(
        "SELECT asset_key FROM monitored_assets WHERE asset_key = ?", (asset_key,)
    )
    if existing:
        raise HTTPException(409, f"asset '{asset_key}' already exists")

    source_ref = str(path)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    _store.execute(
        "INSERT INTO monitored_assets "
        "(asset_key, grp, enabled, source_kind, source_ref, conn_ref, "
        "timestamp_col, status_col, added_at, state, fast_track) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (asset_key, grp, 1, "csv", source_ref, None,
         ts_col, None, now, "NEW", 1 if fast_track else 0),
    )
    _store.commit()
    return {
        "asset_key": asset_key,
        "state": "NEW",
        "source_ref": source_ref,
        "timestamp_col": ts_col,
    }


@router.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        meta = csv_mgr.save_upload(file)
        return meta.model_dump()
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/status")
async def sim_status():
    adp = _require_adapter()
    return adp.get_status()


@router.post("/replay/configure")
async def configure_replay(body: dict):
    adp = _require_adapter()
    publisher_mode = body.pop("publisher_mode", "buffer")
    try:
        config = ReplayConfig(**body)
    except Exception as e:
        raise HTTPException(422, str(e))
    try:
        result = await adp.configure_replay(config, publisher_mode=publisher_mode)
        return result
    except Exception as e:
        raise HTTPException(422, str(e))


@router.post("/replay/start")
async def start_replay():
    adp = _require_adapter()
    try:
        result = await adp.start_replay()
    except Exception as e:
        raise HTTPException(422, str(e))
    try:
        mode = adp.get_status().get("publisher_mode", "")
        if mode in ("opcua", "both"):
            _register_opcua_in_acm()
    except Exception:
        pass  # non-fatal — replay works even if ACM registration fails
    return result


@router.post("/replay/stop")
async def stop_replay():
    adp = _require_adapter()
    return await adp.stop_replay()


@router.post("/replay/restart")
async def restart_replay():
    adp = _require_adapter()
    try:
        result = await adp.restart_replay()
    except Exception as e:
        raise HTTPException(422, str(e))
    try:
        mode = adp.get_status().get("publisher_mode", "")
        if mode in ("opcua", "both"):
            _register_opcua_in_acm()
    except Exception:
        pass
    return result


@router.get("/replay/current-values")
async def current_values():
    adp = _require_adapter()
    return adp.get_current_values().model_dump()


@router.post("/onboard")
async def sim_onboard(body: dict):
    adp = _require_adapter()
    domain_id = body.get("domain_id")
    if not domain_id:
        raise HTTPException(422, "'domain_id' is required")
    asset_key = body.get("asset_key")
    if not asset_key:
        raise HTTPException(422, "'asset_key' is required")
    req_data = body.get("request", {})
    backdate = body.get("backdate", True)
    backdate_days = int(body.get("backdate_days", 45))
    try:
        get_generator(domain_id)
    except KeyError:
        raise HTTPException(404, f"Unknown generator: {domain_id}")
    try:
        req = GenerateRequest(**req_data)
    except Exception as e:
        raise HTTPException(422, str(e))
    try:
        resp = await adp.generate(domain_id, req, backdate=backdate, backdate_days=backdate_days)
    except Exception as e:
        raise HTTPException(422, f"generation failed: {e}")
    source_ref = str(csv_mgr.GENERATED_DIR / resp.filename)
    return {
        "filename": resp.filename,
        "source_ref": source_ref,
        "row_count": resp.row_count,
        "columns": resp.columns,
        "suggested_onboard": {
            "asset_key": asset_key,
            "grp": body.get("grp", "sim"),
            "source_kind": "csv",
            "source_ref": source_ref,
            "timestamp_col": body.get("timestamp_col", "timestamp"),
            "fast_track": body.get("fast_track", False),
        }
    }

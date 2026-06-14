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


def set_adapter(adapter: Any) -> None:
    global _adapter
    _adapter = adapter


def _require_adapter():
    if _adapter is None:
        raise HTTPException(503, "Simulator not initialised")
    return _adapter


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
        return await adp.start_replay()
    except Exception as e:
        raise HTTPException(422, str(e))


@router.post("/replay/stop")
async def stop_replay():
    adp = _require_adapter()
    return await adp.stop_replay()


@router.post("/replay/restart")
async def restart_replay():
    adp = _require_adapter()
    try:
        return await adp.restart_replay()
    except Exception as e:
        raise HTTPException(422, str(e))


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

# utils/paths.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import json
import re


def _slug(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


@dataclass
class RunPaths:
    root: Path
    equip_dir: Path
    run_dir: Path
    models_dir: Path
    tables_dir: Path
    charts_dir: Path
    logs_dir: Path
    run_json: Path
    timers_log: Path
    run_ts: str


def make_run_paths(artifact_root: Path, equip: str, run_ts_format: str = "%Y%m%d_%H%M%S") -> RunPaths:
    """
    Create the standard ACM V5 folder tree and return a RunPaths dataclass.
    Matches the interface used by core/acm_main.py.
    """
    root = Path(artifact_root).expanduser().resolve()
    equip_dir = root / _slug(equip)
    run_ts = datetime.now().strftime(run_ts_format)
    run_dir = equip_dir / f"run_{run_ts}"
    models_dir = run_dir / "models"
    tables_dir = run_dir / "tables"
    charts_dir = run_dir / "charts"
    logs_dir = run_dir / "logs"

    for d in (equip_dir, run_dir, models_dir, tables_dir, charts_dir, logs_dir):
        d.mkdir(parents=True, exist_ok=True)

    return RunPaths(
        root=root,
        equip_dir=equip_dir,
        run_dir=run_dir,
        models_dir=models_dir,
        tables_dir=tables_dir,
        charts_dir=charts_dir,
        logs_dir=logs_dir,
        run_json=run_dir / "run.json",
        timers_log=logs_dir / "timings.jsonl",
        run_ts=run_ts,
    )


def write_run_header(path: Path, header: Dict[str, Any]) -> None:
    """
    Write (or overwrite) the run header JSON. Safe to call multiple times.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(header, indent=2), encoding="utf-8")


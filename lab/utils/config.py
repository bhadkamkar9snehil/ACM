# utils/config.py
from __future__ import annotations

import copy
import yaml
from pathlib import Path
from typing import Any, Dict

from core.observability import Console
from utils import validators


# ---------------- YAML loader ----------------
def load_config(path: Path | str) -> Dict[str, Any]:
    """Load YAML config safely; returns empty dict if missing."""
    p = Path(path)
    if not p.exists():
        Console.warn(f"Config file {p} not found; using empty defaults.")
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config format in {p}")
    return data


# ---------------- merge overrides ----------------
def merge_overrides(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge override dicts into base."""
    merged = copy.deepcopy(base)

    def _merge(a, b):
        for k, v in b.items():
            if isinstance(v, dict) and isinstance(a.get(k), dict):
                _merge(a[k], v)
            else:
                a[k] = v
    _merge(merged, overrides)
    return merged


# ---------------- validate ----------------
def validate_config(cfg: Dict[str, Any]) -> None:
    """Pass through a shared validator stub."""
    validators.validate_config_schema(cfg)

"""Config loading, defaults, and validation for ACM V5."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple
import copy
import yaml


# ---------------------------
# Default configuration (V5)
# ---------------------------
DEFAULTS: Dict[str, Any] = {
    "run": {
        "mode": "batch",                     # batch | stream (future use)
        "equip": None,                       # required
        "artifact_root": "artifacts",        # required
        "run_ts_format": "%Y%m%d_%H%M%S",
        "random_state": 17,
        "log_level": "INFO",
    },
    "data": {
        # Either provide explicit CSVs OR a data_dir to auto-discover “TRAIN/TEST” patterns.
        "train_csv": None,
        "score_csv": None,
        "data_dir": "data",
        "timestamp_col": None,               # auto-detect if None
        "tag_columns": [],                   # [] => auto-detect numerics
        "sampling_secs": 1,
        "max_rows": None,                    # optional row cap for debug
    },
    "clean": {
        "dropna_thresh": 0.7,                # keep columns with >=70% non-null
        "max_gap": 5,                        # interpolate up to N consecutive samples
        "spike_hampel_k": 3.0,               # Tukey/Hampel-like threshold (optional)
        "flatline_window": 50,               # samples to consider “stuck”
        "near_const_var_eps": 1e-9,          # drop near-constant tags
    },
    "features": {
        "window": 5,                         # rolling/window size in samples
        "fft_bands": [0.0, 0.1, 0.2, 0.5],   # normalized freq cutpoints (example)
        "top_k_tags": 5,
    },
    "models": {
        "pca": {"n_components": 0.9, "svd_solver": "randomized", "random_state": 17},
        "ar1": {"enabled": True, "smoothing": 1},
        "iforest": {"n_estimators": 300, "contamination": "auto", "random_state": 17},
        "gmm": {"enabled": False, "n_components": "auto"},
    },
    "fusion": {
        "weights": {"pca": 0.4, "ar1": 0.3, "iforest": 0.2, "gmm": 0.1},
        "cooldown": 10,                      # samples to keep episode latched
        "min_silent_gap": 10,                # min samples between episodes
        "per_regime": False,                 # enable per-regime thresholds
    },
    "thresholds": {
        "alert": 0.85,
        "warn": 0.70,
    },
    "drift": {
        "enable": True,
        "method": "corr_break",              # corr_break | ewma_cusum | rulsif
        "agree_boost_window": 10,            # samples for method agreement check
    },
    "report": {
        "enable": True,
        "theme": "default",
        "include_broken_pairs": True,
        "include_episode_bands": True,
        "max_points": 20000,                 # downsample cap for plotting
    },
}


# ---------------------------
# Helpers
# ---------------------------
def _deep_update(base: Dict[str, Any], upd: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively update dict `base` with `upd` (non-destructive: returns new dict)."""
    out = copy.deepcopy(base)
    for k, v in (upd or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_update(out[k], v)
        else:
            out[k] = v
    return out


def _require(condition: bool, msg: str) -> None:
    if not condition:
        raise ValueError(f"[CONFIG] {msg}")


def _path_exists_or_none(p: str | None) -> bool:
    return p is None or Path(p).expanduser().exists()


# ---------------------------
# Public API
# ---------------------------
def load_config(path: str | Path | None) -> Dict[str, Any]:
    """Load YAML config and validate, returning a fully-populated dict."""
    cfg_disk: Dict[str, Any] = {}
    if path:
        p = Path(path)
        _require(p.exists(), f"Config file not found: {p}")
        with p.open("r", encoding="utf-8") as fh:
            cfg_disk = yaml.safe_load(fh) or {}

    # Merge: disk over defaults
    cfg = _deep_update(DEFAULTS, cfg_disk)

    # --- Required fields
    _require(cfg["run"]["equip"], "run.equip is required")
    _require(cfg["run"]["artifact_root"], "run.artifact_root is required")

    # --- Data sources: either explicit CSVs OR an existing data_dir
    train_csv = cfg["data"].get("train_csv")
    score_csv = cfg["data"].get("score_csv")
    data_dir = cfg["data"].get("data_dir")

    if not train_csv and not score_csv:
        _require(
            data_dir and Path(data_dir).exists(),
            "Provide data.train_csv/data.score_csv OR ensure data.data_dir exists",
        )
    else:
        _require(_path_exists_or_none(train_csv), f"data.train_csv not found: {train_csv}")
        _require(_path_exists_or_none(score_csv), f"data.score_csv not found: {score_csv}")

    # --- Thresholds/fusion blocks must exist (after merge they always should)
    _require("alert" in cfg["thresholds"] and "warn" in cfg["thresholds"],
             "thresholds.alert and thresholds.warn are required")

    weights = cfg["fusion"].get("weights", {})
    _require(all(k in weights for k in ("pca", "ar1", "iforest", "gmm")),
             "fusion.weights must include keys: pca, ar1, iforest, gmm")

    # --- Cleanups: coerce some types
    if isinstance(cfg["features"].get("fft_bands"), list):
        cfg["features"]["fft_bands"] = sorted(float(x) for x in cfg["features"]["fft_bands"])

    # --- Sanity caps
    if cfg["report"]["max_points"] is not None:
        _require(cfg["report"]["max_points"] > 0, "report.max_points must be > 0")

    return cfg

# rust_bridge/ffi.py
from __future__ import annotations

import importlib
from typing import Any
import numpy as np

from .schema import BatchInput, BatchResult


def _try_import_rs(mod_name: str = "acm_rs"):
    """
    Try to import the Rust wheel built via maturin/pyo3.
    Return module or None if missing.
    """
    try:
        return importlib.import_module(mod_name)
    except Exception:
        return None


_RS = _try_import_rs()  # None means: Python fallback


# ---------------- Public API (stable) ----------------

def score_batch(input: BatchInput) -> BatchResult:
    """
    If Rust module is present, call its implementation; else return a minimal Python-constructed result.
    This keeps the core pipeline stable regardless of Rust availability.
    """
    matrix = np.asarray(input["matrix"], dtype=float)
    n_rows = int(matrix.shape[0])
    if _RS is not None and hasattr(_RS, "score_batch"):
        out = _RS.score_batch(input)  # Rust should return a dict matching BatchResult
        return out  # type: ignore[return-value]

    # ---- Python fallback (very light stub) ----
    # Provide empty scores so downstream fusion can still proceed.
    zeros = [0.0] * n_rows
    return {
        "equip": "",
        "run_ts": "",
        "n_rows": n_rows,
        "scores": {
            "fused_score": zeros,
            "pca_recon_err": zeros,
            "iforest_score": zeros,
            "ar1_residual": zeros,
        },
        "culprit_tags": [],
        "thresholds": {"alert": 0.85, "warn": 0.70},
    }


def train_pca(input: BatchInput) -> dict[str, Any]:
    """
    Optional: Rust PCA trainer for parity checks. Python path already trains PCA in core/train.py.
    """
    if _RS is not None and hasattr(_RS, "train_pca"):
        return _RS.train_pca(input)  # type: ignore[no-any-return]
    return {"ok": False, "reason": "rust module not available"}


def iforest_scores(input: BatchInput) -> list[float]:
    """
    Optional: Rust IsolationForest scorer. Python path already implemented.
    """
    if _RS is not None and hasattr(_RS, "iforest_scores"):
        return _RS.iforest_scores(input)  # type: ignore[no-any-return]
    n_rows = len(input.get("matrix", []))
    return [0.0] * n_rows

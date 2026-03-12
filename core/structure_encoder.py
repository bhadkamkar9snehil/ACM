"""
Shared structure encoding and basis construction for ACM.

This module extracts the tag-agnostic numeric surface and basis-building logic
from `core.regimes` without changing runtime semantics. It becomes the durable
owner of structure encoding while callers continue to route through existing
stage order and authority.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from core.observability import Console
from utils.config_dict import cfg_get as _cfg_get


_DEFAULT_SURFACE_MAX_COLS = 24
_DEFAULT_SURFACE_MIN_VALID_FRACTION = 0.60
_DEFAULT_SURFACE_MIN_IQR = 1e-6


def select_tag_agnostic_numeric_surface(
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    cfg: Optional[Dict[str, Any]] = None,
    *,
    max_cols: Optional[int] = None,
    min_valid_fraction: Optional[float] = None,
    min_iqr: Optional[float] = None,
) -> Tuple[List[str], pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Select a deterministic, tag-agnostic numeric surface shared by train and score.

    Selection policy:
    1. Keep columns present in both frames with numeric dtype in at least one frame.
    2. Require minimum finite fraction on the train frame.
    3. Rank remaining columns by train-frame IQR (descending, then name).
    4. Keep the top-N columns.

    The returned frames are numeric-only and coerced to float with inf -> NaN.
    Filling happens in the caller because different call sites may want different
    imputation semantics.
    """
    basis_cfg = _cfg_get(cfg or {}, "regimes.feature_basis", {}) or {}
    resolved_max_cols = (
        int(max_cols)
        if max_cols is not None
        else int(basis_cfg.get("max_cols", _DEFAULT_SURFACE_MAX_COLS))
    )
    resolved_min_valid_fraction = (
        float(min_valid_fraction)
        if min_valid_fraction is not None
        else float(basis_cfg.get("min_valid_fraction", _DEFAULT_SURFACE_MIN_VALID_FRACTION))
    )
    resolved_min_iqr = (
        float(min_iqr)
        if min_iqr is not None
        else float(basis_cfg.get("min_iqr", _DEFAULT_SURFACE_MIN_IQR))
    )

    common_cols = [col for col in train_df.columns if col in score_df.columns]
    numeric_cols = [
        col for col in common_cols
        if pd.api.types.is_numeric_dtype(train_df[col]) or pd.api.types.is_numeric_dtype(score_df[col])
    ]

    if not numeric_cols:
        empty = pd.DataFrame(index=train_df.index), pd.DataFrame(index=score_df.index)
        return [], empty[0], empty[1], {
            "surface_type": "tag_agnostic_numeric",
            "candidate_count": 0,
            "selected_count": 0,
            "min_valid_fraction": resolved_min_valid_fraction,
            "min_iqr": resolved_min_iqr,
            "max_cols": resolved_max_cols,
        }

    train_numeric = (
        train_df.reindex(columns=numeric_cols)
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
    )
    score_numeric = (
        score_df.reindex(columns=numeric_cols)
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
    )

    valid_fraction = train_numeric.notna().mean(axis=0)
    valid_cols = [
        col for col in numeric_cols
        if float(valid_fraction.get(col, 0.0)) >= resolved_min_valid_fraction
    ]

    if not valid_cols:
        return [], train_numeric.iloc[:, 0:0], score_numeric.iloc[:, 0:0], {
            "surface_type": "tag_agnostic_numeric",
            "candidate_count": len(numeric_cols),
            "selected_count": 0,
            "dropped_low_valid_count": len(numeric_cols),
            "dropped_low_iqr_count": 0,
            "min_valid_fraction": resolved_min_valid_fraction,
            "min_iqr": resolved_min_iqr,
            "max_cols": resolved_max_cols,
        }

    iqr = train_numeric[valid_cols].quantile(0.75) - train_numeric[valid_cols].quantile(0.25)
    iqr = iqr.astype(float).replace([np.inf, -np.inf], np.nan)
    variable_cols = [
        col for col in valid_cols
        if np.isfinite(iqr.get(col, np.nan)) and float(iqr[col]) > resolved_min_iqr
    ]
    ranked_cols = sorted(variable_cols, key=lambda col: (-float(iqr[col]), col))
    selected_cols = ranked_cols[:resolved_max_cols] if resolved_max_cols > 0 else ranked_cols

    meta = {
        "surface_type": "tag_agnostic_numeric",
        "candidate_count": len(numeric_cols),
        "selected_count": len(selected_cols),
        "dropped_low_valid_count": len(numeric_cols) - len(valid_cols),
        "dropped_low_iqr_count": len(valid_cols) - len(variable_cols),
        "min_valid_fraction": resolved_min_valid_fraction,
        "min_iqr": resolved_min_iqr,
        "max_cols": resolved_max_cols,
        "truncated": len(selected_cols) < len(ranked_cols),
        "selected_cols": list(selected_cols),
        "selection_metric": "train_iqr",
    }
    if selected_cols:
        meta["selected_iqr"] = {col: float(iqr[col]) for col in selected_cols}

    return (
        selected_cols,
        train_numeric.reindex(columns=selected_cols),
        score_numeric.reindex(columns=selected_cols),
        meta,
    )


def select_ewm_monitoring_surface(
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    cfg: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Select the explicit day-0 monitoring surface for EWM.

    Current contract:
    - raw numeric channels only
    - shared between train and score
    - tag-agnostic
    - no truncation cap by default (monitor every eligible channel)

    Missing values are preserved so score/update paths can skip non-finite rows
    rather than learn from imputed observations.
    """
    ewm_cfg = _cfg_get(cfg or {}, "models.ewm_baseline.surface", {}) or {}
    min_valid_fraction = float(
        ewm_cfg.get("min_valid_fraction", _DEFAULT_SURFACE_MIN_VALID_FRACTION)
    )
    min_iqr = float(ewm_cfg.get("min_iqr", _DEFAULT_SURFACE_MIN_IQR))
    selected_cols, train_numeric, score_numeric, meta = select_tag_agnostic_numeric_surface(
        train_df,
        score_df,
        cfg=cfg,
        max_cols=0,
        min_valid_fraction=min_valid_fraction,
        min_iqr=min_iqr,
    )
    meta = dict(meta)
    meta["surface_type"] = "ewm_monitoring_raw_numeric"
    meta["channel_semantics"] = "raw_numeric"
    meta["max_cols"] = 0
    return selected_cols, train_numeric, score_numeric, meta


def _compute_basis_signature(
    feature_columns: List[str],
    scaler_mean: Optional[List[float]],
    scaler_var: Optional[List[float]],
    n_pca: int,
) -> str:
    """Compute a deterministic signature for the active basis configuration."""
    sig_parts = [
        "cols:" + ",".join(sorted(feature_columns)),
        f"n_pca:{n_pca}",
    ]
    if scaler_mean is not None:
        sig_parts.append("mean:" + ",".join(f"{x:.6f}" for x in scaler_mean[:5]))
    if scaler_var is not None:
        sig_parts.append("var:" + ",".join(f"{x:.6f}" for x in scaler_var[:5]))

    sig_str = "|".join(sig_parts)
    return hashlib.md5(sig_str.encode()).hexdigest()[:16]


def build_feature_basis(
    train_features: pd.DataFrame,
    score_features: pd.DataFrame,
    raw_train: Optional[pd.DataFrame],
    raw_score: Optional[pd.DataFrame],
    pca_detector: Optional[Any],
    cfg: Dict[str, Any],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Construct the current compact tag-agnostic basis for regime clustering."""
    _ = pca_detector

    if raw_train is None or raw_score is None:
        raise ValueError("raw_train/raw_score are required for tag-agnostic regime basis construction")

    aligned_train = raw_train.reindex(train_features.index)
    aligned_score = raw_score.reindex(score_features.index)
    selected_cols, train_numeric, score_numeric, surface_meta = select_tag_agnostic_numeric_surface(
        aligned_train,
        aligned_score,
        cfg=cfg,
    )

    if not selected_cols:
        raise ValueError(
            "No adequate tag-agnostic numeric regime surface found "
            f"(candidates={surface_meta.get('candidate_count', 0)}, "
            f"dropped_low_valid={surface_meta.get('dropped_low_valid_count', 0)}, "
            f"dropped_low_iqr={surface_meta.get('dropped_low_iqr_count', 0)})"
        )

    if surface_meta.get("truncated"):
        Console.info(
            f"Regime basis selected top {len(selected_cols)} tag-agnostic numeric columns "
            f"from {surface_meta.get('candidate_count', len(selected_cols))} candidates",
            component="REGIME",
            selected_count=len(selected_cols),
            candidate_count=surface_meta.get("candidate_count", len(selected_cols)),
        )
    else:
        Console.info(
            f"Regime basis using {len(selected_cols)} tag-agnostic numeric columns: "
            f"{selected_cols[:5]}{'...' if len(selected_cols) > 5 else ''}",
            component="REGIME",
        )

    fill_values = train_numeric.median(axis=0, numeric_only=True)
    train_basis = train_numeric.ffill().bfill().fillna(fill_values).fillna(0.0)
    score_basis = score_numeric.ffill().bfill().fillna(fill_values).fillna(0.0)

    all_cols = list(selected_cols)
    basis_scaler = StandardScaler()
    basis_scaler.fit(train_basis[all_cols].values)
    train_basis = train_basis.astype({c: "float64" for c in all_cols})
    score_basis = score_basis.astype({c: "float64" for c in all_cols})
    train_basis[all_cols] = basis_scaler.transform(train_basis[all_cols].values)
    score_basis[all_cols] = basis_scaler.transform(score_basis[all_cols].values)

    mean_vec_list: Optional[List[float]] = None
    var_vec_list: Optional[List[float]] = None
    if hasattr(basis_scaler, "mean_") and basis_scaler.mean_ is not None:
        mean_vec_list = [float(x) for x in basis_scaler.mean_]
    if hasattr(basis_scaler, "var_") and basis_scaler.var_ is not None:
        var_vec_list = [float(x) for x in basis_scaler.var_]
    basis_signature = _compute_basis_signature(all_cols, mean_vec_list, var_vec_list, 0)

    meta = {
        "n_pca": 0,
        "raw_tags": list(selected_cols),
        "fallback_cols": list(train_basis.columns),
        "basis_normalized": True,
        "basis_signature": basis_signature,
        "feature_surface_type": "tag_agnostic_numeric",
        "surface_meta": surface_meta,
    }
    if hasattr(basis_scaler, "mean_"):
        meta["basis_scaler_mean"] = mean_vec_list
    if hasattr(basis_scaler, "var_"):
        meta["basis_scaler_var"] = var_vec_list
    meta["basis_scaler_cols"] = all_cols
    return train_basis, score_basis, meta


__all__ = [
    "_compute_basis_signature",
    "build_feature_basis",
    "select_ewm_monitoring_surface",
    "select_tag_agnostic_numeric_surface",
]

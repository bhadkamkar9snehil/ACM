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


def _coerce_numeric_frame(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Return a float-coerced numeric frame for the requested columns."""
    return (
        df.reindex(columns=columns)
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
    )


def _coerce_contract_series(
    raw_values: Any,
    *,
    columns: List[str],
    field_name: str,
) -> Optional[pd.Series]:
    """Convert persisted basis metadata back to a column-aligned numeric Series."""
    if raw_values is None:
        return None

    if isinstance(raw_values, dict):
        series = pd.Series(raw_values, dtype="float64")
        return series.reindex(columns)

    values = list(raw_values)
    if len(values) != len(columns):
        raise ValueError(
            f"Basis contract field '{field_name}' has length {len(values)} but expected {len(columns)}"
        )
    return pd.Series([float(v) for v in values], index=columns, dtype="float64")


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
    basis_contract: Optional[Dict[str, Any]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Construct the current compact tag-agnostic basis for regime clustering."""
    _ = pca_detector

    if raw_train is None or raw_score is None:
        raise ValueError("raw_train/raw_score are required for tag-agnostic regime basis construction")

    aligned_train = raw_train.reindex(train_features.index)
    aligned_score = raw_score.reindex(score_features.index)
    basis_contract = dict(basis_contract or {})
    contract_cols = list(
        basis_contract.get("raw_tags")
        or basis_contract.get("feature_columns")
        or basis_contract.get("basis_scaler_cols")
        or []
    )
    contract_reused = bool(contract_cols)

    if contract_reused:
        missing_contract_cols = [
            col for col in contract_cols if col not in aligned_train.columns or col not in aligned_score.columns
        ]
        if missing_contract_cols:
            raise ValueError(
                "Cached regime basis contract cannot be applied because required raw tags are missing: "
                + ", ".join(missing_contract_cols[:5])
            )
        selected_cols = list(contract_cols)
        train_numeric = _coerce_numeric_frame(aligned_train, selected_cols)
        score_numeric = _coerce_numeric_frame(aligned_score, selected_cols)
        surface_meta = {
            "surface_type": "tag_agnostic_numeric",
            "candidate_count": len(selected_cols),
            "selected_count": len(selected_cols),
            "dropped_low_valid_count": 0,
            "dropped_low_iqr_count": 0,
            "min_valid_fraction": None,
            "min_iqr": None,
            "max_cols": len(selected_cols),
            "truncated": False,
            "selected_cols": list(selected_cols),
            "selection_metric": "cached_basis_contract",
            "contract_reused": True,
        }
    else:
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

    fill_values = train_numeric.median(axis=0, numeric_only=True).astype("float64")
    contract_fill_values = _coerce_contract_series(
        basis_contract.get("basis_fill_values") or basis_contract.get("fill_values"),
        columns=selected_cols,
        field_name="basis_fill_values",
    )
    if contract_fill_values is not None:
        fill_values = contract_fill_values.combine_first(fill_values).astype("float64")
    train_basis = train_numeric.ffill().bfill().fillna(fill_values).fillna(0.0)
    score_basis = score_numeric.ffill().bfill().fillna(fill_values).fillna(0.0)

    all_cols = list(selected_cols)
    train_basis = train_basis.astype({c: "float64" for c in all_cols})
    score_basis = score_basis.astype({c: "float64" for c in all_cols})

    mean_vec_list: Optional[List[float]]
    var_vec_list: Optional[List[float]]
    contract_mean = _coerce_contract_series(
        basis_contract.get("basis_scaler_mean") or basis_contract.get("scaler_mean"),
        columns=all_cols,
        field_name="basis_scaler_mean",
    )
    contract_var = _coerce_contract_series(
        basis_contract.get("basis_scaler_var") or basis_contract.get("scaler_var"),
        columns=all_cols,
        field_name="basis_scaler_var",
    )
    contract_scaler_cols = list(basis_contract.get("basis_scaler_cols") or [])

    if contract_reused and contract_scaler_cols and contract_scaler_cols != all_cols:
        raise ValueError(
            "Cached regime basis contract scaler columns do not match active basis columns"
        )

    if contract_mean is not None or contract_var is not None:
        if contract_mean is None or contract_var is None:
            raise ValueError("Cached regime basis contract is missing scaler mean/variance")
        scaler_var = contract_var.astype("float64").clip(lower=0.0)
        scaler_scale = scaler_var.pow(0.5).replace(0.0, 1.0).fillna(1.0)
        train_basis[all_cols] = (train_basis[all_cols] - contract_mean) / scaler_scale
        score_basis[all_cols] = (score_basis[all_cols] - contract_mean) / scaler_scale
        mean_vec_list = [float(x) for x in contract_mean.tolist()]
        var_vec_list = [float(x) for x in scaler_var.tolist()]
        basis_signature = str(
            basis_contract.get("basis_signature")
            or _compute_basis_signature(all_cols, mean_vec_list, var_vec_list, 0)
        )
    else:
        basis_scaler = StandardScaler()
        basis_scaler.fit(train_basis[all_cols].values)
        train_basis[all_cols] = basis_scaler.transform(train_basis[all_cols].values)
        score_basis[all_cols] = basis_scaler.transform(score_basis[all_cols].values)
        mean_vec_list = None
        var_vec_list = None
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
        "basis_contract_reused": contract_reused,
        "basis_fill_values": {col: float(fill_values[col]) for col in all_cols},
    }
    if mean_vec_list is not None:
        meta["basis_scaler_mean"] = mean_vec_list
    if var_vec_list is not None:
        meta["basis_scaler_var"] = var_vec_list
    meta["basis_scaler_cols"] = all_cols
    return train_basis, score_basis, meta


__all__ = [
    "_compute_basis_signature",
    "build_feature_basis",
    "select_ewm_monitoring_surface",
    "select_tag_agnostic_numeric_surface",
]

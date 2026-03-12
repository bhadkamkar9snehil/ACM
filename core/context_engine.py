"""
Context semantics extracted from regime ownership.

This module keeps the current regime-confidence, novelty, and transient-state
behavior intact while moving caller-facing context semantics behind one owner.
Score gating remains out of scope here.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import pairwise_distances_argmin

try:
    import hdbscan
except Exception:  # pragma: no cover - optional dependency in some deployments
    hdbscan = None  # type: ignore

from core.observability import Console
from core.representation_contracts import ContextAssignment
from core.structure_encoder import select_tag_agnostic_numeric_surface
from utils.config_dict import cfg_get as _cfg_get


_DEFAULT_TRANSIENT_HIGH_Z = 3.0
_DEFAULT_TRANSIENT_TRIP_Z = 5.0
_DEFAULT_SURFACE_MIN_IQR = 1e-6
_AMBIGUOUS_CONFIDENCE_THRESHOLD = 0.5


def predict_regime_with_confidence(
    model: Any,
    basis_df: pd.DataFrame,
    cfg: Dict[str, Any],
    training_distances: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Predict regime labels with confidence scores and novelty flags.

    This is a direct extraction of the current runtime behavior. Labels remain
    forced onto valid clusters; novelty and low confidence are annotations only.
    """
    _ = training_distances
    unknown_cfg = _cfg_get(cfg, "regimes.unknown", {}) or {}

    aligned = basis_df.reindex(columns=model.feature_columns, fill_value=0.0)
    aligned_arr = aligned.to_numpy(dtype=np.float64, copy=False, na_value=0.0)
    X_scaled = model.scaler.transform(aligned_arr)
    X_scaled = np.asarray(X_scaled, dtype=np.float64, order="C")
    centers = model.cluster_centers_
    n_samples = len(X_scaled)

    is_novel = np.zeros(n_samples, dtype=bool)
    distance_threshold = model.training_distance_threshold_
    if distance_threshold is None or not np.isfinite(distance_threshold):
        distance_threshold = float("inf")

    if model.is_hdbscan:
        try:
            predict_result = hdbscan.approximate_predict(model.clustering_model, X_scaled)  # type: ignore[union-attr]
            labels = np.asarray(predict_result[0], dtype=int, copy=True)
            strengths = np.asarray(predict_result[1], dtype=float)
            labels = model.apply_label_map(labels)
            confidence = np.clip(strengths, 0.0, 1.0)

            if centers.size > 0 and distance_threshold < float("inf"):
                valid_labels = np.clip(labels, 0, len(centers) - 1)
                point_distances = np.linalg.norm(X_scaled - centers[valid_labels], axis=1)
                is_novel = point_distances > distance_threshold
            else:
                strength_threshold = float(unknown_cfg.get("hdbscan_strength_min", 0.1))
                is_novel = strengths < strength_threshold

            if np.any(is_novel):
                if model.fallback_model_ is not None:
                    gmm_labels = model.fallback_model_.predict(X_scaled[is_novel])
                    gmm_proba = model.fallback_model_.predict_proba(X_scaled[is_novel])
                    gmm_confidence = np.max(gmm_proba, axis=1)
                    labels[is_novel] = gmm_labels
                    confidence[is_novel] = gmm_confidence * 0.5
                elif model.exemplars_ is not None and len(model.exemplars_) > 0:
                    centroid_labels = pairwise_distances_argmin(
                        X_scaled[is_novel], model.exemplars_, axis=1
                    )
                    labels[is_novel] = centroid_labels
                    confidence[is_novel] = 0.3

                n_novel = int(np.sum(is_novel))
                novel_pct = 100.0 * n_novel / n_samples if n_samples > 0 else 0.0
                novel_log = Console.warn if novel_pct >= 25.0 else Console.info
                novel_log(
                    f"HDBSCAN: {n_novel}/{n_samples} ({novel_pct:.1f}%) score points are outside the training envelope (novel). "
                    + ("Regime-indexed calibration thresholds may be unreliable — consider widening the training window. " if novel_pct >= 25.0 else "")
                    + "Assigned to nearest cluster.",
                    component="REGIME",
                )

            return labels, confidence, is_novel

        except Exception as e:
            Console.warn(f"HDBSCAN confidence prediction failed: {e}", component="REGIME")
            if model.fallback_model_ is not None:
                labels = model.fallback_model_.predict(X_scaled).astype(int, copy=False)
                proba = model.fallback_model_.predict_proba(X_scaled)
                confidence = np.max(proba, axis=1) * 0.8
                return labels, confidence, is_novel
            if model.exemplars_ is not None and len(model.exemplars_) > 0:
                labels = pairwise_distances_argmin(X_scaled, model.exemplars_, axis=1).astype(int, copy=False)
                labels = model.apply_label_map(labels)
                distances = np.linalg.norm(X_scaled - model.exemplars_[labels], axis=1)

                if distance_threshold < float("inf"):
                    confidence = np.clip(
                        1.0 - (distances / max(distance_threshold * 2, 1e-6)),
                        0.0,
                        1.0,
                    )
                    is_novel = distances > distance_threshold
                else:
                    threshold = np.percentile(distances, 95) if len(distances) > 0 else 1.0
                    confidence = np.clip(1.0 - (distances / max(threshold, 1e-6)), 0.0, 1.0)
                return labels, confidence, is_novel

            Console.warn("No clustering method available, assigning all to regime 0", component="REGIME")
            return np.zeros(n_samples, dtype=int), np.full(n_samples, 0.1), np.ones(n_samples, dtype=bool)

    labels = model.clustering_model.predict(X_scaled).astype(int, copy=False)
    labels = model.apply_label_map(labels)
    proba = model.clustering_model.predict_proba(X_scaled)
    confidence = proba.max(axis=1)

    if centers.size > 0:
        valid_labels = np.clip(labels, 0, len(centers) - 1)
        point_distances = np.linalg.norm(X_scaled - centers[valid_labels], axis=1)

        if distance_threshold < float("inf"):
            is_novel = point_distances > distance_threshold
        else:
            prob_threshold = 1.0 / max(model.n_clusters, 1)
            is_novel = confidence < prob_threshold * 1.5

        confidence[is_novel] = confidence[is_novel] * 0.5

        if np.any(is_novel):
            Console.info(
                f"GMM: {int(np.sum(is_novel))}/{n_samples} points classified as novel "
                "(low assignment probability). High novel counts may indicate regime drift "
                "or a training window that is too short.",
                component="REGIME",
            )

    return labels, confidence, is_novel


def detect_transient_states(
    data: pd.DataFrame,
    regime_labels: np.ndarray,
    cfg: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """Classify asset-agnostic transient states from normalized change intensity."""
    transient_cfg = (cfg or {}).get("regimes", {}).get("transient_detection", {})

    n_samples = len(data)
    default_states = np.array(["steady"] * n_samples, dtype=object)
    if n_samples == 0:
        return default_states

    roc_window = int(transient_cfg.get("roc_window", 5))
    roc_threshold_high = float(transient_cfg.get("roc_threshold_high", _DEFAULT_TRANSIENT_HIGH_Z))
    roc_threshold_trip = float(transient_cfg.get("roc_threshold_trip", _DEFAULT_TRANSIENT_TRIP_Z))
    transition_lag = int(transient_cfg.get("transition_lag", 3))
    clip_pct = float(transient_cfg.get("clip_percentile", 99.0))
    sensor_weights_cfg = transient_cfg.get("sensor_weights", {}) or {}

    if roc_threshold_high < 1.0 or roc_threshold_trip < 1.0:
        Console.warn(
            "Legacy transient thresholds detected for the asset-agnostic transient index; "
            "using conservative normalized defaults until ACM_Config is refreshed",
            component="TRANSIENT",
            configured_high=roc_threshold_high,
            configured_trip=roc_threshold_trip,
            applied_high=_DEFAULT_TRANSIENT_HIGH_Z,
            applied_trip=_DEFAULT_TRANSIENT_TRIP_Z,
        )
        roc_threshold_high = _DEFAULT_TRANSIENT_HIGH_Z
        roc_threshold_trip = _DEFAULT_TRANSIENT_TRIP_Z

    numeric_cols, data_numeric, _, surface_meta = select_tag_agnostic_numeric_surface(
        data,
        data,
        cfg=cfg,
    )

    if not numeric_cols:
        Console.warn(
            "No adequate tag-agnostic numeric columns for transient detection; "
            "defaulting all rows to steady state",
            component="TRANSIENT",
            n_columns=len(data.columns) if hasattr(data, "columns") else 0,
            n_samples=n_samples,
            candidate_count=surface_meta.get("candidate_count", 0),
        )
        return default_states

    if surface_meta.get("truncated"):
        Console.info(
            f"Transient detection using top {len(numeric_cols)} variable numeric columns",
            component="TRANSIENT",
            selected_count=len(numeric_cols),
            candidate_count=surface_meta.get("candidate_count", len(numeric_cols)),
        )

    configured_weights = list(sensor_weights_cfg.keys())
    if configured_weights:
        matched_cols = [col for col in configured_weights if col in numeric_cols]
        unmatched_cols = [col for col in configured_weights if col not in numeric_cols]
        if unmatched_cols:
            Console.warn(
                f"[TRANSIENT] {len(unmatched_cols)} configured weight keys not in data columns: "
                f"{unmatched_cols[:3]}{'...' if len(unmatched_cols) > 3 else ''}",
                component="TRANSIENT",
                unmatched_count=len(unmatched_cols),
                matched_count=len(matched_cols),
            )
        if matched_cols:
            Console.info(f"Using custom weights for {len(matched_cols)} sensors", component="TRANSIENT")

    raw_weights = np.array([float(sensor_weights_cfg.get(col, 1.0)) for col in numeric_cols], dtype=float)
    if np.any(raw_weights < 0):
        Console.info("Negative weights found; using absolute values for ROC aggregation", component="TRANSIENT")
    weights = np.abs(raw_weights)

    if not np.isfinite(weights).all() or weights.sum() <= 0:
        weights = np.ones(len(numeric_cols), dtype=float)
        Console.warn(
            "Invalid weights detected; falling back to uniform weights",
            component="TRANSIENT",
            n_sensors=len(numeric_cols),
        )
    weights /= weights.sum()

    fill_values = data_numeric.median(axis=0, numeric_only=True)
    data_numeric = data_numeric.ffill().bfill().fillna(fill_values).fillna(0.0)

    data_values = data_numeric.to_numpy(dtype=float, copy=False)
    diff_values = np.diff(data_values, axis=0, prepend=data_values[:1])
    diff_abs = np.abs(diff_values)

    min_scale = float(surface_meta.get("min_iqr", _DEFAULT_SURFACE_MIN_IQR) or _DEFAULT_SURFACE_MIN_IQR)
    level_q25 = np.nanpercentile(data_values, 25, axis=0)
    level_q75 = np.nanpercentile(data_values, 75, axis=0)
    level_iqr = level_q75 - level_q25
    diff_q25 = np.nanpercentile(diff_abs, 25, axis=0)
    diff_q75 = np.nanpercentile(diff_abs, 75, axis=0)
    diff_iqr = diff_q75 - diff_q25

    scale = np.where(
        np.isfinite(diff_iqr) & (diff_iqr > min_scale),
        diff_iqr,
        np.where(
            np.isfinite(level_iqr) & (level_iqr > min_scale),
            level_iqr,
            1.0,
        ),
    )
    change_matrix = diff_abs / scale
    change_matrix = np.where(np.isfinite(change_matrix), change_matrix, np.nan)

    if clip_pct < 100.0:
        try:
            upper = np.nanpercentile(change_matrix, clip_pct)
            change_matrix = np.clip(change_matrix, None, upper)
        except Exception:
            pass

    aggregate_change = np.nansum(change_matrix * weights[np.newaxis, :], axis=1)
    aggregate_change = pd.Series(aggregate_change).ffill().bfill().fillna(0.0)
    aggregate_change_smooth = aggregate_change.rolling(window=max(2, roc_window), min_periods=1).mean()

    regime_changes = np.zeros(n_samples, dtype=bool)
    if len(regime_labels) == n_samples:
        diffs = np.diff(regime_labels.astype(int), prepend=regime_labels[0])
        regime_changes = diffs != 0

    change_values = aggregate_change_smooth.to_numpy(dtype=float)
    change_center = float(np.nanmedian(change_values))
    change_mad = float(np.nanmedian(np.abs(change_values - change_center)))
    change_scale = max(change_mad * 1.4826, 1e-6)
    change_score = np.maximum((change_values - change_center) / change_scale, 0.0)

    trip_mask = change_score >= roc_threshold_trip
    high_mask = (change_score >= roc_threshold_high) & ~trip_mask

    def _dilate(mask: np.ndarray, width: int) -> np.ndarray:
        if width <= 0 or mask.size == 0:
            return mask
        width = int(width)
        kernel = np.ones(2 * width + 1, dtype=int)
        padded = np.pad(mask.astype(int), (width, width), mode="constant")
        return np.convolve(padded, kernel, mode="valid") > 0

    boundary_mask = _dilate(regime_changes, max(1, transition_lag))
    base_transient = boundary_mask | high_mask | trip_mask
    transient_mask = _dilate(base_transient, max(1, transition_lag))
    trip_mask = _dilate(trip_mask, max(1, transition_lag // 2))

    states = np.full(n_samples, "steady", dtype=object)
    states[transient_mask] = "transient"
    states[trip_mask] = "trip"

    state_counts = pd.Series(states).value_counts().to_dict()
    Console.info(f"State distribution: {state_counts}", component="TRANSIENT")
    return states


def apply_transient_state_labels(
    frame: pd.DataFrame,
    score_data: pd.DataFrame,
    cfg: Dict[str, Any],
    logger: Any = Console,
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Detect transient operating states and attach them to the scoring frame."""
    transient_counts: Dict[str, int] = {}

    if "regime_label" not in frame.columns:
        return frame, transient_counts

    transient_states = detect_transient_states(
        data=score_data,
        regime_labels=frame["regime_label"].to_numpy(copy=False),
        cfg=cfg,
    )
    frame["transient_state"] = transient_states
    transient_counts = frame["transient_state"].value_counts().to_dict()
    return frame, transient_counts


def build_context_assignment(
    frame: Optional[pd.DataFrame],
    *,
    ambiguous_confidence_threshold: float = _AMBIGUOUS_CONFIDENCE_THRESHOLD,
) -> ContextAssignment:
    """
    Build a typed context summary from the latest scored frame row.

    This is intentionally conservative in shadow mode: ambiguity is inferred
    from missing labels, novelty, or low confidence rather than being used for
    any downstream suppression.
    """
    if frame is None or frame.empty or "regime_label" not in frame.columns:
        return ContextAssignment()

    last_row = frame.iloc[-1]
    raw_label = last_row.get("regime_label")
    try:
        label_value = None if pd.isna(raw_label) else int(raw_label)
    except Exception:
        label_value = None

    raw_confidence = last_row.get("regime_confidence", 0.0)
    try:
        confidence = 0.0 if pd.isna(raw_confidence) else float(raw_confidence)
    except Exception:
        confidence = 0.0

    raw_novel = last_row.get("regime_is_novel", False)
    is_novel = False if pd.isna(raw_novel) else bool(raw_novel)

    transition_raw = last_row.get("transient_state", "UNASSESSED")
    if transition_raw is None or pd.isna(transition_raw):
        transition_status = "UNASSESSED"
    else:
        transition_status = str(transition_raw).strip().upper() or "UNASSESSED"

    if label_value is None:
        context_id = "unknown"
        context_label = "UNKNOWN"
    else:
        context_id = f"regime:{label_value}"
        context_label = f"REGIME_{label_value}"

    if transition_status in {"TRANSIENT", "TRIP", "STARTUP", "SHUTDOWN"}:
        context_stability = "TRANSIENT"
    elif is_novel:
        context_stability = "EMERGING"
    elif confidence <= 0.0 and "regime_confidence" not in frame.columns:
        context_stability = "UNASSESSED"
    elif confidence < ambiguous_confidence_threshold:
        context_stability = "AMBIGUOUS"
    else:
        context_stability = "STABLE"

    is_ambiguous = (
        label_value is None
        or is_novel
        or confidence < ambiguous_confidence_threshold
        or context_stability == "UNASSESSED"
    )

    return ContextAssignment(
        context_id=context_id,
        context_label=context_label,
        context_confidence=confidence,
        context_stability=context_stability,
        transition_status=transition_status,
        is_novel=is_novel,
        is_ambiguous=is_ambiguous,
    )


__all__ = [
    "apply_transient_state_labels",
    "build_context_assignment",
    "detect_transient_states",
    "predict_regime_with_confidence",
]

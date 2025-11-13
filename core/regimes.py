# core/regimes.py
# Fast + memory-safe regime labeling with auto-k.
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import json
import numpy as np
import pandas as pd
from pathlib import Path

import joblib
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import silhouette_score, calinski_harabasz_score, pairwise_distances_argmin
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import sklearn

import matplotlib
matplotlib.use("Agg")
try:
    from core.output_manager import OutputManager
except Exception:
    OutputManager = None  # type: ignore
import matplotlib.pyplot as plt

from utils.logger import Console

try:
    from scipy.ndimage import median_filter as _median_filter
except Exception:  # pragma: no cover - scipy optional in some deployments
    _median_filter = None

REGIME_MODEL_VERSION = "2.0"

_HEALTH_PRIORITY = {
    "healthy": 0,
    "suspect": 1,
    "critical": 2,
    "unknown": 3,
    None: 3,
}

_REGIME_CONFIG_SCHEMA = {
    "regimes.auto_k.k_min": (int, 2, 20, "Minimum clusters"),
    "regimes.auto_k.k_max": (int, 2, 40, "Maximum clusters"),
    "regimes.quality.silhouette_min": (float, 0.0, 1.0, "Minimum silhouette score"),
    "regimes.auto_k.max_eval_samples": (int, 100, 20000, "Max samples for auto-k evaluation"),
}

# ----------------------------
# Small helpers / sane defaults
# ----------------------------
def _cfg_get(cfg: Dict[str, Any], path: str, default: Any) -> Any:
    cur = cfg or {}
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

def _as_f32(X) -> np.ndarray:
    return np.asarray(X, dtype=np.float32, order="C")

def _finite_impute_inplace(X: np.ndarray) -> np.ndarray:
    X = _as_f32(X)
    nonfinite = ~np.isfinite(X)
    if nonfinite.any():
        X[nonfinite] = np.nan
    col_means = np.nanmean(X, axis=0)
    col_means = np.where(np.isfinite(col_means), col_means, 0.0).astype(np.float32)
    nan_mask = np.isnan(X)
    if nan_mask.any():
        X[nan_mask] = np.take(col_means, np.where(nan_mask)[1])
    return X

def _robust_scale_clip(X: np.ndarray, clip_pct: float = 99.9) -> np.ndarray:
    X = np.asarray(X, dtype=np.float64, order="C")
    lo = np.percentile(X, 100 - clip_pct, axis=0)
    hi = np.percentile(X, clip_pct, axis=0)
    X = np.clip(X, lo, hi, out=X)
    med = np.median(X, axis=0)
    q25 = np.percentile(X, 25, axis=0)
    q75 = np.percentile(X, 75, axis=0)
    iqr = q75 - q25
    scale = iqr / 1.349
    scale = np.where(scale > 0, scale, 1.0)
    X -= med
    X /= scale
    bad = ~np.isfinite(X)
    if bad.any():
        X[bad] = 0.0
    return X


def _compute_sample_durations(index: pd.Index) -> np.ndarray:
    """Estimate per-sample durations in seconds for a time-aligned index."""

    n = len(index)
    if n == 0:
        return np.zeros(0, dtype=float)

    # Default: treat each sample as unit duration
    durations = np.ones(n, dtype=float)

    if isinstance(index, pd.DatetimeIndex):
        if n == 1:
            return np.zeros(1, dtype=float)

        values = index.view("int64")
        diffs = np.diff(values).astype(np.float64) / 1e9  # convert ns -> seconds
        valid = diffs[np.isfinite(diffs) & (diffs > 0)]
        fallback = float(np.median(valid)) if valid.size else 0.0
        durations[:-1] = np.where(np.isfinite(diffs) & (diffs >= 0), diffs, fallback)
        durations[-1] = fallback if fallback > 0 else (diffs[-1] if diffs.size else 0.0)
        # If no positive spacing detected, fall back to unit durations
        if not np.isfinite(durations).any() or np.allclose(durations, 0.0):
            durations = np.ones(n, dtype=float)

    return durations


def _validate_regime_inputs(df: pd.DataFrame, name: str = "train_basis") -> List[str]:
    issues: List[str] = []
    if df is None or df.empty:
        issues.append(f"{name} is empty")
        return issues
    numeric = df.select_dtypes(include=[np.number])
    if numeric.shape[1] != df.shape[1]:
        issues.append(f"{name} contains non-numeric columns")
    if numeric.isna().any().any():
        missing_cols = numeric.columns[numeric.isna().any()].tolist()
        issues.append(f"{name} contains NaNs in columns: {missing_cols}")
    variances = numeric.var(axis=0)
    low_var_cols = variances[variances <= 1e-6].index.tolist()
    if low_var_cols:
        issues.append(f"{name} has near-zero variance columns: {low_var_cols}")
    if numeric.shape[0] < 10:
        issues.append(f"{name} has limited samples ({numeric.shape[0]}); silhouette may be unstable")
    return issues


def _validate_regime_config(cfg: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    for path, (expected_type, low, high, description) in _REGIME_CONFIG_SCHEMA.items():
        value = _cfg_get(cfg, path, None)
        if value is None:
            issues.append(f"Missing config value for {path} ({description})")
            continue
        if not isinstance(value, expected_type):
            issues.append(f"Config {path} expected {expected_type.__name__}, got {type(value).__name__}")
            continue
        if isinstance(value, (int, float)) and not (low <= value <= high):
            issues.append(f"Config {path}={value} outside expected range [{low}, {high}]")
    return issues

# ----------------------------
# Regime model container
# ----------------------------
@dataclass
class RegimeModel:
    scaler: StandardScaler
    kmeans: MiniBatchKMeans
    feature_columns: List[str]
    raw_tags: List[str]
    n_pca_components: int
    train_hash: Optional[int] = None
    health_labels: Dict[int, str] = field(default_factory=dict)
    stats: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


def build_feature_basis(
    train_features: pd.DataFrame,
    score_features: pd.DataFrame,
    raw_train: Optional[pd.DataFrame],
    raw_score: Optional[pd.DataFrame],
    pca_detector: Optional[Any],
    cfg: Dict[str, Any],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Construct a compact feature matrix for regime clustering."""
    basis_cfg = _cfg_get(cfg, "regimes.feature_basis", {})
    n_pca = int(basis_cfg.get("n_pca_components", 3))
    raw_tags_cfg = basis_cfg.get("raw_tags", []) or []

    train_parts: List[pd.DataFrame] = []
    score_parts: List[pd.DataFrame] = []
    used_raw_tags: List[str] = []
    n_pca_used = 0
    pca_variance_ratio: Optional[float] = None
    pca_variance_vector: List[float] = []

    if pca_detector is not None and getattr(pca_detector, "pca", None) is not None:
        keep_cols = getattr(pca_detector, "keep_cols", list(train_features.columns))
        train_subset = train_features.reindex(columns=keep_cols).fillna(0.0)
        score_subset = score_features.reindex(columns=keep_cols).fillna(0.0)
        try:
            train_scaled = pca_detector.scaler.transform(train_subset.to_numpy(dtype=float, copy=False))
            score_scaled = pca_detector.scaler.transform(score_subset.to_numpy(dtype=float, copy=False))
            train_scores = pca_detector.pca.transform(train_scaled)
            score_scores = pca_detector.pca.transform(score_scaled)
            n_pca_available = train_scores.shape[1]
            n_pca_used = max(0, min(n_pca, n_pca_available))
            if n_pca_used > 0:
                variance_ratio = getattr(pca_detector.pca, "explained_variance_ratio_", None)
                if variance_ratio is not None:
                    pca_variance_vector = [float(x) for x in variance_ratio[:n_pca_used]]
                    pca_variance_ratio = float(np.sum(pca_variance_vector))
                cols = [f"PCA_{i+1}" for i in range(n_pca_used)]
                train_parts.append(pd.DataFrame(train_scores[:, :n_pca_used], index=train_features.index, columns=cols))
                score_parts.append(pd.DataFrame(score_scores[:, :n_pca_used], index=score_features.index, columns=cols))
        except Exception:
            n_pca_used = 0

    if raw_train is not None and raw_score is not None:
        available_tags = [tag for tag in raw_tags_cfg if tag in raw_train.columns]
        if available_tags:
            used_raw_tags = available_tags
            train_raw = raw_train.reindex(train_features.index)[available_tags].astype(float).ffill().bfill().fillna(0.0)
            score_raw = raw_score.reindex(score_features.index)[available_tags].astype(float).ffill().bfill().fillna(0.0)
            train_parts.append(train_raw)
            score_parts.append(score_raw)

    if not train_parts:
        fallback_cols = train_features.columns[:max(1, min(5, train_features.shape[1]))]
        train_parts.append(train_features[fallback_cols].fillna(0.0))
        score_parts.append(score_features[fallback_cols].fillna(0.0))

    train_basis = pd.concat(train_parts, axis=1)
    score_basis = pd.concat(score_parts, axis=1)
    train_basis = train_basis.ffill().bfill().fillna(0.0)
    score_basis = score_basis.ffill().bfill().fillna(0.0)

    basis_scaler = StandardScaler()
    basis_scaler.fit(train_basis.values)
    train_basis = pd.DataFrame(
        basis_scaler.transform(train_basis.values),
        index=train_basis.index,
        columns=train_basis.columns,
    )
    score_basis = pd.DataFrame(
        basis_scaler.transform(score_basis.values),
        index=score_basis.index,
        columns=score_basis.columns,
    )

    meta = {
        "n_pca": n_pca_used,
        "raw_tags": used_raw_tags,
        "fallback_cols": list(train_basis.columns),
        "basis_normalized": True,
    }
    mean_vec = getattr(basis_scaler, "mean_", None)
    var_vec = getattr(basis_scaler, "var_", None)
    if mean_vec is not None:
        meta["basis_scaler_mean"] = [float(x) for x in mean_vec]
    if var_vec is not None:
        meta["basis_scaler_var"] = [float(x) for x in var_vec]
    if pca_variance_ratio is not None:
        meta["pca_variance_ratio"] = pca_variance_ratio
        meta["pca_variance_vector"] = pca_variance_vector
        variance_min = float(basis_cfg.get("pca_variance_min", 0.85))
        meta["pca_variance_min"] = variance_min
        if pca_variance_ratio < variance_min:
            Console.warn(
                f"[REGIME] PCA variance coverage {pca_variance_ratio:.3f} below target {variance_min:.3f}."
            )
    return train_basis, score_basis, meta


def _fit_kmeans_scaled(
    X: np.ndarray,
    cfg: Dict[str, Any],
) -> Tuple[StandardScaler, MiniBatchKMeans, int, float, str, List[Tuple[int, float]], bool]:
    """Fit KMeans with auto-k selection using silhouette scoring without k=1 fallback."""

    X = _finite_impute_inplace(X)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    n_samples = X_scaled.shape[0]
    if n_samples == 0:
        raise ValueError("Cannot fit regime model on an empty dataset")

    k_min = int(_cfg_get(cfg, "regimes.auto_k.k_min", 2))
    k_max = int(_cfg_get(cfg, "regimes.auto_k.k_max", 6))
    sil_sample = int(_cfg_get(cfg, "regimes.auto_k.sil_sample", 4000))
    max_eval_samples = int(_cfg_get(cfg, "regimes.auto_k.max_eval_samples", 5000))
    random_state = int(_cfg_get(cfg, "regimes.auto_k.random_state", 17))
    sil_threshold = float(_cfg_get(cfg, "regimes.quality.silhouette_min", 0.2))

    if n_samples < k_min:
        k_min = max(2, n_samples) if n_samples >= 2 else 1
    if k_max < k_min:
        k_max = k_min

    # Sample for evaluation but always refit the final model on full data.
    if n_samples > max_eval_samples:
        rng = np.random.default_rng(random_state)
        eval_idx = rng.choice(n_samples, size=max_eval_samples, replace=False)
        X_eval = X_scaled[eval_idx]
    else:
        X_eval = X_scaled

    best_score = -np.inf
    best_metric = "silhouette"
    best_k = max(2, k_min)
    best_model_eval: Optional[MiniBatchKMeans] = None
    all_scores: List[Tuple[int, float]] = []
    silhouette_scores: List[Tuple[int, float]] = []

    for k in range(max(2, k_min), k_max + 1):
        if X_eval.shape[0] <= k:
            continue
        km_eval = MiniBatchKMeans(
            n_clusters=k,
            batch_size=max(32, min(2048, max(512, X_eval.shape[0] // 10) or 1)),
            n_init=10,
            random_state=random_state,
        )
        km_eval.fit(X_eval)
        labels = km_eval.labels_
        uniq = np.unique(labels)
        if uniq.size < 2:
            score = -np.inf
            metric = "silhouette"
        else:
            try:
                sample_size = min(sil_sample, X_eval.shape[0])
                score = silhouette_score(X_eval, labels, sample_size=sample_size, random_state=random_state)
                metric = "silhouette"
                silhouette_scores.append((k, float(score)))
            except Exception:
                score = calinski_harabasz_score(X_eval, labels)
                metric = "calinski_harabasz"
        all_scores.append((k, float(score)))
        if float(score) > best_score:
            best_score = float(score)
            best_metric = metric
            best_k = k
            best_model_eval = km_eval

    if best_model_eval is None:
        # Degenerate case: fallback to minimal feasible clusters but flag quality
        fallback_k = max(1, min(k_min, n_samples))
        Console.warn(
            f"[REGIME] Unable to evaluate silhouette for candidate k; defaulting to k={fallback_k}."
        )
        best_k = fallback_k
        best_score = float("nan")
        best_metric = "unscored"
        low_quality = True
    else:
        low_quality = bool(
            best_metric == "silhouette"
            and silhouette_scores
            and all(score < sil_threshold for _, score in silhouette_scores)
        )
        if low_quality:
            Console.warn(
                "[REGIME] All silhouette scores below quality threshold; retaining best_k but flagging quality."
            )

    best_model = MiniBatchKMeans(
        n_clusters=best_k,
        batch_size=max(32, min(2048, max(512, X_scaled.shape[0] // 10) or 1)),
        n_init=20,
        random_state=random_state,
    )
    best_model.fit(X_scaled)

    score_str = "nan" if np.isnan(best_score) else f"{best_score:.3f}"
    Console.info(
        f"[REGIME] Auto-k selection complete: k={best_k}, metric={best_metric}, score={score_str}."
    )
    if silhouette_scores:
        formatted = ", ".join(f"k={k}: {score:.3f}" for k, score in sorted(silhouette_scores))
        Console.info(f"[REGIME] Silhouette sweep: {formatted}")
    elif all_scores:
        formatted = ", ".join(f"k={k}: {score:.3f}" for k, score in sorted(all_scores))
        Console.info(f"[REGIME] Score sweep: {formatted}")

    return scaler, best_model, int(best_k), float(best_score), best_metric, all_scores, low_quality


def fit_regime_model(
    train_basis: pd.DataFrame,
    basis_meta: Dict[str, Any],
    cfg: Dict[str, Any],
    train_hash: Optional[int],
) -> RegimeModel:
    input_issues = _validate_regime_inputs(train_basis, "train_basis")
    config_issues = _validate_regime_config(cfg)
    for issue in input_issues:
        Console.warn(f"[REGIME] Input validation: {issue}")
    for issue in config_issues:
        Console.warn(f"[REGIME] Config validation: {issue}")

    (
        scaler,
        kmeans,
        best_k,
        best_score,
        best_metric,
        quality_sweep,
        low_quality,
    ) = _fit_kmeans_scaled(train_basis.to_numpy(dtype=float, copy=False), cfg)
    quality_cfg = _cfg_get(cfg, "regimes.quality", {})
    sil_min = float(quality_cfg.get("silhouette_min", 0.2))
    calinski_min = float(quality_cfg.get("calinski_min", 50.0))
    quality_ok = True
    if best_metric == "silhouette":
        quality_ok = best_score >= sil_min
    elif best_metric == "calinski_harabasz":
        quality_ok = best_score >= calinski_min
    if low_quality or input_issues or config_issues:
        quality_ok = False
    quality_notes: List[str] = []
    if low_quality:
        quality_notes.append("silhouette_below_threshold")
    quality_notes.extend(input_issues)
    quality_notes.extend(config_issues)
    if np.isnan(best_score):
        quality_notes.append("auto_k_unscored")
    meta = {
        "best_k": int(best_k),
        "fit_score": float(best_score),
        "fit_metric": best_metric,
        "quality_ok": bool(quality_ok),
        "quality_notes": quality_notes,
        "quality_sweep": sorted(quality_sweep, key=lambda item: item[0]),
        "model_version": REGIME_MODEL_VERSION,
        "sklearn_version": sklearn.__version__,
    }
    meta.update({k: v for k, v in basis_meta.items() if k not in meta})
    model = RegimeModel(
        scaler=scaler,
        kmeans=kmeans,
        feature_columns=list(train_basis.columns),
        raw_tags=basis_meta.get("raw_tags", []),
        n_pca_components=int(basis_meta.get("n_pca", 0)),
        train_hash=train_hash,
        meta=meta,
    )
    return model


def predict_regime(model: RegimeModel, basis_df: pd.DataFrame) -> np.ndarray:
    aligned = basis_df.reindex(columns=model.feature_columns, fill_value=0.0)
    aligned_arr = aligned.to_numpy(dtype=np.float64, copy=False, na_value=0.0)
    X_scaled = model.scaler.transform(aligned_arr)
    X_scaled = np.asarray(X_scaled, dtype=np.float64, order="C")
    centers = np.asarray(model.kmeans.cluster_centers_, dtype=np.float64, order="C")
    labels = pairwise_distances_argmin(X_scaled, centers, axis=1)
    return labels.astype(int, copy=False)


def update_health_labels(
    model: RegimeModel,
    labels: np.ndarray,
    fused_series: pd.Series | np.ndarray,
    cfg: Dict[str, Any],
) -> Dict[int, Dict[str, Any]]:
    health_cfg = _cfg_get(cfg, "regimes.health", {})
    warn = float(health_cfg.get("fused_warn_z", 1.5))
    alert = float(health_cfg.get("fused_alert_z", 3.0))

    labels = np.asarray(labels, dtype=int)
    fused = pd.Series(fused_series).astype(float)

    durations = _compute_sample_durations(fused.index)
    total_duration_sec = float(durations.sum()) if durations.size else float(len(labels))

    labels_arr = labels.astype(int, copy=False)
    segments: List[Tuple[int, int, int]] = []  # (label, start_idx, end_idx)
    if labels_arr.size:
        start = 0
        current = int(labels_arr[0])
        for idx in range(1, labels_arr.size):
            nxt = int(labels_arr[idx])
            if nxt != current:
                segments.append((current, start, idx))
                current = nxt
                start = idx
        segments.append((current, start, labels_arr.size))

    per_label_segments: Dict[int, Dict[str, Any]] = {}
    transition_counts: Dict[str, int] = {}
    for seg_idx, (label_value, start_idx, end_idx) in enumerate(segments):
        info = per_label_segments.setdefault(
            int(label_value),
            {"segment_count": 0, "dwell_seconds": 0.0, "dwell_samples": 0, "transitions_in": 0, "transitions_out": 0},
        )
        info["segment_count"] += 1
        span = max(end_idx - start_idx, 0)
        info["dwell_samples"] += span
        if durations.size:
            info["dwell_seconds"] += float(np.sum(durations[start_idx:end_idx]))

        if seg_idx > 0:
            prev_label, _, _ = segments[seg_idx - 1]
            key = f"{int(prev_label)}->{int(label_value)}"
            transition_counts[key] = transition_counts.get(key, 0) + 1
            per_label_segments[int(label_value)]["transitions_in"] += 1
            per_label_segments[int(prev_label)]["transitions_out"] += 1

    stats: Dict[int, Dict[str, Any]] = {}
    for label in np.unique(labels_arr):
        mask = labels == label
        if not np.any(mask):
            continue
        fused_vals = fused.loc[mask]
        if fused_vals.empty:
            continue
        seg_info = per_label_segments.get(int(label), {})
        segment_count = int(seg_info.get("segment_count", 0))
        transition_count = max(segment_count - 1, 0)
        dwell_seconds = float(seg_info.get("dwell_seconds", float("nan")))
        if not np.isfinite(dwell_seconds) or dwell_seconds <= 0:
            dwell_seconds = float("nan")
        dwell_samples = int(seg_info.get("dwell_samples", int(mask.sum())))
        med = float(np.nanmedian(fused_vals))
        p95 = float(np.nanpercentile(np.abs(fused_vals), 95))
        count = int(mask.sum())
        if med >= alert:
            state = "critical"
        elif med >= warn:
            state = "suspect"
        else:
            state = "healthy"
        avg_dwell_seconds = float(dwell_seconds / segment_count) if segment_count > 0 and np.isfinite(dwell_seconds) else float("nan")
        dwell_fraction = float(dwell_seconds / total_duration_sec) if np.isfinite(dwell_seconds) and total_duration_sec > 0 else float("nan")
        stability_score = float(1.0 / (1.0 + transition_count)) if transition_count >= 0 else float("nan")
        stats[int(label)] = {
            "median_fused": med,
            "p95_abs_fused": p95,
            "count": count,
            "state": state,
            "dwell_samples": dwell_samples,
            "dwell_seconds": dwell_seconds,
            "avg_dwell_seconds": avg_dwell_seconds,
            "dwell_fraction": dwell_fraction,
            "segment_count": segment_count,
            "transition_count": transition_count,
            "stability_score": stability_score,
        }
        model.health_labels[int(label)] = state
    model.stats = stats
    if transition_counts:
        model.meta["transition_counts"] = {k: int(v) for k, v in transition_counts.items()}
    if np.isfinite(total_duration_sec):
        model.meta["total_duration_seconds"] = float(total_duration_sec)
    model.meta["total_samples"] = int(len(labels_arr))
    return stats
def _persist_regime_error(e: Exception, models_dir: Path):
    """Helper to write error details to a file."""
    err_file = models_dir / "regime_persist.errors.txt"
    import traceback
    with err_file.open("w", encoding="utf-8") as f:
        f.write(f"Error type: {type(e).__name__}\n\n{traceback.format_exc()}")


def build_summary_dataframe(model: RegimeModel) -> pd.DataFrame:
    stats = model.stats or {}
    if not stats:
        return pd.DataFrame(columns=[
            "regime",
            "state",
            "dwell_seconds",
            "dwell_fraction",
            "avg_dwell_seconds",
            "transition_count",
            "stability_score",
            "median_fused",
            "p95_abs_fused",
            "count",
        ])

    total_duration = float(model.meta.get("total_duration_seconds", 0.0) or 0.0)
    if not np.isfinite(total_duration) or total_duration <= 0:
        total_duration = float(sum(stat.get("dwell_seconds", 0.0) for stat in stats.values()))
        if not np.isfinite(total_duration) or total_duration <= 0:
            total_duration = float(sum(stat.get("count", 0) for stat in stats.values()))

    rows: List[Dict[str, Any]] = []
    for label, stat in stats.items():
        dwell_seconds = float(stat.get("dwell_seconds", float("nan")))
        if (not np.isfinite(dwell_seconds) or dwell_seconds <= 0) and total_duration > 0:
            dwell_seconds = float(stat.get("count", 0))
        dwell_fraction_raw = stat.get("dwell_fraction")
        dwell_fraction = float(dwell_fraction_raw) if dwell_fraction_raw is not None else float("nan")
        if not np.isfinite(dwell_fraction) and total_duration > 0:
            dwell_fraction = dwell_seconds / total_duration if dwell_seconds >= 0 else float("nan")
        avg_dwell = float(stat.get("avg_dwell_seconds", float("nan")))
        if not np.isfinite(avg_dwell) and stat.get("segment_count"):
            avg_dwell = dwell_seconds / max(int(stat.get("segment_count", 0)), 1)
        row = {
            "regime": int(label),
            "state": model.health_labels.get(int(label), "unknown"),
            "dwell_seconds": dwell_seconds,
            "dwell_fraction": dwell_fraction,
            "avg_dwell_seconds": avg_dwell,
            "transition_count": int(stat.get("transition_count", 0)),
            "stability_score": float(stat.get("stability_score", float("nan"))),
            "median_fused": stat.get("median_fused", float("nan")),
            "p95_abs_fused": stat.get("p95_abs_fused", float("nan")),
            "count": int(stat.get("count", 0)),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    desired_cols = [
        "regime",
        "state",
        "dwell_seconds",
        "dwell_fraction",
        "avg_dwell_seconds",
        "transition_count",
        "stability_score",
        "median_fused",
        "p95_abs_fused",
        "count",
    ]
    for col in desired_cols:
        if col not in df.columns:
            df[col] = float("nan")
    return df[desired_cols].sort_values("regime").reset_index(drop=True)


def smooth_labels(labels: np.ndarray, passes: int = 1, window: Optional[int] = None) -> np.ndarray:
    """Apply median-like smoothing to integer labels using SciPy when available."""
    if labels.size == 0:
        return labels

    smoothed = labels.astype(int, copy=True)
    if passes <= 0 and window is None:
        return smoothed

    win = window if window is not None else max(1, 2 * passes + 1)
    if win % 2 == 0:
        win += 1
    if _median_filter is not None and win > 1:
        try:
            filtered = _median_filter(smoothed, size=win, mode="nearest")
            return np.asarray(filtered, dtype=int)
        except Exception:
            Console.warn("[REGIME] SciPy median_filter failed; falling back to manual smoothing")

    iterations = max(1, passes)
    for _ in range(iterations):
        changed = False
        for i in range(1, len(smoothed) - 1):
            prev_label = smoothed[i - 1]
            next_label = smoothed[i + 1]
            if smoothed[i] != prev_label and prev_label == next_label:
                smoothed[i] = prev_label
                changed = True
        if not changed:
            break
    return smoothed

def smooth_transitions(
    labels: np.ndarray,
    timestamps: Optional[pd.Index] = None,
    *,
    min_dwell_samples: int = 0,
    min_dwell_seconds: Optional[float] = None,
    health_map: Optional[Dict[int, str]] = None,
) -> np.ndarray:
    """Enforce a minimum dwell time for regime labels.

    If a run of a label is shorter than the dwell threshold, it is replaced by
    the preceding label (or following when no preceding).

    Priority of thresholds:
    - If `min_dwell_seconds` and valid `timestamps` are provided, use time-based dwell.
    - Else if `min_dwell_samples` > 0, use sample-count dwell.
    - Else return labels unchanged.
    """
    arr = np.asarray(labels, dtype=int)
    n = arr.size
    if n == 0:
        return arr

    use_time = False
    ts: Optional[pd.Index] = None
    if min_dwell_seconds is not None and timestamps is not None and len(timestamps) == n:
        try:
            ts = pd.Index(pd.to_datetime(timestamps))
            if not ts.is_monotonic_increasing:
                ts = ts.sort_values()
            use_time = True
        except Exception:
            ts = None
            use_time = False

    if not use_time and min_dwell_samples <= 0:
        return arr

    result = arr.copy()

    def _candidate_score(label: int, segment_start: int, segment_end: int) -> Tuple[int, int]:
        health = None
        if health_map is not None:
            health = health_map.get(int(label))
        health_rank = _HEALTH_PRIORITY.get(health, _HEALTH_PRIORITY["unknown"])
        run = 0
        idx = segment_start - 1
        while idx >= 0 and result[idx] == label:
            run += 1
            idx -= 1
        idx = segment_end
        while idx < n and result[idx] == label:
            run += 1
            idx += 1
        return (health_rank, -run)

    start = 0
    while start < n:
        end = start + 1
        while end < n and arr[end] == arr[start]:
            end += 1

        segment_len = end - start
        violates = False
        if use_time and ts is not None and min_dwell_seconds is not None:
            t0 = pd.Timestamp(ts[start])
            t1 = pd.Timestamp(ts[end - 1])
            dur = (t1 - t0).total_seconds()
            violates = dur < float(min_dwell_seconds)
        elif not use_time:
            violates = segment_len < int(min_dwell_samples)

        if violates:
            candidates: List[int] = []
            if start > 0:
                candidates.append(int(result[start - 1]))
            if end < n:
                candidates.append(int(result[end]))
            if candidates:
                replacement = min(candidates, key=lambda lbl: _candidate_score(lbl, start, end))
                result[start:end] = replacement
        start = end

    return result

# Timestamp parsing (fast, consistent, UTC)
def _to_datetime_mixed(s):
    try:
        return pd.to_datetime(s, format="mixed", errors="coerce")
    except TypeError:
        return pd.to_datetime(s, errors="coerce")

def _read_episodes_csv(p: Path) -> pd.DataFrame:
    if not p.exists():
        return pd.DataFrame(columns=["start_ts", "end_ts"])
    df = pd.read_csv(p, dtype={"start_ts": "string", "end_ts": "string"})
    df["start_ts"] = _to_datetime_mixed(df["start_ts"])
    df["end_ts"]   = _to_datetime_mixed(df["end_ts"])
    return df

def _read_scores_csv(p: Path) -> pd.DataFrame:
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, dtype={"timestamp": "string"})
    df["timestamp"] = _to_datetime_mixed(df["timestamp"])
    df = df.set_index("timestamp")
    return df[~df.index.isna()]

# -----------------------------------
# Core: fit auto-k with safe heuristics
# -----------------------------------
def _fit_auto_k(
    X: np.ndarray,
    *,
    k_min: int = 2,
    k_max: int = 6,
    pca_dim: int = 20,
    sil_sample: int = 4000,
    random_state: int = 17,
) -> Tuple[MiniBatchKMeans, Optional[PCA], int, float, str]:
    X = _finite_impute_inplace(X)
    n, d = X.shape

    if n < 4:
        km = MiniBatchKMeans(
            n_clusters=1,
            batch_size=max(32, min(2048, n or 1)),
            n_init="auto",
            random_state=random_state,
        )
        km.fit(X)
        return km, None, 1, 0.0, "degenerate"

    Xp_f64: Optional[np.ndarray] = None
    pca_obj: Optional[PCA] = None
    max_components = max(1, min(pca_dim, d, n - 1))
    if d > pca_dim and max_components >= 1:
        X_safe = _robust_scale_clip(X, clip_pct=99.9)
        pca = PCA(
            n_components=int(max_components),
            svd_solver="randomized",
            iterated_power=2,
            random_state=random_state,
        )
        Xp = pca.fit_transform(X_safe)
        bad = ~np.isfinite(Xp)
        if bad.any():
            Xp[bad] = 0.0
        Xp_f64 = Xp
        pca_obj = pca
    else:
        Xp_f64 = _robust_scale_clip(X, clip_pct=99.9)

    k_min = max(2, int(k_min))
    k_max = max(k_min, int(k_max))

    best_model: Optional[MiniBatchKMeans] = None
    best_k = k_min
    best_score = -1.0
    best_metric = "silhouette"

    for k in range(k_min, k_max + 1):
        km = MiniBatchKMeans(
            n_clusters=k,
            batch_size=max(32, min(2048, max(512, n // 10))),
            n_init="auto",
            random_state=random_state,
        )
        labels = km.fit_predict(Xp_f64)

        uniq = np.unique(labels).size
        if uniq < 2 or uniq >= len(labels):
            score = -1.0
            metric = "silhouette"
        else:
            try:
                ss = min(int(sil_sample), n)
                score = silhouette_score(
                    Xp_f64, labels, metric="euclidean", sample_size=ss, random_state=random_state
                )
                metric = "silhouette"
            except Exception:
                score = calinski_harabasz_score(Xp_f64, labels)
                metric = "calinski_harabasz"

        if score > best_score:
            best_score = float(score)
            best_model = km
            best_k = int(k)
            best_metric = metric

    assert best_model is not None
    return best_model, pca_obj, best_k, best_score, best_metric

# ------------------------------------------------
# Public API: label(score_df, ctx, score_out, cfg)
# ------------------------------------------------
def label(score_df, ctx: Dict[str, Any], score_out: Dict[str, Any], cfg: Dict[str, Any]):
    basis_train: Optional[pd.DataFrame] = ctx.get("regime_basis_train")
    basis_score: Optional[pd.DataFrame] = ctx.get("regime_basis_score")
    basis_meta: Dict[str, Any] = ctx.get("basis_meta") or {}
    regime_model: Optional[RegimeModel] = ctx.get("regime_model")
    basis_hash: Optional[int] = ctx.get("regime_basis_hash")

    out = dict(score_out or {})
    frame = out.get("frame")

    if basis_train is not None and basis_score is not None:
        if (
            regime_model is None
            or regime_model.feature_columns != list(basis_train.columns)
            or (basis_hash is not None and regime_model.train_hash != basis_hash)
        ):
            regime_model = fit_regime_model(basis_train, basis_meta, cfg, basis_hash)
        elif regime_model.train_hash is None and basis_hash is not None:
            regime_model.train_hash = basis_hash

        train_labels = predict_regime(regime_model, basis_train)
        score_labels = predict_regime(regime_model, basis_score)
        # Smoothing controls
        smooth_cfg = _cfg_get(cfg, "regimes.smoothing", {}) or {}
        passes = int(smooth_cfg.get("passes", 1))
        min_dwell_samples = int(smooth_cfg.get("min_dwell_samples", 0) or 0)
        min_dwell_seconds = smooth_cfg.get("min_dwell_seconds", None)
        try:
            min_dwell_seconds = float(min_dwell_seconds) if min_dwell_seconds is not None else None
        except Exception:
            min_dwell_seconds = None

        # 1) Label smoothing (median-like)
        train_labels = smooth_labels(train_labels, passes=passes)
        score_labels = smooth_labels(score_labels, passes=passes)
        # 2) Transition smoothing (min dwell)
        train_labels = smooth_transitions(
            train_labels,
            timestamps=basis_train.index if isinstance(basis_train.index, pd.DatetimeIndex) else None,
            min_dwell_samples=min_dwell_samples,
            min_dwell_seconds=min_dwell_seconds,
            health_map=regime_model.health_labels,
        )
        score_labels = smooth_transitions(
            score_labels,
            timestamps=basis_score.index if isinstance(basis_score.index, pd.DatetimeIndex) else None,
            min_dwell_samples=min_dwell_samples,
            min_dwell_seconds=min_dwell_seconds,
            health_map=regime_model.health_labels,
        )
        quality_ok = bool(regime_model.meta.get("quality_ok", True))

        out["regime_model"] = regime_model
        out["regime_labels_train"] = train_labels
        out["regime_labels"] = score_labels
        derived_k = regime_model.meta.get("best_k")
        if derived_k is None:
            derived_k = getattr(regime_model.kmeans, "n_clusters", None)
        out["regime_k"] = int(derived_k) if derived_k is not None else 0
        out["regime_score"] = float(regime_model.meta.get("fit_score", 0.0))
        out["regime_metric"] = str(regime_model.meta.get("fit_metric", "silhouette"))
        centers = np.asarray(regime_model.kmeans.cluster_centers_, dtype=float)
        out["regime_centers"] = _as_f32(centers)
        feature_cols = regime_model.feature_columns
        importance = dict(zip(feature_cols, np.abs(centers).mean(axis=0).tolist())) if centers.size else {}
        regime_model.meta["feature_importance"] = importance
        out["regime_feature_importance"] = importance
        out["regime_quality_ok"] = quality_ok
        out["regime_quality_notes"] = list(regime_model.meta.get("quality_notes", []))
        out["regime_sweep_scores"] = list(regime_model.meta.get("quality_sweep", []))
        if basis_meta:
            out["regime_basis_meta"] = basis_meta
        if "pca_variance_ratio" in regime_model.meta:
            out["regime_pca_variance"] = regime_model.meta.get("pca_variance_ratio")

        if frame is not None:
            frame["regime_label"] = score_labels
            out["frame"] = frame
        return out

    return _legacy_label(score_df, ctx, out, cfg)


def _legacy_label(score_df, ctx: Dict[str, Any], out: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    k_min = _cfg_get(cfg, "regimes.auto_k.k_min", 2)
    k_max = _cfg_get(cfg, "regimes.auto_k.k_max", 6)
    pca_dim = _cfg_get(cfg, "regimes.auto_k.pca_dim", 20)
    sil_sample = _cfg_get(cfg, "regimes.auto_k.sil_sample", 4000)
    random_state = _cfg_get(cfg, "regimes.auto_k.random_state", 17)

    X_score = _finite_impute_inplace(score_df.to_numpy(copy=False))
    raw_train = ctx.get("X_train", None)
    X_train_arr: Optional[np.ndarray] = None
    if raw_train is not None:
        try:
            candidate = getattr(raw_train, "to_numpy", lambda **_: raw_train)(copy=False)
        except Exception:
            candidate = raw_train
        if isinstance(candidate, np.ndarray):
            X_train_arr = _finite_impute_inplace(candidate)

    use_train = isinstance(X_train_arr, np.ndarray) and X_train_arr.ndim == 2 and X_train_arr.shape[0] >= 4
    X_fit = X_train_arr if use_train and X_train_arr is not None else X_score

    model, pca_obj, k, sel_score, metric = _fit_auto_k(
        X_fit,
        k_min=k_min,
        k_max=k_max,
        pca_dim=pca_dim,
        sil_sample=sil_sample,
        random_state=random_state,
    )

    if pca_obj is not None:
        Xs = _robust_scale_clip(X_score, clip_pct=99.9)
        try:
            Xp = pca_obj.transform(Xs)
        except Exception:
            Xp = Xs[:, : int(pca_obj.n_components_)]
        bad = ~np.isfinite(Xp)
        if bad.any():
            Xp[bad] = 0.0
        X_pred = Xp
    else:
        X_pred = _robust_scale_clip(X_score, clip_pct=99.9)

    labels = model.predict(X_pred).astype(np.int32, copy=False)
    if use_train and X_train_arr is not None:
        if pca_obj is not None:
            Xt = _robust_scale_clip(X_train_arr, clip_pct=99.9)
            try:
                Xt = pca_obj.transform(Xt)
            except Exception:
                Xt = Xt[:, : int(pca_obj.n_components_)]
        else:
            Xt = _robust_scale_clip(X_train_arr, clip_pct=99.9)
        out["regime_labels_train"] = model.predict(Xt).astype(np.int32, copy=False)

    out["regime_labels"] = labels
    out["regime_k"] = int(k)
    out["regime_score"] = float(sel_score)
    out["regime_metric"] = str(metric)
    # Smoothing controls
    smooth_cfg = _cfg_get(cfg, "regimes.smoothing", {}) or {}
    passes = int(smooth_cfg.get("passes", 1))
    min_dwell_samples = int(smooth_cfg.get("min_dwell_samples", 0) or 0)
    min_dwell_seconds = smooth_cfg.get("min_dwell_seconds", None)
    try:
        min_dwell_seconds = float(min_dwell_seconds) if min_dwell_seconds is not None else None
    except Exception:
        min_dwell_seconds = None
    labels = smooth_labels(labels, passes=passes)
    out["regime_labels"] = labels
    if "regime_labels_train" in out:
        train_labels = np.asarray(out["regime_labels_train"])  # type: ignore[assignment]
        train_labels = smooth_labels(train_labels, passes=passes)
        out["regime_labels_train"] = train_labels
    # Apply transition smoothing if we have timestamps
    ts_pred = score_df.index if isinstance(score_df.index, pd.DatetimeIndex) else None
    labels = smooth_transitions(labels, timestamps=ts_pred,
                                min_dwell_samples=min_dwell_samples, min_dwell_seconds=min_dwell_seconds)
    out["regime_labels"] = labels
    if "regime_labels_train" in out:
        tr = np.asarray(out["regime_labels_train"])  # type: ignore[assignment]
        ts_train = ctx.get("X_train_index") if isinstance(ctx.get("X_train_index"), pd.DatetimeIndex) else None
        tr = smooth_transitions(tr, timestamps=ts_train,
                                min_dwell_samples=min_dwell_samples, min_dwell_seconds=min_dwell_seconds)
        out["regime_labels_train"] = tr
    out["regime_quality_ok"] = True
    out["regime_centers"] = _as_f32(model.cluster_centers_)
    frame = out.get("frame")
    if frame is not None:
        frame["regime_label"] = labels
        out["frame"] = frame
    return out

# ------------------------------------------------
# Reporting hook: run(ctx)
# ------------------------------------------------
def run(ctx: Any) -> Dict[str, Any]:
    """
    Reporting function for the regime module.
    Generates a plot overlaying episodes on the fused score.
    """
    ep_path = ctx.run_dir / "episodes.csv"
    sc_path = ctx.run_dir / "scores.csv"
    if not ep_path.exists():
        return {"module":"regime","tables":[], "plots":[], "metrics":{},
                "error":{"type":"MissingFile","message":"episodes.csv not found"}}

    eps = _read_episodes_csv(ep_path)
    tables: List[Dict[str, Any]] = []
    t_eps = ctx.tables_dir / "regime_episodes.csv"
    try:
        run_id = getattr(ctx, "run_id", None)
        equip_id = getattr(ctx, "equip_id", None)
        if OutputManager is not None:
            om = OutputManager(sql_client=None, run_id=run_id, equip_id=equip_id, base_output_dir=getattr(ctx, "run_dir", None))
            om.write_dataframe(eps, t_eps)
        else:
            df_out = eps.copy()
            if run_id is not None and "RunID" not in df_out.columns:
                df_out.insert(0, "RunID", run_id)
            if equip_id is not None and "EquipID" not in df_out.columns:
                df_out.insert(1, "EquipID", int(equip_id))
            df_out.to_csv(t_eps, index=False)
    except Exception:
        eps.to_csv(t_eps, index=False)
    tables.append({"name":"regime_episodes","path":str(t_eps)})

    summary_df: Optional[pd.DataFrame] = None
    feature_importance_df: Optional[pd.DataFrame] = None
    transitions_df: Optional[pd.DataFrame] = None
    regime_metrics: Dict[str, Any] = {}
    pca_warning: Optional[str] = None
    pca_coverage_ok: Optional[bool] = None

    models_dir: Optional[Path] = None
    if getattr(ctx, "models_dir", None):
        models_dir = Path(ctx.models_dir)
    elif getattr(ctx, "run_dir", None):
        models_dir = Path(ctx.run_dir) / "models"

    regime_model: Optional[RegimeModel] = None
    if models_dir and models_dir.exists():
        try:
            regime_model = load_regime_model(models_dir)
        except Exception as load_exc:
            Console.warn(f"[REGIME] Failed to load regime model for reporting: {load_exc}")

    if regime_model is not None:
        summary_df = build_summary_dataframe(regime_model)
        if not summary_df.empty:
            summary_path = ctx.tables_dir / "regime_summary.csv"
            summary_df.to_csv(summary_path, index=False)
            tables.append({"name":"regime_summary","path":str(summary_path)})

        feature_map = regime_model.meta.get("feature_importance") or {}
        if feature_map:
            feature_importance_df = (
                pd.DataFrame(
                    [{"feature": str(k), "importance": float(v)} for k, v in feature_map.items()]
                )
                .sort_values("importance", ascending=False)
                .reset_index(drop=True)
            )
            fi_path = ctx.tables_dir / "regime_feature_importance.csv"
            feature_importance_df.to_csv(fi_path, index=False)
            tables.append({"name":"regime_feature_importance","path":str(fi_path)})

        transitions_map = regime_model.meta.get("transition_counts") or {}
        if transitions_map:
            transition_rows: List[Dict[str, Any]] = []
            for key, count in transitions_map.items():
                if "->" in key:
                    src_str, dst_str = key.split("->", 1)
                else:
                    src_str, dst_str = key, ""
                try:
                    src = int(src_str)
                except ValueError:
                    src = src_str
                try:
                    dst = int(dst_str) if dst_str != "" else dst_str
                except ValueError:
                    dst = dst_str
                transition_rows.append({"from_regime": src, "to_regime": dst, "count": int(count)})
            transitions_df = pd.DataFrame(transition_rows)
            trans_path = ctx.tables_dir / "regime_transitions.csv"
            transitions_df.to_csv(trans_path, index=False)
            tables.append({"name":"regime_transitions","path":str(trans_path)})

        meta = regime_model.meta or {}
        best_k = meta.get("best_k")
        fit_score = meta.get("fit_score")
        fit_metric = meta.get("fit_metric")
        quality_ok = meta.get("quality_ok")
        quality_notes = meta.get("quality_notes", [])
        if best_k is not None:
            regime_metrics["regime_best_k"] = float(best_k)
        if fit_score is not None:
            regime_metrics["regime_score"] = float(fit_score)
            if fit_metric == "silhouette":
                regime_metrics["regime_silhouette"] = float(fit_score)
        if quality_ok is not None:
            regime_metrics["regime_quality_ok"] = float(bool(quality_ok))

        pca_ratio = meta.get("pca_variance_ratio")
        if pca_ratio is not None:
            pca_ratio = float(pca_ratio)
            pca_min = meta.get("pca_variance_min")
            coverage_ok = True
            if pca_min is not None:
                pca_min = float(pca_min)
                coverage_ok = pca_ratio >= pca_min
                regime_metrics["pca_variance_target"] = pca_min
            regime_metrics["pca_variance_ratio"] = pca_ratio
            regime_metrics["pca_coverage_ok"] = float(bool(coverage_ok))
            if not coverage_ok:
                regime_metrics["pca_coverage_warning"] = 1.0
                pca_warning = "variance_below_target"
            pca_coverage_ok = bool(coverage_ok)

        if transitions_df is not None and not transitions_df.empty:
            regime_metrics["transition_total"] = int(transitions_df["count"].sum())

        # Consolidated report JSON
        report_payload = {
            "generated_at": pd.Timestamp.utcnow().isoformat(),
            "quality": {
                "best_k": best_k,
                "score": fit_score,
                "metric": fit_metric,
                "quality_ok": bool(quality_ok) if quality_ok is not None else False,
                "quality_notes": quality_notes,
                "pca_variance_ratio": pca_ratio,
                "pca_variance_min": meta.get("pca_variance_min"),
                "pca_coverage_ok": pca_coverage_ok,
                "pca_warning": pca_warning,
            },
            "summary": summary_df.to_dict(orient="records") if summary_df is not None else [],
            "feature_importance": feature_importance_df.to_dict(orient="records") if feature_importance_df is not None else [],
            "transitions": transitions_df.to_dict(orient="records") if transitions_df is not None else [],
        }

        def _json_default(obj: Any) -> Any:
            if isinstance(obj, np.generic):
                if np.issubdtype(obj.dtype, np.floating):
                    return float(obj)
                if np.issubdtype(obj.dtype, np.integer):
                    return int(obj)
                if np.issubdtype(obj.dtype, np.bool_):
                    return bool(obj)
            return obj

        report_path = ctx.tables_dir / "regime_report.json"
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report_payload, f, indent=2, default=_json_default)
        tables.append({"name":"regime_report","path":str(report_path)})
    else:
        # Fallback: preserve existing summary file if already generated elsewhere
        summary_path = ctx.tables_dir / "regime_summary.csv"
        if summary_path.exists() and summary_path.stat().st_size > 0:
            summary_df = pd.read_csv(summary_path)
            tables.append({"name":"regime_summary","path":str(summary_path)})

    plots = []
    if sc_path.exists():
        sc = _read_scores_csv(sc_path)
        if "fused" in sc.columns and len(sc) > 0 and len(eps) > 0:
            fig = plt.figure(figsize=(12,4)); ax = plt.gca()
            sc["fused"].plot(ax=ax, linewidth=1)
            for _, r in eps.iterrows():
                if pd.notna(r["start_ts"]) and pd.notna(r["end_ts"]):
                    ax.axvspan(r["start_ts"], r["end_ts"], alpha=0.15, color="red")
            ax.set_title("Fused score with episode windows")
            ax.set_xlabel("")
            plt.tight_layout()
            p = ctx.plots_dir / "regime_overlay.png"
            fig.savefig(p, dpi=144, bbox_inches="tight"); plt.close(fig)
            plots.append({"title":"Episodes overlay","path":str(p),"caption":"Shaded = episodes"})

    # simple regime stability via episode durations
    eps = eps.sort_values(["start_ts","end_ts"])
    durations = (
        (eps["end_ts"] - eps["start_ts"]).dt.total_seconds().clip(lower=0)
        if not eps.empty else pd.Series([], dtype="float64")
    )
    metrics: Dict[str, float] = {"episode_count": float(len(eps))}
    if summary_df is not None and not summary_df.empty:
        metrics["regime_count"] = float(summary_df["regime"].nunique())
        if "state" in summary_df.columns:
            metrics["critical_regimes"] = float((summary_df["state"] == "critical").sum())
    metrics.update({k: v for k, v in regime_metrics.items() if v is not None})
    if len(durations) >= 4:
        metrics["major_minor_ratio"] = float(
            (durations.quantile(0.75)+1e-9)/(durations.quantile(0.25)+1e-9)
        )

    return {"module":"regime","tables":tables,
            "plots":plots,"metrics":metrics}


# ----------------------------
# Model Persistence Functions
# ----------------------------

def save_regime_model(model: RegimeModel, models_dir: Path) -> None:
    """
    Save regime model with joblib persistence for sklearn objects.
    
    Saves:
    - regime_model.joblib: KMeans and StandardScaler objects
    - regime_model.json: Metadata (feature columns, health labels, stats)
    
    Args:
        model: RegimeModel to persist
        models_dir: Directory for model storage (typically artifacts/{EQUIP}/models)
    """
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Save sklearn objects with joblib
    joblib_path = models_dir / "regime_model.joblib"
    try:
        joblib.dump({
            'scaler': model.scaler,
            'kmeans': model.kmeans,
            'train_hash': model.train_hash,
        }, joblib_path)
        Console.info(f"[REGIME] Saved regime models (KMeans+Scaler) -> {joblib_path}")
    except Exception as e:
        Console.warn(f"[REGIME] Failed to save regime joblib: {e}")
        raise
    
    # Save metadata as JSON
    json_path = models_dir / "regime_model.json"
    model.meta.setdefault("model_version", REGIME_MODEL_VERSION)
    model.meta.setdefault("sklearn_version", sklearn.__version__)

    metadata = {
        "feature_columns": model.feature_columns,
        "raw_tags": model.raw_tags,
        "n_pca_components": model.n_pca_components,
        "train_hash": model.train_hash,
        "health_labels": {str(k): str(v) for k, v in (model.health_labels or {}).items()},
        "stats": {
            str(k): {
                kk: (float(vv) if isinstance(vv, (int, float, np.floating)) else str(vv))
                for kk, vv in stat.items()
            }
            for k, stat in (model.stats or {}).items()
        },
        "meta": model.meta,
    }
    try:
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        Console.info(f"[REGIME] Saved regime metadata -> {json_path}")
    except Exception as e:
        Console.warn(f"[REGIME] Failed to save regime metadata: {e}")
        raise


def load_regime_model(models_dir: Path) -> Optional[RegimeModel]:
    """
    Load regime model from disk.
    
    Loads:
    - regime_model.joblib: KMeans and StandardScaler objects
    - regime_model.json: Metadata
    
    Args:
        models_dir: Directory containing model files
        
    Returns:
        RegimeModel if found and valid, None otherwise
    """
    models_dir = Path(models_dir)
    joblib_path = models_dir / "regime_model.joblib"
    json_path = models_dir / "regime_model.json"
    
    # Check if both files exist
    if not joblib_path.exists():
        Console.info(f"[REGIME] No cached regime model found at {joblib_path}")
        return None
    
    if not json_path.exists():
        Console.warn(f"[REGIME] Regime joblib exists but metadata missing: {json_path}")
        return None
    
    try:
        # Load sklearn objects
        joblib_data = joblib.load(joblib_path)
        scaler = joblib_data['scaler']
        kmeans = joblib_data['kmeans']
        train_hash = joblib_data.get('train_hash')
        
        # Load metadata
        with json_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Reconstruct RegimeModel
        meta = metadata.get("meta", {})
        version = meta.get("model_version")
        if version and version != REGIME_MODEL_VERSION:
            Console.warn(
                f"[REGIME] Cached model version {version} mismatches expected {REGIME_MODEL_VERSION}; skipping load."
            )
            return None
        model = RegimeModel(
            scaler=scaler,
            kmeans=kmeans,
            feature_columns=metadata.get("feature_columns", []),
            raw_tags=metadata.get("raw_tags", []),
            n_pca_components=metadata.get("n_pca_components", 0),
            train_hash=train_hash,
            health_labels={int(k): v for k, v in metadata.get("health_labels", {}).items()},
            stats={int(k): v for k, v in metadata.get("stats", {}).items()},
            meta=meta,
        )
        
        Console.info(f"[REGIME] Loaded cached regime model from {joblib_path}")
        cluster_count = getattr(kmeans, "n_clusters", model.meta.get("best_k"))
        Console.info(
            f"[REGIME]   - K={cluster_count}, features={len(model.feature_columns)}, train_hash={train_hash}"
        )
        return model
        
    except Exception as e:
        Console.warn(f"[REGIME] Failed to load regime model: {e}")
        return None


def detect_transient_states(
    data: pd.DataFrame,
    regime_labels: np.ndarray,
    cfg: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """Classify transient regimes using weighted ROC and a state machine."""

    transient_cfg = (cfg or {}).get("regimes", {}).get("transient_detection", {})
    enabled = transient_cfg.get("enabled", True)

    n_samples = len(data)
    default_states = np.array(["steady"] * n_samples, dtype=object)

    if not enabled:
        Console.info("[TRANSIENT] Detection disabled in config")
        return default_states

    if n_samples == 0:
        return default_states

    roc_window = int(transient_cfg.get("roc_window", 5))
    roc_threshold_high = float(transient_cfg.get("roc_threshold_high", 3.0))
    roc_threshold_trip = float(transient_cfg.get("roc_threshold_trip", 5.0))
    transition_lag = int(transient_cfg.get("transition_lag", 3))
    clip_pct = float(transient_cfg.get("clip_percentile", 99.0))
    sensor_weights_cfg = transient_cfg.get("sensor_weights", {}) or {}

    numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        Console.warn("[TRANSIENT] No numeric columns for ROC calculation")
        return default_states

    weights = np.array([abs(float(sensor_weights_cfg.get(col, 1.0))) for col in numeric_cols], dtype=float)
    if not np.isfinite(weights).all() or weights.sum() <= 0:
        weights = np.ones(len(numeric_cols), dtype=float)
    weights /= weights.sum()

    data_numeric = data[numeric_cols].apply(pd.to_numeric, errors="coerce").ffill().bfill()

    weighted_rocs: List[pd.Series] = []
    for col, weight in zip(numeric_cols, weights):
        series = data_numeric[col]
        diff = series.diff().abs()
        baseline = series.shift(1).abs().clip(lower=1e-9)
        roc = (diff / baseline).replace([np.inf, -np.inf], np.nan)
        if clip_pct < 100.0:
            try:
                upper = float(np.nanpercentile(roc.to_numpy(dtype=float), clip_pct))
                roc = roc.clip(upper=upper)
            except Exception:
                pass
        weighted_rocs.append(roc * weight)

    aggregate_roc = pd.DataFrame(weighted_rocs).sum(axis=0).ffill().bfill().fillna(0.0)
    aggregate_roc_smooth = aggregate_roc.rolling(window=max(2, roc_window), min_periods=1).mean()

    regime_changes = np.zeros(n_samples, dtype=bool)
    if len(regime_labels) == n_samples:
        diffs = np.diff(regime_labels.astype(int), prepend=regime_labels[0])
        regime_changes = diffs != 0

    class _StateMachine:
        def __init__(self, lag: int, history: int):
            self.lag = max(0, int(lag))
            self.history = max(2, int(history))
            self.roc_history: deque[float] = deque(maxlen=self.history)
            self.transient_timer = 0

        def update(self, roc_value: float, changed: bool) -> str:
            self.roc_history.append(float(roc_value))
            trend = 0.0
            if len(self.roc_history) >= 2:
                y = np.array(self.roc_history, dtype=float)
                x = np.arange(len(y), dtype=float)
                try:
                    trend = float(np.polyfit(x, y, 1)[0])
                except Exception:
                    trend = y[-1] - y[0]

            if roc_value >= roc_threshold_trip:
                self.transient_timer = self.lag
                return "trip"

            if roc_value >= roc_threshold_high:
                self.transient_timer = self.lag
                return "startup" if trend >= 0 else "shutdown"

            if self.transient_timer > 0:
                self.transient_timer -= 1
                return "transient"

            if changed:
                self.transient_timer = max(self.lag - 1, 0)
                return "transient"

            return "steady"

    machine = _StateMachine(lag=transition_lag, history=max(roc_window, 5))
    states = np.empty(n_samples, dtype=object)

    for idx in range(n_samples):
        state = machine.update(aggregate_roc_smooth.iloc[idx], bool(regime_changes[idx]))
        states[idx] = state

    state_counts = pd.Series(states).value_counts().to_dict()
    Console.info(f"[TRANSIENT] State distribution: {state_counts}")

    return states




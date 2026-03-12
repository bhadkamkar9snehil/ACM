# core/regimes.py
# Fast + memory-safe regime labeling with auto-k.
# v11.1.0: HDBSCAN as primary clustering for density-based regime detection
from __future__ import annotations
from collections import deque, Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple, Union, TYPE_CHECKING, Callable
import json
try:
    import orjson  # type: ignore
except Exception:
    orjson = None  # type: ignore
import numpy as np
import pandas as pd

# v11.1.0: Removed MiniBatchKMeans - using HDBSCAN (primary) and GMM (fallback) only
from sklearn.mixture import GaussianMixture  # v11.0.1: Probabilistic clustering
from sklearn.metrics import silhouette_score, calinski_harabasz_score, pairwise_distances_argmin
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import sklearn

# v11.1.0: HDBSCAN for density-based clustering (primary method)
try:
    import hdbscan
    HDBSCAN_AVAILABLE = True
except ImportError:
    hdbscan = None  # type: ignore
    HDBSCAN_AVAILABLE = False

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from core.observability import Console, Span
import hashlib
from core.context_engine import (
    apply_transient_state_labels as _context_apply_transient_state_labels,
    build_context_assignment,
    detect_transient_states as _context_detect_transient_states,
    predict_regime_with_confidence as _context_predict_regime_with_confidence,
)
from core.representation_contracts import ContextAssignment
from core.schema_drift_manager import SchemaDriftDecision, classify_regime_basis_drift
from core.structure_encoder import (
    _compute_basis_signature as _structure_compute_basis_signature,
    build_feature_basis as _structure_build_feature_basis,
    select_ewm_monitoring_surface as _structure_select_ewm_monitoring_surface,
    select_tag_agnostic_numeric_surface as _structure_select_tag_agnostic_numeric_surface,
)
from utils.config_dict import cfg_get as _cfg_get

try:
    from scipy.ndimage import median_filter as _median_filter
except Exception:  # pragma: no cover - scipy optional in some deployments
    _median_filter = None

REGIME_MODEL_VERSION = "5.0"  # v11.16.x: tag-agnostic regime surface replaces taxonomy-based basis

# v11.3.1: DEPRECATED - UNKNOWN_REGIME_LABEL (-1) is no longer produced
# Equipment is ALWAYS in some physical operating state. Instead of UNKNOWN:
# - label: Always assigned to nearest cluster (equipment IS in a state)
# - confidence: Low for sparse/novel regions (how sure we are)
# - is_novel: True if point was in sparse region (candidate for new regime discovery)
#
# This constant remains for backward compatibility with legacy code that may
# check for -1, but new code should never produce it.
UNKNOWN_REGIME_LABEL = -1  # DEPRECATED: Do not produce this value

# Tag-agnostic surface defaults for early regime/context inference.
_DEFAULT_SURFACE_MAX_COLS = 24
_DEFAULT_SURFACE_MIN_VALID_FRACTION = 0.60
_DEFAULT_SURFACE_MIN_IQR = 1e-6
_DEFAULT_TRANSIENT_HIGH_Z = 3.0
_DEFAULT_TRANSIENT_TRIP_Z = 5.0

# v11.4.0: HEALTH-STATE FEATURES REMOVED FROM REGIME CLUSTERING
# Regime clustering now uses RAW SENSOR VALUES ONLY.
#
# RATIONALE (v11.4.0 Architectural Fix):
# Using detector z-scores (health indicators) in regime clustering creates
# a CIRCULAR DEPENDENCY that masks degradation:
#   1. Equipment degrades -> detector z-scores rise
#   2. Health-state features cause point to cluster into "new regime"
#   3. New regime gets fresh baseline -> degradation masked
#   4. Equipment appears "healthy in its current regime"
#
# CORRECT ARCHITECTURE:
# - Regimes = HOW equipment operates (load, speed, flow, pressure)
# - Detectors = IF equipment is HEALTHY within that operating mode
# - These are orthogonal concerns and MUST NOT be mixed
#
# Detector z-scores are OUTPUTS of the anomaly detection pipeline,
# not INPUTS to regime clustering.


# TO-DO This is not needed. Need to remove this properly.
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
    "regimes.auto_k.max_models": (int, 1, 50, "Maximum candidate models to evaluate"),
    "regimes.quality.silhouette_min": (float, 0.0, 1.0, "Minimum silhouette score"),
    "regimes.auto_k.max_eval_samples": (int, 100, 20000, "Max samples for auto-k evaluation"),
    "regimes.smoothing.passes": (int, 0, 5, "Number of label smoothing passes"),
    "regimes.smoothing.window": (int, 0, 25, "Smoothing window size"),
    "regimes.transient_detection.roc_window": (int, 2, 500, "Transient ROC window"),
    "regimes.transient_detection.roc_threshold_high": (float, 0.0, 100.0, "Transient high ROC threshold"),
    "regimes.transient_detection.roc_threshold_trip": (float, 0.0, 100.0, "Transient trip ROC threshold"),
    "regimes.health.fused_warn_z": (float, 0.0, 10.0, "Fused Z warn threshold"),
    "regimes.health.fused_alert_z": (float, 0.0, 10.0, "Fused Z alert threshold"),
    # V11: UNKNOWN regime support
    "regimes.unknown.enabled": (bool, False, True, "Enable UNKNOWN regime for low-confidence assignments"),
    "regimes.unknown.distance_percentile": (float, 0.0, 100.0, "Distance percentile threshold for UNKNOWN"),
}

# ----------------------------
# Small helpers / sane defaults
# ----------------------------

def _as_f32(X) -> np.ndarray:
    arr = np.asarray(X)
    if arr.dtype == np.float32 and arr.flags["C_CONTIGUOUS"]:
        return arr
    return np.asarray(arr, dtype=np.float32, order="C")


class _IdentityScaler:
    """No-op scaler used when basis is already normalized."""

    mean_: np.ndarray
    scale_: np.ndarray

    def __init__(self):
        self.mean_ = np.array([], dtype=np.float64)
        self.scale_ = np.array([], dtype=np.float64)

    def fit(self, X):
        return self

    def transform(self, X):
        return np.asarray(X, dtype=np.float64, order="C")

    def fit_transform(self, X):
        return self.transform(X)


def _regime_metadata_dict(model: RegimeModel) -> Dict[str, Any]:
    """Extract metadata dictionary from RegimeModel for JSON serialization."""
    return {
        'model_version': model.meta.get('model_version', REGIME_MODEL_VERSION),
        'sklearn_version': model.meta.get('sklearn_version', sklearn.__version__),
        'feature_columns': model.feature_columns,
        'raw_tags': model.raw_tags,
        'n_pca_components': model.n_pca_components,
        'train_hash': model.train_hash,
        'health_labels': model.health_labels,
        'stats': model.stats,
        'meta': model.meta,
    }


def _stable_int_hash(arr: np.ndarray) -> int:
    """Deterministic hash for arrays to replace non-deterministic builtin hash()."""
    buf = np.ascontiguousarray(arr, dtype=np.float64).tobytes()
    digest = hashlib.md5(buf).digest()
    return int.from_bytes(digest[:8], byteorder="little", signed=False)


# v11.4.0: _add_health_state_features() REMOVED
# This function was deleted because it created circular masking:
#   - Detector z-scores were injected into regime clustering
#   - Degrading equipment clustered into "new regimes"
#   - New regimes got fresh baselines, hiding the degradation
# Regime clustering now uses RAW SENSOR VALUES ONLY (as it should).


def _finite_impute_inplace(X: np.ndarray) -> np.ndarray:
    """Impute non-finite values using ROBUST statistics (median)."""
    X = _as_f32(X)
    nonfinite = ~np.isfinite(X)
    if nonfinite.any():
        X[nonfinite] = np.nan
    # v11.1.3: Use median instead of mean for robust imputation
    col_medians = np.nanmedian(X, axis=0)
    col_medians = np.where(np.isfinite(col_medians), col_medians, 0.0).astype(np.float32)
    nan_mask = np.isnan(X)
    if nan_mask.any():
        X[nan_mask] = np.take(col_medians, np.where(nan_mask)[1])
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
    """
    Estimate per-sample durations in seconds for a time-aligned index.
    
    FIX #2: This is the SINGLE SOURCE OF TRUTH for duration calculations.
    All dwell time metrics (dwell_seconds, dwell_fraction, avg_dwell_seconds)
    should derive from this function's output.
    
    Priority:
    1. If DatetimeIndex: compute actual time diffs in seconds
    2. Fallback: unit durations (1.0 per sample)
    
    Returns:
        Array of durations in seconds for each sample. Last sample uses
        median of valid diffs as its duration estimate.
    """

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
        durations[-1] = fallback if (fallback > 0 and np.isfinite(fallback)) else 0.0
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
    median_var = float(np.median(variances)) if len(variances) else 0.0
    low_var_cols = [
        col for col, var in variances.items()
        if var <= 1e-6 or (median_var > 0 and var / median_var < 0.01)
    ]
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
            # Allow float-stored ints (e.g. auto-tune writes k_max=12.0 as float)
            if expected_type is int and isinstance(value, float) and value == int(value):
                value = int(value)
            else:
                issues.append(f"Config {path} expected {expected_type.__name__}, got {type(value).__name__}")
                continue
        if expected_type is bool:
            continue
        if isinstance(value, (int, float)) and not (low <= value <= high):
            issues.append(f"Config {path}={value} outside expected range [{low}, {high}]")
    return issues

# ----------------------------
# Regime model container
# ----------------------------
@dataclass
class RegimeModel:
    """Container for fitted regime clustering model.
    
    v11.1.0: Supports HDBSCAN (primary) and GMM (fallback) only.
    HDBSCAN provides density-based clustering with native noise handling (label=-1).
    
    v11.1.8: ENSEMBLE MODE - HDBSCAN + GMM fallback for noise points.
    When HDBSCAN marks a point as noise (low strength), GMM assigns it to
    the nearest cluster instead of marking UNKNOWN. This ensures ALL points
    get a regime assignment while still benefiting from HDBSCAN's density-based
    cluster discovery.
    
    K-Means has been removed as of v11.1.0 - HDBSCAN and GMM are superior for
    industrial regime detection due to varying density handling and probabilistic
    assignment capabilities.
    """
    scaler: Union[StandardScaler, "_IdentityScaler"]  # Can be either StandardScaler or _IdentityScaler
    clustering_model: Any  # v11.1.0: HDBSCAN or GaussianMixture
    feature_columns: List[str]
    raw_tags: List[str]
    n_pca_components: int
    train_hash: Optional[int] = None
    health_labels: Dict[int, str] = field(default_factory=dict)
    stats: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
    # v11.1.0: Store exemplar points for HDBSCAN (needed for prediction)
    exemplars_: Optional[np.ndarray] = None
    # v11.1.6 FIX #3: Training-derived acceptance thresholds for UNKNOWN detection
    training_distance_threshold_: Optional[float] = None  # P95 of training distances
    training_distance_distribution_: Optional[np.ndarray] = None  # For diagnostic
    # v11.1.6 FIX #4: Stable label mapping for HDBSCAN (new_label -> stable_label)
    label_map_: Optional[Dict[int, int]] = None
    # v11.1.8: Fallback GMM model for HDBSCAN noise points (ensemble clustering)
    fallback_model_: Optional[GaussianMixture] = None
    # v11.4.0: Normal regime identification (highest dwell + lowest anomaly)
    normal_regime_label_: Optional[int] = None  # Identified "Normal" regime
    regime_semantic_labels_: Dict[int, str] = field(default_factory=dict)  # label -> name
    # v11.4.0: Optional PCA model for dimensionality reduction
    pca: Optional[PCA] = None
    
    @property
    def cluster_centers_(self) -> np.ndarray:
        """Get cluster centers regardless of model type."""
        if self.is_hdbscan and self.exemplars_ is not None:
            # HDBSCAN: Use computed centroids from exemplars
            return np.asarray(self.exemplars_, dtype=np.float64)
        elif hasattr(self.clustering_model, 'cluster_centers_'):
            return np.asarray(self.clustering_model.cluster_centers_, dtype=np.float64)
        elif hasattr(self.clustering_model, 'means_'):
            # GaussianMixture uses means_ instead of cluster_centers_
            return np.asarray(self.clustering_model.means_, dtype=np.float64)
        return np.empty((0, 0), dtype=np.float64)
    
    @property
    def n_clusters(self) -> int:
        """Get number of clusters (excludes noise for HDBSCAN)."""
        if self.is_hdbscan:
            labels = getattr(self.clustering_model, 'labels_', np.array([]))
            unique = np.unique(labels)
            # Exclude noise (-1) from count
            return int(len(unique[unique >= 0]))
        elif hasattr(self.clustering_model, 'n_components'):
            return int(self.clustering_model.n_components)  # GMM uses n_components
        return 0
    
    @property
    def is_gmm(self) -> bool:
        """Check if model uses GMM (GaussianMixture)."""
        return isinstance(self.clustering_model, GaussianMixture)
    
    @property
    def is_hdbscan(self) -> bool:
        """Check if model uses HDBSCAN."""
        if not HDBSCAN_AVAILABLE or hdbscan is None:
            return False
        return isinstance(self.clustering_model, hdbscan.HDBSCAN)
    
    def set_cluster_centers_(self, centers: np.ndarray) -> None:
        """Set cluster centers for GMM model.
        
        For GMM: sets means_ attribute
        For HDBSCAN: sets exemplars_ attribute
        
        Note: This modifies the underlying model in-place.
        """
        if self.is_gmm:
            self.clustering_model.means_ = np.asarray(centers, dtype=np.float64)
        elif self.is_hdbscan:
            self.exemplars_ = np.asarray(centers, dtype=np.float64)
    
    @property
    def model(self) -> Any:
        """Get the underlying clustering model (HDBSCAN or GMM).
        
        v11.1.0: Alias for clustering_model attribute.
        """
        return self.clustering_model
    
    def apply_label_map(self, labels: np.ndarray) -> np.ndarray:
        """
        Apply stable label mapping to predicted labels.
        
        v11.1.6 FIX #4: Ensures consistent label semantics across refits.
        HDBSCAN cluster indices can permute between fits; this maps them
        to stable identifiers.
        
        Args:
            labels: Raw predicted labels from clustering model
            
        Returns:
            Labels with mapping applied (if label_map_ exists)
        """
        if self.label_map_ is None or len(self.label_map_) == 0:
            return labels
        
        result = labels.copy()
        for old_label, new_label in self.label_map_.items():
            mask = labels == old_label
            result[mask] = new_label
        return result


def _compute_training_distances(
    model: RegimeModel,
    train_basis: pd.DataFrame,
    distance_percentile: float = 95.0,
) -> Tuple[float, np.ndarray]:
    """
    Compute training-derived distance threshold for UNKNOWN detection.
    
    v11.1.6 FIX #3: Calibrated acceptance region based on training data.
    
    The correct question for UNKNOWN assignment is:
    "Is this point sufficiently close to the training support of any regime?"
    
    This function computes:
    1. Distance from each training point to its assigned cluster center
    2. The P95 (or configured percentile) of these distances as threshold
    
    Points beyond this threshold during scoring are marked UNKNOWN.
    
    Args:
        model: Fitted RegimeModel with scaler and centers
        train_basis: Training data used to fit the model
        distance_percentile: Percentile for threshold (default 95)
        
    Returns:
        Tuple of (threshold, all_distances)
    """
    # Align and scale training data
    aligned = train_basis.reindex(columns=model.feature_columns, fill_value=0.0)
    aligned_arr = aligned.to_numpy(dtype=np.float64, copy=False, na_value=0.0)
    X_scaled = model.scaler.transform(aligned_arr)
    
    centers = model.cluster_centers_
    if centers.size == 0:
        return float("inf"), np.array([])
    
    # Compute distance to nearest center for each training point
    if model.is_hdbscan:
        # For HDBSCAN: use training labels if available
        if hasattr(model.clustering_model, 'labels_') and len(model.clustering_model.labels_) == len(X_scaled):
            train_labels = model.clustering_model.labels_
            # Compute distance to assigned center (excluding noise points)
            distances = np.full(len(X_scaled), np.nan)
            for i, (x, label) in enumerate(zip(X_scaled, train_labels)):
                if label >= 0 and label < len(centers):
                    distances[i] = np.linalg.norm(x - centers[label])
            distances = distances[np.isfinite(distances)]
        else:
            # Fallback: distance to nearest center
            distances = np.min(np.linalg.norm(X_scaled[:, np.newaxis] - centers, axis=2), axis=1)
    else:
        # For GMM: use predicted labels
        labels = model.clustering_model.predict(X_scaled)
        distances = np.array([
            np.linalg.norm(X_scaled[i] - centers[labels[i]])
            for i in range(len(X_scaled))
        ])
    
    if len(distances) == 0:
        return float("inf"), np.array([])
    
    threshold = float(np.percentile(distances, distance_percentile))
    
    Console.info(
        f"Training distance threshold (P{distance_percentile:.0f}): {threshold:.4f} "
        f"(range: {np.min(distances):.4f} - {np.max(distances):.4f})",
        component="REGIME"
    )
    
    return threshold, distances


def select_tag_agnostic_numeric_surface(
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    cfg: Optional[Dict[str, Any]] = None,
    *,
    max_cols: Optional[int] = None,
    min_valid_fraction: Optional[float] = None,
    min_iqr: Optional[float] = None,
) -> Tuple[List[str], pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Compatibility wrapper; structure encoding now lives in core.structure_encoder."""
    return _structure_select_tag_agnostic_numeric_surface(
        train_df,
        score_df,
        cfg=cfg,
        max_cols=max_cols,
        min_valid_fraction=min_valid_fraction,
        min_iqr=min_iqr,
    )


def select_ewm_monitoring_surface(
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    cfg: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Compatibility wrapper; structure encoding now lives in core.structure_encoder."""
    return _structure_select_ewm_monitoring_surface(train_df, score_df, cfg=cfg)


def _compute_basis_signature(feature_columns: List[str], scaler_mean: Optional[List[float]], 
                              scaler_var: Optional[List[float]], n_pca: int) -> str:
    """Compatibility wrapper; basis signatures now live in core.structure_encoder."""
    return _structure_compute_basis_signature(feature_columns, scaler_mean, scaler_var, n_pca)


def build_feature_basis(
    train_features: pd.DataFrame,
    score_features: pd.DataFrame,
    raw_train: Optional[pd.DataFrame],
    raw_score: Optional[pd.DataFrame],
    pca_detector: Optional[Any],
    cfg: Dict[str, Any],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Compatibility wrapper; structure encoding now lives in core.structure_encoder."""
    return _structure_build_feature_basis(
        train_features=train_features,
        score_features=score_features,
        raw_train=raw_train,
        raw_score=raw_score,
        pca_detector=pca_detector,
        cfg=cfg,
    )



# v11.1.0: Removed _fit_kmeans_scaled - using HDBSCAN (primary) and GMM (fallback) only

def _fit_gmm_scaled(
    X: np.ndarray,
    cfg: Dict[str, Any],
    *,
    pre_scaled: bool = False,
) -> Tuple[Union[StandardScaler, "_IdentityScaler"], Optional[GaussianMixture], int, float, str, List[Tuple[int, float]], bool]:
    """Fit GaussianMixture with auto-k selection using BIC scoring.
    
    v11.1.0: GMM is the fallback after HDBSCAN. Used when:
    1. HDBSCAN fails or produces poor quality clusters
    2. Need explicit n_clusters control
    
    Returns:
        Tuple of (scaler, gmm_model, best_k, best_bic, metric_name, all_scores, low_quality)
    """
    X = _finite_impute_inplace(X)
    if pre_scaled:
        scaler = _IdentityScaler()
        X_scaled = scaler.transform(X)
    else:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

    n_samples, n_features = X_scaled.shape
    if n_samples == 0:
        raise ValueError("Cannot fit regime model on an empty dataset")
    if n_samples < 2:
        raise ValueError(f"Cannot fit regime model with fewer than 2 samples (got {n_samples})")

    k_min = int(_cfg_get(cfg, "regimes.auto_k.k_min", 2))
    k_max = int(_cfg_get(cfg, "regimes.auto_k.k_max", 6))
    max_eval_samples = int(_cfg_get(cfg, "regimes.auto_k.max_eval_samples", 5000))
    random_state = int(_cfg_get(cfg, "regimes.auto_k.random_state", 17))
    
    # GMM-specific config with sensible defaults
    gmm_cfg = _cfg_get(cfg, "regimes.gmm", {}) or {}
    covariance_type = str(gmm_cfg.get("covariance_type", "diag"))  # diag is faster and regularized
    max_iter = int(gmm_cfg.get("max_iter", 100))
    n_init = int(gmm_cfg.get("n_init", 5))
    reg_covar = float(gmm_cfg.get("reg_covar", 1e-4))  # Regularization for numerical stability

    if n_samples < k_min:
        k_min = max(2, n_samples) if n_samples >= 2 else 1
    if k_max < k_min:
        k_max = k_min
    # Limit k_max based on sample size (GMM needs at least k samples per component)
    k_max = min(k_max, n_samples // 3) if n_samples >= 6 else min(k_max, 2)
    k_max = max(k_max, k_min)

    # Sample for evaluation if too large
    if n_samples > max_eval_samples:
        rng = np.random.default_rng(random_state)
        eval_idx = rng.choice(n_samples, size=max_eval_samples, replace=False)
        X_eval = X_scaled[eval_idx]
    else:
        X_eval = X_scaled

    best_bic = np.inf
    best_k = max(2, k_min)
    best_model_eval: Optional[GaussianMixture] = None
    all_scores: List[Tuple[int, float]] = []
    bic_scores: List[Tuple[int, float]] = []

    for k in range(max(2, k_min), k_max + 1):
        if X_eval.shape[0] <= k * 2:  # Need at least 2 samples per component
            continue
        try:
            # Cast covariance_type to Literal for type checker
            cov_type: Literal['full', 'tied', 'diag', 'spherical'] = covariance_type if covariance_type in ('full', 'tied', 'diag', 'spherical') else 'diag'  # type: ignore[assignment]
            gmm = GaussianMixture(
                n_components=k,
                covariance_type=cov_type,
                max_iter=max_iter,
                n_init=n_init,
                random_state=random_state,
                reg_covar=reg_covar,
            )
            gmm.fit(X_eval)
            
            # BIC: lower is better (unlike silhouette where higher is better)
            bic = gmm.bic(X_eval)
            bic_scores.append((k, float(bic)))
            all_scores.append((k, float(-bic)))  # Negate for consistency with silhouette
            
            if bic < best_bic:
                best_bic = bic
                best_k = k
                best_model_eval = gmm
        except Exception as e:
            Console.warn(f"GMM fitting failed for k={k}: {e}", component="REGIME")
            continue

    low_quality = False
    if best_model_eval is None:
        # GMM failed - no fallback, raise error
        Console.error(
            f"GMM auto-k selection failed for all k in [{k_min}, {k_max}]; no valid model produced.",
            component="REGIME", k_min=k_min, k_max=k_max, n_samples=n_samples
        )
        return scaler, None, 0, float("nan"), "gmm_failed", all_scores, True

    # Check for quality issues using BIC delta (large BIC = poor fit)
    if len(bic_scores) >= 2:
        bic_values = [s for _, s in bic_scores]
        bic_range = max(bic_values) - min(bic_values)
        # If BIC values are all very similar, clustering may not be meaningful
        if bic_range < 10:
            low_quality = True
            Console.warn(
                f"BIC values have low variance ({bic_range:.1f}), suggesting weak cluster structure.",
                component="REGIME", bic_range=bic_range, best_k=best_k
            )

    # Refit on full data with best k
    cov_type_final: Literal['full', 'tied', 'diag', 'spherical'] = covariance_type if covariance_type in ('full', 'tied', 'diag', 'spherical') else 'diag'  # type: ignore[assignment]
    best_model = GaussianMixture(
        n_components=best_k,
        covariance_type=cov_type_final,
        max_iter=max_iter * 2,  # More iterations for final fit
        n_init=n_init * 2,  # More restarts for final fit
        random_state=random_state,
        reg_covar=reg_covar,
    )
    best_model.fit(X_scaled)

    score_str = f"{best_bic:.1f}"
    Console.info(
        f"GMM auto-k selection complete: k={best_k}, BIC={score_str}, covariance={covariance_type}.",
        component="REGIME"
    )
    if bic_scores:
        formatted = ", ".join(f"k={k}: {bic:.1f}" for k, bic in sorted(bic_scores))
        Console.info(f"BIC sweep: {formatted}", component="REGIME")

    # Return negative BIC as "score" for consistency with other metrics (higher = better)
    return scaler, best_model, int(best_k), float(-best_bic), "bic", all_scores, low_quality


def _compute_hdbscan_centroids(X: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Compute cluster centroids from HDBSCAN labels for prediction.
    
    HDBSCAN doesn't store centroids, so we compute them as mean of cluster members.
    Noise points (label=-1) are excluded.
    
    Returns:
        Array of shape (n_clusters, n_features) with centroid positions
    """
    unique_labels = np.unique(labels)
    # Exclude noise (-1)
    cluster_labels = unique_labels[unique_labels >= 0]
    
    if len(cluster_labels) == 0:
        return np.empty((0, X.shape[1]), dtype=np.float64)
    
    centroids = np.zeros((len(cluster_labels), X.shape[1]), dtype=np.float64)
    for i, label in enumerate(cluster_labels):
        mask = labels == label
        centroids[i] = X[mask].mean(axis=0)
    
    return centroids


def _fit_hdbscan_scaled(
    X: np.ndarray,
    cfg: Dict[str, Any],
    *,
    pre_scaled: bool = False,
) -> Tuple[Union[StandardScaler, "_IdentityScaler"], Any, int, float, str, List[Tuple[Union[str, int], float]], bool, np.ndarray]:
    """Fit HDBSCAN clustering for regime detection.
    
    v11.1.0: HDBSCAN is preferred for industrial regime detection because:
    1. No k specification needed - auto-detects optimal clusters
    2. Native noise handling - outliers labeled as -1 (UNKNOWN_REGIME)
    3. Handles varying density clusters (common in operational regimes)
    4. Robust to outliers - won't distort regime boundaries
    5. Hierarchical - provides cluster stability/persistence metrics
    
    v11.1.7: Added subsampling for large datasets to prevent O(n^2) memory issues
    
    Args:
        X: Feature matrix (n_samples, n_features)
        cfg: Configuration dictionary
        pre_scaled: Whether data is already scaled
        
    Returns:
        Tuple of (scaler, hdbscan_model, n_clusters, quality_score, metric_name, 
                  quality_sweep, low_quality, cluster_centroids)
    """
    if not HDBSCAN_AVAILABLE:
        raise ImportError("hdbscan package not installed")
    
    # Type assertion: hdbscan module is guaranteed available after the above check
    assert hdbscan is not None, "hdbscan should be available here"
    
    X = _finite_impute_inplace(X)
    if pre_scaled:
        scaler = _IdentityScaler()
        X_scaled = scaler.transform(X)
    else:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
    
    n_samples, n_features = X_scaled.shape
    
    # v11.1.7: PERFORMANCE FIX - Subsample for large datasets
    # HDBSCAN has O(n^2) memory/time complexity, becomes very slow >10k samples
    hdb_cfg = _cfg_get(cfg, "regimes.hdbscan", {}) or {}
    max_fit_samples = int(hdb_cfg.get("max_fit_samples", 8000))  # Cap at 8k for reasonable performance
    
    subsample_indices = None
    if n_samples > max_fit_samples:
        Console.info(f"Subsampling for HDBSCAN: {n_samples} -> {max_fit_samples} samples", component="REGIME")
        # v11.3.1 FIX: TIME-STRATIFIED subsampling to preserve rare regime structure
        # Random subsampling can fragment short-lived regimes (startup/shutdown)
        # by scattering their samples across the subsample, breaking density connectivity.
        # Time-stratified sampling takes proportional samples from each time window,
        # ensuring short events remain contiguous in the subsample.
        np.random.seed(42)
        
        # Divide into time windows and sample proportionally from each
        n_windows = min(100, max(10, n_samples // 500))  # 10-100 windows
        window_size = n_samples // n_windows
        samples_per_window = max_fit_samples // n_windows
        
        subsample_indices = []
        for w in range(n_windows):
            start = w * window_size
            end = min(start + window_size, n_samples) if w < n_windows - 1 else n_samples
            window_n = end - start
            
            # Take proportional samples from this window, preserving contiguity
            # For small windows (potential transients), take MORE samples
            n_take = min(window_n, max(samples_per_window, window_n // 2))
            
            if n_take >= window_n:
                # Take all samples from this window
                subsample_indices.extend(range(start, end))
            else:
                # Subsample with contiguous bias: prefer keeping runs together
                # Use regular spacing instead of random to preserve temporal structure
                step = window_n / n_take
                for i in range(n_take):
                    subsample_indices.append(start + int(i * step))
        
        # Deduplicate and sort
        subsample_indices = sorted(set(subsample_indices))
        
        # Trim to max_fit_samples if we overshot
        if len(subsample_indices) > max_fit_samples:
            step = len(subsample_indices) / max_fit_samples
            subsample_indices = [subsample_indices[int(i * step)] for i in range(max_fit_samples)]
        
        subsample_indices = np.array(subsample_indices)
        X_fit = X_scaled[subsample_indices]
        
        Console.info(
            f"Time-stratified subsampling: {n_samples} -> {len(subsample_indices)} samples "
            f"across {n_windows} windows",
            component="REGIME"
        )
    else:
        X_fit = X_scaled
    
    n_fit_samples = len(X_fit)
    if n_fit_samples == 0:
        raise ValueError("Cannot fit regime model on an empty dataset")
    if n_fit_samples < 10:
        raise ValueError(f"HDBSCAN requires at least 10 samples (got {n_fit_samples})")
    
    # HDBSCAN config with sensible defaults for industrial data
    # v11.3.1 FIX: Use ABSOLUTE min_cluster_size, not percentage-based
    #
    # PROBLEM with percentage-based (5% of data):
    #   - 100,000 samples -> 5000 min_cluster -> startup (500 pts) = NOISE
    #   - Rare regimes get absorbed into dominant clusters or labeled noise
    #
    # SOLUTION: Absolute threshold preserves rare regimes
    #   - min_cluster_size = 30-50 allows startup/shutdown clusters to form
    #   - Configurable via regimes.hdbscan.min_cluster_size_absolute
    #
    # RATIONALE:
    #   - Startup event = ~10-30 minutes = 10-180 samples (at 1/min to 1/10s)
    #   - We want at least 30 samples to form a stable cluster
    #   - Upper cap of 100 prevents requiring too many samples
    #
    absolute_min_cluster = int(hdb_cfg.get("min_cluster_size_absolute", 30))
    max_min_cluster = int(hdb_cfg.get("min_cluster_size_max", 100))
    
    # Use absolute threshold, capped at max
    default_min_cluster = min(absolute_min_cluster, max_min_cluster)
    min_cluster_size = int(hdb_cfg.get("min_cluster_size", default_min_cluster))
    
    # min_samples: samples in neighborhood for core point (controls noise sensitivity)
    # Lower value = more points become core points = better for detecting small clusters
    # v11.3.1: Reduced default from min_cluster_size//5 to max(3, min_cluster_size//10)
    # to improve sensitivity to transient regimes
    min_samples = int(hdb_cfg.get("min_samples", max(3, min_cluster_size // 10)))
    cluster_selection_epsilon = float(hdb_cfg.get("cluster_selection_epsilon", 0.0))
    cluster_selection_method = str(hdb_cfg.get("cluster_selection_method", "eom"))
    metric = str(hdb_cfg.get("metric", "euclidean"))
    allow_single_cluster = bool(hdb_cfg.get("allow_single_cluster", True))
    
    # Ensure min_cluster_size doesn't exceed sample count, but keep absolute floor
    min_cluster_size = min(min_cluster_size, max(absolute_min_cluster, n_fit_samples // 3))
    min_samples = min(min_samples, min_cluster_size)
    
    Console.info(
        f"HDBSCAN config: min_cluster_size={min_cluster_size}, min_samples={min_samples}, "
        f"method={cluster_selection_method}, metric={metric}",
        component="REGIME"
    )
    
    try:
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            cluster_selection_epsilon=cluster_selection_epsilon,
            cluster_selection_method=cluster_selection_method,
            metric=metric,
            allow_single_cluster=allow_single_cluster,
            gen_min_span_tree=True,  # For stability metrics
            prediction_data=True,  # Enable approximate_predict for scoring
        )
        clusterer.fit(X_fit)  # v11.1.7: Fit on subsampled data
        
        labels = clusterer.labels_
        unique_labels = np.unique(labels)
        n_clusters = len(unique_labels[unique_labels >= 0])
        n_noise = int(np.sum(labels == -1))
        noise_ratio = n_noise / n_fit_samples
        
        Console.info(
            f"HDBSCAN found {n_clusters} clusters, {n_noise} noise points ({noise_ratio:.1%})",
            component="REGIME"
        )
        
        # Quality metrics for HDBSCAN
        quality_score = 0.0
        quality_metric = "hdbscan_validity"
        quality_sweep: List[Tuple[Union[str, int], float]] = []
        
        # DBCV score (Density-Based Clustering Validation) - preferred for HDBSCAN
        try:
            validity_score = clusterer.relative_validity_
            if np.isfinite(validity_score):
                quality_score = float(validity_score)
                quality_metric = "dbcv"
                quality_sweep.append(("dbcv", quality_score))
        except Exception:
            pass
        
        # Cluster persistence (stability scores from condensed tree)
        try:
            if hasattr(clusterer, 'cluster_persistence_'):
                persistence = clusterer.cluster_persistence_
                if len(persistence) > 0:
                    avg_persistence = float(np.mean(persistence))
                    quality_sweep.append(("persistence", avg_persistence))
                    # Combine DBCV and persistence
                    if quality_score > 0:
                        quality_score = (quality_score + avg_persistence) / 2
                    else:
                        quality_score = avg_persistence
                        quality_metric = "persistence"
        except Exception:
            pass
        
        # Fallback: use silhouette on non-noise points if enough clusters
        # BUGFIX v11.1.5: Penalize by noise ratio to avoid selection bias
        # Excluding noise points inflates the silhouette score artificially
        if quality_score == 0.0 and n_clusters >= 2:
            non_noise_mask = labels >= 0
            if np.sum(non_noise_mask) > n_clusters + 1:
                try:
                    sil_non_noise = silhouette_score(X_fit[non_noise_mask], labels[non_noise_mask])
                    # Penalize by noise ratio: if 30% noise, score drops by 30%
                    adjusted_sil = sil_non_noise * (1.0 - noise_ratio)
                    quality_score = float(adjusted_sil)
                    quality_metric = "silhouette_noise_adjusted"
                    quality_sweep.append(("silhouette_raw", float(sil_non_noise)))
                    quality_sweep.append(("silhouette_adjusted", quality_score))
                except Exception:
                    pass
        
        # Low quality if: no clusters, or too much noise, or low validity
        low_quality = False
        quality_notes = []
        
        if n_clusters == 0:
            low_quality = True
            quality_notes.append("no_clusters_found")
        if noise_ratio > 0.5:  # v11.1.7: Reduced from 0.6 to 0.5
            low_quality = True
            quality_notes.append(f"high_noise_ratio_{noise_ratio:.1%}")
        if quality_score < 0.05 and n_clusters > 1:
            low_quality = True
            quality_notes.append(f"low_validity_{quality_score:.3f}")
        
        if low_quality and quality_notes:
            Console.warn(
                f"HDBSCAN quality issues: {', '.join(quality_notes)}",
                component="REGIME"
            )
        
        # Compute cluster centroids for prediction (HDBSCAN doesn't store these)
        # v11.1.7: Use X_fit (subsampled) for centroid computation
        cluster_centroids = _compute_hdbscan_centroids(X_fit, labels)
        
        Console.info(
            f"HDBSCAN complete: {n_clusters} clusters, validity={quality_score:.3f} ({quality_metric})",
            component="REGIME"
        )
        
        return scaler, clusterer, n_clusters, quality_score, quality_metric, quality_sweep, low_quality, cluster_centroids
        
    except Exception as e:
        Console.error(f"HDBSCAN fitting failed: {e}", component="REGIME")
        raise


def fit_regime_model(
    train_basis: pd.DataFrame,
    basis_meta: Dict[str, Any],
    cfg: Dict[str, Any],
    train_hash: Optional[int],
) -> RegimeModel:
    """Fit regime clustering model using HDBSCAN (primary) or GMM (fallback).
    
    v11.1.0: Uses HDBSCAN for density-based clustering as primary method.
    Falls back to GMM if HDBSCAN fails or produces poor quality.
    
    HDBSCAN advantages for industrial regime detection:
    - No k specification needed (auto-detects)
    - Native noise handling (outliers labeled as -1 = UNKNOWN_REGIME)
    - Handles varying density clusters
    - Robust to outliers
    
    GMM advantages as fallback:
    - Probabilistic soft assignments
    - Works well with lower sample counts
    - Provides predict_proba for confidence
    """
    with Span("regimes.fit", n_samples=len(train_basis), n_features=train_basis.shape[1] if len(train_basis) > 0 else 0):
        input_issues = _validate_regime_inputs(train_basis, "train_basis")
        config_issues = _validate_regime_config(cfg)
        for issue in input_issues:
            Console.warn(f"Input validation: {issue}", component="REGIME", n_samples=len(train_basis), n_features=train_basis.shape[1] if len(train_basis) > 0 else 0)

    # v11.1.0: Clustering method preference - HDBSCAN is primary
    clustering_cfg = _cfg_get(cfg, "regimes.clustering", {}) or {}
    clustering_method = str(clustering_cfg.get("method", "hdbscan")).lower()
    use_gmm_fallback = bool(clustering_cfg.get("use_gmm_fallback", True))
    
    model = None
    exemplars = None
    scaler = None
    best_k = 0
    best_score = float("nan")
    best_metric = "none"
    quality_sweep: List[Tuple[Any, float]] = []
    low_quality = False
    fallback_gmm: Optional[GaussianMixture] = None  # v11.1.8: Ensemble fallback for HDBSCAN noise
    
    # ========== TRY HDBSCAN FIRST (Primary) ==========
    if clustering_method == "hdbscan" and HDBSCAN_AVAILABLE and len(train_basis) >= 10:
        try:
            Console.info("Using HDBSCAN clustering (primary method)", component="REGIME")
            (
                scaler,
                hdb_model,
                best_k,
                best_score,
                best_metric,
                quality_sweep,
                low_quality,
                exemplars,
            ) = _fit_hdbscan_scaled(
                train_basis.to_numpy(dtype=float, copy=False),
                cfg,
                pre_scaled=bool(basis_meta.get("basis_normalized", False)),
            )
            
            if hdb_model is not None and best_k >= 1:
                model = hdb_model
                hdbscan_scaler = scaler  # Keep reference for GMM fallback
                basis_meta["clustering_method"] = "hdbscan"
                basis_meta["hdbscan_n_clusters"] = best_k
                basis_meta["hdbscan_noise_count"] = int(np.sum(hdb_model.labels_ == -1))
                basis_meta["hdbscan_noise_ratio"] = float(np.sum(hdb_model.labels_ == -1) / len(hdb_model.labels_))
                
                # v11.1.8: ENSEMBLE MODE - Fit GMM fallback for noise point assignment
                # When HDBSCAN marks a point as noise/low-strength, GMM assigns it
                fallback_cfg = _cfg_get(cfg, "regimes.clustering", {}) or {}
                use_ensemble = bool(fallback_cfg.get("use_ensemble_fallback", True))
                if use_ensemble and best_k >= 1:
                    try:
                        X_arr = train_basis.to_numpy(dtype=float, copy=False)
                        X_arr = _finite_impute_inplace(X_arr)
                        X_scaled = hdbscan_scaler.transform(X_arr)
                        
                        # Fit GMM with same k as HDBSCAN found
                        from sklearn.mixture import GaussianMixture
                        fallback_gmm = GaussianMixture(
                            n_components=best_k,
                            covariance_type="full",
                            n_init=3,
                            max_iter=200,
                            random_state=42,
                        )
                        fallback_gmm.fit(X_scaled)
                        basis_meta["ensemble_fallback"] = "gmm"
                        basis_meta["ensemble_gmm_converged"] = bool(fallback_gmm.converged_)
                        Console.info(
                            f"Noise assignment: fitted GMM(k={best_k}) to reassign HDBSCAN noise points to nearest cluster",
                            component="REGIME"
                        )
                    except Exception as gmm_e:
                        Console.warn(f"GMM fallback fitting failed: {gmm_e}", component="REGIME")
                        fallback_gmm = None
                else:
                    fallback_gmm = None
                
                # If HDBSCAN produced low quality AND we have GMM fallback, try GMM
                if low_quality and use_gmm_fallback:
                    Console.warn(
            "HDBSCAN produced low-quality clustering (silhouette/BIC below threshold). "
            "Switching to GMM fallback for regime detection.",
            component="REGIME",
        )
                    model = None
                    exemplars = None
                    fallback_gmm = None  # Clear ensemble if switching to pure GMM
                    
        except Exception as e:
            Console.warn(f"HDBSCAN clustering failed: {e}. Falling back to GMM.", component="REGIME")
            model = None
            fallback_gmm = None
    elif clustering_method == "hdbscan" and not HDBSCAN_AVAILABLE:
        Console.warn(
            "HDBSCAN requested (regimes.clustering.method=hdbscan) but hdbscan package is not installed. "
            "Install with: pip install hdbscan. Falling back to GMM.",
            component="REGIME",
        )
    elif clustering_method == "hdbscan" and len(train_basis) < 10:
        Console.warn(f"Too few samples ({len(train_basis)}) for HDBSCAN. Falling back to GMM.", component="REGIME")
    
    # ========== TRY GMM AS FALLBACK ==========
    if model is None and (use_gmm_fallback or clustering_method == "gmm"):
        try:
            Console.info("Using GMM clustering for regime detection.", component="REGIME")
            (
                scaler,
                gmm_model,
                best_k,
                best_score,
                best_metric,
                quality_sweep,
                low_quality,
            ) = _fit_gmm_scaled(
                train_basis.to_numpy(dtype=float, copy=False),
                cfg,
                pre_scaled=bool(basis_meta.get("basis_normalized", False)),
            )
            
            if gmm_model is not None:
                model = gmm_model
                basis_meta["clustering_method"] = "gmm"
                try:
                    basis_meta["gmm_converged"] = bool(gmm_model.converged_)
                    basis_meta["gmm_n_iter"] = int(gmm_model.n_iter_)
                    basis_meta["gmm_bic"] = float(-best_score)  # Un-negate BIC
                except Exception:
                    pass
        except Exception as e:
            Console.warn(
            f"GMM clustering failed: {e}. Falling back to KMeans as last resort.",
            component="REGIME",
        )
    
    # ========== TRY KMEANS AS FINAL FALLBACK (v11.1.7) ==========
    # KMeans is fast, reliable, and always produces clusters
    if model is None:
        try:
            from sklearn.cluster import KMeans
            Console.info("Using KMeans clustering (final fallback)", component="REGIME")
            
            X_arr = train_basis.to_numpy(dtype=float, copy=False)
            X_arr = _finite_impute_inplace(X_arr)
            if not bool(basis_meta.get("basis_normalized", False)):
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X_arr)
            else:
                scaler = _IdentityScaler()
                X_scaled = scaler.transform(X_arr)
            
            # Auto-k selection using silhouette score
            kmeans_cfg = _cfg_get(cfg, "regimes.kmeans", {}) or {}
            k_min = int(kmeans_cfg.get("k_min", 2))
            k_max = int(kmeans_cfg.get("k_max", 6))
            
            best_kmeans = None
            best_k = 2
            best_score = -1.0
            quality_sweep = []
            
            for k in range(k_min, k_max + 1):
                try:
                    km = KMeans(n_clusters=k, n_init=10, max_iter=300, random_state=42)
                    labels = km.fit_predict(X_scaled)
                    if len(np.unique(labels)) >= 2:
                        sil = silhouette_score(X_scaled, labels)
                        quality_sweep.append((k, float(sil)))
                        if sil > best_score:
                            best_score = sil
                            best_k = k
                            best_kmeans = km
                except Exception:
                    continue
            
            if best_kmeans is not None:
                model = best_kmeans
                exemplars = best_kmeans.cluster_centers_
                best_metric = "silhouette"
                low_quality = best_score < 0.15
                basis_meta["clustering_method"] = "kmeans"
                Console.info(f"KMeans complete: k={best_k}, silhouette={best_score:.3f}", component="REGIME")
            else:
                raise RuntimeError("KMeans failed to produce valid clusters")
                
        except Exception as e:
            Console.error(f"All clustering methods failed: {e}", component="REGIME")
            raise RuntimeError(f"All clustering methods failed. Last error: {e}")

    # ========== Quality Assessment ==========
    quality_cfg = _cfg_get(cfg, "regimes.quality", {})
    quality_ok = True
    quality_notes: List[str] = []
    
    # Check quality based on metric type
    if best_metric in ("silhouette", "silhouette_non_noise"):
        sil_min = float(quality_cfg.get("silhouette_min", 0.15))
        quality_ok = best_score >= sil_min
    elif best_metric == "calinski_harabasz":
        calinski_min = float(quality_cfg.get("calinski_min", 50.0))
        quality_ok = best_score >= calinski_min
    elif best_metric in ("dbcv", "persistence"):
        # HDBSCAN metrics - lower thresholds are acceptable
        dbcv_min = float(quality_cfg.get("dbcv_min", 0.05))
        quality_ok = best_score >= dbcv_min
    elif best_metric == "bic":
        # For BIC (negated), higher is better - use different threshold logic
        quality_ok = not low_quality
        
    if low_quality or input_issues or config_issues:
        quality_ok = False
        
    if low_quality:
        quality_notes.append("clustering_quality_low")
    quality_notes.extend(input_issues)
    quality_notes.extend(config_issues)
    if np.isnan(best_score):
        quality_notes.append("auto_k_unscored")
    if not quality_ok and quality_notes:
        Console.warn(
            f"Regime quality failed: {', '.join(quality_notes)} "
            f"(metric={best_metric}, score={best_score:.3f})",
            component="REGIME",
            metric=best_metric,
            score=float(best_score) if np.isfinite(best_score) else None,
            quality_notes=quality_notes,
        )
    meta = {
        "best_k": int(best_k),
        "fit_score": float(best_score),
        "fit_metric": best_metric,
        "quality_ok": bool(quality_ok),
        "quality_notes": quality_notes,
        "quality_sweep": [(str(k), float(v)) for k, v in quality_sweep] if quality_sweep else [],
        "model_version": REGIME_MODEL_VERSION,
        "sklearn_version": sklearn.__version__,
    }
    # v11.1.0: K-Means removed - no longer tracking kmeans_inertia/kmeans_n_iter
    meta.update({k: v for k, v in basis_meta.items() if k not in meta})
    
    # Aggregate quality score (0-100) for observability
    quality_score_pct = 0.0
    if np.isfinite(best_score):
        if best_metric in ("silhouette", "silhouette_non_noise"):
            quality_score_pct = float(np.clip(best_score, 0.0, 1.0) * 100.0)
        elif best_metric == "calinski_harabasz":
            calinski_min = float(quality_cfg.get("calinski_min", 50.0))
            cal_ref = max(calinski_min, 1.0)
            quality_score_pct = float(np.clip(best_score / (2 * cal_ref), 0.0, 1.0) * 100.0)
        elif best_metric in ("dbcv", "persistence"):
            # HDBSCAN metrics are 0-1, scale to 0-100
            quality_score_pct = float(np.clip(best_score, 0.0, 1.0) * 100.0)
        elif best_metric == "bic":
            # BIC is harder to normalize - use quality_ok as proxy
            quality_score_pct = 75.0 if quality_ok else 25.0
    if not quality_ok:
        quality_score_pct = min(quality_score_pct, 50.0)
    meta["regime_quality_score"] = quality_score_pct
    
    if train_hash is None:
        try:
            meta_hash = _stable_int_hash(train_basis.to_numpy(dtype=float, copy=False))
            train_hash = meta_hash
        except Exception:
            pass
    
    # v11.1.0: Store clustering method and HDBSCAN-specific info in meta
    if "clustering_method" in basis_meta:
        meta["clustering_method"] = basis_meta["clustering_method"]
    if "gmm_converged" in basis_meta:
        meta["gmm_converged"] = basis_meta["gmm_converged"]
    if "gmm_n_iter" in basis_meta:
        meta["gmm_n_iter"] = basis_meta["gmm_n_iter"]
    if "gmm_bic" in basis_meta:
        meta["gmm_bic"] = basis_meta["gmm_bic"]
    if "hdbscan_n_clusters" in basis_meta:
        meta["hdbscan_n_clusters"] = basis_meta["hdbscan_n_clusters"]
    if "hdbscan_noise_count" in basis_meta:
        meta["hdbscan_noise_count"] = basis_meta["hdbscan_noise_count"]
    if "hdbscan_noise_ratio" in basis_meta:
        meta["hdbscan_noise_ratio"] = basis_meta["hdbscan_noise_ratio"]
    if "ensemble_fallback" in basis_meta:
        meta["ensemble_fallback"] = basis_meta["ensemble_fallback"]
    
    # Ensure scaler is not None before creating RegimeModel
    if scaler is None:
        raise RuntimeError("Scaler was not initialized - all clustering methods failed")
        
    regime_model = RegimeModel(
        scaler=scaler,
        clustering_model=model,  # v11.1.0: HDBSCAN or GMM
        feature_columns=list(train_basis.columns),
        raw_tags=basis_meta.get("raw_tags", []),
        n_pca_components=int(basis_meta.get("n_pca", 0)),
        train_hash=train_hash,
        meta=meta,
        exemplars_=exemplars,  # v11.1.0: Store centroids for HDBSCAN prediction
        fallback_model_=fallback_gmm,  # v11.1.8: Ensemble GMM fallback for noise points
    )
    
    # v11.1.6 FIX #3: Compute and store calibrated training distance threshold
    # This threshold is used for UNKNOWN detection in predict_regime_with_confidence
    unknown_cfg = _cfg_get(cfg, "regimes.unknown", {}) or {}
    distance_percentile = float(unknown_cfg.get("distance_percentile", 99.0))
    floor_ratio = float(unknown_cfg.get("distance_threshold_floor_ratio", 1.5))
    try:
        threshold, train_distances = _compute_training_distances(
            regime_model, train_basis, distance_percentile
        )
        # Apply a floor so the threshold is never tighter than floor_ratio × median
        # training distance. P99 on a short coldstart window can still be very tight
        # when training data doesn't cover the full operating envelope, causing 100%
        # of scoring points to be misclassified as novel.
        if len(train_distances) > 0 and floor_ratio > 0:
            median_dist = float(np.median(train_distances))
            floor = median_dist * floor_ratio
            if threshold < floor:
                Console.info(
                    f"Distance threshold P{distance_percentile:.0f}={threshold:.4f} "
                    f"below floor ({floor_ratio:.1f}× median={floor:.4f}); clamping up.",
                    component="REGIME",
                )
                threshold = floor
        regime_model.training_distance_threshold_ = threshold
        regime_model.training_distance_distribution_ = train_distances
        meta["training_distance_threshold"] = float(threshold)
        meta["training_distance_percentile"] = distance_percentile
    except Exception as e:
        Console.warn(
            f"Could not compute training distance threshold for novel point detection: {e}. "
            "All scoring points will be treated as known (no UNKNOWN regime assignments).",
            component="REGIME",
        )
        regime_model.training_distance_threshold_ = None
    
    return regime_model


def predict_regime(model: RegimeModel, basis_df: pd.DataFrame) -> np.ndarray:
    """
    Predict regime labels for new data using fitted model.
    
    FIX #6: Now validates feature dimensions and warns on mismatches
    instead of silently filling with zeros.
    """
    expected_cols = set(model.feature_columns)
    provided_cols = set(basis_df.columns)
    
    # FIX #6: Check for feature dimension mismatches
    missing_cols = expected_cols - provided_cols
    extra_cols = provided_cols - expected_cols
    
    if missing_cols:
        missing_pct = len(missing_cols) / len(expected_cols) * 100
        if missing_pct > 50:
            Console.warn(
                f"CRITICAL: {len(missing_cols)}/{len(expected_cols)} features missing ({missing_pct:.1f}%). "
                f"Missing: {list(missing_cols)[:5]}{'...' if len(missing_cols) > 5 else ''}. "
                f"Predictions may be unreliable - filling with 0.0",
                component="REGIME", missing_count=len(missing_cols), expected_count=len(expected_cols), missing_pct=missing_pct
            )
        elif missing_cols:
            Console.warn(
                f"{len(missing_cols)} features missing: {list(missing_cols)[:3]}{'...' if len(missing_cols) > 3 else ''}. "
                f"Filling with 0.0",
                component="REGIME", missing_count=len(missing_cols), expected_count=len(expected_cols)
            )
    
    if extra_cols:
        Console.info(
            f"{len(extra_cols)} extra features ignored: {list(extra_cols)[:3]}{'...' if len(extra_cols) > 3 else ''}",
            component="REGIME"
        )
    
    aligned = basis_df.reindex(columns=model.feature_columns, fill_value=0.0)
    aligned_arr = aligned.to_numpy(dtype=np.float64, copy=False, na_value=0.0)
    
    # v11.6.0 FIX #1: None-guard for scaler.transform()
    # Models loaded from corrupted SQL ModelRegistry may have None scaler
    if model.scaler is None:
        raise ValueError(
            f"[REGIME] Cannot predict: model.scaler is None. "
            f"Model may be corrupted - delete and retrain. "
            f"Features: {model.feature_columns[:3]}..."
        )
    
    X_scaled = model.scaler.transform(aligned_arr)
    X_scaled = np.asarray(X_scaled, dtype=np.float64, order="C")
    
    # v11.1.0: Support HDBSCAN and GMM only
    # v11.3.1: Always assign to a cluster - never return UNKNOWN (-1)
    # Equipment is always in SOME operating state
    if model.is_hdbscan:
        # HDBSCAN: Use approximate_predict for new points
        try:
            predict_result = hdbscan.approximate_predict(model.clustering_model, X_scaled)  # type: ignore[union-attr]
            labels = np.asarray(predict_result[0], dtype=int, copy=True)  # Make mutable copy
            strengths = np.asarray(predict_result[1], dtype=float)
            
            # v11.3.1: Always assign low-strength points to nearest centroid
            # They ARE in some operating state, we just have lower confidence
            low_strength_mask = strengths < 0.1
            if np.any(low_strength_mask):
                if model.fallback_model_ is not None:
                    # Use GMM for better assignment
                    gmm_labels = model.fallback_model_.predict(X_scaled[low_strength_mask])
                    labels[low_strength_mask] = gmm_labels
                elif model.exemplars_ is not None and len(model.exemplars_) > 0:
                    # Assign to nearest centroid
                    centroid_labels = pairwise_distances_argmin(
                        X_scaled[low_strength_mask], model.exemplars_, axis=1
                    )
                    labels[low_strength_mask] = centroid_labels
                n_novel = int(np.sum(low_strength_mask))
                if n_novel > 0:
                    Console.info(
                        f"Assigned {n_novel}/{len(labels)} low-strength points to nearest cluster",
                        component="REGIME"
                    )
                
            return labels.astype(int, copy=False)
        except Exception as e:
            # Fallback: assign to nearest centroid
            Console.warn(f"HDBSCAN approximate_predict failed: {e}, using centroid fallback", component="REGIME")
            if model.exemplars_ is not None and len(model.exemplars_) > 0:
                labels = pairwise_distances_argmin(X_scaled, model.exemplars_, axis=1)
                return labels.astype(int, copy=False)
            elif model.fallback_model_ is not None:
                # Use GMM fallback if available
                labels = model.fallback_model_.predict(X_scaled)
                return labels.astype(int, copy=False)
            else:
                # v11.3.1: Last resort - assign all to cluster 0 with warning
                Console.warn("No clustering method available, assigning all to regime 0", component="REGIME")
                return np.zeros(len(X_scaled), dtype=int)
    else:
        # GaussianMixture uses predict() directly
        labels = model.clustering_model.predict(X_scaled)
    return labels.astype(int, copy=False)


def predict_regime_with_confidence(
    model: RegimeModel,
    basis_df: pd.DataFrame,
    cfg: Dict[str, Any],
    training_distances: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compatibility wrapper; context semantics now live in core.context_engine."""
    return _context_predict_regime_with_confidence(
        model,
        basis_df,
        cfg,
        training_distances=training_distances,
    )


def update_health_labels(
    model: RegimeModel,
    labels: np.ndarray,
    fused_series: pd.Series | np.ndarray,
    cfg: Dict[str, Any],
) -> Dict[int, Dict[str, Any]]:
    def _parse_per_regime_thresholds(
        raw_overrides: Any,
        default_warn: float,
        default_alert: float,
    ) -> Dict[int, Tuple[float, float]]:
        overrides: Dict[int, Tuple[float, float]] = {}
        if raw_overrides is None:
            return overrides
        if not isinstance(raw_overrides, dict):
            Console.warn(
                "regimes.health.per_regime_thresholds must be a dict; ignoring overrides",
                component="REGIME",
            )
            return overrides

        for raw_label, raw_thresholds in raw_overrides.items():
            try:
                label = int(raw_label)
            except Exception:
                Console.warn(
                    f"Skipping invalid per-regime threshold label: {raw_label}",
                    component="REGIME",
                )
                continue
            if not isinstance(raw_thresholds, dict):
                Console.warn(
                    f"Skipping per-regime threshold for label {label}: expected dict, got {type(raw_thresholds).__name__}",
                    component="REGIME",
                )
                continue
            warn_raw = raw_thresholds.get("warn", raw_thresholds.get("fused_warn_z", default_warn))
            alert_raw = raw_thresholds.get("alert", raw_thresholds.get("fused_alert_z", default_alert))
            try:
                warn_value = float(warn_raw)
                alert_value = float(alert_raw)
            except Exception:
                Console.warn(
                    f"Skipping per-regime threshold for label {label}: warn/alert must be numeric",
                    component="REGIME",
                )
                continue
            if not np.isfinite(warn_value) or not np.isfinite(alert_value):
                Console.warn(
                    f"Skipping per-regime threshold for label {label}: warn/alert must be finite",
                    component="REGIME",
                )
                continue
            if warn_value > alert_value:
                Console.warn(
                    f"Skipping per-regime threshold for label {label}: warn ({warn_value}) exceeds alert ({alert_value})",
                    component="REGIME",
                )
                continue
            overrides[label] = (warn_value, alert_value)
        return overrides

    health_cfg = _cfg_get(cfg, "regimes.health", {})
    warn = float(health_cfg.get("fused_warn_z", 1.5))
    alert = float(health_cfg.get("fused_alert_z", 3.0))
    per_regime_thresholds = _parse_per_regime_thresholds(
        health_cfg.get("per_regime_thresholds"),
        warn,
        alert,
    )

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
    transition_keys: List[str] = []
    for seg_idx, (label_value, start_idx, end_idx) in enumerate(segments):
        info = per_label_segments.setdefault(
            int(label_value),
            {"segment_count": 0, "dwell_seconds": 0.0, "dwell_samples": 0, "transitions_in": 0, "transitions_out": 0},
        )
        info["segment_count"] += 1
        span = max(end_idx - start_idx, 0)
        info["dwell_samples"] += span
        # V11 FIX: Bounds check to prevent IndexError if durations array is shorter
        if durations.size:
            end_safe = min(end_idx, durations.size)
            if start_idx < end_safe:
                info["dwell_seconds"] += float(np.sum(durations[start_idx:end_safe]))

        if seg_idx > 0:
            prev_label, _, _ = segments[seg_idx - 1]
            key = f"{int(prev_label)}->{int(label_value)}"
            transition_keys.append(key)
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
        warn_threshold, alert_threshold = per_regime_thresholds.get(int(label), (warn, alert))
        if med >= alert_threshold:
            state = "critical"
        elif med >= warn_threshold:
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
            "warn_threshold": float(warn_threshold),
            "alert_threshold": float(alert_threshold),
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
    if transition_keys:
        counts = Counter(transition_keys)
        model.meta["transition_counts"] = {k: int(v) for k, v in counts.items()}
    if np.isfinite(total_duration_sec):
        model.meta["total_duration_seconds"] = float(total_duration_sec)
    model.meta["total_samples"] = int(len(labels_arr))
    model.meta["health_threshold_mode"] = "per_regime_overrides" if per_regime_thresholds else "global"
    if per_regime_thresholds:
        model.meta["health_threshold_overrides"] = {
            str(label): {"warn": float(thr[0]), "alert": float(thr[1])}
            for label, thr in per_regime_thresholds.items()
        }
    
    # v11.4.0: Identify the "Normal" operating regime using config parameters
    normal_cfg = _cfg_get(cfg, "regimes.normal_identification", {})
    min_dwell = float(normal_cfg.get("min_dwell_fraction", 0.15))
    max_fused = float(normal_cfg.get("max_median_fused", 2.0))
    normal_label = identify_normal_regime(stats, min_dwell_fraction=min_dwell, max_median_fused=max_fused)
    model.normal_regime_label_ = normal_label
    
    # v11.4.0: Generate semantic labels for all regimes
    model.regime_semantic_labels_ = _generate_regime_semantic_labels(stats, normal_label)
    model.meta["normal_regime_label"] = normal_label
    model.meta["regime_semantic_labels"] = dict(model.regime_semantic_labels_)
    
    if normal_label is not None:
        Console.info(
            f"Identified Normal regime: {normal_label} "
            f"(dwell={stats[normal_label].get('dwell_fraction', 0):.1%}, "
            f"median_fused={stats[normal_label].get('median_fused', 0):.2f})",
            component="REGIME"
        )
    
    return stats


def identify_normal_regime(
    regime_stats: Dict[int, Dict[str, Any]],
    min_dwell_fraction: float = 0.15,
    max_median_fused: float = 2.0,
) -> Optional[int]:
    """
    Identify the "Normal" operating regime using dwell time and anomaly score.
    
    v11.4.0: Research-backed Normal regime identification.
    
    The Normal regime is the operating state where:
    1. Equipment spends the MOST time (highest dwell_fraction)
    2. Equipment shows the HEALTHIEST behavior (lowest median_fused)
    
    Combined score: dwell_fraction * (1 / (1 + median_fused))
    
    This approach is consistent with semi-Markov reliability modeling where
    the baseline/steady-state has maximum stationary probability and minimum
    hazard rate (Limnios & Oprisan, 2001).
    
    Args:
        regime_stats: Dict from update_health_labels() with regime statistics
        min_dwell_fraction: Minimum dwell fraction to consider (default: 0.15)
        max_median_fused: Maximum median_fused to consider as potentially normal (default: 2.0)
        
    Returns:
        Integer label of the Normal regime, or None if no suitable regime found
    """
    if not regime_stats:
        return None
    
    best_regime: Optional[int] = None
    best_score: float = -1.0
    
    for label, stats in regime_stats.items():
        # Skip UNKNOWN regime (deprecated but may exist in legacy data)
        if label == UNKNOWN_REGIME_LABEL:
            continue
        
        dwell_fraction = stats.get("dwell_fraction", 0.0)
        median_fused = stats.get("median_fused", float("inf"))
        
        # Validate values
        if not np.isfinite(dwell_fraction) or not np.isfinite(median_fused):
            continue
        
        # Filter out rare regimes and high-anomaly regimes
        if dwell_fraction < min_dwell_fraction:
            continue
        if median_fused > max_median_fused:
            continue
        
        # Combined score: higher dwell + lower anomaly = more "normal"
        # The inverse transform 1/(1+z) maps [0, inf) -> (0, 1]
        # This gives highest weight to regimes with median_fused near 0
        health_factor = 1.0 / (1.0 + max(0.0, median_fused))
        combined_score = dwell_fraction * health_factor
        
        if combined_score > best_score:
            best_score = combined_score
            best_regime = int(label)
    
    return best_regime


def _generate_regime_semantic_labels(
    regime_stats: Dict[int, Dict[str, Any]],
    normal_regime_label: Optional[int],
) -> Dict[int, str]:
    """
    Generate human-readable semantic labels for regimes.
    
    v11.4.0: Provides meaningful names based on regime characteristics.
    
    Naming conventions:
    - Normal: The identified normal operating regime
    - High Load / Low Load: Based on relative dwell patterns
    - Transient: Low dwell fraction, high transition count
    - Stressed: High median_fused (anomaly score)
    
    Args:
        regime_stats: Regime statistics from update_health_labels()
        normal_regime_label: The identified normal regime
        
    Returns:
        Dict mapping regime label (int) to semantic name (str)
    """
    labels: Dict[int, str] = {}
    
    if not regime_stats:
        return labels
    
    # Compute reference values for relative naming
    all_dwell = [s.get("dwell_fraction", 0) for s in regime_stats.values() if np.isfinite(s.get("dwell_fraction", 0))]
    all_fused = [s.get("median_fused", 0) for s in regime_stats.values() if np.isfinite(s.get("median_fused", 0))]
    
    median_dwell = float(np.median(all_dwell)) if all_dwell else 0.0
    median_fused = float(np.median(all_fused)) if all_fused else 0.0
    
    for label, stats in regime_stats.items():
        if label == UNKNOWN_REGIME_LABEL:
            labels[label] = "Unknown"
            continue
        
        dwell_frac = stats.get("dwell_fraction", 0.0)
        fused = stats.get("median_fused", 0.0)
        transition_count = stats.get("transition_count", 0)
        segment_count = stats.get("segment_count", 0)
        state = stats.get("state", "unknown")
        
        # Primary classification
        if label == normal_regime_label:
            labels[label] = "Normal"
        elif state == "critical":
            labels[label] = "Stressed"
        elif state == "suspect":
            # Check if transient (high transitions, low dwell)
            if segment_count > 0 and transition_count / max(segment_count, 1) > 0.5:
                labels[label] = "Transient"
            else:
                labels[label] = "Elevated"
        elif np.isfinite(dwell_frac) and dwell_frac < median_dwell * 0.3:
            # Low dwell = startup/shutdown type regime
            labels[label] = "Transient"
        elif np.isfinite(fused) and fused > median_fused * 1.5:
            labels[label] = "Elevated"
        else:
            # Generic operating regime
            labels[label] = f"Regime_{label}"
    
    return labels


def build_summary_dataframe(model: RegimeModel) -> pd.DataFrame:
    """
    Build summary DataFrame from RegimeModel stats.
    
    FIX #2: Uses pre-computed values from update_health_labels() which uses
    _compute_sample_durations() as the single source of truth. Fallback logic
    only applies when stats are from legacy models without duration data.
    """
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

    # FIX #2: Use authoritative total_duration_seconds from model meta
    # Only fall back to sum(dwell_seconds) or sum(count) for legacy models
    total_duration = float(model.meta.get("total_duration_seconds", 0.0) or 0.0)
    if not np.isfinite(total_duration) or total_duration <= 0:
        # Legacy fallback: sum individual dwell times
        total_duration = float(sum(stat.get("dwell_seconds", 0.0) for stat in stats.values()))
        if not np.isfinite(total_duration) or total_duration <= 0:
            # Ultimate fallback: sample counts
            total_duration = float(sum(stat.get("count", 0) for stat in stats.values()))
            Console.warn("build_summary_dataframe: using sample counts as duration proxy (legacy model)", component="REGIME", total_samples=int(total_duration), model_version=model.meta.get("model_version", "unknown"))

    rows: List[Dict[str, Any]] = []
    for label, stat in stats.items():
        # FIX #2: Trust pre-computed dwell_seconds from update_health_labels
        dwell_seconds = float(stat.get("dwell_seconds", float("nan")))
        
        # Only use count fallback for legacy stats without duration data
        if not np.isfinite(dwell_seconds) or dwell_seconds <= 0:
            # Check if this is legacy data (no valid duration computed)
            if stat.get("count", 0) > 0:
                dwell_seconds = float(stat.get("count", 0))
        
        # Use pre-computed dwell_fraction, recompute only if missing
        dwell_fraction = float(stat.get("dwell_fraction", float("nan")))
        if not np.isfinite(dwell_fraction) and total_duration > 0 and np.isfinite(dwell_seconds):
            dwell_fraction = dwell_seconds / total_duration
        
        # Use pre-computed avg_dwell_seconds, recompute only if missing  
        avg_dwell = float(stat.get("avg_dwell_seconds", float("nan")))
        if not np.isfinite(avg_dwell):
            segment_count = int(stat.get("segment_count", 0))
            if segment_count > 0 and np.isfinite(dwell_seconds):
                avg_dwell = dwell_seconds / segment_count
                
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

    # V11 FIX: Add UNKNOWN regime to summary if present in model stats
    # This ensures users see how many samples were unassigned due to low confidence
    if UNKNOWN_REGIME_LABEL in stats:
        unknown_stat = stats[UNKNOWN_REGIME_LABEL]
        unknown_row = {
            "regime": UNKNOWN_REGIME_LABEL,
            "state": "unknown",  # UNKNOWN is always marked as unknown state
            "dwell_seconds": float(unknown_stat.get("dwell_seconds", float("nan"))),
            "dwell_fraction": float(unknown_stat.get("dwell_fraction", float("nan"))),
            "avg_dwell_seconds": float(unknown_stat.get("avg_dwell_seconds", float("nan"))),
            "transition_count": int(unknown_stat.get("transition_count", 0)),
            "stability_score": float(unknown_stat.get("stability_score", float("nan"))),
            "median_fused": float(unknown_stat.get("median_fused", float("nan"))),
            "p95_abs_fused": float(unknown_stat.get("p95_abs_fused", float("nan"))),
            "count": int(unknown_stat.get("count", 0)),
        }
        # Check if UNKNOWN already in rows (from main loop)
        unknown_exists = any(r.get("regime") == UNKNOWN_REGIME_LABEL for r in rows)
        if not unknown_exists:
            rows.append(unknown_row)
    
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

# TO-DO Remove this.
def smooth_labels(
    labels: np.ndarray,
    passes: int = 1,
    window: Optional[int] = None,
    health_map: Optional[Dict[int, str]] = None,
    preserve_unknown: bool = True,
    timestamps: Optional[pd.Index] = None,
    window_seconds: Optional[float] = None,
) -> np.ndarray:
    """
    Apply mode-based smoothing to integer labels (VECTORIZED for performance).
    
    FIX #3: Replaced median_filter which can introduce non-existent labels
    and create physically impossible state transitions. Now uses mode-based
    smoothing with health-aware tie-breaking.
    
    FIX #6 (v11.1.6): Added time-based window sizing. When timestamps and
    window_seconds are provided, the window size is derived from the median
    sampling interval to represent a consistent time span regardless of
    irregular sampling rates.
    
    V11 FIX: Added preserve_unknown parameter to prevent UNKNOWN_REGIME_LABEL (-1)
    from being overwritten by smoothing. UNKNOWN represents low-confidence
    assignments and should survive smoothing.
    
    V11 PERF: Vectorized implementation using scipy.stats.mode for 100x+ speedup
    on large datasets.
    
    Args:
        labels: Integer regime labels
        passes: Number of smoothing iterations
        window: Smoothing window size in samples (odd number preferred)
        health_map: Optional map of label -> health state for tie-breaking
        preserve_unknown: If True, UNKNOWN labels are never overwritten (V11)
        timestamps: Optional datetime index for time-based window sizing (FIX #6)
        window_seconds: Smoothing window size in seconds (overrides window if timestamps provided)
        
    Returns:
        Smoothed labels that only contain values from the original sequence
    """
    if labels.size == 0:
        return labels

    smoothed = labels.astype(int, copy=True)
    if passes <= 0 and window is None and window_seconds is None:
        return smoothed
    
    # V11 FIX: Remember which positions are UNKNOWN before smoothing
    unknown_mask = None
    if preserve_unknown:
        unknown_mask = (labels == UNKNOWN_REGIME_LABEL)
    
    # Get valid labels from original sequence (FIX #3: prevent introducing new labels)
    # V11: Exclude UNKNOWN from valid_labels so smoothing prefers known regimes
    valid_labels_set = set(np.unique(labels)) - {UNKNOWN_REGIME_LABEL}
    valid_labels_arr = np.array(sorted(valid_labels_set), dtype=int)

    # FIX #6 (v11.1.6): Time-based window sizing
    # If timestamps and window_seconds are provided, derive window size from
    # median sampling interval to ensure consistent time spans regardless of
    # irregular sampling rates.
    if window_seconds is not None and timestamps is not None and len(timestamps) == len(labels):
        try:
            ts = pd.to_datetime(timestamps)
            # Compute median sampling interval
            diffs = np.diff(ts.view('int64'))  # nanoseconds
            if len(diffs) > 0:
                median_interval_ns = float(np.nanmedian(diffs))
                median_interval_sec = median_interval_ns / 1e9
                if median_interval_sec > 0:
                    # Derive window size from time
                    derived_window = int(np.ceil(window_seconds / median_interval_sec))
                    derived_window = max(3, derived_window)  # Minimum 3 samples
                    if derived_window % 2 == 0:
                        derived_window += 1  # Ensure odd for centering
                    
                    Console.info(
                        f"Time-based smoothing: {window_seconds}s -> {derived_window} samples "
                        f"(median interval: {median_interval_sec:.1f}s)",
                        component="REGIME"
                    )
                    window = derived_window
        except Exception as e:
            Console.warn(
                f"Failed to derive time-based window; using sample-based: {e}",
                component="REGIME"
            )

    win = window if window is not None else max(1, 2 * passes + 1)
    if win % 2 == 0:
        win += 1
    
    half = max(1, win // 2)
    iterations = max(1, passes)
    
    # Try to use scipy.stats.mode for vectorized mode computation
    try:
        from scipy.stats import mode as scipy_mode
        use_scipy = True
    except ImportError:
        use_scipy = False
    
    for _ in range(iterations):
        padded = np.pad(smoothed, pad_width=half, mode="edge")
        shape = (smoothed.size, win)
        strides = (padded.strides[0], padded.strides[0])
        windows = np.lib.stride_tricks.as_strided(padded, shape=shape, strides=strides)
        
        if use_scipy and health_map is None:
            # VECTORIZED path: Use scipy.stats.mode for massive speedup
            # This works when we don't need health-aware tie-breaking
            mode_result = scipy_mode(windows, axis=1, keepdims=False)
            modes = mode_result.mode.astype(int)
            
            # FIX #3: Ensure modes only contain valid labels
            invalid_mask = ~np.isin(modes, valid_labels_arr)
            if invalid_mask.any():
                # For invalid modes, fall back to original value
                modes[invalid_mask] = smoothed[invalid_mask]
        else:
            # SCALAR path: Use per-row loop (slower but supports health_map)
            modes = np.empty(smoothed.size, dtype=int)
            
            for idx, row in enumerate(windows):
                vals, counts = np.unique(row, return_counts=True)
                
                # FIX #3: Only consider labels that existed in original sequence
                valid_mask = np.isin(vals, valid_labels_arr)
                if not valid_mask.any():
                    modes[idx] = smoothed[idx]  # Keep current if no valid labels
                    continue
                    
                vals = vals[valid_mask]
                counts = counts[valid_mask]
                
                max_count = counts.max()
                max_mask = counts == max_count
                
                if max_mask.sum() == 1:
                    # Single winner
                    modes[idx] = vals[np.argmax(counts)]
                else:
                    # Tie-breaking: prefer higher health severity if health_map provided
                    candidates = vals[max_mask]
                    if health_map is not None:
                        # FIX #4 integrated: prioritize by health severity (critical > suspect > healthy)
                        best_label = candidates[0]
                        best_priority = _HEALTH_PRIORITY.get(health_map.get(int(best_label)), 3)
                        for lbl in candidates[1:]:
                            priority = _HEALTH_PRIORITY.get(health_map.get(int(lbl)), 3)
                            if priority < best_priority:  # Lower = higher severity
                                best_priority = priority
                                best_label = lbl
                        modes[idx] = best_label
                    else:
                        # No health map: prefer label closest to center sample
                        center_val = row[half]
                        if center_val in candidates:
                            modes[idx] = center_val
                        else:
                            modes[idx] = candidates[0]
                        
        smoothed = modes
    
    # V11 FIX: Restore UNKNOWN labels after smoothing
    # UNKNOWN represents low-confidence assignments and must survive smoothing
    if preserve_unknown and unknown_mask is not None and unknown_mask.any():
        smoothed[unknown_mask] = UNKNOWN_REGIME_LABEL
        
    return smoothed
# TO-DO Remove health priority usage from here
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
        """
        Score a candidate replacement label. Lower score = better candidate.
        
        FIX #4: Prioritize health severity FIRST, then run length.
        This ensures critical/suspect states are preserved even if they have
        shorter runs than adjacent healthy segments.
        
        Returns:
            (health_rank, -run_length) tuple for min() comparison
            health_rank: 0=healthy, 1=suspect, 2=critical, 3=unknown
            Lower health_rank = healthier state (we prefer replacing short
            segments with HEALTHIER adjacent states, not critical ones)
        """
        health = None
        if health_map is not None:
            health = health_map.get(int(label))
        health_rank = _HEALTH_PRIORITY.get(health, _HEALTH_PRIORITY["unknown"])
        
        # Count adjacent run of same label
        run = 0
        idx = segment_start - 1
        while idx >= 0 and result[idx] == label:
            run += 1
            idx -= 1
        idx = segment_end
        while idx < n and result[idx] == label:
            run += 1
            idx += 1
        
        # FIX #4: Health priority comes FIRST
        # Prefer healthier states (lower rank), then longer runs
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
            # V11 FIX: Never replace UNKNOWN labels - they represent low confidence
            current_label = int(arr[start])
            if current_label == UNKNOWN_REGIME_LABEL:
                start = end
                continue
                
            candidates: List[int] = []
            if start > 0:
                prev_label = int(result[start - 1])
                # V11: Don't use UNKNOWN as replacement candidate
                if prev_label != UNKNOWN_REGIME_LABEL:
                    candidates.append(prev_label)
            if end < n:
                next_label = int(result[end])
                # V11: Don't use UNKNOWN as replacement candidate
                if next_label != UNKNOWN_REGIME_LABEL:
                    candidates.append(next_label)
            if candidates:
                replacement = min(candidates, key=lambda lbl: _candidate_score(lbl, start, end))
                result[start:end] = replacement
        start = end

    return result

# -----------------------------------
# Core: fit auto-k with safe heuristics (v11.1.0: Uses GMM, not K-Means)
# DEPRECATED: Legacy path - use fit_regime_model() instead
# TO-DO Remove this deprecated function from code altogether.
# -----------------------------------
def _fit_auto_k(
    X: np.ndarray,
    *,
    k_min: int = 2,
    k_max: int = 6,
    pca_dim: int = 20,
    sil_sample: int = 4000,
    random_state: int = 17,
) -> Tuple[GaussianMixture, Optional[PCA], int, float, str]:
    """Legacy auto-k fitting using GMM (v11.1.0: K-Means removed)."""
    Console.warn("Using deprecated _fit_auto_k - migrate to fit_regime_model()", component="REGIME")
    X = _finite_impute_inplace(X)
    n, d = X.shape

    if n < 4:
        # Degenerate case: single cluster
        gmm = GaussianMixture(n_components=1, random_state=random_state)
        gmm.fit(X)
        return gmm, None, 1, 0.0, "degenerate"

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

    best_model: Optional[GaussianMixture] = None
    best_k = k_min
    best_score = -1.0
    best_metric = "silhouette"

    for k in range(k_min, k_max + 1):
        try:
            gmm = GaussianMixture(
                n_components=k,
                covariance_type="full",
                n_init=3,
                random_state=random_state,
            )
            labels = gmm.fit_predict(Xp_f64)

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
                best_model = gmm
                best_k = int(k)
                best_metric = metric
        except Exception:
            continue

    if best_model is None:
        # Fallback: single component GMM
        best_model = GaussianMixture(n_components=1, random_state=random_state)
        best_model.fit(Xp_f64)
        best_k = 1
        best_score = 0.0
        best_metric = "fallback"
    
    return best_model, pca_obj, best_k, best_score, best_metric

# ------------------------------------------------
# State Persistence Helpers
# ------------------------------------------------
def regime_model_to_state(
    model: RegimeModel,
    equip_id: int,
    state_version: int,
    config_hash: str,
    regime_basis_hash: str
):
    """
    Convert RegimeModel to RegimeState for persistence.
    
    Args:
        model: Fitted RegimeModel object
        equip_id: Equipment ID
        state_version: Version number for this state
        config_hash: Hash of regime configuration
        regime_basis_hash: Hash of regime basis features
    
    Returns:
        RegimeState object for persistence
    """
    from core.model_persistence import RegimeState
    import json
    from datetime import datetime, timezone

    # Extract cluster centers (v11.1.0: Property works for HDBSCAN and GMM)
    cluster_centers = model.cluster_centers_
    cluster_centers_json = json.dumps(cluster_centers.tolist())
    
    # Extract scaler parameters
    scaler_mean = np.asarray(model.scaler.mean_, dtype=float)
    scaler_scale = np.asarray(model.scaler.scale_, dtype=float)
    scaler_mean_json = json.dumps(scaler_mean.tolist())
    scaler_scale_json = json.dumps(scaler_scale.tolist())
    
    # PCA parameters (if any)
    n_pca = model.n_pca_components
    if n_pca > 0 and hasattr(model, 'pca') and model.pca is not None:
        pca_components = np.asarray(model.pca.components_, dtype=float)
        pca_variance = np.asarray(model.pca.explained_variance_ratio_, dtype=float)
        pca_components_json = json.dumps(pca_components.tolist())
        pca_variance_json = json.dumps(pca_variance.tolist())
    else:
        pca_components_json = "[]"
        pca_variance_json = "[]"
    
    # Quality metrics
    silhouette = float(model.meta.get("fit_score", 0.0))
    quality_ok = bool(model.meta.get("quality_ok", False))
    
    meta_payload = _regime_metadata_dict(model)
    try:
        meta_json = orjson.dumps(meta_payload) if orjson else json.dumps(meta_payload)
    except Exception:
        meta_json = json.dumps(meta_payload)

    state = RegimeState(
        equip_id=equip_id,
        state_version=state_version,
        n_clusters=int(model.n_clusters),  # Property supports HDBSCAN and GMM
        cluster_centers_json=cluster_centers_json,
        scaler_mean_json=scaler_mean_json,
        scaler_scale_json=scaler_scale_json,
        pca_components_json=pca_components_json,
        pca_explained_variance_json=pca_variance_json,
        n_pca_components=n_pca,
        silhouette_score=silhouette,
        quality_ok=quality_ok,
        last_trained_time=datetime.now(timezone.utc).isoformat(),
        config_hash=config_hash,
        regime_basis_hash=regime_basis_hash,
        training_distance_threshold=model.training_distance_threshold_,
    )
    
    return state


def regime_state_to_model(
    state,
    feature_columns: List[str],
    raw_tags: List[str],
    train_hash: Optional[int] = None
) -> RegimeModel:
    """
    Reconstruct RegimeModel from RegimeState.
    
    Args:
        state: RegimeState object loaded from persistence
        feature_columns: List of feature column names
        raw_tags: List of raw sensor tag names
        train_hash: Optional hash of training data
    
    Returns:
        Reconstructed RegimeModel object
    """
    from sklearn.preprocessing import StandardScaler

    # Reconstruct scaler
    # If mean/scale are empty arrays the original scaler was _IdentityScaler (pre_scaled=True).
    # Reconstructing a StandardScaler with n_features_in_=0 causes
    # "X has N features, but StandardScaler is expecting 0" on the next batch.
    # Use _IdentityScaler (no-op) whenever the stored params are empty.
    _mean, _scale = state.get_scaler_params()
    if len(_mean) == 0 or len(_scale) == 0:
        scaler: Union[StandardScaler, "_IdentityScaler"] = _IdentityScaler()
    else:
        scaler = StandardScaler()
        scaler.mean_ = _mean
        scaler.scale_ = _scale
        scaler.n_features_in_ = len(_mean)
        scaler.n_samples_seen_ = 1  # Required by sklearn but not critical here
    
    # v11.1.0: Reconstruct GMM instead of KMeans
    cluster_centers = state.get_cluster_centers()
    n_clusters = state.n_clusters
    n_features = cluster_centers.shape[1] if cluster_centers.size else 0
    
    gmm = GaussianMixture(n_components=n_clusters, random_state=17)
    # Set the fitted parameters manually
    gmm.means_ = cluster_centers
    gmm.n_features_in_ = n_features
    # Initialize covariances as identity (approximation for reconstruction)
    gmm.covariances_ = np.array([np.eye(n_features) for _ in range(n_clusters)])
    gmm.precisions_cholesky_ = np.array([np.eye(n_features) for _ in range(n_clusters)])
    gmm.weights_ = np.ones(n_clusters) / n_clusters
    gmm.converged_ = True
    gmm.n_iter_ = 0
    
    # Reconstruct PCA if used
    pca_obj = None
    if state.n_pca_components > 0:
        from sklearn.decomposition import PCA
        pca_components, pca_variance = state.get_pca_params()
        if pca_components is not None:
            pca_obj = PCA(n_components=state.n_pca_components)
            pca_obj.components_ = pca_components
            pca_obj.explained_variance_ratio_ = pca_variance
            pca_obj.n_features_in_ = pca_components.shape[1]
    
    # Build RegimeModel
    model = RegimeModel(
        scaler=scaler,
        clustering_model=gmm,
        feature_columns=feature_columns,
        raw_tags=raw_tags,
        n_pca_components=state.n_pca_components,
        train_hash=train_hash,
        health_labels={},  # Will be recomputed if needed
        stats={},
        meta={
            "fit_score": state.silhouette_score,
            "fit_metric": "silhouette",
            "quality_ok": state.quality_ok,
            "best_k": state.n_clusters,
            "loaded_from_state": True,
            "state_version": state.state_version
        }
    )
    
    if pca_obj is not None:
        model.pca = pca_obj

    model.training_distance_threshold_ = state.training_distance_threshold

    return model

# TO-DO See if this is still needed like this
# ------------------------------------------------
# Public API: label(score_df, ctx, score_out, cfg)
# ------------------------------------------------
def label(score_df, ctx: Dict[str, Any], score_out: Dict[str, Any], cfg: Dict[str, Any]):
    basis_train: Optional[pd.DataFrame] = ctx.get("regime_basis_train")
    basis_score: Optional[pd.DataFrame] = ctx.get("regime_basis_score")
    basis_meta: Dict[str, Any] = ctx.get("basis_meta") or {}
    regime_model: Optional[RegimeModel] = ctx.get("regime_model")
    basis_hash: Optional[int] = ctx.get("regime_basis_hash")  # v11.1.1: Now SCHEMA hash, not data hash
    
    # v11.8.0: Discovery controlled by MaturityState only
    # - COLDSTART/LEARNING: discovery allowed (model is still learning)
    # - CONVERGED: discovery NOT allowed (use existing model)
    model_maturity: Optional[str] = ctx.get("model_maturity")
    discovery_allowed = model_maturity in ("COLDSTART", "LEARNING", None)
    if not discovery_allowed:
        Console.info(
            f"Model maturity is {model_maturity} - regime discovery disabled (using existing model)",
            component="REGIME"
        )

    out = dict(score_out or {})
    frame = out.get("frame")

    if basis_train is not None and basis_score is not None:
        # v11.1.1 FIX: Only check feature column match for regime model validity
        # Previously checked train_hash which changed every batch causing constant refits!
        # Regimes should be STATIC once discovered - same equipment = same regimes
        needs_fit = (
            regime_model is None
            or regime_model.feature_columns != list(basis_train.columns)
        )
        
        # v11.4.0: Fail fast if model missing and discovery not allowed by maturity
        if needs_fit and not discovery_allowed:
            raise RuntimeError(
                f"[CONVERGED MODEL] Regime model not found or feature mismatch. "
                f"Model maturity={model_maturity or 'unknown'} does not allow rediscovery. "
                f"Either provide a valid cached model or reset to LEARNING state."
            )
        
        if needs_fit:
            regime_model = fit_regime_model(basis_train, basis_meta, cfg, basis_hash)
        
        # Type assertion: regime_model is guaranteed non-None at this point
        # Either it was loaded from cache, or fit_regime_model was called (which never returns None)
        assert regime_model is not None, "regime_model should be set by now"
        
        if regime_model.train_hash is None and basis_hash is not None:
            regime_model.train_hash = basis_hash

        # V11: Use confidence-aware prediction for score data
        # Training data uses standard prediction (no novel detection during training)
        train_labels = predict_regime(regime_model, basis_train)
        
        # Compute training distances for establishing threshold
        aligned_train = basis_train.reindex(columns=regime_model.feature_columns, fill_value=0.0)
        train_arr = aligned_train.to_numpy(dtype=np.float64, copy=False, na_value=0.0)
        
        # v11.6.0 FIX #1: Validate scaler before transform
        if regime_model.scaler is None:
            raise ValueError(
                f"[REGIME] Cannot compute distances: regime_model.scaler is None. "
                f"Cached model may be corrupted - delete from ModelRegistry and retrain."
            )
        
        train_scaled = regime_model.scaler.transform(train_arr)
        centers = regime_model.cluster_centers_  # v11.1.0: Property works for HDBSCAN/GMM
        # V11 FIX: Vectorized distance computation (50-100x faster than list comprehension)
        train_distances = np.linalg.norm(
            train_scaled - centers[train_labels], axis=1
        )
        
        # v11.3.1: Score data gets confidence + novelty detection
        # Returns 3-tuple: (labels, confidence, is_novel)
        score_labels, score_confidence, score_is_novel = predict_regime_with_confidence(
            regime_model, basis_score, cfg, training_distances=train_distances
        )
        
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
            health_map=None,  # compute health after smoothing to avoid stale map
        )
        score_labels = smooth_transitions(
            score_labels,
            timestamps=basis_score.index if isinstance(basis_score.index, pd.DatetimeIndex) else None,
            min_dwell_samples=min_dwell_samples,
            min_dwell_seconds=min_dwell_seconds,
            health_map=None,  # compute health after smoothing to avoid stale map
        )
        quality_ok = bool(regime_model.meta.get("quality_ok", True))

        out["regime_model"] = regime_model
        out["regime_labels_train"] = train_labels
        out["regime_labels"] = score_labels
        out["regime_confidence"] = score_confidence  # V11: Assignment confidence
        out["regime_is_novel"] = score_is_novel  # v11.3.1: Novelty flag
        out["regime_novel_count"] = int(np.sum(score_is_novel))  # v11.3.1: Count of novel points
        derived_k = regime_model.meta.get("best_k")
        if derived_k is None:
            derived_k = regime_model.n_clusters  # v11.1.0: Property works for HDBSCAN/GMM
        out["regime_k"] = int(derived_k) if derived_k is not None else 0
        out["regime_score"] = float(regime_model.meta.get("fit_score", 0.0))
        out["regime_metric"] = str(regime_model.meta.get("fit_metric", "silhouette"))
        centers = regime_model.cluster_centers_  # v11.1.0: Property works for HDBSCAN/GMM
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
            frame["regime_confidence"] = score_confidence  # V11: Add confidence to frame
            frame["regime_is_novel"] = score_is_novel  # v11.3.1: Add novelty flag
            out["frame"] = frame
        return out

    if bool(_cfg_get(cfg, "regimes.allow_legacy_label", False)):
        Console.warn(
            "Using legacy regime labeling path (regimes.allow_legacy_label=True). "
            "This path is deprecated and will be removed. Ensure regime model is valid before scoring.",
            component="REGIME",
            n_samples=len(score_df) if hasattr(score_df, "__len__") else 0,
        )
        return _legacy_label(score_df, ctx, out, cfg)
    raise RuntimeError("Regime model unavailable and legacy path disabled (regimes.allow_legacy_label=False)")

# TO-DO Why is this needed and why is _fit_auto_k used here?
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
    # GaussianMixture uses means_ not cluster_centers_
    out["regime_centers"] = _as_f32(model.means_)
    frame = out.get("frame")
    if frame is not None:
        frame["regime_label"] = labels
        out["frame"] = frame
    return out

# ----------------------------
# Model Persistence Functions
# ----------------------------

def detect_transient_states(
    data: pd.DataFrame,
    regime_labels: np.ndarray,
    cfg: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """Compatibility wrapper; context semantics now live in core.context_engine."""
    return _context_detect_transient_states(data, regime_labels, cfg=cfg)


def apply_regime_health_labels(
    frame: pd.DataFrame,
    regime_model: Optional[RegimeModel],
    regime_quality_ok: bool,
    cfg: Dict[str, Any],
    output_manager: Optional[Any] = None,
    logger: Any = Console,
) -> Tuple[pd.DataFrame, Dict[int, Dict[str, float]]]:
    """
    Apply regime health labels to the scoring frame and persist regime summary.
    """
    regime_stats: Dict[int, Dict[str, float]] = {}

    if not regime_quality_ok and "regime_label" in frame.columns:
        frame["regime_state"] = "unknown"

    if (
        regime_model is not None
        and regime_quality_ok
        and "regime_label" in frame.columns
        and "fused" in frame.columns
    ):
        regime_stats = update_health_labels(
            regime_model,
            frame["regime_label"].to_numpy(copy=False),
            frame["fused"],
            cfg,
        )
        frame["regime_state"] = frame["regime_label"].map(
            lambda x: regime_model.health_labels.get(int(x), "unknown")
        )
        summary_df = build_summary_dataframe(regime_model)
        if output_manager is not None and not summary_df.empty:
            output_manager.write_dataframe(summary_df, "regime_summary")

    if "regime_label" in frame.columns and "regime_state" not in frame.columns:
        frame["regime_state"] = frame["regime_label"].map(
            lambda lbl: "unknown" if lbl == -1 else f"regime_{lbl}"
        )

    return frame, regime_stats


@dataclass
class RegimeBasisBuildResult:
    """Result bundle for regime basis build and cached-model compatibility check."""
    regime_basis_train: Optional[pd.DataFrame]
    regime_basis_score: Optional[pd.DataFrame]
    regime_basis_meta: Dict[str, Any]
    regime_basis_hash: Optional[int]
    regime_model: Optional[RegimeModel]
    degraded: bool
    basis_drift_decision: SchemaDriftDecision = field(default_factory=SchemaDriftDecision)


def build_regime_feature_basis_stage(
    *,
    train_features: pd.DataFrame,
    score_features: pd.DataFrame,
    raw_train: Optional[pd.DataFrame],
    raw_score: Optional[pd.DataFrame],
    pca_detector: Optional[Any],
    cfg: Dict[str, Any],
    regime_model: Optional[RegimeModel],
    equip: str,
    logger: Any = Console,
) -> RegimeBasisBuildResult:
    """
    Build regime feature basis and ensure cached regime model compatibility.
    """
    regime_basis_train: Optional[pd.DataFrame] = None
    regime_basis_score: Optional[pd.DataFrame] = None
    regime_basis_meta: Dict[str, Any] = {}
    regime_basis_hash: Optional[int] = None
    degraded = False
    basis_drift_decision = SchemaDriftDecision()

    try:
        basis_train, basis_score, basis_meta = build_feature_basis(
            train_features=train_features,
            score_features=score_features,
            raw_train=raw_train,
            raw_score=raw_score,
            pca_detector=pca_detector,
            cfg=cfg,
        )

        regime_cfg_str = str(cfg.get("regimes", {}))
        schema_str = ",".join(sorted(basis_train.columns)) + "|" + regime_cfg_str
        regime_basis_hash = int(hashlib.sha256(schema_str.encode()).hexdigest()[:15], 16)
        regime_basis_train = basis_train
        regime_basis_score = basis_score
        regime_basis_meta = basis_meta
    except Exception as e:
        logger.warn(
            f"Regime basis build failed (regimes will be unavailable): {e}",
            component="REGIME",
            equip=equip,
            error=str(e)[:200],
        )
        degraded = True

    cached_model_meta = getattr(regime_model, "meta", {}) if regime_model is not None else {}
    cached_model_version = cached_model_meta.get("model_version") if isinstance(cached_model_meta, dict) else None
    version_mismatch = cached_model_version is not None and cached_model_version != REGIME_MODEL_VERSION

    basis_drift_decision = classify_regime_basis_drift(
        regime_model=regime_model,
        regime_basis_train=regime_basis_train,
        cached_model_version=cached_model_version,
        current_model_version=REGIME_MODEL_VERSION,
    )

    if regime_model is not None and (
        regime_basis_train is None
        or regime_model.feature_columns != list(regime_basis_train.columns)
        or version_mismatch
    ):
        logger.warn(
            "Cached regime model is incompatible with the active basis contract; will refit.",
            component="REGIME",
            equip=equip,
            cached_cols=regime_model.feature_columns[:5] if regime_model.feature_columns else [],
            current_cols=list(regime_basis_train.columns)[:5] if regime_basis_train is not None else [],
            cached_model_version=cached_model_version,
            current_model_version=REGIME_MODEL_VERSION,
        )
        regime_model = None

    return RegimeBasisBuildResult(
        regime_basis_train=regime_basis_train,
        regime_basis_score=regime_basis_score,
        regime_basis_meta=regime_basis_meta,
        regime_basis_hash=regime_basis_hash,
        regime_model=regime_model,
        degraded=degraded,
        basis_drift_decision=basis_drift_decision,
    )


@dataclass
class RegimeLabelingStageResult:
    """Result bundle for regime labeling orchestration."""
    frame: pd.DataFrame
    score_out: Dict[str, Any]
    regime_model: Optional[RegimeModel]
    train_regime_labels: Optional[np.ndarray]
    score_regime_labels: Optional[np.ndarray]
    regime_quality_ok: bool
    regime_state_version: int
    regime_loaded_from_state: bool
    regime_model_was_trained: bool = False


def run_regime_labeling_stage(
    score_df: pd.DataFrame,
    frame: pd.DataFrame,
    train_df: pd.DataFrame,
    cfg: Dict[str, Any],
    regime_basis_train: Optional[pd.DataFrame],
    regime_basis_score: Optional[pd.DataFrame],
    regime_basis_meta: Dict[str, Any],
    regime_basis_hash: Optional[int],
    regime_model: Optional[RegimeModel],
    regime_loaded_from_state: bool,
    regime_state: Optional[Any],
    regime_state_version: int,
    raw_train: Optional[pd.DataFrame],
    output_manager: Optional[Any],
    current_model_maturity: Optional[str],
    equip: str,
    equip_id: int,
    sql_client: Optional[Any],
    logger: Any = Console,
    record_regime_fn: Optional[Callable[..., Any]] = None,
) -> RegimeLabelingStageResult:
    """
    Run regime labeling stage including state reconstruction, labeling, and state persistence.
    """
    regime_model_was_trained = False

    if regime_loaded_from_state and regime_state is not None and regime_basis_train is not None:
        regime_model = regime_state_to_model(
            state=regime_state,
            feature_columns=list(regime_basis_train.columns),
            raw_tags=list(raw_train.columns) if raw_train is not None else [],
            train_hash=regime_basis_hash,
        )

    regime_ctx: Dict[str, Any] = {
        "regime_basis_train": regime_basis_train,
        "regime_basis_score": regime_basis_score,
        "basis_meta": regime_basis_meta,
        "regime_model": regime_model,
        "regime_basis_hash": regime_basis_hash,
        "X_train": train_df,
        "model_maturity": current_model_maturity,
    }
    regime_out = label(score_df, regime_ctx, {"frame": frame}, cfg)
    frame = regime_out.get("frame", frame)
    new_regime_model = regime_out.get("regime_model", regime_model)

    if new_regime_model is not regime_model and new_regime_model is not None:
        regime_model_was_trained = True
        regime_model = new_regime_model

    score_regime_labels = regime_out.get("regime_labels")
    train_regime_labels = regime_out.get("regime_labels_train")
    regime_quality_ok = bool(regime_out.get("regime_quality_ok", True))

    if train_regime_labels is None and regime_model is not None and regime_basis_train is not None:
        train_regime_labels = predict_regime(regime_model, regime_basis_train)
    if score_regime_labels is None and regime_model is not None and regime_basis_score is not None:
        score_regime_labels = predict_regime(regime_model, regime_basis_score)

    if (
        record_regime_fn is not None
        and score_regime_labels is not None
        and len(score_regime_labels) > 0
    ):
        current_regime_id = int(score_regime_labels[-1]) if hasattr(score_regime_labels[-1], "__int__") else 0
        regime_label = ""
        if regime_model is not None and hasattr(regime_model, "cluster_labels_"):
            regime_label = regime_model.cluster_labels_.get(current_regime_id, f"regime_{current_regime_id}")
        record_regime_fn(equip, current_regime_id, regime_label)

    if regime_model_was_trained and regime_model is not None:
        from core.model_persistence import save_regime_state

        regime_cfg_str = str(cfg.get("regimes", {}))
        config_hash = hashlib.sha256(regime_cfg_str.encode()).hexdigest()[:16]
        new_state = regime_model_to_state(
            model=regime_model,
            equip_id=equip_id,
            state_version=regime_state_version + 1,
            config_hash=config_hash,
            regime_basis_hash=str(regime_basis_hash) if regime_basis_hash else "",
        )
        save_regime_state(
            state=new_state,
            equip=equip,
            sql_client=sql_client,
        )
        regime_state_version = new_state.state_version
        logger.info(
            f"Regime state saved v{regime_state_version}: K={new_state.n_clusters} -> ACM_RegimeState",
            component="REGIME_STATE",
        )

    write_regime_definitions_for_audit(
        output_manager=output_manager,
        regime_model=regime_model,
        regime_state_version=regime_state_version,
        current_model_maturity=current_model_maturity,
        logger=logger,
        equip=equip,
    )

    return RegimeLabelingStageResult(
        frame=frame,
        score_out=regime_out,
        regime_model=regime_model,
        train_regime_labels=train_regime_labels,
        score_regime_labels=score_regime_labels,
        regime_quality_ok=regime_quality_ok,
        regime_state_version=regime_state_version,
        regime_loaded_from_state=regime_loaded_from_state,
        regime_model_was_trained=regime_model_was_trained,
    )


@dataclass
class ScoringRegimeStageResult:
    """Result bundle for detector scoring plus regime labeling stages."""
    frame: pd.DataFrame
    omr_contributions_data: Optional[pd.DataFrame]
    score_out: Dict[str, Any]
    regime_model: Optional[RegimeModel]
    train_regime_labels: Optional[np.ndarray]
    score_regime_labels: Optional[np.ndarray]
    regime_quality_ok: bool
    regime_state_version: int
    regime_loaded_from_state: bool
    degraded_regime_basis: bool
    current_model_maturity: Optional[str]
    basis_drift_decision: SchemaDriftDecision = field(default_factory=SchemaDriftDecision)
    regime_model_was_trained: bool = False


def run_scoring_regime_stage(
    *,
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    raw_train: Optional[pd.DataFrame],
    raw_score: Optional[pd.DataFrame],
    cfg: Dict[str, Any],
    pca_detector: Optional[Any],
    regime_model: Optional[RegimeModel],
    regime_state: Optional[Any],
    regime_state_version: int,
    regime_loaded_from_state: bool,
    det_flags: Dict[str, bool],
    detectors: Dict[str, Any],
    equip: str,
    equip_id: int,
    sql_client: Any,
    output_manager: Any,
    refit_requested: bool,
    section_fn: Any,
    score_all_detectors_fn: Any,
    resolve_maturity_for_regime_stage_fn: Any,
    record_regime_fn: Optional[Callable[..., Any]] = None,
    logger: Any = Console,
) -> ScoringRegimeStageResult:
    """
    Execute scoring and regime stages.

    Stage order:
    1. Regime feature-basis build
    2. Detector scoring
    3. Regime maturity resolve
    4. Regime labeling
    5. Regime occupancy/transition persistence
    """
    basis_result = build_regime_feature_basis_stage(
        train_features=train_df,
        score_features=score_df,
        raw_train=raw_train,
        raw_score=raw_score,
        pca_detector=pca_detector,
        cfg=cfg,
        regime_model=regime_model,
        equip=equip,
        logger=logger,
    )
    regime_basis_train = basis_result.regime_basis_train
    regime_basis_score = basis_result.regime_basis_score
    regime_basis_meta = basis_result.regime_basis_meta
    regime_basis_hash = basis_result.regime_basis_hash
    regime_model = basis_result.regime_model

    with section_fn("score.detector_score"):
        frame, omr_contributions_data = score_all_detectors_fn(
            data=score_df,
            ar1_detector=detectors.get("ar1_detector"),
            pca_detector=detectors.get("pca_detector"),
            iforest_detector=detectors.get("iforest_detector"),
            gmm_detector=detectors.get("gmm_detector"),
            omr_detector=detectors.get("omr_detector"),
            **det_flags,
        )

    current_model_maturity = resolve_maturity_for_regime_stage_fn(
        sql_client=sql_client,
        equip_id=equip_id,
        refit_requested=refit_requested,
        logger=logger,
    )

    with section_fn("regimes.label"):
        regime_labeling_result = run_regime_labeling_stage(
            score_df=score_df,
            frame=frame,
            train_df=train_df,
            cfg=cfg,
            regime_basis_train=regime_basis_train,
            regime_basis_score=regime_basis_score,
            regime_basis_meta=regime_basis_meta,
            regime_basis_hash=regime_basis_hash,
            regime_model=regime_model,
            regime_loaded_from_state=regime_loaded_from_state,
            regime_state=regime_state,
            regime_state_version=regime_state_version,
            raw_train=raw_train,
            output_manager=output_manager,
            current_model_maturity=current_model_maturity,
            equip=equip,
            equip_id=equip_id,
            sql_client=sql_client,
            logger=logger,
            record_regime_fn=record_regime_fn,
        )

    frame = regime_labeling_result.frame
    score_out = regime_labeling_result.score_out
    regime_model = regime_labeling_result.regime_model
    train_regime_labels = regime_labeling_result.train_regime_labels
    score_regime_labels = regime_labeling_result.score_regime_labels
    regime_quality_ok = regime_labeling_result.regime_quality_ok
    regime_state_version = regime_labeling_result.regime_state_version
    regime_loaded_from_state = regime_labeling_result.regime_loaded_from_state

    with section_fn("regimes.occupancy"):
        write_regime_occupancy_and_transitions(
            score_regime_labels=score_regime_labels,
            frame=frame,
            output_manager=output_manager,
            logger=logger,
            equip=equip,
        )

    return ScoringRegimeStageResult(
        frame=frame,
        omr_contributions_data=omr_contributions_data,
        score_out=score_out,
        regime_model=regime_model,
        train_regime_labels=train_regime_labels,
        score_regime_labels=score_regime_labels,
        regime_quality_ok=bool(score_out.get("regime_quality_ok", True)),
        regime_state_version=regime_state_version,
        regime_loaded_from_state=regime_loaded_from_state,
        degraded_regime_basis=basis_result.degraded,
        current_model_maturity=current_model_maturity,
        basis_drift_decision=basis_result.basis_drift_decision,
        regime_model_was_trained=regime_labeling_result.regime_model_was_trained,
    )


def apply_transient_state_labels(
    frame: pd.DataFrame,
    score_data: pd.DataFrame,
    cfg: Dict[str, Any],
    logger: Any = Console,
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Compatibility wrapper; context semantics now live in core.context_engine."""
    return _context_apply_transient_state_labels(frame, score_data, cfg, logger=logger)


@dataclass
class RegimePostprocessResult:
    """Result bundle for regime health and transient post-processing."""
    frame: pd.DataFrame
    transient_counts: Dict[str, int]
    context_assignment: ContextAssignment


def run_regime_postprocess_stage(
    *,
    frame: pd.DataFrame,
    score_data: pd.DataFrame,
    regime_model: Optional[RegimeModel],
    regime_quality_ok: bool,
    cfg: Dict[str, Any],
    output_manager: Optional[Any] = None,
    logger: Any = Console,
) -> RegimePostprocessResult:
    """
    Apply regime health labels, transient labels, and emit consolidated regime log.
    """
    frame, _ = apply_regime_health_labels(
        frame=frame,
        regime_model=regime_model,
        regime_quality_ok=regime_quality_ok,
        cfg=cfg,
        output_manager=output_manager,
        logger=logger,
    )

    frame, transient_counts = apply_transient_state_labels(
        frame=frame,
        score_data=score_data,
        cfg=cfg,
        logger=logger,
    )

    regime_assigned = frame["regime_label"].notna().sum() if "regime_label" in frame.columns else 0
    quality_notes = list(regime_model.meta.get("quality_notes", [])) if regime_model is not None else []
    notes_str = f" | notes={quality_notes}" if (not regime_quality_ok and quality_notes) else ""
    logger.info(
        f"Regime quality: {'OK' if regime_quality_ok else 'FAIL'}{notes_str} | assigned={regime_assigned} | transient={transient_counts}",
        component="REGIME",
    )

    return RegimePostprocessResult(
        frame=frame,
        transient_counts=transient_counts,
        context_assignment=build_context_assignment(frame),
    )


def write_regime_occupancy_and_transitions(
    score_regime_labels: Optional[np.ndarray],
    frame: pd.DataFrame,
    output_manager: Optional[Any],
    logger: Any = Console,
    equip: str = "",
) -> Tuple[int, int]:
    """
    Persist regime occupancy and transition aggregates for the current score window.
    """
    occupancy_count = 0
    transition_count = 0

    try:
        if score_regime_labels is None or len(score_regime_labels) == 0 or output_manager is None:
            return occupancy_count, transition_count

        regime_series = pd.Series(score_regime_labels)
        regime_counts = regime_series.value_counts()
        total_points = len(score_regime_labels)

        sampling_interval_h = 1.0
        if "Timestamp" in frame.columns and len(frame) > 1:
            try:
                ts_diff = pd.to_datetime(frame["Timestamp"]).diff().dropna()
                if len(ts_diff) > 0:
                    sampling_interval_h = ts_diff.median().total_seconds() / 3600.0
            except Exception:
                pass

        occupancy_data: List[Dict[str, Any]] = []
        for regime_id, count in regime_counts.items():
            occupancy_data.append(
                {
                    "RegimeLabel": str(regime_id),
                    "DwellTimeHours": float(count * sampling_interval_h),
                    "DwellFraction": float(count / total_points) if total_points > 0 else 0.0,
                    "PointCount": int(count),
                }
            )
        if occupancy_data:
            occupancy_count = output_manager.write_regime_occupancy(occupancy_data)

        if len(score_regime_labels) > 1:
            transitions: Dict[str, Dict[str, int]] = {}
            for i in range(1, len(score_regime_labels)):
                from_r = str(score_regime_labels[i - 1])
                to_r = str(score_regime_labels[i])
                if from_r != to_r:
                    if from_r not in transitions:
                        transitions[from_r] = {}
                    transitions[from_r][to_r] = transitions[from_r].get(to_r, 0) + 1
            if transitions:
                transition_count = output_manager.write_regime_transitions(transitions)

        # OUTPUT lines for ACM_RegimeOccupancy / ACM_RegimeTransitions already confirm the writes; no duplicate log here.
    except Exception as e:
        logger.warn(
            f"Regime occupancy/transitions write failed: {e}",
            component="REGIME",
            equip=equip,
            error=str(e)[:200],
        )

    return occupancy_count, transition_count


def write_regime_definitions_for_audit(
    output_manager: Optional[Any],
    regime_model: Optional[Any],
    regime_state_version: int,
    current_model_maturity: Optional[str],
    logger: Any = Console,
    equip: str = "",
) -> int:
    """
    Persist current run regime definitions for auditability.
    """
    if not output_manager or regime_model is None or not getattr(regime_model, "model", None):
        return 0

    try:
        regime_defs: List[Dict[str, Any]] = []
        centroids = regime_model.cluster_centers_
        labels = getattr(regime_model.model, "labels_", [])
        unique_labels = np.unique(labels)
        valid_labels = unique_labels[unique_labels >= 0]
        model_silhouette = regime_model.meta.get("fit_score")
        model_silhouette = (
            float(model_silhouette)
            if model_silhouette is not None and not np.isnan(model_silhouette)
            else None
        )

        for i, centroid in enumerate(centroids):
            regime_id = int(valid_labels[i]) if i < len(valid_labels) else i
            regime_defs.append(
                {
                    "RegimeID": regime_id,
                    "RegimeName": f"Regime_{regime_id}",
                    "CentroidJSON": json.dumps(centroid.tolist()),
                    "FeatureColumns": json.dumps(getattr(regime_model, "feature_columns", [])),
                    "DataPointCount": int(np.sum(np.array(labels) == regime_id)) if len(labels) > 0 else 0,
                    "SilhouetteScore": model_silhouette,
                    "MaturityState": current_model_maturity or "UNKNOWN",
                }
            )

        regime_defs_count = output_manager.write_regime_definitions(regime_defs, version=regime_state_version)
        # SQL insert confirmation from OUTPUT component is sufficient; no duplicate log here.
        return regime_defs_count
    except Exception as e:
        logger.warn(
            f"Failed to write regime definitions: {e}",
            component="REGIME",
            equip=equip,
            error=str(e)[:200],
        )
        return 0

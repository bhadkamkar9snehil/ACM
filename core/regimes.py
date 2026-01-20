# core/regimes.py
# Fast + memory-safe regime labeling with auto-k.
# v11.1.0: HDBSCAN as primary clustering for density-based regime detection
from __future__ import annotations
from collections import deque, Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING
import json
try:
    import orjson  # type: ignore
except Exception:
    orjson = None  # type: ignore
import numpy as np
import pandas as pd
from pathlib import Path

import joblib
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
try:
    from core.output_manager import OutputManager
except Exception:
    OutputManager = None  # type: ignore
import matplotlib.pyplot as plt

from core.observability import Console, Span
import hashlib

try:
    from scipy.ndimage import median_filter as _median_filter
except Exception:  # pragma: no cover - scipy optional in some deployments
    _median_filter = None

REGIME_MODEL_VERSION = "3.1"  # v11.3.1: Removed UNKNOWN regime concept

# v11.3.1: DEPRECATED - UNKNOWN_REGIME_LABEL (-1) is no longer produced
# Equipment is ALWAYS in some physical operating state. Instead of UNKNOWN:
# - label: Always assigned to nearest cluster (equipment IS in a state)
# - confidence: Low for sparse/novel regions (how sure we are)
# - is_novel: True if point was in sparse region (candidate for new regime discovery)
#
# This constant remains for backward compatibility with legacy code that may
# check for -1, but new code should never produce it.
UNKNOWN_REGIME_LABEL = -1  # DEPRECATED: Do not produce this value

# =============================================================================
# TAG TAXONOMY: Explicit classification of sensor types for regime clustering
# =============================================================================
# RULE R1: Regime clustering inputs = operating variables ONLY
# RULE R2: Condition variables may be used for health scoring, NEVER for regime definition
#
# WHY THIS MATTERS:
# If bearing temp or vibration participates in clustering, a degrading asset
# "creates a new regime" simply because it's hotter/noisier than before at the
# same load. This breaks the regime concept: you no longer have stable operating
# states; you have a mixture of operating_state + health_drift.
# =============================================================================

# OPERATING_TAG_KEYWORDS: Variables that define the operating mode/regime
# These represent controllable or process-driven operating conditions
OPERATING_TAG_KEYWORDS = [
    # Speed/rotation
    "speed", "rpm", "frequency", "hz", "vfd",
    # Load/power
    "load", "power", "torque", "kw", "mw",
    # Process variables
    "flow", "pressure", "discharge", "suction", "differential",
    # Control positions
    "valve", "guide_vane", "igv", "damper", "position",
    # Electrical (primary, not secondary effects)
    "current", "voltage", "amps",
    # Ambient/inlet conditions (environmental, not machine health)
    "ambient", "inlet_temp", "inlet_pressure", "atmospheric",
]

# CONDITION_TAG_KEYWORDS: Variables that indicate machine health/condition
# These should NEVER be used for regime clustering - they are health indicators
CONDITION_TAG_KEYWORDS = [
    # Bearing health
    "bearing", "brg", "journal",
    # Winding/electrical health
    "winding", "stator", "rotor",
    # Vibration (always condition, never operating mode)
    "vibration", "vib", "velocity", "acceleration", "displacement",
    # Oil/lubrication health
    "oil_temp", "oil_pressure", "debris", "particle", "contamination",
    # Thermal degradation indicators
    "exhaust", "hot_spot", "thermal",
    # Acoustic/ultrasonic
    "acoustic", "ultrasonic", "noise",
]

# v11.3.0: HEALTH-STATE VARIABLES FOR REGIME DEFINITION
# Rule R3: Pre-fault and post-fault equipment are DISTINCT regimes
# Health degradation is now tracked as part of regime structure, not filtered out
HEALTH_STATE_KEYWORDS = [
    # Synthetic health indicators (computed from detectors)
    "health_ensemble_z", "health_trend", "health_quartile",
    # Degradation markers
    "degradation", "fatigue", "wear",
]


class ModelVersionMismatch(Exception):
    """Raised when a cached regime model version differs from the expected version."""


def _parse_semver(version: str) -> Tuple[int, int, int]:
    """
    Parse semantic version string into (major, minor, patch) tuple.
    
    FIX #10: Supports version strings like "2.0", "2.1.0", "2"
    """
    parts = version.split(".")
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0
    return (major, minor, patch)


def _is_version_compatible(cached_version: str, expected_version: str) -> bool:
    """
    Check if cached model version is compatible with expected version.
    
    FIX #10: Implements semantic versioning compatibility:
    - Major version must match (breaking changes)
    - Minor version can be <= expected (backward compatible features)
    - Patch version is ignored (bug fixes)
    
    Examples:
    - cached="2.0", expected="2.1" -> True (minor upgrade)
    - cached="2.1", expected="2.0" -> True (can use newer model)
    - cached="1.9", expected="2.0" -> False (major mismatch)
    """
    try:
        cached_semver = _parse_semver(cached_version)
        expected_semver = _parse_semver(expected_version)
        
        # Major version must match
        if cached_semver[0] != expected_semver[0]:
            return False
        
        # Same major version = compatible
        return True
    except Exception:
        # If parsing fails, fall back to exact match
        return cached_version == expected_version
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
    "regimes.unknown.enabled": (bool, True, True, "Enable UNKNOWN regime for low-confidence assignments"),
    "regimes.unknown.distance_percentile": (float, 0.0, 100.0, "Distance percentile threshold for UNKNOWN"),
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
    val = cur
    if default is not None:
        expected_type = type(default)
        if expected_type in (int, float, bool, str) and not isinstance(val, expected_type):
            try:
                val = expected_type(val)
            except Exception:
                return default
    return val

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


def _add_health_state_features(
    features_df: pd.DataFrame,
    detector_scores: Dict[str, np.ndarray]
) -> pd.DataFrame:
    """
    Add health-state variables to regime clustering input.
    
    v11.3.0: Health state is now part of regime definition, not excluded.
    This allows clustering to distinguish:
    - Same operating mode but different health state (pre-fault vs degraded)
    - Normal transitions vs fault-driven transitions
    
    Rule R3 (v11.3.0): Pre-fault and post-fault equipment are DISTINCT regimes.
    Equipment at Health=95% is fundamentally different from Health=20%, even
    at identical load/speed. These are separate operating regimes.
    
    Args:
        features_df: DataFrame with operating variables (load, speed, etc.)
        detector_scores: Dict mapping detector names to z-score arrays
        
    Returns:
        DataFrame with both operating and health-state variables
    """
    features_with_health = features_df.copy()
    
    # HEALTH-STATE VARIABLES (v11.3.0)
    # These capture equipment degradation state and are now integral to regimes
    
    # 1. Ensemble Anomaly Score (normalized health indicator)
    # Combines AR1, PCA-SPE, PCA-T2 for robust health assessment
    ensemble_components = []
    for col in ['ar1_z', 'pca_spe_z', 'pca_t2_z']:
        if col in detector_scores:
            arr = np.asarray(detector_scores[col], dtype=float)
            ensemble_components.append(arr)
    
    if ensemble_components:
        ensemble_z = np.nanmean(ensemble_components, axis=0)
        # Clamp to [-3, 3] to avoid outliers distorting clustering
        ensemble_z_clipped = np.clip(ensemble_z, -3.0, 3.0)
        features_with_health['health_ensemble_z'] = ensemble_z_clipped
        
        # 2. Health Degradation Trend (20-point rolling mean of ensemble)
        # Captures sustained degradation (not transient spikes)
        trend_series = pd.Series(ensemble_z_clipped)
        trend = trend_series.rolling(window=20, min_periods=5, center=False).mean()
        trend_filled = trend.fillna(method='bfill').fillna(method='ffill').fillna(0)
        trend_clipped = np.clip(trend_filled.values, -3.0, 3.0)
        features_with_health['health_trend'] = trend_clipped
        
        # 3. Health State Quartile (binned health level: 0=healthy, 3=critical)
        # Assigns each point to a health quartile based on ensemble score distribution
        try:
            quartiles = pd.qcut(
                ensemble_z_clipped,
                q=4,
                labels=[0, 1, 2, 3],
                duplicates='drop'
            )
            health_quartile = quartiles.astype(float).fillna(0)
        except Exception:
            # If qcut fails (e.g., all same value), use simple binning
            health_quartile = np.clip(ensemble_z_clipped / 3.0 + 1.5, 0, 3).astype(float)
        
        features_with_health['health_quartile'] = health_quartile
        
        Console.info(
            f"Added health-state features: ensemble_z, trend, quartile (v11.3.0)",
            component="REGIME",
            n_samples=len(features_with_health)
        )
    else:
        Console.warn(
            "Could not compute health-state features: missing detector scores",
            component="REGIME"
        )
    
    return features_with_health


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
    scaler: StandardScaler
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
        if not HDBSCAN_AVAILABLE:
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


def _classify_tag(col_name: str, cfg: Optional[Dict[str, Any]] = None) -> str:
    """
    Classify a sensor tag as 'operating' or 'condition' based on taxonomy.
    
    v11.1.6 FIX #1: Explicit tag classification to prevent regime contamination.
    
    Args:
        col_name: Column/tag name to classify
        cfg: Optional config with custom keyword overrides
    
    Returns:
        'operating' if tag represents operating mode variable
        'condition' if tag represents health/condition indicator
        'unknown' if cannot be classified
    """
    col_lower = col_name.lower()
    
    # Get custom keywords from config if provided
    basis_cfg = _cfg_get(cfg or {}, "regimes.feature_basis", {}) or {}
    custom_operating = basis_cfg.get("custom_operating_keywords", [])
    custom_condition = basis_cfg.get("custom_condition_keywords", [])
    
    # Check custom condition keywords FIRST (explicit exclusions take priority)
    for kw in custom_condition:
        if kw.lower() in col_lower:
            return "condition"
    
    # Check default condition keywords
    for kw in CONDITION_TAG_KEYWORDS:
        if kw in col_lower:
            return "condition"
    
    # Check custom operating keywords
    for kw in custom_operating:
        if kw.lower() in col_lower:
            return "operating"
    
    # Check default operating keywords
    for kw in OPERATING_TAG_KEYWORDS:
        if kw in col_lower:
            return "operating"
    
    return "unknown"


def _compute_basis_signature(feature_columns: List[str], scaler_mean: Optional[List[float]], 
                              scaler_var: Optional[List[float]], n_pca: int) -> str:
    """
    Compute a deterministic signature for the feature basis configuration.
    
    v11.1.6 FIX #8: Used to detect basis drift and invalidate cached models.
    
    Returns:
        MD5 hash string of basis configuration
    """
    sig_parts = [
        "cols:" + ",".join(sorted(feature_columns)),
        f"n_pca:{n_pca}",
    ]
    if scaler_mean is not None:
        sig_parts.append("mean:" + ",".join(f"{x:.6f}" for x in scaler_mean[:5]))  # First 5 for brevity
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
    """Construct a compact feature matrix for regime clustering.
    
    v11.1.6 CRITICAL FIXES:
    - FIX #1: Uses tag taxonomy to EXCLUDE condition indicators (bearing, winding, vibration)
    - FIX #2: Applies uniform scaling to ENTIRE basis (PCA + raw), not partial
    - FIX #8: Computes basis_signature for cache invalidation
    
    RULE R1: Regime clustering inputs = operating variables ONLY
    RULE R2: Condition variables are for health scoring, NEVER regime definition
    """
    basis_cfg = _cfg_get(cfg, "regimes.feature_basis", {})
    n_pca = int(basis_cfg.get("n_pca_components", 3))
    raw_tags_cfg = basis_cfg.get("raw_tags", []) or []
    
    # v10.1.0: New mode to use raw sensors for operationally-meaningful regimes
    use_raw_sensors = bool(basis_cfg.get("use_raw_sensors", True))  # Default ON
    
    # v11.1.6 FIX #1: Use taxonomy-based classification instead of simple keyword match
    # The old approach included "bearing" and "winding" which are CONDITION indicators!
    strict_operating_only = bool(basis_cfg.get("strict_operating_only", True))  # Default ON

    train_parts: List[pd.DataFrame] = []
    score_parts: List[pd.DataFrame] = []
    used_raw_tags: List[str] = []
    excluded_condition_tags: List[str] = []  # Track what we excluded for logging
    n_pca_used = 0
    pca_variance_ratio: Optional[float] = None
    pca_variance_vector: List[float] = []

    # v10.1.0: Prioritize raw sensor data for regime clustering if available
    if use_raw_sensors and raw_train is not None and raw_score is not None:
        # v11.1.6 FIX #1: Use taxonomy-based classification
        available_operational = []
        for col in raw_train.columns:
            tag_class = _classify_tag(col, cfg)
            
            if tag_class == "condition":
                # NEVER include condition indicators in regime basis
                excluded_condition_tags.append(col)
            elif tag_class == "operating":
                available_operational.append(col)
            elif not strict_operating_only:
                # Unknown tags included only if strict mode is off
                available_operational.append(col)
        
        # Log excluded condition tags (important for transparency)
        if excluded_condition_tags:
            Console.info(
                f"Excluded {len(excluded_condition_tags)} condition indicators from regime basis: "
                f"{excluded_condition_tags[:5]}{'...' if len(excluded_condition_tags) > 5 else ''}",
                component="REGIME", excluded_count=len(excluded_condition_tags)
            )
        
        # Also include any explicitly configured raw_tags (but warn if they're condition tags)
        for tag in raw_tags_cfg:
            if tag in raw_train.columns and tag not in available_operational:
                tag_class = _classify_tag(tag, cfg)
                if tag_class == "condition":
                    Console.warn(
                        f"Configured raw_tag '{tag}' is a condition indicator - excluding from regime basis. "
                        f"Use custom_operating_keywords to override if this is intentional.",
                        component="REGIME", tag=tag
                    )
                else:
                    available_operational.append(tag)
        
        if available_operational:
            Console.info(f"Using {len(available_operational)} raw operational sensors for regime clustering: {available_operational[:5]}{'...' if len(available_operational) > 5 else ''}", component="REGIME")
            used_raw_tags = available_operational
            train_raw = raw_train.reindex(train_features.index)[available_operational].astype(float).ffill().bfill().fillna(0.0)
            score_raw = raw_score.reindex(score_features.index)[available_operational].astype(float).ffill().bfill().fillna(0.0)
            train_parts.append(train_raw)
            score_parts.append(score_raw)
        else:
            Console.warn(f"No operational columns found matching OPERATING_TAG_KEYWORDS. Falling back to PCA features.", component="REGIME", available_cols=len(raw_train.columns) if raw_train is not None else 0)

    # Only use PCA features if raw sensors not available or insufficient
    if not train_parts and pca_detector is not None and getattr(pca_detector, "pca", None) is not None:
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
                    
                    # FIX #5: Validate PCA variance for numerical stability
                    if not np.isfinite(pca_variance_ratio) or pca_variance_ratio < 0 or pca_variance_ratio > 1.0:
                        Console.warn(f"PCA variance ratio out of bounds: {pca_variance_ratio}. Resetting to NaN.", component="REGIME", variance_ratio=pca_variance_ratio, n_components=n_pca_used)
                        pca_variance_ratio = float("nan")
                        pca_variance_vector = None
                    elif any(not np.isfinite(v) for v in pca_variance_vector):
                        Console.warn("PCA variance vector contains non-finite values. Check numerical stability.", component="REGIME", n_components=n_pca_used)
                        
                cols = [f"PCA_{i+1}" for i in range(n_pca_used)]
                train_parts.append(pd.DataFrame(train_scores[:, :n_pca_used], index=train_features.index, columns=cols))
                score_parts.append(pd.DataFrame(score_scores[:, :n_pca_used], index=score_features.index, columns=cols))
        except Exception:
            n_pca_used = 0

    # Legacy raw_tags handling (when use_raw_sensors=False)
    if not use_raw_sensors and raw_train is not None and raw_score is not None:
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

    # v11.1.6 FIX #2: Apply UNIFORM scaling to the ENTIRE basis (PCA + raw)
    # Previously, only raw columns were scaled while PCA columns were left as-is.
    # This caused clustering to be dominated by whichever subspace had larger variance.
    # Now we scale ALL columns uniformly to give equal weight to all features.
    all_cols = list(train_basis.columns)
    basis_scaler: StandardScaler = StandardScaler()
    basis_scaler.fit(train_basis[all_cols].values)
    train_basis.loc[:, all_cols] = basis_scaler.transform(train_basis[all_cols].values)
    score_basis.loc[:, all_cols] = basis_scaler.transform(score_basis[all_cols].values)

    # Compute basis signature for cache invalidation (FIX #8)
    mean_vec_list = [float(x) for x in basis_scaler.mean_] if hasattr(basis_scaler, 'mean_') else None
    var_vec_list = [float(x) for x in basis_scaler.var_] if hasattr(basis_scaler, 'var_') else None
    basis_signature = _compute_basis_signature(all_cols, mean_vec_list, var_vec_list, n_pca_used)

    meta = {
        "n_pca": n_pca_used,
        "raw_tags": used_raw_tags,
        "excluded_condition_tags": excluded_condition_tags,  # v11.1.6: Track excluded tags
        "fallback_cols": list(train_basis.columns),
        "basis_normalized": True,  # v11.1.6: Always True now (uniform scaling)
        "basis_signature": basis_signature,  # v11.1.6 FIX #8: For cache invalidation
    }
    # Store scaler parameters for reproducibility
    if hasattr(basis_scaler, 'mean_'):
        meta["basis_scaler_mean"] = mean_vec_list
    if hasattr(basis_scaler, 'var_'):
        meta["basis_scaler_var"] = var_vec_list
    meta["basis_scaler_cols"] = all_cols  # v11.1.6: All columns are now scaled
    if pca_variance_ratio is not None:
        meta["pca_variance_ratio"] = pca_variance_ratio
        meta["pca_variance_vector"] = pca_variance_vector
        variance_min = float(basis_cfg.get("pca_variance_min", 0.85))
        meta["pca_variance_min"] = variance_min
        
        # FIX #5: Document that PCA variance is computed BEFORE non-PCA columns are scaled
        # The PCA components come from pca_detector which uses its own scaler
        # Non-PCA columns (raw sensors) are scaled separately via basis_scaler
        # This is intentional: PCA variance reflects original feature space explanation
        meta["pca_variance_note"] = "PCA variance computed on pre-scaled features by pca_detector"
        
        if pca_variance_ratio < variance_min:
            Console.warn(
                f"PCA variance coverage {pca_variance_ratio:.3f} below target {variance_min:.3f}.",
                component="REGIME", variance_ratio=pca_variance_ratio, variance_min=variance_min, n_pca=n_pca_used
            )
    return train_basis, score_basis, meta



# v11.1.0: Removed _fit_kmeans_scaled - using HDBSCAN (primary) and GMM (fallback) only

def _fit_gmm_scaled(
    X: np.ndarray,
    cfg: Dict[str, Any],
    *,
    pre_scaled: bool = False,
) -> Tuple[StandardScaler, GaussianMixture, int, float, str, List[Tuple[int, float]], bool]:
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
            gmm = GaussianMixture(
                n_components=k,
                covariance_type=covariance_type,
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
    best_model = GaussianMixture(
        n_components=best_k,
        covariance_type=covariance_type,
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
) -> Tuple[StandardScaler, Any, int, float, str, List[Tuple[int, float]], bool, np.ndarray]:
    """Fit HDBSCAN clustering for regime detection.
    
    v11.1.0: HDBSCAN is preferred for industrial regime detection because:
    1. No k specification needed - auto-detects optimal clusters
    2. Native noise handling - outliers labeled as -1 (UNKNOWN_REGIME)
    3. Handles varying density clusters (common in operational regimes)
    4. Robust to outliers - won't distort regime boundaries
    5. Hierarchical - provides cluster stability/persistence metrics
    
    v11.1.7: Added subsampling for large datasets to prevent O(n²) memory issues
    
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
    
    X = _finite_impute_inplace(X)
    if pre_scaled:
        scaler = _IdentityScaler()
        X_scaled = scaler.transform(X)
    else:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
    
    n_samples, n_features = X_scaled.shape
    
    # v11.1.7: PERFORMANCE FIX - Subsample for large datasets
    # HDBSCAN has O(n²) memory/time complexity, becomes very slow >10k samples
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
        quality_sweep: List[Tuple[int, float]] = []
        
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
                            f"ENSEMBLE: GMM fallback fitted with k={best_k} for noise point assignment",
                            component="REGIME"
                        )
                    except Exception as gmm_e:
                        Console.warn(f"GMM fallback fitting failed: {gmm_e}", component="REGIME")
                        fallback_gmm = None
                else:
                    fallback_gmm = None
                
                # If HDBSCAN produced low quality AND we have GMM fallback, try GMM
                if low_quality and use_gmm_fallback:
                    Console.warn("HDBSCAN produced low-quality clustering, trying GMM fallback", component="REGIME")
                    model = None
                    exemplars = None
                    fallback_gmm = None  # Clear ensemble if switching to pure GMM
                    
        except Exception as e:
            Console.warn(f"HDBSCAN failed: {e}. Trying fallback.", component="REGIME")
            model = None
            fallback_gmm = None
    elif clustering_method == "hdbscan" and not HDBSCAN_AVAILABLE:
        Console.warn("HDBSCAN requested but not installed. Falling back to GMM.", component="REGIME")
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
            Console.warn(f"GMM also failed: {e}. Trying KMeans fallback.", component="REGIME")
    
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
    distance_percentile = float(unknown_cfg.get("distance_percentile", 95.0))
    try:
        threshold, train_distances = _compute_training_distances(
            regime_model, train_basis, distance_percentile
        )
        regime_model.training_distance_threshold_ = threshold
        regime_model.training_distance_distribution_ = train_distances
        meta["training_distance_threshold"] = float(threshold)
        meta["training_distance_percentile"] = distance_percentile
    except Exception as e:
        Console.warn(f"Could not compute training distance threshold: {e}", component="REGIME")
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
    X_scaled = model.scaler.transform(aligned_arr)
    X_scaled = np.asarray(X_scaled, dtype=np.float64, order="C")
    
    # v11.1.0: Support HDBSCAN and GMM only
    # v11.3.1: Always assign to a cluster - never return UNKNOWN (-1)
    # Equipment is always in SOME operating state
    if model.is_hdbscan:
        # HDBSCAN: Use approximate_predict for new points
        try:
            labels, strengths = hdbscan.approximate_predict(model.clustering_model, X_scaled)
            labels = labels.astype(int, copy=True)  # Make mutable copy
            
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
    """
    Predict regime labels with confidence scores and novelty flags.
    
    v11.3.1: MAJOR CHANGE - No longer produces UNKNOWN_REGIME_LABEL (-1).
    Equipment is ALWAYS in some operating state. Instead:
    - label: Always assigned to a valid cluster (nearest centroid for sparse regions)
    - confidence: How confident we are in the assignment (low for sparse/novel regions)
    - is_novel: True if point would have been UNKNOWN under old logic (sparse region)
    
    Args:
        model: Fitted RegimeModel (should have training_distance_threshold_ set)
        basis_df: Data to predict on
        cfg: Configuration dict
        training_distances: Deprecated - use model.training_distance_threshold_
    
    Returns:
        Tuple of (labels, confidence_scores, is_novel)
        - labels: int array, always >= 0 (never -1)
        - confidence_scores: float array 0-1, lower = less confident
        - is_novel: bool array, True = sparse/novel region (candidate for new regime)
    """
    from sklearn.metrics import pairwise_distances
    
    unknown_cfg = _cfg_get(cfg, "regimes.unknown", {}) or {}
    distance_percentile = float(unknown_cfg.get("distance_percentile", 95.0))
    
    # Align features
    aligned = basis_df.reindex(columns=model.feature_columns, fill_value=0.0)
    aligned_arr = aligned.to_numpy(dtype=np.float64, copy=False, na_value=0.0)
    X_scaled = model.scaler.transform(aligned_arr)
    X_scaled = np.asarray(X_scaled, dtype=np.float64, order="C")
    centers = model.cluster_centers_
    n_samples = len(X_scaled)
    
    # Initialize outputs
    is_novel = np.zeros(n_samples, dtype=bool)
    
    # v11.1.6 FIX #3: Get calibrated threshold from model (set during training)
    distance_threshold = model.training_distance_threshold_
    if distance_threshold is None or not np.isfinite(distance_threshold):
        distance_threshold = float("inf")
    
    if model.is_hdbscan:
        # HDBSCAN: Use approximate_predict for probabilistic confidence
        try:
            labels, strengths = hdbscan.approximate_predict(model.clustering_model, X_scaled)
            labels = labels.astype(int, copy=True)
            
            # v11.1.6 FIX #4: Apply label mapping if available
            labels = model.apply_label_map(labels)
            
            # Confidence = prediction strength (0-1)
            confidence = np.clip(strengths, 0.0, 1.0)
            
            # v11.3.1: Identify novel points (low strength = sparse region)
            strength_threshold = float(unknown_cfg.get("hdbscan_strength_min", 0.1))
            low_strength_mask = strengths < strength_threshold
            
            # Also check distance threshold for novelty
            if centers.size > 0 and distance_threshold < float("inf"):
                # Compute distances to assigned centroids
                # Handle invalid labels by clamping to valid range
                valid_labels = np.clip(labels, 0, len(centers) - 1)
                point_distances = np.linalg.norm(X_scaled - centers[valid_labels], axis=1)
                distance_novel_mask = point_distances > distance_threshold
                is_novel = low_strength_mask | distance_novel_mask
            else:
                is_novel = low_strength_mask.copy()
            
            # v11.3.1: Always assign - use GMM or nearest centroid for novel points
            if np.any(is_novel):
                if model.fallback_model_ is not None:
                    # Use GMM for better assignment
                    gmm_labels = model.fallback_model_.predict(X_scaled[is_novel])
                    gmm_proba = model.fallback_model_.predict_proba(X_scaled[is_novel])
                    gmm_confidence = np.max(gmm_proba, axis=1)
                    
                    labels[is_novel] = gmm_labels
                    # Discount confidence for novel points (they're in sparse regions)
                    confidence[is_novel] = gmm_confidence * 0.5
                elif model.exemplars_ is not None and len(model.exemplars_) > 0:
                    # Assign to nearest centroid
                    centroid_labels = pairwise_distances_argmin(
                        X_scaled[is_novel], model.exemplars_, axis=1
                    )
                    labels[is_novel] = centroid_labels
                    # Low confidence for centroid fallback
                    confidence[is_novel] = 0.3
                
                n_novel = int(np.sum(is_novel))
                Console.info(
                    f"Identified {n_novel}/{n_samples} novel points (assigned to nearest cluster)",
                    component="REGIME"
                )
            
            return labels, confidence, is_novel
            
        except Exception as e:
            Console.warn(f"HDBSCAN confidence prediction failed: {e}", component="REGIME")
            # Fallback to centroid distance method OR GMM if available
            if model.fallback_model_ is not None:
                labels = model.fallback_model_.predict(X_scaled).astype(int, copy=False)
                proba = model.fallback_model_.predict_proba(X_scaled)
                confidence = np.max(proba, axis=1) * 0.8
                return labels, confidence, is_novel
            elif model.exemplars_ is not None and len(model.exemplars_) > 0:
                labels = pairwise_distances_argmin(X_scaled, model.exemplars_, axis=1).astype(int, copy=False)
                labels = model.apply_label_map(labels)
                distances = np.linalg.norm(X_scaled - model.exemplars_[labels], axis=1)
                
                if distance_threshold < float("inf"):
                    confidence = np.clip(1.0 - (distances / max(distance_threshold * 2, 1e-6)), 0.0, 1.0)
                    is_novel = distances > distance_threshold
                else:
                    threshold = np.percentile(distances, 95) if len(distances) > 0 else 1.0
                    confidence = np.clip(1.0 - (distances / max(threshold, 1e-6)), 0.0, 1.0)
                return labels, confidence, is_novel
            else:
                # v11.3.1: Last resort - assign all to cluster 0
                Console.warn("No clustering method available, assigning all to regime 0", component="REGIME")
                return np.zeros(n_samples, dtype=int), np.full(n_samples, 0.1), np.ones(n_samples, dtype=bool)
    else:
        # GMM: Use predict_proba for probabilistic confidence
        labels = model.clustering_model.predict(X_scaled).astype(int, copy=False)
        labels = model.apply_label_map(labels)
        proba = model.clustering_model.predict_proba(X_scaled)
        confidence = proba.max(axis=1)
        
        # v11.3.1: Identify novel points based on distance threshold
        if centers.size > 0:
            valid_labels = np.clip(labels, 0, len(centers) - 1)
            point_distances = np.linalg.norm(X_scaled - centers[valid_labels], axis=1)
            
            if distance_threshold < float("inf"):
                is_novel = point_distances > distance_threshold
            else:
                # Fallback: low probability indicates novel
                prob_threshold = 1.0 / max(model.n_clusters, 1)
                is_novel = confidence < prob_threshold * 1.5
            
            # Discount confidence for novel points
            confidence[is_novel] = confidence[is_novel] * 0.5
            
            if np.any(is_novel):
                Console.info(
                    f"Identified {np.sum(is_novel)}/{n_samples} novel points",
                    component="REGIME"
                )
    
    return labels, confidence, is_novel


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
    if transition_keys:
        counts = Counter(transition_keys)
        model.meta["transition_counts"] = {k: int(v) for k, v in counts.items()}
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

# Timestamp parsing (fast, consistent, UTC)
def _to_datetime_mixed(s):
    try:
        return pd.to_datetime(s, format="mixed", errors="coerce")
    except TypeError:
        return pd.to_datetime(s, errors="coerce")

def _read_episodes_csv(p: Path, sql_client=None, equip_id: Optional[int] = None, run_id: Optional[str] = None) -> pd.DataFrame:
    """
    Read episodes from SQL (preferred) or CSV fallback.
    
    REG-CSV-01: SQL-backed episode reader for regime analysis.
    Queries ACM_Episodes by EquipID and RunID when sql_client provided.
    Falls back to CSV for file-mode/dev.
    
    Args:
        p: Path to episodes.csv (used only if SQL unavailable)
        sql_client: SQL client for querying ACM_Episodes (optional)
        equip_id: Equipment ID for SQL query (optional)
        run_id: Run ID for SQL query (optional)
        
    Returns:
        DataFrame with columns: start_ts, end_ts (and other episode fields from SQL)
    """
    # REG-CSV-01: Try SQL first if client provided
    if sql_client is not None and equip_id is not None and run_id is not None:
        try:
            query = """
                SELECT StartTs, EndTs, DurationSeconds, DurationHours, 
                       PeakFusedZ, AvgFusedZ, MinHealthIndex, PeakTimestamp,
                       MaxRegimeLabel, Culprits, AlertMode, Severity, Status
                FROM dbo.ACM_Episodes
                WHERE EquipID = ? AND RunID = ?
                ORDER BY StartTs ASC
            """
            cursor = sql_client.cursor()
            cursor.execute(query, (int(equip_id), run_id))
            rows = cursor.fetchall()
            cursor.close()
            
            if rows:
                # Build DataFrame from SQL results
                df = pd.DataFrame([{
                    'start_ts': _to_datetime_mixed(row[0]),
                    'end_ts': _to_datetime_mixed(row[1]),
                    'duration_s': row[2],
                    'duration_hours': row[3],
                    'peak_fused_z': row[4],
                    'avg_fused_z': row[5],
                    'min_health_index': row[6],
                    'peak_timestamp': _to_datetime_mixed(row[7]),
                    'regime': row[8],  # MaxRegimeLabel
                    'culprits': row[9],
                    'alert_mode': row[10],
                    'severity': row[11],
                    'status': row[12]
                } for row in rows])
                return df
            else:
                # No episodes found in SQL, return empty with correct schema
                return pd.DataFrame(columns=["start_ts", "end_ts"])
        except Exception as e:
            # SQL query failed, fall back to CSV
            from core.observability import Console
            Console.warn(f"SQL episode read failed, falling back to CSV: {e}", component="REGIME", equip_id=equip_id, run_id=run_id, error_type=type(e).__name__)
    
    # REG-CSV-01: Fallback to CSV for file-mode/dev or if SQL unavailable
    safe_base = Path.cwd()
    try:
        resolved = p.resolve()
        if not resolved.is_relative_to(safe_base):
            from core.observability import Console
            Console.warn(f"Episode path outside workspace: {resolved}", component="REGIME", resolved_path=str(resolved), safe_base=str(safe_base))
            return pd.DataFrame(columns=["start_ts", "end_ts"])
    except Exception:
        pass
    if not p.exists():
        return pd.DataFrame(columns=["start_ts", "end_ts"])
    df = pd.read_csv(p, dtype={"start_ts": "string", "end_ts": "string"})
    df["start_ts"] = _to_datetime_mixed(df["start_ts"])
    df["end_ts"]   = _to_datetime_mixed(df["end_ts"])
    
    # FIX #9: Filter invalid timestamps immediately after parsing
    initial_count = len(df)
    
    # Remove rows with NaT timestamps
    valid_mask = df["start_ts"].notna() & df["end_ts"].notna()
    nat_count = (~valid_mask).sum()
    if nat_count > 0:
        Console.warn(f"Filtering {nat_count} episodes with invalid timestamps (NaT)", component="REGIME", nat_count=nat_count, initial_count=initial_count)
        df = df[valid_mask]
    
    # FIX #9: Validate end_ts > start_ts
    if len(df) > 0:
        invalid_range_mask = df["end_ts"] < df["start_ts"]
        invalid_range_count = invalid_range_mask.sum()
        if invalid_range_count > 0:
            Console.warn(
                f"Filtering {invalid_range_count} episodes where end_ts < start_ts (invalid time range)",
                component="REGIME", invalid_count=invalid_range_count, valid_count=len(df) - invalid_range_count
            )
            df = df[~invalid_range_mask]
    
    final_count = len(df)
    if final_count < initial_count:
        Console.info(f"Episodes after validation: {final_count}/{initial_count}", component="REGIME")
    
    return df

def _read_scores_csv(p: Path, sql_client=None, equip_id: Optional[int] = None, run_id: Optional[str] = None, 
                    start_ts: Optional[pd.Timestamp] = None, end_ts: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """
    Read scores from SQL (preferred) or CSV fallback.
    
    REG-CSV-01: SQL-backed scores reader for regime analysis.
    Queries ACM_Scores_Wide by EquipID, RunID, and optional time range when sql_client provided.
    Falls back to CSV for file-mode/dev.
    
    Args:
        p: Path to scores.csv (used only if SQL unavailable)
        sql_client: SQL client for querying ACM_Scores_Wide (optional)
        equip_id: Equipment ID for SQL query (optional)
        run_id: Run ID for SQL query (optional)
        start_ts: Start timestamp for SQL query (optional, filters >= start_ts)
        end_ts: End timestamp for SQL query (optional, filters <= end_ts)
        
    Returns:
        DataFrame with timestamp index and score columns
    """
    # REG-CSV-01: Try SQL first if client provided
    if sql_client is not None and equip_id is not None and run_id is not None:
        try:
            # Build query with optional time range filtering
            query_parts = [
                "SELECT * FROM dbo.ACM_Scores_Wide",
                "WHERE EquipID = ? AND RunID = ?"
            ]
            params = [int(equip_id), run_id]
            
            if start_ts is not None:
                query_parts.append("AND Timestamp >= ?")
                params.append(start_ts)
            if end_ts is not None:
                query_parts.append("AND Timestamp <= ?")
                params.append(end_ts)
            
            query_parts.append("ORDER BY Timestamp ASC")
            query = " ".join(query_parts)
            
            cursor = sql_client.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            cursor.close()
            
            if rows:
                # Build DataFrame from SQL results
                df = pd.DataFrame(rows, columns=cols)
                
                # Set timestamp as index
                if 'Timestamp' in df.columns:
                    df['Timestamp'] = _to_datetime_mixed(df['Timestamp'])
                    df = df.set_index('Timestamp')
                    
                    # Drop RunID, EquipID columns (not needed for analysis)
                    df = df.drop(columns=['RunID', 'EquipID'], errors='ignore')
                    
                    # Clean NaN timestamps
                    df_clean = df[~df.index.isna()]
                    dropped = len(df) - len(df_clean)
                    if dropped > 0:
                        Console.warn(f"Dropped {dropped} rows with invalid timestamps from SQL scores", component="REGIME", dropped_rows=dropped, total_rows=len(df), equip_id=equip_id, run_id=run_id)
                    return df_clean
                else:
                    Console.warn("SQL scores missing Timestamp column", component="REGIME", equip_id=equip_id, run_id=run_id, columns=cols[:5])
                    return pd.DataFrame()
            else:
                # No scores found in SQL, return empty
                return pd.DataFrame()
        except Exception as e:
            # SQL query failed, fall back to CSV
            Console.warn(f"SQL scores read failed, falling back to CSV: {e}", component="REGIME", equip_id=equip_id, run_id=run_id, error_type=type(e).__name__)
    
    # REG-CSV-01: Fallback to CSV for file-mode/dev or if SQL unavailable
    safe_base = Path.cwd()
    try:
        resolved = p.resolve()
        if not resolved.is_relative_to(safe_base):
            Console.warn(f"Scores path outside workspace: {resolved}", component="REGIME", resolved_path=str(resolved), safe_base=str(safe_base))
            return pd.DataFrame()
    except Exception:
        pass
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, dtype={"timestamp": "string"})
    df["timestamp"] = _to_datetime_mixed(df["timestamp"])
    df = df.set_index("timestamp")
    df_clean = df[~df.index.isna()]
    dropped = len(df) - len(df_clean)
    if dropped > 0:
        Console.warn(f"Dropped {dropped} rows with invalid timestamps from scores.csv", component="REGIME", dropped_rows=dropped, total_rows=len(df), file_path=str(p))
    return df_clean

# -----------------------------------
# Core: fit auto-k with safe heuristics (v11.1.0: Uses GMM, not K-Means)
# DEPRECATED: Legacy path - use fit_regime_model() instead
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
    scaler = StandardScaler()
    scaler.mean_, scaler.scale_ = state.get_scaler_params()
    scaler.n_features_in_ = len(scaler.mean_)
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
    
    return model


def align_regime_labels(
    new_model: RegimeModel,
    prev_model: RegimeModel
) -> RegimeModel:
    """
    Align new regime cluster labels to match previous regime labels for continuity.
    
    v11.1.6 FIX #4: Now creates and stores a label_map_ that is applied to all
    predicted labels via apply_label_map(). This ensures stable label semantics
    across refits.
    
    Uses nearest cluster center matching to ensure consistent regime IDs when
    operating conditions recur across batches.
    
    Args:
        new_model: Newly fitted RegimeModel
        prev_model: Previously fitted RegimeModel for reference
    
    Returns:
        RegimeModel with label_map_ set for stable predictions
    """
    if prev_model is None or new_model is None:
        return new_model
    
    # Extract cluster centers (v11.1.0: Property works for HDBSCAN and GMM)
    new_centers = new_model.cluster_centers_
    prev_centers = prev_model.cluster_centers_

    # Handle dimension mismatch (different k or feature space)
    if new_centers.shape[1] != prev_centers.shape[1]:
        # v11.3.x: Fail fast instead of silent skip
        # Regime model must be retrained when feature basis changes
        error_msg = (
            f"Cannot align regimes: feature dimension mismatch "
            f"(new={new_centers.shape[1]}, prev={prev_centers.shape[1]}). "
            f"Feature basis has changed - regime model must be retrained from scratch. "
            f"This typically happens when: "
            f"(1) Number of PCA components changed, "
            f"(2) Raw sensor tags added/removed, "
            f"(3) Feature engineering logic modified. "
            f"Set 'regimes.alignment.fail_on_mismatch=False' to allow silent skip (not recommended)."
        )
        
        alignment_cfg = _cfg_get(cfg or {}, "regimes.alignment", {}) or {}
        fail_on_mismatch = bool(alignment_cfg.get("fail_on_mismatch", True))  # Default: True (fail fast)
        
        if fail_on_mismatch:
            raise ValueError(error_msg)
        else:
            # Legacy behavior: warn and skip alignment
            Console.warn(error_msg, component="REGIME_ALIGN")
            new_model.meta["alignment_skip_reason"] = "feature_dim_mismatch"
            new_model.meta["alignment_skip_dims"] = {
                "new_dim": int(new_centers.shape[1]),
                "prev_dim": int(prev_centers.shape[1]),
            }
            return new_model
    
    # Use Hungarian algorithm for optimal 1:1 assignment
    from scipy.optimize import linear_sum_assignment
    from scipy.spatial.distance import cdist
    
    cost_matrix = cdist(new_centers, prev_centers, metric='euclidean')
    new_k = new_centers.shape[0]
    prev_k = prev_centers.shape[0]
    
    # v11.1.6 FIX #4: Create explicit label_map: raw_label -> stable_label
    # This map is applied in apply_label_map() to all predictions
    label_map: Dict[int, int] = {}
    
    if new_k == prev_k:
        # Same cluster count: 1:1 optimal assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        # row_ind[i] = new cluster index, col_ind[i] = prev cluster index it maps to
        for new_idx, prev_idx in zip(row_ind, col_ind):
            label_map[int(new_idx)] = int(prev_idx)
        
        # Also reorder centroids for centroid-based fallback prediction
        reorder_idx = np.argsort(col_ind)  # Sort by target position
        reordered_centers = new_centers[row_ind[reorder_idx]]
        new_model.set_cluster_centers_(reordered_centers)
        
    elif new_k < prev_k:
        # Fewer new clusters: each maps to closest previous
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        for new_idx, prev_idx in zip(row_ind, col_ind):
            label_map[int(new_idx)] = int(prev_idx)
        
        # Reorder centroids
        reordered = np.zeros_like(new_centers)
        used_positions = set()
        for new_idx in range(new_k):
            prev_idx = label_map.get(new_idx, new_idx)
            if prev_idx < new_k:
                reordered[prev_idx] = new_centers[new_idx]
                used_positions.add(prev_idx)
        # Fill gaps
        free_positions = [i for i in range(new_k) if i not in used_positions]
        unmapped = [i for i in range(new_k) if label_map.get(i, -1) >= new_k]
        for pos, new_idx in zip(free_positions, unmapped):
            reordered[pos] = new_centers[new_idx]
        new_model.set_cluster_centers_(reordered)
        
    else:
        # More new clusters: map previous to closest new, extras get new indices
        row_ind, col_ind = linear_sum_assignment(cost_matrix.T)
        # col_ind[prev_idx] = new_idx that maps to it
        for prev_idx, new_idx in zip(row_ind, col_ind):
            label_map[int(new_idx)] = int(prev_idx)
        
        # Assign new indices to unmatched new clusters
        used_prev = set(label_map.values())
        next_label = max(used_prev) + 1 if used_prev else prev_k
        for new_idx in range(new_k):
            if new_idx not in label_map:
                label_map[new_idx] = next_label
                next_label += 1
        
        # Reorder centroids for matched clusters
        reordered = np.zeros_like(new_centers)
        for new_idx in range(new_k):
            target_pos = label_map.get(new_idx, new_idx)
            if target_pos < new_k:
                reordered[target_pos] = new_centers[new_idx]
        new_model.set_cluster_centers_(reordered)
    
    # v11.1.6 FIX #4: Store the label map in the model
    new_model.label_map_ = label_map
    new_model.meta["label_map"] = {str(k): v for k, v in label_map.items()}
    new_model.meta["alignment_applied"] = True
    
    Console.info(
        f"Aligned {new_k} clusters to {prev_k} previous clusters. "
        f"Label map: {dict(list(label_map.items())[:5])}{'...' if len(label_map) > 5 else ''}",
        component="REGIME_ALIGN"
    )
    
    return new_model


# ------------------------------------------------
# Public API: label(score_df, ctx, score_out, cfg)
# ------------------------------------------------
def label(score_df, ctx: Dict[str, Any], score_out: Dict[str, Any], cfg: Dict[str, Any]):
    basis_train: Optional[pd.DataFrame] = ctx.get("regime_basis_train")
    basis_score: Optional[pd.DataFrame] = ctx.get("regime_basis_score")
    basis_meta: Dict[str, Any] = ctx.get("basis_meta") or {}
    regime_model: Optional[RegimeModel] = ctx.get("regime_model")
    basis_hash: Optional[int] = ctx.get("regime_basis_hash")  # v11.1.1: Now SCHEMA hash, not data hash
    allow_discovery: bool = ctx.get("allow_discovery", True)  # V11: ONLINE mode sets False

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
        
        # V11 ONLINE mode gate: fail fast if model missing and discovery not allowed
        if needs_fit and not allow_discovery:
            raise RuntimeError(
                "[ONLINE MODE] Regime model not found or invalidated. "
                "ONLINE mode requires pre-trained regime model. Run in OFFLINE mode first to discover regimes."
            )
        
        if needs_fit:
            regime_model = fit_regime_model(basis_train, basis_meta, cfg, basis_hash)
        elif regime_model.train_hash is None and basis_hash is not None:
            regime_model.train_hash = basis_hash

        # V11: Use confidence-aware prediction for score data
        # Training data uses standard prediction (no novel detection during training)
        train_labels = predict_regime(regime_model, basis_train)
        
        # Compute training distances for establishing threshold
        aligned_train = basis_train.reindex(columns=regime_model.feature_columns, fill_value=0.0)
        train_arr = aligned_train.to_numpy(dtype=np.float64, copy=False, na_value=0.0)
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
        
        # v11.3.x: Enforce minimum confidence threshold for regime assignments
        # Low-confidence assignments are marked as UNKNOWN (-1) to reflect uncertainty
        confidence_cfg = _cfg_get(cfg, "regimes.confidence", {}) or {}
        min_confidence_threshold = float(confidence_cfg.get("min_threshold", 0.0))  # Default: 0.0 (disabled)
        enforce_threshold = bool(confidence_cfg.get("enforce_threshold", False))  # Default: False (disabled)
        
        if enforce_threshold and min_confidence_threshold > 0.0:
            low_confidence_mask = score_confidence < min_confidence_threshold
            n_low_conf = int(np.sum(low_confidence_mask))
            
            if n_low_conf > 0:
                # Mark low-confidence assignments as UNKNOWN
                score_labels[low_confidence_mask] = UNKNOWN_REGIME_LABEL  # -1
                Console.info(
                    f"Marked {n_low_conf}/{len(score_labels)} assignments as UNKNOWN "
                    f"due to confidence < {min_confidence_threshold:.2f}",
                    component="REGIME", n_unknown=n_low_conf, threshold=min_confidence_threshold
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
        Console.warn("Falling back to legacy labeling path (allow_legacy_label=True)", component="REGIME", n_samples=len(score_df) if hasattr(score_df, '__len__') else 0)
        return _legacy_label(score_df, ctx, out, cfg)
    raise RuntimeError("Regime model unavailable and legacy path disabled (regimes.allow_legacy_label=False)")


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
    
    # REG-CSV-01: Extract SQL parameters from ctx if available
    sql_client = getattr(ctx, "sql_client", None)
    run_id = getattr(ctx, "run_id", None)
    equip_id = getattr(ctx, "equip_id", None)
    
    # REG-CSV-01: Try SQL first, fall back to CSV
    eps = _read_episodes_csv(ep_path, sql_client=sql_client, equip_id=equip_id, run_id=run_id)
    
    if eps.empty and not ep_path.exists():
        return {"module":"regime","tables":[], "plots":[], "metrics":{},
                "error":{"type":"MissingFile","message":"episodes not found in SQL or CSV"}}
    tables: List[Dict[str, Any]] = []

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
            Console.warn(f"Failed to load regime model for reporting: {load_exc}", component="REGIME", models_dir=str(models_dir), error_type=type(load_exc).__name__)

    if regime_model is not None:
        summary_df = build_summary_dataframe(regime_model)
        if not summary_df.empty:
            # Write to ACM_RegimeStats SQL table (SQL-only mode)
            if OutputManager is not None:
                om = OutputManager(sql_client=sql_client, run_id=run_id, equip_id=equip_id, base_output_dir=getattr(ctx, "run_dir", None))
                # Convert dwell_fraction to OccupancyPct (percentage) and prepare correct columns
                if 'dwell_fraction' in summary_df.columns:
                    summary_df['OccupancyPct'] = summary_df['dwell_fraction'] * 100.0
                if 'median_fused' in summary_df.columns:
                    summary_df['FusedMean'] = summary_df['median_fused']
                if 'p95_abs_fused' in summary_df.columns:
                    summary_df['FusedP90'] = summary_df['p95_abs_fused']  # Use p95 for p90 column
                sql_cols = {
                    "regime": "RegimeLabel",
                    "avg_dwell_seconds": "AvgDwellSeconds",
                    "OccupancyPct": "OccupancyPct",
                    "FusedMean": "FusedMean",
                    "FusedP90": "FusedP90"
                }
                om.write_dataframe(summary_df, "regime_summary", sql_table="ACM_RegimeStats", sql_columns=sql_cols)

        feature_map = regime_model.meta.get("feature_importance") or {}
        if feature_map:
            feature_importance_df = (
                pd.DataFrame(
                    [{"feature": str(k), "importance": float(v)} for k, v in feature_map.items()]
                )
                .sort_values("importance", ascending=False)
                .reset_index(drop=True)
            )
            # Write to ACM_RegimeOccupancy SQL table (SQL-only mode)
            if OutputManager is not None:
                om = OutputManager(sql_client=sql_client, run_id=run_id, equip_id=equip_id, base_output_dir=getattr(ctx, "run_dir", None))
                sql_cols = {"feature": "Feature", "importance": "Importance"}
                om.write_dataframe(feature_importance_df, "regime_feature_importance", sql_table="ACM_RegimeOccupancy", sql_columns=sql_cols)

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
            # Write to ACM_RegimeTransitions SQL table (SQL-only mode)
            if OutputManager is not None:
                om = OutputManager(sql_client=sql_client, run_id=run_id, equip_id=equip_id, base_output_dir=getattr(ctx, "run_dir", None))
                sql_cols = {"from_regime": "FromRegime", "to_regime": "ToRegime", "count": "Count"}
                om.write_dataframe(transitions_df, "regime_transitions", sql_table="ACM_RegimeTransitions", sql_columns=sql_cols)

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
    # REG-CSV-03: Skip plotting in SQL-only production mode (for dev/debug only)
    # Plotting now uses SQL-backed _read_scores_csv (from REG-CSV-01)
    plots_dir = getattr(ctx, "plots_dir", None)
    if plots_dir is not None:
        # REG-CSV-01: Try SQL scores first, fall back to CSV, allow plotting if data available
        sc = _read_scores_csv(sc_path, sql_client=sql_client, equip_id=equip_id, run_id=run_id)
        if not sc.empty:
            if "fused" in sc.columns and len(sc) > 0 and len(eps) > 0:
                fig = plt.figure(figsize=(12,4)); ax = plt.gca()
                sc["fused"].plot(ax=ax, linewidth=1)
                for _, r in eps.iterrows():
                    if pd.notna(r["start_ts"]) and pd.notna(r["end_ts"]):
                        ax.axvspan(r["start_ts"], r["end_ts"], alpha=0.15, color="red")
                ax.set_title("Fused score with episode windows")
                ax.set_xlabel("")
                plt.tight_layout()
                p = plots_dir / "regime_overlay.png"
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
    - regime_model.joblib: HDBSCAN/GMM clustering model and StandardScaler
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
            'clustering_model': model.clustering_model,
            'exemplars_': model.exemplars_,  # v11.1.0: Needed for HDBSCAN prediction
            'train_hash': model.train_hash,
        }, joblib_path)
        model_type = "HDBSCAN" if model.is_hdbscan else "GMM"
        Console.info(f"Saved regime models ({model_type}+Scaler) -> {joblib_path}", component="REGIME")
    except Exception as e:
        Console.warn(f"Failed to save regime joblib: {e}", component="REGIME", models_dir=str(models_dir), error_type=type(e).__name__)
        _persist_regime_error(e, models_dir)
        raise
    
    # Save metadata as JSON
    json_path = models_dir / "regime_model.json"
    model.meta.setdefault("model_version", REGIME_MODEL_VERSION)
    model.meta.setdefault("sklearn_version", sklearn.__version__)

    metadata = _regime_metadata_dict(model)
    try:
        if orjson:
            json_path.write_bytes(orjson.dumps(metadata, option=orjson.OPT_INDENT_2))
        else:
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        Console.info(f"Saved regime metadata -> {json_path}", component="REGIME")
    except Exception as e:
        Console.warn(f"Failed to save regime metadata: {e}", component="REGIME", models_dir=str(models_dir), json_path=str(json_path), error_type=type(e).__name__)
        _persist_regime_error(e, models_dir)
        raise


def load_regime_model(models_dir: Path) -> Optional[RegimeModel]:
    """
    Load regime model from disk.
    
    Loads:
    - regime_model.joblib: HDBSCAN/GMM clustering model and StandardScaler
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
        Console.info(f"No cached regime model found at {joblib_path}", component="REGIME")
        return None
    
    if not json_path.exists():
        Console.warn(f"Regime joblib exists but metadata missing: {json_path}", component="REGIME", joblib_path=str(joblib_path), json_path=str(json_path))
        return None
    
    try:
        # Load sklearn objects
        joblib_data = joblib.load(joblib_path)
        scaler = joblib_data['scaler']
        clustering_model = joblib_data['clustering_model']
        exemplars = joblib_data.get('exemplars_')
        train_hash = joblib_data.get('train_hash')
        
        # Load metadata
        with json_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Reconstruct RegimeModel
        meta = metadata.get("meta", {})
        version = meta.get("model_version")
        
        # FIX #10: Use semantic versioning compatibility check
        if version and not _is_version_compatible(version, REGIME_MODEL_VERSION):
            raise ModelVersionMismatch(
                f"Cached model version {version} incompatible with expected {REGIME_MODEL_VERSION} "
                f"(major version mismatch)"
            )
        elif version and version != REGIME_MODEL_VERSION:
            Console.info(
                f"Cached model version {version} compatible with {REGIME_MODEL_VERSION} (same major)",
                component="REGIME"
            )
            
        model = RegimeModel(
            scaler=scaler,
            clustering_model=clustering_model,
            feature_columns=metadata.get("feature_columns", []),
            raw_tags=metadata.get("raw_tags", []),
            n_pca_components=metadata.get("n_pca_components", 0),
            train_hash=train_hash,
            health_labels={int(k): v for k, v in metadata.get("health_labels", {}).items()},
            stats={int(k): v for k, v in metadata.get("stats", {}).items()},
            meta=meta,
            exemplars_=exemplars,  # v11.1.0: HDBSCAN centroids
        )
        
        Console.info(f"Loaded cached regime model from {joblib_path}", component="REGIME")
        cluster_count = model.n_clusters  # Use property
        model_type = "HDBSCAN" if model.is_hdbscan else "GMM"
        Console.info(
            f"  - K={cluster_count}, type={model_type}, features={len(model.feature_columns)}, train_hash={train_hash}",
            component="REGIME"
        )
        return model
        
    except Exception as e:
        Console.warn(f"Failed to load regime model: {e}", component="REGIME", models_dir=str(models_dir), error_type=type(e).__name__)
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
        Console.info("Detection disabled in config", component="TRANSIENT")
        return default_states

    if n_samples == 0:
        return default_states

    roc_window = int(transient_cfg.get("roc_window", 5))
    roc_threshold_high = float(transient_cfg.get("roc_threshold_high", 3.0))
    roc_threshold_trip = float(transient_cfg.get("roc_threshold_trip", 5.0))
    transition_lag = int(transient_cfg.get("transition_lag", 3))
    clip_pct = float(transient_cfg.get("clip_percentile", 99.0))
    sensor_weights_cfg = transient_cfg.get("sensor_weights", {}) or {}

    # FIX #5: Transient detection should ONLY use operating variables
    # Condition indicators (bearing temps, vibration, winding temps) measure HEALTH,
    # not operating state transitions. Using them would conflate fault signatures
    # with normal startup/shutdown dynamics.
    all_numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
    
    # Filter to operating variables only using tag taxonomy
    numeric_cols = [
        col for col in all_numeric_cols
        if _classify_tag(col) == "operating"
    ]
    
    if not numeric_cols:
        # Fallback: if no operating variables found, use all numeric but warn
        Console.warn(
            "No operating-variable columns identified for transient detection; "
            "falling back to all numeric columns. Consider adding operating keywords "
            "(speed, rpm, load, flow, pressure, power) to sensor names.",
            component="TRANSIENT",
            all_numeric=len(all_numeric_cols)
        )
        numeric_cols = all_numeric_cols
    else:
        excluded_count = len(all_numeric_cols) - len(numeric_cols)
        if excluded_count > 0:
            Console.info(
                f"Using {len(numeric_cols)} operating-variable columns for transient detection; "
                f"excluded {excluded_count} condition-indicator columns",
                component="TRANSIENT"
            )
    
    if not numeric_cols:
        Console.warn("No numeric columns for ROC calculation", component="TRANSIENT", n_columns=len(data.columns) if hasattr(data, 'columns') else 0, n_samples=n_samples)
        return default_states

    # FIX #8: Validate sensor_weights_cfg keys match available columns
    # and document why absolute values are used
    configured_weights = list(sensor_weights_cfg.keys())
    if configured_weights:
        matched_cols = [col for col in configured_weights if col in numeric_cols]
        unmatched_cols = [col for col in configured_weights if col not in numeric_cols]
        if unmatched_cols:
            Console.warn(
                f"[TRANSIENT] {len(unmatched_cols)} configured weight keys not in data columns: "
                f"{unmatched_cols[:3]}{'...' if len(unmatched_cols) > 3 else ''}",
                component="TRANSIENT", unmatched_count=len(unmatched_cols), matched_count=len(matched_cols)
            )
        if matched_cols:
            Console.info(f"Using custom weights for {len(matched_cols)} sensors", component="TRANSIENT")
    
    # FIX #8: Document why abs() is used and preserve relative importance
    # Absolute value is used because weights should be non-negative for ROC aggregation
    # (negative ROC contribution would incorrectly reduce transient signal)
    # Normalization happens AFTER abs() to maintain relative importance ratios
    raw_weights = np.array([float(sensor_weights_cfg.get(col, 1.0)) for col in numeric_cols], dtype=float)
    if np.any(raw_weights < 0):
        Console.info("Negative weights found; using absolute values for ROC aggregation", component="TRANSIENT")
    weights = np.abs(raw_weights)
    
    if not np.isfinite(weights).all() or weights.sum() <= 0:
        weights = np.ones(len(numeric_cols), dtype=float)
        Console.warn("Invalid weights detected; falling back to uniform weights", component="TRANSIENT", n_sensors=len(numeric_cols))
    weights /= weights.sum()

    data_numeric = data[numeric_cols].apply(pd.to_numeric, errors="coerce").ffill().bfill()

    # PERF-OPT: Vectorized ROC calculation instead of column-by-column loop
    # Compute diff and baseline for all columns at once using numpy
    data_values = data_numeric.values  # (n_samples, n_cols)
    
    # Vectorized diff: shifted values subtracted from current
    diff_abs = np.abs(np.diff(data_values, axis=0, prepend=data_values[:1]))
    
    # Baseline: shifted absolute values with floor
    baseline = np.abs(np.roll(data_values, 1, axis=0))
    baseline[0] = baseline[1] if len(baseline) > 1 else 1e-9
    baseline = np.clip(baseline, 1e-9, None)
    
    # ROC: rate of change
    roc_matrix = diff_abs / baseline
    roc_matrix = np.where(np.isfinite(roc_matrix), roc_matrix, np.nan)
    
    # Clip to percentile if needed
    if clip_pct < 100.0:
        try:
            upper = np.nanpercentile(roc_matrix, clip_pct)
            roc_matrix = np.clip(roc_matrix, None, upper)
        except Exception:
            pass
    
    # Apply weights and sum across columns
    weighted_roc = np.nansum(roc_matrix * weights[np.newaxis, :], axis=1)
    
    # Fill NaN and smooth
    aggregate_roc = pd.Series(weighted_roc).ffill().bfill().fillna(0.0)
    aggregate_roc_smooth = aggregate_roc.rolling(window=max(2, roc_window), min_periods=1).mean()

    regime_changes = np.zeros(n_samples, dtype=bool)
    if len(regime_labels) == n_samples:
        diffs = np.diff(regime_labels.astype(int), prepend=regime_labels[0])
        regime_changes = diffs != 0

    roc_values = aggregate_roc_smooth.to_numpy(dtype=float)
    trend_window = max(roc_window, 5)
    trend = pd.Series(roc_values).diff().rolling(window=trend_window, min_periods=1).mean().to_numpy()

    trip_mask = roc_values >= roc_threshold_trip
    high_mask = (roc_values >= roc_threshold_high) & ~trip_mask

    def _dilate(mask: np.ndarray, width: int) -> np.ndarray:
        if width <= 0:
            return mask
        kernel = np.ones(2 * width + 1, dtype=int)
        return np.convolve(mask.astype(int), kernel, mode="same") > 0

    base_transient = regime_changes | high_mask | trip_mask
    transient_mask = _dilate(base_transient, transition_lag)
    trip_mask = _dilate(trip_mask, transition_lag)
    high_mask = _dilate(high_mask, transition_lag)

    states = np.full(n_samples, "steady", dtype=object)
    states[transient_mask] = "transient"
    startup_mask = high_mask & (trend >= 0)
    shutdown_mask = high_mask & ~startup_mask
    states[startup_mask] = "startup"
    states[shutdown_mask] = "shutdown"
    states[trip_mask] = "trip"

    state_counts = pd.Series(states).value_counts().to_dict()
    Console.info(f"State distribution: {state_counts}", component="TRANSIENT")

    return states




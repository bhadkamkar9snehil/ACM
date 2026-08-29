# HDBSCAN Implementation Guide for ACM Regime Detection

**Created:** 2025-12-20  
**Status:** Implementation Blueprint  
**Estimated Effort:** 2-3 days

---

## Overview

This document provides a concrete implementation plan for integrating HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise) as an alternative clustering method for ACM's regime detection system.

**Goal:** Enable HDBSCAN as a drop-in replacement for MiniBatchKMeans, selected via configuration parameter `regimes.clustering_method=hdbscan`.

---

## 1. Dependencies

### 1.1 Add to pyproject.toml

```toml
[project]
dependencies = [
  # ... existing dependencies ...
  "hdbscan>=0.8.33",  # Density-based clustering
]
```

### 1.2 Install Command

```bash
cd /home/runner/work/ACM/ACM
pip install hdbscan>=0.8.33
```

---

## 2. Code Changes in core/regimes.py

### 2.1 Add HDBSCAN Import (Line ~18)

```python
# Existing imports
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import silhouette_score, calinski_harabasz_score, pairwise_distances_argmin

# NEW: Add HDBSCAN import
try:
    import hdbscan
    HDBSCAN_AVAILABLE = True
except ImportError:
    HDBSCAN_AVAILABLE = False
    Console.warn("hdbscan package not installed. Install with: pip install hdbscan", component="REGIME")
```

### 2.2 Extend RegimeModel Dataclass (Line ~290)

```python
@dataclass
class RegimeModel:
    scaler: StandardScaler
    kmeans: MiniBatchKMeans  # Will be None for HDBSCAN
    feature_columns: List[str]
    raw_tags: List[str]
    n_pca_components: int
    train_hash: Optional[int] = None
    health_labels: Dict[int, str] = field(default_factory=dict)
    stats: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
    
    # NEW: Add HDBSCAN-specific fields
    hdbscan_clusterer: Optional[Any] = None  # HDBSCAN object
    cluster_centroids: Optional[np.ndarray] = None  # Computed centroids (HDBSCAN has no built-in)
    clustering_method: str = "kmeans"  # Method used: "kmeans" or "hdbscan" or "gmm"
```

### 2.3 Add HDBSCAN Fitting Function (Insert after _fit_kmeans_scaled, Line ~601)

```python
def _fit_hdbscan(
    X: np.ndarray,
    cfg: Dict[str, Any],
    *,
    pre_scaled: bool = False,
) -> Tuple[StandardScaler, Any, int, float, str, List[Tuple[int, float]], bool]:
    """
    Fit HDBSCAN clustering with quality validation.
    
    Returns:
        (scaler, hdbscan_obj, n_clusters, silhouette_score, metric, sweep_scores, low_quality)
    
    HDBSCAN automatically determines number of clusters and marks outliers as label=-1.
    We compute cluster centroids post-hoc for interpretability and prediction.
    """
    if not HDBSCAN_AVAILABLE:
        raise ImportError(
            "HDBSCAN clustering selected but hdbscan package not installed. "
            "Install with: pip install hdbscan"
        )
    
    # Preprocessing (same as k-means)
    X = _finite_impute_inplace(X)
    if pre_scaled:
        scaler = _IdentityScaler()
        X_scaled = scaler.transform(X)
    else:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
    
    n_samples = X_scaled.shape[0]
    if n_samples == 0:
        raise ValueError("Cannot fit regime model on an empty dataset")
    if n_samples < 2:
        raise ValueError(f"Cannot fit regime model with fewer than 2 samples (got {n_samples})")
    
    # HDBSCAN configuration
    min_cluster_size = int(_cfg_get(cfg, "regimes.hdbscan.min_cluster_size", 50))
    min_samples = int(_cfg_get(cfg, "regimes.hdbscan.min_samples", 10))
    cluster_selection_method = _cfg_get(cfg, "regimes.hdbscan.cluster_selection_method", "eom")
    max_noise_ratio = float(_cfg_get(cfg, "regimes.hdbscan.max_noise_ratio", 0.15))
    
    # Ensure min_cluster_size is reasonable for sample size
    if n_samples < min_cluster_size:
        min_cluster_size = max(5, n_samples // 4)
        Console.warn(
            f"[REGIME] Adjusted min_cluster_size to {min_cluster_size} for n={n_samples} samples",
            component="REGIME"
        )
    
    # Fit HDBSCAN
    Console.info(
        f"[REGIME] Fitting HDBSCAN: min_cluster_size={min_cluster_size}, "
        f"min_samples={min_samples}, method={cluster_selection_method}",
        component="REGIME"
    )
    
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric='euclidean',
        cluster_selection_method=cluster_selection_method,
        prediction_data=True,  # Enable approximate_predict for new samples
        core_dist_n_jobs=1  # Use single core (multiprocessing issues in some environments)
    )
    
    clusterer.fit(X_scaled)
    labels = clusterer.labels_
    
    # Analyze results
    unique_labels = set(labels)
    noise_mask = labels == -1
    noise_count = noise_mask.sum()
    noise_ratio = float(noise_count / n_samples) if n_samples > 0 else 0.0
    
    cluster_labels = unique_labels - {-1}  # Exclude noise label
    n_clusters = len(cluster_labels)
    
    Console.info(
        f"[REGIME] HDBSCAN found {n_clusters} clusters + {noise_count} noise samples "
        f"({noise_ratio*100:.1f}% noise)",
        component="REGIME"
    )
    
    # Quality validation
    low_quality = False
    quality_notes: List[str] = []
    
    # Check noise ratio
    if noise_ratio > max_noise_ratio:
        low_quality = True
        quality_notes.append(f"noise_ratio_high_{noise_ratio:.2f}")
        Console.warn(
            f"[REGIME] Noise ratio {noise_ratio*100:.1f}% exceeds threshold "
            f"{max_noise_ratio*100:.1f}%",
            component="REGIME"
        )
    
    # Compute quality metrics
    metric = "silhouette"
    if n_clusters < 2:
        # Degenerate case: only 1 cluster or all noise
        score = -1.0
        low_quality = True
        quality_notes.append("single_cluster_or_all_noise")
        Console.warn(
            "[REGIME] HDBSCAN produced single cluster or all noise. Consider adjusting min_cluster_size.",
            component="REGIME"
        )
    else:
        # Compute silhouette on non-noise samples only
        non_noise_mask = ~noise_mask
        X_non_noise = X_scaled[non_noise_mask]
        labels_non_noise = labels[non_noise_mask]
        
        try:
            sil_sample = min(4000, X_non_noise.shape[0])
            score = silhouette_score(
                X_non_noise,
                labels_non_noise,
                sample_size=sil_sample,
                random_state=17
            )
            metric = "silhouette"
        except Exception as e:
            Console.warn(f"[REGIME] Silhouette calculation failed: {e}. Using Calinski-Harabasz.", component="REGIME")
            score = calinski_harabasz_score(X_non_noise, labels_non_noise)
            metric = "calinski_harabasz"
    
    # Compute cluster centroids (HDBSCAN doesn't provide these by default)
    centroids = []
    for cluster_id in sorted(cluster_labels):
        cluster_mask = labels == cluster_id
        cluster_centroid = X_scaled[cluster_mask].mean(axis=0)
        centroids.append(cluster_centroid)
    
    centroids_array = np.array(centroids) if centroids else np.zeros((0, X_scaled.shape[1]))
    
    # Store centroids in clusterer for prediction (custom attribute)
    clusterer.cluster_centroids_ = centroids_array
    clusterer.n_clusters_ = n_clusters
    
    # Quality sweep (for consistency with k-means API)
    sweep_scores = [(n_clusters, float(score))]
    
    Console.info(
        f"[REGIME] HDBSCAN quality: metric={metric}, score={score:.3f}, "
        f"n_clusters={n_clusters}, noise={noise_ratio*100:.1f}%",
        component="REGIME"
    )
    
    return scaler, clusterer, int(n_clusters), float(score), metric, sweep_scores, low_quality
```

### 2.4 Update fit_regime_model Function (Line ~603)

```python
def fit_regime_model(
    train_basis: pd.DataFrame,
    basis_meta: Dict[str, Any],
    cfg: Dict[str, Any],
    train_hash: Optional[int],
) -> RegimeModel:
    """Fit regime clustering model using configured method (kmeans or hdbscan)."""
    
    input_issues = _validate_regime_inputs(train_basis, "train_basis")
    config_issues = _validate_regime_config(cfg)
    for issue in input_issues:
        Console.warn(f"Input validation: {issue}", component="REGIME")
    
    # NEW: Get clustering method from config
    clustering_method = _cfg_get(cfg, "regimes.clustering_method", "kmeans").lower()
    
    Console.info(f"[REGIME] Using clustering method: {clustering_method}", component="REGIME")
    
    # Fit clustering based on method
    if clustering_method == "hdbscan":
        (
            scaler,
            clusterer,  # HDBSCAN object instead of KMeans
            best_k,
            best_score,
            best_metric,
            quality_sweep,
            low_quality,
        ) = _fit_hdbscan(
            train_basis.to_numpy(dtype=float, copy=False),
            cfg,
            pre_scaled=bool(basis_meta.get("basis_normalized", False)),
        )
        kmeans = None  # No KMeans object for HDBSCAN
        hdbscan_obj = clusterer
        centroids = clusterer.cluster_centroids_
        
    elif clustering_method == "kmeans":
        (
            scaler,
            kmeans,
            best_k,
            best_score,
            best_metric,
            quality_sweep,
            low_quality,
        ) = _fit_kmeans_scaled(
            train_basis.to_numpy(dtype=float, copy=False),
            cfg,
            pre_scaled=bool(basis_meta.get("basis_normalized", False)),
        )
        hdbscan_obj = None
        centroids = kmeans.cluster_centers_
        
    else:
        raise ValueError(
            f"Unknown clustering method '{clustering_method}'. "
            f"Supported: 'kmeans', 'hdbscan'"
        )
    
    # Store convergence diagnostics (k-means only)
    if kmeans is not None:
        try:
            basis_meta["kmeans_inertia"] = float(kmeans.inertia_)
            basis_meta["kmeans_n_iter"] = int(getattr(kmeans, "n_iter_", 0))
        except Exception:
            pass
    
    # Quality validation (same logic for both methods)
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
        quality_notes.append("quality_below_threshold")
    quality_notes.extend(input_issues)
    quality_notes.extend(config_issues)
    if np.isnan(best_score):
        quality_notes.append("unscored")
    
    # Build metadata
    meta = {
        "best_k": int(best_k),
        "fit_score": float(best_score),
        "fit_metric": best_metric,
        "quality_ok": bool(quality_ok),
        "quality_notes": quality_notes,
        "quality_sweep": sorted(quality_sweep, key=lambda item: item[0]),
        "model_version": REGIME_MODEL_VERSION,
        "sklearn_version": sklearn.__version__,
        "clustering_method": clustering_method,  # NEW: Record method used
    }
    
    if "kmeans_inertia" in basis_meta:
        meta["kmeans_inertia"] = basis_meta["kmeans_inertia"]
    if "kmeans_n_iter" in basis_meta:
        meta["kmeans_n_iter"] = basis_meta["kmeans_n_iter"]
    meta.update({k: v for k, v in basis_meta.items() if k not in meta})
    
    # Aggregate quality score
    quality_score = 0.0
    if np.isfinite(best_score):
        if best_metric == "silhouette":
            quality_score = float(np.clip(best_score, 0.0, 1.0) * 100.0)
        elif best_metric == "calinski_harabasz":
            cal_ref = max(calinski_min, 1.0)
            quality_score = float(np.clip(best_score / (2 * cal_ref), 0.0, 1.0) * 100.0)
    if not quality_ok:
        quality_score = min(quality_score, 50.0)
    meta["regime_quality_score"] = quality_score
    
    if train_hash is None:
        try:
            meta_hash = _stable_int_hash(train_basis.to_numpy(dtype=float, copy=False))
            train_hash = meta_hash
        except Exception:
            pass
    
    # Build RegimeModel
    model = RegimeModel(
        scaler=scaler,
        kmeans=kmeans,  # Will be None for HDBSCAN
        feature_columns=list(train_basis.columns),
        raw_tags=basis_meta.get("raw_tags", []),
        n_pca_components=int(basis_meta.get("n_pca", 0)),
        train_hash=train_hash,
        meta=meta,
        hdbscan_clusterer=hdbscan_obj,  # NEW: Store HDBSCAN object
        cluster_centroids=centroids,  # NEW: Store centroids (for both methods)
        clustering_method=clustering_method,  # NEW: Record method
    )
    
    return model
```

### 2.5 Update predict_regime Function (Line ~697)

```python
def predict_regime(model: RegimeModel, basis_df: pd.DataFrame) -> np.ndarray:
    """
    Predict regime labels for new data using fitted model.
    
    Handles both KMeans and HDBSCAN predictions.
    FIX #6: Validates feature dimensions and warns on mismatches.
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
                f"[REGIME] CRITICAL: {len(missing_cols)}/{len(expected_cols)} features missing ({missing_pct:.1f}%). "
                f"Missing: {list(missing_cols)[:5]}{'...' if len(missing_cols) > 5 else ''}. "
                f"Predictions may be unreliable - filling with 0.0"
            )
        elif missing_cols:
            Console.warn(
                f"[REGIME] {len(missing_cols)} features missing: {list(missing_cols)[:3]}{'...' if len(missing_cols) > 3 else ''}. "
                f"Filling with 0.0"
            )
    
    if extra_cols:
        Console.info(
            f"[REGIME] {len(extra_cols)} extra features ignored: {list(extra_cols)[:3]}{'...' if len(extra_cols) > 3 else ''}"
        )
    
    # Align features
    aligned = basis_df.reindex(columns=model.feature_columns, fill_value=0.0)
    aligned_arr = aligned.to_numpy(dtype=np.float64, copy=False, na_value=0.0)
    X_scaled = model.scaler.transform(aligned_arr)
    X_scaled = np.asarray(X_scaled, dtype=np.float64, order="C")
    
    # NEW: Predict based on clustering method
    if model.clustering_method == "hdbscan":
        # HDBSCAN approximate prediction
        if model.hdbscan_clusterer is None:
            raise ValueError("HDBSCAN clusterer not available in model")
        
        # Use approximate_predict for new samples
        labels, _ = hdbscan.approximate_predict(model.hdbscan_clusterer, X_scaled)
        
        # Handle noise labels (-1) by assigning to nearest cluster centroid
        noise_mask = labels == -1
        if noise_mask.any() and model.cluster_centroids is not None and len(model.cluster_centroids) > 0:
            # Assign noise points to nearest centroid
            noise_points = X_scaled[noise_mask]
            nearest_clusters = pairwise_distances_argmin(
                noise_points, 
                model.cluster_centroids,
                axis=1
            )
            labels[noise_mask] = nearest_clusters
            
            noise_count = noise_mask.sum()
            Console.info(
                f"[REGIME] Assigned {noise_count} noise samples to nearest cluster",
                component="REGIME"
            )
        
        return labels.astype(int, copy=False)
        
    elif model.clustering_method == "kmeans":
        # KMeans prediction (original implementation)
        if model.kmeans is None:
            raise ValueError("KMeans clusterer not available in model")
        
        centers = np.asarray(model.kmeans.cluster_centers_, dtype=np.float64, order="C")
        labels = pairwise_distances_argmin(X_scaled, centers, axis=1)
        return labels.astype(int, copy=False)
        
    else:
        raise ValueError(f"Unknown clustering method: {model.clustering_method}")
```

### 2.6 Update save_regime_model Function (Line ~2132)

```python
def save_regime_model(model: RegimeModel, models_dir: Path) -> None:
    """
    Save regime model with joblib persistence for sklearn/hdbscan objects.
    
    Saves:
    - regime_model.joblib: KMeans/HDBSCAN and StandardScaler objects
    - regime_model.json: Metadata (feature columns, health labels, stats)
    """
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Save sklearn/hdbscan objects with joblib
    joblib_path = models_dir / "regime_model.joblib"
    try:
        joblib_data = {
            'scaler': model.scaler,
            'train_hash': model.train_hash,
            'clustering_method': model.clustering_method,  # NEW: Save method type
        }
        
        # NEW: Save method-specific clusterer
        if model.clustering_method == "kmeans":
            joblib_data['kmeans'] = model.kmeans
        elif model.clustering_method == "hdbscan":
            joblib_data['hdbscan_clusterer'] = model.hdbscan_clusterer
            joblib_data['cluster_centroids'] = model.cluster_centroids
        
        joblib.dump(joblib_data, joblib_path)
        Console.info(
            f"Saved regime model ({model.clustering_method}) -> {joblib_path}",
            component="REGIME"
        )
    except Exception as e:
        Console.warn(f"Failed to save regime joblib: {e}", component="REGIME")
        _persist_regime_error(e, models_dir)
        raise
    
    # Save metadata as JSON (same as before)
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
        Console.warn(f"Failed to save regime metadata: {e}", component="REGIME")
        _persist_regime_error(e, models_dir)
        raise
```

### 2.7 Update load_regime_model Function (Line ~2180)

```python
def load_regime_model(models_dir: Path) -> Optional[RegimeModel]:
    """
    Load regime model from disk.
    
    Supports both KMeans and HDBSCAN models.
    """
    models_dir = Path(models_dir)
    joblib_path = models_dir / "regime_model.joblib"
    json_path = models_dir / "regime_model.json"
    
    # Check if both files exist
    if not joblib_path.exists():
        Console.info(f"No cached regime model found at {joblib_path}", component="REGIME")
        return None
    
    if not json_path.exists():
        Console.warn(f"Regime joblib exists but metadata missing: {json_path}", component="REGIME")
        return None
    
    try:
        # Load sklearn/hdbscan objects
        joblib_data = joblib.load(joblib_path)
        scaler = joblib_data['scaler']
        train_hash = joblib_data.get('train_hash')
        clustering_method = joblib_data.get('clustering_method', 'kmeans')  # Default to kmeans for old models
        
        # NEW: Load method-specific clusterer
        if clustering_method == "kmeans":
            kmeans = joblib_data.get('kmeans')
            hdbscan_clusterer = None
            cluster_centroids = kmeans.cluster_centers_ if kmeans is not None else None
        elif clustering_method == "hdbscan":
            kmeans = None
            hdbscan_clusterer = joblib_data.get('hdbscan_clusterer')
            cluster_centroids = joblib_data.get('cluster_centroids')
        else:
            Console.warn(f"Unknown clustering method in cached model: {clustering_method}", component="REGIME")
            return None
        
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
                f"[REGIME] Cached model version {version} compatible with {REGIME_MODEL_VERSION} (same major)"
            )
            
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
            hdbscan_clusterer=hdbscan_clusterer,  # NEW: Restore HDBSCAN object
            cluster_centroids=cluster_centroids,  # NEW: Restore centroids
            clustering_method=clustering_method,  # NEW: Restore method type
        )
        
        Console.info(f"Loaded cached regime model ({clustering_method}) from {joblib_path}", component="REGIME")
        cluster_count = len(cluster_centroids) if cluster_centroids is not None else 0
        Console.info(
            f"[REGIME]   - Method={clustering_method}, K={cluster_count}, "
            f"features={len(model.feature_columns)}, train_hash={train_hash}"
        )
        return model
        
    except Exception as e:
        Console.warn(f"Failed to load regime model: {e}", component="REGIME")
        return None
```

---

## 3. Configuration Updates

### 3.1 Add to configs/config_table.csv

```csv
EquipID,Category,ParamPath,ParamValue,ValueType,LastUpdated,UpdatedBy,ChangeReason,UpdatedDateTime
# Clustering method selection (global default)
0,regimes,clustering_method,kmeans,string,2025-12-20 00:00:00,COPILOT,add_hdbscan_support,

# HDBSCAN parameters
0,regimes,hdbscan.min_cluster_size,50,int,2025-12-20 00:00:00,COPILOT,hdbscan_default_params,
0,regimes,hdbscan.min_samples,10,int,2025-12-20 00:00:00,COPILOT,hdbscan_default_params,
0,regimes,hdbscan.cluster_selection_method,eom,string,2025-12-20 00:00:00,COPILOT,hdbscan_excess_of_mass,
0,regimes,hdbscan.max_noise_ratio,0.15,float,2025-12-20 00:00:00,COPILOT,hdbscan_quality_gate,

# Equipment-specific overrides (example)
1,regimes,clustering_method,hdbscan,string,2025-12-20 00:00:00,COPILOT,fd_fan_cyclic_pattern,
1,regimes,hdbscan.min_cluster_size,40,int,2025-12-20 00:00:00,COPILOT,fd_fan_smaller_clusters,
```

### 3.2 Sync Configuration to SQL

```bash
cd /home/runner/work/ACM/ACM
python scripts/sql/populate_acm_config.py
```

---

## 4. Testing

### 4.1 Create tests/test_regimes_hdbscan.py

```python
"""
Test HDBSCAN clustering integration for regime detection.
"""
import numpy as np
import pandas as pd
import pytest
from core import regimes

@pytest.fixture
def cyclic_data():
    """Generate synthetic data with cyclic pattern (day/night)."""
    np.random.seed(42)
    
    # Day regime (high density): 8am-8pm, 300 samples
    day_mean = [5, 3, 2, 1, 0]
    day_samples = np.random.randn(300, 5) * 0.5 + day_mean
    
    # Night regime (low density): 8pm-8am, 150 samples
    night_mean = [1, 0.5, 0.3, 0.1, 0]
    night_samples = np.random.randn(150, 5) * 0.3 + night_mean
    
    # Transient events (startup/shutdown): 50 scattered samples
    transient_samples = np.random.randn(50, 5) * 2 + [3, 2, 1, 0.5, 0.2]
    
    X = np.vstack([day_samples, night_samples, transient_samples])
    return pd.DataFrame(X, columns=[f'feat_{i}' for i in range(5)])

def test_hdbscan_basic_fitting(cyclic_data):
    """Test HDBSCAN fits and produces reasonable clusters."""
    cfg = {
        'regimes': {
            'clustering_method': 'hdbscan',
            'hdbscan': {
                'min_cluster_size': 50,
                'min_samples': 10,
                'cluster_selection_method': 'eom',
                'max_noise_ratio': 0.20
            }
        }
    }
    
    model = regimes.fit_regime_model(
        train_basis=cyclic_data,
        basis_meta={'basis_normalized': False},
        cfg=cfg,
        train_hash=None
    )
    
    # Verify model structure
    assert model.clustering_method == "hdbscan"
    assert model.hdbscan_clusterer is not None
    assert model.kmeans is None
    assert model.cluster_centroids is not None
    
    # Verify cluster count (expect 2-3 clusters + some noise)
    n_clusters = len(model.cluster_centroids)
    assert 2 <= n_clusters <= 4, f"Expected 2-4 clusters, got {n_clusters}"
    
    # Verify quality metrics
    assert model.meta['fit_metric'] in ['silhouette', 'calinski_harabasz']
    assert model.meta['clustering_method'] == 'hdbscan'

def test_hdbscan_noise_detection(cyclic_data):
    """Test HDBSCAN marks transient samples as noise."""
    cfg = {
        'regimes': {
            'clustering_method': 'hdbscan',
            'hdbscan': {
                'min_cluster_size': 60,  # Larger to force noise
                'min_samples': 15,
                'max_noise_ratio': 0.25
            }
        }
    }
    
    model = regimes.fit_regime_model(cyclic_data, {}, cfg, None)
    labels = regimes.predict_regime(model, cyclic_data)
    
    # Check noise detection (some samples should be reassigned from -1)
    unique_labels = set(labels)
    assert -1 not in unique_labels, "All noise should be reassigned to nearest cluster"
    
    # Verify clustering quality despite noise
    assert model.meta['quality_ok'] or model.meta['fit_score'] > 0.3

def test_hdbscan_prediction(cyclic_data):
    """Test HDBSCAN predicts labels for new data."""
    cfg = {
        'regimes': {
            'clustering_method': 'hdbscan',
            'hdbscan': {
                'min_cluster_size': 50,
                'min_samples': 10
            }
        }
    }
    
    # Fit on training data
    train_data = cyclic_data.iloc[:400]  # Use first 400 samples for training
    model = regimes.fit_regime_model(train_data, {}, cfg, None)
    
    # Predict on test data
    test_data = cyclic_data.iloc[400:]  # Last 100 samples for testing
    labels = regimes.predict_regime(model, test_data)
    
    # Verify predictions
    assert len(labels) == len(test_data)
    assert labels.min() >= 0, "No noise labels should remain after prediction"
    assert labels.max() < len(model.cluster_centroids), "All labels within cluster range"

def test_hdbscan_vs_kmeans_quality(cyclic_data):
    """Compare HDBSCAN vs KMeans on cyclic data."""
    # Fit KMeans
    cfg_kmeans = {
        'regimes': {
            'clustering_method': 'kmeans',
            'auto_k': {'k_min': 2, 'k_max': 6}
        }
    }
    model_kmeans = regimes.fit_regime_model(cyclic_data, {}, cfg_kmeans, None)
    
    # Fit HDBSCAN
    cfg_hdbscan = {
        'regimes': {
            'clustering_method': 'hdbscan',
            'hdbscan': {
                'min_cluster_size': 50,
                'min_samples': 10
            }
        }
    }
    model_hdbscan = regimes.fit_regime_model(cyclic_data, {}, cfg_hdbscan, None)
    
    # Compare quality scores
    kmeans_score = model_kmeans.meta['fit_score']
    hdbscan_score = model_hdbscan.meta['fit_score']
    
    print(f"KMeans silhouette: {kmeans_score:.3f}")
    print(f"HDBSCAN silhouette: {hdbscan_score:.3f}")
    
    # Both should achieve acceptable quality
    assert kmeans_score > 0.3 or model_kmeans.meta['quality_ok']
    assert hdbscan_score > 0.3 or model_hdbscan.meta['quality_ok']

def test_hdbscan_model_persistence(tmp_path, cyclic_data):
    """Test HDBSCAN model save/load cycle."""
    cfg = {
        'regimes': {
            'clustering_method': 'hdbscan',
            'hdbscan': {
                'min_cluster_size': 50,
                'min_samples': 10
            }
        }
    }
    
    # Fit and save
    model = regimes.fit_regime_model(cyclic_data, {}, cfg, None)
    models_dir = tmp_path / "models"
    regimes.save_regime_model(model, models_dir)
    
    # Load and verify
    loaded_model = regimes.load_regime_model(models_dir)
    assert loaded_model is not None
    assert loaded_model.clustering_method == "hdbscan"
    assert loaded_model.hdbscan_clusterer is not None
    
    # Test prediction with loaded model
    labels = regimes.predict_regime(loaded_model, cyclic_data)
    assert len(labels) == len(cyclic_data)
```

### 4.2 Run Tests

```bash
cd /home/runner/work/ACM/ACM
pytest tests/test_regimes_hdbscan.py -v
```

---

## 5. Validation on Historical Data

### 5.1 Create Comparison Script

**File:** `scripts/compare_kmeans_hdbscan.py`

```python
"""
Compare KMeans vs HDBSCAN clustering on historical ACM data.
"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from core import regimes
from utils.config_dict import ConfigDict

def load_historical_features(equipment: str, data_dir: Path = Path("data")):
    """Load historical feature data for equipment."""
    # Example: Load from CSV or SQL
    csv_path = data_dir / f"{equipment}_features.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        return df
    else:
        print(f"No historical data found for {equipment}")
        return None

def compare_clustering_methods(equipment: str):
    """Run KMeans and HDBSCAN on same data and compare."""
    print(f"\n{'='*60}")
    print(f"Clustering Comparison for {equipment}")
    print(f"{'='*60}\n")
    
    # Load configuration
    cfg_dict = ConfigDict(f"configs/config_table.csv")
    cfg = cfg_dict.to_dict()
    
    # Load historical data
    features_df = load_historical_features(equipment)
    if features_df is None or features_df.empty:
        print(f"No data available for {equipment}")
        return
    
    print(f"Loaded {len(features_df)} samples with {features_df.shape[1]} features\n")
    
    # Test 1: KMeans
    print("1. Fitting KMeans...")
    cfg['regimes']['clustering_method'] = 'kmeans'
    model_kmeans = regimes.fit_regime_model(features_df, {}, cfg, None)
    
    kmeans_k = model_kmeans.meta['best_k']
    kmeans_score = model_kmeans.meta['fit_score']
    kmeans_metric = model_kmeans.meta['fit_metric']
    
    print(f"   K={kmeans_k}, {kmeans_metric}={kmeans_score:.3f}\n")
    
    # Test 2: HDBSCAN
    print("2. Fitting HDBSCAN...")
    cfg['regimes']['clustering_method'] = 'hdbscan'
    cfg['regimes']['hdbscan'] = {
        'min_cluster_size': 50,
        'min_samples': 10,
        'cluster_selection_method': 'eom',
        'max_noise_ratio': 0.15
    }
    model_hdbscan = regimes.fit_regime_model(features_df, {}, cfg, None)
    
    hdbscan_k = model_hdbscan.meta['best_k']
    hdbscan_score = model_hdbscan.meta['fit_score']
    hdbscan_metric = model_hdbscan.meta['fit_metric']
    
    print(f"   K={hdbscan_k}, {hdbscan_metric}={hdbscan_score:.3f}\n")
    
    # Comparison
    print("Comparison Summary:")
    print(f"  KMeans:   K={kmeans_k}, score={kmeans_score:.3f}")
    print(f"  HDBSCAN:  K={hdbscan_k}, score={hdbscan_score:.3f}")
    
    if hdbscan_score > kmeans_score:
        improvement = ((hdbscan_score - kmeans_score) / kmeans_score) * 100
        print(f"\n  → HDBSCAN improves quality by {improvement:.1f}%")
    elif kmeans_score > hdbscan_score:
        decline = ((kmeans_score - hdbscan_score) / kmeans_score) * 100
        print(f"\n  → KMeans performs {decline:.1f}% better")
    else:
        print(f"\n  → Methods perform equivalently")
    
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    equipment = sys.argv[1] if len(sys.argv) > 1 else "FD_FAN"
    compare_clustering_methods(equipment)
```

### 5.2 Run Comparison

```bash
cd /home/runner/work/ACM/ACM
python scripts/compare_kmeans_hdbscan.py FD_FAN
python scripts/compare_kmeans_hdbscan.py GAS_TURBINE
```

---

## 6. Deployment Checklist

### 6.1 Pre-Deployment

- [ ] Install hdbscan package: `pip install hdbscan>=0.8.33`
- [ ] Update pyproject.toml dependencies
- [ ] Add HDBSCAN code to `core/regimes.py` (sections 2.1-2.7)
- [ ] Add configuration parameters to `configs/config_table.csv`
- [ ] Sync config to SQL: `python scripts/sql/populate_acm_config.py`
- [ ] Create test file `tests/test_regimes_hdbscan.py`
- [ ] Run unit tests: `pytest tests/test_regimes_hdbscan.py -v`
- [ ] Create comparison script `scripts/compare_kmeans_hdbscan.py`
- [ ] Run comparison on historical FD_FAN and GAS_TURBINE data

### 6.2 Deployment

- [ ] Default global config remains `clustering_method=kmeans` (backward compatible)
- [ ] Enable HDBSCAN for 1-2 test equipments via config override
- [ ] Monitor regime quality metrics (silhouette, noise ratio, cluster count)
- [ ] Compare false positive rates before/after
- [ ] Collect operator feedback on regime interpretability

### 6.3 Post-Deployment Validation

- [ ] Verify regime stability across 10 consecutive batches
- [ ] Check per-regime threshold effectiveness (ScoreCalibrator)
- [ ] Validate noise samples correspond to known transient events
- [ ] Measure clustering runtime (should be <60s for typical batch sizes)
- [ ] Document method selection guidelines based on results

---

## 7. Rollback Plan

If HDBSCAN causes issues:

1. **Immediate Rollback** (per equipment):
   ```csv
   # In ACM_Config or config_table.csv
   1,regimes,clustering_method,kmeans,string
   ```

2. **Sync Configuration**:
   ```bash
   python scripts/sql/populate_acm_config.py
   ```

3. **Clear Cached Models**:
   ```bash
   python -m core.acm_main --equip FD_FAN --clear-cache
   ```

4. **Re-run Batch**:
   ```bash
   python scripts/sql_batch_runner.py --equip FD_FAN --tick-minutes 1440
   ```

Existing KMeans models remain valid and will load without modification.

---

## 8. Expected Outcomes

### 8.1 For Cyclic Equipment (e.g., FD_FAN)

**Before (KMeans):**
- K=2-3 clusters
- Silhouette: 0.85-0.95
- Transient events mixed into steady-state clusters
- Day/night regimes may overlap

**After (HDBSCAN):**
- K=2-3 clusters + noise
- Silhouette: 0.85-1.0 (similar or better)
- Transient events marked as noise (5-10% of samples)
- Day/night regimes better separated (density-aware)

**Impact:**
- **False positives**: -10-20% from transient noise filtering
- **Interpretability**: Clearer regime boundaries
- **Stability**: Similar across batches (±1 cluster)

### 8.2 For Gradual Transition Equipment (e.g., GAS_TURBINE)

**Observation:**
- HDBSCAN may struggle with gradual transitions (no clear density boundaries)
- KMeans likely to remain superior for smooth load ramping

**Recommendation:**
- Keep `clustering_method=kmeans` for GAS_TURBINE
- Consider GMM in Phase 2 for soft clustering

---

## 9. Future Enhancements

### 9.1 HDBSCAN Parameter Auto-Tuning

Automatically adjust `min_cluster_size` based on data characteristics:

```python
def auto_tune_hdbscan_params(X, cfg):
    """Automatically tune HDBSCAN parameters based on data size and variance."""
    n_samples = X.shape[0]
    
    # Rule of thumb: min_cluster_size = 1-5% of samples
    min_cluster_size = int(np.clip(n_samples * 0.02, 20, 200))
    
    # min_samples = sqrt(min_cluster_size)
    min_samples = int(np.sqrt(min_cluster_size))
    
    return min_cluster_size, min_samples
```

### 9.2 Noise Sample Analysis

Track noise samples and correlate with known events:

```python
def analyze_noise_samples(labels, timestamps, events_df):
    """Analyze which noise samples correspond to known startup/shutdown events."""
    noise_mask = labels == -1
    noise_timestamps = timestamps[noise_mask]
    
    # Match noise timestamps with event log
    # Generate report: "85% of noise samples occurred during startup/shutdown"
```

### 9.3 Hybrid Method Selection

Automatically select clustering method based on data characteristics:

```python
def auto_select_clustering_method(X):
    """Automatically select clustering method based on data properties."""
    # Compute density variation
    density_std = compute_local_density_std(X)
    
    # Compute transition smoothness
    transition_score = compute_transition_smoothness(X)
    
    if density_std > 0.5:
        return "hdbscan"  # High density variation
    elif transition_score > 0.7:
        return "gmm"  # Smooth transitions
    else:
        return "kmeans"  # Default
```

---

## 10. References

- **HDBSCAN Documentation**: https://hdbscan.readthedocs.io/
- **Paper**: Campello et al. (2013) "Density-Based Clustering Based on Hierarchical Density Estimates"
- **Implementation**: McInnes & Healy (2017) "Accelerated Hierarchical Density Based Clustering"
- **ACM Codebase**: `core/regimes.py`, `docs/DET-07_PER_REGIME_THRESHOLDS.md`

---

**Document Status:** Implementation Blueprint - Ready for Development  
**Estimated Effort:** 2-3 days (coding + testing)  
**Risk Level:** LOW (backward compatible, opt-in per equipment)  
**Next Action:** Review and approve for Phase 1 implementation

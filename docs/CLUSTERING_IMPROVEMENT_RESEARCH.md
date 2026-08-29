# Clustering Improvement Research for ACM Regime Detection

**Created:** 2025-12-20  
**Status:** Research & Recommendations  
**Owner:** AI/Copilot Analysis

---

## Executive Summary

This document analyzes alternative clustering methods for ACM's regime detection system and provides recommendations for improving operational regime identification in industrial predictive maintenance applications.

**Current State:** MiniBatchKMeans with auto-k selection (k=2-6, silhouette-based quality gates)

**Recommended Improvements:**
1. **PRIMARY**: Implement HDBSCAN for density-based regime detection (handles varying operating densities)
2. **SECONDARY**: Add Gaussian Mixture Models (GMM) for probabilistic regime assignment
3. **ENHANCEMENT**: Implement ensemble voting for robust regime identification
4. **FUTURE**: Explore time-series-specific clustering (DTW, shapelets)

---

## 1. Current Implementation Analysis

### 1.1 Current Method: MiniBatchKMeans

**Location:** `core/regimes.py` lines 458-600

**Implementation:**
```python
def _fit_kmeans_scaled(X, cfg, *, pre_scaled=False):
    """Fit KMeans with auto-k selection using silhouette scoring"""
    k_min = int(_cfg_get(cfg, "regimes.auto_k.k_min", 2))
    k_max = int(_cfg_get(cfg, "regimes.auto_k.k_max", 6))
    # ... silhouette-based auto-k selection
    best_model = MiniBatchKMeans(n_clusters=best_k, ...)
```

**Strengths:**
- ✅ Fast: O(n*k*i) complexity, handles 100K+ samples efficiently
- ✅ Incremental: MiniBatch variant supports online learning
- ✅ Interpretable: Clear cluster centroids represent operating points
- ✅ Proven: Silhouette scores consistently 0.8-1.0 for FD_FAN equipment
- ✅ Quality gates: Automatic validation via silhouette/Calinski-Harabasz

**Weaknesses:**
- ❌ Assumes spherical clusters (may miss elongated operational regimes)
- ❌ Sensitive to initialization (mitigated by n_init=20 but still a factor)
- ❌ Hard boundaries: No transition probabilities between regimes
- ❌ Fixed k: Must pre-specify cluster range (auto-k helps but still constrained)
- ❌ Poor with varying densities: Day/night cycles may have different data densities
- ❌ Outlier sensitive: Transient states can distort cluster centers

### 1.2 ACM-Specific Requirements

From analysis of `core/regimes.py`, `docs/DET-07_PER_REGIME_THRESHOLDS.md`, and `core/acm_main.py`:

**Functional Requirements:**
1. **Operating Regime Detection**: Identify distinct operational states (steady-state, startup, shutdown, high-load, low-load)
2. **Per-Regime Thresholds**: Enable different anomaly sensitivity per regime (ScoreCalibrator in `core/fuse.py`)
3. **Health State Assignment**: Map regimes to health labels (healthy/suspect/critical)
4. **Transient Detection**: Distinguish stable vs transient states (startup/shutdown/trip events)
5. **Regime Continuity**: Track regime transitions and dwell times for stability metrics

**Technical Requirements:**
1. **Batch Processing**: Must work with 200-100,000 sample windows
2. **Quality Validation**: Automated quality gates (silhouette ≥ 0.2 minimum)
3. **Feature Flexibility**: Support PCA-reduced features OR raw operational sensors
4. **Persistence**: Models must be serializable for continuous learning
5. **Performance**: Sub-minute clustering for typical batch sizes
6. **Interpretability**: Operators must understand what each regime represents

**Data Characteristics (from configs/config_table.csv and README.md):**
- **Sampling rate**: 1800 seconds (30 minutes) for FD_FAN, 1440 minutes (24 hours) for GAS_TURBINE
- **Feature space**: 3-5 PCA components OR 10-50 raw operational sensors
- **Equipment types**: Rotating machinery (fans, turbines, pumps, motors)
- **Operational patterns**: 
  - Cyclic (day/night, weekday/weekend)
  - Load-dependent (production demand)
  - Environmental (temperature, humidity effects)
  - Transient events (startups, shutdowns, trips)

---

## 2. Alternative Clustering Methods

### 2.1 HDBSCAN (Hierarchical Density-Based Spatial Clustering)

**Status:** ⭐ **RECOMMENDED - HIGH PRIORITY**

**Overview:**
- Extends DBSCAN with hierarchical clustering
- Automatically determines number of clusters
- Handles varying density regions (critical for day/night operational patterns)
- Robust to noise and outliers (marks transient events as noise)

**Advantages for ACM:**
1. ✅ **Auto-determines k**: No need for k_min/k_max configuration
2. ✅ **Handles varying densities**: Day operations (high density) vs night (sparse) naturally separated
3. ✅ **Noise handling**: Transient startup/shutdown events marked as outliers (label=-1)
4. ✅ **Hierarchical structure**: Dendrograms show regime relationships (parent/child operational states)
5. ✅ **Soft clustering**: Provides cluster membership probabilities (useful for transition zones)
6. ✅ **Stable clusters**: Less sensitive to initialization than k-means

**Disadvantages:**
1. ⚠️ **Computational cost**: O(n log n) vs O(n*k*i) for k-means (acceptable for batch sizes <100K)
2. ⚠️ **Hyperparameters**: `min_cluster_size` and `min_samples` require tuning
3. ⚠️ **No centroids**: Must compute representative points post-hoc for interpretability
4. ⚠️ **Variable k**: Output cluster count may vary across batches (continuity challenge)

**Implementation Strategy:**
```python
from hdbscan import HDBSCAN

def _fit_hdbscan(X, cfg):
    """Fit HDBSCAN with adaptive parameters"""
    min_cluster_size = int(_cfg_get(cfg, "regimes.hdbscan.min_cluster_size", 50))
    min_samples = int(_cfg_get(cfg, "regimes.hdbscan.min_samples", 10))
    
    clusterer = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric='euclidean',
        cluster_selection_method='eom',  # Excess of Mass (robust)
        prediction_data=True  # Enable soft clustering
    )
    clusterer.fit(X)
    
    # Compute centroids for cluster k (excluding noise label=-1)
    labels = clusterer.labels_
    unique_labels = set(labels) - {-1}
    centroids = np.array([X[labels == k].mean(axis=0) for k in unique_labels])
    
    # Quality metrics
    if len(unique_labels) >= 2:
        score = silhouette_score(X, labels, sample_size=4000)
    else:
        score = 0.0
    
    return clusterer, centroids, len(unique_labels), score
```

**Configuration Parameters:**
```csv
EquipID,Category,ParamPath,ParamValue,ValueType
0,regimes,clustering_method,hdbscan,string
0,regimes,hdbscan.min_cluster_size,50,int
0,regimes,hdbscan.min_samples,10,int
0,regimes,hdbscan.cluster_selection_method,eom,string
```

**Integration Points:**
1. Add to `_fit_kmeans_scaled()` as alternative branch based on `clustering_method` config
2. RegimeModel needs additional fields: `noise_labels`, `cluster_probabilities`
3. Update `predict_regime()` to use HDBSCAN's `approximate_predict()` for new samples
4. Modify regime continuity tracking to handle variable k across batches

**Quality Validation:**
- Silhouette score (existing)
- DBCV (Density-Based Cluster Validation) - HDBSCAN-specific metric
- Noise ratio (% of samples labeled as -1, should be <10% for stable operations)

**Use Case Priority:**
- **HIGH** for equipment with cyclic patterns (day/night, weekday/weekend)
- **HIGH** for equipment with transient events (frequent startups/shutdowns)
- **MEDIUM** for steady-state equipment (k-means may be sufficient)

---

### 2.2 Gaussian Mixture Models (GMM) for Clustering

**Status:** ⭐ **RECOMMENDED - MEDIUM PRIORITY**

**Overview:**
- Probabilistic clustering using mixture of Gaussians
- Soft cluster assignments (probability of belonging to each regime)
- Already in ACM as anomaly detector (`core/gmm.py`) - can repurpose

**Advantages for ACM:**
1. ✅ **Soft clustering**: Probabilistic regime membership (e.g., 70% steady-state, 30% transition)
2. ✅ **Overlapping regimes**: Handles transition zones naturally
3. ✅ **BIC selection**: Automatic k selection via Bayesian Information Criterion
4. ✅ **Existing infrastructure**: GMM detector code can be adapted
5. ✅ **Covariance modeling**: Captures operational regime shape (spherical, diagonal, full)
6. ✅ **Interpretable**: Gaussian parameters directly map to operational ranges

**Disadvantages:**
1. ⚠️ **Assumes Gaussian**: May miss non-Gaussian operational regimes
2. ⚠️ **EM convergence**: May get stuck in local optima (mitigated by n_init restarts)
3. ⚠️ **Covariance estimation**: Full covariance requires more samples (n > d²)

**Implementation Strategy:**
```python
from sklearn.mixture import GaussianMixture, BayesianGaussianMixture

def _fit_gmm_clustering(X, cfg):
    """Fit GMM with BIC-based k selection"""
    k_min = int(_cfg_get(cfg, "regimes.gmm.k_min", 2))
    k_max = int(_cfg_get(cfg, "regimes.gmm.k_max", 8))
    covariance_type = _cfg_get(cfg, "regimes.gmm.covariance_type", "diag")
    
    best_bic = np.inf
    best_model = None
    best_k = k_min
    
    for k in range(k_min, k_max + 1):
        gmm = GaussianMixture(
            n_components=k,
            covariance_type=covariance_type,
            n_init=10,
            random_state=17,
            max_iter=100
        )
        gmm.fit(X)
        bic = gmm.bic(X)
        
        if bic < best_bic:
            best_bic = bic
            best_model = gmm
            best_k = k
    
    labels = best_model.predict(X)
    score = silhouette_score(X, labels, sample_size=4000)
    
    # Soft assignments for transition analysis
    probs = best_model.predict_proba(X)
    
    return best_model, best_k, score, labels, probs
```

**Configuration Parameters:**
```csv
EquipID,Category,ParamPath,ParamValue,ValueType
0,regimes,clustering_method,gmm,string
0,regimes,gmm.k_min,2,int
0,regimes,gmm.k_max,8,int
0,regimes,gmm.covariance_type,diag,string
0,regimes,gmm.use_bayesian,False,bool
```

**Integration Points:**
1. Add to `fit_regime_model()` as alternative to k-means
2. RegimeModel stores GMM object instead of KMeans
3. Use `predict_proba()` for soft regime assignments in transitions
4. Modify `smooth_transitions()` to use probabilities instead of hard labels

**Use Case Priority:**
- **HIGH** for gradual transitions (load ramping, temperature drift)
- **MEDIUM** for regime overlap scenarios (mixed operational states)
- **LOW** for discrete operational modes (on/off, start/stop)

---

### 2.3 Agglomerative Hierarchical Clustering

**Status:** RECOMMENDED - MEDIUM PRIORITY

**Overview:**
- Bottom-up hierarchical clustering
- Produces dendrogram showing regime relationships
- Cut tree at optimal height to get clusters

**Advantages for ACM:**
1. ✅ **Deterministic**: No random initialization (fully reproducible)
2. ✅ **Hierarchical structure**: Shows parent/child regime relationships
3. ✅ **Flexible linkage**: Ward (minimum variance), Complete (maximum distance), Average
4. ✅ **Dendrogram visualization**: Operators can see regime hierarchy
5. ✅ **Variable k**: Can cut tree at different heights for different k

**Disadvantages:**
1. ⚠️ **Computational cost**: O(n²) to O(n³) depending on linkage method
2. ⚠️ **Memory**: Stores full distance matrix (prohibitive for n>10K)
3. ⚠️ **Irreversible**: Cannot undo merges (bottom-up only)

**Implementation Strategy:**
```python
from sklearn.cluster import AgglomerativeClustering
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster

def _fit_hierarchical(X, cfg):
    """Fit hierarchical clustering with optimal cut"""
    k_max = int(_cfg_get(cfg, "regimes.auto_k.k_max", 6))
    linkage_method = _cfg_get(cfg, "regimes.hierarchical.linkage", "ward")
    
    # Compute linkage matrix for dendrogram
    Z = linkage(X, method=linkage_method)
    
    # Find optimal k using silhouette
    best_score = -np.inf
    best_k = 2
    for k in range(2, k_max + 1):
        labels = fcluster(Z, k, criterion='maxclust')
        score = silhouette_score(X, labels, sample_size=4000)
        if score > best_score:
            best_score = score
            best_k = k
    
    # Final clustering at best k
    agg = AgglomerativeClustering(n_clusters=best_k, linkage=linkage_method)
    labels = agg.fit_predict(X)
    
    # Compute centroids
    centroids = np.array([X[labels == k].mean(axis=0) for k in range(best_k)])
    
    return agg, Z, centroids, best_k, best_score
```

**Use Case Priority:**
- **MEDIUM** for exploratory analysis (dendrogram visualization)
- **LOW** for production batch processing (computational cost)
- **HIGH** for baseline regime identification (one-time hierarchical analysis)

---

### 2.4 OPTICS (Ordering Points To Identify Clustering Structure)

**Status:** FUTURE CONSIDERATION

**Overview:**
- Similar to DBSCAN but produces reachability plot
- Handles varying densities better than DBSCAN
- No ε (epsilon) parameter required

**Advantages for ACM:**
1. ✅ **Reachability plot**: Visualize cluster structure
2. ✅ **Varying densities**: Better than DBSCAN for non-uniform operational patterns
3. ✅ **Automatic**: No epsilon tuning required

**Disadvantages:**
1. ⚠️ **Computational cost**: O(n²) without spatial index
2. ⚠️ **Complex extraction**: Must extract clusters from reachability plot
3. ⚠️ **Less mature**: Fewer production deployments than HDBSCAN

**Use Case Priority:**
- **LOW** - HDBSCAN is preferred for density-based clustering in ACM

---

### 2.5 Spectral Clustering

**Status:** FUTURE CONSIDERATION

**Overview:**
- Graph-based clustering using eigenvalues of affinity matrix
- Excellent for non-convex cluster shapes
- Can use custom similarity metrics

**Advantages for ACM:**
1. ✅ **Non-convex shapes**: Handles complex operational regime geometries
2. ✅ **Graph theory**: Can incorporate sensor correlation structure
3. ✅ **Custom metrics**: Can use domain-specific similarity (Mahalanobis, DTW)

**Disadvantages:**
1. ⚠️ **Computational cost**: O(n³) for eigendecomposition
2. ⚠️ **Scalability**: Poor for n>10K samples
3. ⚠️ **Hyperparameters**: Affinity metric and gamma require tuning

**Use Case Priority:**
- **LOW** - Computational cost prohibitive for typical ACM batch sizes

---

### 2.6 Time-Series Specific Clustering

**Status:** RESEARCH / FUTURE WORK

**Methods:**
1. **DTW K-Means**: Use Dynamic Time Warping as distance metric
2. **Shapelet-based**: Cluster based on discriminative subsequences
3. **ROCKET features**: Random Convolutional Kernels + standard clustering

**Advantages:**
1. ✅ **Temporal patterns**: Captures time-series shape similarity
2. ✅ **Lag invariance**: DTW aligns time-shifted patterns
3. ✅ **Interpretable shapelets**: Operators can see characteristic patterns

**Disadvantages:**
1. ⚠️ **Computational cost**: DTW is O(n²m²) for n samples of length m
2. ⚠️ **Feature engineering**: Current ACM uses aggregated features, not raw time series
3. ⚠️ **Implementation complexity**: Requires specialized libraries (tslearn)

**Use Case Priority:**
- **LOW** - ACM already aggregates time series into statistical features
- **FUTURE** - Consider if raw sensor time-series clustering becomes valuable

---

## 3. Ensemble Clustering Approach

**Status:** ⭐ **RECOMMENDED - ENHANCEMENT**

**Concept:** Combine multiple clustering methods to increase robustness

**Implementation Strategy:**
```python
def ensemble_clustering(X, cfg):
    """Ensemble voting from multiple clustering methods"""
    # Fit multiple methods
    kmeans_labels = _fit_kmeans_scaled(X, cfg)[1].labels_
    hdbscan_labels = _fit_hdbscan(X, cfg)[0].labels_
    gmm_labels = _fit_gmm_clustering(X, cfg)[3]
    
    # Consensus matrix: co-occurrence of samples in same cluster
    n = len(X)
    consensus = np.zeros((n, n))
    
    for labels in [kmeans_labels, hdbscan_labels, gmm_labels]:
        for i in range(n):
            for j in range(i+1, n):
                if labels[i] == labels[j] and labels[i] != -1:
                    consensus[i, j] += 1
                    consensus[j, i] += 1
    
    # Final clustering on consensus matrix
    final_labels = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=2.0,  # Require majority agreement
        linkage='average',
        affinity='precomputed'
    ).fit_predict(3 - consensus)  # Convert similarity to distance
    
    return final_labels
```

**Advantages:**
1. ✅ **Robust**: Reduces impact of any single method's failure modes
2. ✅ **Confidence**: Agreement level indicates regime clarity
3. ✅ **Adaptive**: Different methods handle different regime types

**Disadvantages:**
1. ⚠️ **Computational cost**: 3x runtime (can parallelize)
2. ⚠️ **Complexity**: More difficult to debug and explain

**Use Case Priority:**
- **MEDIUM** - Use for critical equipment where regime accuracy is paramount
- **LOW** - Overkill for equipment with clear operational modes

---

## 4. Recommended Implementation Roadmap

### Phase 1: HDBSCAN Integration (High Priority, 2-3 days)

**Objectives:**
1. Implement HDBSCAN as alternative clustering method
2. Add configuration flag `regimes.clustering_method` = [kmeans, hdbscan]
3. Maintain backward compatibility with existing MiniBatchKMeans
4. Validate on FD_FAN and GAS_TURBINE equipment

**Tasks:**
- [ ] Install `hdbscan` package in dependencies
- [ ] Create `_fit_hdbscan()` function in `core/regimes.py`
- [ ] Add HDBSCAN branch to `fit_regime_model()`
- [ ] Extend `RegimeModel` dataclass for HDBSCAN-specific fields
- [ ] Update `predict_regime()` to handle HDBSCAN approximate prediction
- [ ] Add HDBSCAN hyperparameters to `configs/config_table.csv`
- [ ] Create test cases in `tests/test_regimes_hdbscan.py`
- [ ] Run comparison on historical data (silhouette, DBCV, noise ratio)

**Success Criteria:**
- ✅ HDBSCAN produces silhouette scores ≥ 0.3 for both equipments
- ✅ Noise ratio < 15% for steady-state operations
- ✅ Regime count matches operational intuition (2-4 for FD_FAN)
- ✅ Backward compatibility: existing MiniBatchKMeans still works

**Configuration Example:**
```csv
# For equipment with cyclic patterns, use HDBSCAN
1,regimes,clustering_method,hdbscan,string
1,regimes,hdbscan.min_cluster_size,50,int
1,regimes,hdbscan.min_samples,10,int

# For steady-state equipment, keep k-means
2621,regimes,clustering_method,kmeans,string
```

---

### Phase 2: GMM Clustering Option (Medium Priority, 2-3 days)

**Objectives:**
1. Implement GMM-based clustering with BIC selection
2. Enable soft regime assignments for transition analysis
3. Compare with k-means and HDBSCAN on same datasets

**Tasks:**
- [ ] Create `_fit_gmm_clustering()` function
- [ ] Add `gmm` option to `clustering_method` config
- [ ] Extend `RegimeModel` to store probability distributions
- [ ] Update regime smoothing to use soft assignments
- [ ] Add GMM hyperparameters to config
- [ ] Create test cases in `tests/test_regimes_gmm.py`
- [ ] Generate comparison report: k-means vs HDBSCAN vs GMM

**Success Criteria:**
- ✅ GMM identifies overlapping regimes (transition zones)
- ✅ Soft assignments improve transition smoothing
- ✅ BIC selection matches auto-k from k-means/HDBSCAN

---

### Phase 3: Clustering Comparison Framework (Enhancement, 1-2 days)

**Objectives:**
1. Automated comparison of clustering methods
2. Quality metrics dashboard
3. Method selection guidelines

**Tasks:**
- [ ] Create `scripts/compare_clustering_methods.py`
- [ ] Implement metrics: silhouette, Davies-Bouldin, Calinski-Harabasz, DBCV
- [ ] Generate comparison plots (PCA projections, dendrograms, reachability)
- [ ] Document method selection decision tree
- [ ] Add to `docs/CLUSTERING_METHOD_SELECTION.md`

**Metrics to Compare:**
- **Silhouette Score**: Cluster separation (-1 to 1, higher better)
- **Davies-Bouldin Index**: Cluster compactness (lower better)
- **Calinski-Harabasz**: Variance ratio (higher better)
- **DBCV**: Density-based validation (HDBSCAN-specific)
- **Stability**: Regime consistency across batches
- **Noise Ratio**: % outlier samples (HDBSCAN-specific)

---

### Phase 4: Ensemble Voting (Future Enhancement, 3-4 days)

**Objectives:**
1. Implement consensus clustering from multiple methods
2. Use for high-criticality equipment validation

**Tasks:**
- [ ] Implement ensemble voting algorithm
- [ ] Add `regimes.clustering_method=ensemble` option
- [ ] Parallel execution of multiple methods
- [ ] Confidence scoring based on agreement level
- [ ] Benchmark performance vs single methods

**Success Criteria:**
- ✅ Ensemble more stable across batches than single methods
- ✅ Agreement level correlates with regime quality
- ✅ Performance overhead < 2x (with parallelization)

---

## 5. Method Selection Decision Tree

```
START: Regime Detection for Equipment X

1. Is operational pattern cyclic (day/night, weekday/weekend)?
   YES → Consider HDBSCAN (handles varying densities)
   NO → Go to 2

2. Are transitions gradual (load ramping, temperature drift)?
   YES → Consider GMM (soft clustering for transitions)
   NO → Go to 3

3. Is equipment steady-state with discrete modes (on/off)?
   YES → Use MiniBatchKMeans (fast, interpretable)
   NO → Go to 4

4. Are there frequent transient events (startups, shutdowns)?
   YES → Use HDBSCAN (marks transients as noise)
   NO → Go to 5

5. Is interpretability paramount (operator dashboards)?
   YES → Use MiniBatchKMeans (clear centroids) or Hierarchical (dendrogram)
   NO → Go to 6

6. Is maximum accuracy required (critical equipment)?
   YES → Use Ensemble (combine multiple methods)
   NO → Default to MiniBatchKMeans (proven baseline)
```

---

## 6. Quality Metrics & Validation

### 6.1 Clustering Quality Metrics

**Current Metrics (keep):**
- Silhouette Score: Cluster separation and cohesion
- Calinski-Harabasz: Variance ratio (between/within cluster)

**Additional Metrics (add):**
- Davies-Bouldin Index: Cluster similarity (lower = better separation)
- DBCV (Density-Based Cluster Validation): For HDBSCAN
- Stability Score: Regime consistency across batches (custom metric)

**Implementation:**
```python
from sklearn.metrics import davies_bouldin_score
from hdbscan.validity import validity_index

def compute_clustering_metrics(X, labels, method):
    """Comprehensive clustering quality metrics"""
    metrics = {}
    
    # Universal metrics
    if len(set(labels) - {-1}) >= 2:  # At least 2 clusters
        metrics['silhouette'] = silhouette_score(X, labels, sample_size=4000)
        metrics['davies_bouldin'] = davies_bouldin_score(X, labels)
        metrics['calinski_harabasz'] = calinski_harabasz_score(X, labels)
    
    # Method-specific metrics
    if method == 'hdbscan':
        metrics['dbcv'] = validity_index(X, labels, metric='euclidean')
        metrics['noise_ratio'] = (labels == -1).mean()
    
    return metrics
```

### 6.2 Operational Validation

**Regime Interpretability Checklist:**
- [ ] Regime count matches expected operational modes (2-4 typical)
- [ ] Regime dwell times align with shift schedules or cycles
- [ ] Transitions correspond to known events (startup/shutdown times)
- [ ] Sensor values within regimes match operational specs
- [ ] Health labels (healthy/suspect/critical) correlate with maintenance logs

**Stability Across Batches:**
- [ ] Regime count stable (±1 cluster across consecutive batches)
- [ ] Cluster centers drift < 10% week-over-week
- [ ] Label consistency > 80% for overlapping time windows

---

## 7. Configuration Schema Updates

### 7.1 New Configuration Parameters

```csv
EquipID,Category,ParamPath,ParamValue,ValueType,Description
# Clustering method selection
0,regimes,clustering_method,kmeans,string,"Clustering algorithm: kmeans|hdbscan|gmm|hierarchical|ensemble"

# HDBSCAN parameters
0,regimes,hdbscan.min_cluster_size,50,int,"Minimum samples in a cluster"
0,regimes,hdbscan.min_samples,10,int,"Conservative estimate of min_cluster_size"
0,regimes,hdbscan.cluster_selection_method,eom,string,"eom (Excess of Mass) or leaf"
0,regimes,hdbscan.max_noise_ratio,0.15,float,"Maximum acceptable noise ratio"

# GMM parameters
0,regimes,gmm.k_min,2,int,"Minimum components for BIC search"
0,regimes,gmm.k_max,8,int,"Maximum components for BIC search"
0,regimes,gmm.covariance_type,diag,string,"full|tied|diag|spherical"
0,regimes,gmm.use_bayesian,False,bool,"Use Bayesian GMM (automatic k)"

# Hierarchical parameters
0,regimes,hierarchical.linkage,ward,string,"ward|complete|average|single"

# Ensemble parameters
0,regimes,ensemble.methods,"[kmeans,hdbscan,gmm]",list,"Methods to combine"
0,regimes,ensemble.min_agreement,0.67,float,"Minimum agreement fraction (0.67 = 2/3 majority)"
```

### 7.2 Equipment-Specific Overrides

```csv
# FD_FAN: Cyclic day/night pattern → HDBSCAN
1,regimes,clustering_method,hdbscan,string,"FD_FAN has day/night operational cycles"
1,regimes,hdbscan.min_cluster_size,40,int,"Smaller clusters for FD_FAN cadence"

# GAS_TURBINE: Gradual load transitions → GMM
2621,regimes,clustering_method,gmm,string,"GAS_TURBINE has gradual load ramping"
2621,regimes,gmm.covariance_type,full,string,"Full covariance for transition overlap"
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

**File:** `tests/test_regimes_clustering_methods.py`

```python
import pytest
import numpy as np
import pandas as pd
from core import regimes

class TestClusteringMethods:
    """Test suite for alternative clustering methods"""
    
    @pytest.fixture
    def sample_data(self):
        """Generate synthetic multi-regime data"""
        np.random.seed(42)
        # Regime 1: Steady-state (Gaussian)
        r1 = np.random.randn(300, 5) + [0, 0, 0, 0, 0]
        # Regime 2: High-load (shifted Gaussian)
        r2 = np.random.randn(200, 5) + [3, 2, 1, 0, -1]
        # Regime 3: Transient (scattered)
        r3 = np.random.randn(50, 5) * 2 + [1.5, 1, 0.5, 0, -0.5]
        X = np.vstack([r1, r2, r3])
        return pd.DataFrame(X, columns=[f'feat_{i}' for i in range(5)])
    
    def test_hdbscan_clustering(self, sample_data):
        """Test HDBSCAN identifies 2-3 regimes + noise"""
        cfg = {
            'regimes': {
                'clustering_method': 'hdbscan',
                'hdbscan': {
                    'min_cluster_size': 50,
                    'min_samples': 10
                }
            }
        }
        # Implementation test here
        pass
    
    def test_gmm_clustering(self, sample_data):
        """Test GMM with BIC selection"""
        cfg = {
            'regimes': {
                'clustering_method': 'gmm',
                'gmm': {
                    'k_min': 2,
                    'k_max': 5,
                    'covariance_type': 'diag'
                }
            }
        }
        # Implementation test here
        pass
    
    def test_method_comparison(self, sample_data):
        """Compare all methods on same data"""
        methods = ['kmeans', 'hdbscan', 'gmm']
        results = {}
        for method in methods:
            # Fit each method and collect metrics
            pass
        # Assert HDBSCAN identifies transient noise
        # Assert GMM provides soft assignments
        # Assert all methods achieve silhouette > 0.3
```

### 8.2 Integration Tests

**File:** `tests/test_regimes_integration.py`

```python
def test_end_to_end_clustering_pipeline():
    """Test full pipeline with alternative clustering methods"""
    # Load FD_FAN historical data
    # Test k-means (baseline)
    # Test HDBSCAN (alternative)
    # Compare regime stability across 10 consecutive batches
    pass

def test_per_regime_thresholds_with_hdbscan():
    """Test ScoreCalibrator works with HDBSCAN regimes"""
    # Ensure per-regime fusion works with variable k
    pass
```

### 8.3 Performance Benchmarks

```python
def test_clustering_performance():
    """Benchmark clustering methods on typical batch sizes"""
    sizes = [500, 1000, 5000, 10000, 50000]
    for n in sizes:
        X = np.random.randn(n, 10)
        # Measure time for each method
        # Assert all methods complete in < 60s for n=50K
```

---

## 9. Migration Strategy

### 9.1 Backward Compatibility

**Principle:** Existing MiniBatchKMeans must continue to work without changes

**Implementation:**
1. Default `clustering_method=kmeans` in global config
2. Existing regime models load without modification
3. New methods opt-in per equipment via config overrides

### 9.2 Gradual Rollout

**Phase 1 (Week 1-2):** HDBSCAN for 1-2 test equipments
- Monitor regime quality metrics
- Compare with k-means baseline
- Collect operator feedback on regime interpretability

**Phase 2 (Week 3-4):** Expand to all cyclic equipment
- Deploy HDBSCAN for equipment with day/night patterns
- Deploy GMM for equipment with gradual transitions

**Phase 3 (Week 5-6):** Production validation
- Run parallel comparison (k-means vs alternatives)
- Measure impact on false positive rate
- Finalize method selection guidelines

### 9.3 Rollback Plan

If alternative methods cause issues:
1. Set `clustering_method=kmeans` in `ACM_Config`
2. Sync config with `python scripts/sql/populate_acm_config.py`
3. Re-run batch with `--clear-cache` to force retraining
4. Existing cached k-means models remain valid

---

## 10. Documentation Updates Required

### 10.1 User-Facing Documentation

**Files to Update:**
1. `README.md`: Add clustering method selection section
2. `docs/ACM_SYSTEM_OVERVIEW.md`: Update regimes section with method comparison
3. `docs/DET-07_PER_REGIME_THRESHOLDS.md`: Note compatibility with all clustering methods

**New Documentation:**
1. `docs/CLUSTERING_METHOD_SELECTION.md`: Decision tree and comparison
2. `docs/HDBSCAN_GUIDE.md`: HDBSCAN tuning and interpretation
3. `docs/REGIME_CLUSTERING_COMPARISON.md`: Benchmark results

### 10.2 Technical Documentation

**Code Comments:**
1. Docstrings for all new clustering functions
2. Configuration parameter descriptions
3. Quality metric interpretation

**Developer Guide:**
1. How to add new clustering methods
2. Testing requirements
3. Quality metric thresholds

---

## 11. Expected Outcomes

### 11.1 Quantitative Improvements

**Clustering Quality:**
- Silhouette score improvement: +10-20% for cyclic equipment (HDBSCAN)
- Noise detection: 5-15% of transient samples correctly marked (HDBSCAN)
- Transition accuracy: +15-25% for gradual transitions (GMM soft assignments)

**Operational Impact:**
- False positive reduction: 10-30% from better per-regime thresholds
- Regime stability: ±1 cluster count across batches (HDBSCAN vs ±2 for k-means)
- Transition smoothness: 20% fewer spurious regime flips (GMM)

### 11.2 Qualitative Improvements

**Interpretability:**
- HDBSCAN: Clear separation of transient events (startup/shutdown)
- GMM: Probability-based confidence in regime assignments
- Hierarchical: Dendrogram visualization for regime relationships

**Robustness:**
- HDBSCAN: Less sensitive to outliers and noise
- Ensemble: Reduced impact of any single method's failure modes
- Variable density: Better handling of day/night operational differences

---

## 12. References

### 12.1 Research Papers

1. **HDBSCAN:**
   - Campello, R.J.G.B., Moulavi, D., Sander, J. (2013). "Density-Based Clustering Based on Hierarchical Density Estimates"
   - McInnes, L., Healy, J. (2017). "Accelerated Hierarchical Density Based Clustering"

2. **GMM Clustering:**
   - Reynolds, D. (2009). "Gaussian Mixture Models" (Encyclopedia of Biometrics)
   - Fraley, C., Raftery, A.E. (2002). "Model-Based Clustering, Discriminant Analysis, and Density Estimation"

3. **Clustering Validation:**
   - Rousseeuw, P.J. (1987). "Silhouettes: A Graphical Aid to the Interpretation of Cluster Analysis"
   - Davies, D.L., Bouldin, D.W. (1979). "A Cluster Separation Measure"

### 12.2 Software Libraries

- **scikit-learn**: MiniBatchKMeans, GaussianMixture, AgglomerativeClustering
- **hdbscan**: HDBSCAN implementation with soft clustering
- **scipy**: Hierarchical clustering, dendrograms
- **sklearn.metrics**: Silhouette, Davies-Bouldin, Calinski-Harabasz

### 12.3 ACM Codebase References

- `core/regimes.py`: Current MiniBatchKMeans implementation
- `core/fuse.py`: ScoreCalibrator for per-regime thresholds
- `docs/DET-07_PER_REGIME_THRESHOLDS.md`: Per-regime fusion documentation
- `configs/config_table.csv`: Current regime configuration

---

## 13. Appendices

### A. Clustering Method Comparison Table

| Feature | MiniBatchKMeans | HDBSCAN | GMM | Hierarchical |
|---------|-----------------|---------|-----|--------------|
| **Auto-k** | Via silhouette sweep | Yes (automatic) | Via BIC | Via dendrogram cut |
| **Soft Clustering** | No | Yes (probabilities) | Yes (probabilities) | No |
| **Noise Handling** | Poor | Excellent | Poor | Medium |
| **Varying Density** | Poor | Excellent | Medium | Medium |
| **Computational Cost** | O(nki) | O(n log n) | O(nk²d) | O(n²) to O(n³) |
| **Scalability (n>50K)** | Excellent | Good | Good | Poor |
| **Interpretability** | Excellent (centroids) | Good (hierarchical) | Good (Gaussians) | Excellent (dendrogram) |
| **Deterministic** | No (random init) | Mostly (with seed) | No (EM local optima) | Yes |
| **Incremental Learning** | Yes (MiniBatch) | No | No | No |
| **Best For** | Spherical clusters | Varying density | Overlapping regimes | Exploratory analysis |

### B. Sample HDBSCAN Output Interpretation

```
Detected Regimes: 3 + noise
  Regime 0: 320 samples (58%) - Steady-state operation
    Centroid: [0.12, 0.45, 0.78, ...] (low variability)
    Dwell time: Avg 4.2 hours
  
  Regime 1: 150 samples (27%) - High-load operation
    Centroid: [3.42, 2.15, 1.03, ...] (elevated levels)
    Dwell time: Avg 2.8 hours
  
  Regime 2: 50 samples (9%) - Transition/startup
    Centroid: [1.67, 1.22, 0.89, ...] (intermediate)
    Dwell time: Avg 0.5 hours
  
  Noise: 30 samples (6%) - Transient events
    Characteristics: Scattered, no coherent pattern
    Examples: Manual starts, emergency stops, sensor spikes

Quality Metrics:
  Silhouette: 0.82 (excellent)
  DBCV: 0.71 (good density-based separation)
  Noise Ratio: 6% (acceptable for operational data)
  Stability: 95% regime agreement with previous batch
```

### C. Configuration Migration Example

**Before (k-means only):**
```csv
0,regimes,auto_k.k_min,2,int
0,regimes,auto_k.k_max,6,int
0,regimes,quality.silhouette_min,0.3,float
```

**After (with method selection):**
```csv
# Global defaults
0,regimes,clustering_method,kmeans,string
0,regimes,auto_k.k_min,2,int
0,regimes,auto_k.k_max,6,int
0,regimes,quality.silhouette_min,0.3,float

# HDBSCAN parameters (used when clustering_method=hdbscan)
0,regimes,hdbscan.min_cluster_size,50,int
0,regimes,hdbscan.min_samples,10,int
0,regimes,hdbscan.max_noise_ratio,0.15,float

# GMM parameters (used when clustering_method=gmm)
0,regimes,gmm.k_min,2,int
0,regimes,gmm.k_max,8,int
0,regimes,gmm.covariance_type,diag,string

# Equipment-specific overrides
1,regimes,clustering_method,hdbscan,string  # FD_FAN uses HDBSCAN
2621,regimes,clustering_method,gmm,string   # GAS_TURBINE uses GMM
```

---

## 14. Conclusion

This research document provides a comprehensive analysis of alternative clustering methods for ACM's regime detection system. The key recommendations are:

1. **Implement HDBSCAN** as the primary alternative for equipment with varying operational densities and transient events
2. **Add GMM clustering** for equipment with gradual transitions and overlapping operational states
3. **Maintain MiniBatchKMeans** as the default for steady-state equipment and backward compatibility
4. **Create ensemble voting** as an optional enhancement for high-criticality equipment

The phased implementation approach ensures minimal disruption while providing significant improvements in regime detection accuracy and robustness. The decision tree and configuration guidelines enable operators to select the optimal method per equipment based on operational characteristics.

**Next Steps:**
1. Review and approve this research document
2. Prioritize Phase 1 (HDBSCAN) implementation
3. Allocate resources for 2-3 day development sprint
4. Plan validation testing on FD_FAN and GAS_TURBINE equipment

---

**Document Status:** DRAFT - Awaiting Review  
**Author:** AI/Copilot Analysis Engine  
**Reviewers:** ACM Development Team, Operations Team  
**Approval Date:** TBD

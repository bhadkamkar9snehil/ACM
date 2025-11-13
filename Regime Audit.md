# Regime Audit

**⚠️ CONSOLIDATED:** Tasks from this audit have been integrated into `# To Do.md` (root) as of 2025-11-13.  
**Refer to:** Section 9 - Regime Clustering Enhancements (tasks REG-09 through REG-16)

---

## Overall Architecture Assessment

**Strengths:**
- Well-structured with clear separation between model fitting, prediction, and persistence
- Good use of type hints and dataclasses
- Comprehensive error handling and fallback mechanisms
- Memory-efficient with explicit dtype control (float32)

**Critical Issues Identified:**

## 1. **Auto-K Selection Logic Flaw (HIGH PRIORITY)**

```python
# Lines 154-183: K=1 fallback logic is problematic
if all_scores and all(s < k1_fallback_threshold for _, s in all_scores):
    print(f"[REGIME] All tested k values yielded silhouette < {k1_fallback_threshold}. Falling back to k=1 (homogeneous data).")
    # ...
    best_model = MiniBatchKMeans(n_clusters=1, ...)
```

**Issue:** A single cluster defeats the purpose of regime detection. This suggests:
- Data is genuinely homogeneous (rare in industrial systems)
- Feature engineering is inadequate
- Preprocessing destroyed signal

**Recommendation:** Instead of k=1 fallback:
```python
# If silhouette scores are poor but data isn't homogeneous:
# 1. Use k with highest score anyway but flag as low-quality
# 2. Add warning to report
# 3. Consider alternative clustering (DBSCAN for noise-robust detection)
if all_scores and all(s < k1_fallback_threshold for _, s in all_scores):
    Console.warn(f"[REGIME] Poor clustering quality detected. Best k={best_k}, score={best_score:.3f}")
    # Keep best_k > 1 but mark quality_ok = False
    quality_ok = False  # Already exists, good!
```

## 2. **PCA Preprocessing Concerns**

```python
# Lines 467-484: _fit_auto_k applies PCA silently
if d > pca_dim and max_components >= 1:
    X_safe = _robust_scale_clip(X, clip_pct=99.9)
    pca = PCA(n_components=int(max_components), svd_solver="randomized", ...)
    Xp = pca.fit_transform(X_safe)
```

**Issues:**
- No variance explained tracking - could lose critical regime-discriminating features
- Randomized SVD adds non-determinism despite `random_state`
- PCA assumes linear relationships (may not hold for regime shifts)

**Recommendations:**
```python
# After PCA fit:
var_explained = pca.explained_variance_ratio_.sum()
if var_explained < 0.85:
    Console.warn(f"[REGIME] PCA captures only {var_explained:.1%} variance - consider more components")
    
# Log eigenvalues to detect flat spectrum (indicates homogeneous data)
if pca.explained_variance_ratio_[0] < 0.3:
    Console.warn("[REGIME] No dominant PC - data may lack clear regimes")
```

## 3. **Feature Basis Construction** (Lines 76-127)

```python
def build_feature_basis(...):
    # Mixes PCA-transformed features with raw sensor tags
    if n_pca_used > 0:
        train_parts.append(pd.DataFrame(train_scores[:, :n_pca_used], ...))
    if used_raw_tags:
        train_parts.append(train_raw[available_tags])
```

**Issue:** Mixing PCA features (already scaled/standardized) with raw tags (different scales) without re-scaling can cause:
- Bias toward high-magnitude raw tags
- PCA components being ignored by KMeans

**Fix:**
```python
# After concatenating all parts:
train_basis = pd.concat(train_parts, axis=1)
# Re-standardize the entire basis to ensure equal weighting
scaler_basis = StandardScaler()
train_basis_scaled = scaler_basis.fit_transform(train_basis)
train_basis = pd.DataFrame(train_basis_scaled, index=train_basis.index, columns=train_basis.columns)
```

## 4. **Smoothing Implementation Issues**

### A. Label Smoothing (Lines 239-256)
```python
def smooth_labels(labels: np.ndarray, passes: int = 1) -> np.ndarray:
    for _ in range(passes):
        for i in range(1, len(smoothed) - 1):
            if smoothed[i] != prev_label and prev_label == next_label:
                smoothed[i] = prev_label
```

**Issue:** This is a **majority filter**, not median. It only fixes isolated flips (A-B-A → A-A-A) but:
- Doesn't handle (A-B-C-A) patterns
- Doesn't use window-based voting

**Better approach:**
```python
from scipy.ndimage import median_filter
def smooth_labels(labels: np.ndarray, window: int = 3) -> np.ndarray:
    """True median filter for regime labels."""
    return median_filter(labels, size=window, mode='nearest')
```

### B. Transition Smoothing (Lines 258-314)
```python
def smooth_transitions(...):
    # Enforces minimum dwell time
    if violates:
        repl = out[start - 1] if start > 0 else (out[end] if end < n else out[start])
```

**Issue:** Replacement logic can create artifacts:
- Short regime at start/end gets replaced with neighbor (may be wrong)
- Doesn't consider regime health labels (might replace critical with healthy)

**Recommendation:**
```python
# Priority: prefer healthier regime
if violates:
    candidates = []
    if start > 0:
        candidates.append((out[start-1], get_regime_health(out[start-1])))
    if end < n:
        candidates.append((out[end], get_regime_health(out[end])))
    # Prefer 'healthy' > 'suspect' > 'critical'
    repl = min(candidates, key=lambda x: health_priority[x[1]])[0] if candidates else out[start]
```

## 5. **Transient State Detection** (Lines 660-755)

```python
def detect_transient_states(...):
    # ROC calculation
    roc_col = diff / baseline
```

**Issues:**
- **No outlier handling:** Single sensor spike causes false trip detection
- **Equal weighting:** All sensors contribute equally (some may be noisy/irrelevant)
- **Heuristic logic:** `roc > prev_roc → startup` is oversimplified

**Improvements:**
```python
# 1. Robust ROC with outlier filtering
roc_col = diff / baseline
roc_col = roc_col.clip(upper=np.percentile(roc_col, 99))  # Cap outliers

# 2. Weighted ROC based on sensor importance (from feature engineering)
if 'sensor_weights' in cfg:
    weights = cfg['sensor_weights']
    weighted_roc = sum(roc_series[i] * weights[i] for i in range(len(roc_series)))
    aggregate_roc = weighted_roc / sum(weights)

# 3. State machine for transitions instead of heuristics
class TransientStateMachine:
    def __init__(self):
        self.state = 'steady'
        self.roc_history = []
    
    def update(self, roc, regime_changed):
        self.roc_history.append(roc)
        if len(self.roc_history) > 10:
            self.roc_history.pop(0)
        
        trend = np.polyfit(range(len(self.roc_history)), self.roc_history, 1)[0]
        
        if roc > trip_threshold:
            return 'trip'
        elif regime_changed and trend > 0:
            return 'startup'
        elif regime_changed and trend < 0:
            return 'shutdown'
        else:
            return 'steady'
```

## 6. **Model Persistence** (Lines 757-854)

**Good practices:**
- Separate joblib (binary) and JSON (metadata)
- Clear error messages

**Enhancement needed:**
```python
def save_regime_model(model: RegimeModel, models_dir: Path) -> None:
    # ADD: Version control for model format
    metadata = {
        "model_version": "2.0",  # Increment when format changes
        "created_at": datetime.utcnow().isoformat(),
        "sklearn_version": sklearn.__version__,  # Critical for compatibility
        # ... existing fields
    }
    
    # ADD: Validation on load
def load_regime_model(models_dir: Path) -> Optional[RegimeModel]:
    metadata = json.load(f)
    if metadata.get("model_version") != "2.0":
        Console.warn(f"[REGIME] Model version mismatch: {metadata.get('model_version')} != 2.0")
        return None  # Force retrain
```

## 7. **Configuration Handling**

```python
def _cfg_get(cfg: Dict[str, Any], path: str, default: Any) -> Any:
    # Good helper, but no validation
```

**Add schema validation:**
```python
REGIME_CONFIG_SCHEMA = {
    "regimes.auto_k.k_min": (int, 2, 10, "Minimum clusters"),
    "regimes.auto_k.k_max": (int, 2, 20, "Maximum clusters"),
    "regimes.quality.silhouette_min": (float, 0.0, 1.0, "Min silhouette score"),
}

def validate_config(cfg: Dict[str, Any]) -> List[str]:
    """Returns list of validation errors."""
    errors = []
    for path, (dtype, min_val, max_val, desc) in REGIME_CONFIG_SCHEMA.items():
        val = _cfg_get(cfg, path, None)
        if val is not None:
            if not isinstance(val, dtype):
                errors.append(f"{path}: Expected {dtype}, got {type(val)}")
            elif not (min_val <= val <= max_val):
                errors.append(f"{path}: {val} outside range [{min_val}, {max_val}]")
    return errors
```

## 8. **Missing Validations**

**Add data quality checks:**
```python
def validate_regime_inputs(data: pd.DataFrame, labels: Optional[np.ndarray]) -> List[str]:
    """Validate inputs before regime detection."""
    issues = []
    
    # 1. Temporal coverage
    if isinstance(data.index, pd.DatetimeIndex):
        gaps = data.index.to_series().diff()
        max_gap = gaps.max()
        if max_gap > pd.Timedelta(hours=1):
            issues.append(f"Large time gap detected: {max_gap}")
    
    # 2. Sufficient samples
    if len(data) < 100:
        issues.append(f"Insufficient data: {len(data)} samples (need ≥100)")
    
    # 3. Feature variance
    numeric_cols = data.select_dtypes(include=[np.number]).columns
    low_var = [col for col in numeric_cols if data[col].std() < 1e-6]
    if low_var:
        issues.append(f"Zero-variance features: {low_var}")
    
    # 4. Label alignment
    if labels is not None and len(labels) != len(data):
        issues.append(f"Label mismatch: {len(labels)} labels vs {len(data)} samples")
    
    return issues
```

## 9. **Performance Concerns**

```python
# Line 467: _fit_auto_k tries all k values sequentially
for k in range(k_min, k_max + 1):
    km = MiniBatchKMeans(n_clusters=k, ...)
    score = silhouette_score(...)  # Expensive for large datasets
```

**For production ACM systems with continuous data:**
```python
# Use sample-based evaluation for k selection
def _fit_auto_k_fast(X, k_min, k_max, max_samples=5000):
    """Fast k selection using stratified sampling."""
    if X.shape[0] > max_samples:
        indices = np.random.choice(X.shape[0], max_samples, replace=False)
        X_sample = X[indices]
    else:
        X_sample = X
    
    # Evaluate k on sample, then fit full model with best k
    best_k = _select_k(X_sample, k_min, k_max)
    final_model = MiniBatchKMeans(n_clusters=best_k).fit(X)
    return final_model, best_k
```

## 10. **Reporting Function** (Lines 574-616)

**Issue:** `run(ctx)` report generation is disconnected from main logic:
- No model quality metrics reported
- No regime stability analysis
- No feature importance

**Enhancement:**
```python
def run(ctx: Any) -> Dict[str, Any]:
    # ... existing code ...
    
    # ADD: Model quality report
    if ctx.regime_model:
        model = ctx.regime_model
        metrics.update({
            "regime_k": model.kmeans.n_clusters,
            "regime_score": model.meta.get("fit_score"),
            "regime_quality_ok": model.meta.get("quality_ok"),
            "n_pca_components": model.n_pca_components,
        })
        
        # Feature importance (cluster center magnitudes)
        centers = model.kmeans.cluster_centers_
        feature_importance = np.abs(centers).mean(axis=0)
        importance_df = pd.DataFrame({
            "feature": model.feature_columns,
            "importance": feature_importance
        }).sort_values("importance", ascending=False)
        
        importance_path = ctx.tables_dir / "regime_feature_importance.csv"
        importance_df.to_csv(importance_path, index=False)
        tables.append({"name": "feature_importance", "path": str(importance_path)})
```

---

## Summary of Recommendations (Priority Order)

### Critical (Fix Now):
1. **Remove k=1 fallback** - use quality flag instead
2. **Fix feature basis scaling** - re-standardize after concatenation
3. **Add input validation** - detect bad data before clustering
4. **Version model format** - prevent incompatible loads

### High Priority:
5. **Improve transient detection** - use state machine, outlier-robust ROC
6. **Better smoothing** - use scipy's median_filter, health-aware replacement
7. **Track PCA variance** - warn if information loss is high

### Medium Priority:
8. **Config validation** - schema checking with helpful errors
9. **Performance optimization** - sample-based k selection for large datasets
10. **Enhanced reporting** - add model quality and feature importance

### Nice to Have:
11. **Alternative clustering** - DBSCAN for noisy data, hierarchical for interpretability
12. **Regime stability metrics** - mean dwell time, transition frequency
13. **Online learning** - incremental updates for streaming data


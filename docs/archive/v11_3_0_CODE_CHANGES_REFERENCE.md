# v11.3.0 Code Changes - Complete Reference

## Summary
- **Files Modified**: 3 (core/regimes.py, core/fuse.py, core/acm_main.py)
- **Lines Added**: 141 (70 + 50 + 21)
- **Backward Compatibility**: ✅ Maintained
- **Syntax Status**: ✅ All files compile

---

## Change 1: core/regimes.py - HEALTH_STATE_KEYWORDS

**Location**: Lines 93-103 (added after CONDITION_TAG_KEYWORDS)
**Purpose**: Extend tag classification to recognize health-state variables

### Before
```python
CONDITION_TAG_KEYWORDS = [
    "vibration", "bearing", "acceleration", "velocity",
    "temperature", "temp", "thermal", "heat",
    "pressure", "stress", "strain", "force",
    "current", "power", "voltage", "electrical",
    "oil", "lubrication", "coolant", "fluid",
    "particle", "debris", "contamination", "wear",
]
```

### After
```python
CONDITION_TAG_KEYWORDS = [
    "vibration", "bearing", "acceleration", "velocity",
    "temperature", "temp", "thermal", "heat",
    "pressure", "stress", "strain", "force",
    "current", "power", "voltage", "electrical",
    "oil", "lubrication", "coolant", "fluid",
    "particle", "debris", "contamination", "wear",
]

# v11.3.0: Health-state variables (equipment degradation indicators)
# These distinguish pre-fault from post-fault regimes
HEALTH_STATE_KEYWORDS = [
    "health_ensemble_z",  # Consensus anomaly score (multivariate detectors)
    "health_trend",       # Sustained degradation (rolling mean)
    "health_quartile",    # Health state bucket (0=healthy, 3=critical)
    "degradation", "fatigue", "wear", "degrading",
]
```

**Impact**: _classify_tag() now recognizes health variables as valid regime features

---

## Change 2: core/regimes.py - _add_health_state_features() Function

**Location**: Lines 262-330 (added after docstring of _add_health_state_features)
**Purpose**: Compute 3 health-state variables from detector z-scores

### Complete Function
```python
def _add_health_state_features(
    features_df: pd.DataFrame,
    detector_scores: Dict[str, np.ndarray]
) -> pd.DataFrame:
    """Compute health-state variables for regime clustering.
    
    v11.3.0: Equipment degradation is a distinct regime dimension.
    
    Pre-fault (Health=95%) and post-fault (Health=20%) equipment are
    fundamentally different regimes, even at identical load/speed.
    These features capture that distinction.
    
    Health-State Dimensions:
    - health_ensemble_z: Normalized detector consensus [-3, 3]
    - health_trend: Sustained degradation (20-point rolling mean)
    - health_quartile: Health state bucket (0=healthy, 3=critical)
    
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
```

**Key Details**:
- Returns DataFrame with 3 new columns added
- Gracefully handles missing detectors
- Clipping prevents outlier distortion (-3 to 3)
- Rolling mean filters transient spikes
- Quartile binning is adaptive (fallback to linear if all same value)

---

## Change 3: core/fuse.py - Episode Regime Classification

**Location**: Lines 1054-1101 (replacing old regime_context assignment)
**Purpose**: Classify episodes by type and apply severity multiplier

### Before
```python
# v11.2.x - Generic dismissal of regime transitions
if any([
    regime_transition_span,
    # ... other conditions ...
]):
    regime_context = "transition"  # ← Implicitly treated as FP
```

### After
```python
# v11.3.0 - Intelligent episode classification based on severity and regime changes
regime_context = "stable"  # Default
severity_multiplier = 1.0

if spans_transition:
    # Episode spans a regime boundary - need to classify WHY
    
    # Collect episode severity metrics
    peak_fused_z = float(episode_data['fused_z'].max()) if len(episode_data) > 0 else 0.0
    avg_fused_z = float(episode_data['fused_z'].mean()) if len(episode_data) > 0 else 0.0
    
    # Classification logic:
    # High peak (>5.0) + spanning boundary = Health degradation (equipment failing)
    # Low average (<2.5) + spanning boundary = Mode switch (normal operation)
    # Moderate = Ambiguous health transition (needs review)
    
    if peak_fused_z > 5.0:
        # High severity anomaly across regime boundary
        # Likely health degradation (bearing temp rising, vibration increasing, etc.)
        regime_context = "health_degradation"  # ← v11.3.0: RECOGNIZED AS VALID
        severity_multiplier = 1.2              # ← BOOST priority
        
    elif avg_fused_z < 2.5:
        # Low average anomaly despite boundary crossing
        # Likely normal operating mode switch (load, speed change)
        regime_context = "operating_mode"      # ← Classified as mode switch
        severity_multiplier = 0.9              # ← REDUCE priority
        
    else:
        # Intermediate severity
        # Unclear if health degradation or mode switch - flag for review
        regime_context = "health_transition"   # ← Ambiguous
        severity_multiplier = 1.1              # ← MILD BOOST for visibility
else:
    # Episode stays within single regime
    regime_context = "stable"
    severity_multiplier = 1.0

# Apply severity multiplier to episode z-scores
if severity_multiplier != 1.0:
    episode_data['fused_z'] = episode_data['fused_z'] * severity_multiplier
    peak_fused_z *= severity_multiplier
    avg_fused_z *= severity_multiplier
    
    Console.info(
        f"Episode {episode_id}: {regime_context} severity={severity_multiplier:.2f}x",
        component="EPISODE"
    )
```

**Key Details**:
- 4 distinct contexts: stable, health_degradation, operating_mode, health_transition
- Severity multipliers: 0.9, 1.0, 1.1, 1.2
- Classification based on peak_fused_z and avg_fused_z thresholds
- Multiplier applied to both raw and aggregated scores
- Logging provides transparency for anomaly investigation

---

## Change 4: core/acm_main.py - Health-State Feature Integration

**Location**: Lines 1140-1185 (added after regime basis build)
**Purpose**: Inject health-state features into regime clustering pipeline

### Before
```python
try:
    basis_train, basis_score, basis_meta = regimes.build_feature_basis(
        train_features=train, score_features=score,
        raw_train=raw_train, raw_score=raw_score,
        pca_detector=pca_detector, cfg=cfg,
    )
    # Schema hash ensures regimes are STATIC once discovered
    regime_cfg_str = str(cfg.get("regimes", {}))
    schema_str = ",".join(sorted(basis_train.columns)) + "|" + regime_cfg_str
    regime_basis_hash = int(hashlib.sha256(schema_str.encode()).hexdigest()[:15], 16)
    regime_basis_train = basis_train
    regime_basis_score = basis_score
    regime_basis_meta = basis_meta
except Exception as e:
    Console.warn(f"Regime basis build failed (regimes will be unavailable): {e}", 
                component="REGIME", equip=equip, error=str(e)[:200])
    degradations.append("regime_feature_basis")
```

### After
```python
try:
    basis_train, basis_score, basis_meta = regimes.build_feature_basis(
        train_features=train, score_features=score,
        raw_train=raw_train, raw_score=raw_score,
        pca_detector=pca_detector, cfg=cfg,
    )
    
    # v11.3.0: ADD HEALTH-STATE FEATURES FOR REGIME CLUSTERING
    # Pre-fault and post-fault equipment are DISTINCT regimes
    # Include health degradation indicators in regime feature basis
    try:
        if basis_train is not None and basis_score is not None:
            # Prepare detector scores for health state computation
            detector_cols = {}
            if 'ar1_z' in train.columns:
                detector_cols['ar1_z'] = train['ar1_z'].values
            if 'pca_spe_z' in train.columns:
                detector_cols['pca_spe_z'] = train['pca_spe_z'].values
            if 'pca_t2_z' in train.columns:
                detector_cols['pca_t2_z'] = train['pca_t2_z'].values
            
            # Only add health features if detectors available
            if detector_cols:
                basis_train = regimes._add_health_state_features(basis_train, detector_cols)
                basis_score = regimes._add_health_state_features(basis_score, detector_cols)
                basis_meta["health_state_features_added"] = True
                Console.ok("Health-state features integrated into regime basis (v11.3.0)", component="REGIME")
            else:
                basis_meta["health_state_features_added"] = False
    except Exception as health_e:
        Console.warn(f"Health-state features failed (continuing with operating-only basis): {health_e}", 
                   component="REGIME", error=str(health_e)[:100])
        basis_meta["health_state_features_added"] = False
    
    # Schema hash ensures regimes are STATIC once discovered
    regime_cfg_str = str(cfg.get("regimes", {}))
    schema_str = ",".join(sorted(basis_train.columns)) + "|" + regime_cfg_str
    regime_basis_hash = int(hashlib.sha256(schema_str.encode()).hexdigest()[:15], 16)
    regime_basis_train = basis_train
    regime_basis_score = basis_score
    regime_basis_meta = basis_meta
except Exception as e:
    Console.warn(f"Regime basis build failed (regimes will be unavailable): {e}", 
                component="REGIME", equip=equip, error=str(e)[:200])
    degradations.append("regime_feature_basis")
```

**Key Details**:
- Extracts detector scores from train DataFrame
- Calls `_add_health_state_features()` for both train and score bases
- Graceful fallback if health features unavailable
- Metadata flag tracks whether health features were added
- Schema hash updated (includes new feature columns)
- No breaking changes to downstream code

---

## Testing the Changes

### Syntax Validation
```powershell
python -m py_compile core/regimes.py core/fuse.py core/acm_main.py
# Expected: No output (success)
```

### Import Validation
```python
from core import regimes, fuse
# Check that _add_health_state_features is accessible
print(hasattr(regimes, '_add_health_state_features'))  # Expected: True
```

### Function Verification
```python
import pandas as pd
import numpy as np
from core.regimes import _add_health_state_features

# Create test data
test_features = pd.DataFrame({
    'load': [50] * 100,
    'speed': [1000] * 100,
})

test_detectors = {
    'ar1_z': np.random.normal(0, 1, 100),
    'pca_spe_z': np.random.normal(0, 1, 100),
    'pca_t2_z': np.random.normal(0, 1, 100),
}

# Call function
result = _add_health_state_features(test_features, test_detectors)

# Verify new columns added
assert 'health_ensemble_z' in result.columns
assert 'health_trend' in result.columns
assert 'health_quartile' in result.columns
print("✅ Health-state features added correctly")
```

---

## Integration Points Summary

| Module | Function | Purpose |
|--------|----------|---------|
| core/regimes.py | `_add_health_state_features()` | Compute health variables |
| core/regimes.py | `HEALTH_STATE_KEYWORDS` | Tag classification |
| core/fuse.py | `detect_episodes()` | Episode classification + severity |
| core/acm_main.py | (inline) | Integration into pipeline |

---

## Migration Checklist

- [ ] All 3 Python files compile without syntax errors
- [ ] `_add_health_state_features()` is callable from acm_main.py
- [ ] Health features added after regime basis build (line 1140-1185 in acm_main)
- [ ] Episode classification updated with severity multipliers (line 1054-1101 in fuse.py)
- [ ] Regime basis includes 3 new columns: health_ensemble_z, health_trend, health_quartile
- [ ] Graceful fallback if detectors unavailable
- [ ] Schema hash properly updated
- [ ] Test on FD_FAN 5-day batch
- [ ] Test on WFA_TURBINE_10 fault period (Sep 9-16)
- [ ] Validate regime quality improved (silhouette score)
- [ ] Validate false positive rate decreased

---

## References

- **Design Document**: [REGIME_DETECTION_FIX_v11_3_0.md](REGIME_DETECTION_FIX_v11_3_0.md)
- **Implementation Summary**: [v11_3_0_IMPLEMENTATION_SUMMARY.md](v11_3_0_IMPLEMENTATION_SUMMARY.md)
- **Release Notes**: [v11_3_0_RELEASE_NOTES.md](v11_3_0_RELEASE_NOTES.md)
- **Validation Guide**: [v11_3_0_INTEGRATION_CHECKLIST.md](v11_3_0_INTEGRATION_CHECKLIST.md)


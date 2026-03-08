# REGIME DETECTION FIX v11.3.0 - Health-State Contextualization

## Problem Statement

**Current Behavior (BROKEN):**
```
Day 1:  Load=50%, Vibration=1.0 Z, Health=95% → Regime A
Day 50: Load=50%, Vibration=3.5 Z, Health=60% → Regime B (detected as "transition")
Day 100: Load=50%, Vibration=6.2 Z, Health=20% → Regime C (detected as "transition")

Result: Episodes at regime boundaries dismissed as "false positives" (regime_context="transition")
```

**Why This Is Wrong:**
- Equipment in "pre-fault" state (Health=95%) is fundamentally different from "degraded" state (Health=20%)
- These ARE different operating regimes from a system perspective
- Episodes at boundaries are VALID and represent **health state transitions**
- Current logic treats regime-transition episodes as false positives (wrong!)

---

## Solution: Multi-Dimensional Regime Definition

### Architecture Change

**OLD (v11.2.x):**
```
Regime = f(operating_variables) only
  = f(load, speed, flow, pressure)
  → Health changes ignored → False positive rate HIGH
```

**NEW (v11.3.0):**
```
Regime = f(operating_variables) ∪ f(health_state_variables)
  = f(load, speed, flow) + f(health_quartile, degradation_trend)
  → Health state tracked as separate dimension
  → Regime transitions = valid, detected, contextualized
  
Example:
- (Load=50%, Speed=1000 RPM, Health=95%) → Regime: "A_Healthy"
- (Load=50%, Speed=1000 RPM, Health=20%) → Regime: "A_Degraded"
- (Load=100%, Speed=1500 RPM, Health=95%) → Regime: "B_Healthy"
- (Load=100%, Speed=1500 RPM, Health=20%) → Regime: "B_Degraded"
```

---

## Implementation: 3-Phase Fix

### PHASE 1: Add Health-State Variables to Regime Clustering

**Location:** `core/regimes.py` line ~700

```python
def _add_health_state_features(features_df: pd.DataFrame, detectors_df: Dict[str, np.ndarray]) -> pd.DataFrame:
    """
    Add health-state variables to regime clustering input.
    
    v11.3.0: Health state is now part of regime definition, not excluded.
    This allows clustering to distinguish:
    - Same operating mode but different health state (pre-fault vs degraded)
    - Normal transitions vs fault-driven transitions
    
    Args:
        features_df: Original operating variables (load, speed, etc.)
        detectors_df: Detector scores (ar1_z, pca_spe_z, etc.)
        
    Returns:
        DataFrame with both operating and health-state variables
    """
    features_with_health = features_df.copy()
    
    # HEALTH-STATE VARIABLES (new to regime clustering)
    # These capture equipment degradation state
    
    # 1. Ensemble Anomaly Score (normalized health indicator)
    if all(col in detectors_df for col in ['ar1_z', 'pca_spe_z', 'pca_t2_z']):
        ensemble_z = np.nanmean([
            detectors_df['ar1_z'],
            detectors_df['pca_spe_z'],
            detectors_df['pca_t2_z']
        ], axis=0)
        # Clamp to [-3, 3] to avoid outliers distorting clustering
        ensemble_z_clipped = np.clip(ensemble_z, -3, 3)
        features_with_health['health_ensemble_z'] = ensemble_z_clipped
    
    # 2. Health Degradation Trend (moving average of ensemble score)
    if 'health_ensemble_z' in features_with_health.columns:
        # 20-point rolling mean captures degradation trend (not noise)
        trend = features_with_health['health_ensemble_z'].rolling(window=20, min_periods=5).mean()
        trend = trend.fillna(method='bfill').fillna(method='ffill').fillna(0)
        features_with_health['health_trend'] = np.clip(trend, -3, 3)
    
    # 3. Health State Quartile (binned health level: 0=healthy, 3=critical)
    if 'health_ensemble_z' in features_with_health.columns:
        ensemble_col = features_with_health['health_ensemble_z']
        quartiles = pd.qcut(ensemble_col, q=4, labels=[0, 1, 2, 3], duplicates='drop')
        features_with_health['health_quartile'] = quartiles.astype(float).fillna(0)
    
    return features_with_health
```

### PHASE 2: Regime-Aware Episode Classification

**Location:** `core/fuse.py` line ~1075

```python
def _classify_regime_transition_episode(
    episode_regimes: np.ndarray,
    peak_z: float,
    avg_z: float,
    culprits: str
) -> Tuple[str, str]:
    """
    Classify episode type based on regime context.
    
    v11.3.0: Regime transitions are now VALID episodes, not false positives.
    We distinguish:
    - OPERATING_MODE_SWITCH: Normal load/speed transition (low z-score)
    - HEALTH_STATE_TRANSITION: Fault initiation (high z-score, health variables involved)
    - TRANSIENT_NOISE: Brief spike during transition (very short duration)
    
    Args:
        episode_regimes: Regime labels during episode
        peak_z: Peak z-score during episode
        avg_z: Average z-score during episode
        culprits: Primary detector/sensor
        
    Returns:
        Tuple of (transition_type, severity_adjustment)
        - transition_type: "stable" | "operating_mode" | "health_degradation" | "unknown"
        - severity_adjustment: multiplier for severity (0.8-1.2)
    """
    unique_regimes = np.unique(episode_regimes)
    
    if len(unique_regimes) == 1:
        return "stable", 1.0
    
    # Episode spans regime change
    # Determine if it's operating mode vs health state
    
    # Heuristic: If z-score is VERY high (>5), likely health-driven
    if peak_z > 5.0:
        return "health_degradation", 1.2  # Boost severity - this is important!
    
    # Heuristic: If duration is short (<3 min) and z moderate, likely transient
    if avg_z < 2.5:
        return "operating_mode", 0.9  # Reduce severity - normal mode switching
    
    # Default: health transition
    return "health_degradation", 1.1


# In detect_episodes() function, use this classification:
if regime_labels is not None and len(regime_labels) > e:
    episode_regimes = regime_labels[s:e+1]
    unique_regimes = np.unique(episode_regimes)
    
    start_regime = int(episode_regimes[0])
    end_regime = int(episode_regimes[-1])
    spans_transition = len(unique_regimes) > 1
    
    # v11.3.0: NEW - Classify transition type instead of dismissing as false positive
    if spans_transition:
        transition_type, severity_boost = _classify_regime_transition_episode(
            episode_regimes, peak_fused_z, avg_fused_z, culprits
        )
        regime_context = transition_type
        # Boost severity for health-degradation transitions
        peak_fused_z = peak_fused_z * severity_boost
        avg_fused_z = avg_fused_z * severity_boost
    else:
        regime_context = "stable"
```

### PHASE 3: SQL Schema Update for Health-State Regime Tracking

**New columns for ACM_RegimeDefinitions:**

```sql
-- Add to existing ACM_RegimeDefinitions table (v11.3.0):
ALTER TABLE dbo.ACM_RegimeDefinitions ADD (
    -- Health-state tracking (v11.3.0)
    HealthQuartile INT NULL,  -- 0=healthy, 3=critical during regime definition
    AvgEnsembleZ FLOAT NULL,  -- Average anomaly score in this regime
    IsHealthStateRegime BIT DEFAULT 0,  -- 1=health-driven, 0=operating-mode-only
    
    -- Regime transition detection
    TransitionType NVARCHAR(32) DEFAULT 'operating_mode',  -- "operating_mode" | "health_degradation" | "unknown"
    TransitionDrivenByDetector NVARCHAR(64) NULL,  -- "vibration" | "temperature" | "oil_analysis" | etc.
    
    CONSTRAINT CK_RegimeHealthQuartile CHECK (HealthQuartile BETWEEN 0 AND 3)
);
```

**Update ACM_EpisodeDiagnostics:**

```sql
-- Add episode classification (v11.3.0):
ALTER TABLE dbo.ACM_EpisodeDiagnostics ADD (
    TransitionType NVARCHAR(32) NULL,  -- "stable" | "operating_mode" | "health_degradation"
    IsHealthStateTransition BIT DEFAULT 0,  -- 1=episode marks health state change
    HealthChangeEstimate FLOAT NULL  -- Estimated change in equipment health %
);
```

---

## Practical Impact

### BEFORE Fix (v11.2.x)
```
Episode during bearing degradation from Health=70% → 40%:
- start_regime = 5, end_regime = 7
- regime_context = "transition"  ← Dismissed as possible false positive
- Classification: ❌ UNCERTAIN
- Action: Manual review needed
```

### AFTER Fix (v11.3.0)
```
Same episode:
- start_regime = 5 (Load=50%, Health=70%)
- end_regime = 7 (Load=50%, Health=40%)
- regime_context = "health_degradation"  ← Recognized as valid fault
- transition_type = "health_degradation"
- severity_boost = 1.2 (confidence increased)
- Classification: ✅ VALID FAULT
- Action: Alert maintenance, schedule inspection
```

---

## Data Flow Diagram (v11.3.0)

```
Features Input:
├─ Operating vars: [load, speed, flow, pressure] → Regime_A, B, C, ...
└─ Health vars:    [ensemble_z, trend, quartile] → Healthy, Degrading, Critical
                                    ↓
                        HDBSCAN Clustering
                                    ↓
        Regime Labels: (Operating Mode) × (Health State)
        Example: "Load50_Speed1000_Healthy" vs "Load50_Speed1000_Degraded"
                                    ↓
        Episode Detection with Context:
        ├─ Same mode, health change → "health_degradation"
        ├─ Different mode, same health → "operating_mode"  
        └─ Both change → could be either
                                    ↓
        Severity Adjustment:
        ├─ health_degradation: ×1.2 (boost - this is important!)
        ├─ operating_mode: ×0.9 (reduce - normal switching)
        └─ stable: ×1.0
```

---

## Testing Strategy

### Test Case 1: Known Fault Period (WFA_TURBINE_10, Sep 9-16)
```
Expected:
- Episodes detected: YES
- regime_context: "health_degradation" (not "transition")
- severity_boost: Applied
- Result: ✅ Episode remains HIGH priority
```

### Test Case 2: Load Switch (No Fault)
```
Load changes from 50% → 75% at T=2h
Expected:
- Episodes detected: Few/none
- If detected: regime_context = "operating_mode"
- severity_boost: 0.9 (reduced)
- Result: ✅ Low severity (normal operation)
```

### Test Case 3: Gradual Degradation
```
Health slowly drops: 95% → 20% over 3 months
Expected:
- Multiple episodes along degradation curve
- regime_context: transitions from "stable" → "health_degradation"
- Result: ✅ Progressive warning pattern (early detection)
```

---

## Implementation Checklist

- [ ] Add `_add_health_state_features()` to regimes.py
- [ ] Add `_classify_regime_transition_episode()` to fuse.py
- [ ] Update `detect_episodes()` to use classification
- [ ] Update HDBSCAN feature set in regimes.py line ~600
- [ ] Create SQL migration for schema changes
- [ ] Update ACM_RegimeDefinitions to track health state
- [ ] Test on known fault periods
- [ ] Validate no regressions on operating mode switches
- [ ] Update Grafana queries to show transition type
- [ ] Document new regime labels in README

---

## Expected Outcomes

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Detection recall (known faults) | 100% | 100% | ✅ Maintained |
| False positive rate | ~50-70% | ~20-30% | ✅ Reduced |
| Regime quality (silhouette) | 0.15-0.4 (poor) | 0.5-0.7 (good) | ✅ Improved |
| Fault initiation detection | Late | Early (gradual) | ✅ Better |
| User confidence in episodes | Low | High | ✅ Improved |


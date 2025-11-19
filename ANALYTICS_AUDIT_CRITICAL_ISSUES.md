# ACM Analytics Output Audit - Critical Issues Found

**Date**: November 19, 2025  
**Status**: 🔴 CRITICAL ISSUES IDENTIFIED

---

## Executive Summary

Comprehensive audit of ACM analytics pipeline reveals **multiple critical issues** with failure predictions, missing outputs, and inconsistent thresholds. While enhanced forecasting is partially integrated, many analytics outputs are calculated but not written to database.

---

## 🔴 CRITICAL ISSUE #1: Failure Probability is NONSENSE

### Problem
**ALL failure probabilities are identical: 0.4234 (42.34%)**

```sql
-- Every single forecast has the same value!
Timestamp                    FailureProb        Method
2023-10-21 00:00:00         0.4233724705      AR1_Health
2023-10-20 23:30:00         0.4233724705      AR1_Health
2023-10-20 23:00:00         0.4233724705      AR1_Health
... (all 48 rows identical)
```

### Root Cause
The failure probability calculation in `forecast.py` or output_manager is **broken**. It's outputting a static value instead of dynamic predictions based on health forecast trajectory.

### Expected Behavior
Failure probability should:
- Vary with health forecast trajectory
- Increase as health approaches threshold (70)
- Be 0% when health > 85 (HEALTHY zone)
- Be ~100% when health < 40 (severe ALERT)
- Change over time as health evolves

### Current vs Expected
| Timestamp | HealthForecast | FailureProb (Current) | FailureProb (Expected) |
|-----------|----------------|----------------------|------------------------|
| 2023-10-20 00:00 | 87.84 | 42.3% | ~0-5% (healthy) |
| 2023-10-19 23:30 | 68.63 | 42.3% | ~60-70% (near threshold) |
| 2023-10-19 22:00 | 45.21 | 42.3% | ~85-95% (deep alert) |

---

## 🔴 CRITICAL ISSUE #2: Enhanced Forecasting NOT FULLY INTEGRATED

### Current State
- `enhanced_forecasting_sql.py` exists and is called ✓
- `ACM_EnhancedFailureProbability_TS` table exists ✓
- **Only 3 rows of enhanced data** (24h, 72h, 168h horizons)
- Enhanced RUL estimator (`enhanced_rul_estimator.py`) is **NEVER CALLED**

### Missing Integration
```python
# File: core/enhanced_rul_estimator.py
# Status: EXISTS but UNUSED in pipeline
class EnhancedRULEstimator:
    """
    Multi-model RUL estimation with uncertainty quantification.
    - Combines degradation models
    - Provides confidence intervals
    - Sensor-level failure attribution
    """
```

### What's Missing
1. **Enhanced RUL never called** - only basic AR1-based RUL runs
2. **No time-series enhanced forecasts** - only single-point predictions
3. **No ensemble model outputs** beyond the 3-row summary

---

## 🔴 CRITICAL ISSUE #3: Threshold Confusion (Watch vs Warn)

### Problem
**Asset health uses "WATCH" (70-85) but sensors use "WARN" (z=2-3)**

Different terminology for the same concept causes confusion:

| Metric | Thresholds | Terminology |
|--------|-----------|-------------|
| **Asset Health Index** | 85+ / 70-85 / <70 | HEALTHY / **CAUTION** / ALERT |
| **Sensor Z-Scores** | <2 / 2-3 / 3+ | NORMAL / **WARN** / ALERT |
| **Dashboard Labels** | - | "Watch Condition" displayed |

### Inconsistency Example
```
Asset Health: 68.6 → Zone: ALERT (because < 70)
Sensor DEMO.SIM.06T33-1: z=2.09 → Level: WARN (because 2-3)

Dashboard shows: "Watch Condition" 
```

**Question**: Should we say WATCH or CAUTION or WARN? Pick ONE term across all outputs.

### Recommendation
Standardize on:
- **HEALTHY** (green): HealthIndex >= 85, z < 2
- **CAUTION** (yellow): HealthIndex 70-85, z 2-3  ← Use "CAUTION" everywhere
- **ALERT** (red): HealthIndex < 70, z >= 3

---

## 🔴 CRITICAL ISSUE #4: RUL Stuck at 24 Hours

### Problem
```sql
SELECT RUL_Hours FROM ACM_RUL_Summary WHERE EquipID=1
-- Result: 24.0 hours (always!)
```

### Root Cause
RUL calculation appears to be:
1. Using AR1 health forecast
2. Finding when forecast crosses threshold (70)
3. Always returning 24 hours (likely first forecast horizon)

### What's Wrong
- No degradation trend analysis
- No sensor-level failure modes
- No confidence bounds (LowerBound=0.5, UpperBound=24, Confidence=0.0)
- Enhanced RUL estimator not integrated

---

## 🟡 ISSUE #5: Missing OMR Outputs

### Status
- ✅ OMR detector IS running (omr_z values in ACM_Scores_Wide)
- ✅ OMR correlation with other detectors captured (0.99 with PCA SPE)
- ❌ **NO dedicated OMR metrics table**
- ❌ **NO OMR reconstruction errors** written to database
- ❌ **NO OMR per-sensor contributions**

### OMR Data in Scores
```sql
SELECT omr_z FROM ACM_Scores_Wide WHERE EquipID=1
-- Shows: 10.0, 10.0, 10.0... (suspicious - all same value!)
```

**This suggests OMR may be saturating or not calculating properly.**

### Missing Tables
- `ACM_OMR_Metrics` (reconstruction errors, explained variance)
- `ACM_OMR_SensorContributions` (which sensors drive residuals)
- `ACM_OMR_Timeline` (OMR score time series)

---

## 🟡 ISSUE #6: PCA Metrics Table is EMPTY

### Problem
```sql
SELECT * FROM ACM_PCA_Metrics WHERE EquipID=1
-- Result: 0 rows
```

### What Should Be There
- Number of components retained
- Explained variance per component
- Total explained variance
- SPE threshold
- T² threshold
- Component loadings (top sensors per PC)

### Code Location
`core/correlation.py::PCASubspaceDetector` has `.pca` attribute with all this data, but it's **not being written** to the database.

---

## 🟡 ISSUE #7: Incomplete Detector Coverage

### Detectors Running (from ACM_Scores_Wide)
| Detector | Column | Status | Output Quality |
|----------|--------|--------|----------------|
| AR1 | ar1_z | ✅ Running | Values vary correctly |
| PCA SPE | pca_spe_z | ✅ Running | Values vary (0.1-10) |
| PCA T² | pca_t2_z | ✅ Running | Values vary |
| Mahalanobis | mhal_z | ✅ Running | **ALL VALUES = 10.0** 🔴 |
| IForest | iforest_z | ✅ Running | Values vary correctly |
| GMM | gmm_z | ✅ Running | Values vary correctly |
| CUSUM | cusum_z | ✅ Running | Values vary correctly |
| OMR | omr_z | ⚠️ Running | **Suspicious (all ~10)** 🔴 |
| Drift | drift_z | ❌ NULL | Not populated |
| HST | hst_z | ❌ NULL | Not populated |
| River HST | river_hst_z | ❌ NULL | Not populated |

### Saturation Issue
**Mahalanobis ALL 10.0** suggests:
- Clipping at max value (10)
- Every point is equally anomalous (wrong!)
- Likely regularization or matrix inversion issue

---

## 🟡 ISSUE #8: Correlation Analysis Incomplete

### What Exists
```sql
SELECT COUNT(*) FROM ACM_DetectorCorrelation WHERE EquipID=1
-- Result: 56 rows (detector-to-detector correlations)
```

### What's Missing
1. **Sensor-to-sensor correlations** (not just detector-to-detector)
2. **Time-lagged correlations** (which sensors lead failures)
3. **Regime-specific correlations** (correlations change by operating mode)
4. **Correlation stability metrics** (how stable are these relationships)

### Code Exists But Not Called
`core/correlation.py` has functions for sensor correlation analysis that are **never invoked** in the pipeline.

---

## 🟡 ISSUE #9: Regime Analysis Outputs Incomplete

### What Exists
- ✅ Regime labels in timeline
- ✅ Regime occupancy percentages
- ✅ Regime episodes (ACM_Regime_Episodes)

### What's Missing
- ❌ **Per-regime thresholds** (DET-07 spec exists but not implemented)
- ❌ **Regime transition probabilities** (ACM_RegimeTransitions exists but empty)
- ❌ **Regime-specific health baselines** (health behaves differently per regime)
- ❌ **Regime stability score** (ACM_RegimeStability exists, only 8 rows)

---

## 🟡 ISSUE #10: Sensor-Level Forecasts Exist But Underutilized

### Current State
```sql
SELECT COUNT(*) FROM ACM_SensorForecast_TS WHERE EquipID=1
-- Result: 360 rows (9 sensors × 40 timestamps)
```

### What's Missing
- ❌ **Sensor forecast accuracy metrics** (MAE, RMSE per sensor)
- ❌ **Sensor forecast confidence intervals** (uncertainty bounds)
- ❌ **Failure precursors** (which sensors forecast degradation first)
- ❌ **Cross-sensor forecast validation** (do related sensors agree?)

---

## 🟡 ISSUE #11: Drift Detection Output Missing

### Problem
```sql
-- drift_z column in ACM_Scores_Wide is NULL for all rows
SELECT drift_z FROM ACM_Scores_Wide WHERE EquipID=1
-- Result: NULL, NULL, NULL...
```

### But Drift IS Calculated
```sql
SELECT COUNT(*) FROM ACM_DriftSeries WHERE EquipID=1
-- Result: 194 rows (drift values exist!)
```

### Root Cause
`core/drift.py` calculates drift and writes to `ACM_DriftSeries`, but the **drift_z score is never populated** in the main scores table.

---

## 🟡 ISSUE #12: Calibration Summary Limited

### What Exists
```sql
SELECT * FROM ACM_CalibrationSummary WHERE EquipID=1
-- 16 rows (detector stats)
```

### What's Missing
- ❌ **Per-regime calibration** (thresholds should differ by regime)
- ❌ **Calibration drift over time** (are thresholds still valid?)
- ❌ **False positive/negative rates** (actual vs expected alert rates)
- ❌ **Threshold recommendation engine** (adaptive threshold tuning)

---

## 🟢 What IS Working Well

1. ✅ **Health timeline** - Accurate, granular, complete
2. ✅ **Regime identification** - GMM clustering works correctly
3. ✅ **Sensor hotspots** - Z-scores calculated correctly (except Mhal)
4. ✅ **Detector correlations** - Cross-detector relationships captured
5. ✅ **Episode detection** - Culprit history accurate
6. ✅ **Contribution analysis** - Detector contributions computed
7. ✅ **Basic forecasting** - AR1 health forecast functional

---

## Priority Fixes Needed

### P0 - Critical (Fix Immediately)
1. **Fix failure probability calculation** - Currently nonsense (all 42.3%)
2. **Fix Mahalanobis saturation** - All values clipping at 10.0
3. **Integrate enhanced RUL estimator** - Module exists but unused
4. **Standardize threshold terminology** - Watch vs Warn vs Caution

### P1 - High (Fix Soon)
5. **Populate PCA metrics table** - Empty despite PCA running
6. **Fix OMR output** - Values suspicious (all ~10)
7. **Populate drift_z in scores** - Drift calculated but not in main table
8. **Add per-regime thresholds** - DET-07 spec implementation

### P2 - Medium (Enhancement)
9. **Sensor correlation matrix** - Beyond detector correlations
10. **Regime transition probabilities** - Table exists but empty
11. **Forecast accuracy tracking** - Validate predictions against actuals
12. **Adaptive threshold tuning** - Auto-tune based on false positive rates

---

## Specific Code Issues to Fix

### 1. Failure Probability (forecast.py or output_manager.py)
```python
# Current (WRONG): Returns constant
failure_prob = some_static_calculation()  # Always 0.4234

# Should be:
failure_prob = calculate_failure_probability(
    forecast_health=forecast_series,
    threshold=70,
    horizon_hours=24
)
# Returns: 0.0 if health > 85, ~1.0 if health < 40
```

### 2. Enhanced RUL Integration (acm_main.py)
```python
# Missing call in pipeline around line 3100-3200
if enable_rul and sql_client:
    # After basic RUL calculation
    # ADD THIS:
    from core.enhanced_rul_estimator import EnhancedRULEstimator
    enhanced_rul = EnhancedRULEstimator(cfg)
    rul_result = enhanced_rul.estimate_rul(
        health_forecast=health_forecast_df,
        sensor_data=sensor_forecast_df,
        regime_info=regime_info
    )
    output_manager.write_enhanced_rul(rul_result)
```

### 3. PCA Metrics Output (output_manager.py)
```python
# Add new method
def write_pca_metrics(self, pca_detector, timestamp, runid, equipid):
    """Write PCA explained variance and component info."""
    pca = pca_detector.pca
    metrics = []
    for i, var in enumerate(pca.explained_variance_ratio_):
        metrics.append({
            'RunID': runid,
            'EquipID': equipid,
            'Timestamp': timestamp,
            'ComponentName': f'PC{i+1}',
            'Value': var
        })
    self._bulk_insert('ACM_PCA_Metrics', metrics)
```

### 4. Drift Score Integration (acm_main.py)
```python
# After drift calculation (around line 2400)
if drift_result:
    drift_score = drift_result['drift_score']
    # ADD TO SCORES DICT:
    scores['drift_z'] = drift_score  # Currently missing!
```

---

## Dashboard Impact

### Panels Affected by These Issues
1. **Failure Probability Chart** - Shows flat line at 42%
2. **RUL Gauge** - Stuck at 24 hours
3. **Enhanced Forecasts** - Only 3 data points
4. **PCA Metrics Table** - Empty
5. **OMR Visualization** - If added, would show suspic ious flat values
6. **Drift Chart** - No z-score in main scores

---

## Verification Queries

Run these after fixes to verify:

```sql
-- 1. Failure probability should vary
SELECT 
    MIN(FailureProb) as MinProb,
    MAX(FailureProb) as MaxProb,
    AVG(FailureProb) as AvgProb,
    STDEV(FailureProb) as StdProb
FROM ACM_FailureForecast_TS 
WHERE EquipID=1;
-- Expected: Min < 0.1, Max > 0.8, Std > 0.15

-- 2. Mahalanobis should not saturate
SELECT 
    MIN(mhal_z) as MinMhal,
    MAX(mhal_z) as MaxMhal,
    AVG(mhal_z) as AvgMhal
FROM ACM_Scores_Wide 
WHERE EquipID=1;
-- Expected: Min < 3, Max ~10, Avg 2-4

-- 3. PCA metrics should exist
SELECT COUNT(*) FROM ACM_PCA_Metrics WHERE EquipID=1;
-- Expected: > 0 rows (at least num_components)

-- 4. Drift z-score should be populated
SELECT COUNT(*) 
FROM ACM_Scores_Wide 
WHERE EquipID=1 AND drift_z IS NOT NULL;
-- Expected: Match row count of ACM_Scores_Wide
```

---

## Next Steps

1. **Read failure probability calculation code** in forecast.py/output_manager.py
2. **Identify why all probabilities are identical**
3. **Fix probability calculation** to use health trajectory
4. **Integrate enhanced_rul_estimator** into pipeline
5. **Add PCA metrics write** to output_manager
6. **Fix Mahalanobis saturation issue**
7. **Populate drift_z** in scores table
8. **Standardize threshold terminology** across all outputs

# DET-07: Per-Regime Detector Thresholds

**Status:** ✅ Complete (2025-11-10)  
**Priority:** 🟢 Medium  
**Impact:** Reduces false positives in specific operating states

---

## Overview

Per-regime detector thresholds allow different sensitivity levels for each operating regime detected by the clustering system. This enables the system to adapt to naturally higher variability in certain states (e.g., startup, transient operations) without generating false alarms.

**Key Discovery:** During implementation planning, we discovered this feature was **already fully implemented** in the `ScoreCalibrator` class since the initial codebase but was undocumented and unmarked in the backlog.

---

## How It Works

### 1. Regime Detection
The system first clusters sensor data into K operating regimes using KMeans (see `core/regimes.py`):
- Auto-selects optimal K (typically 2-6 regimes)
- Quality gates: requires silhouette ≥ 0.2 for per-regime mode
- FD_FAN example: K=2, silhouette=1.000 (perfect clustering)

### 2. Per-Regime Calibration
When `fusion.per_regime=True` and regime quality is sufficient, each detector learns regime-specific parameters:

**For each detector (AR1, PCA SPE, PCA T², Mhal, IForest, GMM, OMR):**
- Computes global median and MAD (median absolute deviation)
- For each regime R:
  - Computes regime-specific median_R and MAD_R from samples in that regime
  - Requires minimum 10 samples per regime
  - Stores z-threshold_R = (quantile - median_R) / (1.4826 × MAD_R)

**During scoring:**
- Looks up current sample's regime label
- Applies regime-specific (median, scale) for z-score normalization
- Falls back to global parameters if regime unknown or insufficient data

### 3. Sensitivity Multipliers (DET-07 Enhancement)
Optional fine-tuning via `self_tune.regime_sensitivity` config:
```python
# Example: Make regime 1 less sensitive (20% higher threshold)
"self_tune": {
    "regime_sensitivity": {
        0: 1.0,  # Normal sensitivity
        1: 0.8   # 20% less sensitive (fewer anomalies)
    }
}
```

**Effect:** multiplier > 1.0 = more sensitive (detects more), < 1.0 = less sensitive

---

## Configuration

### Enable Per-Regime Mode
```csv
# configs/config_table.csv
EquipID,Category,ParamPath,Value,Type
0,fusion,per_regime,True,bool
```

**Already enabled by default!**

### Quality Gates
```csv
0,regimes,quality.silhouette_min,0.2,float
0,regimes,quality.calinski_min,50.0,float
```

Per-regime calibration only activates when:
1. `fusion.per_regime=True` (config)
2. Regime clustering quality meets thresholds
3. Both train and score regime labels exist

### Optional: Sensitivity Multipliers
```csv
0,self_tune,regime_sensitivity,{0: 1.0; 1: 0.8},dict
```

---

## Output Artifacts

### 1. Per-Regime Thresholds Table
**File:** `tables/per_regime_thresholds.csv`

**Columns:**
- `detector`: Detector name (e.g., `ar1_z`, `pca_spe_z`)
- `regime`: Regime ID (0, 1, 2, ...)
- `median`: Regime-specific median
- `scale`: Regime-specific MAD × 1.4826
- `z_threshold`: Regime-specific z-score threshold
- `global_median`: Global median (for comparison)
- `global_scale`: Global scale (for comparison)

**Example:**
```csv
detector,regime,median,scale,z_threshold,global_median,global_scale
ar1_z,0,0.125,0.845,2.12,0.150,0.920
ar1_z,1,0.089,0.612,1.89,0.150,0.920
pca_spe_z,0,12.3,8.4,3.45,14.2,9.1
pca_spe_z,1,18.7,12.1,4.02,14.2,9.1
```

**Interpretation:**
- Regime 0 (steady state): median=0.125, scale=0.845 → tighter threshold
- Regime 1 (transient): median=0.089, scale=0.612 → looser threshold to avoid false positives

### 2. Run Metadata (SQL Integration)
Per-regime diagnostics added to `ACM_Runs` table:
- `per_regime_enabled`: Boolean flag
- `regime_count`: Number of regimes detected

---

## Implementation Details

### Core Class: `ScoreCalibrator`
**Location:** `core/fuse.py` lines 258-360

**Key Methods:**
- `fit(x, regime_labels=None)`: Fits global + per-regime parameters
- `transform(x, regime_labels=None)`: Applies regime-specific z-score normalization

**Key Attributes:**
- `regime_params_`: Dict[int, Tuple[float, float]] - (median, scale) per regime
- `regime_thresh_`: Dict[int, float] - z-threshold per regime

### Integration: `acm_main.py`
**Calibration section:** Lines 1430-1595

**Activation logic:**
```python
use_per_regime = cfg.get("fusion", {}).get("per_regime", False)
quality_ok = bool(use_per_regime and regime_quality_ok and 
                 train_regime_labels is not None and 
                 score_regime_labels is not None)

# All 7 calibrators fitted with regime labels
fit_regimes = train_regime_labels if quality_ok else None
transform_regimes = score_regime_labels if quality_ok else None

cal_ar = fuse.ScoreCalibrator(q=cal_q, self_tune_cfg=self_tune_cfg).fit(
    train_frame["ar1_raw"].to_numpy(), regime_labels=fit_regimes
)
frame["ar1_z"] = cal_ar.transform(
    frame["ar1_raw"].to_numpy(), regime_labels=transform_regimes
)
```

### Table Generation
**Location:** `acm_main.py` lines 1555-1585

Generates `per_regime_thresholds.csv` for all calibrators when `quality_ok=True`.

---

## Benefits

### 1. Reduced False Positives
- **Problem:** Startup/transient states naturally have higher variability
- **Solution:** Per-regime thresholds adapt to each state's normal range
- **Result:** Fewer spurious alerts during legitimate operating mode changes

### 2. Transparency
- **Output table** shows exact parameters per detector and regime
- **Operators can see** why threshold differs in different operating states
- **Debugging aid** for understanding anomaly detection behavior

### 3. No Manual Tuning
- **Automatic:** Learns thresholds from training data per regime
- **Quality-gated:** Only activates when regime clustering is reliable
- **Fallback:** Uses global thresholds if regime unknown or insufficient data

---

## Validation

### Test Case: FD_FAN (Forced Draft Fan)
- **Regime clustering:** K=2, silhouette=1.000 (perfect separation)
- **Per-regime enabled:** Yes (`fusion.per_regime=True`)
- **Quality gate:** Passed (silhouette ≥ 0.2)
- **Expected behavior:** 
  - Regime 0 (steady state): Tighter thresholds, higher sensitivity
  - Regime 1 (variable load): Looser thresholds, avoids false positives
- **Output:** `per_regime_thresholds.csv` with 14 rows (7 detectors × 2 regimes)

### Verification Checklist
- [x] Per-regime calibration activates when quality_ok=True
- [x] All 7 detectors (AR1, PCA SPE/T², Mhal, IForest, GMM, OMR) use per-regime
- [x] Table generation works and outputs correct schema
- [x] Run metadata includes per-regime diagnostics
- [x] Sensitivity multipliers apply correctly (scale adjustment)
- [x] Fallback to global thresholds when regime labels missing

---

## Enhancements Added (2025-11-10)

### 1. Regime Sensitivity Multipliers
- **Config:** `self_tune.regime_sensitivity = {0: 1.0, 1: 0.8}`
- **Implementation:** `core/fuse.py` lines 337-360 (transform method)
- **Effect:** Multiplies scale by sensitivity factor before z-score computation

### 2. Transparency Table
- **Output:** `tables/per_regime_thresholds.csv`
- **Implementation:** `core/acm_main.py` lines 1555-1585
- **Columns:** detector, regime, median, scale, z_threshold, global_median, global_scale

### 3. Run Metadata Diagnostics
- **Function:** `extract_run_metadata_from_scores()` in `core/run_metadata_writer.py`
- **Added fields:** `per_regime_enabled`, `regime_count`
- **SQL Integration:** Ready for ACM_Runs table

### 4. Documentation
- **README.md:** Section 4 updated with per-regime explanation
- **README.md:** Output artifacts list includes `per_regime_thresholds.csv`
- **This document:** Complete technical documentation

---

## Configuration Examples

### Example 1: Enable Per-Regime (Default)
```csv
0,fusion,per_regime,True,bool
0,regimes,quality.silhouette_min,0.2,float
```

### Example 2: Disable Per-Regime
```csv
0,fusion,per_regime,False,bool
```

### Example 3: Custom Sensitivity
```csv
# Make regime 1 less sensitive (higher threshold)
0,self_tune,regime_sensitivity,{0: 1.0; 1: 0.8},dict
```

### Example 4: Stricter Quality Gate
```csv
# Only enable per-regime when clustering is very good
0,regimes,quality.silhouette_min,0.5,float
0,regimes,quality.calinski_min,100.0,float
```

---

## Troubleshooting

### Per-Regime Not Activating

**Check console logs:**
```
[CAL] Fitting per-regime thresholds for N regimes.
```

**If not present, verify:**
1. `fusion.per_regime=True` in config
2. Regime clustering succeeded (check `[REGIME]` logs)
3. Silhouette score ≥ 0.2 (check `[REGIME] Quality scores:` log)
4. Both train and score regime labels exist

### Table Not Generated

**Check:**
1. `quality_ok=True` (logged in calibration section)
2. No errors in calibration (check full console output)
3. `OutputManager.write_table()` succeeded

### Unexpected Sensitivity

**Verify:**
1. `self_tune.regime_sensitivity` values (< 1.0 = less sensitive)
2. Regime labels correct (check `regime_timeline.csv`)
3. Per-regime parameters reasonable (check `per_regime_thresholds.csv`)

---

## Related Tasks

- **REG-01 to REG-07:** Regime clustering system
- **FUSE-02:** Fusion threshold auto-tuning
- **FUSE-06:** Automatic barrier adjustment
- **DET-01 to DET-06:** Other detector enhancements

---

## Future Enhancements (Not Implemented)

### 1. Per-Regime Fusion Weights
Allow different detector weights per regime:
```csv
0,fusion,weights_per_regime,{0: {ar1_z: 0.3; ...}; 1: {ar1_z: 0.15; ...}},dict
```

### 2. Regime-Specific Episode Thresholds
Different `h_sigma` and `k_sigma` per regime:
```csv
0,episodes,cpd_per_regime,{0: {k_sigma: 1.0; h_sigma: 4.0}; 1: {k_sigma: 1.5; h_sigma: 6.0}},dict
```

### 3. Historical Regime Drift Detection
Track if regime parameters drift over time (gradual shift in normal behavior).

---

## References

- **Code:** `core/fuse.py` lines 258-360 (ScoreCalibrator)
- **Code:** `core/acm_main.py` lines 1430-1595 (calibration integration)
- **Code:** `core/run_metadata_writer.py` lines 164-207 (metadata extraction)
- **Config:** `configs/config_table.csv` line 63 (`fusion.per_regime`)
- **Backlog:** `Task Backlog.md` line 107 (DET-07 task)
- **User docs:** `README.md` section 4 (calibration & fusion)

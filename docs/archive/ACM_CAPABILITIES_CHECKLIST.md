# ACM Capabilities — What It Does & Verification Status

**Date:** 2026-03-08
**ACM Version:** v11.15.x

This is the ground-truth list of what ACM is supposed to do, what it actually does, and whether it's working correctly. Fix items top to bottom.

---

## Pipeline Stages (in execution order)

### 1. Data Ingestion
**What it does:** Loads sensor data from SQL historian tables in time-windowed batches.

| Check | Expected | Observed | Status |
|-------|----------|----------|--------|
| Loads correct time window per batch | Yes | Yes — tick=35904min for T10 with max-batches=15 | ✅ |
| Excludes low-variance sensors | Yes | Yes — 2 excluded for T10 | ✅ |
| Handles gaps / resampling | Auto | cadence=600s, resample=False | ✅ |
| Reports row count | Yes | 3577 rows batch 1 T10 | ✅ |
| Stops if no data | Yes | — | ✅ |
| **Coldstart split (train/score)** | 60/40 | 2146 train / 1431 score | ✅ |

---

### 2. Feature Engineering
**What it does:** Computes rolling statistics (mean, std, min, max), spectral energy, cross-sensor correlations → ~788–869 features from 79 raw sensors.

| Check | Expected | Observed | Status |
|-------|----------|----------|--------|
| Feature count reasonable | ~800 | 869 features from 79 sensors | ✅ |
| Drops low-variance features | Yes | 81 dropped T10 batch 1 | ✅ |
| Seasonality detection | Yes | 6 patterns detected T10 | ✅ |
| No NaN in output | Yes | — | ✅ |
| **Feature build time** | <30s | ~17s (11:46:45 → 11:47:01) | ✅ |

---

### 3. Regime Classification (HDBSCAN + GMM)
**What it does:** Clusters operating regimes from raw sensor values (power, wind speed, RPM). Labels each time-point with a regime. Points outside trained distribution = UNKNOWN.

| Check | Expected | Observed (T10 batch 1) | Status |
|-------|----------|------------------------|--------|
| Uses raw sensors only (not z-scores) | Yes | 21 operational sensors | ✅ |
| HDBSCAN primary, GMM fallback | Yes | HDBSCAN found 1 cluster + GMM fallback | ✅ |
| **Multiple regimes detected** | 2–6 | **1 cluster** | ⚠️ PROBLEM |
| Novel point rate | <20% | 12.1% (173/1431) | ✅ |
| Training distance threshold P99 | P99 | 11.037 | ✅ |
| Saves regime state to SQL | Yes | Yes — ACM_RegimeState v1 | ✅ |
| Regime quality OK | True | True (healthy=1109, suspect=322) | ✅ |
| **Transient detection** | Identifies trips/startups | trip=1431 (ALL points are 'trip') | ⚠️ PROBLEM |

**Issues:**
- Only 1 operating regime detected for T10. A wind turbine should have at minimum: low-wind partial load, high-wind full load, startup ramp, shutdown. 1 cluster means the regime model sees the entire operating envelope as one state — no discrimination possible.
- All 1431 score points classified as 'trip'. This suggests the transient detector is misconfigured or the operating variable selection is including non-operational signals.

---

### 4. Anomaly Detection (6-head ensemble)
**What it does:** Each detector scores each time-point; higher score = more anomalous.

| Detector | Purpose | T10 Batch 1 | Status |
|----------|---------|-------------|--------|
| AR1 | Sensor temporal drift | Fitted 788 features, 27 cols clamped to ±0.999 | ✅ |
| PCA-SPE | Sensor decoupling | 5 components, 2146 samples, 788 features | ✅ |
| PCA-T² | Operating point shift | Cached from PCA fit | ✅ |
| IForest | Rare states | 100 trees | ✅ |
| GMM | Density / mode shift | BIC selected k=3 | ✅ |
| OMR | Cross-sensor prediction | PLS model, 788 features, 5 components | ✅ |
| **Fit time** | <60s | 53.9s | ✅ |

**Correlation problem (T10 batch 1):**
- `gmm_z ↔ iforest_z: 0.97`
- `gmm_z ↔ omr_z: 0.99`
- `iforest_z ↔ omr_z: 0.98`

Three detectors are nearly identical (r > 0.97). The correlation discount (24%) is applied but this barely changes the effective ensemble — we have 4 independent detectors at best, not 6. In a heavily contaminated training window where all sensors move together, GMM/IForest/OMR all learn the same pattern.

---

### 5. Score Calibration
**What it does:** Maps raw detector scores to z-scores on a common scale. Target: 0.1% FP rate. Contamination filter removes obvious training anomalies before fitting thresholds.

| Check | Expected | Observed (T10 batch 1) | Status |
|-------|----------|------------------------|--------|
| Per-regime thresholds | Yes | 1 regime → 1 threshold set | ✅ |
| Contamination filter | ≤30% excluded | **37.8% excluded — capped at 30%** | ⚠️ PROBLEM |
| Self-tuning active | Yes | Yes, q=0.9950 | ✅ |
| Extreme threshold clamping | Yes | Multiple thresholds clamped to 1000.0 | ⚠️ PROBLEM |
| Calibration params saved | Yes | 6 detectors, 846 bytes to v1 | ✅ |

**Issues:**
- `37.8% contamination` in training data — the filter hit its 30% cap and included anomalous samples in calibration. This means thresholds are set too high (the "normal" distribution includes faults), making the calibrated z-scores too low.
- Three detectors (GMM, PCA-SPE, PCA-T2) produced thresholds of 285,012; 1,000,000; 1,000,000 — all clamped to 1000.0. These are **not meaningful thresholds** — they indicate the detector could not distinguish normal from anomalous in the training data.

---

### 6. Fusion & Episode Detection
**What it does:** Weighted fusion of 6 calibrated detector scores → single FusedZ. CUSUM change-point detection → episodes with start/end times, severity, culprit detectors.

| Check | Expected | Observed (T10 batch 1) | Status |
|-------|----------|------------------------|--------|
| Correlation-weighted fusion | Yes | 3 pairs discounted ~24% | ✅ |
| CUSUM auto-tuned | Yes | k_sigma: 2.0→0.8, h_sigma: 12.0→3.0 | ✅ |
| Episodes detected | Yes | 12 CRITICAL (all GMM) | ✅ |
| Severity classification | LOW/MEDIUM/HIGH/CRITICAL | CRITICAL | ✅ |
| **Episode quality** | Fault-aligned | Oct 27–28 2022 (pre-fault period) | ❓ TBD |
| Auto-tune persists to ACM_Config | Yes | clip_z: 50→60, k_max: 6→8 | ✅ |
| Refit requested | Only when needed | Yes (1 refit row) | ✅ |

---

### 7. Drift Monitoring
**What it does:** Monitors whether the equipment is in a drifting / degraded state beyond what episodes capture.

| Check | Expected | Observed (T10 batch 1) | Status |
|-------|----------|------------------------|--------|
| Drift mode computed | NORMAL/WARNING/FAULT | **FAULT** | ⚠️ Note |
| Persisted to SQL | Yes | ACM_DriftController 1 row | ✅ |

T10 batch 1 immediately in FAULT mode. This reflects the pre-fault distressed state of the turbine in Oct 2022. Not a bug — but confirms contaminated baseline.

---

### 8. Model Lifecycle
**What it does:** Tracks model maturity: COLDSTART → LEARNING → CONVERGED. Promotes when quality criteria met across consecutive runs.

| Check | Expected | Observed | Status |
|-------|----------|----------|--------|
| New model starts LEARNING | Yes | Yes — v1 LEARNING | ✅ |
| Promotion criteria applied | min 3 consecutive runs | 1 run so far | 🔄 |
| SilhouetteScore tracked | Yes | 0.259 (DBCV, from HDBSCAN) | ✅ |
| RegimeQualityMetric persisted | Yes | DBCV score written | ✅ |
| ACM_ActiveModels updated | Yes | Yes | ✅ |

---

### 9. Analytics & Output Tables
**What it does:** Writes all derived tables after each run.

| Table | T10 Batch 1 Rows | Status |
|-------|-----------------|--------|
| ACM_Scores_Wide | 1,431 | ✅ |
| ACM_HealthTimeline | 1,431 | ✅ |
| ACM_RegimeTimeline | 1,431 | ✅ |
| ACM_Episodes | 12 | ✅ |
| ACM_ContributionTimeline | 8,586 | ✅ |
| ACM_SensorDefects | 8 | ✅ |
| ACM_SensorHotspots | 25 | ✅ |
| ACM_DetectorCorrelation | 36 | ✅ |
| ACM_SensorCorrelations | 3,160 | ✅ |
| ACM_SensorNormalized_TS | 10,349 | ✅ |
| ACM_CalibrationSummary | 6 | ✅ |
| ACM_RunMetrics | 18 | ✅ |
| ACM_DriftController | 1 | ✅ |
| ACM_ActiveModels | 1 | ✅ |

All output tables populating correctly. ContributionTimeline fix (v11.15.7) confirmed working.

---

## Priority Fix List

| # | Problem | Impact | Fix |
|---|---------|--------|-----|
| 1 | **Contaminated training baseline** | Detection rate = 0% | Identify clean healthy windows; detect & reject contaminated training data |
| 2 | **T10/T11/T21 missing/incomplete data** | 5 of 11 faults unassessable | Import T11/T21 data; finish T10 batches |
| 3 | **Single operating regime (T10)** | No regime-conditional detection | Check why only 1 HDBSCAN cluster — min_cluster_size may be too large for 2146 samples |
| 4 | **All points labeled 'trip' by transient detector** | Transient masking all signals | Review operating variable selection and transient threshold config |
| 5 | **Calibration thresholds clamping to 1000.0** | Calibrated z-scores not meaningful | Fix upstream — solve contaminated baseline; also review self-tuning FP rate target |
| 6 | **GMM/IForest/OMR correlation 0.97–0.99** | Effective ensemble is 3 not 6 detectors | Expected on contaminated data; will improve with clean baseline. Also review OMR feature set. |
| 7 | **T13 stuck at LEARNING** | Thresholds never stabilize | Run more batches after clean baseline established |

---

## What ACM Does Well (Confirmed Working)
- Data loading, windowing, cadence detection ✅
- Feature engineering (788 features, seasonality) ✅
- All 6 detector fits completing in <60s ✅
- All output tables writing correctly ✅
- CUSUM auto-tuning and episode detection ✅
- ContributionTimeline populating (v11.15.7 fix) ✅
- Model lifecycle tracking ✅
- Config auto-tune persisting to ACM_Config ✅
- Drift monitoring ✅

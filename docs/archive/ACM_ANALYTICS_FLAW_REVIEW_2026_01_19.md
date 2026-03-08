# ACM Analytics Flaw Review (2026-01-19)

**Scope**: Analytical handling of data for unsupervised condition monitoring and fault detection (feature engineering, scoring, fusion, regimes, confidence, thresholds, forecasting/RUL). This document focuses on analytical correctness and reliability risks, not infrastructure or operational issues.

**Sources**:
- Prior audit: docs/ACM_V11_ANALYTICAL_AUDIT.md
- Fixes summary: docs/ACM_V11_ANALYTICAL_FIXES.md
- System map: docs/ACM_SYSTEM_OVERVIEW.md
- Core modules: core/*.py (feature engineering, regimes, fusion, confidence, thresholds, forecasting)

---

## Executive Summary

The ACM analytics pipeline is sophisticated but still has several **high-risk failure modes** in unsupervised analytics. The most critical risks are:
1. **Regime discovery bias** (small/rare regimes lost, regime uncertainty suppressed).
2. **Regime-agnostic degradation modeling** (RUL and health forecasts fail under regime shifts).
3. **Calibration/thresholding sensitivity** to contaminated training windows and anomaly contamination.
4. **Data leakage risk** in feature imputation if train/score separation is not enforced everywhere.
5. **Confidence decay and aggregation** that can mischaracterize reliability across horizons and states.

Many P0 items were addressed in v11.2.2 (see docs/ACM_V11_ANALYTICAL_FIXES.md), but **P1/P2** issues remain and can still produce false certainty, missed regimes, and RUL bias.

---

## Findings and Mitigations

### 1) Regime discovery misses rare or transient regimes
**Risk**: HDBSCAN min cluster size and subsampling can suppress short-lived or rare regimes (startup/shutdown), collapsing regimes into noise or a dominant cluster. This impacts regime labeling, fusion context multipliers, and downstream analytics.

**Primary references**: core/regimes.py; docs/ACM_V11_ANALYTICAL_AUDIT.md (FLAW #2)

**Impact**:
- Loss of transient regime signatures → missed faults during transitions.
- Over-confident regime assignments in mixed-mode windows.

**Mitigation**:
- Reduce min_cluster_size to an absolute threshold (20–50 points) instead of % of data.
- Add transient-aware overrides using ROC/variance markers.
- Ensure subsampling doesn’t dominate rare regimes (stratify by operating state or time).

---

### 2) Regime uncertainty is diluted by reassignment heuristics
**Risk**: Low-confidence points can be reassigned (e.g., GMM fallback) which reduces UNKNOWN regime coverage and can mask novelty or unstable regimes.

**Primary references**: core/regimes.py

**Impact**:
- Suppresses novelty detection and makes regimes appear more stable than reality.

**Mitigation**:
- Preserve UNKNOWN regime for low-confidence points or keep a separate uncertainty flag.
- Require consistency across multiple windows before reassignment.

---

### 3) Regime-conditioned degradation and RUL (rewrite)
**Problem**: The current degradation model treats the entire health timeline as one regime. It fits a single Holt trend and extrapolates, even though degradation rates are regime-dependent (load, speed, thermal stress). When the operating regime shifts, the “global” trend is no longer valid.

**Where the issue lives**:
- core/degradation_model.py: `LinearTrendModel.fit()` uses only a single health series.
- core/forecast_engine.py: the forecast path instantiates `LinearTrendModel` directly.
- core/rul_estimator.py: has regime-transition support in `_run_monte_carlo_simulations`, but that path is never exercised because regime data is not passed.

**Why this is wrong for ACM’s goal**:
- Unsupervised condition monitoring depends on **regime-aware normalization** and **regime-aware degradation**. If the model collapses multiple regimes into a single trend, it confuses operational shifts with real degradation.
- This produces **biased RUL** and falsely calibrated confidence intervals whenever regimes change mid-horizon.

**Correct approach (default, not optional)**:
1) Fit **per-regime trend models** for degradation.
2) Use a **regime transition model** to project future regimes during the forecast horizon.
3) Run RUL simulations across those regime paths so uncertainty reflects regime switching.

**Required code changes (replace, don’t append)**:
1) core/degradation_model.py
   - Add `RegimeConditionedTrendModel(BaseDegradationModel)`.
   - It must accept `(health_series, regime_series)` and fit a `LinearTrendModel` for each regime with a minimum sample guard.
   - It must also fit a **global fallback** model internally for regimes with insufficient data, but that fallback is not exposed as an external “legacy mode.”

2) core/forecast_engine.py
   - Replace all direct use of `LinearTrendModel()` with `RegimeConditionedTrendModel()`.
   - Align regime labels to the health timeline (forward-fill with a capped window; no long-gap bleed).
   - Compute a transition matrix from observed regime sequences.
   - Pass regime trends + transitions into RUL simulation.

3) core/rul_estimator.py usage
   - Always pass `regime_transition_matrix`, `regime_degradation_rates`, and `current_regime` when running Monte Carlo RUL for a regime-conditioned forecast.
   - Only fall back to the fast path when regime coverage is too low or ill-conditioned (guardrails), not via a user-facing flag.

**Regime-aware forecasting behavior (spec)**:
- **Alignment**: regimes must align to health timestamps; if missing, fill forward only up to a bounded gap (e.g., 2× median cadence).
- **Unknown regime (-1)**: include as a state only if it meets minimum samples; otherwise exclude from transitions but log its coverage.
- **Transition matrix**: build from consecutive regime labels and smooth with a small prior (e.g., add $1$ per state) to avoid zero-probability traps.
- **Path generation**: use the matrix to sample regime sequences; apply the regime-specific trend step-by-step across the horizon.
- **Fallback**: when coverage/quality fails, use the model’s internal global fit but still record the reason in diagnostics.

**Why this method is correct (proof/justification)**:
- **Statistical validity**: regime switching is a classic non-stationary process. A single Holt trend assumes stationarity, which is violated under regime shifts. This yields biased estimates by construction.
- **Reliability literature**: semi-Markov or switching models are standard in RUL estimation (e.g., Limnios & Oprisan, 2001). ACM already references semi-Markov transitions in core/rul_estimator.py, which indicates intended design alignment.
- **Internal consistency**: ACM already models regimes for anomaly scoring and fusion. A regime-aware forecast is the only consistent way to avoid mixing operational shifts into degradation.

**Evidence strategy (how to prove in ACM)**:
1) **Backtest**: compare global-trend vs regime-conditioned RUL against historical failures or known degradation slopes. Expect lower MAE/MAPE and better P10/P50/P90 coverage.
2) **Regime-switch synthetic test**: simulate regime-dependent degradation with known parameters and verify the regime-conditioned model recovers correct RUL distribution while global trend is biased.
3) **Calibration check**: evaluate whether P10/P90 bands achieve target coverage across regime changes. Regime-conditioned paths should reduce systematic under/over-coverage.
4) **Operational sanity**: verify that RUL shifts appropriately when the current regime changes (e.g., switch to low-load should lengthen RUL).

**Mitigation**:
- Replace the single-trend forecasting path with regime-conditioned modeling and regime-aware RUL simulation.
- Keep only internal fallback to global trend for sparse regimes; remove the legacy model path entirely.

---

### 4) Monte Carlo RUL does not model regime transitions
**Risk**: Simulation assumes a single regime during forecast horizon, ignoring regime transitions that can dominate future degradation rates.

**Primary references**: core/rul_estimator.py

**Impact**:
- Underestimates or overestimates RUL when operating modes change.

**Mitigation**:
- Incorporate regime transition probabilities or scenario trees (e.g., switching Markov model).
- Use regime-conditioned forecast paths rather than a single baseline trajectory.

---

### 5) Feature imputation leakage risk
**Risk**: If any score-time feature imputation uses score-derived statistics, that leaks test distribution into the scoring phase.

**Primary references**: core/fast_features.py; core/acm_main.py

**Impact**:
- Inflated detection quality and suppressed anomaly sensitivity.

**Mitigation**:
- Enforce strict mode-based imputation (train-only stats for score).
- Add hard validation to reject score imputation without training statistics.

---

### 6) Calibration and thresholding are sensitive to contaminated training windows ✅ FIXED v11.3.3
**Risk**: Training windows can contain anomalies; calibration and thresholds derived from such windows become too permissive.

**Primary references**: core/adaptive_thresholds.py; core/fuse.py; core/analytics_builder.py

**Impact**:
- Increased false negatives and delayed detection.

**Mitigation** (IMPLEMENTED v11.3.3):
- ✅ NEW: `CalibrationContaminationFilter` class in core/fuse.py
- ✅ Filters anomalous samples BEFORE computing calibration statistics
- ✅ Multiple robust methods: `iterative_mad` (default), `iqr`, `z_trim`, `hybrid`
- ✅ Integrated into `ScoreCalibrator.fit()` and `AdaptiveThresholdCalculator`
- ✅ Safety guards: max 30% exclusion, min 50 samples retained, convergence detection
- ✅ Config: `thresholds.contamination_filter.enabled` (default: True)
- ✅ Config: `thresholds.contamination_filter.method` (default: iterative_mad)
- ✅ Config: `thresholds.contamination_filter.z_threshold` (default: 4.0)
- Uses robust statistics (median/MAD) consistently throughout

---

### 7) Confidence decay may suppress long-horizon usefulness
**Risk**: Confidence decay with horizon can be overly aggressive, marking valid long-range predictions as unreliable.

**Primary references**: core/confidence.py

**Impact**:
- Conservative RUL guidance even when model is stable.

**Mitigation**:
- Calibrate decay curves per asset class or regime stability.
- Add data-driven decay rates based on historical forecast error by horizon.

---

### 8) Confidence aggregation remains sensitive to configuration overrides
**Risk**: Confidence aggregation was fixed to harmonic mean in v11.2.2, but config overrides or legacy calls may still behave inconsistently.

**Primary references**: core/confidence.py; docs/ACM_V11_ANALYTICAL_FIXES.md (FIX #4)

**Impact**:
- Overconfident summary confidence even with weak regime or data quality.

**Mitigation**:
- Audit all call paths for consistency.
- Add a min-factor guard or optional min-operator for safety-critical equipment.

---

### 9) Correlation-aware fusion discount may be incomplete
**Risk**: Correlation discounting may not cover all detector pairs or time-varying correlations, allowing correlated detectors to dominate fusion.

**Primary references**: core/fuse.py

**Impact**:
- Amplified anomaly score due to redundant detectors.

**Mitigation**:
- Compute rolling correlation and discount dynamically per time window.
- Enforce minimum detector diversity in weight allocation.

---

### 10) Seasonality detection assumes stationarity
**Risk**: Seasonality detection uses a single-period FFT on the full series. In industrial data, seasonality is non-stationary (weekday/weekend, shift changes).

**Primary references**: core/seasonality.py; docs/ACM_V11_ANALYTICAL_AUDIT.md (FLAW #5)

**Impact**:
- False seasonal adjustment or missed patterns, skewing anomaly signals.

**Mitigation**:
- Use windowed FFT or time-varying seasonality detection with overlapping windows.

---

### 11) Health jump threshold may miss smaller maintenance resets
**Risk**: Maintenance jump threshold is fixed (15%), so smaller maintenance resets may be missed and distort degradation trends.

**Primary references**: core/degradation_model.py; docs/ACM_V11_ANALYTICAL_AUDIT.md (FLAW #12)

**Impact**:
- Trend fits contaminated by maintenance events → RUL bias.

**Mitigation**:
- Learn thresholds per asset based on historical jump distribution.
- Use change-point detection instead of fixed percent.

---

## Recommended Priority Actions

**Immediate (P0/P1)**
1. Implement regime-conditioned degradation and regime-aware RUL simulation.
2. Enforce strict train-only imputation with validation.
3. Re-tune HDBSCAN min_cluster_size with transient-aware thresholds.

**Short-Term (P1)**
4. ~~Add anomaly-trimmed calibration/thresholding.~~ ✅ DONE v11.3.3 - CalibrationContaminationFilter
5. Introduce windowed seasonality detection.
6. Audit fusion correlation discounting and dynamic correlation handling.

**Medium-Term (P2)**
7. Calibrate confidence decay by asset/regime stability.
8. Replace fixed maintenance jump threshold with adaptive detection.

---

## Validation Checklist (Analytics-Only)

- Regime clustering correctly identifies short-lived transient states.
- RUL forecasts match regime-switch scenarios within error tolerances.
- Calibration windows exclude high-z episodes.
- Score-time imputation always uses train statistics (hard failure if not).
- Confidence values correlate with historical forecast error across horizons.

---

## Appendix: Related Documents

- docs/ACM_V11_ANALYTICAL_AUDIT.md
- docs/ACM_V11_ANALYTICAL_FIXES.md
- docs/ACM_SYSTEM_OVERVIEW.md

---

**Document Owner**: ACM Analytical Review
**Last Updated**: 2026-01-19

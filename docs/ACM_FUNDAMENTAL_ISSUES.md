# ACM — Fundamental Issues Identified (All-Time)

This document catalogues every fundamental design flaw, bug class, and architectural
anti-pattern discovered across all ACM development sessions, with root cause analysis
and the fix applied. Organised by severity and category.

---

## P0 — Critical (System-Breaking)

### P0-1: Circular Regime Masking (v11.4.0)

**Symptom**: Equipment appears "healthy in its current regime" even while degrading.

**Root Cause**: Regime clustering used detector z-scores (`health_ensemble_z`,
`health_trend`, `health_quartile`) as clustering features. When equipment degraded:
1. Detector z-scores rose.
2. Health-state features caused the degraded point to cluster into a **new regime**.
3. New regime got a fresh baseline → degradation masked.
4. Equipment remained "healthy in its current regime" forever.

**Fix (v11.4.0)**: Removed `_add_health_state_features()` entirely. Regime clustering
now uses **raw sensor values only** (load, speed, flow, pressure). Detectors are
outputs of anomaly detection, not inputs to regime clustering. `REGIME_MODEL_VERSION`
bumped 3.1 → 4.0.

**Principle**: Regimes = HOW equipment operates. Detectors = IF equipment is healthy.
These are orthogonal and must never be mixed.

---

### P0-2: False Positive Threshold Bug (v11.6.0)

**Symptom**: 88% of readings were flagged as ALERT.

**Root Cause**: `thresholds.alert=0.85` and `thresholds.warn=0.7` were intended as
percentile cuts but were interpreted as z-scores. A z-score of 0.85 is nearly always
exceeded → constant alerting.

**Fix (v11.6.0)**: Changed config defaults to `alert=3.0`, `warn=1.5` (proper 3-sigma
thresholds). `populate_acm_config.py` must be re-run after updating `config_table.csv`.

---

### P0-3: Double Z-Scoring / Cross-Batch Health Instability (v11.9.0)

**Symptom**: Health score flipped from 39% to 94% between consecutive batches on the
same data. Fusion took 26 minutes on 4 301 samples.

**Root Cause**: `Fuser._zscore()` re-normalised already-calibrated z-scores against the
**current batch** distribution. `ScoreCalibrator` produced training-anchored z-scores,
but fusion then destroyed that anchoring by re-centering per batch.

**Fix (v11.9.0)**: Replaced `_zscore()` with `_sanitize()` (NaN/inf only). Calibrated
z-scores pass through to fusion unchanged. Calibration params persisted to SQL so
scoring batches reuse training-time normalization.

---

### P0-4: Perpetual Refit Loop (v11.5.0 + v11.15.1)

**Two distinct causes of the same symptom: every batch forced a retrain.**

**Cause A — OFFLINE mode every batch (v11.5.0)**:
`sql_batch_runner.py` ran every batch in OFFLINE (training) mode. Fix: coldstart batch
runs OFFLINE, all subsequent batches ONLINE. (Later superseded by v11.8 adaptive.)

**Cause B — Feature mismatch 632→630 (v11.15.1)**:
`impute_features()` dropped low-variance columns using `train.std()`. In scoring
batches, `train` is populated from the baseline buffer (trip-state data with near-zero
variance). Two columns that had variance during coldstart had zero variance in the
baseline-derived train → dropped → 632 cached features vs 630 current → mismatch →
forced retrain every batch.

**Fix (v11.15.1)**: `load_manifest_only()` fetches `train_sensors` from SQL manifest
before imputation. Passed as `protected_columns` to `impute_features()` — protected
columns are **never** dropped regardless of variance.

---

### P0-5: 10× Data Inflation via Upsampling (v11.5.0)

**Symptom**: Row counts inflated 10× per batch; calibration, detection, and analytics
all corrupted.

**Root Cause**: `data.sampling_secs=60` with native cadence of 600s caused resampling
(interpolation) to 10× more rows.

**Fix (v11.5.0)**: Anti-upsample guard — if requested < native cadence × 0.9, skip
resample. Config default changed to `"auto"` (use native cadence).

---

### P0-6: Transform Error on Corrupt Cached Models (v11.6.0)

**Symptom**: NoneType transform errors on `~4` runs per batch sweep.

**Root Cause**: Models loaded from SQL with a `None` scaler (corrupt serialisation).
`predict_regime()` called `scaler.transform()` without a None-guard.

**Fix (v11.6.0)**: Explicit None-guard before `scaler.transform()` in `regimes.py`.
Clear error message pointing to corrupt model in `ModelRegistry`.

---

## P1 — High Impact

### P1-1: Model Accumulation (v11.6.0)

**Symptom**: 171 model versions per equipment, 1 026 rows in `ModelRegistry` per
equipment from a single batch sweep.

**Root Cause**: Every batch created a new model version with no cleanup.

**Fix (v11.6.0)**: `_cleanup_old_versions(keep_n=5)` after each save. Old versions
deleted automatically.

---

### P1-2: Spurious Refit Requests for CONVERGED Models (v11.6.0)

**Symptom**: 170+ refit requests generated for CONVERGED equipment per batch sweep.

**Root Cause**: `auto_tune_parameters()` evaluated all equipment for refit, including
those already CONVERGED.

**Fix (v11.6.0)**: Skip refit evaluation entirely when `model_maturity == "CONVERGED"`.
CONVERGED models only retrain on quality degradation or explicit `--force-retrain`.

---

### P1-3: ONLINE Batch Crash After Coldstart Refit Request (v11.6.1)

**Symptom**: ONLINE batches crashed with "Required detector models not found in cache".

**Root Cause**: Run #1 (coldstart/OFFLINE) created a refit request. Run #2 (ONLINE)
saw `refit_requested=True` → `use_cache=False` → models not loaded → ONLINE mode
cannot retrain → crash.

**Fix (v11.6.1)**: In ONLINE mode, ignore `refit_requested` and always load cached
models. (Later superseded by v11.8 adaptive pipeline which eliminated ONLINE/OFFLINE.)

---

### P1-4: Training Subsampling Missing → 2+ Hour Runs (v11.6.0)

**Symptom**: Batch runs taking 2+ hours with 26 000 training rows.

**Root Cause**: PCA and HDBSCAN are O(n²) in training rows. No subsampling cap.

**Fix (v11.6.0)**: Stratified subsampling to `models.max_train_samples=10000` using
evenly-spaced indices in `fit_all_detectors()`. Runs reduced to ~10 minutes.

---

### P1-5: Seasonal Adjustment Data Flow Bug (v11.1.4)

**Symptom**: Seasonal adjustment applied but downstream features used unadjusted data.

**Root Cause**: `SeasonalityHandler` updated `train_numeric`/`score_numeric` (local
derivatives) but `train`/`score` (the actual source DataFrames used by `_build_features`)
were not updated.

**Fix (v11.1.4)**: After seasonal adjustment, write back sensor columns to the source
DataFrames (`train[col] = train_adj[col].values` for all sensor columns).

---

### P1-6: MHAL Detector — Redundant with PCA-T² (v10.2.0)

**Symptom**: Mahalanobis detector duplicating PCA-T² information with numerical instability.

**Root Cause**: Mahalanobis D² = (x-μ)ᵀΣ⁻¹(x-μ). PCA-T² = Σᵢzᵢ²/λᵢ. These are
mathematically equivalent. MHAL suffered from ill-conditioned covariance under
multicollinearity.

**Fix (v10.2.0)**: MHAL removed. Detector count: 7 → 6. `mhal_z` fusion weight = 0.0.

---

### P1-7: ACM_RunLogs Always Empty (v11.6.0 + v11.13.1)

**Two separate issues:**

**Issue A (v11.6.0)**: `enable_sql_logging()` called BEFORE SQL connection established.
Fix: call after SQL connection, pass `sql_client`.

**Issue B (v11.13.1)**: `_SqlLogSink` was created but never wired into `Console`. No
log records were ever queued. Fix: class deleted entirely. Loki is the sole log
persistence path.

---

### P1-8: Triple Timer Summary on Console (v11.10.0)

**Symptom**: Three timer summaries printed at process exit.

**Root Cause**: Three `Timer()` instances each registered atexit callbacks:
1. `T = Timer()` in `main()` (correct)
2. `_timer = Timer()` at module level in `fast_features.py` (spurious)
3. Second `main()` Timer (now gone)

**Fix (v11.10.0)**: Removed module-level `_timer` from `fast_features.py`. Result:
exactly one timer summary per subprocess.

---

### P1-9: Duplicate `main()` in acm_main.py (v11.10.0)

**Symptom**: Code changes seemed to have no effect; bugs persisted despite fixes.

**Root Cause**: `acm_main.py` had grown to 5 408 lines with **two** `def main()`
(at lines 617 and 3320). Python silently shadows the first definition. Only the
second `main()` was reachable.

**Fix (v11.10.0)**: User removed duplicate block. File cleaned to 2 705 lines, single
`main()`.

---

## P2 — Medium Impact

### P2-1: Detector Correlation Double-Counting (v11.1.4)

**Symptom**: PCA-SPE and PCA-T² (both derived from PCA) had effective 2× influence
in fusion.

**Root Cause**: Naive weighted sum of detector scores ignored inter-detector correlation.
PCA-SPE/T² are often correlated at |r| > 0.8.

**Fix (v11.1.4)**: Correlation discount in `Fuser.fuse()` — for any pair with |r| > 0.5,
weights reduced proportionally (`discount = min(0.3, (|r| - 0.5) × 0.5)`).

---

### P2-2: Mean/Std in Calibration (v11.1.3)

**Symptom**: Thresholds corrupted by outliers in baseline data.

**Root Cause**: Calibration used mean/std (breakdown point = 0%) for threshold fitting.
Single outlier corrupts the threshold.

**Fix (v11.1.3)**: Switched to median/MAD (breakdown point = 50%).
`std_robust = mad × 1.4826` (consistent with σ under normality).

---

### P2-3: Confidence Calculation Geometric vs Harmonic Mean (v11.2.2)

**Symptom**: High confidence reported even when one factor was critically low.
`regime=0.1, others=0.9` → arithmetic = 0.70, geometric = 0.56, harmonic = 0.31.

**Root Cause**: Geometric mean allows high factors to mask low factors.

**Fix (v11.2.2)**: Changed to harmonic mean. One critically low factor now properly
pulls overall confidence down.

---

### P2-4: Health Forecast Level Shift (v11.1.4)

**Symptom**: Degradation model fit entire health history including maintenance resets,
producing corrupted trend and inflated RUL.

**Root Cause**: Health timeline included maintenance-induced jumps (40% → 95%).
Holt-Winters fitted across the jump, seeing a positive trend.

**Fix (v11.1.4)**: `_detect_and_handle_health_jumps()` — detects positive jumps
> 15%, uses only post-jump data for trend fitting. Maintenance events logged.

---

### P2-5: RUL Implausible Predictions Not Rejected (v11.3.4)

**Symptom**: RUL < 1h with health = 95%. FailureProbability = 100% with RUL = 500h.

**Root Cause**: No validation on RUL outputs before writing to SQL.

**Fix (v11.3.4)**: Validation guards in `forecast_engine.py`:
- Reject RUL < 1h when health > 70%
- Reject FailureProbability = 100% when RUL > 100h
- Reject negative, infinite, or NaN values

---

### P2-6: Model State Not Passed to ForecastEngine (v11.x)

**Symptom**: ForecastEngine unaware of model maturity; RUL predictions not gated
by CONVERGED state.

**Root Cause**: `model_state` computed in `acm_main.py` but not passed to
`ForecastEngine` constructor.

**Fix**: `ForecastEngine(sql_client=..., model_state=model_state)`.

---

### P2-7: DBCV Metric Retrain Trigger Loop (v11.12.0)

**Symptom**: Endless retrains even when DBCV score (e.g. 0.324) exceeded threshold (0.0).

**Root Cause**: Retrain trigger compared `quality_ok=False` (bool) regardless of metric
type. For DBCV, `quality_ok` was always False because the boolean gate was designed for
silhouette (where higher = better, and the threshold is the cutoff).

**Fix (v11.12.0)**: Metric-type-aware retrain trigger:
- silhouette → compare score vs `min_regime_quality` (0.3)
- dbcv/persistence → compare score vs `min_dbcv_quality` (0.0)
- BOOLEAN_ONLY (BIC, Calinski-Harabasz) → never trigger retrain

---

### P2-8: ONLINE/OFFLINE Architecture Was Wrong (v11.8.0)

**Root Cause**: Manual mode selection (OFFLINE for coldstart, ONLINE for scoring)
is fragile. Operators and scripts get it wrong. The distinction is artificial — the
pipeline should decide based on model state and quality, not flags.

**Fix (v11.8.0)**: Removed `PipelineMode` enum, `--mode` CLI argument, and all
mode-based gating. Pipeline is now fully adaptive. `--force-retrain` replaces
`--mode offline` for the rare case where manual retraining is needed.

---

## Performance Bottlenecks

### PERF-1: row-by-row `.apply()` in SeasonalityHandler (pre-v11.0.1)

`SeasonalityHandler.adjust_baseline()` used `Series.apply()` with a per-row lambda.
For 250K+ rows × 80 sensors: 30-70 minutes. Fixed with vectorised NumPy.

---

### PERF-2: `smooth_labels()` Python for-loop + `np.unique` per row (pre-v11.0.1)

`smooth_labels()` in `regimes.py` used a Python for-loop calling `np.unique()` per
row. For 250K rows: 30-60 minutes. Fixed with `scipy.stats.mode` vectorised operation.

---

### PERF-3: Monte Carlo Simulation Python Loop (v11.11.0)

`_run_monte_carlo_simulations()` "slow path" ran Python loop over
`n_simulations × n_steps` (1000 × 4310 = 4.3M iterations). Result: 563s.
Fixed with numpy vectorisation — O(n_steps) Python iterations instead of O(n_sims × n_steps).

---

### PERF-4: OutputManager NaN Cleaning (v11.12.0)

`_bulk_insert_sql()` used chained `DataFrame.replace()` calls (triggered 111 times,
430s CPU). Fixed with single vectorised numpy path (isfinite/abs for floats, set-mask
for object columns).

---

### PERF-5: OMR Scorer per-column notna() loop (v11.12.0)

`_prepare_data()` called `notna().mean()` per column in a loop (632 `Series.__init__`
calls). Fixed with `X.notna().mean()` (single pass).

---

### PERF-6: Rolling spectral energy — per-row FFT callbacks (v11.15.2)

`map_elements(FFT_lambda)` called once per row per column (79 cols × 1800 rows =
142 200 FFT calls). Fixed with `np.lib.stride_tricks.as_strided` + batch `np.fft.rfft`
on all windows at once. ~20s → <0.5s.

---

### PERF-7: PCA episode attribution per-episode pandas ops (v11.15.2)

`episode_features.select_dtypes().abs().mean()` called per episode on 632-column DF
(25 episodes × 232 per-column ops = 5 789 calls). Fixed with precomputed float32
numpy array; per-episode attribution = single `np.abs().mean(axis=0)` slice. 191s → 0.1s.

---

### PERF-8: `apply(pd.to_numeric)` on Polars-generated features (v11.15.2)

Two `train_feat.apply(pd.to_numeric)` calls iterated all 632 columns needlessly —
Polars already emits float64. ~24s/batch. Fixed with `select_dtypes` guard: only
object-dtype columns (typically zero) are coerced.

---

### PERF-9: `impute_features()` pandas copy + replace path (v11.15.2)

Two `pd.DataFrame.copy()` + `DataFrame.replace([inf,-inf], nan)` on 632-column DFs.
~40s/batch. Fixed with numpy-native path: `values.astype(float64)`, `arr[~isfinite]=nan`,
`np.nanmedian`, `np.copyto` broadcast fill, `np.std`.

---

## Code Quality / Architecture Anti-Patterns

### AQ-1: Pandas fallback paths in fast_features.py (v11.15.3)

All 6 core rolling functions had silent pandas fallbacks (triggered when `HAS_POLARS`
was False or when `return_type != "polars"`). These paths were dead in production but
could produce different (wrong) output. Removed in v11.15.3.

---

### AQ-2: `return_type` parameter on rolling functions (v11.15.3)

Rolling functions accepted a `return_type: Literal["polars", "pandas"]` parameter and
returned different types based on it. This is an anti-pattern — functions should have
single, consistent return types. All `return_type` parameters removed.

---

### AQ-3: `compute_basic_features()` wrapper (v11.15.3)

A pandas-to-Polars-to-pandas wrapper around `compute_basic_features_pl()`. Dead code
since `_build_features` in `acm_main.py` already called the `_pl` variant directly
with `pl.from_pandas(train)`. Removed.

---

### AQ-4: Module-level Timer in fast_features.py (v11.10.0)

`_timer = Timer()` at module level in `fast_features.py` registered an `atexit`
callback. Every subprocess printed a spurious timer summary in addition to the
correct one from `main()`. Removed.

---

### AQ-5: `CONTINUOUS_LEARNING` misused as force flag (ongoing vigilance)

`CONTINUOUS_LEARNING` (config) is NOT a force-retrain flag — it gates quality
evaluation downstream. Using `CONTINUOUS_LEARNING or force_retrain_cli` makes every
batch force-retrain, breaking scoring batches. `--force-retrain` is the only CLI
mechanism to force retraining.

---

### AQ-6: `meta` object type ambiguity (ongoing vigilance)

`meta` returned from `load_with_retry()` can be either a `dict` or a `DataMeta` object
depending on code path. Always use:
```python
val = meta.get(k, default) if isinstance(meta, dict) else getattr(meta, k, default)
```

---

### AQ-7: `coldstart_complete` vs `is_coldstart_run` confusion (ongoing vigilance)

`coldstart_complete` from `load_with_retry()` means "can_proceed" (True for BOTH
scoring and coldstart runs). Use `meta.is_coldstart_run` to distinguish an actual
coldstart from a scoring batch.

---

## SQL / Data Issues

### SQL-1: Refit Request Timestamp Mismatch (v11.10.0)

`ACM_RefitRequests.RequestedAt` stored as UTC (`SYSUTCDATETIME()`), but all log
timestamps use `datetime.now()` (local time). Apparent 5.5-hour gap between SQL record
and log entry. Fixed: INSERT now passes `datetime.now()` explicitly.

---

### SQL-2: PCA Cache Length Mismatch (v11.6.1)

`pca_train_spe`/`pca_train_t2` cached during fit (10 000 subsampled rows), then used
in calibration with full train data (13 000+ rows). `ValueError: Length of values (10000)
does not match length of index (13369)`. Fixed: only use PCA cache when
`len(pca_train_spe) == len(train)`, else re-score.

---

### SQL-3: Wrong Stored Procedure Parameter Name

`NOOP — no data returned` despite data existing. Root cause: stored procedure called
with `@EquipID` when it expected `@EquipmentName` (or vice versa). Always verify
parameter names match the stored procedure signature.

---

## Statistical Correctness

### STAT-1: MAD to σ Conversion

**Constant**: `1.4826` (`1/Φ⁻¹(0.75)`). Always use `std_robust = mad × 1.4826`
when computing robust standard deviation. Breakdown point: median = 50%, mean = 0%.

---

### STAT-2: Silhouette range and Promotion Thresholds

Silhouette ∈ [-1, 1]. Values below 0.3 indicate poor clustering and should trigger
regime retraining. Promotion from LEARNING → CONVERGED requires silhouette ≥ 0.40
(tightened in v11.2.2 from 0.15).

---

### STAT-3: Correlation Discount Threshold

Detector pairs with |Spearman r| > 0.5 receive a weight discount:
`discount = min(0.3, (|r| - 0.5) × 0.5)`. This prevents double-counting of
correlated information in fusion.

---

## Lessons for Future Development

1. **Never use detector outputs as inputs to regime clustering.** Regime = operating
   mode. Detectors = health state. They are orthogonal.

2. **Never re-normalize already-calibrated z-scores.** Calibration produces
   training-anchored scores; re-centering per batch destroys comparability.

3. **Never drop columns that the cached model was trained on.** Always fetch
   `train_sensors` from the manifest before imputation; pass as `protected_columns`.

4. **Polars is the feature engine.** No pandas fallback in the compute path.
   Conversion boundary is in `_build_features()` only.

5. **Functions must have a single return type.** No `return_type` parameters that
   change what the function returns.

6. **No wrappers.** If a function just converts types and calls another function,
   eliminate it and do the conversion at the call site.

7. **Force-retrain is CLI-only.** Never gate force-retrain on a config flag like
   `CONTINUOUS_LEARNING`.

8. **Use robust statistics everywhere.** Median/MAD (not mean/std) for thresholds.
   MAD × 1.4826 for σ estimate. Percentiles (not mean±kσ) for calibration.

9. **Check for level shifts before fitting trend models.** Maintenance resets
   (health jumps > 15%) must be detected; use only post-jump data.

10. **Initialise variables before all conditional paths.** Uninitialized variables
    in `finally`/`except` blocks cause cascading failures.

---

*Last updated: 2026-02-20 (v11.15.3)*

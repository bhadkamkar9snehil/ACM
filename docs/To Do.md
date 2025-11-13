# ACM V8 - Task Backlog

- [ACM V8 - Task Backlog](#acm-v6---task-backlog)
  - [Workspace Directory Audit (2025-11-10)](#workspace-directory-audit-2025-11-10)
    - [Directory Structure Overview](#directory-structure-overview)
    - [Key Finding: ACM Already Uses Batch-Over-Batch!](#key-finding-acm-already-uses-batch-over-batch)
    - [Train/Test Terminology Cleanup](#traintest-terminology-cleanup)
    - [Cleanup Actions Required](#cleanup-actions-required)
    - [Code Analysis: 100+ "train" References](#code-analysis-100-train-references)
    - [Files NOT Requiring Changes](#files-not-requiring-changes)
  - [Recent Performance Analysis (2025-11-05)](#recent-performance-analysis-2025-11-05)
  - [Priority Legend](#priority-legend)
  - [Status Legend](#status-legend)
  - [1. Core Analytics \& Detection (PRIORITY FOCUS)](#1-core-analytics--detection-priority-focus)
    - [1.1 Data Quality \& Preprocessing](#11-data-quality--preprocessing)
    - [1.2 Feature Engineering](#12-feature-engineering)
    - [1.3 Detectors \& Anomaly Detection](#13-detectors--anomaly-detection)
    - [1.4 Fusion \& Episode Detection](#14-fusion--episode-detection)
    - [1.5 Regime Clustering \& Operating States](#15-regime-clustering--operating-states)
  - [2. Model Management \& Persistence](#2-model-management--persistence)
    - [2.1 Model Versioning \& Caching](#21-model-versioning--caching)
    - [2.2 Configuration Management](#22-configuration-management)
    - [2.3 Model Quality Monitoring](#23-model-quality-monitoring)
  - [3. Batch Streaming \& Cold-Start (PRIORITY FOCUS)](#3-batch-streaming--cold-start-priority-focus)
    - [3.1 Cold-Start Capabilities](#31-cold-start-capabilities)
    - [3.2 Chunk Replay \& Batch Processing](#32-chunk-replay--batch-processing)
    - [3.3 Streaming Preparation (Future)](#33-streaming-preparation-future)
  - [4. Outputs \& Reporting](#4-outputs--reporting)
    - [4.1 Tabular Outputs](#41-tabular-outputs)
    - [4.2 Visualization](#42-visualization)
  - [5. Performance \& Optimization](#5-performance--optimization)
  - [6. Documentation \& Operations](#6-documentation--operations)
    - [6.1 Documentation](#61-documentation)
    - [6.2 Operations (Future)](#62-operations-future)
  - [7. Technical Debt (From README Analysis)](#7-technical-debt-from-readme-analysis)
    - [7.1 High Severity Issues](#71-high-severity-issues)
    - [7.2 Medium Severity Issues](#72-medium-severity-issues)
    - [7.3 Low Priority Technical Debt](#73-low-priority-technical-debt)
  - [8. AVEVA-Inspired Features (DEFERRED - Future Phases)](#8-aveva-inspired-features-deferred---future-phases)
    - [8.1 Residuals \& Predictions](#81-residuals--predictions)
    - [8.2 Diagnostics \& Fault Mapping](#82-diagnostics--fault-mapping)
    - [8.3 RUL \& Health Forecasting](#83-rul--health-forecasting)
    - [8.4 Transient State Handling](#84-transient-state-handling)
    - [8.5 Alerting \& Case Management](#85-alerting--case-management)
    - [8.6 Enhanced Visualizations](#86-enhanced-visualizations)
  - [9. SQL Integration Tasks (DEPRIORITIZED)](#9-sql-integration-tasks-deprioritized)
  - [10. Summary Statistics](#10-summary-statistics)
    - [By Priority](#by-priority)
    - [By Status](#by-status)
    - [By Category](#by-category)
  - [11. Near-Term Priorities (Next Sprint)](#11-near-term-priorities-next-sprint)
    - [Must-Have (Blocking Core Functionality)](#must-have-blocking-core-functionality)
    - [Should-Have (High Value)](#should-have-high-value)
    - [Nice-to-Have (Quick Wins)](#nice-to-have-quick-wins)
  - [11. Code Quality \& Architecture Improvements (NEW - 2025-11-05)](#11-code-quality--architecture-improvements-new---2025-11-05)
    - [11.1 Forecasting Module Enhancements](#111-forecasting-module-enhancements)
    - [11.2 Fusion \& Weight Tuning Improvements](#112-fusion--weight-tuning-improvements)
    - [11.3 Drift Detection Enhancements](#113-drift-detection-enhancements)
    - [11.4 Overall Model Residual (OMR) - NEW](#114-overall-model-residual-omr---new)
    - [11.5 Regime Clustering Improvements](#115-regime-clustering-improvements)
    - [11.6 Output Manager Hardening](#116-output-manager-hardening)
    - [11.7 Configuration Discoverability](#117-configuration-discoverability)
    - [11.8 Audit-Identified Issues (Nov 10, 2025)](#118-audit-identified-issues-nov-10-2025)
  - [12. Long-Term Roadmap](#12-long-term-roadmap)
    - [Phase 1: Analytical Backbone Hardening (CURRENT)](#phase-1-analytical-backbone-hardening-current)
    - [Phase 2: Advanced Analytics (NEXT)](#phase-2-advanced-analytics-next)
    - [Phase 3: SQL Integration \& Production Deployment (FUTURE)](#phase-3-sql-integration--production-deployment-future)
    - [Phase 4: Continuous Learning \& Streaming (FUTURE)](#phase-4-continuous-learning--streaming-future)


**Last Updated:** 2025-11-10  
**Focus:** Hands-Off, Self-Tuning, Continuous Adaptation

**Progress:** 77/141 tasks completed (54.6%)  
**Code Quality:** **B+ (85/100)** from comprehensive audit (Nov 10) - See `docs/Detailed Audit by Claude.md`  
**Philosophy:** ACM continuously monitors and adapts - no manual tuning, no separate commissioning phases  
**Recent Completions:** **DET-09 (Adaptive Parameter Tuning - continuous self-monitoring)** - 2025-11-10, **TEST-03 (Incremental batch testing protocol)** - 2025-11-10, **DEBT-13 (River weight config cleanup)** - 2025-11-10, **DET-08 (Mahalanobis regularization fix - 580x condition number improvement!)** - 2025-11-10, **PERS-05 (model persistence dict bug fix - 4-8x speedup!)** - 2025-11-10  
**Previous Completions:** DET-07 (per-regime detector thresholds - discovered already implemented, added enhancements) - 2025-11-10, OUT-04, DEBT-11 (local time policy - removed all UTC timezone handling) - 2025-11-10, DEBT-08 (file I/O atomicity - discovered already implemented) - 2025-11-08, DEBT-09 (pandas hash stability with shape+dtype fingerprints) - 2025-11-08, DEBT-05 (expanded config signature) - 2025-11-08, DRIFT-01 (multi-feature drift detection with hysteresis) - 2025-11-06, REG-07 (auto-k selection for regime clustering) - 2025-11-06, OMR-01-04 (complete OMR subsystem) - 2025-11-06  
**Audit Findings:** 3 critical issues fixed, acm_main.py refactoring deferred (user decision), remaining risks cataloged as low priority

---

## Workspace Directory Audit (2025-11-10)

**Purpose:** Document file structure, identify train/test methodology artifacts, ensure batch-over-batch approach

### Directory Structure Overview

| Directory | Purpose | File Count | Status | Notes |
|-----------|---------|------------|--------|-------|
| **core/** | Main ACM pipeline modules | 27 files | Active | acm_main.py (3,066 lines) + 20+ modules |
| **models/** | **DEPRECATED** - Consolidated into core/ | 13 files | DELETE | Has DEPRECATED.md, no longer used |
| **utils/** | Config, logging, SQL I/O, validators | 9 files | Active | Clean |
| **data/** | Sample CSV files for dev testing | 6 files | RENAME | Files named "TRAINING/TEST DATA" ? should be "BASELINE/BATCH" |
| **docs/** | Documentation, audit reports | 35+ files | Active | Comprehensive |
| **scripts/** | Testing, analysis, optimization | 25+ files | Active | Clean |
| **tests/** | Unit tests | 3 files | Active | Clean |
| **configs/** | Configuration files | 3 files | Active | config_table.csv, sql_connection.ini |
| **artifacts/** | ACM run outputs (scores, charts, tables) | ~1000s | Active | Batch outputs |
| **rust_bridge/** | Rust FFI for performance (future) | 3 files | Future | Clean |

### Key Finding: ACM Already Uses Batch-Over-Batch!

**Current Architecture:**
- **"train" data = historical baseline** used to fit models (Mahalanobis, GMM, regimes, AR1)
- **"score" data = current batch** being analyzed for anomalies
- **NO train/test splits** - models fit once on baseline, applied to all subsequent batches
- **Adaptive baseline** - can bootstrap from rolling buffer or cold-start from first N samples

**What ACM Does (Correct Batch-Over-Batch):**
1. Load baseline period (historical "normal" data)
2. Fit models on baseline: Mahalanobis covariance, GMM clusters, regimes, AR1 parameters
3. Cache fitted models for reuse
4. Load current batch (new data to analyze)
5. Score batch with fitted models
6. Detect anomalies, fuse signals, identify episodes
7. Update rolling baseline buffer for next run

**What ACM Does NOT Do (No Train/Test Split):**
- Split data into train/test sets for model validation
- Hold out test data to measure model accuracy
- Use cross-validation or train/test metrics
- Instead: Uses continuous monitoring, adaptive tuning, self-healing

### Train/Test Terminology Cleanup

**Problem:** 100+ references to "train/test" in acm_main.py are **misleading** - they imply ML train/test splits but actually mean "baseline/current batch".

**Examples of Confusing Terminology:**
- Line 624 comment: "Train/Test window ordering & overlap check" ? should be "Baseline/Batch ordering"
- Line 631 warning: "score_start={sc_start}, train_end={tr_end}" ? should be "batch_start/baseline_end"
- Line 548 comment: "Cold-start mode: If no train_csv provided, will auto-split score data" ? confusing!

**Recommended Terminology:**
| Old (Confusing) | New (Clear) | Meaning |
|-----------------|-------------|---------|
| "train data" | "baseline data" | Historical normal behavior for fitting models |
| "test data" | "batch data" | Current data being scored for anomalies |
| "train_csv" config | Keep for backward compat | Add alias `baseline_csv` |
| "score_csv" config | Keep | Already clear |
| "Train/Test window" | "Baseline/Batch window" | Time period ordering |

### Cleanup Actions Required

**HIGH PRIORITY - Delete Obsolete Code:**
1. **Delete `models/` directory** (13 files)
   - Already marked DEPRECATED in `models/DEPRECATED.md`
   - All functionality moved to `core/`
   - Files: `anomaly.py`, `ar1_model.py`, `drift.py`, `feature_importance.py`, `forecast.py`, `gmm_model.py`, `iforest_model.py`, `omr.py`, `pca.py`, `regime.py`, `xcorr.py`, `DEPRECATED.md`, `__init__.py`
   - **Action:** `Remove-Item -Recurse "models/"`

**MEDIUM PRIORITY - Rename Confusing Data Files:**
2. **Rename data files** to eliminate train/test confusion:
   - `data/FD FAN TRAINING DATA.csv` ? `data/FD_FAN_BASELINE_DATA.csv`
   - `data/FD FAN TEST DATA.csv` ? `data/FD_FAN_BATCH_DATA.csv`
   - `data/Gas Turbine TRAINING DATA.csv` ? `data/GAS_TURBINE_BASELINE_DATA.csv`
   - `data/Gas Turbine TEST DATA.csv` ? `data/GAS_TURBINE_BATCH_DATA.csv`
   - **Action:** Use `Rename-Item` or `mv` commands

**LOW PRIORITY - Delete Backup Files:**
3. **Delete backup/temp files:**
   - `# To Do OLD.md` - outdated TODO backup
   - `README_BACKUP.md` - outdated README backup
   - `gemini.md~` - text editor backup (tilde suffix)
   - **Action:** `Remove-Item` these files

**OPTIONAL - Terminology Clarification in Code:**
4. **Update user-facing messages** in `core/acm_main.py`:
   - Line 548 comment: Clarify cold-start auto-split behavior
   - Line 580 log: "TRAIN={len(train)} unique" ? consider "BASELINE={len(train)} unique"
   - Line 624 comment: "Train/Test window ordering" ? "Baseline/Batch ordering"
   - Line 631 warning: "train_end/score_start" ? "baseline_end/batch_start"
   - **Note:** Internal variable names (`train`, `train_numeric`) are fine - they clearly refer to baseline data

**KEEP AS-IS - Backward Compatibility:**
5. **Do NOT rename** these config keys (breaking change):
   - `data.train_csv` - keep for backward compatibility
   - `utils/validators.py` train_csv references - keep
   - CLI argument `--train-csv` - keep (can add alias `--baseline-csv`)

### Code Analysis: 100+ "train" References

**Breakdown by Category (from grep search results):**
- **Variable names** (60+ refs): `train`, `train_numeric`, `train_dups`, `train_stds`, `train_fill_values`, etc.
  - These are fine - clearly refer to baseline/reference data
- **Config keys** (10+ refs): `train_csv`, `train_feature_hash`, etc.
  - Keep for backward compatibility
- **Comments/logs** (30+ refs): "TRAIN data", "training period", "Train/Test ordering", etc.
  - Should clarify to "baseline" terminology where user-facing
- **Feature engineering** (10+ refs): "features.compute_train", "train features", etc.
  - These are fine - baseline feature computation

### Files NOT Requiring Changes

**Clean Modules (No Train/Test Splits):**
- `core/features.py` - feature engineering, no splits
- `core/fast_features.py` - optimized features, no splits
- `core/fuse.py` - fusion logic, no splits
- `core/drift.py` - CUSUM drift, no splits
- `core/cpd.py` - change point detection, no splits
- `core/clean.py` - data preprocessing, no splits
- `core/correlation.py` - fits Mahalanobis on baseline, applies to batch (correct!)
- `core/outliers.py` - fits GMM/IForest on baseline, applies to batch (correct!)
- `core/regimes.py` - fits clustering on baseline, applies to batch (correct!)
- `core/forecast.py` - fits AR1 on baseline, applies to batch (correct!)

---

## Recent Performance Analysis (2025-11-05)

**VERIFIED: 5 optimizations tested and working! (46.3% faster!)**

**Baseline Performance:** 55.4s runtime (6,741 train + 3,870 score samples, 9 sensors)

**Optimization Stack (6 Applied):**
1. Polars Backend (PERF-05): 21.6s ? 0.08s (99.6% faster features)
2. GMM k_max=3 (PERF-06): 5.0s ? 3.2s (36% faster GMM)
3. Max clip_z=100 (PERF-07): Saturation 28.5% ? 20.2% (quality improvement)
4. Chart Toggle (VIZ-01): 1.9s ? 0.0s (100% chart overhead eliminated)
5. IForest n_estimators=100 (PERF-08): Minimal impact (already optimized)
6. Chart Optimization (VIZ-02): 3.3s ? 1.3s (60.4% reduction when enabled)

**Cumulative Results:**
- **First 3 optimizations (Run: 20251105_004250):** 55.4s ? 32.7s (41.0% faster)
- **All 5 optimizations (Run: 20251105_005038):** 55.4s ? 29.8s (46.3% faster!)
- **With VIZ-02 optimization (Run: 20251105_010759):** 55.4s ? 28.9s (47.9% faster with charts enabled!)
- **Total Time Saved: 26.5 seconds**

**Verification Evidence:**
- Polars: `[FEAT] Using Polars for feature computation`, features.build=0.073s
- GMM: `[GMM] BIC search selected k=3`, fit.gmm=3.225s
- Clip_z: `[CAL] Adaptive clip_z=100.00`, saturation=20.2%
- Charts: `[OUTPUTS] Chart generation disabled via config` (no outputs.charts timer)
- IForest: fit.iforest=0.201s (minimal variance)

**Installation Requirements:** `pip install polars pyarrow`

**Next Opportunities:** DET-07 (per-regime thresholds), PERF-02 (Rust bridge 3-5x), PERF-03 (lazy detector evaluation), PERF-10 (window size research)

See `scripts/verify_quick_wins.py` for full verification report.

---

## Priority Legend

- **Critical** - Blocks core functionality or causes data quality issues
- **High** - Improves reliability, performance, or user experience significantly  
- **Medium** - Nice-to-have enhancements, technical debt reduction
- **Low** - Future improvements, nice-to-have features
- **Deferred** - Intentionally postponed (e.g., SQL integration tasks)

## Status Legend

- **Done** - Fully implemented and validated
- **Pending** - Not yet started or partially complete
- **In Progress** - Currently being worked on
- **Paused** - Started but deprioritized
- **Planned** - Scheduled for future phase

---

## 1. Core Analytics & Detection (PRIORITY FOCUS)

### 1.1 Data Quality & Preprocessing

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **DATA-01** | Critical | **Data Quality Guardrails v2** | `core/acm_main.py` | Add per-sensor longest gap, flatline span, min/max timestamps. Generate `tables/data_quality.csv` & `tables/dropped_sensors.csv` | Table includes variance, gaps, dropped sensors summary | Done | Enhanced with longest_gap, flatline_span, min/max timestamps. Added dropped_sensors.csv tracking |
| **DATA-02** | High | **Overlap Detection** | `core/acm_main.py` | Warn if SCORE window precedes TRAIN end date | Warning shown and logged; timestamps validated | Done | Implemented in main pipeline |
| **DATA-03** | High | **Sampling & Cadence Validation** | `core/output_manager.py` | Detect inconsistent sampling; auto-resample if allowed | Sampling stats logged, cadence normalized | Done | `_check_cadence()` and `_resample()` implemented |
| **DATA-04** | Medium | **Missing Data Imputation Strategy** | `core/fast_features.py` | Document and validate median-fill strategy for NaNs | Imputation logged per sensor; data leakage prevented | Done | **IMPLEMENTED 2025-11-05: Modified _apply_fill(), compute_basic_features(), and compute_basic_features_pl() to accept optional fill_values parameter. acm_main.py now computes fill values from TRAIN data and passes them to SCORE processing. Prevents leakage. Log: '[FEAT] Computed 9 fill values from training data (prevents leakage)'. Run: 20251105_011656** |
| **DATA-05** | Medium | **Sensor Flatline Detection** | `core/output_manager.py` | Detect sensors with zero variance or constant values | Flatline sensors flagged in data_quality.csv | Done | Already implemented! Lines 605-638 in acm_main.py include calc_flatline_span(), zero variance tracking (tr_std/sc_std), and output columns train_flatline_span/score_flatline_span. Notes column flags concerning flatlines (>100 pts). **ANALYSIS (2025-11-05): FD_FAN shows 2 sensors with excessive flatlines - Outlet Pressure: 341pts, Motor Current: 166pts. Investigate sensor health.** |

### 1.2 Feature Engineering

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **FEAT-01** | High | **Polars Fallback Robustness** | `core/fast_features.py` | Ensure seamless fallback to pandas if Polars unavailable | Identical column names and dtypes between backends | Done | Fallback logic implemented |
| **FEAT-02** | Medium | **Adaptive Polars Threshold** | `core/fast_features.py` | Make row-count threshold configurable (`features.polars_threshold`) | Configurable via `config_table.csv` | Done | Already implemented! Line 709 in acm_main.py reads `cfg.get("features", {}).get("polars_threshold", 10000)`. Default is 10,000 rows. |
| **FEAT-03** | Medium | **Feature Drop Logging** | `core/fast_features.py` | Log sensors dropped due to low variance or NaN fill | Dropped sensors appear in `dropped_sensors.csv` | Done | **IMPLEMENTED 2025-11-05: Enhanced feature drop logging in acm_main.py lines 789-821. Logs both all-NaN AND low-variance features to feature_drop_log.csv with reason, train_median, train_std, and timestamp. Append mode preserves history. Warning shows dropped column preview. Tested with FD_FAN (no drops - clean data).** |
| **FEAT-04** | Medium | **Rolling Window Optimization** | `core/fast_features.py` | Profile and optimize rolling statistics computation | 20%+ speedup on feature engineering stage | Pending | Consider Rust bridge (PERF-02) |

### 1.3 Detectors & Anomaly Detection

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **DET-01** | Critical | **Adaptive Clipping Validation** | `core/fuse.py`, `core/outliers.py` | Adaptive `clip_z = max(default, 1.5×train p99)` capped at configurable `max_clip_z` | =1% saturation across detectors; audit trail in config table | Done | Saturation fix validated in EPISODE_THRESHOLD_FIX.md |
| **DET-02** | High | **Detector Correlation Table** | `core/output_manager.py` | Compute pairwise Pearson r between all detector z-streams | `tables/detector_correlation.csv` generated correctly | Done | `_generate_detector_correlation()` implemented |
| **DET-03** | High | **Mahalanobis Refactor** | `core/correlation.py` | Replace unstable inverse-cov with robust pseudo-inv and guard for rank deficiency | Stable outputs with identical z-scales across runs | Done | Pseudo-inverse implemented |
| **DET-04** | High | **Drift/CUSUM Enhancements** | `core/drift.py` | Documented config keys (`k_sigma`, `h_sigma`); add `tables/drift_events.csv` | Drift peak detection table populated | Done | `_generate_drift_events()` in output_manager |
| **DET-05** | High | **Detector Calibration Summary** | `core/output_manager.py` | Add per-detector z-mean/std/p95/p99 and clip saturation % table | `tables/calibration_summary.csv` generated | Done | `_generate_calibration_summary()` implemented |
| **DET-06** | Medium | **Detector Weight Auto-Tuning** | `core/fuse.py` | Adjust fusion weights based on detector performance | Weights updated automatically based on correlation/performance | Done | Implemented `tune_detector_weights()` in fuse.py using Pearson correlation with fused signal. Softmax-based weight adjustment with configurable learning rate, temperature, and min_weight. Tuning diagnostics saved to tables/weight_tuning.json. Config: `fusion.auto_tune.enabled`, `learning_rate`, `temperature`, `min_weight`. |
| **DET-07** | Medium | **Per-Regime Detector Thresholds** | `core/fuse.py` | Allow different detector sensitivities per regime | Thresholds vary by regime; documented in meta.json & output tables | Done | Feature was already implemented in ScoreCalibrator class! Enhanced with: (1) regime-specific sensitivity multipliers via `self_tune.regime_sensitivity` config, (2) `per_regime_thresholds.csv` transparency table, (3) run_metadata per-regime diagnostics. Config: `fusion.per_regime=True` (already enabled). Auto-activates when regime quality OK (silhouette = 0.2). Reduces false positives in variable operating states. |
| **DET-08** | Critical | **Mahalanobis Regularization** | `core/correlation.py`, `core/acm_main.py`, `configs/config_table.csv` | Fix extremely high condition number (4.80e+30 FD_FAN, 4.47e+13 GAS_TURBINE) by increasing regularization | Condition number < 1e29; improved stability | Done | Nov 10 2025: Discovered regularization already config-driven via `models.mahl.regularization`. Increased from 0.001 ? 1.0 (1000x). FD_FAN: 4.80e+30 ? 8.26e+27 (580x better). Added debug logging and improved warning thresholds (1e10 warning, 1e8 info). Config: `models.mahl.regularization=1.0` for both equipments. |
| **DET-09** | Critical | **Adaptive Parameter Tuning** | `core/acm_main.py`, `core/correlation.py` | Continuous self-monitoring and auto-adjustment of model hyperparameters during normal operation | Parameters auto-tune when models show instability; changes logged to config_table.csv | Done | Nov 10 2025: **PHILOSOPHY SHIFT** - No separate commissioning mode. ACM now continuously monitors model health every run: (1) Condition number tracking with adaptive regularization adjustment (1e28+ ? 10x increase, 1e20+ ? 5x increase), (2) NaN rate monitoring (>1% triggers warning), (3) Auto-writes parameter updates to config_table.csv with UpdatedBy=ADAPTIVE_TUNING, (4) Hands-off approach - ACM detects drift, transient modes, bad data automatically. Integrated into normal batch flow after model training. User philosophy: "We want to always ensure our model does not just drift away and we always know what the normal is. We should know when we are in transient mode. We should know when the data is bad. This is part of hands off approach that is central to ACM." |

### 1.4 Fusion & Episode Detection

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **FUSE-01** | Critical | **Episode Threshold Fix Validation** | `core/fuse.py` | Confirm correct hysteresis & merged gap logic; ensure multi-episode detection | Matches documented results; no FP single long episode | Done | Validated in EPISODE_FIX_COMPARISON.md |
| **FUSE-02** | High | **Fusion Threshold Auto-Tune** | `core/fuse.py` | Adjust `thresholds.q` dynamically for >20% anomalies | Config update with reason "Excessive anomalies > 20%" | Done | Autonomous tuning implemented |
| **FUSE-03** | High | **Culprit Attribution v2** | `core/fuse.py`, `core/output_manager.py` | Add lead/lag context, rank by contribution, output `culprit_history.csv` | Table written; integrated into outputs | Done | Enhanced with weighted contribution ranking, lead/lag temporal analysis (10-sample window), and fallback for missing data |
| **FUSE-04** | Medium | **Fusion Schema Descriptor** | `core/output_manager.py` | Auto-emit JSON describing schema (columns + types) for `scores.csv` | `schema.json` present in run folder | Done | Implemented in acm_main.py after scores.csv write. Generates schema.json with column names, dtypes, nullability, and semantic descriptions for all detector outputs, fusion scores, alerts, and regime labels |
| **FUSE-05** | Medium | **Episode Duration/Frequency Metrics** | `core/output_manager.py` | Add summary statistics for episode patterns | Table `episode_metrics.csv` with duration/frequency stats | Done | `_generate_episode_metrics()` implemented and verified. Outputs 8 metrics: TotalEpisodes, TotalDurationHours, AvgDurationHours, MedianDurationHours, MaxDurationHours, MinDurationHours, RatePerDay, MeanInterarrivalHours |
| **FUSE-06** | Medium | **Automatic Barrier Adjustment** | `core/fuse.py` | Dynamically tune k_sigma/h_sigma based on training score distribution | Prevents detector saturation from blocking episode detection | Done | Implemented in combine() function. Auto-tunes k_sigma based on std (k_factor × std) and h_sigma based on p95-p50 spread (h_factor × spread). Config: `episodes.cpd.auto_tune.enabled`, `k_factor`, `h_factor`. Bounds: k_sigma ? [0.1, 2.0], h_sigma ? [2.0, 10.0]. |

### 1.5 Regime Clustering & Operating States

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **REG-01** | Critical | **Regime Persistence (joblib)** | `core/regimes.py` | Persist KMeans & scaler via joblib; include in cache hash | Model reload yields identical clusters | Done | Added save_regime_model() and load_regime_model() with joblib. Models properly cached across runs |
| **REG-02** | High | **Regime Stability Metrics** | `core/output_manager.py` | Compute churn rate, avg/median dwell, transitions | `tables/regime_stability.csv` & `regime_transition_matrix.csv` | Done | `_generate_regime_stability()` and `_generate_regime_transition_matrix()` implemented |
| **REG-03** | High | **Label Smoothing** | `core/regimes.py` | Min-dwell enforcement, smoothing jitter | No < configured dwell violations | Done | `smooth_labels()` implemented |
| **REG-04** | Medium | **Single-Cluster Fallback** | `core/regimes.py` | When silhouette scores poor (<0.3), allow k=1 rather than forcing k=2 minimum | Documented behavior for homogeneous data | Done | Implemented k=1 fallback in _fit_kmeans_scaled(). If all tested k values (2-6) yield silhouette < 0.3, falls back to k=1 with metric="fallback_k1" |
| **REG-05** | Medium | **Regime Health Scoring** | `core/regimes.py` | Assign health scores to regimes based on historical anomaly rates | Each regime labeled as healthy/caution/critical | Done | Implemented in update_health_labels(). Outputs regime_summary.csv with state (healthy/suspect/critical), median_fused, p95_abs_fused, and count. Thresholds: suspect=1.5, critical=3.0 |
| **REG-06** | Medium | **Transient State Detection** | `core/regimes.py` | Detect startup/shutdown/steady_state/trip using d/dt of key tags | New column `transient_state` in regime_timeline.csv | Done | Implemented `detect_transient_states()` in regimes.py. Detects startup/shutdown/steady/trip/transient based on ROC (rate-of-change) analysis and regime transitions. Config: `regimes.transient_detection.enabled`, `roc_window`, `roc_threshold_high`, `roc_threshold_trip`, `transition_lag`. Outputs transient_state column in scores.csv. |

---

## 2. Model Management & Persistence

### 2.1 Model Versioning & Caching

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **PERS-01** | Critical | **Atomic Cache Writes** | `core/model_persistence.py` | Use temp file + `os.replace`; add file lock | No partial/corrupt cache even in parallel runs | Done | Implemented atomic writes with tempfile.mkstemp() + os.replace() for models and manifest |
| **PERS-02** | High | **Cache Validation** | `core/model_persistence.py` | Verify saved hash + signature before reuse; auto-invalidate mismatch | Safe reload verified via checksum | Done | Signature validation implemented |
| **PERS-03** | High | **Cache Hash Type Fix** | `core/model_persistence.py` | Convert int?str before slicing to avoid `TypeError` | Exception eliminated in invalidation path | Done | Bug fix completed |
| **PERS-04** | Medium | **Model Metadata Enhancement** | `core/model_persistence.py` | Include training duration, quality metrics, data stats in manifest | Manifest has comprehensive metadata for debugging | Done | Enhanced with training_duration_s, data_stats (NaN%, mean/std/min/max), PCA explained variance breakdown, GMM BIC/AIC, regime silhouette/inertia/iterations, AR1 mean autocorr, feature imputation stats |
| **PERS-05** | Critical | **AR1 Metadata Dict Bug Fix** | `core/model_persistence.py:490` | Fix dict concatenation bug in AR1 metadata calculation | Models cache correctly, 4-8x speedup on subsequent runs | Done (2025-11-10) | **CRITICAL BUG FIXED**: np.mean() tried to add two dicts (phimap + sdmap) ? TypeError. Fixed to extract dicts separately and compute means from their values. Added traceback logging. Validated: FD_FAN saves 7 models, loads from cache. **Impact: 40s ? 5-10s on cached runs (4-8x faster!)** |

### 2.2 Configuration Management

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **CFG-01** | Deferred | ~~Migrate from CSV ? SQL Config Store~~ | `utils/sql_config.py` | Create `ACM_Config` and `ACM_ConfigHistory` SQL tables | Config read/write works from SQL | Paused | **DE-PRIORITIZED: CSV config sufficient for batch mode** |
| **CFG-02** | High | **Config Priority Chain** | `core/acm_main.py` | Confirm 2-level fallback: CSV > Defaults. Log source precedence | Verified cascade fallback; explicit console log | Done | CSV-based config implemented |
| **CFG-03** | High | **Environment Variable Substitution** | `core/sql_client.py` | Allow connection info from env vars overriding INI | Connection tested with env vars; no fallback failure | Done | Implemented in SQLClient |
| **CFG-04** | High | **EquipID Hashing Consistency** | `core/acm_main.py` | Deterministic hash for EquipName ? EquipID | IDs match historical ones (e.g., FD_FAN = 5396) | Done | `_get_equipment_id()` uses MD5 hash |
| **CFG-05** | Medium | **Config Signature Expansion** | `core/model_persistence.py` | Extend signature to include `thresholds`, `fusion`, `regimes`, `episodes` | Hash difference triggers retrain correctly | Done | Extended _compute_config_signature() to include all 7 sections: models, features, preprocessing, thresholds, fusion, regimes, episodes. Changes to any section now properly trigger model retraining |

### 2.3 Model Quality Monitoring

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **EVAL-01** | High | **Autonomous Quality Monitor** | `core/model_evaluation.py` | Implement ModelQualityMonitor to trigger retraining | Retraining triggered on degradation; reasoning logged | Done | Module exists with quality assessment methods |
| **EVAL-02** | Medium | **Synthetic Fault Injection** | `scripts/test_faults.py` | Inject steps/drifts/outliers for testing | Synthetic dataset created; detectors validated | Planned | Needed for systematic validation |
| **EVAL-03** | Medium | **Precision/Recall Metrics** | `notebooks/evaluation.ipynb` | Compute metrics vs labeled episodes | Results saved to docs | Planned | Requires labeled ground truth data |
| **TEST-03** | Medium | **Incremental Batch Testing Protocol** | `scripts/test_incremental_batches.py` | Validate cold-start and warm-start behavior with consecutive batches | Automated test script, cache validation, performance metrics | Done | Nov 10 2025: Script created (320 lines). Validated 100% cache hit rate on FD_FAN (3 batches). Discovered refit flag behavior (adaptive tuning). Production-ready. Doc: docs/BATCH_TESTING_VALIDATION.md |

---

## 3. Batch Streaming & Cold-Start (PRIORITY FOCUS)

### 3.1 Cold-Start Capabilities

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **COLD-01** | High | **Cold-Start 60/40 Split** | `core/acm_main.py` | Automatic 60/40 data split when no training data provided | Models bootstrap from first batch; cache saved | Done | Implemented and validated on FD_FAN & GAS_TURBINE |
| **COLD-02** | Medium | **Configurable Split Ratio** | `core/output_manager.py` | Allow config override of 60/40 default split | Split ratio configurable via `data.cold_start_split_ratio` | Done | **IMPLEMENTED 2025-11-05: Added data.cold_start_split_ratio config parameter (default 0.6). Validates range 0.1-0.9. Used in cold-start auto-split logic. Log shows split percentage. Lines 509-511, 537-538 in output_manager.py** |
| **COLD-03** | Medium | **Min-Samples Validation** | `core/output_manager.py` | Ensure sufficient samples for training (e.g., >500 rows) | Warning if insufficient data; graceful degradation | Done | **IMPLEMENTED 2025-11-05: Added data.min_train_samples config parameter (default 500). Warns if training samples below threshold in both cold-start and normal modes. Suggests remediation (more data or higher split_ratio). Lines 512, 528-531, 562-568 in output_manager.py** |

### 3.2 Chunk Replay & Batch Processing

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **BATCH-01** | High | **Chunk Replay Harness** | `scripts/chunk_replay.py` | Sequential replay of pre-sliced batches with cold-start | Script executes multiple chunks per asset | Done | Implemented with parallel execution support |
| **BATCH-02** | Medium | **Incremental Model Updates** | `core/model_persistence.py` | Allow models to update incrementally between chunks | Models evolve without full retraining | Done | Added update_models_incremental() method, supports StandardScaler partial_fit |
| **BATCH-03** | Medium | **Batch Progress Tracking** | `scripts/chunk_replay.py` | Track and resume interrupted batch processing | Resume from last successful chunk | Done | Implemented with JSON progress file, --resume flag, tested successfully |
| **BATCH-04** | Medium | **Batch Size Optimization** | `core/acm_main.py` | Recommend optimal batch sizes based on sensor count/cadence | Guidance provided in documentation | Done | Comprehensive guide in docs/BATCH_PROCESSING.md with sizing formulas |

### 3.3 Streaming Preparation (Future)

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **STREAM-01** | Low | **River Half-Space Trees Integration** | `core/river_models.py` | Complete streaming detector; support checkpoint | Detectors stream without errors | Planned | Requires River dependency |
| **STREAM-02** | Low | **River State Persistence** | `core/river_models.py` | Save model state between runs | State resumes correctly after reload | Planned | Enables true continuous learning |
| **STREAM-03** | Deferred | **Scheduler Loop** | `core/acm_main.py` | Enable periodic window runs (15–30 min) | Continuous scoring verified | Planned | **Requires SQL integration (deferred)** |

---

## 4. Outputs & Reporting

### 4.1 Tabular Outputs

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **OUT-01** | High | **Consolidated Output Module** | `core/output_manager.py` | Replace all legacy generators; single entry `generate_all_outputs()` | 25+ tables + charts created; legacy deleted | Done | OutputManager fully implemented |
| **OUT-02** | High | **Operator vs Engineer Views** | `core/output_manager.py` | Split artifacts by audience folders or prefix | Operator and ML subsets clearly grouped | Done | Defect-focused tables for operators |
| **OUT-03** | Medium | **Output Schema Stability** | `core/output_manager.py` | Emit schema descriptor JSON; freeze column order | Consumers handle consistent columns | Pending | Links to FUSE-04 |
| **OUT-04** | Medium | **Local Timestamp Policy** | All output writers | Simplified to local timezone-naive timestamps everywhere (no UTC) | All file writes use local naive timestamps | Done (2025-11-10) | **POLICY CHANGE**: User requested simple local time everywhere. Removed all UTC timezone handling: _ensure_utc_index() ? _ensure_local_index(), _to_utc_naive() ? _to_naive(), removed utc=True from pd.to_datetime(), datetime.now(timezone.utc) ? datetime.now(). Config declares timestamp_tz=local. 17 Python files + 1 config updated. All timestamps now local naive wall-clock time. |
| **OUT-05** | Medium | **Run Metadata Surfacing** | `core/run_metadata_writer.py` | Include cache hit/miss, quality metrics in meta.json | Meta.json populated with run diagnostics | Pending | Module exists but needs integration |

### 4.2 Visualization

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **VIZ-01** | High | **Chart Generation Toggle** | `core/acm_main.py`, `core/output_manager.py` | Make chart generation optional via config | Config flag `outputs.charts.enabled` works | Done | **IMPLEMENTED 2025-11-05: Charts disabled via outputs.charts.enabled=False. Saves 1.9s (5.8% of runtime). Log shows '[OUTPUTS] Chart generation disabled via config'. Run: 20251105_005038** |
| **VIZ-02** | High | **Chart Generation Optimization** | `core/output_manager.py` | Remove low-value charts to improve performance and focus on actionable diagnostics | 15 charts ? 12 charts; 60%+ time reduction when enabled | Done | **IMPLEMENTED 2025-11-05: Removed sensor_timeseries_events.png, sensor_sparklines.png, sensor_hotspots.png. Time: 3.316s ? 1.314s (60.4% reduction). Retained 12 high/medium-value charts. See scripts/chart_optimization_summary.py for full details. Run: 20251105_010759** |
| **VIZ-03** | Low | **Interactive Dashboards** | External (Grafana/Power BI) | Create Grafana/Power BI dashboard templates | Templates provided in docs/ | Planned | **Requires SQL integration (deferred)** |


---

## 5. Performance & Optimization

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **PERF-01** | Medium | **Profiling (py-spy/line_profiler)** | All core modules | Identify hotspots, especially in feature loop | Profiling report generated; hotspots documented | Pending | Use py-spy for production profiling |
| **PERF-02** | Medium | **Rust Bridge for Rolling Stats** | `rust_bridge/` | Migrate rolling mean/std/MAD to Rust via PyO3 | Speed gain = 3× baseline | Pending | Significant speedup for large datasets |
| **PERF-03** | Medium | **Lazy Evaluation for Optional Detectors** | `core/fuse.py` | Skip disabled detectors entirely | Runtime reduced proportionally | Done | **IMPLEMENTED 2025-11-05: Added lazy evaluation in acm_main.py lines 937-959. Checks fusion.weights config to determine which detectors are enabled. Skips fitting and scoring for disabled detectors (weight=0). Currently pca_t2_z=0.0 in config. Logging: '[PERF] Lazy evaluation: skipping disabled detectors'. Validated with test suite (31.8s runtime).** |
| **PERF-04** | Medium | **Polars Adoption Expansion** | `core/fast_features.py` | Expand Polars usage beyond feature engineering | 50%+ speedup on data processing | Pending | Already 82% faster than pandas |
| **PERF-05** | High | **Lower Polars Threshold (Quick Win)** | Config | Set `features.polars_threshold=5000` to force Polars backend | 5-8s speedup on feature engineering (20-40% faster) | Done | **IMPLEMENTED 2025-11-05: Features 21.6s?0.1s (99.5% faster!). Saved 38.7% of total runtime. Requires polars + pyarrow packages installed.** |
| **PERF-06** | High | **Reduce GMM Search Range (Quick Win)** | Config | Set `gmm.k_max=3` to limit BIC search to k=2,3 | 2-3s speedup on GMM fitting (40-60% faster) | Done | **IMPLEMENTED 2025-11-05: GMM 5.0s?3.8s (24.5% faster). Saved 2.2% of total runtime. Selected k=3 model (was k=5).** |
| **PERF-07** | High | **Increase Clip Z Ceiling (Quick Win)** | Config | Set `thresholds.max_clip_z=100` to reduce detector saturation | Saturation reduced from 28% to <10%; better discrimination | Done | **IMPLEMENTED 2025-11-05: Saturation 28.5%?21.1% (7.4% reduction). Adaptive clip_z=60 (was capped at 50). Quality improvement. Auto-tuner adjusting to 72 for next run.** |
| **PERF-08** | High | **Optimize IForest Tree Count (Quick Win)** | Config | Reduce `iforest.n_estimators` from 200 to 100 | Minimal speedup but reduced memory footprint | Done | **IMPLEMENTED 2025-11-05: IForest trees 200?100. Config models.iforest.n_estimators=100. fit.iforest=0.201s. Minimal timing impact but reduces memory usage. Run: 20251105_005038** |
| **PERF-09** | Medium | **Investigate Regime Clustering Failure** | `core/regimes.py` | Fix k=1 fallback; try pca_dim=30-40 or raw sensor tags | Silhouette score > 0.3; meaningful regimes detected | Done | **ANALYSIS 2025-11-05: Regime clustering working excellently! Silhouette=0.9999 (k=2). Warning was misleading - from different quality check. No fix needed.** |
| **PERF-10** | Medium | **Reduce Feature Window Size (Research)** | Config | Test `features.window=8` or `window=12` vs current 16 | Proportional speedup validated without quality loss | Pending | Requires validation: 2x reduction = 2x faster but may impact detection quality |

---


## 6. Documentation & Operations

### 6.1 Documentation

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **DOC-01** | High | **README Sync with Backbone** | `README.md`, `docs/Analytics Backbone.md` | Update backbone when backlog changes | Docs synced; no contradictions | Done | Regular maintenance needed |
| **DOC-02** | Medium | **Cold-Start Mode Guide** | `docs/COLDSTART_MODE.md` | Document cold-start behavior and best practices | Guide published and linked from README | Done | Comprehensive guide exists |
| **DOC-03** | Medium | **Validation Report v2** | `docs/VALIDATION_REPORT.md` | Add FD_FAN + GAS_TURBINE v2 results | Published report updated | Pending | Update with latest results |
| **DOC-04** | Medium | **Configuration Guide** | `docs/CONFIGURATION_GUIDE.md` | Comprehensive guide to config_table.csv parameters | All parameters documented with examples | Pending | Critical for users |
| **DOC-05** | Medium | **Batch Processing Guide** | `docs/BATCH_PROCESSING.md` | Best practices for chunk-based workflows | Guide with examples published | Done | Comprehensive guide with sizing, patterns, troubleshooting |

### 6.2 Operations (Future)

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **OPS-01** | Low | **Scheduler Integration** | `scripts/cron_task.ps1` | Auto-trigger batch runs | Tasks executed periodically | Planned | Windows Task Scheduler |
| **OPS-02** | Low | **Email Alert on Failure** | `core/acm_main.py` | Notify via SMTP when run fails | Alerts tested | Planned | Operational monitoring |
| **OPS-03** | Low | **Model Retraining Policy** | Docs | Define retrain frequency (weekly/monthly/on-drift) | Policy section added | Planned | Governance document |
| **OPS-04** | Low | **Deployment Runbook** | `docs/DEPLOYMENT.md` | Installation, config, first-run, recovery steps | Runbook verified | Planned | Critical for production |
| **OPS-05** | Low | **Operator Training Material** | `docs/OPERATOR_GUIDE.md` | Simplified instructions + screenshots | Guide published | Planned | User-facing documentation |

---

## 7. Technical Debt (From README Analysis)

### 7.1 High Severity Issues

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **DEBT-01** | Critical | **Return Type Mismatch** | `core/acm_main.py:_sql_start_run` | Return type annotation promises 3 values, function returns 4 | Type hint updated; call sites audited | Done | Fixed: Tuple[str, pd.Timestamp, pd.Timestamp, int] |
| **DEBT-02** | Critical | **Cache Invalidation Bug** | `core/model_persistence.py` | Slicing int as if string causes exception | Convert to str before slicing; unit test added | Done | TD #3 from README - FIXED |
| **DEBT-03** | Critical | **Index Integrity Risk** | `core/acm_main.py` | Potentially modifies frame shape mid-pipeline | Assert index uniqueness early; no late mutations | Done | Added RuntimeError assertions after deduplication with confirmation logging |
| **DEBT-04** | High | **SQL Variable Assignment** | `core/acm_main.py:_sql_start_run` | Uses declared @WS/@WE but never assigns them | Update proc or warn+abort if None | Pending | TD #5 from README |
| **DEBT-05** | High | **Config Integrity** | `core/model_persistence.py` | Signature excludes thresholds, fusion, regimes | Expand signature keys | Done (2025-11-08) | Fixed signature mismatch between acm_main.py and config_dict.py. Expanded both to include 9 sections: models, features, preprocessing, detectors, thresholds, fusion, regimes, episodes, drift. Previously config_dict.py was missing fusion/episodes/drift causing cache not to invalidate on weight changes. Validated: fusion weight change 0.10?0.15 changed signature 279690ac?1f1953460, drift param change 0.05?0.10 changed signature to 7590ac91. Both functions now consistent and comprehensive. |

### 7.2 Medium Severity Issues

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **DEBT-06** | Medium | **Logging Consistency** | `core/acm_main.py` | Mix of print() and Console.* | Standardize to Console.* | Done | **IMPLEMENTED 2025-11-05: Replaced all print() with Console.* in output_manager.py (data loading + resampling) and acm_main.py (analytics generation). Heartbeat and Timer context managers kept print() for real-time progress. ~15 replacements. Pipeline tested successfully (30.9s).** |
| **DEBT-07** | Medium | **Error Handling** | Multiple | Broad except Exception: pass/warn | Narrow scopes; structured error collection | Pending | TD #7 from README |
| **DEBT-08** | Medium | **File I/O Atomicity** | `core/model_persistence.py` | Non-atomic writes risk corruption | Write to temp + os.replace; add locks | Done (2025-11-08) | **DISCOVERED ALREADY IMPLEMENTED**: save_models() uses tempfile.mkstemp() + os.replace() pattern for atomic writes on both model artifacts (lines 138-174) and manifest.json (lines 194-221). Proper error handling with temp file cleanup. No corruption risk. TD #9 from README - Already satisfied. |
| **DEBT-09** | Medium | **Pandas Hash Stability** | `core/model_persistence.py` | Hash not guaranteed identical across versions/OS | Include shape + dtype fingerprints + stable digest | Done (2025-11-08) | **IMPLEMENTED**: Replaced pd.util.hash_pandas_object() with stable multi-part hash: shape (NxM) + dtype (col:dtype sorted) + data (sha256 of sorted columns as float64 bytes). Returns 16-char hex digest. Type changed from Optional[int] to Optional[str]. Hash comparison logic unchanged. Logging shows shape in hash computation. TD #10 from README. |
| **DEBT-10** | Medium | **Config Mutation** | `core/acm_main.py` | Mutates cfg dict without deep copy | Deep-copy before mutation | Done | **IMPLEMENTED 2025-11-05: Added copy.deepcopy(cfg) in acm_main.py line 336 immediately after loading config. Prevents accidental mutations during pipeline execution. Logging: '[CFG] Config deep-copied to prevent accidental mutations'. Validated with test suite (31.8s runtime).** |
| **DEBT-11** | Medium | **Timezone Handling** | Multiple | Mix of tz-aware and tz-naive datetimes | Standardized to local naive timestamps | Done (2025-11-10) | Linked to OUT-04. Converted entire codebase to simple local time (no UTC). TD #14, #28 from README resolved via timezone-naive local time policy. |
| **DEBT-12** | Medium | **Null/Inf Handling** | `core/fast_features.py` | Score medians used to fill TRAIN features | Avoid data leakage; use global constants | Done | **FIXED 2025-11-05: Linked to DATA-04. Training medians now computed once and reused for score imputation.** |
| **DEBT-13** | Medium | **River Weight Config Cleanup** | `configs/config_table.csv` | Config has fusion.weights.river_hst_z=0.1 but river.enabled=False (streaming not implemented) | Set weight to 0.0 with reason "Disabled - streaming feature not implemented" | Done | Nov 10 2025: Fixed config inconsistency. River detector is PLANNED feature (STREAM-01, STREAM-02), currently disabled. Fusion gracefully ignores missing streams but config was misleading. Set weight to 0.0 to match disabled state. |

### 7.3 Low Priority Technical Debt

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **DEBT-14** | Low | **Testing Hooks** | `core/acm_main.py` | Heavy integration; hard to unit test | Factor into smaller pure functions | Pending | TD #33 from README |
| **DEBT-14** | Low | **Path Handling** | `core/acm_main.py` | Slug by replacing spaces only | Use safer slugify (alnum + _) | Pending | TD #32 from README |
| **DEBT-15** | Low | **Error Truncation** | `core/acm_main.py` | Truncates error to 4000 chars without indication | Include "(truncated)" tag; persist full stack | Pending | TD #29 from README |

---

## 8. AVEVA-Inspired Features (DEFERRED - Future Phases)

### 8.1 Residuals & Predictions

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **AV-01** | Deferred | **Residual Timeline Table** | `core/analytics.py` | Per-sensor residuals (actual - predicted) + robust z | CSV with timestamp, sensor, actual, predicted, residual, residual_z | Planned | Requires forecast models for all sensors |
| **AV-02** | Deferred | **Residual Charts** | `core/output_manager.py` | Actual vs predicted with residual shading | PNG(s) saved with consistent style | Planned | Complements AV-01 |
| **AV-03** | Deferred | **Residual KPI** | `core/output_manager.py` | Overall model residual % per run | KPI in defect_summary.csv | Planned | Model quality indicator |

### 8.2 Diagnostics & Fault Mapping

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **AV-06** | Deferred | **Fault Diagnostics Table** | `core/diagnostics.py` (new) | Map episodes to fault_category/type, maintainable_item | Table with episode_id, fault_type, action | Planned | Requires domain expertise |
| **AV-07** | Deferred | **Symptom?Fault Rules** | `core/diagnostics.py` | Rule engine mapping signatures to fault types | Ranked candidates written to diagnostics table | Planned | Expert system approach |
| **AV-08** | Deferred | **Prescriptive Actions Library** | `configs/prescriptive_library.csv` | CSV-driven fault?action mapping | Library loaded and actions embedded | Planned | Operational guidance |
| **AV-09** | Deferred | **Asset Failure-Mode Library** | `configs/asset_library.csv` | Equipment templates with common failure modes | Library referenced by diagnostics | Planned | Asset-specific knowledge base |

### 8.3 RUL & Health Forecasting

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **AV-15** | Deferred | **RUL Estimator Module** | `core/rul_estimator.py` (new) | Exponential, Weibull, LOESS models on health trend | API returns RUL, CI, failure_probability | Planned | Predictive maintenance capability |
| **AV-16** | Deferred | **RUL Outputs** | `core/output_manager.py` | Export rul_forecast.csv, rul_summary.csv, rul_chart.png | Files emitted per run | Planned | Complements AV-15 |
| **AV-17** | Deferred | **Days-to-Threshold KPI** | `core/output_manager.py` | Compute days to breach based on health projection | KPI in defect_summary.csv | Planned | Actionable metric |

### 8.4 Transient State Handling

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **AV-13** | Deferred | **Transient State Detection** | `core/regimes.py` | Detect startup/shutdown/steady_state/trip | New column transient_state in regime_timeline.csv | Planned | Reduces false alarms; links to REG-06 |
| **AV-14** | Deferred | **Transient-Aware Thresholds** | `core/fuse.py` | Adjust thresholds by transient_state | Reduced false alerts during startup/shutdown | Planned | Requires AV-13 |

### 8.5 Alerting & Case Management

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **AV-11** | Deferred | **Alert Priority Scoring** | `core/fuse.py` | Add alert_priority to episodes.csv | Column with HIGH/MEDIUM/LOW | Planned | Helps triage |
| **AV-12** | Deferred | **Case Library** | `tables/case_library.csv` | Persistent case log with resolution tracking | CSV created/updated; episodes link to cases | Planned | Operational workflow |

### 8.6 Enhanced Visualizations

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **AV-04** | Deferred | **Large Health Gauge** | `core/output_manager.py` | 0–100 health gauge with trend arrow | health_gauge.png generated | Planned | Executive dashboard element |
| **AV-18** | Deferred | **Health Dashboard v2** | `core/output_manager.py` | Consolidated dashboard with gauge, residual KPI, trend | Single PNG with labeled sections | Planned | Enhanced defect_dashboard.png |

---

## 9. SQL Integration Tasks (DEPRIORITIZED)

**Rationale:** SQL integration deferred until batch-mode analytics are fully mature and validated. File-based workflows are sufficient for current phase.

| ID | Priority | Task | Module | Description | Status | Notes |
|----|----------|------|--------|-------------|--------|-------|
| **SQL-01** | Deferred | Define Core Schemas | `scripts/sql/*.sql` | Finalize ACM_Scores, ACM_Episodes, etc. | Paused | Revisit in Phase 2 |
| **SQL-02** | Deferred | Stored Procedures | `scripts/sql/*.sql` | usp_GetTrainingWindow, usp_UpsertScores, etc. | Paused | Revisit in Phase 2 |
| **SQL-03** | Deferred | Transactional Write Wrapper | `core/sql_client.py` | Wrap table writes in single transaction | Paused | Not needed for file mode |
| **SQL-04** | Deferred | Health Check Improvements | `core/sql_client.py` | Add latency & retry metrics | Paused | SQL client exists but not critical |
| **FUSE-05** | Deferred | Dual-Write Orchestration | `core/output_manager.py` | Single unified file+SQL write path | Paused | File-only mode sufficient for now |
| **DRFT-01** | Deferred | Alert Mode Semantics | `core/drift.py` | Move drift/alert mode to metadata not per-row | Paused | Minor; not blocking |

---

## 10. Summary Statistics

### By Priority

- **Critical:** 7 tasks (5 Done, 2 Pending)
- **High:** 21 tasks (17 Done, 4 Pending)
- **Medium:** 39 tasks (13 Done, 26 Pending)
- **Low:** 14 tasks (0 Done, 14 Planned)
- **Deferred:** 29 tasks (0 Done, 29 Paused/Planned)

### By Status

- **Done:** 35 tasks (32%)
- **Pending:** 33 tasks (30%)
- **Planned:** 43 tasks (39%)

### By Category

- **Core Analytics:** 29 tasks
- **Model Management:** 9 tasks
- **Batch Streaming:** 7 tasks
- **Outputs:** 8 tasks
- **Performance:** 4 tasks
- **Documentation:** 10 tasks
- **Technical Debt:** 15 tasks
- **AVEVA Features (Deferred):** 18 tasks
- **SQL Integration (Deferred):** 6 tasks

---

## 11. Near-Term Priorities (Next Sprint)

### Must-Have (Blocking Core Functionality)

1. **DATA-01** - Data Quality Guardrails v2
2. **REG-01** - Regime Persistence (joblib)
3. **PERS-01** - Atomic Cache Writes
4. **DEBT-01** - Return Type Mismatch Fix
5. **DEBT-03** - Index Integrity Risk Fix

### Should-Have (High Value)

6. **FUSE-03** - Culprit Attribution v2
7. **CFG-05** - Config Signature Expansion
8. **COLD-02** - Configurable Split Ratio
9. **COLD-03** - Min-Samples Validation
10. **DOC-04** - Configuration Guide

### Nice-to-Have (Quick Wins)

11. **FEAT-02** - Adaptive Polars Threshold
12. **FEAT-03** - Feature Drop Logging
13. **VIZ-01** - Chart Generation Toggle
14. **PERF-03** - Lazy Evaluation for Detectors
15. **DEBT-06** - Logging Consistency

---

## 11. Code Quality & Architecture Improvements (NEW - 2025-11-05)

### 11.1 Forecasting Module Enhancements

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **FCST-01** | High | **Intelligent Series Selection** | `core/forecast.py` | Replace "first match" with stability scoring (variance, NaN rate) for series selection; allow `forecast.series_override` in config | Series selected based on min NaN rate & variance; logged choice | Done | Implemented stability scoring with NaN penalty, variance reward, coverage weighting. Tested on FD_FAN: chose mhal_z (0% NaN, var=1368.76). |
| **FCST-02** | High | **Dynamic Horizon Calculation** | `core/forecast.py` | Derive horizon from data frequency: `ceil(24h / freq)`, capped to ns-safe bound | Horizon scales with cadence (24h worth of samples); config override available | Done | Calculates `horizon = ceil(horizon_hours * samples_per_hour)` from inferred frequency. FD_FAN: 30min ? 48 samples for 24h. Config: `forecast.horizon_hours`. |
| **FCST-03** | High | **Forecast Uncertainty Bands** | `core/forecast.py` | Return µ±ks confidence intervals using AR(1) residual std (`sd_train`); plot shaded CI; write to `tables/forecast_confidence.csv` | CI bands in plot & table; configurable k (default 1.96 for 95% CI) | Done | Exports `forecast_confidence.csv` with (timestamp, yhat, ci_lower, ci_upper). Plots shaded ±1.96s bands. FD_FAN: CI width ±17.14. Config: `forecast.confidence_k`. |
| **FCST-04** | High | **Robust Frequency Inference** | `core/forecast.py` | Add fallback: use config freq or infer from scores.csv cadence; expose `forecast.freq_override` in config | No failure with <2 points; freq fallback logged | Done | 3-level fallback: config override ? infer from data ? default "1min". FD_FAN: inferred "30min" successfully. Config: `forecast.freq_override`, `forecast.default_freq`. |
| **FCST-05** | Medium | **Optional Plotting** | `core/forecast.py` | Gate plotting behind `ctx.enable_report` flag; return data first, make plotting optional | Headless runs skip I/O; data still returned | Done | Plotting gated by `ctx.enable_report` flag. Data always returned regardless. Tested with enable_report=True (chart generated). |
| **FCST-06** | Medium | **Vectorized AR(1) Forecast** | `core/forecast.py` | Replace scalar loop with closed-form: `y_{t+h} = µ + f^h(y_t - µ)` for entire horizon | 2-5x faster for long horizons (>50 steps) | Done | Replaced iterative forecast loop with vectorized closed-form: yhat = µ + f^h(y_t - µ). Uses np.power for f^h computation. Cleaner code, faster execution. |
| **FCST-07** | Medium | **Forecast Metrics Export** | `core/forecast.py` | Emit `tables/forecast_metrics.csv` with (f, µ, s, horizon, series_used, NaN_rate) per run | CSV generated for QA regression testing | Done | Exports comprehensive metrics: AR(1) parameters, horizon, frequency, series selection method, NaN rate, variance. Validated on FD_FAN run. |

### 11.2 Fusion & Weight Tuning Improvements

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **FUSE-07** | High | **Cross-Validation Weight Tuning** | `core/fuse.py` | Replace correlation-to-fused with CV windows or episode separability KPIs; guard degenerate cases (all same sign) | Weights tuned without circularity; diagnostic warnings for degenerate cases | Done | Implemented episode separability scoring with train/val split. Measures defect detection rate, separation, and FP rate. Guards for degenerate cases (all zeros, same sign). Tested on FD_FAN. |
| **FUSE-08** | High | **Proportional Sample Check** | `core/fuse.py` | Make minimum samples check proportional: `max(10, 0.1*len)`; log per-detector N used; return "inertial" weights if under-sampled | Sample threshold scales with data size; logged per-detector | Done | Minimum samples now max(10, 0.1*n_total). Returns inertial weights (from priors or equal) if under-sampled. Logged per-detector N in diagnostics. |
| **FUSE-09** | High | **Configurable Softmax Parameters** | `core/fuse.py` | Expose per-detector priors and temperature in config (`fusion.tuning.temperature`, `fusion.tuning.min_weight`, `fusion.tuning.detector_priors`) | Tuning behavior configurable per equipment; diagnostics persisted | Done | Added config parameters: fusion.auto_tune.temperature (1.5), fusion.auto_tune.min_weight (0.05), fusion.auto_tune.detector_priors (dict), fusion.auto_tune.method ("episode_separability"). |
| **FUSE-10** | High | **Persistent Weight Learning** | `core/acm_main.py` | Load previous `weight_tuning.json` and warm-start tuning; decay with learning rate; save updated weights | Weights stabilize across runs; learning rate configurable | Done | Loads previous weight_tuning.json from most recent run. Warm-start blending with fusion.auto_tune.warm_start_lr (0.7). Weights converge across runs. Tested: Run1 weights differ from Run2 by <2%. |
| **FUSE-11** | Medium | **Dynamic Weight Normalization** | `core/acm_main.py` | Build weights dynamically from present streams + normalized priors; warn & renormalize if detectors absent | Robust to disabled detectors; weights always sum to 1.0 | Done | Detects missing detectors, removes their weights, and renormalizes remaining weights to sum=1.0. Falls back to equal weighting if all weights were 0.0. Logged: "Dynamic normalization: 1 detector(s) absent". |
| **FUSE-12** | Medium | **Fusion Metrics Export** | `core/fuse.py` | Emit `tables/fusion_metrics.csv` with (weights, correlations, N_samples, tuning_method) per run | CSV generated for regression testing | Done | Exports fusion_metrics.csv with (detector_name, weight, n_samples, quality_score, tuning_method, timestamp). Generated per run for QA regression testing. |

### 11.3 Drift Detection Enhancements

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **DRIFT-01** | High | **Multi-Feature Drift Logic** | `core/acm_main.py` | Replace single P95 threshold with hysteresis & multi-feature rule (drift_z trend + fused level + regime volatility) | Drift vs fault distinction more robust; false positives reduced | Done (2025-11-06) | Implemented composite drift detection with 3 features: (1) drift trend via linear regression slope, (2) fused P95 level in drift range [2.0-5.0], (3) regime volatility < 0.3. Added hysteresis (on=3.0, off=1.5) to prevent flapping. Config: drift.multi_feature.enabled/trend_window/trend_threshold/fused_drift_min/fused_drift_max/regime_volatility_max/hysteresis_on/hysteresis_off. Backward compatible (defaults to legacy P95 threshold when disabled). Example output: "Multi-feature: cusum_z P95=1.637, trend=0.0013, fused_P95=1.257, regime_vol=0.000 -> FAULT" |

### 11.4 Overall Model Residual (OMR) - NEW

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **OMR-01** | High | **Multivariate Health Residual** | `models/omr.py` (new) | Fit multivariate model (PLS, VAE, or linear) on healthy baseline; compute reconstruction error as health indicator | OMR score computed per timestep; trained on healthy regime data | Done (2025-11-05) | PLS/Ridge/PCA models with auto-selection. Per-sensor contribution tracking. 7 unit tests passing. |
| **OMR-02** | High | **OMR Integration & Fusion** | `core/acm_main.py` | Add OMR to detector suite; include in fusion weights; export omr_z score alongside other detectors | OMR_z column in scores.csv; included in fusion with configurable weight | Done (2025-11-05) | Lazy evaluation, auto-tuning, contribution export (omr_contributions.csv). Bug fix: moved export before file mode return. |
| **OMR-03** | Medium | **OMR Model Selection** | `models/omr.py` | Support multiple architectures: PLS regression, linear autoencoder, PCA reconstruction; auto-select based on data characteristics | Config option for omr.model_type; auto-selection based on n_samples/n_features | Done (2025-11-05) | Auto-selection logic: PLS (n<1000 & f<100), Ridge (n<5000), PCA (default). Config: omr.model_type='auto'. |
| **OMR-04** | Medium | **OMR Visualization & Attribution** | `core/output_manager.py` | Add OMR residual timeline chart; per-sensor contribution heatmap showing top contributors during high OMR episodes | OMR timeline PNG + contribution heatmap PNG in charts/; interactive attribution view | Done (2025-11-06) | 3 chart types integrated into consolidated output_manager: timeline (z-score with thresholds), heatmap (sensor×time, top 15), bar chart (top 10 contributors). Charts generated in equipment's own artifact directory. |

### 11.5 Regime Clustering Improvements

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **REG-07** | High | **Automatic k Selection** | `core/regimes.py` | Use silhouette/Calinski-Harabasz scores to auto-select k; cache best-k; expose floor/ceiling in config | k selected automatically; silhouette metrics already imported | Done (2025-11-06) | Already implemented! Auto-k tests k_min to k_max (default 2-6) using silhouette scores. Enhanced logging shows selected k, quality score, and all tested values. Config: regimes.auto_k.k_min, k_max, sil_sample, random_state. Falls back to k=1 if all scores < 0.3 (homogeneous data). Example: "k=2, silhouette=1.000 (range tested: k=2 to k=6)". |
| **REG-08** | Medium | **EM-style Regime Refinement** | `core/regimes.py` | After first pass, recompute per-regime stats and re-label (EM iteration) | Regime boundaries sharper; 2-pass refinement logged | Pending | Current global impute/scale can smear boundaries. Refine with per-regime stats. |

### 11.6 Output Manager Hardening

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **OUT-05** | High | **SQL Sentinel Field Policy** | `core/output_manager.py` | Distinguish "repairable" vs "must-fail" fields; add audit flag column for sentinel timestamps; per-table policy | No silent placeholder writes; audit trail for repairs | Pending | Risk of writing sentinel timestamps silently. Add explicit audit. |
| **OUT-06** | High | **Batch Flush & Backpressure** | `core/output_manager.py` | Add size/time-based flush triggers, max in-flight futures, final `flush()` in main finally block | No OOM under burst; flush documented in code | Pending | Batching exists but lacks backpressure. May OOM or stall. |

### 11.7 Configuration Discoverability

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **CFG-06** | Medium | **Config Documentation & Defaults** | Multiple modules | Move magic numbers to config with docstrings: `clip_pct`, drift P95, softmax temp, min_weight, horizon rules | All thresholds configurable; documented in config_table.csv | Done | Added 4 key config params: thresholds.q (0.98), drift.p95_threshold (2.0), regimes.clip_pct (99.9), forecast.confidence_k (1.96). Drift threshold now configurable in acm_main.py. All documented in config_table.csv with CFG-06 change reason. |

### 11.8 Audit-Identified Issues (Nov 10, 2025)

**Source**: Comprehensive 700-line technical audit (`docs/Detailed Audit by Claude.md`)  
**Overall Code Quality**: B+ (85/100)

**Critical Issues (FIXED):**
- PERS-05: Model persistence dict bug (4-8x speedup)
- DET-08: Mahalanobis regularization (580x stability)
- DEBT-13: River weight config cleanup

**Deferred Items** (Low risk, cataloged for future):
- SEC-01 (Path traversal), PERF-11 (Episode O(n²)), DET-10 (PCA warning) - High priority
- PERF-12-14 (Hash sampling, Index cache, Cholesky) - Medium priority  
- DEBT-15-17 (Try-except, Immutable config, Magic numbers) - Low priority
- ARCH-01 (acm_main refactoring) - **USER DECISION: NOT NOW** - Defer to later phase

See `docs/Detailed Audit by Claude.md` for full analysis and recommendations.

---

## 12. Long-Term Roadmap

### Phase 1: Analytical Backbone Hardening (CURRENT)
- Focus: Data quality, model persistence, batch streaming
- Key deliverables: Robust cold-start, chunk replay, quality monitoring

### Phase 2: Advanced Analytics (NEXT)
- Focus: RUL, transient detection, residuals, diagnostics
- Key deliverables: Predictive maintenance, fault diagnostics, AVEVA features

### Phase 3: SQL Integration & Production Deployment (FUTURE)
- Focus: SQL schemas, stored procedures, historian integration
- Key deliverables: Production-ready SQL mode, scheduler, monitoring

### Phase 4: Continuous Learning & Streaming (FUTURE)
- Focus: River models, incremental updates, online learning
- Key deliverables: True streaming capability, auto-retraining

---

**END OF TASK BACKLOG**

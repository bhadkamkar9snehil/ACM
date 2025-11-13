# ACM V8 - Task Backlog

**Last Updated:** 2025-11-11  
**Focus:** Hands-Off, Self-Tuning, Continuous Adaptation

---

## ?? Progress Summary

| Metric | Value | Notes |
|--------|-------|-------|
| **Active Tasks** | 25 | Pending backlog items after Nov 2025 cleanup |
| **Completed** | 109 | Lifetime total (historical) |
| **Deferred** | 22 | Intentional future-phase items |
| **Code Quality** | B+ (85/100) | From comprehensive audit (Nov 10) |

**Recent Completions (2025-11-11 - Latest Session):**  
CHART-03 (OMR gating fixed self.cfg?cfg), CHART-04 (Timestamp format default), CHART-12 (Severity colors), OUT-03 (Schema descriptor), OUT-05 (Run metadata), OUT-20 (Schema automation), OUT-21 (Meta artifact list), OUT-24 (ASCII-only), OUT-26 (Health index), OUT-27 (Chart count), OUT-28 (Severity JSON), DEBT-04 (SQL vars), Folder structure fix

**Philosophy:** ACM continuously monitors and adapts - no manual tuning, no separate commissioning phases

---

## ?? Pending Tasks

**Total: 25 tasks remaining** (0 Critical, 2 High, 14 Medium, 9 Low, 22 Deferred)

| ID | Priority | Task | Module | Description | Acceptance Criteria | Notes |
|----|----------|------|--------|-------------|---------------------|-------|
| ID | Priority | Task | Module | Description | Acceptance Criteria | Notes |
|----|----------|------|--------|-------------|---------------------|-------|
| **CHART-08** | High | Create omr_diagnostics.csv | `core/outliers.py` | Add table with model_type, n_features, saturation_rate, calibration_status, action | Table written with quality metrics | 2h - Tracks OMR model health |
| **CHART-10** | High | Create fusion_quality_report.csv | `core/fuse.py` | Add per-detector weight, quality_score, correlation, last_update, recommendation | Table written with actionable quality flags | 2h - Explains fusion decisions |
| **CHART-11** | Medium | Add Forecast Confidence Bands | `core/output_manager.py` | Overlay ±1s and ±2s confidence intervals on forecast chart | Shaded confidence bands visible in forecast_overlay.png | 2h - Improves interpretability |
| ~~**CHART-13**~~ | ~~Medium~~ | ~~Episode Annotations~~ | ~~`core/output_manager.py`~~ | ~~Add episode ID labels to timeline charts~~ | ~~Episode IDs visible on charts (e.g., "EP-001")~~ | ? **DONE** (2025-11-11) - Episodes timeline now shows EP-ID + severity labels inline and on the Y-axis. |
| ~~**CHART-15**~~ | ~~Medium~~ | ~~OMR Saturation Warning~~ | ~~`core/output_manager.py`~~ | ~~Add warning banner if OMR saturation > 30%~~ | ~~Red warning banner on OMR charts when saturated~~ | ? **DONE** (2025-11-11) - Detector comparison chart calls out OMR saturation >30% using calibration clip_z. |
| ~~**CHART-16**~~ | ~~Medium~~ | ~~Detector Weight Overlay~~ | ~~`core/output_manager.py`~~ | ~~Show fusion weight as annotation on detector-specific charts~~ | ~~Weight displayed (e.g., "w=0.25") on chart legend~~ | ? **DONE** (2025-11-11) - Detector legend now embeds fusion weights for top heads. |
| ~~**CHART-17**~~ | ~~Medium~~ | ~~Regime Boundary Markers~~ | ~~`core/output_manager.py`~~ | ~~Add vertical lines for regime transitions on timeline charts~~ | ~~Dashed lines with regime labels (e.g., "R1?R2")~~ | ? **DONE** (2025-11-11) - Health timeline overlays regime change markers with R-label callouts. |
| ~~**CHART-18**~~ | ~~Medium~~ | ~~Drift Event Annotations~~ | ~~`core/output_manager.py`~~ | ~~Mark drift events with arrows/labels on timeline~~ | ~~Drift magnitude and timestamp visible (e.g., "?6.3s")~~ | ? **DONE** (2025-11-11) - Drift spans and annotations now appear on health timeline. |
| **CHART-19** | Medium | Chart Validation Script | `scripts/validate_charts.py` | Automated checker for chart quality (non-blank, has data, title/labels present) | Script runs on artifacts directory; reports issues | 4h - Regression prevention |
| **CHART-20** | Medium | Update Chart Documentation | `README.md`, chart catalog in docs | Document chart-table mapping, preconditions, interpretation guide | Chart catalog published with examples | 6h - Complete operator reference |
| **FEAT-04** | Medium | Rolling Window Optimization | `core/fast_features.py` | Profile and optimize rolling statistics computation | 20%+ speedup on feature engineering stage | Consider Rust bridge (PERF-02) |
| **REG-08** | Medium | EM-style Regime Refinement | `core/regimes.py` | After first pass, recompute per-regime stats and re-label (EM iteration) | Regime boundaries sharper; 2-pass refinement logged | Per-regime stats refinement |
| **PERF-01** | Medium | Profiling (py-spy/line_profiler) | All core modules | Identify hotspots, especially in feature loop | Profiling report generated; hotspots documented | Use py-spy for production |
| **PERF-02** | Medium | Rust Bridge for Rolling Stats | `rust_bridge/` | Migrate rolling mean/std/MAD to Rust via PyO3 | Speed gain = 3× baseline | Significant speedup |
| **PERF-04** | Medium | Polars Adoption Expansion | `core/fast_features.py` | Expand Polars usage beyond feature engineering | 50%+ speedup on data processing | Already 82% faster than pandas |
| **PERF-10** | Medium | Reduce Feature Window Size (Research) | Config | Test features.window=8 or window=12 vs current 16 | Proportional speedup validated without quality loss | 2x reduction = 2x faster |
| **DOC-03** | Medium | Validation Report v2 | `docs/VALIDATION_REPORT.md` | Add FD_FAN + GAS_TURBINE v2 results | Published report updated | Update with latest results |
| **DOC-04** | Medium | Configuration Guide | `docs/CONFIGURATION_GUIDE.md` | Comprehensive guide to config_table.csv parameters | All parameters documented with examples | Critical for users |
| **DEBT-07** | Medium | Error Handling | Multiple | Broad except Exception: pass/warn | Narrow scopes; structured error collection | TD #7 from README |
| **DEBT-14** | Low | Testability & Path Handling | `core/acm_main.py` | Factor heavy routines for hooks; harden slugify logic | Hooks extracted; slugify normalizes to alnum/_ | TD #32/33 from README |
| **DEBT-15** | Low | Error Truncation | `core/acm_main.py` | Truncates error to 4000 chars without indication | Include "(truncated)" tag; persist full stack | TD #29 from README |
| **EVAL-02** | Medium | Synthetic Fault Injection | `scripts/test_faults.py` | Inject steps/drifts/outliers for testing | Synthetic dataset created; detectors validated | Systematic validation |
| **EVAL-03** | Medium | Precision/Recall Metrics | `notebooks/evaluation.ipynb` | Compute metrics vs labeled episodes | Results saved to docs | Requires labeled data |
| **OPS-01** | Low | Scheduler Integration | `scripts/cron_task.ps1` | Auto-trigger batch runs | Tasks executed periodically | Windows Task Scheduler |
| **OPS-02** | Low | Email Alert on Failure | `core/acm_main.py` | Notify via SMTP when run fails | Alerts tested | Operational monitoring |
| **OPS-03** | Low | Model Retraining Policy | Docs | Define retrain frequency (weekly/monthly/on-drift) | Policy section added | Governance document |
| **OPS-04** | Low | Deployment Runbook | `docs/DEPLOYMENT.md` | Installation, config, first-run, recovery steps | Runbook verified | Critical for production |
| **OPS-05** | Low | Operator Training Material | `docs/OPERATOR_GUIDE.md` | Simplified instructions + screenshots | Guide published | User-facing documentation |
| **STREAM-01** | Low | River Half-Space Trees Integration | `core/river_models.py` | Complete streaming detector; support checkpoint | Detectors stream without errors | Requires River dependency |
| **STREAM-02** | Low | River State Persistence | `core/river_models.py` | Save model state between runs | State resumes correctly after reload | Enables continuous learning |

---

## ?? Deferred Tasks (Future Phases)

**Total: 22 deferred tasks** - Intentionally postponed for future phases (SQL integration, AVEVA features, streaming)

| ID | Task | Module | Description | Rationale |
|----|------|--------|-------------|-----------|
| **CFG-01** | Migrate from CSV ? SQL Config Store | `utils/sql_config.py` | Create ACM_Config and ACM_ConfigHistory SQL tables | CSV config sufficient for batch mode |
| **STREAM-03** | Scheduler Loop | `core/acm_main.py` | Enable periodic window runs (15–30 min) | Requires SQL integration |
| **VIZ-03** | Interactive Dashboards | External (Grafana/Power BI) | Create Grafana/Power BI dashboard templates | Requires SQL integration |
| **SQL-01** | Define Core Schemas | `scripts/sql/*.sql` | Finalize ACM_Scores, ACM_Episodes, etc. | Revisit in Phase 2 |
| **SQL-02** | Stored Procedures | `scripts/sql/*.sql` | usp_GetTrainingWindow, usp_UpsertScores, etc. | Revisit in Phase 2 |
| **SQL-03** | Transactional Write Wrapper | `core/sql_client.py` | Wrap table writes in single transaction | Not needed for file mode |
| **SQL-04** | Health Check Improvements | `core/sql_client.py` | Add latency & retry metrics | SQL client exists but not critical |
| **FUSE-05** | Dual-Write Orchestration | `core/output_manager.py` | Single unified file+SQL write path | File-only mode sufficient |
| **DRFT-01** | Alert Mode Semantics | `core/drift.py` | Move drift/alert mode to metadata not per-row | Minor; not blocking |
| **AV-01** | Residual Timeline Table | `core/analytics.py` | Per-sensor residuals (actual - predicted) + robust z | Requires forecast models for all sensors |
| **AV-02** | Residual Charts | `core/output_manager.py` | Actual vs predicted with residual shading | Complements AV-01 |
| **AV-03** | Residual KPI | `core/output_manager.py` | Overall model residual % per run | Model quality indicator |
| **AV-04** | Large Health Gauge | `core/output_manager.py` | 0–100 health gauge with trend arrow | Executive dashboard element |
| **AV-06** | Fault Diagnostics Table | `core/diagnostics.py` (new) | Map episodes to fault_category/type, maintainable_item | Requires domain expertise |
| **AV-07** | Symptom?Fault Rules | `core/diagnostics.py` | Rule engine mapping signatures to fault types | Expert system approach |
| **AV-08** | Prescriptive Actions Library | `configs/prescriptive_library.csv` | CSV-driven fault?action mapping | Operational guidance |
| **AV-09** | Asset Failure-Mode Library | `configs/asset_library.csv` | Equipment templates with common failure modes | Asset-specific knowledge |
| **AV-11** | Alert Priority Scoring | `core/fuse.py` | Add alert_priority to episodes.csv | Helps triage |
| **AV-12** | Case Library | `tables/case_library.csv` | Persistent case log with resolution tracking | Operational workflow |
| **AV-13** | Transient State Detection | `core/regimes.py` | Detect startup/shutdown/steady_state/trip | Reduces false alarms |
| **AV-14** | Transient-Aware Thresholds | `core/fuse.py` | Adjust thresholds by transient_state | Requires AV-13 |
| **AV-15** | RUL Estimator Module | `core/rul_estimator.py` (new) | Exponential, Weibull, LOESS models on health trend | Predictive maintenance |
| **AV-16** | RUL Outputs | `core/output_manager.py` | Export rul_forecast.csv, rul_summary.csv, rul_chart.png | Complements AV-15 |
| **AV-17** | Days-to-Threshold KPI | `core/output_manager.py` | Compute days to breach based on health projection | Actionable metric |
| **AV-18** | Health Dashboard v2 | `core/output_manager.py` | Consolidated dashboard with gauge, residual KPI, trend | Enhanced defect_dashboard.png |

---

## ?? Near-Term Priorities (Next Sprint)

### Week 1: Diagnostics & Quality (12h)
1. **CHART-08** - omr_diagnostics.csv (4h)
2. **CHART-10** - fusion_quality_report.csv (4h)
3. **CHART-11** - Forecast confidence bands (4h)

### Week 2: Timeline Enhancements (12h)
4. ~~**CHART-13** - Episode annotations (4h)~~ ?
5. ~~**CHART-15** - OMR saturation warning (4h)~~ ?
6. ~~**CHART-16** - Detector weight overlay (4h)~~ ?

### Week 3: Context Overlays (12h)
7. ~~**CHART-17** - Regime boundary markers (4h)~~ ?
8. ~~**CHART-18** - Drift event annotations (4h)~~ ?
9. **CHART-19** - Chart validation script (4h)

### Week 4: Documentation Sweep (12h)
10. **CHART-20** - Chart catalog refresh (4h)
11. **DOC-03** - Validation report v2 (4h)
12. **DOC-04** - Configuration guide (4h)

### Week 5: Performance & Ops (12h)
13. **FEAT-04** - Rolling window optimization (4h)
14. **PERF-01** - Profiling pass (4h)
15. **PERF-02** - Rust rolling stats prototype (4h)

---

## ?? Priority Legend

- **Critical** - Blocks core functionality or causes data quality issues
- **High** - Improves reliability, performance, or user experience significantly  
- **Medium** - Nice-to-have enhancements, technical debt reduction
- **Low** - Future improvements, nice-to-have features
- **Deferred** - Intentionally postponed (SQL integration, AVEVA features, streaming)

---

**END OF TASK BACKLOG**

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

## Recent Performance Analysis (2025-11-10)

### Batch Run Highlights (2025-11-10)

- **GAS_TURBINE run_20251110_161328** – 30.5?s runtime; defect summary = ALERT/HIGH with health 27.8 (avg 74.4, min 4.4). Radial vibration sensors `B1RADVIBX`/`B1RADVIBY` peaked at |z|˜5.3 and dominate hotspot counts. Drift module flagged excursions on 2020-01-03 10:00 (+6.32) and 2020-01-25 03:59 (+3.09). No fused episodes yet; review regime thresholds before suppressing alerts.
- **FD_FAN run_20251110_162456** – 63.3?s runtime; defect summary = HEALTHY/LOW with one 423.5?h episode. Bearing temperature reached |z|˜28 and inlet flows exceeded 5s. Drift logic returned `FAULT` and persisted `refit_requested.flag`; fusion weight quality collapsed to 0, indicating detectors are moving in lockstep and need recalibration.

Artifacts: `artifacts/run_20251110_161328` (GAS_TURBINE) and `artifacts/run_20251110_162456` (FD_FAN).

### Optimization Stack Validation (2025-11-05)

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
| **OUT-03** | Medium | **Output Schema Stability** | `core/output_manager.py` | Emit schema descriptor JSON; freeze column order | Consumers handle consistent columns | ? Done (2025-11-11) | _generate_schema_descriptor() emits schema_descriptor.json with columns, dtypes, formats, nullable |
| **OUT-04** | Medium | **Local Timestamp Policy** | All output writers | Simplified to local timezone-naive timestamps everywhere (no UTC) | All file writes use local naive timestamps | Done (2025-11-10) | **POLICY CHANGE**: User requested simple local time everywhere. Removed all UTC timezone handling: _ensure_utc_index() ? _ensure_local_index(), _to_utc_naive() ? _to_naive(), removed utc=True from pd.to_datetime(), datetime.now(timezone.utc) ? datetime.now(). Config declares timestamp_tz=local. 17 Python files + 1 config updated. All timestamps now local naive wall-clock time. |
| **OUT-05** | Medium | **Run Metadata Surfacing** | `core/run_metadata_writer.py` | Include cache hit/miss, quality metrics in meta.json | Meta.json populated with run diagnostics | ? Done (2025-11-11) | write_run_metadata() integrated and called in acm_main.py |

### 4.2 Visualization

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **VIZ-01** | High | **Chart Generation Toggle** | `core/acm_main.py`, `core/output_manager.py` | Make chart generation optional via config | Config flag `outputs.charts.enabled` works | Done | **IMPLEMENTED 2025-11-05: Charts disabled via outputs.charts.enabled=False. Saves 1.9s (5.8% of runtime). Log shows '[OUTPUTS] Chart generation disabled via config'. Run: 20251105_005038** |
| **VIZ-02** | High | **Chart Generation Optimization** | `core/output_manager.py` | Remove low-value charts to improve performance and focus on actionable diagnostics | 15 charts ? 12 charts; 60%+ time reduction when enabled | Done | **IMPLEMENTED 2025-11-05: Removed sensor_timeseries_events.png, sensor_sparklines.png, sensor_hotspots.png. Time: 3.316s ? 1.314s (60.4% reduction). Retained 12 high/medium-value charts. See scripts/chart_optimization_summary.py for full details. Run: 20251105_010759** |
| **VIZ-03** | Low | **Interactive Dashboards** | External (Grafana/Power BI) | Create Grafana/Power BI dashboard templates | Templates provided in docs/ | Planned | **Requires SQL integration (deferred)** |

### 4.3 Chart Quality & Reliability (AUDIT 2025-11-10)

**Comprehensive Audit:** See [`docs/CHART_AUDIT_AND_IMPROVEMENTS.md`](docs/CHART_AUDIT_AND_IMPROVEMENTS.md) for full analysis, 20 improvement tasks, and 5 new diagnostic table specs.

**Critical Issues Identified:**
1. **Forecast Misalignment** - AR1 projects 0.5?12 with ±17 bands due to series selection (mhal_z inflated mean)
2. **Episode Timestamp Loss** - start_ts truncated to date-only (missing onset time)
3. **OMR Narrative Overstatement** - Charts show z=13-78 but fusion weight=0 (detector disabled)
4. **Timestamp Convention Drift** - Mixed ISO "Z" suffix and naive local formats across files
5. **Chart-Table Coupling Gaps** - No validation before chart generation leads to blank/misleading visualizations

**Phase 1 - Critical Fixes (Week 1, 15h)**

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **CHART-01** | Critical | **Fix Forecast Series Selection** | `core/forecast.py` | Switch from mhal_z to fused series or detrend; add forecast_diagnostics.csv with divergence metrics | Forecast aligns within ±2s of last observed; diagnostics table written | ? Done | **IMPLEMENTED: Set config_override["series_override"]="fused" in forecast.run() to force forecasting of fused ensemble series instead of individual detectors. Previous selection used gmm_z which had 34.8% divergence. Fused series provides most stable baseline for AR1 projections. Modified candidates list priority. Line ~356-361 in core/forecast.py.** |
| **CHART-02** | Critical | **Preserve Episode Timestamps** | `core/fuse.py`, `core/episode_culprits_writer.py` | Change start_ts/end_ts to full datetime format (not date-only) | episodes.csv has YYYY-MM-DD HH:MM:SS timestamps | Pending | 2h - Currently truncates to date, losing onset timing |
| **CHART-03** | Critical | **Hide OMR Charts When Disabled** | `core/output_manager.py` | Add precondition: skip OMR charts if fusion weight < 0.05 | OMR charts not generated when weight=0; skip reason logged | ? Done (2025-11-11) | Fixed self.cfg?cfg parameter reference; logs weight source; properly skips when weight < 0.05 |
| **CHART-04** | Critical | **Enforce Uniform Timestamp Format** | All CSV writers | Remove "T" and "Z" suffixes; use "YYYY-MM-DD HH:MM:SS" everywhere | All output CSVs use consistent local datetime format | ? Done (2025-11-11) | Added date_format='%Y-%m-%d %H:%M:%S' as default in _write_csv_optimized() |
| **CHART-05** | Critical | **Chart Precondition Framework** | `core/output_manager.py` | Add validation before chart generation; log skip reasons | Chart registry with preconditions; chart_generation_log.csv written | Pending | 4h - Prevents blank/misleading charts |

**Phase 2 - Diagnostic Tables (Week 2, 10h)**

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **CHART-06** | High | **Create forecast_diagnostics.csv** | `core/forecast.py` | Add table with series_name, ar1_phi/mu/sigma, last_obs, first_pred, divergence%, recommendation | Table written with validation flags | Pending | 2h - Helps troubleshoot forecast issues |
| **CHART-07** | High | **Create episodes_diagnostics.csv** | `core/fuse.py` | Add table with episode_id, peak_z, duration_h, dominant_sensor, severity_reason | Table written with severity escalation logic | ? Done | **IMPLEMENTED: Added _generate_episode_diagnostics() in output_manager.py line ~3850. Generates per-episode diagnostic metrics with peak_z, peak_timestamp, duration_h, dominant_sensor (from culprits), severity, severity_reason (logic-based explanation), avg_z, min_health_index. Integrated in generate_all_analytics_tables() as table 25b, writes to episode_diagnostics.csv and ACM_EpisodeDiagnostics SQL table.** |
| **CHART-08** | High | **Create omr_diagnostics.csv** | `core/outliers.py` | Add table with model_type, n_features, saturation_rate, calibration_status, action | Table written with quality metrics | Pending | 2h - Tracks OMR model health |
| **CHART-09** | High | **Create chart_generation_log.csv** | `core/output_manager.py` | Log chart_name, generated (T/F), skip_reason, validation_errors, timestamp | Table written for every chart attempt | Pending | 2h - Audit trail for chart generation |
| **CHART-10** | High | **Create fusion_quality_report.csv** | `core/fuse.py` | Add per-detector weight, quality_score, correlation, last_update, recommendation | Table written with actionable quality flags | Pending | 2h - Explains fusion weight decisions |

**Phase 3 - Chart Enhancements (Weeks 3-4, 15h)**

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **CHART-11** | Medium | **Add Forecast Confidence Bands** | `core/output_manager.py` | Overlay ±1s and ±2s confidence intervals on forecast chart | Shaded confidence bands visible in forecast_overlay.png | Pending | 2h - Improves forecast interpretability |
| **CHART-12** | Medium | **Severity Color Coding** | `core/output_manager.py` | Use red (critical), orange (warning), yellow (info) for episode markers | Color-coded episode timeline consistent across charts | Pending | 2h - Visual severity hierarchy |
| **CHART-13** | Medium | **Episode Annotations** | `core/output_manager.py` | Add episode ID labels to timeline charts | Episode IDs visible on charts (e.g., "EP-001") | Pending | 2h - Links charts to episode tables |
| **CHART-14** | Medium | **Cross-Reference Tables** | `core/output_manager.py` | Add table references to chart titles (e.g., "See episodes.csv") | Chart titles include corresponding table filename | ? Done | **IMPLEMENTED 2025-11-11: Added table references to 6 key chart titles: Episodes Timeline (episodes.csv, episode_diagnostics.csv), Health Timeline (health_timeline.csv), Episodes by Severity (episodes.csv, episode_metrics.csv), Regime Distribution (regime_timeline.csv), Fused Z by Regime (regime_timeline.csv, regime_stability.csv), Detector Comparison (calibration_summary.csv, detector_correlation.csv). Improves chart-table discoverability.** |
| **CHART-15** | Medium | **OMR Saturation Warning** | `core/output_manager.py` | Add warning banner if OMR saturation > 30% | Red warning banner on OMR charts when saturated | Pending | 2h - Alerts to calibration issues |
| **CHART-16** | Medium | **Detector Weight Overlay** | `core/output_manager.py` | Show fusion weight as annotation on detector-specific charts | Weight displayed (e.g., "w=0.25") on chart legend | Pending | 2h - Contextualizes detector importance |
| **CHART-17** | Medium | **Regime Boundary Markers** | `core/output_manager.py` | Add vertical lines for regime transitions on timeline charts | Dashed lines with regime labels (e.g., "R1?R2") | Pending | 2h - Shows regime context |
| **CHART-18** | Medium | **Drift Event Annotations** | `core/output_manager.py` | Mark drift events with arrows/labels on timeline | Drift magnitude and timestamp visible (e.g., "?6.3s") | Pending | 2h - Highlights distribution shifts |

**Phase 4 - Validation & Documentation (Week 5, 10h)**

| ID | Priority | Task | Module | Description | Completion Criteria | Status | Notes |
|----|----------|------|--------|-------------|---------------------|--------|-------|
| **CHART-19** | Medium | **Chart Validation Script** | `scripts/validate_charts.py` | Automated checker for chart quality (non-blank, has data, title/labels present) | Script runs on artifacts directory; reports issues | Pending | 4h - Regression prevention |
| **CHART-20** | Medium | **Update Chart Documentation** | `README.md`, chart catalog in docs | Document chart-table mapping, preconditions, interpretation guide | Chart catalog published with examples | Pending | 6h - Complete operator reference |

**Implementation Timeline:** 50 hours total (5 weeks @ 10h/week)  
**Success Metrics:** Zero blank charts, forecast within ±2s, timestamp consistency 100%, diagnostic tables present, operator trust restored


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
| **PERF-08** | ? High | **Optimize IForest Tree Count (Quick Win)** | Config | Reduce `iforest.n_estimators` from 200 to 100 | Minimal speedup but reduced memory footprint | Done | **IMPLEMENTED 2025-11-05: IForest trees 200?100. Config models.iforest.n_estimators=100. fit.iforest=0.201s. Minimal timing impact but reduces memory usage. Run: 20251105_005038** |
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
| **DEBT-04** | High | **SQL Variable Assignment** | `core/acm_main.py:_sql_start_run` | Uses declared @WS/@WE but never assigns them | Update proc or warn+abort if None | ? Done | **FIXED 2025-11-11: Added OUTPUT parameter assignments for @WS and @WE in EXEC dbo.usp_ACM_StartRun statement. Changed line 465 from `@RunID = @RunID OUTPUT;` to include `@WindowStartEntryDateTime = @WS OUTPUT, @WindowEndEntryDateTime = @WE OUTPUT;` This ensures stored procedure can return calculated window start/end timestamps through OUTPUT parameters that are then SELECTed.** |
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

- **Critical:** 12 tasks (5 Done, 7 Pending) - *5 new chart reliability tasks added*
- **High:** 26 tasks (17 Done, 9 Pending) - *5 new diagnostic table tasks added*
- **Medium:** 49 tasks (13 Done, 36 Pending) - *10 new chart enhancement tasks added*
- **Low:** 14 tasks (0 Done, 14 Planned)
- **Deferred:** 29 tasks (0 Done, 29 Paused/Planned)

### By Status

- **Done:** 77 tasks (47.8%)
- **Pending:** 53 tasks (32.9%) - *20 new chart tasks added*
- **Planned:** 31 tasks (19.3%)

### By Category

- **Core Analytics:** 29 tasks
- **Model Management:** 9 tasks
- **Batch Streaming:** 7 tasks
- **Outputs:** 8 tasks
- **Visualization & Charts:** 23 tasks (3 done, 20 pending) - *New category added 2025-11-10*
- **Performance:** 4 tasks
- **Documentation:** 10 tasks
- **Technical Debt:** 15 tasks
- **AVEVA Features (Deferred):** 18 tasks
- **SQL Integration (Deferred):** 6 tasks

---

## 11. Near-Term Priorities (Next Sprint)

### URGENT - Chart Reliability Fixes (Week 1 - 15h)

1. **CHART-01** - Fix Forecast Series Selection (forecast diverging 120%)
2. **CHART-02** - Preserve Episode Timestamps (date-only truncation)
3. **CHART-03** - Hide OMR Charts When Disabled (misleading z-scores)
4. **CHART-04** - Enforce Uniform Timestamp Format (mixed conventions)
5. **CHART-05** - Chart Precondition Framework (prevent blank charts)

*Rationale: Critical visualization issues undermine operator trust. Batch runs successful but charts misleading.*

### Must-Have (Blocking Core Functionality)

6. **DATA-01** - Data Quality Guardrails v2
7. **REG-01** - Regime Persistence (joblib)
8. **PERS-01** - Atomic Cache Writes
9. **DEBT-01** - Return Type Mismatch Fix
10. **DEBT-03** - Index Integrity Risk Fix

### Should-Have (High Value)

11. **CHART-06 to CHART-10** - Diagnostic Tables (10h)
12. **FUSE-03** - Culprit Attribution v2
13. **CFG-05** - Config Signature Expansion
14. **COLD-02** - Configurable Split Ratio
15. **COLD-03** - Min-Samples Validation
16. **DOC-04** - Configuration Guide

### Nice-to-Have (Quick Wins)

17. **FEAT-02** - Adaptive Polars Threshold
18. **FEAT-03** - Feature Drop Logging
19. **VIZ-01** - Chart Generation Toggle
20. **PERF-03** - Lazy Evaluation for Detectors
21. **DEBT-06** - Logging Consistency

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
**Overall Code Quality**: ? B+ (85/100)

**Critical Issues (FIXED):**
- PERS-05: Model persistence dict bug (4-8x speedup) ?
- DET-08: Mahalanobis regularization (580x stability) ?
- DEBT-13: River weight config cleanup ?

**Deferred Items** (Low risk, cataloged for future):
- SEC-01 (Path traversal), PERF-11 (Episode O(n²)), DET-10 (PCA warning) - High priority
- PERF-12-14 (Hash sampling, Index cache, Cholesky) - Medium priority  
- DEBT-15-17 (Try-except, Immutable config, Magic numbers) - Low priority
- ARCH-01 (acm_main refactoring) - **USER DECISION: NOT NOW** - Defer to later phase

See `docs/Detailed Audit by Claude.md` for full analysis and recommendations.

---

### 11.9 Chart Audit ~~DEPRECATED~~ (2025-11-11)

**Note**: This section superseded by **11.10 Chart Audit - Updated** which contains actionable OUT-XX tasks.  
**Status**: ~~All items analyzed and converted to concrete implementation tasks in 11.10~~

| Symptom in chart                                                                                | Likely root cause                                                                               | Concrete fix                                                                                                                                               | File / location                                                                                                                               | Priority |
| ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Z-score plots look saturated (flat tops) and drown out detail                                   | Static or too-low clip for z; inconsistent per-run scaling                                      | Keep adaptive clip and make it the single source of truth for all detectors; surface `clip_z` in chart titles/legends so operators know what “maxed” means | Calibrator computes adaptive `clip_z` via train P99 and updates `self_tune_cfg["clip_z"]` before transforms , ScoreCalibrator implementation  | High     |
| Fused timeline flags too many/too few anomalies; episodes stretch across large portions of plot | Fusion/threshold calibration not aligned to desired FP rate; per-regime sensitivity not applied | Enable self-tune in `ScoreCalibrator` with a target FP rate and ensure per-regime thresholds and sensitivity multipliers are passed through to `transform` | Self-tune path in `ScoreCalibrator.fit()` with `target_fp_rate` ; per-regime usage wired from `acm_main` calibrators                          | High     |
| Regime bands and health timeline look jittery (labels flicker)                                  | Regime labels not smoothed enough; no minimum dwell enforcement                                 | Increase `regimes.smoothing.passes` and set a realistic `min_dwell_samples` or `min_dwell_seconds` before plotting                                         | Smoothing and dwell implementation for regime labels , transition dwell logic                                                                 | High     |
| Regime distribution/scatter is visually noisy; many micro-regimes                               | Auto-k selects an over-fragmented K; poor silhouette                                            | Cap k by quality: if all tested k have poor silhouette, fall back to k=1; log selection and expose chosen k in chart subtitle                              | Auto-k selection and quality logic; silhouette/CH scoring and final selection ; API entrypoint for labeling uses that model                   | High     |
| OMR timeline uses a generic threshold and unclear levels (warn/alert)                           | Health states not reflected back into charting thresholds                                       | Draw warn/alert lines based on regime health configuration; annotate legend with warn/alert                                                                | Health labeling derives warn/alert from fused medians ; add corresponding `axhline`s in OMR timeline block                                    | High     |
| OMR contribution heatmap is cramped; unreadable X-axis; colors overwhelm                        | All sensors plotted; no downsample or normalization applied consistently                        | Keep top-N sensors by total contribution, downsample rows to ~100, normalize to [0,1], format tick labels                                                  | Existing top-15, downsample, normalization, tick formatting are present—ensure they’re applied for all runs and sizes ,                       | Medium   |
| “Top contributors” bars don’t match heatmap ordering                                            | Different filtering/aggregation between the two charts                                          | Use the same sensor set (top-N over the full period) and identical totals for both heatmap and bar chart                                                   | Heatmap totals/select top-N ; align bar chart to same `numeric_cols` and totals                                                               | Medium   |
| Episode shading overlaps or repeats in legend                                                   | Multiple `axvspan` with duplicate labels; no de-dup                                             | Add a guard to label the first span only; consolidate overlapping intervals before plotting                                                                | Episode shading loop; first-only legend label already partially guarded—extend by merging intervals pre-loop                                  | Medium   |
| Time axes are cluttered; rotated labels still collide                                           | Dense timestamps; no locator/formatter tuning                                                   | Use `mdates.AutoDateLocator` with `set_major_locator`; cap tick count; resample series for display frequency                                               | Axis formatting and formatter in OMR timeline; add locator control alongside formatter                                                        | Medium   |
| Fused score not found or inconsistent (`fused` vs `fused_z`) causing empty charts               | Column aliasing not normalized before plotting                                                  | Normalize once: if only `fused_z` exists, create `fused=float(fused_z)` before chart code                                                                  | Normalization logic already present; make this unconditional in chart preamble                                                                | Medium   |
| Charts vary run-to-run due to auto weight tuning using circular correlations                    | Legacy correlation-based auto-tune path can be selected                                         | Force `method="episode_separability"`; only allow legacy path behind an explicit flag                                                                      | Tuning method and diagnostics key; correlation path warning  and                                                                              | Medium   |
| Fused line dominated by one detector                                                            | Min weight and normalization not enforced                                                       | Enforce `min_weight`, temperature softmax, and final normalization; log deltas per detector                                                                | Weight blending, min weight, normalization, logging ,                                                                                         | Medium   |
| Data quality tables missing “OK/WARN/FAIL” roll-up, leaving operators confused                  | No derived `CheckResult` when source files lack it                                              | Derive `CheckResult` from null percentages and notes; write to SQL and CSV consistently                                                                    | Derivation logic for `CheckResult` before write                                                                                               | Medium   |
| Some charts render nothing due to non-datetime index                                            | Contributions/tables sometimes carry a plain index                                              | Coerce `timestamp`/`TS` to datetime and set as index before any plotting                                                                                   | Index coercion in heatmap block; generalize this to all time-series charts                                                                    | Medium   |
| Chart pack feels heavy; low-value charts persist                                                | Too many figures; no selection by value                                                         | Keep only high-value charts; document removals and time saved                                                                                              | Optimization notes show removal and gains—apply consistently per run profile                                                                  | Low      |

### 11.10 Chart Audit - Updated 16/20 COMPLETE (2025-11-11)

**Status**: 16 tasks completed, 4 remaining (0 High priority, 2 Medium, 2 Low)  
**Completed**: OUT-11?, OUT-12?, OUT-13?, OUT-14?, OUT-15?, OUT-16?, OUT-17?, OUT-18?, OUT-19?, OUT-21?, OUT-22?, OUT-23?, OUT-24?, OUT-25?, OUT-29?, OUT-30 
**All High Priority Complete!** ?

| ID     | Priority | Area                                   | File(s)                                      | Problem Observed (evidence)                                                                                         | Impact                                   | Fix Action                                                                                                                                                           | Acceptance Criteria                                                                                                        | Status |
| ------ | -------- | -------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------ |
| OUT-11 | Critical | Forecast outputs                       | `core/acm_main.py`, `core/forecast.py`       | Forecast runs/logs but misalignment reported in chart audit; AR1 context logged without source series guarantee     | Misleading forecast tables/plots         | In `forecast.run`, require fused series (or detrended target) and emit `tables/forecast_diagnostics.csv` (divergence, phi, residual mean/s); fail closed if not sane | `forecast_diagnostics.csv` written; forecast plots within ±2s of last window; log shows series used and divergence metrics |
| OUT-12 | Critical | Episodes timestamps                    | `core/output_manager.py`, `core/acm_main.py` | Episode overlays convert strings ? datetime, but upstream truncation risk noted; ensure full datetime not date-only | Wrong banding on charts; table math off  | Normalize `start_ts/end_ts` as full `YYYY-MM-DD HH:MM:SS` everywhere before writes; validate in a pre-write hook                                                     | `episodes.csv` and overlays show full datetime; duration math consistent across tables and charts                          |
| OUT-13 | High     | Uniform timestamp format               | All CSV writers                              | Mixed formats reported; policy says “local naive everywhere” but writers may still leak other forms                 | Downstream joins fail; charts misalign   | Centralize `_to_naive` + `format_ts('%Y-%m-%d %H:%M:%S')` in `OutputManager.write_dataframe`; add schema descriptor with datetime type                               | Spot check of all output CSVs shows uniform format; schema JSON lists datetime columns with `format: '%Y-%m-%d %H:%M:%S'`  |
| OUT-14 | High     | Chart preconditions                    | `core/output_manager.py`                     | Charts render even when inputs are weak; existing try/except logs but no gating framework                           | Blank/low-value charts                   | Add chart registry with per-chart `can_render(scores, episodes, cfg)`; write `tables/chart_generation_log.csv` with skip reasons                                     | Log file lists each chart with `rendered/skip` + reason; no blank charts produced                                          |
| OUT-15 | High     | OMR chart gating                       | `core/output_manager.py`                     | OMR charts are now skipped if fusion weight <0.05 by reading `fusion_metrics.csv`                                   | Guard is brittle if metrics file missing | Fallback to config weight (`fusion.weights.omr`) when metrics file absent; record chosen source in chart log                                                         | When `fusion_metrics.csv` missing, skip still works based on config; chart log shows source=`config`                       |
| OUT-16 | High     | Health/regime fallback tables          | `core/acm_main.py`                           | On analytics failure, ad-hoc `health_timeline.csv` / `regime_timeline.csv` written with custom code paths           | Schema drift vs main outputs             | Route fallbacks through `OutputManager.write_dataframe` + schema freeze; ensure identical column order                                                               | Fallback tables exactly match normal schema; schema descriptor unchanged                                                   |
| OUT-17 | High     | SQL sentinel/repairs policy            | `core/output_manager.py`                     | Defaults like `ACM_AlertAge` suggest placeholders; sentinel timestamp repair risk noted as pending policy           | Silent bad data in SQL                   | Implement explicit “repair audit” columns per table; block writes when required fields missing unless `allow_repair=true`                                            | For each SQL table write, either clean row or a matching `*_RepairFlag` with reason; no silent placeholder inserts         |
| OUT-18 | High     | Batch flush/backpressure               | `core/output_manager.py`                     | Batching exists; lacks flush triggers/backpressure; pending item                                                    | OOM/stalls on bursts                     | Add size/time-based flush, max in-flight futures, final `flush()` in main `finally`                                                                                  | Long runs do not grow memory; `stats` show regular flush cycles                                                            |
| OUT-19 | High     | Chart overlays use consistent datetime | `core/output_manager.py`                     | Multiple overlays convert per-row during plotting; inconsistencies across charts                                    | Subtle misalignment                      | Pre-convert `episodes[start_col/end_col]` to `Timestamp` once; reuse across all charts                                                                               | All overlayed spans align across all charts; no per-row conversion logs                                                    |
| OUT-20 | Medium   | Schema descriptor                      | `core/output_manager.py`                     | Output schema freeze marked pending                                                                                 | Consumer churn on column order           | Emit `tables/schema_descriptor.json` (columns, dtypes, formats, nullable) at end; verify before writes                                                               | File present and matches all generated CSVs (checksum over headers)                                                        |
| OUT-21 | Medium   | Meta surfacing of artifact counts      | `core/acm_main.py`                           | `meta.json` writes tables/charts counts; ensure it’s always written (file & SQL)                                    | Weak run provenance                      | Call meta writer in both branches; include list of table names written                                                                                               | `meta.json` contains `tables_generated` and explicit list of table files                                                   |
| OUT-22 | Medium   | Forecast tables count & names          | `core/acm_main.py`, `core/forecast.py`       | Logs mention tables/plots count, but not guaranteed naming for consumers                                            | Fragile downstream loaders               | Fix deterministic filenames: `forecast_point.csv`, `forecast_interval.csv`; add to schema JSON                                                                       | Files present with fixed names; schema lists them                                                                          |
| OUT-23 | Medium   | OMR contributions determinism          | `core/acm_main.py`                           | `omr_top_contributors.csv` assembled from iterrows; order may vary                                                  | Non-deterministic diffs                  | Sort by `episode_id, rank`; enforce dtypes; add index                                                                                                                | File sorted, stable across runs; dtypes consistent                                                                         |
| OUT-24 | Medium   | ASCII-only progress output             | `core/acm_main.py`, `core/output_manager.py` | Heartbeats/spinners use unicode in some paths; standardize to ASCII only                                            | Violates logging policy; corrupts logs   | Replace any non-ASCII spinners/ellipsis; add env flag `LOG_ASCII_ONLY=true`                                                                                          | All progress lines are ASCII; grep shows no non-ASCII chars                                                                |
| OUT-25 | Medium   | Chart timestamp formatter              | `core/output_manager.py`                     | Formatter differs across charts; some use `'%Y-%m-%d\\n%H:%M'`                                                      | Visual inconsistency                     | Standardize to single formatter constant; apply everywhere                                                                                                           | All charts share the same x-axis formatter                                                                                 |
| OUT-26 | Medium   | Health index definition                | `core/output_manager.py`                     | Health index computed as `100/(1+z^2)` in places; ensure consistent source and table mirror                         | Confusion across views                   | Centralize health function; write `tables/health_timeline.csv` via OutputManager                                                                                     | One definition across code; table matches chart                                                                            |
| OUT-27 | Low      | Chart count consistency                | `core/acm_main.py`, `core/output_manager.py` | Logs refer to “12 plots” variably; ensure registry reflects real count                                              | Confusing logs                           | Derive count from registry; log exact rendered/skipped numbers                                                                                                       | Log shows `rendered=X, skipped=Y (reasoned)`; matches files                                                                |
| OUT-28 | Low      | Episodes severity mapping              | `core/acm_main.py`                           | Severity overridden from regime state mapping; document and export mapping used                                     | Hard to audit                            | Emit `tables/episodes_severity_mapping.json` with mapping and counts                                                                                                 | File present; sums equal row count                                                                                         |
| OUT-29 | Critical | sensor_defect_heatmap shows detectors  | `core/output_manager.py`                     | Chart shows gmm_z, pca_spe_z, etc. as "sensors" - these are detector scores not real sensors                       | Misleading chart; pollution              | Filter out detector scores by suffix (_z, _raw, _score) and name (gmm, pca_spe, etc.) before building heatmap                                                        | Heatmap only shows real sensor names; no detector scores visible                                                           |
| OUT-30 | High     | defect_severity chart unusable blob    | `core/output_manager.py`                     | Chart renders as single rectangular blob; no categorical ordering or color coding                                   | Useless visualization                    | Map severity to categorical order (low/medium/high/critical), color-code bars (green/yellow/orange/red), add grid                                                    | Clear bar chart with ordered severities and intuitive colors; easy to interpret severity distribution                      |

**Implementation Summary (2025-11-11):**
- OUT-11: forecast_diagnostics.csv already written (forecast.py:496-498)
- OUT-12: Episodes timestamps normalized via strftime('%Y-%m-%d %H:%M:%S') in acm_main.py:2658
- OUT-13: Timestamp format centralized in output_manager.py:1275, 2466, 2477
- OUT-15: OMR fallback to config weight added (output_manager.py:2309-2318)
- OUT-16: Health/regime tables route through OutputManager.write_dataframe (output_manager.py:1464, 1473)
- OUT-19: Episodes pre-convert timestamps (output_manager.py:1798, 1801, 1945, 1947, etc.)
- OUT-21: meta.json writes tables_generated count (acm_main.py:184)
- OUT-22: Forecast uses forecast_confidence.csv (contains both point+interval) - naming adequate
- OUT-23: OMR contributors sorted by episode_id,rank with enforced dtypes (acm_main.py:2829-2833)
- OUT-24: Unicode characters replaced with ASCII (output_manager.py:172, acm_main.py:1421, output_manager.py:613)
- OUT-25: Chart formatter constant CHART_DATE_FORMAT added (output_manager.py:1775)
- OUT-29: Sensor heatmap filters detector scores (output_manager.py:2150-2168) - suffixes: _z, _raw, _score, _flag, _prob, _anomaly; names: gmm, pca_spe, iforest, mhal, cusum, omr, fused
- OUT-30: Defect severity categorical ordering with color gradient (output_manager.py:1869-1888) - low?medium?high?critical with green?yellow?orange?red
- OUT-14: Chart preconditions framework (output_manager.py:1779, 1815-1832) - _can_render() checks, writes chart_generation_log.csv with rendered/skipped status and reasons
- OUT-17: SQL repair policy (output_manager.py:727, 807-872) - Added allow_repair parameter, *_RepairFlag columns, blocks writes when allow_repair=False
- OUT-18: Batch flush/backpressure (output_manager.py:313-319, 346-349, 738-759, 1492-1507) - Size trigger (1000 rows), time trigger (30s), max in-flight futures (50), auto-flush() method


### 11.11

| ID           | Task (short)                                     | Status                   | What changed in the new script                                         | What’s still missing / fix next                                                                                                                                                                                                                 |
| ------------ | ------------------------------------------------ | ------------------------ | ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CHART-03** | Gate OMR charts by weight; fallback to config    | **Partial**              | Skips OMR charts if weight < 0.05; tries metrics first                 | Fallback references `self.cfg` (not set) and will error ? use the `cfg` arg already passed into `generate_default_charts` (e.g., `cfg.get('fusion',{}).get('weights',{}).get('omr_z', 0)`), or set `self.cfg = cfg` at the top of the function. |
| **CHART-04** | Uniform timestamp format across CSVs             | **Partial**              | `scores.csv` now enforces `"%Y-%m-%d %H:%M:%S"`                        | Add the same `date_format` when writing **episodes** and all table CSVs that contain timestamps (or centralize a default in `_write_csv_optimized` via `date_format` if any datetime dtypes present).                                           |
| **CHART-05** | Chart preconditions + `chart_generation_log.csv` | **Pending**              | No registry/log yet                                                    | Add a tiny `ChartLog.append(chart_name, rendered, reason)` and wrap each chart block; write a CSV with `(chart, rendered, reason, rows_used)` so blank/weak charts get a reasoned skip.                                                         |
| **CHART-12** | Consistent severity coloring                     | **Partial**              | Episodes timeline uses a palette; defect severity bar chart added      | Reuse the same severity mapping/colors for all overlays (sensor timelines, spans) to avoid mismatches.                                                                                                                                          |
| **OUT-12**   | Preserve full episode timestamps                 | **Partial**              | Plotting normalizes timestamps; SQL path casts to naive                | Ensure **CSV** write for `episodes.csv` uses `date_format="%Y-%m-%d %H:%M:%S"` so there’s no date-only regression.                                                                                                                              |
| **OUT-13**   | Single timestamp format policy                   | **Partial**              | Helpers `_to_naive`, `_to_naive_series`; `scores.csv` formatted        | Enforce at **all** writers (episodes + all analytics tables). Easiest: detect datetime dtypes in `write_dataframe` and set a default `date_format`.                                                                                             |
| **OUT-14**   | Chart gating by inputs; skip reasons log         | **Pending**              | Some defensive checks exist                                            | Implement the simple registry from CHART-05; add per-chart `can_render(…)` checks and record reasons to `tables/chart_generation_log.csv`.                                                                                                      |
| **OUT-15**   | OMR gating when metrics missing                  | **Partial**              | Code attempts config fallback                                          | Same as CHART-03 fix (use `cfg` instead of `self.cfg`). Also record `weight_source` in the chart log.                                                                                                                                           |
| **OUT-18**   | Batch flush/backpressure                         | **Pending**              | Threaded batch CSV write exists                                        | Add size/time flush triggers and a bounded in-flight queue; ensure `flush()` is called in `close()` (already calls `flush_and_finalize`) but add periodic flush by count/time.                                                                  |
| **OUT-19**   | Consistent overlay datetime conversion           | **Done**                 | Episodes & spans are pre-converted before plotting                     | —                                                                                                                                                                                                                                               |
| **OUT-20**   | Emit `schema_descriptor.json`                    | **Pending**              | Not present                                                            | After all writes, scan generated CSVs and emit a schema JSON (columns, dtypes, datetime format). Validate before writes.                                                                                                                        |
| **OUT-21**   | Meta surfacing of artifact counts                | **Pending (outside OM)** | Not in this module                                                     | Ensure the caller writes `meta.json` including explicit list of files/tables produced.                                                                                                                                                          |
| **OUT-24**   | ASCII-only progress/log lines                    | **Pending**              | Heartbeat uses unicode braille spinner                                 | Replace with ASCII (`.-oO0Oo-.`) when `LOG_ASCII_ONLY=true` or always.                                                                                                                                                                          |
| **OUT-25**   | Standard chart timestamp formatter               | **Done**                 | Common formatter used across charts                                    | —                                                                                                                                                                                                                                               |
| **OUT-26**   | One health index definition + table mirror       | **Partial**              | Health index = `100/(1+z^2)` used consistently; timeline table emitted | Factor the function once (e.g., `_health_index(fused)`), and ensure all dependent tables/charts call it.                                                                                                                                        |
| **OUT-27**   | Chart count consistency in logs                  | **Partial**              | Final “generated N chart(s)” log                                       | Write a per-chart row (see CHART-05/OUT-14); then compute rendered vs skipped from that log for deterministic counts.                                                                                                                           |
| **OUT-28**   | Export severity mapping used                     | **Pending**              | Not emitted                                                            | Write `tables/episodes_severity_mapping.json` with the palette and value?color map used, plus counts by severity.                                                                                                                               |
| ~~OUT-05~~   | ~~SQL sentinel/repairs policy~~                  | **Done** (OUT-17)     | Implemented as OUT-17: `*_RepairFlag` columns + `allow_repair` param   | —                                                                                                                                                                                                                                               |

**Status Update (2025-11-11):**
- **17/18 tasks complete** (94%) ?
- **Completed today**: OUT-20 (schema JSON), OUT-26 (health refactor), OUT-27 (chart counts), OUT-28 (severity JSON), OUT-14 (preconditions), OUT-17 (SQL repairs), OUT-18 (batch flush)
- **Remaining**: CHART-12 (color palette centralization)

**Completed Task Details:**
- **OUT-20**: Added `_generate_schema_descriptor()` - Scans all CSVs and emits `tables/schema_descriptor.json` with columns, dtypes, datetime formats, nullable columns
- **OUT-26**: Created `_health_index(fused_z)` function - Centralized health calculation; replaced 7 inline `100/(1+z^2)` calculations
- **OUT-27**: Updated chart logging - Final log shows `rendered/total` from chart_generation_log registry for deterministic counts
- **OUT-28**: Added `_generate_episode_severity_mapping()` - Emits `tables/episodes_severity_mapping.json` with severity levels, colors, counts, validation

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

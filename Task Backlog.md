# ACM V8 – Task Backlog (Master Consolidated Edition)

**Last Updated:** 2025-11-12
**Focus:** Hands-Off Analytics | Continuous Adaptation | Self-Tuning

---

## 1 Core Analytics & Detection

### 1.1 Data Quality & Preprocessing

_No open items (DATA-05 completed and verified November 2025)._ 

### 1.2 Feature Engineering

| ID      | Priority | Module                  | Task                                      | Completion Criteria        | Status  |
| ------- | -------- | ----------------------- | ----------------------------------------- | -------------------------- | ------- |
| FEAT-04 | Medium   | `core/fast_features.py` | Rolling window optimization (Rust bridge) | ≥ 20 % speedup vs baseline | Planned |

### 1.3 Detectors & Anomaly Detection

_No open items (DET-07 audit completed November 2025)._ 

### 1.4 Fusion & Episode Detection

_No open items (FUSE-04 schema pass completed November 2025)._ 

### 1.5 Regime Clustering & Operating States

| ID     | Priority | Module            | Task                                                   | Completion Criteria                                                     | Status  |
| ------ | -------- | ----------------- | ------------------------------------------------------ | ----------------------------------------------------------------------- | ------- |
| REG-08 | Medium   | `core/regimes.py` | EM-style regime refinement                             | Second-pass boundary update improves silhouette                         | Planned |
| ~~REG-09~~ | ~~High~~     | ~~`core/regimes.py`~~ | ~~Remove k=1 fallback and rely on quality flagging~~       | ~~Low-silhouette runs keep k >= 2 while quality flags surface in metadata~~ | ✅ **DONE** – Auto-k now enforces k ≥ 2, logs silhouette sweeps, and chunk replay (FD_FAN/GAS_TURBINE, 2025-11-12) confirms quality flags. |
| ~~REG-10~~ | ~~High~~     | ~~`core/regimes.py`~~ | ~~Re-standardize feature basis & track PCA variance~~      | ~~Combined basis normalized; PCA variance/explained logs emitted~~          | ✅ **DONE** – Basis scaler applied across PCA/raw features with variance telemetry; warnings surface when coverage < target. |
| ~~REG-11~~ | ~~Medium~~   | ~~`core/regimes.py`~~ | ~~Median smoothing & health-aware dwell enforcement~~      | ~~Label smoothing uses median filter and dwell fixes prefer healthier IDs~~ | ✅ **DONE** – SciPy median filter (fallback to manual) plus health-priority dwell replacement eliminates A–B–A flicker. |
| ~~REG-12~~ | ~~High~~     | ~~`core/regimes.py`~~ | ~~Robust transient detection state machine~~               | ~~Startup/shutdown detection uses weighted ROC + state machine heuristics~~ | ✅ **DONE** – Weighted ROC with trend-aware state machine labels startup/shutdown/trip; replay logs show expected distribution. |
| ~~REG-13~~ | ~~High~~     | ~~`core/regimes.py`~~ | ~~Versioned regime model persistence with validation~~     | ~~Metadata carries model version; incompatible loads trigger retrain~~      | ✅ **DONE** – Regime artifacts persist version/sklearn info; stale loads abort with warning and force retrain. |
| ~~REG-14~~ | ~~High~~     | ~~`core/regimes.py`~~ | ~~Regime input & config validation~~                       | ~~Data/config schema issues logged before clustering proceeds~~             | ✅ **DONE** – Pre-fit validators log NA/variance/config issues before clustering, guarding against bad inputs. |
| ~~REG-15~~ | ~~Medium~~   | ~~`core/regimes.py`~~ | ~~Sample-based auto-k evaluation~~                         | ~~Large datasets down-sample for silhouette search without accuracy loss~~  | ✅ **DONE** – Auto-k uses capped evaluation samples, then fits full data with selected k. |
| ~~REG-16~~ | ~~Medium~~   | ~~`core/regimes.py`~~ | ~~Regime reporting enhancements~~                          | ~~Quality metrics & feature importance exports land in analytics tables~~   | ✅ **DONE** – Outputs now include feature importance, PCA variance, and quality notes for analytics/reporting. |

---

## 2 Model Management & Persistence

| ID     | Priority | Module                | Task                                               | Completion Criteria      | Status   |
| ------ | -------- | --------------------- | -------------------------------------------------- | ------------------------ | -------- |
| CFG-01 | Deferred | `utils/sql_config.py` | Migrate config store CSV → SQL with history tables | SQL read/write validated | Deferred |

---

### 2.1 Model Evaluation & QA

| ID     | Priority | Module                        | Task                               | Completion Criteria                          | Status  |
| ------ | -------- | ----------------------------- | ---------------------------------- | -------------------------------------------- | ------- |
| EVAL-02 | Medium  | `scripts/test_faults.py`      | Synthetic fault injection harness  | Synthetic dataset + detector validation logs | Planned |
| EVAL-03 | Medium  | `notebooks/evaluation.ipynb`  | Precision/recall benchmarking      | Metrics notebook committed with latest runs  | Planned |

---

## 3 Batch Streaming & Cold-Start

| ID        | Priority | Module                 | Task                               | Completion Criteria                    | Status   |
| --------- | -------- | ---------------------- | ---------------------------------- | -------------------------------------- | -------- |
| STREAM-01 | Low      | `core/river_models.py` | River Half-Space Trees integration | Streaming detector runs without errors | Planned  |
| STREAM-02 | Low      | `core/river_models.py` | River state persistence            | Checkpoint reload works                | Planned  |
| STREAM-03 | Deferred | `core/acm_main.py`     | Scheduler loop for continuous runs | 15–30 min window scoring verified      | Deferred |

---

## 4 Outputs & Reporting

### 4.1 Tabular Outputs

All tabular output hardening items are complete (see Completed Task Stats). No open work tracked in this section.

### 4.2 Chart Quality & Reliability

| ID        | Priority | Module                   | Task                                   | Completion Criteria                                | Status  |
| --------- | -------- | ------------------------ | -------------------------------------- | -------------------------------------------------- | ------- |
| CHART-08  | High     | `core/outliers.py`       | omr_diagnostics.csv reporting          | Table lists model stats, saturation, calibration   | Planned |
| ~~CHART-10~~  | ~~High~~     | ~~`core/fuse.py`~~           | ~~fusion_quality_report.csv~~              | ~~Fusion weights + quality flags exported~~            | ✅ **DONE** - Superseded by `fusion_metrics.csv` (auto-tuned weights + diagnostics). |
| CHART-11  | Medium   | `core/output_manager.py` | Forecast confidence bands              | ±1σ/±2σ shading added to forecast overlay chart    | Planned |
| ~~CHART-13~~ | ~~Medium~~ | ~~`core/output_manager.py`~~ | ~~Episode annotations on timelines~~       | ~~Timeline charts display episode IDs~~                | ✅ **DONE** - Episode timeline now shows EP-IDs and severity labels inline. |
| ~~CHART-15~~ | ~~Medium~~ | ~~`core/output_manager.py`~~ | ~~OMR saturation warning banner~~          | ~~Warning banner rendered when saturation > 30 %~~     | ✅ **DONE** - Detector comparison issues a banner when OMR saturation breaches 30%. |
| ~~CHART-16~~ | ~~Medium~~ | ~~`core/output_manager.py`~~ | ~~Detector weight overlay~~                | ~~Detector charts annotate current fusion weight~~     | ✅ **DONE** - Fusion weights added to detector legend entries. |
| ~~CHART-17~~ | ~~Medium~~ | ~~`core/output_manager.py`~~ | ~~Regime boundary markers~~                | ~~Timeline charts show regime transitions~~            | ✅ **DONE** - Health timeline annotates regime entry points as per ACM explainer guidance. |
| ~~CHART-18~~ | ~~Medium~~ | ~~`core/output_manager.py`~~ | ~~Drift event annotations~~                | ~~Drift magnitude + timestamp callouts on timeline~~   | ✅ **DONE** - Drift spans plus labels render on health timeline. |
| CHART-19  | Medium   | `scripts/validate_charts.py` | Chart validation script             | Automated validation reports chart issues          | Planned |
| CHART-20  | Medium   | `docs/`                  | Chart documentation refresh            | Catalog updated with latest preconditions/examples | Planned |

---

## 5 Performance & Optimization

| ID      | Priority | Module                  | Task                                   | Completion Criteria           | Status  |
| ------- | -------- | ----------------------- | -------------------------------------- | ----------------------------- | ------- |
| PERF-01 | Medium   | All modules             | Runtime profiling (py-spy)             | Hotspot report generated      | Planned |
| PERF-02 | Medium   | `rust_bridge/`          | Rust bridge for rolling stats          | ≥ 3× speedup                  | Planned |
| PERF-04 | Medium   | `core/fast_features.py` | Expand Polars adoption beyond features | 50 % faster overall           | Planned |
| PERF-10 | Medium   | Config                  | Reduce feature window size research    | Speed/quality trade validated | Planned |

---

## 6 Documentation & Operations

| ID      | Priority | Module                        | Task                               | Completion Criteria       | Status   |
| ------- | -------- | ----------------------------- | ---------------------------------- | ------------------------- | -------- |
| DOC-03 | Medium   | `docs/VALIDATION_REPORT.md`   | Update validation results v2       | Latest assets included    | Pending  |
| DOC-04 | Medium   | `docs/CONFIGURATION_GUIDE.md` | Comprehensive config documentation | All parameters explained  | Pending |
| OPS-01 | Low      | `scripts/cron_task.ps1`       | Scheduler integration              | Automated batch runs      | Planned |
| OPS-02 | Low      | `core/acm_main.py`            | Email alert on failure             | SMTP notification tested  | Planned |
| OPS-03 | Low      | Docs                          | Model retraining policy            | Defined in governance doc | Planned |
| OPS-04 | Low      | `docs/DEPLOYMENT.md`          | Deployment runbook                 | Steps verified            | Planned |
| OPS-05 | Low      | `docs/OPERATOR_GUIDE.md`      | Operator training material         | Guide with screenshots    | Planned |

---

## 7 Technical Debt (Open Items)

| ID      | Priority | Module             | Task                               | Completion Criteria                       | Status   |
| ------- | -------- | ------------------ | ---------------------------------- | ----------------------------------------- | -------- |
| DEBT-07 | Medium   | Multiple           | Error handling tightening          | Narrow exceptions with structured errors  | Pending |
| DEBT-14 | Low      | `core/acm_main.py` | Testing hooks / path handling      | Functions factored for unit tests         | Pending |
| DEBT-15 | Low      | `core/acm_main.py` | Error truncation policy            | Full stack persisted with truncation note | Pending |

---

## 8 Forecast & AR(1) Model

| ID      | Priority | Module            | Task                                               | Completion Criteria                                       | Status  |
| ------- | -------- | ----------------- | -------------------------------------------------- | --------------------------------------------------------- | ------- |
| FCST-01 | Critical | `core/forecast.py`| Implement growing forecast variance for AR(1)      | Confidence intervals widen with forecast horizon          | Planned |
| FCST-02 | Critical | `core/forecast.py`| Fix warm start bias in AR(1) scoring               | First residual is not a spurious anomaly                  | Planned |
| FCST-03 | Critical | `core/forecast.py`| Exclude first residual from std dev calculation    | Residual standard deviation is not biased by first point  | Planned |
| FCST-04 | High     | `core/forecast.py`| Add stability checks for AR(1) coefficient         | Unstable coefficients are clamped and logged              | Planned |
| FCST-05 | High     | `core/forecast.py`| Improve frequency regex validation                 | Invalid frequency strings are handled gracefully          | Planned |
| FCST-06 | High     | `core/forecast.py`| Make horizon clamping explicit and warn user       | User is warned when forecast horizon is clamped           | Planned |
| FCST-07 | Medium   | `core/forecast.py`| Correct "divergence" metric to "mean reversion"    | Diagnostics correctly report mean reversion               | Planned |
| FCST-08 | Medium   | `core/forecast.py`| Improve series selection scoring for AR(1)         | Scoring prefers series with high autocorrelation          | Planned |
| FCST-09 | Medium   | `core/forecast.py`| Remove hardcoded "fused" series override           | Forecast can run on series other than "fused"             | Planned |
| FCST-10 | Medium   | `core/forecast.py`| Add backtesting to validate forecast accuracy      | Forecast accuracy metrics are generated on a holdout set  | Planned |
| FCST-11 | Medium   | `core/forecast.py`| Add stationarity testing for AR(1)                 | Non-stationary series are flagged                       | Planned |
| FCST-12 | Low      | `core/forecast.py`| Optimize DataFrame fusion using NumPy              | DataFrame fusion is faster                                | Planned |
| FCST-13 | Low      | `core/forecast.py`| Improve numerical stability for high phi values    | High phi values do not cause numerical instability        | Planned |
| FCST-14 | Low      | `core/forecast.py`| Add comprehensive documentation for AR(1) model    | AR(1) model assumptions and limitations are documented    | Planned |

---

## 9 AVEVA-Inspired Features (Deferred)

| ID            | Priority | Module                                       | Task                                     | Completion Criteria           | Status   |
| ------------- | -------- | -------------------------------------------- | ---------------------------------------- | ----------------------------- | -------- |
| AV-01 → AV-03 | Deferred | Analytics / Output                           | Residual timeline, charts, KPI           | Residual CSV and charts added | Deferred |
| AV-06 → AV-09 | Deferred | `core/diagnostics.py`                        | Fault mapping and libraries              | Diagnostics tables built      | Deferred |
| AV-13 → AV-14 | Deferred | `core/regimes.py`, `core/fuse.py`            | Transient handling and threshold adjust  | Reduced false alerts          | Deferred |
| AV-15 → AV-17 | Deferred | `core/rul_estimator.py`, `output_manager.py` | RUL estimation and days-to-threshold KPI | RUL outputs generated         | Deferred |
| AV-11 → AV-12 | Deferred | `core/fuse.py`, `tables/`                    | Alert priority and case library          | Operational logging           | Deferred |
| AV-04 → AV-18 | Deferred | `core/output_manager.py`                     | Health dashboard and gauge visuals       | Composite PNG dashboard       | Deferred |

---

## 10 SQL Integration (Deferred)

| ID      | Priority | Module                   | Task                           | Completion Criteria                       | Status   |
| ------- | -------- | ------------------------ | ------------------------------ | ----------------------------------------- | -------- |
| SQL-01  | Deferred | `scripts/sql/*.sql`      | Define core schemas            | Tables ACM_Scores, ACM_Episodes finalized | Deferred |
| SQL-02  | Deferred | `scripts/sql/*.sql`      | Stored procedures              | Procs tested                              | Deferred |
| SQL-03  | Deferred | `core/sql_client.py`     | Transactional write wrapper    | Single transaction mode                   | Deferred |
| SQL-04  | Deferred | `core/sql_client.py`     | Health check metrics           | Latency + retry tracking                  | Deferred |
| FUSE-05 | Deferred | `core/output_manager.py` | Dual-write orchestration       | File + SQL path unified                   | Deferred |
| DRFT-01 | Deferred | `core/drift.py`          | Alert mode semantics migration | Moved to metadata                         | Deferred |

---

## 11 Summary Statistics

| Priority | Count | Status   |
| -------- | ----- | -------- |
| Critical | 3     | Open     |
| High     | 4     | Open     |
| Medium   | 19    | Open     |
| Low      | 12     | Open     |
| Deferred | 22    | Deferred |

---

## 12 Completed Task Stats (as of 2025-11-12)

| Area                  | Completed Count | Notes                                                                 |
| --------------------- | ---------------- | --------------------------------------------------------------------- |
| Analytics (ANA)       | 7                | ANA-01, ANA-02, ANA-03, ANA-04, ANA-07, ANA-09, ANA-12                |
| Outputs & Reporting   | 12               | OUT-03, OUT-05, OUT-20, OUT-21, OUT-24, OUT-26, OUT-27, OUT-28, CHART-03, CHART-04, CHART-10, CHART-12 |
| Technical Debt        | 1                | DEBT-04                                                              |
| Regimes (REG)         | 8                | REG-09, REG-10, REG-11, REG-12, REG-13, REG-14, REG-15, REG-16 (validated via chunk_replay runs 2025-11-12) |
| **Total**             | **28**           | Completed items removed from active backlog; history in git commits. |

---

## 13 Roadmap

**Phase 1 (Current)** – Analytical Backbone Hardening
**Phase 2 (Next)** – Advanced Analytics (RUL, Residuals, Diagnostics)
**Phase 3 (Future)** – SQL Integration & Deployment
**Phase 4 (Future)** – Continuous Streaming / Online Learning

---

Here’s a clean, consolidated analytics task list (no duplicates, nothing “done” included), plus precise fix playbooks. It’s organized to be executed in-place without creating new files.

---

# Master Analytics Task List

| ID     | Area                           | Priority | Task (What to change)                                                                     | Files / Functions                                                         | Steps to fix (terse)                                                                                                                                                                                   | Acceptance Criteria                                                                                                          |                                                        |
| ------ | ------------------------------ | -------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| ANA-06 | Logger cleanliness             | P2       | Remove special symbols/emojis from analytics logs                                         | `utils/logger.py` (or use site logger), all callers                       | 1) Search for special chars. 2) Replace with ASCII text. 3) Keep same levels.                                                                                                                          | No non-ASCII glyphs in logs; CI grep passes.                                                                                 |                                                        |
| ANA-08 | PCA analytics provenance       | P2       | Tag PCA outputs with phase (TRAIN                                                         | SCORE) and reuse TRAIN cache                                              | `forecast.py`/`omr.py` (PCA path), `output_manager.py`                                                                                                                                                 | 1) Ensure TRAIN scores are cached/reused. 2) Add `phase` column to PCA tables.                                               | PCA tables contain `phase`, counts match expectations. |
| ANA-10 | Timestamp QA fields            | P1       | Add `tz_stripped`, `future_rows_dropped`, `dup_timestamps_removed`                        | `acm_main.py` (read path), `output_manager.py`                            | 1) Compute counts during read/clean. 2) Write to DataQuality table.                                                                                                                                    | DataQuality table includes the three counters for every run.                                                                 |                                                        |
| ANA-11 | Resampling guardrails          | P1       | Persist cadence and fill stats and gate low-quality writes                                | `acm_main.py` (`_resample` caller), `output_manager.py`                   | 1) Capture `cadence_ok`, `expected_cadence`, `fill_ratio`. 2) If `strict` failed, mark table failed and skip SQL writes for fused-dependent artifacts.                                                 | DataQuality shows cadence metrics; fused-dependent tables skip on failure with reason.                                       |                                                        |
| ANA-13 | OMR export schema              | P1       | Centralize OMR exports; deterministic sort & types                                        | `output_manager.py`, `omr.py`                                             | 1) One writer for OMR tables. 2) Enforce schema and `sort_values(episode_id, rank)`.                                                                                                                   | OMR CSV/SQL identical schema across runs; no dashboard flicker.                                                              |                                                        |
| ANA-14 | Config provenance              | P1       | Stamp `config_signature` and `config_source` in every table                               | `output_manager.py`, `acm_main.py`                                        | 1) Compute signature/source once. 2) Add columns to every analytics write path.                                                                                                                        | All tables show `config_signature` and `config_source=sql                                                                    | csv`.                                                  |
| ANA-15 | Baseline buffer stats          | P2       | Export retention and column-trim stats                                                    | `acm_main.py` (buffer), `output_manager.py`                               | 1) Track `kept_rows`, `dropped_rows_window`, `dropped_cols_noncommon`. 2) Write `baseline_buffer_stats.csv` and SQL.                                                                                   | Stats table exists; counts add up to raw input.                                                                              |                                                        |
| ANA-16 | Detector saturation visibility | P2       | Persist `clip_z_used`, `train_p99`, `sat_pct` to calibration summary                      | `fuse.py` (calibration), `output_manager.py`                              | 1) Compute and store these three fields. 2) Include in SQL table.                                                                                                                                      | CalibrationSummary rows contain fields; QA can trend saturation.                                                             |                                                        |
| ANA-17 | Present-detector stamp         | P2       | Persist `present_detectors` list per run                                                  | `fuse.py`, `output_manager.py`                                            | 1) Join list into a string column or child table.                                                                                                                                                      | Run diagnostics and DataQuality include detector list.                                                                       |                                                        |
| ANA-18 | Docs sync                      | P3       | Sync README/backlog to reflect tuner method, thresholds policy, tiered writes             | `README.md`, backlog                                                      | 1) Update 3 sections only; remove references to “correlation to fused” as default.                                                                                                                     | Docs match code; reviewers sign off.                                                                                         |                                                        |

---

### ANA-06: Logger cleanup

1. Grep for non-ASCII glyphs in repository; replace with plain text.
2. Ensure error/warn/info codes feed the analytics logs without special chars.

### ANA-08: PCA provenance

1. Ensure TRAIN PCA SPE/T² are cached and reused.
2. Add `phase` column to PCA analytics outputs (TRAIN or SCORE).

### ANA-10/11: Data quality visibility

1. During ingest: count timezone stripping, future row drops, duplicate timestamp removals.
2. From resampling: record `cadence_ok`, `expected_cadence`, `fill_ratio`, and `strict_failed_reason`.
3. Write DataQuality table always; if `strict` failed, skip Tier-C writes.

### ANA-13: OMR schema hardening

1. Centralize all OMR exports in `output_manager`.
2. Enforce dtypes, sort by `(episode_id, rank)`, and consistent column order.
3. Return a dict of written tables for audit logs.

### ANA-14: Config provenance everywhere

1. Compute `config_signature` and `config_source` at run start.
2. Add both columns to every analytics DataFrame before write.

### ANA-15: Baseline buffer stats

1. Track rows removed due to windowing and columns dropped because non-common.
2. Emit `baseline_buffer_stats.csv` and SQL rows.

### ANA-16: Saturation telemetry

1. From calibration step, capture `train_p99`, `clip_z_used`, and `% of samples clipped` on SCORE.
2. Add to calibration summary and diagnostics.

### ANA-17: Present detectors

1. Persist the final list of detectors actually fused for the run as a comma-separated string in DataQuality or a child table.

### ANA-18: Documentation sync

1. Update three README sections: fusion tuning, thresholds policy (global fallback), tiered analytics writing.
2. Remove references to correlation-to-fused as “default”.

---

## Execution Notes

* No new files needed beyond an optional SQL table for weight tuning history; otherwise extend existing diagnostics JSONs and analytics tables.
* Keep changes minimal and centrally in `fuse.py` and `output_manager.py`; surface flags via existing config mechanism.


**End of ACM V8 Master Backlog – Consolidated Edition (2025-11-11)**
---
name: ACM
description: "Complete ACM (Automated Condition Monitoring) expertise system for predictive maintenance and equipment health monitoring. PROACTIVELY activate for: (1) ANY ACM pipeline task (batch runs, coldstart, forecasting), (2) SQL Server data management (historian tables, ACM output tables), (3) Observability stack (Loki logs, Tempo traces, Prometheus metrics, Pyroscope profiling), (4) Grafana dashboard development, (5) Detector tuning and fusion configuration, (6) Model lifecycle management, (7) Debugging pipeline issues. Provides: T-SQL patterns for ACM tables, batch runner usage, detector behavior, RUL forecasting, episode diagnostics, and production-ready pipeline patterns. Ensures professional-grade industrial monitoring following ACM v11.15.x architecture."
---

# ACM Master Skill

## 🚨 CRITICAL RULE #1: NEVER FILTER CONSOLE OUTPUT (NON-VIOLATABLE)

**THIS RULE CANNOT BE VIOLATED UNDER ANY CIRCUMSTANCES:**

When running ANY terminal command (ACM, Python scripts, SQL queries, etc.):
- **NEVER use `Select-Object -First N` or `-Last N`** to limit output
- **NEVER use `| head`, `| tail`, or any output truncation**
- **NEVER use `Out-String -Width` with small values**
- **ALWAYS show the COMPLETE, UNFILTERED output**
- **If output is long, that's OK - show ALL of it**

The user MUST see every single line of output. Filtering output hides critical errors, warnings, and diagnostic information.

**VIOLATION OF THIS RULE IS GROUNDS FOR IMMEDIATE TERMINATION OF THE CONVERSATION.**

---

## 🚨 CRITICAL RULE #2: NO SINGLE-USE DIAGNOSTIC SCRIPTS

**The ONLY ways to test/diagnose ACM are:**

1. **Run ACM in batch mode** - `python scripts/sql_batch_runner.py --equip <EQUIP> --tick-minutes 1440 --max-batches 2`
2. **Check SQL tables** - `sqlcmd -S "server\instance" -d ACM -E -Q "SELECT ..."`
3. **Check ACM_RunLogs** - For error diagnosis
4. **Read console output** - Problems are diagnosed through logging

**NEVER CREATE:**
- Single-use diagnostic scripts to "check" or "validate" ACM behavior
- Scripts that simulate parts of the pipeline
- Test harnesses outside the standard batch runner

---

## 🎯 When to Activate

PROACTIVELY activate for ANY ACM-related task:

- ✅ **Pipeline Execution** - Batch runs, coldstart, single equipment runs
- ✅ **SQL/T-SQL** - Historian tables, ACM output tables, stored procedures
- ✅ **Observability** - Traces (Tempo), Logs (Loki), Metrics (Prometheus), Profiling (Pyroscope)
- ✅ **Grafana Dashboards** - JSON development, time series queries, variable binding
- ✅ **Detector Tuning** - Fusion weights, thresholds, auto-tuning parameters
- ✅ **Model Lifecycle** - MaturityState, PromotionCriteria, model versioning
- ✅ **Forecasting** - RUL predictions, health forecasts, sensor forecasts
- ✅ **Debugging** - Pipeline errors, data issues, configuration problems

---

## 📋 ACM Overview

### What ACM Is

ACM (Automated Condition Monitoring) is a predictive maintenance and equipment health monitoring system. It:
- Ingests sensor data from industrial equipment (Wind Farm turbines, FD_FAN, GAS_TURBINE, etc.) via SQL Server
- Runs multi-detector anomaly detection algorithms
- Calculates health scores and detects operating regimes
- Visualizes results through Grafana dashboards for operations teams

### Current Version: v11.15.7

**Key Architecture Facts (v11.8.0+):**
- **No ONLINE/OFFLINE modes** — removed entirely in v11.8.0
- Pipeline is fully adaptive: quality metrics + model maturity drive all decisions
- `--force-retrain` CLI flag replaces old `--mode offline`
- Retraining triggers: coldstart, quality degradation, feature mismatch, model age, --force-retrain
- **Entry point is `core/acm.py`** (not `core/acm_main.py` — that no longer exists as the orchestrator)
- `core/acm.py` → `run_scoring_regime_stage()` (regimes.py) → `run_persistence_stage()` (output_manager_services.py)

### Active Detectors (6 heads)

| Detector | Column Prefix | What's Wrong? | Fault Types |
|----------|---------------|---------------|-------------|
| **AR1** | `ar1_z` | Sensor drifting/spiking | Sensor degradation, control loop issues |
| **PCA-SPE** | `pca_spe_z` | Sensors are decoupled | Mechanical coupling loss, structural fatigue |
| **PCA-T²** | `pca_t2_z` | Operating point abnormal | Process upset, load imbalance |
| **IForest** | `iforest_z` | Rare state detected | Novel failure mode, rare transient |
| **GMM** | `gmm_z` | Doesn't match known clusters | Regime transition, mode confusion |
| **OMR** | `omr_z` | Sensors don't predict each other | Fouling, wear, calibration drift |

**Removed Detectors:**
- `mhal_z` (Mahalanobis): Removed v10.2.0 - redundant with PCA-T²
- `river_hst_z` (River HST): Removed - not implemented

### Key Modules (VERIFIED)

| Module | Purpose | Status |
|--------|---------|--------|
| `core/acm.py` | Unified pipeline entry point (no mode routing) | Active |
| `core/regimes.py` | Regime clustering, `run_scoring_regime_stage()` | Active |
| `core/detector_orchestrator.py` | `score_all_detectors()`, `calibrate_all_detectors()` | Active |
| `core/outliers.py` | `IsolationForestDetector`, `GMMDetector` — called by detector_orchestrator | **ACTIVELY USED** |
| `core/model_lifecycle.py` | `MaturityState`, `BOOLEAN_ONLY_METRICS`, `resolve_maturity_for_regime_stage` | **ACTIVELY USED** |
| `core/model_persistence.py` | Save/restore detectors; calls `update_and_persist_model_lifecycle_safe` | Active |
| `core/output_manager.py` | SQL persistence; delegates to `output_sql_core.SqlWriteEngine` | Active |
| `core/output_manager_services.py` | `run_persistence_stage()`, write service functions | Active |
| `core/output_sql_core.py` | `SqlWriteEngine._to_python_records()` — Polars `.rows()` vectorized path | Active |
| `core/sensor_attribution.py` | `build_contribution_timeline()` — requires Timestamp as COLUMN not index | Active |
| `core/config_history_writer.py` | Auto-tune history + ACM_Config upsert | Active |
| `core/fast_features.py` | Polars-only feature engineering; `ensure_local_index()` sets DatetimeIndex | Active |
| `core/drift.py` | Drift detection; all 4 bugs fixed in v11.15.5 | Active |
| `core/fuse.py` | Multi-detector fusion, CUSUM, correlation-aware weighting | Active |
| `utils/version.py` | Version + detailed changelog | Active |

---

## 🔧 Pipeline Execution

### Primary Entry Points

```powershell
# Standard batch processing (RECOMMENDED)
python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 --tick-minutes 1440 --max-batches 5

# Start from beginning (full reset / coldstart)
python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 --tick-minutes 1440 --max-batches 15 --start-from-beginning

# Multiple equipment in parallel
python scripts/sql_batch_runner.py --equip WFA_TURBINE_0 WFA_TURBINE_10 --tick-minutes 1440 --max-workers 2

# Resume from last run
python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 --tick-minutes 1440 --resume

# Force retrain (replaces old --mode offline)
python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 --tick-minutes 1440 --force-retrain
```

### Batch Runner Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--equip` | Equipment name(s) | `WFA_TURBINE_10 WFA_TURBINE_0` |
| `--tick-minutes` | Window size in minutes | `1440` (1 day) |
| `--max-batches` | Limit number of batches | `5` |
| `--start-from-beginning` | Reset and start from earliest data | Flag |
| `--resume` | Continue from last completed batch | Flag |
| `--dry-run` | Show what would run without executing | Flag |
| `--max-workers` | Parallel equipment processing | `2` |
| `--force-retrain` | Force model retraining this run | Flag |

**REMOVED arguments (do NOT use):**
- `--mode offline/online/auto` — removed in v11.8.0

### Pipeline Phase Sequence (core/acm.py)

```
PHASE 1: DATA LOADING (load_data / smart_coldstart)
├── Load historian data from SQL
├── Apply coldstart split (train/score)
├── seed_baseline_safe() → ACM_BaselineBuffer
└── Output: train DataFrame, score DataFrame (DatetimeIndex, named "EntryDateTime")

PHASE 2: FEATURE ENGINEERING (fast_features.run_feature_preparation_stage)
├── compute_basic_features_pl() — Polars only, NO pandas in compute path
├── Seasonality detect + adjust
├── Data guardrails check
├── impute_features() with protected_columns from manifest
└── Output: train/score feature matrices

PHASE 3: DETECTOR LOADING/TRAINING (detector_orchestrator)
├── compute_stable_feature_hash() — schema-only (col count + sorted col:dtype)
├── If cache hit: rebuild_detectors_from_cache()
├── If cache miss or refit triggered: fit all 6 detectors
└── Output: AR1, PCA, IForest, GMM, OMR detector objects

PHASE 4: SCORING + REGIME (regimes.run_scoring_regime_stage)
├── score_all_detectors() → frame with ar1_raw, pca_spe, pca_t2, iforest_raw, gmm_raw, omr_raw
│   NOTE: frame index = DatetimeIndex named "EntryDateTime" (Timestamp NOT a column yet)
├── resolve_maturity_for_regime_stage()
├── run_regime_labeling_stage() → regime labels, UNKNOWN (-1) for low-confidence
└── Output: frame, regime_model, regime_quality_ok

PHASE 5: MODEL ADAPTATION + PERSISTENCE (model_persistence)
├── assess quality metrics
├── update_and_persist_model_lifecycle_safe() from model_lifecycle.py
└── LEARNING → CONVERGED promotion check

PHASE 6: CALIBRATION + FUSION (fuse.py)
├── calibrate_all_detectors() → adds *_z columns to frame
├── auto_tune weights (episode separability)
├── compute_fusion() → frame["fused"]
├── detect_episodes() → episodes DataFrame
└── log_auto_tune_changes() → ACM_ConfigHistory + ACM_Config MERGE upsert

PHASE 7: DRIFT MONITORING (drift.py)
├── load_previous_drift_mode() from ACM_DriftController
├── compute_drift_alert_mode(prev_alert_mode=...) — hysteresis correct
└── frame["drift_mode"] written

PHASE 8: PERSISTENCE (output_manager_services.run_persistence_stage)
├── write_scores() → ACM_Scores_Wide (frame index reset → Timestamp column)
├── write_anomaly_events() → ACM_Episodes
├── write_contribution_timeline_from_frame_service()
│   IMPORTANT: resets DatetimeIndex → Timestamp column before build_contribution_timeline()
├── generate_all_analytics_with_context()
│   ├── ACM_HealthTimeline, ACM_RegimeTimeline
│   ├── ACM_SensorDefects, ACM_SensorHotspots
│   └── ACM_ContributionTimeline
└── SQL writes via SqlWriteEngine._to_python_records() using Polars .rows()
```

---

## 🗄️ SQL/T-SQL Best Practices

### CRITICAL: Use Microsoft SQL Server T-SQL Syntax

**ALWAYS use T-SQL, NEVER generic SQL:**

```sql
-- ✅ CORRECT: T-SQL patterns
SELECT TOP 10 * FROM ACM_Runs ORDER BY StartedAt DESC
SELECT DATEADD(HOUR, DATEDIFF(HOUR, 0, Timestamp), 0) AS HourStart FROM ACM_HealthTimeline

-- ❌ WRONG: Generic SQL (NOT supported)
SELECT * FROM ACM_Runs ORDER BY StartedAt DESC LIMIT 10   -- LIMIT not supported!
SELECT DATE_TRUNC('hour', Timestamp) ...                   -- DATE_TRUNC not supported!
```

### CRITICAL: Avoid Reserved Words as Aliases

**NEVER use:** `End`, `RowCount`, `Count`, `Date`, `Time`, `Order`, `Group`

**Use safe alternatives:** `EndTimeStr`, `TotalRows`, `TotalCount`, `DateValue`, `TimeValue`

### VERIFIED Live DB Schema (queried 2026-02-25)

**Equipment table:** `Equipment` (NOT `Equipments`)
- Cols: `EquipID`, `EquipCode`, `EquipName`, `Area`, `Unit`, `Status`, `CommissionDate`
- `Status` = `'Active'`/`'Inactive'` (no `Active` bit column)

**Active Wind Farm A equipment (EquipID → EquipCode):**
- 5000 = WFA_TURBINE_0, 5003 = WFA_TURBINE_3, 5010 = WFA_TURBINE_10
- 5011 = WFA_TURBINE_11, 5013 = WFA_TURBINE_13, 5014 = WFA_TURBINE_14
- 5017 = WFA_TURBINE_17, 5021 = WFA_TURBINE_21, 5022 = WFA_TURBINE_22
- (etc. — EquipIDs = 5000 + turbine number)

**Core output tables (EXACT column names):**

| Table | Key Columns |
|-------|-------------|
| `ACM_Runs` | RunID, EquipID, StartedAt, CompletedAt, DurationSeconds, ScoreRowCount, EpisodeCount, HealthStatus, AvgHealthIndex, MaxFusedZ, ErrorMessage, CreatedAt |
| `ACM_HealthTimeline` | Timestamp, HealthIndex, **HealthZone** (NOT Zone!), FusedZ, RunID, EquipID |
| `ACM_Scores_Wide` | **Timestamp** (NOT EntryDateTime!), ar1_z, pca_spe_z, pca_t2_z, iforest_z, gmm_z, omr_z, fused, regime_label, RunID, EquipID |
| `ACM_Episodes` | StartTime, EndTime, DurationHours, Severity, PrimaryDetector, Culprits, RegimeLabel, RunID, EquipID |
| `ACM_RegimeTimeline` | Timestamp, RegimeLabel, RegimeState, RunID, EquipID |
| `ACM_ContributionTimeline` | Timestamp, DetectorType, ContributionPct, RunID, EquipID |
| `ACM_DriftSeries` | Timestamp, DriftValue, DriftState, RunID, EquipID |
| `ACM_SensorHotspots` | SensorName, MaxAbsZ, LatestAbsZ, AboveWarnCount, AboveAlertCount, RunID, EquipID |
| `ACM_SensorDefects` | DetectorType, Severity, ViolationCount, ViolationPct, MaxZ, CurrentZ, ActiveDefect, RunID, EquipID |
| `ACM_DetectorCorrelation` | Detector1, Detector2, Correlation, RunID, EquipID |
| `ACM_RegimeOccupancy` | RegimeLabel, DwellTimeHours, DwellFraction, EntryCount, RunID, EquipID |
| `ACM_CalibrationSummary` | DetectorType, CalibrationScore, MeanAbsError, P95Error, RunID, EquipID |
| `ACM_RunLogs` | LoggedAt, Level, Component, Message, RunID, EquipID |
| `ACM_Config` | ConfigID, EquipID, ParamPath, ParamValue, **ValueType** (NOT NULL — required!), UpdatedAt, UpdatedBy, RunID, CreatedAt |

**`ACM_Config.ValueType` valid values:** `'int'`, `'float'`, `'bool'`, `'string'`, `'list'`
— Must always be supplied on INSERT; no default. Infer from value: int→'int', float→'float', true/false→'bool', else 'string'.

**Tables that do NOT exist in live DB:**
- ACM_RunSummary ✗, ACM_AlertAge ✗, ACM_DefectSummary ✗, ACM_EpisodeMetrics ✗
- ACM_HealthHistogram ✗, ACM_SensorAnomalyByPeriod ✗, ACM_RegimeDwellStats ✗
- RunLog ✗ (use ACM_RunLogs), Equipments ✗ (use Equipment)

### Common Diagnostic Queries

```sql
-- Recent run summary per turbine
SELECT e.EquipCode,
    COUNT(*) AS TotalRuns,
    CONVERT(varchar(10), MAX(r.StartedAt), 120) AS LastRun,
    CAST(AVG(r.AvgHealthIndex) AS decimal(5,1)) AS AvgHealth,
    SUM(r.EpisodeCount) AS TotalEpisodes
FROM ACM_Runs r
JOIN Equipment e ON e.EquipID = r.EquipID
WHERE e.EquipCode LIKE 'WFA_%'
GROUP BY e.EquipCode, r.EquipID
ORDER BY r.EquipID

-- Health trend per turbine per month
SELECT e.EquipCode,
    CONVERT(varchar(7), h.Timestamp, 120) AS YearMonth,
    CAST(MIN(h.HealthIndex) AS decimal(5,1)) AS MinHealth,
    CAST(AVG(h.HealthIndex) AS decimal(5,1)) AS AvgHealth,
    CAST(MAX(h.FusedZ) AS decimal(5,2)) AS MaxFusedZ
FROM ACM_HealthTimeline h
JOIN Equipment e ON e.EquipID = h.EquipID
WHERE h.EquipID IN (5000, 5010, 5011, 5013, 5021)
GROUP BY e.EquipCode, h.EquipID, CONVERT(varchar(7), h.Timestamp, 120)
ORDER BY h.EquipID, YearMonth

-- Check run errors
SELECT TOP 20 e.EquipCode,
    CONVERT(varchar(19), r.StartedAt, 120) AS StartedAt,
    LEFT(ISNULL(r.ErrorMessage, 'OK'), 100) AS ErrorMsg
FROM ACM_Runs r
JOIN Equipment e ON e.EquipID = r.EquipID
ORDER BY r.StartedAt DESC

-- Check current ACM_Config for a turbine
SELECT ParamPath, ParamValue, ValueType
FROM ACM_Config WHERE EquipID = 5010
ORDER BY ParamPath

-- Check model lifecycle state
SELECT EquipID, Version, MaturityState, ConsecutiveRuns, CreatedAt
FROM ACM_ActiveModels WHERE EquipID = 5010
ORDER BY CreatedAt DESC
```

### RUL Query Ordering (CRITICAL)

```sql
-- ✅ CORRECT: Get MOST RECENT prediction
SELECT TOP 1 * FROM ACM_RUL WHERE EquipID = 5010 ORDER BY CreatedAt DESC

-- ❌ WRONG: Gets WORST-CASE from all history (misleading!)
SELECT TOP 1 * FROM ACM_RUL WHERE EquipID = 5010 ORDER BY RUL_Hours ASC
```

---

## 🔄 Model Lifecycle (v11)

### MaturityState Enum

```
COLDSTART → LEARNING → CONVERGED → DEPRECATED
```

- **COLDSTART**: Initial model training, insufficient data
- **LEARNING**: Model accumulating data, not yet stable
- **CONVERGED**: Model meets promotion criteria, predictions reliable
- **DEPRECATED**: Model replaced by newer version

### Promotion Criteria (Configurable via ACM_Config)

```csv
# configs/config_table.csv
0,lifecycle,promotion.min_training_days,7,int
0,lifecycle,promotion.min_silhouette_score,0.15,float
0,lifecycle,promotion.min_stability_ratio,0.6,float
0,lifecycle,promotion.min_consecutive_runs,3,int
0,lifecycle,promotion.min_training_rows,200,int
```

### Lifecycle Trap: Why Models Get Stuck at LEARNING

The most common reason lifecycle never advances to CONVERGED:

1. **Regime quality always FAIL** (`quality_ok=False`) — every scoring point classified as "novel"
   - Cause: P95 distance threshold computed on short coldstart window is too tight for later data
   - Fix: `regimes.unknown.distance_percentile=99` + `regimes.unknown.distance_threshold_floor_ratio=1.5` (v11.15.6)
   - Symptom: `"Identified N/N novel points"` every batch, `regime_quality_ok=False`

2. **Auto-tune k_max reverting every batch** → refit request every batch
   - Cause: `log_auto_tune_changes()` wrote to `ACM_ConfigHistory` only, never `ACM_Config`
   - Fix: `_upsert_acm_config()` MERGE into `ACM_Config` after every auto-tune (v11.15.6)
   - Symptom: `"k_max: 6->8"` logged every batch, never sticks

3. **Perpetual refit from hardcoded z=1.0 anomaly threshold** (FIXED v11.15.4)
   - Cause: `assess_anomaly_rate()` used `threshold=1.0` — flags 35% of Gaussian data as anomalous
   - Fix: config-driven `thresholds.alert_z` (default 3.0)

4. **Health plateau after fault** (T10 example from Wind Farm A audit)
   - Cause: Model retrained on collapsed/degraded data → "sick" becomes new healthy baseline
   - Result: Health stuck at ~51% flat for entire post-fault period; new faults invisible
   - Fix: `--start-from-beginning` after resolving underlying bugs; regime fixes help

---

## 🐛 Debugging Guide

### Quick Diagnosis Checklist

When a turbine run looks wrong, check in this order:

1. **Did it run at all?**
   ```sql
   SELECT TOP 5 CONVERT(varchar(19), StartedAt, 120), ScoreRowCount, EpisodeCount, HealthStatus, LEFT(ISNULL(ErrorMessage,'OK'),80)
   FROM ACM_Runs WHERE EquipID = 5010 ORDER BY StartedAt DESC
   ```

2. **Is model stuck at LEARNING?**
   ```sql
   SELECT Version, MaturityState, ConsecutiveRuns, CreatedAt FROM ACM_ActiveModels WHERE EquipID = 5010 ORDER BY CreatedAt DESC
   ```

3. **Are all scoring points "unknown"?**
   Look for `"Identified N/N novel points"` in logs — means P99 distance threshold fix needed.

4. **Is k_max reverting every batch?**
   Look for `"k_max: 6->8"` in every batch log — means ACM_Config upsert fix needed.

5. **Is ContributionTimeline empty?**
   ```sql
   SELECT COUNT(*) FROM ACM_ContributionTimeline WHERE EquipID = 5010
   ```
   Should be non-zero after v11.15.7. If still zero, check fusion_weights are non-empty.

6. **Is health flat/plateau?**
   Run `--start-from-beginning` after applying all v11.15.x fixes. The plateau is from a model trained on degraded data.

### Performance Hotspots

| Operation | Typical Time | Status |
|-----------|-------------|--------|
| `output_manager._bulk_insert_sql` listcomp | ~37s/batch | **FIXED v11.15.6**: Polars `.rows()` |
| `fuse.detect_episodes PCA attribution` | ~180s coldstart | **FIXED v11.15.2**: precompute numpy matrix |
| `rolling_spectral_energy` per-row FFT | ~20s | **FIXED v11.15.2**: stride-trick batch FFT |
| `impute_features` pandas copy+replace | ~40s | **FIXED v11.15.2**: numpy-native path |
| `acm._build_features` apply(pd.to_numeric) | ~24s | **FIXED v11.15.2**: `select_dtypes("object")` guard |

**Target total batch time: < 300s.** If exceeding 600s, profile for Python loops over DataFrames.

### Common Issues

#### "ContributionTimeline skipped: build returned empty/None DataFrame" (FIXED v11.15.7)

**Root cause:** `build_contribution_timeline()` checks `'Timestamp' not in frame.columns` and returns None. The pipeline `frame` uses `DatetimeIndex` named `"EntryDateTime"` — Timestamp is the index, not a column.

**Fix (v11.15.7):** `write_contribution_timeline_from_frame_service()` now resets index before calling `build_contribution_timeline()`.

**If still appearing:** Check that `fusion_weights` dict is non-empty (logged as separate warning if empty).

#### "Failed to upsert auto-tune param ... Cannot insert NULL into ValueType"

**Root cause:** `ACM_Config.ValueType` is NOT NULL with no default. MERGE INSERT must supply it.

**Fix (v11.15.8):** `_infer_value_type()` helper infers `'int'`/`'float'`/`'bool'`/`'string'` from the value string before MERGE.

**When writing any SQL MERGE into ACM_Config always include ValueType:**
```sql
MERGE [dbo].[ACM_Config] AS target
USING (VALUES (?, ?, ?, ?)) AS src (EquipID, ParamPath, ParamValue, ValueType)
ON target.EquipID = src.EquipID AND target.ParamPath = src.ParamPath
WHEN MATCHED THEN
    UPDATE SET ParamValue = src.ParamValue, ValueType = src.ValueType, UpdatedAt = GETUTCDATE(), UpdatedBy = 'AUTO_TUNE'
WHEN NOT MATCHED THEN
    INSERT (EquipID, ParamPath, ParamValue, ValueType, UpdatedBy)
    VALUES (src.EquipID, src.ParamPath, src.ParamValue, src.ValueType, 'AUTO_TUNE');
```

#### "Identified N/N novel points" every batch

Regime distance threshold too tight. Apply:
```
regimes.unknown.distance_percentile = 99   (was 95)
regimes.unknown.distance_threshold_floor_ratio = 1.5
```
Then run `python scripts/sql/populate_acm_config.py` and `--start-from-beginning`.

#### "k_max: 6->8" logged every batch, never sticks

Auto-tune writes to ACM_ConfigHistory (audit log) only. The `_upsert_acm_config()` MERGE into ACM_Config was added in v11.15.6. Verify `config_history_writer.py` has `_AUTO_TUNE_PATH_MAP` and calls `_upsert_acm_config()`.

#### Health plateau (flat line, new faults invisible)

Classic symptom of model trained on degraded data where degraded = new normal. Fix:
1. Apply all v11.15.x bug fixes
2. Run `--start-from-beginning` to retrain on clean data from the start
3. Monitor `consecutive_runs` accumulating toward 5 for CONVERGED promotion

---

## 🌬️ Wind Farm A Equipment Analysis

### Known Fault History (data/event_info.csv)

| Turbine | EquipID | Fault Type | Period | ACM Detection |
|---------|---------|------------|--------|---------------|
| T10 | 5010 | Generator bearing failure | 2022-12-26 → 2023-01-26 | ✅ Detected — health crashed to min=3.2 in Feb, HIGH episode |
| T10 | 5010 | Hydraulic group | 2023-09-09 | ❌ Missed — health plateau at 51% masks all post-Feb faults |
| T10 | 5010 | Gearbox failure | 2023-10-11 | ❌ Missed — same plateau |
| T11 | 5011 | Transformer failure | 2023-07-28 → 2023-08-11 | ❌ T11 has ZERO ACM runs — never processed |
| T13 | 5013 | Hydraulic group | 2023-04-19 | ✅ Detected — health min=15.4, MaxFusedZ=4.48, 40 episodes |
| T13 | 5013 | Hydraulic group | 2023-09-05 | ❌ No data — T13 runs cut off May 2023 |
| T21 | 5021 | Hydraulic group | 2023-08-12 | ❌ T21 has ZERO ACM runs — never processed |
| T21 | 5021 | Gearbox failure | 2023-10-10 | ❌ T21 has ZERO ACM runs — never processed |
| T21 | 5021 | Gearbox bearings | 2023-10-06 | ❌ T21 has ZERO ACM runs — never processed |
| T0 | 5000 | Generator bearing / Hydraulic | 2023-06/08/10 | ❌ Missed — MaxFusedZ only 1.2–2.0 during fault windows |

**Summary:** T11 and T21 need to be run through ACM. T10 plateau must be resolved with `--start-from-beginning` after v11.15.x fixes. T13 partially good but needs more runs. T0 has weak detection signal.

### Equipment Picker SQL (correct)

```sql
SELECT EquipID AS __value, EquipCode AS __text
FROM Equipment
WHERE Status = 'Active' AND EquipCode LIKE 'WFA_%'
ORDER BY EquipCode
```

---

## ⚙️ Configuration System

### Config Loading

Config is loaded fresh from `ACM_Config` SQL table at each batch run start. Changes take effect next batch.

```python
from utils.config_dict import ConfigDict
cfg = ConfigDict.from_sql(sql_client, equip_id=5010)
# Access: cfg["regimes"]["unknown"]["distance_percentile"]
```

### After any edit to `configs/config_table.csv`:

```powershell
python scripts/sql/populate_acm_config.py
```

This is the ONLY way to push CSV changes to SQL.

### Key Configuration Parameters

**Regime novelty (v11.15.6 new params):**
- `regimes.unknown.distance_percentile` = `99` (was 95 — P99 prevents 100% novel on short coldstart)
- `regimes.unknown.distance_threshold_floor_ratio` = `1.5` (threshold ≥ 1.5× median training distance)

**Auto-tune paths (mapped in config_history_writer._AUTO_TUNE_PATH_MAP):**
- `k_max` → `regimes.auto_k.k_max`
- `k_sigma` → `episodes.cpd.k_sigma`
- `clip_z` → `thresholds.self_tune.clip_z`

**Lifecycle:**
- `lifecycle.promotion.min_consecutive_runs` = `3`
- `lifecycle.promotion.min_silhouette_score` = `0.15`
- `lifecycle.promotion.min_stability_ratio` = `0.6`

**Thresholds:**
- `thresholds.alert_z` = `3.0` (anomaly rate check uses this, NOT hardcoded 1.0)
- `runtime.phases.forecast` = `False` (forecasting disabled — prevents QA FAIL)

---

## 📦 Module Dependency Graph (verified)

```
scripts/sql_batch_runner.py
    └── subprocess: core/acm.py

core/acm.py (MAIN ORCHESTRATOR — not acm_main.py)
    ├── core/fast_features.py (run_feature_preparation_stage, ensure_local_index)
    ├── core/detector_orchestrator.py (score_all_detectors, calibrate_all_detectors)
    │   └── core/outliers.py (IsolationForestDetector, GMMDetector) — ACTIVELY USED
    ├── core/regimes.py (run_scoring_regime_stage, run_regime_labeling_stage)
    ├── core/model_lifecycle.py (resolve_maturity_for_regime_stage, BOOLEAN_ONLY_METRICS) — ACTIVELY USED
    ├── core/model_persistence.py
    │   └── core/model_lifecycle.py (update_and_persist_model_lifecycle_safe) — ACTIVELY USED
    ├── core/fuse.py (calibrate, auto_tune, compute_fusion, detect_episodes)
    ├── core/drift.py (run_drift_pipeline, load_previous_drift_mode)
    ├── core/config_history_writer.py (log_auto_tune_changes → _upsert_acm_config)
    ├── core/output_manager.py (OutputManager)
    │   └── core/output_sql_core.py (SqlWriteEngine._to_python_records — Polars .rows())
    └── core/output_manager_services.py (run_persistence_stage)
        └── core/sensor_attribution.py (build_contribution_timeline)
            NOTE: requires Timestamp as COLUMN not index — reset_index() applied in service

core/sensor_attribution.py
    build_contribution_timeline(frame, fusion_weights):
        RETURNS None if 'Timestamp' not in frame.columns
        frame from score_all_detectors uses DatetimeIndex — service must reset_index() first
```

---

## 📊 Observability Stack

### Docker Compose Stack

```powershell
cd install/observability; docker compose up -d

# Expected containers:
# acm-grafana      (port 3000) - Dashboard UI, admin/admin  [grafana/grafana:12.4.0]
# acm-alloy        (port 4317, 4318) - OTLP collector
# acm-tempo        (port 3200) - Traces
# acm-loki         (port 3100) - Logs
# acm-prometheus   (port 9090) - Metrics
# acm-pyroscope    (port 4040) - Profiling
```

### Grafana Version & Feature Toggles (VERIFIED 2026-02-26)

**Pinned image:** `grafana/grafana:12.4.0` (released 2026-02-25)
- Do NOT use `:latest` — always pin to exact version for reproducibility
- Verify running version: `curl -s http://admin:admin@localhost:3000/api/health`

**All 25 Public Preview feature toggles are enabled** via `GF_FEATURE_TOGGLES_ENABLE` in `docker-compose.yaml`:

| Toggle | What it unlocks |
|--------|----------------|
| `dashboardNewLayouts` | Flexible tabs, auto grid, side toolbar |
| `newGauge` | Circular gauge with sparkline + gradient |
| `newVizSuggestions` | Full-sized previews in visualization picker |
| `vizPresets` | Visualization presets |
| `sqlExpressions` | SQL queries against datasource results |
| `queryLibrary` | Saved/reusable query library |
| `savedQueriesRBAC` | RBAC permissions for query library |
| `dashboardTemplates` | Start dashboards from a template |
| `logsPanelControls` | Control component for logs panel in Explore |
| `canvasPanelPanZoom` | Pan and zoom in canvas panels |
| `alertingSaveStateCompressed` | Compressed protobuf alert state storage |
| `alertRuleRestore` | Alert rule restore |
| `grpcServer` | gRPC server |
| `renderAuthJWT` | JWT-based rendering auth |
| `externalServiceAccounts` | Auto service accounts for plugins |
| `pdfTables` | Table data in PDF reports |
| `azureMonitorLogsBuilderEditor` | Azure Monitor logs builder mode |
| `interactiveLearning` | Interactive learning app |
| `panelTitleSearch` | Dashboard search by panel title |
| `refactorVariablesTimeRange` | Fewer API calls for chained query variables |
| `faroDatasourceSelector` | Datasource selector in Frontend Observability |
| `enableDatagridEditing` | Edit functionality in datagrid panels |
| `preventPanelChromeOverflow` | Restrict panel contents with overflow:hidden |
| `newPanelPadding` | Increased panel padding globally |
| `transformationsEmptyPlaceholder` | Quick-start cards in empty transformations |

Source: https://grafana.com/docs/grafana/v12.4/setup-grafana/configure-grafana/feature-toggles/

**To add/remove toggles:** Edit `GF_FEATURE_TOGGLES_ENABLE` in `install/observability/docker-compose.yaml`, then `docker compose up -d grafana`.

### Console API (core/observability.py)

```python
from core.observability import Console

Console.info("Message", component="COMP", **kwargs)    # General info → Loki
Console.warn("Message", component="COMP", **kwargs)    # Warnings → Loki
Console.error("Message", component="COMP", **kwargs)   # Errors → Loki
Console.ok("Message", component="COMP", **kwargs)      # Success → Loki
Console.status("Message")                               # Console-only (NO Loki)
Console.header("Title", char="=")                       # Section headers (NO Loki)
```

**NEVER use:** `print()`, `utils/logger.py` (deleted v10.3.0), `utils/acm_logger.py` (deleted v10.3.0)

---

## 📈 Grafana Dashboard Best Practices

### Active Dashboards

| File | UID | Purpose |
|------|-----|---------|
| `grafana_dashboards/acm_master_complete.json` | `acm-master-complete-v2` | Per-equipment master (47 panels) |
| `grafana_dashboards/acm_fleet_overview.json` | `acm-fleet-overview-v1` | All equipment fleet view |
| `grafana_dashboards/acm_observability.json` | `acm-observability-v4` | Runs/logs/traces |

Datasource UIDs: `mssql-ds`, `prometheus-ds`, `loki-ds`, `tempo-ds`, `pyroscope-ds`

### Time Series Query Pattern (MANDATORY)

```sql
-- ✅ CORRECT: Raw DATETIME, ASC order, time filter
SELECT Timestamp AS time, HealthIndex AS 'Health %'
FROM ACM_HealthTimeline
WHERE EquipID = $equipment
  AND Timestamp BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY Timestamp ASC

-- ❌ WRONG patterns:
SELECT FORMAT(Timestamp, 'yyyy-MM-dd') AS time  -- Breaks time axis
SELECT * ORDER BY Timestamp DESC                  -- Breaks rendering
SELECT * -- No time filter!                       -- Performance disaster
```

### Equipment Variable Query (CORRECT)

```sql
-- Use Equipment (not Equipments), Status not Active column
SELECT EquipID AS __value, EquipCode AS __text
FROM Equipment
WHERE Status = 'Active'
  AND EquipID IN (SELECT DISTINCT EquipID FROM ACM_HealthTimeline)
ORDER BY EquipCode
```

### Schema Facts Critical for Dashboards

- `ACM_HealthTimeline` time col = `Timestamp`; zone col = `HealthZone` (NOT Zone)
- `ACM_Scores_Wide` time col = `Timestamp` (verified live — NOT EntryDateTime)
- `Equipment.Status` = 'Active'/'Inactive' (NOT a bit column called Active)

### Panel Configuration

```json
{ "custom": { "spanNulls": 3600000, "lineInterpolation": "smooth" } }
```

### Threshold Color Standards

```json
{
  "thresholds": { "mode": "absolute", "steps": [
    { "color": "#C4162A", "value": null },
    { "color": "#FF9830", "value": 50 },
    { "color": "#FADE2A", "value": 70 },
    { "color": "#73BF69", "value": 85 }
  ]}
}
```

---

## ⚡ Performance Optimization

### NEVER Use Python Loops for DataFrame Operations

```python
# ❌ CATASTROPHIC - N × M Python calls
for col in sensor_cols:
    for i, (ts, val) in enumerate(zip(timestamps, values)):
        rows.append({'Timestamp': ts, 'SensorName': col, 'Value': val})

# ✅ Vectorized - use pd.melt()
long_df = df[['Timestamp'] + sensor_cols].melt(
    id_vars=['Timestamp'], value_vars=sensor_cols,
    var_name='SensorName', value_name='NormalizedValue'
).dropna(subset=['NormalizedValue'])
```

### SQL Write Performance (output_sql_core.py)

The correct vectorized path (v11.15.6+):
```python
# SqlWriteEngine._to_python_records() uses Polars .rows()
pl_df = pl.from_pandas(df_clean[columns])
# Strip tz-aware datetime columns
cast_exprs = [pl.col(c).dt.replace_time_zone(None) for c,d in zip(pl_df.columns, pl_df.dtypes)
              if isinstance(d, pl.Datetime) and d.time_zone is not None]
if cast_exprs:
    pl_df = pl_df.with_columns(cast_exprs)
return pl_df.rows()  # Python-native tuples, no per-cell callback
```

### Acceptable Batch Timings

| Phase | Target | Critical |
|-------|--------|----------|
| load_data | < 30s | > 120s |
| features.build | < 30s | > 120s |
| output_manager SQL writes | < 5s | > 30s |
| total_run | < 300s | > 1200s |

---

## ⚠️ Common Mistakes to AVOID

| Category | ❌ Wrong | ✅ Correct |
|----------|---------|-----------|
| Pipeline mode | `--mode offline` | `--force-retrain` (v11.8.0+) |
| Entry point | `core/acm_main.py` | `core/acm.py` |
| SQL table | `Equipments` | `Equipment` |
| SQL column | `Equipment.Active` | `Equipment.Status = 'Active'` |
| SQL column | `ACM_Config` INSERT without ValueType | Always include ValueType (NOT NULL) |
| SQL columns | `ACM_HealthTimeline.Zone` | `ACM_HealthTimeline.HealthZone` |
| SQL syntax | `LIMIT 10` | `TOP 10` |
| SQL syntax | `DATE_TRUNC(...)` | `DATEADD(HOUR, DATEDIFF(HOUR, 0, ...), 0)` |
| SQL alias | `AS End`, `AS RowCount` | `AS EndTimeStr`, `AS TotalRows` |
| Time series | `FORMAT(time, ...)` | Return raw `DATETIME` |
| Time series | `ORDER BY time DESC` | `ORDER BY time ASC` |
| RUL queries | `ORDER BY RUL_Hours ASC` | `ORDER BY CreatedAt DESC` |
| Grafana | `"spanNulls": true` | `"spanNulls": 3600000` |
| Logging | `print()` | `Console.status()` |
| frame Timestamp | Pass frame directly to `build_contribution_timeline()` | `reset_index()` + rename first |

---

## 🔄 Version History

| Version | Key Changes |
|---------|-------------|
| v11.15.7 | ContributionTimeline fix: reset_index before build_contribution_timeline (Timestamp was index not column) |
| v11.15.6 | Regime P99 threshold + floor clamp; OutputManager Polars .rows() perf; auto-tune ACM_Config upsert |
| v11.15.5 | Drift hysteresis state continuity; CUSUM reset on fit; drift_mode naming consistency; prev_alert_mode from SQL |
| v11.15.4 | Refit loop fix (z=3.0 threshold); regime_quality_ok stale manifest; model_state fallback; forecast QA; hash stability |
| v11.15.3 | fast_features Polars hard dependency; stride-trick FFT; rolling_corr keyword-only |
| v11.15.2 | Performance: PCA attribution, spectral FFT, impute_features numpy path, _build_features guard |
| v11.15.1 | Feature mismatch fix: impute_features protected_columns from manifest |
| v11.9.0 | Calibrated z-scores no longer re-normalized in fusion |
| v11.8.0 | ONLINE/OFFLINE modes removed; adaptive pipeline; --force-retrain |
| v11.4.0 | Regime clustering uses raw sensor values only (no z-scores) |
| v11.0.0 | MaturityState lifecycle, DataContract validation, seasonality detection, UNKNOWN regime |
| v10.3.0 | Unified observability (Console class), Docker Compose stack |
| v10.0.0 | Continuous forecasting, hazard-based RUL, Monte Carlo simulations |

---

## ⚠️ Analytical Correctness Rules (non-negotiable)

### Statistical Rules

- **Robust stats**: median/MAD not mean/std. `std_robust = mad × 1.4826`
- **Harmonic mean** for confidence (not geometric or arithmetic)
- **Detector correlation discount**: pairs with |r| > 0.5 get weight reduction in fusion
- **Health jump threshold**: > 15% positive jump = maintenance reset; use only post-jump data for trend
- **Anomaly threshold**: always config-driven (`thresholds.alert_z` default 3.0), NEVER hardcoded

### Regime Clustering Rules

- **MUST use raw sensor values only** — never z-scores or health-state features in regime basis
- Regimes = HOW equipment operates (wind speed, load, RPM). Detectors = IF healthy. Orthogonal.
- Z-scores in regime basis = circular masking: regime transitions look like anomalies

### Data Flow Rules

1. **Timestamp is the DataFrame index** throughout the pipeline (DatetimeIndex named "EntryDateTime")
2. Write services that need Timestamp as a column must call `reset_index()` first
3. When transforming data, verify which variable is the TRUE source used by downstream functions
4. Model state must flow via constructor injection to ALL consumers

### Code Review Checklist for Analytical Code

- [ ] **Data Flow**: Is transformed data flowing to the correct consumers?
- [ ] **Timestamp**: Does the function need Timestamp as a column? If so, reset_index() first.
- [ ] **ACM_Config MERGE**: Does it supply ValueType?
- [ ] **Correlation**: Are fused/combined signals checked for correlation before fusion?
- [ ] **Robustness**: Using median/MAD instead of mean/std?
- [ ] **Initialization**: All variables initialized before conditional logic?
- [ ] **Vectorization**: No Python loops over DataFrame rows?
- [ ] **Level Shifts**: Are health jumps/maintenance resets handled before trend fitting?

---

## 📁 Project Structure

```
ACM/
├── core/
│   ├── acm.py                    # MAIN ORCHESTRATOR (not acm_main.py)
│   ├── detector_orchestrator.py  # score_all_detectors, uses outliers.py
│   ├── outliers.py               # IsolationForestDetector, GMMDetector — USED
│   ├── model_lifecycle.py        # MaturityState, BOOLEAN_ONLY_METRICS — USED
│   ├── model_persistence.py      # Save/restore detectors + lifecycle
│   ├── regimes.py                # run_scoring_regime_stage, regime clustering
│   ├── fuse.py                   # Fusion, CUSUM, auto-tune
│   ├── drift.py                  # Drift detection (all bugs fixed v11.15.5)
│   ├── config_history_writer.py  # Auto-tune history + ACM_Config upsert
│   ├── output_manager.py         # OutputManager class
│   ├── output_manager_services.py # run_persistence_stage, write services
│   ├── output_sql_core.py        # SqlWriteEngine, Polars .rows() path
│   ├── sensor_attribution.py     # build_contribution_timeline (needs Timestamp col)
│   ├── fast_features.py          # Polars feature engineering, ensure_local_index
│   ├── observability.py          # Console class
│   └── sql_client.py             # SQL Server connectivity
├── configs/
│   ├── config_table.csv          # ~355+ configuration parameters
│   └── sql_connection.ini        # SQL credentials (gitignored)
├── scripts/
│   ├── sql_batch_runner.py       # Primary batch processing
│   └── sql/
│       ├── populate_acm_config.py  # Sync CSV → ACM_Config SQL
│       └── export_comprehensive_schema.py
├── data/
│   └── event_info.csv            # Known fault events for Wind Farm A turbines
├── grafana_dashboards/
│   ├── acm_master_complete.json  # Master per-equipment dashboard
│   ├── acm_fleet_overview.json   # Fleet overview
│   ├── acm_observability.json    # Observability
│   └── archive/                  # Old dashboards (NOT provisioned)
├── install/observability/        # Docker Compose stack
├── utils/
│   └── version.py                # Currently v11.15.7
└── docs/
    ├── ACM_SYSTEM_OVERVIEW.md
    ├── ACM_ARCHITECTURE_DECISIONS.md  # Bug catalogue
    └── sql/COMPREHENSIVE_SCHEMA_REFERENCE.md
```

---

## 📚 Key Documentation

| Document | Purpose |
|----------|---------|
| `README.md` | Product overview, setup, running ACM |
| `docs/ACM_SYSTEM_OVERVIEW.md` | Architecture, module map, data flow |
| `docs/ACM_ARCHITECTURE_DECISIONS.md` | All-time bug catalogue with root causes |
| `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md` | Authoritative SQL table definitions |
| `data/event_info.csv` | Known fault events for Wind Farm A turbines (asset=turbine number) |
| `plans/CONTINUOUS_LEARNING_AUDIT_2026_02_24.md` | 14-batch audit for WFA_TURBINE_10 |

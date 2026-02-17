---
name: acm-master
description: "Complete ACM (Automated Condition Monitoring) expertise system for predictive maintenance and equipment health monitoring. PROACTIVELY activate for: (1) ANY ACM pipeline task (batch runs, coldstart, forecasting), (2) SQL Server data management (historian tables, ACM output tables), (3) Observability stack (Loki logs, Tempo traces, Prometheus metrics, Pyroscope profiling), (4) Grafana dashboard development, (5) Detector tuning and fusion configuration, (6) Model lifecycle management, (7) Debugging pipeline issues. Provides: T-SQL patterns for ACM tables, batch runner usage, detector behavior, RUL forecasting, episode diagnostics, and production-ready pipeline patterns. Ensures professional-grade industrial monitoring following ACM v11.0.0 architecture."
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
- Ingests sensor data from industrial equipment (FD_FAN, GAS_TURBINE, etc.) via SQL Server
- Runs multi-detector anomaly detection algorithms
- Calculates health scores and detects operating regimes
- Forecasts Remaining Useful Life (RUL) with Monte Carlo simulations
- Visualizes results through Grafana dashboards for operations teams

### Current Version: v11.0.0

**Key V11 Features:**
- ONLINE/OFFLINE pipeline mode separation (`--mode auto/online/offline`)
- MaturityState lifecycle (COLDSTART → LEARNING → CONVERGED → DEPRECATED)
- Unified confidence model with ReliabilityStatus for all outputs
- RUL reliability gating (NOT_RELIABLE when model not CONVERGED)
- UNKNOWN regime (label=-1) for low-confidence assignments
- DataContract validation at pipeline entry
- Seasonality detection and adjustment

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

---

## 🔧 Pipeline Execution

### Primary Entry Points

```powershell
# Standard batch processing (RECOMMENDED for testing)
python scripts/sql_batch_runner.py --equip FD_FAN --tick-minutes 1440 --max-batches 2 --start-from-beginning

# Multiple equipment
python scripts/sql_batch_runner.py --equip FD_FAN GAS_TURBINE --tick-minutes 1440 --max-workers 2

# Resume from last run
python scripts/sql_batch_runner.py --equip FD_FAN --tick-minutes 1440 --resume

# Single equipment run (internal, rarely used directly)
python -m core.acm_main --equip FD_FAN --start-time "2024-01-01T00:00:00" --end-time "2024-01-02T00:00:00"
```

### Batch Runner Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--equip` | Equipment name(s) | `FD_FAN GAS_TURBINE` |
| `--tick-minutes` | Window size in minutes | `1440` (1 day) |
| `--max-batches` | Limit number of batches | `2` |
| `--start-from-beginning` | Reset and start from earliest data | Flag |
| `--resume` | Continue from last completed batch | Flag |
| `--dry-run` | Show what would run without executing | Flag |
| `--max-workers` | Parallel equipment processing | `2` |
| `--mode` | Pipeline mode | `auto`, `online`, `offline` |

### Understanding Pipeline Phases

```
COLDSTART → DATA_LOADING → FEATURES → DETECTORS → FUSION → FORECASTING → PERSIST
```

Each phase logs with component tags:
- `[COLDSTART]` - Initial model training
- `[DATA]` - Data loading and validation
- `[FEAT]` - Feature engineering
- `[MODEL]` - Detector fitting/scoring
- `[REGIME]` - Operating regime detection
- `[FUSE]` - Multi-detector fusion
- `[FORECAST]` - RUL and health predictions
- `[OUTPUT]` - SQL persistence

---

## � Script Relationships & Entry Points

### Entry Points Hierarchy

```
1. scripts/sql_batch_runner.py (PRODUCTION - Primary entry point)
   └── core/acm_main.py::run_acm() (called via subprocess)
       └── All pipeline phases (see Pipeline Phase Sequence below)

2. python -m core.acm_main --equip EQUIPMENT (TESTING - Single run)
   └── core/acm_main.py::run_acm() (direct call)
       └── All pipeline phases

3. core/acm.py (ALTERNATIVE - Mode-aware router)
   ├── Parses --mode (auto/online/offline)
   ├── Detects mode based on cached models if auto
   └── Calls core/acm_main.py::run_acm() with mode
```

### Script Relationships

```
sql_batch_runner.py
├── Purpose: Continuous batch processing, coldstart management, multi-equipment
├── Calls: core/acm_main.py via subprocess (python -m core.acm_main)
├── Manages: Coldstart state, batch windows, resume from last run
├── SQL Tables: Reads ACM_ColdstartState, writes ACM_Runs
└── Arguments:
    --equip FD_FAN GAS_TURBINE  # Multiple equipment
    --tick-minutes 1440          # Batch window size
    --max-workers 2              # Parallel equipment processing
    --start-from-beginning       # Full reset (coldstart)
    --resume                     # Continue from last run
    --max-batches 1              # Limit batches (testing)

core/acm_main.py
├── Purpose: Single pipeline run (train/score/forecast)
├── Imports: All core modules (see Module Dependency Graph)
├── Manages: Model training, scoring, persistence
└── Arguments:
    --equip FD_FAN               # Single equipment
    --start-time "2024-01-01T00:00:00"
    --end-time "2024-01-31T23:59:59"
    --mode offline|online|auto   # Pipeline mode

scripts/sql/verify_acm_connection.py
├── Purpose: Test SQL Server connectivity
├── Calls: core/sql_client.SQLClient
└── Output: Connection test result

scripts/sql/export_comprehensive_schema.py
├── Purpose: Export SQL schema to markdown
├── Calls: SQL INFORMATION_SCHEMA
└── Output: docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md

scripts/sql/populate_acm_config.py
├── Purpose: Sync config_table.csv to SQL ACM_Config
├── Reads: configs/config_table.csv
└── Writes: SQL ACM_Config table
```

---

## 🔄 Pipeline Phase Sequence (acm_main.py)

The main pipeline executes in this order. Each phase corresponds to a timed section in the output:

```
PHASE 1: INITIALIZATION (startup)
├── Parse CLI arguments (--equip, --start-time, --end-time, --mode)
├── Load config from SQL (ConfigDict)
├── Determine PipelineMode (ONLINE/OFFLINE/AUTO)
├── Initialize OutputManager with SQL client
└── Create RunID for this execution

PHASE 2: DATA CONTRACT VALIDATION (data.contract)
├── DataContract.validate(raw_data)
├── Check sensor coverage (min 70% required)
├── Write ACM_DataContractValidation
└── Fail fast if validation fails

PHASE 3: DATA LOADING (load_data)
├── Load historian data from SQL (stored procedure)
├── Apply coldstart split (60% train / 40% score)
├── Validate timestamp column and cadence
└── Output: train DataFrame, score DataFrame

PHASE 4: BASELINE SEEDING (baseline.seed)
├── Load baseline from ACM_BaselineBuffer
├── Check for overlap with score data
└── Apply baseline for normalization

PHASE 5: SEASONALITY DETECTION (seasonality.detect)
├── SeasonalityHandler.detect_patterns()
├── Detect DAILY/WEEKLY cycles using FFT
├── Apply seasonal adjustment if enabled (v11)
└── Write ACM_SeasonalPatterns

PHASE 6: DATA QUALITY GUARDRAILS (data.guardrails)
├── Check train/score overlap
├── Validate variance and coverage
├── Write ACM_DataQuality
└── Output quality metrics

PHASE 7: FEATURE ENGINEERING (features.build + features.impute)
├── fast_features.compute_all_features()
├── Build rolling stats, lag features, z-scores
├── Impute missing values from train medians
├── Compute feature hash for caching
└── Output: Feature matrices (train_features, score_features)

PHASE 8: MODEL LOADING/TRAINING (train.detector_fit)
├── Check for cached models in ModelRegistry
├── If OFFLINE or models missing:
│   ├── Fit AR1 detector (ar1_detector.py)
│   ├── Fit PCA detector (pca via sklearn)
│   ├── Fit IForest detector (sklearn.ensemble)
│   ├── Fit GMM detector (sklearn.mixture)
│   └── Fit OMR detector (omr.py)
├── If ONLINE: Load all detectors from cache
└── Output: Trained detector objects

PHASE 9: TRANSFER LEARNING CHECK (v11)
├── AssetSimilarity.load_profiles_from_sql()
├── Build profile for current equipment
├── find_similar() to match equipment
└── Log transfer learning opportunity

PHASE 10: DETECTOR SCORING (score.detector_score)
├── Score all detectors on score data
├── Compute z-scores per detector
├── Output: scores_wide DataFrame with detector columns
└── Columns: ar1_z, pca_spe_z, pca_t2_z, iforest_z, gmm_z, omr_z

PHASE 11: REGIME LABELING (regimes.label)
├── regimes.label() with regime context
├── Auto-k selection (silhouette/BIC scoring)
├── Clustering on raw sensor values (GMM or KMeans)
├── UNKNOWN regime (-1) for low-confidence assignments
├── Write ACM_RegimeDefinitions
└── Output: Regime labels per row

PHASE 12: MODEL PERSISTENCE (models.persistence.save)
├── Save all models to SQL ModelRegistry
├── Increment model version
└── Write metadata to ACM_ModelHistory

PHASE 13: MODEL LIFECYCLE (v11)
├── load_model_state_from_sql()
├── Update model state with run metrics
├── Check promotion criteria (LEARNING -> CONVERGED)
├── Write ACM_ActiveModels
└── Output: MaturityState (COLDSTART/LEARNING/CONVERGED/DEPRECATED)

PHASE 14: CALIBRATION (calibrate)
├── Score TRAIN data for calibration baseline
├── Compute adaptive clip_z from P99
├── Self-tune thresholds for target FP rate
└── Write ACM_Thresholds

PHASE 15: DETECTOR FUSION (fusion.auto_tune + fusion)
├── Auto-tune detector weights (episode separability)
├── Compute fused_z (weighted combination)
├── CUSUM parameter tuning (k_sigma, h_sigma)
├── Detect anomaly episodes
└── Output: fused_alert, episode markers

PHASE 16: ADAPTIVE THRESHOLDS (thresholds.adaptive)
├── Calculate per-regime thresholds
├── Global thresholds: alert=3.0, warn=1.5
└── Write to SQL

PHASE 17: TRANSIENT DETECTION (regimes.transient_detection)
├── Detect state transitions (startup, trip, steady)
├── Label transient periods
└── Output: Transient state per row

PHASE 18: DRIFT MONITORING (drift)
├── Compute drift metrics (CUSUM trend)
└── Classify: STABLE, DRIFTING, FAULT

PHASE 19: OUTPUT GENERATION (persist.*)
├── write_scores_wide() -> ACM_Scores_Wide
├── write_anomaly_events() -> ACM_Anomaly_Events
├── write_detector_correlation() -> ACM_DetectorCorrelation
├── write_sensor_correlation() -> ACM_SensorCorrelations
├── write_sensor_normalized_ts() -> ACM_SensorNormalized_TS
├── write_asset_profile() -> ACM_AssetProfiles
└── write_seasonal_patterns() -> ACM_SeasonalPatterns

PHASE 20: ANALYTICS GENERATION (outputs.comprehensive_analytics)
├── _generate_health_timeline() -> ACM_HealthTimeline
├── _generate_regime_timeline() -> ACM_RegimeTimeline
├── _generate_sensor_defects() -> ACM_SensorDefects
├── _generate_sensor_hotspots() -> ACM_SensorHotspots
└── Compute confidence values (v11)

PHASE 21: FORECASTING (outputs.forecasting)
├── ForecastEngine.run_forecast()
│   ├── Load health history from ACM_HealthTimeline
│   ├── Fit degradation model (Holt-Winters)
│   ├── Generate health forecast -> ACM_HealthForecast
│   ├── Generate failure forecast -> ACM_FailureForecast
│   ├── Compute RUL with Monte Carlo -> ACM_RUL
│   ├── Compute confidence and reliability (v11)
│   └── Generate sensor forecasts -> ACM_SensorForecast
└── Write forecast tables

PHASE 22: RUN FINALIZATION (sql.run_stats)
├── Write PCA loadings -> ACM_PCA_Loadings
├── Write run statistics -> ACM_Run_Stats
├── Write run metadata -> ACM_Runs
└── Commit all pending SQL writes
```

---

## 📦 Module Dependency Graph

```
sql_batch_runner.py
    └── subprocess calls: core/acm_main.py

core/acm_main.py (MAIN ORCHESTRATOR)
    ├── utils/config_dict.py (ConfigDict)
    ├── core/sql_client.py (SQLClient)
    ├── core/output_manager.py (OutputManager)
    ├── core/observability.py (Console, Span, Metrics, T)
    ├── core/pipeline_types.py (DataContract, PipelineMode)
    ├── core/fast_features.py (compute_all_features)
    ├── core/ar1_detector.py (AR1Detector)
    ├── core/omr.py (OMRDetector)
    ├── core/regimes.py (label, detect_transient_states)
    ├── core/fuse.py (compute_fusion, detect_episodes)
    ├── core/adaptive_thresholds.py (calculate_thresholds)
    ├── core/drift.py (compute_drift_metrics)
    ├── core/model_persistence.py (save_models, load_models)
    ├── core/model_lifecycle.py (ModelState, promote_model)
    ├── core/confidence.py (compute_*_confidence)
    ├── core/seasonality.py (SeasonalityHandler)
    ├── core/asset_similarity.py (AssetSimilarity)
    ├── core/forecast_engine.py (ForecastEngine)
    └── core/health_tracker.py (HealthTracker)

core/output_manager.py
    ├── core/sql_client.py (SQLClient)
    ├── core/observability.py (Console)
    └── core/confidence.py (compute_*_confidence)

core/forecast_engine.py
    ├── core/sql_client.py (SQLClient)
    ├── core/degradation_model.py (fit_degradation)
    ├── core/rul_estimator.py (estimate_rul)
    ├── core/confidence.py (compute_rul_confidence)
    ├── core/model_lifecycle.py (load_model_state_from_sql)
    └── core/health_tracker.py (HealthTracker)

core/regimes.py
    ├── sklearn.mixture (GaussianMixture)  # v11.0.1: GMM for probabilistic clustering
    ├── sklearn.cluster (MiniBatchKMeans)  # fallback
    ├── sklearn.metrics (silhouette_score)
    └── core/observability.py (Console)
```

---

## �🗄️ SQL/T-SQL Best Practices

### CRITICAL: Use Microsoft SQL Server T-SQL Syntax

**ALWAYS use T-SQL, NEVER generic SQL:**

```sql
-- ✅ CORRECT: T-SQL patterns
SELECT TOP 10 * FROM ACM_Runs ORDER BY StartedAt DESC
SELECT DATEADD(HOUR, DATEDIFF(HOUR, 0, Timestamp), 0) AS HourStart FROM ACM_HealthTimeline
SELECT COALESCE(SUM(TotalEpisodes), 0) AS Total FROM ACM_EpisodeMetrics

-- ❌ WRONG: Generic SQL (NOT supported)
SELECT * FROM ACM_Runs ORDER BY StartedAt DESC LIMIT 10  -- LIMIT not supported!
SELECT DATE_TRUNC('hour', Timestamp) AS HourStart FROM ACM_HealthTimeline  -- DATE_TRUNC not supported!
```

### CRITICAL: Avoid Reserved Words as Aliases

**NEVER use these reserved words as column aliases:**
- `End`, `RowCount`, `Count`, `Date`, `Time`, `Order`, `Group`

**Use safe alternatives:**
- `EndTimeStr`, `TotalRows`, `TotalCount`, `DateValue`, `TimeValue`, `OrderNum`, `GroupName`

```sql
-- ❌ WRONG
SELECT COUNT(*) AS RowCount, EndTime AS End FROM ACM_Runs

-- ✅ CORRECT
SELECT COUNT(*) AS TotalRows, EndTime AS EndTimeStr FROM ACM_Runs
```

### Key ACM Tables

**Core Output Tables:**
- `ACM_Runs` - Run metadata (StartedAt, Outcome, RowsIn, RowsOut)
- `ACM_Scores_Wide` - Detector Z-scores per timestamp
- `ACM_HealthTimeline` - Health scores over time
- `ACM_RegimeTimeline` - Operating regime labels
- `ACM_Anomaly_Events` - Detected episodes with culprits
- `ACM_RUL` - RUL predictions with P10/P50/P90 bounds
- `ACM_HealthForecast` - Health projections
- `ACM_SensorDefects` - Active sensor defects

**V11 New Tables:**
- `ACM_ActiveModels` - Model lifecycle and maturity state
- `ACM_RegimeDefinitions` - Regime cluster definitions
- `ACM_DataContractValidation` - Data quality validation results
- `ACM_SeasonalPatterns` - Detected seasonal patterns
- `ACM_AssetProfiles` - Asset similarity profiles

### Common Queries

```sql
-- Check recent runs
SELECT TOP 20 RunID, EquipID, StartedAt, Outcome, RowsIn, RowsOut, DurationSec
FROM ACM_Runs ORDER BY StartedAt DESC

-- Get latest RUL prediction (CORRECT ordering!)
SELECT TOP 1 Method, RUL_Hours, P10_LowerBound, P50_Median, P90_UpperBound, Confidence
FROM ACM_RUL WHERE EquipID = 1 ORDER BY CreatedAt DESC

-- Check model lifecycle state
SELECT EquipID, Version, MaturityState, TrainingRows, SilhouetteScore
FROM ACM_ActiveModels WHERE EquipID = 1

-- Check run logs for errors
SELECT TOP 50 LoggedAt, Level, Component, Message
FROM ACM_RunLogs WHERE Level IN ('ERROR', 'WARN') ORDER BY LoggedAt DESC

-- Equipment data range
SELECT MIN(EntryDateTime) AS EarliestData, MAX(EntryDateTime) AS LatestData, COUNT(*) AS TotalRows
FROM FD_FAN_Data
```

### RUL Query Ordering (CRITICAL)

```sql
-- ✅ CORRECT: Get MOST RECENT prediction
SELECT TOP 1 * FROM ACM_RUL WHERE EquipID = 1 ORDER BY CreatedAt DESC

-- ❌ WRONG: Gets WORST-CASE from all history (misleading!)
SELECT TOP 1 * FROM ACM_RUL WHERE EquipID = 1 ORDER BY RUL_Hours ASC
```

---

## 📊 Observability Stack

### Docker Compose Stack

```powershell
# Start complete observability stack
cd install/observability; docker compose up -d

# Verify containers
docker ps --format "table {{.Names}}\t{{.Status}}"

# Expected containers:
# acm-grafana      (port 3000) - Dashboard UI, admin/admin
# acm-alloy        (port 4317, 4318) - OTLP collector
# acm-tempo        (port 3200) - Traces
# acm-loki         (port 3100) - Logs
# acm-prometheus   (port 9090) - Metrics
# acm-pyroscope    (port 4040) - Profiling

# Access Grafana
# Open http://localhost:3000 (admin/admin)

# Clean restart
docker compose down -v; docker compose up -d
```

### Console API (core/observability.py)

**ALWAYS use Console class for logging:**

```python
from core.observability import Console

# Use these methods:
Console.info("Message", component="COMP", **kwargs)    # General info → Loki
Console.warn("Message", component="COMP", **kwargs)    # Warnings → Loki
Console.error("Message", component="COMP", **kwargs)   # Errors → Loki
Console.ok("Message", component="COMP", **kwargs)      # Success → Loki
Console.status("Message")                               # Console-only (NO Loki)
Console.header("Title", char="=")                       # Section headers (NO Loki)
Console.section("Title")                                # Lighter separators (NO Loki)
```

**NEVER use:**
- `print()` - Use `Console.status()` instead
- `utils/logger.py` - Deleted in v10.3.0
- `utils/acm_logger.py` - Deleted in v10.3.0

### Trace-to-Logs/Metrics Linking

In Grafana datasources, trace attributes use `acm.` prefix:
- Span attribute: `acm.equipment`
- Query variable: `${__span.tags.equipment}` (after mapping `key: acm.equipment, value: equipment`)

---

## 📈 Grafana Dashboard Best Practices

### Time Series Queries

```sql
-- ✅ CORRECT: Return raw DATETIME, order ASC
SELECT Timestamp AS time, HealthScore AS value
FROM ACM_HealthTimeline
WHERE EquipID = $equipment
  AND Timestamp BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY time ASC

-- ❌ WRONG: Don't use FORMAT() for time series
SELECT FORMAT(Timestamp, 'yyyy-MM-dd') AS time, HealthScore AS value  -- BREAKS time series!
```

### Panel Configuration

```json
{
  "custom": {
    "spanNulls": 3600000,      // Disconnect if gap > 1 hour (NOT true/false!)
    "lineInterpolation": "smooth"
  }
}
```

### Default Time Range

ACM dashboards should default to 5 years: `"from": "now-5y"`

---

## 🔄 Model Lifecycle (V11)

### MaturityState Enum

```
COLDSTART → LEARNING → CONVERGED → DEPRECATED
```

- **COLDSTART**: Initial model training, insufficient data
- **LEARNING**: Model accumulating data, not yet stable
- **CONVERGED**: Model meets promotion criteria, predictions reliable
- **DEPRECATED**: Model replaced by newer version

### Promotion Criteria (Configurable)

```csv
# configs/config_table.csv (v11.0.1 relaxed defaults)
0,lifecycle,promotion.min_training_days,7,int
0,lifecycle,promotion.min_silhouette_score,0.15,float
0,lifecycle,promotion.min_stability_ratio,0.6,float  # v11.0.1: relaxed from 0.8
0,lifecycle,promotion.min_consecutive_runs,3,int
0,lifecycle,promotion.min_training_rows,200,int  # v11.0.1: relaxed from 1000
```

### RUL Reliability Gating

```python
# RUL predictions are NOT_RELIABLE when:
# - Model maturity is COLDSTART or LEARNING
# - Confidence bounds are NULL
# - Health > 80% but RUL < 24h (likely false positive)
```

---

## 🐛 Debugging Guide

### Pipeline Progress Logging

ACM uses `Console.status()` for progress messages that appear in console but NOT in Loki logs. Key progress checkpoints:

1. `[DATA] Kept N numeric columns` - Data columns validated
2. `Checking cadence and resampling...` - Cadence validation starting
3. `[DATA] SQL historian load complete` - Data loading finished
4. `Seeding baseline for EQUIP...` - Baseline seeding starting
5. `Loading baseline from ACM_BaselineBuffer...` - SQL baseline query
6. `[SEASON] Detected N seasonal patterns` - Seasonality detection complete
7. `[SEASON] Applied seasonal adjustment` - Seasonality adjustment applied
8. `[REGIME] Marked N/M points as UNKNOWN` - Regime labeling complete

If pipeline hangs after a progress message, the NEXT step is the bottleneck.

### Performance Hotspots (Common Bottlenecks)

**Top CPU-intensive operations in large batches (250K+ rows):**

| Operation | Typical Time | Cause | Solution |
|-----------|-------------|-------|----------|
| `seasonality.detect` | 30-70 min | `SeasonalityHandler.adjust_baseline` using row-by-row `.apply()` | **FIXED v11.0.1**: Vectorized implementation |
| `regimes.label` | 30-60 min | `smooth_labels` using Python for-loop | **FIXED v11.0.1**: Vectorized scipy.stats.mode |
| `outputs.comprehensive_analytics` | 10-20 min | Large SQL inserts to ACM_HealthTimeline (252K rows) | Batched inserts with commit intervals |
| `persist.write_scores` | 3-5 min | ACM_Scores_Wide inserts | Batched 5000-row inserts |

**If profiling shows these as bottlenecks, check for non-vectorized code patterns like:**
- `series.apply(lambda x: ...)` on large DataFrames
- `for idx, row in enumerate(...)` loops
- `np.unique()` called inside loops

### Common Issues

#### "Stuck after Kept N numeric columns"

**Symptom:** Pipeline logs `[DATA] Kept 9 numeric columns, dropped 0 non-numeric` then hangs.

**Causes:**
1. Slow cadence check on large score DataFrame
2. `_seed_baseline()` loading from `ACM_BaselineBuffer` (slow SQL query with 72h default window)
3. DataContract validation on large data

**Diagnosis:**
```sql
-- Check baseline buffer size
SELECT COUNT(*) AS BufferRows, MIN(Timestamp) AS Earliest, MAX(Timestamp) AS Latest
FROM ACM_BaselineBuffer WHERE EquipID = 1
```

**Solution:** 
- If buffer is huge (>100K rows), truncate old data
- Reduce `runtime.baseline.window_hours` from 72 to 24

#### "Stuck at seasonality.detect for 60+ minutes"

**Symptom:** Pipeline shows `[SEASON] Detected N seasonal patterns` then hangs for long time.

**Cause:** `SeasonalityHandler.adjust_baseline()` was using non-vectorized `Series.apply()` with `_compute_pattern_offset()` lambda.

**Solution (v11.0.1):** Now uses vectorized NumPy operations for 100x+ speedup.

#### "Stuck at regimes.label for 60+ minutes"

**Symptom:** Pipeline shows regime auto-k selection complete but then hangs.

**Cause:** `smooth_labels()` was using Python for-loop with `np.unique()` per row.

**Solution (v11.0.1):** Now uses scipy.stats.mode for vectorized mode computation.

#### "NOOP despite data existing"

**Cause:** Wrong parameter passed to stored procedure (`@EquipID` vs `@EquipmentName`).

**Solution:** Check `output_manager.py::_load_data_from_sql()` uses correct parameter name.

#### "RUL shows imminent failure (<24h) incorrectly"

**Cause:** Query using `ORDER BY RUL_Hours ASC` instead of `ORDER BY CreatedAt DESC`.

**Solution:** Always use most recent prediction: `ORDER BY CreatedAt DESC`.

### Diagnostic Queries

```sql
-- Check recent run outcomes
SELECT TOP 20 EquipID, StartedAt, Outcome, ErrorJSON
FROM ACM_Runs ORDER BY StartedAt DESC

-- Check data availability
SELECT EquipID, MIN(Timestamp), MAX(Timestamp), COUNT(*)
FROM ACM_Scores_Wide GROUP BY EquipID

-- Check model versions
SELECT EquipID, ModelType, Version, TrainedAt, TrainingRows
FROM ModelRegistry WHERE EquipID = 1 ORDER BY TrainedAt DESC
```

---

## 📁 Project Structure

```
ACM/
├── core/                 # Main codebase
│   ├── acm_main.py       # Pipeline orchestrator (entry point)
│   ├── output_manager.py # All CSV/PNG/SQL writes
│   ├── sql_client.py     # SQL Server connectivity
│   ├── observability.py  # Unified logging/traces/metrics
│   ├── model_lifecycle.py # V11 maturity state management
│   ├── forecast_engine.py # RUL and health forecasting
│   ├── fuse.py           # Multi-detector fusion
│   ├── regimes.py        # Operating regime detection
│   └── ...
├── configs/
│   ├── config_table.csv  # 238+ configuration parameters
│   └── sql_connection.ini # SQL credentials (gitignored)
├── scripts/
│   ├── sql_batch_runner.py # Primary batch processing
│   └── sql/              # SQL utilities
├── docs/                 # All documentation
├── grafana_dashboards/   # Grafana JSON dashboards
├── install/observability/ # Docker Compose stack
└── tests/                # pytest test suites
```

---

## ⚠️ Common Mistakes to AVOID

| Category | ❌ Wrong | ✅ Correct |
|----------|---------|-----------|
| SQL columns | `ACM_RUL.LowerBound` | `ACM_RUL.P10_LowerBound` |
| SQL columns | `ACM_RUL.UpperBound` | `ACM_RUL.P90_UpperBound` |
| SQL columns | `ACM_Runs.StartTime` | `ACM_Runs.StartedAt` |
| SQL reserved | `AS End`, `AS RowCount` | `AS EndTimeStr`, `AS TotalRows` |
| SQL syntax | `LIMIT 10` | `TOP 10` |
| SQL syntax | `DATE_TRUNC('hour', ...)` | `DATEADD(HOUR, DATEDIFF(HOUR, 0, ...), 0)` |
| Time series | `FORMAT(time, 'yyyy-MM-dd')` | Return raw `DATETIME` |
| Time series | `ORDER BY time DESC` | `ORDER BY time ASC` |
| RUL queries | `ORDER BY RUL_Hours ASC` | `ORDER BY CreatedAt DESC` |
| Grafana | `"spanNulls": true` | `"spanNulls": 3600000` |
| PowerShell | `command1 && command2` | `command1; command2` |
| PowerShell | `tail -n 20` | `Select-Object -Last 20` |
| Logging | `print()` | `Console.status()` |
| Logging | Legacy loggers | `Console.info/warn/error` |

---

## 🔧 Configuration System

### Config Loading

```python
from utils.config_dict import ConfigDict

# Load from CSV
cfg = ConfigDict.from_csv(Path("configs/config_table.csv"), equip_id=0)

# Access values
pca_components = cfg["models"]["pca"]["n_components"]  # 5
tick_minutes = cfg["runtime"]["tick_minutes"]  # 1440
```

### Key Configuration Parameters

**Data Loading:**
- `data.timestamp_col` = "EntryDateTime"
- `data.sampling_secs` = 1800 (30 min)
- `data.min_train_samples` = 200

**Detectors:**
- `models.pca.n_components` = 5
- `models.iforest.n_estimators` = 100
- `models.gmm.k_max` = 6

**Fusion:**
- `fusion.weights.ar1_z` = 0.20
- `fusion.weights.pca_spe_z` = 0.30
- `fusion.weights.pca_t2_z` = 0.20

**Forecasting:**
- `forecast.horizon_hours` = 168 (7 days)
- `forecast.alpha` = 0.30
- `forecast.failure_threshold` = 70.0

### Sync Config to SQL

After modifying `configs/config_table.csv`:
```powershell
python scripts/sql/populate_acm_config.py
```

---

## 🧪 Testing

### Verify Imports

```powershell
python -c "from core import acm_main; print('OK')"
python -c "from core import model_lifecycle; print('OK')"
python -c "from core import observability; print('OK')"
```

### Verify SQL Connection

```powershell
python scripts/sql/verify_acm_connection.py
```

### Run Batch Test

```powershell
# Minimal test (2 batches)
python scripts/sql_batch_runner.py --equip FD_FAN --tick-minutes 1440 --max-batches 2 --start-from-beginning

# Watch for:
# - [SUCCESS] messages
# - "BATCH RUNNER COMPLETED SUCCESSFULLY"
# - No ERROR or WARN messages related to core functionality
```

### Run Unit Tests

```powershell
pytest tests/test_fast_features.py
pytest tests/test_observability.py
pytest tests/test_progress_tracking.py
```

---

## 📚 Key Documentation

| Document | Purpose |
|----------|---------|
| `README.md` | Product overview, setup, running ACM |
| `docs/ACM_SYSTEM_OVERVIEW.md` | Architecture, module map, data flow |
| `docs/OBSERVABILITY.md` | Observability stack guide |
| `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md` | Authoritative SQL table definitions |
| `.github/copilot-instructions.md` | AI assistant guidelines |
| `install/observability/README.md` | Docker stack installation |

---

## 🔄 Version History

| Version | Key Changes |
|---------|-------------|
| v11.0.2 | GMM replaces KMeans for regime clustering, transfer learning activation, correlation-aware detector fusion |
| v11.0.1 | Relaxed promotion criteria, vectorized seasonality/regime smoothing |
| v11.0.0 | MaturityState lifecycle, DataContract validation, seasonality detection, UNKNOWN regime |
| v10.3.0 | Unified observability (Console class), Docker Compose stack |
| v10.2.0 | Mahalanobis detector removed (redundant with PCA-T²) |
| v10.0.0 | Continuous forecasting, hazard-based RUL, Monte Carlo simulations |

---

## 📝 Output Manager Best Practices (v11.0.3+)

### CRITICAL: Write Method Contract

Every table in `ALLOWED_TABLES` MUST have:
1. **A write method** in `output_manager.py`
2. **A call to that method** in the appropriate pipeline phase in `acm_main.py`
3. **Proper column schema** matching the SQL table definition

**When adding a new table:**
```python
# 1. Add to ALLOWED_TABLES in output_manager.py (line ~95)
ALLOWED_TABLES = {
    ...
    'ACM_NewTable',  # Add here with tier comment
}

# 2. Create write method in output_manager.py
def write_new_table(self, data: pd.DataFrame) -> int:
    """Write to ACM_NewTable.
    
    Schema: ID, RunID, EquipID, <your columns>, CreatedAt
    """
    if not self._check_sql_health() or data is None or data.empty:
        return 0
    try:
        df = data.copy()
        df['RunID'] = self.run_id
        df['EquipID'] = self.equip_id or 0
        return self.write_table('ACM_NewTable', df, delete_existing=True)
    except Exception as e:
        Console.warn(f"write_new_table failed: {e}", component="OUTPUT")
        return 0

# 3. Call from acm_main.py at appropriate pipeline phase
with T.section("persist.new_table"):
    rows = output_manager.write_new_table(my_dataframe)
    Console.info(f"Wrote {rows} rows to ACM_NewTable", component="OUTPUT")
```

### Table Write Location Reference

| Table | Write Method | Pipeline Phase | Line in acm_main.py |
|-------|--------------|----------------|---------------------|
| ACM_Scores_Wide | `write_scores()` | persist | ~5530 |
| ACM_HealthTimeline | `_generate_health_timeline()` | outputs.comprehensive_analytics | ~5650 |
| ACM_RegimeTimeline | `_generate_regime_timeline()` | outputs.comprehensive_analytics | ~5650 |
| ACM_Anomaly_Events | `write_anomaly_events()` | persist.episodes | ~5560 |
| ACM_CalibrationSummary | `write_calibration_summary()` | calibrate | ~4955 |
| ACM_RegimeOccupancy | `write_regime_occupancy()` | regimes.occupancy | ~4530 |
| ACM_RegimeTransitions | `write_regime_transitions()` | regimes.occupancy | ~4545 |
| ACM_RegimePromotionLog | `write_regime_promotion_log()` | models.lifecycle | ~4780 |
| ACM_DriftController | `write_drift_controller()` | drift.controller | ~5365 |
| ACM_ContributionTimeline | `write_contribution_timeline()` | contribution.timeline | ~5510 |
| ACM_RUL | `ForecastEngine.run_forecast()` | outputs.forecasting | ~5800 |

### Column Naming Standards (MANDATORY)

**Timestamp Columns:**
- `Timestamp` - For all time-series fact tables (HealthTimeline, Scores, etc.)
- `StartTime` / `EndTime` - For interval events (Episodes, Anomaly_Events)
- `CreatedAt` - For record insertion timestamp (auto-generated)
- `ModifiedAt` - For record update timestamp (if UPSERT supported)

**NEVER use:**
- `EntryDateTime` (legacy, migrate to `Timestamp`)
- `start_ts` / `end_ts` (snake_case mixed with PascalCase)
- `ValidatedAt`, `LoggedAt`, `DroppedAt` (use `CreatedAt`)
- `CreatedByRunID`, `DetectedByRunID`, `LastUpdatedByRunID` (use `RunID`)

**ID Columns:**
- Always `RunID`, `EquipID` (PascalCase, NEVER snake_case)
- ALL tables use `RunID` (NEVER `CreatedByRunID`, `DetectedByRunID`, etc.)

**Column Casing:**
- **ALL columns MUST be PascalCase** (e.g., `HealthIndex`, `RegimeLabel`)
- **NEVER use snake_case** for SQL columns (e.g., NOT `health_index`)

### Tables Written by Different Modules

Not all ALLOWED_TABLES writes are in output_manager.py:

**acm_main.py direct writes:**
- `ACM_Runs` - Run start/completion metadata
- `ACM_HealthTimeline` - Via `_generate_health_timeline()`
- `ACM_RegimeTimeline` - Via `_generate_regime_timeline()`
- `ACM_SensorDefects` - Via `_generate_sensor_defects()`
- `ACM_SensorHotspots` - Via `_generate_sensor_hotspots()`

**forecast_engine.py writes:**
- `ACM_RUL` - Via `run_forecast()`
- `ACM_HealthForecast` - Via `run_forecast()`
- `ACM_FailureForecast` - Via `run_forecast()`
- `ACM_SensorForecast` - Via `run_forecast()`

**Reference-only tables (written by external processes):**
- `ACM_Config` - Written by `populate_acm_config.py`
- `ACM_HistorianData` - Populated by data import process
- `ACM_BaselineBuffer` - Populated by baseline seeding

---

## 📊 Grafana Dashboard Best Practices (v11.0.3+)

### Dashboard Structure Pattern

All ACM dashboards should follow this structure:
```json
{
  "templating": {
    "list": [
      { "name": "datasource", "type": "datasource", "query": "mssql" },
      { "name": "equipment", "type": "query", "query": "SELECT EquipCode AS __text, EquipID AS __value FROM Equipment WHERE EquipID IN (SELECT DISTINCT EquipID FROM <primary_table>) ORDER BY EquipCode" }
    ]
  },
  "time": { "from": "now-7d", "to": "now" },
  "tags": ["acm", "v11", "<category>"]
}
```

### Time Series Query Pattern (MANDATORY)

```sql
-- ✅ CORRECT: Raw DATETIME, proper ORDER, time filter
SELECT 
    Timestamp AS time,           -- Raw datetime, NOT formatted
    HealthIndex AS 'Health %'    -- Alias for legend
FROM ACM_HealthTimeline
WHERE EquipID = $equipment
  AND Timestamp BETWEEN $__timeFrom() AND $__timeTo()  -- Always filter!
ORDER BY Timestamp ASC           -- MUST be ASC for time series

-- ❌ WRONG patterns that break dashboards:
SELECT FORMAT(Timestamp, 'yyyy-MM-dd') AS time  -- Breaks time axis
SELECT * ORDER BY Timestamp DESC                 -- Breaks rendering
SELECT * -- No time filter!                      -- Performance disaster
```

### Panel Type Selection

| Data Type | Panel Type | Key Settings |
|-----------|------------|--------------|
| Continuous metrics | Time Series | `spanNulls: 3600000` (disconnect on 1h gap) |
| Latest value | Stat | `reduceOptions.calcs: ["lastNotNull"]` |
| Health gauge | Gauge | `max: 100`, thresholds at 50/70/85 |
| Category data | Pie Chart | `pieType: "donut"` |
| Tabular data | Table | Enable pagination |
| Severity/Status | Stat with mappings | Color mappings for GOOD/WATCH/ALERT/CRITICAL |

### Threshold Color Standards

Use consistent colors across all dashboards:
```json
{
  "thresholds": {
    "mode": "absolute",
    "steps": [
      { "color": "#C4162A", "value": null },    // Red (Critical/Bad)
      { "color": "#FF9830", "value": 50 },      // Orange (Warning)
      { "color": "#FADE2A", "value": 70 },      // Yellow (Watch)
      { "color": "#73BF69", "value": 85 }       // Green (Good)
    ]
  }
}
```

For inverted scales (where low is good, like RUL hours):
```json
{
  "thresholds": {
    "steps": [
      { "color": "#C4162A", "value": null },    // Red (< 24h)
      { "color": "#FF9830", "value": 24 },      // Orange (< 72h)
      { "color": "#FADE2A", "value": 72 },      // Yellow (< 168h)
      { "color": "#73BF69", "value": 168 }      // Green (> 1 week)
    ]
  }
}
```

### Value Mappings for Status Fields

```json
{
  "mappings": [
    { "options": { "GOOD": { "color": "green", "index": 0 } }, "type": "value" },
    { "options": { "WATCH": { "color": "yellow", "index": 1 } }, "type": "value" },
    { "options": { "ALERT": { "color": "orange", "index": 2 } }, "type": "value" },
    { "options": { "CRITICAL": { "color": "red", "index": 3 } }, "type": "value" }
  ]
}
```

### Equipment Variable Query Pattern

Always include existence check in variable query:
```sql
-- Shows only equipment that has data in the relevant table
SELECT EquipCode AS __text, EquipID AS __value 
FROM Equipment 
WHERE EquipID IN (SELECT DISTINCT EquipID FROM ACM_HealthTimeline)
ORDER BY EquipCode
```

### Dashboard File Naming

- `acm_v11_<category>.json` - Standard V11 dashboards
- Categories: `executive`, `diagnostics`, `forecasting`, `operations`, `detectors`, `regimes`

---

## ⚡ Performance Optimization (CRITICAL)

### NEVER Use Python Loops for DataFrame Operations

**Problem Example (v11.0.2 bug)**:
```python
# ❌ CATASTROPHIC - 1000+ seconds for 17k rows × 50 sensors
long_rows = []
for col in sensor_cols:
    for i, (ts, val) in enumerate(zip(timestamps, values)):
        long_rows.append({'Timestamp': ts, 'SensorName': col, 'Value': val})
df = pd.DataFrame(long_rows)
```

**Fixed (vectorized)**:
```python
# ✅ 1-2 seconds for same data (100-1000x faster)
long_df = df[['Timestamp'] + sensor_cols].melt(
    id_vars=['Timestamp'],
    value_vars=sensor_cols,
    var_name='SensorName',
    value_name='NormalizedValue'
)
long_df = long_df.dropna(subset=['NormalizedValue'])
```

### Vectorization Patterns

| Operation | Wrong (Python loop) | Right (Vectorized) |
|-----------|---------------------|---------------------|
| Wide→Long | `for col... for row...` | `pd.melt()` |
| Filter NaN | `if pd.notna(val)` | `df.dropna(subset=[col])` |
| Add column | `for row: row['x'] = val` | `df['x'] = val` |
| Upper tri | `for i... for j... if i<=j` | `np.triu()` + `np.where()` |
| Correlation | Loop over `.loc[s1, s2]` | `df.values[rows_idx, cols_idx]` |

### SQL Write Performance

Use pyodbc `fast_executemany`:
```python
cur = self.sql_client.cursor()
cur.fast_executemany = True  # CRITICAL - 10-100x faster
cur.executemany(insert_sql, batch)
```

### Acceptable Batch Timings

| Phase | Target | Concern | Critical |
|-------|--------|---------|----------|
| load_data | < 30s | > 60s | > 120s |
| features.build | < 30s | > 60s | > 120s |
| persist.sensor_normalized_ts | < 30s | > 60s | > 120s |
| persist.sensor_correlation | < 10s | > 30s | > 60s |
| outputs.forecasting | < 120s | > 300s | > 600s |
| **total_run** | < 300s | > 600s | > 1200s |

If any phase exceeds "Critical" threshold, investigate immediately.

### Testing Equipment Selection

**ALWAYS test with the equipment that has the LEAST data:**
```sql
-- Check data volumes before testing
SELECT 'GAS_TURBINE' as Equipment, COUNT(*) as Rows FROM GAS_TURBINE_Data
UNION ALL
SELECT 'FD_FAN', COUNT(*) FROM FD_FAN_Data
ORDER BY Rows ASC
```

Use the smallest dataset for development/testing to catch performance issues early.

---

## V11.0.2 Implementation Details

### GMM Clustering for Operating Regimes

V11.0.2 replaces MiniBatchKMeans with Gaussian Mixture Models (GMM) for regime detection:

**Why GMM?**
- KMeans finds spherical density clusters, not operational modes
- GMM uses probabilistic soft assignments with confidence scores
- BIC (Bayesian Information Criterion) for optimal k selection
- Naturally supports UNKNOWN regime via low-probability assignments

**Implementation** (`core/regimes.py`):
```python
# BIC-based GMM model selection (k=1 to k_max)
from sklearn.mixture import GaussianMixture

def _fit_gmm_scaled(X_scaled, k_max=8, k_min=1, random_state=42):
    best_gmm, best_k, best_bic = None, 1, np.inf
    for k in range(k_min, k_max + 1):
        gmm = GaussianMixture(n_components=k, covariance_type="diag", random_state=random_state)
        gmm.fit(X_scaled)
        bic = gmm.bic(X_scaled)
        if bic < best_bic:
            best_gmm, best_k, best_bic = gmm, k, bic
    return best_gmm, best_k
```

**Fallback**: If GMM fails (e.g., covariance issues), KMeans is used as fallback.

### Transfer Learning Activation

V11.0.2 activates transfer learning for cold-start equipment:

**Implementation** (`core/acm_main.py` lines 4195-4265):
```python
# When detectors_missing and similar equipment found:
transfer_result = similarity_engine.transfer_baseline(
    source_id=transfer_source_id,
    target_id=equip_id,
    source_baseline=None
)
# TransferResult contains:
# - scaling_factors: Dict[str, float] per sensor
# - confidence: float 0-1
# - sensors_transferred: List[str]
```

**Logged to Console** (and Loki via observability):
- Source equipment ID
- Similarity score
- Sensor overlap count
- Transfer confidence

### Correlation-Aware Detector Fusion

V11.1.4 addresses FLAW-4 (detector inter-correlation):

**Implementation** (`core/fuse.py` in `Fuser.fuse()` method):
```python
# GENERALIZED correlation adjustment for ALL detector pairs
# Not just PCA-SPE/T² but any pair with correlation > 0.5
for i, k1 in enumerate(sorted_keys):
    for k2 in sorted_keys[i+1:]:
        corr, _ = pearsonr(arr1[valid_mask], arr2[valid_mask])
        if abs(corr) > 0.5:
            discount_factor = min(0.3, (abs(corr) - 0.5) * 0.5)
            detector_corr_adjustments[k1] *= (1 - discount_factor)
            detector_corr_adjustments[k2] *= (1 - discount_factor)
```

**Effect**: Any correlated detector pair has weights automatically reduced to prevent double-counting of the same information.

---

## ⚠️ Analytical Correctness Rules (v11.1.4+)

### CRITICAL: Lessons Learned from Bug Hunting

These are MANDATORY rules for any statistical/ML code in ACM. Violations of these principles caused subtle but critical bugs in production.

---

### Rule 1: Data Pipeline Flow Must Be Traced End-to-End

**Bug Found (SEASON-EP)**: Seasonal adjustment updated `train_numeric` but feature engineering used `train`:
```python
# BUG: train_numeric was adjusted but train (used in _build_features) was not
train_numeric = train_adj  # ❌ Only updated derivative, not source
score_numeric = score_adj

# FIX: Also update the source dataframes
for col in sensor_cols:
    if col in train.columns:
        train[col] = train_adj[col].values  # ✅ Update actual source
```

**Rule**: When transforming data, ALWAYS verify:
1. Which variable is the TRUE source used by downstream functions?
2. Are you updating a derivative or the actual source?
3. Trace the variable name through ALL downstream calls.

---

### Rule 2: Correlated Variables Must Be Decorrelated Before Fusion

**Bug Found (FUSE-CORR)**: Simple weighted sum of detector scores ignores inter-correlation:
```python
# BUG: Naive fusion double-counts correlated information
fused = w["pca_spe_z"] * spe + w["pca_t2_z"] * t2  # ❌ If corr=0.8, PCA gets 2x influence

# FIX: Discount weights based on pairwise correlation
if corr > 0.5:
    discount = min(0.3, (abs(corr) - 0.5) * 0.5)
    w["pca_spe_z"] *= (1 - discount)  # ✅ Reduce double-counting
    w["pca_t2_z"] *= (1 - discount)
```

**Rule**: When fusing multiple signals:
1. Always check pairwise correlation BEFORE fusion
2. Discount correlated pairs proportionally to their correlation
3. Statistical basis: Effective df = n / (1 + avg_corr)

---

### Rule 3: Trend Models Must Handle Level Shifts

**Bug Found (HEALTH-JUMP)**: Degradation model fit ENTIRE history, including maintenance resets:
```python
# BUG: Fitting on health history with maintenance jumps
model.fit(health_series)  # ❌ Jumps from 40% → 95% corrupt the trend

# FIX: Detect jumps and use only post-jump data
def _detect_and_handle_health_jumps(health_series, jump_threshold=15.0):
    diffs = health_series.diff()
    last_jump = (diffs > jump_threshold).iloc[::-1].idxmax()  # Find last jump
    return health_series[last_jump:]  # ✅ Use only post-maintenance data
```

**Rule**: Before fitting ANY trend model:
1. Check for level shifts (sudden jumps > X%)
2. Maintenance resets are POSITIVE jumps in health
3. Use only post-jump data for trend fitting
4. Log maintenance events for audit trail

---

### Rule 4: Model State Must Flow to ALL Consumers

**Bug Found (STATE-SYNC)**: ForecastEngine didn't receive model_state from acm_main:
```python
# BUG: Model state computed but not passed to forecasting
model_state = load_model_state_from_sql(...)
forecast_engine = ForecastEngine(sql_client=...)  # ❌ model_state missing!

# FIX: Pass model_state via constructor
forecast_engine = ForecastEngine(
    sql_client=...,
    model_state=model_state  # ✅ Now ForecastEngine knows model maturity
)
```

**Rule**: When adding new pipeline state:
1. Trace EVERY consumer that needs it
2. Pass via constructor, NOT global state
3. Verify with grep: `grep -n "TheClass(" *.py` to find all instantiations

---

### Rule 5: Use Robust Statistics (Median/MAD, Not Mean/Std)

**Constant (v11.1.3)**: MAD to σ conversion factor = 1.4826

```python
# BUG: Mean/std corrupted by outliers in baseline
mu = np.nanmean(x)
sd = np.nanstd(x)  # ❌ One outlier can corrupt threshold

# FIX: Median/MAD is 50% breakdown point robust
mu = np.nanmedian(x)
mad = np.nanmedian(np.abs(x - mu))
sd = mad * 1.4826  # ✅ Consistent with σ under normality, robust to outliers
```

**Rule**: In anomaly detection, ALWAYS use:
1. **Median** instead of mean for central tendency
2. **MAD × 1.4826** instead of std for spread
3. **Percentiles** instead of mean±k*std for thresholds
4. **Breakdown point**: Mean = 0%, Median = 50%

---

### Rule 6: Variable Initialization Must Precede All Access Paths

**Bug Found (INIT-SCOPE)**: Variables accessed before initialization in some code paths:
```python
# BUG: regime_state_version used before any path initializes it
if use_hdbscan:
    # ... code that might skip initialization
    regime_state_version = ...  # ❌ Not initialized if exception occurs

# FIX: Initialize at scope start, before any conditional logic
regime_state_version: int = 0  # ✅ Default at function scope
train_start = pd.Timestamp.min
train_end = pd.Timestamp.max

try:
    if use_hdbscan:
        ...
```

**Rule**: For any variable used in finally/except/downstream:
1. Initialize with safe default at function scope top
2. Don't rely on conditional branches to initialize
3. Use type hints to catch uninitialized usage

---

### Rule 7: Monotonicity Assumptions Must Be Validated

**Principle**: Many degradation models assume monotonic decline. Real systems don't follow this.

**Non-Monotonic Events**:
1. **Maintenance resets** - Health jumps from 40% → 95%
2. **Seasonal variations** - Health varies with load cycles
3. **Intermittent faults** - Fault appears, disappears, reappears
4. **Regime changes** - Different operating modes have different "healthy" baselines

**Rule**: Before using any trend/degradation model:
1. Plot the data - does it actually decline?
2. Test for level shifts using changepoint detection
3. Consider piecewise models for multi-regime data
4. Document the monotonicity assumption and its validity

---

### Statistical Constants Reference

| Constant | Value | Formula | Usage |
|----------|-------|---------|-------|
| MAD to σ | 1.4826 | 1/Φ⁻¹(0.75) | `std_robust = mad * 1.4826` |
| Median breakdown | 50% | — | Median is robust to 50% contamination |
| Mean breakdown | 0% | — | Single outlier corrupts mean |
| Silhouette range | [-1, 1] | — | >0.5 = good clustering |
| HDBSCAN min_cluster_size | 5% of n | — | `max(10, n // 20)` |
| Correlation discount threshold | 0.5 | — | Pairs with |r| > 0.5 get weight reduction |
| Health jump threshold | 15% | — | Positive jumps > 15% = maintenance reset |

---

### Code Review Checklist for Analytical Code

Before approving any PR with statistical/ML code:

- [ ] **Data Flow**: Is transformed data flowing to the correct consumers?
- [ ] **Correlation**: Are fused/combined signals checked for correlation?
- [ ] **Robustness**: Using median/MAD instead of mean/std?
- [ ] **Initialization**: All variables initialized before conditional logic?
- [ ] **State Passthrough**: Is pipeline state reaching ALL consumers?
- [ ] **Monotonicity**: Does the model assume monotonic trends? Is that valid?
- [ ] **Level Shifts**: Are jumps/resets handled appropriately?
- [ ] **Edge Cases**: What happens with empty/NaN/constant data?

---

### Bug Taxonomy for ACM

| Bug ID | Category | Root Cause | Prevention |
|--------|----------|------------|------------|
| SEASON-EP | Data Flow | Transform updates derivative, not source | Trace variable through pipeline |
| FUSE-CORR | Statistical | Ignored inter-detector correlation | Pairwise correlation check |
| HEALTH-JUMP | Temporal | No level shift detection | Changepoint detection |
| STATE-SYNC | Integration | State not passed to consumer | Constructor injection |
| INIT-SCOPE | Control Flow | Variable used before init | Scope-level defaults |
| ROBUST-STAT | Statistical | Mean/std corrupted by outliers | Median/MAD always |

---

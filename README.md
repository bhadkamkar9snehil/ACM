# ACM - Automated Condition Monitoring

Version and Changelog: `docs/CHANGELOG.md`
Last Updated: 2026-02-22
Operational Entrypoint: `python -m core.acm`

ACM is a SQL-first condition monitoring system for industrial equipment. It ingests sensor data from historian tables, builds robust feature frames, scores a multi-detector ensemble, applies regime-aware calibration and fusion, detects episodes, computes drift behavior, and persists analytics and run metadata to SQL.

## Table of Contents

1. What Problem Does ACM Solve
2. Runtime Truth
3. System Architecture
4. Core Concepts
5. Data Flow Pipeline
6. Detection Algorithms
7. Health and Confidence Scoring
8. Episodes and Drift
9. Configuration Model
10. Running ACM
11. Output Tables
12. Observability
13. Validation Checklist
14. Troubleshooting
15. Documentation Map

## 1. What Problem Does ACM Solve

Industrial maintenance has a structural decision problem.

```text
+----------------------------------------------------------------------+
|                        MAINTENANCE DECISION SPACE                    |
+----------------------------------------------------------------------+
|                                                                      |
| Reactive strategy                 Preventive strategy                |
| -----------------                 ------------------                 |
| wait for failure                  replace on schedule                |
| high downtime risk                over-maintenance cost              |
| collateral damage risk            unnecessary part and labor spend   |
|                                                                      |
| ACM objective                                                          |
| -------------                                                          |
| predictive maintenance                                                  |
| early degradation detection                                             |
| context-aware interpretation                                            |
| action-oriented outputs                                                 |
|                                                                      |
+----------------------------------------------------------------------+
```

ACM answers these questions each run:
1. Is current behavior abnormal?
2. Is abnormality transient or sustained?
3. Is this a regime shift or a degradation signal?
4. How severe is current condition in operational terms?

Run outcomes are strict:
- `OK`
- `DEGRADED`
- `NOOP`
- `FAIL`

## 2. Runtime Truth

Current runtime facts for this repository:
1. Supported runtime command is `python -m core.acm`.
2. `core/acm_main.py` is not used in active runtime path.
3. `scripts/sql_batch_runner.py` invokes `core.acm`.
4. Runtime config source of truth is SQL table `ACM_Config`.
5. Forecast and RUL stage are currently disabled in active orchestrator flow.
6. SQL run lifecycle is strict: run start and run finalize are both required.

## 3. System Architecture

### 3.1 High-level view

```text
+------------------------+
| Historian and SQL      |
| raw data + config      |
+------------------------+
           |
           |
+------------------------+
| ACM Runtime            |
| python -m core.acm     |
| stage orchestrator     |
+------------------------+
           |
           |
+------------------------+
| SQL Outputs            |
| scores episodes runs   |
| health regime quality  |
+------------------------+
           |
           |
+------------------------+
| Observability Stack    |
| Grafana Loki Tempo     |
| Prometheus Pyroscope   |
+------------------------+
```

### 3.2 Technology stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Runtime | Python 3.11 | Pipeline orchestration and model execution |
| Data processing | pandas, NumPy, scikit-learn | Features, detectors, calibration, fusion |
| Database | SQL Server | Historian source and output persistence |
| SQL connectivity | pyodbc, T-SQL | Runtime read and write operations |
| Visualization | Grafana | Operational dashboards |
| Observability | OpenTelemetry stack | Logs, traces, metrics, profiling |

### 3.3 Ownership map for core runtime

- `core/acm.py`: top-level orchestrator
- `core/sql_client.py`: SQL connect and run bootstrap
- `core/smart_coldstart.py`: load, retry, coldstart, noop logic
- `core/fast_features.py`: feature preparation and imputation
- `core/detector_orchestrator.py`: detector init, fit, score, calibrate
- `core/regimes.py`: regime basis, labeling, occupancy, transient analysis
- `core/model_persistence.py`: adaptation, retrain, model lifecycle persistence
- `core/fuse.py`: calibration, fusion, episodes, threshold updates
- `core/drift.py`: drift mode computation and controller persistence
- `core/output_manager.py`: SQL persistence stage and analytics writes
- `core/run_metadata_writer.py`: outcome mapping and teardown finalization

## 4. Core Concepts

### 4.1 Operating regimes

Regimes describe how equipment is operating. They are not anomaly labels.

```text
+------------------------------------------------------------------+
|                       REGIME PRINCIPLE                           |
+------------------------------------------------------------------+
| Regime modeling answers: how is machine operating now?           |
| Detector scoring answers: how abnormal is behavior in context?   |
|                                                                  |
| These concerns stay separate to avoid masking true faults.       |
+------------------------------------------------------------------+
```

### 4.2 Multi-detector fusion

Different fault shapes require different detectors.

```text
+------------------------------------------------------------------+
|                        DETECTOR ENSEMBLE                         |
+------------------------------------------------------------------+
| AR1      : local temporal residual change                         |
| PCA SPE  : off-subspace novelty                                   |
| PCA T2   : latent-space extremity                                 |
| IForest  : sparse outlier isolation                               |
| GMM      : low likelihood under learned density                   |
| OMR      : inter-sensor relationship break                        |
+------------------------------------------------------------------+
| calibrated detector z-scores are fused into one operational score |
+------------------------------------------------------------------+
```

### 4.3 Model lifecycle

Model state evolves through maturity states in lifecycle logic.

```text
COLDSTART  LEARNING  CONVERGED  DEPRECATED
```

Maturity influences how aggressively adaptation and persistence decisions are applied.

## 5. Data Flow Pipeline

### 5.1 End-to-end stage sequence

```text
Phase 1  startup and SQL bootstrap
Phase 2  data load and coldstart/noop resolution
Phase 3  data contract validation and guardrails
Phase 4  baseline seed
Phase 5  feature preparation and imputation
Phase 6  detector initialization and compatibility checks
Phase 7  detector scoring and regime labeling
Phase 8  model adaptation and persistence
Phase 9  calibration fusion episodes threshold updates
Phase 10 drift postprocess
Phase 11 persistence input preparation
Phase 12 SQL output persistence and analytics
Phase 13 outcome resolution and teardown finalization
```

### 5.2 Typical timing shape

Timing varies by equipment, data volume, and cache state, but these usually dominate:
1. feature preparation
2. detector fit when retrain occurs
3. SQL persistence and analytics writes

## 6. Detection Algorithms

### 6.1 AR1 detector

Intent:
- Detect per-sensor local residual shifts against short-memory expectation.

Strength:
- Good for abrupt univariate changes.

Typical blind spot:
- Purely multivariate shifts where no single sensor is individually extreme.

### 6.2 PCA SPE and PCA T2

Intent:
- SPE detects novelty off learned latent manifold.
- T2 detects extreme movement inside latent manifold.

Strength:
- Captures structure-level behavior not visible in one-sensor analysis.

Typical blind spot:
- Patterns that remain plausible in latent space but are faulty for other reasons.

### 6.3 Isolation Forest

Intent:
- Detect sparse outliers through random partition isolation behavior.

Strength:
- Non-parametric outlier sensitivity in high-dimensional frames.

Typical blind spot:
- Dense collective shifts that are not sparse outliers.

### 6.4 GMM detector

Intent:
- Score low-probability states under fitted mixture density.

Strength:
- Useful for multimodal healthy operating distributions.

Typical blind spot:
- Training contamination can normalize degraded states.

### 6.5 OMR detector

Intent:
- Detect breakage in inter-sensor consistency relationships.

Strength:
- Catches dependency break patterns even when individual channels look plausible.

Typical blind spot:
- Uniform global shifts that preserve relationships.

### 6.6 Why all six are needed

No single detector family covers all realistic failure morphologies. Ensemble agreement is more reliable than single-detector excursions.

## 7. Health and Confidence Scoring

### 7.1 Score transformation

ACM scoring path:
1. Detector raw score generation.
2. Detector-level calibration into comparable z-space.
3. Fusion into a unified anomaly intensity.
4. Health-oriented downstream interpretation from fused behavior.

Conceptual fusion expression:
- `fused_z(t) = sum(w_i * z_i(t))`

### 7.2 Confidence and reliability factors

Operational confidence depends on factors such as:
1. data quality
2. regime quality
3. consistency of detector agreement
4. model maturity and adaptation state

## 8. Episodes and Drift

### 8.1 Episode logic

Episodes capture sustained abnormal intervals, not isolated spikes.

Why this matters:
1. sustained events are operationally actionable
2. duration and severity together are better than peak-only scoring

### 8.2 Drift logic

Drift identifies directional behavior change beyond point anomaly level.

Practical distinction:
- anomaly score: how unusual current behavior is
- drift mode: whether behavior trend state is moving directionally

## 9. Configuration Model

### 9.1 Runtime source of truth

- SQL table: `ACM_Config`

### 9.2 Config seeding and sync

- Seeder script: `scripts/sql/populate_acm_config.py`
- Seed source: `configs/config_table.csv`

### 9.3 SQL connection config

- `configs/sql_connection.ini` (gitignored)

## 10. Running ACM

### 10.1 Production-like batch mode

```powershell
python scripts/sql_batch_runner.py --equip FD_FAN GAS_TURBINE --max-workers 2 --resume
```

### 10.2 Single run mode

```powershell
python -m core.acm --equip FD_FAN --start-time "2024-01-01T00:00:00" --end-time "2024-01-02T00:00:00"
```

### 10.3 CLI options

```text
--equip
--force-retrain
--clear-cache
--log-level
--log-format
--log-file
--log-module-level
--start-time
--end-time
```

## 11. Output Tables

### 11.1 Core output categories

1. scores and fused signals
2. episodes and culprits
3. regime timelines and summaries
4. data quality diagnostics
5. run metadata and lifecycle closure

### 11.2 Typical operational tables

- `ACM_Runs`
- `ACM_Scores_Wide`
- `ACM_Episodes` and or `ACM_Anomaly_Events`
- `ACM_HealthTimeline`
- `ACM_RegimeTimeline`
- `ACM_DataQuality`
- `ACM_RunMetadata`

Forecast note:
- Forecast-related schema may exist.
- Active orchestrator currently keeps forecast stage disabled.

## 12. Observability

Signals emitted by ACM:
1. logs for stage and error context
2. traces for run and stage timing
3. metrics for outcomes, health, and quality

Typical local endpoints:
- Grafana: `http://localhost:3000`
- Loki: `http://localhost:3100`
- Tempo: `http://localhost:3200`
- Prometheus: `http://localhost:9090`
- Pyroscope: `http://localhost:4040`

## 13. Validation Checklist

Use this after structural or behavior-sensitive changes:

```powershell
python -m py_compile core/acm.py
python -m core.acm --help
python -c "from core.acm import main; print(callable(main))"
pytest tests/test_v11_modules.py -v
python scripts/sql_batch_runner.py --equip FD_FAN --dry-run
```

Recommended parity checks for refactor slices:
1. outcome
2. rows_read
3. rows_written
4. episode count
5. final drift mode
6. regime quality status
7. run finalization success

## 14. Troubleshooting

### 14.1 SQL startup failures

1. validate `configs/sql_connection.ini`
2. validate SQL reachability and credentials
3. run with debug logging for startup context

### 14.2 Unexpected NOOP outcomes

1. validate historian coverage for selected window
2. check coldstart minimum-data thresholds
3. inspect batch runner precheck path

### 14.3 Unstable adaptation behavior

1. inspect model cache compatibility logs
2. inspect regime quality and drift outputs
3. inspect run metadata and quality records

### 14.4 Dashboard mismatch

1. verify query table and field names match active schema
2. verify panel options and color settings are valid for installed Grafana version
3. verify selected equipment and time range contain rows

## 15. Documentation Map

Primary references:
- `docs/CHANGELOG.md`
- `docs/ACM_SYSTEM_OVERVIEW.md`
- `docs/ACM_SINGLE_ENTRYPOINT_REFACTOR_MASTER_PLAN.md`
- `docs/OUTPUT_MANAGER_REFACTOR_MASTER_PLAN.md`
- `docs/ACM Main Refactoring Analysis - Action.md`

Code map for runtime first-read:
- `core/acm.py`
- `core/sql_client.py`
- `core/smart_coldstart.py`
- `core/fast_features.py`
- `core/detector_orchestrator.py`
- `core/regimes.py`
- `core/fuse.py`
- `core/drift.py`
- `core/output_manager.py`
- `core/run_metadata_writer.py`

---

This README intentionally keeps release history in `docs/CHANGELOG.md` and keeps runtime truth aligned to active code.

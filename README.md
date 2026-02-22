# ACM - Automated Condition Monitoring

Version and Changelog: `docs/CHANGELOG.md`
Last Updated: 2026-02-22
Operational Entrypoint: `python -m core.acm`

ACM is a SQL-first condition monitoring platform for industrial equipment. It ingests historian data, builds robust features, scores detector ensembles, applies regime-aware calibration, detects episodes, computes drift, and persists analytics to SQL.

## Table of Contents

1. What ACM Solves
2. Runtime Truth
3. Architecture Overview
4. Pipeline Flow in `core.acm`
5. Detector and Regime Logic
6. Entrypoints and Operations
7. Configuration and SQL Model
8. Outputs and Tables
9. Observability
10. Validation Checklist
11. Troubleshooting
12. Repository Map
13. Refactor Status
14. Related Documents

## 1. What ACM Solves

Industrial monitoring systems usually fail in one of two ways:
1. Too many noisy alerts that operators ignore.
2. Too little context, so true degradation is discovered late.

ACM focuses on four operational questions:
1. What is the current health state of this equipment?
2. Which sensors and detectors are driving that state?
3. Is behavior change a normal operating regime shift or a fault?
4. Is the trend stable, degrading, or drifting from learned baseline?

ACM run outcomes are strict and machine-readable:
- `OK`
- `DEGRADED`
- `NOOP`
- `FAIL`

## 2. Runtime Truth

Current codebase runtime facts:
1. Single supported entrypoint is `python -m core.acm`.
2. `core/acm_main.py` is removed and not used in active runtime.
3. `scripts/sql_batch_runner.py` invokes `core.acm`.
4. Runtime config source is SQL table `ACM_Config`.
5. Forecast and RUL execution are currently disabled in active orchestrator path.
6. Observability emits logs, traces, and metrics through `core/observability.py`.

## 3. Architecture Overview

### 3.1 System-level view

```text
+----------------------+       +-----------------------+       +-----------------------+
| Historian and SQL    |       | ACM Runtime           |       | Observability Stack   |
| (raw + config + runs)| ----> | python -m core.acm    | ----> | Grafana/Tempo/Loki/   |
|                      |       |                       |       | Prometheus/Pyroscope  |
+----------------------+       +-----------------------+       +-----------------------+
                                       |
                                       v
                             +-----------------------+
                             | SQL Outputs           |
                             | Scores, Episodes,     |
                             | Health, Regimes, Runs |
                             +-----------------------+
```

### 3.2 Ownership map for orchestrator calls

- `core/acm.py`: orchestration only
- `core/sql_client.py`: SQL connect, bootstrap, runtime policy
- `core/smart_coldstart.py`: load, retry, coldstart, NOOP logic
- `core/fast_features.py`: feature prep stage and imputation
- `core/detector_orchestrator.py`: detector init, fit, score helpers
- `core/regimes.py`: regime stage, quality, labels
- `core/model_persistence.py`: model adaptation and persistence
- `core/fuse.py`: calibration, fusion, episodes, threshold updates
- `core/drift.py`: drift mode and drift post-processing
- `core/output_manager.py`: persistence stage and analytics writes
- `core/run_metadata_writer.py`: summary and run finalization

## 4. Pipeline Flow in `core.acm`

### 4.1 Stage sequence

```text
startup
  -> SQL connect (fail-fast)
  -> bootstrap run state
  -> load and validate data
  -> baseline seed
  -> feature preparation
  -> detector initialization
  -> scoring and regime stage
  -> model adaptation and persistence
  -> calibration/fusion/episodes
  -> drift post-process
  -> persistence inputs
  -> persistence stage
  -> outcome resolution
  -> teardown and finalize
```

### 4.2 Error and teardown behavior

- Core stage exceptions are not silently swallowed.
- Any unhandled exception sets `outcome=FAIL` and serializes error payload.
- Finalization always runs in `finally` through `finalize_pipeline_teardown(...)`.

## 5. Detector and Regime Logic

### 5.1 Detector ensemble intent

ACM uses multiple detector families because faults present differently:
- AR1 residual behavior anomalies
- PCA SPE and PCA T2 distribution/structure anomalies
- Isolation forest rare-state anomalies
- GMM density and cluster likelihood anomalies
- OMR residual consistency anomalies

These detector outputs are calibrated and fused to produce an interpretable fused signal.

### 5.2 Regime principle

Regime modeling answers how equipment is operating, while detectors answer whether behavior is healthy.

Operational rule:
- Regime and health logic are related but not interchangeable.
- Regime stage output is used as context for scoring, calibration, and post-analysis.

## 6. Entrypoints and Operations

### 6.1 Production batch runner

```powershell
python scripts/sql_batch_runner.py --equip FD_FAN GAS_TURBINE --max-workers 2 --resume
```

### 6.2 Single run execution

```powershell
python -m core.acm --equip FD_FAN --start-time "2024-01-01T00:00:00" --end-time "2024-01-02T00:00:00"
```

### 6.3 CLI options in `core.acm`

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

## 7. Configuration and SQL Model

### 7.1 Runtime configuration source

- Primary runtime config source: `ACM_Config` in SQL.
- Seeder/sync utility: `scripts/sql/populate_acm_config.py`.
- Seed file: `configs/config_table.csv`.

Operational interpretation:
- CSV is a management artifact.
- SQL is the active runtime source of truth.

### 7.2 SQL connection source

- `configs/sql_connection.ini` (gitignored)

## 8. Outputs and Tables

### 8.1 Core output categories

ACM persistence writes are organized around these categories:
1. Scores and health state over time.
2. Episodes and culprit context.
3. Regime timeline and regime summaries.
4. Data quality and diagnostics.
5. Run metadata and run lifecycle closure.

### 8.2 Typical key tables

- `ACM_Runs`
- `ACM_Scores_Wide`
- `ACM_Episodes` and/or `ACM_Anomaly_Events` depending on write path
- `ACM_HealthTimeline`
- `ACM_RegimeTimeline`
- `ACM_DataQuality`
- `ACM_RunMetadata`

Forecast note:
- Forecast-related tables can exist in schema and output manager APIs.
- Active orchestrator flow currently logs forecasting as disabled.

## 9. Observability

### 9.1 Stack components

- Grafana
- Tempo
- Loki
- Prometheus
- Pyroscope
- Alloy

Typical local access:
- Grafana: `http://localhost:3000`

### 9.2 Signal model

- Logs: lifecycle, stage status, warnings, failures
- Traces: phase timing and span correlation
- Metrics: run outcomes, data quality, health score, detector signals

## 10. Validation Checklist

Use this after structural or behavioral changes:

```powershell
python -m py_compile core/acm.py
python -m core.acm --help
python -c "from core.acm import main; print(callable(main))"
pytest tests/test_v11_modules.py -v
python scripts/sql_batch_runner.py --equip FD_FAN --dry-run
```

Recommended runtime parity checks for major refactor slices:
- outcome
- rows_read
- rows_written
- episode count
- final drift mode
- regime quality status
- run finalization success

## 11. Troubleshooting

### 11.1 SQL connection failures

- Verify `configs/sql_connection.ini` is valid.
- Verify SQL instance availability and credentials.
- Run SQL verification utility scripts under `scripts/sql/` when needed.

### 11.2 Unexpected NOOP outcomes

- Validate historian table has rows in requested window.
- Check coldstart and minimum data conditions.
- Check batch runner precheck logs.

### 11.3 Unstable retraining behavior

- Check feature compatibility and cache state logs.
- Check regime quality and drift outputs.
- Check model adaptation signals in run metadata.

### 11.4 Dashboard mismatch

- Verify dashboard queries target active tables.
- Verify panel field names match current schema.
- Validate color and panel option values are supported by current Grafana version.

## 12. Repository Map

Runtime-relevant paths:
- `core/`: pipeline and ownership modules
- `scripts/sql_batch_runner.py`: production batch orchestration
- `scripts/sql/`: migrations, config sync, SQL utilities
- `configs/`: SQL connection and config seed artifacts
- `docs/`: architecture and operations documentation
- `tests/`: module and regression checks

## 13. Refactor Status

Current structural status:
1. Single runtime entrypoint migration completed at runtime level.
2. `core/acm.py` is orchestrator and active command surface.
3. Remaining simplification focus is destination-module complexity reduction in:
   - `core/output_manager.py`
   - `core/regimes.py`
   - `core/fuse.py`

## 14. Related Documents

Primary references:
- `docs/CHANGELOG.md` (single canonical version and changelog document)
- `docs/ACM_SYSTEM_OVERVIEW.md`
- `docs/ACM_SINGLE_ENTRYPOINT_REFACTOR_MASTER_PLAN.md`
- `docs/OUTPUT_MANAGER_REFACTOR_MASTER_PLAN.md`
- `docs/ACM Main Refactoring Analysis - Action.md`

---

This README is intentionally detailed enough for onboarding and operations while keeping release history in `docs/CHANGELOG.md`.

# ACM System Overview

Version: 11.15.5
Last Updated: 2026-02-22
Scope: Current active runtime behavior in this repository

This document is the implementation-level reference for how ACM currently runs, what modules own which responsibilities, and how to validate behavior safely during refactor work.

## 1. Runtime Positioning

ACM is a SQL-first condition monitoring pipeline.

Current runtime facts:
1. Supported runtime command is `python -m core.acm`.
2. `core/acm_main.py` is removed from active runtime path.
3. `scripts/sql_batch_runner.py` runs ACM by invoking `core.acm`.
4. Forecast and RUL execution are currently disabled in active orchestration.
5. Run outcome contract is strict: `OK`, `DEGRADED`, `NOOP`, `FAIL`.

## 2. Mental Model

ACM run lifecycle for one equipment window:

1. SQL connect and run bootstrap.
2. Config and run window resolution.
3. Data load and coldstart decision.
4. Feature preparation.
5. Detector and regime scoring.
6. Calibration, fusion, episodes, thresholds.
7. Drift evaluation.
8. Persistence and analytics output.
9. Run metadata finalization and observability flush.

The orchestrator is intentionally thin and delegates stage logic into owner modules under `core/`.

## 3. Entrypoints

### 3.1 Operational entrypoint

```powershell
python -m core.acm --equip FD_FAN
```

### 3.2 Batch runner

```powershell
python scripts/sql_batch_runner.py --equip FD_FAN GAS_TURBINE --max-workers 2 --resume
```

Batch runner responsibilities:
- equipment loop and scheduling
- historian window progression
- coldstart retries
- dry-run and resume workflows

## 4. Orchestrator Structure (`core/acm.py`)

Public functions:
- `build_arg_parser()`
- `run_pipeline(args)`
- `main(args=None)`

`main()` performs orchestration and delegates logic through explicit stage calls. It does not own heavy algorithm logic anymore.

## 5. Stage Ownership Map

### 5.1 Bootstrap and runtime policy
- Module: `core/sql_client.py`
- Functions used by orchestrator:
  - `connect_acm_sql_failfast`
  - `bootstrap_acm_run_state`
  - `resolve_runtime_policy`

Responsibilities:
- fail-fast SQL initialization
- equipment and run window bootstrap
- config signature and run count setup
- run start registration

### 5.2 Data load and coldstart
- Module: `core/smart_coldstart.py`
- Function used by orchestrator:
  - `load_and_validate_data_stage`
  - `seed_baseline_safe`

Responsibilities:
- historian load with retries
- coldstart defer/continue decisions
- NOOP resolution and finalize callback path
- baseline seeding

### 5.3 Data contract and guardrails
- Module: `core/pipeline_types.py`
- Functions used by orchestrator:
  - `validate_data_contract_at_entry`
  - `run_data_guardrails_safe`

Responsibilities:
- entry validation and threshold checks
- guardrail metrics and quality constraints

### 5.4 Feature preparation
- Module: `core/fast_features.py`
- Function used by orchestrator:
  - `run_feature_preparation_stage`

Responsibilities:
- feature engineering and imputation
- seasonal adjustment wiring
- protected columns handling from model manifest
- train and score feature framing

### 5.5 Detector initialization and scoring
- Module: `core/detector_orchestrator.py`
- Functions used by orchestrator:
  - `run_detector_initialization_stage`
  - `fit_all_detectors`
  - `score_all_detectors`

Responsibilities:
- detector enable flags
- cache compatibility validation
- detector load or retrain path
- train and score detector raw outputs

### 5.6 Regime stage
- Module: `core/regimes.py`
- Function used by orchestrator:
  - `run_scoring_regime_stage`

Responsibilities:
- regime basis and model state handling
- regime labels for train and score windows
- regime quality signals and degraded tagging

### 5.7 Model adaptation and persistence decisions
- Module: `core/model_persistence.py`
- Function used by orchestrator:
  - `run_model_adaptation_and_persistence_stage`

Responsibilities:
- post-score model quality assessment
- retrain and persistence decisions
- model state transitions and versioning

### 5.8 Health stage
- Module: `core/fuse.py`
- Function used by orchestrator:
  - `run_health_stage`

Responsibilities:
- calibration on train frame
- score transform to z-space
- fused score computation
- episode detection
- adaptive threshold update hook

### 5.9 Drift stage
- Module: `core/drift.py`
- Function used by orchestrator:
  - `run_drift_postprocess_stage`

Responsibilities:
- drift mode computation
- drift controller payload and persistence wiring
- final episode schema normalization integration

### 5.10 Persistence stage
- Module: `core/output_manager.py`
- Functions used by orchestrator:
  - `prepare_persistence_inputs`
  - `run_persistence_stage`

Responsibilities:
- baseline buffer update
- sensor analytics context preparation
- core output writes and analytics table generation
- SQL artifact persistence final call

### 5.11 Finalization and metadata
- Module: `core/run_metadata_writer.py`
- Functions used by orchestrator:
  - `resolve_run_outcome_from_degradations`
  - `serialize_run_exception`
  - `finalize_pipeline_teardown`

Responsibilities:
- batch summary logging
- data quality extraction for run metadata
- write `ACM_Runs` metadata
- run finalization and observability closeout

## 6. Active Pipeline Execution Order

Current `core.acm` execution sequence:

1. `init_run_observability`
2. `connect_acm_sql_failfast`
3. `bootstrap_acm_run_state`
4. `load_and_validate_data_stage`
5. `seed_baseline_safe`
6. `run_feature_preparation_stage`
7. `run_detector_initialization_stage`
8. `run_scoring_regime_stage`
9. `run_model_adaptation_and_persistence_stage`
10. `run_health_stage`
11. `run_drift_postprocess_stage`
12. `prepare_persistence_inputs`
13. `run_persistence_stage`
14. `resolve_run_outcome_from_degradations`
15. `finalize_pipeline_teardown`

If any stage raises unexpectedly:
- outcome is set to `FAIL`
- serialized error payload is attached
- teardown still runs in `finally`

## 7. SQL and Configuration Model

### 7.1 Runtime config source
- Table: `ACM_Config`

### 7.2 Config seeding and sync
- Script: `scripts/sql/populate_acm_config.py`
- Seed source file: `configs/config_table.csv`

### 7.3 SQL connection source
- File: `configs/sql_connection.ini` (gitignored)

### 7.4 Run registration and closure
- run start and window registration happens during bootstrap
- final closure happens during teardown via SQL finalize logic

## 8. Core Data Outputs

At minimum, normal runs persist:
- scores and detector outputs
- episode records
- health and regime analytics
- run-level metadata

Primary operational tables include:
- `ACM_Runs`
- `ACM_Scores_Wide`
- `ACM_Episodes` or `ACM_Anomaly_Events` depending on writer path
- `ACM_HealthTimeline`
- `ACM_RegimeTimeline`
- `ACM_DataQuality`
- `ACM_RunMetadata`

Note on forecasts:
- forecast-related schema may still exist and be managed in output layers
- active orchestrator path currently logs forecast as disabled and does not run forecasting stage

## 9. Observability Model

Instrumentation entry points in orchestrator:
- run initialization: `init_run_observability`
- span creation: `start_run_span`
- metric and event emissions during stages
- teardown: `close_run_span`, `shutdown_run_observability`

Typical local stack:
- Grafana on 3000
- Loki on 3100
- Tempo on 3200
- Prometheus on 9090
- Pyroscope on 4040

## 10. Run Outcomes and Semantics

### 10.1 `OK`
All required stages completed and outputs were written.

### 10.2 `DEGRADED`
Run completed but one or more non-fatal degraded conditions were recorded.

### 10.3 `NOOP`
No actionable data for scoring window or coldstart defer path. Finalization still occurs.

### 10.4 `FAIL`
Unhandled exception in core path. Error payload serialized, then teardown finalization attempted.

## 11. Refactor Context

Single-entrypoint migration status:
1. Runtime decommission of `acm_main` is complete.
2. Orchestrator exists in `core/acm.py`.
3. Remaining work is complexity reduction in owner modules, especially:
   - `core/output_manager.py`
   - `core/regimes.py`
   - `core/fuse.py`

Refactor rules currently followed:
- no behavior loss in run lifecycle
- no schema-destructive changes in refactor slices
- move full logic units to ownership modules
- keep `core/acm.py` as orchestrator

## 12. Validation and Safety Checklist

Use this after structural changes:

```powershell
python -m py_compile core/acm.py
python -m core.acm --help
python -c "from core.acm import main; print(callable(main))"
pytest tests/test_v11_modules.py -v
python scripts/sql_batch_runner.py --equip FD_FAN --dry-run
```

For runtime validation, compare with baseline values:
- outcome
- rows_read
- rows_written
- episode count
- drift mode
- regime quality status
- run finalization success

## 13. Troubleshooting

### 13.1 SQL startup failure
- check `configs/sql_connection.ini`
- validate SQL service availability and credentials

### 13.2 Frequent NOOP
- validate historian coverage for equipment table
- review coldstart state and required minimum rows

### 13.3 Unexpected degradation or retrain activity
- inspect model compatibility and cache logs
- inspect regime quality and drift indicators
- review adaptive threshold behavior from recent runs

### 13.4 Dashboard mismatch
- verify Grafana dashboards are using current table names and valid color palettes
- verify output tables are populated for selected equipment and window

## 14. Codebase Navigation Quick Map

Runtime files you usually need first:
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

Supporting docs:
- `docs/ACM_SINGLE_ENTRYPOINT_REFACTOR_MASTER_PLAN.md`
- `docs/OUTPUT_MANAGER_REFACTOR_MASTER_PLAN.md`
- `docs/ACM Main Refactoring Analysis - Action.md`

---

This overview is intentionally aligned to the current runtime state in code, not historical architecture notes.

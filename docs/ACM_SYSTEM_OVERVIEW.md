# ACM System Overview

Version: 11.15.5
Last Updated: 2026-02-22
Scope: Current active runtime behavior in this repository

This document is the implementation-level and theory-level reference for ACM. It explains:
1. What ACM is trying to infer.
2. Why the detection problem is difficult in production.
3. How the active module graph executes one run.
4. What reliability and data issues are already handled.

## 1. Runtime Positioning

ACM is a SQL-first condition monitoring pipeline.

Current runtime facts:
1. Supported operational command is `python -m core.acm`.
2. `core/acm_main.py` is removed from active runtime path.
3. `scripts/sql_batch_runner.py` invokes `core.acm`.
4. Forecast and RUL execution are currently disabled in active orchestrator path.
5. Run outcome contract is strict: `OK`, `DEGRADED`, `NOOP`, `FAIL`.

## 2. What ACM Is Solving

ACM solves an unsupervised reliability inference problem on multivariate time series.

Given sensor vector `x_t` at time `t`, ACM must estimate:
1. Is `x_t` unusual relative to learned healthy behavior?
2. Is the current state abnormal only because the operating regime changed?
3. Is current high score a spike or part of sustained episode behavior?
4. Is system behavior drifting away from expected baseline?

ACM therefore combines:
1. Multiple detector families with different assumptions.
2. Regime context to avoid one-size-fits-all thresholds.
3. Robust calibration before score fusion.
4. Episode and drift logic for temporal continuity.

## 3. Theory and Statistical Foundations

### 3.1 Why this is an ensemble problem

No single detector can cover all industrial fault morphologies.

ACM detector families and their assumptions:
1. AR1 residual detector:
- Assumes short-memory temporal predictability per signal.
- Strong for abrupt univariate residual changes.

2. PCA SPE and PCA T2:
- Assumes healthy behavior lies on a dominant latent subspace.
- SPE captures off-subspace novelty.
- T2 captures extreme movement along learned latent directions.

3. Isolation Forest:
- Assumes anomalies isolate quickly in randomized partition trees.
- Strong for sparse outlier states in high-dimensional feature space.

4. GMM likelihood:
- Assumes healthy states follow mixture-density structure.
- Strong for low-likelihood points under learned density.

5. OMR residual:
- Assumes stable inter-sensor relationships.
- Strong when dependencies between sensors break.

Practical implication:
- Detector agreement increases confidence.
- Detector disagreement is expected and informative.

### 3.2 Feature pipeline and robustness principles

Feature engineering is not optional. Raw historian channels are often noisy, shifted, and partially missing.

Core principles used:
1. Fill-value leakage prevention.
- Score-frame fill values are derived from train-frame statistics.

2. Low-variance and all-NaN feature pruning.
- Removes non-informative channels from detector feature space.

3. Manifest-protected feature set.
- Features required by cached models are protected from accidental drop.

4. Index hygiene and deduplication.
- Prevents timestamp duplication artifacts in rolling transforms and persistence.

### 3.3 Calibration and fusion objective

Detector outputs are heterogeneous and not directly comparable.

Calibration stage maps each detector raw score to calibrated z-space.
- Robust center/scale estimates.
- Quantile threshold extraction.
- Optional per-regime calibration when regime quality permits.

Fusion stage aggregates calibrated detector evidence.
Conceptual form:
- `fused_z(t) = sum_i w_i * z_i(t)`

Weight behavior:
1. Starts from configured priors.
2. Can be tuned using run evidence.
3. Treated as diagnostic metadata for downstream interpretability.

### 3.4 Regime and health separation

ACM uses regime modeling as context, not as anomaly ground truth.

Key idea:
1. Regime says how machine is operating.
2. Detector/fusion says how abnormal current behavior is in that context.

This separation reduces false alarms when machine load/state legitimately changes.

### 3.5 Episodes and drift as temporal layers

Point anomalies are insufficient for operational decisions.

Temporal layers add continuity:
1. Episode logic captures sustained abnormal periods.
2. Drift logic captures directional or mode-level change behavior.
3. Final outputs represent both intensity and persistence dimensions.

## 4. Why ACM Is Hard to Develop

### 4.1 Data and ML difficulty

1. Ground truth labels are sparse or absent.
2. Coldstart windows can contain degraded periods.
3. Regime shifts can imitate faults in naive models.
4. Sensor quality issues can dominate model behavior if not gated early.

### 4.2 Production-system difficulty

1. SQL run lifecycle must remain strict on all paths.
2. Batch windows can have sparse or no data.
3. Partial failures must degrade safely without losing core writes.
4. Dashboard compatibility depends on stable schema and field semantics.

### 4.3 Refactor difficulty

1. Large legacy monolith had intertwined concerns.
2. Ownership extraction risks hidden behavioral drift.
3. Finalization semantics are easy to break during decomposition.
4. Complexity can shift from orchestrator to owner modules if not controlled.

## 5. Active Architecture and Ownership

### 5.1 Orchestrator

- Module: `core/acm.py`
- Public functions:
  - `build_arg_parser()`
  - `run_pipeline(args)`
  - `main(args=None)`

Role:
- Thin orchestration.
- Explicit stage ordering.
- Outcome and teardown coordination.

### 5.2 Stage ownership map

1. Bootstrap and runtime policy
- Module: `core/sql_client.py`
- Functions:
  - `connect_acm_sql_failfast`
  - `bootstrap_acm_run_state`
  - `resolve_runtime_policy`

2. Data load and coldstart
- Module: `core/smart_coldstart.py`
- Functions:
  - `load_and_validate_data_stage`
  - `seed_baseline_safe`

3. Data contract and guardrails
- Module: `core/pipeline_types.py`
- Functions:
  - `validate_data_contract_at_entry`
  - `run_data_guardrails_safe`

4. Feature preparation
- Module: `core/fast_features.py`
- Function:
  - `run_feature_preparation_stage`

5. Detector initialization and score helpers
- Module: `core/detector_orchestrator.py`
- Functions:
  - `run_detector_initialization_stage`
  - `fit_all_detectors`
  - `score_all_detectors`
  - `calibrate_all_detectors`

6. Regime stage
- Module: `core/regimes.py`
- Functions:
  - `run_scoring_regime_stage`
  - `run_regime_postprocess_stage`

7. Model adaptation and persistence logic
- Module: `core/model_persistence.py`
- Function:
  - `run_model_adaptation_and_persistence_stage`

8. Health stage
- Module: `core/fuse.py`
- Function:
  - `run_health_stage`

9. Drift stage
- Module: `core/drift.py`
- Function:
  - `run_drift_postprocess_stage`

10. Persistence stage
- Module: `core/output_manager.py`
- Functions:
  - `prepare_persistence_inputs`
  - `run_persistence_stage`

11. Finalization and metadata
- Module: `core/run_metadata_writer.py`
- Functions:
  - `resolve_run_outcome_from_degradations`
  - `serialize_run_exception`
  - `finalize_pipeline_teardown`

## 6. Active Pipeline Execution Order

Current `core.acm` top-level sequence:

1. `init_run_observability`
2. `connect_acm_sql_failfast`
3. `bootstrap_acm_run_state`
4. `resolve_runtime_policy`
5. `load_and_validate_data_stage`
6. `seed_baseline_safe`
7. `run_feature_preparation_stage`
8. `run_detector_initialization_stage`
9. `run_scoring_regime_stage`
10. `run_model_adaptation_and_persistence_stage`
11. `run_health_stage`
12. `run_drift_postprocess_stage`
13. `prepare_persistence_inputs`
14. `run_persistence_stage`
15. `resolve_run_outcome_from_degradations`
16. `finalize_pipeline_teardown`

If any stage raises unexpectedly:
1. outcome is set to `FAIL`
2. serialized error payload is attached
3. teardown still runs in `finally`

## 7. Detailed Module-to-Module Call Chain

This section documents one normal scoring run at function level.

1. `core.acm.main`
- Calls `core.observability.init_run_observability`
- Calls `core.sql_client.connect_acm_sql_failfast`
- Calls `core.sql_client.bootstrap_acm_run_state`
- Calls `core.sql_client.resolve_runtime_policy`
- Creates `core.output_manager.OutputManager`

2. `core.sql_client.connect_acm_sql_failfast`
- Calls `core.sql_client.connect_acm_sql`
- `connect_acm_sql` attempts INI path first then cfg fallback
- Performs `SELECT 1` probe

3. `core.sql_client.bootstrap_acm_run_state`
- Calls `load_config_required_from_sql`
- Calls `resolve_equipment_id_required`
- Calls `get_acm_run_count`
- Calls `start_acm_run`
- Calls `apply_cli_window_overrides`
- Returns `AcmRunBootstrapState`

4. `core.smart_coldstart.load_and_validate_data_stage`
- Creates `SmartColdstart`
- Calls `SmartColdstart.load_with_retry`
- Calls `classify_noop_reason` for deferred/no-data paths
- Calls `finalize_noop_run` if run should stop
- Calls `ensure_local_index` and `deduplicate_index`
- Calls `validate_data_contract_at_entry`
- Returns `DataLoadStageResult`

5. `core.smart_coldstart.seed_baseline_safe`
- Baseline continuity update
- Returns updated `train` and `score`

6. `core.fast_features.run_feature_preparation_stage`
- Calls `detect_and_adjust_safe`
- Calls `run_data_guardrails_safe`
- Calls `build_features_for_pipeline`
- Calls `load_manifest_protected_columns`
- Calls `impute_features`
- Calls `OutputManager.check_refit_request`
- Returns `FeaturePreparationResult`

7. `core.detector_orchestrator.run_detector_initialization_stage`
- Runs detector cache/load/fit orchestration
- Uses `load_cached_models_with_validation`
- Uses detector rebuild helpers when needed
- Optionally calls `fit_all_detectors`
- Returns `DetectorInitState`

8. `core.regimes.run_scoring_regime_stage`
- Calls regime basis build stage
- Calls `score_all_detectors`
- Calls maturity resolver for regime path
- Calls regime labeling stage
- Calls occupancy and transition writer
- Returns `ScoringRegimeStageResult`

9. `core.model_persistence.run_model_adaptation_and_persistence_stage`
- Calls `core.model_evaluation.run_auto_retrain_stage`
- Calls model persistence and lifecycle stage
- Returns `ModelAdaptationPersistenceResult`

10. `core.fuse.run_health_stage`
- Calls calibration stage
- Calibration stage uses `score_all_detectors`, `calibrate_all_detectors`, and calibration persistence helper
- Calls fusion stage
- Calls `maybe_update_adaptive_thresholds`
- Calls `core.regimes.run_regime_postprocess_stage`
- Calls `core.model_evaluation.auto_tune_parameters`
- Returns `HealthStageResult`

11. `core.drift.run_drift_postprocess_stage`
- Calls `run_drift_pipeline`
- `run_drift_pipeline` calls:
  - `compute`
  - `load_previous_drift_mode`
  - `compute_drift_alert_mode`
  - `write_drift_controller_state`
- Calls `core.fuse.normalize_episodes_schema`
- Returns `DriftPostprocessStageResult`

12. `core.output_manager.OutputManager.prepare_persistence_inputs`
- Calls `update_baseline_buffer`
- Calls `build_sensor_analytics_context`
- Returns `PersistenceInputPreparationResult`

13. `core.output_manager.OutputManager.run_persistence_stage`
- Calls `persist_pipeline_outputs`
- Calls `core.output_artifacts.write_sql_artifacts`
- Returns `PersistenceStageResult`

14. `core.run_metadata_writer.resolve_run_outcome_from_degradations`
- Maps degradation list to final outcome and optional `err_json`

15. `core.run_metadata_writer.finalize_pipeline_teardown`
- Calls `emit_batch_summary`
- Calls `finalize_run_with_metadata`
- `finalize_run_with_metadata` calls:
  - `extract_run_metadata_from_scores`
  - `extract_data_quality_score`
  - `write_run_metadata`
  - `sql_client.finalize_run`
  - `output_manager.close`
  - `sql_client.close`
- Calls `close_run_span`
- Calls `shutdown_run_observability`

## 8. Non-Linear Early Exit Paths

1. Coldstart deferred or no scoring data:
- `load_and_validate_data_stage` finalizes run through `finalize_noop_run`
- orchestrator returns with `outcome=NOOP`
- teardown still runs from `finally`

2. Unhandled exception in any core stage:
- orchestrator sets `outcome=FAIL`
- orchestrator calls `serialize_run_exception`
- exception re-raised for caller visibility
- teardown still executes

## 9. Reliability and Data Issues Already Mitigated

The following issues are handled in current implementation:

1. SQL startup fragility
- Mitigated by fail-fast connect and explicit health probe.

2. Config drift between files and SQL
- Mitigated by SQL-first config load from `ACM_Config` and config signature handling.

3. Coldstart dead-end behavior
- Mitigated by staged coldstart retry and deterministic NOOP finalize path.

4. Data leakage in feature fill values
- Mitigated by deriving score fill values from train distribution.

5. Timestamp duplication artifacts
- Mitigated by index normalization and deduplication before feature and scoring stages.

6. Feature-shape mismatch with cached models
- Mitigated by manifest-protected columns and cache compatibility alignment.

7. Calibration inconsistency across runs
- Mitigated by persisted calibration parameters and reuse path.

8. Regime write fragility
- Mitigated by explicit regime occupancy/transition persistence calls and postprocess stage.

9. Drift hysteresis continuity gap
- Mitigated by loading previous drift mode before drift-mode computation.

10. Run-finalize loss risk
- Mitigated by centralized teardown that always attempts metadata write, SQL finalize, and resource close.

## 10. What Remains Difficult

1. Unsupervised contamination is not fully solvable by code structure alone.
2. Destination module complexity is still high in:
- `core/output_manager.py`
- `core/output_artifacts.py`
- `core/regimes.py`
- `core/fuse.py`
3. Optional-path error policy still needs careful hardening without breaking ops observability.
4. Forecast layer remains disabled in orchestrator, so long-horizon prognostics are not active.

## 11. SQL and Configuration Model

### 11.1 Runtime config source
- `ACM_Config`

### 11.2 Config seed and sync
- Script: `scripts/sql/populate_acm_config.py`
- Seed file: `configs/config_table.csv`

### 11.3 SQL connection source
- File: `configs/sql_connection.ini` (gitignored)

### 11.4 Run lifecycle boundaries
1. Run start registered at bootstrap stage.
2. Run status finalized during teardown stage.

## 12. Core Data Outputs

At minimum, normal runs persist:
1. Detector scores and fused signals.
2. Episode records and culprit context.
3. Regime labels and regime analytics.
4. Data quality diagnostics.
5. Run metadata and closure state.

Key operational tables include:
- `ACM_Runs`
- `ACM_Scores_Wide`
- `ACM_Episodes` and or `ACM_Anomaly_Events`
- `ACM_HealthTimeline`
- `ACM_RegimeTimeline`
- `ACM_DataQuality`
- `ACM_RunMetadata`

Forecast note:
- Forecast-related schema may exist in SQL and output layers.
- Active orchestrator path currently logs forecast as disabled.

## 13. Observability Model

Orchestrator integration points:
1. Startup: `init_run_observability`
2. Span: `start_run_span`
3. Stage-level metrics and logs
4. Teardown: `close_run_span`, `shutdown_run_observability`

Typical local stack:
- Grafana: 3000
- Loki: 3100
- Tempo: 3200
- Prometheus: 9090
- Pyroscope: 4040

## 14. Validation and Safety Checklist

Use this after structural changes:

```powershell
python -m py_compile core/acm.py
python -m core.acm --help
python -c "from core.acm import main; print(callable(main))"
pytest tests/test_v11_modules.py -v
python scripts/sql_batch_runner.py --equip FD_FAN --dry-run
```

For parity-sensitive changes compare:
1. outcome
2. rows_read
3. rows_written
4. episode count
5. drift mode
6. regime quality status
7. run finalization success

## 15. Troubleshooting

### 15.1 SQL startup failure
1. Validate `configs/sql_connection.ini`.
2. Validate SQL service availability and credentials.

### 15.2 Frequent NOOP
1. Verify historian coverage.
2. Verify coldstart minimum data criteria.

### 15.3 Unexpected retrain or degradation behavior
1. Inspect cache compatibility and model adaptation logs.
2. Inspect regime quality and drift outputs.
3. Inspect data quality score path and metadata rows.

### 15.4 Dashboard mismatch
1. Verify dashboards target active tables and field names.
2. Verify Grafana panel options and palettes are valid for installed version.

## 16. Code Navigation Quick Map

Runtime files to read first:
- `core/acm.py`
- `core/sql_client.py`
- `core/smart_coldstart.py`
- `core/fast_features.py`
- `core/detector_orchestrator.py`
- `core/regimes.py`
- `core/fuse.py`
- `core/drift.py`
- `core/output_manager.py`
- `core/output_artifacts.py`
- `core/run_metadata_writer.py`

Related planning docs:
- `docs/ACM_SINGLE_ENTRYPOINT_REFACTOR_MASTER_PLAN.md`
- `docs/OUTPUT_MANAGER_REFACTOR_MASTER_PLAN.md`
- `docs/ACM Main Refactoring Analysis - Action.md`

---

This overview is intentionally aligned to active runtime code and refactor direction, not historical architecture snapshots.

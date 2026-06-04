# ACM - Automated Condition Monitoring

Version: `11.15.15`
Version date: `2026-03-08`
Last README update: `2026-06-04`
Canonical changelog: `docs/CHANGELOG.md`
Operational entrypoint: `python -m core.acm`

ACM is a SQL-first condition monitoring system for industrial equipment. It ingests historian data from SQL tables, builds robust feature frames, scores a multi-detector anomaly ensemble, applies regime-aware calibration and fusion, detects episodes, computes drift behavior, and persists analytics plus run metadata back to SQL.

This README is the quick operational map. Detailed architecture lives in `docs/ACM_SYSTEM_OVERVIEW.md`. Version history lives in `docs/CHANGELOG.md`. Database schema reference lives in `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md`.

## Table of Contents

1. Runtime Truth
2. What ACM Solves
3. System Architecture
4. Core Runtime Ownership
5. Active Pipeline Sequence
6. Detector and Scoring Model
7. SQL and Configuration Model
8. Running ACM
9. Validation Checklist
10. Agent and AI Workflow
11. Troubleshooting
12. Documentation Map

## 1. Runtime Truth

Current runtime facts for this repository:

1. Supported operational command is `python -m core.acm`.
2. `core/acm.py` is the active top-level orchestrator.
3. `core/acm_main.py` is not part of the active runtime path.
4. `scripts/sql_batch_runner.py` invokes `core.acm` for batch execution.
5. Runtime configuration source of truth is SQL table `ACM_Config`.
6. Forecast and RUL execution are currently disabled in the active orchestrator flow.
7. SQL run lifecycle is strict: run start and run finalization are both required.
8. Valid run outcomes are `OK`, `DEGRADED`, `NOOP`, and `FAIL`.

When documents conflict, prefer this order:

1. Active code in `core/acm.py` and direct owner modules.
2. `docs/ACM_SYSTEM_OVERVIEW.md`.
3. `docs/CHANGELOG.md` and `utils/version.py`.
4. Generated agent memory under `skills/acm-codebase-memory/references/`.
5. Archived docs only for historical context.

## 2. What ACM Solves

Industrial maintenance sits between reactive failure response and preventive over-maintenance. ACM supports predictive maintenance by answering these questions each run:

1. Is current behavior abnormal?
2. Is the abnormality transient or sustained?
3. Is this a regime shift or a degradation signal?
4. How severe is current condition in operational terms?
5. Did the run complete cleanly, degrade safely, noop intentionally, or fail?

ACM is difficult because it combines unsupervised time-series modeling, noisy historian data, SQL lifecycle correctness, model persistence, regime context, dashboard compatibility, and observability.

## 3. System Architecture

```text
+------------------------+
| Historian and SQL      |
| raw data + config      |
+------------------------+
           |
           v
+------------------------+
| ACM Runtime            |
| python -m core.acm     |
| stage orchestrator     |
+------------------------+
           |
           v
+------------------------+
| SQL Outputs            |
| scores episodes runs   |
| health regime quality  |
+------------------------+
           |
           v
+------------------------+
| Observability Stack    |
| Grafana Loki Tempo     |
| Prometheus Pyroscope   |
+------------------------+
```

Technology stack:

| Layer | Technology | Purpose |
| --- | --- | --- |
| Runtime | Python 3.11 | Pipeline orchestration and model execution |
| Data processing | pandas, NumPy, scikit-learn | Features, detectors, calibration, fusion |
| Database | SQL Server | Historian source and output persistence |
| SQL connectivity | pyodbc, T-SQL | Runtime read and write operations |
| Visualization | Grafana | Operational dashboards |
| Observability | OpenTelemetry stack | Logs, traces, metrics, profiling |

## 4. Core Runtime Ownership

Read these files first for runtime work:

| Area | Owner file | Responsibility |
| --- | --- | --- |
| Top-level orchestration | `core/acm.py` | CLI, stage ordering, outcome coordination, teardown |
| SQL bootstrap | `core/sql_client.py` | SQL connection, config load, run start, runtime policy |
| Data load and coldstart | `core/smart_coldstart.py` | Historian load, coldstart/noop handling, retry path |
| Data contracts | `core/pipeline_types.py` | Entry validation and guardrails |
| Feature preparation | `core/fast_features.py` | Index hygiene, feature engineering, imputation |
| Detector orchestration | `core/detector_orchestrator.py` | Detector load, fit, score, calibration helpers |
| Regime modeling | `core/regimes.py` | Regime basis, labeling, occupancy, transitions |
| Model lifecycle | `core/model_persistence.py` | Adaptation, retrain, active model persistence |
| Health and fusion | `core/fuse.py` | Calibration, fusion, episodes, adaptive thresholds |
| Drift | `core/drift.py` | Drift computation and controller state |
| Output persistence | `core/output_manager.py` | SQL persistence stage and analytics writes |
| Finalization | `core/run_metadata_writer.py` | Outcome mapping, metadata, teardown finalization |
| Observability | `core/observability.py` | Logs, traces, metrics, profiling hooks |

## 5. Active Pipeline Sequence

Current `core.acm` execution order:

1. Initialize run observability.
2. Connect to SQL fail-fast.
3. Bootstrap ACM run state.
4. Resolve runtime policy.
5. Load and validate data.
6. Seed baseline when needed.
7. Prepare features and run guardrails.
8. Initialize, load, or fit detectors.
9. Score detectors and label regimes.
10. Run model adaptation and persistence.
11. Run calibration, fusion, health, episodes, and threshold updates.
12. Run drift postprocess.
13. Prepare persistence inputs.
14. Persist SQL outputs and analytics.
15. Resolve final run outcome.
16. Finalize run metadata, SQL lifecycle, resources, spans, and observability.

Early-exit and failure behavior:

1. Coldstart-deferred or no-data paths finalize as `NOOP`.
2. Unexpected stage exceptions mark the run as `FAIL`.
3. Teardown still runs from `finally` so SQL lifecycle closure is attempted.
4. Partial optional-output failures should degrade safely when designed to do so.

## 6. Detector and Scoring Model

ACM uses multiple detector families because no single detector covers all industrial fault shapes.

| Detector | Signal | Typical strength |
| --- | --- | --- |
| AR1 | Local temporal residual change | Abrupt univariate shifts |
| PCA SPE | Off-subspace novelty | Structure-level deviations |
| PCA T2 | Latent-space extremity | Extreme latent movement |
| Isolation Forest | Sparse outlier isolation | High-dimensional sparse anomalies |
| GMM | Low likelihood under mixture density | Multimodal healthy distributions |
| OMR | Inter-sensor relationship break | Dependency failures between sensors |

Core scoring path:

1. Generate detector raw scores.
2. Calibrate detector scores into comparable z-space.
3. Fuse calibrated evidence into a unified anomaly intensity.
4. Interpret fused behavior into health, episodes, drift, confidence, and operational outputs.

Regime modeling is context, not anomaly truth:

```text
Regime modeling answers: how is the machine operating?
Detector scoring answers: how abnormal is behavior in that context?
```

## 7. SQL and Configuration Model

Runtime configuration:

1. SQL table: `ACM_Config`.
2. Seed file: `configs/config_table.csv`.
3. Config seeder: `scripts/sql/populate_acm_config.py`.
4. SQL connection file: `configs/sql_connection.ini`.
5. SQL connection file is local-only and should remain gitignored.

Core output categories:

1. Detector scores and fused signals.
2. Episode records and culprit context.
3. Regime labels and regime analytics.
4. Data quality diagnostics.
5. Run metadata and closure state.
6. Model lifecycle and calibration state.

Important operational tables include:

- `ACM_Runs`
- `ACM_Scores_Wide`
- `ACM_Episodes`
- `ACM_Anomaly_Events`
- `ACM_HealthTimeline`
- `ACM_RegimeTimeline`
- `ACM_DataQuality`
- `ACM_RunMetadata`
- `ACM_ActiveModels`
- `ACM_Config`
- `ModelRegistry`

Use `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md` for table details, column definitions, row counts, and schema review.

## 8. Running ACM

Production-like batch mode:

```powershell
python scripts/sql_batch_runner.py --equip FD_FAN GAS_TURBINE --max-workers 2 --resume
```

Single run mode:

```powershell
python -m core.acm --equip FD_FAN --start-time "2024-01-01T00:00:00" --end-time "2024-01-02T00:00:00"
```

Help and CLI inspection:

```powershell
python -m core.acm --help
```

Supported CLI options include:

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

Note: `--log-file` is ignored by the active runtime. ACM writes logs to SQL and the observability stack.

## 9. Validation Checklist

Use this after structural or behavior-sensitive changes:

```powershell
python -m py_compile core/acm.py
python -m core.acm --help
python -c "from core.acm import main; print(callable(main))"
pytest tests/test_v11_modules.py -v
python scripts/sql_batch_runner.py --equip FD_FAN --dry-run
```

For refactors, compare these before accepting the change:

1. Final outcome.
2. Rows read.
3. Rows written.
4. Episode count.
5. Drift mode.
6. Regime quality status.
7. Run finalization success.
8. Affected SQL tables.
9. Grafana/dashboard compatibility where relevant.

## 10. Agent and AI Workflow

This repository already contains agent-facing context.

Required agent entrypoints:

1. `AGENTS.md`.
2. `skills/acm-codebase-memory/SKILL.md`.
3. `skills/acm-codebase-memory/references/00_Agent-Memory-Hub.md`.
4. `skills/acm-codebase-memory/references/01_Runtime-Critical-Path.md`.
5. `skills/acm-codebase-memory/references/02_Module-Ownership.md`.
6. `skills/acm-codebase-memory/references/03_SQL-Output-Map.md`.

Before major changes, refresh and check memory:

```powershell
python scripts/manage_acm_agent_memory.py refresh --sync-repo-skill --sync-local-skill
python scripts/manage_acm_agent_memory.py health
```

Agent rules for ACM work:

1. Read runtime-critical memory before planning.
2. Treat `python -m core.acm` as the active runtime path.
3. Do not revive `core/acm_main.py` as the active orchestrator.
4. Inspect owner modules before editing.
5. Avoid blind patch scripts for behavioral changes.
6. Keep SQL lifecycle and finalization semantics stable.
7. Update tests or validation notes for behavior-sensitive changes.
8. Record diff, commands run, verification result, and remaining risk.

## 11. Troubleshooting

### SQL startup failures

1. Validate `configs/sql_connection.ini`.
2. Validate SQL Server reachability and credentials.
3. Confirm `pyodbc` driver availability.
4. Run `python -m core.acm --help` to separate CLI/import issues from SQL runtime issues.

### Unexpected NOOP outcomes

1. Validate historian coverage for the selected window.
2. Check coldstart minimum-data thresholds.
3. Inspect `ACM_ColdstartState` and batch-runner precheck behavior.
4. Confirm the selected equipment exists in SQL metadata.

### Unstable adaptation or retrain behavior

1. Inspect model cache compatibility logs.
2. Inspect regime quality and drift outputs.
3. Inspect `ACM_ActiveModels`, `ModelRegistry`, and run metadata.
4. Check `ACM_Config` values against `configs/config_table.csv`.

### Dashboard mismatch

1. Verify dashboard queries target active table and field names.
2. Verify selected equipment and time range contain rows.
3. Verify Grafana panel options are valid for the installed version.
4. Use `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md` as the schema reference.

## 12. Documentation Map

Current primary references:

- `docs/CHANGELOG.md` - version history and change rationale.
- `docs/ACM_SYSTEM_OVERVIEW.md` - active architecture and runtime sequence.
- `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md` - SQL schema reference.
- `docs/SOURCE_CONTROL_PRACTICES.md` - source control and release practices.
- `AGENTS.md` - agent skill discovery and usage rule.
- `skills/acm-codebase-memory/SKILL.md` - repository-specific agent memory workflow.

Historical or archived docs may exist under `docs/archive/`. Use them only as historical context unless they are explicitly promoted back into active documentation.

---

This README intentionally keeps release history in `docs/CHANGELOG.md`, keeps schema details in `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md`, and keeps active runtime truth aligned to `core/acm.py`.

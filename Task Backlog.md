# ACM V8 Unified Backlog & Issue Tracker

**Last Updated:** 2025-11-16  
**Scope:** SQL Mode rollout, Forecast/RUL roadmap, charting/documentation polish, and technical debt items carried over from the prior To-Do documents.

---

## Why this document?

`Task Backlog.md` now replaces the old `Task Backlog.md`. The two lists diverged and became hard to maintain, so they have been consolidated here. All day-to-day work should now be tracked in **GitHub Issues** instead of ad-hoc markdown tables. This file summarizes the active workstreams, how to label issues, and what is still genuinely outstanding after auditing the old backlog entries.

---

## Issue-Based Workflow

1. **Open a GitHub issue** for every piece of work. Use the naming convention `AREA-ID: short description` (e.g., `SQL-12: Complete dual-write run matrix`).
2. **Apply labels** so filtering by workstream is easy. Suggested labels: `SQL`, `Forecast`, `RUL`, `Charts`, `Docs`, `TechDebt`, and priority labels (`P0`, `P1`, `P2`).
3. **Cross-reference this file** from the issue description so the original context is preserved.
4. **Close issues** via pull requests. Avoid adding new TODO tables in markdown?use Issues/Projects for status tracking.

> ? The old `Task Backlog.md` file has been removed. If you come across references to it, update them to point here or directly to the GitHub Issues board.

---

## Workstream Summary (What is truly remaining)

The sections below list the still-open themes from the merged backlogs. Each bullet either already has an associated issue or needs one created.

### 1. SQL Integration (Phase 1 and Model Persistence)
- **SQL-12**  Finish the remaining 6/10 dual-write validation runs and capture the results in SQL tables.
- **SQL-13**  Build `validate_dual_write.py` to compare CSV vs SQL outputs automatically.
- **SQL-14**  Row-count/value parity checks between file and SQL storage.
- **SQL-15**  Baseline SQL write performance (<15 s target, capture stats in Run Logs).
- **SQL-20/21/22/23**  Save/load detectors to ModelRegistry and wire them into the training pipeline.

### 2. Forecast & RUL
- **FCST-15**  Remove the `scores.csv` dependency so forecasting works in SQL-only runs.
- **FCST-16**  Publish per-sensor/regime forecasts into `ACM_SensorForecast_TS` with diagnostics.
- **RUL-01**  Make `rul_estimator.py` consume SQL health timelines instead of CSVs.
- **RUL-02**  Add probabilistic RUL bands and maintenance telemetry to the SQL outputs.
- *(FCST-17, RUL-03, SQL-57, etc., were completed or superseded and do not need new issues.)*

### 3. Charting & Documentation
- **CHART-19**  Build `scripts/validate_charts.py` (chart smoke tests).
- **CHART-20**  Refresh chart documentation/quick-reference guides.
- All older chart tasks that were already done (CHART-03/04/13/15/16/17/18, OUT-24, etc.) remain marked completed.

### 4. Technical Debt & Ops
- **DEBT-07**  Tighten error handling around detector training and SQL IO.
- **DEBT-14/15**  Improve test hooks/path handling in `core/acm_main.py` and ensure error truncation captures full stacks.
- **OPS** tasks (scheduler integration, alerting, deployment runbooks) still need issues opened as we prepare for automation in SQL-only mode.

---

## Issue Migration Checklist

Use the following mapping when opening/triaging GitHub issues. Strike through entries if they are already covered by an existing issue or PR.

| Legacy ID | Area | Status | Action |
| --------- | ---- | ------ | ------ |
| SQL-12 | SQL Integration | Planned | Create/maintain issue covering the remaining dual-write validation matrix. |
| SQL-13 | SQL Integration | Planned | Issue for the CSV vs SQL comparison tool. |
| SQL-14 | SQL Integration | Planned | Issue for parity validation automation. |
| SQL-15 | SQL Integration | Planned | Issue for benchmarking SQL write times. |
| SQL-20/21/22/23 | Model Persistence | Planned | Either one umbrella issue or separate ones for save/load + integration + testing. |
| FCST-15/16 | Forecast | Planned | Two issues tracking SQL-only forecast support and sensor forecasts. |
| RUL-01/02 | RUL | Planned | Two issues covering SQL ingestion + probabilistic outputs. |
| CHART-19/20 | Charts/Docs | Planned | Open documentation + tooling issues. |
| DEBT-07/14/15 | Tech Debt | Planned | Create issues for structured error handling and test hooks. |

All other historical tasks were either completed (already struck through in previous versions) or removed because they duplicated the finished logging/chart work. If you discover a missing item while working through the code, open an issue instead of reintroducing a markdown TODO.

---

## Historical Context

- The previous `Task Backlog.md` and `Task Backlog.md` documents were audited on 2025-11-16. Duplicates were removed, chart/CSV-only tasks were archived, and completed logging upgrades were marked done.
- `CHART-03/04/13/15/16/17/18`, OUT-03/05/20/21/24/26/27/28, DEBT-04, CFG-07, SQL-57, and all logging upgrades are confirmed complete.
- SQL Run Logs, module-level logging overrides, and CLI logging flags now ship, so DEBT-16/17 are closed.

For everything else, the single source of truth is now **GitHub Issues**. This document will be updated only when the set of workstreams changes (e.g., adding a new audit area or closing a pillar entirely).

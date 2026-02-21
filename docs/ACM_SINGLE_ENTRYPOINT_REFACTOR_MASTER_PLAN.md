# ACM Single Entrypoint Refactor Master Plan

Date: 2026-02-20  
Owner: Snehil  
Status: Active execution on integration branch

---

## 0. Execution Progress Log

Updated: 2026-02-21

Current snapshot:

1. Runtime entrypoint migration is complete:
   - `core/acm_main.py` is removed.
   - `python -m core.acm` is the only runtime entrypoint.
2. `core/acm.py` is shrinking:
   - recent high watermark in this effort: 1758 lines
   - current: 1237 lines
3. Extracted and wired into ownership modules:
   - calibration and fusion orchestration pieces in `core/fuse.py`
   - NOOP outcome/error/finalization helpers in `core/run_metadata_writer.py`
   - persist-stage orchestration helpers in `core/output_manager.py`
   - regime labeling stage orchestration in `core/regimes.py`
   - data-load stage orchestration in `core/smart_coldstart.py`
   - early manifest-protection lookup in `core/model_persistence.py`
   - detector runtime initialization orchestration in `core/detector_orchestrator.py`
   - regime basis build and compatibility gating in `core/regimes.py`
   - auto-retrain stage orchestration in `core/model_evaluation.py`
   - model persistence and lifecycle stage orchestration in `core/model_persistence.py`
   - consolidated teardown orchestration in `core/run_metadata_writer.py`
4. Tests were updated throughout extraction:
   - `tests/test_v11_modules.py` currently passes with new helper coverage.
5. Source control policy has been followed:
   - all work through `refactor/*` branches merged into `integration/acm-single-entrypoint`
   - `main` remains untouched.

Progress interpretation:

1. Entrypoint unification and runtime cutover are done.
2. Monolith extraction is in progress and moving in the right direction.
3. The orchestrator is lighter than before but still too large for final target.

Remaining structural backlog:

1. Additional cleanup is needed to reduce nested conditional and exception handling in orchestrator path.
2. Orchestrator still carries local state plumbing that can be collapsed into stage payloads.
3. Startup and run-context initialization path can be further decomposed into ownership helpers.

Validation executed after each extraction slice:

1. `python -m py_compile` on touched modules.
2. `pytest tests/test_v11_modules.py -q`.
3. `python scripts/sql_batch_runner.py --equip FD_FAN --dry-run --max-batches 1`.

Notes:

1. `main` branch remains untouched.
2. Work continues only through phase branches merged into `integration/acm-single-entrypoint`.

---

## 1. Objective

Migrate the ACM runtime to a **single supported entrypoint**:

- Supported entrypoint: `python -m core.acm`
- Unsupported for direct execution: `python -m core.acm_main`

This migration must preserve existing pipeline behavior while the refactor is in progress.

---

## 2. Hard Requirements (Non-Negotiable)

1. No loss of runtime behavior:
   - same outcome semantics: `OK`, `DEGRADED`, `NOOP`, `FAIL`
   - same SQL run lifecycle behavior
   - same data/model/fusion/drift logic
2. Pipeline remains runnable at the end of every phase.
3. `scripts/sql_batch_runner.py` and operator runbooks must continue to work.
4. Mid-refactor states must be safe and reversible.
5. No destructive schema changes as part of this refactor.

---

## 3. Current State Summary

1. `core/acm.py` is the canonical runtime command surface and currently contains full SQL pipeline orchestration (large monolith).
2. `core/acm_main.py` has been decommissioned from runtime and removed from active execution paths.
3. `scripts/sql_batch_runner.py` invokes `python -m core.acm`.
4. Remaining `core.acm_main` references are historical/decommission references in planning docs only.

---

## 4. Target End State

1. `core/acm.py`:
   - single operational entrypoint
   - owns CLI parser and top-level orchestration call
2. `core/acm_main.py`:
   - removed permanently after migration completion
3. All production and automation invocations use:
   - `python -m core.acm ...`

---

## 5. Scope and Out-of-Scope

### In Scope

1. Entrypoint unification (`acm` only).
2. Gradual orchestration migration from `acm_main` to `acm`.
3. Compatibility updates in automation and active docs.
4. Stability and parity validation.

### Out of Scope

1. Algorithm redesign (detectors/regime/fusion/drift logic changes).
2. SQL schema redesign.
3. Forecasting feature re-enable (currently disabled).

---

## 6. Refactor Strategy: Strangler Pattern with Safe Intermediate States

Use an incremental strangler approach:

1. Keep existing core logic callable.
2. Move one boundary at a time.
3. Keep one stable entry command throughout migration (`core.acm`).
4. Verify parity after each extraction.

Each phase has:
- code moves
- explicit acceptance tests
- rollback instructions

---

## 7. Behavior Invariants (Must Stay True Through Every PR)

### 7.1 Run Lifecycle Invariants

1. A run started in SQL must always be finalized once.
2. `NOOP` finalization must still occur for no-data/coldstart-deferred paths.
3. Failure paths must still set `outcome=FAIL` and preserve error payload behavior.

### 7.2 Data and Model Invariants

1. DataContract validation behavior unchanged.
2. Detector enable/disable reconciliation unchanged.
3. Cache validation and retrain trigger conditions unchanged.
4. Regime state persistence behavior unchanged.

### 7.3 Output Invariants

1. Core writes stay present: scores, episodes, metadata, finalization.
2. `rows_read`/`rows_written` semantics unchanged.
3. Observability emission order remains compatible.

---

## 8. Implementation Phases

Execution status (current):
- Phase 1 completed.
- Phase 2 completed.
- Phase 3 completed.
- Phase 4 in progress.
- Phase 5 completed for operational usage.
- Phase 6 completed for runtime decommission (`core/acm_main.py` removed).

Phase 4 extraction highlights:
  - `classify_noop_reason` moved to `core/smart_coldstart.py`.
  - pipeline feature-build wrapper moved to `core/fast_features.py`.
  - SQL/config/run-start helpers moved to `core/sql_client.py`:
    - `connect_acm_sql`
    - `resolve_equipment_id_required`
    - `load_config_required_from_sql`
    - `start_acm_run`
  - regime occupancy/transition write block moved to `core/regimes.py`:
    - `write_regime_occupancy_and_transitions`
  - regime definitions audit write block moved to `core/regimes.py`:
    - `write_regime_definitions_for_audit`
  - drift helper blocks moved to `core/drift.py`:
    - `load_previous_drift_mode`
    - `build_drift_controller_state`
  - calibration payload row-builders moved to `core/fuse.py`:
    - `build_per_regime_threshold_rows`
    - `build_threshold_rows`
    - `build_calibration_summary_rows`
  - calibration orchestration helper internals moved to `core/fuse.py`:
    - `apply_contamination_filter_config`
    - `choose_pca_cache_for_calibration`
    - `compute_and_set_adaptive_clip`
    - `compute_pca_train_percentiles`
    - `collect_enabled_calibrators`
    - `write_calibration_summary_safe`
  - persistence optional artifact wrappers moved to `core/output_manager.py`:
    - `write_detector_correlation_from_scores`
    - `write_sensor_correlations_from_raw`
    - `write_sensor_normalized_ts_from_raw`
    - `write_seasonal_patterns_from_detected`
  - sensor analytics context builder moved to `core/sensor_attribution.py`:
    - `build_sensor_analytics_context`
  - contribution timeline persistence moved to `core/sensor_attribution.py`:
    - `persist_contribution_timeline`
  - consolidated batch summary emission moved to `core/run_metadata_writer.py`:
    - `emit_batch_summary`
  - SQL finalization/metadata block moved to `core/run_metadata_writer.py`:
    - `finalize_run_with_metadata`
  - run metadata writer hardened:
    - fixed `write_retrain_metadata` boundary so summary logging does not execute retrain SQL payload logic
    - made `extract_data_quality_score` SQL-only and removed CSV fallback remnants
  - finalization state made explicit in `core/acm.py`:
    - removed `locals()` guard branches from summary/finalize calls
  - observability finalize helpers moved out of `core/acm.py`:
    - `close_run_span` in `core/observability.py`
    - `shutdown_run_observability` in `core/observability.py`
  - model force-retrain policy extracted from `core/acm.py` to `core/model_evaluation.py`:
    - `evaluate_force_retrain_triggers`
  - detector runtime initialization extracted from `core/acm.py` to `core/detector_orchestrator.py`:
    - `initialize_detectors_for_run`
    - includes cache load path, runtime cache restore path, fit-when-missing path, flag reconcile, and required-detector validation
  - regime basis stage extracted from `core/acm.py` to `core/regimes.py`:
    - `build_regime_feature_basis_stage`
    - includes basis hash construction, degraded fallback, and cached regime feature-compatibility reset
  - auto-retrain stage extracted from `core/acm.py` to `core/model_evaluation.py`:
    - `run_auto_retrain_stage`
    - applies retrain outputs back to detector bundle after trigger evaluation
  - model save and lifecycle stage extracted from `core/acm.py` to `core/model_persistence.py`:
    - `run_model_persistence_and_lifecycle_stage`
    - owns trained-versus-scoring persistence branch and lifecycle fallback load
  - final teardown stage extracted from `core/acm.py` to `core/run_metadata_writer.py`:
    - `finalize_pipeline_teardown`
    - consolidates summary emit, SQL finalization, span close, and observability shutdown calls
  - run invocation compatibility path simplified in `core/acm.py`:
    - removed argv reconstruction adapter and switched `run_pipeline(args)` to direct `main(args)` execution
  - removed unused legacy context dataclasses and enum from `core/acm.py`.
  - Remaining work is structural extraction of monolith responsibilities from `core/acm.py` into ownership modules with parity checks.

Immediate next extraction queue:

1. Collapse remaining orchestration state plumbing in `core/acm.py` into stage payload outputs.
2. Extract startup and runtime-context initialization path into ownership helpers where applicable.
3. Continue until `core/acm.py` is primarily high-level stage calls and run-level control flow only.

## Phase 0 - Baseline and Safety Harness

### Goal
Capture objective parity baselines before moving entrypoint/orchestration.

### Actions

1. Capture one coldstart-ish run and one regular scoring run.
2. Save baseline fields:
   - run outcome
   - rows read/written
   - episode count
   - regime quality flag
   - drift mode
   - finalization success
3. Save representative logs for startup + finalize sections.

### Acceptance

Baseline artifacts are available for side-by-side comparison in all later phases.

### Rollback

None needed (no behavior edits).

---

## Phase 1 - Establish `core.acm` as Canonical Entrypoint

### Goal
Make `core.acm` the official execution command without changing pipeline internals.

### Code Changes

1. `core/acm.py`
   - remove duplicate parser layer behavior that can drift from `acm_main`.
   - call internal pipeline entry directly.
2. `scripts/sql_batch_runner.py`
   - switch subprocess call from `core.acm_main` to `core.acm`.
3. Update active docs commands (`docs/` non-archive) to `core.acm`.

### Acceptance

1. `python -m core.acm --equip <EQUIP>` works.
2. batch runner invokes `core.acm` correctly.
3. parity metrics match baseline.

### Rollback

Revert caller switch in batch runner and entry wrapper changes.

---

## Phase 2 - Introduce Internal Callable API in `acm_main`

### Goal
Prepare orchestration migration by separating parser from execution.

### Code Changes

1. In `core/acm_main.py`, define explicit internal callable:
   - `run_pipeline(args: argparse.Namespace) -> int` (or equivalent)
2. Keep existing behavior by making current `main()` a thin wrapper around that callable.
3. `core/acm.py` becomes owner of parser and passes parsed args into internal callable.

### Acceptance

1. Parser behavior exposed by `core.acm` matches previous supported CLI.
2. Pipeline behavior parity remains intact.

### Rollback

Restore `acm.py` delegation to old `acm_main.main()` behavior.

---

## Phase 3 - Move Startup/Bootstrap Ownership to `acm.py`

### Goal
Shift top-level orchestration boundaries to `acm.py` while keeping heavy logic internal.

### Code Changes

1. Move argument parser construction to `acm.py`.
2. Keep bootstrap helpers internal but called via stable API.
3. Ensure only `acm.py` is referenced in operational scripts/docs.

### Acceptance

1. Startup logs and config signature behavior unchanged.
2. SQL connection failure behavior unchanged.

### Rollback

Move bootstrap calls back behind `acm_main.main()` wrapper.

---

## Phase 4 - Gradual Extraction of Monolith Blocks (Function-Owned Placement)

### Goal
Reduce `acm_main.py` complexity without introducing stage-package churn.

### Placement Rule

Move code to **existing ownership modules first**:

1. SQL run lifecycle and lookup helpers -> `core/sql_client.py`
2. data loading/coldstart utilities -> `core/smart_coldstart.py` / `core/data_loader.py`
3. feature building/imputation wrappers -> `core/fast_features.py`
4. model orchestration wrappers -> `core/detector_orchestrator.py`
5. regime derived payload helpers -> `core/regimes.py`
6. calibration/threshold table builders -> `core/fuse.py`
7. drift state assembly helpers -> `core/drift.py`
8. persistence write wrappers -> `core/output_manager.py`
9. run summary metadata extraction -> `core/run_metadata_writer.py`

### Acceptance

1. No policy/algorithm changes introduced.
2. Each extraction PR passes parity checks.

### Rollback

Revert only the latest extracted function group.

---

## Phase 5 - Finalize Single Entrypoint Enforcement (Temporary Compatibility)

### Goal
Ensure no operational path relies on direct `core.acm_main` execution.

### Code Changes

1. `core/acm_main.py`:
   - optional temporary compatibility shim only
   - not a supported operational entry
2. Verify all automation uses `core.acm`.

### Acceptance

1. `core.acm` is sole supported operational entrypoint.
2. No production script invokes `core.acm_main`.

### Rollback

Temporarily restore compatibility shim while issues are fixed.

---

## Phase 6 - Permanent `acm_main` Decommission

### Goal
Remove `core/acm_main.py` entirely once all callers and integrations are migrated.

### Preconditions

1. No active script invokes `python -m core.acm_main`.
2. No non-archive docs instruct `core.acm_main` usage.
3. Batch runner and operator flows are stable on `core.acm`.
4. Parity checks pass for at least one coldstart-like run and one scoring run.

### Code Changes

1. Move any remaining required internals from `acm_main.py` into owned modules or `core/acm.py`.
2. Delete `core/acm_main.py`.
3. Run repository-wide search to ensure no runtime imports reference `core.acm_main`.

### Acceptance

1. `core/acm_main.py` no longer exists.
2. `python -m core.acm` is fully functional and sole runtime entrypoint.
3. Tests and operational checks pass unchanged.

### Rollback

Restore `core/acm_main.py` from previous commit and re-enable temporary shim only if needed.

---

## 9. Detailed Migration Map (`acm.py` to Ownership Modules)

This map describes where major current blocks should migrate as helper functions.

| Current concern in `acm.py` | Target module | Notes |
|---|---|---|
| Equipment/config SQL lookup helpers | `core/sql_client.py` | Keep SQL-only semantics |
| NOOP reason classification + load retry wiring | `core/smart_coldstart.py` | Maintain current priority rules |
| Feature construction wrapper | `core/fast_features.py` | Keep fill-from-train leakage guard |
| Detector fit/load/reconcile orchestration wrappers | `core/detector_orchestrator.py` | Keep existing flag reconciliation behavior |
| Regime occupancy/transition payload assembly | `core/regimes.py` | Keep write payload format stable |
| Calibration threshold row assembly | `core/fuse.py` | Keep global/per-regime behavior |
| Drift previous mode + controller payload | `core/drift.py` | Preserve hysteresis path |
| Correlation/seasonal/sensor TS write wrappers | `core/output_manager.py` | Keep SQL write order stable |
| Run summary metadata extraction | `core/run_metadata_writer.py` | Keep final health status logic |

---

## 10. Validation Matrix (Run at Every Phase)

## 10.1 Fast Checks

1. `pytest tests/test_v11_modules.py -v`
2. import smoke:
   - `python -c "from core.acm import main; print(callable(main))"`

## 10.2 Runtime Checks

1. Single run:
   - `python -m core.acm --equip <EQUIP> --start-time <T1> --end-time <T2>`
2. Batch runner plumbing:
   - `python scripts/sql_batch_runner.py --equip <EQUIP> --dry-run`

## 10.3 Parity Checks Against Baseline

Compare:
1. Outcome
2. rows_read
3. rows_written
4. episode count
5. final drift mode
6. regime quality status
7. run finalization success

Fail any check => stop next phase.

---

## 11. Failure Handling and Rollback Policy

1. Revert only one phase at a time.
2. Never combine multiple phase extractions in one rollback event.
3. If runtime fails after a merge:
   - freeze new extraction work
   - patch compatibility first
   - resume phase sequence only after parity restored

---

## 12. PR Breakdown (Recommended)

1. PR-1: Canonical entrypoint switch (`core.acm`) + batch runner update
2. PR-2: Parser ownership + internal callable API in `acm_main` (temporary)
3. PR-3: Startup/finalize boundary cleanup
4. PR-4: Data/feature helper extractions to existing modules
5. PR-5: Model/regime helper extractions
6. PR-6: Calibration/fusion/drift helper extractions
7. PR-7: Persistence helper extractions
8. PR-8: Remove `acm_main.py` permanently + documentation hardening

Each PR must include:
1. parity check outputs
2. explicit "no behavior change intended" statement
3. rollback note

---

## 13. Documentation Migration Plan

Update active docs (non-archive) to use `core.acm`:

1. `docs/QUICK_TEST_GUIDE.md`
2. `docs/ACM_SYSTEM_OVERVIEW.md`
3. `docs/CHANGELOG.md`
4. `docs/SOURCE_CONTROL_PRACTICES.md`
5. `docs/ACM Main Refactoring Analysis - Action.md`

Archive docs remain historical and may keep legacy command references.

---

## 14. Definition of Done

Refactor is complete when all are true:

1. `python -m core.acm` is the only supported operational entrypoint.
2. `scripts/sql_batch_runner.py` uses `core.acm`.
3. `core/acm_main.py` has been removed permanently.
4. Baseline parity maintained across all critical runtime metrics.
5. Monolith complexity reduced by moving ownership-appropriate functions into existing modules.
6. Active docs consistently point to `core.acm`.

---

## 15. Execution Guardrails

1. One phase per PR.
2. No policy changes while doing structure changes.
3. No "cleanup" mixed with behavior movement unless parity is proven first.
4. Keep diffs reviewable and reversible.
5. Wrapper-only refactors are not sufficient:
   - every extraction PR must remove meaningful inline orchestration logic from `core/acm.py`
   - helper introduction must be paired with callsite simplification.
6. Track orchestrator reduction explicitly per PR:
   - report `core/acm.py` line count before and after
   - report which inline block was removed or simplified.

---

## 16. Source Control Method for This Refactor (Main Stays Untouched)

This section overrides normal day-to-day flow for this high-risk migration.

Core rule:
- No refactor PR merges into `main` until ACM is validated working without `core/acm_main.py`.

### 16.1 Branch Topology

1. `main`
   - production baseline only
   - receives hotfixes and normal non-refactor work only
2. `integration/acm-single-entrypoint`
   - long-lived refactor integration branch
   - all migration phases land here first
3. `refactor/acm-entrypoint-p<N>-<topic>`
   - short-lived phase branches
   - one branch per phase/PR

### 16.2 Merge Policy

1. Phase branches merge only into `integration/acm-single-entrypoint`.
2. No direct merge from phase branches to `main`.
3. `main` receives a single promotion merge only after final acceptance gates.
4. If urgent production hotfix lands on `main`, it must be merged/cherry-picked into integration branch immediately.

### 16.3 Protection Rules

For `main`:
1. Require PR + review approvals.
2. Block refactor-labelled PRs by branch policy.
3. Disallow force-push.
4. Require status checks (tests, lint, smoke).

For `integration/acm-single-entrypoint`:
1. Require PR + at least 1 reviewer.
2. Require phase acceptance checklist in PR description.
3. Require parity evidence attachment before merge.

### 16.4 PR Requirements (Per Phase)

Every phase PR into integration must include:
1. Scope statement: exact files/functions moved.
2. Non-goal statement: no algorithm/policy changes.
3. Parity report:
   - baseline vs current outcome
   - rows_read / rows_written
   - episodes count
   - drift mode
   - finalization status
4. Rollback plan for that phase.

### 16.5 Promotion Gate: Integration -> Main

Promotion to `main` is allowed only when all conditions are true:
1. `core/acm_main.py` is removed from codebase.
2. Runtime command is only `python -m core.acm`.
3. `scripts/sql_batch_runner.py` uses `core.acm`.
4. Active docs no longer direct users to `core.acm_main`.
5. Validation matrix passes on representative equipment windows.
6. Team sign-off confirms no functionality regression.

Recommended promotion method:
1. Create `release/acm-single-entrypoint-cutover` from integration.
2. Run final full validation there.
3. Merge release branch to `main` once (single controlled cutover PR).

### 16.6 Rollback Strategy

Before cutover merge:
1. Tag current `main` as pre-cutover baseline.
2. Keep deployment rollback pointer to that tag.

If post-cutover issues appear:
1. Revert the cutover merge commit on `main`.
2. Redeploy from pre-cutover tag.
3. Continue fixes on integration branch, not directly on `main`.

### 16.7 Operational Rule During Migration

1. Production runs continue from `main` artifacts only.
2. Experimental/refactor validation runs execute from integration branch environment.
3. Do not use integration artifacts for production decisions until cutover complete.

---

## 17. Progress Log

### 2026-02-21 - Linkage and Memory Graph Integrity Hardening

Branch flow used:
1. `refactor/acm-entrypoint-p4-linkage-health` (merged into integration)
2. `integration/acm-single-entrypoint` (updated and pushed)

Completed:
1. Added strict wiki-link integrity checks in `scripts/manage_acm_agent_memory.py`.
2. Scoped link health validation to canonical vault notes under `docs/obsidian_vault`.
3. Added refresh health gating so `refresh` exits non-zero on broken links.
4. Fixed core import link resolution in `scripts/build_acm_obsidian_graph.py` for statements like `from core import x`.
5. Removed per-module and per-function `generated_at` frontmatter to reduce graph churn noise.
6. Regenerated vault and skill references with zero broken links.

Validation completed:
1. `python scripts/manage_acm_agent_memory.py refresh --sync-repo-skill --sync-local-skill`
2. `python scripts/manage_acm_agent_memory.py health` with `ok=true` and `broken_count=0`
3. `python -c "from core.acm import main; print(callable(main))"`
4. `pytest tests/test_v11_modules.py -q` with all tests passing

Main branch status:
1. `main` was not touched.
2. Work was delivered through phase branch to integration branch only.

### 2026-02-21 - Grafana Dashboard Stability Detour

Branch flow used:
1. `refactor/acm-entrypoint-p4-grafana-dashboards-fix` (merged into integration)
2. `integration/acm-single-entrypoint` (updated and pushed)

Completed:
1. Added a new operational skill: `skills/grafana-dashboard-ops`.
2. Added validator scripts for:
   - SQL schema-level dashboard query validation
   - Grafana API runtime query validation
3. Fixed active dashboard SQL in:
   - `acm_fleet_overview.json`
   - `acm_master_complete.json`
   - `acm_observability.json`
4. Enforced active provisioning path:
   - `install/observability/provisioning/dashboards/dashboards.yaml`
   - active path now points to `/etc/grafana/dashboards/active`
5. Added active dashboard folders under both dashboard roots and synchronized content.
6. Removed stale archive dashboards from Grafana runtime using API so only active dashboards remain visible.

Validation completed:
1. `python skills/grafana-dashboard-ops/scripts/validate_acm_dashboards.py` passed
2. `python skills/grafana-dashboard-ops/scripts/validate_grafana_api_queries.py` passed
3. Grafana `/api/search?type=dash-db` shows exactly 3 active dashboards
4. Grafana provisioning duplicate-UID warnings and panel query `status=400` errors were eliminated for active dashboards

Main branch status:
1. `main` was not touched.
2. Work was delivered through phase branch to integration branch only.

### 2026-02-21 - Phase 4 Extraction: Persist Memory Cleanup and Runtime Validation

Branch flow used:
1. `integration/acm-single-entrypoint` (in-progress refactor branch for this slice)

Completed:
1. Extracted persist-phase memory cleanup call from `core/acm.py` into `core/output_manager.py` using `OutputManager.release_persist_memory(...)`.
2. Removed inline cleanup block in `core/acm.py` for raw frame deletion and detector model pointer cleanup.
3. Added test coverage for the extracted helper in `tests/test_v11_modules.py`:
   - `test_release_persist_memory_clears_raw_frames_and_detector_models`
4. Fixed observability stack scrape wiring so Prometheus scrapes Alloy correctly:
   - `install/observability/prometheus.yaml` target changed from `host.docker.internal:12345` to `acm-alloy:9099`.
5. Verified Fleet Overview palette compatibility remains valid:
   - `python skills/grafana-dashboard-ops/scripts/validate_grafana_palette_modes.py`

Validation completed:
1. `pytest tests/test_v11_modules.py -q` passed (34 tests).
2. `python -c "from core.acm import main; print(callable(main))"` returned `True`.
3. Batch runner execution on wind turbines:
   - `WFA_TURBINE_0` completed with ACM run finalized `outcome=OK`
   - `WFA_TURBINE_10` completed with ACM run finalized `outcome=OK`
   - `WFA_TURBINE_13` completed with ACM run finalized `outcome=OK`
   - `WFA_TURBINE_11` precheck failed due no historian data (expected runner error path)
4. Grafana dashboard query validation:
   - `python skills/grafana-dashboard-ops/scripts/validate_acm_dashboards.py` passed
   - `python skills/grafana-dashboard-ops/scripts/validate_grafana_api_queries.py` passed (`checked=58 errors=0`)
5. Loki verification:
   - Observed finalized run logs for the three successful ACM RunIDs.
6. Prometheus verification:
   - Before fix: `prom_targets_up=1/2` (`alloy` target down)
   - After fix and restart: `prom_targets_up=2/2`.

Main branch status:
1. `main` was not touched.
2. Work remains on refactor integration branch.

### 2026-02-21 - Phase 4 Extraction: Outcome and Error Serialization Helpers

Branch flow used:
1. `refactor/acm-entrypoint-p4-outcome-error-helpers` (in progress)

Completed:
1. Extracted run-outcome mapping helper to `core/run_metadata_writer.py`:
   - `resolve_run_outcome_from_degradations(...)`
2. Extracted run-exception serialization helper to `core/run_metadata_writer.py`:
   - `serialize_run_exception(...)`
3. Extracted NOOP run finalization helper to `core/run_metadata_writer.py`:
   - `finalize_noop_run(...)`
4. Wired `core/acm.py` to use these helpers in the main try/except block and NOOP early-return paths.
5. Added unit tests in `tests/test_v11_modules.py`:
   - `test_resolve_run_outcome_from_degradations`
   - `test_serialize_run_exception_returns_json`
   - `test_finalize_noop_run_calls_sql_finalize`
   - `test_finalize_noop_run_skips_without_run_id`
6. Hardened Obsidian graph generation against Windows file locks:
   - `scripts/build_acm_obsidian_graph.py` now skips locked note deletions and continues.

Validation completed:
1. `pytest tests/test_v11_modules.py -q` passed (38 tests).
2. `python -c "from core.acm import main; print(callable(main))"` returned `True`.
3. `python scripts/sql_batch_runner.py --equip WFA_TURBINE_0 --max-batches 1 --dry-run` completed successfully.
4. Memory refresh:
   - `python scripts/manage_acm_agent_memory.py refresh --sync-repo-skill --sync-local-skill` succeeded with locked-note skip warnings.
   - `python scripts/manage_acm_agent_memory.py health` passed with `ok=true` and `broken_count=0` when run after refresh completion.

# Output Manager Refactor Master Plan

Date: 2026-02-22
Owner: Snehil
Status: Draft for execution on integration branch

## 1. Objective

Refactor `core/output_manager.py` so that:

1. Core persistence paths are strict and fail fast.
2. Optional analytics and observability writes remain best-effort.
3. Duplicate and overlapping write logic is removed.
4. The module is easier to reason about and test without changing ACM runtime semantics.

## 2. Hard Requirements

1. No loss of core runtime behavior:
   - scores and episodes still persist with same schema expectations
   - run metadata and finalization behavior unchanged
2. No change to ACM outcome semantics:
   - `OK`, `DEGRADED`, `NOOP`, `FAIL`
3. No destructive SQL schema changes in this slice.
4. Pipeline remains runnable after every commit.
5. Main branch remains untouched during this work.

## 3. Baseline Snapshot

Current complexity baseline:

1. `core/output_manager.py`: 4017 lines
2. `try`: 93
3. `except`: 90

Observed issues:

1. Broad exception handling in core write functions can hide real failures.
2. Mixed strict and optional behavior is not consistently enforced.
3. Duplicate or overlapping write paths increase maintenance cost.
4. Some utility methods still perform guard checks that should have been validated earlier.

## 4. Behavior Classification

All methods in this module should be classified into one of two categories.

### 4.1 Strict core path methods

These must raise on failure.

1. `_bulk_insert_sql`
2. `write_dataframe` when `required=True`
3. `write_scores`
4. `write_episodes`
5. `persist_core_outputs`
6. `run_persistence_stage`
7. Any method used to persist ACM run-critical tables

### 4.2 Optional best-effort methods

These may warn and continue.

1. Correlation helper writes
2. Seasonal pattern helper writes
3. Sensor normalized series helper writes
4. Additional analytics table writes
5. Pure observability or diagnostics writes

Rule:
1. Optional behavior must be explicit and isolated.
2. Strict behavior must be default for core pipeline writes.

## 5. Phase Plan

## Phase A - Method Inventory and Strictness Map

Goal:
1. Build exact inventory of all public and private write methods.
2. Mark each as strict or optional.

Actions:

1. Create a method inventory table in this document with:
   - method name
   - target tables
   - callsites
   - strict or optional
2. Confirm call chains from `core/acm.py` into persistence stage.

Acceptance:

1. Every write method is classified.
2. No ambiguous strictness remains.

Rollback:

1. No code changes in this phase.

## Phase B - Core Write Fail-Fast Hardening

Goal:
1. Ensure core writes fail immediately and visibly.

Actions:

1. Enforce strict behavior in `_bulk_insert_sql`:
   - missing SQL client raises
   - missing target table raises
   - pre-delete failures for strict path raise
2. Ensure `write_dataframe(required=True)` raises on:
   - SQL write failure
   - unexpected zero-row insert for non-empty required data
3. Ensure `write_scores` and `write_episodes` remain strict.

Acceptance:

1. Core write failures propagate to orchestrator.
2. Existing tests pass after changes.

Rollback:

1. Revert only strictness edits from this phase.

## Phase C - Optional Write Isolation

Goal:
1. Keep best-effort behavior only where intended.

Actions:

1. Move optional write behavior behind clearly named helper methods.
2. Remove broad catch blocks from strict methods.
3. Keep warning-based handling only in optional methods.

Acceptance:

1. Strict methods no longer swallow broad exceptions.
2. Optional methods retain warning-only behavior.

Rollback:

1. Revert optional-isolation commit only.

## Phase D - Duplicate Path Removal

Goal:
1. Remove overlapping write logic and dead code.

Actions:

1. Identify duplicate payload build and write logic.
2. Collapse duplicate paths into one authoritative method per table family.
3. Remove dead helper code and stale TODO placeholders in active paths.

Acceptance:

1. No duplicate SQL write path for same artifact category.
2. Tests and runtime dry-run checks pass.

Rollback:

1. Revert duplicate-removal commit only.

## Phase E - API Surface Cleanup

Goal:
1. Make module behavior obvious from signatures and docs.

Actions:

1. Normalize method signatures with explicit `required` or optional semantics.
2. Add concise method docstrings that state strictness policy.
3. Remove obsolete compatibility comments from active code paths.

Acceptance:

1. Every key write method has clear strictness contract.
2. Static compile and tests pass.

Rollback:

1. Revert signature and docs cleanup commit only.

## 6. Validation Matrix

Run after each phase:

1. `python -m py_compile core/output_manager.py core/acm.py`
2. `pytest tests/test_v11_modules.py -q`
3. `python scripts/sql_batch_runner.py --equip FD_FAN --dry-run --max-batches 1`

Runtime parity checks:

1. Outcome
2. rows_read
3. rows_written
4. episode count
5. drift mode
6. run finalization success

## 7. Testing Additions Required

In `tests/test_v11_modules.py`, add or update tests for:

1. Required write raises on failure.
2. Required write raises when inserted rows are zero for non-empty input.
3. Optional write warns and returns cleanly.
4. `_bulk_insert_sql` raises on missing table.
5. `_bulk_insert_sql` raises on SQL client missing in strict path.

## 8. Source Control Execution

1. Work branch:
   - `refactor/acm-output-manager-hardening`
2. Merge target:
   - `integration/acm-single-entrypoint`
3. No direct merge to `main`.
4. Commit slicing:
   - Commit 1: strictness map and method inventory notes
   - Commit 2: core fail-fast hardening
   - Commit 3: optional-write isolation
   - Commit 4: duplicate removal and cleanup
   - Commit 5: tests and docs updates

Each commit must include:

1. touched methods and tables
2. no-behavior-change statement unless explicit
3. rollback note

## 9. Risks and Mitigations

Risk 1:
Core writes may fail more often after hardening.
Mitigation:
1. Keep strictness limited to core methods first.
2. Run dry-run and short-window live checks after each phase.

Risk 2:
Hidden dependencies on optional writes.
Mitigation:
1. Trace callsites from `run_persistence_stage`.
2. Add tests for optional path expectations.

Risk 3:
Large file edits cause merge conflicts.
Mitigation:
1. Small phased commits.
2. One concern per commit.

## 10. Definition of Done

This slice is complete when all are true:

1. Core write paths are fail-fast and explicit.
2. Optional writes are clearly isolated.
3. Duplicate write logic is reduced or removed.
4. `tests/test_v11_modules.py` passes.
5. Dry-run and runtime parity checks pass.
6. `core/output_manager.py` complexity metrics are reduced from baseline.

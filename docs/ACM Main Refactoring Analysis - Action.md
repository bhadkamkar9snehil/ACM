# ACM Refactoring Analysis and Action Guide

Date: 2026-02-22
Owner: Snehil
Status: Active

## Purpose

This document is the practical action layer for the single-entrypoint refactor.
The governing strategy remains in:
- `docs/ACM_SINGLE_ENTRYPOINT_REFACTOR_MASTER_PLAN.md`

This guide tracks what is done, what is risky, and what must be executed next.

## Current State Summary

1. Runtime entrypoint migration is complete:
   - `core/acm_main.py` removed.
   - `python -m core.acm` is the only runtime entrypoint.
2. Orchestrator shrink is substantial:
   - `core/acm.py`: 694 lines, `try=2`, `except=2`.
3. Complexity concentration shifted into destination modules:
   - `core/output_manager.py`: 4017 lines, `try=93`, `except=90`.
   - `core/regimes.py`: 3678 lines, `try=35`, `except=35`.
   - `core/fuse.py`: 2916 lines, `try=10`, `except=10`.
4. Refactor tests are green:
   - `pytest tests/test_v11_modules.py -q` -> `90 passed`.

## Completed Work That Must Stay

1. Single runtime entrypoint cutover.
2. Stage extraction into ownership modules (data, detector init, regime stage, fusion stage, persistence stage, teardown stage).
3. Removal of major runtime kill-switch gates in critical paths.
4. Initial fail-fast hardening in key core paths.

## Remaining High-Risk Work

1. `core/output_manager.py`
   - Too many broad exception catches in core write paths.
   - Mixed strict and best-effort behavior still unclear in several methods.
   - Some duplicated or overlapping write paths remain.
2. `core/regimes.py`
   - Large number of broad catches around core algorithmic flow.
   - Legacy fallback paths are still mixed with primary runtime flow.
3. `core/fuse.py`
   - Residual fallback and diagnostics branching still larger than desired.
4. `core/acm.py`
   - Now mostly orchestrator, but can be simplified further once destination modules are hardened.

## Mandatory Refactor Principles

1. No behavior loss in outcomes and SQL run lifecycle.
2. No wrapper-only refactors.
3. Extract full logic units to ownership modules.
4. Keep best-effort behavior only for optional analytics and observability.
5. Core writes must fail fast.
6. ASCII only in code and docs.

## Source Control Rules

1. `main` remains untouched during refactor.
2. Work on `refactor/*` branches.
3. Merge into `integration/acm-single-entrypoint` only.
4. Include parity and rollback notes per PR.

## Validation Minimum Per Slice

1. `python -m py_compile` on touched modules.
2. `pytest tests/test_v11_modules.py -q`.
3. `python scripts/sql_batch_runner.py --equip <EQUIP> --dry-run --max-batches 1`.
4. Runtime parity checks:
   - outcome
   - rows_read
   - rows_written
   - episode count
   - drift mode
   - finalization success

## Next Action

1. Execute dedicated `output_manager` hardening plan first.
2. Then continue `regimes` and `fuse` cleanup.
3. Then perform final `acm.py` orchestration simplification pass.

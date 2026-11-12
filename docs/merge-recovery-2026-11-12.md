# ACM merge recovery - 2026-11-12

## Result

Reconciled local ee9540f with remote aa55d12 (35 newer commits), preserving
both histories in a two-parent merge on main. No reset, clean, force-push,
data deletion or stash was used. The merge is local only; push and service
relaunch are blocked by a reproduced upstream statistical test failure.

## Preserved work and decisions

- Actual repository: `C:/Users/bhadk/ACM`. The chat's configured
  `C:/Users/bhadk/Documents/ACM` directory is empty.
- Local parent: `ee9540fcd1bda995171ac8175d4468446cc80ebb`.
- Remote parent: `aa55d12a1ea62c23852c01e0be38628ea82fbd1c`.
- Recovery branch: `recovery/pre-merge-20261112` (local only).
- Newer flat `src/` runtime, dependencies, SQLite persistence, ingestion,
  governed workers, UI and tests retained. Relative to the remote, production
  differences are only the added prototype/evaluation and raw-store doc path.
- Prototype relocated to `src/opmap.py`, evaluator to
  `src/evidence/opmap_eval.py`; caller imports in `tests/test_opmap.py` adapted.
  It is still not integrated into the monitor.
- New goal/design docs retained, reviewed against newer source, and corrected
  to distinguish proposed capabilities from implemented features and historical
  measurements. Unsupported universal mathematical claims were qualified.
- Newer CLAUDE.md guide retained in full, with AGENTS.md imported. Standing
  rules updated for flat imports and the user's explicit no-agent workflow.
- Local review-era MEMORY.md and lab instructions/README preserved under
  `docs/archive/review-ee9540f/`, marked historical rather than current.
- All 16 local lab docs/screenshots preserved in `docs/archive/lab-docs/`,
  verified byte-for-byte against the local parent, including 9 explicitly
  staged PNGs. Remote lab runtime deletion retained; full code remains in Git.
- Scratch files, nested benchmark repository, datasets and runtime data left
  in place. Nothing untracked was committed or deleted.
- `.gbrain-source` pins this repo to `acm`. GBrain MCP and CLI were unavailable;
  recall, entity lookup, registration and summary storage could not be run.

## Backup and recovery

Backup directory: `D:/Backups/ACM-merge-20261112-152841/`.

- `all-refs.bundle`: verified complete Git history and refs before merge.
- `local-head.zip`: original local tracked tree.
- `untracked/`: original untracked work plus the full nested benchmark tree.
  Benchmark tree: 200 files, 1,026,484,874 bytes, hash-verified.
- `acm_data-before-restart/`: 321 files, 214,256,150 bytes, hash-verified.
  Includes raw data, bootstrap/ledger JSON and model caches before migration.
- `remote-baseline/`: fresh archive of untouched aa55d12 for reproduction.
- `remote-baseline-failure.txt`: captured upstream failing-test output.
- `RECOVERY.txt`: non-destructive recovery instructions.

For rollback, first stop any service. Clone the bundle into a NEW directory
and check out the recovery ref; restore runtime data into a NEW root before
switching a service. Do not reset this checkout or overwrite live data.

## Verification

- `uv run --inexact --locked pytest tests`: **170 passed, 1 failed** in
  551.20 seconds; one FastAPI/httpx deprecation warning. No skipped tests.
- Torch 2.13.0+cu126 retained; CUDA available. `--inexact` avoids removing the
  separately installed Torch while syncing the merged project dependencies.
- `uv run --no-sync python -m service --help`: passed.
- Service/runtime/prototype imports: passed.
- No unresolved conflicts; staged diff whitespace check passed.
- Remote runtime, UI and dependencies verified identical in the merge.
- Untracked/nested files, runtime backup and archived lab content verified.
- Failing test repeated against `remote-baseline/src/runtime.py`, not the
  merged imports, using the same interpreter and isolated temporary root:
  `tests/test_novelty_episodes.py::test_change_not_fault_auto_absorbs_after_anchor_period`.
  Same failure and refusal reason reproduced on untouched remote aa55d12.

## Existing defect and operational state

The test's legitimate change is ledgered and its episode cleared before
recalibration succeeds. Recalibration refuses the proposed reference:
`|acf|=0.41 at the largest supportable block (64)`. The old model epoch
remains, while scorer and bank become None. This is an existing upstream
failure, not a merge conflict or prototype regression. Do not bypass the
exchangeability audit, tune constants, skip the test or hide Torch to pass.

No service was listening on port 8999 at task start. This recovery did not
start or stop a service, migrate acm_data, or push. Local data remains unchanged.
The repo's AGENTS.md says a red statistical lane blocks pushing; that gate
was respected. The screenshot's July service was not running on this machine.

## Next bounded stream: repair safe change absorption

Entry points:

- `src/episodes.py:EpisodicMonitor.reanchor`
- `src/monitor.py:AssetMonitor.calibrate_from_lifetime`
- `src/runtime.py:Runtime.tick` absorption branch
- `src/memory/baseline.py:LifetimeBaseline.calibration_sample`
- `tests/test_novelty_episodes.py` absorption/guard tests
- `tests/test_state_store.py` and `tests/test_runtime_service.py` continuity

Scope: diagnose the rejected calibration and make absorption a safe state
transition. Preserve the previous valid model/episode when replacement fails;
make refusal visible and retryable without losing ledger/wealth continuity.
Determine how a valid held-out reference can support an accepted change without
relaxing statistical validity. If that requires changing a frozen invariant or
rationale-carrying constant, explain the specific change to the owner first.
Do not conflate a safe fallback with successful absorption or weaken the test.

Acceptance: existing failing test and fault/non-absorption guards pass;
explicit rejected-recalibration regression proves no active model or episode
is lost; restart/SQLite continuity passes; full suite including Torch is green.
Then fetch/reconcile any further remote changes, push main without force, and
start `uv run --no-sync python -m service --root acm_data --port 8999` after
rechecking/backing up the data root. Verify API, rendered UI, fleet onboarding
and migration/restart behavior. This task did not execute that repair stream.

Next-chat prompt: "Read docs/merge-recovery-2026-11-12.md. Repair the reproduced
upstream auto-absorption failure without weakening statistical validity or
losing state. Work serially. Once the complete suite passes with Torch,
push main without force and relaunch/verify ACM on port 8999."

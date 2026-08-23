# ACM Codebase Guide

This file is the compact operating knowledge for future agents working on the
current ACM codebase. Previous implementations, investigation transcripts and
superseded experiments remain available in Git history; do not carry them in
the always-loaded project context.

## Product boundary

The repo root is the product. Production code is under `src/`; tests are under
`tests/`. There is no separate legacy implementation in the active tree.

The distribution name is `acm`, but modules are intentionally flat under
`src/` and imported as top-level modules (`runtime`, `service`, `monitor`,
`decision`, `scoring`, `memory`, ...). Run the service with:

```bash
uv run python -m service --root acm_data --port 8899
```

Start with:

- `README.md` for install/run/data entry points;
- `docs/how-acm-works.md` for the statistical and product architecture;
- `docs/src-file-guide.md` for the current source map;
- `docs/testing-and-datasets.md` for tests and external evidence.

## Non-negotiable architecture rules

1. **One asset is one independent statistical world.** Never share scorer,
   evidence-bank, episode or baseline state across assets.
2. **The raw lifetime store is append-only and UTC-strict.** Labels never enter
   model input. Naive timestamps are rejected unless an adapter explicitly
   declares the dataset's documented timezone.
3. **Column order is not part of the data contract.** Store-frame concatenation
   must match columns by name (`diagonal_relaxed` where Polars concat is used).
   This was found by the operational soak when live JSON key order differed
   from seeded history.
4. **The healthy calibration reference must be out-of-sample.** A scorer is fit
   on one portion and the e-process reference is scored on held-out data.
5. **Lifetime calibration sampling must preserve serial dependence.** Use
   consecutive chunks, never row-striding; striding whitens autocorrelation and
   invalidates live-vs-calibration block assumptions.
6. **The alpha ledger is load-bearing.** Evidence-domain shares must sum to 1.0;
   do not add a detector/bank without funding it from the existing budget and
   preserving the union-bound argument.
7. **Never move the definition of normal during accumulating fault evidence.**
   Rebuild/re-anchor is governed and blocked while a fault episode is open.
8. **A bootstrap mask must not destroy the possibility of a baseline.** If a
   newly-created mask makes final calibration impossible, the self-refuting
   window repair must restore a viable reference.
9. **Tier changes may change power/cost, not verdict semantics.** Tier-0 and
   Tier-2 scorers must expose the same downstream contract (score, PIT,
   attribution, concentration, coverage, channel-local lens).
10. **External labeled datasets are evidence, never tuning targets.** CARE and
    other benchmarks may falsify a design or expose a bug; never adjust a
    parameter merely to improve a benchmark number.

## Runtime and persistence

`Runtime` is the fleet host. It owns monitors, verdicts, lifecycle state,
activity, evidence history and the governed tick/rebuild/immune schedule.

Durable state is SQLite (`src/store/state.py`) in WAL mode:

- asset registry and runtime journal (`last_seen`, `tick_count`);
- episode ledger mirror;
- verdict/evidence history;
- activity and immune results;
- per-tick e-process wealth snapshots.

Restart continuity is a correctness property, not a UI convenience. Losing
`last_seen` re-scores old history and double-counts evidence; losing wealth
changes the e-process trajectory. Tests pin both behaviors.

The pre-SQLite `ledger.json` / `bootstrapped.json` migration is an upgrade path.
Do not remove it casually while deployed data roots may still predate SQLite.

## Parallel fleet work

Onboard/bootstrap may fan across processes; per-tick scoring remains simple.
Workers never mutate shared fleet state. Bootstrap workers use a private
throwaway ledger and return episode diffs; the parent applies shared-state
writes sequentially.

Use **spawn, never fork**. The live service applies BLAS thread caps before
numpy is imported and workers re-apply them in `worker_init()`.

Retained historical mistake IDs still referenced from source:

- **Mistake #42 - unconstrained parallelism on ~16 GB hosts.** Large worker
  counts caused memory pressure/OOM. Resource concurrency must come from the
  hardware governor, not CPU count alone.
- **Mistake #44 - fork + initialized BLAS.** Forking after numpy/OpenBLAS had
  initialized produced workers parked in inherited internal locks (large wall
  time, near-zero CPU). Cap BLAS threads before numerical imports and use the
  spawn context.

A standalone caller that directly triggers multiprocessing must itself use the
normal Python `if __name__ == "__main__":` guard. A pool-wide
`BrokenProcessPool` is not an asset-level insufficient-history result; fall
back loudly rather than misclassifying every asset.

## Service loop safety

An unsupervised `asyncio.create_task` can die while FastAPI keeps serving,
which makes a stopped monitor look healthy. Background monitoring loops must
catch/log failures and continue on the next interval. Fire-and-forget tasks
must retain references until completion.

Long onboarding/bootstrap work belongs off the event loop. Bind the server
first and perform heavy work through worker threads/processes so the UI can
show progress instead of appearing dead.

## Evidence and self-test

The immune path tests whether the detector is still trustworthy. Do not weaken
or remove it as "extra validation". The live scorer must be checked as well as
the recipe; a fresh test model cannot reveal a dead deployed scorer.

PIT/conformance failures during an active real fault are not automatic reasons
to rebuild: the fault itself violates the healthy-reference assumption. The
runtime defers that interpretation so it never absorbs an active degradation.

CARE replay detection means any alarming tick at/after the documented event
start. A pre-event alarm is recorded separately and must not hide a later
in-window alarm. Normal events are equally important because they exercise the
false-alarm promise.

Current evidence should be described conservatively. A passed soak or sampled
CARE result is regression evidence, not a universal performance guarantee.

## World models

`TorchWorldModel` predicts each channel from other channels and their lags; a
channel's own history is excluded so a model cannot simply track its own fault.

`MaskedWorldModel` is the wide-asset O(d) alternative. It is intentionally not
governor-selected yet; it remains reachable through the evidence scorer
override until parity evidence justifies promotion. Do not delete it as dead
code or promote it as default merely because it exists.

Torch is optional (`tier2` dependency group). Tier 0 must remain complete
without it.

## Testing rules

Before considering a change complete, run the smallest relevant tests, then the
full active lane when possible:

```bash
uv run pytest tests -q -m "not statistical"
uv run pytest tests -q -m statistical
```

Validity-critical changes require the statistical lane. Never replace a test
that protects a guarantee with a weaker implementation-specific assertion just
to simplify code.

The operational soak (`python -m evidence.soak`) is the release-level check for
healthy -> legitimate change -> absorption -> fault behavior through the real
service path.

## Repository hygiene

- ASCII-only source/docs is enforced by test. Use `-`, `->`, `x`, `+/-`.
- Prefer deleting obsolete paths over adding compatibility wrappers around
  them. Git history is the archive.
- Prefer one implementation over speculative interfaces/factories. Add an
  abstraction when a second real implementation exists.
- Prefer one source of truth. A registered constant that no code consumes is
  worse than a literal because it falsely claims authority.
- Preserve behavior when simplifying statistical, persistence, concurrency and
  safety paths. When equivalence cannot be demonstrated, do not refactor for
  aesthetics.
- Do not preserve old command examples or architecture snapshots in active
  docs. Update the canonical document instead.

## Files that deserve extra caution

- `src/decision/eprocess.py` - validity keystone and alpha accounting.
- `src/monitor.py` - calibration split and cross-domain decision contract.
- `src/memory/baseline.py` - lifetime/recency arithmetic and serial-dependence
  preserving sample construction.
- `src/episodes.py` - episode classification, absorption and re-anchor rules.
- `src/runtime.py` - restart continuity, governed orchestration, bootstrap and
  immune lifecycle.
- `src/fleet_workers.py` - process isolation and parent-only shared writes.
- `src/store/state.py` - durable decision trajectory and upgrade migration.

For historical rationale beyond these standing rules, inspect Git history or
the dated design documents rather than growing this file back into a session
transcript.

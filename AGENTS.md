# ACM - agent instructions

This file holds the standing rules for any agent working in this repo.
It is the single source: `CLAUDE.md` imports it. Current project state
(evidence, open items) is in `MEMORY.md`. The pre-rewrite history is in
`docs/archive/kb-lab-history.md` and is not loaded by default.

## What this repo is

ACM (Asset Condition Monitor, version 2.0.0a0) is a self-learning,
unsupervised condition monitor for industrial assets. The goal and its
fixed constraints are in `docs/acm-goals-and-routes.md`, and the
design ACM is being built to is in `docs/acm-design.md`. Read both before any design
work. In short:

- No human in the loop: deployment, learning and operation do not
  depend on people. Operator feedback is a later addition, so do not
  design the core around it.
- Cold start from t=0: assume a new historian and no earlier history.
- No list of expected faults.
- Hundreds of assets: cost per asset per tick stays small.
- Plug and play: nobody marks assets as similar or configures them.
- One input schema for any asset in any industry: a timestamp column
  and numeric channels, with no asset type or tag meaning supplied.
- No tuned numbers. Do not pick or adjust a constant by looking at a
  benchmark. Follow the rules of evidence in section 10 of the goals
  document: every number has a source, structural constants are tested
  for sensitivity, development data and judging data are separate, and
  every run is reported including failures. CARE is development data.
- Do not claim ACM works from one dataset or the best case.
- Data faults are in scope, and advisories have to be usable by plant
  operators.

Everything else is negotiable, including the current code, the
invariants below and the two earlier plans. Benchmarks are evidence,
not tuning targets. CARE data is pre-aggregated, so it cannot stand in
for raw-data evaluation.

```
src/acm/         the product (import name acm; python -m acm.service)
tests/           unit + statistical lanes
docs/            acm-goals-and-routes.md (goal, constraints, routes),
                 acm-design.md (the design, with build order and gates), archive/ (superseded
                 plans and lab-era docs; history, not instructions)
paper/           research paper draft (lab-era)
lab/             the pre-rewrite ACM1 system (six-detector pipeline,
                 simulator, benchmark harnesses). Reference and tooling,
                 not the product. Run its commands from inside lab/.
```

Older docs say "ACM2" or `acm2.*`. That is this product; the package is
now `acm`.

## Commands

```
uv sync                      install (drops torch, see below)
uv run pytest tests          full suite: the merge gate
uv run python -m acm.service start the service
uv pip install torch --index-url https://download.pytorch.org/whl/cu126
```

Torch is in the `tier2` dependency group, so `uv sync` removes it.
Reinstall it after each sync on this machine (Windows, RTX 4060).
Without torch, `test_worldmodel.py` skips and the world-model path does
not run. That skip is silent, so check for it when the world model
matters.

## Workflow

- Work on `main` and push to `main`. The user asked for this repeatedly;
  open a branch or a PR only when asked. Do not force-push.
- GitHub Actions is billing-locked and does not run, so the local suite
  is the only gate. Run `uv run pytest tests` before each push. A red
  statistical lane blocks a push the same way a red unit test does.
- Each non-trivial code change has a GitHub issue, and the commit
  references it (`Fix #N - ...`). `gh` is installed and authenticated.
  Docs-only changes need no issue.
- When a change adds or changes a user-facing flag or command, update
  the matching section of `README.md` in the same change.
- Use ASCII only in files you touch. `tests/test_ascii.py` enforces this
  for `src/` and `tests/`; apply it to docs and instruction files too.

### Steps that need no approval

Read any file. Run the test suite, the service, evidence replays and
benchmark harnesses. Edit code, tests and docs for the task in hand.
Create and close GitHub issues for that task. Commit and push to `main`
once the suite is green and the user asked for the change.

### Steps to confirm first

- Deleting data directories (`acm_data/`, `care_data/`, `results/`,
  `*.db`) or remote branches.
- Changing a frozen contract or an invariant listed below.
- Changing a rationale-carrying constant in `src/acm/constants.py` in
  response to one dataset's result.

## Finishing work

Carry a task through to the end. When you hit an ordinary obstacle (a
failing test, a timeout, a locked file, an empty result), diagnose it
and work through it. Stop for the user only when the next step is in
the "confirm first" list or the task cannot move without their answer.
The user expects results that work end to end, verified by running
them, not changes that are correct on paper.

Do the work yourself in the session. Start a subagent only for
independent parallel work that is large enough to repay a cold start.

## Invariants

Most of these are pinned by tests. Each one exists for the reason given.
If a better outcome needs one changed, say which invariant and why
before you act; the user decides, and has said results matter more than
precedent.

- **One dial.** Everything other than `ALPHA_PER_ASSET_YEAR` is derived
  from the asset's own data or is a constant in `src/acm/constants.py`
  with its rationale. There are no config files and no per-site tuning.
  Reason: a tuning surface is how the lab system drifted into
  dataset-specific fixes.
- **Verdict contract v1 fields are frozen** (`src/acm/verdict.py`).
  Reason: the UI and downstream consumers depend on them.
- **`acm` does not import the lab** (`tests/test_import_boundary.py`).
- **Not built, on purpose:** trailing or trim retention windows,
  threshold alarm rules, a distrust gate, fusion auto-tuning, kurtosis
  or skewness features. Reason: each one caused a documented failure in
  the lab. This list is under review (see "Status of prior analysis").
- **Timestamps are timezone-aware UTC.** The adapter declares the zone;
  ingest rejects naive timestamps and does not guess.
- **Labels and metadata columns do not enter the raw store.** Reason:
  the monitor is unsupervised, and leaked labels invalidate evidence.
- **Alpha is a probability per anchor**, converted from the yearly rate
  by `REANCHORS_PER_YEAR`. `EProcess` rejects alpha outside (0, 1).
- **Verdict meaning is the same at every hardware tier.** Only detection
  power differs.

## Code patterns that have broken production before

- Concatenate store frames with `how="diagonal_relaxed"`. Column order
  is not part of the store contract, and three order-sensitive concats
  each crashed a live path.
- Guard every long-lived asyncio task in the service (log, then retry).
  An unguarded tick loop once died silently while the API kept serving.
- New action endpoints run blocking work through `asyncio.to_thread`,
  then broadcast a fleet snapshot on `/api/ws`. Otherwise the event
  loop blocks or the UI goes stale.
- Handle NaN the same way at fit time and at score time. Three null
  rows in 52k once produced a non-finite scorer.
- An asset is "virgin" when it has never been bootstrapped
  (`data_root/bootstrapped.json`), not when its ledger is empty.
- Fault episodes mask the baseline. Change-not-fault episodes are
  absorbed into it. A mask that leaves no baseline is invalid, and
  bootstrap repairs it.
- The UI is one zero-build file (`src/acm/ui.html`) with ECharts
  vendored at `src/acm/vendor/`. It has to work air-gapped, so do not
  add a CDN reference or a build step.
- `TestClient` accepts WebSocket connections even when uvicorn has no
  WebSocket library. Check live-stream changes in a real browser.

## Status of prior analysis

The user has asked for a fundamental re-evaluation of the analysis done
so far. Until that is complete, treat earlier conclusions as hypotheses
to re-test, not as settled facts. This covers the lab-era diagnoses in
`docs/archive/kb-lab-history.md`, the evidence summary in `MEMORY.md`, the
invariants above, and the method choices in `docs/archive/plans-2026-07/acm-gem-plan.md` and
`docs/archive/plans-2026-07/acm-rethink-plan.md`. The 2026-11-12 review found that the current
build assumes history exists, does not handle data faults, and needs a
person to close a fault episode. When you rely on an earlier
conclusion, re-measure it or say that you did not.

## Writing reports and notes

Write for a reader who did not see your tool calls. Put the result
first. Use plain words and full sentences, and use one term for one
thing. Report what you ran and what it showed, including failures and
anything you did not verify.

Keep these files short. Put a durable, current fact in `MEMORY.md` and
remove the fact it replaces. Put a standing rule here, with its reason
and its scope. Do not append session logs to either file; git history
and the issue tracker hold those.

# ACM Status Snapshot

Last updated: 2026-03-13 UTC

This file is a rewritten snapshot, not an append-only log.
Each meaningful ACM slice replaces this file with current repo and runtime truth.

## At A Glance

| Item | Current value |
|---|---|
| Overall `2026.2` completion | `80%` |
| Architecture / ownership extraction | `90%` |
| Runtime governed behavior | `84%` |
| Coldstart / baseline unification | `90%` |
| SQL / control-plane alignment | `78%` |
| Replay qualification | `85%` |
| Dashboard / operator cutover | `35%` |
| Forecast / RUL governed cutover | `20%` |
| Current branch | `refactor/2026.2-rg-13-audit-hygiene` |
| Latest validated runtime commit | `a9ee9c0` |
| Latest checkpoint tag | `checkpoint/2026.2-governed-coldstart-runner-cutover-20260313` |

## Time Estimate

| Scope | Estimated remaining time |
|---|---|
| Core ACM runtime unification | `0.5 to 1 focused day` |
| Full `2026.2` completion | `2.5 to 4.5 focused days` |

The remaining work is concentrated in:

- earlier representation-first stop ordering
- final lifecycle-wrapper removal
- dashboard / operator cutover
- forecast / RUL governed cutover
- replay-qualified legacy deletion

## What ACM Is Right Now

ACM is now a governed representation-aware runtime with:

- live SQL-backed suppression and baseline-governance truth
- stable multi-asset no-score behavior
- score-head / score-split baseline fallback removed
- explicit governed load-path selection for existing-model reuse
- `smart_coldstart` reduced to a narrow historian-window / progress helper
- `sql_batch_runner.py` using governed baseline status first for coldstart completion
- many no-score runs short-circuit before feature, detector, regime, zero-day, and health work

Current repo/runtime truth:

- governed representation authority is live
- governed no-score runs persist correct control-plane truth
- baseline fallback now stays in `TRUSTED_WINDOW_PENDING`
- `smart_coldstart` no longer owns lifecycle meaning
- the runner no longer treats `ACM_ActiveModels.RegimeMaturityState` as primary coldstart authority
- governed runtime mode now decides whether existing models may be used whenever that truth is available

What ACM is not yet:

- fully representation-first from the earliest possible stop point
- fully unified under `baseline_governor` as the only readiness authority
- operator-complete in dashboards
- forecast / RUL governed end-to-end
- fully stripped of transitional legacy owners

## Latest Validated Runtime Truth

Latest live 3-asset validation, run in parallel with observability disabled:

| Asset | RunID | Result | What it proved |
|---|---|---|---|
| `FD_FAN` | `b0aa40a0-8123-4d0d-a920-5b7ce1435427` | `NOOP` | governed no-data / no-progress path still exits cleanly |
| `WFA_TURBINE_0` | `972a697d-74e3-4548-bd48-6310ef0aef71` | `DEGRADED` | later pre-transient suppression path still works under governed baseline formation |
| `WFA_TURBINE_10` | `df3658a9-f380-4950-99c3-28de487d7279` | `DEGRADED` | cached feature-preview suppression path still works under governed baseline formation |

Observed in logs:

- `FD_FAN`
  - clean `NOOP` finalization
- `WFA_TURBINE_0`
  - `Representation authority short-circuited transient, zero-day, and health stages after regime-context precheck`
  - `RUN END: outcome=DEGRADED`
- `WFA_TURBINE_10`
  - `Representation authority short-circuited detector scoring, zero-day, and health stages from cached feature-frame regime preview`
  - `RUN END: outcome=DEGRADED`

Observed in SQL:

| Asset | Runtime mode | Baseline candidate | Shadow refresh | Score allowed | Learn allowed | Score rows |
|---|---|---|---|---|---|---|
| `FD_FAN` | `NULL in ACM_Runs representation columns for this NOOP path` | `NULL` | `NULL` | `NULL` | `NULL` | `0` |
| `WFA_TURBINE_0` | `BASELINE_FORMATION` | `COLLECTING_TRUSTED_WINDOW` | `LEARNING_ALLOWED` | `0` | `1` | `0` |
| `WFA_TURBINE_10` | `BASELINE_FORMATION` | `COLLECTING_TRUSTED_WINDOW` | `LEARNING_ALLOWED` | `0` | `0` | `0` |

This means:

- governed coldstart/load authority now works across runtime and runner paths
- assets can still land in different valid governed states during baseline formation
- score tables remain correctly empty when score output is not allowed

## What Was Completed Recently

Recent validated slices:

| Commit | Summary |
|---|---|
| `a9ee9c0` | prefer governed coldstart status in runtime and runner |
| `add8f03` | remove retry semantics from smart coldstart |
| `22628a3` | trim dead smart coldstart helper state |
| `7310955` | remove dead smart-coldstart retry API |
| `c83e630` | replace coldstart load boolean with explicit decision |
| `16e3b3a` | narrow smart coldstart to helper-only flow |

Net effect of recent slices:

- runtime no longer depends on hidden lifecycle meaning inside `smart_coldstart`
- runner coldstart progression now prefers governed baseline truth
- public and internal load-stage contracts are explicit instead of boolean-driven
- retry-era `smart_coldstart` naming and dead state are gone
- coldstart / baseline formation is much closer to a single governed personality

## Remaining Work Burn-Down

| Area | Current state | Remaining | Difficulty |
|---|---|---|---|
| Coldstart / baseline authority | Runtime and runner both prefer governed load decisions | Remove the last lifecycle fallback wrappers and make `baseline_governor` the only readiness/mode authority | Medium |
| Representation-first runtime ordering | Many governed no-score runs stop before feature / detector / regime work | Push stop conditions earlier than seasonality / raw preview / feature prep where evidence already exists | High |
| Zero-day demotion | Zero-day is non-authoritative on governed no-score runs | Remove remaining alternate-personality feel from runtime summaries and operator surfaces | Medium |
| SQL / control-plane semantics | Governed tables and views are live and useful | Finalize target semantics for `ACM_SignalProfiles` and `ACM_RepresentationSchemas` | Medium |
| Dashboards / operator truth | Governed views exist | Cut Grafana and operator queries over to governed views | High |
| Forecast / RUL | Still mostly legacy | Bring forecast / RUL under governed eligibility and suppression rules | High |
| Legacy deletion | Some obsolete code and tables already removed | Delete remaining transitional owners only after replay-qualified replacement is proven | Medium |

## Biggest Current Blockers

Ordered by importance:

1. Earlier representation-first stop ordering
2. Final lifecycle-wrapper removal
3. Dashboard / operator cutover
4. Forecast / RUL governed cutover
5. Final legacy deletion

The main blocker is no longer coldstart boolean cleanup.
The main blocker is stopping more non-scoreable work earlier, then cutting operator truth over to governed ACM.

## Source Control State

Current branch hygiene is good for runtime slices:

- runtime slices are committed separately
- validated slices are checkpoint-tagged
- the current rolling branch is still the integration line for this work

Current intentional dirtiness:

- only the old memory-reference files under `skills/acm-codebase-memory/references/`
- these are being left out of runtime commits on purpose

## Next Planned Slices

Immediate next slices:

1. remove the remaining lifecycle fallback wrappers so `baseline_governor` is the only real readiness authority
2. push governed no-score resolution earlier than seasonality / raw preview / feature prep where evidence already exists
3. continue 2-3 asset parallel validation after each runtime-affecting slice

After that:

4. finish SQL / control-plane semantic cleanup
5. cut dashboards over to governed views
6. bring forecast / RUL under governed ACM
7. delete transitional legacy owners after replay-qualified replacement

## Completion Definition

`2026.2` is complete only when:

- `baseline_governor` is the only readiness / mode authority
- no authoritative score-derived baseline fallback remains
- zero-day is never an alternate authority
- `core/acm.py` is orchestration-only
- governed SQL tables and views are canonical
- dashboards reflect governed ACM truth
- forecast / RUL obey governed eligibility
- transitional legacy owners are removed
- replay validation passes on the target assets under the final model

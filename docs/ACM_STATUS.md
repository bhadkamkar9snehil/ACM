# ACM Status Snapshot

Last updated: 2026-03-13 UTC

This file is a rewritten snapshot, not an append-only log.
Each meaningful ACM slice replaces this file with current repo and runtime truth.

## At A Glance

| Item | Current value |
|---|---|
| Overall `2026.2` completion | `79%` |
| Architecture / ownership extraction | `90%` |
| Runtime governed behavior | `83%` |
| Coldstart / baseline unification | `87%` |
| SQL / control-plane alignment | `78%` |
| Replay qualification | `84%` |
| Dashboard / operator cutover | `35%` |
| Forecast / RUL governed cutover | `20%` |
| Current branch | `refactor/2026.2-rg-13-audit-hygiene` |
| Latest validated runtime commit | `add8f03` |
| Latest checkpoint tag | `checkpoint/2026.2-smart-coldstart-retry-semantics-removal-20260313` |

## Time Estimate

| Scope | Estimated remaining time |
|---|---|
| Core ACM runtime unification | `0.5 to 1.5 focused days` |
| Full `2026.2` completion | `3 to 5 focused days` |

The remaining work is concentrated in:

- final coldstart / baseline authority cleanup
- earlier representation-first stop ordering
- dashboard / operator cutover
- forecast / RUL governed cutover
- replay-qualified legacy deletion

## What ACM Is Right Now

ACM is now a governed representation-aware runtime with:

- live SQL-backed suppression and baseline-governance truth
- stable multi-asset no-score behavior
- score-head / score-split baseline fallback removed
- explicit load-path selection for existing-model reuse
- `smart_coldstart` reduced to real progress/load-window work instead of retry-era wrappers
- many no-score runs short-circuit before feature, detector, regime, zero-day, and health work

Current repo/runtime truth:

- governed representation authority is live
- governed no-score runs persist correct control-plane truth
- baseline fallback now stays in `TRUSTED_WINDOW_PENDING`
- `smart_coldstart` no longer carries dead retry naming or dead helper-only state
- `ColdstartState` now only carries live progress/load-path fields
- `load_window()` now names the real behavior instead of pretending internal retry still exists

What ACM is not yet:

- fully representation-first from the earliest possible stop point
- fully unified under `baseline_governor` as the only readiness authority
- operator-complete in dashboards
- forecast / RUL governed end-to-end
- fully stripped of transitional legacy owners

## Latest Validated Runtime Truth

Latest live 3-asset validation, run in parallel with observability disabled:

| Asset | RunID | Result |
|---|---|---|
| `FD_FAN` | `5b565207-44f0-4eca-8724-b38de3ac0de2` | `DEGRADED` |
| `WFA_TURBINE_0` | `c3116f56-27e1-40e6-b7fe-304cb9120573` | `DEGRADED` |
| `WFA_TURBINE_10` | `b049a07a-9da1-4976-9f80-9e712cd37ee7` | `DEGRADED` |

Observed in logs for all three:

- `Baseline candidate retained as shadow-only: trusted window pending`
- `Representation authority short-circuited feature, detector, regime, zero-day, and health stages`
- `RUN END: outcome=DEGRADED`

Observed in SQL for all three:

| Field | Expected / observed value |
|---|---|
| `RuntimeMode` | `BASELINE_FORMATION` |
| `BaselineCandidateState` | `TRUSTED_WINDOW_PENDING` |
| `ShadowRefreshState` | `WAITING_FOR_TRUSTED_WINDOW` |
| `ScoreAllowed` | `0` |
| `LearnAllowed` | `0` |
| `SuppressedReasonsJson` | `["baseline_formation_scoring_disabled"]` |
| `DegradedReasonsJson` | includes `baseline_trusted_window_pending` |
| `ACM_Scores_Wide` rows | `0` |

This means the governed no-score path is still stable across multiple assets after the latest smart-coldstart cleanup.

## What Was Completed Recently

Recent validated slices:

| Commit | Summary |
|---|---|
| `add8f03` | remove retry semantics from smart coldstart |
| `22628a3` | trim dead smart coldstart helper state |
| `7310955` | remove dead smart-coldstart retry API |
| `c83e630` | replace coldstart load boolean with explicit decision |
| `16e3b3a` | narrow smart coldstart to helper-only flow |
| `5625637` | remove `coldstart_complete` from load-stage result |
| `9b138e1` | demote `coldstart_complete` from baseline governance |

Net effect of recent slices:

- runtime no longer depends on `coldstart_complete` in representation, persistence, health, or public load-stage contracts
- load-path selection is explicit instead of hidden in an overloaded boolean
- retry-era `smart_coldstart` naming and dead state are being removed, not wrapped
- baseline formation semantics are cleaner and closer to the target ACM definition

## Remaining Work Burn-Down

| Area | Current state | Remaining | Difficulty |
|---|---|---|---|
| Coldstart / baseline authority | Most runtime-facing legacy coldstart semantics are removed | Finish demoting `smart_coldstart` to historian-window / progress helper only; remove remaining lifecycle wrappers that still encode old readiness meaning | Medium |
| Representation-first runtime ordering | No-score runs often stop before feature / detector / regime work | Push stop conditions earlier than any remaining avoidable preview / preparation cost where evidence already exists | High |
| Zero-day demotion | Zero-day is non-authoritative on governed no-score runs | Remove remaining alternate-personality feel from runtime summaries and operator surfaces | Medium |
| SQL / control-plane semantics | Governed tables and views are live and useful | Finalize target semantics for `ACM_SignalProfiles` and `ACM_RepresentationSchemas` | Medium |
| Dashboards / operator truth | Governed views exist | Cut Grafana and operator queries over to governed views | High |
| Forecast / RUL | Still mostly legacy | Bring forecast / RUL under governed eligibility and suppression rules | High |
| Legacy deletion | Some obsolete code and tables already removed | Delete remaining transitional owners only after replay-qualified replacement is proven | Medium |

## Biggest Current Blockers

Ordered by importance:

1. Final coldstart / baseline authority unification
2. Earlier representation-first stop ordering
3. Dashboard / operator cutover
4. Forecast / RUL governed cutover
5. Final legacy deletion

The main blocker is no longer basis churn.
The main blocker is finishing authority cleanup and then cutting operator surfaces over to governed ACM truth.

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

1. remove the remaining old coldstart / lifecycle wrappers that still carry readiness semantics outside `baseline_governor`
2. push governed no-score resolution earlier than any remaining avoidable prep cost
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

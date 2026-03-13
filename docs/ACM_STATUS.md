# ACM Status Snapshot

Last updated: 2026-03-13 UTC

This file is a rewritten snapshot, not an append-only log.
Each meaningful ACM slice should replace the contents of this file with current repo and runtime truth.

## At A Glance

| Item | Current value |
|---|---|
| Overall `2026.2` completion | `76%` |
| Architecture / ownership extraction | `90%` |
| Runtime governed behavior | `80%` |
| Coldstart / baseline unification | `79%` |
| SQL / control-plane alignment | `78%` |
| Replay qualification | `81%` |
| Dashboard / operator cutover | `35%` |
| Forecast / RUL governed cutover | `20%` |
| Current branch | `refactor/2026.2-rg-13-audit-hygiene` |
| Latest runtime commit | `c83e630` |
| Latest checkpoint tag | `checkpoint/2026.2-explicit-coldstart-load-decision-20260313` |

## Time Estimate

| Scope | Estimated remaining time |
|---|---|
| Core ACM runtime unification | `1.5 to 3 focused days` |
| Full `2026.2` completion | `4 to 7 focused days` |

The project is no longer in the extraction-heavy phase.
Most new owners are already in place.
The remaining time is concentrated in the harder tail:

- final coldstart / baseline authority cleanup
- earlier representation-first stop ordering
- dashboard / operator cutover
- forecast / RUL governed cutover
- replay-qualified deletion of transitional owners

## What ACM Is Right Now

ACM is no longer a pure legacy detector-first runtime.
It is now a governed representation-aware runtime with real SQL-backed suppression and baseline-governance truth.

Current repo/runtime truth:

- governed representation authority is live
- governed no-score runs are persisted correctly in SQL
- score-head / score-split baseline fallback mechanics are removed
- baseline candidate state now uses `TRUSTED_WINDOW_PENDING`
- the old load-stage `needs_coldstart` boolean is replaced with an explicit load decision:
  - `use_existing_models`
  - `runtime_mode_hint`
  - `reason_code`
- many no-score runs now short-circuit before feature, detector, regime, zero-day, and health stages

What ACM is not yet:

- fully representation-first from the earliest possible stop point
- fully unified around `baseline_governor` as the only readiness authority
- operator-complete in dashboards
- forecast / RUL governed end-to-end
- fully stripped of transitional legacy owners

## Latest Validated Runtime Truth

Latest live 3-asset validation, run in parallel with observability disabled:

| Asset | RunID | Result |
|---|---|---|
| `FD_FAN` | `e50175be-a412-4fa3-8882-418a7811ea7a` | `DEGRADED` |
| `WFA_TURBINE_0` | `71835aa3-81ae-4b70-ab72-65dbf8759738` | `DEGRADED` |
| `WFA_TURBINE_10` | `34622f4e-c334-4575-8bea-898479b2c678` | `DEGRADED` |

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
| `ACM_Scores_Wide` rows | `0` |

This means the current governed no-score path is stable across multiple assets and is not regressing as coldstart/baseline authority is cleaned up.

## What Was Completed Recently

Recent validated slices:

| Commit | Summary |
|---|---|
| `c83e630` | replace coldstart load boolean with explicit decision |
| `16e3b3a` | narrow smart coldstart to helper-only flow |
| `5625637` | remove `coldstart_complete` from load-stage result |
| `9b138e1` | demote `coldstart_complete` from baseline governance |
| `4e7099a` | remove legacy coldstart plumbing from persistence path |
| `7964b38` | remove legacy coldstart plumbing from health path |

Net effect of these slices:

- `coldstart_complete` is no longer part of the operative runtime contract for representation, health, persistence, or load-stage public output
- the load-stage decision is now explicit instead of being hidden in one overloaded boolean
- baseline formation semantics are now cleaner and closer to the target ACM definition

## Remaining Work Burn-Down

| Area | Current state | Remaining | Difficulty |
|---|---|---|---|
| Coldstart / baseline authority | Most runtime-facing legacy coldstart semantics are removed | Finish demoting `smart_coldstart` to historian-window / progress helper only; remove remaining lifecycle wrappers that still encode old readiness meaning | Medium |
| Representation-first runtime ordering | No-score runs often stop before detector/regime work | Push stop conditions earlier than feature prep / seasonality / preview cost where evidence already exists | High |
| Zero-day demotion | Zero-day is non-authoritative on governed no-score runs | Remove remaining alternate-personality feel from runtime summaries and operator surfaces | Medium |
| SQL / control-plane semantics | Governed tables and views are live and useful | Finalize target semantics for `ACM_SignalProfiles` and `ACM_RepresentationSchemas` | Medium |
| Dashboards / operator truth | Governed views exist | Cut Grafana and operator queries over to governed views | High |
| Forecast / RUL | Still mostly legacy | Bring forecast / RUL under governed eligibility and suppression rules | High |
| Legacy deletion | Some obsolete code and tables already removed | Delete remaining transitional owners only after replay-qualified replacement is proven | Medium |

## Biggest Current Blockers

Ordered by importance:

1. Earlier representation-first stop ordering
2. Final coldstart / baseline unification
3. Dashboard / operator cutover
4. Forecast / RUL governed cutover
5. Final legacy deletion

The main blocker is no longer basis churn.
The dominant remaining technical problem is that ACM still pays too much cost before final authority is known on many non-scoreable batches.

## Source Control State

Current branch hygiene is good for runtime slices:

- runtime slices are being committed separately
- validated slices are being checkpoint-tagged
- the current rolling branch is still the integration line for this work

Current intentional dirtiness:

- only the old memory-reference files under `skills/acm-codebase-memory/references/`
- these are being left out of runtime commits on purpose

## Next Planned Slices

Immediate next slices:

1. Remove the remaining old coldstart / lifecycle wrappers that still carry readiness semantics outside `baseline_governor`
2. Push governed no-score resolution earlier than feature prep where possible
3. Continue 2-3 asset parallel validation after each runtime-affecting slice

After that:

4. Finish SQL/control-plane semantic cleanup
5. Cut dashboards over to governed views
6. Bring forecast / RUL under governed ACM
7. Delete transitional legacy owners after replay-qualified replacement

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

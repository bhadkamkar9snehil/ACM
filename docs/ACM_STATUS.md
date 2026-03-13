# ACM Status Snapshot

Last updated: 2026-03-13 UTC

This file is a rewritten snapshot, not an append-only log.
Each major ACM slice replaces this file with current repo and runtime truth.

## At A Glance

| Item | Current value |
|---|---|
| Overall `2026.2` completion | `81%` |
| Architecture / ownership extraction | `91%` |
| Runtime governed behavior | `85%` |
| Coldstart / baseline unification | `92%` |
| SQL / control-plane alignment | `78%` |
| Replay qualification | `86%` |
| Dashboard / operator cutover | `35%` |
| Forecast / RUL governed cutover | `20%` |
| Current branch | `refactor/2026.2-rg-13-audit-hygiene` |
| Latest validated runtime commit | `pending commit from current governed-only coldstart slice` |
| Latest checkpoint tag | `pending tag for current governed-only coldstart slice` |

## Time Estimate

| Scope | Estimated remaining time |
|---|---|
| Core ACM runtime unification | `0.5 to 1 focused day` |
| Full `2026.2` completion | `2 to 4 focused days` |

The remaining work is now concentrated in:

- earlier representation-first stop ordering
- final trusted-window package evolution
- dashboard / operator cutover
- forecast / RUL governed cutover
- replay-qualified legacy deletion

## What ACM Is Right Now

ACM is now a governed representation-aware runtime with:

- live SQL-backed suppression and baseline-governance truth
- stable multi-asset no-score behavior
- score-head / score-split baseline fallback removed
- governed coldstart/load decisions shared by runtime and runner
- `smart_coldstart` reduced to a narrow historian-window / progress helper
- many no-score runs short-circuit before feature, detector, regime, zero-day, and health work

Current repo/runtime truth:

- governed representation authority is live
- governed no-score runs persist correct control-plane truth
- baseline fallback now stays in `TRUSTED_WINDOW_PENDING`
- `smart_coldstart` no longer owns lifecycle meaning
- the runner no longer treats `ACM_ActiveModels.RegimeMaturityState` as coldstart authority
- coldstart/load decisions now use governed runtime mode only:
  - `ACM_BaselineGovernance.RuntimeMode`
  - then `ACM_Runs.RepresentationRuntimeMode`
  - else safe default: baseline formation

What ACM is not yet:

- fully representation-first from the earliest possible stop point
- fully complete in operator-facing dashboards
- forecast / RUL governed end-to-end
- fully stripped of transitional legacy owners

## Latest Validated Runtime Truth

Latest live 3-asset validation, run in parallel with observability disabled:

| Asset | RunID | Result | What it proved |
|---|---|---|---|
| `FD_FAN` | `46b1cb4b-f983-4e2c-acf5-1e54a0a58e8e` | `NOOP` | governed-only coldstart/load authority still exits cleanly when no governed row exists yet |
| `WFA_TURBINE_0` | `31c85cfe-5724-4712-9bdb-209702ca4238` | `DEGRADED` | later pre-transient suppression path still works under governed baseline formation |
| `WFA_TURBINE_10` | `22f34578-ee55-4a9a-b4c0-55ba9eb9da40` | `DEGRADED` | cached feature-preview suppression path still works under governed baseline formation |

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
| `FD_FAN` | `NULL in governed columns for this NOOP path` | `NULL` | `NULL` | `NULL` | `NULL` | `0` |
| `WFA_TURBINE_0` | `BASELINE_FORMATION` | `COLLECTING_TRUSTED_WINDOW` | `LEARNING_ALLOWED` | `0` | `1` | `0` |
| `WFA_TURBINE_10` | `BASELINE_FORMATION` | `COLLECTING_TRUSTED_WINDOW` | `LEARNING_ALLOWED` | `0` | `0` | `0` |

This means:

- runtime and replay now agree on governed coldstart/load authority
- assets can still land in different valid governed states during baseline formation
- score tables remain correctly empty when score output is not allowed

## What Was Completed Recently

Recent validated slices:

| Commit | Summary |
|---|---|
| `current pending runtime commit` | remove lifecycle fallback from governed coldstart/load decisions |
| `a9ee9c0` | prefer governed coldstart status in runtime and runner |
| `add8f03` | remove retry semantics from smart coldstart |
| `22628a3` | trim dead smart coldstart helper state |
| `7310955` | remove dead smart-coldstart retry API |
| `c83e630` | replace coldstart load boolean with explicit decision |

Net effect of recent slices:

- runtime no longer depends on hidden lifecycle meaning inside `smart_coldstart`
- runner coldstart progression now uses governed coldstart/load authority
- lifecycle fallback is now removed from those load decisions
- public and internal load-stage contracts are explicit instead of boolean-driven
- retry-era `smart_coldstart` naming and dead state are gone
- coldstart / baseline formation is now much closer to a single governed personality

## Remaining Work Burn-Down

| Area | Current state | Remaining | Difficulty |
|---|---|---|---|
| Coldstart / baseline authority | Goverened load authority is in place for runtime and runner | Finish helper-only demotion and trusted-window package evolution; no major authority seams remain | Medium |
| Representation-first runtime ordering | Many governed no-score runs stop before detector / regime work | Push stop conditions earlier than seasonality / raw preview / feature prep where evidence already exists | High |
| Zero-day demotion | Zero-day is non-authoritative on governed no-score runs | Remove remaining alternate-personality feel from runtime summaries and operator surfaces | Medium |
| SQL / control-plane semantics | Governed tables and views are live and useful | Finalize target semantics for `ACM_SignalProfiles` and `ACM_RepresentationSchemas` | Medium |
| Dashboards / operator truth | Governed views exist | Cut Grafana and operator queries over to governed views | High |
| Forecast / RUL | Still mostly legacy | Bring forecast / RUL under governed eligibility and suppression rules | High |
| Legacy deletion | Some obsolete code and tables already removed | Delete remaining transitional owners only after replay-qualified replacement is proven | Medium |

## Biggest Current Blockers

Ordered by importance:

1. Earlier representation-first stop ordering
2. Dashboard / operator cutover
3. Forecast / RUL governed cutover
4. Final trusted-window package evolution
5. Final legacy deletion

The main blocker is no longer coldstart authority cleanup.
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

1. push governed no-score resolution earlier than seasonality / raw preview / feature prep where evidence already exists
2. keep final smart-coldstart helper demotion honest and avoid new wrappers
3. continue targeted validation after each runtime-affecting slice, with 2-3 asset parallel runs only for major semantic changes

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

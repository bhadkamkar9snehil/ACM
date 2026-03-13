# ACM Status Snapshot

Last updated: 2026-03-13 UTC

This file is a rewritten snapshot, not an append-only log.
Each major ACM slice replaces this file with current repo and runtime truth.

## At A Glance

| Item | Current value |
|---|---|
| Overall `2026.2` completion | `88%` |
| Architecture / ownership extraction | `91%` |
| Runtime governed behavior | `87%` |
| Coldstart / baseline unification | `94%` |
| SQL / control-plane alignment | `78%` |
| Replay qualification | `88%` |
| Dashboard / operator cutover | `75%` |
| Forecast / RUL governed cutover | `20%` |
| Current branch | `refactor/2026.2-rg-13-audit-hygiene` |
| Latest validated runtime slice | `manifest-only feature-schema preview gate` |

## Time Estimate

| Scope | Estimated remaining time |
|---|---|
| Core ACM runtime unification | `0.5 to 1 focused day` |
| Full `2026.2` completion | `1.5 to 3 focused days` |

The remaining work is now concentrated in:

- earlier representation-first stop ordering on learnable baseline-formation paths
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
- additive-growth/schema-blocked batches now able to stop from a manifest-only feature-schema preview before seasonality and feature preparation
- fleet and observability dashboards now consume governed run-insight views for the top-level operator surface
- the asset-specific master dashboard now uses governed views for its top summary/status panels

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
- the latest major stop-line improvement is a manifest-only feature-schema preview from raw columns before feature-value build
- `grafana_dashboards/acm_fleet_overview.json`, `grafana_dashboards/acm_observability.json`, and their `active/` copies now read governed views instead of only legacy score/health tables
- `grafana_dashboards/acm_master_complete.json` and its `active/` copy now use governed views for current-status summary panels while leaving historical scored panels intact

What ACM is not yet:

- fully representation-first from the earliest possible stop point
- fully complete in operator-facing dashboards; fleet/runtime dashboards and master summary panels are now governed-first, but deeper explanation/history dashboards are still legacy-heavy
- forecast / RUL governed end-to-end
- fully stripped of transitional legacy owners

## Latest Validated Runtime Truth

Latest live 3-asset validation, run in parallel with observability disabled:

| Asset | RunID | Result | What it proved |
|---|---|---|---|
| `FD_FAN` | `a2cc9e19-e1bb-4909-8dfc-1851beb57515` | `NOOP` | governed NOOP path remains clean; no regression from the earlier schema gate |
| `WFA_TURBINE_0` | `5503ffaa-faad-4778-a9e0-1afb1e56d500` | `DEGRADED` | additive-growth/schema-blocked baseline-formation batch now stops from the manifest-only schema gate before seasonality and feature prep |
| `WFA_TURBINE_10` | `d40a7f60-9c4a-461a-81b2-143f59f62aae` | `DEGRADED` | the same earlier schema gate now blocks this path before seasonality and feature prep |

Observed in logs:

- `FD_FAN`
  - clean `NOOP` finalization
- `WFA_TURBINE_0`
  - `Representation authority short-circuited feature, detector, regime, zero-day, and health stages from manifest-only feature-schema preview`
  - no `seasonality.detect`
  - no `Building features`
- `WFA_TURBINE_10`
  - `Representation authority short-circuited feature, detector, regime, zero-day, and health stages from manifest-only feature-schema preview`
  - no `seasonality.detect`
  - no `Building features`

Observed in SQL:

| Asset | Runtime mode | Baseline candidate | Shadow refresh | Schema | Basis | Score allowed | Learn allowed | Score rows |
|---|---|---|---|---|---|---|---|---|
| `FD_FAN` | `NULL in governed columns for this NOOP path` | `NULL` | `NULL` | `NULL` | `NULL` | `NULL` | `NULL` | `0` |
| `WFA_TURBINE_0` | `BASELINE_FORMATION` | `COLLECTING_TRUSTED_WINDOW` | `LEARNING_ALLOWED` | `ADDITIVE_GROWTH` | `PENDING` | `0` | `0` | `0` |
| `WFA_TURBINE_10` | `BASELINE_FORMATION` | `COLLECTING_TRUSTED_WINDOW` | `LEARNING_ALLOWED` | `ADDITIVE_GROWTH` | `PENDING` | `0` | `0` | `0` |

This means:

- runtime and replay still agree on governed coldstart/load authority
- additive-growth/schema-blocked baseline-formation runs now stop much earlier
- score tables remain correctly empty when score output is not allowed
- the next runtime-ordering bottleneck is no longer seasonality on these windows; it is the remaining learnable baseline-formation path and later trusted-window evolution

## What Was Completed Recently

Recent validated slices:

| Commit | Summary |
|---|---|
| `pending current operator commit` | cut master dashboard summary panels over to governed views |
| `03b6541` | cut fleet and observability dashboards over to governed views |
| `a6b9c44` | add manifest-only feature-schema preview before feature build |
| `7eb012b` | add cheap unadjusted raw preview gate |
| `f093677` | remove local coldstart completion semantics |
| `7ef15a6` | remove lifecycle fallback from coldstart authority |
| `a9ee9c0` | prefer governed coldstart status in runtime and runner |
| `add8f03` | remove retry semantics from smart coldstart |

Net effect of recent slices:

- runtime no longer depends on hidden lifecycle meaning inside `smart_coldstart`
- runner coldstart progression now uses governed coldstart/load authority
- additive-growth/schema-blocked no-score runs now stop from a manifest-only preview before seasonality / feature prep
- the fleet/runtime operator surface is now governed-first through the fleet, observability, and master-summary dashboards
- the main runtime-ordering problem has moved deeper into the remaining learnable baseline-formation path, while the remaining operator gap is the deeper asset-specific history/explanation dashboard family

## Remaining Work Burn-Down

| Area | Current state | Remaining | Difficulty |
|---|---|---|---|
| Coldstart / baseline authority | Governed load authority is in place for runtime and runner | Finish helper-only demotion and trusted-window package evolution; no major authority seams remain | Medium |
| Representation-first runtime ordering | Many governed no-score runs now stop before seasonality / feature prep | Push stop conditions earlier on the remaining learnable baseline-formation and trusted-window paths | High |
| Zero-day demotion | Zero-day is non-authoritative on governed no-score runs | Remove remaining alternate-personality feel from runtime summaries and operator surfaces | Medium |
| SQL / control-plane semantics | Governed tables and views are live and useful | Finalize target semantics for `ACM_SignalProfiles` and `ACM_RepresentationSchemas` | Medium |
| Dashboards / operator truth | Fleet and observability dashboards now use governed views, and master summary panels are governed-first | Finish deeper asset-specific history/explanation dashboard cutover and retire legacy score-first operator assumptions | High |
| Forecast / RUL | Still mostly legacy | Bring forecast / RUL under governed eligibility and suppression rules | High |
| Legacy deletion | Some obsolete code and tables already removed | Delete remaining transitional owners only after replay-qualified replacement is proven | Medium |

## Biggest Current Blockers

Ordered by importance:

1. Remaining late cost on learnable baseline-formation runtime
2. Forecast / RUL governed cutover
3. Remaining asset-specific history/explanation dashboard cutover
4. Final trusted-window package evolution
5. Final legacy deletion

The main blocker is no longer coldstart authority cleanup.
The main blocker is finishing runtime ordering on the remaining expensive baseline-formation path, then bringing the remaining deeper asset-specific/operator surfaces and forecast stack under governed ACM.

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

1. push governed no-score resolution earlier on the remaining learnable baseline-formation paths
2. keep final smart-coldstart helper demotion honest and avoid new wrappers
3. continue targeted validation after each runtime-affecting slice, with 2-3 asset parallel runs only for major semantic changes

After that:

4. finish SQL / control-plane semantic cleanup
5. finish the remaining asset-specific history/explanation dashboard cutover
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

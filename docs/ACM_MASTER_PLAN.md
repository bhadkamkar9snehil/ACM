---
type: canonical-plan
status: canonical
version: 2026.2.0-draft
updated: 2026-03-12
tags: [acm, master-plan, system-design, runtime, release-2026.2]
supersedes:
  - docs/NewPlan12032026.md
  - docs/obsidian_vault/knowledge/Plan-Zero-Day-Implementation.md
  - docs/archive/Major Refactor Plan.md
---

# ACM Master System Design and Delivery Plan

This document is the single source of system design truth for ACM.

It is the only planning document with normative authority.

All other plan, design, debt, and audit documents are reference-only background unless this document explicitly says otherwise.

If another document conflicts with this one, this document wins.

## Document contract

This document owns four things:

1. the non-negotiable system design rules
2. the current runtime truth
3. the single prioritized backlog
4. the release and rollout gates

This document does not duplicate deep audit evidence.

Audits, debt reviews, and historical plans may remain in the repo, but they are not allowed to define current design truth or active implementation priority.

## Documentation cleanup plan

The repo must enforce a clean boundary between canonical project documentation and the local Obsidian knowledge workspace.

Cleanup will proceed as follows:

1. keep all active planning and system-design authority in tracked top-level `docs/`
2. keep `docs/ACM_MASTER_PLAN.md` as the only normative planning document
3. move any remaining live planning content out of `docs/obsidian_vault/` into tracked canonical docs if it still has operational value
4. reduce vault planning files to either redirects, reference notes, or generated knowledge artifacts
5. keep `docs/obsidian_vault/` for graph navigation, agent memory, code references, and manual investigation notes only
6. mark historical documents in `docs/archive/` as non-authoritative and link them back to this master plan
7. reject new planning documents that create a second source of truth instead of extending this one

The target end state is simple:

- `docs/` contains authoritative project documentation
- `docs/obsidian_vault/` contains supporting local knowledge and graph material
- `docs/archive/` contains historical reference only

## Versioning scheme

ACM major release trains now use a calendar-half scheme with semver-compatible patching:

`YYYY.H.PATCH[-stage]`

Where:

- `YYYY` = target release year
- `H` = half-year release train: `1` for first half, `2` for second half
- `PATCH` = patch or service release within that train, starting at `0`
- `-stage` = optional prerelease suffix such as `draft`, `alpha.N`, `beta.N`, or `rc.N`

Examples:

- `2026.2.0-draft` = planning and design stage for the second-half 2026 major line
- `2026.2.0-rc.1` = first release candidate for that line
- `2026.2.0` = first production release in that line
- `2026.2.1` = first patch release on that line
- `2027.1.0` = next half-year major train

This is better than `26H2` because it:

- sorts naturally
- is semver-like enough for tooling and release notes
- keeps the half-year train explicit
- leaves room for patch and prerelease cadence

The major refactor defined in this document belongs to the `2026.2` release line.

## Source control strategy

`main` stays untouched until the `2026.2` line is replay-qualified, SQL-qualified, and ready for controlled release.

The repo should use a two-track model:

1. maintain the active runtime stabilization line separately
2. build `2026.2` on a dedicated integration branch with short-lived execution branches underneath it

### Current branch roles

The current repo reality is:

- `feature/v11-17-zero-day-system` is the active runtime stabilization line
- `main` must not become the staging area for the representation-governance refactor
- `integration/2026.2-representation-governance` is the long-lived integration branch for this refactor

This means:

- zero-day stabilization and urgent runtime safety fixes continue on the runtime line
- the major refactor happens on the `2026.2` integration line
- `main` only receives the refactor after replay signoff and release readiness

### Branch hierarchy

Use the following branch classes:

- `main`
  - protected release branch
  - no direct `2026.2` development
- `feature/v11-17-zero-day-system`
  - runtime stabilization branch for the current live line
  - source of urgent bug fixes that may need to be forward-merged into `2026.2`
- `integration/2026.2-representation-governance`
  - long-lived branch for the full major refactor
  - the only integration target for `2026.2` delivery slices
- short-lived slice branches from the integration branch
  - `refactor/2026.2-rg-02-representation-contracts`
  - `refactor/2026.2-rg-04-time-normalizer`
  - `refactor/2026.2-rg-10-baseline-governor`
  - `docs/2026.2-plan-tightening`
  - `test/2026.2-replay-hardening`

### Branching rules

1. do not branch `2026.2` work from `main`
2. branch all `2026.2` implementation slices from `integration/2026.2-representation-governance`
3. keep one branch per delivery slice or tightly related change set
4. merge completed slices back into the integration branch only after tests for that slice pass
5. merge to `main` only from the integration branch, never from a slice branch
6. if a production-safety fix lands on the runtime branch, forward-merge or cherry-pick it into the integration branch quickly so the lines do not drift invisibly
7. do not let planning-only commits and runtime code commits mix unless the documentation change is inseparable from the code change

### Commit discipline

Commits in the `2026.2` line should be slice-scoped and auditable.

Good commit shapes:

- `docs(2026.2): add file-by-file execution playbook`
- `refactor(rep): add representation contracts and pipeline shell`
- `refactor(time): extract timestamp normalization owner`
- `feat(rep-sql): add representation control-plane tables and store`
- `test(rep): add replay and gating coverage for comparability engine`

Bad commit shapes:

- catch-all commits that mix migrations, dashboards, docs, runtime fixes, and refactor code without one clear purpose
- commits that move ownership and cut authority in the same change without a shadow phase

### Merge policy

The merge path for `2026.2` should be:

1. slice branch
2. `integration/2026.2-representation-governance`
3. release qualification and replay signoff
4. controlled merge into `main`

Merge expectations:

- every slice branch must state which `RG-*` or `ZD-*` items it closes
- every slice branch must update this master plan if scope, sequencing, or gates change
- every merge into the integration branch must leave the branch runnable
- authority-shift merges must be separate from extraction-only merges whenever possible

### Hotfix and backport policy

Urgent fixes discovered during `2026.2` work should follow this rule:

1. if the fix protects the active runtime, land it on `feature/v11-17-zero-day-system` first
2. then forward-merge or cherry-pick it into `integration/2026.2-representation-governance`
3. do not fix the integration branch only and assume the active runtime is safe

If a fix is purely `2026.2` scaffolding and does not apply to the live runtime, it stays on the integration path only.

### Tagging and milestones

Use tags to keep the major refactor auditable:

- continue patch tags for the runtime line as `v11.17.x`
- tag integration milestones when major gates are reached:
  - `2026.2.0-alpha.1` after contracts, normalization, and state shadowing are integrated
  - `2026.2.0-beta.1` after SQL dual-write and replay validation are stable
  - `2026.2.0-rc.1` after authoritative gating is validated
  - `2026.2.0` only when the release gates in this plan are closed

### Dirty-worktree rule

This repo often carries concurrent docs, dashboards, SQL, and runtime changes.

To avoid accidental cross-contamination:

1. inspect `git status` before starting each slice
2. if unrelated local changes exist, either commit them on the correct branch first or create a new slice branch without broadening scope
3. do not bundle unrelated dashboard, vault, or SQL view edits into a representation-governance code slice unless they are required for that slice
4. before opening or merging a slice, verify that only intentional files changed for that slice

### Definition of good source control practice for `2026.2`

For this refactor, proper source control means:

- `main` remains protected and boring
- the active runtime line remains supportable while the refactor proceeds
- the refactor has one integration branch
- each slice is isolated, reviewable, and replay-testable
- hotfixes flow forward from the runtime line into the refactor line
- no authority cutover happens in the same step as an unvalidated extraction if that can be avoided

## Non-negotiable system design rules

The following rules are binding.

1. ACM is a state-consistency engine, not a fault classifier.
2. ACM must answer questions in this order: context, consistency, persistence, then risk.
3. If ACM cannot answer a stage reliably, it must degrade or suppress downstream decisions rather than force an answer.
4. Online and offline responsibilities must remain separate. Online batch scoring may assign or degrade; it may not silently redefine historical truth.
5. Cold start is a first-class state and must never be hidden.
6. `unknown`, `emerging`, `ambiguous`, or `non-comparable` are valid internal context outcomes.
7. Run outcomes remain `OK`, `DEGRADED`, `NOOP`, `FAIL`.
8. Train-score separation is absolute. A batch may not influence its own baseline, comparability envelope, or anomaly score.
9. Episodes are the only alerting unit. Point scores are evidence, not decisions.
10. RUL is optional and may be suppressed when prerequisites fail.
11. Detector-specific feature engineering is not the system representation contract.
12. Representation validity requires all of: temporal normalization, structural compatibility, contextual comparability, trust qualification, and baseline compatibility.

## Current runtime truth

The active runtime today is the `v11.17.x` zero-day overlay on the legacy ACM pipeline.

What is already true in code:

- the runtime entrypoint remains `python -m core.acm`
- tag-agnostic regime basis selection is live
- tag-agnostic transient-state logic is live
- EWM uses an explicit raw monitoring surface
- `OnlinePCABinner` is the early online context proxy before mature HDBSCAN labels exist
- regime state and EWM state are version-gated
- run outcomes remain `OK`, `DEGRADED`, `NOOP`, `FAIL`

What is not yet closed:

- replay validation on the latest runtime across the target assets
- SQL persistence verification for the current zero-day artifacts
- operator rollout/runbook closure for non-validation environments
- consolidation of scattered representation-governance logic into one owner layer

## Current runtime owners

The current runtime still spreads representation-adjacent responsibilities across multiple modules:

| Responsibility | Current owners |
|---|---|
| raw historian load and timestamp normalization | `core/data_loader.py`, `core/smart_coldstart.py` |
| basic guardrails and contract validation | `core/pipeline_types.py` |
| detector feature engineering | `core/fast_features.py` |
| tag-agnostic basis and context labeling | `core/regimes.py` |
| detector fit/load/calibration bootstrap | `core/detector_orchestrator.py`, `core/model_persistence.py`, `core/fuse.py` |
| baseline contamination and lifecycle gates | `core/detector_orchestrator.py`, `core/model_lifecycle.py` |
| EWM freeze and day-0 baseline behavior | `core/ewm_baseline.py` |
| output persistence | `core/output_manager.py` |

This split ownership is the core design debt that `2026.2` must resolve.

## Problem statement

ACM needs a first-class representation-governance layer that converts historian telemetry into governed asset-time states that downstream logic can trust.

That layer must be:

- asset-agnostic
- reusable across detectors and models
- explicit about context confidence and comparability
- explicit about schema compatibility
- explicit about baseline compatibility and learning eligibility
- persisted as operational metadata, not just in-memory vectors

The problem is not "add more features."

The problem is "create a governed, reusable asset-time state contract that all unsupervised ACM capabilities can consume safely."

## Target 2026.2 architecture

`2026.2` introduces a single representation-governance pipeline in front of downstream scoring.

### Target pipeline

1. load raw historian rows
2. normalize observations onto a governed time grid
3. profile signal quality and monitorability
4. build windowed state snapshots keyed by batch end
5. apply canonical feature schema and structure encoding
6. assign context and context confidence
7. evaluate comparability, score eligibility, and learn eligibility
8. if scoreable, pass governed state to detectors and fusion
9. if not scoreable, emit degraded metadata and suppress scoring
10. evaluate baseline update/adaptation candidacy
11. persist representation status, baseline governance, and downstream outputs

### New owner modules

| Module | Responsibility |
|---|---|
| `core/representation_contracts.py` | typed contracts for observations, signal profiles, states, context, comparability, baseline governance, reason codes |
| `core/time_normalizer.py` | timestamp parsing, deduplication, cadence inference, resampling, fill policy, stale policy, coverage metrics |
| `core/signal_profiler.py` | per-tag quality, weak-signal decisions, monitorability summary |
| `core/state_builder.py` | fixed-window state snapshots keyed by batch end |
| `core/feature_schema.py` | canonical descriptor families, schema versioning, required vs optional features |
| `core/structure_encoder.py` | tag-agnostic numeric surface, scaling, basis versioning, structural descriptors |
| `core/context_engine.py` | context assignment, confidence, novelty, transition and ambiguity handling |
| `core/comparability_engine.py` | `score_allowed`, `learn_allowed`, degraded reasons, trust thresholds |
| `core/baseline_governor.py` | bootstrap readiness, baseline eligibility, contamination protection, freeze/update rules, shadow refresh |
| `core/schema_drift_manager.py` | schema change detection, compatibility classes, downgrade behavior |
| `core/representation_store.py` | SQL persistence of representation artifacts |
| `core/representation_pipeline.py` | orchestration wrapper for the representation-governance layer |

## Repository assessment

This section records the current repo assessment against the `2026.2` target.

It is intentionally strict.

If a responsibility is only implied in helper logic and not carried by an explicit runtime contract, that responsibility is treated as partial.

### Executive conclusion

- A true representation-governance layer is not present today.
- The repo contains several useful fragments of the target design, but they are materially fragmented across loading, feature preparation, regimes, lifecycle, persistence, and zero-day baseline logic.
- The single biggest analytical risk is that detector scoring becomes authoritative before contextual comparability is explicitly decided.
- The single biggest ownership problem is that `core/regimes.py` currently owns structure encoding, context confidence, novelty handling, transient logic, cached-basis compatibility checks, stage orchestration, and regime-state persistence instead of just regime-specific behavior.

### Conformance to the current master plan

Aligned with current runtime truth:

- `python -m core.acm` remains the active entrypoint.
- Tag-agnostic regime basis selection is live.
- Tag-agnostic transient-state logic is live.
- EWM uses an explicit raw monitoring surface.
- `OnlinePCABinner` is the early online context proxy.
- Regime state and EWM state are version-gated.
- Run outcomes remain `OK`, `DEGRADED`, `NOOP`, `FAIL`.

Only partially aligned:

- Observation normalization exists, but not as a first-class integrity contract.
- Data quality and weak-signal logic exists, but only as guardrails and summaries.
- Schema compatibility exists, but not as a first-class drift manager.
- Baseline contamination, lifecycle, freeze, and refit controls exist, but not under one authority.
- Context confidence and novelty exist, but not as authoritative score-gating inputs.

Architecturally in conflict with the target:

- Detector scoring occurs before an authoritative comparability decision.
- Novel points are still forced into some regime label instead of yielding a first-class non-comparable context.
- Silent continuation exists through zero-fill and feature-intersection paths.
- The current runtime has implied modes, not an explicit operating-mode contract.

### Responsibility assessment matrix

| Responsibility | Current implementation points | Status | Ownership quality | Analytical risk | Recommended target owner |
|---|---|---|---|---|---|
| observation normalization | `core/data_loader.py`, `core/smart_coldstart.py`, `core/fast_features.py` | partial | scattered | no explicit coverage, stale ratio, or fill-policy contract | `core/time_normalizer.py` |
| signal qualification | `core/pipeline_types.py`, `core/output_dataframe_builders.py`, persisted low-variance artifact logic | partial | scattered and partly wrong | weak-signal policy is not queryable or centrally governed | `core/signal_profiler.py` |
| windowed state construction | `core/fast_features.py` rolling feature flow | partial | wrong | rolling features are not governed asset-time states | `core/state_builder.py` |
| geometry stabilization / structure encoding | `core/regimes.py::select_tag_agnostic_numeric_surface`, `build_feature_basis`, `select_ewm_monitoring_surface` | present but partial | wrong | good implementation under the wrong long-term owner | `core/feature_schema.py` and `core/structure_encoder.py` |
| context assignment | `core/regimes.py::predict_regime_with_confidence`, `label`, transient logic | partial | wrong | context semantics are tied to regime ownership and not reusable | `core/context_engine.py` |
| comparability / score gating | implied through novelty flags, lifecycle checks, and degradations | missing as first-class contract | wrong | scores can be produced without a governed comparability verdict | `core/comparability_engine.py` |
| baseline governance | `core/smart_coldstart.py`, `core/detector_orchestrator.py`, `core/model_lifecycle.py`, `core/ewm_baseline.py`, `core/model_evaluation.py` | partial | scattered | readiness, contamination, freeze, refit, and promotion can diverge | `core/baseline_governor.py` |
| schema drift governance | `core/model_persistence.py`, `core/detector_orchestrator.py`, `core/regimes.py` | partial | scattered | some paths retrain, others subset, others zero-fill | `core/schema_drift_manager.py` |
| governance outputs | `core/output_manager.py`, `core/run_metadata_writer.py`, `core/output_contracts.py` | partial | wrong | no persisted representation status or scoreability contract | `core/representation_store.py` |

### Runtime mode assessment

The repo does not currently implement a clean and enforceable operating-mode model.

It has scattered rules that imply modes, but no first-class runtime-mode contract that downstream logic must obey.

| Runtime mode | Current implementation points | Current authority owner(s) | Gaps | Risks | Target authority owner |
|---|---|---|---|---|---|
| Bootstrap / Not Ready | `SmartColdstart.check_status`, `load_with_retry`, NOOP finalization | `core/smart_coldstart.py`, `core/run_metadata_writer.py`, `core/acm.py` | readiness is tied to coldstart and model presence, not governed state quality | insufficient-history states do not emit a typed representation status | `core/baseline_governor.py` |
| Baseline Formation | coldstart split, baseline seeding, detector fit, contamination check, lifecycle creation | `core/data_loader.py`, `core/smart_coldstart.py`, `core/detector_orchestrator.py`, `core/model_lifecycle.py` | no single baseline package contract, no trusted-window selector, no explicit freeze candidate state | baseline semantics are spread across unrelated runtime modules | `core/baseline_governor.py` |
| Online Scoring | `core.acm` main flow, cached model load, scoring, fusion, EWM scoring | `core/acm.py`, `core/regimes.py`, `core/fuse.py`, `core/ewm_baseline.py` | no governed asset-time state object, no authoritative pre-score comparability gate | non-comparable states can still be scored | `core/comparability_engine.py` |
| Controlled Adaptation | auto-retrain, refit requests, auto-tune, lifecycle promotion | `core/model_evaluation.py`, `core/model_persistence.py`, `core/model_lifecycle.py` | no shadow-refresh mode, no explicit separation between scoring authority and adaptation authority | silent or poorly bounded adaptation can leak into runtime truth | `core/baseline_governor.py` |
| Schema Break / Requalification | cache validity checks, feature alignment, regime basis mismatch -> refit | `core/model_persistence.py`, `core/detector_orchestrator.py`, `core/regimes.py` | no explicit requalification mode, no persisted compatibility class, no standard degrade path | silent continuation and inconsistent retrain behavior | `core/schema_drift_manager.py` |

### Schema drift and signal-loss assessment

Schema drift is not first-class today.

Current handling is fragmented and inconsistent:

| Drift event | Current handling | Current risk | Target handling |
|---|---|---|---|
| temporary tag loss | cached feature alignment may reduce to intersection in `align_current_features_to_cached_manifest()` | temporary loss can silently narrow the feature space | classify as temporary compatibility downgrade with explicit reason code |
| permanent tag loss | current behavior looks like feature mismatch, retrain, or subset continuation depending path | no explicit distinction from temporary loss | classify as persistent schema break requiring requalification or package downgrade |
| new tag appearance | cache invalidation occurs in some detector paths when extra features appear | behavior depends on owner module, not one contract | classify as additive schema evolution; do not let it silently redefine current authority |
| feature invalidation from upstream signal loss | low-variance and all-NaN pruning occurs during feature prep; regime basis paths also reindex/fill | upstream signal loss can masquerade as a valid feature vector | propagate invalidated-feature set into schema and comparability decisions |
| basis/schema incompatibility | regime basis mismatch forces refit; detector cache compatibility is separately checked | basis compatibility is not uniformly governed across the runtime | persist schema class, basis class, and downgrade reason together |
| silent continuation on partial inputs | `reindex(..., fill_value=0.0)` in regime prediction and feature intersection alignment in model loading | missing information can be turned into synthetic comparability | prohibit authoritative continuation without an explicit compatibility verdict |

### Conflict register

| Issue | Current locations | Why analytically wrong or fragile | Impact | Required fix |
|---|---|---|---|---|
| detector scoring happens before comparability is decided | `core/regimes.py::run_scoring_regime_stage` | stage order allows scores before governed context/comparability | non-comparable states can still emit detector outputs | move score authority behind `core/comparability_engine.py` |
| novel points are always assigned to a valid regime | `core/regimes.py::predict_regime_with_confidence` | novelty is annotation only, not a gating outcome | ambiguous context gets forced into a comparable-looking label | let `core/context_engine.py` emit explicit `unknown`, `ambiguous`, or `non-comparable` |
| regime prediction zero-fills missing basis columns | `core/regimes.py::predict_regime`, `predict_regime_with_confidence`, `label` | synthetic zeros mask missing structure | schema loss can look like valid state continuity | replace with explicit schema/basis compatibility classes |
| cached-model feature alignment can continue on intersections | `core/model_persistence.py::align_current_features_to_cached_manifest` | partial feature sets can silently continue | temporary and permanent tag loss are not cleanly separated | route all such decisions through `core/schema_drift_manager.py` |
| weak-signal exclusion is file-based and local | `core/pipeline_types.py::run_data_guardrails`, `core/data_loader.py` | canonical input policy depends on local JSON artifacts | hidden input mutation outside SQL control-plane visibility | move to SQL-backed `core/signal_profiler.py` and persisted reason codes |
| baseline governance is split across many modules | coldstart, contamination, lifecycle, EWM freeze, auto-retrain | one analytical responsibility has multiple runtime authorities | partial implementations can bite later during cutover | centralize in `core/baseline_governor.py` |
| online scoring mutates state directly | EWM update/save, binner observe/save, same-run retrain flow | scoring and adaptation are not cleanly separated | violates the target no-silent-learning model | make adaptation explicit, shadow-first, and promotable |
| operator-facing suppression contract is missing | `core/output_manager.py`, `core/run_metadata_writer.py` | suppression and degrade reasons are not stored as a first-class queryable contract | operators must infer meaning from logs or missing rows | persist `ACM_RepresentationStatus` and related governance tables |

## Canonical backlog

There is one backlog.

It has two workstreams:

- close the currently active zero-day runtime validation
- deliver the `2026.2` representation-governance extraction

The zero-day workstream is first because `2026.2` is not allowed to become authoritative on top of an unclosed runtime validation plan.

### Workstream A: Close the active zero-day runtime

| ID | Task | Priority | Depends On | Exit criteria |
|---|---|---|---|---|
| ZD-01 | Fresh replay of `WFA_TURBINE_10` on latest runtime | P0 | None | replay completes end to end and transient labels match the current contract |
| ZD-02 | SQL verification for `ACM_EWMBaseline`, `ACM_RegimeBinnerState`, `ACM_Runs`, `ACM_RunLogs` | P0 | ZD-01 | no schema/version mismatch and continuity is confirmed |
| ZD-03 | Replay `WFA_TURBINE_11` | P0 | ZD-02 | replay completes with expected day-0 behavior and no critical degradations |
| ZD-04 | Replay `WFA_TURBINE_21` | P0 | ZD-02 | replay completes with expected day-0 behavior and no critical degradations |
| ZD-05 | Per-regime threshold tuning | P1 | ZD-01, ZD-03, ZD-04 | threshold logic validated against replay outputs |
| ZD-06 | Non-validation environment rollout runbook | P1 | ZD-02 | runbook covers migrations, config refresh, and state cleanup policy |
| ZD-07 | Optional stale-state cleanup procedure | P2 | ZD-06 | cleanup is executed or explicitly waived per environment |

### Workstream B: Deliver the 2026.2 representation-governance layer

| ID | Task | Priority | Depends On | Exit criteria |
|---|---|---|---|---|
| RG-01 | Freeze current runtime invariants and replay fixtures | P0 | None | regression harness approved |
| RG-02 | Add representation contracts | P0 | RG-01 | typed contracts import cleanly |
| RG-03 | Add representation pipeline shell | P0 | RG-02 | pipeline can run in no-op/shadow mode |
| RG-04 | Extract time normalizer | P0 | RG-02 | shadow output matches current behavior |
| RG-05 | Build signal profiler | P0 | RG-04 | monitorability summary available |
| RG-06 | Build state builder | P0 | RG-04 | deterministic `StateSnapshot` exists per batch |
| RG-07 | Build feature schema and structure encoder | P1 | RG-06 | explicit schema and basis versioning active |
| RG-08 | Build context engine | P1 | RG-07 | context assignment and confidence available |
| RG-09 | Build comparability engine in shadow mode | P1 | RG-08 | `score_allowed` and `learn_allowed` persist in shadow |
| RG-10 | Build baseline governor | P1 | RG-05, RG-09 | readiness, contamination, freeze, and update decisions share one contract |
| RG-11 | Build schema drift manager | P1 | RG-07 | compatibility classes and downgrade reasons emitted |
| RG-12 | Add representation SQL tables and store | P1 | RG-09, RG-10, RG-11 | new tables are written on replay with idempotency coverage |
| RG-13 | Enable authoritative representation gating for `2026.2` | P0 | ZD-01, ZD-02, ZD-03, ZD-04, RG-12 | non-comparable states no-score correctly and queryably |
| RG-14 | Remove legacy duplicate ownership | P1 | RG-13 | old policy paths deleted without replay regression |
| RG-15 | Update dashboards and runbook | P2 | RG-12 | operators can interpret new statuses and suppression reasons |

## Hard release gates

These gates are mandatory.

| Gate | What it blocks | Condition |
|---|---|---|
| G1 | `2026.2` authoritative cutover | `ZD-01` through `ZD-04` complete |
| G2 | any score suppression behavior | suppressed reason is persisted, queryable, and visible in run metadata |
| G3 | new SQL table rollout | write contract, migration, idempotency test, and rollback path all exist |
| G4 | legacy owner deletion | replacement owner is replay validated and explicitly covered by tests |
| G5 | baseline policy cutover | contamination verdict, readiness, freeze, learn eligibility, and promotion share one contract |
| G6 | context-conditioned gating | context confidence and ambiguity are persisted and replay validated |

## Anti-partial-implementation rules

The following states are forbidden:

- code merged without tests for the changed behavior
- new SQL writes without rollback and idempotency coverage
- new owner modules added while decision authority still lives in the old path
- score suppression enabled before operators can query the reason
- baseline governance centralized without centralizing contamination, freeze, learn eligibility, and promotion together
- legacy path deletion before a replay-qualified replacement exists
- changing current zero-day semantics while zero-day validation tasks remain open

## Detailed implementation plan

This section expands the canonical backlog into the required execution sequence.

The sequencing rule is strict:

1. extract without semantic change
2. run in shadow
3. dual-write and validate
4. shift authority only after replay signoff
5. delete legacy ownership only after replacement authority is proven

### Phase 0: Freeze current runtime truth

Maps to `ZD-01` through `ZD-04` and `RG-01`.

Objective:

- freeze the current `v11.17.x` runtime behavior that `2026.2` must not regress

Required work:

- define replay fixtures and target assets as the non-regression corpus
- capture expected outputs for coldstart, cached-model scoring, regime-basis degradation, EWM fallback, and contaminated-baseline scenarios
- freeze current run-outcome semantics, zero-day status semantics, and SQL artifacts as the baseline contract
- identify current dashboards and operator queries that must keep working during shadow mode

Must not happen in this phase:

- no ownership movement
- no new score suppression behavior
- no SQL cutover

Exit criteria:

- replay corpus approved
- current runtime invariants documented and queryable
- legacy outputs accepted as the shadow-comparison baseline

### Phase 1: Create contracts and pipeline shell

Maps to `RG-02` and `RG-03`.

Objective:

- add the explicit contract layer and orchestration shell without changing runtime authority

Required modules:

- `core/representation_contracts.py`
- `core/representation_pipeline.py`

Required work:

- define typed contracts for observation integrity, signal profile, state snapshot, context assignment, compatibility status, eligibility decision, baseline governance, and reason codes
- define a top-level representation pipeline result object that can carry shadow outputs even when no scoring change occurs
- add a no-op integration point in `core.acm` that can execute the pipeline in shadow mode and return typed artifacts

What should move here:

- typed result semantics currently scattered across `DataMeta`, `GuardrailResult`, regime confidence payloads, and degradation reason strings

What must not move yet:

- no normalization logic
- no detector logic
- no SQL authority shift

Exit criteria:

- the contracts import cleanly
- the representation pipeline can run in no-op or shadow mode
- existing runtime behavior is unchanged

### Phase 2: Extract observation normalization

Maps to `RG-04`.

Objective:

- create one authoritative normalization owner for observation-level integrity

Required module:

- `core/time_normalizer.py`

Required work:

- move timestamp parsing, timezone stripping, future filtering, duplicate removal, cadence inference, anti-upsample protection, resampling, and fill-policy handling into one module
- add explicit outputs for coverage ratio, stale ratio, missingness grade, duplicate count, future-row count, effective cadence, and fill method
- keep train-score separation intact while normalizing both windows against the same governed contract

Primary extraction sources:

- `core/data_loader.py`
- `core/fast_features.py::ensure_local_index` and `deduplicate_index`
- `core/smart_coldstart.py::load_and_validate_data_stage`

Must not happen in this phase:

- no weak-signal exclusions
- no regime-specific logic
- no score gating

Exit criteria:

- shadow normalization output matches current runtime behavior
- normalization integrity metrics are explicit and typed
- all call sites use the same normalization owner

### Phase 3: Build signal profiling and governed input integrity

Maps to `RG-05`.

Objective:

- promote signal qualification from summary guardrails to a reusable and persisted control-plane contract

Required module:

- `core/signal_profiler.py`

Required work:

- implement per-signal missingness, flatline, low-variance, intermittency, effective cadence, spike/noise tendency, and monitorability classification
- replace local artifact-driven low-variance exclusion as the future policy source
- emit asset-level monitorability rollups used by downstream readiness and comparability decisions

Primary extraction sources:

- `core/pipeline_types.py`
- `core/output_dataframe_builders.py`
- low-variance artifact logic currently split across `core/pipeline_types.py` and `core/data_loader.py`

Must not happen in this phase:

- no permanent authority cutover away from current guardrails
- no detector-facing feature pruning based only on profiler output

Exit criteria:

- shadow signal profiles are available per run
- monitorability summary is queryable
- profiler outputs can explain why a signal is not trusted

### Phase 4: Build governed state snapshots

Maps to `RG-06`.

Objective:

- create a first-class asset-time state object keyed by batch end

Required module:

- `core/state_builder.py`

Required work:

- define the canonical `StateSnapshot` construction flow from normalized observations plus signal profiles
- compute source-window identity, effective signal count, integrity grades, and state timestamps
- ensure deterministic batch-end identity so replays produce stable state keys

Primary extraction sources:

- `core/fast_features.py::run_feature_preparation_stage`
- current train/score window handling in `core.acm`

Must not happen in this phase:

- do not call rolling detector features the canonical state
- do not bind the state contract to one detector family

Exit criteria:

- every batch can produce deterministic state snapshots in shadow mode
- the state object exists even when downstream scoring is skipped

### Phase 5: Extract schema ownership and structure encoding

Maps to `RG-07`.

Objective:

- separate reusable structural representation from regime ownership

Required modules:

- `core/feature_schema.py`
- `core/structure_encoder.py`

Required work:

- define schema versioning, required vs optional feature families, and invalidated-feature handling
- move tag-agnostic numeric surface selection and basis scaling into a shared structure encoder
- persist basis signatures, scaler parameters, encoder type, and schema metadata
- keep EWM raw monitoring surface selection under the same structural ownership model, even if its downstream consumer remains EWM-specific

Primary extraction sources:

- `core/regimes.py::select_tag_agnostic_numeric_surface`
- `core/regimes.py::build_feature_basis`
- `core/regimes.py::select_ewm_monitoring_surface`
- manifest-compatibility behavior in `core/model_persistence.py`

Must not happen in this phase:

- no clustering ownership migration yet
- no authoritative schema gating yet

Exit criteria:

- schema version and basis signature are explicit
- structure encoding no longer conceptually belongs to `core/regimes.py`

### Phase 6: Extract context semantics

Maps to `RG-08`.

Objective:

- separate context semantics from regime implementation details

Required module:

- `core/context_engine.py`

Required work:

- wrap or extract current context signals: context label, confidence, novelty, transition status, and ambiguity
- preserve current HDBSCAN and binner behavior as input mechanisms, not final long-term owners of context semantics
- explicitly support `unknown`, `emerging`, `ambiguous`, and `non-comparable` as valid context outcomes

Primary extraction sources:

- `core/regimes.py::predict_regime_with_confidence`
- `core/regimes.py::label`
- `core/regimes.py::detect_transient_states`
- `core/regimes.py::apply_transient_state_labels`

Must not happen in this phase:

- no score suppression yet
- no hard replacement of current regime labeling in production authority

Exit criteria:

- context assignment and confidence are available as a typed shadow output
- novelty and ambiguity are explicit context fields, not side annotations only

### Phase 7: Build comparability engine in shadow mode

Maps to `RG-09`.

Objective:

- create the first authoritative place where scoreability and learnability are decided

Required module:

- `core/comparability_engine.py`

Required work:

- combine integrity, context, schema, and baseline inputs into `score_allowed` and `learn_allowed`
- define degraded and suppressed reason codes
- ensure detector scoring authority remains unchanged while the comparability verdict is shadow-only
- persist shadow comparability results for replay analysis

Must not happen in this phase:

- no production suppression of detector scores
- no silent fallback to current behavior without recording the shadow verdict

Exit criteria:

- `score_allowed` and `learn_allowed` exist per batch in shadow mode
- replay can compare current scores against shadow comparability decisions

### Phase 8: Centralize baseline governance

Maps to `RG-10`.

Objective:

- move readiness, contamination, freeze, adaptation, and promotion under one authority

Required module:

- `core/baseline_governor.py`

Required work:

- define explicit baseline modes: bootstrap, baseline formation, online scoring, controlled adaptation, and requalification
- centralize coldstart readiness and insufficient-history handling
- centralize contamination verdicts from fresh detector fits
- centralize EWM freeze and resume semantics
- centralize shadow refresh, learn eligibility, and promotion decisions
- ensure online scoring does not silently redefine authoritative baseline truth

Primary extraction sources:

- `core/smart_coldstart.py`
- `core/detector_orchestrator.py::assess_baseline_contamination`
- `core/model_lifecycle.py`
- `core/ewm_baseline.py`
- `core/model_evaluation.py`

Must not happen in this phase:

- no same-batch baseline mutation becoming more authoritative than today
- no deletion of existing lifecycle writes until replay-qualified replacement exists

Exit criteria:

- one contract owns readiness, contamination, freeze, learn eligibility, and promotion
- runtime modes are explicit and queryable

### Phase 9: Build schema drift manager and representation store

Maps to `RG-11` and `RG-12`.

Objective:

- make compatibility and persistence first-class and queryable

Required modules:

- `core/schema_drift_manager.py`
- `core/representation_store.py`

Required work:

- classify temporary tag loss, permanent tag loss, additive schema growth, invalidated features, basis mismatch, and representation break
- remove silent continuation as a hidden behavior by routing all compatibility decisions through one owner
- add new SQL tables:
  - `ACM_RepresentationStatus`
  - `ACM_SignalProfiles`
  - `ACM_RepresentationSchemas`
  - `ACM_BaselineGovernance`
- add idempotent dual-write behavior and rollback-aware migrations
- extend `core/output_contracts.py` so the new control-plane tables are governed explicitly

Primary extraction sources:

- `core/model_persistence.py`
- `core/detector_orchestrator.py`
- `core/output_manager.py`
- `core/run_metadata_writer.py`

Must not happen in this phase:

- no detector-output cutover away from `ACM_Scores_Wide`
- no deletion of legacy persistence contracts

Exit criteria:

- compatibility classes and downgrade reasons are emitted explicitly
- new tables write idempotently in replay
- operators can query representation state without reading logs

### Phase 10: Replay-qualified authority shift

Maps to `RG-13`.

Objective:

- make representation governance authoritative only after replay signoff

Required work:

- enable authoritative `score_allowed` gating in replay and validation environments first
- confirm that suppressed scoring states are persisted with queryable reasons
- confirm that no unacceptable analytical regressions exist across the replay corpus
- confirm that baseline-governor and schema-drift decisions are visible in SQL and run metadata

Must not happen in this phase:

- no authority shift before `G1` through `G6` are satisfied
- no silent production enablement without runbook and dashboard readiness

Exit criteria:

- non-comparable states correctly no-score
- suppression reasons are queryable
- authoritative gating has replay evidence and operator signoff

### Phase 11: Legacy ownership cleanup and operational rollout

Maps to `RG-14` and `RG-15`.

Objective:

- remove duplicate ownership only after the new owners are fully authoritative

Required work:

- delete duplicated governance logic from legacy paths in `data_loader`, `smart_coldstart`, `regimes`, `model_persistence`, and `output_manager`
- remove file-based weak-signal exclusion once SQL-backed profiling is trusted
- update dashboards, observability queries, and operator runbooks to use representation-governance control-plane outputs
- verify that old dashboards continue to function until their replacements are ready

Exit criteria:

- legacy ownership is unambiguous
- operators can interpret suppressed scoring, degraded runs, baseline freezes, and schema breaks directly from SQL
- replay confirms no regression after duplicate-owner deletion

## File-by-file execution playbook

This section is the executable implementation map for `2026.2`.

An engineer should be able to follow this section and complete the refactor without consulting older plans.

The operating rule is simple:

1. create the new owner first
2. route old code through the new owner without changing authority
3. run in shadow and dual-write
4. shift authority only after replay signoff
5. delete the duplicate legacy owner last

### Implementation discipline

These rules apply to every file change below:

1. new modules must start as extraction or wrapper owners, not as parallel policy engines
2. every extracted responsibility must end with exactly one authoritative owner
3. legacy files may delegate to new owners during transition, but they must not keep silent authority after cutover
4. no SQL table becomes required until migrations, idempotency coverage, and replay validation exist
5. no downstream scoring, health, forecast, or risk stage may act authoritative when `score_allowed = false`
6. detailed batch-level reasons belong in representation tables, not only in logs
7. `core/acm.py` remains the runtime entrypoint; the refactor changes ownership, not the entrypoint

### New modules to create

#### `core/representation_contracts.py`

First touch:

- Phase 1

Purpose:

- define the typed system contract for representation governance
- provide stable enums and dataclasses used by all new owner modules
- remove reliance on loosely shaped dicts, helper tuples, and ad hoc reason strings

Create in this file:

- `RuntimeMode`
- `ObservationIntegrity`
- `SignalProfile`
- `SignalProfileSummary`
- `StateSnapshot`
- `ContextAssignment`
- `CompatibilityStatus`
- `EligibilityDecision`
- `BaselineGovernanceDecision`
- `RepresentationRefs`
- `OperationalGrades`
- `RepresentationPipelineResult`
- reason-code enums for degrade and suppress paths

Extract or normalize semantics currently implied in:

- `core/data_loader.py::DataMeta`
- `core/pipeline_types.py` guardrail and validation result payloads
- `core/regimes.py` confidence and novelty payloads
- `core/run_metadata_writer.py` zero-day status semantics
- lifecycle and degradation reason strings scattered in runtime code

How to implement:

- keep this file dependency-light: `dataclasses`, `enum`, `typing`, `datetime`
- do not import heavy runtime modules, SQL helpers, pandas-specific business logic, or detector code here
- add small serialization helpers only if they are needed by SQL writers or logs
- keep reason-code names stable and explicit because they will become SQL-queryable

Files that must import it:

- `core/acm.py`
- `core/representation_pipeline.py`
- all other new representation-governance modules
- `core/run_metadata_writer.py`
- selected persistence and validation tests

Must not live here:

- resampling logic
- signal-quality scoring math
- regime clustering
- SQL writes
- detector feature engineering

Tests to add:

- `tests/test_representation_contracts.py`

Exit condition for this file:

- all new modules compile against one shared typed contract

#### `core/representation_pipeline.py`

First touch:

- Phase 1

Purpose:

- orchestrate the representation-governance stages in one place
- provide the single shadow-mode hook that `core/acm.py` can call
- separate stage order from stage ownership

Create in this file:

- `run_representation_pipeline(...)`
- stage wrapper methods or pure helper calls for:
  - normalization
  - signal profiling
  - state building
  - schema binding
  - structure encoding
  - context assignment
  - baseline governance
  - schema drift classification
  - comparability decision

How to implement:

- accept raw train and score dataframes plus run metadata, config, equipment identity, and currently active model/package metadata
- return `RepresentationPipelineResult`
- start in shadow-only mode with config control for enabled stages
- make stage outputs explicit even when later stages are skipped
- keep orchestration pure; persistence should be called elsewhere

Files that must change to call it:

- `core/acm.py`

Files that may call it later:

- replay harnesses
- validation scripts
- targeted integration tests

Must not live here:

- SQL write code
- detector scoring
- model promotion decisions beyond calling `baseline_governor`
- ad hoc fallback logic hidden from the returned contract

Tests to add:

- `tests/test_representation_pipeline.py`

Exit condition for this file:

- the full representation-governance chain can run in shadow mode from `core/acm.py`

#### `core/time_normalizer.py`

First touch:

- Phase 2

Purpose:

- become the only owner of observation-level temporal normalization
- make timestamp integrity explicit and reusable

Create in this file:

- functions for timestamp parsing and index normalization
- future-row filtering
- duplicate detection and removal
- cadence inference
- governed resampling
- fill-policy application
- observation-integrity metric computation

Primary extraction sources:

- `core/data_loader.py::parse_ts_index`
- `core/data_loader.py::coerce_local_and_filter_future`
- `core/data_loader.py::check_cadence`
- `core/data_loader.py::resample_df`
- `core/fast_features.py::ensure_local_index`
- `core/fast_features.py::deduplicate_index`
- normalization logic embedded in `core/smart_coldstart.py::load_and_validate_data_stage`

How to implement:

- first move existing logic with behavior parity
- wrap current helper functions in `core/data_loader.py` so call sites stay stable during extraction
- add explicit outputs for coverage ratio, stale ratio, effective cadence, duplicate count, future-row count, observed rows, and expected rows
- keep separate metadata for train and score windows while using one normalization contract
- prohibit hidden upsampling or fill behavior that is not recorded in the returned integrity object

Files that must change:

- `core/data_loader.py`
- `core/fast_features.py`
- `core/smart_coldstart.py`
- `core/representation_pipeline.py`

Must not live here:

- weak-signal policy
- detector features
- regime surface selection
- SQL writes

Tests to add:

- `tests/test_time_normalizer.py`

Exit condition for this file:

- all observation normalization in ACM routes through one owner

#### `core/signal_profiler.py`

First touch:

- Phase 3

Purpose:

- convert signal-quality checks into a reusable, persisted control-plane contract

Create in this file:

- per-signal missingness analysis
- flatline and low-variance analysis
- intermittency and effective-cadence analysis
- spike and noise tendency analysis
- monitorability classification
- asset-level monitorability rollups

Primary extraction sources:

- `core/pipeline_types.py::SensorValidator`
- `core/pipeline_types.py::run_data_guardrails`
- `core/output_dataframe_builders.py::build_data_quality_records`
- file-based low-variance exclusion logic currently read in `core/data_loader.py`

How to implement:

- start by reproducing current low-variance and valid-fraction behavior
- extend the output to include explicit reason codes rather than hidden local artifacts
- emit both per-signal profiles and an asset-level summary
- keep profiler outputs advisory until comparability and baseline governance are ready

Files that must change:

- `core/pipeline_types.py`
- `core/data_loader.py`
- `core/output_dataframe_builders.py`
- `core/representation_pipeline.py`

Must not live here:

- schema compatibility decisions
- detector feature pruning as an implicit side effect
- direct score suppression without `comparability_engine`

Tests to add:

- `tests/test_signal_profiler.py`

Exit condition for this file:

- weak-signal policy is explicit, queryable, and no longer dependent on local JSON artifacts

#### `core/state_builder.py`

First touch:

- Phase 4

Purpose:

- create the first-class governed asset-time state snapshot used by downstream logic

Create in this file:

- state-window specification helpers
- deterministic batch-end state identity
- source-window range capture
- effective signal count and integrity rollup logic
- governed snapshot builders for train and score windows

Primary extraction sources:

- `core/fast_features.py::run_feature_preparation_stage`
- train and score window handling in `core/acm.py`

How to implement:

- define `StateSnapshot` around the canonical contract, not around detector features
- keep the raw normalized observations and profiler outputs as inputs
- emit the state snapshot even when the batch is not scoreable
- keep state identity deterministic across replays

Files that must change:

- `core/fast_features.py`
- `core/acm.py`
- `core/representation_pipeline.py`

Must not live here:

- rolling feature engineering specific to a detector
- PCA or clustering logic
- SQL persistence

Tests to add:

- `tests/test_state_builder.py`

Exit condition for this file:

- ACM has a canonical asset-time state object before any detector-specific feature preparation

#### `core/feature_schema.py`

First touch:

- Phase 5

Purpose:

- define the canonical representation schema and feature-family ownership

Create in this file:

- schema version objects
- required versus optional feature-family rules
- feature invalidation tracking
- schema-application helpers
- schema comparison helpers used by drift management

Primary extraction sources:

- feature-manifest alignment semantics in `core/model_persistence.py`
- feature compatibility checks in `core/detector_orchestrator.py`
- structural descriptor assumptions currently embedded in `core/regimes.py`

How to implement:

- describe the representation schema independently of any one detector cache
- capture required signal families and allowed optional expansions
- make invalidated features explicit whenever upstream signal loss removes part of the structural surface

Files that must change:

- `core/model_persistence.py`
- `core/detector_orchestrator.py`
- `core/regimes.py`
- `core/representation_pipeline.py`

Must not live here:

- scaling math
- clustering logic
- SQL writes

Tests to add:

- `tests/test_feature_schema.py`

Exit condition for this file:

- representation schema is versioned and independent of detector cache manifests

#### `core/structure_encoder.py`

First touch:

- Phase 5

Purpose:

- own tag-agnostic structural encoding and basis metadata

Create in this file:

- tag-agnostic numeric surface selection
- raw monitoring surface selection for EWM
- basis fitting and application helpers
- scaler handling
- basis-signature creation
- encoded representation metadata builders

Primary extraction sources:

- `core/regimes.py::select_tag_agnostic_numeric_surface`
- `core/regimes.py::select_ewm_monitoring_surface`
- `core/regimes.py::_compute_basis_signature`
- `core/regimes.py::build_feature_basis`

How to implement:

- move existing live basis logic with parity first
- keep basis signatures stable wherever possible so replay diffs are explainable
- expose both fit and apply paths so online scoring can consume frozen basis packages
- persist encoder type, schema version, scaler params, and basis signature together

Files that must change:

- `core/regimes.py`
- `core/ewm_baseline.py`
- `core/model_persistence.py`
- `core/representation_pipeline.py`

Must not live here:

- regime clustering ownership
- score gating
- baseline promotion logic

Tests to add:

- `tests/test_structure_encoder.py`

Exit condition for this file:

- structure encoding no longer belongs analytically to `core/regimes.py`

#### `core/context_engine.py`

First touch:

- Phase 6

Purpose:

- own context semantics without forcing regime-specific ownership on the whole system

Create in this file:

- context assignment wrappers
- confidence and novelty normalization
- ambiguity handling
- transition-status computation
- context-stability grading

Primary extraction sources:

- `core/regimes.py::predict_regime_with_confidence`
- `core/regimes.py::label`
- `core/regimes.py::detect_transient_states`
- `core/regimes.py::apply_transient_state_labels`
- online context proxy behavior from `core/regime_binner.py`

How to implement:

- preserve current HDBSCAN and binner outputs as input mechanisms
- normalize them into `ContextAssignment`
- explicitly support `unknown`, `emerging`, `ambiguous`, and `non-comparable`
- keep novelty as a first-class field, not just a side annotation

Files that must change:

- `core/regimes.py`
- `core/regime_binner.py`
- `core/representation_pipeline.py`

Must not live here:

- score suppression policy
- detector scoring
- baseline freeze or adaptation policy

Tests to add:

- `tests/test_context_engine.py`

Exit condition for this file:

- context semantics are typed and reusable outside `core/regimes.py`

#### `core/comparability_engine.py`

First touch:

- Phase 7

Purpose:

- become the authoritative owner of `score_allowed` and `learn_allowed`

Create in this file:

- comparability policy evaluation
- eligibility decision creation
- degrade and suppress reason-code mapping
- rule evaluation against integrity, context, schema, and baseline inputs

How to implement:

- start in shadow mode only
- accept `ObservationIntegrity`, `ContextAssignment`, `CompatibilityStatus`, and `BaselineGovernanceDecision`
- return one `EligibilityDecision` per batch
- keep rules explicit and configuration-backed where thresholds are tunable

Files that must change:

- `core/representation_pipeline.py`
- `core/acm.py`
- `core/fuse.py`
- downstream risk and forecast files that consume score outputs

Must not live here:

- actual detector scoring
- SQL writes
- auto-retrain policy

Tests to add:

- `tests/test_comparability_engine.py`

Exit condition for this file:

- ACM has a first-class typed verdict for whether a batch may be scored or learned from

#### `core/baseline_governor.py`

First touch:

- Phase 8

Purpose:

- centralize runtime modes, readiness, contamination, freeze, adaptation, and promotion decisions

Create in this file:

- mode-resolution logic for:
  - bootstrap / not ready
  - baseline formation
  - online scoring
  - controlled adaptation
  - schema break / requalification
- readiness decision logic
- baseline candidate and freeze decision objects
- contamination verdict logic
- learn-eligibility rules
- shadow refresh and promotion interfaces

Primary extraction sources:

- `core/smart_coldstart.py`
- `core/detector_orchestrator.py::assess_baseline_contamination`
- `core/model_lifecycle.py`
- `core/model_evaluation.py`
- `core/ewm_baseline.py::check_and_apply_freeze`

How to implement:

- define runtime modes explicitly in the typed contract
- keep same-batch learning forbidden by default
- allow shadow refresh packages, but require explicit promotion before authority shifts
- let this module decide whether EWM update, detector refit, or lifecycle promotion is even allowed

Files that must change:

- `core/smart_coldstart.py`
- `core/detector_orchestrator.py`
- `core/model_lifecycle.py`
- `core/model_evaluation.py`
- `core/ewm_baseline.py`
- `core/acm.py`
- `core/representation_pipeline.py`

Must not live here:

- raw SQL data access
- detector math
- structural encoding

Tests to add:

- `tests/test_baseline_governor.py`

Exit condition for this file:

- runtime modes and baseline decisions have one authoritative owner

#### `core/schema_drift_manager.py`

First touch:

- Phase 9

Purpose:

- make schema and basis compatibility explicit and queryable

Create in this file:

- temporary tag-loss classification
- permanent tag-loss classification
- additive schema growth classification
- feature invalidation tracking
- basis-compatibility checks
- schema-break and requalification triggers

Primary extraction sources:

- `core/model_persistence.py::align_current_features_to_cached_manifest`
- `core/model_persistence.py::load_cached_models_with_validation`
- `core/detector_orchestrator.py::validate_model_feature_compatibility`
- basis-mismatch handling in `core/regimes.py`

How to implement:

- classify before any detector or context code silently continues
- replace hidden intersection and zero-fill continuation with explicit compatibility classes
- emit both machine-readable reason codes and operator-readable summaries

Files that must change:

- `core/model_persistence.py`
- `core/detector_orchestrator.py`
- `core/regimes.py`
- `core/representation_pipeline.py`
- `core/drift.py`

Must not live here:

- SQL write code
- detector fitting
- baseline promotion

Tests to add:

- `tests/test_schema_drift_manager.py`

Exit condition for this file:

- schema drift is first-class and cannot continue silently

#### `core/representation_store.py`

First touch:

- Phase 9

Purpose:

- become the SQL persistence owner for representation-governance control-plane artifacts

Create in this file:

- dataframe builders or row-builders for:
  - `ACM_RepresentationStatus`
  - `ACM_SignalProfiles`
  - `ACM_RepresentationSchemas`
  - `ACM_BaselineGovernance`
- insert and replace wrappers using the existing SQL write infrastructure
- read helpers needed by replay validation or batch inspection

How to implement:

- reuse shared SQL write helpers from `core/output_sql_core.py` instead of duplicating pyodbc patterns
- keep detector-output persistence in `core/output_manager.py`
- support shadow-write first
- keep write contracts aligned with `core/output_contracts.py`

Files that must change:

- `core/output_contracts.py`
- `core/output_sql_core.py`
- `core/output_manager.py`
- `core/output_manager_services.py`
- `core/run_metadata_writer.py`
- `core/acm.py`

Must not live here:

- detector scoring outputs
- context or comparability decisions
- raw SQL historian load behavior

Tests to add:

- `tests/test_representation_store.py`

Exit condition for this file:

- all representation control-plane artifacts can be written and queried independently of detector outputs

### Existing runtime files to modify

#### `core/acm.py`

Role after `2026.2`:

- remain the entrypoint and top-level runtime orchestrator
- stop owning hidden representation-governance policy

What to change:

- add imports for the new representation modules
- call `run_representation_pipeline(...)` immediately after raw train and score windows are loaded
- carry `RepresentationPipelineResult` through the runtime context
- keep current detector feature preparation and scoring paths unchanged during extraction
- after replay signoff, gate detector scoring, fusion, drift, forecast, and risk paths on `score_allowed`
- gate any learning or baseline mutation on `learn_allowed` and runtime mode
- persist representation tables before or alongside detector outputs, but without making them detector-owned

How to change it safely:

- first add shadow-mode invocation only
- second, thread the result through downstream stage inputs without changing old behavior
- third, make authoritative gating config-controlled and validation-only
- fourth, enable production authority only after `G1` through `G6`

Do not leave behind:

- ad hoc comparability heuristics local to `core/acm.py`
- same-batch authority shifts
- branching that bypasses the representation contract silently

Tests to update:

- `tests/test_v11_modules.py`
- replay harness coverage

#### `core/data_loader.py`

Role after `2026.2`:

- own historian access and raw dataframe retrieval only

What to change:

- convert `parse_ts_index`, `coerce_local_and_filter_future`, `check_cadence`, and `resample_df` into thin wrappers around `core/time_normalizer.py`
- remove long-term ownership of low-variance exclusion artifacts
- return raw-plus-normalized outputs only if needed during transition; after cutover, return raw observations and let the pipeline normalize

How to change it safely:

- preserve the public loading API first
- move logic behind wrappers before changing callers
- do not mix new profiler policy with old artifact exclusions after cutover

Do not leave behind:

- hidden temporal-policy ownership
- file-based sensor exclusion as authoritative input policy

Tests to update:

- `tests/test_v11_modules.py`
- `tests/test_time_normalizer.py`

#### `core/smart_coldstart.py`

Role after `2026.2`:

- transitional helper until baseline governance is fully centralized

What to change:

- route readiness checks through `core/baseline_governor.py`
- move baseline seeding policy into baseline-governor-owned helpers
- use normalized and profiled inputs rather than hidden load-stage heuristics
- make `NOOP` reasons derive from typed runtime mode and representation status where applicable

How to change it safely:

- keep retry, backoff, and orchestration behavior initially
- replace policy decisions before deleting orchestration helpers
- leave a thin compatibility layer until cutover is validated

Do not leave behind:

- a second readiness authority
- a second baseline-formation policy

Tests to update:

- `tests/test_v11_modules.py`
- `tests/test_baseline_governor.py`

#### `core/pipeline_types.py`

Role after `2026.2`:

- generic config and boundary validation only

What to change:

- keep input-contract validation that is not representation-policy-specific
- redirect `SensorValidator` and `run_data_guardrails` outputs into `core/signal_profiler.py`
- remove ownership of persisted weak-signal exclusions

How to change it safely:

- preserve current validation entrypoints while changing internals to call the profiler
- keep human-readable validation messages, but source the facts from typed profiles

Do not leave behind:

- a parallel signal-quality authority

Tests to update:

- `tests/test_v11_modules.py`
- `tests/test_signal_profiler.py`

#### `core/fast_features.py`

Role after `2026.2`:

- detector-specific feature engineering only

What to change:

- stop owning timestamp normalization and deduplication
- accept normalized inputs or governed state views as the source for feature engineering
- keep rolling features as derived detector inputs, not as canonical system state

How to change it safely:

- keep function names stable initially
- move input cleaning into the new normalizer, then reduce this file to feature generation and feature imputation

Do not leave behind:

- canonical state ownership
- hidden observation normalization

Tests to update:

- `tests/test_v11_modules.py`
- feature-prep parity assertions in replay coverage

#### `core/regimes.py`

Role after `2026.2`:

- regime-specific algorithms and regime package behavior only

What to change first:

- move structural encoding ownership out:
  - `select_tag_agnostic_numeric_surface`
  - `select_ewm_monitoring_surface`
  - `_compute_basis_signature`
  - `build_feature_basis`

What to change next:

- wrap or extract context semantics into `core/context_engine.py`:
  - `predict_regime_with_confidence`
  - `label`
  - transient-state logic

What to change last:

- remove silent zero-fill continuation from regime prediction paths
- stop using regime code as the authoritative location of score gating

How to change it safely:

- preserve current regime models and label semantics during extraction
- keep algorithmic primitives here if they remain regime-specific
- make `context_engine` the caller-facing owner, even if it temporarily delegates to this file

Do not leave behind:

- structure encoding ownership
- first-class context semantics ownership
- compatibility decisions hidden in `reindex(..., fill_value=0.0)`

Tests to update:

- `tests/test_v11_modules.py`
- `tests/reproduce_regime_alignment.py`
- `tests/test_context_engine.py`
- `tests/test_structure_encoder.py`

#### `core/regime_binner.py`

Role after `2026.2`:

- online context proxy helper only

What to change:

- expose a cleaner interface for `core/context_engine.py`
- stop any direct ownership creep into score gating or baseline decisions

Tests to update:

- `tests/test_context_engine.py`

#### `core/detector_orchestrator.py`

Role after `2026.2`:

- detector build, load, and execution only

What to change:

- route baseline contamination assessment through `core/baseline_governor.py`
- route feature compatibility checks through `core/schema_drift_manager.py`
- accept schema-bound feature views from the representation layer rather than implicitly shaped frames

How to change it safely:

- keep detector fit and cache reconstruction here
- strip out policy verdict ownership one function at a time

Do not leave behind:

- compatibility verdict authority
- baseline contamination authority

Tests to update:

- `tests/test_v11_modules.py`
- `tests/test_schema_drift_manager.py`
- `tests/test_baseline_governor.py`

#### `core/model_persistence.py`

Role after `2026.2`:

- model and package persistence only

What to change:

- keep load/save of detector and regime model artifacts
- remove authoritative feature-intersection and schema-verdict ownership
- turn `align_current_features_to_cached_manifest` into either:
  - a low-level alignment helper with no policy authority, or
  - a deleted function after `schema_drift_manager` fully replaces it
- separate regime package metadata persistence from representation schema persistence

How to change it safely:

- preserve cache loading behavior until drift classification is replay-validated
- make any legacy alignment path emit warnings and typed downgrade diagnostics before deletion

Do not leave behind:

- silent continuation on partial feature intersections

Tests to update:

- `tests/test_v11_modules.py`
- `tests/test_schema_drift_manager.py`

#### `core/model_lifecycle.py`

Role after `2026.2`:

- lifecycle bookkeeping and promotion criteria implementation only

What to change:

- consume baseline-governor decisions instead of independently deciding readiness or promotion eligibility
- keep lifecycle state transitions and persistence helpers only if they do not conflict with baseline-governor ownership

Do not leave behind:

- a second promotion authority
- readiness logic detached from representation validity

Tests to update:

- `tests/test_baseline_governor.py`
- targeted lifecycle regression tests

#### `core/model_evaluation.py`

Role after `2026.2`:

- adaptation candidate evaluation only

What to change:

- convert auto-retrain into candidate generation for controlled adaptation
- emit shadow refresh packages and metrics
- require `baseline_governor` to approve any promotion or activation

Do not leave behind:

- same-run or silent activation of new authoritative packages

Tests to update:

- `tests/test_baseline_governor.py`
- replay validation for adaptation scenarios

#### `core/ewm_baseline.py`

Role after `2026.2`:

- EWM scoring and state math only

What to change:

- keep the raw monitoring surface and update logic
- move freeze and adaptation policy decisions to `core/baseline_governor.py`
- require explicit runtime-mode and `learn_allowed` approval before updating state

How to change it safely:

- preserve current EWM score output first
- externalize policy before changing update behavior

Do not leave behind:

- freeze authority
- baseline-governance authority

Tests to update:

- `tests/test_v11_modules.py`
- `tests/test_baseline_governor.py`

#### `core/fuse.py`

Role after `2026.2`:

- downstream health fusion only

What to change:

- accept representation eligibility as an explicit input
- if `score_allowed = false`, do not fabricate authoritative health from absent detector scores
- emit degraded health evidence consistent with suppression reason codes

Do not leave behind:

- implicit assumptions that detector outputs always exist

Tests to update:

- `tests/test_v11_analytical_fixes.py`
- targeted fusion gating tests

#### `core/drift.py`

Role after `2026.2`:

- distribution or behavior drift analysis only

What to change:

- consume schema-drift results from `core/schema_drift_manager.py`
- do not let statistical drift logic hide or replace schema-break classifications
- skip authoritative drift decisions when the batch is not structurally comparable

Tests to update:

- targeted drift-versus-schema-drift tests

#### `core/analytics_builder.py`, `core/degradation_model.py`, `core/failure_probability.py`, `core/rul_estimator.py`, `core/forecast_engine.py`

Role after `2026.2`:

- downstream persistence, risk, and forecast layers only

What to change:

- accept explicit no-score and degraded representation states
- suppress risk or forecast outputs when upstream prerequisites fail
- never infer a healthy or low-risk state merely because upstream scoring was suppressed

How to change it safely:

- first thread the representation verdict through as metadata
- second, make suppression behavior explicit and queryable

Tests to update:

- integration coverage in `tests/test_v11_modules.py`
- focused suppression-behavior tests for any file that writes user-visible outputs

#### `core/output_contracts.py`

Role after `2026.2`:

- remain the write-contract registry for SQL tables

What to change:

- add:
  - `ACM_RepresentationStatus`
  - `ACM_SignalProfiles`
  - `ACM_RepresentationSchemas`
  - `ACM_BaselineGovernance`
- add replace-key policy for any table that requires idempotent replacement
- mark representation tables as required only after authoritative cutover, not before
- extend audit helpers so missing contracts fail tests early

Tests to update:

- existing contract audits
- `tests/test_representation_store.py`

#### `core/output_sql_core.py`

Role after `2026.2`:

- shared SQL write mechanics only

What to change:

- expose or extend generic insert and replace helpers so `core/representation_store.py` can reuse them
- do not add business logic for representation decisions here

Tests to update:

- SQL write contract tests
- `tests/test_representation_store.py`

#### `core/output_dataframe_builders.py`

Role after `2026.2`:

- optional small dataframe-shaping helpers only

What to change:

- either:
  - keep tiny builder helpers that `representation_store.py` can call, or
  - retire representation-adjacent builders from here if `representation_store.py` builds rows directly
- stop treating `ACM_DataQuality` summary rows as the canonical signal-governance output

Tests to update:

- `tests/test_signal_profiler.py`
- `tests/test_representation_store.py`

#### `core/output_manager_services.py`

Role after `2026.2`:

- keep shared persistence input preparation and helper utilities

What to change:

- add a clean handoff path for representation payloads if service-layer shaping remains useful
- update any run-inspection helpers to recognize the new representation tables during validation

Tests to update:

- `tests/test_sql_batch_runner.py`
- representation-store integration tests

#### `core/output_manager.py`

Role after `2026.2`:

- detector-output and analytics-output persistence owner only

What to change:

- keep `ACM_Scores_Wide` and other detector analytics outputs here
- call `representation_store.py` or accept prebuilt representation payloads for write dispatch
- do not let new representation business logic grow inside this file
- keep `ACM_DataQuality` as a compatibility artifact until dashboards migrate, then reduce or retire it

How to change it safely:

- add representation table handling through explicit delegation
- update audit and verification methods to include the new tables once whitelisted

Do not leave behind:

- a second owner for representation status

Tests to update:

- `tests/test_v11_modules.py`
- `tests/test_representation_store.py`

#### `core/run_metadata_writer.py`

Role after `2026.2`:

- run-level summary writer only

What to change:

- keep `ACM_Runs` as a run summary table, not a detailed representation-state table
- update run-outcome resolution so it distinguishes:
  - `NOOP`
  - `DEGRADED`
  - `OK`
  - score-suppressed but explainable representation states
- mirror only summary representation status at run level
- keep detailed reason codes in `ACM_RepresentationStatus`

How to change it safely:

- reuse existing zero-day status pattern where useful
- do not force the detailed control-plane contract into `ACM_Runs`

Tests to update:

- `tests/test_v11_modules.py`
- `tests/test_sql_batch_runner.py`

#### `scripts/sql_batch_runner.py`

Role after `2026.2`:

- operational runner and replay helper

What to change:

- extend run inspection to query representation tables during validation and rollout
- surface whether a batch was scoreable, suppressed, or in baseline-formation mode
- eventually use explicit baseline-governor status rather than inferring readiness only from active-model maturity

Tests to update:

- `tests/test_sql_batch_runner.py`

#### `grafana_dashboards/acm_insight_storyboard.json`

Role after `2026.2`:

- operator-facing explanation surface

What to change:

- add panels or queries for:
  - representation confidence
  - score allowed
  - learn allowed
  - schema compatibility
  - baseline compatibility
  - suppression reason codes
- preserve current score and health panels during dual-write

Do not do this too early:

- dashboard cutover should follow SQL shadow-write validation, not lead it

### SQL migrations and persistence rollout

Current highest numbered migration in repo is `022`.

The representation-governance control-plane migrations and run-level summary migration now exist in repo.

What remains is rollout validation, replay evidence, and operator/runbook closure rather than file creation.

These files now exist:

#### `scripts/sql/migrations/v11/018_acm_representation_status.sql`

Purpose:

- store one row per run, equipment, and batch timestamp describing the governed state verdict

Minimum columns:

- `RunID`
- `EquipID`
- `Timestamp`
- `RepresentationVersion`
- `SchemaVersion`
- `BasisSignature`
- `BaselinePackageVersion`
- `RuntimeMode`
- `CoverageRatio`
- `StaleRatio`
- `MissingnessGrade`
- `EffectiveSignalCount`
- `ContextID`
- `ContextLabel`
- `ContextConfidence`
- `ContextStability`
- `TransitionStatus`
- `SchemaCompatibility`
- `BasisCompatibility`
- `BaselineCompatibility`
- `ScoreAllowed`
- `LearnAllowed`
- `RepresentationConfidence`
- `DegradedReasonCodes`
- `SuppressedReasonCodes`
- `SourceWindowStart`
- `SourceWindowEnd`
- audit timestamps

Implementation notes:

- primary uniqueness should support idempotent replay by run, equipment, and timestamp
- add operational indexes on `(EquipID, Timestamp)` and `(RunID)`

#### `scripts/sql/migrations/v11/019_acm_signal_profiles.sql`

Purpose:

- store per-signal monitorability and integrity results

Minimum columns:

- `RunID`
- `EquipID`
- `SignalName`
- `ProfileVersion`
- `MissingRatio`
- `FlatlineRatio`
- `EffectiveCadenceSeconds`
- `VariabilityScore`
- `IntermittencyScore`
- `NoiseScore`
- `MonitorabilityClass`
- `ReasonCodes`
- audit timestamps

Implementation notes:

- support replace semantics by run, equipment, and signal
- keep one stable profile version field so replay comparisons are possible

#### `scripts/sql/migrations/v11/020_acm_representation_schemas.sql`

Purpose:

- store schema and basis registry data

Minimum columns:

- `SchemaVersion`
- `BasisSignature`
- `EncoderType`
- `FeatureListJson`
- `RequiredFeatureListJson`
- `ScalerParamsJson`
- `CompatibilityClass`
- `CreatedAt`
- optional provenance fields such as package owner or training window

Implementation notes:

- this is a registry table, not a per-batch table
- uniqueness should key on schema version and basis signature

#### `scripts/sql/migrations/v11/021_acm_baseline_governance.sql`

Purpose:

- store runtime mode and baseline-governance decisions

Minimum columns:

- `RunID`
- `EquipID`
- `Timestamp`
- `RuntimeMode`
- `ReadinessState`
- `BaselineCandidateState`
- `ContaminationVerdict`
- `FreezeState`
- `ShadowRefreshState`
- `PromotedPackageVersion`
- `LearnAllowed`
- `ReasonCodes`
- audit timestamps

Implementation notes:

- support replace semantics by run, equipment, and timestamp
- link clearly to the representation status row for the same batch

#### `scripts/sql/migrations/v11/022_acm_runs_representation_status.sql`

Purpose:

- project run-level representation authority and suppression metadata directly onto `ACM_Runs`

Minimum columns:

- `RepresentationAuthoritative`
- `RepresentationScoreAllowed`
- `RepresentationLearnAllowed`
- `RepresentationContextLabel`
- `RepresentationRuntimeMode`
- `RepresentationSchemaCompatibility`
- `RepresentationBasisCompatibility`
- `RepresentationBaselineCompatibility`
- `RepresentationSuppressedReasons`
- `RepresentationDegradedReasons`

Implementation notes:

- this migration is now required because run-level representation summaries are part of the `G2` suppression-visibility contract
- keep these fields as operator-facing summaries; detailed batch reasoning remains in `ACM_RepresentationStatus`

Files to modify with the migrations:

- `core/output_contracts.py`
- any installer or deployment script that enumerates v11 migrations
- `tests/test_sql_batch_runner.py`
- `tests/test_v11_modules.py`
- representation-store tests

### Test files to add or expand

Add new focused test files:

- `tests/test_representation_contracts.py`
- `tests/test_representation_pipeline.py`
- `tests/test_time_normalizer.py`
- `tests/test_signal_profiler.py`
- `tests/test_state_builder.py`
- `tests/test_feature_schema.py`
- `tests/test_structure_encoder.py`
- `tests/test_context_engine.py`
- `tests/test_comparability_engine.py`
- `tests/test_baseline_governor.py`
- `tests/test_schema_drift_manager.py`
- `tests/test_representation_store.py`

Expand existing test files:

- `tests/test_v11_modules.py`
  - shadow-mode parity
  - end-to-end gating behavior
  - no-score on comparability failure
  - no silent schema-drift continuation
- `tests/test_v11_analytical_fixes.py`
  - enforce analytical rules that the refactor is intended to protect
- `tests/test_sql_batch_runner.py`
  - representation-table inspection and rollout verification
- `tests/reproduce_regime_alignment.py`
  - keep replay parity checks for context extraction while regime ownership is being reduced

Every new module above must have:

- pure unit tests
- one integration path through `core/acm.py` shadow mode
- replay evidence before authority shift

### Implementation progress

Status as of 2026-03-12:

- Slice 1 completed: contracts and shadow shell are live in repo.
- Slice 2 completed: observation normalization now routes through `core/time_normalizer.py`.
- Slice 3 completed: signal qualification now has a shared owner in `core/signal_profiler.py`.
- Slice 4 completed: governed batch-window state construction now lives in `core/state_builder.py`.
- Slice 5 completed: the `RG-07` milestone was delivered as two reviewable extractions, `core/structure_encoder.py` and `core/feature_schema.py`, while keeping runtime authority unchanged.
- Slice 6 completed: context ownership now routes through `core/context_engine.py`, and regime postprocess emits a shadow typed `ContextAssignment` without changing score authority.
- Slice 7 completed: shadow comparability now lives in `core/comparability_engine.py`, `core/fuse.py` forwards typed context back to the representation layer, and `core/acm.py` re-evaluates `score_allowed` and `learn_allowed` after postprocess without changing production authority.
- Slice 8 completed: baseline governance now routes through `core/baseline_governor.py`, the representation layer consumes a first-class shadow `BaselineGovernanceDecision`, and ACM feeds contamination, coldstart, refit, and EWM freeze signals into that contract without changing legacy mutation authority.
- Slice 9 completed: schema drift now routes through `core/schema_drift_manager.py`, cached-manifest alignment and regime-basis mismatch emit first-class compatibility decisions, and ACM feeds shadow schema/basis compatibility into the representation layer without changing current retrain or fallback authority.
- Slice 10 completed: representation control-plane persistence now routes through `core/representation_store.py`, shadow governance artifacts can be dual-written to SQL through the existing output contract path, and migrations/contracts exist for the new representation tables without changing production detector-output authority.
- Slice 11 completed: authoritative representation gating now exists in validation mode only, activation is explicit and replay-safe, learning-side effects are blocked when `learn_allowed = false`, downstream scoring outputs are suppressed when `score_allowed = false`, `scripts/sql_batch_runner.py` can invoke validation authority and surface representation status during replay inspection, and run-level representation status is now projected onto `ACM_Runs` so suppression/degradation reasons are visible in top-level run metadata without changing default production authority.

### Audit checkpoint: 2026-03-12

Strict repo audit against this plan shows:

- the implementation is on track through Slice 11, but not beyond it
- the new representation owners, SQL tables, validation-only authority path, and run-level representation summary projection are all real in code
- `G2` is now satisfied in code because suppression reasons are persisted in `ACM_RepresentationStatus`, surfaced by `scripts/sql_batch_runner.py`, and projected onto `ACM_Runs`
- a validation-authority replay on `WFA_TURBINE_10` confirmed that authoritative suppression is activating in runtime, not just in tests
- that replay also exposed two real hardening gaps which are now fixed in code: score-suppressed runs were still attempting score-derived analytics writes, and `ACM_Runs` writes were still allowing `NaN` float payloads after suppression
- the persistence prep path now also blocks baseline buffer mutation when authoritative representation says `learn_allowed = false`, closing a remaining learning-side-effect hole in validation mode
- the target `ACM` database used for replay initially lacked migrations `018` through `022`; that rollout gap is now closed, and validation-mode replay prechecks enforce it before processing starts
- `scripts/sql_batch_runner.py` now has an explicit validation-mode SQL precheck so future replay runs fail fast when the representation SQL contract is missing instead of discovering it mid-run
- `G1`, `G4`, and `G6` remain open because zero-day replay closure and replay-qualified legacy-owner replacement are not complete
- the repo is intentionally carrying duplicate owners in shadow/validation mode; this is acceptable until `RG-14`, but only if those owners are treated as transitional

Transitional duplicate owners that should survive until replay-qualified replacement exists:

- `core/regimes.py` compatibility wrappers for structure and context extraction
- `core/model_persistence.py::align_current_features_to_cached_manifest()`
- `core/detector_orchestrator.py::validate_model_feature_compatibility()`
- legacy adaptation side effects in `core/ewm_baseline.py`, `core/model_lifecycle.py`, and `core/model_evaluation.py`

Audit cleanup findings that are safe immediately:

- remove dead locals and unused shadow-write placeholders when they are not read anywhere
- fix stale operator and knowledge docs that advertise unsupported CLI flags
- keep generated ACM memory artifacts refreshed after runtime/tooling changes so the repo navigation layer stays green

Audit findings that must wait for `RG-14`:

- deleting the `core/regimes.py` compatibility wrappers
- removing legacy schema-alignment entrypoints before direct callers cut over
- deleting legacy adaptation authorities before replay-qualified replacement exists

### Recommended delivery slices

These slices are the safest implementation order.

#### Slice 1: contracts and shell

Files:

- `core/representation_contracts.py`
- `core/representation_pipeline.py`
- `core/acm.py`
- `tests/test_representation_contracts.py`
- `tests/test_representation_pipeline.py`

Goal:

- create the typed scaffold and shadow hook with no semantic change

#### Slice 2: temporal extraction

Files:

- `core/time_normalizer.py`
- `core/data_loader.py`
- `core/fast_features.py`
- `core/smart_coldstart.py`
- `tests/test_time_normalizer.py`
- `tests/test_v11_modules.py`

Goal:

- centralize normalization with parity

#### Slice 3: signal qualification

Files:

- `core/signal_profiler.py`
- `core/pipeline_types.py`
- `core/output_dataframe_builders.py`
- `core/data_loader.py`
- tests for profiling and parity

Goal:

- make signal quality explicit and queryable

#### Slice 4: governed state snapshots

Files:

- `core/state_builder.py`
- `core/acm.py`
- `core/fast_features.py`
- tests for deterministic batch state

Goal:

- create the canonical asset-time state object

#### Slice 5: schema and structure

Files:

- `core/feature_schema.py`
- `core/structure_encoder.py`
- `core/regimes.py`
- `core/model_persistence.py`
- `core/detector_orchestrator.py`
- `core/ewm_baseline.py`
- tests for basis parity and schema versioning

Goal:

- separate reusable structural representation from regime ownership

#### Slice 6: context extraction

Files:

- `core/context_engine.py`
- `core/regimes.py`
- `core/regime_binner.py`
- tests for context confidence, novelty, and transition behavior

Goal:

- make context a first-class typed output

#### Slice 7: comparability shadow mode

Files:

- `core/comparability_engine.py`
- `core/representation_pipeline.py`
- `core/acm.py`
- `core/fuse.py`
- targeted downstream consumers
- tests for score-allowed and learn-allowed decisions

Goal:

- create the authoritative gating owner without changing production authority yet

#### Slice 8: baseline governance

Files:

- `core/baseline_governor.py`
- `core/smart_coldstart.py`
- `core/detector_orchestrator.py`
- `core/model_lifecycle.py`
- `core/model_evaluation.py`
- `core/ewm_baseline.py`
- `core/acm.py`
- tests for runtime modes and baseline decisions

Goal:

- centralize readiness, contamination, freeze, and adaptation policy

#### Slice 9: schema drift manager

Files:

- `core/schema_drift_manager.py`
- `core/model_persistence.py`
- `core/detector_orchestrator.py`
- `core/regimes.py`
- `core/drift.py`
- tests for all drift classes

Goal:

- eliminate silent partial-input continuation

#### Slice 10: SQL control plane

Files:

- `core/representation_store.py`
- `core/output_contracts.py`
- `core/output_sql_core.py`
- `core/output_manager.py`
- `core/output_manager_services.py`
- `core/run_metadata_writer.py`
- `scripts/sql/migrations/v11/018_acm_representation_status.sql`
- `scripts/sql/migrations/v11/019_acm_signal_profiles.sql`
- `scripts/sql/migrations/v11/020_acm_representation_schemas.sql`
- `scripts/sql/migrations/v11/021_acm_baseline_governance.sql`
- SQL and persistence tests

Goal:

- dual-write the representation control plane safely

#### Slice 11: validation-only authority shift

Files:

- `core/acm.py`
- `core/fuse.py`
- downstream consumers
- validation and replay harnesses

Goal:

- enable authoritative gating in replay and validation environments only

#### Slice 12: cleanup and rollout

Files:

- legacy owners that still carry duplicate governance behavior
- `scripts/sql_batch_runner.py`
- `grafana_dashboards/acm_insight_storyboard.json`
- runbooks and dashboard references

Goal:

- remove duplicate authority and make operator behavior explainable end to end

### Legacy logic that must survive until replay-qualified replacement exists

Do not delete these early:

- `core/smart_coldstart.py` orchestration and NOOP handling
- `core/model_persistence.py` current cache-loading path
- `core/regimes.py` active basis and context path
- `core/output_manager.py` current detector-output writes
- `core/ewm_baseline.py` current scoring and persistence path
- current dashboard queries that rely on `ACM_Scores_Wide`, `ACM_DataQuality`, and `ACM_Runs`

### Final completion checklist

`2026.2` is not complete until every item below is true:

1. every responsibility in the target architecture has one explicit code owner
2. `core/acm.py` calls one representation pipeline before downstream scoring
3. `score_allowed` and `learn_allowed` are explicit, typed, persisted, and replay-validated
4. temporary tag loss, permanent tag loss, additive schema growth, and basis breaks are separately classified
5. no detector or regime file silently owns canonical representation policy
6. no SQL write path stores representation reasons only in logs
7. online scoring does not silently mutate authoritative baselines
8. dashboards and run inspection can explain suppressed scoring without code or log access
9. legacy duplicate governance logic has been removed only after replay-qualified replacement exists

## Canonical governed state contract

The canonical asset-time state contract for `2026.2` must be explicit and typed.

Illustrative shape:

```python
@dataclass
class GovernedAssetState:
    asset_id: int
    batch_end_time: datetime
    run_id: str
    source_window_start: datetime
    source_window_end: datetime
    integrity: ObservationIntegrity
    context: ContextAssignment
    compatibility: CompatibilityStatus
    eligibility: EligibilityDecision
    refs: RepresentationRefs
    grades: OperationalGrades


@dataclass
class ObservationIntegrity:
    coverage_ratio: float
    stale_ratio: float
    missingness_grade: str
    effective_signal_count: int
    expected_rows: int
    observed_rows: int


@dataclass
class ContextAssignment:
    context_id: str
    context_label: str
    context_confidence: float
    context_stability: str
    transition_status: str
    is_novel: bool
    is_ambiguous: bool


@dataclass
class CompatibilityStatus:
    schema_compatibility: str
    basis_compatibility: str
    baseline_compatibility: str
    missing_signals: list[str]
    new_signals: list[str]
    invalidated_features: list[str]


@dataclass
class EligibilityDecision:
    score_allowed: bool
    learn_allowed: bool
    degraded_reason_codes: list[str]
    suppressed_reason_codes: list[str]


@dataclass
class RepresentationRefs:
    representation_version: str
    schema_version: str
    basis_signature: str
    baseline_package_version: str
    signal_profile_version: str


@dataclass
class OperationalGrades:
    representation_confidence: float
    input_integrity_grade: str
    context_stability_grade: str
```

Required contract semantics:

- every scoring batch must produce one governed state result, even when scoring is suppressed
- detector-specific feature frames are derived artifacts, not the canonical governed state
- `score_allowed` and `learn_allowed` must be explicit fields, not inferred indirectly from model maturity or helper behavior
- schema, basis, and baseline compatibility must be separate fields
- degraded and suppressed reason codes must be persisted and queryable

## Definition of a complete task or phase

No task or phase is complete unless all applicable items below are done:

- code path implemented or explicitly marked no-op by design
- unit and integration coverage added or updated
- replay evidence captured for affected behavior
- SQL impact documented as either "no SQL impact" or "migration plus rollback complete"
- observability, logs, and operator-facing reason codes updated
- this master plan updated if scope, priority, or gates changed
- legacy ownership after the change is unambiguous

## SQL and persistence design

`ACM_Scores_Wide` remains the detector-output table.

Representation-governance control-plane data belongs in dedicated companion artifacts:

1. `ACM_RepresentationStatus`
   - per `EquipID`, `Timestamp`, `RunID`
   - stores representation version, state version, integrity grade, context confidence, context stability, score allowed, learn allowed, baseline compatible, schema compatibility, degraded reason, source window range

2. `ACM_SignalProfiles`
   - per `EquipID`, `SignalName`, `ProfileVersion`
   - stores missing ratio, flatline ratio, effective cadence, variability score, monitorability class, reason codes

3. `ACM_RepresentationSchemas`
   - schema and basis registry
   - stores schema version, basis signature, feature list, scaler params, encoder type, compatibility class

4. `ACM_BaselineGovernance`
   - baseline package and adaptation decisions
   - stores readiness, contamination verdict, freeze state, shadow refresh status, promoted package version

## Validation strategy

Validation happens in four layers.

### 1. Unit validation

- duplicates, future rows, cadence irregularity, anti-upsample
- sparse, flatline, intermittent, and noisy signals
- deterministic state-building and batch-end identity
- schema and basis compatibility classification
- comparability decisions and degraded reasons
- baseline readiness, contamination, and freeze behavior

### 2. Integration validation

- current scoring path still behaves as expected with shadow-mode representation enabled
- representation shadow outputs persist without breaking existing writes
- regime confidence and novelty survive the new context contract
- score gating remains config-controlled until cutover

### 3. Replay acceptance validation

Replay coverage must include:

- coldstart / insufficient-history runs
- cached-model scoring runs
- regime-basis degradation paths
- schema mismatch paths
- EWM zero-day paths
- contaminated-baseline scenarios

### 4. SQL and operational validation

- all new tables write idempotently
- old dashboards keep working until replacements are ready
- run metadata distinguishes `NOOP`, `DEGRADED`, and `score suppressed because no scoreable state`
- operators can query the reason a score was suppressed without reading logs

## Rollout plan

### Stage A: shadow extraction

- add contracts, normalization, profiling, state building, and comparability in memory only
- do not change score authority

### Stage B: dual-write persistence

- write representation-governance tables
- keep current detector score path authoritative

### Stage C: controlled gating enablement

- enable `score_allowed` gating in replay/validation first
- then enable in the target runtime only after signoff

### Stage D: legacy cleanup

- remove obsolete ownership paths
- remove file-based signal exclusion policy only after SQL-backed profiling is trusted

## Definition of done

This plan is complete only when all of the following are true:

- ACM has one explicit representation-governance layer with one owner per responsibility.
- Every scoring batch produces a typed representation status, whether or not detector scoring occurs.
- Context confidence, comparability, schema compatibility, and baseline compatibility are explicit and persisted.
- Detectors consume governed inputs rather than implicit raw/feature-frame assumptions.
- Non-comparable states are suppressed or degraded intentionally and explainably.
- Replay validation confirms no unacceptable regression in analytical correctness.
- The runtime no longer depends on hidden governance logic spread across `data_loader`, `smart_coldstart`, `regimes`, `model_persistence`, and `output_manager`.

## Reference-only documents

The following documents may remain in the repo, but they are not planning authorities:

- `docs/NewPlan12032026.md`
- `docs/obsidian_vault/knowledge/Plan-Zero-Day-Implementation.md`
- `docs/archive/Major Refactor Plan.md`
- debt, audit, architecture-debt, analytical-audit, and version-history notes

They exist only as historical or evidentiary support for this master plan.

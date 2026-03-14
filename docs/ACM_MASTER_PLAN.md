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
- validation-only representation authority is live in repo and replay-validated
- the representation-governance owner layer is real in code, even though the runtime is not representation-first yet
- tag-agnostic regime basis selection is live
- cached regime basis-contract reuse is replay-validated and is no longer the primary blocker
- tag-agnostic transient-state logic is live
- EWM uses an explicit raw monitoring surface
- `OnlinePCABinner` is the early online context proxy before mature HDBSCAN labels exist
- regime state and EWM state are version-gated
- post-regime governed gating now has two levels:
  - pre-transient suppression for already-known ambiguous, novel, unknown, or low-confidence context
  - later post-transient suppression fallback when transition evidence is required
- validation-mode pre-score regime-context preview is now live on compatible cached-regime paths and can short-circuit detector scoring before the legacy scored/regime pass executes
- validation-mode feature-frame regime-context preview can now load only cached `regime_model` plus manifest/state, reuse the cached basis contract, and short-circuit before full detector initialization on compatible cached-model paths
- validation-mode raw regime-context preview is now also live before full feature preparation on cached `ACM_RegimeState` paths; it is intentionally read-only and currently serves as an earlier evidence probe rather than a universal short-circuit
- load-time structural fast-fail is live for purely structural no-score batches whose suppression reasons are already fully known before feature preparation
- post-baseline structural fast-fail is now also live for authoritative `no_score_rows` batches, so empty-score windows can degrade cleanly after baseline seeding instead of crashing later in detector scoring
- authoritative no-score runs now skip zero-day, calibration, fusion, adaptive postprocess, and sensor-analytics context preparation
- authoritative no-score runs on the new pre-score preview path now also skip detector scoring and PCA SQL artifact writes
- authoritative no-score runs now also skip non-score secondary artifacts such as `ACM_SensorCorrelations`, `ACM_SensorNormalized_TS`, and per-run `ACM_SeasonalPatterns`, while still keeping control-plane writes and `ACM_Run_Stats`
- canonical per-signal profiles now flow through `core/representation_pipeline.py` and are persisted by `core/representation_store.py`; store-time reprofiling remains only as a transitional fallback
- later representation refresh/re-authority logic is now centralized in `core/representation_pipeline.py` instead of being rebuilt inline at each `core/acm.py` gate
- dev and replay runs can now disable the observability stack centrally with `ACM_OBS_DISABLE=1`, and `scripts/sql_batch_runner.py` honors the same owner-level environment flags instead of hard-wiring exporters on
- run outcomes remain `OK`, `DEGRADED`, `NOOP`, `FAIL`

What is not yet closed:

- the runtime still reaches representation authority too late for many non-scoreable batches, even though detector scoring can now be skipped on some cached-model suppressed paths and an earlier raw-preview probe now exists
- current primary blockers are contextual comparability and pending baseline governance, not basis churn
- the current structural fast-fail path is still intentionally narrow and is not yet sufficient to stop most scoring-window no-score batches before all feature/model work
- the latest no-score persistence cleanup removed the previous secondary-artifact bottleneck on replay-validated suppressed runs, and the newer regime-only preview path removed broad detector loading from some suppressed runs, so the dominant remaining cost is now earlier feature preparation, seasonality, raw preview, and narrow regime-preview loading
- `ACM_SignalProfiles` and `ACM_RepresentationSchemas` still use transitional run-scoped shapes instead of their final control-plane semantics
- replay-qualified replacement and deletion of duplicate legacy owners is not complete
- operator rollout/runbook closure for non-validation environments is not complete

## Current runtime owners

The current runtime now has explicit representation-governance owners, but the active runtime path is still transitional and layered over legacy orchestration:

| Responsibility | Current owners |
|---|---|
| raw historian load and timestamp normalization | `core/data_loader.py` with `core/time_normalizer.py` as the extracted owner |
| basic guardrails and signal qualification | `core/pipeline_types.py` with `core/signal_profiler.py` as the extracted owner |
| governed state and shadow orchestration | `core/representation_pipeline.py`, `core/state_builder.py`, `core/representation_contracts.py` |
| detector feature engineering | `core/fast_features.py` |
| schema and structure encoding | `core/feature_schema.py`, `core/structure_encoder.py`, with transitional wrappers in `core/regimes.py` and `core/model_persistence.py` |
| context and comparability | `core/context_engine.py`, `core/comparability_engine.py`, reached through `core/acm.py` after load, on the validation-mode pre-score regime preview path, and again after the later regime/postprocess gates |
| baseline governance | `core/baseline_governor.py` with transitional legacy mutation owners in `core/smart_coldstart.py`, `core/model_lifecycle.py`, `core/model_evaluation.py`, and `core/ewm_baseline.py` |
| zero-day scoring and online proxy state | `core/ewm_baseline.py`, `core/regime_binner.py`, `core/acm.py` |
| schema drift classification | `core/schema_drift_manager.py` with transitional callers in `core/model_persistence.py`, `core/detector_orchestrator.py`, and `core/regimes.py` |
| representation persistence and run summaries | `core/representation_store.py`, `core/run_metadata_writer.py`, `core/output_manager.py`, `core/output_contracts.py` |

The remaining design debt is no longer "missing owners." It is "late runtime ordering and duplicate transitional owners."

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

- A first-class representation-governance layer now exists in code, but only in shadow and validation-authority form.
- The repo still runs as a legacy ACM pipeline with a governed veto layer rather than as a representation-first runtime.
- The single biggest analytical risk is late gating: expensive feature preparation, detector work, and the first regime-scoring pass still run before many authoritative no-score outcomes are known.
- The single biggest ownership problem is late orchestration in `core/acm.py` around transitional legacy stages, even though the new representation owners now exist.

### Conformance to the current master plan

Aligned with current runtime truth:

- `python -m core.acm` remains the active entrypoint.
- `RG-13` is materially real in code: validation-only representation authority is live, persisted, and replay-validated.
- Tag-agnostic regime basis selection is live.
- Cached regime basis-contract reuse is now replay-validated in direct governed `core.acm` runs.
- Tag-agnostic transient-state logic is live.
- EWM uses an explicit raw monitoring surface.
- `OnlinePCABinner` is the early online context proxy.
- Regime state and EWM state are version-gated.
- Run outcomes remain `OK`, `DEGRADED`, `NOOP`, `FAIL`.
- `G2` is satisfied: suppressed reasons are persisted in `ACM_RepresentationStatus`, surfaced by `scripts/sql_batch_runner.py`, and mirrored onto `ACM_Runs`.

Only partially aligned:

- Observation normalization exists under an extracted owner, but callers are still partly transitional.
- Data quality and weak-signal logic exist under a shared profiler owner, but final persistence semantics are not complete.
- Schema compatibility and basis compatibility are first-class in validation mode, but the runtime still carries transitional drift callers.
- Baseline contamination, lifecycle, freeze, and refit controls now feed one typed contract, but legacy mutation owners still remain.
- Context confidence and novelty are typed and authoritative in validation mode, but they are still reached too late for many batches.

Architecturally in conflict with the target:

- The system is still representation-aware rather than representation-first.
- Detector scoring, feature preparation, and regime labeling still run before enough context/baseline truth exists to suppress most non-scoreable batches.
- Novel points are still forced into some regime label and then degraded or suppressed later rather than yielding a first-class pre-score non-comparable branch.
- Silent continuation still exists through zero-fill and feature-intersection paths.
- `G1`, `G4`, and `G6` remain open because replay-qualified replacement and final cutover are not complete.

### Responsibility assessment matrix

| Responsibility | Current implementation points | Status | Ownership quality | Analytical risk | Recommended target owner |
|---|---|---|---|---|---|
| observation normalization | `core/time_normalizer.py`, delegated callers in `core/data_loader.py`, `core/fast_features.py`, `core/smart_coldstart.py` | present | correct but transitional | remaining risk is caller duplication, not missing owner | `core/time_normalizer.py` |
| signal qualification | `core/signal_profiler.py`, delegated guardrail path in `core/pipeline_types.py`, runtime use in `core/representation_pipeline.py` | present | correct but transitional | canonical persistence semantics are not finished yet | `core/signal_profiler.py` |
| windowed state construction | `core/state_builder.py`, fed by `core/representation_pipeline.py` | present | correct but shadow-mode | state exists, but runtime still reaches it too late for many no-score batches | `core/state_builder.py` |
| geometry stabilization / structure encoding | `core/feature_schema.py`, `core/structure_encoder.py`, transitional callers in `core/regimes.py` and `core/model_persistence.py` | present | correct but transitional | main remaining risk is legacy caller ordering, not missing ownership | `core/feature_schema.py` and `core/structure_encoder.py` |
| context assignment | `core/context_engine.py` with transitional regime-backed callers | present | correct but transitional | context is typed, but runtime still pays much of the legacy path before it becomes authoritative | `core/context_engine.py` |
| comparability / score gating | `core/comparability_engine.py`, validation authority flow in `core/representation_pipeline.py`, `core/acm.py`, `core/fuse.py` | present in validation mode | correct but late-enforced | no-score decisions still arrive after expensive feature/model/regime work in many batches | `core/comparability_engine.py` |
| baseline governance | `core/baseline_governor.py` with transitional signals from coldstart, contamination, lifecycle, and EWM | present in validation mode | correct but transitional | pending baseline readiness still blocks governed scoring; legacy mutation owners still exist | `core/baseline_governor.py` |
| schema drift governance | `core/schema_drift_manager.py` with transitional callers in cache loading, detector orchestration, and regimes | present in validation mode | correct but transitional | silent continuation is reduced but not fully removed everywhere | `core/schema_drift_manager.py` |
| governance outputs | `core/representation_store.py`, `core/run_metadata_writer.py`, `core/output_contracts.py`, `scripts/sql_batch_runner.py` | present in validation mode | correct but incomplete | `ACM_SignalProfiles` and `ACM_RepresentationSchemas` still have transitional run-scoped shapes | `core/representation_store.py` |

### Runtime mode assessment

The repo now implements a partial and enforceable runtime-mode model, but not yet a fully representation-first one.

Typed runtime modes, baseline decisions, and eligibility exist in the governed layer, but legacy stages still execute too far into the pipeline before those decisions can short-circuit work.

| Runtime mode | Current implementation points | Current authority owner(s) | Gaps | Risks | Target authority owner |
|---|---|---|---|---|---|
| Bootstrap / Not Ready | typed runtime-mode resolution in `core/baseline_governor.py`, transitional coldstart orchestration in `core/smart_coldstart.py` | `core/baseline_governor.py`, `core/smart_coldstart.py`, `core/acm.py` | runtime still partly keys off legacy coldstart state and model presence | not-ready runs are clearer than before, but still not fully representation-first | `core/baseline_governor.py` |
| Baseline Formation | governed baseline decisions in `core/baseline_governor.py`, contamination signals from detector fit path, run projection in `core/representation_store.py` and `core/run_metadata_writer.py` | `core/baseline_governor.py` with transitional legacy callers | baseline package semantics remain partially split across lifecycle and coldstart code | baseline compatibility can stay pending longer than operators expect | `core/baseline_governor.py` |
| Online Scoring | validation-authority flow in `core/representation_pipeline.py`, `core/comparability_engine.py`, and `core/acm.py` | `core/comparability_engine.py` with transitional legacy stage order | feature prep, detector scoring, and the first regime pass still run before many no-score decisions | runtime cost and legacy influence remain higher than intended | `core/comparability_engine.py` |
| Controlled Adaptation | typed `learn_allowed` verdicts, blocked mutation paths in `core/acm.py` and `core/output_manager_services.py`, transitional lifecycle owners remain | `core/baseline_governor.py` with legacy adaptation helpers | shadow-refresh and promotion boundaries are still not the only runtime path | learning authority is safer, but not fully centralized yet | `core/baseline_governor.py` |
| Schema Break / Requalification | typed compatibility classes in `core/schema_drift_manager.py`, representation persistence in `core/representation_store.py`, replay surfacing in `scripts/sql_batch_runner.py` | `core/schema_drift_manager.py` with transitional callers | mode semantics do not yet fully collapse schema-break cases into an earlier structural fast-fail branch | some late-stage work still happens before requalification is evident | `core/schema_drift_manager.py` |

### Schema drift and signal-loss assessment

Schema drift is now first-class in validation-mode governance, but it is not fully cleaned up across the whole runtime yet.

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
| late gating still spends too much runtime before no-score resolution | `core/acm.py`, `core/regimes.py`, `core/fuse.py` | expensive feature/model/regime work still happens before many authoritative no-score outcomes are known | replay cost stays high and legacy influence remains deeper than intended | add earlier pre-feature / pre-detector structural fast-fail |
| online scoring still owns some mutation paths | EWM update/save, binner observe/save, same-run retrain flow | scoring and adaptation are not fully separated everywhere | violates the target no-silent-learning model when governance is not yet early enough | keep moving adaptation behind `core/baseline_governor.py` and `learn_allowed` |
| operator-facing suppression contract is only partially normalized | `core/representation_store.py`, `core/run_metadata_writer.py`, `scripts/sql_batch_runner.py` | suppression reasons are queryable now, but summary language and SQL table semantics are still transitional | operators can reason from SQL, but some summaries still read like legacy score-first ACM | keep the representation tables authoritative and normalize summary semantics around them |

## Canonical backlog

There is one backlog.

It has two workstreams:

- close the currently active zero-day runtime validation
- deliver the `2026.2` representation-governance extraction

The zero-day workstream is first because `2026.2` is not allowed to become authoritative on top of an unclosed runtime validation plan.

### Historian data inventory (verified 2026-03-14)

22 of 24 WFA turbines have historian data. `WFA_TURBINE_11` and `WFA_TURBINE_21` have empty historian tables and cannot be replayed until source data is loaded.

Turbines with data and no ACM runs (highest priority for fresh replay):
`WFA_TURBINE_3`, `WFA_TURBINE_17`, `WFA_TURBINE_24`, `WFA_TURBINE_25`, `WFA_TURBINE_26`,
`WFA_TURBINE_42`, `WFA_TURBINE_45`, `WFA_TURBINE_51`, `WFA_TURBINE_68`, `WFA_TURBINE_69`,
`WFA_TURBINE_71`, `WFA_TURBINE_72`, `WFA_TURBINE_84`, `WFA_TURBINE_92`

Turbines with partial existing runs (need review before re-running):
`WFA_TURBINE_0` (27 runs, 0 scored rows), `WFA_TURBINE_22` (386 runs, 3-day coverage only),
`WFA_TURBINE_38` (2 runs, 0 scored rows), `WFA_TURBINE_13`, `WFA_TURBINE_14`, `WFA_TURBINE_40`,
`WFA_TURBINE_73` (large run counts but stuck in coldstart loop — same H2 pattern as T10)

### Workstream A: Close the active zero-day runtime

| ID | Task | Priority | Depends On | Exit criteria |
|---|---|---|---|---|
| ZD-01 | Fresh replay of `WFA_TURBINE_10` on latest runtime | P0 | None | replay executes end to end; EWM/binner/run SQL tables verified |
| ZD-02 | SQL verification for `ACM_EWMBaseline`, `ACM_RegimeBinnerState`, `ACM_Runs`, `ACM_RunLogs` | P0 | ZD-01 | no schema/version mismatch and continuity is confirmed — **CONFIRMED PASS 2026-03-14** |
| ZD-03 | Replay `WFA_TURBINE_17` (clean data, ~385 days, no prior runs) | P0 | ZD-02 | replay completes with expected day-0 behavior and no critical degradations |
| ZD-04 | Replay `WFA_TURBINE_3` (clean data, ~388 days, no prior runs) | P0 | ZD-02 | replay completes with expected day-0 behavior and no critical degradations |
| ZD-04b | Replay `WFA_TURBINE_0`, `WFA_TURBINE_22`, `WFA_TURBINE_38` (partial prior runs — reset and replay) | P1 | ZD-02 | all three complete end-to-end without error |
| ZD-04c | Replay remaining no-run turbines: T24, T25, T26, T42, T45, T51, T68, T69, T71, T72, T84, T92 | P1 | ZD-03, ZD-04 | fleet-wide baseline established |
| ZD-04d | Load historian data for `WFA_TURBINE_11` and `WFA_TURBINE_21` then replay | P2 | None (data dependency) | source data loaded; replay completes with day-0 behavior |
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
| RG-13 | Enable authoritative representation gating for `2026.2` | P0 | ZD-01, ZD-02, ZD-03, ZD-04, ZD-04b, RG-12 | non-comparable states no-score correctly and queryably |
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

Current condition:

- Live in repo
- typed governed contracts, runtime modes, eligibility, baseline-governance decision objects, and reason-code enums now exist and are imported by the representation pipeline and validation-authority path

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

Current condition:

- Live in repo
- owns canonical shadow orchestration across normalization, profiling, state building, schema/basis/context/baseline/drift/comparability stages
- now emits canonical per-signal profiles on `RepresentationPipelineResult` and derives the asset-level summary from the same profiler output
- now also owns the shared runtime refresh helper that recomputes compatibility, baseline governance, comparability, and authority together instead of leaving that assembly duplicated inside `core/acm.py`
- the representation API no longer threads the raw legacy `coldstart_complete` flag; runtime-mode and readiness inference now come from governed metadata first, with legacy fallback remaining inside `core/baseline_governor.py`
- downstream SQL persistence still uses transitional run-scoped audit tables rather than the final registry/control-plane shapes

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

Current condition:

- Live in repo
- current callers route timestamp parsing, deduplication, cadence inference, and resampling through this owner, though some wrapper-style delegation still remains in legacy files

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

Current condition:

- Live in repo
- owns shared weak-signal and monitorability profiling in the governed path
- persistence shape is still transitional because `ACM_SignalProfiles` is run-scoped audit data and store-time sourcing is not final yet

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

Current condition:

- Live in repo
- governed batch-window state snapshots are produced in the representation path, but runtime still reaches them too late for many structural no-score outcomes

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

Current condition:

- Live in repo
- schema compatibility and manifest-alignment ownership have moved here, with transitional legacy callers still present

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

Current condition:

- Live in repo
- cached regime basis reuse is now replay-validated and active through this owner
- transitional regime callers still remain, but basis-selection ownership has already moved

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

Current condition:

- Live in repo
- typed context, novelty, ambiguity, and transition semantics are now owned here
- runtime still reaches this owner too late for many non-scoreable batches because the load-time structural fast-fail only handles purely structural blockers and later contextual/baseline truth still arrives after much of the legacy path

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

Current condition:

- Live in repo
- typed `score_allowed` and `learn_allowed` verdicts are live in validation authority
- runtime still reaches this owner too late for many non-scoreable batches because feature/model/regime work often happens before final no-score authority resolves

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

Current condition:

- Live in repo
- typed runtime-mode and baseline-governance decisions are active in validation authority
- explicit `enough_history_to_proceed` and `baseline_ready` fields are now live in the governed contract, but legacy coldstart still feeds the initial authority inputs
- transitional interpretation of legacy `RegimeMaturityState` now lives here instead of in `core/smart_coldstart.py`
- transitional baseline-seeding authority now also routes through this file: non-authoritative cached-scoring batches are explicitly marked as `TRUSTED_WINDOW_PENDING` instead of inventing a score-derived baseline slice
- `core/smart_coldstart.py` now delegates the legacy coldstart/scoring gate decision into this file instead of interpreting lifecycle SQL hints locally
- load-stage runtime hints (`baseline_runtime_mode`, `enough_history_to_proceed`, `baseline_ready`, `coldstart_gate_reason`) now also originate here and are stamped onto load-stage metadata for downstream governed runtime use
- baseline readiness and compatibility are still a primary blocker for governed scoring, and legacy mutation owners remain transitional

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

Current condition:

- Live in repo
- schema and basis compatibility are first-class in validation authority
- remaining work is earlier fast-fail and cleanup of late legacy continuation paths, not absence of a drift owner

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

Current condition:

- Partial / transitional
- `ACM_RepresentationStatus` is useful and live as the main run-scoped representation verdict table
- `ACM_SignalProfiles` now persists canonical pipeline-produced per-signal payloads in the normal path, with store-time reprofiling kept only as a transitional fallback
- `ACM_RepresentationSchemas` is still per-run audit shaped, not a true schema/basis registry

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

Current condition:

- Partial / transitional
- Live in repo:
  - representation shadow pipeline after load
  - validation-only authority
  - load-time structural fast-fail for purely structural no-score batches
  - post-baseline structural fast-fail for authoritative `no_score_rows` batches
  - helperized pre-feature short-circuit orchestration so the load-time and post-baseline structural exits share one close-out path instead of duplicating teardown logic inline
  - raw regime-context preview on seasonality-adjusted raw windows before full feature preparation, using cached `ACM_RegimeState` when available
  - raw regime-context precheck is now also wrapped in one focused helper so the entrypoint no longer carries that full branch inline
  - structural early zero-day skip
  - feature-frame cached regime preview before full detector initialization, using a regime-only cached-model load plus manifest/state alignment
  - validation-mode pre-score regime-context preview on cached-model compatible basis paths
  - post-regime pre-transient suppression
  - post-regime suppression of zero-day, calibration, fusion, and adaptive postprocess
  - representation prechecks and refresh calls now consume explicit governed load-stage hints from `meta` instead of threading the raw `coldstart_complete` flag through the representation API
- Remaining work:
  - extend pre-feature / pre-detector structural fast-fail so more scoring-window no-score batches terminate before expensive work when earlier baseline-governance or context truth is genuinely available
  - reduce pre-feature runtime cost further on suppressed runs; the remaining dominant cost is now feature prep, seasonality, raw preview, and regime-only preview loading rather than broad detector loading
  - cleaner runtime-mode semantics when `ONLINE_SCORING` is intended but score is suppressed

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

Current condition:

- Partial / transitional
- historian access is still here, but timestamp normalization ownership has already moved to `core/time_normalizer.py`

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

Current condition:

- Partial / transitional
- orchestration remains here, but readiness and baseline-governance semantics now also flow through `core/baseline_governor.py`
- `coldstart_complete` is now explicitly treated as a transitional legacy signal, not the intended final readiness contract
- SQL lookup and retry/progress behavior still live here, but interpretation of `RegimeMaturityState` has already moved out to `core/baseline_governor.py`
- compatibility wrappers for the older seeding helper surface still live here, but the real seeding policy owner is now `core/baseline_governor.py`; the underlying score-head / score-split mechanics are gone and governed cached-scoring runs now persist only a `TRUSTED_WINDOW_PENDING` state
- explicit governed load-stage hints are now stamped onto `meta` here, but they are resolved by `core/baseline_governor.py` rather than being interpreted locally

What to change:

- route readiness checks through `core/baseline_governor.py`
- keep deleting compatibility-only remnants now that baseline seeding policy already lives in `core/baseline_governor.py`
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

Current condition:

- Partial / transitional
- generic guardrail entrypoints remain here, but shared weak-signal profiling ownership has moved to `core/signal_profiler.py`

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

Current condition:

- Partial / transitional
- detector feature engineering still lives here, but canonical state ownership has already moved to `core/state_builder.py` and temporal normalization has moved to `core/time_normalizer.py`
- a reusable seasonality-only stage now lives here so earlier validation previews can reuse seasonality-adjusted raw windows without rerunning the expensive detect/adjust step during full feature prep
- empty-train scoring paths can now reuse cached raw training medians and cached feature medians instead of immediately depending on score-derived runtime baseline material for feature prep

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

Current condition:

- Partial / transitional
- regime algorithms still live here, but structure encoding, context semantics, and schema/basis compatibility ownership have already moved to dedicated governed owners
- validation-mode regime context preview now reuses the cached basis/model path here before detector scoring so `core/acm.py` can short-circuit some no-score batches earlier without training or persistence side effects
- a lighter raw-surface regime preview now also lives here for validation runs that can probe context from cached `ACM_RegimeState` before full feature preparation

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

Current condition:

- Partial / transitional
- detector execution remains here, but baseline contamination and feature-compatibility ownership have already moved toward governed owners
- Live in repo:
  - full detector build/load/restore remains here
  - a regime-only cached preview loader now exists here so validation mode can load only `regime_model` plus manifest/state before full detector reconstruction
- Remaining work:
  - delete the transitional split between regime-only preview loading and full detector loading once representation-first runtime authority is earlier and cleaner
  - keep this file focused on detector/runtime reconstruction mechanics only, not governance verdicts

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

Current condition:

- Partial / transitional
- persistence remains here, but authoritative schema/basis compatibility semantics now come from `core/feature_schema.py` and `core/schema_drift_manager.py`
- Live in repo:
  - selective SQL cache loading now exists here, so callers can load only `regime_model` when they need a light preview path
  - manifest-only loading remains available for pre-feature protection flows
  - raw training-signal medians are now persisted with trained model packages and can be loaded independently of feature-space manifest validation for empty-train scoring paths
- Remaining work:
- keep selective load behavior mechanical; do not let this file regain compatibility-policy authority
- continue shrinking caller dependence on manifest-alignment side effects once the representation-first runtime path is complete
  - preserve cached training references as the normal technical support path for score-only cached runs and delete any remaining stale compatibility references to the old fallback semantics

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

Current condition:

- Partial / transitional
- EWM math remains here, but lazy initialization and governed mutation blocking are already live from the validation-authority path

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

Current condition:

- Partial / transitional
- downstream health logic remains here, but authoritative no-score suppression already prevents health fusion from acting authoritative when representation blocks scoring

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

Current condition:

- Live in repo
- representation table contracts are already present and used by validation-mode persistence

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

Current condition:

- Partial / transitional
- Live in repo:
  - suppressed runs skip score-derived persistence
  - baseline buffer mutation is blocked when `learn_allowed = false`
  - baseline-buffer refresh now prefers governed readiness hints (`baseline_runtime_mode`, `baseline_ready`) over the legacy `coldstart_complete` flag
  - sensor-analytics context build is skipped when authoritative score is unavailable
  - PCA SQL artifacts are skipped when authoritative score is unavailable
  - authoritative no-score runs now also skip raw secondary artifacts (`ACM_SensorCorrelations`, `ACM_SensorNormalized_TS`, and per-run `ACM_SeasonalPatterns`) while keeping run-scoped control-plane writes and `ACM_Run_Stats`
- Remaining work:
  - keep the no-score persistence policy minimal and explicit so additional non-score diagnostics do not creep back into suppressed runs without review

What to change:

- add a clean handoff path for representation payloads if service-layer shaping remains useful
- update any run-inspection helpers to recognize the new representation tables during validation

Tests to update:

- `tests/test_sql_batch_runner.py`
- representation-store integration tests

#### `core/output_manager.py`

Role after `2026.2`:

- detector-output and analytics-output persistence owner only

Current condition:

- Partial / transitional
- detector-output persistence remains here, while representation control-plane persistence is already delegated through `core/representation_store.py`
- persistence prep now forwards governed load-stage `meta` into the baseline-buffer helper so this file is less dependent on the raw legacy coldstart boolean

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

Current condition:

- Partial / transitional
- run-level representation summary projection is already live in `ACM_Runs`, but summary language is still partly legacy score-first

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

Current condition:

- Partial / transitional
- Live in repo:
  - validation SQL precheck
  - suppression-aware QA
  - representation summary inspection
  - deterministic inspection by explicit `RunID` when ACM emits it in console output, with fallback to latest `ACM_Runs` row only when no run identifier is available
  - coldstart replay now prefers governed `ACM_BaselineGovernance.RuntimeMode`, then governed `ACM_Runs.RepresentationRuntimeMode`; legacy lifecycle state is no longer part of the coldstart completion decision
  - coldstart replay now expands the source window on governed `NOOP` runs instead of repeating the same first-day window until `max_coldstart_attempts`
  - `ACM_RunLogs` can now serve as a SQL-backed review source for per-run console flow when detached Windows replay launches are not teeing to files
  - `DEGRADED` is no longer collapsed to `OK`
- Remaining work:
  - decomposition of inspection logic
  - declarative QA modes
  - fuller mode-aware operator summaries beyond the current execution-window vs source-data-window split

What to change:

- extend run inspection to query representation tables during validation and rollout
- surface whether a batch was scoreable, suppressed, or in baseline-formation mode
- eventually use explicit baseline-governor status rather than inferring readiness only from active-model maturity

Tests to update:

- `tests/test_sql_batch_runner.py`

#### `scripts/sql/91_create_representation_run_views.sql`

Role after `2026.2`:

- source-controlled run-insight view layer for governed ACM

Current condition:

- Live in repo
- Live in DB
- currently provides:
  - `vw_ACM_RunOutputCoverage`
  - `vw_ACM_RunQualityGates`
  - `vw_ACM_RunFact`
  - `vw_ACM_RunStory`
  - `vw_ACM_EquipCurrentSnapshot`
- latest live validation on `WFA_TURBINE_0` and `WFA_TURBINE_10` confirms:
  - `SUPPRESSED_VALID` runs are classified correctly
  - `BASELINE_FORMATION` runs are classified correctly
  - zero score-derived rows are shown as expected when `ScoreArtifactsExpected = 0`

Remaining work:

- cut Grafana panels and operator workflows over to these governed views
- keep summary language aligned with final runtime-mode semantics if `ONLINE_SCORING` remains the intended phase while scoreability is vetoed
- expand scored-run narratives so legacy scored assets and governed suppressed assets are equally readable

What to change:

- treat these views as the primary operator SQL surface for governed replay and post-run review
- avoid pushing representation semantics back into ad hoc dashboard SQL once these views exist
- keep the view logic source-controlled and replay-validated whenever classification rules change

#### `grafana_dashboards/acm_insight_storyboard.json`

Role after `2026.2`:

- operator-facing explanation surface

Current condition:

- Partial / transitional
- fleet and observability dashboards now materially use governed run-insight views (`vw_ACM_RunFact`, `vw_ACM_EquipCurrentSnapshot`), and their active copies are aligned
- the master dashboard summary/status panels now also use governed run-insight views, while the deeper asset-specific history panels and the insight/storyboard surfaces still read mostly from legacy score/health tables plus legacy `ACM_Runs` fields
- governed no-score runs are now operator-clear at the fleet/runtime-summary level and at the top of the main asset dashboard, but not yet on the deeper asset-specific explanation/history surfaces

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

Status as of 2026-03-13:

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
- Current runtime truth beyond the slice checklist:
  - load-time structural fast-fail is now live for purely structural no-score batches in `core/acm.py`
  - post-baseline structural fast-fail is now live for authoritative `no_score_rows` batches in `core/acm.py`, so empty-score replay windows can degrade cleanly before feature prep instead of reaching detector errors
- validation-mode pre-score regime-context preview is now live in `core/acm.py` and `core/regimes.py`
- validation-mode cached feature-frame regime preview is now live in `core/acm.py`, `core/detector_orchestrator.py`, and `core/model_persistence.py`, and can suppress before broad detector reconstruction by loading only the cached `regime_model`
  - validation-mode raw regime-context preview is now live before full feature preparation on cached `ACM_RegimeState` paths, and `core/fast_features.py` now exposes a reusable seasonality-only stage so that early preview does not force seasonality work to run twice
  - that raw-preview helper now attempts a cheaper unadjusted pass before paying `seasonality.detect`, so context-driven no-score batches can stop before seasonality when the unadjusted preview is already decisive
  - validation-mode manifest-only feature-schema preview is now live before seasonality and feature-value build on cached-manifest paths, and can suppress additive-growth/schema-blocked baseline-formation batches from raw columns alone
  - the raw pre-feature regime preview path in `core/acm.py` is now helperized behind one focused precheck function, reducing inline entrypoint branching without changing runtime authority or replay behavior
  - post-regime pre-transient suppression is live in `core/acm.py`
- authoritative suppressed runs can now skip detector scoring on compatible cached-regime paths when context blockers are already evident from the previewed regime assignment
- authoritative suppressed runs can now also skip broad detector reconstruction on compatible cached-model paths by doing a regime-only cached preview before full detector initialization
- authoritative suppressed runs now skip zero-day, calibration, fusion, adaptive postprocess, and later drift postprocess
- authoritative suppressed runs now skip sensor-analytics context preparation before persistence
- authoritative suppressed runs now also skip PCA SQL artifacts before final persistence
- authoritative suppressed runs now also skip raw secondary persistence artifacts (`ACM_SensorCorrelations`, `ACM_SensorNormalized_TS`, and per-run `ACM_SeasonalPatterns`) while still writing control-plane tables and `ACM_Run_Stats`
- canonical per-signal signal profiles now flow through `core/representation_pipeline.py` and are written by `core/representation_store.py`; store-time reprofiling remains only as a transitional fallback path
- the governed baseline contract now carries explicit readiness fields (`enough_history_to_proceed` and `baseline_ready`) in addition to runtime mode, candidate state, and contamination/freeze state, reducing the overload still carried by legacy `coldstart_complete`
- the interpretation of legacy `ACM_ActiveModels.RegimeMaturityState` now routes through `core/baseline_governor.py`; `core/smart_coldstart.py` still performs the SQL lookup and retry/progress behavior, but no longer owns the meaning of that lifecycle hint
- validation authority now keeps non-authoritative cached-scoring baseline state out of the runtime frames on governed no-score paths; `core/baseline_governor.py` now persists that state as `TRUSTED_WINDOW_PENDING`, `core/smart_coldstart.py` is down to historian-window/progress helper behavior plus compatibility wrappers, and `core/acm.py` short-circuits before feature prep when no authoritative trusted baseline window is available yet
- baseline-seeding policy ownership now also lives in `core/baseline_governor.py`: `core/acm.py` calls `seed_baseline_safe` from that owner directly, while `core/smart_coldstart.py` keeps only compatibility wrappers for the older helper surface
- the remaining smart-coldstart authority leak is now narrower again: `core/smart_coldstart.py::check_status()` still reads SQL lifecycle/progress state, but the decision about whether that legacy lifecycle hint still implies coldstart now also routes through `core/baseline_governor.py`
- load-stage metadata now also carries explicit governed readiness hints (`baseline_runtime_mode`, `enough_history_to_proceed`, `baseline_ready`, and `coldstart_gate_reason`), so downstream runtime no longer depends only on the overloaded `coldstart_complete` boolean for pre-baseline governance context
- the representation path now consumes those explicit load-stage readiness hints directly: `core/representation_pipeline.py` no longer accepts the raw `coldstart_complete` flag, and the representation refresh/precheck calls in `core/acm.py` now rely on stamped metadata rather than threading that legacy boolean through every authority re-evaluation
- persistence-stage baseline-buffer writes now also prefer governed readiness hints over the legacy boolean: `core/output_manager_services.py` and `core/output_manager.py` now accept stamped `meta` and use `baseline_runtime_mode` / `baseline_ready` before falling back to `coldstart_complete`
- that persistence-path fallback is now removed as well: `core/output_manager_services.py`, `core/output_manager.py`, and the `core/acm.py` persistence-prep call path no longer thread `coldstart_complete`, and baseline-buffer refresh now depends on governed `meta` plus its periodic refresh policy rather than carrying the legacy boolean through the API surface
- the baseline-governor surface is now cleaner too: `core/baseline_governor.py::resolve_runtime_mode()` and `build_shadow_baseline_governance()` no longer accept `coldstart_complete`, and `core/smart_coldstart.py::classify_noop_reason()` now falls back on explicit governed load-stage hints (`enough_history_to_proceed`) rather than the raw legacy boolean
- the public load-stage result is now cleaner too: `core/smart_coldstart.py::DataLoadStageResult` no longer exposes `coldstart_complete`, so downstream runtime consumes `should_continue`, `noop_reason`, and governed `meta` hints rather than treating the legacy boolean as part of the stage contract
- `core/smart_coldstart.py` is now narrower again internally: `load_with_retry()` uses `can_proceed` terminology instead of re-exporting the old `coldstart_complete` concept through its own local flow, and the dead `seed_baseline` / `seed_baseline_safe` compatibility wrappers have been removed entirely because runtime ownership already lives in `core/baseline_governor.py`
- the remaining load-stage coldstart boolean is now gone too: `core/baseline_governor.py::ColdstartLoadDecision` now carries an explicit `use_existing_models` decision with a governed `reason_code`, and `core/smart_coldstart.py` now branches on that explicit load-path contract instead of treating `needs_coldstart` as the operative runtime truth
- the dead retry-era smart-coldstart API baggage is now gone too: `core/smart_coldstart.py::load_with_retry()` no longer accepts unused `max_attempts`, `historical_replay`, or `equipment` parameters, `check_status()` no longer carries the unused `tick_minutes` argument, and `ColdstartState` no longer exposes an `is_ready()` semantic helper that implied coldstart authority still lived there
- the smart-coldstart helper state is now smaller and more truthful too: `core/smart_coldstart.py` no longer stores dead `runtime_mode_hint` state, no longer pretends to be stage-generic when it only persists score-stage progress, and its NOOP messaging now describes governed baseline formation instead of legacy detector-fit semantics
- the remaining retry-era naming is now gone as well: `core/smart_coldstart.py::load_with_retry()` is now `load_window()`, and `ColdstartState` is now a small dataclass that carries only live progress/load-path fields instead of stale state baggage
- governed coldstart/load decisions now also drive both runtime and replay orchestration: `core/smart_coldstart.py::check_status()` and `scripts/sql_batch_runner.py::_check_coldstart_status()` now use governed runtime mode only (`ACM_BaselineGovernance.RuntimeMode`, then `ACM_Runs.RepresentationRuntimeMode`) and default to baseline formation when governed runtime truth is absent
- the runner-side local coldstart-complete shim is gone too: `scripts/sql_batch_runner.py` now uses governed SQL status as the only coldstart/bootstrap completion authority during resume/summary flow, its local progress file only tracks batch position (`last_batch_end`, `batches_completed`), and `core/smart_coldstart.py::build_noop_observability()` now exposes governed runtime readiness wording instead of the old `legacy_fit_ready` field
- `core/adaptive_thresholds.py::maybe_update_adaptive_thresholds()` no longer carries a dead `coldstart_complete` parameter through the health stage path
- `core/fuse.py::run_health_stage()` no longer carries that dead `coldstart_complete` dependency either; the health-stage path now depends on governed representation/baseline state and its actual runtime inputs instead of plumbing the legacy boolean through unchanged
- trained model packages now also persist raw training-signal medians, and `core/fast_features.py` can now reuse cached raw/feature medians on empty-train scoring paths; that replaces the old score-head / score-split mechanics with a purely technical cached-reference path for governed no-score runs
- repeated representation refresh/re-authority assembly is now centralized in `core/representation_pipeline.py`, which lets `core/acm.py` call one shared helper instead of rebuilding compatibility + baseline-governance + authority steps inline at every later gate
- cached regime basis reuse is replay-validated and no longer the primary active blocker
  - observability exporters can now be disabled centrally for dev/replay with `ACM_OBS_DISABLE=1`, and `scripts/sql_batch_runner.py` now respects the same owner-level environment flags
- full `start-from-beginning` replay is now actively validated on `WFA_TURBINE_0` and `WFA_TURBINE_10` in parallel:
  - both turbines moved past the old one-day governed `NOOP` loop into real `BASELINE_FORMATION` training windows
  - both now persist governed follow-on runs after baseline seeding and can short-circuit later one-day no-score windows with authoritative `no_score_rows` outcomes
- the most reliable review source for those long-running parallel replays is currently `ACM_RunLogs`, not ad hoc detached stdout
- source-controlled governed run-insight views are now live and replay-validated:
  - `vw_ACM_RunOutputCoverage`
  - `vw_ACM_RunQualityGates`
  - `vw_ACM_RunFact`
  - `vw_ACM_RunStory`
  - `vw_ACM_EquipCurrentSnapshot`
- the live schema has now been conservatively cleaned:
  - obsolete `ACM_ForecastState` is gone from the live database
  - obsolete `ACM_Forecast_QualityMetrics` is gone from the live database
  - `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md` has been regenerated against the cleaned schema
  - `ACM_RunMetadata` is intentionally retained because `core/run_metadata_writer.py` still writes to it
  - `ACM_AssetProfiles` is intentionally deferred because it is dormant but not yet proven safe to delete automatically

### Audit checkpoint: 2026-03-13

Strict repo audit against this plan shows:

- the implementation is on track through Slice 11, but not beyond it
- the new representation owners, SQL tables, validation-only authority path, and run-level representation summary projection are all real in code
- `G2` is now satisfied in code because suppression reasons are persisted in `ACM_RepresentationStatus`, surfaced by `scripts/sql_batch_runner.py`, and projected onto `ACM_Runs`
- a validation-authority replay on `WFA_TURBINE_10` confirmed that authoritative suppression is activating in runtime, not just in tests
- that replay also exposed two real hardening gaps which are now fixed in code: score-suppressed runs were still attempting score-derived analytics writes, and `ACM_Runs` writes were still allowing `NaN` float payloads after suppression
- the replay harness now also reflects governed runtime truth more accurately: `DEGRADED` is no longer collapsed to `OK`, coldstart replay can treat governed degraded runs as progress when lifecycle state advances, and QA now treats zero score-derived tables as expected when authoritative representation suppression is active
- the replay harness now also resolves governed batch inspection more deterministically: when ACM emits a concrete `RunID`, `scripts/sql_batch_runner.py` inspects that exact run instead of inferring the latest run from downstream forecast tables, and the operator summary now distinguishes ACM execution time from replay source-data time
- the persistence prep path now also blocks baseline buffer mutation when authoritative representation says `learn_allowed = false`, closing a remaining learning-side-effect hole in validation mode
- the governed readiness contract is now clearer in code: `core/baseline_governor.py` emits explicit `enough_history_to_proceed` and `baseline_ready` fields, and `core/comparability_engine.py` now consumes those fields instead of relying only on the older readiness-state string
- the coldstart dual-authority cleanup has also started in code: the legacy `RegimeMaturityState` interpretation now lives in `core/baseline_governor.py`, while `core/smart_coldstart.py` retains only the SQL read plus retry/progress mechanics for that hint
- the target `ACM` database used for replay initially lacked migrations `018` through `022`; that rollout gap is now closed, and validation-mode replay prechecks enforce it before processing starts
- `scripts/sql_batch_runner.py` now has an explicit validation-mode SQL precheck so future replay runs fail fast when the representation SQL contract is missing instead of discovering it mid-run
- zero-day runtime is now partially hardened for validation authority: EWM and `OnlinePCABinner` state are lazily initialized instead of being loaded eagerly at run start, structurally blocked authoritative runs can now skip the zero-day scoring path before that state is loaded, and `OnlinePCABinner` mutation/save now stops when governed learning is disabled
- the latest validation replay still confirms that ACM is representation-aware rather than representation-first, but the runtime gap is now narrower: a fresh governed replay on `WFA_TURBINE_10` proved that cached regime basis-contract reuse is live in runtime and that authoritative post-regime context gating can now short-circuit zero-day, calibration, fusion, and later health work once the batch is already known to be non-scoreable
- authoritative post-regime precheck now goes one step earlier: when regime context is already ambiguous, novel, unknown, or low-confidence, ACM suppresses before transient detection runs, so transient labeling is only paid for batches that still need transition evidence
- validation-mode pre-score regime preview now goes one step earlier again on cached-model compatible basis paths: when the previewed regime context is already ambiguous, novel, unknown, or low-confidence, ACM suppresses before detector scoring runs, so the legacy scored/regime pass is no longer paid for those batches
- persistence prep now also respects authoritative no-score runs more tightly: when score output is already suppressed, ACM skips sensor-analytics context preparation instead of building analytics-only context that will never be consumed
- PCA SQL artifact writes now also respect authoritative no-score runs: when score output is already suppressed, ACM skips the PCA model/loadings/metrics artifact path and only keeps run-scoped control-plane writes plus `ACM_Run_Stats`
- load-time structural fast-fail is now implemented and unit-tested for purely structural blockers, but a direct governed replay on the `2023-06-15` to `2023-07-10` `WFA_TURBINE_10` window also showed why it is not yet the dominant runtime savings path: the decisive blockers on that scoring window were still discovered later as contextual comparability and pending baseline-governance truth
- direct governed `core.acm` replay on `WFA_TURBINE_10` proved `basis=COMPATIBLE` on the stabilized cached-basis path
- the direct governed run that ended at `2026-03-12 19:45:43 UTC` showed authoritative suppression due to `context_ambiguous` and `context_low_confidence`, not basis churn
- that same live path also proved transient detection was skipped on the new pre-transient short-circuit branch
- the direct governed run that ended at `2026-03-12 22:47:05 UTC` proved the new pre-score regime preview path is working end-to-end: persisted SQL truth showed `schema=COMPATIBLE`, `basis=COMPATIBLE`, `baseline=PENDING`, `score_allowed=False`, `learn_allowed=False`, suppressed reasons `context_ambiguous` / `context_low_confidence`, and the console showed no detector scoring, no transient detection, no zero-day scoring, and no fusion/calibration path for that batch
- that same live run also showed the next bottleneck has shifted: feature preparation, seasonality detection, model loading, and the preview itself now dominate the suppressed validation path, so the remaining savings opportunity is earlier than detector scoring
- a direct governed run on `WFA_TURBINE_0` for `2023-07-30 06:10:00` through `2023-08-24 06:10:00`, recorded in `ACM_Runs` as `RunID=98AB97F6-AC8C-4F8D-AB7F-226F579C3475`, proved the new regime-only cached feature preview path end-to-end: ACM loaded only `regime_model` from `ModelRegistry`, reused the cached basis contract, suppressed before full detector initialization, skipped zero-day/calibration/fusion/adaptation, and persisted `schema=COMPATIBLE`, `basis=COMPATIBLE`, `baseline=PENDING`, with suppressed reasons `context_novel` / `context_ambiguous`
- that same `WFA_TURBINE_0` run also tightened the runtime-cost picture again: the remaining dominant no-score cost is now feature preparation, seasonality detection, raw preview, and regime-only preview loading, not broad detector reconstruction or the already-removed secondary artifact writes
- a follow-up governed rerun on `FD_FAN` for `2025-08-20 23:30:00` through `2025-09-14 23:30:00` confirmed that the older post-baseline structural fast-fail still holds after the new regime-only preview slice: ACM degraded cleanly in about `0.6s`, never entered feature prep, and preserved the authoritative `no_score_rows`-style blocked path instead of regressing into later detector/runtime work
- a direct governed run on `WFA_TURBINE_0` for `2023-07-30 06:10:00` through `2023-08-24 06:10:00` proved the lighter validation path on another wind turbine: `basis=COMPATIBLE`, zero-day stayed blocked, detector scoring was skipped from the pre-score context preview, and the batch degraded cleanly in about six seconds with observability disabled
- a later direct governed rerun on that same `WFA_TURBINE_0` window proved the new raw-preview slice is live but not yet universally decisive: ACM now loads `ACM_RegimeState`, first attempts a cheaper unadjusted raw regime-context preview, then falls back to the seasonality-adjusted raw preview only when the cheap pass is not decisive, but on that window the final decisive blockers still arrived on the later cached-model preview path
- that same `WFA_TURBINE_0` rerun also shifted the runtime-cost picture: the suppressed batch finished cleanly in about `13.2s`, with persistence of non-score-derived artifacts (`persist.pipeline_outputs=9.3s`) dominating the remaining cost, while `features.build=0.6s`, `models.load=0.4s`, and `representation.preview.raw.seasonality=0.4s`
- the follow-up no-score persistence slice is now replay-validated on direct governed runs for `WFA_TURBINE_0` and `WFA_TURBINE_38`: authoritative suppressed runs now complete in about four seconds, raw secondary artifact writes are skipped, and SQL spot-checks confirm `ACM_RepresentationStatus`, `ACM_BaselineGovernance`, and `ACM_Run_Stats` still write while `ACM_SensorCorrelations`, `ACM_SensorNormalized_TS`, `ACM_SeasonalPatterns`, and `ACM_PCA_Metrics` stay empty for those runs
- a later direct governed rerun on `WFA_TURBINE_0` for the same `2023-07-30 06:10:00` through `2023-08-24 06:10:00` window confirmed that the raw-preview helper extraction is behavior-preserving: the run still degraded cleanly in about `3.9s`, detector scoring stayed skipped from the pre-score preview path, and the remaining cost profile stayed centered on feature prep, model load, and representation persistence rather than on the removed raw secondary artifacts
- a direct governed run on `FD_FAN` for `2025-08-20 23:30:00` through `2025-09-14 23:30:00` exposed a real empty-score replay bug: baseline seeding consumed the full window, `score` became empty, and ACM previously crashed later in detector scoring; that gap is now fixed in `core/acm.py` by a post-baseline structural fast-fail keyed off authoritative `no_score_rows`
- the rerun of that same `FD_FAN` window after the fix now degrades cleanly in under a second with `score_allowed=False`, `learn_allowed=False`, and suppressed reason `no_score_rows`, proving the fix without reintroducing detector-specific special cases
- a later `FD_FAN` rerun after the raw-preview/refresh refactor still degrades cleanly in under a second, confirming that the new helperized orchestration did not regress the post-baseline `no_score_rows` fast-fail
- a fresh governed `FD_FAN` run on `2025-08-20 23:30:00` through `2025-09-14 23:30:00` after the explicit-readiness contract slice still degraded cleanly after baseline seeding, proving the additive contract change did not break runtime behavior; it also re-confirmed that legacy `score head` baseline seeding is still a real transitional authority path that must be retired later
- a later governed rerun of that same `FD_FAN` window, recorded as `RunID=D8F25443-3078-456E-9CFC-62052A8D903F`, proved the semantic cleanup of that shadow-only path: `ACM_BaselineGovernance` now reports `RuntimeMode=BASELINE_FORMATION` and `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, while `ACM_RepresentationStatus` suppresses the run with `baseline_formation_scoring_disabled` instead of presenting the batch as `ONLINE_SCORING` plus later veto reasons
- a fresh governed `FD_FAN` probe after the cached-training-reference slice, recorded as `RunID=2CE7368D-A3D5-4A09-A62E-0900D8AFBB5C`, confirmed that the new feature/model reference support did not regress the live no-score path: the shadow-only score-derived candidate was still retained without being applied to runtime, ACM still short-circuited before feature, detector, regime, zero-day, and health work, and the run remained a clean `BASELINE_FORMATION` / authoritative no-score outcome in about `0.6s`
- the follow-up governed `FD_FAN` probe recorded as `RunID=1E68FB8A-D877-4D79-9378-EB7CA5F86DA5` confirmed the ownership demotion did not change runtime truth: `core/acm.py` now calls the governed seeding owner directly, `core/smart_coldstart.py` is down to compatibility wrappers, and the run still remained a clean `BASELINE_FORMATION` / authoritative no-score outcome in about `0.9s`
- the latest governed `FD_FAN` probe, recorded as `RunID=0B45AF70-1A2E-4114-BF62-8090B9624D20`, proves the fallback mechanics themselves are now gone: `core/baseline_governor.py` persists `BaselineCandidateState=TRUSTED_WINDOW_PENDING` with `ShadowRefreshState=WAITING_FOR_TRUSTED_WINDOW`, `ACM_RepresentationStatus` degrades the batch with `baseline_trusted_window_pending`, and ACM short-circuits before feature, detector, regime, zero-day, and health work without inventing a score-derived baseline slice
- a parallel governed validation probe on `FD_FAN`, `WFA_TURBINE_0`, and `WFA_TURBINE_10`, recorded respectively as `RunID=34CBBB70-34DD-475C-971F-E1292B435FED`, `RunID=F3A34467-B624-4077-8315-794D1DFBB12F`, and `RunID=1E787305-B97D-4EAC-A4E8-8BA54E12ED63`, confirmed the same runtime truth across three assets in parallel: each run short-circuited before feature/detector/regime work, each persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ScoreAllowed=0`, `LearnAllowed=0`, and none wrote score rows
- a later parallel governed validation probe on the same three assets, recorded as `RunID=E3321F1F-3999-4382-AC7B-A400D34559AA` (`FD_FAN`), `RunID=1BE8481B-F8C6-4422-95BE-3ADC7D131EC6` (`WFA_TURBINE_0`), and `RunID=37B4BD08-5A66-4D51-B098-6C706AD8A33B` (`WFA_TURBINE_10`), confirmed that the new explicit load-stage readiness hints do not change runtime truth: all three still short-circuited before feature/detector/regime work, all three persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ScoreAllowed=0`, `LearnAllowed=0`, and all three wrote zero score rows
- a fresh parallel governed validation probe on `FD_FAN`, `WFA_TURBINE_0`, and `WFA_TURBINE_10`, recorded respectively as `RunID=47632A3A-1879-47E4-A29F-9D289CFACEA0`, `RunID=B497BA6A-45D5-4050-988C-1F08AB23B0CC`, and `RunID=CF3AF6C4-50A4-456D-92B3-4789E8B0EF9B`, confirmed the next cleanup slice is behavior-preserving: the representation API no longer threads `coldstart_complete`, but all three assets still short-circuited before feature/detector/regime work, all three persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ScoreAllowed=0`, `LearnAllowed=0`, and all three wrote zero score rows
- another fresh parallel governed validation probe on `FD_FAN`, `WFA_TURBINE_0`, and `WFA_TURBINE_10`, recorded respectively as `RunID=964BE814-C295-499D-A3F0-A923F98169D7`, `RunID=60703FFF-57EE-4DD3-B4BE-4D2679A6F157`, and `RunID=C14F2C09-9EB6-4A28-B5FB-3F28B1E5AA56`, confirmed the persistence/helper cleanup is also behavior-preserving: all three assets still short-circuited before feature/detector/regime work, all three persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ScoreAllowed=0`, `LearnAllowed=0`, and all three wrote zero score rows
- a subsequent parallel governed validation probe on `FD_FAN`, `WFA_TURBINE_0`, and `WFA_TURBINE_10`, recorded respectively as `RunID=0C41E078-5F2E-4DBA-89E2-3F96ABE5D3B3`, `RunID=11693495-6E07-4B59-9C97-73166502007E`, and `RunID=80DF7D5A-1122-46BE-ADDB-707EACF69D4C`, confirmed the health-stage cleanup is also behavior-preserving: all three assets still short-circuited before feature/detector/regime work, all three persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ScoreAllowed=0`, `LearnAllowed=0`, and all three wrote zero score rows
- the latest parallel governed validation probe on `FD_FAN`, `WFA_TURBINE_0`, and `WFA_TURBINE_10`, recorded respectively as `RunID=D3BC49DC-EE0F-4F0F-B6B4-3959D4FC9DE6`, `RunID=BAE69B33-8BA0-4560-A90C-EB1CE386540A`, and `RunID=52BA7364-8303-49C0-AB1A-59A8C9FF3E44`, confirms that the persistence-path API cleanup is also behavior-preserving: all three assets still short-circuited before feature/detector/regime work, all three persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ShadowRefreshState=WAITING_FOR_TRUSTED_WINDOW`, `ScoreAllowed=0`, `LearnAllowed=0`, and all three wrote zero score rows
- the next parallel governed validation probe on the same three assets, recorded respectively as `RunID=D3C797E0-555A-4845-91BE-F31118D068B3`, `RunID=4D1E6C33-C842-4A74-8185-2200E3C1D0CB`, and `RunID=623D41CC-DC7A-4BB4-9DB1-B9B1EEC630A3`, confirmed that removing `coldstart_complete` from the baseline-governor surface is also behavior-preserving: all three assets still short-circuited before feature/detector/regime work, all three persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ShadowRefreshState=WAITING_FOR_TRUSTED_WINDOW`, `ScoreAllowed=0`, `LearnAllowed=0`, and all three wrote zero score rows
- the latest parallel governed validation probe on the same three assets, recorded respectively as `RunID=763A8A6F-EE90-4044-AFDE-85DED0AD06FF`, `RunID=41315FB1-364E-4A49-9905-4471F065C3B2`, and `RunID=08B2D77B-1093-4575-A3BD-F5DB8B7F6362`, confirmed that removing `coldstart_complete` from the public load-stage result is also behavior-preserving: all three assets still short-circuited before feature/detector/regime work, all three persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ShadowRefreshState=WAITING_FOR_TRUSTED_WINDOW`, `ScoreAllowed=0`, `LearnAllowed=0`, and all three wrote zero score rows
- the next parallel governed validation probe on the same three assets, recorded respectively as `RunID=B1473621-7638-4C57-92B3-899DD6760981`, `RunID=3945BE89-CF49-4C2E-BBA4-BA2566280087`, and `RunID=93480FF7-9C3A-4779-B25A-DA45939A4704`, confirmed that the next smart-coldstart cleanup is also behavior-preserving: internal `can_proceed` naming and deletion of the dead baseline-seeding wrappers did not change runtime truth, and all three assets still persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ShadowRefreshState=WAITING_FOR_TRUSTED_WINDOW`, `ScoreAllowed=0`, `LearnAllowed=0`, with zero score rows
- the latest parallel governed validation probe on the same three assets, recorded respectively as `RunID=e50175be-a412-4fa3-8882-418a7811ea7a`, `RunID=71835aa3-81ae-4b70-ab72-65dbf8759738`, and `RunID=34622f4e-c334-4575-8bea-898479b2c678`, confirmed that replacing the last load-stage `needs_coldstart` boolean with the explicit `use_existing_models` / `reason_code` contract is also behavior-preserving: all three assets still short-circuited before feature/detector/regime work, all three persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ShadowRefreshState=WAITING_FOR_TRUSTED_WINDOW`, `ScoreAllowed=0`, `LearnAllowed=0`, and all three wrote zero score rows
- the next governed-only coldstart validation probe, recorded respectively as `RunID=46b1cb4b-f983-4e2c-acf5-1e54a0a58e8e`, `RunID=31c85cfe-5724-4712-9bdb-209702ca4238`, and `RunID=22f34578-ee55-4a9a-b4c0-55ba9eb9da40`, confirmed the lifecycle fallback removal is also behavior-preserving: `FD_FAN` still exits cleanly as `NOOP` when no governed row is present, while `WFA_TURBINE_0` and `WFA_TURBINE_10` still persist governed `BASELINE_FORMATION` truth with zero score rows and later no-score suppression on their existing preview paths
- the next parallel governed validation probe on the same three assets, recorded respectively as `RunID=ef4e00f2-b03d-4a85-91a1-e07a2224d4d7`, `RunID=3cf17bf2-5e1e-417c-aba6-b5ba445873bd`, and `RunID=698d5b83-4f8f-4d09-ac94-92749afec5a3`, confirmed that removing the dead retry-era smart-coldstart API baggage is also behavior-preserving: all three assets still short-circuited before feature/detector/regime work, all three persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ShadowRefreshState=WAITING_FOR_TRUSTED_WINDOW`, `ScoreAllowed=0`, `LearnAllowed=0`, and all three wrote zero score rows
- the latest parallel governed validation probe on `FD_FAN`, `WFA_TURBINE_0`, and `WFA_TURBINE_10`, recorded respectively as `RunID=59161dfd-5f2a-4d1c-a5ca-47910f65b7b7`, `RunID=4781a34f-a17f-42a7-979c-5ff0a39f11f2`, and `RunID=0336fb74-beb6-4426-9c16-4b70b13afdb6`, confirmed that trimming the last dead smart-coldstart state is also behavior-preserving: all three assets still short-circuited before feature/detector/regime work, all three persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ShadowRefreshState=WAITING_FOR_TRUSTED_WINDOW`, `ScoreAllowed=0`, `LearnAllowed=0`, and all three wrote zero score rows
- the latest parallel governed validation probe on `FD_FAN`, `WFA_TURBINE_0`, and `WFA_TURBINE_10`, recorded respectively as `RunID=5b565207-44f0-4eca-8724-b38de3ac0de2`, `RunID=c3116f56-27e1-40e6-b7fe-304cb9120573`, and `RunID=b049a07a-9da1-4976-9f80-9e712cd37ee7`, confirmed that removing the last misleading retry/helper semantics from `core.smart_coldstart` is also behavior-preserving: all three assets still short-circuited before feature/detector/regime work, all three persisted `RuntimeMode=BASELINE_FORMATION`, `BaselineCandidateState=TRUSTED_WINDOW_PENDING`, `ShadowRefreshState=WAITING_FOR_TRUSTED_WINDOW`, `ScoreAllowed=0`, `LearnAllowed=0`, and all three wrote zero score rows
- the next governed 3-asset validation probe, recorded respectively as `RunID=b0aa40a0-8123-4d0d-a920-5b7ce1435427`, `RunID=972a697d-74e3-4548-bd48-6310ef0aef71`, and `RunID=df3658a9-f380-4950-99c3-28de487d7279`, confirmed the runner/runtime cutover to governed coldstart authority: `FD_FAN` now cleanly NOOPs when no governed row exists, `WFA_TURBINE_0` still reaches the later pre-transient suppression path with `RuntimeMode=BASELINE_FORMATION`, and `WFA_TURBINE_10` still uses the cached feature-preview suppression path while `scripts/sql_batch_runner.py` no longer treats lifecycle state as the primary coldstart completion authority
- the latest major runtime-ordering replay, recorded respectively as `RunID=a2cc9e19-e1bb-4909-8dfc-1851beb57515`, `RunID=5503ffaa-faad-4778-a9e0-1afb1e56d500`, and `RunID=d40a7f60-9c4a-461a-81b2-143f59f62aae`, proved the manifest-only schema gate end-to-end: `FD_FAN` remained a clean governed `NOOP`, while both `WFA_TURBINE_0` and `WFA_TURBINE_10` short-circuited from the manifest-only feature-schema preview before `seasonality.detect` and before `Building features`, persisted `RepresentationSchemaCompatibility=ADDITIVE_GROWTH`, `RepresentationBasisCompatibility=PENDING`, `RuntimeMode=BASELINE_FORMATION`, `ScoreAllowed=0`, and wrote zero score rows
- a direct governed coldstart run on `WFA_TURBINE_38` for `2023-06-22 07:40:00` through `2023-07-17 07:40:00` proved the opposite boundary: because `learn_allowed=True` in `BASELINE_FORMATION`, the new structural fast-fail did not incorrectly short-circuit detector training; ACM trained, labeled regime context, then suppressed later for baseline-formation reasons
- a full parallel `start-from-beginning` replay is now behaving correctly for both `WFA_TURBINE_0` and `WFA_TURBINE_10`: SQL truth shows that the runner no longer repeats the same first-day deferred coldstart window, both turbines advanced to four-day `BASELINE_FORMATION` windows with `learn_allowed=True`, and both then progressed into later one-day governed no-score windows that short-circuit cleanly after baseline seeding
- `ACM_RunLogs` has now been confirmed as a practical SQL-backed log source for replay review: the latest `T0` and `T10` governed batches show the exact short-circuit message, proving that we can read real per-run console flow from SQL even when detached Windows runner launches were not teeing to files
- repo audit against dashboards and SQL-backed operator surfaces still shows a visibility gap, but the SQL-view side is now improved: new source-controlled run-insight views (`vw_ACM_RunOutputCoverage`, `vw_ACM_RunQualityGates`, `vw_ACM_RunFact`, `vw_ACM_RunStory`, `vw_ACM_EquipCurrentSnapshot`) are live and correctly classify both `SUPPRESSED_VALID` and `BASELINE_FORMATION` replay runs
- Grafana cutover is now partially real in repo: `grafana_dashboards/acm_fleet_overview.json`, `grafana_dashboards/acm_observability.json`, `grafana_dashboards/acm_master_complete.json`, and their `grafana_dashboards/active/` copies now read governed run-insight views for fleet/runtime and current-status summary panels; the remaining gap is the deeper asset-specific explanation/history surface under `RG-15`
- conservative live-schema cleanup is now partly complete:
  - `ACM_ForecastState` is gone from the live DB and from the refreshed comprehensive schema reference
  - `ACM_Forecast_QualityMetrics` is also gone from the live DB and the refreshed schema reference
  - `ACM_RunMetadata` remains live by design because it still has an active runtime writer
  - `ACM_AssetProfiles` remains a dormant legacy table and should be reviewed again during later cleanup, not dropped speculatively in the current slice
- zero-day replay still carries a legacy influence path deeper than intended: feature prep, seasonality detection, and detector/model loading still run before authoritative context/baseline gating resolves many no-score outcomes, so ACM still needs an earlier representation-first operating shape
- repeated `basis=INCOMPATIBLE` results are no longer the primary blocker on current code; cached basis-contract reuse has now been replay-validated on a direct governed `core.acm` scoring run, and the active blocker has shifted to contextual comparability and baseline-governance readiness (`context_ambiguous`, `context_transition_active`, `context_low_confidence`, plus pending/unassessed baseline compatibility)
- `ACM_RepresentationSchemas` and `ACM_SignalProfiles` currently behave more like per-run audit tables than the final control-plane shapes described in the target architecture; they are useful now, but they still need registry-style ownership and canonical pipeline sourcing before completion
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

### Confirmed next improvements from validation replay

These items are now promoted from implied debt to explicit execution work:

- keep extending earlier governed no-score gating, but do it through extracted owners rather than more inline `core/acm.py` policy: load-time and post-baseline structural fast-fail now exist, raw regime-context preview now exists before full feature prep, regime-context precheck now short-circuits detector scoring on compatible cached-model paths, and later paths still short-circuit transient detection
- the no-score persistence cleanup is now landed and replay-validated, and the newer regime-only cached preview path now avoids broad detector loading on some suppressed runs, so the dominant remaining runtime cost has shifted to earlier feature preparation, seasonality, raw preview, and narrow regime-preview loading rather than secondary artifact writes
- the newer unadjusted raw-preview pass is also now live and replay-safe: it removes the seasonality cost on context-driven no-score batches only when the cheap pass is already decisive, but the latest `WFA_TURBINE_10` / `WFA_TURBINE_0` validation windows still mostly hit later feature-preview or post-regime blockers, so the next material runtime-ordering gain must target schema/feature-preview cost, not just seasonality
- that schema/feature-preview gain is now landed and replay-validated too: additive-growth/schema-blocked baseline-formation batches can now short-circuit from a manifest-only feature-schema preview before seasonality and feature-value build
- the next runtime slice should therefore target the remaining expensive learnable baseline-formation path and trusted-window package evolution, not more basis fixes and not more post-score cleanup
- the next baseline-governance slice should now target remaining prep-cost reduction and trusted-window package evolution, not more lifecycle fallback cleanup: the baseline-governor surface, persistence path, health stage, representation path, public load-stage result, smart-coldstart helper state, runner coldstart authority, and lifecycle fallback semantics are now cleaned up enough that the main remaining coldstart/baseline work is final helper demotion plus end-state trusted-window/package semantics
- keep validating `scripts/sql_batch_runner.py` under full-history parallel replay:
  - the governed `NOOP` coldstart retry bug is now fixed
  - next runner work should improve long-run readability and operator review, not re-open outcome semantics that are now correct
- plan `RG-15` dashboard and SQL-view updates explicitly around representation-aware operator truth:
  - the fleet and observability dashboards are now partially cut over and can show governed no-score batches correctly at the run/fleet level
  - the master dashboard summary panels are now also partially cut over, but the remaining asset-specific history/explanation panels still misread governed no-score batches as empty legacy output instead of valid authoritative suppression
  - replacement dashboard queries should consume `vw_ACM_RunFact`, `vw_ACM_RunStory`, and `vw_ACM_EquipCurrentSnapshot` first, then fall back to legacy score/health views only where needed
  - keep the new run-insight views source-controlled and authoritative for governed operator truth instead of scattering representation logic across dashboard queries
- extend the zero-day hardening that is already landed:
  - lazy EWM / `OnlinePCABinner` initialization is now implemented for structurally blocked validation runs
  - `OnlinePCABinner` observe/save side effects are now blocked when governed learning is disabled
  - post-regime context gating now also blocks zero-day, calibration, fusion, and later health work when authoritative suppression is already known
  - validation-mode pre-score regime preview now also blocks the detector-scoring pass on compatible cached-model runs
  - validation-mode raw regime preview now also probes comparability before full feature prep on cached `ACM_RegimeState` paths
  - remaining work is to stop more of the expensive pre-feature path earlier where it materially changes outcomes, because suppressed-run persistence cost is no longer the dominant runtime expense on the validated no-score path
- continue replay validation with the stabilized basis contract now that direct governed runs are producing `basis=COMPATIBLE`; the remaining replay focus is context/baseline governance, not cached-basis churn
- tighten operator semantics for authoritative no-score runs so runtime mode, scoreability, and summary language are coherent without needing to inspect logs manually
- convert representation persistence from “useful per-run audit rows” toward the final contract:
  - `ACM_RepresentationSchemas` should become a schema/basis registry, not just a run-scoped echo table
  - `ACM_SignalProfiles` now persists canonical pipeline-produced per-signal profiles in the normal path; remaining work is to remove the transitional store-time fallback once replay and backfill safety are proven

### Architecture hygiene review rule

The refactor must include periodic objective code review checkpoints so ACM does not drift into wrapper-heavy or orchestration-heavy complexity.

Required review cadence:

- run a focused architecture/code review after every runtime-affecting slice
- run a broader repo review at the end of each major gate (`G1`, `G2`, `G4`, `G6`)
- do not treat "tests passed" as sufficient proof that the implementation stayed clean

Every review must explicitly check:

- whether `core/acm.py` got simpler or more complex
- whether ownership moved into the intended module instead of adding another transitional wrapper
- whether a new helper is a real owner or just indirection with no analytical value
- whether runtime decisions are becoming earlier and clearer, not just vetoed later
- whether persistence semantics became cleaner or more ad hoc
- whether logs, summaries, and SQL outputs reflect governed runtime truth cleanly
- whether any new branch, adapter, or fallback exists only because it was convenient

The review must call out:

- wrapper creep
- duplicate authority
- hidden policy in orchestrators
- policy encoded in persistence or logging layers
- temporary code that is no longer pulling its weight
- anything that makes a future cleanup harder than it needs to be

The default review stance is:

- prefer fewer owners, clearer boundaries, and explicit contracts
- reject complexity added only to avoid doing the extraction properly
- accept transitional code only when it directly protects replay safety or cutover safety

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

Documentation maintenance rule:

- every runtime-affecting slice must update:
  - `Implementation progress`
  - `Audit checkpoint`
  - the relevant file entries in `File-by-file execution playbook`
  - `SQL and persistence design` if runtime SQL semantics changed

## SQL and persistence design

`ACM_Scores_Wide` remains the detector-output table.

### Target control-plane design

Representation-governance control-plane data belongs in dedicated companion artifacts:

1. `ACM_RepresentationStatus`
   - per `EquipID`, `Timestamp`, `RunID`
   - stores representation version, state version, integrity grade, context confidence, context stability, score allowed, learn allowed, baseline compatible, schema compatibility, degraded reason, source window range

2. `ACM_SignalProfiles`
   - canonical per-signal profile store
   - target shape is durable signal-governance state rather than a replay-only echo
   - stores missing ratio, flatline ratio, effective cadence, variability score, monitorability class, and reason codes from the canonical profiler output

3. `ACM_RepresentationSchemas`
   - schema and basis registry
   - target shape stores schema version, basis signature, feature list, scaler params, encoder type, compatibility class, and registry-style reuse metadata

4. `ACM_BaselineGovernance`
   - baseline package and adaptation decisions
   - stores readiness, contamination verdict, freeze state, shadow refresh status, promoted package version

### Current live SQL shape

1. `ACM_RepresentationStatus`
   - current live shape is aligned enough to keep as the main run-scoped representation verdict table
   - it is already useful for validation authority, suppression reasons, and run inspection

2. `ACM_SignalProfiles`
   - current live shape is run-scoped audit data keyed by run, equipment, timestamp, and signal
   - it is useful now, but it is not yet the final canonical per-signal profile store

3. `ACM_RepresentationSchemas`
   - current live shape is run-scoped audit data keyed by run, equipment, and timestamp
   - it is useful for replay inspection, but it is not yet a true schema/basis registry

4. `ACM_BaselineGovernance`
   - current live shape is acceptable as the main run-scoped governance table
   - remaining work is in runtime semantics and authority timing more than SQL table shape

5. Transitional notes
  - canonical pipeline-produced signal profiles are now the normal source for `ACM_SignalProfiles`
  - store-time reprofiling is still present only as a backward-compatible fallback and should be removed after replay-qualified validation
  - the live schema no longer contains `ACM_ForecastState` or `ACM_Forecast_QualityMetrics`
  - `ACM_RunMetadata` remains in the live schema because it still has an active runtime writer
  - `ACM_AssetProfiles` remains present as dormant legacy data and is not currently part of the governed runtime contract

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

# ACM2 Implementation Plan: Building the Gem

> The build guide. Design basis: docs/acm-gem-plan.md (target architecture) with
> docs/acm-rethink-plan.md as the conceptual map. This document covers what gets
> built, in what order, with what engineering discipline, and how source control
> works. No open decisions remain - every previously-open item is resolved here.
> Status: ADOPTED as the working plan, 2026-07-02.

Context that shapes everything: what exists today is a lab, not a deployment.
There are no users, no production, no fallback obligation. This is a greenfield
build with an unusually well-stocked quarry (salvageable components) and good lab
equipment (datasets, harnesses). We build the gem directly.

---

## 1. Two Requirements Folded Into the Design (2026-07-02)

### 1.1 Hardware adaptation is a system capability, not a decision

The system probes its environment at startup - GPU presence and VRAM, CPU cores,
available memory - and selects its own capability tier:

- **Tier 0 (CPU, modest)**: per-channel probabilistic prediction with lightweight
  models; full verdict vocabulary; full guarantee. Everything works everywhere.
- **Tier 1 (CPU, strong)**: larger models, richer conditioning, more frequent
  rebuilds, deeper novelty search.
- **Tier 2-S (small GPU, ~8GB VRAM)**: small foundation-model variants and
  compact world models; full Tier 2 semantics at reduced capacity. Reference
  hardware: the RTX 4060-class dev box (Section 10).
- **Tier 2 (GPU)**: transformer-class world model with foundation-prior
  adaptation; dynamics-drift channel at full depth.

Rules:
- Verdict SEMANTICS are identical across tiers; only detection POWER differs.
  The false-alarm guarantee (alpha) holds at every tier - validity is tier-free.
- Tier selection re-evaluates at runtime. Hardware appears -> upgrade at the next
  rebuild. Hardware disappears -> degrade gracefully. Monitoring never stops
  because hardware changed.
- Training/adaptation is scheduled opportunistically (rebuild windows); inference
  is CPU-cheap at every tier by design.
- The active tier and its consequences ("prognostic horizon shorter at Tier 0")
  are visible in the UI as part of the confidence story - the system explains its
  own capability honestly.

### 1.2 Multi-asset is a construction principle, not a feature

ACM2 runs 1 to 1000+ assets concurrently. Analytically each asset is an island
(no cross-asset models - unchanged principle); operationally the platform is a
fleet machine:

- Per-asset isolation makes the workload embarrassingly parallel: one asset's
  fast path / slow path / immune path never touches another's state.
- A resource governor sets concurrency from the hardware probe plus measured
  per-asset cost (memory and wall-clock are measured empirically per asset and
  fed back - the BLAS-threads-times-workers OOM lesson from the lab is a standing
  input here: thread caps per worker, workers sized to measured memory).
- Storage is partitioned per asset (raw history, summaries, ledger, verdicts) so
  fleet size scales storage linearly and never contends.
- Slow-path rebuilds are staggered across the fleet by the scheduler so the
  amortized cost stays flat (never all assets rebuilding at once).
- UI adapts to fleet size by aggregation: the fleet view is a verdict-first
  matrix (counts and worst-first sorting over the six verdicts), drill-down is
  lazy, and every rendering lesson already learned in the lab UI (fragment
  batching, lazy episode rows, data-equality debounce) carries forward as
  standing requirements. One asset renders as a degenerate fleet of one - there
  is no separate single-asset mode.

## 2. All Decisions, Resolved

No item below is delegated. Each is the best call available now, with the trigger
that would revisit it stated explicitly.

| # | Decision | Resolution | Rationale / revisit trigger |
|---|---|---|---|
| D1 | Alpha (false-alarm budget) | One false alarm per asset-year, per asset. Single dial, global default, never per-site tuned. Spent hierarchically across the e-process bank (each timescale strategy funded from the shared budget). | Industry-credible unattended rate; loose enough to preserve power. Revisit only if operators ask for stricter (never looser without evidence). |
| D2 | Recency cap | Recent window contributes at most 20% weight to the definition of normal; lifetime evidence holds the other 80%. | Bounds the boiling frog arithmetically while allowing legitimate aging. Revisit if immune-path calibration shows systematic staleness on fast-aging assets. |
| D3 | Rebuild cadence | Weekly scheduled per asset (staggered across fleet) + event triggers: epoch change (intervention), immune-check failure, tier change. | Weekly bounds staleness at negligible cost; triggers cover everything urgent. |
| D4 | Conditioning | Learned (world model / probabilistic predictor conditions on history and channels automatically). No designated-covariate configuration exists at any tier. | Dissolves per-asset-class setup; Tier 0 models condition on lagged inputs, higher tiers condition on everything. |
| D5 | Fusion auto-tune | Retired outright. Never rebuilt. Evidence combination happens at the e-process level (each scorer's evidence stream is its own betting strategy; the bank combines wealth). | The old mechanism was confirmed dead weight; the wrapper makes score-level weighting unnecessary. |
| D6 | Model class (Tier 2) | Transformer-class, patch-based. | Foundation priors are transformer-class; adaptation path and tooling maturity dominate. Revisit at S7 only if the adaptation spike shows a state-space model materially better on SCADA cadence. |
| D7 | Foundation prior | Adopted automatically at Tier 2 when the S7 spike passes; Tier 0/1 modest models are the automatic path elsewhere. Not a user choice. | The design benefits from the prior but never depends on it. |
| D8 | Prognostic exposure | Self-gating: failure-time distributions appear in UI/report only after their own conformance check passes for that asset. Until then the escalating verdict shows trend evidence without a horizon. | Never show an uncalibrated date; never hide a calibrated one. |
| D9 | Repo posture (RE-REVISED 2026-07-04, user directive) | SAME repository (ACM). The new spine lives in a new top-level package acm2/; old pipeline code is in-tree quarry, copied deliberately and deleted when superseded, never imported live into acm2/. The never-built filter is enforced by review checklist (factory doc Section 5) instead of physical separation. | User directive overrides the clean-history argument. The agent factory (Section 10, docs/acm2-factory.md) needs one workdir for board, briefs, and CI; a single repo keeps the whole factory pointed at one place. Import-boundary discipline (no acm2/ -> old-code imports) is a CI check, recovering most of what physical separation bought. |
| D10 | Placeholder scorer in the skeleton | The existing six detectors, unchanged, imported as-is. | Fastest route to a standing spine; the wrapper is scorer-agnostic; they are demoted at S4 and retired when they stop earning their compute. |
| D11 | Pilot assets (re-revised 2026-07-04) | One CARE anomaly event + one CARE normal event + one live simulator asset. These are LAB BENCH MATERIAL (test data for building), not a benchmarking program - public leaderboard chasing remains explicitly out of scope. | Ground truth for sensitivity, a clean asset for alpha conformance, a live-streaming asset for the operational path. In deployment, ACM is bundled with a historian-class data source per asset; the lab pilots stand in for that. |
| D15 | Development workforce (2026-07-04) | ALL code is written by AI agents - cloud frontier agents (Claude Code, Codex-class) for architecture-critical and novel components plus review; a local agent (Hermes / qwopus-class on the RTX 4060 box) for high-volume low-stakes work and overnight evidence runs. The human role is architect and approver; no human writes code. | Section 10 defines the full workforce model, verification discipline, and hardware rules. |
| D16 | Historian backfill (2026-07-04) | DEFERRED. Pilots ingest files/streams; the store's backfill path keeps the interface slot so the capability lands later without rework. | User directive; nothing on the critical path depends on it. |
| D12 | Exchangeability scheme | E-processes run on the surprise/score stream after model conditioning (residual space), with block-based betting to absorb residual serial dependence. Empirical alpha-conformance on known-healthy stretches is the S1 gate - the scheme is validated, not assumed. | THE technical trap of the whole design; gated accordingly. |
| D13 | Novelty substrate | Matrix profile runs over the low-dimensional surprise stream (per-channel surprise and aggregate), not the raw 100-1000 channel space. | Dissolves the dimensionality problem by construction; raw-space profiles only if S5 evidence demands them. |
| D14 | Verdict store | Verdicts, evidence trails, ledger, and summaries live in the existing store layer (SQLite default / MSSQL optional), extended - salvaged plumbing, new tables. Raw history is file-partitioned per asset (parquet-style), not in the relational store. | Right tool per payload; keeps report/UI plumbing salvageable. |

## 3. Build Doctrine

1. **Walking skeleton first.** The entire spine, end to end, thin and crude, on
   the pilot assets - then deepen components in risk order. Integration risk
   surfaces in week one, not month four. From the day the skeleton stands, ACM2
   exists and every week makes a working thing better.
2. **Validity is never crude.** The e-process decision layer is real from day
   one. The scorer may be a placeholder forever-upgraded; the guarantee is a
   property of ACM2 from its first week.
3. **The referee arrives before the athletes.** The statistical acceptance
   harness (injection sensitivity, alpha conformance, degeneracy checks) is built
   immediately after the skeleton and gates every subsequent phase.
4. **No fallback, no parallel-run, no migration scaffolding.** The old pipeline
   is quarry. When a phase supersedes old code, the old code is deleted in that
   same phase. Nothing is kept "just in case."
5. **Research-grade parts stay off the critical path.** Foundation prior,
   dynamics drift: time-boxed spikes producing go/no-go evidence before any
   production commitment. The spine never waits on them.
6. **Design-time evidence only.** CARE and public datasets are regression
   instruments and acceptance evidence - never tuning targets. The label-driven
   patching loop (rethink plan R12) does not exist in ACM2 development either.
7. **Multi-asset from S1.** The skeleton already runs its three pilot assets
   through the scheduler as a fleet of three. Scale is exercised continuously
   (S6 raises it to hundreds), never bolted on.

## 4. Implementation Order

Each phase lists: what gets built, what to take care of, and the done-criteria
(evidence gates). A phase is closed by a written evidence summary in the KB.

### S0 - Foundations (the boring week that pays for everything)

Build:
- Immortal raw store: per-asset, append-only, file-partitioned by time period;
  atomic writes (salvage the existing atomic-replace pattern). No trim exists.
- Pilot ingestion is FILE/STREAM ONLY for now: CARE CSVs and simulator streams
  feed the immortal store directly. Historian backfill (the deployment-time
  capability: onboard = connect bundled historian + pull full available history;
  maturity computed from historian depth, not install date) is DEFERRED per
  directive (D16) - its interface slot is documented here so the store's
  append/backfill path is designed to accept it later without rework, but
  nothing is built for it now.
- Hardware probe + capability tier selection + resource governor skeleton
  (workers/thread-caps derived from probe; per-asset cost measurement hooks).
- Config spine: alpha (D1) and almost nothing else. ACM2's config philosophy is
  ONE dial plus structural constants; the ml_defaults sprawl is not recreated.
- Repo scaffolding per Section 6 (package, milestones, issue set, CI lanes).

Take care:
- Windows + Linux path/asyncio discipline from day one (the lab's compatibility
  lessons are inherited as standing rules, not relearned).
- BLAS/thread caps set at import-time in every entrypoint (the deadlock lesson).

Done when: raw store survives kill-mid-write; probe selects tiers correctly on
GPU and CPU machines; a fleet-of-three scheduler stub round-robins the pilots.

### S1 - Walking Skeleton (ACM2 exists)

Build:
- Ingestion (salvaged source-kind plumbing: csv/table/query/opcua/mqtt) ->
  immortal store -> placeholder scorer (existing six detectors, unchanged, D10)
  -> e-process decision layer (real, D12) -> six-verdict vocabulary with
  confidence and evidence trail -> minimal report page per asset + fleet-of-three
  matrix.
- Inside this phase, gating it: the exchangeability spike (D12) - empirical
  alpha-conformance on known-healthy CARE stretches. Days, not weeks.

Take care:
- The verdict contract (verdict word + confidence + evidence trail + attribution
  + coverage statement) is defined HERE, completely, even though most fields are
  thin. Every later phase enriches fields; none may change the contract.
- Do not gold-plate the placeholder scorer. It is scaffolding.

Done when: all three pilots run end-to-end continuously; on the clean pilot the
e-process layer produces zero alarms over the full replay (alpha conformance);
on the anomaly pilot evidence visibly accumulates and crosses; verdicts render.

### S2 - The Immune Harness (the referee)

Build:
- Injection framework: canonical fault signatures (drift, step, variance change,
  correlation break) injected into held-out healthy pilot data; per-scorer
  sensitivity profiles.
- Calibration conformance checks (score distributions on healthy holdout) and
  degeneracy checks (constant/dead scorer detection).
- Wired three ways: CI statistical-acceptance lane (Section 7), scheduled
  runtime self-test per asset, and phase-gate evidence generator.

Take care:
- The harness tests BEHAVIOR on data, not code paths. It must catch a silently
  dead scorer (the OMR class) by construction - that is its acceptance test.

Done when: the harness, pointed at the skeleton, produces a sensitivity profile
per detector per pilot; a deliberately-broken scorer (zeroed output) is flagged
automatically; the CI lane runs it on every merge to main.

### S3 - Lifetime Memory (the boiling frog dies here)

Build:
- Mergeable, condition/season-indexed summaries (quantile sketches, moments,
  covariance accumulators) with merge-tree telescoping; tails kept raw (top-k
  anomalous stretches verbatim per period).
- Recency-capped baseline composition (D2); episode-ledger scaffolding (windows
  masked out of baselines); amortized tick/rebuild split with staggered weekly
  rebuilds (D3).
- E-process calibration re-anchored from recent-window to lifetime baseline.

Take care:
- Mergeability is a hard invariant: nothing non-mergeable enters the memory.
- Bootstrap iteration (detect -> mask -> re-detect to convergence) on first
  full-history build.
- This phase DELETES: the 180-day trim concept, the train/score split, and the
  alarm-rule zoo's calibration inputs (quarry removal R1, R2, R4 begins).

Done when: rebuild from full history reproduces the same baseline as incremental
maintenance (derivability proof); injected slow drift on a pilot no longer
migrates into the baseline (the frog test - THE acceptance test of this phase);
S2 harness green.

### S4 - Surprise Substrate (early-detection power arrives)

Build:
- Per-channel probabilistic prediction (Tier 0/1 models), producing NLL/CRPS/PIT
  streams; PIT-uniformity monitoring wired into the immune path (the free
  self-test).
- E-process bank re-based onto surprise streams as the primary evidence;
  legacy detectors demoted to auxiliary scorers under the same wrapper.
- Attribution from per-channel surprise (which channels carry the evidence).
- Availability/standstill evidence stream (the surviving JOB of the old R4 rule):
  standstill and outage patterns detected from status/telemetry and fed into the
  e-process bank as their own evidence stream, distinct from score magnitude.

Take care:
- PIT distortion must be classified (global+immediate = model sickness;
  channel-local+drifting = fault) - this classification IS the immune/detection
  boundary and gets its own injection tests.
- Kurt/skew-style noise features are simply never generated (R10 honored by
  absence).

Done when: on CARE design-time evidence, surprise-based detection matches or
beats the detector ensemble it demotes, with earlier evidence accumulation on
developing-fault events; PIT self-test catches an injected miscalibration.

### S5 - Novelty Engine + Episode Ledger (corroboration)

Build:
- Streaming matrix profile (left-discords) over the surprise stream (D13);
  novelty-vs-recurrence gate; drift-vs-step shape discrimination
  (change-not-fault verdict goes live).
- Episode ledger completed: episodes open/close from e-process crossings,
  signatures stored, nearest-past-episode matching with confidence %; ledger
  windows feed S3 masking.

Take care:
- Recurrence whitelists only never-alarmed patterns (a recurring fault stays a
  fault).
- Intervention auto-detection (downtime + step toward lifetime envelope) lands
  here as epoch boundaries; the UI maintenance indicator remains a designed slot,
  deferred.
- This phase DELETES: the self-distrust gate concept from the quarry (R6) - its
  job is now done properly.

Done when: on CARE replays, known setpoint-like changes classify as
change-not-fault, known faults as novel; contamination injected into a pilot's
history is caught by the mask-and-rebuild loop; S2 harness green.

### S6 - Fleet Scale-Out + UI (1 to 1000)

Build:
- Scheduler and resource governor to full strength: staggered rebuilds, measured
  per-asset budgets, tier-aware concurrency; fleet of hundreds exercised with
  simulator-generated assets.
- Fleet UI: verdict-first matrix with aggregation (counts by verdict,
  worst-first), lazy drill-down to the full evidence trail per asset; tier and
  confidence visible; report flow at fleet level.

Take care:
- Salvaged UI rendering lessons are requirements: fragment batching, lazy detail
  rows, data-equality debounce, no per-row queries.
- The fleet view is the ONLY view; one asset is a fleet of one.

Done when: 500 simulated assets tick within budget on a Tier 0 machine with flat
memory; UI renders the 500-asset matrix inside the lab's established latency
budgets; a single asset's page shows the complete verdict contract.

### S7 - World Model Tier (Tier 2 power)

Build:
- Spike first (time-boxed): foundation-prior adaptation quality on pilot assets
  vs the S4 modest models - go/no-go memo.
- On go: transformer-class world model (D6) with foundation-prior initialization
  (D7); tier ladder activation (probe already selects it); adaptation scheduled
  in rebuild windows.

Take care:
- The guarantee never depends on this phase (validity is tier-free); if the
  spike says no-go, S7 closes with the memo and Tier 2 waits for better priors -
  the system remains complete at Tier 0/1.

Done when: Tier 2 beats Tier 0/1 on the S2 harness and CARE evidence (earlier
accumulation on developing faults, same alpha conformance), and tier
upgrade/downgrade transitions preserve verdict continuity on a live pilot.

### S8 - Prognostics + Dynamics Drift (the horizon)

Build:
- Health index from accumulated evidence -> gamma/Wiener degradation-process
  model -> failure-time distributions with credible intervals; self-gating
  exposure (D8) on the escalating verdict.
- Dynamics-drift channel (spike first, research-grade): periodic
  re-identification, operator/parameter drift tracking as the slow-creep
  evidence stream feeding the same e-process bank.

Take care:
- Never show an uncalibrated horizon (D8 is absolute).
- Koopman-flavored drift is the last-added channel and never a dependency.

Done when: on CARE developing-fault events, the escalating verdict carries a
calibrated time-to-threshold that covers the true label window within its
credible interval; drift-channel spike memo written either way.

### Amendment (2026-07-04): placement of gem components C6-C10

The gem plan's assumption audit (gem plan Section 10) added five components.
They slot into the existing S-order without extending the critical path:

- **C10 health narrative**: the verdict contract defined at S1 IS the narrative
  contract from day one (falsifiability statement + model-epoch stamp are
  fields, thin at first); full rendering matures with the S6 UI.
- **C9 multi-horizon + two-sided band**: joins S4 - multi-horizon quantile
  models are Tier 0 capable; the horizon-calibration-gap statistic and the
  too-predictable exit of the band are S4 evidence streams with their own
  injection tests.
- **C7 transient fingerprinting**: joins S5 - it shares the lifetime-catalogue
  machinery (align/catalogue over immortal history; classical, Tier 0 capable).
  Flagged as the likely highest value-per-effort addition in the plan; its
  done-criterion: on CARE developing-fault events, transient-response drift
  accumulates evidence before steady-state surprise does.
- **C6 learned anatomy**: classical form (sparse conditional-dependence graph,
  stability-selected; organ communities; per-organ aggregation) joins S5;
  attention-based form and full propagation/root-cause tracking deepen at S7.
- **C8 counterfactual rehearsal**: requires the world model - lands at S7 and
  upgrades the S2 immune harness from four canonical injections to the dense
  rehearsed manifold; the measured sensitivity floor enters the verdict
  contract then.

## 5. Salvage Inventory

**Lab equipment (kept, actively used, never "the product"):**
CARE datasets + care_benchmark harness; public-dataset adapters +
public_dataset_benchmark; synthetic fault generators; the sim/ package and
Simulate flow (S6's fleet-scale fuel); tests as patterns; CI pipeline; the
knowledge base (CLAUDE.md) and its standing rules (ASCII, README-sync,
issue-first, flag-architecture-violations).

**Quarry (EXPANDED 2026-07-04 under agent economics - see Section 10):** with
agents writing all code, adaptation cost is near zero, so the salvage filter is
no longer effort - it is ONLY the never-built list. Anything that passes that
filter and accelerates a phase gets copied and refactored to the new interfaces.
The mined-harder inventory:

- Source-kind ingestion dispatch + both bridges (OPC UA asyncio, MQTT thread,
  SQLite buffer pattern) - wholesale, S1.
- Store abstraction (sqlite/mssql, qmark discipline, migration pattern) -
  wholesale, S1.
- The ENTIRE sim/ package (11 generators, replay engine, multi-replay,
  BufferPublisher, SimAdapter) - wholesale; it is the fleet-scale test fuel for
  S6 and the live pilot stream for S1.
- Detector implementations incl. their hard-won fixes (GMM PCA+clip, OMR
  recalibration) - placeholder scorers S1 -> auxiliary S4 -> retired when they
  stop earning compute.
- fast_features polars pipeline - Tier 0 model inputs until S4 learns better.
- ScoreCalibrator's robust-calibration machinery - adapted (hard-clip semantics
  removed per R7) as the score-conditioning stage under the wrapper.
- Service shell: FastAPI app structure, asyncio tick scheduler, ProcessPool
  wiring with thread caps, UDP log fan-in, WebSocket log streaming - adapted at
  S1/S6.
- Report flow (acm_report HTML generation) - adapted to render the verdict
  contract/narrative.
- UI shell: themes, layout machinery, uPlot wiring, the fleet-matrix rendering
  optimizations - salvaged as the shell; the DATA layer is rewritten against
  the verdict contract (revises the earlier "not salvaged wholesale" stance -
  with agents, shell salvage + data-layer rewrite is cheaper than greenfield
  and keeps the proven rendering lessons as code, not prose).
- Test-suite patterns (false-alarm-resistance and fault-sensitivity synthetic
  tests) - templates for the S2 statistical harness.
- Installer patterns (resilient warn-don't-abort steps) - S6 packaging.

Deleted-when-superseded still applies; the never-built list below is untouched
and remains the only filter.

**Never built into ACM2 (rethink plan Section 8, honored by absence):**
The 180-day trim; the train/score split; per-tick full refit as sole mode;
max-anchored thresholds; the rule zoo (R4 availability's JOB survives - as a
standstill evidence stream into the e-process bank - the rule does not); the
self-distrust gate; the hard-clip-as-signal pattern; fusion auto-tune;
fused-scalar decisions; blind kurt/skew features; the unconditional substrate;
label-driven patching; the binary maturity gate.

## 6. Repository Posture and Source Control

**Repo posture (D9, re-revised 2026-07-04 by user directive):** the SAME ACM
repository. The new spine lives in a new top-level package `acm2/`; the old
pipeline code remains in-tree as quarry. Discipline that replaces physical
separation:

- **Import boundary as a CI check:** nothing under acm2/ may import the old
  pipeline modules at runtime. Salvage means COPY into acm2/ (with a commit
  message stating what was taken and why), never a live import. This recovers
  most of what a separate repo would have bought.
- **The never-built list is a PR review checklist item** (factory doc
  Section 5), enforced by the reviewer role on every merge.
- Old code is deleted when its replacement's phase closes (deletions are part
  of a phase's definition of done, recorded in the KB).
- The KB gains a distilled ACM2 agent contract in AGENTS.md (task S0.7);
  CLAUDE.md's lab history remains as the archive it already is.
- ACM2 declares its own dependency surface (acm2-scoped pyproject + uv
  lockfile, Section 7) rather than inheriting the lab's install scripts.

**Structure inside the repo:** acm2/ is a product monorepo package - engine
(the core as an importable library), service (thin shell), UI, harnesses -
with a standard src-layout and a single lockfile. Industrial on-prem
deployment wants a monolithic, versioned, installable artifact - not
microservices. The engine/service split keeps the ML core embeddable and
testable without the service.

**Branching model:** trunk-based. `main` is always green (CI-enforced).
Short-lived feature branches, one per issue, named per existing convention;
merge to main fast-forward or merge-commit per current repo pattern; never
force-push, never skip hooks (existing standing rules). Long-lived divergence is
forbidden - a phase is many small merged branches, not one giant one.

**Issues and milestones:** issue-first rule continues unchanged. One GitHub
milestone per phase: `ACM2 S0 - Foundations` through `ACM2 S8 - Prognostics`.
Every task is an issue in a milestone with existing labels (`ml`, `data`,
`infra`, `test`, `ux` as appropriate). Phase-gate evidence summaries are posted
on the milestone-closing issue and mirrored into the KB.

**Tags and releases:** `v2.0.0-alpha.N` at each phase close (N = phase number),
with the evidence summary as release notes. `v2.0.0` when S6 closes (the system
is complete at Tier 0/1 and fleet-scale); S7/S8 land as `v2.x` minors. The old
`v0.x-acm` line ends; no more releases from the quarry.

**CI lanes:**
1. Fast lane (every push, every PR): unit tests + ASCII scan + skeleton smoke
   run on a tiny pilot slice.
2. Statistical acceptance lane (every merge to main): the S2 harness -
   injection sensitivity, alpha conformance on healthy holdout, degeneracy
   checks. A red statistical lane blocks exactly like a red unit test.
3. Evidence lane (manual/scheduled, phase gates): replays over lab datasets
   (CARE events, simulator-generated fleets) and fleet-scale runs. Results
   archived as phase evidence, gitignored data, summarized in the KB.

**Testing philosophy:** three kinds, all required - unit tests (code
correctness), statistical acceptance tests (behavior on data; the S2 harness),
and design-time evidence (CARE/public datasets; regression only, never tuning).
The lab's hard rule is inherited: a fix or feature that greens its own target
but reds the statistical lane is rejected, not negotiated.

**Configuration philosophy:** one dial (alpha) plus structural constants with
written derivations. There is no per-asset, per-site, or per-dataset tuning
surface, and no ml_defaults sprawl. Anything that looks like a tunable is either
derived from the asset's own data by the system or is a structural constant with
its rationale documented inline.

**Data and storage:** raw history file-partitioned per asset per period,
append-only, atomic writes; summaries/ledger/verdicts in the store layer (D14);
datasets and results stay gitignored; plan docs and KB committed.

**Documentation rules:** README-sync and KB-update standing rules apply to ACM2
from S0. Each phase updates the KB with what was built, the evidence summary,
and what was quarried (copied) or superseded.

## 7. Technology Stack (decided)

Chosen for industrial on-prem reality: Windows-heavy plants, air-gapped installs,
long support horizons, CPU-only as the common case. Every choice below is a
decision, with its revisit trigger stated.

| Concern | Decision | Rationale / revisit trigger |
|---|---|---|
| Language | Python 3.12+, single src-layout package, type-annotated throughout | The ML ecosystem gravity is decisive (torch, sklearn, numpy, stumpy). Performance-critical inner loops go through polars/numpy vectorization; compiled extensions only if profiling ever demands them. |
| Environment/build | uv-managed, pyproject-based, committed lockfile | Reproducible installs, fast resolution, one-command bootstrap; air-gapped bundle = wheels + lockfile. Replaces the lab's ad-hoc pip list. |
| Dataframes/transforms | polars primary, numpy for math kernels; pandas only at library boundaries that require it | Already proven in the lab (fast_features); float32 discipline carries over. |
| Telemetry lake | Parquet, partitioned per asset per period, append-only, atomic writes | The immortal raw store (S0). Small at SCADA cadence, columnar for selective reads. |
| Analytical queries | DuckDB over the parquet lake | Querying years of history, summaries, and evidence trails without loading frames into memory; zero-server, embeddable - fits air-gapped on-prem exactly. |
| Operational store | SQLite default, MSSQL optional (same qmark discipline as the lab) | Plants have MSSQL; SQLite for self-contained installs. Verdicts, ledger, episodes, config live here (D14). |
| Tier 0/1 surprise models | Gradient-boosted quantile regression (LightGBM-class), per channel | CPU-fast, robust to messy telemetry, native quantile objectives give predictive distributions without a GPU; strong baseline the world model must beat. |
| Tier 2 world model | PyTorch; patch-based transformer; Chronos-class foundation prior adaptation | D6/D7. Torch is where the priors live. Inference stays CPU-cheap; training/adaptation scheduled in rebuild windows on the probed GPU. |
| E-process / conformal layer | Bespoke, in-house, pure numpy | It is small mathematics with no adequate off-the-shelf library; it is the validity keystone, so it is owned code - property-tested (hypothesis) against the Ville bound and exchangeability invariants, heaviest-tested module in the codebase. |
| Novelty engine | STUMPY (matrix profile), streaming left-discord configuration over surprise streams | Mature, maintained, exact; D13 keeps the input low-dimensional. |
| Prognostics | Bespoke gamma/Wiener degradation models (scipy-backed) | Classical, small, well-documented mathematics; no heavyweight dependency justified. |
| Service | FastAPI + uvicorn; asyncio scheduler; ProcessPool workers with import-time BLAS thread caps | Proven shape in the lab; the discipline (caps, parent-only bridges, pickle-safe worker payloads) carries forward as standing rules. |
| UI | Zero-build vanilla JS + uPlot/canvas, rebuilt fresh against the verdict contract; no framework, no bundler | A build-chain-free UI is a genuine virtue for air-gapped industrial deployment (nothing to compile, nothing to fetch). The lab's rendering lessons are requirements; the lab's UI code is not salvaged wholesale - the verdict contract is the new API. Revisit only if interaction complexity outgrows vanilla (trigger: state management bugs, not aesthetics). |
| Testing | pytest + hypothesis (property tests for mergeability, e-process invariants); the three-lane CI of Section 6 | Statistical acceptance as a first-class CI lane is the defining discipline. |
| CI matrix | GitHub Actions, Windows + Linux both, on every push | Plants run Windows; the lab's Windows lessons (asyncio, paths, subprocess) become CI-enforced instead of remembered. |
| Logging/observability | structlog structured logging; every verdict self-describing (evidence trail embedded, not reconstructed) | An unattended system's logs are its testimony; verdicts must be auditable after the fact with nothing but the store. |
| Distribution | One-command installer (PowerShell + sh) built on uv; optional container image; documented air-gapped bundle (wheels + lockfile + datasets-on-disk) | The lab's installer philosophy (resilient, warn-don't-abort) survives; the mechanism is rebuilt on uv. |

## 8. Risk Register (engineering)

- **Exchangeability (D12)** - the one design-level trap; gated inside S1 before
  anything depends on the wrapper. Mitigation: block-based betting on
  conditioned residuals + empirical conformance as the gate.
- **Skeleton gold-plating** - the classic failure of walking-skeleton builds.
  Mitigation: S1's done-criteria are deliberately minimal; enrichment belongs to
  later phases by plan.
- **Placeholder overstay** - legacy detectors lingering past their usefulness.
  Mitigation: S4's done-criteria explicitly demote them; retirement is tracked
  as a deletion task.
- **Sketch/summary correctness bugs** - subtle, silent, foundational.
  Mitigation: S3's derivability proof (rebuild == incremental) is a hard gate;
  property-style tests on mergeability invariants in the fast lane.
- **Fleet-scale resource surprises** - per-asset costs vary wildly with channel
  count. Mitigation: measured budgets from S0 hooks; the governor admits assets
  by measured cost, not by count; S6's 500-asset gate on a Tier 0 machine.
- **Research-grade disappointment (prior, Koopman)** - contained by design:
  spikes with go/no-go memos; the system is complete without both (Tier 0/1 +
  S1-S6 is a full product).
- **Scope creep back toward the quarry** - old habits reasserting (a new
  threshold here, a special case there). Mitigation: the never-built list
  (Section 5) is a review checklist; anything resembling an entry needs the
  flag-architecture-violation treatment before merge.

## 9. What Gets Built First - the Literal First Moves

REVISED 2026-07-04: same-repo posture (D9) and the agent factory
(docs/acm2-factory.md) are live. The S0 work is filed as briefs on the Hermes
kanban board `acm2` (workdir = this repo), parent task t_179b14d2:

1. S0.1 Package skeleton: acm2/ src-layout + pyproject + uv lock + CI fast
   lane (Windows+Linux) - Claude Code.
2. S0.2 Immortal raw store, atomic append + kill-test - Claude Code
   (validity-critical foundation).
3. S0.3 Pilot data ingestion (CARE CSVs + simulator stream) into the raw
   store - Codex-grade; historian backfill deferred (D16).
4. S0.4 Hardware probe + tier selection + governor stub - Codex-grade.
5. S0.5 Config spine: alpha + structural-constants registry - local-coder,
   reviewed up-chain.
6. S0.6 Fleet-of-three scheduler stub on a timer - Codex-grade.
7. S0.7 Distilled agent contract in AGENTS.md + KB pointers - kb-curator.

The GitHub milestone/issue mirror of these briefs is created when the first
code lands (issue-first rule satisfied by the board briefs; GitHub issues
remain the public record for merges).

Then S1 opens, and ACM2 exists by the end of it.

Then S1 opens, and ACM2 exists by the end of it.

## 10. Agent-Native Development Model (2026-07-04)

No human writes code. The workforce is AI agents; the human is architect and
approver. This section is the re-questioned implementation guide under that
assumption - and the guiding observation is that agent-built software needs the
same philosophy as the product itself: verification-first, because the builders,
like the monitor, must never be trusted on self-report.

OPERATIONALIZED 2026-07-04: the concrete factory (task board, profiles,
endpoints, brief format, GPU calendar, bootstrap state) is documented in
docs/acm2-factory.md. This section is the model; that document is the floor
plan.

### 10.1 The workforce and its division of labor

- **Cloud frontier agents (Claude Code, Codex-class)** - the senior engineers:
  - Validity-critical modules: the e-process layer, memory-core invariants,
    calibration mathematics. These are frontier-agent-only, both authorship and
    review.
  - Architecture-critical integration: interface definitions, the verdict
    contract, cross-component refactors.
  - Review of every merge (see 10.3).
- **Codex/Claude worker sessions in parallel** - the implementation fleet:
  independent, well-briefed feature work (one issue = one brief = one branch),
  parallelized across components once interfaces are frozen.
- **Local agent (Hermes / qwopus-class, RTX 4060 box)** - the night shift and
  the triage desk:
  - Overnight evidence-lane runs (replays, fleet-scale tests) and result
    summarization into the KB.
  - First-pass review triage: lint-level findings, convention checks (ASCII,
    README-sync), test-fixture generation, log analysis.
  - KB housekeeping and documentation drift checks.
  - Explicitly NOT trusted with validity-critical math or merge authority -
    its outputs are inputs to frontier review, never a substitute for it.

### 10.2 Issues are agent briefs

The issue-first rule becomes issue-AS-BRIEF: every issue is written so a fresh
agent session can execute it with no other context:

- Goal and the plan-section pointer that motivates it.
- The interface contract it must satisfy (frozen, versioned).
- Machine-checkable acceptance criteria (the tests/gates that define done).
- An explicit out-of-scope list, including the relevant never-built entries
  inline - the filter travels with every brief.

Agents are stateless across sessions: anything not in the repo (plan docs,
distilled KB, per-package agent contracts) does not exist. The repo is the
shared memory of the workforce; keeping it current is not documentation
hygiene, it is the coordination mechanism.

### 10.3 Verification discipline (the management layer)

- **CI is the arbiter, not the author.** No agent self-certifies. The three
  lanes (fast, statistical, evidence) gate every merge; a red statistical lane
  blocks regardless of which agent wrote the code or how confident its summary
  reads.
- **Author != reviewer, always.** Cross-review between agent families (a
  Claude-authored PR is reviewed by Codex or vice versa; local-agent triage
  runs first on everything). No agent merges its own work.
- **Adversarial test authorship for validity-critical modules**: the property
  tests for the e-process layer and memory invariants are written by a
  DIFFERENT agent than the implementation, from the spec alone - the two must
  meet in the middle. This is the anti-self-grading rule that matters most.
- Small PRs, agent-attributed commits, full trails - the git history is also
  the audit log of which agent did what under which brief.

### 10.4 Phase parallelization (revised from strict sequence)

With a workforce that parallelizes freely, the S-order becomes a dependency
DAG rather than a strict sequence:

- S0 and the S1 interface freeze (verdict contract, component interfaces) are
  the only true serialization points.
- After the freeze: S1 skeleton wiring, S2 harness, and the S3 summary/memory
  core proceed in parallel by different agents (S2 gates S3's merge, not S3's
  start).
- S4+ components (surprise models, novelty engine, anatomy, transients) are
  parallel briefs against frozen interfaces, integrating in the planned order.
- The exchangeability spike remains the one gate nothing may pass in parallel:
  it must close before any component depends on the wrapper's guarantee.

### 10.5 The dev box (RTX 4060, Ryzen 5, 16GB RAM) - three hats, strict rules

The single local machine is simultaneously: (a) the local agent's host, (b) the
Tier 2-S reference hardware and experiment bench for ACM2's own small world
models, and (c) the evidence-lane runner. Rules to keep the hats from
colliding:

- **VRAM is single-tenant.** The local LLM and model-training experiments never
  run concurrently (8GB VRAM does not share); the scheduler owns the GPU
  calendar - agents by day, training/evidence by night, never both.
- **16GB RAM means evidence-lane workers <= 2 with BLAS thread caps** - the
  lab's ProcessPool OOM/deadlock lessons apply to this exact machine verbatim
  and are enforced in the runner, not remembered.
- This box IS the Tier 2-S reference target: if a small world model cannot
  train/adapt within its envelope, Tier 2-S does not claim it. The dev
  machine doubling as the minimum-GPU deployment target keeps the tier honest.

### 10.6 What changes nowhere

The guarantee culture is unchanged by who codes: alpha is still the only dial,
the statistical lane still blocks like a unit test, the never-built list is
still the filter, and the KB/README rules still bind - agents inherit the
standing rules as contract, not convention.

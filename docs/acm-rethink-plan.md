# ACM Rethink: Lifetime, Unsupervised, Single-Asset Condition Monitoring

> Design plan only. No code, no APIs, no file layout. This is the agreed conceptual
> architecture from the 2026-07-02 design discussion. Status: PROPOSED - not yet
> broken into issues or implemented.
>
> Companion document: docs/acm-gem-plan.md - the ground-up "gem" target
> architecture. This plan is the classical, buildable-now floor; the gem plan is
> the method ceiling each layer upgrades into. Same skeleton, two horizons.

---

## 1. Problem Statement

ACM today answers: "is the current window anomalous relative to this asset's recent
past?" The goal is a system that answers: "is this asset drifting, in
condition-adjusted terms, into states its entire life has never contained - and is
that drift building?"

Target properties, in priority order:

1. Fully unsupervised operation - no labels, no tuning, no human in any loop.
2. Single asset is the unit - no fleet dependency, ever. Every asset is an island.
3. Early detection - catch faults WHILE developing, not after they mature.
4. False-alarm rate as an explicit design input, not an emergent property.
5. The system continuously proves its own detection power to itself (no silent
   detector death like the OMR-pinned-at-zero incident).

## 2. Design Principles

- **P1 - Derivability, not statelessness.** Everything the system holds (baselines,
  summaries, episode ledger) is a cache derivable from raw history by re-running the
  algorithm. Nothing is an unreconstructable source of truth. This preserves the
  stateless philosophy; only the recompute schedule changes.
- **P2 - Corroboration on every verdict.** No judgment rests on a single statistic.
  Every decision pairs two independent evidence axes (novelty x recurrence,
  magnitude x trend, alarm x signature match). Every past ACM failure (contamination
  filter, distrust-gate v1, silent OMR) traces to a single-axis judgment.
- **P3 - Storage is free, compute is the budget.** At SCADA cadence, full raw history
  is tens of MB per asset-year. Keep ALL raw data forever. The design constraint is
  per-tick compute, solved by amortization, never by truncation.
- **P4 - Recency gets a bounded vote.** No matter how long a fault develops, recent
  data can never own more than a capped fraction of the definition of "normal"
  (the boiling-frog guard).
- **P5 - Humans are optional enrichment, never a dependency.** Confidence is shown as
  a percentage; nothing waits for confirmation. A future maintenance indicator in the
  UI feeds an input slot the system already has - it never gates behavior.
- **P6 - Declare the detectability floor.** Sub-cadence transients are out of scope by
  physics at 10-minute SCADA cadence. State it as a contract, not a surprise.

## 3. Architecture

The core is one coherent object: an immortal raw history, condition-indexed mergeable
summaries over it, an episode ledger partitioning it into healthy/unhealthy epochs,
and a conditional model defining the residual space everything operates in. All other
layers are consumers of that core.

### Layer 0 - Immortal raw history + amortized computation

- Raw telemetry retained forever (P3). The 180-day trailing window is abolished as a
  statistical device; it survives only as "the recent raw working set."
- Two compute paths:
  - **Per tick:** score new data against the STANDING baseline; fold new rows into
    the current period's summaries. Cost proportional to new data only.
  - **Rebuild (slow schedule or triggered):** reconstruct baseline from full history
    via summaries. Triggers: scheduled cadence, epoch change (intervention), or
    self-test failure. Cost proportional to life, paid rarely.
- Consequence: tick cost is constant as the asset ages; full-history correctness is
  preserved because rebuilds genuinely see everything.

### Layer 1 - Condition-indexed, mergeable summaries

- Every per-period summary MUST be mergeable (combinable across periods with
  preserved error guarantees): counts, sums, moments, min/max, covariance
  accumulators, quantile sketches (t-digest / KLL class). A stored median is not
  mergeable; nothing non-mergeable is allowed in the memory.
- Resolution telescopes by merging: hours -> days -> months. Any historical window's
  distribution is composable on demand without touching raw data.
- **Keep the tails raw.** Sketch the bulk of each period, but retain the top-k most
  anomalous stretches verbatim at full resolution. Recurrence questions are about
  past extremes; they must be answered from exact memory, not the blurriest part of
  a sketch.
- Summaries are indexed by operating condition (Layer 2 covariates) and calendar
  context (season), so lifetime comparisons compare like with like. Comparing this
  January to a 60%-summer lifetime average is a statistical error, not a detail.

### Layer 2 - Conditional normality (continuous covariates, NO discrete regimes)

- Firm verdict: conditioning on operating state is load-bearing and non-optional.
  Without it, the healthy envelope's width is dominated by load/ambient variation and
  early symptoms sit inside it. This is THE reason pre-failure symptoms are invisible
  to unconditional detectors.
- Equally firm: the previously-culled discrete-regime machinery stays dead. Cluster
  count is arbitrary, boundaries flap between refits, transitions belong to no
  regime, sparse regimes starve. The goal returns; the mechanism does not.
- Correct form: designate a small set of DRIVING covariates per asset (load, speed,
  ambient - the inputs that cause operation to vary) and model the remaining
  sensors' expected behavior as a smooth function of them. Detection operates on
  residuals from that conditional expectation. One continuous conditional model per
  asset; no clusters, no k, no boundaries.
- The same covariates are the indexing dimensions for Layer 1 summaries and Layer 8
  coverage-aware confidence.

### Layer 3 - Detector ensemble (largely retained)

- The existing detector stack (AR1, PCA-SPE/T2, IForest, GMM, OMR) survives
  conceptually, but operates in Layer 2's conditional-residual space instead of raw
  feature space, and is calibrated against the Layer 1 lifetime envelope instead of
  a sliding window.

### Layer 4 - Sequential evidence accumulation (replaces the alarm-rule zoo)

- The decision layer becomes sequential changepoint detection (CUSUM /
  Shiryaev-Roberts / Bayesian online changepoint detection class), which integrates
  evidence over time instead of requiring any single window to be extreme. This is
  provably minimum-delay detection of small persistent shifts under a false-alarm
  constraint (Wald/Lorden optimality).
- **Multi-timescale bank, not one accumulator.** Fault physics spans minutes (trips)
  to months (bearing wear). Run a small parallel bank of accumulators at staggered
  timescales, each with its own share of the false-alarm budget.
- The false-alarm budget becomes a design INPUT: average run length between false
  alarms (e.g. one per asset-year) is set directly. The pinned-at-0.9 threshold
  pathology stops existing because there is no per-window rate threshold to pin.
- Retires: R1 sustained, R2 24h rate, R3 per-head 7d as separate hand-built rules;
  their intents (persistence, density, per-head evidence) fall out of accumulation
  naturally.

### Layer 5 - Novelty vs. recurrence gate (contamination defense, single-asset)

- When evidence accumulates, ask the lifetime memory: is this pattern RECURRENT
  (seen in prior periods/years -> legitimate rare operation, absorb) or NOVEL and
  persistent (never seen -> candidate fault)?
- Recurrence is the single-asset substitute for peer comparison: legitimate rare
  operation recurs across an asset's life; faults appear once and grow.
- **Novelty needs shape, not just existence:**
  - Monotone drift that never stabilizes -> fault-like, escalate.
  - Step to a tight, stationary, internally-consistent new plateau -> change-like
    ("operating change detected, re-baseline proposed") - a different message, not
    an alarm. Without this, the first deliberate setpoint change after deployment is
    a permanent false alarm.
- Recurrence only whitelists patterns that never accumulated to an alarm episode - a
  recurring fault stays a fault (recognized via Layer 6, not re-discovered).
- Subsumes: the self-distrust gate's job (its timing+saturation heuristics are
  replaced by novelty/recurrence + confidence), and the rejected contamination-filter
  approach (recurrence IS the corroborating signal percentile-trimming lacked).

### Layer 6 - Episode ledger + fault-signature memory (derived cache)

- **The load-bearing reason this exists: baseline hygiene.** A lifetime healthy
  baseline is only healthy if unhealthy stretches are excluded. The episode ledger IS
  the healthy/unhealthy partition of history; Layer 1 baselines are built from
  history MINUS ledger windows. Lifetime memory is impossible without it.
- The ledger is system-generated (episodes the algorithm itself declared) and
  re-derivable by re-running over raw history (P1) - a cache, not new state.
- Signature matching comes free: when evidence accumulates, compare against past
  episodes' signatures (sensors involved, shape, timescale, outcome) and report
  match confidence as a percentage. "Resembles the June episode which took 11 days
  from this point to trip" - case-based reasoning on the asset's own history.
- No human validation anywhere. A future confirmed/spurious toggle is optional
  enrichment via the deferred maintenance indicator (P5).

### Layer 7 - Trend / prognostic layer

- Track the baseline LEVEL of accumulated evidence over weeks and test for monotone
  trend (nonparametric, Mann-Kendall class - no distributional assumptions, no
  labels). A healthy asset's evidence level is stationary; a degrading one's creeps.
- Layer 4 says "something changed"; Layer 7 says "and it has been building for five
  weeks." That is the honest version of detect-before-failure without pretending to
  do remaining-useful-life estimation.

### Layer 8 - Calibrated confidence and abstention

- Generalize the existing embryos, do not invent parallel mechanisms: the maturity
  gate (binary abstention) becomes graded confidence; the distrust gate's job moves
  to Layer 5; data-quality metrics stop being decorative and feed confidence.
- Confidence is continuous, attached to EVERY verdict, and assessed per operating
  condition, not per asset ("high-load behavior well known; low-temperature
  behavior seen twice").
- "Insufficient history to monitor this condition" is an explicit output, distinct
  from "healthy." Silence-as-health with no confidence attached is how unattended
  monitors lose trust.

### Layer 9 - Alarm semantics (graded vocabulary)

Verdicts, each carrying its evidence trail and confidence:

- **watch** - evidence accumulating, below decision threshold
- **alarm** - changepoint declared; attribution + matched signature attached
- **escalating** - trend layer confirms the drift is building
- **change-not-fault** - step-to-stable detected; re-baseline proposed
- (**sensor-suspect** - reserved slot; sensor-health layer is out of scope for now)

This graded vocabulary is what lets downstream automation choose between "log,"
"schedule inspection," and "act now" without a human.

### Cross-cutting - The immune system (label-free self-validation)

- Runs from Phase 1 onward; validates every other layer as it lands.
- Per asset, on schedule, automatically:
  - **Injected-fault sensitivity:** perturb held-out healthy data with canonical
    fault signatures (drift, step, variance change, correlation break) and confirm
    every detector responds. A detector with sensitivity ~0 (the OMR incident) is
    flagged the week it happens, not months later via a labelled benchmark.
  - **Calibration conformance:** calibrated scores on healthy holdout must follow
    their expected distribution; distortion is flagged before it becomes bad alarms.
  - **Degeneracy checks:** any detector whose output collapses to (near-)constant is
    flagged as dead.
- This is the answer to "the tests for OMR weren't good enough": continuous
  statistical tests on the asset's own data, not more unit tests on code.

## 4. Intervention handling (conceptual only - deferred)

- Automatic path (design now, build later): intervention signature = downtime
  followed by a coordinated step BACK TOWARD the lifetime healthy envelope.
  Degradation never moves that direction spontaneously; repairs do. Declare
  "probable intervention, re-anchoring" autonomously with confidence.
- The asset's life is a sequence of health epochs separated by interventions;
  re-anchoring after an intervention is the one governed occasion the baseline moves
  discontinuously.
- The future UI maintenance indicator resolves the ambiguous case (upgrade that moves
  the asset somewhere new, healthily). Design the input slot now; build the UI later.
  Never a dependency (P5).

## 5. Explicitly Out of Scope / Dropped

- **Sensor-health / instrument-fault disambiguation** - dropped per decision
  (2026-07-02). The Layer 9 sensor-suspect verdict is a reserved slot only.
- **Fleet / peer models** - permanently out. Every asset is an island.
- **Human validation loops** - never a dependency; optional enrichment only.
- **Remaining-useful-life estimation** - Layer 7 trend is the honest substitute.
- **Benchmark chasing** - CARE/public datasets remain design-time regression
  evidence, never runtime tuning targets.

## 6. What Survives From Current ACM

- Detector ensemble concepts and their hard-won fixes (GMM PCA pre-reduction +
  z-clip, OMR out-of-sample recalibration + kurt/skew exclusion).
- Feature engineering (fast_features), fusion's calibration machinery (recalibrated
  against lifetime envelopes).
- All plumbing: source kinds, SQLite buffer pattern, store, service, report flow,
  ablation wiring (--override), the immune-system-style test suite.
- The availability rule (R4) concept - standstill detection is a different domain
  than score magnitude and keeps its own path.

## 7. What Is Replaced or Retired

| Current | Fate |
|---|---|
| 180-day trailing window as the definition of history | Retired; becomes "recent raw working set" only |
| Re-fit everything from scratch every tick | Replaced by per-tick incremental + scheduled/triggered full rebuild (P1 makes this safe) |
| Alarm rule zoo (R1 sustained, R2 rate, R3 per-head) with SAFETY margins and 0.9 ceilings | Replaced by multi-timescale sequential accumulation with ARL budget |
| Self-distrust gate (timing + saturation heuristics) | Subsumed by novelty/recurrence gate + graded confidence |
| Unconditional normality over engineered features | Replaced by conditional-residual space (continuous covariates) |
| Binary MATURING/READY gate | Generalized into graded, per-condition confidence + abstention |
| Fusion auto-tune (currently a damped pull to uniform) | Decision subsumed: weights informed by immune-system sensitivity profiles (label-free), or retired in favor of accumulator-level evidence combination - decide in Phase 3 |

## 8. Removals - What Is Deleted Outright

Framing that makes this list coherent: every removal below is the same single idea -
THE WINDOW - wearing a different hat: as memory model, as training definition, as
decision scope, or as calibration reference. The rethink is, at its core, the removal
of that one idea. Existing code is not sacred; only the end goal is.

### 8.1 The window, in all four incarnations

- **R1 - The 180-day cache trim** (the trailing-window trim in the feed/cache layer).
  Deleted. Raw history becomes immortal; the trim survives only as "recent raw
  working set" sizing, never as the boundary of what the system may know.
- **R2 - The sliding train/score split** (train = the older slice of the recent
  window). Deleted. "Train" is defined by the lifetime healthy baseline (history
  minus episode-ledger windows); "score" is the newly arrived data. A developing
  fault can no longer migrate into its own training set.
- **R3 - Full re-fit every tick as the only compute mode.** Deleted as a mode of
  operation, retained as a capability (P1 derivability). Per-tick work is score +
  summary-fold; full rebuilds are scheduled or triggered events.
- **R4 - Training-max-anchored thresholds** (the `worst-recent-behavior x safety
  margin, clipped to a ceiling` pattern that recurs across every rule). Deleted.
  A threshold may never be a function of the same window it judges. Detection
  standards come from the accumulator bank's explicit false-alarm budget against
  the lifetime envelope.

### 8.2 The decision layer

- **R5 - The alarm-rule zoo**: R1 sustained-run, R2 24h rolling-rate, R3 per-head 7d
  rules, plus their scaffolding (the 1h persistence floor, the 1.5x safety
  multiplier, the 0.05-0.9 threshold clips, the 500-sample arming gates). Deleted
  wholesale, replaced by the multi-timescale sequential accumulator bank (Layer 4).
  Their intents - persistence, density, per-detector evidence - are not lost; they
  fall out of evidence accumulation naturally, with optimality guarantees instead of
  hand-tuned constants. The R4 availability rule is the ONE survivor (standstill is
  a different domain than score magnitude) and keeps its own path.
- **R6 - The self-distrust gate, entirely** - including its saturation heuristic,
  which reads the calibrator's own hard clip as if it were signal (one mechanism
  destroys magnitude information, another divines meaning from the destruction).
  The gate exists only because window-derived thresholds cannot be trusted; its
  timing and saturation checks are proxies for the real question - "is this pattern
  novel or recurrent?" - which Layer 5 answers directly from lifetime memory.

### 8.3 Calibration and fusion

- **R7 - The unconditional hard z-clip as an information destroyer.** Calibration
  must become heavy-tail-robust without truncating the extremes that anomaly
  detection lives on. Standing rule extracted from this incident: no mechanism may
  ever treat another mechanism's artifact as evidence.
- **R8 - Fusion auto-tuning (episode-separability path).** Deleted. Confirmed dead
  weight: with no labels it degrades to a damped pull toward uniform weights -
  intelligence theater. If detector weighting survives at all (Phase 3 decision),
  it is informed by the immune system's per-detector sensitivity profiles, which
  are label-free and per-asset.
- **R9 - The fused scalar as the sole decision input.** The 1-D projection of six
  detectors' evidence may exist for display, but decisions consume per-detector
  evidence streams in the accumulator bank. Information is combined at the
  evidence level, not destroyed at the score level.

### 8.4 Features and substrate

- **R10 - Blind kurtosis/skewness feature generation** (window-16 third/fourth
  moments whose estimator variance is enormous by construction). Removed at the
  source - from the generated feature set itself - not merely excluded inside one
  detector, which is where the current patch stops. Noise features poison every
  consumer, not just OMR.
- **R11 - The unconditional feature space as detection substrate.** Detectors move
  to Layer 2's conditional-residual space. Raw-space envelopes are hopelessly wide;
  this removal is what makes early symptoms visible at all.

### 8.5 Process principles

- **R12 - Label-driven patching as a development method.** The deploy-time system
  never has labels; therefore label-steered fixes produce a fossil record of
  benchmark-shaped special cases (the distrust gate's generations are the proof).
  Labelled datasets are demoted to design-time regression evidence, full stop.
  Runtime self-assessment comes from the immune system, which needs no labels.
- **R13 - The binary MATURING/READY gate.** Replaced by graded, per-condition
  confidence with an explicit abstention verdict (Layer 8).

### 8.6 Removal-to-replacement map

Nothing is removed without its job being reassigned:

| Removed | Job it was doing | Reassigned to |
|---|---|---|
| R1 cache trim | bound compute | Layer 0 amortization |
| R2 train/score split | define "normal" vs "now" | Lifetime baseline vs new data |
| R3 per-tick refit | adapt to change | Tick/rebuild split + P4 recency cap |
| R4 max-anchored thresholds | set detection standard | ARL false-alarm budget (Layer 4) |
| R5 rule zoo | persistence/density evidence | Multi-timescale accumulators (Layer 4) |
| R6 distrust gate | reject broken baselines | Novelty/recurrence gate (Layer 5) |
| R7 hard clip semantics | bound score influence | Robust calibration, tails preserved |
| R8 fusion auto-tune | weight detectors | Sensitivity-informed weights or retirement (Phase 3) |
| R9 fused-scalar decisions | combine evidence | Evidence-level combination (Layer 4) |
| R10 kurt/skew features | capture distribution shape | Dropped; conditional residuals carry the signal |
| R11 unconditional space | detection substrate | Conditional residuals (Layer 2) |
| R12 label-driven patching | find weaknesses | Immune system (cross-cutting) |
| R13 binary maturity gate | protect against thin data | Graded confidence + abstention (Layer 8) |

## 9. The Target ACM, End to End

What the whole system looks like when the plan is complete. Three compute paths over
one core, feeding one verdict engine.

```
                        SOURCES (unchanged plumbing)
              csv / table / query / opcua / mqtt bridges
                                |
                                v
              +---------------------------------------+
              |  IMMORTAL RAW HISTORY (per asset)      |
              |  full-resolution telemetry, forever    |
              +---------------------------------------+
                 |                |                 |
        FAST PATH (per tick)  SLOW PATH (rebuild)  IMMUNE PATH (weekly)
                 |                |                 |
                 v                v                 v
   1. New rows -> conditional   Rebuild from FULL   Inject canonical faults
      model -> RESIDUALS        history MINUS       into healthy holdout;
      (given covariates:        episode-ledger      check every detector
      load/speed/ambient)       windows:            responds (sensitivity
                 |              - conditional model profile); check score
   2. Detector ensemble         - lifetime envelope calibration conformance;
      scores residuals ->       - summaries verify  flag dead/degenerate
      calibrated per-detector   Recency capped (P4) detectors
      evidence streams          Bootstrap: iterate           |
                 |              detect->mask->      failures lower Layer-8
   3. Fold new rows into        re-detect           confidence and trigger
      mergeable summaries                |          a SLOW PATH rebuild
      (condition+season         triggered by:
      indexed); retain          schedule, epoch
      extreme stretches raw     change, immune-
                 |              path failure
                 v
   4. MULTI-TIMESCALE ACCUMULATOR BANK
      per-detector evidence accumulated at staggered
      timescales (minutes...months), each with its
      share of the explicit false-alarm budget (ARL)
                 |
                 v (accumulator crossing -> candidate episode)
   5. VERDICT ENGINE
      a. Novelty vs recurrence: consult lifetime memory -
         "seen before in any prior period?" recurrent -> absorb
      b. Shape: monotone drift (fault-like) vs
         step-to-stable (change-like -> re-baseline proposal)
      c. Signature match: compare against episode ledger,
         report match + expected progression + confidence %
      d. Attribution: which sensors/subsystems carry the evidence
                 |
                 v
   6. VERDICT (one of, always with confidence % + evidence trail):
      healthy | insufficient-history (abstention) | watch |
      alarm | escalating | change-not-fault
      [sensor-suspect: reserved slot, out of scope]
                 |
                 v
      Store -> UI / report flow (existing plumbing) ->
      episode ledger updated when episodes open/close ->
      ledger windows masked out of all future baselines
```

Narrative form:

- **The core** (center of everything): immortal raw history; condition- and
  season-indexed mergeable summaries with tails kept raw; the episode ledger
  partitioning life into healthy/unhealthy epochs; the conditional model defining
  residual space. Everything else consumes the core.
- **Fast path, every tick:** new data is scored against the STANDING baseline in
  conditional-residual space; per-detector evidence feeds the accumulator bank;
  summaries absorb the new rows. Cost is proportional to new data only, forever.
- **Slow path, scheduled or triggered:** the baseline, conditional model, and
  envelope are rebuilt from the entire life (minus ledger windows, recency capped).
  This is the ONLY occasion the definition of normal moves, and it moves under
  governance: not during accumulating evidence of degradation, discontinuously only
  at detected interventions (epoch boundaries).
- **Immune path, background:** the system proves its own detection power on
  schedule - injected-fault sensitivity per detector, calibration conformance,
  degeneracy checks. A failed check is itself a first-class event: confidence
  drops, a rebuild is triggered, and the failure is visible in the UI. This is how
  a silent-dead detector (the OMR incident) becomes a same-week finding with no
  labels and no humans.
- **The asset's lifecycle through this system:** onboarding starts at
  insufficient-history (graded abstention, not a binary gate); confidence grows
  per operating condition as coverage accumulates ("knows high-load well, has seen
  cold starts twice"); interventions close epochs and re-anchor; age keeps adding
  memory while the recency cap keeps any one period from owning the definition of
  health. A slowly developing fault meets a baseline anchored in years it cannot
  poison, accumulators that integrate its faint evidence at the right timescale,
  a novelty gate that has genuinely never seen it before, and a trend layer
  reporting that it is building - which is the early warning the whole design
  exists to produce.

What a verdict contains, always: the verdict word, confidence percent, the
per-detector evidence trail (which accumulators, at which timescales, since when),
attribution (which sensors/subsystems), novelty/recurrence finding, signature match
if any (with historical progression), and the operating-condition coverage statement.
Nothing is a bare number; everything is inspectable after the fact.

## 10. Phasing (dependency order)

Each phase gates on: (a) immune-system checks for what it built, (b) existing
synthetic test suite equivalents, (c) CARE A/B/C as design-time regression evidence
(no tuning against them), (d) no phase ships while a prior phase's validation is red.

- **Phase 0 - Immune system first.** Injected-fault sensitivity, calibration
  conformance, degeneracy checks against the CURRENT pipeline. Rationale: it
  validates every later phase as it lands, and would already have caught the OMR
  class of failure. Standalone value even if nothing else ships.
- **Phase 1 - Lifetime memory core.** Immortal raw retention, mergeable
  condition/season-indexed summaries, tails-kept-raw, amortized tick/rebuild split,
  recency cap (P4). The foundation everything else consumes.
- **Phase 2 - Conditional normality.** Covariate designation, smooth conditional
  model, residual space; detectors re-based onto it. Depends on Phase 1 indexing.
- **Phase 3 - Sequential decision layer.** Multi-timescale accumulator bank, ARL
  budget as config, retire the rule zoo. Depends on Phase 2 residuals for clean
  inputs. Decide fusion auto-tune's fate here.
- **Phase 4 - Novelty/recurrence gate + episode ledger.** Baseline masking (Layer 6
  hygiene), drift-vs-step shape discrimination, signature matching with confidence.
  Depends on Phases 1 (extremes memory) and 3 (episodes to ledger).
- **Phase 5 - Trend, confidence, semantics.** Mann-Kendall-class trend on evidence
  level, graded per-condition confidence, the five-verdict vocabulary. Intervention
  auto-detection (conceptual slot from section 4) lands here or later.

## 11. Open Decisions - RESOLVED

> All six decisions below are RESOLVED as of 2026-07-02. Authoritative answers and
> rationale: docs/acm-implementation-plan.md Section 2. Summary: (1) ARL/alpha =
> one false alarm per asset-year; (2) recency cap = 20% maximum weight for the
> recent window; (3) rebuilds weekly scheduled plus event-triggered; (4) covariate
> designation superseded by learned conditioning (gem Component 1); (5) fusion
> auto-tune retired outright; (6) migration posture superseded entirely - this is
> a greenfield build with no fallback (see implementation plan). The list below is
> retained as the historical record of what was open.

1. ARL default: what false-alarm budget per asset (e.g. one per asset-year)?
2. Recency cap value (P4): what fraction of "normal" may the recent window own?
3. Rebuild cadence and triggers: weekly? monthly? event-driven only?
4. Covariate designation: auto-detected per asset (mutual-information style
   screening) vs. declared per asset class in config?
5. Fusion auto-tune: repair (sensitivity-informed weights) or retire (accumulator
   bank replaces fusion-level weighting)?
6. Migration posture: parallel-run new decision layer alongside the old rule zoo for
   a period, or hard cutover per phase?

## 12. Risks

- **Scope**: this is a re-architecture, not a fix series. Phases are designed to be
  independently shippable to contain this.
- **Conditional model quality**: if driving covariates are chosen badly, residual
  space is no better than raw space. Phase 2 needs its own validation gate
  (residual-space envelope must be measurably tighter than raw-space).
- **Sequential-layer calibration**: ARL guarantees assume roughly-known noise
  behavior of the evidence stream; heavy-tailed residuals need robustification.
  Phase 3's immune-system checks must include ARL-conformance on healthy data.
- **Episode ledger bootstrapping**: on first full-history run there is no ledger yet;
  first rebuild must iterate (detect -> mask -> re-detect) to convergence.
- **Known blind spot carried forward**: genuinely inseparable events (no signal in
  any measured channel at this cadence) remain undetectable by design - P6 declares
  this rather than chasing it.

# ACM Gem Plan: The Ground-Up Target Architecture

> Design plan only. No code, no APIs, no file layout. This is the from-first-principles
> "gem" architecture from the 2026-07-02 design discussion - designed as if nothing
> existed, optimizing purely for the stated goals. It is a SEPARATE plan from
> docs/acm-rethink-plan.md: that document is the classical, buildable-now floor;
> this document is the target ceiling. Section 9 defines how the two relate.
> Build guide: docs/acm2-implementation-plan.md (adopted 2026-07-02) - all open
> decisions resolved there; hardware adaptation and multi-asset scale folded in.
> Status: ADOPTED as the design basis for the ACM2 build.

---

## 1. The Problem in Its Purest Form

One machine. One multivariate telemetry stream. No labels, no peers, unbounded
lifetime. Required output: early, trustworthy warning of developing faults, with a
false-alarm rate that can be promised in advance, from a system that can prove to
itself that it still works - with zero human intervention.

Goals, restated as hard requirements:

1. Fully unsupervised: no labels, no tuning, no human in any loop.
2. Every asset is an island: no fleet data at runtime, ever.
3. Detect faults WHILE developing - before failure, not after maturity.
4. False-alarm rate is a design input with a guarantee, not a tuning outcome.
5. The system continuously proves its own detection power (no silent detector death).
6. Entire life of the asset is usable; compute stays bounded as life grows.
7. Multi-asset by construction: the platform runs 1 to 1000+ assets concurrently.
   Each asset remains an island analytically; the scheduler, storage, and UI scale
   and adapt to fleet size without reconfiguration.
8. Hardware-adaptive: the system probes available compute (GPU/CPU/memory) and
   selects its own capability tier. Verdict semantics are identical across tiers;
   only detection power differs. No hardware decision is delegated to the user.

## 2. The Central Design Insight

**Separate validity from power. Never let one component provide both.**

- POWER - sensitivity, earliness, seeing faint symptoms - comes from the strongest
  model that can be learned from the asset's own life.
- VALIDITY - the guarantee that false alarms stay within budget - comes from
  machinery that is assumption-free and label-free by construction, wrapped around
  the model, and indifferent to whether the model is any good.

Every classical failure mode (including all of legacy ACM's) traces to violating
this separation: thresholds derived from the data they judge were asked to provide
both power and validity from the same window, and delivered neither.

The load-bearing consequence of the split: **a bad model costs power, never
validity.** If the learned model degrades, detection gets less sensitive - but the
false-alarm guarantee holds unconditionally. Trust is unconditional; sensitivity is
best-effort. That asymmetry is exactly what unattended operation requires, and no
threshold-based scheme can offer it.

## 3. Architecture - Ten Components

Components 1-5 are the foundational design (2026-07-02). Components 6-10 come from
the assumption audit of 2026-07-04 (Section 10), which re-questioned every premise
of the original five. The audit's governing rule: every new capability is a POWER
addition feeding the same guaranteed decision layer - validity (Component 3) is
never touched, which is exactly what makes this freedom safe.

### Component 1 - A learned world model of the asset (the power source)

Do not model features; model the MACHINE. A probabilistic sequence model
(transformer-class or modern state-space class) trained on the asset's own
telemetry, predicting each channel's DISTRIBUTION ahead, conditioned on everything:
history, other channels, operating inputs.

- Health becomes one universal quantity: SURPRISE - how improbable is what the
  machine just did, under its own learned dynamics?
- Conditioning is LEARNED, not designated. The load/ambient/regime dependence that
  makes raw envelopes uselessly wide is absorbed automatically. No covariate
  designation, no functional form, no per-asset-class configuration.
- Cold start on an island is solved by a **time-series foundation model prior**
  (Chronos/TimesFM/Moirai class): pretrained on planetary-scale telemetry, adapted
  to this asset with weeks - not years - of its own healthy data. The fleet exists
  only inside the pretrained prior; no peer data ever touches the runtime. This is
  the legitimate reconciliation of "every asset is an island" with the cold-start
  problem.

### Component 2 - Surprise as the self-calibrating health signal

Proper probabilistic scoring over the world model's predictions: predictive
log-likelihood, CRPS, and above all PIT (probability integral transform - where
each observation lands within its predicted distribution).

- On a healthy asset with a correct model, PIT values are uniform BY MATHEMATICAL
  NECESSITY. Detection = watching that uniformity break, per channel, in
  characteristic and attributable ways.
- **The immune system comes free.** Model miscalibration ALSO breaks PIT
  uniformity, in ways distinguishable from faults (global vs channel-local,
  immediate vs drifting). The same statistic that detects faults continuously
  validates the detector. The silent-dead-detector class of failure (the OMR
  incident) is structurally impossible: a dead model announces itself in its own
  output distribution.

### Component 3 - Anytime-valid detection: conformal martingales / e-processes (the validity source)

The decision layer is game-theoretic sequential testing - conformal test
martingales and e-processes (the modern successor to SPRT/CUSUM):

- Bet against the hypothesis "the data is still exchangeable with healthy
  behavior." Under genuine health, no betting strategy can grow wealth.
- Ville's inequality gives a GUARANTEED, distribution-free bound: the probability
  that the evidence process ever exceeds 1/alpha is at most alpha. Set alpha, and
  "at most one false alarm per asset-year" becomes a mathematical promise - with
  zero labels, zero distributional assumptions.
- Validity survives CONTINUOUS monitoring with optional stopping: the evidence may
  be inspected every tick, forever, and the guarantee never degrades (the thing
  classical p-value thresholding catastrophically fails at).
- Evidence accumulation, the "watch" verdict, and multi-timescale behavior fall out
  naturally: a martingale IS accumulated evidence. Run a small bank of betting
  strategies tuned to different drift rates (minutes to months), each funded from
  its share of the alpha budget.
- Pairing with Component 1 is the whole design: the conformal layer wraps ANY
  scorer. Model degrades -> less power, never more false alarms.

### Component 4 - The novelty engine: matrix profile against the entire life

The recurrence/novelty question ("has this machine ever done this before?") has an
exact algorithmic embodiment: the matrix profile family, specifically streaming
left-discord discovery (DAMP-class algorithms).

- For every new subsequence: distance to its nearest neighbor ANYWHERE in the
  asset's entire past, computed efficiently on unbounded history. High value =
  "this shape has never occurred in this machine's life."
- This is the corroborating second axis for every alarm (P2 of the rethink plan):
  the martingale says THE DISTRIBUTION SHIFTED; the matrix profile says AND THE
  SHAPE IS UNPRECEDENTED.
- Contamination defense, setpoint-change discrimination (a step to a recurring
  plateau has near neighbors; drift into virgin territory does not), and episode
  signature matching (nearest past episode, with its recorded progression) all come
  from the same structure - parameter-light, label-free, exact.

### Component 5 - The slow channel: watch the model itself, then true prognostics

Two mechanisms for the months-scale creep that residual monitoring sees last:

- **Dynamics drift (Koopman-flavored):** periodically re-identify the asset's
  dynamics and track the LEARNED OPERATOR itself over time - its parameters, its
  spectrum. A degrading machine's governing equations change slowly; eigenvalue
  migration of the identified dynamics is degradation made directly visible, often
  before residuals accumulate anything. Monitor what the machine forces you to
  learn about it.
- **Degradation-process prognostics:** once the components above yield a monotone
  health index, classical reliability theory (gamma-process / Wiener-process
  degradation models) converts its trajectory into a FAILURE-TIME DISTRIBUTION -
  "70% probability of crossing the critical level within 30 days" - with credible
  intervals, from the asset's own drift. This is the honest, mathematically
  grounded version of "detect faults before they come": not a black-box RUL guess,
  a stochastic-process extrapolation.

### Component 6 - Learned anatomy: the machine's structure, discovered (audit: A1)

The original design treated the asset as one flat multivariate blob. But a machine
is made of subsystems - drivetrain, pitch, generator, transformer, cooling - and
its channels have a functional anatomy. That anatomy is LEARNABLE from healthy
data: which channels predict which, which move together, which drive and which
follow. Learn a sparse channel-interaction graph (classical sparse conditional-
dependence estimation at Tier 0; learned attention structure at Tier 2); its
communities are the machine's ORGANS, discovered without a single engineering
drawing.

What this buys, concretely:

- **Per-organ health.** Surprise and evidence are aggregated per organ, not just
  per channel or per asset. "The pitch subsystem is degrading" is a different
  product than "channel 412 is anomalous."
- **Root-cause localization from propagation.** When evidence accumulates, track
  its spread ACROSS the graph over time. The origin organ - earliest, most
  upstream in the learned dependency structure - is the root-cause candidate;
  everything downstream is symptom. The verdict becomes anatomical: "originating
  in pitch, propagating into drivetrain loads, generator unaffected."
- **Structural drift as its own evidence stream.** The graph itself is
  re-identified at each rebuild; edges appearing, vanishing, or reweighting are
  degradation made structural (a coupling that was never there = a new physical
  pathway = wear). This feeds the e-process bank like any other stream.

### Component 7 - Natural-experiment mining: the machine tests itself daily (audit: A3)

The original design observed the asset passively, implicitly privileging steady
state. But an industrial asset performs EXPERIMENTS on itself constantly: every
start-up is a step-response test, every shutdown a free-decay test, every load
ramp a frequency sweep, every ambient swing a boundary-condition study. These
transients excite dynamics that steady state never reveals - and degradation
appears in transient response (rise times, overshoot, settling behavior, ring-
down) long before it appears in steady operation.

The immortal history makes the marvel possible: CATALOGUE every recurring
transient across the asset's entire life, align them (classical elastic
alignment - Tier 0 capable), and compare each new transient against the lifetime
family of its siblings. The 400th start-up, laid over the previous 399, is an
exquisitely sensitive degradation instrument - fully unsupervised, single-asset,
and needing no new sensors.

- Feeds the e-process bank as its own evidence stream (transient-response drift).
- Softens the cadence ceiling honestly: transients carry higher effective
  information bandwidth than steady state at the same sampling rate.
- Assets that rarely stop still ramp: load transitions are the probe family of
  last resort.

### Component 8 - Counterfactual fault rehearsal: the dreaming immune system (audit: A4)

The original immune system injected four canonical fault signatures. The audit
found this the weakest link: four hand-picked shapes cannot map a detection
boundary. But a world model that has learned the machine's healthy dynamics can
IMAGINE the machine degraded: perturb its learned dynamics in physically coherent
directions - slowed responses, growing cross-couplings, efficiency loss, widening
hysteresis - and generate the telemetry those degradations would produce. The
immune system then rehearses detection against this DENSE, self-generated fault
space, continuously, per asset.

What this buys is the missing half of the accuracy story:

- **A measured sensitivity floor.** False alarms are bounded by mathematics
  (Ville, Component 3). Missed detections can never be bounded by mathematics
  (unknowable without labels) - but rehearsal produces the strongest possible
  substitute: a measured detection rate over a dense manifold of plausible
  faults, per asset, per tier, refreshed at every rebuild. The system reports
  BOTH sides: "false alarms <= alpha, guaranteed; detection >= X% over the
  rehearsed fault space, measured."
- **A sensitivity MAP, not a number**: which fault directions, at which
  magnitudes, at which timescales this asset's current model can and cannot see
  - feeding the confidence layer (Component/Layer 8) and the honest
  detectability contract.
- The unknown-unknown residue (faults outside anything imaginable) remains
  covered by the novelty engine (Component 4) - the catch-all that needs no
  fault model at all.

### Component 9 - Multi-horizon surprise and two-sided predictability (audit: A2)

The original design scored one-step-ahead surprise. Two flaws found:

- **A slowly tracking model hides slow drift.** One-step prediction stays good
  while the machine decays, because each step is conditioned on the recent
  (already degraded) past. Predict at MULTIPLE horizons simultaneously - minutes,
  hours, a day ahead. Slow degradation appears at long horizons FIRST: the
  long-horizon prediction is anchored in what the machine used to be, the
  short-horizon one in what it is becoming. The gap between horizon-calibrations
  is itself an early-warning statistic.
- **Pathology is two-sided.** Surprise detects the machine becoming LESS
  predictable. But a machine becoming TOO predictable is equally sick: a stuck
  sensor, a derated turbine, a control loop no longer regulating (variance
  collapse). Health is a BAND of predictability at every horizon, not a floor.
  Both exits from the band are evidence.

Multi-horizon quantile models are Tier 0 capable; the world model does this
natively at Tier 2.

### Component 10 - The health narrative: the system explains itself (audit: A6)

The original design emitted point-in-time verdicts. An unattended system needs to
be an ACCOUNTABLE WITNESS, not a dashboard: for each asset it maintains a
continuously updated narrative - what it currently believes, on what evidence,
what changed since yesterday, what it expects next, and - explicitly - WHAT
EVIDENCE WOULD CHANGE ITS MIND (a falsifiability statement attached to every
verdict: "this alarm downgrades if transient response renormalizes over the next
N starts").

- Every claim in the narrative is a pointer into stored evidence - nothing is
  prose without provenance.
- Every verdict is stamped with the model epoch that produced it, so any
  historical statement is auditable to the exact model, data, and tier that made
  it (the missing model-provenance piece the audit surfaced).
- The narrative is the natural rendering surface for operators and for any
  downstream automation; it is generated FROM the evidence structure, never the
  other way around.

## 4. The Target System, End to End

```
                     SOURCES (any transport)
                            |
                            v
          +------------------------------------+
          |  IMMORTAL RAW HISTORY (per asset)   |
          +------------------------------------+
             |                |               |
        FAST PATH        SLOW PATH        IMMUNE PATH
        (per tick)       (amortized)      (continuous, free)
             |                |               |
   1. World model        Re-adapt world   PIT uniformity per
      predicts each      model on         channel: distortion
      channel's          history minus    = fault OR sick
      distribution       episode ledger   model, and the two
             |           windows;         are distinguishable;
   2. Observations ->    foundation prior + injected-fault
      SURPRISE stream    + recency-capped sensitivity checks
      (NLL / CRPS /      adaptation       on schedule
      PIT per channel)        |               |
             |           Re-identify      failures cut
   3. E-PROCESS BANK     dynamics ->      confidence, trigger
      bets against       operator drift   slow path, and are
      "still healthy     tracking         first-class events
      /exchangeable"     (Component 5)
      at staggered
      drift rates;
      Ville: false-alarm
      rate <= alpha,
      guaranteed
             |
             v  (evidence crosses 1/alpha -> candidate episode)
   4. CORROBORATION
      a. Matrix profile vs entire life: unprecedented shape?
         (recurrent -> absorb; step-to-known-plateau ->
         change-not-fault; virgin drift -> fault-like)
      b. Nearest past episode -> signature match + recorded
         progression + confidence %
      c. Attribution: which channels' PIT/surprise carry it
             |
             v
   5. HEALTH INDEX -> degradation-process model ->
      failure-time distribution with credible intervals
             |
             v
   6. VERDICT (always with confidence % + evidence trail):
      healthy | insufficient-history | watch | alarm |
      escalating (+ time-to-threshold distribution) |
      change-not-fault
```

- **Fast path** cost is proportional to new data only: one forward pass, scoring,
  betting updates, matrix-profile append.
- **Slow path** is the only occasion the definition of health moves: re-adaptation
  on full history minus ledger windows, recency-capped, epoch-aware
  (interventions), never during accumulating evidence of degradation.
- **Immune path** is not a separate subsystem here - it is Component 2's PIT
  calibration read continuously, plus scheduled injected-fault sensitivity checks.
  Self-validation is inherent, not bolted on.

Where Components 6-10 enter this same picture (no new spine - new evidence
streams and richer outputs on the existing one):

- C6 anatomy: a structure layer over steps 1-2 (per-organ surprise aggregation),
  a propagation tracker inside step 4 (root-cause localization), and a
  structural-drift evidence stream into step 3.
- C7 transients: a catalogue/alignment process over the immortal history whose
  transient-response-drift statistic is one more evidence stream into step 3.
- C8 rehearsal: lives in the immune path; its output (the sensitivity map and
  floor) feeds the confidence layer and the verdict contract.
- C9 multi-horizon: widens steps 1-2 (predictions at several horizons, band
  monitoring two-sided); each horizon's calibration is its own evidence stream.
- C10 narrative: wraps step 6 - the verdict contract becomes a continuously
  maintained, evidence-pointed, falsifiable account per asset, stamped with the
  model epoch that produced it.

The load-bearing invariant: every one of these is POWER (new evidence streams,
better attribution, honest self-knowledge). VALIDITY - the alpha guarantee in
step 3 - is architecturally untouched by all five. Marvels are safe to add
precisely because they cannot corrupt trust.

## 5. Goal-by-Goal Verification

| Stated goal | Answered by |
|---|---|
| Unsupervised, zero human | Every component label-free; foundation prior removes even the wait-for-maturity dependence |
| Every asset an island | Runtime uses only the asset's data; the fleet exists only as a pretrained prior |
| Catch faults while developing | Learned conditioning (C1) makes faint symptoms visible; e-processes (C3) accumulate faint evidence optimally; dynamics drift (C5) catches what residuals miss |
| False alarms controlled, no tuning | Ville's inequality - a guarantee, not a hope; alpha is the only dial |
| System proves its own health | PIT uniformity is a continuous free self-test; injection testing on top |
| Entire history, bounded compute | Streaming matrix profile on unbounded history; amortized model adaptation; surprise/PIT streams are tiny |
| Earliest possible warning | Multi-horizon calibration gap (C9) + transient fingerprinting (C7) see drift before steady-state symptoms exist |
| Root cause, not just detection | Learned anatomy + propagation tracking (C6): origin organ vs downstream symptoms |
| Missed-detection assurance (the "impossible" side) | Counterfactual rehearsal (C8): a measured sensitivity floor and map over a dense self-generated fault space - the strongest label-free substitute for a recall guarantee that can exist |
| Accountability of an unattended system | The health narrative (C10): every verdict evidence-pointed, model-stamped, and falsifiable |

## 6. Honest Caveats (expert risk register)

- **Deep models are the power source AND the risk source.** Training instability,
  silent overfitting, data appetite on a young asset. The architecture CONTAINS all
  of it by construction: the conformal layer's guarantee holds regardless of model
  quality, and PIT monitoring exposes model sickness. This containment is the only
  reason a neural model belongs in an unattended plant system.
- **The cadence ceiling is physics.** Nothing detects what 10-minute averages do
  not contain. The gem SYSTEM includes a data recommendation: for bearing-class
  faults, the single highest-ROI change is higher-frequency vibration channels,
  which unlock the classical envelope-analysis/cyclostationarity literature as
  additional surprise inputs. Declare the detectability floor as a contract.
- **Foundation-model priors are new.** Zero-shot quality on industrial SCADA
  varies; the adaptation recipe (what to freeze, how much healthy data suffices)
  needs empirical validation per asset class. Fallback if the prior underperforms:
  train the world model from scratch on the asset (slower cold start, same
  architecture - the design does not depend on the prior, only benefits from it).
- **Exchangeability is the martingale's assumption.** Telemetry has serial
  dependence; conformal martingales for time series require care (blocking,
  de-trending via the world model's residuals - which are approximately
  exchangeable when the model is right). This is a known, solved-in-literature
  engineering point, but it is THE technical detail to get right in Component 3.
- **Koopman/operator-drift tracking is the most research-grade component.** Treat
  it as the last-added channel, not a dependency: Components 1-4 are complete
  without it; Component 5's prognostics only need a monotone health index, which
  Components 2-3 already produce.
- **Learned anatomy (C6) can hallucinate structure.** Dense correlation in SCADA
  data produces spurious edges; organ discovery must use stability selection
  (structure that survives resampling and re-fitting) before any edge is trusted
  for root-cause claims. Root-cause verdicts carry their own confidence, and
  propagation-based localization is corroboration for attribution, never a
  standalone proof.
- **Rehearsal (C8) maps only the imaginable.** The sensitivity floor is honest
  over the rehearsed fault manifold and silent beyond it; the novelty engine
  (C4) remains the catch-all for unknown unknowns, and the narrative must state
  the floor's scope, never imply totality.
- **Transient mining (C7) needs transients.** Base-load assets that never stop
  still ramp and still experience ambient swings - the probe family thins but
  never empties. Confidence per probe family reflects its population size.

## 7. Phasing

Ordered so that VALIDITY ships first and the guarantee is never absent:

- **Phase G0 - The conformal wrapper over any scorer.** Implement the e-process /
  conformal-martingale decision layer over existing anomaly scores (whatever
  scorer exists - even legacy detectors). From this day forward, false alarms are
  budgeted by alpha, not tuned. Highest value-to-risk ratio in the entire plan and
  independently shippable.
- **Phase G1 - Surprise substrate.** Probabilistic per-channel prediction +
  NLL/CRPS/PIT streams + continuous PIT-calibration monitoring (the free immune
  system). Start with a modest learned model; foundation prior optional here.
- **Phase G2 - The novelty engine.** Streaming matrix profile (left-discords)
  against the immortal history; wire as the corroboration axis and episode
  signature matcher.
- **Phase G3 - The world model proper.** Foundation-prior-initialized sequence
  model replacing/absorbing the modest G1 model; learned conditioning replaces any
  designated covariates.
- **Phase G4 - Prognostics.** Health index -> gamma/Wiener degradation model ->
  failure-time distributions on the escalating verdict. Ceiling upgrade: latent-
  trajectory (degradation-manifold) prognosis once the world model exists -
  extrapolate the PATH through learned state space, matched against the episode
  ledger, not just a scalar decay curve.
- **Phase G5 - Dynamics-drift channel.** Operator re-identification and drift
  tracking as the final slow-creep channel.

Placement of the audit components (they slot into the same sequence; none
extends the critical path):

- **C10 narrative**: the verdict contract from G0 day one; full rendering
  matures with the UI.
- **C9 multi-horizon**: joins G1 (multi-horizon quantile models are Tier 0
  capable); the horizon-gap statistic and two-sided band from the start.
- **C7 transients**: joins G2 (it shares the lifetime-catalogue machinery;
  classical alignment, Tier 0 capable). Likely the single highest
  value-per-effort addition in the whole plan.
- **C6 anatomy**: classical form (sparse conditional-dependence graph, organ
  communities, per-organ aggregation) alongside G2; learned/attention form and
  full propagation tracking deepen at G3.
- **C8 rehearsal**: requires the world model - lands with G3 and upgrades the
  immune system from four canonical injections to the dense rehearsed manifold;
  the sensitivity floor enters the verdict contract then.

Each phase gates on: injected-fault sensitivity for what it built, PIT/ARL
conformance on healthy holdout (the alpha guarantee must be empirically confirmed,
not just asserted), and labelled benchmarks as design-time regression evidence only
(never tuning targets).

## 8. Resolved Decisions

All previously-open decisions are resolved (2026-07-02, per the directive that the
system decides for itself and nothing is delegated). Full rationale lives in
docs/acm2-implementation-plan.md Section 2.

1. Alpha: one false alarm per asset-year, per asset, spent hierarchically across
   the e-process bank. Single exposed dial; sane default; never per-site tuned.
2. Foundation prior: adopted automatically when the hardware tier permits;
   from-scratch modest model is the automatic lower tier, not a user choice.
3. World model class: transformer-class (patch-based), chosen for compatibility
   with foundation-model priors and salvageability of the adaptation path.
4. Prognostic exposure: self-gating - failure-time distributions surface in the UI
   only after their own conformance check passes on the asset in question.
5. Hardware: no envelope decision exists. The system probes compute at startup and
   selects a capability tier (see goal 8); tiers degrade and upgrade gracefully at
   runtime. Monitoring never stops because hardware changed.

## 9. Relationship to the Rethink Plan (docs/acm-rethink-plan.md)

The two plans share one skeleton. The rethink plan's layer structure - lifetime
memory, conditional residuals, evidence accumulation, novelty gate, trend,
confidence, immune system - is EXACTLY right and is preserved here. What the gem
plan changes is the METHOD inside each layer:

| Layer (rethink plan) | Classical floor (rethink) | Gem ceiling (this plan) |
|---|---|---|
| Conditional normality | Designated covariates, smooth regression | Learned world model, foundation prior (C1) |
| Health signal | Detector z-scores, calibrated | Surprise: NLL/CRPS/PIT (C2) |
| Decision layer | CUSUM/BOCPD bank, ARL budget | Conformal martingales / e-processes, Ville guarantee (C3) |
| Novelty/recurrence gate | Summary-envelope heuristics | Streaming matrix profile, exact (C4) |
| Trend / prognostics | Mann-Kendall on evidence level | Operator drift + degradation-process failure-time distributions (C5) |
| Immune system | Scheduled injection + calibration checks | Inherent (PIT uniformity) + scheduled injection |

Sequencing posture: the classical floor is the right FIRST implementation -
simpler, inspectable, adequate - and nothing in it is wasted: every classical
component occupies the exact slot its gem successor upgrades into. The two plans
are one roadmap read at two horizons. If a single starting point must be chosen
across both plans, it is Phase G0: the conformal wrapper works over the CURRENT
pipeline's scores today, ships the false-alarm guarantee first, and makes every
later upgrade safe to attempt.

## 10. The Assumption Audit (2026-07-04)

Every premise of the original five-component design was re-questioned with
nothing sacred but the end goal. The full ledger, so no assumption is ever
silently load-bearing again:

| # | Assumption in the original design | Verdict | Consequence |
|---|---|---|---|
| A1 | The asset is one flat multivariate blob | BROKEN - machines have discoverable functional anatomy | Component 6: learned anatomy, per-organ health, propagation-based root cause |
| A2 | One-step-ahead surprise is the sufficient health signal | BROKEN twice - tracking models hide slow drift; pathology is two-sided (too-predictable is also sick) | Component 9: multi-horizon prediction, calibration-gap early warning, predictability BAND not floor |
| A3 | Detection is passive observation of whatever the asset happens to do | BROKEN - the asset performs natural experiments on itself daily (starts, stops, ramps) | Component 7: transient fingerprinting over the lifetime catalogue |
| A4 | Four canonical injected faults suffice for the immune system | BROKEN - four shapes cannot map a detection boundary | Component 8: counterfactual rehearsal over a dense self-generated fault manifold; measured sensitivity floor |
| A5 | Health index is a scalar; prognosis extrapolates a curve | REFINED - degradation is a path through state space | G4 ceiling upgrade: degradation-manifold prognosis matched against the episode ledger |
| A6 | Verdicts are point-in-time outputs | BROKEN - an unattended system must be an accountable witness | Component 10: the health narrative - evidence-pointed, model-stamped, falsifiable |
| A7 | Validity and power must be separated (Ville-guaranteed decision layer wrapping any scorer) | HOLDS - reaffirmed as the keystone | It is exactly what makes A1-A6's ambition safe: marvels add power; trust is architecturally untouchable |
| A8 | Every asset is an island; the fleet exists only as a pretrained prior | HOLDS (user constraint and good design) | Unchanged |
| A9 | Exchangeability handling is the design's one real technical trap | HOLDS | Still the gating spike before anything depends on the wrapper |
| A10 | Telemetry as given is the only input | RELAXED - modality-open by design | Any new sensor stream (vibration, acoustic, thermal) becomes another surprise stream feeding the same bank; no redesign needed |
| A11 | The cadence ceiling is untouchable physics | HOLDS as physics, SOFTENED in practice | C7: transients carry higher effective information bandwidth than steady state at the same cadence |
| A12 | Model provenance was implicit | GAP FOUND | Every verdict stamps the model epoch that produced it (folded into C10) |

The audit's meta-finding: the original design's one non-negotiable (A7) is what
made the rest negotiable. Because validity lives in an assumption-free wrapper,
every other assumption could be broken freely and the additions absorbed as
evidence streams - the architecture is EXTENSIBLE BY CONSTRUCTION, which is
itself the property that matters most over a decades-long industrial life.

## 11. One-Paragraph Verdict

The comprehensive solution is a learned probabilistic world model of the single
asset (foundation-prior-initialized, so the island is not cold) whose
multi-horizon surprise streams are the universal health signal, wrapped in an
anytime-valid conformal/e-process layer that converts surprise into alarms with
mathematically guaranteed false-alarm rates, corroborated by an exact novelty
engine over the asset's whole life - a machine whose functional anatomy the
system has discovered for itself, so alarms localize to an origin organ; whose
every start-up and ramp is mined as a self-administered experiment; whose immune
system rehearses detection nightly against faults the world model imagines, so
missed-detection risk carries a measured floor, not a shrug; whose prognosis
extrapolates the degradation path with credible intervals; and whose every
verdict is a falsifiable, evidence-pointed, model-stamped statement an auditor
can replay years later. Power from learning, validity from game-theoretic
statistics, memory from the immortal history, accountability from the narrative
- each goal answered by construction rather than by tuning, and the whole thing
extensible forever because trust and ambition live in different rooms.

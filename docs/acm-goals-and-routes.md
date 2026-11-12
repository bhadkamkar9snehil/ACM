# ACM: the goal, the constraints, and the routes to it

Written 2026-11-12. This document records what ACM has to be, as the
owner stated it, and evaluates the ways to build it. It supersedes the
earlier rethink and gem plans, which are now in `docs/archive/`. The
design that follows from this document is `acm-design.md`.

Status: the goal and constraints (sections 1 and 2) are fixed. The
routes in sections 4 to 9 were the options considered. The decision
is in `acm-design.md`.

## 1. The goal

ACM is a self-learning, unsupervised condition monitor for industrial
assets. For each asset, using only that asset's own telemetry, it keeps
answering four questions for the people who run the plant:

1. Can this data be trusted? Which sensors are stuck, missing,
   drifting or wrong.
2. Is the machine still behaving like itself, given how it is being
   operated right now?
3. If not: where, since when, how fast is it growing, and has this
   happened before?
4. How sure is ACM, and what can it not see yet?

It raises few advisories, at a false-advisory rate set in advance. It
does not fail silently.

## 2. Fixed constraints

These came from the owner. They are the goal, not design choices.

- **C1. No human in the loop.** Deployment, learning and operation do
  not depend on people. Nobody labels data, picks training periods,
  tunes thresholds, or confirms alarms. Operator feedback may be added
  later as extra input. It is not part of the core route.
- **C2. Cold start from t=0.** ACM is deployed with a new historian.
  Assume no earlier history can be loaded. ACM has to behave correctly
  from the first sample, and its early behaviour has to be accurate,
  not merely quiet.
- **C3. No fault list.** ACM is not told which faults to expect.
- **C4. Hundreds of assets.** The cost per asset per tick has to stay
  small and must not grow with the asset's age.
- **C5. Data faults are in scope.** ACM has to tell a bad sensor from a
  sick machine and keep working through bad data.
- **C6. Useful to operators.** An advisory has to say what, where,
  since when and how sure, in terms an operator can act on.

- **C7. Any asset, any industry, one input schema.** ACM takes a
  table with one timestamp column (ISO 8601 with an offset) and any
  number of numeric channel columns. It is told nothing else: no asset
  type, no tag meanings, no units. It has to run on any dataset in that
  shape.
- **C8. No tuned numbers.** No constant may be chosen by looking at a
  benchmark, and no constant may be adjusted to make a result come
  out. Section 10 gives the rules that enforce this.

## 3. What the constraints rule out

C2 changes the design more than anything else. The current build
assumes history exists:

- It fits on the older 60 percent of a calibration sample and
  calibrates on the rest. At t=0 there is no sample.
- Its evidence process needs at least 30 calibration blocks before it
  can run at all. Until then the verdict is "insufficient history".
- Its world model needed about a year of data per CARE event.

So the present design is a monitor for an asset with a past. C2 asks
for a monitor that grows up with the asset.

C1 also has a consequence the current build does not meet. A fault
episode stays open until someone presses Re-anchor. With no human, ACM
has to detect the repair itself.

C4 rules out anything that retrains a large model per asset on a
schedule. The world model took about 19 minutes per calibration on CPU.
At 300 assets and weekly rebuilds that is about 95 CPU-hours a week
for one model type.

## 4. The routes

Each route is a way to build the core learner: the part that decides
what "normal" is. They are scored against the constraints.

### Route A. Harden the current build

Batch ridge regression of each channel on the others, a fixed
calibration sample, six evidence streams.

- Cold start: poor. It abstains until history exists.
- Scale: acceptable.
- Data faults: none handled.
- Verdict: keep the plumbing (store, service, ledger, UI). Replace the
  learner and the decision layer.

### Route B. Online learner built from mergeable statistics

Keep, per asset, the running sums a linear model needs (counts, sums,
cross-products of the channels). Each new row updates them in place.
The model is solved from those sums whenever it is needed.

- Cold start: native. The model exists from the first rows. With
  little data its predictive range is wide, so it says little and
  alarms rarely. The range narrows as data arrives. Maturity is
  graded by the mathematics, with no gate to tune.
- New operating conditions: the same mathematics widens the range
  when the asset is somewhere it has not been before (the first cold
  start, the first winter). ACM reports "unfamiliar" and does not
  alarm.
- Scale: best of all routes. Cost per tick depends on the number of
  channels, not on age. Memory is one small matrix per period.
- Lifetime memory: the per-period sums are the memory. Masking a
  fault episode means leaving its sums out. A recency cap is a weight.
  A full rebuild from raw history gives the same answer.
- Power: limited to linear structure, unless the inputs are expanded
  with fixed nonlinear features, which keeps every property above.
- Verdict: recommended as the spine.

### Route C. A deep model per asset

The current Tier 2 world model.

- Cold start: worst. It needs the most data before it is useful.
- Scale: worst. See section 3.
- Power: possibly the best after a year or more. One CARE event was
  detected at 48 hours against 240 hours. That is a single example.
- Verdict: an optional later tier. It stays only if the evaluation
  harness shows a gain worth its cost.

### Route D. A pretrained time-series model, used without training

A published forecasting model predicts each channel from its own
recent past.

- Cold start: best for single-channel behaviour. It works after a few
  hundred samples.
- Blind spot: it does not know how channels relate to each other,
  which is where most fault evidence is.
- Scale: needs a GPU at hundreds of assets.
- Evidence: benchmark authors report that such models have not yet
  delivered for anomaly detection.
- Verdict: an experiment for the first weeks of an asset's life only.

### Route E. Memory of past states

Store representative past operating states. Ask of each new state
whether the asset has been here before, and what the channels read
last time.

- Cold start: works with a small memory and abstains outside it.
- Scale: needs the memory kept to a bounded set of representatives.
- Verdict: recommended as the "have I been here before" check beside
  Route B, not as the main learner. The current novelty engine asks
  this about a single score. It should ask it about the operating
  state.

### Route F. Compare similar assets with each other

- Cold start: the strongest tool there is. An asset that is faulty on
  day one stands out from twenty siblings on day two.
- Conflict: someone would have to mark which assets are alike. That
  breaks plug and play and constraint C1.
- Verdict: not needed and not recommended. `acm-design.md` section 5
  covers the faulty-at-start case without it.

### Summary

| Route | Cold start | Scale | Power when mature | Role |
|---|---|---|---|---|
| A current build | poor | fair | fair | keep plumbing only |
| B online statistics | good | best | fair to good | spine |
| C deep model | worst | worst | possibly best | later, if earned |
| D pretrained model | good, one channel at a time | needs GPU | unproven | early-life experiment |
| E state memory | good | fair | n/a | familiarity check |
| F peer comparison | best | good | good | rejected: needs manual marking |

## 5. What cold start can honestly deliver

No method can know on day one what a machine's normal year looks
like. The design goal is that ACM says the most that is true at each
age, and says which stage it is in.

| Age of data | What ACM can say |
|---|---|
| First minutes | Data faults: missing, stuck, out of range, spikes, bad timestamps. These need no baseline. |
| Hours to days | Sudden changes in a channel against its own short past. Which channels move together. |
| Days to weeks | Cross-channel breaks: a channel disagrees with what the others imply. Wide ranges, so only large faults. |
| Weeks to months | Slow drift. Familiarity with the common operating conditions. First repeating transients (starts, ramps). |
| One year and on | Seasonal conditions known. Full sensitivity. Comparison with earlier episodes. |

Two limits have to be stated to the operator, not hidden:

- **An asset that is already faulty at t=0** looks normal to a monitor
  that has only seen it faulty. ACM can catch this later: once enough
  life exists, it re-scores the early period and can report that the
  first weeks do not match the rest. `acm-design.md` section 5 gives the partial answers that
  need no other asset.
- **The first occurrence of any legitimate condition** (first winter,
  first product change) is unfamiliar. ACM should report "unfamiliar
  operating state" and not an alarm.

## 6. The other parts the goal needs

These hold whichever learner is chosen.

- **Data-quality layer, in front of everything.** Per-channel checks
  from the first sample. Then isolation: if replacing one channel
  with the value the others imply removes the anomaly, the sensor is
  suspect and the machine is not. ACM keeps monitoring with that
  channel replaced. This needs a "sensor suspect" verdict.
- **Decision layer.** Accumulate evidence per group of channels, not
  as one average over all of them. Use a detector that controls the
  average time between false advisories and restarts itself, so that
  a long healthy life does not slow detection. Let its reference grow
  from t=0 with the data. Check the promised rate on real healthy
  data, and state the assumption it rests on.
- **Self-closing episodes.** ACM detects a repair by itself: downtime
  followed by a coordinated return toward the earlier baseline.
- **Self-test.** Keep injecting synthetic disturbances into healthy
  data to confirm ACM still responds. These are generic shapes (step,
  drift, noise change, broken relationship), not a fault list.
- **Advisory.** One per episode: what, where, since when, actual
  against expected, growth, similar past episode, confidence, and the
  cold-start stage.

## 7. Evaluation, and the data it needs

CARE is pre-aggregated: each value is a 10-minute mean or similar. It
cannot test raw-data behaviour, data faults, or cold start from the
first sample. The harness needs raw data with known faults.

Candidates. Items marked "to verify" are from memory and need
checking before use.

| Source | Kind | Why it fits | Caveat |
|---|---|---|---|
| `lab/sim` generators (11 domains) | synthetic | Raw, any cadence, any length, faults and sensor faults placed exactly, starts at t=0 | ACM must not be shaped to its own simulator |
| MetroPT-3 | real, compressor on a metro train | Raw analogue and digital sensors, months long, failures known from maintenance reports | Sources disagree on sampling rate and dates |
| 3W 2.0 (Petrobras) | real and simulated oil wells | 1 Hz, 27 variables, 2,228 labelled instances from 42 wells | Short instances, weak for lifetime behaviour |
| Tennessee Eastman | simulated chemical plant | Raw process variables, 20 fault types, sustained faults | Simulated, short healthy history |
| Cranfield multiphase flow, PRONTO | real test rig | Raw, seeded faults (to verify) | Short runs |
| Hydraulic rig (UCI, ZeMA) | real test rig | Raw, graded degradation of four components (to verify) | Cyclic test, not continuous operation |

The harness should report, per method:

- false advisories per asset-year on long healthy data;
- detection and lead time on known faults;
- sensor faults correctly separated from machine faults;
- the same numbers at each cold-start stage of section 5;
- cost per asset per tick.

Every component has to beat a plain baseline on this harness to keep
its place.

## 8. Recommended order

1. Build the harness and the raw datasets of section 7.
2. Build the data-quality layer.
3. Build the Route B learner and the Route E familiarity check.
4. Rebuild the decision layer and self-closing episodes on top.
5. Rebuild the advisory.
6. Run Routes C and D as harness experiments.

## 9. Decisions this needs from the owner

- Approval of the design in `acm-design.md`.
- Whether the verdict contract may change to add "sensor suspect"
  and the learning stage. It is currently frozen.

## 10. Rules of evidence

Added 2026-11-12 at the owner's instruction. These exist so that ACM is
never declared finished on the strength of numbers that were tuned.

1. **Every number has a source.** A quantity in the code is one of:
   derived from the asset's own data at run time; the one false-advisory
   budget; or a structural constant with a written reason that does not
   mention any dataset. Anything else is a defect.
2. **Structural constants are tested for sensitivity.** For each one,
   the harness reruns with the constant halved and doubled. If the
   conclusions change, the constant is a hidden tuning knob and has to
   be replaced by something derived.
3. **Development data and judging data are separate.** Datasets used
   while building a method are named as such. A claim that ACM works is
   made only from datasets, asset types and seeds the method was not
   developed on. CARE is development data from now on.
4. **Report everything.** Every run on the judging data is reported,
   including the failures. A result is a table across all assets, never
   the best case.
5. **A baseline always runs beside ACM.** A change is kept only if it
   beats a plain baseline on the judging data.
6. **Limits are stated.** What ACM cannot detect is written down and
   shown to the operator, as in `acm-design.md` sections 9 and 11.

### What can honestly be promised

No design can be proved in advance to work on every asset in every
industry. What can be done is to make the claim testable and to refuse
shortcuts. The honest form of "ACM is solved" is: on judging data from
several unrelated asset types, with no settings changed between them,
ACM holds its false-advisory budget, detects the faults that leave a
trace in the data, separates sensor faults from machine faults, and
says plainly what it cannot see. Until the harness shows that, ACM is
not done, whatever a single benchmark says.

## 11. What can be certain, and where numbers come from

Added 2026-11-12 after the owner asked whether a right answer exists.

### There is a right structure

Two results from statistics fix the shape of the answer.

- **The decision layer has a provably best form.** For a given
  false-advisory rate there is a lower limit on how fast any detector
  can react to a given change, and known sequential tests reach that
  limit. Nothing can do better, so this part has a right answer.
- **The learner has a provably safe form.** Some learners are
  guaranteed to converge to the true normal behaviour of any asset as
  data grows, whatever the asset is. No learner is fastest on every
  asset, but one of this kind is never wrong in the long run.

A learner of the second kind feeding a test of the first kind is the
right combination. What differs from asset to asset is how long the
learner takes, and ACM can measure and report that per channel.

### Certain by construction

1. The false-advisory rate holds, on one condition: healthy behaviour
   in the future resembles healthy behaviour already seen, in the same
   operating state. ACM checks this condition continuously and says so
   when it fails.
2. For that rate, detection is as fast as the data allows.
3. The model approaches the asset's true normal as data accumulates.
4. A dead or blind part of ACM is noticed, because ACM keeps computing
   the smallest change it could detect on each channel.

### Never certain, for any method

1. A fault that leaves no trace in the measured channels is invisible.
2. The condition in point 1 above cannot be removed. Without it
   nothing can be learned from the past at all.
3. How long an asset takes to learn cannot be known before seeing it.

### Where every number comes from

The owner's rule: numbers are derived from the asset and its data, not
written in. In full:

- **One number is chosen by people:** the false-advisory budget.
- **Every statistical threshold is derived** from that budget (as the
  probability it implies) or estimated from the asset's own data.
  Examples: how close two readings must be to count as the same
  place; how fast a movement must be to count as a transient; how
  many repetitions make a state accepted.
- **Resource limits are allowed** (memory per asset, time per tick).
  They are not statistical. If one is reached, ACM reports reduced
  resolution instead of changing its conclusions silently.
- **Structural constants, kept short.** A few fixed numbers may remain
  where a derivation would mean judging data by itself, which was the
  failure of the old lab. Each has a written reason that names no
  dataset and has to pass the halve-and-double test of section 10.

This tightens rule 1 of section 10. The operating-map prototype does
not meet it yet: it has six written-in statistical constants (for
example "3 noise widths"), each of which has to be replaced by a
quantity derived from the budget or the data.

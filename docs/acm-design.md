# ACM: the design

Decided 2026-11-12. This is the design ACM will be built to. It follows
from the goal and constraints in `acm-goals-and-routes.md` and is bound
by the rules of evidence in section 10 of that document.

Status of each part is given in section 12. Most of it is not built. A
part becomes "done" only when it passes its gate on judging data.

Implementation review: the original review used ff7ed51. The merged
implementation includes aa55d12 and its preceding 34 commits: flat `src/`
modules, SQLite runtime/episode/evidence/wealth persistence, asset registry,
ingestion adapters, governed workers and the newer UI. These are retained.
The parts below describe the replacement design, not all existing product
features. Historical prototype results in section 10 were not rerun here.

Current verification limitation: the merged suite has 170 passing tests
and one auto-absorption failure, also reproduced on untouched aa55d12.
Rejected recalibration can leave the monitor uncalibrated after closing
the episode. See `merge-recovery-2026-11-12.md` for evidence and repair scope.

## 1. What ACM does

For any asset, given only a timestamp and numeric channels, ACM learns
what the asset normally does in each of its operating states, from the
first sample onward. It then reports four things: bad data, a suspect
sensor, a machine that no longer behaves like itself, and an operating
state it has not seen before. It holds a false-advisory rate that is
set once. It says what it cannot yet see.

## 2. The design in one page

```
rows -> [1 intake] -> [2 operating map] -> [3 residual graph]
     -> [4 evidence] -> [5 episodes] -> [6 advisory]
side loops: [7 delayed learning] [8 self-test] [9 slow drift]
```

Two learned objects per asset carry everything:

- **The operating map** answers "where is the asset operating, and
  what does each channel normally read there?" It handles what is
  nonlinear and what depends on state.
- **The residual graph** answers "given what is left after the map,
  what does each channel imply about each other channel?" It handles
  the tight local relationships: twin sensors, a bearing and its
  housing, three phases.

The split is deliberate. The behaviour of a machine is a few shared
drivers plus many local couplings. One model for both is either too
coarse or too expensive. Two simple models, each doing one job, are
cheap, update row by row, and exist from the first minutes.

## 3. The parts

### Part 1. Intake

- Checks that need no history: missing values, gaps, bad timestamps,
  a channel that stops changing, single-value spikes, all channels
  freezing together.
- **Channel typing, from the data alone.** A channel that takes only a
  few distinct values and switches between them repeatedly is a mode
  channel (a valve, a status bit, a tilt position). Mode channels are
  used as operating context, not judged as measurements. This is the
  answer to modes that are set by a single channel.
- Each value gets a validity flag. Invalid values are not learned
  from and are not evidence about the machine.

### Part 2. The operating map

1. **Operating coordinates.** The few directions in which the whole
   asset moves together, taken from running sums. Their number is set
   by the data. A fault on one channel hardly moves them.
2. **Memory coordinates.** Each operating coordinate is also kept as
   a small set of smoothed copies, at time scales spaced between the
   sampling interval and the correlation time of the asset itself.
   These let a slow channel (a temperature that lags load) be
   predicted, and they make "rising" and "falling" through the same
   point different places. This one device covers slow channels,
   ramps, and the phases of a batch cycle.
3. **Places.** Visited positions in these coordinates, plus the mode
   channels, are remembered as a bounded set. Two rows are in the
   same place when they differ by less than the uncertainty of the
   fit, at the probability the advisory budget implies.
4. **Normal at a place.** Each place keeps what every channel reads
   there and how much it varies. A young place borrows from its
   neighbours and from the whole asset, by an amount set by how much
   data it has.
5. **Familiarity.** How much experience ACM has near the present
   position. Low familiarity widens every uncertainty that follows.

States shown to people are groups of places the asset drifts between
slowly. They are a view for operators. The mathematics uses places,
so nothing flips at a state boundary.

### Part 3. The residual graph

After the expectation from the map is removed, the leftovers of all
channels still move together in small groups. ACM keeps running sums
of those leftovers and derives, in closed form, what each channel
should read given the others, and how sure that is. With little data
the estimate is pulled toward "unrelated", by an amount computed from
the data.

It gives three things at once: a much tighter expectation for coupled
channels, the groups themselves (the structure of the asset, without
drawings), and the test for a suspect sensor.

A second expectation uses the recent past of each channel, to catch
sudden changes on raw high-rate data.

### Part 4. Evidence

- The residual of each channel is turned into a probability by
  ranking it against clean residuals from the same state. This makes
  no assumption about the shape of the noise.
- A sequential test per channel adds evidence over time and restarts
  itself, so it stays fast after a long healthy life. Optimality depends on the specified change model and
  assumptions; no such result has been established for this ACM design.
- Channels in one asset are combined by averaging their evidence,
  which keeps the budget valid however the channels depend on each
  other.
- Low familiarity means little evidence. An asset in a new place does
  not accumulate evidence of a fault.

### Part 5. Episodes

When evidence crosses the line an episode opens. One test classifies
it: replace each suspect channel by its expectation and see what is
left.

| What is left | Verdict |
|---|---|
| One channel disagrees, the rest agree with each other | sensor suspect |
| Several coupled channels disagree | machine |
| The asset is somewhere it has not been, and its couplings hold | new operating state |
| Validity flags | data fault |

Closing needs no person:

- readings return and stay: closed, and marked as a probable repair
  if downtime came first;
- a new place is accepted when the asset returns to it or stays there
  without trending;
- anything that keeps trending is never accepted.

### Part 6. Advisory

One per episode: kind, channel group and the channel that moved first,
since when, whether growing, actual against expected, any similar
earlier episode, confidence, and the learning stage of the asset.

### Part 7. Delayed learning

New rows wait before they are learned, and are learned only if no
episode covered them. The wait starts short and grows with the age of
the asset, up to a cap. A developing fault cannot teach ACM that it is
normal.

### Part 8. Self-test

ACM computes, per channel and per state, the smallest change it could
detect and how long that would take. It publishes this. A channel it
cannot monitor is flagged. It also checks that clean residuals keep
ranking evenly. If they stop, the model is wrong: confidence drops
and the two objects are rebuilt from raw history.

### Part 9. Slow drift

The sums are stored per period. ACM compares recent couplings with
earlier life in the places both share. A steady move is evidence.

## 4. Decisions, with reasons

Each of these was a real choice. Where it differs from what the owner
suggested, that is said.

| Question | Decision | Reason |
|---|---|---|
| One model or two? | Map plus residual graph | Shared drivers and local couplings are different problems. The prototype showed the map alone leaves coupled channels loose. |
| Discrete states or continuous? | Continuous places. States are a view. | The owner asked for clearly identified states. Hard states flip at boundaries, and a fault can become one. Places give the same benefit without that. Operators still see named groups. |
| Slow channels and cycles? | Memory coordinates | One device, no asset knowledge. The prototype failed on exactly this, so it is the first thing to prove. |
| Single-channel modes? | Channel typing in intake | Repetition is the only thing that separates a mode from a fault. Typing uses repetition directly. |
| Compare similar assets? | No | Needs manual marking. The cases it helps are covered by trend, internal twins and later repair. |
| Human feedback? | Not in the core | Owner constraint, and correct: a monitor that needs confirmation does not scale to hundreds of assets. |
| Deep or pretrained models? | Not in the core | Worst at cold start and at scale. A slot remains: any model that gives an expectation and a spread per channel can replace parts 2 and 3. |
| Every number derived from data? | Mostly, not absolutely | The owner asked for no written-in numbers. On merit: thresholds come from the budget or the data. A short list of structural constants is allowed, each with a reason, and each has to pass the halve-and-double test. Deriving everything from the data being judged was the failure of the old lab, so "derive it" is not always safer than "fix it and prove it does not matter". |
| Certainty? | Conditional | The rate holds while healthy behaviour stays like itself within a state. ACM checks that and says when it fails. No method avoids this condition. |
| Accurate at t=0? | Staged | At t=0 ACM is accurate about data faults and honest that it knows nothing else. It reports its stage. Claiming more would be false. |
| Keep the current scoring code? | No | It needs history, has no data-fault handling, and averages away single-channel faults. It runs once on the harness as the baseline, then goes. |
| Keep the current plumbing? | Yes | Store, ingest, service, ledger and UI shell are sound. |

## 5. The learning stages

| Stage | Typical age | ACM reports |
|---|---|---|
| 0 | minutes | data faults only |
| 1 | hours to days | sudden changes, large breaks |
| 2 | days to weeks | coupled-channel breaks, first states |
| 3 | weeks to months | drift, most states familiar |
| 4 | a year | seasons covered, full sensitivity |

Stage is computed per channel and per state from the published
detectable change, not from the calendar.

## 6. Numbers

- Chosen by people: the false-advisory budget.
- Derived: every probability threshold (from the budget) and every
  scale, count of coordinates, time scale and resolution (from the
  data of the asset).
- Resource limits: places per asset, memory, time per tick. Reaching
  one lowers resolution and is reported.
- Structural constants: a short declared list, each with a reason
  that names no dataset, each passing the halve-and-double test.

## 7. Cost

Per asset: two tables of running sums per period, a bounded set of
places, one number per channel for evidence. Work per row grows with
the square of the channel count and not with age. No scheduled
retraining. Assets share nothing.

## 8. Limits, stated to the operator

- A fault with no trace in the measured channels is invisible.
- A defect present and stable from the first sample, with no twin
  channel and no later change, is invisible.
- The first visit to any state is "unfamiliar", never "healthy" or
  "faulty".
- States get numbers, not names.

## 9. What was rejected

Hard regimes; a single global model; a deep model per asset as the
core; pretrained forecasting models as the core; peer comparison;
thresholds derived from the window they judge; any constant chosen
from a benchmark; operator confirmation as a requirement.

## 10. Evidence so far

Only the map exists, as a prototype without memory coordinates,
channel typing or the residual graph (`src/opmap.py`). On single
runs:

| Asset | Result |
|---|---|
| Batch furnace, synthetic | 3 of 4 phases found. The two joined differ in one channel. |
| Motor, synthetic | Off and running separated. Running split in two. |
| Pump, synthetic | High found. Off and low joined, through slow thermal channels. |
| Wind turbine, real | Producing and stopped separated cleanly. Little gain over a global model on 10-minute averages. |

In all four, a fault on one channel did not create a state, and an
unseen operating level was reported as new. The three failures map
onto memory coordinates and channel typing. Whether those fix them is
not yet shown.

## 11. Build order and gates

Each step is gated on judging data, with the baseline beside it.

1. **Harness.** Raw datasets from several unrelated asset types, a
   fixed input schema, cold-start replay, the baseline, and the
   halve-and-double test. Gate: the numbers of the current build are
   recorded.
2. **Intake.** Gate: injected data faults found; channel typing
   correct on assets with known mode channels.
3. **Map with memory coordinates.** Gate: states match truth on
   continuous, stepped and cyclic assets with no settings changed;
   slow channels unbiased.
4. **Residual graph.** Gate: coupled channels tighter than the map
   alone; a suspect sensor isolated.
5. **Evidence and episodes.** Gate: budget held on healthy data;
   faults detected; sensor and machine told apart; episodes close
   unaided.
6. **Advisory and stages.**
7. **Remove the old scoring code.**

If a gate fails, the design is wrong at that point and is changed.
The gate is not moved.

## 12. Status

| Part | Status |
|---|---|
| Cross-asset judging harness | built (`src/bench/`), synthetic assets only; see section 14 |
| Online monitor (`src/online.py`) | built as a harness method, not wired into the runtime; gate 5 failed on detection, see section 14 |
| Proposed intake and sensor isolation | not built; validation and availability scoring already exist |
| Operating map | prototype, three known failures |
| Memory coordinates, channel typing | designed, not built |
| Residual graph | designed, not built |
| Replacement evidence, autonomous fault-repair closure | designed, not built; current banks, episodes and change absorption retained |
| Proposed advisory and maturity stages | not built; current verdicts and UI retained |
| Plumbing | retained: SQLite continuity, raw store, registry, ingestion, workers, service and UI |

## 13. Refinements proposed 2026-11-13

Proposed, not yet gated. Items 1 and 2 have a synthetic check behind
them; items 3 to 5 are argument only.

1. **Evidence needs no calibration set.** Rank each score against all
   earlier clean scores from the same state, bet on the resulting
   probabilities, and use a detector that restarts. Under
   exchangeable scores this is valid from the second score, so the
   "at least 30 calibration blocks" gate goes away. Maturity is then
   automatic: with n earlier scores the smallest probability is about
   1/(n+1), so a young asset cannot alarm and gains power as it ages.
2. **The unit of evidence is a block, not a row.** Block length is at
   least the correlation time of the residual, estimated from running
   lagged sums. Row-level evidence on strongly correlated residuals
   breaks the budget.
3. **State the budget as mean time between false advisories.** That is
   what a restarting detector controls, and it is what the owner sets
   (advisories per asset-year). It would replace the probability per
   anchor and `REANCHORS_PER_YEAR`. This changes a listed invariant
   and needs the owner's decision.
4. **A channel must not help define the place it is judged at.** The
   map places a row using all channels, including the faulty one, so
   part of a fault is absorbed into its own expectation. On assets
   with few channels this may be large. Gate 3 gains a measurement:
   the fraction of an injected single-channel offset that the
   expectation absorbs. If it is material, the expectation for a
   channel is formed without that channel.
5. **The map gets a challenger.** The prototype map carries ten
   written-in constants and is a clustering method. Route B with
   fixed nonlinear features of the operating coordinates gives an
   expectation, a spread and familiarity in closed form from running
   sums, with no codebook. Both run at gate 3; the one that passes
   stays. States shown to operators can be derived from either.

Synthetic check for items 1 and 2 (Gaussian scores, budget 0.05,
horizon 1000 scores from t=0, 1000 trials, two seeds; standard error
0.007). The number is the share of healthy runs that ever alarmed.

| Scores | Seed 0 | Seed 1 |
|---|---|---|
| independent rows | 0.001 | 0.002 |
| independent rows, reference delayed by 50 | 0.000 | 0.000 |
| AR(1) 0.5, rows | 0.004 | 0.007 |
| AR(1) 0.9, rows | 0.079 | 0.104 |
| AR(1) 0.9, block means of 1 correlation time | 0.004 | 0.003 |
| AR(1) 0.9, block means of 3 and 10 correlation times | 0.002 to 0.004 | 0.003 |

Detection of a mean shift by the restarting detector (threshold 1000,
seed 1, 400 trials, 500 scores allowed after onset):

| Age at onset (scores) | 2 sd shift: detected, median delay | 4 sd shift: detected, median delay |
|---|---|---|
| 10 | 0.17, 52 | 0.24, 16 |
| 30 | 0.66, 14 | 0.96, 6 |
| 100 | 1.00, 8 | 1.00, 3 |
| 300 | 1.00, 6 | 1.00, 2 |
| 1000 | 1.00, 5 | 1.00, 1 |
| 3000 | 1.00, 5 | 1.00, 1 |

Not covered by this check: scores from a model that is still
learning (early scores are larger, so scores are not exchangeable),
non-Gaussian or seasonal residuals, per-state ranking with few scores
per state, and real data. The test is conservative by a factor of
ten or more on independent scores, which costs detection delay.

## 14. First build and gate results, 2026-11-13

The harness (step 1) and a first online monitor covering parts 1 to 7
(`src/online.py`) were built. The monitor is not wired into the
runtime. Commands and scoring rules are in `testing-and-datasets.md`.

### Results

All runs: 1-minute data, lives of 30 days (healthy) or onset plus 5
days, onset at 6 hours, 3 days and 14 days, one seed per asset type.
The judging split was run once, after the method was frozen.

| Method, split | Cases | Healthy asset-years | False fault advisories | Machine faults found | Sensor offset or drift found | Stuck sensor, missing, frozen found | Spikes found | Cost per row |
|---|---|---|---|---|---|---|---|---|
| Plain baseline, development (4 onset ages) | 111 | 5.55 | 97 | chance level | chance level | 1 of 36 | 1 of 12 | 0.9 us |
| Current build, pump only, onset 14 days, 20-day lives | 10 | 0.44 | 57 | 0 of 2 | 0 of 2 | 0 of 3 | 0 of 1 | 2400 us |
| Online monitor, development | 84 | 1.86 | 0 | 1 of 18 | 0 of 18 | 27 of 27 | 0 of 9 | 480 us |
| Plain baseline, judging | 56 | 1.24 | 56 | 0 of 12 | 0 of 12 | 0 of 18 | 0 of 6 | 1.0 us |
| Online monitor, judging | 56 | 1.24 | 0 | 1 of 12 | 1 of 12 | 18 of 18 | 0 of 6 | 530 us |

New operating level reported as a new state: 5 of 9 (development) and
2 of 6 (judging), never misread as a fault. The monitor also raised
176 and 116 new-state notices on unlabelled data; most fall in an
asset's first days, when most states are new. That is too many to
show an operator as they are.

### What passed and what failed

- Gate 1 (harness, current numbers recorded): passed, with the limit
  that every asset is synthetic and written by the same hand as the
  method. The current build was measured on a reduced suite only.
- Gate 2 (intake): stuck, missing and frozen data found in every case
  within an hour and named correctly. Spikes are not found. Channel
  typing and timestamp checks are not built.
- Gate 5 (evidence and episodes): the budget held on both splits, with
  no false fault advisory in 3.1 asset-years. Detection failed: 2 of
  30 machine faults and 1 of 30 sensor offsets or drifts were found.
  By the rule in section 11 the design is wrong at this point and has
  to change; the gate is not moved.

### What was learned

1. The reference has to be scored the way a live row is scored. A
   reference scored by a model that had seen the data around it gave
   64 false advisories per asset-year, nearly all in the first week.
   Scoring each reference period by a model as far behind it as the
   live model is behind the present removed them. This replaces
   refinement 1 of section 13: ranking against all earlier scores is
   not enough while the model itself is still changing.
2. The learning delay of part 7 is a tuning knob. With delays of a
   quarter, an eighth and a sixteenth of the asset's age, false
   advisories stayed at zero on nine development cases while faults
   found went from 0 to 1 to 3 of 6. It fails the halve-and-double
   test. It was replaced: rows are learned at once and taken back out
   of the running sums exactly when an episode opens. A fault slower
   than about a tenth of the asset's age is still partly learned.
3. Serial dependence decides the power (refinement 2). Evidence at a
   scale is discounted by how long disturbances of that residual last,
   measured across block scales. On the development assets this
   discount is 50 to 100 fold at short scales for most channels,
   because one linear model per channel leaves errors that persist
   while the asset sits in one operating state. That is why detection
   fails. Subtracting the habitual error of similar states did not
   recover it.
4. A channel must not help define its own expectation (refinement 4).
   Built in: each channel is predicted from the others only, and a
   suspect sensor is named by replacing each candidate with its
   expectation and keeping the one that leaves the least behind.
5. A young asset cannot tell a fault from its own ignorance. Three
   rules now grade this by counts, not by a calendar gate: the rank
   cannot fall below 1/(n+1); a run is called a fault only if clean
   life holds enough blocks of that run's length; and an episode may
   block learning for at most a quarter of the life before it.
6. A rank cannot certify a few isolated spikes. Ten single-row spikes
   in a day stay within what ranks allow by chance. A spike rule needs
   a stated assumption about tails; none is built.

### Next change to the design

The expectation model is the weak part, not the test. The challenger
of refinement 5 (the operating map, or fixed nonlinear features of the
operating coordinates) is now needed for a measured reason: to remove
the state-dependent errors that make the residuals persistent. The
measure of success is the dependence discount at short scales, then
gate 5 detection, with the budget still held.

Also open: real raw labelled datasets for the judging split; the
structural constants in `online.py` have not been through the
halve-and-double run; cost per row is about 0.5 ms and has to fall;
new-state notices need grouping before they reach an operator.

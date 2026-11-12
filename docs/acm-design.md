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
| Cross-asset judging harness | not built; existing tests and soak are regression evidence |
| Proposed intake and sensor isolation | not built; validation and availability scoring already exist |
| Operating map | prototype, three known failures |
| Memory coordinates, channel typing | designed, not built |
| Residual graph | designed, not built |
| Replacement evidence, autonomous fault-repair closure | designed, not built; current banks, episodes and change absorption retained |
| Proposed advisory and maturity stages | not built; current verdicts and UI retained |
| Plumbing | retained: SQLite continuity, raw store, registry, ingestion, workers, service and UI |

# ACM — Problems and Solutions

Date: 2026-02-21
Owner: Snehil
Status: Living document — authoritative design reference

---

## Purpose

This document is the single authoritative record of what is wrong with ACM, why it is wrong, and what the correct solution is for each problem. It supersedes all prior issue lists, refactor trackers, and architecture notes. It is organized by problem category, not by fix history.

No code is discussed here. This is a design and reasoning document. Every problem statement is grounded in observed system behavior, not speculation.

---

## Part I — The Fundamental Architecture Problem

### What ACM Was Designed to Be

ACM was designed as a streaming system. A historian captures sensor readings at fixed intervals. A scheduled ACM job runs every X minutes, reads the latest X minutes of data, detects anomalies, and writes results. Over months of operation, the system accumulates evidence, refines its understanding of the equipment, and produces increasingly confident assessments.

That is the intended behavior. It is not what actually happens.

### What ACM Actually Does

Each batch run loads a window of historical data — in practice, 13-day windows for the wind turbines. It trains or reloads detectors, scores the window, writes output, and terminates. The next batch run loads the next 13-day window. The two runs share persisted detector models and regime cluster centroids, but share no knowledge of what the equipment was doing, how health was trending, or what happened in the days between the two scored windows.

The system is not accumulating knowledge. It is making repeated independent assessments of disjoint time windows using the same fixed detector baseline.

### Why This Matters

The consequence is visible in the data. WFA_TURBINE_0 had a HealthIndex of 72 at the end of batch 1. Batch 2 opened — 14 days later in historian time — with a HealthIndex of 6. The turbine degraded catastrophically in those 14 days. No alert was generated about the 66-point health drop. No signal existed that it was sudden rather than gradual. The system correctly labeled batch 2 as ALERT, but had no context for why, how fast, or whether it was expected.

This is not a detector sensitivity problem. The detectors were working correctly within each window. This is an architectural problem: the system has no memory.

---

## Part II — The Six Active Problems

### Problem 1: Batch Amnesia

**What it is:** Each batch forgets everything the previous batch observed. There is no representation of long-run health trajectory, degradation acceleration, or persistent anomaly duration anywhere in the system's output or decision-making.

**Why it happens:** The pipeline was designed around a single-batch evaluation model. The outputs — scores, episodes, health timeline — are written per-run and serve as independent snapshots. Nothing reads across runs to synthesize a multi-run signal.

**What breaks because of it:**

- There is no answer to "how long has this equipment been in degradation?" The answer exists in the data but no component computes it.
- There is no distinction between "health dropped from 80 to 20 over three months" and "health dropped from 80 to 20 overnight." Both produce identical per-batch outputs.
- Chronic persistent degradation — the most operationally dangerous pattern — is the least visible pattern in the current system.
- The drift detection module (which is intended to answer trend questions) resets its cumulative state at every batch boundary, making it structurally incapable of detecting trends that span more than one batch.

**What the solution requires:** A persistent summary row written at the end of every batch containing: the historian window covered, average and ending HealthIndex, the fitted degradation slope, the dominant operating regime, and a flag for whether a maintenance event was detected. This batch summary becomes the input to all cross-batch analysis. It is lightweight — one row per batch per equipment — and requires no changes to the per-batch detector pipeline.

Once the batch summary exists, a second artifact is needed: a trend anchor — the last observed HealthIndex value, its historian timestamp, and the fitted slope — persisted as a single upserted row per equipment. The next batch reads this anchor, projects where health should be at the start of its window, and compares that projection to the actual observed opening value. The deviation between projected and actual is a new signal that does not exist anywhere in the current system.

---

### Problem 2: Gap Blindness

**What it is:** Between scored windows, equipment keeps running and the historian keeps recording. ACM scores none of it. When the next batch starts, ACM sees only the state of the equipment at the beginning of that window — not the trajectory that led to it.

**Why it happens:** The batch windowing model was designed for a scenario where batches are contiguous or nearly contiguous. In practice, the wind turbine data shows 12-14 day gaps between consecutive scored windows. During each gap, any degradation, maintenance, or failure event is invisible to ACM.

**What breaks because of it:**

- Sudden events in unmonitored periods (seizure, bearing failure, partial repair) look identical to gradual events. The opening HealthIndex of the next batch is all that is observable.
- Maintenance performed during a gap appears as an unexplained positive jump at batch start. The system has no way to classify this as maintenance rather than normal operating variation.
- Accelerated degradation during a gap — health declining faster than the prior trend projected — produces no alert. The next batch opens in ALERT with no explanation of how it got there.

**What the solution requires:** At the start of every batch, load the trend anchor from the previous batch. Compute the expected health at the start of this batch by extrapolating the prior slope across the gap duration. Compare expected to actual. If the deviation exceeds a configurable threshold in the negative direction, classify as a gap degradation event and write a gap alert. If the deviation is strongly positive, classify as a potential maintenance event. In both cases, write a structured record that operators and the dashboard can surface.

This gap deviation is the most operationally actionable new signal the system can produce. It answers the question maintenance engineers are actually asking: "what happened while we weren't watching?"

---

### Problem 3: Baseline Drift

**What it is:** All six detectors calibrate their z-scores against the statistical distribution of the training window. That calibration is anchored to training time and never automatically updated. As the equipment's true normal state slowly evolves over months — natural aging, wear, component replacement — the training-time "normal" becomes an increasingly inaccurate reference.

**Why it happens:** This is by design, but the design has a flaw. Anchoring z-scores to training is correct for preventing false negatives (detectors should remain sensitive to departures from original normal). But the system has no mechanism to distinguish between three very different scenarios that all produce the same observable effect — rising z-scores over time:

1. Genuine degradation: equipment is getting worse, rising z-scores are correct
2. Normal aging: equipment has shifted to a new stable state at a lower performance level, rising z-scores are misleading
3. Calibration drift: the training baseline was set during a mild anomaly period, so "normal" operation now looks anomalous

**What breaks because of it:**

- On well-maintained equipment that has aged gracefully, the health index declines over months even during healthy operation. Operators lose trust in the signal.
- On equipment that recovers after maintenance, the post-maintenance healthy state may look anomalous relative to the pre-failure training baseline if the training captured pre-failure as "normal."
- There is no way for an operator or the system itself to know whether a rising health alert reflects a real problem or a stale calibration reference.

**What the solution requires:** Separating two concepts that are currently conflated. The training anchor — the statistical distribution against which detectors compute z-scores — should remain fixed. Detector sensitivity must not degrade with time. But a separate health reference — the most recently confirmed healthy operating state — should be tracked and updated when the equipment demonstrably returns to good health (after maintenance, or after a sustained period of low z-scores with high model confidence). The health reference is used for trend direction assessment only, not for anomaly scoring. This separation prevents calibration drift from distorting health trend analysis while keeping detector sensitivity anchored to a meaningful baseline.

---

### Problem 4: Maintenance Events Are Invisible

**What it is:** When maintenance is performed on equipment — bearing replacement, lubrication service, component overhaul — health typically improves. In the data, this appears as a sudden positive jump in HealthIndex at the start of the next scored window. The current system has no mechanism to detect, classify, record, or respond to this event.

**Why it happens:** The pipeline was designed around anomaly detection, which is fundamentally about detecting negative deviations. Positive deviations were not considered as first-class events.

**What breaks because of it:**

- Trend slopes computed across a maintenance event are corrupted. A slope fitted on data from both before a repair and after will underestimate degradation (because the post-maintenance data pulls the average up). The existing code in the old forecasting module noted this and truncated data at detected jumps, but this logic was never applied to the cross-batch trend persistence that does not yet exist.
- There is no record of when maintenance occurred as observed by ACM, what health level was restored to, or whether it restored health to the expected level. This information is valuable for maintenance effectiveness analysis.
- Post-maintenance, the trend anchor still contains the pre-maintenance slope. If the next batch computes a new slope from only its current window (which is post-maintenance data), and compares it to the pre-maintenance anchor, the gap deviation will look like an anomalous positive jump rather than a maintenance event.

**What the solution requires:** A formal maintenance event registry. When a batch opens with a HealthIndex significantly higher than the prior trend projected — beyond normal noise — classify this as a maintenance event. Record the detected timestamp, the health level before (end of prior batch) and after (start of this batch), and the magnitude of improvement. After detecting a maintenance event, reset the trend anchor to the post-maintenance operating state. Begin tracking a new maintenance epoch from this point. Do not carry pre-maintenance slopes forward.

The threshold for classifying a maintenance event versus normal positive variation is configurable. The 15% positive jump rule established in the statistical conventions is a reasonable starting point.

---

### Problem 5: Drift Detection Is Broken

**What it is:** The drift detection module has four distinct bugs that are all currently known and none are fixed. Collectively, they mean the drift signal is unreliable in both the within-batch and cross-batch dimensions.

**The four bugs:**

**Bug 1 — Hysteresis never fires.** The drift state machine is designed with hysteresis: once in SUSTAINED_DRIFT mode, the system requires sustained evidence of improvement before exiting. This prevents noisy oscillation. The bug is that the previous batch's drift mode is never passed into the current batch's computation. Every batch starts the hysteresis logic from a default FAULT state. Sustained drift can never be detected because the state machine resets every batch.

**Bug 2 — Alert condition logic is inverted.** The condition for scoring a drift vote based on the fused z-score's 95th percentile is written with an upper bound that causes the opposite of the intended behavior: severe faults (z-score above 5.0) reduce the drift vote rather than increase it. A batch with extreme anomalies scores as less drifting than a batch with moderate anomalies.

**Bug 3 — Column naming mismatch.** The drift module writes its computed mode to a column named `alert_mode`. The pipeline reads from a column named `drift_mode`. These never connect. The drift state is always read as STABLE regardless of what the drift module computed.

**Bug 4 — CUSUM state contaminated.** The CUSUM detector used in drift computation accumulates state during its calibration (fit) phase. That accumulated state is not reset before the scoring phase begins. The CUSUM sums are non-zero at the start of scoring, producing systematically biased drift scores.

**What the solution requires:** Four targeted fixes, in dependency order. Fix the column naming mismatch first (it is the most fundamental — without it, no drift state ever propagates). Fix the CUSUM reset second (it corrupts the raw signal). Fix the alert condition logic third (it inverts the meaningful output). Fix the hysteresis state passing fourth (it makes sustained drift detectable). Each fix is isolated to a specific location. None requires architectural changes.

After the bugs are fixed, there remains the deeper architectural gap: within-batch drift can only detect trend changes visible within a 13-day window. Cross-batch drift — the signal that answers "is this equipment's condition declining month over month?" — requires running the CUSUM on the batch summary history, not on within-batch scores. This is a separate implementation, not a bug fix.

---

### Problem 6: Forecasting Is Disabled and the Prior Design Was Wrong

**What it is:** The forecasting module (`forecast_engine.py`) is explicitly disabled. The prior design attempted to use a Holt-Winters regime-conditioned trend model for RUL estimation. It was disabled because it produced unstable, unreliable estimates.

**Why the prior approach was wrong:** The prior approach tried to fit a per-batch trend model, extrapolate it forward, and estimate hours to failure. This fails for two reasons. First, a 13-day window of HealthIndex data — oscillating within a regime, with potential episodes — does not reliably reveal the long-run degradation slope. The within-batch trend is dominated by within-batch noise. Second, estimating Remaining Useful Life requires knowing the failure threshold and having a reliable long-run slope. Neither is available from a single batch.

**Why a foundation model (TimesFM) is also wrong:** Loading 2GB of model weights per process for 20+ equipment running in parallel is not operationally feasible. More importantly, industrial health degradation is smooth and monotonic — it is not the kind of complex, chaotic signal that requires a neural network to model. A weighted median slope estimator (Theil-Sen) runs in milliseconds, requires no weights, and is the industry standard method referenced in ISO 13381-1 for condition-based prognostics.

**What the solution requires:** Three lightweight statistical components, no new dependencies.

The first component estimates the current degradation slope: a Theil-Sen estimator applied to the HealthIndex series within the current batch, conditioned on the current regime, truncated at the most recent maintenance event if one was detected. Theil-Sen is the median of all pairwise slopes — it is maximally robust to the episodic anomaly dips that contaminate health series within a batch.

The second component projects when each alarm threshold will be crossed: given a current HealthIndex value and a slope estimate with confidence interval, compute the expected time to cross each zone boundary (WARNING, ALERT, FAILURE) under the P50 (median), P10 (pessimistic), and P90 (optimistic) slope assumptions. For late-stage degradation where the slope is steepening across recent windows, extend to quadratic extrapolation if the fit quality justifies it.

The third component assesses whether the forecast is trustworthy enough to surface. A confidence score is computed as the harmonic mean of sub-scores for window length, slope uncertainty, data quality flag, regime stability, and spread between pessimistic and optimistic breach times. Below a threshold (0.25), the forecast is suppressed entirely rather than shown with false precision.

When the batch summary history (from Problem 1's solution) is available, the slope estimate should prefer the multi-batch slope — computed over the last N batch summaries — over the within-batch slope. The multi-batch slope is far more reliable for long-range breach projection.

The output is not an RUL number. It is a calendar timestamp: "At current trend, health will cross the WARNING threshold at approximately [datetime], with uncertainty spanning [datetime_P10] to [datetime_P90]." This is directly actionable for maintenance scheduling. A confidence width that spans more than 7 days is a signal to show but not to act on — the trend is not well-established enough for confident planning.

---

## Part III — What the Detector Ensemble Gets Right and Wrong

### Why Six Detectors

The six detectors — AR1, PCA-SPE, PCA-T², IForest, GMM, OMR — exist because fault manifestations in industrial sensor data come in fundamentally different shapes, and each detector only reliably sees one shape.

AR1 asks whether an individual sensor deviated from its own recent pattern. It catches isolated spikes and abrupt changes in single sensors. It misses coordinated multi-sensor shifts entirely.

PCA-SPE asks whether the current combination of sensor readings lies outside the normal operating manifold learned during training. It catches novel multivariate operating states that no individual sensor would flag. It misses faults that happen to lie along a principal direction of normal variation.

PCA-T² is the complement of SPE: it asks whether the equipment is at an extreme position along the normal axes, rather than off those axes entirely. Together, SPE and T² cover the full PCA decomposition.

IForest asks how easy this data point is to isolate from the normal data cloud, without making any assumptions about the shape of that cloud. It is the only detector that makes no distributional assumptions, making it valuable for equipment with complex non-Gaussian operating behavior.

GMM asks how probable this operating state is under the learned mixture distribution of healthy operation. It is the most sensitive to rare density events but also the most sensitive to training contamination.

OMR asks whether the relationships between sensors are intact. A bearing lubrication fault may not spike any individual sensor but will cause temperature and vibration to decouple — a relationship that was stable during healthy operation. OMR is the only detector that explicitly models these inter-sensor dependencies.

No fault type in the coverage map is caught by all six detectors. No fault type is caught by only one. This complementarity is the argument for the ensemble. A complex real-world fault will often leave signatures in three or four of the six detectors simultaneously, producing a high-confidence fused alarm. A borderline event might only appear in one detector, producing a moderate signal that is surfaced but not acted on.

### Where the Ensemble Fails

**Training contamination.** All six detectors are trained on whatever data was available at coldstart. If that first window contained a degradation episode — as the WFA_TURBINE_0 data shows is entirely possible — all detectors absorb some of that degraded behavior as "normal." The contamination filter (iterative MAD exclusion) reduces but cannot eliminate this. The consequence is that future instances of the same fault pattern are systematically underscored. The only full solution is to re-train on a clean confirmed-healthy window, which requires knowing when one exists — a chicken-and-egg problem in unsupervised learning.

**No temporal structure in most detectors.** IForest, GMM, and OMR score each time point as if it were independent — no knowledge of adjacent points. A fault that is only visible as a pattern across 20 consecutive readings (each one plausible in isolation) will not be detected by these three detectors. Episode detection by CUSUM partially fills this gap at the fusion stage, but CUSUM only sees the fused z-score, not the raw sensor relationships that OMR could exploit if it had temporal memory.

**Baseline drift.** The calibration anchors are set at training time and never automatically updated. On equipment that ages slowly, the health index declines even during genuinely healthy operation. On equipment that undergoes maintenance, the post-repair state may look anomalous relative to a pre-failure training baseline. This is addressed by Problem 3's solution (baseline separation), not by changes to the detectors themselves.

**Shared blind spots.** PCA-SPE, PCA-T², and OMR all involve dimensionality reduction or reconstruction and share the same structural blind spot: faults whose signatures are well-represented in the training data will be well-reconstructed and poorly scored. A fault mode that happened to occur during training is invisible to all three of these detectors simultaneously.

### What Is Not a Detector Problem

The most important coverage gaps are not addressed by adding more detectors or changing detector weights. They are architectural:

- Whether this equipment is getting worse month over month is not answerable by any within-batch detector. It requires the batch summary history.
- Whether a repair was effective is not answerable by any detector. It requires the maintenance event registry and health reference tracking.
- Whether the anomaly score trend is accelerating across batches is not answerable by any detector. It requires cross-batch drift.

Six detectors covering the six primary fault families is the correct ensemble. The gaps that remain belong to the continuity and forecasting layers that sit above the detectors, not to the detectors themselves.

---

## Part IV — The Refactoring Context

### What Is Being Refactored and Why

The pipeline previously had two entry points and two files that shared responsibility in an unclear way. `acm_main.py` contained the orchestration logic. `acm.py` was the command surface. Over time, `acm_main.py` grew to thousands of lines containing a mixture of configuration, orchestration, statistics, SQL write logic, and business rules, all interleaved.

The refactoring objective is a single entry point (`core/acm.py`) with clear ownership boundaries: each concern — calibration, fusion, drift, regime, model lifecycle, output writing — lives in its own module and is called by the orchestrator with a clear interface.

This is not architectural redesign. It is not changing what the pipeline does. It is making the code legible and testable so that the actual architectural changes described in this document can be implemented safely.

### What the Refactoring Does Not Fix

The refactoring, when complete, will produce a clean single-entrypoint pipeline that still has all six problems described above. A clean monolith is still a monolith. The pipeline will still have batch amnesia, gap blindness, baseline drift, invisible maintenance events, broken drift detection, and no forecasting.

The refactoring is a prerequisite, not a solution. It creates the conditions under which the solutions can be added safely — modularly, testably, with clear ownership of each new concern.

---

## Part V — The Solution Architecture

The solutions to the six problems are organized into two workstreams that are independent but reinforce each other.

### Workstream A: Batch Continuity

This workstream gives ACM memory. It does not change the detector pipeline, calibration, or episode detection. It adds persistence of summary information across batch boundaries and uses that information to generate signals that are currently impossible.

**A1 — Batch Summary**
A single row written at the end of every batch, appended to a permanent per-equipment history. Contains the historian window, health statistics, fitted slope, dominant regime, maintenance flag. This is the coarse time series from which all long-run analysis reads. Nothing long-run is possible without this.

**A2 — Trend Anchor**
A single upserted row per equipment per series containing the last observed value, its historian timestamp, the fitted slope, and a confidence score. Read at the start of each batch. Used to project expected health at batch start and detect gap deviations. The gap deviation signal is the most immediately valuable output of this entire workstream.

**A3 — Gap Alerts**
Structured records written when the gap deviation between projected and actual health exceeds a threshold. Surfaced in dashboards and logs. This is the answer to "what happened while we weren't watching?"

**A4 — Maintenance Event Detection and Registry**
Classification of large positive health jumps at batch boundaries as maintenance events. Formal recording in a dedicated table. Post-maintenance reset of the trend anchor to exclude pre-maintenance data. Tracking of maintenance effectiveness in subsequent batches.

**A5 — Health Reference**
A separate persistent record of the most recent confirmed-healthy operating state, distinct from the training anchor. Updated after maintenance events and after sustained confirmed-healthy periods. Used for trend direction assessment so that baseline drift does not corrupt the long-run health signal.

**A6 — Drift Bug Fixes**
Four targeted fixes to the drift detection module: standardize the column name, reset CUSUM state before scoring, correct the alert condition logic, pass the prior batch's drift mode into the current batch's hysteresis computation.

**A7 — Cross-Batch Drift**
A second drift signal, independent of the within-batch signal, computed by running CUSUM on the batch summary history. Detects sustained multi-month deterioration that no single-batch signal can see. Produces a `drift_mode_sustained` field distinct from the existing within-batch drift mode.

### Workstream B: Forecasting

This workstream answers the question "when will this equipment need attention?" It depends on Workstream A being done first, because the most reliable forecasts use multi-batch slope history rather than within-batch slope estimates alone.

**B1 — Degradation Slope Estimation**
Theil-Sen slope fitted on the HealthIndex series within the current batch, conditioned on the current regime, truncated at detected maintenance events. Returns slope with 95% confidence interval. Prefers multi-batch slope history from the batch summary when available.

**B2 — Horizon Projection**
Given slope and current health, compute expected time to cross each alarm threshold (WARNING, ALERT, FAILURE) under pessimistic (P10), median (P50), and optimistic (P90) slope assumptions. For late-stage equipment with steepening slope, extend to quadratic if fit quality justifies it. Output is a calendar timestamp per threshold per confidence band.

**B3 — Forecast Confidence**
Harmonic mean confidence score from five sub-scores: fit window length, slope confidence interval width, data quality flag, regime stability, and breach time uncertainty spread. Below 0.25, suppress output entirely. Above 0.25, surface with explicit confidence percentage.

**B4 — Stable Detector Z-Score Forecasting**
After Workstream A is delivering reliable batch summaries, extend the slope estimation and horizon projection to the two most stable detector z-scores: GMM and OMR. These have demonstrated stable within-batch behavior. Project when each will cross its alert threshold (z = 3.0). Skip AR1 and CUSUM until their cross-batch continuity bugs are resolved.

---

## Part VI — Principles That Must Not Be Violated

These are rules that have been learned through fixing bugs. Violating them has caused some of the most damaging failures in the system's history.

**Detectors calibrate against training. Never scoring.** The ScoreCalibrator is fit on the training window and applied to the scoring window unchanged. Re-calibrating on scoring data would make the anomaly score relative to the scoring window itself — a circular definition that destroys anomaly detection entirely. This was broken in an early version and caused the system to report every window as healthy.

**Regimes are defined by how the equipment operates, not by how healthy it is.** Regime clustering must use raw sensor readings (load, speed, flow, pressure) as its basis features. It must never use health-state features (z-scores, health index). Including health-state features in regime clustering creates a circular dependency: a regime is partly defined by anomaly severity, but anomaly severity is calibrated per-regime. This causes degraded equipment to be clustered into a "degraded regime" which then receives a high anomaly threshold, masking the very degradation that created the regime.

**Robust statistics everywhere.** All statistical computations use median and MAD, not mean and standard deviation. The breakdown point of median/MAD is 50% (half the data can be corrupt before the estimate is meaningless). The breakdown point of mean/std is 0% (a single extreme value destroys the estimate). In industrial data, contaminated windows are the rule, not the exception.

**Harmonic mean for confidence, not geometric or arithmetic.** A confidence score that is the harmonic mean of its components is pulled strongly toward its lowest component. This is the correct behavior: a forecast that is uncertain in one dimension (say, short fit window) should not be reported as high-confidence just because the other four dimensions are good. Geometric mean is insufficient; arithmetic mean is wrong.

**Force retraining must come only from explicit operator instruction.** The `CONTINUOUS_LEARNING` config flag gates whether quality evaluation runs, but it is not a force-retrain signal. Treating it as one causes every scoring batch to retrain, destroying the cross-batch model consistency that makes z-scores comparable across runs.

**Batch continuity additions are additive, never modifying.** The batch summary, trend anchor, gap alerts, and maintenance registry are written as new SQL rows. They never modify the existing per-batch output tables. The existing pipeline behavior is invariant. If the new tables are absent or empty, the pipeline proceeds normally with a logged warning.

---

## Part VII — What Success Looks Like

A fully-implemented ACM should be able to answer all of the following questions from its outputs, without operator interpretation:

**Immediate questions (answerable from a single batch):**
- Is this equipment healthy right now?
- Which sensors are most anomalous?
- Which detectors are alarming?
- Is this a new episode or a continuation of a prior one?
- What operating regime is the equipment in?

**Short-range questions (answerable once forecasting is implemented):**
- At current trend, when will this equipment cross the WARNING threshold?
- How confident is that projection?
- Is the degradation rate accelerating or stable?

**Long-range questions (answerable once batch continuity is implemented):**
- How long has this equipment been in degradation?
- Was the last maintenance event effective? Did health recover to expected levels?
- Is this equipment's condition getting worse month over month, or is it stable?
- What happened in the unmonitored gap before this batch? Was there an event?
- How many consecutive batches has this equipment spent in ALERT?

**Trust questions (answerable once health reference separation is implemented):**
- Is the training baseline still a valid reference for this equipment?
- How old is the training calibration?
- Is rising anomaly score reflecting genuine degradation or calibration staleness?

No current version of ACM can answer any question in the long-range or trust categories. These are the missing capabilities, not missing detector sensitivity.

---

## Part VIII — Implementation Order

The correct sequence of implementation respects dependencies: nothing that reads from a table should be built before the table is written.

**Stage 1 — Foundation of memory**
Batch summary and trend anchor. These have no dependencies on anything else. They write at batch end and read at batch start. Nothing in the existing pipeline changes. Every subsequent capability depends on these existing.

**Stage 2 — Gap and maintenance signals**
Gap alert generation and maintenance event detection. These depend on the trend anchor. They add new output tables and new log entries. No changes to existing pipeline outputs.

**Stage 3 — Health reference separation**
Separate the training anchor from the health reference. Track confirmed-healthy periods. Update health reference post-maintenance. This changes how trend direction is assessed but does not change anomaly scoring.

**Stage 4 — Drift bug fixes**
The four drift bugs. These are self-contained code fixes with no new tables or architectural changes. They should be done as early as possible since they affect existing output, but their dependencies are minimal.

**Stage 5 — Within-batch forecasting**
Slope estimation, horizon projection, confidence scoring on HealthIndex within the current batch. New tables: health forecast trajectory and breach projections. Reads from existing HealthTimeline. Depends on zone threshold values being accessible from config.

**Stage 6 — Cross-batch drift**
CUSUM on batch summary history. New drift signal distinct from within-batch. Depends on Stage 1 (batch summary must exist).

**Stage 7 — Multi-batch slope for forecasting**
Upgrade the slope estimator to use batch summary history when available. Forecasts become significantly more reliable. Depends on Stage 1 and Stage 5.

**Stage 8 — Stable detector z-score forecasting**
Extend forecasting to GMM and OMR z-scores. Depends on Stage 5 pattern being established and validated.

---

## Appendix: Known Problems Not Yet Designed

The following problems are identified but their solutions have not been designed in detail. They are recorded here to prevent them from being forgotten.

**Sensor relationship drift.** OMR detects sensor relationship breaks within a batch. It cannot detect that the normal relationships between sensors have slowly shifted over six months (indicating gradual mechanical wear). Detecting this would require comparing current OMR reconstruction error characteristics to those at training time, which in turn requires the training-time OMR residual distribution to be persisted — it currently is not.

**Training contamination with no clean reference.** The contamination filter (iterative MAD exclusion) reduces the impact of anomalies in training data but cannot remove them if the anomaly fraction is high. The fundamental solution is to identify a clean confirmed-healthy window and retrain from it. This requires a human-confirmed "this period was definitely healthy" annotation, which ACM does not currently support.

**Fleet-level learning.** All 25 wind turbines are nominally identical equipment running in the same conditions. They should share information — a fault pattern that appears on turbine 3 may appear on turbine 7 two weeks later. Currently each turbine is entirely independent. Fleet-level learning would require a new architecture component that has not been designed.

**Regime discovery in CONVERGED state.** Once a model reaches CONVERGED, regime discovery is blocked. If the equipment enters a genuinely new operating regime — a new load profile, seasonal operating condition, or post-maintenance configuration — the CONVERGED model cannot adapt. The current solution is to trigger a refit, which resets maturity to LEARNING. A more nuanced solution that allows novel regime detection without requiring a full refit has not been designed.

# ACM Batch Continuity — Design for a True Adaptive System

Date: 2026-02-21
Owner: Snehil
Status: Design — analytical plan, no code

---

## 0. The Core Problem, Stated Simply

ACM was designed for streaming data — new readings arrive every X minutes, a batch runs, and the system adapts. In reality, the system scores a 13-day historical window, stores results, then scores the *next* 13-day window with no memory of what it just saw.

The machine does not accumulate knowledge over time. It re-learns from scratch on each isolated slice. That is not unsupervised learning — that is repeated supervised fitting on disjoint windows.

Every batch asks: "is this window anomalous relative to itself?" It never asks: "is this equipment worse than it was three months ago?"

That question — the long-run question — is what a true condition monitoring system must answer.

---

## 1. What the Data Reveals

From the live database for WFA_TURBINE_0:

```
Run 1:  Aug 19 → Aug 29     HealthIndex: 83.5 → 72.4    (zone: WATCH, declining)
        [14-day gap in historian — unscored, equipment was running]
Run 2:  Sep 12 → Sep 24     HealthIndex: 6.2 → 59.2     (zone: ALERT at start)
        [13-day gap]
Run 3:  Oct 07 → Oct 20     HealthIndex: 6.9 → 40.4     (zone: ALERT at start)
        [12-day gap]
... continues, each window opens in ALERT with HealthIndex 6-8
Run 8:  Feb 12 → Aug 24     HealthIndex: 7.2 → 15.5     (4619 hours, still degrading)
```

The turbine started at health 83, degraded to 6 in an unmonitored 14-day window, and never recovered. The system correctly identified ALERT within each batch, but it had no way to say: "this equipment has been in persistent degradation for six months." The timeline was visible only to someone who looked at all eight runs side by side.

No automated signal was ever generated about the long-run trajectory. No threshold was crossed based on *cumulative* information. Each batch generated its own local alerts and forgot them.

---

## 2. What ACM Currently Persists Across Batches

To understand what is missing, it helps to know what already works:

**Correctly persisted (works well):**
- Detector ensemble models (AR1, PCA, IForest, GMM, OMR) — versioned in `ModelRegistry`
- ScoreCalibrator parameters — training-anchored z-score normalization
- Regime cluster centroids and scalers — equipment operating modes
- Model maturity state (COLDSTART/LEARNING/CONVERGED) — lifecycle gating
- Adaptive thresholds — per-regime quantile-based alert levels
- Consecutive run count — maturity promotion gating

**Not persisted — lost at batch boundary:**
- Drift controller CUSUM state (`sum_pos`/`sum_neg`) — resets to zero each batch
- Previous drift alert mode — hysteresis never fires because mode is not passed forward
- Health trend direction — no memory of whether health was improving or worsening
- Episode history — each batch detects episodes independently with no continuity
- Forecast trajectory — disabled entirely
- Cross-batch sensor correlation trends
- Any information about what happened in the *gap* between scored windows

**The deepest problem:** The detector models persist, but they were trained on the *first* scored window. The detectors become anchored to whatever was happening in that initial training window. If equipment was already in mild degradation at training time, that degraded state becomes the "normal" baseline. The models adapt only if explicit quality triggers fire — and those triggers are evaluated per-batch, independently.

---

## 3. The Three Continuity Failures

### Failure 1: The Baseline Drift Problem

The training baseline is set once during coldstart and updated only when quality checks trigger a refit. The `ScoreCalibrator` anchors z-scores to training-time statistics. If the training window happened to capture a period of moderate degradation, "normal" is defined as that degraded state. A subsequent further degradation looks only mildly anomalous relative to the (already degraded) baseline.

Over months, the baseline silently shifts toward the equipment's declining state. The detectors remain calibrated to a "normal" that is no longer normal. This is baseline drift — a well-known failure mode in unsupervised anomaly detection.

The existing `ModelQualityMonitor` partially addresses this by monitoring anomaly rates and triggering refits. But it evaluates each batch independently. It cannot distinguish "the anomaly rate is high because this batch has many events" from "the anomaly rate is high because we have been in sustained anomalous operation for four months."

### Failure 2: The Gap Blindness Problem

Between scored windows, the equipment keeps running. Readings accumulate in the historian, but ACM does not score them until the next batch job runs. During that gap:

- A bearing could seize
- A maintenance event could occur and restore health
- A regime shift could happen
- A slow degradation could accelerate

When the next batch opens, ACM sees only the *result* of whatever happened — not the trajectory. Run 2's opening HealthIndex of 6.2 was preceded by Run 1's closing of 72.4. Something catastrophic happened in those 14 days. ACM had no way to flag it. The shift engineer would see the ALERT state in Run 2 and have no context for how suddenly it occurred.

A true monitoring system would detect that the projected health from batch 1's trend diverges sharply from batch 2's opening state, and raise an alert: "Unexpected deterioration in unmonitored period — inspect gap window."

### Failure 3: The Trend Amnesia Problem

Degradation in industrial equipment is almost never a single-batch event. It is a months-long process of gradually declining health punctuated by regime changes, maintenance events, and acceleration phases. Understanding whether the trend is worsening, stable, or improving requires information *across* batches.

Currently, the drift detection module (`core/drift.py`) attempts to detect trend changes within a batch. But it resets its CUSUM state at every batch boundary (a known bug, but also a fundamental architectural choice). The batch-level drift signal cannot capture a trend that is visible only when you look across six months of data.

The question "is this equipment getting worse month-over-month?" cannot be answered by any single batch's output. It requires a component that looks across batch outputs — treating each batch's summary statistics as its own data point in a longer-run time series.

---

## 4. What "True Adaptive Learning" Means Here

An unsupervised learning system that genuinely improves over time would exhibit these properties:

**Property 1: The baseline evolves correctly.** Normal behavior is tracked as a running reference that can distinguish "equipment improved after maintenance" from "detectors drifted toward a degraded state." The calibration anchors are updated when genuine improvement is confirmed, not blindly on each batch.

**Property 2: The system knows what it does not know.** Gaps in scored windows are not silently ignored. They are explicitly represented as periods of uncertainty. The system can project what *should* have happened during a gap and compare that projection to what *actually* happened when the next scored window opens.

**Property 3: The trend is a first-class signal.** Long-run trajectory — is this equipment getting worse, stable, or recovering — is computed across batches and stored as a persistent signal, not inferred anew on each batch.

**Property 4: Maintenance events are detected and their effects quantified.** A sudden positive health jump is a maintenance reset. After a maintenance event, the system should: record the event, reset its trend baseline to post-maintenance data only, and track whether the maintenance restored health to expected levels.

**Property 5: Confidence is proportional to evidence.** A model trained on 14 days of data and a model validated across 6 months of consistent scoring should express different confidence levels. The longer the consistent track record, the higher the confidence in projections.

---

## 5. The Design: Five Cross-Batch Continuity Layers

These five additions, taken together, transform ACM from a batch anomaly detector into an adaptive condition monitoring system.

---

### Layer 1 — Trend Anchor (Per-Batch Slope Persistence)

**What:** At the end of every batch, compute a Theil-Sen slope on the `HealthIndex` series for the current window and persist it alongside the last observed value and its timestamp. The next batch loads this anchor.

**Why Theil-Sen:** Median of all pairwise slopes. Maximally robust to the anomalous dips that episodic events cause within a batch. Does not require stationarity. Runs in milliseconds.

**What gets stored per equipment:**
- Last `HealthIndex` value and its historian timestamp
- Slope (health units per hour) and its 95% confidence interval
- Which regime the slope was computed in
- Confidence score (degrades with short windows, wide CI, recent regime switch)
- The run that wrote it

**What the next batch does with it:**
1. Load the anchor
2. Compute the gap between anchor's last timestamp and this batch's first timestamp
3. If the gap is larger than zero: project the expected health at batch start using the anchor slope
4. Compare projected vs. actual first value of this batch
5. The deviation is a signal:
   - Large negative deviation (worse than projected) → accelerated degradation in gap
   - Large positive deviation (better than projected) → maintenance or regime improvement in gap
   - Close to projection → trend held across gap

**This gap deviation is a new alert type that does not exist anywhere in the current system.**

---

### Layer 2 — Multi-Batch Trend Memory

**What:** Maintain a rolling history of per-batch slopes, gap deviations, and average health values. This is a time series of summary statistics, not raw sensor data. Each row is one batch's summary.

**What gets stored:**
- Batch start/end (historian timestamps)
- Average HealthIndex for the batch
- Slope for the batch
- Gap deviation from prior batch (if applicable)
- Dominant regime for the batch
- Whether a maintenance event was detected

**What this enables:**
- Long-run trend analysis: is the slope getting steeper (accelerating degradation)?
- Persistent degradation detection: how many consecutive batches has health been below a threshold?
- Maintenance effectiveness: did the post-maintenance batch recover to expected health?
- Seasonal pattern detection: does this equipment always degrade in certain operating conditions?

**This is the foundation for any meaningful long-term prognosis.** Without it, every prognostic question can only be answered within a single 13-day window.

---

### Layer 3 — Baseline Anchor Separation

**What:** Separate the "training baseline" (what the detectors were calibrated against) from the "current health reference" (what healthy operation looks like today, after N months of operation and maintenance).

Currently these are the same thing — the calibration is set during training and drifts with the equipment. This is the root cause of the baseline drift problem.

**The fix:** Maintain two distinct references per equipment:

*Training anchor* — the statistical distribution at model training time. Fixed. Used for computing anomaly scores consistently (z-scores are relative to this). Never updated automatically.

*Health reference* — the most recent confirmed-healthy period. Updated after:
- A maintenance reset is detected (positive health jump > 15%)
- The equipment returns to a high-confidence HEALTHY zone and stays there for N consecutive batches

The health reference is not used for anomaly scoring — it is used for trend direction assessment. "Is this equipment improving or degrading?" is answered relative to the health reference, not the training anchor.

**This eliminates baseline drift without destabilizing the anomaly detectors.** The detectors stay anchored to their training statistics. The trend assessment stays anchored to the most recent confirmed healthy state.

---

### Layer 4 — Maintenance Event Registry

**What:** Formally detect, record, and act on maintenance events. A maintenance event is any batch where the first `HealthIndex` value is significantly higher than would be projected from the prior batch's trend.

**Detection logic:**
- Load trend anchor from prior batch
- Project expected health at this batch's start
- If actual is > (projected + maintenance_jump_threshold), classify as maintenance event
- This is distinct from normal positive slope (gradual improvement)

**What gets recorded:** Timestamp of the detected event, estimated health before and after, which sensors showed the largest improvement, which regime the equipment entered post-maintenance.

**What changes after a maintenance event:**
- Trend anchor is reset: start computing slopes from post-maintenance data only
- Health reference is updated to post-maintenance level
- Consecutive degradation count resets
- A new "maintenance epoch" begins — performance in this epoch is tracked separately from pre-maintenance performance

**Why this matters:** Without explicit maintenance detection, a maintenance event looks like an anomalous positive jump, then the system continues computing trends from the pre-maintenance degraded baseline. The post-maintenance recovery is invisible. The system would continue to flag ALERT conditions based on pre-maintenance calibration even after a successful repair.

---

### Layer 5 — Cross-Batch Drift Resolution

**What:** Fix the drift detection module to carry its CUSUM state across batch boundaries, and feed it the multi-batch trend summary rather than (only) the within-batch score series.

**Currently broken:**
- CUSUM `sum_pos`/`sum_neg` resets to zero on every `.fit()` call
- Previous drift alert mode is not passed forward (hysteresis never fires)
- Drift mode column name mismatch between drift.py and acm_main.py

**The deeper issue beyond bugs:** Even if the bugs were fixed, single-batch CUSUM can only detect drift *within* a 13-day window. A drift that develops over six months — health declining at -0.02 units/hour across 15 consecutive batches — would never trigger single-batch CUSUM because the within-batch signal is too small.

**The fix:** Run CUSUM on the multi-batch trend summary (from Layer 2). Each batch contributes one row: its average health and its slope. CUSUM applied to this coarser time series detects sustained multi-month degradation that is invisible within any single batch.

This is a second drift signal — "fleet-level drift" vs. the existing "within-batch drift." Both are needed. The within-batch drift catches acute events. The cross-batch drift catches chronic deterioration.

---

## 6. How These Layers Interact

```
Batch N completes
│
├── Compute Theil-Sen slope on HealthIndex within batch N
├── Detect maintenance event? (compare to Layer 1 anchor)
│     YES → reset trend anchor, update health reference, log maintenance event
│     NO  → continue
├── Compute gap deviation (projected vs actual)
├── Write row to multi-batch trend summary (Layer 2)
├── Update trend anchor with batch N's slope (Layer 1)
│
├── Run cross-batch CUSUM on multi-batch summary (Layer 5)
│     STABLE → no action
│     SUSTAINED_DEGRADATION → write alert, flag for operator
│
└── Persist all to ACM_TrendAnchor + ACM_BatchSummary + ACM_MaintenanceEvents

Batch N+1 starts
│
├── Load Layer 1 anchor → compute expected health at batch start
├── If gap deviation large → write ACM_GapAlert
├── Load Layer 2 summary → compute long-run slope (OLS on last K batch slopes)
├── Long-run slope used for breach projection (not just within-batch slope)
└── Proceed with normal scoring pipeline
```

---

## 7. What Each Layer Answers

| Layer | Question answered |
|---|---|
| 1 — Trend Anchor | What was the trend at end of last batch? What happened in the gap? |
| 2 — Multi-Batch Memory | Is this equipment getting worse month over month? How many consecutive batches in degradation? |
| 3 — Baseline Separation | Are anomaly scores drifting with equipment state, or anchored to true normal? |
| 4 — Maintenance Registry | Did a repair happen? Did it restore the expected health level? |
| 5 — Cross-Batch Drift | Is there a sustained multi-month trend that no single batch can see? |

---

## 8. What This Enables That Does Not Exist Today

**Prognostic timeline across months:** "At current 6-month trend rate, health will reach WARNING zone in approximately 45 days." This requires Layer 2. No single batch can produce this.

**Gap alerts:** "In the 14-day unmonitored window before this batch, health was projected at 55 but opened at 6. Investigate gap period." This requires Layer 1. No single batch can produce this.

**Maintenance effectiveness scoring:** "Post-repair health is 71. Pre-failure health reference was 89. Repair restored 85% of healthy capacity." This requires Layers 3 and 4.

**Chronic degradation alert:** "This equipment has been in continuous ALERT for 6 consecutive batches spanning 78 days." This requires Layer 2. Current system generates per-batch alerts with no cumulative count.

**Calibration trust:** "Anomaly scores are anchored to training data from August 2022. 6 months of operation without a full refit. Confidence in baseline calibration: MODERATE." This requires Layer 3.

**Drift mode with memory:** "Equipment entered SUSTAINED_DEGRADATION mode 3 batches ago and has not recovered. This is the 4th consecutive degrading batch." This requires Layer 5.

---

## 9. What Does NOT Change

The detector ensemble (AR1, PCA, IForest, GMM, OMR) and its per-batch scoring is unchanged. It does what it does well: detect whether the current window is anomalous relative to its training baseline.

The regime clustering is unchanged. HOW the equipment operates is still captured by unsupervised regime discovery.

The episode detection within batches is unchanged. Short-duration anomalies within a batch are still detected by CUSUM.

The model lifecycle (COLDSTART/LEARNING/CONVERGED) is unchanged. Maturity still gates regime discovery and calibration confidence.

These five layers are additive, not replacements. They operate on the *outputs* of the existing pipeline, not its internals.

---

## 10. New SQL Tables Required

Five new tables, all lightweight (one row per equipment per batch or per event):

**`ACM_TrendAnchor`** — Layer 1
One row per equipment per series (HealthIndex initially; later detector z-scores).
Upserted at batch end. Contains: last value, timestamp, Theil-Sen slope, CI bounds, confidence, regime, run ID.

**`ACM_BatchSummary`** — Layer 2
One row per equipment per run. Append-only.
Contains: historian start/end, avg/min/max HealthIndex, slope, dominant regime, gap deviation, maintenance detected flag, run ID.

**`ACM_HealthReference`** — Layer 3
One row per equipment. Upserted when confirmed-healthy period is detected.
Contains: reference HealthIndex, timestamp, the run that established it, reason (maintenance / natural recovery / coldstart).

**`ACM_MaintenanceEvents`** — Layer 4
One row per detected event. Append-only.
Contains: detected timestamp, pre-event projected health, actual opening health, improvement magnitude, sensors most improved, post-event regime.

**`ACM_GapAlerts`** — Layer 1 (gap deviation signal)
One row per significant gap deviation. Append-only.
Contains: batch start time, data gap start/end, projected health, actual opening health, deviation magnitude, severity.

---

## 11. Implementation Order

**Phase 1 — Foundation (Layers 1 and 2)**
Implement `ACM_TrendAnchor` and `ACM_BatchSummary`. At batch end, compute Theil-Sen slope on `HealthIndex` and persist. At batch start, load anchor and compute gap deviation. Write gap alerts. This alone gives the system memory of the prior batch's state.

No changes to the detector pipeline. No changes to calibration. Pure addition of batch-end and batch-start hooks.

**Phase 2 — Baseline Integrity (Layer 3)**
Implement `ACM_HealthReference`. Detect confirmed-healthy periods (consecutive batches with HealthIndex > threshold and low anomaly rate). Separate training anchor from health reference in the analytics layer. This makes trend assessments trustworthy.

**Phase 3 — Maintenance Detection (Layer 4)**
Implement `ACM_MaintenanceEvents`. Detect positive health jumps at batch boundaries. Reset trend anchor post-maintenance. Begin tracking maintenance effectiveness over subsequent batches.

**Phase 4 — Cross-Batch Drift (Layer 5)**
Fix the known drift bugs (prev_alert_mode, CUSUM state reset, naming mismatch). Then extend the drift pipeline to consume `ACM_BatchSummary` as its input series in addition to within-batch scores. Two drift signals: within-batch (existing) and cross-batch (new).

**Phase 5 — Forecasting Integration**
With Layers 1-4 in place, `ACM_BatchSummary` provides a rich multi-month time series of health summaries. This is the ideal input for breach projection — compute Theil-Sen slope across the last N batch summaries, not just the current batch's within-window slope. Projections become dramatically more reliable.

---

## 12. The Relationship to the Known Drift Bugs

The four known drift bugs documented in `MEMORY.md` are symptoms of a deeper architectural issue: the drift module was designed to detect change within a single batch, but was given responsibility for a signal that spans batches. Fixing the bugs without addressing the architecture will produce a working within-batch drift signal, but still no cross-batch signal.

The correct resolution is:

1. Fix the four bugs so within-batch drift works correctly
2. Implement Layer 5 (cross-batch drift) as a separate signal fed from `ACM_BatchSummary`
3. Surface both signals distinctly in output tables and dashboards

Do not try to make a single drift signal do both jobs. They operate at different time scales and serve different purposes. Within-batch drift catches a sensor spike. Cross-batch drift catches six months of gradual machine wear.

---

## 13. Principles for Implementation

**Everything persists to SQL.** No in-memory state that lives only in a Python process. ACM runs in parallel subprocesses for multiple assets. State shared across runs must live in the database.

**Additive only.** None of these layers modify the existing detector pipeline, calibration, or episode detection. They operate on outputs. The existing pipeline behavior is invariant.

**Graceful degradation.** If the trend anchor is missing (first run, table not yet created), the batch proceeds normally with a logged warning. The new layers are optional enrichment, not hard dependencies of the core scoring pipeline.

**One row per batch per equipment.** Summary tables must not grow unbounded. Keep the last N rows (configurable, default 365 batches ≈ one year at daily frequency). Older rows archive to a separate table.

**The gap deviation is a first-class alert.** It must appear in Grafana dashboards, in `ACM_RunLogs`, and optionally trigger operator notifications. It is currently invisible and it is arguably the most actionable signal in the system.

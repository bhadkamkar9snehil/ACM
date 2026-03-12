# Major Refactor Plan

Historical reference only.

The canonical ACM system-design and delivery plan is now:

- [../ACM_MASTER_PLAN.md](../ACM_MASTER_PLAN.md)

This archived file remains for historical rationale and detailed background, not as an active planning authority.


22 Dec 2025 16:36


## Summary Task List

1. Split `acm_main.py` into explicit ONLINE (assignment-only) and OFFLINE (discovery-only) modes and ensure no regime discovery ever runs in the default online batch path.
2. Introduce `ACM_ActiveModels` and force **all** regime, threshold, and forecasting reads to go through this pointer.
3. Treat cold start explicitly as `ActiveRegimeVersion = NULL` and disable all regime-aware logic until a version exists.
4. Allow `UNKNOWN / EMERGING` regime (`RegimeLabel = -1`) and stop forced nearest-regime assignment.
5. Remove anomaly scores, health indices, residuals, and detector outputs from regime discovery feature inputs.
6. Make episode construction the only alerting primitive and eliminate point-anomaly-driven alerts.
7. Add an explicit “RUL NOT RELIABLE” outcome and prevent numeric RUL from being written when prerequisites fail.
8. Enforce strict train–score separation so a batch cannot influence its own anomaly score or health.
9. Add a single data-contract gate (timestamp order, duplicates, cadence, future rows) that blocks downstream stages on violation.
10. Promote drift and novelty signals to control-plane triggers instead of dashboard-only metrics.
11. Create `ACM_RegimeDefinitions` with versioned, write-once semantics for regime models.
12. Add `RegimeVersion` and `AssignmentConfidence` to all regime timeline writes and queries.
13. Gate all regime-conditioned thresholds and forecasting on `MaturityState == CONVERGED`.
14. Implement an offline historical replay runner that discovers regimes using accumulated history and writes a new `RegimeVersion`.
15. Persist objective regime evaluation metrics (stability, novelty rate, overlap entropy, transition entropy, consistency).
16. Add a promotion procedure that updates `ACM_ActiveModels` only if acceptance criteria are met and logs an audit trail.
17. Condition anomaly normalization and thresholds on regime context **only** when assignment confidence is sufficient.
18. Refactor ACM into explicit pipeline stages and emit per-stage timing, row counts, and feature counts.
19. Standardize feature engineering into a single canonical feature matrix consumed by all detectors.
20. Replace detector-specific normalization with a unified baseline normalization layer.
21. Convert all detectors to a strict `fit_baseline()` / `score()` API with identical output schema. 
22. Redesign fusion as a calibrated evidence combiner with explicit missingness handling.
23. Persist per-run fusion quality explaining which detectors contributed and why.
24. Redefine health as a time-evolving state with confidence, not an instantaneous score.
25. Implement explicit recovery logic (hysteresis, cooldown, decay) for health transitions.
26. Add replay reproducibility checks so identical inputs + params yield identical regime assignments.
27. Introduce an explicit baseline window policy per equipment and persist it per run.
28. Add sensor validity and plausibility checks and persist a sensor-validity mask.
29. Handle maintenance and recalibration events to reset or segment baselines.
30. Track novelty pressure independent of regimes as a first-class metric.
31. Persist drift events as objects that down-weight confidence and trigger offline replay.
32. Unify sensor attribution using frozen normalized artifacts for episode explanation.
33. Track detector correlation and flag redundant or unstable detectors automatically.
34. Enforce SQL-only persistence by removing all file-based artifact paths.
35. Harden `OutputManager` with strict schema guards and mandatory version keys.
36. Persist forecasting quality diagnostics and self-evaluation metrics on every run.
37. Add a replay-based regression harness to detect unintended behavioral changes.
38. Build a “truth dashboard” exposing invariants (data quality, drift, novelty, fusion health).
39. Introduce a compact operational decision contract (State, Confidence, Action, RULStatus).
40. Add seasonality/diurnal baseline handling where applicable.
41. Introduce asset-similarity priors for cold start with full auditability.
42. Capture operator feedback (false alarm, valid, maintenance) for objective evaluation.
43. Implement alert-fatigue controls (rate limits, escalation ladders, suppression logging).
44. Cluster episodes into recurring deviation families for pattern mining and proto-RCA.
45. Add explicit “failure mode unknown” semantics to prevent implied fault labels.
46. Introduce controlled configuration/version management for analytics experiments.
47. Enforce idempotent SQL writes and run-completeness checks.
48. Add formal model deprecation workflows with forensic comparison.
49. Introduce a unified confidence model across health, episodes, and RUL.
50. Separate analytics from decision-policy logic so operational behavior can change without re-training models.


## Purpose of this Document

This document defines the **ground truth operating model** of ACM after refactoring.

Its intent is to:

* Stop oscillation and rework
* Prevent algorithm-driven design drift
* Ensure long-term convergence and correctness
* Act as a **design constitution** for ACM

If any future change violates the rules here, the change is **wrong**, even if it improves a metric temporarily.

---

## 1. What ACM *Is* (and Is Not)

### ACM is:

A **state-consistency engine** that continuously evaluates whether an asset’s behaviour is consistent with its own historical operating envelope, under uncertainty, using only time-series data.

### ACM is not:

* A fault classifier
* A failure predictor by default
* A single-model ML system
* A system that “must always give an answer”

Accuracy is **not** ACM’s primary goal.
Correctness under uncertainty **is**.

---

## 2. The Only Questions ACM Is Allowed to Answer

ACM must answer questions **strictly in this order**:

1. **What operating context am I in (if any)?**
2. **Given that context, is behaviour statistically consistent?**
3. **Is the inconsistency persistent over time?**
4. **If persistence exists, what is the risk trajectory?**

If a stage cannot answer its question reliably, ACM must **stop progressing downstream** and explicitly return uncertainty.

Skipping or re-ordering these questions is forbidden.

---

## 3. Online vs Offline ACM (Core Mechanism)

### Online ACM

* Runs on every batch
* Must be fast, stable, deterministic
* Never rewrites historical truth
* Never creates or modifies regimes
* May operate with **no regimes**

Online ACM answers:

> “What is our current best operational belief?”

### Offline ACM

* Runs only when triggered
* Replays historical data
* Competes alternative explanations
* Creates **new versions**, never overwrites
* May invalidate old assumptions **only by promotion**

Offline ACM answers:

> “Is our current belief still the best explanation of behaviour?”

**This separation is absolute.**

---

## 4. Regimes: What They Are and What They Are Not

### Regimes ARE:

* Hypotheses about operating envelopes
* Derived from operational/context features only
* Incomplete early and convergent over time
* Versioned, auditable, confidence-scored

### Regimes ARE NOT:

* Health states
* Fault states
* Anomaly clusters
* Truth at cold start

At cold start:

* **No regimes exist**
* Online ACM must operate in a regime-agnostic mode
* Any forced clustering at this stage is incorrect by design

---

## 5. Cold Start Is a First-Class State

Cold start is not an error condition.

During cold start:

* `ActiveRegimeVersion = NULL`
* Regime-conditioned thresholds are disabled
* Regime-conditioned forecasting is disabled
* Deviation detection runs globally
* Confidence must be explicitly low

Cold start **must never be hidden**.

---

## 6. Unknown / Emerging Is a Valid Outcome

ACM must be able to say:

> “This behaviour does not belong to any known operating envelope.”

Therefore:

* `UNKNOWN / EMERGING` is a valid regime label
* Forced assignment is forbidden
* Novelty must not be silently converted into anomaly or fault

If ACM cannot say “unknown”, it is lying.

---

## 7. Deviation, Not Anomaly, Is the Primitive

ACM does not detect “anomalies” as final outputs.

It produces:

* Deviation evidence relative to context
* Aggregated across sensors and detectors
* Interpreted only after persistence

Point-wise scores are raw material, **never decisions**.

---

## 8. Episodes Are the Only Alerting Unit

Alerts, notifications, and health transitions must be driven by **episodes**, not points.

An episode must:

* Have duration
* Have integrated severity
* Have persistence
* Be explainable by contributing sensors

If something is not an episode, it is not actionable.

---

## 9. Health Is a Trajectory, Not a Number

Health represents:

* Direction (degrading / stable / recovering)
* Confidence
* Evidence accumulation

Health must not:

* Jump abruptly
* Mirror raw anomaly scores
* Be presented without confidence

A stable but “bad” asset is different from a degrading asset.

---

## 10. RUL Is Optional and Often Invalid

RUL may be computed **only if all prerequisites are met**:

* Stable regime
* Persistent degradation trend
* Sufficient data quality
* Low novelty and drift

If prerequisites are not met:

* Output **“RUL NOT RELIABLE”**
* Never force a numeric value

A wrong RUL is worse than no RUL.

---

## 11. Drift and Change Are Control Signals

Drift is not:

* A chart
* A diagnostic curiosity

Drift is:

* A signal that current assumptions are decaying
* A trigger for confidence reduction
* A trigger for offline replay

Ignoring drift guarantees long-term failure.

---

## 12. Versioning Is Mandatory Everywhere

Anything that can change must be versioned:

* Regimes
* Thresholds
* Forecast models
* Policies

Historical outputs must never be silently reinterpreted.

Truth is **time-relative** and **version-relative**.

---

## 13. Promotion Is the Only Way Truth Changes

A new model/version becomes active **only if** it demonstrably improves:

* Stability
* Coverage (less forced assignment)
* Temporal coherence

Offline discovery without promotion is experimentation.
Promotion without evidence is corruption.

---

## 14. Confidence Is a First-Class Output

Every decision must carry confidence derived from:

* Data quality
* Regime confidence (if applicable)
* Detector agreement
* Drift level
* Novelty pressure

No decision without confidence is acceptable.

---

# NON-NEGOTIABLE RULES (THE RULEBOOK)

These rules must **always** be followed during refactoring and future work.

1. Online code must never create or modify regimes
2. Offline code must never overwrite historical truth
3. No forced assignment is allowed when confidence is low
4. Cold start must be explicit and visible
5. Regime features must be operational only
6. Detector outputs must never define regimes
7. Point anomalies must never trigger alerts
8. Episodes are the only alerting primitive
9. Health must be time-based and confidence-aware
10. RUL must be gated or suppressed
11. Drift must influence control flow
12. All model changes must be versioned
13. Promotion requires objective evidence
14. UNKNOWN is a valid system output
15. SQL is the single source of truth
16. Replays must be reproducible
17. Confidence must always be exposed
18. Dashboards must reflect uncertainty, not hide it
19. No module may silently reinterpret historical data
20. If unsure, the system must say “not reliable”

---

## Final Statement

This refactor is **not about adding sophistication**.

It is about:

* Making ACM honest
* Making ACM convergent
* Making ACM governable
* Making ACM trustworthy

If this document is followed, ACM will improve slowly but **monotonically**.

If it is violated, ACM may appear smarter short-term but will **never stabilize**.

This document is the **reference truth** going forward.

# Why Multiple Detectors — And What Each One Actually Does

Date: 2026-02-21
Owner: Snehil
Status: Reference document

---

## 0. The Short Answer

No single anomaly detector can reliably detect all types of faults in a multivariate sensor system. Each detector makes a different assumption about what "normal" looks like, and therefore catches a different shape of fault. The ensemble exists because these shapes of fault are all real, and they are mutually exclusive coverage zones.

The health index is the weighted sum of their outputs — a single number that represents how many detectors are alarming simultaneously, and by how much.

---

## 1. The Coverage Problem

Sensors in industrial equipment produce multivariate time series. A fault can manifest in many different ways:

- A single sensor spikes while all others remain normal
- Multiple sensors shift in a coordinated way that has never been seen before
- The equipment shifts into a low-probability operating state (not a spike — just unusual)
- Two sensors that are normally correlated decouple (pressure rises while flow does not)
- A slow monotonic drift that is consistent within each reading but accumulates over hours

No single detector model catches all five of these. The detectors in ACM are chosen specifically because each one covers a different case.

---

## 2. What Each Detector Actually Does

### AR1 — "Did this sensor deviate from its own recent past?"

**The math:** For each sensor independently, fit an autoregressive model `x[t] = phi * x[t-1] + (1-phi)*mu`. At scoring time, predict `x[t]` from `x[t-1]` and score the residual.

**What it catches:** A single sensor that breaks from its own recent pattern. Temperature suddenly spikes. A valve position jumps. A flow reading drops unexpectedly. AR1 is the closest thing to "compare this reading to what I would have predicted."

**What it misses:** It is entirely univariate — one model per sensor, no awareness of other sensors. If bearing temperature and shaft vibration both rise together by 15% (a coordinated degradation signature), AR1 scores each sensor independently. Neither may look anomalous on its own. The fault is invisible.

**When it fails:** Near-constant sensors (flatlines, stuck readings) return zero residuals always. Also: the first data point of every batch has no prior value, so `pred[0] = x[0]`, producing a zero residual. This is the source of the fixed `ar1_z = -1.4455` spike at every batch boundary visible in Grafana — it is not a calibration artifact, it is a structural first-row artifact.

---

### PCA-SPE — "Is the equipment behaving in a way it has never behaved before?"

**The math:** Fit PCA on training data, keep the top k components (the directions of normal variation). At scoring time, project a new point onto those k components, reconstruct it, and measure the reconstruction error (Squared Prediction Error).

**What it catches:** Faults whose signature lies *outside* the subspace of normal variation. If the training data varies along 5 principal directions, SPE measures how far a new point is from that 5-dimensional surface. A fault that involves sensors moving in a direction never seen during normal operation produces high SPE even if each individual sensor reading looks plausible.

**Why this is different from AR1:** AR1 asks "is this sensor reading consistent with its own history?" SPE asks "is this combination of sensor readings consistent with the normal operating manifold?" It is sensitive to the *structure* of the multivariate distribution, not individual sensor trajectories.

**What it misses:** If a fault mode happens to align with one of the normal principal directions (for example, the equipment degrades along the same dimension it normally varies during load changes), SPE will be low. The anomaly is invisible.

**When it fails:** If the training data had very low variance (sensors barely moved during training), PCA captures a nearly degenerate subspace and SPE is artificially high for everything. Also: if the number of sensors is much larger than the number of training samples, PCA is poorly conditioned.

---

### PCA-T² — "Is the equipment at an unusual position within its normal range?"

**The math:** Same PCA model as SPE, but instead of measuring distance *from* the subspace, T² measures distance *within* the subspace from the origin (the mean operating point). Hotelling's T² statistic: sum of squared standardized latent coordinates.

**Why both SPE and T²:** They cover complementary failure regions in the PCA decomposition.
- SPE catches faults that lie *outside* the normal operating manifold entirely.
- T² catches faults that are *on* the manifold but at an extreme position within it — the equipment is operating in a legitimate direction but at an extreme point it has never reached before.

An analogy: SPE detects if a car is on a road that does not exist on the map. T² detects if the car is on a known road but 200 miles beyond where it has ever driven.

**What it misses:** Low-amplitude anomalies that stay near the center of the subspace. Gradual drift toward the edges of the training envelope may produce only slowly-rising T², easily missed by threshold-based alerting.

---

### IForest — "How easy is this point to isolate from all others?"

**The math:** Build random binary trees by repeatedly splitting feature space at random thresholds. Anomalies require fewer splits to isolate (they are in sparse regions). Score = average path length across all trees (shorter = more anomalous).

**What it catches:** Points that are genuinely outliers in the multivariate space — observations that stand apart from the density of normal operation without making any assumptions about the shape of that density. IForest does not assume Gaussianity, does not require a distance metric, and works in high dimensions.

**Why this is different from PCA and GMM:** PCA assumes normal behavior lies on a linear subspace. GMM assumes normal behavior is a mixture of Gaussians. IForest assumes nothing about the shape. It is purely data-driven. If normal operation is a twisted, non-convex cloud of points, IForest learns that cloud's sparsity structure.

**What it misses:** Collective anomalies — a coherent group of points that all shift together. If 50 data points all shift slightly in the same direction, that region is *dense*, so IForest sees it as low-anomaly. The anomaly is a pattern, not an outlier, and IForest only finds outliers.

**When it fails:** If training data contains faults (contamination), IForest learns the fault region as "not sparse" and future identical faults appear normal. This is a fundamental limitation of all unsupervised detectors trained on potentially contaminated data.

---

### GMM — "How probable is this operating state under the learned distribution?"

**The math:** Fit a Gaussian Mixture Model to training data (k=2 to 5, selected by BIC). At scoring time, compute the log-likelihood of each point under the mixture. Low log-likelihood = anomalous.

**What it catches:** Operating states that are genuinely rare under the probability distribution of healthy operation. If the equipment has two normal operating modes (low load and high load), GMM learns two Gaussians. A fault that produces a reading in the low-probability tail between those modes — or outside both — scores as anomalous.

**Why this is different from PCA:** PCA is deterministic — it defines a subspace and measures distance from it. GMM is probabilistic — it estimates the full distribution and measures likelihood. GMM can handle multi-modal normal behavior (multiple legitimate operating states) without confusing them with anomalies.

**What it misses:** Faults that happened during training become learned components. If the training window contained a 3-day degradation episode, GMM may have fit one of its Gaussians to that fault state. Future identical faults appear normal.

**When it fails:** Small training sets produce degenerate mixture estimates. High-dimensional feature spaces make likelihood estimation unreliable (curse of dimensionality). The diagonal covariance assumption ignores sensor correlations, which can produce false positives when correlated sensors move together in a healthy but unusual direction.

---

### OMR — "Are the relationships between sensors intact?"

**The math:** Fit a reconstruction model (PLS, Ridge regression, or PCA — selected by sample count) that learns how to predict each sensor from the others. At scoring time, compare predicted sensor values to actual values. Large reconstruction error = sensor relationships have broken down.

**Why this is different from everything else:** OMR explicitly models *inter-sensor dependencies*, not individual sensor distributions. It is asking: "given all other sensor readings, what should this sensor read?" If bearing temperature is normally predictable from vibration and load current, OMR learns that relationship. A fault that causes temperature to decouple from vibration and load — the signature of, say, early bearing lubrication failure — produces high OMR reconstruction error even if each individual sensor reading looks normal.

**What it catches:** Sensor relationship breaks. One sensor rising while the others predict it should be falling. Cascading faults where a primary failure causes secondary sensors to lose their normal relationship to the primary. Cross-sensor dependencies that are invisible to any univariate or density-based detector.

**What it misses:** Faults where *all* sensors move together in a consistent (but unhealthy) direction. If the entire machine slows down by 10%, all sensors shift proportionally, the relationships between them are preserved, and OMR reconstruction error is low.

---

## 3. The Coverage Map

```
FAULT TYPE                     AR1   PCA-SPE   PCA-T²   IForest   GMM   OMR
─────────────────────────────────────────────────────────────────────────────
Single sensor spike             ✓      ○         ○        ✓        ○     ○
Single sensor drift             ✓      ○         ○        ○        ○     ○
All sensors shift together      ✗      ✓         ✓        ✗        ✓     ✗
Novel multivariate combination  ✗      ✓         ○        ✓        ✓     ✗
Sensor relationship breaks      ✗      ○         ○        ○        ○     ✓
Equipment in rare density zone  ○      ✗         ✗        ✓        ✓     ✗
Extreme position on known axis  ○      ✗         ✓        ○        ✗     ○
Gradual collective degradation  ○      ✓         ✓        ✗        ✓     ✓

✓ = strong coverage
○ = partial or incidental coverage
✗ = structural blind spot
```

No single column is all ✓. No row has only one ✓. This is the argument for the ensemble.

---

## 4. How They Are Combined Into One Number

**Step 1 — Calibration:** Each detector's raw scores are mapped to a z-score using training-period statistics. The calibration is fit on the training window and never re-fit on scoring batches. This anchors the z-score scale to what "normal" looked like at training time.

**Step 2 — Weighted fusion:** The calibrated z-scores are combined as a weighted average. Default weights:

| Detector | Weight | Reason |
|---|---|---|
| PCA-SPE | 0.30 | Multivariate structure — the most general anomaly signal |
| PCA-T² | 0.20 | Complement to SPE along principal directions |
| AR1 | 0.20 | Reliable univariate baseline |
| OMR | 0.10 | Sensor relationships — unique signal not in PCA or AR1 |
| IForest | 0.15 | Non-parametric outlier signal |
| GMM | 0.05 | Lowest weight: most sensitive to training contamination |

Weights are auto-tunable via episode separability scoring — detectors that better predict which time windows correspond to known episodes get higher weights.

**Correlation discounting:** If two detectors produce highly correlated z-scores (|r| > 0.5), their combined weight is reduced. Two correlated detectors do not provide twice the evidence — they provide the same evidence twice. This discount prevents PCA-SPE and PCA-T² from jointly dominating the fused score just because they share the same PCA model.

**Step 3 — Health index:** The fused z-score is passed through a sigmoid: `health = 100 × (1 - sigmoid((|z| - threshold/2) / scale))`. This maps:
- z = 0 → health ≈ 92%
- z = 2.5 → health = 50%
- z = 5.0 → health ≈ 8%

The sigmoid is monotonic and bounded. It gives a smooth, human-readable number. A gradient-smoothed version (EMA applied before the sigmoid) captures sustained low-level anomalies that would not trigger any single-point threshold.

---

## 5. What the Ensemble Gets Right That a Single Detector Cannot

**Robustness to detector failure:** If GMM is poorly calibrated on a given equipment (training contamination, unusual operating modes), it produces noisy scores. With weight 0.05, it contributes 5% of the fused signal — its failure is contained. If that 5% weight were 100%, the health index would be unreliable.

**Fault-type coverage:** A bearing lubrication fault might not spike any individual sensor (each reading looks plausible in isolation) but will: break the temperature-vibration relationship (OMR catches it), produce an operating state the equipment has never been in before (SPE catches it), and gradually push readings toward the tail of the density (GMM catches it). Any one detector alone might miss the early signature. The ensemble is more sensitive to the combination.

**Confidence through consensus:** When all detectors alarm simultaneously, the fused z-score is high and the diagnosis is confident. When one detector alarms and the others are quiet, the fused score is moderate — a signal, but not an alert. This natural consensus filtering reduces false positives compared to any single detector with the same sensitivity.

---

## 6. What the Ensemble Gets Wrong

**Training contamination:** All detectors are unsupervised and trained on whatever data was available at coldstart. If the first 13 days of data contained a degradation episode, all detectors learn some of that degraded state as "normal." The ensemble inherits this contamination from all of its members simultaneously. The contamination filter (iterative MAD exclusion before calibration) partially mitigates this, but cannot remove it entirely.

**Correlated detectors:** PCA-SPE and PCA-T² share the same PCA model. OMR sometimes uses PCA internally. In practice, these three detectors are not independent — their scores are correlated. The correlation discounting reduces the impact, but a shared blind spot (a fault that lies along a principal direction and is well-reconstructed) is shared by all three.

**No temporal structure in most detectors:** IForest, GMM, and OMR score each time point independently with no knowledge of what came before or after. A fault that is only visible as a pattern across 20 consecutive readings — each one individually plausible, but collectively abnormal — may not be detected by these detectors. AR1 has one step of memory. Only the episode detection layer (CUSUM on fused scores) captures multi-point patterns.

**Baseline drift:** All detectors calibrate their z-scores to training-time statistics. As the equipment ages and its "normal" state slowly changes, the calibration anchor becomes stale. Gradual drift toward a new normal state will produce ever-rising z-scores even if the equipment is technically healthy relative to its current condition. This is not a bug in the individual detectors — it is a feature (it detects aging). But it means the health index degrades over time on healthy aging equipment, which can lead to false urgency.

---

## 7. The Open Question: Are Six Detectors the Right Number?

The ensemble covers the main fault families: point anomalies (AR1, IForest), subspace violations (PCA-SPE, T²), density anomalies (GMM), and relationship breaks (OMR). Adding more detectors adds complexity, training time, and potential for weight dilution without meaningfully expanding coverage.

The coverage gaps that currently exist are not addressed by adding more detectors of similar types. They are addressed by:

1. **Cross-batch continuity** — none of the six detectors can detect that health has been declining for three consecutive months. That requires the `ACM_BatchSummary` trend layer described in the continuity design.

2. **Maintenance event detection** — none of the six detectors distinguish a positive health jump (maintenance) from a temporary operating mode change. That requires the maintenance registry.

3. **Sensor relationship drift over time** — OMR detects relationship breaks within a batch. It cannot detect that the normal sensor relationships themselves have slowly shifted over six months (indicating equipment wear). That requires comparing current OMR reconstruction error characteristics to those at training time, across multiple batches.

These gaps are architectural, not detector-count problems. Six well-chosen detectors covering complementary fault families is the right design. The gaps belong to the continuity layer above them.

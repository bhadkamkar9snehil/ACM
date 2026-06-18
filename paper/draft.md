# ACM: Self-Tuning Ensemble Anomaly Detection for Industrial Assets with Contamination-Aware Calibration and Self-Distrust Gating

---

## Abstract

Industrial condition monitoring systems are deployed with zero runtime labels, on
training windows that are rarely clean, and across historians with widely different
sampling cadences — yet most published unsupervised anomaly detection methods assume
away all three of these conditions. We present ACM, a fully unsupervised, stateless
anomaly-scoring pipeline for industrial sensor time-series that combines six
complementary detectors (autoregressive, two PCA-based, isolation forest, Gaussian
mixture, and a multivariate reconstruction detector we call OMR) through
correlation-discounted weighted fusion and a set of self-tuned alarm rules. ACM makes
five deployment-driven design choices: (1) contamination-aware calibration that filters
likely-anomalous samples out of the calibration window before thresholds are derived
from it; (2) a self-distrust gate that discriminates a broken (already-faulted) training
baseline from a genuine catastrophic fault using calibrated z-score saturation, rather
than discarding both indiscriminately; (3) cadence-inferred alarm-rule horizons that
convert physical-time windows (1 hour, 24 hours, 7 days) into sample counts from the
data's own measured sampling interval, so one configuration works unmodified from 1 Hz
to hourly cadence; (4) an interleaved calibration split that scatters the held-out
calibration blocks across the entire training history rather than reserving only a
trailing window, so pre-fault degradation cannot silently bake into the "normal"
baseline; and (5) OMR's top-3-of-per-feature scoring rule, which avoids both the dilution
of an L2 norm and the calibration-crushing tail growth of a max statistic on wide sensor
sets. We evaluate ACM under a zero-per-deployment-tuning protocol: the same fixed
configuration is applied unmodified across industrial datasets regardless of sensor
count, sampling cadence, or fault type, with ablations isolating each design choice's
contribution. This paper reports results from the public CARE-to-Compare wind-turbine
SCADA benchmark (Farm A, 22 labelled events, 86 sensors; Farm C, 58 labelled events, 957
sensors); the same protocol is designed to extend to additional industrial domains as
further evaluation completes.

[RESULTS PENDING]

---

## 1. Introduction

Industrial condition monitoring is, in practice, a label-scarce problem. An operator
onboarding a new wind turbine, pump, or compressor to a monitoring system has no
catalog of past faults to train against — only a recent window of historian data and
the hope that most of it reflects healthy operation. Three properties of this setting
are routinely assumed away by published unsupervised anomaly detection methods, but
none of them can be assumed away in deployment:

1. **The training window is not guaranteed clean.** Sensors drift during commissioning;
   assets are sometimes registered into a monitoring system mid-fault; early
   degradation can be present from day one. A calibration procedure that treats the
   training window as ground-truth-normal will calibrate its threshold *to the fault*,
   not around it.
2. **The model's own baseline can be the broken part.** When degradation is present at
   registration time, every behavior rule trained on that baseline will trip
   immediately and continuously. The correct response is not "lower sensitivity" — it
   is recognizing that the alarm rule's premise (a captured *healthy* reference) failed,
   and that the rule's output is not informative until that premise is restored. Most
   ensemble anomaly detectors have no mechanism to recognize this distinction from a
   genuine, fully-developed catastrophic fault that happens to look identical at the
   level of "alarm fires from t=0."
3. **Sampling cadence is not fixed.** A SCADA historian might report 10-minute
   averages; an OPC UA feed might publish at 1 Hz; a slow batch process might log
   hourly. A detection rule defined in sample counts ("persist for 6 samples") changes
   physical meaning by three orders of magnitude depending on which of these applies,
   silently, with no error raised.

We present ACM (the name is internal/product-historical and not an acronym requiring
expansion here), a stateless scoring pipeline that takes a label-free training window
and a scoring window for one asset and returns a fused anomaly score, calibrated
per-detector z-scores, and a label-free alarm decision. ACM is built from six detectors
or "heads" — an autoregressive residual detector, PCA via squared prediction error (SPE)
and Hotelling's T², an isolation forest, a Gaussian mixture model, and a multivariate
reconstruction detector we introduce as OMR (Overall Model Residual) — fused through a
correlation-discounted weighted sum and gated by alarm rules that self-tune their own
thresholds from the asset's own history.

ACM's contribution is not a new detector architecture; AR1, PCA, isolation forest, and
GMM are standard. The contribution is the set of deployment-driven design choices around
that ensemble that address the three problems above directly:

1. **Contamination-aware calibration** (§4.5) — an iterative MAD-based filter removes
   likely-anomalous samples from the calibration window before any threshold is derived
   from it, with a hard cap on how much can be excluded (so the filter cannot itself
   become a way to silently discard real signal).
2. **A self-distrust gate that discriminates by magnitude, not just timing** (§4.7) — a
   behavior rule that fires from the very start of a scoring window and covers most of
   it is ambiguous: it is the signature of both a broken baseline *and* a genuine,
   fully-developed fault (event labels in CARE sometimes place the fault onset at the
   train/score boundary itself, i.e. zero observable lead time is possible by
   construction). The ambiguity is resolved with a magnitude criterion tied to the
   shared calibration scale's universal numerical ceiling, which a contaminated/mis-fit
   baseline rarely approaches but a genuinely catastrophic fault does.
3. **Cadence-inferred alarm-rule horizons** (§4.7) — every rule horizon is defined in
   physical time and converted to sample counts using the cadence measured directly
   from the scored data's own timestamps.
4. **An interleaved calibration split** (§4.3) — held-out calibration blocks are
   scattered across the entire training history via a fixed stride, rather than
   reserved as a single trailing window, so that slow pre-fault degradation late in
   training cannot be silently absorbed into the "normal" calibration reference.
5. **OMR's top-3 multivariate residual aggregation** (§4.4.6) — a model-agnostic
   reconstruction detector whose anomaly score is the mean of the three largest
   per-feature scaled residuals, chosen deliberately over both an L2 norm (which dilutes
   a single faulty channel by the square root of the feature count) and a max statistic
   (whose healthy tail grows with feature count, eroding calibration contrast on wide
   sensor sets).

Our evaluation protocol holds the configuration fixed and applies it unmodified across
industrial datasets of different scale and origin — zero per-asset, per-deployment
hand-tuning — and we report ablations that isolate each design choice's measured
contribution. This paper reports results from the CARE-to-Compare wind-farm benchmark
(Farm A: 86 sensors; Farm C: 957 sensors); the same protocol extends to additional
industrial domains as further evaluation completes.

[RESULTS PENDING]

---

## 2. Related Work

**Unsupervised anomaly detection for multivariate time-series.** Isolation Forest
(Liu et al., 2008) and One-Class SVM treat anomaly scoring as density/isolation
estimation in feature space; PCA-based monitoring (Hotelling's T² and squared
prediction error) is a longstanding multivariate statistical process control technique.
Autoencoder and other reconstruction-based detectors learn a compressed representation
of "normal" and score by reconstruction error. ACM uses representatives of both families
(isolation forest, PCA-SPE/T², GMM, and a reconstruction detector, OMR) as an ensemble
rather than betting on a single one — but ensembling alone is not the contribution; how
the ensemble is calibrated and gated under realistic deployment conditions is.

**Ensemble diversity.** Kuncheva and Whitaker (2003) formalize the diversity-accuracy
trade-off for classifier ensembles; ACM's fusion stage's correlation discount (§4.6) and
its statistical-diversity weighting are a direct, if informal, application of that idea
to continuous anomaly scores rather than discrete classifier votes.

**Threshold tuning without labels.** Methods such as ECOD and copula-based outlier
scoring derive thresholds from the empirical distribution of unlabeled training data,
implicitly assuming that distribution is uncontaminated. ACM's contamination-aware
calibration (§4.5) makes the contamination assumption explicit and addresses it with an
iterative robust filter rather than assuming it away.

**Industrial benchmarks.** Industrial anomaly-detection benchmarks span a range of
domains and sensor scales. CARE-to-Compare is one such public, multi-farm wind-turbine
SCADA benchmark with labelled fault events and an explicit train/test split column per
asset.

[RESULTS PENDING]

**What is not jointly addressed elsewhere.** To our knowledge, no published industrial
anomaly detection pipeline combines (a) an explicit contamination-aware calibration
step, (b) a mechanism for discriminating a broken training baseline from a genuine
catastrophic fault using calibrated-scale magnitude evidence rather than timing alone,
and (c) alarm-rule horizons that are portable across sampling cadences by construction
rather than by re-tuning. Each is individually simple; the combination is what a
real deployment needs.

---

## 3. System Architecture

Before describing each design choice in detail (§4), this section states the
architectural principles that hold the pipeline together as a system, and separates
what is a genuine contribution of this work from what is standard systems-design
practice applied to this problem.

### 3.1 A Stateless, Single-Entry Scoring Contract

ACM exposes exactly one entry point: a function that takes a label-free training window
and a scoring window of numeric sensor channels on a shared timestamp index, and returns
a fused score, six calibrated per-detector z-scores, and an alarm decision. No model
state persists between calls — every detector is refit from the training window supplied
in that call, every time.

This is a deliberate architectural choice, not a missing optimization. Industrial assets
drift continuously (seasonal load, component wear, maintenance interventions); a
stateless contract means every scored decision reflects the asset's *current* training
window, never a fitted model that has quietly gone stale relative to it. It also
collapses the usual train/serve skew in ML systems to zero by construction: the function
that runs in production and the function used for benchmark evaluation (§5) are the same
code, called the same way — there is no separate "research" implementation that could
drift from what is actually deployed.

### 3.2 Modular Detector Composition Behind a Common Calibration Contract

The six detectors (§4.4) are independent and interchangeable: each is responsible only
for producing one raw anomaly score per row from the training window it is given.
Everything downstream — calibration (§4.5), correlation-discounted fusion (§4.6), and
alarm-rule evaluation (§4.7) — operates purely on calibrated z-scores and is entirely
agnostic to which detector produced them, how many detectors are present, or what each
one's raw score scale looks like.

This composability is what makes the ablation study in §5–6 possible without any code
branching: removing a detector (or, for OMR, adding one) is a one-line configuration
change, because no other stage of the pipeline has a hardcoded dependency on any
specific detector's presence, scale, or behavior.

### 3.3 What Is Novel vs. What Is Standard Systems Design

The stateless contract and the modular detector composition above are standard
systems-design patterns (idempotent service design; a strategy-pattern ensemble), not
contributions of this paper — they are stated here because they are the structural
reason the genuine contributions below are possible to build, test, and ablate cleanly.
The contributions specific to this anomaly-detection problem are the five design choices
detailed in §4:

| Component | Status |
|---|---|
| Stateless, single-entry scoring contract | Standard practice; applied for drift-robustness and zero train/serve skew |
| Modular detector composition behind a common calibration contract | Standard practice; enables clean ablation (§5–6) |
| Contamination-aware calibration (§4.5) | Novel |
| Self-distrust gate (§4.7) | Novel |
| Cadence-inferred alarm-rule horizons (§4.7) | Novel |
| Interleaved calibration split (§4.3) | Novel |
| OMR detector and its top-3 residual aggregation (§4.4.6) | Novel |

---

## 4. Method

ACM's entry point is a single stateless function, `score_asset(train, score)`: given a
label-free training window and a scoring window of numeric sensor channels on a
shared timestamp index, it returns a fused anomaly score, six calibrated per-detector
z-scores, and a label-free alarm decision. The same code path, with the same
hyperparameters, runs in production (re-fit on every scoring tick) and in the
benchmark harness used for evaluation in §5–6 — there is no separate "research" code
path. The pipeline has seven stages, described in this section in execution order.

### 4.1 Channel Role Detection

Industrial historians frequently log pre-derived statistics (a rolling min, max, or std
of a base channel) alongside the base channel itself, under SQL/SCADA naming
conventions that are not standardized enough to detect by name. Feature-engineering a
derived channel a second time (e.g., computing a rolling std-of-std) adds redundant
dimensionality without new information and dilutes detectors that are sensitive to
feature count (notably GMM; see §4.4.5).

ACM detects derived channels by verifying numerical relationships directly on sampled
training data, not by column-name pattern matching: a candidate "max" channel must
satisfy `max >= base` at matching timestamps; a candidate "std" channel must be
non-negative and bounded relative to the base channel's own spread. Channels that pass
this verification are classified as **derived** and pass through to the feature matrix
unmodified (no rolling statistics computed on them); everything else is classified as
**primary** and is feature-engineered as described next.

### 4.2 Feature Engineering

Primary channels are expanded with a rolling window of size `w = 16` samples (Polars,
computed in float32) into the following per-channel features:

- **Rolling median and MAD** (median absolute deviation) — robust location and scale.
- **Rolling mean and std** — for comparison against the robust statistics above.
- **OLS slope** over the window, via the closed-form covariance/variance ratio on the
  window's time index — captures local trend.
- **Skewness and kurtosis**, each clipped to a bounded range (±100 and ±1000
  respectively) to prevent low-sample-count windows from producing unbounded moment
  estimates that would otherwise dominate downstream scaling.
- **Spectral band energy** — a vectorized FFT computed over the rolling window (via
  stride tricks, avoiding a Python-level loop per window), log1p-compressed, and
  aggregated into a small number of frequency bands (default edges
  `[0.0, 0.1, 0.3, 0.5]` × Nyquist). This is the only feature family that captures
  periodic/vibrational signal rather than purely statistical location/scale/shape.
- **Robust z-score** of the instantaneous value against its own rolling median/MAD
  (`(x - median) / (MAD * 1.4826)`, clipped ±100) — a per-sample novelty signal distinct
  from the window-level aggregates above.

Derived channels (§4.1) join the feature matrix unchanged, with no rolling statistics
computed. The full feature matrix is cast to float32 throughout, for both memory and
cache-line efficiency on what are often several-thousand-column matrices (Farm C: 957
raw sensors expand to roughly 2,600+ engineered columns).

**Warm-up handling.** Rolling features computed on the first `w` samples of a fresh
scoring window are degenerate (a rolling statistic over 1–2 points). ACM prepends the
tail of the training window (`min(len(train), 2w)` samples) to the scoring window before
feature engineering, then discards the prepended rows after computing features — so
every scored sample has a full rolling window of real history behind it, without
leaking any scored sample's own data into another scored sample's features.

### 4.3 Interleaved Calibration Split

A subsequent calibration stage (§4.5) needs an out-of-sample reference: detector fit
data and the data used to compute alarm thresholds must not be the same rows, or the
thresholds will be calibrated against data the detectors have already memorized.

The naive solution — reserve a trailing window of training data as the calibration
holdout — has a specific failure mode in industrial data: slow, pre-fault degradation
is, by construction, concentrated in the period immediately preceding a fault, which is
exactly the trailing edge of the training window. A trailing-window holdout would then
calibrate the "normal" threshold using exactly the samples in which the asset is
already degrading, baking the early fault into the definition of normal.

ACM instead scatters the calibration holdout across the *entire* training history. Given
a configured holdout fraction (default 0.2), it computes a stride
`s = max(2, round(1 / holdout_frac))` (default 5) and a block size

```
block = clip(len(train_features) // (s * 8), 2w, 432)
```

— adaptively sized so that even a short training history yields at least roughly 8
holdout blocks, and capped at 432 samples per block so a single block cannot dominate
the calibration reference on long histories. Row index `i` is assigned to the holdout
when `(i // block) % s == s - 1` — i.e., every `s`-th block, distributed evenly through
the whole timeline rather than concentrated at either end. Detectors (§4.4) are fit on
the remaining `~80%`; calibration (§4.5) and OMR's residual-scale recalibration
(§4.4.6) both use the held-out blocks.

### 4.4 Detector Ensemble

Six detectors ("heads") are fit on the non-holdout training rows and scored on the
scoring window, each producing one raw score per row. Every head's raw score is
calibrated independently into a z-score by the shared calibration stage (§4.5); no
detector applies its own ad hoc clipping or scaling before calibration sees it.

| Head | Signal | Why it is included |
|---|---|---|
| `ar1_z` | Univariate AR(1) residual, one channel's own short memory | Catches slow monotonic drift that multivariate detectors are not sensitive to |
| `pca_spe_z` | PCA squared prediction error (subspace residual) | Sensitive to abrupt shifts that break the learned linear correlation structure |
| `pca_t2_z` | Hotelling's T² in the PCA subspace | Captures the magnitude of deviation along the directions PCA already explains |
| `iforest_z` | Isolation depth in feature space | Density-agnostic; works on non-Gaussian, high-dimensional data without a parametric assumption |
| `gmm_z` | Negative log-likelihood under a Gaussian mixture | Density-based; sensitive to operating-regime shifts that PCA's linear model misses |
| `omr_z` | Multivariate reconstruction residual (top-3 aggregation; §4.4.6) | Captures correlated multi-sensor relationship breakdown and provides per-channel fault attribution |

No single head is sufficient on its own; each is included because it is sensitive to a
failure mode at least one of the others is not.

**4.4.1 AR1.** A per-channel order-1 autoregression with smoothing parameter
`alpha = 0.05` over a rolling window of `256` samples; raw residual z-scores are capped
at `z_cap = 8.0` before aggregation across channels (this is a detector-internal cap
applied to the per-channel residual before cross-channel aggregation, not to the head's
final calibrated output).

**4.4.2/4.4.3 PCA-SPE / PCA-T².** A single PCA fit (randomized SVD,
`n_components = 5`) on the scaled training features produces both signals: SPE is the
squared norm of the residual outside the retained `5`-dimensional subspace; T² is the
Mahalanobis-type distance within that subspace. PCA is refit from scratch on every
scoring run, consistent with the pipeline's fully stateless design.

**4.4.4 Isolation Forest.** `n_estimators = 100`, `max_samples = 2048`,
`contamination = 0.01`, with bootstrap sampling and warm-start enabled for incremental
refits when reused across consecutive ticks in production.

**4.4.5 Gaussian Mixture Model.** Components are selected by BIC search in the range
`k = 2..3`, with diagonal covariance. The feature matrix is reduced to a whitened PCA
subspace before the mixture is fit, sized adaptively from the training sample count and
the configured component budget (`d_budget = n_samples / (min_samples_per_param *
k_for_budget * 2)`, capped at `max_pca_components = 25`). A diagonal-covariance GMM
estimates two parameters (mean, variance) per feature per component, so without
dimensionality reduction the parameter count would scale directly with raw sensor count;
the PCA pre-reduction decouples GMM reliability from sensor count regardless of how many
engineered features exist. Whitening is required: an unwhitened PCA basis leaves
trailing low-variance components that are incompatible with a diagonal-covariance fit.

Ahead of PCA, the scaled feature matrix (RobustScaler, median/IQR) is clipped to
`±feature_z_clip` (default `8.0`). Columns with heavy point-mass at the median — common
for engineered slope/skew-type features during flat operation, or sparse/spiky features
that are usually exactly zero — can have a near-zero IQR even with genuine healthy
spread; dividing by a near-zero IQR amplifies ordinary variation into very large
z-magnitudes, and since PCA selects components by variance, a handful of such columns
can otherwise swallow the entire component budget with numerical noise instead of real
inter-sensor structure. The clip bounds this without altering RobustScaler's behavior
for well-behaved columns, following the same bounding idiom used elsewhere in the
pipeline (AR1's `z_cap`, the shared calibrator's hard z-clip; §4.5).

**4.4.6 OMR (Overall Model Residual).** OMR fits a single multivariate model — not one
model per sensor — on the healthy training baseline to learn the correlation structure
across all channels simultaneously. The model family is selected automatically from
data shape: PCA when the feature count exceeds the sample count; ordinary/ridge linear
regression when there are more than 1,000 samples and fewer than 20 features; PLS
regression otherwise (the default for moderate-sized, highly correlated sensor sets,
which describes most industrial assets). At inference, the fitted model reconstructs
each channel from the others, producing one residual per channel per row. Each
channel's residual is scaled by a per-feature robust location/scale pair (median, and
MAD scaled by 1.4826, floored against a minimum to avoid divide-by-near-zero on
near-constant channels).

The per-feature median/MAD/scale values are computed from an out-of-sample calibration
holdout (§4.3) rather than from the rows the model was fit on: a model is optimized to
minimize exactly the residuals it was fit against, so in-sample residual scale
understates true out-of-sample residual variance, and dividing later, genuinely
out-of-sample residuals by an understated in-sample scale would inflate every raw OMR
z-score, including on healthy data. This recalibration step runs immediately after
detector fitting and before any scoring occurs, and degrades gracefully (keeping an
in-sample estimate, never raising) if the holdout is smaller than
`max(20, 2 × n_features)` or its columns do not align with the fitted model's.

OMR's raw aggregate score reaches the shared calibration stage (§4.5) unclipped, on the
same terms as every other head — calibration and the universal hard ceiling described in
§4.5 are the only place any head's score is bounded.

The anomaly score is **the mean of the top-3 largest scaled per-feature residuals per
row** (`k = min(3, n_features)`), not a row-wise L2 norm and not the row-wise maximum.
This choice is deliberate and is justified by two specific failure modes of the more
obvious alternatives on sensor counts in the range this pipeline targets (tens to
~1,000 channels):

- An **L2 norm** dilutes a single faulty channel's contribution by the square root of
  the feature count. On Farm A's 86 sensors a bearing-temperature fault's contribution
  is divided by roughly 9×; on Farm C's 957 sensors, by roughly 31× — effectively
  invisible against the aggregate noise floor of the remaining healthy channels.
- A **maximum** is an extreme-value statistic whose own *healthy* tail grows with
  feature count (the more channels, the more likely at least one is, by chance, at an
  unusually high quantile of its own residual distribution on any given row), which
  erodes the calibration contrast between healthy and faulty rows precisely on the
  wide-sensor assets where attribution matters most.
- **Top-3** requires three channels to be simultaneously elevated. Pure measurement
  noise rarely produces that by chance, but a single physically faulty sensor channel
  reliably elevates several of its own engineered derivatives at once (median, MAD,
  mean, std, slope, skew, kurtosis, spectral bands — typically on the order of 11
  derived features per base channel), so a genuine fault on even one channel reliably
  clears the bar without requiring multiple independently faulty sensors.

A separate, unrelated-to-scoring computation on the same per-feature residuals — mapping
each elevated engineered feature back to its base channel name and ranking by mean
contribution during alarm windows — produces the "culprit channel" attribution surfaced
to operators; this is OMR's only use of per-feature granularity, not part of the OMR
score itself.

### 4.5 Contamination-Aware Calibration

Each head's raw score is converted to a calibrated z-score by a shared calibrator fit on
the out-of-sample calibration holdout (§4.3): `z = (x - median) / (MAD × 1.4826)`, with a
fallback to the standard deviation when MAD is degenerate, and a floor on the scale to
prevent z-score explosion on near-constant raw scores.

Before these statistics are computed, the calibration holdout is passed through an
**iterative MAD contamination filter** (default method): median and MAD are computed,
points beyond `z_threshold = 4.0` MAD-sigma are excluded, the median/MAD are recomputed
on the retained points, and the process repeats (up to 10 iterations, converging when
the median stops moving by more than a small tolerance). This prevents anomalous samples
that happen to fall inside the calibration holdout — degradation that survived the
interleaved split's scattering, or genuinely contaminated history — from inflating the
scale estimate used to derive the alarm threshold. Two safety bounds apply regardless of
how the iteration converges: at most 30% of the holdout may be excluded in total, and at
least 50 samples must always be retained; if either bound would be violated, the filter
falls back to keeping the points closest to the median up to the bound. Calibration is
bypassed entirely below 50 finite samples.

On the cleaned holdout, the alarm threshold is computed at a self-tuned quantile
targeting a fixed false-positive rate (`target_fp_rate = 0.001`, giving
`q ≈ 0.999`, clamped to `[0.9, 0.995]`), rather than at a fixed `q`. An adaptive z-clip
is computed once per run from the 99th percentile of each detector's *raw* training
z-scores (scaled 1.5×, capped at 50, with a floor at the configured default of 8.0) and
applied during the `transform` step; a final, unconditional hard clip to `±10.0` is then
applied after that — a dataset-independent ceiling that holds for every detector on
every asset regardless of the adaptive clip's value, and which the self-distrust gate's
magnitude criterion (§4.7) is calibrated against directly.

### 4.6 Correlation-Discounted Weighted Fusion

The six calibrated z-score streams are combined into a single fused score by a weighted
sum, normalized over whichever heads are actually present for a given asset (a head can
be absent if its detector failed to fit, e.g. too few samples for OMR's
`min_samples = 100`). Default weights — `pca_spe_z = 0.30`, `ar1_z = pca_t2_z = 0.20`,
`iforest_z = 0.15`, `omr_z = 0.10`, `gmm_z = 0.05` — reflect each head's general
reliability across the validated benchmark assets, and are adjusted in two ways before
the weighted sum is computed.

**Correlation discount.** Pairwise Spearman correlation is computed between every pair
of present heads' calibrated streams. A pair with `|r| > 0.5` contributes to a
per-detector running average; a detector's final weight is discounted by
`min(0.3, (avg_corr − 0.5) × 0.5)` — e.g., a detector whose average correlation with
others is 0.8 has its weight cut by 15%, capped at 30% regardless of how high the
correlation runs — preventing near-duplicate signal from being double-counted simply
because two heads happen to respond to the same underlying physics. As a stronger,
discrete case of the same idea: if GMM's or Isolation Forest's correlation with OMR
specifically reaches `0.95` or higher, that head's weight is set fully to zero rather
than merely discounted — OMR is judged to already capture that signal entirely.

**Weight auto-tuning.** A separate stage adjusts the *base* weights themselves
(before the per-run correlation discount above) toward whichever detectors best separate
genuine anomalies from normal operation, using an exponential moving average at
`learning_rate = 0.3` with each detector's per-run drift clamped to `±20%` and a floor
of `min_weight = 0.05`. Each detector is scored either by an episode-separability metric
(PR-AUC, or Youden's J when label imbalance prevents that, against externally supplied
positive/negative episode labels when available) or, in the absence of such labels, by a
label-free `statistical_diversity` score combining three properties: robust signal
variance (normalized by MAD), a diversity bonus (`1 − mean |correlation|` with the other
present detectors), and tail sensitivity (the ratio of the 95th to 50th percentile of
absolute score, capped) — combined as `0.4 × variance + 0.4 × diversity + 0.2 × tail`. A
`require_external_labels` guard governs which of the two scoring methods is active for a
given run, preventing the degenerate case of tuning weights toward whichever detector
spiked on the *current* run's own fused output — a feedback loop that would overfit to
one fault signature and starve the weights available to detect the next, different one.

### 4.7 Alarm Rules and the Self-Distrust Gate

Four label-free rules are combined by OR; any rule firing constitutes an alarm.

- **Sustained.** The fused score holds at or above a self-tuned threshold for longer
  than the healthy training history's own longest such excursion (scaled by a 1.5×
  safety margin), for a minimum of `persist_floor` samples. The threshold itself is the
  lowest holdout quantile (tried in increasing order: 0.98, 0.99, 0.995, 0.999) whose
  implied persistence requirement stays within a physically sensible cap.
- **Rate.** The trailing 24-hour fraction of samples with fused score above a fixed,
  calibration-scale-anchored "clearly elevated" level (`z = 3.0`) is compared against
  1.5× the worst such fraction ever observed in training, plus an additive 5-percentage-point
  margin (the additive term gives headroom when the healthy base rate is itself
  small — a multiplicative margin alone gives almost no headroom on a 4% base rate).
  Active only when at least 500 finite training samples are available to estimate the
  baseline rate reliably.
- **Per-head.** Each of the six detector heads runs its own version of the rate rule
  independently, over a 7-day trailing window, with the same self-tuned multiplicative +
  additive threshold logic and the same 500-sample minimum to arm. This catches faults
  that live primarily in one detector's signal and would be diluted by the fused score's
  weighted average.
- **Availability.** A continuous run of non-operating SCADA status beyond a self-tuned
  floor (default 48 hours, raised to 1.5× the 95th percentile of the asset's own
  historical stop durations when at least 20 stops are observable) is itself treated as
  the symptom — a parked, failed asset produces no anomalous *sensor* signal to detect.

**Cadence portability.** All four horizons above are specified in physical time
(1 hour persistence floor, 24-hour rate window, 7-day per-head window, 48-hour
availability floor) and converted to sample counts at runtime using the cadence measured
directly from the scored window's own timestamps (the median of consecutive timestamp
differences). The same configuration therefore produces the same physical-time behavior
whether the underlying historian samples once a second or once an hour, with no
per-deployment retuning. Horizons longer than the scored window itself are capped to a
quarter or a third of the window length respectively (for the rate and per-head
windows) so the rules remain evaluable on short windows; the 1-hour persistence floor —
the system's declared minimum detection latency for a developing fault — is never
weakened by this capping.

**Self-distrust gate.** A rule's score-side mask that fires from very near the start of
the scoring window (within 5% of its length) and covers more than half the window is
ambiguous on its own: it is the signature both of a broken training baseline (the
asset's training data already contained the fault the rule is now flagging, so every
threshold derived from it is meaningless) and of a genuine, fully-developed catastrophic
fault that was already underway when scoring began — CARE's own event labels sometimes
place the labelled fault onset exactly at the train/score boundary, making zero
observable lead time possible by construction, not a labeling error.

The gate resolves the ambiguity using **magnitude**, not timing alone: the shared
calibrator's universal hard clip at `z = ±10.0` (§4.5) is, in practice, always the
binding ceiling for every detector on every asset (the adaptive self-tuned clip is
always looser than 10.0 by construction). A contaminated or mis-fit baseline drifts only
moderately past its own derived threshold — it takes the 1.5× safety margin just to fire
at all — and so its z-scores rarely approach that universal ceiling. A genuine
catastrophic fault, by contrast, tends to overwhelm the model's learned relationships
entirely, pegging its z-scores near the ceiling. The gate therefore only discards an
ambiguous-by-timing rule firing when the magnitude evidence *inside that firing region*
is also mild: fewer than 20% of the masked samples reaching `z ≥ 9.0` (90% of the
universal ceiling). The gate is evaluated independently per rule and, for the per-head
rule, independently per head, so one head's genuine saturation does not rescue another
head whose own firing pattern still looks like a broken baseline.

---

## 5. Experimental Setup

**Datasets.** This paper reports results on CARE-to-Compare, a public wind-turbine SCADA
benchmark (Zenodo record 15846963) with per-event labelled fault windows and an explicit
`train_test` split column per timestamp, evaluated on Farm A (22 labelled events, 86
sensor channels) and Farm C (58 labelled events: 31 normal, 27 anomaly; 957 sensor
channels) — chosen to stress-test the same fixed configuration across an
order-of-magnitude difference in sensor count. Farm B is present in the dataset but not
evaluated in this work. The same zero-tuning protocol is designed to extend to
additional industrial datasets beyond CARE-to-Compare as evaluation continues.

**Protocol.** `score_asset()` (§4) is called once per labelled event with that event's
own train/score split (defined by CARE's `train_test` column), under one fixed
configuration (`core/ml_defaults.py`) used identically across both farms — no per-farm
or per-event hyperparameter adjustment. Labels are used only at evaluation time, never
during fitting, calibration, fusion, or alarm-rule self-tuning.

**Metrics.** Event-level precision, recall, and F1 (an event counts as detected if any
alarm falls inside its labelled window, allowing for the lead-time analysis below);
median lead time (hours between first alarm and labelled fault onset, for detected
events); false-alarm rate on labelled-normal events. The product KPI bar is
`recall ≥ 0.80` and `F1 ≥ 0.75`.

**Ablations.** Five configurations isolate each design choice's contribution by
disabling it via the pipeline's config-override mechanism (`--override`, JSON-deep-merged
onto the default config; no code branches needed): the full system; the contamination
filter disabled; the self-distrust gate disabled (`distrust_coverage` raised to an
unreachable `2.0`); fixed equal fusion weights with auto-tuning off; and OMR disabled
entirely. Each detector head's enabled flag is independently controllable through
`cfg["models"][<name>]["enabled"]`.

**Compute.** All experiments run single-machine, CPU-only, with `OMP_NUM_THREADS=1`
(and the equivalent BLAS/MKL/NumExpr variables) set before any NumPy/process-pool import.

---

## 6. Results

### 6.1 CARE-to-Compare: Farm A

[RESULTS PENDING]

### 6.2 CARE-to-Compare: Farm C

[RESULTS PENDING]

### 6.3 Ablations (CARE-to-Compare, Farm A)

[RESULTS PENDING]

### 6.4 Figures

[FIGURES PENDING]

---

## 7. Discussion

[RESULTS PENDING]

---

## 8. Limitations

- The maturation gate requires roughly 14 days of accumulated history before an asset
  scores at all (or an explicit fast-track override); OMR requires at least 100 training
  samples to fit. Neither applies to the CARE benchmark (each event ships its own
  sufficient history) but both apply in production.
- Farm B is unevaluated. Generality claims within CARE-to-Compare rest on two farms
  differing by sensor count, not a third independent farm.
- OMR's top-3 choice (§4.4.6) is justified by failure-mode reasoning (L2 dilution, max
  tail growth).
- The self-distrust gate's constants (`distrust_coverage = 0.5`, `SATURATION_Z = 9.0`,
  `SATURATION_FRAC_FLOOR = 0.2`) are fixed, dataset-independent values tied to the shared
  calibrator's universal z-clip ceiling rather than to any per-farm statistic.
- This paper's reported results are limited to CARE-to-Compare. The zero-tuning
  evaluation protocol described in §5 is designed to extend to additional industrial
  domains spanning different sensor scales, sampling cadences, and fault types; broader
  cross-domain evidence is part of the validation methodology going forward.

---

## 9. Conclusion

[RESULTS PENDING]

---

## References

- Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2008). Isolation Forest.
- Kuncheva, L. I., & Whitaker, C. J. (2003). Measures of Diversity in Classifier
  Ensembles and Their Relationship with the Ensemble Accuracy.
- Hotelling, H. (1947). Multivariate Quality Control (T² statistic).
- Leys, C., Ley, C., Klein, O., Bernard, P., & Licata, L. (2013). Detecting outliers: Do
  not use standard deviation around the mean, use absolute deviation around the median.
- Wold, S. (1985). Partial Least Squares regression.
- Tipping, M. E., & Bishop, C. M. (1999). Mixtures of Probabilistic Principal Component
  Analyzers.
- CARE-to-Compare dataset (Zenodo record 15846963). [Full citation TBD.]

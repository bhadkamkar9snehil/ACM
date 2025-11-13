# ACM V8 — Analytical Backbone (Master)

**Revision:** October 27, 2025
**Audience:** Analytics, Data, and Platform engineers; reviewers and stakeholders
**Scope:** A single canonical document that (a) captures the **current tactical snapshot** (file-mode, CSV I/O) and (b) anchors the **strategic end-state**: an **unguided, asset-agnostic, self-regulating, self-tuning ACM** operating in SQL + streaming modes with autonomous learning loops.
**Status TL;DR:** File-mode is validated and producing actionable artifacts; SQL + streaming are designed here and will be delivered incrementally. No unit-tests by directive; manual verification checklists included.

---

## 0) Why this backbone exists

* To **unify** implementation details with the **end goal**, avoiding drift between code, docs, and vision.
* To **operationalize autonomy**: thresholds adapt, regimes re-learn, detectors re-weight, and retrains trigger **without human labels**.
* To provide one **source-of-truth** for developers and reviewers across code modules, SQL contracts, artifacts, and runtime behavior.

---

## 1) Vision & Design Principles

### 1.1 End-state (what “good” looks like)

An **unguided, asset-agnostic ACM** that:

* **Learns from cold-start** using historian slices and asset metadata (no labels).
* **Streams** fused health scores in near-real-time; **stores** full timelines and episodes in SQL.
* **Self-tunes** its calibration, thresholds, and regime cut-points using drift signals, backtests, and synthetic fault injection.
* **Explains itself** (culprits, regimes, change-points, detector attributions) for operators and engineers.
* **Scales** to thousands of assets with minimal per-asset configuration (asset-agnostic).
* **Survives data reality**: missingness, cadence drift, junk timestamps, ill-conditioned covariance, regime flips.

### 1.2 Core principles

* **File ↔ SQL parity**: identical analytics, only I/O abstraction changes.
* **Polars-first performance** with safe pandas fallback.
* **Detectors ensemble** with **robust fusion** (weights, clipping, hysteresis).
* **No labels**: evaluate via **synthetic injections**, **backtests**, **stability envelopes**.
* **Idempotence**: same inputs ⇒ same outputs, hashes on features/models.
* **Explainability over accuracy** where trade-offs arise.

---

## 2) Current Tactical Snapshot (File-mode reality)

**Validated on FD_FAN scenario** (example evidence in artifacts):

* **Train/Score processed**: 6,741 test rows; **4 regimes** detected.
* **Z-clip saturation**: ~25–26% of PCA outputs hit clip (z=8.0) → calibration tightening required.
* **Episode structure**: single 55-day contiguous episode observed → threshold review needed.

**Working modules**:

* `core/data_io.py`: CSV ingest; mixed timestamp parsing; UTC normalization; numeric intersection (train ∩ score); cadence check; fill-ratio guard.
* `core/fast_features.py`: rolling median/MAD/mean/std/skew/kurtosis/OLS-slope; FFT energy buckets; robust z per tag; **Polars-first**; perf instrumentation (`utils.timer`).
* **Detectors** (ensemble):

  * `models/forecast.AR1Detector` ✅ z of residuals per tag; fuseable.
  * `core/correlation.PCASubspaceDetector` ✅ SPE + Hotelling T² with clipping/regularization.
  * `core/outliers.IsolationForestDetector` ✅ median-imputed numeric; warm-start toggles.
  * `core/outliers.GMMDetector` ✅ BIC-auto-k; covariance fallbacks; toggleable.
  * `core/correlation.MahalanobisDetector` ✅ ridge-regularized Σ⁻¹.
  * `core/river_models.RiverTAD` ⏳ stub (future online learning).
* `core/fuse.py`: calibration to robust z (FPR-target), weighted fusion, hysteresis episode detection, culprit attribution (PCA residuals + AR1 z).
* `core/drift.py`: CUSUM on fused score (raw + z).
* `core/regimes.py`: PCA basis + MiniBatchKMeans; persisted `RegimeModel` with health labels (healthy/suspect/critical).
* Outputs: `scores.csv`, `episodes.csv`, `drift.csv`, `fusion.json`, `culprits.jsonl`, `tables/regime_summary.csv`, `models/regime_model.json`.
* **Model cache**: optional `detectors.joblib` keyed by feature hash & columns.

> **Limitations discovered**: `_resample` referencing `cfg` global; missing `Mapping` import; z-clip saturation; regime labeling needs quality gates; reporting is staging (not production).

### 2.1 Non-SQL Completion Checklist (Blocking Items)

| Capability bucket | Status | What remains | Doc pointer |
| ----------------- | ------ | ------------ | ----------- |
| Calibration self-tuning & clip governance | 🚧 In progress | Implement tail-mass monitoring loop and auto-adjust clip/scale per Section 8.1 | §8.1 |
| Regime quality gates & smoothing | 🚧 In progress | Enforce silhouette/size thresholds, dwell smoothing, persist metrics | §7.2 |
| Episode threshold backtests | ⛔ Not started | Build synthetic evaluation harness to tune hysteresis hi/lo per asset class | §8.2 / §9 |
| Autonomy triggers (drift, saturation, regime decay) | 🚧 In progress | Wire drift/calibration monitors to refit scheduler; persist run metadata | §8.5 |
| Synthetic injection + backtest harness | ⛔ Not started | Implement injection library, latency/FPR scoring, parameter sweeps | §9 |
| Fusion weight auto-fit | ⛔ Not started | Solve constrained weight optimization from backtests; persist per asset | §8.4 |
| Streaming & River online detectors | 🚧 In progress | Service loop, state persistence, River integration minus SQL wiring | §10.3 |
| Operator-grade reporting parity | 🚧 In progress | Promote staging charts/tables to operator-ready outputs; align with change log | §12 / §13 |

---

## 3) Data Contract (File vs SQL)

### 3.1 Logical tables (common schema expectations)

* **SignalsTS** (train/score windows)

  * `Timestamp (UTC)`, `EquipId`, `<Tag...>` numeric columns
  * Constraints: strictly increasing timestamps post-resample; per-window fixed cadence; fill-ratio ≤ configured cap.
* **ScoresTS** (detector + fused outputs)

  * `Timestamp`, `EquipId`, `<detector>_z` columns, `fused_z`, `fused_raw`, `active_episode_id (nullable)`
* **Episodes**

  * `EpisodeId`, `EquipId`, `StartTs`, `EndTs`, `PeakZ`, `MeanZ`, `Duration`, `RegimeAtOnset`, `Notes`
* **DriftTS**

  * `Timestamp`, `EquipId`, `cusum_raw`, `cusum_z`
* **Culprits** (jsonl or SQL TVP)

  * `Timestamp`, `EquipId`, `TopTags` (array/dict of tag→score), `Method` (PCA_resid+AR1)

### 3.2 File-mode mapping

* CSV/JSON in `artifacts/<EQUIP>/run_YYYYMMDD_HHMMSS/…`

### 3.3 SQL-mode mapping (end-state)

* **TVP-based writers** to SQL Server stored procs:

  * `usp_Write_ScoresTS(@ScoresTVP)`
  * `usp_Write_Episodes(@EpisodesTVP)`
  * `usp_Write_DriftTS(@DriftTVP)`
  * `usp_Write_Culprits(@CulpritsTVP)`
* **Readers**:

  * `usp_Read_SignalsTS(@EquipId, @TrainFrom, @TrainTo, @ScoreFrom, @ScoreTo, @MinCadenceMs)`
* **Metadata**: `ModelRegistry` (hashes, params), `RunLog` (start/end, status, ErrorJSON).

---

## 4) Feature Engineering

### 4.1 Time-domain

* Rolling **median/MAD** (robust), mean/std, **skew/kurtosis**, **OLS slope** (local trend), **z-scoring** per tag.
* **Cadence enforcement**: resample to nearest allowed cadence; fill small gaps (ffill/bfill/interp) to capped ratio; explode guard on large gaps.

### 4.2 Frequency-domain

* FFT energy in configurable bands (or Goertzel for short windows).
* **Stability**: guard on NaN/Inf; clip extreme energy outliers pre-detectors.

### 4.3 Implementation notes

* **Polars** windows with explicit dtype; pandas fallback ensures identical semantics.
* **Memory**: chunk processing per asset when window × sensors is large.
* **Perf hooks**: `utils.timer` stamps phase times to `fusion.json`.

---

## 5) Detector Heads (Ensemble)

| Module                | Purpose                         | Inputs                      | Robustness/Notes                                        | Status           |
| --------------------- | ------------------------------- | --------------------------- | ------------------------------------------------------- | ---------------- |
| AR1Detector           | Residual anomalies per tag      | De-trended tag series       | Absolute residual z; fuse via mean/median/p95           | ✅                |
| PCA Subspace (SPE/T²) | Multivariate subspace residuals | Standardized feature matrix | Ridge for ill-conditioned Σ; **clip z**                 | ✅ (z-clip heavy) |
| Isolation Forest      | Density outliers                | Median-imputed matrix       | Warm-start & bootstrap flags; stable on skewed tags     | ✅                |
| GMM (auto-k)          | Multi-modal behavior            | Normalized matrix           | BIC grid; fallback to diagonal cov; guard singularities | ✅                |
| Mahalanobis           | Correlation-break detection     | Cov-regularized matrix      | λ-ridge on Σ; monitor condition number                  | ✅                |
| River TAD             | Online anomaly pipeline         | Streaming features          | Requires persistence & service mode                     | ⏳ (planned)      |

**Calibration:** Each head → **robust z** via MAD/quantile calibration; target **FPR** drives clip and scaling. Persist **calibration state** per asset.

---

## 6) Fusion, Episodes, Culprits

### 6.1 Fusion

* **Weighted** aggregation of detector z’s: `fused_raw = Σ w_i * z_i` → **calibrated fused_z** to target FPR.
* **Weights** supplied via config (per asset / class) or **auto-learned** from backtests (end-state).
* **Expose** `effective_weights` in `fusion.json`.

### 6.2 Episode detection

* **Hysteresis:** `hi_z` to enter, `lo_z` to exit;
* **Gap merge:** fuse gaps ≤ `gap_max`;
* **Min length** filter.
* Label **episode_id** across `scores.csv`.

### 6.3 Culprit attribution

* For timestamps in/near episodes:

  * Rank tags by **PCA residual contributions** and **AR1 z**; merge ranks.
  * Emit top-k with scores in `culprits.jsonl`.

---

## 7) Drift & Regimes

### 7.1 Drift (`core/drift.py`)

* **CUSUM** on `fused_raw` (or `fused_z`) with config’d slack; produce `cusum_raw`, `cusum_z`.
* **Usage:** observability & **retrain trigger** candidate when exceeding threshold or persistence.

### 7.2 Regimes (`core/regimes.py`)

* **Compact basis**: top PCA scores (+ optional raw tags).
* **Clustering**: MiniBatchKMeans with auto-k sweep (silhouette/DB indices).
* **Labels**: assign **healthy/suspect/critical** via regime medians of `fused_z` and tag stability.
* **Persistence**: `models/regime_model.json` with cluster centers, basis, quality metrics.
* **Transitions**: optional smoothing to reduce flapping on noisy assets.

**Next:** introduce **quality gates** (min cluster size, separation) and fallback to `k=2` when metrics weak; per-regime **thresholds**.

---

## 8) Autonomy Loops (Self-tuning without labels)

### 8.1 Calibration self-tuning

* Track **z-clip saturation** and **tail mass**; adjust clip & scale to hit target FPR window-wise.
* Store **calibration drifts**; if unstable → trigger **re-fit**.

### 8.2 Threshold adaptation

* Optimize `hi/lo` hysteresis per asset via **synthetic injection** backtests (Section 9) to achieve target **latency** and **false alarms**.

### 8.3 Regime re-learning

* Periodically recompute basis & clusters when **drift** exceeds guard or when **stability envelope** violated.

### 8.4 Fusion weight re-estimation

* Use backtests to solve small **convex weight fit** that minimizes detection loss under constraints (non-negativity, sum-to-1, head caps).

### 8.5 Retrain triggers (no labels)

* If **CUSUM** persists above threshold for `T_persist`
* If **calibration drift** large for `N` consecutive windows
* If **regime separability** degrades below floor
* If **episode load** exceeds historical envelope (rate, duration)

> These feed a **scheduler** (SQL Agent / service) to queue re-fit on next maintenance window.

---

## 9) Evaluation without Labels

### 9.1 Synthetic Fault Injection Engine

* Injection types per tag/class: **steps, ramps, spikes, variance bursts, stuck-at, drift**.
* Multi-tag **correlation breaks** (simulate process decoupling).
* Control **severity**, **duration**, and **regime context**.

### 9.2 Backtest harness

* Run injections across historical windows; compute:

  * **Detection latency** (first `fused_z > hi_z`),
  * **False-positive rate** on clean stretches,
  * **Episode stitching quality** (over/under segmentation),
  * **Culprit precision** (does top-k include injected tags?).
* Sweep **fusion weights**, **thresholds**, **calibration** to near-Pareto optimal settings per asset class.

---

## 10) SQL & Streaming Architecture (End-state)

### 10.1 Storage abstraction

* `storage_backend: file|sql` in config;
* `SqlClient` provides readers/writers using TVPs and stored procs above.
* **Run lifecycle** writes to `RunLog` with `OK/ERROR` and `ErrorJSON`.

### 10.2 Streaming

* **Service mode** (Windows service / container):

  * Poll historian or consume Kafka topic;
  * **Micro-batch** windows for feature calc;
  * Maintain **River** state (online normalization, drift/adapt);
  * Periodically flush **ScoresTS/Drift/Episodes** to SQL.

### 10.3 Persistence

* Persist **detector fits**, **PCA basis**, **calibrations**, **fusion weights**, **regime model** per `EquipId` and feature-hash.

---

## 11) Config Surfaces (YAML)

```yaml
runtime:
  storage_backend: file        # file | sql
  mode: batch                  # batch | service
  reuse_model_fit: true
  tick_minutes: 5              # service mode micro-batch

data:
  cadence_ms: 60000
  max_fill_ratio: 0.05
  resample_method: median      # median | mean
  explode_guard: true

features:
  windows:
    - { name: medmad_15m, len: "15min", funcs: ["median","mad","slope"] }
    - { name: stats_60m,   len: "60min", funcs: ["mean","std","skew","kurt"] }
  fft:
    bands: [[0.0,0.01],[0.01,0.05],[0.05,0.5]]

detectors:
  ar1:   { enabled: true }
  pca:   { enabled: true, max_components: 8, ridge: 1e-4, z_clip: 8.0 }
  ifor:  { enabled: true, n_estimators: 200, warm_start: true }
  gmm:   { enabled: true, k_min: 1, k_max: 5, cov: "full", bic: true }
  maha:  { enabled: true, ridge: 1e-3 }

calibration:
  target_fpr: 0.01
  method: robust_mad
  clip_policy: soft               # soft | hard
  monitor_tail_mass: true

fusion:
  weights: { ar1: 0.25, pca: 0.35, ifor: 0.15, gmm: 0.10, maha: 0.15 }
  hysteresis: { hi_z: 4.0, lo_z: 2.5, gap_max_min: 60, min_len_min: 120 }

drift:
  cusum:
    k: 0.5
    h: 5.0
    use_fused_raw: true

regimes:
  k_auto: { k_min: 2, k_max: 6 }
  quality_gates: { min_size: 0.1, min_sep: 0.15 }
  smoothing: { enabled: true, half_life_points: 5 }
```

---

## 12) Operator-grade Explainability

* **Culprit bars**: top contributing tags for each episode/timepoint with z-scores.
* **Regime map**: scatter in PCA plane with cluster colors; timeline of regime transitions.
* **Fusion breakdown**: stacked contribution of each detector to `fused_raw`.
* **Drift ribbon**: cusum trajectory with trigger markers.
* **Anomaly “story”**: who/when/why with links to raw tags and comparable historical regimes.

---

## 13) Reporting & Artifacts (File-mode today, SQL dashboards tomorrow)

* **Today (file)**:

  * `scores.csv`, `episodes.csv`, `drift.csv`, `fusion.json`, `culprits.jsonl`, `tables/regime_summary.csv`, `models/regime_model.json`.
  * Staging HTML charts for reference (not production dashboards).
* **Tomorrow (SQL)**:

  * Grafana/BI dashboards reading **ScoresTS/Drift/Episodes**; drill-downs to culprits, regimes; export PDFs via existing n8n pipeline.

---

## 14) Risks & Mitigations

| Risk                       | Symptom                     | Mitigation                                                          |
| -------------------------- | --------------------------- | ------------------------------------------------------------------- |
| Z-clip overuse             | 20–30% head outputs at clip | Tail-mass monitoring → auto scale/clip re-tune; per-asset clip caps |
| Ill-conditioned covariance | PCA/T² unstable             | Ridge regularization; component cap; tag pruning                    |
| Regime over-fragmentation  | Too many micro-clusters     | Quality gates; min cluster size; smoothing                          |
| False long episodes        | Episodes spanning weeks     | Threshold backtests; hysteresis tuning; per-regime thresholds       |
| Data path hiccups          | NaNs, future timestamps     | Strict ingest guards; junk date clipping; fill-ratio caps           |

---

## 15) Roadmap (from now to end-state)

### 15.1 Hardening (immediate)

1. **Fix `_resample`** to pass `max_fill_ratio` explicitly (no globals).
2. **Add `Mapping` import** and strengthen type hints in `core/fuse.py`.
3. **Calibration self-tuning**: monitor z-tail; auto-adjust clip/scale to target FPR.
4. **Regime quality gates & smoothing**; persist metrics in model bundle.
5. **Episode thresholds**: backtest-driven hi/lo per asset class.

### 15.2 SQL Parity

6. Implement `SqlClient` with **TVPs** & writers/readers; finalize stored procs.
7. Mirror artifacts to **SQL tables**; wire `RunLog` finalize-on-error in `finally`.
8. Persist **ModelRegistry** (hashes, params, fits, calibration, fusion weights).

### 15.3 Streaming & Online Learning

9. **Service mode**: micro-batch tick loop; **River** normalization & online detectors.
10. **Retrain scheduler**: triggers from drift/calibration/regime metrics.

### 15.4 Evaluation & Auto-tuning

11. **Synthetic injector & backtest harness**; automated sweeps for fusion & thresholds.
12. **Autonomous weight fit** under constraints; save to ModelRegistry.

### 15.5 Visualization

13. **Operator dashboards** over SQL; export jobs via n8n; story views for episodes.

---

## 16) Ownership & RACI

| Component                                                  | Owner          | R/A/C/I            |
| ---------------------------------------------------------- | -------------- | ------------------ |
| `core/acm_main.py`                                         | Analytics Eng. | A/R                |
| `core/data_io.py`                                          | Data Eng.      | A/R                |
| `core/fast_features.py`                                    | Analytics Eng. | A/R                |
| Detectors (`forecast.py`, `correlation.py`, `outliers.py`) | Analytics Eng. | A/R                |
| `core/fuse.py`                                             | Analytics Eng. | A/R                |
| `core/drift.py`                                            | Analytics Eng. | A/R                |
| `core/regimes.py`                                          | Analytics Eng. | A/R                |
| `core/river_models.py`                                     | Analytics Eng. | R (C: Platform)    |
| SQL client & procs                                         | Data Eng.      | A/R (C: Analytics) |
| Reporting & dashboards                                     | Analytics Eng. | A/R (C: Data)      |

---

## 17) Manual Verification Checklist (no tests by directive)

1. Run `python -m core.acm_main --equip <EQUIP> --artifact-root artifacts --config configs\config.yaml --mode batch --enable-report`.
2. Confirm artifacts: `scores.csv`, `episodes.csv`, `drift.csv`, `fusion.json`, `culprits.jsonl`, `tables/regime_summary.csv`, `models/regime_model.json`.
3. Inspect `scores.csv`: detector `*_z`, `fused_z`, `active_episode_id` consistency (no NaNs, monotonic TS).
4. Check `fusion.json`: per-phase timings; `effective_weights`; calibration stats; z-tail mass.
5. Review `episodes.csv`: hysteresis coherence (no micro-flicker unless configured).
6. Open staging charts: fused timeline, culprits bar, regime map; sanity-check shapes.
7. If Polars present, verify timer logs show Polars path; else pandas fallback OK.
8. Record any anomalies/regressions into backlog with artifact references.

---

## 18) Mermaid Views

### 18.1 Analytics flow

```mermaid
flowchart TD
    A[Train CSV] -->|load_data| B[Clean & Align]
    A2[Score CSV] -->|load_data| B
    B --> C[Feature Builder\n(core/fast_features.py)]
    C --> D1[AR1]
    C --> D2[PCA SPE/T²]
    C --> D3[Isolation Forest]
    C --> D4[GMM]
    C --> D5[Mahalanobis]
    D1 & D2 & D3 & D4 & D5 --> E[Fuse & Calibrate\n(core/fuse.py)]
    E --> F[Episode Detection]
    E --> H[Drift CUSUM]
    F --> G1[scores.csv / ScoresTS]
    F --> G2[episodes.csv / Episodes]
    H --> G3[drift.csv / DriftTS]
    F --> I[culprits.jsonl / Culprits]
    G1 & G2 & G3 & I --> J[Staging Charts / SQL Dashboards]
```

### 18.2 Autonomy loop

```mermaid
flowchart LR
    S[Scores & Artifacts] --> M[Monitor tails, drift, regimes]
    M -->|violations| T[Trigger re-fit/recalibration]
    T --> R[Re-train & Re-calibrate]
    R --> W[Re-learn fusion weights]
    W --> B[Backtests (synthetic injection)]
    B -->|opt settings| R
    B -->|publish| S
```

---

## 19) Change Log Sync (Template for `CHANGELOG.md`, v6.0.x)

* **Added:** Self-tuning calibration (tail-mass monitor); regime quality gates & smoothing.
* **Fixed:** `_resample` no-globals; `Mapping` import + stronger typing in `fuse.py`.
* **Improved:** Culprit attribution merge logic; fusion JSON exposing `effective_weights`.
* **Docs:** This **Master Analytical Backbone** replaces prior design notes and aligns roadmap to SQL parity & service mode.

---

## 20) Appendices

### A. Error Handling (Finalize-on-error)

* `acm_main` wraps run in `try/finally`: write **RunLog** with `OK/ERROR`, include `ErrorJSON` (module, message, stack digest).
* In file-mode, persist `error.json` inside run folder for forensics.

### B. Model Hashing

* **Feature hash** = SHA256 of selected tag list + feature recipe + cadence + window params.
* **Fit hash** = feature hash + detector params + PCA ridge + fusion weights + calibration params.

### C. Security & Governance

* No PII; telemetry limited to performance counters & run metadata.
* SQL writes via least-privilege `EXECUTE AS` procs; audit RunLog.

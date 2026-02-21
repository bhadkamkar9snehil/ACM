# ACM V11 - System Handbook

**Complete Implementation-Level Technical Reference**

This handbook provides a comprehensive walkthrough of ACM V11 for engineers and maintainers. It covers end-to-end data flow, module architecture, configuration surfaces, algorithmic reasoning, and operational procedures.

**Current Version:** v11.15.5 (February 20, 2026)

---

## Table of Contents

1. [Mental Model - Top Level Flow](#1-mental-model---top-level-flow)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Pipeline Phase Sequence](#3-pipeline-phase-sequence)
4. [Module Dependency Graph](#4-module-dependency-graph)
5. [Detector Algorithms](#5-detector-algorithms)
6. [Regime Detection](#6-regime-detection)
7. [Fusion and Episode Detection](#7-fusion-and-episode-detection)
8. [Health Scoring](#8-health-scoring)
9. [RUL Forecasting](#9-rul-forecasting)
10. [Model Lifecycle](#10-model-lifecycle)
11. [Configuration System](#11-configuration-system)
12. [SQL Schema](#12-sql-schema)
13. [Observability Stack](#13-observability-stack)
14. [Entry Points and Runtime Modes](#14-entry-points-and-runtime-modes)
15. [Codebase Map](#15-codebase-map)
16. [Troubleshooting](#16-troubleshooting)
17. [Extending ACM](#17-extending-acm)

---

## 1. Mental Model - Top Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                 ACM PIPELINE OVERVIEW                                    │
└─────────────────────────────────────────────────────────────────────────────────────────┘

     DATA SOURCE                    PROCESSING                         OUTPUTS
     ───────────                    ──────────                         ───────

  ┌──────────────┐            ┌─────────────────────┐            ┌──────────────────┐
  │ SQL Server   │            │  Feature Engineering │            │ ACM_Scores_Wide  │
  │ Historian    │───────────▶│  (fast_features.py)  │            │ ACM_HealthTimeline│
  │              │            └──────────┬──────────┘            │ ACM_Anomaly_Events│
  │ Equipment    │                       │                        │ ACM_RUL           │
  │ Sensor Data  │                       ▼                        │ ACM_RegimeTimeline│
  └──────────────┘            ┌─────────────────────┐            │ ACM_*Forecast     │
                              │  6-Head Detector     │            └──────────────────┘
                              │  Ensemble            │                     │
                              │  ┌───┬───┬───┐       │                     ▼
                              │  │AR1│PCA│IF │       │            ┌──────────────────┐
                              │  ├───┼───┼───┤       │            │ Grafana          │
                              │  │GMM│OMR│T2 │       │            │ Dashboards       │
                              │  └───┴───┴───┘       │            │                  │
                              └──────────┬──────────┘            │ Operations       │
                                         │                        │ Console          │
                                         ▼                        └──────────────────┘
                              ┌─────────────────────┐
                              │  Regime Clustering   │
                              │  (Raw Sensors Only)  │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │  Weighted Fusion     │
                              │  + Episode Detection │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │  Forecasting & RUL   │
                              │  Monte Carlo Sim     │
                              └─────────────────────┘
```

**Key Principles:**

1. **SQL-First Architecture**: All production data flows through SQL Server. File mode exists only for diagnostics.

2. **Six Independent Detectors**: Each detector answers a different "what's wrong?" question:
   - AR1: Sensor drift/spikes
   - PCA-SPE: Sensor decoupling
   - PCA-T2: Operating point anomaly
   - IForest: Rare states
   - GMM: Cluster membership
   - OMR: Cross-sensor residuals

3. **Regime Clustering Uses Raw Sensors Only** (v11.4.0 Architecture):
   - Regimes = HOW equipment operates (load, speed, flow, pressure)
   - Detectors = IF equipment is healthy
   - These are ORTHOGONAL concerns that must never be mixed

4. **Weighted Fusion**: Detector z-scores are weighted and combined into a single fused anomaly score.

5. **Episode Detection**: CUSUM change-point detection identifies sustained anomaly periods.

6. **RUL Forecasting**: Monte Carlo simulation projects health trajectory to estimate remaining useful life.

---

## 2. Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                              DETAILED SYSTEM ARCHITECTURE                                   │
└────────────────────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────────────┐
                                    │   sql_batch_runner  │
                                    │   (Entry Point)     │
                                    └──────────┬──────────┘
                                               │ subprocess
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                    core/acm_main.py                                       │
│                                    (Pipeline Orchestrator)                                │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                           │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐ │
│  │ ConfigDict  │   │ SQLClient   │   │ OutputMgr   │   │ Observability│   │ PipelineType│ │
│  │ (config)    │   │ (sql)       │   │ (writes)    │   │ (logging)   │   │ (contracts) │ │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘ │
│         │                 │                 │                 │                 │        │
│         └─────────────────┴─────────────────┴─────────────────┴─────────────────┘        │
│                                          │                                                │
│  ┌───────────────────────────────────────┴───────────────────────────────────────────┐   │
│  │                              PIPELINE PHASES                                       │   │
│  │                                                                                    │   │
│  │  [1] Data Load ──▶ [2] Validation ──▶ [3] Features ──▶ [4] Detectors ──────────▶  │   │
│  │                                                                                    │   │
│  │  ──▶ [5] Regimes ──▶ [6] Calibration ──▶ [7] Fusion ──▶ [8] Episodes ──────────▶  │   │
│  │                                                                                    │   │
│  │  ──▶ [9] Analytics ──▶ [10] Forecasting ──▶ [11] RUL ──▶ [12] Finalize           │   │
│  │                                                                                    │   │
│  └────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                           │
└───────────────────────────────────────────────────────────────────────────────────────────┘
         │                    │                    │                    │
         ▼                    ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ fast_features.py│  │ ar1_detector.py │  │  regimes.py     │  │ forecast_engine │
│ Feature Builder │  │ PCA, IF, GMM    │  │  Clustering     │  │ RUL Estimator   │
│                 │  │ omr.py          │  │                 │  │                 │
│ - Rolling stats │  │                 │  │ - K-Means       │  │ - Holt-Winters  │
│ - Lag features  │  │ - AR1 residuals │  │ - Auto-k        │  │ - Monte Carlo   │
│ - Z-scores      │  │ - SPE, T2       │  │ - Smoothing     │  │ - P10/P50/P90   │
│ - Spectral      │  │ - IsolationForest│ │ - Transients    │  │ - Culprits      │
│                 │  │ - GMM likelihood │  │                 │  │                 │
└─────────────────┘  │ - OMR residual  │  └─────────────────┘  └─────────────────┘
                     └─────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │    fuse.py      │
                     │                 │
                     │ - Weighted sum  │
                     │ - Weight tuning │
                     │ - CUSUM CPD     │
                     │ - Episode detect│
                     └─────────────────┘
```

---

## 3. Pipeline Phase Sequence

Each pipeline run executes these phases in order. Phase names appear in console output and SQL logs.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              PIPELINE PHASE EXECUTION                                   │
└────────────────────────────────────────────────────────────────────────────────────────┘

PHASE 1: INITIALIZATION [startup]
├── Parse CLI arguments (--equip, --start-time, --end-time, --mode)
├── Load configuration from SQL ACM_Config (cascading: global then equipment-specific)
├── Determine PipelineMode (ONLINE = scoring only, OFFLINE = full training)
├── Initialize OutputManager with SQL client
├── Create RunID for this execution
└── Start OpenTelemetry trace span

PHASE 2: DATA CONTRACT VALIDATION [data.contract]
├── DataContract.validate(raw_data) from pipeline_types.py
├── Check sensor column coverage (minimum 70% required)
├── Validate timestamp column exists and is parseable
├── Check data cadence matches config (sampling_secs)
├── Write validation results to ACM_DataContractValidation
└── FAIL FAST if validation fails (no point continuing with bad data)

PHASE 3: DATA LOADING [load_data]
├── Call stored procedure usp_ACM_GetHistorianData_TEMP
├── Parameters: @StartTime, @EndTime, @EquipmentName
├── Apply coldstart split: 60% train / 40% score
├── Deduplicate timestamps (keep last occurrence)
├── Ensure monotonically increasing index
├── Guard: NOOP if score data empty after deduplication
└── Output: train_df, score_df DataFrames

PHASE 4: BASELINE SEEDING [baseline.seed]
├── Load baseline from ACM_BaselineBuffer (persisted healthy data)
├── Check for temporal overlap with score data
├── Apply baseline for z-score normalization
├── If no baseline: use training data head
└── Output: baseline_df for calibration

PHASE 5: SEASONALITY DETECTION [seasonality.detect]
├── SeasonalityHandler.detect_patterns() from seasonality.py
├── FFT analysis to detect DAILY (24h) and WEEKLY (168h) cycles
├── Compute seasonal adjustment factors per sensor
├── Apply adjustment if config enables (seasonality.adjust_enabled)
└── Write results to ACM_SeasonalPatterns

PHASE 6: DATA QUALITY GUARDRAILS [data.guardrails]
├── Check train/score temporal overlap (warn if present)
├── Validate sensor variance (drop low-variance columns)
├── Check sensor coverage (% of expected sensors present)
├── Compute overall data quality score
├── Write to ACM_DataQuality table
└── Output: quality_score, valid_columns list

PHASE 7: FEATURE ENGINEERING [features.build + features.impute]
├── Pandas→Polars conversion: pl.from_pandas(train/score) in _build_features()
├── fast_features.compute_basic_features_pl() — Polars-only, no pandas fallback
│   ├── rolling_median, rolling_mad, rolling_mean_std (robust statistics)
│   ├── rolling_ols_slope (local trend)
│   ├── rolling_skew_kurt (distribution shape)
│   └── rolling_spectral_energy (vectorized stride-trick FFT, 3 frequency bands)
├── Polars→Pandas conversion: result.to_pandas() at pipeline boundary
├── impute_features(): protected_columns from load_manifest_only() prevents
│   low-var column drops that would cause feature mismatch (v11.15.1 fix)
├── Compute feature hash for model cache validation
└── Output: train_features, score_features DataFrames (pandas, in pipeline)

PHASE 8: MODEL TRAINING [train.detector_fit] (adaptive)
├── Check ModelRegistry for cached models matching feature hash
├── If cache miss, quality trigger, or --force-retrain:
│   ├── Fit AR1 detector: per-sensor autoregressive residuals
│   ├── Fit PCA detector: principal components, compute loadings
│   ├── Fit IForest detector: isolation forest ensemble
│   ├── Fit GMM detector: Gaussian mixture with BIC k-selection
│   └── Fit OMR detector: cross-sensor regression residuals
├── If cache hit and quality OK: load all detectors from cache
├── Validate loaded models against current feature columns
│   └── If mismatch: force retrain (v11.3.2 compatibility fix)
└── Output: trained detector objects

PHASE 9: DETECTOR SCORING [score.detector_score]
├── Score all 6 detectors on score_features
├── Compute raw scores:
│   ├── AR1: residual magnitude per sensor, aggregate
│   ├── PCA-SPE: squared prediction error (reconstruction loss)
│   ├── PCA-T2: Hotelling T-squared (distance in PC space)
│   ├── IForest: isolation path length (inverted)
│   ├── GMM: negative log-likelihood
│   └── OMR: cross-sensor prediction residual
├── Normalize to z-scores using training distribution (mean, std)
├── Apply clipping (z_cap, typically 8-10)
└── Output: scores_wide DataFrame with columns ar1_z, pca_spe_z, pca_t2_z, iforest_z, gmm_z, omr_z

PHASE 10: REGIME LABELING [regimes.label]
├── Build regime basis from RAW SENSOR VALUES ONLY (v11.4.0)
│   ├── Include: load, speed, flow, pressure, inlet_temp, etc.
│   └── Exclude: ALL detector z-scores, health metrics, engineered features
├── Standardize basis (StandardScaler)
├── Auto-k selection using silhouette score (k_min to k_max range)
├── Run K-Means clustering (or HDBSCAN if configured)
├── Smooth labels using median filter (smoothing.window)
├── Compute regime confidence per point
├── Identify NORMAL regime (highest dwell + lowest fused_z)
├── Label semantic regimes: Normal, Stressed, Transient, OpMode_N
├── Write ACM_RegimeDefinitions (cluster centers, statistics)
├── Write ACM_RegimeTimeline (per-timestamp labels)
└── Output: regime_labels array, regime_confidence array

PHASE 11: CALIBRATION [calibrate]
├── Score TRAINING data through all detectors (for calibration baseline)
├── Compute per-detector percentiles (P50, P95, P99)
├── Set adaptive clip_z from P99 to prevent saturation
├── Compute per-regime thresholds (if enabled)
├── Apply contamination filtering (v11.3.3): remove outliers from calibration
├── Self-tune thresholds to achieve target false positive rate
├── Write ACM_Thresholds (per-detector, per-regime)
└── Write ACM_CalibrationSummary

PHASE 12: DETECTOR FUSION [fusion.auto_tune + fusion]
├── Auto-tune detector weights:
│   ├── Primary method: Episode separability (maximize AUROC vs labeled episodes)
│   ├── Fallback method: Statistical diversity (variance + decorrelation)
│   └── Correlation discount: reduce weight for correlated detector pairs
├── Compute fused_z = sum(weight_i * z_i) / sum(weight_i)
├── Apply severity multipliers (context-aware):
│   ├── stable: x1.0
│   ├── regime_transition: x0.9 (mode switches less alarming)
│   └── health_degradation: x1.2 (boost priority when degrading)
├── Write ACM_DetectorCorrelation (28 pairwise correlations)
└── Output: fused_z series

PHASE 13: EPISODE DETECTION [episodes.detect]
├── CUSUM change-point detection on fused_z
├── Parameters: k_sigma (start threshold), h_sigma (severity threshold)
├── Identify episode boundaries (start_time, end_time)
├── Merge nearby episodes (gap_merge parameter)
├── Filter short episodes (min_len parameter)
├── Compute per-episode statistics:
│   ├── max_fused_z, mean_fused_z, duration_seconds
│   ├── Culprit sensors (top contributors)
│   └── Severity classification (INFO, WARNING, CRITICAL)
├── Write ACM_Anomaly_Events
├── Write ACM_EpisodeDiagnostics
└── Output: episodes DataFrame

PHASE 14: DRIFT MONITORING [drift]
├── CUSUMDetector on fused_z trend
├── Compute drift score (cumulative deviation from baseline)
├── Classify: STABLE (score < 1), DRIFTING (1-3), FAULT (> 3)
├── Write ACM_Drift_TS (time series of drift score)
├── Write ACM_DriftController (current state)
└── Output: drift_status, drift_score

PHASE 15: MODEL PERSISTENCE [models.persistence.save]
├── Save all trained models to SQL ModelRegistry
├── Include: detector objects, scaler params, feature columns
├── Compute model version hash from config signature
├── Write metadata to ACM_ModelHistory
└── Update ACM_ActiveModels pointer

PHASE 16: MODEL LIFECYCLE [models.lifecycle]
├── Load model state from ACM_ModelHistory
├── Compute model maturity metrics:
│   ├── run_count, total_samples_seen, silhouette_score
│   └── stability_ratio, forecast_mape
├── Check promotion criteria (v11.2.2 tightened):
│   ├── min_runs: 5
│   ├── min_silhouette: 0.40
│   ├── min_stability: 0.75
│   └── min_days: 7
├── Transition state if criteria met:
│   └── COLDSTART -> LEARNING -> CONVERGED -> DEPRECATED
├── Update ACM_ActiveModels with new state
└── Output: MaturityState

PHASE 17: OUTPUT GENERATION [persist.*]
├── write_scores_wide() -> ACM_Scores_Wide
├── write_anomaly_events() -> ACM_Anomaly_Events
├── write_detector_correlation() -> ACM_DetectorCorrelation
├── write_sensor_correlation() -> ACM_SensorCorrelations
├── write_sensor_normalized_ts() -> ACM_SensorNormalized_TS
├── write_seasonal_patterns() -> ACM_SeasonalPatterns
└── All writes batched for performance

PHASE 18: ANALYTICS GENERATION [outputs.comprehensive_analytics]
├── _generate_health_timeline() -> ACM_HealthTimeline
│   ├── Compute health_index = 100 * exp(-fused_z / scale)
│   ├── Apply smoothing (EWMA with smoothing_alpha)
│   └── Classify health zones (HEALTHY, DEGRADING, CRITICAL)
├── _generate_regime_timeline() -> ACM_RegimeTimeline
├── _generate_sensor_defects() -> ACM_SensorDefects
│   ├── Identify sensors with sustained high z-scores
│   └── Classify by severity
├── _generate_sensor_hotspots() -> ACM_SensorHotspots
└── Compute confidence values for all outputs (v11.0.0)

PHASE 19: FORECASTING [outputs.forecasting]
├── ForecastEngine.run_forecast() from forecast_engine.py
├── Load health history from ACM_HealthTimeline (30-90 days)
├── Detect maintenance resets (health jumps > 15%)
│   └── Use only post-reset data for trend fitting
├── Fit degradation model:
│   ├── Holt-Winters exponential smoothing
│   ├── Parameters: alpha, beta (trend)
│   └── Handle quality gates (reject SPARSE/FLAT/NOISY)
├── Generate health forecast (horizon: 7-30 days)
├── Generate sensor forecasts for top-10 changing sensors
├── Write ACM_HealthForecast
├── Write ACM_SensorForecast
└── Write ACM_FailureForecast

PHASE 20: RUL ESTIMATION [outputs.rul]
├── Load health forecast from previous phase
├── Monte Carlo simulation:
│   ├── Generate N=1000 random trajectories
│   ├── Add noise based on historical variance
│   ├── Project forward until health < failure_threshold (20%)
│   └── Record time-to-failure for each trajectory
├── Compute confidence intervals:
│   ├── P10 = 10th percentile (optimistic)
│   ├── P50 = 50th percentile (median)
│   └── P90 = 90th percentile (pessimistic)
├── Identify culprit sensors (top-3 contributors to degradation)
├── Validation guards (v11.3.4):
│   ├── Reject RUL < 1h if health > 70%
│   ├── Reject FailureProbability=100% if RUL > 100h
│   └── Reject negative/infinite/NaN values
├── Compute RUL confidence based on model maturity
├── Write ACM_RUL
└── Output: rul_hours, p10, p50, p90, top_sensors

PHASE 21: RUN FINALIZATION [sql.run_stats]
├── Write PCA loadings -> ACM_PCA_Loadings
├── Write run statistics -> ACM_Run_Stats
├── Write run metadata -> ACM_Runs
│   ├── StartedAt, CompletedAt, Status
│   ├── RowsProcessed, EpisodesDetected
│   ├── HealthIndexMin, HealthIndexMax, HealthIndexAvg
│   └── DriftStatus, ModelVersion
├── Update ACM_ColdstartState with progress
├── Commit all pending SQL transactions
├── Emit final OTEL span
└── Console summary output
```

---

## 4. Module Dependency Graph

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              MODULE DEPENDENCY GRAPH                                    │
└────────────────────────────────────────────────────────────────────────────────────────┘

scripts/sql_batch_runner.py
    └── subprocess calls: core/acm_main.py

core/acm_main.py (ORCHESTRATOR - 6000+ lines)
    │
    ├── Configuration & I/O
    │   ├── utils/config_dict.py ─────────── ConfigDict (cascading config loader)
    │   ├── core/sql_client.py ───────────── SQLClient (pyodbc wrapper)
    │   ├── core/output_manager.py ───────── OutputManager (all SQL/CSV writes)
    │   └── core/observability.py ────────── Console, Span, Metrics, T (logging)
    │
    ├── Data Processing
    │   ├── core/pipeline_types.py ───────── DataContract, PipelineMode enums
    │   ├── core/fast_features.py ────────── compute_basic_features_pl (Polars-only)
    │   ├── core/seasonality.py ──────────── SeasonalityHandler (FFT patterns)
    │   └── core/smart_coldstart.py ──────── SmartColdstart (historian retry)
    │
    ├── Detectors
    │   ├── core/ar1_detector.py ─────────── AR1Detector (autoregressive)
    │   ├── core/correlation.py ──────────── PCASubspaceDetector (SPE, T2)
    │   ├── core/outliers.py ─────────────── IsolationForestDetector, GMMDetector
    │   └── core/omr.py ──────────────────── OMRDetector (cross-sensor)
    │
    ├── Regimes & Fusion
    │   ├── core/regimes.py ──────────────── label(), detect_transient_states()
    │   ├── core/fuse.py ─────────────────── Fuser, ScoreCalibrator, tune_weights()
    │   ├── core/adaptive_thresholds.py ─── AdaptiveThresholdCalculator
    │   └── core/drift.py ────────────────── CUSUMDetector, compute_drift_metrics()
    │
    ├── Lifecycle & Persistence
    │   ├── core/model_persistence.py ────── save_models(), load_models()
    │   ├── core/model_lifecycle.py ──────── ModelState, promote_model()
    │   └── core/confidence.py ───────────── compute_*_confidence() functions
    │
    └── Forecasting
        ├── core/forecast_engine.py ──────── ForecastEngine (main forecaster)
        ├── core/degradation_model.py ────── fit_degradation(), health_jump_detect()
        ├── core/rul_estimator.py ────────── estimate_rul(), monte_carlo_sim()
        └── core/health_tracker.py ───────── HealthTracker (history management)

core/output_manager.py (I/O HUB)
    ├── core/sql_client.py ────────── SQLClient
    ├── core/observability.py ─────── Console
    └── core/confidence.py ────────── compute_*_confidence()

core/forecast_engine.py (FORECASTER)
    ├── core/sql_client.py
    ├── core/degradation_model.py
    ├── core/rul_estimator.py
    ├── core/confidence.py
    ├── core/model_lifecycle.py
    └── core/health_tracker.py
```

---

## 5. Detector Algorithms

### 5.1 AR1 Detector (Autoregressive Residuals)

**Purpose:** Detect sensor drift, spikes, and temporal pattern anomalies.

**Algorithm:**
```
For each sensor s:
    1. Fit AR(1) model: x(t) = phi * x(t-1) + epsilon(t)
    2. Compute residual: epsilon(t) = x(t) - phi * x(t-1)
    3. Normalize: z(t) = (epsilon(t) - mu_train) / sigma_train

Aggregate:
    ar1_z = sqrt(sum(z_i^2) / n_sensors)  # RMS across sensors
```

**Configuration:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `ar1.window` | 256 | Lookback window for AR coefficient |
| `ar1.alpha` | 0.05 | Significance level |
| `ar1.z_cap` | 8.0 | Maximum z-score cap |

**Fault Types Detected:** Sensor degradation, control loop oscillation, actuator wear, calibration drift.

---

### 5.2 PCA Detector (Principal Component Analysis)

**Purpose:** Detect multivariate anomalies - both sensor decoupling and operating point shifts.

**Training:**
```
1. Standardize features: X_scaled = (X - mu) / sigma
2. Fit PCA: X = T * P^T + E  (T = scores, P = loadings, E = residual)
3. Retain k components explaining 95% variance
4. Compute training statistics for SPE and T2
```

**Scoring - Two Metrics:**

**SPE (Squared Prediction Error):**
```
SPE(x) = ||x - x_hat||^2 = sum((x_i - x_hat_i)^2)

where x_hat = P * P^T * x  (projection onto PC subspace)

pca_spe_z = (SPE - SPE_mean_train) / SPE_std_train
```
*Detects: Sensor decoupling, reconstruction error, correlation breakdown*

**T2 (Hotelling's T-squared):**
```
T2(x) = sum(t_i^2 / lambda_i)  for i = 1..k

where t_i = score on i-th principal component
      lambda_i = variance explained by i-th component

pca_t2_z = (T2 - T2_mean_train) / T2_std_train
```
*Detects: Operating point anomalies, process upsets, off-design operation*

**Configuration:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `pca.n_components` | 5 | Number of principal components |
| `pca.svd_solver` | randomized | SVD algorithm |
| `pca.variance_threshold` | 0.95 | Minimum variance explained |

---

### 5.3 IForest Detector (Isolation Forest)

**Purpose:** Detect rare states and novel failure modes.

**Algorithm:**
```
Training:
1. Build ensemble of N=100 isolation trees
2. Each tree randomly partitions feature space
3. Anomalies are isolated with fewer splits (shorter path)

Scoring:
1. Compute average path length h(x) across all trees
2. Anomaly score: s(x) = 2^(-E[h(x)] / c(n))
3. Normalize: iforest_z = (s - s_mean_train) / s_std_train

where c(n) = 2 * (ln(n-1) + 0.5772) - 2*(n-1)/n
      (average path length in unsuccessful search)
```

**Configuration:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `iforest.n_estimators` | 100 | Number of trees |
| `iforest.contamination` | 0.01 | Expected anomaly fraction |
| `iforest.max_samples` | 2048 | Samples per tree |

**Fault Types Detected:** Novel failure modes, rare transients, unknown conditions.

---

### 5.4 GMM Detector (Gaussian Mixture Model)

**Purpose:** Detect cluster membership anomalies and mode confusion.

**Algorithm:**
```
Training:
1. Search k from k_min to k_max
2. Fit GMM for each k, compute BIC
3. Select k with lowest BIC
4. Final model: p(x) = sum_k pi_k * N(x | mu_k, Sigma_k)

Scoring:
1. Compute log-likelihood: log p(x)
2. Low likelihood = anomaly
3. Normalize: gmm_z = -(log_p - log_p_mean_train) / log_p_std_train
   (negative because low likelihood = high z)
```

**Configuration:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `gmm.k_min` | 2 | Minimum components |
| `gmm.k_max` | 3 | Maximum components |
| `gmm.covariance_type` | diag | Covariance structure |
| `gmm.bic_enabled` | True | Use BIC for k selection |

**Fault Types Detected:** Mode confusion, startup/shutdown anomalies, regime transitions.

---

### 5.5 OMR Detector (Overall Model Residual)

**Purpose:** Detect cross-sensor relationship breakdowns.

**Algorithm:**
```
Training:
1. For each sensor s_i:
   a. Train model: s_i_hat = f(s_1, s_2, ..., s_n \ s_i)
   b. Model type: Linear regression, PLS, or auto-selected
2. Store trained models and residual statistics

Scoring:
1. For each sensor, compute residual: r_i = s_i - s_i_hat
2. Aggregate: OMR = sqrt(sum(r_i^2) / n)
3. Normalize: omr_z = (OMR - OMR_mean_train) / OMR_std_train
```

**Configuration:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `omr.model_type` | auto | Model type: auto/pca/linear |
| `omr.n_components` | 5 | PCA components for reconstruction |
| `omr.min_samples` | 100 | Minimum training samples |
| `omr.z_clip` | 10.0 | Z-score clipping |

**Fault Types Detected:** Bearing degradation, mechanical wear, fouling, calibration drift, coupling failures.

---

### 5.6 Detector Comparison Summary

| Detector | Z-Column | What It Detects | Strengths | Weaknesses |
|----------|----------|-----------------|-----------|------------|
| AR1 | `ar1_z` | Temporal drift, spikes | Fast, interpretable | Single-sensor focus |
| PCA-SPE | `pca_spe_z` | Sensor decoupling | Multivariate | Needs many sensors |
| PCA-T2 | `pca_t2_z` | Operating point shift | Sensitive to mode changes | False positives on regime change |
| IForest | `iforest_z` | Rare states | Novel detection | Less interpretable |
| GMM | `gmm_z` | Cluster anomalies | Probabilistic | Assumes Gaussian clusters |
| OMR | `omr_z` | Relationship breakdown | Cross-sensor | Computationally expensive |

---

## 6. Regime Detection

### 6.1 Architectural Principle (v11.4.0)

**CRITICAL:** Regime clustering uses RAW SENSOR VALUES ONLY.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              REGIME CLUSTERING ARCHITECTURE                             │
└────────────────────────────────────────────────────────────────────────────────────────┘

    CORRECT (v11.4.0)                           WRONG (pre-v11.4.0)
    ─────────────────                           ───────────────────

    Raw Sensors                                 Raw Sensors + Health Features
    ────────────                                ─────────────────────────────
    • Load (%)         ─┐                       • Load (%)              ─┐
    • Speed (RPM)       │                       • Speed (RPM)            │
    • Flow (m3/h)       ├──▶ K-Means            • Flow (m3/h)            │
    • Pressure (bar)    │    Clustering         • health_ensemble_z      ├──▶ K-Means
    • Inlet Temp (C)   ─┘                       • health_trend           │    CIRCULAR!
                                                • health_quartile       ─┘

    WHY THIS MATTERS:
    ─────────────────
    Using health features in clustering creates CIRCULAR MASKING:

    1. Equipment degrades -> detector z-scores rise
    2. Health features push point to "new regime"
    3. New regime gets fresh baseline -> degradation hidden
    4. Equipment appears "healthy in its current regime"

    RESULT: Masked degradation, missed failures, delayed alerts

    CORRECT SEPARATION:
    ───────────────────
    • Regimes = HOW equipment operates (controllable inputs)
    • Detectors = IF equipment is healthy (condition outputs)
    • These are ORTHOGONAL and must NEVER be mixed
```

### 6.2 Regime Discovery Algorithm

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              REGIME DISCOVERY FLOW                                      │
└────────────────────────────────────────────────────────────────────────────────────────┘

Step 1: Build Regime Basis
├── Select operating variables (OPERATING_TAG_KEYWORDS):
│   ├── speed, rpm, load, flow, pressure, power
│   ├── stroke, valve, frequency, setpoint
│   └── Exclude: bearing, winding, vibration, current (condition indicators)
├── Scale using StandardScaler
└── Output: basis_matrix (N_samples x M_operating_vars)

Step 2: Auto-K Selection
├── For k in range(k_min, k_max):
│   ├── Fit K-Means with k clusters
│   ├── Compute silhouette score: (b - a) / max(a, b)
│   │   where a = mean intra-cluster distance
│   │         b = mean nearest-cluster distance
│   └── Store score
├── Select k with highest silhouette score
└── Guard: minimum silhouette_min (0.40 in v11.2.2)

Step 3: Clustering
├── Fit K-Means with selected k
├── Assign labels (0, 1, 2, ... k-1)
├── Compute per-point confidence:
│   confidence = 1 - (dist_to_centroid / max_dist)
└── Output: raw_labels, confidence

Step 4: Label Smoothing
├── Apply median filter (smoothing.window)
├── Enforce minimum dwell time (min_dwell_samples, min_dwell_seconds)
├── Handle transient states (rapid regime changes)
└── Output: smoothed_labels

Step 5: Normal Regime Identification
├── For each regime:
│   ├── Compute dwell_fraction = time_in_regime / total_time
│   ├── Compute median_fused = median(fused_z in regime)
│   └── Score = dwell_fraction * (1 / (1 + median_fused))
├── Regime with highest score = NORMAL
└── Guards: min_dwell_fraction (0.15), max_median_fused (2.0)

Step 6: Semantic Labeling
├── NORMAL: Highest dwell + low fused (identified above)
├── STRESSED: High median_fused (> 2.0)
├── TRANSIENT: Low dwell_fraction (< 0.10)
└── OpMode_N: Other stable operating modes
```

### 6.3 Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `regimes.auto_k.k_min` | 2 | Minimum clusters |
| `regimes.auto_k.k_max` | 6 | Maximum clusters |
| `regimes.quality.silhouette_min` | 0.40 | Minimum clustering quality (v11.2.2 tightened) |
| `regimes.smoothing.passes` | 3 | Smoothing iterations |
| `regimes.smoothing.window` | 7 | Median filter window |
| `regimes.smoothing.min_dwell_samples` | 10 | Minimum samples in regime |
| `regimes.smoothing.min_dwell_seconds` | 900 | Minimum regime duration (15 min) |

---

## 7. Fusion and Episode Detection

### 7.1 Detector Fusion

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              DETECTOR FUSION ALGORITHM                                  │
└────────────────────────────────────────────────────────────────────────────────────────┘

Step 1: Weight Assignment
├── Default weights:
│   ├── ar1_z:     0.20
│   ├── pca_spe_z: 0.20
│   ├── pca_t2_z:  0.15
│   ├── iforest_z: 0.15
│   ├── gmm_z:     0.15
│   └── omr_z:     0.15

Step 2: Auto-Tuning (if enabled)
├── Primary Method: Episode Separability
│   ├── Compute AUROC for each detector vs known episodes
│   ├── Weight ~ AUROC (better separation = higher weight)
│   └── Requires: require_external_labels = True (v11.2.2 default)
│
├── Fallback Method: Statistical Diversity
│   ├── variance_score: Higher variance = more informative
│   ├── diversity_score: Low correlation with others = unique info
│   ├── tail_score: P95/P50 ratio = sensitivity to extremes
│   └── weight_score = 0.4*variance + 0.4*diversity + 0.2*tail

Step 3: Correlation Discount (v11.1.4)
├── For each detector pair (i, j):
│   ├── Compute correlation: r = corr(z_i, z_j)
│   ├── If |r| > 0.5:
│   │   ├── discount = min(0.3, (|r| - 0.5) * 0.5)
│   │   ├── w_i *= (1 - discount)
│   │   └── w_j *= (1 - discount)
│   └── Prevents double-counting correlated information

Step 4: Fusion Computation
├── fused_z = sum(w_i * z_i) / sum(w_i)
├── Apply z_clip to prevent extreme values
└── Output: fused_z series
```

### 7.2 Episode Detection (CUSUM)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              CUSUM EPISODE DETECTION                                    │
└────────────────────────────────────────────────────────────────────────────────────────┘

CUSUM Algorithm:
────────────────
S_t = max(0, S_{t-1} + (x_t - mu - k))

where:
• S_t = cumulative sum at time t
• x_t = fused_z at time t
• mu = mean fused_z (typically 0 after calibration)
• k = allowance parameter (k_sigma * sigma)

Episode Boundaries:
───────────────────
• Episode START: S_t > h (h = h_sigma * sigma)
• Episode END: S_t returns to 0

Post-Processing:
────────────────
• Merge episodes separated by < gap_merge samples
• Filter episodes shorter than min_len samples
• Compute per-episode statistics (max_z, mean_z, duration)
• Identify culprit sensors (top contributors)
• Classify severity: INFO (z < 3), WARNING (3-5), CRITICAL (> 5)
```

### 7.3 Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `fusion.weights.*` | See above | Per-detector weights |
| `fusion.auto_tune.enabled` | True | Enable weight tuning |
| `fusion.auto_tune.require_external_labels` | True | Require labeled episodes (v11.2.2) |
| `episodes.cpd.k_sigma` | 2.0 | Episode start threshold |
| `episodes.cpd.h_sigma` | 12.0 | Episode severity threshold |
| `episodes.min_len` | 3 | Minimum episode length |
| `episodes.gap_merge` | 5 | Merge gap threshold |

---

## 8. Health Scoring

### 8.1 Health Index Calculation

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              HEALTH INDEX FORMULA                                       │
└────────────────────────────────────────────────────────────────────────────────────────┘

Raw Health:
───────────
health_raw(t) = 100 * exp(-fused_z(t) / scale)

where:
• fused_z(t) = weighted fusion of detector z-scores
• scale = calibration parameter (default: 3.0)
• Result: 100% when fused_z=0, decays exponentially

Smoothed Health (EWMA):
───────────────────────
health(t) = alpha * health_raw(t) + (1 - alpha) * health(t-1)

where:
• alpha = smoothing_alpha (default: 0.3)
• Higher alpha = more responsive, noisier
• Lower alpha = smoother, slower to react

Health Zones:
─────────────
┌──────────────┬─────────────┬────────────────────────────┐
│ Range        │ Zone        │ Action                     │
├──────────────┼─────────────┼────────────────────────────┤
│ 80-100%      │ HEALTHY     │ Normal operation           │
│ 50-80%       │ DEGRADING   │ Monitor closely            │
│ 20-50%       │ CRITICAL    │ Schedule maintenance       │
│ 0-20%        │ FAILURE     │ Immediate intervention     │
└──────────────┴─────────────┴────────────────────────────┘
```

### 8.2 Confidence Model (v11.2.2)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              CONFIDENCE CALCULATION                                     │
└────────────────────────────────────────────────────────────────────────────────────────┘

Confidence = Harmonic Mean of:
──────────────────────────────
1. model_maturity:
   • COLDSTART:  0.3
   • LEARNING:   0.6
   • CONVERGED:  1.0
   • DEPRECATED: 0.4

2. data_coverage:
   • n_sensors_present / n_sensors_expected

3. regime_confidence:
   • 1 - (distance_to_centroid / max_distance)

4. temporal_stability:
   • 1 - std(health_last_N) / mean(health_last_N)

Formula:
────────
confidence = 4 / (1/maturity + 1/coverage + 1/regime_conf + 1/stability)

Why Harmonic Mean? (v11.2.2 fix)
────────────────────────────────
• Penalizes imbalanced factors heavily
• If ANY factor is low, overall confidence is low
• Prevents false confidence when one factor masks weakness

Example:
• Arithmetic mean: (0.1 + 0.9 + 0.9 + 0.9) / 4 = 0.70 (too optimistic)
• Harmonic mean:   4 / (10 + 1.1 + 1.1 + 1.1) = 0.31 (appropriate)
```

---

## 9. RUL Forecasting

### 9.1 Forecasting Pipeline

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              RUL FORECASTING PIPELINE                                   │
└────────────────────────────────────────────────────────────────────────────────────────┘

Step 1: Load Health History
├── Query ACM_HealthTimeline for last 30-90 days
├── Resample to uniform cadence
└── Handle gaps with linear interpolation

Step 2: Detect Maintenance Resets (v11.1.4)
├── Compute health differences: diff = health(t) - health(t-1)
├── Identify positive jumps > 15% (maintenance resets)
├── Find last reset index
└── Use ONLY post-reset data for trend fitting

Step 3: Fit Degradation Model
├── Method: Holt-Winters exponential smoothing
├── Parameters: alpha (level), beta (trend)
├── Quality gates:
│   ├── Reject SPARSE: < 50 samples
│   ├── Reject FLAT: std(health) < 1.0
│   ├── Reject NOISY: std(residuals) > 20
│   └── Allow GAPPY: for historical replay

Step 4: Monte Carlo Simulation
├── Generate N=1000 trajectories
├── For each trajectory:
│   ├── Start from current health
│   ├── Apply trend + random noise (calibrated from history)
│   ├── Project forward hour-by-hour
│   ├── Record time when health < failure_threshold (20%)
│   └── Store time-to-failure
├── Sort all times-to-failure
└── Output: distribution of RUL values

Step 5: Confidence Intervals
├── P10 = 10th percentile (optimistic - 90% chance of lasting longer)
├── P50 = 50th percentile (median estimate)
├── P90 = 90th percentile (pessimistic - 90% chance of failing sooner)
└── RUL_Hours = P50 (primary estimate)

Step 6: Culprit Identification
├── For each sensor, compute contribution to degradation:
│   contribution_i = corr(sensor_z_i, fused_z) * mean(sensor_z_i)
├── Rank sensors by contribution
├── TopSensor1 = highest contribution
├── TopSensor2 = second highest
└── TopSensor3 = third highest

Step 7: Validation Guards (v11.3.4)
├── REJECT if: RUL < 1h AND health > 70%
│   Reason: Implausible imminent failure
├── REJECT if: FailureProbability = 100% AND RUL > 100h
│   Reason: Inconsistent prediction
├── REJECT if: RUL is negative, infinite, or NaN
│   Reason: Invalid computation
└── Log rejections with Console.warn()
```

### 9.2 RUL Reliability Gating

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              RUL RELIABILITY STATUS                                     │
└────────────────────────────────────────────────────────────────────────────────────────┘

ReliabilityStatus based on MaturityState:
─────────────────────────────────────────

┌───────────────┬────────────────────┬──────────────────────────────────────┐
│ MaturityState │ ReliabilityStatus  │ Dashboard Display                    │
├───────────────┼────────────────────┼──────────────────────────────────────┤
│ COLDSTART     │ NOT_RELIABLE       │ "RUL: Insufficient History"          │
│ LEARNING      │ NOT_RELIABLE       │ "RUL: Model Training (N/5 runs)"     │
│ CONVERGED     │ RELIABLE           │ "RUL: 142h (P10: 98h, P90: 201h)"    │
│ DEPRECATED    │ STALE              │ "RUL: Model Outdated - Retraining"   │
└───────────────┴────────────────────┴──────────────────────────────────────┘

Promotion Criteria (v11.2.2 tightened):
───────────────────────────────────────
• min_consecutive_runs: 5 (was 3)
• min_silhouette_score: 0.40 (was 0.15)
• min_stability_ratio: 0.75 (was 0.6)
• min_days_of_history: 7
• max_forecast_mape: 35.0 (was 50.0)
```

---

## 10. Model Lifecycle

### 10.1 MaturityState Transitions

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              MODEL LIFECYCLE STATE MACHINE                              │
└────────────────────────────────────────────────────────────────────────────────────────┘

     ┌─────────────┐
     │  COLDSTART  │ ─── First run, no history
     └──────┬──────┘
            │ After 1 successful run
            ▼
     ┌─────────────┐
     │  LEARNING   │ ─── Building baselines, accumulating statistics
     └──────┬──────┘
            │ All promotion criteria met:
            │ • 5+ runs
            │ • Silhouette >= 0.40
            │ • Stability >= 0.75
            │ • 7+ days history
            ▼
     ┌─────────────┐
     │  CONVERGED  │ ─── Stable, reliable outputs, full confidence
     └──────┬──────┘
            │ Any of:
            │ • Config signature changed
            │ • Schema version bumped
            │ • Force retrain flag set
            ▼
     ┌─────────────┐
     │ DEPRECATED  │ ─── Stale model, pending retrain
     └──────┬──────┘
            │ On next run
            ▼
     ┌─────────────┐
     │  COLDSTART  │ ─── Cycle restarts
     └─────────────┘
```

### 10.2 Regime Model Versioning

```
REGIME_MODEL_VERSION History:
─────────────────────────────
• v3.0 (Dec 2025): Tag taxonomy, uniform scaling, P95 threshold
• v3.1 (Jan 2026): Label mapping, transient detection on operating vars
• v4.0 (Jan 21, 2026): RAW SENSORS ONLY - removed health-state features

When REGIME_MODEL_VERSION changes:
──────────────────────────────────
• All cached regime models invalidated
• Full clustering retraining on next run
• Existing regime labels may change
• Dashboard may show discontinuity
```

---

## 11. Configuration System

### 11.1 Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              CONFIGURATION FLOW                                         │
└────────────────────────────────────────────────────────────────────────────────────────┘

configs/config_table.csv ──▶ Python ConfigDict ──▶ SQL ACM_Config
         │                        │                       │
         ▼                        ▼                       ▼
    EquipID=0                Dot-path access         Sync via:
    (global)                 cfg['models.pca']       populate_acm_config.py
         │
    EquipID=N
    (override)

Cascading Logic:
────────────────
1. Load global defaults (EquipID=0)
2. Apply equipment-specific overrides (EquipID=N)
3. Apply runtime CLI overrides (--config)
4. Result: merged configuration for this run
```

### 11.2 Key Configuration Categories

**DATA (Most Likely to Need Override)**
| Parameter | Default | Description | Override? |
|-----------|---------|-------------|-----------|
| `data.sampling_secs` | 1800 | Data cadence (seconds) | YES |
| `data.timestamp_col` | EntryDateTime | Timestamp column name | YES |
| `data.min_train_samples` | 200 | Minimum coldstart rows | Sometimes |

**MODELS (Detector Hyperparameters)**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `models.pca.n_components` | 5 | PCA dimensions |
| `models.ar1.window` | 256 | AR lookback window |
| `models.iforest.contamination` | 0.01 | Anomaly fraction |
| `models.gmm.k_max` | 3 | Max GMM components |
| `models.omr.model_type` | auto | OMR model selection |

**FUSION (Auto-Tuned)**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `fusion.weights.ar1_z` | 0.20 | AR1 weight |
| `fusion.weights.pca_spe_z` | 0.20 | PCA-SPE weight |
| `fusion.auto_tune.enabled` | True | Enable auto-tuning |

**EPISODES**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `episodes.cpd.k_sigma` | 2.0 | Episode start threshold |
| `episodes.cpd.h_sigma` | 12.0 | Severity threshold |
| `episodes.min_len` | 3 | Minimum episode length |

**REGIMES**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `regimes.auto_k.k_min` | 2 | Minimum clusters |
| `regimes.auto_k.k_max` | 6 | Maximum clusters |
| `regimes.quality.silhouette_min` | 0.40 | Minimum quality |

**THRESHOLDS**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `thresholds.alert_z` | 3.0 | Alert threshold |
| `thresholds.warn_z` | 1.5 | Warning threshold |
| `thresholds.self_tune.enabled` | True | Enable self-tuning |

### 11.3 Syncing Configuration

```powershell
# After editing config_table.csv
python scripts/sql/populate_acm_config.py

# Verify sync
sqlcmd -S "server\instance" -d ACM -E -Q "SELECT COUNT(*) FROM ACM_Config"
```

---

## 12. SQL Schema

### 12.1 Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `Equipment` | Equipment registry | EquipID, EquipCode, EquipName |
| `{Equipment}_Data` | Historian data | EntryDateTime, sensor columns |
| `ACM_Config` | Configuration | EquipID, ParamPath, ParamValue |
| `ACM_Runs` | Run metadata | RunID, EquipID, StartedAt, Status |
| `ACM_ColdstartState` | Coldstart progress | EquipID, DataPointsAccumulated |

### 12.2 Output Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `ACM_Scores_Wide` | Detector z-scores | Timestamp, ar1_z, pca_spe_z, fused_z |
| `ACM_HealthTimeline` | Health history | Timestamp, HealthIndex, Confidence |
| `ACM_RegimeTimeline` | Regime assignments | Timestamp, RegimeLabel, Confidence |
| `ACM_Anomaly_Events` | Detected episodes | StartTime, EndTime, Severity, MaxZ |
| `ACM_RUL` | RUL predictions | RUL_Hours, P10, P50, P90, TopSensor1 |
| `ACM_HealthForecast` | Health projections | ForecastTime, ForecastHealth |
| `ACM_SensorForecast` | Sensor projections | SensorName, ForecastValue |

### 12.3 Dashboard Views

| View | Purpose |
|------|---------|
| `vw_ACM_CurrentHealth` | Latest health per equipment |
| `vw_ACM_HealthHistory` | Health time series |
| `vw_ACM_ActiveDefects` | Active sensor defects |
| `vw_ACM_RULSummary` | RUL overview |
| `vw_ACM_EquipmentOverview` | Fleet summary |

### 12.4 Schema Reference

Full schema documentation: [docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md](sql/COMPREHENSIVE_SCHEMA_REFERENCE.md)

Export fresh schema:
```powershell
python scripts/sql/export_comprehensive_schema.py --output docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md
```

---

## 13. Observability Stack

### 13.1 Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              OBSERVABILITY STACK                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  ACM        │     │  Alloy      │     │  Storage    │     │  Grafana    │
│  Pipeline   │────▶│  (OTLP)     │────▶│  Backends   │────▶│  Dashboards │
│             │     │             │     │             │     │             │
│  Console.*  │     │  Port 4317  │     │  Tempo      │     │  Port 3000  │
│  Span.*     │     │  Port 4318  │     │  Loki       │     │             │
│  Metrics.*  │     │             │     │  Prometheus │     │  admin/admin│
│             │     │             │     │  Pyroscope  │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### 13.2 Components

| Component | Port | Purpose |
|-----------|------|---------|
| Grafana | 3000 | Dashboard UI (admin/admin) |
| Alloy | 4317, 4318 | OTLP collector |
| Tempo | 3200 | Distributed traces |
| Loki | 3100 | Log aggregation |
| Prometheus | 9090 | Metrics |
| Pyroscope | 4040 | Continuous profiling |

### 13.3 Console API (core/observability.py)

```python
from core.observability import Console, Span, Metrics

# Logging (goes to Loki)
Console.info("Processing equipment", equipment="FD_FAN", batch=5)
Console.warn("High anomaly rate", rate=0.15)
Console.error("SQL connection failed", error=str(e))

# Console-only output (NOT to Loki)
Console.status("Loading data...")
Console.header("Phase 1: Initialization")
Console.section("Feature Engineering")

# Tracing (goes to Tempo)
with Span("detector.score", detector="PCA"):
    scores = pca.score(features)

# Metrics (goes to Prometheus)
Metrics.counter("acm.episodes.detected", 5, equipment="FD_FAN")
Metrics.histogram("acm.run.duration_seconds", 45.3)
```

### 13.4 Starting the Stack

```powershell
cd install/observability
docker compose up -d

# Verify
docker ps --format "table {{.Names}}\t{{.Status}}"

# Expected: 6 containers running
# acm-grafana, acm-alloy, acm-tempo, acm-loki, acm-prometheus, acm-pyroscope
```

---

## 14. Entry Points and Adaptive Learning

### 14.1 Adaptive Pipeline Architecture (v11.8.0)

ACM uses a single adaptive pipeline - no manual ONLINE/OFFLINE mode selection.
The system automatically decides whether to train or score based on model state
and quality metrics:

```
ADAPTIVE PIPELINE DECISION TREE
================================

1. CHECK: Do cached models exist?
   ├─ NO  → Train fresh models (coldstart)
   └─ YES → Continue to step 2

2. CHECK: Are cached models valid? (feature count match, not corrupt)
   ├─ NO  → Retrain automatically
   └─ YES → Continue to step 3

3. SCORE: Run detectors with cached models

4. ASSESS: Evaluate quality after scoring
   - Silhouette score, anomaly rate, drift score
   - Feature count match, model age

5. DECIDE: Should retrain?
   ├─ YES → Retrain models, save new cache
   └─ NO  → Continue with current models

MODEL LIFECYCLE (quality-driven, no manual modes):
  COLDSTART → LEARNING → CONVERGED
  - Promotion based on: 5+ runs, silhouette >= 0.40, stability >= 0.75
  - Retraining triggered by quality degradation, not manual mode switch
```

### 14.2 Anti-Upsample Guard (v11.5.0)

```
DATA RESAMPLING PROTECTION
==========================

ACM NEVER upsamples data. If requested cadence < native cadence:
  - Native data preserved (no interpolation)
  - Log: "ANTI-UPSAMPLE: Requested (60s) < native (600s)"
  - cadence_ok = True (native is valid)

WHY THIS MATTERS:
  - Upsampling creates synthetic data via interpolation
  - 10x row inflation corrupts all calibration
  - False detection rates increase dramatically
  - Model convergence becomes impossible

CONFIG RECOMMENDATION:
  data.sampling_secs = auto   # Always use native cadence
```

### 14.3 Production: sql_batch_runner.py

```powershell
python scripts/sql_batch_runner.py \
    --equip FD_FAN GAS_TURBINE \
    --tick-minutes 1440 \
    --max-workers 2 \
    --resume
```

| Argument | Description |
|----------|-------------|
| `--equip` | Equipment codes to process |
| `--tick-minutes` | Batch window size (1440 = 1 day) |
| `--max-workers` | Parallel equipment processing |
| `--resume` | Continue from last run |
| `--start-from-beginning` | Full reset (coldstart) |
| `--max-batches` | Limit batches (testing) |

### 14.4 Testing: acm_main.py

```powershell
python -m core.acm \
    --equip FD_FAN \
    --start-time "2024-01-01T00:00:00" \
    --end-time "2024-01-31T23:59:59"
```

| Argument | Description |
|----------|-------------|
| `--equip` | Equipment code |
| `--start-time` | ISO 8601 start |
| `--end-time` | ISO 8601 end |
| `--force-retrain` | Force model retraining regardless of cache/quality |
| `--clear-cache` | Clear cached models before run |

### 14.5 Adaptive Training Decisions

| Condition | Behavior |
|-----------|----------|
| Coldstart (no cached models) | Full training of all detectors |
| Cache hit + quality OK | Load cached models, scoring only |
| Quality trigger (silhouette < 0.30, drift > 3.0, etc.) | Automatic retraining |
| Feature hash mismatch | Force retrain (compatibility) |
| `--force-retrain` CLI flag | Force full retraining |
| `--clear-cache` CLI flag | Clear cache, then retrain |

---

## 15. Codebase Map

### 15.1 Core Modules

```
core/
├── acm_main.py          # Pipeline orchestrator (6000+ lines)
├── acm.py               # Unified entry point
├── output_manager.py    # All SQL/CSV writes
├── sql_client.py        # pyodbc wrapper
├── observability.py     # Console, Span, Metrics
├── pipeline_types.py    # DataContract, ValidationResult
│
├── fast_features.py     # Feature engineering (Polars-only; pandas boundary in acm_main._build_features)
├── seasonality.py       # FFT pattern detection
├── smart_coldstart.py   # Historian retry logic
│
├── ar1_detector.py      # AR1 detector
├── correlation.py       # PCA detector (SPE, T2)
├── outliers.py          # IForest, GMM detectors
├── omr.py               # OMR detector
│
├── regimes.py           # Regime clustering (RAW SENSORS ONLY)
├── fuse.py              # Weighted fusion, CUSUM episodes
├── adaptive_thresholds.py # Per-regime thresholds
├── drift.py             # CUSUM drift detection
│
├── model_persistence.py # SQL model registry
├── model_lifecycle.py   # MaturityState management
├── confidence.py        # Confidence calculations
│
├── forecast_engine.py   # Health/RUL forecasting
├── degradation_model.py # Holt-Winters, jump detection
├── rul_estimator.py     # Monte Carlo RUL
└── health_tracker.py    # Health history management
```

### 15.2 Scripts

```
scripts/
├── sql_batch_runner.py      # Production batch runner
├── sql/
│   ├── populate_acm_config.py        # Sync config to SQL
│   ├── verify_acm_connection.py      # Test connectivity
│   ├── export_comprehensive_schema.py # Schema export
│   ├── import_csv_to_acm.py          # Import equipment data
│   └── truncate_run_data.sql         # Clear run data
```

### 15.3 Configuration

```
configs/
├── config_table.csv         # 238+ parameters
├── sql_connection.ini       # SQL credentials (gitignored)
└── sql_connection.example.ini
```

---

## 16. Troubleshooting

### 16.1 Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| NOOP - No data | Wrong sampling_secs | Match data cadence in config |
| NOOP - Insufficient rows | Coldstart incomplete | Wait for accumulation or reduce min_train_samples |
| RUL NOT_RELIABLE | Model not converged | Run 5+ batches |
| Episodes every batch | k_sigma too low | Increase to 3.0-4.0 |
| Health score flat | Baseline not seeding | Check ACM_BaselineBuffer |
| SQL timeout | Connection pool exhausted | Increase sql.pool_max |
| Regime oscillation | Clustering unstable | Increase smoothing.window |

### 16.2 Diagnostic Commands

```powershell
# Test SQL connectivity
python scripts/sql/verify_acm_connection.py

# Check recent runs
sqlcmd -S "server\instance" -d ACM -E -Q "SELECT TOP 10 RunID, EquipID, Status, StartedAt FROM ACM_Runs ORDER BY ID DESC"

# Check run logs
sqlcmd -S "server\instance" -d ACM -E -Q "SELECT TOP 20 LoggedAt, Level, Message FROM ACM_RunLogs ORDER BY ID DESC"

# Check coldstart state
sqlcmd -S "server\instance" -d ACM -E -Q "SELECT * FROM ACM_ColdstartState"

# Check regime distribution
sqlcmd -S "server\instance" -d ACM -E -Q "SELECT RegimeLabel, COUNT(*) AS N FROM ACM_RegimeTimeline GROUP BY RegimeLabel"
```

### 16.3 Cache Invalidation

```powershell
# Force retrain all detectors
python -m core.acm --equip FD_FAN --clear-cache

# Reset coldstart state for equipment
sqlcmd -S "server\instance" -d ACM -E -Q "DELETE FROM ACM_ColdstartState WHERE EquipID = 1"

# Clear all run data (use with caution)
sqlcmd -S "server\instance" -d ACM -E -i "scripts/sql/truncate_run_data.sql"
```

---

## 17. Extending ACM

### 17.1 Adding a New Detector

1. Create detector class in `core/`:
```python
class NewDetector:
    def fit(self, X: pd.DataFrame) -> None: ...
    def score(self, X: pd.DataFrame) -> pd.Series: ...
```

2. Register in `acm_main.py` detector fitting section
3. Add z-column to fusion weights in config
4. Update `fuse.py` to include in weighted sum
5. Add to `ACM_Scores_Wide` schema

### 17.2 Adding New Output Table

1. Add table name to `OutputManager.ALLOWED_TABLES`
2. Create write method: `write_new_table(df)`
3. Wire up call in appropriate pipeline phase
4. Create SQL table with proper schema
5. Update `COMPREHENSIVE_SCHEMA_REFERENCE.md`

### 17.3 Bumping Regime Model Version

When changing regime clustering logic:

```python
# In core/regimes.py
REGIME_MODEL_VERSION = "5.0"  # Increment from 4.0
```

This invalidates all cached regime models.

---

## Version History

| Version | Date | Key Changes |
|---------|------|-------------|
| v11.15.5 | 2026-02-20 | Drift hysteresis continuity fix: load previous ControllerState from ACM_DriftController and pass as prev_alert_mode; CUSUM accumulator reset on fit; unified drift_mode output |
| v11.15.4 | 2026-02-20 | 5 correctness bugs: config-driven anomaly threshold (was z=1.0→perpetual refit), remove stale regime_quality_ok from manifest, load model_state on scoring batches, disable forecast QA via config, schema-only feature hash |
| v11.15.3 | 2026-02-20 | Polars-only fast_features: remove pandas wrapper, HAS_POLARS guard, return_type params; fix rolling_spectral_energy crash; dead code cleanup |
| v11.15.2 | 2026-02-20 | Performance: 4 bottlenecks fixed (~270s/batch saved): apply(pd.to_numeric), episode PCA attribution, rolling_spectral_energy, impute_features |
| v11.15.1 | 2026-02-19 | Feature mismatch fix: protected_columns in impute_features prevents 632→630 drop on scoring batches; load_manifest_only() for cheap SQL manifest fetch |
| v11.15.0 | 2026-02-19 | Latent attribution activation: OMR per-sensor episode culprits, OMR-aware hotspot ranking (MaxAbsOMR, RankingScore), baseline data leakage fix, model persistence return value, QA checks for OMR attribution |
| v11.14.0 | 2026-02-19 | Log quality: deduplicated FUSE/DEGRADE logs, batch summary shows health % not z-scores, SUMMARY component to Loki, top_sensors truncation fix |
| v11.13.1 | 2026-02-18 | Remove dead SQL log sink (_SqlLogSink never wired to Console; ACM_RunLogs always empty) |
| v11.12.0 | 2026-02-18 | Metric-aware regime quality, DBCV retrain trigger fix, OMR/OutputManager performance, consolidated batch analytics summary |
| v11.11.0 | 2026-02-18 | Forecasting 563s→<5s: vectorize Monte Carlo slow path; cap forecast_resolution_hours=1.0h |
| v11.10.0 | 2026-02-18 | Fusion cleanup: delete combine() wrapper, named Spans; fix refit timestamp mismatch, triple timer, duplicate main() |
| v11.9.0 | 2026-02-18 | Fusion stability: cross-batch health comparability, remove double z-scoring, calibration persistence, 3× fusion speedup |
| v11.8.0 | 2026-02-12 | Adaptive pipeline: remove ONLINE/OFFLINE modes entirely, --force-retrain replaces --mode offline |
| v11.6.0 | 2026-02-08 | 6 critical fixes: transform error guard, model accumulation, spurious refits, training subsampling, false positive thresholds |
| v11.5.0 | 2026-01-28 | Anti-upsample guard, batch mode selection, refit loop fix |
| v11.4.0 | 2026-01-21 | Regime clustering: raw sensors only (circular masking fix — health-state features removed) |
| v11.3.4 | 2026-01-20 | RUL validation guards |
| v11.3.3 | 2026-01-18 | Contamination filtering for calibration |
| v11.3.2 | 2026-01-16 | Model compatibility validation |
| v11.3.0 | 2026-01-13 | Interactive installer, false positive reduction |
| v11.2.2 | 2026-01-04 | P0 analytical fixes (harmonic mean confidence, circular weight guard, tightened promotion) |
| v11.1.4 | 2025-12-24 | Detector correlation discount, maintenance reset detection, seasonal adjustment data flow fix |
| v11.0.0 | 2025-12-15 | Model lifecycle (COLDSTART→LEARNING→CONVERGED), confidence model, UNKNOWN regime |
| v10.3.0 | 2025-12-01 | Observability stack (Grafana, Tempo, Loki, Prometheus, Pyroscope) |
| v10.2.0 | 2025-12-16 | MHAL detector removed (redundant with PCA-T²) |
| v10.0.0 | 2025-12-04 | Unified forecasting, Monte Carlo RUL, 11→4 forecast tables |

---

**Document Version:** 11.15.5 | **Updated:** February 20, 2026

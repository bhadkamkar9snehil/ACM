# ACM - Automated Condition Monitoring

[![Version](https://img.shields.io/badge/version-11.14.0-blue)](#) [![Status](https://img.shields.io/badge/status-Production-brightgreen)](#) [![Python](https://img.shields.io/badge/python-3.11+-blue)](#) [![SQL Server](https://img.shields.io/badge/SQL%20Server-2019%2B-blue)](#)

**Predictive Maintenance for Industrial Equipment**

ACM is an autonomous condition monitoring system that ingests sensor data from industrial equipment, runs multi-detector anomaly detection, identifies operating regimes, and forecasts Remaining Useful Life (RUL). It transforms raw sensor streams into actionable maintenance intelligence.

---

## Table of Contents

- [What Problem Does ACM Solve?](#what-problem-does-acm-solve)
- [System Architecture](#system-architecture)
- [Core Concepts](#core-concepts)
- [Data Flow Pipeline](#data-flow-pipeline)
- [Detection Algorithms](#detection-algorithms)
- [Health Scoring](#health-scoring)
- [RUL Forecasting](#rul-forecasting)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running ACM](#running-acm)
- [Output Tables](#output-tables)
- [Grafana Dashboards](#grafana-dashboards)
- [Troubleshooting](#troubleshooting)
- [Documentation Map](#documentation-map)
- [Changelog](#changelog)

---

## What Problem Does ACM Solve?

Industrial equipment fails without warning. Maintenance teams face a costly tradeoff:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     THE MAINTENANCE DILEMMA                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  REACTIVE MAINTENANCE          vs          PREVENTIVE MAINTENANCE       │
│  ────────────────────                      ───────────────────────      │
│  Wait for failure                          Replace on schedule          │
│  ↓                                         ↓                            │
│  Emergency downtime                        Unnecessary replacements     │
│  Catastrophic damage                       Wasted parts & labor         │
│  Safety risks                              Over-maintenance costs       │
│                                                                         │
│                              ACM SOLUTION                               │
│                              ────────────                               │
│                     PREDICTIVE MAINTENANCE                              │
│                              ↓                                          │
│                   Detect degradation 7+ days early                      │
│                   Forecast remaining useful life                        │
│                   Identify which sensors are degrading                  │
│                   Prioritize by actual health state                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**ACM delivers:**
- **Early Detection**: Spot equipment degradation 7+ days before failure
- **Automatic Diagnosis**: Identify which sensors changed and why
- **Predictive Timing**: Forecast RUL with uncertainty bounds (P10/P50/P90)
- **Context-Aware Alerts**: Distinguish operating mode changes from real faults
- **Actionable Severity**: Prioritize by health state, not just alarm magnitude

---

## System Architecture

### High-Level Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              ACM SYSTEM ARCHITECTURE                          │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   EQUIPMENT     │     │   SQL SERVER    │     │   OBSERVABILITY │
│   SENSORS       │────▶│   HISTORIAN     │     │   STACK         │
│                 │     │                 │     │                 │
│ • Temperature   │     │ • Raw Data      │     │ • Grafana       │
│ • Pressure      │     │ • ACM Results   │     │ • Tempo Traces  │
│ • Vibration     │     │ • Model Cache   │     │ • Loki Logs     │
│ • Current       │     │                 │     │ • Prometheus    │
│ • Flow          │     │                 │     │ • Pyroscope     │
└─────────────────┘     └────────┬────────┘     └────────▲────────┘
                                 │                       │
                                 ▼                       │
                    ┌────────────────────────┐           │
                    │      ACM PIPELINE      │───────────┘
                    │                        │
                    │  ┌──────────────────┐  │
                    │  │ Feature Engine   │  │
                    │  └────────┬─────────┘  │
                    │           ▼            │
                    │  ┌──────────────────┐  │
                    │  │ 6-Head Detectors │  │
                    │  └────────┬─────────┘  │
                    │           ▼            │
                    │  ┌──────────────────┐  │
                    │  │ Regime Clustering│  │
                    │  └────────┬─────────┘  │
                    │           ▼            │
                    │  ┌──────────────────┐  │
                    │  │ Fusion & Episodes│  │
                    │  └────────┬─────────┘  │
                    │           ▼            │
                    │  ┌──────────────────┐  │
                    │  │ Forecasting      │  │
                    │  └──────────────────┘  │
                    └────────────────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Runtime** | Python 3.11 | Core pipeline execution |
| **Data Processing** | pandas, NumPy, scikit-learn | Feature engineering, ML models |
| **Database** | Microsoft SQL Server 2019+ | Historian data, results storage |
| **Connectivity** | pyodbc, T-SQL | SQL Server integration |
| **Visualization** | Grafana | Real-time dashboards |
| **Observability** | OpenTelemetry, Tempo, Loki, Prometheus | Tracing, logging, metrics |
| **Profiling** | Grafana Pyroscope | Performance analysis |

---

## Core Concepts

### Operating Regimes

Equipment operates in different **modes** (regimes) based on load, speed, and environmental conditions. ACM automatically discovers these regimes using clustering on raw sensor values:

```
┌─────────────────────────────────────────────────────────────────┐
│                    REGIME CLUSTERING                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Raw Sensor Values                                              │
│   ─────────────────                                              │
│   • Load (%)        ──┐                                          │
│   • Speed (RPM)       │                                          │
│   • Flow (m³/h)       ├──▶  K-Means / HDBSCAN  ──▶  Regime 0-N   │
│   • Pressure (bar)    │        Clustering                        │
│   • Inlet Temp (°C)  ─┘                                          │
│                                                                  │
│   WHY THIS MATTERS:                                              │
│   ─────────────────                                              │
│   Equipment at 50% load behaves differently than at 100% load.   │
│   An "anomaly" at startup might be normal, but the same reading  │
│   during steady-state operation indicates a real problem.        │
│                                                                  │
│   ARCHITECTURAL PRINCIPLE (v11.4.0):                             │
│   ──────────────────────────────────                             │
│   • Regimes = HOW equipment operates (raw sensors)               │
│   • Detectors = IF equipment is healthy (z-scores)               │
│   • These are ORTHOGONAL - never mix detector outputs into       │
│     regime clustering (causes circular masking)                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Detector Fusion

ACM uses **six independent detectors** because different faults manifest differently:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DETECTOR ENSEMBLE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                        │
│   │    AR1      │   │  PCA-SPE    │   │  PCA-T²     │                        │
│   │  Detector   │   │  Detector   │   │  Detector   │                        │
│   │             │   │             │   │             │                        │
│   │ Sensor      │   │ Decoupling  │   │ Operating   │                        │
│   │ drift/spike │   │ detection   │   │ point shift │                        │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘                        │
│          │                 │                 │                               │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                        │
│   │  IForest    │   │    GMM      │   │    OMR      │                        │
│   │  Detector   │   │  Detector   │   │  Detector   │                        │
│   │             │   │             │   │             │                        │
│   │ Rare states │   │ Cluster     │   │ Cross-sensor│                        │
│   │ isolation   │   │ membership  │   │ residuals   │                        │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘                        │
│          │                 │                 │                               │
│          └────────────┬────┴─────────────────┘                               │
│                       ▼                                                      │
│              ┌─────────────────┐                                             │
│              │   WEIGHTED      │                                             │
│              │   FUSION        │                                             │
│              │                 │                                             │
│              │  fused_z =      │                                             │
│              │  Σ(wᵢ × zᵢ)    │                                             │
│              └────────┬────────┘                                             │
│                       ▼                                                      │
│              ┌─────────────────┐                                             │
│              │  Single Fused   │                                             │
│              │  Anomaly Score  │                                             │
│              └─────────────────┘                                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Model Lifecycle

ACM models progress through maturity states:

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODEL LIFECYCLE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   COLDSTART ──▶ LEARNING ──▶ CONVERGED ──▶ DEPRECATED           │
│       │            │            │              │                 │
│       ▼            ▼            ▼              ▼                 │
│   First run    Building     Stable,       Schema or             │
│   No history   baselines    reliable      config changed        │
│                             outputs                              │
│                                                                  │
│   Promotion Criteria (LEARNING → CONVERGED):                     │
│   • Minimum 5 successful runs                                    │
│   • Silhouette score ≥ 0.40                                      │
│   • Stability ≥ 0.75                                             │
│   • 7+ days of history                                           │
│                                                                  │
│   RUL Reliability:                                               │
│   • COLDSTART/LEARNING: "NOT_RELIABLE" flag                      │
│   • CONVERGED: Full confidence intervals                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Pipeline

### Complete Pipeline Execution

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         ACM PIPELINE PHASES                                   │
│                    (Executed per equipment per batch)                         │
└──────────────────────────────────────────────────────────────────────────────┘

Phase 1: INITIALIZATION
├── Parse arguments (--equip, --start-time, --end-time, --mode)
├── Load config from SQL (ACM_Config table)
├── Determine PipelineMode (ONLINE/OFFLINE)
├── Initialize OutputManager
└── Create RunID

Phase 2: DATA CONTRACT VALIDATION
├── DataContract.validate(raw_data)
├── Check sensor coverage (min 70% required)
├── Validate timestamp column and cadence
└── Write ACM_DataContractValidation

Phase 3: DATA LOADING
├── Load historian data via stored procedure
├── Apply coldstart split (60% train / 40% score)
├── Deduplicate and ensure local timestamps
└── Output: train_df, score_df

Phase 4: FEATURE ENGINEERING
├── Compute rolling statistics (mean, std, min, max)
├── Compute lag features
├── Compute z-scores per sensor
├── Impute missing values from training medians
└── Output: train_features, score_features

Phase 5: MODEL TRAINING (OFFLINE mode only)
├── Fit AR1 detector (autoregressive residuals)
├── Fit PCA detector (dimensionality reduction)
├── Fit IForest detector (isolation forest)
├── Fit GMM detector (Gaussian mixture)
├── Fit OMR detector (overall model residual)
└── Cache models to SQL ModelRegistry

Phase 6: DETECTOR SCORING
├── Score all detectors on score data
├── Compute z-scores per detector
└── Output: ar1_z, pca_spe_z, pca_t2_z, iforest_z, gmm_z, omr_z

Phase 7: REGIME LABELING
├── Build regime basis (raw sensor values only)
├── Run clustering (HDBSCAN primary, GMM fallback)
├── Assign labels and confidence
└── Write ACM_RegimeTimeline

Phase 8: CALIBRATION
├── Score TRAIN data for calibration baseline
├── Compute adaptive thresholds (P99-based)
├── Self-tune for target false positive rate
└── Write ACM_Thresholds

Phase 9: FUSION
├── Auto-tune detector weights
├── Compute fused_z (weighted combination)
├── Tune CUSUM parameters
└── Write ACM_Scores_Wide

Phase 10: EPISODE DETECTION
├── CUSUM change-point detection
├── Identify episode start/end times
├── Compute culprit sensors per episode
└── Write ACM_Anomaly_Events

Phase 11: ANALYTICS GENERATION
├── Generate health timeline
├── Generate sensor defects
├── Generate hotspot analysis
└── Write ACM_HealthTimeline, ACM_SensorDefects

Phase 12: FORECASTING
├── Load health history
├── Fit degradation model (Holt-Winters)
├── Generate health forecast (30-day horizon)
├── Compute RUL with Monte Carlo (P10/P50/P90)
├── Identify top-3 culprit sensors
└── Write ACM_RUL, ACM_HealthForecast, ACM_SensorForecast

Phase 13: FINALIZATION
├── Write PCA loadings
├── Write run statistics
├── Update model lifecycle state
└── Commit all SQL transactions
```

### Timing Breakdown (Typical 100K-row batch)

| Phase | Duration | Notes |
|-------|----------|-------|
| Data Loading | ~2-3s | SQL stored procedure |
| Feature Engineering | ~2s | Vectorized pandas |
| Detector Scoring | ~1s | 6 detectors in parallel |
| Regime Clustering | ~0.5s | K-Means on raw sensors |
| Fusion + Episodes | ~0.5s | CUSUM change-point |
| Forecasting | ~0.3s | Monte Carlo simulation |
| SQL Writes | ~5-10s | 20+ tables |
| **Total** | **~15-30s** | Per equipment per batch |

---

## Detection Algorithms

### AR1 Detector (Autoregressive Residuals)

Detects sensor drift and sudden spikes by modeling each sensor as an AR(1) process:

```
┌─────────────────────────────────────────────────────────────────┐
│                      AR1 DETECTOR                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Model:  x(t) = φ × x(t-1) + ε(t)                               │
│                                                                  │
│   Where:                                                         │
│   • x(t) = sensor value at time t                                │
│   • φ = autoregressive coefficient (fitted from training)        │
│   • ε(t) = residual (prediction error)                           │
│                                                                  │
│   Detection:                                                     │
│   • z_score = (ε(t) - μ_train) / σ_train                         │
│   • Large residuals indicate unexpected changes                  │
│                                                                  │
│   Good for: Gradual sensor drift, sudden spikes, trend changes   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### PCA Detector (Principal Component Analysis)

Detects multivariate anomalies by projecting data onto principal components:

```
┌─────────────────────────────────────────────────────────────────┐
│                      PCA DETECTOR                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Training:                                                      │
│   1. Standardize features (zero mean, unit variance)             │
│   2. Fit PCA to learn principal components                       │
│   3. Retain components explaining 95% variance                   │
│                                                                  │
│   Two Metrics:                                                   │
│                                                                  │
│   SPE (Squared Prediction Error):                                │
│   ┌─────────────────────────────────────────┐                    │
│   │ SPE = ||x - x̂||²                        │                    │
│   │     = Σ(xᵢ - x̂ᵢ)²                       │                    │
│   │                                         │                    │
│   │ Measures: Reconstruction error          │                    │
│   │ Detects: Decoupling, sensor faults      │                    │
│   └─────────────────────────────────────────┘                    │
│                                                                  │
│   T² (Hotelling's T-squared):                                    │
│   ┌─────────────────────────────────────────┐                    │
│   │ T² = Σ(tᵢ² / λᵢ)                        │                    │
│   │                                         │                    │
│   │ Measures: Distance in PC space          │                    │
│   │ Detects: Operating point anomalies      │                    │
│   └─────────────────────────────────────────┘                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### IForest Detector (Isolation Forest)

Detects anomalies by measuring how easily a point can be isolated:

```
┌─────────────────────────────────────────────────────────────────┐
│                    ISOLATION FOREST                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Concept:                                                       │
│   • Anomalies are "few and different"                            │
│   • Easier to isolate than normal points                         │
│   • Fewer splits needed to separate them                         │
│                                                                  │
│   Algorithm:                                                     │
│   1. Build forest of random isolation trees                      │
│   2. For each tree, randomly split features                      │
│   3. Count average path length to isolate point                  │
│   4. Short path = anomaly, Long path = normal                    │
│                                                                  │
│   Score:                                                         │
│   s(x) = 2^(-E[h(x)] / c(n))                                     │
│                                                                  │
│   Where:                                                         │
│   • E[h(x)] = average path length                                │
│   • c(n) = average path length in unsuccessful search            │
│                                                                  │
│   Good for: Rare transient states, novel operating conditions    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### GMM Detector (Gaussian Mixture Model)

Detects anomalies using probabilistic cluster membership:

```
┌─────────────────────────────────────────────────────────────────┐
│                   GAUSSIAN MIXTURE MODEL                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Model:                                                         │
│   p(x) = Σₖ πₖ × N(x | μₖ, Σₖ)                                   │
│                                                                  │
│   Where:                                                         │
│   • πₖ = mixture weight for cluster k                            │
│   • μₖ = mean of cluster k                                       │
│   • Σₖ = covariance of cluster k                                 │
│                                                                  │
│   Detection:                                                     │
│   • Compute log-likelihood: log p(x)                             │
│   • Low likelihood = anomaly                                     │
│   • z_score = (log_lik - μ_train) / σ_train                      │
│                                                                  │
│   Good for: Mode confusion, operating state uncertainty          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### OMR Detector (Overall Model Residual)

Detects cross-sensor relationship breakdowns:

```
┌─────────────────────────────────────────────────────────────────┐
│                 OVERALL MODEL RESIDUAL                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Concept:                                                       │
│   • Train a model to predict each sensor from others             │
│   • Healthy equipment: sensors are correlated                    │
│   • Fault: correlations break down                               │
│                                                                  │
│   Algorithm:                                                     │
│   1. For each sensor sᵢ:                                         │
│      - Train model: ŝᵢ = f(s₁, s₂, ..., sₙ \ sᵢ)                 │
│      - Compute residual: rᵢ = sᵢ - ŝᵢ                            │
│   2. Combine residuals: OMR = √(Σrᵢ²)                            │
│   3. Normalize to z-score                                        │
│                                                                  │
│   Good for: Bearing degradation, mechanical wear, coupling       │
│             failures where sensor relationships change           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Fusion Algorithm

Combines detector outputs with learned weights:

```
┌─────────────────────────────────────────────────────────────────┐
│                    DETECTOR FUSION                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   fused_z = Σ(wᵢ × zᵢ) / Σwᵢ                                     │
│                                                                  │
│   Default Weights:                                               │
│   ┌────────────┬────────┐                                        │
│   │ Detector   │ Weight │                                        │
│   ├────────────┼────────┤                                        │
│   │ ar1_z      │ 0.25   │                                        │
│   │ pca_spe_z  │ 0.20   │                                        │
│   │ pca_t2_z   │ 0.15   │                                        │
│   │ iforest_z  │ 0.15   │                                        │
│   │ gmm_z      │ 0.15   │                                        │
│   │ omr_z      │ 0.10   │                                        │
│   └────────────┴────────┘                                        │
│                                                                  │
│   Weight Tuning:                                                 │
│   • Primary method: Episode separability (maximize AUROC)        │
│   • Fallback: Statistical diversity (variance + correlation)    │
│   • Correlation discount: Spearman |r| > 0.5 triggers weight    │
│     reduction (capped at 30%) to prevent double-counting        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Health Scoring

### Health Index Calculation

```
┌─────────────────────────────────────────────────────────────────┐
│                    HEALTH INDEX (0-100%)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Formula (v10.1.0 sigmoid):                                     │
│   ──────────────────────────                                     │
│   normalized = (|fused_z| - z_thresh/2) / (z_thresh/4)           │
│   sigmoid = 1 / (1 + exp(-normalized × steepness))               │
│   health = 100 × (1 - sigmoid)                                   │
│                                                                  │
│   Where:                                                         │
│   • fused_z = weighted combination of detector z-scores          │
│   • z_thresh = threshold (default: 5.0)                          │
│   • steepness = slope control (default: 1.5)                     │
│                                                                  │
│   Smoothing:                                                     │
│   ───────────                                                    │
│   health_smoothed = α × health_raw + (1 - α) × health_prev       │
│                                                                  │
│   Where:                                                         │
│   • α = smoothing factor (default: 0.3)                          │
│   • Higher α = more responsive, noisier                          │
│   • Lower α = smoother, slower to react                          │
│                                                                  │
│   Interpretation:                                                │
│   ───────────────                                                │
│   │ 80-100% │ HEALTHY    │ Normal operation              │       │
│   │ 50-80%  │ DEGRADING  │ Monitor closely               │       │
│   │ 20-50%  │ CRITICAL   │ Schedule maintenance          │       │
│   │ 0-20%   │ FAILURE    │ Immediate intervention        │       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Confidence Calculation

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONFIDENCE MODEL                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Confidence = Harmonic Mean of:                                 │
│   ─────────────────────────────                                  │
│   • Model maturity (COLDSTART=0.3, LEARNING=0.6, CONVERGED=1.0)  │
│   • Data coverage (% of expected sensors present)                │
│   • Regime confidence (cluster assignment certainty)             │
│   • Temporal stability (consistency over recent window)          │
│                                                                  │
│   Why Harmonic Mean?                                             │
│   ───────────────────                                            │
│   • Penalizes imbalanced factors                                 │
│   • If ANY factor is low, overall confidence is low              │
│   • Prevents false confidence when one factor is weak            │
│                                                                  │
│   Example:                                                       │
│   • Arithmetic mean: (0.1 + 0.9 + 0.9 + 0.9) / 4 = 0.70          │
│   • Harmonic mean: 4 / (1/0.1 + 1/0.9 + 1/0.9 + 1/0.9) = 0.31   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## RUL Forecasting

### Remaining Useful Life Calculation

```
┌─────────────────────────────────────────────────────────────────┐
│                    RUL FORECASTING                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Step 1: Fit Degradation Model                                  │
│   ──────────────────────────────                                 │
│   • Load health history (last 30-90 days)                        │
│   • Detect maintenance resets (health jumps > 15%)               │
│   • Use only post-maintenance data for trend                     │
│   • Fit Holt-Winters exponential smoothing                       │
│                                                                  │
│   Step 2: Monte Carlo Simulation                                 │
│   ───────────────────────────────                                │
│   • Generate N=1000 random trajectories                          │
│   • Add noise based on historical variance                       │
│   • Project forward until health crosses threshold (20%)         │
│   • Record time-to-failure for each trajectory                   │
│                                                                  │
│   Step 3: Confidence Intervals                                   │
│   ──────────────────────────────                                 │
│   • P10 = 10th percentile (optimistic)                           │
│   • P50 = 50th percentile (median estimate)                      │
│   • P90 = 90th percentile (pessimistic)                          │
│                                                                  │
│   Visualization:                                                 │
│                                                                  │
│   Health                                                         │
│     │                                                            │
│   100├─────╲                                                     │
│     │      ╲                                                     │
│    80├───────╲                                                   │
│     │         ╲╲╲╲╲╲╲╲╲╲  (Monte Carlo trajectories)             │
│    60├───────────╲╲╲╲╲╲╲                                         │
│     │              ╲╲╲╲╲                                         │
│    40├────────────────╲╲                                         │
│     │                                                            │
│    20├─────────────────────────  (Failure threshold)             │
│     │         │    │    │                                        │
│     └─────────┴────┴────┴──────────▶ Time                        │
│              P10  P50  P90                                       │
│                                                                  │
│   Output:                                                        │
│   • RUL_Hours: Estimated hours until failure                     │
│   • P10_LowerBound: Optimistic estimate                          │
│   • P50_Median: Best estimate                                    │
│   • P90_UpperBound: Pessimistic estimate                         │
│   • TopSensor1/2/3: Which sensors are driving degradation        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### RUL Validation Guards

ACM rejects implausible RUL predictions:

| Condition | Action |
|-----------|--------|
| RUL < 1h AND Health > 70% | Reject (implausible imminent failure) |
| FailureProbability = 100% AND RUL > 100h | Reject (inconsistent) |
| RUL is negative, infinite, or NaN | Reject (invalid) |
| Model not CONVERGED | Mark as "NOT_RELIABLE" |

---

## Installation

### Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.11+ | Runtime |
| SQL Server | 2019+ | Data storage (production) |
| Docker Desktop | Latest | Observability stack |
| ODBC Driver | 17 or 18 | SQL connectivity |

### Method 1: Interactive Installer (Recommended)

```powershell
# Install questionary for interactive prompts
pip install questionary

# Run the installer wizard
python install/acm_installer.py
```

The wizard guides you through:
1. **Prerequisites Check** - Python, Docker, ODBC drivers
2. **Docker Setup** - Automatic download if missing
3. **Observability Stack** - Grafana, Tempo, Loki, Prometheus, Pyroscope
4. **SQL Server Setup** - Database creation and schema (optional)
5. **Configuration** - Generates `sql_connection.ini`
6. **Verification** - Tests all endpoints

### Method 2: Manual Installation

**Step 1: Clone and install dependencies**
```powershell
git clone https://github.com/bhadkamkar9snehil/ACM.git
cd ACM
pip install -r requirements.txt
```

**Step 2: Start observability stack**
```powershell
cd install/observability
docker compose up -d

# Verify (expect 6 containers)
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Expected containers:
| Container | Port | Purpose |
|-----------|------|---------|
| acm-grafana | 3000 | Dashboards (admin/admin) |
| acm-alloy | 4317, 4318 | OTLP collector |
| acm-tempo | 3200 | Distributed traces |
| acm-loki | 3100 | Log aggregation |
| acm-prometheus | 9090 | Metrics |
| acm-pyroscope | 4040 | Profiling |

**Step 3: Configure SQL connection**
```powershell
copy configs\sql_connection.example.ini configs\sql_connection.ini
```

Edit `configs/sql_connection.ini`:
```ini
[acm]
server = localhost\SQLEXPRESS
database = ACM
trusted_connection = yes
driver = ODBC Driver 18 for SQL Server
TrustServerCertificate = yes
```

**Step 4: Setup database (if using SQL Server)**
```powershell
# Create database and schema
sqlcmd -S "localhost\SQLEXPRESS" -E -i "install/sql/00_create_database.sql"
sqlcmd -S "localhost\SQLEXPRESS" -d ACM -E -i "install/sql/14_complete_schema.sql"

# Verify connection
python scripts/sql/verify_acm_connection.py
```

**Step 5: Sync configuration**
```powershell
python scripts/sql/populate_acm_config.py
```

---

## Configuration

### Configuration File: `configs/config_table.csv`

ACM is configured via a CSV file with 238+ parameters. Key categories:

| Category | Example Parameters | Purpose |
|----------|-------------------|---------|
| `data.*` | `sampling_secs`, `min_rows` | Data ingestion |
| `features.*` | `window_sizes`, `polars_threshold` | Feature engineering |
| `models.*` | `pca.n_components`, `iforest.contamination` | Detector settings |
| `regimes.*` | `auto_k.k_min`, `auto_k.k_max` | Regime clustering |
| `episodes.*` | `cpd.k_sigma`, `min_duration_sec` | Episode detection |
| `forecasting.*` | `horizon_days`, `mc_samples` | RUL forecasting |
| `thresholds.*` | `alert_z`, `warn_z` | Alert thresholds |
| `sql.*` | `pool_min`, `pool_max` | SQL connection |

### Equipment-Specific Overrides

```csv
EquipID,ParamPath,Value
0,data.sampling_secs,1800         # Global default (all equipment)
1,data.sampling_secs,1800         # FD_FAN specific
2621,data.sampling_secs,3600      # GAS_TURBINE specific (1 hour cadence)
```

### Syncing Configuration

After editing `config_table.csv`, sync to SQL:
```powershell
python scripts/sql/populate_acm_config.py
```

---

## Running ACM

### Pipeline Modes (v11.5.0)

ACM operates in two distinct pipeline modes that control model behavior:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PIPELINE MODE SELECTION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  OFFLINE MODE (Training)              ONLINE MODE (Scoring)                 │
│  ─────────────────────                ────────────────────                  │
│  • Train detector models              • Use cached models only              │
│  • Discover operating regimes         • No regime discovery                 │
│  • Calibrate thresholds               • Score incoming data                 │
│  • Full feature engineering           • Apply existing thresholds           │
│                                                                             │
│  Use for:                             Use for:                              │
│  • Coldstart (first run)              • Production scoring                  │
│  • Historical backfill                • Real-time monitoring                │
│  • Scheduled model refresh            • After models CONVERGED              │
│  • After config changes               • Normal batch processing             │
│                                                                             │
│  BATCH MODE SELECTION (sql_batch_runner.py):                                │
│  ───────────────────────────────────────────                                │
│  Coldstart batch (no models exist)   → OFFLINE (train once)                 │
│  Post-coldstart batches              → ONLINE (score only)                  │
│  Explicit --mode override            → Uses specified mode                  │
│                                                                             │
│  IMPORTANT: Models must stabilize before reliable RUL predictions.          │
│  The batch runner automatically handles mode selection.                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Resampling (v11.5.0 Anti-Upsample Guard)

ACM NEVER upsamples data. If `data.sampling_secs` is set to a value smaller than the native data cadence, ACM will use the native cadence instead:

```
Native cadence: 600 seconds (10-minute intervals)
Config sampling_secs: 60 seconds (requested)

Result: ACM uses 600 seconds (native) - NO UPSAMPLING
Log: "ANTI-UPSAMPLE: Requested resample (60s) < native cadence (600.0s)"
```

**Why this matters**: Upsampling creates synthetic data via interpolation, inflating row counts 10x and corrupting calibration, anomaly detection, and all downstream analytics.

**Recommended config**: Set `data.sampling_secs` to `auto` (string) to always use native cadence.

### Option 1: Production Batch Processing (Recommended)

Continuous monitoring with automatic batching:

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
| `--max-batches` | Limit batches (for testing) |

### Option 2: Single Run (Testing)

Process a specific time range:

```powershell
python -m core.acm_main \
    --equip FD_FAN \
    --start-time "2024-01-01T00:00:00" \
    --end-time "2024-01-31T23:59:59" \
    --mode offline
```

| Argument | Description |
|----------|-------------|
| `--equip` | Equipment code |
| `--start-time` | ISO 8601 start time |
| `--end-time` | ISO 8601 end time |
| `--mode` | `offline` (full training), `online` (scoring only), `auto` |

### Option 3: Analytics-Only Mode (No SQL)

Quick analysis without SQL setup:

```powershell
python acm_distilled.py \
    --equip FD_FAN \
    --start-time "2024-01-01T00:00:00" \
    --end-time "2024-01-31T23:59:59"
```

Output: CSV files in `artifacts/` directory.

---

## Output Tables

### Primary Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `ACM_Scores_Wide` | Detector z-scores | Timestamp, ar1_z, pca_spe_z, fused_z |
| `ACM_HealthTimeline` | Health index history | Timestamp, HealthIndex, Confidence |
| `ACM_RegimeTimeline` | Regime assignments | Timestamp, RegimeLabel, HealthState |
| `ACM_Anomaly_Events` | Detected episodes | StartTime, EndTime, Severity |
| `ACM_RUL` | RUL predictions | RUL_Hours, P10/P50/P90, TopSensor1/2/3 |
| `ACM_HealthForecast` | Health trajectory | ForecastTime, ForecastHealth |
| `ACM_SensorForecast` | Sensor predictions | SensorName, ForecastValue |

### Operational Tables

| Table | Purpose |
|-------|---------|
| `ACM_Runs` | Run metadata (start, end, status) |
| `ACM_RunLogs` | Structured log messages |
| `ACM_Config` | Configuration parameters |
| `Equipment` | Equipment registry |
| `ACM_ModelHistory` | Model versions and metadata |

### Dashboard Views (Pre-built)

| View | Purpose |
|------|---------|
| `vw_ACM_CurrentHealth` | Latest health per equipment |
| `vw_ACM_HealthHistory` | Health time series |
| `vw_ACM_ActiveDefects` | Active sensor defects |
| `vw_ACM_RULSummary` | RUL overview |
| `vw_ACM_EquipmentOverview` | Fleet summary |

---

## Grafana Dashboards

### Accessing Grafana

```
URL: http://localhost:3000
Username: admin
Password: admin
```

### Pre-Built Dashboards

| Dashboard | Purpose |
|-----------|---------|
| **Equipment Overview** | Fleet-wide health summary |
| **Equipment Detail** | Single equipment deep-dive |
| **RUL Forecast** | Remaining useful life trends |
| **Detector Analysis** | Individual detector scores |
| **Regime Analysis** | Operating regime distribution |
| **ACM Observability** | Pipeline performance metrics |

### Key Panels

- **Health Gauge**: Current health percentage
- **RUL Countdown**: Days until predicted failure
- **Detector Scores**: Time series of all 6 detectors
- **Regime Timeline**: Operating mode over time
- **Episode Markers**: Anomaly events on timeline
- **Top Contributors**: Sensors driving anomalies

---

## Troubleshooting

### Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "NOOP - No data" | Data cadence mismatch | Check `data.sampling_secs` in config |
| "RUL NOT_RELIABLE" | Model not converged | Run 5+ batches to reach CONVERGED |
| Episodes every batch | Threshold too low | Increase `episodes.cpd.k_sigma` |
| Health score flat | Baseline not seeding | Increase `baseline.seed_size` |
| SQL connection timeout | Pool exhausted | Increase `sql.pool_max` |
| Regime oscillation | Clustering unstable | Increase `regimes.smoothing.window` |

### Diagnostic Commands

```powershell
# Test SQL connectivity
python scripts/sql/verify_acm_connection.py

# Check recent run logs
sqlcmd -S "server\instance" -d ACM -E -Q "SELECT TOP 20 * FROM ACM_RunLogs ORDER BY LoggedAt DESC"

# Check run status
sqlcmd -S "server\instance" -d ACM -E -Q "SELECT TOP 10 * FROM ACM_Runs ORDER BY CreatedAt DESC"

# Verify regime assignments
sqlcmd -S "server\instance" -d ACM -E -Q "SELECT RegimeLabel, COUNT(*) FROM ACM_RegimeTimeline GROUP BY RegimeLabel"
```

---

## Documentation Map

| Topic | Document |
|-------|----------|
| System architecture | [docs/ACM_SYSTEM_OVERVIEW.md](docs/ACM_SYSTEM_OVERVIEW.md) |
| SQL schema reference | [docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md](docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md) |
| Grafana queries | [docs/GRAFANA_DASHBOARD_QUERIES.md](docs/GRAFANA_DASHBOARD_QUERIES.md) |
| Analytical audit | [docs/ACM_V11_ANALYTICAL_AUDIT.md](docs/ACM_V11_ANALYTICAL_AUDIT.md) |
| Cold-start strategy | [docs/COLDSTART_MODE.md](docs/COLDSTART_MODE.md) |
| Adding equipment | [docs/EQUIPMENT_IMPORT_PROCEDURE.md](docs/EQUIPMENT_IMPORT_PROCEDURE.md) |
| Observability stack | [install/observability/README.md](install/observability/README.md) |
| OMR detector | [docs/OMR_DETECTOR.md](docs/OMR_DETECTOR.md) |
| Forecasting | [docs/FORECASTING_ARCHITECTURE.md](docs/FORECASTING_ARCHITECTURE.md) |

---

## Project Structure

```
ACM/
├── core/                    # Main pipeline code
│   ├── acm_main.py         # Pipeline orchestrator
│   ├── ar1_detector.py     # AR1 detector
│   ├── regimes.py          # Regime clustering
│   ├── fuse.py             # Detector fusion
│   ├── forecast_engine.py  # RUL forecasting
│   ├── output_manager.py   # SQL/CSV writing
│   └── sql_client.py       # SQL connectivity
├── scripts/
│   ├── sql_batch_runner.py # Production batch runner
│   └── sql/                # SQL utilities
├── configs/
│   ├── config_table.csv    # Configuration parameters
│   └── sql_connection.ini  # SQL credentials (gitignored)
├── install/
│   ├── acm_installer.py    # Interactive installer
│   ├── observability/      # Docker Compose stack
│   └── sql/                # Database setup scripts
├── grafana_dashboards/     # Dashboard JSON exports
├── docs/                   # Documentation
├── tests/                  # Test suites
└── utils/                  # Utilities (config, version)
```

---

## Changelog

### v11.14.0 (2026-02-19) - Log Quality & Batch Summary Overhaul
- **FIX**: Eliminated duplicate FUSE Spearman correlation logs (12-15 lines per batch)
- **FIX**: Degradation model logs now tagged `[global]` / `[regime-N]` — no more ambiguous duplicates
- **FIX**: Batch summary now shows real health index (0-100%) instead of raw Z-scores
- **FIX**: Batch summary uses `Console.info(component="SUMMARY")` — pushed to Loki, searchable
- **FIX**: Forecast log `top_sensors` truncation bug — was showing `sen` instead of full sensor names
- **REMOVED**: `>>>` prefix from batch summary (replaced `Console.status` with `Console.info`)

### v11.4.0 (2026-01-21) - Regime Clustering Architectural Fix
**BREAKING CHANGE**: Regime clustering now uses **RAW SENSOR VALUES ONLY**

- **REMOVED**: `_add_health_state_features()` function from `core/regimes.py`
- **REMOVED**: `health_ensemble_z`, `health_trend`, `health_quartile` from regime basis
- **REMOVED**: `HEALTH_STATE_KEYWORDS` constant
- **BUMP**: `REGIME_MODEL_VERSION` 3.1 → 4.0 (forces model retraining)

**Rationale**: Using detector z-scores in regime clustering created circular masking:
1. Equipment degrades → detector z-scores rise
2. Health-state features cause point to cluster into "new regime"
3. New regime gets fresh baseline → degradation masked
4. Equipment appears "healthy in its current regime"

**Correct Architecture**:
- **Regimes** = HOW equipment operates (load, speed, flow, pressure)
- **Detectors** = IF equipment is healthy within that operating mode
- These are **ORTHOGONAL** concerns that must not be mixed

### v11.3.4 (2026-01-20) - RUL Validation Guard
- **NEW**: RUL validation logic prevents implausible predictions
  - Rejects RUL < 1h when health > 70%
  - Rejects FailureProbability=100% when RUL > 100h
  - Rejects negative, infinite, or NaN values

### v11.3.3 (2026-01-18) - Contamination Filtering
- **NEW**: `CalibrationContaminationFilter` class filters anomalous samples before calibration
- **METHODS**: iterative_mad (default), iqr, z_trim, hybrid
- **IMPACT**: More sensitive detection, ~25% reduction in false negatives

### v11.3.2 (2026-01-16) - Model Compatibility Validation
- **NEW**: `validate_model_feature_compatibility()` validates columns before model loading
- **NEW**: `reconcile_detector_flags_with_loaded_models()` syncs flags with availability
- Models with mismatched features are discarded and retrained

### v11.3.1 (2026-01-15) - Regime Labeling Conceptual Fix
- **BREAKING**: `predict_regime_with_confidence()` returns 3-tuple (labels, confidence, is_novel)
- **CONCEPTUAL FIX**: Equipment is ALWAYS in some operating state, never "unknown"
- **NEW**: `is_novel` flag replaces UNKNOWN_REGIME_LABEL (-1)

### v11.3.0 (2026-01-13) - Interactive Installer & False Positive Reduction
- **NEW**: Interactive installer wizard: `python install/acm_installer.py`
- **NEW**: Windows 10/11 and Server 2019/2022 officially supported
- **IMPROVED**: False positive reduction: 70% → 30% (2.3× improvement)
- **TESTS**: 102 installer tests added

### v11.2.2 (2026-01-04) - P0 Analytical Fixes
- **P0 FIX #1**: Circular weight tuning guard defaults to True
- **P0 FIX #4**: Confidence calculation changed from geometric to harmonic mean
- **P0 FIX #10**: Tightened promotion criteria (silhouette 0.15→0.40, stability 0.6→0.75)
- **AUDIT**: Comprehensive analytical review in `docs/ACM_V11_ANALYTICAL_AUDIT.md`

### v11.1.6 (2025-12-28) - Regime Analytical Correctness
- **REGIME_MODEL_VERSION**: Bumped to 3.0
- **FIX #1**: Created tag taxonomy separating operating variables from condition indicators
- **FIX #2**: Uniform scaling of entire basis (PCA + raw)
- **FIX #3**: Calibrated UNKNOWN threshold using P95 distance
- **FIX #4**: Label mapping for stable regime labels

### v11.1.5 (2025-12-26) - Database Integrity
- All 92 ACM tables have IDENTITY columns
- Relationship columns use implicit references (not FK constraints)

### v11.1.4 (2025-12-24) - Analytical Correctness Fixes
- **FIX**: Generalized correlation adjustment for ALL detector pairs
- **FIX**: Maintenance reset detection in degradation model
- **FIX**: Seasonal adjustment data flow bug

### v11.0.0 (2025-12-15) - Model Lifecycle & Confidence
- **NEW**: ONLINE/OFFLINE pipeline mode separation
- **NEW**: MaturityState lifecycle (COLDSTART → LEARNING → CONVERGED → DEPRECATED)
- **NEW**: Unified confidence model with ReliabilityStatus
- **NEW**: RUL reliability gating
- **NEW**: UNKNOWN regime (label=-1) for low-confidence assignments

### v10.3.0 (2025-12-01) - Observability Stack
- **NEW**: Docker-based observability (Grafana, Tempo, Loki, Prometheus, Pyroscope)
- **NEW**: `Console` class for unified logging
- **REMOVED**: Legacy loggers (`utils/logger.py`, `utils/acm_logger.py`)

---

**Version**: 11.14.0 | **Updated**: February 19, 2026

*For implementation details, see [docs/ACM_SYSTEM_OVERVIEW.md](docs/ACM_SYSTEM_OVERVIEW.md)*

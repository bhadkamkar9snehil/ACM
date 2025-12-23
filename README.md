# ACM - Automated Condition Monitoring System

ACM is a predictive maintenance and equipment health monitoring system for industrial assets. It ingests sensor data from equipment (fans, turbines, motors, etc.), applies machine learning and statistical analysis to detect anomalies, forecasts equipment health and remaining useful life (RUL), and delivers actionable insights through Grafana dashboards.

**Current Version:** v10.4.0 - Tactical Stability Improvements *(In Progress - 21% complete)*

**Key Value**: Engineers can understand **what is degrading**, **when it started**, **which sensors are responsible**, and **when failure is likely** - all through automated analysis and visual dashboards.

For complete implementation details, see `docs/ACM_SYSTEM_OVERVIEW.md`.

---

## 🚨 v10.4.0 Status Update (2025-12-23)

**Question**: Is v10.3 completely unusable?  
**Answer**: **NO** - v10.3 is usable but unstable (Grade: B-)

**What's Working**: Core analytics (6 detectors, fusion, health tracking, episodes)  
**What's Broken**: Missing safety gates cause misleading outputs in edge cases

**Solution**: v10.4 tactical improvements - "Amputate, don't fix"

### Progress: 3 of 8 Phases Complete (21%)

✅ **Phase 1: UNKNOWN Regime Support** - System can now say "I don't know"  
✅ **Phase 2: RUL Reliability Gating** - Prevents unreliable predictions  
✅ **Phase 3: Data Contract Validation** - Rejects corrupt data at entry  
⏳ **Phases 4-8**: Wire contracts, fix leakage, consolidate, test (8-11 hours remaining)

**See**: [`docs/V10.3_AUDIT_REPORT.md`](docs/V10.3_AUDIT_REPORT.md) for full audit  
**See**: [`docs/V10.4_SUMMARY.md`](docs/V10.4_SUMMARY.md) for implementation status

---

## Recent Updates (December 2025)

### v10.4.0 - Tactical Stability Improvements *(In Progress)*
Critical safety improvements to address v11 architectural requirements:
- **UNKNOWN Regime Support**: System can now say "I don't know" instead of forcing nearest-regime assignment
  - Added `REGIME_UNKNOWN = -1` constant for low-confidence states
  - Confidence-based gating: `1.0 / (1.0 + normalized_distance)`
  - Config: `regimes.assignment.min_confidence` (default: 0.0 = disabled)
- **RUL Reliability Gating**: Prevents unreliable predictions
  - Added `RULStatus` enum: RELIABLE, NOT_RELIABLE, INSUFFICIENT_DATA
  - Prerequisite checks: data quality, stable regime, persistent degradation, low drift
  - Returns NaN when prerequisites fail instead of misleading numbers
- **Data Contract Validation**: Rejects corrupt data at pipeline entry
  - 4 validation rules: timestamp order, no duplicates, no future rows, cadence
  - Fail-fast approach with clear error messages
  - Config: `data_contract.strict` (to be enabled in Phase 4)
- **Status**: 3 of 8 phases complete (21%) - See `docs/V10.4_SUMMARY.md`

### v10.3.0 - Consolidated Observability Stack
Complete observability integration with Docker-based stack:
- **OpenTelemetry Tracing**: Distributed tracing to Grafana Tempo (OTLP endpoint localhost:4318)
- **OpenTelemetry Metrics**: Prometheus counters, histograms, and gauges for performance monitoring
- **Structured Logging**: JSON logging via structlog to Grafana Loki (localhost:3100)
- **CPU/Memory Profiling**: Continuous profiling with Grafana Pyroscope (localhost:4040)
- **Unified Console API**: Single `Console` class with `.info()/.warn()/.error()/.ok()/.status()/.header()` methods
- **Integrated Timers**: Automatic span emission and histogram recording in `utils/timer.py`
- **Pre-configured Dashboards**: ACM Observability and Performance Monitor dashboards
- **Docker Deployment**: Complete stack in `install/observability/docker-compose.yaml`
- See `docs/OBSERVABILITY.md` for full documentation

### v10.2.0 - Detector Simplification
- Removed Mahalanobis detector (mathematically redundant with PCA-T-squared)
- Both MHAL and PCA-T-squared compute Mahalanobis distance, but PCA-T-squared is numerically stable
- Simplified to 6 active detectors with clearer fault-type mapping
- Updated fusion weights to reflect detector contributions

### Other Updates
- SQL historian sample data time-shifted (2023-10-15 to 2025-09-14) for Grafana compatibility
- Archived single-purpose diagnostic scripts to `scripts/archive/`
- Schema documentation via `scripts/sql/export_comprehensive_schema.py`

## v10.0.0 Release Highlights

### Continuous Forecasting with Exponential Blending
Health forecasts now evolve smoothly across batch runs using exponential temporal blending (12-hour time constant), eliminating per-batch duplication in Grafana dashboards. Single continuous forecast line per equipment with automatic state persistence and version tracking.

### Hazard-Based RUL Estimation
Converts health forecasts to failure hazard rates with exponential weighted moving average (EWMA) smoothing. Provides survival probability curves and probabilistic RUL predictions with P10/P50/P90 confidence bounds from Monte Carlo simulations (1000 runs). Includes top-3 culprit sensor attribution.

### Multi-Signal Evolution
All analytical signals evolve correctly across batches:
- Drift tracking via CUSUM detector
- Regime evolution via MiniBatchKMeans clustering
- 28 pairwise detector correlations across 6 active detectors
- Adaptive thresholds with precision-recall AUC throttling

### Time-Series Forecast Tables
- `ACM_HealthForecast_Continuous`: Merged health forecasts with exponential blending
- `ACM_FailureHazard_TS`: EWMA-smoothed hazard rates with survival probability
- Grafana-ready format with smooth transitions across batch boundaries

### Production Validation
- Comprehensive analytical robustness report in `docs/CONTINUOUS_LEARNING_ROBUSTNESS.md`
- 14-component validation checklist (all passing)
- RMSE, MAPE, and Theil-U coefficient tracking
- P10/P50/P90 confidence bounds for RUL predictions

### Additional Features
- Unified forecasting engine consolidating health, RUL, and sensor forecasts
- Sensor value forecasting with confidence intervals using linear trend and VAR methods
- Smart coldstart mode with progressive data loading and exponential window expansion
- Gap tolerance increased to 720 hours (30 days) for historical replay
- Forecast state management with version tracking and optimistic locking
- Adaptive configuration with per-equipment auto-tuning and history tracking
- Standardized detector labels across all outputs and dashboards

## Core Capabilities

### Multi-Detector Anomaly Detection

ACM analyzes equipment through six specialized detectors, each answering a specific diagnostic question:

| Detector | Z-Score Column | Diagnostic Question | Fault Types Detected |
|----------|----------------|---------------------|---------------------|
| **AR1** | `ar1_z` | "Is a sensor drifting or spiking?" | Sensor degradation, control loop issues, actuator wear |
| **PCA-SPE** | `pca_spe_z` | "Are sensors decoupled?" | Mechanical coupling loss, thermal expansion, structural fatigue |
| **PCA-T-squared** | `pca_t2_z` | "Is the operating point abnormal?" | Process upset, load imbalance, off-design operation |
| **IForest** | `iforest_z` | "Is this a rare state?" | Novel failure mode, rare transient, unknown condition |
| **GMM** | `gmm_z` | "Does this match known clusters?" | Regime transition, mode confusion, startup/shutdown anomaly |
| **OMR** | `omr_z` | "Do sensors predict each other?" | Fouling, wear, misalignment, calibration drift |

**Additional Analysis:**
- Drift tracking for gradual degradation detection
- Adaptive threshold tuning based on historical performance
- Episode identification with root cause attribution

### Predictive Forecasting

**Health Forecasting:**
- 7-day ahead health trajectory prediction
- Exponential blending for smooth multi-batch evolution
- Confidence intervals and quality metrics

**RUL (Remaining Useful Life) Estimation:**
- Probabilistic predictions with P10/P50/P90 confidence bounds
- Monte Carlo simulations (1000 runs) for uncertainty quantification
- Hazard rate calculation and survival probability curves
- Top-3 culprit sensor attribution for failure drivers

**Sensor Value Forecasting:**
- Predicts future values for critical physical sensors
- Linear trend and Vector Auto-Regression (VAR) methods
- Per-sensor confidence intervals and bounds enforcement

### Operating Regime Detection

- Automatic cluster detection (2-6 regimes)
- MiniBatchKMeans clustering with quality scoring
- Regime-aware thresholding and fusion
- Transient change detection
- Regime timeline tracking

### Episode Diagnostics

When anomalies occur, ACM provides:
- Episode start/end times and duration
- Severity classification (warning, alert, critical)
- Culprit sensors ranked by contribution
- Dominant detector identification
- Episode correlation and clustering

## System Architecture

### Data Flow Pipeline

```
[SQL Historian]  -->  [ACM Ingestion]  -->  [Feature Engineering]
      |                     |                        |
      v                     v                        v
[Equipment Data]      [Data Cleaning]      [Fast Features Module]
                           |                   (Pandas/Polars)
                           v                        |
                    [Baseline/Batch]                v
                      Split Logic          [Windowing, FFT, Stats]
                           |                        |
                           v                        v
              +------------+------------+    [6 Detector Heads]
              |                         |           |
         [Training]              [Scoring]          v
              |                         |    [AR1, PCA, IForest,
              v                         |     GMM, OMR, Drift]
      [Model Fitting]                   |           |
              |                         v           v
              +--------> [Model Registry] <--[Z-Scores]
                                |                   |
                                v                   v
                         [SQL Storage]      [Fusion Engine]
                                                    |
                                                    v
                                            [Episode Detection]
                                                    |
                        +---------------------------+
                        |                           |
                        v                           v
                [Regime Detection]         [Forecast Engine]
                        |                           |
                        v                           v
                [Health Scores]            [RUL Predictions]
                        |                           |
                        +---------------------------+
                                    |
                                    v
                            [Output Manager]
                                    |
                    +---------------+---------------+
                    |               |               |
                    v               v               v
            [SQL Tables]    [CSV Artifacts]  [PNG Charts]
                    |
                    v
         [Grafana Dashboards]
```

### Key Modules

**Core Pipeline (`core/`):**
- `acm_main.py` - Main orchestrator and CLI entry point
- `output_manager.py` - Unified I/O hub for SQL, CSV, and PNG outputs
- `fast_features.py` - High-performance feature engineering (Pandas/Polars)
- `model_persistence.py` - Model registry and caching manager

**Detectors:**
- `ar1_detector.py` - Autoregressive residual detector
- `correlation.py` - PCA-based detectors (SPE and T-squared)
- `outliers.py` - Isolation Forest and Gaussian Mixture Models
- `omr.py` - Overall Model Residual detector
- `drift.py` - CUSUM-based drift detection

**Analytics:**
- `fuse.py` - Multi-detector fusion with weighted averaging
- `regimes.py` - Operating regime detection and clustering
- `adaptive_thresholds.py` - Dynamic threshold adjustment
- `forecast_engine.py` - Health and RUL forecasting
- `health_tracker.py` - Health index calculation and trending

**Infrastructure:**
- `sql_client.py` - SQL Server connectivity via pyodbc
- `observability.py` - Unified logging, tracing, metrics, and profiling
- `resource_monitor.py` - System resource tracking

### Storage Architecture

**Database (Microsoft SQL Server):**
- Equipment master data and historian tables
- ACM analysis results (scores, episodes, health, RUL)
- Model registry for detector persistence
- Configuration and run metadata
- Forecast state and adaptive configuration

**File System:**
- `artifacts/{equipment}/run_<timestamp>/` - Per-run outputs
- `artifacts/{equipment}/models/` - Cached detector models
- `configs/` - Configuration files
- `data/` - Sample CSV data for testing

## Configuration Management

ACM configuration is stored in `configs/config_table.csv` (238+ parameters) and synchronized to the SQL `ACM_Config` table. Configuration follows a cascading model with global defaults and equipment-specific overrides.

### Configuration Structure

**Global Defaults (EquipID = 0):**
Default values applied to all equipment unless overridden.

**Equipment-Specific Overrides:**
Per-equipment customization for unique operational characteristics:
- `EquipID=1`: FD_FAN specific settings
- `EquipID=2621`: GAS_TURBINE specific settings
- `EquipID=8634`: ELECTRIC_MOTOR specific settings

### Key Configuration Categories

**Data Ingestion (`data.*`):**
- `timestamp_col`: Timestamp column name (default: `EntryDateTime`)
- `sampling_secs`: Data sampling interval in seconds (default: 1800)
- `max_rows`: Maximum rows per batch (default: 100000)
- `min_train_samples`: Minimum training samples required (default: 200)

**Feature Engineering (`features.*`):**
- `window`: Rolling window size (default: 16)
- `fft_bands`: Frequency bands for FFT decomposition
- `polars_threshold`: Row count threshold for Polars acceleration (default: 10)

**Detector Configuration (`models.*`):**
- `pca.*`: PCA settings (n_components=5, randomized SVD)
- `ar1.*`: AR1 detector parameters (window=256, alpha=0.05)
- `iforest.*`: Isolation Forest (n_estimators=100, contamination=0.01)
- `gmm.*`: Gaussian Mixture Models (k_min=2, k_max=3, BIC search)
- `omr.*`: Overall Model Residual (auto model selection, n_components=5)
- `use_cache`: Enable model caching
- `auto_retrain.*`: Automatic retraining thresholds

**Fusion and Weights (`fusion.*`):**
Detector contribution weights (must sum to 1.0):
- `pca_spe_z`: 0.30 (correlation breaks)
- `pca_t2_z`: 0.20 (multivariate outliers)
- `ar1_z`: 0.20 (temporal patterns)
- `iforest_z`: 0.15 (rare states)
- `omr_z`: 0.10 (sensor relationships)
- `gmm_z`: 0.05 (distribution anomalies)
- `per_regime`: Enable per-regime fusion (default: True)
- `auto_tune.*`: Adaptive weight tuning settings

**Anomaly Detection (`episodes.*`):**
- `cpd.k_sigma`: K-sigma threshold for change-point detection (default: 2.0)
- `cpd.h_sigma`: H-sigma threshold for episode boundaries (default: 12.0)
- `min_len`: Minimum episode length (default: 3 samples)
- `gap_merge`: Merge episodes with small gaps (default: 5 samples)

**Thresholds (`thresholds.*`):**
- `q`: Quantile threshold for anomaly detection (default: 0.98)
- `alert`: Alert threshold (default: 0.85)
- `warn`: Warning threshold (default: 0.7)
- `self_tune.*`: Self-tuning parameters
- `adaptive.*`: Per-regime adaptive thresholds

**Operating Regimes (`regimes.*`):**
- `auto_k.k_min`: Minimum clusters (default: 2)
- `auto_k.k_max`: Maximum clusters (default: 6)
- `quality.silhouette_min`: Minimum silhouette score (default: 0.3)
- `smoothing.*`: Regime label smoothing settings
- `transient_detection.*`: Transient change detection

**Drift Detection (`drift.*`):**
- `cusum.*`: CUSUM drift detector (threshold=2.0, smoothing_alpha=0.3)
- `p95_threshold`: P95 threshold for drift classification (default: 2.0)
- `multi_feature.*`: Multi-feature drift detection settings

**Forecasting (`forecasting.*`):**
- `enhanced_enabled`: Enable unified forecasting engine (default: True)
- `enable_continuous`: Enable continuous stateful forecasting (default: True)
- `failure_threshold`: Health threshold for failure prediction (default: 70.0)
- `max_forecast_hours`: Maximum forecast horizon (default: 168 hours)
- `confidence_k`: Confidence interval multiplier (default: 1.96 for 95% CI)
- `blend_tau_hours`: Exponential blending time constant (default: 12 hours)
- `hazard_smoothing_alpha`: EWMA alpha for hazard smoothing (default: 0.3)

**SQL Integration (`sql.*`):**
- `enabled`: Enable SQL connection (default: True)
- Connection parameters (driver, server, database, encryption)
- Performance tuning (pooling, fast execution, retry logic)

**Runtime (`runtime.*`):**
- `storage_backend`: Storage mode (`sql` or `file`)
- `tick_minutes`: Data cadence for batch runs
- `version`: Current ACM version
- `phases.*`: Enable/disable pipeline phases

### Configuration Workflow

**Editing Configuration:**
1. Edit `configs/config_table.csv` directly
2. Run `python scripts/sql/populate_acm_config.py` to sync to SQL
3. Commit changes to version control

**Configuration History:**
All adaptive tuning changes are logged to `ACM_ConfigHistory` with:
- Timestamp and parameter path
- Old and new values
- Change reason and author tag

**Critical Parameters for Tuning:**

| Parameter | Why Tune? | Tuning Indicators |
|-----------|-----------|-------------------|
| `data.sampling_secs` | Must match equipment data cadence | "Insufficient data" despite many rows returned |
| `data.timestamp_col` | Different column names across equipment | Data loading failures or empty results |
| `thresholds.self_tune.clip_z` | Detector saturation | "High saturation" warnings |
| `episodes.cpd.k_sigma` | Episode detection sensitivity | Too many/few episodes detected |

For complete configuration documentation, see `docs/ACM_SYSTEM_OVERVIEW.md` Section 20.

## Continuous Learning and Forecasting

ACM v10.0.0 implements true continuous forecasting where health predictions evolve smoothly across batch runs instead of creating per-batch duplicates.

### Exponential Blending Architecture

**Temporal Smoothing:**
The `merge_forecast_horizons()` function blends previous and current forecasts using exponential decay with a 12-hour time constant (configurable via `blend_tau_hours`).

**Dual Weighting Strategy:**
- Recency weight: `exp(-age/tau)` favors recent predictions
- Horizon awareness: `1/(1+hours/24)` accounts for forecast uncertainty
- Combined weight: `w_prev = recency_weight * horizon_weight` (capped at 0.9)
- Merged value: `w_prev * prev_forecast + (1-w_prev) * curr_forecast`

**Intelligent NaN Handling:**
Prefers non-null values without treating missing data as zero.

**Benefits:**
- Single continuous forecast line per equipment
- Smooth transitions across batch boundaries
- Prevents stale forecasts from dominating (0.9 cap)
- Mathematically sound blending preserves forecast quality

### State Persistence and Evolution

**Versioned Tracking:**
The `ForecastState` class maintains version identifiers (e.g., v807 to v813) stored in the `ACM_ForecastState` table.

**Audit Trail:**
Each forecast includes:
- RunID and BatchNum for reproducibility
- Version identifier for evolution tracking
- Timestamp for temporal ordering

**Self-Healing:**
Gracefully handles missing or invalid state with automatic fallback to current forecasts.

**Validation:**
Multi-batch progression confirmed across sequential batches with state evolution tracking.

### Hazard-Based RUL Estimation

**Hazard Rate Calculation:**
Converts health forecasts to instantaneous failure rates:
```
lambda(t) = -ln(1 - p(t)) / dt
```

**EWMA Smoothing:**
Configurable alpha parameter reduces noise in failure probability curves while preserving trend information.

**Survival Probability:**
Cumulative survival curves computed via:
```
S(t) = exp(-integral(lambda_smooth(t) dt))
```

**Confidence Bounds:**
- Monte Carlo simulations (1000 runs) generate probability distributions
- P10/P50/P90 confidence intervals for RUL predictions
- Uncertainty quantification for decision support

**Culprit Attribution:**
Identifies top 3 sensors driving failure risk through z-score contribution analysis.

### Multi-Signal Evolution

All analytical signals evolve correctly across batch runs:

**Drift Tracking:**
- CUSUM detector with P95 threshold per batch
- Coldstart windowing approach for initial batches
- Gradual vs. sudden change classification

**Regime Evolution:**
- MiniBatchKMeans clustering with auto-k selection
- Quality scoring via Calinski-Harabasz and silhouette metrics
- Regime transition detection and smoothing

**Detector Correlation:**
- 28 pairwise correlations tracked across 6 active detectors
- Correlation evolution monitoring for detector redundancy
- Used for fusion weight optimization

**Adaptive Thresholds:**
- Quantile/MAD/hybrid threshold methods
- Precision-Recall AUC based throttling
- Prevents over-tuning while maintaining sensitivity

**Health Forecasting:**
- Exponential smoothing with 168-hour horizon (7 days)
- Confidence intervals based on historical forecast error
- Quality metrics (RMSE, MAPE, Theil-U coefficient)

**Sensor Forecasting:**
- VAR(3) models for critical sensors
- Lag-3 dependencies capture temporal dynamics
- Per-sensor bounds enforcement

### Time-Series Tables

**ACM_HealthForecast_Continuous:**
- Merged health forecasts with exponential blending
- Single continuous line per equipment (no per-run duplicates)
- Smooth transitions across batch boundaries
- Grafana-ready time-series format

**ACM_FailureHazard_TS:**
- EWMA-smoothed hazard rates
- Raw hazard, survival probability, and failure probability
- Enables risk-based maintenance scheduling

**Benefits:**
- Eliminates Grafana dashboard clutter from per-batch forecasts
- 12-hour blending window creates seamless transitions
- Ready for direct visualization without post-processing

### Quality Assurance

**RMSE Validation:**
Root Mean Square Error gates ensure forecast quality meets thresholds.

**MAPE Tracking:**
Median Absolute Percentage Error (typically 33.8% for noisy industrial data) validates forecast accuracy.

**Theil-U Coefficient:**
Value of 1.098 indicates acceptable forecast accuracy versus naive baseline (values below 1.0 are excellent, below 2.0 are acceptable).

**Confidence Bounds:**
P10/P50/P90 intervals validated via Monte Carlo simulation convergence.

**Production Validation:**
14-component checklist covering:
- Mathematical soundness of exponential blending
- State persistence correctness
- Multi-batch signal evolution
- Forecast quality metrics
- RUL confidence bounds
- All checks passing (see `docs/CONTINUOUS_LEARNING_ROBUSTNESS.md`)

### Production Benefits

- **Reduced False Alarms**: EWMA hazard smoothing filters noise in health forecasts
- **Probabilistic RUL**: P10/P50/P90 bounds support risk-based decision making
- **Multi-Batch Learning**: Models improve with accumulated data across runs
- **Single Forecast View**: Operators see one continuous line, not overlapping batch predictions
- **Validated Accuracy**: All analytical checks passed for production deployment

## Installation and Setup

### Requirements

- **Python**: Version 3.11 or higher
- **Database**: Microsoft SQL Server (2016 or later)
- **Operating System**: Windows, Linux, or macOS

### Python Environment Setup

1. **Create virtual environment:**
   ```bash
   python -m venv .venv
   ```

2. **Activate environment:**
   - Windows: `.venv\Scripts\activate`
   - Linux/macOS: `source .venv/bin/activate`

3. **Upgrade pip:**
   ```bash
   pip install -U pip
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   # OR
   pip install .
   ```

### Optional Components

**Full Observability Stack:**
```bash
pip install -e ".[observability]"
```
Includes OpenTelemetry, Pyroscope profiling, and full telemetry support.

**Development Tools:**
```bash
pip install -e ".[dev]"
```
Includes ruff, mypy, and profiling tools.

### Database Configuration

1. **SQL Connection File:**
   Create `configs/sql_connection.ini`:
   ```ini
   [acm]
   server = localhost\INSTANCENAME
   database = ACM
   trusted_connection = yes
   driver = ODBC Driver 18 for SQL Server
   TrustServerCertificate = yes
   ```

2. **Synchronize Configuration:**
   ```powershell
   python scripts/sql/populate_acm_config.py
   ```

3. **Verify Connection:**
   ```powershell
   python scripts/sql/verify_acm_connection.py
   ```

### Observability Stack Setup

The observability stack runs in Docker and provides monitoring, logging, and profiling.

1. **Start Docker Stack:**
   ```powershell
   cd install/observability
   docker compose up -d
   ```

2. **Verify Services:**
   ```powershell
   docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
   ```

3. **Access Grafana:**
   - URL: http://localhost:3000
   - Username: `admin`
   - Password: `admin`

Expected services:
- `acm-grafana` (port 3000) - Dashboards
- `acm-alloy` (ports 4317, 4318) - OTLP collector
- `acm-tempo` (port 3200) - Traces
- `acm-loki` (port 3100) - Logs
- `acm-prometheus` (port 9090) - Metrics
- `acm-pyroscope` (port 4040) - Profiling

For detailed setup instructions, see `install/observability/README.md`.

## Running ACM

### Single Equipment Run

**Basic Execution:**
```powershell
python -m core.acm_main --equip FD_FAN
```

**With Custom Data Files:**
```powershell
python -m core.acm_main --equip FD_FAN \
  --train-csv data/baseline.csv \
  --score-csv data/batch.csv
```

**With Configuration Override:**
```powershell
python -m core.acm_main --equip FD_FAN --config custom_config.yaml
```

**Force File Mode:**
```powershell
$env:ACM_FORCE_FILE_MODE = "1"
python -m core.acm_main --equip FD_FAN
```

### Batch Processing

**Continuous Batch Mode:**
```powershell
python scripts/sql_batch_runner.py \
  --equip FD_FAN \
  --tick-minutes 1440 \
  --max-ticks 10
```

**Multi-Equipment Parallel Processing:**
```powershell
python scripts/sql_batch_runner.py \
  --equip FD_FAN GAS_TURBINE ELECTRIC_MOTOR \
  --tick-minutes 1440 \
  --max-workers 3 \
  --start-from-beginning
```

**Resume After Interruption:**
```powershell
python scripts/sql_batch_runner.py \
  --equip WFA_TURBINE_0 \
  --tick-minutes 1440 \
  --resume
```

### Command-Line Options

**Core Parameters:**
- `--equip <name>` - Equipment code (required)
- `--config <path>` - Custom YAML configuration file
- `--train-csv` / `--baseline-csv` - Training data CSV path
- `--score-csv` / `--batch-csv` - Scoring data CSV path
- `--clear-cache` - Force model retraining (ignore cached models)

**Logging Options:**
- `--log-level <LEVEL>` - Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--log-format <FORMAT>` - Log format (json, console)
- `--log-module-level <MODULE=LEVEL>` - Per-module logging level
- `--log-file <PATH>` - Write logs to file

**Batch Runner Options:**
- `--tick-minutes <N>` - Data window size in minutes
- `--max-ticks <N>` - Maximum number of batches to process
- `--max-workers <N>` - Parallel workers for multi-equipment
- `--start-from-beginning` - Start from earliest available data
- `--resume` - Resume from last checkpoint

### Output Locations

**SQL Tables:**
ACM writes results to these primary tables:
- `ACM_Runs` - Run metadata and status
- `ACM_Scores_Wide` - Detector scores time series
- `ACM_Anomaly_Events` - Detected anomaly episodes
- `ACM_EpisodeDiagnostics` - Episode analysis and culprits
- `ACM_HealthTimeline` - Health index over time
- `ACM_RUL` - Remaining Useful Life predictions
- `ACM_HealthForecast` - Health forecast time series
- `ACM_FailureForecast` - Failure probability forecasts
- `ACM_SensorForecast` - Physical sensor value forecasts
- `ACM_RegimeTimeline` - Operating regime history
- `ACM_RunLogs` - Detailed execution logs

**File Artifacts** (when file mode enabled):
- `artifacts/{equipment}/run_<timestamp>/` - Per-run outputs
  - CSV files with detector scores and analytics
  - PNG charts and visualizations
- `artifacts/{equipment}/models/` - Cached detector models

**Grafana Dashboards:**
Pre-configured dashboards in `grafana_dashboards/`:
- ACM Behavior - Equipment health and anomaly detection
- ACM Observability - System performance and tracing
- ACM Performance Monitor - Resource utilization

## Observability and Monitoring

ACM v10.3.0 provides comprehensive observability through a Docker-based stack built on open standards.

### Observability Components

| Signal Type | Technology | Backend | Port | Purpose |
|-------------|------------|---------|------|---------|
| **Traces** | OpenTelemetry SDK | Grafana Tempo | 3200 | Distributed tracing and request flow |
| **Metrics** | OpenTelemetry SDK | Prometheus | 9090 | Performance counters and histograms |
| **Logs** | structlog | Grafana Loki | 3100 | Structured JSON logging |
| **Profiling** | yappi + HTTP API | Grafana Pyroscope | 4040 | CPU and memory flamegraphs |

### Quick Start Example

```python
from core.observability import Console, Span, Metrics

# Structured logging
Console.info("Batch started", equipment="FD_FAN", rows=1500)
Console.warn("High anomaly rate", rate=0.15, threshold=0.10)
Console.error("Database connection failed", error=str(e))

# Distributed tracing
with Span("detector.fit", detector="pca") as span:
    span.set_attribute("n_components", 5)
    # ... detector fitting code ...

# Metrics
Metrics.counter("acm.detector.fit", {"detector": "pca"})
Metrics.histogram("acm.detector.duration", 234.5, {"detector": "pca"})
```

### Environment Variables

Configure observability endpoints via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | http://localhost:4318 | OTLP collector endpoint |
| `ACM_PYROSCOPE_ENDPOINT` | http://localhost:4040 | Pyroscope profiling server |
| `ACM_LOG_FORMAT` | json | Log format: `json` or `console` |
| `ACM_LOG_LEVEL` | INFO | Logging level |

### Accessing Observability Data

**Grafana Dashboards:**
- URL: http://localhost:3000
- Pre-configured datasources for Tempo, Prometheus, Loki, and Pyroscope
- Dashboards in ACM folder:
  - ACM Behavior - Health, anomalies, RUL
  - ACM Observability - Traces, logs, metrics correlation
  - ACM Performance Monitor - CPU, memory, duration metrics

**Direct Access:**
- Loki logs: http://localhost:3100
- Prometheus metrics: http://localhost:9090
- Tempo traces: http://localhost:3200
- Pyroscope profiles: http://localhost:4040

For complete observability documentation, see `docs/OBSERVABILITY.md`.

## Technology Stack

### Core Technologies

**Programming Language:**
- Python 3.11+ (primary runtime)
- Optional Rust bridge for performance-critical operations

**Data Processing:**
- **pandas** - Primary data manipulation and analysis
- **Polars** - High-performance alternative for large datasets (auto-enabled for batches >10 rows)
- **NumPy** - Numerical computing and array operations
- **SciPy** - Scientific computing and statistics

**Machine Learning:**
- **scikit-learn** - Detector implementations (PCA, IForest, GMM)
- **statsmodels** - Statistical models and time series analysis

**Database:**
- **Microsoft SQL Server** - Primary data storage
- **pyodbc** - Database connectivity
- Connection pooling and optimistic concurrency control

**Visualization:**
- **Grafana** - Dashboard platform
- **matplotlib** - Chart generation for artifacts
- **seaborn** - Statistical visualizations

**Observability Stack:**
- **OpenTelemetry** - Distributed tracing and metrics
- **structlog** - Structured logging
- **Grafana Tempo** - Trace storage and visualization
- **Prometheus** - Metrics collection
- **Grafana Loki** - Log aggregation
- **Grafana Pyroscope** - Continuous profiling
- **yappi** - CPU profiling (pure Python, no Rust required)

### Performance Optimization

**Vectorization:**
ACM heavily uses vectorized operations via pandas and NumPy to avoid Python loops.

**Polars Acceleration:**
Automatically enabled for feature engineering when batch size exceeds threshold (configurable via `fusion.features.polars_threshold`).

**Model Caching:**
Detectors are persisted to SQL `ACM_ModelRegistry` table or filesystem cache to avoid retraining.

**SQL Optimization:**
- Query hints (NOLOCK, ROWLOCK, UPDLOCK)
- Partition-ready indexes on (EquipID, RunID, Timestamp)
- Table-valued parameters for bulk inserts
- Connection pooling (MinPoolSize=10, MaxPoolSize=100)

**Parallel Processing:**
Batch runner supports multi-equipment parallel processing with configurable worker count.

## Project Structure

```
ACM/
+-- core/                      # Core pipeline implementation
|   +-- acm_main.py            # Main orchestrator and entry point
|   +-- output_manager.py      # I/O hub for SQL, CSV, PNG outputs
|   +-- fast_features.py       # Feature engineering (pandas/Polars)
|   +-- model_persistence.py   # Model registry and caching
|   +-- observability.py       # Unified logging, tracing, metrics
|   +-- sql_client.py          # SQL Server connectivity
|   +-- forecast_engine.py     # Health and RUL forecasting
|   +-- health_tracker.py      # Health index calculation
|   +-- ar1_detector.py        # AR1 residual detector
|   +-- correlation.py         # PCA-based detectors
|   +-- outliers.py            # IForest and GMM detectors
|   +-- omr.py                 # Overall Model Residual
|   +-- drift.py               # CUSUM drift detection
|   +-- fuse.py                # Multi-detector fusion
|   +-- regimes.py             # Operating regime detection
|   +-- adaptive_thresholds.py # Dynamic threshold adjustment
|   +-- sensor_attribution.py  # Culprit sensor identification
|   +-- metrics.py             # Forecast quality metrics
|
+-- configs/                   # Configuration files
|   +-- config_table.csv       # Main configuration (238+ parameters)
|   +-- sql_connection.ini     # SQL credentials (gitignored)
|
+-- scripts/                   # Operational scripts
|   +-- sql_batch_runner.py    # Batch processing orchestrator
|   +-- sql/                   # SQL utilities and migrations
|   |   +-- export_comprehensive_schema.py  # Schema documentation
|   |   +-- populate_acm_config.py          # Config sync to SQL
|   |   +-- verify_acm_connection.py        # Connection testing
|   +-- archive/               # Archived diagnostic scripts
|
+-- docs/                      # Documentation
|   +-- ACM_SYSTEM_OVERVIEW.md             # Complete system handbook
|   +-- OBSERVABILITY.md                   # Observability guide
|   +-- CONTINUOUS_LEARNING_ROBUSTNESS.md  # Validation report
|   +-- OMR_DETECTOR.md                    # OMR detector details
|   +-- EQUIPMENT_IMPORT_PROCEDURE.md      # Adding new equipment
|   +-- sql/                               # SQL documentation
|       +-- COMPREHENSIVE_SCHEMA_REFERENCE.md  # Authoritative schema
|
+-- grafana_dashboards/        # Grafana dashboard definitions
|   +-- acm_behavior.json      # Health and anomaly dashboard
|   +-- acm_observability.json # Traces, logs, metrics
|   +-- acm_performance_monitor.json  # Resource utilization
|
+-- install/                   # Installation scripts and configs
|   +-- observability/         # Docker-based observability stack
|   |   +-- docker-compose.yaml        # Complete stack definition
|   |   +-- grafana-datasources.yaml   # Auto-provisioned datasources
|   |   +-- provisioning/              # Grafana provisioning configs
|   +-- sql/                   # SQL installation scripts
|
+-- tests/                     # Test suites
|   +-- test_fast_features.py
|   +-- test_observability.py
|   +-- test_forecast_engine.py
|
+-- utils/                     # Utility modules
|   +-- version.py             # Version management
|   +-- timer.py               # Timing utilities with OTEL integration
|   +-- config_dict.py         # Configuration handling
|
+-- artifacts/                 # Runtime outputs (gitignored)
|   +-- {equipment}/
|       +-- run_<timestamp>/   # Per-run outputs
|       +-- models/            # Cached detector models
|
+-- data/                      # Sample data (gitignored)
+-- logs/                      # Runtime logs (gitignored)
+-- rust_bridge/               # Optional Rust acceleration
+-- pyproject.toml             # Python project configuration
+-- README.md                  # This file
```

### Key Directories

**`core/`** - All pipeline implementation code
- Detectors, feature engineering, fusion, forecasting
- SQL integration and observability
- Main entry point (`acm_main.py`)

**`configs/`** - Configuration files
- `config_table.csv` - Equipment settings and parameters
- `sql_connection.ini` - Database credentials (local only)

**`scripts/`** - Operational and utility scripts
- Batch processing (`sql_batch_runner.py`)
- SQL tools (`sql/` subdirectory)
- Archived diagnostics (`archive/` subdirectory)

**`docs/`** - Comprehensive documentation
- System overview, observability, detector details
- SQL schema reference (authoritative)
- Equipment procedures and validation reports

**`install/`** - Installation and deployment
- Observability stack (Docker Compose)
- SQL installation scripts
- Provisioning configurations

**`grafana_dashboards/`** - Pre-built Grafana dashboards
- JSON dashboard definitions
- Auto-provisioned to Grafana instance

## Quick Reference

### Essential Commands

**Run Single Equipment:**
```powershell
python -m core.acm_main --equip FD_FAN
```

**Batch Processing:**
```powershell
python scripts/sql_batch_runner.py --equip FD_FAN --tick-minutes 1440 --max-ticks 10
```

**Start Observability Stack:**
```powershell
cd install/observability
docker compose up -d
```

**Sync Configuration to SQL:**
```powershell
python scripts/sql/populate_acm_config.py
```

**Export Database Schema:**
```powershell
python scripts/sql/export_comprehensive_schema.py --output docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md
```

### Important Files

**Configuration:**
- `configs/config_table.csv` - Main configuration (238+ parameters)
- `configs/sql_connection.ini` - Database credentials

**Documentation:**
- `docs/ACM_SYSTEM_OVERVIEW.md` - Complete system handbook
- `docs/OBSERVABILITY.md` - Observability and monitoring guide
- `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md` - Authoritative database schema

**Scripts:**
- `scripts/sql_batch_runner.py` - Batch processing orchestrator
- `scripts/sql/verify_acm_connection.py` - Test database connectivity
- `scripts/sql/populate_acm_config.py` - Sync configuration

**Dashboards:**
- `grafana_dashboards/acm_behavior.json` - Equipment health dashboard
- `grafana_dashboards/acm_observability.json` - System monitoring
- `grafana_dashboards/acm_performance_monitor.json` - Resource tracking

### Key SQL Tables

**Run Management:**
- `ACM_Runs` - Run metadata and execution status
- `ACM_RunLogs` - Detailed execution logs
- `ACM_Config` - Equipment configuration parameters

**Analysis Results:**
- `ACM_Scores_Wide` - Detector scores time series
- `ACM_Anomaly_Events` - Detected anomaly episodes
- `ACM_EpisodeDiagnostics` - Episode analysis with culprits
- `ACM_HealthTimeline` - Equipment health over time

**Forecasting:**
- `ACM_HealthForecast` - Health trajectory predictions
- `ACM_FailureForecast` - Failure probability forecasts
- `ACM_SensorForecast` - Physical sensor value forecasts
- `ACM_RUL` - Remaining Useful Life predictions

**Operating Context:**
- `ACM_RegimeTimeline` - Operating regime history
- `ACM_SensorNormalized_TS` - Normalized sensor data

**Model Management:**
- `ACM_ModelRegistry` - Persisted detector models
- `ACM_ForecastState` - Forecast state versioning
- `ACM_AdaptiveConfig` - Auto-tuning configuration

### Service Endpoints

**Grafana:** http://localhost:3000 (admin/admin)
**Prometheus:** http://localhost:9090
**Loki:** http://localhost:3100
**Tempo:** http://localhost:3200
**Pyroscope:** http://localhost:4040

### Getting Help

**System Documentation:**
- Complete architecture: `docs/ACM_SYSTEM_OVERVIEW.md`
- Detector details: `docs/OMR_DETECTOR.md`
- Adding equipment: `docs/EQUIPMENT_IMPORT_PROCEDURE.md`
- Observability setup: `docs/OBSERVABILITY.md`

**Database Schema:**
- Run: `python scripts/sql/export_comprehensive_schema.py`
- Output: `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md`

**Configuration:**
- All parameters documented in `docs/ACM_SYSTEM_OVERVIEW.md` Section 20
- Equipment-specific overrides in `configs/config_table.csv`

### Version Information

**Current Version:** v10.3.0 (December 2025)

**Release History:**
- v10.3.0 - Consolidated observability stack with Docker deployment
- v10.2.0 - Detector simplification (removed redundant Mahalanobis)
- v10.0.0 - Continuous forecasting with exponential blending and hazard-based RUL
- v9.0.0 - Production release with P0 fixes and professional versioning

For detailed release notes, see `utils/version.py`.

---

## License

Proprietary - Copyright (c) ACM Development Team

---

## Support and Contribution

For system documentation, see `docs/ACM_SYSTEM_OVERVIEW.md`.
For specific topics, refer to the documentation files listed in the Quick Reference section above.

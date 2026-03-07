# Asset Condition Monitoring (ACM) System Architecture

**Version:** 11 (Estimated)

## Overview

The Asset Condition Monitoring (ACM) System is a sophisticated industrial analytics pipeline designed to monitor equipment health, detect anomalies, identify operating regimes, and forecast remaining useful life (RUL). It ingests sensor data from a SQL Server historian, processes it through an ensemble of machine learning models, and outputs actionable insights for maintenance and operations.

## System Architecture

### 1. Core Purpose
The system ingests sensor data (e.g., temperature, vibration, pressure) from a SQL Server historian, processes it through an ensemble of machine learning models, and outputs health assessments, anomaly alerts, and prognostics back to a database for visualization (likely via Grafana).

### 2. Key Functional Layers

#### A. Data Ingestion & Preparation
*   **`core/sql_client.py`**: A wrapper around `pyodbc` for managing SQL Server connections, including support for multiple databases and retry logic for deadlocks.
*   **`core/data_loader.py`**: Handles loading time-series data, enforcing schema contracts, and managing "cold starts" (waiting for sufficient data accumulation before training).
*   **`core/fast_features.py`**: Uses **Polars** (for speed) to compute rolling statistics (median, skew, kurtosis, spectral energy) and other engineered features used by the models.
*   **`core/seasonality.py`**: Detects and adjusts for periodic patterns (e.g., daily temperature cycles) to prevent false positives.

#### B. Anomaly Detection (The Ensemble)
The system uses a "Detector Ensemble" approach, running multiple models in parallel to catch different types of faults. Orchestrated by **`core/detector_orchestrator.py`**:
*   **PCA (`core/correlation.py`)**: Detects correlation breaks among sensors using Principal Component Analysis (SPE and T² statistics).
*   **Isolation Forest & GMM (`core/outliers.py`)**: Detects density-based outliers and points that don't fit the learned probability distribution.
*   **OMR (`core/omr.py`)**: "Overall Model Residual" — uses multivariate regression (PLS/Ridge) to predict sensor values from others and flags reconstruction errors.
*   **AR1**: Univariate autoregressive model for single-sensor anomalies.

#### C. Context & Fusion
*   **`core/regimes.py`**: Uses clustering (HDBSCAN or GMM) to identify operating modes (e.g., "High Load", "Idle"). This allows the system to apply different thresholds for different states.
*   **`core/fuse.py`**: The "brain" of the scoring logic. It:
    1.  **Calibrates** raw detector scores into normalized Z-scores.
    2.  **Fuses** them into a single "Health Index".
    3.  **Detects Episodes**: Identifies sustained periods of anomalous behavior using hysteresis logic.

#### D. Prognostics (Forecasting & RUL)
*   **`core/forecast_engine.py`**: Orchestrates the forecasting workflow.
*   **`core/degradation_model.py`**: Fits trend models (like Holt's Linear Trend) to the Health Index to model degradation over time.
*   **`core/rul_estimator.py`**: Uses Monte Carlo simulations to estimate **Remaining Useful Life (RUL)**, providing confidence intervals (P10/P50/P90) for when the equipment will cross a failure threshold.
*   **`core/drift.py`**: Detects gradual, long-term shifts in equipment behavior that might not trigger immediate anomaly alerts.

#### E. Diagnostics
*   **`core/sensor_attribution.py`**: Performs counterfactual analysis to determine *which* sensors are responsible for an anomaly (e.g., "Vibration is 30% responsible").
*   **`core/episode_culprits_writer.py`**: Persists root-cause analysis for detected episodes.

### 3. Infrastructure & Operations

#### State & Persistence
The system is designed to be stateless in memory but stateful via SQL.
*   **`core/model_persistence.py`**: Serializes trained models (using `joblib`) and stores them as binary blobs in the SQL database. This allows the pipeline to stop and restart without losing training.
*   **`core/state_manager.py`**: Manages optimistic locking for configuration updates and forecasting state.
*   **`core/model_lifecycle.py`**: Tracks the maturity of models (`COLDSTART` -> `LEARNING` -> `CONVERGED`), ensuring only stable models are used for critical alerts.

#### Observability
*   **`core/observability.py`**: A unified logging and tracing wrapper. It integrates **structlog** (for JSON logs), **OpenTelemetry** (for traces), and **Pyroscope** (for profiling), sending telemetry to backend systems like Loki and Tempo.
*   **`core/resource_monitor.py`**: Tracks CPU, memory, and GPU usage per pipeline stage.
*   **`core/output_manager.py`**: Centralizes all data writing operations, ensuring efficient batched inserts into SQL tables.

### 4. Design Philosophy
*   **Robustness**: Extensive use of robust statistics (Median/MAD instead of Mean/Std) to handle outliers in industrial data.
*   **SQL-Centric**: It treats SQL Server as the source of truth for data, models, configuration, and state.
*   **Adaptive**: Includes logic (`core/model_evaluation.py`) to auto-tune parameters and trigger retraining if model quality degrades (e.g., if anomaly rates become too high or low).
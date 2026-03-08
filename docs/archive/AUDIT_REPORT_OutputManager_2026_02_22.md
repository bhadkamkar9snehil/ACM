# ACM System Audit Report

**Date:** 2026-02-22
**Version:** 11.x (Estimated)
**Scope:** Core modules, documentation, and scripts provided in the repository.

## 1. Executive Summary

The Asset Condition Monitoring (ACM) system is a mature, industrial-grade analytics pipeline designed for robustness and observability. It exhibits a strong "SQL-first" architecture, treating the database as the single source of truth for state, configuration, and results. The codebase demonstrates a transition from legacy monolithic scripts to a modular, domain-driven design.

However, the system is currently in a transitional state regarding its forecasting capabilities, with the `ForecastEngine` explicitly disabled in parts of the codebase. While the anomaly detection and regime identification layers are robust, the prognostic layer requires reintegration.

## 2. Architecture Review

### Strengths
*   **Stateless Compute / Stateful Persistence:** The Python runtime is effectively stateless, reloading context from SQL Server on every run. This ensures resilience against process crashes and enables horizontal scaling of batch workers.
*   **Robust Statistics:** The pervasive use of Median and Median Absolute Deviation (MAD) instead of Mean/Std (`core/fast_features.py`, `core/fuse.py`) makes the system highly resistant to outliers common in industrial sensor data.
*   **Observability:** The integration of OpenTelemetry, Loki, and Pyroscope (`core/observability.py`) provides excellent visibility into pipeline performance and errors.
*   **Performance:** The use of Polars for feature engineering (`core/fast_features.py`) and `fast_executemany` for SQL writes (`core/sql_client.py`) indicates a focus on high-throughput processing.

### Weaknesses
*   **Model Serialization Fragility:** Models are serialized using `joblib` and stored as binary blobs in SQL (`core/model_persistence.py`). This creates a tight coupling between the training environment and the scoring environment. Updates to `scikit-learn` or other dependencies could render persisted models unreadable.
*   **Complex State Management:** The logic for handling "Cold Starts," "Refits," and "Regime Discovery" is distributed across `core/smart_coldstart.py`, `core/model_lifecycle.py`, and `core/state_manager.py`. While modular, the interaction complexity is high.

## 3. Critical Findings

### 3.1. Forecasting Module Disabled
The file `core/forecast_engine.py` contains a header explicitly stating:
> "This module is currently NOT called by the pipeline. The outputs.forecasting phase in acm_main.py is commented out."

This indicates that RUL (Remaining Useful Life) and health forecasting features are currently dormant, despite the presence of sophisticated logic in `core/rul_estimator.py` and `core/degradation_model.py`.

### 3.2. Regime Logic Flux
`core/regimes.py` contains conflicting comments regarding "Unknown" regimes.
*   Code implements `UNKNOWN_REGIME_LABEL = -1`.
*   Comments state: *"v11.3.1: DEPRECATED - UNKNOWN_REGIME_LABEL (-1) is no longer produced... Equipment is ALWAYS in some physical operating state."*
*   However, `fit_regime_model` still uses HDBSCAN which naturally produces noise labels (-1), and fallback logic exists to handle them. This suggests the transition to "always-assigned" regimes is incomplete or partially rolled back.

### 3.3. Output Manager Complexity
`core/output_manager.py` is a monolithic class handling persistence for over 30 different SQL tables. While it delegates some logic (e.g., to `AnalyticsBuilder`), it remains a bottleneck for maintenance. The `ALLOWED_TABLES` set is extensive, and the class mixes low-level SQL operations with high-level artifact formatting.

## 4. Module Analysis

### Core Infrastructure
*   **`core/sql_client.py`**: Robust. Includes retry logic for deadlocks (Error 1205), which is critical for high-concurrency SQL Server environments.
*   **`core/observability.py`**: Excellent. Provides a unified interface for logging, tracing, and profiling without polluting business logic.

### Detection Layer
*   **`core/detector_orchestrator.py`**: Well-structured. Handles the lifecycle of multiple detectors (AR1, PCA, IForest, etc.) and manages feature alignment between training and scoring.
*   **`core/fast_features.py`**: High performance. The switch to Polars for rolling window calculations is a significant optimization.

### Prognostics Layer
*   **`core/degradation_model.py`**: Implements a regime-conditioned trend model. This is a sophisticated approach that accounts for different degradation rates in different operating modes.
*   **`core/sensor_attribution.py`**: Moves towards causal attribution (counterfactual analysis) rather than just correlation, which is the correct direction for actionable diagnostics.

## 5. Code Quality & Standards

*   **Type Hinting:** Extensively used throughout the codebase, improving maintainability.
*   **Error Handling:** The system favors "fail-soft" behavior (logging warnings instead of crashing) for non-critical components (e.g., `_write_optional_table` in `OutputManager`). This is appropriate for batch processing where partial results are better than none.
*   **Documentation:** Inline documentation is generally good, with references to specific "Fix IDs" (e.g., `FIX #5`) and architectural decisions.

## 6. Recommendations

### Immediate Actions
1.  **Re-enable Forecasting:** Validate the stability of `core/forecast_engine.py` and uncomment the integration points in the main orchestrator (likely `core/acm.py` or `acm_main.py`).
2.  **Clarify Regime Policy:** Finalize the decision on "Unknown" regimes. If they are deprecated, ensure HDBSCAN noise points are consistently reassigned (e.g., via nearest centroid or GMM fallback) and remove legacy handling code.

### Long-term Improvements
1.  **Decouple Model Persistence:** Consider ONNX or a schema-based storage for model parameters instead of raw `joblib` pickles to reduce dependency version fragility.
2.  **Refactor OutputManager:** Split `OutputManager` into domain-specific writers (e.g., `TelemetryWriter`, `ModelWriter`, `AnalyticsWriter`) to reduce class size and responsibility.
3.  **Data Contract Enforcement:** `core/pipeline_types.py` introduces `DataContract`. Ensure this is strictly enforced at the *start* of the pipeline (`core/data_loader.py`) to prevent bad data from propagating deep into the system.

## 7. Conclusion

ACM v11 is a well-engineered system that prioritizes operational stability and data integrity. The core anomaly detection pipeline is solid. The primary area for attention is the reintegration of the forecasting module and the simplification of the output persistence layer.
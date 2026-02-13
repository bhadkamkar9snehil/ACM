//! ACM Rust Extension Module
//!
//! High-performance compute kernels for ACM predictive maintenance pipeline.
//! This module provides Python bindings via PyO3 for:
//!
//! - Feature engineering (rolling statistics, correlations, FFT)
//! - Detector scoring (AR1, PCA, IForest)
//! - Clustering (K-means, silhouette scores)
//! - Linear algebra utilities (matrix operations, decompositions)
//!
//! # Architecture
//!
//! Python (orchestrator) -> PyO3 FFI -> Rust (compute) -> NumPy arrays (zero-copy)
//!
//! # Usage from Python
//!
//! ```python
//! import acm_rs
//! import numpy as np
//!
//! # Rolling median on 2D array
//! data = np.random.randn(1000, 50)
//! result = acm_rs.rolling_median_f64(data, window=16, min_periods=8)
//!
//! # AR1 detector
//! residuals = acm_rs.ar1_residuals(signal, alpha=0.05)
//! ```

use pyo3::prelude::*;

// Re-export submodule functions
use acm_features;
// use acm_detectors;  // Phase 3
// use acm_clustering; // Phase 4
// use acm_linalg;     // Future

/// ACM Rust extension module
///
/// Provides high-performance implementations of compute-intensive operations
/// for the ACM predictive maintenance pipeline.
#[pymodule]
fn acm_rs(_py: Python, m: &PyModule) -> PyResult<()> {
    // Module metadata
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("__author__", "ACM Development Team")?;

    // Feature engineering functions (Phase 2)
    m.add_function(wrap_pyfunction!(acm_features::rolling_median_f64, m)?)?;
    m.add_function(wrap_pyfunction!(acm_features::rolling_mad_f64, m)?)?;
    m.add_function(wrap_pyfunction!(acm_features::rolling_mean_std_f64, m)?)?;
    m.add_function(wrap_pyfunction!(acm_features::compute_correlations_f64, m)?)?;

    // Detector scoring (Phase 3 - commented out for now)
    // m.add_function(wrap_pyfunction!(acm_detectors::ar1_residuals, m)?)?;
    // m.add_function(wrap_pyfunction!(acm_detectors::pca_score, m)?)?;

    // Clustering (Phase 4 - commented out for now)
    // m.add_function(wrap_pyfunction!(acm_clustering::fit_kmeans, m)?)?;
    // m.add_function(wrap_pyfunction!(acm_clustering::silhouette_score, m)?)?;

    Ok(())
}

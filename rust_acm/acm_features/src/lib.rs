//! Feature Engineering Module
//!
//! High-performance implementations of rolling statistics, correlations,
//! and frequency-domain features for time series data.
//!
//! # Features
//!
//! - Rolling median, MAD, mean, std (optimized with SIMD)
//! - Correlation matrices with batching
//! - FFT-based spectral features
//! - Lag features with efficient windowing

use numpy::{PyArray1, PyArray2, PyReadonlyArray2};
use pyo3::prelude::*;
use ndarray::{Array1, Array2, ArrayView1, ArrayView2, Axis, s};
use rayon::prelude::*;

mod rolling;
mod correlations;
mod spectral;

pub use rolling::{rolling_median_f64, rolling_mad_f64, rolling_mean_std_f64};
pub use correlations::compute_correlations_f64;
pub use spectral::compute_fft_energy;

// Re-export for main module
#[pymodule]
pub fn acm_features(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rolling_median_f64, m)?)?;
    m.add_function(wrap_pyfunction!(rolling_mad_f64, m)?)?;
    m.add_function(wrap_pyfunction!(rolling_mean_std_f64, m)?)?;
    m.add_function(wrap_pyfunction!(compute_correlations_f64, m)?)?;
    Ok(())
}

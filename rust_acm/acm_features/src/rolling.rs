//! Rolling window statistics with parallel computation
//!
//! Optimized implementations of rolling median, MAD, mean, and std
//! using efficient algorithms and parallel processing.

use numpy::{PyArray2, PyReadonlyArray2};
use pyo3::prelude::*;
use ndarray::{Array2, ArrayView1, Axis, s};
use rayon::prelude::*;

/// Compute rolling median for 2D array (optimized with selection algorithm)
///
/// # Arguments
///
/// * `data` - Input 2D array (rows=time, cols=sensors)
/// * `window` - Window size
/// * `min_periods` - Minimum observations required (default: 1)
///
/// # Returns
///
/// 2D array of rolling medians (same shape as input)
///
/// # Performance
///
/// - O(n * window) time complexity using quickselect
/// - Parallel computation across columns
/// - In-place operations minimize memory allocation
///
/// # Example
///
/// ```python
/// import numpy as np
/// import acm_rs
///
/// data = np.random.randn(1000, 50)
/// medians = acm_rs.rolling_median_f64(data, window=16, min_periods=8)
/// ```
#[pyfunction]
#[pyo3(signature = (data, window, min_periods=1))]
pub fn rolling_median_f64(
    py: Python<'_>,
    data: PyReadonlyArray2<f64>,
    window: usize,
    min_periods: usize,
) -> PyResult<Py<PyArray2<f64>>> {
    let data_view = data.as_array();
    let (nrows, ncols) = data_view.dim();
    
    if window == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("window must be > 0"));
    }
    
    // Allocate output array
    let mut result = Array2::<f64>::from_elem((nrows, ncols), f64::NAN);
    
    // Parallel processing across columns for efficiency
    result.axis_iter_mut(Axis(1))
        .into_par_iter()
        .zip(data_view.axis_iter(Axis(1)))
        .for_each(|(mut out_col, in_col)| {
            compute_rolling_median_column(in_col, window, min_periods, out_col.as_slice_mut().unwrap());
        });
    
    Ok(PyArray2::from_array(py, &result).to_owned())
}

/// Compute rolling median for a single column
fn compute_rolling_median_column(
    data: ArrayView1<f64>,
    window: usize,
    min_periods: usize,
    output: &mut [f64],
) {
    let n = data.len();
    
    for i in 0..n {
        let start = i.saturating_sub(window - 1);
        let end = i + 1;
        
        // Extract window
        let window_slice = data.slice(s![start..end]);
        
        if window_slice.len() >= min_periods {
            // Compute median using quickselect (O(n) average)
            let mut window_vec: Vec<f64> = window_slice.iter()
                .filter(|&&x| x.is_finite())
                .copied()
                .collect();
            
            if window_vec.is_empty() {
                output[i] = f64::NAN;
            } else {
                output[i] = select_median(&mut window_vec);
            }
        } else {
            output[i] = f64::NAN;
        }
    }
}

/// Compute median using quickselect algorithm (O(n) average)
#[inline]
fn select_median(data: &mut [f64]) -> f64 {
    let len = data.len();
    if len == 0 {
        return f64::NAN;
    }
    
    let mid = len / 2;
    
    // Partition-based selection (faster than full sort for median)
    data.select_nth_unstable_by(mid, |a, b| {
        a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal)
    });
    
    if len % 2 == 0 {
        // Even length: average of two middle values
        let upper = data[mid];
        data[..mid].select_nth_unstable_by(mid - 1, |a, b| {
            a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal)
        });
        (data[mid - 1] + upper) / 2.0
    } else {
        // Odd length: middle value
        data[mid]
    }
}

/// Compute rolling Median Absolute Deviation (MAD)
///
/// MAD = median(|x - median(x)|) is a robust measure of variability
///
/// # Arguments
///
/// * `data` - Input 2D array (rows=time, cols=sensors)
/// * `window` - Window size
/// * `min_periods` - Minimum observations required (default: 1)
///
/// # Returns
///
/// 2D array of rolling MAD values
#[pyfunction]
#[pyo3(signature = (data, window, min_periods=1))]
pub fn rolling_mad_f64(
    py: Python<'_>,
    data: PyReadonlyArray2<f64>,
    window: usize,
    min_periods: usize,
) -> PyResult<Py<PyArray2<f64>>> {
    let data_view = data.as_array();
    let (nrows, ncols) = data_view.dim();
    
    if window == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("window must be > 0"));
    }
    
    let mut result = Array2::<f64>::from_elem((nrows, ncols), f64::NAN);
    
    result.axis_iter_mut(Axis(1))
        .into_par_iter()
        .zip(data_view.axis_iter(Axis(1)))
        .for_each(|(mut out_col, in_col)| {
            compute_rolling_mad_column(in_col, window, min_periods, out_col.as_slice_mut().unwrap());
        });
    
    Ok(PyArray2::from_array(py, &result).to_owned())
}

/// Compute rolling MAD for a single column
fn compute_rolling_mad_column(
    data: ArrayView1<f64>,
    window: usize,
    min_periods: usize,
    output: &mut [f64],
) {
    let n = data.len();
    
    for i in 0..n {
        let start = i.saturating_sub(window - 1);
        let end = i + 1;
        
        let window_slice = data.slice(s![start..end]);
        
        if window_slice.len() >= min_periods {
            let mut window_vec: Vec<f64> = window_slice.iter()
                .filter(|&&x| x.is_finite())
                .copied()
                .collect();
            
            if window_vec.is_empty() {
                output[i] = f64::NAN;
            } else {
                // Compute median
                let median = select_median(&mut window_vec.clone());
                
                // Compute absolute deviations
                let mut deviations: Vec<f64> = window_vec.iter()
                    .map(|&x| (x - median).abs())
                    .collect();
                
                // Median of absolute deviations
                output[i] = select_median(&mut deviations);
            }
        } else {
            output[i] = f64::NAN;
        }
    }
}

/// Compute rolling mean and standard deviation
///
/// Returns interleaved array: [mean_col0, std_col0, mean_col1, std_col1, ...]
///
/// # Arguments
///
/// * `data` - Input 2D array (rows=time, cols=sensors)
/// * `window` - Window size
/// * `min_periods` - Minimum observations required (default: 1)
///
/// # Returns
///
/// 2D array with shape (nrows, ncols*2) containing means and stds
#[pyfunction]
#[pyo3(signature = (data, window, min_periods=1))]
pub fn rolling_mean_std_f64(
    py: Python<'_>,
    data: PyReadonlyArray2<f64>,
    window: usize,
    min_periods: usize,
) -> PyResult<Py<PyArray2<f64>>> {
    let data_view = data.as_array();
    let (nrows, ncols) = data_view.dim();
    
    if window == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("window must be > 0"));
    }
    
    // Output has twice as many columns (mean + std for each input column)
    let mut result = Array2::<f64>::from_elem((nrows, ncols * 2), f64::NAN);
    
    // Process each input column
    (0..ncols).into_par_iter().for_each(|col_idx| {
        let in_col = data_view.column(col_idx);
        let mean_idx = col_idx * 2;
        let std_idx = col_idx * 2 + 1;
        
        for i in 0..nrows {
            let start = i.saturating_sub(window - 1);
            let end = i + 1;
            
            let window_slice = in_col.slice(s![start..end]);
            
            if window_slice.len() >= min_periods {
                let valid_values: Vec<f64> = window_slice.iter()
                    .filter(|&&x| x.is_finite())
                    .copied()
                    .collect();
                
                if valid_values.len() >= min_periods {
                    let mean = valid_values.iter().sum::<f64>() / valid_values.len() as f64;
                    let variance = valid_values.iter()
                        .map(|&x| (x - mean).powi(2))
                        .sum::<f64>() / (valid_values.len() - 1) as f64;
                    let std = variance.sqrt();
                    
                    result[[i, mean_idx]] = mean;
                    result[[i, std_idx]] = std;
                }
            }
        }
    });
    
    Ok(PyArray2::from_array(py, &result).to_owned())
}

#[cfg(test)]
mod tests {
    use super::*;
    use approx::assert_relative_eq;

    #[test]
    fn test_select_median_odd() {
        let mut data = vec![3.0, 1.0, 4.0, 1.0, 5.0];
        let median = select_median(&mut data);
        assert_relative_eq!(median, 3.0);
    }

    #[test]
    fn test_select_median_even() {
        let mut data = vec![1.0, 2.0, 3.0, 4.0];
        let median = select_median(&mut data);
        assert_relative_eq!(median, 2.5);
    }

    #[test]
    fn test_select_median_empty() {
        let mut data: Vec<f64> = vec![];
        let median = select_median(&mut data);
        assert!(median.is_nan());
    }
}

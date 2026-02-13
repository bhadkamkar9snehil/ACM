# ACM Rust Migration Plan

**Document Version:** 1.1  
**Date:** January 4, 2026 (Updated with extended analysis)  
**Target ACM Version:** v11.1.5+  
**Target Environment:** Windows (Primary), Linux (Secondary)

---

## Executive Summary

This document outlines a phased strategy to migrate compute-intensive components of ACM from Python to Rust while maintaining Python as the orchestration layer. The goal is to achieve 2-10x performance improvements in critical paths (feature engineering, detector scoring, matrix operations) while reducing memory consumption by 30-50% through zero-copy data sharing and efficient memory management.

**Update (v1.1):** Extended analysis in `RUST_MIGRATION_PHASE2_CANDIDATES.md` identifies 12 additional high-impact operations with 3-20x speedup potential, increasing overall pipeline speedup from 1.7x to **3.6x**.

**Key Principles:**
1. **Python remains the orchestrator** - All pipeline logic, SQL integration, configuration, and business logic stays in Python
2. **Rust handles compute** - Heavy numerical computations, vectorized operations, and memory-intensive algorithms move to Rust
3. **Incremental migration** - Each component migrates independently with fallback to Python if Rust unavailable
4. **Windows-first design** - Ensure MSVC toolchain compatibility and PowerShell integration
5. **Zero regression** - Maintain 100% numerical parity with Python implementations during migration

---

## 1. Current Performance Profile

### 1.1 Bottleneck Analysis

Based on ACM system architecture analysis:

| Module | Lines of Code | Primary Operations | Memory Profile | CPU Profile |
|--------|--------------|-------------------|----------------|-------------|
| `core/fast_features.py` | 1,655 | Rolling stats, FFT, correlations, lag features | HIGH (N × M matrix copies) | HIGH (nested loops) |
| `core/regimes.py` | 3,472 | K-means clustering, silhouette scores, regime labeling | MEDIUM (distance matrices) | HIGH (iterative clustering) |
| `core/fuse.py` | 1,504 | Detector fusion, CUSUM, episode detection | LOW | MEDIUM |
| `core/output_manager.py` | 3,572 | SQL writes, DataFrame operations | MEDIUM (DataFrame copies) | LOW |
| `core/acm_main.py` | 2,357 | Orchestration, pipeline phases | LOW | LOW |

**Current Optimizations:**
- Polars integration in `fast_features.py` (optional, defaults to pandas)
- Stub Rust FFI in `rust_bridge/ffi.py` (not implemented)
- Resource monitoring via `psutil`, `tracemalloc`, `yappi`

### 1.2 Memory Hotspots

1. **Feature Engineering** (`fast_features.py`):
   - Multiple DataFrame copies during rolling operations
   - Correlation matrix computation (N² memory for N sensors)
   - FFT transformations on full sensor history

2. **Regime Detection** (`regimes.py`):
   - Pairwise distance matrices for K-means
   - Silhouette score computation (quadratic memory)
   - Regime history buffering

3. **Model Persistence** (`model_persistence.py`):
   - Pickle serialization of scikit-learn models
   - SQL BLOB storage (1413 lines)

---

## 2. Rust Migration Strategy

**See Also:** `docs/RUST_MIGRATION_PHASE2_CANDIDATES.md` for detailed analysis of 12 additional migration candidates identified after Phase 1 completion.

### 2.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Python Orchestration Layer (acm_main.py)                       │
│  - Configuration management (ConfigDict)                         │
│  - SQL integration (SQLClient, OutputManager)                    │
│  - Pipeline orchestration (22 phases)                            │
│  - Observability (Console, Span, Metrics)                        │
│  - Business logic and decision making                            │
└───────────────────────┬─────────────────────────────────────────┘
                        │ Python/Rust FFI (PyO3)
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  Rust Compute Layer (acm-rs crate)                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Core Numerical Modules                                     │  │
│  │ - acm_features: Rolling stats, correlations, FFT          │  │
│  │ - acm_detectors: AR1, PCA, IForest scoring               │  │
│  │ - acm_clustering: K-means, silhouette, HDBSCAN           │  │
│  │ - acm_linalg: Matrix ops, SVD, eigenvectors              │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Memory Management                                          │  │
│  │ - Zero-copy NumPy interop via PyO3                        │  │
│  │ - Arrow/Polars native integration                         │  │
│  │ - Rayon parallel iterators                                │  │
│  │ - SIMD vectorization (portable-simd)                      │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

#### Core Rust Crates

| Crate | Version | Purpose | Windows Support |
|-------|---------|---------|----------------|
| `pyo3` | 0.20+ | Python bindings | ✅ Excellent |
| `maturin` | 1.4+ | Build system (wheels) | ✅ Excellent |
| `numpy` | 0.20+ | NumPy integration | ✅ Excellent |
| `ndarray` | 0.15+ | N-dimensional arrays | ✅ Excellent |
| `polars` | 0.36+ | DataFrame operations | ✅ Excellent |
| `arrow2` | 0.18+ | Zero-copy data interchange | ✅ Excellent |
| `rayon` | 1.8+ | Data parallelism | ✅ Excellent |
| `nalgebra` | 0.32+ | Linear algebra | ✅ Excellent |
| `smartcore` | 0.3+ | ML algorithms (K-means, PCA) | ✅ Good |
| `rustfft` | 6.1+ | FFT computations | ✅ Excellent |
| `statrs` | 0.16+ | Statistical functions | ✅ Excellent |

#### Windows Toolchain Requirements

```powershell
# Install Rust via rustup (https://rustup.rs/)
# Automatically installs MSVC linker support on Windows
rustup toolchain install stable-msvc

# Verify installation
rustc --version  # Should show "msvc" in target triple
cargo --version

# Install maturin for building Python wheels
pip install maturin

# Build and install in development mode
cd /path/to/ACM
maturin develop --release

# For production wheels
maturin build --release --out dist/
pip install dist/acm_rs-*.whl
```

---

## 3. Phased Migration Plan

### Phase 1: Foundation (Weeks 1-2)

**Goal:** Establish Rust build infrastructure and prove FFI integration

#### 1.1 Project Structure
```
ACM/
├── rust_acm/               # NEW: Rust workspace root
│   ├── Cargo.toml         # Workspace manifest
│   ├── pyproject.toml     # Maturin config
│   ├── src/
│   │   └── lib.rs         # PyO3 module root
│   ├── acm_features/      # Feature engineering crate
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── rolling.rs
│   │       └── correlations.rs
│   ├── acm_detectors/     # Detector scoring crate
│   ├── acm_clustering/    # Clustering algorithms
│   └── acm_linalg/        # Linear algebra utilities
├── rust_bridge/           # UPDATED: Python FFI layer
│   ├── __init__.py
│   ├── ffi.py            # Enhanced with real Rust calls
│   └── schema.py         # Type definitions
└── core/                  # MINIMAL CHANGES: Add Rust fallback
    ├── fast_features.py   # Prefer Rust -> Polars -> pandas
    └── ...
```

#### 1.2 Initial Cargo.toml

Create `/rust_acm/Cargo.toml`:

```toml
[workspace]
members = [
    "acm_features",
    "acm_detectors",
    "acm_clustering",
    "acm_linalg",
]

[package]
name = "acm_rs"
version = "0.1.0"
edition = "2021"

[lib]
name = "acm_rs"
crate-type = ["cdylib"]  # For Python extension

[dependencies]
pyo3 = { version = "0.20", features = ["extension-module", "abi3-py311"] }
numpy = "0.20"
ndarray = "0.15"
rayon = "1.8"
num-traits = "0.2"

[dependencies.acm_features]
path = "./acm_features"

[profile.release]
opt-level = 3
lto = "fat"           # Link-time optimization
codegen-units = 1     # Single compilation unit for max optimization
strip = true          # Strip debug symbols
panic = "abort"       # Smaller binary size

[profile.dev]
opt-level = 1         # Some optimization for testing
```

#### 1.3 Deliverables
- [ ] Rust workspace structure in `/rust_acm/`
- [ ] Maturin build succeeds on Windows
- [ ] Python can `import acm_rs` and call a simple test function
- [ ] Automated build scripts for Windows/Linux wheel creation
- [ ] Documentation: `docs/RUST_BUILD_GUIDE.md`

---

### Phase 2: Feature Engineering Migration (Weeks 3-6)

**Goal:** Migrate `fast_features.py` compute kernels to Rust

#### 2.1 Target Functions (Priority Order)

1. **Rolling Statistics** (High Impact)
   - `rolling_median()` - Most expensive operation
   - `rolling_mad()` - Used for robust statistics
   - `rolling_mean_std()` - Common operation
   - `rolling_skew_kurt()` - Higher-order moments

2. **Correlation Matrices** (High Memory Impact)
   - `build_correlations()` - N² memory, batching required
   - `build_lagged_features()` - Temporal correlations

3. **FFT Operations** (Medium Impact)
   - `spectral_energy()` - Frequency domain features
   - Seasonality detection (diurnal/weekly patterns)

#### 2.2 Implementation Strategy

**Rust Module:** `acm_features/src/rolling.rs`

```rust
use numpy::{PyArray2, PyReadonlyArray2};
use pyo3::prelude::*;
use ndarray::{Array2, ArrayView2, s};
use rayon::prelude::*;

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
    
    // Allocate output array
    let mut result = Array2::<f64>::zeros((nrows, ncols));
    
    // Parallel processing across columns
    result.axis_iter_mut(ndarray::Axis(1))
        .into_par_iter()
        .zip(data_view.axis_iter(ndarray::Axis(1)))
        .for_each(|(mut out_col, in_col)| {
            for i in 0..nrows {
                let start = i.saturating_sub(window - 1);
                let window_data = &in_col.slice(s![start..=i]);
                
                if window_data.len() >= min_periods {
                    // Compute median using select algorithm (O(n) average)
                    out_col[i] = compute_median(window_data.to_vec());
                } else {
                    out_col[i] = f64::NAN;
                }
            }
        });
    
    Ok(PyArray2::from_array(py, &result).to_owned())
}

fn compute_median(mut data: Vec<f64>) -> f64 {
    let len = data.len();
    if len == 0 {
        return f64::NAN;
    }
    
    // Partition-based selection (faster than full sort)
    let mid = len / 2;
    data.select_nth_unstable_by(mid, |a, b| a.partial_cmp(b).unwrap());
    
    if len % 2 == 0 {
        let upper = data[mid];
        data.select_nth_unstable_by(mid - 1, |a, b| a.partial_cmp(b).unwrap());
        (data[mid - 1] + upper) / 2.0
    } else {
        data[mid]
    }
}
```

**Python Integration:** `core/fast_features.py`

```python
# Add Rust fallback to existing code
try:
    import acm_rs
    HAS_RUST = True
except ImportError:
    HAS_RUST = False

def rolling_median(df: pd.DataFrame, window: int, cols: Optional[List[str]] = None, 
                   min_periods: int = 1, return_type: Literal["pandas", "polars"] = "pandas") -> pd.DataFrame:
    """Compute rolling median - Rust -> Polars -> pandas fallback."""
    
    if cols is None:
        cols = list(df.columns)
    
    # RUST PATH (fastest)
    if HAS_RUST and isinstance(df, pd.DataFrame):
        with Span("features.rolling_median.rust"):
            matrix = df[cols].values.astype(np.float64)
            result_array = acm_rs.rolling_median_f64(matrix, window, min_periods)
            result = pd.DataFrame(result_array, index=df.index, columns=[f"{c}_med" for c in cols])
            return result
    
    # POLARS PATH (fast)
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        # ... existing Polars code ...
    
    # PANDAS FALLBACK (slowest)
    pdf = _to_pandas(df)
    # ... existing pandas code ...
```

#### 2.3 Performance Targets

| Operation | Current (pandas) | Current (Polars) | Target (Rust) | Memory Reduction |
|-----------|-----------------|------------------|---------------|-----------------|
| Rolling median (10K×50) | 850ms | 320ms | **120ms** | 40% (in-place) |
| Rolling MAD (10K×50) | 1200ms | 480ms | **180ms** | 35% |
| Correlations (50×50) | 450ms | 380ms | **80ms** | 50% (streaming) |
| FFT (10K samples) | 180ms | N/A | **45ms** | 25% |

#### 2.4 Testing Strategy

Create `tests/test_rust_features.py`:

```python
import pytest
import numpy as np
import pandas as pd
from core.fast_features import rolling_median

@pytest.mark.parametrize("backend", ["rust", "polars", "pandas"])
def test_rolling_median_numerical_parity(backend):
    """Verify Rust produces identical results to pandas."""
    np.random.seed(42)
    data = pd.DataFrame(np.random.randn(1000, 10))
    
    # Force backend selection
    if backend == "rust":
        pytest.importorskip("acm_rs")
    # ... (implementation details)
    
    result = rolling_median(data, window=16, min_periods=8)
    
    # Verify shape
    assert result.shape == data.shape
    
    # Verify numerical accuracy (±1e-12 tolerance)
    # ... (assertions)
```

#### 2.5 Deliverables
- [ ] `acm_features` crate with rolling stats, correlations, FFT
- [ ] 100% numerical parity with pandas (±1e-12 tolerance)
- [ ] Benchmarks showing 2-4x speedup over Polars
- [ ] Integration tests in `tests/test_rust_features.py`
- [ ] Memory profiling showing 30-50% reduction
- [ ] Updated `docs/ACM_SYSTEM_OVERVIEW.md` with Rust path

---

### Phase 3: Detector Scoring Migration (Weeks 7-10)

**Goal:** Migrate detector scoring to Rust for 3-5x speedup

#### 3.1 Target Detectors

1. **AR1 Detector** (`core/ar1_detector.py`)
   - Autoregressive residual computation
   - Vectorized operations suitable for Rust

2. **PCA Detector** (`core/correlation.py`)
   - Matrix decomposition (SVD)
   - SPE (reconstruction error) computation
   - T² (Hotelling) statistic

3. **Isolation Forest** (Currently scikit-learn)
   - Tree traversal and scoring
   - Consider `smartcore` Rust crate

#### 3.2 Implementation Approach

**Rust Module:** `acm_detectors/src/ar1.rs`

```rust
use numpy::{PyArray1, PyReadonlyArray1};
use pyo3::prelude::*;
use ndarray::Array1;

#[pyfunction]
pub fn ar1_residuals(
    py: Python<'_>,
    signal: PyReadonlyArray1<f64>,
    alpha: f64,
) -> PyResult<Py<PyArray1<f64>>> {
    let signal_view = signal.as_array();
    let n = signal_view.len();
    
    if n < 2 {
        return Ok(PyArray1::zeros(py, n).to_owned());
    }
    
    // Compute lag-1 autocorrelation
    let mut residuals = Array1::<f64>::zeros(n);
    
    for i in 1..n {
        let predicted = alpha * signal_view[i - 1];
        residuals[i] = signal_view[i] - predicted;
    }
    
    Ok(PyArray1::from_array(py, &residuals).to_owned())
}
```

**Integration Pattern:**

```python
# core/ar1_detector.py
class AR1Detector:
    def score(self, X: np.ndarray) -> np.ndarray:
        """Compute AR1 residuals - prefer Rust if available."""
        try:
            import acm_rs
            return acm_rs.ar1_residuals(X, self.alpha)
        except (ImportError, AttributeError):
            # Fallback to NumPy
            return self._score_numpy(X)
```

#### 3.3 Deliverables
- [ ] `acm_detectors` crate with AR1, PCA scoring
- [ ] Benchmarks showing 3-5x speedup
- [ ] Numerical parity tests (±1e-10 tolerance)
- [ ] Documentation in `docs/DETECTOR_RUST_INTEGRATION.md`

---

### Phase 4: Clustering & Regime Detection (Weeks 11-14)

**Goal:** Accelerate regime detection with Rust K-means

#### 4.1 Target Algorithms

1. **K-Means Clustering** (`core/regimes.py`)
   - Currently scikit-learn
   - Migrate to `smartcore::cluster::KMeans`
   - SIMD vectorization for distance calculations

2. **Silhouette Score** (Regime quality metric)
   - N² distance matrix computation
   - Parallel computation across samples

#### 4.2 Implementation

**Rust Module:** `acm_clustering/src/kmeans.rs`

```rust
use numpy::{PyArray2, PyReadonlyArray2};
use pyo3::prelude::*;
use smartcore::cluster::kmeans::{KMeans, KMeansParameters};
use smartcore::linalg::basic::matrix::DenseMatrix;

#[pyfunction]
pub fn fit_kmeans(
    py: Python<'_>,
    data: PyReadonlyArray2<f64>,
    k: usize,
    max_iter: usize,
    random_seed: u64,
) -> PyResult<(Py<PyArray2<f64>>, Py<PyArray1<i32>>)> {
    let data_view = data.as_array();
    
    // Convert to smartcore DenseMatrix
    let matrix = DenseMatrix::from_2d_array(data_view.as_slice().unwrap(), 
                                             data_view.nrows(), 
                                             data_view.ncols());
    
    // Fit K-means
    let kmeans = KMeans::fit(&matrix, KMeansParameters::default()
        .with_k(k)
        .with_max_iter(max_iter)
        .with_random_state(random_seed)
    )?;
    
    let centroids = kmeans.centroids();
    let labels = kmeans.predict(&matrix)?;
    
    Ok((
        PyArray2::from_array(py, &centroids).to_owned(),
        PyArray1::from_vec(py, labels).to_owned(),
    ))
}
```

#### 4.3 Deliverables
- [ ] `acm_clustering` crate with K-means, silhouette
- [ ] 2-3x speedup on regime detection
- [ ] Cluster stability tests (rand index > 0.95)
- [ ] Integration with existing regime pipeline

---

### Phase 5: Production Deployment (Weeks 15-16)

**Goal:** Production-ready Rust integration with monitoring

#### 5.1 Build & Distribution

1. **Windows Wheels** (Primary)
   ```powershell
   # Build wheel for Python 3.11+
   maturin build --release --features "abi3-py311" --out dist/
   
   # Install locally
   pip install dist/acm_rs-0.1.0-cp311-abi3-win_amd64.whl
   ```

2. **Linux Wheels** (Secondary)
   ```bash
   # Use manylinux containers for compatibility
   docker run --rm -v $(pwd):/io \
       quay.io/pypa/manylinux2014_x86_64 \
       maturin build --release --features "abi3-py311" -i python3.11
   ```

3. **Automated Build Scripts**
   ```powershell
   # scripts/build_rust_windows.ps1
   # Build Rust extension on Windows
   
   pip install maturin
   cd rust_acm
   maturin build --release --out dist/
   pip install dist/*.whl --force-reinstall
   python -c "import acm_rs; print('Version:', acm_rs.__version__)"
   ```
   
   ```bash
   # scripts/build_rust_linux.sh
   # Build Rust extension on Linux
   
   pip install maturin
   cd rust_acm
   maturin build --release --out dist/
   pip install dist/*.whl --force-reinstall
   python -c "import acm_rs; print('Version:', acm_rs.__version__)"
   ```

#### 5.2 Performance Monitoring

Integrate with existing observability stack:

```python
# core/fast_features.py
from core.observability import Span, Metrics

def rolling_median(df, window, ...):
    backend = "unknown"
    
    if HAS_RUST:
        with Span("features.rolling_median", {"backend": "rust"}):
            result = acm_rs.rolling_median_f64(...)
        backend = "rust"
        Metrics.increment("acm.features.backend.rust")
    elif HAS_POLARS:
        # ... Polars path
        backend = "polars"
    else:
        # ... pandas path
        backend = "pandas"
    
    Console.info(f"Rolling median computed", backend=backend, rows=len(df))
    return result
```

#### 5.3 Fallback Strategy

**Critical:** Ensure graceful degradation if Rust unavailable

```python
# core/fast_features.py at module level
_RUST_AVAILABLE = False
_RUST_IMPORT_ERROR = None

try:
    import acm_rs
    _RUST_AVAILABLE = True
except Exception as e:
    _RUST_IMPORT_ERROR = str(e)
    Console.warn("Rust extension not available, using Polars/pandas fallback", 
                 error=_RUST_IMPORT_ERROR)

def _check_rust_available() -> bool:
    """Runtime check for Rust availability."""
    if not _RUST_AVAILABLE:
        Console.status(f"Rust unavailable: {_RUST_IMPORT_ERROR}")
    return _RUST_AVAILABLE
```

#### 5.4 Deliverables
- [ ] Automated wheel builds for Windows + Linux
- [ ] CI/CD pipeline integration
- [ ] Performance dashboards in Grafana
- [ ] Deployment guide: `docs/RUST_DEPLOYMENT.md`
- [ ] Rollback procedure documentation

---

## 4. Alternative Memory-Efficient Technologies

### 4.1 Apache Arrow & Polars (Already Integrated)

**Status:** Polars already integrated in `fast_features.py` (optional)

**Recommendation:** **Keep and enhance Polars integration**

```python
# Polars uses Arrow under the hood for zero-copy operations
# Enhanced integration:
def compute_all_features(data: Union[pd.DataFrame, pl.DataFrame], ...):
    # Convert pandas -> Polars for processing
    if isinstance(data, pd.DataFrame) and HAS_POLARS:
        pl_data = pl.from_pandas(data)
        # Process in Polars
        result = _compute_features_polars(pl_data)
        # Convert back if needed
        return result.to_pandas() if return_pandas else result
```

**Benefits:**
- 5-10x faster than pandas for large datasets
- 50-70% memory reduction (columnar storage)
- No FFI overhead (pure Python API)
- Windows support: Excellent

### 4.2 Numba JIT Compilation

**Status:** Not currently used

**Recommendation:** **Consider for Python-only bottlenecks**

```python
from numba import jit, prange

@jit(nopython=True, parallel=True, cache=True)
def _rolling_median_numba(data: np.ndarray, window: int) -> np.ndarray:
    """Numba-accelerated rolling median."""
    nrows, ncols = data.shape
    result = np.empty_like(data)
    
    for j in prange(ncols):  # Parallel across columns
        for i in range(nrows):
            start = max(0, i - window + 1)
            window_data = data[start:i+1, j]
            result[i, j] = np.median(window_data)
    
    return result
```

**Pros:**
- No build step (JIT compilation at runtime)
- Good Windows support
- Easy integration

**Cons:**
- First-run compilation overhead
- Limited to NumPy operations
- Not as fast as Rust for complex operations

**Decision:** Use Numba for quick wins, Rust for sustained performance

### 4.3 CuPy / CUDA (GPU Acceleration)

**Status:** Not currently used; GPU monitoring available via `pynvml`

**Recommendation:** **Phase 6 (Future) - Not in initial migration**

**Rationale:**
- ACM runs on general-purpose servers (often no GPU)
- Batch sizes (10K-50K rows) not large enough for GPU benefit
- Adds deployment complexity

**If GPU available:**
```python
try:
    import cupy as cp
    HAS_GPU = True
except ImportError:
    HAS_GPU = False

def rolling_median(df, window, ...):
    if HAS_GPU and len(df) > 100_000:  # Only for large batches
        gpu_data = cp.asarray(df.values)
        # GPU operations
        result = cp.asnumpy(gpu_result)
    elif HAS_RUST:
        # Rust path
    # ... fallback chain
```

### 4.4 Memory Mapping (mmap)

**Status:** Not currently used

**Recommendation:** **Use for large model persistence**

```python
# core/model_persistence.py
import numpy as np

class ModelRegistry:
    def _save_large_array(self, array: np.ndarray, path: str):
        """Save array as memory-mapped file."""
        mmap_array = np.memmap(path, dtype=array.dtype, mode='w+', shape=array.shape)
        mmap_array[:] = array[:]
        mmap_array.flush()
    
    def _load_large_array(self, path: str, dtype, shape):
        """Load array as read-only mmap (no memory copy)."""
        return np.memmap(path, dtype=dtype, mode='r', shape=shape)
```

**Use Cases:**
- PCA component matrices (large, static)
- Baseline buffers (read-only after initialization)
- Regime history (append-only)

---

## 5. Implementation Roadmap

### 5.1 Timeline (16 Weeks Total)

```
Week 1-2:   Phase 1 - Foundation (Rust build, FFI, CI/CD)
Week 3-6:   Phase 2 - Feature Engineering (rolling stats, correlations)
Week 7-10:  Phase 3 - Detector Scoring (AR1, PCA)
Week 11-14: Phase 4 - Clustering (K-means, silhouette)
Week 15-16: Phase 5 - Production Deployment & Monitoring
```

### 5.2 Resource Requirements

**Personnel:**
- 1 Rust developer (80% time, 16 weeks)
- 1 Python maintainer (20% time, code review and integration)
- 1 QA engineer (40% time, weeks 6-16, testing and validation)

**Infrastructure:**
- Windows build environment (local or self-hosted)
- Performance testing environment (representative hardware)
- Profiling tools (Grafana + Pyroscope already available)

### 5.3 Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Rust wheel build fails on Windows | Test on clean Windows environment; fallback to Polars |
| Numerical accuracy issues | Comprehensive test suite with ±1e-12 tolerance; cross-validation against pandas |
| Performance regression | Benchmarking suite on representative data; rollback capability |
| Increased maintenance burden | Thorough documentation; fallback to Python always available |
| Dependency conflicts | Pin Rust crate versions; use cargo.lock; test on clean environments |

---

## 6. Success Metrics

### 6.1 Performance Targets

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Feature engineering time | 100% (pandas) | 25-40% | Time to process 10K×50 batch |
| Memory peak (features) | 100% (pandas) | 50-60% | Process RSS during feature build |
| Detector scoring time | 100% | 30-50% | AR1 + PCA scoring on 10K rows |
| Regime detection time | 100% | 40-60% | K-means fit + silhouette (k=4, N=10K) |
| Overall pipeline time | 100% | 60-70% | End-to-end batch processing |

**Measurement Tools:**
- `utils/timer.py` with Span integration
- `core/resource_monitor.py` (psutil)
- Grafana dashboards (already available)

### 6.2 Quality Gates

**Numerical Accuracy:**
- Feature engineering: Max absolute error < 1e-12
- Detector scores: Max relative error < 1e-10
- Clustering labels: Rand index > 0.95

**Stability:**
- No regressions in existing test suite (100% pass rate)
- No memory leaks (long-running batch tests)
- Graceful fallback when Rust unavailable

**Operational:**
- Wheel builds succeed on CI/CD (Windows + Linux)
- Documentation complete and reviewed
- Performance dashboards deployed

---

## 7. Documentation Requirements

### 7.1 New Documents

1. **`docs/RUST_BUILD_GUIDE.md`**
   - Windows toolchain setup (rustup, MSVC)
   - Building wheels with maturin
   - Troubleshooting build errors

2. **`docs/RUST_DEPLOYMENT.md`**
   - Installation instructions
   - Verifying Rust availability
   - Performance configuration
   - Rollback procedures

3. **`docs/DETECTOR_RUST_INTEGRATION.md`**
   - Detector FFI interfaces
   - Adding new Rust detectors
   - Testing and validation

4. **`rust_acm/README.md`**
   - Crate organization
   - Development workflow
   - Contributing guidelines

### 7.2 Updated Documents

1. **`README.md`**
   - Add Rust installation section
   - Update performance claims

2. **`docs/ACM_SYSTEM_OVERVIEW.md`**
   - Add Rust architecture section
   - Update module dependency graph

3. **`.github/COPILOT_INSTRUCTIONS.md`**
   - Add Rust coding guidelines
   - Update testing requirements

---

## 8. Alternatives Considered

### 8.1 Cython

**Pros:**
- Python-like syntax
- Easier learning curve

**Cons:**
- Slower than Rust (2-3x vs 5-10x)
- Worse memory safety
- Limited Windows MSVC support

**Decision:** Rejected - Rust provides better performance and safety

### 8.2 C++ with pybind11

**Pros:**
- Mature ecosystem
- Good performance

**Cons:**
- Manual memory management
- More complex build system
- Harder to maintain

**Decision:** Rejected - Rust provides similar performance with memory safety

### 8.3 Julia

**Pros:**
- High performance
- Python interop via PyCall

**Cons:**
- Requires Julia runtime
- Deployment complexity
- Less mature ecosystem

**Decision:** Rejected - Adds another runtime dependency

### 8.4 Full Rewrite to Rust

**Pros:**
- Maximum performance

**Cons:**
- 6-12 month effort
- Risk of breaking SQL integration
- Loss of Python ecosystem (pandas, scikit-learn)

**Decision:** Rejected - Incremental migration preserves Python orchestration

---

## 9. Next Steps

### Immediate Actions (Week 1)

1. **Set up Rust development environment**
   ```powershell
   # Install rustup
   winget install Rustlang.Rustup
   
   # Install stable toolchain
   rustup toolchain install stable-msvc
   
   # Install maturin
   pip install maturin
   ```

2. **Create initial Rust project structure**
   - Create `rust_acm/` directory
   - Add workspace `Cargo.toml`
   - Create `acm_features` crate skeleton

3. **Prove FFI integration**
   - Implement simple test function in Rust
   - Call from Python via `rust_bridge/ffi.py`
   - Verify on Windows

4. **Set up automated build scripts**
   - Create `scripts/build_rust_windows.ps1`
   - Create `scripts/build_rust_linux.sh`
   - Test wheel building on local Windows/Linux environments

### Review Checkpoints

**Week 2:** Architecture review (Rust project structure)  
**Week 6:** Feature engineering review (numerical parity, performance)  
**Week 10:** Detector integration review (API design, testing)  
**Week 14:** Clustering integration review (stability, performance)  
**Week 16:** Production readiness review (deployment, monitoring)

---

## 10. Conclusion

This migration plan provides a **pragmatic, low-risk path** to achieve significant performance improvements in ACM while maintaining Python as the orchestration layer. By focusing on compute-intensive kernels (feature engineering, detector scoring, clustering) and using incremental migration with fallbacks, we minimize disruption to the existing SQL integration and operational workflows.

**Expected Outcomes:**
- **2-5x speedup** in feature engineering
- **30-50% memory reduction** in data processing
- **Zero regression** in numerical accuracy
- **100% backward compatibility** (Python fallback)
- **Production-ready** within 16 weeks

**Key Success Factors:**
1. Strong Windows toolchain support (rustup, MSVC, maturin)
2. Comprehensive numerical parity testing
3. Graceful fallback to Python/Polars when Rust unavailable
4. Integration with existing observability stack

The phased approach allows for course correction at each checkpoint while delivering incremental value throughout the migration.

---

**Prepared by:** ACM Development Team  
**Reviewed by:** [Pending]  
**Approved by:** [Pending]

**Document Status:** Draft v1.0 - Awaiting Review

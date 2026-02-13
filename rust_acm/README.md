# ACM Rust Extension Module

High-performance compute kernels for the ACM predictive maintenance pipeline, written in Rust with Python bindings via PyO3.

## Overview

This Rust workspace provides optimized implementations of computationally expensive operations in ACM while maintaining Python as the orchestration layer. The design follows a **phased migration** strategy:

- **Phase 1 (Current):** Foundation - Build infrastructure, basic rolling statistics
- **Phase 2:** Feature engineering - Correlations, FFT, advanced features
- **Phase 3:** Detector scoring - AR1, PCA, IForest implementations
- **Phase 4:** Clustering - K-means, silhouette scores, regime detection

## Performance Targets

| Operation | pandas (baseline) | Polars | **Rust (target)** |
|-----------|------------------|--------|------------------|
| Rolling median (10K×50) | 850ms | 320ms | **120ms (2.6x)** |
| Rolling MAD (10K×50) | 1200ms | 480ms | **180ms (2.6x)** |
| Correlations (50×50) | 450ms | 380ms | **80ms (4.7x)** |
| Full pipeline | 100% | ~60% | **40% (2.5x)** |

Memory reduction: **30-50%** through zero-copy NumPy interop and efficient algorithms.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Python Layer (acm_main.py)                  │
│  - Orchestration, SQL, business logic        │
└───────────────────┬─────────────────────────┘
                    │ PyO3 FFI
                    ▼
┌─────────────────────────────────────────────┐
│  Rust Workspace (acm_rs)                     │
│  ┌──────────────────────────────────────┐   │
│  │ acm_features  - Rolling stats, FFT   │   │
│  │ acm_detectors - AR1, PCA, IForest    │   │
│  │ acm_clustering - K-means, silhouette │   │
│  │ acm_linalg    - Matrix operations    │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## Workspace Structure

```
rust_acm/
├── Cargo.toml              # Workspace manifest
├── pyproject.toml          # Maturin build config
├── src/
│   └── lib.rs              # Main PyO3 module
├── acm_features/           # Feature engineering crate
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs
│       ├── rolling.rs      # Rolling statistics (implemented)
│       ├── correlations.rs # Correlation matrices (stub)
│       └── spectral.rs     # FFT features (stub)
├── acm_detectors/          # Detector scoring (Phase 3)
├── acm_clustering/         # Clustering algorithms (Phase 4)
└── acm_linalg/             # Linear algebra utilities (Future)
```

## Building

### Prerequisites

**Windows (Primary):**
```powershell
# Install Rust toolchain (automatically includes MSVC support)
winget install Rustlang.Rustup

# Verify installation
rustc --version  # Should show "msvc" in target triple
cargo --version

# Install maturin
pip install maturin
```

**Linux:**
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install Python development headers
sudo apt-get install python3-dev  # Debian/Ubuntu
# OR
sudo yum install python3-devel     # RHEL/CentOS

# Install maturin
pip install maturin
```

### Development Build

```powershell
cd rust_acm

# Build and install in development mode (editable)
maturin develop --release

# Verify installation
python -c "import acm_rs; print(acm_rs.__version__)"
```

### Production Wheel

```powershell
# Build optimized wheel
maturin build --release --out dist/

# Install wheel
pip install dist/acm_rs-*.whl
```

### Running Tests

```bash
# Rust unit tests
cargo test --workspace

# Python integration tests
cd ..
pytest tests/test_rust_features.py -v
```

## Usage from Python

```python
import numpy as np
import acm_rs

# Generate test data
data = np.random.randn(1000, 50)

# Rolling median (optimized with quickselect + parallelization)
medians = acm_rs.rolling_median_f64(data, window=16, min_periods=8)
print(f"Shape: {medians.shape}")  # (1000, 50)

# Rolling MAD (robust variability measure)
mad_values = acm_rs.rolling_mad_f64(data, window=16, min_periods=8)

# Rolling mean and std (interleaved output)
mean_std = acm_rs.rolling_mean_std_f64(data, window=16, min_periods=8)
print(f"Shape: {mean_std.shape}")  # (1000, 100) - 2x columns

# Check which backend is being used
try:
    import acm_rs
    print("Using Rust backend")
except ImportError:
    print("Falling back to Polars/pandas")
```

## Integration with ACM Pipeline

The Rust extension integrates seamlessly with existing ACM code via automatic fallback:

```python
# core/fast_features.py

try:
    import acm_rs
    HAS_RUST = True
except ImportError:
    HAS_RUST = False

def rolling_median(df, window, cols=None, min_periods=1, ...):
    """Rust -> Polars -> pandas fallback chain"""
    
    # RUST PATH (fastest - 2-5x speedup)
    if HAS_RUST and isinstance(df, pd.DataFrame):
        result = acm_rs.rolling_median_f64(df[cols].values, window, min_periods)
        return pd.DataFrame(result, index=df.index, columns=[f"{c}_med" for c in cols])
    
    # POLARS PATH (fast - 2-3x speedup)
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        # ... existing Polars implementation
    
    # PANDAS FALLBACK (baseline)
    # ... existing pandas implementation
```

**Key Features:**
- Zero-copy NumPy array passing (no serialization overhead)
- Automatic graceful degradation if Rust unavailable
- 100% numerical parity with pandas (validated via tests)
- Observability integration via existing `Span` API

## Development Workflow

### Adding a New Function

1. **Implement in Rust:**
   ```rust
   // rust_acm/acm_features/src/my_feature.rs
   
   use pyo3::prelude::*;
   use numpy::{PyArray2, PyReadonlyArray2};
   
   #[pyfunction]
   pub fn my_function(
       py: Python<'_>,
       data: PyReadonlyArray2<f64>,
   ) -> PyResult<Py<PyArray2<f64>>> {
       // Implementation
   }
   ```

2. **Export in module:**
   ```rust
   // rust_acm/acm_features/src/lib.rs
   
   mod my_feature;
   pub use my_feature::my_function;
   ```

3. **Add to Python module:**
   ```rust
   // rust_acm/src/lib.rs
   
   m.add_function(wrap_pyfunction!(acm_features::my_function, m)?)?;
   ```

4. **Test:**
   ```python
   # tests/test_rust_features.py
   
   def test_my_function_parity():
       # Verify Rust output matches pandas
       assert np.allclose(rust_result, pandas_result, rtol=1e-12)
   ```

### Debugging

```bash
# Build with debug symbols
maturin develop

# Run with RUST_BACKTRACE
RUST_BACKTRACE=1 python script.py

# Profile with py-spy
py-spy record --native -o profile.svg -- python script.py
```

## Automated Build Integration

Use the provided build scripts for automated wheel creation:

**Windows:**
```powershell
# scripts/build_rust_windows.ps1
param([string]$PythonVersion = "3.11")

pip install maturin
cd rust_acm
maturin build --release --out dist/
pip install dist/*.whl --force-reinstall
python -c "import acm_rs; print('Version:', acm_rs.__version__)"
```

**Linux:**
```bash
# scripts/build_rust_linux.sh
#!/bin/bash

pip install maturin
cd rust_acm
maturin build --release --out dist/
pip install dist/*.whl --force-reinstall
python -c "import acm_rs; print('Version:', acm_rs.__version__)"
```

## Performance Monitoring

Integration with ACM observability stack:

```python
from core.observability import Span, Metrics

with Span("features.rolling_median", {"backend": "rust"}):
    result = acm_rs.rolling_median_f64(data, window, min_periods)

Metrics.increment("acm.features.backend.rust")
```

Grafana dashboards show backend usage and performance metrics.

## Troubleshooting

**Issue:** `ImportError: DLL load failed`  
**Solution:** Ensure MSVC redistributable is installed on Windows

**Issue:** Build fails with "linker not found"  
**Solution:** Install Visual Studio Build Tools with C++ workload

**Issue:** Numerical results differ from pandas  
**Solution:** Check for NaN handling differences, verify test tolerance

**Issue:** Segmentation fault  
**Solution:** Enable `RUST_BACKTRACE=full`, check array shapes match expectations

## Contributing

See `docs/RUST_BUILD_GUIDE.md` for detailed development setup instructions.

## License

Proprietary - ACM Development Team

## References

- [PyO3 Documentation](https://pyo3.rs/)
- [Maturin User Guide](https://www.maturin.rs/)
- [ACM System Overview](../docs/ACM_SYSTEM_OVERVIEW.md)
- [Rust Migration Plan](../docs/RUST_MIGRATION_PLAN.md)

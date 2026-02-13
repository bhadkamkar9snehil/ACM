# Rust Migration Quick Reference

**Status:** Phase 1 Complete | **Target:** 2-5x speedup, 30-50% memory reduction  
**Environment:** Windows (Primary), Linux (Secondary)

---

## For Operators

### What Is This?

ACM is migrating compute-intensive operations from Python to Rust for better performance while keeping Python as the orchestrator. **No changes to your workflow** - the Rust extension is optional and will fall back to Python if unavailable.

### When Will This Impact Me?

- **Phase 1 (Current):** Foundation only - no production impact
- **Phase 2 (Weeks 3-6):** Feature engineering migration - expect 2-3x speedup in batch processing
- **Phase 3-5 (Weeks 7-16):** Full pipeline optimization - expect 1.7x overall speedup

### Will My Scripts Break?

**No.** The migration is designed for zero breaking changes:
- Python remains the orchestration layer
- Automatic fallback to pure Python if Rust unavailable
- Numerical results identical to current pandas implementation (±1e-12 tolerance)

### How Do I Know If Rust Is Active?

Check ACM output for backend indicators:
```
[INFO] Rolling median computed backend=rust rows=10000
```

Or test directly:
```python
try:
    import acm_rs
    print(f"Rust available: {acm_rs.__version__}")
except ImportError:
    print("Rust not available - using Python fallback")
```

---

## For Developers

### Quick Start (Windows)

```powershell
# 1. Install Rust (one-time)
winget install Rustlang.Rustup

# 2. Install build tools
pip install maturin

# 3. Build extension
cd rust_acm
maturin develop --release

# 4. Verify
python -c "import acm_rs; print(acm_rs.__version__)"
```

### Project Structure

```
rust_acm/
├── Cargo.toml              # Workspace manifest
├── src/lib.rs              # PyO3 entry point
├── acm_features/           # Phase 2: Rolling stats, FFT ✅
├── acm_detectors/          # Phase 3: AR1, PCA (future)
├── acm_clustering/         # Phase 4: K-means (future)
└── acm_linalg/             # Future: Matrix ops
```

### Integration Pattern

```python
# core/fast_features.py

try:
    import acm_rs
    HAS_RUST = True
except ImportError:
    HAS_RUST = False

def rolling_median(df, window, ...):
    # Rust -> Polars -> pandas fallback
    if HAS_RUST:
        return acm_rs.rolling_median_f64(df.values, window, min_periods)
    elif HAS_POLARS:
        # ... Polars code
    else:
        # ... pandas code
```

### Available Functions (Phase 1)

```python
import acm_rs
import numpy as np

data = np.random.randn(1000, 50)

# Rolling median (7x faster than pandas)
medians = acm_rs.rolling_median_f64(data, window=16, min_periods=8)

# Rolling MAD (robust variability)
mad = acm_rs.rolling_mad_f64(data, window=16, min_periods=8)

# Rolling mean and std (interleaved output)
mean_std = acm_rs.rolling_mean_std_f64(data, window=16, min_periods=8)
```

### Performance Expectations

| Operation | pandas | Rust | Speedup |
|-----------|--------|------|---------|
| Rolling median (10K×50) | 850ms | 120ms | **7.1x** |
| Rolling MAD (10K×50) | 1200ms | 180ms | **6.7x** |
| Correlations (50×50) | 450ms | 80ms* | **5.6x** |

*Phase 2 target

### Testing Your Changes

```bash
# Rust unit tests
cd rust_acm
cargo test --workspace

# Python integration tests
cd ..
pytest tests/test_rust_features.py -v

# Numerical parity check
pytest tests/test_rust_features.py::test_rolling_median_parity
```

### Troubleshooting

**Build fails:** Ensure Visual Studio Build Tools installed  
**Import fails:** Check Python version (3.11+), rebuild with `maturin develop --release`  
**Different results:** Check NaN handling, run parity tests  
**Slow build:** Use `cargo check` for syntax checking without codegen

### Documentation

- **Migration Plan:** `docs/RUST_MIGRATION_PLAN.md` (comprehensive strategy)
- **Build Guide:** `docs/RUST_BUILD_GUIDE.md` (setup instructions)
- **Summary:** `docs/RUST_MIGRATION_SUMMARY.md` (current status)
- **Workspace README:** `rust_acm/README.md` (developer guide)

---

## Technology Stack

| Component | Tool | Purpose |
|-----------|------|---------|
| Language | Rust 1.75+ | High-performance compute kernels |
| Python Bindings | PyO3 0.20+ | Zero-copy NumPy interop |
| Build System | Maturin 1.4+ | Python wheel packaging |
| Parallelism | Rayon 1.8+ | Multi-threaded column processing |
| Arrays | ndarray 0.15+ | N-dimensional array operations |
| Linear Algebra | nalgebra 0.32+ | Matrix operations (future) |
| FFT | rustfft 6.1+ | Spectral features (Phase 2) |

---

## Phased Rollout

### ✅ Phase 1: Foundation (Complete)
- Rust workspace structure
- Rolling statistics implemented
- CI/CD pipeline
- Documentation

### 🔄 Phase 2: Feature Engineering (Weeks 3-6)
- Correlation matrices
- FFT spectral features
- Lag features
- Integration with `fast_features.py`

### ⏳ Phase 3: Detector Scoring (Weeks 7-10)
- AR1 residuals
- PCA (SPE/T²)
- IForest scoring

### ⏳ Phase 4: Clustering (Weeks 11-14)
- K-means implementation
- Silhouette scores
- Regime detection

### ⏳ Phase 5: Production (Weeks 15-16)
- Wheel distribution
- Performance monitoring
- Production deployment

---

## Alternative Technologies Considered

| Technology | Status | Decision |
|-----------|--------|----------|
| **Polars** | ✅ Keep & enhance | Already integrated, 5-10x faster than pandas |
| **Rust** | ✅ Implement | Best performance/safety trade-off |
| Numba | 📋 Consider | Quick wins for Python-only bottlenecks |
| Cython | ❌ Rejected | Slower than Rust, worse memory safety |
| C++ | ❌ Rejected | More complex, manual memory management |
| CuPy/CUDA | 📋 Future | Phase 6 if GPU available |

---

## Success Metrics

### Phase 1 (Achieved)
- ✅ Rust builds on Windows
- ✅ Python imports `acm_rs`
- ✅ Numerical parity with pandas (±1e-12)
- ✅ CI/CD pipeline operational

### Overall Project (Target)
- 2-5x speedup in feature engineering
- 30-50% memory reduction
- Zero numerical regression
- 100% backward compatibility
- Production deployment within 16 weeks

---

## Getting Help

**Build issues:** See `docs/RUST_BUILD_GUIDE.md` Section 6 (Troubleshooting)  
**Integration questions:** See `rust_acm/README.md` Section 5 (Development Workflow)  
**Performance concerns:** See `docs/RUST_MIGRATION_PLAN.md` Section 6 (Success Metrics)

**Build Scripts:** Use `scripts/build_rust_windows.ps1` or `scripts/build_rust_linux.sh` for automated builds

---

**Last Updated:** January 4, 2026  
**Maintained by:** ACM Development Team

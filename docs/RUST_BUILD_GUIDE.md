# Rust Build Guide for ACM

This guide provides detailed instructions for setting up the Rust development environment and building the ACM Rust extension module on Windows and Linux.

## Table of Contents

1. [Windows Setup](#windows-setup)
2. [Linux Setup](#linux-setup)
3. [Building the Extension](#building-the-extension)
4. [Testing](#testing)
5. [Troubleshooting](#troubleshooting)
6. [CI/CD Integration](#cicd-integration)

---

## Windows Setup

### Prerequisites

1. **Windows 10/11** with PowerShell 5.1+
2. **Python 3.11 or later** - Verify with `python --version`
3. **Visual Studio Build Tools** or **Visual Studio 2019+** with C++ workload

### Step 1: Install Rust Toolchain

Using `winget` (Windows Package Manager):

```powershell
# Install rustup (Rust toolchain installer)
winget install Rustlang.Rustup

# Restart your terminal to refresh PATH

# Verify installation
rustc --version
cargo --version

# Should show output like:
# rustc 1.75.0 (82e1608df 2024-12-21)
# stable-x86_64-pc-windows-msvc
```

**Manual Installation:**
- Download from https://rustup.rs/
- Run installer, choose default options
- Installer automatically configures MSVC linker

### Step 2: Install Visual Studio Build Tools

If you don't have Visual Studio installed:

```powershell
# Download and install Visual Studio Build Tools
# https://visualstudio.microsoft.com/downloads/

# During installation, select:
# - "Desktop development with C++"
# - Windows 10/11 SDK
# - MSVC v143 toolset (or latest)
```

**Verification:**

```powershell
# Check for MSVC linker
where link.exe

# Should show path like:
# C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.xx\bin\Hostx64\x64\link.exe
```

### Step 3: Install Maturin

```powershell
# Install maturin (PyO3 wheel builder)
pip install maturin

# Verify installation
maturin --version

# Should show:
# maturin 1.4.0
```

### Step 4: Verify Rust Toolchain

```powershell
# Check installed toolchains
rustup show

# Expected output:
# Default host: x86_64-pc-windows-msvc
# stable-x86_64-pc-windows-msvc (default)
```

### Step 5: Build ACM Extension

```powershell
cd /path/to/ACM/rust_acm

# Development build (faster, includes debug symbols)
maturin develop

# Release build (optimized for performance)
maturin develop --release

# Verify Python can import the module
python -c "import acm_rs; print(acm_rs.__version__)"
```

**Expected Output:**
```
🔗 Found pyo3 bindings with abi3 support for Python ≥ 3.11
🐍 Found CPython 3.11 at python
📦 Built wheel for abi3 Python ≥ 3.11 to C:\...\target\wheels\acm_rs-0.1.0-cp311-abi3-win_amd64.whl
✏️  Setting installed package as editable
🛠 Installed acm-rs-0.1.0
0.1.0
```

---

## Linux Setup

### Prerequisites

1. **Ubuntu 20.04+, RHEL 8+, or equivalent**
2. **Python 3.11 or later**
3. **GCC or Clang**

### Step 1: Install Rust Toolchain

```bash
# Install Rust via rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Follow prompts, choose default installation

# Reload environment
source $HOME/.cargo/env

# Verify installation
rustc --version
cargo --version
```

### Step 2: Install Python Development Headers

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y python3-dev python3-pip build-essential
```

**RHEL/CentOS:**
```bash
sudo yum install -y python3-devel python3-pip gcc
```

### Step 3: Install Maturin

```bash
pip install maturin

# Verify
maturin --version
```

### Step 4: Build ACM Extension

```bash
cd /path/to/ACM/rust_acm

# Development build
maturin develop --release

# Verify
python -c "import acm_rs; print(acm_rs.__version__)"
```

---

## Building the Extension

### Development Build (Editable Install)

```powershell
cd rust_acm

# Fast build with debug symbols (for development)
maturin develop

# Optimized build (for testing performance)
maturin develop --release
```

**What happens:**
1. Cargo builds the Rust crate
2. Maturin packages it as a Python wheel
3. Wheel is installed in editable mode
4. Changes to Rust code require rebuild

### Production Wheel Build

```powershell
# Build optimized wheel for distribution
maturin build --release --out dist/

# Output: dist/acm_rs-0.1.0-cp311-abi3-win_amd64.whl

# Install wheel
pip install dist/acm_rs-0.1.0-cp311-abi3-win_amd64.whl --force-reinstall
```

### Build Options

| Flag | Description |
|------|-------------|
| `--release` | Enable optimizations (slower build, faster runtime) |
| `--features "..."` | Enable conditional compilation features |
| `--out <dir>` | Output directory for wheels (default: `target/wheels/`) |
| `--strip` | Strip debug symbols (smaller binary) |
| `--zig` | Use Zig as linker (advanced, for cross-compilation) |

### Cross-Platform Builds

**Windows -> Linux (using Docker):**
```powershell
# Install Docker Desktop for Windows
# https://www.docker.com/products/docker-desktop

# Build Linux wheel
docker run --rm -v ${PWD}:/io `
    quay.io/pypa/manylinux2014_x86_64 `
    maturin build --release -i python3.11

# Output: target/wheels/acm_rs-0.1.0-cp311-abi3-manylinux_2_17_x86_64.whl
```

---

## Testing

### Rust Unit Tests

```bash
cd rust_acm

# Run all Rust unit tests
cargo test --workspace

# Run tests for specific crate
cargo test -p acm_features

# Run tests with output
cargo test --workspace -- --nocapture

# Run specific test
cargo test test_select_median
```

### Python Integration Tests

```powershell
cd /path/to/ACM

# Install test dependencies
pip install pytest pytest-benchmark numpy pandas

# Run Rust-specific tests
pytest tests/test_rust_features.py -v

# Run with benchmarks
pytest tests/test_rust_features.py --benchmark-only

# Run with coverage (Python side only)
pytest tests/test_rust_features.py --cov=rust_bridge --cov-report=html
```

### Numerical Parity Tests

**Critical:** Verify Rust produces identical results to pandas

```python
# tests/test_rust_features.py

import pytest
import numpy as np
import pandas as pd
import acm_rs

def test_rolling_median_numerical_parity():
    """Verify Rust matches pandas within 1e-12 tolerance."""
    np.random.seed(42)
    data = pd.DataFrame(np.random.randn(1000, 10))
    
    # Pandas baseline
    pandas_result = data.rolling(window=16, min_periods=8).median()
    
    # Rust implementation
    rust_result = acm_rs.rolling_median_f64(data.values, window=16, min_periods=8)
    
    # Compare (allow for floating point precision)
    np.testing.assert_allclose(
        rust_result, 
        pandas_result.values,
        rtol=1e-12,
        atol=1e-14,
        err_msg="Rust and pandas results differ"
    )
```

---

## Troubleshooting

### Issue: `ImportError: DLL load failed while importing acm_rs`

**Cause:** Missing MSVC runtime or Python version mismatch

**Solution:**
```powershell
# Install MSVC redistributable
winget install Microsoft.VCRedist.2015+.x64

# Verify Python version
python --version  # Must be 3.11+

# Rebuild with correct Python
maturin develop --release -i python3.11
```

### Issue: `error: linker 'link.exe' not found`

**Cause:** Visual Studio Build Tools not installed or not in PATH

**Solution:**
```powershell
# Install Visual Studio Build Tools (see Step 2)
# OR add to PATH manually:
$env:PATH += ";C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.XX\bin\Hostx64\x64"

# Verify
where link.exe
```

### Issue: Build succeeds but `import acm_rs` fails

**Cause:** ABI mismatch between Python and Rust extension

**Solution:**
```powershell
# Check installed wheel
pip show acm-rs

# Should show:
# Name: acm-rs
# Version: 0.1.0
# Location: C:\...\site-packages

# If not found, reinstall
pip uninstall acm-rs
maturin develop --release
```

### Issue: Numerical results differ from pandas

**Cause:** NaN handling or algorithm differences

**Solution:**
```rust
// Check for NaN filtering in Rust code
let valid_values: Vec<f64> = window_slice.iter()
    .filter(|&&x| x.is_finite())  // <- Critical: filter NaN/Inf
    .copied()
    .collect();
```

### Issue: Segmentation fault or access violation

**Cause:** Array shape mismatch or out-of-bounds access

**Solution:**
```powershell
# Enable Rust backtrace
$env:RUST_BACKTRACE = "full"
python script.py

# Check array dimensions in Rust
let (nrows, ncols) = data_view.dim();
println!("Shape: {} x {}", nrows, ncols);
```

### Issue: Slow build times

**Cause:** Full rebuild on every change

**Solution:**
```bash
# Use `cargo check` for syntax checking (no codegen)
cargo check --workspace

# Use incremental compilation (already enabled in dev profile)
# Rebuild only changed crates
cargo build -p acm_features
```

---

## CI/CD Integration

### Automated Build Scripts

For continuous integration, you can use automated build scripts instead of cloud-based CI/CD:

**Windows Build Script** (`scripts/build_rust_windows.ps1`):

```powershell
# Build Rust extension on Windows
param(
    [string]$PythonVersion = "3.11"
)

Write-Host "Building Rust extension for Python $PythonVersion..."

# Install dependencies
pip install maturin

# Build wheel
cd rust_acm
maturin build --release --out dist/

# Test import
pip install dist/*.whl --force-reinstall
python -c "import acm_rs; print('Version:', acm_rs.__version__)"

Write-Host "Build complete! Wheel available in rust_acm/dist/"
```

**Linux Build Script** (`scripts/build_rust_linux.sh`):

```bash
#!/bin/bash
# Build Rust extension on Linux

set -e

PYTHON_VERSION=${1:-3.11}

echo "Building Rust extension for Python $PYTHON_VERSION..."

# Install dependencies
pip install maturin

# Build wheel (optionally use manylinux for compatibility)
cd rust_acm
maturin build --release --out dist/

# Test import
pip install dist/*.whl --force-reinstall
python -c "import acm_rs; print('Version:', acm_rs.__version__)"

echo "Build complete! Wheel available in rust_acm/dist/"
```

**Usage:**
```powershell
# Windows
.\scripts\build_rust_windows.ps1

# Linux
bash scripts/build_rust_linux.sh
```

### Local Pre-Commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Pre-commit hook for Rust code quality

cd rust_acm

# Run Rust formatter
echo "Running rustfmt..."
cargo fmt --all -- --check

# Run Rust linter
echo "Running clippy..."
cargo clippy --workspace -- -D warnings

# Run Rust tests
echo "Running Rust tests..."
cargo test --workspace

if [ $? -ne 0 ]; then
    echo "Pre-commit checks failed! Fix errors before committing."
    exit 1
fi

echo "Pre-commit checks passed!"
```

---

## Performance Validation

### Benchmarking Script

```python
# scripts/benchmark_rust.py

import numpy as np
import pandas as pd
import time

try:
    import acm_rs
    HAS_RUST = True
except ImportError:
    HAS_RUST = False

def benchmark_rolling_median():
    """Compare Rust vs pandas performance."""
    data = pd.DataFrame(np.random.randn(10000, 50))
    window = 16
    
    # Pandas baseline
    start = time.perf_counter()
    pandas_result = data.rolling(window=window, min_periods=8).median()
    pandas_time = time.perf_counter() - start
    
    # Rust implementation
    if HAS_RUST:
        start = time.perf_counter()
        rust_result = acm_rs.rolling_median_f64(data.values, window=window, min_periods=8)
        rust_time = time.perf_counter() - start
        
        speedup = pandas_time / rust_time
        print(f"Pandas: {pandas_time*1000:.1f}ms")
        print(f"Rust:   {rust_time*1000:.1f}ms")
        print(f"Speedup: {speedup:.1f}x")
    else:
        print("Rust extension not available")

if __name__ == "__main__":
    benchmark_rolling_median()
```

**Expected Output:**
```
Pandas: 850.2ms
Rust:   120.4ms
Speedup: 7.1x
```

---

## Additional Resources

- **PyO3 Documentation:** https://pyo3.rs/
- **Maturin User Guide:** https://www.maturin.rs/
- **Cargo Book:** https://doc.rust-lang.org/cargo/
- **Rust by Example:** https://doc.rust-lang.org/rust-by-example/
- **ACM Rust Migration Plan:** `docs/RUST_MIGRATION_PLAN.md`

---

**Document Version:** 1.0  
**Last Updated:** January 4, 2026  
**Maintainer:** ACM Development Team

# Regime Identification Configuration Guide

**Version**: ACM v11.3.x  
**Last Updated**: 2026-01-20

---

## Overview

The ACM regime identification system provides several configuration options to control how equipment operating regimes are detected, categorized, and tracked. This guide explains each option and provides recommended settings for different scenarios.

---

## Configuration Parameters

### 1. Health-State Features

**Location**: `regimes.health_state_features.enabled`  
**Type**: Boolean  
**Default**: `False`  
**Added**: v11.3.x

**Description**: Controls whether health-state variables (ensemble_z, health_trend, health_quartile) are included in regime clustering.

**Impact**:
- `False` (RECOMMENDED): Regimes based on operating variables only (load, speed, pressure)
  - **Pros**: Regimes remain stable as equipment degrades
  - **Cons**: May miss health-driven operating mode changes
  - **Use When**: Need stable regime labels for long-term trending

- `True`: Adds health state to regime definition
  - **Pros**: Distinguishes pre-fault vs. degraded equipment
  - **Cons**: Regimes drift as health changes (same load/speed gets different regime ID)
  - **Use When**: Fault transitions are more important than regime stability

**Example**:
```ini
[regimes.health_state_features]
enabled = False  # RECOMMENDED: Keep regimes stable
```

**Warning**: Enabling health-state features causes regime labels to change as equipment health degrades. This breaks the assumption that regimes represent stable operating states.

---

### 2. Confidence Threshold

**Location**: `regimes.confidence.min_threshold`  
**Type**: Float (0.0 to 1.0)  
**Default**: `0.0` (disabled)  
**Added**: v11.3.x

**Description**: Minimum confidence score required for regime assignment. Assignments below this threshold are marked as UNKNOWN (-1).

**Location**: `regimes.confidence.enforce_threshold`  
**Type**: Boolean  
**Default**: `False`  
**Added**: v11.3.x

**Description**: Whether to enforce the minimum confidence threshold.

**Impact**:
- `enforce_threshold=False`: All assignments kept, even low confidence
  - **Pros**: Every point gets a regime label
  - **Cons**: Hides model uncertainty

- `enforce_threshold=True`: Low-confidence assignments marked UNKNOWN
  - **Pros**: Reveals model uncertainty
  - **Cons**: Requires UNKNOWN regime handling in downstream logic

**Recommended Values**:
- `min_threshold = 0.3`: Conservative (≈30% of assignments may be UNKNOWN)
- `min_threshold = 0.5`: Moderate (≈10-20% UNKNOWN)
- `min_threshold = 0.7`: Aggressive (≈5-10% UNKNOWN)

**Example**:
```ini
[regimes.confidence]
min_threshold = 0.3
enforce_threshold = True
```

**Use Cases**:
- **Production monitoring**: `enforce_threshold=True` to flag uncertain periods
- **Batch analysis**: `enforce_threshold=False` to always assign regime
- **Model validation**: `enforce_threshold=True, min_threshold=0.5` to evaluate coverage

---

### 3. Regime Alignment

**Location**: `regimes.alignment.fail_on_mismatch`  
**Type**: Boolean  
**Default**: `True`  
**Added**: v11.3.x

**Description**: Controls behavior when regime model feature dimensions change between batches.

**Impact**:
- `True` (RECOMMENDED): Raises ValueError on dimension mismatch
  - **Pros**: Prevents silent regime ID permutations
  - **Cons**: Requires manual intervention on feature basis changes
  - **Use When**: Production environment where regime ID stability is critical

- `False`: Logs warning and skips alignment (legacy behavior)
  - **Pros**: Allows system to continue
  - **Cons**: Regime IDs may permute (Regime A in batch 1 becomes Regime C in batch 2)
  - **Use When**: Development/testing where ID permutation is acceptable

**Common Causes of Dimension Mismatch**:
- Number of PCA components changed
- Raw sensor tags added/removed from config
- Feature engineering logic modified

**Example**:
```ini
[regimes.alignment]
fail_on_mismatch = True  # RECOMMENDED: Fail fast
```

**Error Message**:
```
ValueError: Cannot align regimes: feature dimension mismatch (new=8, prev=6).
Feature basis has changed - regime model must be retrained from scratch.
```

**Resolution**: Retrain regime model when feature basis changes intentionally. If unintentional, investigate config changes.

---

### 4. Feature Basis

**Location**: `regimes.feature_basis.use_raw_sensors`  
**Type**: Boolean  
**Default**: `True`

**Description**: Whether to use raw sensor values for regime clustering (recommended) or PCA features only.

**Location**: `regimes.feature_basis.strict_operating_only`  
**Type**: Boolean  
**Default**: `True`

**Description**: Whether to exclude unknown sensor tags (not classified as operating or condition).

**Example**:
```ini
[regimes.feature_basis]
use_raw_sensors = True
strict_operating_only = True
n_pca_components = 3
raw_tags = ["load", "speed", "inlet_pressure"]
```

---

### 5. HDBSCAN Parameters

**Location**: `regimes.hdbscan.*`  
**Type**: Various

**Key Parameters**:
- `min_cluster_size_absolute`: Absolute minimum samples for cluster (default: 30)
- `min_cluster_size_max`: Cap on minimum cluster size (default: 100)
- `min_samples`: Neighborhood size for core points (default: max(3, min_cluster_size//10))
- `max_fit_samples`: Maximum samples for HDBSCAN fit (default: 8000)

**Example**:
```ini
[regimes.hdbscan]
min_cluster_size_absolute = 30  # Allows small transient regimes
min_samples = 5                 # More sensitive to small clusters
max_fit_samples = 8000          # Performance limit
```

**Impact of min_cluster_size**:
- **Too high** (>100): Loses rare regimes (startup, shutdown)
- **Too low** (<20): Creates fragmented regimes (noise sensitivity)
- **Recommended**: 30-50 for typical industrial data

---

## Recommended Configurations

### Production Monitoring (Stable Regimes)

**Goal**: Stable regime labels for long-term trending and fault context.

```ini
[regimes.health_state_features]
enabled = False  # CRITICAL: Keep regimes stable

[regimes.confidence]
min_threshold = 0.3
enforce_threshold = True  # Flag uncertain periods

[regimes.alignment]
fail_on_mismatch = True  # Prevent silent ID changes

[regimes.feature_basis]
use_raw_sensors = True
strict_operating_only = True

[regimes.hdbscan]
min_cluster_size_absolute = 30
min_samples = 5
```

---

### Fault Analysis (Health-Aware Regimes)

**Goal**: Detect health-driven operating mode changes.

```ini
[regimes.health_state_features]
enabled = True  # Track health state as part of regime

[regimes.confidence]
min_threshold = 0.5
enforce_threshold = True

[regimes.alignment]
fail_on_mismatch = True

[regimes.feature_basis]
use_raw_sensors = True
strict_operating_only = True

[regimes.hdbscan]
min_cluster_size_absolute = 30
min_samples = 5
```

**Warning**: This configuration will cause regime drift. Same load/speed at different health levels gets different regime IDs.

---

### Development/Testing

**Goal**: Maximum flexibility for experimentation.

```ini
[regimes.health_state_features]
enabled = False  # Start with stable baseline

[regimes.confidence]
min_threshold = 0.0
enforce_threshold = False  # See all assignments

[regimes.alignment]
fail_on_mismatch = False  # Allow basis changes

[regimes.feature_basis]
use_raw_sensors = True
strict_operating_only = False  # Include unknown tags

[regimes.hdbscan]
min_cluster_size_absolute = 20
min_samples = 3
```

---

## Migration Guide

### From v11.2.x to v11.3.x

**Breaking Changes**: None (all new configs have backward-compatible defaults)

**Recommended Actions**:

1. **Disable health-state features** (if you upgraded from v11.2.x):
   ```ini
   [regimes.health_state_features]
   enabled = False
   ```
   v11.3.0 added health variables by default. Disable to restore v11.2.x behavior.

2. **Enable confidence threshold** (optional):
   ```ini
   [regimes.confidence]
   min_threshold = 0.3
   enforce_threshold = True
   ```
   Adds uncertainty tracking without changing regime labels.

3. **Keep alignment fail-fast** (default):
   ```ini
   [regimes.alignment]
   fail_on_mismatch = True
   ```
   No action needed - default is safe.

---

## Troubleshooting

### Issue: Regime labels changing between batches

**Symptoms**: Same operating conditions get different regime IDs across runs.

**Diagnosis**:
1. Check if `health_state_features.enabled = True` → Disable it
2. Check if feature basis changed (dimension mismatch errors)
3. Run regime diagnostics:
   ```python
   from core.regime_diagnostics import RegimeDiagnostics
   report = diagnostics.generate_report()
   print(f"Fragmentation score: {report['stability_metrics']['fragmentation_score']}")
   ```

**Solution**: Disable health-state features and retrain model.

---

### Issue: Too many UNKNOWN regime assignments

**Symptoms**: 30-50% of data marked as UNKNOWN (-1).

**Diagnosis**:
1. Check `min_confidence_threshold` value → Lower it
2. Check if operating modes are outside training coverage
3. Run diagnostics to see novelty ratio

**Solution**:
- Lower `min_threshold` to 0.2-0.3
- OR disable threshold enforcement: `enforce_threshold = False`
- OR retrain model with more representative data

---

### Issue: Rare regimes not detected

**Symptoms**: Startup/shutdown events labeled as dominant regime or noise.

**Diagnosis**:
1. Check `min_cluster_size_absolute` → Lower it to 20-30
2. Check if time-stratified subsampling is enabled (v11.3.1+)

**Solution**:
```ini
[regimes.hdbscan]
min_cluster_size_absolute = 20
min_samples = 3
```

---

## Diagnostic Tools

### Regime Quality Monitoring

```python
from core.regime_diagnostics import RegimeDiagnostics

diagnostics = RegimeDiagnostics(
    regime_model=model,
    regime_labels=labels,
    basis_df=basis_df,
    regime_confidence=confidence,
    regime_is_novel=is_novel
)

# Generate report
report = diagnostics.generate_report()
print(f"Quality Score: {report['quality_score']:.1f}/100")
print(f"Issues: {report['quality_issues']}")

# Create plots
diagnostics.plot_stability_analysis(output_path="regime_diagnostics.png")
```

**Quality Score Interpretation**:
- **90-100**: Excellent (stable, high confidence, low fragmentation)
- **70-89**: Good (minor issues, acceptable for production)
- **50-69**: Fair (significant issues, needs tuning)
- **0-49**: Poor (unstable, requires retraining or config changes)

---

## References

- **Analysis Document**: `docs/REGIME_IDENTIFICATION_ANALYSIS.md`
- **Diagnostic Tool**: `core/regime_diagnostics.py`
- **Source Code**: `core/regimes.py`
- **System Overview**: `docs/ACM_SYSTEM_OVERVIEW.md`

---

**Last Updated**: 2026-01-20

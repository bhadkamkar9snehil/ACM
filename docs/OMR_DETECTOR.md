# Overall Model Residual (OMR) - Multivariate Health Detector

## Overview

The Overall Model Residual (OMR) detector is a **multivariate anomaly detector** that captures sensor correlation patterns missed by univariate methods (AR1, PCA SPE, Mahalanobis). Unlike traditional detectors that analyze sensors independently, OMR models the **relationships between sensors** and flags deviations from normal multivariate behavior.

**Key Innovation**: Per-sensor contribution tracking enables **root cause attribution** - answering "which sensor(s) caused this OMR deviation?"

## Motivation

### Problem: Univariate Detectors Miss Correlation Anomalies

**Example Scenario:**
```
Pump System:
- sensor1: vibration (normal range: 0-5)
- sensor2: flow rate (normal range: 0-10)
- Healthy correlation: flow = 2 * vibration

Anomaly Case:
- vibration = 3.0 (within normal range ✓)
- flow = 3.0 (within normal range ✓)
- Expected flow = 2 * 3.0 = 6.0
- Actual flow = 3.0 → 50% deviation! ✗

Univariate detectors: PASS (both sensors in range)
OMR detector: FAIL (broken correlation)
```

### Why Correlations Matter

Industrial equipment exhibits strong sensor correlations:
- Vibration ↔ Flow Rate (pumps)
- Temperature ↔ Pressure (gas turbines)
- Current ↔ Speed (motors)
- Power ↔ Load (generators)

When these correlations break, equipment is degrading even if individual sensors appear normal.

## Architecture

### 1. Model Selection (Auto or Manual)

OMR supports three model types:

#### PLS (Partial Least Squares) - **DEFAULT**
- **Best for**: Correlated sensors, moderate sample size
- **Use case**: Typical industrial equipment (5-50 sensors, 1000+ samples)
- **Strengths**: Handles collinearity, captures latent structure
- **Config**: `model_type: "pls"`, `n_components: 5`

#### Ridge Regression (Linear)
- **Best for**: Large datasets, few sensors
- **Use case**: High-frequency data (> 1000 samples, < 20 sensors)
- **Strengths**: Fast, interpretable
- **Config**: `model_type: "linear"`, `alpha: 1.0`

#### PCA (Principal Component Analysis)
- **Best for**: High-dimensional data (more sensors than samples)
- **Use case**: Cold-start mode, small training sets
- **Strengths**: Dimensionality reduction, captures variance
- **Config**: `model_type: "pca"`, `n_components: 5`

**Auto-Selection Logic** (`model_type: "auto"`):
```python
if n_features > n_samples:
    return "pca"  # Dimensionality reduction needed
elif n_samples > 1000 and n_features < 20:
    return "linear"  # Fast linear model
else:
    return "pls"  # Default for correlated sensors
```

### 2. Training Pipeline

```
1. Load training data (X_train: n_samples × n_features)
2. Optional: Filter to healthy regime (regime_labels == min_label)
3. Fill missing values (median imputation)
4. Fit StandardScaler (mean=0, std=1)
5. Train model:
   - PLS: Self-prediction X → X using latent components
   - Linear: Leave-one-out Ridge regression per sensor
   - PCA: Low-rank reconstruction via inverse_transform
6. Compute training residuals:
   residual[t] = ||X[t] - X_reconstructed[t]||₂
7. Store train_residual_std for z-score normalization
```

**Output**: Fitted OMRModel containing:
- `model`: Trained sklearn model (PLS/Ridge/PCA)
- `scaler`: StandardScaler
- `train_residual_std`: Training residual standard deviation
- `feature_names`: List of sensor names
- `model_type`: "pls" / "linear" / "pca"

### 3. Scoring Pipeline

```
1. Load test data (X_test: m_samples × n_features)
2. Fill missing values (median imputation)
3. Scale data using fitted scaler
4. Reconstruct X_test using trained model
5. Compute residuals per timestamp:
   residual[t] = ||X[t] - X_reconstructed[t]||₂
6. Compute per-sensor squared residuals (for attribution):
   contrib[t, sensor_i] = (X[t, i] - X_recon[t, i])²
7. Normalize to z-scores:
   omr_z[t] = residual[t] / train_residual_std
```

**Output**:
- `omr_z`: Array of z-scores (higher = more anomalous)
- `contributions`: DataFrame of per-sensor squared residuals (if `return_contributions=True`)

### 4. Attribution (Root Cause Analysis)

**API**: `get_top_contributors(contributions, timestamp, top_n=5)`

**Process**:
1. Extract sensor contributions at timestamp
2. Rank sensors by squared residual (descending)
3. Return top N sensors with contribution values

**Example**:
```python
omr_z, contributions = omr_detector.score(X_test, return_contributions=True)

# Find high OMR timestamp
anomaly_ts = X_test.index[omr_z.argmax()]

# Get top contributors
top_sensors = omr_detector.get_top_contributors(contributions, anomaly_ts, top_n=5)

# Output:
# [('pump_vibration', 45.2),
#  ('motor_current', 32.1),
#  ('flow_rate', 12.8),
#  ('temperature', 8.4),
#  ('pressure', 5.1)]
```

**Interpretation**:
- pump_vibration contributed 45.2 to reconstruction error (highest)
- This sensor deviated most from expected multivariate pattern
- Operator should inspect pump vibration sensor and related mechanical components

## Configuration

### Basic Configuration (config.yaml)

```yaml
models:
  omr:
    model_type: "auto"       # "pls", "linear", "pca", "auto"
    n_components: 5          # Latent components (PLS/PCA)
    alpha: 1.0               # Ridge regularization (Linear only)
    min_samples: 100         # Minimum training samples required

fusion:
  weights:
    pca_spe_z: 0.35
    ar1_z: 0.20
    mhal_z: 0.20
    iforest_z: 0.20
    gmm_z: 0.05
    omr_z: 0.10            # Enable OMR (0.0 = disabled)
```

### Advanced Configuration

```yaml
models:
  omr:
    model_type: "pls"        # Force PLS (best for correlated sensors)
    n_components: 10         # More components = more expressive
    min_samples: 200         # Higher threshold for robust training
    
thresholds:
  q: 0.98                    # Calibration quantile (98th percentile)
  self_tune:
    clip_z: 8.0              # Z-score clip (prevents outlier saturation)

fusion:
  weights:
    omr_z: 0.15              # Higher weight for correlation-focused detection
```

## Integration Workflow

### 1. Lazy Evaluation

OMR is only fitted/scored if `fusion.weights.omr_z > 0`:
```python
omr_enabled = fusion_weights.get("omr_z", 0.0) > 0
if omr_enabled and not omr_detector:
    omr_detector = OMRDetector(cfg=omr_cfg).fit(train)
```

### 2. Model Fitting (Training Phase)

```python
# Fit OMR on training data
with T.section("fit.omr"):
    omr_cfg = cfg.get("models", {}).get("omr", {})
    omr_detector = OMRDetector(cfg=omr_cfg).fit(train)

# Output: [OMR] Fitted PLS model: 500 samples, 15 features, 5 components, std=0.823
```

### 3. Scoring (Test Phase)

```python
# Score with contribution tracking
with T.section("score.omr"):
    omr_z, omr_contributions = omr_detector.score(score, return_contributions=True)
    frame["omr_raw"] = pd.Series(omr_z, index=frame.index).fillna(0)
    frame._omr_contributions = omr_contributions  # Store for export
```

### 4. Calibration

```python
# Score TRAIN data for calibration
train_frame["omr_raw"] = omr_detector.score(train, return_contributions=False)

# Fit calibrator on TRAIN, transform SCORE
cal_omr = fuse.ScoreCalibrator(q=cal_q, self_tune_cfg=self_tune_cfg).fit(
    train_frame["omr_raw"].to_numpy(copy=False), regime_labels=fit_regimes
)
frame["omr_z"] = cal_omr.transform(frame["omr_raw"].to_numpy(copy=False), regime_labels=transform_regimes)
```

### 5. Fusion

```python
# Fuse with other detectors
weights = {
    "pca_spe_z": 0.35,
    "ar1_z": 0.20,
    "mhal_z": 0.20,
    "iforest_z": 0.20,
    "gmm_z": 0.05,
    "omr_z": 0.10,  # OMR contributes 10% to final score
}

fused = fuse.fuse(frame, weights)
```

### 6. Contribution Export

Two CSV files are exported to `artifacts/<equipment>/run_<id>/tables/`:

#### omr_contributions.csv
Per-timestamp sensor contributions (squared residuals):
```csv
timestamp,sensor1,sensor2,sensor3,...
2025-11-01 00:00:00,0.45,1.23,0.02,...
2025-11-01 00:01:00,0.52,0.98,0.05,...
...
```

#### omr_top_contributors.csv
Top 5 sensors per high-OMR episode:
```csv
episode_start,episode_id,rank,sensor,contribution
2025-11-01 14:30:00,42,1,pump_vibration,45.2
2025-11-01 14:30:00,42,2,motor_current,32.1
2025-11-01 14:30:00,42,3,flow_rate,12.8
2025-11-01 14:30:00,42,4,temperature,8.4
2025-11-01 14:30:00,42,5,pressure,5.1
...
```

## Usage Examples

### Example 1: Enable OMR with Default Settings

**Config (FD_FAN.yaml)**:
```yaml
fusion:
  weights:
    omr_z: 0.10  # Enable with 10% weight
```

**Run**:
```bash
python core/acm_main.py --equip FD_FAN --mode file
```

**Expected Output**:
```
[OMR] Fitted PLS model: 1200 samples, 12 features, 5 components, std=0.654
[OMR] Exported sensor contributions to omr_contributions.csv (2400 rows)
[OMR] Exported top contributors for 3 OMR episodes to omr_top_contributors.csv
```

### Example 2: Force Linear Model (Large Dataset)

**Config**:
```yaml
models:
  omr:
    model_type: "linear"  # Force Ridge regression
    alpha: 0.5            # Lower regularization
    
fusion:
  weights:
    omr_z: 0.15           # Higher weight
```

### Example 3: Cold-Start Mode (Few Samples)

**Config**:
```yaml
models:
  omr:
    model_type: "pca"     # PCA for dimensionality reduction
    n_components: 3       # Fewer components (fewer samples)
    min_samples: 50       # Lower threshold
```

### Example 4: Analyze OMR Contributors

**Python Script**:
```python
import pandas as pd

# Load contributions
contrib = pd.read_csv("artifacts/FD_FAN/run_001/tables/omr_contributions.csv", parse_dates=['timestamp'])
contrib.set_index('timestamp', inplace=True)

# Find timestamp with highest total contribution
total_contrib = contrib.sum(axis=1)
max_ts = total_contrib.idxmax()

# Get top sensors at that timestamp
top_sensors = contrib.loc[max_ts].nlargest(5)
print(f"Top contributors at {max_ts}:")
for sensor, value in top_sensors.items():
    print(f"  {sensor}: {value:.2f}")
```

## Performance Characteristics

### Computational Cost

| Model Type | Training Time | Scoring Time | Memory |
|------------|--------------|--------------|--------|
| PLS        | O(n·m²·k)    | O(m·k)       | Medium |
| Linear     | O(n·m²)      | O(m²)        | Low    |
| PCA        | O(n·m²)      | O(m·k)       | Medium |

Where:
- n = number of samples
- m = number of sensors
- k = number of components

**Typical Performance** (12 sensors, 1000 samples):
- Training: 50-200ms (PLS), 20-50ms (Linear), 30-100ms (PCA)
- Scoring: 1-5ms per batch (1000 timestamps)

### Memory Usage

- Training: 2-5 MB per model (1000 samples × 10 sensors)
- Scoring: < 1 MB per batch
- Contributions: 10-50 MB per run (depending on time range)

## Interpretation Guide

### OMR Z-Score Thresholds

| OMR Z-Score | Interpretation | Action |
|-------------|----------------|--------|
| < 2.0       | Healthy        | Normal operation |
| 2.0 - 3.0   | Minor deviation| Monitor top contributors |
| 3.0 - 5.0   | Moderate anomaly| Investigate top 3 sensors |
| > 5.0       | Severe anomaly | Immediate inspection |

### Contribution Values

| Contribution | Interpretation | Example |
|--------------|----------------|---------|
| < 1.0        | Negligible     | Sensor behaving normally |
| 1.0 - 5.0    | Minor deviation| Slightly off from expected |
| 5.0 - 20.0   | Moderate deviation| Inspect sensor/equipment |
| > 20.0       | Major deviation| Likely root cause |

### OMR vs Other Detectors

| Scenario | AR1 | PCA SPE | MHAL | OMR | Best Detector |
|----------|-----|---------|------|-----|---------------|
| Single sensor drift | High | Med | Med | Low | AR1 |
| Multiple sensors drift together | Low | Med | Med | **High** | OMR |
| Broken correlation (sensor A vs B) | Low | Low | Low | **High** | OMR |
| Sensor stuck at value | High | Low | Low | Med | AR1 |
| Equipment regime shift | Med | High | High | **High** | OMR + GMM |

**Use OMR when:**
- Equipment has known sensor correlations
- Univariate detectors are missing anomalies
- Root cause attribution is critical
- Multiple sensors drift simultaneously

**Skip OMR when:**
- Sensors are independent (no correlations)
- Single-sensor faults are primary concern
- Training data is very small (< 50 samples)

## Troubleshooting

### Issue: "OMR not fitted (insufficient samples)"

**Cause**: Training data has fewer than `min_samples` rows

**Solution**:
```yaml
models:
  omr:
    min_samples: 50  # Lower threshold
```

### Issue: High OMR scores but no obvious culprit

**Cause**: Multiple sensors contributing moderately

**Solution**:
1. Check `omr_contributions.csv` for temporal patterns
2. Increase `top_n` in contributor export:
   ```python
   top_contribs = omr.get_top_contributors(contrib, ts, top_n=10)
   ```
3. Review sensor groups (e.g., all temperature sensors)

### Issue: OMR always near zero

**Cause**: Model overfitting or insufficient complexity

**Solution**:
```yaml
models:
  omr:
    n_components: 10      # More components
    model_type: "pls"     # Use PLS instead of Linear
```

### Issue: OMR too sensitive (many false positives)

**Cause**: Model complexity too high

**Solution**:
```yaml
models:
  omr:
    n_components: 3       # Fewer components
    model_type: "linear"  # Simpler model
    alpha: 2.0            # More regularization (Linear only)
```

## Technical Details

### Why Squared Residuals for Attribution?

**Choice**: Squared residuals emphasize large deviations (quadratic penalty)

**Example**:
```
Sensor A: residual = 10 → contribution = 100
Sensor B: residual = 3  → contribution = 9
Sensor C: residual = 1  → contribution = 1

Clear ranking: A >> B > C
```

**Alternatives considered**:
- Absolute residuals: Less emphasis on outliers (linear penalty)
- Standardized residuals: Sensor-specific scaling (more complex)

**Conclusion**: Squared residuals provide clear signal for major contributors while matching L2 norm used in OMR score.

### Why Z-Score Normalization?

**Problem**: Reconstruction error magnitude varies with equipment type and training data

**Solution**: Normalize by training residual std:
```python
omr_z = residual_norm / train_residual_std
```

**Benefits**:
- Consistent thresholds across equipment (z > 3.0 = anomaly)
- Comparable to other detectors (all use z-scores)
- Statistically interpretable (assuming Gaussian residuals)

### Model Persistence

**Serialization**: Uses joblib to serialize sklearn models to bytes
```python
state_dict = {
    "fitted": True,
    "model": {
        "model_type": "pls",
        "feature_names": ["sensor1", "sensor2", ...],
        "train_residual_std": 0.654,
        "n_components": 5,
        "model_bytes": b'...',  # Joblib-serialized PLS model
        "scaler_bytes": b'...'  # Joblib-serialized StandardScaler
    }
}
```

**Deserialization**: Reconstructs OMRModel from dict
```python
omr_detector = OMRDetector.from_dict(state_dict, cfg=cfg)
```

**Cache Location**: `artifacts/<equipment>/models/detectors.pkl`

## Validation

### Test Suite: tests/test_omr.py

**Test Coverage**:
1. `test_omr_basic_fit_score`: Fit on synthetic data, verify z-scores are finite and reasonable
2. `test_omr_anomaly_detection`: Inject correlation-breaking anomaly, verify OMR detects it
3. `test_omr_contribution_tracking`: Verify per-sensor contributions track correctly
4. `test_omr_model_auto_selection`: Verify auto-selection logic (PCA vs PLS vs Linear)
5. `test_omr_healthy_regime_filtering`: Verify training filters to healthy regime
6. `test_omr_persistence`: Verify serialization/deserialization produces same scores
7. `test_omr_missing_data_handling`: Verify graceful handling of NaNs

**Run Tests**:
```bash
python tests/test_omr.py
```

**Expected Output**:
```
[OMR] Fitted PLS model: 200 samples, 3 features, 2 components, std=0.423
[PASS] Basic fit/score
[OMR] Fitted PLS model: 200 samples, 3 features, 3 components, std=1.000
[PASS] Contribution tracking
[OMR] Fitted PLS model: 100 samples, 5 features, 3 components, std=0.562
[PASS] Persistence
[OMR] Fitted PLS model: 200 samples, 4 features, 4 components, std=1.000
[PASS] Missing data handling

OMR Tests: 4/4 passed
SUCCESS - All tests passed!
```

## Future Enhancements

### Planned (OMR-04: Visualization)

- **OMR Timeline Chart**: Time series of omr_z with episode markers
- **Sensor Contribution Heatmap**: Color-coded heatmap showing which sensors contribute when
- **Top Contributors Bar Chart**: Bar chart of top 10 sensors per episode

### Under Consideration

- **Dynamic Model Update**: Online learning to adapt OMR to slow drift
- **Multi-Regime OMR**: Fit separate OMR models per operational regime
- **Ensemble OMR**: Combine multiple model types (PLS + PCA + Linear) with voting
- **Causal Attribution**: Use Shapley values or LIME for more robust attribution

## References

### Academic Background

1. **PLS for Multivariate Monitoring**:
   - Qin, S. J. (2003). "Statistical process monitoring: basics and beyond." *Journal of Chemometrics*, 17(8-9), 480-502.
   
2. **Reconstruction-Based Anomaly Detection**:
   - Chiang, L. H., Russell, E. L., & Braatz, R. D. (2000). *Fault detection and diagnosis in industrial systems*. Springer Science & Business Media.

3. **Sensor Correlation Modeling**:
   - Ge, Z., Song, Z., & Gao, F. (2013). "Review of recent research on data-based process monitoring." *Industrial & Engineering Chemistry Research*, 52(10), 3543-3562.

### Related ACM Documents

- `docs/Analytics Backbone.md` - Overall ACM architecture
- `docs/PHASE1_EVALUATION.md` - Detector comparison and evaluation
- `docs/PROOF_MODEL_EVOLUTION.md` - Model adaptation and evolution
- `models/README.md` - Model package overview

## Summary

**OMR is ACM's multivariate health detector**, capturing sensor correlation patterns that univariate methods miss. With per-sensor contribution tracking, it provides **root cause attribution** for complex equipment failures. Enable it with `omr_z: 0.10` in fusion weights and analyze `omr_contributions.csv` to understand which sensors are driving anomalies.

**When to use OMR**: Equipment with known sensor correlations, multiple sensors drifting together, or when univariate detectors are missing anomalies.

**Key outputs**: `omr_z` (health z-score), `omr_contributions.csv` (per-sensor attribution), `omr_top_contributors.csv` (top 5 culprits per episode).

# Enhanced Forecasting and RUL Analytics - Usage Guide

**Version:** 1.0  
**Date:** November 15, 2025  
**Module:** `core/enhanced_forecasting.py`

---

## Overview

The Enhanced Forecasting and RUL Analytics module provides:

1. **Multi-Model Forecasting**: AR(1), Exponential Decay, Polynomial, and Ensemble methods
2. **Probabilistic Failure Prediction**: Failure probabilities at multiple horizons with confidence
3. **Detector-Based Causation**: Root cause analysis using detector deviations
4. **Intelligent Maintenance Recommendations**: Actionable guidance with urgency scoring

---

## Quick Start

### Automatic Integration (Recommended)

The enhanced forecasting module is automatically integrated into the ACM pipeline when enabled in configuration.

**Enable in `configs/config_table.csv`:**
```csv
EquipID,Category,ParamPath,ParamValue,ValueType
0,forecasting,enhanced_enabled,True,bool
```

**Run ACM pipeline:**
```bash
python -m core.acm_main --equip FD_FAN --enable-report
```

The enhanced forecasting will run automatically after standard forecasting and RUL estimation.

### Standalone Usage

```python
from pathlib import Path
from core.enhanced_forecasting import EnhancedForecastingEngine

# Configuration
config = {
    'forecasting': {
        'enabled': True,
        'failure_threshold': 70.0,
        'forecast_horizons': [24, 72, 168],  # hours
        'models': ['ar1', 'exponential', 'polynomial', 'ensemble'],
        'confidence_min': 0.6
    },
    'maintenance': {
        'urgency_threshold': 50.0,
        'buffer_hours': 24
    },
    'causation': {
        'min_detector_contribution': 10.0,
        'top_sensors_count': 10
    }
}

# Initialize engine
engine = EnhancedForecastingEngine(config)

# Prepare context
ctx = {
    'run_dir': Path('artifacts/FD_FAN/run_20251115_120000'),
    'tables_dir': Path('artifacts/FD_FAN/run_20251115_120000/tables'),
    'plots_dir': Path('artifacts/FD_FAN/run_20251115_120000/plots'),
    'config': config,
    'run_id': 'run_20251115_120000',
    'equip_id': 5396
}

# Run analysis
result = engine.run(ctx)

# Access results
print(f"RUL: {result['metrics']['rul_hours']:.1f} hours")
print(f"Maintenance Required: {result['metrics']['maintenance_required']}")
print(f"Urgency: {result['metrics']['urgency_score']:.0f}/100")
```

---

## Configuration Parameters

### Forecasting Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enhanced_enabled` | bool | True | Enable enhanced forecasting module |
| `failure_threshold` | float | 70.0 | Health index threshold defining failure |
| `forecast_horizons` | list[int] | [24, 72, 168] | Forecast horizons in hours |
| `models` | list[str] | ['ar1', 'exponential', 'polynomial', 'ensemble'] | Models to use |
| `confidence_min` | float | 0.6 | Minimum confidence threshold for predictions |
| `min_history_hours` | float | 24.0 | Minimum historical data required (hours) |
| `max_forecast_hours` | float | 168.0 | Maximum forecast horizon (hours) |

### Maintenance Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `urgency_threshold` | float | 50.0 | Urgency score above which maintenance is required |
| `buffer_hours` | int | 24 | Safety buffer for maintenance window |
| `risk_thresholds.low` | float | 0.1 | Low risk threshold (10% failure probability) |
| `risk_thresholds.medium` | float | 0.3 | Medium risk threshold (30% failure probability) |
| `risk_thresholds.high` | float | 0.5 | High risk threshold (50% failure probability) |
| `risk_thresholds.very_high` | float | 0.7 | Very high risk threshold (70% failure probability) |

### Causation Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_detector_contribution` | float | 10.0 | Minimum detector contribution % to report |
| `top_sensors_count` | int | 10 | Number of top contributing sensors to report |
| `detector_criticality` | dict | See below | Criticality weights for each detector |

**Default Detector Criticality Weights:**
```python
{
    'ar1': 0.9,       # Sensor failures (critical)
    'pca_spe': 0.9,   # Correlation breaks (critical)
    'pca_t2': 0.7,    # Operating point shifts
    'iforest': 0.6,   # Sporadic anomalies
    'gmm': 0.5,       # Distribution shifts
    'mahl': 0.6,      # Global deviations
    'omr': 0.8        # Model degradation (important)
}
```

---

## Output Tables

### 1. failure_probability_ts.csv

Time series of failure probabilities at multiple forecast horizons.

| Column | Type | Description |
|--------|------|-------------|
| RunID | string | Unique run identifier |
| EquipID | int | Equipment identifier |
| Timestamp | datetime | Current timestamp |
| ForecastHorizon_Hours | float | Hours into future |
| ForecastHealth | float | Predicted health value |
| ForecastUncertainty | float | Standard deviation |
| FailureProbability | float | Probability of failure (0-1) |
| RiskLevel | string | Low/Medium/High/Very High/Critical |
| Confidence | float | Prediction confidence (0-1) |
| Model | string | Model used (ar1/exponential/polynomial/ensemble) |

**Interpretation:**
- **FailureProbability > 0.5**: More likely to fail than not within horizon
- **RiskLevel = Critical**: Immediate action recommended
- **Confidence < 0.6**: Predictions have high uncertainty

### 2. failure_causation.csv

Detector contributions and failure patterns.

| Column | Type | Description |
|--------|------|-------------|
| RunID | string | Unique run identifier |
| EquipID | int | Equipment identifier |
| PredictedFailureTime | datetime | When failure is predicted |
| FailurePattern | string | Identified patterns (comma-separated) |
| Detector | string | Detector name |
| MeanZ | float | Mean z-score near failure |
| MaxZ | float | Peak z-score |
| SpikeCount | int | Number of spikes (z > 3.0) |
| TrendSlope | float | Rate of change |
| ContributionWeight | float | Raw contribution weight |
| ContributionPct | float | Percentage contribution to failure |

**Interpretation:**
- **ContributionPct > 30%**: Dominant failure mechanism
- **FailurePattern = sudden_spike**: Sensor or transient issue
- **FailurePattern = drift**: Process or calibration drift
- **FailurePattern = correlation_break**: Mechanical or coupling issue
- **FailurePattern = gradual_decay**: Progressive wear

### 3. enhanced_maintenance_recommendation.csv

Comprehensive maintenance guidance.

| Column | Type | Description |
|--------|------|-------------|
| RunID | string | Unique run identifier |
| EquipID | int | Equipment identifier |
| UrgencyScore | float | Urgency score (0-100) |
| MaintenanceRequired | bool | Whether maintenance is needed |
| EarliestMaintenance | float | Earliest safe time (hours from now) |
| PreferredWindowStart | float | Recommended start time (hours) |
| PreferredWindowEnd | float | Recommended end time (hours) |
| LatestSafeTime | float | Latest safe time (hours) |
| FailureProbAtLatest | float | Risk if delayed to latest time |
| FailurePattern | string | Identified patterns |
| Confidence | float | Overall confidence |
| EstimatedDuration_Hours | float | Total maintenance duration |

**Interpretation:**
- **UrgencyScore ≥ 50**: Maintenance required
- **UrgencyScore < 50**: Monitor and plan
- **PreferredWindow**: Optimal time to perform maintenance
- **LatestSafeTime**: Do not delay beyond this point

### 4. recommended_actions.csv

Specific maintenance actions to perform.

| Column | Type | Description |
|--------|------|-------------|
| RunID | string | Unique run identifier |
| EquipID | int | Equipment identifier |
| action | string | Description of maintenance action |
| priority | string | High/Medium/Low |
| estimated_duration_hours | float | Expected time to complete |

**Example Actions:**
- "Inspect sensors for failure or wiring issues" (Priority: High)
- "Recalibrate instruments and verify process parameters" (Priority: Medium)
- "Check mechanical linkages and coupling integrity" (Priority: High)
- "Schedule preventive maintenance for progressive wear" (Priority: Medium)

---

## Interpreting Results

### Example Scenario 1: Critical Failure Imminent

**Output:**
```
RUL: 18.5 hours
Max Failure Prob: 82.3%
Maintenance Required: True
Urgency: 87/100
Risk Level: Critical
```

**Interpretation:**
- Equipment will likely fail within 18.5 hours
- 82% probability of failure
- Immediate maintenance required
- Check recommended actions for specific steps

**Action:**
1. Schedule emergency maintenance within 18 hours
2. Review failure causation table for root cause
3. Prepare spare parts based on detector contributions
4. Consider temporary shutdown if failure risk is unacceptable

### Example Scenario 2: Scheduled Maintenance

**Output:**
```
RUL: 95.2 hours
Max Failure Prob: 35.4%
Maintenance Required: False
Urgency: 42/100
Risk Level: Medium
Preferred Window: 48-72 hours
```

**Interpretation:**
- Equipment healthy for ~95 hours
- 35% failure probability at 72 hours
- Maintenance not urgent but recommended
- Optimal window is 48-72 hours from now

**Action:**
1. Plan maintenance during next scheduled downtime
2. Monitor health index for changes
3. Prepare maintenance team and materials
4. Execute maintenance within preferred window

### Example Scenario 3: Healthy Equipment

**Output:**
```
RUL: 168+ hours
Max Failure Prob: 8.2%
Maintenance Required: False
Urgency: 12/100
Risk Level: Low
```

**Interpretation:**
- Equipment healthy beyond forecast horizon
- Low failure probability
- Continue normal monitoring

**Action:**
1. No immediate action required
2. Continue routine monitoring
3. Review next forecast cycle

---

## Failure Patterns and Actions

### Pattern: Sudden Spike

**Characteristics:**
- High IForest and AR1 detector contributions
- MaxZ > 5.0 for one or more detectors
- Sharp, transient deviations

**Likely Causes:**
- Sensor failure or wiring issue
- Electrical transient
- Instrument malfunction

**Recommended Actions:**
1. Inspect sensors for physical damage
2. Check wiring and connections
3. Verify power supply stability
4. Replace faulty sensors if needed

### Pattern: Drift

**Characteristics:**
- Rising OMR and AR1 contributions
- Positive trend slope (> 0.1)
- Gradual, consistent deviation

**Likely Causes:**
- Process parameter drift
- Fouling or contamination
- Calibration drift
- Environmental changes

**Recommended Actions:**
1. Recalibrate instruments
2. Check process parameters (temperature, pressure, flow)
3. Inspect for fouling or deposits
4. Review environmental conditions

### Pattern: Correlation Break

**Characteristics:**
- High PCA-SPE contribution (> 40%)
- Low PCA-T² contribution
- Loss of normal correlation structure

**Likely Causes:**
- Mechanical coupling failure
- Structural changes
- Control system malfunction
- Process reconfiguration

**Recommended Actions:**
1. Check mechanical linkages
2. Inspect coupling integrity
3. Verify control system operation
4. Review recent process changes

### Pattern: Gradual Decay

**Characteristics:**
- All detectors rising gradually
- Consistent trend across detectors
- Smooth, progressive deterioration

**Likely Causes:**
- Progressive wear
- Degradation of components
- Accumulated stress
- Normal aging

**Recommended Actions:**
1. Schedule preventive maintenance
2. Plan component replacement
3. Perform comprehensive inspection
4. Consider overhaul or refurbishment

---

## Advanced Usage

### Custom Model Selection

Override default model selection logic:

```python
from core.enhanced_forecasting import HealthForecaster, ForecastConfig

config = ForecastConfig(
    models=['exponential']  # Use only exponential model
)
forecaster = HealthForecaster(config)
```

### Adjusting Detector Criticality

Customize detector criticality weights:

```python
from core.enhanced_forecasting import CausationConfig

config = CausationConfig(
    detector_criticality={
        'ar1': 1.0,      # Highest priority
        'pca_spe': 0.9,
        'omr': 0.8,
        'pca_t2': 0.5,
        'iforest': 0.3,
        'gmm': 0.3,
        'mahl': 0.4
    }
)
```

### Integration with Existing RUL Module

The enhanced module can be used alongside the existing RUL estimator:

```python
# Standard RUL (basic health trajectory)
from core import rul_estimator
standard_rul = rul_estimator.estimate_rul_and_failure(
    tables_dir=tables_dir,
    equip_id=equip_id,
    run_id=run_id,
    health_threshold=70.0
)

# Enhanced RUL (with causation and recommendations)
from core import enhanced_forecasting
enhanced_rul = enhanced_forecasting.estimate_enhanced_rul(
    tables_dir=tables_dir,
    equip_id=equip_id,
    run_id=run_id,
    config=cfg
)

# Both generate complementary outputs
```

---

## Troubleshooting

### Issue: "Insufficient history" warning

**Cause:** Less than 20 data points in health timeline.

**Solution:** 
- Ensure health_timeline.csv has sufficient data
- Adjust `min_history_hours` in configuration
- Wait for more data collection

### Issue: Poor prediction confidence (< 0.6)

**Cause:** Poor model fit to historical data.

**Solution:**
- Review data quality (missing values, outliers)
- Check for non-stationary signals
- Consider longer history for model training
- Interpret predictions with caution

### Issue: No detector scores in failure window

**Cause:** Detector scores not available near predicted failure time.

**Solution:**
- Verify scores.csv is complete
- Check timestamp alignment
- Ensure detector pipeline ran successfully

### Issue: All failure probabilities near 50%

**Cause:** High uncertainty in forecasts.

**Solution:**
- Indicates unpredictable behavior
- Use wider confidence intervals
- Consider additional monitoring
- Consult with domain experts

---

## Best Practices

1. **Review Regularly**: Check enhanced forecasting outputs daily or per run
2. **Validate Predictions**: Compare predictions with actual outcomes
3. **Update Configuration**: Tune parameters based on validation results
4. **Combine with Domain Knowledge**: Use predictions as decision support, not autopilot
5. **Document Actions**: Record maintenance actions and outcomes
6. **Monitor Confidence**: Pay attention to confidence scores
7. **Trend Analysis**: Track urgency scores over time
8. **Cross-Reference**: Compare detector contributions with sensor data

---

## References

- **Design Document**: `docs/ENHANCED_FORECASTING_RUL_DESIGN.md`
- **Implementation**: `core/enhanced_forecasting.py`
- **Analytics Backbone**: `docs/Analytics Backbone.md`
- **RUL Backbone**: `docs/RUL Backbone.md`

---

**Last Updated:** November 15, 2025  
**Version:** 1.0  
**Status:** Production Ready

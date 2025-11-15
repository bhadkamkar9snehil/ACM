# Enhanced Forecasting and RUL Analytics - Analytical Design

**Version:** 1.0  
**Date:** November 15, 2025  
**Status:** Design Complete, Ready for Implementation  
**Objective:** Create analytically rigorous, flawless forecasting and RUL system with probabilistic failure prediction, detector-based causation, and actionable maintenance recommendations

---

## 1. Executive Summary

This document defines the analytical backbone for an enhanced forecasting and Remaining Useful Life (RUL) estimation system that:

1. **Provides clear failure probability percentages** with confidence levels
2. **Identifies root causes** through detector deviation analysis
3. **Generates actionable maintenance recommendations** with urgency levels
4. **Operates flawlessly** through robust design and comprehensive validation

The system builds upon existing ACM capabilities while adding sophisticated probabilistic reasoning, multi-detector causation analysis, and intelligent decision support.

---

## 2. Architectural Overview

### 2.1 System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    ACM Pipeline Output                       │
│  • Detector Z-Scores (AR1, PCA, IForest, GMM, Mahl, OMR)   │
│  • Fused Health Score                                        │
│  • Episode Detection                                         │
│  • Sensor Hotspots                                          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│           Enhanced Forecasting Module                        │
│  • Multi-Model Health Trajectory Forecasting                │
│  • Ensemble AR(1) + Exponential Decay + Polynomial          │
│  • Growing Uncertainty Quantification                        │
│  • Model Selection Based on Fit Quality                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│         Probabilistic Failure Prediction                     │
│  • Threshold Crossing Probability                           │
│  • Multi-Horizon Failure Risk (24h, 72h, 168h)             │
│  • Confidence-Weighted Probability                          │
│  • Risk Category Assignment                                 │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│         Detector-Based Causation Analysis                    │
│  • Per-Detector Deviation Tracking                          │
│  • Sensor-Level Attribution via Detector Contributions      │
│  • Regime-Aware Baseline Comparison                         │
│  • Failure Mode Pattern Recognition                         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│      Intelligent Maintenance Recommendation                  │
│  • Risk-Based Urgency Scoring                               │
│  • Optimal Maintenance Window Calculation                   │
│  • Cost-Benefit Analysis Integration                        │
│  • Actionable Guidance Generation                           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

1. **Input**: Historical health scores, detector outputs, sensor data, regime labels
2. **Forecasting**: Multi-model ensemble predicts health trajectory
3. **Probability**: Calculate failure probability at multiple horizons
4. **Causation**: Analyze detector deviations to identify root causes
5. **Recommendation**: Generate maintenance guidance based on risk and causation
6. **Output**: Tables, charts, and actionable alerts

---

## 3. Enhanced Health Forecasting

### 3.1 Multi-Model Ensemble Approach

Instead of relying solely on AR(1), we implement an ensemble of complementary models:

#### Model 1: AR(1) with Drift Compensation
- **Use Case**: Short-term predictions (< 24h), stationary signals
- **Formula**: `H(t+h) = μ + φ^h * (H(t) - μ) + α*h`
  - Where `α` captures linear drift
- **Advantages**: Fast, interpretable, handles autocorrelation
- **Limitations**: Assumes stationarity, linear mean reversion

#### Model 2: Exponential Decay
- **Use Case**: Degradation scenarios, medium-term (24-168h)
- **Formula**: `H(t+h) = H(t) * exp(-λ*h)`
  - Where `λ` is estimated from recent slope
- **Advantages**: Natural for degradation, bounded at zero
- **Limitations**: Cannot capture recovery or stability

#### Model 3: Polynomial Regression (degree 2-3)
- **Use Case**: Non-linear trends, acceleration in degradation
- **Formula**: `H(t+h) = a*h^2 + b*h + c`
- **Advantages**: Captures acceleration, flexible
- **Limitations**: Can extrapolate poorly, overfits small samples

#### Model Selection Logic
```python
def select_forecast_model(history: pd.Series) -> str:
    """
    Intelligent model selection based on:
    - Trend strength (monotonic decline → exponential)
    - Autocorrelation (high ACF1 → AR1)
    - Curvature (acceleration → polynomial)
    - Stationarity (stationary → AR1)
    """
    metrics = compute_signal_metrics(history)
    
    if metrics['trend_strength'] > 0.7 and metrics['monotonic_decline']:
        return 'exponential'
    elif metrics['acf1'] > 0.6 and metrics['stationarity_ratio'] < 0.3:
        return 'ar1'
    elif metrics['curvature'] > 0.5:
        return 'polynomial'
    else:
        # Ensemble: weighted average of all models
        return 'ensemble'
```

### 3.2 Uncertainty Quantification

For each model, compute uncertainty that grows with forecast horizon:

#### AR(1) Uncertainty
```
σ_h = σ_residual * sqrt((1 - φ^(2h)) / (1 - φ^2))
```

#### Exponential Decay Uncertainty
```
σ_h = σ_λ * H(t) * h * exp(-λ*h)
where σ_λ is uncertainty in λ estimate
```

#### Polynomial Uncertainty
```
σ_h = σ_fit * sqrt(1 + h^2/n)
where σ_fit is residual std from training
```

#### Ensemble Uncertainty
```
σ_ensemble = sqrt(Σ w_i * σ_i^2 + Σ w_i * (μ_i - μ_ensemble)^2)
```
This captures both within-model and between-model uncertainty.

### 3.3 Forecast Validation

Before accepting forecasts, validate:
- **Stationarity**: ADF test or rolling mean variance < threshold
- **Fit Quality**: R² > 0.4, RMSE < 20% of signal range
- **Residual Whiteness**: Ljung-Box test p-value > 0.05
- **Physical Bounds**: Health ∈ [0, 100], non-negative RUL

If validation fails, fall back to simple linear extrapolation with high uncertainty flag.

---

## 4. Probabilistic Failure Prediction

### 4.1 Failure Threshold Definition

Define **critical health threshold** (`H_crit`) as:
```python
H_crit = config.get('failure_threshold', 70.0)
# Can be asset-specific or regime-specific
```

### 4.2 Multi-Horizon Failure Probability

For each forecast horizon `h`, compute probability that health crosses threshold:

```python
def compute_failure_probability(forecast_h, sigma_h, H_crit):
    """
    P(Failure at h) = P(H(t+h) <= H_crit)
    
    Using Normal approximation:
    P = Φ((H_crit - forecast_h) / sigma_h)
    where Φ is standard normal CDF
    """
    z_score = (H_crit - forecast_h) / sigma_h
    return norm.cdf(z_score)
```

### 4.3 Cumulative Failure Risk

Compute cumulative probability of failure within horizon:
```python
P(Failure before h) = 1 - Π(1 - P(Failure at i)) for i in [1, h]
```

### 4.4 Risk Categories

Classify failure risk into actionable categories:

| Failure Probability | Risk Level | Maintenance Urgency | Color Code |
|-------------------|-----------|-------------------|-----------|
| < 10% | **Low** | Monitor | 🟢 Green |
| 10-30% | **Medium** | Plan | 🟡 Yellow |
| 30-50% | **High** | Schedule | 🟠 Orange |
| 50-70% | **Very High** | Urgent | 🔴 Red |
| > 70% | **Critical** | Immediate | 🔴 Red (Flashing) |

### 4.5 Confidence Adjustment

Adjust reported probability based on forecast confidence:
```python
reported_probability = raw_probability * confidence_factor
confidence_factor = min(1.0, fit_quality / 0.6)  # Penalize poor fits
```

---

## 5. Detector-Based Causation Analysis

### 5.1 Detector Contribution Framework

Each detector represents a distinct failure mechanism:

| Detector | Physical Interpretation | Failure Mode |
|---------|------------------------|-------------|
| **AR1** | Sensor-level deviation from temporal baseline | Individual sensor anomaly, instrument failure |
| **PCA-SPE** | Multivariate correlation breakdown | Cross-correlation changes, process shift |
| **PCA-T²** | Deviation from normal operating subspace | Operating point shift, regime change |
| **IForest** | Outlier detection in feature space | Sporadic anomalies, transients |
| **GMM** | Density-based anomaly | Statistical distribution shift |
| **Mahalanobis** | Global multivariate distance | Overall system deviation |
| **OMR** | Overall model residual | Model fit degradation, concept drift |

### 5.2 Detector Deviation Scoring

At predicted failure time `t_fail`, compute detector contribution:

```python
def compute_detector_contributions(detector_scores, failure_time):
    """
    Score each detector's contribution to predicted failure
    """
    # Extract detector z-scores near failure time
    window = [failure_time - 6h, failure_time + 6h]
    scores = detector_scores.loc[window]
    
    contributions = {}
    for detector in ['ar1', 'pca_spe', 'pca_t2', 'iforest', 'gmm', 'mahl', 'omr']:
        # Metrics for each detector
        contributions[detector] = {
            'mean_z': scores[f'{detector}_z'].mean(),
            'max_z': scores[f'{detector}_z'].max(),
            'spike_count': (scores[f'{detector}_z'] > 3.0).sum(),
            'trend_slope': fit_linear_slope(scores[f'{detector}_z']),
            'contribution_weight': compute_contribution_weight(scores, detector)
        }
    
    # Normalize contributions to sum to 100%
    total = sum(c['contribution_weight'] for c in contributions.values())
    for det in contributions:
        contributions[det]['contribution_pct'] = 
            contributions[det]['contribution_weight'] / total * 100
    
    return contributions
```

### 5.3 Sensor-Level Root Cause Attribution

Link detector deviations to specific sensors:

```python
def identify_root_cause_sensors(detector_contributions, sensor_hotspots):
    """
    Map detector contributions to sensor-level causes
    """
    sensor_causes = []
    
    # For AR1: direct sensor mapping
    if detector_contributions['ar1']['contribution_pct'] > 20:
        ar1_sensors = sensor_hotspots.query("detector == 'ar1'")
        sensor_causes.extend(ar1_sensors.to_dict('records'))
    
    # For PCA: use component loadings
    if detector_contributions['pca_spe']['contribution_pct'] > 20:
        pca_sensors = get_pca_top_contributors(sensor_hotspots)
        sensor_causes.extend(pca_sensors)
    
    # For IForest/GMM: use feature importance
    if detector_contributions['iforest']['contribution_pct'] > 20:
        outlier_sensors = get_outlier_features(sensor_hotspots)
        sensor_causes.extend(outlier_sensors)
    
    # Sort by aggregate contribution
    sensor_causes = aggregate_and_rank(sensor_causes)
    return sensor_causes[:10]  # Top 10 sensors
```

### 5.4 Failure Mode Pattern Recognition

Identify common failure patterns from detector signatures:

| Pattern | Detector Signature | Likely Cause | Action |
|---------|-------------------|-------------|--------|
| **Sudden Spike** | High IForest, AR1 spike | Sensor failure, transient | Inspect sensors |
| **Drift** | Rising OMR, AR1 | Process drift, fouling | Recalibrate |
| **Correlation Break** | High PCA-SPE, low T² | Coupling failure | Check mechanical links |
| **Mode Shift** | High GMM, high T² | Regime change | Verify operating conditions |
| **Gradual Decay** | Smooth rise in all detectors | Progressive wear | Schedule maintenance |

```python
def classify_failure_pattern(detector_contributions, detector_time_series):
    """
    Pattern recognition from detector signatures
    """
    patterns = []
    
    # Check for sudden spike
    if max_spike_rate(detector_time_series) > 5.0:
        patterns.append('sudden_spike')
    
    # Check for drift
    if detector_contributions['omr']['trend_slope'] > 0.1:
        patterns.append('drift')
    
    # Check for correlation break
    if detector_contributions['pca_spe']['contribution_pct'] > 40:
        patterns.append('correlation_break')
    
    # Check for gradual decay
    if all_detectors_rising(detector_time_series):
        patterns.append('gradual_decay')
    
    return patterns
```

---

## 6. Intelligent Maintenance Recommendation

### 6.1 Maintenance Urgency Scoring

Compute urgency score based on multiple factors:

```python
def compute_maintenance_urgency(failure_prob, rul_hours, detector_contrib, confidence):
    """
    Urgency Score = f(failure_prob, rul, criticality, confidence)
    Range: 0-100 (100 = immediate action required)
    """
    # Base score from failure probability
    prob_score = failure_prob * 50  # 0-50 points
    
    # RUL component (inverse relationship)
    if rul_hours < 24:
        rul_score = 40
    elif rul_hours < 72:
        rul_score = 30
    elif rul_hours < 168:
        rul_score = 20
    else:
        rul_score = 10
    
    # Detector criticality (some detectors indicate more critical issues)
    critical_detectors = ['ar1', 'pca_spe']  # Sensor/correlation failures
    critical_contribution = sum(
        detector_contrib[d]['contribution_pct'] 
        for d in critical_detectors
    )
    criticality_score = min(critical_contribution / 10, 10)  # 0-10 points
    
    # Confidence adjustment
    urgency = (prob_score + rul_score + criticality_score) * confidence
    
    return min(urgency, 100)
```

### 6.2 Maintenance Window Calculation

Determine optimal maintenance timing:

```python
def calculate_maintenance_window(failure_probs, rul_hours, confidence):
    """
    Find optimal window balancing risk and planning time
    """
    # Earliest safe time: when failure prob exceeds lower threshold
    earliest = find_first_crossing(failure_probs, threshold=0.1)
    
    # Latest safe time: when failure prob exceeds upper threshold
    latest = find_first_crossing(failure_probs, threshold=0.5)
    
    # Preferred time: mid-point with buffer
    if confidence > 0.7:
        buffer_hours = 24  # High confidence: tighter window
    else:
        buffer_hours = 48  # Low confidence: more buffer
    
    preferred_start = earliest
    preferred_end = latest - buffer_hours
    
    return {
        'earliest_maintenance': earliest,
        'preferred_window_start': preferred_start,
        'preferred_window_end': preferred_end,
        'latest_safe_time': latest,
        'confidence': confidence
    }
```

### 6.3 Maintenance Action Recommendation

Generate specific, actionable recommendations:

```python
def generate_maintenance_actions(
    failure_pattern, 
    root_cause_sensors, 
    detector_contributions
):
    """
    Map failure patterns and causes to specific actions
    """
    actions = []
    
    # Pattern-based actions
    if 'sudden_spike' in failure_pattern:
        actions.append({
            'action': 'Inspect sensors for failure',
            'sensors': [s['name'] for s in root_cause_sensors[:3]],
            'priority': 'High',
            'estimated_duration': '2 hours'
        })
    
    if 'drift' in failure_pattern:
        actions.append({
            'action': 'Recalibrate instruments and check process parameters',
            'sensors': 'All affected sensors',
            'priority': 'Medium',
            'estimated_duration': '4 hours'
        })
    
    if 'correlation_break' in failure_pattern:
        actions.append({
            'action': 'Check mechanical linkages and coupling integrity',
            'components': extract_coupled_components(root_cause_sensors),
            'priority': 'High',
            'estimated_duration': '6 hours'
        })
    
    if 'gradual_decay' in failure_pattern:
        actions.append({
            'action': 'Schedule preventive maintenance for progressive wear',
            'components': 'Primary equipment',
            'priority': 'Medium',
            'estimated_duration': '8 hours'
        })
    
    # Detector-specific actions
    if detector_contributions['ar1']['contribution_pct'] > 30:
        actions.append({
            'action': 'Verify sensor readings and wiring',
            'sensors': root_cause_sensors[:5],
            'priority': 'High'
        })
    
    return actions
```

### 6.4 Cost-Benefit Analysis (Optional)

For advanced implementations, integrate cost considerations:

```python
def compute_cost_benefit(maintenance_window, failure_cost, maintenance_cost):
    """
    Simple cost-benefit analysis for maintenance timing
    """
    expected_failure_cost = failure_cost * failure_probability
    
    # Cost of early maintenance (lost production)
    early_cost = maintenance_cost + opportunity_cost(maintenance_window['earliest'])
    
    # Cost of delayed maintenance (higher failure risk)
    delayed_cost = maintenance_cost + expected_failure_cost
    
    # Optimal timing minimizes total expected cost
    optimal_time = minimize_cost(
        range(maintenance_window['earliest'], maintenance_window['latest']),
        cost_function
    )
    
    return {
        'optimal_maintenance_time': optimal_time,
        'expected_cost': compute_expected_cost(optimal_time),
        'cost_of_delay': delayed_cost - early_cost
    }
```

---

## 7. Output Specification

### 7.1 Enhanced Tables

#### Table 1: `failure_probability_ts.csv`
| Column | Type | Description |
|--------|------|-------------|
| RunID | string | Unique run identifier |
| EquipID | int | Equipment identifier |
| Timestamp | datetime | Forecast timestamp |
| ForecastHorizon_Hours | float | Hours into future |
| FailureProbability | float | Probability (0-1) |
| RiskLevel | string | Low/Medium/High/Very High/Critical |
| Confidence | float | Prediction confidence (0-1) |
| Model | string | AR1/Exponential/Polynomial/Ensemble |

#### Table 2: `failure_causation.csv`
| Column | Type | Description |
|--------|------|-------------|
| RunID | string | Unique run identifier |
| EquipID | int | Equipment identifier |
| PredictedFailureTime | datetime | When failure predicted |
| Detector | string | Detector name |
| ContributionPct | float | % contribution to failure |
| MeanZ | float | Mean z-score near failure |
| MaxZ | float | Peak z-score |
| TrendSlope | float | Rate of change |
| FailurePattern | string | Spike/Drift/Decay/etc |

#### Table 3: `root_cause_sensors.csv`
| Column | Type | Description |
|--------|------|-------------|
| RunID | string | Unique run identifier |
| EquipID | int | Equipment identifier |
| PredictedFailureTime | datetime | When failure predicted |
| SensorName | string | Sensor identifier |
| CausationScore | float | Contribution score |
| DetectorSource | string | Which detector flagged it |
| DeviationMagnitude | float | Z-score or equivalent |
| Rank | int | Importance ranking |

#### Table 4: `maintenance_recommendation.csv` (Enhanced)
| Column | Type | Description |
|--------|------|-------------|
| RunID | string | Unique run identifier |
| EquipID | int | Equipment identifier |
| UrgencyScore | float | 0-100 urgency |
| MaintenanceRequired | bool | Yes/No flag |
| EarliestMaintenance | datetime | Earliest safe time |
| PreferredWindowStart | datetime | Recommended start |
| PreferredWindowEnd | datetime | Recommended end |
| LatestSafeTime | datetime | Latest safe time |
| FailureProbAtLatest | float | Risk if delayed |
| FailurePattern | string | Identified pattern |
| RecommendedActions | JSON | List of actions |
| EstimatedDuration_Hours | float | Work duration |
| Confidence | float | Recommendation confidence |

### 7.2 Enhanced Charts

#### Chart 1: Failure Probability Timeline
- X-axis: Forecast horizon (hours)
- Y-axis: Failure probability (%)
- Multiple lines: 24h, 72h, 168h horizons
- Color-coded risk zones
- Confidence bands (shaded)

#### Chart 2: Detector Contribution Pie/Bar
- Show relative contribution of each detector
- Color-coded by detector type
- Hover shows specific metrics

#### Chart 3: Root Cause Sensor Ranking
- Bar chart of top 10 sensors
- Grouped by detector source
- Sorted by causation score

#### Chart 4: Maintenance Window Visualization
- Timeline showing:
  - Earliest safe time
  - Preferred window (highlighted)
  - Latest safe time
  - Current time marker
- Failure probability curve overlay

---

## 8. Implementation Strategy

### 8.1 Module Structure

Create new module `core/enhanced_forecasting.py`:
```python
class EnhancedForecastingEngine:
    def __init__(self, config):
        self.config = config
        self.models = self._initialize_models()
    
    def forecast_health_trajectory(self, health_history):
        """Multi-model health forecasting"""
        pass
    
    def compute_failure_probabilities(self, forecasts, threshold):
        """Probabilistic failure prediction"""
        pass
    
    def analyze_detector_causation(self, detector_scores, failure_time):
        """Detector-based root cause analysis"""
        pass
    
    def generate_maintenance_recommendation(self, failure_probs, causation):
        """Intelligent maintenance guidance"""
        pass
    
    def run(self, ctx):
        """Main entry point called by acm_main.py"""
        pass
```

### 8.2 Integration Points

1. **After fusion**: Extract detector scores and fused health
2. **After episode detection**: Get episode timeline
3. **After regime clustering**: Use regime context for baselines
4. **Before output**: Generate enhanced tables and charts

### 8.3 Configuration

Add to `config_table.csv`:
```csv
EquipID,Category,ParamPath,ParamValue,ValueType,ChangeReason
0,forecasting,enabled,True,bool,Enable enhanced forecasting
0,forecasting,failure_threshold,70.0,float,Health threshold for failure
0,forecasting,forecast_horizons,"[24, 72, 168]",list,Forecast horizons (hours)
0,forecasting,models,"[ar1, exponential, polynomial]",list,Models to use
0,forecasting,confidence_min,0.6,float,Minimum confidence threshold
0,maintenance,urgency_threshold,50.0,float,Urgency score for required maintenance
0,maintenance,buffer_hours,24,int,Safety buffer for maintenance window
0,causation,min_detector_contribution,10.0,float,Min % to report detector
0,causation,top_sensors_count,10,int,Number of sensors to report
```

### 8.4 Testing Strategy

1. **Unit Tests**: Test each component independently
2. **Integration Tests**: Validate full pipeline
3. **Regression Tests**: Ensure existing functionality preserved
4. **Validation Tests**: Compare with known scenarios

---

## 9. Success Criteria

The enhanced system is considered successful when:

1. ✅ **Failure Probability**: Clear percentage values at multiple horizons
2. ✅ **Causation**: Top 3 detectors and top 10 sensors identified with scores
3. ✅ **Maintenance Recommendation**: Binary yes/no plus specific actions
4. ✅ **Confidence**: All predictions include confidence scores
5. ✅ **Flawless Operation**: No crashes, graceful degradation on poor data
6. ✅ **Interpretability**: Outputs understandable by operators
7. ✅ **Validation**: Predictions validated against historical episodes

---

## 10. Future Enhancements

- **Machine Learning**: Replace statistical models with LSTM/GRU for complex patterns
- **Transfer Learning**: Use knowledge from similar assets
- **Real-Time Updates**: Continuous forecasting as new data arrives
- **Prescriptive Analytics**: Specific part replacement recommendations
- **Digital Twin**: Integrate with physics-based models
- **Explainable AI**: SHAP values for sensor importance

---

## 11. References

- ACM Analytics Backbone: `/docs/Analytics Backbone.md`
- RUL Backbone: `/docs/RUL Backbone.md`
- Existing Implementation: `core/forecast.py`, `core/rul_estimator.py`
- Detector Documentation: `docs/OMR_DETECTOR.md`

---

**Document Status**: ✅ Complete and Ready for Implementation

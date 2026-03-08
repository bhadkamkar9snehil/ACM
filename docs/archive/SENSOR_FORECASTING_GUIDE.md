# ACM V10 - Physical Sensor Forecasting Guide

## Overview

ACM V10 introduces physical sensor forecasting - the ability to predict future values of critical equipment sensors (Motor Current, Bearing Temperature, Pressure, etc.) over a 7-day forecast horizon. This goes beyond anomaly detection to provide actionable predictions about equipment behavior.

## What Gets Forecasted

**Automatic Sensor Selection:**
- ACM automatically identifies the **top 10 most variable sensors** based on coefficient of variation (CV = std/mean)
- Sensors showing significant change patterns are prioritized
- Selection is data-driven and adapts per equipment and time window

**Typical Sensors Forecasted:**
- Motor Current (amperage trends indicating load changes)
- Bearing Temperatures (thermal degradation patterns)
- Vibration Measurements (mechanical wear indicators)
- Pressure Readings (system performance metrics)
- Flow Rates (operational efficiency indicators)

## Forecasting Methods

### 1. LinearTrend (Default)
- **Algorithm:** Simple linear extrapolation from recent 24-hour trend
- **Confidence Intervals:** Based on residual standard deviation
- **Best For:** Sensors with clear upward/downward trends
- **Speed:** Very fast (~10ms per sensor)
- **Parameters:**
  - `max_sensor_slope`: Maximum allowed slope (default: 10.0 units/hour)
  - `sensor_bounds`: Per-sensor min/max constraints

**Example Use Case:** Bearing temperature increasing by 2°F/hour → forecasts 336°F in 7 days

### 2. VAR (Vector AutoRegression)
- **Algorithm:** Multivariate time series model capturing sensor interactions
- **Confidence Intervals:** Model-based prediction intervals
- **Best For:** Groups of correlated sensors (e.g., temperature cluster)
- **Requirements:** Minimum 3 sensors, sufficient history
- **Speed:** Moderate (~100ms for 10 sensors)

**Example Use Case:** Motor current and bearing temp both increasing → VAR captures coupled dynamics

## Configuration

**In `configs/config_table.csv`:**
```csv
forecast.sensor_forecast_method,linear  # or "var"
forecast.sensor_min,0.0                  # Global minimum sensor value
forecast.sensor_max,1000.0               # Global maximum sensor value
forecast.sensor_bounds,{"Motor_Current": {"min": 0, "max": 100}}  # Per-sensor bounds
```

## Database Schema

**Table: `ACM_SensorForecast`**
```sql
CREATE TABLE dbo.ACM_SensorForecast (
    RunID           UNIQUEIDENTIFIER NOT NULL,  -- FK to ACM_Runs
    EquipID         INT NOT NULL,               -- FK to Equipment
    Timestamp       DATETIME2 NOT NULL,         -- Forecast timestamp
    SensorName      NVARCHAR(255) NOT NULL,     -- Physical sensor name
    ForecastValue   FLOAT NOT NULL,             -- Predicted value
    CiLower         FLOAT NULL,                 -- Lower 95% confidence bound
    CiUpper         FLOAT NULL,                 -- Upper 95% confidence bound
    ForecastStd     FLOAT NULL,                 -- Forecast standard deviation
    Method          NVARCHAR(50) NOT NULL,      -- LinearTrend or VAR
    RegimeLabel     INT NULL,                   -- Operating regime
    CreatedAt       DATETIME2 NOT NULL,
    
    PRIMARY KEY (RunID, EquipID, Timestamp, SensorName)
);
```

**Typical Data Volume:**
- **Per Run:** 1,680 rows (168 timestamps × 10 sensors)
- **Storage:** ~200 KB per run
- **Retention:** Configure based on audit requirements (default: 90 days)

## Querying Sensor Forecasts

### Get Latest Sensor Forecasts for Equipment
```sql
SELECT 
    sf.SensorName,
    sf.Timestamp,
    ROUND(sf.ForecastValue, 2) AS ForecastValue,
    ROUND(sf.CiLower, 2) AS LowerBound,
    ROUND(sf.CiUpper, 2) AS UpperBound,
    sf.Method
FROM ACM_SensorForecast sf
WHERE sf.EquipID = 1  -- FD_FAN
  AND sf.RunID = (SELECT MAX(RunID) FROM ACM_Runs WHERE EquipID = 1)
ORDER BY sf.SensorName, sf.Timestamp;
```

### Identify Sensors with Concerning Trends
```sql
WITH SensorTrends AS (
    SELECT
        SensorName,
        MAX(ForecastValue) - MIN(ForecastValue) AS TrendRange,
        AVG(ForecastValue) AS AvgValue,
        Method
    FROM ACM_SensorForecast
    WHERE EquipID = 1
      AND RunID = (SELECT MAX(RunID) FROM ACM_Runs WHERE EquipID = 1)
    GROUP BY SensorName, Method
)
SELECT TOP 5
    SensorName,
    ROUND(TrendRange, 2) AS TrendChange,
    ROUND(AvgValue, 2) AS AvgValue,
    Method
FROM SensorTrends
ORDER BY TrendRange DESC;
```

### Compare Forecast vs Actual (Post-Validation)
```sql
-- After 7 days, compare forecasts with actual sensor readings
SELECT 
    sf.SensorName,
    sf.Timestamp AS ForecastTime,
    sf.ForecastValue,
    hist.SensorValue AS ActualValue,
    ABS(sf.ForecastValue - hist.SensorValue) AS Error,
    CASE 
        WHEN hist.SensorValue BETWEEN sf.CiLower AND sf.CiUpper 
        THEN 'Within CI' 
        ELSE 'Outside CI' 
    END AS AccuracyCheck
FROM ACM_SensorForecast sf
LEFT JOIN ACM_HistorianData hist 
    ON sf.EquipID = hist.EquipID 
    AND sf.Timestamp = hist.EntryDateTime
WHERE sf.EquipID = 1
  AND sf.RunID = (SELECT MAX(RunID) FROM ACM_Runs WHERE EquipID = 1)
ORDER BY sf.SensorName, sf.Timestamp;
```

## Grafana Dashboard

**New Panels in v10 Dashboard (FORECASTING & RUL Section):**

1. **"Top 5 Physical Sensor Forecasts (7-Day Trend)"** (Panel ID: 44)
   - Time series visualization showing 5 most variable sensors
   - Multiple lines with legend showing last/mean values
   - Interactive hover for precise values and confidence intervals

2. **"Sensor Forecast Summary - Top Changing Sensors"** (Panel ID: 45)
   - Table showing top 10 sensors by trend magnitude
   - Columns: Sensor name (truncated), Trend (gauge), Average, Method
   - Color-coded trend indicators (blue=stable, red=high change)

## Operational Use Cases

### 1. Predictive Maintenance Scheduling
**Scenario:** Bearing temperature forecast shows 180°F in 72 hours (above failure threshold of 160°F)
**Action:** Schedule bearing replacement within 2 days to avoid unplanned downtime

### 2. Load Planning
**Scenario:** Motor current forecast shows increasing trend, reaching 95% capacity in 5 days
**Action:** Plan load redistribution or equipment rotation to prevent overload

### 3. Process Optimization
**Scenario:** Multiple pressure sensors forecasted to decrease, indicating filter clogging
**Action:** Schedule filter replacement before performance degradation

### 4. Anomaly Validation
**Scenario:** Anomaly detector flags high bearing temp, but forecast shows decreasing trend
**Action:** Confirm temporary spike (not sustained degradation); continue monitoring

## Integration with Other ACM Features

**Combined with Health Forecasting:**
- Health score drops below 70 in 4 days
- Sensor forecasts identify bearing temp as primary driver
- **Result:** Pinpoint root cause for proactive intervention

**Combined with RUL:**
- RUL shows 48 hours remaining
- Sensor forecasts show motor current at 110% in 36 hours
- **Result:** Confirm failure mode and timing

**Combined with Regime Analysis:**
- Sensor forecasts tagged with operating regime
- Different forecasts for "High Load" vs "Normal" regimes
- **Result:** Context-aware predictions

## Limitations & Considerations

### Data Requirements
- **Minimum:** 10 rows of historical sensor data
- **Optimal:** 100+ rows (5+ days at 30-min cadence)
- **Quality:** Missing data filled with median; excessive gaps reduce accuracy

### Forecast Horizon
- **Default:** 168 hours (7 days)
- **Accuracy:** Degrades with distance (most reliable: 0-48h)
- **Confidence Intervals:** Widen with forecast distance

### Sensor Selection
- Only numeric sensors considered
- Low-variability sensors (std < 1e-6) excluded
- Maximum 10 sensors forecasted per run

### Method Selection
- LinearTrend: Always available
- VAR: Requires ≥3 sensors and adequate training data
- Automatic fallback: VAR → LinearTrend if VAR fails

## Performance Benchmarks

**Forecasting Speed (10 sensors, 168 timestamps):**
- LinearTrend: ~50ms
- VAR: ~150ms
- Total overhead: <0.5% of ACM run time

**Accuracy Metrics (Validated on Test Equipment):**
- **24h Forecast:** MAPE ~5% (Mean Absolute Percentage Error)
- **72h Forecast:** MAPE ~12%
- **168h Forecast:** MAPE ~20%
- **Confidence Interval Coverage:** 92% (target: 95%)

## Troubleshooting

### No Sensor Forecasts Generated
**Check:**
1. `SELECT COUNT(*) FROM ACM_SensorForecast WHERE RunID = '<latest_run>'`
2. Review logs for "Insufficient sensor data for forecasting"
3. Verify sensor data quality: `SELECT COUNT(*), MIN(EntryDateTime), MAX(EntryDateTime) FROM {Equipment}_Data`

### Forecast Values Out of Range
**Solution:** Configure `sensor_bounds` in config_table.csv:
```csv
forecast.sensor_bounds,{"Motor_Current": {"min": 0, "max": 100}, "Bearing_Temp": {"min": -40, "max": 200}}
```

### VAR Method Failing
**Check Logs:** Look for "VAR failed; falling back to linear trend"
**Common Causes:**
- Insufficient correlated sensors (need ≥3)
- Too many missing values
- Numerical instability (singular covariance matrix)

## Future Enhancements (Roadmap)

- [ ] LSTM/RNN deep learning models for complex patterns
- [ ] Seasonal decomposition for equipment with periodic behavior
- [ ] Multi-step forecasting with recursive updates
- [ ] Forecast accuracy tracking and adaptive method selection
- [ ] Sensor forecast-based alerting (threshold crossing predictions)
- [ ] Integration with external factors (weather, production schedule)

---

**For Questions/Support:** Refer to `docs/ACM_SYSTEM_OVERVIEW.md` or contact ACM development team

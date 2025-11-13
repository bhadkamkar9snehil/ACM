# ACM Dashboard SQL Queries Reference

This document provides the complete SQL query reference for all panels in the ACM Asset Health Dashboard. Use this for troubleshooting, customization, or creating derivative dashboards.

## Variables

All queries use these Grafana variables:
- `$datasource`: SQL Server data source (auto-selected)
- `$equipment`: Equipment ID (user-selectable)
- `$__timeFrom()`: Start of selected time range
- `$__timeTo()`: End of selected time range
- `$health_zone`: Health zone filter (optional, multi-select)

## Executive Summary Panels

### 1. Overall Health Score (Gauge)
```sql
SELECT TOP 1 HealthIndex 
FROM ACM_HealthTimeline 
WHERE EquipID = $equipment 
ORDER BY Timestamp DESC
```
**Purpose**: Current health index (0-100 scale)  
**Expected Result**: Single numeric value  
**Thresholds**: Red <70, Yellow 70-84, Green 85-100

---

### 2. Current Status (Stat)
```sql
SELECT TOP 1 
  CASE 
    WHEN HealthIndex >= 85 THEN 'HEALTHY'
    WHEN HealthIndex >= 70 THEN 'CAUTION'
    ELSE 'ALERT'
  END as Status
FROM ACM_HealthTimeline 
WHERE EquipID = $equipment 
ORDER BY Timestamp DESC
```
**Purpose**: Text status badge  
**Expected Result**: String - HEALTHY/CAUTION/ALERT  
**Color Mode**: Background color based on value

---

### 3. Days Since Last Alert (Stat)
```sql
SELECT TOP 1 
  DATEDIFF(day, StartTimestamp, GETDATE()) as DaysSince
FROM ACM_AlertAge 
WHERE EquipID = $equipment 
  AND AlertZone = 'ALERT'
ORDER BY StartTimestamp DESC
```
**Purpose**: Days since equipment was last in ALERT zone  
**Expected Result**: Integer (days)  
**Unit**: days (d)

---

### 4. Active Episodes (Stat)
```sql
SELECT COUNT(*) as ActiveEpisodes
FROM ACM_CulpritHistory 
WHERE EquipID = $equipment 
  AND (EndTimestamp IS NULL OR EndTimestamp >= DATEADD(hour, -24, GETDATE()))
```
**Purpose**: Count of episodes active or recently ended (<24h)  
**Expected Result**: Integer count  
**Color**: Green=0, Yellow=1-4, Red=5+

---

### 5. Worst Sensor (Stat)
```sql
SELECT TOP 1 
  CONCAT(SensorName, ' (z=', CAST(ROUND(LatestAbsZ, 2) as VARCHAR), ')') as WorstSensor
FROM ACM_SensorHotspots 
WHERE EquipID = $equipment 
ORDER BY LatestAbsZ DESC
```
**Purpose**: Sensor with highest current z-score  
**Expected Result**: String (e.g., "BEARING_TEMP (z=3.45)")  
**Display**: Text only

---

### 6. Current Regime (Stat)
```sql
SELECT TOP 1 
  CONCAT('Regime ', CAST(RegimeLabel as VARCHAR)) as CurrentRegime
FROM ACM_RegimeTimeline 
WHERE EquipID = $equipment 
ORDER BY Timestamp DESC
```
**Purpose**: Current operating regime/mode  
**Expected Result**: String (e.g., "Regime 2")  
**Display**: Text only

---

## Health Timeline Panel

### 7. Health Index Timeline (Time Series)
```sql
SELECT 
  Timestamp as time, 
  HealthIndex, 
  HealthZone
FROM ACM_HealthTimeline 
WHERE EquipID = $equipment 
  AND Timestamp >= $__timeFrom() 
  AND Timestamp <= $__timeTo()
ORDER BY Timestamp
```
**Purpose**: Health index over time with zone classification  
**Expected Result**: Time series with 3 columns  
**Visualization**: Line chart with area fill  
**Colors**: Gradient based on HealthZone (GOOD=green, WATCH=yellow, ALERT=red)

**Performance Note**: This is the most frequently queried table. Ensure index exists:
```sql
CREATE NONCLUSTERED INDEX IX_ACM_HealthTimeline_EquipTime 
ON ACM_HealthTimeline(EquipID, Timestamp) 
INCLUDE (HealthIndex, HealthZone, FusedZ);
```

---

## Regime Timeline Panel

### 8. Operating Regime Timeline (State Timeline)
```sql
SELECT 
  Timestamp as time, 
  CONCAT('Regime ', CAST(RegimeLabel as VARCHAR)) as regime,
  RegimeState as state
FROM ACM_RegimeTimeline 
WHERE EquipID = $equipment 
  AND Timestamp >= $__timeFrom() 
  AND Timestamp <= $__timeTo()
ORDER BY Timestamp
```
**Purpose**: Operating mode over time  
**Expected Result**: Time series with regime labels  
**Visualization**: State timeline (horizontal colored bars)  
**Colors**: Auto-assigned per regime or use overrides

---

## Root Cause Analysis Panels

### 9. Current Sensor Contributions (Bar Chart)
```sql
SELECT TOP 15 
  DetectorType as sensor, 
  ContributionPct as contribution,
  ZScore as zscore
FROM ACM_ContributionCurrent 
WHERE EquipID = $equipment 
ORDER BY ContributionPct DESC
```
**Purpose**: Top sensors contributing to current anomaly score  
**Expected Result**: 3 columns, up to 15 rows  
**Visualization**: Horizontal bar chart  
**Colors**: Thresholds on zscore (green <2, yellow 2-2.5, orange 2.5-3, red >3)

**Note**: If table is empty, equipment is healthy (no anomaly)

---

### 10. Sensor Contributions Over Time (Stacked Area)
```sql
SELECT 
  Timestamp as time, 
  DetectorType as metric, 
  ContributionPct as value
FROM ACM_ContributionTimeline 
WHERE EquipID = $equipment 
  AND Timestamp >= $__timeFrom() 
  AND Timestamp <= $__timeTo()
ORDER BY Timestamp, DetectorType
```
**Purpose**: Historical sensor contribution trends  
**Expected Result**: Time series with multiple sensors  
**Visualization**: Stacked area chart (100% stack)  
**Colors**: Distinct color per sensor

**Performance Warning**: Large table (~50k rows per 30 days). Consider limiting to top 8 sensors:
```sql
-- Optimized version (filter to top sensors first)
WITH TopSensors AS (
  SELECT TOP 8 DetectorType
  FROM ACM_ContributionCurrent 
  WHERE EquipID = $equipment 
  ORDER BY ContributionPct DESC
)
SELECT 
  ct.Timestamp as time, 
  ct.DetectorType as metric, 
  ct.ContributionPct as value
FROM ACM_ContributionTimeline ct
INNER JOIN TopSensors ts ON ct.DetectorType = ts.DetectorType
WHERE ct.EquipID = $equipment 
  AND ct.Timestamp >= $__timeFrom() 
  AND ct.Timestamp <= $__timeTo()
ORDER BY ct.Timestamp, ct.DetectorType
```

---

## Sensor Hotspots Panel

### 11. Sensor Hotspots Table
```sql
SELECT TOP 20 
  SensorName as [Sensor Name],
  ROUND(LatestAbsZ, 2) as [Current Z-Score],
  ROUND(MaxAbsZ, 2) as [Peak Z-Score],
  MaxTimestamp as [Peak Time],
  ROUND(LatestValue, 2) as [Current Value],
  ROUND(TrainMean, 2) as [Normal Mean],
  AboveAlertCount as [Alert Count]
FROM ACM_SensorHotspots 
WHERE EquipID = $equipment 
ORDER BY LatestAbsZ DESC
```
**Purpose**: Detailed sensor deviation metrics  
**Expected Result**: Table with up to 20 rows  
**Visualization**: Table with cell color overrides on z-score columns  
**Sorting**: Default by Current Z-Score descending

**Cell Color Override** (apply to Current Z-Score and Peak Z-Score columns):
- Green: 0-2.0
- Yellow: 2.0-2.5
- Orange: 2.5-3.0
- Red: >3.0

---

## Diagnostics Panels

### 12. Detector Correlation Matrix (Heatmap)
```sql
SELECT 
  DetectorA as detector1, 
  DetectorB as detector2, 
  PearsonR as correlation
FROM ACM_DetectorCorrelation 
WHERE EquipID = $equipment
```
**Purpose**: Show which detectors agree/disagree  
**Expected Result**: ~28 rows (8 detectors × 7 pairs)  
**Visualization**: Heatmap  
**Color Scale**: -1 (red) to +1 (green), 0 = neutral

**Interpretation**:
- High correlation (>0.8): Detectors see same anomalies (redundant)
- Low correlation (<0.3): Detectors see different anomalies (complementary)
- Negative correlation (<0): Inverse relationship (unusual, investigate)

---

### 13. Health Zone Distribution by Period (Stacked Bar)
```sql
SELECT 
  PeriodStart as period, 
  HealthZone as zone, 
  ZonePct as percentage
FROM ACM_HealthZoneByPeriod 
WHERE EquipID = $equipment 
  AND PeriodStart >= $__timeFrom() 
  AND PeriodStart <= $__timeTo()
ORDER BY PeriodStart
```
**Purpose**: Daily health zone percentages  
**Expected Result**: 3 rows per day (GOOD, WATCH, ALERT)  
**Visualization**: Stacked bar chart (100% stack)  
**Colors**: Green (GOOD), Yellow (WATCH), Red (ALERT)

**Trend Analysis**:
- Increasing red % = degrading
- Increasing green % = improving
- High yellow % = borderline, needs attention

---

## Defect Timeline Panel

### 14. Defect Event Timeline (Time Series)
```sql
SELECT 
  Timestamp as time, 
  CONCAT(FromZone, ' → ', ToZone) as transition,
  HealthIndex as health,
  FusedZ as zscore
FROM ACM_DefectTimeline 
WHERE EquipID = $equipment 
  AND Timestamp >= $__timeFrom() 
  AND Timestamp <= $__timeTo()
ORDER BY Timestamp
```
**Purpose**: Health zone transitions and events  
**Expected Result**: Time series with zone change markers  
**Visualization**: Time series with points (draw_style: points)  
**Colors**: Based on ToZone (target zone color)

**Event Types**:
- GOOD → WATCH: Early warning
- WATCH → ALERT: Escalation
- ALERT → WATCH: Improving
- WATCH → GOOD: Recovery

---

## Historical Context Panels

### 15. Episode Metrics (Stat Grid)
```sql
SELECT 
  TotalEpisodes as [Total Episodes],
  ROUND(AvgDurationHours, 1) as [Avg Duration (h)],
  ROUND(MaxDurationHours, 1) as [Max Duration (h)],
  ROUND(RatePerDay, 2) as [Episodes/Day],
  ROUND(MeanInterarrivalHours, 1) as [Interarrival (h)]
FROM ACM_EpisodeMetrics 
WHERE EquipID = $equipment
```
**Purpose**: Aggregate episode statistics  
**Expected Result**: Single row with 5 metrics  
**Visualization**: Stat grid (5 panels)  
**Display**: Each metric in its own stat panel

---

### 16. Regime Occupancy (Pie Chart)
```sql
SELECT 
  CONCAT('Regime ', CAST(RegimeLabel as VARCHAR)) as regime,
  Percentage as value
FROM ACM_RegimeOccupancy 
WHERE EquipID = $equipment
```
**Purpose**: Time distribution across operating regimes  
**Expected Result**: 3-5 rows (one per regime)  
**Visualization**: Donut chart  
**Display**: Percentage labels on slices

---

### 17. Drift Detection (Time Series)
```sql
SELECT 
  Timestamp as time, 
  DriftValue as value
FROM ACM_DriftSeries 
WHERE EquipID = $equipment 
  AND Timestamp >= $__timeFrom() 
  AND Timestamp <= $__timeTo()
ORDER BY Timestamp
```
**Purpose**: Baseline drift over time (CUSUM statistic)  
**Expected Result**: Time series, one value per timestamp  
**Visualization**: Line chart  
**Threshold**: Horizontal line at 3.0 (drift detected above this)

**Interpretation**:
- Flat near 0: Stable baseline
- Gradual increase: Slow drift
- Spikes above 3: Drift events (baseline shift detected)

---

## Sensor Anomaly Heatmap Panel

### 18. Sensor Anomaly Rates by Period (Heatmap)
```sql
SELECT 
  PeriodStart as time,
  DetectorType as sensor,
  AnomalyRatePct as value
FROM ACM_SensorAnomalyByPeriod 
WHERE EquipID = $equipment 
  AND PeriodStart >= $__timeFrom() 
  AND PeriodStart <= $__timeTo()
ORDER BY PeriodStart, DetectorType
```
**Purpose**: Daily anomaly rates per sensor  
**Expected Result**: Multiple rows (days × sensors)  
**Visualization**: Heatmap  
**Color Scale**: White (0%) to Red (100%)

**Pattern Recognition**:
- Horizontal bright stripes: Chronic sensor issue
- Vertical bright stripes: Event affecting multiple sensors
- Scattered bright cells: Intermittent issues
- Dark (all green): Healthy period

---

## Calibration & System Health Panels

### 19. Detector Calibration Summary (Table)
```sql
SELECT 
  DetectorType as [Detector],
  ROUND(MeanZ, 2) as [Mean Z],
  ROUND(P95Z, 2) as [P95 Z],
  ROUND(P99Z, 2) as [P99 Z],
  ROUND(ClipZ, 1) as [Clip Threshold],
  ROUND(SaturationPct, 1) as [Saturation %]
FROM ACM_CalibrationSummary 
WHERE EquipID = $equipment
```
**Purpose**: Detector health and calibration metrics  
**Expected Result**: 8-10 rows (one per detector)  
**Visualization**: Table  
**Alert Threshold**: Highlight if Saturation % > 10% (detector clipping too often)

**Interpretation**:
- Mean Z near 0: Well calibrated
- P95 Z < clip threshold: Good headroom
- Saturation % > 10%: Detector saturating, needs recalibration

---

### 20. Regime Stability Metrics (Stat Grid)
```sql
SELECT 
  MetricName as metric,
  ROUND(MetricValue, 2) as value
FROM ACM_RegimeStability 
WHERE EquipID = $equipment
```
**Purpose**: Regime detection quality metrics  
**Expected Result**: 4 rows (churn_rate, total_transitions, avg_dwell, median_dwell)  
**Visualization**: Stat grid (4 panels)  
**Display**: One stat panel per metric

**Interpretation**:
- Low churn rate (<5%): Stable regime detection
- High avg dwell (>1000 periods): Regimes don't flip frequently
- High transitions: Noisy regime detection (may need tuning)

---

## Query Optimization Tips

### 1. Always Filter by EquipID and Time
```sql
-- Good
WHERE EquipID = $equipment 
  AND Timestamp >= $__timeFrom() 
  AND Timestamp <= $__timeTo()

-- Bad
WHERE EquipID = $equipment  -- Missing time filter, scans entire table
```

### 2. Use TOP for Ranking Queries
```sql
-- Good
SELECT TOP 15 ... ORDER BY ContributionPct DESC

-- Bad
SELECT ... ORDER BY ContributionPct DESC  -- Returns all rows, Grafana limits display
```

### 3. Round Floats in Query, Not in Grafana
```sql
-- Good
SELECT ROUND(HealthIndex, 2) as HealthIndex

-- Bad
SELECT HealthIndex  -- Let Grafana round (slower, inconsistent)
```

### 4. Use CONCAT for String Building
```sql
-- Good
CONCAT('Regime ', CAST(RegimeLabel as VARCHAR))

-- Bad
'Regime ' + CAST(RegimeLabel as VARCHAR)  -- Fails on NULLs
```

### 5. Ensure Indexes Exist
```sql
-- Critical indexes for dashboard performance
CREATE NONCLUSTERED INDEX IX_ACM_HealthTimeline_EquipTime 
ON ACM_HealthTimeline(EquipID, Timestamp) INCLUDE (HealthIndex, HealthZone);

CREATE NONCLUSTERED INDEX IX_ACM_ContributionTimeline_EquipTime 
ON ACM_ContributionTimeline(EquipID, Timestamp) INCLUDE (DetectorType, ContributionPct);

CREATE NONCLUSTERED INDEX IX_ACM_SensorHotspots_EquipZ 
ON ACM_SensorHotspots(EquipID, LatestAbsZ DESC) INCLUDE (SensorName, MaxAbsZ);
```

---

## Troubleshooting Query Issues

### Query Returns No Data
**Check**:
1. Equipment ID exists: `SELECT COUNT(*) FROM ACM_HealthTimeline WHERE EquipID = 1`
2. Time range has data: `SELECT MIN(Timestamp), MAX(Timestamp) FROM ACM_HealthTimeline WHERE EquipID = 1`
3. Variable syntax: Ensure `$equipment` not `${equipment}` in SQL mode

### Query Timeout
**Solutions**:
1. Add missing indexes (see section 5 above)
2. Reduce time range
3. Limit result set (TOP N)
4. Consider table partitioning for large datasets

### Wrong Data Type Errors
**Common Issues**:
- CAST datetime to VARCHAR for CONCAT: `CAST(Timestamp as VARCHAR(30))`
- Handle NULLs: Use `ISNULL()` or `COALESCE()`
- Grafana expects specific column names: `time`, `metric`, `value` for time series

### Performance Tuning
**Query execution time targets**:
- Stat panels: <100ms
- Time series: <500ms
- Tables: <1s
- Heatmaps: <2s

If queries exceed these, optimize using:
1. Indexed views for expensive aggregations
2. Materialized summary tables
3. Query result caching (Grafana level)
4. Table partitioning by month/year

---

## Custom Query Examples

### Example 1: Top 5 Episodes by Duration
```sql
SELECT TOP 5
  StartTimestamp as StartTime,
  EndTimestamp as EndTime,
  ROUND(DurationHours, 1) as [Duration (h)],
  PrimaryDetector as [Culprit Sensor]
FROM ACM_CulpritHistory
WHERE EquipID = $equipment
  AND StartTimestamp >= $__timeFrom()
  AND StartTimestamp <= $__timeTo()
ORDER BY DurationHours DESC
```

### Example 2: Health Trend (Daily Average)
```sql
SELECT 
  CAST(Timestamp as DATE) as date,
  ROUND(AVG(HealthIndex), 1) as AvgHealth,
  MIN(HealthIndex) as MinHealth,
  MAX(HealthIndex) as MaxHealth
FROM ACM_HealthTimeline
WHERE EquipID = $equipment
  AND Timestamp >= $__timeFrom()
  AND Timestamp <= $__timeTo()
GROUP BY CAST(Timestamp as DATE)
ORDER BY date
```

### Example 3: Sensor Z-Score Distribution
```sql
SELECT 
  SensorName,
  COUNT(*) as Observations,
  ROUND(AVG(LatestAbsZ), 2) as AvgZ,
  ROUND(STDEV(LatestAbsZ), 2) as StdZ,
  MAX(MaxAbsZ) as PeakZ
FROM ACM_SensorHotspotTimeline
WHERE EquipID = $equipment
  AND Timestamp >= $__timeFrom()
  AND Timestamp <= $__timeTo()
GROUP BY SensorName
ORDER BY PeakZ DESC
```

---

## Related Documentation

- **Dashboard README**: `grafana_dashboards/README.md` - Setup and usage
- **Operator Guide**: `grafana_dashboards/docs/OPERATOR_QUICK_START.md` - Non-technical guide
- **Charting Philosophy**: `grafana_dashboards/docs/CHARTING_PHILOSOPHY.md` - Design principles
- **SQL Schema**: `docs/SQL_SCHEMA_DESIGN.md` - Table structures
- **Output Manager**: `core/output_manager.py` - Table population logic

---

**Last Updated**: 2025-11-13  
**Dashboard Version**: 1.0  
**SQL Server**: 2016+  
**Author**: ACM Team

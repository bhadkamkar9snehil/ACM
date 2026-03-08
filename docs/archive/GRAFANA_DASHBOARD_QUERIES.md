# ACM Grafana Dashboard Queries Reference

**Version:** 11.1.5  
**Last Updated:** 2026-01-03  
**Purpose:** Authoritative reference for all Grafana dashboard SQL queries

---

## Overview

This document contains validated SQL queries for ACM Grafana dashboards. All queries:
- Use `$equipment` variable for EquipID filtering
- Use `$__timeFrom()` and `$__timeTo()` for time range filtering where appropriate
- Follow T-SQL syntax (Microsoft SQL Server)
- Are tested against the ACM schema

### Key Rules
1. **Time Series panels**: Must use `ORDER BY ... ASC` and alias time column as `time`
2. **Pie Charts**: Grafana expects numeric values - use column names like `value` or specific count columns
3. **Latest Run queries**: Use subquery to get most recent RunID
4. **Numeric columns**: Don't cast integers to strings - Grafana handles value mappings

---

## 1. Health & Status Overview

### 1.1 Current Health Score
```sql
SELECT TOP 1 
    HealthIndex,
    HealthZone,
    Confidence
FROM ACM_HealthTimeline
WHERE EquipID = $equipment
ORDER BY Timestamp DESC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Stat / Gauge |
| **Format** | Table |
| **Shows** | Current equipment health percentage with zone |
| **Data Scope** | Latest record only |

---

### 1.2 Health Timeline
```sql
SELECT 
    Timestamp AS time,
    HealthIndex AS value,
    'Health %' AS metric
FROM ACM_HealthTimeline
WHERE EquipID = $equipment
  AND Timestamp BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY Timestamp ASC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Time Series |
| **Format** | Time series |
| **Shows** | Health trend over time |
| **Thresholds** | 70% (warn), 50% (critical) |

---

### 1.3 Health Zone Distribution (Pie Chart)
```sql
SELECT 
    HealthZone AS metric,
    COUNT(*) AS value
FROM ACM_HealthTimeline
WHERE EquipID = $equipment
  AND Timestamp BETWEEN $__timeFrom() AND $__timeTo()
GROUP BY HealthZone
ORDER BY value DESC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Pie Chart |
| **Format** | Table |
| **Shows** | Time distribution across health zones |
| **Value Mappings** | GOOD→Green, WATCH→Yellow, ALERT→Red |

**Pie Chart Settings:**
- Legend: `metric` field
- Value: `value` field
- Display labels: Percent

---

## 2. Anomaly Detection

### 2.1 Detector Scores Timeline
```sql
SELECT 
    Timestamp AS time,
    ar1_z,
    pca_spe_z,
    pca_t2_z,
    iforest_z,
    gmm_z,
    cusum_z
FROM ACM_Scores_Wide
WHERE EquipID = $equipment
  AND Timestamp BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY Timestamp ASC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Time Series (multi-line) |
| **Format** | Time series |
| **Shows** | All detector z-scores; spikes = anomalies |

---

### 2.2 Fused Anomaly Score
```sql
SELECT 
    Timestamp AS time,
    fused AS value,
    'Fused Score' AS metric
FROM ACM_Scores_Wide
WHERE EquipID = $equipment
  AND Timestamp BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY Timestamp ASC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Time Series with thresholds |
| **Format** | Time series |
| **Shows** | Combined anomaly score |
| **Thresholds** | 1.5 (warn), 3.0 (alert) |

---

### 2.3 Recent Anomaly Episodes
```sql
SELECT TOP 20
    StartTime,
    EndTime,
    ROUND(DATEDIFF(MINUTE, StartTime, COALESCE(EndTime, GETDATE())) / 60.0, 1) AS DurationHours,
    Severity,
    Confidence
FROM ACM_Anomaly_Events
WHERE EquipID = $equipment
  AND StartTime BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY StartTime DESC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Table |
| **Format** | Table |
| **Shows** | List of anomaly episodes with duration |
| **Value Mappings** | info→Green, warning→Yellow, critical→Red |

---

### 2.4 Episode Count by Day
```sql
SELECT 
    CAST(StartTime AS DATE) AS time,
    COUNT(*) AS value,
    'Episodes' AS metric
FROM ACM_Anomaly_Events
WHERE EquipID = $equipment
  AND StartTime BETWEEN $__timeFrom() AND $__timeTo()
GROUP BY CAST(StartTime AS DATE)
ORDER BY time ASC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Bar Chart |
| **Format** | Time series |
| **Shows** | Daily count of anomaly episodes |

---

## 3. Sensor Analysis

### 3.1 Active Sensor Defects (Latest Run)
```sql
SELECT 
    DetectorType,
    DetectorFamily,
    Severity,
    ViolationCount,
    ROUND(ViolationPct, 2) AS ViolationPct,
    ROUND(MaxZ, 2) AS MaxZ,
    ROUND(CurrentZ, 2) AS CurrentZ,
    ActiveDefect
FROM ACM_SensorDefects
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID 
      FROM ACM_SensorDefects 
      WHERE EquipID = $equipment 
      ORDER BY ID DESC
  )
ORDER BY ViolationPct DESC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Table |
| **Format** | Table |
| **Shows** | Current defect status per detector |
| **Value Mappings** | LOW→Green, MEDIUM→Yellow, HIGH→Red |

---

### 3.2 Top Sensor Hotspots (Latest Run)
```sql
SELECT TOP 10
    SensorName,
    ROUND(MaxAbsZ, 2) AS MaxZ,
    ROUND(LatestAbsZ, 2) AS LatestZ,
    AboveAlertCount AS Alerts,
    AboveWarnCount AS Warnings
FROM ACM_SensorHotspots
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID 
      FROM ACM_SensorHotspots 
      WHERE EquipID = $equipment 
      ORDER BY ID DESC
  )
ORDER BY MaxAbsZ DESC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Bar Chart (horizontal) |
| **Format** | Table |
| **Shows** | Sensors with highest anomaly z-scores |

---

### 3.3 Sensor Correlations (Latest Run)
```sql
SELECT TOP 50
    Sensor1,
    Sensor2,
    ROUND(Correlation, 3) AS Correlation
FROM ACM_SensorCorrelations
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID 
      FROM ACM_SensorCorrelations 
      WHERE EquipID = $equipment 
      ORDER BY ID DESC
  )
  AND Sensor1 <> Sensor2
  AND ABS(Correlation) > 0.8
ORDER BY ABS(Correlation) DESC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Table |
| **Format** | Table |
| **Shows** | Highly correlated sensor pairs |

---

## 4. Operating Regimes

### 4.1 Regime Timeline
```sql
SELECT 
    Timestamp AS time,
    RegimeLabel AS value,
    'Regime' AS metric
FROM ACM_RegimeTimeline
WHERE EquipID = $equipment
  AND Timestamp BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY Timestamp ASC
```
| Property | Value |
|----------|-------|
| **Chart Type** | State Timeline or Time Series |
| **Format** | Time series |
| **Shows** | Operating regime changes over time |
| **Value Mappings** | -1→UNKNOWN (purple), 0→Regime 0, 1→Regime 1, etc. |

**Note:** RegimeLabel is an INTEGER column. Use Grafana value mappings:
- `-1` → "UNKNOWN" (dark purple)
- `0` → "Normal" (green)
- `1` → "High Load" (yellow)
- `2` → "Startup" (orange)

---

### 4.2 Regime Distribution (Pie Chart)
```sql
SELECT 
    CASE 
        WHEN RegimeLabel = -1 THEN 'UNKNOWN'
        ELSE CONCAT('Regime ', RegimeLabel)
    END AS metric,
    COUNT(*) AS value
FROM ACM_RegimeTimeline
WHERE EquipID = $equipment
  AND Timestamp BETWEEN $__timeFrom() AND $__timeTo()
GROUP BY RegimeLabel
ORDER BY value DESC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Pie Chart |
| **Format** | Table |
| **Shows** | Time distribution across operating regimes |

---

### 4.3 Current Regime Status
```sql
SELECT TOP 1
    RegimeLabel,
    RegimeState,
    AssignmentConfidence
FROM ACM_RegimeTimeline
WHERE EquipID = $equipment
ORDER BY Timestamp DESC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Stat |
| **Format** | Table |
| **Shows** | Current operating regime with confidence |

---

## 5. RUL & Forecasting

### 5.1 Current RUL Estimate
```sql
SELECT TOP 1
    ROUND(RUL_Hours, 1) AS RUL_Hours,
    ROUND(P10_LowerBound, 1) AS P10_Lower,
    ROUND(P50_Median, 1) AS P50_Median,
    ROUND(P90_UpperBound, 1) AS P90_Upper,
    ROUND(Confidence, 3) AS Confidence,
    Method
FROM ACM_RUL
WHERE EquipID = $equipment
  AND (P10_LowerBound IS NOT NULL OR P50_Median IS NOT NULL)
ORDER BY CreatedAt DESC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Stat / Table |
| **Format** | Table |
| **Shows** | Remaining useful life with confidence bounds |

---

### 5.2 Health Forecast Timeline
```sql
SELECT 
    Timestamp AS time,
    ForecastHealth AS value,
    'Forecast' AS metric
FROM ACM_HealthForecast
WHERE EquipID = $equipment
  AND Timestamp BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY Timestamp ASC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Time Series |
| **Format** | Time series |
| **Shows** | Projected health trajectory into the future |

**Note:** Column is `ForecastHealth` (NOT `ForecastValue`)

---

### 5.3 Health Forecast with Confidence Bands
```sql
SELECT 
    Timestamp AS time,
    ForecastHealth,
    CiLower,
    CiUpper
FROM ACM_HealthForecast
WHERE EquipID = $equipment
  AND Timestamp BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY Timestamp ASC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Time Series with fill between |
| **Format** | Time series |
| **Shows** | Health forecast with uncertainty bounds |

---

### 5.4 Sensor Forecast (Select Sensors)
```sql
SELECT 
    Timestamp AS time,
    ForecastValue,
    CiLower,
    CiUpper,
    SensorName
FROM ACM_SensorForecast
WHERE EquipID = $equipment
  AND SensorName IN ('power_29_avg', 'power_30_avg')
  AND Timestamp BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY Timestamp ASC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Time Series |
| **Format** | Time series |
| **Shows** | Predicted sensor values with uncertainty |

---

## 6. Seasonality Patterns

### 6.1 Detected Seasonal Patterns (Latest Run)
```sql
SELECT 
    SensorName,
    PatternType,
    ROUND(PeriodHours, 1) AS PeriodHours,
    ROUND(Amplitude, 4) AS Amplitude,
    ROUND(Confidence, 3) AS Confidence
FROM ACM_SeasonalPatterns
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID 
      FROM ACM_SeasonalPatterns 
      WHERE EquipID = $equipment 
      ORDER BY ID DESC
  )
  AND Confidence > 0.3
ORDER BY Confidence DESC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Table |
| **Format** | Table |
| **Shows** | Sensors with daily/weekly patterns |

---

## 7. Run History & Diagnostics

### 7.1 Recent ACM Runs
```sql
SELECT TOP 20
    RunID,
    StartedAt,
    CompletedAt,
    DATEDIFF(SECOND, StartedAt, CompletedAt) AS DurationSec,
    Status,
    RowsProcessed
FROM ACM_Runs
WHERE EquipID = $equipment
ORDER BY StartedAt DESC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Table |
| **Format** | Table |
| **Shows** | ACM execution history |
| **Value Mappings** | SUCCESS→Green, NOOP→Gray, FAILED→Red |

---

### 7.2 Run Success Rate (Pie Chart)
```sql
SELECT 
    Status AS metric,
    COUNT(*) AS value
FROM ACM_Runs
WHERE EquipID = $equipment
  AND StartedAt BETWEEN $__timeFrom() AND $__timeTo()
GROUP BY Status
ORDER BY value DESC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Pie Chart |
| **Format** | Table |
| **Shows** | Distribution of run outcomes |

---

## 8. Multi-Equipment Overview

### 8.1 Fleet Health Summary
```sql
SELECT 
    e.EquipCode,
    h.HealthIndex,
    h.HealthZone,
    h.Timestamp AS LastUpdate
FROM ACM_HealthTimeline h
INNER JOIN Equipment e ON h.EquipID = e.EquipID
WHERE h.Timestamp = (
    SELECT MAX(h2.Timestamp) 
    FROM ACM_HealthTimeline h2
    WHERE h2.EquipID = h.EquipID
)
ORDER BY h.HealthIndex ASC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Table |
| **Format** | Table |
| **Shows** | Current health of all equipment (worst first) |
| **Value Mappings** | By HealthZone color |

---

### 8.2 Equipment Comparison - Health Trends
```sql
SELECT 
    h.Timestamp AS time,
    h.HealthIndex AS value,
    e.EquipCode AS metric
FROM ACM_HealthTimeline h
INNER JOIN Equipment e ON h.EquipID = e.EquipID
WHERE h.Timestamp BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY h.Timestamp ASC
```
| Property | Value |
|----------|-------|
| **Chart Type** | Time Series (multi-line) |
| **Format** | Time series |
| **Shows** | Compare health trends across equipment |

---

## Query Summary Table

| # | Query Name | Chart Type | Format | Latest Run? | Time Filter? |
|---|------------|------------|--------|-------------|--------------|
| 1.1 | Current Health | Stat/Gauge | Table | ✅ (TOP 1) | ❌ |
| 1.2 | Health Timeline | Time Series | Time series | ❌ | ✅ |
| 1.3 | Health Zone Distribution | Pie | Table | ❌ | ✅ |
| 2.1 | Detector Scores | Time Series | Time series | ❌ | ✅ |
| 2.2 | Fused Score | Time Series | Time series | ❌ | ✅ |
| 2.3 | Anomaly Episodes | Table | Table | ❌ | ✅ |
| 2.4 | Episode Count | Bar | Time series | ❌ | ✅ |
| 3.1 | Sensor Defects | Table | Table | ✅ | ❌ |
| 3.2 | Sensor Hotspots | Bar | Table | ✅ | ❌ |
| 3.3 | Correlations | Table | Table | ✅ | ❌ |
| 4.1 | Regime Timeline | State Timeline | Time series | ❌ | ✅ |
| 4.2 | Regime Distribution | Pie | Table | ❌ | ✅ |
| 4.3 | Current Regime | Stat | Table | ✅ (TOP 1) | ❌ |
| 5.1 | RUL Estimate | Stat/Table | Table | ✅ (TOP 1) | ❌ |
| 5.2 | Health Forecast | Time Series | Time series | ❌ | ✅ |
| 5.3 | Health Forecast + CI | Time Series | Time series | ❌ | ✅ |
| 5.4 | Sensor Forecast | Time Series | Time series | ❌ | ✅ |
| 6.1 | Seasonal Patterns | Table | Table | ✅ | ❌ |
| 7.1 | Run History | Table | Table | ❌ | ❌ |
| 7.2 | Run Success Rate | Pie | Table | ❌ | ✅ |
| 8.1 | Fleet Health | Table | Table | ✅ | ❌ |
| 8.2 | Equipment Compare | Time Series | Time series | ❌ | ✅ |

---

## Column Reference Quick Guide

| Table | Common Wrong Name | Correct Column Name |
|-------|-------------------|---------------------|
| ACM_HealthTimeline | HealthPercent | **HealthIndex** |
| ACM_HealthForecast | ForecastValue | **ForecastHealth** |
| ACM_RUL | LowerBound | **P10_LowerBound** |
| ACM_RUL | UpperBound | **P90_UpperBound** |
| ACM_Anomaly_Events | TopSensor1 | ❌ Does not exist |
| ACM_RegimeTimeline | RegimeLabel | INTEGER (not text) |

---

## Grafana Value Mappings Reference

### Severity (ACM_Anomaly_Events, ACM_SensorDefects)
| Value | Display | Color |
|-------|---------|-------|
| info | INFO | Green |
| warning | WARNING | Yellow |
| critical | CRITICAL | Red |
| LOW | LOW | Green |
| MEDIUM | MEDIUM | Yellow |
| HIGH | HIGH | Red |

### HealthZone
| Value | Display | Color |
|-------|---------|-------|
| GOOD | GOOD | Green |
| WATCH | WATCH | Yellow |
| ALERT | ALERT | Red |

### RegimeLabel
| Value | Display | Color |
|-------|---------|-------|
| -1 | UNKNOWN | Purple |
| 0 | Normal | Green |
| 1 | High Load | Yellow |
| 2+ | Custom | Various |

### Run Status
| Value | Display | Color |
|-------|---------|-------|
| SUCCESS | SUCCESS | Green |
| NOOP | NOOP | Gray |
| FAILED | FAILED | Red |

---

## Maintenance Notes

- **Update this document** when schema changes
- **Test all queries** after ACM version upgrades
- **Schema Reference**: See `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md`
- **Export Schema**: Run `python scripts/sql/export_comprehensive_schema.py`

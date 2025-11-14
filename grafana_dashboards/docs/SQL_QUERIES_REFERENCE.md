# ACM Dashboard SQL Queries Reference

This document provides the SQL query reference for all panels in the ACM Grafana dashboards:

- **ACM Asset Health Dashboard** (`asset_health_dashboard.json`)
- **ACM Operator View** (`acm_operator_dashboard.json`)

Use this for troubleshooting, customization, or creating derivative dashboards.

## Common Variables

All queries use these Grafana variables:
- `$datasource`: SQL Server data source (auto-selected).
- `$equipment`: Equipment ID (user-selectable).
- `$__timeFrom()`: Start of selected time range.
- `$__timeTo()`: End of selected time range.

Unless stated otherwise, all queries are scoped by `EquipID` and the dashboard time picker.

---

## Executive Summary Panels

Used by both dashboards (with minor label differences).

### 1. Overall Health Score (Gauge / Bar Gauge)
```sql
SELECT TOP 1 HealthIndex
FROM ACM_HealthTimeline
WHERE EquipID = $equipment
ORDER BY Timestamp DESC;
```
**Purpose**: Current health index (0‑100 scale).  
**Expected Result**: Single numeric value.  
**Thresholds**: Red <70, Yellow 70‑84, Green 85‑100.

---

### 2. Current Status (Stat)
```sql
SELECT TOP 1
  CASE
    WHEN HealthIndex >= 85 THEN 'HEALTHY'
    WHEN HealthIndex >= 70 THEN 'CAUTION'
    ELSE 'ALERT'
  END AS Status
FROM ACM_HealthTimeline
WHERE EquipID = $equipment
ORDER BY Timestamp DESC;
```
**Purpose**: Text status badge.  
**Expected Result**: `HEALTHY` / `CAUTION` / `ALERT`.

---

### 3. Days Since Last Alert (Stat)
```sql
SELECT TOP 1
  DATEDIFF(DAY, StartTimestamp, SYSUTCDATETIME()) AS DaysSinceLastAlert
FROM ACM_AlertAge
WHERE EquipID = $equipment;
```
**Purpose**: Days since equipment was last in the ALERT zone.  
**Expected Result**: Integer (days).

> Asset Health Dashboard originally filtered explicitly on `AlertZone = 'ALERT'`; the operator dashboard treats `ACM_AlertAge` as pre‑filtered per zone. Adjust if you store multiple zones.

---

### 4. Active Episodes (Stat)

Asset Health Dashboard (recent episodes from culprit history):
```sql
SELECT COUNT(*) AS ActiveEpisodes
FROM ACM_CulpritHistory
WHERE EquipID = $equipment
  AND (EndTimestamp IS NULL OR EndTimestamp >= DATEADD(HOUR, -24, GETDATE()));
```

Operator View (summary from latest `ACM_EpisodeMetrics`):
```sql
SELECT TOP 1 TotalEpisodes
FROM ACM_EpisodeMetrics
WHERE EquipID = $equipment
ORDER BY RunID DESC;
```
**Purpose**: Episode burden indicator – either active/recent episodes or per‑run totals.

---

### 5. Worst Sensor (Stat)
```sql
SELECT TOP 1
  SensorName AS WorstSensor,
  ROUND(LatestAbsZ, 2) AS CurrentZ
FROM ACM_SensorHotspots
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID
      FROM ACM_SensorHotspots
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
ORDER BY LatestAbsZ DESC;
```
**Purpose**: Highest deviating sensor in the latest run.  
**Expected Result**: Single row with sensor name and current z‑score.

---

### 6. Current Regime (Stat – Asset Health Dashboard)
```sql
SELECT TOP 1
  CONCAT('Regime ', CAST(RegimeLabel AS VARCHAR)) AS CurrentRegime
FROM ACM_RegimeTimeline
WHERE EquipID = $equipment
ORDER BY Timestamp DESC;
```
**Purpose**: Current operating regime label.  
Operator View instead uses the full regime state in the timeline panel (see below).

---

## Health & Regime Panels

### 7. Health Index Timeline (Time Series)

Asset Health Dashboard (health + fused z‑score, latest run):
```sql
SELECT
    Timestamp AS time,
    HealthIndex,
    FusedZ
FROM ACM_HealthTimeline
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID
      FROM ACM_HealthTimeline
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
  AND $__timeFilter(Timestamp)
ORDER BY Timestamp;
```

Operator View (health only, same pattern):
```sql
SELECT
    Timestamp AS time,
    HealthIndex AS [Health Index]
FROM ACM_HealthTimeline
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID
      FROM ACM_HealthTimeline
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
  AND $__timeFilter(Timestamp)
ORDER BY Timestamp;
```
**Purpose**: Health index trend for the latest run, aligned to the dashboard time range.

**Index recommendation**:
```sql
CREATE NONCLUSTERED INDEX IX_ACM_HealthTimeline_EquipTime
ON ACM_HealthTimeline(EquipID, Timestamp)
INCLUDE (HealthIndex, HealthZone, FusedZ);
```

---

### 8. Operating Regime Timeline (State Timeline)

Asset Health Dashboard:
```sql
SELECT
    Timestamp AS time,
    CONCAT('Regime ', CAST(RegimeLabel AS VARCHAR(10))) AS value
FROM ACM_RegimeTimeline
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID
      FROM ACM_RegimeTimeline
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
  AND $__timeFilter(Timestamp)
ORDER BY Timestamp;
```

Operator View (uses `RegimeState` directly as the categorical value):
```sql
SELECT
    Timestamp AS time,
    RegimeState AS value
FROM ACM_RegimeTimeline
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID
      FROM ACM_RegimeTimeline
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
  AND $__timeFilter(Timestamp)
ORDER BY Timestamp;
```
**Purpose**: Visual ribbon of operating modes over time, aligned with the health timeline.

---

## Detector & Sensor Root Cause Panels

### 9. Current Detector Contributions (Bar Chart)

Used in both dashboards (titled “Current Detector Contributions”; `Sensor` wording is legacy).
```sql
SELECT TOP 10
       DetectorType AS detector,
       ContributionPct AS contribution
FROM ACM_ContributionCurrent
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID
      FROM ACM_ContributionCurrent
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
ORDER BY ContributionPct DESC;
```
**Purpose**: Shows which heads/detectors are contributing most to the fused anomaly right now.  
**Expected Result**: Up to 10 rows; one per `DetectorType`.

If you want to surface z‑scores for severity coloring:
```sql
SELECT TOP 10
       DetectorType AS detector,
       ContributionPct AS contribution,
       ZScore
FROM ACM_ContributionCurrent
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID
      FROM ACM_ContributionCurrent
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
ORDER BY ContributionPct DESC;
```

---

### 10. Detector Contributions Over Time (Time Series)

Operator View:
```sql
SELECT
  Timestamp AS time,
  DetectorType AS metric,
  ContributionPct AS value
FROM ACM_ContributionTimeline
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID
      FROM ACM_ContributionTimeline
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
  AND $__timeFilter(Timestamp)
ORDER BY Timestamp, DetectorType;
```
**Purpose**: How each detector’s contribution evolves during the latest run.  
**Visualization**: Multi‑line or stacked area chart (per detector).

For large histories, you can pre‑filter to top N detectors:
```sql
WITH TopHeads AS (
  SELECT TOP 8 DetectorType
  FROM ACM_ContributionCurrent
  WHERE EquipID = $equipment
  ORDER BY ContributionPct DESC
)
SELECT
  ct.Timestamp AS time,
  ct.DetectorType AS metric,
  ct.ContributionPct AS value
FROM ACM_ContributionTimeline ct
JOIN TopHeads th ON th.DetectorType = ct.DetectorType
WHERE ct.EquipID = $equipment
  AND ct.RunID = (
      SELECT TOP 1 RunID
      FROM ACM_ContributionTimeline
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
  AND $__timeFilter(ct.Timestamp)
ORDER BY ct.Timestamp, ct.DetectorType;
```

---

### 11. Sensor Hotspots (Table)

Asset Health Dashboard (includes extra level and time window):
```sql
SELECT
  TOP 20 SensorName        AS [Sensor Name],
         ROUND(LatestAbsZ, 2) AS [Current Z-Score],
         ROUND(MaxAbsZ, 2)    AS [Peak Z-Score],
         MaxTimestamp          AS [Peak Time],
         ROUND(LatestValue, 2) AS [Current Value],
         ROUND(TrainMean, 2)   AS [Normal Mean],
         AboveAlertCount       AS [Alert Count],
         CASE
           WHEN LatestAbsZ >= 3 THEN 'ALERT'
           WHEN LatestAbsZ >= 2 THEN 'WARN'
           ELSE 'NORMAL'
         END AS [Level]
FROM ACM_SensorHotspots
WHERE EquipID = $equipment
  AND MaxTimestamp >= DATEADD(HOUR, -48, GETDATE())
ORDER BY LatestAbsZ DESC;
```

Operator View (simpler, no time filter or level column):
```sql
SELECT TOP 20
       SensorName           AS [Sensor Name],
       ROUND(LatestAbsZ, 2) AS [Current Z-Score],
       ROUND(MaxAbsZ, 2)    AS [Peak Z-Score],
       MaxTimestamp          AS [Peak Time],
       ROUND(LatestValue, 2) AS [Current Value],
       ROUND(TrainMean, 2)   AS [Normal Mean],
       AboveAlertCount       AS [Alert Count]
FROM ACM_SensorHotspots
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID
      FROM ACM_SensorHotspots
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
ORDER BY [Current Z-Score] DESC;
```
**Purpose**: Rank sensors by current deviation and context against baseline.

---

## Diagnostics & Distribution Panels

### 12. Detector Correlation Matrix (Heatmap)
```sql
SELECT
  DetectorA AS detector1,
  DetectorB AS detector2,
  PearsonR  AS correlation
FROM ACM_DetectorCorrelation
WHERE EquipID = $equipment;
```
**Purpose**: Show which detectors agree/disagree (`PearsonR` from ‑1 to +1).  
High correlation = redundant heads; low correlation = complementary heads.

---

### 13. Health Zone Distribution by Period

Asset Health Dashboard (raw rows):
```sql
SELECT
    PeriodStart AS period,
    HealthZone  AS zone,
    ZonePct     AS percentage
FROM ACM_HealthZoneByPeriod
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID
      FROM ACM_HealthZoneByPeriod
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
  AND $__timeFilter(PeriodStart)
ORDER BY PeriodStart, HealthZone;
```

Operator View (pivoted for stacked bar):
```sql
SELECT
    PeriodStart AS period,
    SUM(CASE WHEN HealthZone = 'GOOD'  THEN ZonePct ELSE 0 END) AS GoodPct,
    SUM(CASE WHEN HealthZone = 'WATCH' THEN ZonePct ELSE 0 END) AS WatchPct,
    SUM(CASE WHEN HealthZone = 'ALERT' THEN ZonePct ELSE 0 END) AS AlertPct
FROM ACM_HealthZoneByPeriod
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID
      FROM ACM_HealthZoneByPeriod
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
  AND $__timeFilter(PeriodStart)
GROUP BY PeriodStart
ORDER BY PeriodStart;
```
**Purpose**: For each period, what fraction of time was GOOD/WATCH/ALERT.

---

### 14. Defect Event Timeline (Time Series)

Operator View (recommended):
```sql
SELECT
  Timestamp AS time,
  HealthIndex AS [Health Index],
  FusedZ      AS [Fused Score]
FROM ACM_DefectTimeline
WHERE EquipID = $equipment
  AND RunID = (
      SELECT TOP 1 RunID
      FROM ACM_DefectTimeline
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
  AND $__timeFilter(Timestamp)
ORDER BY Timestamp;
```
**Purpose**: Plot discrete defect events on the same scale as health and fused score.

Asset Health Dashboard may omit the `RunID` filter to show events from multiple runs; for run‑scoped views the filter is recommended.

---

### 15. Episode Metrics (Stat / Table)
```sql
SELECT TOP 1
  TotalEpisodes,
  AvgDurationHours,
  MaxDurationHours,
  RatePerDay,
  MeanInterarrivalHours
FROM ACM_EpisodeMetrics
WHERE EquipID = $equipment
ORDER BY RunID DESC;
```
**Purpose**: Summarise how often and how long anomalies occur.

---

### 16. Regime Occupancy (Pie Chart)
```sql
SELECT
  CONCAT('Regime ', CAST(RegimeLabel AS VARCHAR)) AS regime,
  Percentage AS value
FROM ACM_RegimeOccupancy
WHERE EquipID = $equipment;
```
**Purpose**: How time is distributed across regimes.

---

### 17. Drift Detection (Time Series)
```sql
SELECT
  Timestamp AS time,
  DriftValue AS value
FROM ACM_DriftSeries
WHERE EquipID = $equipment
  AND $__timeFilter(Timestamp)
ORDER BY Timestamp;
```
**Purpose**: Visualise slowly accumulating drift metrics.

---

### 18. Sensor Anomaly Rates by Period (Heatmap)
```sql
SELECT
  PeriodStart AS time,
  DetectorType AS detector,
  AnomalyRatePct AS value
FROM ACM_SensorAnomalyByPeriod
WHERE EquipID = $equipment
  AND $__timeFilter(PeriodStart)
ORDER BY PeriodStart, DetectorType;
```
**Purpose**: Which detectors have high anomaly rates in each period.

---

### 19. Detector Calibration Summary (Table)
```sql
SELECT
  DetectorType      AS [Detector],
  ROUND(MeanZ, 2)   AS [Mean Z],
  ROUND(P95Z, 2)    AS [P95 Z],
  ROUND(P99Z, 2)    AS [P99 Z],
  ROUND(ClipZ, 1)   AS [Clip Threshold],
  ROUND(SaturationPct, 1) AS [Saturation %]
FROM ACM_CalibrationSummary
WHERE EquipID = $equipment;
```
**Purpose**: Calibration quality of each head; helps tune thresholds and identify saturation.

---

### 20. Regime Stability Metrics (Stat / Table)
```sql
SELECT
  MetricName  AS metric,
  ROUND(MetricValue, 2) AS value
FROM ACM_RegimeStability
WHERE EquipID = $equipment;
```
**Purpose**: High‑level summary of regime model stability (e.g., transitions per day, dwell characteristics).

---

## Detector Explanations Panel (Operator View)

The **Detector Explanations** table combines `ACM_SensorDefects` with `ACM_DetectorMetadata` to provide human‑readable descriptions per detector family.

```sql
SELECT
  sd.DetectorType,
  sd.DetectorFamily,
  sd.Severity,
  sd.CurrentZ,
  sd.ViolationPct,
  dm.ShortName,
  dm.Explanation,
  dm.OperatorHint
FROM ACM_SensorDefects sd
LEFT JOIN ACM_DetectorMetadata dm
  ON dm.DetectorFamily = sd.DetectorFamily
WHERE sd.EquipID = $equipment
  AND sd.RunID = (
      SELECT TOP 1 RunID
      FROM ACM_SensorDefects
      WHERE EquipID = $equipment
      ORDER BY RunID DESC
  )
ORDER BY
  CASE sd.Severity
    WHEN 'CRITICAL' THEN 3
    WHEN 'HIGH'     THEN 2
    WHEN 'MEDIUM'   THEN 1
    ELSE 0
  END DESC,
  sd.ViolationPct DESC;
```

**Tables used**:
- `ACM_SensorDefects` – per‑detector severity and violation statistics.
- `ACM_DetectorMetadata` – lookup table with explanations and operator hints (created by `scripts/sql/56_create_detector_metadata.sql`).


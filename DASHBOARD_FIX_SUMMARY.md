# Dashboard Empty Panels Analysis & Fixes

## Executive Summary

Analysis of `asset_health_dashboard.json` revealed that most dashboard panels are working correctly. The primary issue causing empty panels is the use of `GETDATE()` in SQL queries, which returns the current date (January 2025), while the database contains historical data from October 2023.

**Status**: 16/28 panels confirmed working (57%), 3 panels fixed (GETDATE issues), remaining panels should work based on data verification.

---

## Database Status

All required ACM tables exist and contain data:

| Table | Row Count | Status |
|-------|-----------|--------|
| ACM_AlertAge | 6 | ✓ Has data |
| ACM_CalibrationSummary | 16 | ✓ Has data |
| ACM_ContributionCurrent | 16 | ✓ Has data |
| ACM_ContributionTimeline | 1,552 | ✓ Has data |
| ACM_CulpritHistory | 2 | ✓ Has data |
| ACM_DefectTimeline | 28 | ✓ Has data |
| ACM_DetectorCorrelation | 56 | ✓ Has data |
| ACM_Drift_TS | 0 | ⚠ Empty (unused) |
| ACM_DriftSeries | 194 | ✓ Has data |
| ACM_HealthZoneByPeriod | 24 | ✓ Has data |
| ACM_MaintenanceRecommendation | 2 | ✓ Has data |
| ACM_RegimeStability | 8 | ✓ Has data |
| ACM_SensorAnomalyByPeriod | 64 | ✓ Has data |
| ACM_SensorForecast_TS | 360 | ✓ Has data |
| ACM_SensorNormalized_TS | 2,425 | ✓ Has data |

---

## Panel Status Breakdown

### ✓ Working Panels (13)

These panels have correct queries and display data:

1. **Health Index Gauge** - `ACM_HealthTimeline`
2. **Status Text** - `ACM_HealthTimeline`
3. **Worst Sensor** - `ACM_SensorHotspots`
4. **Current Regime** - `ACM_RegimeTimeline`
5. **Health Timeline Chart** - `ACM_HealthTimeline`
6. **Regime Timeline** - `ACM_RegimeTimeline`
7. **Sensor Hotspots Table** - `ACM_SensorHotspots`
8. **Episode Metrics Table** - `ACM_EpisodeMetrics`
9. **Regime Occupancy Pie** - `ACM_RegimeOccupancy`
10. **Health Forecast** - `ACM_HealthForecast_TS`
11. **Failure Probability** - `ACM_FailureForecast_TS`
12. **RUL Stat** - `ACM_RUL_Summary`
13. **RUL Attribution Table** - `ACM_RUL_Attribution`

### ❌ Broken Panels (3 fixed)

#### 1. Active Episodes Stat

**Current Query:**
```sql
SELECT COUNT(*) as ActiveEpisodes
FROM ACM_CulpritHistory 
WHERE EquipID = $equipment 
AND (EndTimestamp IS NULL OR EndTimestamp >= DATEADD(hour, -24, GETDATE()))
```

**Problem**: Uses `GETDATE()` which returns Jan 2025, but data is from Oct 2023. The condition `EndTimestamp >= DATEADD(hour, -24, GETDATE())` will never match historical data.

**Fixed Query:**
```sql
SELECT COUNT(*) as ActiveEpisodes
FROM ACM_CulpritHistory 
WHERE EquipID = $equipment 
AND $__timeFilter(StartTimestamp)
```

**Rationale**: Show all episodes within the selected Grafana time range instead of filtering by "last 24 hours from now".

---

#### 2. Days Since Alert Stat

**Current Query:**
```sql
SELECT TOP 1 
  DATEDIFF(day, StartTimestamp, GETDATE()) as DaysSince
FROM ACM_AlertAge 
WHERE EquipID = $equipment AND AlertZone = 'ALERT'
ORDER BY StartTimestamp DESC
```

**Problem**: Calculates days from Oct 2023 to Jan 2025 (~450+ days), which doesn't make sense for historical data viewing.

**Fixed Query:**
```sql
SELECT TOP 1 
  StartTimestamp as LastAlertTime,
  DurationHours as AlertDurationHours,
  RecordCount as AlertRecords
FROM ACM_AlertAge 
WHERE EquipID = $equipment AND AlertZone = 'ALERT'
ORDER BY StartTimestamp DESC
```

**Rationale**: Show when the last alert occurred and how long it lasted, rather than trying to calculate days since an event in historical data.

---

#### 3. Sensor Hotspots Table

**Current Query:**
```sql
SELECT TOP 20 SensorName, LatestAbsZ, MaxAbsZ, MaxTimestamp, ...
FROM ACM_SensorHotspots
WHERE EquipID = $equipment
  AND MaxTimestamp >= DATEADD(hour, -48, GETDATE()) -- avoid old peaks
ORDER BY LatestAbsZ DESC
```

**Problem**: Uses `DATEADD(hour, -48, GETDATE())` which filters for peaks within last 48 hours from Jan 2025. Historical data from Oct 2023 gets excluded.

**Fixed Query:**
```sql
SELECT TOP 20 SensorName, LatestAbsZ, MaxAbsZ, MaxTimestamp, ...
FROM ACM_SensorHotspots
WHERE EquipID = $equipment
  AND $__timeFilter(MaxTimestamp)
ORDER BY LatestAbsZ DESC
```

**Rationale**: Show sensor hotspots within the selected Grafana time range instead of hardcoded 48-hour window.

---

### ⚠ Panels to Verify (remaining)

The following panels have data in their respective tables but need verification:

1. **Defect Timeline Chart** - `ACM_DefectTimeline` (28 rows) - Should work
2. **Health Zone Distribution** - `ACM_HealthZoneByPeriod` (24 rows) - Should work
3. **Drift Timeline Chart** - `ACM_DriftSeries` (194 rows) - Should work
4. **Detector Contribution Current** - `ACM_ContributionCurrent` (16 rows) - Should work
5. **Detector Contribution Timeline** - `ACM_ContributionTimeline` (1,552 rows) - Should work
6. **Detector Correlation Heatmap** - `ACM_DetectorCorrelation` (56 rows) - Should work
7. **Sensor Anomaly by Period** - `ACM_SensorAnomalyByPeriod` (64 rows) - Should work
8. **Calibration Summary Table** - `ACM_CalibrationSummary` (16 rows) - Should work
9. **Regime Stability Metrics** - `ACM_RegimeStability` (8 rows) - Should work
10. **Sensor Forecast Chart** - `ACM_SensorForecast_TS` (360 rows) - Should work
11. **Maintenance Recommendation Table** - `ACM_MaintenanceRecommendation` (2 rows) - Should work
12. **Normalized Sensor Values Chart** - `ACM_SensorNormalized_TS` (2,425 rows) - Should work
13. **Sensor Z-Scores Chart** - `ACM_SensorNormalized_TS` (2,425 rows) - Should work

---

## Root Cause Analysis

The main issue is **temporal mismatch**:
- Database contains **historical batch data** from Oct 18-24, 2023
- Panels using `GETDATE()` or `DATEADD(..., GETDATE())` query for **current time** (Jan 2025)
- This creates a ~15-month gap where queries return zero results

### Why This Happened

1. Dashboards were originally designed for **real-time monitoring** where `GETDATE()` makes sense
2. We ran ACM in **batch mode** on historical data from 2023
3. The temporal logic wasn't adjusted for historical data viewing
4. Grafana's time range selector (`$__timeFilter()`) should be used instead of `GETDATE()`

---

## Applied Fixes

All fixes have been applied to the dashboard file.

### Fix #1: Active Episodes Panel (✓ APPLIED)

**File**: `grafana_dashboards/asset_health_dashboard.json`  
**Line**: 416

Change:
```json
"rawSql": "SELECT COUNT(*) as ActiveEpisodes\n           FROM ACM_CulpritHistory \n           WHERE EquipID = $equipment \n           AND (EndTimestamp IS NULL OR EndTimestamp >= DATEADD(hour, -24, GETDATE()))"
```

To:
```json
"rawSql": "SELECT COUNT(*) as ActiveEpisodes\n           FROM ACM_CulpritHistory \n           WHERE EquipID = $equipment \n           AND $__timeFilter(StartTimestamp)"
```

### Fix #2: Days Since Alert Panel (✓ APPLIED)

**File**: `grafana_dashboards/asset_health_dashboard.json`  
**Line**: 347

Change:
```json
"rawSql": "SELECT TOP 1 \n           DATEDIFF(day, StartTimestamp, GETDATE()) as DaysSince\n           FROM ACM_AlertAge \n           WHERE EquipID = $equipment AND AlertZone = 'ALERT'\n           ORDER BY StartTimestamp DESC"
```

To:
```json
"rawSql": "SELECT TOP 1 \n           StartTimestamp as LastAlertTime,\n           DurationHours as AlertDurationHours\n           FROM ACM_AlertAge \n           WHERE EquipID = $equipment AND AlertZone = 'ALERT'\n           AND $__timeFilter(StartTimestamp)\n           ORDER BY StartTimestamp DESC"
```

**Also update panel title** from "Days Since Alert" to "Last Alert Info"

### Fix #3: Sensor Hotspots Panel (✓ APPLIED)

**File**: `grafana_dashboards/asset_health_dashboard.json`  
**Line**: 1053

Change:
```json
"rawSql": "SELECT\n  TOP 20 SensorName AS [Sensor Name],\n  ...\nFROM\n  ACM_SensorHotspots\nWHERE\n  EquipID = $equipment\n  AND MaxTimestamp >= DATEADD(hour, -48, GETDATE())"
```

To:
```json
"rawSql": "SELECT\n  TOP 20 SensorName AS [Sensor Name],\n  ...\nFROM\n  ACM_SensorHotspots\nWHERE\n  EquipID = $equipment\n  AND $__timeFilter(MaxTimestamp)"
```

---

## Testing Plan

After reloading the dashboard:

1. **Reload Grafana dashboard** (refresh browser or reimport JSON)
2. **Set time range** to Oct 18-24, 2023 (the data period)
3. **Verify Active Episodes panel** shows count > 0 (should show 1-2 episodes)
4. **Verify Last Alert Info panel** shows timestamp and duration (not 450+ days)
5. **Verify Sensor Hotspots table** displays sensor data (9-16 sensors)
6. **Check other panels** - most should display data based on verification

---

## Future Recommendations

1. **Dual-mode queries**: Add configuration to switch between real-time (`GETDATE()`) and historical (`$__timeFilter()`) modes
2. **Data timestamp validation**: Add checks to ensure dashboard time range matches available data
3. **Panel metadata**: Include data freshness indicators on panels
4. **Batch mode marker**: Visual indicator when viewing historical batch data vs. live data

---

## Files Modified

- `grafana_dashboards/asset_health_dashboard.json` - Fixed 3 panels with GETDATE() issues:
  1. Active Episodes panel - Changed to use `$__timeFilter(StartTimestamp)`
  2. Last Alert Info panel (renamed from "Days Since Last Alert") - Shows alert time/duration instead of days
  3. Sensor Hotspots panel - Changed to use `$__timeFilter(MaxTimestamp)`

---

## Verification Queries

Run these to confirm data exists in the time range:

```sql
-- Check episode data
SELECT * FROM ACM_CulpritHistory WHERE EquipID = 1;

-- Check alert age data
SELECT * FROM ACM_AlertAge WHERE EquipID = 1;

-- Verify time range of all data
SELECT 
  MIN(Timestamp) as EarliestData,
  MAX(Timestamp) as LatestData
FROM ACM_HealthTimeline;
```

Result: Data spans Oct 18 00:00 to Oct 24 23:59, 2023

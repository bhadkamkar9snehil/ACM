# ACM Asset Health Dashboard - Charting Philosophy

## Purpose
This document defines the storytelling approach and visualization strategy for presenting ACM (Autonomous Condition Monitoring) analytics to non-expert operators. The goal is to transform complex ML-based condition monitoring outputs into an intuitive, actionable narrative that answers key operational questions.

## Target Audience
- **Primary**: Operations personnel and plant operators (non-ML experts)
- **Secondary**: Maintenance engineers, reliability engineers
- **Tertiary**: Management and executives (high-level health overview)

## Core Principle: Tell a Story, Not Just Data
The dashboard should answer the operator's natural progression of questions:
1. **"Is my equipment healthy?"** → Current health status and trend
2. **"What's happening?"** → Active episodes, anomalies, and alerts
3. **"Why is this happening?"** → Root cause attribution (sensor contributions)
4. **"Has this happened before?"** → Historical context and patterns
5. **"What should I do?"** → Actionable insights and severity levels

---

## Visualization Hierarchy

### Level 1: Executive Summary (Top of Dashboard)
**Purpose**: Instant situational awareness - understand equipment state in <5 seconds

**Components**:
- **Overall Health Score**: Large gauge/stat panel (0-100 scale)
  - Color-coded: Green (85-100 GOOD), Yellow (70-84 WATCH), Red (<70 ALERT)
  - Single number with trend indicator (↑↓→)
  
- **Current Status Badge**: Text panel with semantic meaning
  - "HEALTHY - All Systems Normal"
  - "CAUTION - Elevated Anomaly Activity"
  - "ALERT - Immediate Attention Required"
  
- **Key Metrics Row**: 4-6 stat panels showing:
  - Days since last alert
  - Active anomaly episodes (count)
  - Worst sensor deviation (name + z-score)
  - Current operating regime
  - Time in current health zone

**Data Sources**:
- `ACM_HealthTimeline` (latest row for current health)
- `ACM_Episodes` (count where end_ts is NULL or recent)
- `ACM_SensorHotspots` (top sensor by MaxAbsZ)
- `ACM_RegimeTimeline` (latest regime)
- `ACM_AlertAge` (current zone duration)

---

### Level 2: Health Timeline & Context (Upper-Middle)
**Purpose**: Show the journey - where we've been, where we are, where we're heading

**Components**:

#### A. Health Index Timeline (Primary Chart)
- **Type**: Time series with filled area
- **Y-Axis**: Health index (0-100)
- **Color Fill**: Gradient based on zones
  - Green fill above 85
  - Yellow fill 70-85
  - Red fill below 70
- **Overlay**: Background shading for health zones
- **Annotations**: Mark significant events (threshold crossings, regime changes)
- **Time Range**: Default last 30 days, adjustable via dashboard variable

**Query**: `SELECT Timestamp, HealthIndex, HealthZone, FusedZ FROM ACM_HealthTimeline WHERE EquipID = $equipment ORDER BY Timestamp`

#### B. Operating Regime Ribbon (Below Health Timeline)
- **Type**: State timeline / discrete values over time
- **Display**: Colored horizontal bars showing regime transitions
- **Colors**: Distinct color per regime (auto-assigned or configured)
- **Tooltip**: Regime label, state (healthy/degraded/faulty), duration
- **Purpose**: Correlate health changes with operating mode changes

**Query**: `SELECT Timestamp, RegimeLabel, RegimeState FROM ACM_RegimeTimeline WHERE EquipID = $equipment ORDER BY Timestamp`

#### C. Episode Markers
- **Type**: Overlay annotations on health timeline
- **Display**: Vertical spans or markers at episode start/end
- **Color**: Severity-based (low=yellow, medium=orange, high=red, critical=dark red)
- **Tooltip**: Episode ID, duration, peak z-score, primary culprit
- **Purpose**: Identify anomaly events and their context

**Query**: `SELECT StartTimestamp, EndTimestamp, Severity, PrimaryDetector FROM ACM_CulpritHistory WHERE EquipID = $equipment`

---

### Level 3: Root Cause Analysis (Middle Section)
**Purpose**: Answer "What's causing the problem?"

**Components**:

#### A. Current Sensor Contributions (Bar Chart)
- **Type**: Horizontal bar chart, sorted by contribution
- **X-Axis**: Contribution percentage (0-100%)
- **Y-Axis**: Sensor names
- **Color**: Bars colored by severity (z-score thresholds)
  - Green: z < 2.0 (normal)
  - Yellow: 2.0 ≤ z < 2.5 (watch)
  - Orange: 2.5 ≤ z < 3.0 (alert)
  - Red: z ≥ 3.0 (critical)
- **Limit**: Top 10-15 sensors
- **Tooltip**: Sensor name, contribution %, z-score, current value

**Query**: `SELECT TOP 15 DetectorType, ContributionPct, ZScore FROM ACM_ContributionCurrent WHERE EquipID = $equipment ORDER BY ContributionPct DESC`

#### B. Sensor Contributions Over Time (Stacked Area)
- **Type**: Stacked area chart
- **Y-Axis**: Contribution percentage (0-100%)
- **Series**: Top 5-8 contributing sensors
- **Colors**: Distinct palette per sensor
- **Purpose**: Show how blame shifts over time
- **Tooltip**: Timestamp, sensor, contribution %, cumulative %

**Query**: `SELECT Timestamp, DetectorType, ContributionPct FROM ACM_ContributionTimeline WHERE EquipID = $equipment AND Timestamp >= $__timeFrom AND Timestamp <= $__timeTo ORDER BY Timestamp`

#### C. Sensor Hotspots Table
- **Type**: Sortable table
- **Columns**:
  - Sensor Name
  - Current z-score (colored cell based on severity)
  - Peak z-score (all-time or time window)
  - Timestamp of peak
  - Current value vs normal range
  - Alert/warn violation counts
- **Sorting**: Default by current z-score descending
- **Purpose**: Identify persistent problem sensors

**Query**: `SELECT TOP 20 SensorName, LatestAbsZ, MaxAbsZ, MaxTimestamp, LatestValue, TrainMean, TrainStd, AboveAlertCount FROM ACM_SensorHotspots WHERE EquipID = $equipment ORDER BY LatestAbsZ DESC`

---

### Level 4: Detailed Diagnostics (Lower-Middle Section)
**Purpose**: Deep dive into specific anomaly characteristics

**Components**:

#### A. Detector Performance Matrix (Heatmap)
- **Type**: Heatmap or correlation matrix
- **Purpose**: Show which detectors are firing together
- **Axes**: Detector types (PCA, Mahalanobis, IForest, etc.)
- **Cell Color**: Correlation strength (-1 to +1)
- **Insight**: High correlation = redundant detectors; Low = orthogonal detection

**Query**: `SELECT DetectorA, DetectorB, PearsonR FROM ACM_DetectorCorrelation WHERE EquipID = $equipment`

#### B. Health Zone Distribution (Stacked Bar)
- **Type**: Stacked bar chart by time period (daily/weekly)
- **Y-Axis**: Percentage of time (0-100%)
- **Stack Colors**: Green (GOOD), Yellow (WATCH), Red (ALERT)
- **X-Axis**: Date/week
- **Purpose**: Trend analysis - are we getting better or worse?

**Query**: `SELECT PeriodStart, HealthZone, ZonePct FROM ACM_HealthZoneByPeriod WHERE EquipID = $equipment ORDER BY PeriodStart`

#### C. Defect Timeline (Event Markers)
- **Type**: Timeline with event markers
- **Events**: Zone transitions, threshold crossings, defect incidents
- **Color**: Event type based coloring
- **Tooltip**: Event details, from/to states, z-score at event
- **Purpose**: Understand event sequence and patterns

**Query**: `SELECT Timestamp, EventType, FromZone, ToZone, HealthIndex, FusedZ FROM ACM_DefectTimeline WHERE EquipID = $equipment ORDER BY Timestamp`

---

### Level 5: Historical Context & Patterns (Lower Section)
**Purpose**: "Has this happened before?" and trend analysis

**Components**:

#### A. Episode Metrics Summary (Stat Panels)
- **Type**: Single-stat panels in a row
- **Metrics**:
  - Total episodes (time range)
  - Average episode duration
  - Longest episode
  - Episodes per day rate
  - Mean inter-arrival time
- **Purpose**: Understand failure frequency and patterns

**Query**: `SELECT TotalEpisodes, AvgDurationHours, MaxDurationHours, RatePerDay, MeanInterarrivalHours FROM ACM_EpisodeMetrics WHERE EquipID = $equipment`

#### B. Regime Occupancy Distribution (Pie/Donut Chart)
- **Type**: Pie or donut chart
- **Slices**: Operating regimes
- **Size**: Percentage of time in each regime
- **Colors**: Distinct per regime
- **Tooltip**: Regime name, percentage, record count, avg health in regime

**Query**: `SELECT RegimeLabel, Percentage FROM ACM_RegimeOccupancy WHERE EquipID = $equipment`

#### C. Drift Detection Timeline
- **Type**: Time series line chart
- **Y-Axis**: Drift statistic (CUSUM or drift index)
- **Threshold Line**: Horizontal line at drift detection threshold (e.g., 3.0)
- **Color**: Red when above threshold, blue when below
- **Purpose**: Detect slow baseline shifts vs acute anomalies
- **Annotations**: Mark drift events

**Query**: `SELECT Timestamp, DriftValue FROM ACM_DriftSeries WHERE EquipID = $equipment ORDER BY Timestamp`

#### D. Sensor Anomaly Rates by Period (Heatmap)
- **Type**: Heatmap
- **X-Axis**: Time period (days)
- **Y-Axis**: Sensors/detectors
- **Cell Color**: Anomaly rate percentage (0-100%)
- **Purpose**: Identify chronic vs intermittent problems

**Query**: `SELECT PeriodStart, DetectorType, AnomalyRatePct FROM ACM_SensorAnomalyByPeriod WHERE EquipID = $equipment ORDER BY PeriodStart, DetectorType`

---

### Level 6: Calibration & System Health (Bottom Section)
**Purpose**: ML model quality and trust indicators for advanced users

**Components**:

#### A. Detector Calibration Summary (Table)
- **Type**: Simple table
- **Columns**:
  - Detector name
  - Mean z-score
  - P95/P99 z-scores
  - Clip threshold
  - Saturation % (how often clipping occurs)
- **Purpose**: Show if detectors are well-calibrated or saturating
- **Alert**: Highlight rows where saturation > 10%

**Query**: `SELECT DetectorType, MeanZ, P95Z, P99Z, ClipZ, SaturationPct FROM ACM_CalibrationSummary WHERE EquipID = $equipment`

#### B. Regime Stability Metrics (Stat Panels)
- **Type**: Stat panels
- **Metrics**:
  - Regime churn rate (transitions per unit time)
  - Average dwell time
  - Regime stability score
- **Purpose**: Indicate if regime detection is stable or noisy

**Query**: `SELECT MetricName, MetricValue FROM ACM_RegimeStability WHERE EquipID = $equipment`

---

## Color Palette & Semantic Meaning

### Health Zones
- **GOOD (85-100)**: `#10b981` (green)
- **WATCH (70-84)**: `#f59e0b` (amber/yellow)
- **ALERT (<70)**: `#dc2626` (red)

### Severity Levels
- **INFO/LOW**: `#10b981` (green)
- **MEDIUM/WARNING**: `#f59e0b` (amber)
- **HIGH**: `#f97316` (orange)
- **CRITICAL**: `#dc2626` (red)

### Detector Types (Consistent Colors)
- **Fused Score**: `#3b82f6` (blue) - primary indicator
- **Mahalanobis**: `#8b5cf6` (purple)
- **PCA SPE**: `#ec4899` (pink)
- **PCA T²**: `#f472b6` (light pink)
- **IForest**: `#14b8a6` (teal)
- **GMM**: `#06b6d4` (cyan)
- **AR1**: `#84cc16` (lime)
- **OMR**: `#fb923c` (light orange)

---

## Dashboard Variables

### Required Variables
1. **$equipment** (multi-select): Equipment ID or name
   - Default: All or single asset
   - Source: Query from equipment master table or EquipID list

2. **$time_range** (time range picker): Dashboard time window
   - Default: Last 30 days
   - Presets: Last 24h, 7d, 30d, 90d, 1y

3. **$refresh_interval** (dropdown): Auto-refresh rate
   - Options: Off, 30s, 1m, 5m, 15m
   - Default: 5m for live monitoring

### Optional Variables
4. **$health_zone** (multi-select): Filter by health zone
   - Options: GOOD, WATCH, ALERT
   - Default: All

5. **$regime** (multi-select): Filter by operating regime
   - Source: Query distinct regimes for selected equipment
   - Default: All

6. **$detector_type** (multi-select): Filter specific detectors
   - Options: fused, mhal, pca_spe, iforest, etc.
   - Default: fused

---

## Query Optimization Guidelines

1. **Use WHERE Clauses**: Always filter by EquipID and time range
   ```sql
   WHERE EquipID = $equipment 
     AND Timestamp >= $__timeFrom 
     AND Timestamp <= $__timeTo
   ```

2. **Limit Result Sets**: Use TOP N for ranked results
   ```sql
   SELECT TOP 20 ... ORDER BY ContributionPct DESC
   ```

3. **Pre-aggregate When Possible**: Leverage existing aggregate tables
   - Use `ACM_HealthZoneByPeriod` instead of computing from raw scores
   - Use `ACM_EpisodeMetrics` for summary stats

4. **Index Hints**: Ensure queries use indexes on (EquipID, Timestamp)

5. **Avoid SELECT ***: Only fetch needed columns

6. **Consider Caching**: Enable Grafana query caching for slower queries (>5s)

---

## Interactivity & Drill-Down

### Click Actions
1. **Health Timeline**: Click on time point → update panels to show state at that moment
2. **Sensor Contribution Bar**: Click sensor → show detailed sensor timeline
3. **Episode Marker**: Click episode → show episode detail panel with culprit breakdown
4. **Regime Ribbon**: Click regime → show regime-specific metrics

### Annotations
- **Episode boundaries**: Vertical spans showing anomaly periods
- **Threshold crossings**: Markers when fused z-score crosses 2.0, 2.5, 3.0
- **Drift events**: Markers when drift detected
- **Regime transitions**: Markers when regime changes

---

## Panel Layout Strategy

### Responsive Grid (24 columns)
```
┌──────────────────────────────────────────────────────┐
│  Row 1: Executive Summary (24 cols x 6 rows)         │
│  [Health Gauge] [Status] [Days] [Episodes] [Sensor]  │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  Row 2: Health Timeline (24 cols x 8 rows)           │
│  [Health Index Time Series with Zone Fills]          │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  Row 3: Regime Ribbon (24 cols x 3 rows)             │
│  [Operating Regime State Timeline]                   │
└──────────────────────────────────────────────────────┘
┌────────────────────┬─────────────────────────────────┐
│  Row 4: Root Cause                                    │
│  Col A (8 cols):   │  Col B (16 cols x 8 rows):     │
│  [Current Contrib] │  [Contrib Timeline Stacked]    │
│   Bar Chart        │                                 │
└────────────────────┴─────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  Row 5: Sensor Hotspots Table (24 cols x 6 rows)     │
│  [Sortable Table with Z-score color cells]           │
└──────────────────────────────────────────────────────┘
┌────────────────────┬─────────────────────────────────┐
│  Row 6: Diagnostics                                   │
│  Col A (12 cols):  │  Col B (12 cols):              │
│  [Detector Corr]   │  [Health Zone Distribution]    │
│   Heatmap          │   Stacked Bar                  │
└────────────────────┴─────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  Row 7: Defect Timeline (24 cols x 6 rows)           │
│  [Event Timeline with Markers]                       │
└──────────────────────────────────────────────────────┘
┌────────────────────┬─────────────────┬───────────────┐
│  Row 8: Historical Context (24 cols)                  │
│  Col A (8 cols):   │  Col B (8 cols):│  Col C (8):  │
│  [Episode Stats]   │  [Regime Pie]   │  [Drift TS]  │
└────────────────────┴─────────────────┴───────────────┘
┌──────────────────────────────────────────────────────┐
│  Row 9: Sensor Anomaly Heatmap (24 cols x 8 rows)    │
│  [Time vs Sensor Anomaly Rate Heatmap]               │
└──────────────────────────────────────────────────────┘
┌────────────────────┬─────────────────────────────────┐
│  Row 10: Calibration (24 cols)                        │
│  Col A (16 cols):  │  Col B (8 cols):               │
│  [Calibration Tbl] │  [Regime Stability Stats]      │
└────────────────────┴─────────────────────────────────┘
```

---

## Operator Workflow Examples

### Scenario 1: Morning Health Check
1. Open dashboard → see overall health gauge (GREEN = good to go)
2. Check "Days since last alert" stat (e.g., 14 days = stable)
3. Scan health timeline for any recent yellow/red zones
4. ✅ All clear → proceed with operations

### Scenario 2: Active Alert Investigation
1. Open dashboard → see health gauge RED, status "ALERT"
2. Health timeline shows sharp drop 2 hours ago
3. Scroll to "Current Sensor Contributions" bar chart
   - See "BEARING_TEMP_01" at 65% contribution, z-score 4.2 (red)
4. Click on sensor → drill down to sensor-specific dashboard
5. Check "Sensor Hotspots Table" → see elevated bearing temp values
6. Cross-reference with "Defect Timeline" → see this is a new event
7. 📞 Call maintenance team: "Bearing temperature anomaly detected, investigate BEARING_TEMP_01"

### Scenario 3: Trend Analysis for Preventive Maintenance
1. Set time range to last 90 days
2. Check "Health Zone Distribution" stacked bar
   - Notice increasing % of time in WATCH zone over past month
3. Check "Sensor Contributions Over Time" stacked area
   - See VIBRATION sensors increasing contribution
4. Review "Episode Metrics" → episodes becoming more frequent
5. 🔧 Schedule preventive maintenance before full failure

---

## Implementation Notes

### SQL Server Configuration
- Ensure all ACM tables have clustered indexes on (EquipID, Timestamp)
- Consider partitioning large tables (ACM_Scores_Wide, ACM_ContributionTimeline) by month
- Create indexed views for common aggregations if query performance < 2s

### Grafana Panel Recommendations
- **Health Timeline**: Use "Time series" panel with gradient area fill
- **Regime Ribbon**: Use "State timeline" panel (Grafana 8.0+)
- **Contribution Bars**: Use "Bar chart" panel (horizontal orientation)
- **Heatmaps**: Use "Heatmap" panel with appropriate color scheme
- **Tables**: Use "Table" panel with cell color overrides based on value thresholds

### Alert Rules (Optional)
Create Grafana alerts for:
1. Health index < 70 for > 1 hour
2. Episode duration > 24 hours
3. Sensor z-score > 4.0 (critical threshold)
4. Drift detected (drift flag = 1)

### Data Refresh Strategy
- **Real-time mode**: 1-5 minute refresh for live monitoring
- **Historical analysis**: No auto-refresh, on-demand updates
- **Cache strategy**: 5-minute cache for expensive queries

---

## Success Metrics
A successful dashboard implementation means:
1. **Operator can assess health in <10 seconds** without ML knowledge
2. **Root cause identified in <2 minutes** for active anomalies
3. **No false positives** due to misinterpreted visualizations
4. **Actionable insights** lead to maintenance actions, not just alerts
5. **Trust in system** - operators understand why ACM flagged an issue

---

## Maintenance & Evolution
- **Review quarterly**: Update based on operator feedback
- **Add panels as needed**: New detectors → new contribution panels
- **Simplify, don't complexify**: Remove panels that aren't used
- **Version control**: Store dashboard JSON in git (this repo)
- **Document changes**: Update this philosophy doc with lessons learned

---

## References
- ACM SQL Tables: `core/output_manager.py` (ALLOWED_TABLES)
- Table Schemas: `docs/CHART_TABLES_SPEC.md`
- Analytics Backbone: `docs/Analytics Backbone.md`
- SQL Schema Design: `docs/SQL_SCHEMA_DESIGN.md`

---

**Last Updated**: 2025-11-13
**Version**: 1.0
**Author**: ACM Team

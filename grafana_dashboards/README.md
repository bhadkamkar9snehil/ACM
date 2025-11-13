# ACM Grafana Dashboards

This folder contains production-ready Grafana dashboards for visualizing ACM (Autonomous Condition Monitoring) analytics and asset health data stored in SQL Server.

## Overview

The ACM system generates comprehensive condition monitoring data across ~30 SQL tables covering:
- **Health metrics**: Overall equipment health index, zones (GOOD/WATCH/ALERT)
- **Episodes**: Anomaly detection events with duration and severity
- **Sensor analysis**: Contribution analysis, hotspots, and anomaly rates
- **Regimes**: Operating mode detection and transitions
- **Drift detection**: Baseline shift identification
- **Calibration**: ML model quality metrics

These dashboards transform this technical data into operator-friendly visualizations that tell a clear story about equipment condition.

## Available Dashboards

### 1. Asset Health Dashboard (`asset_health_dashboard.json`)

**Purpose**: Comprehensive asset condition monitoring dashboard for operations personnel

**Target Audience**: Plant operators, maintenance engineers, reliability engineers (non-ML experts)

**Key Features**:
- **Executive Summary**: Instant health status with gauge, current status badge, key metrics
- **Health Timeline**: 30-day health index trend with zone coloring and episode annotations
- **Root Cause Analysis**: Current and historical sensor contribution charts
- **Sensor Hotspots**: Sortable table of problem sensors with z-scores
- **Regime Analysis**: Operating mode timeline and occupancy distribution
- **Defect Tracking**: Event timeline with zone transitions and threshold crossings
- **Historical Context**: Episode statistics, drift detection, anomaly heatmaps
- **Calibration Metrics**: Detector performance and system health indicators

**Dashboard Structure**:
```
┌─────────────────────────────────────────────────┐
│ Executive Summary (6 panels)                     │
│ [Health Gauge] [Status] [Days] [Episodes]       │
│ [Worst Sensor] [Current Regime]                 │
├─────────────────────────────────────────────────┤
│ Health Index Timeline (time series)             │
├─────────────────────────────────────────────────┤
│ Regime Ribbon (state timeline)                  │
├────────────────┬────────────────────────────────┤
│ Current Sensor │ Sensor Contributions Over Time │
│ Contributions  │ (stacked area chart)           │
│ (bar chart)    │                                │
├────────────────┴────────────────────────────────┤
│ Sensor Hotspots Table                           │
├────────────────┬────────────────────────────────┤
│ Detector       │ Health Zone Distribution       │
│ Correlation    │ (stacked bar)                  │
├────────────────┴────────────────────────────────┤
│ Defect Event Timeline (time series markers)     │
├─────────────┬──────────────┬───────────────────┤
│ Episode     │ Regime       │ Drift Detection   │
│ Metrics     │ Occupancy    │ (time series)     │
├─────────────────────────────────────────────────┤
│ Sensor Anomaly Rates Heatmap                    │
├──────────────────────┬──────────────────────────┤
│ Detector Calibration │ Regime Stability Metrics │
│ Table                │ (stat panels)            │
└──────────────────────┴──────────────────────────┘
```

**SQL Tables Used**:
- `ACM_HealthTimeline` - Health index over time
- `ACM_Episodes` - Anomaly episodes
- `ACM_SensorHotspots` - Top problem sensors
- `ACM_ContributionCurrent` - Current sensor contributions
- `ACM_ContributionTimeline` - Historical contributions
- `ACM_RegimeTimeline` - Operating regime over time
- `ACM_RegimeOccupancy` - Regime time distribution
- `ACM_DefectTimeline` - Health zone transitions
- `ACM_DriftSeries` / `ACM_DriftEvents` - Drift detection
- `ACM_HealthZoneByPeriod` - Aggregated health zones
- `ACM_SensorAnomalyByPeriod` - Aggregated anomaly rates
- `ACM_DetectorCorrelation` - Detector relationships
- `ACM_CalibrationSummary` - Detector calibration metrics
- `ACM_EpisodeMetrics` - Episode statistics
- `ACM_CulpritHistory` - Episode-level root cause
- `ACM_AlertAge` / `ACM_SinceWhen` - Alert duration tracking
- `ACM_RegimeStability` - Regime stability metrics

## Installation & Setup

### Prerequisites
1. **Grafana**: Version 9.0+ (recommended: 10.0+)
2. **SQL Server Data Source**: Configured in Grafana pointing to your ACM database
3. **SQL Server**: ACM tables populated by ACM pipeline
4. **Permissions**: Data source user needs SELECT permissions on all `ACM_*` tables

### Step 1: Configure SQL Server Data Source

1. In Grafana, navigate to **Configuration** → **Data Sources**
2. Click **Add data source** → select **Microsoft SQL Server**
3. Configure connection:
   ```
   Name: ACM-SQL (or your preferred name)
   Host: your-sql-server:1433
   Database: your_acm_database
   User: acm_reader (recommended: read-only user)
   Password: ********
   ```
4. Enable **TLS/SSL** if required by your SQL Server setup
5. Click **Save & Test** to verify connection

### Step 2: Import Dashboard

#### Method 1: Via Grafana UI (Recommended)
1. In Grafana, navigate to **Dashboards** → **Import**
2. Click **Upload JSON file**
3. Select `asset_health_dashboard.json` from this folder
4. On the import screen:
   - **Folder**: Select or create "ACM Dashboards" folder
   - **Datasource**: Select your ACM SQL Server data source
   - **UID**: Keep as `acm-asset-health` or customize
5. Click **Import**

#### Method 2: Via Grafana API
```bash
# Using curl (replace placeholders)
curl -X POST \
  -H "Authorization: Bearer YOUR_GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @asset_health_dashboard.json \
  http://your-grafana-instance/api/dashboards/db
```

#### Method 3: Provisioning (for automated deployments)
1. Copy `asset_health_dashboard.json` to Grafana provisioning folder:
   ```bash
   cp asset_health_dashboard.json /etc/grafana/provisioning/dashboards/
   ```
2. Create provisioning config (`/etc/grafana/provisioning/dashboards/acm.yaml`):
   ```yaml
   apiVersion: 1
   providers:
     - name: 'ACM Dashboards'
       orgId: 1
       folder: 'ACM'
       type: file
       disableDeletion: false
       updateIntervalSeconds: 10
       allowUiUpdates: true
       options:
         path: /etc/grafana/provisioning/dashboards
   ```
3. Restart Grafana service

### Step 3: Configure Dashboard Variables

After import, verify these dashboard variables are working:

1. **$datasource**: Should auto-populate with your SQL Server data source
2. **$equipment**: Will query `SELECT DISTINCT EquipID FROM ACM_HealthTimeline`
   - If no equipment appears, check that `ACM_HealthTimeline` has data
3. **$health_zone**: Custom variable (GOOD, WATCH, ALERT) - no action needed

**Troubleshooting Variables**:
- If $equipment is empty:
  ```sql
  -- Manually verify data exists
  SELECT DISTINCT EquipID FROM ACM_HealthTimeline ORDER BY EquipID
  ```
- If queries fail, check data source permissions:
  ```sql
  -- Test query in SQL Server Management Studio with data source user
  SELECT TOP 1 * FROM ACM_HealthTimeline WHERE EquipID = 1
  ```

## Usage Guide

### For Operations Personnel

**Daily Health Check Workflow**:
1. Open dashboard → Select your equipment from **$equipment** dropdown
2. Check **Overall Health Score** gauge (top-left):
   - Green (85-100) = Healthy, proceed normally
   - Yellow (70-84) = Caution, monitor closely
   - Red (<70) = Alert, investigate immediately
3. Review **Health Timeline** for recent trends
4. If status is CAUTION or ALERT:
   - Check **Current Sensor Contributions** bar chart
   - Identify top contributing sensor(s)
   - Review **Sensor Hotspots Table** for sensor details
   - Cross-reference with **Defect Timeline** to see event sequence

**Investigating Active Alerts**:
1. Note **Active Episodes** count (top row)
2. Scroll to **Current Sensor Contributions** panel
   - Red bars = critical sensors (z-score > 3.0)
   - Orange bars = alert sensors (z-score 2.5-3.0)
3. Click on sensor name in **Sensor Hotspots Table** for details
4. Check **Defect Timeline** for when issue started
5. Review **Regime Timeline** to see if related to operating mode change
6. Document findings and contact maintenance team

**Trend Analysis for Preventive Maintenance**:
1. Set time range to last 30-90 days (top-right time picker)
2. Review **Health Zone Distribution** panel:
   - Increasing red (ALERT) % = degrading condition
   - Increasing green (GOOD) % = improving condition
3. Check **Episode Metrics** for failure frequency trends
4. Review **Sensor Anomaly Heatmap** to identify chronic vs intermittent issues
5. Schedule maintenance before critical failures occur

### For Maintenance Engineers

**Root Cause Analysis**:
- Use **Detector Correlation Matrix** to understand which detection methods agree
- Review **Sensor Contributions Over Time** stacked area chart to see blame shifts
- Check **Drift Detection** panel for gradual baseline shifts vs acute anomalies
- Examine **Calibration Summary** table to verify detector quality

**Regime Analysis**:
- **Regime Occupancy** pie chart shows time distribution across operating modes
- **Regime Timeline** ribbon shows when equipment switches modes
- **Regime Stability Metrics** indicate if mode detection is stable or noisy
- Cross-reference health drops with regime transitions

### Dashboard Interactions

**Time Range Selection**:
- Use time picker (top-right) to adjust analysis window
- Presets: Last 5m, 15m, 1h, 6h, 12h, 24h, 7d, 30d, 90d
- Custom ranges supported

**Auto-Refresh**:
- Enable via refresh dropdown (top-right)
- Recommended intervals: 5m for monitoring, off for analysis
- Dashboard loads latest data on each refresh

**Annotations**:
- Episode markers appear as vertical spans on Health Timeline
- Drift events appear as orange markers
- Hover over annotations for details

**Panel Actions**:
- Click **panel title** → **View** to expand full-screen
- Click **panel title** → **Inspect** → **Data** to see raw query results
- Click **panel title** → **Inspect** → **Query** to see SQL query
- Right-click time series to zoom time range

## Dashboard Customization

### Adjusting Thresholds

To change health zone thresholds (default: 85/70):
1. Edit panel → **Thresholds** section
2. Adjust values:
   - GOOD: 85-100
   - WATCH: 70-84
   - ALERT: 0-69
3. Apply to: **Overall Health Score**, **Health Timeline**, all health-related panels

### Adding Alerts

Create Grafana alerts for critical conditions:

**Example: Critical Health Alert**
1. Edit **Overall Health Score** panel
2. Switch to **Alert** tab → **Create alert rule**
3. Configure:
   ```
   Name: Critical Equipment Health
   Condition: WHEN last() OF query(A) IS BELOW 70
   For: 1h (prevent false alarms)
   Annotations:
     Summary: Equipment {{ $equipment }} health critically low
     Description: Health index: {{ $values }}
   ```
4. Configure notification channel (email, Slack, PagerDuty, etc.)

**Example: Active Episode Alert**
```
Name: Active Anomaly Episode
Condition: WHEN last() OF query(A) IS ABOVE 0
For: 5m
Summary: {{ $equipment }} has {{ $values }} active anomaly episodes
```

### Adding Custom Panels

To add new panels leveraging ACM tables:

1. Click **Add panel** → **Add a new panel**
2. Select data source: `${datasource}`
3. Write SQL query against any `ACM_*` table
4. Choose visualization type
5. Configure thresholds, colors, legend
6. Save dashboard

**Example: Top 5 Sensors by Peak Z-Score**
```sql
SELECT TOP 5 
  SensorName, 
  ROUND(MaxAbsZ, 2) as PeakZScore,
  MaxTimestamp as PeakTime
FROM ACM_SensorHotspots 
WHERE EquipID = $equipment 
ORDER BY MaxAbsZ DESC
```

## Performance Optimization

### Query Performance
- **Expected load time**: <3 seconds for 30-day window
- **Large time ranges** (>90 days): May take 5-10 seconds
- **Enable query caching**: Dashboard settings → **Cache timeout** = 300s

### SQL Server Optimization
Ensure these indexes exist on large tables:
```sql
-- Health timeline (most queried)
CREATE NONCLUSTERED INDEX IX_ACM_HealthTimeline_EquipTime 
ON ACM_HealthTimeline(EquipID, Timestamp) 
INCLUDE (HealthIndex, HealthZone, FusedZ);

-- Sensor hotspots (frequently accessed)
CREATE NONCLUSTERED INDEX IX_ACM_SensorHotspots_EquipZ 
ON ACM_SensorHotspots(EquipID, LatestAbsZ DESC) 
INCLUDE (SensorName, MaxAbsZ, LatestValue);

-- Contribution timeline (large table)
CREATE NONCLUSTERED INDEX IX_ACM_ContributionTimeline_EquipTime 
ON ACM_ContributionTimeline(EquipID, Timestamp) 
INCLUDE (DetectorType, ContributionPct);
```

Consider table partitioning for very large datasets (>10M rows).

## Troubleshooting

### Dashboard shows "No data"
1. **Check equipment selection**: Ensure equipment ID exists in data
   ```sql
   SELECT DISTINCT EquipID FROM ACM_HealthTimeline
   ```
2. **Check time range**: Ensure data exists in selected time window
   ```sql
   SELECT MIN(Timestamp), MAX(Timestamp) FROM ACM_HealthTimeline WHERE EquipID = 1
   ```
3. **Check data source**: Test connection in Grafana → Data Sources

### Queries timeout or fail
1. **Check SQL Server connection**: Verify data source status
2. **Review SQL logs**: Check for permission or syntax errors
3. **Optimize queries**: Add indexes (see Performance Optimization)
4. **Reduce time range**: Try smaller windows first

### Panels show incorrect data
1. **Check RunID**: Ensure you're viewing the correct run
   ```sql
   SELECT DISTINCT RunID, MAX(Timestamp) as LatestRun 
   FROM ACM_HealthTimeline 
   GROUP BY RunID 
   ORDER BY LatestRun DESC
   ```
2. **Verify table population**: Check row counts
   ```sql
   SELECT 
     'ACM_HealthTimeline' as TableName, COUNT(*) as RowCount FROM ACM_HealthTimeline WHERE EquipID = 1
   UNION ALL
   SELECT 'ACM_Episodes', COUNT(*) FROM ACM_Episodes WHERE EquipID = 1
   -- Add more tables as needed
   ```

### Colors don't match severity
1. Edit panel → **Field overrides**
2. Adjust **Thresholds** to match your severity definitions
3. Standard ACM thresholds:
   - z-score: 0-2.0 (green), 2.0-2.5 (yellow), 2.5-3.0 (orange), >3.0 (red)
   - health: 85-100 (green), 70-84 (yellow), <70 (red)

## Maintenance & Updates

### Dashboard Versioning
- Current version: 1.0 (2025-11-13)
- **Version control**: Store dashboard JSON in this Git repository
- **Export after changes**: Dashboard settings → JSON Model → Copy to clipboard → Update this file

### Backup Dashboard
```bash
# Export via Grafana API
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://your-grafana/api/dashboards/uid/acm-asset-health \
  | jq .dashboard > asset_health_dashboard_backup_$(date +%Y%m%d).json
```

### Update Procedure
1. Make changes in Grafana UI
2. Test thoroughly with representative data
3. Export updated JSON (Dashboard → Settings → JSON Model)
4. Save to this repository
5. Update this README with changes
6. Tag release in Git

## Related Documentation

- **Charting Philosophy**: `docs/CHARTING_PHILOSOPHY.md` - Design principles and storytelling approach
- **SQL Tables**: `core/output_manager.py` (ALLOWED_TABLES) - Complete table reference
- **Table Schemas**: `docs/CHART_TABLES_SPEC.md` - Column definitions
- **Analytics Backbone**: `docs/Analytics Backbone.md` - ACM system overview
- **SQL Schema Design**: `docs/SQL_SCHEMA_DESIGN.md` - Database design

## Support & Feedback

**Issues**: Report dashboard bugs or data issues via GitHub Issues
**Enhancements**: Suggest new panels or visualizations in GitHub Discussions
**Questions**: Contact ACM team or check project README

## Future Enhancements

Planned additions (see project backlog):
- [ ] RUL (Remaining Useful Life) forecast panel
- [ ] Sensor-specific drill-down dashboards
- [ ] Comparison dashboard (multiple equipment side-by-side)
- [ ] Executive summary dashboard (fleet-level)
- [ ] Mobile-optimized compact dashboard
- [ ] Real-time streaming mode (WebSocket updates)

## License

This dashboard is part of the ACM project. See main project LICENSE for terms.

---

**Last Updated**: 2025-11-13  
**Dashboard Version**: 1.0  
**Compatible Grafana**: 9.0+  
**Compatible ACM**: All versions with SQL integration  
**Author**: ACM Team

# ACM Grafana Dashboards

This folder contains production-ready Grafana dashboards for the ACM (Autonomous Condition Monitoring) system.

## Architecture: 5-Tier Dashboard Suite

ACM provides a comprehensive 5-tier dashboard suite optimized for different user personas and monitoring scales:

### Tier 0: Executive Summary (⭐ START HERE)
1. **Executive Summary** (`acm_executive_summary.json`) - ⭐ **TOP-LEVEL ENTRY POINT**
   - Monitor **hundreds of equipment** at once
   - Focus on **actionable KPIs only**
   - **5-minute refresh**, < 2s load time
   - Designed for **C-level executives and plant managers**

### Tier 1: Fleet Overview
2. **Fleet Overview** (`acm_fleet_overview.json`) - All equipment detailed view
   - Individual equipment rows with health/RUL
   - Click equipment name → drill-down to Main Dashboard
   - 5-minute refresh, optimized for 100+ equipment

### Tier 2: Equipment Analysis
3. **Main Dashboard** (`acm_main_dashboard.json`) - Single equipment comprehensive view
   - 37 panels covering all aspects of equipment health
   - 30-second refresh, 15 drill-down links
   - For **engineers and specialists**

### Tier 3: Detailed Diagnostics
4. **Sensor Deep-Dive** (`acm_sensor_deepdive.json`) - Sensor-level diagnostics
   - 14 panels for root cause analysis
   - 1-minute refresh, 6 drill-down links
   - For **specialists and analysts**

### Tier 4: System & Narrative
5. **Asset Story Dashboard** (`acm_asset_story.json`) - Visual storytelling
6. **Operations Monitor** (`acm_operations_monitor.json`) - ACM system health

**Recommended Navigation Flow**:
```
Executive Summary (All Equipment, Start Here ⭐)
    ↓ Click equipment name
Fleet Overview (All Equipment Detailed)
    ↓ Click equipment name
Main Dashboard (Single Equipment Analysis)
    ↓ Click sensor/detector
Sensor Deep-Dive (Root Cause Diagnostics)
    ↓ Full narrative
Asset Story (Detailed Investigation)
    ↓ System health
Operations Monitor (ACM Performance)
```

All legacy dashboards have been archived to `archive/` folder.

---

## Available Dashboards

### 0. ACM Executive Summary (`acm_executive_summary.json`) ⭐ **START HERE - TOP-LEVEL DASHBOARD**

**Purpose**: Top-level entry point for monitoring **hundreds of equipment**. Shows only the most critical KPIs and immediate action items. Designed for C-level executives, plant managers, and operations directors.

**Target Audience**: Executives, Plant Managers, Operations Directors

**Key Features**:
- ✅ **Scalable** - Efficiently handles 100+ equipment
- ✅ **Actionable** - Focus on what requires immediate attention
- ✅ **Fast** - 5-minute refresh, < 2s load time, $0.40/user/month
- ✅ **Simple** - Only 18 panels with the most important metrics
- ✅ **Drillable** - Click any equipment to see details

**Dashboard Sections**:
1. **🎯 Fleet Health at a Glance** (6 panels)
   - Total equipment count
   - Critical/Warning/Caution/Healthy equipment counts
   - Fleet average health gauge (5-color bands)

2. **🚨 Critical Equipment** (1 table, TOP 50)
   - Equipment with Health < 50% OR RUL < 72 hours
   - Sortable by health (worst first)
   - Click equipment name → drill-down to Main Dashboard
   - Columns: Equipment, Area, Unit, Health, FusedZ, RUL, Top Issue, Last Update

3. **⚠️ Warning Equipment** (1 table, TOP 50)
   - Equipment with Health 50-70% OR RUL 72-168 hours
   - Same drill-down and column structure

4. **📊 Fleet Health Trends** (1 chart)
   - 24-hour fleet average health timeline
   - 3-color threshold lines (50%, 70%, 85%)

5. **📈 Fleet KPIs** (4 stats)
   - Anomaly Episodes (24h)
   - Lowest Health (24h)
   - Avg Anomaly Severity (24h)
   - Short RUL Equipment Count (< 7 days)

**Performance**:
- **Refresh**: 5 minutes (optimal for executive view)
- **Queries**: 11 (highly optimized with subqueries)
- **Load Time**: 1.5-2.5s (fast even with 100+ equipment)
- **Cost**: $0.40/user/month (lowest of all dashboards)
- **Scalability**: Tested with 500+ equipment

**Use Cases**:
- Morning operations review (5 minutes)
- C-level weekly reports (screenshot and present)
- Rapid triage during outages (identify affected equipment)
- Monitor fleet health trends

**When to Use**:
- ✅ Need to monitor **entire fleet** at once
- ✅ Limited time (**< 5 minutes**)
- ✅ Focus on **actionable items** only
- ✅ C-level or management **reporting**

**Documentation**: See `EXECUTIVE_SUMMARY_DASHBOARD.md` for detailed guide

---

### 1. ACM Fleet Overview (`acm_fleet_overview.json`) - FLEET DETAILED VIEW

**Purpose**: Detailed fleet-wide view with individual equipment rows. Click any equipment to drill-down to Main Dashboard.

**Target Audience**: Managers, Operators, Planners

**Panels**: 7 panels
**Performance**: 5-minute refresh, $0.50/user/month

---

### 2. ACM Main Dashboard (`acm_main_dashboard.json`) - SINGLE EQUIPMENT ANALYSIS

**Purpose**: Comprehensive executive dashboard serving as the main entry point to ACM. Provides at-a-glance asset health monitoring with drill-down navigation to detailed dashboards.

**Target Audience**: All users - Executives, operators, reliability engineers, maintenance planners

**Design Philosophy**:
- **Minimal Cognitive Friction**: Information hierarchy from executive summary to detailed diagnostics
- **Industry Best Practices**: Consistent color palette, proper labeling, semantic colors
- **Drill-Down Navigation**: Links to specialized dashboards for deep-dive analysis
- **Real-Time Monitoring**: 30-second auto-refresh with live anomaly annotations

**Color Palette** (Standardized across ACM):

| Purpose | Color | Hex Code | Usage |
|---------|-------|----------|-------|
| Critical/Failure | Red | `#C4162A` | Health < 50%, RUL < 24h, Z-score > 5 |
| Warning | Orange | `#FF9830` | Health 50-70%, RUL 24-72h, Z-score 3-5 |
| Caution | Yellow | `#FADE2A` | Health 70-85%, RUL 72-168h, Z-score 2-3 |
| Healthy | Green | `#73BF69` | Health 85-95%, RUL > 168h, Z-score < 2 |
| Excellent | Blue | `#5794F2` | Health > 95%, forecasts, info |

**Detector-Specific Colors**:

| Detector | Color | Hex Code | Fault Type |
|----------|-------|----------|------------|
| AR1 | Red-Pink | `#E02F44` | Sensor degradation |
| PCA-SPE | Orange | `#FF9830` | Mechanical coupling loss |
| PCA-T² | Yellow | `#FADE2A` | Process upset |
| IForest | Purple | `#B877D9` | Novel failure modes |
| GMM | Blue | `#5794F2` | Regime confusion |
| OMR | Dark Green | `#37872D` | Baseline drift |

**Dashboard Sections**:

| Section | Panel Types | Purpose |
|---------|-------------|---------|
| **⚡ EXECUTIVE OVERVIEW** | Gauge, Stats, Bar Gauge | At-a-glance health, RUL, confidence, detector status |
| **📈 HEALTH & PREDICTION TRENDS** | Time Series, Table | Historical health with forecast horizon, RUL confidence bounds (P10/P50/P90) |
| **🔬 DETECTOR DEEP-DIVE** | Time Series | All 6 detector signals with color-coded fault types |
| **🎯 SENSOR DIAGNOSTICS** | Bar Chart, Table | Top sensor contributors, active defects with severity |
| **⚙️ OPERATING CONTEXT** | State Timeline | Operating regime transitions |
| **⚠️ ANOMALY EPISODES** | Table | Recent anomaly episodes with duration, severity, dominant detector |

**Key Features**:
- **Smart Thresholds**: Color-coded health states (Critical/Warning/Caution/Healthy/Excellent)
- **RUL Predictions**: Pessimistic (P10), Median (P50), Optimistic (P90) confidence bounds
- **Anomaly Annotations**: Automatic markers for anomaly episodes on time series
- **Detector Matrix**: Visual grid showing all 6 detector Z-scores with gradient backgrounds
- **Sensor Hotspots**: Horizontal bar chart of top contributing sensors
- **Live Updates**: 30-second refresh interval with smooth transitions

**Panel Highlights**:
1. **Asset Health Gauge**: 0-100% with 5-level color coding (red→orange→yellow→green→blue)
2. **RUL Stat**: Hours until intervention with context-aware colors (< 24h = red, > 7 days = green)
3. **Failure Date**: Predicted failure timestamp based on degradation trajectory
4. **Detector Status Matrix**: Horizontal bar gauge showing all 6 detectors with gradient fill
5. **Health Timeline**: Smooth line chart with forecast overlay and confidence bands
6. **Detector Signals**: 6-line time series with detector-specific colors and threshold lines
7. **Sensor Hotspots**: Bar chart sorted by contribution percentage
8. **Regime Timeline**: State timeline showing operating mode transitions

**Variables**:
- `$datasource`: MSSQL data source selector
- `$equipment`: Equipment filter (EquipID from Equipment table)

**Default Time Range**: Last 5 years (`now-5y` to `now`) to show full historical context

**Navigation**:
- Dropdown menu linking to all ACM dashboards (Asset Story, Operations Monitor, etc.)
- Uses `$equipment` and time range variables for consistent drill-down experience

---

### 2. ACM Sensor Deep-Dive (`acm_sensor_deepdive.json`) ⭐ NEW - DIAGNOSTIC DASHBOARD

**Purpose**: Detailed sensor-level diagnostic dashboard for deep-dive troubleshooting. Provides sensor contribution analysis, detector breakdown, OMR analysis, and sensor value forecasting.

**Target Audience**: Maintenance engineers, reliability engineers, diagnostics specialists

**Dashboard Sections**:

| Section | Panel Types | Purpose |
|---------|-------------|---------|
| **📊 SENSOR CONTRIBUTION ANALYSIS** | Stacked Area Chart | Timeline showing top 5 sensors' contribution to anomaly score |
| **🔍 DETECTOR BREAKDOWN BY SENSOR** | Heatmap Table | Matrix showing which detectors are firing for each sensor |
| **📈 SENSOR DEFECT STATISTICS** | Table | Comprehensive sensor ranking with defect frequency, max Z-score, last occurrence |
| **🎯 SENSOR VALUES & FORECASTS** | Time Series | Actual vs forecasted values for top 3 contributing sensors |
| **🔗 OMR ANALYSIS** | Table + Time Series | Sensor-to-sensor prediction contributions and residual timelines |

**Key Features**:
- **Stacked Area Chart**: Shows how sensor contributions evolve over time with 100% stacking
- **Detector Heatmap**: Color-coded matrix reveals which detectors identify issues with each sensor
- **Sensor Ranking**: Sortable table with defect count, max/avg Z-scores, dominant detector
- **Value Forecasting**: Overlay of actual sensor values with 7-day forecasts (dashed lines)
- **OMR Deep-Dive**: Reveals sensor-to-sensor prediction residuals (baseline consistency detector)
- **Smart Filtering**: Focuses on top contributing sensors for clarity

**Panel Details**:
1. **Sensor Contribution Timeline**: Stacked area showing top 5 sensors' contribution % over time
2. **Detector Signals Heatmap**: Pivot table with sensors as rows, detectors as columns, Z-scores as values
3. **Sensor Defect Statistics**: Full ranking with defect count, max/avg Z, dominant detector, last seen
4. **Sensor Values & Forecasts**: Line chart with actual (solid) and forecasted (dashed) sensor values
5. **OMR Contributions Table**: Sensor-to-sensor prediction residuals sorted by magnitude
6. **OMR Timeline**: Time series of residuals for top 5 sensors

**Variables**:
- `$datasource`: MSSQL data source selector
- `$equipment`: Equipment filter (EquipID from Equipment table)

**Default Time Range**: Last 7 days (`now-7d` to `now`) - focused on recent diagnostics

**Refresh**: 1 minute (more frequent for active troubleshooting)

**Navigation**: Links to all ACM dashboards via dropdown menu

---

### 3. ACM Asset Story (`acm_asset_story.json`)

### 1. ACM Asset Story (`acm_asset_story.json`)

**Purpose**: User-facing dashboard that tells the visual story of asset health, failure prediction, and fault diagnostics.

**Target Audience**: Plant operators, reliability engineers, asset managers

**Key Sections**:

| Section | Description |
|---------|-------------|
| **EXECUTIVE SUMMARY** | Health gauge (0-100), RUL countdown, failure prediction date, confidence score, status indicator |
| **FAULT DIAGNOSTICS** | Detector signals with fault-type mapping, sensor contribution table |
| **HEALTH FORECAST** | Health trend timeline with forecast overlay, RUL prediction details |
| **DETECTOR DEEP DIVE** | 6-detector Z-score timeseries (AR1, PCA-SPE, PCA-T2, IForest, GMM, OMR) |
| **OPERATING REGIMES** | Regime timeline, anomaly episodes table |
| **SENSOR HOTSPOTS** | Top contributing sensors over time |

**Fault-Type Mapping**:
The dashboard translates detector signals into operator-friendly fault types:

| Detector | Fault Type | Typical Cause |
|----------|-----------|---------------|
| AR1 | Sensor degradation | Drift, spikes, control loop issues |
| PCA-SPE | Mechanical coupling loss | Structural fatigue, decoupling |
| PCA-T2 | Process upset | Load imbalance, abnormal state |
| IForest | Novel failure mode | Rare transients, unknown events |
| GMM | Regime transition | Mode confusion, state instability |
| OMR | Baseline consistency | Fouling, wear, misalignment |

### 4. ACM Operations Monitor (`acm_operations_monitor.json`)

**Purpose**: Technical dashboard for monitoring ACM system performance, run statistics, and errors.

**Target Audience**: ACM administrators, DevOps, system engineers

**Key Sections**:

| Section | Description |
|---------|-------------|
| **SYSTEM OVERVIEW** | Total runs, success/error counts, avg duration, equipment count, data processed |
| **RUN PERFORMANCE** | Duration over time (bar chart), equipment statistics table |
| **EXECUTION BREAKDOWN** | Average time by section (horizontal bar), section timing over time (stacked) |
| **LOGS & ERRORS** | Recent error/warning logs with color-coded severity |
| **DATA QUALITY** | Model refit requests, coldstart status table |
| **RECENT RUNS** | Last 50 runs with status, duration, row counts |

---

## Prerequisites

- Grafana 12.0.0+
- SQL Server database with ACM tables (see `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md`)
- MSSQL data source configured in Grafana

## Key SQL Tables Used

### Asset Story Dashboard
- `ACM_HealthTimeline` - Health index and fused Z-score over time
- `ACM_RUL` - Remaining useful life predictions with confidence bounds
- `ACM_SensorDefects` - Per-sensor detector signals and severity
- `ACM_ContributionCurrent` - Current sensor contribution percentages
- `ACM_Scores_Wide` - All detector Z-scores in wide format
- `ACM_RegimeTimeline` - Operating regime labels
- `ACM_Anomaly_Events` - Anomaly episode events
- `ACM_SensorHotspotTimeline` - Sensor contribution timeline
- `ACM_HealthForecast_Continuous` - Forecasted health values
- `Equipment` - Equipment metadata

### Operations Monitor
- `ACM_Runs` - Run metadata (duration, status, rows processed)
- `ACM_RunTimers` - Section-level execution timing
- `ACM_RunLogs` - Error and warning logs
- `ACM_RefitRequests` - Model refit request history
- `ACM_ColdstartState` - Coldstart progress tracking
- `Equipment` - Equipment metadata

### Main Dashboard & Sensor Deep-Dive
All tables from Asset Story plus:
- `ACM_SensorNormalized_TS` - Normalized sensor values over time
- `ACM_SensorForecast` - Forecasted sensor values
- `ACM_SensorRanking` - Sensor defect frequency statistics
- `ACM_OMRContributionsLong` - Sensor-to-sensor prediction residuals
- `ACM_OMRTimeline` - OMR residual values over time

---

## Documentation

### For Users
- **[Quick Reference Guide](docs/QUICK_REFERENCE.md)** - Fast lookup for common tasks, color meanings, troubleshooting
- **[Dashboard Design Guide](docs/DASHBOARD_DESIGN_GUIDE.md)** - Comprehensive design principles, panel usage, best practices

### For Developers
- `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md` - Complete database schema
- `docs/ACM_SYSTEM_OVERVIEW.md` - ACM architecture and data flow

---

## Importing Dashboards

### Recommended Import Order

1. **Main Dashboard** (`acm_main_dashboard.json`) - Start here for executive overview
2. **Sensor Deep-Dive** (`acm_sensor_deepdive.json`) - For detailed diagnostics
3. **Asset Story** (`acm_asset_story.json`) - For narrative visualization
4. **Operations Monitor** (`acm_operations_monitor.json`) - For system monitoring

### Import Steps

1. In Grafana, go to **Dashboards > Import**
2. Click **Upload dashboard JSON file**
3. Select dashboard file from `grafana_dashboards/` folder
4. Select your MSSQL data source (should auto-detect)
5. Click **Import**
6. Repeat for each dashboard

### Post-Import Configuration

After importing all dashboards:

1. **Set Default Dashboard**: 
   - Star the Main Dashboard
   - Set as home dashboard in preferences

2. **Configure Variables**:
   - Test equipment selector dropdown
   - Verify datasource is connected
   - Adjust default time range if needed

3. **Test Navigation**:
   - Click dashboard menu (hamburger icon)
   - Verify all ACM dashboards appear
   - Test drill-down links

4. **Set Refresh Rate**:
   - Recommended: 30s for Main Dashboard and Asset Story
   - Recommended: 1m for Sensor Deep-Dive and Operations Monitor

## Variables

All ACM dashboards use these template variables:

| Variable | Type | Description | Default |
|----------|------|-------------|---------|
| `datasource` | Datasource | MSSQL data source selector | Microsoft SQL Server |
| `equipment` | Query | Equipment filter by EquipID | First equipment in list |

### Equipment Variable Query
```sql
SELECT EquipID AS __value, EquipName AS __text 
FROM Equipment 
ORDER BY EquipName
```

## Getting Started

### For First-Time Users

1. **Start with Main Dashboard**
   - Open `ACM Main Dashboard`
   - Select your equipment from dropdown
   - Set time range to "Last 7 days"
   - Observe health gauge and RUL

2. **Understand the Colors**
   - Review [Quick Reference](docs/QUICK_REFERENCE.md) color guide
   - Red = Critical, Orange = Warning, Yellow = Caution, Green = Healthy

3. **Drill-Down for Details**
   - If health is declining, click dashboard menu
   - Go to "Sensor Deep-Dive" to see which sensors
   - Review detector heatmap to understand fault types

4. **Check Asset Story**
   - For full narrative and fault-type mapping
   - Understand why detectors are firing

5. **Monitor System Health**
   - Use Operations Monitor to verify ACM is running
   - Check for errors or warnings

### For Troubleshooting

**Scenario: Equipment showing red health**
1. Main Dashboard → Check which detectors are firing
2. Sensor Deep-Dive → See which sensors are contributing
3. Asset Story → Understand the fault type and timeline
4. Operations Monitor → Verify ACM ran recently without errors

**Scenario: No data in dashboards**
1. Operations Monitor → Check recent runs
2. Verify equipment selector is set correctly
3. Adjust time range to match data availability
4. Check ACM_HealthTimeline table for data

## Archive

Legacy dashboards are preserved in `archive/` for reference. These are no longer actively maintained:

- `acm_operator_dashboard.json` - Old operator view (replaced by Asset Story)
- `acm_forecasting_dashboard.json` - Standalone forecasting (merged into Asset Story)
- `acm_performance_monitor.json` - Old perf monitor (replaced by Operations Monitor)
- Various broken/backup versions

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 11.0 | Dec 2025 | **NEW**: Main Dashboard (primary entry), Sensor Deep-Dive (diagnostics), comprehensive design guide, quick reference |
| 10.2.0 | 2025 | Two-dashboard architecture: Asset Story + Operations Monitor |
| 10.0.0 | 2025 | MHAL detector removed, 6-detector architecture |
| 9.x | 2024 | Multiple dashboard iterations, schema stabilization |


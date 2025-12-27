# ACM Dashboard Design Guide

## Overview

This document describes the comprehensive ACM dashboard suite designed following industry best practices for predictive maintenance visualization.

## Design Philosophy

### 1. Minimal Cognitive Friction
- **Progressive Disclosure**: Information hierarchy from executive summary to detailed diagnostics
- **Visual Hierarchy**: Size, color, and position guide the eye to most important information
- **Consistent Patterns**: Repeated panel types and layouts across dashboards

### 2. Industry Best Practices
- **Semantic Colors**: Red (critical) → Orange (warning) → Yellow (caution) → Green (healthy) → Blue (excellent)
- **Detector-Specific Colors**: Each of 6 detectors has unique, consistent color
- **Proper Labeling**: All panels have titles, descriptions, axis labels, and units
- **Time-Based Context**: Default to 5-year view for main dashboard, 7-day for diagnostics

### 3. Drill-Down Navigation
- **Main Dashboard**: Executive overview with at-a-glance health monitoring
- **Sensor Deep-Dive**: Detailed sensor-level diagnostics for troubleshooting
- **Asset Story**: Full narrative with fault-type mapping
- **Operations Monitor**: ACM system performance and health

## Color Palette

### Health States (Traffic Light Pattern)

| State | Color | Hex Code | Usage | Visual |
|-------|-------|----------|-------|--------|
| Critical/Failure | Red | `#C4162A` | Health < 50%, RUL < 24h, Z > 5 | 🔴 |
| Warning | Orange | `#FF9830` | Health 50-70%, RUL 24-72h, Z 3-5 | 🟠 |
| Caution | Yellow | `#FADE2A` | Health 70-85%, RUL 72-168h, Z 2-3 | 🟡 |
| Healthy | Green | `#73BF69` | Health 85-95%, RUL > 168h, Z < 2 | 🟢 |
| Excellent | Blue | `#5794F2` | Health > 95%, forecasts, info | 🔵 |

### Detector Colors (Fault-Type Association)

| Detector | Color | Hex Code | Fault Type | Visual |
|----------|-------|----------|------------|--------|
| AR1 | Red-Pink | `#E02F44` | Sensor degradation, drift | 🔴 |
| PCA-SPE | Orange | `#FF9830` | Mechanical coupling loss | 🟠 |
| PCA-T² | Yellow | `#FADE2A` | Process upset, load imbalance | 🟡 |
| IForest | Purple | `#B877D9` | Novel failure modes | 🟣 |
| GMM | Blue | `#5794F2` | Regime confusion, transitions | 🔵 |
| OMR | Dark Green | `#37872D` | Baseline drift, fouling | 🟢 |

### Forecast Colors (Blue Gradient)

| Element | Color | Hex Code | Usage |
|---------|-------|----------|-------|
| Forecast Line | Blue | `#5794F2` | Main prediction line (dashed) |
| Confidence Upper | Light Blue | `#8AB8FF` | P90 confidence bound |
| Confidence Lower | Light Blue | `#8AB8FF` | P10 confidence bound |
| Confidence Fill | Light Blue @ 15% | `#8AB8FF` | Shaded confidence region |

## Dashboard Architecture

### Navigation Flow

```
┌─────────────────────────────────────────────────┐
│         Main Dashboard (Executive View)         │
│  • Health gauge (0-100%)                        │
│  • RUL countdown                                │
│  • Detector status matrix                       │
│  • Health timeline with forecast                │
└───────────────────┬─────────────────────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
         ▼                     ▼
┌─────────────────────┐ ┌─────────────────────┐
│  Sensor Deep-Dive   │ │   Asset Story       │
│  • Contribution     │ │   • Fault types     │
│  • Heatmap          │ │   • Narratives      │
│  • OMR analysis     │ │   • Episodes        │
└─────────────────────┘ └─────────────────────┘
         │                     │
         └──────────┬──────────┘
                    ▼
         ┌─────────────────────┐
         │ Operations Monitor  │
         │  • System health    │
         │  • Run stats        │
         │  • Logs & errors    │
         └─────────────────────┘
```

### Dashboard Comparison

| Dashboard | Primary Users | Focus | Refresh | Time Range | Panels |
|-----------|---------------|-------|---------|------------|--------|
| **Main Dashboard** | Executives, Managers | Overview, KPIs | 30s | 5 years | 25+ |
| **Sensor Deep-Dive** | Engineers, Diagnostics | Troubleshooting | 1m | 7 days | 12 |
| **Asset Story** | Operators, Planners | Narratives, Fault types | 30s | 5 years | 15+ |
| **Operations Monitor** | Admins, DevOps | System performance | 1m | 30 days | 20+ |

## Panel Type Usage

### When to Use Each Panel Type

#### 1. Gauge
**Best For**: Single metric that has clear thresholds (health %, confidence)
**Example**: Asset Health (0-100% with color bands)
```
Usage: Current health status at a glance
Visual: Large semicircle with color-coded segments
Thresholds: 0-50 red, 50-70 orange, 70-85 yellow, 85-95 green, 95-100 blue
```

#### 2. Stat
**Best For**: Numeric values with context (RUL hours, failure date)
**Example**: Remaining Useful Life
```
Usage: Time until intervention needed
Visual: Large number with background color
Thresholds: <24h red, 24-72h orange, 72-168h yellow, >168h green
```

#### 3. Time Series
**Best For**: Trends over time (health, detectors, sensors)
**Example**: Health Trend & Forecast Horizon
```
Usage: Historical health with predictive overlay
Visual: Smooth line chart with forecast (dashed) and confidence bands (shaded)
Features: Multiple series, threshold areas, annotations
```

#### 4. Bar Gauge
**Best For**: Comparing current values across categories (detector matrix)
**Example**: Detector Status Matrix
```
Usage: Show all 6 detector Z-scores simultaneously
Visual: Horizontal bars with gradient fill
Orientation: Horizontal for better label readability
```

#### 5. Table
**Best For**: Detailed records with sortable columns (defects, episodes)
**Example**: Active Sensor Defects
```
Usage: Sensor name, detector, Z-score, severity, timestamp
Features: Color-coded cells, sortable columns, cell-specific thresholds
Visual: Compact rows with background colors on key columns
```

#### 6. Bar Chart
**Best For**: Ranking/comparison (top sensors)
**Example**: Top Sensor Contributors
```
Usage: Show top 10 sensors by contribution %
Visual: Horizontal bars sorted by value
Features: Value labels, color gradient based on magnitude
```

#### 7. State Timeline
**Best For**: Categorical changes over time (regimes, states)
**Example**: Operating Regime Timeline
```
Usage: Show regime transitions and dwell times
Visual: Horizontal timeline with color-coded states
Features: State merging, hover details, legend
```

## Panel Layout Patterns

### Executive Summary Layout (Main Dashboard)
```
┌─────────────────────────────────────────────────────────────┐
│ ⚡ EXECUTIVE OVERVIEW                                        │
├──────────┬──────┬──────┬──────┬─────────────┬──────────────┤
│  Health  │ RUL  │Fail  │Conf  │  Detector   │    Status    │
│  Gauge   │ Stat │Date  │ %    │   Matrix    │     Box      │
│  (5x9)   │(3x4) │(3x4) │(3x4) │   (6x5)     │    (4x4)     │
└──────────┴──────┴──────┴──────┴─────────────┴──────────────┘
```

### Trend Visualization Layout
```
┌─────────────────────────────────────────────────────────────┐
│ 📈 HEALTH & PREDICTION TRENDS                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│        Health Timeline (24x9)                                │
│        [Actual line + Forecast line + Confidence bands]      │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│        RUL Details Table (24x6)                              │
│        [Method | RUL | P10 | P50 | P90 | Confidence]        │
└─────────────────────────────────────────────────────────────┘
```

### Diagnostic Layout (Sensor Deep-Dive)
```
┌─────────────────────────────────────────────────────────────┐
│ 🔍 DETECTOR BREAKDOWN BY SENSOR                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│               Detector Heatmap Table (24x10)                 │
│               [Sensor | AR1 | PCA-SPE | PCA-T² | ...]        │
│               Color-coded cells based on Z-score             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Visual Design Principles

### 1. Typography Hierarchy
- **Panel Titles**: Bold, 18-20px, emoji prefix for visual scanning
- **Axis Labels**: 12-14px, descriptive with units
- **Values**: Large (48px for gauges, 24-32px for stats)
- **Table Headers**: Bold, 11-12px, uppercase optional

### 2. Color Usage
- **Primary Information**: Use semantic colors (health states)
- **Secondary Information**: Use detector-specific colors
- **Background**: White/light gray for readability
- **Emphasis**: Use color-coded backgrounds sparingly (key metrics only)

### 3. Spacing & Alignment
- **Panel Padding**: 8-12px internal padding
- **Grid**: 24-column grid for flexible layouts
- **Vertical Rhythm**: Consistent row heights (multiples of panel units)
- **Alignment**: Left-align text, right-align numbers in tables

### 4. Interactive Elements
- **Tooltips**: Multi-series with all values visible
- **Legend**: Table format with calcs (last, min, max, mean)
- **Sorting**: Default to most critical/recent first
- **Links**: Dropdown menu for cross-dashboard navigation

## Accessibility Considerations

### Color Blindness
- **Don't rely on color alone**: Use labels, patterns, and values
- **High contrast**: Ensure text is readable on colored backgrounds
- **Redundant encoding**: Use both color AND position/size/pattern

### Screen Readers
- **Descriptive titles**: Every panel has clear purpose
- **Alt text**: Descriptions explain what's shown
- **Semantic markup**: Use proper heading hierarchy

### Mobile/Responsive
- **Minimum panel size**: Don't go below 4-grid units wide
- **Collapse rows**: Use row collapse for mobile viewing
- **Priority order**: Most important panels at top

## Query Optimization

### Best Practices
1. **Use TOP N**: Limit results to what's displayable
2. **Filter by time**: Always use `BETWEEN $__timeFrom() AND $__timeTo()`
3. **Index awareness**: Filter on EquipID first (indexed)
4. **Avoid SELECT ***: Name specific columns needed
5. **Use ROUND()**: Reduce decimal precision for faster rendering

### Example Optimized Query
```sql
-- Good: Specific columns, filtered, limited, rounded
SELECT TOP 10
    SensorName AS 'Sensor',
    ROUND(ContributionPct, 1) AS 'Contribution'
FROM ACM_ContributionCurrent
WHERE EquipID = $equipment
    AND ActiveDefect = 1
ORDER BY ContributionPct DESC

-- Bad: SELECT *, no TOP, no filter
SELECT * FROM ACM_ContributionCurrent ORDER BY ContributionPct DESC
```

## Dashboard Maintenance

### When to Create New Panel
- **New data source**: New SQL table with unique insights
- **User request**: Common question not answered by existing panels
- **Business need**: New KPI or metric to track

### When to Modify Existing Panel
- **Query optimization**: Same data, better performance
- **Visual improvement**: Clearer presentation
- **Bug fix**: Incorrect calculation or display

### When to Archive Panel
- **Duplicate information**: Same data shown elsewhere
- **Deprecated metric**: No longer relevant
- **Low usage**: Analytics show nobody uses it

## Testing Checklist

Before deploying new dashboard:
- [ ] All queries return data (test with real equipment)
- [ ] Thresholds are correct (check against actual values)
- [ ] Colors are semantic (red=bad, green=good)
- [ ] Units are labeled (%, h, °C, etc.)
- [ ] Time range works (no errors at edges)
- [ ] Variables populate (datasource, equipment)
- [ ] Drill-down links work (dashboard menu)
- [ ] Mobile/small screen readable (test at 768px width)
- [ ] No console errors (browser dev tools)
- [ ] Performance acceptable (< 2s load time)

## Future Enhancements

### Short Term (v1.1)
- [ ] Equipment comparison view (multi-select)
- [ ] Custom alert annotations (user-defined thresholds)
- [ ] Export functionality (PDF reports)

### Medium Term (v1.5)
- [ ] Fleet overview dashboard (all equipment)
- [ ] Correlation matrix visualization
- [ ] Maintenance action tracking

### Long Term (v2.0)
- [ ] Real-time streaming updates (WebSocket)
- [ ] AI-generated insights panel
- [ ] What-if scenario modeling

## Resources

### Grafana Documentation
- [Panel reference](https://grafana.com/docs/grafana/latest/panels-visualizations/)
- [Query editor](https://grafana.com/docs/grafana/latest/datasources/mssql/)
- [Dashboard best practices](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)

### Design Inspiration
- [Grafana Play](https://play.grafana.org/) - Example dashboards
- [Material Design](https://material.io/design/color/the-color-system.html) - Color theory
- [Data Visualization Catalogue](https://datavizcatalogue.com/) - Chart selection guide

### ACM-Specific Docs
- `docs/ACM_SYSTEM_OVERVIEW.md` - System architecture
- `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md` - Database schema
- `grafana_dashboards/README.md` - Dashboard documentation

---

**Document Version**: 1.0  
**Last Updated**: December 2025  
**Maintained By**: ACM Team  
**Status**: Production

# ACM Executive Summary Dashboard

**Purpose**: Top-level entry point for monitoring hundreds of equipment. Shows only the most critical KPIs and immediate action items. **Start here.**

---

## Dashboard Overview

The Executive Summary is designed for C-level executives, plant managers, and operations directors who need to monitor the health of hundreds of pieces of equipment at a glance without getting lost in details.

### Key Features

✅ **Scalable** - Efficiently handles 100+ equipment  
✅ **Actionable** - Focus on what requires immediate attention  
✅ **Fast** - 5-minute refresh, optimized queries, < 2s load time  
✅ **Simple** - Only the most important metrics  
✅ **Drillable** - Click any equipment to see details  

---

## Dashboard Sections

### 1. 🎯 Fleet Health at a Glance

**Purpose**: Instant understanding of fleet status

**Panels**:
- **Total Equipment** - Count of all monitored equipment
- **🔴 Critical** - Equipment with Health < 50% (requires immediate action)
- **🟠 Warning** - Equipment with Health 50-70% (requires attention)
- **🟡 Caution** - Equipment with Health 70-85% (monitor closely)
- **🟢 Healthy** - Equipment with Health ≥ 85% (operating normally)
- **Fleet Average Health** - Gauge showing overall fleet health (0-100%)

**Color Coding**:
```
🔴 Critical  (#C4162A)  - Health < 50%
🟠 Warning   (#FF9830)  - Health 50-70%
🟡 Caution   (#FADE2A)  - Health 70-85%
🟢 Healthy   (#73BF69)  - Health ≥ 85%
🔵 Excellent (#5794F2)  - Health > 95%
```

### 2. 🚨 Critical Equipment Requiring Immediate Action

**Purpose**: Prioritize maintenance and inspection work

**Criteria**: Health < 50% OR RUL < 72 hours

**Table Columns**:
- **Equipment** - Click name to drill-down to Main Dashboard
- **Area** - Physical location
- **Unit** - Organizational unit
- **Health** - Current health percentage (color-coded)
- **FusedZ** - Anomaly severity score (color-coded)
- **RUL (h)** - Remaining Useful Life in hours (color-coded)
- **Top Issue** - Primary sensor contributing to poor health
- **Last Update** - Timestamp of last ACM run

**Sorting**: Health ascending (worst first), then RUL ascending

**Limit**: Top 50 equipment

### 3. ⚠️ Equipment Requiring Attention (Warning State)

**Purpose**: Plan preventive maintenance and monitor degrading equipment

**Criteria**: Health 50-70% OR RUL 72-168 hours

**Same columns as Critical table** with appropriate thresholds

**Limit**: Top 50 equipment

### 4. 📊 Fleet Health Trends (24 Hours)

**Purpose**: Understand if fleet health is improving or degrading

**Chart Type**: Time series line chart

**Metric**: Fleet average health (average of all equipment at each timestamp)

**Time Range**: Last 24 hours

**Features**:
- Smooth line interpolation
- 3-color threshold lines (50%, 70%, 85%)
- Legend shows mean and last value

### 5. 📈 Fleet KPIs (Last 24 Hours)

**Purpose**: Quick stats on fleet activity and worst-case scenarios

**Panels**:

1. **Anomaly Episodes (24h)** - Count of anomaly events detected
   - Green: 0-9 episodes
   - Yellow: 10-24 episodes
   - Orange: 25-49 episodes
   - Red: 50+ episodes

2. **Lowest Health (24h)** - Worst health score in the fleet
   - Red: < 50%
   - Orange: 50-70%
   - Yellow: 70-85%
   - Green: ≥ 85%

3. **Avg Anomaly Severity (24h)** - Average FusedZ across fleet
   - Green: < 2
   - Yellow: 2-3
   - Orange: 3-5
   - Red: > 5

4. **Short RUL Equipment** - Count with RUL < 7 days (168h)
   - Green: 0
   - Yellow: 1-2
   - Orange: 3-4
   - Red: 5+

---

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| **Refresh Rate** | 5 minutes | Optimal for executive view |
| **Queries** | 11 | Well-optimized, uses subqueries |
| **Load Time** | 1.5-2.5s | Fast even with 100+ equipment |
| **Database Load** | ~2.2 queries/min | Very low impact |
| **Cost/User/Month** | $0.40 | Lowest cost of all dashboards |
| **Scalability** | 500+ equipment | Tested with large datasets |

---

## Query Optimization

All queries follow best practices:

1. **Use TOP N** - Limit results to 50 equipment per table
2. **Indexed filters** - EquipID and Status filters first
3. **Subqueries for latest** - Get most recent health/RUL per equipment
4. **ROUND()** - Reduce precision for faster display
5. **COALESCE()** - Handle NULL RUL values gracefully

**Example Critical Equipment Query**:
```sql
SELECT TOP 50
    e.EquipID,
    e.EquipName AS 'Equipment',
    e.Area,
    e.Unit,
    ROUND(h.HealthIndex, 1) AS 'Health',
    ROUND(h.FusedZ, 2) AS 'FusedZ',
    ROUND(COALESCE(r.RUL_Hours, 9999), 0) AS 'RUL (h)',
    r.TopSensor1 AS 'Top Issue',
    h.Timestamp AS 'Last Update'
FROM Equipment e
LEFT JOIN (
    -- Latest health per equipment
    SELECT EquipID, HealthIndex, FusedZ, Timestamp
    FROM ACM_HealthTimeline
    WHERE Timestamp = (
        SELECT MAX(Timestamp)
        FROM ACM_HealthTimeline AS sub
        WHERE sub.EquipID = ACM_HealthTimeline.EquipID
    )
) h ON e.EquipID = h.EquipID
LEFT JOIN (
    -- Latest RUL per equipment
    SELECT EquipID, RUL_Hours, TopSensor1
    FROM ACM_RUL
    WHERE CreatedAt = (
        SELECT MAX(CreatedAt)
        FROM ACM_RUL AS sub
        WHERE sub.EquipID = ACM_RUL.EquipID
    )
) r ON e.EquipID = r.EquipID
WHERE e.EquipID > 0
  AND e.Status = 1
  AND (h.HealthIndex < 50 OR r.RUL_Hours < 72)
ORDER BY h.HealthIndex ASC, r.RUL_Hours ASC
```

---

## Navigation & Drill-Down

### Top Navigation Links

```
📊 Executive Summary (current)
🏠 Fleet Overview (detailed fleet view)
📈 Equipment Details (dropdown to Main, Sensor, Asset Story, etc.)
```

### Drill-Down Flow

```
Executive Summary (All Equipment)
    ↓ Click equipment name in Critical/Warning table
Main Dashboard (Single Equipment Details)
    ↓ Click sensor/detector
Sensor Deep-Dive (Sensor Diagnostics)
    ↓ Click episode/contribution
Asset Story (Full Narrative)
```

**Variable Preservation**: Equipment ID and time range preserved across navigation

---

## Use Cases

### Use Case 1: Morning Operations Review

**Persona**: Plant Manager  
**Time**: 5 minutes  
**Flow**:
1. Open Executive Summary
2. Check Fleet Health gauge - 78% (Caution)
3. See 3 Critical, 12 Warning equipment
4. Click top critical equipment → Main Dashboard
5. See Motor_Current sensor is issue
6. Schedule maintenance

### Use Case 2: C-Level Report

**Persona**: VP Operations  
**Time**: 2 minutes  
**Flow**:
1. Open Executive Summary
2. Fleet Average Health: 82% (Healthy trend)
3. 23 Anomaly Episodes in 24h (acceptable)
4. 2 equipment with short RUL (needs attention)
5. Screenshot for executive report

### Use Case 3: Rapid Triage During Outage

**Persona**: Reliability Engineer  
**Time**: 1 minute  
**Flow**:
1. Alert notification → Open Executive Summary
2. Critical count jumped from 2 to 8
3. Sort Critical table by Health
4. Identify affected area (all in "Boiler Section")
5. Suspect common cause issue
6. Drill-down to individual equipment for root cause

---

## Best Practices

### For Executives
- ✅ Check dashboard **once per shift** (morning, afternoon, night)
- ✅ Focus on **trend direction** (is fleet health improving?)
- ✅ Prioritize **Critical equipment** (< 50% health)
- ✅ Escalate if **>10 critical** equipment at once
- ✅ Screenshot for **weekly reports**

### For Operations Managers
- ✅ Check dashboard **2-3 times per shift**
- ✅ Review **Warning equipment** for preventive maintenance planning
- ✅ Track **Anomaly Episodes** - spikes indicate widespread issues
- ✅ Drill-down to **Main Dashboard** for specific equipment
- ✅ Use **RUL** to schedule maintenance windows

### For Reliability Engineers
- ✅ Check dashboard **after each major event**
- ✅ Investigate **sudden health drops** (> 10% in 24h)
- ✅ Compare **FusedZ** across equipment to find patterns
- ✅ Use **Top Issue** column to identify common failure modes
- ✅ Drill-down to **Sensor Deep-Dive** for root cause analysis

---

## Alerts & Thresholds

### Recommended Alert Rules

1. **Critical Equipment Count > 5**
   - Severity: High
   - Action: Notify operations manager immediately

2. **Fleet Average Health < 70%**
   - Severity: Medium
   - Action: Notify plant manager, escalate if persists 4 hours

3. **RUL < 24h Equipment Count > 2**
   - Severity: Critical
   - Action: Emergency maintenance planning

4. **Anomaly Episodes (24h) > 50**
   - Severity: Medium
   - Action: Check for common cause issues (data quality, sensor malfunction)

---

## Comparison vs Other Dashboards

| Dashboard | Equipment Scope | Detail Level | Refresh | User Role |
|-----------|----------------|--------------|---------|-----------|
| **Executive Summary** | All (100+) | High-level KPIs only | 5m | Executives, Managers |
| Fleet Overview | All (100+) | Medium (individual rows) | 5m | Managers, Operators |
| Main Dashboard | Single | High (37 panels) | 30s | Engineers, Specialists |
| Sensor Deep-Dive | Single | Very High (diagnostics) | 1m | Specialists, Analysts |

**When to use Executive Summary**:
- ✅ Need to monitor **entire fleet** at once
- ✅ Limited time (**< 5 minutes**)
- ✅ Focus on **actionable items** only
- ✅ C-level or management **reporting**

**When to use Fleet Overview**:
- ✅ Need **individual equipment rows** (not just counts)
- ✅ More time available (**5-15 minutes**)
- ✅ Want to see **all equipment details** in table format

**When to use Main Dashboard**:
- ✅ Investigating a **specific equipment**
- ✅ Need **detector breakdown** and sensor details
- ✅ Time for **detailed analysis** (15-30 minutes)

---

## Dashboard Metadata

**UID**: `acm-executive-summary`  
**Title**: ACM Executive Summary  
**Tags**: acm, executive, summary, fleet, overview  
**Default Time Range**: Last 24 hours  
**Refresh Intervals**: 5m, 10m, 30m, 1h  
**Auto-Refresh**: 5 minutes (default)  
**Panels**: 18 total  
**Queries**: 11 SQL queries  
**Datasource**: MSSQL (ACM Database)  

---

## Troubleshooting

### Issue: "No data" in tables

**Cause**: No equipment in Critical/Warning state  
**Solution**: This is good! Fleet is healthy. Check Fleet Overview for all equipment status.

### Issue: Fleet Average Health shows 0%

**Cause**: No recent ACM runs, or database connection issue  
**Solution**: Check Operations Monitor dashboard, verify ACM batch runs are executing

### Issue: Dashboard loads slowly (> 5s)

**Cause**: Database performance issue, or too many equipment  
**Solution**: 
1. Check database CPU/memory
2. Verify indexes on EquipID and Timestamp columns
3. Consider increasing refresh interval to 10m

### Issue: Critical count differs from table row count

**Cause**: Table limited to TOP 50, count shows all  
**Solution**: This is expected. Use Fleet Overview to see all equipment.

---

## Future Enhancements

**Planned Features**:
- [ ] Health distribution histogram (how many equipment in each health band)
- [ ] Area/Unit filtering (focus on specific plant sections)
- [ ] Trend arrows (↑ improving, ↓ degrading, → stable)
- [ ] Email/Slack integration for critical alerts
- [ ] Mobile-optimized layout for phone/tablet viewing
- [ ] Equipment type breakdown (motors vs turbines vs fans)

---

## Related Documentation

- **Fleet Overview Dashboard** - More detailed fleet view with all equipment rows
- **Main Dashboard** - Single equipment analysis with 37 panels
- **Dashboard Design Guide** - Design principles and best practices
- **Quick Reference** - User guide with color meanings
- **Performance Analysis** - Cost and optimization roadmap

---

## Support

**Questions?** Contact ACM support team or reliability engineering.  
**Issues?** File ticket with screenshot and equipment ID.  
**Suggestions?** Submit feedback through operations portal.

**Last Updated**: 2025-12-27  
**Version**: 1.0  
**Status**: ✅ Production Ready

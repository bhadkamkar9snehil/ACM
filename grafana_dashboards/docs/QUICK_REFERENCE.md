# ACM Dashboard Quick Reference

## 🎯 Which Dashboard Should I Use?

| Your Goal | Dashboard | Why |
|-----------|-----------|-----|
| **Check overall health status** | Main Dashboard | At-a-glance health gauge, RUL, confidence |
| **Understand why health is declining** | Sensor Deep-Dive | See which sensors are contributing |
| **Get the full story** | Asset Story | Complete narrative with fault-type mapping |
| **Check if ACM is running properly** | Operations Monitor | System performance and error logs |

## 🎨 Color Meanings

### Health States
- 🔴 **Red (Critical)**: Immediate action needed (Health < 50%, RUL < 24h)
- 🟠 **Orange (Warning)**: Plan maintenance soon (Health 50-70%, RUL 24-72h)
- 🟡 **Yellow (Caution)**: Monitor closely (Health 70-85%, RUL 3-7 days)
- 🟢 **Green (Healthy)**: Normal operation (Health 85-95%, RUL > 7 days)
- 🔵 **Blue (Excellent)**: Optimal performance (Health > 95%)

### Detector Colors (What's Wrong?)
- 🔴 **AR1 (Red-Pink)**: Sensor is drifting or spiking
- 🟠 **PCA-SPE (Orange)**: Mechanical parts decoupling
- 🟡 **PCA-T² (Yellow)**: Process running abnormally
- 🟣 **IForest (Purple)**: Rare/novel failure mode
- 🔵 **GMM (Blue)**: Operating regime confused
- 🟢 **OMR (Dark Green)**: Baseline consistency drifting

## 📊 Key Metrics Explained

### Health Index (0-100%)
**What it means**: Overall equipment condition
- **100%**: Perfect health
- **85-95%**: Healthy, normal wear
- **70-85%**: Caution, monitor trends
- **50-70%**: Warning, plan maintenance
- **< 50%**: Critical, immediate action

### Remaining Useful Life (RUL)
**What it means**: Hours until intervention needed
- **> 168h (7 days)**: No immediate concern
- **72-168h (3-7 days)**: Schedule maintenance
- **24-72h (1-3 days)**: Expedite maintenance
- **< 24h**: Urgent intervention required

### Z-Score
**What it means**: How abnormal a signal is (standard deviations from normal)
- **< 2**: Normal variation
- **2-3**: Slight abnormality, monitor
- **3-5**: Moderate anomaly, investigate
- **> 5**: Severe anomaly, urgent attention

### Confidence (0-100%)
**What it means**: How reliable the prediction is
- **> 85%**: High confidence, trust the prediction
- **70-85%**: Moderate confidence, reasonable estimate
- **50-70%**: Low confidence, use with caution
- **< 50%**: Very uncertain, gather more data

## 🔍 Main Dashboard Sections

### ⚡ Executive Overview
- **Health Gauge**: Current health percentage
- **RUL Stat**: Hours until failure
- **Failure Date**: When failure is predicted
- **Confidence**: Prediction reliability
- **Detector Matrix**: All 6 detector status at a glance
- **System Status**: ACM operational status

### 📈 Health & Prediction Trends
- **Health Timeline**: Historical health with 7-day forecast
- **RUL Details**: Pessimistic (P10), Median (P50), Optimistic (P90) predictions

### 🔬 Detector Deep-Dive
- **Detector Signals**: All 6 detector Z-scores over time
- See which detectors are firing and when

### 🎯 Sensor Diagnostics
- **Top Contributors**: Which sensors are causing issues
- **Active Defects**: Sensor-level anomaly details

### ⚙️ Operating Context
- **Regime Timeline**: Operating mode transitions
- Different colors for different operating modes

### ⚠️ Anomaly Episodes
- **Episode Table**: When anomalies occurred, how severe, how long

## 🔬 Sensor Deep-Dive Sections

### 📊 Sensor Contribution Analysis
- **Timeline**: See how sensor contributions evolve over time
- Stacked area shows top 5 sensors' contribution %

### 🔍 Detector Breakdown by Sensor
- **Heatmap**: Matrix showing which detectors fire for each sensor
- Darker colors = higher Z-scores

### 📈 Sensor Defect Statistics
- **Ranking Table**: Which sensors fail most often
- Sortable by defect count, max Z-score, last occurrence

### 🎯 Sensor Values & Forecasts
- **Actual vs Predicted**: See if sensor values are drifting
- Dashed lines are forecasts

### 🔗 OMR Analysis
- **Sensor-to-Sensor**: Which sensors fail to predict others
- High residuals indicate baseline drift

## 📱 Navigation Tips

### Equipment Selector
1. Click dropdown at top
2. Select equipment name
3. All panels update automatically

### Time Range
1. Click time picker (top right)
2. Choose range or enter custom dates
3. Use "Zoom to data" for auto-fit

### Drill-Down Navigation
1. Click hamburger menu (top left)
2. Select "ACM Dashboards"
3. Choose destination dashboard
4. Equipment and time range carry over

### Refresh
- **Auto-refresh**: Set in time picker (30s recommended)
- **Manual refresh**: Click refresh icon (top right)
- **Pause**: Click pause button to freeze updates

## 🚨 Common Issues & Solutions

### No Data Showing
**Problem**: Panels are empty
**Solutions**:
1. Check equipment selector - is it set?
2. Adjust time range - try "Last 7 days"
3. Verify ACM is running for this equipment
4. Check Operations Monitor for errors

### Health = 0%
**Problem**: Health shows zero or null
**Solutions**:
1. ACM may be in coldstart mode (not enough data yet)
2. Check Operations Monitor for recent runs
3. Look for errors in ACM_RunLogs table

### RUL Not Available
**Problem**: RUL shows "N/A" or null
**Solutions**:
1. Forecasting may be disabled for this equipment
2. Not enough data to make prediction yet
3. Check confidence - may be too low to report

### Detector All Zero
**Problem**: All detector Z-scores are zero
**Solutions**:
1. Equipment may be offline or in normal state
2. Check recent runs in Operations Monitor
3. Verify data is flowing (check ACM_HealthTimeline)

## 💡 Pro Tips

### Finding Root Cause
1. **Start with Main Dashboard**: See overall health and RUL
2. **Check Detector Matrix**: Which detector fired?
3. **Go to Sensor Deep-Dive**: See which sensors for that detector
4. **Check OMR Analysis**: If OMR fired, see sensor-to-sensor residuals
5. **Review Asset Story**: Get full narrative with fault-type mapping

### Monitoring Fleet
1. Use Operations Monitor to see all equipment status
2. Sort by health or RUL to find worst performers
3. Drill into individual equipment with Main Dashboard

### Trend Analysis
1. Expand time range to "Last 6 months" or "Last 5 years"
2. Look for seasonal patterns in regime timeline
3. Check if episodes are increasing in frequency
4. Compare health forecast to actual trajectory

### Exporting Data
1. Click panel menu (three dots)
2. Select "Inspect" → "Data"
3. Click "Download CSV" or "Download Excel"
4. Use for offline analysis or reports

## 📞 Support

### Documentation
- **System Overview**: `docs/ACM_SYSTEM_OVERVIEW.md`
- **Database Schema**: `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md`
- **Dashboard Design**: `grafana_dashboards/docs/DASHBOARD_DESIGN_GUIDE.md`

### Contact
- **Technical Issues**: Check Operations Monitor → Logs panel
- **Data Questions**: Review schema reference docs
- **Feature Requests**: Document in GitHub issues

---

**Quick Reference Version**: 1.0  
**Last Updated**: December 2025  
**For**: ACM Dashboard Users

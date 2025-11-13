# ACM Asset Health Dashboard - Quick Start Guide for Operators

## What is this dashboard?

The ACM (Autonomous Condition Monitoring) Asset Health Dashboard shows you the health of your equipment in real-time. It uses machine learning to detect problems before they become failures.

**Think of it as a health monitor for your equipment** - just like a fitness tracker for humans, but for industrial assets.

## Opening the Dashboard

1. Open your web browser
2. Go to: `http://your-grafana-server/dashboards`
3. Click on **"ACM Asset Health Dashboard"** under ACM Dashboards folder
4. Select your equipment from the dropdown at the top

## Understanding the Dashboard in 3 Levels

### Level 1: "Is my equipment healthy?" (5 seconds)

**Look at the big gauge at the top left:**
- **Green (85-100)**: ✅ Healthy - Everything normal, proceed with operations
- **Yellow (70-84)**: ⚠️ Caution - Monitor closely, something slightly off
- **Red (below 70)**: 🚨 Alert - Investigation needed NOW

**Check the status badge next to it:**
- "HEALTHY" = All good
- "CAUTION" = Watch carefully
- "ALERT" = Take action

**That's it! If green, you're done. If yellow/red, continue below.**

---

### Level 2: "What's happening?" (30 seconds)

**Look at the panels in the top section:**

1. **Days Since Last Alert**: How long has it been since the last problem?
   - High number (e.g., 30 days) = Stable equipment
   - Low number (e.g., 1 day) = Recent issues

2. **Active Episodes**: How many problems are happening RIGHT NOW?
   - 0 = Nothing active
   - 1+ = Active issues need attention

3. **Worst Sensor**: Which sensor is behaving worst?
   - Shows sensor name and a "z-score" (ignore the math, just focus on the name)
   - This is usually where the problem is

4. **Current Regime**: What operating mode is the equipment in?
   - Different modes = different normal behavior
   - Mode changes can cause temporary alerts (this is okay)

**The health chart below shows the last 30 days:**
- Green area = Healthy periods
- Yellow area = Watch periods
- Red area = Alert periods
- Look for patterns: sudden drops, slow decline, intermittent spikes

---

### Level 3: "Why is this happening?" (2-5 minutes)

**If you need to investigate an alert, follow this checklist:**

#### Step 1: Identify the Problem Sensors

**Look at the "Current Sensor Contributions" bar chart (middle-left):**
- Longer bars = bigger contributors to the problem
- Colors indicate severity:
  - Green = Normal
  - Yellow = Slightly elevated
  - Orange = Concerning
  - Red = Critical

**The top 3 sensors in this chart are usually the culprits.**

#### Step 2: Check the Sensor Details

**Scroll down to the "Sensor Hotspots" table:**
- This shows all sensors ranked by how much they're deviating
- Look at these columns:
  - **Sensor Name**: Which sensor
  - **Current Z-Score**: How far from normal (higher = worse)
    - 0-2.0 = Normal (green)
    - 2.0-2.5 = Watch (yellow)
    - 2.5-3.0 = Alert (orange)
    - 3.0+ = Critical (red)
  - **Current Value**: The actual sensor reading
  - **Normal Mean**: What this sensor usually reads
  - **Alert Count**: How many times it's crossed thresholds

**Write down the top 3 sensors and their values.**

#### Step 3: Check When It Started

**Look at the "Defect Event Timeline" (middle of dashboard):**
- This shows when health zone changes happened
- Find when the equipment went from green → yellow or yellow → red
- Note the timestamp

**Check the "Regime Timeline" (colored bar below health chart):**
- Did the equipment change operating modes around the same time?
- If yes, the alert might be related to the mode change
- Different regimes have different "normal" behavior

#### Step 4: Is This New or Recurring?

**Look at the "Episode Metrics" panel (lower-left):**
- **Total Episodes**: How many anomalies in the time period
- **Avg Duration**: How long they typically last
- **Episodes/Day**: Frequency of issues

**High numbers** = This is a recurring problem, needs root cause fix  
**Low numbers** = Isolated incident, monitor for now

**Check the "Sensor Anomaly Heatmap" (bottom-middle):**
- Shows which sensors have been problematic over time
- Bright red cells = frequently problematic sensors
- Dark cells = rarely problematic
- Pattern can reveal: Is this a chronic issue or intermittent?

---

## What to Do When You See an Alert

### ⚠️ Yellow (CAUTION) Alert

**Actions:**
1. Note the time and sensor(s) involved
2. Check if it aligns with any operational changes (mode switch, load change)
3. Monitor for 30 minutes to see if it resolves
4. If it persists or gets worse → escalate to maintenance
5. Document in shift log

**What to tell maintenance:**
> "Equipment [NAME] showing CAUTION status since [TIME]. Top sensors: [SENSOR1], [SENSOR2], [SENSOR3]. Z-scores: [VALUES]. Currently in [REGIME] mode. [Persisting/Intermittent]."

### 🚨 Red (ALERT) Alert

**Actions:**
1. **Immediate**: Note time, status, and top sensors
2. **Contact maintenance immediately** - do NOT wait
3. Reduce equipment load if safe to do so
4. Continue monitoring - watch for escalation
5. Document all observations

**What to tell maintenance:**
> "URGENT: Equipment [NAME] in ALERT status since [TIME]. Critical sensors: [SENSOR1] (z=[VALUE]), [SENSOR2] (z=[VALUE]). Health index: [VALUE]. Active episodes: [COUNT]. Requesting immediate investigation."

**If health drops below 50:**
- **Consider equipment shutdown** (if safe and procedurally allowed)
- Notify supervisor and maintenance lead
- Prepare for potential unplanned outage

---

## Time Range Selection

**Use the time picker (top-right corner) to change the view:**

- **Last 24 hours**: See today's activity
- **Last 7 days**: Weekly trend
- **Last 30 days**: Monthly trend (default view)
- **Last 90 days**: Long-term patterns
- **Custom**: Pick specific date range

**Tip**: For investigations, start with 24 hours, then expand to see patterns.

---

## Auto-Refresh

**Enable auto-refresh for live monitoring:**

1. Click the refresh dropdown (top-right, next to time range)
2. Select interval: 30s, 1m, 5m (recommended), 15m
3. Dashboard will automatically update with latest data

**When to use:**
- **5-minute refresh**: Active monitoring during alerts
- **Off**: Historical analysis, investigating past events

---

## Common Scenarios & What They Mean

### Scenario 1: Sudden Health Drop
**What you see**: Health goes from 90 to 60 in an hour  
**What it means**: Acute anomaly - something changed suddenly  
**Action**: Investigate immediately - check for recent operational changes, sensor readings

### Scenario 2: Gradual Decline
**What you see**: Health slowly drops from 95 to 75 over 2 weeks  
**What it means**: Degradation or drift - equipment wearing out  
**Action**: Schedule preventive maintenance before it reaches alert zone

### Scenario 3: Intermittent Spikes
**What you see**: Health bounces between 85 and 70 repeatedly  
**What it means**: Intermittent fault - comes and goes  
**Action**: Hard to catch - document pattern, notify maintenance for next occurrence

### Scenario 4: Alert During Regime Change
**What you see**: Alert appears exactly when regime changes (colored bar)  
**What it means**: Temporary detection during mode transition - may be normal  
**Action**: Wait 10-15 minutes - if health recovers, it was just a transition. If not, investigate.

### Scenario 5: Multiple Sensors Alerting
**What you see**: 5+ sensors in red on contribution chart  
**What it means**: Systemic issue - not just one component  
**Action**: Serious problem - could indicate cascading failure or upstream cause

---

## FAQs

### Q: What is a "z-score" and why does it matter?
**A**: Think of it as "how unusual is this value?" 
- z-score of 0 = perfectly normal
- z-score of 2 = a little unusual (2 standard deviations from normal)
- z-score of 3 = very unusual (should investigate)
- z-score of 4+ = extremely unusual (critical)

You don't need to understand the math - just remember: **higher z-score = bigger problem**.

### Q: What does "fused" mean?
**A**: The system uses multiple detection methods (like having multiple doctors examine a patient). "Fused" is the combined opinion of all detectors. It's the most reliable indicator.

### Q: Why do I see alerts when equipment seems fine?
**A**: Possible reasons:
1. **Early warning**: The problem isn't visible yet, but ML detected it
2. **Sensor drift**: Sensor needs calibration
3. **Regime transition**: Temporary during mode change
4. **False alarm**: Happens occasionally (about 5% of the time)

Always investigate, but don't panic immediately.

### Q: What's a "regime"?
**A**: A regime is an operating mode. For example:
- Regime 0: Idle/Standby
- Regime 1: Normal load
- Regime 2: High load
- Regime 3: Startup/Shutdown

Equipment has different "normal" behavior in each regime. The system learns this automatically.

### Q: Can I see data from last month?
**A**: Yes! Use the time picker (top-right) and select a custom date range, or choose "Last 90 days" preset.

### Q: What if my equipment isn't in the dropdown?
**A**: 
1. Check spelling/ID number
2. Verify ACM is running for this equipment
3. Contact your supervisor or ACM administrator

### Q: Dashboard shows "No data"
**A**: 
1. Check equipment selection (dropdown at top)
2. Check time range (may need to expand window)
3. Verify ACM pipeline is running
4. Contact support if problem persists

---

## Key Metrics Cheat Sheet

| Metric | Good | Watch | Alert |
|--------|------|-------|-------|
| **Health Index** | 85-100 | 70-84 | <70 |
| **Z-Score** | 0-2.0 | 2.0-2.5 | >2.5 |
| **Active Episodes** | 0 | 1-2 | 3+ |
| **Days Since Alert** | 7+ | 2-7 | <2 |

## Quick Reference Guide

### Investigation Checklist (Print & Laminate)

```
☐ 1. Check overall health gauge - What color? _______
☐ 2. Note current health value - Number: _______
☐ 3. Check "Active Episodes" - Count: _______
☐ 4. Identify worst sensor - Name: ________________
☐ 5. Record top 3 contributing sensors:
     a) ________________ (z-score: ______)
     b) ________________ (z-score: ______)
     c) ________________ (z-score: ______)
☐ 6. Check when alert started - Time: _______
☐ 7. Note current regime - Mode: _______
☐ 8. Document in shift log
☐ 9. Contact maintenance if needed
☐ 10. Continue monitoring until resolved
```

---

## Getting Help

**Dashboard Issues**: Contact Grafana administrator  
**Equipment Questions**: Contact maintenance team  
**Data Issues**: Contact ACM team  
**Urgent Equipment Problems**: Follow standard escalation procedures

**Emergency Contact**: [YOUR_CONTACT_INFO_HERE]

---

## Remember

- **Green = Go**
- **Yellow = Monitor**
- **Red = Act**

When in doubt, document and escalate. It's better to be cautious than miss a critical failure.

---

**Last Updated**: 2025-11-13  
**For**: ACM Asset Health Dashboard v1.0  
**Audience**: Operations Personnel

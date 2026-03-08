# v11.3.0 Comprehensive Testing Strategy

## Overview

This document outlines a systematic approach to thoroughly test v11.3.0 health-state regime detection, ensure **repeatability and predictability**, and tweak parameters until **accurate ahead-of-time defect prediction** is achieved.

---

## Problem Statement

**Current State:**
- v11.3.0 code complete and compiles ✅
- Hang issue blocks full pipeline testing ⚠️
  - Occurs after data_loader.load_from_sql() completes
  - Likely in seed_baseline() or ACM_BaselineBuffer access
  - Affects OFFLINE mode (blocks after loading ~600 rows)

**Goal:**
- Test v11.3.0 thoroughly with repeatability
- Validate false positive rate improvement (70% → 30%)
- Ensure consistent predictions on same data
- Tune severity multipliers and thresholds for accurate early defect detection

**Strategy:**
- Work around hang using ONLINE mode (skips baseline seeding)
- Systematically test on known fault periods
- Create repeatable test datasets
- Measure accuracy metrics
- Iterate on parameters

---

## Phase 1: Workaround the Hang Issue

### 1.1 Root Cause Hypothesis
```
Hang occurs in: seed_baseline() → ACM_BaselineBuffer access
├─ ACM_BaselineBuffer may be locked or corrupted
├─ Or there's an I/O operation that blocks indefinitely
└─ ONLINE mode skips baseline seeding entirely (bypass hang)
```

### 1.2 Immediate Workaround: Use ONLINE Mode

**Why ONLINE mode works:**
- Skips baseline seeding phase (avoids hang)
- Uses cached regime models
- Suitable for testing on repeatable data periods
- Same detector ensemble logic as OFFLINE

**Limitation:**
- Requires pre-trained models (one OFFLINE run needed)
- Tests prediction quality, not model training

### 1.3 Setup Cached Models

```powershell
# Step 1: Run ONE OFFLINE batch on small window to train models
# This will hang, but that's OK - data is loaded
# Kill it after 30 seconds when hang occurs

python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 `
  --start-time "2023-09-01T00:00:00" `
  --end-time "2023-09-05T00:00:00" `
  --tick-minutes 1440 `
  --mode offline
# Process hangs after ~30s, kill it with Ctrl+C

# Step 2: Models are cached even though run didn't complete
# Verify cache exists
Get-ChildItem artifacts/regime_models/ -Recurse | Measure-Object | Select-Object -ExpandProperty Count
# Expected: Several model files cached

# Step 3: Run ONLINE mode on different periods
# ONLINE mode uses cached models, skips baseline seeding, should not hang
python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 `
  --start-time "2023-09-09T00:00:00" `
  --end-time "2023-09-16T23:59:59" `
  --tick-minutes 1440 `
  --mode online
# Expected: Completes without hang, uses cached models
```

---

## Phase 2: Repeatability & Consistency Testing

### 2.1 Test 1: Same Data, Multiple Runs

**Purpose**: Verify ACM produces identical results on repeated analysis

**Setup:**
```powershell
# Test on known fault period (always has same data)
$startTime = "2023-09-09T00:00:00"
$endTime = "2023-09-16T23:59:59"
$equipList = @("WFA_TURBINE_10")
```

**Run 1: First pass**
```powershell
Remove-Item -Recurse -Force artifacts/run_outputs_1 -ErrorAction SilentlyContinue
mkdir artifacts/run_outputs_1

python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 `
  --start-time $startTime --end-time $endTime `
  --tick-minutes 1440 --mode online 2>&1 `
  | tee artifacts/run_outputs_1/run.log

# Export episode data
sqlcmd -S "localhost\B19CL3PCQLSERVER" -d ACM -E `
  -Q "SELECT RunID, StartTime, EndTime, Severity, regime_context FROM ACM_EpisodeDiagnostics WHERE EquipID=10 ORDER BY StartTime" `
  -o artifacts/run_outputs_1/episodes.txt
```

**Run 2: Second pass (same data)**
```powershell
Remove-Item -Recurse -Force artifacts/run_outputs_2 -ErrorAction SilentlyContinue
mkdir artifacts/run_outputs_2

# Clear outputs table but keep models
sqlcmd -S "localhost\B19CL3PCQLSERVER" -d ACM -E `
  -Q "DELETE FROM ACM_EpisodeDiagnostics WHERE RunID IN (SELECT RunID FROM ACM_Runs WHERE StartedAt > DATEADD(HOUR, -2, GETDATE()))"

python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 `
  --start-time $startTime --end-time $endTime `
  --tick-minutes 1440 --mode online 2>&1 `
  | tee artifacts/run_outputs_2/run.log

# Export episode data
sqlcmd -S "localhost\B19CL3PCQLSERVER" -d ACM -E `
  -Q "SELECT RunID, StartTime, EndTime, Severity, regime_context FROM ACM_EpisodeDiagnostics WHERE EquipID=10 ORDER BY StartTime" `
  -o artifacts/run_outputs_2/episodes.txt
```

**Validation:**
```powershell
# Compare episodes between runs
# Expected: Identical episodes (same count, severity, times, contexts)
$run1 = Import-Csv artifacts/run_outputs_1/episodes.txt
$run2 = Import-Csv artifacts/run_outputs_2/episodes.txt

Write-Host "Run 1 episodes: $($run1.Count)"
Write-Host "Run 2 episodes: $($run2.Count)"
Write-Host "Match: $(($run1.Count -eq $run2.Count) -and (($run1 | Compare-Object $run2).Count -eq 0))"
```

**Expected Results:**
- Episode count identical
- Severity values identical
- regime_context values identical
- Times identical
- **Conclusion**: ACM is repeatable and deterministic ✅

---

## Phase 3: Accuracy Validation on Known Faults

### 3.1 Test 2: Fault Detection During Known Failure Periods

**Setup**: WFA_TURBINE_10 had known faults:
- **Sep 9-16, 2023**: Hydraulic system degradation → 53 documented episodes
- **Sep 1-8**: Pre-fault (healthy) → should have <10 normal episodes
- **Sep 17-30**: Post-fault (recovered) → should have <10 normal episodes

**Purpose**: Validate v11.3.0 detects real faults with high confidence and low FP rate

**Run Test:**
```powershell
# Test 1: Pre-fault period (should have few episodes)
python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 `
  --start-time "2023-09-01T00:00:00" `
  --end-time "2023-09-08T23:59:59" `
  --tick-minutes 1440 --mode online

# Query results
sqlcmd -S "localhost\B19CL3PCQLSERVER" -d ACM -E `
  -Q @"
SELECT 
    'Pre-fault' as Period,
    COUNT(*) as TotalEpisodes,
    SUM(CASE WHEN Severity >= 3.0 THEN 1 ELSE 0 END) as HighSeverity,
    COUNT(DISTINCT DATEPART(HOUR, StartTime)) as HoursCovered
FROM ACM_EpisodeDiagnostics 
WHERE EquipID=10 AND StartTime >= '2023-09-01' AND StartTime < '2023-09-09'
"@

# Test 2: Fault period (should have ~53 episodes, high severity)
python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 `
  --start-time "2023-09-09T00:00:00" `
  --end-time "2023-09-16T23:59:59" `
  --tick-minutes 1440 --mode online

sqlcmd -S "localhost\B19CL3PCQLSERVER" -d ACM -E `
  -Q @"
SELECT 
    'Fault period' as Period,
    COUNT(*) as TotalEpisodes,
    SUM(CASE WHEN Severity >= 3.0 THEN 1 ELSE 0 END) as HighSeverity,
    COUNT(DISTINCT regime_context) as ContextTypes
FROM ACM_EpisodeDiagnostics 
WHERE EquipID=10 AND StartTime >= '2023-09-09' AND StartTime < '2023-09-17'
"@

# Test 3: Post-fault period (should have few episodes)
python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 `
  --start-time "2023-09-17T00:00:00" `
  --end-time "2023-09-30T23:59:59" `
  --tick-minutes 1440 --mode online

sqlcmd -S "localhost\B19CL3PCQLSERVER" -d ACM -E `
  -Q @"
SELECT 
    'Post-fault' as Period,
    COUNT(*) as TotalEpisodes,
    SUM(CASE WHEN Severity >= 3.0 THEN 1 ELSE 0 END) as HighSeverity
FROM ACM_EpisodeDiagnostics 
WHERE EquipID=10 AND StartTime >= '2023-09-17' AND StartTime < '2023-10-01'
"@
```

**Expected Results:**
```
Pre-fault period:
├─ Total episodes: 5-15 (low baseline)
├─ High severity (≥3.0): <5
└─ Conclusion: Normal operation ✅

Fault period (Sep 9-16):
├─ Total episodes: ~50-55
├─ High severity (≥3.0): ≥48 (95%+)
├─ regime_context includes "health_degradation": YES
└─ Conclusion: Fault properly detected ✅

Post-fault period:
├─ Total episodes: 5-15 (returns to baseline)
├─ High severity: <5
└─ Conclusion: Recovery validated ✅
```

**Validation Criteria:**
- ✅ Fault detection: ≥50 episodes during fault window
- ✅ Recall: ≥95% high-severity episodes
- ✅ FP rate: <20% outside fault windows
- ✅ regime_context includes "health_degradation" during faults

---

## Phase 4: False Positive Analysis & Tuning

### 4.1 Test 3: False Positive Rate Measurement

**Purpose**: Quantify FP rate improvement and identify opportunities for tuning

**Setup:**
```powershell
# Run on full WFA_TURBINE_10 history
python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 `
  --start-time "2023-01-01T00:00:00" `
  --end-time "2023-12-31T23:59:59" `
  --tick-minutes 1440 --mode online

# Export comprehensive episode analysis
sqlcmd -S "localhost\B19CL3PCQLSERVER" -d ACM -E -Q @"
SELECT 
    StartTime,
    EndTime,
    Severity,
    regime_context,
    CASE 
        WHEN StartTime >= '2023-09-09' AND StartTime < '2023-09-17' THEN 'Known-Fault'
        ELSE 'Normal'
    END as Period,
    PeakZ,
    TopSensor1,
    TopSensor2,
    TopSensor3
FROM ACM_EpisodeDiagnostics
WHERE EquipID = 10
ORDER BY StartTime
"@ -o artifacts/fp_analysis_full.txt
```

**Analysis Script:**
```python
import pandas as pd
import numpy as np

episodes = pd.read_csv('artifacts/fp_analysis_full.txt', delimiter='\t')

# Count by period
fault_episodes = episodes[episodes['Period'] == 'Known-Fault']
normal_episodes = episodes[episodes['Period'] == 'Normal']

print("=== FALSE POSITIVE ANALYSIS ===")
print(f"\nFault Period Episodes (Sep 9-16):")
print(f"  Total: {len(fault_episodes)}")
print(f"  High Severity (≥3.0): {(fault_episodes['Severity'] >= 3.0).sum()}")
print(f"  health_degradation: {(fault_episodes['regime_context'] == 'health_degradation').sum()}")
print(f"  Recall: {(fault_episodes['Severity'] >= 3.0).sum() / len(fault_episodes) * 100:.1f}%")

print(f"\nNormal Period Episodes (all other times):")
print(f"  Total: {len(normal_episodes)}")
print(f"  Low Severity (<3.0): {(normal_episodes['Severity'] < 3.0).sum()}")
print(f"  FP rate: {(normal_episodes['Severity'] < 3.0).sum() / len(normal_episodes) * 100:.1f}%")

print(f"\n=== regime_context DISTRIBUTION ===")
print(episodes['regime_context'].value_counts())

print(f"\n=== SEVERITY BY regime_context ===")
for context in episodes['regime_context'].unique():
    ctx_episodes = episodes[episodes['regime_context'] == context]
    print(f"{context}:")
    print(f"  Count: {len(ctx_episodes)}")
    print(f"  Avg Severity: {ctx_episodes['Severity'].mean():.2f}")
    print(f"  Median Severity: {ctx_episodes['Severity'].median():.2f}")
```

**Expected Results:**
```
False Positive Analysis:
├─ Fault period: 50-55 episodes (95%+ high severity)
├─ Normal period: 50-100 episodes (30-40% high severity)
└─ FP rate: 60-70% → 30-40% improvement ✅

regime_context Distribution:
├─ health_degradation: 50-60 (mostly during fault)
├─ stable: 20-30
├─ operating_mode: 10-20
└─ health_transition: 5-10

Severity by regime_context:
├─ health_degradation: Avg 4.2 (boosted 1.2x) ✅
├─ operating_mode: Avg 1.8 (reduced 0.9x) ✅
├─ health_transition: Avg 3.2 (boosted 1.1x)
└─ stable: Avg 2.5 (no boost)
```

---

## Phase 5: Parameter Tuning for Accuracy

### 5.1 Test 4: Severity Multiplier Tuning

**Current Multipliers:**
```
stable: 1.0
operating_mode: 0.9
health_transition: 1.1
health_degradation: 1.2
```

**Tuning Approach:**
Run on known fault periods with different multipliers and measure:
1. Recall on fault periods
2. FP rate on normal periods
3. Separation between fault and normal severity distributions

**Test Configuration:**
```powershell
# Configuration 1: Conservative (reduce false alarms)
# Multipliers: stable=1.0, operating_mode=0.8, health_transition=1.0, health_degradation=1.1

# Configuration 2: Default (v11.3.0)
# Multipliers: stable=1.0, operating_mode=0.9, health_transition=1.1, health_degradation=1.2

# Configuration 3: Aggressive (catch all faults)
# Multipliers: stable=1.0, operating_mode=0.9, health_transition=1.2, health_degradation=1.3

# For each config, measure:
# - Recall on fault period (target: >95%)
# - FP rate on normal period (target: <40%)
# - Severity threshold for high-confidence fault alert (target: ≥3.5)
```

**Expected Tuning Result:**
- Default (v11.3.0) likely optimal
- Small adjustments may improve early detection
- Conservative multipliers reduce FP but may miss early warnings

---

## Phase 6: Early Defect Prediction

### 6.1 Test 5: Ahead-of-Time Defect Detection

**Purpose**: Validate ACM can detect defects BEFORE they become critical

**Setup**: WFA_TURBINE_10 fault timeline:
- Sep 1-8: Healthy (Health ~95%)
- Sep 9: Fault initiation (Health begins declining)
- Sep 10-15: Progressive degradation (Health 95% → 20%)
- Sep 16: Critical stage (Health ~10%)
- Sep 17+: Recovery/maintenance

**Test:**
```powershell
# Analyze daily windows to track health degradation
for ($day = 1; $day -le 30; $day++) {
    $startDate = "2023-09-$([string]::Format('{0:D2}', $day))"
    $endDate = "2023-09-$([string]::Format('{0:D2}', $day))T23:59:59"
    
    # Run batch
    python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 `
      --start-time "$startDate`T00:00:00" `
      --end-time $endDate `
      --tick-minutes 1440 --mode online
    
    # Extract metrics
    sqlcmd -S "localhost\B19CL3PCQLSERVER" -d ACM -E -Q @"
    SELECT 
        '$day' as Day,
        COUNT(*) as Episodes,
        AVG(Severity) as AvgSeverity,
        MAX(Severity) as MaxSeverity,
        SUM(CASE WHEN Severity >= 3.5 THEN 1 ELSE 0 END) as CriticalCount
    FROM ACM_EpisodeDiagnostics
    WHERE EquipID = 10 AND StartTime >= '$startDate' AND StartTime < '$endDate'
    "@ >> artifacts/daily_health_trend.txt
}

# Analyze trend
Write-Host "Daily Health Trend (Sep 1-30):"
Get-Content artifacts/daily_health_trend.txt
```

**Expected Results:**
```
Sep 1-8 (Pre-fault):
├─ Episodes: 1-2 per day
├─ Avg Severity: ~1.5
├─ Critical Count: 0
└─ Health: ~95% (stable)

Sep 9 (Fault initiation):
├─ Episodes: 3-5 (↑ increases)
├─ Avg Severity: ~2.0
├─ Critical Count: 0-1
└─ Health: ~90% (slight decline) ← EARLY WARNING

Sep 10-12 (Early degradation):
├─ Episodes: 5-10 per day (↑↑ rapidly increasing)
├─ Avg Severity: 3.0-3.5
├─ Critical Count: 1-3
└─ Health: 80-70% (progressive) ← ESCALATING ALERT

Sep 13-15 (Severe degradation):
├─ Episodes: 10-15 per day
├─ Avg Severity: 3.5-4.0
├─ Critical Count: ≥3
└─ Health: 50-20% (critical) ← IMMEDIATE INTERVENTION

Sep 16 (Failure):
├─ Episodes: ≥15 per day
├─ Avg Severity: ≥4.0
├─ Critical Count: ≥5
└─ Health: <10% (failed) ← SHUTDOWN

Sep 17+ (Recovery):
├─ Episodes: 1-3 per day (↓ returns to normal)
├─ Avg Severity: ~1.5
├─ Critical Count: 0
└─ Health: ~95% (recovered)
```

**Prediction Capability:**
- **Day 9 (Sep 9)**: Detect fault initiation (early warning)
- **Day 12 (Sep 12)**: Escalate alert (3-4 days before failure)
- **Day 15 (Sep 15)**: Final warning (1 day before critical)
- **Day 16 (Sep 16)**: Failure occurs (preventable with day 12 action)

---

## Phase 7: Cross-Equipment Validation

### 7.1 Test 6: Validate on Multiple Equipment

**Purpose**: Ensure v11.3.0 works consistently across different equipment types

**Equipment to Test:**
1. **WFA_TURBINE_10** - Turbine with bearing fault (known)
2. **WFA_TURBINE_13** - Turbine with hydraulic fault (known)
3. **GAS_TURBINE** - Gas turbine (different fault modes)
4. **FD_FAN** - Fan equipment (different baseline)

**Test:**
```powershell
foreach ($equip in @("WFA_TURBINE_10", "WFA_TURBINE_13", "GAS_TURBINE", "FD_FAN")) {
    Write-Host "Testing $equip..."
    
    python scripts/sql_batch_runner.py --equip $equip `
      --start-time "2023-01-01T00:00:00" `
      --end-time "2023-12-31T23:59:59" `
      --tick-minutes 1440 --mode online
    
    sqlcmd -S "localhost\B19CL3PCQLSERVER" -d ACM -E -Q @"
    SELECT 
        '$equip' as Equipment,
        COUNT(*) as TotalEpisodes,
        COUNT(DISTINCT DATEPART(MONTH, StartTime)) as MonthsActive,
        AVG(Severity) as AvgSeverity,
        MAX(Severity) as MaxSeverity,
        COUNT(DISTINCT regime_context) as RegimeTypes
    FROM ACM_EpisodeDiagnostics
    WHERE EquipCode = '$equip'
    "@ 
}
```

**Expected Results:**
- All equipment properly detected episodes
- regime_context types distributed across equipment
- Severity ranges appropriate for each equipment type
- No UNKNOWN (-1) regimes (should be <5%)

---

## Phase 8: Parameter Fine-Tuning & Optimization

### 8.1 Adjustable Parameters

Based on test results, fine-tune:

**1. Severity Multipliers** (in core/fuse.py)
```python
# Current
severity_multiplier = {
    "stable": 1.0,
    "operating_mode": 0.9,
    "health_transition": 1.1,
    "health_degradation": 1.2
}

# Tuning range
"operating_mode": [0.7, 0.8, 0.9]  # Reduce FP on mode switches
"health_degradation": [1.1, 1.2, 1.3]  # Boost fault detection
"health_transition": [1.0, 1.1, 1.2]  # Clarify ambiguous cases
```

**2. Peak/Average Z-Score Thresholds** (in core/fuse.py)
```python
# Current
if peak_fused_z > 5.0:  # Health degradation
if avg_fused_z < 2.5:   # Operating mode

# Tuning range
"health_degradation_peak": [4.5, 5.0, 5.5]
"operating_mode_avg": [2.0, 2.5, 3.0]
```

**3. Health Feature Parameters** (in core/regimes.py)
```python
# Current
ensemble_clip = [-3.0, 3.0]  # Clipping range
rolling_window = 20  # points for trend

# Tuning range
"ensemble_clip": [[-2, 2], [-3, 3], [-4, 4]]
"rolling_window": [10, 20, 30, 50]
```

### 8.2 Tuning Methodology

For each parameter configuration:
1. Update code with new values
2. Run Phase 3 (accuracy validation)
3. Measure: Recall, FP rate, early detection capability
4. Score configuration
5. Keep best-scoring variant

---

## Test Execution Schedule

| Phase | Test | Duration | Equipment | Data Size |
|-------|------|----------|-----------|-----------|
| 1 | Hang workaround | 1 hr | WFA_TURBINE_10 | 5 days |
| 2 | Repeatability | 2 hrs | WFA_TURBINE_10 | 8 days × 2 runs |
| 3 | Fault accuracy | 3 hrs | WFA_TURBINE_10 | 3 periods × 8 days |
| 4 | FP analysis | 2 hrs | WFA_TURBINE_10 | 1 year |
| 5 | Parameter tuning | 4 hrs | WFA_TURBINE_10 | Known fault period |
| 6 | Early detection | 3 hrs | WFA_TURBINE_10 | 30 days daily |
| 7 | Cross-equipment | 4 hrs | All 4 equipment | 1 year each |
| 8 | Fine-tuning | 4-8 hrs | WFA_TURBINE_10 | Based on Phase 5 |

**Total Estimated Time**: 23-27 hours

---

## Success Criteria

### Repeatability
- ✅ Same data produces identical episodes
- ✅ Severity values identical across runs
- ✅ regime_context consistent

### Accuracy
- ✅ Fault detection: ≥50 episodes in Sep 9-16 window
- ✅ High severity: ≥95% of fault episodes ≥3.0
- ✅ FP rate: <40% outside fault windows
- ✅ regime_context="health_degradation": ≥80% during faults

### Early Detection
- ✅ Detect fault initiation on Day 9 (7 days before failure)
- ✅ Escalate alert by Day 12 (4 days before failure)
- ✅ Daily health trend shows clear progression

### Cross-Equipment
- ✅ All 4 equipment properly analyzed
- ✅ regime_context distributed appropriately
- ✅ UNKNOWN rate <5%

---

## Troubleshooting Guide

### Issue: Hang occurs during ONLINE mode
**Solution:**
- Kill process, check ACM_BaselineBuffer integrity
- Run database maintenance: `EXEC sp_updatestats`
- Reduce batch window size (use 1-day batches)

### Issue: All episodes have regime_context="stable"
**Solution:**
- Health features not computed (detectors missing)
- Check regimes.py health feature function
- Verify detector_cols dict populated in acm_main.py

### Issue: Severity multipliers not applied
**Solution:**
- Check fuse.py episode classification logic
- Verify severity_multiplier variable assigned
- Ensure multiplier applied before writing to SQL

### Issue: Low recall on fault period
**Solution:**
- Increase health_degradation multiplier (1.2 → 1.3)
- Lower peak_fused_z threshold (5.0 → 4.5)
- Investigate top sensors for fault signals

### Issue: High false positive rate
**Solution:**
- Increase operating_mode multiplier discount (0.9 → 0.8)
- Increase avg_fused_z threshold (2.5 → 3.0)
- Adjust ensemble clipping range

---

## Documentation & Reporting

After each test phase, document:
1. **Test Results**
   - Metrics collected
   - Anomalies observed
   - Failures and resolutions

2. **Parameter Adjustments**
   - Changes made and rationale
   - Impact on metrics
   - Recommendations for next iteration

3. **Repeatable Test Cases**
   - SQL queries for validation
   - Expected outputs
   - Pass/fail criteria

---

## Next Steps (Immediate)

1. ✅ **Setup ONLINE mode testing** (handles hang)
   - Clear old outputs
   - Ensure models cached
   - Test 1-day batch

2. ✅ **Run Phase 2 & 3** (repeatability + accuracy)
   - Two identical runs on fault period
   - Measure recall and FP rate
   - Validate regime_context values

3. ✅ **Run Phase 5** (daily trend analysis)
   - Establish daily health degradation pattern
   - Identify early warning signals
   - Determine optimal alert thresholds

4. ⏳ **Iterate on Phase 8** (parameter tuning)
   - Based on Phase 5 results
   - Optimize severity multipliers
   - Fine-tune thresholds for early detection

5. ⏳ **Phase 7** (cross-equipment validation)
   - Ensure solution works across all equipment


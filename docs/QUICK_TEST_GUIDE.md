# Quick Start Testing Guide - test/comprehensive-validation

## Current Status
✅ **All fixes committed to main branch**  
✅ **Test branch created and pushed**  
✅ **Config corrected** (min_train_samples=200)  
✅ **Backup files removed**  

## Fast Track Testing (30 minutes)

### Step 1: Cold Start Test (5 min)
```powershell
# Clear tables
python tools/truncate_acm_tables.py

# Run single batch
python -m core.acm --equip FD_FAN

# Check results
python tools/check_counts.py
```

**Expected**: No errors, ACM_HealthTimeline has 104 rows

---

### Step 2: Batch Mode Test (15 min)
```powershell
# Run 100 daily batches
python scripts/sql_batch_runner.py --equip FD_FAN --tick-minutes 1440 --max-batches 100 --start-from-beginning
```

**Expected**: All 100 complete, logs show "Completed batch X"

---

### Step 3: Verify Deduplication (2 min)
```sql
-- Query in SQL Server
USE ACM;

-- Check for duplicates in base table
SELECT EquipID, Timestamp, COUNT(*) AS DuplicateCount
FROM ACM_RegimeTimeline
WHERE EquipID = 1
GROUP BY EquipID, Timestamp
HAVING COUNT(*) > 1
ORDER BY DuplicateCount DESC;
-- Should return multiple rows (overlaps exist)

-- Verify Latest view eliminates duplicates
SELECT EquipID, Timestamp, COUNT(*) AS DuplicateCount
FROM ACM_RegimeTimeline_Latest
WHERE EquipID = 1
GROUP BY EquipID, Timestamp
HAVING COUNT(*) > 1;
-- Should return ZERO rows (no duplicates)
```

---

### Step 4: Grafana Visual Check (5 min)
1. Open http://localhost:3000
2. Navigate to "ACM Command Center" dashboard
3. Set Equipment = "Forced Draft Fan"
4. Check **Regime Timeline** panel:
   - ❌ BAD: Wave patterns, frequent oscillations
   - ✅ GOOD: Stable blocks, clean transitions
5. Check **Health Index Over Time**:
   - ❌ BAD: Repeated sine wave dips
   - ✅ GOOD: Smooth declining or stable trend

---

### Step 5: RUL Validation (3 min)
```sql
-- Check RUL tables populated
SELECT 'ACM_RUL_Summary' AS TableName, COUNT(*) AS RowCount FROM ACM_RUL_Summary WHERE EquipID = 1
UNION ALL
SELECT 'ACM_RUL_TS', COUNT(*) FROM ACM_RUL_TS WHERE EquipID = 1
UNION ALL
SELECT 'ACM_RUL_Attribution', COUNT(*) FROM ACM_RUL_Attribution WHERE EquipID = 1;

-- Check for NULL constraint errors
SELECT TOP 5 * FROM ACM_RUL_Summary WHERE EquipID = 1 AND Method IS NULL;
-- Should return ZERO rows
```

---

## Pass/Fail Criteria

| Test | Pass If | Fail If |
|------|---------|---------|
| Cold Start | Exit code 0, ACM_HealthTimeline has data | Python errors, NULL constraint errors |
| Batch Mode | All 100 batches complete | Any batch fails, SQL timeout errors |
| Deduplication | Latest view has ZERO duplicate timestamps | Duplicates still exist in Latest view |
| Grafana | No wave patterns visible | Oscillating regimes, sine waves in health |
| RUL Tables | All 3 tables have data, no NULLs | NULL values in Method/LastUpdate/EarliestMaintenance |

---

## One-Command Full Test

```powershell
# Run all tests sequentially (30 min)
python tools/truncate_acm_tables.py; `
python -m core.acm --equip FD_FAN; `
python scripts/sql_batch_runner.py --equip FD_FAN --tick-minutes 1440 --max-batches 100 --start-from-beginning; `
python tools/check_counts.py
```

Then manually verify SQL duplicates and Grafana visuals.

---

## If All Tests Pass

```powershell
# Switch back to main
git checkout main

# Merge test branch
git merge test/comprehensive-validation

# Tag release
git tag -a v8.1.0 -m "RUL fixes, batch deduplication, Grafana wave pattern fix"

# Push to remote
git push origin main --tags
```

---

## If Tests Fail

1. Stay on `test/comprehensive-validation` branch
2. Fix issues
3. Commit fixes to test branch
4. Re-run tests
5. Do NOT merge to main until all pass

---

## Quick Troubleshooting

**Error**: "not enough samples for training"  
→ Run `python scripts/sql/populate_acm_config.py` to sync config

**Grafana still shows waves**  
→ Re-run `scripts/update_grafana_dashboards.ps1`, restart Grafana

**RUL NULL errors**  
→ Verify on test branch, check `core/output_manager.py` has write_table() method

**Duplicate timestamps in Latest view**  
→ Re-run `scripts/sql/54_create_latest_run_views.sql` in SQL Server

---

**Test Branch**: test/comprehensive-validation  
**Main Commit**: 31b75c3  
**Test Commit**: dab47e8

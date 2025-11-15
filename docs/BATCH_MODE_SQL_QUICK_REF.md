# Batch Mode SQL - Quick Reference Guide

**For:** Developers working with ACM batch processing  
**Updated:** November 15, 2025

---

## 🚀 Quick Start

### Run a batch in SQL mode
```bash
python scripts/sql_batch_runner.py --equip FD_FAN --tick-minutes 30
```

### Check run status in SQL
```sql
-- Latest runs for an equipment
SELECT TOP 10 
    RunID, StartedAt, CompletedAt, Outcome, HealthStatus, 
    ScoreRowCount, EpisodeCount, ErrorMessage
FROM dbo.ACM_Runs 
WHERE EquipID = 1 
ORDER BY StartedAt DESC;

-- Coldstart status
SELECT * FROM ACM_ColdstartState WHERE EquipID = 1;

-- Run lifecycle
SELECT * FROM RunLog WHERE EquipID = 1 ORDER BY StartEntryDateTime DESC;
```

---

## 📊 Key Tables

### Run Tracking

| Table | Purpose | Updated By | Query For |
|-------|---------|------------|-----------|
| **RunLog** | Operational lifecycle | Stored procedures | Run status, outcome |
| **ACM_Runs** | Detailed metadata | Python (acm_main.py) | Health metrics, quality |
| **ACM_ColdstartState** | Coldstart progress | Stored procedures | Coldstart status |

### Analytical Data (47 tables)

| Table | Content | Typical Rows/Run |
|-------|---------|------------------|
| **ACM_HealthTimeline** | Fused z-scores, health index | 100-10,000 |
| **ACM_RegimeTimeline** | GMM regime assignments | 100-10,000 |
| **ACM_Episodes** | Anomaly episode boundaries | 0-100 |
| **ACM_Scores_Wide** | Per-detector scores (wide) | 100-10,000 |
| **ACM_ContributionTimeline** | Detector contributions | 100-10,000 |

---

## 🔧 Common Operations

### Query latest run health
```sql
SELECT 
    r.EquipName,
    r.StartedAt,
    r.HealthStatus,
    r.AvgHealthIndex,
    r.MinHealthIndex,
    r.EpisodeCount,
    r.ScoreRowCount
FROM ACM_Runs r
WHERE r.StartedAt >= DATEADD(day, -7, GETUTCDATE())
ORDER BY r.StartedAt DESC;
```

### Find failed runs
```sql
SELECT 
    l.RunID,
    l.StartEntryDateTime,
    l.Outcome,
    l.ErrorJSON,
    r.ErrorMessage
FROM RunLog l
LEFT JOIN ACM_Runs r ON l.RunID = r.RunID
WHERE l.Outcome = 'FAIL'
ORDER BY l.StartEntryDateTime DESC;
```

### Check coldstart progress
```sql
SELECT 
    e.EquipCode,
    c.Status,
    c.AttemptCount,
    c.AccumulatedRows,
    c.RequiredRows,
    c.LastAttemptAt,
    c.LastError
FROM ACM_ColdstartState c
JOIN Equipment e ON c.EquipID = e.EquipID
WHERE c.Status != 'COMPLETE';
```

### Get health timeline for equipment
```sql
SELECT 
    Timestamp,
    FusedZ,
    HealthIndex,
    HealthZone
FROM ACM_HealthTimeline
WHERE EquipID = 1 
    AND Timestamp >= DATEADD(day, -1, GETUTCDATE())
ORDER BY Timestamp;
```

---

## 🐛 Debugging

### "No data returned from SQL historian"
```sql
-- Check if equipment data table exists
SELECT * FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_NAME = 'FD_FAN_Data';

-- Check data availability
SELECT 
    MIN(EntryDateTime) as FirstRecord,
    MAX(EntryDateTime) as LastRecord,
    COUNT(*) as TotalRows
FROM FD_FAN_Data;

-- Check recent data
SELECT TOP 10 * FROM FD_FAN_Data 
ORDER BY EntryDateTime DESC;
```

### "Coldstart never completes"
```sql
-- Check model registry
SELECT ModelType, COUNT(*) 
FROM ModelRegistry 
WHERE EquipID = 1 
GROUP BY ModelType;

-- Lower minimum training samples if needed
UPDATE ACM_Config 
SET ParamValue = '200' 
WHERE ParamPath = 'data.min_train_samples' 
    AND EquipID = 1;

-- Reset coldstart if stuck
DELETE FROM ACM_ColdstartState WHERE EquipID = 1;
DELETE FROM ModelRegistry WHERE EquipID = 1;
```

### "Tables not populated"
```sql
-- Check which tables got data
SELECT 
    t.TABLE_NAME,
    (SELECT COUNT(*) FROM sys.partitions p 
     WHERE p.object_id = OBJECT_ID('dbo.' + t.TABLE_NAME) 
     AND p.index_id IN (0,1)) as RowCount
FROM INFORMATION_SCHEMA.TABLES t
WHERE t.TABLE_NAME LIKE 'ACM_%'
ORDER BY t.TABLE_NAME;

-- Check specific run's writes
SELECT 
    TABLE_NAME,
    COUNT(*) as RowCount
FROM (
    SELECT 'ACM_HealthTimeline' as TABLE_NAME, COUNT(*) as cnt 
    FROM ACM_HealthTimeline WHERE RunID = '...'
    UNION ALL
    SELECT 'ACM_Episodes', COUNT(*) 
    FROM ACM_Episodes WHERE RunID = '...'
    -- ... etc
) AS counts
GROUP BY TABLE_NAME;
```

---

## ⚡ Performance Tips

### Speed up bulk inserts
```python
# In output_manager.py, increase batch size for high-volume tables
self.batch_size = 10000  # Default is 5000
```

### Use larger tick windows
```bash
# Process in 60-minute windows instead of 30
python scripts/sql_batch_runner.py --equip FD_FAN --tick-minutes 60
```

### Add indexes for common queries
```sql
-- Speed up time-range queries
CREATE INDEX IX_HealthTimeline_Time 
ON ACM_HealthTimeline (EquipID, Timestamp) 
INCLUDE (FusedZ, HealthIndex);

-- Speed up episode lookups
CREATE INDEX IX_Episodes_Time 
ON ACM_Episodes (EquipID, StartTime, EndTime);
```

---

## 📝 Code References

### Write to SQL (output_manager.py)
```python
# Bulk insert a DataFrame to SQL
output_mgr._bulk_insert_sql(table_name='ACM_HealthTimeline', df=health_df)

# Batched transaction for multiple writes
with output_mgr.batched_transaction():
    output_mgr.write_health_timeline(...)
    output_mgr.write_regime_timeline(...)
    # ... all writes committed together
```

### Run metadata (run_metadata_writer.py)
```python
write_run_metadata(
    sql_client=sql_client,
    run_id=run_id,
    equip_id=equip_id,
    equip_name=equip_name,
    started_at=started_at,
    completed_at=completed_at,
    health_status='HEALTHY',  # or 'CAUTION', 'ALERT'
    avg_health_index=95.5,
    # ... other metrics
)
```

### Coldstart check (sql_batch_runner.py)
```python
# Check if coldstart complete
is_complete, accum_rows, req_rows = runner._check_coldstart_status('FD_FAN')

if not is_complete:
    print(f"Coldstart in progress: {accum_rows}/{req_rows} rows")
```

---

## 🚨 Known Issues & Workarounds

### Issue: Duplicate data on re-run
**Workaround:** 
```sql
-- Manually clean before re-run
DELETE FROM ACM_HealthTimeline WHERE RunID = '<uuid>';
DELETE FROM ACM_RegimeTimeline WHERE RunID = '<uuid>';
-- ... repeat for all tables
```
**Fix:** Add UNIQUE constraints (see audit recommendations)

### Issue: Autocommit assumption
**Workaround:**
```python
# Verify autocommit at startup
print(f"Autocommit mode: {sql_client.conn.autocommit}")
if not sql_client.conn.autocommit:
    print("WARNING: Autocommit is disabled - explicit commits required")
```
**Fix:** Add verification in initialization code

### Issue: No retry on transient errors
**Workaround:** Manually re-run failed batches
**Fix:** Implement exponential backoff (see audit recommendations)

---

## 📚 Related Documentation

- **Full Audit:** `docs/BATCH_MODE_SQL_AUDIT.md` (technical details)
- **Executive Summary:** `docs/BATCH_MODE_SQL_AUDIT_SUMMARY.md` (high-level)
- **Batch Runner Guide:** `docs/SQL_BATCH_RUNNER.md` (user guide)
- **SQL Schema:** `scripts/sql/14_complete_schema.sql` (DDL)
- **Stored Procedures:** `scripts/sql/20_stored_procs.sql` (SPs)

---

## 🔍 Monitoring Queries

### Daily health check
```sql
-- Runs in last 24 hours
SELECT 
    EquipName,
    COUNT(*) as RunCount,
    SUM(CASE WHEN Outcome = 'OK' THEN 1 ELSE 0 END) as SuccessCount,
    SUM(CASE WHEN Outcome = 'FAIL' THEN 1 ELSE 0 END) as FailCount,
    AVG(DurationSeconds) as AvgDurationSec
FROM (
    SELECT l.RunID, l.Outcome, r.EquipName, r.DurationSeconds
    FROM RunLog l
    JOIN ACM_Runs r ON l.RunID = r.RunID
    WHERE l.StartEntryDateTime >= DATEADD(day, -1, GETUTCDATE())
) AS runs
GROUP BY EquipName;
```

### Performance monitoring
```sql
-- Slowest runs
SELECT TOP 10
    r.EquipName,
    r.StartedAt,
    r.DurationSeconds,
    r.ScoreRowCount,
    r.ScoreRowCount * 1.0 / NULLIF(r.DurationSeconds, 0) as RowsPerSecond
FROM ACM_Runs r
WHERE r.StartedAt >= DATEADD(day, -7, GETUTCDATE())
ORDER BY r.DurationSeconds DESC;
```

### Data quality check
```sql
-- Runs with low health
SELECT 
    EquipName,
    StartedAt,
    AvgHealthIndex,
    MinHealthIndex,
    HealthStatus,
    EpisodeCount
FROM ACM_Runs
WHERE MinHealthIndex < 50 
    AND StartedAt >= DATEADD(day, -7, GETUTCDATE())
ORDER BY MinHealthIndex;
```

---

## 💡 Tips & Tricks

### Resume interrupted batch
```bash
# Progress saved automatically - just re-run with --resume
python scripts/sql_batch_runner.py --equip FD_FAN --resume
```

### Process multiple equipment in parallel
```bash
python scripts/sql_batch_runner.py \
    --equip FD_FAN GAS_TURBINE COND_PUMP \
    --max-workers 3
```

### Dry-run before executing
```bash
# Preview what would be processed
python scripts/sql_batch_runner.py --equip FD_FAN --dry-run
```

### Clear all outputs for fresh start
```sql
-- Development only - clears all analytical data for equipment
DECLARE @EquipID INT = 1;

DELETE FROM ACM_HealthTimeline WHERE EquipID = @EquipID;
DELETE FROM ACM_RegimeTimeline WHERE EquipID = @EquipID;
DELETE FROM ACM_Episodes WHERE EquipID = @EquipID;
-- ... repeat for all 47 tables
DELETE FROM ModelRegistry WHERE EquipID = @EquipID;
DELETE FROM ACM_ColdstartState WHERE EquipID = @EquipID;
DELETE FROM RunLog WHERE EquipID = @EquipID;
DELETE FROM ACM_Runs WHERE EquipID = @EquipID;
```

---

## 🎓 Key Concepts

### RunID
- Unique identifier for each ACM execution (UUID)
- Generated by `usp_ACM_StartRun` stored procedure
- Used as foreign key in all analytical tables

### Outcome
- **OK**: Run completed successfully, data written
- **NOOP**: Run deferred (insufficient data, waiting for coldstart)
- **FAIL**: Run failed with error

### Health Status
- **HEALTHY**: AvgHealthIndex > 90, MinHealthIndex > 70
- **CAUTION**: AvgHealthIndex 70-90 or MinHealthIndex 50-70
- **ALERT**: AvgHealthIndex < 70 or MinHealthIndex < 50

### Coldstart Stages
- **PENDING**: Waiting for sufficient data
- **IN_PROGRESS**: Accumulating data, models not ready
- **COMPLETE**: Models trained and cached in ModelRegistry
- **FAILED**: Errors during coldstart process

---

**Need Help?** 
- Check full audit: `docs/BATCH_MODE_SQL_AUDIT.md`
- Review examples: `docs/SQL_BATCH_RUNNER.md`
- Ask team in #acm-support


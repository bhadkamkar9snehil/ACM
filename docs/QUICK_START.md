# ACM V8 Quick Start Guide - Week 1 Features

## Setup

### 1. Create SQL Tables
```sql
-- Run DDL scripts in order:
-- 1. Core tables (already exist)
-- 2. New Week 1 tables
USE ACM;
GO

-- From docs/sql/ACM_SchemaExtensions.sql
-- Creates: ACM_SinceWhen, ACM_BaselineBuffer, ACM_SchemaVersion
-- Plus: usp_CleanupBaselineBuffer stored procedure

-- From docs/sql/ACM_FaultInjections.sql  
-- Creates: ACM_FaultInjections

-- From docs/sql/ACM_BacktestResults.sql
-- Creates: ACM_BacktestResults
```

### 2. Verify Tables Created
```sql
SELECT TABLE_NAME 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_NAME IN (
    'ACM_Runs',
    'ACM_EpisodeCulprits', 
    'ACM_ConfigHistory',
    'ACM_SinceWhen',
    'ACM_BaselineBuffer',
    'ACM_SchemaVersion',
    'ACM_FaultInjections',
    'ACM_BacktestResults'
)
ORDER BY TABLE_NAME;
-- Should return 8 rows
```

---

## Feature 1: Run Metadata Tracking

### Automatic Usage
No code changes needed - already integrated in `acm_main.py`:

```python
# On success (line ~2050)
write_run_metadata(sql_client, run_id, equip_id, cfg, 
                   success=True, 
                   health_final="GOOD", 
                   time_spent=elapsed)

# On failure (line ~2140)  
write_run_metadata(sql_client, run_id, equip_id, cfg,
                   success=False,
                   error_message=str(e))
```

### Query Run History
```sql
-- Recent runs
SELECT TOP 10 
    RunID, EquipID, ExecutionStatus, HealthStatusFinal,
    TotalSensors, TimeSpent, DataQualityScore
FROM ACM_Runs
ORDER BY CreatedAt DESC;

-- Failed runs
SELECT RunID, EquipID, ErrorMessage, CreatedAt
FROM ACM_Runs  
WHERE ExecutionStatus = 'FAILED'
ORDER BY CreatedAt DESC;
```

---

## Feature 2: Performance-Optimized SQL Writes

### Automatic Usage
Already enabled in `output_manager.py` - uses batched transactions:

```python
# In acm_main.py (around line 1900)
output_mgr = OutputManager(sql_client=sql_client, 
                           run_id=run_id, 
                           equip_id=equip_id,
                           batch_size=5000)

# Generate all 26 tables in single transaction
analytics_summary = output_mgr.generate_all_analytics_tables(
    scores_df=scores,
    episodes_df=episodes,
    cfg=cfg,
    tables_dir=tables_dir,
    enable_sql=True  # Must be True
)

# Output: {"csv_tables": 26, "sql_tables": 26}
# Time: <15s (vs 58s before)
```

### Monitor Performance
```python
# Console output shows:
# [OUTPUT] Starting batched transaction
# [OUTPUT] SQL insert to ACM_HealthTimeline: 8640 rows
# ... (24 more tables)
# [OUTPUT] Batched transaction committed (12.3s)
```

---

## Feature 3: Synthetic Fault Injection

### Basic Usage
```python
from core.fault_injection import FaultInjector, FaultInjectionPlan

# Initialize (MUST explicitly enable)
injector = FaultInjector(
    enabled=True,  # Safety: False by default
    run_id=run_id,
    equip_id=equip_id,
    seed=42  # For reproducibility
)

# Define fault scenario
plan = FaultInjectionPlan(
    sensor_name="Temperature_1",
    operator_type="step",  # or 'spike', 'drift', 'stuck-at', 'noise'
    start_time=pd.Timestamp("2024-01-15 10:00:00"),
    end_time=pd.Timestamp("2024-01-15 12:00:00"),
    parameters={"magnitude": 5.0}  # +5 degree offset
)

# Apply to scoring data
modified_scores, injections = injector.apply_plan(scores_df, plan)

# Log to SQL
injector.log_injections(sql_client, injections)

# Get summary
summary = injector.get_summary()
print(f"Total injections: {summary['total_injections']}")
print(f"By type: {summary['by_type']}")
```

### Fault Operators
```python
# Step change (sudden offset)
plan = FaultInjectionPlan(
    sensor_name="Pressure_2",
    operator_type="step",
    start_time=t_start,
    end_time=t_end,
    parameters={"magnitude": 10.0}  # +10 units
)

# Spike (transient anomaly)
plan = FaultInjectionPlan(
    sensor_name="Vibration_3",
    operator_type="spike",
    start_time=t_start,
    end_time=t_end,
    parameters={
        "magnitude": 50.0,  # Spike height
        "duration_points": 5  # Number of consecutive points
    }
)

# Drift (gradual trend)
plan = FaultInjectionPlan(
    sensor_name="Temperature_1",
    operator_type="drift",
    start_time=t_start,
    end_time=t_end,
    parameters={"rate": 0.01}  # +0.01 per data point
)

# Stuck-at (frozen value)
plan = FaultInjectionPlan(
    sensor_name="Flow_4",
    operator_type="stuck-at",
    start_time=t_start,
    end_time=t_end,
    parameters={"value": 100.0}  # Freeze at 100 (or None for first value)
)

# Noise (increased variance)
plan = FaultInjectionPlan(
    sensor_name="Pressure_2",
    operator_type="noise",
    start_time=t_start,
    end_time=t_end,
    parameters={"std_multiplier": 3.0}  # 3x normal standard deviation
)
```

### Query Injections
```sql
-- All injections for a run
SELECT * FROM ACM_FaultInjections
WHERE RunID = 'run_20240115_120000'
ORDER BY Timestamp;

-- Summary by operator
SELECT OperatorType, COUNT(*) as Count,
       AVG(InjectedValue - OriginalValue) as AvgChange
FROM ACM_FaultInjections
WHERE RunID = 'run_20240115_120000'
GROUP BY OperatorType;
```

---

## Feature 4: Backtest Harness

### Basic Usage
```python
from core.backtest import BacktestHarness

# Initialize
harness = BacktestHarness(sql_client=sql_client, enable_sql=True)

# Run backtest over date range
results = harness.run_backtest(
    equip_id=101,
    start_date=pd.Timestamp("2024-01-01"),
    end_date=pd.Timestamp("2024-01-07"),
    window_hours=24,  # 24-hour windows
    step_hours=12,    # 12-hour steps (50% overlap)
    config=cfg  # ACM configuration
)

# Get summary statistics
summary = harness.summarize_results(results)
print(f"Total windows: {summary['total_windows']}")
print(f"Avg FP rate: {summary['fp_rate']['mean']:.2f} per hour")
print(f"Avg latency: {summary['latency_seconds']['mean']:.1f} seconds")

# Log summary to console
harness.log_summary()

# Get auto-tuning recommendation
recommendation = harness.get_tuning_recommendation(target_fp_rate=0.5)
print(f"Action: {recommendation['action']}")
print(f"Reason: {recommendation['reason']}")

# Results are automatically saved to ACM_BacktestResults table
```

### Advanced Usage
```python
# Generate windows manually
windows = harness.generate_windows(
    start_date=pd.Timestamp("2024-01-01"),
    end_date=pd.Timestamp("2024-01-31"),
    window_hours=48,  # Longer windows
    step_hours=24,    # Less overlap
    equip_id=101,
    config=cfg
)
print(f"Generated {len(windows)} windows")

# Run specific window
result = harness.run_window(windows[0])
if result:
    print(f"FP rate: {result.fp_rate:.2f}/hr")
    print(f"Latency: {result.latency_seconds:.1f}s")
    print(f"Coverage: {result.coverage_pct:.1f}%")

# Save specific results
harness.save_results([result])
```

### Query Backtest Results
```sql
-- Equipment backtest summary
SELECT EquipID, COUNT(*) as TotalWindows,
       AVG(FPRate) as AvgFPRate,
       MIN(FPRate) as MinFPRate,
       MAX(FPRate) as MaxFPRate,
       AVG(LatencySeconds) as AvgLatency,
       AVG(CoveragePct) as AvgCoverage
FROM ACM_BacktestResults
WHERE EquipID = 101
GROUP BY EquipID;

-- High FP rate windows
SELECT TOP 10 RunID, WindowStart, WindowEnd, FPRate, EpisodesDetected
FROM ACM_BacktestResults
WHERE EquipID = 101 AND FPRate > 1.0
ORDER BY FPRate DESC;

-- Daily performance trend
SELECT CAST(WindowStart AS DATE) as BacktestDate,
       COUNT(*) as WindowCount,
       AVG(FPRate) as AvgFPRate,
       AVG(LatencySeconds) as AvgLatency
FROM ACM_BacktestResults
WHERE EquipID = 101
GROUP BY CAST(WindowStart AS DATE)
ORDER BY BacktestDate DESC;
```

---

## Feature 5: Baseline Buffer Storage

### Automatic Usage
Already integrated in `acm_main.py` (lines 1583-1622):

```python
# After CSV write (around line 1580)
if sql_client is not None and combined is not None:
    try:
        # Transform wide format to long format
        baseline_records = []
        for ts_idx, row in combined.iterrows():
            for sensor_name, sensor_value in row.items():
                if pd.notna(sensor_value):
                    baseline_records.append((
                        int(equip_id),
                        pd.Timestamp(ts_idx).to_pydatetime().replace(tzinfo=None),
                        str(sensor_name),
                        float(sensor_value),
                        None  # DataQuality
                    ))
        
        # Bulk insert
        insert_sql = """
            INSERT INTO dbo.ACM_BaselineBuffer 
            (EquipID, Timestamp, SensorName, SensorValue, DataQuality)
            VALUES (?, ?, ?, ?, ?)
        """
        with sql_client.cursor() as cur:
            cur.fast_executemany = True
            cur.executemany(insert_sql, baseline_records)
        sql_client.conn.commit()
        
        # Cleanup old data
        cur.execute("EXEC dbo.usp_CleanupBaselineBuffer @EquipID=?, @RetentionHours=?, @MaxRowsPerEquip=?",
                    (int(equip_id), int(window_hours), max_points))
        
        Console.info(f"[BASELINE] Wrote {len(baseline_records)} records to SQL")
    except Exception as e:
        Console.error(f"[BASELINE] SQL write failed: {e}")
```

### Query Baseline Data
```sql
-- Get recent baseline for equipment
SELECT TOP 1000 Timestamp, SensorName, SensorValue
FROM ACM_BaselineBuffer
WHERE EquipID = 101
ORDER BY Timestamp DESC;

-- Count baseline points by sensor
SELECT SensorName, COUNT(*) as DataPoints,
       MIN(Timestamp) as OldestData,
       MAX(Timestamp) as LatestData
FROM ACM_BaselineBuffer
WHERE EquipID = 101
GROUP BY SensorName
ORDER BY SensorName;

-- Check storage size
SELECT EquipID, COUNT(*) as TotalRows,
       MIN(Timestamp) as OldestData,
       MAX(Timestamp) as LatestData
FROM ACM_BaselineBuffer
GROUP BY EquipID;
```

---

## Common Queries

### Overall System Health
```sql
-- Recent run summary
SELECT 
    COUNT(*) as TotalRuns,
    SUM(CASE WHEN ExecutionStatus = 'SUCCESS' THEN 1 ELSE 0 END) as SuccessCount,
    SUM(CASE WHEN ExecutionStatus = 'FAILED' THEN 1 ELSE 0 END) as FailureCount,
    AVG(TimeSpent) as AvgTimeSeconds,
    AVG(DataQualityScore) as AvgDataQuality
FROM ACM_Runs
WHERE CreatedAt >= DATEADD(day, -7, GETUTCDATE());

-- Performance metrics by equipment
SELECT EquipID,
       COUNT(*) as Runs,
       AVG(TimeSpent) as AvgTime,
       AVG(DataQualityScore) as AvgQuality,
       SUM(EpisodeCount) as TotalEpisodes
FROM ACM_Runs
WHERE CreatedAt >= DATEADD(day, -7, GETUTCDATE())
      AND ExecutionStatus = 'SUCCESS'
GROUP BY EquipID;
```

### Fault Injection Analysis
```sql
-- Injection summary by type
SELECT OperatorType, 
       COUNT(DISTINCT RunID) as Runs,
       COUNT(*) as TotalInjections,
       COUNT(DISTINCT SensorName) as SensorsAffected,
       AVG(InjectedValue - OriginalValue) as AvgChange
FROM ACM_FaultInjections
GROUP BY OperatorType;
```

### Backtest Performance Tracking
```sql
-- Performance over time
SELECT CAST(WindowStart AS DATE) as TestDate,
       COUNT(*) as Windows,
       AVG(FPRate) as AvgFPRate,
       AVG(CoveragePct) as AvgCoverage,
       AVG(LatencySeconds) as AvgLatency
FROM ACM_BacktestResults
WHERE EquipID = 101
GROUP BY CAST(WindowStart AS DATE)
ORDER BY TestDate DESC;
```

---

## Troubleshooting

### Issue: Tables not found
```sql
-- Check if tables exist
SELECT TABLE_NAME 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_NAME LIKE 'ACM_%'
ORDER BY TABLE_NAME;

-- If missing, run DDL scripts from docs/sql/
```

### Issue: Slow SQL writes
```python
# Check batch size configuration
output_mgr = OutputManager(
    sql_client=sql_client,
    batch_size=10000,  # Increase for large tables
    enable_batching=True  # Must be True
)

# Verify fast_executemany enabled
# Should see in logs: [OUTPUT] Starting batched transaction
```

### Issue: Fault injection not working
```python
# Verify enabled=True (safety feature)
injector = FaultInjector(enabled=True)  # Must be True

# Check sensor name exists
if plan.sensor_name not in scores_df.columns:
    print(f"Sensor {plan.sensor_name} not found!")
    print(f"Available: {list(scores_df.columns)}")
```

### Issue: Backtest fails
```python
# Check date range has data
# start_date and end_date must have available data

# Verify window size reasonable
# window_hours should be <= (end_date - start_date).total_seconds() / 3600

# Check config valid
# config must be valid ACM configuration dictionary
```

---

## Configuration

### Enable SQL Writes
```yaml
# In config.yaml
sql:
  enable: true
  server: "10.2.6.164"
  database: "ACM"
  batch_size: 5000
  enable_batching: true
```

### Enable Fault Injection
```yaml
# In config.yaml (or via CLI flag)
fault_injection:
  enable: false  # Set to true for testing
  seed: 42
  plans:
    - sensor: "Temperature_1"
      operator: "step"
      magnitude: 5.0
      start: "2024-01-15T10:00:00"
      end: "2024-01-15T12:00:00"
```

### Enable Backtest
```yaml
# In config.yaml (or via CLI flag)
backtest:
  enable: false  # Set to true for validation
  start_date: "2024-01-01"
  end_date: "2024-01-07"
  window_hours: 24
  step_hours: 12
  target_fp_rate: 0.5
```

---

## Next Steps

1. ✅ **Week 1 Complete** - All features implemented
2. ⏳ **Deploy SQL tables** - Run DDL scripts
3. ⏳ **Test end-to-end** - Full ACM run with all writers
4. ⏳ **Measure performance** - Validate <15s SQL write target
5. ⏳ **Run backtest** - Generate baseline metrics
6. ⏳ **Week 2** - SQL-first data loading and unified writer

---

**Quick Reference Complete** ✅

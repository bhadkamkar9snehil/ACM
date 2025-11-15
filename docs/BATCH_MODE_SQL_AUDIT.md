# Batch Mode SQL Saving Audit

**Date:** November 15, 2025  
**Version:** ACM V8  
**Scope:** Comprehensive audit of how batch mode runs are saved to SQL database  
**Author:** ACM Team

---

## Executive Summary

This audit examines the complete data flow and persistence mechanisms for ACM batch mode operations when running against SQL Server. The analysis covers run tracking, data writes, progress persistence, and identifies gaps and optimization opportunities.

### Key Findings

✅ **Strengths:**
- Dual-table run tracking (RunLog + ACM_Runs) with different purposes
- Comprehensive metadata capture in ACM_Runs table
- 26+ analytical tables populated with health, regime, and detector data
- Intelligent coldstart tracking via ACM_ColdstartState
- Progress tracking for batch resumption

⚠️ **Concerns:**
- Inconsistent transaction management across output operations
- No validation of critical columns before SQL writes
- Silent column dropping when schema mismatches occur
- Caching strategies lack TTL and invalidation logic
- Progress tracking split between SQL and JSON file

🔴 **Critical Issues:**
- Potential duplicate data accumulation without unique constraints
- Autocommit mode assumptions that may not match SQL Server defaults
- Missing rollback handling in several error paths
- No monitoring of SQL write performance or failures

---

## 1. Data Flow Architecture

### 1.1 Batch Processing Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    sql_batch_runner.py                       │
│                                                              │
│  ┌──────────────┐        ┌─────────────────┐               │
│  │  Equipment   │  ───>  │  Coldstart      │               │
│  │  Discovery   │        │  Phase          │               │
│  └──────────────┘        └─────────────────┘               │
│                                  │                           │
│                                  v                           │
│                          ┌─────────────────┐                │
│                          │  Batch          │                │
│                          │  Processing     │                │
│                          │  Loop           │                │
│                          └─────────────────┘                │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               │ For each batch window
                               v
┌─────────────────────────────────────────────────────────────┐
│                       acm_main.py                            │
│                                                              │
│  1. usp_ACM_StartRun       ───> Creates RunID in RunLog     │
│  2. Data Loading           ───> From {EQUIP}_Data table     │
│  3. Feature Engineering    ───> In-memory transforms         │
│  4. Model Training/Loading ───> ModelRegistry cache          │
│  5. Scoring & Detection    ───> Fused z-scores computed     │
│  6. Output Generation      ───> output_manager writes        │
│  7. Run Metadata           ───> ACM_Runs table               │
│  8. usp_ACM_FinalizeRun    ───> Updates RunLog              │
└─────────────────────────────────────────────────────────────┘
                               │
                               │ SQL writes
                               v
┌─────────────────────────────────────────────────────────────┐
│                    SQL Server (ACM Database)                 │
│                                                              │
│  ┌───────────────────┐  ┌──────────────────┐               │
│  │  Run Tracking     │  │  Analytics       │               │
│  │  - RunLog         │  │  - ACM_HealthTimeline            │
│  │  - ACM_Runs       │  │  - ACM_RegimeTimeline            │
│  │  - ACM_Coldstart  │  │  - ACM_Episodes                  │
│  └───────────────────┘  │  - ACM_Scores_Wide               │
│                         │  - 22 more tables...              │
│  ┌───────────────────┐  └──────────────────┘               │
│  │  Model Storage    │                                      │
│  │  - ModelRegistry  │  ┌──────────────────┐               │
│  │  - Model blobs    │  │  Config & Master │               │
│  └───────────────────┘  │  - Equipment                     │
│                         │  - ACM_Config                    │
│                         │  - Tag_Equipment_Map             │
│                         └──────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Run Tracking Tables

### 2.1 RunLog Table (Core Run Tracking)

**Purpose:** Lightweight run lifecycle tracking for stored procedures  
**File:** `scripts/sql/20_stored_procs.sql`

**Schema:**
```sql
CREATE TABLE dbo.RunLog (
    RunID UNIQUEIDENTIFIER PRIMARY KEY,
    EquipID INT,
    Stage NVARCHAR(32),              -- 'started', 'score', 'finalize'
    StartEntryDateTime DATETIME2(3),
    EndEntryDateTime DATETIME2(3),
    Outcome NVARCHAR(16),             -- 'OK', 'NOOP', 'FAIL'
    RowsRead INT,
    RowsWritten INT,
    ErrorJSON NVARCHAR(MAX),
    TriggerReason NVARCHAR(64),
    Version NVARCHAR(32),
    ConfigHash NVARCHAR(64),
    WindowStartEntryDateTime DATETIME2(3),
    WindowEndEntryDateTime DATETIME2(3)
)
```

**Written By:** 
- `usp_ACM_StartRun` (INSERT at run start)
- `usp_ACM_FinalizeRun` (UPDATE at run end)

**Write Pattern:**
```python
# In acm_main.py
run_id = uuid.uuid4()
sql_client.execute_sp('usp_ACM_StartRun', params={
    'EquipID': equip_id,
    'ConfigHash': config_signature,
    'WindowStartEntryDateTime': start_time,
    'WindowEndEntryDateTime': end_time,
    'Stage': 'started',
    'RunID': run_id  # OUTPUT parameter
})

# ... run pipeline ...

sql_client.execute_sp('usp_ACM_FinalizeRun', params={
    'RunID': run_id,
    'Outcome': 'OK',  # or 'NOOP', 'FAIL'
    'RowsRead': len(data),
    'RowsWritten': total_writes
})
```

**Issues:**
1. ❌ No indexes on EquipID or StartEntryDateTime for efficient querying
2. ❌ No retention policy - table grows unbounded
3. ⚠️ Outcome constraint not enforced at DB level (relies on app logic)

---

### 2.2 ACM_Runs Table (Detailed Metadata)

**Purpose:** Comprehensive run analytics and health tracking  
**File:** `scripts/sql/54_create_acm_runs_table.sql`

**Schema:**
```sql
CREATE TABLE dbo.ACM_Runs (
    RunID UNIQUEIDENTIFIER PRIMARY KEY,
    EquipID INT NOT NULL,
    EquipName NVARCHAR(200),
    StartedAt DATETIME2 NOT NULL,
    CompletedAt DATETIME2 NULL,
    DurationSeconds INT,
    ConfigSignature VARCHAR(64),
    TrainRowCount INT,
    ScoreRowCount INT,
    EpisodeCount INT,
    HealthStatus VARCHAR(50),         -- 'HEALTHY', 'CAUTION', 'ALERT'
    AvgHealthIndex FLOAT,
    MinHealthIndex FLOAT,
    MaxFusedZ FLOAT,
    DataQualityScore FLOAT,
    RefitRequested BIT DEFAULT 0,
    ErrorMessage NVARCHAR(1000),
    KeptColumns NVARCHAR(MAX),
    CreatedAt DATETIME2 DEFAULT GETUTCDATE()
)
```

**Written By:**
- `core/run_metadata_writer.py::write_run_metadata()`

**Write Pattern:**
```python
# In acm_main.py (lines 3436-3455 for success, 3502-3520 for failure)
write_run_metadata(
    sql_client=sql_client,
    run_id=run_id,
    equip_id=int(equip_id),
    equip_name=equip,
    started_at=run_start_time,
    completed_at=run_completion_time,
    config_signature=config_signature,
    train_row_count=len(train),
    score_row_count=len(frame),
    episode_count=len(episodes),
    health_status=run_metadata.get("health_status", "UNKNOWN"),
    avg_health_index=run_metadata.get("avg_health_index"),
    min_health_index=run_metadata.get("min_health_index"),
    max_fused_z=run_metadata.get("max_fused_z"),
    data_quality_score=data_quality_score,
    refit_requested=refit_flag_path.exists(),
    kept_columns=",".join(kept_cols),
    error_message=None  # or error string on failure
)
```

**Strengths:**
✅ Indexes on (EquipID, StartedAt DESC) for time-series queries  
✅ Filtered index on (EquipID, HealthStatus) WHERE HealthStatus IN ('CAUTION', 'ALERT')  
✅ Foreign key to Equipment table for referential integrity  
✅ Separate error handling writes for failed runs

**Issues:**
1. ⚠️ No UNIQUE constraint on RunID - theoretically allows duplicates
2. ⚠️ HealthStatus values ('HEALTHY', 'CAUTION', 'ALERT') not CHECK constrained
3. ⚠️ KeptColumns stored as comma-delimited string instead of normalized table
4. ⚠️ No validation that StartedAt <= CompletedAt
5. ⚠️ DurationSeconds computed in Python instead of COMPUTED column

---

### 2.3 Dual-Table Pattern Analysis

**Why Two Tables?**

| Aspect | RunLog | ACM_Runs |
|--------|--------|----------|
| **Purpose** | Operational lifecycle tracking | Analytics and health metrics |
| **Written** | Stored procedures (BEGIN/END) | Python code (after completion) |
| **Frequency** | Every run (2 writes) | Every run (1 write) |
| **Size** | Small (15 columns) | Large (18 columns) |
| **Usage** | Progress tracking, debugging | Dashboards, health reports |
| **Retention** | Short-term (days/weeks) | Long-term (months/years) |

**Concerns:**
1. 🔴 **Data Inconsistency Risk:** No transaction spanning both tables
   - RunLog may succeed while ACM_Runs fails (or vice versa)
   - No way to reconcile mismatches

2. ⚠️ **Redundant Data:** RunID, EquipID, timestamps duplicated
   - Could normalize with ACM_Runs.RunID → RunLog.RunID FK

3. ⚠️ **Query Complexity:** Joins required for complete run history
   ```sql
   SELECT r.RunID, r.StartedAt, r.Outcome, a.HealthStatus, a.AvgHealthIndex
   FROM RunLog r
   LEFT JOIN ACM_Runs a ON r.RunID = a.RunID
   WHERE r.EquipID = 1 AND r.StartEntryDateTime >= '2025-01-01'
   ```

**Recommendation:**
Consider merging into single table OR establish FK relationship:
```sql
ALTER TABLE ACM_Runs 
ADD CONSTRAINT FK_ACM_Runs_RunLog 
FOREIGN KEY (RunID) REFERENCES dbo.RunLog(RunID);
```

---

## 3. Coldstart Tracking

### 3.1 ACM_ColdstartState Table

**Purpose:** Track coldstart progress to enable intelligent retry logic  
**File:** `scripts/sql/55_create_coldstart_tracking.sql`

**Schema:**
```sql
CREATE TABLE dbo.ACM_ColdstartState (
    EquipID INT,
    Stage VARCHAR(20) DEFAULT 'score',  -- 'train' or 'score'
    Status VARCHAR(20),                  -- 'PENDING', 'IN_PROGRESS', 'COMPLETE', 'FAILED'
    AttemptCount INT DEFAULT 0,
    FirstAttemptAt DATETIME2,
    LastAttemptAt DATETIME2,
    CompletedAt DATETIME2,
    AccumulatedRows INT DEFAULT 0,
    RequiredRows INT DEFAULT 500,
    DataStartTime DATETIME2,
    DataEndTime DATETIME2,
    TickMinutes INT,
    ColdstartSplitRatio FLOAT DEFAULT 0.6,
    LastError NVARCHAR(2000),
    ErrorCount INT DEFAULT 0,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    UpdatedAt DATETIME2 DEFAULT GETUTCDATE(),
    CONSTRAINT PK_ACM_ColdstartState PRIMARY KEY (EquipID, Stage)
)
```

**Read By:**
- `sql_batch_runner.py::_check_coldstart_status()` (line 372)
- `usp_ACM_CheckColdstartStatus` stored procedure

**Write By:**
- `usp_ACM_UpdateColdstartProgress` stored procedure
- Implicit update via ModelRegistry check (if models exist, mark COMPLETE)

**Logic Flow:**
```python
# In sql_batch_runner.py
def _check_coldstart_status(self, equip_name: str):
    # 1. Query ModelRegistry for existing models
    SELECT COUNT(*) FROM ModelRegistry 
    WHERE EquipID = ? AND ModelType IN ('pca_model', 'gmm_model', 'iforest_model')
    
    # If models exist (count >= 3), coldstart is complete
    if model_count >= 3:
        return (True, 0, 0)  # is_complete, accumulated_rows, required_rows
    
    # 2. Query ACM_ColdstartState
    SELECT Status, AccumulatedRows, RequiredRows
    FROM ACM_ColdstartState
    WHERE EquipID = ? AND Stage = 'score'
    
    # 3. Return status
    return (is_complete, accum_rows, req_rows)
```

**Strengths:**
✅ Tracks accumulated data across multiple attempts  
✅ Exponential window expansion strategy visible in tracking  
✅ Error history preserved for debugging  
✅ Composite PK on (EquipID, Stage) prevents duplicate entries

**Issues:**
1. ⚠️ Status transitions not validated (no state machine enforcement)
   - Could jump from PENDING → COMPLETE without IN_PROGRESS
   
2. ⚠️ AccumulatedRows not automatically decremented on failure
   - May count same data multiple times if window overlaps

3. ⚠️ No TTL or reset mechanism
   - FAILED state persists forever - operator must manually reset

4. ⚠️ Stage column underutilized
   - Always 'score' in practice, 'train' stage never used

5. 🔴 Race condition risk
   - Multiple batch runners could update same equipment concurrently
   - No SERIALIZABLE isolation or optimistic concurrency control

---

### 3.2 ModelRegistry Interaction

**Coldstart Completion Criteria:**
```python
# From sql_batch_runner.py (line 398-404)
SELECT COUNT(*) FROM ModelRegistry 
WHERE EquipID = ? AND ModelType IN ('pca_model', 'gmm_model', 'iforest_model')

if model_count >= 3:
    # Coldstart complete - models exist
    UPDATE ACM_ColdstartState SET Status = 'COMPLETE' WHERE EquipID = ?
```

**Critical Dependency:**
- Coldstart completion relies on ModelRegistry, NOT data volume
- If models are deleted/corrupted, coldstart restarts even with sufficient data
- No fallback to data accumulation threshold alone

**Gap:**
- ModelRegistry write and ColdstartState update not in same transaction
- Could have models but Status = 'PENDING' (or vice versa)

---

## 4. Progress Tracking

### 4.1 File-Based Progress (.sql_batch_progress.json)

**Location:** `artifacts/.sql_batch_progress.json`  
**Written By:** `sql_batch_runner.py::_save_progress()` (line 334)

**Structure:**
```json
{
  "FD_FAN": {
    "coldstart_complete": true,
    "last_batch_end": "2012-01-10 00:00:00",
    "batches_completed": 192
  },
  "GAS_TURBINE": {
    "coldstart_complete": false,
    "last_batch_end": null,
    "batches_completed": 0
  }
}
```

**Usage:**
```python
# Resume logic (line 600-609)
if resume and 'last_batch_end' in equip_progress:
    current_ts = datetime.fromisoformat(equip_progress['last_batch_end'])
    batches_completed = equip_progress.get('batches_completed', 0)
    print(f"Resuming from {current_ts} ({batches_completed} batches completed)")
```

**Issues:**
1. 🔴 **Critical: File-based state separate from SQL**
   - Database has no knowledge of batch progress
   - Cannot query "which batches processed" via SQL
   - File corruption loses all progress (no backup)

2. ⚠️ **No locking mechanism**
   - Concurrent batch runners could corrupt file
   - Last write wins - no conflict resolution

3. ⚠️ **Timestamps as strings**
   - ISO format parsing fragile across timezones
   - Should store as Unix timestamps for precision

4. ⚠️ **No metadata**
   - Missing: tick_minutes used, config_hash, data_range
   - Cannot validate if progress is stale

---

### 4.2 Hybrid Tracking Comparison

| Aspect | File (.json) | SQL (ColdstartState) | SQL (RunLog) |
|--------|--------------|----------------------|--------------|
| **Tracks** | Batch position | Coldstart progress | Individual runs |
| **Granularity** | Per equipment | Per equipment | Per RunID |
| **Persistence** | Local file | Database | Database |
| **Queryable** | No | Yes | Yes |
| **Concurrent Safe** | No | Mostly | Yes |
| **Backup** | No | Yes (DB backup) | Yes (DB backup) |

**Recommendation:**
Create `ACM_BatchProgress` table to replace JSON file:
```sql
CREATE TABLE dbo.ACM_BatchProgress (
    EquipID INT PRIMARY KEY,
    ColdstartComplete BIT DEFAULT 0,
    LastBatchEndTime DATETIME2,
    BatchesCompleted INT DEFAULT 0,
    TickMinutes INT,
    ConfigHash VARCHAR(64),
    UpdatedAt DATETIME2 DEFAULT GETUTCDATE(),
    CONSTRAINT FK_BatchProgress_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
)
```

---

## 5. Analytical Data Writes

### 5.1 Output Manager Bulk Insert Flow

**Entry Point:** `core/output_manager.py::_bulk_insert_sql()` (line 1314)

**Flow:**
```python
def _bulk_insert_sql(self, table_name: str, df: pd.DataFrame) -> int:
    # 1. Validate table is whitelisted
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Table {table_name} not in whitelist")
    
    # 2. Check SQL health (cached)
    if not self._check_sql_health():
        return 0
    
    # 3. Get table columns (cached)
    table_cols = self._get_table_columns(table_name)
    
    # 4. Filter DataFrame columns to match schema
    columns = [c for c in df.columns if c in table_cols]
    df_clean = df[columns].copy()
    
    # 5. Clean data (NaN, Inf, extreme floats)
    df_clean = self._clean_for_sql(df_clean)
    
    # 6. Convert to records
    records = [tuple(row) for row in df_clean.itertuples(index=False)]
    
    # 7. Batch insert with executemany
    batch_size = self.batch_size  # Default: 5000
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        cur.executemany(insert_sql, batch)
    
    # 8. Commit (or rely on batched_transaction context)
    if not self._batched_transaction_active:
        self.sql_client.conn.commit()
    
    return len(records)
```

**26+ Tables Written:**
- ACM_HealthTimeline (fused z-scores, health index)
- ACM_RegimeTimeline (GMM regime assignments)
- ACM_ContributionTimeline (per-detector z-scores)
- ACM_DriftSeries (drift metrics per sensor)
- ACM_Episodes (anomaly episode boundaries)
- ACM_Scores_Wide (wide-format detector scores)
- ACM_Scores_Long (long-format for BI)
- ... (20 more tables)

---

### 5.2 Transaction Management

**Pattern:**
```python
# In acm_main.py (line 3307)
with output_mgr.batched_transaction():
    output_mgr.write_health_timeline(...)
    output_mgr.write_regime_timeline(...)
    output_mgr.write_contribution_timeline(...)
    # ... 20+ writes
    # Commit only once at context exit
```

**Implementation (output_manager.py, line 558):**
```python
@contextmanager
def batched_transaction(self):
    self._batched_transaction_active = True
    try:
        yield
        # Commit all writes in batch
        if hasattr(self.sql_client, "commit"):
            self.sql_client.commit()
        elif hasattr(self.sql_client, "conn"):
            if not getattr(self.sql_client.conn, "autocommit", True):
                self.sql_client.conn.commit()
    except Exception as e:
        # Rollback on error
        try:
            if hasattr(self.sql_client, "rollback"):
                self.sql_client.rollback()
            elif hasattr(self.sql_client, "conn"):
                self.sql_client.conn.rollback()
        except:
            pass
        raise
    finally:
        self._batched_transaction_active = False
```

**Issues:**
1. 🔴 **Autocommit Assumption:**
   - Code assumes `autocommit=True` is default (line 582)
   - SQL Server pyodbc default is `autocommit=False`
   - Could silently skip commits if assumption wrong

2. ⚠️ **Nested Transaction Risk:**
   - If write_run_metadata() called inside batched_transaction(), nested commit/rollback
   - No SAVEPOINT support for partial rollback

3. ⚠️ **No Transaction Verification:**
   - Doesn't check `@@TRANCOUNT` to confirm commit succeeded
   - Could return success while transaction still open

**Recommendation:**
```python
# After commit, verify
cur.execute("SELECT @@TRANCOUNT")
tran_count = cur.fetchone()[0]
if tran_count > 0:
    raise RuntimeError(f"Transaction not committed (@@TRANCOUNT={tran_count})")
```

---

### 5.3 Schema Mismatch Handling

**Current Behavior:**
```python
# output_manager.py line 1353
table_cols = self._get_table_columns(table_name)
columns = [c for c in df.columns if c in table_cols]
df_clean = df[columns].copy()

# SILENTLY drops columns not in schema
# Example: If DataFrame has 50 columns but table has 48, 2 columns lost
```

**Gap:**
- No warning logged when columns dropped
- No validation of critical columns (RunID, EquipID, Timestamp)
- Could lose data without operator awareness

**Recommendation:**
```python
# Validate critical columns exist
CRITICAL_COLS = {'RunID', 'EquipID', 'Timestamp'}
missing_critical = CRITICAL_COLS - set(df.columns)
if missing_critical:
    raise ValueError(f"Missing critical columns: {missing_critical}")

# Warn about dropped columns
dropped = set(df.columns) - set(table_cols)
if dropped:
    Console.warn(f"[SQL] Dropping {len(dropped)} columns not in {table_name}: {dropped}")
```

---

### 5.4 Data Cleaning Pipeline

**Float Handling (output_manager.py, line 670-690):**
```python
# Replace extreme floats > 1e100 with NULL
for col in df_clean.columns:
    if df_clean[col].dtype in [np.float64, np.float32]:
        extreme_mask = valid_mask & (df_clean[col].abs() > 1e100)
        if extreme_mask.any():
            df_clean.loc[extreme_mask, col] = None

# Replace NaN and Inf with NULL
df_clean = df_clean.replace([np.nan, np.inf, -np.inf], None)
```

**Issues:**
1. ⚠️ **Magic Number:** 1e100 threshold not documented or configurable
   - SQL Server FLOAT max is ~1.79e308
   - Threshold seems arbitrary

2. ⚠️ **Silent Data Loss:** No audit trail of replaced values
   - Could hide data quality issues in source

3. ⚠️ **No Aggregation:** Multiple extreme values replaced, but count not reported

**Recommendation:**
```python
# Log affected rows
if extreme_mask.any():
    extreme_count = extreme_mask.sum()
    extreme_sample = df_clean[extreme_mask][[col]].head(3)
    Console.warn(
        f"[SQL] Replaced {extreme_count} extreme values in {table_name}.{col}:\n"
        f"{extreme_sample.to_string()}"
    )
    # Optionally write to audit table
    self._write_data_quality_alert(table_name, col, 'extreme_float', extreme_count)
```

---

## 6. Performance Characteristics

### 6.1 Batch Insert Performance

**Current Method:** pyodbc `executemany()` with `fast_executemany=True`

**Benchmark (Estimated):**
- 5000 rows/batch (default)
- ~0.1-0.5 seconds per batch
- 10K-50K rows/second throughput

**Bottlenecks:**
1. Network round-trips (one per batch)
2. SQL Server parse/plan overhead per statement
3. Index maintenance on 26+ tables

**Alternatives:**

#### Option A: Table-Valued Parameters (TVP)
```python
# 10-100x faster for large inserts
from pyodbc import TVP
tvp_data = TVP(table_type_name='dbo.ACM_HealthTimeline_TVP', rows=records)
cur.execute("EXEC dbo.usp_BulkInsert_HealthTimeline @data=?", tvp_data)
```

**Pros:**
- Single round-trip
- Optimized bulk insert path
- Better transaction safety

**Cons:**
- Requires CREATE TYPE for each table
- More complex setup

#### Option B: BULK INSERT via CSV
```python
# For very large datasets (>100K rows)
temp_csv = f"/tmp/{table_name}_{uuid.uuid4()}.csv"
df_clean.to_csv(temp_csv, index=False, header=False)
cur.execute(f"BULK INSERT dbo.[{table_name}] FROM '{temp_csv}' WITH (FORMAT='CSV')")
os.remove(temp_csv)
```

**Pros:**
- Fastest option (>100K rows/sec)
- Bypasses transaction log (TABLOCK hint)

**Cons:**
- Requires file system access
- Cleanup on error tricky
- Less granular error handling

---

### 6.2 Caching Strategies

**Current Caches:**
```python
# output_manager.py (line 599-607)
self._sql_health_cache: Tuple[float, bool] = (0.0, False)
self._table_exists_cache: Dict[str, bool] = {}
self._table_columns_cache: Dict[str, set] = {}
self._table_insertable_cache: Dict[str, set] = {}
```

**Issues:**
1. ⚠️ **No TTL:** Caches never expire
   - Schema changes mid-run not detected
   - Health check staleness if long-running

2. ⚠️ **No Size Limit:** Unbounded memory growth
   - Could cache hundreds of tables if dynamically created

3. ⚠️ **No Invalidation:** Manual clear required
   - If table altered (ALTER TABLE ADD COLUMN), cache out of sync

**Recommendation:**
```python
from collections import OrderedDict
from time import time

class LRUCache:
    def __init__(self, max_size=100, ttl_seconds=300):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl_seconds
    
    def get(self, key):
        if key not in self.cache:
            return None
        value, timestamp = self.cache[key]
        if time() - timestamp > self.ttl:
            del self.cache[key]
            return None
        self.cache.move_to_end(key)  # LRU update
        return value
    
    def set(self, key, value):
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)  # Evict oldest
        self.cache[key] = (value, time())
```

---

## 7. Error Handling and Recovery

### 7.1 SQL Write Failures

**Current Behavior:**
```python
# output_manager.py line 1400
try:
    inserted = self._bulk_insert_sql(table_name, df)
    self.stats['sql_writes'] += 1
    self.stats['sql_rows_written'] += inserted
except Exception as e:
    self.stats['sql_failures'] += 1
    Console.warn(f"[SQL] Failed to write {table_name}: {e}")
    # Write continues to next table - NO ROLLBACK
```

**Issues:**
1. 🔴 **Partial Writes:** If table 10/26 fails, tables 1-9 committed
   - Run has inconsistent data across tables
   - Cannot tell which tables succeeded

2. ⚠️ **No Retry Logic:** Transient errors (network hiccup, deadlock) fail permanently

3. ⚠️ **Silent Failures:** Stats incremented but not surfaced to user
   - Operator may not know data is incomplete

**Recommendation:**
```python
# Add retry with exponential backoff
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
def _bulk_insert_sql_with_retry(self, table_name, df):
    return self._bulk_insert_sql(table_name, df)

# Track failures per table
self.failed_tables = []

try:
    inserted = self._bulk_insert_sql_with_retry(table_name, df)
except Exception as e:
    self.failed_tables.append(table_name)
    Console.error(f"[SQL] Failed to write {table_name} after retries: {e}")
    
# At end of run
if self.failed_tables:
    Console.error(f"[SQL] WARNING: {len(self.failed_tables)} tables failed: {self.failed_tables}")
    # Write to ACM_Runs.ErrorMessage
```

---

### 7.2 Rollback Handling

**Current Rollback Logic:**
```python
# output_manager.py line 593-606
except Exception as e:
    try:
        if hasattr(self.sql_client, "rollback"):
            self.sql_client.rollback()
        elif hasattr(self.sql_client, "conn"):
            self.sql_client.conn.rollback()
    except:
        pass  # Silent failure
    raise
```

**Issues:**
1. ⚠️ **Nested try-except:** Rollback exception swallowed
   - Cannot tell if rollback succeeded or failed
   
2. ⚠️ **No logging:** Silent pass on rollback failure
   - Transaction may be left in limbo

3. ⚠️ **No cleanup:** Partial data not marked as invalid

**Recommendation:**
```python
except Exception as e:
    rollback_success = False
    try:
        if hasattr(self.sql_client, "rollback"):
            self.sql_client.rollback()
            rollback_success = True
        elif hasattr(self.sql_client, "conn"):
            self.sql_client.conn.rollback()
            rollback_success = True
    except Exception as rollback_err:
        Console.error(f"[SQL] ROLLBACK FAILED: {rollback_err}")
        # Critical: transaction may be stuck - log to alert monitoring
    
    if rollback_success:
        Console.warn(f"[SQL] Transaction rolled back due to: {e}")
    else:
        Console.error(f"[SQL] CRITICAL: Rollback failed, transaction state unknown")
    
    raise
```

---

## 8. Data Integrity Concerns

### 8.1 Duplicate Data Risk

**Scenario:** Re-run with same RunID
```python
# If ACM crashes after partial SQL writes but before updating progress
# Operator re-runs with same time window
# Same RunID could be generated (if not UUID)
```

**Current Protection:**
- ✅ `usp_ACM_StartRun` deletes prior artifacts for same RunID (line 69-74)
- ⚠️ But only for subset of tables (ScoresTS, DriftTS, etc.)
- ⚠️ ACM_HealthTimeline and 20+ other tables NOT cleaned

**Gap:**
```sql
-- usp_ACM_StartRun only cleans these:
DELETE FROM dbo.ScoresTS WHERE RunID = @RunID;
DELETE FROM dbo.DriftTS WHERE RunID = @RunID;
DELETE FROM dbo.AnomalyEvents WHERE RunID = @RunID;
DELETE FROM dbo.RegimeEpisodes WHERE RunID = @RunID;
DELETE FROM dbo.PCA_Metrics WHERE RunID = @RunID;

-- Missing: ACM_HealthTimeline, ACM_RegimeTimeline, ACM_ContributionTimeline, ...
```

**Recommendation:**
1. Add UNIQUE constraint to prevent duplicates at DB level:
   ```sql
   ALTER TABLE ACM_HealthTimeline
   ADD CONSTRAINT UQ_HealthTimeline_Run_Equip_Time 
   UNIQUE (RunID, EquipID, Timestamp);
   ```

2. Or expand cleanup in usp_ACM_StartRun:
   ```sql
   -- Clean ALL analytics tables
   DELETE FROM dbo.ACM_HealthTimeline WHERE RunID = @RunID;
   DELETE FROM dbo.ACM_RegimeTimeline WHERE RunID = @RunID;
   -- ... (add all 26 tables)
   ```

---

### 8.2 Timestamp Consistency

**Issue:** Timestamps stored as timezone-naive local time
```python
# output_manager.py line 145-187
def _to_naive(ts) -> Optional[pd.Timestamp]:
    """Convert to timezone-naive local timestamp or None."""
    result = pd.to_datetime(ts, errors='coerce')
    if hasattr(result, 'tz') and result.tz is not None:
        return result.tz_localize(None)  # Strip timezone
    return result
```

**Problems:**
1. 🔴 Ambiguous during DST transitions (spring forward, fall back)
2. ⚠️ Cross-timezone queries impossible (no UTC reference)
3. ⚠️ Historical analysis broken if system timezone changes

**SQL Server Best Practice:** Store as UTC, display as local
```python
def _to_utc_naive(ts) -> Optional[pd.Timestamp]:
    """Convert to UTC, then strip timezone for SQL Server."""
    result = pd.to_datetime(ts, errors='coerce', utc=True)
    if result is pd.NaT:
        return None
    # SQL Server doesn't support tz-aware DATETIME2, so store UTC as naive
    return result.tz_localize(None) if result.tz else result
```

**Schema Change:**
```sql
-- Add computed column for display
ALTER TABLE dbo.ACM_HealthTimeline 
ADD TimestampLocal AS DATEADD(HOUR, DATEDIFF(HOUR, GETUTCDATE(), GETDATE()), Timestamp);

-- Document that Timestamp is UTC
EXEC sp_addextendedproperty 
    @name = 'Description', 
    @value = 'Timestamp stored in UTC; use TimestampLocal for local display',
    @level0type = 'SCHEMA', @level0name = 'dbo',
    @level1type = 'TABLE', @level1name = 'ACM_HealthTimeline',
    @level2type = 'COLUMN', @level2name = 'Timestamp';
```

---

## 9. Gap Analysis

### 9.1 Missing Features

| Feature | Current State | Recommendation | Priority |
|---------|---------------|----------------|----------|
| **Data validation before write** | ❌ None | Add schema validation layer | High |
| **Write performance monitoring** | ⚠️ Partial (stats counter) | Add per-table timing, row counts | Medium |
| **Retry logic for transient errors** | ❌ None | Implement exponential backoff | High |
| **Batch progress in SQL** | ❌ File only | Create ACM_BatchProgress table | High |
| **Unique constraints on time-series** | ❌ None | Add UQ on (RunID, EquipID, Timestamp) | Critical |
| **Transaction verification** | ❌ None | Check @@TRANCOUNT after commit | High |
| **Audit trail for data cleaning** | ❌ None | Log extreme values, NaNs replaced | Medium |
| **Connection pooling** | ❌ Single connection | Implement pool for parallel writes | Low |
| **Circuit breaker for SQL failures** | ⚠️ Partial (cache) | Add backoff, failure threshold | Medium |

---

### 9.2 Documentation Gaps

| Topic | Current Docs | Gap |
|-------|--------------|-----|
| **RunLog vs ACM_Runs** | ❌ Not explained | When to query which table |
| **Transaction boundaries** | ⚠️ Mentioned | Detailed commit/rollback flow diagram |
| **Coldstart state machine** | ❌ None | PENDING → IN_PROGRESS → COMPLETE transitions |
| **Progress file format** | ❌ None | Schema, versioning, migration path |
| **SQL performance tuning** | ⚠️ Brief | Index strategies, query patterns |
| **Error recovery procedures** | ❌ None | Operator runbook for failures |
| **Batch mode vs file mode** | ⚠️ Partial | Complete comparison, migration guide |

---

## 10. Recommendations

### 10.1 Critical (Deploy Blockers)

1. **Add UNIQUE constraints on time-series tables**
   ```sql
   ALTER TABLE ACM_HealthTimeline
   ADD CONSTRAINT UQ_HealthTimeline_Run_Equip_Time 
   UNIQUE (RunID, EquipID, Timestamp);
   -- Repeat for all 26 tables
   ```
   **Why:** Prevents duplicate data on re-runs

2. **Verify autocommit mode assumption**
   ```python
   # At SQL client initialization
   actual_autocommit = sql_client.conn.autocommit
   Console.info(f"[SQL] Connection autocommit mode: {actual_autocommit}")
   if not actual_autocommit:
       Console.warn("[SQL] Autocommit is FALSE - explicit commits required")
   ```
   **Why:** Silent commit failures if assumption wrong

3. **Add transaction verification**
   ```python
   # After commit
   cur.execute("SELECT @@TRANCOUNT")
   tran_count = cur.fetchone()[0]
   if tran_count > 0:
       raise RuntimeError(f"Transaction not committed (@@TRANCOUNT={tran_count})")
   ```
   **Why:** Detect partial commit scenarios

4. **Validate critical columns before SQL write**
   ```python
   CRITICAL_COLS = {'RunID', 'EquipID', 'Timestamp'}
   missing = CRITICAL_COLS - set(df.columns)
   if missing:
       raise ValueError(f"Missing critical columns: {missing}")
   ```
   **Why:** Catch schema mismatches before data loss

---

### 10.2 High Priority (Week 1)

5. **Create ACM_BatchProgress table** (replace JSON file)
   ```sql
   CREATE TABLE dbo.ACM_BatchProgress (
       EquipID INT PRIMARY KEY,
       ColdstartComplete BIT DEFAULT 0,
       LastBatchEndTime DATETIME2,
       BatchesCompleted INT DEFAULT 0,
       TickMinutes INT,
       ConfigHash VARCHAR(64),
       UpdatedAt DATETIME2 DEFAULT GETUTCDATE()
   )
   ```
   **Why:** Queryable, concurrent-safe, backed up

6. **Implement retry logic with exponential backoff**
   ```python
   @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
   def _bulk_insert_sql_with_retry(self, table_name, df):
       return self._bulk_insert_sql(table_name, df)
   ```
   **Why:** Transient errors (deadlocks, network) shouldn't fail runs

7. **Add per-table write timing and logging**
   ```python
   start = time.perf_counter()
   inserted = self._bulk_insert_sql(table_name, df)
   elapsed = time.perf_counter() - start
   Console.info(f"[SQL] {table_name}: {inserted} rows in {elapsed:.2f}s ({inserted/elapsed:.0f} rows/sec)")
   ```
   **Why:** Identify slow tables, monitor performance degradation

8. **Merge RunLog and ACM_Runs or add FK relationship**
   ```sql
   ALTER TABLE ACM_Runs 
   ADD CONSTRAINT FK_ACM_Runs_RunLog 
   FOREIGN KEY (RunID) REFERENCES dbo.RunLog(RunID);
   ```
   **Why:** Data consistency, simplified queries

---

### 10.3 Medium Priority (Month 1)

9. **Convert timestamps to UTC storage**
   - Change `_to_naive()` to `_to_utc_naive()`
   - Add computed local columns: `TimestampLocal AS DATEADD(...)`
   - Document in schema: "Timestamp is UTC"

10. **Implement LRU cache with TTL**
    - Replace unbounded dicts with `LRUCache(max_size=100, ttl_seconds=300)`
    - Prevents memory leaks, detects schema changes

11. **Add audit table for data cleaning**
    ```sql
    CREATE TABLE dbo.ACM_DataQualityEvents (
        EventID BIGINT IDENTITY PRIMARY KEY,
        RunID UNIQUEIDENTIFIER,
        TableName VARCHAR(100),
        ColumnName VARCHAR(100),
        EventType VARCHAR(50),  -- 'extreme_float', 'nan_replaced', 'schema_mismatch'
        AffectedRows INT,
        SampleValues NVARCHAR(500),
        EventTime DATETIME2 DEFAULT GETUTCDATE()
    )
    ```

12. **Optimize bulk inserts with TVP**
    - Create USER-DEFINED TABLE TYPES for high-volume tables
    - Implement TVP fallback for pyodbc compatibility

---

### 10.4 Low Priority (Future)

13. **Connection pooling** (if parallel writes implemented)
14. **Partitioning strategy** for time-series tables >100M rows
15. **Data retention policies** for RunLog, ColdstartState
16. **Real-time monitoring dashboard** for batch progress

---

## 11. Testing Recommendations

### 11.1 Integration Tests Needed

```python
def test_batch_run_sql_writes():
    """Verify complete batch run writes to all 26 tables."""
    # Run ACM for single equipment, single batch
    run_id = run_acm_batch(equip='TEST_EQUIP', window='1h')
    
    # Verify RunLog
    assert run_exists_in_runlog(run_id)
    assert get_run_outcome(run_id) == 'OK'
    
    # Verify ACM_Runs
    assert run_exists_in_acm_runs(run_id)
    assert get_health_status(run_id) in ('HEALTHY', 'CAUTION', 'ALERT')
    
    # Verify all analytics tables populated
    for table in EXPECTED_TABLES:
        row_count = get_table_row_count(table, run_id)
        assert row_count > 0, f"Table {table} has no rows for RunID={run_id}"

def test_batch_resume_after_failure():
    """Verify batch progress resumption after interruption."""
    # Start batch run
    runner = start_batch_run(equip='TEST_EQUIP', batches=10)
    
    # Kill after 5 batches
    runner.interrupt_after_batches(5)
    
    # Verify progress saved
    progress = load_batch_progress('TEST_EQUIP')
    assert progress['batches_completed'] == 5
    
    # Resume
    runner = resume_batch_run(equip='TEST_EQUIP')
    
    # Verify continues from batch 6
    assert runner.next_batch_number == 6

def test_transaction_rollback_on_error():
    """Verify rollback when SQL write fails mid-transaction."""
    # Inject error on table 15/26
    with patch('output_manager._bulk_insert_sql') as mock:
        mock.side_effect = [
            *[100] * 14,  # First 14 tables succeed
            Exception("Simulated failure"),  # Table 15 fails
        ]
        
        with pytest.raises(Exception):
            run_acm_batch(equip='TEST_EQUIP')
        
        # Verify NO data committed (rollback successful)
        for table in EXPECTED_TABLES[:14]:
            assert get_table_row_count(table, run_id) == 0

def test_duplicate_runid_prevention():
    """Verify duplicate RunID handling."""
    run_id = uuid.uuid4()
    
    # First run
    run_acm_batch(equip='TEST_EQUIP', run_id=run_id)
    count1 = get_table_row_count('ACM_HealthTimeline', run_id)
    
    # Re-run with same RunID (simulates crash recovery)
    run_acm_batch(equip='TEST_EQUIP', run_id=run_id)
    count2 = get_table_row_count('ACM_HealthTimeline', run_id)
    
    # Verify no duplicates (count should be same, not doubled)
    assert count2 == count1
```

---

### 11.2 Performance Tests

```python
def test_bulk_insert_performance():
    """Benchmark bulk insert throughput."""
    df = generate_test_dataframe(rows=100_000)
    
    start = time.perf_counter()
    output_mgr._bulk_insert_sql('ACM_HealthTimeline', df)
    elapsed = time.perf_counter() - start
    
    throughput = len(df) / elapsed
    print(f"Throughput: {throughput:.0f} rows/sec")
    
    # Assert meets minimum performance
    assert throughput > 10_000, "Throughput below acceptable threshold"

def test_concurrent_batch_runs():
    """Verify multiple batch runners don't corrupt data."""
    # Start 3 runners for different equipment simultaneously
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(run_acm_batch, equip='EQUIP_1'),
            executor.submit(run_acm_batch, equip='EQUIP_2'),
            executor.submit(run_acm_batch, equip='EQUIP_3'),
        ]
        
        # Wait for completion
        results = [f.result() for f in futures]
    
    # Verify no data corruption (row counts match expected)
    for equip in ['EQUIP_1', 'EQUIP_2', 'EQUIP_3']:
        run_id = get_latest_run_id(equip)
        for table in EXPECTED_TABLES:
            row_count = get_table_row_count(table, run_id)
            assert row_count > 0
```

---

## 12. Conclusion

### 12.1 Current State Assessment

**Overall SQL Batch Mode Readiness: 7.5/10**

| Category | Score | Rationale |
|----------|-------|-----------|
| **Run Tracking** | 8/10 | Dual-table approach works, but redundancy concerns |
| **Data Writes** | 7/10 | Comprehensive coverage, but transaction management gaps |
| **Progress Tracking** | 6/10 | Works but file-based approach fragile |
| **Error Handling** | 6/10 | Basic rollback present, missing retry logic |
| **Data Integrity** | 6/10 | No unique constraints, potential duplicates |
| **Performance** | 8/10 | Acceptable throughput, caching helps |
| **Monitoring** | 5/10 | Basic stats, no per-table visibility |
| **Documentation** | 7/10 | Good user docs, missing technical diagrams |

---

### 12.2 Deployment Readiness

✅ **Ready for Production (with mitigations):**
- Core functionality works - 26 tables populated correctly
- Coldstart logic proven in testing
- Batch processing handles interruptions gracefully
- Performance acceptable for typical workloads

⚠️ **Requires Pre-Deployment Changes:**
1. Add UNIQUE constraints on time-series tables (critical)
2. Verify autocommit mode (critical)
3. Add transaction verification (critical)
4. Implement retry logic (high)
5. Create ACM_BatchProgress table (high)

🔴 **Not Recommended Without:**
- Unique constraints (data integrity risk)
- Transaction verification (silent failure risk)
- Retry logic (transient error brittleness)

---

### 12.3 Next Steps

**Immediate (Before Production):**
1. [ ] Add UNIQUE constraints script
2. [ ] Verify SQL connection autocommit setting
3. [ ] Add transaction verification code
4. [ ] Test rollback scenarios

**Short-Term (Sprint 1-2):**
5. [ ] Implement retry with exponential backoff
6. [ ] Create ACM_BatchProgress table and migration
7. [ ] Add per-table timing logs
8. [ ] Merge RunLog and ACM_Runs schemas

**Long-Term (Backlog):**
9. [ ] Optimize with TVP bulk inserts
10. [ ] UTC timestamp migration
11. [ ] LRU cache with TTL
12. [ ] Data quality audit table

---

## Appendix A: SQL Schema Reference

### A.1 Run Tracking Tables

```sql
-- Core run lifecycle (stored procedures)
CREATE TABLE dbo.RunLog (
    RunID UNIQUEIDENTIFIER PRIMARY KEY,
    EquipID INT,
    Stage NVARCHAR(32),
    StartEntryDateTime DATETIME2(3),
    EndEntryDateTime DATETIME2(3),
    Outcome NVARCHAR(16),  -- 'OK', 'NOOP', 'FAIL'
    RowsRead INT,
    RowsWritten INT,
    ErrorJSON NVARCHAR(MAX),
    TriggerReason NVARCHAR(64),
    Version NVARCHAR(32),
    ConfigHash NVARCHAR(64),
    WindowStartEntryDateTime DATETIME2(3),
    WindowEndEntryDateTime DATETIME2(3)
);

-- Comprehensive run metadata (Python writes)
CREATE TABLE dbo.ACM_Runs (
    RunID UNIQUEIDENTIFIER PRIMARY KEY,
    EquipID INT NOT NULL,
    EquipName NVARCHAR(200),
    StartedAt DATETIME2 NOT NULL,
    CompletedAt DATETIME2,
    DurationSeconds INT,
    ConfigSignature VARCHAR(64),
    TrainRowCount INT,
    ScoreRowCount INT,
    EpisodeCount INT,
    HealthStatus VARCHAR(50),  -- 'HEALTHY', 'CAUTION', 'ALERT'
    AvgHealthIndex FLOAT,
    MinHealthIndex FLOAT,
    MaxFusedZ FLOAT,
    DataQualityScore FLOAT,
    RefitRequested BIT DEFAULT 0,
    ErrorMessage NVARCHAR(1000),
    KeptColumns NVARCHAR(MAX),
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_ACM_Runs_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID),
    INDEX IX_ACM_Runs_EquipStarted (EquipID, StartedAt DESC),
    INDEX IX_ACM_Runs_Status (EquipID, HealthStatus) WHERE HealthStatus IN ('CAUTION', 'ALERT')
);
```

---

## Appendix B: File Inventory

### B.1 Core Files

| File | Lines | Purpose | Audit Notes |
|------|-------|---------|-------------|
| `scripts/sql_batch_runner.py` | 897 | Batch orchestration | Progress tracking (line 311-341), coldstart logic (line 372-438) |
| `core/acm_main.py` | 3600+ | Main pipeline | SQL writes (line 3307+), run metadata (line 3436, 3502) |
| `core/output_manager.py` | 1800+ | Output coordination | Bulk insert (line 1314), transaction mgmt (line 558) |
| `core/run_metadata_writer.py` | 242 | ACM_Runs writer | Health computation (line 132-161), metadata extraction (line 163-208) |
| `scripts/sql/20_stored_procs.sql` | 96 | Run lifecycle SPs | usp_ACM_StartRun (line 43), usp_ACM_FinalizeRun (line 79) |
| `scripts/sql/54_create_acm_runs_table.sql` | 62 | ACM_Runs DDL | Table definition, indexes |
| `scripts/sql/55_create_coldstart_tracking.sql` | 210 | Coldstart DDL & SPs | ACM_ColdstartState table, check/update procedures |

---

## Appendix C: Glossary

**Terms:**
- **Batch Mode:** Sequential processing of time-windowed data chunks
- **Coldstart:** Initial model training when no prior models exist
- **RunID:** Unique identifier (UUID) for each ACM execution
- **Tick:** Fixed time window size for batch processing (e.g., 30 minutes)
- **Outcome:** Run result status: OK (success), NOOP (deferred), FAIL (error)
- **Fused Z-Score:** Combined anomaly score from multiple detectors
- **Health Index:** Inverse metric of fused z-score: `100 / (1 + z²)`

**Acronyms:**
- TVP: Table-Valued Parameter (SQL Server bulk insert optimization)
- LRU: Least Recently Used (cache eviction policy)
- TTL: Time To Live (cache expiration)
- DDL: Data Definition Language (CREATE TABLE, etc.)
- DML: Data Manipulation Language (INSERT, UPDATE, etc.)

---

**Document Version:** 1.0  
**Last Updated:** November 15, 2025  
**Next Review:** After deployment validation

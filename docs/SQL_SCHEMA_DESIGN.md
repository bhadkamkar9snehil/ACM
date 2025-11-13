# ACM SQL Schema Design - Holistic Analysis

## Current State Assessment (October 28, 2025)

### Files Generated Per Run (26 files)
```
Core Outputs:
- scores.csv (6,741 rows) - Time-series detector scores
- episodes.csv (3 rows) - Anomaly episodes
- culprits.jsonl - Detailed culprit attribution
- run.jsonl - Run metadata

Tables (26 CSV files):
1. health_timeline.csv - Health index over time
2. regime_timeline.csv - Operating regime over time
3. contrib_now.csv - Current sensor contributions
4. contrib_timeline.csv (47,187 rows) - Contribution over time
5. drift_series.csv - Drift detector series
6. drift_events.csv - Drift change points
7. threshold_crossings.csv (462 rows) - Alert events
8. since_when.csv - Duration in current state
9. sensor_rank_now.csv - Current sensor ranking
10. regime_occupancy.csv - Regime time distribution
11. regime_transition_matrix.csv - Regime changes
12. regime_dwell_stats.csv - Regime duration stats
13. health_hist.csv - Health distribution
14. alert_age.csv - Alert duration tracking
15. defect_summary.csv - Defect overview
16. defect_timeline.csv (819 rows) - Defect history
17. sensor_defects.csv - Per-detector violation counts
18. health_zone_by_period.csv (142 rows) - Aggregated health zones
19. sensor_anomaly_by_period.csv (738 rows) - Aggregated anomalies
20. regime_stability.csv - Regime stability metrics
21. detector_correlation.csv (28 rows) - Detector relationships
22. calibration_summary.csv - Detector calibration stats
23. episode_metrics.csv - Episode aggregate metrics
24. culprit_history.csv - Episode-level culprits
25. data_quality.csv - Data quality report
26. regime_summary.csv - Regime overview
```

### Current SQL Tables (Partial Implementation)
```sql
Core Tables:
✅ ACM_Scores_Wide (20,223 rows) - Wide format, all detectors
✅ ACM_Episodes (15 rows) - Episode records

Analytics Tables:
✅ ACM_HealthTimeline (13,482 rows)
✅ ACM_RegimeTimeline (13,482 rows)
✅ ACM_DetectorCorrelation (6 rows)
✅ ACM_CalibrationSummary (14 rows)
✅ ACM_RegimeTransitions (4 rows)
✅ ACM_RegimeDwellStats (4 rows)
✅ ACM_ThresholdCrossings (462 rows)
✅ ACM_RegimeOccupancy (4 rows)
✅ ACM_EpisodeMetrics (2 rows)
✅ ACM_CulpritHistory (3 rows)
❌ ACM_DriftEvents (0 rows) - No data yet

Missing Tables (16 tables):
❌ contrib_now, contrib_timeline
❌ drift_series
❌ since_when, sensor_rank_now
❌ health_hist, alert_age
❌ defect_summary, defect_timeline, sensor_defects
❌ health_zone_by_period, sensor_anomaly_by_period
❌ regime_stability, regime_summary
❌ data_quality
❌ run.jsonl metadata
```

## Design Problems Identified

### 1. **Schema Follows CSV Structure (Anti-Pattern)**
Current approach blindly mirrors CSV column names instead of designing for:
- Query efficiency
- Normalization
- Business logic
- Multi-equipment scale
- Time-series analysis
- Dashboard/BI integration

### 2. **Missing Core Dimensions**
- **Equipment Hierarchy**: No link to XStudio_Equipment_Tag_Mst_Vw
- **Tag Metadata**: Detector names are strings, not FK to tag registry
- **Run Metadata**: run.jsonl not persisted (timing, config, quality)
- **Temporal Partitioning**: No date-based partitioning for scale

### 3. **Denormalization Issues**
- **ACM_Scores_Wide**: 22 columns per row (ar1_z, pca_spe_z, etc.)
  - Problem: Schema changes when detectors added/removed
  - Problem: Cannot query "all detectors > threshold" efficiently
  - Problem: Column explosion with 50+ equipment types
  
### 4. **Missing Aggregation Tables**
- No daily/hourly rollups for dashboard performance
- No pre-computed KPIs for executive dashboards
- Every query re-scans millions of rows

### 5. **Scale Considerations**
- **Multiple Instances**: Currently handled (RunID + EquipID)
- **High Frequency**: Every few minutes → millions of rows/day
- **Retention**: No archival strategy (5 years = billions of rows)
- **Partitioning**: None (queries scan entire tables)
- **Indexing**: Minimal (only PKs)

## Proposed Normalized Schema (Long-Term)

### **Core Time-Series Tables**

```sql
-- Fact Table: Detector Scores (Long Format)
CREATE TABLE ACM_DetectorScores (
    ID BIGINT IDENTITY(1,1) PRIMARY KEY,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    DetectorType VARCHAR(50) NOT NULL, -- 'ar1', 'pca_spe', 'mhal', etc.
    TagID INT NULL, -- FK to tag registry (for tag-level detectors)
    ZScore FLOAT NOT NULL,
    RawValue FLOAT NULL,
    Threshold FLOAT NULL,
    IsAnomaly BIT DEFAULT 0,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    INDEX IX_DetectorScores_EquipTS (EquipID, Timestamp) INCLUDE (DetectorType, ZScore),
    INDEX IX_DetectorScores_RunDetector (RunID, DetectorType, EquipID)
) ON PS_ACM_Monthly(Timestamp); -- Monthly partitioning

-- Fact Table: Fused Scores
CREATE TABLE ACM_FusedScores (
    ID BIGINT IDENTITY(1,1) PRIMARY KEY,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    FusedZ FLOAT NOT NULL,
    HealthIndex FLOAT NOT NULL,
    HealthZone VARCHAR(20) NOT NULL, -- 'GOOD', 'WATCH', 'ALERT'
    RegimeLabel INT NULL,
    RegimeState VARCHAR(50) NULL,
    AlertMode VARCHAR(20) NULL,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    INDEX IX_FusedScores_EquipTS (EquipID, Timestamp) INCLUDE (FusedZ, HealthZone),
    INDEX IX_FusedScores_Anomalies (EquipID, HealthZone, Timestamp) WHERE HealthZone = 'ALERT'
) ON PS_ACM_Monthly(Timestamp);

-- Fact Table: Episodes (Normalized)
CREATE TABLE ACM_Episodes (
    EpisodeID BIGINT IDENTITY(1,1) PRIMARY KEY,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    StartTs DATETIME2 NOT NULL,
    EndTs DATETIME2 NULL,
    DurationSeconds INT NULL,
    MaxFusedZ FLOAT NULL,
    AvgFusedZ FLOAT NULL,
    PeakTimestamp DATETIME2 NULL,
    Severity VARCHAR(20) NULL, -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    Status VARCHAR(20) DEFAULT 'ACTIVE', -- 'ACTIVE', 'CLOSED', 'ACKNOWLEDGED'
    AcknowledgedBy INT NULL,
    AcknowledgedAt DATETIME2 NULL,
    Notes NVARCHAR(1000) NULL,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    INDEX IX_Episodes_EquipStart (EquipID, StartTs DESC),
    INDEX IX_Episodes_Active (EquipID, Status) WHERE Status = 'ACTIVE'
);

-- Fact Table: Episode Culprits (Many-to-Many)
CREATE TABLE ACM_EpisodeCulprits (
    ID BIGINT IDENTITY(1,1) PRIMARY KEY,
    EpisodeID BIGINT NOT NULL,
    DetectorType VARCHAR(50) NOT NULL,
    TagID INT NULL, -- FK to tag registry
    TagName NVARCHAR(200) NULL,
    ContributionPct FLOAT NULL,
    MaxZScore FLOAT NULL,
    AvgZScore FLOAT NULL,
    FOREIGN KEY (EpisodeID) REFERENCES ACM_Episodes(EpisodeID) ON DELETE CASCADE,
    INDEX IX_EpisodeCulprits_Episode (EpisodeID),
    INDEX IX_EpisodeCulprits_Tag (TagID, DetectorType)
);
```

### **Dimension Tables**

```sql
-- Dimension: Equipment Registry (Link to XStudio)
CREATE TABLE ACM_Equipment (
    EquipID INT PRIMARY KEY,
    EquipName NVARCHAR(200) NOT NULL,
    EquipType VARCHAR(100) NULL, -- 'Motor', 'Pump', 'Fan', 'Turbine'
    Plant VARCHAR(100) NULL,
    Area VARCHAR(100) NULL,
    Unit VARCHAR(100) NULL,
    IsActive BIT DEFAULT 1,
    ConfigSignature VARCHAR(64) NULL, -- Config hash
    LastRunAt DATETIME2 NULL,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    UpdatedAt DATETIME2 DEFAULT GETUTCDATE()
);

-- Dimension: Tag Registry (Link to XStudio_Equipment_Tag_Mst_Vw)
CREATE TABLE ACM_Tags (
    TagID INT PRIMARY KEY,
    TagName NVARCHAR(200) NOT NULL,
    InstrumentTag NVARCHAR(200) NULL,
    EquipID INT NOT NULL,
    Attribute NVARCHAR(200) NULL,
    TagType VARCHAR(50) NULL, -- 'Weight', 'Status', 'Parameter'
    UOM VARCHAR(50) NULL,
    HHRange FLOAT NULL,
    LLRange FLOAT NULL,
    IsActive BIT DEFAULT 1,
    FOREIGN KEY (EquipID) REFERENCES ACM_Equipment(EquipID),
    INDEX IX_Tags_Equip (EquipID, IsActive)
);

-- Dimension: Detector Types
CREATE TABLE ACM_DetectorTypes (
    DetectorType VARCHAR(50) PRIMARY KEY,
    DisplayName VARCHAR(100) NOT NULL,
    Description NVARCHAR(500) NULL,
    Category VARCHAR(50) NULL, -- 'Temporal', 'Outlier', 'Correlation', 'Regime'
    IsActive BIT DEFAULT 1
);

-- Dimension: Run Metadata
CREATE TABLE ACM_Runs (
    RunID UNIQUEIDENTIFIER PRIMARY KEY,
    EquipID INT NOT NULL,
    StartedAt DATETIME2 NOT NULL,
    CompletedAt DATETIME2 NULL,
    DurationSeconds INT NULL,
    ConfigSignature VARCHAR(64) NULL,
    TrainRowCount INT NULL,
    ScoreRowCount INT NULL,
    EpisodeCount INT NULL,
    HealthStatus VARCHAR(50) NULL, -- 'HEALTHY', 'DEGRADED', 'CRITICAL'
    QualityScore FLOAT NULL,
    RefitRequested BIT DEFAULT 0,
    ErrorMessage NVARCHAR(1000) NULL,
    CreatedBy VARCHAR(100) DEFAULT SYSTEM_USER,
    FOREIGN KEY (EquipID) REFERENCES ACM_Equipment(EquipID),
    INDEX IX_Runs_EquipStarted (EquipID, StartedAt DESC)
);
```

### **Aggregation Tables (Pre-computed for Dashboards)**

```sql
-- Aggregation: Hourly Health Summary
CREATE TABLE ACM_HealthSummary_Hourly (
    ID BIGINT IDENTITY(1,1) PRIMARY KEY,
    EquipID INT NOT NULL,
    HourBucket DATETIME2 NOT NULL, -- Truncated to hour
    AvgHealthIndex FLOAT NULL,
    MinHealthIndex FLOAT NULL,
    MaxFusedZ FLOAT NULL,
    AvgFusedZ FLOAT NULL,
    MinutesGood INT DEFAULT 0,
    MinutesWatch INT DEFAULT 0,
    MinutesAlert INT DEFAULT 0,
    AnomalyCount INT DEFAULT 0,
    ThresholdCrossings INT DEFAULT 0,
    SamplesCount INT DEFAULT 0,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    UNIQUE (EquipID, HourBucket),
    INDEX IX_HealthSummary_EquipHour (EquipID, HourBucket DESC)
) ON PS_ACM_Monthly(HourBucket);

-- Aggregation: Daily Equipment KPIs
CREATE TABLE ACM_EquipmentKPI_Daily (
    ID BIGINT IDENTITY(1,1) PRIMARY KEY,
    EquipID INT NOT NULL,
    DateBucket DATE NOT NULL,
    AvgHealthIndex FLOAT NULL,
    MinHealthIndex FLOAT NULL,
    MaxFusedZ FLOAT NULL,
    TotalEpisodes INT DEFAULT 0,
    TotalEpisodeDuration INT DEFAULT 0, -- seconds
    AvgEpisodeDuration INT DEFAULT 0,
    TopCulpritDetector VARCHAR(50) NULL,
    TopCulpritTag NVARCHAR(200) NULL,
    RegimeStabilityScore FLOAT NULL,
    DataQualityScore FLOAT NULL,
    UptimePct FLOAT NULL,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    UNIQUE (EquipID, DateBucket),
    INDEX IX_EquipmentKPI_Date (DateBucket DESC, EquipID)
);

-- Aggregation: Detector Performance Summary
CREATE TABLE ACM_DetectorSummary (
    ID BIGINT IDENTITY(1,1) PRIMARY KEY,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    DetectorType VARCHAR(50) NOT NULL,
    AvgZScore FLOAT NULL,
    StdZScore FLOAT NULL,
    MaxZScore FLOAT NULL,
    P95ZScore FLOAT NULL,
    P99ZScore FLOAT NULL,
    ThresholdUsed FLOAT NULL,
    ExceedanceCount INT DEFAULT 0,
    ExceedancePct FLOAT NULL,
    SamplesCount INT DEFAULT 0,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    UNIQUE (RunID, EquipID, DetectorType),
    INDEX IX_DetectorSummary_EquipDetector (EquipID, DetectorType)
);
```

### **Operational Tables**

```sql
-- Data Quality Tracking
CREATE TABLE ACM_DataQuality (
    ID BIGINT IDENTITY(1,1) PRIMARY KEY,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CheckType VARCHAR(100) NOT NULL, -- 'missing_pct', 'cadence_ok', 'outlier_pct'
    CheckResult VARCHAR(20) NOT NULL, -- 'PASS', 'WARN', 'FAIL'
    MetricValue FLOAT NULL,
    Threshold FLOAT NULL,
    Message NVARCHAR(500) NULL,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    INDEX IX_DataQuality_EquipRun (EquipID, RunID)
);

-- Configuration Change History
CREATE TABLE ACM_ConfigHistory (
    ID BIGINT IDENTITY(1,1) PRIMARY KEY,
    EquipID INT NOT NULL,
    ConfigSignature VARCHAR(64) NOT NULL,
    ChangedBy VARCHAR(100) NULL,
    ChangedAt DATETIME2 DEFAULT GETUTCDATE(),
    ParameterName VARCHAR(200) NOT NULL,
    OldValue NVARCHAR(500) NULL,
    NewValue NVARCHAR(500) NULL,
    ChangeReason NVARCHAR(500) NULL,
    INDEX IX_ConfigHistory_EquipTime (EquipID, ChangedAt DESC)
);
```

## Migration Strategy

### Phase 2A: Add Missing Tables (Immediate - Keep CSV Structure)
**Target: Complete parity with 26 CSV files**

```sql
-- Add 16 missing analytics tables following CSV structure
- ACM_ContributionTimeline (47k rows)
- ACM_DefectTimeline (819 rows)
- ACM_SensorAnomalyByPeriod (738 rows)
- ACM_HealthZoneByPeriod (142 rows)
- ACM_DataQuality
- ACM_AlertAge
- etc.
```

### Phase 2B: Enhance Existing Tables (Short-term - 2-4 weeks)
**Target: Add indexes, partitioning, metadata**

```sql
-- Add run metadata table
- ACM_Runs (from run.jsonl)

-- Add partitioning
- Monthly partitioning on all time-series tables

-- Add missing indexes
- Equipment + Timestamp
- Anomaly filters (WHERE HealthZone = 'ALERT')

-- Add equipment/tag dimensions
- Link to XStudio_Equipment_Tag_Mst_Vw
```

### Phase 3: Normalize Schema (Long-term - 2-3 months)
**Target: Production-ready normalized schema**

```sql
-- Replace ACM_Scores_Wide with ACM_DetectorScores (long format)
-- Add dimension tables (Equipment, Tags, DetectorTypes)
-- Add aggregation tables (Hourly, Daily)
-- Add partitioning strategy (monthly, 5-year retention)
-- Add archival process (cold storage after 1 year)
```

## Scale Design Decisions

### 1. **Partitioning Strategy**
```sql
-- Monthly partitioning for time-series
CREATE PARTITION FUNCTION PF_ACM_Monthly (DATETIME2)
AS RANGE RIGHT FOR VALUES (
    '2025-01-01', '2025-02-01', '2025-03-01', ...
);

-- Automatically add new partitions monthly
-- Archive partitions > 12 months to cold storage
```

### 2. **Retention Policy**
```
Hot Storage (SQL): Last 6 months (fast queries)
Warm Storage (SQL): 6-12 months (slower, partitioned)
Cold Storage (Archive): 1-5 years (data lake/blob)
Purge: > 5 years
```

### 3. **Indexing Strategy**
```sql
-- Clustered: Primary key (time-based for fact tables)
-- Non-clustered: Equipment + Timestamp (dashboard queries)
-- Filtered: Active episodes, anomalies only
-- Columnstore: Historical analysis (after 6 months)
```

### 4. **Query Optimization**
```sql
-- Pre-compute aggregations (hourly, daily)
-- Materialized views for complex joins
-- Dashboard queries hit aggregation tables only
-- Time-series queries use partitioning elimination
```

### 5. **Concurrent Writes**
```
✅ Already handled: RunID + EquipID partitioning
✅ Already handled: DELETE + INSERT pattern (idempotent)
⚠️  Need: Batch writes (1000 rows) for performance
⚠️  Need: Connection pooling for multiple instances
⚠️  Need: Lock timeout handling
```

## Immediate Action Items

1. **Complete Phase 2A** ✅ (10/11 done)
   - Add 16 missing tables with CSV structure
   - Verify all 26 CSV files → SQL

2. **Add Run Metadata Table**
   - Parse run.jsonl → ACM_Runs table
   - Track timing, row counts, quality

3. **Add Equipment Link**
   - Create ACM_Equipment dimension
   - Link to XStudio_Equipment_Tag_Mst_Vw
   - Populate from config

4. **Add Date Partitioning**
   - Partition time-series tables by month
   - Test query performance improvement

5. **Create Aggregation Tables**
   - ACM_HealthSummary_Hourly (dashboards)
   - ACM_EquipmentKPI_Daily (executive reports)

6. **Document Schema**
   - ERD diagram
   - Table catalog
   - Query examples
   - Dashboard patterns

## Questions to Answer

1. **What is retention requirement?** (Assuming 5 years)
2. **What is query SLA?** (Dashboard < 2 sec, Reports < 30 sec?)
3. **How many equipment instances?** (10? 100? 1000?)
4. **Run frequency per equipment?** (Every 5 min = 288/day)
5. **Expected row growth?** (1000 equip × 288 runs × 6741 rows = 1.9B rows/day?)
6. **Archive strategy?** (Data lake? Blob storage? Compressed files?)
7. **BI tool?** (Power BI? Grafana? Custom dashboard?)

## Recommended Next Steps

1. **Immediate** (This session):
   - Add all 16 missing CSV tables to SQL
   - Add ACM_Runs metadata table
   - Test full end-to-end dual-write

2. **This Week**:
   - Add equipment dimension (link to XStudio view)
   - Add monthly partitioning
   - Create hourly aggregation table
   - Test with 2nd equipment (GAS_TURBINE)

3. **Next Sprint**:
   - Normalize to long-format scores
   - Add tag dimension
   - Create daily KPI aggregations
   - Build sample dashboard queries

4. **Long-term**:
   - Implement retention/archival
   - Optimize for 1000+ equipment
   - Add alerting/notification tables
   - Build BI integration layer

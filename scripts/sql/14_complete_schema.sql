/*
====================================================================================
ACM SQL Schema - Complete Normalized Design
====================================================================================
Design Principles:
1. Proper normalization (separate time-series, metadata, aggregations)
2. Correct data types (DATETIME2 for timestamps, FLOAT for metrics, proper string lengths)
3. Comprehensive indexes (clustered on time, non-clustered on equipment+time)
4. Scale-ready (partitioning hints, proper PKs, efficient queries)
5. BI-friendly (denormalized where needed, pre-computed aggregations)

Schema Coverage:
- Core time-series: Scores, Episodes, Health, Regimes
- Analytics: Contributions, Defects, Thresholds, Correlations
- Aggregations: Hourly summaries, Period rollups, KPIs
- Metadata: Runs, Equipment, Data Quality
- All 26 CSV outputs covered

Author: ACM Team
Date: 2025-10-28
====================================================================================
*/

USE ACM;
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- ============================================================================
-- METADATA TABLES
-- ============================================================================

-- Run Metadata (from run.jsonl)
IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL DROP TABLE dbo.ACM_Runs;
CREATE TABLE dbo.ACM_Runs (
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    EquipName NVARCHAR(200) NULL,
    StartedAt DATETIME2 NOT NULL,
    CompletedAt DATETIME2 NULL,
    DurationSeconds INT NULL,
    ConfigSignature VARCHAR(64) NULL,
    TrainRowCount INT NULL,
    ScoreRowCount INT NULL,
    EpisodeCount INT NULL,
    HealthStatus VARCHAR(50) NULL, -- 'HEALTHY', 'DEGRADED', 'CRITICAL'
    AvgHealthIndex FLOAT NULL,
    MinHealthIndex FLOAT NULL,
    MaxFusedZ FLOAT NULL,
    DataQualityScore FLOAT NULL,
    RefitRequested BIT DEFAULT 0,
    ErrorMessage NVARCHAR(1000) NULL,
    KeptColumns NVARCHAR(MAX) NULL, -- JSON array from run.jsonl
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_Runs PRIMARY KEY CLUSTERED (RunID),
    INDEX IX_ACM_Runs_EquipStarted NONCLUSTERED (EquipID, StartedAt DESC),
    INDEX IX_ACM_Runs_Status NONCLUSTERED (EquipID, HealthStatus) WHERE HealthStatus IN ('DEGRADED', 'CRITICAL')
);
GO

-- Data Quality Metrics
IF OBJECT_ID('dbo.ACM_DataQuality', 'U') IS NOT NULL DROP TABLE dbo.ACM_DataQuality;
CREATE TABLE dbo.ACM_DataQuality (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CheckName VARCHAR(100) NOT NULL, -- 'missing_pct', 'cadence_ok', 'outlier_pct', 'duplicate_pct'
    CheckResult VARCHAR(20) NOT NULL, -- 'PASS', 'WARN', 'FAIL'
    MetricValue FLOAT NULL,
    ThresholdValue FLOAT NULL,
    Message NVARCHAR(500) NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_DataQuality PRIMARY KEY CLUSTERED (ID),
    INDEX IX_ACM_DataQuality_Run NONCLUSTERED (RunID, EquipID)
);
GO

-- ============================================================================
-- CORE TIME-SERIES TABLES (High Volume)
-- ============================================================================

-- Fused Scores with Health Metrics
IF OBJECT_ID('dbo.ACM_HealthTimeline', 'U') IS NOT NULL DROP TABLE dbo.ACM_HealthTimeline;
CREATE TABLE dbo.ACM_HealthTimeline (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    FusedZ FLOAT NOT NULL,
    HealthIndex FLOAT NOT NULL,
    HealthZone VARCHAR(20) NOT NULL, -- 'GOOD', 'WATCH', 'ALERT'
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_HealthTimeline PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp),
    INDEX IX_ACM_HealthTimeline_EquipTime NONCLUSTERED (EquipID, Timestamp DESC) INCLUDE (FusedZ, HealthIndex, HealthZone),
    INDEX IX_ACM_HealthTimeline_Alerts NONCLUSTERED (EquipID, HealthZone, Timestamp) WHERE HealthZone = 'ALERT'
);
GO

-- Regime Timeline
IF OBJECT_ID('dbo.ACM_RegimeTimeline', 'U') IS NOT NULL DROP TABLE dbo.ACM_RegimeTimeline;
CREATE TABLE dbo.ACM_RegimeTimeline (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    RegimeLabel INT NOT NULL,
    RegimeState VARCHAR(50) NULL, -- 'healthy', 'fault', etc.
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_RegimeTimeline PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp),
    INDEX IX_ACM_RegimeTimeline_EquipTime NONCLUSTERED (EquipID, Timestamp DESC) INCLUDE (RegimeLabel, RegimeState)
);
GO

-- Detector Contributions Timeline (Long Format - Normalized)
IF OBJECT_ID('dbo.ACM_ContributionTimeline', 'U') IS NOT NULL DROP TABLE dbo.ACM_ContributionTimeline;
CREATE TABLE dbo.ACM_ContributionTimeline (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    DetectorType VARCHAR(50) NOT NULL, -- 'ar1', 'pca_spe', 'mhal', etc.
    ContributionPct FLOAT NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_ContributionTimeline PRIMARY KEY CLUSTERED (ID),
    INDEX IX_ACM_ContributionTimeline_RunTime NONCLUSTERED (RunID, Timestamp, DetectorType),
    INDEX IX_ACM_ContributionTimeline_EquipTime NONCLUSTERED (EquipID, Timestamp DESC)
);
GO

-- Drift Series (CUSUM values over time)
IF OBJECT_ID('dbo.ACM_DriftSeries', 'U') IS NOT NULL DROP TABLE dbo.ACM_DriftSeries;
CREATE TABLE dbo.ACM_DriftSeries (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    DriftValue FLOAT NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_DriftSeries PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp),
    INDEX IX_ACM_DriftSeries_EquipTime NONCLUSTERED (EquipID, Timestamp DESC) INCLUDE (DriftValue)
);
GO

-- Defect Timeline (State Change Events)
IF OBJECT_ID('dbo.ACM_DefectTimeline', 'U') IS NOT NULL DROP TABLE dbo.ACM_DefectTimeline;
CREATE TABLE dbo.ACM_DefectTimeline (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    EventType VARCHAR(50) NOT NULL, -- 'ISSUE_START', 'ISSUE_END'
    HealthZone VARCHAR(20) NOT NULL,
    HealthIndex FLOAT NOT NULL,
    FusedZ FLOAT NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_DefectTimeline PRIMARY KEY CLUSTERED (ID),
    INDEX IX_ACM_DefectTimeline_EquipTime NONCLUSTERED (EquipID, Timestamp DESC) INCLUDE (EventType, HealthZone)
);
GO

-- ============================================================================
-- EPISODE TABLES
-- ============================================================================

-- Episodes (Wide Format - One Row Per Episode)
IF OBJECT_ID('dbo.ACM_Episodes', 'U') IS NOT NULL DROP TABLE dbo.ACM_Episodes;
CREATE TABLE dbo.ACM_Episodes (
    EpisodeID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    StartTs DATETIME2 NOT NULL,
    EndTs DATETIME2 NULL,
    DurationSeconds INT NULL,
    DurationHours FLOAT NULL,
    PeakFusedZ FLOAT NULL,
    AvgFusedZ FLOAT NULL,
    MinHealthIndex FLOAT NULL,
    PeakTimestamp DATETIME2 NULL,
    MaxRegimeLabel INT NULL,
    Culprits NVARCHAR(500) NULL, -- Comma-separated list
    AlertMode VARCHAR(50) NULL,
    Severity VARCHAR(20) NULL,
    Status VARCHAR(20) DEFAULT 'CLOSED',
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_Episodes PRIMARY KEY CLUSTERED (EpisodeID),
    INDEX IX_ACM_Episodes_RunEquip NONCLUSTERED (RunID, EquipID, StartTs DESC),
    INDEX IX_ACM_Episodes_EquipStart NONCLUSTERED (EquipID, StartTs DESC) INCLUDE (DurationHours, PeakFusedZ, Culprits),
    INDEX IX_ACM_Episodes_Active NONCLUSTERED (EquipID, Status) WHERE Status = 'ACTIVE'
);
GO

-- Episode Culprits (Normalized - Episode-Level Snapshot)
IF OBJECT_ID('dbo.ACM_EpisodeCulprits', 'U') IS NOT NULL DROP TABLE dbo.ACM_EpisodeCulprits;
CREATE TABLE dbo.ACM_EpisodeCulprits (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    EpisodeStartTs DATETIME2 NOT NULL,
    EpisodeEndTs DATETIME2 NULL,
    DurationHours FLOAT NULL,
    CulpritsText NVARCHAR(500) NULL, -- From CSV: "mhal_z(DEMO.SIM.FSAB)"
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_EpisodeCulprits PRIMARY KEY CLUSTERED (RunID, EquipID, EpisodeStartTs),
    INDEX IX_ACM_EpisodeCulprits_Equip NONCLUSTERED (EquipID, EpisodeStartTs DESC)
);
GO

-- ============================================================================
-- EVENT TABLES
-- ============================================================================

-- Threshold Crossings
IF OBJECT_ID('dbo.ACM_ThresholdCrossings', 'U') IS NOT NULL DROP TABLE dbo.ACM_ThresholdCrossings;
CREATE TABLE dbo.ACM_ThresholdCrossings (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    DetectorType VARCHAR(50) NOT NULL, -- 'ar1', 'pca_spe', etc.
    ZScore FLOAT NOT NULL,
    Threshold FLOAT NOT NULL,
    Direction VARCHAR(20) NOT NULL, -- 'rising', 'falling'
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_ThresholdCrossings PRIMARY KEY CLUSTERED (ID),
    INDEX IX_ACM_ThresholdCrossings_EquipTime NONCLUSTERED (EquipID, Timestamp DESC) INCLUDE (DetectorType, Direction),
    INDEX IX_ACM_ThresholdCrossings_Detector NONCLUSTERED (EquipID, DetectorType, Timestamp DESC)
);
GO

-- Drift Events (Change Point Detection)
IF OBJECT_ID('dbo.ACM_DriftEvents', 'U') IS NOT NULL DROP TABLE dbo.ACM_DriftEvents;
CREATE TABLE dbo.ACM_DriftEvents (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    DriftValue FLOAT NOT NULL,
    SegmentStart DATETIME2 NULL,
    SegmentEnd DATETIME2 NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_DriftEvents PRIMARY KEY CLUSTERED (ID),
    INDEX IX_ACM_DriftEvents_EquipTime NONCLUSTERED (EquipID, Timestamp DESC)
);
GO

-- ============================================================================
-- SUMMARY/SNAPSHOT TABLES (Per Run)
-- ============================================================================

-- Current Sensor Contributions (Snapshot at end of run)
IF OBJECT_ID('dbo.ACM_ContributionCurrent', 'U') IS NOT NULL DROP TABLE dbo.ACM_ContributionCurrent;
CREATE TABLE dbo.ACM_ContributionCurrent (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    DetectorType VARCHAR(50) NOT NULL,
    ContributionPct FLOAT NOT NULL,
    ZScore FLOAT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_ContributionCurrent PRIMARY KEY CLUSTERED (RunID, EquipID, DetectorType),
    INDEX IX_ACM_ContributionCurrent_Equip NONCLUSTERED (EquipID, ContributionPct DESC)
);
GO

-- Current Sensor Ranking
IF OBJECT_ID('dbo.ACM_SensorRanking', 'U') IS NOT NULL DROP TABLE dbo.ACM_SensorRanking;
CREATE TABLE dbo.ACM_SensorRanking (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    DetectorType VARCHAR(50) NOT NULL,
    RankPosition INT NOT NULL,
    ZScore FLOAT NOT NULL,
    ContributionPct FLOAT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_SensorRanking PRIMARY KEY CLUSTERED (RunID, EquipID, DetectorType),
    INDEX IX_ACM_SensorRanking_Rank NONCLUSTERED (EquipID, RankPosition)
);
GO

-- Since When Summary (Duration in current state)
IF OBJECT_ID('dbo.ACM_StateDuration', 'U') IS NOT NULL DROP TABLE dbo.ACM_StateDuration;
CREATE TABLE dbo.ACM_StateDuration (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    StateType VARCHAR(50) NOT NULL, -- 'health_zone', 'regime', 'alert'
    CurrentState VARCHAR(50) NOT NULL,
    DurationHours FLOAT NOT NULL,
    SinceTimestamp DATETIME2 NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_StateDuration PRIMARY KEY CLUSTERED (RunID, EquipID, StateType),
    INDEX IX_ACM_StateDuration_Equip NONCLUSTERED (EquipID, StateType)
);
GO

-- Alert Age (Time in alert state)
IF OBJECT_ID('dbo.ACM_AlertAge', 'U') IS NOT NULL DROP TABLE dbo.ACM_AlertAge;
CREATE TABLE dbo.ACM_AlertAge (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    AlertZone VARCHAR(20) NOT NULL, -- 'WATCH', 'ALERT'
    DurationHours FLOAT NOT NULL,
    StartTimestamp DATETIME2 NULL,
    RecordCount INT DEFAULT 0,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_AlertAge PRIMARY KEY CLUSTERED (RunID, EquipID, AlertZone),
    INDEX IX_ACM_AlertAge_Equip NONCLUSTERED (EquipID, AlertZone) WHERE DurationHours > 0
);
GO

-- Defect Summary (Aggregate counts)
IF OBJECT_ID('dbo.ACM_DefectSummary', 'U') IS NOT NULL DROP TABLE dbo.ACM_DefectSummary;
CREATE TABLE dbo.ACM_DefectSummary (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    TotalIssues INT DEFAULT 0,
    AlertIssues INT DEFAULT 0,
    WatchIssues INT DEFAULT 0,
    TotalDurationHours FLOAT NULL,
    AvgIssueDurationHours FLOAT NULL,
    MaxIssueDurationHours FLOAT NULL,
    CurrentHealthZone VARCHAR(20) NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_DefectSummary PRIMARY KEY CLUSTERED (RunID, EquipID),
    INDEX IX_ACM_DefectSummary_Equip NONCLUSTERED (EquipID) WHERE TotalIssues > 0
);
GO

-- Sensor Defects Summary
IF OBJECT_ID('dbo.ACM_SensorDefects', 'U') IS NOT NULL DROP TABLE dbo.ACM_SensorDefects;
CREATE TABLE dbo.ACM_SensorDefects (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    DetectorType VARCHAR(50) NOT NULL,
    DefectCount INT DEFAULT 0,
    DefectDurationHours FLOAT NULL,
    AvgZScore FLOAT NULL,
    MaxZScore FLOAT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_SensorDefects PRIMARY KEY CLUSTERED (RunID, EquipID, DetectorType),
    INDEX IX_ACM_SensorDefects_Equip NONCLUSTERED (EquipID, DefectCount DESC)
);
GO

-- ============================================================================
-- REGIME ANALYSIS TABLES
-- ============================================================================

-- Regime Occupancy (Time distribution)
IF OBJECT_ID('dbo.ACM_RegimeOccupancy', 'U') IS NOT NULL DROP TABLE dbo.ACM_RegimeOccupancy;
CREATE TABLE dbo.ACM_RegimeOccupancy (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    RegimeLabel INT NOT NULL,
    RecordCount INT DEFAULT 0,
    Percentage FLOAT NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_RegimeOccupancy PRIMARY KEY CLUSTERED (RunID, EquipID, RegimeLabel),
    INDEX IX_ACM_RegimeOccupancy_Equip NONCLUSTERED (EquipID, Percentage DESC)
);
GO

-- Regime Transitions (Markov matrix)
IF OBJECT_ID('dbo.ACM_RegimeTransitions', 'U') IS NOT NULL DROP TABLE dbo.ACM_RegimeTransitions;
CREATE TABLE dbo.ACM_RegimeTransitions (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    FromLabel INT NOT NULL,
    ToLabel INT NOT NULL,
    TransitionCount INT DEFAULT 0,
    Probability FLOAT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_RegimeTransitions PRIMARY KEY CLUSTERED (RunID, EquipID, FromLabel, ToLabel),
    INDEX IX_ACM_RegimeTransitions_Equip NONCLUSTERED (EquipID, TransitionCount DESC)
);
GO

-- Regime Dwell Statistics
IF OBJECT_ID('dbo.ACM_RegimeDwellStats', 'U') IS NOT NULL DROP TABLE dbo.ACM_RegimeDwellStats;
CREATE TABLE dbo.ACM_RegimeDwellStats (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    RegimeLabel INT NOT NULL,
    RunCount INT DEFAULT 0, -- Number of continuous segments
    MeanSeconds FLOAT NULL,
    MedianSeconds FLOAT NULL,
    MinSeconds FLOAT NULL,
    MaxSeconds FLOAT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_RegimeDwellStats PRIMARY KEY CLUSTERED (RunID, EquipID, RegimeLabel),
    INDEX IX_ACM_RegimeDwellStats_Equip NONCLUSTERED (EquipID, MeanSeconds DESC)
);
GO

-- Regime Stability Score
IF OBJECT_ID('dbo.ACM_RegimeStability', 'U') IS NOT NULL DROP TABLE dbo.ACM_RegimeStability;
CREATE TABLE dbo.ACM_RegimeStability (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    MetricName VARCHAR(100) NOT NULL, -- 'stability_score', 'transition_rate', etc.
    MetricValue FLOAT NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_RegimeStability PRIMARY KEY CLUSTERED (RunID, EquipID, MetricName),
    INDEX IX_ACM_RegimeStability_Equip NONCLUSTERED (EquipID, MetricName)
);
GO

-- ============================================================================
-- DETECTOR ANALYSIS TABLES
-- ============================================================================

-- Detector Correlation Matrix
IF OBJECT_ID('dbo.ACM_DetectorCorrelation', 'U') IS NOT NULL DROP TABLE dbo.ACM_DetectorCorrelation;
CREATE TABLE dbo.ACM_DetectorCorrelation (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    DetectorA VARCHAR(50) NOT NULL,
    DetectorB VARCHAR(50) NOT NULL,
    PearsonR FLOAT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_DetectorCorrelation PRIMARY KEY CLUSTERED (RunID, EquipID, DetectorA, DetectorB),
    INDEX IX_ACM_DetectorCorrelation_Equip NONCLUSTERED (EquipID)
);
GO

-- Calibration Summary (Per detector stats)
IF OBJECT_ID('dbo.ACM_CalibrationSummary', 'U') IS NOT NULL DROP TABLE dbo.ACM_CalibrationSummary;
CREATE TABLE dbo.ACM_CalibrationSummary (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    DetectorType VARCHAR(50) NOT NULL,
    Mean FLOAT NULL,
    StdDev FLOAT NULL,
    P95 FLOAT NULL,
    P99 FLOAT NULL,
    ClipZ FLOAT NULL,
    ClipPct FLOAT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_CalibrationSummary PRIMARY KEY CLUSTERED (RunID, EquipID, DetectorType),
    INDEX IX_ACM_CalibrationSummary_Equip NONCLUSTERED (EquipID, DetectorType)
);
GO

-- ============================================================================
-- AGGREGATION TABLES (Pre-computed for Dashboards)
-- ============================================================================

-- Health Distribution Histogram
IF OBJECT_ID('dbo.ACM_HealthHistogram', 'U') IS NOT NULL DROP TABLE dbo.ACM_HealthHistogram;
CREATE TABLE dbo.ACM_HealthHistogram (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    HealthBin VARCHAR(20) NOT NULL, -- '[90-95)', '[85-90)', etc.
    RecordCount INT DEFAULT 0,
    Percentage FLOAT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_HealthHistogram PRIMARY KEY CLUSTERED (RunID, EquipID, HealthBin),
    INDEX IX_ACM_HealthHistogram_Equip NONCLUSTERED (EquipID, RecordCount DESC)
);
GO

-- Health Zone by Period (Hourly/Daily rollups)
IF OBJECT_ID('dbo.ACM_HealthZoneByPeriod', 'U') IS NOT NULL DROP TABLE dbo.ACM_HealthZoneByPeriod;
CREATE TABLE dbo.ACM_HealthZoneByPeriod (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    PeriodStart DATETIME2 NOT NULL,
    PeriodType VARCHAR(20) NOT NULL, -- 'hour', 'day', 'week'
    HealthZone VARCHAR(20) NOT NULL,
    RecordCount INT DEFAULT 0,
    AvgHealthIndex FLOAT NULL,
    AvgFusedZ FLOAT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_HealthZoneByPeriod PRIMARY KEY CLUSTERED (RunID, EquipID, PeriodStart, PeriodType, HealthZone),
    INDEX IX_ACM_HealthZoneByPeriod_Equip NONCLUSTERED (EquipID, PeriodStart DESC)
);
GO

-- Sensor Anomaly by Period
IF OBJECT_ID('dbo.ACM_SensorAnomalyByPeriod', 'U') IS NOT NULL DROP TABLE dbo.ACM_SensorAnomalyByPeriod;
CREATE TABLE dbo.ACM_SensorAnomalyByPeriod (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    PeriodStart DATETIME2 NOT NULL,
    PeriodType VARCHAR(20) NOT NULL,
    DetectorType VARCHAR(50) NOT NULL,
    AnomalyCount INT DEFAULT 0,
    AvgZScore FLOAT NULL,
    MaxZScore FLOAT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_SensorAnomalyByPeriod PRIMARY KEY CLUSTERED (RunID, EquipID, PeriodStart, PeriodType, DetectorType),
    INDEX IX_ACM_SensorAnomalyByPeriod_Equip NONCLUSTERED (EquipID, PeriodStart DESC, DetectorType)
);
GO

-- Episode Aggregate Metrics (Per Run)
IF OBJECT_ID('dbo.ACM_EpisodeMetrics', 'U') IS NOT NULL DROP TABLE dbo.ACM_EpisodeMetrics;
CREATE TABLE dbo.ACM_EpisodeMetrics (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    TotalEpisodes INT DEFAULT 0,
    TotalDurationHours FLOAT NULL,
    AvgDurationHours FLOAT NULL,
    MedianDurationHours FLOAT NULL,
    MaxDurationHours FLOAT NULL,
    MinDurationHours FLOAT NULL,
    RatePerDay FLOAT NULL,
    MeanInterarrivalHours FLOAT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_EpisodeMetrics PRIMARY KEY CLUSTERED (RunID, EquipID),
    INDEX IX_ACM_EpisodeMetrics_Equip NONCLUSTERED (EquipID)
);
GO

-- Regime Summary (MISSING from original 26 - from CSV list)
IF OBJECT_ID('dbo.ACM_RegimeSummary', 'U') IS NOT NULL DROP TABLE dbo.ACM_RegimeSummary;
CREATE TABLE dbo.ACM_RegimeSummary (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    TotalRegimes INT DEFAULT 0,
    MostCommonRegime INT NULL,
    MostCommonPct FLOAT NULL,
    TransitionCount INT DEFAULT 0,
    AvgDwellSeconds FLOAT NULL,
    StabilityScore FLOAT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_RegimeSummary PRIMARY KEY CLUSTERED (RunID, EquipID),
    INDEX IX_ACM_RegimeSummary_Equip NONCLUSTERED (EquipID)
);
GO

-- ============================================================================
-- WIDE FORMAT TABLES (Keep for backward compatibility and quick queries)
-- ============================================================================

-- Scores Wide Format (All detectors in columns)
IF OBJECT_ID('dbo.ACM_Scores_Wide', 'U') IS NOT NULL DROP TABLE dbo.ACM_Scores_Wide;
CREATE TABLE dbo.ACM_Scores_Wide (
    ID BIGINT IDENTITY(1,1) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    ar1_z FLOAT NULL,
    pca_spe_z FLOAT NULL,
    pca_t2_z FLOAT NULL,
    mhal_z FLOAT NULL,
    iforest_z FLOAT NULL,
    gmm_z FLOAT NULL,
    cusum_z FLOAT NULL,
    hst_z FLOAT NULL,
    fused FLOAT NULL,
    regime_label INT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_Scores_Wide PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp),
    INDEX IX_ACM_Scores_Wide_EquipTime NONCLUSTERED (EquipID, Timestamp DESC) INCLUDE (fused, regime_label)
);
GO

PRINT 'ACM Schema created successfully - 26 tables covering all outputs';
PRINT 'Tables: Runs, DataQuality, HealthTimeline, RegimeTimeline, ContributionTimeline, DriftSeries, DefectTimeline,';
PRINT '        Episodes, EpisodeCulprits, ThresholdCrossings, DriftEvents, ContributionCurrent, SensorRanking,';
PRINT '        StateDuration, AlertAge, DefectSummary, SensorDefects, RegimeOccupancy, RegimeTransitions,';
PRINT '        RegimeDwellStats, RegimeStability, DetectorCorrelation, CalibrationSummary, HealthHistogram,';
PRINT '        HealthZoneByPeriod, SensorAnomalyByPeriod, EpisodeMetrics, RegimeSummary, Scores_Wide';
GO

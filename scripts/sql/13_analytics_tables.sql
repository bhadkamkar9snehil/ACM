-- =============================================
-- ACM Analytics Tables (Phase 2 - All Output Tables)
-- =============================================
-- Comprehensive tables for all ACM analytics outputs
-- Designed for multi-instance concurrent runs
-- Each table has RunID + EquipID for filtering
-- =============================================

USE [ACM];
GO

-- 1. Health Timeline (time-series health index)
IF OBJECT_ID('dbo.ACM_HealthTimeline','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_HealthTimeline (
    RunID              uniqueidentifier NOT NULL,
    EquipID            int NOT NULL,
    Timestamp          datetime2(3) NOT NULL,
    FusedZ             float NULL,
    HealthIndex        float NULL,
    Zone               nvarchar(16) NULL,  -- GOOD, WATCH, ALERT
    CreatedAt          datetime2(3) NOT NULL CONSTRAINT DF_ACM_HealthTimeline_CreatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_ACM_HealthTimeline PRIMARY KEY CLUSTERED (RunID, Timestamp)
);
CREATE NONCLUSTERED INDEX IX_HealthTimeline_EquipID_Time ON dbo.ACM_HealthTimeline(EquipID, Timestamp DESC);
END
GO

-- 2. Regime Timeline
IF OBJECT_ID('dbo.ACM_RegimeTimeline','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_RegimeTimeline (
    RunID              uniqueidentifier NOT NULL,
    EquipID            int NOT NULL,
    Timestamp          datetime2(3) NOT NULL,
    RegimeLabel        int NULL,
    RegimeState        nvarchar(32) NULL,
    CreatedAt          datetime2(3) NOT NULL CONSTRAINT DF_ACM_RegimeTimeline_CreatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_ACM_RegimeTimeline PRIMARY KEY CLUSTERED (RunID, Timestamp)
);
CREATE NONCLUSTERED INDEX IX_RegimeTimeline_EquipID_Time ON dbo.ACM_RegimeTimeline(EquipID, Timestamp DESC);
END
GO

-- 3. Detector Correlation
IF OBJECT_ID('dbo.ACM_DetectorCorrelation','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_DetectorCorrelation (
    RunID              uniqueidentifier NOT NULL,
    EquipID            int NOT NULL,
    DetectorA          nvarchar(64) NOT NULL,
    DetectorB          nvarchar(64) NOT NULL,
    PearsonR           float NULL,
    CreatedAt          datetime2(3) NOT NULL CONSTRAINT DF_ACM_DetectorCorrelation_CreatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_ACM_DetectorCorrelation PRIMARY KEY CLUSTERED (RunID, DetectorA, DetectorB)
);
CREATE NONCLUSTERED INDEX IX_DetectorCorrelation_EquipID ON dbo.ACM_DetectorCorrelation(EquipID, RunID);
END
GO

-- 4. Calibration Summary
IF OBJECT_ID('dbo.ACM_CalibrationSummary','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_CalibrationSummary (
    RunID              uniqueidentifier NOT NULL,
    EquipID            int NOT NULL,
    Detector           nvarchar(64) NOT NULL,
    Mean               float NULL,
    Std                float NULL,
    P95                float NULL,
    P99                float NULL,
    ClipZ              float NULL,
    ClipPct            float NULL,
    CreatedAt          datetime2(3) NOT NULL CONSTRAINT DF_ACM_CalibrationSummary_CreatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_ACM_CalibrationSummary PRIMARY KEY CLUSTERED (RunID, Detector)
);
CREATE NONCLUSTERED INDEX IX_CalibrationSummary_EquipID ON dbo.ACM_CalibrationSummary(EquipID, RunID);
END
GO

-- 5. Regime Transition Matrix
IF OBJECT_ID('dbo.ACM_RegimeTransitions','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_RegimeTransitions (
    RunID              uniqueidentifier NOT NULL,
    EquipID            int NOT NULL,
    FromLabel          int NOT NULL,
    ToLabel            int NOT NULL,
    TransitionCount    int NULL,
    Probability        float NULL,
    CreatedAt          datetime2(3) NOT NULL CONSTRAINT DF_ACM_RegimeTransitions_CreatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_ACM_RegimeTransitions PRIMARY KEY CLUSTERED (RunID, FromLabel, ToLabel)
);
CREATE NONCLUSTERED INDEX IX_RegimeTransitions_EquipID ON dbo.ACM_RegimeTransitions(EquipID, RunID);
END
GO

-- 6. Regime Dwell Stats
IF OBJECT_ID('dbo.ACM_RegimeDwellStats','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_RegimeDwellStats (
    RunID              uniqueidentifier NOT NULL,
    EquipID            int NOT NULL,
    RegimeLabel        int NOT NULL,
    Runs               int NULL,
    MeanSeconds        float NULL,
    MedianSeconds      float NULL,
    MinSeconds         float NULL,
    MaxSeconds         float NULL,
    CreatedAt          datetime2(3) NOT NULL CONSTRAINT DF_ACM_RegimeDwellStats_CreatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_ACM_RegimeDwellStats PRIMARY KEY CLUSTERED (RunID, RegimeLabel)
);
CREATE NONCLUSTERED INDEX IX_RegimeDwellStats_EquipID ON dbo.ACM_RegimeDwellStats(EquipID, RunID);
END
GO

-- 7. Drift Events
IF OBJECT_ID('dbo.ACM_DriftEvents','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_DriftEvents (
    RunID              uniqueidentifier NOT NULL,
    EquipID            int NOT NULL,
    Timestamp          datetime2(3) NOT NULL,
    DriftValue         float NULL,
    SegmentStart       datetime2(3) NULL,
    SegmentEnd         datetime2(3) NULL,
    CreatedAt          datetime2(3) NOT NULL CONSTRAINT DF_ACM_DriftEvents_CreatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_ACM_DriftEvents PRIMARY KEY CLUSTERED (RunID, Timestamp)
);
CREATE NONCLUSTERED INDEX IX_DriftEvents_EquipID_Time ON dbo.ACM_DriftEvents(EquipID, Timestamp DESC);
END
GO

-- 8. Threshold Crossings
IF OBJECT_ID('dbo.ACM_ThresholdCrossings','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_ThresholdCrossings (
    RunID              uniqueidentifier NOT NULL,
    EquipID            int NOT NULL,
    Timestamp          datetime2(3) NOT NULL,
    Detector           nvarchar(64) NOT NULL,
    ZScore             float NULL,
    Threshold          float NULL,
    Direction          nvarchar(16) NULL,  -- UP, DOWN
    CreatedAt          datetime2(3) NOT NULL CONSTRAINT DF_ACM_ThresholdCrossings_CreatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_ACM_ThresholdCrossings PRIMARY KEY CLUSTERED (RunID, Timestamp, Detector)
);
CREATE NONCLUSTERED INDEX IX_ThresholdCrossings_EquipID_Time ON dbo.ACM_ThresholdCrossings(EquipID, Timestamp DESC);
END
GO

-- 9. Regime Occupancy
IF OBJECT_ID('dbo.ACM_RegimeOccupancy','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_RegimeOccupancy (
    RunID              uniqueidentifier NOT NULL,
    EquipID            int NOT NULL,
    RegimeLabel        int NOT NULL,
    RecordCount        int NULL,
    Percentage         float NULL,
    CreatedAt          datetime2(3) NOT NULL CONSTRAINT DF_ACM_RegimeOccupancy_CreatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_ACM_RegimeOccupancy PRIMARY KEY CLUSTERED (RunID, RegimeLabel)
);
CREATE NONCLUSTERED INDEX IX_RegimeOccupancy_EquipID ON dbo.ACM_RegimeOccupancy(EquipID, RunID);
END
GO

-- 10. Episode Metrics Summary (single row per run)
IF OBJECT_ID('dbo.ACM_EpisodeMetrics','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_EpisodeMetrics (
    RunID                    uniqueidentifier NOT NULL PRIMARY KEY,
    EquipID                  int NOT NULL,
    TotalEpisodes            int NULL,
    TotalDurationHours       float NULL,
    AvgDurationHours         float NULL,
    MedianDurationHours      float NULL,
    MaxDurationHours         float NULL,
    MinDurationHours         float NULL,
    RatePerDay               float NULL,
    MeanInterarrivalHours    float NULL,
    CreatedAt                datetime2(3) NOT NULL CONSTRAINT DF_ACM_EpisodeMetrics_CreatedAt DEFAULT (SYSUTCDATETIME())
);
CREATE NONCLUSTERED INDEX IX_EpisodeMetrics_EquipID ON dbo.ACM_EpisodeMetrics(EquipID, RunID);
END
GO

-- 11. Culprit History (detector frequency across episodes)
IF OBJECT_ID('dbo.ACM_CulpritHistory','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_CulpritHistory (
    RunID              uniqueidentifier NOT NULL,
    EquipID            int NOT NULL,
    Detector           nvarchar(128) NOT NULL,
    EpisodeCount       int NULL,
    TotalDurationHours float NULL,
    CreatedAt          datetime2(3) NOT NULL CONSTRAINT DF_ACM_CulpritHistory_CreatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_ACM_CulpritHistory PRIMARY KEY CLUSTERED (RunID, Detector)
);
CREATE NONCLUSTERED INDEX IX_CulpritHistory_EquipID ON dbo.ACM_CulpritHistory(EquipID, RunID);
END
GO

PRINT 'ACM Analytics tables created successfully';
GO

-- Verification
SELECT 
    t.name AS TableName,
    (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS ColumnCount
FROM sys.tables t
WHERE t.name LIKE 'ACM[_]%'
ORDER BY t.name;
GO

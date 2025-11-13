-- ==============================================================================
-- ACM Analytics Tables Schema
-- Created: 2024-11-13
-- Purpose: Dual-write analytics tables for ACM V8 SQL integration
-- ==============================================================================

USE ACM;
GO

-- ==============================================================================
-- Time-series analytics tables (primary monitoring views)
-- ==============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_HealthTimeline')
CREATE TABLE dbo.ACM_HealthTimeline (
    Timestamp DATETIME2 NOT NULL,
    HealthIndex FLOAT NOT NULL,
    HealthZone NVARCHAR(50) NOT NULL,
    FusedZ FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_HealthTimeline PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp),
    CONSTRAINT FK_ACM_HealthTimeline_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_RegimeTimeline')
CREATE TABLE dbo.ACM_RegimeTimeline (
    Timestamp DATETIME2 NOT NULL,
    RegimeLabel NVARCHAR(50) NOT NULL,
    RegimeState NVARCHAR(50) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_RegimeTimeline PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp),
    CONSTRAINT FK_ACM_RegimeTimeline_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_ContributionTimeline')
CREATE TABLE dbo.ACM_ContributionTimeline (
    Timestamp DATETIME2 NOT NULL,
    DetectorType NVARCHAR(50) NOT NULL,
    ContributionPct FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_ContributionTimeline PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp, DetectorType),
    CONSTRAINT FK_ACM_ContributionTimeline_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_DriftSeries')
CREATE TABLE dbo.ACM_DriftSeries (
    Timestamp DATETIME2 NOT NULL,
    DriftValue FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_DriftSeries PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp),
    CONSTRAINT FK_ACM_DriftSeries_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_DefectTimeline')
CREATE TABLE dbo.ACM_DefectTimeline (
    Timestamp DATETIME2 NOT NULL,
    EventType NVARCHAR(50) NOT NULL,
    FromZone NVARCHAR(50),
    ToZone NVARCHAR(50),
    HealthZone NVARCHAR(50) NOT NULL,
    HealthAtEvent FLOAT NOT NULL,
    HealthIndex FLOAT NOT NULL,
    FusedZ FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_DefectTimeline PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp),
    CONSTRAINT FK_ACM_DefectTimeline_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_SensorHotspotTimeline')
CREATE TABLE dbo.ACM_SensorHotspotTimeline (
    Timestamp DATETIME2 NOT NULL,
    SensorName NVARCHAR(255) NOT NULL,
    Rank INT NOT NULL,
    AbsZ FLOAT NOT NULL,
    SignedZ FLOAT NOT NULL,
    Value FLOAT NOT NULL,
    Level NVARCHAR(50) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_SensorHotspotTimeline PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp, SensorName),
    CONSTRAINT FK_ACM_SensorHotspotTimeline_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

-- ==============================================================================
-- Current state / snapshot tables (latest readings)
-- ==============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_ContributionCurrent')
CREATE TABLE dbo.ACM_ContributionCurrent (
    DetectorType NVARCHAR(50) NOT NULL,
    ContributionPct FLOAT NOT NULL,
    ZScore FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_ContributionCurrent PRIMARY KEY CLUSTERED (RunID, EquipID, DetectorType),
    CONSTRAINT FK_ACM_ContributionCurrent_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_SensorRanking')
CREATE TABLE dbo.ACM_SensorRanking (
    DetectorType NVARCHAR(50) NOT NULL,
    RankPosition INT NOT NULL,
    ContributionPct FLOAT NOT NULL,
    ZScore FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_SensorRanking PRIMARY KEY CLUSTERED (RunID, EquipID, RankPosition),
    CONSTRAINT FK_ACM_SensorRanking_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_SensorHotspots')
CREATE TABLE dbo.ACM_SensorHotspots (
    SensorName NVARCHAR(255) NOT NULL,
    MaxTimestamp DATETIME2 NOT NULL,
    LatestTimestamp DATETIME2 NOT NULL,
    MaxAbsZ FLOAT NOT NULL,
    MaxSignedZ FLOAT NOT NULL,
    LatestAbsZ FLOAT NOT NULL,
    LatestSignedZ FLOAT NOT NULL,
    ValueAtPeak FLOAT NOT NULL,
    LatestValue FLOAT NOT NULL,
    TrainMean FLOAT NOT NULL,
    TrainStd FLOAT NOT NULL,
    AboveWarnCount INT NOT NULL,
    AboveAlertCount INT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_SensorHotspots PRIMARY KEY CLUSTERED (RunID, EquipID, SensorName),
    CONSTRAINT FK_ACM_SensorHotspots_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_SinceWhen')
CREATE TABLE dbo.ACM_SinceWhen (
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    AlertZone NVARCHAR(50) NOT NULL,
    DurationHours FLOAT NOT NULL,
    StartTimestamp DATETIME2 NOT NULL,
    RecordCount INT NOT NULL,
    CONSTRAINT PK_ACM_SinceWhen PRIMARY KEY CLUSTERED (RunID, EquipID, AlertZone),
    CONSTRAINT FK_ACM_SinceWhen_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

-- ==============================================================================
-- Episode & alert tables (anomaly event tracking)
-- ==============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_Episodes')
CREATE TABLE dbo.ACM_Episodes (
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    EpisodeCount INT NOT NULL,
    MedianDurationMinutes FLOAT NOT NULL,
    CoveragePct FLOAT NOT NULL,
    TimeInAlertPct FLOAT NOT NULL,
    MaxFusedZ FLOAT NOT NULL,
    AvgFusedZ FLOAT NOT NULL,
    CONSTRAINT PK_ACM_Episodes PRIMARY KEY CLUSTERED (RunID, EquipID),
    CONSTRAINT FK_ACM_Episodes_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_EpisodeMetrics')
CREATE TABLE dbo.ACM_EpisodeMetrics (
    TotalEpisodes INT NOT NULL,
    TotalDurationHours FLOAT NOT NULL,
    AvgDurationHours FLOAT NOT NULL,
    MedianDurationHours FLOAT NOT NULL,
    MaxDurationHours FLOAT NOT NULL,
    MinDurationHours FLOAT NOT NULL,
    RatePerDay FLOAT NOT NULL,
    MeanInterarrivalHours FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_EpisodeMetrics PRIMARY KEY CLUSTERED (RunID, EquipID),
    CONSTRAINT FK_ACM_EpisodeMetrics_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_ThresholdCrossings')
CREATE TABLE dbo.ACM_ThresholdCrossings (
    Timestamp DATETIME2 NOT NULL,
    DetectorType NVARCHAR(50) NOT NULL,
    Threshold FLOAT NOT NULL,
    ZScore FLOAT NOT NULL,
    Direction NVARCHAR(10) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_ThresholdCrossings PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp, DetectorType),
    CONSTRAINT FK_ACM_ThresholdCrossings_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_AlertAge')
CREATE TABLE dbo.ACM_AlertAge (
    AlertZone NVARCHAR(50) NOT NULL,
    StartTimestamp DATETIME2 NOT NULL,
    DurationHours FLOAT NOT NULL,
    RecordCount INT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_AlertAge PRIMARY KEY CLUSTERED (RunID, EquipID, AlertZone),
    CONSTRAINT FK_ACM_AlertAge_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_CulpritHistory')
CREATE TABLE dbo.ACM_CulpritHistory (
    StartTimestamp DATETIME2 NOT NULL,
    EndTimestamp DATETIME2 NOT NULL,
    DurationHours FLOAT NOT NULL,
    PrimaryDetector NVARCHAR(50) NOT NULL,
    WeightedContribution FLOAT NOT NULL,
    LeadMeanZ FLOAT NOT NULL,
    DuringMeanZ FLOAT NOT NULL,
    LagMeanZ FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_CulpritHistory PRIMARY KEY CLUSTERED (RunID, EquipID, StartTimestamp),
    CONSTRAINT FK_ACM_CulpritHistory_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

-- ==============================================================================
-- Regime analysis tables (operating mode clustering)
-- ==============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_RegimeOccupancy')
CREATE TABLE dbo.ACM_RegimeOccupancy (
    RegimeLabel NVARCHAR(50) NOT NULL,
    RecordCount INT NOT NULL,
    Percentage FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_RegimeOccupancy PRIMARY KEY CLUSTERED (RunID, EquipID, RegimeLabel),
    CONSTRAINT FK_ACM_RegimeOccupancy_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_RegimeStability')
CREATE TABLE dbo.ACM_RegimeStability (
    MetricName NVARCHAR(100) NOT NULL,
    MetricValue FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_RegimeStability PRIMARY KEY CLUSTERED (RunID, EquipID, MetricName),
    CONSTRAINT FK_ACM_RegimeStability_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_RegimeTransitions')
CREATE TABLE dbo.ACM_RegimeTransitions (
    FromLabel NVARCHAR(50) NOT NULL,
    ToLabel NVARCHAR(50) NOT NULL,
    Count INT NOT NULL,
    Prob FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_RegimeTransitions PRIMARY KEY CLUSTERED (RunID, EquipID, FromLabel, ToLabel),
    CONSTRAINT FK_ACM_RegimeTransitions_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_RegimeDwellStats')
CREATE TABLE dbo.ACM_RegimeDwellStats (
    RegimeLabel NVARCHAR(50) NOT NULL,
    Runs INT NOT NULL,
    MeanSeconds FLOAT NOT NULL,
    MedianSeconds FLOAT NOT NULL,
    MinSeconds FLOAT NOT NULL,
    MaxSeconds FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_RegimeDwellStats PRIMARY KEY CLUSTERED (RunID, EquipID, RegimeLabel),
    CONSTRAINT FK_ACM_RegimeDwellStats_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

-- ==============================================================================
-- Defect & diagnostics tables
-- ==============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_DefectSummary')
CREATE TABLE dbo.ACM_DefectSummary (
    Status NVARCHAR(50) NOT NULL,
    Severity NVARCHAR(50) NOT NULL,
    CurrentHealth FLOAT NOT NULL,
    AvgHealth FLOAT NOT NULL,
    MinHealth FLOAT NOT NULL,
    EpisodeCount INT NOT NULL,
    WorstSensor NVARCHAR(255),
    GoodCount INT NOT NULL,
    WatchCount INT NOT NULL,
    AlertCount INT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_DefectSummary PRIMARY KEY CLUSTERED (RunID, EquipID),
    CONSTRAINT FK_ACM_DefectSummary_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_SensorDefects')
CREATE TABLE dbo.ACM_SensorDefects (
    DetectorType NVARCHAR(50) NOT NULL,
    DetectorFamily NVARCHAR(50) NOT NULL,
    Severity NVARCHAR(50) NOT NULL,
    ViolationCount INT NOT NULL,
    ViolationPct FLOAT NOT NULL,
    MaxZ FLOAT NOT NULL,
    AvgZ FLOAT NOT NULL,
    CurrentZ FLOAT NOT NULL,
    ActiveDefect NVARCHAR(10) NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_SensorDefects PRIMARY KEY CLUSTERED (RunID, EquipID, DetectorType),
    CONSTRAINT FK_ACM_SensorDefects_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

-- ==============================================================================
-- Drift analysis tables
-- ==============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_DriftEvents')
CREATE TABLE dbo.ACM_DriftEvents (
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_DriftEvents PRIMARY KEY CLUSTERED (RunID, EquipID),
    CONSTRAINT FK_ACM_DriftEvents_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

-- ==============================================================================
-- Calibration & detector diagnostics tables
-- ==============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_CalibrationSummary')
CREATE TABLE dbo.ACM_CalibrationSummary (
    DetectorType NVARCHAR(50) NOT NULL,
    MeanZ FLOAT NOT NULL,
    StdZ FLOAT NOT NULL,
    P95Z FLOAT NOT NULL,
    P99Z FLOAT NOT NULL,
    ClipZ FLOAT NOT NULL,
    SaturationPct FLOAT NOT NULL,
    MahalCondNum FLOAT,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_CalibrationSummary PRIMARY KEY CLUSTERED (RunID, EquipID, DetectorType),
    CONSTRAINT FK_ACM_CalibrationSummary_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_DetectorCorrelation')
CREATE TABLE dbo.ACM_DetectorCorrelation (
    DetectorA NVARCHAR(50) NOT NULL,
    DetectorB NVARCHAR(50) NOT NULL,
    PearsonR FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_DetectorCorrelation PRIMARY KEY CLUSTERED (RunID, EquipID, DetectorA, DetectorB),
    CONSTRAINT FK_ACM_DetectorCorrelation_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

-- ==============================================================================
-- Period-based aggregation tables (daily/weekly rollups)
-- ==============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_HealthZoneByPeriod')
CREATE TABLE dbo.ACM_HealthZoneByPeriod (
    PeriodStart DATETIME2 NOT NULL,
    PeriodType NVARCHAR(20) NOT NULL,
    HealthZone NVARCHAR(50) NOT NULL,
    ZonePct FLOAT NOT NULL,
    ZoneCount INT NOT NULL,
    TotalPoints INT NOT NULL,
    Date DATE NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_HealthZoneByPeriod PRIMARY KEY CLUSTERED (RunID, EquipID, PeriodStart, HealthZone),
    CONSTRAINT FK_ACM_HealthZoneByPeriod_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_SensorAnomalyByPeriod')
CREATE TABLE dbo.ACM_SensorAnomalyByPeriod (
    Date DATE NOT NULL,
    PeriodStart DATETIME2 NOT NULL,
    PeriodType NVARCHAR(20) NOT NULL,
    PeriodSeconds FLOAT NOT NULL,
    DetectorType NVARCHAR(50) NOT NULL,
    AnomalyRatePct FLOAT NOT NULL,
    MaxZ FLOAT NOT NULL,
    AvgZ FLOAT NOT NULL,
    Points INT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_SensorAnomalyByPeriod PRIMARY KEY CLUSTERED (RunID, EquipID, Date, DetectorType),
    CONSTRAINT FK_ACM_SensorAnomalyByPeriod_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

-- ==============================================================================
-- Histogram / distribution tables
-- ==============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_HealthHistogram')
CREATE TABLE dbo.ACM_HealthHistogram (
    HealthBin NVARCHAR(50) NOT NULL,
    RecordCount INT NOT NULL,
    Percentage FLOAT NOT NULL,
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CONSTRAINT PK_ACM_HealthHistogram PRIMARY KEY CLUSTERED (RunID, EquipID, HealthBin),
    CONSTRAINT FK_ACM_HealthHistogram_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

-- ==============================================================================
-- Data quality table (sensor validation metrics)
-- ==============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_DataQuality')
CREATE TABLE dbo.ACM_DataQuality (
    sensor NVARCHAR(255) NOT NULL,
    train_count INT,
    train_nulls INT,
    train_null_pct FLOAT,
    train_std FLOAT,
    train_longest_gap INT,
    train_flatline_span INT,
    train_min_ts DATETIME2,
    train_max_ts DATETIME2,
    score_count INT,
    score_nulls INT,
    score_null_pct FLOAT,
    score_std FLOAT,
    score_longest_gap INT,
    score_flatline_span INT,
    score_min_ts DATETIME2,
    score_max_ts DATETIME2,
    interp_method NVARCHAR(50),
    sampling_secs FLOAT,
    notes NVARCHAR(MAX),
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    CheckName NVARCHAR(100) NOT NULL,
    CheckResult NVARCHAR(50) NOT NULL,
    CONSTRAINT PK_ACM_DataQuality PRIMARY KEY CLUSTERED (RunID, EquipID, CheckName, sensor),
    CONSTRAINT FK_ACM_DataQuality_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

-- ==============================================================================
-- Verification query
-- ==============================================================================
PRINT 'Created ACM analytics tables:';
SELECT name 
FROM sys.tables 
WHERE name LIKE 'ACM_%' 
ORDER BY name;
GO

PRINT 'Schema creation complete.';
GO

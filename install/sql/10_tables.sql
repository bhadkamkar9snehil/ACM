USE [ACM];
GO

-- ACM_AdaptiveConfig
IF OBJECT_ID('dbo.[ACM_AdaptiveConfig]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_AdaptiveConfig] (
        [ConfigID] INT IDENTITY(1,1) NOT NULL,
        [EquipID] INT NULL,
        [ConfigKey] NVARCHAR(100) NOT NULL,
        [ConfigValue] FLOAT(53) NOT NULL,
        [MinBound] FLOAT(53) NOT NULL,
        [MaxBound] FLOAT(53) NOT NULL,
        [IsLearned] BIT NOT NULL CONSTRAINT [DF__ACM_Adapt__IsLea__7F4BDEC0] DEFAULT ((0)),
        [DataVolumeAtTuning] BIGINT NULL,
        [PerformanceMetric] FLOAT(53) NULL,
        [ResearchReference] NVARCHAR(500) NULL,
        [Source] NVARCHAR(50) NOT NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Adapt__Creat__004002F9] DEFAULT (getdate()),
        [UpdatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Adapt__Updat__01342732] DEFAULT (getdate()),
        CONSTRAINT [PK__ACM_Adap__C3BC333CD5B812F4] PRIMARY KEY CLUSTERED ([ConfigID])
    );
END
GO

-- ACM_AlertAge
IF OBJECT_ID('dbo.[ACM_AlertAge]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_AlertAge] (
        [AlertZone] NVARCHAR(50) NOT NULL,
        [StartTimestamp] DATETIME2(7) NOT NULL,
        [DurationHours] FLOAT(53) NOT NULL,
        [RecordCount] INT NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_Anomaly_Events
IF OBJECT_ID('dbo.[ACM_Anomaly_Events]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_Anomaly_Events] (
        [Id] BIGINT IDENTITY(1,1) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NULL,
        [EquipID] INT NULL,
        [StartTime] DATETIME2(3) NULL,
        [EndTime] DATETIME2(3) NULL,
        [Severity] NVARCHAR(32) NULL,
        CONSTRAINT [PK__ACM_Anom__3214EC07E3B7FFEC] PRIMARY KEY CLUSTERED ([Id])
    );
END
GO

-- ACM_BaselineBuffer
IF OBJECT_ID('dbo.[ACM_BaselineBuffer]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_BaselineBuffer] (
        [Id] INT IDENTITY(1,1) NOT NULL,
        [EquipID] INT NOT NULL,
        [Timestamp] DATETIME NOT NULL,
        [SensorName] NVARCHAR(128) NOT NULL,
        [SensorValue] FLOAT(53) NOT NULL,
        [DataQuality] NVARCHAR(64) NULL,
        [CreatedAt] DATETIME NOT NULL CONSTRAINT [DF_ACM_BaselineBuffer_CreatedAt] DEFAULT (getdate()),
        CONSTRAINT [PK__ACM_Base__3214EC07A71949B0] PRIMARY KEY CLUSTERED ([Id])
    );
END
GO

-- ACM_CalibrationSummary
IF OBJECT_ID('dbo.[ACM_CalibrationSummary]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_CalibrationSummary] (
        [DetectorType] NVARCHAR(50) NOT NULL,
        [MeanZ] FLOAT(53) NOT NULL,
        [StdZ] FLOAT(53) NOT NULL,
        [P95Z] FLOAT(53) NOT NULL,
        [P99Z] FLOAT(53) NOT NULL,
        [ClipZ] FLOAT(53) NOT NULL,
        [SaturationPct] FLOAT(53) NOT NULL,
        [MahalCondNum] FLOAT(53) NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_ColdstartState
IF OBJECT_ID('dbo.[ACM_ColdstartState]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_ColdstartState] (
        [EquipID] INT NOT NULL,
        [Stage] VARCHAR(20) NOT NULL CONSTRAINT [DF__ACM_Colds__Stage__73501C2F] DEFAULT ('score'),
        [Status] VARCHAR(20) NOT NULL,
        [AttemptCount] INT NOT NULL CONSTRAINT [DF__ACM_Colds__Attem__74444068] DEFAULT ((0)),
        [FirstAttemptAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Colds__First__753864A1] DEFAULT (getutcdate()),
        [LastAttemptAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Colds__LastA__762C88DA] DEFAULT (getutcdate()),
        [CompletedAt] DATETIME2(7) NULL,
        [AccumulatedRows] INT NOT NULL CONSTRAINT [DF__ACM_Colds__Accum__7720AD13] DEFAULT ((0)),
        [RequiredRows] INT NOT NULL CONSTRAINT [DF__ACM_Colds__Requi__7814D14C] DEFAULT ((500)),
        [DataStartTime] DATETIME2(7) NULL,
        [DataEndTime] DATETIME2(7) NULL,
        [TickMinutes] INT NOT NULL,
        [ColdstartSplitRatio] FLOAT(53) NOT NULL CONSTRAINT [DF__ACM_Colds__Colds__7908F585] DEFAULT ((0.6)),
        [LastError] NVARCHAR(2000) NULL,
        [ErrorCount] INT NOT NULL CONSTRAINT [DF__ACM_Colds__Error__79FD19BE] DEFAULT ((0)),
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Colds__Creat__7AF13DF7] DEFAULT (getutcdate()),
        [UpdatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Colds__Updat__7BE56230] DEFAULT (getutcdate()),
        CONSTRAINT [PK_ACM_ColdstartState] PRIMARY KEY CLUSTERED ([EquipID], [Stage])
    );
END
GO

-- ACM_Config
IF OBJECT_ID('dbo.[ACM_Config]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_Config] (
        [ConfigID] INT IDENTITY(1,1) NOT NULL,
        [EquipID] INT NOT NULL,
        [ParamPath] NVARCHAR(500) NOT NULL,
        [ParamValue] NVARCHAR(MAX) NOT NULL,
        [ValueType] VARCHAR(50) NOT NULL,
        [UpdatedAt] DATETIME2(3) NOT NULL CONSTRAINT [DF__ACM_Confi__Updat__17C286CF] DEFAULT (getutcdate()),
        [UpdatedBy] NVARCHAR(100) NULL CONSTRAINT [DF__ACM_Confi__Updat__18B6AB08] DEFAULT (suser_sname()),
        CONSTRAINT [PK_ACM_Config] PRIMARY KEY CLUSTERED ([ConfigID])
    );
END
GO

-- ACM_ConfigHistory
IF OBJECT_ID('dbo.[ACM_ConfigHistory]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_ConfigHistory] (
        [ID] BIGINT IDENTITY(1,1) NOT NULL,
        [Timestamp] DATETIME2(3) NOT NULL CONSTRAINT [DF_ACM_ConfigHistory_Timestamp] DEFAULT (sysutcdatetime()),
        [EquipID] INT NOT NULL,
        [ParameterPath] NVARCHAR(256) NOT NULL,
        [OldValue] NVARCHAR(MAX) NULL,
        [NewValue] NVARCHAR(MAX) NULL,
        [ChangedBy] NVARCHAR(64) NULL,
        [ChangeReason] NVARCHAR(256) NULL,
        [RunID] NVARCHAR(64) NULL,
        CONSTRAINT [PK__ACM_Conf__3214EC274D689A75] PRIMARY KEY CLUSTERED ([ID])
    );
END
GO

-- ACM_ContributionCurrent
IF OBJECT_ID('dbo.[ACM_ContributionCurrent]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_ContributionCurrent] (
        [DetectorType] NVARCHAR(50) NOT NULL,
        [ContributionPct] FLOAT(53) NOT NULL,
        [ZScore] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_ContributionTimeline
IF OBJECT_ID('dbo.[ACM_ContributionTimeline]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_ContributionTimeline] (
        [Timestamp] DATETIME2(7) NOT NULL,
        [DetectorType] NVARCHAR(50) NOT NULL,
        [ContributionPct] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_DailyFusedProfile
IF OBJECT_ID('dbo.[ACM_DailyFusedProfile]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_DailyFusedProfile] (
        [ID] BIGINT IDENTITY(1,1) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [ProfileDate] DATE NOT NULL,
        [AvgFusedScore] FLOAT(53) NULL,
        [MaxFusedScore] FLOAT(53) NULL,
        [MinFusedScore] FLOAT(53) NULL,
        [SampleCount] INT NULL,
        [CreatedAt] DATETIME2(3) NULL CONSTRAINT [DF__ACM_Daily__Creat__53A266AC] DEFAULT (getutcdate()),
        CONSTRAINT [PK__ACM_Dail__3214EC27702C73D2] PRIMARY KEY CLUSTERED ([ID])
    );
END
GO

-- ACM_DataQuality
IF OBJECT_ID('dbo.[ACM_DataQuality]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_DataQuality] (
        [sensor] NVARCHAR(255) NOT NULL,
        [train_count] INT NULL,
        [train_nulls] INT NULL,
        [train_null_pct] FLOAT(53) NULL,
        [train_std] FLOAT(53) NULL,
        [train_longest_gap] INT NULL,
        [train_flatline_span] INT NULL,
        [train_min_ts] DATETIME2(7) NULL,
        [train_max_ts] DATETIME2(7) NULL,
        [score_count] INT NULL,
        [score_nulls] INT NULL,
        [score_null_pct] FLOAT(53) NULL,
        [score_std] FLOAT(53) NULL,
        [score_longest_gap] INT NULL,
        [score_flatline_span] INT NULL,
        [score_min_ts] DATETIME2(7) NULL,
        [score_max_ts] DATETIME2(7) NULL,
        [interp_method] NVARCHAR(50) NULL,
        [sampling_secs] FLOAT(53) NULL,
        [notes] NVARCHAR(MAX) NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [CheckName] NVARCHAR(100) NOT NULL,
        [CheckResult] NVARCHAR(50) NOT NULL
    );
END
GO

-- ACM_DefectSummary
IF OBJECT_ID('dbo.[ACM_DefectSummary]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_DefectSummary] (
        [Status] NVARCHAR(50) NOT NULL,
        [Severity] NVARCHAR(50) NOT NULL,
        [CurrentHealth] FLOAT(53) NOT NULL,
        [AvgHealth] FLOAT(53) NOT NULL,
        [MinHealth] FLOAT(53) NOT NULL,
        [EpisodeCount] INT NOT NULL,
        [WorstSensor] NVARCHAR(255) NULL,
        [GoodCount] INT NOT NULL,
        [WatchCount] INT NOT NULL,
        [AlertCount] INT NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_DefectTimeline
IF OBJECT_ID('dbo.[ACM_DefectTimeline]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_DefectTimeline] (
        [Timestamp] DATETIME2(7) NOT NULL,
        [EventType] NVARCHAR(50) NOT NULL,
        [FromZone] NVARCHAR(50) NULL,
        [ToZone] NVARCHAR(50) NULL,
        [HealthZone] NVARCHAR(50) NOT NULL,
        [HealthAtEvent] FLOAT(53) NOT NULL,
        [HealthIndex] FLOAT(53) NOT NULL,
        [FusedZ] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_DetectorCorrelation
IF OBJECT_ID('dbo.[ACM_DetectorCorrelation]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_DetectorCorrelation] (
        [DetectorA] NVARCHAR(50) NOT NULL,
        [DetectorB] NVARCHAR(50) NOT NULL,
        [PearsonR] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [PairLabel] NVARCHAR(256) NULL,
        [DisturbanceHint] NVARCHAR(256) NULL
    );
END
GO

-- ACM_DetectorForecast_TS
IF OBJECT_ID('dbo.[ACM_DetectorForecast_TS]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_DetectorForecast_TS] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [DetectorName] NVARCHAR(100) NOT NULL,
        [Timestamp] DATETIME2(7) NOT NULL,
        [ForecastValue] FLOAT(53) NOT NULL,
        [CiLower] FLOAT(53) NULL,
        [CiUpper] FLOAT(53) NULL,
        [ForecastStd] FLOAT(53) NULL,
        [Method] NVARCHAR(50) NOT NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF_ACM_DetectorForecast_TS_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_DetectorForecast_TS] PRIMARY KEY CLUSTERED ([RunID], [EquipID], [DetectorName], [Timestamp])
    );
END
GO

-- ACM_DriftEvents
IF OBJECT_ID('dbo.[ACM_DriftEvents]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_DriftEvents] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_DriftSeries
IF OBJECT_ID('dbo.[ACM_DriftSeries]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_DriftSeries] (
        [Timestamp] DATETIME2(7) NOT NULL,
        [DriftValue] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_EnhancedFailureProbability_TS
IF OBJECT_ID('dbo.[ACM_EnhancedFailureProbability_TS]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_EnhancedFailureProbability_TS] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [Timestamp] DATETIME2(7) NOT NULL,
        [ForecastHorizon_Hours] FLOAT(53) NOT NULL,
        [ForecastHealth] FLOAT(53) NULL,
        [ForecastUncertainty] FLOAT(53) NULL,
        [FailureProbability] FLOAT(53) NOT NULL,
        [RiskLevel] NVARCHAR(50) NOT NULL,
        [Confidence] FLOAT(53) NULL,
        [Model] NVARCHAR(50) NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF_ACM_EnhancedFailureProbability_TS_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_EnhancedFailureProbability_TS] PRIMARY KEY CLUSTERED ([RunID], [EquipID], [Timestamp], [ForecastHorizon_Hours])
    );
END
GO

-- ACM_EnhancedMaintenanceRecommendation
IF OBJECT_ID('dbo.[ACM_EnhancedMaintenanceRecommendation]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_EnhancedMaintenanceRecommendation] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [UrgencyScore] FLOAT(53) NOT NULL,
        [MaintenanceRequired] BIT NOT NULL,
        [EarliestMaintenance] FLOAT(53) NULL,
        [PreferredWindowStart] FLOAT(53) NULL,
        [PreferredWindowEnd] FLOAT(53) NULL,
        [LatestSafeTime] FLOAT(53) NULL,
        [FailureProbAtLatest] FLOAT(53) NULL,
        [FailurePattern] NVARCHAR(200) NULL,
        [Confidence] FLOAT(53) NULL,
        [EstimatedDuration_Hours] FLOAT(53) NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF_ACM_EnhancedMaintenanceRecommendation_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_EnhancedMaintenanceRecommendation] PRIMARY KEY CLUSTERED ([RunID], [EquipID])
    );
END
GO

-- ACM_EpisodeCulprits
IF OBJECT_ID('dbo.[ACM_EpisodeCulprits]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_EpisodeCulprits] (
        [ID] BIGINT IDENTITY(1,1) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EpisodeID] INT NOT NULL,
        [DetectorType] NVARCHAR(64) NULL,
        [SensorName] NVARCHAR(200) NULL,
        [ContributionPct] FLOAT(53) NULL,
        [Rank] INT NULL,
        [CreatedAt] DATETIME2(3) NOT NULL CONSTRAINT [DF__ACM_Episo__Creat__408F9238] DEFAULT (getutcdate()),
        [EquipID] INT NOT NULL CONSTRAINT [DF__ACM_Episo__Equip__369C13AA] DEFAULT ((1)),
        CONSTRAINT [PK__ACM_Epis__3214EC27E4E059C2] PRIMARY KEY CLUSTERED ([ID])
    );
END
GO

-- ACM_EpisodeDiagnostics
IF OBJECT_ID('dbo.[ACM_EpisodeDiagnostics]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_EpisodeDiagnostics] (
        [ID] BIGINT IDENTITY(1,1) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [episode_id] INT NULL,
        [peak_z] FLOAT(53) NULL,
        [peak_timestamp] DATETIME2(3) NULL,
        [duration_h] FLOAT(53) NULL,
        [dominant_sensor] NVARCHAR(200) NULL,
        [severity] NVARCHAR(50) NULL,
        [severity_reason] NVARCHAR(500) NULL,
        [avg_z] FLOAT(53) NULL,
        [min_health_index] FLOAT(53) NULL,
        [CreatedAt] DATETIME2(3) NOT NULL CONSTRAINT [DF__ACM_Episo__Creat__436BFEE3] DEFAULT (getutcdate()),
        CONSTRAINT [PK__ACM_Epis__3214EC27A0D3AD94] PRIMARY KEY CLUSTERED ([ID])
    );
END
GO

-- ACM_EpisodeDiagnostics: add columns introduced in v11.15.0 if missing
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.ACM_EpisodeDiagnostics') AND name = 'StartTime')
    ALTER TABLE dbo.[ACM_EpisodeDiagnostics] ADD [StartTime] DATETIME2(3) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.ACM_EpisodeDiagnostics') AND name = 'EndTime')
    ALTER TABLE dbo.[ACM_EpisodeDiagnostics] ADD [EndTime] DATETIME2(3) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.ACM_EpisodeDiagnostics') AND name = 'Culprits')
    ALTER TABLE dbo.[ACM_EpisodeDiagnostics] ADD [Culprits] NVARCHAR(512) NULL;
GO

-- ACM_EpisodeMetrics
IF OBJECT_ID('dbo.[ACM_EpisodeMetrics]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_EpisodeMetrics] (
        [TotalEpisodes] INT NOT NULL,
        [TotalDurationHours] FLOAT(53) NOT NULL,
        [AvgDurationHours] FLOAT(53) NOT NULL,
        [MedianDurationHours] FLOAT(53) NOT NULL,
        [MaxDurationHours] FLOAT(53) NOT NULL,
        [MinDurationHours] FLOAT(53) NOT NULL,
        [RatePerDay] FLOAT(53) NOT NULL,
        [MeanInterarrivalHours] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_Episodes
IF OBJECT_ID('dbo.[ACM_Episodes]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_Episodes] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [EpisodeCount] INT NULL,
        [MedianDurationMinutes] FLOAT(53) NULL,
        [CoveragePct] FLOAT(53) NULL,
        [TimeInAlertPct] FLOAT(53) NULL,
        [MaxFusedZ] FLOAT(53) NULL,
        [AvgFusedZ] FLOAT(53) NULL
    );
END
GO

-- ACM_EpisodesQC
IF OBJECT_ID('dbo.[ACM_EpisodesQC]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_EpisodesQC] (
        [RecordID] INT IDENTITY(1,1) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [EpisodeCount] INT NULL,
        [MedianDurationMinutes] FLOAT(53) NULL,
        [CoveragePct] FLOAT(53) NULL,
        [TimeInAlertPct] FLOAT(53) NULL,
        [MaxFusedZ] FLOAT(53) NULL,
        [AvgFusedZ] FLOAT(53) NULL,
        [CreatedAt] DATETIME2(7) NULL CONSTRAINT [DF__ACM_Episo__Creat__2A6B46EF] DEFAULT (getdate()),
        CONSTRAINT [PK__ACM_Epis__FBDF78C9954CBFA8] PRIMARY KEY CLUSTERED ([RecordID])
    );
END
GO

-- ACM_FailureCausation
IF OBJECT_ID('dbo.[ACM_FailureCausation]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_FailureCausation] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [PredictedFailureTime] DATETIME2(7) NOT NULL,
        [FailurePattern] NVARCHAR(200) NULL,
        [Detector] NVARCHAR(100) NOT NULL,
        [MeanZ] FLOAT(53) NULL,
        [MaxZ] FLOAT(53) NULL,
        [SpikeCount] INT NULL,
        [TrendSlope] FLOAT(53) NULL,
        [ContributionWeight] FLOAT(53) NULL,
        [ContributionPct] FLOAT(53) NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF_ACM_FailureCausation_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_FailureCausation] PRIMARY KEY CLUSTERED ([RunID], [EquipID], [Detector])
    );
END
GO

-- ACM_FailureForecast
IF OBJECT_ID('dbo.[ACM_FailureForecast]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_FailureForecast] (
        [EquipID] INT NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [Timestamp] DATETIME2(7) NOT NULL,
        [FailureProb] FLOAT(53) NOT NULL,
        [SurvivalProb] FLOAT(53) NULL,
        [HazardRate] FLOAT(53) NULL,
        [ThresholdUsed] FLOAT(53) NOT NULL,
        [Method] NVARCHAR(50) NOT NULL CONSTRAINT [DF__ACM_Failu__Metho__72E607DB] DEFAULT ('GaussianCDF'),
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Failu__Creat__73DA2C14] DEFAULT (getdate()),
        CONSTRAINT [PK_ACM_FailureForecast] PRIMARY KEY CLUSTERED ([EquipID], [RunID], [Timestamp])
    );
END
GO

-- ACM_FailureForecast_TS
IF OBJECT_ID('dbo.[ACM_FailureForecast_TS]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_FailureForecast_TS] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [Timestamp] DATETIME2(7) NOT NULL,
        [FailureProb] FLOAT(53) NOT NULL,
        [ThresholdUsed] FLOAT(53) NOT NULL,
        [Method] NVARCHAR(50) NOT NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF_ACM_FailureForecast_TS_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_FailureForecast_TS] PRIMARY KEY CLUSTERED ([RunID], [EquipID], [Timestamp])
    );
END
GO

-- ACM_FailureHazard_TS
IF OBJECT_ID('dbo.[ACM_FailureHazard_TS]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_FailureHazard_TS] (
        [Timestamp] DATETIME2(7) NOT NULL,
        [HazardRaw] FLOAT(53) NULL,
        [HazardSmooth] FLOAT(53) NULL,
        [Survival] FLOAT(53) NULL,
        [FailureProb] FLOAT(53) NULL,
        [RunID] NVARCHAR(50) NOT NULL,
        [EquipID] INT NOT NULL,
        [CreatedAt] DATETIME2(7) NULL CONSTRAINT [DF__ACM_Failu__Creat__3C54ED00] DEFAULT (getdate()),
        CONSTRAINT [PK_FailureHazard_TS] PRIMARY KEY CLUSTERED ([EquipID], [RunID], [Timestamp])
    );
END
GO

-- ACM_FeatureDropLog
IF OBJECT_ID('dbo.[ACM_FeatureDropLog]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_FeatureDropLog] (
        [LogID] INT IDENTITY(1,1) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [FeatureName] NVARCHAR(500) NOT NULL,
        [Reason] NVARCHAR(200) NOT NULL,
        [TrainMedian] FLOAT(53) NULL,
        [TrainStd] FLOAT(53) NULL,
        [Timestamp] DATETIME NOT NULL CONSTRAINT [DF__ACM_Featu__Times__48EFCE0F] DEFAULT (getdate()),
        CONSTRAINT [PK__ACM_Feat__5E5499A8738AB582] PRIMARY KEY CLUSTERED ([LogID])
    );
END
GO

-- ACM_ForecastingState
IF OBJECT_ID('dbo.[ACM_ForecastingState]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_ForecastingState] (
        [EquipID] INT NOT NULL,
        [StateVersion] INT NOT NULL,
        [ModelCoefficientsJson] NVARCHAR(MAX) NULL,
        [LastForecastJson] NVARCHAR(MAX) NULL,
        [LastRetrainTime] DATETIME2(7) NULL,
        [TrainingDataHash] NVARCHAR(64) NULL,
        [DataVolumeAnalyzed] BIGINT NULL,
        [RecentMAE] FLOAT(53) NULL,
        [RecentRMSE] FLOAT(53) NULL,
        [RetriggerReason] NVARCHAR(200) NULL,
        [RowVersion] TIMESTAMP NOT NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Forec__Creat__7A8729A3] DEFAULT (getdate()),
        [UpdatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Forec__Updat__7B7B4DDC] DEFAULT (getdate()),
        CONSTRAINT [PK_ACM_ForecastingState] PRIMARY KEY CLUSTERED ([EquipID], [StateVersion])
    );
END
GO

-- ACM_ForecastState
IF OBJECT_ID('dbo.[ACM_ForecastState]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_ForecastState] (
        [EquipID] INT NOT NULL,
        [StateVersion] INT NOT NULL,
        [ModelType] NVARCHAR(50) NULL,
        [ModelParamsJson] NVARCHAR(MAX) NULL,
        [ResidualVariance] FLOAT(53) NULL,
        [LastForecastHorizonJson] NVARCHAR(MAX) NULL,
        [HazardBaseline] FLOAT(53) NULL,
        [LastRetrainTime] DATETIME2(7) NULL,
        [TrainingDataHash] NVARCHAR(64) NULL,
        [TrainingWindowHours] INT NULL,
        [ForecastQualityJson] NVARCHAR(MAX) NULL,
        [CreatedAt] DATETIME2(7) NULL CONSTRAINT [DF__ACM_Forec__Creat__61F08603] DEFAULT (getdate()),
        CONSTRAINT [PK_ForecastState] PRIMARY KEY CLUSTERED ([EquipID], [StateVersion])
    );
END
GO

-- ACM_FusionQualityReport
IF OBJECT_ID('dbo.[ACM_FusionQualityReport]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_FusionQualityReport] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [Detector] NVARCHAR(64) NOT NULL,
        [Weight] FLOAT(53) NOT NULL,
        [Present] BIT NOT NULL,
        [MeanZ] FLOAT(53) NULL,
        [MaxZ] FLOAT(53) NULL,
        [Points] INT NULL,
        [CreatedAt] DATETIME2(3) NOT NULL CONSTRAINT [DF_ACM_FusionQualityReport_CreatedAt] DEFAULT (sysutcdatetime())
    );
END
GO

-- ACM_HealthDistributionOverTime
IF OBJECT_ID('dbo.[ACM_HealthDistributionOverTime]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_HealthDistributionOverTime] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [BucketStart] DATETIME2(3) NOT NULL,
        [BucketSeconds] INT NOT NULL,
        [FusedP50] FLOAT(53) NULL,
        [FusedP75] FLOAT(53) NULL,
        [FusedP90] FLOAT(53) NULL,
        [FusedP95] FLOAT(53) NULL,
        [HealthP50] FLOAT(53) NULL,
        [HealthP10] FLOAT(53) NULL,
        [BucketCount] INT NULL,
        [CreatedAt] DATETIME2(3) NOT NULL CONSTRAINT [DF_ACM_HealthDistributionOverTime_CreatedAt] DEFAULT (sysutcdatetime())
    );
END
GO

-- ACM_HealthForecast
IF OBJECT_ID('dbo.[ACM_HealthForecast]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_HealthForecast] (
        [EquipID] INT NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [Timestamp] DATETIME2(7) NOT NULL,
        [ForecastHealth] FLOAT(53) NOT NULL,
        [CiLower] FLOAT(53) NULL,
        [CiUpper] FLOAT(53) NULL,
        [ForecastStd] FLOAT(53) NULL,
        [Method] NVARCHAR(50) NOT NULL CONSTRAINT [DF__ACM_Healt__Metho__6F1576F7] DEFAULT ('LinearTrend'),
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Healt__Creat__70099B30] DEFAULT (getdate()),
        CONSTRAINT [PK_ACM_HealthForecast] PRIMARY KEY CLUSTERED ([EquipID], [RunID], [Timestamp])
    );
END
GO

-- ACM_HealthForecast_Continuous
IF OBJECT_ID('dbo.[ACM_HealthForecast_Continuous]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_HealthForecast_Continuous] (
        [Timestamp] DATETIME2(7) NOT NULL,
        [ForecastHealth] FLOAT(53) NOT NULL,
        [CI_Lower] FLOAT(53) NULL,
        [CI_Upper] FLOAT(53) NULL,
        [SourceRunID] NVARCHAR(50) NOT NULL,
        [MergeWeight] FLOAT(53) NULL,
        [EquipID] INT NOT NULL,
        [CreatedAt] DATETIME2(7) NULL CONSTRAINT [DF__ACM_Healt__Creat__39788055] DEFAULT (getdate()),
        CONSTRAINT [PK_HealthForecast_Continuous] PRIMARY KEY CLUSTERED ([EquipID], [Timestamp], [SourceRunID])
    );
END
GO

-- ACM_HealthForecast_TS
IF OBJECT_ID('dbo.[ACM_HealthForecast_TS]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_HealthForecast_TS] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [Timestamp] DATETIME2(7) NOT NULL,
        [ForecastHealth] FLOAT(53) NULL,
        [CiLower] FLOAT(53) NULL,
        [CiUpper] FLOAT(53) NULL,
        [ForecastStd] FLOAT(53) NULL,
        [Method] NVARCHAR(50) NOT NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF_ACM_HealthForecast_TS_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_HealthForecast_TS] PRIMARY KEY CLUSTERED ([RunID], [EquipID], [Timestamp])
    );
END
GO

-- ACM_HealthHistogram
IF OBJECT_ID('dbo.[ACM_HealthHistogram]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_HealthHistogram] (
        [HealthBin] NVARCHAR(50) NOT NULL,
        [RecordCount] INT NOT NULL,
        [Percentage] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_HealthTimeline
IF OBJECT_ID('dbo.[ACM_HealthTimeline]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_HealthTimeline] (
        [Timestamp] DATETIME2(7) NOT NULL,
        [HealthIndex] FLOAT(53) NOT NULL,
        [HealthZone] NVARCHAR(50) NOT NULL,
        [FusedZ] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [RawHealthIndex] FLOAT(53) NULL,
        [QualityFlag] NVARCHAR(50) NULL
    );
END
GO

-- ACM_HealthZoneByPeriod
IF OBJECT_ID('dbo.[ACM_HealthZoneByPeriod]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_HealthZoneByPeriod] (
        [PeriodStart] DATETIME2(7) NOT NULL,
        [PeriodType] NVARCHAR(20) NOT NULL,
        [HealthZone] NVARCHAR(50) NOT NULL,
        [ZonePct] FLOAT(53) NOT NULL,
        [ZoneCount] INT NOT NULL,
        [TotalPoints] INT NOT NULL,
        [Date] DATE NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_HistorianData
IF OBJECT_ID('dbo.[ACM_HistorianData]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_HistorianData] (
        [DataID] BIGINT IDENTITY(1,1) NOT NULL,
        [EquipID] INT NOT NULL,
        [TagName] VARCHAR(255) NOT NULL,
        [Timestamp] DATETIME2(7) NOT NULL,
        [Value] FLOAT(53) NOT NULL,
        [Quality] TINYINT NULL CONSTRAINT [DF__ACM_Histo__Quali__442B18F2] DEFAULT ((192)),
        [CreatedAt] DATETIME2(7) NULL CONSTRAINT [DF__ACM_Histo__Creat__451F3D2B] DEFAULT (getutcdate()),
        CONSTRAINT [PK__ACM_Hist__9D05305D67C38C66] PRIMARY KEY CLUSTERED ([DataID])
    );
END
GO

-- ACM_MaintenanceRecommendation
IF OBJECT_ID('dbo.[ACM_MaintenanceRecommendation]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_MaintenanceRecommendation] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [EarliestMaintenance] DATETIME2(7) NOT NULL,
        [PreferredWindowStart] DATETIME2(7) NOT NULL,
        [PreferredWindowEnd] DATETIME2(7) NOT NULL,
        [FailureProbAtWindowEnd] FLOAT(53) NOT NULL,
        [Comment] NVARCHAR(400) NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF_ACM_MaintenanceRecommendation_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_MaintenanceRecommendation] PRIMARY KEY CLUSTERED ([RunID], [EquipID])
    );
END
GO

-- ACM_OMR_Diagnostics
IF OBJECT_ID('dbo.[ACM_OMR_Diagnostics]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_OMR_Diagnostics] (
        [DiagnosticID] INT IDENTITY(1,1) NOT NULL,
        [RunID] VARCHAR(100) NOT NULL,
        [EquipID] INT NOT NULL,
        [ModelType] VARCHAR(20) NOT NULL,
        [NComponents] INT NOT NULL,
        [TrainSamples] INT NOT NULL,
        [TrainFeatures] INT NOT NULL,
        [TrainResidualStd] FLOAT(53) NOT NULL,
        [TrainStartTime] DATETIME2(7) NULL,
        [TrainEndTime] DATETIME2(7) NULL,
        [CalibrationStatus] VARCHAR(20) NOT NULL,
        [SaturationRate] FLOAT(53) NULL,
        [FusionWeight] FLOAT(53) NULL,
        [FitTimestamp] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_OMR_D__FitTi__1A34DF26] DEFAULT (getdate()),
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_OMR_D__Creat__1B29035F] DEFAULT (getdate()),
        CONSTRAINT [PK__ACM_OMR___A3D00EA668EEBC11] PRIMARY KEY CLUSTERED ([DiagnosticID])
    );
END
GO

-- ACM_OMRContributionsLong
IF OBJECT_ID('dbo.[ACM_OMRContributionsLong]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_OMRContributionsLong] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [Timestamp] DATETIME2(3) NOT NULL,
        [SensorName] NVARCHAR(128) NOT NULL,
        [ContributionScore] FLOAT(53) NOT NULL,
        [ContributionPct] FLOAT(53) NOT NULL,
        [OMR_Z] FLOAT(53) NULL,
        [CreatedAt] DATETIME2(3) NOT NULL CONSTRAINT [DF_ACM_OMRContributionsLong_CreatedAt] DEFAULT (sysutcdatetime())
    );
END
GO

-- ACM_OMRTimeline
IF OBJECT_ID('dbo.[ACM_OMRTimeline]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_OMRTimeline] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [Timestamp] DATETIME2(3) NOT NULL,
        [OMR_Z] FLOAT(53) NULL,
        [OMR_Weight] FLOAT(53) NULL,
        [CreatedAt] DATETIME2(3) NOT NULL CONSTRAINT [DF_ACM_OMRTimeline_CreatedAt] DEFAULT (sysutcdatetime())
    );
END
GO

-- ACM_PCA_Loadings
IF OBJECT_ID('dbo.[ACM_PCA_Loadings]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_PCA_Loadings] (
        [RecordID] BIGINT IDENTITY(1,1) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [EntryDateTime] DATETIME2(7) NOT NULL,
        [ComponentNo] INT NOT NULL,
        [ComponentID] INT NULL,
        [Sensor] NVARCHAR(200) NOT NULL,
        [FeatureName] NVARCHAR(200) NULL,
        [Loading] FLOAT(53) NOT NULL,
        [CreatedAt] DATETIME2(7) NULL CONSTRAINT [DF__ACM_PCA_L__Creat__3C89F72A] DEFAULT (getdate()),
        CONSTRAINT [PK__ACM_PCA___FBDF78C96066D639] PRIMARY KEY CLUSTERED ([RecordID])
    );
END
GO

-- ACM_PCA_Metrics
IF OBJECT_ID('dbo.[ACM_PCA_Metrics]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_PCA_Metrics] (
        [RunID] NVARCHAR(72) NOT NULL,
        [EquipID] INT NOT NULL,
        [ComponentName] NVARCHAR(200) NOT NULL,
        [MetricType] NVARCHAR(50) NOT NULL,
        [Value] FLOAT(53) NOT NULL,
        [Timestamp] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_PCA_M__Times__3335971A] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_PCA_Metrics] PRIMARY KEY CLUSTERED ([RunID], [EquipID], [ComponentName], [MetricType])
    );
END
GO

-- ACM_PCA_Models
IF OBJECT_ID('dbo.[ACM_PCA_Models]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_PCA_Models] (
        [RecordID] BIGINT IDENTITY(1,1) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [EntryDateTime] DATETIME2(7) NOT NULL,
        [NComponents] INT NULL,
        [TargetVar] NVARCHAR(MAX) NULL,
        [VarExplainedJSON] NVARCHAR(MAX) NULL,
        [ScalingSpecJSON] NVARCHAR(MAX) NULL,
        [ModelVersion] NVARCHAR(50) NULL,
        [TrainStartEntryDateTime] DATETIME2(7) NULL,
        [TrainEndEntryDateTime] DATETIME2(7) NULL,
        [CreatedAt] DATETIME2(7) NULL CONSTRAINT [DF__ACM_PCA_M__Creat__38B96646] DEFAULT (getdate()),
        CONSTRAINT [PK__ACM_PCA___FBDF78C9397B4528] PRIMARY KEY CLUSTERED ([RecordID])
    );
END
GO

-- ACM_RecommendedActions
IF OBJECT_ID('dbo.[ACM_RecommendedActions]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RecommendedActions] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [Action] NVARCHAR(400) NOT NULL,
        [Priority] NVARCHAR(50) NULL,
        [EstimatedDuration_Hours] FLOAT(53) NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF_ACM_RecommendedActions_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_RecommendedActions] PRIMARY KEY CLUSTERED ([RunID], [EquipID], [Action])
    );
END
GO

-- ACM_RefitRequests
IF OBJECT_ID('dbo.[ACM_RefitRequests]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RefitRequests] (
        [RequestID] INT IDENTITY(1,1) NOT NULL,
        [EquipID] INT NOT NULL,
        [RequestedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Refit__Reque__147C05D0] DEFAULT (sysutcdatetime()),
        [Reason] NVARCHAR(MAX) NULL,
        [AnomalyRate] FLOAT(53) NULL,
        [DriftScore] FLOAT(53) NULL,
        [ModelAgeHours] FLOAT(53) NULL,
        [RegimeQuality] FLOAT(53) NULL,
        [Acknowledged] BIT NOT NULL CONSTRAINT [DF__ACM_Refit__Ackno__15702A09] DEFAULT ((0)),
        [AcknowledgedAt] DATETIME2(7) NULL,
        CONSTRAINT [PK__ACM_Refi__33A8519A1E14D4CB] PRIMARY KEY CLUSTERED ([RequestID])
    );
END
GO

-- ACM_Regime_Episodes
IF OBJECT_ID('dbo.[ACM_Regime_Episodes]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_Regime_Episodes] (
        [Id] BIGINT IDENTITY(1,1) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NULL,
        [EquipID] INT NULL,
        [StartTime] DATETIME2(3) NULL,
        [EndTime] DATETIME2(3) NULL,
        [RegimeID] INT NULL,
        CONSTRAINT [PK__ACM_Regi__3214EC07A8E38C5C] PRIMARY KEY CLUSTERED ([Id])
    );
END
GO

-- ACM_RegimeDwellStats
IF OBJECT_ID('dbo.[ACM_RegimeDwellStats]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RegimeDwellStats] (
        [RegimeLabel] NVARCHAR(50) NOT NULL,
        [Runs] INT NOT NULL,
        [MeanSeconds] FLOAT(53) NOT NULL,
        [MedianSeconds] FLOAT(53) NOT NULL,
        [MinSeconds] FLOAT(53) NOT NULL,
        [MaxSeconds] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_RegimeOccupancy
IF OBJECT_ID('dbo.[ACM_RegimeOccupancy]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RegimeOccupancy] (
        [RegimeLabel] NVARCHAR(50) NOT NULL,
        [RecordCount] INT NOT NULL,
        [Percentage] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_RegimeStability
IF OBJECT_ID('dbo.[ACM_RegimeStability]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RegimeStability] (
        [MetricName] NVARCHAR(100) NOT NULL,
        [MetricValue] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_RegimeState
IF OBJECT_ID('dbo.[ACM_RegimeState]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RegimeState] (
        [EquipID] INT NOT NULL,
        [StateVersion] INT NOT NULL,
        [NumClusters] INT NOT NULL,
        [ClusterCentersJson] NVARCHAR(MAX) NULL,
        [ScalerMeanJson] NVARCHAR(MAX) NULL,
        [ScalerScaleJson] NVARCHAR(MAX) NULL,
        [PCAComponentsJson] NVARCHAR(MAX) NULL,
        [PCAExplainedVarianceJson] NVARCHAR(MAX) NULL,
        [NumPCAComponents] INT NOT NULL CONSTRAINT [DF__ACM_Regim__NumPC__22CA2527] DEFAULT ((0)),
        [SilhouetteScore] FLOAT(53) NULL,
        [QualityOk] BIT NOT NULL CONSTRAINT [DF__ACM_Regim__Quali__23BE4960] DEFAULT ((0)),
        [LastTrainedTime] DATETIME2(3) NOT NULL,
        [ConfigHash] NVARCHAR(64) NULL,
        [RegimeBasisHash] NVARCHAR(64) NULL,
        [CreatedAt] DATETIME2(3) NOT NULL CONSTRAINT [DF_ACM_RegimeState_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_RegimeState] PRIMARY KEY CLUSTERED ([EquipID], [StateVersion])
    );
END
GO

-- ACM_RegimeStats
IF OBJECT_ID('dbo.[ACM_RegimeStats]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RegimeStats] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [RegimeLabel] INT NOT NULL,
        [OccupancyPct] FLOAT(53) NULL,
        [AvgDwellSeconds] FLOAT(53) NULL,
        [FusedMean] FLOAT(53) NULL,
        [FusedP90] FLOAT(53) NULL,
        [CreatedAt] DATETIME2(3) NOT NULL CONSTRAINT [DF_ACM_RegimeStats_CreatedAt] DEFAULT (sysutcdatetime())
    );
END
GO

-- ACM_RegimeTimeline
IF OBJECT_ID('dbo.[ACM_RegimeTimeline]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RegimeTimeline] (
        [Timestamp] DATETIME2(7) NOT NULL,
        [RegimeLabel] NVARCHAR(50) NOT NULL,
        [RegimeState] NVARCHAR(50) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_RegimeTransitions
IF OBJECT_ID('dbo.[ACM_RegimeTransitions]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RegimeTransitions] (
        [FromLabel] NVARCHAR(50) NOT NULL,
        [ToLabel] NVARCHAR(50) NOT NULL,
        [Count] INT NOT NULL,
        [Prob] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_RUL
IF OBJECT_ID('dbo.[ACM_RUL]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RUL] (
        [EquipID] INT NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [RUL_Hours] FLOAT(53) NOT NULL,
        [P10_LowerBound] FLOAT(53) NULL,
        [P50_Median] FLOAT(53) NULL,
        [P90_UpperBound] FLOAT(53) NULL,
        [Confidence] FLOAT(53) NULL,
        [FailureTime] DATETIME2(7) NULL,
        [Method] NVARCHAR(50) NOT NULL CONSTRAINT [DF__ACM_RUL__Method__76B698BF] DEFAULT ('MonteCarlo'),
        [NumSimulations] INT NULL,
        [TopSensor1] NVARCHAR(255) NULL,
        [TopSensor2] NVARCHAR(255) NULL,
        [TopSensor3] NVARCHAR(255) NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_RUL__Created__77AABCF8] DEFAULT (getdate()),
        CONSTRAINT [PK_ACM_RUL] PRIMARY KEY CLUSTERED ([EquipID], [RunID])
    );
END
GO

-- ACM_RUL_Attribution
IF OBJECT_ID('dbo.[ACM_RUL_Attribution]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RUL_Attribution] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [FailureTime] DATETIME2(7) NOT NULL,
        [SensorName] NVARCHAR(255) NOT NULL,
        [FailureContribution] FLOAT(53) NOT NULL,
        [ZScoreAtFailure] FLOAT(53) NULL,
        [AlertCount] INT NULL,
        [Comment] NVARCHAR(400) NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF_ACM_RUL_Attribution_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_RUL_Attribution] PRIMARY KEY CLUSTERED ([RunID], [EquipID], [FailureTime], [SensorName])
    );
END
GO

-- ACM_RUL_LearningState
IF OBJECT_ID('dbo.[ACM_RUL_LearningState]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RUL_LearningState] (
        [EquipID] INT NOT NULL,
        [AR1_MAE] FLOAT(53) NULL,
        [AR1_RMSE] FLOAT(53) NULL,
        [AR1_Bias] FLOAT(53) NULL,
        [AR1_RecentErrors] NVARCHAR(MAX) NULL,
        [AR1_Weight] FLOAT(53) NULL,
        [Exp_MAE] FLOAT(53) NULL,
        [Exp_RMSE] FLOAT(53) NULL,
        [Exp_Bias] FLOAT(53) NULL,
        [Exp_RecentErrors] NVARCHAR(MAX) NULL,
        [Exp_Weight] FLOAT(53) NULL,
        [Weibull_MAE] FLOAT(53) NULL,
        [Weibull_RMSE] FLOAT(53) NULL,
        [Weibull_Bias] FLOAT(53) NULL,
        [Weibull_RecentErrors] NVARCHAR(MAX) NULL,
        [Weibull_Weight] FLOAT(53) NULL,
        [CalibrationFactor] FLOAT(53) NULL,
        [LastUpdated] DATETIME2(7) NULL,
        [PredictionHistory] NVARCHAR(MAX) NULL,
        CONSTRAINT [PK__ACM_RUL___50D22319D320EC60] PRIMARY KEY CLUSTERED ([EquipID])
    );
END
GO

-- ACM_RUL_Summary
IF OBJECT_ID('dbo.[ACM_RUL_Summary]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RUL_Summary] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [RUL_Hours] FLOAT(53) NOT NULL,
        [LowerBound] FLOAT(53) NULL,
        [UpperBound] FLOAT(53) NULL,
        [Confidence] FLOAT(53) NULL,
        [Method] NVARCHAR(50) NOT NULL,
        [LastUpdate] DATETIME2(7) NOT NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF_ACM_RUL_Summary_CreatedAt] DEFAULT (sysutcdatetime()),
        [RUL_Trajectory_Hours] FLOAT(53) NULL,
        [RUL_Hazard_Hours] FLOAT(53) NULL,
        [RUL_Energy_Hours] FLOAT(53) NULL,
        [RUL_Final_Hours] FLOAT(53) NULL,
        [ConfidenceBand_Hours] FLOAT(53) NULL,
        [DominantPath] NVARCHAR(20) NULL,
        CONSTRAINT [PK_ACM_RUL_Summary] PRIMARY KEY CLUSTERED ([RunID], [EquipID])
    );
END
GO

-- ACM_RUL_TS
IF OBJECT_ID('dbo.[ACM_RUL_TS]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RUL_TS] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [Timestamp] DATETIME2(7) NOT NULL,
        [RUL_Hours] FLOAT(53) NOT NULL,
        [LowerBound] FLOAT(53) NULL,
        [UpperBound] FLOAT(53) NULL,
        [Confidence] FLOAT(53) NULL,
        [Method] NVARCHAR(50) NOT NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF_ACM_RUL_TS_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_RUL_TS] PRIMARY KEY CLUSTERED ([RunID], [EquipID], [Timestamp])
    );
END
GO

-- ACM_Run_Stats
IF OBJECT_ID('dbo.[ACM_Run_Stats]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_Run_Stats] (
        [RecordID] BIGINT IDENTITY(1,1) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [WindowStartEntryDateTime] DATETIME2(7) NULL,
        [WindowEndEntryDateTime] DATETIME2(7) NULL,
        [SamplesIn] INT NULL,
        [SamplesKept] INT NULL,
        [SensorsKept] INT NULL,
        [CadenceOKPct] FLOAT(53) NULL,
        [DriftP95] FLOAT(53) NULL,
        [ReconRMSE] FLOAT(53) NULL,
        [AnomalyCount] INT NULL,
        [CreatedAt] DATETIME2(7) NULL CONSTRAINT [DF__ACM_Run_S__Creat__405A880E] DEFAULT (getdate()),
        CONSTRAINT [PK__ACM_Run___FBDF78C95B685BB7] PRIMARY KEY CLUSTERED ([RecordID])
    );
END
GO

-- ACM_RunLogs
IF OBJECT_ID('dbo.[ACM_RunLogs]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RunLogs] (
        [LogID] BIGINT IDENTITY(1,1) NOT NULL,
        [RunID] NVARCHAR(64) NULL,
        [EquipID] INT NULL,
        [LoggedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_RunLo__Logge__7073AF84] DEFAULT (sysutcdatetime()),
        [Level] NVARCHAR(16) NOT NULL,
        [Module] NVARCHAR(128) NULL,
        [Message] NVARCHAR(4000) NOT NULL,
        [Context] NVARCHAR(MAX) NULL,
        [LoggedLocal] DATETIMEOFFSET(7) NULL,
        [LoggedLocalNaive] DATETIME2(7) NULL,
        [EventType] NVARCHAR(32) NULL,
        [Stage] NVARCHAR(64) NULL,
        [StepName] NVARCHAR(128) NULL,
        [DurationMs] FLOAT(53) NULL,
        [RowCount] INT NULL,
        [ColCount] INT NULL,
        [WindowSize] INT NULL,
        [BatchStart] DATETIME2(7) NULL,
        [BatchEnd] DATETIME2(7) NULL,
        [BaselineStart] DATETIME2(7) NULL,
        [BaselineEnd] DATETIME2(7) NULL,
        [DataQualityMetric] NVARCHAR(64) NULL,
        [DataQualityValue] FLOAT(53) NULL,
        [LeakageFlag] BIT NULL,
        [ParamsJson] NVARCHAR(MAX) NULL,
        CONSTRAINT [PK__ACM_RunL__5E5499A85A5E5F02] PRIMARY KEY CLUSTERED ([LogID])
    );
END
GO

-- ACM_RunMetadata
IF OBJECT_ID('dbo.[ACM_RunMetadata]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RunMetadata] (
        [RunMetadataID] INT IDENTITY(1,1) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [EquipName] NVARCHAR(128) NOT NULL,
        [CreatedAt] DATETIME2(0) NOT NULL CONSTRAINT [DF__ACM_RunMe__Creat__740F363E] DEFAULT (sysutcdatetime()),
        [RetrainDecision] BIT NOT NULL,
        [RetrainReason] NVARCHAR(256) NULL,
        [ForecastStateVersion] INT NULL,
        [ModelAgeBatches] INT NULL,
        [ForecastRMSE] FLOAT(53) NULL,
        [ForecastMAE] FLOAT(53) NULL,
        [ForecastMAPE] FLOAT(53) NULL,
        CONSTRAINT [PK__ACM_RunM__C5B9C2D43D309239] PRIMARY KEY CLUSTERED ([RunMetadataID])
    );
END
GO

-- ACM_RunMetrics
IF OBJECT_ID('dbo.[ACM_RunMetrics]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RunMetrics] (
        [RunID] NVARCHAR(72) NOT NULL,
        [EquipID] INT NOT NULL,
        [MetricName] NVARCHAR(100) NOT NULL,
        [MetricValue] FLOAT(53) NOT NULL,
        [Timestamp] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_RunMe__Times__5A1A5A11] DEFAULT (getdate()),
        CONSTRAINT [PK_ACM_RunMetrics] PRIMARY KEY CLUSTERED ([RunID], [EquipID], [MetricName])
    );
END
GO

-- ACM_Runs
IF OBJECT_ID('dbo.[ACM_Runs]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_Runs] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [EquipName] NVARCHAR(200) NULL,
        [StartedAt] DATETIME2(7) NOT NULL,
        [CompletedAt] DATETIME2(7) NULL,
        [DurationSeconds] INT NULL,
        [ConfigSignature] VARCHAR(64) NULL,
        [TrainRowCount] INT NULL,
        [ScoreRowCount] INT NULL,
        [EpisodeCount] INT NULL,
        [HealthStatus] VARCHAR(50) NULL,
        [AvgHealthIndex] FLOAT(53) NULL,
        [MinHealthIndex] FLOAT(53) NULL,
        [MaxFusedZ] FLOAT(53) NULL,
        [DataQualityScore] FLOAT(53) NULL,
        [RefitRequested] BIT NULL CONSTRAINT [DF__ACM_Runs__RefitR__5C37ACAD] DEFAULT ((0)),
        [ErrorMessage] NVARCHAR(1000) NULL,
        [KeptColumns] NVARCHAR(MAX) NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Runs__Create__5D2BD0E6] DEFAULT (getutcdate()),
        CONSTRAINT [PK_ACM_Runs] PRIMARY KEY CLUSTERED ([RunID])
    );
END
GO

-- ACM_SchemaVersion
IF OBJECT_ID('dbo.[ACM_SchemaVersion]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_SchemaVersion] (
        [VersionID] INT IDENTITY(1,1) NOT NULL,
        [VersionNumber] VARCHAR(20) NOT NULL,
        [Description] VARCHAR(500) NULL,
        [AppliedAt] DATETIME2(3) NOT NULL CONSTRAINT [DF__ACM_Schem__Appli__6497E884] DEFAULT (getutcdate()),
        [AppliedBy] VARCHAR(100) NOT NULL CONSTRAINT [DF__ACM_Schem__Appli__658C0CBD] DEFAULT (suser_sname()),
        CONSTRAINT [PK__ACM_Sche__16C6402FF0C41685] PRIMARY KEY CLUSTERED ([VersionID])
    );
END
GO

-- ACM_Scores_Long
IF OBJECT_ID('dbo.[ACM_Scores_Long]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_Scores_Long] (
        [Id] BIGINT IDENTITY(1,1) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NULL,
        [EquipID] INT NULL,
        [Timestamp] DATETIME2(3) NULL,
        [SensorName] NVARCHAR(128) NULL,
        [DetectorName] NVARCHAR(64) NULL,
        [Score] FLOAT(53) NULL,
        [Threshold] FLOAT(53) NULL,
        [IsAnomaly] BIT NULL,
        CONSTRAINT [PK__ACM_Scor__3214EC074D103B22] PRIMARY KEY CLUSTERED ([Id])
    );
END
GO

-- ACM_Scores_Wide
IF OBJECT_ID('dbo.[ACM_Scores_Wide]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_Scores_Wide] (
        [Timestamp] DATETIME2(7) NOT NULL,
        [ar1_z] FLOAT(53) NULL,
        [pca_spe_z] FLOAT(53) NULL,
        [pca_t2_z] FLOAT(53) NULL,
        [mhal_z] FLOAT(53) NULL,
        [iforest_z] FLOAT(53) NULL,
        [gmm_z] FLOAT(53) NULL,
        [cusum_z] FLOAT(53) NULL,
        [drift_z] FLOAT(53) NULL,
        [hst_z] FLOAT(53) NULL,
        [river_hst_z] FLOAT(53) NULL,
        [fused] FLOAT(53) NULL,
        [regime_label] NVARCHAR(50) NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_SensorAnomalyByPeriod
IF OBJECT_ID('dbo.[ACM_SensorAnomalyByPeriod]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_SensorAnomalyByPeriod] (
        [Date] DATE NOT NULL,
        [PeriodStart] DATETIME2(7) NOT NULL,
        [PeriodType] NVARCHAR(20) NOT NULL,
        [PeriodSeconds] FLOAT(53) NOT NULL,
        [DetectorType] NVARCHAR(50) NOT NULL,
        [AnomalyRatePct] FLOAT(53) NOT NULL,
        [MaxZ] FLOAT(53) NOT NULL,
        [AvgZ] FLOAT(53) NOT NULL,
        [Points] INT NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_SensorDefects
IF OBJECT_ID('dbo.[ACM_SensorDefects]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_SensorDefects] (
        [DetectorType] NVARCHAR(50) NOT NULL,
        [DetectorFamily] NVARCHAR(50) NOT NULL,
        [Severity] NVARCHAR(50) NOT NULL,
        [ViolationCount] INT NOT NULL,
        [ViolationPct] FLOAT(53) NOT NULL,
        [MaxZ] FLOAT(53) NOT NULL,
        [AvgZ] FLOAT(53) NOT NULL,
        [CurrentZ] FLOAT(53) NOT NULL,
        [ActiveDefect] NVARCHAR(10) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_SensorForecast
IF OBJECT_ID('dbo.[ACM_SensorForecast]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_SensorForecast] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [Timestamp] DATETIME2(7) NOT NULL,
        [SensorName] NVARCHAR(255) NOT NULL,
        [ForecastValue] FLOAT(53) NOT NULL,
        [CiLower] FLOAT(53) NULL,
        [CiUpper] FLOAT(53) NULL,
        [ForecastStd] FLOAT(53) NULL,
        [Method] NVARCHAR(50) NOT NULL,
        [RegimeLabel] INT NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF__ACM_Senso__Creat__0E8E2250] DEFAULT (getdate()),
        CONSTRAINT [PK_ACM_SensorForecast] PRIMARY KEY CLUSTERED ([RunID], [EquipID], [Timestamp], [SensorName])
    );
END
GO

-- ACM_SensorForecast_TS
IF OBJECT_ID('dbo.[ACM_SensorForecast_TS]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_SensorForecast_TS] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [SensorName] NVARCHAR(255) NOT NULL,
        [Timestamp] DATETIME2(7) NOT NULL,
        [ForecastValue] FLOAT(53) NOT NULL,
        [CiLower] FLOAT(53) NULL,
        [CiUpper] FLOAT(53) NULL,
        [ForecastStd] FLOAT(53) NULL,
        [Method] NVARCHAR(50) NOT NULL,
        [CreatedAt] DATETIME2(7) NOT NULL CONSTRAINT [DF_ACM_SensorForecast_TS_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_ACM_SensorForecast_TS] PRIMARY KEY CLUSTERED ([RunID], [EquipID], [SensorName], [Timestamp])
    );
END
GO

-- ACM_SensorHotspots
IF OBJECT_ID('dbo.[ACM_SensorHotspots]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_SensorHotspots] (
        [SensorName] NVARCHAR(255) NOT NULL,
        [MaxTimestamp] DATETIME2(7) NOT NULL,
        [LatestTimestamp] DATETIME2(7) NOT NULL,
        [MaxAbsZ] FLOAT(53) NOT NULL,
        [MaxSignedZ] FLOAT(53) NOT NULL,
        [LatestAbsZ] FLOAT(53) NOT NULL,
        [LatestSignedZ] FLOAT(53) NOT NULL,
        [ValueAtPeak] FLOAT(53) NOT NULL,
        [LatestValue] FLOAT(53) NOT NULL,
        [TrainMean] FLOAT(53) NOT NULL,
        [TrainStd] FLOAT(53) NOT NULL,
        [AboveWarnCount] INT NOT NULL,
        [AboveAlertCount] INT NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [FailureContribution] FLOAT(53) NULL,
        [ZScoreAtFailure] FLOAT(53) NULL,
        [AlertCount] INT NULL
    );
END
GO

-- ACM_SensorHotspots: add columns introduced in v11.15.0 if missing
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.ACM_SensorHotspots') AND name = 'MaxAbsOMR')
    ALTER TABLE dbo.[ACM_SensorHotspots] ADD [MaxAbsOMR] FLOAT(53) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.ACM_SensorHotspots') AND name = 'RankingScore')
    ALTER TABLE dbo.[ACM_SensorHotspots] ADD [RankingScore] FLOAT(53) NULL;
GO

-- ACM_SensorHotspotTimeline
IF OBJECT_ID('dbo.[ACM_SensorHotspotTimeline]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_SensorHotspotTimeline] (
        [Timestamp] DATETIME2(7) NOT NULL,
        [SensorName] NVARCHAR(255) NOT NULL,
        [Rank] INT NOT NULL,
        [AbsZ] FLOAT(53) NOT NULL,
        [SignedZ] FLOAT(53) NOT NULL,
        [Value] FLOAT(53) NOT NULL,
        [Level] NVARCHAR(50) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_SensorNormalized_TS
IF OBJECT_ID('dbo.[ACM_SensorNormalized_TS]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_SensorNormalized_TS] (
        [Id] BIGINT IDENTITY(1,1) NOT NULL,
        [EquipID] INT NOT NULL,
        [Timestamp] DATETIME NOT NULL,
        [SensorName] NVARCHAR(128) NOT NULL,
        [NormValue] FLOAT(53) NULL,
        [ZScore] FLOAT(53) NULL,
        [AnomalyLevel] NVARCHAR(16) NULL,
        [EpisodeActive] BIT NULL,
        [RunID] VARCHAR(64) NULL,
        [CreatedAt] DATETIME NOT NULL CONSTRAINT [DF_ACM_SensorNormalized_TS_CreatedAt] DEFAULT (getdate()),
        CONSTRAINT [PK_ACM_SensorNormalized_TS] PRIMARY KEY CLUSTERED ([Id])
    );
END
GO

-- ACM_SensorRanking
IF OBJECT_ID('dbo.[ACM_SensorRanking]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_SensorRanking] (
        [DetectorType] NVARCHAR(50) NOT NULL,
        [RankPosition] INT NOT NULL,
        [ContributionPct] FLOAT(53) NOT NULL,
        [ZScore] FLOAT(53) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_SinceWhen
IF OBJECT_ID('dbo.[ACM_SinceWhen]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_SinceWhen] (
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [AlertZone] NVARCHAR(50) NOT NULL,
        [DurationHours] FLOAT(53) NOT NULL,
        [StartTimestamp] DATETIME2(7) NOT NULL,
        [RecordCount] INT NOT NULL
    );
END
GO

-- ACM_TagEquipmentMap
IF OBJECT_ID('dbo.[ACM_TagEquipmentMap]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_TagEquipmentMap] (
        [TagID] INT IDENTITY(1,1) NOT NULL,
        [TagName] VARCHAR(255) NOT NULL,
        [EquipmentName] VARCHAR(50) NOT NULL,
        [EquipID] INT NOT NULL,
        [TagDescription] VARCHAR(500) NULL,
        [TagUnit] VARCHAR(50) NULL,
        [TagType] VARCHAR(50) NULL,
        [IsActive] BIT NULL CONSTRAINT [DF__ACM_TagEq__IsAct__2334397B] DEFAULT ((1)),
        [CreatedAt] DATETIME2(7) NULL CONSTRAINT [DF__ACM_TagEq__Creat__24285DB4] DEFAULT (getutcdate()),
        [UpdatedAt] DATETIME2(7) NULL CONSTRAINT [DF__ACM_TagEq__Updat__251C81ED] DEFAULT (getutcdate()),
        CONSTRAINT [PK_ACM_TagEquipmentMap] PRIMARY KEY CLUSTERED ([TagID])
    );
END
GO

-- ACM_ThresholdCrossings
IF OBJECT_ID('dbo.[ACM_ThresholdCrossings]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_ThresholdCrossings] (
        [Timestamp] DATETIME2(7) NOT NULL,
        [DetectorType] NVARCHAR(50) NOT NULL,
        [Threshold] FLOAT(53) NOT NULL,
        [ZScore] FLOAT(53) NOT NULL,
        [Direction] NVARCHAR(10) NOT NULL,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL
    );
END
GO

-- ACM_ThresholdMetadata
IF OBJECT_ID('dbo.[ACM_ThresholdMetadata]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_ThresholdMetadata] (
        [ThresholdID] INT IDENTITY(1,1) NOT NULL,
        [EquipID] INT NOT NULL,
        [RegimeID] INT NULL,
        [ThresholdType] VARCHAR(50) NOT NULL,
        [ThresholdValue] FLOAT(53) NOT NULL,
        [CalculationMethod] VARCHAR(100) NOT NULL,
        [SampleCount] INT NULL,
        [TrainStartTime] DATETIME2(3) NULL,
        [TrainEndTime] DATETIME2(3) NULL,
        [CreatedAt] DATETIME2(3) NULL CONSTRAINT [DF__ACM_Thres__Creat__0EC32C7A] DEFAULT (getdate()),
        [ConfigSignature] VARCHAR(32) NULL,
        [IsActive] BIT NULL CONSTRAINT [DF__ACM_Thres__IsAct__0FB750B3] DEFAULT ((1)),
        [Notes] VARCHAR(500) NULL,
        CONSTRAINT [PK__ACM_Thre__8E87A6309EA40F2C] PRIMARY KEY CLUSTERED ([ThresholdID])
    );
END
GO

-- Equipment
IF OBJECT_ID('dbo.[Equipment]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[Equipment] (
        [EquipID] INT IDENTITY(1,1) NOT NULL,
        [EquipCode] NVARCHAR(100) NOT NULL,
        [EquipName] NVARCHAR(200) NULL,
        [Area] NVARCHAR(100) NULL,
        [Unit] NVARCHAR(100) NULL,
        [Status] TINYINT NULL,
        [CommissionDate] DATETIME2(3) NULL,
        [CreatedAtUTC] DATETIME2(3) NOT NULL CONSTRAINT [DF_Equipment_CreatedAt] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK__Equipmen__50D22319037F1521] PRIMARY KEY CLUSTERED ([EquipID])
    );
END
GO

-- FD_FAN_Data
IF OBJECT_ID('dbo.[FD_FAN_Data]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[FD_FAN_Data] (
        [EntryDateTime] DATETIME2(0) NOT NULL,
        [DEMO.SIM.06G31_1FD Fan Damper Position] FLOAT(53) NULL,
        [DEMO.SIM.06I03_1FD Fan Motor Current] FLOAT(53) NULL,
        [DEMO.SIM.06GP34_1FD Fan Outlet Pressure] FLOAT(53) NULL,
        [DEMO.SIM.06T31_1FD Fan Inlet Temperature] FLOAT(53) NULL,
        [DEMO.SIM.06T32-1_1FD Fan Bearing Temperature] FLOAT(53) NULL,
        [DEMO.SIM.06T33-1_1FD Fan Winding Temperature] FLOAT(53) NULL,
        [DEMO.SIM.06T34_1FD Fan Outlet Termperature] FLOAT(53) NULL,
        [DEMO.SIM.FSAA_1FD Fan Left Inlet Flow] FLOAT(53) NULL,
        [DEMO.SIM.FSAB_1FD Fan Right Inlet Flow] FLOAT(53) NULL,
        [LoadedAt] DATETIME2(7) NULL CONSTRAINT [DF__FD_FAN_Da__Loade__2F9A1060] DEFAULT (getutcdate()),
        CONSTRAINT [PK_FD_FAN_Data] PRIMARY KEY CLUSTERED ([EntryDateTime])
    );
END
GO

-- GAS_TURBINE_Data
IF OBJECT_ID('dbo.[GAS_TURBINE_Data]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[GAS_TURBINE_Data] (
        [EntryDateTime] DATETIME2(0) NOT NULL,
        [DWATT] FLOAT(53) NULL,
        [B1VIB1] FLOAT(53) NULL,
        [B1VIB2] FLOAT(53) NULL,
        [B1RADVIBX] FLOAT(53) NULL,
        [B1RADVIBY] FLOAT(53) NULL,
        [B2VIB1] FLOAT(53) NULL,
        [B2VIB2] FLOAT(53) NULL,
        [B2RADVIBX] FLOAT(53) NULL,
        [B2RADVIBY] FLOAT(53) NULL,
        [TURBAXDISP1] FLOAT(53) NULL,
        [TURBAXDISP2] FLOAT(53) NULL,
        [B1TEMP1] FLOAT(53) NULL,
        [B2TEMP1] FLOAT(53) NULL,
        [ACTTBTEMP1] FLOAT(53) NULL,
        [INACTTBTEMP1] FLOAT(53) NULL,
        [LOTEMP1] FLOAT(53) NULL,
        [LoadedAt] DATETIME2(7) NULL CONSTRAINT [DF__GAS_TURBI__Loade__32767D0B] DEFAULT (getutcdate()),
        CONSTRAINT [PK_GAS_TURBINE_Data] PRIMARY KEY CLUSTERED ([EntryDateTime])
    );
END
GO

-- ModelRegistry
IF OBJECT_ID('dbo.[ModelRegistry]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ModelRegistry] (
        [ModelType] VARCHAR(32) NOT NULL,
        [EquipID] INT NOT NULL,
        [Version] INT NOT NULL,
        [EntryDateTime] DATETIME2(3) NOT NULL CONSTRAINT [DF_ModelRegistry_Entry] DEFAULT (sysutcdatetime()),
        [ParamsJSON] NVARCHAR(MAX) NULL,
        [StatsJSON] NVARCHAR(MAX) NULL,
        [RunID] UNIQUEIDENTIFIER NULL,
        [ModelBytes] VARBINARY(MAX) NULL,
        CONSTRAINT [PK_ModelRegistry] PRIMARY KEY CLUSTERED ([ModelType], [EquipID], [Version])
    );
END
GO
-- ============================================================================
-- v11.0.0 NEW TABLES
-- ============================================================================

-- ACM_ActiveModels - Single source of truth for active model versions
IF OBJECT_ID('dbo.[ACM_ActiveModels]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_ActiveModels] (
        [EquipID] INT NOT NULL PRIMARY KEY,
        [ActiveRegimeVersion] INT NULL,
        [RegimeMaturityState] NVARCHAR(20) DEFAULT 'INITIALIZING',
        [RegimePromotedAt] DATETIME2(7) NULL,
        [ActiveThresholdVersion] INT NULL,
        [ThresholdPromotedAt] DATETIME2(7) NULL,
        [ActiveForecastVersion] INT NULL,
        [ForecastPromotedAt] DATETIME2(7) NULL,
        [LastUpdatedAt] DATETIME2(7) DEFAULT GETDATE(),
        [LastUpdatedBy] NVARCHAR(100) NULL
    );
END
GO

-- ACM_RegimeDefinitions - Persisted regime centroids and metadata
IF OBJECT_ID('dbo.[ACM_RegimeDefinitions]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_RegimeDefinitions] (
        [EquipID] INT NOT NULL,
        [RegimeVersion] INT NOT NULL,
        [RegimeID] INT NOT NULL,
        [RegimeName] NVARCHAR(50) NOT NULL,
        [CentroidJSON] NVARCHAR(MAX) NOT NULL,
        [FeatureColumns] NVARCHAR(MAX) NOT NULL,
        [DataPointCount] INT NOT NULL,
        [SilhouetteScore] FLOAT NULL,
        [CreatedAt] DATETIME2(7) DEFAULT GETDATE(),
        [RunID] UNIQUEIDENTIFIER NULL,
        CONSTRAINT [PK_RegimeDefinitions] PRIMARY KEY CLUSTERED ([EquipID], [RegimeVersion], [RegimeID])
    );
END
GO

-- ACM_DataContractValidation - Contract validation history
IF OBJECT_ID('dbo.[ACM_DataContractValidation]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_DataContractValidation] (
        [ID] BIGINT IDENTITY(1,1) PRIMARY KEY,
        [RunID] UNIQUEIDENTIFIER NOT NULL,
        [EquipID] INT NOT NULL,
        [Passed] BIT NOT NULL,
        [RowsValidated] INT NOT NULL,
        [ColumnsValidated] INT NOT NULL,
        [IssuesJSON] NVARCHAR(MAX) NULL,
        [WarningsJSON] NVARCHAR(MAX) NULL,
        [ContractSignature] NVARCHAR(20) NULL,
        [ValidatedAt] DATETIME2(7) DEFAULT GETDATE()
    );
END
GO

-- ACM_SeasonalPatterns - Detected seasonal patterns
IF OBJECT_ID('dbo.[ACM_SeasonalPatterns]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_SeasonalPatterns] (
        [ID] BIGINT IDENTITY(1,1) PRIMARY KEY,
        [EquipID] INT NOT NULL,
        [SensorName] NVARCHAR(100) NOT NULL,
        [PatternType] NVARCHAR(20) NOT NULL,
        [PeriodHours] FLOAT NOT NULL,
        [Amplitude] FLOAT NOT NULL,
        [PhaseShift] FLOAT NOT NULL,
        [Confidence] FLOAT NOT NULL,
        [DetectedAt] DATETIME2(7) DEFAULT GETDATE(),
        [RunID] UNIQUEIDENTIFIER NULL
    );
END
GO

-- ACM_AssetProfiles - Asset similarity profiles for cold-start transfer
IF OBJECT_ID('dbo.[ACM_AssetProfiles]','U') IS NULL
BEGIN
    CREATE TABLE dbo.[ACM_AssetProfiles] (
        [EquipID] INT NOT NULL PRIMARY KEY,
        [EquipType] NVARCHAR(50) NOT NULL,
        [SensorNamesJSON] NVARCHAR(MAX) NOT NULL,
        [SensorMeansJSON] NVARCHAR(MAX) NOT NULL,
        [SensorStdsJSON] NVARCHAR(MAX) NOT NULL,
        [RegimeCount] INT NOT NULL,
        [TypicalHealth] FLOAT NOT NULL,
        [DataHours] FLOAT NOT NULL,
        [LastUpdatedAt] DATETIME2(7) DEFAULT GETDATE(),
        [RunID] UNIQUEIDENTIFIER NULL
    );
END
GO
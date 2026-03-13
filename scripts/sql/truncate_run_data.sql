-- =============================================================================
-- Truncate All Run-Generated ACM Tables
-- =============================================================================
-- Purpose: Clear all run-generated data while preserving static configuration
--
-- PRESERVED Tables (NOT truncated):
--   - ACM_Config               : Equipment configuration parameters
--   - ACM_AdaptiveConfig       : Adaptive configuration overrides
--   - ACM_TagEquipmentMap      : Tag to equipment mapping (static)
--   - ACM_ColdstartState       : Batch processing state (optional - reset if starting fresh)
--   - ACM_SchemaVersion        : Schema version tracking
--   - Equipment                : Equipment master data (not ACM_ prefixed)
--   - *_Data tables            : Historian data (source data)
--
-- TRUNCATED Tables (run-generated):
--   - All time series tables (Scores, Health, Regime timelines)
--   - All analytics tables (Episodes, Forecasts, RUL)
--   - All run metadata (Runs, RunTimers, RunLogs, etc.)
--
-- Usage:
--   sqlcmd -S "server\instance" -d ACM -E -i truncate_run_data.sql
-- =============================================================================

SET QUOTED_IDENTIFIER ON;
SET NOCOUNT ON;
PRINT '=== Truncating Run-Generated ACM Tables ===';
PRINT 'Started at: ' + CONVERT(VARCHAR(30), GETDATE(), 120);
PRINT '';

-- Must disable FK constraints before truncating
PRINT 'Disabling foreign key constraints...';

DECLARE @sql NVARCHAR(MAX) = '';

-- Generate NOCHECK statements for all FK constraints on ACM tables
SELECT @sql = @sql + 'ALTER TABLE ' + QUOTENAME(OBJECT_NAME(parent_object_id)) + 
              ' NOCHECK CONSTRAINT ' + QUOTENAME(name) + ';' + CHAR(13)
FROM sys.foreign_keys
WHERE OBJECT_NAME(parent_object_id) LIKE 'ACM_%';

EXEC sp_executesql @sql;
PRINT '  Done.';
PRINT '';

-- =============================================================================
-- Tables to PRESERVE (do NOT truncate)
-- =============================================================================
-- ACM_Config, ACM_AdaptiveConfig, ACM_TagEquipmentMap, ACM_SchemaVersion, ACM_ColdstartState

-- =============================================================================
-- Truncate run-generated tables in dependency order (children first, then parents)
-- =============================================================================

PRINT 'Truncating run-generated tables...';
PRINT '';

-- Child tables first (have FK references)
PRINT '  Episode-related tables...';
IF OBJECT_ID('dbo.ACM_EpisodeCulprits', 'U') IS NOT NULL TRUNCATE TABLE ACM_EpisodeCulprits;
IF OBJECT_ID('dbo.ACM_EpisodeDiagnostics', 'U') IS NOT NULL TRUNCATE TABLE ACM_EpisodeDiagnostics;
IF OBJECT_ID('dbo.ACM_Regime_Episodes', 'U') IS NOT NULL TRUNCATE TABLE ACM_Regime_Episodes;
IF OBJECT_ID('dbo.ACM_EpisodeMetrics', 'U') IS NOT NULL TRUNCATE TABLE ACM_EpisodeMetrics;
IF OBJECT_ID('dbo.ACM_EpisodesQC', 'U') IS NOT NULL TRUNCATE TABLE ACM_EpisodesQC;
IF OBJECT_ID('dbo.ACM_Episodes', 'U') IS NOT NULL TRUNCATE TABLE ACM_Episodes;

PRINT '  Time series tables...';
IF OBJECT_ID('dbo.ACM_Scores_Wide', 'U') IS NOT NULL TRUNCATE TABLE ACM_Scores_Wide;
IF OBJECT_ID('dbo.ACM_Scores_Long', 'U') IS NOT NULL TRUNCATE TABLE ACM_Scores_Long;
IF OBJECT_ID('dbo.ACM_HealthTimeline', 'U') IS NOT NULL TRUNCATE TABLE ACM_HealthTimeline;
IF OBJECT_ID('dbo.ACM_RegimeTimeline', 'U') IS NOT NULL TRUNCATE TABLE ACM_RegimeTimeline;
IF OBJECT_ID('dbo.ACM_SensorNormalized_TS', 'U') IS NOT NULL TRUNCATE TABLE ACM_SensorNormalized_TS;
IF OBJECT_ID('dbo.ACM_OMRTimeline', 'U') IS NOT NULL TRUNCATE TABLE ACM_OMRTimeline;
IF OBJECT_ID('dbo.ACM_ContributionTimeline', 'U') IS NOT NULL TRUNCATE TABLE ACM_ContributionTimeline;
IF OBJECT_ID('dbo.ACM_DefectTimeline', 'U') IS NOT NULL TRUNCATE TABLE ACM_DefectTimeline;
IF OBJECT_ID('dbo.ACM_SensorHotspotTimeline', 'U') IS NOT NULL TRUNCATE TABLE ACM_SensorHotspotTimeline;
IF OBJECT_ID('dbo.ACM_DriftSeries', 'U') IS NOT NULL TRUNCATE TABLE ACM_DriftSeries;

PRINT '  Forecast tables...';
IF OBJECT_ID('dbo.ACM_HealthForecast', 'U') IS NOT NULL TRUNCATE TABLE ACM_HealthForecast;
IF OBJECT_ID('dbo.ACM_HealthForecast_TS', 'U') IS NOT NULL TRUNCATE TABLE ACM_HealthForecast_TS;
IF OBJECT_ID('dbo.ACM_HealthForecast_Continuous', 'U') IS NOT NULL TRUNCATE TABLE ACM_HealthForecast_Continuous;
IF OBJECT_ID('dbo.ACM_FailureForecast', 'U') IS NOT NULL TRUNCATE TABLE ACM_FailureForecast;
IF OBJECT_ID('dbo.ACM_FailureForecast_TS', 'U') IS NOT NULL TRUNCATE TABLE ACM_FailureForecast_TS;
IF OBJECT_ID('dbo.ACM_FailureHazard_TS', 'U') IS NOT NULL TRUNCATE TABLE ACM_FailureHazard_TS;
IF OBJECT_ID('dbo.ACM_SensorForecast', 'U') IS NOT NULL TRUNCATE TABLE ACM_SensorForecast;
IF OBJECT_ID('dbo.ACM_SensorForecast_TS', 'U') IS NOT NULL TRUNCATE TABLE ACM_SensorForecast_TS;
IF OBJECT_ID('dbo.ACM_DetectorForecast_TS', 'U') IS NOT NULL TRUNCATE TABLE ACM_DetectorForecast_TS;
IF OBJECT_ID('dbo.ACM_EnhancedFailureProbability_TS', 'U') IS NOT NULL TRUNCATE TABLE ACM_EnhancedFailureProbability_TS;

PRINT '  RUL tables...';
IF OBJECT_ID('dbo.ACM_RUL', 'U') IS NOT NULL TRUNCATE TABLE ACM_RUL;
IF OBJECT_ID('dbo.ACM_RUL_TS', 'U') IS NOT NULL TRUNCATE TABLE ACM_RUL_TS;
IF OBJECT_ID('dbo.ACM_RUL_Attribution', 'U') IS NOT NULL TRUNCATE TABLE ACM_RUL_Attribution;
IF OBJECT_ID('dbo.ACM_RUL_Summary', 'U') IS NOT NULL TRUNCATE TABLE ACM_RUL_Summary;
IF OBJECT_ID('dbo.ACM_RUL_LearningState', 'U') IS NOT NULL TRUNCATE TABLE ACM_RUL_LearningState;
IF OBJECT_ID('dbo.ACM_FailureCausation', 'U') IS NOT NULL TRUNCATE TABLE ACM_FailureCausation;

PRINT '  Analytics tables...';
IF OBJECT_ID('dbo.ACM_Anomaly_Events', 'U') IS NOT NULL TRUNCATE TABLE ACM_Anomaly_Events;
IF OBJECT_ID('dbo.ACM_SensorDefects', 'U') IS NOT NULL TRUNCATE TABLE ACM_SensorDefects;
IF OBJECT_ID('dbo.ACM_SensorHotspots', 'U') IS NOT NULL TRUNCATE TABLE ACM_SensorHotspots;
IF OBJECT_ID('dbo.ACM_SensorCorrelations', 'U') IS NOT NULL TRUNCATE TABLE ACM_SensorCorrelations;
IF OBJECT_ID('dbo.ACM_SensorRanking', 'U') IS NOT NULL TRUNCATE TABLE ACM_SensorRanking;
IF OBJECT_ID('dbo.ACM_SensorAnomalyByPeriod', 'U') IS NOT NULL TRUNCATE TABLE ACM_SensorAnomalyByPeriod;
IF OBJECT_ID('dbo.ACM_DetectorCorrelation', 'U') IS NOT NULL TRUNCATE TABLE ACM_DetectorCorrelation;
IF OBJECT_ID('dbo.ACM_SeasonalPatterns', 'U') IS NOT NULL TRUNCATE TABLE ACM_SeasonalPatterns;
IF OBJECT_ID('dbo.ACM_ThresholdCrossings', 'U') IS NOT NULL TRUNCATE TABLE ACM_ThresholdCrossings;
IF OBJECT_ID('dbo.ACM_ThresholdMetadata', 'U') IS NOT NULL TRUNCATE TABLE ACM_ThresholdMetadata;

PRINT '  Regime tables...';
IF OBJECT_ID('dbo.ACM_RegimeDefinitions', 'U') IS NOT NULL TRUNCATE TABLE ACM_RegimeDefinitions;
IF OBJECT_ID('dbo.ACM_RegimeStats', 'U') IS NOT NULL TRUNCATE TABLE ACM_RegimeStats;
IF OBJECT_ID('dbo.ACM_RegimeStability', 'U') IS NOT NULL TRUNCATE TABLE ACM_RegimeStability;
IF OBJECT_ID('dbo.ACM_RegimeOccupancy', 'U') IS NOT NULL TRUNCATE TABLE ACM_RegimeOccupancy;
IF OBJECT_ID('dbo.ACM_RegimeTransitions', 'U') IS NOT NULL TRUNCATE TABLE ACM_RegimeTransitions;
IF OBJECT_ID('dbo.ACM_RegimeDwellStats', 'U') IS NOT NULL TRUNCATE TABLE ACM_RegimeDwellStats;
IF OBJECT_ID('dbo.ACM_RegimePromotionLog', 'U') IS NOT NULL TRUNCATE TABLE ACM_RegimePromotionLog;
IF OBJECT_ID('dbo.ACM_RegimeState', 'U') IS NOT NULL TRUNCATE TABLE ACM_RegimeState;

PRINT '  Health & drift tables...';
IF OBJECT_ID('dbo.ACM_HealthHistogram', 'U') IS NOT NULL TRUNCATE TABLE ACM_HealthHistogram;
IF OBJECT_ID('dbo.ACM_HealthDistributionOverTime', 'U') IS NOT NULL TRUNCATE TABLE ACM_HealthDistributionOverTime;
IF OBJECT_ID('dbo.ACM_HealthZoneByPeriod', 'U') IS NOT NULL TRUNCATE TABLE ACM_HealthZoneByPeriod;
IF OBJECT_ID('dbo.ACM_DriftController', 'U') IS NOT NULL TRUNCATE TABLE ACM_DriftController;
IF OBJECT_ID('dbo.ACM_DriftEvents', 'U') IS NOT NULL TRUNCATE TABLE ACM_DriftEvents;

PRINT '  Model & calibration tables...';
IF OBJECT_ID('dbo.ACM_PCA_Loadings', 'U') IS NOT NULL TRUNCATE TABLE ACM_PCA_Loadings;
IF OBJECT_ID('dbo.ACM_PCA_Metrics', 'U') IS NOT NULL TRUNCATE TABLE ACM_PCA_Metrics;
IF OBJECT_ID('dbo.ACM_PCA_Models', 'U') IS NOT NULL TRUNCATE TABLE ACM_PCA_Models;
IF OBJECT_ID('dbo.ACM_CalibrationSummary', 'U') IS NOT NULL TRUNCATE TABLE ACM_CalibrationSummary;
IF OBJECT_ID('dbo.ACM_ActiveModels', 'U') IS NOT NULL TRUNCATE TABLE ACM_ActiveModels;
IF OBJECT_ID('dbo.ACM_OMR_Diagnostics', 'U') IS NOT NULL TRUNCATE TABLE ACM_OMR_Diagnostics;
IF OBJECT_ID('dbo.ACM_OMRContributionsLong', 'U') IS NOT NULL TRUNCATE TABLE ACM_OMRContributionsLong;
IF OBJECT_ID('dbo.ACM_FusionQualityReport', 'U') IS NOT NULL TRUNCATE TABLE ACM_FusionQualityReport;

PRINT '  Recommendation tables...';
IF OBJECT_ID('dbo.ACM_MaintenanceRecommendation', 'U') IS NOT NULL TRUNCATE TABLE ACM_MaintenanceRecommendation;
IF OBJECT_ID('dbo.ACM_EnhancedMaintenanceRecommendation', 'U') IS NOT NULL TRUNCATE TABLE ACM_EnhancedMaintenanceRecommendation;
IF OBJECT_ID('dbo.ACM_RecommendedActions', 'U') IS NOT NULL TRUNCATE TABLE ACM_RecommendedActions;
IF OBJECT_ID('dbo.ACM_RefitRequests', 'U') IS NOT NULL TRUNCATE TABLE ACM_RefitRequests;

PRINT '  Run metadata tables...';
IF OBJECT_ID('dbo.ACM_FeatureDropLog', 'U') IS NOT NULL TRUNCATE TABLE ACM_FeatureDropLog;
IF OBJECT_ID('dbo.ACM_DataQuality', 'U') IS NOT NULL TRUNCATE TABLE ACM_DataQuality;
IF OBJECT_ID('dbo.ACM_DataContractValidation', 'U') IS NOT NULL TRUNCATE TABLE ACM_DataContractValidation;
IF OBJECT_ID('dbo.ACM_ConfigHistory', 'U') IS NOT NULL TRUNCATE TABLE ACM_ConfigHistory;
IF OBJECT_ID('dbo.ACM_RunTimers', 'U') IS NOT NULL TRUNCATE TABLE ACM_RunTimers;
IF OBJECT_ID('dbo.ACM_RunLogs', 'U') IS NOT NULL TRUNCATE TABLE ACM_RunLogs;
IF OBJECT_ID('dbo.ACM_RunMetadata', 'U') IS NOT NULL TRUNCATE TABLE ACM_RunMetadata;
IF OBJECT_ID('dbo.ACM_RunMetrics', 'U') IS NOT NULL TRUNCATE TABLE ACM_RunMetrics;
IF OBJECT_ID('dbo.ACM_Run_Stats', 'U') IS NOT NULL TRUNCATE TABLE ACM_Run_Stats;

PRINT '  State tables...';
IF OBJECT_ID('dbo.ACM_AssetProfiles', 'U') IS NOT NULL TRUNCATE TABLE ACM_AssetProfiles;
IF OBJECT_ID('dbo.ACM_AlertAge', 'U') IS NOT NULL TRUNCATE TABLE ACM_AlertAge;
IF OBJECT_ID('dbo.ACM_SinceWhen', 'U') IS NOT NULL TRUNCATE TABLE ACM_SinceWhen;
IF OBJECT_ID('dbo.ACM_ContributionCurrent', 'U') IS NOT NULL TRUNCATE TABLE ACM_ContributionCurrent;
IF OBJECT_ID('dbo.ACM_DailyFusedProfile', 'U') IS NOT NULL TRUNCATE TABLE ACM_DailyFusedProfile;
IF OBJECT_ID('dbo.ACM_DefectSummary', 'U') IS NOT NULL TRUNCATE TABLE ACM_DefectSummary;
IF OBJECT_ID('dbo.ACM_ForecastingState', 'U') IS NOT NULL TRUNCATE TABLE ACM_ForecastingState;
IF OBJECT_ID('dbo.ACM_HistorianData', 'U') IS NOT NULL TRUNCATE TABLE ACM_HistorianData;
IF OBJECT_ID('dbo.ACM_BaselineBuffer', 'U') IS NOT NULL TRUNCATE TABLE ACM_BaselineBuffer;

PRINT '  Parent run table (last)...';
-- Cannot TRUNCATE ACM_Runs due to FK constraints - use DELETE instead
IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL DELETE FROM ACM_Runs;

PRINT '';
PRINT 'Re-enabling foreign key constraints...';

SET @sql = '';
SELECT @sql = @sql + 'ALTER TABLE ' + QUOTENAME(OBJECT_NAME(parent_object_id)) + 
              ' WITH CHECK CHECK CONSTRAINT ' + QUOTENAME(name) + ';' + CHAR(13)
FROM sys.foreign_keys
WHERE OBJECT_NAME(parent_object_id) LIKE 'ACM_%';

EXEC sp_executesql @sql;
PRINT '  Done.';

-- =============================================================================
-- Reset coldstart state (optional - comment out to preserve batch state)
-- =============================================================================
PRINT '';
PRINT 'Resetting coldstart state...';
IF OBJECT_ID('dbo.ACM_ColdstartState', 'U') IS NOT NULL 
BEGIN
    TRUNCATE TABLE ACM_ColdstartState;
    PRINT '  ACM_ColdstartState truncated (batch will start fresh)';
END

-- =============================================================================
-- Summary
-- =============================================================================
PRINT '';
PRINT '=== Truncation Complete ===';
PRINT 'Completed at: ' + CONVERT(VARCHAR(30), GETDATE(), 120);
PRINT '';
PRINT 'PRESERVED tables (not truncated):';
PRINT '  - ACM_Config (equipment configuration)';
PRINT '  - ACM_AdaptiveConfig (adaptive overrides)';
PRINT '  - ACM_TagEquipmentMap (tag mapping)';
PRINT '  - ACM_SchemaVersion (schema tracking)';
PRINT '  - Equipment (equipment master)';
PRINT '  - *_Data tables (historian data)';
PRINT '';
PRINT 'To repopulate data, run:';
PRINT '  python scripts/sql_batch_runner.py --equip EQUIPMENT --start-from-beginning';

GO

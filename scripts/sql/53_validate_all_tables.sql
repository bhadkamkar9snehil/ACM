-- SQL-50 Validation: Check all ACM tables for data and schema correctness
-- Run this to validate the SQL-only mode implementation

PRINT '========================================';
PRINT 'SQL-50 VALIDATION REPORT';
PRINT 'Checking all ACM tables for data...';
PRINT '========================================';
PRINT '';

-- Core Tables
PRINT '--- CORE TABLES ---';
SELECT 'Equipments' as TableName, COUNT(*) as RowCount FROM dbo.Equipments;
SELECT 'ACM_Config' as TableName, COUNT(*) as RowCount FROM dbo.ACM_Config;
SELECT 'ACM_Runs' as TableName, COUNT(*) as RowCount FROM dbo.ACM_Runs;
SELECT 'ModelRegistry' as TableName, COUNT(*) as RowCount FROM dbo.ModelRegistry;
PRINT '';

-- Equipment Data Tables
PRINT '--- EQUIPMENT DATA TABLES ---';
SELECT 'FD_FAN_Data' as TableName, COUNT(*) as RowCount, MIN(EntryDateTime) as MinDate, MAX(EntryDateTime) as MaxDate FROM dbo.FD_FAN_Data;
SELECT 'GAS_TURBINE_Data' as TableName, COUNT(*) as RowCount, MIN(EntryDateTime) as MinDate, MAX(EntryDateTime) as MaxDate FROM dbo.GAS_TURBINE_Data;
SELECT 'ACM_TagEquipmentMap' as TableName, COUNT(*) as RowCount FROM dbo.ACM_TagEquipmentMap;
PRINT '';

-- Analytics Output Tables
PRINT '--- ANALYTICS OUTPUT TABLES ---';
SELECT 'ACM_Scores_Wide' as TableName, COUNT(*) as RowCount FROM dbo.ACM_Scores_Wide;
SELECT 'ACM_Scores_Long' as TableName, COUNT(*) as RowCount FROM dbo.ACM_Scores_Long;
SELECT 'ACM_Episodes' as TableName, COUNT(*) as RowCount FROM dbo.ACM_Episodes;
SELECT 'ACM_HealthTimeline' as TableName, COUNT(*) as RowCount FROM dbo.ACM_HealthTimeline;
SELECT 'ACM_RegimeTimeline' as TableName, COUNT(*) as RowCount FROM dbo.ACM_RegimeTimeline;
PRINT '';

-- Contribution & Drift Tables
PRINT '--- CONTRIBUTION & DRIFT TABLES ---';
SELECT 'ACM_ContributionCurrent' as TableName, COUNT(*) as RowCount FROM dbo.ACM_ContributionCurrent;
SELECT 'ACM_ContributionTimeline' as TableName, COUNT(*) as RowCount FROM dbo.ACM_ContributionTimeline;
SELECT 'ACM_DriftSeries' as TableName, COUNT(*) as RowCount FROM dbo.ACM_DriftSeries;
SELECT 'ACM_DriftEvents' as TableName, COUNT(*) as RowCount FROM dbo.ACM_DriftEvents;
SELECT 'ACM_Drift_TS' as TableName, COUNT(*) as RowCount FROM dbo.ACM_Drift_TS;
PRINT '';

-- Summary & Ranking Tables
PRINT '--- SUMMARY & RANKING TABLES ---';
SELECT 'ACM_ThresholdCrossings' as TableName, COUNT(*) as RowCount FROM dbo.ACM_ThresholdCrossings;
SELECT 'ACM_AlertAge' as TableName, COUNT(*) as RowCount FROM dbo.ACM_AlertAge;
SELECT 'ACM_SensorRanking' as TableName, COUNT(*) as RowCount FROM dbo.ACM_SensorRanking;
SELECT 'ACM_RegimeOccupancy' as TableName, COUNT(*) as RowCount FROM dbo.ACM_RegimeOccupancy;
SELECT 'ACM_HealthHistogram' as TableName, COUNT(*) as RowCount FROM dbo.ACM_HealthHistogram;
SELECT 'ACM_RegimeStability' as TableName, COUNT(*) as RowCount FROM dbo.ACM_RegimeStability;
PRINT '';

-- Defect Tables
PRINT '--- DEFECT TABLES ---';
SELECT 'ACM_DefectSummary' as TableName, COUNT(*) as RowCount FROM dbo.ACM_DefectSummary;
SELECT 'ACM_DefectTimeline' as TableName, COUNT(*) as RowCount FROM dbo.ACM_DefectTimeline;
SELECT 'ACM_SensorDefects' as TableName, COUNT(*) as RowCount FROM dbo.ACM_SensorDefects;
SELECT 'ACM_HealthZoneByPeriod' as TableName, COUNT(*) as RowCount FROM dbo.ACM_HealthZoneByPeriod;
SELECT 'ACM_SensorAnomalyByPeriod' as TableName, COUNT(*) as RowCount FROM dbo.ACM_SensorAnomalyByPeriod;
PRINT '';

-- Calibration & Correlation Tables
PRINT '--- CALIBRATION & DETECTOR TABLES ---';
SELECT 'ACM_DetectorCorrelation' as TableName, COUNT(*) as RowCount FROM dbo.ACM_DetectorCorrelation;
SELECT 'ACM_CalibrationSummary' as TableName, COUNT(*) as RowCount FROM dbo.ACM_CalibrationSummary;
SELECT 'ACM_CulpritHistory' as TableName, COUNT(*) as RowCount FROM dbo.ACM_CulpritHistory;
SELECT 'ACM_EpisodeMetrics' as TableName, COUNT(*) as RowCount FROM dbo.ACM_EpisodeMetrics;
PRINT '';

-- Regime Tables
PRINT '--- REGIME TABLES ---';
SELECT 'ACM_RegimeTransitions' as TableName, COUNT(*) as RowCount FROM dbo.ACM_RegimeTransitions;
SELECT 'ACM_RegimeDwellStats' as TableName, COUNT(*) as RowCount FROM dbo.ACM_RegimeDwellStats;
SELECT 'ACM_Regime_Episodes' as TableName, COUNT(*) as RowCount FROM dbo.ACM_Regime_Episodes;
PRINT '';

-- PCA Tables
PRINT '--- PCA TABLES ---';
SELECT 'ACM_PCA_Models' as TableName, COUNT(*) as RowCount FROM dbo.ACM_PCA_Models;
SELECT 'ACM_PCA_Loadings' as TableName, COUNT(*) as RowCount FROM dbo.ACM_PCA_Loadings;
SELECT 'ACM_PCA_Metrics' as TableName, COUNT(*) as RowCount FROM dbo.ACM_PCA_Metrics;
PRINT '';

-- Event Tables
PRINT '--- EVENT TABLES ---';
SELECT 'ACM_Anomaly_Events' as TableName, COUNT(*) as RowCount FROM dbo.ACM_Anomaly_Events;
PRINT '';

PRINT '========================================';
PRINT 'VALIDATION COMPLETE';
PRINT 'Check above for any tables with 0 rows after first pipeline run';
PRINT '========================================';

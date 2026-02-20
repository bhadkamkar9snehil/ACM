-- =============================================================================
-- Migration: v11.15.0 Schema Additions
-- Date:       2026-02-20
-- Author:     ACM Auto-Migration
-- Description:
--   Adds columns introduced in v11.15.0 that are required by the QA checks
--   and output manager but were missing from deployed databases.
--
--   Tables affected:
--     dbo.ACM_EpisodeDiagnostics  -> StartTime, EndTime, Culprits
--     dbo.ACM_SensorHotspots      -> MaxAbsOMR, RankingScore
--
--   Safe to run on any database that was deployed before v11.15.0.
--   All ALTER statements are guarded by IF NOT EXISTS and are idempotent.
-- =============================================================================

USE ACM;
GO

PRINT 'Migration v11.15.0: Starting schema additions...';
GO

-- ---------------------------------------------------------------------------
-- ACM_EpisodeDiagnostics
-- ---------------------------------------------------------------------------
PRINT 'Checking ACM_EpisodeDiagnostics...';
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.ACM_EpisodeDiagnostics') AND name = 'StartTime'
)
BEGIN
    ALTER TABLE dbo.[ACM_EpisodeDiagnostics] ADD [StartTime] DATETIME2(3) NULL;
    PRINT '  + Added ACM_EpisodeDiagnostics.StartTime';
END
ELSE
    PRINT '  . ACM_EpisodeDiagnostics.StartTime already exists - skipped';
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.ACM_EpisodeDiagnostics') AND name = 'EndTime'
)
BEGIN
    ALTER TABLE dbo.[ACM_EpisodeDiagnostics] ADD [EndTime] DATETIME2(3) NULL;
    PRINT '  + Added ACM_EpisodeDiagnostics.EndTime';
END
ELSE
    PRINT '  . ACM_EpisodeDiagnostics.EndTime already exists - skipped';
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.ACM_EpisodeDiagnostics') AND name = 'Culprits'
)
BEGIN
    ALTER TABLE dbo.[ACM_EpisodeDiagnostics] ADD [Culprits] NVARCHAR(512) NULL;
    PRINT '  + Added ACM_EpisodeDiagnostics.Culprits';
END
ELSE
    PRINT '  . ACM_EpisodeDiagnostics.Culprits already exists - skipped';
GO

-- ---------------------------------------------------------------------------
-- ACM_SensorHotspots
-- ---------------------------------------------------------------------------
PRINT 'Checking ACM_SensorHotspots...';
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.ACM_SensorHotspots') AND name = 'MaxAbsOMR'
)
BEGIN
    ALTER TABLE dbo.[ACM_SensorHotspots] ADD [MaxAbsOMR] FLOAT(53) NULL;
    PRINT '  + Added ACM_SensorHotspots.MaxAbsOMR';
END
ELSE
    PRINT '  . ACM_SensorHotspots.MaxAbsOMR already exists - skipped';
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.ACM_SensorHotspots') AND name = 'RankingScore'
)
BEGIN
    ALTER TABLE dbo.[ACM_SensorHotspots] ADD [RankingScore] FLOAT(53) NULL;
    PRINT '  + Added ACM_SensorHotspots.RankingScore';
END
ELSE
    PRINT '  . ACM_SensorHotspots.RankingScore already exists - skipped';
GO

-- ---------------------------------------------------------------------------
PRINT 'Migration v11.15.0: Complete.';
GO

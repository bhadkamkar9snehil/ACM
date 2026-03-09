-- ============================================================================
-- ACM v11.16.x - Explicit zero-day run observability on ACM_Runs
-- ============================================================================
-- Purpose:
-- - Persist per-run day-0/EWM status directly on ACM_Runs so operators can tell
--   whether zero-day scoring was active even when ACM_RunLogs is unavailable.
-- - Keep the contract queryable with scalar columns instead of hiding it in logs.
--
-- Added columns:
-- - ZeroDayScoringActive BIT
-- - ZeroDayStatus NVARCHAR(64)
-- - ZeroDaySurfaceType NVARCHAR(64)
-- - ZeroDayChannelCount INT
-- ============================================================================

USE ACM;
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'ZeroDayScoringActive') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD ZeroDayScoringActive BIT NULL;

    PRINT 'Added ACM_Runs.ZeroDayScoringActive';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.ZeroDayScoringActive already exists or table is missing (skipped)';
END
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'ZeroDayStatus') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD ZeroDayStatus NVARCHAR(64) NULL;

    PRINT 'Added ACM_Runs.ZeroDayStatus';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.ZeroDayStatus already exists or table is missing (skipped)';
END
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'ZeroDaySurfaceType') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD ZeroDaySurfaceType NVARCHAR(64) NULL;

    PRINT 'Added ACM_Runs.ZeroDaySurfaceType';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.ZeroDaySurfaceType already exists or table is missing (skipped)';
END
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'ZeroDayChannelCount') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD ZeroDayChannelCount INT NULL;

    PRINT 'Added ACM_Runs.ZeroDayChannelCount';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.ZeroDayChannelCount already exists or table is missing (skipped)';
END
GO

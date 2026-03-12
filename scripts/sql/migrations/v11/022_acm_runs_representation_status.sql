-- ============================================================================
-- ACM 2026.2 - Explicit representation run observability on ACM_Runs
-- ============================================================================
-- Purpose:
-- - Persist per-run representation-governance status directly on ACM_Runs so
--   operators can inspect scoreability, learnability, and compatibility without
--   joining shadow control-plane tables.
-- - Keep the contract queryable with scalar columns instead of relying only on
--   ACM_RepresentationStatus for top-level run review.
--
-- Added columns:
-- - RepresentationAuthoritative BIT
-- - RepresentationScoreAllowed BIT
-- - RepresentationLearnAllowed BIT
-- - RepresentationContextLabel NVARCHAR(128)
-- - RepresentationRuntimeMode NVARCHAR(64)
-- - RepresentationSchemaCompatibility NVARCHAR(64)
-- - RepresentationBasisCompatibility NVARCHAR(64)
-- - RepresentationBaselineCompatibility NVARCHAR(64)
-- - RepresentationSuppressedReasons NVARCHAR(MAX)
-- - RepresentationDegradedReasons NVARCHAR(MAX)
-- ============================================================================

USE ACM;
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'RepresentationAuthoritative') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD RepresentationAuthoritative BIT NULL;

    PRINT 'Added ACM_Runs.RepresentationAuthoritative';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.RepresentationAuthoritative already exists or table is missing (skipped)';
END
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'RepresentationScoreAllowed') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD RepresentationScoreAllowed BIT NULL;

    PRINT 'Added ACM_Runs.RepresentationScoreAllowed';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.RepresentationScoreAllowed already exists or table is missing (skipped)';
END
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'RepresentationLearnAllowed') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD RepresentationLearnAllowed BIT NULL;

    PRINT 'Added ACM_Runs.RepresentationLearnAllowed';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.RepresentationLearnAllowed already exists or table is missing (skipped)';
END
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'RepresentationContextLabel') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD RepresentationContextLabel NVARCHAR(128) NULL;

    PRINT 'Added ACM_Runs.RepresentationContextLabel';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.RepresentationContextLabel already exists or table is missing (skipped)';
END
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'RepresentationRuntimeMode') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD RepresentationRuntimeMode NVARCHAR(64) NULL;

    PRINT 'Added ACM_Runs.RepresentationRuntimeMode';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.RepresentationRuntimeMode already exists or table is missing (skipped)';
END
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'RepresentationSchemaCompatibility') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD RepresentationSchemaCompatibility NVARCHAR(64) NULL;

    PRINT 'Added ACM_Runs.RepresentationSchemaCompatibility';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.RepresentationSchemaCompatibility already exists or table is missing (skipped)';
END
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'RepresentationBasisCompatibility') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD RepresentationBasisCompatibility NVARCHAR(64) NULL;

    PRINT 'Added ACM_Runs.RepresentationBasisCompatibility';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.RepresentationBasisCompatibility already exists or table is missing (skipped)';
END
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'RepresentationBaselineCompatibility') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD RepresentationBaselineCompatibility NVARCHAR(64) NULL;

    PRINT 'Added ACM_Runs.RepresentationBaselineCompatibility';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.RepresentationBaselineCompatibility already exists or table is missing (skipped)';
END
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'RepresentationSuppressedReasons') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD RepresentationSuppressedReasons NVARCHAR(MAX) NULL;

    PRINT 'Added ACM_Runs.RepresentationSuppressedReasons';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.RepresentationSuppressedReasons already exists or table is missing (skipped)';
END
GO

IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_Runs', 'RepresentationDegradedReasons') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_Runs
        ADD RepresentationDegradedReasons NVARCHAR(MAX) NULL;

    PRINT 'Added ACM_Runs.RepresentationDegradedReasons';
END
ELSE
BEGIN
    PRINT 'ACM_Runs.RepresentationDegradedReasons already exists or table is missing (skipped)';
END
GO

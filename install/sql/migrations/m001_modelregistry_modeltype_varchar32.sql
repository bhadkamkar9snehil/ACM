-- Migration m001: Widen ModelRegistry.ModelType from VARCHAR(16) to VARCHAR(32)
--
-- Root cause: 'calibration_params' (18 chars) exceeds the original VARCHAR(16) limit,
-- causing calibration state to never be persisted. Every scoring batch was silently
-- recalibrating from scratch.
--
-- Safe to run multiple times (ALTER TABLE is idempotent here via column width check).
-- Run this against the ACM database before the next pipeline restart.
-- ============================================================================

USE ACM;
GO

-- Only alter if the column is still the old width
IF EXISTS (
    SELECT 1
    FROM   sys.columns c
    JOIN   sys.objects o ON c.object_id = o.object_id
    WHERE  o.name        = 'ModelRegistry'
      AND  o.schema_id   = SCHEMA_ID('dbo')
      AND  c.name        = 'ModelType'
      AND  c.max_length  < 32          -- VARCHAR max_length is in bytes
)
BEGIN
    ALTER TABLE dbo.[ModelRegistry]
        ALTER COLUMN [ModelType] VARCHAR(32) NOT NULL;

    PRINT 'ModelRegistry.ModelType widened to VARCHAR(32).';
END
ELSE
BEGIN
    PRINT 'ModelRegistry.ModelType already VARCHAR(32) or wider — no change needed.';
END
GO

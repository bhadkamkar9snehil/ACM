-- scripts/sql/migrations/v11/016_acm_ewm_baseline_state_version.sql
-- ACM v11.16.x - EWM baseline state versioning
--
-- Background:
-- EWM baseline semantics changed from an accidental engineered detector frame
-- to an explicit tag-agnostic raw numeric monitoring surface. Persisted state
-- must therefore be versioned so legacy rows are ignored instead of silently
-- reused under the new contract.
--
-- Migration policy:
-- - Add nullable StateVersion to ACM_EWMBaseline.
-- - Existing rows remain NULL and are treated as legacy state.
-- - New runtime writes StateVersion = 2.

USE ACM;
GO

SET NOCOUNT ON;

IF OBJECT_ID('dbo.ACM_EWMBaseline', 'U') IS NOT NULL
   AND COL_LENGTH('dbo.ACM_EWMBaseline', 'StateVersion') IS NULL
BEGIN
    ALTER TABLE dbo.ACM_EWMBaseline
        ADD StateVersion SMALLINT NULL;

    PRINT 'Added ACM_EWMBaseline.StateVersion';
END
ELSE
BEGIN
    PRINT 'ACM_EWMBaseline.StateVersion already exists or table is missing (skipped)';
END
GO

PRINT 'Migration 016 complete.';
GO

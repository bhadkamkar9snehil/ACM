-- scripts/sql/migrations/v11/015_acm_regime_binner_state.sql
-- ACM v11.16.0+ - Zero-Day Learning: online regime proxy persistence
--
-- Background:
-- The active runtime persists the asset-agnostic online regime proxy state in
-- this table. The current JSON payload is written by OnlinePCABinner, which
-- tracks a latent PC1 regime proxy over a tag-agnostic monitoring surface.
--
-- The table remains intentionally generic: one JSON blob per equipment. Old
-- ControlVariableBinner JSON and current OnlinePCABinner JSON can coexist at
-- the table level; runtime validates binner_type before restoring state.
--
-- One row per EquipID. StateJson contains:
--   {
--     "binner_type": "OnlinePCABinner",
--     "state_version": 1,
--     "n_bins": 3,
--     "min_rows_for_assignment": 20,
--     "sensor_cols": ["sensor_00_avg", "sensor_01_avg", "sensor_02_avg"],
--     "n_rows_seen": 847,
--     "n_batches_seen": 47,
--     "mean": [...],
--     "cov": [[...], [...], [...]],
--     "dominant_vector": [...],
--     "pc1_history": [...],
--     "binner_remapped": false
--   }
--
-- See docs/obsidian_vault/knowledge/Paradigm-Zero-Day-Learning.md
-- Safe to run on any DB state: guarded by IF OBJECT_ID check.

USE ACM;
GO

SET NOCOUNT ON;

IF OBJECT_ID('dbo.ACM_RegimeBinnerState', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ACM_RegimeBinnerState (
        EquipID     INT           NOT NULL,
        StateJson   NVARCHAR(MAX) NOT NULL,    -- JSON blob of edges + metadata
        UpdatedAt   DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_ACM_RegimeBinnerState PRIMARY KEY CLUSTERED (EquipID)
    );

    PRINT 'Created table dbo.ACM_RegimeBinnerState';
END
ELSE
BEGIN
    PRINT 'Table dbo.ACM_RegimeBinnerState already exists (skipped)';
END
GO

PRINT 'Migration 015 complete.';
GO

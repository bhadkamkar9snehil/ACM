-- scripts/sql/migrations/v11/014_acm_ewm_baseline.sql
-- ACM v11.16.0 - Zero-Day Learning: EWM Baseline table
--
-- Background:
-- ACM's current training-window paradigm requires a clean historical window
-- before scoring can begin. This table enables zero-day learning via
-- Exponentially Weighted Moving (EWM) baselines that start updating from the
-- second observation, with no pre-training requirement.
--
-- Each row represents the current EWM state for one (EquipID, RegimeID, SensorName)
-- combination. RegimeID = -1 is the global fallback used before per-regime
-- statistics are mature.
--
-- Dual-rate baselines:
--   Fast (α=0.05): adapts over ~20 batches — captures operating envelope shifts
--   Slow (α=0.005): adapts over ~200 batches — captures machine character
--
-- Cross-rate anomaly logic:
--   Anomalous vs fast AND slow → genuine fault
--   Anomalous vs fast only    → regime shift (NOT a fault)
--
-- BaselineIntegrity:
--   'ok'     — updating normally
--   'suspect' — score distribution showing early collapse signs
--   'frozen'  — EWM update paused; scoring against frozen baseline to expose fault
--
-- See docs/obsidian_vault/knowledge/Paradigm-Zero-Day-Learning.md
-- Safe to run on any DB state: guarded by IF OBJECT_ID check.

USE ACM;
GO

SET NOCOUNT ON;

IF OBJECT_ID('dbo.ACM_EWMBaseline', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ACM_EWMBaseline (
        EquipID             INT          NOT NULL,
        RegimeID            INT          NOT NULL,   -- -1 = global fallback
        SensorName          VARCHAR(200) NOT NULL,
        EWMMean_Fast        FLOAT        NULL,        -- alpha=0.05 EWM mean
        EWMVar_Fast         FLOAT        NULL,        -- alpha=0.05 EWM variance
        EWMMean_Slow        FLOAT        NULL,        -- alpha=0.005 EWM mean
        EWMVar_Slow         FLOAT        NULL,        -- alpha=0.005 EWM variance
        NSamples            INT          NOT NULL DEFAULT 0,  -- obs count in this regime
        BaselineIntegrity   VARCHAR(20)  NOT NULL DEFAULT 'ok', -- 'ok'|'suspect'|'frozen'
        ScoreP50            FLOAT        NULL,        -- rolling P50 of z-scores
        ScoreP95            FLOAT        NULL,        -- rolling P95 of z-scores
        UpdatedAt           DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_ACM_EWMBaseline PRIMARY KEY CLUSTERED (EquipID, RegimeID, SensorName)
    );

    -- Index for equipment-level queries (load all state for one equipment)
    CREATE NONCLUSTERED INDEX IX_ACM_EWMBaseline_EquipID
        ON dbo.ACM_EWMBaseline (EquipID)
        INCLUDE (RegimeID, SensorName, NSamples, BaselineIntegrity);

    PRINT 'Created table dbo.ACM_EWMBaseline';
END
ELSE
BEGIN
    PRINT 'Table dbo.ACM_EWMBaseline already exists (skipped)';
END
GO

PRINT 'Migration 014 complete.';
GO

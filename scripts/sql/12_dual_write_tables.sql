-- =============================================
-- ACM Dual-Write Tables (Phase 2)
-- =============================================
-- Simplified tables that accept wide-format data directly
-- without complex transformations. Optimized for dual-write mode.
-- =============================================

USE [ACM];
GO

-- Scores in wide format (one row per timestamp with all detector scores)
IF OBJECT_ID('dbo.ACM_Scores_Wide','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_Scores_Wide (
    RunID              uniqueidentifier NOT NULL,
    EquipID            int NOT NULL,
    EntryDateTime      datetime2(3) NOT NULL,
    
    -- Raw detector scores
    ar1_raw            float NULL,
    pca_spe            float NULL,
    pca_t2             float NULL,
    mhal_raw           float NULL,
    iforest_raw        float NULL,
    gmm_raw            float NULL,
    cusum_raw          float NULL,
    
    -- Z-scores (normalized)
    ar1_z              float NULL,
    pca_spe_z          float NULL,
    pca_t2_z           float NULL,
    mhal_z             float NULL,
    iforest_z          float NULL,
    gmm_z              float NULL,
    cusum_z            float NULL,
    
    -- Fusion and alerts
    fused              float NULL,
    alert_mode         tinyint NULL,
    
    -- Regime info
    regime_label       int NULL,
    regime_state       nvarchar(32) NULL,
    per_regime_active  bit NULL,
    
    CreatedAt          datetime2(3) NOT NULL CONSTRAINT DF_ACM_Scores_Wide_CreatedAt DEFAULT (SYSUTCDATETIME())
);

CREATE CLUSTERED INDEX IX_ScoresWide_RunID_Time ON dbo.ACM_Scores_Wide(RunID, EntryDateTime);
CREATE NONCLUSTERED INDEX IX_ScoresWide_EquipID_Time ON dbo.ACM_Scores_Wide(EquipID, EntryDateTime DESC);
END
GO

-- Episodes/Anomalies in simple format
IF OBJECT_ID('dbo.ACM_Episodes','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_Episodes (
    RunID                uniqueidentifier NOT NULL,
    EquipID              int NOT NULL,
    EpisodeID            int NOT NULL,
    StartEntryDateTime   datetime2(3) NOT NULL,
    EndEntryDateTime     datetime2(3) NOT NULL,
    DurationSeconds      float NULL,
    DurationHours        float NULL,
    RecordCount          int NULL,
    
    -- Primary detectors/culprits
    Culprits             nvarchar(512) NULL,
    PrimaryDetector      nvarchar(64) NULL,
    
    -- Severity/state
    Severity             nvarchar(16) NULL,
    RegimeLabel          int NULL,
    RegimeState          nvarchar(32) NULL,
    
    CreatedAt            datetime2(3) NOT NULL CONSTRAINT DF_ACM_Episodes_CreatedAt DEFAULT (SYSUTCDATETIME())
);

CREATE CLUSTERED INDEX IX_Episodes_RunID_Start ON dbo.ACM_Episodes(RunID, StartEntryDateTime);
CREATE NONCLUSTERED INDEX IX_Episodes_EquipID_Time ON dbo.ACM_Episodes(EquipID, StartEntryDateTime DESC);
END
GO

-- Run Summary (lightweight metadata for each run)
IF OBJECT_ID('dbo.ACM_RunSummary','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_RunSummary (
    RunID                uniqueidentifier NOT NULL PRIMARY KEY,
    EquipID              int NOT NULL,
    EquipCode            nvarchar(64) NOT NULL,
    
    StartEntryDateTime   datetime2(3) NOT NULL,
    EndEntryDateTime     datetime2(3) NULL,
    
    -- Data stats
    RowsProcessed        int NULL,
    EpisodesDetected     int NULL,
    
    -- Config info
    ConfigSignature      nvarchar(64) NULL,
    DualMode             bit NOT NULL CONSTRAINT DF_ACM_RunSummary_DualMode DEFAULT (1),
    
    -- Timing
    ProcessingTimeMs     int NULL,
    
    -- Outcome
    Status               nvarchar(16) NULL, -- 'OK', 'ERROR', 'PARTIAL'
    ErrorMessage         nvarchar(max) NULL,
    
    CreatedAt            datetime2(3) NOT NULL CONSTRAINT DF_ACM_RunSummary_CreatedAt DEFAULT (SYSUTCDATETIME())
);

CREATE NONCLUSTERED INDEX IX_RunSummary_EquipID_Start ON dbo.ACM_RunSummary(EquipID, StartEntryDateTime DESC);
END
GO

PRINT 'ACM Dual-Write tables created successfully';
GO

-- Verification queries
SELECT 'ACM_Scores_Wide' AS TableName, COUNT(*) AS RecordCount FROM dbo.ACM_Scores_Wide;
SELECT 'ACM_Episodes' AS TableName, COUNT(*) AS RecordCount FROM dbo.ACM_Episodes;
SELECT 'ACM_RunSummary' AS TableName, COUNT(*) AS RecordCount FROM dbo.ACM_RunSummary;
GO

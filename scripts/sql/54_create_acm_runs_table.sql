-- ============================================================================
-- SQL-50: Create ACM_Runs table for detailed run metadata
-- ============================================================================
-- This table stores comprehensive run-level metadata including health metrics,
-- data quality, and performance tracking. This is separate from the simple
-- Runs table used by usp_ACM_StartRun for basic run tracking.
-- ============================================================================

USE ACM;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- Create ACM_Runs table with comprehensive metadata
IF OBJECT_ID('dbo.ACM_Runs', 'U') IS NOT NULL 
BEGIN
    PRINT 'ACM_Runs table already exists, dropping...';
    DROP TABLE dbo.ACM_Runs;
END
GO

CREATE TABLE dbo.ACM_Runs (
    RunID UNIQUEIDENTIFIER NOT NULL,
    EquipID INT NOT NULL,
    EquipName NVARCHAR(200) NULL,
    StartedAt DATETIME2 NOT NULL,
    CompletedAt DATETIME2 NULL,
    DurationSeconds INT NULL,
    ConfigSignature VARCHAR(64) NULL,
    TrainRowCount INT NULL,
    ScoreRowCount INT NULL,
    EpisodeCount INT NULL,
    HealthStatus VARCHAR(50) NULL, -- 'HEALTHY', 'CAUTION', 'ALERT'
    AvgHealthIndex FLOAT NULL,
    MinHealthIndex FLOAT NULL,
    MaxFusedZ FLOAT NULL,
    DataQualityScore FLOAT NULL,
    RefitRequested BIT DEFAULT 0,
    ErrorMessage NVARCHAR(1000) NULL,
    KeptColumns NVARCHAR(MAX) NULL, -- Comma-separated list of sensor columns
    ZeroDayScoringActive BIT NULL,
    ZeroDayStatus NVARCHAR(64) NULL,
    ZeroDaySurfaceType NVARCHAR(64) NULL,
    ZeroDayChannelCount INT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_Runs PRIMARY KEY CLUSTERED (RunID),
    CONSTRAINT FK_ACM_Runs_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID)
);
GO

-- Create indexes for common queries
CREATE INDEX IX_ACM_Runs_EquipStarted 
    ON dbo.ACM_Runs (EquipID, StartedAt DESC);
GO

CREATE INDEX IX_ACM_Runs_Status 
    ON dbo.ACM_Runs (EquipID, HealthStatus) 
    WHERE HealthStatus IN ('CAUTION', 'ALERT');
GO

PRINT 'ACM_Runs table created successfully';
GO

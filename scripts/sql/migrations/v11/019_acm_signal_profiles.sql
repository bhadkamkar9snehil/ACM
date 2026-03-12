-- ============================================================================
-- ACM 2026.2 - Shadow signal profile control-plane table
-- ============================================================================

USE ACM;
GO

SET NOCOUNT ON;

IF OBJECT_ID('dbo.ACM_SignalProfiles', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ACM_SignalProfiles (
        RunID                  VARCHAR(64)   NOT NULL,
        EquipID                INT           NOT NULL,
        Timestamp              DATETIME2     NOT NULL,
        SignalName             NVARCHAR(200) NOT NULL,
        MissingRatio           FLOAT         NULL,
        FlatlineRatio          FLOAT         NULL,
        EffectiveCadenceSeconds FLOAT        NULL,
        MonitorabilityClass    NVARCHAR(32)  NULL,
        ReasonCodesJson        NVARCHAR(MAX) NULL,
        SignalProfileVersion   NVARCHAR(64)  NOT NULL,
        CreatedAt              DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_ACM_SignalProfiles PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp, SignalName)
    );

    CREATE NONCLUSTERED INDEX IX_ACM_SignalProfiles_EquipTime
        ON dbo.ACM_SignalProfiles (EquipID, Timestamp DESC);

    PRINT 'Created table dbo.ACM_SignalProfiles';
END
ELSE
BEGIN
    PRINT 'Table dbo.ACM_SignalProfiles already exists (skipped)';
END
GO

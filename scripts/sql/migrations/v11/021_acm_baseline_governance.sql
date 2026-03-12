-- ============================================================================
-- ACM 2026.2 - Shadow baseline governance control-plane table
-- ============================================================================

USE ACM;
GO

SET NOCOUNT ON;

IF OBJECT_ID('dbo.ACM_BaselineGovernance', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ACM_BaselineGovernance (
        RunID                  VARCHAR(64)   NOT NULL,
        EquipID                INT           NOT NULL,
        Timestamp              DATETIME2     NOT NULL,
        RuntimeMode            NVARCHAR(64)  NOT NULL,
        ReadinessState         NVARCHAR(64)  NULL,
        BaselineCandidateState NVARCHAR(128) NULL,
        ContaminationVerdict   NVARCHAR(64)  NULL,
        FreezeState            NVARCHAR(64)  NULL,
        ShadowRefreshState     NVARCHAR(64)  NULL,
        PromotedPackageVersion NVARCHAR(128) NULL,
        ReasonCodesJson        NVARCHAR(MAX) NULL,
        CreatedAt              DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_ACM_BaselineGovernance PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp)
    );

    CREATE NONCLUSTERED INDEX IX_ACM_BaselineGovernance_EquipTime
        ON dbo.ACM_BaselineGovernance (EquipID, Timestamp DESC);

    PRINT 'Created table dbo.ACM_BaselineGovernance';
END
ELSE
BEGIN
    PRINT 'Table dbo.ACM_BaselineGovernance already exists (skipped)';
END
GO

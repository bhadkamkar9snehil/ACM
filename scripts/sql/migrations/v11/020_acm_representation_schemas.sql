-- ============================================================================
-- ACM 2026.2 - Shadow representation schema/basis control-plane table
-- ============================================================================

USE ACM;
GO

SET NOCOUNT ON;

IF OBJECT_ID('dbo.ACM_RepresentationSchemas', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ACM_RepresentationSchemas (
        RunID                 VARCHAR(64)   NOT NULL,
        EquipID               INT           NOT NULL,
        Timestamp             DATETIME2     NOT NULL,
        RepresentationVersion NVARCHAR(64)  NOT NULL,
        SchemaVersion         NVARCHAR(64)  NOT NULL,
        BasisSignature        NVARCHAR(128) NOT NULL,
        BaselinePackageVersion NVARCHAR(128) NOT NULL,
        SignalProfileVersion  NVARCHAR(64)  NOT NULL,
        SchemaCompatibility   NVARCHAR(64)  NULL,
        BasisCompatibility    NVARCHAR(64)  NULL,
        MissingSignalsJson    NVARCHAR(MAX) NULL,
        NewSignalsJson        NVARCHAR(MAX) NULL,
        InvalidatedFeaturesJson NVARCHAR(MAX) NULL,
        CreatedAt             DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_ACM_RepresentationSchemas PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp)
    );

    CREATE NONCLUSTERED INDEX IX_ACM_RepresentationSchemas_EquipTime
        ON dbo.ACM_RepresentationSchemas (EquipID, Timestamp DESC);

    PRINT 'Created table dbo.ACM_RepresentationSchemas';
END
ELSE
BEGIN
    PRINT 'Table dbo.ACM_RepresentationSchemas already exists (skipped)';
END
GO

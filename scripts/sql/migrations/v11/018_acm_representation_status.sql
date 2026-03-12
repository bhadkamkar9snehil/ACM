-- ============================================================================
-- ACM 2026.2 - Shadow representation control-plane status table
-- ============================================================================

USE ACM;
GO

SET NOCOUNT ON;

IF OBJECT_ID('dbo.ACM_RepresentationStatus', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ACM_RepresentationStatus (
        RunID                    VARCHAR(64)   NOT NULL,
        EquipID                  INT           NOT NULL,
        Timestamp                DATETIME2     NOT NULL,
        SourceWindowStart        DATETIME2     NULL,
        SourceWindowEnd          DATETIME2     NULL,
        WindowLabel              NVARCHAR(32)  NULL,
        Enabled                  BIT           NOT NULL DEFAULT 1,
        Authoritative            BIT           NOT NULL DEFAULT 0,
        RepresentationVersion    NVARCHAR(64)  NOT NULL,
        SchemaVersion            NVARCHAR(64)  NOT NULL,
        BasisSignature           NVARCHAR(128) NOT NULL,
        BaselinePackageVersion   NVARCHAR(128) NOT NULL,
        SignalProfileVersion     NVARCHAR(64)  NOT NULL,
        CoverageRatio            FLOAT         NULL,
        StaleRatio               FLOAT         NULL,
        MissingnessGrade         NVARCHAR(32)  NULL,
        EffectiveSignalCount     INT           NULL,
        ExpectedRows             INT           NULL,
        ObservedRows             INT           NULL,
        DuplicateRowsRemoved     INT           NULL,
        FutureRowsDropped        INT           NULL,
        MonitorableSignalCount   INT           NULL,
        WeakSignalCount          INT           NULL,
        UntrustedSignalCount     INT           NULL,
        SignalSummaryReasonsJson NVARCHAR(MAX) NULL,
        ContextID                NVARCHAR(128) NULL,
        ContextLabel             NVARCHAR(128) NULL,
        ContextConfidence        FLOAT         NULL,
        ContextStability         NVARCHAR(32)  NULL,
        TransitionStatus         NVARCHAR(32)  NULL,
        ContextIsNovel           BIT           NOT NULL DEFAULT 0,
        ContextIsAmbiguous       BIT           NOT NULL DEFAULT 1,
        SchemaCompatibility      NVARCHAR(64)  NULL,
        BasisCompatibility       NVARCHAR(64)  NULL,
        BaselineCompatibility    NVARCHAR(64)  NULL,
        ScoreAllowed             BIT           NULL,
        LearnAllowed             BIT           NULL,
        RepresentationConfidence FLOAT         NULL,
        InputIntegrityGrade      NVARCHAR(32)  NULL,
        ContextStabilityGrade    NVARCHAR(32)  NULL,
        DegradedReasonsJson      NVARCHAR(MAX) NULL,
        SuppressedReasonsJson    NVARCHAR(MAX) NULL,
        MissingSignalsJson       NVARCHAR(MAX) NULL,
        NewSignalsJson           NVARCHAR(MAX) NULL,
        InvalidatedFeaturesJson  NVARCHAR(MAX) NULL,
        NotesJson                NVARCHAR(MAX) NULL,
        CreatedAt                DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_ACM_RepresentationStatus PRIMARY KEY CLUSTERED (RunID, EquipID, Timestamp)
    );

    CREATE NONCLUSTERED INDEX IX_ACM_RepresentationStatus_EquipTime
        ON dbo.ACM_RepresentationStatus (EquipID, Timestamp DESC);

    PRINT 'Created table dbo.ACM_RepresentationStatus';
END
ELSE
BEGIN
    PRINT 'Table dbo.ACM_RepresentationStatus already exists (skipped)';
END
GO

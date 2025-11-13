/*
ACM Stored Procedures: run lifecycle + equipment registration
Assumptions:
- Core tables exist from 10_core_tables.sql
- Optional config tables from 15_config_tables.sql
*/
USE [ACM];
GO

/* Safety drop (idempotent deploy) */
IF OBJECT_ID('dbo.usp_ACM_StartRun','P') IS NOT NULL DROP PROCEDURE dbo.usp_ACM_StartRun; 
IF OBJECT_ID('dbo.usp_ACM_FinalizeRun','P') IS NOT NULL DROP PROCEDURE dbo.usp_ACM_FinalizeRun; 
IF OBJECT_ID('dbo.usp_ACM_RegisterEquipment','P') IS NOT NULL DROP PROCEDURE dbo.usp_ACM_RegisterEquipment; 
GO

CREATE PROCEDURE dbo.usp_ACM_RegisterEquipment
    @EquipCode   nvarchar(64),
    @ExternalDb  sysname = NULL,
    @Active      bit = 1,
    @EquipID     int OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    -- Upsert-like: try find by code
    SELECT @EquipID = EquipID FROM dbo.Equipments WITH (UPDLOCK, HOLDLOCK) WHERE EquipCode = @EquipCode;
    IF @EquipID IS NULL
    BEGIN
        INSERT INTO dbo.Equipments(EquipCode, ExternalDb, Active)
        VALUES(@EquipCode, @ExternalDb, @Active);
        SET @EquipID = SCOPE_IDENTITY();
    END
    ELSE
    BEGIN
        UPDATE dbo.Equipments
        SET ExternalDb = COALESCE(@ExternalDb, ExternalDb),
            Active     = COALESCE(@Active, Active)
        WHERE EquipID = @EquipID;
    END
END
GO

/* Start a run: records metadata and returns RunID */
CREATE PROCEDURE dbo.usp_ACM_StartRun
    @EquipID     int,
    @ConfigHash  nvarchar(64)  = NULL,
    @WindowStartEntryDateTime datetime2(3)  = NULL,
    @WindowEndEntryDateTime   datetime2(3)  = NULL,
    @Stage       nvarchar(32) = N'started',
    @Version     nvarchar(32) = NULL,
    @TriggerReason nvarchar(64) = NULL,
    @RunID       uniqueidentifier OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    IF @RunID IS NULL SET @RunID = NEWID();
    DECLARE @now datetime2(3) = SYSUTCDATETIME();

    INSERT INTO dbo.RunLog(
        RunID, EquipID, Stage, StartEntryDateTime, EndEntryDateTime,
        Outcome, RowsRead, RowsWritten, ErrorJSON, TriggerReason, Version, ConfigHash,
        WindowStartEntryDateTime, WindowEndEntryDateTime
    )
    VALUES(
        @RunID, @EquipID, @Stage, @now, NULL,
        NULL, NULL, NULL, NULL, @TriggerReason, @Version, @ConfigHash,
        @WindowStartEntryDateTime, @WindowEndEntryDateTime
    );

    -- Delete prior partial artifacts for same RunID if any (idempotent re-run)
    DELETE FROM dbo.ScoresTS WHERE RunID = @RunID;
    DELETE FROM dbo.DriftTS WHERE RunID = @RunID;
    DELETE FROM dbo.AnomalyEvents WHERE RunID = @RunID;
    DELETE FROM dbo.RegimeEpisodes WHERE RunID = @RunID;
    DELETE FROM dbo.PCA_Metrics WHERE RunID = @RunID;
END
GO

/* Finalize a run: set status and stats */
CREATE PROCEDURE dbo.usp_ACM_FinalizeRun
    @RunID       uniqueidentifier,
    @Outcome     nvarchar(16),
    @RowsRead    int = NULL,
    @RowsWritten int = NULL,
    @ErrorJSON   nvarchar(max) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.RunLog
    SET Outcome = @Outcome,
        EndEntryDateTime = SYSUTCDATETIME(),
        RowsRead = COALESCE(@RowsRead, RowsRead),
        RowsWritten = COALESCE(@RowsWritten, RowsWritten),
        ErrorJSON = COALESCE(@ErrorJSON, ErrorJSON)
    WHERE RunID = @RunID;
END
GO

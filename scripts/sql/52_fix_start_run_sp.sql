-- SQL-50: Fix usp_ACM_StartRun to use equipment-specific data tables instead of dbo.Historian
-- This allows the stored procedure to work with FD_FAN_Data, GAS_TURBINE_Data, etc.

-- Drop and recreate the procedure
IF OBJECT_ID('dbo.usp_ACM_StartRun', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ACM_StartRun;
GO

CREATE PROC dbo.usp_ACM_StartRun
  @EquipCode                 NVARCHAR(100) = NULL,
  @EquipID                   INT = NULL,
  @Stage                     VARCHAR(10),
  @TickMinutes               INT,
  @DefaultStartUtc           DATETIME2(3) = NULL,
  @Version                   VARCHAR(50) = NULL,
  @ConfigHash                VARCHAR(128) = NULL,
  @TriggerReason             VARCHAR(64) = 'timer',
  @RunID                     UNIQUEIDENTIFIER OUTPUT,
  @WindowStartEntryDateTime  DATETIME2(3) OUTPUT,
  @WindowEndEntryDateTime    DATETIME2(3) OUTPUT
AS
BEGIN
  SET NOCOUNT ON;
  BEGIN TRY
    -- Resolve EquipID
    DECLARE @EquipName NVARCHAR(100);
    IF @EquipID IS NULL
    BEGIN
      SELECT @EquipID = e.EquipID, @EquipName = e.EquipName 
      FROM dbo.Equipment e WHERE e.EquipCode = @EquipCode;
      IF @EquipID IS NULL
        THROW 50001, 'Unknown equipment (EquipCode/EquipID).', 1;
    END
    ELSE
    BEGIN
      SELECT @EquipName = e.EquipName 
      FROM dbo.Equipment e WHERE e.EquipID = @EquipID;
      IF @EquipName IS NULL
        THROW 50002, 'Equipment ID exists but EquipName not found', 1;
    END

    -- Get last run window end time
    DECLARE @lastEnd DATETIME2(3);
    SELECT @lastEnd = MAX(r.WindowEndEntryDateTime)
    FROM dbo.Runs r WHERE r.EquipID = @EquipID AND r.Outcome IN ('OK','WARN','FAIL','NOOP');

    IF @lastEnd IS NULL
    BEGIN
      -- First run: Query equipment-specific data table dynamically
      DECLARE @sql NVARCHAR(MAX);
      DECLARE @tableName NVARCHAR(200) = (SELECT EquipCode FROM dbo.Equipment WHERE EquipID = @EquipID) + '_Data';
      DECLARE @minDate DATETIME2(3);
      
      -- Check if equipment data table exists
      IF OBJECT_ID('dbo.' + @tableName, 'U') IS NOT NULL
      BEGIN
        SET @sql = N'SELECT @minDate = MIN(EntryDateTime) FROM dbo.' + QUOTENAME(@tableName);
        EXEC sp_executesql @sql, N'@minDate DATETIME2(3) OUTPUT', @minDate OUTPUT;
        SET @WindowStartEntryDateTime = @minDate;
      END
      
      -- Fallback to DefaultStartUtc or calculated time if no data
      IF @WindowStartEntryDateTime IS NULL 
        SET @WindowStartEntryDateTime = ISNULL(@DefaultStartUtc, DATEADD(MINUTE, -@TickMinutes, SYSUTCDATETIME()));
    END
    ELSE
      SET @WindowStartEntryDateTime = @lastEnd;

    -- Calculate window end time
    SET @WindowEndEntryDateTime = DATEADD(MINUTE, @TickMinutes, @WindowStartEntryDateTime);
    SET @RunID = NEWID();

    -- Insert run record into Runs table (matching actual schema)
    INSERT INTO dbo.Runs (
      RunID, EquipID, Stage, EntryDateTime, EndEntryDateTime,
      WindowStartEntryDateTime, WindowEndEntryDateTime,
      Outcome, Version, ConfigHash, TriggerReason, RowsRead, RowsWritten, ErrorJSON
    )
    VALUES (
      @RunID, @EquipID, @Stage, SYSUTCDATETIME(), NULL,
      @WindowStartEntryDateTime, @WindowEndEntryDateTime,
      'OK', @Version, @ConfigHash, @TriggerReason, NULL, NULL, NULL
    );

  END TRY
  BEGIN CATCH
    THROW;
  END CATCH
END
GO

PRINT 'usp_ACM_StartRun fixed to use equipment-specific data tables';
GO

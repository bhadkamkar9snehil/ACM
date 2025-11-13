/*
 * Script: 51_create_historian_sp_temp.sql
 * Purpose: Create stored procedure to retrieve equipment data by time range
 * Context: SQL-42 - Temporary SP for historian simulation
 * 
 * IMPORTANT: This is named _TEMP to indicate it's a stopgap solution.
 * When moving to production, replace with usp_ACM_GetHistorianData_PROD
 * that connects to the actual historian system.
 * 
 * See docs/SP_MIGRATION_GUIDE.md for all locations to update during migration.
 */

USE ACM;
GO

PRINT 'Creating usp_ACM_GetHistorianData_TEMP stored procedure...';
PRINT '';

IF OBJECT_ID('dbo.usp_ACM_GetHistorianData_TEMP', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ACM_GetHistorianData_TEMP;
GO

CREATE PROCEDURE dbo.usp_ACM_GetHistorianData_TEMP
    @StartTime DATETIME2,
    @EndTime DATETIME2,
    @TagNames NVARCHAR(MAX) = NULL,        -- Comma-separated tag names (NULL = all tags)
    @EquipID INT = NULL,                   -- Equipment ID (alternative to EquipmentName)
    @EquipmentName VARCHAR(50) = NULL      -- Equipment name (alternative to EquipID)
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @ErrorMsg NVARCHAR(500);
    DECLARE @SQL NVARCHAR(MAX);
    DECLARE @TableName VARCHAR(100);
    DECLARE @ColumnList NVARCHAR(MAX);
    DECLARE @WhereClause NVARCHAR(500);
    
    -- =====================================================================
    -- Validate inputs and determine equipment
    -- =====================================================================
    IF @EquipID IS NULL AND @EquipmentName IS NULL
    BEGIN
        RAISERROR('Either @EquipID or @EquipmentName must be provided', 16, 1);
        RETURN;
    END
    
    -- Resolve EquipmentName from EquipID if needed
    IF @EquipmentName IS NULL
    BEGIN
        SELECT @EquipmentName = EquipCode
        FROM dbo.Equipment
        WHERE EquipID = @EquipID;
        
        IF @EquipmentName IS NULL
        BEGIN
            SET @ErrorMsg = 'EquipID ' + CAST(@EquipID AS VARCHAR(10)) + ' not found in Equipment table';
            RAISERROR(@ErrorMsg, 16, 1);
            RETURN;
        END
    END
    ELSE
    BEGIN
        -- Resolve EquipID from EquipmentName if needed
        IF @EquipID IS NULL
        BEGIN
            SELECT @EquipID = EquipID
            FROM dbo.Equipment
            WHERE EquipCode = @EquipmentName OR EquipName = @EquipmentName;
            
            IF @EquipID IS NULL
            BEGIN
                SET @ErrorMsg = 'Equipment ''' + @EquipmentName + ''' not found in Equipment table';
                RAISERROR(@ErrorMsg, 16, 1);
                RETURN;
            END
        END
    END
    
    -- Determine data table name based on equipment
    SET @TableName = @EquipmentName + '_Data';
    
    -- Verify table exists
    IF OBJECT_ID('dbo.' + @TableName, 'U') IS NULL
    BEGIN
        SET @ErrorMsg = 'Data table dbo.' + @TableName + ' does not exist';
        RAISERROR(@ErrorMsg, 16, 1);
        RETURN;
    END
    
    -- =====================================================================
    -- Build column list (validate tags if specified)
    -- =====================================================================
    IF @TagNames IS NULL OR LTRIM(RTRIM(@TagNames)) = ''
    BEGIN
        -- Return all sensor columns (exclude EntryDateTime, audit columns)
        SELECT @ColumnList = STRING_AGG(QUOTENAME(TagName), ', ') WITHIN GROUP (ORDER BY TagName)
        FROM dbo.ACM_TagEquipmentMap
        WHERE EquipID = @EquipID AND IsActive = 1;
        
        IF @ColumnList IS NULL
        BEGIN
            SET @ErrorMsg = 'No active tags found for EquipID ' + CAST(@EquipID AS VARCHAR(10));
            RAISERROR(@ErrorMsg, 16, 1);
            RETURN;
        END
    END
    ELSE
    BEGIN
        -- Parse and validate requested tags
        DECLARE @TagList TABLE (TagName VARCHAR(255));
        DECLARE @InvalidTags NVARCHAR(MAX);
        
        -- Split comma-separated tag names
        INSERT INTO @TagList (TagName)
        SELECT LTRIM(RTRIM(value))
        FROM STRING_SPLIT(@TagNames, ',')
        WHERE LTRIM(RTRIM(value)) <> '';
        
        -- Validate all requested tags exist for this equipment
        SELECT @InvalidTags = STRING_AGG(t.TagName, ', ')
        FROM @TagList t
        LEFT JOIN dbo.ACM_TagEquipmentMap m ON t.TagName = m.TagName AND m.EquipID = @EquipID AND m.IsActive = 1
        WHERE m.TagID IS NULL;
        
        IF @InvalidTags IS NOT NULL
        BEGIN
            SET @ErrorMsg = 'Invalid tags for ' + @EquipmentName + ': ' + @InvalidTags;
            RAISERROR(@ErrorMsg, 16, 1);
            RETURN;
        END
        
        -- Build column list from validated tags
        SELECT @ColumnList = STRING_AGG(QUOTENAME(t.TagName), ', ') WITHIN GROUP (ORDER BY t.TagName)
        FROM @TagList t
        INNER JOIN dbo.ACM_TagEquipmentMap m ON t.TagName = m.TagName AND m.EquipID = @EquipID;
    END
    
    -- =====================================================================
    -- Build WHERE clause
    -- =====================================================================
    SET @WhereClause = 'EntryDateTime >= @StartTime AND EntryDateTime <= @EndTime';
    
    -- =====================================================================
    -- Execute dynamic SQL
    -- =====================================================================
    SET @SQL = N'
        SELECT 
            EntryDateTime,
            ' + @ColumnList + N'
        FROM dbo.' + QUOTENAME(@TableName) + N'
        WHERE ' + @WhereClause + N'
        ORDER BY EntryDateTime ASC;
    ';
    
    -- Uncomment for debugging:
    -- PRINT @SQL;
    
    EXEC sp_executesql 
        @SQL,
        N'@StartTime DATETIME2, @EndTime DATETIME2',
        @StartTime = @StartTime,
        @EndTime = @EndTime;
    
END
GO

PRINT '✓ usp_ACM_GetHistorianData_TEMP created';
PRINT '';
PRINT '========================================';
PRINT 'Stored procedure ready!';
PRINT '';
PRINT 'Usage examples:';
PRINT '';
PRINT '-- Get all FD_FAN data for 15-minute batch';
PRINT 'EXEC usp_ACM_GetHistorianData_TEMP';
PRINT '    @StartTime = ''2012-05-21 14:00:00'',';
PRINT '    @EndTime = ''2012-05-21 14:15:00'',';
PRINT '    @EquipmentName = ''FD_FAN'';';
PRINT '';
PRINT '-- Get specific tags for GAS_TURBINE';
PRINT 'EXEC usp_ACM_GetHistorianData_TEMP';
PRINT '    @StartTime = ''2019-06-01 00:00:00'',';
PRINT '    @EndTime = ''2019-06-01 01:00:00'',';
PRINT '    @EquipID = 2621,';
PRINT '    @TagNames = ''DWATT,B1TEMP1,B2TEMP1'';';
PRINT '';
PRINT 'Next: SQL-43 - Run CSV migration script';
PRINT '========================================';
GO

/*
ACM Equipment Discovery Procedures (XStudio_DOW Integration)
These procedures read equipment metadata from XStudio_DOW database.
Assumptions:
- ACM and XStudio_DOW are on the same SQL Server instance
- ACM has READ access to XStudio_DOW tables
- Equipment types follow naming convention: {Type}_Mst_Tbl, {Type}_Tag_Mapping_Tbl
*/
USE [ACM];
GO

/* Safety drop (idempotent deploy) */
IF OBJECT_ID('dbo.usp_GetEquipmentInstances','P') IS NOT NULL DROP PROCEDURE dbo.usp_GetEquipmentInstances;
IF OBJECT_ID('dbo.usp_GetEquipmentTagMappings','P') IS NOT NULL DROP PROCEDURE dbo.usp_GetEquipmentTagMappings;
IF OBJECT_ID('dbo.usp_SyncEquipmentFromDOW','P') IS NOT NULL DROP PROCEDURE dbo.usp_SyncEquipmentFromDOW;
IF OBJECT_ID('dbo.usp_ListEquipmentTypes','P') IS NOT NULL DROP PROCEDURE dbo.usp_ListEquipmentTypes;
GO

/* List all active equipment types from DOW */
CREATE PROCEDURE dbo.usp_ListEquipmentTypes
AS
BEGIN
    SET NOCOUNT ON;
    SELECT 
        ID AS EquipmentTypeID,
        Name AS EquipmentTypeName,
        Hierarchy,
        BlockType,
        Icon,
        IsBatchingEntity,
        IsEventCheck,
        CreatedOn,
        ModifiedOn
    FROM [XStudio_DOW].[dbo].[Equipment_Type_Mst_Tbl]
    WHERE IsDeleted = 0 AND IsSystem = 0
    ORDER BY Name;
END
GO

/* Get all equipment instances for a given equipment type */
CREATE PROCEDURE dbo.usp_GetEquipmentInstances
    @EquipmentTypeName nvarchar(128)
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Validate equipment type exists
    DECLARE @TypeID int;
    SELECT @TypeID = ID 
    FROM [XStudio_DOW].[dbo].[Equipment_Type_Mst_Tbl]
    WHERE Name = @EquipmentTypeName AND IsDeleted = 0;
    
    IF @TypeID IS NULL
    BEGIN
        RAISERROR('Equipment type "%s" not found in XStudio_DOW', 16, 1, @EquipmentTypeName);
        RETURN;
    END
    
    -- Dynamic query to read from corresponding equipment master table
    DECLARE @sql nvarchar(max);
    DECLARE @tableName sysname = QUOTENAME(@EquipmentTypeName + '_Mst_Tbl');
    
    SET @sql = N'
    SELECT 
        ID AS EquipmentID,
        Name AS EquipmentName,
        EquipmentTypeID,
        AreaID,
        TemplateID,
        AssetIdentificationProperties,
        CreatedBy,
        CreatedOn,
        ModifiedBy,
        ModifiedOn
    FROM [XStudio_DOW].[dbo].' + @tableName + N'
    WHERE IsDeleted = 0 AND EquipmentTypeID = @TypeID
    ORDER BY Name';
    
    EXEC sp_executesql @sql, N'@TypeID int', @TypeID;
END
GO

/* Get tag mappings for a specific equipment instance */
CREATE PROCEDURE dbo.usp_GetEquipmentTagMappings
    @EquipmentTypeName nvarchar(128),
    @EquipmentID int
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Dynamic query to read tag mappings
    DECLARE @sql nvarchar(max);
    DECLARE @tableName sysname = QUOTENAME(@EquipmentTypeName + '_Tag_Mapping_Tbl');
    
    SET @sql = N'
    SELECT 
        ID AS MappingID,
        EquipmentID,
        Attribute,
        TagName,
        InstrumentTag,
        DataSourceID,
        Type,
        IsXBatchTag,
        HHRange,
        HRange,
        LRange,
        LLRange,
        ColorGTHH,
        ColorBWHHH,
        ColorBWHL,
        ColorBWLLL,
        ColorLTLL,
        CreatedOn,
        ModifiedOn
    FROM [XStudio_DOW].[dbo].' + @tableName + N'
    WHERE EquipmentID = @EquipID AND IsDeleted = 0
    ORDER BY Attribute';
    
    EXEC sp_executesql @sql, N'@EquipID int', @EquipmentID;
END
GO

/* Sync equipment instance from DOW to ACM.Equipments table */
CREATE PROCEDURE dbo.usp_SyncEquipmentFromDOW
    @EquipmentTypeName nvarchar(128),
    @EquipmentID_DOW int,
    @EquipID_ACM int OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Get equipment instance details from DOW
    DECLARE @EquipName nvarchar(128);
    DECLARE @sql nvarchar(max);
    DECLARE @ParmDefinition nvarchar(500);
    DECLARE @tableName sysname = QUOTENAME(@EquipmentTypeName + '_Mst_Tbl');
    
    SET @sql = N'
    SELECT @Name = Name 
    FROM [XStudio_DOW].[dbo].' + @tableName + N'
    WHERE ID = @ID AND IsDeleted = 0';
    
    SET @ParmDefinition = N'@ID int, @Name nvarchar(128) OUTPUT';
    
    EXEC sp_executesql @sql, @ParmDefinition, 
         @ID = @EquipmentID_DOW, 
         @Name = @EquipName OUTPUT;
    
    IF @EquipName IS NULL
    BEGIN
        RAISERROR('Equipment ID %d not found in %s', 16, 1, @EquipmentID_DOW, @tableName);
        RETURN;
    END
    
    -- Build EquipCode as Type_Name (e.g., "Pump_PumpA-001")
    DECLARE @EquipCode nvarchar(64);
    SET @EquipCode = @EquipmentTypeName + '_' + @EquipName;
    
    -- Upsert into ACM.Equipments using existing proc
    EXEC dbo.usp_ACM_RegisterEquipment 
        @EquipCode = @EquipCode,
        @ExternalDb = 'XStudio_DOW',
        @Active = 1,
        @EquipID = @EquipID_ACM OUTPUT;
    
    -- Return ACM EquipID and metadata
    SELECT 
        @EquipID_ACM AS EquipID_ACM, 
        @EquipCode AS EquipCode, 
        @EquipName AS EquipName,
        @EquipmentTypeName AS EquipmentType,
        @EquipmentID_DOW AS EquipmentID_DOW;
END
GO

/* Example usage:

-- List all equipment types
EXEC ACM.dbo.usp_ListEquipmentTypes;

-- Get all pump instances
EXEC ACM.dbo.usp_GetEquipmentInstances @EquipmentTypeName = 'Pump';

-- Get tag mappings for a specific pump
EXEC ACM.dbo.usp_GetEquipmentTagMappings 
    @EquipmentTypeName = 'Pump',
    @EquipmentID = 123;

-- Sync a pump from DOW to ACM
DECLARE @acm_id int;
EXEC ACM.dbo.usp_SyncEquipmentFromDOW 
    @EquipmentTypeName = 'Pump',
    @EquipmentID_DOW = 123,
    @EquipID_ACM = @acm_id OUTPUT;
SELECT @acm_id AS ACM_EquipID;

*/

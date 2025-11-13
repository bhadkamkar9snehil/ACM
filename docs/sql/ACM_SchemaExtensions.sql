-- ACM SQL Schema Extensions
-- Missing tables: ACM_SinceWhen, ACM_BaselineBuffer
-- Date: October 30, 2025

-- ========================================
-- ACM_SinceWhen: Alert duration tracking
-- ========================================
-- Purpose: Track when anomaly alert zones were first entered and their duration
-- Used by: output_manager._generate_since_when()
-- Updates: Every run

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_SinceWhen')
BEGIN
    CREATE TABLE dbo.ACM_SinceWhen (
        ID BIGINT IDENTITY(1,1) PRIMARY KEY,
        RunID UNIQUEIDENTIFIER NOT NULL,
        EquipID INT NOT NULL,
        AlertZone VARCHAR(50) NOT NULL,  -- 'ALERT', 'CAUTION', 'GOOD'
        DurationHours FLOAT NOT NULL,
        StartTimestamp DATETIME2(3) NULL,
        RecordCount INT NOT NULL,
        CreatedAt DATETIME2(3) NOT NULL DEFAULT GETUTCDATE(),
        
        -- Indexes for efficient querying
        INDEX IX_SinceWhen_RunID (RunID),
        INDEX IX_SinceWhen_EquipID_CreatedAt (EquipID, CreatedAt DESC),
        INDEX IX_SinceWhen_AlertZone (AlertZone)
    );
    
    PRINT 'Created table: ACM_SinceWhen';
END
ELSE
BEGIN
    PRINT 'Table ACM_SinceWhen already exists';
END
GO

-- ========================================
-- ACM_BaselineBuffer: Rolling baseline data
-- ========================================
-- Purpose: Store rolling window of sensor data for cold-start training
-- Used by: acm_main.py adaptive rolling baseline logic
-- Updates: Continuous append + retention policy (72 hours default)

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_BaselineBuffer')
BEGIN
    CREATE TABLE dbo.ACM_BaselineBuffer (
        ID BIGINT IDENTITY(1,1) PRIMARY KEY,
        EquipID INT NOT NULL,
        Timestamp DATETIME2(3) NOT NULL,
        SensorName VARCHAR(200) NOT NULL,
        SensorValue FLOAT NOT NULL,
        DataQuality FLOAT NULL,  -- 0-100 quality score
        CreatedAt DATETIME2(3) NOT NULL DEFAULT GETUTCDATE(),
        
        -- Clustered index on EquipID + Timestamp for time-series queries
        INDEX IX_BaselineBuffer_EquipID_Timestamp CLUSTERED (EquipID, Timestamp DESC),
        
        -- Nonclustered index for sensor-level queries
        INDEX IX_BaselineBuffer_SensorName (SensorName),
        
        -- Index for retention cleanup
        INDEX IX_BaselineBuffer_CreatedAt (CreatedAt)
    );
    
    PRINT 'Created table: ACM_BaselineBuffer';
END
ELSE
BEGIN
    PRINT 'Table ACM_BaselineBuffer already exists';
END
GO

-- ========================================
-- Verify ACM_RegimeStability exists
-- ========================================
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_RegimeStability')
BEGIN
    PRINT 'Verified: ACM_RegimeStability exists';
    
    -- Check schema
    SELECT 
        c.COLUMN_NAME,
        c.DATA_TYPE,
        c.IS_NULLABLE,
        c.CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS c
    WHERE c.TABLE_NAME = 'ACM_RegimeStability'
    ORDER BY c.ORDINAL_POSITION;
END
ELSE
BEGIN
    PRINT 'ERROR: ACM_RegimeStability does not exist!';
END
GO

-- ========================================
-- Add schema version tracking
-- ========================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_SchemaVersion')
BEGIN
    CREATE TABLE dbo.ACM_SchemaVersion (
        VersionID INT IDENTITY(1,1) PRIMARY KEY,
        VersionNumber VARCHAR(20) NOT NULL,
        Description VARCHAR(500) NULL,
        AppliedAt DATETIME2(3) NOT NULL DEFAULT GETUTCDATE(),
        AppliedBy VARCHAR(100) NOT NULL DEFAULT SYSTEM_USER,
        
        INDEX IX_SchemaVersion_VersionNumber (VersionNumber)
    );
    
    -- Insert initial version
    INSERT INTO dbo.ACM_SchemaVersion (VersionNumber, Description, AppliedBy)
    VALUES ('1.0.0', 'Initial ACM schema with core tables', 'SYSTEM');
    
    PRINT 'Created table: ACM_SchemaVersion';
END
ELSE
BEGIN
    PRINT 'Table ACM_SchemaVersion already exists';
END
GO

-- Insert version record for this migration
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_SchemaVersion')
BEGIN
    IF NOT EXISTS (SELECT * FROM ACM_SchemaVersion WHERE VersionNumber = '1.1.0')
    BEGIN
        INSERT INTO dbo.ACM_SchemaVersion (VersionNumber, Description, AppliedBy)
        VALUES ('1.1.0', 'Added ACM_SinceWhen and ACM_BaselineBuffer tables', SYSTEM_USER);
        
        PRINT 'Schema version updated to 1.1.0';
    END
END
GO

-- ========================================
-- Baseline retention cleanup procedure
-- ========================================
CREATE OR ALTER PROCEDURE dbo.usp_CleanupBaselineBuffer
    @EquipID INT = NULL,
    @RetentionHours INT = 72,
    @MaxRowsPerEquip INT = 100000
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @CutoffTime DATETIME2(3) = DATEADD(HOUR, -@RetentionHours, GETUTCDATE());
    DECLARE @RowsDeleted INT = 0;
    
    -- Time-based cleanup
    DELETE FROM dbo.ACM_BaselineBuffer
    WHERE (@EquipID IS NULL OR EquipID = @EquipID)
        AND CreatedAt < @CutoffTime;
    
    SET @RowsDeleted = @@ROWCOUNT;
    
    -- Row count limit per equipment
    IF @MaxRowsPerEquip > 0
    BEGIN
        ;WITH RankedRows AS (
            SELECT 
                ID,
                ROW_NUMBER() OVER (PARTITION BY EquipID ORDER BY Timestamp DESC) AS RowNum
            FROM dbo.ACM_BaselineBuffer
            WHERE @EquipID IS NULL OR EquipID = @EquipID
        )
        DELETE FROM RankedRows
        WHERE RowNum > @MaxRowsPerEquip;
        
        SET @RowsDeleted = @RowsDeleted + @@ROWCOUNT;
    END
    
    PRINT 'Deleted ' + CAST(@RowsDeleted AS VARCHAR(20)) + ' rows from ACM_BaselineBuffer';
    
    RETURN @RowsDeleted;
END
GO

PRINT '========================================';
PRINT 'ACM Schema Extensions Completed';
PRINT 'Tables created/verified:';
PRINT '  - ACM_SinceWhen';
PRINT '  - ACM_BaselineBuffer';
PRINT '  - ACM_RegimeStability (verified)';
PRINT '  - ACM_SchemaVersion';
PRINT 'Stored procedures:';
PRINT '  - usp_CleanupBaselineBuffer';
PRINT '========================================';

-- Add ModelBytes column to ModelRegistry for binary model storage
USE ACM;
GO

-- Check if ModelBytes column already exists
IF NOT EXISTS (
    SELECT 1 
    FROM sys.columns 
    WHERE object_id = OBJECT_ID('ModelRegistry') 
    AND name = 'ModelBytes'
)
BEGIN
    ALTER TABLE dbo.ModelRegistry
    ADD ModelBytes VARBINARY(MAX) NULL;
    
    PRINT 'Added ModelBytes column to ModelRegistry';
END
ELSE
BEGIN
    PRINT 'ModelBytes column already exists in ModelRegistry';
END
GO

-- Create index for efficient version queries
IF NOT EXISTS (
    SELECT 1 
    FROM sys.indexes 
    WHERE object_id = OBJECT_ID('ModelRegistry') 
    AND name = 'IX_ModelRegistry_EquipID_Version'
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_ModelRegistry_EquipID_Version
    ON dbo.ModelRegistry (EquipID, Version)
    INCLUDE (ModelType, EntryDateTime, ModelBytes);
    
    PRINT 'Created index IX_ModelRegistry_EquipID_Version';
END
ELSE
BEGIN
    PRINT 'Index IX_ModelRegistry_EquipID_Version already exists';
END
GO

PRINT '';
PRINT 'ModelRegistry schema updated for binary model storage';
PRINT 'Columns: ModelType, EquipID, Version, EntryDateTime, ParamsJSON, StatsJSON, RunID, ModelBytes';
GO

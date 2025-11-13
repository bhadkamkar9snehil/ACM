-- Insert all missing equipment records for config_table.csv EquipIDs
USE ACM;
GO

-- EquipID=0: Wildcard/Default (global configs)
IF NOT EXISTS (SELECT 1 FROM dbo.Equipment WHERE EquipID = 0)
BEGIN
    SET IDENTITY_INSERT dbo.Equipment ON;
    
    INSERT INTO dbo.Equipment (EquipID, EquipCode, EquipName, Area, Unit, Status, CommissionDate, CreatedAtUTC)
    VALUES (0, '*', 'Default/Wildcard Config', 'Global', 'All Plants', 1, CAST('2025-01-01' AS DATETIME2), SYSUTCDATETIME());
    
    SET IDENTITY_INSERT dbo.Equipment OFF;
    PRINT 'Inserted equipment: * (EquipID=0) - Wildcard/Default';
END
ELSE
    PRINT 'Equipment * (EquipID=0) already exists';
GO

-- EquipID=6296: Unknown equipment from config_table.csv
IF NOT EXISTS (SELECT 1 FROM dbo.Equipment WHERE EquipID = 6296)
BEGIN
    SET IDENTITY_INSERT dbo.Equipment ON;
    
    INSERT INTO dbo.Equipment (EquipID, EquipCode, EquipName, Area, Unit, Status, CommissionDate, CreatedAtUTC)
    VALUES (6296, 'EQUIP_6296', 'Equipment 6296', 'Unknown', 'Unknown', 1, CAST('2025-01-01' AS DATETIME2), SYSUTCDATETIME());
    
    SET IDENTITY_INSERT dbo.Equipment OFF;
    PRINT 'Inserted equipment: EQUIP_6296 (EquipID=6296)';
END
ELSE
    PRINT 'Equipment EQUIP_6296 (EquipID=6296) already exists';
GO

-- EquipID=8630: Unknown equipment from config_table.csv
IF NOT EXISTS (SELECT 1 FROM dbo.Equipment WHERE EquipID = 8630)
BEGIN
    SET IDENTITY_INSERT dbo.Equipment ON;
    
    INSERT INTO dbo.Equipment (EquipID, EquipCode, EquipName, Area, Unit, Status, CommissionDate, CreatedAtUTC)
    VALUES (8630, 'EQUIP_8630', 'Equipment 8630', 'Unknown', 'Unknown', 1, CAST('2025-01-01' AS DATETIME2), SYSUTCDATETIME());
    
    SET IDENTITY_INSERT dbo.Equipment OFF;
    PRINT 'Inserted equipment: EQUIP_8630 (EquipID=8630)';
END
ELSE
    PRINT 'Equipment EQUIP_8630 (EquipID=8630) already exists';
GO

-- Verify all equipment now exist
PRINT '';
PRINT 'Current Equipment records:';
SELECT EquipID, EquipCode, EquipName FROM dbo.Equipment ORDER BY EquipID;
GO

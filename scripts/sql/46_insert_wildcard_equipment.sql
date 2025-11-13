-- Insert wildcard/default equipment (EquipID=0) for global config parameters
USE ACM;
GO

-- Insert wildcard equipment if it doesn't exist
IF NOT EXISTS (SELECT 1 FROM dbo.Equipment WHERE EquipID = 0)
BEGIN
    SET IDENTITY_INSERT dbo.Equipment ON;
    
    INSERT INTO dbo.Equipment (EquipID, EquipCode, EquipName, Area, Unit, Status, CommissionDate, CreatedAtUTC)
    VALUES (
        0,
        '*',
        'Default/Wildcard Config',
        'Global',
        'All Plants',
        1,  -- Active
        CAST('2025-01-01' AS DATETIME2),
        SYSUTCDATETIME()
    );
    
    SET IDENTITY_INSERT dbo.Equipment OFF;
    PRINT 'Inserted wildcard equipment (EquipID=0) for default config parameters';
END
ELSE
BEGIN
    PRINT 'Wildcard equipment (EquipID=0) already exists';
END
GO

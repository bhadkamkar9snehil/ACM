/*
 * Script: 50_create_tag_equipment_map.sql
 * Purpose: Create mapping table for sensor tags to equipment
 * Context: SQL-41 - Maps sensor columns to equipment for SP routing
 * 
 * This table enables the stored procedure to:
 * 1. Determine which equipment data table to query based on tag names
 * 2. Validate requested tags exist for the equipment
 * 3. Provide metadata about each sensor tag
 */

USE ACM;
GO

PRINT 'Creating ACM_TagEquipmentMap table...';
PRINT '';

IF OBJECT_ID('dbo.ACM_TagEquipmentMap', 'U') IS NOT NULL
    DROP TABLE dbo.ACM_TagEquipmentMap;
GO

CREATE TABLE dbo.ACM_TagEquipmentMap (
    TagID INT IDENTITY(1,1) NOT NULL,
    TagName VARCHAR(255) NOT NULL,           -- Exact column name from data table
    EquipmentName VARCHAR(50) NOT NULL,      -- FD_FAN, GAS_TURBINE, etc.
    EquipID INT NOT NULL,                    -- Links to Equipment table
    TagDescription VARCHAR(500) NULL,        -- Human-readable description
    TagUnit VARCHAR(50) NULL,                -- Measurement unit (optional)
    TagType VARCHAR(50) NULL,                -- temperature, pressure, flow, vibration, etc.
    IsActive BIT DEFAULT 1,                  -- Enable/disable tags
    CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
    UpdatedAt DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_ACM_TagEquipmentMap PRIMARY KEY CLUSTERED (TagID),
    CONSTRAINT FK_TagEquipmentMap_Equipment FOREIGN KEY (EquipID) 
        REFERENCES dbo.Equipment(EquipID),
    CONSTRAINT UQ_TagEquipmentMap_TagEquip UNIQUE (TagName, EquipID)
);

-- Index for SP lookups (by equipment)
CREATE NONCLUSTERED INDEX IX_TagEquipmentMap_Equipment 
    ON dbo.ACM_TagEquipmentMap(EquipID, IsActive)
    INCLUDE (TagName, EquipmentName);

-- Index for tag name lookups
CREATE NONCLUSTERED INDEX IX_TagEquipmentMap_TagName 
    ON dbo.ACM_TagEquipmentMap(TagName, IsActive)
    INCLUDE (EquipmentName, EquipID);

PRINT '✓ ACM_TagEquipmentMap table created';
PRINT '';

-- =====================================================================
-- Populate with FD_FAN tags (EquipID = 1)
-- =====================================================================
PRINT 'Populating FD_FAN tags (EquipID = 1)...';

INSERT INTO dbo.ACM_TagEquipmentMap (TagName, EquipmentName, EquipID, TagDescription, TagType, TagUnit)
VALUES
    ('DEMO.SIM.06G31_1FD Fan Damper Position', 'FD_FAN', 1, 'FD Fan Damper Position', 'position', '%'),
    ('DEMO.SIM.06I03_1FD Fan Motor Current', 'FD_FAN', 1, 'FD Fan Motor Current', 'current', 'A'),
    ('DEMO.SIM.06GP34_1FD Fan Outlet Pressure', 'FD_FAN', 1, 'FD Fan Outlet Pressure', 'pressure', 'bar'),
    ('DEMO.SIM.06T31_1FD Fan Inlet Temperature', 'FD_FAN', 1, 'FD Fan Inlet Temperature', 'temperature', '°C'),
    ('DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'FD_FAN', 1, 'FD Fan Bearing Temperature', 'temperature', '°C'),
    ('DEMO.SIM.06T33-1_1FD Fan Winding Temperature', 'FD_FAN', 1, 'FD Fan Winding Temperature', 'temperature', '°C'),
    ('DEMO.SIM.06T34_1FD Fan Outlet Termperature', 'FD_FAN', 1, 'FD Fan Outlet Temperature', 'temperature', '°C'),
    ('DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 'FD_FAN', 1, 'FD Fan Left Inlet Flow', 'flow', 'm³/h'),
    ('DEMO.SIM.FSAB_1FD Fan Right Inlet Flow', 'FD_FAN', 1, 'FD Fan Right Inlet Flow', 'flow', 'm³/h');

PRINT '   ✓ Inserted 9 FD_FAN tags';
PRINT '';

-- =====================================================================
-- Populate with GAS_TURBINE tags (EquipID = 2621)
-- =====================================================================
PRINT 'Populating GAS_TURBINE tags (EquipID = 2621)...';

INSERT INTO dbo.ACM_TagEquipmentMap (TagName, EquipmentName, EquipID, TagDescription, TagType, TagUnit)
VALUES
    ('DWATT', 'GAS_TURBINE', 2621, 'Power Output', 'power', 'MW'),
    ('B1VIB1', 'GAS_TURBINE', 2621, 'Bearing 1 Vibration 1', 'vibration', 'mm/s'),
    ('B1VIB2', 'GAS_TURBINE', 2621, 'Bearing 1 Vibration 2', 'vibration', 'mm/s'),
    ('B1RADVIBX', 'GAS_TURBINE', 2621, 'Bearing 1 Radial Vibration X', 'vibration', 'mm/s'),
    ('B1RADVIBY', 'GAS_TURBINE', 2621, 'Bearing 1 Radial Vibration Y', 'vibration', 'mm/s'),
    ('B2VIB1', 'GAS_TURBINE', 2621, 'Bearing 2 Vibration 1', 'vibration', 'mm/s'),
    ('B2VIB2', 'GAS_TURBINE', 2621, 'Bearing 2 Vibration 2', 'vibration', 'mm/s'),
    ('B2RADVIBX', 'GAS_TURBINE', 2621, 'Bearing 2 Radial Vibration X', 'vibration', 'mm/s'),
    ('B2RADVIBY', 'GAS_TURBINE', 2621, 'Bearing 2 Radial Vibration Y', 'vibration', 'mm/s'),
    ('TURBAXDISP1', 'GAS_TURBINE', 2621, 'Turbine Axial Displacement 1', 'displacement', 'mm'),
    ('TURBAXDISP2', 'GAS_TURBINE', 2621, 'Turbine Axial Displacement 2', 'displacement', 'mm'),
    ('B1TEMP1', 'GAS_TURBINE', 2621, 'Bearing 1 Temperature', 'temperature', '°C'),
    ('B2TEMP1', 'GAS_TURBINE', 2621, 'Bearing 2 Temperature', 'temperature', '°C'),
    ('ACTTBTEMP1', 'GAS_TURBINE', 2621, 'Active Turbine Blade Temperature', 'temperature', '°C'),
    ('INACTTBTEMP1', 'GAS_TURBINE', 2621, 'Inactive Turbine Blade Temperature', 'temperature', '°C'),
    ('LOTEMP1', 'GAS_TURBINE', 2621, 'Lube Oil Temperature', 'temperature', '°C');

PRINT '   ✓ Inserted 16 GAS_TURBINE tags';
PRINT '';

PRINT '========================================';
PRINT 'ACM_TagEquipmentMap populated!';
PRINT '';
PRINT 'Summary:';
PRINT '  - FD_FAN: 9 tags (EquipID=1)';
PRINT '  - GAS_TURBINE: 16 tags (EquipID=2621)';
PRINT '  - Total: 25 tags';
PRINT '';
PRINT 'Next: SQL-42 - Create usp_ACM_GetHistorianData_TEMP';
PRINT '========================================';
GO

-- Verify the mapping
SELECT 
    EquipmentName,
    COUNT(*) AS TagCount,
    STRING_AGG(TagType, ', ') WITHIN GROUP (ORDER BY TagType) AS TagTypes
FROM dbo.ACM_TagEquipmentMap
WHERE IsActive = 1
GROUP BY EquipmentName, EquipID
ORDER BY EquipmentName;
GO

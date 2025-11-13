-- =============================================
-- ACM_Config Table Creation and Population
-- =============================================
-- This script creates the ACM_Config table for storing
-- equipment-specific configuration parameters in SQL
-- and populates it from configs/config_table.csv
--
-- Usage:
--   sqlcmd -S localhost\B19CL3PCQLSERVER -d ACM -E -i scripts\sql\45_create_acm_config_table.sql
-- =============================================

USE ACM;
GO

-- Drop table if exists (for clean rebuild)
IF OBJECT_ID('dbo.ACM_Config', 'U') IS NOT NULL
BEGIN
    PRINT 'Dropping existing ACM_Config table...';
    DROP TABLE dbo.ACM_Config;
END
GO

-- Create ACM_Config table
CREATE TABLE dbo.ACM_Config (
    ConfigID INT IDENTITY(1,1) NOT NULL,
    EquipID INT NOT NULL,
    ParamPath NVARCHAR(500) NOT NULL,
    ParamValue NVARCHAR(MAX) NOT NULL,
    ValueType VARCHAR(50) NOT NULL,  -- 'int', 'float', 'bool', 'str', 'list', 'dict'
    UpdatedAt DATETIME2(3) NOT NULL DEFAULT GETUTCDATE(),
    UpdatedBy NVARCHAR(100) NULL DEFAULT SYSTEM_USER,
    
    CONSTRAINT PK_ACM_Config PRIMARY KEY (ConfigID),
    CONSTRAINT FK_ACM_Config_Equipment FOREIGN KEY (EquipID) REFERENCES dbo.Equipment(EquipID),
    CONSTRAINT UQ_ACM_Config_Path UNIQUE (EquipID, ParamPath)
);
GO

-- Create index on ParamPath for faster lookups
CREATE NONCLUSTERED INDEX IX_ACM_Config_ParamPath 
ON dbo.ACM_Config(ParamPath)
INCLUDE (ParamValue, ValueType);
GO

PRINT 'ACM_Config table created successfully';
PRINT 'Next step: Run Python script to populate from config_table.csv:';
PRINT '  python scripts\sql\populate_acm_config.py';
GO

/*
 * Script: 49_create_equipment_data_tables.sql
 * Purpose: Create historian simulation tables for FD_FAN and GAS_TURBINE
 * Context: SQL-40 - Stopgap tables until live historian integration
 * 
 * These tables store ALL training + scoring data to simulate batch historian reads.
 * Pipeline will call usp_ACM_GetHistorianData_TEMP with time ranges to fetch batches.
 * 
 * Future: Replace with actual historian SP when moving to production.
 */

USE ACM;
GO

PRINT 'Creating equipment data tables for historian simulation...';
PRINT '';

-- =====================================================================
-- FD_FAN_Data: 9 sensor tags + timestamp
-- =====================================================================
PRINT '1. Creating FD_FAN_Data table...';

IF OBJECT_ID('dbo.FD_FAN_Data', 'U') IS NOT NULL
    DROP TABLE dbo.FD_FAN_Data;
GO

CREATE TABLE dbo.FD_FAN_Data (
    EntryDateTime DATETIME2(0) NOT NULL,  -- Timestamp (from TS column in CSV)
    
    -- 9 sensor tag columns (exact names from CSV for traceability)
    [DEMO.SIM.06G31_1FD Fan Damper Position] FLOAT NULL,
    [DEMO.SIM.06I03_1FD Fan Motor Current] FLOAT NULL,
    [DEMO.SIM.06GP34_1FD Fan Outlet Pressure] FLOAT NULL,
    [DEMO.SIM.06T31_1FD Fan Inlet Temperature] FLOAT NULL,
    [DEMO.SIM.06T32-1_1FD Fan Bearing Temperature] FLOAT NULL,
    [DEMO.SIM.06T33-1_1FD Fan Winding Temperature] FLOAT NULL,
    [DEMO.SIM.06T34_1FD Fan Outlet Termperature] FLOAT NULL,
    [DEMO.SIM.FSAA_1FD Fan Left Inlet Flow] FLOAT NULL,
    [DEMO.SIM.FSAB_1FD Fan Right Inlet Flow] FLOAT NULL,
    
    -- Audit columns
    LoadedAt DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_FD_FAN_Data PRIMARY KEY CLUSTERED (EntryDateTime)
);

-- Index for time-range queries (used by SP)
CREATE NONCLUSTERED INDEX IX_FD_FAN_Data_TimeRange 
    ON dbo.FD_FAN_Data(EntryDateTime ASC);

PRINT '   ✓ FD_FAN_Data created (9 sensor tags)';
PRINT '';

-- =====================================================================
-- GAS_TURBINE_Data: 16 sensor tags + timestamp
-- =====================================================================
PRINT '2. Creating GAS_TURBINE_Data table...';

IF OBJECT_ID('dbo.GAS_TURBINE_Data', 'U') IS NOT NULL
    DROP TABLE dbo.GAS_TURBINE_Data;
GO

CREATE TABLE dbo.GAS_TURBINE_Data (
    EntryDateTime DATETIME2(0) NOT NULL,  -- Timestamp (from Ts column in CSV)
    
    -- 16 sensor tag columns (exact names from CSV)
    DWATT FLOAT NULL,
    B1VIB1 FLOAT NULL,
    B1VIB2 FLOAT NULL,
    B1RADVIBX FLOAT NULL,
    B1RADVIBY FLOAT NULL,
    B2VIB1 FLOAT NULL,
    B2VIB2 FLOAT NULL,
    B2RADVIBX FLOAT NULL,
    B2RADVIBY FLOAT NULL,
    TURBAXDISP1 FLOAT NULL,
    TURBAXDISP2 FLOAT NULL,
    B1TEMP1 FLOAT NULL,
    B2TEMP1 FLOAT NULL,
    ACTTBTEMP1 FLOAT NULL,
    INACTTBTEMP1 FLOAT NULL,
    LOTEMP1 FLOAT NULL,
    
    -- Audit columns
    LoadedAt DATETIME2 DEFAULT GETUTCDATE(),
    
    CONSTRAINT PK_GAS_TURBINE_Data PRIMARY KEY CLUSTERED (EntryDateTime)
);

-- Index for time-range queries
CREATE NONCLUSTERED INDEX IX_GAS_TURBINE_Data_TimeRange 
    ON dbo.GAS_TURBINE_Data(EntryDateTime ASC);

PRINT '   ✓ GAS_TURBINE_Data created (16 sensor tags)';
PRINT '';

PRINT '========================================';
PRINT 'Equipment data tables created!';
PRINT '';
PRINT 'Tables:';
PRINT '  - FD_FAN_Data (9 sensor tags)';
PRINT '  - GAS_TURBINE_Data (16 sensor tags)';
PRINT '';
PRINT 'Next steps:';
PRINT '  - SQL-41: Create ACM_TagEquipmentMap';
PRINT '  - SQL-42: Create usp_ACM_GetHistorianData_TEMP';
PRINT '  - SQL-43: Run migration script to load CSVs';
PRINT '========================================';
GO

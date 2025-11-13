/*
ACM Configuration Tables (tabular config + history)
*/
USE [ACM];
GO

IF OBJECT_ID('dbo.ACM_Config','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_Config (
    EquipID      int NOT NULL,           -- 0 = global defaults; >0 asset-specific
    Category     nvarchar(64) NOT NULL,
    ParamPath    nvarchar(256) NOT NULL,
    ParamValue   nvarchar(4000) NULL,
    ValueType    nvarchar(32) NULL,      -- string|int|float|bool|json
    LastUpdated  datetime2(3) NOT NULL CONSTRAINT DF_ACM_Config_LastUpdated DEFAULT (SYSUTCDATETIME()),
    UpdatedBy    nvarchar(64) NULL,
    ChangeReason nvarchar(256) NULL,
    Version      int NOT NULL CONSTRAINT DF_ACM_Config_Version DEFAULT (1),
    CONSTRAINT PK_ACM_Config PRIMARY KEY (EquipID, ParamPath)
);
END
GO

IF OBJECT_ID('dbo.ACM_ConfigHistory','U') IS NULL
BEGIN
CREATE TABLE dbo.ACM_ConfigHistory (
    HistoryID    bigint IDENTITY(1,1) PRIMARY KEY,
    EquipID      int NOT NULL,
    ParamPath    nvarchar(256) NOT NULL,
    OldValue     nvarchar(4000) NULL,
    NewValue     nvarchar(4000) NULL,
    ValueType    nvarchar(32) NULL,
    ChangedAt    datetime2(3) NOT NULL CONSTRAINT DF_ACM_ConfigHistory_ChangedAt DEFAULT (SYSUTCDATETIME()),
    ChangedBy    nvarchar(64) NULL,
    ChangeReason nvarchar(256) NULL,
    RunID        uniqueidentifier NULL
);
CREATE INDEX IX_ACM_ConfigHist_Equip_Param ON dbo.ACM_ConfigHistory(EquipID, ParamPath, ChangedAt DESC);
END
GO

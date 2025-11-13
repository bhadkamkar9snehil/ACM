/*
ACM Core Tables (aligns with core/data_io.py writers)
*/
USE [ACM];
GO

-- Equipments master (maps EquipCode -> EquipID)
IF OBJECT_ID('dbo.Equipments','U') IS NULL
BEGIN
CREATE TABLE dbo.Equipments (
    EquipID       int IDENTITY(1,1) PRIMARY KEY,
    EquipCode     nvarchar(64) NOT NULL UNIQUE,
    ExternalDb    sysname NULL,
    Active        bit NOT NULL CONSTRAINT DF_Equipments_Active DEFAULT (1),
    CreatedAt     datetime2(3) NOT NULL CONSTRAINT DF_Equipments_CreatedAt DEFAULT (SYSUTCDATETIME())
);
END
GO

-- Run log & scheduling
IF OBJECT_ID('dbo.RunLog','U') IS NULL
BEGIN
CREATE TABLE dbo.RunLog (
    RunID                        uniqueidentifier NOT NULL PRIMARY KEY,
    EquipID                      int NOT NULL REFERENCES dbo.Equipments(EquipID),
    Stage                        nvarchar(32) NOT NULL,
    StartEntryDateTime           datetime2(3) NOT NULL CONSTRAINT DF_RunLog_Start DEFAULT (SYSUTCDATETIME()),
    EndEntryDateTime             datetime2(3) NULL,
    Outcome                      nvarchar(16) NULL,
    RowsRead                     int NULL,
    RowsWritten                  int NULL,
    ErrorJSON                    nvarchar(max) NULL,
    TriggerReason                nvarchar(64) NULL,
    Version                      nvarchar(32) NULL,
    ConfigHash                   nvarchar(64) NULL,
    WindowStartEntryDateTime     datetime2(3) NULL,
    WindowEndEntryDateTime       datetime2(3) NULL
);
CREATE INDEX IX_RunLog_EquipID_Start ON dbo.RunLog(EquipID, StartEntryDateTime DESC);
END
GO

-- ScoresTS (long format)
IF OBJECT_ID('dbo.ScoresTS','U') IS NULL
BEGIN
CREATE TABLE dbo.ScoresTS (
    EntryDateTime   datetime2(3) NOT NULL,
    EquipID         int NOT NULL REFERENCES dbo.Equipments(EquipID),
    Sensor          nvarchar(64) NOT NULL,
    Value           float NULL,
    Source          nvarchar(32) NULL,
    RunID           uniqueidentifier NOT NULL
);
CREATE INDEX IX_Scores_Equip_Time ON dbo.ScoresTS(EquipID, EntryDateTime);
CREATE INDEX IX_Scores_RunID ON dbo.ScoresTS(RunID);
END
GO

-- DriftTS
IF OBJECT_ID('dbo.DriftTS','U') IS NULL
BEGIN
CREATE TABLE dbo.DriftTS (
    EntryDateTime   datetime2(3) NOT NULL,
    EquipID         int NOT NULL REFERENCES dbo.Equipments(EquipID),
    DriftZ          float NOT NULL,
    Method          nvarchar(32) NOT NULL,
    RunID           uniqueidentifier NOT NULL
);
CREATE INDEX IX_Drift_Equip_Time ON dbo.DriftTS(EquipID, EntryDateTime);
CREATE INDEX IX_Drift_RunID ON dbo.DriftTS(RunID);
END
GO

-- AnomalyEvents
IF OBJECT_ID('dbo.AnomalyEvents','U') IS NULL
BEGIN
CREATE TABLE dbo.AnomalyEvents (
    EquipID              int NOT NULL REFERENCES dbo.Equipments(EquipID),
    StartEntryDateTime   datetime2(3) NOT NULL,
    EndEntryDateTime     datetime2(3) NOT NULL,
    Severity             nvarchar(16) NOT NULL,
    Detector             nvarchar(32) NOT NULL,
    Score                float NULL,
    ContributorsJSON     nvarchar(max) NULL,
    RunID                uniqueidentifier NOT NULL
);
CREATE INDEX IX_Anom_Equip_Start ON dbo.AnomalyEvents(EquipID, StartEntryDateTime);
CREATE INDEX IX_Anom_RunID ON dbo.AnomalyEvents(RunID);
END
GO

-- RegimeEpisodes
IF OBJECT_ID('dbo.RegimeEpisodes','U') IS NULL
BEGIN
CREATE TABLE dbo.RegimeEpisodes (
    EquipID              int NOT NULL REFERENCES dbo.Equipments(EquipID),
    StartEntryDateTime   datetime2(3) NOT NULL,
    EndEntryDateTime     datetime2(3) NOT NULL,
    RegimeLabel          nvarchar(32) NOT NULL,
    Confidence           float NULL,
    RunID                uniqueidentifier NOT NULL
);
CREATE INDEX IX_Regime_Equip_Start ON dbo.RegimeEpisodes(EquipID, StartEntryDateTime);
CREATE INDEX IX_Regime_RunID ON dbo.RegimeEpisodes(RunID);
END
GO

-- PCA model metadata
IF OBJECT_ID('dbo.PCA_Model','U') IS NULL
BEGIN
CREATE TABLE dbo.PCA_Model (
    RunID                  uniqueidentifier NOT NULL PRIMARY KEY,
    EquipID                int NOT NULL REFERENCES dbo.Equipments(EquipID),
    EntryDateTime          datetime2(3) NOT NULL,
    NComponents            int NOT NULL,
    TargetVar              nvarchar(max) NULL,      -- JSON: { SPE_P95_train, T2_P95_train }
    VarExplainedJSON       nvarchar(max) NULL,      -- JSON: array of ratios
    ScalingSpecJSON        nvarchar(max) NULL,      -- JSON: scaler + params
    ModelVersion           nvarchar(32) NULL,
    TrainStartEntryDateTime datetime2(3) NULL,
    TrainEndEntryDateTime   datetime2(3) NULL
);
END
GO

-- PCA components (loadings)
IF OBJECT_ID('dbo.PCA_Components','U') IS NULL
BEGIN
CREATE TABLE dbo.PCA_Components (
    RunID          uniqueidentifier NOT NULL,
    EntryDateTime  datetime2(3) NOT NULL,
    ComponentNo    int NOT NULL,
    Sensor         nvarchar(64) NOT NULL,
    Loading        float NOT NULL
);
CREATE INDEX IX_PCAComp_Run ON dbo.PCA_Components(RunID);
END
GO

-- PCA metrics (score window)
IF OBJECT_ID('dbo.PCA_Metrics','U') IS NULL
BEGIN
CREATE TABLE dbo.PCA_Metrics (
    RunID          uniqueidentifier NOT NULL,
    EntryDateTime  datetime2(3) NOT NULL,
    Var90_N        int NULL,
    ReconRMSE      float NULL,
    P95_ReconRMSE  float NULL,
    Notes          nvarchar(max) NULL
);
CREATE INDEX IX_PCAMet_Run ON dbo.PCA_Metrics(RunID);
END
GO

-- RunStats (header KPI for the run)
IF OBJECT_ID('dbo.RunStats','U') IS NULL
BEGIN
CREATE TABLE dbo.RunStats (
    RunID                   uniqueidentifier NOT NULL PRIMARY KEY,
    EquipID                 int NOT NULL REFERENCES dbo.Equipments(EquipID),
    WindowStartEntryDateTime datetime2(3) NOT NULL,
    WindowEndEntryDateTime   datetime2(3) NOT NULL,
    SamplesIn               int NULL,
    SamplesKept             int NULL,
    SensorsKept             int NULL,
    CadenceOKPct            float NULL,
    DriftP95                float NULL,
    ReconRMSE               float NULL,
    AnomalyCount            int NULL
);
END
GO

-- ConfigLog (best-effort snapshot of config hash/JSON used)
IF OBJECT_ID('dbo.ConfigLog','U') IS NULL
BEGIN
CREATE TABLE dbo.ConfigLog (
    RunID          uniqueidentifier NOT NULL PRIMARY KEY,
    EquipID        int NOT NULL REFERENCES dbo.Equipments(EquipID),
    EntryDateTime  datetime2(3) NOT NULL,
    ConfigHash     nvarchar(64) NOT NULL,
    ConfigJSON     nvarchar(max) NOT NULL,
    Active         bit NOT NULL
);
END
GO

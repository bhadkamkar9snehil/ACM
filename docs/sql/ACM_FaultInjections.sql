-- ACM_FaultInjections Table
-- Logs all synthetic fault injections for validation and traceability

CREATE TABLE dbo.ACM_FaultInjections (
    ID INT IDENTITY(1,1) PRIMARY KEY,
    RunID VARCHAR(50) NOT NULL,
    EquipID INT NOT NULL,
    Timestamp DATETIME2 NOT NULL,
    SensorName VARCHAR(255) NOT NULL,
    OperatorType VARCHAR(50) NOT NULL,  -- 'step', 'spike', 'drift', 'stuck-at', 'noise'
    Parameters NVARCHAR(MAX),  -- JSON parameters for injection
    OriginalValue FLOAT NULL,
    InjectedValue FLOAT NULL,
    CreatedAt DATETIME2 DEFAULT GETUTCDATE()
);

-- Indexes for efficient queries
CREATE NONCLUSTERED INDEX IX_FaultInjections_RunID ON dbo.ACM_FaultInjections(RunID);
CREATE NONCLUSTERED INDEX IX_FaultInjections_EquipID ON dbo.ACM_FaultInjections(EquipID);
CREATE NONCLUSTERED INDEX IX_FaultInjections_Timestamp ON dbo.ACM_FaultInjections(Timestamp);
CREATE NONCLUSTERED INDEX IX_FaultInjections_SensorName ON dbo.ACM_FaultInjections(SensorName);
CREATE NONCLUSTERED INDEX IX_FaultInjections_OperatorType ON dbo.ACM_FaultInjections(OperatorType);

-- Composite index for common query pattern
CREATE NONCLUSTERED INDEX IX_FaultInjections_RunEquip_Timestamp 
    ON dbo.ACM_FaultInjections(RunID, EquipID, Timestamp);

GO

-- Sample queries

-- Get all injections for a specific run
-- SELECT * FROM dbo.ACM_FaultInjections WHERE RunID = 'run_20240115_120000' ORDER BY Timestamp;

-- Get injections by operator type
-- SELECT OperatorType, COUNT(*) as Count, AVG(InjectedValue - OriginalValue) as AvgChange
-- FROM dbo.ACM_FaultInjections
-- WHERE RunID = 'run_20240115_120000'
-- GROUP BY OperatorType;

-- Get affected sensors
-- SELECT SensorName, OperatorType, COUNT(*) as InjectionCount
-- FROM dbo.ACM_FaultInjections
-- WHERE RunID = 'run_20240115_120000'
-- GROUP BY SensorName, OperatorType
-- ORDER BY InjectionCount DESC;

-- Get time series of injections
-- SELECT Timestamp, SensorName, OperatorType, OriginalValue, InjectedValue
-- FROM dbo.ACM_FaultInjections
-- WHERE RunID = 'run_20240115_120000' AND SensorName = 'Temperature_1'
-- ORDER BY Timestamp;

-- ACM_BacktestResults Table
-- Stores results from historical backtest runs for validation and auto-tuning

CREATE TABLE dbo.ACM_BacktestResults (
    ID INT IDENTITY(1,1) PRIMARY KEY,
    RunID VARCHAR(50) NOT NULL,
    EquipID INT NOT NULL,
    WindowStart DATETIME2 NOT NULL,
    WindowEnd DATETIME2 NOT NULL,
    FPRate FLOAT NOT NULL,  -- False positives per hour
    LatencySeconds FLOAT NOT NULL,  -- Runtime duration
    CoveragePct FLOAT NOT NULL,  -- % of sensors evaluated
    DetectionRate FLOAT NULL,  -- % of known defects detected (if ground truth available)
    AlertDurationHours FLOAT NOT NULL DEFAULT 0.0,  -- Time spent in alert zones
    HealthFinal VARCHAR(50) NOT NULL DEFAULT 'UNKNOWN',
    TotalSensors INT NOT NULL DEFAULT 0,
    SensorsEvaluated INT NOT NULL DEFAULT 0,
    EpisodesDetected INT NOT NULL DEFAULT 0,
    MetricsJSON NVARCHAR(MAX) NULL,  -- Additional metrics as JSON
    CreatedAt DATETIME2 DEFAULT GETUTCDATE()
);

-- Indexes for efficient queries
CREATE NONCLUSTERED INDEX IX_BacktestResults_RunID ON dbo.ACM_BacktestResults(RunID);
CREATE NONCLUSTERED INDEX IX_BacktestResults_EquipID ON dbo.ACM_BacktestResults(EquipID);
CREATE NONCLUSTERED INDEX IX_BacktestResults_WindowStart ON dbo.ACM_BacktestResults(WindowStart);
CREATE NONCLUSTERED INDEX IX_BacktestResults_WindowEnd ON dbo.ACM_BacktestResults(WindowEnd);

-- Composite index for common query pattern
CREATE NONCLUSTERED INDEX IX_BacktestResults_EquipID_Window 
    ON dbo.ACM_BacktestResults(EquipID, WindowStart, WindowEnd);

GO

-- Sample queries

-- Get backtest summary for equipment
SELECT 
    EquipID,
    COUNT(*) as TotalWindows,
    AVG(FPRate) as AvgFPRate,
    MIN(FPRate) as MinFPRate,
    MAX(FPRate) as MaxFPRate,
    AVG(LatencySeconds) as AvgLatency,
    AVG(CoveragePct) as AvgCoverage
FROM dbo.ACM_BacktestResults
WHERE EquipID = 101
GROUP BY EquipID;

-- Get time series of FP rates
SELECT 
    WindowStart,
    WindowEnd,
    FPRate,
    LatencySeconds,
    CoveragePct
FROM dbo.ACM_BacktestResults
WHERE EquipID = 101
ORDER BY WindowStart;

-- Find windows with high FP rates
SELECT TOP 10
    RunID,
    WindowStart,
    WindowEnd,
    FPRate,
    EpisodesDetected,
    HealthFinal
FROM dbo.ACM_BacktestResults
WHERE EquipID = 101 AND FPRate > 1.0
ORDER BY FPRate DESC;

-- Get recent backtest performance trend
SELECT 
    CAST(WindowStart AS DATE) as BacktestDate,
    COUNT(*) as WindowCount,
    AVG(FPRate) as AvgFPRate,
    AVG(LatencySeconds) as AvgLatency,
    AVG(CoveragePct) as AvgCoverage
FROM dbo.ACM_BacktestResults
WHERE EquipID = 101 AND WindowStart >= DATEADD(day, -30, GETUTCDATE())
GROUP BY CAST(WindowStart AS DATE)
ORDER BY BacktestDate DESC;

-- Compare performance before/after tuning changes
WITH Periods AS (
    SELECT 
        CASE 
            WHEN WindowStart < '2024-01-15' THEN 'Before'
            ELSE 'After'
        END as Period,
        FPRate,
        LatencySeconds,
        CoveragePct
    FROM dbo.ACM_BacktestResults
    WHERE EquipID = 101
)
SELECT 
    Period,
    COUNT(*) as Windows,
    AVG(FPRate) as AvgFPRate,
    STDEV(FPRate) as StdFPRate,
    AVG(LatencySeconds) as AvgLatency,
    AVG(CoveragePct) as AvgCoverage
FROM Periods
GROUP BY Period;

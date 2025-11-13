/*
ACM Views for common analytics consumption
*/
USE [ACM];
GO

IF OBJECT_ID('dbo.vw_AnomalyEvents','V') IS NOT NULL DROP VIEW dbo.vw_AnomalyEvents;
GO
CREATE VIEW dbo.vw_AnomalyEvents AS
SELECT 
    e.RunID,
    e.EquipID,
    eq.EquipCode,
    e.StartEntryDateTime,
    e.EndEntryDateTime,
    e.Severity,
    e.Detector,
    e.Score,
    e.ContributorsJSON
FROM dbo.AnomalyEvents e
JOIN dbo.Equipments eq ON e.EquipID = eq.EquipID;
GO

IF OBJECT_ID('dbo.vw_Scores','V') IS NOT NULL DROP VIEW dbo.vw_Scores;
GO
/* Pass-through view with EquipCode join for convenience */
CREATE VIEW dbo.vw_Scores AS
SELECT s.RunID, s.EquipID, eq.EquipCode, s.EntryDateTime, s.Sensor, s.Value, s.Source
FROM dbo.ScoresTS s
JOIN dbo.Equipments eq ON s.EquipID = eq.EquipID;
GO

IF OBJECT_ID('dbo.vw_RunSummary','V') IS NOT NULL DROP VIEW dbo.vw_RunSummary;
GO
CREATE VIEW dbo.vw_RunSummary AS
SELECT r.RunID, r.EquipID, eq.EquipCode, r.Stage, r.StartEntryDateTime, r.EndEntryDateTime, r.Outcome,
       r.RowsRead, r.RowsWritten, r.ConfigHash,
       r.WindowStartEntryDateTime, r.WindowEndEntryDateTime
FROM dbo.RunLog r
JOIN dbo.Equipments eq ON r.EquipID = eq.EquipID;
GO

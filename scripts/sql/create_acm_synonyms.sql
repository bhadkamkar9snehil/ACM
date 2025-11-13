-- ==============================================================================
-- ACM Table Synonyms
-- Purpose: Create synonyms for existing tables to match ACM_* naming convention
-- ==============================================================================

USE ACM;
GO

-- Drop existing synonyms if they exist
IF EXISTS (SELECT * FROM sys.synonyms WHERE name = 'ACM_Scores_Long')
    DROP SYNONYM dbo.ACM_Scores_Long;
IF EXISTS (SELECT * FROM sys.synonyms WHERE name = 'ACM_Drift_TS')
    DROP SYNONYM dbo.ACM_Drift_TS;
IF EXISTS (SELECT * FROM sys.synonyms WHERE name = 'ACM_Anomaly_Events')
    DROP SYNONYM dbo.ACM_Anomaly_Events;
IF EXISTS (SELECT * FROM sys.synonyms WHERE name = 'ACM_Regime_Episodes')
    DROP SYNONYM dbo.ACM_Regime_Episodes;
IF EXISTS (SELECT * FROM sys.synonyms WHERE name = 'ACM_PCA_Models')
    DROP SYNONYM dbo.ACM_PCA_Models;
IF EXISTS (SELECT * FROM sys.synonyms WHERE name = 'ACM_PCA_Loadings')
    DROP SYNONYM dbo.ACM_PCA_Loadings;
IF EXISTS (SELECT * FROM sys.synonyms WHERE name = 'ACM_PCA_Metrics')
    DROP SYNONYM dbo.ACM_PCA_Metrics;
IF EXISTS (SELECT * FROM sys.synonyms WHERE name = 'ACM_Run_Stats')
    DROP SYNONYM dbo.ACM_Run_Stats;
GO

-- Create synonyms
CREATE SYNONYM dbo.ACM_Scores_Long FOR dbo.ScoresTS;
CREATE SYNONYM dbo.ACM_Drift_TS FOR dbo.DriftTS;
CREATE SYNONYM dbo.ACM_Anomaly_Events FOR dbo.AnomalyEvents;
CREATE SYNONYM dbo.ACM_Regime_Episodes FOR dbo.RegimeEpisodes;
CREATE SYNONYM dbo.ACM_PCA_Models FOR dbo.PCA_Model;
CREATE SYNONYM dbo.ACM_PCA_Loadings FOR dbo.PCA_Components;
CREATE SYNONYM dbo.ACM_PCA_Metrics FOR dbo.PCA_Metrics;
CREATE SYNONYM dbo.ACM_Run_Stats FOR dbo.RunStats;
GO

PRINT 'Created synonyms:';
SELECT name, base_object_name 
FROM sys.synonyms 
WHERE name LIKE 'ACM_%'
ORDER BY name;
GO

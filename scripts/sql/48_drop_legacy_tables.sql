/*
 * Script: 48_drop_legacy_tables.sql
 * Purpose: Remove unused legacy tables (non-ACM prefix) that have zero rows
 * Context: After SQL integration, ACM_* tables are the authoritative schema
 * 
 * Tables dropped: 18 legacy tables never written by current pipeline
 * Tables kept: 30 ACM_* tables + Equipment + ModelRegistry + Runs
 * 
 * CAUTION: This is destructive. Verify no external processes use these tables.
 * Run TABLE_AUDIT.md analysis first to confirm zero usage.
 */

USE ACM;
GO

PRINT 'Starting legacy table cleanup...';
PRINT 'Dropping 18 unused tables without ACM_ prefix';
PRINT '';

-- Time-series tables (replaced by ACM_* equivalents)
PRINT '1. Dropping time-series tables...';
DROP TABLE IF EXISTS dbo.ScoresTS;
DROP TABLE IF EXISTS dbo.DriftTS;
DROP TABLE IF EXISTS dbo.PCA_ScoresTS;
DROP TABLE IF EXISTS dbo.DataQualityTS;
DROP TABLE IF EXISTS dbo.ForecastResidualsTS;
PRINT '   ✓ Dropped 5 time-series tables';
PRINT '';

-- Event tables (replaced by ACM_Episodes and ACM_RegimeTimeline)
PRINT '2. Dropping event tables...';
DROP TABLE IF EXISTS dbo.AnomalyEvents;
DROP TABLE IF EXISTS dbo.AnomalyTopSpikes;
DROP TABLE IF EXISTS dbo.RegimeEpisodes;
PRINT '   ✓ Dropped 3 event tables';
PRINT '';

-- PCA tables (not used by current pipeline)
PRINT '3. Dropping PCA tables...';
DROP TABLE IF EXISTS dbo.PCA_Model;
DROP TABLE IF EXISTS dbo.PCA_Components;
DROP TABLE IF EXISTS dbo.PCA_Metrics;
PRINT '   ✓ Dropped 3 PCA tables';
PRINT '';

-- Summary tables (not used)
PRINT '4. Dropping summary/analytics tables...';
DROP TABLE IF EXISTS dbo.DriftSummary;
DROP TABLE IF EXISTS dbo.XCorrTopPairs;
DROP TABLE IF EXISTS dbo.FeatureImportance;
DROP TABLE IF EXISTS dbo.CPD_Points;
PRINT '   ✓ Dropped 4 summary tables';
PRINT '';

-- Metadata tables (not used)
PRINT '5. Dropping metadata tables...';
DROP TABLE IF EXISTS dbo.RunStats;
DROP TABLE IF EXISTS dbo.ConfigLog;
DROP TABLE IF EXISTS dbo.Historian;
PRINT '   ✓ Dropped 3 metadata tables';
PRINT '';

-- Verify final table count
DECLARE @TableCount INT;
SELECT @TableCount = COUNT(*) FROM sys.tables;

PRINT '========================================';
PRINT 'Cleanup complete!';
PRINT CONCAT('Remaining tables: ', @TableCount);
PRINT 'Expected: 33 tables (30 ACM_* + Equipment + ModelRegistry + Runs)';
PRINT '';
PRINT 'Tables kept:';
PRINT '  - 30 ACM_* tables (active pipeline output)';
PRINT '  - Equipment (equipment registry)';
PRINT '  - ModelRegistry (model persistence)';
PRINT '  - Runs (run metadata - needs schema fix per SQL-30)';
PRINT '';
PRINT 'See docs/TABLE_AUDIT.md for full analysis';
PRINT '========================================';
GO

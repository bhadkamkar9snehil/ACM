-- scripts/sql/migrations/v11/013_acm_active_models_quality_metric.sql
-- ACM v11.15.10 - Add missing lifecycle metric columns to ACM_ActiveModels
--
-- Background:
-- Python writes SilhouetteScore, StabilityRatio, TrainingRows, TrainingDays,
-- ConsecutiveRuns, TotalRuns, ForecastMAPE, ForecastRMSE, CreatedAt, and
-- RegimeQualityMetric via get_active_model_dict() -> write_active_models().
-- However, ACM_ActiveModels was created without these columns.
-- SqlWriteEngine.project_insert_columns() silently drops columns not present
-- in the SQL table, so write_active_models() returned rows_inserted=1 (success)
-- while all lifecycle metric data was silently discarded. Promotion checks then
-- read zeros/nulls back, permanently blocking LEARNING->CONVERGED.
--
-- Also adds RegimeQualityMetric which was never persisted at all, causing
-- BIC-based regime equipment to be evaluated against a silhouette threshold.
--
-- Safe to run on any DB state: each ALTER is guarded by IF NOT EXISTS.

USE ACM;
GO

SET NOCOUNT ON;

DECLARE @cols TABLE (
    ColName NVARCHAR(128) NOT NULL,
    ColDef  NVARCHAR(256) NOT NULL
);

INSERT INTO @cols (ColName, ColDef) VALUES
    ('SilhouetteScore',    'FLOAT NULL'),
    ('StabilityRatio',     'FLOAT NULL'),
    ('TrainingRows',       'INT NULL'),
    ('TrainingDays',       'FLOAT NULL'),
    ('ConsecutiveRuns',    'INT NOT NULL DEFAULT 0'),
    ('TotalRuns',          'INT NOT NULL DEFAULT 0'),
    ('ForecastMAPE',       'FLOAT NULL'),
    ('ForecastRMSE',       'FLOAT NULL'),
    ('CreatedAt',          'DATETIME2 NULL'),
    ('RegimeQualityMetric','NVARCHAR(30) NULL');

DECLARE @col NVARCHAR(128);
DECLARE @def NVARCHAR(256);
DECLARE @sql NVARCHAR(512);

DECLARE col_cursor CURSOR LOCAL FAST_FORWARD FOR
    SELECT ColName, ColDef FROM @cols;

OPEN col_cursor;
FETCH NEXT FROM col_cursor INTO @col, @def;

WHILE @@FETCH_STATUS = 0
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM sys.columns
        WHERE object_id = OBJECT_ID('dbo.ACM_ActiveModels')
          AND name = @col
    )
    BEGIN
        SET @sql = N'ALTER TABLE dbo.ACM_ActiveModels ADD ['
                 + @col + N'] ' + @def + N';';
        EXEC sp_executesql @sql;
        PRINT 'Added column: ' + @col;
    END
    ELSE
    BEGIN
        PRINT 'Column already exists (skipped): ' + @col;
    END

    FETCH NEXT FROM col_cursor INTO @col, @def;
END

CLOSE col_cursor;
DEALLOCATE col_cursor;
GO

PRINT 'Migration 013 complete.';
GO

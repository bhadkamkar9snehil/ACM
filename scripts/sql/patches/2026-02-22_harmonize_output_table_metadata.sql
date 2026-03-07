-- ============================================================================
-- ACM Output Metadata Harmonization Patch
-- Date: 2026-02-22
-- Purpose:
--   1) Ensure ALLOWED_TABLES expose join and lineage metadata columns:
--      - RunID (UNIQUEIDENTIFIER)
--      - EquipID (INT)
--      - CreatedAt (DATETIME2(3))
--   2) Add supporting indexes for common joins/lookups.
--
-- Notes:
--   - Columns are added only when missing.
--   - Added columns are nullable for backward compatibility with legacy rows.
--   - CreatedAt gets a default constraint for new inserts.
-- ============================================================================

SET NOCOUNT ON;

DECLARE @tables TABLE (TableName SYSNAME PRIMARY KEY);

INSERT INTO @tables (TableName)
VALUES
    ('ACM_HealthTimeline'),
    ('ACM_Scores_Wide'),
    ('ACM_Episodes'),
    ('ACM_RegimeTimeline'),
    ('ACM_SensorDefects'),
    ('ACM_SensorHotspots'),
    ('ACM_RUL'),
    ('ACM_HealthForecast'),
    ('ACM_FailureForecast'),
    ('ACM_SensorForecast'),
    ('ACM_MultivariateForecast'),
    ('ACM_EpisodeCulprits'),
    ('ACM_EpisodeDiagnostics'),
    ('ACM_DetectorCorrelation'),
    ('ACM_DriftSeries'),
    ('ACM_SensorCorrelations'),
    ('ACM_FeatureDropLog'),
    ('ACM_OMR_Diagnostics'),
    ('ACM_BaselineBuffer'),
    ('ACM_HistorianData'),
    ('ACM_SensorNormalized_TS'),
    ('ACM_DataQuality'),
    ('ACM_ForecastingState'),
    ('ACM_CalibrationSummary'),
    ('ACM_AdaptiveConfig'),
    ('ACM_RefitRequests'),
    ('ACM_PCA_Metrics'),
    ('ACM_RunMetadata'),
    ('ACM_Runs'),
    ('ACM_RunLogs'),
    ('ACM_RunMetrics'),
    ('ACM_Run_Stats'),
    ('ACM_Config'),
    ('ACM_ConfigHistory'),
    ('ACM_RegimeOccupancy'),
    ('ACM_RegimeTransitions'),
    ('ACM_Regime_Episodes'),
    ('ACM_RegimePromotionLog'),
    ('ACM_RegimeState'),
    ('ACM_ContributionTimeline'),
    ('ACM_DriftController'),
    ('ACM_PCA_Models'),
    ('ACM_PCA_Loadings'),
    ('ACM_Anomaly_Events'),
    ('ACM_RegimeDefinitions'),
    ('ACM_ActiveModels'),
    ('ACM_DataContractValidation'),
    ('ACM_SeasonalPatterns');

DECLARE @t SYSNAME;
DECLARE @obj_name NVARCHAR(300);
DECLARE @tbl_ddl NVARCHAR(300);
DECLARE @idx_equip NVARCHAR(260);
DECLARE @idx_run NVARCHAR(260);
DECLARE @idx_created NVARCHAR(260);
DECLARE @df_created NVARCHAR(260);
DECLARE @sql NVARCHAR(MAX);

DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
    SELECT TableName FROM @tables ORDER BY TableName;

OPEN cur;
FETCH NEXT FROM cur INTO @t;

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @obj_name = N'dbo.' + @t;
    SET @tbl_ddl = N'dbo.[' + REPLACE(@t, N']', N']]') + N']';
    SET @idx_equip = N'IX_' + @t + N'_EquipID';
    SET @idx_run = N'IX_' + @t + N'_RunID';
    SET @idx_created = N'IX_' + @t + N'_CreatedAt';
    SET @df_created = N'DF_' + @t + N'_CreatedAt_Metadata';

    IF OBJECT_ID(@obj_name, N'U') IS NULL
    BEGIN
        PRINT 'SKIP (missing table): ' + @t;
        FETCH NEXT FROM cur INTO @t;
        CONTINUE;
    END;

    IF COL_LENGTH(@obj_name, 'RunID') IS NULL
    BEGIN
        SET @sql = N'ALTER TABLE ' + @tbl_ddl + N' ADD RunID UNIQUEIDENTIFIER NULL;';
        EXEC sp_executesql @sql;
        PRINT 'ADD COLUMN RunID -> ' + @t;
    END;

    IF COL_LENGTH(@obj_name, 'EquipID') IS NULL
    BEGIN
        SET @sql = N'ALTER TABLE ' + @tbl_ddl + N' ADD EquipID INT NULL;';
        EXEC sp_executesql @sql;
        PRINT 'ADD COLUMN EquipID -> ' + @t;
    END;

    IF COL_LENGTH(@obj_name, 'CreatedAt') IS NULL
    BEGIN
        SET @sql = N'ALTER TABLE ' + @tbl_ddl + N' ADD CreatedAt DATETIME2(3) NULL;';
        EXEC sp_executesql @sql;
        PRINT 'ADD COLUMN CreatedAt -> ' + @t;
    END;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.default_constraints dc
        JOIN sys.columns c
            ON c.object_id = dc.parent_object_id
           AND c.column_id = dc.parent_column_id
        WHERE dc.parent_object_id = OBJECT_ID(@obj_name)
          AND c.name = 'CreatedAt'
    )
    BEGIN
        SET @sql = N'ALTER TABLE ' + @tbl_ddl
            + N' ADD CONSTRAINT [' + REPLACE(@df_created, N']', N']]') + N']'
            + N' DEFAULT (SYSUTCDATETIME()) FOR CreatedAt;';
        EXEC sp_executesql @sql;
        PRINT 'ADD DEFAULT CreatedAt -> ' + @t;
    END;

    -- Add pragmatic join/filter indexes when absent.
    IF EXISTS (
        SELECT 1 FROM sys.columns
        WHERE object_id = OBJECT_ID(@obj_name)
          AND name = 'EquipID'
    )
    AND NOT EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(@obj_name)
          AND name = @idx_equip
    )
    BEGIN
        SET @sql = N'CREATE INDEX [' + REPLACE(@idx_equip, N']', N']]') + N']'
            + N' ON ' + @tbl_ddl + N'(EquipID);';
        EXEC sp_executesql @sql;
        PRINT 'ADD INDEX EquipID -> ' + @t;
    END;

    IF EXISTS (
        SELECT 1 FROM sys.columns
        WHERE object_id = OBJECT_ID(@obj_name)
          AND name = 'RunID'
    )
    AND NOT EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(@obj_name)
          AND name = @idx_run
    )
    BEGIN
        SET @sql = N'CREATE INDEX [' + REPLACE(@idx_run, N']', N']]') + N']'
            + N' ON ' + @tbl_ddl + N'(RunID);';
        EXEC sp_executesql @sql;
        PRINT 'ADD INDEX RunID -> ' + @t;
    END;

    IF EXISTS (
        SELECT 1 FROM sys.columns
        WHERE object_id = OBJECT_ID(@obj_name)
          AND name = 'CreatedAt'
    )
    AND NOT EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE object_id = OBJECT_ID(@obj_name)
          AND name = @idx_created
    )
    BEGIN
        SET @sql = N'CREATE INDEX [' + REPLACE(@idx_created, N']', N']]') + N']'
            + N' ON ' + @tbl_ddl + N'(CreatedAt);';
        EXEC sp_executesql @sql;
        PRINT 'ADD INDEX CreatedAt -> ' + @t;
    END;

    FETCH NEXT FROM cur INTO @t;
END;

CLOSE cur;
DEALLOCATE cur;

PRINT 'Metadata harmonization complete.';

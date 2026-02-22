-- ============================================================================
-- ACM Output Metadata Backfill Patch
-- Date: 2026-02-22
-- Purpose:
--   Backfill NULL metadata in ALLOWED_TABLES after harmonization patch.
--   - RunID: set to zero-guid fallback where NULL
--   - EquipID: set to 0 fallback where NULL
--   - CreatedAt: set to Timestamp when available, else SYSUTCDATETIME()
-- ============================================================================

SET NOCOUNT ON;

DECLARE @tables TABLE (TableName SYSNAME PRIMARY KEY);
INSERT INTO @tables (TableName)
VALUES
    ('ACM_HealthTimeline'), ('ACM_Scores_Wide'), ('ACM_Episodes'), ('ACM_RegimeTimeline'), ('ACM_SensorDefects'),
    ('ACM_SensorHotspots'), ('ACM_RUL'), ('ACM_HealthForecast'), ('ACM_FailureForecast'), ('ACM_SensorForecast'),
    ('ACM_MultivariateForecast'), ('ACM_EpisodeCulprits'), ('ACM_EpisodeDiagnostics'), ('ACM_DetectorCorrelation'),
    ('ACM_DriftSeries'), ('ACM_SensorCorrelations'), ('ACM_FeatureDropLog'), ('ACM_OMR_Diagnostics'),
    ('ACM_BaselineBuffer'), ('ACM_HistorianData'), ('ACM_SensorNormalized_TS'), ('ACM_DataQuality'),
    ('ACM_ForecastingState'), ('ACM_CalibrationSummary'), ('ACM_AdaptiveConfig'), ('ACM_RefitRequests'),
    ('ACM_PCA_Metrics'), ('ACM_RunMetadata'), ('ACM_Runs'), ('ACM_RunLogs'), ('ACM_RunMetrics'),
    ('ACM_Run_Stats'), ('ACM_Config'), ('ACM_ConfigHistory'), ('ACM_RegimeOccupancy'), ('ACM_RegimeTransitions'),
    ('ACM_Regime_Episodes'), ('ACM_RegimePromotionLog'), ('ACM_RegimeState'), ('ACM_ContributionTimeline'),
    ('ACM_DriftController'), ('ACM_PCA_Models'), ('ACM_PCA_Loadings'), ('ACM_Anomaly_Events'),
    ('ACM_RegimeDefinitions'), ('ACM_ActiveModels'), ('ACM_DataContractValidation'), ('ACM_SeasonalPatterns');

DECLARE @t SYSNAME;
DECLARE @obj_name NVARCHAR(300);
DECLARE @tbl_ddl NVARCHAR(300);
DECLARE @sql NVARCHAR(MAX);

DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
    SELECT TableName FROM @tables ORDER BY TableName;

OPEN cur;
FETCH NEXT FROM cur INTO @t;

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @obj_name = N'dbo.' + @t;
    SET @tbl_ddl = N'dbo.[' + REPLACE(@t, N']', N']]') + N']';

    IF OBJECT_ID(@obj_name, N'U') IS NULL
    BEGIN
        PRINT 'SKIP (missing table): ' + @t;
        FETCH NEXT FROM cur INTO @t;
        CONTINUE;
    END;

    IF COL_LENGTH(@obj_name, 'RunID') IS NOT NULL
    BEGIN
        SET @sql = N'UPDATE ' + @tbl_ddl + N' SET RunID = ''00000000-0000-0000-0000-000000000000'' WHERE RunID IS NULL;';
        EXEC sp_executesql @sql;
        PRINT 'BACKFILL RunID -> ' + @t;
    END;

    IF COL_LENGTH(@obj_name, 'EquipID') IS NOT NULL
    BEGIN
        SET @sql = N'UPDATE ' + @tbl_ddl + N' SET EquipID = 0 WHERE EquipID IS NULL;';
        EXEC sp_executesql @sql;
        PRINT 'BACKFILL EquipID -> ' + @t;
    END;

    IF COL_LENGTH(@obj_name, 'CreatedAt') IS NOT NULL
    BEGIN
        IF COL_LENGTH(@obj_name, 'Timestamp') IS NOT NULL
        BEGIN
            SET @sql = N'UPDATE ' + @tbl_ddl + N' SET CreatedAt = COALESCE(TRY_CONVERT(DATETIME2(3), [Timestamp]), SYSUTCDATETIME()) WHERE CreatedAt IS NULL;';
            EXEC sp_executesql @sql;
        END
        ELSE
        BEGIN
            SET @sql = N'UPDATE ' + @tbl_ddl + N' SET CreatedAt = SYSUTCDATETIME() WHERE CreatedAt IS NULL;';
            EXEC sp_executesql @sql;
        END;
        PRINT 'BACKFILL CreatedAt -> ' + @t;
    END;

    FETCH NEXT FROM cur INTO @t;
END;

CLOSE cur;
DEALLOCATE cur;

PRINT 'Metadata backfill complete.';

/*
024_drop_acm_forecast_quality_metrics.sql

Purpose:
- Remove legacy ACM_Forecast_QualityMetrics.

Rationale:
- Live database inspection shows 0 rows.
- No active runtime code paths write to or read from this table.
- No Grafana dashboards or SQL views depend on it.
- No SQL object dependencies were found in sys.sql_expression_dependencies.
*/

USE ACM;
GO

IF OBJECT_ID('dbo.ACM_Forecast_QualityMetrics', 'U') IS NOT NULL
BEGIN
    DROP TABLE dbo.ACM_Forecast_QualityMetrics;
    PRINT 'Dropped dbo.ACM_Forecast_QualityMetrics';
END
ELSE
BEGIN
    PRINT 'dbo.ACM_Forecast_QualityMetrics not present; nothing to drop';
END
GO

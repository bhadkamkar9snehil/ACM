/*
023_drop_acm_forecaststate.sql

Purpose:
- Remove legacy ACM_ForecastState after forecasting ownership moved to
  ACM_ForecastingState.

Why this is safe:
- core/state_manager.py persists forecasting continuity in ACM_ForecastingState.
- core/model_persistence.py marks ACM_ForecastState compatibility fields as
  deprecated and unused at runtime.
- Live database inspection shows ACM_ForecastState currently has 0 rows.
*/

USE ACM;
GO

IF OBJECT_ID('dbo.ACM_ForecastState', 'U') IS NOT NULL
BEGIN
    DROP TABLE dbo.ACM_ForecastState;
    PRINT 'Dropped dbo.ACM_ForecastState';
END
ELSE
BEGIN
    PRINT 'dbo.ACM_ForecastState not present; nothing to drop';
END
GO

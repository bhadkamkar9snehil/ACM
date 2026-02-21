---
type: method
id: core.multivariate_forecast.MultivariateSensorForecaster.forecast_var
module: core.multivariate_forecast
source: core/multivariate_forecast.py
line_start: 266
line_end: 366
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.multivariate_forecast.MultivariateSensorForecaster.forecast_var

Defined in: [[modules/core.multivariate_forecast|core.multivariate_forecast]]

Source: `core/multivariate_forecast.py:266`

Kind: `method`

Signature: `forecast_var(self, df: pd.DataFrame, horizon_hours: float, dt_hours: float=1.0)`

Summary: Forecast using Vector Autoregression (VAR) model.

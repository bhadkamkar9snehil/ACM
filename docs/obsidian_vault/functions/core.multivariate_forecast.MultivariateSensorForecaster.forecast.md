---
type: method
id: core.multivariate_forecast.MultivariateSensorForecaster.forecast
module: core.multivariate_forecast
source: core/multivariate_forecast.py
line_start: 442
line_end: 516
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.multivariate_forecast.MultivariateSensorForecaster.forecast

Defined in: [[modules/core.multivariate_forecast|core.multivariate_forecast]]

Source: `core/multivariate_forecast.py:442`

Kind: `method`

Signature: `forecast(self, sensor_names: List[str], horizon_hours: float=168.0, prefer_var: bool=True)`

Summary: Main forecasting method - chooses best available approach.

---
type: method
id: core.multivariate_forecast.MultivariateSensorForecaster.detect_lead_lag_relationships
module: core.multivariate_forecast
source: core/multivariate_forecast.py
line_start: 186
line_end: 264
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.multivariate_forecast.MultivariateSensorForecaster.detect_lead_lag_relationships

Defined in: [[modules/core.multivariate_forecast|core.multivariate_forecast]]

Source: `core/multivariate_forecast.py:186`

Kind: `method`

Signature: `detect_lead_lag_relationships(self, df: pd.DataFrame, max_lag: int=24)`

Summary: Detect lead-lag relationships using cross-correlation (vectorized).

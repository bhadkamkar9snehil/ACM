---
type: function
id: core.metrics.rolling_backtest
module: core.metrics
source: core/metrics.py
line_start: 662
line_end: 810
generated_at: 2026-02-21T06:37:09+00:00
---

# core.metrics.rolling_backtest

Defined in: [[modules/core.metrics|core.metrics]]

Source: `core/metrics.py:662`

Kind: `function`

Signature: `rolling_backtest(health_series: np.ndarray, forecast_model, horizon: int=24, min_train_samples: int=100, step_size: int=1)`

Summary: Perform rolling backtest on forecast model with expanding window.

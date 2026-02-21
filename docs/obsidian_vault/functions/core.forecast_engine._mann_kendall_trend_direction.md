---
type: function
id: core.forecast_engine._mann_kendall_trend_direction
module: core.forecast_engine
source: core/forecast_engine.py
line_start: 90
line_end: 115
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.forecast_engine._mann_kendall_trend_direction

Defined in: [[modules/core.forecast_engine|core.forecast_engine]]

Source: `core/forecast_engine.py:90`

Kind: `function`

Signature: `_mann_kendall_trend_direction(y: np.ndarray, threshold_tau: float=0.1, alpha: float=0.05, positive_label: str='Increasing', negative_label: str='Decreasing', stable_label: str='Stable', unknown_label: str='Unknown')`

Summary: Detect monotonic trend using Mann-Kendall test with explicit labels.

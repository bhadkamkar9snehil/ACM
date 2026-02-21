---
type: method
id: core.degradation_model.LinearTrendModel._compute_cv_error_vectorized
module: core.degradation_model
source: core/degradation_model.py
line_start: 702
line_end: 767
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.degradation_model.LinearTrendModel._compute_cv_error_vectorized

Defined in: [[modules/core.degradation_model|core.degradation_model]]

Source: `core/degradation_model.py:702`

Kind: `method`

Signature: `_compute_cv_error_vectorized(self, health_arr: np.ndarray, alpha: float, beta: float, min_train_size: int, forecast_horizon: int, step_size: int, n: int)`

Summary: Compute CV error using vectorized Holt's filter.

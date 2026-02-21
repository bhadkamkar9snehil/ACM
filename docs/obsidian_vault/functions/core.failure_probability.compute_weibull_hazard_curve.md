---
type: function
id: core.failure_probability.compute_weibull_hazard_curve
module: core.failure_probability
source: core/failure_probability.py
line_start: 550
line_end: 600
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.failure_probability.compute_weibull_hazard_curve

Defined in: [[modules/core.failure_probability|core.failure_probability]]

Source: `core/failure_probability.py:550`

Kind: `function`

Signature: `compute_weibull_hazard_curve(health_forecast: np.ndarray, failure_threshold: float=70.0, dt_hours: float=1.0, weibull_shape: float=2.0, weibull_scale: float=168.0)`

Summary: Compute hazard/survival curves using proper Weibull model.

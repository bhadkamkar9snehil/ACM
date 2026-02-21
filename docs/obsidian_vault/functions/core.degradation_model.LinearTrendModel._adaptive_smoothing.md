---
type: method
id: core.degradation_model.LinearTrendModel._adaptive_smoothing
module: core.degradation_model
source: core/degradation_model.py
line_start: 648
line_end: 700
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.degradation_model.LinearTrendModel._adaptive_smoothing

Defined in: [[modules/core.degradation_model|core.degradation_model]]

Source: `core/degradation_model.py:648`

Kind: `method`

Signature: `_adaptive_smoothing(self, health_values: pd.Series)`

Summary: Adaptive alpha/beta tuning via expanding-window time-series cross-validation.

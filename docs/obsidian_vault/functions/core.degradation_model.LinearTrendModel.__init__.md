---
type: method
id: core.degradation_model.LinearTrendModel.__init__
module: core.degradation_model
source: core/degradation_model.py
line_start: 136
line_end: 181
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.degradation_model.LinearTrendModel.__init__

Defined in: [[modules/core.degradation_model|core.degradation_model]]

Source: `core/degradation_model.py:136`

Kind: `method`

Signature: `__init__(self, alpha: float=0.3, beta: float=0.1, max_trend_per_hour: float=5.0, flatline_epsilon: float=0.001, enable_adaptive: bool=True, min_samples_for_adaptive: int=30, max_gap_hours: float=720.0, label: str='global')`

Summary: Initialize Holt's linear trend model.

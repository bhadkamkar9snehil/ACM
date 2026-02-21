---
type: method
id: core.degradation_model.LinearTrendModel.predict
module: core.degradation_model
source: core/degradation_model.py
line_start: 312
line_end: 417
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.degradation_model.LinearTrendModel.predict

Defined in: [[modules/core.degradation_model|core.degradation_model]]

Source: `core/degradation_model.py:312`

Kind: `method`

Signature: `predict(self, steps: int, dt_hours: Optional[float]=None, confidence_level: float=0.95)`

Summary: Generate multi-step ahead forecast with properly widening uncertainty bounds.

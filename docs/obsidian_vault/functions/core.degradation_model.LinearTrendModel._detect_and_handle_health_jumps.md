---
type: method
id: core.degradation_model.LinearTrendModel._detect_and_handle_health_jumps
module: core.degradation_model
source: core/degradation_model.py
line_start: 529
line_end: 621
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.degradation_model.LinearTrendModel._detect_and_handle_health_jumps

Defined in: [[modules/core.degradation_model|core.degradation_model]]

Source: `core/degradation_model.py:529`

Kind: `method`

Signature: `_detect_and_handle_health_jumps(self, health_series: pd.Series, jump_threshold: float=15.0, min_post_jump_samples: int=10)`

Summary: v11.1.4: Detect maintenance resets (sudden health improvements) and reset forecast baseline.

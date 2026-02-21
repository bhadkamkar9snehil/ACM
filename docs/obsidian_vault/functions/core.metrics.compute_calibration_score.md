---
type: function
id: core.metrics.compute_calibration_score
module: core.metrics
source: core/metrics.py
line_start: 544
line_end: 659
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.metrics.compute_calibration_score

Defined in: [[modules/core.metrics|core.metrics]]

Source: `core/metrics.py:544`

Kind: `function`

Signature: `compute_calibration_score(actual: np.ndarray, forecast: np.ndarray, lower_bound: np.ndarray, upper_bound: np.ndarray, coverage_levels: Optional[list]=None)`

Summary: Compute probabilistic calibration score for forecast intervals.

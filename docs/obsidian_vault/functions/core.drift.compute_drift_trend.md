---
type: function
id: core.drift.compute_drift_trend
module: core.drift
source: core/drift.py
line_start: 64
line_end: 131
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.drift.compute_drift_trend

Defined in: [[modules/core.drift|core.drift]]

Source: `core/drift.py:64`

Kind: `function`

Signature: `compute_drift_trend(drift_series: np.ndarray, window: int=20, timestamps=None, min_hours: float=24.0)`

Summary: Compute drift trend as the slope of linear regression over recent points.

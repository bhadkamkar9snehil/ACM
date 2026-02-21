---
type: function
id: core.confidence.compute_rul_confidence
module: core.confidence
source: core/confidence.py
line_start: 376
line_end: 424
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.confidence.compute_rul_confidence

Defined in: [[modules/core.confidence|core.confidence]]

Source: `core/confidence.py:376`

Kind: `function`

Signature: `compute_rul_confidence(p10: float, p50: float, p90: float, maturity_state: str, training_rows: int, training_days: float, drift_z: Optional[float]=None, prediction_horizon_hours: Optional[float]=None)`

Summary: Compute confidence and reliability for RUL estimate.

---
type: function
id: core.confidence.check_rul_reliability
module: core.confidence
source: core/confidence.py
line_start: 196
line_end: 260
generated_at: 2026-02-21T06:37:09+00:00
---

# core.confidence.check_rul_reliability

Defined in: [[modules/core.confidence|core.confidence]]

Source: `core/confidence.py:196`

Kind: `function`

Signature: `check_rul_reliability(maturity_state: str, training_rows: int, training_days: float, health_history_days: float, min_training_rows: int=500, min_training_days: float=7.0, min_health_history_days: float=3.0, drift_z: Optional[float]=None, drift_threshold: float=3.0)`

Summary: Gate RUL predictions based on prerequisites.

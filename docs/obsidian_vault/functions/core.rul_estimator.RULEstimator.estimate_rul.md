---
type: method
id: core.rul_estimator.RULEstimator.estimate_rul
module: core.rul_estimator
source: core/rul_estimator.py
line_start: 109
line_end: 215
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.rul_estimator.RULEstimator.estimate_rul

Defined in: [[modules/core.rul_estimator|core.rul_estimator]]

Source: `core/rul_estimator.py:109`

Kind: `method`

Signature: `estimate_rul(self, current_health: float, dt_hours: float=1.0, max_horizon_hours: float=720.0, regime_transition_matrix: Optional[np.ndarray]=None, regime_degradation_rates: Optional[Dict[int, float]]=None, current_regime: Optional[int]=None)`

Summary: Estimate RUL via Monte Carlo simulation.

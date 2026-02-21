---
type: method
id: core.rul_estimator.RULEstimator._run_monte_carlo_simulations
module: core.rul_estimator
source: core/rul_estimator.py
line_start: 217
line_end: 366
generated_at: 2026-02-21T06:37:09+00:00
---

# core.rul_estimator.RULEstimator._run_monte_carlo_simulations

Defined in: [[modules/core.rul_estimator|core.rul_estimator]]

Source: `core/rul_estimator.py:217`

Kind: `method`

Signature: `_run_monte_carlo_simulations(self, baseline_forecast: np.ndarray, model_std: float, dt_hours: float, max_steps: int, regime_transition_matrix: Optional[np.ndarray]=None, regime_degradation_rates: Optional[Dict[int, float]]=None, current_regime: Optional[int]=None, current_health: Optional[float]=None)`

Summary: Run Monte Carlo simulations with stochastic noise and regime transitions.

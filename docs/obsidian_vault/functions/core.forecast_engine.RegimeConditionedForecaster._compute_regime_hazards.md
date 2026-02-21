---
type: method
id: core.forecast_engine.RegimeConditionedForecaster._compute_regime_hazards
module: core.forecast_engine
source: core/forecast_engine.py
line_start: 2428
line_end: 2513
generated_at: 2026-02-21T06:37:09+00:00
---

# core.forecast_engine.RegimeConditionedForecaster._compute_regime_hazards

Defined in: [[modules/core.forecast_engine|core.forecast_engine]]

Source: `core/forecast_engine.py:2428`

Kind: `method`

Signature: `_compute_regime_hazards(self, current_health: float, degradation_model: RegimeConditionedTrendModel, regime_stats: Dict[int, RegimeStats], max_horizon: float, dt_hours: float, current_drift_z: Optional[float]=None, current_omr_z: Optional[float]=None)`

Summary: Compute hazard rates per regime over forecast horizon.

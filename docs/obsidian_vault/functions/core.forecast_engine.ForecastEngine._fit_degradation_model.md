---
type: method
id: core.forecast_engine.ForecastEngine._fit_degradation_model
module: core.forecast_engine
source: core/forecast_engine.py
line_start: 727
line_end: 783
---

# core.forecast_engine.ForecastEngine._fit_degradation_model

Defined in: [[modules/core.forecast_engine]]

Source: `core/forecast_engine.py:727`

Kind: `method`

Signature: `_fit_degradation_model(self, health_df: pd.DataFrame, forecast_config: Dict[str, Any], state: ForecastingState, regime_series: Optional[pd.Series]=None)`

Summary: Fit degradation model with warm-start from previous state

---
type: function
id: core.model_lifecycle.update_model_state_from_run
module: core.model_lifecycle
source: core/model_lifecycle.py
line_start: 401
line_end: 460
---

# core.model_lifecycle.update_model_state_from_run

Defined in: [[modules/core.model_lifecycle|core.model_lifecycle]]

Source: `core/model_lifecycle.py:401`

Kind: `function`

Signature: `update_model_state_from_run(state: ModelState, run_id: str, run_success: bool, silhouette_score: Optional[float]=None, regime_quality_metric: Optional[str]=None, regime_quality_ok: Optional[bool]=None, stability_ratio: Optional[float]=None, additional_rows: int=0, additional_days: float=0.0, forecast_mape: Optional[float]=None, forecast_rmse: Optional[float]=None)`

Summary: Update model state after a run completes.

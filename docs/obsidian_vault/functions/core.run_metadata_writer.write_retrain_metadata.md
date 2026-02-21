---
type: function
id: core.run_metadata_writer.write_retrain_metadata
module: core.run_metadata_writer
source: core/run_metadata_writer.py
line_start: 325
line_end: 404
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.run_metadata_writer.write_retrain_metadata

Defined in: [[modules/core.run_metadata_writer|core.run_metadata_writer]]

Source: `core/run_metadata_writer.py:325`

Kind: `function`

Signature: `write_retrain_metadata(sql_client, run_id: str, equip_id: int, equip_name: str, retrain_decision: bool, retrain_reason: str, forecast_state_version: int, model_age_batches: Optional[int]=None, forecast_rmse: Optional[float]=None, forecast_mae: Optional[float]=None, forecast_mape: Optional[float]=None)`

Summary: Write forecasting retrain decision + model age + quality metrics to ACM_RunMetadata.

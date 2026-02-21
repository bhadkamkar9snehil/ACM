---
type: function
id: core.run_metadata_writer.finalize_run_with_metadata
module: core.run_metadata_writer
source: core/run_metadata_writer.py
line_start: 528
line_end: 651
generated_at: 2026-02-21T06:37:09+00:00
---

# core.run_metadata_writer.finalize_run_with_metadata

Defined in: [[modules/core.run_metadata_writer|core.run_metadata_writer]]

Source: `core/run_metadata_writer.py:528`

Kind: `function`

Signature: `finalize_run_with_metadata(sql_client: Any, output_manager: Optional[Any], run_id: Optional[str], equip_id: int, equip_name: str, started_at: datetime, outcome: str, rows_read: int, rows_written: int, err_json: Optional[str], frame: Optional[pd.DataFrame]=None, train: Optional[pd.DataFrame]=None, episodes: Optional[pd.DataFrame]=None, meta: Optional[Any]=None, refit_requested: bool=False, config_signature: str='UNKNOWN', per_regime_enabled: bool=False, regime_count: int=0, observability_enabled: bool=False, record_data_quality_fn: Optional[Any]=None, record_run_fn: Optional[Any]=None, record_batch_processed_fn: Optional[Any]=None, record_health_score_fn: Optional[Any]=None, record_error_fn: Optional[Any]=None, logger: Any=Console)`

Summary: Finalize ACM run metadata + status and close SQL/output resources (best-effort).

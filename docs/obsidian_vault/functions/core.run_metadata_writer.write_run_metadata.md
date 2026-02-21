---
type: function
id: core.run_metadata_writer.write_run_metadata
module: core.run_metadata_writer
source: core/run_metadata_writer.py
line_start: 20
line_end: 136
---

# core.run_metadata_writer.write_run_metadata

Defined in: [[modules/core.run_metadata_writer|core.run_metadata_writer]]

Source: `core/run_metadata_writer.py:20`

Kind: `function`

Signature: `write_run_metadata(sql_client, run_id: str, equip_id: int, equip_name: str, started_at: datetime, completed_at: datetime, config_signature: str, train_row_count: int, score_row_count: int, episode_count: int, health_status: str, avg_health_index: float, min_health_index: float, max_fused_z: float, data_quality_score: float, refit_requested: bool, kept_columns: str, error_message: Optional[str]=None)`

Summary: Write run metadata to ACM_Runs table.

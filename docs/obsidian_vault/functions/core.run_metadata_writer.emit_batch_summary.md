---
type: function
id: core.run_metadata_writer.emit_batch_summary
module: core.run_metadata_writer
source: core/run_metadata_writer.py
line_start: 407
line_end: 525
---

# core.run_metadata_writer.emit_batch_summary

Defined in: [[modules/core.run_metadata_writer|core.run_metadata_writer]]

Source: `core/run_metadata_writer.py:407`

Kind: `function`

Signature: `emit_batch_summary(console: Any, equip: str, run_id: Optional[str], win_start: Optional[pd.Timestamp], win_end: Optional[pd.Timestamp], outcome: str, frame: Optional[pd.DataFrame]=None, episodes: Optional[pd.DataFrame]=None, score_out: Optional[Dict[str, Any]]=None, regime_quality_ok: bool=False, model_state: Optional[Any]=None, rows_read: int=0, train: Optional[pd.DataFrame]=None, degradations: Optional[List[str]]=None, refit_requested: bool=False, timer: Optional[Any]=None)`

Summary: Emit consolidated batch summary and timing logs (best-effort).

---
type: function
id: core.fuse.run_fusion_pipeline
module: core.fuse
source: core/fuse.py
line_start: 2589
line_end: 2704
---

# core.fuse.run_fusion_pipeline

Defined in: [[modules/core.fuse]]

Source: `core/fuse.py:2589`

Kind: `function`

Signature: `run_fusion_pipeline(frame: pd.DataFrame, train_frame: Optional[pd.DataFrame], score_data: pd.DataFrame, train_data: Optional[pd.DataFrame], cfg: Optional[Dict[str, Any]], score_regime_labels: Optional[np.ndarray]=None, train_regime_labels: Optional[np.ndarray]=None, output_manager: Optional[Any]=None, previous_weights: Optional[Dict[str, float]]=None, omr_contributions: Optional[pd.DataFrame]=None, equip: str='')`

Summary: Execute complete fusion pipeline: validate → auto-tune → fuse → detect episodes.

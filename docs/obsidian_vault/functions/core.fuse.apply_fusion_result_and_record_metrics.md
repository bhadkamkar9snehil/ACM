---
type: function
id: core.fuse.apply_fusion_result_and_record_metrics
module: core.fuse
source: core/fuse.py
line_start: 2707
line_end: 2737
---

# core.fuse.apply_fusion_result_and_record_metrics

Defined in: [[modules/core.fuse]]

Source: `core/fuse.py:2707`

Kind: `function`

Signature: `apply_fusion_result_and_record_metrics(frame: pd.DataFrame, train_frame: Optional[pd.DataFrame], fusion_result: 'FusionResult', equip: str='', record_detector_scores_fn: Optional[Callable[..., None]]=None, record_episode_fn: Optional[Callable[..., None]]=None)`

Summary: Apply fusion outputs to score/train frames and emit observability metrics.

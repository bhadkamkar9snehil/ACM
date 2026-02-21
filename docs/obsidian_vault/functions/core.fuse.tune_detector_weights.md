---
type: function
id: core.fuse.tune_detector_weights
module: core.fuse
source: core/fuse.py
line_start: 454
line_end: 1010
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.fuse.tune_detector_weights

Defined in: [[modules/core.fuse|core.fuse]]

Source: `core/fuse.py:454`

Kind: `function`

Signature: `tune_detector_weights(streams: Dict[str, np.ndarray], fused: np.ndarray, current_weights: Dict[str, float], cfg: Optional[Dict[str, Any]]=None, episodes_df: Optional[pd.DataFrame]=None, fused_index: Optional[pd.Index]=None)`

Summary: FUSE-07/08/09: Auto-tune detector weights using episode separability metrics.

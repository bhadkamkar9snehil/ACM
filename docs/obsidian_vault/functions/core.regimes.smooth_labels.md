---
type: function
id: core.regimes.smooth_labels
module: core.regimes
source: core/regimes.py
line_start: 2226
line_end: 2395
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.regimes.smooth_labels

Defined in: [[modules/core.regimes|core.regimes]]

Source: `core/regimes.py:2226`

Kind: `function`

Signature: `smooth_labels(labels: np.ndarray, passes: int=1, window: Optional[int]=None, health_map: Optional[Dict[int, str]]=None, preserve_unknown: bool=True, timestamps: Optional[pd.Index]=None, window_seconds: Optional[float]=None)`

Summary: Apply mode-based smoothing to integer labels (VECTORIZED for performance).

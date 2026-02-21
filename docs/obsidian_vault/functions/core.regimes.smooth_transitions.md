---
type: function
id: core.regimes.smooth_transitions
module: core.regimes
source: core/regimes.py
line_start: 2397
line_end: 2510
---

# core.regimes.smooth_transitions

Defined in: [[modules/core.regimes]]

Source: `core/regimes.py:2397`

Kind: `function`

Signature: `smooth_transitions(labels: np.ndarray, timestamps: Optional[pd.Index]=None, *, min_dwell_samples: int=0, min_dwell_seconds: Optional[float]=None, health_map: Optional[Dict[int, str]]=None)`

Summary: Enforce a minimum dwell time for regime labels.

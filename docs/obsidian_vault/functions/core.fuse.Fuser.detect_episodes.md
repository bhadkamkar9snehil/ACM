---
type: method
id: core.fuse.Fuser.detect_episodes
module: core.fuse
source: core/fuse.py
line_start: 1839
line_end: 2191
---

# core.fuse.Fuser.detect_episodes

Defined in: [[modules/core.fuse]]

Source: `core/fuse.py:1839`

Kind: `method`

Signature: `detect_episodes(self, series: pd.Series, streams: Dict[str, np.ndarray], original_features: pd.DataFrame, regime_labels: Optional[np.ndarray]=None, omr_contributions: Optional[pd.DataFrame]=None)`

Summary: CUSUM-like episode builder on z-series.

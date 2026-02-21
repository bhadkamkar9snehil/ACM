---
type: method
id: core.fuse.Fuser.detect_episodes
module: core.fuse
source: core/fuse.py
line_start: 1476
line_end: 1828
---

# core.fuse.Fuser.detect_episodes

Defined in: [[modules/core.fuse|core.fuse]]

Source: `core/fuse.py:1476`

Kind: `method`

Signature: `detect_episodes(self, series: pd.Series, streams: Dict[str, np.ndarray], original_features: pd.DataFrame, regime_labels: Optional[np.ndarray]=None, omr_contributions: Optional[pd.DataFrame]=None)`

Summary: CUSUM-like episode builder on z-series.

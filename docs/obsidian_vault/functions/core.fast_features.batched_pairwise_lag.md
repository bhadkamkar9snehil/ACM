---
type: function
id: core.fast_features.batched_pairwise_lag
module: core.fast_features
source: core/fast_features.py
line_start: 389
line_end: 498
---

# core.fast_features.batched_pairwise_lag

Defined in: [[modules/core.fast_features|core.fast_features]]

Source: `core/fast_features.py:389`

Kind: `function`

Signature: `batched_pairwise_lag(df: pl.DataFrame, max_lag: int=3, cols: Optional[List[str]]=None, window: Optional[int]=None, min_periods: int=1, batch_size: int=100, min_corr: float=0.0, unique_pairs: bool=True)`

Summary: Generate rolling pairwise lag features between column pairs with optional batching and pruning.

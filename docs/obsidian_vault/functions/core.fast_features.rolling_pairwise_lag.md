---
type: function
id: core.fast_features.rolling_pairwise_lag
module: core.fast_features
source: core/fast_features.py
line_start: 322
line_end: 386
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.fast_features.rolling_pairwise_lag

Defined in: [[modules/core.fast_features|core.fast_features]]

Source: `core/fast_features.py:322`

Kind: `function`

Signature: `rolling_pairwise_lag(df: pl.DataFrame, max_lag: int=3, cols: Optional[List[str]]=None, window: Optional[int]=None, min_periods: int=1)`

Summary: Generate rolling pairwise lag features between all ordered column pairs.

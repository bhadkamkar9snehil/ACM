---
type: function
id: core.fast_features.rolling_median
module: core.fast_features
source: core/fast_features.py
line_start: 147
line_end: 156
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.fast_features.rolling_median

Defined in: [[modules/core.fast_features|core.fast_features]]

Source: `core/fast_features.py:147`

Kind: `function`

Signature: `rolling_median(df: pl.DataFrame, window: int, cols: Optional[List[str]]=None, min_periods: int=1)`

Summary: Compute rolling median for specified columns. Requires Polars DataFrame input.

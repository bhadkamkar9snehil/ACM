---
type: function
id: core.fast_features.rolling_mean_std
module: core.fast_features
source: core/fast_features.py
line_start: 174
line_end: 184
generated_at: 2026-02-21T06:37:09+00:00
---

# core.fast_features.rolling_mean_std

Defined in: [[modules/core.fast_features|core.fast_features]]

Source: `core/fast_features.py:174`

Kind: `function`

Signature: `rolling_mean_std(df: pl.DataFrame, window: int, cols: Optional[List[str]]=None, min_periods: int=1)`

Summary: Rolling mean and std per column. Requires Polars DataFrame input.

---
type: function
id: core.fast_features.rolling_skew_kurt
module: core.fast_features
source: core/fast_features.py
line_start: 187
line_end: 202
---

# core.fast_features.rolling_skew_kurt

Defined in: [[modules/core.fast_features]]

Source: `core/fast_features.py:187`

Kind: `function`

Signature: `rolling_skew_kurt(df: pl.DataFrame, window: int, cols: Optional[List[str]]=None, min_periods: int=1, skew_clip: float=100.0, kurt_clip: float=1000.0)`

Summary: Compute rolling skewness and kurtosis per column. Requires Polars DataFrame input.

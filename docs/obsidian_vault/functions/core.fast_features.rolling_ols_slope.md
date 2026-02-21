---
type: function
id: core.fast_features.rolling_ols_slope
module: core.fast_features
source: core/fast_features.py
line_start: 205
line_end: 223
---

# core.fast_features.rolling_ols_slope

Defined in: [[modules/core.fast_features]]

Source: `core/fast_features.py:205`

Kind: `function`

Signature: `rolling_ols_slope(df: pl.DataFrame, window: int, cols: Optional[List[str]]=None, min_periods: int=1)`

Summary: Rolling OLS slope via covariance formula. Requires Polars DataFrame input.

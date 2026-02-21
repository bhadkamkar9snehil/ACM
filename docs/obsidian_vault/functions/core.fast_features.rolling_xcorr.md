---
type: function
id: core.fast_features.rolling_xcorr
module: core.fast_features
source: core/fast_features.py
line_start: 300
line_end: 315
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.fast_features.rolling_xcorr

Defined in: [[modules/core.fast_features|core.fast_features]]

Source: `core/fast_features.py:300`

Kind: `function`

Signature: `rolling_xcorr(df: pl.DataFrame, window: int, target_col: str, ref_cols: Optional[List[str]]=None, min_periods: int=1)`

Summary: Compute rolling cross-correlation between target column and reference columns.

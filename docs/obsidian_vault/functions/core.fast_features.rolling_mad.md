---
type: function
id: core.fast_features.rolling_mad
module: core.fast_features
source: core/fast_features.py
line_start: 159
line_end: 171
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.fast_features.rolling_mad

Defined in: [[modules/core.fast_features|core.fast_features]]

Source: `core/fast_features.py:159`

Kind: `function`

Signature: `rolling_mad(df: pl.DataFrame, window: int, cols: Optional[List[str]]=None, min_periods: int=1)`

Summary: Rolling median absolute deviation (MAD) per column. Requires Polars DataFrame input.

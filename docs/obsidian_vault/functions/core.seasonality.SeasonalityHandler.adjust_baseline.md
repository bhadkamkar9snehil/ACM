---
type: method
id: core.seasonality.SeasonalityHandler.adjust_baseline
module: core.seasonality
source: core/seasonality.py
line_start: 357
line_end: 409
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.seasonality.SeasonalityHandler.adjust_baseline

Defined in: [[modules/core.seasonality|core.seasonality]]

Source: `core/seasonality.py:357`

Kind: `method`

Signature: `adjust_baseline(self, data: pd.DataFrame, sensor_cols: List[str], timestamp_col: str='Timestamp')`

Summary: Adjust data by removing seasonal components (vectorized for performance).

---
type: method
id: core.seasonality.SeasonalityHandler._detect_periodic_pattern
module: core.seasonality
source: core/seasonality.py
line_start: 231
line_end: 311
---

# core.seasonality.SeasonalityHandler._detect_periodic_pattern

Defined in: [[modules/core.seasonality]]

Source: `core/seasonality.py:231`

Kind: `method`

Signature: `_detect_periodic_pattern(self, data: pd.DataFrame, col: str, timestamp_col: str, period_hours: float, pattern_type: PatternType)`

Summary: Detect pattern with specific period using autocorrelation.

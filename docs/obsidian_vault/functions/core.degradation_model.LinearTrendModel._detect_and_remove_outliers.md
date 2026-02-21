---
type: method
id: core.degradation_model.LinearTrendModel._detect_and_remove_outliers
module: core.degradation_model
source: core/degradation_model.py
line_start: 487
line_end: 527
---

# core.degradation_model.LinearTrendModel._detect_and_remove_outliers

Defined in: [[modules/core.degradation_model|core.degradation_model]]

Source: `core/degradation_model.py:487`

Kind: `method`

Signature: `_detect_and_remove_outliers(self, series: pd.Series, n_std: float=3.0)`

Summary: Detect and remove outliers using ROBUST statistics (median/MAD).

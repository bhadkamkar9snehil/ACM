---
type: method
id: core.degradation_model.LinearTrendModel._detect_and_handle_data_gaps
module: core.degradation_model
source: core/degradation_model.py
line_start: 623
line_end: 646
---

# core.degradation_model.LinearTrendModel._detect_and_handle_data_gaps

Defined in: [[modules/core.degradation_model]]

Source: `core/degradation_model.py:623`

Kind: `method`

Signature: `_detect_and_handle_data_gaps(self, health_series: pd.Series)`

Summary: v11.9.1: Detect large data gaps and use only post-gap data for fitting.

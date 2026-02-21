---
type: method
id: core.smart_coldstart.SmartColdstart.calculate_optimal_window
module: core.smart_coldstart
source: core/smart_coldstart.py
line_start: 241
line_end: 318
generated_at: 2026-02-21T06:37:09+00:00
---

# core.smart_coldstart.SmartColdstart.calculate_optimal_window

Defined in: [[modules/core.smart_coldstart|core.smart_coldstart]]

Source: `core/smart_coldstart.py:241`

Kind: `method`

Signature: `calculate_optimal_window(self, current_window_end: datetime, required_rows: int=500, data_cadence_seconds: Optional[int]=None, expansion_factor: float=1.0)`

Summary: Calculate optimal lookback window to get required_rows of data.

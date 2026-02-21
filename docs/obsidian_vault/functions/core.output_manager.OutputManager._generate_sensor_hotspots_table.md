---
type: method
id: core.output_manager.OutputManager._generate_sensor_hotspots_table
module: core.output_manager
source: core/output_manager.py
line_start: 3402
line_end: 3417
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.output_manager.OutputManager._generate_sensor_hotspots_table

Defined in: [[modules/core.output_manager|core.output_manager]]

Source: `core/output_manager.py:3402`

Kind: `method`

Signature: `_generate_sensor_hotspots_table(self, sensor_zscores: pd.DataFrame, sensor_values: pd.DataFrame, train_mean: Optional[pd.Series], train_std: Optional[pd.Series], warn_z: float, alert_z: float, top_n: int)`

Summary: Backward compat wrapper - delegates to AnalyticsBuilder.

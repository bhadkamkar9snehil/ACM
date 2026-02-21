---
type: method
id: core.analytics_builder.AnalyticsBuilder.generate_sensor_hotspots
module: core.analytics_builder
source: core/analytics_builder.py
line_start: 529
line_end: 625
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.analytics_builder.AnalyticsBuilder.generate_sensor_hotspots

Defined in: [[modules/core.analytics_builder|core.analytics_builder]]

Source: `core/analytics_builder.py:529`

Kind: `method`

Signature: `generate_sensor_hotspots(self, sensor_zscores: pd.DataFrame, sensor_values: pd.DataFrame, train_mean: Optional[pd.Series], train_std: Optional[pd.Series], warn_z: float, alert_z: float, top_n: int, omr_contributions: Optional[pd.DataFrame]=None)`

Summary: Summarize top sensors by peak z-score deviation (vectorized).

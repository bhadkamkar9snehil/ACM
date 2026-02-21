---
type: module
module: core.sensor_attribution
source: core/sensor_attribution.py
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - module
---

# core.sensor_attribution

Source file: `core/sensor_attribution.py`

Summary: Sensor Attribution via Counterfactual Analysis (v11.0.0)

## Imports from core
- [[modules/core.observability|core.observability]]

## Top-level symbols
- [[functions/core.sensor_attribution.DeviationDirection|core.sensor_attribution.DeviationDirection]] (line 53, class)
- [[functions/core.sensor_attribution.SensorStats|core.sensor_attribution.SensorStats]] (line 62, class)
- [[functions/core.sensor_attribution.SensorStats.compute_z_score|core.sensor_attribution.SensorStats.compute_z_score]] (line 69, method)
- [[functions/core.sensor_attribution.SensorContribution|core.sensor_attribution.SensorContribution]] (line 77, class)
- [[functions/core.sensor_attribution.SensorContribution.to_dict|core.sensor_attribution.SensorContribution.to_dict]] (line 93, method)
- [[functions/core.sensor_attribution.AttributionResult|core.sensor_attribution.AttributionResult]] (line 105, class)
- [[functions/core.sensor_attribution.AttributionResult.to_dict|core.sensor_attribution.AttributionResult.to_dict]] (line 121, method)
- [[functions/core.sensor_attribution.AttributionResult.to_sql_row|core.sensor_attribution.AttributionResult.to_sql_row]] (line 131, method)
- [[functions/core.sensor_attribution.BaselineNormalizerProtocol|core.sensor_attribution.BaselineNormalizerProtocol]] (line 146, class)
- [[functions/core.sensor_attribution.BaselineNormalizerProtocol.get_sensor_stats|core.sensor_attribution.BaselineNormalizerProtocol.get_sensor_stats]] (line 149, method)
- [[functions/core.sensor_attribution.BaselineNormalizerProtocol.sensor_names|core.sensor_attribution.BaselineNormalizerProtocol.sensor_names]] (line 154, method)
- [[functions/core.sensor_attribution.UnifiedAttribution|core.sensor_attribution.UnifiedAttribution]] (line 159, class)
- [[functions/core.sensor_attribution.UnifiedAttribution.__init__|core.sensor_attribution.UnifiedAttribution.__init__]] (line 183, method)
- [[functions/core.sensor_attribution.UnifiedAttribution.attribute|core.sensor_attribution.UnifiedAttribution.attribute]] (line 202, method)
- [[functions/core.sensor_attribution.UnifiedAttribution._compute_contributions|core.sensor_attribution.UnifiedAttribution._compute_contributions]] (line 262, method)
- [[functions/core.sensor_attribution.UnifiedAttribution._determine_direction|core.sensor_attribution.UnifiedAttribution._determine_direction]] (line 339, method)
- [[functions/core.sensor_attribution.UnifiedAttribution._generate_explanation|core.sensor_attribution.UnifiedAttribution._generate_explanation]] (line 348, method)
- [[functions/core.sensor_attribution.UnifiedAttribution.attribute_episode|core.sensor_attribution.UnifiedAttribution.attribute_episode]] (line 377, method)
- [[functions/core.sensor_attribution.SensorAttribution|core.sensor_attribution.SensorAttribution]] (line 425, class)
- [[functions/core.sensor_attribution.SensorAttributor|core.sensor_attribution.SensorAttributor]] (line 434, class)
- [[functions/core.sensor_attribution.SensorAttributor.__init__|core.sensor_attribution.SensorAttributor.__init__]] (line 458, method)
- [[functions/core.sensor_attribution.SensorAttributor.load_from_sql|core.sensor_attribution.SensorAttributor.load_from_sql]] (line 467, method)
- [[functions/core.sensor_attribution.SensorAttributor._load_hotspots_dataframe|core.sensor_attribution.SensorAttributor._load_hotspots_dataframe]] (line 513, method)
- [[functions/core.sensor_attribution.SensorAttributor._derive_missing_columns|core.sensor_attribution.SensorAttributor._derive_missing_columns]] (line 591, method)
- [[functions/core.sensor_attribution.SensorAttributor.get_top_n|core.sensor_attribution.SensorAttributor.get_top_n]] (line 637, method)
- [[functions/core.sensor_attribution.SensorAttributor.format_top_n|core.sensor_attribution.SensorAttributor.format_top_n]] (line 654, method)
- [[functions/core.sensor_attribution.SensorAttributor.compute_attribution_scores|core.sensor_attribution.SensorAttributor.compute_attribution_scores]] (line 676, method)
- [[functions/core.sensor_attribution.rank_sensors_by_contribution|core.sensor_attribution.rank_sensors_by_contribution]] (line 732, function)
- [[functions/core.sensor_attribution.build_contribution_timeline|core.sensor_attribution.build_contribution_timeline]] (line 767, function)
- [[functions/core.sensor_attribution.persist_contribution_timeline|core.sensor_attribution.persist_contribution_timeline]] (line 865, function)
- [[functions/core.sensor_attribution.build_sensor_analytics_context|core.sensor_attribution.build_sensor_analytics_context]] (line 892, function)

---
type: module
module: core.output_manager
source: core/output_manager.py
generated_at: 2026-02-21T06:37:09+00:00
---

# core.output_manager

Source file: `core/output_manager.py`

Summary: Unified Output Manager for ACM

## Imports from core
- [[modules/core.analytics_builder|core.analytics_builder]]
- [[modules/core.data_loader|core.data_loader]]
- [[modules/core.observability|core.observability]]

## Top-level symbols
- [[functions/core.output_manager._table_exists|core.output_manager._table_exists]] (line 198, function)
- [[functions/core.output_manager._get_table_columns|core.output_manager._get_table_columns]] (line 213, function)
- [[functions/core.output_manager._get_insertable_columns|core.output_manager._get_insertable_columns]] (line 225, function)
- [[functions/core.output_manager._cfg_get|core.output_manager._cfg_get]] (line 270, function)
- [[functions/core.output_manager._future_cutoff_ts|core.output_manager._future_cutoff_ts]] (line 282, function)
- [[functions/core.output_manager._health_index|core.output_manager._health_index]] (line 299, function)
- [[functions/core.output_manager.OutputBatch|core.output_manager.OutputBatch]] (line 308, class)
- [[functions/core.output_manager.OutputManager|core.output_manager.OutputManager]] (line 317, class)
- [[functions/core.output_manager.OutputManager.__init__|core.output_manager.OutputManager.__init__]] (line 329, method)
- [[functions/core.output_manager.OutputManager.set_maturity_state|core.output_manager.OutputManager.set_maturity_state]] (line 404, method)
- [[functions/core.output_manager.OutputManager.batched_transaction|core.output_manager.OutputManager.batched_transaction]] (line 417, method)
- [[functions/core.output_manager.OutputManager._load_data_from_sql|core.output_manager.OutputManager._load_data_from_sql]] (line 464, method)
- [[functions/core.output_manager.OutputManager._check_sql_health|core.output_manager.OutputManager._check_sql_health]] (line 483, method)
- [[functions/core.output_manager.OutputManager._prepare_dataframe_for_sql|core.output_manager.OutputManager._prepare_dataframe_for_sql]] (line 524, method)
- [[functions/core.output_manager.OutputManager._should_auto_flush|core.output_manager.OutputManager._should_auto_flush]] (line 610, method)
- [[functions/core.output_manager.OutputManager._wait_for_futures_capacity|core.output_manager.OutputManager._wait_for_futures_capacity]] (line 624, method)
- [[functions/core.output_manager.OutputManager.write_dataframe|core.output_manager.OutputManager.write_dataframe]] (line 638, method)
- [[functions/core.output_manager.OutputManager.write_table|core.output_manager.OutputManager.write_table]] (line 823, method)
- [[functions/core.output_manager.OutputManager._bulk_insert_sql|core.output_manager.OutputManager._bulk_insert_sql]] (line 868, method)
- [[functions/core.output_manager.OutputManager.get_cached_table|core.output_manager.OutputManager.get_cached_table]] (line 1050, method)
- [[functions/core.output_manager.OutputManager.write_pca_metrics|core.output_manager.OutputManager.write_pca_metrics]] (line 1076, method)
- [[functions/core.output_manager.OutputManager.write_pca_loadings|core.output_manager.OutputManager.write_pca_loadings]] (line 1162, method)
- [[functions/core.output_manager.OutputManager._upsert_pca_metrics|core.output_manager.OutputManager._upsert_pca_metrics]] (line 1244, method)
- [[functions/core.output_manager.OutputManager._upsert_health_forecast|core.output_manager.OutputManager._upsert_health_forecast]] (line 1324, method)
- [[functions/core.output_manager.OutputManager._upsert_failure_forecast|core.output_manager.OutputManager._upsert_failure_forecast]] (line 1339, method)
- [[functions/core.output_manager.OutputManager._upsert_detector_forecast_ts|core.output_manager.OutputManager._upsert_detector_forecast_ts]] (line 1353, method)
- [[functions/core.output_manager.OutputManager._upsert_sensor_forecast|core.output_manager.OutputManager._upsert_sensor_forecast]] (line 1431, method)
- [[functions/core.output_manager.OutputManager.write_run_stats|core.output_manager.OutputManager.write_run_stats]] (line 1445, method)
- [[functions/core.output_manager.OutputManager.write_scores|core.output_manager.OutputManager.write_scores]] (line 1467, method)
- [[functions/core.output_manager.OutputManager.write_episodes|core.output_manager.OutputManager.write_episodes]] (line 1547, method)
- [[functions/core.output_manager.OutputManager.write_threshold_metadata|core.output_manager.OutputManager.write_threshold_metadata]] (line 1690, method)
- [[functions/core.output_manager.OutputManager._upsert_adaptive_config|core.output_manager.OutputManager._upsert_adaptive_config]] (line 1756, method)
- [[functions/core.output_manager.OutputManager.load_omr_drift_context|core.output_manager.OutputManager.load_omr_drift_context]] (line 1809, method)
- [[functions/core.output_manager.OutputManager._build_data_quality_records|core.output_manager.OutputManager._build_data_quality_records]] (line 1934, method)
- [[functions/core.output_manager.OutputManager.write_anomaly_events|core.output_manager.OutputManager.write_anomaly_events]] (line 2065, method)
- [[functions/core.output_manager.OutputManager.write_regime_episodes|core.output_manager.OutputManager.write_regime_episodes]] (line 2144, method)
- [[functions/core.output_manager.OutputManager.write_pca_model|core.output_manager.OutputManager.write_pca_model]] (line 2164, method)
- [[functions/core.output_manager.OutputManager.write_detector_correlation|core.output_manager.OutputManager.write_detector_correlation]] (line 2225, method)
- [[functions/core.output_manager.OutputManager.write_detector_correlation_from_scores|core.output_manager.OutputManager.write_detector_correlation_from_scores]] (line 2259, method)
- [[functions/core.output_manager.OutputManager.write_drift_series|core.output_manager.OutputManager.write_drift_series]] (line 2288, method)
- [[functions/core.output_manager.OutputManager.write_sensor_normalized_ts|core.output_manager.OutputManager.write_sensor_normalized_ts]] (line 2308, method)
- [[functions/core.output_manager.OutputManager.write_sensor_correlations|core.output_manager.OutputManager.write_sensor_correlations]] (line 2427, method)
- [[functions/core.output_manager.OutputManager.write_sensor_correlations_from_raw|core.output_manager.OutputManager.write_sensor_correlations_from_raw]] (line 2488, method)
- [[functions/core.output_manager.OutputManager.write_feature_drop_log|core.output_manager.OutputManager.write_feature_drop_log]] (line 2512, method)
- [[functions/core.output_manager.OutputManager.write_calibration_summary|core.output_manager.OutputManager.write_calibration_summary]] (line 2529, method)
- [[functions/core.output_manager.OutputManager.write_regime_occupancy|core.output_manager.OutputManager.write_regime_occupancy]] (line 2546, method)
- [[functions/core.output_manager.OutputManager.write_regime_transitions|core.output_manager.OutputManager.write_regime_transitions]] (line 2563, method)
- [[functions/core.output_manager.OutputManager.write_contribution_timeline|core.output_manager.OutputManager.write_contribution_timeline]] (line 2598, method)
- [[functions/core.output_manager.OutputManager.write_regime_promotion_log|core.output_manager.OutputManager.write_regime_promotion_log]] (line 2615, method)
- [[functions/core.output_manager.OutputManager.write_refit_request|core.output_manager.OutputManager.write_refit_request]] (line 2632, method)
- [[functions/core.output_manager.OutputManager.write_fusion_metrics|core.output_manager.OutputManager.write_fusion_metrics]] (line 2698, method)
- [[functions/core.output_manager.OutputManager.check_refit_request|core.output_manager.OutputManager.check_refit_request]] (line 2781, method)
- [[functions/core.output_manager.OutputManager.update_baseline_buffer|core.output_manager.OutputManager.update_baseline_buffer]] (line 2824, method)
- [[functions/core.output_manager.OutputManager._ensure_local_index|core.output_manager.OutputManager._ensure_local_index]] (line 2946, method)
- [[functions/core.output_manager.OutputManager.write_drift_controller|core.output_manager.OutputManager.write_drift_controller]] (line 2963, method)
- [[functions/core.output_manager.OutputManager.write_regime_definitions|core.output_manager.OutputManager.write_regime_definitions]] (line 2980, method)
- [[functions/core.output_manager.OutputManager.write_active_models|core.output_manager.OutputManager.write_active_models]] (line 2999, method)
- [[functions/core.output_manager.OutputManager.write_data_contract_validation|core.output_manager.OutputManager.write_data_contract_validation]] (line 3030, method)
- [[functions/core.output_manager.OutputManager.write_seasonal_patterns|core.output_manager.OutputManager.write_seasonal_patterns]] (line 3048, method)
- [[functions/core.output_manager.OutputManager.write_sensor_normalized_ts_from_raw|core.output_manager.OutputManager.write_sensor_normalized_ts_from_raw]] (line 3066, method)
- [[functions/core.output_manager.OutputManager.write_seasonal_patterns_from_detected|core.output_manager.OutputManager.write_seasonal_patterns_from_detected]] (line 3096, method)
- [[functions/core.output_manager.OutputManager.get_stats|core.output_manager.OutputManager.get_stats]] (line 3128, method)
- [[functions/core.output_manager.OutputManager.flush|core.output_manager.OutputManager.flush]] (line 3136, method)
- [[functions/core.output_manager.OutputManager.flush_and_finalize|core.output_manager.OutputManager.flush_and_finalize]] (line 3142, method)
- [[functions/core.output_manager.OutputManager.close|core.output_manager.OutputManager.close]] (line 3156, method)
- [[functions/core.output_manager.OutputManager._delete_timeline_overlaps|core.output_manager.OutputManager._delete_timeline_overlaps]] (line 3165, method)
- [[functions/core.output_manager.OutputManager._bulk_delete_analytics_tables|core.output_manager.OutputManager._bulk_delete_analytics_tables]] (line 3225, method)
- [[functions/core.output_manager.OutputManager.generate_all_analytics_tables|core.output_manager.OutputManager.generate_all_analytics_tables]] (line 3366, method)
- [[functions/core.output_manager.OutputManager._generate_health_timeline|core.output_manager.OutputManager._generate_health_timeline]] (line 3387, method)
- [[functions/core.output_manager.OutputManager._generate_regime_timeline|core.output_manager.OutputManager._generate_regime_timeline]] (line 3392, method)
- [[functions/core.output_manager.OutputManager._generate_sensor_defects|core.output_manager.OutputManager._generate_sensor_defects]] (line 3397, method)
- [[functions/core.output_manager.OutputManager._generate_sensor_hotspots_table|core.output_manager.OutputManager._generate_sensor_hotspots_table]] (line 3402, method)
- [[functions/core.output_manager.write_pca_artifacts|core.output_manager.write_pca_artifacts]] (line 3424, function)
- [[functions/core.output_manager.write_sql_artifacts|core.output_manager.write_sql_artifacts]] (line 3559, function)

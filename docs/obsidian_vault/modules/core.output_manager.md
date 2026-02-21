---
type: module
module: core.output_manager
source: core/output_manager.py
---

# core.output_manager

Source file: `core/output_manager.py`

Summary: Unified Output Manager for ACM

## Imports from core
- [[modules/core.analytics_builder]]
- [[modules/core.data_loader]]
- [[modules/core.observability]]

## Top-level symbols
- [[functions/core.output_manager._table_exists]] (line 199, function)
- [[functions/core.output_manager._get_table_columns]] (line 214, function)
- [[functions/core.output_manager._get_insertable_columns]] (line 226, function)
- [[functions/core.output_manager._cfg_get]] (line 271, function)
- [[functions/core.output_manager._future_cutoff_ts]] (line 283, function)
- [[functions/core.output_manager._health_index]] (line 300, function)
- [[functions/core.output_manager.OutputBatch]] (line 309, class)
- [[functions/core.output_manager.OutputManager]] (line 318, class)
- [[functions/core.output_manager.OutputManager.__init__]] (line 330, method)
- [[functions/core.output_manager.OutputManager.set_maturity_state]] (line 405, method)
- [[functions/core.output_manager.OutputManager.batched_transaction]] (line 418, method)
- [[functions/core.output_manager.OutputManager._load_data_from_sql]] (line 465, method)
- [[functions/core.output_manager.OutputManager._check_sql_health]] (line 484, method)
- [[functions/core.output_manager.OutputManager._prepare_dataframe_for_sql]] (line 525, method)
- [[functions/core.output_manager.OutputManager._should_auto_flush]] (line 611, method)
- [[functions/core.output_manager.OutputManager._wait_for_futures_capacity]] (line 625, method)
- [[functions/core.output_manager.OutputManager.write_dataframe]] (line 639, method)
- [[functions/core.output_manager.OutputManager.write_table]] (line 824, method)
- [[functions/core.output_manager.OutputManager._bulk_insert_sql]] (line 869, method)
- [[functions/core.output_manager.OutputManager.get_cached_table]] (line 1051, method)
- [[functions/core.output_manager.OutputManager.write_pca_metrics]] (line 1077, method)
- [[functions/core.output_manager.OutputManager.write_pca_loadings]] (line 1163, method)
- [[functions/core.output_manager.OutputManager._upsert_pca_metrics]] (line 1245, method)
- [[functions/core.output_manager.OutputManager._upsert_health_forecast]] (line 1325, method)
- [[functions/core.output_manager.OutputManager._upsert_failure_forecast]] (line 1340, method)
- [[functions/core.output_manager.OutputManager._upsert_detector_forecast_ts]] (line 1354, method)
- [[functions/core.output_manager.OutputManager._upsert_sensor_forecast]] (line 1432, method)
- [[functions/core.output_manager.OutputManager.write_run_stats]] (line 1446, method)
- [[functions/core.output_manager.OutputManager.write_scores]] (line 1468, method)
- [[functions/core.output_manager.OutputManager.write_episodes]] (line 1548, method)
- [[functions/core.output_manager.OutputManager.write_threshold_metadata]] (line 1691, method)
- [[functions/core.output_manager.OutputManager._upsert_adaptive_config]] (line 1757, method)
- [[functions/core.output_manager.OutputManager.load_omr_drift_context]] (line 1810, method)
- [[functions/core.output_manager.OutputManager._build_data_quality_records]] (line 1935, method)
- [[functions/core.output_manager.OutputManager.write_anomaly_events]] (line 2066, method)
- [[functions/core.output_manager.OutputManager.write_regime_episodes]] (line 2145, method)
- [[functions/core.output_manager.OutputManager.write_pca_model]] (line 2165, method)
- [[functions/core.output_manager.OutputManager.write_detector_correlation]] (line 2226, method)
- [[functions/core.output_manager.OutputManager.write_detector_correlation_from_scores]] (line 2260, method)
- [[functions/core.output_manager.OutputManager.write_drift_series]] (line 2289, method)
- [[functions/core.output_manager.OutputManager.write_sensor_normalized_ts]] (line 2309, method)
- [[functions/core.output_manager.OutputManager.write_sensor_correlations]] (line 2428, method)
- [[functions/core.output_manager.OutputManager.write_sensor_correlations_from_raw]] (line 2489, method)
- [[functions/core.output_manager.OutputManager.write_feature_drop_log]] (line 2513, method)
- [[functions/core.output_manager.OutputManager.write_calibration_summary]] (line 2530, method)
- [[functions/core.output_manager.OutputManager.write_regime_occupancy]] (line 2547, method)
- [[functions/core.output_manager.OutputManager.write_regime_transitions]] (line 2564, method)
- [[functions/core.output_manager.OutputManager.write_contribution_timeline]] (line 2599, method)
- [[functions/core.output_manager.OutputManager.write_regime_promotion_log]] (line 2616, method)
- [[functions/core.output_manager.OutputManager.write_refit_request]] (line 2633, method)
- [[functions/core.output_manager.OutputManager.write_fusion_metrics]] (line 2699, method)
- [[functions/core.output_manager.OutputManager.check_refit_request]] (line 2782, method)
- [[functions/core.output_manager.OutputManager.update_baseline_buffer]] (line 2825, method)
- [[functions/core.output_manager.OutputManager._ensure_local_index]] (line 2947, method)
- [[functions/core.output_manager.OutputManager.write_drift_controller]] (line 2964, method)
- [[functions/core.output_manager.OutputManager.write_regime_definitions]] (line 2981, method)
- [[functions/core.output_manager.OutputManager.write_active_models]] (line 3000, method)
- [[functions/core.output_manager.OutputManager.write_data_contract_validation]] (line 3031, method)
- [[functions/core.output_manager.OutputManager.write_seasonal_patterns]] (line 3049, method)
- [[functions/core.output_manager.OutputManager.write_sensor_normalized_ts_from_raw]] (line 3067, method)
- [[functions/core.output_manager.OutputManager.write_seasonal_patterns_from_detected]] (line 3097, method)
- [[functions/core.output_manager.OutputManager.release_persist_memory]] (line 3128, method)
- [[functions/core.output_manager.OutputManager.get_stats]] (line 3154, method)
- [[functions/core.output_manager.OutputManager.flush]] (line 3162, method)
- [[functions/core.output_manager.OutputManager.flush_and_finalize]] (line 3168, method)
- [[functions/core.output_manager.OutputManager.close]] (line 3182, method)
- [[functions/core.output_manager.OutputManager._delete_timeline_overlaps]] (line 3191, method)
- [[functions/core.output_manager.OutputManager._bulk_delete_analytics_tables]] (line 3251, method)
- [[functions/core.output_manager.OutputManager.generate_all_analytics_tables]] (line 3392, method)
- [[functions/core.output_manager.OutputManager._generate_health_timeline]] (line 3413, method)
- [[functions/core.output_manager.OutputManager._generate_regime_timeline]] (line 3418, method)
- [[functions/core.output_manager.OutputManager._generate_sensor_defects]] (line 3423, method)
- [[functions/core.output_manager.OutputManager._generate_sensor_hotspots_table]] (line 3428, method)
- [[functions/core.output_manager.write_pca_artifacts]] (line 3450, function)
- [[functions/core.output_manager.write_sql_artifacts]] (line 3585, function)

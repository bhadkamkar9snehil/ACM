# OutputManager Function Index Audit

Date: 2026-02-22

## Scope
This audit indexes every `def` in `core/output_manager.py` and scores each function for complexity and overprotection patterns.

## Summary
1. Total defs indexed: 81
2. Complexity: low=57, medium=18, high=6
3. Overprotection: low=36, medium=42, high=3

## Highest Priority Simplification Targets
1. `OutputManager.write_dataframe` at line 719 (loc=175, try=2, broad_except=2, complexity=high, overprotection=medium)
2. `OutputManager._bulk_insert_sql` at line 947 (loc=175, try=10, broad_except=10, complexity=high, overprotection=high)
3. `module.write_sql_artifacts` at line 3899 (loc=139, try=2, broad_except=2, complexity=high, overprotection=medium)
4. `OutputManager._bulk_delete_analytics_tables` at line 3597 (loc=138, try=5, broad_except=4, complexity=high, overprotection=high)
5. `OutputManager.update_baseline_buffer` at line 2922 (loc=121, try=4, broad_except=4, complexity=high, overprotection=high)
6. `OutputManager.write_sensor_normalized_ts` at line 2386 (loc=116, try=2, broad_except=2, complexity=high, overprotection=medium)

## Full Index
| Owner | Def | Line | Expected Functionality | LOC | Try | Broad Except | Depth | Complexity | Overprotection | Simplifiable |
|---|---|---:|---|---:|---:|---:|---:|---|---|---|
| `module` | `_table_exists` | 201 | No docstring | 14 | 2 | 2 | 3 | medium | medium | maybe |
| `module` | `_get_table_columns` | 216 | Return the list of column names for a table by probing TOP 0. | 11 | 2 | 1 | 2 | low | medium | no |
| `module` | `_get_insertable_columns` | 228 | Return columns excluding identity columns for safe INSERT. | 18 | 2 | 1 | 2 | low | medium | no |
| `module` | `_health_index` | 277 | Backward compat wrapper - delegates to core.analytics_builder.health_index. | 3 | 0 | 0 | 0 | low | low | no |
| `OutputManager` | `__init__` | 354 | Initialize OutputManager. | 74 | 0 | 0 | 1 | low | low | maybe |
| `OutputManager` | `set_maturity_state` | 429 | V11 CRITICAL: Update maturity state after model lifecycle is computed. | 11 | 0 | 0 | 0 | low | low | no |
| `OutputManager` | `batched_transaction` | 442 | Context manager for writing multiple tables in a single transaction. | 44 | 2 | 2 | 2 | medium | medium | maybe |
| `OutputManager` | `_load_data_from_sql` | 487 | Load training and scoring data from SQL historian using stored procedure. | 18 | 0 | 0 | 0 | low | low | no |
| `OutputManager` | `_check_sql_health` | 506 | Check SQL availability with caching for performance. | 40 | 2 | 2 | 3 | medium | medium | maybe |
| `OutputManager` | `_is_non_empty_dataframe` | 548 | Return True when DataFrame exists and has at least one row. | 3 | 0 | 0 | 0 | low | low | no |
| `OutputManager` | `_can_write_dataframe` | 552 | Centralized write gate for DataFrame payloads. | 10 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `_can_write_payload` | 563 | Centralized write gate for dict/list payloads. | 9 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `_write_optional_table` | 573 | Best-effort table writer for optional artifacts. | 31 | 1 | 1 | 1 | low | medium | no |
| `OutputManager` | `_prepare_dataframe_for_sql` | 605 | Prepare DataFrame for SQL insertion with robust type coercion (SQL Server safe). | 84 | 3 | 1 | 5 | medium | medium | yes |
| `OutputManager` | `_should_auto_flush` | 691 | OUT-18: Check if batch should be automatically flushed based on triggers. | 13 | 0 | 0 | 2 | low | low | no |
| `OutputManager` | `_wait_for_futures_capacity` | 705 | OUT-18: Block if too many in-flight operations (backpressure). | 13 | 0 | 0 | 3 | low | low | no |
| `OutputManager` | `write_dataframe` | 719 | Write DataFrame to SQL (SQL-only; file output removed). | 175 | 2 | 2 | 6 | high | medium | yes |
| `OutputManager` | `_delete_existing_by_run` | 895 | Delete existing rows for current run before replace-style writes. | 18 | 0 | 0 | 2 | low | low | no |
| `OutputManager` | `write_table` | 914 | Generic SQL table writer routed through `write_dataframe`. | 32 | 1 | 1 | 3 | low | medium | no |
| `OutputManager` | `_bulk_insert_sql` | 947 | Perform bulk SQL insert with optimized batching and robust commit. | 175 | 10 | 10 | 5 | high | high | yes |
| `OutputManager` | `get_cached_table` | 1126 | Retrieve a cached DataFrame from the artifact cache. | 25 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `write_pca_metrics` | 1152 | Write PCA fit metrics to ACM_PCA_Metrics table (SQL-only). | 85 | 1 | 1 | 4 | medium | medium | yes |
| `OutputManager` | `write_pca_loadings` | 1238 | Write PCA loadings to ACM_PCA_Loadings table. | 79 | 1 | 1 | 4 | medium | medium | yes |
| `OutputManager` | `_upsert_pca_metrics` | 1318 | Upsert PCA metrics using DELETE + INSERT pattern. | 79 | 2 | 2 | 3 | medium | medium | yes |
| `OutputManager` | `_upsert_health_forecast` | 1398 | FORECAST-WRITE-01: Write health forecast using bulk insert. | 14 | 1 | 1 | 1 | low | medium | no |
| `OutputManager` | `_upsert_failure_forecast` | 1413 | FORECAST-WRITE-02: Write failure forecast using bulk insert. | 13 | 1 | 1 | 1 | low | medium | no |
| `OutputManager` | `_upsert_detector_forecast_ts` | 1427 | FORECAST-UPSERT-03: Upsert detector forecast time series using MERGE. | 77 | 1 | 1 | 2 | medium | medium | yes |
| `OutputManager` | `_upsert_sensor_forecast` | 1505 | FORECAST-WRITE-04: Write sensor forecast using bulk insert. | 13 | 1 | 1 | 1 | low | medium | no |
| `OutputManager` | `write_run_stats` | 1519 | Write run statistics to ACM_Run_Stats table. | 21 | 1 | 1 | 2 | low | medium | no |
| `OutputManager` | `write_scores` | 1541 | Write scores (SQL-only) to dbo.ACM_Scores_Wide. | 76 | 1 | 1 | 6 | medium | medium | yes |
| `OutputManager` | `write_episodes` | 1618 | Write episodes to SQL (SQL-only). | 139 | 0 | 0 | 2 | medium | low | yes |
| `OutputManager` | `persist_core_outputs` | 1758 | Persist core outputs and return inserted row counts for batch accounting. | 16 | 0 | 0 | 0 | low | low | no |
| `OutputManager` | `write_threshold_metadata` | 1775 | Write adaptive threshold metadata to ACM_AdaptiveConfig. | 65 | 1 | 1 | 2 | low | medium | yes |
| `OutputManager` | `_upsert_adaptive_config` | 1841 | Upsert single row into ACM_AdaptiveConfig using MERGE. | 52 | 2 | 2 | 3 | medium | medium | yes |
| `OutputManager` | `load_omr_drift_context` | 1894 | Load OMR and drift context from recent data for forecasting. | 116 | 1 | 1 | 4 | medium | medium | yes |
| `OutputManager` | `_build_data_quality_records` | 2019 | Build a SINGLE summary data quality record (not per-sensor). | 130 | 1 | 0 | 2 | medium | low | yes |
| `OutputManager` | `write_anomaly_events` | 2150 | Write anomaly events to ACM_Anomaly_Events table. | 72 | 1 | 1 | 4 | medium | medium | yes |
| `OutputManager` | `write_regime_episodes` | 2223 | Write regime episodes to ACM_RegimeEpisodes table. | 20 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `write_pca_model` | 2244 | Write PCA model metadata to ACM_PCA_Models table. | 50 | 2 | 0 | 1 | low | medium | yes |
| `OutputManager` | `write_detector_correlation` | 2295 | Write detector correlation matrix to ACM_DetectorCorrelation. | 33 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `write_detector_correlation_from_scores` | 2329 | Build detector correlation matrix from score frame and persist it. | 36 | 1 | 1 | 2 | low | medium | no |
| `OutputManager` | `write_drift_series` | 2366 | Write drift detection time series to ACM_DriftSeries. | 19 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `write_sensor_normalized_ts` | 2386 | Write normalized sensor z-scores to ACM_SensorNormalized_TS. | 116 | 2 | 2 | 6 | high | medium | yes |
| `OutputManager` | `write_sensor_correlations` | 2503 | Write sensor correlation matrix to ACM_SensorCorrelations. | 60 | 2 | 2 | 4 | medium | medium | yes |
| `OutputManager` | `write_sensor_correlations_from_raw` | 2564 | Build sensor correlation matrix from raw sensor frame and persist it. | 23 | 1 | 1 | 2 | low | medium | no |
| `OutputManager` | `write_feature_drop_log` | 2588 | Write dropped features log to ACM_FeatureDropLog. | 16 | 1 | 1 | 1 | low | medium | no |
| `OutputManager` | `write_calibration_summary` | 2605 | Write detector calibration summary to ACM_CalibrationSummary. | 16 | 1 | 1 | 1 | low | medium | no |
| `OutputManager` | `write_regime_occupancy` | 2622 | Write regime occupancy stats to ACM_RegimeOccupancy. | 16 | 1 | 1 | 1 | low | medium | no |
| `OutputManager` | `write_regime_transitions` | 2639 | Write regime transition matrix to ACM_RegimeTransitions. | 34 | 1 | 1 | 2 | low | medium | no |
| `OutputManager` | `write_contribution_timeline` | 2674 | Write detector contribution timeline to ACM_ContributionTimeline. | 16 | 1 | 1 | 1 | low | medium | no |
| `OutputManager` | `write_contribution_timeline_from_frame` | 2691 | Build and persist detector contribution timeline from score frame. | 24 | 1 | 1 | 2 | low | medium | no |
| `OutputManager` | `write_regime_promotion_log` | 2716 | Write regime maturity promotions to ACM_RegimePromotionLog. | 16 | 1 | 1 | 1 | low | medium | no |
| `OutputManager` | `write_refit_request` | 2733 | Write refit request to ACM_RefitRequests table. | 65 | 1 | 1 | 2 | low | medium | yes |
| `OutputManager` | `write_fusion_metrics` | 2799 | Write fusion tuning diagnostics and metrics to ACM_RunMetrics (EAV format). | 79 | 1 | 1 | 2 | medium | medium | yes |
| `OutputManager` | `check_refit_request` | 2879 | Check for pending refit requests in ACM_RefitRequests table. | 42 | 1 | 1 | 3 | low | medium | maybe |
| `OutputManager` | `update_baseline_buffer` | 2922 | Update the ACM_BaselineBuffer table with latest raw score data. | 121 | 4 | 4 | 4 | high | high | yes |
| `OutputManager` | `_ensure_local_index` | 3044 | Ensure the DataFrame index is a timezone-naive local DatetimeIndex. | 16 | 1 | 1 | 3 | low | medium | no |
| `OutputManager` | `_get_numeric_sensor_columns` | 3061 | Return numeric sensor columns excluding metadata and z-score columns. | 19 | 0 | 0 | 2 | low | low | no |
| `OutputManager` | `_filter_low_variance_columns` | 3081 | Keep only columns with variance above the configured floor. | 13 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `write_drift_controller` | 3095 | Write drift controller state to ACM_DriftController. | 17 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `write_regime_definitions` | 3113 | Write regime definitions to ACM_RegimeDefinitions (v11). | 19 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `write_active_models` | 3133 | Write/update active model versions to ACM_ActiveModels (v11). | 30 | 0 | 0 | 3 | low | low | no |
| `OutputManager` | `write_data_contract_validation` | 3164 | Write data contract validation result to ACM_DataContractValidation (v11). | 18 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `write_seasonal_patterns` | 3183 | Write detected seasonal patterns to ACM_SeasonalPatterns (v11). | 18 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `write_sensor_normalized_ts_from_raw` | 3202 | Sample raw sensor frame and persist normalized sensor time series rows. | 17 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `write_seasonal_patterns_from_detected` | 3220 | Flatten detected seasonal patterns and persist them to SQL. | 23 | 0 | 0 | 3 | low | low | no |
| `OutputManager` | `persist_additional_artifacts` | 3244 | Persist optional secondary artifacts derived from current run data. | 19 | 0 | 0 | 0 | low | low | no |
| `OutputManager` | `generate_all_analytics_with_context` | 3264 | Persist analytics tables after optional fusion-weight injection into cfg. | 17 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `persist_pipeline_outputs` | 3282 | Persist core and optional run artifacts, then release persist-phase memory. | 64 | 0 | 0 | 1 | low | low | maybe |
| `OutputManager` | `run_persistence_stage` | 3347 | Execute full persistence stage for pipeline outputs and SQL artifacts. | 88 | 0 | 0 | 3 | low | low | yes |
| `OutputManager` | `prepare_persistence_inputs` | 3436 | Prepare persistence-stage inputs: baseline buffer update and sensor context. | 37 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `release_persist_memory` | 3474 | Free large persist-phase objects after SQL writes are complete. | 24 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `get_stats` | 3500 | Get performance statistics. | 7 | 0 | 0 | 0 | low | low | no |
| `OutputManager` | `flush` | 3508 | OUT-18: Flush current batch without finalizing (for auto-flush triggers). | 5 | 0 | 0 | 1 | low | low | no |
| `OutputManager` | `flush_and_finalize` | 3514 | Flush any pending operations and return final statistics. | 13 | 0 | 0 | 0 | low | low | no |
| `OutputManager` | `close` | 3528 | Gracefully finalize outstanding work. Compatible with acm_main finally block. | 6 | 1 | 1 | 1 | low | medium | no |
| `OutputManager` | `_delete_timeline_overlaps` | 3537 | v11.1.5 FIX: Delete overlapping rows from timeline tables by TIMESTAMP RANGE. | 59 | 1 | 1 | 5 | medium | medium | yes |
| `OutputManager` | `_bulk_delete_analytics_tables` | 3597 | PERF-OPT v11: Delete existing rows for current RunID/EquipID from multiple tables in ONE SQL batch. | 138 | 5 | 4 | 5 | high | high | yes |
| `OutputManager` | `generate_all_analytics_tables` | 3738 | Generate essential analytics tables (v11 - SQL-only). | 20 | 0 | 0 | 0 | low | low | no |
| `module` | `write_pca_artifacts` | 3764 | Write PCA model, loadings, and metrics to SQL tables. | 133 | 1 | 1 | 4 | medium | medium | yes |
| `module` | `write_sql_artifacts` | 3899 | Write SQL-specific artifacts: DriftTS, AnomalyEvents, RegimeEpisodes, PCA, RunStats, Culprits. | 139 | 2 | 2 | 4 | high | medium | yes |

## Split Scope Assessment
Low-hanging split candidates in existing ownership direction:
1. Extract module-level SQL artifact writers (`write_pca_artifacts`, `write_sql_artifacts`) into a dedicated `core/output_artifacts.py`.
2. Keep `OutputManager` focused on table write primitives and persistence-stage orchestration.
3. Keep analytics generation in `core/analytics_builder.py` as already implemented.

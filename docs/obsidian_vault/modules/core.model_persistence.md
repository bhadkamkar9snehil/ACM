---
type: module
module: core.model_persistence
source: core/model_persistence.py
---

# core.model_persistence

Source file: `core/model_persistence.py`

Summary: Model Versioning & Persistence Module

## Imports from core
- [[modules/core.observability|core.observability]]

## Top-level symbols
- [[functions/core.model_persistence.ForecastState|core.model_persistence.ForecastState]] (line 71, class)
- [[functions/core.model_persistence.ForecastState.to_dict|core.model_persistence.ForecastState.to_dict]] (line 106, method)
- [[functions/core.model_persistence.ForecastState.from_dict|core.model_persistence.ForecastState.from_dict]] (line 111, method)
- [[functions/core.model_persistence.ForecastState.get_last_forecast_horizon|core.model_persistence.ForecastState.get_last_forecast_horizon]] (line 115, method)
- [[functions/core.model_persistence.ForecastState.serialize_forecast_horizon|core.model_persistence.ForecastState.serialize_forecast_horizon]] (line 129, method)
- [[functions/core.model_persistence.save_forecast_state|core.model_persistence.save_forecast_state]] (line 145, function)
- [[functions/core.model_persistence.load_forecast_state|core.model_persistence.load_forecast_state]] (line 207, function)
- [[functions/core.model_persistence.RegimeState|core.model_persistence.RegimeState]] (line 271, class)
- [[functions/core.model_persistence.RegimeState.to_dict|core.model_persistence.RegimeState.to_dict]] (line 307, method)
- [[functions/core.model_persistence.RegimeState.from_dict|core.model_persistence.RegimeState.from_dict]] (line 312, method)
- [[functions/core.model_persistence.RegimeState.get_cluster_centers|core.model_persistence.RegimeState.get_cluster_centers]] (line 316, method)
- [[functions/core.model_persistence.RegimeState.get_scaler_params|core.model_persistence.RegimeState.get_scaler_params]] (line 325, method)
- [[functions/core.model_persistence.RegimeState.get_pca_params|core.model_persistence.RegimeState.get_pca_params]] (line 335, method)
- [[functions/core.model_persistence.RegimeState.serialize_array|core.model_persistence.RegimeState.serialize_array]] (line 348, method)
- [[functions/core.model_persistence.save_regime_state|core.model_persistence.save_regime_state]] (line 357, function)
- [[functions/core.model_persistence.load_regime_state|core.model_persistence.load_regime_state]] (line 421, function)
- [[functions/core.model_persistence.ModelVersionManager|core.model_persistence.ModelVersionManager]] (line 484, class)
- [[functions/core.model_persistence.ModelVersionManager.__init__|core.model_persistence.ModelVersionManager.__init__]] (line 487, method)
- [[functions/core.model_persistence.ModelVersionManager.get_latest_version|core.model_persistence.ModelVersionManager.get_latest_version]] (line 503, method)
- [[functions/core.model_persistence.ModelVersionManager.get_next_version|core.model_persistence.ModelVersionManager.get_next_version]] (line 511, method)
- [[functions/core.model_persistence.ModelVersionManager.save_models|core.model_persistence.ModelVersionManager.save_models]] (line 516, method)
- [[functions/core.model_persistence.ModelVersionManager._save_models_to_sql|core.model_persistence.ModelVersionManager._save_models_to_sql]] (line 586, method)
- [[functions/core.model_persistence.ModelVersionManager.save_calibration_params|core.model_persistence.ModelVersionManager.save_calibration_params]] (line 693, method)
- [[functions/core.model_persistence.ModelVersionManager._cleanup_old_versions|core.model_persistence.ModelVersionManager._cleanup_old_versions]] (line 742, method)
- [[functions/core.model_persistence.ModelVersionManager._get_latest_version_from_sql|core.model_persistence.ModelVersionManager._get_latest_version_from_sql]] (line 798, method)
- [[functions/core.model_persistence.ModelVersionManager.load_manifest_only|core.model_persistence.ModelVersionManager.load_manifest_only]] (line 815, method)
- [[functions/core.model_persistence.ModelVersionManager._load_models_from_sql|core.model_persistence.ModelVersionManager._load_models_from_sql]] (line 859, method)
- [[functions/core.model_persistence.ModelVersionManager.load_models|core.model_persistence.ModelVersionManager.load_models]] (line 966, method)
- [[functions/core.model_persistence.ModelVersionManager.update_models_incremental|core.model_persistence.ModelVersionManager.update_models_incremental]] (line 1026, method)
- [[functions/core.model_persistence.ModelVersionManager.check_model_validity|core.model_persistence.ModelVersionManager.check_model_validity]] (line 1113, method)
- [[functions/core.model_persistence.ModelVersionManager.list_versions|core.model_persistence.ModelVersionManager.list_versions]] (line 1182, method)
- [[functions/core.model_persistence.create_model_metadata|core.model_persistence.create_model_metadata]] (line 1223, function)
- [[functions/core.model_persistence.load_cached_models_with_validation|core.model_persistence.load_cached_models_with_validation]] (line 1415, function)
- [[functions/core.model_persistence.align_current_features_to_cached_manifest|core.model_persistence.align_current_features_to_cached_manifest]] (line 1525, function)
- [[functions/core.model_persistence.restore_detectors_from_runtime_cache|core.model_persistence.restore_detectors_from_runtime_cache]] (line 1596, function)
- [[functions/core.model_persistence.load_quality_regime_state_if_needed|core.model_persistence.load_quality_regime_state_if_needed]] (line 1640, function)
- [[functions/core.model_persistence.load_and_rebuild_detectors_from_sql_cache|core.model_persistence.load_and_rebuild_detectors_from_sql_cache]] (line 1665, function)
- [[functions/core.model_persistence.save_trained_models|core.model_persistence.save_trained_models]] (line 1752, function)

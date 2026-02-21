---
type: module
module: core.forecast_engine
source: core/forecast_engine.py
generated_at: 2026-02-21T06:37:09+00:00
---

# core.forecast_engine

Source file: `core/forecast_engine.py`

Summary: # =============================================================================

## Imports from core
- [[modules/core.confidence|core.confidence]]
- [[modules/core.degradation_model|core.degradation_model]]
- [[modules/core.failure_probability|core.failure_probability]]
- [[modules/core.health_tracker|core.health_tracker]]
- [[modules/core.metrics|core.metrics]]
- [[modules/core.model_lifecycle|core.model_lifecycle]]
- [[modules/core.observability|core.observability]]
- [[modules/core.output_manager|core.output_manager]]
- [[modules/core.rul_estimator|core.rul_estimator]]
- [[modules/core.sensor_attribution|core.sensor_attribution]]
- [[modules/core.state_manager|core.state_manager]]

## Top-level symbols
- [[functions/core.forecast_engine._mann_kendall_trend_direction|core.forecast_engine._mann_kendall_trend_direction]] (line 90, function)
- [[functions/core.forecast_engine.RegimeStats|core.forecast_engine.RegimeStats]] (line 118, class)
- [[functions/core.forecast_engine.ForecastContext|core.forecast_engine.ForecastContext]] (line 135, class)
- [[functions/core.forecast_engine.ForecastEngine|core.forecast_engine.ForecastEngine]] (line 151, class)
- [[functions/core.forecast_engine.ForecastEngine.__init__|core.forecast_engine.ForecastEngine.__init__]] (line 177, method)
- [[functions/core.forecast_engine.ForecastEngine.run_forecast|core.forecast_engine.ForecastEngine.run_forecast]] (line 211, method)
- [[functions/core.forecast_engine.ForecastEngine._load_health_timeline|core.forecast_engine.ForecastEngine._load_health_timeline]] (line 472, method)
- [[functions/core.forecast_engine.ForecastEngine._load_forecast_config|core.forecast_engine.ForecastEngine._load_forecast_config]] (line 518, method)
- [[functions/core.forecast_engine.ForecastEngine._load_regime_series_for_health|core.forecast_engine.ForecastEngine._load_regime_series_for_health]] (line 563, method)
- [[functions/core.forecast_engine.ForecastEngine._build_regime_transition_context|core.forecast_engine.ForecastEngine._build_regime_transition_context]] (line 666, method)
- [[functions/core.forecast_engine.ForecastEngine._fit_degradation_model|core.forecast_engine.ForecastEngine._fit_degradation_model]] (line 727, method)
- [[functions/core.forecast_engine.ForecastEngine._generate_forecast_and_rul|core.forecast_engine.ForecastEngine._generate_forecast_and_rul]] (line 785, method)
- [[functions/core.forecast_engine.ForecastEngine._get_model_maturity_state|core.forecast_engine.ForecastEngine._get_model_maturity_state]] (line 903, method)
- [[functions/core.forecast_engine.ForecastEngine._load_sensor_attributions|core.forecast_engine.ForecastEngine._load_sensor_attributions]] (line 935, method)
- [[functions/core.forecast_engine.ForecastEngine._validate_forecast_timestamps|core.forecast_engine.ForecastEngine._validate_forecast_timestamps]] (line 941, method)
- [[functions/core.forecast_engine.ForecastEngine._write_outputs|core.forecast_engine.ForecastEngine._write_outputs]] (line 1001, method)
- [[functions/core.forecast_engine.ForecastEngine._run_regime_conditioned_forecasting|core.forecast_engine.ForecastEngine._run_regime_conditioned_forecasting]] (line 1298, method)
- [[functions/core.forecast_engine.ForecastEngine._generate_sensor_forecasts|core.forecast_engine.ForecastEngine._generate_sensor_forecasts]] (line 1396, method)
- [[functions/core.forecast_engine.RegimeConditionedForecaster|core.forecast_engine.RegimeConditionedForecaster]] (line 1719, class)
- [[functions/core.forecast_engine.RegimeConditionedForecaster.__init__|core.forecast_engine.RegimeConditionedForecaster.__init__]] (line 1749, method)
- [[functions/core.forecast_engine.RegimeConditionedForecaster.load_forecast_context|core.forecast_engine.RegimeConditionedForecaster.load_forecast_context]] (line 1767, method)
- [[functions/core.forecast_engine.RegimeConditionedForecaster.compute_regime_stats|core.forecast_engine.RegimeConditionedForecaster.compute_regime_stats]] (line 1815, method)
- [[functions/core.forecast_engine.RegimeConditionedForecaster.estimate_rul_by_regime|core.forecast_engine.RegimeConditionedForecaster.estimate_rul_by_regime]] (line 1985, method)
- [[functions/core.forecast_engine.RegimeConditionedForecaster.write_regime_conditioned_outputs|core.forecast_engine.RegimeConditionedForecaster.write_regime_conditioned_outputs]] (line 2111, method)
- [[functions/core.forecast_engine.RegimeConditionedForecaster._load_current_regime|core.forecast_engine.RegimeConditionedForecaster._load_current_regime]] (line 2218, method)
- [[functions/core.forecast_engine.RegimeConditionedForecaster._compute_regime_confidence|core.forecast_engine.RegimeConditionedForecaster._compute_regime_confidence]] (line 2237, method)
- [[functions/core.forecast_engine.RegimeConditionedForecaster._detect_health_trend|core.forecast_engine.RegimeConditionedForecaster._detect_health_trend]] (line 2293, method)
- [[functions/core.forecast_engine.RegimeConditionedForecaster._count_active_defects|core.forecast_engine.RegimeConditionedForecaster._count_active_defects]] (line 2327, method)
- [[functions/core.forecast_engine.RegimeConditionedForecaster._check_retraining_needed|core.forecast_engine.RegimeConditionedForecaster._check_retraining_needed]] (line 2345, method)
- [[functions/core.forecast_engine.RegimeConditionedForecaster._estimate_data_quality|core.forecast_engine.RegimeConditionedForecaster._estimate_data_quality]] (line 2372, method)
- [[functions/core.forecast_engine.RegimeConditionedForecaster._compute_regime_hazards|core.forecast_engine.RegimeConditionedForecaster._compute_regime_hazards]] (line 2428, method)

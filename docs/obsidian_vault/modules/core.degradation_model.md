---
type: module
module: core.degradation_model
source: core/degradation_model.py
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - module
---

# core.degradation_model

Source file: `core/degradation_model.py`

Summary: # =============================================================================

## Imports from core
- [[modules/core.observability|core.observability]]

## Top-level symbols
- [[functions/core.degradation_model.DegradationForecast|core.degradation_model.DegradationForecast]] (line 40, class)
- [[functions/core.degradation_model.BaseDegradationModel|core.degradation_model.BaseDegradationModel]] (line 51, class)
- [[functions/core.degradation_model.BaseDegradationModel.fit|core.degradation_model.BaseDegradationModel.fit]] (line 64, method)
- [[functions/core.degradation_model.BaseDegradationModel.predict|core.degradation_model.BaseDegradationModel.predict]] (line 74, method)
- [[functions/core.degradation_model.BaseDegradationModel.update_incremental|core.degradation_model.BaseDegradationModel.update_incremental]] (line 94, method)
- [[functions/core.degradation_model.BaseDegradationModel.get_parameters|core.degradation_model.BaseDegradationModel.get_parameters]] (line 104, method)
- [[functions/core.degradation_model.BaseDegradationModel.set_parameters|core.degradation_model.BaseDegradationModel.set_parameters]] (line 109, method)
- [[functions/core.degradation_model.LinearTrendModel|core.degradation_model.LinearTrendModel]] (line 114, class)
- [[functions/core.degradation_model.LinearTrendModel.__init__|core.degradation_model.LinearTrendModel.__init__]] (line 136, method)
- [[functions/core.degradation_model.LinearTrendModel.fit|core.degradation_model.LinearTrendModel.fit]] (line 183, method)
- [[functions/core.degradation_model.LinearTrendModel.predict|core.degradation_model.LinearTrendModel.predict]] (line 312, method)
- [[functions/core.degradation_model.LinearTrendModel.update_incremental|core.degradation_model.LinearTrendModel.update_incremental]] (line 419, method)
- [[functions/core.degradation_model.LinearTrendModel.get_parameters|core.degradation_model.LinearTrendModel.get_parameters]] (line 458, method)
- [[functions/core.degradation_model.LinearTrendModel.set_parameters|core.degradation_model.LinearTrendModel.set_parameters]] (line 470, method)
- [[functions/core.degradation_model.LinearTrendModel._detect_and_remove_outliers|core.degradation_model.LinearTrendModel._detect_and_remove_outliers]] (line 487, method)
- [[functions/core.degradation_model.LinearTrendModel._detect_and_handle_health_jumps|core.degradation_model.LinearTrendModel._detect_and_handle_health_jumps]] (line 529, method)
- [[functions/core.degradation_model.LinearTrendModel._detect_and_handle_data_gaps|core.degradation_model.LinearTrendModel._detect_and_handle_data_gaps]] (line 623, method)
- [[functions/core.degradation_model.LinearTrendModel._adaptive_smoothing|core.degradation_model.LinearTrendModel._adaptive_smoothing]] (line 648, method)
- [[functions/core.degradation_model.LinearTrendModel._compute_cv_error_vectorized|core.degradation_model.LinearTrendModel._compute_cv_error_vectorized]] (line 702, method)
- [[functions/core.degradation_model.LinearTrendModel._simple_grid_search|core.degradation_model.LinearTrendModel._simple_grid_search]] (line 769, method)
- [[functions/core.degradation_model.LinearTrendModel._evaluate_smoothing_params|core.degradation_model.LinearTrendModel._evaluate_smoothing_params]] (line 792, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel|core.degradation_model.RegimeConditionedTrendModel]] (line 823, class)
- [[functions/core.degradation_model.RegimeConditionedTrendModel.__init__|core.degradation_model.RegimeConditionedTrendModel.__init__]] (line 831, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel.set_current_regime|core.degradation_model.RegimeConditionedTrendModel.set_current_regime]] (line 860, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel._get_active_model|core.degradation_model.RegimeConditionedTrendModel._get_active_model]] (line 863, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel.level|core.degradation_model.RegimeConditionedTrendModel.level]] (line 869, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel.trend|core.degradation_model.RegimeConditionedTrendModel.trend]] (line 873, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel.std_error|core.degradation_model.RegimeConditionedTrendModel.std_error]] (line 877, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel.dt_hours|core.degradation_model.RegimeConditionedTrendModel.dt_hours]] (line 881, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel.fit|core.degradation_model.RegimeConditionedTrendModel.fit]] (line 884, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel.predict|core.degradation_model.RegimeConditionedTrendModel.predict]] (line 955, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel.update_incremental|core.degradation_model.RegimeConditionedTrendModel.update_incremental]] (line 967, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel.get_parameters|core.degradation_model.RegimeConditionedTrendModel.get_parameters]] (line 973, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel.set_parameters|core.degradation_model.RegimeConditionedTrendModel.set_parameters]] (line 983, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel.get_regime_degradation_rates|core.degradation_model.RegimeConditionedTrendModel.get_regime_degradation_rates]] (line 1020, method)
- [[functions/core.degradation_model.RegimeConditionedTrendModel._get_longest_contiguous_segment|core.degradation_model.RegimeConditionedTrendModel._get_longest_contiguous_segment]] (line 1025, method)

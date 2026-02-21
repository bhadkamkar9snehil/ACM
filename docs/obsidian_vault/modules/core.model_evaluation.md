---
type: module
module: core.model_evaluation
source: core/model_evaluation.py
generated_at: 2026-02-21T06:37:09+00:00
---

# core.model_evaluation

Source file: `core/model_evaluation.py`

Summary: Autonomous Model Re-evaluation Module

## Imports from core
- [[modules/core.observability|core.observability]]

## Top-level symbols
- [[functions/core.model_evaluation.ModelQualityMonitor|core.model_evaluation.ModelQualityMonitor]] (line 35, class)
- [[functions/core.model_evaluation.ModelQualityMonitor.__init__|core.model_evaluation.ModelQualityMonitor.__init__]] (line 38, method)
- [[functions/core.model_evaluation.ModelQualityMonitor.assess_detector_quality|core.model_evaluation.ModelQualityMonitor.assess_detector_quality]] (line 59, method)
- [[functions/core.model_evaluation.ModelQualityMonitor.assess_anomaly_rate|core.model_evaluation.ModelQualityMonitor.assess_anomaly_rate]] (line 104, method)
- [[functions/core.model_evaluation.ModelQualityMonitor.assess_regime_quality|core.model_evaluation.ModelQualityMonitor.assess_regime_quality]] (line 176, method)
- [[functions/core.model_evaluation.ModelQualityMonitor.assess_episode_quality|core.model_evaluation.ModelQualityMonitor.assess_episode_quality]] (line 199, method)
- [[functions/core.model_evaluation.ModelQualityMonitor.should_retrain|core.model_evaluation.ModelQualityMonitor.should_retrain]] (line 251, method)
- [[functions/core.model_evaluation.ModelQualityMonitor.create_quality_report|core.model_evaluation.ModelQualityMonitor.create_quality_report]] (line 298, method)
- [[functions/core.model_evaluation.assess_model_quality|core.model_evaluation.assess_model_quality]] (line 324, function)
- [[functions/core.model_evaluation.evaluate_force_retrain_triggers|core.model_evaluation.evaluate_force_retrain_triggers]] (line 384, function)
- [[functions/core.model_evaluation.evaluate_and_maybe_refit_cached_models|core.model_evaluation.evaluate_and_maybe_refit_cached_models]] (line 486, function)
- [[functions/core.model_evaluation.auto_tune_parameters|core.model_evaluation.auto_tune_parameters]] (line 572, function)

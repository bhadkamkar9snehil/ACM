---
type: function
id: core.model_evaluation.evaluate_and_maybe_refit_cached_models
module: core.model_evaluation
source: core/model_evaluation.py
line_start: 486
line_end: 569
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.model_evaluation.evaluate_and_maybe_refit_cached_models

Defined in: [[modules/core.model_evaluation|core.model_evaluation]]

Source: `core/model_evaluation.py:486`

Kind: `function`

Signature: `evaluate_and_maybe_refit_cached_models(*, cfg: Dict[str, Any], cached_models: Optional[Dict[str, Any]], cached_manifest: Optional[Dict[str, Any]], detectors_just_trained: bool, score_out: Dict[str, Any], regime_quality_ok: bool, current_model_maturity: Optional[str], boolean_only_metrics: List[str], equip: str, logger: Any, record_model_refit_fn: Any, fit_all_detectors_fn: Any, train: pd.DataFrame, det_flags: Dict[str, Any], output_manager: Any, sql_client: Any, run_id: Optional[str], equip_id: int, regime_model: Optional[Any])`

Summary: Evaluate auto-retrain triggers for cached models and optionally refit detectors.

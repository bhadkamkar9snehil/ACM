---
type: function
id: core.model_evaluation.auto_tune_parameters
module: core.model_evaluation
source: core/model_evaluation.py
line_start: 486
line_end: 689
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.model_evaluation.auto_tune_parameters

Defined in: [[modules/core.model_evaluation|core.model_evaluation]]

Source: `core/model_evaluation.py:486`

Kind: `function`

Signature: `auto_tune_parameters(frame: pd.DataFrame, episodes: pd.DataFrame, score_out: Dict[str, Any], regime_quality_ok: bool, cfg: Dict[str, Any], sql_client: Any, run_id: Optional[str], equip_id: int, equip: str, output_manager: Optional[Any]=None, cached_manifest: Optional[Dict[str, Any]]=None)`

Summary: Perform autonomous parameter tuning based on model quality assessment.

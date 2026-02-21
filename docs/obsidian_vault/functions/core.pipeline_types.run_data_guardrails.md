---
type: function
id: core.pipeline_types.run_data_guardrails
module: core.pipeline_types
source: core/pipeline_types.py
line_start: 481
line_end: 599
---

# core.pipeline_types.run_data_guardrails

Defined in: [[modules/core.pipeline_types]]

Source: `core/pipeline_types.py:481`

Kind: `function`

Signature: `run_data_guardrails(train: pd.DataFrame, score: pd.DataFrame, meta: Any, cfg: Dict[str, Any], output_manager: Any, run_id: int, equip_id: int, equip: str)`

Summary: Run all data quality guardrails. Returns GuardrailResult with findings.

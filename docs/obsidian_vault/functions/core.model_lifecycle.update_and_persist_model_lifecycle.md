---
type: function
id: core.model_lifecycle.update_and_persist_model_lifecycle
module: core.model_lifecycle
source: core/model_lifecycle.py
line_start: 463
line_end: 608
---

# core.model_lifecycle.update_and_persist_model_lifecycle

Defined in: [[modules/core.model_lifecycle|core.model_lifecycle]]

Source: `core/model_lifecycle.py:463`

Kind: `function`

Signature: `update_and_persist_model_lifecycle(*, sql_client: Any, output_manager: Any, equip_id: int, regime_state_version: int, cfg: Dict[str, Any], train_data: Any, run_id: Optional[str], regime_model: Optional[Any], score_out: Optional[Dict[str, Any]], regime_quality_ok: Optional[bool], logger: Any=Console)`

Summary: Update lifecycle state after model training and persist active-model pointers.

---
type: function
id: core.model_lifecycle.update_and_persist_model_lifecycle_safe
module: core.model_lifecycle
source: core/model_lifecycle.py
line_start: 611
line_end: 650
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.model_lifecycle.update_and_persist_model_lifecycle_safe

Defined in: [[modules/core.model_lifecycle|core.model_lifecycle]]

Source: `core/model_lifecycle.py:611`

Kind: `function`

Signature: `update_and_persist_model_lifecycle_safe(*, sql_client: Any, output_manager: Any, equip_id: int, regime_state_version: int, cfg: Dict[str, Any], train_data: Any, run_id: Optional[str], regime_model: Optional[Any], score_out: Optional[Dict[str, Any]], regime_quality_ok: Optional[bool], logger: Any=Console)`

Summary: Safe wrapper around update_and_persist_model_lifecycle.

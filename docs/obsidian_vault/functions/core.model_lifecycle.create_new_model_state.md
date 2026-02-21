---
type: function
id: core.model_lifecycle.create_new_model_state
module: core.model_lifecycle
source: core/model_lifecycle.py
line_start: 343
line_end: 398
---

# core.model_lifecycle.create_new_model_state

Defined in: [[modules/core.model_lifecycle]]

Source: `core/model_lifecycle.py:343`

Kind: `function`

Signature: `create_new_model_state(equip_id: int, version: int, training_rows: int, training_start: datetime, training_end: datetime, silhouette_score: Optional[float]=None, regime_quality_metric: str='silhouette', regime_quality_ok: Optional[bool]=None, run_id: Optional[str]=None)`

Summary: Create a new model state in LEARNING maturity.

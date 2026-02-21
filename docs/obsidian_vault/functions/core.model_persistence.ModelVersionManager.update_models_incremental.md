---
type: method
id: core.model_persistence.ModelVersionManager.update_models_incremental
module: core.model_persistence
source: core/model_persistence.py
line_start: 1026
line_end: 1111
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.model_persistence.ModelVersionManager.update_models_incremental

Defined in: [[modules/core.model_persistence|core.model_persistence]]

Source: `core/model_persistence.py:1026`

Kind: `method`

Signature: `update_models_incremental(self, models: Dict[str, Any], new_data: pd.DataFrame, version: Optional[int]=None)`

Summary: Update models incrementally with new data using partial_fit where available.

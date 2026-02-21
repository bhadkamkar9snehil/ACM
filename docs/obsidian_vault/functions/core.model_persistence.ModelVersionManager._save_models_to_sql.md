---
type: method
id: core.model_persistence.ModelVersionManager._save_models_to_sql
module: core.model_persistence
source: core/model_persistence.py
line_start: 586
line_end: 691
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.model_persistence.ModelVersionManager._save_models_to_sql

Defined in: [[modules/core.model_persistence|core.model_persistence]]

Source: `core/model_persistence.py:586`

Kind: `method`

Signature: `_save_models_to_sql(self, models: Dict[str, Any], metadata: Dict[str, Any], version: int)`

Summary: Save models to SQL ModelRegistry table with atomic transaction handling.

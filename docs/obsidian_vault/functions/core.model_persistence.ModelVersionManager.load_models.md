---
type: method
id: core.model_persistence.ModelVersionManager.load_models
module: core.model_persistence
source: core/model_persistence.py
line_start: 966
line_end: 1024
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.model_persistence.ModelVersionManager.load_models

Defined in: [[modules/core.model_persistence|core.model_persistence]]

Source: `core/model_persistence.py:966`

Kind: `method`

Signature: `load_models(self, version: Optional[int]=None, prefer_sql: bool=True)`

Summary: Load models from a specific version (SQL first, then filesystem fallback).

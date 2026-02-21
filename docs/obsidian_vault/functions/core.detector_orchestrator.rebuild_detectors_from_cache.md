---
type: function
id: core.detector_orchestrator.rebuild_detectors_from_cache
module: core.detector_orchestrator
source: core/detector_orchestrator.py
line_start: 489
line_end: 741
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.detector_orchestrator.rebuild_detectors_from_cache

Defined in: [[modules/core.detector_orchestrator|core.detector_orchestrator]]

Source: `core/detector_orchestrator.py:489`

Kind: `function`

Signature: `rebuild_detectors_from_cache(cached_models: Dict[str, Any], cached_manifest: Optional[Dict[str, Any]], cfg: Dict[str, Any], equip: str='', current_columns: Optional[list]=None)`

Summary: Reconstruct detector objects from cached model data with feature validation.

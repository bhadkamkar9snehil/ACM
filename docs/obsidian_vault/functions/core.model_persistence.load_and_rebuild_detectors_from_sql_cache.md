---
type: function
id: core.model_persistence.load_and_rebuild_detectors_from_sql_cache
module: core.model_persistence
source: core/model_persistence.py
line_start: 1665
line_end: 1749
generated_at: 2026-02-21T06:37:09+00:00
---

# core.model_persistence.load_and_rebuild_detectors_from_sql_cache

Defined in: [[modules/core.model_persistence|core.model_persistence]]

Source: `core/model_persistence.py:1665`

Kind: `function`

Signature: `load_and_rebuild_detectors_from_sql_cache(*, train: pd.DataFrame, score: pd.DataFrame, equip: str, sql_client: Optional[Any], equip_id: int, cfg: Dict[str, Any], rebuild_from_cache_fn: Any, logger: Any=Console)`

Summary: Load cached models from SQL, align features, and rebuild detector instances.

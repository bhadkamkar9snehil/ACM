---
type: function
id: core.smart_coldstart.seed_baseline
module: core.smart_coldstart
source: core/smart_coldstart.py
line_start: 567
line_end: 705
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.smart_coldstart.seed_baseline

Defined in: [[modules/core.smart_coldstart|core.smart_coldstart]]

Source: `core/smart_coldstart.py:567`

Kind: `function`

Signature: `seed_baseline(train: pd.DataFrame, score: pd.DataFrame, sql_client: Optional[Any], equip_id: int, cfg: Dict[str, Any], equip: str='', is_coldstart: bool=False, ensure_local_index_fn: Optional[Any]=None)`

Summary: Seed training baseline when insufficient data available (batch mode).

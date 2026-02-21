---
type: function
id: core.drift.load_previous_drift_mode
module: core.drift
source: core/drift.py
line_start: 335
line_end: 361
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.drift.load_previous_drift_mode

Defined in: [[modules/core.drift|core.drift]]

Source: `core/drift.py:335`

Kind: `function`

Signature: `load_previous_drift_mode(sql_client: Optional[Any], equip_id: int, default_mode: str='FAULT')`

Summary: Load last persisted drift controller mode for hysteresis continuity.

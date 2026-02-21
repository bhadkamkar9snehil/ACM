---
type: function
id: core.drift.write_drift_controller_state
module: core.drift
source: core/drift.py
line_start: 387
line_end: 424
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.drift.write_drift_controller_state

Defined in: [[modules/core.drift|core.drift]]

Source: `core/drift.py:387`

Kind: `function`

Signature: `write_drift_controller_state(*, output_manager: Optional[Any], frame: pd.DataFrame, cfg: Dict[str, Any], score_out: Optional[Dict[str, Any]]=None, logger: Optional[Any]=None, equip: str='')`

Summary: Build and persist drift-controller payload.

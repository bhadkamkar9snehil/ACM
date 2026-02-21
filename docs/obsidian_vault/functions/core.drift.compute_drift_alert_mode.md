---
type: function
id: core.drift.compute_drift_alert_mode
module: core.drift
source: core/drift.py
line_start: 204
line_end: 332
generated_at: 2026-02-21T06:37:09+00:00
---

# core.drift.compute_drift_alert_mode

Defined in: [[modules/core.drift|core.drift]]

Source: `core/drift.py:204`

Kind: `function`

Signature: `compute_drift_alert_mode(frame: pd.DataFrame, cfg: Dict[str, Any], regime_quality_ok: bool=False, equip: str='', prev_alert_mode: str='FAULT')`

Summary: Compute drift alert mode using multi-feature detection or simple threshold.

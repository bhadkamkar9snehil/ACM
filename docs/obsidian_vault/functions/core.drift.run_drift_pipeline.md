---
type: function
id: core.drift.run_drift_pipeline
module: core.drift
source: core/drift.py
line_start: 427
line_end: 482
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.drift.run_drift_pipeline

Defined in: [[modules/core.drift|core.drift]]

Source: `core/drift.py:427`

Kind: `function`

Signature: `run_drift_pipeline(*, score_data: pd.DataFrame, frame: pd.DataFrame, score_out: Dict[str, Any], cfg: Dict[str, Any], regime_quality_ok: bool, equip: str, sql_client: Optional[Any], equip_id: int, output_manager: Optional[Any], logger: Optional[Any]=None)`

Summary: Execute drift compute, alert-mode classification, and controller persistence.

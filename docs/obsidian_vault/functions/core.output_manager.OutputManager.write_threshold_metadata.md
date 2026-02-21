---
type: method
id: core.output_manager.OutputManager.write_threshold_metadata
module: core.output_manager
source: core/output_manager.py
line_start: 1690
line_end: 1754
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.output_manager.OutputManager.write_threshold_metadata

Defined in: [[modules/core.output_manager|core.output_manager]]

Source: `core/output_manager.py:1690`

Kind: `method`

Signature: `write_threshold_metadata(self, equip_id: int, threshold_type: str, threshold_value: float, calculation_method: str, sample_count: int, train_start: Optional[datetime]=None, train_end: Optional[datetime]=None, config_signature: Optional[str]=None, notes: Optional[str]=None)`

Summary: Write adaptive threshold metadata to ACM_AdaptiveConfig.

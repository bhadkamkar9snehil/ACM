---
type: method
id: core.output_manager.OutputManager.write_fusion_metrics
module: core.output_manager
source: core/output_manager.py
line_start: 2698
line_end: 2779
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.output_manager.OutputManager.write_fusion_metrics

Defined in: [[modules/core.output_manager|core.output_manager]]

Source: `core/output_manager.py:2698`

Kind: `method`

Signature: `write_fusion_metrics(self, fusion_weights: Dict[str, float], tuning_diagnostics: Dict[str, Any], previous_weights: Optional[Dict[str, float]]=None)`

Summary: Write fusion tuning diagnostics and metrics to ACM_RunMetrics (EAV format).

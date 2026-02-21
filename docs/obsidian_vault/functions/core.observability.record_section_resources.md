---
type: function
id: core.observability.record_section_resources
module: core.observability
source: core/observability.py
line_start: 1982
line_end: 2037
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.observability.record_section_resources

Defined in: [[modules/core.observability|core.observability]]

Source: `core/observability.py:1982`

Kind: `function`

Signature: `record_section_resources(section: str, duration_s: float, mem_start_mb: float=0, mem_end_mb: float=0, mem_peak_mb: float=0, mem_delta_mb: float=0, cpu_avg_pct: float=0, equipment: str='', run_id: str='')`

Summary: Record comprehensive resource metrics for a code section.

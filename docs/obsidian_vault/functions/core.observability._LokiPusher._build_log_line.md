---
type: method
id: core.observability._LokiPusher._build_log_line
module: core.observability
source: core/observability.py
line_start: 2391
line_end: 2414
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.observability._LokiPusher._build_log_line

Defined in: [[modules/core.observability|core.observability]]

Source: `core/observability.py:2391`

Kind: `method`

Signature: `_build_log_line(self, message: str, context: Dict[str, Any])`

Summary: Build Loki line payload preserving structured context without label explosion.

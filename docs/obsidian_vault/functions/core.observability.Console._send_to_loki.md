---
type: method
id: core.observability.Console._send_to_loki
module: core.observability
source: core/observability.py
line_start: 1259
line_end: 1266
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.observability.Console._send_to_loki

Defined in: [[modules/core.observability|core.observability]]

Source: `core/observability.py:1259`

Kind: `method`

Signature: `_send_to_loki(level: str, message: str, component: Optional[str]=None, **kwargs)`

Summary: Send structured log to Loki with proper labels.

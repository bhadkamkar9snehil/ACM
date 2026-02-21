---
type: method
id: core.observability.Console.ok
module: core.observability
source: core/observability.py
line_start: 1304
line_end: 1311
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.observability.Console.ok

Defined in: [[modules/core.observability|core.observability]]

Source: `core/observability.py:1304`

Kind: `method`

Signature: `ok(message: str, component: Optional[str]=None, **kwargs)`

Summary: Success message (green). Logs as level=info with tag=success to Loki.

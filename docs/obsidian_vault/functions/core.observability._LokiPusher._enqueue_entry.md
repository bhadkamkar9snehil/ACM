---
type: method
id: core.observability._LokiPusher._enqueue_entry
module: core.observability
source: core/observability.py
line_start: 2416
line_end: 2447
generated_at: 2026-02-21T06:37:09+00:00
---

# core.observability._LokiPusher._enqueue_entry

Defined in: [[modules/core.observability|core.observability]]

Source: `core/observability.py:2416`

Kind: `method`

Signature: `_enqueue_entry(self, entry: tuple[str, Dict[str, str], str], level: str)`

Summary: Queue one Loki line with bounded-memory policy.

---
type: function
id: core.observability.close_run_span
module: core.observability
source: core/observability.py
line_start: 1040
line_end: 1057
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.observability.close_run_span

Defined in: [[modules/core.observability|core.observability]]

Source: `core/observability.py:1040`

Kind: `function`

Signature: `close_run_span(span_ctx: Optional[Any], root_span: Optional[Any], outcome: str, rows_read: int, rows_written: int)`

Summary: Close root span for a run and attach terminal attributes.

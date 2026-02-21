---
type: method
id: core.observability._PyroscopePusher._log_top_memory_allocations
module: core.observability
source: core/observability.py
line_start: 3022
line_end: 3098
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.observability._PyroscopePusher._log_top_memory_allocations

Defined in: [[modules/core.observability|core.observability]]

Source: `core/observability.py:3022`

Kind: `method`

Signature: `_log_top_memory_allocations(self, snapshot, top_n: int=10)`

Summary: Log the top N memory-allocating call sites from a tracemalloc snapshot.

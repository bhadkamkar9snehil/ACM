---
type: function
id: core.output_manager._get_insertable_columns
module: core.output_manager
source: core/output_manager.py
line_start: 225
line_end: 242
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.output_manager._get_insertable_columns

Defined in: [[modules/core.output_manager|core.output_manager]]

Source: `core/output_manager.py:225`

Kind: `function`

Signature: `_get_insertable_columns(cursor_factory: Callable[[], Any], name: str)`

Summary: Return columns excluding identity columns for safe INSERT.

---
type: method
id: core.output_manager.OutputManager._bulk_delete_analytics_tables
module: core.output_manager
source: core/output_manager.py
line_start: 3225
line_end: 3362
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.output_manager.OutputManager._bulk_delete_analytics_tables

Defined in: [[modules/core.output_manager|core.output_manager]]

Source: `core/output_manager.py:3225`

Kind: `method`

Signature: `_bulk_delete_analytics_tables(self, tables: List[str])`

Summary: PERF-OPT v11: Delete existing rows for current RunID/EquipID from multiple tables in ONE SQL batch.

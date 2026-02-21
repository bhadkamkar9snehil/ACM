---
type: method
id: core.output_manager.OutputManager._bulk_insert_sql
module: core.output_manager
source: core/output_manager.py
line_start: 868
line_end: 1045
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.output_manager.OutputManager._bulk_insert_sql

Defined in: [[modules/core.output_manager|core.output_manager]]

Source: `core/output_manager.py:868`

Kind: `method`

Signature: `_bulk_insert_sql(self, table_name: str, df: pd.DataFrame)`

Summary: Perform bulk SQL insert with optimized batching and robust commit.

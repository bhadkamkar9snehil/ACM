---
type: method
id: core.output_manager.OutputManager._delete_timeline_overlaps
module: core.output_manager
source: core/output_manager.py
line_start: 3165
line_end: 3223
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.output_manager.OutputManager._delete_timeline_overlaps

Defined in: [[modules/core.output_manager|core.output_manager]]

Source: `core/output_manager.py:3165`

Kind: `method`

Signature: `_delete_timeline_overlaps(self, tables: List[str], min_ts: pd.Timestamp, max_ts: pd.Timestamp)`

Summary: v11.1.5 FIX: Delete overlapping rows from timeline tables by TIMESTAMP RANGE.

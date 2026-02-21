---
type: function
id: core.data_loader.coerce_local_and_filter_future
module: core.data_loader
source: core/data_loader.py
line_start: 92
line_end: 129
generated_at: 2026-02-21T06:37:09+00:00
---

# core.data_loader.coerce_local_and_filter_future

Defined in: [[modules/core.data_loader|core.data_loader]]

Source: `core/data_loader.py:92`

Kind: `function`

Signature: `coerce_local_and_filter_future(df: pd.DataFrame, label: str, now_cutoff: pd.Timestamp)`

Summary: Convert timestamp index to naive local time and drop future rows.

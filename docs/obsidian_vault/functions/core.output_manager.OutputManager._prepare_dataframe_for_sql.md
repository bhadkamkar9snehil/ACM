---
type: method
id: core.output_manager.OutputManager._prepare_dataframe_for_sql
module: core.output_manager
source: core/output_manager.py
line_start: 524
line_end: 607
generated_at: 2026-02-21T06:37:09+00:00
---

# core.output_manager.OutputManager._prepare_dataframe_for_sql

Defined in: [[modules/core.output_manager|core.output_manager]]

Source: `core/output_manager.py:524`

Kind: `method`

Signature: `_prepare_dataframe_for_sql(self, df: pd.DataFrame, non_numeric_cols: Optional[set]=None)`

Summary: Prepare DataFrame for SQL insertion with robust type coercion (SQL Server safe).

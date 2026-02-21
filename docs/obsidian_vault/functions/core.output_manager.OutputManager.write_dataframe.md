---
type: method
id: core.output_manager.OutputManager.write_dataframe
module: core.output_manager
source: core/output_manager.py
line_start: 638
line_end: 821
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.output_manager.OutputManager.write_dataframe

Defined in: [[modules/core.output_manager|core.output_manager]]

Source: `core/output_manager.py:638`

Kind: `method`

Signature: `write_dataframe(self, df: pd.DataFrame, artifact_name: str, sql_table: Optional[str]=None, sql_columns: Optional[Dict[str, str]]=None, non_numeric_cols: Optional[set]=None, add_created_at: bool=False, required: bool=False)`

Summary: Write DataFrame to SQL (SQL-only; file output removed).

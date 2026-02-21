---
type: method
id: core.output_manager.OutputManager.write_table
module: core.output_manager
source: core/output_manager.py
line_start: 824
line_end: 867
---

# core.output_manager.OutputManager.write_table

Defined in: [[modules/core.output_manager]]

Source: `core/output_manager.py:824`

Kind: `method`

Signature: `write_table(self, table_name: str, df: pd.DataFrame, delete_existing: bool=False)`

Summary: Generic SQL table writer with RunID/EquipID injection and upsert routing.

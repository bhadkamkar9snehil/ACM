---
type: method
id: core.output_manager.OutputManager._load_data_from_sql
module: core.output_manager
source: core/output_manager.py
line_start: 465
line_end: 482
---

# core.output_manager.OutputManager._load_data_from_sql

Defined in: [[modules/core.output_manager]]

Source: `core/output_manager.py:465`

Kind: `method`

Signature: `_load_data_from_sql(self, cfg: Dict[str, Any], equipment_name: str, start_utc: Optional[pd.Timestamp], end_utc: Optional[pd.Timestamp], is_coldstart: bool=False)`

Summary: Load training and scoring data from SQL historian using stored procedure.

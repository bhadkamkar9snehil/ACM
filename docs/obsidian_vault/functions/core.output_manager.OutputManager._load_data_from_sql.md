---
type: method
id: core.output_manager.OutputManager._load_data_from_sql
module: core.output_manager
source: core/output_manager.py
line_start: 464
line_end: 481
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.output_manager.OutputManager._load_data_from_sql

Defined in: [[modules/core.output_manager|core.output_manager]]

Source: `core/output_manager.py:464`

Kind: `method`

Signature: `_load_data_from_sql(self, cfg: Dict[str, Any], equipment_name: str, start_utc: Optional[pd.Timestamp], end_utc: Optional[pd.Timestamp], is_coldstart: bool=False)`

Summary: Load training and scoring data from SQL historian using stored procedure.

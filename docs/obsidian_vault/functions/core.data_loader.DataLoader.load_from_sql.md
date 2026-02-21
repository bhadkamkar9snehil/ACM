---
type: method
id: core.data_loader.DataLoader.load_from_sql
module: core.data_loader
source: core/data_loader.py
line_start: 214
line_end: 504
generated_at: 2026-02-21T06:37:09+00:00
---

# core.data_loader.DataLoader.load_from_sql

Defined in: [[modules/core.data_loader|core.data_loader]]

Source: `core/data_loader.py:214`

Kind: `method`

Signature: `load_from_sql(self, cfg: Dict[str, Any], equipment_name: str, start_utc: Optional[pd.Timestamp], end_utc: Optional[pd.Timestamp], is_coldstart: bool=False)`

Summary: Load training and scoring data from SQL historian using stored procedure.

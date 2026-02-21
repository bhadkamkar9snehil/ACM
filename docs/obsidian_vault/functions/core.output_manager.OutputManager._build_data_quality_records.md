---
type: method
id: core.output_manager.OutputManager._build_data_quality_records
module: core.output_manager
source: core/output_manager.py
line_start: 1934
line_end: 2063
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.output_manager.OutputManager._build_data_quality_records

Defined in: [[modules/core.output_manager|core.output_manager]]

Source: `core/output_manager.py:1934`

Kind: `method`

Signature: `_build_data_quality_records(train_numeric: pd.DataFrame, score_numeric: pd.DataFrame, cfg: Dict[str, Any], low_var_threshold: float=0.0001)`

Summary: Build a SINGLE summary data quality record (not per-sensor).

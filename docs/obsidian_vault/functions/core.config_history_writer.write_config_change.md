---
type: function
id: core.config_history_writer.write_config_change
module: core.config_history_writer
source: core/config_history_writer.py
line_start: 54
line_end: 139
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.config_history_writer.write_config_change

Defined in: [[modules/core.config_history_writer|core.config_history_writer]]

Source: `core/config_history_writer.py:54`

Kind: `function`

Signature: `write_config_change(sql_client, equip_id: int, parameter_path: str, old_value: Any, new_value: Any, changed_by: str='SYSTEM', change_reason: str='', run_id: Optional[str]=None)`

Summary: Write config change record to ACM_ConfigHistory table.

---
type: function
id: core.config_history_writer.write_config_changes_bulk
module: core.config_history_writer
source: core/config_history_writer.py
line_start: 142
line_end: 234
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.config_history_writer.write_config_changes_bulk

Defined in: [[modules/core.config_history_writer|core.config_history_writer]]

Source: `core/config_history_writer.py:142`

Kind: `function`

Signature: `write_config_changes_bulk(sql_client, equip_id: int, changes: list, changed_by: str='SYSTEM', run_id: Optional[str]=None)`

Summary: Write multiple config changes in a single transaction.

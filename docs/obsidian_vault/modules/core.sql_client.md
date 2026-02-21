---
type: module
module: core.sql_client
source: core/sql_client.py
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - module
---

# core.sql_client

Source file: `core/sql_client.py`

Summary: no module docstring summary

## Imports from core
- none

## Top-level symbols
- [[functions/core.sql_client.SQLClient|core.sql_client.SQLClient]] (line 50, class)
- [[functions/core.sql_client.SQLClient.__init__|core.sql_client.SQLClient.__init__]] (line 69, method)
- [[functions/core.sql_client.SQLClient.from_ini|core.sql_client.SQLClient.from_ini]] (line 77, method)
- [[functions/core.sql_client.SQLClient._maybe_load_ini|core.sql_client.SQLClient._maybe_load_ini]] (line 104, method)
- [[functions/core.sql_client.SQLClient._build_conn_str|core.sql_client.SQLClient._build_conn_str]] (line 138, method)
- [[functions/core.sql_client.SQLClient.connect|core.sql_client.SQLClient.connect]] (line 187, method)
- [[functions/core.sql_client.SQLClient.close|core.sql_client.SQLClient.close]] (line 211, method)
- [[functions/core.sql_client.SQLClient.commit|core.sql_client.SQLClient.commit]] (line 218, method)
- [[functions/core.sql_client.SQLClient.rollback|core.sql_client.SQLClient.rollback]] (line 223, method)
- [[functions/core.sql_client.SQLClient.cursor|core.sql_client.SQLClient.cursor]] (line 229, method)
- [[functions/core.sql_client.SQLClient.get_cursor|core.sql_client.SQLClient.get_cursor]] (line 235, method)
- [[functions/core.sql_client.SQLClient.call_proc|core.sql_client.SQLClient.call_proc]] (line 254, method)
- [[functions/core.sql_client.SQLClient.execute|core.sql_client.SQLClient.execute]] (line 283, method)
- [[functions/core.sql_client.SQLClient.executemany|core.sql_client.SQLClient.executemany]] (line 344, method)
- [[functions/core.sql_client.SQLClient.get_equipment_id|core.sql_client.SQLClient.get_equipment_id]] (line 395, method)
- [[functions/core.sql_client.SQLClient.start_run|core.sql_client.SQLClient.start_run]] (line 425, method)
- [[functions/core.sql_client.SQLClient.finalize_run|core.sql_client.SQLClient.finalize_run]] (line 495, method)
- [[functions/core.sql_client.execute_with_deadlock_retry|core.sql_client.execute_with_deadlock_retry]] (line 537, function)
- [[functions/core.sql_client.connect_acm_sql|core.sql_client.connect_acm_sql]] (line 577, function)
- [[functions/core.sql_client.resolve_equipment_id_required|core.sql_client.resolve_equipment_id_required]] (line 602, function)
- [[functions/core.sql_client.load_config_required_from_sql|core.sql_client.load_config_required_from_sql]] (line 633, function)
- [[functions/core.sql_client.start_acm_run|core.sql_client.start_acm_run]] (line 707, function)

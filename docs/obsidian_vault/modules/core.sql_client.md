---
type: module
module: core.sql_client
source: core/sql_client.py
---

# core.sql_client

Source file: `core/sql_client.py`

Summary: no module docstring summary

## Imports from core
- none

## Top-level symbols
- [[functions/core.sql_client.SQLClient]] (line 50, class)
- [[functions/core.sql_client.SQLClient.__init__]] (line 69, method)
- [[functions/core.sql_client.SQLClient.from_ini]] (line 77, method)
- [[functions/core.sql_client.SQLClient._maybe_load_ini]] (line 104, method)
- [[functions/core.sql_client.SQLClient._build_conn_str]] (line 138, method)
- [[functions/core.sql_client.SQLClient.connect]] (line 187, method)
- [[functions/core.sql_client.SQLClient.close]] (line 211, method)
- [[functions/core.sql_client.SQLClient.commit]] (line 218, method)
- [[functions/core.sql_client.SQLClient.rollback]] (line 223, method)
- [[functions/core.sql_client.SQLClient.cursor]] (line 229, method)
- [[functions/core.sql_client.SQLClient.get_cursor]] (line 235, method)
- [[functions/core.sql_client.SQLClient.call_proc]] (line 254, method)
- [[functions/core.sql_client.SQLClient.execute]] (line 283, method)
- [[functions/core.sql_client.SQLClient.executemany]] (line 344, method)
- [[functions/core.sql_client.SQLClient.get_equipment_id]] (line 395, method)
- [[functions/core.sql_client.SQLClient.start_run]] (line 425, method)
- [[functions/core.sql_client.SQLClient.finalize_run]] (line 495, method)
- [[functions/core.sql_client.execute_with_deadlock_retry]] (line 537, function)
- [[functions/core.sql_client.connect_acm_sql]] (line 577, function)
- [[functions/core.sql_client.resolve_equipment_id_required]] (line 602, function)
- [[functions/core.sql_client.load_config_required_from_sql]] (line 633, function)
- [[functions/core.sql_client.start_acm_run]] (line 707, function)

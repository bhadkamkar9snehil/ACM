---
type: function
id: core.sql_client.start_acm_run
module: core.sql_client
source: core/sql_client.py
line_start: 707
line_end: 728
generated_at: 2026-02-21T06:37:09+00:00
---

# core.sql_client.start_acm_run

Defined in: [[modules/core.sql_client|core.sql_client]]

Source: `core/sql_client.py:707`

Kind: `function`

Signature: `start_acm_run(cli: Any, cfg: Dict[str, Any], equip_code: str, deadlock_retry_func: Optional[Callable]=None, logger: Optional[Any]=None)`

Summary: Start a run in ACM_Runs and return (run_id, window_start, window_end, equip_id).

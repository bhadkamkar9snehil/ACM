---
type: method
id: core.sql_client.SQLClient.start_run
module: core.sql_client
source: core/sql_client.py
line_start: 425
line_end: 493
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.sql_client.SQLClient.start_run

Defined in: [[modules/core.sql_client|core.sql_client]]

Source: `core/sql_client.py:425`

Kind: `method`

Signature: `start_run(self, cfg: Dict[str, Any], equip_code: str, deadlock_retry_func: Optional[Callable]=None)`

Summary: Start a run by inserting into ACM_Runs table.

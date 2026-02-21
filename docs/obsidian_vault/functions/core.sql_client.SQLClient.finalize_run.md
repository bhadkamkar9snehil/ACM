---
type: method
id: core.sql_client.SQLClient.finalize_run
module: core.sql_client
source: core/sql_client.py
line_start: 495
line_end: 534
---

# core.sql_client.SQLClient.finalize_run

Defined in: [[modules/core.sql_client]]

Source: `core/sql_client.py:495`

Kind: `method`

Signature: `finalize_run(self, run_id: str, outcome: str, rows_read: int, rows_written: int, err_json: Optional[str]=None)`

Summary: Finalize a run by updating ACM_Runs with completion status.

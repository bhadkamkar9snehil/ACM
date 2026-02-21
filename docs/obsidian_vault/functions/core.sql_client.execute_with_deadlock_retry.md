---
type: function
id: core.sql_client.execute_with_deadlock_retry
module: core.sql_client
source: core/sql_client.py
line_start: 537
line_end: 570
---

# core.sql_client.execute_with_deadlock_retry

Defined in: [[modules/core.sql_client|core.sql_client]]

Source: `core/sql_client.py:537`

Kind: `function`

Signature: `execute_with_deadlock_retry(cur: Any, sql: str, params: tuple=(), max_retries: int=3, delay: float=0.5)`

Summary: Execute SQL with automatic retry on deadlock (SQL Server error 1205).

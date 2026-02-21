---
type: function
id: core.sql_client.connect_acm_sql
module: core.sql_client
source: core/sql_client.py
line_start: 577
line_end: 599
---

# core.sql_client.connect_acm_sql

Defined in: [[modules/core.sql_client]]

Source: `core/sql_client.py:577`

Kind: `function`

Signature: `connect_acm_sql(cfg: Dict[str, Any], logger: Optional[Any]=None)`

Summary: Connect to ACM SQL using INI first, then fallback to cfg["sql"].

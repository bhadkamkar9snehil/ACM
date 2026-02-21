---
type: method
id: core.output_manager.OutputManager.__init__
module: core.output_manager
source: core/output_manager.py
line_start: 330
line_end: 403
---

# core.output_manager.OutputManager.__init__

Defined in: [[modules/core.output_manager]]

Source: `core/output_manager.py:330`

Kind: `method`

Signature: `__init__(self, sql_client=None, run_id: Optional[str]=None, equip_id: Optional[int]=None, batch_size: int=5000, enable_batching: bool=True, sql_health_cache_seconds: float=60.0, max_io_workers: int=8, batch_flush_rows: int=1000, batch_flush_seconds: float=30.0, max_in_flight_futures: int=50, maturity_state: Optional[str]=None)`

Summary: Initialize OutputManager.

---
type: function
id: core.observability.init
module: core.observability
source: core/observability.py
line_start: 584
line_end: 955
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.observability.init

Defined in: [[modules/core.observability|core.observability]]

Source: `core/observability.py:584`

Kind: `function`

Signature: `init(equipment: str='', equip_id: int=0, run_id: str='', sql_client: Optional[Any]=None, service_name: str='acm-pipeline', otlp_endpoint: str=DEFAULT_OTLP_ENDPOINT, loki_endpoint: str=DEFAULT_LOKI_ENDPOINT, pyroscope_endpoint: str=DEFAULT_PYROSCOPE_ENDPOINT, tempo_endpoint: Optional[str]=None, enable_tracing: bool=True, enable_metrics: bool=True, enable_loki: bool=True, enable_profiling: bool=True)`

Summary: Initialize observability stack.

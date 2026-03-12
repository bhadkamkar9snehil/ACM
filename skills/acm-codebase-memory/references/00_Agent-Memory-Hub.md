---
type: agent-memory
generated_at: 2026-03-12T10:56:09+00:00
---

# ACM Agent Memory Hub

This note is generated for agent-first ACM context loading.

## Quick Start
1. Read `[[../00_Home]]`
2. Read `[[../01_Modules]]`
3. Read `[[../modules/core.acm]]`
4. Read `[[../modules/core.output_manager]]`
5. Read `[[../modules/core.run_metadata_writer]]`

## Highest Symbol Density Modules
- [[modules/core.observability|core.observability]] symbols=118
- [[modules/core.output_manager|core.output_manager]] symbols=106
- [[modules/core.regimes|core.regimes]] symbols=56
- [[modules/core.fuse|core.fuse]] symbols=51
- [[modules/core.model_persistence|core.model_persistence]] symbols=41
- [[modules/core.degradation_model|core.degradation_model]] symbols=36
- [[modules/core.fast_features|core.fast_features]] symbols=36
- [[modules/core.output_manager_services|core.output_manager_services]] symbols=32
- [[modules/core.sensor_attribution|core.sensor_attribution]] symbols=30
- [[modules/core.sql_client|core.sql_client]] symbols=30
- [[modules/core.forecast_engine|core.forecast_engine]] symbols=29
- [[modules/core.resource_monitor|core.resource_monitor]] symbols=27

## Commands
1. Refresh memory:
`python scripts/manage_acm_agent_memory.py refresh --sync-repo-skill --sync-local-skill`
2. Health check:
`python scripts/manage_acm_agent_memory.py health`

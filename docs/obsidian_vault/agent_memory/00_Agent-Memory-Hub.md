---
type: agent-memory
generated_at: 2026-02-21T03:41:53+00:00
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
- [[modules/core.observability|core.observability]] symbols=108
- [[modules/core.output_manager|core.output_manager]] symbols=74
- [[modules/core.regimes|core.regimes]] symbols=57
- [[modules/core.degradation_model|core.degradation_model]] symbols=36
- [[modules/core.fuse|core.fuse]] symbols=34
- [[modules/core.model_persistence|core.model_persistence]] symbols=34
- [[modules/core.fast_features|core.fast_features]] symbols=33
- [[modules/core.forecast_engine|core.forecast_engine]] symbols=31
- [[modules/core.sensor_attribution|core.sensor_attribution]] symbols=31
- [[modules/core.resource_monitor|core.resource_monitor]] symbols=27
- [[modules/core.sql_client|core.sql_client]] symbols=22
- [[modules/core.pipeline_types|core.pipeline_types]] symbols=21

## Commands
1. Refresh memory:
`python scripts/manage_acm_agent_memory.py refresh --sync-repo-skill --sync-local-skill`
2. Health check:
`python scripts/manage_acm_agent_memory.py health`

---
name: acm-codebase-memory
description: Use when an agent needs persistent ACM codebase memory, including module ownership, runtime flow, function lookup, and SQL output interpretation, backed by generated Obsidian graph notes and syncable skill references.
---

# ACM Codebase Memory

## Purpose
Keep ACM context persistent and agent-usable across sessions.

## Agent-First Workflow
1. Refresh memory graph and artifacts:
`python scripts/manage_acm_agent_memory.py refresh --sync-repo-skill --sync-local-skill`
2. Run health check:
`python scripts/manage_acm_agent_memory.py health`
3. Load references in this order:
- `references/00_Agent-Memory-Hub.md`
- `references/01_Runtime-Critical-Path.md`
- `references/02_Module-Ownership.md`
- `references/03_SQL-Output-Map.md`
- `references/00_Home.md`
- `references/01_Modules.md`
- `references/03_Runtime-Flow.md`
- `references/04_Outputs-and-Status.md`
- `references/memory_index.json`

## Rules
1. Treat generated memory files as source of navigation truth.
2. Regenerate memory after major refactor or ownership movement.
3. Keep entrypoint semantics aligned with `python -m core.acm`.
4. Keep run outcome semantics stable: `OK`, `DEGRADED`, `NOOP`, `FAIL`.
5. Use ASCII only for generated and maintained docs.

## Commands
```powershell
python scripts/manage_acm_agent_memory.py refresh --sync-repo-skill --sync-local-skill
python scripts/manage_acm_agent_memory.py health
python scripts/manage_acm_agent_memory.py sync-repo-skill
python scripts/manage_acm_agent_memory.py sync-local-skill
```

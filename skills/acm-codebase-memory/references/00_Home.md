---
type: index
auto-updated: true
generated_at: 2026-03-12T12:53:31+00:00
---

# ACM Obsidian Knowledge Graph

Single source of truth for ACM codebase knowledge.

- **Generated notes** (`modules/`, `functions/`): auto-rebuilt from `core/*.py` — do not edit manually
- **Knowledge notes** (`knowledge/`): hand-authored — edit these to capture decisions, bugs, context

## Snapshot (auto-generated)
- modules: 55
- symbols (functions/classes/methods): 1087
- generated_at_utc: 2026-03-12T12:53:31+00:00

## Generated — Codebase Navigation
- [[01_Modules]] — all core modules
- [[02_Functions]] — all functions and classes
- [[03_Runtime-Flow]] — pipeline stage sequence
- [[04_Outputs-and-Status]] — SQL output tables and outcome codes

## Knowledge — Authored Reference
- [[knowledge/Pipeline-Stages]] — detailed per-stage breakdown with line numbers
- [[knowledge/Detector-Ensemble]] — six detectors, fusion logic, weight rules
- [[knowledge/Model-Lifecycle]] — COLDSTART → LEARNING → CONVERGED, promotion criteria
- [[knowledge/Architecture-Decisions]] — all-time bug catalogue and architectural rules
- [[knowledge/Config-Schema]] — ACM_Config table, all key paths, auto-tune map
- [[knowledge/SQL-Schema]] — all output tables, column names, timestamp rules
- [[knowledge/Known-Equipment]] — Wind Farm A fleet, fault history, batch commands
- [[knowledge/Version-History]] — changelog from v11.4.0 to current

## Refresh Command
```
python scripts/manage_acm_agent_memory.py refresh --sync-repo-skill
```

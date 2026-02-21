# Obsidian ACM Skill Graph Guide

## Goal
Create a persistent, searchable memory layer for ACM so code navigation and change safety do not depend on session memory.

## What This Adds
1. Generated linked notes for `core/*.py` in `docs/obsidian_vault/`.
2. A repeatable generator script:
`python scripts/build_acm_obsidian_graph.py`
3. Agent memory manager script:
`python scripts/manage_acm_agent_memory.py`
4. A repository skill (`skills/acm-codebase-memory/`) that agents can load directly.
5. A sync path into local CODEX skills so agent memory is reusable across sessions.

## Daily Workflow
1. Refresh full agent memory after significant code movement:
`python scripts/manage_acm_agent_memory.py refresh --sync-repo-skill --sync-local-skill`
2. Open repository as an Obsidian vault.
3. Start from `docs/obsidian_vault/00_Home.md`.
4. Navigate to `01_Modules`, then module notes, then symbol notes.
5. Use local graph and backlinks to trace dependencies before edits.

## Agent Workflow
1. Load skill: `acm-codebase-memory`.
2. Read synced references from `skills/acm-codebase-memory/references/`.
3. Use `memory_index.json` for machine-readable module and dependency lookup.
4. Re-run `health` command before high-risk refactor:
`python scripts/manage_acm_agent_memory.py health`

## Obsidian Features to Enable
1. Core plugin: Graph view.
2. Core behavior: wikilinks for internal linking.
3. Core behavior: automatic internal link updates on file rename.

## Optional Plugin Stack
1. Obsidian Skills (`kepano/obsidian-skills`) for structured assistant prompts in vault workflows.
2. Dataview (`blacksmithgu/obsidian-dataview`) for query-driven dashboards.
3. Juggl (`HEmile/obsidian-juggl`) for more advanced graph exploration.
4. Obsidian Git (`Vinzent03/obsidian-git`) for vault history and sync.

## Adapted Patterns from External Projects
This repo now adapts these ideas for agent-managed memory:
1. Vault-first structured documentation workflow from `nemocake/claude-obsidian-assistant`.
2. Command-oriented memory lifecycle (`setup/health/reseed/upgrade` style) from `agenticnotetaking/arscontexta`.
3. Three-space separation adapted for ACM:
   - `docs/obsidian_vault/` for graph and human navigation
   - `docs/obsidian_vault/agent_memory/` for machine-usable memory packets
   - `skills/acm-codebase-memory/` for agent-consumable references

## Safety Notes
1. Community plugins are optional and should be reviewed before enabling.
2. Keep generated graph notes in git so team context is shared.
3. Do not edit generated module and function notes manually.
4. Add manual notes in separate files and link to generated notes.

## Recommended Manual Notes
1. `docs/obsidian_vault/10_Refactor-Log.md` for extraction decisions and rationale.
2. `docs/obsidian_vault/11_Known-Risks.md` for fragile paths and regression risks.
3. `docs/obsidian_vault/12_Validation-History.md` for parity evidence by phase.

## Regeneration Rule
Regenerate when one of these happens:
1. function moved between files
2. module ownership changed
3. entrypoint or lifecycle flow changed
4. major refactor PR merged into integration branch

## Commands
```powershell
python scripts/build_acm_obsidian_graph.py
python scripts/manage_acm_agent_memory.py refresh --sync-repo-skill --sync-local-skill
python scripts/manage_acm_agent_memory.py health
python scripts/manage_acm_agent_memory.py sync-repo-skill
python scripts/manage_acm_agent_memory.py sync-local-skill
```

## Command Mapping
1. `refresh`: rebuild graph and regenerate memory packets.
2. `health`: verify required memory files and skill references.
3. `sync-repo-skill`: publish fresh memory into repo skill references.
4. `sync-local-skill`: install/update local CODEX skill for cross-session agent use.

# Obsidian ACM Skill Graph Guide

## Goal
Create a persistent, searchable memory layer for ACM so code navigation and change safety do not depend on session memory.

## What This Adds
1. Generated linked notes for `core/*.py` in `docs/obsidian_vault/`.
2. A repeatable generator script:
`python scripts/build_acm_obsidian_graph.py`
3. A skill workflow that loads graph notes first before major ACM changes.

## Daily Workflow
1. Regenerate graph notes after significant code movement:
`python scripts/build_acm_obsidian_graph.py`
2. Open repository as an Obsidian vault.
3. Start from `docs/obsidian_vault/00_Home.md`.
4. Navigate to `01_Modules`, then module notes, then symbol notes.
5. Use local graph and backlinks to trace dependencies before edits.

## Obsidian Features to Enable
1. Core plugin: Graph view.
2. Core behavior: wikilinks for internal linking.
3. Core behavior: automatic internal link updates on file rename.

## Optional Plugin Stack
1. Obsidian Skills (`kepano/obsidian-skills`) for structured assistant prompts in vault workflows.
2. Dataview (`blacksmithgu/obsidian-dataview`) for query-driven dashboards.
3. Juggl (`HEmile/obsidian-juggl`) for more advanced graph exploration.
4. Obsidian Git (`Vinzent03/obsidian-git`) for vault history and sync.

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

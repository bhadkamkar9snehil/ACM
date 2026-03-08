# Agent Task Planner: Structlog Migration

Audience: Agents only (Codex / Claude / Gemini)  
Status: Active  
Source Design: `docs/AGENT_STRUCTLOG_MIGRATION.md`

## How To Use This File
- Treat this as the authoritative task tracker for the migration.
- Update status inline as work progresses.
- Keep task order unless dependencies change.

Legend: `[ ]` pending, `[~]` in progress, `[x]` done, `[!]` blocked

## Phase 0: Prep / Baseline
- [x] Remove runtime flag dependency (structlog-on by default, no toggles required)
- [ ] Confirm current console formatting expectations (sample output)
- [ ] Capture a baseline run log for comparison (no structlog)

## Phase 1: Add Structlog Core
- [x] Add `structlog` dependency in `pyproject.toml`
- [x] Add structlog init function in `core/observability.py`
- [x] Wire structlog init into `init_observability()`
- [x] Remove `ACM_STRUCTLOG_*` runtime flags and use single structlog path
- [x] Emit to structlog in `Console.debug/info/warn/error/ok` (primary path)
- [x] Ensure `Console.status/header/section` unchanged
- [ ] Run batch once and verify no startup/render crashes

## Phase 2: Dual-Path Console Output
- [x] Implement optional structlog console rendering path
- [x] Keep Loki pusher path unchanged
- [ ] Verify console output parity (or document deliberate differences)
  - Note: structlog console rendering is default and always on.
  - Default console view is compact (`timestamp + level + component + message`).
  - Verbose mode is code-controlled (no runtime env toggle).
  - Beautification: redundant `[LEVEL]` / `[COMPONENT]` prefixes are stripped from message text.
  - Console renderer uses `structlog.dev.ConsoleRenderer` + `RichTracebackFormatter` (website-style standard).
  - Profile breakdown logs (Top CPU / Top Memory) use `[PROFILE]` column-aligned output (no `>>>` lane).

## Phase 3: Single Event Dict Source of Truth
- [x] Centralize event dict assembly in Console
- [x] Use structlog processors on event dict
- [x] Adapt Loki pusher to consume processed dict
- [ ] Verify Loki labels remain unchanged

## Phase 4: Optional Call-Site Migration
- [ ] Identify candidate modules for direct structlog usage (low-risk)
- [ ] Migrate 1-2 modules as examples (optional)
- [ ] Document pattern for future migration

## Validation Checklist (Per Phase)
- [ ] No regression in console output
- [ ] Loki still receives expected labels
- [ ] Traces/Metrics/Profiling unaffected
- [x] No runtime feature flags for structlog path

## Rollback Plan
- [ ] Rollback requires code revert (no runtime flags)
- [ ] Ensure dependency pin can be reverted if needed

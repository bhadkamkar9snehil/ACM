# Agent-Only Design: Structlog-Only Logging Migration (ACM)

Status: Active
Audience: Agents only (Codex / Claude / Gemini)
Scope: Console + Loki logging path in `core/observability.py`
Non-goal: Change traces/metrics/profiling backends (Tempo/Prometheus/Pyroscope)

## 1) Current Target Architecture
- `Console.*` is the single logging API used by ACM modules.
- Each log call creates one normalized event dict.
- Event dict is processed by structlog processors.
- Console output uses `structlog.dev.ConsoleRenderer` (colors forced on).
- Loki receives structured labels/context from the same processed event.
- No runtime feature flags for structlog behavior.

## 2) Design Principles
- No runtime toggles (`ACM_STRUCTLOG_*` removed from behavior control).
- One canonical rendering style in parent and child processes.
- Message readability first; avoid duplicated prefixes in message body.
- Keep Loki labels stable for dashboard/query continuity.

## 3) Implemented Path
1. Build event:
   - Keys: `event`, `level`, `component`, plus context (`equipment`, `equip_id`, `run_id`) and caller kwargs.
2. Normalize message:
   - Strip redundant leading `[INFO]`, `[WARN]`, `[COMPONENT]` prefixes.
3. Process with structlog:
   - `merge_contextvars`
   - `add_log_level`
   - timestamp processor
4. Render to console:
   - `ConsoleRenderer` with explicit columns and rich traceback formatter.
   - `force_colors=True` to keep colors in piped output.
5. Emit to Loki:
   - Reuse processed event dict.
   - Preserve component/level/run labels and filtering behavior.

## 4) Console Standard
- Renderer: `structlog.dev.ConsoleRenderer`
- Exception formatter: `RichTracebackFormatter(show_locals=True, word_wrap=True)`
- Column layout:
  - timestamp
  - level
  - component
  - event
- Extra key/value pairs are hidden from console for readability (still sent to Loki context).

## 5) Remaining Work
- Validate Loki label parity after migration (`component`, `level`, `equip_id`, `run_id`, trace correlation fields).
- Decide final behavior for `Console.status/header/section`:
  - Currently console-only and rendered through structlog style, no Loki push.
- Optional: migrate selected modules to direct `structlog.get_logger()` where beneficial.

## 6) Rollback
- No runtime flag rollback path.
- Rollback is code-level revert of `core/observability.py` (and any dependent formatting changes).

## 7) Acceptance Checklist
- [x] Structlog is the only runtime logging path.
- [x] No `ACM_STRUCTLOG_*` runtime behavior toggles required.
- [x] Console logs are colored and style-consistent across parent/child process output.
- [ ] Loki label parity confirmed in Grafana queries.
- [ ] Full batch run validated end-to-end.


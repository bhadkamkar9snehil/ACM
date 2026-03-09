# ACM — Claude Code Instructions

This file is loaded automatically by Claude Code at the start of every session.
All rules here are **non-negotiable** and override any default Claude behavior.

---

## SESSION START PROTOCOL (MANDATORY — do this before ANYTHING else)

At the start of every session, run these three commands and report the output:

```powershell
python scripts/acm_session_start.py
git status && git log --oneline -5
```

Then read `docs/KNOWN_ISSUES.md` and summarize the open CRITICAL and HIGH items to the user.

**Do not answer any question, write any code, or touch any file until this briefing is done.**

---

## TESTING DOCTRINE (NON-VIOLATABLE)

The ONLY valid ways to test or diagnose ACM:

1. **Batch runner** — `python scripts/sql_batch_runner.py --equip <EQUIP> --tick-minutes 1440 --max-batches N`
2. **sqlcmd queries** — `sqlcmd -S "<server>" -d ACM -E -Q "SELECT ..."`
3. **Reading log files** — in `logs/batch_runner_YYYYMMDD_HHMMSS.log`

**NEVER:**
- Write standalone diagnostic scripts to "simulate" or "validate" ACM behavior
- Create test harnesses outside the standard batch runner
- Truncate, filter, or limit console output in any way (`Select-Object -First`, `-Last`, `| head`, etc.)
- Use `print()` — use `Console.info/warn/error/ok/status/header` from `core/observability.py`

---

## WARN BEFORE BREAKING (MANDATORY GATE)

Before ANY edit to these 5 files, stop and explicitly state:
- What could break
- Which running ACM processes would be affected
- Ask for confirmation before proceeding

**Protected files:**
- `core/acm.py`
- `core/detector_orchestrator.py`
- `core/regimes.py`
- `core/fuse.py`
- `core/model_persistence.py`

---

## CODE QUALITY RULES (NON-NEGOTIABLE)

These are the rules you will be corrected on if violated. They are encoded here so you don't need to be told again.

| Rule | Detail |
|------|--------|
| No wrappers | Never write a function that just converts types and calls another function |
| No fallback paths | No `if HAS_POLARS`, no pandas fallback, no try/except around imports |
| Polars is a hard dependency | `import polars as pl` directly — no conditional import |
| No `return_type` parameters | Functions have a single return type, always |
| No asset-specific logic | ACM must work identically on any equipment. No wind farm names, turbine IDs, or domain-specific assumptions |
| No diagnostic scripts | See Testing Doctrine above |
| No backward-compat shims | If something is removed, remove it completely |
| Robust stats only | median/MAD not mean/std. `std_robust = mad × 1.4826` |
| Anomaly threshold config-driven | Always `thresholds.alert_z` (default 3.0), never hardcoded |

---

## SOURCE CONTROL WORKFLOW

**Branch naming:**
- Bug fixes: `fix/vNN-NN-NN-short-description`
- New features: `feature/short-description`

**Merge rules:**
- NEVER merge to `main` directly
- Always push to a feature/fix branch
- PRs are reviewed before merging

**Every non-trivial commit must:**
1. Bump the PATCH version in `utils/version.py` (semver: MAJOR.MINOR.PATCH)
2. Add a changelog entry at the **TOP** of the comment block in `utils/version.py` (newest-first)
3. Use HEREDOC commit format with Co-Authored-By footer:

```bash
git commit -m "$(cat <<'EOF'
type(vNN.NN.NN): Short description

Longer explanation of what changed and why.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

**After editing `configs/config_table.csv`:**
```powershell
python scripts/sql/populate_acm_config.py
```
This is the ONLY way to push CSV changes to the live SQL database. Not optional.

**SQL schema changes:**
- NEVER edit install scripts and call it done
- ALWAYS create a numbered migration script: `scripts/sql/migrations/v11/NNN_description.sql`
- Migrations must be idempotent (safe to run twice)

---

## MULTI-AGENT COORDINATION

When Codex is active on a branch:
1. Run `git branch -a` at session start to see all in-flight branches
2. Claude does NOT touch files that Codex has modified on its branch
3. Announce which files you are taking before starting any implementation
4. If conflict risk exists, resolve by sequencing (finish one agent's work before the other starts)

---

## PIPELINE ARCHITECTURE (always-on facts)

- **Entry point:** `core/acm.py` — NOT `core/acm_main.py` (does not exist as orchestrator)
- **No ONLINE/OFFLINE modes** — removed in v11.8.0. Use `--force-retrain` for manual override
- **`force_retraining` is CLI-only** — `CONTINUOUS_LEARNING=True` is NOT a force flag
- **Timestamp is the DataFrame index** (DatetimeIndex named "EntryDateTime") throughout the pipeline
  - Write services that need Timestamp as a column MUST call `reset_index()` first
- **Regime clustering uses raw sensors only** — never z-scores (v11.4.0 fix)
- **Calibrated z-scores are NOT re-normalized** — ScoreCalibrator output passes through fusion unchanged (v11.9.0 fix)
- **`meta` can be dict or DataMeta** — always use `meta.get(k, default) if isinstance(meta, dict) else getattr(meta, k, default)`

---

## AVAILABLE SKILLS

Use these by invoking them explicitly when the task matches:

| Skill | Invoke when | Location |
|-------|-------------|----------|
| `commit-changelog` | Committing changes, bumping version, writing changelog | `.claude/skills/commit-changelog/SKILL.md` |
| `bug-fix-plan` | Investigating or fixing any bug | `.claude/skills/bug-fix-plan/SKILL.md` |
| `log-triage` | Reading batch runner logs, diagnosing failures | `.claude/skills/log-triage/SKILL.md` |
| `ACM` | All ACM pipeline tasks, SQL queries, detector tuning | `.claude/skills/ACM/SKILL.md` |
| `Grafana` | Dashboard development | `.claude/skills/Grafana/SKILL.md` |

---

## KEY FILE LOCATIONS

```
core/acm.py                          Main pipeline orchestrator
core/detector_orchestrator.py        score_all_detectors()
core/regimes.py                      run_scoring_regime_stage(), regime clustering
core/fuse.py                         Calibration, fusion, CUSUM episodes
core/model_lifecycle.py              MaturityState, PromotionCriteria
core/model_persistence.py            Save/restore detectors
core/ewm_baseline.py                 EWMBaselineManager (7th detector, zero-day)
core/regime_binner.py                ControlVariableBinner / OnlinePCABinner
scripts/sql_batch_runner.py          Production batch runner
scripts/acm_session_start.py         Session briefing script
scripts/sql/populate_acm_config.py   Sync config_table.csv → SQL
utils/version.py                     Version + changelog (v11.16.2)
configs/config_table.csv            ~355+ config parameters
docs/KNOWN_ISSUES.md                 Current open issues register
docs/ACM_ARCHITECTURE_DECISIONS.md  All-time bug catalogue
data/event_info.csv                  Known Wind Farm A fault events
```

---

## COMMON PITFALLS (things Claude has been corrected on before)

Do not repeat these mistakes:

1. Using `core/acm_main.py` — it is NOT the entry point
2. Adding `if HAS_POLARS` guards or pandas fallback paths
3. Writing diagnostic scripts to "test" ACM behavior
4. Using `LIMIT` instead of `TOP` in T-SQL
5. Using `Equipment.Active` instead of `Equipment.Status = 'Active'`
6. Using `ACM_HealthTimeline.Zone` instead of `ACM_HealthTimeline.HealthZone`
7. Inserting into `ACM_Config` without supplying `ValueType` (NOT NULL column)
8. Calling `build_contribution_timeline()` without `reset_index()` first
9. Hardcoding `threshold=1.0` or any anomaly threshold — always config-driven
10. Re-normalizing calibrated z-scores in fusion
11. Treating `coldstart_complete` as "is this a coldstart batch" — it means "can_proceed"
12. Making `CONTINUOUS_LEARNING` act as a force-retrain flag

---
name: commit-changelog
description: "ACM commit and changelog skill. Activate for: committing changes, bumping version, writing changelog entries, pushing to branch. Handles version bump, version.py changelog update, and correct HEREDOC commit format automatically."
---

# Commit + Changelog Skill

Activated when the user says: "commit", "version bump", "changelog", "push changes", "save work", or similar.

---

## STEP 1 — Read current state

Run these in parallel:

```bash
git status
git diff --staged
git log --oneline -5
```

Also read `utils/version.py` (first 25 lines) to get current version and changelog format.

---

## STEP 2 — Determine version bump

### Which track are you on?

Check `git branch --show-current` and `__version__` in `utils/version.py`:

- **2026.2 branch** (`integration/2026.2-*`, `refactor/2026.2-*`, `feature/2026.2-*`):
  Version format is `2026.2.N` — increment N by 1 for every commit regardless of change type.
  Example: `2026.2.3` → `2026.2.4`

- **Main/runtime track** (`main`, `feature/v11-*`, `fix/v11-*`):
  Version format is `MAJOR.MINOR.PATCH` semver.

  | Change type | Bump | Example |
  |------------|------|---------|
  | Bug fix | PATCH | 11.16.2 → 11.16.3 |
  | New feature / new detector / new module | MINOR | 11.16.x → 11.17.0 |
  | Breaking architecture change | MAJOR | 11.x.x → 12.0.0 |
  | Docs, refactor, chore (no behavior change) | PATCH | 11.16.2 → 11.16.3 |

State the proposed new version explicitly before proceeding.

---

## STEP 3 — Write changelog entry in version.py

### 2026.2 branch format (EXACT — newest entry at TOP):

```python
# 2026.2.4 (2026-03-15) -- Short description of what changed
#
# 1. file.py: What changed and why (root cause -> fix)
# 2. other_file.py: What changed and why
#
# Co-Authored-By: Claude Sonnet 4.6
```

### Main track format (EXACT — newest entry at TOP):

```python
# v11.16.3 (2026-03-09) -- Short description of what changed
#
# 1. file.py: What changed and why (root cause -> fix)
# 2. other_file.py: What changed and why
#
# Co-Authored-By: Claude Sonnet 4.6
```

**Rules:**
- Use `--` not `—` (ASCII only — Windows cp1252 console)
- Use `->` not `→` (ASCII only)
- Insert the new entry ABOVE the existing top entry
- One numbered item per changed file/component
- Always include the date (today)
- Keep entries factual: root cause -> fix, not just "fixed X"

After writing the entry, stage `utils/version.py`:
```bash
git add utils/version.py
```

---

## STEP 4 — Commit with HEREDOC format

**MANDATORY FORMAT** — always use HEREDOC, never inline -m with escaped quotes:

```bash
git commit -m "$(cat <<'EOF'
type(2026.2): Short imperative description (50 chars max)

- What changed and why (root cause -> fix)
- Second change if applicable
- Third change if applicable

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

**Type prefix:**
- `fix` — bug fixes
- `feat` — new features
- `chore` — refactor, docs, maintenance
- `perf` — performance improvements

**2026.2 branch example:**
```bash
git commit -m "$(cat <<'EOF'
fix(2026.2): raise coldstart attempt ceiling to match --max-batches

- scripts/sql_batch_runner.py: max_coldstart_attempts was hardcoded at
  10. Derive from max_batches when set so full replay budget applies.
- utils/version.py: Bump to 2026.2.4, add changelog entry.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

**Main track example:**
```bash
git commit -m "$(cat <<'EOF'
fix(v11.16.3): Regime basis fallback for generic sensor names

- core/regimes.py: When _classify_tag() returns no operating cols,
  fall back to all numeric raw sensors as regime basis. HDBSCAN
  now works for sensor_N_avg naming conventions.
- utils/version.py: Bump to v11.16.3, add changelog entry

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## STEP 5 — Report and remind

After committing, report:
- Branch name (from `git branch --show-current`)
- Commit hash (from `git log --oneline -1`)
- New version number
- **Reminder: push to feature branch, NOT main**

```bash
git push origin <branch-name>
```

If the branch has no upstream yet:
```bash
git push -u origin <branch-name>
```

---

## RULES

- NEVER merge to `main` directly
- NEVER use `--no-verify` (do not skip hooks)
- NEVER amend a published commit
- ALWAYS bump version before committing — no commits at same version as previous commit
- On 2026.2 branches: use `2026.2.N` version format, never `v11.x.x`
- On main track branches: use `MAJOR.MINOR.PATCH` semver, never `2026.2.N`
- After editing `configs/config_table.csv`: run `python scripts/sql/populate_acm_config.py` and stage the result before committing
- SQL migration scripts (`scripts/sql/migrations/v11/NNN_*.sql`) must be staged with their associated code changes

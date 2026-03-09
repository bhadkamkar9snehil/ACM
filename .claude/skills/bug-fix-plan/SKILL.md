---
name: bug-fix-plan
description: "ACM bug fix planning skill. PROACTIVELY activate for: any bug, broken behavior, 'what's wrong', investigation, 'fix this', errors, failures. Enforces root-cause-first systemic fix planning. No shortcuts, no wrappers, no jugaad. Requires explicit confirmation before touching any of the 5 protected files."
---

# Bug Fix Plan Skill

Activated when the user says: "fix", "bug", "broken", "wrong", "investigate", "why is", "what's causing", "error in", or similar.

**MANDATORY SEQUENCE: Do not write a single line of code until all 5 steps are documented.**

---

## STEP 1 — ROOT CAUSE (not the symptom)

Answer these exactly:
1. What is the **exact root cause**? (a specific line, a wrong assumption, a missing call, a bad default)
2. In which **file and function** does it originate? (file:line)
3. What **type** of bug is this?
   - Logic bug (code does something unintended)
   - Data contract violation (wrong shape, wrong type, wrong index state)
   - Design flaw (the architecture is wrong — needs structural change, not a patch)

If you cannot pinpoint a specific line, read the code before proceeding. Do not guess.

---

## STEP 2 — IMPACT SURFACE

List:
- Every file that will be modified
- Which ACM pipeline phase(s) are touched (Data Load / Feature Engineering / Detector / Scoring / Lifecycle / Fusion / Persistence)
- Is a SQL migration needed? (schema change, new column, new table)
- Will this affect a currently running ACM batch? (if yes, warn explicitly)

---

## STEP 3 — PROPOSED FIX

State the fix clearly. Before proposing it, self-check:

**REJECT the fix if it:**
- Adds a wrapper function (a function that just converts types and calls another function)
- Adds a fallback path (`if HAS_POLARS`, `try: import polars`, pandas fallback)
- Adds a `return_type` parameter
- Returns more than one type
- Uses any asset-specific logic (wind farm names, turbine IDs, sensor naming conventions)
- Is a "quick fix" that masks the root cause rather than eliminating it
- Adds backward-compatibility shim for removed functionality

**The fix must:**
- Eliminate the root cause, not work around it
- Be the same change you would make if this were a greenfield implementation
- If a SQL migration is required, name the migration file (`NNN_description.sql`) before writing any code

State: "This fix is systemic because ___."

---

## STEP 4 — RISK + CONFIRMATION GATE

Answer: What could break?

**Protected files — FULL STOP if any of these are touched:**

| File | Risk if changed incorrectly |
|------|----------------------------|
| `core/acm.py` | Entire pipeline fails or silently produces wrong output |
| `core/detector_orchestrator.py` | All detector scoring breaks |
| `core/regimes.py` | Regime detection / lifecycle state management breaks |
| `core/fuse.py` | Calibration, fusion, episode detection breaks |
| `core/model_persistence.py` | Model save/load corrupts; lifecycle state lost |

**If any protected file is in the impact surface:**
```
⚠️ PROTECTED FILE: [filename]
This change could break [specific thing].
Confirming before proceeding. Do you want me to continue?
```

Do NOT proceed until the user explicitly confirms.

---

## STEP 5 — VERIFICATION

State exactly how we will know the fix worked:

1. **Batch runner command** to run after the fix:
   ```powershell
   python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 --tick-minutes 1440 --max-batches N
   ```

2. **Log pattern** to look for (what a successful run produces):
   - e.g., "Promoted to CONVERGED" instead of "regime_quality_ok=False"

3. **SQL query** to verify output (if applicable):
   ```sql
   SELECT TOP 5 MaturityState, ConsecutiveRuns FROM ACM_ActiveModels WHERE EquipID = 5010 ORDER BY CreatedAt DESC
   ```

---

## AFTER APPROVAL — IMPLEMENT

Only after the user approves the plan:
1. Implement the fix
2. If a SQL migration is needed, create it at `scripts/sql/migrations/v11/NNN_description.sql`
3. If `configs/config_table.csv` changed, run `python scripts/sql/populate_acm_config.py`
4. Use the `commit-changelog` skill to commit with proper version bump and changelog

---

## PROHIBITED OUTPUTS (never produce these)

- "Here's a quick fix..."
- "As a workaround..."
- "We can add a fallback..."
- "For backward compatibility..."
- Any function named `_convert_*`, `_wrap_*`, `_ensure_type_*`
- Any `try: import polars` block
- Any `if HAS_POLARS:` guard
- Any hardcoded equipment name, turbine ID, or sensor keyword

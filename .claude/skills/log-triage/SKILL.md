---
name: log-triage
description: "ACM log triage skill. PROACTIVELY activate for: 'check logs', 'what's wrong', 'look at logs', 'batch failed', 'run failed', 'what happened', pasted log output. Reads full log, scans against known failure pattern catalogue, outputs structured diagnosis with file:line pointers."
---

# Log Triage Skill

Activated when the user says: "check logs", "what's wrong", "look at the logs", "batch failed", "what happened", "run failed", "diagnose", or pastes raw log output.

---

## STEP 1 — Find the log

If the user did not paste the log or give a path, find the latest log file:

```powershell
powershell -Command "Get-ChildItem logs -Filter *.log | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | Format-Table Name, LastWriteTime, Length"
```

Read the **most recent** log file in FULL. **Never truncate.** If the file is large, read all of it — every line matters.

---

## STEP 2 — Scan against the pattern catalogue

Check each pattern in order. Stop at first match and note it, then continue checking for additional issues (a run can have multiple problems).

### PATTERN CATALOGUE

```
□ P1  "Identified N/N novel points"
      → Regime distance threshold too tight
      → Root: P95 threshold (should be P99) + no floor ratio clamp
      → Fix: regimes.unknown.distance_percentile=99, distance_threshold_floor_ratio=1.5
      → File: core/regimes.py (build_distance_threshold, ~line 580)
      → Fixed in v11.15.6 — if still appearing, check config was pushed

□ P2  "k_max: N->M" appears every batch / auto-tune values changing every batch
      → ACM_Config upsert not persisting auto-tune changes
      → Root: log_auto_tune_changes() wrote to ACM_ConfigHistory only, not ACM_Config
      → Fix: _upsert_acm_config() MERGE in config_history_writer.py
      → File: core/config_history_writer.py (_upsert_acm_config)
      → Fixed in v11.15.6

□ P3  "quality_ok=False" / "regime_quality_ok=False" every batch
      → Could be P1 (novel points) OR stale manifest
      → Check: is "Identified N/N novel points" also present?
      → If yes: P1. If no: stale manifest — look for "regime_quality_ok" being set from cache
      → File: core/detector_orchestrator.py (removed stale assignment in v11.15.4)

□ P4  "Cannot insert NULL into column 'ValueType'" / NULL ValueType
      → ACM_Config MERGE missing ValueType column (NOT NULL, no default)
      → Fix: _infer_value_type() helper must supply ValueType in both INSERT and UPDATE
      → File: core/config_history_writer.py (_upsert_acm_config)
      → Fixed in v11.15.8

□ P5  "ContributionTimeline skipped" / "build returned None"
      → build_contribution_timeline() got frame with DatetimeIndex (not Timestamp column)
      → Fix: reset_index() + rename before calling build_contribution_timeline()
      → File: core/output_manager_services.py (write_contribution_timeline_from_frame_service)
      → Fixed in v11.15.7

□ P6  "n_features_in_" mismatch / "X has N features, but StandardScaler is expecting M"
      → Model cache stale — feature hash changed, or _IdentityScaler reload bug
      → If StandardScaler expecting 0: _IdentityScaler serialization bug (v11.15.15)
      → If feature count mismatch: compute_stable_feature_hash() change or schema drift
      → File: core/regimes.py (regime_state_to_model), core/detector_orchestrator.py
      → Fixed in v11.15.15 (_IdentityScaler), v11.15.4 (hash schema-only)

□ P7  "COLDSTART" not advancing / stuck in coldstart across multiple batches
      → smart_coldstart.py check_status() using wrong gate
      → Check: is ACM_ActiveModels.RegimeMaturityState being queried? (not ModelRegistry SP)
      → File: core/smart_coldstart.py (check_status, _load_progress)
      → Fixed in v11.15.10

□ P8  "LEARNING" not promoting to CONVERGED / consecutive_runs not incrementing
      → One of 3 causes:
        (a) baseline contamination blocking promotion ("contaminated" verdict) — EXPECTED if training on fault data, not a bug
        (b) trigger_refit firing unconditionally (was fixed v11.15.9)
        (c) PromotionCriteria defaults too strict (was fixed v11.15.10)
      → Check logs for: "contamination verdict", "refit request", "consecutive_runs=N"
      → File: core/model_lifecycle.py (PromotionCriteria), core/config_history_writer.py

□ P9  "contaminated" verdict blocking promotion
      → assess_baseline_contamination() found >40% anomalous rows + >20% sustained block
      → This is CORRECT behavior if training data contains a real fault
      → Not a bug — the system is working as designed (v11.15.16)
      → Expected outcome: wait for cleaner training data, promotion will happen

□ P10 "h_sigma" not persisting / CUSUM threshold reverting
      → h_sigma missing from _AUTO_TUNE_PATH_MAP
      → File: core/config_history_writer.py (_AUTO_TUNE_PATH_MAP)
      → Fixed in v11.15.9

□ P11 Performance: total batch time >300s
      → Check timer breakdown in log for slowest phase
      → Known hotspots (ALL fixed in v11.15.2/v11.15.6):
          B1 _build_features apply(pd.to_numeric): ~24s
          B2 rolling_spectral_energy per-row FFT: ~20s
          B3 fuse.detect_episodes PCA attribution: ~180s coldstart
          B4 impute_features pandas copy+replace: ~40s
          B5 _bulk_insert_sql listcomp: ~37s
      → If a known hotspot is still slow: verify the fix is in place
      → If a new hotspot: look for Python loops over DataFrame rows

□ P12 Stack trace / unhandled exception
      → Extract: file, function, line number from the traceback
      → Identify which pipeline PHASE failed (look for phase markers in log before the trace)
      → Report file:line and phase
```

---

## STEP 3 — Check lifecycle state (always, regardless of patterns found)

Look for these in the log:
- Current `MaturityState` (COLDSTART / LEARNING / CONVERGED)
- `consecutive_runs` count
- `regime_quality_ok` value
- `contamination_verdict` if present
- Any `PROMOTE` / `DEMOTE` messages

---

## STEP 4 — Output structured diagnosis

Format your output exactly like this:

```
WHAT HAPPENED:
  [1-sentence summary of what went wrong]

ROOT CAUSE:
  [Pattern matched: P_N]
  [File: path/to/file.py, function_name(), ~line NNN]
  [Exact reason]

LIFECYCLE STATE:
  MaturityState: [state]
  consecutive_runs: [N]
  regime_quality_ok: [True/False]
  contamination: [verdict if present]

KNOWN FIX:
  [The fix, with version it was introduced in]
  [Or: "No known fix — new issue, use bug-fix-plan skill"]

NEXT STEP:
  [Exact command or action to take]
  e.g.: python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 --tick-minutes 1440 --max-batches 3
  or:   Check core/regimes.py line ~600 for build_feature_basis() operating_cols
```

---

## RULES

- NEVER filter, truncate, or summarize the log — read all of it
- NEVER create a diagnostic script to "reproduce" the issue — the log IS the diagnostic
- If the issue is not in the catalogue: use the `bug-fix-plan` skill
- If the fix is already applied (version check): the config may not have been pushed → `python scripts/sql/populate_acm_config.py`
- Multiple patterns can be active simultaneously — report all of them

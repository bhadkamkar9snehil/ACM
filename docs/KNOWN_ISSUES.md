# ACM Known Issues

_Updated: 2026-03-10_
_Update this file whenever a bug is found (add) or fixed (move to RESOLVED)._
_Resolved items stay for 30 days, then are archived to `docs/ACM_ARCHITECTURE_DECISIONS.md`._

---

## CRITICAL (blocking — must fix before next production run)

### C1 — All v11.16.x work uncommitted
- **Status:** Resolved — committed as v11.17.0 on `feature/v11-17-zero-day-system` (2026-03-10)
- **Risk:** Was: Lost work. All v11.16.x–v11.17.0 changes now committed and pushed.

## HIGH (active degradation — fix soon)

### H1 — T11 and T21 have zero ACM runs
- **Status:** Open
- **Impact:** Known faults unmonitored: T11 transformer failure (Jul 2023), T21 hydraulic + gearbox (Aug–Oct 2023)
- **Fix:** `python scripts/sql_batch_runner.py --equip WFA_TURBINE_11 WFA_TURBINE_21 --tick-minutes 1440 --start-from-beginning --max-batches 50`
- **Prerequisite:** Deploy the tag-agnostic regime-path changes before replaying the assets

### H2 — T10 health plateau (post-fault faults invisible)
- **Status:** Open
- **Root cause:** Model retrained on degraded data after Feb 2023 generator bearing failure → "sick" became new healthy baseline → health stuck at ~51% flat → post-fault hydraulic (Sep) and gearbox (Oct) faults missed
- **Fix:** Apply the tag-agnostic regime-path changes, then `--start-from-beginning` for T10
- **Prerequisite:** Deploy the regime-path changes in `core/regimes.py`

### H4 — EWM persistence requires SQL migration 016 for cross-run continuity
- **Status:** Open
- **Impact:** The runtime now scores EWM on the explicit raw monitoring surface, but persisted EWM state is skipped until `ACM_EWMBaseline.StateVersion` exists. Runs still work, but zero-day EWM continuity is in-memory only until migration 016 is applied.
- **Root cause:** The new monitoring-surface contract intentionally ignores legacy pre-versioned rows.
- **Fix:** Apply `scripts/sql/migrations/v11/016_acm_ewm_baseline_state_version.sql` before relying on persisted EWM continuity.
- **Files:** `core/ewm_baseline.py`, `scripts/sql/migrations/v11/016_acm_ewm_baseline_state_version.sql`

### H5 — Online regime proxy continuity depends on reusing ACM_RegimeBinnerState
- **Status:** Monitor after rollout
- **Impact:** The runtime now uses `OnlinePCABinner` as the day-0 regime proxy, but continuity depends on `ACM_RegimeBinnerState` containing the new `binner_type = "OnlinePCABinner"` payload. Legacy JSON is intentionally discarded.
- **Fix:** Verify `ACM_RegimeBinnerState` rows repopulate under the new runtime and delete obsolete legacy rows during rollout if operators want a clean state table.
- **Files:** `core/regime_binner.py`, `scripts/sql/migrations/v11/015_acm_regime_binner_state.sql`

### H6 — Explicit day-0 run observability requires SQL migration 017
- **Status:** Open
- **Impact:** The runtime now persists zero-day run status to `ACM_Runs` when the new columns exist, but until migration 017 is applied operators still cannot query `ZeroDayStatus` or `ZeroDayChannelCount` directly from run rows.
- **Root cause:** `ACM_RunLogs` is not a trustworthy live operator surface, so the new contract intentionally writes day-0 status to `ACM_Runs` instead of inventing another fallback sink.
- **Fix:** Apply `scripts/sql/migrations/v11/017_acm_runs_zero_day_status.sql`
- **Files:** `core/run_metadata_writer.py`, `core/acm.py`, `core/smart_coldstart.py`, `scripts/sql/migrations/v11/017_acm_runs_zero_day_status.sql`

---

## MEDIUM (workaround exists or low urgency)

### M1 — Per-regime alert thresholds not implemented
- **Status:** Open — planned for v11.17.x
- **Impact:** Global `thresholds.alert_z = 3.0` applies to all regimes. Equipment with different noise levels per operating mode will have false alerts or missed detections.
- **Design:** `ACM_RegimeThresholds` table, per-regime P99 threshold from `ACM_Scores_Wide` history
- **Workaround:** Global threshold is conservative; acceptable for now

### M2 — EWM freeze observability not in Grafana
- **Status:** Deferred
- **Impact:** Cannot see which (regime, sensor) pairs are frozen vs. active in EWM baseline
- **Fix:** Add Grafana panel querying `ACM_EWMBaseline WHERE BaselineIntegrity = 'frozen'`
- **Workaround:** SQL query: `SELECT EquipID, RegimeID, SUM(CASE WHEN BaselineIntegrity='frozen' THEN 1 ELSE 0 END) AS NFrozen FROM ACM_EWMBaseline GROUP BY EquipID, RegimeID`

### M3 — Forecast/RUL disabled
- **Status:** Disabled by config (`runtime.phases.forecast = False`)
- **Impact:** No remaining useful life predictions. Module exists but is off.
- **Workaround:** Disabled intentionally — forecasting was causing QA FAILs every run before fix in v11.15.4

### M4 — RegimePromotedAt NULL parse warning every batch
- **Status:** Open — low priority
- **Impact:** `[WARN] [OUTPUT] 1 timestamps failed to parse in column RegimePromotedAt` fires every scoring batch for any model stuck in LEARNING (RegimePromotedAt is NULL). Cosmetic only — no data loss.
- **Root cause:** Output writer does not handle NULL timestamp gracefully in ACM_ActiveModels write path
- **Workaround:** None needed — output is correct, warning is noise

---

## RESOLVED (last 30 days — keep for reference)

### R12 — EWM save_to_sql: 2,132 SQL round-trips (~25s per batch) (v11.17.1, 2026-03-10)
- **Was:** `_upsert_rows()` in `core/ewm_baseline.py` executed one `MERGE` per row via
  `for _, row in df.iterrows(): cur.execute(merge_sql, tuple(row))`. With 2,132 state rows
  this produced 2,132 network round-trips per batch. Profiler: `save_to_sql ~24,640ms`.
  Root cause: row-by-row execute loop — SQL Server supports multi-row VALUES in a single MERGE.
- **Fixed in:** v11.17.1 — `_upsert_rows()` now issues chunked bulk MERGE statements
  (chunk_size=500). 2,132 rows → 5 round-trips. `itertuples` replaces `iterrows` for
  record extraction. Semantics identical; expected save time <1s.
- **Files:** `core/ewm_baseline.py` (`_upsert_rows`, `_UPSERT_CHUNK_SIZE`, `_MERGE_TEMPLATE`)

### R11 — Refit-every-batch loop for LEARNING models (v11.16.3, 2026-03-09)
- **Was:** Two interacting bugs caused every scoring batch to fully retrain all 5 detectors:
  1. `run_auto_retrain_stage()` (`core/model_evaluation.py:867`) wrote `ACM_RefitRequests` whenever anomaly rate > 25%, with no guard for LEARNING models. The CONVERGED guard existed (line 728) but LEARNING was unprotected.
  2. `compute_config_signature()` (`utils/config_dict.py`) included `thresholds`, `fusion`, `regimes`, `episodes` in the hash. Auto-tune upserts `k_sigma`, `clip_z`, `k_max` into ACM_Config each run → hash changes next batch → cache invalid → forced refit → new auto-tune values → repeat.
  - Combined effect: 14-batch replay cost ~13 extra minutes (55s × 14 refits) and prevented model calibration from stabilising.
- **Fixed in:** v11.16.3
  - `model_evaluation.py`: quality-based refit request gated on `model_maturity == "CONVERGED"`
  - `utils/config_dict.py`: `compute_config_signature()` now hashes only `models`, `features`, `preprocessing`, `detectors`, `drift` — the sections that actually require detector retraining. Auto-tuned runtime namespaces (`thresholds.self_tune`, `episodes.cpd`, `regimes.auto_k`, `fusion`) excluded.

### R1 — LEARNING lifecycle never promoting (v11.15.10, 2026-03-07)
- **Was:** 6 coldstart + lifecycle bugs — `coldstart_complete` misused as `is_coldstart_run`, SP gate bypassing coldstart check, dead retry loop, wrong guard on `seed_baseline`, PromotionCriteria defaults stricter than config, `RegimeQualityMetric` never persisted
- **Fixed in:** v11.15.10, SQL migration 013

### R2 — Regime novel point flood (v11.15.6, 2026-02-25)
- **Was:** P95 distance threshold too tight → all scoring points classified as novel → `quality_ok=False` every batch
- **Fixed in:** v11.15.6 — P99 threshold + `floor_ratio=1.5` clamp in `regimes.py`

### R3 — Auto-tune k_max reverting every batch (v11.15.6, 2026-02-25)
- **Was:** `log_auto_tune_changes()` wrote to `ACM_ConfigHistory` only, never to `ACM_Config` → k_max changed every batch but never stuck
- **Fixed in:** v11.15.6 — `_upsert_acm_config()` MERGE in `config_history_writer.py`

### R4 — ACM_Config ValueType NULL violation (v11.15.8, 2026-02-25)
- **Was:** `_upsert_acm_config()` MERGE INSERT missing `ValueType` (NOT NULL column)
- **Fixed in:** v11.15.8 — `_infer_value_type()` helper added

### R5 — ContributionTimeline always empty (v11.15.7, 2026-02-25)
- **Was:** `build_contribution_timeline()` returns None if `'Timestamp' not in frame.columns`. Frame uses DatetimeIndex — Timestamp is the index, not a column.
- **Fixed in:** v11.15.7 — `reset_index()` + rename in `write_contribution_timeline_from_frame_service()`

### R6 — _IdentityScaler crash on reload (v11.15.15, 2026-03-08)
- **Was:** `_IdentityScaler` serializes mean/scale as `[]`. On reload, a `StandardScaler` with `n_features_in_=0` was created → "X has 21 features, but StandardScaler is expecting 0"
- **Fixed in:** v11.15.15 — detect empty mean/scale on load, recreate `_IdentityScaler` instead

### R7 — OMR weight not fully disabled when correlated (v11.15.15, 2026-03-08)
- **Was:** When GMM or IForest |r| ≥ threshold with OMR, only discounted (not zeroed)
- **Fixed in:** v11.15.15 — `omr_correlation_disable_threshold=0.95` → full weight=0.0 disable

### R8 — Regime basis and transient logic depended on tag taxonomy (v11.16.x, 2026-03-09)
- **Was:** `_classify_tag()` and keyword taxonomies drove regime-basis selection and transient detection, which broke generic-named assets and violated ACM's asset-agnostic intent.
- **Fixed in:** v11.16.x — active regime basis and transient detection now use a deterministic tag-agnostic numeric surface selector in `core/regimes.py`; cached regime models are invalidated via `REGIME_MODEL_VERSION = 5.0`

### R9 — EWM consumed the accidental engineered detector frame (v11.16.x, 2026-03-09)
- **Was:** EWM selected numeric columns from engineered `train` / `score`, so zero-day semantics depended on detector feature engineering instead of an explicit day-0 monitoring surface.
- **Fixed in:** v11.16.x — `core/acm.py` now selects an explicit raw numeric monitoring surface from `raw_train` / `raw_score`; persisted state is gated by `EWM_STATE_VERSION = 2`

### R10 — Day-0 regime proxy depended on named control variables (v11.16.x, 2026-03-09)
- **Was:** `ControlVariableBinner` assumed manually meaningful control-variable columns and was disabled in runtime because that design was incompatible with ACM's asset-agnostic intent.
- **Fixed in:** v11.16.x — `core/regime_binner.py` now provides `OnlinePCABinner`, a persisted tag-agnostic online latent regime proxy, and `core/acm.py` uses it before mature HDBSCAN labels exist

---

## Diagnostic Quick Reference

```sql
-- Is model stuck at LEARNING?
SELECT Version, MaturityState, ConsecutiveRuns, CreatedAt
FROM ACM_ActiveModels WHERE EquipID = 5010 ORDER BY CreatedAt DESC

-- Are all points novel? (C2 symptom)
-- Look in logs for: "Identified N/N novel points"

-- Check binner state (H3 tracking)
SELECT EquipID, JSON_VALUE(StateJson,'$.binner_type') AS BinnerType,
    JSON_VALUE(StateJson,'$.n_batches') AS NBatches
FROM ACM_RegimeBinnerState ORDER BY EquipID

-- EWM baseline health
SELECT EquipID, RegimeID, COUNT(*) AS NSensors,
    SUM(CASE WHEN BaselineIntegrity='frozen' THEN 1 ELSE 0 END) AS NFrozen
FROM ACM_EWMBaseline GROUP BY EquipID, RegimeID ORDER BY EquipID, RegimeID
```

# Annotated Historical Draft

This document is retained for traceability, but it is **not** the canonical source of runtime truth for ACM zero-day work.

Canonical references:
- [ACM-Zero-Day-Analytical-Audit](obsidian_vault/knowledge/ACM-Zero-Day-Analytical-Audit.md)
- [Plan-Zero-Day-Implementation](obsidian_vault/knowledge/Plan-Zero-Day-Implementation.md)

Current runtime note:
- The active regime-basis and transient paths no longer use `_classify_tag()`.
- EWM now uses an explicit raw numeric monitoring surface and version-gated persistence.
- The active runtime now uses `OnlinePCABinner` as the day-0 regime proxy.
- The remaining zero-day work is rollout of the EWM state-version migration and cleanup of legacy persisted state.

## Annotation Summary

### What This Document Gets Right

- ACM should be asset-agnostic from T=0.
- The zero-day workstream needs explicit early regime/context handling.
- Online latent regime inference is the right direction.
- HDBSCAN is better treated as a mature regime model or refiner than as the only regime source from the first batches.

### What Is Stale

- The current runtime now uses an explicit raw numeric monitoring surface for EWM, so any statements below describing engineered-frame EWM wiring are historical.
- The current regime path is no longer naming-dependent; active code now uses a tag-agnostic numeric surface selector in `core/regimes.py`.
- `ControlVariableBinner` is currently disabled in runtime, so this document should not be read as a status-accurate description of live ACM behavior.
- Live deployment claims such as "migrations run live" or "config pushed" are not verified by repository evidence alone.

### What Is Rejected

- Tag-name-based `_classify_tag()` logic as a valid long-term fix.
- Manual `control_vars` as a required dependency for asset-agnostic zero-day regime inference.
- Treating the current engineered detector frame as an acceptable zero-day surface just because it is already available.
- Treating raw-only behavior as a doctrinal requirement. The current research-backed view is that day-0 logic may use raw, derived, or hybrid streaming features, as long as the surface is tag-agnostic and causal.

### What Is Still Useful

- The core intuition that ACM needs a data-driven online regime proxy before mature HDBSCAN convergence.
- The recognition that current naming-dependent regime logic is not acceptable for an asset-agnostic system.
- The need to think about state transfer, state invalidation, and day-0-to-mature-regime continuity.

Historical body preserved below for context. Superseded proposals below should not be treated as active implementation guidance.

ACM — Comprehensive Architecture & Full Completion Plan
Date: 2026-03-08 Current version: v11.16.2 Branch: main (all v11.16.x work uncommitted — see R1 below)

Part 1: What ACM Is and Does
Philosophy
Zero asset-specific configuration. ACM must work on any industrial equipment from T=0 without domain knowledge about which sensors are control variables, what constitutes "normal", or what faults look like. Every algorithm must be fully self-initializing from observed data alone.

Full Pipeline Sequence (core/acm.py)
1.  Load config           ACM_Config → ConfigDict (global + per-equip overrides)
2.  Load raw data         SQL historian → pd.DataFrame of raw sensor readings
3.  Feature engineering   compute_basic_features_pl() → 9 features × n_sensors
                          (med, mad, mean, std, skew, kurt, slope, se, rz)
                          ~270 columns for 30-sensor equipment
4.  Data guardrails       Quality/completeness checks → gate or warn
5.  Detector init         load from SQL cache (ModelRegistry) or fit fresh
6.  Score all detectors   score_all_detectors() → raw scores per detector
7.  Regime labeling       build_feature_basis() → HDBSCAN/GMM → integer labels
8.  EWM scoring           EWMBaselineManager → ewm_z score per batch row
9.  Calibration           ScoreCalibrator fit/score → z-scores (training-anchored)
                          ewm_z BYPASSES calibration (already a z-score)
10. Fusion                Fuser.fuse() → weighted sum → fused health score
11. Episode detection     Hysteresis state machine → ACM_Episodes
12. Drift detection       CUSUMDetector → gradual degradation trend
13. Persistence           All results → SQL (Scores, Episodes, HealthTimeline, etc.)
14. Model persistence     ModelVersionManager → ModelRegistry (if version changed)
15. Lifecycle update      MaturityState → COLDSTART → LEARNING → CONVERGED
The 7-Detector Ensemble
Detector	File	Algorithm	Input	Weight
AR1	core/ar1_detector.py	Per-sensor AR(1) baseline, MAD-robust residuals	Engineered features	0.18
PCA-SPE	core/correlation.py	Squared prediction error from PCA subspace	Engineered features	0.28
PCA-T²	core/correlation.py	Hotelling T² in PCA latent space	Engineered features	0.18
IForest	core/outliers.py	sklearn IsolationForest, inverted anomaly score	Engineered features	0.14
GMM	core/outliers.py	sklearn GaussianMixture, negative log-likelihood	Engineered features	0.05
OMR	core/omr.py	Multivariate reconstruction error (PLS/Linear/PCA)	Engineered features	0.09
EWM-Z	core/ewm_baseline.py	Dual-rate EWM baseline, z_slow=fault signal	Raw sensors	0.08
All 6 original detectors consume engineered features (the ~270-column output of compute_basic_features_pl()). EWM-Z consumes raw sensor medians directly.

Regime Detection
Regime labels group observations into operating modes (e.g., turbine at idle vs. full load). Used for:

Per-regime EWM baselines (separate anomaly reference for each operating mode)
Per-regime alert thresholds (future — not yet implemented)
Health score context
Regime pipeline:

build_feature_basis() — selects OPERATING-tag sensors only (_classify_tag() → 'operating': speed, rpm, load, power, flow). Applies StandardScaler. Never uses engineered features or z-scores (v11.4.0 fix).
HDBSCAN clustering (requires ~500+ rows for stability). Returns labels -1 (noise) + 0..k.
GMM fallback for noise points (strength < 0.1). Assigns to nearest centroid.
label_map_ stability — maps raw HDBSCAN cluster indices to stable IDs across retrains.
When model available: approximate_predict() for scoring batch.
Critical gap: _classify_tag() uses keyword matching on column names ('speed', 'rpm', 'power', etc.). Wind Farm A's sensors are named sensor_N_avg (generic) → all classify as 'unknown' → regime basis is empty → HDBSCAN runs on zero features → regime detection is effectively broken for generic-named equipment.

Calibration
ScoreCalibrator (core/fuse.py):

Fit: On training data. Contamination-filtered (iterative MAD, max 30% exclusion). Computes robust median/MAD. Sets per-detector z-score anchor.
Score: z = (x - med) / (mad × 1.4826). Training-anchored — NOT renormalized per batch (v11.9.0 fix). Enables cross-batch health comparability.
ewm_z bypass: Already a z-score by construction. Flows directly to fusion.
Fusion
Fuser.fuse() (core/fuse.py):

Spearman-based correlation discount between detector pairs
OMR correlation disable: if GMM or IForest |r| ≥ 0.95 with OMR → weight=0 (v11.15.15)
compute_discounted_weights() → normalized weight vector → weighted sum → fused health score
Episode Detection
Hysteresis state machine in detect_episodes():

Entry: z > alert_z (default 3.0, config-driven)
Exit: z < clear_z (default alert_z - 1.0)
Culprit assignment via per-detector contribution ranking
OMR culprits formatted: "Baseline Consistency (OMR) -> sensor_name" via format_culprit_label()
Model Lifecycle
COLDSTART → LEARNING → CONVERGED

Promotion criteria: ≥3 consecutive runs, silhouette ≥ 0.15, stability ≥ 0.60, ≥200 training rows
All state in SQL: ACM_ActiveModels, ModelRegistry, ACM_RegimeState
Part 2: What Is Complete vs. What Is Broken
Complete ✓
Component	Notes
Full 6-detector ensemble + calibration + fusion	Working end-to-end
Model lifecycle (COLDSTART→LEARNING→CONVERGED)	v11.15.10 fixes applied
Episode detection + culprit attribution	Hysteresis, OMR culprit format fixed
Drift detection (CUSUM)	Working
EWM baseline manager (v11.16.0)	Dual-rate, vectorized, freeze, SQL persist
EWM fusion wiring (v11.16.1)	ewm_z in DEFAULT_WEIGHTS, bypass calibration
Phase 3 remap scaffold (v11.16.2)	Activates when _binner≠None
SQL migrations 014+015	Run against live DB
SQL-Schema.md, config pushed	Done
T10 fault detection (Feb 2023)	Health crashed to 3.2 ✓
T13 hydraulic fault (Apr 2023)	Detected, health min 15.4 ✓
Broken / Missing ✗
Issue	Severity	Root Cause
Regime detection broken for generic sensor names	Critical	_classify_tag() returns 'unknown' for sensor_N_avg → empty basis → HDBSCAN fails
Zero-day regime context missing	High	ControlVariableBinner disabled (wrong approach). EWM uses global regime (-1) only
T11, T21 have zero ACM runs	High	Operational gap
T10 plateau	High	Trained on degraded data; post-fault faults missed
Nothing committed since a731861	High	All v11.16.x at risk
Per-regime alert thresholds	Medium	Not implemented; global threshold only
Freeze observability (Grafana)	Low	Deferred
Online OMR (recursive LS)	Low	Batch-fitted OMR acceptable for now
Forecast/RUL disabled	Low	Module exists, disabled by config
The Two Intertwined Problems
Problem A — Regime detection is keyword-dependent: The operating-mode clustering that drives per-regime baselines AND per-regime thresholds depends entirely on _classify_tag() classifying sensors as 'operating'. This works for named sensors (wind_speed, rotor_rpm, power_output) but fails completely on generic names (sensor_0_avg … sensor_29_avg). Without a proper basis, HDBSCAN has nothing to cluster.

Problem B — Zero-day regime context: Even if HDBSCAN eventually works (for named sensors), it requires 500+ rows. During coldstart (batch 1–5), EWM has no regime separation. All sensors share one global baseline (-1), making EWM's zero-day capability theoretically sound but practically worthless for detecting mode-dependent anomalies.

Both problems share the same root cause: the system relies on column naming conventions or training data volume to discover operating modes.

The fix for both: OnlinePCABinner — data-driven operating mode discovery from raw sensor covariance, works from ~observation 20, zero domain knowledge.

Part 3: The Fix — OnlinePCABinner (v11.16.3)
Principle
Maintain an EWM covariance matrix across all raw sensors. The dominant eigenvector (PC1) of this covariance naturally captures the largest source of variation in the data — which, for any industrial equipment, is operating mode (load, speed, power demand). Percentile-bin PC1 scores → integer regime IDs.

No column names needed. No domain knowledge. Works on sensor_N_avg identically to wind_speed_avg.

EWM Covariance Update (vectorized)
# Per batch (all numpy, no Python loops over rows)
batch_mean = np.nanmedian(X, axis=0)           # (n_sensors,) — robust batch summary
delta = batch_mean - self._ewm_mean
self._ewm_mean += self.alpha * delta            # EWM mean
outer = delta[:, None] @ delta[None, :]         # (n_sensors, n_sensors)
self._cov = (1 - self.alpha) * self._cov + self.alpha * outer  # EWM covariance
PC1 Extraction (5-step power iteration, warm-started)
v = self._eigvec.copy()
for _ in range(5):
    v = self._cov @ v
    norm = np.linalg.norm(v)
    if norm < 1e-12: break
    v /= norm
self._eigvec = v
5 iterations sufficient: eigenvector changes slowly (EWM-smoothed covariance), warm-started each batch.

Percentile Binning
Ring buffer (size 200) of per-batch median PC1 scores → adaptive percentile edges
np.searchsorted(edges, pc1_scores).clip(0, n_bins-1) → bin index 0..n_bins-1
Returns np.full(n_rows, -1, dtype=int) when _n_rows_total < min_n_to_assign (default 20)
Class Design (core/regime_binner.py — full replacement)
class OnlinePCABinner:
    def __init__(self, equip_id, n_bins=3, alpha=0.05, min_n_to_assign=20)
    def observe_batch(self, raw_df) -> np.ndarray   # update state + return IDs
    def assign_batch(self, raw_df) -> np.ndarray    # read-only, Phase 3 use only
    def has_binner_regime_ids(self, _unused) -> bool  # returns not _binner_remapped
    def mark_remapped(self) -> None                  # set _binner_remapped=True
    def save_to_sql(self, sql_client, equip_id) -> bool
    def load_from_sql(self, sql_client, equip_id) -> bool
Column locking: On first observe_batch(), record all numeric columns alphabetically as _sensor_cols. Subsequent calls: drop unknown cols, fill missing with _ewm_mean. Ensures covariance matrix stays square.

SQL state (reuses ACM_RegimeBinnerState table — already exists):

{
  "binner_type": "OnlinePCABinner",
  "n_bins": 3, "alpha": 0.05, "n_batches": 47, "n_rows_total": 4230,
  "sensor_cols": ["sensor_0_avg", ...], "ewm_mean": [...],
  "cov_upper": [...],   // upper triangle only — halves storage
  "eigvec": [...], "pc1_edges": [...],
  "pc1_history": [...], "pc1_history_ptr": 47, "binner_remapped": false
}
Migration: load_from_sql() validates binner_type == "OnlinePCABinner". Old ControlVariableBinner rows (no binner_type key) silently discarded → cold rebuild. No SQL migration needed.

Integration into core/acm.py (4 edits)
Edit 1 — import: ControlVariableBinner → OnlinePCABinner

Edit 2 — instantiation (replace disabled block):

_binner: Optional[OnlinePCABinner] = None
if _ewm_enabled:
    _binner = OnlinePCABinner(
        equip_id=equip_id,
        n_bins=int(_ewm_cfg.get("n_bins", 3)),
        alpha=float(_ewm_cfg.get("alpha_fast", 0.05)),
        min_n_to_assign=20,
    )
    _binner.load_from_sql(sql_client, equip_id)
Edit 3 — Phase 3 remap block: add _binner.mark_remapped() after ewm_manager.remap_regime_ids(_remap):

ewm_manager.remap_regime_ids(_remap)
_binner.mark_remapped()    # sync idempotency flag
ewm_manager.save_to_sql(sql_client)
Edit 4 — EWM fallback block: _binner.observe_batch(_score_numeric) (update + assign in one call)

The Phase 3 _binner.assign_batch(_train_numeric) call is unchanged — already correct.

Config change (configs/config_table.csv)
Remove row: models.ewm_baseline.control_vars (orphaned — ControlVariableBinner gone) Keep row: models.ewm_baseline.n_bins = 3 After: python scripts/sql/populate_acm_config.py

Part 4: Regime Detection Fix for Generic Sensor Names
The Problem
_classify_tag() in core/regimes.py classifies sensor columns into 'operating' / 'condition' / 'unknown' by keyword matching. Wind Farm A uses generic names (sensor_0_avg … sensor_29_avg) → all 'unknown' → build_feature_basis() returns an empty basis → HDBSCAN has no features.

This is a separate bug from the zero-day problem. Even after OnlinePCABinner is live, HDBSCAN regime labeling will not work for generic-named equipment. Phase 3 remap (binner → HDBSCAN) will never trigger because HDBSCAN never converges.

The Fix
When build_feature_basis() produces an empty basis (all sensors classified 'unknown'), fall back to ALL numeric raw sensors as the regime basis. This is correct behavior: if we cannot distinguish operating from condition sensors, use all sensors — HDBSCAN will still find natural clusters, just without the bias-correction benefit of excluding condition sensors.

Location: core/regimes.py, build_feature_basis() (line ~600)

# After filtering to operating-tag columns:
if len(operating_cols) == 0:
    # Cannot classify sensors by tag — use all numeric raw sensors as basis
    # This is safe: HDBSCAN discovers natural clusters from any sensor set
    operating_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    Console.warn("No operating-tag sensors found; using all sensors for regime basis", ...)
This is a 3-line fix, but it unblocks the entire regime detection pipeline for generic-named equipment.

Part 5: Full Completion Roadmap
Priority 1 — NOW (blocking everything else)
R1: Create feature branch + commit all v11.16.x work

git checkout -b feature/zero-day-pca-binner
git add core/ewm_baseline.py core/regime_binner.py core/acm.py core/fuse.py \
        core/regimes.py configs/config_table.csv utils/version.py \
        scripts/sql/migrations/v11/014_acm_ewm_baseline.sql \
        scripts/sql/migrations/v11/015_acm_regime_binner_state.sql \
        docs/obsidian_vault/knowledge/SQL-Schema.md \
        docs/obsidian_vault/knowledge/Plan-Zero-Day-Implementation.md
git commit -m "feat(v11.16.0-2): EWM baseline, fusion wiring, SQL migrations, Phase 3 remap"
Priority 2 — OnlinePCABinner + Regime Fallback (v11.16.3)
Files changed:

core/regime_binner.py — full replacement with OnlinePCABinner
core/acm.py — 4 surgical edits
core/regimes.py — 3-line fallback in build_feature_basis()
configs/config_table.csv — remove control_vars row
utils/version.py — bump to v11.16.3, add changelog
Commit: feat(v11.16.3): OnlinePCABinner + regime basis fallback for generic sensor names

Priority 3 — Operational Catch-Up
Run T11 (5011) + T21 (5021) --start-from-beginning — both have zero ACM runs
T10 (5010) plateau: --start-from-beginning after v11.16.3 deployed
Verify EWM regime IDs appearing in scoring logs
Priority 4 — Per-Regime Alert Thresholds (v11.17.x)
Currently thresholds.alert_z = 3.0 is global. With regime detection working, we can compute per-regime P99 thresholds from ACM_Scores_Wide history. Requires:

ACM_RegimeThresholds table: (EquipID, RegimeID, AlertZ, WarnZ, UpdatedAt)
Adaptive threshold computation from historical per-regime score distribution
detect_episodes() lookup by current regime label
Config flag: fusion.per_regime_thresholds
Priority 5 — Backlog (no fixed date)
Item	What	Why deferred
Freeze observability	Grafana panel for ACM_EWMBaseline WHERE BaselineIntegrity='frozen'	Low urgency, deferred by user
Online OMR (RLS)	Recursive least squares for online coefficient updates	Batch-fitted OMR already works
Forecast/RUL re-enable	runtime.phases.forecast = True + API validation	Module exists; lower priority than detection
Part 6: Verification Plan
Unit Tests (tests/test_online_pca_binner.py)
Test	Checks
Returns -1 before min_n_to_assign	No premature assignment
Returns valid bins [0..n_bins-1] after threshold	Binning is active
Mode separation: idle (low) vs. running (high) signals	PC1 separates operating modes
Column locking: unknown cols dropped, missing filled	Schema-drift robustness
SQL round-trip (mock cursor)	save/load restores identical assign_batch output
mark_remapped() idempotency	Second call safe, flag stays True
assign_batch() does not update state	Phase 3 read-only contract
EWM covariance converges toward true covariance	Numerics correctness
Integration Test
-- Reset binner state
DELETE FROM ACM_RegimeBinnerState WHERE EquipID = 5010;
python -m core.acm --equip T10
Pass criteria:

Log: "EWM using PCA-binner regimes" with n_sensors > 0
SELECT JSON_VALUE(StateJson,'$.binner_type') FROM ACM_RegimeBinnerState WHERE EquipID=5010 → "OnlinePCABinner"
No FAIL in ACM_Runs
On HDBSCAN convergence (later run): log shows "EWM regime remap", then binner_remapped=true
Subsequent runs: remap does NOT fire again
Diagnostic Queries
-- Binner state health
SELECT EquipID,
    JSON_VALUE(StateJson, '$.binner_type') AS BinnerType,
    JSON_VALUE(StateJson, '$.n_batches') AS NBatches,
    JSON_VALUE(StateJson, '$.n_rows_total') AS NRowsTotal,
    JSON_VALUE(StateJson, '$.binner_remapped') AS Remapped,
    LEN(StateJson) AS JsonBytes
FROM ACM_RegimeBinnerState ORDER BY EquipID;

-- EWM baseline health (regime distribution)
SELECT EquipID, RegimeID, COUNT(*) AS NSensors,
    AVG(NSamples) AS AvgSamples,
    SUM(CASE WHEN BaselineIntegrity='frozen' THEN 1 ELSE 0 END) AS NFrozen
FROM ACM_EWMBaseline GROUP BY EquipID, RegimeID ORDER BY EquipID, RegimeID;
Critical File Reference
File	Role in Plan
core/regime_binner.py	Replace entirely with OnlinePCABinner
core/acm.py	4 surgical edits: import, instantiation, mark_remapped, observe_batch
core/regimes.py	3-line fallback in build_feature_basis() for empty basis
configs/config_table.csv	Remove models.ewm_baseline.control_vars
utils/version.py	Bump to v11.16.3, add changelog
core/ewm_baseline.py	No changes — use as pattern for SQL
 persistence
core/fuse.py	No changes — fusion wiring already complete

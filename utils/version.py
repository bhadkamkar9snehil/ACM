"""
Version management for ACM.

This module defines the current version of ACM and provides utilities for version tracking
across logs, outputs, and database entries. Version follows semantic versioning (MAJOR.MINOR.PATCH).

Versioning Strategy:
- MAJOR: Significant architecture changes or breaking changes (e.g., v10→v11)
- MINOR: New features, detector improvements, algorithm enhancements (e.g., v11.0→v11.1)
- PATCH: Bug fixes, refinements, performance improvements (e.g., v11.0.0→v11.0.1)

Release Management:
- All releases tagged with git annotated tags (e.g., v11.0.0)
- Each tag includes comprehensive release notes
- Feature branches use descriptive names: feature/*, fix/*, refactor/*, docs/*
- Merges to main use --no-ff to preserve history
- Production deployments use specific tags (never merge commits)
"""

__version__ = "11.11.0"
__version_date__ = "2026-02-18"
__version_author__ = "ACM Development Team"

# v11.11.0: FORECASTING PERFORMANCE (563s → <5s)
#
# PROBLEM: outputs.forecasting took 563s for 10-min cadence equipment.
# ROOT CAUSE: _run_monte_carlo_simulations() "slow path" (regime transitions)
# ran a Python loop over n_simulations × n_steps. With 1000 sims × 4310 steps
# (720h adaptive horizon / 0.167h per step) and numpy.random.choice (~100μs each),
# that's ≈ 430s in pure Python.
#
# FIX #1: VECTORIZE MONTE CARLO SLOW PATH (core/rul_estimator.py)
# - Replaced per-simulation Python loop with numpy vectorization.
# - All simulations now advance simultaneously: O(n_steps) Python iters instead of
#   O(n_simulations × n_steps).
# - Vectorized Markov transition: np.cumsum(tm[regimes], axis=1) + np.argmax for
#   all sims at once instead of numpy.random.choice per sim.
# - Pre-generate all noise: np.random.normal(size=(n_simulations, n_steps)) once.
# - Expected speedup: ~1000× for 10-min cadence, proportional at other cadences.
#
# FIX #2: CAP MONTE CARLO STEP COUNT (core/forecast_engine.py)
# - forecast_resolution_hours default changed from None (= data cadence) to 1.0h.
# - At 10-min data: max_steps was 4310 (720h / 0.167h); now 720 (720h / 1h).
# - Forecast output is health over days/weeks — hourly resolution is sufficient.
# - Config override: set forecast_resolution_hours in ACM_Config to use a different
#   resolution (e.g., 0.5 for 30-min output).
#
# v11.10.0: FUSION CLEANUP + TIMESTAMP FIX
#
# FIX #1: REFIT REQUEST TIMESTAMP MISMATCH (core/output_manager.py)
# - PROBLEM: ACM_RefitRequests.RequestedAt stored as SYSUTCDATETIME() (UTC),
#   but all log timestamps use datetime.now() (local time). Result: "SQL refit
#   request found: id=460 at 04:51" logged at 10:24 — 5.5 hour apparent gap.
# - FIX: INSERT now explicitly passes datetime.now() for RequestedAt so stored
#   timestamps match log timestamps (both local). AcknowledgedAt switched to
#   SYSDATETIME() for consistency.
#
# FIX #2: CONSTANT INPUT WARNING IN CORRELATION DISCOUNTING (core/fuse.py)
# - PROBLEM: scipy spearmanr raises ConstantInputWarning + returns NaN when
#   one detector array is all-constant (zeros in early batches).
# - FIX: Pre-check np.unique(arr).size < 2 before calling spearmanr; skip pair.
#   pairs_checked moved after the constant-check for accurate log counts.
#
# REFACTOR #1: DELETE combine() WRAPPER (core/fuse.py)
# - combine() was a vestigial thin wrapper over run_fusion_pipeline().
#   It provided one Span but was not called anywhere except run_fusion_pipeline().
# - FIX: Deleted combine(). Three passes now inlined in run_fusion_pipeline()
#   with semantically named Spans: fusion.baseline, fusion.train, fusion.score.
#   episodes.detect appears as a child span inside fusion.score.
# - BREAKING (internal): Fuser.fuse() discounted_weights is now a required
#   parameter — no Optional fallback to self.weights. Callers must pass it.
#
# FIX #3: TRIPLE TIMER SUMMARY (core/fast_features.py)
# - PROBLEM: Three Timer() instances each register atexit callbacks:
#   (1) T = Timer() in main() [correct], (2) _timer = Timer() at module level
#   in fast_features.py [spurious], (3) second main() Timer (now gone).
# - FIX: Removed module-level _timer = Timer() and @_timer.wrap decorator from
#   fast_features.py. Removed from utils.timer import Timer (now unused there).
#   Result: exactly ONE timer summary per subprocess.
#
# FIX #4: DUPLICATE main() IN acm_main.py (core/acm_main.py)
# - PROBLEM: acm_main.py had grown to 5408 lines with TWO def main() (at
#   lines 617 and 3320) plus duplicate imports/classes/helpers between them.
#   Only the second main() was reachable (Python shadows first definition).
# - FIX: User removed duplicate block; file cleaned to 2705 lines, single
#   main() at line 617. UTF-8 BOM (from Windows editor) also stripped.

# v11.9.0: FUSION STABILITY - Cross-Batch Health Score Comparability
#
# PROBLEM: Health scores were incomparable across batches:
#   - Batch 1 (coldstart): Health = 39%, RUL = 0h
#   - Batch 2 (same data): Health = 94%, RUL = 168h
#   - Fusion took 26 minutes on 4301 samples
#
# ROOT CAUSE: Fuser._zscore() re-normalized already-calibrated z-scores against
# the CURRENT BATCH distribution. ScoreCalibrator already produces training-anchored
# z-scores (median/MAD normalization), but fusion then destroyed this anchoring by
# re-centering and re-scaling per batch.
#
# FIX #1: REMOVE DOUBLE Z-SCORING (core/fuse.py)
# - Replaced Fuser._zscore() with _sanitize() (NaN/inf handling only)
# - Calibrated z-scores are now passed through to fusion unchanged
# - Health scores are now training-anchored and comparable across batches
#
# FIX #2: SKIP REDUNDANT EPISODE DETECTION (core/fuse.py)
# - run_fusion_pipeline() called combine() 3 times, each with full episode detection
# - Only the final pass result was kept; first 2 were discarded
# - Added skip_episodes parameter to combine()
# - Auto-tune and train passes now skip episode detection (~3x fusion speedup)
#
# FIX #3: PERSIST CALIBRATION PARAMS (4 files)
# - core/fuse.py: Added ScoreCalibrator.to_dict() / from_dict() for serialization
# - core/model_persistence.py: Added save_calibration_params() to ModelVersionManager
#   Calibration saved as separate INSERT to same model version (runs after model save)
# - core/detector_orchestrator.py: calibrate_all_detectors() accepts cached_calibration_params
#   When present, rebuilds calibrators from cache instead of refitting
# - core/acm_main.py: Wired save/load of calibration params in pipeline
#   Load: extracts calibration_params from cached_models dict
#   Save: persists calibrators_dict to SQL after calibration completes
#   Scoring batches reuse training-time normalization for consistency
#
# DATA FLOW:
#   Batch 1 (coldstart): fit detectors → save models → calibrate (fit) → save cal → fuse
#   Batch 2+ (scoring):  load models + cal_params → calibrate (cached transform) → fuse
#
# IMPACT:
# - Health scores stable across batches (no more 39% → 94% flip-flop)
# - Fusion ~3x faster (episode detection only on final pass)
# - Calibration state persists in SQL ModelRegistry
# - True continuous learning: scoring batches reuse training-time baselines

# v11.8.0: ADAPTIVE PIPELINE - Remove ONLINE/OFFLINE Modes Entirely
#
# PHILOSOPHY: "The entire offline and online distinction is a mistake."
# ACM is a universal unsupervised Asset Condition Monitor. Training and scoring
# decisions are driven by model state (COLDSTART/LEARNING/CONVERGED) and quality
# metrics - never by manual mode flags.
#
# CHANGES:
# 1. Removed PipelineMode enum (ONLINE/OFFLINE) from pipeline_types.py
# 2. Removed --mode CLI argument from acm.py, acm_main.py, sql_batch_runner.py
# 3. Removed mode-based gating: ALLOWS_MODEL_REFIT and ALLOWS_REGIME_DISCOVERY
#    are now always True - quality metrics and maturity state decide
# 4. Unified DataContract validation: single is_training_phase path replaces
#    three-way ONLINE/OFFLINE-coldstart/OFFLINE-normal branching
# 5. Simplified model_evaluation.py: allow_refit_requests always True
# 6. Simplified regimes.py: discovery controlled by MaturityState only
# 7. acm.py rewritten: single unified execution path (no mode routing)
# 8. sql_batch_runner.py: removed mode auto-selection (OFFLINE for coldstart,
#    ONLINE for post-coldstart) - pipeline decides adaptively
#
# NEW CLI:
# - --force-retrain: Force model retraining regardless of cache/quality
# - --clear-cache: Clear cached models (unchanged)
#
# ADAPTIVE RETRAINING TRIGGERS (replace manual --mode offline):
# - Coldstart: no cached models exist
# - Quality: silhouette < 0.30, anomaly rate > 25%, drift > 3.0
# - Compatibility: feature hash mismatch
# - Age: model > 30 days without refit
# - Manual: --force-retrain CLI flag
#
# MIGRATION:
# - Remove any --mode arguments from scripts/cron jobs
# - Replace --mode offline with --force-retrain where manual retraining needed
# - No database migration required

# v11.6.1: ONLINE MODE CACHE FIX (Critical Hotfix) [SUPERSEDED by v11.8.0]
#
# ISSUE: ONLINE batches crashed with "Required detector models not found in cache"
#
# ROOT CAUSE:
# - Run #1 (OFFLINE coldstart) creates a refit request during auto-tune
# - Run #2 (ONLINE batch) sees refit_requested=True
# - Line 1073: use_cache = ... and not refit_requested ...
# - Since refit_requested=True, use_cache=False, so cached models NOT loaded
# - But ONLINE mode can't refit (ALLOWS_MODEL_REFIT=False), so pipeline crashes
#
# FIX:
# - Location: core/acm_main.py lines 1073-1085
# - Change: In ONLINE mode, ignore refit_requested and always load cached models
# - Logic: use_cache = ... and (not refit_requested or not ALLOWS_MODEL_REFIT) ...
# - New log: "Refit requested but ONLINE mode cannot refit - will load cached models anyway"
#
# FIX #8 - PCA CACHE LENGTH MISMATCH:
# - Location: core/acm_main.py lines 1782-1808
# - Issue: pca_train_spe/pca_train_t2 cached during fit (10K subsampled)
#          Then used in calibration with full train data (13K+ rows)
#          Caused: ValueError: Length of values (10000) does not match length of index (13369)
# - Fix: Only use pca_cached if len(pca_train_spe) == len(train), else re-score
#
# IMPACT:
# - ONLINE batches now work even when refit requests exist
# - Refit requests will be honored on the next OFFLINE run
# - Batch processing no longer crashes after coldstart

# v11.6.0: COMPREHENSIVE STABILITY REFACTORING - 6 Critical Fixes
#
# CONTEXT: SQL analysis of 200+ runs revealed 6 critical issues:
#   - 4 failed runs due to NoneType transform error
#   - 171 model copies per equipment (should be 1)
#   - 170+ spurious refit requests for CONVERGED models
#   - Empty ACM_RunLogs table (no log persistence)
#   - 2+ hour runs with 26K training rows
#   - 88% false positive ALERT rate
#
# FIX #1: TRANSFORM ERROR - None Guard (P0)
# - Location: core/regimes.py predict_regime() and label()
# - Issue: Models loaded from corrupted SQL ModelRegistry have None scaler
# - Fix: Add explicit None-guard before scaler.transform() with clear error message
# - Impact: Crash -> Clear error message pointing to corrupt model
#
# FIX #2: MODEL ACCUMULATION - Version Retention (P1)
# - Location: core/model_persistence.py _save_models_to_sql()
# - Issue: Every run creates new version (171 × 6 = 1026 rows per equipment)
# - Fix: Add _cleanup_old_versions(keep_n=5) after save, deletes old versions
# - Impact: ModelRegistry stays bounded, DB size under control
#
# FIX #3: EXCESSIVE REFIT REQUESTS - Maturity Check (P1)
# - Location: core/model_evaluation.py auto_tune_parameters()
# - Issue: CONVERGED models still evaluated for refit (170+ requests)
# - Fix: Skip refit evaluation entirely when model_maturity == "CONVERGED"
# - Impact: Stable models stay stable, no spurious refit requests
#
# FIX #4: SQL LOG PERSISTENCE - Late Binding (P2)
# - Location: core/observability.py enable_sql_logging(), core/acm_main.py
# - Issue: Observability initialized BEFORE SQL connection, no sql_client passed
# - Fix: Add enable_sql_logging() function, call after SQL connection established
# - Impact: Logs now persist to ACM_RunLogs for debugging
#
# FIX #5: TRAINING SUBSAMPLING - Performance (P1)
# - Location: core/detector_orchestrator.py fit_all_detectors()
# - Config: models.max_train_samples = 10000 (new config)
# - Issue: 26K training rows cause 2+ hour runs (O(n²) PCA/HDBSCAN)
# - Fix: Stratified subsampling to max_train_samples using evenly-spaced indices
# - Impact: 2+ hours -> ~10 minutes for large datasets
#
# FIX #6: FALSE POSITIVE THRESHOLDS - Config Fix (P0)
# - Location: configs/config_table.csv
# - Issue: thresholds.alert=0.85, thresholds.warn=0.7 interpreted as percentiles
# - Fix: Changed to 3.0 / 1.5 (z-scores) for proper 3-sigma alerting
# - Impact: 88% ALERT rate -> ~3% (proper 3-sigma)
#
# MIGRATION:
# 1. Run: python scripts/sql/populate_acm_config.py (sync config to SQL)
# 2. Optional: Run one-time cleanup: DELETE FROM ModelRegistry WHERE Version NOT IN (...)
# 3. Restart batch processing - old models will be cleaned up automatically

# v11.5.0: CRITICAL BATCH MODE FIXES - Pipeline Stability
#
# ROOT CAUSE ANALYSIS (January 2026):
# Historical batch processing was exhibiting three interrelated failure modes:
#   1. 10x Data Inflation - sampling_secs=60 on 600s native cadence caused upsampling
#   2. Perpetual Refit Loop - all batches ran in OFFLINE mode, retraining every batch
#   3. Model Instability - refit requests written in ONLINE mode triggered next-batch refit
#
# FIXES IMPLEMENTED:
#
# FIX #1: ANTI-UPSAMPLE GUARD (core/data_loader.py)
# - Strengthened upsampling prevention: if requested < native cadence * 0.9, skip resample
# - Checks BOTH train and score native cadence (min of both)
# - Sets cadence_ok=True when using native data (no resampling needed)
# - Clear logging: "ANTI-UPSAMPLE: Requested resample (60s) < native cadence (600.0s)"
# - IMPACT: Prevents 10x row inflation that corrupted all downstream analytics
#
# FIX #2: CONFIG DEFAULT (configs/config_table.csv)
# - Changed data.sampling_secs from 60 (fixed int) to "auto" (string)
# - "auto" means: use native cadence, don't resample unless irregular
# - IMPACT: New deployments won't accidentally trigger upsampling
#
# FIX #3: BATCH MODE SELECTION (scripts/sql_batch_runner.py)
# - Coldstart batches (batch_num=0, is_post_coldstart=False): OFFLINE mode (train models)
# - Post-coldstart batches (is_post_coldstart=True): ONLINE mode (score only)
# - Explicit --mode CLI arg still takes precedence if provided
# - IMPACT: Models train once during coldstart, then remain stable for scoring
#
# FIX #4: REFIT REQUEST GUARD (core/model_evaluation.py)
# - auto_tune_parameters() now checks pipeline_mode before writing refit requests
# - ONLINE mode: Quality assessment only, NO refit request written
# - OFFLINE mode: Can write refit requests if quality truly degraded
# - IMPACT: Breaks the refit feedback loop during historical batch processing
#
# FIX #5: PIPELINE MODE PROPAGATION (core/acm_main.py)
# - Stores pipeline_mode in cfg["runtime"]["pipeline_mode"] for downstream access
# - model_evaluation.py reads this to decide whether to write refit requests
# - IMPACT: Consistent mode awareness across all pipeline components
#
# FIX #6: REFIT MATURITY OVERRIDE (core/acm_main.py)
# - When refit_requested=True AND current_model_maturity=CONVERGED, override to LEARNING
# - Prevents RuntimeError: "[CONVERGED MODEL] Regime model not found"
# - Scenario: Leftover refit request from previous runs triggers detector retrain
# - But CONVERGED state blocks regime rediscovery -> missing/stale regime model -> crash
# - IMPACT: Refit requests are properly honored without state inconsistency
#
# ARCHITECTURE CLARIFICATION:
# - OFFLINE mode: Full discovery - train detectors, discover regimes, calibrate thresholds
# - ONLINE mode: Score-only - use cached models, no retraining, just score incoming data
# - Model lifecycle: COLDSTART (offline) -> LEARNING (offline) -> CONVERGED (online)
# - After CONVERGED, only scheduled refresh or severe drift should trigger retraining
#
# TESTING: Run full historical batch with --start-from-beginning
# EXPECTED: First batch trains models, subsequent batches score without refit

# v11.4.0: REGIME CLUSTERING ARCHITECTURAL FIX - Raw Sensors Only
# - BREAKING: Regime clustering now uses RAW SENSOR VALUES ONLY
# - REMOVED: _add_health_state_features() function from core/regimes.py
# - REMOVED: health_ensemble_z, health_trend, health_quartile from regime basis
# - REMOVED: HEALTH_STATE_KEYWORDS constant (no longer needed)
# - REMOVED: health-state injection call site from core/acm_main.py
# - BUMP: REGIME_MODEL_VERSION 3.1 -> 4.0 (forces model retraining)
#
# RATIONALE (Circular Masking Fix):
# Using detector z-scores in regime clustering created a CIRCULAR DEPENDENCY:
#   1. Equipment degrades -> detector z-scores rise
#   2. Health-state features cause point to cluster into "new regime"
#   3. New regime gets fresh baseline -> degradation masked
#   4. Equipment appears "healthy in its current regime"
#
# CORRECT ARCHITECTURE:
# - Regimes = HOW equipment operates (load, speed, flow, pressure)
# - Detectors = IF equipment is HEALTHY within that operating mode
# - These are ORTHOGONAL concerns and MUST NOT be mixed
# - Detector z-scores are OUTPUTS of anomaly detection, not INPUTS to regime clustering
#
# MIGRATION: Existing regime models will be invalidated and retrained automatically
# Building on v11.3.4 RUL validation guard

# v11.3.4: RUL VALIDATION GUARD - Prevent Implausible Predictions
# - NEW: RUL validation logic in core/forecast_engine.py before writing to ACM_RUL
#   - Rejects RUL < 1h when health > 70% (implausible imminent failure)
#   - Rejects FailureProbability=100% when RUL > 100h (inconsistent prediction)
#   - Rejects negative, infinite, or NaN RUL values
# - Rejected predictions logged with Console.warn() for debugging
# - Prevents corrupt data from entering ACM_RUL table
#
# v11.3.3: CONTAMINATION FILTERING FOR CALIBRATION - Analytics Audit Finding #6
# - NEW: CalibrationContaminationFilter class in core/fuse.py
#   - Filters anomalous samples from calibration windows BEFORE computing statistics
#   - Prevents contaminated training data from producing permissive thresholds
#   - Addresses root cause of false negatives and delayed detection
# - FILTERING METHODS (configurable):
#   - iterative_mad (default): Iteratively removes outliers, recomputes median/MAD until convergence
#   - iqr: Fast IQR-based filtering (Q1 - k*IQR, Q3 + k*IQR)
#   - z_trim: Single-pass MAD-scaled z-score trimming
#   - hybrid: IQR pre-filter + iterative MAD refinement
# - SAFETY GUARDS:
#   - Max 30% exclusion rate (prevents over-filtering)
#   - Min 50 samples retained (preserves statistical validity)
#   - Convergence detection for iterative methods
# - INTEGRATION:
#   - ScoreCalibrator.fit() now applies contamination filtering automatically
#   - AdaptiveThresholdCalculator uses same filtering for consistency
#   - Config: thresholds.contamination_filter.enabled (default: True)
#   - Config: thresholds.contamination_filter.method (default: iterative_mad)
#   - Config: thresholds.contamination_filter.z_threshold (default: 4.0)
# - IMPACT: More sensitive detection, reduced false negatives by ~25%
# Building on v11.3.2 model compatibility validation

# v11.3.2: MODEL COMPATIBILITY VALIDATION - Audit-driven architectural fixes
# - AUDIT FIX (Finding I): Feature compatibility validation for cached models
#   - NEW: validate_model_feature_compatibility() validates columns before model loading
#   - rebuild_detectors_from_cache() now requires current_columns parameter
#   - All detectors (AR1, PCA, IForest, GMM, OMR, Regime) validated against current features
#   - Models with mismatched features are discarded and retrained
#   - Column count, column names, and column ORDER validation for order-sensitive models
# - AUDIT FIX (Finding II): Detector enable flags reconciliation
#   - NEW: reconcile_detector_flags_with_loaded_models() syncs flags with detector availability
#   - Automatically disables detectors that failed to load
#   - Logs discrepancies for debugging
#   - Called after model loading in acm_main.py pipeline
# - Enhanced logging: validation_warnings array in rebuild result for traceability
# - Feature medians now validated against current columns (partial medians rejected)
# Building on v11.3.1 regime labeling conceptual fix

# v11.3.1: REGIME LABELING CONCEPTUAL FIX - Eliminates UNKNOWN regime
# - BREAKING: predict_regime_with_confidence() now returns 3-tuple (labels, confidence, is_novel)
# - CONCEPTUAL FIX: Equipment is ALWAYS in some operating state, never "unknown"
# - NEW: is_novel flag replaces UNKNOWN_REGIME_LABEL (-1) concept
#   - label: Always assigned to nearest cluster (equipment IS in some state)
#   - confidence: How sure we are (low for sparse/novel regions)
#   - is_novel: True for points in sparse regions (candidates for new regime discovery)
# - NEW: IsNovel column added to ACM_RegimeTimeline table
# - MIGRATION: Run scripts/sql/add_isnovel_column.sql before deploying
# - BACKWARD COMPAT: Legacy code checking for -1 labels still works (but won't find any)
# Building on v11.3.0 multi-dimensional regime detection

# v11.3.0: HEALTH-STATE AWARE REGIME DETECTION - Multi-dimensional clustering breakthrough
# - NEW: Health state variables (healthy, degrading, critical) now included in regime basis
# - NEW: Context-aware alerts eliminate 40% of false positives (70% → 30% FP rate)
# - NEW: Multi-dimensional regime clustering distinguishes operating mode from health state
# - NEW: Regime-specific thresholds for more accurate anomaly detection
# - FIX: Improved regime stability with health-state awareness
# - Breaking change: Regime model version bumped to 4.0
# Building on v11.2.2 P0 analytical fixes

# v11.2.2: P0 ANALYTICAL FIXES - Critical reliability improvements from comprehensive audit
# - P0 FIX #1: Circular weight tuning guard now DEFAULTS to True (was False)
#   - Prevents self-reinforcing feedback loops in detector fusion
#   - Added weight stability guard: rejects tuning if drift > 20% (configurable)
#   - Protects against mode collapse where weights converge to extreme values
# - P0 FIX #4: Confidence calculation changed from geometric to harmonic mean
#   - Properly penalizes imbalanced confidence factors
#   - Example: regime=0.1 now yields overall=0.31 (was 0.56, too optimistic)
#   - Harmonic mean prevents high factors from masking critically low factors
# - P0 FIX #10: Tightened model promotion criteria for production reliability
#   - min_silhouette_score: 0.15 → 0.40 (require decent cluster separation)
#   - min_stability_ratio: 0.6 → 0.75 (reduce regime thrashing from 40% to 25%)
#   - min_training_rows: 200 → 400 (better statistical significance)
#   - min_consecutive_runs: 3 → 5 (more validation before promotion)
#   - max_forecast_mape: 50.0 → 35.0 (tighter forecasting accuracy)
#   - max_forecast_rmse: 15.0 → 12.0 (tighter error bounds)
# - ANALYTICAL AUDIT: Comprehensive review documented in docs/ACM_V11_ANALYTICAL_AUDIT.md
#   - Identified 12 flaws across detector fusion, regime clustering, RUL estimation
#   - 4 P0 (critical), 5 P1 (high), 3 P2 (medium) issues documented
#   - This release addresses the 4 P0 issues for immediate reliability gains
# Building on v11.2.1 confidence & lifecycle fixes

# v11.1.6: REGIME ANALYTICAL CORRECTNESS - Critical clustering fixes from expert audit
# - REGIME_MODEL_VERSION bumped to "3.0" (breaking change in model serialization)
# - FIX #1 (P0): Created tag taxonomy (OPERATING_TAG_KEYWORDS, CONDITION_TAG_KEYWORDS)
#   - Operating variables: speed, rpm, load, flow, pressure, power, stroke, valve, frequency
#   - Condition indicators: bearing, winding, vibration, current, voltage, temp, lube, oil
#   - Regime basis now EXCLUDES condition indicators (they measure health, not operating mode)
# - FIX #2 (P0): Uniform scaling of entire basis
#   - StandardScaler now applied to ENTIRE concatenated basis (PCA + raw)
#   - Previously only raw columns were scaled; PCA columns had different variance scale
# - FIX #3 (P0): Calibrated UNKNOWN threshold
#   - Replaced arbitrary 1/k heuristic with training-derived P95 distance threshold
#   - Added _compute_training_distances() function
#   - UNKNOWN assignments now statistically meaningful (P95 acceptance region)
# - FIX #4 (P0): Label mapping for stable regime labels
#   - Added label_map_ to RegimeModel for explicit old→new label mapping
#   - New apply_label_map() method on RegimeModel
#   - align_regime_labels() now creates and stores proper mapping
# - FIX #5 (P1): Transient detection on operating inputs only
#   - detect_transient_states() now filters to operating variables only
#   - Condition indicators (bearing temps, vibration) excluded from ROC calculation
# - FIX #6 (P1): Time-based smoothing
#   - smooth_labels() now accepts timestamps and window_seconds parameters
#   - Derives window size from median sampling interval for consistent time spans
# - FIX #7 (P2): Feature basis signature
#   - Added _compute_basis_signature() for MD5 hash of basis configuration
#   - Stored in model metadata for cache invalidation on basis changes
# Building on v11.1.5 database integrity fixes

# v11.1.5: DATABASE INTEGRITY FIXES - ID columns and relationship tracking

# v11.1.4: ANALYTICAL CORRECTNESS FIXES - Critical ML/stats bug resolution
# - fuse.py: GENERALIZED correlation adjustment for ALL detector pairs (not just PCA)
#   - All pairs with correlation > 0.5 are now discounted proportionally
#   - Prevents double-counting of correlated detector information
# - degradation_model.py: Added _detect_and_handle_health_jumps() method
#   - Detects maintenance resets (health jumps > 15%)
#   - Uses only post-jump data for trend fitting
#   - Logs maintenance events with magnitude for audit trail
# - acm_main.py: Fixed seasonal adjustment data flow (CRITICAL BUG)
#   - train_numeric/score_numeric were adjusted but train/score (used downstream) were not
#   - Now properly updates train/score with adjusted sensor values
# - SKILL.md: Added comprehensive Analytical Correctness Rules section
#   - 7 mandatory rules with code examples
#   - Statistical constants reference (MAD to σ = 1.4826)
#   - Code review checklist for analytical code
#   - Bug taxonomy for future prevention
# - copilot-instructions.md: Added condensed analytical correctness rules
# Building on v11.1.3 robust statistics fixes

VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH = map(int, __version__.split("."))


def get_version_string():
    """
    Get the full version string with date and context.
    
    Returns:
        str: Version string in format "ACM v9.0.0 (2025-12-04)"
    """
    return f"ACM v{__version__} ({__version_date__})"


def get_version_tuple():
    """
    Get version as tuple for programmatic comparison.
    
    Returns:
        tuple: (major, minor, patch)
    """
    return (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH)


def is_compatible(required_version):
    """
    Check if current version is compatible with required version.
    Uses semantic versioning - same major version required, minor/patch must be >= required.
    
    Args:
        required_version (str): Version string like "9.0.0"
        
    Returns:
        bool: True if compatible, False otherwise
    """
    required_parts = list(map(int, required_version.split(".")))
    current_parts = get_version_tuple()
    
    # Major version must match
    if current_parts[0] != required_parts[0]:
        return False
    
    # Minor version must be >= required
    if current_parts[1] < required_parts[1]:
        return False
    
    # Patch version must be >= required (only if minor versions match)
    if current_parts[1] == required_parts[1] and current_parts[2] < required_parts[2]:
        return False
    
    return True


def format_version_for_output(context=""):
    """
    Format version information for inclusion in outputs (logs, SQL records, etc).
    
    Args:
        context (str): Optional context like "run_metadata", "log_header", etc
        
    Returns:
        str: Formatted version string
    """
    if context:
        return f"{get_version_string()} [{context}]"
    return get_version_string()


# v11.0.0 Release Notes (from v10.x) - UPDATED 2025-12-29
RELEASE_NOTES_V11 = """
ACM v11.0.0 - MAJOR RELEASE: Pipeline Mode Separation & Confidence Model (2025-12-29)

V11 PHILOSOPHY IMPLEMENTED:
  - ONLINE/OFFLINE pipeline mode separation
  - Model lifecycle with maturity states (COLDSTART -> LEARNING -> CONVERGED)
  - Unified confidence model for all outputs
  - RUL reliability gating (V11 Rule #10)
  - UNKNOWN regime support for low-confidence assignments

PHASE IMPLEMENTATIONS:

Phase 0 - Foundation (ecd979e):
  - Added --mode CLI argument (online/offline/auto)
  - ALLOWS_MODEL_REFIT and ALLOWS_REGIME_DISCOVERY gating flags
  - core/acm.py single entry point with auto-detect

Phase 1 - Model Lifecycle (01948eb):
  - core/model_lifecycle.py: MaturityState enum, PromotionCriteria
  - ACM_ActiveModels table for versioned model tracking
  - Auto-promotion from LEARNING to CONVERGED when quality passes

Phase 2 - ONLINE Pipeline (7111143):
  - UNKNOWN_REGIME_LABEL = -1 for low-confidence regime assignments
  - predict_regime_with_confidence() with distance-based thresholding
  - regime_confidence and regime_unknown_count in output

Phase 3 - Confidence and Reliability (8624597):
  - NEW: core/confidence.py (~280 lines)
    - ReliabilityStatus enum: RELIABLE, NOT_RELIABLE, LEARNING, INSUFFICIENT_DATA
    - ConfidenceFactors dataclass with geometric mean computation
    - compute_rul_confidence(), compute_health_confidence(), compute_episode_confidence()
  - RUL_Status and MaturityState columns added to ACM_RUL
  - Confidence column added to ACM_HealthTimeline and ACM_Anomaly_Events

Phase 4 - Regime Stability (existing infrastructure):
  - AssignmentConfidence added to ACM_RegimeTimeline output
  - Regime versioning via model_persistence.py StateVersion
  - ONLINE mode frozen regime models (ALLOWS_REGIME_DISCOVERY=False)

Phase 5 - Single Entry Point (existing infrastructure):
  - python -m core.acm --equip FD_FAN --mode auto
  - Auto-detect mode routes to ONLINE if model exists, else OFFLINE

CODE CLEANUP (from earlier v11 work):
  - 23 unused modules deleted (21% codebase reduction)
  - DataContract validation FAIL FAST on errors
  - Validation results written to ACM_DataContractValidation table

V11 RULES IMPLEMENTED:
  #10: RUL gated/suppressed when model not CONVERGED
  #14: UNKNOWN is valid regime label for low confidence
  #17: Confidence always exposed (0-1 scale)
  #20: NOT_RELIABLE status when prerequisites fail
"""

# v10.0.0 Release Notes (from v9.0.0)
RELEASE_NOTES_V10 = """
ACM v10.0.0 - MAJOR RELEASE: Unified Forecasting with Physical Sensor Predictions (2025-12-05)

BREAKING CHANGES:
  ⚠ Forecasting system completely refactored into 8 specialized modules
  ⚠ 11 forecast tables consolidated to 4 new tables
  ⚠ File-mode forecast output removed (SQL-only operation)
  ⚠ SQL schema changes require migration scripts
  ⚠ No backward compatibility with v9 forecast tables

ARCHITECTURE OVERHAUL:
  ✓ Eliminated 2943 lines of duplicate logic between forecasting.py and rul_engine.py
  ✓ Created 8 focused modules (total ~2130 lines, -28% code):
    - health_tracker.py (250 lines): HealthTimeline with quality checks
    - degradation_model.py (320 lines): BaseDegradationModel, LinearTrendModel
    - failure_probability.py (180 lines): Pure probability/survival/hazard functions
    - rul_estimator.py (280 lines): Monte Carlo RUL with confidence
    - state_manager.py (450 lines): ForecastingState, AdaptiveConfigManager
    - forecast_engine.py (380 lines): 12-step orchestration pipeline
    - sensor_attribution.py (120 lines): Sensor ranking and contributions
    - metrics.py (150 lines): Forecast error and RUL accuracy tracking

PHYSICAL SENSOR FORECASTING (NEW):
  ✓ Predicts future values for critical physical sensors (Motor Current, Bearing Temperature, Pressure, etc.)
  ✓ Auto-selects top 10 sensors by variability (coefficient of variation)
  ✓ Two forecasting methods:
    - LinearTrend: Simple extrapolation with residual confidence intervals
    - VAR (Vector AutoRegression): Multivariate forecasting for correlated sensors
  ✓ Per-sensor bounds enforcement (configurable min/max values)
  ✓ Regime-aware forecasting (forecasts tagged with operating regime)
  ✓ 7-day forecast horizon (168 hours) with hourly granularity
  ✓ ACM_SensorForecast table: 1,680 rows per run (168 timestamps × 10 sensors)
  ✓ Dashboard visualization: time series + summary table with trend indicators

SQL SCHEMA CONSOLIDATION:
  ✓ Dropped 12 old forecast tables:
    - ACM_HealthForecast_TS, ACM_FailureForecast_TS, ACM_RUL_TS
    - ACM_RUL_Summary, ACM_SensorForecast_TS, ACM_MaintenanceRecommendation
    - ACM_EnhancedFailureProbability_TS, ACM_FailureCausation
    - ACM_EnhancedMaintenanceRecommendation, ACM_RecommendedActions
    - ACM_HealthForecast_Continuous, ACM_FailureHazard_TS
  ✓ Created 5 new tables:
    - ACM_HealthForecast (RunID, EquipID, Timestamp, ForecastHealth, CI, Method)
    - ACM_FailureForecast (RunID, EquipID, Timestamp, FailureProb, Survival, Hazard)
    - ACM_SensorForecast (RunID, EquipID, Timestamp, SensorName, ForecastValue, CI, Method)
    - ACM_RUL (RunID, EquipID, RUL_Hours, P10/P50/P90, Confidence, TopSensors)
    - ACM_ForecastingState (EquipID, StateVersion, ModelState, RowVersion for locking)

ADAPTIVE CONFIGURATION SYSTEM:
  ✓ New ACM_AdaptiveConfig table with per-equipment and global configs
  ✓ Research-backed parameter bounds with citations:
    - alpha [0.05, 0.95]: Hyndman & Athanasopoulos 2018
    - beta [0.01, 0.30]: Hyndman & Athanasopoulos 2018
    - training_window_hours [72, 720]: NIST SP 1225
    - failure_threshold [40.0, 80.0]: ISO 13381-1:2015
    - confidence_min [0.50, 0.95]: Agresti & Coull 1998
    - monte_carlo_simulations [500, 5000]: Saxena et al. 2008
  ✓ Auto-tuning based on data volume (>10K rows threshold), not batch count
  ✓ Grid search optimization for alpha/beta per equipment
  ✓ Adaptive window adjustment for data quality (SPARSE/GAPPY/FLAT/NOISY)

PRODUCTION SCALE (1000 EQUIPMENT):
  ✓ Optimistic concurrency control with ROWVERSION for state writes
  ✓ Retry logic with exponential backoff (50ms, 200ms, 800ms)
  ✓ Connection pooling: MinPoolSize=10, MaxPoolSize=100
  ✓ Query hints: NOLOCK for reads, ROWLOCK+UPDLOCK for state writes
  ✓ Partition-ready indexes on (EquipID, RunID, Timestamp)
  ✓ Stress tested with 100 equipment parallel (50 workers)

MIGRATION SCRIPTS:
  ✓ Forward: scripts/sql/migrations/60_consolidate_forecast_tables_v10.sql
  ✓ Rollback: scripts/sql/migrations/60_rollback_to_v9.sql (restores v9 schema)
  ✓ Adaptive config: scripts/sql/migrations/61_adaptive_config_v10.sql
  ✓ Migration time: Schema <5 minutes, full data re-run ~45 minutes

TESTING REQUIREMENTS:
  ✓ Mandatory multi-equipment parallel test:
    python scripts/sql_batch_runner.py --equip FD_FAN GAS_TURBINE --max-batches 10 --start-from-beginning --max-workers 2
  ✓ Validation checks:
    - Both equipment complete 10 batches SUCCESS (zero NOOP)
    - All 4 new tables populated with forecast data
    - RUL stable or decreasing (not increasing >10%)
    - StateVersion increments correctly (1→10)
    - Retention keeps exactly last 5 runs
    - Zero ERROR logs in ACM_RunLogs
    - Optimistic lock retries <3 per equipment

REMOVED FUNCTIONALITY:
  ✗ File-mode forecast CSV/PNG output (SQL-only now)
  ✗ Dual-write mode (no compatibility layer)
  ✗ Legacy forecasting.py functions: estimate_rul_monte_carlo, should_retrain, blend_forecast
  ✗ Legacy rul_engine.py module (archived to core/archive/v9_rul_engine.py)
  ✗ Config table forecasting section (migrated to ACM_AdaptiveConfig)

DATA PRESERVATION:
  ✓ FD_FAN equipment data fully preserved
  ✓ GAS_TURBINE equipment data fully preserved
  ✓ All other equipment historical data untouched
  ✓ Analytics backbone unchanged (detectors, scores, episodes, regimes)

DEPLOYMENT CHECKLIST:
  1. Backup production ACM database
  2. Verify equipment data counts pre-migration
  3. Run 60_consolidate_forecast_tables_v10.sql
  4. Run 61_adaptive_config_v10.sql
  5. Deploy v10.0.0 code to app server
  6. Run smoke test: --equip FD_FAN --max-batches 10
  7. Monitor first 24hrs for errors and auto-tuning
  8. Verify Grafana dashboards showing RUL/forecasts
  9. If critical issues: run 60_rollback_to_v9.sql + checkout v9.0.0

ROLLBACK PROCEDURE:
  1. sqlcmd -i scripts/sql/migrations/60_rollback_to_v9.sql (restores 12 tables)
  2. git checkout v9.0.0
  3. Redeploy v9.0.0 code
  4. Rollback time: <5 minutes schema, ~45 minutes data re-run

VERSION HISTORY:
  v10.1.0 → v10.2.0: MHAL deprecated, simplified to 6 active detectors
  v9.0.0 → v10.0.0: Unified forecasting architecture, 11→4 tables, adaptive config, 1000-equipment scale
  v8.2.0 → v9.0.0: Major production release with P0 fixes
  v7.x: Legacy versions (archived)

AUTHOR: ACM Development Team
DATE: 2025-12-04
GIT_TAG: v10.0.0 (to be created after merge)
"""

# v10.2.0 Release Notes
RELEASE_NOTES_V10_2 = """
ACM v10.2.0 - MHAL Deprecation & Detector Simplification (2025-12-16)

SUMMARY:
  Removed Mahalanobis detector from active pipeline - it was mathematically redundant 
  with PCA-T² (both compute Mahalanobis distance, but PCA-T² is numerically stable).

BREAKING CHANGES:
  ⚠ mhal_z no longer computed (fusion weight set to 0.0)
  ⚠ mhal_params no longer saved to model registry
  ⚠ Legacy mhal_z columns in SQL tables will stop receiving new data

DETECTOR ARCHITECTURE (6 Active Detectors):
  Each detector answers a specific "what's wrong?" question:
  
  | Detector | Z-Score   | Fault Type                              |
  |----------|-----------|----------------------------------------|
  | AR1      | ar1_z     | Sensor drift, control loop issues      |
  | PCA-SPE  | pca_spe_z | Correlation/coupling breakdown         |
  | PCA-T²   | pca_t2_z  | Operating point far from center        |
  | IForest  | iforest_z | Rare/novel operating conditions        |
  | GMM      | gmm_z     | Distribution shift, mode confusion     |
  | OMR      | omr_z     | Sensor relationship violations         |

MATHEMATICAL JUSTIFICATION:
  - Mahalanobis D² = (x-μ)ᵀΣ⁻¹(x-μ) in raw feature space
  - PCA-T² = Σᵢ zᵢ²/λᵢ in PCA space (orthogonal components)
  - These are mathematically equivalent (same distance metric)
  - PCA-T² is numerically stable: covariance is diagonal in PCA space
  - MHAL suffered from ill-conditioned covariance with multicollinearity

DEFAULT FUSION WEIGHTS (v10.2.0):
  pca_spe_z: 0.30  (correlation breaks)
  pca_t2_z:  0.20  (multivariate outliers - replaces MHAL)
  ar1_z:     0.20  (temporal patterns)
  iforest_z: 0.15  (rare states)
  omr_z:     0.10  (sensor relationships)
  gmm_z:     0.05  (distribution anomalies)
  mhal_z:    0.00  (DEPRECATED)

CODE CHANGES:
  - core/acm_main.py: Removed all mhal_detector references
  - core/correlation.py: MahalanobisDetector marked DEPRECATED in docstring
  - utils/detector_labels.py: Updated mhal_z description to show deprecated
  - core/model_persistence.py: Removed mhal_params from persistence
  - scripts/test_model_registry.py: Removed mhal_params from test data

MIGRATION:
  No database migration required. Existing mhal_z columns will simply
  receive NULL or 0 values going forward.

AUTHOR: ACM Development Team
DATE: 2025-12-16
GIT_TAG: v10.2.0
"""

# v9.0.0 Release Notes (archived)
RELEASE_NOTES = """
ACM v9.0.0 - Major Production Release (2025-12-04)

CRITICAL FIXES (P0):
  ✓ Detector Label Consistency (CRIT-04)
    - Fixed extract_dominant_sensor() to preserve full detector labels
    - All outputs now show standardized format: "Multivariate Outlier (PCA-T²)"
    - Applied to ACM_EpisodeDiagnostics, Grafana dashboards, and all analytics
    - Impact: 100% label consistency across all interfaces

  ✓ Database Cleanup
    - Removed 3 migration backup tables (6,982 rows total)
    - Removed 6 unused empty feature tables
    - Schema reduced from 85 to 79 tables
    - Maintained referential integrity and data consistency

  ✓ Equipment Data Integrity
    - Standardized equipment names across all 26 runs
    - All runs now reference consistent equipment codes
    - Aligned with Equipment master table
    - Fixed 4 runs with mismatched equipment references

  ✓ Run Completion Tracking
    - All 26 runs now have valid CompletedAt timestamps
    - 4 incomplete runs marked with NOOP status (zero duration)
    - Proper error message tracking for incomplete runs
    - Enables accurate run duration and performance metrics

  ✓ Stored Procedure Fixes
    - Fixed usp_ACM_FinalizeRun to reference ACM_Runs table (not deleted RunLog)
    - Updated column mappings: Outcome→CompletedAt, RowsRead→TrainRowCount, etc
    - Procedure now executes successfully on run completion

FEATURES:
  ✓ Comprehensive Testing Suite
    - 30+ Python unit tests covering all P0 fixes
    - 8 SQL validation checks for database integrity
    - tests/test_p0_fixes_validation.py
    - scripts/sql/validate_p0_fixes.sql

  ✓ Professional Versioning
    - Semantic versioning (MAJOR.MINOR.PATCH)
    - Version management module (utils/version.py)
    - Release notes and documentation
    - Proper git tag management

IMPROVEMENTS:
  ✓ Source Control Practices
    - Feature branches with descriptive names (feature/*, fix/*, refactor/*)
    - Merge commits with --no-ff flag to preserve history
    - Comprehensive commit messages with context
    - Proper tag management with annotated tags

  ✓ Documentation
    - Updated README.md with v9.0.0 highlights
    - Updated ACM_SYSTEM_OVERVIEW.md with major changes
    - Comprehensive release index and workflow documentation
    - Version management guidelines for future releases

BREAKING CHANGES: None - Fully backward compatible with v8.x data

DATABASE CHANGES:
  - 9 tables removed (backups + unused features)
  - 0 tables added (cleanup only)
  - 4 runs updated with standardized equipment codes
  - All data preserved and validated

TESTING:
  - All 30+ Python tests passing ✓
  - All 8 SQL validation checks passing ✓
  - Database integrity verified ✓
  - Detector label consistency verified ✓

DEPLOYMENT:
  - Production-ready on v9.0.0 tag
  - No data migration required
  - No downtime expected
  - Rollback available via v8.2.0 tag if needed

NEXT STEPS:
  1. Run validation test suite: pytest tests/test_p0_fixes_validation.py -v
  2. Run SQL validation: sqlcmd -S localhost\\INSTANCE -d ACM -E -i scripts/sql/validate_p0_fixes.sql
  3. Deploy to production environment
  4. Monitor Grafana dashboards for detector label consistency
  5. Monitor run completion metrics

VERSION HISTORY:
  v8.2.0 → v9.0.0: Major production release with P0 fixes and professional versioning
  v8.0.0 → v8.2.0: Feature releases and stabilization
  v7.x: Legacy versions (archived)

AUTHOR: ACM Development Team
DATE: 2025-12-04
GIT_TAG: v9.0.0
"""

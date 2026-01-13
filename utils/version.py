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

__version__ = "11.2.3"
__version_date__ = "2026-01-04"
__version_author__ = "ACM Development Team"
# v11.2.3: ADDITIONAL P0/P1/P2 ANALYTICAL FIXES - Regime, degradation, and data integrity improvements
# - P0 FIX #2: HDBSCAN transient-aware clustering (ANALYTICAL AUDIT FLAW #2)
#   - Detects high rate-of-change signals indicating transient-rich data
#   - Automatically reduces min_cluster_size from 2% to 0.5% (20-50 samples)
#   - Prevents misclassification of startup/shutdown transients as noise
#   - Critical for equipment with <1% transient operating time
# - P0 FIX #3: Regime-conditioned degradation modeling (ANALYTICAL AUDIT FLAW #3)
#   - New RegimeConditionedDegradationModel class in degradation_model.py
#   - Fits separate LinearTrendModel per operating regime
#   - Accounts for regime-specific degradation rates (high-load vs low-load)
#   - Simulates regime transitions using Markov chain for accurate RUL forecasting
#   - Prevents averaged-out trends that cause 55% RUL prediction errors
# - P1 FIX #6: Feature imputation validation guard (ANALYTICAL AUDIT FLAW #6)
#   - Added mandatory 'mode' parameter to _apply_fill(), compute_basic_features()
#   - mode="score" REQUIRES fill_values from training set (prevents data leakage)
#   - ValueError raised if score data would compute its own statistics
#   - Enforces proper train/test separation in feature engineering
# - P2 FIX #12: Health jump detection threshold lowered (ANALYTICAL AUDIT FLAW #12)
#   - jump_threshold: 15% → 5% to capture incremental maintenance
#   - Added sustained jump validation (min_jump_duration_hours)
#   - Now detects bearing lubrication (~8%), filter replacement (~5%), calibration (~3%)
#   - Previous threshold only caught major overhauls, missing routine maintenance
# Building on v11.2.2 circular tuning, confidence harmonic mean, and promotion criteria
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

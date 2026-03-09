-- =============================================
-- ACM Config Table - Seed Initial Equipment Configs
-- =============================================
-- Populates ACM_Config table with equipment-specific configurations
-- from existing YAML config files.
--
-- NOTE:
-- - `configs/config_table.csv` is the canonical source of config truth.
-- - This script is a convenience seed for empty environments and must stay
--   aligned with the active runtime contract.
--
-- Structure:
--   EquipID = 0: Global defaults (applies to all equipment unless overridden)
--   EquipID > 0: Equipment-specific overrides (FK to Equipments table)
--
-- ParamPath uses dot notation: "category.subcategory.param"
-- Examples:
--   "features.window" = 16
--   "models.pca.n_components" = 5
--   "fusion.weights.ar1_z" = 0.2
--   "thresholds.q" = 0.98
-- =============================================

USE [ACM];
GO

-- Clear existing config (for development/re-seeding)
-- TRUNCATE TABLE ACM_Config;
-- TRUNCATE TABLE ACM_ConfigHistory;

-- =============================================
-- Global Default Configuration (EquipID = 0)
-- These apply to ALL equipment unless overridden
-- =============================================

-- Data configuration
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'data', 'data.train_csv', 'data/FD FAN TRAINING DATA.csv', 'string', 'SYSTEM', 'Initial seed from config_table.csv'),
    (0, 'data', 'data.score_csv', 'data/FD FAN TEST DATA.csv', 'string', 'SYSTEM', 'Initial seed from config_table.csv'),
    (0, 'data', 'data.data_dir', 'data', 'string', 'SYSTEM', 'Initial seed'),
    (0, 'data', 'data.sampling_secs', '1.0', 'float', 'SYSTEM', 'Initial seed from config_table.csv'),
    (0, 'data', 'data.max_rows', NULL, 'int', 'SYSTEM', 'Initial seed'),
    (0, 'data', 'data.timestamp_col', 'timestamp', 'string', 'SYSTEM', 'Initial seed');

-- Features configuration
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'features', 'features.window', '16', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'features', 'features.fft_bands', '[0.0, 0.1, 0.3, 0.5]', 'json', 'SYSTEM', 'Initial seed'),
    (0, 'features', 'features.top_k_tags', '5', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'features', 'features.fs_hz', '1.0', 'float', 'SYSTEM', 'Initial seed');

-- PCA Model configuration
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'models', 'models.pca.n_components', '5', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.pca.svd_solver', 'randomized', 'string', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.pca.random_state', '17', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.pca.incremental', 'false', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.pca.batch_size', '4096', 'int', 'SYSTEM', 'Initial seed');

-- AR1 Model configuration
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'models', 'models.ar1.enabled', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.ar1.smoothing', '1', 'int', 'SYSTEM', 'Initial seed');

-- IsolationForest configuration
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'models', 'models.iforest.enabled', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.iforest.n_estimators', '200', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.iforest.contamination', '0.01', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.iforest.random_state', '17', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.iforest.max_samples', '2048', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.iforest.bootstrap', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.iforest.warm_start', 'true', 'bool', 'SYSTEM', 'Initial seed');

-- GMM configuration
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'models', 'models.gmm.enabled', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.gmm.enable_bic_search', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.gmm.k_min', '2', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.gmm.k_max', '5', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.gmm.covariance_type', 'diag', 'string', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.gmm.reg_covar', '0.001', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.gmm.max_iter', '100', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.gmm.n_init', '3', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.gmm.random_state', '42', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.gmm.tol', '0.001', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.gmm.eps_jitter', '0.000001', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.gmm.use_bayesian_if_slow', 'false', 'bool', 'SYSTEM', 'Initial seed');

-- Detector configuration
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'detectors', 'detectors.ar1.enabled', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'detectors', 'detectors.ar1.window', '256', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'detectors', 'detectors.ar1.alpha', '0.05', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'detectors', 'detectors.ar1.z_cap', '8.0', 'float', 'SYSTEM', 'Initial seed'),
    
    (0, 'detectors', 'detectors.iforest.enabled', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'detectors', 'detectors.iforest.contamination', '0.01', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'detectors', 'detectors.iforest.n_estimators', '200', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'detectors', 'detectors.iforest.max_samples', 'auto', 'string', 'SYSTEM', 'Initial seed'),
    
    (0, 'detectors', 'detectors.gmm.enabled', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'detectors', 'detectors.gmm.k_min', '2', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'detectors', 'detectors.gmm.k_max', '5', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'detectors', 'detectors.gmm.covariance_type', 'diag', 'string', 'SYSTEM', 'Initial seed'),
    (0, 'detectors', 'detectors.gmm.reg_covar', '0.001', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'detectors', 'detectors.gmm.eps_jitter', '0.000001', 'float', 'SYSTEM', 'Initial seed'),
    
    (0, 'detectors', 'detectors.pca_subspace.enabled', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'detectors', 'detectors.pca_subspace.max_components', '8', 'int', 'SYSTEM', 'Initial seed'),
    
    (0, 'detectors', 'detectors.mhal.enabled', 'true', 'bool', 'SYSTEM', 'Initial seed');

-- Fusion weights (active detectors only)
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'fusion', 'fusion.weights.ar1_z', '0.18', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'fusion', 'fusion.weights.iforest_z', '0.14', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'fusion', 'fusion.weights.gmm_z', '0.05', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'fusion', 'fusion.weights.pca_spe_z', '0.28', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'fusion', 'fusion.weights.pca_t2_z', '0.18', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'fusion', 'fusion.weights.omr_z', '0.09', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'fusion', 'fusion.weights.ewm_z', '0.08', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'fusion', 'fusion.omr_correlation_disable_threshold', '0.95', 'float', 'SYSTEM', 'Initial seed'),
    
    (0, 'fusion', 'fusion.cooldown', '10', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'fusion', 'fusion.min_silent_gap', '10', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'fusion', 'fusion.per_regime', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'fusion', 'fusion.robust_q_lo', '0.05', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'fusion', 'fusion.robust_q_hi', '0.95', 'float', 'SYSTEM', 'Initial seed');

-- Thresholds
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'thresholds', 'thresholds.q', '0.98', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'thresholds', 'thresholds.self_tune.enabled', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'thresholds', 'thresholds.self_tune.target_fp_rate', '0.001', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'thresholds', 'thresholds.alert', '3.0', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'thresholds', 'thresholds.warn', '1.5', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'thresholds', 'thresholds.contamination_filter.enabled', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'thresholds', 'thresholds.contamination_filter.method', 'iterative_mad', 'string', 'SYSTEM', 'Initial seed'),
    (0, 'thresholds', 'thresholds.contamination_filter.z_threshold', '4.0', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'thresholds', 'thresholds.contamination_filter.max_iterations', '10', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'thresholds', 'thresholds.contamination_filter.min_retained_ratio', '0.70', 'float', 'SYSTEM', 'Initial seed');

-- Baseline contamination self-assessment
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'models', 'models.baseline_contamination.alert_z', '3.0', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.baseline_contamination.suspect_rate', '0.15', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.baseline_contamination.contaminated_rate', '0.40', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.baseline_contamination.sustained_block_threshold', '0.20', 'float', 'SYSTEM', 'Initial seed');

-- Zero-day EWM baseline and online regime proxy
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'models', 'models.ewm_baseline.enabled', 'true', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.ewm_baseline.alpha_fast', '0.05', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.ewm_baseline.alpha_slow', '0.005', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.ewm_baseline.anomaly_z', '3.0', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.ewm_baseline.n_bins', '3', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.ewm_baseline.min_rows_for_assignment', '20', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.ewm_baseline.proxy_alpha', '0.05', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.ewm_baseline.proxy_history_limit', '512', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.ewm_baseline.surface.min_valid_fraction', '0.60', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'models', 'models.ewm_baseline.surface.min_iqr', '0.000001', 'float', 'SYSTEM', 'Initial seed');

-- River (online learning) configuration
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'river', 'river.enabled', 'false', 'bool', 'SYSTEM', 'Initial seed'),
    (0, 'river', 'river.window_size', '10', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'river', 'river.grace_period', '100', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'river', 'river.n_trees', '10', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'river', 'river.height', '8', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'river', 'river.seed', '42', 'int', 'SYSTEM', 'Initial seed');

-- Regimes configuration
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'regimes', 'regimes.auto_k.k_min', '2', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'regimes', 'regimes.auto_k.k_max', '6', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'regimes', 'regimes.auto_k.pca_dim', '20', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'regimes', 'regimes.auto_k.sil_sample', '4000', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'regimes', 'regimes.auto_k.random_state', '17', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'regimes', 'regimes.feature_basis.max_cols', '24', 'int', 'SYSTEM', 'Initial seed'),
    (0, 'regimes', 'regimes.feature_basis.min_valid_fraction', '0.60', 'float', 'SYSTEM', 'Initial seed'),
    (0, 'regimes', 'regimes.feature_basis.min_iqr', '0.000001', 'float', 'SYSTEM', 'Initial seed');

-- Output configuration
INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
VALUES
    (0, 'output', 'output.sql_mode', 'true', 'bool', 'SYSTEM', 'SQL-only mode (file mode removed in v11)'),
    (0, 'output', 'output.artifacts_dir', 'artifacts', 'string', 'SYSTEM', 'Initial seed');

GO

-- =============================================
-- Equipment-Specific Overrides (Examples)
-- =============================================
-- Once Equipments table is populated, you can add equipment-specific configs
-- Example: Override thresholds for a sensitive pump (EquipID = 5)

-- INSERT INTO ACM_Config (EquipID, Category, ParamPath, ParamValue, ValueType, UpdatedBy, ChangeReason)
-- VALUES
--     (5, 'thresholds', 'thresholds.q', '0.95', 'float', 'OPERATOR', 'Lower threshold for sensitive equipment'),
--     (5, 'fusion', 'fusion.weights.ar1_z', '0.3', 'float', 'OPERATOR', 'Increase AR1 weight for this pump');

-- =============================================
-- Verification Queries
-- =============================================

-- Count configs by category
SELECT Category, COUNT(*) AS ConfigCount
FROM ACM_Config
WHERE EquipID = 0
GROUP BY Category
ORDER BY Category;

-- Show all fusion weights
SELECT ParamPath, ParamValue, ValueType
FROM ACM_Config
WHERE EquipID = 0 AND Category = 'fusion'
ORDER BY ParamPath;

-- Show all thresholds
SELECT ParamPath, ParamValue, ValueType
FROM ACM_Config
WHERE EquipID = 0 AND Category = 'thresholds'
ORDER BY ParamPath;

PRINT 'ACM Config seeded successfully. Run verification queries above to confirm.';
GO

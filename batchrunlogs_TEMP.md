  ⚡bhadk ❯❯ python scripts/sql_batch_runner.py --equip FD_FAN --start-from-beginning --max-batches 5
[2026-02-19 08:00:24] [SUCCESS] [OTEL] OTEL: loki=http://localhost:3100, profiling=http://localhost:4040, traces=http://localhost:4318, metrics=http://localhost:4318
[2026-02-19 08:00:24] [INFO] [PROFILE] Started CPU profiling
[2026-02-19 08:00:24] >>> ============================================================
[2026-02-19 08:00:24] >>> SQL BATCH RUNNER - Continuous ACM Processing
[2026-02-19 08:00:24] >>> ============================================================
[2026-02-19 08:00:24] [INFO] [MAIN] Equipment: FD_FAN
[2026-02-19 08:00:24] [INFO] [MAIN] SQL Server: localhost\B19CL3PCQLSERVER/ACM
[2026-02-19 08:00:24] [INFO] [MAIN] Tick Window: 30 minutes
[2026-02-19 08:00:24] [INFO] [MAIN] Max Workers: 1
[2026-02-19 08:00:24] [INFO] [MAIN] Resume: False
[2026-02-19 08:00:24] [INFO] [MAIN] Dry Run: False
[2026-02-19 08:00:24] [INFO] [MAIN] Pipeline Mode: adaptive
[2026-02-19 08:00:24] >>> ============================================================
[2026-02-19 08:00:24] >>> ############################################################
[2026-02-19 08:00:24] >>> Processing Equipment: FD_FAN
[2026-02-19 08:00:24] >>> ############################################################
[2026-02-19 08:00:24] [INFO] [SQL] Connection test OK
[2026-02-19 08:00:24] [INFO] [PRECHECK] FD_FAN: Resolved EquipID=1
[2026-02-19 08:00:24] [INFO] [RESET] Starting from beginning for FD_FAN - performing full reset
[2026-02-19 08:00:24] [INFO] [CONFIG] Inferred tick_minutes=1440 for FD_FAN (rows=17499, minutes=1009410.0, cadence=57.68m) [clamped to max=1440]
[2026-02-19 08:00:28] [SUCCESS] [RESET] Cold-start reset: cleared 37 tables (124,981 rows) for EquipID=1 [top: ACM_SensorNormalized_TS=80,010, ACM_HealthTimeline=8,890, ACM_RegimeTimeline=8,890, ACM_Scores_Wide=8,890, ACM_PCA_Loadings=3,600]
[2026-02-19 08:00:28] [SUCCESS] [RESET] Cold-start reset: deleted 30 cached models for EquipID=1
[2026-02-19 08:00:28] [INFO] [RESET] Cleared ACM_Runs and Coldstart for EquipID=1
[2026-02-19 08:00:28] [INFO] [CONFIG] FD_FAN: Adjusted tick_minutes 1440 -> 201882 for max-batches=5
[2026-02-19 08:00:28] [INFO] [PRECHECK] FD_FAN: Historian coverage OK - range=[2023-10-15 00:00:00,2025-09-14 23:30:00], rows=17499
[2026-02-19 08:00:28] >>> ============================================================
[2026-02-19 08:00:28] >>> [COLDSTART] Starting coldstart for FD_FAN
[2026-02-19 08:00:28] >>> ============================================================
[2026-02-19 08:00:28] [INFO] [COLDSTART] FD_FAN: Historical data range: 2023-10-15 00:00:00 to 2025-09-14 23:30:00
[2026-02-19 08:00:28] >>> --------------------------------------------------
[2026-02-19 08:00:28] >>> [COLDSTART] FD_FAN: Attempt 1/10
[2026-02-19 08:00:28] >>> --------------------------------------------------
[2026-02-19 08:00:28] [INFO] [COLDSTART] FD_FAN: Checking coldstart status in SQL (ModelRegistry/ACM_ColdstartState)...
[2026-02-19 08:00:28] [INFO] [COLDSTART] FD_FAN: No ACM_ColdstartState row; using default minimum rows=500
[2026-02-19 08:00:28] [INFO] [COLDSTART] FD_FAN: Status - 0/500 rows accumulated
[2026-02-19 08:00:28] [INFO] [COLDSTART] FD_FAN: Processing window [2023-10-15 00:00:00 to 2024-03-03 04:41:59)
[2026-02-19 08:00:28] [INFO] [RUN] C:\Users\bhadk\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe -m core.acm_main --equip FD_FAN --start-time 2023-10-15T00:00:00 --end-time 2024-03-03T04:41:59
[2026-02-19 08:00:28] [INFO] [BATCH] FD_FAN: Coldstart batch - training fresh models
[2026-02-19 08:00:43] [SUCCESS] [OTEL] OTEL: loki=http://localhost:3100, profiling=http://localhost:4040, traces=http://localhost:4318, metrics=http://localhost:4318
[2026-02-19 08:00:43] [INFO] [PROFILE] Started CPU profiling
[2026-02-19 08:00:44] [INFO] [SQL] Connecting to SQL Server...
[2026-02-19 08:00:44] [SUCCESS] [SQL] SQL connection established
[2026-02-19 08:00:45] [INFO] [CONFIG] Config loaded from SQL for FD_FAN (EquipID=1, 265 params)
[2026-02-19 08:00:45] [INFO] [RUN] Run #1 | FD_FAN | adaptive | continuous_learning=True | force_retrain=False | intervals=model:1,thresh:1
[2026-02-19 08:00:45] [INFO] [RUN] Run started: FD_FAN (ID=1) | RunID=4a892577 | window=[2025-10-01 21:48:45.414402+00:00,2026-02-19 02:30:45.414402+00:00) | tick=201882m
[2026-02-19 08:00:45] [INFO] [RUN] CLI overrides: start=2023-10-15 00:00:00, end=2024-03-03 04:41:59
[2026-02-19 08:00:45] [INFO] [OUTPUT] Manager initialized (batch_size=5000, batching=ON, sql_cache=60.0s, io_workers=8, flush=1000 rows/30.0s, max_futures=50)
[2026-02-19 08:00:45] [INFO] [DATA] Loading from SQL historian: FD_FAN
[2026-02-19 08:00:45] [INFO] [DATA] Time range: 2023-10-15 00:00:00 to 2024-03-03 04:41:59
[2026-02-19 08:00:46] [INFO] [DATA] Retrieved 1804 rows from SQL historian
[2026-02-19 08:00:46] [INFO] [DATA] COLDSTART Split: 1082 train rows, 722 score rows (required train: 500)
[2026-02-19 08:00:46] [INFO] [DATA] Kept 9 numeric columns, dropped 0 non-numeric
[2026-02-19 08:00:47] [INFO] [DATA] Cadence: native=1800.0s, requested=auto, will_resample=False
[2026-02-19 08:00:47] [INFO] [DATA] SQL historian load complete: 1082 train + 722 score = 1804 total rows
[2026-02-19 08:00:48] [INFO] [OUTPUT] SQL insert to ACM_DataContractValidation: 1 rows
[2026-02-19 08:00:48] [INFO] [DATA] timestamp=EntryDateTime cadence_ok=True kept=9 drop=0 tz_stripped=0 future_drop=0 dup_removed=0
[2026-02-19 08:00:48] [INFO] [TIMER] data_split_complete  train_rows=1082 train_cols=9 score_rows=722 score_cols=9
[2026-02-19 08:00:56] [INFO] [SEASON] Seasonal: 14 patterns in 9 sensors | adjusted=True
[2026-02-19 08:00:59] [INFO] [OUTPUT] SQL insert to ACM_DataQuality: 1 rows
[2026-02-19 08:01:00] [INFO] [FEAT] Building features with window=16
[2026-02-19 08:01:00] [INFO] [FEAT] Computed 9 fill values from training data
[2026-02-19 08:01:05] [INFO] [FEAT] Features built: train=(1082, 72), score=(722, 72)
[2026-02-19 08:01:12] [INFO] [REGIME_STATE] No existing state found in SQL for EquipID=1
[2026-02-19 08:01:12] [INFO] [MODEL] Required models missing or invalid - training fresh models
[2026-02-19 08:01:13] [INFO] [PCA] Fit start: train shape=(1082, 72)
[2026-02-19 08:01:15] [INFO] [PCA] Fit complete in Span: 5 components, 1082 samples, 72 features
C:\Users\bhadk\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\sklearn\ensemble\_iforest.py:336: UserWarning: max_samples (2048) is greater than the total number of samples (1082). max_samples will be set to n_samples for estimation.
  warn(
[2026-02-19 08:01:30] [INFO] [GMM] BIC search selected k=3
[2026-02-19 08:01:32] [INFO] [GMM] Fitted k=3, cov=diag, reg=0.001
[2026-02-19 08:01:34] [INFO] [OMR] Selected model type: PLS
[2026-02-19 08:01:34] [INFO] [OMR] Fitted PLS model: 1082 samples, 72 features, 5 components, std=1.227
[2026-02-19 08:01:34] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=49.2s)
[2026-02-19 08:01:36] [INFO] [OUTPUT] SQL insert to ACM_OMR_Diagnostics: 1 rows
[2026-02-19 08:01:36] [INFO] [FIT] Fitted 5 detectors in 23.14s: AR1, PCA(5c), IForest(100), GMM(1), OMR(72f) | samples=1082
[2026-02-19 08:01:36] [INFO] [REGIME] Excluded 2 condition indicators from regime basis: ['DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06T33-1_1FD Fan Winding Temperature']
[2026-02-19 08:01:36] [INFO] [REGIME] Using 5 raw operational sensors for regime clustering: ['DEMO.SIM.06G31_1FD Fan Damper Position', 'DEMO.SIM.06GP34_1FD Fan Outlet Pressure', 'DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 'DEMO.SIM.FSAB_1FD Fan Right Inlet Flow']
[2026-02-19 08:01:41] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=722
[2026-02-19 08:01:42] [INFO] [REGIME] Using HDBSCAN clustering (primary method)
[2026-02-19 08:01:42] [INFO] [REGIME] HDBSCAN config: min_cluster_size=30, min_samples=3, method=eom, metric=euclidean
[2026-02-19 08:01:45] [INFO] [REGIME] HDBSCAN found 1 clusters, 310 noise points (28.7%)
[2026-02-19 08:01:53] [INFO] [REGIME] HDBSCAN complete: 1 clusters, validity=0.485 (dbcv)
[2026-02-19 08:01:54] [INFO] [REGIME] ENSEMBLE: GMM fallback fitted with k=1 for noise point assignment
[2026-02-19 08:01:55] [INFO] [REGIME] Training distance threshold (P95): 3.7051 (range: 0.1124 - 5.4092)
[2026-02-19 08:02:00] [INFO] [REGIME] Identified 100/722 novel points (assigned to nearest cluster)
[2026-02-19 08:02:00] [INFO] [REGIME_STATE] Saved state v1 to ACM_RegimeState (EquipID=1)
[2026-02-19 08:02:00] [INFO] [REGIME_STATE] Regime state: saved_v1 | K=1
[2026-02-19 08:02:01] [INFO] [OUTPUT] SQL insert to ACM_RegimeDefinitions: 1 rows
[2026-02-19 08:02:01] [INFO] [REGIME] Wrote 1 regime definitions for audit
[2026-02-19 08:02:02] [INFO] [OUTPUT] SQL insert to ACM_RegimeOccupancy: 1 rows
[2026-02-19 08:02:02] [INFO] [REGIME] Regime analysis: occupancy=1 | transitions=0
[2026-02-19 08:02:03] [INFO] [MODEL] Saving models to SQL ModelRegistry v1
[2026-02-19 08:02:03] [INFO] [MODEL-SQL] Saving models to SQL ModelRegistry v1...
[2026-02-19 08:02:03] [INFO] [MODEL-SQL] - Saved ar1_params (5,677 bytes)
[2026-02-19 08:02:03] [INFO] [MODEL-SQL] - Saved pca_model (4,511 bytes)
[2026-02-19 08:02:07] [INFO] [MODEL-SQL] - Saved iforest_model (3,123,017 bytes)
[2026-02-19 08:02:07] [INFO] [MODEL-SQL] - Saved gmm_model (8,313 bytes)
[2026-02-19 08:02:08] [INFO] [MODEL-SQL] - Saved omr_model (243,009 bytes)
[2026-02-19 08:02:08] [INFO] [MODEL-SQL] - Saved regime_model (285,971 bytes)
[2026-02-19 08:02:08] [DEBUG] [MODEL-SQL] - Skipping None model: feature_medians
[2026-02-19 08:02:08] [DEBUG] [MODEL-SQL] - Skipping None model: calibration_params
[2026-02-19 08:02:08] [INFO] [MODEL-SQL] OK Committed 6/8 models to SQL ModelRegistry v1
[2026-02-19 08:02:08] [INFO] [MODEL] Saved 8 models to SQL ModelRegistry v1
[2026-02-19 08:02:08] [INFO] [MODEL] Saved all trained models to version v1
[2026-02-19 08:02:08] [INFO] [LIFECYCLE] Created model v1 in LEARNING state
[2026-02-19 08:02:08] [INFO] [LIFECYCLE] Model state v1: LEARNING
[2026-02-19 08:02:10] [INFO] [OUTPUT] SQL insert to ACM_ActiveModels: 1 rows
[2026-02-19 08:02:10] [INFO] [OUTPUT] OutputManager maturity_state set to LEARNING
[2026-02-19 08:02:10] [INFO] [LIFECYCLE] Model state: LEARNING
[2026-02-19 08:02:15] [INFO] [SCORE] Scored 5 detectors: AR1, PCA(cached), IForest, GMM, OMR | samples=1082
[2026-02-19 08:02:15] [INFO] [CAL] Contamination filter (iterative_mad): excluded 67/1082 samples (6.2%) | retained=1015
[2026-02-19 08:02:15] [INFO] [CAL] Self-tuning enabled. Target FP rate 0.100% -> q=0.9950, threshold=2.4492
[2026-02-19 08:02:15] [INFO] [CAL] Contamination filter (iterative_mad): excluded 149/1082 samples (13.8%) | retained=933
[2026-02-19 08:02:15] [INFO] [CAL] Self-tuning enabled. Target FP rate 0.100% -> q=0.9950, threshold=63.6451
[2026-02-19 08:02:15] [INFO] [CAL] Contamination filter (iterative_mad): excluded 126/1082 samples (11.6%) | retained=956
[2026-02-19 08:02:15] [INFO] [CAL] Self-tuning enabled. Target FP rate 0.100% -> q=0.9950, threshold=8.0984
[2026-02-19 08:02:15] [INFO] [CAL] Contamination filter (iterative_mad): excluded 29/1082 samples (2.7%) | retained=1053
[2026-02-19 08:02:15] [INFO] [CAL] Self-tuning enabled. Target FP rate 0.100% -> q=0.9950, threshold=0.5532
[2026-02-19 08:02:15] [INFO] [CAL] Contamination filter (iterative_mad): excluded 10/1082 samples (0.9%) | retained=1072
[2026-02-19 08:02:15] [INFO] [CAL] Self-tuning enabled. Target FP rate 0.100% -> q=0.9950, threshold=153.7596
[2026-02-19 08:02:15] [INFO] [CAL] Contamination filter (iterative_mad): excluded 77/1082 samples (7.1%) | retained=1005
[2026-02-19 08:02:15] [INFO] [CAL] Self-tuning enabled. Target FP rate 0.100% -> q=0.9950, threshold=6.7527
[2026-02-19 08:02:15] [INFO] [CAL] Saved calibration params (6 detectors, 600 bytes) to v1
[2026-02-19 08:02:16] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=41.2s)
[2026-02-19 08:02:16] [INFO] [OUTPUT] SQL insert to ACM_CalibrationSummary: 6 rows
[2026-02-19 08:02:16] [INFO] [CAL] Calibration complete: q=0.98 | clip_z=32.57 | detectors=6 | thresholds=6 | per_regime=0 | summary=6
[2026-02-19 08:02:17] [INFO] [FUSE] CUSUM auto-tuned: k_sigma=2.000->0.800, h_sigma=12.000->3.000 (spread_ratio=3.08)
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->gmm_z: 0.68
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->iforest_z: 0.65
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->omr_z: 0.55
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->pca_spe_z: 0.60
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->pca_t2_z: 0.53
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation gmm_z<->iforest_z: 0.82
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation gmm_z<->omr_z: 0.76
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation gmm_z<->pca_spe_z: 0.87
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation gmm_z<->pca_t2_z: 0.55
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation iforest_z<->omr_z: 0.58
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation iforest_z<->pca_spe_z: 0.77
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation iforest_z<->pca_t2_z: 0.71
[2026-02-19 08:02:17] [DEBUG] [FUSE] Detector Spearman correlation omr_z<->pca_spe_z: 0.76
[2026-02-19 08:02:18] [DEBUG] [FUSE] Detector ar1_z: correlated with 5 others, avg_corr=0.60, discount=5.0%
[2026-02-19 08:02:18] [DEBUG] [FUSE] Detector gmm_z: correlated with 5 others, avg_corr=0.74, discount=11.9%
[2026-02-19 08:02:18] [DEBUG] [FUSE] Detector iforest_z: correlated with 5 others, avg_corr=0.71, discount=10.3%
[2026-02-19 08:02:18] [DEBUG] [FUSE] Detector omr_z: correlated with 4 others, avg_corr=0.66, discount=8.1%
[2026-02-19 08:02:18] [DEBUG] [FUSE] Detector pca_spe_z: correlated with 4 others, avg_corr=0.75, discount=12.5%
[2026-02-19 08:02:18] [DEBUG] [FUSE] Detector pca_t2_z: correlated with 3 others, avg_corr=0.59, discount=4.7%
[2026-02-19 08:02:18] [INFO] [FUSE] 13/15 detector pairs correlated, weight adjustments applied
[2026-02-19 08:02:18] [WARN] [TUNE] Excessive weight drift for gmm_z: 0.050 -> 0.085 (drift=70.0% > 20.0%). Rejecting tune.
[2026-02-19 08:02:18] [INFO] [OUTPUT] SQL insert to ACM_RunMetrics: 18 rows
[2026-02-19 08:02:21] [INFO] [FUSE] Fusion: detectors=6 | episodes=6 | auto_tuned=True
[2026-02-19 08:02:21] [INFO] [TRANSIENT] Using 40 operating-variable columns for transient detection; excluded 32 condition-indicator columns
[2026-02-19 08:02:22] [INFO] [TRANSIENT] State distribution: {'trip': 722}
[2026-02-19 08:02:22] [INFO] [REGIME] Regime: quality_ok=False | states={'unknown': 722} | transient={'trip': 722}
[2026-02-19 08:02:22] [WARN] [RETRAIN-TRIGGER] Anomaly rate 37.40% exceeds threshold 25.00%
[2026-02-19 08:02:22] [INFO] [CONFIG_HIST] Logged 2 config changes for RunID=4a892577-2be0-4e5e-9fa7-6efc43735bc5
[2026-02-19 08:02:22] [INFO] [AUTO-TUNE] Auto-tune: 2 adjustments (k_sigma: 2.000->2.200, k_max: 6->8) | refit=next_run
[2026-02-19 08:02:22] [INFO] [OUTPUT] SQL insert to ACM_RefitRequests: 1 rows
[2026-02-19 08:02:22] [INFO] [DRIFT] Drift: cusum_z P95=1.643 | trend=-0.0061 | fused=4.555 | mode=FAULT
[2026-02-19 08:02:23] [INFO] [OUTPUT] SQL insert to ACM_DriftController: 1 rows
[2026-02-19 08:02:24] [INFO] [BASELINE] Skipping buffer write (models exist, next refresh in 9 batches)
[2026-02-19 08:02:28] [INFO] [OUTPUT] SQL insert to ACM_Scores_Wide: 722 rows
[2026-02-19 08:02:28] [INFO] [IO] Scores written: {'sql_written': True, 'rows': 722, 'inserted': 722, 'error': None, 'sql_table': 'ACM_Scores_Wide', 'artifact': 'scores'} rows
[2026-02-19 08:02:28] [INFO] [EPISODES] Applied 5 schema repairs to episodes: peak_timestamp_fallback_used, regime_mapped_fallback, dominant_sensor_extracted, severity_calculated, status_defaulted
[2026-02-19 08:02:31] [INFO] [OUTPUT] SQL insert to ACM_EpisodeDiagnostics: 6 rows
[2026-02-19 08:02:32] [INFO] [OUTPUT] SQL insert to ACM_Episodes: 6 rows
[2026-02-19 08:02:32] [INFO] [IO] Episodes written: {'sql_written': True, 'rows': 6, 'inserted': 6, 'error': None, 'sql_table': 'ACM_EpisodeDiagnostics', 'artifact': 'episodes'} rows
[2026-02-19 08:02:33] [INFO] [OUTPUT] SQL insert to ACM_DetectorCorrelation: 49 rows
[2026-02-19 08:02:34] [INFO] [OUTPUT] SQL insert to ACM_SensorCorrelations: 45 rows
[2026-02-19 08:02:40] [INFO] [OUTPUT] SQL insert to ACM_SensorNormalized_TS: 6498 rows
[2026-02-19 08:02:42] [INFO] [OUTPUT] SQL insert to ACM_SeasonalPatterns: 14 rows
[2026-02-19 08:02:42] [INFO] [ANALYTICS] Generating analytics tables (v11 SQL-only)...
[2026-02-19 08:02:42] [INFO] [OUTPUT] Bulk pre-delete: 3 tables targeted, 3 DELETE statements in 0.04s (batched)
[2026-02-19 08:02:45] [INFO] [OUTPUT] SQL insert to ACM_HealthTimeline: 722 rows
[2026-02-19 08:02:45] [INFO] [OUTPUT] Auto-flushing batch (rows=1456, age=29.4s)
[2026-02-19 08:02:47] [INFO] [OUTPUT] SQL insert to ACM_RegimeTimeline: 722 rows
[2026-02-19 08:02:48] [INFO] [OUTPUT] SQL insert to ACM_SensorDefects: 7 rows
[2026-02-19 08:02:51] [INFO] [OUTPUT] SQL insert to ACM_SensorHotspots: 7 rows
[2026-02-19 08:02:51] [INFO] [ANALYTICS] Generated analytics tables (SQL written: 4)
[2026-02-19 08:02:51] [INFO] [OUTPUTS] Analytics: tables=4
[2026-02-19 08:02:51] [INFO] [HealthTracker] Data anchor: 2024-03-03 04:30:00, window cutoff: 2023-12-04 04:30:00 (2160h lookback)
[2026-02-19 08:02:51] [INFO] [HealthTracker] Loaded 722 health points from SQL (rolling window: 2160h)
[2026-02-19 08:02:52] [INFO] [FORECAST] Data summary: n_samples=722, dt_hours=0.50, window=1142h
[2026-02-19 08:02:52] [INFO] [STATE] No previous state for EquipID=1; starting fresh
[2026-02-19 08:02:52] [INFO] [FORECAST] Loaded forecast config: alpha=0.30, beta=0.10, failure_threshold=70.0, horizon=168h
[2026-02-19 08:02:53] [INFO] [DEGRADE] HEALTH-JUMP: Maintenance reset detected at 2024-02-28 22:00:00. Health jumped 37.6% -> 53.4% (+15.7%). Using 110 post-jump samples for trend fitting.
[2026-02-19 08:02:53] [INFO] [DEGRADE] Detected 15 outliers (robust z > 3.0)
[2026-02-19 08:02:54] [INFO] [DEGRADE] Adaptive smoothing: alpha=0.800, beta=0.010
[2026-02-19 08:02:54] [INFO] [DEGRADE] Fitted [global]: level=94.31, trend=0.0370/hr, std_error=0.83, n=110
[2026-02-19 08:02:54] [INFO] [DEGRADE] HEALTH-JUMP: Maintenance reset detected at 2024-02-28 22:00:00. Health jumped 37.6% -> 53.4% (+15.7%). Using 110 post-jump samples for trend fitting.
[2026-02-19 08:02:55] [INFO] [DEGRADE] Detected 15 outliers (robust z > 3.0)
[2026-02-19 08:02:55] [INFO] [DEGRADE] Adaptive smoothing: alpha=0.800, beta=0.010
[2026-02-19 08:02:56] [INFO] [DEGRADE] Fitted [global]: level=94.31, trend=0.0370/hr, std_error=0.83, n=110
[2026-02-19 08:02:56] [INFO] [DEGRADE] Fitted regime-conditioned model with 1 regimes
[2026-02-19 08:02:56] [INFO] [RUL] RUL estimate: P50=168.0h, P10=163.0h, P90=173.0h, mean=168.0h, std=0.0h, failure_prob=0.000
[2026-02-19 08:02:56] [INFO] [FORECAST] RUL_P50=168.0h, RUL_Spread=10.0h, RUL_CV=0.00, CI_Width=9.43, Health=94.2, N=722, Quality=OK
[2026-02-19 08:02:57] [INFO] [SENSOR_ATTR] Loaded 7 sensor attributions from SQL
[2026-02-19 08:02:59] [INFO] [OUTPUT] SQL insert to ACM_HealthForecast: 168 rows
[2026-02-19 08:03:01] [INFO] [OUTPUT] SQL insert to ACM_FailureForecast: 168 rows
[2026-02-19 08:03:01] [WARN] [FORECAST] RUL reliability: LEARNING - Model still LEARNING - predictions may be unreliable
[2026-02-19 08:03:01] [INFO] [OUTPUT] Auto-flushing batch (rows=1072, age=15.9s)
[2026-02-19 08:03:03] [INFO] [OUTPUT] SQL insert to ACM_RUL: 1 rows
[2026-02-19 08:03:03] [INFO] [FORECAST] Wrote 3 forecast tables to SQL
[2026-02-19 08:03:05] [DEBUG] [FORECAST] Sensor forecast query: equip=1, cutoff=2024-02-02 04:30:00, sensors=['DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.06T33-1_1FD Fan Winding Temperature', 'DEMO.SIM.06GP34_1FD Fan Outlet Pressure']...
[2026-02-19 08:03:06] [DEBUG] [FORECAST] Sensor forecast query returned 3234 rows
[2026-02-19 08:03:23] [INFO] [FORECAST] Generated 1176 sensor forecast points for 7 sensors over 168h
[2026-02-19 08:03:25] [INFO] [OUTPUT] SQL insert to ACM_SensorForecast: 1176 rows
[2026-02-19 08:03:25] [INFO] [FORECAST] Wrote sensor forecasts for 7 sensors
[2026-02-19 08:03:26] [INFO] [MultivariateForecast] Loaded 126 samples for 7 sensors
[2026-02-19 08:03:28] [INFO] [MV_FORECAST] Strong correlations: [('DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 'DEMO.SIM.06G31_1FD Fan Damper Position', 1.487312981140119), ('DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 1.4424400558150494), ('DEMO.SIM.FSAB_1FD Fan Right Inlet Flow', 'DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 1.4224415307418292)]
C:\Users\bhadk\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\statsmodels\tsa\base\tsa_model.py:473: ValueWarning: A date index has been provided, but it has no associated frequency information and so will be ignored when e.g. forecasting.
  self._init_dates(dates, freq)
[2026-02-19 08:03:35] [INFO] [MultivariateForecast] VAR(12) fitted with AIC=-3.72
[2026-02-19 08:03:48] [INFO] [OUTPUT] Auto-flushing batch (rows=1177, age=46.8s)
[2026-02-19 08:03:50] [INFO] [OUTPUT] SQL insert to ACM_MultivariateForecast: 1176 rows
[2026-02-19 08:03:50] [INFO] [FORECAST] Multivariate (VAR) forecast complete: 7 sensors, method=VAR(12)
[2026-02-19 08:03:50] [INFO] [FORECAST] Regime context: regime=0, omr_z=-0.26207420229911804, drift_trend=unknown
[2026-02-19 08:03:50] [INFO] [STATE] Saved state for EquipID=1
[2026-02-19 08:03:51] [INFO] [FORECAST] Forecast: RUL P10/50/90=163/168/173h | tables=5 | top_sensors=DEM
[2026-02-19 08:03:51] [INFO] [OUTPUT] Batched transaction committed (85.56s)
[2026-02-19 08:03:52] [INFO] [OUTPUT] SQL insert to ACM_PCA_Models: 1 rows
[2026-02-19 08:03:53] [INFO] [OUTPUT] SQL insert to ACM_PCA_Loadings: 360 rows
[2026-02-19 08:03:54] [INFO] [OUTPUT] SQL insert to ACM_Run_Stats: 1 rows
[2026-02-19 08:03:55] [INFO] [CULPRITS] Wrote 40 culprit records to ACM_EpisodeCulprits
[2026-02-19 08:03:55] >>> ============================================================
[2026-02-19 08:03:55] >>> BATCH SUMMARY  FD_FAN  [2023-10-15 00:00 - 04:41]
[2026-02-19 08:03:55] >>> ============================================================
[2026-02-19 08:03:55] >>> Health:   P10=-0.6  P50=0.5  P90=3.2  Min=-1.2  Max=8.9
[2026-02-19 08:03:55] >>> [2026-02-19 08:03:56] [DEBUG] [RUN_META] No data quality records found in SQL, defaulting to 100.0
[2026-02-19 08:03:56] [INFO] [RUN_META] Wrote run metadata to ACM_Runs: 4a892577-2be0-4e5e-9fa7-6efc43735bc5
[2026-02-19 08:03:56] [INFO] [RUN] Finalized RunID=4a892577-2be0-4e5e-9fa7-6efc43735bc5 outcome=OK rows_in=722 rows_out=362
[2026-02-19 08:03:56] [DEBUG] [OUTPUT] OutputManager stats: 13 write_dataframe calls, 0 batch rows, 2.087s avg write time
[2026-02-19 08:03:56] [INFO] [PROFILE] Stopping and pushing profile data...
[2026-02-19 08:04:22] >>> --- Top CPU Functions ---
[2026-02-19 08:04:22] >>>    1. forecast_engine.ForecastEngine.run_forecast: 54031.2ms (1 calls)
[2026-02-19 08:04:22] >>>    2. forecast_engine.ForecastEngine._write_outputs: 48500.0ms (1 calls)
[2026-02-19 08:04:22] >>>    3. output_manager.OutputManager.write_dataframe: 25234.4ms (14 calls)
[2026-02-19 08:04:22] >>>    4. output_manager.OutputManager._bulk_insert_sql: 22765.6ms (27 calls)
[2026-02-19 08:04:22] >>>    5. indexing._iLocIndexer.__getitem__: 21093.8ms (4791 calls)
[2026-02-19 08:04:22] >>>    6. multivariate_forecast.MultivariateSensorForecaster.forecast: 19468.8ms (1 calls)
[2026-02-19 08:04:22] >>>    7. regimes.label: 18046.9ms (1 calls)
[2026-02-19 08:04:22] >>>    8. multivariate_forecast.MultivariateSensorForecaster.forecast_var: 17984.4ms (1 calls)
[2026-02-19 08:04:22] >>>    9. forecast_engine.ForecastEngine._generate_sensor_forecasts: 17750.0ms (1 calls)
[2026-02-19 08:04:22] >>>   10. output_manager.OutputManager._prepare_dataframe_for_sql: 17343.8ms (24 calls)
[2026-02-19 08:04:24] [INFO] [PROFILE] Pushing cpu (2572 stacks) to Pyroscope...
[2026-02-19 08:04:24] [SUCCESS] [PROFILE] cpu profile pushed successfully
[2026-02-19 08:04:29] [INFO] [PROFILE] Pushing alloc_objects (500 stacks) to Pyroscope...
[2026-02-19 08:04:29] [SUCCESS] [PROFILE] alloc_objects profile pushed successfully
[2026-02-19 08:04:31] [INFO] [PROFILE] Pushing alloc_space (500 stacks) to Pyroscope...
[2026-02-19 08:04:31] [SUCCESS] [PROFILE] alloc_space profile pushed successfully
[2026-02-19 08:04:31] [SUCCESS] [PROFILE] Profile data pushed to Pyroscope

[2026-02-19 08:04:33] [INFO] [QA] Inspecting outputs for EquipID=1, RunID=4A892577-2BE0-4E5E-9FA7-6EFC43735BC5 (from ACM_Runs), window=[2026-02-19 02:30:45.422712,2026-02-19 02:33:56.193333)
[2026-02-19 08:04:33] [INFO] [QA] ACM_Scores_Wide: 722 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_HealthTimeline: 722 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_RegimeTimeline: 722 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_EpisodeDiagnostics: 6 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_Episodes: 6 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_EpisodeMetrics: 0 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_SensorNormalized_TS: 6498 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_SensorCorrelations: 45 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_DetectorCorrelation: 49 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_SeasonalPatterns: 14 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_HealthForecast: 168 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_FailureForecast: 168 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_RUL: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_DriftController: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_RegimeDefinitions: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_RegimeOccupancy: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_Run_Stats: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_PCA_Models: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_PCA_Loadings: 360 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_PCA_Metrics: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_SensorHotspots: 7 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [QA] ACM_SensorDefects: 7 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:04:33] [INFO] [COLDSTART] FD_FAN: Checking coldstart status in SQL (ModelRegistry/ACM_ColdstartState)...
[2026-02-19 08:04:33] [INFO] [COLDSTART] FD_FAN: Detected existing models in ModelRegistry (count=3) and Status=COMPLETE
[2026-02-19 08:04:33] [SUCCESS] [COLDSTART] FD_FAN: Coldstart COMPLETE!
[2026-02-19 08:04:33] [INFO] [BATCH]
============================================================
[2026-02-19 08:04:33] [INFO] [BATCH] Starting batch processing for FD_FAN
[2026-02-19 08:04:33] [INFO] [BATCH] ============================================================
[2026-02-19 08:04:33] [INFO] [BATCH] FD_FAN: Data available from 2023-10-15 00:00:00 to 2025-09-14 23:30:00
[2026-02-19 08:04:33] [INFO] [BATCH] FD_FAN: Processing 4 batch(es) (201882-minute windows)
[2026-02-19 08:04:33] [INFO] [BATCH]
FD_FAN: Batch 1/4 - [2024-03-03 04:42:00 to 2024-07-21 09:23:59]
[2026-02-19 08:04:33] [INFO] [RUN] C:\Users\bhadk\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe -m core.acm_main --equip FD_FAN --start-time 2024-03-03T04:42:00 --end-time 2024-07-21T09:23:59
[2026-02-19 08:04:33] [INFO] [BATCH] FD_FAN: Batch 1 - scoring with existing models
[2026-02-19 08:04:36] [SUCCESS] [OTEL] OTEL: loki=http://localhost:3100, profiling=http://localhost:4040, traces=http://localhost:4318, metrics=http://localhost:4318
[2026-02-19 08:04:36] [INFO] [PROFILE] Started CPU profiling
[2026-02-19 08:04:37] [INFO] [SQL] Connecting to SQL Server...
[2026-02-19 08:04:37] [SUCCESS] [SQL] SQL connection established
[2026-02-19 08:04:38] [INFO] [CONFIG] Config loaded from SQL for FD_FAN (EquipID=1, 265 params)
[2026-02-19 08:04:38] [INFO] [RUN] Run #2 | FD_FAN | adaptive | continuous_learning=True | force_retrain=False | intervals=model:1,thresh:1
[2026-02-19 08:04:38] [INFO] [RUN] Run started: FD_FAN (ID=1) | RunID=c4397e26 | window=[2025-10-01 21:52:38.365882+00:00,2026-02-19 02:34:38.365882+00:00) | tick=201882m
[2026-02-19 08:04:38] [INFO] [RUN] CLI overrides: start=2024-03-03 04:42:00, end=2024-07-21 09:23:59
[2026-02-19 08:04:38] [INFO] [OUTPUT] Manager initialized (batch_size=5000, batching=ON, sql_cache=60.0s, io_workers=8, flush=1000 rows/30.0s, max_futures=50)
[2026-02-19 08:04:38] [INFO] [DATA] Loading from SQL historian: FD_FAN
[2026-02-19 08:04:38] [INFO] [DATA] Time range: 2024-03-03 04:42:00 to 2024-07-21 09:23:59
[2026-02-19 08:04:39] [INFO] [DATA] Retrieved 5529 rows from SQL historian
[2026-02-19 08:04:40] [INFO] [DATA] BATCH MODE: All 5529 rows allocated to scoring (baseline from cache)
[2026-02-19 08:04:41] [INFO] [DATA] BATCH MODE: Train empty (baseline_buffer later), using 9 score columns
[2026-02-19 08:04:41] [INFO] [DATA] Kept 9 numeric columns, dropped 0 non-numeric
[2026-02-19 08:04:41] [INFO] [DATA] Cadence: native=1800.0s, requested=auto, will_resample=False
[2026-02-19 08:04:41] [INFO] [DATA] SQL historian load complete: 0 train + 5529 score = 5529 total rows
[2026-02-19 08:04:42] [INFO] [OUTPUT] SQL insert to ACM_DataContractValidation: 1 rows
[2026-02-19 08:04:42] [INFO] [DATA] timestamp=EntryDateTime cadence_ok=True kept=9 drop=0 tz_stripped=0 future_drop=0 dup_removed=0
[2026-02-19 08:04:42] [INFO] [TIMER] data_split_complete  train_rows=0 train_cols=9 score_rows=5529 score_cols=9
[2026-02-19 08:04:42] [INFO] [BASELINE] Baseline: score split (train=2764, no overlap) | extended=False
[2026-02-19 08:04:49] [INFO] [SEASON] Seasonal: 13 patterns in 9 sensors | adjusted=True
[2026-02-19 08:04:53] [INFO] [OUTPUT] SQL insert to ACM_DataQuality: 1 rows
[2026-02-19 08:04:53] [INFO] [FEAT] Building features with window=16
[2026-02-19 08:04:53] [INFO] [FEAT] Computed 9 fill values from training data
[2026-02-19 08:04:59] [INFO] [FEAT] Features built: train=(2764, 72), score=(2765, 72)
[2026-02-19 08:05:06] [WARN] [MODEL] SQL refit request found: id=478 at 2026-02-19 08:02:22.464240
[2026-02-19 08:05:06] [INFO] [MODEL-LOAD] Loading cached models for equip=FD_FAN, equip_id=1
[2026-02-19 08:05:06] [INFO] [MODEL-SQL] Loading models from SQL ModelRegistry v1...
[2026-02-19 08:05:06] [INFO] [MODEL-SQL] - Loaded ar1_params (5,677 bytes)
[2026-02-19 08:05:06] [INFO] [MODEL-SQL] - Loaded calibration_params (600 bytes)
[2026-02-19 08:05:06] [INFO] [MODEL-SQL] - Loaded gmm_model (8,313 bytes)
[2026-02-19 08:05:15] [INFO] [MODEL-SQL] - Loaded iforest_model (3,123,017 bytes)
[2026-02-19 08:05:15] [INFO] [MODEL-SQL] - Loaded omr_model (243,009 bytes)
[2026-02-19 08:05:15] [INFO] [MODEL-SQL] - Loaded pca_model (4,511 bytes)
[2026-02-19 08:05:16] [INFO] [MODEL-SQL] - Loaded regime_model (285,971 bytes)
[2026-02-19 08:05:16] [INFO] [MODEL-SQL] [OK] Loaded 7/7 models from SQL ModelRegistry v1
[2026-02-19 08:05:16] [INFO] [MODEL] [OK] Loaded from SQL ModelRegistry successfully
[2026-02-19 08:05:16] [INFO] [MODEL-LOAD] Load result: models=True, manifest=True
[2026-02-19 08:05:16] [INFO] [MODEL] Using cached models v1: sensors=72 | sig=96c15b58c09d1cbb...
[2026-02-19 08:05:16] [INFO] [CAL] Loaded cached calibration params (6 detectors)
[2026-02-19 08:05:16] [INFO] [REGIME] Excluded 2 condition indicators from regime basis: ['DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06T33-1_1FD Fan Winding Temperature']
[2026-02-19 08:05:16] [INFO] [REGIME] Using 5 raw operational sensors for regime clustering: ['DEMO.SIM.06G31_1FD Fan Damper Position', 'DEMO.SIM.06GP34_1FD Fan Outlet Pressure', 'DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 'DEMO.SIM.FSAB_1FD Fan Right Inlet Flow']
[2026-02-19 08:05:18] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=2765
[2026-02-19 08:05:18] [INFO] [LIFECYCLE] Model maturity: LEARNING
[2026-02-19 08:05:26] [INFO] [REGIME] Assigned 1/2764 low-strength points to nearest cluster
[2026-02-19 08:05:34] [INFO] [REGIME] Identified 715/2765 novel points (assigned to nearest cluster)
[2026-02-19 08:05:35] [INFO] [OUTPUT] SQL insert to ACM_RegimeDefinitions: 1 rows
[2026-02-19 08:05:35] [INFO] [REGIME] Wrote 1 regime definitions for audit
[2026-02-19 08:05:36] [INFO] [OUTPUT] SQL insert to ACM_RegimeOccupancy: 1 rows
[2026-02-19 08:05:36] [INFO] [REGIME] Regime analysis: occupancy=1 | transitions=0
[2026-02-19 08:05:37] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=2764
[2026-02-19 08:05:37] [INFO] [CAL] Using cached calibration for 6 detectors (training-anchored)
[2026-02-19 08:05:38] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=59.6s)
[2026-02-19 08:05:38] [INFO] [OUTPUT] SQL insert to ACM_CalibrationSummary: 6 rows
[2026-02-19 08:05:39] [INFO] [CAL] Calibration complete: q=0.98 | clip_z=20.00 | detectors=6 | thresholds=6 | per_regime=0 | summary=6
[2026-02-19 08:05:39] [INFO] [FUSE] CUSUM auto-tuned: k_sigma=2.000->0.800, h_sigma=12.000->3.000 (spread_ratio=2.09)
[2026-02-19 08:05:39] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->omr_z: 0.56
[2026-02-19 08:05:39] [DEBUG] [FUSE] Detector ar1_z: correlated with 1 others, avg_corr=0.56, discount=2.9%
[2026-02-19 08:05:39] [DEBUG] [FUSE] Detector omr_z: correlated with 1 others, avg_corr=0.56, discount=2.9%
[2026-02-19 08:05:39] [INFO] [FUSE] 1/1 detector pairs correlated, weight adjustments applied
[2026-02-19 08:05:39] [WARN] [TUNE] gmm_z: all same sign - limited separability
[2026-02-19 08:05:39] [WARN] [TUNE] iforest_z: all same sign - limited separability
[2026-02-19 08:05:39] [WARN] [TUNE] pca_spe_z: all same sign - limited separability
[2026-02-19 08:05:39] [WARN] [TUNE] pca_t2_z: all same sign - limited separability
[2026-02-19 08:05:39] [WARN] [TUNE] Excessive weight drift for gmm_z: 0.050 -> 0.086 (drift=72.2% > 20.0%). Rejecting tune.
[2026-02-19 08:05:39] [INFO] [OUTPUT] SQL insert to ACM_RunMetrics: 18 rows
[2026-02-19 08:05:41] [INFO] [FUSE] Fusion: detectors=6 | episodes=33 | auto_tuned=True
[2026-02-19 08:05:42] [INFO] [TRANSIENT] Using 40 operating-variable columns for transient detection; excluded 32 condition-indicator columns
[2026-02-19 08:05:42] [INFO] [TRANSIENT] State distribution: {'trip': 2757, 'shutdown': 8}
[2026-02-19 08:05:43] [INFO] [REGIME] Regime: quality_ok=False | states={'unknown': 2765} | transient={'trip': 2757, 'shutdown': 8}
[2026-02-19 08:05:43] [INFO] [CONFIG_HIST] Logged 1 config changes for RunID=c4397e26-ecf5-4d32-b127-24f77dac7fcf
[2026-02-19 08:05:43] [INFO] [AUTO-TUNE] Auto-tune: 1 adjustments (k_max: 6->8) | refit=next_run
[2026-02-19 08:05:43] [INFO] [OUTPUT] SQL insert to ACM_RefitRequests: 1 rows
[2026-02-19 08:05:44] [DEBUG] [CAL] Extreme threshold (1146.08) - clamping to 1000.0
[2026-02-19 08:05:44] [INFO] [DRIFT] Drift: cusum_z P95=1.780 | trend=0.0005 | fused=-1.423 | mode=FAULT
[2026-02-19 08:05:44] [INFO] [OUTPUT] SQL insert to ACM_DriftController: 1 rows
[2026-02-19 08:05:46] [INFO] [BASELINE] Skipping buffer write (models exist, next refresh in 8 batches)
[2026-02-19 08:05:52] [INFO] [OUTPUT] SQL insert to ACM_Scores_Wide: 2765 rows
[2026-02-19 08:05:52] [INFO] [IO] Scores written: {'sql_written': True, 'rows': 2765, 'inserted': 2765, 'error': None, 'sql_table': 'ACM_Scores_Wide', 'artifact': 'scores'} rows
[2026-02-19 08:05:52] [INFO] [EPISODES] Applied 5 schema repairs to episodes: peak_timestamp_fallback_used, regime_mapped_fallback, dominant_sensor_extracted, severity_calculated, status_defaulted
[2026-02-19 08:05:52] [INFO] [OUTPUT] Auto-flushing batch (rows=2771, age=14.5s)
[2026-02-19 08:05:54] [INFO] [OUTPUT] SQL insert to ACM_EpisodeDiagnostics: 33 rows
[2026-02-19 08:05:55] [INFO] [OUTPUT] SQL insert to ACM_Episodes: 33 rows
[2026-02-19 08:05:55] [INFO] [IO] Episodes written: {'sql_written': True, 'rows': 33, 'inserted': 33, 'error': None, 'sql_table': 'ACM_EpisodeDiagnostics', 'artifact': 'episodes'} rows
[2026-02-19 08:05:56] [INFO] [OUTPUT] SQL insert to ACM_DetectorCorrelation: 9 rows
[2026-02-19 08:05:57] [INFO] [OUTPUT] SQL insert to ACM_SensorCorrelations: 45 rows
[2026-02-19 08:06:07] [INFO] [OUTPUT] SQL insert to ACM_SensorNormalized_TS: 12447 rows
[2026-02-19 08:06:09] [INFO] [OUTPUT] SQL insert to ACM_SeasonalPatterns: 13 rows
[2026-02-19 08:06:09] [INFO] [ANALYTICS] Generating analytics tables (v11 SQL-only)...
[2026-02-19 08:06:09] [INFO] [OUTPUT] Bulk pre-delete: 3 tables targeted, 3 DELETE statements in 0.03s (batched)
[2026-02-19 08:06:14] [INFO] [OUTPUT] SQL insert to ACM_HealthTimeline: 2765 rows
[2026-02-19 08:06:14] [INFO] [OUTPUT] Auto-flushing batch (rows=2798, age=22.1s)
[2026-02-19 08:06:17] [INFO] [OUTPUT] SQL insert to ACM_RegimeTimeline: 2765 rows
[2026-02-19 08:06:18] [INFO] [OUTPUT] Auto-flushing batch (rows=2765, age=3.5s)
[2026-02-19 08:06:19] [INFO] [OUTPUT] SQL insert to ACM_SensorDefects: 7 rows
[2026-02-19 08:06:22] [INFO] [OUTPUT] SQL insert to ACM_SensorHotspots: 9 rows
[2026-02-19 08:06:22] [INFO] [ANALYTICS] Generated analytics tables (SQL written: 4)
[2026-02-19 08:06:22] [INFO] [OUTPUTS] Analytics: tables=4
[2026-02-19 08:06:22] [INFO] [HealthTracker] Data anchor: 2024-07-21 09:00:00, window cutoff: 2024-04-22 09:00:00 (2160h lookback)
[2026-02-19 08:06:22] [INFO] [HealthTracker] Loaded 2765 health points from SQL (rolling window: 2160h)
[2026-02-19 08:06:23] [INFO] [FORECAST] Data summary: n_samples=2765, dt_hours=0.50, window=1742h
[2026-02-19 08:06:23] [INFO] [STATE] Loaded state: EquipID=1, StateVersion=1, DataVolume=722
[2026-02-19 08:06:23] [INFO] [FORECAST] Loaded forecast config: alpha=0.30, beta=0.10, failure_threshold=70.0, horizon=168h
[2026-02-19 08:06:25] [INFO] [DEGRADE] Restored state [global]: level=94.31, trend=0.0370/hr, std_error=0.83
[2026-02-19 08:06:25] [INFO] [DEGRADE] Restored state [regime-0]: level=94.31, trend=0.0370/hr, std_error=0.83
[2026-02-19 08:06:25] [INFO] [FORECAST] Warm-started degradation model from previous state
[2026-02-19 08:06:25] [INFO] [DEGRADE] Detected 23 outliers [global] (robust z > 3.0)
[2026-02-19 08:06:33] [INFO] [DEGRADE] Fitted [global]: level=54.83, trend=-0.0478/hr, std_error=1.80, n=2765
[2026-02-19 08:06:33] [INFO] [DEGRADE] Detected 23 outliers [regime-0] (robust z > 3.0)
[2026-02-19 08:06:51] [INFO] [DEGRADE] Adaptive smoothing [regime-0]: alpha=0.800, beta=0.080
[2026-02-19 08:06:59] [INFO] [DEGRADE] Fitted [regime-0]: level=54.83, trend=-0.1837/hr, std_error=1.79, n=2765
[2026-02-19 08:06:59] [INFO] [DEGRADE] Fitted regime-conditioned model with 1 regimes
[2026-02-19 08:06:59] [INFO] [FORECAST] RUL_P50=0.0h, RUL_Spread=0.0h, RUL_CV=nan, CI_Width=73.02, Health=54.5, N=2765, Quality=OK
[2026-02-19 08:06:59] [INFO] [SENSOR_ATTR] Loaded 9 sensor attributions from SQL
[2026-02-19 08:07:00] [INFO] [OUTPUT] Auto-flushing batch (rows=16, age=42.0s)
[2026-02-19 08:07:01] [INFO] [OUTPUT] SQL insert to ACM_HealthForecast: 168 rows
[2026-02-19 08:07:03] [INFO] [OUTPUT] SQL insert to ACM_FailureForecast: 168 rows
[2026-02-19 08:07:03] [WARN] [FORECAST] RUL reliability: NOT_RELIABLE - Model in COLDSTART state - no baseline established
[2026-02-19 08:07:06] [INFO] [OUTPUT] SQL insert to ACM_RUL: 1 rows
[2026-02-19 08:07:06] [INFO] [FORECAST] Wrote 3 forecast tables to SQL
[2026-02-19 08:07:07] [DEBUG] [FORECAST] Sensor forecast query: equip=1, cutoff=2024-06-21 09:00:00, sensors=['DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.06T31_1FD Fan Inlet Temperature', 'DEMO.SIM.06GP34_1FD Fan Outlet Pressure']...
[2026-02-19 08:07:07] [DEBUG] [FORECAST] Sensor forecast query returned 5409 rows
[2026-02-19 08:07:28] [INFO] [FORECAST] Generated 1512 sensor forecast points for 9 sensors over 168h
[2026-02-19 08:07:31] [INFO] [OUTPUT] SQL insert to ACM_SensorForecast: 1512 rows
[2026-02-19 08:07:31] [INFO] [FORECAST] Wrote sensor forecasts for 9 sensors
[2026-02-19 08:07:32] [INFO] [MultivariateForecast] Loaded 130 samples for 9 sensors
[2026-02-19 08:07:33] [INFO] [MV_FORECAST] Strong correlations: [('DEMO.SIM.FSAB_1FD Fan Right Inlet Flow', 'DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 1.3649565043784957), ('DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 1.3478734872109794), ('DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.FSAB_1FD Fan Right Inlet Flow', 1.2951161760789678)]
C:\Users\bhadk\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\statsmodels\tsa\base\tsa_model.py:473: ValueWarning: No frequency information was provided, so inferred frequency h will be used.
  self._init_dates(dates, freq)
[2026-02-19 08:07:38] [ERROR] [MultivariateForecast] VAR forecasting failed: maxlags is too large for the number of observations and the number of equations. The largest model cannot be estimated.
[2026-02-19 08:07:41] [INFO] [OUTPUT] Auto-flushing batch (rows=1849, age=41.7s)
[2026-02-19 08:07:44] [INFO] [OUTPUT] SQL insert to ACM_MultivariateForecast: 1512 rows
[2026-02-19 08:07:44] [INFO] [FORECAST] Multivariate (VAR) forecast complete: 9 sensors, method=CorrelatedEWM
[2026-02-19 08:07:44] [INFO] [FORECAST] Regime context: regime=0, omr_z=-2.429950475692749, drift_trend=unknown
[2026-02-19 08:07:44] [INFO] [STATE] Saved state for EquipID=1
[2026-02-19 08:07:44] [INFO] [FORECAST] Forecast: RUL P10/50/90=0/0/0h | tables=5 | top_sensors=DEMO.SIM.06I03_1FD Fan Motor Current (15.5%), DEMO.SIM.06T31_1FD Fan Inlet Temperature (13.8%), DEMO.SIM.06GP34_1FD Fan Outlet Pressure (12.9%)
[2026-02-19 08:07:44] [INFO] [OUTPUT] Batched transaction committed (117.64s)
[2026-02-19 08:07:45] [INFO] [OUTPUT] SQL insert to ACM_PCA_Models: 1 rows
[2026-02-19 08:07:47] [INFO] [OUTPUT] SQL insert to ACM_PCA_Loadings: 360 rows
[2026-02-19 08:07:47] [INFO] [OUTPUT] SQL insert to ACM_Run_Stats: 1 rows
[2026-02-19 08:07:54] [INFO] [CULPRITS] Wrote 228 culprit records to ACM_EpisodeCulprits
[2026-02-19 08:07:54] [DEBUG] [RUN_META] No data quality records found in SQL, defaulting to 100.0
[2026-02-19 08:07:54] [INFO] [RUN_META] Wrote run metadata to ACM_Runs: c4397e26-ecf5-4d32-b127-24f77dac7fcf
[2026-02-19 08:07:54] [INFO] [RUN] Finalized RunID=c4397e26-ecf5-4d32-b127-24f77dac7fcf outcome=OK rows_in=2765 rows_out=362
[2026-02-19 08:07:54] [DEBUG] [OUTPUT] OutputManager stats: 12 write_dataframe calls, 0 batch rows, 2.596s avg write time
[2026-02-19 08:07:54] [INFO] [PROFILE] Stopping and pushing profile data...
[2026-02-19 08:08:15] >>> --- Top CPU Functions ---
[2026-02-19 08:08:15] >>>    1. forecast_engine.ForecastEngine.run_forecast: 79718.8ms (1 calls)
[2026-02-19 08:08:15] >>>    2. forecast_engine.ForecastEngine._write_outputs: 42593.8ms (1 calls)
[2026-02-19 08:08:15] >>>    3. forecast_engine.ForecastEngine._fit_degradation_model: 33781.2ms (1 calls)
[2026-02-19 08:08:15] >>>    4. degradation_model.RegimeConditionedTrendModel.fit: 33375.0ms (1 calls)
[2026-02-19 08:08:15] >>>    5. degradation_model.LinearTrendModel.fit: 33187.5ms (2 calls)
[2026-02-19 08:08:15] >>>    6. output_manager.OutputManager.write_dataframe: 29437.5ms (13 calls)
[2026-02-19 08:08:15] >>>    7. output_manager.OutputManager._bulk_insert_sql: 27859.4ms (25 calls)
[2026-02-19 08:08:15] >>>    8. forecast_engine.ForecastEngine._generate_sensor_forecasts: 21031.2ms (1 calls)
[2026-02-19 08:08:15] >>>    9. indexing._iLocIndexer.__getitem__: 20578.1ms (6642 calls)
[2026-02-19 08:08:15] >>>   10. output_manager.OutputManager._prepare_dataframe_for_sql: 18375.0ms (22 calls)
[2026-02-19 08:08:17] [INFO] [PROFILE] Pushing cpu (2274 stacks) to Pyroscope...
[2026-02-19 08:08:17] [SUCCESS] [PROFILE] cpu profile pushed successfully
[2026-02-19 08:08:19] [INFO] [PROFILE] Pushing alloc_objects (500 stacks) to Pyroscope...
[2026-02-19 08:08:19] [SUCCESS] [PROFILE] alloc_objects profile pushed successfully
[2026-02-19 08:08:21] [INFO] [PROFILE] Pushing alloc_space (500 stacks) to Pyroscope...
[2026-02-19 08:08:21] [SUCCESS] [PROFILE] alloc_space profile pushed successfully
[2026-02-19 08:08:21] [SUCCESS] [PROFILE] Profile data pushed to Pyroscope

[2026-02-19 08:08:23] [INFO] [QA] Inspecting outputs for EquipID=1, RunID=C4397E26-ECF5-4D32-B127-24F77DAC7FCF (from ACM_Runs), window=[2026-02-19 02:34:38.371559,2026-02-19 02:37:54.660000)
[2026-02-19 08:08:23] [INFO] [QA] ACM_Scores_Wide: 2765 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_HealthTimeline: 2765 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_RegimeTimeline: 2765 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_EpisodeDiagnostics: 33 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_Episodes: 33 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_EpisodeMetrics: 0 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_SensorNormalized_TS: 12447 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_SensorCorrelations: 45 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_DetectorCorrelation: 9 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_SeasonalPatterns: 13 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_HealthForecast: 168 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_FailureForecast: 168 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_RUL: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_DriftController: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_RegimeDefinitions: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_RegimeOccupancy: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_Run_Stats: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_PCA_Models: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_PCA_Loadings: 360 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_PCA_Metrics: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_SensorHotspots: 9 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [INFO] [QA] ACM_SensorDefects: 7 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:08:23] [SUCCESS] [BATCH] FD_FAN: Batch 1 completed (outcome=OK)
[2026-02-19 08:08:23] [INFO] [BATCH]
FD_FAN: Batch 2/4 - [2024-07-21 09:24:00 to 2024-12-08 14:05:59]
[2026-02-19 08:08:23] [INFO] [RUN] C:\Users\bhadk\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe -m core.acm_main --equip FD_FAN --start-time 2024-07-21T09:24:00 --end-time 2024-12-08T14:05:59
[2026-02-19 08:08:23] [INFO] [BATCH] FD_FAN: Batch 2 - scoring with existing models
[2026-02-19 08:08:26] [SUCCESS] [OTEL] OTEL: loki=http://localhost:3100, profiling=http://localhost:4040, traces=http://localhost:4318, metrics=http://localhost:4318
[2026-02-19 08:08:26] [INFO] [PROFILE] Started CPU profiling
[2026-02-19 08:08:27] [INFO] [SQL] Connecting to SQL Server...
[2026-02-19 08:08:27] [SUCCESS] [SQL] SQL connection established
[2026-02-19 08:08:28] [INFO] [CONFIG] Config loaded from SQL for FD_FAN (EquipID=1, 265 params)
[2026-02-19 08:08:28] [INFO] [RUN] Run #3 | FD_FAN | adaptive | continuous_learning=True | force_retrain=False | intervals=model:1,thresh:1
[2026-02-19 08:08:28] [INFO] [RUN] Run started: FD_FAN (ID=1) | RunID=189ec893 | window=[2025-10-01 21:56:28.462210+00:00,2026-02-19 02:38:28.462210+00:00) | tick=201882m
[2026-02-19 08:08:28] [INFO] [RUN] CLI overrides: start=2024-07-21 09:24:00, end=2024-12-08 14:05:59
[2026-02-19 08:08:28] [INFO] [OUTPUT] Manager initialized (batch_size=5000, batching=ON, sql_cache=60.0s, io_workers=8, flush=1000 rows/30.0s, max_futures=50)
[2026-02-19 08:08:28] [INFO] [DATA] Loading from SQL historian: FD_FAN
[2026-02-19 08:08:28] [INFO] [DATA] Time range: 2024-07-21 09:24:00 to 2024-12-08 14:05:59
[2026-02-19 08:08:30] [INFO] [DATA] Retrieved 5576 rows from SQL historian
[2026-02-19 08:08:30] [INFO] [DATA] BATCH MODE: All 5576 rows allocated to scoring (baseline from cache)
[2026-02-19 08:08:31] [INFO] [DATA] BATCH MODE: Train empty (baseline_buffer later), using 9 score columns
[2026-02-19 08:08:31] [INFO] [DATA] Kept 9 numeric columns, dropped 0 non-numeric
[2026-02-19 08:08:31] [INFO] [DATA] Cadence: native=1800.0s, requested=auto, will_resample=False
[2026-02-19 08:08:31] [INFO] [DATA] SQL historian load complete: 0 train + 5576 score = 5576 total rows
[2026-02-19 08:08:32] [INFO] [OUTPUT] SQL insert to ACM_DataContractValidation: 1 rows
[2026-02-19 08:08:32] [INFO] [DATA] timestamp=EntryDateTime cadence_ok=True kept=9 drop=0 tz_stripped=0 future_drop=0 dup_removed=0
[2026-02-19 08:08:32] [INFO] [TIMER] data_split_complete  train_rows=0 train_cols=9 score_rows=5576 score_cols=9
[2026-02-19 08:08:32] [INFO] [BASELINE] Baseline: score split (train=2788, no overlap) | extended=False
[2026-02-19 08:08:38] [INFO] [SEASON] Seasonal: 11 patterns in 9 sensors | adjusted=True
[2026-02-19 08:08:42] [INFO] [OUTPUT] SQL insert to ACM_DataQuality: 1 rows
[2026-02-19 08:08:42] [INFO] [FEAT] Building features with window=16
[2026-02-19 08:08:42] [INFO] [FEAT] Computed 9 fill values from training data
[2026-02-19 08:08:48] [INFO] [FEAT] Features built: train=(2788, 72), score=(2788, 72)
[2026-02-19 08:08:55] [WARN] [MODEL] SQL refit request found: id=479 at 2026-02-19 08:05:43.144404
[2026-02-19 08:08:55] [INFO] [MODEL-LOAD] Loading cached models for equip=FD_FAN, equip_id=1
[2026-02-19 08:08:55] [INFO] [MODEL-SQL] Loading models from SQL ModelRegistry v1...
[2026-02-19 08:08:55] [INFO] [MODEL-SQL] - Loaded ar1_params (5,677 bytes)
[2026-02-19 08:08:55] [INFO] [MODEL-SQL] - Loaded calibration_params (600 bytes)
[2026-02-19 08:08:56] [INFO] [MODEL-SQL] - Loaded gmm_model (8,313 bytes)
[2026-02-19 08:09:04] [INFO] [MODEL-SQL] - Loaded iforest_model (3,123,017 bytes)
[2026-02-19 08:09:04] [INFO] [MODEL-SQL] - Loaded omr_model (243,009 bytes)
[2026-02-19 08:09:04] [INFO] [MODEL-SQL] - Loaded pca_model (4,511 bytes)
[2026-02-19 08:09:05] [INFO] [MODEL-SQL] - Loaded regime_model (285,971 bytes)
[2026-02-19 08:09:05] [INFO] [MODEL-SQL] [OK] Loaded 7/7 models from SQL ModelRegistry v1
[2026-02-19 08:09:05] [INFO] [MODEL] [OK] Loaded from SQL ModelRegistry successfully
[2026-02-19 08:09:05] [INFO] [MODEL-LOAD] Load result: models=True, manifest=True
[2026-02-19 08:09:05] [INFO] [MODEL] Using cached models v1: sensors=72 | sig=96c15b58c09d1cbb...
[2026-02-19 08:09:06] [INFO] [CAL] Loaded cached calibration params (6 detectors)
[2026-02-19 08:09:06] [INFO] [REGIME] Excluded 2 condition indicators from regime basis: ['DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06T33-1_1FD Fan Winding Temperature']
[2026-02-19 08:09:06] [INFO] [REGIME] Using 5 raw operational sensors for regime clustering: ['DEMO.SIM.06G31_1FD Fan Damper Position', 'DEMO.SIM.06GP34_1FD Fan Outlet Pressure', 'DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 'DEMO.SIM.FSAB_1FD Fan Right Inlet Flow']
[2026-02-19 08:09:07] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=2788
[2026-02-19 08:09:07] [INFO] [LIFECYCLE] Model maturity: LEARNING
[2026-02-19 08:09:15] [INFO] [REGIME] Assigned 2/2788 low-strength points to nearest cluster
[2026-02-19 08:09:23] [INFO] [REGIME] Identified 1722/2788 novel points (assigned to nearest cluster)
[2026-02-19 08:09:24] [INFO] [OUTPUT] SQL insert to ACM_RegimeDefinitions: 1 rows
[2026-02-19 08:09:24] [INFO] [REGIME] Wrote 1 regime definitions for audit
[2026-02-19 08:09:25] [INFO] [OUTPUT] SQL insert to ACM_RegimeOccupancy: 1 rows
[2026-02-19 08:09:25] [INFO] [REGIME] Regime analysis: occupancy=1 | transitions=0
[2026-02-19 08:09:26] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=2788
[2026-02-19 08:09:27] [INFO] [CAL] Using cached calibration for 6 detectors (training-anchored)
[2026-02-19 08:09:27] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=58.6s)
[2026-02-19 08:09:27] [INFO] [OUTPUT] SQL insert to ACM_CalibrationSummary: 6 rows
[2026-02-19 08:09:27] [INFO] [CAL] Calibration complete: q=0.98 | clip_z=20.00 | detectors=6 | thresholds=6 | per_regime=0 | summary=6
[2026-02-19 08:09:28] [INFO] [FUSE] CUSUM auto-tuned: k_sigma=2.000->0.800, h_sigma=12.000->3.000 (spread_ratio=5.19)
[2026-02-19 08:09:28] [WARN] [TUNE] gmm_z: all same sign - limited separability
[2026-02-19 08:09:28] [WARN] [TUNE] iforest_z: all same sign - limited separability
[2026-02-19 08:09:28] [WARN] [TUNE] pca_spe_z: all same sign - limited separability
[2026-02-19 08:09:28] [WARN] [TUNE] pca_t2_z: all same sign - limited separability
[2026-02-19 08:09:28] [WARN] [TUNE] Excessive weight drift for gmm_z: 0.050 -> 0.086 (drift=72.2% > 20.0%). Rejecting tune.
[2026-02-19 08:09:28] [INFO] [OUTPUT] SQL insert to ACM_RunMetrics: 18 rows
[2026-02-19 08:09:29] [INFO] [FUSE] Fusion: detectors=6 | episodes=9 | auto_tuned=True
[2026-02-19 08:09:30] [INFO] [TRANSIENT] Using 40 operating-variable columns for transient detection; excluded 32 condition-indicator columns
[2026-02-19 08:09:31] [INFO] [TRANSIENT] State distribution: {'trip': 2652, 'shutdown': 136}
[2026-02-19 08:09:31] [INFO] [REGIME] Regime: quality_ok=False | states={'unknown': 2788} | transient={'trip': 2652, 'shutdown': 136}
[2026-02-19 08:09:31] [INFO] [CONFIG_HIST] Logged 1 config changes for RunID=189ec893-331e-47a6-8e5b-f30e2d2958a9
[2026-02-19 08:09:31] [INFO] [AUTO-TUNE] Auto-tune: 1 adjustments (k_max: 6->8) | refit=next_run
[2026-02-19 08:09:31] [INFO] [OUTPUT] SQL insert to ACM_RefitRequests: 1 rows
[2026-02-19 08:09:32] [DEBUG] [CAL] Extreme threshold (5086.36) - clamping to 1000.0
[2026-02-19 08:09:32] [INFO] [DRIFT] Drift: cusum_z P95=2.180 | trend=0.0007 | fused=-0.884 | mode=FAULT
[2026-02-19 08:09:33] [INFO] [OUTPUT] SQL insert to ACM_DriftController: 1 rows
[2026-02-19 08:09:34] [INFO] [BASELINE] Skipping buffer write (models exist, next refresh in 7 batches)
[2026-02-19 08:09:39] [INFO] [OUTPUT] SQL insert to ACM_Scores_Wide: 2788 rows
[2026-02-19 08:09:39] [INFO] [IO] Scores written: {'sql_written': True, 'rows': 2788, 'inserted': 2788, 'error': None, 'sql_table': 'ACM_Scores_Wide', 'artifact': 'scores'} rows
[2026-02-19 08:09:40] [INFO] [EPISODES] Applied 5 schema repairs to episodes: peak_timestamp_fallback_used, regime_mapped_fallback, dominant_sensor_extracted, severity_calculated, status_defaulted
[2026-02-19 08:09:40] [INFO] [OUTPUT] Auto-flushing batch (rows=2794, age=12.9s)
[2026-02-19 08:09:42] [INFO] [OUTPUT] SQL insert to ACM_EpisodeDiagnostics: 9 rows
[2026-02-19 08:09:43] [INFO] [OUTPUT] SQL insert to ACM_Episodes: 9 rows
[2026-02-19 08:09:43] [INFO] [IO] Episodes written: {'sql_written': True, 'rows': 9, 'inserted': 9, 'error': None, 'sql_table': 'ACM_EpisodeDiagnostics', 'artifact': 'episodes'} rows
[2026-02-19 08:09:44] [INFO] [OUTPUT] SQL insert to ACM_DetectorCorrelation: 9 rows
[2026-02-19 08:09:45] [INFO] [OUTPUT] SQL insert to ACM_SensorCorrelations: 45 rows
[2026-02-19 08:09:55] [INFO] [OUTPUT] SQL insert to ACM_SensorNormalized_TS: 12546 rows
[2026-02-19 08:09:56] [INFO] [OUTPUT] SQL insert to ACM_SeasonalPatterns: 11 rows
[2026-02-19 08:09:56] [INFO] [ANALYTICS] Generating analytics tables (v11 SQL-only)...
[2026-02-19 08:09:56] [INFO] [OUTPUT] Bulk pre-delete: 3 tables targeted, 3 DELETE statements in 0.03s (batched)
[2026-02-19 08:10:01] [INFO] [OUTPUT] SQL insert to ACM_HealthTimeline: 2788 rows
[2026-02-19 08:10:01] [INFO] [OUTPUT] Auto-flushing batch (rows=2797, age=21.7s)
[2026-02-19 08:10:04] [INFO] [OUTPUT] SQL insert to ACM_RegimeTimeline: 2788 rows
[2026-02-19 08:10:05] [INFO] [OUTPUT] Auto-flushing batch (rows=2788, age=3.2s)
[2026-02-19 08:10:06] [INFO] [OUTPUT] SQL insert to ACM_SensorDefects: 7 rows
[2026-02-19 08:10:08] [INFO] [OUTPUT] SQL insert to ACM_SensorHotspots: 9 rows
[2026-02-19 08:10:09] [INFO] [ANALYTICS] Generated analytics tables (SQL written: 4)
[2026-02-19 08:10:09] [INFO] [OUTPUTS] Analytics: tables=4
[2026-02-19 08:10:09] [INFO] [HealthTracker] Data anchor: 2024-12-08 14:00:00, window cutoff: 2024-09-09 14:00:00 (2160h lookback)
[2026-02-19 08:10:09] [INFO] [HealthTracker] Loaded 2788 health points from SQL (rolling window: 2160h)
[2026-02-19 08:10:10] [INFO] [FORECAST] Data summary: n_samples=2788, dt_hours=0.50, window=1730h
[2026-02-19 08:10:10] [INFO] [STATE] Loaded state: EquipID=1, StateVersion=1, DataVolume=3487
[2026-02-19 08:10:10] [INFO] [FORECAST] Loaded forecast config: alpha=0.30, beta=0.10, failure_threshold=70.0, horizon=168h
[2026-02-19 08:10:12] [INFO] [DEGRADE] Restored state [global]: level=54.83, trend=-0.0478/hr, std_error=1.80
[2026-02-19 08:10:12] [INFO] [DEGRADE] Restored state [regime-0]: level=54.83, trend=-0.1837/hr, std_error=1.79
[2026-02-19 08:10:12] [INFO] [FORECAST] Warm-started degradation model from previous state
[2026-02-19 08:10:12] [INFO] [DEGRADE] Detected 1 outliers [global] (robust z > 3.0)
[2026-02-19 08:10:20] [INFO] [DEGRADE] Fitted [global]: level=59.56, trend=-0.0565/hr, std_error=0.94, n=2788
[2026-02-19 08:10:21] [INFO] [DEGRADE] Detected 1 outliers [regime-0] (robust z > 3.0)
[2026-02-19 08:10:39] [INFO] [DEGRADE] Adaptive smoothing [regime-0]: alpha=0.800, beta=0.200
[2026-02-19 08:10:47] [INFO] [DEGRADE] Fitted [regime-0]: level=59.46, trend=-0.5675/hr, std_error=0.93, n=2788
[2026-02-19 08:10:47] [INFO] [DEGRADE] Fitted regime-conditioned model with 1 regimes
[2026-02-19 08:10:47] [INFO] [FORECAST] RUL_P50=0.0h, RUL_Spread=0.0h, RUL_CV=nan, CI_Width=66.56, Health=59.3, N=2788, Quality=OK
[2026-02-19 08:10:47] [INFO] [SENSOR_ATTR] Loaded 9 sensor attributions from SQL
[2026-02-19 08:10:47] [INFO] [OUTPUT] Auto-flushing batch (rows=16, age=42.8s)
[2026-02-19 08:10:49] [INFO] [OUTPUT] SQL insert to ACM_HealthForecast: 168 rows
[2026-02-19 08:10:51] [INFO] [OUTPUT] SQL insert to ACM_FailureForecast: 168 rows
[2026-02-19 08:10:51] [WARN] [FORECAST] RUL reliability: NOT_RELIABLE - Model in COLDSTART state - no baseline established
[2026-02-19 08:10:53] [INFO] [OUTPUT] SQL insert to ACM_RUL: 1 rows
[2026-02-19 08:10:53] [INFO] [FORECAST] Wrote 3 forecast tables to SQL
[2026-02-19 08:10:54] [DEBUG] [FORECAST] Sensor forecast query: equip=1, cutoff=2024-11-08 13:30:00, sensors=['DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.06T33-1_1FD Fan Winding Temperature']...
[2026-02-19 08:10:55] [DEBUG] [FORECAST] Sensor forecast query returned 4968 rows
[2026-02-19 08:11:14] [INFO] [FORECAST] Generated 1512 sensor forecast points for 9 sensors over 168h
[2026-02-19 08:11:17] [INFO] [OUTPUT] SQL insert to ACM_SensorForecast: 1512 rows
[2026-02-19 08:11:17] [INFO] [FORECAST] Wrote sensor forecasts for 9 sensors
[2026-02-19 08:11:18] [INFO] [MultivariateForecast] Loaded 168 samples for 9 sensors
[2026-02-19 08:11:19] [INFO] [MV_FORECAST] Strong correlations: [('DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06I03_1FD Fan Motor Current', 7.106263776986033), ('DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.06T33-1_1FD Fan Winding Temperature', 3.81854269884269), ('DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06T33-1_1FD Fan Winding Temperature', 3.548194959777697)]
C:\Users\bhadk\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\statsmodels\tsa\base\tsa_model.py:473: ValueWarning: A date index has been provided, but it has no associated frequency information and so will be ignored when e.g. forecasting.
  self._init_dates(dates, freq)
[2026-02-19 08:11:26] [INFO] [MultivariateForecast] VAR(12) fitted with AIC=1.71
[2026-02-19 08:11:42] [INFO] [OUTPUT] Auto-flushing batch (rows=1849, age=55.0s)
[2026-02-19 08:11:45] [INFO] [OUTPUT] SQL insert to ACM_MultivariateForecast: 1512 rows
[2026-02-19 08:11:45] [INFO] [FORECAST] Multivariate (VAR) forecast complete: 9 sensors, method=VAR(12)
[2026-02-19 08:11:45] [INFO] [FORECAST] Regime context: regime=0, omr_z=-2.322613477706909, drift_trend=unknown
[2026-02-19 08:11:45] [INFO] [STATE] Saved state for EquipID=1
[2026-02-19 08:11:45] [INFO] [FORECAST] Forecast: RUL P10/50/90=0/0/0h | tables=5 | top_sensors=DEMO.SIM.06T32-1_1FD Fan Bearing Temperature (38.3%), DEMO.SIM.06I03_1FD Fan Motor Current (16.1%), DEMO.SIM.06T33-1_1FD Fan Winding Temperature (8.0%)
[2026-02-19 08:11:45] [INFO] [OUTPUT] Batched transaction committed (130.85s)
[2026-02-19 08:11:46] [INFO] [OUTPUT] SQL insert to ACM_PCA_Models: 1 rows
[2026-02-19 08:11:48] [INFO] [OUTPUT] SQL insert to ACM_PCA_Loadings: 360 rows
[2026-02-19 08:11:48] [INFO] [OUTPUT] SQL insert to ACM_Run_Stats: 1 rows
[2026-02-19 08:11:50] [INFO] [CULPRITS] Wrote 62 culprit records to ACM_EpisodeCulprits
[2026-02-19 08:11:51] [DEBUG] [RUN_META] No data quality records found in SQL, defaulting to 100.0
[2026-02-19 08:11:51] [INFO] [RUN_META] Wrote run metadata to ACM_Runs: 189ec893-331e-47a6-8e5b-f30e2d2958a9
[2026-02-19 08:11:51] [INFO] [RUN] Finalized RunID=189ec893-331e-47a6-8e5b-f30e2d2958a9 outcome=OK rows_in=2788 rows_out=362
[2026-02-19 08:11:51] [DEBUG] [OUTPUT] OutputManager stats: 12 write_dataframe calls, 0 batch rows, 2.543s avg write time
[2026-02-19 08:11:51] [INFO] [PROFILE] Stopping and pushing profile data...
[2026-02-19 08:12:10] >>> --- Top CPU Functions ---
[2026-02-19 08:12:10] >>>    1. forecast_engine.ForecastEngine.run_forecast: 94265.6ms (1 calls)
[2026-02-19 08:12:10] >>>    2. forecast_engine.ForecastEngine._write_outputs: 56359.4ms (1 calls)
[2026-02-19 08:12:10] >>>    3. forecast_engine.ForecastEngine._fit_degradation_model: 34421.9ms (1 calls)
[2026-02-19 08:12:10] >>>    4. degradation_model.RegimeConditionedTrendModel.fit: 34015.6ms (1 calls)
[2026-02-19 08:12:10] >>>    5. degradation_model.LinearTrendModel.fit: 33812.5ms (2 calls)
[2026-02-19 08:12:10] >>>    6. indexing._iLocIndexer.__getitem__: 32656.2ms (11038 calls)
[2026-02-19 08:12:10] >>>    7. output_manager.OutputManager.write_dataframe: 29218.8ms (13 calls)
[2026-02-19 08:12:10] >>>    8. output_manager.OutputManager._bulk_insert_sql: 27500.0ms (25 calls)
[2026-02-19 08:12:10] >>>    9. multivariate_forecast.MultivariateSensorForecaster.forecast: 24312.5ms (1 calls)
[2026-02-19 08:12:10] >>>   10. multivariate_forecast.MultivariateSensorForecaster.forecast_var: 22625.0ms (1 calls)
[2026-02-19 08:12:12] [INFO] [PROFILE] Pushing cpu (2297 stacks) to Pyroscope...
[2026-02-19 08:12:12] [SUCCESS] [PROFILE] cpu profile pushed successfully
[2026-02-19 08:12:14] [INFO] [PROFILE] Pushing alloc_objects (500 stacks) to Pyroscope...
[2026-02-19 08:12:14] [SUCCESS] [PROFILE] alloc_objects profile pushed successfully
[2026-02-19 08:12:15] [INFO] [PROFILE] Pushing alloc_space (500 stacks) to Pyroscope...
[2026-02-19 08:12:15] [SUCCESS] [PROFILE] alloc_space profile pushed successfully
[2026-02-19 08:12:15] [SUCCESS] [PROFILE] Profile data pushed to Pyroscope

[2026-02-19 08:12:17] [INFO] [QA] Inspecting outputs for EquipID=1, RunID=189EC893-331E-47A6-8E5B-F30E2D2958A9 (from ACM_Runs), window=[2026-02-19 02:38:28.465360,2026-02-19 02:41:51.260000)
[2026-02-19 08:12:17] [INFO] [QA] ACM_Scores_Wide: 2788 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:17] [INFO] [QA] ACM_HealthTimeline: 2788 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:17] [INFO] [QA] ACM_RegimeTimeline: 2788 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:17] [INFO] [QA] ACM_EpisodeDiagnostics: 9 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_Episodes: 9 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_EpisodeMetrics: 0 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_SensorNormalized_TS: 12546 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_SensorCorrelations: 45 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_DetectorCorrelation: 9 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_SeasonalPatterns: 11 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_HealthForecast: 168 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_FailureForecast: 168 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_RUL: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_DriftController: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_RegimeDefinitions: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_RegimeOccupancy: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_Run_Stats: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_PCA_Models: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_PCA_Loadings: 360 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_PCA_Metrics: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_SensorHotspots: 9 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [INFO] [QA] ACM_SensorDefects: 7 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:12:18] [SUCCESS] [BATCH] FD_FAN: Batch 2 completed (outcome=OK)
[2026-02-19 08:12:18] [INFO] [BATCH]
FD_FAN: Batch 3/4 - [2024-12-08 14:06:00 to 2025-04-27 18:47:59]
[2026-02-19 08:12:18] [INFO] [RUN] C:\Users\bhadk\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe -m core.acm_main --equip FD_FAN --start-time 2024-12-08T14:06:00 --end-time 2025-04-27T18:47:59
[2026-02-19 08:12:18] [INFO] [BATCH] FD_FAN: Batch 3 - scoring with existing models
[2026-02-19 08:12:21] [SUCCESS] [OTEL] OTEL: loki=http://localhost:3100, profiling=http://localhost:4040, traces=http://localhost:4318, metrics=http://localhost:4318
[2026-02-19 08:12:21] [INFO] [PROFILE] Started CPU profiling
[2026-02-19 08:12:22] [INFO] [SQL] Connecting to SQL Server...
[2026-02-19 08:12:22] [SUCCESS] [SQL] SQL connection established
[2026-02-19 08:12:22] [INFO] [CONFIG] Config loaded from SQL for FD_FAN (EquipID=1, 265 params)
[2026-02-19 08:12:22] [INFO] [RUN] Run #4 | FD_FAN | adaptive | continuous_learning=True | force_retrain=False | intervals=model:1,thresh:1
[2026-02-19 08:12:22] [INFO] [RUN] Run started: FD_FAN (ID=1) | RunID=b0742e08 | window=[2025-10-01 22:00:22.757159+00:00,2026-02-19 02:42:22.757159+00:00) | tick=201882m
[2026-02-19 08:12:22] [INFO] [RUN] CLI overrides: start=2024-12-08 14:06:00, end=2025-04-27 18:47:59
[2026-02-19 08:12:22] [INFO] [OUTPUT] Manager initialized (batch_size=5000, batching=ON, sql_cache=60.0s, io_workers=8, flush=1000 rows/30.0s, max_futures=50)
[2026-02-19 08:12:22] [INFO] [DATA] Loading from SQL historian: FD_FAN
[2026-02-19 08:12:22] [INFO] [DATA] Time range: 2024-12-08 14:06:00 to 2025-04-27 18:47:59
[2026-02-19 08:12:23] [INFO] [DATA] Retrieved 3396 rows from SQL historian
[2026-02-19 08:12:23] [INFO] [DATA] BATCH MODE: All 3396 rows allocated to scoring (baseline from cache)
[2026-02-19 08:12:24] [INFO] [DATA] BATCH MODE: Train empty (baseline_buffer later), using 9 score columns
[2026-02-19 08:12:24] [INFO] [DATA] Kept 9 numeric columns, dropped 0 non-numeric
[2026-02-19 08:12:24] [INFO] [DATA] Cadence: native=1800.0s, requested=auto, will_resample=False
[2026-02-19 08:12:24] [INFO] [DATA] SQL historian load complete: 0 train + 3396 score = 3396 total rows
[2026-02-19 08:12:26] [INFO] [OUTPUT] SQL insert to ACM_DataContractValidation: 1 rows
[2026-02-19 08:12:26] [INFO] [DATA] timestamp=EntryDateTime cadence_ok=True kept=9 drop=0 tz_stripped=0 future_drop=0 dup_removed=0
[2026-02-19 08:12:26] [INFO] [TIMER] data_split_complete  train_rows=0 train_cols=9 score_rows=3396 score_cols=9
[2026-02-19 08:12:26] [INFO] [BASELINE] Baseline: score split (train=1698, no overlap) | extended=False
[2026-02-19 08:12:32] [INFO] [SEASON] Seasonal: 9 patterns in 8 sensors | adjusted=True
[2026-02-19 08:12:35] [INFO] [OUTPUT] SQL insert to ACM_DataQuality: 1 rows
[2026-02-19 08:12:35] [INFO] [FEAT] Building features with window=16
[2026-02-19 08:12:35] [INFO] [FEAT] Computed 9 fill values from training data
[2026-02-19 08:12:41] [INFO] [FEAT] Features built: train=(1698, 72), score=(1698, 72)
[2026-02-19 08:12:47] [WARN] [MODEL] SQL refit request found: id=480 at 2026-02-19 08:09:31.305962
[2026-02-19 08:12:47] [INFO] [MODEL-LOAD] Loading cached models for equip=FD_FAN, equip_id=1
[2026-02-19 08:12:47] [INFO] [MODEL-SQL] Loading models from SQL ModelRegistry v1...
[2026-02-19 08:12:47] [INFO] [MODEL-SQL] - Loaded ar1_params (5,677 bytes)
[2026-02-19 08:12:47] [INFO] [MODEL-SQL] - Loaded calibration_params (600 bytes)
[2026-02-19 08:12:47] [INFO] [MODEL-SQL] - Loaded gmm_model (8,313 bytes)
[2026-02-19 08:12:56] [INFO] [MODEL-SQL] - Loaded iforest_model (3,123,017 bytes)
[2026-02-19 08:12:56] [INFO] [MODEL-SQL] - Loaded omr_model (243,009 bytes)
[2026-02-19 08:12:56] [INFO] [MODEL-SQL] - Loaded pca_model (4,511 bytes)
[2026-02-19 08:12:57] [INFO] [MODEL-SQL] - Loaded regime_model (285,971 bytes)
[2026-02-19 08:12:57] [INFO] [MODEL-SQL] [OK] Loaded 7/7 models from SQL ModelRegistry v1
[2026-02-19 08:12:57] [INFO] [MODEL] [OK] Loaded from SQL ModelRegistry successfully
[2026-02-19 08:12:57] [INFO] [MODEL-LOAD] Load result: models=True, manifest=True
[2026-02-19 08:12:57] [INFO] [MODEL] Using cached models v1: sensors=72 | sig=96c15b58c09d1cbb...
[2026-02-19 08:12:58] [INFO] [CAL] Loaded cached calibration params (6 detectors)
[2026-02-19 08:12:58] [INFO] [REGIME] Excluded 2 condition indicators from regime basis: ['DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06T33-1_1FD Fan Winding Temperature']
[2026-02-19 08:12:58] [INFO] [REGIME] Using 5 raw operational sensors for regime clustering: ['DEMO.SIM.06G31_1FD Fan Damper Position', 'DEMO.SIM.06GP34_1FD Fan Outlet Pressure', 'DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 'DEMO.SIM.FSAB_1FD Fan Right Inlet Flow']
[2026-02-19 08:12:59] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=1698
[2026-02-19 08:12:59] [INFO] [LIFECYCLE] Model maturity: LEARNING
[2026-02-19 08:13:04] [INFO] [REGIME] Assigned 50/1698 low-strength points to nearest cluster
[2026-02-19 08:13:09] [INFO] [REGIME] Identified 172/1698 novel points (assigned to nearest cluster)
[2026-02-19 08:13:10] [INFO] [OUTPUT] SQL insert to ACM_RegimeDefinitions: 1 rows
[2026-02-19 08:13:10] [INFO] [REGIME] Wrote 1 regime definitions for audit
[2026-02-19 08:13:11] [INFO] [OUTPUT] SQL insert to ACM_RegimeOccupancy: 1 rows
[2026-02-19 08:13:11] [INFO] [REGIME] Regime analysis: occupancy=1 | transitions=0
[2026-02-19 08:13:12] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=1698
[2026-02-19 08:13:12] [INFO] [CAL] Using cached calibration for 6 detectors (training-anchored)
[2026-02-19 08:13:12] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=49.9s)
[2026-02-19 08:13:13] [INFO] [OUTPUT] SQL insert to ACM_CalibrationSummary: 6 rows
[2026-02-19 08:13:13] [INFO] [CAL] Calibration complete: q=0.98 | clip_z=37.57 | detectors=6 | thresholds=6 | per_regime=0 | summary=6
[2026-02-19 08:13:13] [INFO] [FUSE] CUSUM auto-tuned: k_sigma=2.000->0.800, h_sigma=12.000->3.000 (spread_ratio=3.64)
[2026-02-19 08:13:13] [WARN] [TUNE] gmm_z: all same sign - limited separability
[2026-02-19 08:13:13] [WARN] [TUNE] iforest_z: all same sign - limited separability
[2026-02-19 08:13:13] [WARN] [TUNE] pca_spe_z: all same sign - limited separability
[2026-02-19 08:13:13] [WARN] [TUNE] pca_t2_z: all same sign - limited separability
[2026-02-19 08:13:13] [WARN] [TUNE] Excessive weight drift for gmm_z: 0.050 -> 0.086 (drift=72.2% > 20.0%). Rejecting tune.
[2026-02-19 08:13:14] [INFO] [OUTPUT] SQL insert to ACM_RunMetrics: 18 rows
[2026-02-19 08:13:15] [INFO] [FUSE] Fusion: detectors=6 | episodes=15 | auto_tuned=True
[2026-02-19 08:13:16] [INFO] [TRANSIENT] Using 40 operating-variable columns for transient detection; excluded 32 condition-indicator columns
[2026-02-19 08:13:17] [INFO] [TRANSIENT] State distribution: {'trip': 1697, 'shutdown': 1}
[2026-02-19 08:13:17] [INFO] [REGIME] Regime: quality_ok=False | states={'unknown': 1698} | transient={'trip': 1697, 'shutdown': 1}
[2026-02-19 08:13:17] [INFO] [CONFIG_HIST] Logged 1 config changes for RunID=b0742e08-0318-41a7-88f0-946a74df921e
[2026-02-19 08:13:17] [INFO] [AUTO-TUNE] Auto-tune: 1 adjustments (k_max: 6->8) | refit=next_run
[2026-02-19 08:13:17] [INFO] [OUTPUT] SQL insert to ACM_RefitRequests: 1 rows
[2026-02-19 08:13:18] [DEBUG] [CAL] Extreme threshold (1288.82) - clamping to 1000.0
[2026-02-19 08:13:18] [INFO] [DRIFT] Drift: cusum_z P95=2.029 | trend=-0.0001 | fused=0.058 | mode=FAULT
[2026-02-19 08:13:18] [INFO] [OUTPUT] SQL insert to ACM_DriftController: 1 rows
[2026-02-19 08:13:20] [INFO] [BASELINE] Skipping buffer write (models exist, next refresh in 6 batches)
[2026-02-19 08:13:25] [INFO] [OUTPUT] SQL insert to ACM_Scores_Wide: 1698 rows
[2026-02-19 08:13:25] [INFO] [IO] Scores written: {'sql_written': True, 'rows': 1698, 'inserted': 1698, 'error': None, 'sql_table': 'ACM_Scores_Wide', 'artifact': 'scores'} rows
[2026-02-19 08:13:25] [INFO] [EPISODES] Applied 5 schema repairs to episodes: peak_timestamp_fallback_used, regime_mapped_fallback, dominant_sensor_extracted, severity_calculated, status_defaulted
[2026-02-19 08:13:25] [INFO] [OUTPUT] Auto-flushing batch (rows=1704, age=12.9s)
[2026-02-19 08:13:27] [INFO] [OUTPUT] SQL insert to ACM_EpisodeDiagnostics: 15 rows
[2026-02-19 08:13:28] [INFO] [OUTPUT] SQL insert to ACM_Episodes: 15 rows
[2026-02-19 08:13:28] [INFO] [IO] Episodes written: {'sql_written': True, 'rows': 15, 'inserted': 15, 'error': None, 'sql_table': 'ACM_EpisodeDiagnostics', 'artifact': 'episodes'} rows
[2026-02-19 08:13:29] [INFO] [OUTPUT] SQL insert to ACM_DetectorCorrelation: 9 rows
[2026-02-19 08:13:30] [INFO] [OUTPUT] SQL insert to ACM_SensorCorrelations: 45 rows
[2026-02-19 08:13:41] [INFO] [OUTPUT] SQL insert to ACM_SensorNormalized_TS: 15282 rows
[2026-02-19 08:13:43] [INFO] [OUTPUT] SQL insert to ACM_SeasonalPatterns: 9 rows
[2026-02-19 08:13:43] [INFO] [ANALYTICS] Generating analytics tables (v11 SQL-only)...
[2026-02-19 08:13:43] [INFO] [OUTPUT] Bulk pre-delete: 3 tables targeted, 3 DELETE statements in 0.03s (batched)
[2026-02-19 08:13:47] [INFO] [OUTPUT] SQL insert to ACM_HealthTimeline: 1698 rows
[2026-02-19 08:13:47] [INFO] [OUTPUT] Auto-flushing batch (rows=1713, age=21.9s)
[2026-02-19 08:13:49] [INFO] [OUTPUT] SQL insert to ACM_RegimeTimeline: 1698 rows
[2026-02-19 08:13:50] [INFO] [OUTPUT] Auto-flushing batch (rows=1698, age=2.5s)
[2026-02-19 08:13:51] [INFO] [OUTPUT] SQL insert to ACM_SensorDefects: 7 rows
[2026-02-19 08:13:53] [INFO] [OUTPUT] SQL insert to ACM_SensorHotspots: 9 rows
[2026-02-19 08:13:53] [INFO] [ANALYTICS] Generated analytics tables (SQL written: 4)
[2026-02-19 08:13:54] [INFO] [OUTPUTS] Analytics: tables=4
[2026-02-19 08:13:54] [INFO] [HealthTracker] Data anchor: 2025-04-14 23:30:00, window cutoff: 2025-01-14 23:30:00 (2160h lookback)
[2026-02-19 08:13:54] [INFO] [HealthTracker] Loaded 1698 health points from SQL (rolling window: 2160h)
[2026-02-19 08:13:55] [INFO] [FORECAST] Data summary: n_samples=1698, dt_hours=0.50, window=1872h
[2026-02-19 08:13:55] [INFO] [STATE] Loaded state: EquipID=1, StateVersion=1, DataVolume=6275
[2026-02-19 08:13:55] [INFO] [FORECAST] Loaded forecast config: alpha=0.30, beta=0.10, failure_threshold=70.0, horizon=168h
[2026-02-19 08:13:56] [INFO] [DEGRADE] Restored state [global]: level=59.56, trend=-0.0565/hr, std_error=0.94
[2026-02-19 08:13:56] [INFO] [DEGRADE] Restored state [regime-0]: level=59.46, trend=-0.5675/hr, std_error=0.93
[2026-02-19 08:13:56] [INFO] [FORECAST] Warm-started degradation model from previous state
[2026-02-19 08:14:01] [INFO] [DEGRADE] Fitted [global]: level=77.71, trend=0.0499/hr, std_error=1.89, n=1698
[2026-02-19 08:14:12] [INFO] [DEGRADE] Adaptive smoothing [regime-0]: alpha=0.800, beta=0.080
[2026-02-19 08:14:17] [INFO] [DEGRADE] Fitted [regime-0]: level=77.93, trend=0.8432/hr, std_error=1.85, n=1698
[2026-02-19 08:14:17] [INFO] [DEGRADE] Fitted regime-conditioned model with 1 regimes
[2026-02-19 08:14:17] [INFO] [RUL] RUL estimate: P50=168.0h, P10=163.0h, P90=173.0h, mean=164.8h, std=22.7h, failure_prob=0.020
[2026-02-19 08:14:17] [INFO] [FORECAST] RUL_P50=168.0h, RUL_Spread=10.0h, RUL_CV=0.14, CI_Width=9.61, Health=77.6, N=1698, Quality=OK
[2026-02-19 08:14:18] [INFO] [SENSOR_ATTR] Loaded 9 sensor attributions from SQL
[2026-02-19 08:14:20] [INFO] [OUTPUT] SQL insert to ACM_HealthForecast: 168 rows
[2026-02-19 08:14:20] [INFO] [OUTPUT] Auto-flushing batch (rows=184, age=30.1s)
[2026-02-19 08:14:21] [INFO] [OUTPUT] SQL insert to ACM_FailureForecast: 168 rows
[2026-02-19 08:14:21] [WARN] [FORECAST] RUL reliability: NOT_RELIABLE - Model in COLDSTART state - no baseline established
[2026-02-19 08:14:24] [INFO] [OUTPUT] SQL insert to ACM_RUL: 1 rows
[2026-02-19 08:14:24] [INFO] [FORECAST] Wrote 3 forecast tables to SQL
[2026-02-19 08:14:25] [DEBUG] [FORECAST] Sensor forecast query: equip=1, cutoff=2025-03-15 23:30:00, sensors=['DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.06T33-1_1FD Fan Winding Temperature']...
[2026-02-19 08:14:25] [DEBUG] [FORECAST] Sensor forecast query returned 2169 rows
[2026-02-19 08:14:52] [INFO] [FORECAST] Generated 1512 sensor forecast points for 9 sensors over 168h
[2026-02-19 08:14:52] [INFO] [OUTPUT] Auto-flushing batch (rows=169, age=32.8s)
[2026-02-19 08:14:56] [INFO] [OUTPUT] SQL insert to ACM_SensorForecast: 1512 rows
[2026-02-19 08:14:56] [INFO] [FORECAST] Wrote sensor forecasts for 9 sensors
[2026-02-19 08:14:57] [INFO] [MultivariateForecast] Loaded 240 samples for 9 sensors
[2026-02-19 08:14:58] [INFO] [MV_FORECAST] Strong correlations: [('DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06I03_1FD Fan Motor Current', 21.095790908535182), ('DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06T33-1_1FD Fan Winding Temperature', 20.820415245957193), ('DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 11.29492463969929)]
C:\Users\bhadk\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\statsmodels\tsa\base\tsa_model.py:473: ValueWarning: No frequency information was provided, so inferred frequency 30min will be used.
  self._init_dates(dates, freq)
[2026-02-19 08:15:05] [INFO] [MultivariateForecast] VAR(1) fitted with AIC=6.10
[2026-02-19 08:15:20] [INFO] [OUTPUT] Auto-flushing batch (rows=1512, age=28.0s)
[2026-02-19 08:15:23] [INFO] [OUTPUT] SQL insert to ACM_MultivariateForecast: 1512 rows
[2026-02-19 08:15:23] [INFO] [FORECAST] Multivariate (VAR) forecast complete: 9 sensors, method=VAR(1)
[2026-02-19 08:15:23] [INFO] [FORECAST] Regime context: regime=0, omr_z=-1.6111726760864258, drift_trend=unknown
[2026-02-19 08:15:23] [INFO] [STATE] Saved state for EquipID=1
[2026-02-19 08:15:23] [INFO] [FORECAST] Forecast: RUL P10/50/90=163/168/173h | tables=5 | top_sensors=DEMO.SIM.06T32-1_1FD Fan Bearing Temperature (50.6%), DEMO.SIM.06I03_1FD Fan Motor Current (8.8%), DEMO.SIM.06T33-1_1FD Fan Winding Temperature (8.2%)
[2026-02-19 08:15:23] [INFO] [OUTPUT] Batched transaction committed (122.37s)
[2026-02-19 08:15:25] [INFO] [OUTPUT] SQL insert to ACM_PCA_Models: 1 rows
[2026-02-19 08:15:26] [INFO] [OUTPUT] SQL insert to ACM_PCA_Loadings: 360 rows
[2026-02-19 08:15:27] [INFO] [OUTPUT] SQL insert to ACM_Run_Stats: 1 rows
[2026-02-19 08:15:29] [INFO] [CULPRITS] Wrote 102 culprit records to ACM_EpisodeCulprits
[2026-02-19 08:15:30] [DEBUG] [RUN_META] No data quality records found in SQL, defaulting to 100.0
[2026-02-19 08:15:30] [INFO] [RUN_META] Wrote run metadata to ACM_Runs: b0742e08-0318-41a7-88f0-946a74df921e
[2026-02-19 08:15:30] [INFO] [RUN] Finalized RunID=b0742e08-0318-41a7-88f0-946a74df921e outcome=OK rows_in=1698 rows_out=362
[2026-02-19 08:15:30] [DEBUG] [OUTPUT] OutputManager stats: 12 write_dataframe calls, 0 batch rows, 2.278s avg write time
[2026-02-19 08:15:30] [INFO] [PROFILE] Stopping and pushing profile data...
[2026-02-19 08:15:49] >>> --- Top CPU Functions ---
[2026-02-19 08:15:49] >>>    1. forecast_engine.ForecastEngine.run_forecast: 87218.8ms (1 calls)
[2026-02-19 08:15:49] >>>    2. forecast_engine.ForecastEngine._write_outputs: 63375.0ms (1 calls)
[2026-02-19 08:15:49] >>>    3. indexing._iLocIndexer.__getitem__: 29562.5ms (8868 calls)
[2026-02-19 08:15:49] >>>    4. forecast_engine.ForecastEngine._generate_sensor_forecasts: 27750.0ms (1 calls)
[2026-02-19 08:15:49] >>>    5. output_manager.OutputManager._bulk_insert_sql: 26500.0ms (25 calls)
[2026-02-19 08:15:49] >>>    6. output_manager.OutputManager.write_dataframe: 26078.1ms (13 calls)
[2026-02-19 08:15:49] >>>    7. multivariate_forecast.MultivariateSensorForecaster.forecast: 23890.6ms (1 calls)
[2026-02-19 08:15:49] >>>    8. multivariate_forecast.MultivariateSensorForecaster.forecast_var: 21890.6ms (1 calls)
[2026-02-19 08:15:49] >>>    9. forecast_engine.ForecastEngine._fit_degradation_model: 20625.0ms (1 calls)
[2026-02-19 08:15:49] >>>   10. degradation_model.RegimeConditionedTrendModel.fit: 20312.5ms (1 calls)
[2026-02-19 08:15:51] [INFO] [PROFILE] Pushing cpu (2281 stacks) to Pyroscope...
[2026-02-19 08:15:51] [SUCCESS] [PROFILE] cpu profile pushed successfully
[2026-02-19 08:15:53] [INFO] [PROFILE] Pushing alloc_objects (500 stacks) to Pyroscope...
[2026-02-19 08:15:53] [SUCCESS] [PROFILE] alloc_objects profile pushed successfully
[2026-02-19 08:15:54] [INFO] [PROFILE] Pushing alloc_space (500 stacks) to Pyroscope...
[2026-02-19 08:15:54] [SUCCESS] [PROFILE] alloc_space profile pushed successfully
[2026-02-19 08:15:54] [SUCCESS] [PROFILE] Profile data pushed to Pyroscope

[2026-02-19 08:15:57] [INFO] [QA] Inspecting outputs for EquipID=1, RunID=B0742E08-0318-41A7-88F0-946A74DF921E (from ACM_Runs), window=[2026-02-19 02:42:22.767220,2026-02-19 02:45:30.393333)
[2026-02-19 08:15:57] [INFO] [QA] ACM_Scores_Wide: 1698 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_HealthTimeline: 1698 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_RegimeTimeline: 1698 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_EpisodeDiagnostics: 15 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_Episodes: 15 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_EpisodeMetrics: 0 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_SensorNormalized_TS: 15282 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_SensorCorrelations: 45 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_DetectorCorrelation: 9 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_SeasonalPatterns: 9 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_HealthForecast: 168 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_FailureForecast: 168 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_RUL: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_DriftController: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_RegimeDefinitions: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_RegimeOccupancy: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_Run_Stats: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_PCA_Models: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_PCA_Loadings: 360 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_PCA_Metrics: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_SensorHotspots: 9 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [INFO] [QA] ACM_SensorDefects: 7 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:15:57] [SUCCESS] [BATCH] FD_FAN: Batch 3 completed (outcome=OK)
[2026-02-19 08:15:57] [INFO] [BATCH]
FD_FAN: Batch 4/4 - [2025-04-27 18:48:00 to 2025-09-14 23:29:59]
[2026-02-19 08:15:57] [INFO] [RUN] C:\Users\bhadk\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe -m core.acm_main --equip FD_FAN --start-time 2025-04-27T18:48:00 --end-time 2025-09-14T23:29:59
[2026-02-19 08:15:57] [INFO] [BATCH] FD_FAN: Batch 4 - scoring with existing models
[2026-02-19 08:16:00] [SUCCESS] [OTEL] OTEL: loki=http://localhost:3100, profiling=http://localhost:4040, traces=http://localhost:4318, metrics=http://localhost:4318
[2026-02-19 08:16:00] [INFO] [PROFILE] Started CPU profiling
[2026-02-19 08:16:01] [INFO] [SQL] Connecting to SQL Server...
[2026-02-19 08:16:01] [SUCCESS] [SQL] SQL connection established
[2026-02-19 08:16:01] [INFO] [CONFIG] Config loaded from SQL for FD_FAN (EquipID=1, 265 params)
[2026-02-19 08:16:01] [INFO] [RUN] Run #5 | FD_FAN | adaptive | continuous_learning=True | force_retrain=False | intervals=model:1,thresh:1
[2026-02-19 08:16:01] [INFO] [RUN] Run started: FD_FAN (ID=1) | RunID=4bb22202 | window=[2025-10-01 22:04:01.862301+00:00,2026-02-19 02:46:01.862301+00:00) | tick=201882m
[2026-02-19 08:16:01] [INFO] [RUN] CLI overrides: start=2025-04-27 18:48:00, end=2025-09-14 23:29:59
[2026-02-19 08:16:01] [INFO] [OUTPUT] Manager initialized (batch_size=5000, batching=ON, sql_cache=60.0s, io_workers=8, flush=1000 rows/30.0s, max_futures=50)
[2026-02-19 08:16:01] [INFO] [DATA] Loading from SQL historian: FD_FAN
[2026-02-19 08:16:02] [INFO] [DATA] Time range: 2025-04-27 18:48:00 to 2025-09-14 23:29:59
[2026-02-19 08:16:02] [INFO] [DATA] Retrieved 1193 rows from SQL historian
[2026-02-19 08:16:02] [INFO] [DATA] BATCH MODE: All 1193 rows allocated to scoring (baseline from cache)
[2026-02-19 08:16:02] [INFO] [DATA] BATCH MODE: Train empty (baseline_buffer later), using 9 score columns
[2026-02-19 08:16:02] [INFO] [DATA] Kept 9 numeric columns, dropped 0 non-numeric
[2026-02-19 08:16:03] [INFO] [DATA] Cadence: native=1800.0s, requested=auto, will_resample=False
[2026-02-19 08:16:03] [INFO] [DATA] SQL historian load complete: 0 train + 1193 score = 1193 total rows
[2026-02-19 08:16:04] [INFO] [OUTPUT] SQL insert to ACM_DataContractValidation: 1 rows
[2026-02-19 08:16:04] [INFO] [DATA] timestamp=EntryDateTime cadence_ok=True kept=9 drop=0 tz_stripped=0 future_drop=0 dup_removed=0
[2026-02-19 08:16:04] [INFO] [TIMER] data_split_complete  train_rows=0 train_cols=9 score_rows=1193 score_cols=9
[2026-02-19 08:16:04] [INFO] [BASELINE] Baseline: score split (train=596, no overlap) | extended=False
[2026-02-19 08:16:10] [INFO] [SEASON] Seasonal: 7 patterns in 6 sensors | adjusted=True
[2026-02-19 08:16:13] [INFO] [OUTPUT] SQL insert to ACM_DataQuality: 1 rows
[2026-02-19 08:16:13] [INFO] [FEAT] Building features with window=16
[2026-02-19 08:16:14] [INFO] [FEAT] Computed 9 fill values from training data
[2026-02-19 08:16:19] [INFO] [FEAT] Features built: train=(596, 72), score=(597, 72)
[2026-02-19 08:16:24] [WARN] [MODEL] SQL refit request found: id=481 at 2026-02-19 08:13:17.389448
[2026-02-19 08:16:24] [INFO] [MODEL-LOAD] Loading cached models for equip=FD_FAN, equip_id=1
[2026-02-19 08:16:24] [INFO] [MODEL-SQL] Loading models from SQL ModelRegistry v1...
[2026-02-19 08:16:25] [INFO] [MODEL-SQL] - Loaded ar1_params (5,677 bytes)
[2026-02-19 08:16:25] [INFO] [MODEL-SQL] - Loaded calibration_params (600 bytes)
[2026-02-19 08:16:25] [INFO] [MODEL-SQL] - Loaded gmm_model (8,313 bytes)
[2026-02-19 08:16:34] [INFO] [MODEL-SQL] - Loaded iforest_model (3,123,017 bytes)
[2026-02-19 08:16:34] [INFO] [MODEL-SQL] - Loaded omr_model (243,009 bytes)
[2026-02-19 08:16:34] [INFO] [MODEL-SQL] - Loaded pca_model (4,511 bytes)
[2026-02-19 08:16:34] [INFO] [MODEL-SQL] - Loaded regime_model (285,971 bytes)
[2026-02-19 08:16:35] [INFO] [MODEL-SQL] [OK] Loaded 7/7 models from SQL ModelRegistry v1
[2026-02-19 08:16:35] [INFO] [MODEL] [OK] Loaded from SQL ModelRegistry successfully
[2026-02-19 08:16:35] [INFO] [MODEL-LOAD] Load result: models=True, manifest=True
[2026-02-19 08:16:35] [INFO] [MODEL] Using cached models v1: sensors=72 | sig=96c15b58c09d1cbb...
[2026-02-19 08:16:35] [INFO] [CAL] Loaded cached calibration params (6 detectors)
[2026-02-19 08:16:35] [INFO] [REGIME] Excluded 2 condition indicators from regime basis: ['DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06T33-1_1FD Fan Winding Temperature']
[2026-02-19 08:16:35] [INFO] [REGIME] Using 5 raw operational sensors for regime clustering: ['DEMO.SIM.06G31_1FD Fan Damper Position', 'DEMO.SIM.06GP34_1FD Fan Outlet Pressure', 'DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 'DEMO.SIM.FSAB_1FD Fan Right Inlet Flow']
[2026-02-19 08:16:36] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=597
[2026-02-19 08:16:36] [INFO] [LIFECYCLE] Model maturity: LEARNING
[2026-02-19 08:16:40] [INFO] [REGIME] Identified 12/597 novel points (assigned to nearest cluster)
[2026-02-19 08:16:41] [INFO] [OUTPUT] SQL insert to ACM_RegimeDefinitions: 1 rows
[2026-02-19 08:16:41] [INFO] [REGIME] Wrote 1 regime definitions for audit
[2026-02-19 08:16:42] [INFO] [OUTPUT] SQL insert to ACM_RegimeOccupancy: 1 rows
[2026-02-19 08:16:42] [INFO] [REGIME] Regime analysis: occupancy=1 | transitions=0
[2026-02-19 08:16:43] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=596
[2026-02-19 08:16:43] [INFO] [CAL] Using cached calibration for 6 detectors (training-anchored)
[2026-02-19 08:16:43] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=41.8s)
[2026-02-19 08:16:44] [INFO] [OUTPUT] SQL insert to ACM_CalibrationSummary: 6 rows
[2026-02-19 08:16:44] [INFO] [CAL] Calibration complete: q=0.98 | clip_z=50.00 | detectors=6 | thresholds=6 | per_regime=0 | summary=6
[2026-02-19 08:16:44] [INFO] [FUSE] CUSUM auto-tuned: k_sigma=2.000->0.800, h_sigma=12.000->3.000 (spread_ratio=5.19)
[2026-02-19 08:16:44] [WARN] [TUNE] gmm_z: all same sign - limited separability
[2026-02-19 08:16:44] [WARN] [TUNE] iforest_z: all same sign - limited separability
[2026-02-19 08:16:44] [WARN] [TUNE] pca_spe_z: all same sign - limited separability
[2026-02-19 08:16:44] [WARN] [TUNE] pca_t2_z: all same sign - limited separability
[2026-02-19 08:16:44] [WARN] [TUNE] Excessive weight drift for gmm_z: 0.050 -> 0.086 (drift=72.2% > 20.0%). Rejecting tune.
[2026-02-19 08:16:45] [INFO] [OUTPUT] SQL insert to ACM_RunMetrics: 18 rows
[2026-02-19 08:16:46] [INFO] [FUSE] Fusion: detectors=6 | episodes=6 | auto_tuned=True
[2026-02-19 08:16:46] [INFO] [TRANSIENT] Using 40 operating-variable columns for transient detection; excluded 32 condition-indicator columns
[2026-02-19 08:16:47] [INFO] [TRANSIENT] State distribution: {'trip': 597}
[2026-02-19 08:16:47] [INFO] [REGIME] Regime: quality_ok=False | states={'unknown': 597} | transient={'trip': 597}
[2026-02-19 08:16:47] [INFO] [CONFIG_HIST] Logged 1 config changes for RunID=4bb22202-2bb6-48a4-a37c-1bfb350e9d3a
[2026-02-19 08:16:47] [INFO] [AUTO-TUNE] Auto-tune: 1 adjustments (k_max: 6->8) | refit=next_run
[2026-02-19 08:16:47] [INFO] [OUTPUT] SQL insert to ACM_RefitRequests: 1 rows
[2026-02-19 08:16:48] [INFO] [DRIFT] Drift: cusum_z P95=0.812 | trend=-0.0028 | fused=0.058 | mode=FAULT
[2026-02-19 08:16:48] [INFO] [OUTPUT] SQL insert to ACM_DriftController: 1 rows
[2026-02-19 08:16:49] [INFO] [BASELINE] Skipping buffer write (models exist, next refresh in 5 batches)
[2026-02-19 08:16:53] [INFO] [OUTPUT] SQL insert to ACM_Scores_Wide: 597 rows
[2026-02-19 08:16:53] [INFO] [IO] Scores written: {'sql_written': True, 'rows': 597, 'inserted': 597, 'error': None, 'sql_table': 'ACM_Scores_Wide', 'artifact': 'scores'} rows
[2026-02-19 08:16:54] [INFO] [EPISODES] Applied 5 schema repairs to episodes: peak_timestamp_fallback_used, regime_mapped_fallback, dominant_sensor_extracted, severity_calculated, status_defaulted
[2026-02-19 08:16:56] [INFO] [OUTPUT] SQL insert to ACM_EpisodeDiagnostics: 6 rows
[2026-02-19 08:16:56] [INFO] [OUTPUT] SQL insert to ACM_Episodes: 6 rows
[2026-02-19 08:16:57] [INFO] [IO] Episodes written: {'sql_written': True, 'rows': 6, 'inserted': 6, 'error': None, 'sql_table': 'ACM_EpisodeDiagnostics', 'artifact': 'episodes'} rows
[2026-02-19 08:16:57] [INFO] [OUTPUT] SQL insert to ACM_DetectorCorrelation: 9 rows
[2026-02-19 08:16:59] [INFO] [OUTPUT] SQL insert to ACM_SensorCorrelations: 45 rows
[2026-02-19 08:17:04] [INFO] [OUTPUT] SQL insert to ACM_SensorNormalized_TS: 5373 rows
[2026-02-19 08:17:05] [INFO] [OUTPUT] SQL insert to ACM_SeasonalPatterns: 7 rows
[2026-02-19 08:17:05] [INFO] [ANALYTICS] Generating analytics tables (v11 SQL-only)...
[2026-02-19 08:17:06] [INFO] [OUTPUT] Bulk pre-delete: 3 tables targeted, 3 DELETE statements in 0.02s (batched)
[2026-02-19 08:17:08] [INFO] [OUTPUT] SQL insert to ACM_HealthTimeline: 597 rows
[2026-02-19 08:17:08] [INFO] [OUTPUT] Auto-flushing batch (rows=1206, age=24.8s)
[2026-02-19 08:17:10] [INFO] [OUTPUT] SQL insert to ACM_RegimeTimeline: 597 rows
[2026-02-19 08:17:11] [INFO] [OUTPUT] SQL insert to ACM_SensorDefects: 7 rows
[2026-02-19 08:17:14] [INFO] [OUTPUT] SQL insert to ACM_SensorHotspots: 9 rows
[2026-02-19 08:17:14] [INFO] [ANALYTICS] Generated analytics tables (SQL written: 4)
[2026-02-19 08:17:14] [INFO] [OUTPUTS] Analytics: tables=4
[2026-02-19 08:17:14] [INFO] [HealthTracker] Data anchor: 2025-09-14 23:00:00, window cutoff: 2025-06-16 23:00:00 (2160h lookback)
[2026-02-19 08:17:14] [INFO] [HealthTracker] Loaded 597 health points from SQL (rolling window: 2160h)
[2026-02-19 08:17:15] [INFO] [FORECAST] Data summary: n_samples=597, dt_hours=0.50, window=1522h
[2026-02-19 08:17:15] [INFO] [STATE] Loaded state: EquipID=1, StateVersion=1, DataVolume=7973
[2026-02-19 08:17:15] [INFO] [FORECAST] Loaded forecast config: alpha=0.30, beta=0.10, failure_threshold=70.0, horizon=168h
[2026-02-19 08:17:15] [INFO] [DEGRADE] Restored state [global]: level=77.71, trend=0.0499/hr, std_error=1.89
[2026-02-19 08:17:15] [INFO] [DEGRADE] Restored state [regime-0]: level=77.93, trend=0.8432/hr, std_error=1.85
[2026-02-19 08:17:15] [INFO] [FORECAST] Warm-started degradation model from previous state
[2026-02-19 08:17:17] [INFO] [DEGRADE] Fitted [global]: level=70.03, trend=0.0018/hr, std_error=2.08, n=597
[2026-02-19 08:17:21] [INFO] [DEGRADE] Adaptive smoothing [regime-0]: alpha=0.800, beta=0.080
[2026-02-19 08:17:23] [INFO] [DEGRADE] Fitted [regime-0]: level=70.13, trend=0.2212/hr, std_error=1.96, n=597
[2026-02-19 08:17:23] [INFO] [DEGRADE] Fitted regime-conditioned model with 1 regimes
[2026-02-19 08:17:23] [INFO] [FORECAST] RUL_P50=0.0h, RUL_Spread=0.0h, RUL_CV=nan, CI_Width=66.05, Health=69.5, N=597, Quality=OK
[2026-02-19 08:17:24] [INFO] [SENSOR_ATTR] Loaded 9 sensor attributions from SQL
[2026-02-19 08:17:25] [INFO] [OUTPUT] SQL insert to ACM_HealthForecast: 168 rows
[2026-02-19 08:17:27] [INFO] [OUTPUT] SQL insert to ACM_FailureForecast: 168 rows
[2026-02-19 08:17:27] [WARN] [FORECAST] RUL reliability: NOT_RELIABLE - Model in COLDSTART state - no baseline established
[2026-02-19 08:17:30] [INFO] [OUTPUT] SQL insert to ACM_RUL: 1 rows
[2026-02-19 08:17:30] [INFO] [FORECAST] Wrote 3 forecast tables to SQL
[2026-02-19 08:17:31] [DEBUG] [FORECAST] Sensor forecast query: equip=1, cutoff=2025-08-15 23:00:00, sensors=['DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06I03_1FD Fan Motor Current', 'DEMO.SIM.06T33-1_1FD Fan Winding Temperature']...
[2026-02-19 08:17:31] [DEBUG] [FORECAST] Sensor forecast query returned 2169 rows
[2026-02-19 08:17:58] [INFO] [FORECAST] Generated 1512 sensor forecast points for 9 sensors over 168h
[2026-02-19 08:17:58] [INFO] [OUTPUT] Auto-flushing batch (rows=950, age=49.6s)
[2026-02-19 08:18:01] [INFO] [OUTPUT] SQL insert to ACM_SensorForecast: 1512 rows
[2026-02-19 08:18:01] [INFO] [FORECAST] Wrote sensor forecasts for 9 sensors
[2026-02-19 08:18:02] [INFO] [MultivariateForecast] Loaded 239 samples for 9 sensors
[2026-02-19 08:18:03] [INFO] [MV_FORECAST] Strong correlations: [('DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06I03_1FD Fan Motor Current', 36.989636045185264), ('DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.FSAA_1FD Fan Left Inlet Flow', 16.94305360716604), ('DEMO.SIM.06T32-1_1FD Fan Bearing Temperature', 'DEMO.SIM.06T31_1FD Fan Inlet Temperature', 16.43219061587583)]
C:\Users\bhadk\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\statsmodels\tsa\base\tsa_model.py:473: ValueWarning: No frequency information was provided, so inferred frequency 30min will be used.
  self._init_dates(dates, freq)
[2026-02-19 08:18:09] [INFO] [MultivariateForecast] VAR(2) fitted with AIC=6.77
[2026-02-19 08:18:25] [INFO] [OUTPUT] Auto-flushing batch (rows=1512, age=27.8s)
[2026-02-19 08:18:28] [INFO] [OUTPUT] SQL insert to ACM_MultivariateForecast: 1512 rows
[2026-02-19 08:18:28] [INFO] [FORECAST] Multivariate (VAR) forecast complete: 9 sensors, method=VAR(2)
[2026-02-19 08:18:28] [INFO] [FORECAST] Regime context: regime=0, omr_z=-1.994093656539917, drift_trend=unknown
[2026-02-19 08:18:28] [INFO] [STATE] Saved state for EquipID=1
[2026-02-19 08:18:28] [INFO] [FORECAST] Forecast: RUL P10/50/90=0/0/0h | tables=5 | top_sensors=DEMO.SIM.06T32-1_1FD Fan Bearing Temperature (26.9%), DEMO.SIM.06I03_1FD Fan Motor Current (18.1%), DEMO.SIM.06T33-1_1FD Fan Winding Temperature (11.2%)
[2026-02-19 08:18:28] [INFO] [OUTPUT] Batched transaction committed (97.49s)
[2026-02-19 08:18:29] [INFO] [OUTPUT] SQL insert to ACM_PCA_Models: 1 rows
[2026-02-19 08:18:31] [INFO] [OUTPUT] SQL insert to ACM_PCA_Loadings: 360 rows
[2026-02-19 08:18:31] [INFO] [OUTPUT] SQL insert to ACM_Run_Stats: 1 rows
[2026-02-19 08:18:33] [INFO] [CULPRITS] Wrote 40 culprit records to ACM_EpisodeCulprits
[2026-02-19 08:18:33] [DEBUG] [RUN_META] No data quality records found in SQL, defaulting to 100.0
[2026-02-19 08:18:33] [INFO] [RUN_META] Wrote run metadata to ACM_Runs: 4bb22202-2bb6-48a4-a37c-1bfb350e9d3a
[2026-02-19 08:18:33] [INFO] [RUN] Finalized RunID=4bb22202-2bb6-48a4-a37c-1bfb350e9d3a outcome=OK rows_in=597 rows_out=362
[2026-02-19 08:18:33] [DEBUG] [OUTPUT] OutputManager stats: 12 write_dataframe calls, 0 batch rows, 2.042s avg write time
[2026-02-19 08:18:33] [INFO] [PROFILE] Stopping and pushing profile data...
[2026-02-19 08:18:51] >>> --- Top CPU Functions ---
[2026-02-19 08:18:51] >>>    1. forecast_engine.ForecastEngine.run_forecast: 72500.0ms (1 calls)
[2026-02-19 08:18:51] >>>    2. forecast_engine.ForecastEngine._write_outputs: 62890.6ms (1 calls)
[2026-02-19 08:18:51] >>>    3. forecast_engine.ForecastEngine._generate_sensor_forecasts: 27343.8ms (1 calls)
[2026-02-19 08:18:51] >>>    4. indexing._iLocIndexer.__getitem__: 25125.0ms (6647 calls)
[2026-02-19 08:18:51] >>>    5. multivariate_forecast.MultivariateSensorForecaster.forecast: 23937.5ms (1 calls)
[2026-02-19 08:18:51] >>>    6. output_manager.OutputManager.write_dataframe: 23343.8ms (13 calls)
[2026-02-19 08:18:51] >>>    7. multivariate_forecast.MultivariateSensorForecaster.forecast_var: 22078.1ms (1 calls)
[2026-02-19 08:18:51] >>>    8. output_manager.OutputManager._bulk_insert_sql: 20125.0ms (25 calls)
[2026-02-19 08:18:51] >>>    9. _decorators.wrapper: 16640.6ms (72 calls)
[2026-02-19 08:18:51] >>>   10. model.ExponentialSmoothing._predict: 16406.2ms (18 calls)
[2026-02-19 08:18:53] [INFO] [PROFILE] Pushing cpu (2266 stacks) to Pyroscope...
[2026-02-19 08:18:53] [SUCCESS] [PROFILE] cpu profile pushed successfully
[2026-02-19 08:18:55] [INFO] [PROFILE] Pushing alloc_objects (500 stacks) to Pyroscope...
[2026-02-19 08:18:55] [SUCCESS] [PROFILE] alloc_objects profile pushed successfully
[2026-02-19 08:18:56] [INFO] [PROFILE] Pushing alloc_space (500 stacks) to Pyroscope...
[2026-02-19 08:18:56] [SUCCESS] [PROFILE] alloc_space profile pushed successfully
[2026-02-19 08:18:56] [SUCCESS] [PROFILE] Profile data pushed to Pyroscope

[2026-02-19 08:18:59] [INFO] [QA] Inspecting outputs for EquipID=1, RunID=4BB22202-2BB6-48A4-A37C-1BFB350E9D3A (from ACM_Runs), window=[2026-02-19 02:46:01.862301,2026-02-19 02:48:33.613333)
[2026-02-19 08:18:59] [INFO] [QA] ACM_Scores_Wide: 597 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_HealthTimeline: 597 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_RegimeTimeline: 597 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_EpisodeDiagnostics: 6 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_Episodes: 6 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_EpisodeMetrics: 0 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_SensorNormalized_TS: 5373 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_SensorCorrelations: 45 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_DetectorCorrelation: 9 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_SeasonalPatterns: 7 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_HealthForecast: 168 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_FailureForecast: 168 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_RUL: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_DriftController: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_RegimeDefinitions: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_RegimeOccupancy: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_Run_Stats: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_PCA_Models: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_PCA_Loadings: 360 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_PCA_Metrics: 1 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_SensorHotspots: 9 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [INFO] [QA] ACM_SensorDefects: 7 row(s) for EquipID=1 (RunID scoped)
[2026-02-19 08:18:59] [SUCCESS] [BATCH] FD_FAN: Batch 4 completed (outcome=OK)
[2026-02-19 08:18:59] [INFO] [BATCH]
FD_FAN: Processed 4 batch(es)
[2026-02-19 08:18:59] [SUCCESS] [BATCH] FD_FAN: Completed - 4 batch(es) processed
[2026-02-19 08:18:59] [INFO] [TIMING] FD_FAN: Total time = 18m 34s
[2026-02-19 08:18:59] >>>
============================================================
[2026-02-19 08:18:59] [INFO] [TIMING] Overall execution time: 18m 34s
[2026-02-19 08:18:59] >>> ============================================================
[2026-02-19 08:18:59] [INFO] [PROFILE] Stopping and pushing profile data...
[2026-02-19 08:18:59] >>> --- Top CPU Functions ---
[2026-02-19 08:18:59] >>>    1. sql_batch_runner.SQLBatchRunner.process_equipment: 2125.0ms (1 calls)
[2026-02-19 08:18:59] >>>    2. sql_batch_runner.SQLBatchRunner._run_acm_batch: 1921.9ms (5 calls)
[2026-02-19 08:18:59] >>>    3. sql_batch_runner.SQLBatchRunner._process_batches: 1484.4ms (1 calls)
[2026-02-19 08:18:59] >>>    4. sql_batch_runner.SQLBatchRunner._process_coldstart: 562.5ms (1 calls)
[2026-02-19 08:18:59] >>>    5. ansitowin32.AnsiToWin32.write: 406.2ms (2084 calls)
[2026-02-19 08:18:59] >>>    6. ansitowin32.StreamWrapper.write: 406.2ms (2084 calls)
[2026-02-19 08:18:59] >>>    7. threading.Event.wait: 187.5ms (331 calls)
[2026-02-19 08:18:59] >>>    8. threading.Condition.wait: 187.5ms (331 calls)
[2026-02-19 08:18:59] >>>    9. sql_batch_runner.SQLBatchRunner._inspect_last_run_outputs: 171.9ms (5 calls)
[2026-02-19 08:18:59] >>>   10. observability._render_console: 140.6ms (168 calls)
[2026-02-19 08:18:59] [INFO] [PROFILE] Pushing cpu (60 stacks) to Pyroscope...
[2026-02-19 08:18:59] [SUCCESS] [PROFILE] cpu profile pushed successfully
[2026-02-19 08:19:00] [INFO] [PROFILE] Pushing alloc_objects (500 stacks) to Pyroscope...
[2026-02-19 08:19:00] [SUCCESS] [PROFILE] alloc_objects profile pushed successfully
[2026-02-19 08:19:01] [INFO] [PROFILE] Pushing alloc_space (500 stacks) to Pyroscope...
[2026-02-19 08:19:01] [SUCCESS] [PROFILE] alloc_space profile pushed successfully
[2026-02-19 08:19:01] [SUCCESS] [PROFILE] Profile data pushed to Pyroscope
[2026-02-19 08:19:03] [SUCCESS] [MAIN] BATCH RUNNER COMPLETED SUCCESSFULLY
[2026-02-19 08:19:03] >>> ============================================================
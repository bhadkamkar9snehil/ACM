  ⚡bhadk ❯❯ python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 --start-from-beginning --max-batches 5
[2026-02-18 16:18:27] [SUCCESS] [OTEL] Loki logs -> http://localhost:3100
[2026-02-18 16:18:27] [SUCCESS] [OTEL] Profiling -> http://localhost:4040 [cpu (yappi), memory (tracemalloc)]
[2026-02-18 16:18:27] [SUCCESS] [OTEL] Traces -> http://localhost:4318/v1/traces
[2026-02-18 16:18:27] [SUCCESS] [OTEL] Metrics -> http://localhost:4318/v1/metrics
[2026-02-18 16:18:27] [INFO] [PROFILE] Started CPU profiling
[2026-02-18 16:18:27] >>> ============================================================
[2026-02-18 16:18:27] >>> SQL BATCH RUNNER - Continuous ACM Processing
[2026-02-18 16:18:27] >>> ============================================================
[2026-02-18 16:18:27] [INFO] [MAIN] Equipment: WFA_TURBINE_10
[2026-02-18 16:18:27] [INFO] [MAIN] SQL Server: localhost\B19CL3PCQLSERVER/ACM
[2026-02-18 16:18:27] [INFO] [MAIN] Tick Window: 30 minutes
[2026-02-18 16:18:27] [INFO] [MAIN] Max Workers: 1
[2026-02-18 16:18:27] [INFO] [MAIN] Resume: False
[2026-02-18 16:18:27] [INFO] [MAIN] Dry Run: False
[2026-02-18 16:18:27] [INFO] [MAIN] Pipeline Mode: adaptive
[2026-02-18 16:18:27] >>> ============================================================
[2026-02-18 16:18:27] >>> ############################################################
[2026-02-18 16:18:27] >>> Processing Equipment: WFA_TURBINE_10
[2026-02-18 16:18:27] >>> ############################################################
[2026-02-18 16:18:27] [INFO] [SQL] Connection test OK
[2026-02-18 16:18:27] [INFO] [PRECHECK] WFA_TURBINE_10: Resolved EquipID=5010
[2026-02-18 16:18:27] [INFO] [RESET] Starting from beginning for WFA_TURBINE_10 - performing full reset
[2026-02-18 16:18:27] [INFO] [CONFIG] Inferred tick_minutes=1440 for WFA_TURBINE_10 (rows=53592, minutes=538560.0, cadence=10.05m) [clamped to max=1440]
[2026-02-18 16:18:29] [SUCCESS] [RESET] Cold-start reset: cleared 36 tables (194,846 rows) for EquipID=5010 [top: ACM_SensorNormalized_TS=50,706, ACM_HealthTimeline=26,797, ACM_RegimeTimeline=26,797, ACM_Scores_Wide=26,797, ACM_PCA_Loadings=25,270]
[2026-02-18 16:18:30] [SUCCESS] [RESET] Cold-start reset: deleted 34 cached models for EquipID=5010
[2026-02-18 16:18:30] [INFO] [RESET] Cleared ACM_Runs and Coldstart for EquipID=5010
[2026-02-18 16:18:30] [INFO] [CONFIG] WFA_TURBINE_10: Adjusted tick_minutes 1440 -> 107712 for max-batches=5
[2026-02-18 16:18:30] [INFO] [PRECHECK] WFA_TURBINE_10: Historian coverage OK - range=[2022-10-09 08:40:00,2023-10-18 08:40:00], rows=53592
[2026-02-18 16:18:30] >>> ============================================================
[2026-02-18 16:18:30] >>> [COLDSTART] Starting coldstart for WFA_TURBINE_10
[2026-02-18 16:18:30] >>> ============================================================
[2026-02-18 16:18:30] [INFO] [COLDSTART] WFA_TURBINE_10: Historical data range: 2022-10-09 08:40:00 to 2023-10-18 08:40:00
[2026-02-18 16:18:30] >>> --------------------------------------------------
[2026-02-18 16:18:30] >>> [COLDSTART] WFA_TURBINE_10: Attempt 1/10
[2026-02-18 16:18:30] >>> --------------------------------------------------
[2026-02-18 16:18:30] [INFO] [COLDSTART] WFA_TURBINE_10: Checking coldstart status in SQL (ModelRegistry/ACM_ColdstartState)...
[2026-02-18 16:18:30] [INFO] [COLDSTART] WFA_TURBINE_10: No ACM_ColdstartState row; using default minimum rows=500
[2026-02-18 16:18:30] [INFO] [COLDSTART] WFA_TURBINE_10: Status - 0/500 rows accumulated
[2026-02-18 16:18:30] [INFO] [COLDSTART] WFA_TURBINE_10: Processing window [2022-10-09 08:40:00 to 2022-12-23 03:51:59)
[2026-02-18 16:18:30] [INFO] [RUN] C:\Users\bhadk\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe -m core.acm_main --equip WFA_TURBINE_10 --start-time 2022-10-09T08:40:00 --end-time 2022-12-23T03:51:59
[2026-02-18 16:18:30] [INFO] [BATCH] WFA_TURBINE_10: Coldstart batch - training fresh models
[2026-02-18 16:18:35] [SUCCESS] [OTEL] Loki logs -> http://localhost:3100
[2026-02-18 16:18:35] [SUCCESS] [OTEL] Profiling -> http://localhost:4040 [cpu (yappi), memory (tracemalloc)]
[2026-02-18 16:18:35] [SUCCESS] [OTEL] Traces -> http://localhost:4318/v1/traces
[2026-02-18 16:18:35] [SUCCESS] [OTEL] Metrics -> http://localhost:4318/v1/metrics
[2026-02-18 16:18:35] [INFO] [PROFILE] Started CPU profiling
[2026-02-18 16:18:35] [INFO] [SQL] Connecting to SQL Server...
[2026-02-18 16:18:36] [SUCCESS] [SQL] SQL connection established
[2026-02-18 16:18:36] [INFO] [CONFIG] Config loaded from SQL for WFA_TURBINE_10 (EquipID=5010, 265 params)
[2026-02-18 16:18:36] [SUCCESS] [OTEL] SQL log persistence enabled -> ACM_RunLogs
[2026-02-18 16:18:36] [INFO] [RUN] Run #1 | WFA_TURBINE_10 | adaptive | continuous_learning=True | force_retrain=False | intervals=model:1,thresh:1
[2026-02-18 16:18:36] [INFO] [RUN] Run started: WFA_TURBINE_10 (ID=5010) | RunID=cf55f748 | window=[2025-12-05 15:36:36.678526+00:00,2026-02-18 10:48:36.678526+00:00) | tick=107712m
[2026-02-18 16:18:36] [INFO] [RUN] CLI overrides: start=2022-10-09 08:40:00, end=2022-12-23 03:51:59
[2026-02-18 16:18:36] [INFO] [OUTPUT] Manager initialized (batch_size=5000, batching=ON, sql_cache=60.0s, io_workers=8, flush=1000 rows/30.0s, max_futures=50)
[2026-02-18 16:18:36] [INFO] [DATA] Loading from SQL historian: WFA_TURBINE_10
[2026-02-18 16:18:36] [INFO] [DATA] Time range: 2022-10-09 08:40:00 to 2022-12-23 03:51:59
[2026-02-18 16:18:52] [INFO] [DATA] Retrieved 10751 rows from SQL historian
[2026-02-18 16:18:52] [INFO] [DATA] COLDSTART Split: 6450 train rows, 4301 score rows (required train: 500)
[2026-02-18 16:18:54] [INFO] [DATA] Kept 81 numeric columns, dropped 0 non-numeric
[2026-02-18 16:18:54] >>> Checking cadence and resampling for 4301 score rows...
[2026-02-18 16:18:54] >>>   Checking train cadence...
[2026-02-18 16:18:54] >>>   Checking score cadence...
[2026-02-18 16:18:54] >>>   Cadence check complete: train=True, score=True
[2026-02-18 16:18:54] [INFO] [DATA] Cadence: native=600.0s, requested=auto, will_resample=False
[2026-02-18 16:18:54] [INFO] [DATA] SQL historian load complete: 6450 train + 4301 score = 10751 total rows
[2026-02-18 16:18:56] [INFO] [OUTPUT] SQL insert to ACM_DataContractValidation: 1 rows
[2026-02-18 16:18:56] [INFO] [DATA] timestamp=EntryDateTime cadence_ok=True kept=81 drop=0 tz_stripped=0 future_drop=0 dup_removed=0
[2026-02-18 16:18:56] [INFO] [TIMER] data_split_complete  train_rows=6450 train_cols=81 score_rows=4301 score_cols=81
[2026-02-18 16:18:56] >>> CHECKPOINT 1: Data loading complete, about to start baseline seeding
[2026-02-18 16:18:56] >>> CHECKPOINT 2: Entering baseline.seed section for WFA_TURBINE_10...
[2026-02-18 16:18:56] >>> CHECKPOINT 3: About to call seed_baseline() function
[2026-02-18 16:19:35] [INFO] [SEASON] Seasonal: 79 patterns in 68 sensors | adjusted=True
[2026-02-18 16:19:36] [WARN] [DATA] 2 low-variance sensor(s) in TRAIN (std<0.0001): sensor_46, sensor_49
[2026-02-18 16:19:36] [INFO] [DATA] Persisted 2 new low-variance sensors for permanent exclusion.
[2026-02-18 16:19:40] [INFO] [OUTPUT] Auto-flushing batch (rows=0, age=63.9s)
[2026-02-18 16:19:43] [INFO] [OUTPUT] SQL insert to ACM_DataQuality: 1 rows
[2026-02-18 16:19:43] [INFO] [FEAT] Building features with window=16
[2026-02-18 16:19:44] [INFO] [FEAT] Computed 81 fill values from training data
[2026-02-18 16:20:33] [INFO] [FEAT] Features built: train=(6450, 648), score=(4301, 648)
[2026-02-18 16:20:33] [INFO] [FEAT] Features built: train=(6450, 648), score=(4301, 648)
[2026-02-18 16:21:15] [WARN] [FEAT] Dropping 16 columns (0 NaN, 16 low-var)
[2026-02-18 16:21:16] [INFO] [OUTPUT] SQL insert to ACM_FeatureDropLog: 16 rows
[2026-02-18 16:21:19] [INFO] [REGIME_STATE] No existing state found in SQL for EquipID=5010
[2026-02-18 16:21:19] [INFO] [MODEL] Required models missing or invalid - training fresh models
[2026-02-18 16:21:27] [WARN] [AR1] 49 columns with phi clamped to +/-0.999
[2026-02-18 16:21:27] [INFO] [PCA] Fit start: train shape=(6450, 632)
[2026-02-18 16:21:38] [INFO] [PCA] Fit complete in Span: 5 components, 6450 samples, 632 features
[2026-02-18 16:22:30] [INFO] [GMM] BIC search selected k=3
[2026-02-18 16:22:34] [INFO] [GMM] Fitted k=3, cov=diag, reg=0.001
[2026-02-18 16:22:58] [INFO] [OMR] Selected model type: PLS
[2026-02-18 16:23:00] [INFO] [OMR] Fitted PLS model: 6450 samples, 632 features, 5 components, std=3.799
[2026-02-18 16:23:00] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=199.5s)
[2026-02-18 16:23:01] [INFO] [OUTPUT] SQL insert to ACM_OMR_Diagnostics: 1 rows
[2026-02-18 16:23:01] [INFO] [FIT] Fitted 5 detectors in 101.79s: AR1, PCA(5c), IForest(100), GMM(1), OMR(632f) | samples=6450
[2026-02-18 16:23:01] [INFO] [REGIME] Using 21 raw operational sensors for regime clustering: ['power_29_avg', 'power_29_max', 'power_29_min', 'power_29_std', 'power_30_avg']...
[2026-02-18 16:23:56] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=4301
[2026-02-18 16:23:56] [INFO] [REGIME] Using HDBSCAN clustering (primary method)
[2026-02-18 16:23:56] [INFO] [REGIME] HDBSCAN config: min_cluster_size=30, min_samples=3, method=eom, metric=euclidean
[2026-02-18 16:24:23] [INFO] [REGIME] HDBSCAN found 1 clusters, 924 noise points (14.3%)
[2026-02-18 16:25:12] [INFO] [REGIME] HDBSCAN complete: 1 clusters, validity=0.324 (dbcv)
[2026-02-18 16:25:13] [INFO] [REGIME] ENSEMBLE: GMM fallback fitted with k=1 for noise point assignment
[2026-02-18 16:25:16] [INFO] [REGIME] Training distance threshold (P95): 7.2345 (range: 1.2706 - 10.6530)
[2026-02-18 16:25:34] [INFO] [REGIME] Assigned 6413/6450 low-strength points to nearest cluster
[2026-02-18 16:25:47] [INFO] [REGIME] Identified 4301/4301 novel points (assigned to nearest cluster)
[2026-02-18 16:25:47] [INFO] [REGIME_STATE] Saved state v1 to ACM_RegimeState (EquipID=5010)
[2026-02-18 16:25:47] [INFO] [REGIME_STATE] Regime state: saved_v1 | K=1
[2026-02-18 16:25:48] [INFO] [OUTPUT] SQL insert to ACM_RegimeDefinitions: 1 rows
[2026-02-18 16:25:48] [INFO] [REGIME] Wrote 1 regime definitions for audit
[2026-02-18 16:25:49] [INFO] [OUTPUT] SQL insert to ACM_RegimeOccupancy: 1 rows
[2026-02-18 16:25:50] [INFO] [REGIME] Regime analysis: occupancy=1 | transitions=0
[2026-02-18 16:25:51] [INFO] [MODEL] Saving models to SQL ModelRegistry v1
[2026-02-18 16:25:51] [INFO] [MODEL-SQL] Saving models to SQL ModelRegistry v1...
[2026-02-18 16:25:54] [INFO] [MODEL-SQL] - Saved ar1_params (34,392 bytes)
[2026-02-18 16:25:54] [INFO] [MODEL-SQL] - Saved pca_model (31,391 bytes)
[2026-02-18 16:25:58] [INFO] [MODEL-SQL] - Saved iforest_model (4,321,481 bytes)
[2026-02-18 16:25:58] [INFO] [MODEL-SQL] - Saved gmm_model (61,921 bytes)
[2026-02-18 16:25:59] [INFO] [MODEL-SQL] - Saved omr_model (4,441,490 bytes)
[2026-02-18 16:26:00] [INFO] [MODEL-SQL] - Saved regime_model (4,192,531 bytes)
[2026-02-18 16:26:00] [DEBUG] [MODEL-SQL] - Skipping None model: feature_medians
[2026-02-18 16:26:00] [DEBUG] [MODEL-SQL] - Skipping None model: calibration_params
[2026-02-18 16:26:00] [INFO] [MODEL-SQL] OK Committed 6/8 models to SQL ModelRegistry v1
[2026-02-18 16:26:00] [INFO] [MODEL] Saved 8 models to SQL ModelRegistry v1
[2026-02-18 16:26:00] [INFO] [MODEL] Saved all trained models to version v1
[2026-02-18 16:26:00] [INFO] [LIFECYCLE] Created model v1 in LEARNING state
[2026-02-18 16:26:00] [INFO] [LIFECYCLE] Model state v1: LEARNING
[2026-02-18 16:26:02] [INFO] [OUTPUT] SQL insert to ACM_ActiveModels: 1 rows
[2026-02-18 16:26:02] [INFO] [OUTPUT] OutputManager maturity_state set to LEARNING
[2026-02-18 16:26:02] [INFO] [LIFECYCLE] Model state: LEARNING
[2026-02-18 16:26:54] [INFO] [SCORE] Scored 5 detectors: AR1, PCA(cached), IForest, GMM, OMR | samples=6450
[2026-02-18 16:26:55] [INFO] [CAL] Contamination filter (iterative_mad): excluded 347/6450 samples (5.4%) | retained=6103
[2026-02-18 16:26:55] [INFO] [CAL] Self-tuning enabled. Target FP rate 0.100% -> q=0.9950, threshold=5.3016
[2026-02-18 16:26:55] [INFO] [CAL] Contamination filter (iterative_mad): excluded 880/6450 samples (13.6%) | retained=5570
[2026-02-18 16:26:55] [INFO] [CAL] Self-tuning enabled. Target FP rate 0.100% -> q=0.9950, threshold=16016.2448
[2026-02-18 16:26:55] [DEBUG] [CAL] Extreme threshold (16016.24) - clamping to 1000.0
[2026-02-18 16:26:55] [DEBUG] [CAL.FILTER] Iterative MAD: stopping early to preserve min retention ratio
[2026-02-18 16:26:55] [INFO] [CAL] Self-tuning enabled. Target FP rate 0.100% -> q=0.9950, threshold=49.3841
[2026-02-18 16:26:55] [DEBUG] [CAL] Extreme q_z (871.02) - clamping to +/-20
[2026-02-18 16:26:55] [INFO] [CAL] Contamination filter (iterative_mad): excluded 78/6450 samples (1.2%) | retained=6372
[2026-02-18 16:26:55] [INFO] [CAL] Self-tuning enabled. Target FP rate 0.100% -> q=0.9950, threshold=0.4887
[2026-02-18 16:26:55] [INFO] [CAL] Contamination filter (iterative_mad): excluded 377/6450 samples (5.8%) | retained=6073
[2026-02-18 16:26:55] [INFO] [CAL] Self-tuning enabled. Target FP rate 0.100% -> q=0.9950, threshold=1366.4220
[2026-02-18 16:26:55] [DEBUG] [CAL] Extreme threshold (1366.42) - clamping to 1000.0
[2026-02-18 16:26:55] [INFO] [CAL] Contamination filter (iterative_mad): excluded 132/6450 samples (2.0%) | retained=6318
[2026-02-18 16:26:55] [INFO] [CAL] Self-tuning enabled. Target FP rate 0.100% -> q=0.9950, threshold=8.1336
[2026-02-18 16:26:55] [INFO] [CAL] Saved calibration params (6 detectors, 600 bytes) to v1
[2026-02-18 16:26:55] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=235.6s)
[2026-02-18 16:26:56] [INFO] [OUTPUT] SQL insert to ACM_CalibrationSummary: 6 rows
[2026-02-18 16:26:56] [INFO] [CAL] Calibration complete: q=0.98 | clip_z=20.00 | detectors=6 | thresholds=6 | per_regime=0 | summary=6
[2026-02-18 16:26:56] [INFO] [FUSE] CUSUM auto-tuned: k_sigma=2.000->0.800, h_sigma=12.000->3.000 (spread_ratio=9.65)
[2026-02-18 16:26:57] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->gmm_z: 0.51
[2026-02-18 16:26:57] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->omr_z: 0.60
[2026-02-18 16:26:57] [DEBUG] [FUSE] Detector Spearman correlation gmm_z<->iforest_z: 0.87
[2026-02-18 16:26:57] [DEBUG] [FUSE] Detector Spearman correlation gmm_z<->omr_z: 0.82
[2026-02-18 16:26:57] [DEBUG] [FUSE] Detector Spearman correlation iforest_z<->omr_z: 0.73
[2026-02-18 16:26:57] [DEBUG] [FUSE] Detector Spearman correlation pca_spe_z<->pca_t2_z: 0.53
[2026-02-18 16:26:57] [DEBUG] [FUSE] Detector ar1_z: correlated with 2 others, avg_corr=0.55, discount=2.7%
[2026-02-18 16:26:57] [DEBUG] [FUSE] Detector gmm_z: correlated with 3 others, avg_corr=0.73, discount=11.7%
[2026-02-18 16:26:57] [DEBUG] [FUSE] Detector iforest_z: correlated with 2 others, avg_corr=0.80, discount=15.0%
[2026-02-18 16:26:57] [DEBUG] [FUSE] Detector omr_z: correlated with 3 others, avg_corr=0.71, discount=10.7%
[2026-02-18 16:26:57] [DEBUG] [FUSE] Detector pca_spe_z: correlated with 1 others, avg_corr=0.53, discount=1.4%
[2026-02-18 16:26:57] [DEBUG] [FUSE] Detector pca_t2_z: correlated with 1 others, avg_corr=0.53, discount=1.4%
[2026-02-18 16:26:57] [INFO] [FUSE] 6/15 detector pairs correlated, weight adjustments applied
[2026-02-18 16:26:58] [WARN] [TUNE] Excessive weight drift for gmm_z: 0.050 -> 0.085 (drift=70.0% > 20.0%). Rejecting tune.
[2026-02-18 16:26:58] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->gmm_z: 0.51
[2026-02-18 16:26:58] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->omr_z: 0.60
[2026-02-18 16:26:58] [DEBUG] [FUSE] Detector Spearman correlation gmm_z<->iforest_z: 0.87
[2026-02-18 16:26:58] [DEBUG] [FUSE] Detector Spearman correlation gmm_z<->omr_z: 0.82
[2026-02-18 16:26:58] [DEBUG] [FUSE] Detector Spearman correlation iforest_z<->omr_z: 0.73
[2026-02-18 16:26:58] [DEBUG] [FUSE] Detector Spearman correlation pca_spe_z<->pca_t2_z: 0.53
[2026-02-18 16:26:58] [DEBUG] [FUSE] Detector ar1_z: correlated with 2 others, avg_corr=0.55, discount=2.7%
[2026-02-18 16:26:58] [DEBUG] [FUSE] Detector gmm_z: correlated with 3 others, avg_corr=0.73, discount=11.7%
[2026-02-18 16:26:58] [DEBUG] [FUSE] Detector iforest_z: correlated with 2 others, avg_corr=0.80, discount=15.0%
[2026-02-18 16:26:58] [DEBUG] [FUSE] Detector omr_z: correlated with 3 others, avg_corr=0.71, discount=10.7%
[2026-02-18 16:26:58] [DEBUG] [FUSE] Detector pca_spe_z: correlated with 1 others, avg_corr=0.53, discount=1.4%
[2026-02-18 16:26:58] [DEBUG] [FUSE] Detector pca_t2_z: correlated with 1 others, avg_corr=0.53, discount=1.4%
[2026-02-18 16:26:58] [INFO] [FUSE] 6/15 detector pairs correlated, weight adjustments applied
[2026-02-18 16:26:58] [INFO] [OUTPUT] Saved fusion metrics -> SQL:ACM_RunMetrics (18 records)
[2026-02-18 16:35:26] [INFO] [FUSE] Fusion: detectors=6 | episodes=67 | auto_tuned=True
[2026-02-18 16:35:26] [INFO] [TRANSIENT] Using 168 operating-variable columns for transient detection; excluded 464 condition-indicator columns
[2026-02-18 16:35:29] [INFO] [TRANSIENT] State distribution: {'trip': 4218, 'shutdown': 67, 'startup': 16}
[2026-02-18 16:35:29] [INFO] [REGIME] Regime: quality_ok=False | states={'unknown': 4301} | transient={'trip': 4218, 'shutdown': 67, 'startup': 16}
[2026-02-18 16:35:29] [WARN] [RETRAIN-TRIGGER] Anomaly rate 41.27% exceeds threshold 25.00%
[2026-02-18 16:35:30] [INFO] [CONFIG_HIST] Logged 2 config changes for RunID=cf55f748-799b-4cf3-ae47-615cef193830
[2026-02-18 16:35:30] [INFO] [AUTO-TUNE] Auto-tune: 2 adjustments (k_sigma: 2.000->2.200, k_max: 6->8) | refit=next_run
[2026-02-18 16:35:30] [INFO] [OUTPUT] SQL refit request recorded in ACM_RefitRequests
[2026-02-18 16:35:31] [DEBUG] [CAL] Extreme threshold (3278.03) - clamping to 1000.0
[2026-02-18 16:35:31] [INFO] [DRIFT] Drift: cusum_z P95=3.379 | trend=0.0053 | fused=5.084 | mode=FAULT
[2026-02-18 16:35:32] [INFO] [OUTPUT] SQL insert to ACM_DriftController: 1 rows
[2026-02-18 16:35:33] [INFO] [BASELINE] Skipping buffer write (models exist, next refresh in 9 batches)
[2026-02-18 16:35:39] [INFO] [OUTPUT] Auto-flushing batch (rows=6, age=523.3s)
[2026-02-18 16:35:45] [INFO] [OUTPUT] SQL insert to ACM_Scores_Wide: 4301 rows
[2026-02-18 16:35:45] [INFO] [IO] Scores written: {'sql_written': True, 'rows': 4301, 'inserted': 4301, 'error': None, 'sql_table': 'ACM_Scores_Wide', 'artifact': 'scores'} rows
[2026-02-18 16:35:45] [INFO] [EPISODES] Applied 5 schema repairs to episodes: peak_timestamp_fallback_used, regime_mapped_fallback, dominant_sensor_extracted, severity_calculated, status_defaulted
[2026-02-18 16:35:45] [INFO] [OUTPUT] Auto-flushing batch (rows=4301, age=6.4s)
[2026-02-18 16:35:47] [INFO] [OUTPUT] SQL insert to ACM_EpisodeDiagnostics: 67 rows
[2026-02-18 16:35:49] [INFO] [OUTPUT] SQL insert to ACM_Episodes: 67 rows
[2026-02-18 16:35:49] [INFO] [IO] Episodes written: {'sql_written': True, 'rows': 67, 'inserted': 67, 'error': None, 'sql_table': 'ACM_EpisodeDiagnostics', 'artifact': 'episodes'} rows
[2026-02-18 16:35:51] [INFO] [OUTPUT] SQL insert to ACM_DetectorCorrelation: 49 rows
[2026-02-18 16:35:54] [INFO] [OUTPUT] SQL insert to ACM_SensorCorrelations: 3160 rows
[2026-02-18 16:36:04] [INFO] [OUTPUT] SQL insert to ACM_SensorNormalized_TS: 10287 rows
[2026-02-18 16:36:05] [INFO] [OUTPUT] SQL insert to ACM_SeasonalPatterns: 79 rows
[2026-02-18 16:36:06] [INFO] [ANALYTICS] Generating analytics tables (v11 SQL-only)...
[2026-02-18 16:36:06] [INFO] [OUTPUT] Bulk pre-delete: 3 tables targeted, 3 DELETE statements in 0.04s (batched)
[2026-02-18 16:36:12] [INFO] [OUTPUT] SQL insert to ACM_HealthTimeline: 4301 rows
[2026-02-18 16:36:13] [INFO] [OUTPUT] Auto-flushing batch (rows=4368, age=27.4s)
[2026-02-18 16:36:17] [INFO] [OUTPUT] SQL insert to ACM_RegimeTimeline: 4301 rows
[2026-02-18 16:36:17] [INFO] [OUTPUT] Auto-flushing batch (rows=4301, age=4.7s)
[2026-02-18 16:36:18] [INFO] [OUTPUT] SQL insert to ACM_SensorDefects: 7 rows
[2026-02-18 16:36:25] [INFO] [OUTPUT] SQL insert to ACM_SensorHotspots: 25 rows
[2026-02-18 16:36:25] [INFO] [ANALYTICS] Generated analytics tables (SQL written: 4)
[2026-02-18 16:36:25] [INFO] [OUTPUTS] Analytics: tables=4
[2026-02-18 16:36:25] [INFO] [HealthTracker] Data anchor: 2022-12-23 03:50:00, window cutoff: 2022-09-24 03:50:00 (2160h lookback)
[2026-02-18 16:36:26] [INFO] [HealthTracker] Loaded 4301 health points from SQL (rolling window: 2160h)
[2026-02-18 16:36:27] [INFO] [FORECAST] Data summary: n_samples=4301, dt_hours=0.17, window=718h
[2026-02-18 16:36:27] [INFO] [STATE] No previous state for EquipID=5010; starting fresh
[2026-02-18 16:36:27] [INFO] [FORECAST] Loaded forecast config: alpha=0.30, beta=0.10, failure_threshold=70.0, horizon=168h
[2026-02-18 16:36:29] [INFO] [DEGRADE] HEALTH-JUMP: Using second-to-last jump at 2022-12-22 22:20:00 (33 post-jump samples)
[2026-02-18 16:36:31] [INFO] [DEGRADE] Adaptive smoothing: alpha=0.950, beta=0.300
[2026-02-18 16:36:31] [INFO] [DEGRADE] Fitted: level=59.46, trend=-0.8333/hr, std_error=5.15, n=33
[2026-02-18 16:36:31] [INFO] [DEGRADE] HEALTH-JUMP: Using second-to-last jump at 2022-12-22 22:20:00 (33 post-jump samples)
[2026-02-18 16:36:33] [INFO] [DEGRADE] Adaptive smoothing: alpha=0.950, beta=0.300
[2026-02-18 16:36:33] [INFO] [DEGRADE] Fitted: level=59.46, trend=-0.8333/hr, std_error=5.15, n=33
[2026-02-18 16:36:33] [INFO] [DEGRADE] Fitted regime-conditioned model with 1 regimes
[2026-02-18 16:36:33] [INFO] [FORECAST] RUL_P50=0.0h, RUL_Spread=0.0h, RUL_CV=nan, CI_Width=95.79, Health=59.4, N=4301, Quality=OK
[2026-02-18 16:36:34] [INFO] [SENSOR_ATTR] Loaded 25 sensor attributions from SQL
[2026-02-18 16:36:35] [INFO] [OUTPUT] SQL insert to ACM_HealthForecast: 168 rows
[2026-02-18 16:36:37] [INFO] [OUTPUT] SQL insert to ACM_FailureForecast: 168 rows
[2026-02-18 16:36:37] [WARN] [FORECAST] RUL reliability: LEARNING - Model still LEARNING - predictions may be unreliable
[2026-02-18 16:36:40] [INFO] [OUTPUT] SQL insert to ACM_RUL: 1 rows
[2026-02-18 16:36:40] [INFO] [FORECAST] Wrote 3 forecast tables to SQL
[2026-02-18 16:36:40] [DEBUG] [FORECAST] Sensor forecast query: equip=5010, cutoff=2022-11-23 01:10:00, sensors=['sensor_31_std', 'sensor_5_std', 'sensor_18_std']...
[2026-02-18 16:36:40] [DEBUG] [FORECAST] Sensor forecast query returned 1270 rows
[2026-02-18 16:36:53] [INFO] [FORECAST] Generated 1680 sensor forecast points for 10 sensors over 168h
[2026-02-18 16:36:53] [INFO] [OUTPUT] Auto-flushing batch (rows=369, age=36.0s)
[2026-02-18 16:36:57] [INFO] [OUTPUT] SQL insert to ACM_SensorForecast: 1680 rows
[2026-02-18 16:36:57] [INFO] [FORECAST] Wrote sensor forecasts for 25 sensors
[2026-02-18 16:36:58] [WARN] [MultivariateForecast] Insufficient data: 30 < 100
[2026-02-18 16:36:58] [INFO] [FORECAST] Regime context: regime=0, omr_z=2.2928645610809326, drift_trend=unknown
[2026-02-18 16:36:58] [INFO] [STATE] Saved state for EquipID=5010
[2026-02-18 16:36:59] [INFO] [FORECAST] Forecast: RUL P10/50/90=0/0/0h | tables=4 | top_sensors=sen
[2026-02-18 16:36:59] [INFO] [OUTPUT] Batched transaction committed (80.52s)
[2026-02-18 16:37:00] [INFO] [OUTPUT] SQL insert to ACM_PCA_Models: 1 rows
[2026-02-18 16:37:04] [INFO] [OUTPUT] SQL insert to ACM_PCA_Loadings: 3160 rows
[2026-02-18 16:37:05] [INFO] [OUTPUT] SQL insert to ACM_Run_Stats: 1 rows
[2026-02-18 16:37:17] [INFO] [CULPRITS] Wrote 454 culprit records to ACM_EpisodeCulprits
[2026-02-18 16:37:17] >>> --- Performance Summary ---
[2026-02-18 16:37:17] >>> startup: 0.3364s
[2026-02-18 16:37:17] >>> data.contract: 1.6606s
[2026-02-18 16:37:17] >>> load_data: 19.3484s
[2026-02-18 16:37:17] >>> baseline.seed: 0.0522s
[2026-02-18 16:37:17] >>> seasonality.detect: 39.5370s
[2026-02-18 16:37:17] >>> data.guardrails: 7.5707s
[2026-02-18 16:37:17] >>> features.build: 49.2037s
[2026-02-18 16:37:17] >>> features.impute: 43.4438s
[2026-02-18 16:37:17] >>> features.hash: 2.9993s
[2026-02-18 16:37:17] >>> models.refit_flag: 0.0271s
[2026-02-18 16:37:17] >>> models.load: 0.0409s
[2026-02-18 16:37:17] >>> train.detector_fit: 101.8254s
[2026-02-18 16:37:17] >>> score.detector_score: 53.6366s
[2026-02-18 16:37:17] >>> regimes.label: 112.7374s
[2026-02-18 16:37:17] >>> regimes.occupancy: 1.5274s
[2026-02-18 16:37:17] >>> models.persistence.save: 11.9688s
[2026-02-18 16:37:17] >>> calibrate: 54.2571s
[2026-02-18 16:37:17] >>> fusion: 509.4716s
[2026-02-18 16:37:17] >>> thresholds.adaptive: 0.0222s
[2026-02-18 16:37:17] >>> regimes.transient_detection: 3.3847s
[2026-02-18 16:37:17] >>> drift: 1.2255s
[2026-02-18 16:37:17] >>> drift.controller: 0.8224s
[2026-02-18 16:37:17] >>> baseline.buffer_write: 0.0456s
[2026-02-18 16:37:17] >>> sensor.context: 4.7414s
[2026-02-18 16:37:17] >>> contribution.timeline: 0.0218s
[2026-02-18 16:37:17] >>> persist.write_scores: 6.5949s
[2026-02-18 16:37:17] >>> persist.write_episodes: 4.6272s
[2026-02-18 16:37:17] >>> persist.detector_correlation: 1.1187s
[2026-02-18 16:37:17] >>> persist.sensor_correlation: 3.0551s
[2026-02-18 16:37:17] >>> persist.sensor_normalized_ts: 9.9422s
[2026-02-18 16:37:17] >>> persist.seasonal_patterns: 1.6112s
[2026-02-18 16:37:17] >>> outputs.comprehensive_analytics: 19.3552s
[2026-02-18 16:37:17] >>> outputs.forecasting: 33.5462s
[2026-02-18 16:37:17] >>> persist: 80.5645s
[2026-02-18 16:37:17] >>> sql.pca: 5.7081s
[2026-02-18 16:37:17] >>> sql.run_stats: 0.5978s
[2026-02-18 16:37:17] >>> sql.culprits: 11.5502s
[2026-02-18 16:37:18] [DEBUG] [RUN_META] No data quality records found in SQL, defaulting to 100.0
[2026-02-18 16:37:18] [INFO] [RUN_META] Wrote run metadata to ACM_Runs: cf55f748-799b-4cf3-ae47-615cef193830
[2026-02-18 16:37:18] [INFO] [RUN] Finalized RunID=cf55f748-799b-4cf3-ae47-615cef193830 outcome=OK rows_in=4301 rows_out=3162
[2026-02-18 16:37:18] [DEBUG] [OUTPUT] OutputManager stats: 12 write_dataframe calls, 0 batch rows, 2.806s avg write time
[2026-02-18 16:37:18] [INFO] [PROFILE] Stopping and pushing profile data...
[2026-02-18 16:37:43] >>> --- Top CPU Functions ---
[2026-02-18 16:37:43] >>>    1. common.DatetimeIndex.new_method: 699887.4ms (969 calls)
[2026-02-18 16:37:43] >>>    2. frame.DataFrame._arith_method: 695278.0ms (136 calls)
[2026-02-18 16:37:43] >>>    3. frame.DataFrame._dispatch_frame_op: 662293.6ms (138 calls)
[2026-02-18 16:37:43] >>>    4. managers.BlockManager.operate_blockwise: 662199.9ms (136 calls)
[2026-02-18 16:37:43] >>>    5. ops.operate_blockwise: 662199.9ms (136 calls)
[2026-02-18 16:37:43] >>>    6. arraylike.DataFrame.__truediv__: 578918.6ms (147 calls)
[2026-02-18 16:37:43] >>>    7. detector_orchestrator.score_all_detectors: 533684.2ms (2 calls)
[2026-02-18 16:37:43] >>>    8. outliers._finite_impute: 504262.4ms (6 calls)
[2026-02-18 16:37:43] >>>    9. fuse.run_fusion_pipeline: 503640.6ms (1 calls)
[2026-02-18 16:37:43] >>>   10. fuse.Fuser.detect_episodes: 501546.9ms (1 calls)
[2026-02-18 16:37:45] [INFO] [PROFILE] Pushing cpu (2615 stacks) to Pyroscope...
[2026-02-18 16:37:45] [SUCCESS] [PROFILE] cpu profile pushed successfully
[2026-02-18 16:37:47] [INFO] [PROFILE] Pushing alloc_objects (500 stacks) to Pyroscope...
[2026-02-18 16:37:47] [SUCCESS] [PROFILE] alloc_objects profile pushed successfully
[2026-02-18 16:37:48] [INFO] [PROFILE] Pushing alloc_space (500 stacks) to Pyroscope...
[2026-02-18 16:37:48] [SUCCESS] [PROFILE] alloc_space profile pushed successfully
[2026-02-18 16:37:48] [SUCCESS] [PROFILE] Profile data pushed to Pyroscope
[2026-02-18 16:37:52] >>> --- Timer Summary ---
[2026-02-18 16:37:52] >>> fusion                         509.472s ( 44.0%)
[2026-02-18 16:37:52] >>> regimes.label                  112.737s (  9.7%)
[2026-02-18 16:37:52] >>> train.detector_fit             101.825s (  8.8%)
[2026-02-18 16:37:52] >>> persist                         80.564s (  7.0%)
[2026-02-18 16:37:52] >>> calibrate                       54.257s (  4.7%)
[2026-02-18 16:37:52] >>> score.detector_score            53.637s (  4.6%)
[2026-02-18 16:37:52] >>> features.build                  49.204s (  4.3%)
[2026-02-18 16:37:52] >>> features.impute                 43.444s (  3.8%)
[2026-02-18 16:37:52] >>> seasonality.detect              39.537s (  3.4%)
[2026-02-18 16:37:52] >>> outputs.forecasting             33.546s (  2.9%)
[2026-02-18 16:37:52] >>> outputs.comprehensive_analytics  19.355s (  1.7%)
[2026-02-18 16:37:52] >>> load_data                       19.348s (  1.7%)
[2026-02-18 16:37:52] >>> models.persistence.save         11.969s (  1.0%)
[2026-02-18 16:37:52] >>> sql.culprits                    11.550s (  1.0%)
[2026-02-18 16:37:52] >>> persist.sensor_normalized_ts     9.942s (  0.9%)
[2026-02-18 16:37:52] >>> data.guardrails                  7.571s (  0.7%)
[2026-02-18 16:37:52] >>> persist.write_scores             6.595s (  0.6%)
[2026-02-18 16:37:52] >>> sql.pca                          5.708s (  0.5%)
[2026-02-18 16:37:52] >>> sensor.context                   4.741s (  0.4%)
[2026-02-18 16:37:52] >>> persist.write_episodes           4.627s (  0.4%)
[2026-02-18 16:37:52] >>> regimes.transient_detection      3.385s (  0.3%)
[2026-02-18 16:37:52] >>> persist.sensor_correlation       3.055s (  0.3%)
[2026-02-18 16:37:52] >>> features.hash                    2.999s (  0.3%)
[2026-02-18 16:37:52] >>> data.contract                    1.661s (  0.1%)
[2026-02-18 16:37:52] >>> persist.seasonal_patterns        1.611s (  0.1%)
[2026-02-18 16:37:52] >>> regimes.occupancy                1.527s (  0.1%)
[2026-02-18 16:37:52] >>> drift                            1.226s (  0.1%)
[2026-02-18 16:37:52] >>> persist.detector_correlation     1.119s (  0.1%)
[2026-02-18 16:37:52] >>> drift.controller                 0.822s (  0.1%)
[2026-02-18 16:37:52] >>> sql.run_stats                    0.598s (  0.1%)
[2026-02-18 16:37:52] >>> startup                          0.336s (  0.0%)
[2026-02-18 16:37:52] >>> baseline.seed                    0.052s (  0.0%)
[2026-02-18 16:37:52] >>> baseline.buffer_write            0.046s (  0.0%)
[2026-02-18 16:37:52] >>> models.load                      0.041s (  0.0%)
[2026-02-18 16:37:52] >>> models.refit_flag                0.027s (  0.0%)
[2026-02-18 16:37:52] >>> thresholds.adaptive              0.022s (  0.0%)
[2026-02-18 16:37:52] >>> contribution.timeline            0.022s (  0.0%)
[2026-02-18 16:37:52] >>> total_run                      1157.057s

[2026-02-18 16:37:52] [INFO] [QA] Inspecting outputs for EquipID=5010, RunID=CF55F748-799B-4CF3-AE47-615CEF193830 (from ACM_Runs), window=[2026-02-18 10:48:36.695158,2026-02-18 11:07:18.226666)
[2026-02-18 16:37:52] [INFO] [QA] ACM_Scores_Wide: 4301 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_HealthTimeline: 4301 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_RegimeTimeline: 4301 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_EpisodeDiagnostics: 67 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_Episodes: 67 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_EpisodeMetrics: 0 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_SensorNormalized_TS: 10287 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_SensorCorrelations: 3160 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_DetectorCorrelation: 49 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_SeasonalPatterns: 79 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_HealthForecast: 168 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_FailureForecast: 168 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_RUL: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_DriftController: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_RegimeDefinitions: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_RegimeOccupancy: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_Run_Stats: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_PCA_Models: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_PCA_Loadings: 3160 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_PCA_Metrics: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_SensorHotspots: 25 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [QA] ACM_SensorDefects: 7 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:37:52] [INFO] [COLDSTART] WFA_TURBINE_10: Checking coldstart status in SQL (ModelRegistry/ACM_ColdstartState)...
[2026-02-18 16:37:52] [INFO] [COLDSTART] WFA_TURBINE_10: Detected existing models in ModelRegistry (count=3) and Status=COMPLETE
[2026-02-18 16:37:52] [SUCCESS] [COLDSTART] WFA_TURBINE_10: Coldstart COMPLETE!
[2026-02-18 16:37:52] [INFO] [BATCH]
============================================================
[2026-02-18 16:37:52] [INFO] [BATCH] Starting batch processing for WFA_TURBINE_10
[2026-02-18 16:37:52] [INFO] [BATCH] ============================================================
[2026-02-18 16:37:52] [INFO] [BATCH] WFA_TURBINE_10: Data available from 2022-10-09 08:40:00 to 2023-10-18 08:40:00
[2026-02-18 16:37:52] [INFO] [BATCH] WFA_TURBINE_10: Processing 4 batch(es) (107712-minute windows)
[2026-02-18 16:37:52] [INFO] [BATCH]
WFA_TURBINE_10: Batch 1/4 - [2022-12-23 03:52:00 to 2023-03-07 23:03:59]
[2026-02-18 16:37:52] [INFO] [RUN] C:\Users\bhadk\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe -m core.acm_main --equip WFA_TURBINE_10 --start-time 2022-12-23T03:52:00 --end-time 2023-03-07T23:03:59
[2026-02-18 16:37:52] [INFO] [BATCH] WFA_TURBINE_10: Batch 1 - scoring with existing models
[2026-02-18 16:37:56] [SUCCESS] [OTEL] Loki logs -> http://localhost:3100
[2026-02-18 16:37:56] [SUCCESS] [OTEL] Profiling -> http://localhost:4040 [cpu (yappi), memory (tracemalloc)]
[2026-02-18 16:37:56] [SUCCESS] [OTEL] Traces -> http://localhost:4318/v1/traces
[2026-02-18 16:37:56] [SUCCESS] [OTEL] Metrics -> http://localhost:4318/v1/metrics
[2026-02-18 16:37:56] [INFO] [PROFILE] Started CPU profiling
[2026-02-18 16:37:57] [INFO] [SQL] Connecting to SQL Server...
[2026-02-18 16:37:57] [SUCCESS] [SQL] SQL connection established
[2026-02-18 16:37:57] [INFO] [CONFIG] Config loaded from SQL for WFA_TURBINE_10 (EquipID=5010, 265 params)
[2026-02-18 16:37:58] [SUCCESS] [OTEL] SQL log persistence enabled -> ACM_RunLogs
[2026-02-18 16:37:58] [INFO] [RUN] Run #2 | WFA_TURBINE_10 | adaptive | continuous_learning=True | force_retrain=False | intervals=model:1,thresh:1
[2026-02-18 16:37:58] [INFO] [RUN] Run started: WFA_TURBINE_10 (ID=5010) | RunID=6d60b75f | window=[2025-12-05 15:55:58.283425+00:00,2026-02-18 11:07:58.283425+00:00) | tick=107712m
[2026-02-18 16:37:58] [INFO] [RUN] CLI overrides: start=2022-12-23 03:52:00, end=2023-03-07 23:03:59
[2026-02-18 16:37:58] [INFO] [OUTPUT] Manager initialized (batch_size=5000, batching=ON, sql_cache=60.0s, io_workers=8, flush=1000 rows/30.0s, max_futures=50)
[2026-02-18 16:37:58] [INFO] [DATA] Loading from SQL historian: WFA_TURBINE_10
[2026-02-18 16:37:58] [INFO] [DATA] Time range: 2022-12-23 03:52:00 to 2023-03-07 23:03:59
[2026-02-18 16:38:13] [INFO] [DATA] Retrieved 10722 rows from SQL historian
[2026-02-18 16:38:13] [INFO] [DATA] BATCH MODE: All 10722 rows allocated to scoring (baseline from cache)
[2026-02-18 16:38:14] [INFO] [DATA] BATCH MODE: Train empty (baseline_buffer later), using 81 score columns
[2026-02-18 16:38:14] [INFO] [DATA] Kept 81 numeric columns, dropped 0 non-numeric
[2026-02-18 16:38:14] >>> Checking cadence and resampling for 10722 score rows...
[2026-02-18 16:38:14] >>>   Checking train cadence...
[2026-02-18 16:38:14] >>>   Checking score cadence...
[2026-02-18 16:38:14] >>>   Cadence check complete: train=True, score=True
[2026-02-18 16:38:14] [INFO] [DATA] Cadence: native=600.0s, requested=auto, will_resample=False
[2026-02-18 16:38:14] [INFO] [DATA] SQL historian load complete: 0 train + 10722 score = 10722 total rows
[2026-02-18 16:38:16] [INFO] [OUTPUT] SQL insert to ACM_DataContractValidation: 1 rows
[2026-02-18 16:38:16] [INFO] [DATA] timestamp=EntryDateTime cadence_ok=True kept=81 drop=0 tz_stripped=0 future_drop=0 dup_removed=0
[2026-02-18 16:38:16] [INFO] [TIMER] data_split_complete  train_rows=0 train_cols=81 score_rows=10722 score_cols=81
[2026-02-18 16:38:16] >>> CHECKPOINT 1: Data loading complete, about to start baseline seeding
[2026-02-18 16:38:16] >>> CHECKPOINT 2: Entering baseline.seed section for WFA_TURBINE_10...
[2026-02-18 16:38:16] >>> CHECKPOINT 3: About to call seed_baseline() function
[2026-02-18 16:38:16] [INFO] [BASELINE] Baseline: score split (train=5361, no overlap) | extended=False
[2026-02-18 16:39:03] [INFO] [SEASON] Seasonal: 142 patterns in 76 sensors | adjusted=True
[2026-02-18 16:39:04] [WARN] [DATA] 2 low-variance sensor(s) in TRAIN (std<0.0001): sensor_46, sensor_49
[2026-02-18 16:39:04] [INFO] [DATA] Persisted 0 new low-variance sensors for permanent exclusion.
[2026-02-18 16:39:08] [INFO] [OUTPUT] Auto-flushing batch (rows=0, age=69.8s)
[2026-02-18 16:39:10] [INFO] [OUTPUT] SQL insert to ACM_DataQuality: 1 rows
[2026-02-18 16:39:11] [INFO] [FEAT] Building features with window=16
[2026-02-18 16:39:11] [INFO] [FEAT] Computed 81 fill values from training data
[2026-02-18 16:39:58] [INFO] [FEAT] Features built: train=(5361, 648), score=(5361, 648)
[2026-02-18 16:39:58] [INFO] [FEAT] Features built: train=(5361, 648), score=(5361, 648)
[2026-02-18 16:40:39] [WARN] [FEAT] Dropping 16 columns (0 NaN, 16 low-var)
[2026-02-18 16:40:39] [INFO] [OUTPUT] SQL insert to ACM_FeatureDropLog: 16 rows
[2026-02-18 16:40:43] [WARN] [MODEL] SQL refit request found: id=468 at 2026-02-18 16:35:30.071453
[2026-02-18 16:40:43] [INFO] [MODEL-LOAD] Loading cached models for equip=WFA_TURBINE_10, equip_id=5010
[2026-02-18 16:40:43] [INFO] [MODEL-SQL] Loading models from SQL ModelRegistry v1...
[2026-02-18 16:40:45] [INFO] [MODEL-SQL] - Loaded ar1_params (34,392 bytes)
[2026-02-18 16:40:45] [INFO] [MODEL-SQL] - Loaded calibration_params (600 bytes)
[2026-02-18 16:40:45] [INFO] [MODEL-SQL] - Loaded gmm_model (61,921 bytes)
[2026-02-18 16:40:54] [INFO] [MODEL-SQL] - Loaded iforest_model (4,321,481 bytes)
[2026-02-18 16:40:55] [INFO] [MODEL-SQL] - Loaded omr_model (4,441,490 bytes)
[2026-02-18 16:40:55] [INFO] [MODEL-SQL] - Loaded pca_model (31,391 bytes)
[2026-02-18 16:40:56] [INFO] [MODEL-SQL] - Loaded regime_model (4,192,531 bytes)
[2026-02-18 16:40:56] [INFO] [MODEL-SQL] [OK] Loaded 7/7 models from SQL ModelRegistry v1
[2026-02-18 16:40:56] [INFO] [MODEL] [OK] Loaded from SQL ModelRegistry successfully
[2026-02-18 16:40:56] [INFO] [MODEL-LOAD] Load result: models=True, manifest=True
[2026-02-18 16:40:56] [INFO] [MODEL] Using cached models v1: sensors=632 | sig=96c15b58c09d1cbb...
[2026-02-18 16:40:56] [INFO] [CAL] Loaded cached calibration params (6 detectors)
[2026-02-18 16:40:57] [INFO] [REGIME] Using 21 raw operational sensors for regime clustering: ['power_29_avg', 'power_29_max', 'power_29_min', 'power_29_std', 'power_30_avg']...
[2026-02-18 16:41:20] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=5361
[2026-02-18 16:41:20] [INFO] [LIFECYCLE] Model maturity: LEARNING
[2026-02-18 16:41:42] [INFO] [REGIME] Assigned 5361/5361 low-strength points to nearest cluster
[2026-02-18 16:42:04] [INFO] [REGIME] Identified 5361/5361 novel points (assigned to nearest cluster)
[2026-02-18 16:42:05] [INFO] [OUTPUT] SQL insert to ACM_RegimeDefinitions: 1 rows
[2026-02-18 16:42:05] [INFO] [REGIME] Wrote 1 regime definitions for audit
[2026-02-18 16:42:06] [INFO] [OUTPUT] SQL insert to ACM_RegimeOccupancy: 1 rows
[2026-02-18 16:42:07] [INFO] [REGIME] Regime analysis: occupancy=1 | transitions=0
[2026-02-18 16:42:07] [WARN] [MODEL] Forcing retraining: regime_quality_ok=False (metric=dbcv, score=0.324)
[2026-02-18 16:42:17] [WARN] [AR1] 77 columns with phi clamped to +/-0.999
[2026-02-18 16:42:17] [INFO] [PCA] Fit start: train shape=(5361, 632)
[2026-02-18 16:42:26] [INFO] [PCA] Fit complete in Span: 5 components, 5361 samples, 632 features
[2026-02-18 16:43:10] [INFO] [GMM] BIC search selected k=3
[2026-02-18 16:43:15] [INFO] [GMM] Fitted k=3, cov=diag, reg=0.001
[2026-02-18 16:43:37] [INFO] [OMR] Selected model type: PLS
[2026-02-18 16:43:38] [INFO] [OMR] Fitted PLS model: 5361 samples, 632 features, 5 components, std=4.738
[2026-02-18 16:43:38] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=270.4s)
[2026-02-18 16:43:39] [INFO] [OUTPUT] SQL insert to ACM_OMR_Diagnostics: 1 rows
[2026-02-18 16:43:39] [INFO] [FIT] Fitted 5 detectors in 92.51s: AR1, PCA(5c), IForest(100), GMM(1), OMR(632f) | samples=5361
[2026-02-18 16:43:40] [INFO] [MODEL] Saving models to SQL ModelRegistry v2
[2026-02-18 16:43:40] [INFO] [MODEL-SQL] Saving models to SQL ModelRegistry v2...
[2026-02-18 16:43:43] [INFO] [MODEL-SQL] - Saved ar1_params (34,392 bytes)
[2026-02-18 16:43:43] [INFO] [MODEL-SQL] - Saved pca_model (31,391 bytes)
[2026-02-18 16:43:47] [INFO] [MODEL-SQL] - Saved iforest_model (4,149,369 bytes)
[2026-02-18 16:43:47] [INFO] [MODEL-SQL] - Saved gmm_model (62,263 bytes)
[2026-02-18 16:43:49] [INFO] [MODEL-SQL] - Saved omr_model (4,267,274 bytes)
[2026-02-18 16:43:49] [DEBUG] [MODEL-SQL] - Skipping None model: regime_model
[2026-02-18 16:43:49] [DEBUG] [MODEL-SQL] - Skipping None model: feature_medians
[2026-02-18 16:43:49] [DEBUG] [MODEL-SQL] - Skipping None model: calibration_params
[2026-02-18 16:43:49] [INFO] [MODEL-SQL] OK Committed 5/8 models to SQL ModelRegistry v2
[2026-02-18 16:43:49] [INFO] [MODEL] Saved 8 models to SQL ModelRegistry v2
[2026-02-18 16:43:49] [INFO] [MODEL] Saved all trained models to version v2
[2026-02-18 16:43:49] [INFO] [LIFECYCLE] Promotion not eligible: consecutive_runs=2 < 3
[2026-02-18 16:43:49] [INFO] [LIFECYCLE] Model state v1: LEARNING
[2026-02-18 16:43:51] [INFO] [OUTPUT] SQL insert to ACM_ActiveModels: 1 rows
[2026-02-18 16:43:51] [INFO] [OUTPUT] OutputManager maturity_state set to LEARNING
[2026-02-18 16:43:51] [INFO] [LIFECYCLE] Model state: LEARNING
[2026-02-18 16:44:41] [INFO] [SCORE] Scored 5 detectors: AR1, PCA(cached), IForest, GMM, OMR | samples=5361
[2026-02-18 16:44:42] [INFO] [CAL] Using cached calibration for 6 detectors (training-anchored)
[2026-02-18 16:44:42] [INFO] [CAL] Saved calibration params (6 detectors, 600 bytes) to v2
[2026-02-18 16:44:42] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=63.8s)
[2026-02-18 16:44:43] [INFO] [OUTPUT] SQL insert to ACM_CalibrationSummary: 6 rows
[2026-02-18 16:44:43] [INFO] [CAL] Calibration complete: q=0.98 | clip_z=28.95 | detectors=6 | thresholds=6 | per_regime=0 | summary=6
[2026-02-18 16:44:43] [INFO] [FUSE] CUSUM auto-tuned: k_sigma=2.000->0.800, h_sigma=12.000->3.000 (spread_ratio=1.10)
[2026-02-18 16:44:43] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->omr_z: 0.62
[2026-02-18 16:44:43] [DEBUG] [FUSE] Detector ar1_z: correlated with 1 others, avg_corr=0.62, discount=6.0%
[2026-02-18 16:44:43] [DEBUG] [FUSE] Detector omr_z: correlated with 1 others, avg_corr=0.62, discount=6.0%
[2026-02-18 16:44:43] [INFO] [FUSE] 1/1 detector pairs correlated, weight adjustments applied
[2026-02-18 16:44:43] [WARN] [TUNE] gmm_z: all same sign - limited separability
[2026-02-18 16:44:43] [WARN] [TUNE] iforest_z: all same sign - limited separability
[2026-02-18 16:44:43] [WARN] [TUNE] pca_spe_z: all same sign - limited separability
[2026-02-18 16:44:43] [WARN] [TUNE] pca_t2_z: all same sign - limited separability
[2026-02-18 16:44:43] [WARN] [TUNE] Excessive weight drift for gmm_z: 0.050 -> 0.086 (drift=72.2% > 20.0%). Rejecting tune.
[2026-02-18 16:44:44] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->omr_z: 0.62
[2026-02-18 16:44:44] [DEBUG] [FUSE] Detector ar1_z: correlated with 1 others, avg_corr=0.62, discount=6.0%
[2026-02-18 16:44:44] [DEBUG] [FUSE] Detector omr_z: correlated with 1 others, avg_corr=0.62, discount=6.0%
[2026-02-18 16:44:44] [INFO] [FUSE] 1/1 detector pairs correlated, weight adjustments applied
[2026-02-18 16:44:44] [INFO] [OUTPUT] Saved fusion metrics -> SQL:ACM_RunMetrics (18 records)
[2026-02-18 16:44:56] [INFO] [FUSE] Fusion: detectors=6 | episodes=77 | auto_tuned=True
[2026-02-18 16:44:57] [INFO] [TRANSIENT] Using 168 operating-variable columns for transient detection; excluded 464 condition-indicator columns
[2026-02-18 16:44:59] [INFO] [TRANSIENT] State distribution: {'trip': 5116, 'shutdown': 196, 'startup': 49}
[2026-02-18 16:45:00] [INFO] [REGIME] Regime: quality_ok=False | states={'unknown': 5361} | transient={'trip': 5116, 'shutdown': 196, 'startup': 49}
[2026-02-18 16:45:00] [INFO] [CONFIG_HIST] Logged 1 config changes for RunID=6d60b75f-ee8d-42f1-b33b-b550f17919fa
[2026-02-18 16:45:00] [INFO] [AUTO-TUNE] Auto-tune: 1 adjustments (k_max: 6->8) | refit=next_run
[2026-02-18 16:45:00] [INFO] [OUTPUT] SQL refit request recorded in ACM_RefitRequests
[2026-02-18 16:45:01] [INFO] [CAL] Contamination filter (iterative_mad): excluded 375/5361 samples (7.0%) | retained=4986
[2026-02-18 16:45:01] [DEBUG] [CAL] Extreme threshold (1441.42) - clamping to 1000.0
[2026-02-18 16:45:01] [INFO] [DRIFT] Drift: cusum_z P95=1.502 | trend=0.0242 | fused=-1.185 | mode=FAULT
[2026-02-18 16:45:02] [INFO] [OUTPUT] SQL insert to ACM_DriftController: 1 rows
[2026-02-18 16:45:04] [INFO] [BASELINE] Skipping buffer write (models exist, next refresh in 8 batches)
[2026-02-18 16:45:17] [INFO] [OUTPUT] SQL insert to ACM_Scores_Wide: 5361 rows
[2026-02-18 16:45:17] [INFO] [IO] Scores written: {'sql_written': True, 'rows': 5361, 'inserted': 5361, 'error': None, 'sql_table': 'ACM_Scores_Wide', 'artifact': 'scores'} rows
[2026-02-18 16:45:17] [INFO] [EPISODES] Applied 5 schema repairs to episodes: peak_timestamp_fallback_used, regime_mapped_fallback, dominant_sensor_extracted, severity_calculated, status_defaulted
[2026-02-18 16:45:17] [INFO] [OUTPUT] Auto-flushing batch (rows=5367, age=35.6s)
[2026-02-18 16:45:19] [INFO] [OUTPUT] SQL insert to ACM_EpisodeDiagnostics: 77 rows
[2026-02-18 16:45:22] [INFO] [OUTPUT] SQL insert to ACM_Episodes: 77 rows
[2026-02-18 16:45:22] [INFO] [IO] Episodes written: {'sql_written': True, 'rows': 77, 'inserted': 77, 'error': None, 'sql_table': 'ACM_EpisodeDiagnostics', 'artifact': 'episodes'} rows
[2026-02-18 16:45:23] [INFO] [OUTPUT] SQL insert to ACM_DetectorCorrelation: 9 rows
[2026-02-18 16:45:26] [INFO] [OUTPUT] SQL insert to ACM_SensorCorrelations: 3160 rows
[2026-02-18 16:45:36] [INFO] [OUTPUT] SQL insert to ACM_SensorNormalized_TS: 10125 rows
[2026-02-18 16:45:38] [INFO] [OUTPUT] SQL insert to ACM_SeasonalPatterns: 142 rows
[2026-02-18 16:45:38] [INFO] [ANALYTICS] Generating analytics tables (v11 SQL-only)...
[2026-02-18 16:45:38] [INFO] [OUTPUT] Bulk pre-delete: 3 tables targeted, 3 DELETE statements in 0.04s (batched)
[2026-02-18 16:45:46] [INFO] [OUTPUT] SQL insert to ACM_HealthTimeline: 5361 rows
[2026-02-18 16:45:46] [INFO] [OUTPUT] Auto-flushing batch (rows=5438, age=28.8s)
[2026-02-18 16:45:51] [INFO] [OUTPUT] SQL insert to ACM_RegimeTimeline: 5361 rows
[2026-02-18 16:45:52] [INFO] [OUTPUT] Auto-flushing batch (rows=5361, age=5.3s)
[2026-02-18 16:45:53] [INFO] [OUTPUT] SQL insert to ACM_SensorDefects: 7 rows
[2026-02-18 16:45:59] [INFO] [OUTPUT] SQL insert to ACM_SensorHotspots: 25 rows
[2026-02-18 16:45:59] [INFO] [ANALYTICS] Generated analytics tables (SQL written: 4)
[2026-02-18 16:45:59] [INFO] [OUTPUTS] Analytics: tables=4
[2026-02-18 16:45:59] [INFO] [HealthTracker] Data anchor: 2023-03-07 23:00:00, window cutoff: 2022-12-07 23:00:00 (2160h lookback)
[2026-02-18 16:46:00] [INFO] [HealthTracker] Loaded 7551 health points from SQL (rolling window: 2160h)
[2026-02-18 16:46:02] [WARN] [FORECAST] Data quality issue: Max gap 901.5 hours (threshold 720.0 hours)
[2026-02-18 16:46:02] [INFO] [FORECAST] Data summary: n_samples=7551, dt_hours=0.17, window=2160h
[2026-02-18 16:46:02] [WARN] [FORECAST] GAPPY data detected - proceeding with available data (historical replay mode)
[2026-02-18 16:46:02] [INFO] [STATE] Loaded state: EquipID=5010, StateVersion=1, DataVolume=4301
[2026-02-18 16:46:02] [INFO] [FORECAST] Loaded forecast config: alpha=0.30, beta=0.10, failure_threshold=70.0, horizon=168h
[2026-02-18 16:46:02] [INFO] [FORECAST] Auto-tuning triggered at DataVolume=11852
[2026-02-18 16:46:05] [INFO] [DEGRADE] Restored state: level=59.46, trend=-0.8333/hr, std_error=5.15
[2026-02-18 16:46:05] [INFO] [DEGRADE] Restored state: level=59.46, trend=-0.8333/hr, std_error=5.15
[2026-02-18 16:46:05] [INFO] [FORECAST] Warm-started degradation model from previous state
[2026-02-18 16:46:06] [INFO] [DEGRADE] HEALTH-JUMP: Maintenance reset detected at 2023-03-05 21:40:00. Health jumped 34.9% -> 50.6% (+15.7%). Using 297 post-jump samples for trend fitting.
[2026-02-18 16:46:06] [INFO] [DEGRADE] Detected 50 outliers (robust z > 3.0)
[2026-02-18 16:46:07] [INFO] [DEGRADE] Fitted: level=59.73, trend=0.5115/hr, std_error=0.88, n=297
[2026-02-18 16:46:07] [INFO] [DEGRADE] HEALTH-JUMP: Maintenance reset detected at 2023-03-05 21:40:00. Health jumped 34.9% -> 50.6% (+15.7%). Using 297 post-jump samples for trend fitting.
[2026-02-18 16:46:07] [INFO] [DEGRADE] Detected 50 outliers (robust z > 3.0)
[2026-02-18 16:46:10] [INFO] [DEGRADE] Adaptive smoothing: alpha=0.800, beta=0.010
[2026-02-18 16:46:11] [INFO] [DEGRADE] Fitted: level=59.68, trend=-0.0638/hr, std_error=1.22, n=297
[2026-02-18 16:46:11] [INFO] [DEGRADE] Fitted regime-conditioned model with 1 regimes
[2026-02-18 16:46:11] [INFO] [FORECAST] RUL_P50=0.0h, RUL_Spread=0.0h, RUL_CV=nan, CI_Width=21.96, Health=60.0, N=7551, Quality=GAPPY
[2026-02-18 16:46:11] [INFO] [SENSOR_ATTR] Loaded 25 sensor attributions from SQL
[2026-02-18 16:46:13] [INFO] [OUTPUT] SQL insert to ACM_HealthForecast: 168 rows
[2026-02-18 16:46:15] [INFO] [OUTPUT] SQL insert to ACM_FailureForecast: 168 rows
[2026-02-18 16:46:15] [WARN] [FORECAST] RUL reliability: LEARNING - Model still LEARNING - predictions may be unreliable
[2026-02-18 16:46:17] [INFO] [OUTPUT] SQL insert to ACM_RUL: 1 rows
[2026-02-18 16:46:17] [INFO] [FORECAST] Wrote 3 forecast tables to SQL
[2026-02-18 16:46:18] [DEBUG] [FORECAST] Sensor forecast query: equip=5010, cutoff=2023-02-05 18:20:00, sensors=['sensor_31_std', 'sensor_5_std', 'sensor_18_std']...
[2026-02-18 16:46:19] [DEBUG] [FORECAST] Sensor forecast query returned 1010 rows
[2026-02-18 16:46:31] [INFO] [FORECAST] Generated 1680 sensor forecast points for 10 sensors over 168h
[2026-02-18 16:46:31] [INFO] [OUTPUT] Auto-flushing batch (rows=369, age=39.0s)
[2026-02-18 16:46:34] [INFO] [OUTPUT] SQL insert to ACM_SensorForecast: 1680 rows
[2026-02-18 16:46:34] [INFO] [FORECAST] Wrote sensor forecasts for 25 sensors
[2026-02-18 16:46:35] [WARN] [MultivariateForecast] Insufficient data: 24 < 100
[2026-02-18 16:46:35] [INFO] [FORECAST] Regime context: regime=0, omr_z=-1.7548941373825073, drift_trend=unknown
[2026-02-18 16:46:35] [INFO] [STATE] Saved state for EquipID=5010
[2026-02-18 16:46:35] [INFO] [FORECAST] Forecast: RUL P10/50/90=0/0/0h | tables=4 | top_sensors=sen
[2026-02-18 16:46:36] [INFO] [OUTPUT] Batched transaction committed (85.73s)
[2026-02-18 16:46:37] [INFO] [OUTPUT] SQL insert to ACM_PCA_Models: 1 rows
[2026-02-18 16:46:41] [INFO] [OUTPUT] SQL insert to ACM_PCA_Loadings: 3160 rows
[2026-02-18 16:46:42] [INFO] [OUTPUT] SQL insert to ACM_Run_Stats: 1 rows
[2026-02-18 16:46:56] [INFO] [CULPRITS] Wrote 529 culprit records to ACM_EpisodeCulprits
[2026-02-18 16:46:56] >>> ============================================================
[2026-02-18 16:46:56] >>> [2026-02-18 16:46:56] [DEBUG] [RUN_META] No data quality records found in SQL, defaulting to 100.0
[2026-02-18 16:46:56] [INFO] [RUN_META] Wrote run metadata to ACM_Runs: 6d60b75f-ee8d-42f1-b33b-b550f17919fa
[2026-02-18 16:46:56] [INFO] [RUN] Finalized RunID=6d60b75f-ee8d-42f1-b33b-b550f17919fa outcome=OK rows_in=5361 rows_out=3162
[2026-02-18 16:46:56] [DEBUG] [OUTPUT] OutputManager stats: 12 write_dataframe calls, 0 batch rows, 3.002s avg write time
[2026-02-18 16:46:56] [INFO] [PROFILE] Stopping and pushing profile data...
[2026-02-18 16:47:22] >>> --- Top CPU Functions ---
[2026-02-18 16:47:22] >>>    1. output_manager.OutputManager._bulk_insert_sql: 465574.9ms (27 calls)
[2026-02-18 16:47:22] >>>    2. output_manager.OutputManager.write_table: 449340.5ms (12 calls)
[2026-02-18 16:47:22] >>>    3. generic.DataFrame.replace: 436668.6ms (111 calls)
[2026-02-18 16:47:22] >>>    4. base.BlockManager.replace_list: 436262.4ms (85 calls)
[2026-02-18 16:47:22] >>>    5. blocks.NumpyBlock.replace_list: 435403.0ms (413 calls)
[2026-02-18 16:47:22] >>>    6. blocks.<genexpr>: 431918.6ms (624 calls)
[2026-02-18 16:47:22] >>>    7. missing.mask_missing: 431903.0ms (440 calls)
[2026-02-18 16:47:22] >>>    8. output_manager.OutputManager.write_detector_correlation: 430168.6ms (1 calls)
[2026-02-18 16:47:22] >>>    9. masked.BooleanArray.to_numpy: 429856.1ms (178 calls)
[2026-02-18 16:47:22] >>>   10. generic.Series.fillna: 110171.9ms (5834 calls)
[2026-02-18 16:47:24] [INFO] [PROFILE] Pushing cpu (2577 stacks) to Pyroscope...
[2026-02-18 16:47:24] [SUCCESS] [PROFILE] cpu profile pushed successfully
[2026-02-18 16:47:26] [INFO] [PROFILE] Pushing alloc_objects (500 stacks) to Pyroscope...
[2026-02-18 16:47:26] [SUCCESS] [PROFILE] alloc_objects profile pushed successfully
[2026-02-18 16:47:27] [INFO] [PROFILE] Pushing alloc_space (500 stacks) to Pyroscope...
[2026-02-18 16:47:27] [SUCCESS] [PROFILE] alloc_space profile pushed successfully
[2026-02-18 16:47:27] [SUCCESS] [PROFILE] Profile data pushed to Pyroscope
[2026-02-18 16:47:30] >>> --- Timer Summary ---
[2026-02-18 16:47:30] >>> models.quality_check            92.596s ( 16.1%)
[2026-02-18 16:47:30] >>> persist                         85.766s ( 15.0%)
[2026-02-18 16:47:30] >>> calibrate                       52.164s (  9.1%)
[2026-02-18 16:47:30] >>> features.build                  47.061s (  8.2%)
[2026-02-18 16:47:30] >>> seasonality.detect              46.288s (  8.1%)
[2026-02-18 16:47:30] >>> regimes.label                   44.518s (  7.8%)
[2026-02-18 16:47:30] >>> features.impute                 41.782s (  7.3%)
[2026-02-18 16:47:30] >>> outputs.forecasting             36.341s (  6.3%)
[2026-02-18 16:47:30] >>> score.detector_score            23.360s (  4.1%)
[2026-02-18 16:47:30] >>> outputs.comprehensive_analytics  21.317s (  3.7%)
[2026-02-18 16:47:30] >>> load_data                       18.364s (  3.2%)
[2026-02-18 16:47:30] >>> models.load                     13.616s (  2.4%)
[2026-02-18 16:47:30] >>> sql.culprits                    13.605s (  2.4%)
[2026-02-18 16:47:30] >>> fusion                          13.108s (  2.3%)
[2026-02-18 16:47:30] >>> models.persistence.save         11.237s (  2.0%)
[2026-02-18 16:47:30] >>> persist.sensor_normalized_ts     9.586s (  1.7%)
[2026-02-18 16:47:30] >>> data.guardrails                  7.328s (  1.3%)
[2026-02-18 16:47:30] >>> persist.write_scores             7.216s (  1.3%)
[2026-02-18 16:47:30] >>> sensor.context                   5.811s (  1.0%)
[2026-02-18 16:47:30] >>> sql.pca                          5.719s (  1.0%)
[2026-02-18 16:47:30] >>> persist.write_episodes           4.778s (  0.8%)
[2026-02-18 16:47:30] >>> regimes.transient_detection      3.350s (  0.6%)
[2026-02-18 16:47:30] >>> persist.sensor_correlation       3.132s (  0.5%)
[2026-02-18 16:47:30] >>> features.hash                    3.069s (  0.5%)
[2026-02-18 16:47:30] >>> persist.seasonal_patterns        1.752s (  0.3%)
[2026-02-18 16:47:30] >>> regimes.occupancy                1.594s (  0.3%)
[2026-02-18 16:47:30] >>> drift                            1.561s (  0.3%)
[2026-02-18 16:47:30] >>> data.contract                    1.538s (  0.3%)
[2026-02-18 16:47:30] >>> persist.detector_correlation     0.971s (  0.2%)
[2026-02-18 16:47:30] >>> drift.controller                 0.854s (  0.1%)
[2026-02-18 16:47:30] >>> sql.run_stats                    0.582s (  0.1%)
[2026-02-18 16:47:30] >>> startup                          0.332s (  0.1%)
[2026-02-18 16:47:30] >>> baseline.seed                    0.139s (  0.0%)
[2026-02-18 16:47:30] >>> models.refit_flag                0.061s (  0.0%)
[2026-02-18 16:47:30] >>> baseline.buffer_write            0.045s (  0.0%)
[2026-02-18 16:47:30] >>> thresholds.adaptive              0.021s (  0.0%)
[2026-02-18 16:47:30] >>> contribution.timeline            0.021s (  0.0%)
[2026-02-18 16:47:30] >>> total_run                      573.621s

[2026-02-18 16:47:30] [INFO] [QA] Inspecting outputs for EquipID=5010, RunID=6D60B75F-EE8D-42F1-B33B-B550F17919FA (from ACM_Runs), window=[2026-02-18 11:07:58.293808,2026-02-18 11:16:56.750000)
[2026-02-18 16:47:30] [INFO] [QA] ACM_Scores_Wide: 5361 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:30] [INFO] [QA] ACM_HealthTimeline: 5361 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_RegimeTimeline: 5361 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_EpisodeDiagnostics: 77 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_Episodes: 77 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_EpisodeMetrics: 0 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_SensorNormalized_TS: 10125 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_SensorCorrelations: 3160 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_DetectorCorrelation: 9 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_SeasonalPatterns: 142 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_HealthForecast: 168 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_FailureForecast: 168 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_RUL: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_DriftController: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_RegimeDefinitions: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_RegimeOccupancy: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_Run_Stats: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_PCA_Models: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_PCA_Loadings: 3160 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_PCA_Metrics: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_SensorHotspots: 25 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [INFO] [QA] ACM_SensorDefects: 7 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:47:31] [SUCCESS] [BATCH] WFA_TURBINE_10: Batch 1 completed (outcome=OK)
[2026-02-18 16:47:31] [INFO] [BATCH]
WFA_TURBINE_10: Batch 2/4 - [2023-03-07 23:04:00 to 2023-05-21 18:15:59]
[2026-02-18 16:47:31] [INFO] [RUN] C:\Users\bhadk\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe -m core.acm_main --equip WFA_TURBINE_10 --start-time 2023-03-07T23:04:00 --end-time 2023-05-21T18:15:59
[2026-02-18 16:47:31] [INFO] [BATCH] WFA_TURBINE_10: Batch 2 - scoring with existing models
[2026-02-18 16:47:34] [SUCCESS] [OTEL] Loki logs -> http://localhost:3100
[2026-02-18 16:47:34] [SUCCESS] [OTEL] Profiling -> http://localhost:4040 [cpu (yappi), memory (tracemalloc)]
[2026-02-18 16:47:34] [SUCCESS] [OTEL] Traces -> http://localhost:4318/v1/traces
[2026-02-18 16:47:34] [SUCCESS] [OTEL] Metrics -> http://localhost:4318/v1/metrics
[2026-02-18 16:47:34] [INFO] [PROFILE] Started CPU profiling
[2026-02-18 16:47:34] [INFO] [SQL] Connecting to SQL Server...
[2026-02-18 16:47:35] [SUCCESS] [SQL] SQL connection established
[2026-02-18 16:47:35] [INFO] [CONFIG] Config loaded from SQL for WFA_TURBINE_10 (EquipID=5010, 265 params)
[2026-02-18 16:47:35] [SUCCESS] [OTEL] SQL log persistence enabled -> ACM_RunLogs
[2026-02-18 16:47:35] [INFO] [RUN] Run #3 | WFA_TURBINE_10 | adaptive | continuous_learning=True | force_retrain=False | intervals=model:1,thresh:1
[2026-02-18 16:47:35] [INFO] [RUN] Run started: WFA_TURBINE_10 (ID=5010) | RunID=be10426a | window=[2025-12-05 16:05:35.811969+00:00,2026-02-18 11:17:35.811969+00:00) | tick=107712m
[2026-02-18 16:47:35] [INFO] [RUN] CLI overrides: start=2023-03-07 23:04:00, end=2023-05-21 18:15:59
[2026-02-18 16:47:35] [INFO] [OUTPUT] Manager initialized (batch_size=5000, batching=ON, sql_cache=60.0s, io_workers=8, flush=1000 rows/30.0s, max_futures=50)
[2026-02-18 16:47:35] [INFO] [DATA] Loading from SQL historian: WFA_TURBINE_10
[2026-02-18 16:47:35] [INFO] [DATA] Time range: 2023-03-07 23:04:00 to 2023-05-21 18:15:59
[2026-02-18 16:47:51] [INFO] [DATA] Retrieved 10765 rows from SQL historian
[2026-02-18 16:47:51] [INFO] [DATA] BATCH MODE: All 10765 rows allocated to scoring (baseline from cache)
[2026-02-18 16:47:52] [INFO] [DATA] BATCH MODE: Train empty (baseline_buffer later), using 81 score columns
[2026-02-18 16:47:52] [INFO] [DATA] Kept 81 numeric columns, dropped 0 non-numeric
[2026-02-18 16:47:52] >>> Checking cadence and resampling for 10765 score rows...
[2026-02-18 16:47:52] >>>   Checking train cadence...
[2026-02-18 16:47:52] >>>   Checking score cadence...
[2026-02-18 16:47:52] >>>   Cadence check complete: train=True, score=True
[2026-02-18 16:47:52] [INFO] [DATA] Cadence: native=600.0s, requested=auto, will_resample=False
[2026-02-18 16:47:53] [INFO] [DATA] SQL historian load complete: 0 train + 10765 score = 10765 total rows
[2026-02-18 16:47:54] [INFO] [OUTPUT] SQL insert to ACM_DataContractValidation: 1 rows
[2026-02-18 16:47:54] [INFO] [DATA] timestamp=EntryDateTime cadence_ok=True kept=81 drop=0 tz_stripped=0 future_drop=0 dup_removed=0
[2026-02-18 16:47:54] [INFO] [TIMER] data_split_complete  train_rows=0 train_cols=81 score_rows=10765 score_cols=81
[2026-02-18 16:47:54] >>> CHECKPOINT 1: Data loading complete, about to start baseline seeding
[2026-02-18 16:47:55] >>> CHECKPOINT 2: Entering baseline.seed section for WFA_TURBINE_10...
[2026-02-18 16:47:55] >>> CHECKPOINT 3: About to call seed_baseline() function
[2026-02-18 16:47:55] [INFO] [BASELINE] Baseline: score split (train=5382, no overlap) | extended=False
[2026-02-18 16:48:31] [INFO] [SEASON] Seasonal: 70 patterns in 63 sensors | adjusted=True
[2026-02-18 16:48:31] [WARN] [DATA] 2 low-variance sensor(s) in TRAIN (std<0.0001): sensor_46, sensor_49
[2026-02-18 16:48:32] [INFO] [DATA] Persisted 0 new low-variance sensors for permanent exclusion.
[2026-02-18 16:48:36] [INFO] [OUTPUT] Auto-flushing batch (rows=0, age=60.5s)
[2026-02-18 16:48:39] [INFO] [OUTPUT] SQL insert to ACM_DataQuality: 1 rows
[2026-02-18 16:48:39] [INFO] [FEAT] Building features with window=16
[2026-02-18 16:48:39] [INFO] [FEAT] Computed 81 fill values from training data
[2026-02-18 16:49:27] [INFO] [FEAT] Features built: train=(5382, 648), score=(5383, 648)
[2026-02-18 16:49:27] [INFO] [FEAT] Features built: train=(5382, 648), score=(5383, 648)
[2026-02-18 16:50:10] [WARN] [FEAT] Dropping 16 columns (0 NaN, 16 low-var)
[2026-02-18 16:50:11] [INFO] [OUTPUT] SQL insert to ACM_FeatureDropLog: 16 rows
[2026-02-18 16:50:14] [WARN] [MODEL] SQL refit request found: id=469 at 2026-02-18 16:45:00.212572
[2026-02-18 16:50:14] [INFO] [MODEL-LOAD] Loading cached models for equip=WFA_TURBINE_10, equip_id=5010
[2026-02-18 16:50:14] [INFO] [MODEL-SQL] Loading models from SQL ModelRegistry v2...
[2026-02-18 16:50:16] [INFO] [MODEL-SQL] - Loaded ar1_params (34,392 bytes)
[2026-02-18 16:50:16] [INFO] [MODEL-SQL] - Loaded calibration_params (600 bytes)
[2026-02-18 16:50:16] [INFO] [MODEL-SQL] - Loaded gmm_model (62,263 bytes)
[2026-02-18 16:50:25] [INFO] [MODEL-SQL] - Loaded iforest_model (4,149,369 bytes)
[2026-02-18 16:50:26] [INFO] [MODEL-SQL] - Loaded omr_model (4,267,274 bytes)
[2026-02-18 16:50:26] [INFO] [MODEL-SQL] - Loaded pca_model (31,391 bytes)
[2026-02-18 16:50:26] [INFO] [MODEL-SQL] [OK] Loaded 6/6 models from SQL ModelRegistry v2
[2026-02-18 16:50:26] [INFO] [MODEL] [OK] Loaded from SQL ModelRegistry successfully
[2026-02-18 16:50:26] [INFO] [MODEL-LOAD] Load result: models=True, manifest=True
[2026-02-18 16:50:26] [INFO] [MODEL] Using cached models v2: sensors=632 | sig=96c15b58c09d1cbb...
[2026-02-18 16:50:27] [INFO] [CAL] Loaded cached calibration params (6 detectors)
[2026-02-18 16:50:27] [INFO] [REGIME_STATE] Loaded state v1 from SQL (EquipID=5010)
[2026-02-18 16:50:27] [INFO] [REGIME] Using 21 raw operational sensors for regime clustering: ['power_29_avg', 'power_29_max', 'power_29_min', 'power_29_std', 'power_30_avg']...
[2026-02-18 16:50:53] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=5383
[2026-02-18 16:50:53] [INFO] [LIFECYCLE] Model maturity: LEARNING
[2026-02-18 16:50:53] [INFO] [REGIME] Using HDBSCAN clustering (primary method)
[2026-02-18 16:50:54] [INFO] [REGIME] HDBSCAN config: min_cluster_size=30, min_samples=3, method=eom, metric=euclidean
[2026-02-18 16:51:16] [INFO] [REGIME] HDBSCAN found 1 clusters, 490 noise points (9.1%)
[2026-02-18 16:51:56] [INFO] [REGIME] HDBSCAN complete: 1 clusters, validity=0.335 (dbcv)
[2026-02-18 16:52:01] [INFO] [REGIME] ENSEMBLE: GMM fallback fitted with k=1 for noise point assignment
[2026-02-18 16:52:04] [INFO] [REGIME] Training distance threshold (P95): 6.4721 (range: 1.6406 - 7.8976)
[2026-02-18 16:52:17] [INFO] [REGIME] Assigned 5349/5382 low-strength points to nearest cluster
[2026-02-18 16:52:34] [INFO] [REGIME] Identified 5380/5383 novel points (assigned to nearest cluster)
[2026-02-18 16:52:34] [INFO] [REGIME_STATE] Saved state v1 to ACM_RegimeState (EquipID=5010)
[2026-02-18 16:52:34] [INFO] [REGIME_STATE] Regime state: saved_v1 | K=1
[2026-02-18 16:52:35] [INFO] [OUTPUT] SQL insert to ACM_RegimeDefinitions: 1 rows
[2026-02-18 16:52:35] [INFO] [REGIME] Wrote 1 regime definitions for audit
[2026-02-18 16:52:36] [INFO] [OUTPUT] SQL insert to ACM_RegimeOccupancy: 1 rows
[2026-02-18 16:52:37] [INFO] [REGIME] Regime analysis: occupancy=1 | transitions=0
[2026-02-18 16:52:37] [WARN] [MODEL] Forcing retraining: regime_quality_ok=False (metric=dbcv, score=0.335)
[2026-02-18 16:52:47] [WARN] [AR1] 50 columns with phi clamped to +/-0.999
[2026-02-18 16:52:47] [INFO] [PCA] Fit start: train shape=(5382, 632)
[2026-02-18 16:52:57] [INFO] [PCA] Fit complete in Span: 5 components, 5382 samples, 632 features
[2026-02-18 16:53:36] [INFO] [GMM] BIC search selected k=3
[2026-02-18 16:53:38] [INFO] [GMM] Fitted k=3, cov=diag, reg=0.001
[2026-02-18 16:54:01] [INFO] [OMR] Selected model type: PLS
[2026-02-18 16:54:02] [INFO] [OMR] Fitted PLS model: 5382 samples, 632 features, 5 components, std=4.011
[2026-02-18 16:54:02] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=325.8s)
[2026-02-18 16:54:03] [INFO] [OUTPUT] SQL insert to ACM_OMR_Diagnostics: 1 rows
[2026-02-18 16:54:03] [INFO] [FIT] Fitted 5 detectors in 85.84s: AR1, PCA(5c), IForest(100), GMM(1), OMR(632f) | samples=5382
[2026-02-18 16:54:04] [INFO] [MODEL] Saving models to SQL ModelRegistry v3
[2026-02-18 16:54:04] [INFO] [MODEL-SQL] Saving models to SQL ModelRegistry v3...
[2026-02-18 16:54:07] [INFO] [MODEL-SQL] - Saved ar1_params (34,392 bytes)
[2026-02-18 16:54:07] [INFO] [MODEL-SQL] - Saved pca_model (31,391 bytes)
[2026-02-18 16:54:11] [INFO] [MODEL-SQL] - Saved iforest_model (4,415,481 bytes)
[2026-02-18 16:54:11] [INFO] [MODEL-SQL] - Saved gmm_model (62,111 bytes)
[2026-02-18 16:54:13] [INFO] [MODEL-SQL] - Saved omr_model (4,270,610 bytes)
[2026-02-18 16:54:13] [DEBUG] [MODEL-SQL] - Skipping None model: regime_model
[2026-02-18 16:54:13] [DEBUG] [MODEL-SQL] - Skipping None model: feature_medians
[2026-02-18 16:54:13] [DEBUG] [MODEL-SQL] - Skipping None model: calibration_params
[2026-02-18 16:54:13] [INFO] [MODEL-SQL] OK Committed 5/8 models to SQL ModelRegistry v3
[2026-02-18 16:54:13] [INFO] [MODEL] Saved 8 models to SQL ModelRegistry v3
[2026-02-18 16:54:13] [INFO] [MODEL] Saved all trained models to version v3
[2026-02-18 16:54:13] [INFO] [LIFECYCLE] Model v1 promoted to CONVERGED
[2026-02-18 16:54:14] [INFO] [OUTPUT] SQL insert to ACM_RegimePromotionLog: 1 rows
[2026-02-18 16:54:14] [SUCCESS] [LIFECYCLE] Model promoted: LEARNING->CONVERGED (runs=3, days=119.8)
[2026-02-18 16:54:14] [INFO] [LIFECYCLE] Model state v1: CONVERGED
[2026-02-18 16:54:16] [INFO] [OUTPUT] SQL insert to ACM_ActiveModels: 1 rows
[2026-02-18 16:54:16] [INFO] [OUTPUT] OutputManager maturity_state set to CONVERGED
[2026-02-18 16:54:16] [INFO] [LIFECYCLE] Model state: CONVERGED
[2026-02-18 16:55:07] [INFO] [SCORE] Scored 5 detectors: AR1, PCA(cached), IForest, GMM, OMR | samples=5382
[2026-02-18 16:55:07] [INFO] [CAL] Using cached calibration for 6 detectors (training-anchored)
[2026-02-18 16:55:07] [INFO] [CAL] Saved calibration params (6 detectors, 600 bytes) to v3
[2026-02-18 16:55:07] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=65.4s)
[2026-02-18 16:55:08] [INFO] [OUTPUT] SQL insert to ACM_CalibrationSummary: 6 rows
[2026-02-18 16:55:08] [INFO] [CAL] Calibration complete: q=0.98 | clip_z=30.12 | detectors=6 | thresholds=6 | per_regime=0 | summary=6
[2026-02-18 16:55:08] [INFO] [FUSE] CUSUM auto-tuned: k_sigma=2.000->0.800, h_sigma=12.000->3.000 (spread_ratio=1.41)
[2026-02-18 16:55:08] [WARN] [TUNE] gmm_z: all same sign - limited separability
[2026-02-18 16:55:08] [WARN] [TUNE] iforest_z: all same sign - limited separability
[2026-02-18 16:55:08] [WARN] [TUNE] pca_spe_z: all same sign - limited separability
[2026-02-18 16:55:08] [WARN] [TUNE] pca_t2_z: all same sign - limited separability
[2026-02-18 16:55:08] [WARN] [TUNE] Excessive weight drift for gmm_z: 0.050 -> 0.086 (drift=72.2% > 20.0%). Rejecting tune.
[2026-02-18 16:55:09] [INFO] [OUTPUT] Saved fusion metrics -> SQL:ACM_RunMetrics (18 records)
[2026-02-18 16:55:19] [INFO] [FUSE] Fusion: detectors=6 | episodes=0 | auto_tuned=True
[2026-02-18 16:55:19] [INFO] [TRANSIENT] Using 168 operating-variable columns for transient detection; excluded 464 condition-indicator columns
[2026-02-18 16:55:22] [INFO] [TRANSIENT] State distribution: {'trip': 5290, 'shutdown': 78, 'startup': 15}
[2026-02-18 16:55:22] [INFO] [REGIME] Regime: quality_ok=False | states={'unknown': 5383} | transient={'trip': 5290, 'shutdown': 78, 'startup': 15}
[2026-02-18 16:55:23] [INFO] [CONFIG_HIST] Logged 1 config changes for RunID=be10426a-7bbf-4a74-9a6e-6c2e77e53b67
[2026-02-18 16:55:23] [INFO] [AUTO-TUNE] Auto-tune: 1 adjustments (k_max: 6->8) | refit=next_run
[2026-02-18 16:55:23] [INFO] [OUTPUT] SQL refit request recorded in ACM_RefitRequests
[2026-02-18 16:55:24] [INFO] [DRIFT] Drift: cusum_z P95=0.783 | trend=-0.0012 | fused=-0.748 | mode=FAULT
[2026-02-18 16:55:25] [INFO] [OUTPUT] SQL insert to ACM_DriftController: 1 rows
[2026-02-18 16:55:26] [INFO] [BASELINE] Skipping buffer write (models exist, next refresh in 7 batches)
[2026-02-18 16:55:38] [INFO] [OUTPUT] SQL insert to ACM_Scores_Wide: 5383 rows
[2026-02-18 16:55:38] [INFO] [IO] Scores written: {'sql_written': True, 'rows': 5383, 'inserted': 5383, 'error': None, 'sql_table': 'ACM_Scores_Wide', 'artifact': 'scores'} rows
[2026-02-18 16:55:39] [INFO] [OUTPUT] SQL insert to ACM_DetectorCorrelation: 9 rows
[2026-02-18 16:55:42] [INFO] [OUTPUT] SQL insert to ACM_SensorCorrelations: 3160 rows
[2026-02-18 16:55:52] [INFO] [OUTPUT] SQL insert to ACM_SensorNormalized_TS: 10206 rows
[2026-02-18 16:55:54] [INFO] [OUTPUT] SQL insert to ACM_SeasonalPatterns: 70 rows
[2026-02-18 16:55:54] [INFO] [ANALYTICS] Generating analytics tables (v11 SQL-only)...
[2026-02-18 16:55:54] [INFO] [OUTPUT] Bulk pre-delete: 3 tables targeted, 3 DELETE statements in 0.04s (batched)
[2026-02-18 16:55:55] [INFO] [OUTPUT] Auto-flushing batch (rows=5389, age=48.2s)
[2026-02-18 16:56:01] [INFO] [OUTPUT] SQL insert to ACM_HealthTimeline: 5383 rows
[2026-02-18 16:56:02] [INFO] [OUTPUT] Auto-flushing batch (rows=5383, age=6.4s)
[2026-02-18 16:56:07] [INFO] [OUTPUT] SQL insert to ACM_RegimeTimeline: 5383 rows
[2026-02-18 16:56:07] [INFO] [OUTPUT] Auto-flushing batch (rows=5383, age=5.6s)
[2026-02-18 16:56:08] [INFO] [OUTPUT] SQL insert to ACM_SensorDefects: 7 rows
[2026-02-18 16:56:14] [INFO] [OUTPUT] SQL insert to ACM_SensorHotspots: 25 rows
[2026-02-18 16:56:14] [INFO] [ANALYTICS] Generated analytics tables (SQL written: 4)
[2026-02-18 16:56:15] [INFO] [OUTPUTS] Analytics: tables=4
[2026-02-18 16:56:15] [INFO] [HealthTracker] Data anchor: 2023-05-21 18:10:00, window cutoff: 2023-02-20 18:10:00 (2160h lookback)
[2026-02-18 16:56:16] [INFO] [HealthTracker] Loaded 7573 health points from SQL (rolling window: 2160h)
[2026-02-18 16:56:18] [WARN] [FORECAST] Data quality issue: Max gap 898.2 hours (threshold 720.0 hours)
[2026-02-18 16:56:18] [INFO] [FORECAST] Data summary: n_samples=7573, dt_hours=0.17, window=2160h
[2026-02-18 16:56:18] [WARN] [FORECAST] GAPPY data detected - proceeding with available data (historical replay mode)
[2026-02-18 16:56:18] [INFO] [STATE] Loaded state: EquipID=5010, StateVersion=1, DataVolume=11852
[2026-02-18 16:56:18] [INFO] [FORECAST] Loaded forecast config: alpha=0.30, beta=0.10, failure_threshold=70.0, horizon=168h
[2026-02-18 16:56:18] [INFO] [FORECAST] Auto-tuning triggered at DataVolume=19425
[2026-02-18 16:56:21] [INFO] [DEGRADE] Restored state: level=59.73, trend=0.5115/hr, std_error=0.88
[2026-02-18 16:56:21] [INFO] [DEGRADE] Restored state: level=59.68, trend=-0.0638/hr, std_error=1.22
[2026-02-18 16:56:21] [INFO] [FORECAST] Warm-started degradation model from previous state
[2026-02-18 16:56:22] [INFO] [DEGRADE] HEALTH-JUMP: Maintenance reset detected at 2023-04-14 09:20:00. Health jumped 23.5% -> 41.5% (+18.0%). Using 5382 post-jump samples for trend fitting.
[2026-02-18 16:56:22] [INFO] [DEGRADE] Detected 6 outliers (robust z > 3.0)
[2026-02-18 16:56:37] [INFO] [DEGRADE] Fitted: level=89.12, trend=0.0000/hr, std_error=0.00, n=5382
[2026-02-18 16:56:37] [INFO] [DEGRADE] HEALTH-JUMP: Maintenance reset detected at 2023-04-14 09:20:00. Health jumped 23.5% -> 41.5% (+18.0%). Using 5382 post-jump samples for trend fitting.
[2026-02-18 16:56:37] [INFO] [DEGRADE] Detected 6 outliers (robust z > 3.0)
[2026-02-18 16:57:02] [INFO] [DEGRADE] Adaptive smoothing: alpha=0.800, beta=0.080
[2026-02-18 16:57:17] [INFO] [DEGRADE] Fitted: level=89.12, trend=0.0000/hr, std_error=0.06, n=5382
[2026-02-18 16:57:17] [INFO] [DEGRADE] Fitted regime-conditioned model with 1 regimes
[2026-02-18 16:57:18] [INFO] [RUL] RUL estimate: P50=168.0h, P10=163.0h, P90=173.0h, mean=168.0h, std=0.0h, failure_prob=0.000
[2026-02-18 16:57:18] [INFO] [FORECAST] RUL_P50=168.0h, RUL_Spread=10.0h, RUL_CV=0.00, CI_Width=4.05, Health=89.1, N=7573, Quality=GAPPY
[2026-02-18 16:57:18] [INFO] [SENSOR_ATTR] Loaded 25 sensor attributions from SQL
[2026-02-18 16:57:18] [INFO] [OUTPUT] Auto-flushing batch (rows=32, age=70.9s)
[2026-02-18 16:57:20] [INFO] [OUTPUT] SQL insert to ACM_HealthForecast: 168 rows
[2026-02-18 16:57:22] [INFO] [OUTPUT] SQL insert to ACM_FailureForecast: 168 rows
[2026-02-18 16:57:24] [INFO] [OUTPUT] SQL insert to ACM_RUL: 1 rows
[2026-02-18 16:57:24] [INFO] [FORECAST] Wrote 3 forecast tables to SQL
[2026-02-18 16:57:25] [DEBUG] [FORECAST] Sensor forecast query: equip=5010, cutoff=2023-04-21 17:00:00, sensors=['sensor_5_min', 'sensor_31_std', 'sensor_5_std']...
[2026-02-18 16:57:25] [DEBUG] [FORECAST] Sensor forecast query returned 1010 rows
[2026-02-18 16:57:37] [INFO] [FORECAST] Generated 1680 sensor forecast points for 10 sensors over 168h
[2026-02-18 16:57:41] [INFO] [OUTPUT] SQL insert to ACM_SensorForecast: 1680 rows
[2026-02-18 16:57:41] [INFO] [FORECAST] Wrote sensor forecasts for 25 sensors
[2026-02-18 16:57:42] [WARN] [MultivariateForecast] Insufficient data: 24 < 100
[2026-02-18 16:57:42] [INFO] [FORECAST] Regime context: regime=0, omr_z=-0.7475934028625488, drift_trend=unknown
[2026-02-18 16:57:42] [INFO] [STATE] Saved state for EquipID=5010
[2026-02-18 16:57:42] [INFO] [FORECAST] Forecast: RUL P10/50/90=163/168/173h | tables=4 | top_sensors=sen
[2026-02-18 16:57:42] [INFO] [OUTPUT] Batched transaction committed (131.30s)
[2026-02-18 16:57:43] [INFO] [OUTPUT] SQL insert to ACM_PCA_Models: 1 rows
[2026-02-18 16:57:47] [INFO] [OUTPUT] SQL insert to ACM_PCA_Loadings: 3160 rows
[2026-02-18 16:57:48] [INFO] [OUTPUT] SQL insert to ACM_Run_Stats: 1 rows
[2026-02-18 16:57:49] >>> ============================================================
[2026-02-18 16:57:49] >>> [2026-02-18 16:57:49] [DEBUG] [RUN_META] No data quality records found in SQL, defaulting to 100.0
[2026-02-18 16:57:49] [INFO] [RUN_META] Wrote run metadata to ACM_Runs: be10426a-7bbf-4a74-9a6e-6c2e77e53b67
[2026-02-18 16:57:49] [INFO] [RUN] Finalized RunID=be10426a-7bbf-4a74-9a6e-6c2e77e53b67 outcome=OK rows_in=5383 rows_out=3162
[2026-02-18 16:57:49] [DEBUG] [OUTPUT] OutputManager stats: 11 write_dataframe calls, 0 batch rows, 3.060s avg write time
[2026-02-18 16:57:49] [INFO] [PROFILE] Stopping and pushing profile data...
[2026-02-18 16:58:14] >>> --- Top CPU Functions ---
[2026-02-18 16:58:14] >>>    1. frame.DataFrame.__setitem__: 468637.4ms (4866 calls)
[2026-02-18 16:58:14] >>>    2. frame.DataFrame._set_item: 466090.5ms (4866 calls)
[2026-02-18 16:58:14] >>>    3. frame.DataFrame._set_item_mgr: 456918.6ms (4866 calls)
[2026-02-18 16:58:14] >>>    4. managers.BlockManager.insert: 430731.1ms (88 calls)
[2026-02-18 16:58:14] >>>    5. warnings.filterwarnings: 430699.9ms (1458 calls)
[2026-02-18 16:58:14] >>>    6. __init__.compile: 430403.0ms (1402 calls)
[2026-02-18 16:58:14] >>>    7. detector_orchestrator.calibrate_all_detectors: 429653.0ms (1 calls)
[2026-02-18 16:58:14] >>>    8. generic.Series.fillna: 111296.9ms (5831 calls)
[2026-02-18 16:58:14] >>>    9. regimes.label: 97265.6ms (1 calls)
[2026-02-18 16:58:14] >>>   10. forecast_engine.ForecastEngine.run_forecast: 85093.8ms (1 calls)
[2026-02-18 16:58:16] [INFO] [PROFILE] Pushing cpu (2494 stacks) to Pyroscope...
[2026-02-18 16:58:16] [SUCCESS] [PROFILE] cpu profile pushed successfully
[2026-02-18 16:58:18] [INFO] [PROFILE] Pushing alloc_objects (500 stacks) to Pyroscope...
[2026-02-18 16:58:18] [SUCCESS] [PROFILE] alloc_objects profile pushed successfully
[2026-02-18 16:58:19] [INFO] [PROFILE] Pushing alloc_space (500 stacks) to Pyroscope...
[2026-02-18 16:58:19] [SUCCESS] [PROFILE] alloc_space profile pushed successfully
[2026-02-18 16:58:19] [SUCCESS] [PROFILE] Profile data pushed to Pyroscope
[2026-02-18 16:58:22] >>> --- Timer Summary ---
[2026-02-18 16:58:22] >>> persist                        131.341s ( 20.3%)
[2026-02-18 16:58:22] >>> regimes.label                  102.100s ( 15.8%)
[2026-02-18 16:58:22] >>> outputs.forecasting             87.318s ( 13.5%)
[2026-02-18 16:58:22] >>> models.quality_check            85.922s ( 13.3%)
[2026-02-18 16:58:22] >>> calibrate                       52.099s (  8.0%)
[2026-02-18 16:58:22] >>> features.build                  48.531s (  7.5%)
[2026-02-18 16:58:22] >>> features.impute                 43.481s (  6.7%)
[2026-02-18 16:58:22] >>> seasonality.detect              36.222s (  5.6%)
[2026-02-18 16:58:22] >>> score.detector_score            25.032s (  3.9%)
[2026-02-18 16:58:22] >>> outputs.comprehensive_analytics  20.736s (  3.2%)
[2026-02-18 16:58:22] >>> load_data                       18.986s (  2.9%)
[2026-02-18 16:58:22] >>> models.load                     13.203s (  2.0%)
[2026-02-18 16:58:22] >>> models.persistence.save         12.789s (  2.0%)
[2026-02-18 16:58:22] >>> fusion                          10.709s (  1.7%)
[2026-02-18 16:58:22] >>> persist.sensor_normalized_ts     9.857s (  1.5%)
[2026-02-18 16:58:22] >>> data.guardrails                  7.622s (  1.2%)
[2026-02-18 16:58:22] >>> persist.write_scores             7.266s (  1.1%)
[2026-02-18 16:58:22] >>> sql.pca                          5.688s (  0.9%)
[2026-02-18 16:58:22] >>> sensor.context                   4.522s (  0.7%)
[2026-02-18 16:58:22] >>> regimes.transient_detection      3.448s (  0.5%)
[2026-02-18 16:58:22] >>> persist.sensor_correlation       3.032s (  0.5%)
[2026-02-18 16:58:22] >>> features.hash                    2.870s (  0.4%)
[2026-02-18 16:58:22] >>> data.contract                    1.645s (  0.3%)
[2026-02-18 16:58:22] >>> regimes.occupancy                1.634s (  0.3%)
[2026-02-18 16:58:22] >>> persist.seasonal_patterns        1.570s (  0.2%)
[2026-02-18 16:58:22] >>> drift                            1.562s (  0.2%)
[2026-02-18 16:58:22] >>> persist.detector_correlation     0.917s (  0.1%)
[2026-02-18 16:58:22] >>> drift.controller                 0.805s (  0.1%)
[2026-02-18 16:58:22] >>> sql.run_stats                    0.580s (  0.1%)
[2026-02-18 16:58:22] >>> startup                          0.341s (  0.1%)
[2026-02-18 16:58:22] >>> baseline.seed                    0.095s (  0.0%)
[2026-02-18 16:58:22] >>> models.refit_flag                0.048s (  0.0%)
[2026-02-18 16:58:22] >>> baseline.buffer_write            0.044s (  0.0%)
[2026-02-18 16:58:22] >>> persist.write_episodes           0.023s (  0.0%)
[2026-02-18 16:58:22] >>> thresholds.adaptive              0.022s (  0.0%)
[2026-02-18 16:58:22] >>> contribution.timeline            0.021s (  0.0%)
[2026-02-18 16:58:22] >>> sql.culprits                     0.021s (  0.0%)
[2026-02-18 16:58:22] >>> total_run                      647.985s

[2026-02-18 16:58:22] [INFO] [QA] Inspecting outputs for EquipID=5010, RunID=BE10426A-7BBF-4A74-9A6E-6C2E77E53B67 (from ACM_Runs), window=[2026-02-18 11:17:35.818465,2026-02-18 11:27:49.470000)
[2026-02-18 16:58:22] [INFO] [QA] ACM_Scores_Wide: 5383 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:22] [INFO] [QA] ACM_HealthTimeline: 5383 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:22] [INFO] [QA] ACM_RegimeTimeline: 5383 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:22] [INFO] [QA] ACM_EpisodeDiagnostics: 0 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:22] [WARN] [QA] QA check failed: ACM_EpisodeDiagnostics has 0 rows for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:22] [INFO] [QA] ACM_Episodes: 0 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:22] [INFO] [QA] ACM_EpisodeMetrics: 0 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:22] [INFO] [QA] ACM_SensorNormalized_TS: 10206 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_SensorCorrelations: 3160 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_DetectorCorrelation: 9 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_SeasonalPatterns: 70 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_HealthForecast: 168 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_FailureForecast: 168 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_RUL: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_DriftController: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_RegimeDefinitions: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_RegimeOccupancy: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_Run_Stats: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_PCA_Models: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_PCA_Loadings: 3160 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_PCA_Metrics: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_SensorHotspots: 25 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [INFO] [QA] ACM_SensorDefects: 7 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 16:58:23] [SUCCESS] [BATCH] WFA_TURBINE_10: Batch 2 completed (outcome=OK)
[2026-02-18 16:58:23] [INFO] [BATCH]
WFA_TURBINE_10: Batch 3/4 - [2023-05-21 18:16:00 to 2023-08-04 13:27:59]
[2026-02-18 16:58:23] [INFO] [RUN] C:\Users\bhadk\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe -m core.acm_main --equip WFA_TURBINE_10 --start-time 2023-05-21T18:16:00 --end-time 2023-08-04T13:27:59
[2026-02-18 16:58:23] [INFO] [BATCH] WFA_TURBINE_10: Batch 3 - scoring with existing models
[2026-02-18 16:58:26] [SUCCESS] [OTEL] Loki logs -> http://localhost:3100
[2026-02-18 16:58:26] [SUCCESS] [OTEL] Profiling -> http://localhost:4040 [cpu (yappi), memory (tracemalloc)]
[2026-02-18 16:58:26] [SUCCESS] [OTEL] Traces -> http://localhost:4318/v1/traces
[2026-02-18 16:58:26] [SUCCESS] [OTEL] Metrics -> http://localhost:4318/v1/metrics
[2026-02-18 16:58:26] [INFO] [PROFILE] Started CPU profiling
[2026-02-18 16:58:26] [INFO] [SQL] Connecting to SQL Server...
[2026-02-18 16:58:27] [SUCCESS] [SQL] SQL connection established
[2026-02-18 16:58:27] [INFO] [CONFIG] Config loaded from SQL for WFA_TURBINE_10 (EquipID=5010, 265 params)
[2026-02-18 16:58:27] [SUCCESS] [OTEL] SQL log persistence enabled -> ACM_RunLogs
[2026-02-18 16:58:27] [INFO] [RUN] Run #4 | WFA_TURBINE_10 | adaptive | continuous_learning=True | force_retrain=False | intervals=model:1,thresh:1
[2026-02-18 16:58:27] [INFO] [RUN] Run started: WFA_TURBINE_10 (ID=5010) | RunID=3eee78a0 | window=[2025-12-05 16:16:27.713567+00:00,2026-02-18 11:28:27.713567+00:00) | tick=107712m
[2026-02-18 16:58:27] [INFO] [RUN] CLI overrides: start=2023-05-21 18:16:00, end=2023-08-04 13:27:59
[2026-02-18 16:58:27] [INFO] [OUTPUT] Manager initialized (batch_size=5000, batching=ON, sql_cache=60.0s, io_workers=8, flush=1000 rows/30.0s, max_futures=50)
[2026-02-18 16:58:27] [INFO] [DATA] Loading from SQL historian: WFA_TURBINE_10
[2026-02-18 16:58:27] [INFO] [DATA] Time range: 2023-05-21 18:16:00 to 2023-08-04 13:27:59
[2026-02-18 16:58:42] [INFO] [DATA] Retrieved 10615 rows from SQL historian
[2026-02-18 16:58:42] [WARN] [DATA] Permanently excluded 2 low-variance sensors based on persisted list.
[2026-02-18 16:58:42] [INFO] [DATA] BATCH MODE: All 10615 rows allocated to scoring (baseline from cache)
[2026-02-18 16:58:44] [INFO] [DATA] BATCH MODE: Train empty (baseline_buffer later), using 79 score columns
[2026-02-18 16:58:44] [INFO] [DATA] Kept 79 numeric columns, dropped 0 non-numeric
[2026-02-18 16:58:44] >>> Checking cadence and resampling for 10615 score rows...
[2026-02-18 16:58:44] >>>   Checking train cadence...
[2026-02-18 16:58:44] >>>   Checking score cadence...
[2026-02-18 16:58:44] >>>   Cadence check complete: train=True, score=True
[2026-02-18 16:58:44] [INFO] [DATA] Cadence: native=600.0s, requested=auto, will_resample=False
[2026-02-18 16:58:44] [INFO] [DATA] SQL historian load complete: 0 train + 10615 score = 10615 total rows
[2026-02-18 16:58:46] [INFO] [OUTPUT] SQL insert to ACM_DataContractValidation: 1 rows
[2026-02-18 16:58:46] [INFO] [DATA] timestamp=EntryDateTime cadence_ok=True kept=79 drop=0 tz_stripped=0 future_drop=0 dup_removed=0
[2026-02-18 16:58:46] [INFO] [TIMER] data_split_complete  train_rows=0 train_cols=79 score_rows=10615 score_cols=79
[2026-02-18 16:58:46] >>> CHECKPOINT 1: Data loading complete, about to start baseline seeding
[2026-02-18 16:58:46] >>> CHECKPOINT 2: Entering baseline.seed section for WFA_TURBINE_10...
[2026-02-18 16:58:46] >>> CHECKPOINT 3: About to call seed_baseline() function
[2026-02-18 16:58:46] [INFO] [BASELINE] Baseline: score split (train=5307, no overlap) | extended=False
[2026-02-18 16:59:29] [INFO] [SEASON] Seasonal: 125 patterns in 73 sensors | adjusted=True
[2026-02-18 16:59:34] [INFO] [OUTPUT] Auto-flushing batch (rows=0, age=66.4s)
[2026-02-18 16:59:36] [INFO] [OUTPUT] SQL insert to ACM_DataQuality: 1 rows
[2026-02-18 16:59:37] [INFO] [FEAT] Building features with window=16
[2026-02-18 16:59:37] [INFO] [FEAT] Computed 79 fill values from training data
[2026-02-18 17:00:23] [INFO] [FEAT] Features built: train=(5307, 632), score=(5308, 632)
[2026-02-18 17:00:23] [INFO] [FEAT] Features built: train=(5307, 632), score=(5308, 632)
[2026-02-18 17:01:03] [WARN] [FEAT] Dropping 2 columns (0 NaN, 2 low-var)
[2026-02-18 17:01:04] [INFO] [OUTPUT] SQL insert to ACM_FeatureDropLog: 2 rows
[2026-02-18 17:01:07] [WARN] [MODEL] SQL refit request found: id=470 at 2026-02-18 16:55:23.080281
[2026-02-18 17:01:07] [INFO] [MODEL-LOAD] Loading cached models for equip=WFA_TURBINE_10, equip_id=5010
[2026-02-18 17:01:07] [INFO] [MODEL-SQL] Loading models from SQL ModelRegistry v3...
[2026-02-18 17:01:09] [INFO] [MODEL-SQL] - Loaded ar1_params (34,392 bytes)
[2026-02-18 17:01:09] [INFO] [MODEL-SQL] - Loaded calibration_params (600 bytes)
[2026-02-18 17:01:09] [INFO] [MODEL-SQL] - Loaded gmm_model (62,111 bytes)
[2026-02-18 17:01:18] [INFO] [MODEL-SQL] - Loaded iforest_model (4,415,481 bytes)
[2026-02-18 17:01:19] [INFO] [MODEL-SQL] - Loaded omr_model (4,270,610 bytes)
[2026-02-18 17:01:19] [INFO] [MODEL-SQL] - Loaded pca_model (31,391 bytes)
[2026-02-18 17:01:19] [INFO] [MODEL-SQL] [OK] Loaded 6/6 models from SQL ModelRegistry v3
[2026-02-18 17:01:19] [INFO] [MODEL] [OK] Loaded from SQL ModelRegistry successfully
[2026-02-18 17:01:19] [INFO] [MODEL-LOAD] Load result: models=True, manifest=True
[2026-02-18 17:01:19] [WARN] [MODEL-CACHE] Minor sensor mismatch: 2 of 632 cached features not in current data (99.7% overlap)
[2026-02-18 17:01:19] [INFO] [MODEL] Using cached models v3: sensors=630 | sig=96c15b58c09d1cbb...
[2026-02-18 17:01:19] [INFO] [MODEL] Aligning features: cached=632, current=630, common=630, missing_in_current=2, extra_in_current=0, overlap=100.0%
[2026-02-18 17:01:19] [WARN] [MODEL] Using feature subset: 2 cached features missing in current data
[2026-02-18 17:01:20] [INFO] [MODEL] Features aligned to intersection: train=(5307, 630), score=(5308, 630)
[2026-02-18 17:01:20] [WARN] [MODEL] AR1 detector columns don't match current features - will retrain
[2026-02-18 17:01:20] [WARN] [MODEL] PCA detector feature count doesn't match - will retrain
[2026-02-18 17:01:20] [WARN] [MODEL] IForest detector feature count doesn't match - will retrain
[2026-02-18 17:01:20] [WARN] [MODEL] GMM detector feature count doesn't match - will retrain
[2026-02-18 17:01:20] [WARN] [MODEL] Incomplete model cache, missing: ['ar1', 'pca', 'iforest'], retraining required
[2026-02-18 17:01:20] [INFO] [CAL] Loaded cached calibration params (6 detectors)
[2026-02-18 17:01:20] [INFO] [MODEL] Model validation: AR1 column mismatch: cached=632, current=630
[2026-02-18 17:01:20] [INFO] [MODEL] Model validation: PCA feature count mismatch: cached=632, current=630
[2026-02-18 17:01:20] [INFO] [MODEL] Model validation: IForest feature count mismatch: cached=632, current=630
[2026-02-18 17:01:20] [INFO] [MODEL] Model validation: GMM feature count mismatch: cached=632, current=630
[2026-02-18 17:01:20] [INFO] [REGIME_STATE] Loaded state v1 from SQL (EquipID=5010)
[2026-02-18 17:01:20] [INFO] [MODEL] Required models missing or invalid - training fresh models
[2026-02-18 17:01:30] [WARN] [AR1] 49 columns with phi clamped to +/-0.999
[2026-02-18 17:01:30] [INFO] [PCA] Fit start: train shape=(5307, 630)
[2026-02-18 17:01:40] [INFO] [PCA] Fit complete in Span: 5 components, 5307 samples, 630 features
[2026-02-18 17:02:23] [INFO] [GMM] BIC search selected k=3
[2026-02-18 17:02:24] [INFO] [GMM] Fitted k=2, cov=diag, reg=0.001
[2026-02-18 17:02:47] [INFO] [OMR] Selected model type: PLS
[2026-02-18 17:02:48] [INFO] [OMR] Fitted PLS model: 5307 samples, 630 features, 5 components, std=3.903
[2026-02-18 17:02:48] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=194.3s)
[2026-02-18 17:02:49] [INFO] [OUTPUT] SQL insert to ACM_OMR_Diagnostics: 1 rows
[2026-02-18 17:02:49] [INFO] [FIT] Fitted 5 detectors in 89.22s: AR1, PCA(5c), IForest(100), GMM(1), OMR(630f) | samples=5307
[2026-02-18 17:02:49] [INFO] [REGIME] Using 21 raw operational sensors for regime clustering: ['power_29_avg', 'power_29_max', 'power_29_min', 'power_29_std', 'power_30_avg']...
[2026-02-18 17:03:41] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=5308
[2026-02-18 17:03:41] [INFO] [LIFECYCLE] Model maturity: CONVERGED
[2026-02-18 17:03:41] [INFO] [LIFECYCLE] Refit requested with CONVERGED state - overriding to LEARNING to allow regime rediscovery
[2026-02-18 17:03:41] [INFO] [REGIME] Using HDBSCAN clustering (primary method)
[2026-02-18 17:03:41] [INFO] [REGIME] HDBSCAN config: min_cluster_size=30, min_samples=3, method=eom, metric=euclidean
[2026-02-18 17:03:58] [INFO] [REGIME] HDBSCAN found 1 clusters, 298 noise points (5.6%)
[2026-02-18 17:04:37] [INFO] [REGIME] HDBSCAN complete: 1 clusters, validity=0.313 (dbcv)
[2026-02-18 17:04:38] [INFO] [REGIME] ENSEMBLE: GMM fallback fitted with k=1 for noise point assignment
[2026-02-18 17:04:41] [INFO] [REGIME] Training distance threshold (P95): 6.3924 (range: 1.9479 - 9.1069)
[2026-02-18 17:04:54] [INFO] [REGIME] Assigned 5274/5307 low-strength points to nearest cluster
[2026-02-18 17:05:11] [INFO] [REGIME] Identified 5300/5308 novel points (assigned to nearest cluster)
[2026-02-18 17:05:12] [INFO] [REGIME_STATE] Saved state v1 to ACM_RegimeState (EquipID=5010)
[2026-02-18 17:05:12] [INFO] [REGIME_STATE] Regime state: saved_v1 | K=1
[2026-02-18 17:05:13] [INFO] [OUTPUT] SQL insert to ACM_RegimeDefinitions: 1 rows
[2026-02-18 17:05:13] [INFO] [REGIME] Wrote 1 regime definitions for audit
[2026-02-18 17:05:14] [INFO] [OUTPUT] SQL insert to ACM_RegimeOccupancy: 1 rows
[2026-02-18 17:05:14] [INFO] [REGIME] Regime analysis: occupancy=1 | transitions=0
[2026-02-18 17:06:06] [INFO] [SCORE] Scored 5 detectors: AR1, PCA(cached), IForest, GMM, OMR | samples=5307
[2026-02-18 17:06:06] [INFO] [CAL] Using cached calibration for 6 detectors (training-anchored)
[2026-02-18 17:06:06] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=197.9s)
[2026-02-18 17:06:07] [INFO] [OUTPUT] SQL insert to ACM_CalibrationSummary: 6 rows
[2026-02-18 17:06:07] [INFO] [CAL] Calibration complete: q=0.98 | clip_z=20.00 | detectors=6 | thresholds=6 | per_regime=0 | summary=6
[2026-02-18 17:06:07] [INFO] [FUSE] CUSUM auto-tuned: k_sigma=2.000->0.800, h_sigma=12.000->3.000 (spread_ratio=3.92)
[2026-02-18 17:06:07] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->iforest_z: 0.52
[2026-02-18 17:06:07] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->omr_z: 0.58
[2026-02-18 17:06:07] [DEBUG] [FUSE] Detector Spearman correlation gmm_z<->iforest_z: 0.87
[2026-02-18 17:06:07] [DEBUG] [FUSE] Detector Spearman correlation gmm_z<->omr_z: 0.80
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector Spearman correlation iforest_z<->omr_z: 0.74
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector ar1_z: correlated with 2 others, avg_corr=0.55, discount=2.6%
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector gmm_z: correlated with 2 others, avg_corr=0.84, discount=16.8%
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector iforest_z: correlated with 3 others, avg_corr=0.71, discount=10.5%
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector omr_z: correlated with 3 others, avg_corr=0.71, discount=10.4%
[2026-02-18 17:06:08] [INFO] [FUSE] 5/10 detector pairs correlated, weight adjustments applied
[2026-02-18 17:06:08] [WARN] [TUNE] pca_spe_z: all same sign - limited separability
[2026-02-18 17:06:08] [WARN] [TUNE] Excessive weight drift for gmm_z: 0.050 -> 0.084 (drift=68.9% > 20.0%). Rejecting tune.
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->iforest_z: 0.52
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector Spearman correlation ar1_z<->omr_z: 0.58
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector Spearman correlation gmm_z<->iforest_z: 0.87
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector Spearman correlation gmm_z<->omr_z: 0.80
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector Spearman correlation iforest_z<->omr_z: 0.74
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector ar1_z: correlated with 2 others, avg_corr=0.55, discount=2.6%
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector gmm_z: correlated with 2 others, avg_corr=0.84, discount=16.8%
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector iforest_z: correlated with 3 others, avg_corr=0.71, discount=10.5%
[2026-02-18 17:06:08] [DEBUG] [FUSE] Detector omr_z: correlated with 3 others, avg_corr=0.71, discount=10.4%
[2026-02-18 17:06:08] [INFO] [FUSE] 5/10 detector pairs correlated, weight adjustments applied
[2026-02-18 17:06:09] [INFO] [OUTPUT] Saved fusion metrics -> SQL:ACM_RunMetrics (18 records)
[2026-02-18 17:12:07] [INFO] [FUSE] Fusion: detectors=6 | episodes=68 | auto_tuned=True
[2026-02-18 17:12:08] [INFO] [TRANSIENT] Using 168 operating-variable columns for transient detection; excluded 462 condition-indicator columns
[2026-02-18 17:12:11] [INFO] [TRANSIENT] State distribution: {'trip': 5124, 'shutdown': 160, 'startup': 24}
[2026-02-18 17:12:11] [INFO] [REGIME] Regime: quality_ok=False | states={'unknown': 5308} | transient={'trip': 5124, 'shutdown': 160, 'startup': 24}
[2026-02-18 17:12:11] [WARN] [RETRAIN-TRIGGER] Anomaly rate 100.00% exceeds threshold 25.00%
[2026-02-18 17:12:11] [INFO] [CONFIG_HIST] Logged 2 config changes for RunID=3eee78a0-249f-40c8-b539-243570862a29
[2026-02-18 17:12:11] [INFO] [AUTO-TUNE] Auto-tune: 2 adjustments (k_sigma: 2.000->2.200, k_max: 6->8) | refit=next_run
[2026-02-18 17:12:11] [INFO] [OUTPUT] SQL refit request recorded in ACM_RefitRequests
[2026-02-18 17:12:13] [DEBUG] [CAL] Extreme threshold (3804.17) - clamping to 1000.0
[2026-02-18 17:12:13] [INFO] [DRIFT] Drift: cusum_z P95=1.223 | trend=0.0002 | fused=6.019 | mode=FAULT
[2026-02-18 17:12:14] [INFO] [OUTPUT] SQL insert to ACM_DriftController: 1 rows
[2026-02-18 17:12:15] [INFO] [BASELINE] Skipping buffer write (models exist, next refresh in 6 batches)
[2026-02-18 17:12:21] [INFO] [OUTPUT] Auto-flushing batch (rows=6, age=374.6s)
[2026-02-18 17:12:27] [INFO] [OUTPUT] SQL insert to ACM_Scores_Wide: 5308 rows
[2026-02-18 17:12:27] [INFO] [IO] Scores written: {'sql_written': True, 'rows': 5308, 'inserted': 5308, 'error': None, 'sql_table': 'ACM_Scores_Wide', 'artifact': 'scores'} rows
[2026-02-18 17:12:28] [INFO] [EPISODES] Applied 5 schema repairs to episodes: peak_timestamp_fallback_used, regime_mapped_fallback, dominant_sensor_extracted, severity_calculated, status_defaulted
[2026-02-18 17:12:28] [INFO] [OUTPUT] Auto-flushing batch (rows=5308, age=7.2s)
[2026-02-18 17:12:30] [INFO] [OUTPUT] SQL insert to ACM_EpisodeDiagnostics: 68 rows
[2026-02-18 17:12:32] [INFO] [OUTPUT] SQL insert to ACM_Episodes: 68 rows
[2026-02-18 17:12:32] [INFO] [IO] Episodes written: {'sql_written': True, 'rows': 68, 'inserted': 68, 'error': None, 'sql_table': 'ACM_EpisodeDiagnostics', 'artifact': 'episodes'} rows
[2026-02-18 17:12:33] [INFO] [OUTPUT] SQL insert to ACM_DetectorCorrelation: 36 rows
[2026-02-18 17:12:37] [INFO] [OUTPUT] SQL insert to ACM_SensorCorrelations: 3160 rows
[2026-02-18 17:12:46] [INFO] [OUTPUT] SQL insert to ACM_SensorNormalized_TS: 10033 rows
[2026-02-18 17:12:48] [INFO] [OUTPUT] SQL insert to ACM_SeasonalPatterns: 125 rows
[2026-02-18 17:12:48] [INFO] [ANALYTICS] Generating analytics tables (v11 SQL-only)...
[2026-02-18 17:12:48] [INFO] [OUTPUT] Bulk pre-delete: 3 tables targeted, 3 DELETE statements in 0.04s (batched)
[2026-02-18 17:12:55] [INFO] [OUTPUT] SQL insert to ACM_HealthTimeline: 5308 rows
[2026-02-18 17:12:56] [INFO] [OUTPUT] Auto-flushing batch (rows=5376, age=28.2s)
[2026-02-18 17:13:01] [INFO] [OUTPUT] SQL insert to ACM_RegimeTimeline: 5308 rows
[2026-02-18 17:13:01] [INFO] [OUTPUT] Auto-flushing batch (rows=5308, age=5.3s)
[2026-02-18 17:13:02] [INFO] [OUTPUT] SQL insert to ACM_SensorDefects: 7 rows
[2026-02-18 17:13:09] [INFO] [OUTPUT] SQL insert to ACM_SensorHotspots: 25 rows
[2026-02-18 17:13:09] [INFO] [ANALYTICS] Generated analytics tables (SQL written: 4)
[2026-02-18 17:13:09] [INFO] [OUTPUTS] Analytics: tables=4
[2026-02-18 17:13:09] [INFO] [HealthTracker] Data anchor: 2023-08-04 13:20:00, window cutoff: 2023-05-06 13:20:00 (2160h lookback)
[2026-02-18 17:13:10] [INFO] [HealthTracker] Loaded 7498 health points from SQL (rolling window: 2160h)
[2026-02-18 17:13:11] [WARN] [FORECAST] Data quality issue: Max gap 886.5 hours (threshold 720.0 hours)
[2026-02-18 17:13:11] [INFO] [FORECAST] Data summary: n_samples=7498, dt_hours=0.17, window=2160h
[2026-02-18 17:13:11] [WARN] [FORECAST] GAPPY data detected - proceeding with available data (historical replay mode)
[2026-02-18 17:13:12] [INFO] [STATE] Loaded state: EquipID=5010, StateVersion=1, DataVolume=19425
[2026-02-18 17:13:12] [INFO] [FORECAST] Loaded forecast config: alpha=0.30, beta=0.10, failure_threshold=70.0, horizon=168h
[2026-02-18 17:13:12] [INFO] [FORECAST] Auto-tuning triggered at DataVolume=26923
[2026-02-18 17:13:15] [INFO] [DEGRADE] Restored state: level=89.12, trend=0.0000/hr, std_error=0.00
[2026-02-18 17:13:15] [INFO] [DEGRADE] Restored state: level=89.12, trend=0.0000/hr, std_error=0.06
[2026-02-18 17:13:15] [INFO] [FORECAST] Warm-started degradation model from previous state
[2026-02-18 17:13:15] [INFO] [DEGRADE] HEALTH-JUMP: Maintenance reset detected at 2023-08-04 03:00:00. Health jumped 5.5% -> 22.8% (+17.4%). Using 63 post-jump samples for trend fitting.
[2026-02-18 17:13:16] [INFO] [DEGRADE] Fitted: level=25.56, trend=0.8333/hr, std_error=7.02, n=63
[2026-02-18 17:13:16] [INFO] [DEGRADE] HEALTH-JUMP: Maintenance reset detected at 2023-08-04 03:00:00. Health jumped 5.5% -> 22.8% (+17.4%). Using 63 post-jump samples for trend fitting.
[2026-02-18 17:13:17] [INFO] [DEGRADE] Adaptive smoothing: alpha=0.800, beta=0.200
[2026-02-18 17:13:17] [INFO] [DEGRADE] Fitted: level=23.77, trend=0.8333/hr, std_error=7.90, n=63
[2026-02-18 17:13:17] [INFO] [DEGRADE] Fitted regime-conditioned model with 1 regimes
[2026-02-18 17:13:17] [INFO] [FORECAST] RUL_P50=0.0h, RUL_Spread=0.0h, RUL_CV=nan, CI_Width=95.70, Health=26.2, N=7498, Quality=GAPPY
[2026-02-18 17:13:18] [INFO] [SENSOR_ATTR] Loaded 25 sensor attributions from SQL
[2026-02-18 17:13:20] [INFO] [OUTPUT] SQL insert to ACM_HealthForecast: 168 rows
[2026-02-18 17:13:21] [INFO] [OUTPUT] SQL insert to ACM_FailureForecast: 168 rows
[2026-02-18 17:13:21] [WARN] [FORECAST] RUL reliability: NOT_RELIABLE - Model in COLDSTART state - no baseline established
[2026-02-18 17:13:24] [INFO] [OUTPUT] SQL insert to ACM_RUL: 1 rows
[2026-02-18 17:13:24] [INFO] [FORECAST] Wrote 3 forecast tables to SQL
[2026-02-18 17:13:25] [DEBUG] [FORECAST] Sensor forecast query: equip=5010, cutoff=2023-07-05 10:50:00, sensors=['sensor_31_std', 'sensor_5_std', 'sensor_52_std']...
[2026-02-18 17:13:25] [DEBUG] [FORECAST] Sensor forecast query returned 1000 rows
[2026-02-18 17:13:38] [INFO] [FORECAST] Generated 1680 sensor forecast points for 10 sensors over 168h
[2026-02-18 17:13:38] [INFO] [OUTPUT] Auto-flushing batch (rows=369, age=36.3s)
[2026-02-18 17:13:41] [INFO] [OUTPUT] SQL insert to ACM_SensorForecast: 1680 rows
[2026-02-18 17:13:41] [INFO] [FORECAST] Wrote sensor forecasts for 25 sensors
[2026-02-18 17:13:42] [WARN] [MultivariateForecast] Insufficient data: 25 < 100
[2026-02-18 17:13:43] [INFO] [FORECAST] Regime context: regime=0, omr_z=2.39093017578125, drift_trend=unknown
[2026-02-18 17:13:43] [INFO] [STATE] Saved state for EquipID=5010
[2026-02-18 17:13:43] [INFO] [FORECAST] Forecast: RUL P10/50/90=0/0/0h | tables=4 | top_sensors=sen
[2026-02-18 17:13:43] [INFO] [OUTPUT] Batched transaction committed (82.92s)
[2026-02-18 17:13:44] [INFO] [OUTPUT] SQL insert to ACM_PCA_Models: 1 rows
[2026-02-18 17:13:48] [INFO] [OUTPUT] SQL insert to ACM_PCA_Loadings: 3150 rows
[2026-02-18 17:13:49] [INFO] [OUTPUT] SQL insert to ACM_Run_Stats: 1 rows
[2026-02-18 17:14:01] [INFO] [CULPRITS] Wrote 460 culprit records to ACM_EpisodeCulprits
[2026-02-18 17:14:01] >>> ============================================================
[2026-02-18 17:14:01] >>> [2026-02-18 17:14:02] [DEBUG] [RUN_META] No data quality records found in SQL, defaulting to 100.0
[2026-02-18 17:14:02] [INFO] [RUN_META] Wrote run metadata to ACM_Runs: 3eee78a0-249f-40c8-b539-243570862a29
[2026-02-18 17:14:02] [INFO] [RUN] Finalized RunID=3eee78a0-249f-40c8-b539-243570862a29 outcome=OK rows_in=5308 rows_out=3152
[2026-02-18 17:14:02] [DEBUG] [OUTPUT] OutputManager stats: 12 write_dataframe calls, 0 batch rows, 2.971s avg write time
[2026-02-18 17:14:02] [INFO] [PROFILE] Stopping and pushing profile data...
[2026-02-18 17:14:27] >>> --- Top CPU Functions ---
[2026-02-18 17:14:27] >>>    1. generic.Series.fillna: 557653.0ms (7048 calls)
[2026-02-18 17:14:27] >>>    2. omr.OMRDetector._prepare_data: 495840.5ms (3 calls)
[2026-02-18 17:14:27] >>>    3. frame.DataFrame.__getitem__: 475731.1ms (14241 calls)
[2026-02-18 17:14:27] >>>    4. frame.DataFrame._ixs: 469246.7ms (13578 calls)
[2026-02-18 17:14:27] >>>    5. forecast_engine.ForecastEngine.run_forecast: 461856.1ms (1 calls)
[2026-02-18 17:14:27] >>>    6. frame.DataFrame._get_item_cache: 459496.7ms (14303 calls)
[2026-02-18 17:14:27] >>>    7. forecast_engine.ForecastEngine._write_outputs: 453074.9ms (1 calls)
[2026-02-18 17:14:27] >>>    8. output_manager.OutputManager._prepare_dataframe_for_sql: 448371.7ms (23 calls)
[2026-02-18 17:14:27] >>>    9. managers.BlockManager.iget: 436449.9ms (14689 calls)
[2026-02-18 17:14:27] >>>   10. common.pandas_dtype: 430949.9ms (3365 calls)
[2026-02-18 17:14:28] [INFO] [PROFILE] Pushing cpu (2566 stacks) to Pyroscope...
[2026-02-18 17:14:28] [SUCCESS] [PROFILE] cpu profile pushed successfully
[2026-02-18 17:14:30] [INFO] [PROFILE] Pushing alloc_objects (500 stacks) to Pyroscope...
[2026-02-18 17:14:30] [SUCCESS] [PROFILE] alloc_objects profile pushed successfully
[2026-02-18 17:14:31] [INFO] [PROFILE] Pushing alloc_space (500 stacks) to Pyroscope...
[2026-02-18 17:14:31] [SUCCESS] [PROFILE] alloc_space profile pushed successfully
[2026-02-18 17:14:31] [SUCCESS] [PROFILE] Profile data pushed to Pyroscope
[2026-02-18 17:14:34] >>> --- Timer Summary ---
[2026-02-18 17:14:34] >>> fusion                         360.633s ( 37.2%)
[2026-02-18 17:14:34] >>> regimes.label                   91.622s (  9.5%)
[2026-02-18 17:14:34] >>> train.detector_fit              89.260s (  9.2%)
[2026-02-18 17:14:34] >>> persist                         82.964s (  8.6%)
[2026-02-18 17:14:34] >>> calibrate                       52.339s (  5.4%)
[2026-02-18 17:14:34] >>> score.detector_score            51.011s (  5.3%)
[2026-02-18 17:14:34] >>> features.build                  45.984s (  4.7%)
[2026-02-18 17:14:34] >>> seasonality.detect              42.995s (  4.4%)
[2026-02-18 17:14:34] >>> features.impute                 41.246s (  4.3%)
[2026-02-18 17:14:34] >>> outputs.forecasting             33.959s (  3.5%)
[2026-02-18 17:14:34] >>> outputs.comprehensive_analytics  20.623s (  2.1%)
[2026-02-18 17:14:34] >>> load_data                       18.530s (  1.9%)
[2026-02-18 17:14:34] >>> models.load                     12.994s (  1.3%)
[2026-02-18 17:14:34] >>> sql.culprits                    11.670s (  1.2%)
[2026-02-18 17:14:34] >>> persist.sensor_normalized_ts     9.424s (  1.0%)
[2026-02-18 17:14:34] >>> persist.write_scores             7.390s (  0.8%)
[2026-02-18 17:14:34] >>> data.guardrails                  7.209s (  0.7%)
[2026-02-18 17:14:34] >>> sql.pca                          5.618s (  0.6%)
[2026-02-18 17:14:34] >>> persist.write_episodes           5.006s (  0.5%)
[2026-02-18 17:14:34] >>> sensor.context                   4.499s (  0.5%)
[2026-02-18 17:14:34] >>> regimes.transient_detection      3.388s (  0.3%)
[2026-02-18 17:14:34] >>> persist.sensor_correlation       3.272s (  0.3%)
[2026-02-18 17:14:34] >>> features.hash                    2.781s (  0.3%)
[2026-02-18 17:14:34] >>> regimes.occupancy                1.690s (  0.2%)
[2026-02-18 17:14:34] >>> persist.seasonal_patterns        1.578s (  0.2%)
[2026-02-18 17:14:34] >>> data.contract                    1.545s (  0.2%)
[2026-02-18 17:14:34] >>> drift                            1.493s (  0.2%)
[2026-02-18 17:14:34] >>> persist.detector_correlation     1.004s (  0.1%)
[2026-02-18 17:14:34] >>> drift.controller                 0.937s (  0.1%)
[2026-02-18 17:14:34] >>> sql.run_stats                    0.683s (  0.1%)
[2026-02-18 17:14:34] >>> startup                          0.333s (  0.0%)
[2026-02-18 17:14:34] >>> baseline.seed                    0.110s (  0.0%)
[2026-02-18 17:14:34] >>> models.refit_flag                0.047s (  0.0%)
[2026-02-18 17:14:34] >>> baseline.buffer_write            0.044s (  0.0%)
[2026-02-18 17:14:34] >>> contribution.timeline            0.022s (  0.0%)
[2026-02-18 17:14:34] >>> thresholds.adaptive              0.021s (  0.0%)
[2026-02-18 17:14:34] >>> total_run                      968.350s

[2026-02-18 17:14:34] [INFO] [QA] Inspecting outputs for EquipID=5010, RunID=3EEE78A0-249F-40C8-B539-243570862A29 (from ACM_Runs), window=[2026-02-18 11:28:27.716412,2026-02-18 11:44:02.056666)
[2026-02-18 17:14:35] [INFO] [QA] ACM_Scores_Wide: 5308 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_HealthTimeline: 5308 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_RegimeTimeline: 5308 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_EpisodeDiagnostics: 68 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_Episodes: 68 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_EpisodeMetrics: 0 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_SensorNormalized_TS: 10033 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_SensorCorrelations: 3160 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_DetectorCorrelation: 36 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_SeasonalPatterns: 125 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_HealthForecast: 168 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_FailureForecast: 168 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_RUL: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_DriftController: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_RegimeDefinitions: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_RegimeOccupancy: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_Run_Stats: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_PCA_Models: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_PCA_Loadings: 3150 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_PCA_Metrics: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_SensorHotspots: 25 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [INFO] [QA] ACM_SensorDefects: 7 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:14:35] [SUCCESS] [BATCH] WFA_TURBINE_10: Batch 3 completed (outcome=OK)
[2026-02-18 17:14:35] [INFO] [BATCH]
WFA_TURBINE_10: Batch 4/4 - [2023-08-04 13:28:00 to 2023-10-18 08:39:59]
[2026-02-18 17:14:35] [INFO] [RUN] C:\Users\bhadk\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe -m core.acm_main --equip WFA_TURBINE_10 --start-time 2023-08-04T13:28:00 --end-time 2023-10-18T08:39:59
[2026-02-18 17:14:35] [INFO] [BATCH] WFA_TURBINE_10: Batch 4 - scoring with existing models
[2026-02-18 17:14:38] [SUCCESS] [OTEL] Loki logs -> http://localhost:3100
[2026-02-18 17:14:38] [SUCCESS] [OTEL] Profiling -> http://localhost:4040 [cpu (yappi), memory (tracemalloc)]
[2026-02-18 17:14:38] [SUCCESS] [OTEL] Traces -> http://localhost:4318/v1/traces
[2026-02-18 17:14:38] [SUCCESS] [OTEL] Metrics -> http://localhost:4318/v1/metrics
[2026-02-18 17:14:38] [INFO] [PROFILE] Started CPU profiling
[2026-02-18 17:14:39] [INFO] [SQL] Connecting to SQL Server...
[2026-02-18 17:14:39] [SUCCESS] [SQL] SQL connection established
[2026-02-18 17:14:39] [INFO] [CONFIG] Config loaded from SQL for WFA_TURBINE_10 (EquipID=5010, 265 params)
[2026-02-18 17:14:39] [SUCCESS] [OTEL] SQL log persistence enabled -> ACM_RunLogs
[2026-02-18 17:14:39] [INFO] [RUN] Run #5 | WFA_TURBINE_10 | adaptive | continuous_learning=True | force_retrain=False | intervals=model:1,thresh:1
[2026-02-18 17:14:39] [INFO] [RUN] Run started: WFA_TURBINE_10 (ID=5010) | RunID=ed7ff586 | window=[2025-12-05 16:32:39.839010+00:00,2026-02-18 11:44:39.839010+00:00) | tick=107712m
[2026-02-18 17:14:39] [INFO] [RUN] CLI overrides: start=2023-08-04 13:28:00, end=2023-10-18 08:39:59
[2026-02-18 17:14:39] [INFO] [OUTPUT] Manager initialized (batch_size=5000, batching=ON, sql_cache=60.0s, io_workers=8, flush=1000 rows/30.0s, max_futures=50)
[2026-02-18 17:14:39] [INFO] [DATA] Loading from SQL historian: WFA_TURBINE_10
[2026-02-18 17:14:39] [INFO] [DATA] Time range: 2023-08-04 13:28:00 to 2023-10-18 08:39:59
[2026-02-18 17:14:55] [INFO] [DATA] Retrieved 10738 rows from SQL historian
[2026-02-18 17:14:55] [WARN] [DATA] Permanently excluded 2 low-variance sensors based on persisted list.
[2026-02-18 17:14:55] [INFO] [DATA] BATCH MODE: All 10738 rows allocated to scoring (baseline from cache)
[2026-02-18 17:14:56] [INFO] [DATA] BATCH MODE: Train empty (baseline_buffer later), using 79 score columns
[2026-02-18 17:14:56] [INFO] [DATA] Kept 79 numeric columns, dropped 0 non-numeric
[2026-02-18 17:14:56] >>> Checking cadence and resampling for 10738 score rows...
[2026-02-18 17:14:56] >>>   Checking train cadence...
[2026-02-18 17:14:56] >>>   Checking score cadence...
[2026-02-18 17:14:56] >>>   Cadence check complete: train=True, score=True
[2026-02-18 17:14:56] [INFO] [DATA] Cadence: native=600.0s, requested=auto, will_resample=False
[2026-02-18 17:14:56] [INFO] [DATA] SQL historian load complete: 0 train + 10738 score = 10738 total rows
[2026-02-18 17:14:58] [INFO] [OUTPUT] SQL insert to ACM_DataContractValidation: 1 rows
[2026-02-18 17:14:58] [INFO] [DATA] timestamp=EntryDateTime cadence_ok=True kept=79 drop=0 tz_stripped=0 future_drop=0 dup_removed=0
[2026-02-18 17:14:58] [INFO] [TIMER] data_split_complete  train_rows=0 train_cols=79 score_rows=10738 score_cols=79
[2026-02-18 17:14:58] >>> CHECKPOINT 1: Data loading complete, about to start baseline seeding
[2026-02-18 17:14:58] >>> CHECKPOINT 2: Entering baseline.seed section for WFA_TURBINE_10...
[2026-02-18 17:14:58] >>> CHECKPOINT 3: About to call seed_baseline() function
[2026-02-18 17:14:58] [INFO] [BASELINE] Baseline: score split (train=5369, no overlap) | extended=False
[2026-02-18 17:15:36] [INFO] [SEASON] Seasonal: 99 patterns in 73 sensors | adjusted=True
[2026-02-18 17:15:41] [INFO] [OUTPUT] Auto-flushing batch (rows=0, age=61.5s)
[2026-02-18 17:15:44] [INFO] [OUTPUT] SQL insert to ACM_DataQuality: 1 rows
[2026-02-18 17:15:44] [INFO] [FEAT] Building features with window=16
[2026-02-18 17:15:45] [INFO] [FEAT] Computed 79 fill values from training data
[2026-02-18 17:16:30] [INFO] [FEAT] Features built: train=(5369, 632), score=(5369, 632)
[2026-02-18 17:16:30] [INFO] [FEAT] Features built: train=(5369, 632), score=(5369, 632)
[2026-02-18 17:17:13] [WARN] [MODEL] SQL refit request found: id=471 at 2026-02-18 17:12:11.766980
[2026-02-18 17:17:13] [INFO] [MODEL-LOAD] Loading cached models for equip=WFA_TURBINE_10, equip_id=5010
[2026-02-18 17:17:13] [INFO] [MODEL-SQL] Loading models from SQL ModelRegistry v3...
[2026-02-18 17:17:15] [INFO] [MODEL-SQL] - Loaded ar1_params (34,392 bytes)
[2026-02-18 17:17:15] [INFO] [MODEL-SQL] - Loaded calibration_params (600 bytes)
[2026-02-18 17:17:15] [INFO] [MODEL-SQL] - Loaded gmm_model (62,111 bytes)
[2026-02-18 17:17:24] [INFO] [MODEL-SQL] - Loaded iforest_model (4,415,481 bytes)
[2026-02-18 17:17:25] [INFO] [MODEL-SQL] - Loaded omr_model (4,270,610 bytes)
[2026-02-18 17:17:25] [INFO] [MODEL-SQL] - Loaded pca_model (31,391 bytes)
[2026-02-18 17:17:25] [INFO] [MODEL-SQL] [OK] Loaded 6/6 models from SQL ModelRegistry v3
[2026-02-18 17:17:25] [INFO] [MODEL] [OK] Loaded from SQL ModelRegistry successfully
[2026-02-18 17:17:25] [INFO] [MODEL-LOAD] Load result: models=True, manifest=True
[2026-02-18 17:17:25] [INFO] [MODEL] Using cached models v3: sensors=632 | sig=96c15b58c09d1cbb...
[2026-02-18 17:17:25] [INFO] [CAL] Loaded cached calibration params (6 detectors)
[2026-02-18 17:17:25] [INFO] [REGIME_STATE] Loaded state v1 from SQL (EquipID=5010)
[2026-02-18 17:17:26] [INFO] [REGIME] Using 21 raw operational sensors for regime clustering: ['power_29_avg', 'power_29_max', 'power_29_min', 'power_29_std', 'power_30_avg']...
[2026-02-18 17:17:49] [INFO] [SCORE] Scored 5 detectors: AR1, PCA, IForest, GMM, OMR | samples=5369
[2026-02-18 17:17:50] [INFO] [LIFECYCLE] Model maturity: CONVERGED
[2026-02-18 17:17:50] [INFO] [LIFECYCLE] Refit requested with CONVERGED state - overriding to LEARNING to allow regime rediscovery
[2026-02-18 17:17:50] [INFO] [REGIME] Using HDBSCAN clustering (primary method)
[2026-02-18 17:17:50] [INFO] [REGIME] HDBSCAN config: min_cluster_size=30, min_samples=3, method=eom, metric=euclidean
[2026-02-18 17:18:09] [INFO] [REGIME] HDBSCAN found 1 clusters, 110 noise points (2.0%)
[2026-02-18 17:18:49] [INFO] [REGIME] HDBSCAN complete: 1 clusters, validity=0.320 (dbcv)
[2026-02-18 17:18:54] [INFO] [REGIME] ENSEMBLE: GMM fallback fitted with k=1 for noise point assignment
[2026-02-18 17:18:57] [INFO] [REGIME] Training distance threshold (P95): 6.8566 (range: 1.4710 - 9.3818)
[2026-02-18 17:19:11] [INFO] [REGIME] Assigned 5319/5369 low-strength points to nearest cluster
[2026-02-18 17:19:27] [INFO] [REGIME] Identified 5366/5369 novel points (assigned to nearest cluster)
[2026-02-18 17:19:28] [INFO] [REGIME_STATE] Saved state v1 to ACM_RegimeState (EquipID=5010)
[2026-02-18 17:19:28] [INFO] [REGIME_STATE] Regime state: saved_v1 | K=1
[2026-02-18 17:19:29] [INFO] [OUTPUT] SQL insert to ACM_RegimeDefinitions: 1 rows
[2026-02-18 17:19:29] [INFO] [REGIME] Wrote 1 regime definitions for audit
[2026-02-18 17:19:30] [INFO] [OUTPUT] SQL insert to ACM_RegimeOccupancy: 1 rows
[2026-02-18 17:19:30] [INFO] [REGIME] Regime analysis: occupancy=1 | transitions=0
[2026-02-18 17:19:30] [WARN] [MODEL] Forcing retraining: regime_quality_ok=False (metric=dbcv, score=0.320)
[2026-02-18 17:19:40] [WARN] [AR1] 54 columns with phi clamped to +/-0.999
[2026-02-18 17:19:40] [INFO] [PCA] Fit start: train shape=(5369, 632)
[2026-02-18 17:19:50] [INFO] [PCA] Fit complete in Span: 5 components, 5369 samples, 632 features
[2026-02-18 17:20:29] [INFO] [GMM] BIC search selected k=3
[2026-02-18 17:20:33] [INFO] [GMM] Fitted k=3, cov=diag, reg=0.001
[2026-02-18 17:20:55] [INFO] [OMR] Selected model type: PLS
[2026-02-18 17:20:56] [INFO] [OMR] Fitted PLS model: 5369 samples, 632 features, 5 components, std=3.859
[2026-02-18 17:20:56] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=314.9s)
[2026-02-18 17:20:57] [INFO] [OUTPUT] SQL insert to ACM_OMR_Diagnostics: 1 rows
[2026-02-18 17:20:57] [INFO] [FIT] Fitted 5 detectors in 86.89s: AR1, PCA(5c), IForest(100), GMM(1), OMR(632f) | samples=5369
[2026-02-18 17:20:58] [INFO] [MODEL] Saving models to SQL ModelRegistry v4
[2026-02-18 17:20:58] [INFO] [MODEL-SQL] Saving models to SQL ModelRegistry v4...
[2026-02-18 17:21:01] [INFO] [MODEL-SQL] - Saved ar1_params (34,392 bytes)
[2026-02-18 17:21:01] [INFO] [MODEL-SQL] - Saved pca_model (31,391 bytes)
[2026-02-18 17:21:05] [INFO] [MODEL-SQL] - Saved iforest_model (4,365,145 bytes)
[2026-02-18 17:21:05] [INFO] [MODEL-SQL] - Saved gmm_model (61,997 bytes)
[2026-02-18 17:21:07] [INFO] [MODEL-SQL] - Saved omr_model (4,268,554 bytes)
[2026-02-18 17:21:07] [DEBUG] [MODEL-SQL] - Skipping None model: regime_model
[2026-02-18 17:21:07] [DEBUG] [MODEL-SQL] - Skipping None model: feature_medians
[2026-02-18 17:21:07] [DEBUG] [MODEL-SQL] - Skipping None model: calibration_params
[2026-02-18 17:21:07] [INFO] [MODEL-SQL] OK Committed 5/8 models to SQL ModelRegistry v4
[2026-02-18 17:21:07] [INFO] [MODEL] Saved 8 models to SQL ModelRegistry v4
[2026-02-18 17:21:07] [INFO] [MODEL] Saved all trained models to version v4
[2026-02-18 17:21:07] [INFO] [LIFECYCLE] Model state v1: CONVERGED
[2026-02-18 17:21:09] [INFO] [OUTPUT] SQL insert to ACM_ActiveModels: 1 rows
[2026-02-18 17:21:09] [INFO] [OUTPUT] OutputManager maturity_state set to CONVERGED
[2026-02-18 17:21:09] [INFO] [LIFECYCLE] Model state: CONVERGED
[2026-02-18 17:22:00] [INFO] [SCORE] Scored 5 detectors: AR1, PCA(cached), IForest, GMM, OMR | samples=5369
[2026-02-18 17:22:00] [INFO] [CAL] Using cached calibration for 6 detectors (training-anchored)
[2026-02-18 17:22:00] [INFO] [CAL] Saved calibration params (6 detectors, 600 bytes) to v4
[2026-02-18 17:22:00] [INFO] [OUTPUT] Auto-flushing batch (rows=1, age=64.3s)
[2026-02-18 17:22:01] [INFO] [OUTPUT] SQL insert to ACM_CalibrationSummary: 6 rows
[2026-02-18 17:22:01] [INFO] [CAL] Calibration complete: q=0.98 | clip_z=20.00 | detectors=6 | thresholds=6 | per_regime=0 | summary=6
[2026-02-18 17:22:01] [INFO] [FUSE] CUSUM auto-tuned: k_sigma=2.000->0.800, h_sigma=12.000->3.000 (spread_ratio=1.41)
[2026-02-18 17:22:01] [WARN] [TUNE] gmm_z: all same sign - limited separability
[2026-02-18 17:22:01] [WARN] [TUNE] iforest_z: all same sign - limited separability
[2026-02-18 17:22:01] [WARN] [TUNE] pca_spe_z: all same sign - limited separability
[2026-02-18 17:22:01] [WARN] [TUNE] pca_t2_z: all same sign - limited separability
[2026-02-18 17:22:01] [WARN] [TUNE] Excessive weight drift for gmm_z: 0.050 -> 0.086 (drift=72.2% > 20.0%). Rejecting tune.
[2026-02-18 17:22:02] [INFO] [OUTPUT] Saved fusion metrics -> SQL:ACM_RunMetrics (18 records)
[2026-02-18 17:22:13] [INFO] [FUSE] Fusion: detectors=6 | episodes=45 | auto_tuned=True
[2026-02-18 17:22:13] [INFO] [TRANSIENT] Using 168 operating-variable columns for transient detection; excluded 464 condition-indicator columns
[2026-02-18 17:22:17] [INFO] [TRANSIENT] State distribution: {'trip': 5189, 'shutdown': 161, 'startup': 19}
[2026-02-18 17:22:17] [INFO] [REGIME] Regime: quality_ok=False | states={'unknown': 5369} | transient={'trip': 5189, 'shutdown': 161, 'startup': 19}
[2026-02-18 17:22:17] [INFO] [CONFIG_HIST] Logged 1 config changes for RunID=ed7ff586-0cb7-4fe5-8e7b-48f9d4becf80
[2026-02-18 17:22:17] [INFO] [AUTO-TUNE] Auto-tune: 1 adjustments (k_max: 6->8) | refit=next_run
[2026-02-18 17:22:17] [INFO] [OUTPUT] SQL refit request recorded in ACM_RefitRequests
[2026-02-18 17:22:18] [INFO] [CAL] Contamination filter (iterative_mad): excluded 805/5369 samples (15.0%) | retained=4564
[2026-02-18 17:22:18] [DEBUG] [CAL] Extreme threshold (1364.65) - clamping to 1000.0
[2026-02-18 17:22:18] [INFO] [DRIFT] Drift: cusum_z P95=4.757 | trend=0.0020 | fused=-0.748 | mode=FAULT
[2026-02-18 17:22:19] [INFO] [OUTPUT] SQL insert to ACM_DriftController: 1 rows
[2026-02-18 17:22:21] [INFO] [BASELINE] Skipping buffer write (models exist, next refresh in 5 batches)
[2026-02-18 17:22:34] [INFO] [OUTPUT] SQL insert to ACM_Scores_Wide: 5369 rows
[2026-02-18 17:22:34] [INFO] [IO] Scores written: {'sql_written': True, 'rows': 5369, 'inserted': 5369, 'error': None, 'sql_table': 'ACM_Scores_Wide', 'artifact': 'scores'} rows
[2026-02-18 17:22:34] [INFO] [EPISODES] Applied 5 schema repairs to episodes: peak_timestamp_fallback_used, regime_mapped_fallback, dominant_sensor_extracted, severity_calculated, status_defaulted
[2026-02-18 17:22:34] [INFO] [OUTPUT] Auto-flushing batch (rows=5375, age=34.3s)
[2026-02-18 17:22:36] [INFO] [OUTPUT] SQL insert to ACM_EpisodeDiagnostics: 45 rows
[2026-02-18 17:22:38] [INFO] [OUTPUT] SQL insert to ACM_Episodes: 45 rows
[2026-02-18 17:22:38] [INFO] [IO] Episodes written: {'sql_written': True, 'rows': 45, 'inserted': 45, 'error': None, 'sql_table': 'ACM_EpisodeDiagnostics', 'artifact': 'episodes'} rows
[2026-02-18 17:22:39] [INFO] [OUTPUT] SQL insert to ACM_DetectorCorrelation: 9 rows
[2026-02-18 17:22:42] [INFO] [OUTPUT] SQL insert to ACM_SensorCorrelations: 3160 rows
[2026-02-18 17:22:53] [INFO] [OUTPUT] SQL insert to ACM_SensorNormalized_TS: 10112 rows
[2026-02-18 17:22:54] [INFO] [OUTPUT] SQL insert to ACM_SeasonalPatterns: 99 rows
[2026-02-18 17:22:55] [INFO] [ANALYTICS] Generating analytics tables (v11 SQL-only)...
[2026-02-18 17:22:55] [INFO] [OUTPUT] Bulk pre-delete: 3 tables targeted, 3 DELETE statements in 0.04s (batched)
[2026-02-18 17:23:02] [INFO] [OUTPUT] SQL insert to ACM_HealthTimeline: 5369 rows
[2026-02-18 17:23:03] [INFO] [OUTPUT] Auto-flushing batch (rows=5414, age=28.3s)
[2026-02-18 17:23:08] [INFO] [OUTPUT] SQL insert to ACM_RegimeTimeline: 5369 rows
[2026-02-18 17:23:08] [INFO] [OUTPUT] Auto-flushing batch (rows=5369, age=5.5s)
[2026-02-18 17:23:09] [INFO] [OUTPUT] SQL insert to ACM_SensorDefects: 7 rows
[2026-02-18 17:23:16] [INFO] [OUTPUT] SQL insert to ACM_SensorHotspots: 25 rows
[2026-02-18 17:23:16] [INFO] [ANALYTICS] Generated analytics tables (SQL written: 4)
[2026-02-18 17:23:16] [INFO] [OUTPUTS] Analytics: tables=4
[2026-02-18 17:23:16] [INFO] [HealthTracker] Data anchor: 2023-10-18 08:30:00, window cutoff: 2023-07-20 08:30:00 (2160h lookback)
[2026-02-18 17:23:17] [INFO] [HealthTracker] Loaded 7559 health points from SQL (rolling window: 2160h)
[2026-02-18 17:23:19] [WARN] [FORECAST] Data quality issue: Max gap 895.5 hours (threshold 720.0 hours)
[2026-02-18 17:23:19] [INFO] [FORECAST] Data summary: n_samples=7559, dt_hours=0.17, window=2160h
[2026-02-18 17:23:19] [WARN] [FORECAST] GAPPY data detected - proceeding with available data (historical replay mode)
[2026-02-18 17:23:19] [INFO] [STATE] Loaded state: EquipID=5010, StateVersion=1, DataVolume=26923
[2026-02-18 17:23:19] [INFO] [FORECAST] Loaded forecast config: alpha=0.30, beta=0.10, failure_threshold=70.0, horizon=168h
[2026-02-18 17:23:19] [INFO] [FORECAST] Auto-tuning triggered at DataVolume=34482
[2026-02-18 17:23:22] [INFO] [DEGRADE] Restored state: level=25.56, trend=0.8333/hr, std_error=7.02
[2026-02-18 17:23:22] [INFO] [DEGRADE] Restored state: level=23.77, trend=0.8333/hr, std_error=7.90
[2026-02-18 17:23:22] [INFO] [FORECAST] Warm-started degradation model from previous state
[2026-02-18 17:23:23] [INFO] [DEGRADE] HEALTH-JUMP: Maintenance reset detected at 2023-09-10 21:00:00. Health jumped 27.2% -> 45.8% (+18.6%). Using 5368 post-jump samples for trend fitting.
[2026-02-18 17:23:23] [INFO] [DEGRADE] Detected 345 outliers (robust z > 3.0)
[2026-02-18 17:23:39] [INFO] [DEGRADE] Fitted: level=79.38, trend=-0.1719/hr, std_error=0.23, n=5368
[2026-02-18 17:23:39] [INFO] [DEGRADE] HEALTH-JUMP: Maintenance reset detected at 2023-09-10 21:00:00. Health jumped 27.2% -> 45.8% (+18.6%). Using 5368 post-jump samples for trend fitting.
[2026-02-18 17:23:39] [INFO] [DEGRADE] Detected 345 outliers (robust z > 3.0)
[2026-02-18 17:24:13] [INFO] [DEGRADE] Adaptive smoothing: alpha=0.800, beta=0.200
[2026-02-18 17:24:28] [INFO] [DEGRADE] Fitted: level=79.33, trend=-0.2363/hr, std_error=0.28, n=5368
[2026-02-18 17:24:28] [INFO] [DEGRADE] Fitted regime-conditioned model with 1 regimes
[2026-02-18 17:24:29] [INFO] [RUL] RUL estimate: P50=41.0h, P10=32.0h, P90=53.6h, mean=41.9h, std=8.1h, failure_prob=1.000
[2026-02-18 17:24:29] [INFO] [FORECAST] RUL_P50=41.0h, RUL_Spread=21.6h, RUL_CV=0.19, CI_Width=39.69, Health=79.4, N=7559, Quality=GAPPY
[2026-02-18 17:24:29] [INFO] [SENSOR_ATTR] Loaded 25 sensor attributions from SQL
[2026-02-18 17:24:29] [INFO] [OUTPUT] Auto-flushing batch (rows=32, age=81.2s)
[2026-02-18 17:24:31] [INFO] [OUTPUT] SQL insert to ACM_HealthForecast: 168 rows
[2026-02-18 17:24:33] [INFO] [OUTPUT] SQL insert to ACM_FailureForecast: 168 rows
[2026-02-18 17:24:35] [INFO] [OUTPUT] SQL insert to ACM_RUL: 1 rows
[2026-02-18 17:24:35] [INFO] [FORECAST] Wrote 3 forecast tables to SQL
[2026-02-18 17:24:36] [DEBUG] [FORECAST] Sensor forecast query: equip=5010, cutoff=2023-09-18 02:50:00, sensors=['sensor_31_std', 'sensor_5_std', 'sensor_2_avg']...
[2026-02-18 17:24:36] [DEBUG] [FORECAST] Sensor forecast query returned 1030 rows
[2026-02-18 17:24:49] [INFO] [FORECAST] Generated 1680 sensor forecast points for 10 sensors over 168h
[2026-02-18 17:24:53] [INFO] [OUTPUT] SQL insert to ACM_SensorForecast: 1680 rows
[2026-02-18 17:24:53] [INFO] [FORECAST] Wrote sensor forecasts for 25 sensors
[2026-02-18 17:24:54] [WARN] [MultivariateForecast] Insufficient data: 24 < 100
[2026-02-18 17:24:54] [INFO] [FORECAST] Regime context: regime=0, omr_z=-1.3903566598892212, drift_trend=unknown
[2026-02-18 17:24:54] [INFO] [STATE] Saved state for EquipID=5010
[2026-02-18 17:24:54] [INFO] [FORECAST] Forecast: RUL P10/50/90=32/41/54h | tables=4 | top_sensors=sen
[2026-02-18 17:24:55] [INFO] [OUTPUT] Batched transaction committed (148.30s)
[2026-02-18 17:24:56] [INFO] [OUTPUT] SQL insert to ACM_PCA_Models: 1 rows
[2026-02-18 17:25:00] [INFO] [OUTPUT] SQL insert to ACM_PCA_Loadings: 3160 rows
[2026-02-18 17:25:01] [INFO] [OUTPUT] SQL insert to ACM_Run_Stats: 1 rows
[2026-02-18 17:25:09] [INFO] [CULPRITS] Wrote 309 culprit records to ACM_EpisodeCulprits
[2026-02-18 17:25:09] >>> ============================================================
[2026-02-18 17:25:09] >>> [2026-02-18 17:25:09] [DEBUG] [RUN_META] No data quality records found in SQL, defaulting to 100.0
[2026-02-18 17:25:10] [INFO] [RUN_META] Wrote run metadata to ACM_Runs: ed7ff586-0cb7-4fe5-8e7b-48f9d4becf80
[2026-02-18 17:25:10] [INFO] [RUN] Finalized RunID=ed7ff586-0cb7-4fe5-8e7b-48f9d4becf80 outcome=OK rows_in=5369 rows_out=3162
[2026-02-18 17:25:10] [DEBUG] [OUTPUT] OutputManager stats: 12 write_dataframe calls, 0 batch rows, 3.051s avg write time
[2026-02-18 17:25:10] [INFO] [PROFILE] Stopping and pushing profile data...
[2026-02-18 17:25:35] >>> --- Top CPU Functions ---
[2026-02-18 17:25:35] >>>    1. _function_base_impl._ureduce: 468231.1ms (13328 calls)
[2026-02-18 17:25:35] >>>    2. generic.Series._stat_function: 457590.5ms (2175 calls)
[2026-02-18 17:25:35] >>>    3. _nanfunctions_impl.nanmedian: 456168.6ms (1406 calls)
[2026-02-18 17:25:35] >>>    4. _nanfunctions_impl._nanmedian: 455668.6ms (1406 calls)
[2026-02-18 17:25:35] >>>    5. nanops.f: 455074.9ms (3644 calls)
[2026-02-18 17:25:35] >>>    6. frame.DataFrame._reduce: 453903.0ms (80 calls)
[2026-02-18 17:25:35] >>>    7. _nanfunctions_impl._nanmedian1d: 453559.2ms (7907 calls)
[2026-02-18 17:25:35] >>>    8. _function_base_impl.median: 452715.5ms (9215 calls)
[2026-02-18 17:25:35] >>>    9. _shape_base_impl.apply_along_axis: 452574.9ms (189 calls)
[2026-02-18 17:25:35] >>>   10. managers.BlockManager.reduce: 451981.1ms (80 calls)
[2026-02-18 17:25:37] [INFO] [PROFILE] Pushing cpu (2623 stacks) to Pyroscope...
[2026-02-18 17:25:37] [SUCCESS] [PROFILE] cpu profile pushed successfully
[2026-02-18 17:25:39] [INFO] [PROFILE] Pushing alloc_objects (500 stacks) to Pyroscope...
[2026-02-18 17:25:39] [SUCCESS] [PROFILE] alloc_objects profile pushed successfully
[2026-02-18 17:25:40] [INFO] [PROFILE] Pushing alloc_space (500 stacks) to Pyroscope...
[2026-02-18 17:25:40] [SUCCESS] [PROFILE] alloc_space profile pushed successfully
[2026-02-18 17:25:40] [SUCCESS] [PROFILE] Profile data pushed to Pyroscope
[2026-02-18 17:25:44] >>> --- Timer Summary ---
[2026-02-18 17:25:44] >>> persist                        148.342s ( 22.3%)
[2026-02-18 17:25:44] >>> regimes.label                   99.023s ( 14.9%)
[2026-02-18 17:25:44] >>> outputs.forecasting             98.594s ( 14.8%)
[2026-02-18 17:25:44] >>> models.quality_check            86.980s ( 13.1%)
[2026-02-18 17:25:44] >>> calibrate                       52.025s (  7.8%)
[2026-02-18 17:25:44] >>> features.build                  45.710s (  6.9%)
[2026-02-18 17:25:44] >>> features.impute                 40.156s (  6.0%)
[2026-02-18 17:25:44] >>> seasonality.detect              37.896s (  5.7%)
[2026-02-18 17:25:44] >>> score.detector_score            23.374s (  3.5%)
[2026-02-18 17:25:44] >>> outputs.comprehensive_analytics  21.297s (  3.2%)
[2026-02-18 17:25:44] >>> load_data                       18.836s (  2.8%)
[2026-02-18 17:25:44] >>> models.load                     12.493s (  1.9%)
[2026-02-18 17:25:44] >>> fusion                          11.894s (  1.8%)
[2026-02-18 17:25:44] >>> models.persistence.save         11.611s (  1.7%)
[2026-02-18 17:25:44] >>> persist.sensor_normalized_ts    10.166s (  1.5%)
[2026-02-18 17:25:44] >>> sql.culprits                     7.980s (  1.2%)
[2026-02-18 17:25:44] >>> persist.write_scores             7.756s (  1.2%)
[2026-02-18 17:25:44] >>> data.guardrails                  7.164s (  1.1%)
[2026-02-18 17:25:44] >>> sql.pca                          5.641s (  0.8%)
[2026-02-18 17:25:44] >>> sensor.context                   5.476s (  0.8%)
[2026-02-18 17:25:44] >>> persist.write_episodes           4.086s (  0.6%)
[2026-02-18 17:25:44] >>> regimes.transient_detection      3.431s (  0.5%)
[2026-02-18 17:25:44] >>> persist.sensor_correlation       3.198s (  0.5%)
[2026-02-18 17:25:44] >>> features.hash                    2.822s (  0.4%)
[2026-02-18 17:25:44] >>> persist.seasonal_patterns        1.622s (  0.2%)
[2026-02-18 17:25:44] >>> regimes.occupancy                1.600s (  0.2%)
[2026-02-18 17:25:44] >>> data.contract                    1.587s (  0.2%)
[2026-02-18 17:25:44] >>> drift                            1.552s (  0.2%)
[2026-02-18 17:25:44] >>> persist.detector_correlation     0.910s (  0.1%)
[2026-02-18 17:25:44] >>> drift.controller                 0.883s (  0.1%)
[2026-02-18 17:25:44] >>> sql.run_stats                    0.612s (  0.1%)
[2026-02-18 17:25:44] >>> startup                          0.334s (  0.1%)
[2026-02-18 17:25:44] >>> baseline.seed                    0.094s (  0.0%)
[2026-02-18 17:25:44] >>> models.refit_flag                0.047s (  0.0%)
[2026-02-18 17:25:44] >>> baseline.buffer_write            0.043s (  0.0%)
[2026-02-18 17:25:44] >>> contribution.timeline            0.026s (  0.0%)
[2026-02-18 17:25:44] >>> thresholds.adaptive              0.022s (  0.0%)
[2026-02-18 17:25:44] >>> total_run                      665.864s

[2026-02-18 17:25:44] [INFO] [QA] Inspecting outputs for EquipID=5010, RunID=ED7FF586-0CB7-4FE5-8E7B-48F9D4BECF80 (from ACM_Runs), window=[2026-02-18 11:44:39.846876,2026-02-18 11:55:10.056666)
[2026-02-18 17:25:44] [INFO] [QA] ACM_Scores_Wide: 5369 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_HealthTimeline: 5369 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_RegimeTimeline: 5369 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_EpisodeDiagnostics: 45 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_Episodes: 45 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_EpisodeMetrics: 0 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_SensorNormalized_TS: 10112 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_SensorCorrelations: 3160 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_DetectorCorrelation: 9 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_SeasonalPatterns: 99 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_HealthForecast: 168 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_FailureForecast: 168 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_RUL: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_DriftController: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_RegimeDefinitions: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_RegimeOccupancy: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_Run_Stats: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_PCA_Models: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_PCA_Loadings: 3160 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_PCA_Metrics: 1 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_SensorHotspots: 25 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [INFO] [QA] ACM_SensorDefects: 7 row(s) for EquipID=5010 (RunID scoped)
[2026-02-18 17:25:45] [SUCCESS] [BATCH] WFA_TURBINE_10: Batch 4 completed (outcome=OK)
[2026-02-18 17:25:45] [INFO] [BATCH]
WFA_TURBINE_10: Processed 4 batch(es)
[2026-02-18 17:25:45] [SUCCESS] [BATCH] WFA_TURBINE_10: Completed - 4 batch(es) processed
[2026-02-18 17:25:45] [INFO] [TIMING] WFA_TURBINE_10: Total time = 67m 18s
[2026-02-18 17:25:45] >>>
============================================================
[2026-02-18 17:25:45] [INFO] [TIMING] Overall execution time: 67m 18s
[2026-02-18 17:25:45] >>> ============================================================
[2026-02-18 17:25:45] [INFO] [PROFILE] Stopping and pushing profile data...
[2026-02-18 17:25:45] >>> --- Top CPU Functions ---
[2026-02-18 17:25:45] >>>    1. sql_batch_runner.SQLBatchRunner.process_equipment: 2359.4ms (1 calls)
[2026-02-18 17:25:45] >>>    2. sql_batch_runner.SQLBatchRunner._run_acm_batch: 2156.2ms (5 calls)
[2026-02-18 17:25:45] >>>    3. sql_batch_runner.SQLBatchRunner._process_batches: 1734.4ms (1 calls)
[2026-02-18 17:25:45] >>>    4. sql_batch_runner.SQLBatchRunner._process_coldstart: 546.9ms (1 calls)
[2026-02-18 17:25:45] >>>    5. threading.Event.wait: 468.8ms (1207 calls)
[2026-02-18 17:25:45] >>>    6. threading.Condition.wait: 468.8ms (1207 calls)
[2026-02-18 17:25:45] >>>    7. ansitowin32.StreamWrapper.write: 421.9ms (3020 calls)
[2026-02-18 17:25:45] >>>    8. ansitowin32.AnsiToWin32.write: 406.2ms (3020 calls)
[2026-02-18 17:25:45] >>>    9. sql_batch_runner.SQLBatchRunner._inspect_last_run_outputs: 171.9ms (5 calls)
[2026-02-18 17:25:45] >>>   10. observability._render_console: 140.6ms (169 calls)
[2026-02-18 17:25:45] [INFO] [PROFILE] Pushing cpu (67 stacks) to Pyroscope...
[2026-02-18 17:25:45] [SUCCESS] [PROFILE] cpu profile pushed successfully
[2026-02-18 17:25:46] [INFO] [PROFILE] Pushing alloc_objects (500 stacks) to Pyroscope...
[2026-02-18 17:25:46] [SUCCESS] [PROFILE] alloc_objects profile pushed successfully
[2026-02-18 17:25:47] [INFO] [PROFILE] Pushing alloc_space (500 stacks) to Pyroscope...
[2026-02-18 17:25:47] [SUCCESS] [PROFILE] alloc_space profile pushed successfully
[2026-02-18 17:25:47] [SUCCESS] [PROFILE] Profile data pushed to Pyroscope
[2026-02-18 17:25:47] [SUCCESS] [MAIN] BATCH RUNNER COMPLETED SUCCESSFULLY
[2026-02-18 17:25:47] >>> ============================================================
---
type: module
module: core.fuse
source: core/fuse.py
---

# core.fuse

Source file: `core/fuse.py`

Summary: Score fusion, calibration (global or per-regime), and episode detection.

## Imports from core
- [[modules/core.observability]]

## Top-level symbols
- [[functions/core.fuse.ContaminationFilterResult]] (line 28, class)
- [[functions/core.fuse.CalibrationContaminationFilter]] (line 43, class)
- [[functions/core.fuse.CalibrationContaminationFilter.__init__]] (line 76, method)
- [[functions/core.fuse.CalibrationContaminationFilter.filter]] (line 111, method)
- [[functions/core.fuse.CalibrationContaminationFilter._bypass_result]] (line 149, method)
- [[functions/core.fuse.CalibrationContaminationFilter._filter_iqr]] (line 165, method)
- [[functions/core.fuse.CalibrationContaminationFilter._filter_z_trim]] (line 204, method)
- [[functions/core.fuse.CalibrationContaminationFilter._filter_iterative_mad]] (line 236, method)
- [[functions/core.fuse.CalibrationContaminationFilter._filter_hybrid]] (line 314, method)
- [[functions/core.fuse.CalibrationContaminationFilter._apply_exclusion_with_guards]] (line 375, method)
- [[functions/core.fuse.tune_detector_weights]] (line 454, function)
- [[functions/core.fuse.ScoreCalibrator]] (line 1013, class)
- [[functions/core.fuse.ScoreCalibrator.__init__]] (line 1021, method)
- [[functions/core.fuse.ScoreCalibrator.to_dict]] (line 1035, method)
- [[functions/core.fuse.ScoreCalibrator.from_dict]] (line 1045, method)
- [[functions/core.fuse.ScoreCalibrator.fit]] (line 1057, method)
- [[functions/core.fuse.ScoreCalibrator.transform]] (line 1216, method)
- [[functions/core.fuse.ScoreCalibrator.transform_with_raw]] (line 1255, method)
- [[functions/core.fuse.build_per_regime_threshold_rows]] (line 1296, function)
- [[functions/core.fuse.build_threshold_rows]] (line 1321, function)
- [[functions/core.fuse.build_calibration_summary_rows]] (line 1354, function)
- [[functions/core.fuse.persist_threshold_artifacts]] (line 1374, function)
- [[functions/core.fuse.apply_contamination_filter_config]] (line 1405, function)
- [[functions/core.fuse.choose_pca_cache_for_calibration]] (line 1434, function)
- [[functions/core.fuse.compute_and_set_adaptive_clip]] (line 1454, function)
- [[functions/core.fuse.compute_pca_train_percentiles]] (line 1498, function)
- [[functions/core.fuse.collect_enabled_calibrators]] (line 1527, function)
- [[functions/core.fuse.write_calibration_summary_safe]] (line 1562, function)
- [[functions/core.fuse.CalibrationStageResult]] (line 1590, class)
- [[functions/core.fuse.run_calibration_stage]] (line 1602, function)
- [[functions/core.fuse.EpisodeParams]] (line 1738, class)
- [[functions/core.fuse.Fuser]] (line 1765, class)
- [[functions/core.fuse.Fuser.__init__]] (line 1766, method)
- [[functions/core.fuse.Fuser._sanitize]] (line 1771, method)
- [[functions/core.fuse.Fuser._get_base_sensor]] (line 1783, method)
- [[functions/core.fuse.Fuser.fuse]] (line 1789, method)
- [[functions/core.fuse.Fuser.detect_episodes]] (line 1839, method)
- [[functions/core.fuse.compute_episode_params]] (line 2194, function)
- [[functions/core.fuse.compute_discounted_weights]] (line 2284, function)
- [[functions/core.fuse.normalize_episodes_schema]] (line 2371, function)
- [[functions/core.fuse.FusionResult]] (line 2532, class)
- [[functions/core.fuse.prepare_fusion_inputs]] (line 2552, function)
- [[functions/core.fuse.run_fusion_pipeline]] (line 2589, function)
- [[functions/core.fuse.apply_fusion_result_and_record_metrics]] (line 2707, function)

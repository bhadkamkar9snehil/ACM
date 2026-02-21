---
type: module
module: core.fuse
source: core/fuse.py
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - module
---

# core.fuse

Source file: `core/fuse.py`

Summary: Score fusion, calibration (global or per-regime), and episode detection.

## Imports from core
- [[modules/core.observability|core.observability]]

## Top-level symbols
- [[functions/core.fuse.ContaminationFilterResult|core.fuse.ContaminationFilterResult]] (line 28, class)
- [[functions/core.fuse.CalibrationContaminationFilter|core.fuse.CalibrationContaminationFilter]] (line 43, class)
- [[functions/core.fuse.CalibrationContaminationFilter.__init__|core.fuse.CalibrationContaminationFilter.__init__]] (line 76, method)
- [[functions/core.fuse.CalibrationContaminationFilter.filter|core.fuse.CalibrationContaminationFilter.filter]] (line 111, method)
- [[functions/core.fuse.CalibrationContaminationFilter._bypass_result|core.fuse.CalibrationContaminationFilter._bypass_result]] (line 149, method)
- [[functions/core.fuse.CalibrationContaminationFilter._filter_iqr|core.fuse.CalibrationContaminationFilter._filter_iqr]] (line 165, method)
- [[functions/core.fuse.CalibrationContaminationFilter._filter_z_trim|core.fuse.CalibrationContaminationFilter._filter_z_trim]] (line 204, method)
- [[functions/core.fuse.CalibrationContaminationFilter._filter_iterative_mad|core.fuse.CalibrationContaminationFilter._filter_iterative_mad]] (line 236, method)
- [[functions/core.fuse.CalibrationContaminationFilter._filter_hybrid|core.fuse.CalibrationContaminationFilter._filter_hybrid]] (line 314, method)
- [[functions/core.fuse.CalibrationContaminationFilter._apply_exclusion_with_guards|core.fuse.CalibrationContaminationFilter._apply_exclusion_with_guards]] (line 375, method)
- [[functions/core.fuse.tune_detector_weights|core.fuse.tune_detector_weights]] (line 454, function)
- [[functions/core.fuse.ScoreCalibrator|core.fuse.ScoreCalibrator]] (line 1013, class)
- [[functions/core.fuse.ScoreCalibrator.__init__|core.fuse.ScoreCalibrator.__init__]] (line 1021, method)
- [[functions/core.fuse.ScoreCalibrator.to_dict|core.fuse.ScoreCalibrator.to_dict]] (line 1035, method)
- [[functions/core.fuse.ScoreCalibrator.from_dict|core.fuse.ScoreCalibrator.from_dict]] (line 1045, method)
- [[functions/core.fuse.ScoreCalibrator.fit|core.fuse.ScoreCalibrator.fit]] (line 1057, method)
- [[functions/core.fuse.ScoreCalibrator.transform|core.fuse.ScoreCalibrator.transform]] (line 1216, method)
- [[functions/core.fuse.ScoreCalibrator.transform_with_raw|core.fuse.ScoreCalibrator.transform_with_raw]] (line 1255, method)
- [[functions/core.fuse.build_per_regime_threshold_rows|core.fuse.build_per_regime_threshold_rows]] (line 1296, function)
- [[functions/core.fuse.build_threshold_rows|core.fuse.build_threshold_rows]] (line 1321, function)
- [[functions/core.fuse.build_calibration_summary_rows|core.fuse.build_calibration_summary_rows]] (line 1354, function)
- [[functions/core.fuse.EpisodeParams|core.fuse.EpisodeParams]] (line 1375, class)
- [[functions/core.fuse.Fuser|core.fuse.Fuser]] (line 1402, class)
- [[functions/core.fuse.Fuser.__init__|core.fuse.Fuser.__init__]] (line 1403, method)
- [[functions/core.fuse.Fuser._sanitize|core.fuse.Fuser._sanitize]] (line 1408, method)
- [[functions/core.fuse.Fuser._get_base_sensor|core.fuse.Fuser._get_base_sensor]] (line 1420, method)
- [[functions/core.fuse.Fuser.fuse|core.fuse.Fuser.fuse]] (line 1426, method)
- [[functions/core.fuse.Fuser.detect_episodes|core.fuse.Fuser.detect_episodes]] (line 1476, method)
- [[functions/core.fuse.compute_episode_params|core.fuse.compute_episode_params]] (line 1831, function)
- [[functions/core.fuse.compute_discounted_weights|core.fuse.compute_discounted_weights]] (line 1921, function)
- [[functions/core.fuse.normalize_episodes_schema|core.fuse.normalize_episodes_schema]] (line 2008, function)
- [[functions/core.fuse.FusionResult|core.fuse.FusionResult]] (line 2169, class)
- [[functions/core.fuse.prepare_fusion_inputs|core.fuse.prepare_fusion_inputs]] (line 2189, function)
- [[functions/core.fuse.run_fusion_pipeline|core.fuse.run_fusion_pipeline]] (line 2226, function)

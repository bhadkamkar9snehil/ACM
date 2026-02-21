---
type: function
id: core.detector_orchestrator.calibrate_all_detectors
module: core.detector_orchestrator
source: core/detector_orchestrator.py
line_start: 110
line_end: 181
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.detector_orchestrator.calibrate_all_detectors

Defined in: [[modules/core.detector_orchestrator|core.detector_orchestrator]]

Source: `core/detector_orchestrator.py:110`

Kind: `function`

Signature: `calibrate_all_detectors(train_frame: pd.DataFrame, score_frame: pd.DataFrame, cal_q: float, self_tune_cfg: Dict[str, Any], fit_regimes: Optional[np.ndarray], transform_regimes: Optional[np.ndarray], omr_enabled: bool=True, cached_calibration_params: Optional[Dict[str, Any]]=None)`

Summary: Fit calibrators on TRAIN data and transform SCORE data.

---
type: function
id: core.detector_orchestrator.score_all_detectors
module: core.detector_orchestrator
source: core/detector_orchestrator.py
line_start: 31
line_end: 107
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - function
---

# core.detector_orchestrator.score_all_detectors

Defined in: [[modules/core.detector_orchestrator|core.detector_orchestrator]]

Source: `core/detector_orchestrator.py:31`

Kind: `function`

Signature: `score_all_detectors(data: pd.DataFrame, ar1_detector: Optional[Any], pca_detector: Optional[Any], iforest_detector: Optional[Any], gmm_detector: Optional[Any], omr_detector: Optional[Any], ar1_enabled: bool=True, pca_enabled: bool=True, iforest_enabled: bool=True, gmm_enabled: bool=True, omr_enabled: bool=True, pca_cached: Optional[Tuple[np.ndarray, np.ndarray]]=None, return_omr_contributions: bool=True)`

Summary: Score all enabled detectors and return raw scores frame.

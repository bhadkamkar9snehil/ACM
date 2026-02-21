---
type: function
id: core.detector_orchestrator.fit_all_detectors
module: core.detector_orchestrator
source: core/detector_orchestrator.py
line_start: 184
line_end: 326
---

# core.detector_orchestrator.fit_all_detectors

Defined in: [[modules/core.detector_orchestrator|core.detector_orchestrator]]

Source: `core/detector_orchestrator.py:184`

Kind: `function`

Signature: `fit_all_detectors(train: pd.DataFrame, cfg: Dict[str, Any], ar1_enabled: bool, pca_enabled: bool, iforest_enabled: bool, gmm_enabled: bool, omr_enabled: bool, ar1_detector: Optional[Any]=None, pca_detector: Optional[Any]=None, iforest_detector: Optional[Any]=None, gmm_detector: Optional[Any]=None, omr_detector: Optional[Any]=None, output_manager: Optional[Any]=None, sql_client: Optional[Any]=None, run_id: Optional[str]=None, equip_id: int=0, equip: str='')`

Summary: Fit all enabled detectors that haven't been loaded from cache.

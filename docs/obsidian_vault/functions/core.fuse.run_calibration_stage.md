---
type: function
id: core.fuse.run_calibration_stage
module: core.fuse
source: core/fuse.py
line_start: 1602
line_end: 1734
---

# core.fuse.run_calibration_stage

Defined in: [[modules/core.fuse]]

Source: `core/fuse.py:1602`

Kind: `function`

Signature: `run_calibration_stage(*, train: pd.DataFrame, frame: pd.DataFrame, cfg: Dict[str, Any], regime_quality_ok: bool, train_regime_labels: Optional[np.ndarray], score_regime_labels: Optional[np.ndarray], pca_train_spe: Optional[np.ndarray], pca_train_t2: Optional[np.ndarray], detectors: Dict[str, Any], detector_flags: Dict[str, bool], cached_calibration_params: Optional[Dict[str, Any]], saved_model_version: Optional[int], score_all_detectors_fn: Callable[..., Tuple[pd.DataFrame, Optional[Any]]], calibrate_all_detectors_fn: Callable[..., Tuple[pd.DataFrame, Dict[str, Any]]], persist_calibration_params_fn: Optional[Callable[..., bool]]=None, output_manager: Optional[Any]=None, logger: Any=Console, equip: str='')`

Summary: Run calibration stage end-to-end while keeping behavior parity with acm.py.

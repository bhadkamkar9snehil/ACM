---
type: function
id: core.model_persistence.save_trained_models
module: core.model_persistence
source: core/model_persistence.py
line_start: 1525
line_end: 1634
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.model_persistence.save_trained_models

Defined in: [[modules/core.model_persistence|core.model_persistence]]

Source: `core/model_persistence.py:1525`

Kind: `function`

Signature: `save_trained_models(equip: str, sql_client: Optional[Any], equip_id: int, cfg: Dict[str, Any], train: 'pd.DataFrame', ar1_detector: Any, pca_detector: Any, iforest_detector: Any, gmm_detector: Any, omr_detector: Any, regime_model: Any, col_meds: Optional[Dict[str, float]], regime_quality_ok: bool, timing_sections: Optional[Dict[str, Any]]=None, run_id: str='', calibrators_dict: Optional[Dict[str, Any]]=None)`

Summary: Save all trained models with versioning and metadata.

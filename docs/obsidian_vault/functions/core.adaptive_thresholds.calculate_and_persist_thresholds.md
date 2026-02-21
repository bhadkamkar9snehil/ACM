---
type: function
id: core.adaptive_thresholds.calculate_and_persist_thresholds
module: core.adaptive_thresholds
source: core/adaptive_thresholds.py
line_start: 504
line_end: 616
---

# core.adaptive_thresholds.calculate_and_persist_thresholds

Defined in: [[modules/core.adaptive_thresholds]]

Source: `core/adaptive_thresholds.py:504`

Kind: `function`

Signature: `calculate_and_persist_thresholds(fused_scores: np.ndarray, cfg: Dict[str, Any], equip_id: int, output_manager: Optional[Any], train_index: Optional[pd.Index]=None, regime_labels: Optional[np.ndarray]=None, regime_quality_ok: bool=False)`

Summary: Calculate adaptive thresholds and persist to SQL.

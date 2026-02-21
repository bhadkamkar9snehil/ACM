---
type: function
id: core.adaptive_thresholds.maybe_update_adaptive_thresholds
module: core.adaptive_thresholds
source: core/adaptive_thresholds.py
line_start: 619
line_end: 666
---

# core.adaptive_thresholds.maybe_update_adaptive_thresholds

Defined in: [[modules/core.adaptive_thresholds|core.adaptive_thresholds]]

Source: `core/adaptive_thresholds.py:619`

Kind: `function`

Signature: `maybe_update_adaptive_thresholds(*, train_frame: pd.DataFrame, train_data: pd.DataFrame, cfg: Dict[str, Any], equip_id: int, output_manager: Optional[Any], coldstart_complete: bool, continuous_learning: bool, threshold_update_interval: int, regime_quality_ok: bool, logger: Any)`

Summary: Decide whether thresholds should be refreshed this run and persist if needed.

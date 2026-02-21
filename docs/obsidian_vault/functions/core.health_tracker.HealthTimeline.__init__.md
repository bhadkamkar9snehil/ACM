---
type: method
id: core.health_tracker.HealthTimeline.__init__
module: core.health_tracker
source: core/health_tracker.py
line_start: 121
line_end: 170
---

# core.health_tracker.HealthTimeline.__init__

Defined in: [[modules/core.health_tracker|core.health_tracker]]

Source: `core/health_tracker.py:121`

Kind: `method`

Signature: `__init__(self, sql_client: Optional[Any], equip_id: int, run_id: str, output_manager: Optional[Any]=None, min_train_samples: int=200, max_gap_hours: float=720.0, min_std_dev: float=1.0, max_std_dev: float=50.0, max_timeline_rows: int=10000, downsample_freq: str='15min', history_window_hours: float=2160.0)`

Summary: Initialize health timeline loader.

---
type: method
id: core.smart_coldstart.SmartColdstart.load_with_retry
module: core.smart_coldstart
source: core/smart_coldstart.py
line_start: 320
line_end: 479
---

# core.smart_coldstart.SmartColdstart.load_with_retry

Defined in: [[modules/core.smart_coldstart]]

Source: `core/smart_coldstart.py:320`

Kind: `method`

Signature: `load_with_retry(self, cfg: Dict[str, Any], equipment: str, start_time: Optional[pd.Timestamp], end_time: Optional[pd.Timestamp], output_manager, max_attempts: int=3, historical_replay: bool=False)`

Summary: Returns (train, score, meta, can_proceed).

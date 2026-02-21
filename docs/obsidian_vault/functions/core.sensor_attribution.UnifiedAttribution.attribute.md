---
type: method
id: core.sensor_attribution.UnifiedAttribution.attribute
module: core.sensor_attribution
source: core/sensor_attribution.py
line_start: 202
line_end: 260
---

# core.sensor_attribution.UnifiedAttribution.attribute

Defined in: [[modules/core.sensor_attribution|core.sensor_attribution]]

Source: `core/sensor_attribution.py:202`

Kind: `method`

Signature: `attribute(self, raw_data: pd.DataFrame, fused_z: float, sensor_cols: Optional[List[str]]=None, detector_outputs: Optional[Dict[str, pd.DataFrame]]=None, timestamp_col: str='Timestamp')`

Summary: Compute sensor contributions to an anomaly.

---
type: method
id: core.adaptive_thresholds.AdaptiveThresholdCalculator.calculate_fused_threshold
module: core.adaptive_thresholds
source: core/adaptive_thresholds.py
line_start: 70
line_end: 186
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - method
---

# core.adaptive_thresholds.AdaptiveThresholdCalculator.calculate_fused_threshold

Defined in: [[modules/core.adaptive_thresholds|core.adaptive_thresholds]]

Source: `core/adaptive_thresholds.py:70`

Kind: `method`

Signature: `calculate_fused_threshold(self, train_fused_z: Union[np.ndarray, pd.Series], method: str='quantile', confidence: float=0.997, regime_labels: Optional[Union[np.ndarray, pd.Series]]=None, fallback_threshold: float=3.0)`

Summary: Calculate adaptive threshold for FusedZ scores.

---
type: method
id: core.adaptive_thresholds.AdaptiveThresholdCalculator._calculate_per_regime
module: core.adaptive_thresholds
source: core/adaptive_thresholds.py
line_start: 188
line_end: 245
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.adaptive_thresholds.AdaptiveThresholdCalculator._calculate_per_regime

Defined in: [[modules/core.adaptive_thresholds|core.adaptive_thresholds]]

Source: `core/adaptive_thresholds.py:188`

Kind: `method`

Signature: `_calculate_per_regime(self, train_fused_z: np.ndarray, regime_labels: Union[np.ndarray, pd.Series], method: str, confidence: float, fallback_threshold: float)`

Summary: Calculate separate thresholds for each operating regime.

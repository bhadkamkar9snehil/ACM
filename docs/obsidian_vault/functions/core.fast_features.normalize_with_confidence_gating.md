---
type: function
id: core.fast_features.normalize_with_confidence_gating
module: core.fast_features
source: core/fast_features.py
line_start: 1048
line_end: 1158
---

# core.fast_features.normalize_with_confidence_gating

Defined in: [[modules/core.fast_features]]

Source: `core/fast_features.py:1048`

Kind: `function`

Signature: `normalize_with_confidence_gating(df: pd.DataFrame, sensor_cols: List[str], regime_labels: pd.Series, confidences: pd.Series, global_mean: pd.Series, global_std: pd.Series, regime_means: Optional[Dict[int, pd.Series]]=None, regime_stds: Optional[Dict[int, pd.Series]]=None, confidence_threshold: float=0.7)`

Summary: Convenience function for one-shot confidence-gated normalization.

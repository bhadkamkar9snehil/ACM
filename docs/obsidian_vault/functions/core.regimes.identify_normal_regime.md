---
type: function
id: core.regimes.identify_normal_regime
module: core.regimes
source: core/regimes.py
line_start: 1974
line_end: 2036
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.regimes.identify_normal_regime

Defined in: [[modules/core.regimes|core.regimes]]

Source: `core/regimes.py:1974`

Kind: `function`

Signature: `identify_normal_regime(regime_stats: Dict[int, Dict[str, Any]], min_dwell_fraction: float=0.15, max_median_fused: float=2.0)`

Summary: Identify the "Normal" operating regime using dwell time and anomaly score.

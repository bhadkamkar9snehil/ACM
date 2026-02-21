---
type: function
id: core.failure_probability.bootstrap_degradation_rate
module: core.failure_probability
source: core/failure_probability.py
line_start: 609
line_end: 728
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.failure_probability.bootstrap_degradation_rate

Defined in: [[modules/core.failure_probability|core.failure_probability]]

Source: `core/failure_probability.py:609`

Kind: `function`

Signature: `bootstrap_degradation_rate(health_series: np.ndarray, dt_hours: float=1.0, n_bootstrap: int=500, confidence_level: float=0.95)`

Summary: Compute degradation rate with bootstrap confidence intervals.

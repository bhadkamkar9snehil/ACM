---
type: function
id: core.failure_probability.health_to_failure_probability
module: core.failure_probability
source: core/failure_probability.py
line_start: 26
line_end: 71
---

# core.failure_probability.health_to_failure_probability

Defined in: [[modules/core.failure_probability|core.failure_probability]]

Source: `core/failure_probability.py:26`

Kind: `function`

Signature: `health_to_failure_probability(health_forecast: np.ndarray, failure_threshold: float=70.0, health_std: float=10.0)`

Summary: Convert health forecast to failure probability via normal CDF.

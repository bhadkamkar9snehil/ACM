---
type: function
id: core.confidence.compute_episode_confidence
module: core.confidence
source: core/confidence.py
line_start: 310
line_end: 373
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.confidence.compute_episode_confidence

Defined in: [[modules/core.confidence|core.confidence]]

Source: `core/confidence.py:310`

Kind: `function`

Signature: `compute_episode_confidence(episode_duration_seconds: float, peak_z: float, regime_confidence: float=1.0, maturity_state: str='CONVERGED', min_duration_seconds: float=60.0, rise_time_seconds: Optional[float]=None)`

Summary: Compute confidence for an episode detection.

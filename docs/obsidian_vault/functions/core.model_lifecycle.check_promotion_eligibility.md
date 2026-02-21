---
type: function
id: core.model_lifecycle.check_promotion_eligibility
module: core.model_lifecycle
source: core/model_lifecycle.py
line_start: 245
line_end: 297
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.model_lifecycle.check_promotion_eligibility

Defined in: [[modules/core.model_lifecycle|core.model_lifecycle]]

Source: `core/model_lifecycle.py:245`

Kind: `function`

Signature: `check_promotion_eligibility(state: ModelState, criteria: Optional[PromotionCriteria]=None)`

Summary: Check if a model in LEARNING state can be promoted to CONVERGED.

---
type: module
module: core.model_lifecycle
source: core/model_lifecycle.py
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - module
---

# core.model_lifecycle

Source file: `core/model_lifecycle.py`

Summary: Model Lifecycle Management for V11

## Imports from core
- [[modules/core.observability|core.observability]]

## Top-level symbols
- [[functions/core.model_lifecycle.MaturityState|core.model_lifecycle.MaturityState]] (line 39, class)
- [[functions/core.model_lifecycle.MaturityState.__str__|core.model_lifecycle.MaturityState.__str__]] (line 46, method)
- [[functions/core.model_lifecycle.PromotionCriteria|core.model_lifecycle.PromotionCriteria]] (line 66, class)
- [[functions/core.model_lifecycle.PromotionCriteria.from_config|core.model_lifecycle.PromotionCriteria.from_config]] (line 105, method)
- [[functions/core.model_lifecycle.ModelState|core.model_lifecycle.ModelState]] (line 127, class)
- [[functions/core.model_lifecycle.ModelState.silhouette_score|core.model_lifecycle.ModelState.silhouette_score]] (line 163, method)
- [[functions/core.model_lifecycle.ModelState.silhouette_score|core.model_lifecycle.ModelState.silhouette_score]] (line 167, method)
- [[functions/core.model_lifecycle.ModelState.total_days|core.model_lifecycle.ModelState.total_days]] (line 171, method)
- [[functions/core.model_lifecycle.ModelState.to_dict|core.model_lifecycle.ModelState.to_dict]] (line 175, method)
- [[functions/core.model_lifecycle._regime_quality_criterion_met|core.model_lifecycle._regime_quality_criterion_met]] (line 195, function)
- [[functions/core.model_lifecycle.check_promotion_eligibility|core.model_lifecycle.check_promotion_eligibility]] (line 245, function)
- [[functions/core.model_lifecycle.promote_model|core.model_lifecycle.promote_model]] (line 300, function)
- [[functions/core.model_lifecycle.deprecate_model|core.model_lifecycle.deprecate_model]] (line 323, function)
- [[functions/core.model_lifecycle.create_new_model_state|core.model_lifecycle.create_new_model_state]] (line 342, function)
- [[functions/core.model_lifecycle.update_model_state_from_run|core.model_lifecycle.update_model_state_from_run]] (line 400, function)
- [[functions/core.model_lifecycle.get_active_model_dict|core.model_lifecycle.get_active_model_dict]] (line 462, function)
- [[functions/core.model_lifecycle.load_model_state_from_sql|core.model_lifecycle.load_model_state_from_sql]] (line 506, function)

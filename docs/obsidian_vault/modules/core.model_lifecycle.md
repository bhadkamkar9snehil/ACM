---
type: module
module: core.model_lifecycle
source: core/model_lifecycle.py
generated_at: 2026-02-21T06:33:21+00:00
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
- [[functions/core.model_lifecycle.MaturityState|core.model_lifecycle.MaturityState]] (line 40, class)
- [[functions/core.model_lifecycle.MaturityState.__str__|core.model_lifecycle.MaturityState.__str__]] (line 47, method)
- [[functions/core.model_lifecycle.PromotionCriteria|core.model_lifecycle.PromotionCriteria]] (line 67, class)
- [[functions/core.model_lifecycle.PromotionCriteria.from_config|core.model_lifecycle.PromotionCriteria.from_config]] (line 106, method)
- [[functions/core.model_lifecycle.ModelState|core.model_lifecycle.ModelState]] (line 128, class)
- [[functions/core.model_lifecycle.ModelState.silhouette_score|core.model_lifecycle.ModelState.silhouette_score]] (line 164, method)
- [[functions/core.model_lifecycle.ModelState.silhouette_score|core.model_lifecycle.ModelState.silhouette_score]] (line 168, method)
- [[functions/core.model_lifecycle.ModelState.total_days|core.model_lifecycle.ModelState.total_days]] (line 172, method)
- [[functions/core.model_lifecycle.ModelState.to_dict|core.model_lifecycle.ModelState.to_dict]] (line 176, method)
- [[functions/core.model_lifecycle._regime_quality_criterion_met|core.model_lifecycle._regime_quality_criterion_met]] (line 196, function)
- [[functions/core.model_lifecycle.check_promotion_eligibility|core.model_lifecycle.check_promotion_eligibility]] (line 246, function)
- [[functions/core.model_lifecycle.promote_model|core.model_lifecycle.promote_model]] (line 301, function)
- [[functions/core.model_lifecycle.deprecate_model|core.model_lifecycle.deprecate_model]] (line 324, function)
- [[functions/core.model_lifecycle.create_new_model_state|core.model_lifecycle.create_new_model_state]] (line 343, function)
- [[functions/core.model_lifecycle.update_model_state_from_run|core.model_lifecycle.update_model_state_from_run]] (line 401, function)
- [[functions/core.model_lifecycle.update_and_persist_model_lifecycle|core.model_lifecycle.update_and_persist_model_lifecycle]] (line 463, function)
- [[functions/core.model_lifecycle.update_and_persist_model_lifecycle_safe|core.model_lifecycle.update_and_persist_model_lifecycle_safe]] (line 611, function)
- [[functions/core.model_lifecycle.load_model_state_safe|core.model_lifecycle.load_model_state_safe]] (line 653, function)
- [[functions/core.model_lifecycle.get_active_model_dict|core.model_lifecycle.get_active_model_dict]] (line 676, function)
- [[functions/core.model_lifecycle.load_model_state_from_sql|core.model_lifecycle.load_model_state_from_sql]] (line 720, function)

---
type: module
module: core.omr
source: core/omr.py
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - module
---

# core.omr

Source file: `core/omr.py`

Summary: Overall Model Residual (OMR) - Multivariate health indicator.

## Imports from core
- none

## Top-level symbols
- [[functions/core.omr.ModelType|core.omr.ModelType]] (line 29, class)
- [[functions/core.omr.OMRModel|core.omr.OMRModel]] (line 38, class)
- [[functions/core.omr.OMRModel.to_dict|core.omr.OMRModel.to_dict]] (line 52, method)
- [[functions/core.omr.OMRDetector|core.omr.OMRDetector]] (line 91, class)
- [[functions/core.omr.OMRDetector.__init__|core.omr.OMRDetector.__init__]] (line 118, method)
- [[functions/core.omr.OMRDetector._select_model_type|core.omr.OMRDetector._select_model_type]] (line 145, method)
- [[functions/core.omr.OMRDetector._validate_input|core.omr.OMRDetector._validate_input]] (line 170, method)
- [[functions/core.omr.OMRDetector._prepare_data|core.omr.OMRDetector._prepare_data]] (line 193, method)
- [[functions/core.omr.OMRDetector._compute_optimal_components|core.omr.OMRDetector._compute_optimal_components]] (line 228, method)
- [[functions/core.omr.OMRDetector._fit_pls_model|core.omr.OMRDetector._fit_pls_model]] (line 261, method)
- [[functions/core.omr.OMRDetector._fit_linear_model|core.omr.OMRDetector._fit_linear_model]] (line 268, method)
- [[functions/core.omr.OMRDetector._fit_pca_model|core.omr.OMRDetector._fit_pca_model]] (line 293, method)
- [[functions/core.omr.OMRDetector.fit|core.omr.OMRDetector.fit]] (line 300, method)
- [[functions/core.omr.OMRDetector._reconstruct_data|core.omr.OMRDetector._reconstruct_data]] (line 424, method)
- [[functions/core.omr.OMRDetector.score|core.omr.OMRDetector.score]] (line 459, method)
- [[functions/core.omr.OMRDetector.get_top_contributors|core.omr.OMRDetector.get_top_contributors]] (line 613, method)
- [[functions/core.omr.OMRDetector.get_diagnostics|core.omr.OMRDetector.get_diagnostics]] (line 638, method)
- [[functions/core.omr.OMRDetector.to_dict|core.omr.OMRDetector.to_dict]] (line 658, method)
- [[functions/core.omr.OMRDetector.from_dict|core.omr.OMRDetector.from_dict]] (line 668, method)

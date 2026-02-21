---
type: module
module: core.seasonality
source: core/seasonality.py
generated_at: 2026-02-21T06:37:09+00:00
---

# core.seasonality

Source file: `core/seasonality.py`

Summary: Seasonality Handler for ACM v11.0.0 (P5.9)

## Imports from core
- none

## Top-level symbols
- [[functions/core.seasonality.PatternType|core.seasonality.PatternType]] (line 44, class)
- [[functions/core.seasonality.SeasonalPattern|core.seasonality.SeasonalPattern]] (line 53, class)
- [[functions/core.seasonality.SeasonalPattern.to_dict|core.seasonality.SeasonalPattern.to_dict]] (line 71, method)
- [[functions/core.seasonality.SeasonalAdjustment|core.seasonality.SeasonalAdjustment]] (line 84, class)
- [[functions/core.seasonality.SeasonalAdjustment.to_dict|core.seasonality.SeasonalAdjustment.to_dict]] (line 100, method)
- [[functions/core.seasonality.SeasonalitySummary|core.seasonality.SeasonalitySummary]] (line 112, class)
- [[functions/core.seasonality.SeasonalitySummary.to_dict|core.seasonality.SeasonalitySummary.to_dict]] (line 128, method)
- [[functions/core.seasonality.SeasonalityHandler|core.seasonality.SeasonalityHandler]] (line 139, class)
- [[functions/core.seasonality.SeasonalityHandler.__init__|core.seasonality.SeasonalityHandler.__init__]] (line 153, method)
- [[functions/core.seasonality.SeasonalityHandler.detect_patterns|core.seasonality.SeasonalityHandler.detect_patterns]] (line 169, method)
- [[functions/core.seasonality.SeasonalityHandler._detect_periodic_pattern|core.seasonality.SeasonalityHandler._detect_periodic_pattern]] (line 231, method)
- [[functions/core.seasonality.SeasonalityHandler.get_seasonal_offset|core.seasonality.SeasonalityHandler.get_seasonal_offset]] (line 313, method)
- [[functions/core.seasonality.SeasonalityHandler.adjust_baseline|core.seasonality.SeasonalityHandler.adjust_baseline]] (line 357, method)
- [[functions/core.seasonality.SeasonalityHandler._compute_pattern_offset|core.seasonality.SeasonalityHandler._compute_pattern_offset]] (line 411, method)
- [[functions/core.seasonality.SeasonalityHandler.get_summary|core.seasonality.SeasonalityHandler.get_summary]] (line 428, method)
- [[functions/core.seasonality.SeasonalityHandler.clear_patterns|core.seasonality.SeasonalityHandler.clear_patterns]] (line 460, method)
- [[functions/core.seasonality.SeasonalityHandler.has_patterns|core.seasonality.SeasonalityHandler.has_patterns]] (line 464, method)
- [[functions/core.seasonality.SeasonalityHandler.get_pattern_strength|core.seasonality.SeasonalityHandler.get_pattern_strength]] (line 478, method)
- [[functions/core.seasonality.detect_and_adjust|core.seasonality.detect_and_adjust]] (line 498, function)
- [[functions/core.seasonality.detect_and_adjust_safe|core.seasonality.detect_and_adjust_safe]] (line 562, function)

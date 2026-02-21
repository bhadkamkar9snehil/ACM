---
type: module
module: core.health_tracker
source: core/health_tracker.py
---

# core.health_tracker

Source file: `core/health_tracker.py`

Summary: Health Timeline Loader and Quality Assessment (v10.0.0)

## Imports from core
- [[modules/core.observability|core.observability]]

## Top-level symbols
- [[functions/core.health_tracker.HealthQuality|core.health_tracker.HealthQuality]] (line 32, class)
- [[functions/core.health_tracker.HealthStatistics|core.health_tracker.HealthStatistics]] (line 43, class)
- [[functions/core.health_tracker.DataSummary|core.health_tracker.DataSummary]] (line 62, class)
- [[functions/core.health_tracker.HealthTimeline|core.health_tracker.HealthTimeline]] (line 87, class)
- [[functions/core.health_tracker.HealthTimeline.__init__|core.health_tracker.HealthTimeline.__init__]] (line 121, method)
- [[functions/core.health_tracker.HealthTimeline.load_from_sql|core.health_tracker.HealthTimeline.load_from_sql]] (line 172, method)
- [[functions/core.health_tracker.HealthTimeline._normalize_columns|core.health_tracker.HealthTimeline._normalize_columns]] (line 271, method)
- [[functions/core.health_tracker.HealthTimeline._apply_row_limit|core.health_tracker.HealthTimeline._apply_row_limit]] (line 296, method)
- [[functions/core.health_tracker.HealthTimeline.quality_check|core.health_tracker.HealthTimeline.quality_check]] (line 310, method)
- [[functions/core.health_tracker.HealthTimeline.get_statistics|core.health_tracker.HealthTimeline.get_statistics]] (line 352, method)
- [[functions/core.health_tracker.HealthTimeline._get_quality_reason|core.health_tracker.HealthTimeline._get_quality_reason]] (line 421, method)
- [[functions/core.health_tracker.HealthTimeline.get_data_summary|core.health_tracker.HealthTimeline.get_data_summary]] (line 436, method)
- [[functions/core.health_tracker.HealthTimeline.detect_regime_shift|core.health_tracker.HealthTimeline.detect_regime_shift]] (line 502, method)

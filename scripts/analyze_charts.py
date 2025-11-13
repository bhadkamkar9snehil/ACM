#!/usr/bin/env python3
"""
Comprehensive Chart Analysis and Optimization Plan
Run: 20251105_010417 (15 charts generated, 3.316s, 10.6% of runtime)
"""

import os
from pathlib import Path

chart_dir = Path("artifacts/FD_FAN/run_20251105_010417/charts")

print("="*70)
print("CHART ANALYSIS & OPTIMIZATION PLAN")
print("="*70)
print(f"\n📊 Run: 20251105_010417")
print(f"📈 Charts generated: 15")
print(f"⏱️  Time: 3.316s (10.6% of total runtime)")
print(f"📁 Location: {chart_dir}")

charts = [
    "contribution_bars.png",
    "defect_dashboard.png", 
    "defect_severity.png",
    "detector_comparison.png",
    "episodes_timeline.png",
    "health_distribution_over_time.png",
    "health_timeline.png",
    "regime_distribution.png",
    "regime_scatter.png",
    "sensor_anomaly_heatmap.png",
    "sensor_daily_profile.png",
    "sensor_defect_heatmap.png",
    "sensor_hotspots.png",
    "sensor_sparklines.png",
    "sensor_timeseries_events.png"
]

print("\n" + "="*70)
print("CHART CATEGORIZATION & ASSESSMENT")
print("="*70)

high_value = {
    "defect_dashboard.png": "Quick KPI overview - very useful for triage",
    "detector_comparison.png": "Shows detector behavior over time - essential for debugging",
    "episodes_timeline.png": "Visual episode summary - high value",
    "health_timeline.png": "Health trend over time - critical for monitoring",
    "sensor_anomaly_heatmap.png": "Identifies problematic sensors - high diagnostic value"
}

medium_value = {
    "contribution_bars.png": "Snapshot detector contribution - useful but static",
    "defect_severity.png": "Episode severity distribution - moderate value",
    "regime_distribution.png": "Regime balance - useful for understanding states",
    "regime_scatter.png": "Regime vs anomaly score - good visualization",
    "sensor_daily_profile.png": "Diurnal pattern detection - moderate value"
}

low_value = {
    "health_distribution_over_time.png": "Heatmap of health by date/hour - niche use",
    "sensor_defect_heatmap.png": "Sensor vs severity matrix - only useful with many episodes",
    "sensor_hotspots.png": "Top anomalous sensors - likely redundant with heatmap",
    "sensor_sparklines.png": "Mini sensor timeseries - hard to read, low utility",
    "sensor_timeseries_events.png": "Full sensor plots - very slow to generate, often unclear"
}

print("\n🟢 HIGH VALUE CHARTS (5) - Keep and potentially improve:")
for chart, desc in high_value.items():
    status = "✓" if (chart_dir / chart).exists() else "✗"
    print(f"  {status} {chart:40s} | {desc}")

print("\n🟡 MEDIUM VALUE CHARTS (5) - Keep but consider simplifying:")
for chart, desc in medium_value.items():
    status = "✓" if (chart_dir / chart).exists() else "✗"
    print(f"  {status} {chart:40s} | {desc}")

print("\n🔴 LOW VALUE CHARTS (5) - Consider removing:")
for chart, desc in low_value.items():
    status = "✓" if (chart_dir / chart).exists() else "✗"
    print(f"  {status} {chart:40s} | {desc}")

print("\n" + "="*70)
print("OPTIMIZATION RECOMMENDATIONS")
print("="*70)

print("\n📌 TIER 1 - Remove Low-Value Charts (saves ~1.0-1.5s)")
print("   - Remove: sensor_timeseries_events.png (slowest, least clear)")
print("   - Remove: sensor_sparklines.png (too small to read)")
print("   - Remove: sensor_hotspots.png (redundant with heatmap)")
print("   - Keep as optional: health_distribution_over_time.png, sensor_defect_heatmap.png")

print("\n📌 TIER 2 - Improve High-Value Charts")
print("   ✓ defect_dashboard.png: Add regime distribution stats")
print("   ✓ detector_comparison.png: Add episode markers/shading")
print("   ✓ health_timeline.png: Add regime overlay")
print("   ✓ episodes_timeline.png: Add severity color legend")

print("\n📌 TIER 3 - Consolidation Opportunities")
print("   • Merge contribution_bars.png + detector_comparison.png into single figure")
print("   • Merge regime_distribution.png + regime_scatter.png into single 2-panel figure")
print("   • Make chart generation more selective based on data characteristics:")
print("     - Skip sensor_defect_heatmap if <5 episodes")
print("     - Skip regime charts if k=1 (homogeneous data)")

print("\n📌 TIER 4 - Performance Optimizations")
print("   • Use lower sampling rates for timeseries (current: step=max(1, len/2000))")
print("   • Reduce DPI from 150 to 100 for non-critical charts")
print("   • Skip heavy computations (rolling windows) on large datasets")

print("\n" + "="*70)
print("EXPECTED IMPROVEMENTS")
print("="*70)
print("\n📊 Current: 15 charts, 3.316s (10.6% of runtime)")
print("🎯 Target: 8-10 charts, ~1.5s (5% of runtime)")
print("💡 Approach:")
print("   1. Remove 3 low-value charts immediately: -1.0s")
print("   2. Consolidate 2 pairs into combined figures: -0.4s")  
print("   3. Optimize sampling/DPI: -0.4s")
print("   4. Total savings: ~1.8s (55% reduction)")

print("\n" + "="*70)
print("IMPLEMENTATION PRIORITY")
print("="*70)
print("\n1️⃣ Quick Win: Remove sensor_timeseries_events.png (saves ~0.5s)")
print("2️⃣ Quick Win: Remove sensor_sparklines.png (saves ~0.2s)")
print("3️⃣ Quick Win: Remove sensor_hotspots.png (saves ~0.2s)")
print("4️⃣ Enhancement: Add episode markers to detector_comparison.png")
print("5️⃣ Enhancement: Add regime overlay to health_timeline.png")
print("6️⃣ Consolidation: Merge regime charts into single figure")

print("\n" + "="*70)

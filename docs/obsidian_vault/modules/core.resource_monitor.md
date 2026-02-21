---
type: module
module: core.resource_monitor
source: core/resource_monitor.py
generated_at: 2026-02-21T06:37:09+00:00
---

# core.resource_monitor

Source file: `core/resource_monitor.py`

Summary: Resource Monitor for ACM - Tracks CPU, memory, and timing metrics.

## Imports from core
- none

## Top-level symbols
- [[functions/core.resource_monitor.enable_resource_metrics|core.resource_monitor.enable_resource_metrics]] (line 60, function)
- [[functions/core.resource_monitor.set_resource_equipment|core.resource_monitor.set_resource_equipment]] (line 76, function)
- [[functions/core.resource_monitor.get_gpu_info|core.resource_monitor.get_gpu_info]] (line 86, function)
- [[functions/core.resource_monitor.get_cpu_per_core|core.resource_monitor.get_cpu_per_core]] (line 128, function)
- [[functions/core.resource_monitor.get_system_info|core.resource_monitor.get_system_info]] (line 138, function)
- [[functions/core.resource_monitor.get_disk_io|core.resource_monitor.get_disk_io]] (line 162, function)
- [[functions/core.resource_monitor.SectionMetrics|core.resource_monitor.SectionMetrics]] (line 181, class)
- [[functions/core.resource_monitor.SectionMetrics.finalize|core.resource_monitor.SectionMetrics.finalize]] (line 212, method)
- [[functions/core.resource_monitor.ResourceMonitor|core.resource_monitor.ResourceMonitor]] (line 222, class)
- [[functions/core.resource_monitor.ResourceMonitor.__init__|core.resource_monitor.ResourceMonitor.__init__]] (line 239, method)
- [[functions/core.resource_monitor.ResourceMonitor.start_run|core.resource_monitor.ResourceMonitor.start_run]] (line 267, method)
- [[functions/core.resource_monitor.ResourceMonitor._get_memory_rss|core.resource_monitor.ResourceMonitor._get_memory_rss]] (line 275, method)
- [[functions/core.resource_monitor.ResourceMonitor._get_cpu_percent|core.resource_monitor.ResourceMonitor._get_cpu_percent]] (line 284, method)
- [[functions/core.resource_monitor.ResourceMonitor._start_cpu_sampling|core.resource_monitor.ResourceMonitor._start_cpu_sampling]] (line 293, method)
- [[functions/core.resource_monitor.ResourceMonitor._stop_cpu_sampling|core.resource_monitor.ResourceMonitor._stop_cpu_sampling]] (line 320, method)
- [[functions/core.resource_monitor.ResourceMonitor.section|core.resource_monitor.ResourceMonitor.section]] (line 327, method)
- [[functions/core.resource_monitor.ResourceMonitor.record|core.resource_monitor.ResourceMonitor.record]] (line 408, method)
- [[functions/core.resource_monitor.ResourceMonitor.get_metrics|core.resource_monitor.ResourceMonitor.get_metrics]] (line 431, method)
- [[functions/core.resource_monitor.ResourceMonitor.get_summary|core.resource_monitor.ResourceMonitor.get_summary]] (line 452, method)
- [[functions/core.resource_monitor.ResourceMonitor.print_summary|core.resource_monitor.ResourceMonitor.print_summary]] (line 468, method)
- [[functions/core.resource_monitor.ResourceMonitor.to_dataframe|core.resource_monitor.ResourceMonitor.to_dataframe]] (line 490, method)
- [[functions/core.resource_monitor.ResourceMonitor.write_to_sql|core.resource_monitor.ResourceMonitor.write_to_sql]] (line 517, method)
- [[functions/core.resource_monitor.ResourceMonitor.reset|core.resource_monitor.ResourceMonitor.reset]] (line 549, method)
- [[functions/core.resource_monitor.ResourceMonitor.record_gpu_metrics|core.resource_monitor.ResourceMonitor.record_gpu_metrics]] (line 559, method)
- [[functions/core.resource_monitor.ResourceMonitor.record_capacity_metrics|core.resource_monitor.ResourceMonitor.record_capacity_metrics]] (line 586, method)
- [[functions/core.resource_monitor.ResourceMonitor.record_cpu_per_core|core.resource_monitor.ResourceMonitor.record_cpu_per_core]] (line 612, method)
- [[functions/core.resource_monitor.get_full_system_info|core.resource_monitor.get_full_system_info]] (line 636, function)

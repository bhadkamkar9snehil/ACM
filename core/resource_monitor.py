"""
Resource Monitor for ACM - Tracks CPU, memory, and timing metrics.

Integrates with OTEL metrics for Prometheus export.

Usage:
    from core.resource_monitor import ResourceMonitor, R

    # Global singleton (like Timer T)
    R = ResourceMonitor()

    # Context manager for sections
    with R.section("detector.fit.gmm"):
        gmm_detector.fit(train)

    # Get metrics
    metrics = R.get_metrics()
    R.write_to_sql(sql_client, equip_id, run_id)

    # Reset for next run
    R.reset()
"""

import os
import time
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# GPU monitoring (optional - requires pynvml/nvidia-ml-py)
try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
    GPU_COUNT = pynvml.nvmlDeviceGetCount()
except Exception:
    GPU_AVAILABLE = False
    GPU_COUNT = 0

import pandas as pd

# OTEL metrics integration (lazy loaded)
_otel_enabled = False
_record_memory_fn: Optional[Callable] = None
_record_cpu_fn: Optional[Callable] = None
_record_gpu_fn: Optional[Callable] = None
_record_capacity_fn: Optional[Callable] = None
_record_disk_io_fn: Optional[Callable] = None
_equipment_context: str = ""


def enable_resource_metrics(equipment: str = "") -> None:
    """Enable OTEL metrics recording for ResourceMonitor."""
    global _otel_enabled, _record_memory_fn, _record_cpu_fn, _record_gpu_fn, _record_capacity_fn, _record_disk_io_fn, _equipment_context
    try:
        from core.observability import record_memory, record_cpu, record_gpu, record_capacity, record_disk_io
        _record_memory_fn = record_memory
        _record_cpu_fn = record_cpu
        _record_gpu_fn = record_gpu
        _record_capacity_fn = record_capacity
        _record_disk_io_fn = record_disk_io
        _otel_enabled = True
        _equipment_context = equipment
    except ImportError:
        _otel_enabled = False


def set_resource_equipment(equipment: str) -> None:
    """Set the equipment context for resource metrics."""
    global _equipment_context
    _equipment_context = equipment


# =============================================================================
# GPU Monitoring Utilities
# =============================================================================

def get_gpu_info() -> List[Dict[str, Any]]:
    """Get GPU usage information for all available GPUs.
    
    Returns:
        List of dicts with gpu_id, name, memory_used_mb, memory_total_mb, 
        memory_percent, utilization_percent, temperature_c
    """
    if not GPU_AVAILABLE:
        return []
    
    gpu_info = []
    try:
        for i in range(GPU_COUNT):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            
            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                temp = 0
            
            gpu_info.append({
                "gpu_id": i,
                "name": name,
                "memory_used_mb": mem_info.used / (1024 * 1024),
                "memory_total_mb": mem_info.total / (1024 * 1024),
                "memory_percent": (mem_info.used / mem_info.total) * 100 if mem_info.total > 0 else 0,
                "utilization_percent": util.gpu,
                "memory_utilization_percent": util.memory,
                "temperature_c": temp
            })
    except Exception:
        pass
    
    return gpu_info


def get_cpu_per_core() -> List[float]:
    """Get CPU usage percentage for each core."""
    if not PSUTIL_AVAILABLE:
        return []
    try:
        return psutil.cpu_percent(percpu=True, interval=0.0)
    except Exception:
        return []


def get_system_info() -> Dict[str, Any]:
    """Get system hardware info for capacity planning."""
    info = {
        "cpu_count_logical": 0,
        "cpu_count_physical": 0,
        "memory_total_gb": 0,
        "gpu_count": GPU_COUNT,
        "gpu_memory_total_gb": 0,
    }
    
    if PSUTIL_AVAILABLE:
        info["cpu_count_logical"] = psutil.cpu_count(logical=True) or 0
        info["cpu_count_physical"] = psutil.cpu_count(logical=False) or 0
        info["memory_total_gb"] = psutil.virtual_memory().total / (1024**3)
    
    if GPU_AVAILABLE:
        total_gpu_mem = 0
        for gpu in get_gpu_info():
            total_gpu_mem += gpu.get("memory_total_mb", 0)
        info["gpu_memory_total_gb"] = total_gpu_mem / 1024
    
    return info


def get_disk_io() -> Dict[str, int]:
    """Get current disk I/O counters."""
    if not PSUTIL_AVAILABLE:
        return {"read_bytes": 0, "write_bytes": 0, "read_count": 0, "write_count": 0}
    try:
        io = psutil.disk_io_counters()
        if io:
            return {
                "read_bytes": io.read_bytes,
                "write_bytes": io.write_bytes,
                "read_count": io.read_count,
                "write_count": io.write_count,
            }
    except Exception:
        pass
    return {"read_bytes": 0, "write_bytes": 0, "read_count": 0, "write_count": 0}


@dataclass
class SectionMetrics:
    """Metrics captured for a single code section."""
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_s: float = 0.0
    
    # Memory metrics (bytes)
    mem_start_rss: int = 0
    mem_end_rss: int = 0
    mem_peak_rss: int = 0
    mem_delta_mb: float = 0.0
    
    # CPU metrics
    cpu_percent_avg: float = 0.0
    cpu_samples: List[float] = field(default_factory=list)
    
    # Thread count
    thread_count: int = 0
    
    # Disk I/O metrics (bytes)
    disk_read_start: int = 0
    disk_read_end: int = 0
    disk_write_start: int = 0
    disk_write_end: int = 0
    disk_read_mb: float = 0.0
    disk_write_mb: float = 0.0
    
    # Nested depth (for hierarchy)
    depth: int = 0
    
    def finalize(self):
        """Calculate derived metrics after section completes."""
        self.duration_s = self.end_time - self.start_time
        self.mem_delta_mb = (self.mem_end_rss - self.mem_start_rss) / (1024 * 1024)
        self.disk_read_mb = (self.disk_read_end - self.disk_read_start) / (1024 * 1024)
        self.disk_write_mb = (self.disk_write_end - self.disk_write_start) / (1024 * 1024)
        if self.cpu_samples:
            self.cpu_percent_avg = sum(self.cpu_samples) / len(self.cpu_samples)


class ResourceMonitor:
    """
    Lightweight resource monitor for ACM pipeline sections.
    
    Tracks:
    - Wall-clock time (always)
    - Memory RSS delta (if psutil available)
    - CPU usage samples (if psutil available, background thread)
    - Peak memory per section
    
    Design goals:
    - Minimal overhead (<1% runtime impact)
    - Non-blocking CPU sampling via background thread
    - Compatible with existing Timer (T) pattern
    - SQL output for Grafana dashboards
    """
    
    def __init__(self, sample_interval: float = 0.5, enabled: bool = True):
        """
        Initialize resource monitor.
        
        Args:
            sample_interval: CPU sampling interval in seconds (default 0.5s)
            enabled: Whether monitoring is active (can disable for production)
        """
        self.enabled = enabled and PSUTIL_AVAILABLE
        self.sample_interval = sample_interval
        self._sections: Dict[str, SectionMetrics] = {}
        self._section_order: List[str] = []
        self._active_stack: List[str] = []
        self._lock = threading.Lock()
        
        # Background CPU sampler
        self._sampling = False
        self._sampler_thread: Optional[threading.Thread] = None
        self._current_section: Optional[str] = None
        
        # Process handle
        self._process = psutil.Process() if PSUTIL_AVAILABLE else None
        
        # Run-level aggregates
        self._run_start_time: float = 0.0
        self._run_start_mem: int = 0
        self._peak_mem_rss: int = 0
    
    def start_run(self):
        """Mark the start of an ACM run for aggregate metrics."""
        if not self.enabled:
            return
        self._run_start_time = time.perf_counter()
        self._run_start_mem = self._get_memory_rss()
        self._peak_mem_rss = self._run_start_mem
    
    def _get_memory_rss(self) -> int:
        """Get current RSS memory in bytes."""
        if self._process:
            try:
                return self._process.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return 0
        return 0
    
    def _get_cpu_percent(self) -> float:
        """Get current CPU percent (0-100 per core)."""
        if self._process:
            try:
                return self._process.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return 0.0
        return 0.0
    
    def _start_cpu_sampling(self, section_name: str):
        """Start background CPU sampling for a section."""
        if not self.enabled:
            return
        
        self._current_section = section_name
        self._sampling = True
        
        def sampler():
            # Prime the CPU percent counter
            self._get_cpu_percent()
            while self._sampling and self._current_section == section_name:
                time.sleep(self.sample_interval)
                if self._sampling and self._current_section == section_name:
                    cpu = self._get_cpu_percent()
                    mem = self._get_memory_rss()
                    with self._lock:
                        if section_name in self._sections:
                            self._sections[section_name].cpu_samples.append(cpu)
                            if mem > self._sections[section_name].mem_peak_rss:
                                self._sections[section_name].mem_peak_rss = mem
                            if mem > self._peak_mem_rss:
                                self._peak_mem_rss = mem
        
        self._sampler_thread = threading.Thread(target=sampler, daemon=True)
        self._sampler_thread.start()
    
    def _stop_cpu_sampling(self):
        """Stop background CPU sampling."""
        self._sampling = False
        self._current_section = None
        # Don't wait for thread - it's daemon and will stop on next iteration
    
    @contextmanager
    def section(self, name: str):
        """
        Context manager to monitor a code section.
        
        Args:
            name: Dotted section name (e.g., "detector.fit.gmm")
        
        Yields:
            SectionMetrics object (can be ignored)
        """
        if not self.enabled:
            yield None
            return
        
        depth = len(self._active_stack)
        self._active_stack.append(name)
        
        metrics = SectionMetrics(name=name, depth=depth)
        metrics.start_time = time.perf_counter()
        metrics.mem_start_rss = self._get_memory_rss()
        metrics.mem_peak_rss = metrics.mem_start_rss
        metrics.thread_count = threading.active_count()
        
        # Capture disk I/O start
        disk_start = get_disk_io()
        metrics.disk_read_start = disk_start["read_bytes"]
        metrics.disk_write_start = disk_start["write_bytes"]
        
        with self._lock:
            self._sections[name] = metrics
            if name not in self._section_order:
                self._section_order.append(name)
        
        # Start CPU sampling for longer sections
        self._start_cpu_sampling(name)
        
        try:
            yield metrics
        finally:
            self._stop_cpu_sampling()
            
            metrics.end_time = time.perf_counter()
            metrics.mem_end_rss = self._get_memory_rss()
            if metrics.mem_end_rss > metrics.mem_peak_rss:
                metrics.mem_peak_rss = metrics.mem_end_rss
            
            # Capture disk I/O end
            disk_end = get_disk_io()
            metrics.disk_read_end = disk_end["read_bytes"]
            metrics.disk_write_end = disk_end["write_bytes"]
            
            metrics.finalize()
            
            # Record to OTEL metrics if enabled
            if _otel_enabled:
                try:
                    if _record_memory_fn:
                        _record_memory_fn(
                            current_mb=metrics.mem_end_rss / (1024*1024),
                            peak_mb=metrics.mem_peak_rss / (1024*1024),
                            equipment=_equipment_context,
                            section=name
                        )
                    if _record_cpu_fn and metrics.cpu_percent_avg > 0:
                        _record_cpu_fn(
                            percent=metrics.cpu_percent_avg,
                            equipment=_equipment_context,
                            section=name
                        )
                    if _record_disk_io_fn and (metrics.disk_read_mb > 0 or metrics.disk_write_mb > 0):
                        _record_disk_io_fn(
                            read_mb=metrics.disk_read_mb,
                            write_mb=metrics.disk_write_mb,
                            equipment=_equipment_context,
                            section=name
                        )
                except Exception:
                    pass  # Don't let metrics errors break monitoring
            
            self._active_stack.pop()
    
    def record(self, name: str, duration_s: float, mem_delta_mb: float = 0.0):
        """
        Manually record metrics for a section (for integration with Timer).
        
        Args:
            name: Section name
            duration_s: Duration in seconds
            mem_delta_mb: Memory change in MB (optional)
        """
        if not self.enabled:
            return
        
        metrics = SectionMetrics(
            name=name,
            duration_s=duration_s,
            mem_delta_mb=mem_delta_mb
        )
        
        with self._lock:
            self._sections[name] = metrics
            if name not in self._section_order:
                self._section_order.append(name)
    
    def get_metrics(self) -> List[Dict[str, Any]]:
        """Get all section metrics as list of dicts."""
        with self._lock:
            result = []
            for name in self._section_order:
                if name in self._sections:
                    m = self._sections[name]
                    result.append({
                        "section": m.name,
                        "duration_s": round(m.duration_s, 4),
                        "mem_start_mb": round(m.mem_start_rss / (1024*1024), 2),
                        "mem_end_mb": round(m.mem_end_rss / (1024*1024), 2),
                        "mem_peak_mb": round(m.mem_peak_rss / (1024*1024), 2),
                        "mem_delta_mb": round(m.mem_delta_mb, 2),
                        "cpu_avg_pct": round(m.cpu_percent_avg, 1),
                        "cpu_samples": len(m.cpu_samples),
                        "depth": m.depth,
                        "threads": m.thread_count
                    })
            return result
    
    def get_summary(self) -> Dict[str, Any]:
        """Get run-level summary metrics."""
        if not self.enabled:
            return {}
        
        current_mem = self._get_memory_rss()
        return {
            "total_duration_s": time.perf_counter() - self._run_start_time,
            "mem_start_mb": round(self._run_start_mem / (1024*1024), 2),
            "mem_current_mb": round(current_mem / (1024*1024), 2),
            "mem_peak_mb": round(self._peak_mem_rss / (1024*1024), 2),
            "mem_delta_mb": round((current_mem - self._run_start_mem) / (1024*1024), 2),
            "section_count": len(self._sections),
            "psutil_available": PSUTIL_AVAILABLE
        }
    
    def print_summary(self, top_n: int = 20):
        """Print a summary of resource usage to console."""
        from core.observability import Console
        
        metrics = self.get_metrics()
        summary = self.get_summary()
        
        Console.section("Resource Usage Summary")
        Console.info(f"Total duration: {summary.get('total_duration_s', 0):.2f}s", component="RESOURCE")
        Console.info(f"[RESOURCE] Memory: start={summary.get('mem_start_mb', 0):.0f}MB, "
                    f"peak={summary.get('mem_peak_mb', 0):.0f}MB, "
                    f"delta={summary.get('mem_delta_mb', 0):+.0f}MB")
        
        # Sort by duration and show top N
        sorted_metrics = sorted(metrics, key=lambda x: x['duration_s'], reverse=True)[:top_n]
        
        Console.info(f"Top {min(top_n, len(sorted_metrics))} sections by duration:", component="RESOURCE")
        for m in sorted_metrics:
            indent = "  " * m['depth']
            Console.info(f"[RESOURCE] {indent}{m['section']}: {m['duration_s']:.3f}s, "
                        f"mem={m['mem_delta_mb']:+.1f}MB, cpu={m['cpu_avg_pct']:.0f}%")
    
    def to_dataframe(self, equip_id: int, run_id: str) -> pd.DataFrame:
        """Convert metrics to DataFrame for SQL storage."""
        metrics = self.get_metrics()
        if not metrics:
            return pd.DataFrame()
        
        df = pd.DataFrame(metrics)
        df["EquipID"] = equip_id
        df["RunID"] = run_id
        df["CreatedAt"] = datetime.now()
        
        # Rename for SQL table
        df = df.rename(columns={
            "section": "SectionName",
            "duration_s": "DurationSeconds",
            "mem_start_mb": "MemStartMB",
            "mem_end_mb": "MemEndMB", 
            "mem_peak_mb": "MemPeakMB",
            "mem_delta_mb": "MemDeltaMB",
            "cpu_avg_pct": "CpuAvgPct",
            "cpu_samples": "CpuSampleCount",
            "depth": "SectionDepth",
            "threads": "ThreadCount"
        })
        
        return df
    
    def write_to_sql(self, output_manager, run_id: str, equip_id: int) -> bool:
        """
        Write metrics to SQL via output_manager.
        
        Args:
            output_manager: ACM OutputManager instance
            run_id: Current run ID
            equip_id: Equipment ID
            
        Returns:
            True if successful
        """
        if not self.enabled:
            return False
        
        try:
            df = self.to_dataframe(equip_id, run_id)
            if df.empty:
                return False
            
            result = output_manager.write_sql_table(
                table_name="ACM_ResourceMetrics",
                df=df,
                artifact_name="resource_metrics",
            )
            return bool(result.get("sql_written", False))
        except Exception as e:
            from core.observability import Console
            Console.warn(f"Failed to write metrics to SQL: {e}", component="RESOURCE", equip_id=equip_id, run_id=run_id, error_type=type(e).__name__, error=str(e)[:200])
            return False
    
    def reset(self):
        """Reset all metrics for next run."""
        with self._lock:
            self._sections.clear()
            self._section_order.clear()
            self._active_stack.clear()
        self._run_start_time = 0.0
        self._run_start_mem = 0
        self._peak_mem_rss = 0
    
    def record_gpu_metrics(self, equipment: str = "") -> List[Dict[str, Any]]:
        """Record GPU metrics if available.
        
        Returns:
            List of GPU info dicts
        """
        gpu_info = get_gpu_info()
        if not gpu_info:
            return []
        
        if _otel_enabled and _record_gpu_fn:
            for gpu in gpu_info:
                try:
                    _record_gpu_fn(
                        gpu_id=gpu["gpu_id"],
                        utilization_pct=gpu["utilization_percent"],
                        memory_used_mb=gpu["memory_used_mb"],
                        memory_percent=gpu["memory_percent"],
                        temperature_c=gpu["temperature_c"],
                        gpu_name=gpu["name"],
                        equipment=equipment or _equipment_context
                    )
                except Exception:
                    pass
        
        return gpu_info
    
    def record_capacity_metrics(self, equipment: str = "", equipment_count: int = 0,
                                 tag_count: int = 0, rows_processed: int = 0,
                                 duration_s: float = 0, parallel_workers: int = 1) -> None:
        """Record capacity planning metrics.
        
        Args:
            equipment: Equipment name(s)
            equipment_count: Number of equipment
            tag_count: Number of sensor tags
            rows_processed: Rows processed in batch
            duration_s: Processing time
            parallel_workers: Number of workers
        """
        if _otel_enabled and _record_capacity_fn:
            try:
                _record_capacity_fn(
                    equipment=equipment or _equipment_context,
                    equipment_count=equipment_count,
                    tag_count=tag_count,
                    rows_processed=rows_processed,
                    duration_s=duration_s,
                    parallel_workers=parallel_workers
                )
            except Exception:
                pass
    
    def record_cpu_per_core(self, equipment: str = "") -> List[float]:
        """Record per-core CPU usage.
        
        Returns:
            List of CPU percentages per core
        """
        core_pcts = get_cpu_per_core()
        if not core_pcts:
            return []
        
        if _otel_enabled:
            try:
                from core.observability import record_cpu_per_core as _record_cores
                _record_cores(core_pcts, equipment=equipment or _equipment_context)
            except Exception:
                pass
        
        return core_pcts


# Global singleton instance
R = ResourceMonitor()


def get_full_system_info() -> Dict[str, Any]:
    """Get comprehensive system information for capacity planning."""
    info = {
        "python_version": os.sys.version.split()[0],
        "platform": os.sys.platform,
        "psutil_available": PSUTIL_AVAILABLE,
        "gpu_available": GPU_AVAILABLE,
        "gpu_count": GPU_COUNT,
    }
    
    if PSUTIL_AVAILABLE:
        vm = psutil.virtual_memory()
        info.update({
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "cpu_count_physical": psutil.cpu_count(logical=False),
            "total_memory_gb": round(vm.total / (1024**3), 1),
            "available_memory_gb": round(vm.available / (1024**3), 1),
            "memory_percent_used": vm.percent,
        })
    
    if GPU_AVAILABLE:
        gpu_info = get_gpu_info()
        if gpu_info:
            info["gpus"] = gpu_info
            info["total_gpu_memory_gb"] = sum(g["memory_total_mb"] for g in gpu_info) / 1024
    
    return info

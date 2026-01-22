# utils/timer.py
"""Performance timing utilities for ACM.

Provides section-based timing with:
- OTEL trace spans (parent-child hierarchy in Tempo)
- OTEL metrics (histograms in Prometheus)
- Resource monitoring (memory/CPU via ResourceMonitor)
- Console output (text or JSON format)
- Summary at exit

v2.1: Now integrates with ResourceMonitor for memory/CPU profiling.
"""
from __future__ import annotations
import atexit
import time
import os
import functools
import json
from datetime import datetime
from typing import Any, Callable, Dict, Optional

# Import from unified observability module (lazy to handle import order)
_Span: Optional[type] = None
_record_section_fn: Optional[Callable] = None
_equipment_context: str = ""
_Console: Optional[type] = None
_log_timer_fn: Optional[Callable] = None
_observability_initialized: bool = False

# ResourceMonitor integration (lazy loaded)
_resource_monitor: Optional[Any] = None
_resource_enabled: bool = False

def _ensure_observability() -> None:
    """Lazily import observability module to handle import order issues."""
    global _Span, _Console, _log_timer_fn, _observability_initialized
    if _observability_initialized:
        return
    _observability_initialized = True
    try:
        from core.observability import Span as _OtelSpan, Console, log_timer as _otel_log_timer
        _Span = _OtelSpan
        _Console = Console
        _log_timer_fn = _otel_log_timer
    except ImportError:
        pass


def _ensure_resource_monitor() -> None:
    """Lazily import ResourceMonitor."""
    global _resource_monitor, _resource_enabled
    if _resource_monitor is not None or _resource_enabled:
        return
    try:
        from core.resource_monitor import R
        _resource_monitor = R
        _resource_enabled = True
    except ImportError:
        _resource_enabled = False


# Try import at module load (works if observability loaded first)
try:
    from core.observability import Span as _OtelSpan, Console, log_timer as _otel_log_timer
    _Span = _OtelSpan
    _Console = Console
    _log_timer_fn = _otel_log_timer
    _observability_initialized = True
except ImportError:
    pass


def enable_timer_metrics(equipment: str = "") -> None:
    """Enable OTEL metrics recording for Timer sections."""
    global _equipment_context
    _equipment_context = equipment
    # Also enable resource monitor
    _ensure_resource_monitor()


def set_timer_equipment(equipment: str) -> None:
    """Set the equipment context for timer metrics."""
    global _equipment_context
    _equipment_context = equipment


class Timer:
    """Lightweight stage timer with OTEL integration.
    
    Usage:
       T = Timer()
       with T.section("load_data"):
           df = load_data()
       T.log("custom", extra="info")
    
    Each section creates:
    - An OTEL span (visible in Grafana Tempo)
    - A metric recording (visible in Prometheus)
    - Console output (text or JSON)
    
    Environment variables:
        ACM_TIMINGS: Enable/disable timing output (default: 1)
        LOG_FORMAT: Output format (text|json)
    """
    def __init__(self, enable: bool | None = None, profile_resources: bool = True):
        self.enable = bool(int(os.getenv("ACM_TIMINGS", "1"))) if enable is None else enable
        self.profile_resources = profile_resources
        self.totals: Dict[str, float] = {}
        self._active_spans: Dict[str, Any] = {}  # name -> (span, start_time, resource_ctx)
        self._t0 = time.perf_counter()
        self._json_mode = os.getenv("LOG_FORMAT", "text").lower() == "json"
        atexit.register(self._print_summary)

    def section(self, name: str, profile: bool = True):
        """Start a timed section. Returns a context manager.
        
        Creates an OTEL span for proper trace hierarchy.
        Also starts ResourceMonitor section for memory/CPU profiling.
        
        Args:
            name: Section name (hierarchical with dots, e.g., "fit.pca")
            profile: Whether to enable resource profiling (default True)
        """
        if not self.enable:
            return _NullContext()
        return _TracedSection(self, name, profile=profile and self.profile_resources)

    def _start_section(self, name: str, profile: bool = True) -> Any:
        """Internal: start tracking a section."""
        start_time = time.perf_counter()
        span = None
        resource_ctx = None
        
        # Create OTEL span if available
        if _Span:
            span = _Span(name)
            span.__enter__()
        
        # Start resource monitoring if enabled and available
        if profile and self.profile_resources:
            _ensure_resource_monitor()
            if _resource_monitor:
                try:
                    resource_ctx = _resource_monitor.section(name)
                    resource_ctx.__enter__()
                except Exception:
                    resource_ctx = None
        
        self._active_spans[name] = (span, start_time, resource_ctx)
        return span

    def _end_section(self, name: str) -> float:
        """Internal: end a section and record metrics."""
        if name not in self._active_spans:
            return 0.0
        
        span, start_time, resource_ctx = self._active_spans.pop(name)
        duration = time.perf_counter() - start_time
        
        # Accumulate for summary
        self.totals[name] = self.totals.get(name, 0.0) + duration
        
        # End resource monitoring first (while memory is still allocated)
        if resource_ctx:
            try:
                resource_ctx.__exit__(None, None, None)
            except Exception:
                pass
        
        # End OTEL span (this also records metrics via Span.__exit__)
        if span:
            span.__exit__(None, None, None)
        elif _record_section_fn:
            # Fallback: just record metric without span
            try:
                _record_section_fn(name, duration, _equipment_context)
            except Exception:
                pass
        
        # Console output (only if NOT using Span which does its own logging)
        # Span.__exit__ already emits structured log event
        if not span:
            self._log_section(name, duration)
        
        return duration

    def _get_timestamp(self) -> str:
        """Get timestamp (UTC by default for observability consistency)."""
        # Use UTC for consistency with OTEL stack
        return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    def _log_section(self, name: str, duration: float) -> None:
        """Output section timing to console (fallback when Span not available).
        
        Also pushes structured log to Loki with log_type='timer'.
        """
        # Ensure observability is available (handles import order)
        _ensure_observability()
        
        # Extract parent from hierarchical name (e.g., "fit.pca" -> "fit")
        parts = name.split(".")
        parent = parts[0] if parts else name
        
        if self._json_mode:
            print(json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "INFO",
                "log_type": "timer",
                "section": name,
                "parent": parent,
                "duration_s": round(duration, 6),
                "equipment": _equipment_context,
            }))
        elif _Console:
            # Push structured timer log to Loki
            if _log_timer_fn:
                _log_timer_fn(section=name, duration_s=duration, parent=parent)
            # Console output only (skip_loki=True since log_timer_fn handles Loki)
            _Console.info(f"{name:<30} {duration:7.3f}s", skip_loki=True)
        else:
            timestamp = self._get_timestamp()
            print(f"[{timestamp}] [INFO] [TIMER] {name:<30} {duration:7.3f}s")

    def wrap(self, name: str):
        """Decorator: @T.wrap('features') on a function."""
        def deco(fn: Callable[..., Any]):
            @functools.wraps(fn)
            def inner(*a, **k):
                with self.section(name):
                    return fn(*a, **k)
            return inner
        return deco

    def log(self, name: str, **kv: Any):
        """Log a message with optional key-value pairs."""
        if not self.enable: 
            return
        
        # Ensure observability is available (handles import order)
        _ensure_observability()
        
        if self._json_mode:
            data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": "timer_log",
                "section": name,
            }
            data.update(kv)
            print(json.dumps(data))
        elif _Console:
            extra = " ".join(f"{k}={v}" for k, v in kv.items())
            _Console.info(f"{name:<20} {extra}".rstrip(), component="TIMER")
        else:
            timestamp = self._get_timestamp()
            extra = " ".join(f"{k}={v}" for k, v in kv.items())
            print(f"[{timestamp}] [INFO] [TIMER] {name:<20} {extra}".rstrip())

    def total_elapsed(self) -> float:
        """Return total elapsed time since Timer start."""
        return time.perf_counter() - self._t0

    def _print_summary(self):
        """Print summary of all sections at exit."""
        if not self.enable: 
            return
        total = self.total_elapsed()
        accounted = sum(self.totals.values()) if self.totals else 0.0
        unaccounted = max(total - accounted, 0.0)
        
        # Ensure observability is available (handles import order)
        _ensure_observability()
        
        if self._json_mode:
            sections = [
                {"name": k, "duration_s": round(v, 3), "percent": round((v / total) * 100.0, 1)}
                for k, v in sorted(self.totals.items(), key=lambda x: -x[1])
            ]
            if unaccounted > 0:
                sections.append({
                    "name": "unaccounted",
                    "duration_s": round(unaccounted, 3),
                    "percent": round((unaccounted / total) * 100.0, 1)
                })
            print(json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "log_type": "timer_summary",
                "total_duration_s": round(total, 3),
                "sections": sections
            }))
        elif _Console:
            if self.totals:
                # Console-only section header (not logged to Loki)
                _Console.section("Timer Summary")
                for k, v in sorted(self.totals.items(), key=lambda x: -x[1]):
                    pct = (v / total) * 100.0 if total > 0 else 0.0
                    parts = k.split(".")
                    parent = parts[0] if parts else k
                    # Push structured timer to Loki (skip console's Loki push to avoid duplicates)
                    if _log_timer_fn:
                        _log_timer_fn(section=k, duration_s=v, pct=pct, parent=parent, total_s=total)
                    # Console output only (status = no Loki)
                    _Console.status(f"{k:<30} {v:7.3f}s ({pct:5.1f}%)")
                if unaccounted > 0:
                    pct = (unaccounted / total) * 100.0 if total > 0 else 0.0
                    if _log_timer_fn:
                        _log_timer_fn(section="unaccounted", duration_s=unaccounted, pct=pct, parent="total_run", total_s=total)
                    _Console.status(f"{'unaccounted':<30} {unaccounted:7.3f}s ({pct:5.1f}%)")
            # Log total run as structured timer
            if _log_timer_fn:
                _log_timer_fn(section="total_run", duration_s=total, parent="total_run", total_s=total)
            _Console.status(f"total_run                      {total:7.3f}s")
        else:
            timestamp = self._get_timestamp()
            if self.totals:
                print(f"[{timestamp}] [INFO] [TIMER] -- Summary ------------------------------")
                for k, v in sorted(self.totals.items(), key=lambda x: -x[1]):
                    pct = (v / total) * 100.0 if total > 0 else 0.0
                    print(f"[{timestamp}] [INFO] [TIMER] {k:<30} {v:7.3f}s ({pct:5.1f}%)")
                if unaccounted > 0:
                    pct = (unaccounted / total) * 100.0 if total > 0 else 0.0
                    print(f"[{timestamp}] [INFO] [TIMER] {'unaccounted':<30} {unaccounted:7.3f}s ({pct:5.1f}%)")
            print(f"[{timestamp}] [INFO] [TIMER] total_run                      {total:7.3f}s")


class _TracedSection:
    """Context manager for timed sections with OTEL span and resource profiling support."""
    
    def __init__(self, timer: Timer, name: str, profile: bool = True):
        self.timer = timer
        self.name = name
        self.profile = profile
    
    def __enter__(self):
        self.timer._start_section(self.name, profile=self.profile)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.timer._end_section(self.name)
        return False


class _NullContext:
    """No-op context manager when timing is disabled."""
    def __enter__(self): return self
    def __exit__(self, *a): return False

"""
ACM Unified Observability v4.0

Built on standard libraries: structlog + rich + OpenTelemetry.

COMPONENTS:
- structlog: Structured logging with processors
- rich: Colorful console output, progress indicators
- OpenTelemetry: Traces to Tempo, Metrics to Prometheus, Logs to Loki

API:
    from core.observability import log, Console, Span, traced, init

    # Initialize at startup (optional - works without init for basic logging)
    init(equipment="FD_FAN", equip_id=1, run_id="abc-123")

    # Logging - uses structlog
    log.info("Loaded data", rows=5000)
    log.warning("Low variance", sensors=3)
    log.error("SQL failed", table="ACM_Scores")

    # Console - backwards compatible wrapper
    Console.info("Loaded 5000 rows", component="DATA")
    Console.warn("Warning message", component="MODEL")

    # Spans - OpenTelemetry traces
    with Span("fit.pca"):
        model.fit(X)

    @traced("score.gmm")
    def score_gmm(X):
        return gmm.score(X)
"""
from __future__ import annotations

import atexit
import functools
import logging
import os
import queue
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Callable, Dict, Generator, List, Optional, TypeVar

# =============================================================================
# STRUCTLOG + COLORAMA SETUP (Rich doesn't work reliably when piped)
# =============================================================================

import structlog
import colorama
from colorama import Fore, Back, Style

# Initialize colorama - strip=False ensures colors even when piped
colorama.init(autoreset=True, strip=False)

# Color definitions for different log elements
class _Colors:
    """Color constants for console output."""
    # Timestamp colors
    DATE = Fore.YELLOW  # Gold-ish
    TIME = Fore.CYAN    # Blue-ish
    # Level colors
    INFO = Fore.CYAN + Style.BRIGHT
    WARN = Fore.YELLOW + Style.BRIGHT
    ERROR = Fore.RED + Style.BRIGHT
    OK = Fore.GREEN + Style.BRIGHT
    DEBUG = Fore.CYAN + Style.DIM  # Dim cyan for visibility without prominence
    STATUS = Fore.MAGENTA + Style.BRIGHT  # Console-only status (purple/magenta)
    # Component tag (module name like CAL, FUSE, THRESHOLD)
    COMPONENT = Fore.WHITE + Style.BRIGHT  # Neutral color works with all levels
    # Message
    MSG = Fore.WHITE
    RESET = Style.RESET_ALL

# Configure structlog
def _configure_structlog():
    """Configure structlog with console output."""
    
    # Processors for structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.dev.ConsoleRenderer(colors=True),
    ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

_configure_structlog()

# Global logger
log = structlog.get_logger("acm")


# =============================================================================
# OPENTELEMETRY (OPTIONAL)
# =============================================================================

try:
    from opentelemetry import trace as otel_trace
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, AggregationTemporality
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.trace import Status, StatusCode, SpanKind
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    otel_trace = None
    otel_metrics = None
    StatusCode = None
    Status = None
    AggregationTemporality = None

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    OTEL_EXPORTERS_AVAILABLE = True
except ImportError:
    OTEL_EXPORTERS_AVAILABLE = False

try:
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    OTEL_LOGS_AVAILABLE = True
except ImportError:
    OTEL_LOGS_AVAILABLE = False


# =============================================================================
# PYROSCOPE (CONTINUOUS PROFILING) - Using yappi + HTTP API
# No native pyroscope-io required (avoids Rust compilation on Windows)
# =============================================================================

try:
    import yappi
    YAPPI_AVAILABLE = True
except ImportError:
    yappi = None
    YAPPI_AVAILABLE = False

# Legacy flag for backwards compatibility
PYROSCOPE_AVAILABLE = YAPPI_AVAILABLE


# =============================================================================
# CONFIGURATION
# =============================================================================

# OTLP HTTP endpoint (Alloy/Collector on port 4318)
DEFAULT_OTLP_ENDPOINT = "http://localhost:4318"
# Loki native push endpoint
DEFAULT_LOKI_ENDPOINT = "http://localhost:3100"
# Prometheus remote-write endpoint  
DEFAULT_PROMETHEUS_ENDPOINT = "http://localhost:9090"
# Pyroscope profiling endpoint
DEFAULT_PYROSCOPE_ENDPOINT = "http://localhost:4040"

class _Config:
    """Runtime configuration."""
    service_name: str = "acm-pipeline"
    service_version: str = "10.3.0"
    otlp_endpoint: str = DEFAULT_OTLP_ENDPOINT
    loki_endpoint: str = DEFAULT_LOKI_ENDPOINT
    prometheus_endpoint: str = DEFAULT_PROMETHEUS_ENDPOINT
    pyroscope_endpoint: str = DEFAULT_PYROSCOPE_ENDPOINT
    equipment: str = ""
    equip_id: int = 0
    run_id: str = ""

_config = _Config()
_tracer: Optional[Any] = None
_meter: Optional[Any] = None
_loki_pusher: Optional["_LokiPusher"] = None
_pyroscope_enabled: bool = False
_pyroscope_pusher: Optional["_PyroscopePusher"] = None
_initialized: bool = False
_shutdown_called: bool = False
_sql_sink: Optional["_SqlLogSink"] = None
_metrics: Dict[str, Any] = {}
_init_lock = threading.Lock()

# NOTE: Phase-specific tracers removed in v11.1.6
# Having multiple service.name values per process is semantically wrong:
# - Fragments telemetry (many 'services' that are one process)
# - Breaks service-level dashboards (latency/throughput/error rate)
# - Complicates correlation with logs/profiles
# Instead, use span attributes: acm.phase = "features"|"models"|... for Tempo filtering/coloring


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _check_endpoint_reachable(endpoint: str, timeout: float = 1.0) -> bool:
    """Check if an HTTP endpoint is reachable (quick connectivity test)."""
    import socket
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(endpoint)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


# =============================================================================
# INITIALIZATION
# =============================================================================

def init(
    equipment: str = "",
    equip_id: int = 0,
    run_id: str = "",
    sql_client: Optional[Any] = None,
    service_name: str = "acm-pipeline",
    otlp_endpoint: str = DEFAULT_OTLP_ENDPOINT,
    loki_endpoint: str = DEFAULT_LOKI_ENDPOINT,
    pyroscope_endpoint: str = DEFAULT_PYROSCOPE_ENDPOINT,
    # Legacy param - maps to otlp_endpoint
    tempo_endpoint: Optional[str] = None,
    enable_tracing: bool = True,
    enable_metrics: bool = True,
    enable_loki: bool = True,
    enable_profiling: bool = True,
) -> None:
    """Initialize observability stack.
    
    Args:
        equipment: Equipment name (e.g., "FD_FAN")
        equip_id: Equipment ID in database
        run_id: Unique run identifier
        sql_client: Optional SQLClient for ACM_RunLogs sink
        service_name: OpenTelemetry service name
        tempo_endpoint: Tempo OTLP endpoint (default: http://localhost:4321)
        loki_endpoint: Loki push endpoint (default: http://localhost:3100)
        pyroscope_endpoint: Pyroscope endpoint (default: http://localhost:4040)
        enable_tracing: Enable trace export to Tempo
        enable_metrics: Enable metric export via OTEL
        enable_profiling: Enable continuous profiling with Pyroscope
        enable_loki: Enable log push to Loki
    """
    global _initialized, _tracer, _meter, _sql_sink, _loki_pusher, _config, _metrics
    
    # Handle legacy tempo_endpoint param
    if tempo_endpoint is not None:
        otlp_endpoint = tempo_endpoint
    
    with _init_lock:
        if _initialized:
            return
        
        # Update config
        _config.service_name = service_name
        _config.otlp_endpoint = otlp_endpoint
        _config.loki_endpoint = loki_endpoint
        _config.equipment = equipment
        _config.equip_id = equip_id
        _config.run_id = run_id
        
        # Bind context to structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            equipment=equipment,
            equip_id=equip_id,
            run_id=run_id,
        )
        
        # SQL log sink
        if sql_client is not None:
            _sql_sink = _SqlLogSink(sql_client, run_id, equip_id)
        
        # Collect enabled services for a single consolidated log line
        _otel_services: list[str] = []

        # Loki log pusher (native Loki API, not OTLP)
        if enable_loki:
            _loki_pusher = _LokiPusher(
                endpoint=f"{loki_endpoint}/loki/api/v1/push",
                labels={
                    "app": "acm",
                    "service": service_name, 
                    "equipment": equipment or "unknown"
                },
            )
            if _loki_pusher._connected:
                _otel_services = [f"loki={loki_endpoint}"]
            else:
                Console.warn(f"Loki not connected at {loki_endpoint}", component="OTEL", endpoint=loki_endpoint, service="loki")
        
        # Pyroscope continuous profiling (via yappi + tracemalloc + HTTP API - no Rust required)
        global _pyroscope_enabled, _pyroscope_pusher
        if enable_profiling and YAPPI_AVAILABLE:
            try:
                pyroscope_reachable = _check_endpoint_reachable(pyroscope_endpoint)
                if pyroscope_reachable:
                    # Use consistent label names for Grafana correlation:
                    # - service_name: Standard Grafana label (matches tracesToProfiles)
                    # - equipment: Equipment name for filtering
                    # - equip_id: Equipment database ID
                    # - run_id: Run identifier for log/trace correlation
                    _pyroscope_pusher = _PyroscopePusher(
                        endpoint=pyroscope_endpoint,
                        app_name="acm",  # Simple app name, labels provide context
                        tags={
                            "service_name": service_name,  # Standard Grafana label
                            "equipment": equipment or "unknown",
                            "equip_id": str(equip_id),
                            "run_id": run_id or "unknown",
                        },
                    )
                    _pyroscope_enabled = True
                    _config.pyroscope_endpoint = pyroscope_endpoint
                    profile_types = ["cpu (yappi)"]
                    if TRACEMALLOC_AVAILABLE:
                        profile_types.append("memory (tracemalloc)")
                    _otel_services.append(f"profiling={pyroscope_endpoint}")
                else:
                    Console.warn(f"Pyroscope not reachable at {pyroscope_endpoint} - profiling disabled", component="OTEL", endpoint=pyroscope_endpoint, service="pyroscope")
            except Exception as e:
                Console.warn(f"Pyroscope setup failed: {e}", component="OTEL", endpoint=pyroscope_endpoint, service="pyroscope", error_type=type(e).__name__, error=str(e)[:200])
        elif enable_profiling and not YAPPI_AVAILABLE:
            Console.warn("yappi not installed - profiling disabled (pip install yappi)", component="OTEL", service="pyroscope", reason="yappi_not_installed")
        
        # OpenTelemetry setup for tracing
        if not OTEL_AVAILABLE or not OTEL_EXPORTERS_AVAILABLE:
            if _otel_services:
                Console.ok(f"OTEL: {', '.join(_otel_services)}", component="OTEL")
            _initialized = True
            return

        # Pre-check OTLP endpoint connectivity to avoid noisy export errors
        otlp_reachable = _check_endpoint_reachable(otlp_endpoint)
        if not otlp_reachable:
            Console.warn(f"OTLP endpoint not reachable at {otlp_endpoint} - tracing/metrics disabled", component="OTEL", endpoint=otlp_endpoint, service="otlp")
            if _otel_services:
                Console.ok(f"OTEL: {', '.join(_otel_services)}", component="OTEL")
            _initialized = True
            return
        
        resource = Resource.create({SERVICE_NAME: service_name})
        
        # Tracing via OTLP - single tracer provider (v11.1.6: removed multi-service hack)
        if enable_tracing:
            # Create the single tracer provider with consistent service identity
            trace_provider = TracerProvider(resource=resource)
            span_processor = BatchSpanProcessor(
                OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
            )
            trace_provider.add_span_processor(span_processor)
            otel_trace.set_tracer_provider(trace_provider)
            _tracer = otel_trace.get_tracer(service_name)
            
            _otel_services.append(f"traces={otlp_endpoint}")
        
        # Metrics via OTLP
        if enable_metrics:
            try:
                # Import instrument types for temporality mapping
                from opentelemetry.sdk.metrics import Counter, Histogram, UpDownCounter, ObservableCounter, ObservableUpDownCounter, ObservableGauge
                
                # Use CUMULATIVE temporality for Prometheus compatibility
                # Delta temporality (default) doesn't work with Prometheus
                cumulative_temporality = {
                    Counter: AggregationTemporality.CUMULATIVE,
                    Histogram: AggregationTemporality.CUMULATIVE,
                    UpDownCounter: AggregationTemporality.CUMULATIVE,
                    ObservableCounter: AggregationTemporality.CUMULATIVE,
                    ObservableUpDownCounter: AggregationTemporality.CUMULATIVE,
                    ObservableGauge: AggregationTemporality.CUMULATIVE,
                }
                
                metric_exporter = OTLPMetricExporter(
                    endpoint=f"{otlp_endpoint}/v1/metrics",
                    preferred_temporality=cumulative_temporality,
                )
                metric_reader = PeriodicExportingMetricReader(
                    metric_exporter,
                    export_interval_millis=10000,  # Export every 10s for faster feedback
                )
                meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
                otel_metrics.set_meter_provider(meter_provider)
                _meter = otel_metrics.get_meter(service_name)
                
                # ===== TIMING METRICS =====
                _metrics["stage_duration"] = _meter.create_histogram(
                    "acm_stage_duration_seconds",
                    description="Duration of pipeline stages (hierarchical: fit.pca, score.gmm, etc.)",
                    unit="s",
                )
                _metrics["run_duration"] = _meter.create_histogram(
                    "acm_run_duration_seconds",
                    description="Total run duration",
                    unit="s",
                )
                
                # ===== COUNTER METRICS =====
                _metrics["runs"] = _meter.create_counter(
                    "acm_runs_total",
                    description="Run outcomes by status (OK/FAIL/NOOP)",
                )
                _metrics["batches"] = _meter.create_counter(
                    "acm_batches_total",
                    description="Total batches processed",
                )
                _metrics["rows_processed"] = _meter.create_counter(
                    "acm_rows_processed_total",
                    description="Total rows processed",
                )
                _metrics["sql_ops"] = _meter.create_counter(
                    "acm_sql_ops_total",
                    description="SQL operations by table",
                )
                _metrics["coldstarts"] = _meter.create_counter(
                    "acm_coldstarts_total",
                    description="Coldstart completions",
                )
                _metrics["episodes"] = _meter.create_counter(
                    "acm_episodes_total",
                    description="Anomaly episodes detected",
                )
                _metrics["errors"] = _meter.create_counter(
                    "acm_errors_total",
                    description="Errors by type",
                )
                _metrics["model_refits"] = _meter.create_counter(
                    "acm_model_refits_total",
                    description="Model refit/retrain events",
                )
                
                # ===== GAUGE METRICS (current values) =====
                _metrics["health_score"] = _meter.create_gauge(
                    "acm_health_score",
                    description="Current equipment health score (0-100)",
                )
                _metrics["rul_hours"] = _meter.create_gauge(
                    "acm_rul_hours",
                    description="Remaining useful life in hours",
                )
                _metrics["active_defects"] = _meter.create_gauge(
                    "acm_active_defects",
                    description="Number of active defects",
                )
                _metrics["fused_z"] = _meter.create_gauge(
                    "acm_fused_z_score",
                    description="Current fused anomaly z-score",
                )
                _metrics["detector_z"] = _meter.create_gauge(
                    "acm_detector_z_score",
                    description="Per-detector z-scores (ar1, pca_spe, pca_t2, iforest, gmm, omr)",
                )
                _metrics["regime"] = _meter.create_gauge(
                    "acm_current_regime",
                    description="Current operating regime ID",
                )
                _metrics["data_quality"] = _meter.create_gauge(
                    "acm_data_quality_score",
                    description="Data quality score (0-100)",
                )
                
                # ===== RESOURCE METRICS =====
                _metrics["memory_rss_mb"] = _meter.create_gauge(
                    "acm_memory_rss_mb",
                    description="Process RSS memory in MB",
                )
                _metrics["memory_peak_mb"] = _meter.create_gauge(
                    "acm_memory_peak_mb",
                    description="Peak process memory in MB",
                )
                _metrics["memory_delta_mb"] = _meter.create_gauge(
                    "acm_memory_delta_mb",
                    description="Memory change for section in MB",
                )
                _metrics["cpu_percent"] = _meter.create_gauge(
                    "acm_cpu_percent",
                    description="CPU utilization percentage",
                )
                _metrics["cpu_per_core"] = _meter.create_gauge(
                    "acm_cpu_per_core_percent",
                    description="CPU utilization per logical core",
                )
                _metrics["section_duration"] = _meter.create_histogram(
                    "acm_section_duration_seconds",
                    description="Duration of code sections with resource tracking",
                    unit="s",
                )
                
                # ===== GPU METRICS =====
                _metrics["gpu_utilization"] = _meter.create_gauge(
                    "acm_gpu_utilization_percent",
                    description="GPU compute utilization percentage",
                )
                _metrics["gpu_memory_used"] = _meter.create_gauge(
                    "acm_gpu_memory_used_mb",
                    description="GPU memory used in MB",
                )
                _metrics["gpu_memory_percent"] = _meter.create_gauge(
                    "acm_gpu_memory_percent",
                    description="GPU memory utilization percentage",
                )
                _metrics["gpu_temperature"] = _meter.create_gauge(
                    "acm_gpu_temperature_celsius",
                    description="GPU temperature in Celsius",
                )
                
                # ===== CAPACITY PLANNING METRICS =====
                _metrics["parallel_workers"] = _meter.create_gauge(
                    "acm_parallel_workers",
                    description="Number of parallel workers currently active",
                )
                _metrics["equipment_count"] = _meter.create_gauge(
                    "acm_equipment_count",
                    description="Number of equipment being processed",
                )
                _metrics["tag_count"] = _meter.create_gauge(
                    "acm_tag_count",
                    description="Number of sensor tags being processed",
                )
                _metrics["rows_per_second"] = _meter.create_gauge(
                    "acm_rows_per_second",
                    description="Processing throughput in rows per second",
                )
                _metrics["batch_duration"] = _meter.create_histogram(
                    "acm_batch_duration_seconds",
                    description="Duration of batch processing",
                    unit="s",
                )
                
                # ===== DISK I/O METRICS =====
                _metrics["disk_read_mb"] = _meter.create_gauge(
                    "acm_disk_read_mb",
                    description="Disk read in MB for section",
                )
                _metrics["disk_write_mb"] = _meter.create_gauge(
                    "acm_disk_write_mb",
                    description="Disk write in MB for section",
                )
                _metrics["disk_read_total_mb"] = _meter.create_counter(
                    "acm_disk_read_total_mb",
                    description="Total disk read in MB",
                )
                _metrics["disk_write_total_mb"] = _meter.create_counter(
                    "acm_disk_write_total_mb",
                    description="Total disk write in MB",
                )
                
                _otel_services.append(f"metrics={otlp_endpoint}")
            except Exception as e:
                Console.warn(f"Metrics setup failed: {e}", component="OTEL", endpoint=otlp_endpoint, service="metrics", error_type=type(e).__name__, error=str(e)[:200])
        
        if _otel_services:
            Console.ok(f"OTEL: {', '.join(_otel_services)}", component="OTEL")
        _initialized = True
        atexit.register(shutdown)


def enable_sql_logging(sql_client: Any, run_id: str, equip_id: int) -> None:
    """
    Enable SQL log persistence after SQL connection is established.
    
    v11.6.0 FIX #4: Late-binding SQL sink
    =====================================
    The observability stack is initialized BEFORE SQL connection for early
    logging. This function enables SQL log persistence AFTER the connection
    is established.
    
    Args:
        sql_client: SQLClient instance with active connection
        run_id: Current run identifier
        equip_id: Equipment ID
    """
    global _sql_sink
    
    if _sql_sink is not None:
        return  # Already enabled
    
    try:
        _sql_sink = _SqlLogSink(sql_client, run_id, equip_id)
        Console.ok("SQL log persistence enabled -> ACM_RunLogs", component="OTEL")
    except Exception as e:
        Console.warn(
            f"Failed to enable SQL log persistence: {e}",
            component="OTEL", error_type=type(e).__name__
        )


def shutdown() -> None:
    """Flush and shutdown all providers."""
    global _sql_sink, _loki_pusher, _shutdown_called, _pyroscope_enabled, _pyroscope_pusher
    
    # Prevent double shutdown (atexit may call again)
    if _shutdown_called:
        return
    _shutdown_called = True
    
    # Shutdown Pyroscope profiling (yappi-based)
    if _pyroscope_enabled and _pyroscope_pusher is not None:
        try:
            _pyroscope_pusher.stop_and_push()
        except KeyboardInterrupt:
            pass  # Graceful exit on Ctrl+C during shutdown
        except Exception:
            pass  # Best effort
        _pyroscope_enabled = False
        _pyroscope_pusher = None
    
    # Flush and shutdown OTEL metric provider to ensure final metrics are exported
    if OTEL_AVAILABLE and otel_metrics is not None:
        try:
            provider = otel_metrics.get_meter_provider()
            if hasattr(provider, 'force_flush'):
                provider.force_flush(timeout_millis=10000)
            if hasattr(provider, 'shutdown'):
                provider.shutdown()
        except Exception:
            pass  # Best effort flush
    
    # Flush and shutdown OTEL trace provider
    if OTEL_AVAILABLE and otel_trace is not None:
        try:
            provider = otel_trace.get_tracer_provider()
            if hasattr(provider, 'force_flush'):
                provider.force_flush(timeout_millis=10000)
            if hasattr(provider, 'shutdown'):
                provider.shutdown()
        except Exception:
            pass  # Best effort flush
    
    if _sql_sink:
        _sql_sink.close()
        _sql_sink = None
    if _loki_pusher:
        _loki_pusher.close()
        _loki_pusher = None


# =============================================================================
# PROFILING HELPERS
# =============================================================================

def start_profiling() -> None:
    """Start CPU profiling for the current process.
    
    Call this at the start of a batch/run to begin collecting profile data.
    Profile data is automatically pushed to Pyroscope on shutdown or
    when stop_profiling() is called.
    """
    global _pyroscope_pusher
    if _pyroscope_pusher is not None:
        _pyroscope_pusher.start()
        Console.info("Started CPU profiling", component="PROFILE")
    else:
        # Silently skip if not initialized
        pass


def stop_profiling() -> None:
    """Stop CPU profiling and push results to Pyroscope.
    
    Call this at the end of a batch/run to push profile data.
    """
    global _pyroscope_pusher
    if _pyroscope_pusher is not None:
        Console.info("Stopping and pushing profile data...", component="PROFILE")
        _pyroscope_pusher.stop_and_push()
        Console.ok("Profile data pushed to Pyroscope", component="PROFILE")
    else:
        # Silently skip if not initialized
        pass


def get_trace_context() -> Dict[str, Optional[str]]:
    """Get the current trace context (trace_id and span_id).
    
    Returns a dictionary with 'trace_id' and 'span_id' keys.
    Values are None if no active trace context exists.
    
    This is useful for:
    - Adding trace context to custom log entries
    - Correlating external operations with the current trace
    - Debugging trace propagation issues
    
    Returns:
        Dict with 'trace_id' (32-char hex) and 'span_id' (16-char hex),
        or None values if no valid context.
    
    Example:
        ctx = get_trace_context()
        if ctx["trace_id"]:
            log_external_system(message, trace_id=ctx["trace_id"])
    """
    result: Dict[str, Optional[str]] = {"trace_id": None, "span_id": None}
    
    if OTEL_AVAILABLE and otel_trace is not None:
        try:
            current_span = otel_trace.get_current_span()
            if current_span is not None:
                span_ctx = current_span.get_span_context()
                if span_ctx is not None and span_ctx.is_valid:
                    result["trace_id"] = format(span_ctx.trace_id, '032x')
                    result["span_id"] = format(span_ctx.span_id, '016x')
        except Exception:
            pass
    
    return result


@contextmanager
def profile_section(name: str) -> Generator[None, None, None]:
    """Context manager to profile a specific section of code.
    
    Usage:
        with profile_section("fit_models"):
            model.fit(X)
    
    This starts profiling, runs the code, then stops and pushes
    the profile for that section.
    """
    if _pyroscope_pusher is None:
        yield
        return
    
    _pyroscope_pusher.start()
    try:
        yield
    finally:
        _pyroscope_pusher.stop_and_push()


def set_context(
    equipment: Optional[str] = None,
    equip_id: Optional[int] = None,
    run_id: Optional[str] = None,
) -> None:
    """Update context for all subsequent logs, traces, and profiles."""
    global _pyroscope_pusher
    
    if equipment is not None:
        _config.equipment = equipment
    if equip_id is not None:
        _config.equip_id = equip_id
    if run_id is not None:
        _config.run_id = run_id
    
    # Update structlog context
    structlog.contextvars.bind_contextvars(
        equipment=_config.equipment,
        equip_id=_config.equip_id,
        run_id=_config.run_id,
    )
    
    # Update Pyroscope pusher tags with new context
    # Use consistent label names for Grafana correlation:
    # - service_name: Standard Grafana label (matches tracesToProfiles)
    # - equipment: Equipment name
    # - equip_id: Equipment database ID
    # - run_id: Run identifier for log/trace correlation
    if _pyroscope_pusher is not None:
        _pyroscope_pusher._tags = {
            "service_name": _config.service_name,  # Standard Grafana label
            "equipment": _config.equipment or "unknown",
            "equip_id": str(_config.equip_id),
            "run_id": _config.run_id or "unknown",
        }


# =============================================================================
# CONSOLE - Backwards Compatible Wrapper using Colorama
# =============================================================================

class Console:
    """
    Unified logging with structured records.
    
    Each log call creates a single LogRecord that is:
    1. Rendered to console with colors and formatting
    2. Sent to Loki with proper labels (no regex extraction needed)
    
    Usage:
        Console.info("Loading data", component="DATA", rows=5000)
        Console.warn("Low variance", component="MODEL")
        Console.error("SQL failed", component="SQL", table="ACM_Scores")
    
    The `component` parameter becomes:
    - Console: [INFO] [DATA] Loading data
    - Loki label: {component="data", level="info"} "Loading data"
    """
    
    @staticmethod
    def _format_timestamp() -> tuple:
        """Format current timestamp as (date, time) tuple."""
        now = datetime.now()
        return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
    
    @staticmethod
    def _render_console(level: str, level_color: str, message: str, component: Optional[str] = None) -> None:
        """Render a log record to console with colors."""
        date, time_str = Console._format_timestamp()
        
        # Build the console line
        timestamp = f"{_Colors.DATE}[{date}{_Colors.RESET} {_Colors.TIME}{time_str}]{_Colors.RESET}"
        level_tag = f"{level_color}[{level}]{_Colors.RESET}"
        
        if component:
            comp_tag = f"{level_color}[{component.upper()}]{_Colors.RESET} "
        else:
            comp_tag = ""
        
        print(f"{timestamp} {level_tag} {comp_tag}{_Colors.MSG}{message}{_Colors.RESET}", flush=True)
    
    @staticmethod
    def _send_to_loki(level: str, message: str, component: Optional[str] = None, **kwargs) -> None:
        """Send structured log to Loki with proper labels.
        
        Automatically filters out formatting-only messages (separators, blank lines)
        to prevent log pollution.
        """
        if not _loki_pusher:
            return
        # Filter out formatting-only lines (separators, banners)
        stripped = message.strip()
        if not stripped or all(c in '=-_*#~' for c in stripped):
            return  # Skip pure separator/decoration lines
        _loki_pusher.log(level, message, component=component, **kwargs)
    
    @staticmethod
    def debug(message: str, component: Optional[str] = None, **kwargs) -> None:
        """Debug message. Only shown in console, low priority in Loki."""
        Console._render_console("DEBUG", _Colors.DEBUG, message, component)
        Console._send_to_loki("debug", message, component, **kwargs)
    
    @staticmethod
    def info(message: str, component: Optional[str] = None, skip_loki: bool = False, **kwargs) -> None:
        """Info message. Standard operational logging."""
        Console._render_console("INFO", _Colors.INFO, message, component)
        if not skip_loki:
            Console._send_to_loki("info", message, component, **kwargs)
    
    @staticmethod
    def warn(message: str, component: Optional[str] = None, **kwargs) -> None:
        """Warning message. Something unexpected but not fatal."""
        Console._render_console("WARN", _Colors.WARN, message, component)
        Console._send_to_loki("warning", message, component, **kwargs)
    
    warning = warn
    
    @staticmethod
    def error(message: str, component: Optional[str] = None, **kwargs) -> None:
        """Error message. Something failed."""
        Console._render_console("ERROR", _Colors.ERROR, message, component)
        Console._send_to_loki("error", message, component, **kwargs)
    
    @staticmethod
    def ok(message: str, component: Optional[str] = None, **kwargs) -> None:
        """Success message (green). Logs as level=info with tag=success to Loki."""
        Console._render_console("SUCCESS", _Colors.OK, message, component)
        kwargs.pop("level", None)  # Avoid conflict
        Console._send_to_loki("info", message, component, tag="success", **kwargs)
    
    @staticmethod
    def status(message: str) -> None:
        """Console-only status message (magenta). Does NOT push to Loki.
        
        Use for progress indicators, section headers, decorative separators,
        and operational messages that would pollute log analysis.
        
        Examples:
            Console.status("Processing Equipment: FD_FAN")
            Console.status("="*60)  # Section divider
        """
        date, time_str = Console._format_timestamp()
        print(f"{_Colors.DATE}[{date}{_Colors.RESET} {_Colors.TIME}{time_str}]{_Colors.RESET} {_Colors.STATUS}>>>{_Colors.RESET} {_Colors.MSG}{message}{_Colors.RESET}", flush=True)
        # Intentionally NO Loki push - console only
    
    @staticmethod
    def header(title: str, char: str = "=", width: int = 60) -> None:
        """Print a section header box. Console-only, no Loki.
        
        Example:
            Console.header("Processing Equipment: FD_FAN")
            
        Output:
            >>> ============================================================
            >>> Processing Equipment: FD_FAN
            >>> ============================================================
        """
        Console.status(char * width)
        Console.status(title)
        Console.status(char * width)
    
    @staticmethod  
    def section(title: str) -> None:
        """Print a lighter section marker. Console-only, no Loki.
        
        Example:
            Console.section("Starting coldstart")
            
        Output:
            >>> --- Starting coldstart ---
        """
        Console.status(f"--- {title} ---")

# =============================================================================
# SPANS - OpenTelemetry Tracing
# =============================================================================

# Span kind mapping for colorful traces in Tempo
# Different span kinds get different colors in the trace view
# Strategy: Use all 5 span kinds for visual clarity (not just green INTERNAL)
#
# Color distribution goal:
#   🔵 Blue (CLIENT): 20% - All I/O operations (data in/out)
#   🟢 Green (INTERNAL): 30% - Core algorithms (processing)
#   🟣 Purple (SERVER): 10% - High-level orchestration (entry/exit)
#   🟠 Orange (PRODUCER): 20% - Data generation (creation)
#   🟡 Yellow (CONSUMER): 20% - Aggregation/fusion (consumption)
#
_SPAN_KIND_MAP = {
    # 🔵 CLIENT (blue): External I/O - data in/out
    "load_data": "CLIENT",
    "load": "CLIENT",
    "sql": "CLIENT",
    "persist": "CLIENT",
    "write": "CLIENT",
    "read": "CLIENT",
    "fetch": "CLIENT",
    
    # 🟢 INTERNAL (green): Core algorithms - processing
    "fit": "INTERNAL",
    "score": "INTERNAL",
    "compute": "INTERNAL",
    "calibrate": "INTERNAL",
    "regimes": "INTERNAL",
    "drift": "INTERNAL",
    "hash": "INTERNAL",
    "normalize": "INTERNAL",
    "impute": "INTERNAL",
    
    # 🟣 SERVER (purple): High-level orchestration - entry/exit
    "startup": "SERVER",
    "outputs": "SERVER",
    "finalize": "SERVER",
    "shutdown": "SERVER",
    "pipeline": "SERVER",
    "acm": "SERVER",
    "models": "SERVER",
    
    # 🟠 PRODUCER (orange): Data generation - creation
    "features": "PRODUCER",
    "baseline": "PRODUCER",
    "data": "PRODUCER",
    "forecast": "PRODUCER",
    "analytics": "PRODUCER",
    
    # 🟡 CONSUMER (yellow): Aggregation/fusion - consumption
    "fusion": "CONSUMER",
    "thresholds": "CONSUMER",
    "episodes": "CONSUMER",
    "culprits": "CONSUMER",
    "train": "CONSUMER",  # Orchestrates multiple fit operations
}


# Try to import psutil for memory tracking in Span
try:
    import psutil
    _PSUTIL_AVAILABLE = True
    _PROCESS = psutil.Process()
except ImportError:
    _PSUTIL_AVAILABLE = False
    _PROCESS = None


class Span:
    """
    Context manager for OpenTelemetry spans with integrated resource tracking.
    
    Usage:
        with Span("fit.pca"):
            model.fit(X)
        
        # With resource tracking and custom attributes
        with Span("fit.pca", track_resources=True, n_samples=1000, n_features=50):
            model.fit(X)
    
    Spans are color-coded in Tempo based on span kind (determined by prefix):
    - 🔵 CLIENT (blue): I/O operations (sql, load, persist, write)
    - 🟢 INTERNAL (green): Algorithms (fit, score, compute, calibrate)
    - 🟣 SERVER (purple): Orchestration (startup, outputs, pipeline, models)
    - 🟠 PRODUCER (orange): Data generation (features, forecast, analytics)
    - 🟡 CONSUMER (yellow): Aggregation (fusion, thresholds, episodes)
    
    Standard attributes (auto-added):
    - acm.service: "acm-pipeline"
    - acm.equipment: Equipment name
    - acm.equip_id: Equipment database ID
    - acm.run_id: Run identifier (UUID)
    - acm.category: Top-level category (from span name prefix)
    - acm.phase: High-level phase group (startup/features/fit/score/fusion/persist/finalize)
    - acm.batch_num: Batch number (for batch runs)
    - acm.batch_total: Total batches (for batch runs)
    
    Resource metrics (when track_resources=True):
    - acm_memory_rss_mb: Process memory at section end
    - acm_memory_delta_mb: Memory change during section
    - acm_cpu_percent: CPU usage during section
    - All metrics labeled with {equipment, section, run_id}
    
    Custom attributes (caller-provided):
    - n_samples, n_features, n_detectors (data attributes)
    - detector, model_version (model attributes)
    - outcome, error_type (result attributes)
    """
    
    def __init__(self, name: str, track_resources: bool = True, **attributes):
        self.name = name
        self.attributes = attributes
        self.track_resources = track_resources
        self._span: Optional[Any] = None
        self._context_token: Optional[Any] = None
        self._start_time = 0.0
        self._mem_start: float = 0.0
        self._cpu_start: Optional[float] = None
    
    def _get_memory_mb(self) -> float:
        """Get current process memory in MB."""
        if _PSUTIL_AVAILABLE and _PROCESS:
            try:
                return _PROCESS.memory_info().rss / (1024 * 1024)
            except Exception:
                return 0.0
        return 0.0
    
    def _get_cpu_times(self) -> Optional[float]:
        """Get CPU times for delta calculation."""
        if _PSUTIL_AVAILABLE and _PROCESS:
            try:
                times = _PROCESS.cpu_times()
                return times.user + times.system
            except Exception:
                return None
        return None
    
    def _get_span_kind(self) -> Any:
        """Determine span kind based on span name prefix."""
        if not OTEL_AVAILABLE:
            return None
        # Get the first part of hierarchical name (e.g., "fit" from "fit.pca")
        prefix = self.name.split(".")[0]
        kind_str = _SPAN_KIND_MAP.get(prefix, "INTERNAL")
        return getattr(SpanKind, kind_str, SpanKind.INTERNAL)
    
    def _get_phase_tracer(self) -> Any:
        """Get tracer for this span.
        
        v11.1.6: Simplified - always returns global tracer.
        Phase identification is via span attributes (acm.phase), not service.name.
        """
        return _tracer
    
    def __enter__(self) -> "Span":
        self._start_time = time.perf_counter()
        
        # Capture starting resource metrics
        if self.track_resources:
            self._mem_start = self._get_memory_mb()
            self._cpu_start = self._get_cpu_times()
        
        # Use phase-specific tracer for Tempo coloring (v10.3.0)
        tracer = self._get_phase_tracer()
        if tracer is not None:
            span_kind = self._get_span_kind()
            # Include equipment in span name for easy identification in Tempo
            # e.g., "fit.pca" -> "fit.pca:FD_FAN"
            equip_suffix = f":{_config.equipment}" if _config.equipment else ""
            span_display_name = f"{self.name}{equip_suffix}"
            
            # CRITICAL: Pass current context to link spans across different TracerProviders
            # Without this, spans from phase-specific tracers won't link to parent spans
            # from the main tracer, causing "root span not yet received" in Tempo
            from opentelemetry import context as otel_context
            current_context = otel_context.get_current()
            
            self._span = tracer.start_span(
                span_display_name, 
                kind=span_kind,
                context=current_context  # Explicit parent context for cross-tracer linking
            )
            self._context_token = otel_trace.use_span(self._span, end_on_exit=False)
            self._context_token.__enter__()
            
            # Add standard attributes
            self._span.set_attribute("acm.service", _config.service_name)  # Always "acm-pipeline"
            if _config.equipment:
                self._span.set_attribute("acm.equipment", _config.equipment)
            if _config.equip_id:
                self._span.set_attribute("acm.equip_id", _config.equip_id)
            if _config.run_id:
                self._span.set_attribute("acm.run_id", _config.run_id)
            
            # Add span category for easier filtering
            category = self.name.split(".")[0]
            self._span.set_attribute("acm.category", category)
            
            # Add high-level phase for grouping and COLORING in Tempo (v10.3.0)
            # Map category to broader phase groups - each phase gets a distinct color
            # Categories extracted from all T.section() calls in acm_main.py
            phase_map = {
                # Startup phase (loading, config, initialization)
                "startup": "startup", "load": "startup", "load_data": "startup", "config": "startup",
                # Features phase (data prep, baseline, feature engineering)
                "features": "features", "data": "features", "baseline": "features", "sensor": "features",
                # Fit phase (model training/fitting)
                "fit": "fit", "train": "fit", "models": "fit",
                # Score phase (model inference, regime detection, calibration)
                "score": "score", "regimes": "score", "calibrate": "score",
                # Fusion phase (threshold, episodes, fusing detectors)
                "fusion": "fusion", "thresholds": "fusion", "episodes": "fusion",
                # Monitoring phase (drift detection, adaptive thresholds)
                "drift": "monitoring", "adaptive": "monitoring",
                # Forecast phase (RUL, health forecasting)
                "forecast": "forecast",
                # Analytics phase (comprehensive analytics)
                "analytics": "analytics", "outputs": "analytics",
                # Persist phase (SQL writes, caching)
                "persist": "persist", "sql": "persist", "write": "persist",
                # Finalize phase (cleanup, shutdown)
                "finalize": "finalize", "shutdown": "finalize",
            }
            phase = phase_map.get(category, category)
            self._span.set_attribute("acm.phase", phase)
            
            # v11.1.6: Removed "virtual service.name" hack - was setting different service.name
            # per span which is semantically wrong. Use acm.phase attribute for Tempo filtering.
            # Keep parent service reference for correlation
            self._span.set_attribute("acm.service", _config.service_name)  # Always "acm-pipeline"
            if _config.equipment:
                self._span.set_attribute("acm.equipment", _config.equipment)
            if _config.equip_id:
                self._span.set_attribute("acm.equip_id", _config.equip_id)
            if _config.run_id:
                self._span.set_attribute("acm.run_id", _config.run_id)
            
            # Add custom attributes from caller
            for key, value in self.attributes.items():
                self._span.set_attribute(f"acm.{key}", value)
            
            # Set trace context in Pyroscope for profile-to-trace correlation
            if _pyroscope_pusher is not None:
                span_context = self._span.get_span_context()
                if span_context.is_valid:
                    trace_id = format(span_context.trace_id, '032x')
                    span_id = format(span_context.span_id, '016x')
                    _pyroscope_pusher.set_trace_context(trace_id, span_id)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        elapsed = time.perf_counter() - self._start_time
        
        # Clear trace context from Pyroscope when span ends
        if _pyroscope_pusher is not None:
            _pyroscope_pusher.clear_trace_context()
        
        # Capture ending resource metrics
        mem_end = 0.0
        mem_delta = 0.0
        cpu_pct = 0.0
        if self.track_resources:
            mem_end = self._get_memory_mb()
            mem_delta = mem_end - self._mem_start
            
            # Calculate CPU usage
            if self._cpu_start is not None:
                cpu_end = self._get_cpu_times()
                if cpu_end is not None and elapsed > 0:
                    cpu_delta = cpu_end - self._cpu_start
                    # Convert to percentage (cpu_delta is seconds of CPU time)
                    cpu_pct = (cpu_delta / elapsed) * 100.0
        
        # Get context for metrics
        equipment = _config.equipment or "unknown"
        run_id = _config.run_id or ""
        parts = self.name.split(".")
        parent = parts[0] if parts else self.name
        
        # Record stage duration metric
        if _meter and "stage_duration" in _metrics:
            attrs = {
                "stage": self.name,  # Full hierarchical name
                "parent": parent,     # Top-level category
                "equipment": equipment
            }
            if run_id:
                attrs["run_id"] = run_id
            _metrics["stage_duration"].record(elapsed, attrs)
        
        # Record resource metrics (memory per module per equipment per run)
        if self.track_resources and _meter:
            resource_attrs = {
                "section": self.name,
                "equipment": equipment
            }
            if run_id:
                resource_attrs["run_id"] = run_id
            
            # Memory at end of section
            if "memory_rss_mb" in _metrics:
                _metrics["memory_rss_mb"].set(mem_end, resource_attrs)
            
            # Memory delta (how much this section added/freed)
            if "memory_delta_mb" in _metrics:
                _metrics["memory_delta_mb"].set(mem_delta, resource_attrs)
            
            # CPU usage
            if "cpu_percent" in _metrics and cpu_pct > 0:
                _metrics["cpu_percent"].set(cpu_pct, resource_attrs)
            
            # Add resource info to span
            if self._span is not None:
                self._span.set_attribute("acm.mem_mb", round(mem_end, 1))
                self._span.set_attribute("acm.mem_delta_mb", round(mem_delta, 1))
                self._span.set_attribute("acm.cpu_pct", round(cpu_pct, 1))
                self._span.set_attribute("acm.duration_s", round(elapsed, 4))
        
        # Push structured timer log to Loki with resources
        if _loki_pusher:
            _loki_pusher.log(
                "info",
                f"{self.name} completed in {elapsed:.3f}s",
                log_type="timer",
                section=self.name,
                duration_s=round(elapsed, 6),
                parent=parent,
                equipment=equipment,
                run_id=run_id,
                mem_mb=round(mem_end, 1),
                mem_delta_mb=round(mem_delta, 1),
                cpu_pct=round(cpu_pct, 1)
            )
        
        # End span
        if self._span is not None:
            if exc_val is not None:
                self._span.set_status(Status(StatusCode.ERROR, str(exc_val)))
                self._span.record_exception(exc_val)
            else:
                self._span.set_status(Status(StatusCode.OK))
            
            self._span.end()
            if self._context_token:
                self._context_token.__exit__(exc_type, exc_val, exc_tb)
    
    def set_attribute(self, key: str, value: Any) -> None:
        """Add attribute to current span."""
        if self._span is not None:
            self._span.set_attribute(key, value)


def traced(name: str, track_resources: bool = True):
    """Decorator to trace a function with optional resource tracking."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with Span(name, track_resources=track_resources):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# METRICS
# =============================================================================

def record_batch(equipment: str, rows: int, duration_s: float) -> None:
    """Record batch processing metrics."""
    if _meter:
        if "batches" in _metrics:
            _metrics["batches"].add(1, {"equipment": equipment})
        if "rows_processed" in _metrics:
            _metrics["rows_processed"].add(rows, {"equipment": equipment})
        if "run_duration" in _metrics:
            _metrics["run_duration"].record(duration_s, {"equipment": equipment, "type": "batch"})
    if _loki_pusher:
        _loki_pusher.log("info", f"Batch completed: {rows} rows in {duration_s:.2f}s", equipment=equipment, rows=rows, duration_s=duration_s)


def record_run(equipment: str, outcome: str, duration_s: float) -> None:
    """Record run outcome metrics."""
    if _meter:
        if "runs" in _metrics:
            _metrics["runs"].add(1, {"equipment": equipment, "outcome": outcome})
        if "run_duration" in _metrics:
            _metrics["run_duration"].record(duration_s, {"equipment": equipment, "outcome": outcome})
    if _loki_pusher:
        _loki_pusher.log("info", f"Run {outcome}: {duration_s:.2f}s", equipment=equipment, outcome=outcome, duration_s=duration_s)


def record_batch_processed(equipment: str, rows: int = 0, duration_seconds: float = 0.0, **kwargs) -> None:
    """Record batch rows processed."""
    if _meter and "rows_processed" in _metrics:
        _metrics["rows_processed"].add(rows, {"equipment": equipment})
    if _loki_pusher:
        _loki_pusher.log("info", f"Batch processed: {rows} rows in {duration_seconds:.1f}s", equipment=equipment, rows=rows, duration_seconds=duration_seconds)


def record_health(equipment: str, health: float) -> None:
    """Record health score metric."""
    if _meter and "health_score" in _metrics:
        _metrics["health_score"].set(health, {"equipment": equipment})
    if _loki_pusher:
        _loki_pusher.log("info", f"Health: {health:.1f}%", equipment=equipment, health=health)


def record_health_score(equipment: str, health: float) -> None:
    """Alias for record_health."""
    record_health(equipment, health)


def record_rul(equipment: str, rul_hours: float, p10: float = 0, p50: float = 0, p90: float = 0) -> None:
    """Record RUL prediction with confidence bounds."""
    if _meter and "rul_hours" in _metrics:
        _metrics["rul_hours"].set(rul_hours, {"equipment": equipment, "percentile": "mean"})
        if p10 > 0:
            _metrics["rul_hours"].set(p10, {"equipment": equipment, "percentile": "p10"})
        if p50 > 0:
            _metrics["rul_hours"].set(p50, {"equipment": equipment, "percentile": "p50"})
        if p90 > 0:
            _metrics["rul_hours"].set(p90, {"equipment": equipment, "percentile": "p90"})
    if _loki_pusher:
        _loki_pusher.log("info", f"RUL: {rul_hours:.1f}h", equipment=equipment, rul_hours=rul_hours, p10=p10, p50=p50, p90=p90)


def record_active_defects(equipment: str, count: int) -> None:
    """Record active defect count."""
    if _meter and "active_defects" in _metrics:
        _metrics["active_defects"].set(count, {"equipment": equipment})
    if _loki_pusher:
        _loki_pusher.log("info", f"Active defects: {count}", equipment=equipment, active_defects=count)


def record_episode(equipment: str, count: int = 1, episode_id: str = "", severity: str = "warning") -> None:
    """Record episode event(s)."""
    if _meter and "episodes" in _metrics:
        _metrics["episodes"].add(count, {"equipment": equipment, "severity": severity})
    if _loki_pusher:
        _loki_pusher.log("info", f"Episode: {count} detected ({severity})", equipment=equipment, episode_id=episode_id, severity=severity, count=count)


def record_error(equipment: str, error: str, error_type: str = "unknown") -> None:
    """Record error event."""
    if _meter and "errors" in _metrics:
        _metrics["errors"].add(1, {"equipment": equipment, "error_type": error_type})
    if _loki_pusher:
        _loki_pusher.log("error", f"Error: {error}", equipment=equipment, error=error, error_type=error_type)


def record_coldstart(equipment: str, status: str = "complete") -> None:
    """Record coldstart status."""
    if _meter and "coldstarts" in _metrics and status == "complete":
        _metrics["coldstarts"].add(1, {"equipment": equipment})
    if _loki_pusher:
        _loki_pusher.log("info", f"Coldstart: {status}", equipment=equipment, coldstart_status=status)


def record_sql_op(table: str = "", operation: str = "", rows: int = 0, 
                  equipment: str = "", duration_ms: float = 0.0) -> None:
    """Record SQL operation metrics."""
    if _meter and "sql_ops" in _metrics:
        _metrics["sql_ops"].add(1, {"table": table, "operation": operation, "equipment": equipment})
    if _loki_pusher:
        _loki_pusher.log("debug", f"SQL: {operation} {table} ({rows} rows, {duration_ms:.1f}ms)", 
                        table=table, operation=operation, rows=rows, equipment=equipment, duration_ms=duration_ms)


def record_detector_scores(equipment: str, scores: dict) -> None:
    """Record per-detector z-scores.
    
    Args:
        equipment: Equipment name
        scores: Dict of detector_name -> z_score, e.g.:
            {"ar1_z": 2.5, "pca_spe_z": 1.2, "fused_z": 3.1}
    """
    if _meter:
        # Record fused score
        if "fused_z" in _metrics and "fused_z" in scores:
            _metrics["fused_z"].set(float(scores["fused_z"]), {"equipment": equipment})
        
        # Record individual detector scores
        if "detector_z" in _metrics:
            for detector in ["ar1_z", "pca_spe_z", "pca_t2_z", "iforest_z", "gmm_z", "omr_z"]:
                if detector in scores:
                    _metrics["detector_z"].set(
                        float(scores[detector]), 
                        {"equipment": equipment, "detector": detector.replace("_z", "")}
                    )
    
    if _loki_pusher:
        fused = scores.get("fused_z", 0)
        _loki_pusher.log("info", f"Detector scores: fused_z={fused:.2f}", 
                        equipment=equipment, component="detector", **{k: round(v, 3) for k, v in scores.items()})


def record_regime(equipment: str, regime_id: int, regime_label: str = "") -> None:
    """Record current operating regime."""
    if _meter and "regime" in _metrics:
        _metrics["regime"].set(regime_id, {"equipment": equipment, "label": regime_label})
    if _loki_pusher:
        _loki_pusher.log("info", f"Regime: {regime_id} ({regime_label})", 
                        equipment=equipment, component="regime", regime_id=regime_id, regime_label=regime_label)


def record_data_quality(equipment: str, quality_score: float, missing_pct: float = 0.0, 
                        outlier_pct: float = 0.0, sensors_dropped: int = 0) -> None:
    """Record data quality metrics."""
    if _meter and "data_quality" in _metrics:
        _metrics["data_quality"].set(quality_score, {"equipment": equipment})
    if _loki_pusher:
        _loki_pusher.log("info", f"Data quality: {quality_score:.1f}%", 
                        equipment=equipment, component="data",
                        quality_score=quality_score, missing_pct=missing_pct, 
                        outlier_pct=outlier_pct, sensors_dropped=sensors_dropped)


def record_model_refit(equipment: str, reason: str = "", detector: str = "") -> None:
    """Record model refit/retrain event."""
    if _meter and "model_refits" in _metrics:
        _metrics["model_refits"].add(1, {"equipment": equipment, "reason": reason, "detector": detector})
    if _loki_pusher:
        _loki_pusher.log("info", f"Model refit: {detector} ({reason})", 
                        equipment=equipment, component="model", reason=reason, detector=detector)


# =============================================================================
# RESOURCE METRICS (CPU, Memory, Section Profiling)
# =============================================================================

def record_memory(current_mb: float, peak_mb: float = 0.0, 
                  equipment: str = "", section: str = "", run_id: str = "") -> None:
    """Record memory usage metrics.
    
    Args:
        current_mb: Current RSS memory in MB
        peak_mb: Peak memory during section in MB
        equipment: Equipment name
        section: Code section name (optional)
        run_id: Run identifier for drill-down
    """
    # Get run_id from context if not provided
    if not run_id:
        run_id = _config.run_id or ""
    
    if _meter:
        if "memory_rss_mb" in _metrics:
            attrs = {"equipment": equipment}
            if section:
                attrs["section"] = section
            if run_id:
                attrs["run_id"] = run_id
            _metrics["memory_rss_mb"].set(current_mb, attrs)
        if "memory_peak_mb" in _metrics and peak_mb > 0:
            peak_attrs = {"equipment": equipment}
            if run_id:
                peak_attrs["run_id"] = run_id
            _metrics["memory_peak_mb"].set(peak_mb, peak_attrs)
    
    # Log to Loki with structured data only (no console spam)
    # The memory values are used for metrics dashboards, not human reading
    if _loki_pusher:
        _loki_pusher.log(
            "debug", 
            f"memory_sample",
            component="resource",
            log_type="memory",
            memory_mb=round(current_mb, 1),
            memory_peak_mb=round(peak_mb, 1),
            section=section or "global",
            equipment=equipment,
            run_id=run_id
        )


def record_cpu(percent: float, equipment: str = "", section: str = "") -> None:
    """Record CPU usage metric.
    
    Args:
        percent: CPU percentage (0-100 per core, can exceed 100 for multi-core)
        equipment: Equipment name
        section: Code section name (optional)
    """
    if _meter and "cpu_percent" in _metrics:
        attrs = {"equipment": equipment}
        if section:
            attrs["section"] = section
        _metrics["cpu_percent"].set(percent, attrs)
    
    if _loki_pusher:
        _loki_pusher.log(
            "debug",
            f"CPU: {percent:.1f}%",
            component="resource",
            log_type="cpu",
            cpu_percent=round(percent, 1),
            section=section or "global",
            equipment=equipment
        )


def record_section_resources(section: str, duration_s: float, 
                             mem_start_mb: float = 0, mem_end_mb: float = 0,
                             mem_peak_mb: float = 0, mem_delta_mb: float = 0,
                             cpu_avg_pct: float = 0, equipment: str = "",
                             run_id: str = "") -> None:
    """Record comprehensive resource metrics for a code section.
    
    Args:
        section: Section name (e.g., "detector.fit.pca")
        duration_s: Duration in seconds
        mem_start_mb: Memory at start in MB
        mem_end_mb: Memory at end in MB
        mem_peak_mb: Peak memory during section in MB
        mem_delta_mb: Memory change (end - start) in MB
        cpu_avg_pct: Average CPU percentage
        equipment: Equipment name
        run_id: Run identifier for drill-down
    """
    # Get run_id from context if not provided
    if not run_id:
        run_id = _config.run_id or ""
    
    if _meter:
        attrs = {"equipment": equipment, "section": section}
        if run_id:
            attrs["run_id"] = run_id
        
        if "section_duration" in _metrics:
            _metrics["section_duration"].record(duration_s, attrs)
        
        if "memory_delta_mb" in _metrics:
            _metrics["memory_delta_mb"].set(mem_delta_mb, attrs)
        
        if "memory_rss_mb" in _metrics:
            mem_attrs = {"equipment": equipment, "section": section}
            if run_id:
                mem_attrs["run_id"] = run_id
            _metrics["memory_rss_mb"].set(mem_end_mb, mem_attrs)
        
        if "cpu_percent" in _metrics and cpu_avg_pct > 0:
            _metrics["cpu_percent"].set(cpu_avg_pct, attrs)
    
    if _loki_pusher:
        _loki_pusher.log(
            "info",
            f"Section {section}: {duration_s:.3f}s, mem={mem_delta_mb:+.1f}MB, cpu={cpu_avg_pct:.0f}%",
            component="resource",
            log_type="section_profile",
            section=section,
            duration_s=round(duration_s, 4),
            mem_start_mb=round(mem_start_mb, 1),
            mem_end_mb=round(mem_end_mb, 1),
            mem_peak_mb=round(mem_peak_mb, 1),
            mem_delta_mb=round(mem_delta_mb, 1),
            cpu_avg_pct=round(cpu_avg_pct, 1),
            equipment=equipment,
            run_id=run_id
        )


def record_cpu_per_core(core_percentages: list, equipment: str = "") -> None:
    """Record CPU usage per logical core.
    
    Args:
        core_percentages: List of CPU percentages for each core
        equipment: Equipment name
    """
    if _meter and "cpu_per_core" in _metrics:
        for core_id, pct in enumerate(core_percentages):
            _metrics["cpu_per_core"].set(pct, {"equipment": equipment, "core": str(core_id)})


def record_gpu(gpu_id: int = 0, utilization_pct: float = 0, memory_used_mb: float = 0,
               memory_percent: float = 0, temperature_c: float = 0, 
               gpu_name: str = "", equipment: str = "") -> None:
    """Record GPU usage metrics.
    
    Args:
        gpu_id: GPU index (0, 1, 2, ...)
        utilization_pct: GPU compute utilization (0-100)
        memory_used_mb: GPU memory used in MB
        memory_percent: GPU memory utilization percentage
        temperature_c: GPU temperature in Celsius
        gpu_name: GPU model name
        equipment: Equipment being processed
    """
    if _meter:
        attrs = {"equipment": equipment, "gpu_id": str(gpu_id)}
        
        if "gpu_utilization" in _metrics:
            _metrics["gpu_utilization"].set(utilization_pct, attrs)
        if "gpu_memory_used" in _metrics:
            _metrics["gpu_memory_used"].set(memory_used_mb, attrs)
        if "gpu_memory_percent" in _metrics:
            _metrics["gpu_memory_percent"].set(memory_percent, attrs)
        if "gpu_temperature" in _metrics and temperature_c > 0:
            _metrics["gpu_temperature"].set(temperature_c, attrs)
    
    if _loki_pusher:
        _loki_pusher.log(
            "debug",
            f"GPU{gpu_id} ({gpu_name}): {utilization_pct:.0f}% util, {memory_used_mb:.0f}MB ({memory_percent:.0f}%), {temperature_c}°C",
            component="resource",
            log_type="gpu",
            gpu_id=gpu_id,
            gpu_name=gpu_name,
            gpu_utilization_pct=round(utilization_pct, 1),
            gpu_memory_mb=round(memory_used_mb, 0),
            gpu_memory_pct=round(memory_percent, 1),
            gpu_temp_c=temperature_c,
            equipment=equipment
        )


def record_capacity(equipment: str = "", equipment_count: int = 0, tag_count: int = 0,
                    rows_processed: int = 0, duration_s: float = 0, 
                    parallel_workers: int = 1) -> None:
    """Record capacity planning metrics for hardware sizing.
    
    Args:
        equipment: Equipment name(s) being processed
        equipment_count: Number of equipment being processed
        tag_count: Number of sensor tags being processed
        rows_processed: Number of data rows processed
        duration_s: Processing duration in seconds
        parallel_workers: Number of parallel workers active
    """
    if _meter:
        attrs = {"equipment": equipment}
        
        if "equipment_count" in _metrics:
            _metrics["equipment_count"].set(equipment_count, attrs)
        if "tag_count" in _metrics:
            _metrics["tag_count"].set(tag_count, attrs)
        if "parallel_workers" in _metrics:
            _metrics["parallel_workers"].set(parallel_workers, attrs)
        
        # Calculate throughput
        if "rows_per_second" in _metrics and duration_s > 0:
            rps = rows_processed / duration_s
            _metrics["rows_per_second"].set(rps, attrs)
        
        if "batch_duration" in _metrics and duration_s > 0:
            _metrics["batch_duration"].record(duration_s, attrs)
    
    if _loki_pusher:
        rps = rows_processed / duration_s if duration_s > 0 else 0
        _loki_pusher.log(
            "info",
            f"Capacity: {equipment_count} equip, {tag_count} tags, {rows_processed} rows in {duration_s:.1f}s ({rps:.0f} rows/s)",
            component="capacity",
            log_type="capacity",
            equipment=equipment,
            equipment_count=equipment_count,
            tag_count=tag_count,
            rows_processed=rows_processed,
            duration_s=round(duration_s, 2),
            rows_per_second=round(rps, 1),
            parallel_workers=parallel_workers
        )


def record_disk_io(read_mb: float = 0, write_mb: float = 0, 
                   equipment: str = "", section: str = "") -> None:
    """Record disk I/O metrics for a section.
    
    Args:
        read_mb: Bytes read in MB
        write_mb: Bytes written in MB  
        equipment: Equipment being processed
        section: Code section name
    """
    if _meter:
        attrs = {"equipment": equipment, "section": section}
        
        if "disk_read_mb" in _metrics:
            _metrics["disk_read_mb"].set(read_mb, attrs)
        if "disk_write_mb" in _metrics:
            _metrics["disk_write_mb"].set(write_mb, attrs)
        if "disk_read_total_mb" in _metrics and read_mb > 0:
            _metrics["disk_read_total_mb"].add(read_mb, attrs)
        if "disk_write_total_mb" in _metrics and write_mb > 0:
            _metrics["disk_write_total_mb"].add(write_mb, attrs)
    
    # Only log significant I/O (>1MB)
    if _loki_pusher and (read_mb > 1 or write_mb > 1):
        _loki_pusher.log(
            "debug",
            f"Disk I/O [{section}]: read={read_mb:.1f}MB, write={write_mb:.1f}MB",
            component="resource",
            log_type="disk_io",
            equipment=equipment,
            section=section,
            disk_read_mb=round(read_mb, 2),
            disk_write_mb=round(write_mb, 2)
        )


def log_timer(section: str, duration_s: float, pct: float = 0.0, 
              parent: str = "", total_s: float = 0.0) -> None:
    """Log timer section with structured fields for Loki.
    
    Args:
        section: Timer section name (e.g., 'models.persistence.load')
        duration_s: Duration in seconds
        pct: Percentage of parent time (optional)
        parent: Parent section name (optional)
        total_s: Total run time for percentage calculation (optional)
    """
    if _loki_pusher:
        # Format message with percentage if available
        if pct > 0:
            msg = f"{section}: {duration_s:.3f}s ({pct:.1f}%)"
        else:
            msg = f"{section}: {duration_s:.3f}s"
        
        _loki_pusher.log(
            "info", 
            msg,
            component="timer",  # Use component for Loki label filtering
            log_type="timer",
            section=section,
            parent=parent if parent else "root"
        )


def get_tracer():
    """Get the OpenTelemetry tracer."""
    return _tracer


def get_meter():
    """Get the OpenTelemetry meter."""
    return _meter


# OTEL availability flag
OTEL_AVAILABLE = OTEL_AVAILABLE if "OTEL_AVAILABLE" in dir() else False


# =============================================================================
# LOKI LOG PUSHER (Native Loki API)
# =============================================================================

import json
import urllib.request
import urllib.error

class _LokiPusher:
    """Push logs to Loki using native push API (not OTLP).
    
    Loki uses LABELS for efficient filtering and the log LINE for the message.
    Labels should contain: level, component (from [BRACKETS]), equip_id, etc.
    Loki uses LABELS for efficient filtering and the log LINE for the message.
    Labels are passed as parameters from Console methods - no regex extraction needed.
    
    Example output in Grafana:
        {app="acm", level="info", component="fuse", equip_id="1"} Computing final fusion...
    
    Label structure:
        - app: "acm" (static)
        - service: service name (static)
        - equipment: equipment name (static)
        - level: info/warning/error/debug (per-log)
        - component: fuse/data/model/sql etc. (per-log, from caller)
        - equip_id: equipment ID as string (per-log)
        - run_id: run identifier (per-log, if set)
        - tag: optional extra tag like "success" (per-log)
    
    Rate Limiting:
        - Batches up to 100 logs per push
        - Flushes every 5 seconds
        - On 429 (rate limit), backs off with exponential delay
    """
    
    def __init__(self, endpoint: str, labels: Dict[str, str], batch_size: int = 100):
        self._endpoint = endpoint
        self._base_labels = labels  # Static labels: app, service, equipment
        self._batch_size = batch_size
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._connected = False
        self._backoff_until = 0.0  # Timestamp until which we should back off
        self._consecutive_failures = 0
        
        # Test connection
        try:
            req = urllib.request.Request(
                endpoint.replace("/loki/api/v1/push", "/ready"),
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                self._connected = resp.status == 200
        except Exception:
            self._connected = False
        
        if self._connected:
            # Background flush thread
            self._thread = threading.Thread(target=self._flush_loop, daemon=True)
            self._thread.start()
    
    def log(self, level: str, message: str, component: Optional[str] = None, **context) -> None:
        """Queue a structured log record for Loki.
        
        Args:
            level: Log level (info, warning, error, debug)
            message: Clean log message (no [COMPONENT] prefix needed)
            component: Component name (e.g., "DATA", "MODEL", "FUSE")
            **context: Additional labels (e.g., tag="success")
        
        The message is sent as-is. Component becomes a Loki label.
        No regex extraction - component is passed explicitly from Console methods.
        
        Trace context:
            trace_id and span_id are automatically captured from the current
            OpenTelemetry span context. This enables Grafana's logs-to-traces
            correlation. The trace_id is formatted as a 32-char hex string
            (matching Tempo's format), and span_id as 16-char hex.
        """
        if not self._connected:
            return
        
        # Loki expects nanosecond timestamps
        ts_ns = str(int(time.time() * 1_000_000_000))
        
        # Build dynamic labels (merged with base labels)
        # Note: Loki labels must be strings
        labels = {
            **self._base_labels,
            "level": level,
            "component": (component or "general").lower(),
            "equip_id": str(_config.equip_id) if _config.equip_id else "0",
        }
        
        # Add trace_id and span_id from current span for trace-to-logs correlation
        # This enables Grafana's "derived fields" to link logs -> traces
        if OTEL_AVAILABLE and otel_trace is not None:
            try:
                current_span = otel_trace.get_current_span()
                if current_span is not None:
                    span_ctx = current_span.get_span_context()
                    # Use is_valid to check if context has valid trace/span IDs
                    # Don't use is_recording() - non-recording spans still have valid context
                    if span_ctx is not None and span_ctx.is_valid:
                        # Format as 32-char hex string (Tempo format) - trace_id is 128-bit
                        labels["trace_id"] = format(span_ctx.trace_id, '032x')
                        # Format as 16-char hex string - span_id is 64-bit
                        labels["span_id"] = format(span_ctx.span_id, '016x')
            except Exception:
                pass  # Best effort - don't break logging
        
        # Add optional context as labels (must be strings)
        # Handle known label fields from context
        if context.get("tag"):
            labels["tag"] = str(context.pop("tag"))
        if context.get("log_type"):
            labels["log_type"] = str(context.pop("log_type"))
        if context.get("section"):
            labels["section"] = str(context.pop("section"))
        if context.get("parent"):
            labels["parent"] = str(context.pop("parent"))
        if _config.run_id:
            labels["run_id"] = _config.run_id
        
        # Queue the entry: (timestamp, labels_dict, message)
        self._queue.put((ts_ns, labels, message))
    
    def _flush_loop(self) -> None:
        """Background thread that flushes logs to Loki with rate limiting."""
        while not self._stop.is_set():
            # Check if we're in backoff mode
            now = time.time()
            if now < self._backoff_until:
                # Still in backoff - wait
                time.sleep(min(1.0, self._backoff_until - now))
                continue
            
            self._flush_batch()
            time.sleep(5.0)  # Flush every 5 seconds (not 2)
        self._flush_batch()  # Final flush
    
    def _flush_batch(self) -> None:
        """Flush queued logs to Loki.
        
        Since each log can have different labels (level, component), we need to
        group them by label set. Loki requires all entries in a stream to have
        the same labels.
        
        New payload format (proper Loki structure):
        {
            "streams": [
                {"stream": {"app":"acm", "level":"info", "component":"fuse"}, "values": [[ts, "msg1"], [ts, "msg2"]]},
                {"stream": {"app":"acm", "level":"error", "component":"sql"}, "values": [[ts, "error msg"]]}
            ]
        }
        """
        batch = []
        while len(batch) < self._batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        
        if not batch:
            return
        
        # Group by label set (convert dict to frozenset for hashing)
        # Each entry is (ts_ns, labels_dict, message)
        streams_map = {}  # type: ignore
        for ts_ns, labels, message in batch:
            label_key = frozenset(labels.items())
            if label_key not in streams_map:
                streams_map[label_key] = {"labels": labels, "values": []}
            streams_map[label_key]["values"].append([ts_ns, message])
        
        # Build Loki push payload with multiple streams
        streams_list = []
        for stream_data in streams_map.values():
            streams_list.append({
                "stream": stream_data["labels"],
                "values": stream_data["values"]
            })
        payload = {"streams": streams_list}
        
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self._endpoint,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                # Success - reset backoff
                self._consecutive_failures = 0
                self._backoff_until = 0.0
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Rate limited - exponential backoff
                self._consecutive_failures += 1
                backoff_secs = min(60.0, 2.0 ** self._consecutive_failures)
                self._backoff_until = time.time() + backoff_secs
                # Only log first occurrence
                if self._consecutive_failures == 1:
                    print(f"[LOKI] Rate limited (429), backing off {backoff_secs:.0f}s")
            elif not hasattr(self, '_http_error_logged'):
                # Log other HTTP errors once (don't spam)
                print(f"[LOKI] Push failed: {e.code} {e.reason}")
                self._http_error_logged = True
        except Exception:
            pass  # Don't crash on other failures
    
    def _flush_all(self) -> None:
        """Drain the queue completely."""
        while True:
            try:
                self._flush_batch()
                if self._queue.empty():
                    break
            except Exception:
                break
    
    def close(self) -> None:
        """Stop background thread and flush remaining logs."""
        self._stop.set()
        if hasattr(self, "_thread") and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        # Final synchronous flush of any remaining logs
        self._flush_all()


# =============================================================================
# PYROSCOPE PUSHER (yappi + HTTP API + tracemalloc for memory)
# =============================================================================

# Try to import tracemalloc for memory profiling
try:
    import tracemalloc
    TRACEMALLOC_AVAILABLE = True
except ImportError:
    tracemalloc = None
    TRACEMALLOC_AVAILABLE = False


class _PyroscopePusher:
    """Push profiling data to Pyroscope using yappi (CPU) and tracemalloc (memory).
    
    This avoids requiring pyroscope-io (which needs Rust compilation on Windows).
    Uses yappi (pure Python profiler) and Pyroscope's simple /ingest endpoint.
    
    Profile types pushed:
        - process_cpu:cpu:nanoseconds:cpu:nanoseconds (CPU time via yappi)
        - memory:alloc_objects:count:space:bytes (Memory allocations via tracemalloc)
    
    Profile format (collapsed/folded):
        function1;function2;function3 <count>
        main;process_data;compute 150
        main;load_data;read_sql 42
    
    Labels (for correlation with traces/logs):
        - service_name: "acm-pipeline" (standard Grafana label)
        - equipment: Equipment name (e.g., "FD_FAN")
        - equip_id: Equipment database ID  
        - run_id: Current run identifier (for log/trace correlation)
    """
    
    def __init__(self, endpoint: str, app_name: str, tags: Dict[str, str]):
        self._endpoint = endpoint
        self._app_name = app_name
        # Standardize tags for Grafana correlation
        # Always include service_name for Grafana's tracesToProfiles
        self._tags = {
            "service_name": tags.get("service", "acm-pipeline"),
            **{k: v for k, v in tags.items() if k != "service"}
        }
        self._profiling_active = False
        self._memory_profiling_active = False
        self._profile_start_time: Optional[float] = None
        self._current_trace_id: Optional[str] = None
        self._current_span_id: Optional[str] = None
    
    def set_trace_context(self, trace_id: Optional[str], span_id: Optional[str]) -> None:
        """Set current trace/span context for profile correlation.
        
        Called by Span.__enter__ to link profiles to the active trace.
        """
        self._current_trace_id = trace_id
        self._current_span_id = span_id
    
    def clear_trace_context(self) -> None:
        """Clear trace context when span ends."""
        self._current_trace_id = None
        self._current_span_id = None
        
    def start(self) -> None:
        """Start CPU and memory profiling for the current process."""
        if self._profiling_active:
            return
        
        # Start CPU profiling with yappi
        if YAPPI_AVAILABLE:
            try:
                yappi.clear_stats()
                yappi.start(builtins=False)
                self._profiling_active = True
                self._profile_start_time = time.time()
            except Exception as e:
                Console.warn(f"Failed to start CPU profiling: {e}", component="PROFILE", error_type=type(e).__name__, error=str(e)[:200])
        
        # Start memory profiling with tracemalloc
        if TRACEMALLOC_AVAILABLE and not self._memory_profiling_active:
            try:
                tracemalloc.start(25)  # Track 25 frames for detailed stacks
                self._memory_profiling_active = True
            except Exception as e:
                Console.warn(f"Failed to start memory profiling: {e}", component="PROFILE", error_type=type(e).__name__, error=str(e)[:200])
    
    def stop_and_push(self) -> None:
        """Stop CPU and memory profiling and push results to Pyroscope."""
        # Calculate time range first (needed for both profile types)
        end_time = time.time()
        start_time = self._profile_start_time or (end_time - 60)
        
        # Push CPU profile (yappi)
        if self._profiling_active and YAPPI_AVAILABLE:
            try:
                yappi.stop()
                self._profiling_active = False
                
                # Get function stats
                stats = yappi.get_func_stats()
                if stats:
                    # Log top CPU-consuming functions locally for visibility
                    self._log_top_functions(stats, top_n=10)
                    
                    # Convert to collapsed format and push
                    collapsed_lines = self._stats_to_collapsed(stats)
                    if collapsed_lines:
                        self._push_profile(
                            collapsed_lines, 
                            int(start_time), 
                            int(end_time),
                            profile_type="cpu",
                            units="samples",
                        )
            except Exception as e:
                Console.warn(f"Failed to push CPU profile: {e}", component="PROFILE", endpoint=self._endpoint, error_type=type(e).__name__, error=str(e)[:200])
            finally:
                try:
                    yappi.clear_stats()
                except Exception:
                    pass
        
        # Push memory profile (tracemalloc)
        if self._memory_profiling_active and TRACEMALLOC_AVAILABLE:
            try:
                snapshot = tracemalloc.take_snapshot()
                tracemalloc.stop()
                self._memory_profiling_active = False
                
                # Convert memory snapshot to collapsed format
                memory_lines = self._memory_snapshot_to_collapsed(snapshot)
                if memory_lines:
                    self._push_profile(
                        memory_lines,
                        int(start_time),
                        int(end_time),
                        profile_type="alloc_objects",
                        units="objects",
                    )
                    # Also push bytes allocated
                    memory_bytes_lines = self._memory_snapshot_to_collapsed(snapshot, use_bytes=True)
                    if memory_bytes_lines:
                        self._push_profile(
                            memory_bytes_lines,
                            int(start_time),
                            int(end_time),
                            profile_type="alloc_space",
                            units="bytes",
                        )
            except KeyboardInterrupt:
                pass  # Graceful exit on Ctrl+C during memory profiling
            except Exception as e:
                Console.warn(f"Failed to push memory profile: {e}", component="PROFILE", endpoint=self._endpoint, error_type=type(e).__name__, error=str(e)[:200])
    
    def _memory_snapshot_to_collapsed(self, snapshot, use_bytes: bool = False, top_n: int = 500) -> List[str]:
        """Convert tracemalloc snapshot to collapsed stack format.
        
        Args:
            snapshot: tracemalloc snapshot
            use_bytes: If True, use bytes as sample value; otherwise use count
            top_n: Limit to top N allocations
        
        Returns:
            List of collapsed stack lines with readable function names
        """
        import linecache
        import os
        
        # Filter out profiler noise (yappi, tracemalloc itself, threading internals)
        NOISE_PATTERNS = {
            'yappi', 'tracemalloc', '_yappi', 'threading_bootstrap',
            'weakrefset', '_weakrefset', 'profile_thread_callback',
        }
        
        lines = []
        try:
            # Group by traceback and sum allocations
            stats = snapshot.statistics('traceback')[:top_n * 2]  # Get more to compensate for filtering
            
            filtered_count = 0
            for stat in stats:
                if filtered_count >= top_n:
                    break
                    
                # Skip if any frame is from profiler internals
                is_noise = False
                for frame in stat.traceback:
                    filename_lower = frame.filename.lower()
                    for pattern in NOISE_PATTERNS:
                        if pattern in filename_lower:
                            is_noise = True
                            break
                    if is_noise:
                        break
                
                if is_noise:
                    continue
                    
                filtered_count += 1
                # Build stack from traceback (reversed for Pyroscope - oldest first)
                stack_parts = []
                for frame in reversed(stat.traceback):
                    filename = frame.filename
                    lineno = frame.lineno
                    
                    # Try to get function name from source code
                    func_name = self._get_function_name_at_line(filename, lineno)
                    
                    # Clean up module name from filename
                    module_name = filename
                    if "/" in filename or "\\" in filename:
                        parts = filename.replace("\\", "/").split("/")
                        # Keep ACM package structure
                        if "core" in parts:
                            idx = parts.index("core")
                            module_name = ".".join(parts[idx:])
                        elif "scripts" in parts:
                            idx = parts.index("scripts")
                            module_name = ".".join(parts[idx:])
                        else:
                            module_name = os.path.basename(filename)
                        module_name = module_name.replace(".py", "")
                    
                    # Build readable symbol: module.function or module.<line N> if no function found
                    if func_name:
                        symbol = f"{module_name}.{func_name}"
                    else:
                        symbol = f"{module_name}.<line {lineno}>"
                    
                    stack_parts.append(symbol)
                
                if stack_parts:
                    stack = ";".join(stack_parts)
                    value = stat.size if use_bytes else stat.count
                    if value > 0:
                        lines.append(f"{stack} {value}")
        except Exception:
            pass
        
        return lines
    
    def _get_function_name_at_line(self, filename: str, lineno: int) -> Optional[str]:
        """Try to determine the function name containing the given line.
        
        Uses linecache to read the file and searches backward from the line
        to find the enclosing 'def' or 'class' statement.
        """
        import linecache
        import re
        
        # Skip frozen/built-in modules - no source available
        if filename.startswith('<frozen') or filename.startswith('<'):
            return None
            
        # Skip if file doesn't exist or isn't readable
        if not filename or not os.path.isfile(filename):
            return None
        
        try:
            # Search backward from lineno to find enclosing function/class
            for search_line in range(lineno, max(1, lineno - 100), -1):
                line = linecache.getline(filename, search_line)
                if not line:
                    continue
                
                # Match function definition (including async def)
                func_match = re.match(r'\s*(?:async\s+)?def\s+(\w+)\s*\(', line)
                if func_match:
                    return func_match.group(1)
                
                # Match class definition
                class_match = re.match(r'\s*class\s+(\w+)\s*[:\(]', line)
                if class_match:
                    return class_match.group(1)
            
            return None
        except Exception:
            return None
    
    def _log_top_functions(self, stats, top_n: int = 10) -> None:
        """Log the top N CPU-consuming functions."""
        # Sort by total time and get top N
        sorted_stats = sorted(stats, key=lambda s: s.ttot, reverse=True)[:top_n]
        
        if sorted_stats:
            Console.section("Top CPU Functions")
            for i, stat in enumerate(sorted_stats, 1):
                # Format time nicely
                ttot_ms = stat.ttot * 1000
                ncall = stat.ncall
                module = stat.module or ""
                name = stat.name or "unknown"
                
                # Clean up module path
                if "/" in module or "\\" in module:
                    import os
                    module = os.path.basename(module).replace(".py", "")
                
                Console.status(f"  {i:2}. {module}.{name}: {ttot_ms:.1f}ms ({ncall} calls)")
    
    def _stats_to_collapsed(self, stats) -> List[str]:
        """Convert yappi stats to collapsed stack format.
        
        Collapsed format: "func1;func2;func3 <total_time_in_microseconds>"
        
        Since yappi gives us flat function stats (not stack traces),
        we create a meaningful stack from the full module path.
        """
        lines = []
        for stat in stats:
            # Build a descriptive stack from module.function
            module = stat.module or "unknown"
            name = stat.name or "unknown"
            full_name = stat.full_name or f"{module}.{name}"
            
            # Extract meaningful path (keep package structure for ACM code)
            if "core" in module or "acm" in module.lower():
                # ACM code - keep the package structure
                # e.g., "c:\path\to\ACM\core\fuse.py" -> "core.fuse"
                import os
                parts = module.replace("\\", "/").split("/")
                # Find "core" or relevant package
                try:
                    if "core" in parts:
                        idx = parts.index("core")
                        module = ".".join(parts[idx:])
                    elif "scripts" in parts:
                        idx = parts.index("scripts")
                        module = ".".join(parts[idx:])
                    else:
                        module = os.path.splitext(os.path.basename(module))[0]
                except (ValueError, IndexError):
                    module = os.path.splitext(os.path.basename(module))[0]
                # Remove .py extension
                module = module.replace(".py", "")
            elif "/" in module or "\\" in module:
                # External code - just use filename
                import os
                module = os.path.splitext(os.path.basename(module))[0]
            
            # Skip internal/builtin functions
            if name.startswith("_") and not name.startswith("__init__"):
                if stat.ttot < 0.001:  # Skip if < 1ms
                    continue
            
            # Stack format: module;function <sample_count>
            # Use CALL COUNT (ncall) as sample count - this is what Pyroscope expects
            # NOT time (ttot) which causes cumulative inflation
            sample_count = stat.ncall
            if sample_count > 0 and stat.ttot > 0.001:  # At least 1 call and > 1ms total time
                stack = f"{module};{name}"
                lines.append(f"{stack} {sample_count}")
        
        return lines
    
    def _push_profile(
        self, 
        collapsed_lines: List[str], 
        from_ts: int, 
        until_ts: int,
        profile_type: str = "cpu",
        units: str = "samples",
    ) -> None:
        """Push collapsed profile to Pyroscope /ingest endpoint.
        
        Args:
            collapsed_lines: Profile data in collapsed/folded format
            from_ts: Start timestamp (UNIX seconds)
            until_ts: End timestamp (UNIX seconds)
            profile_type: Profile type (cpu, alloc_objects, alloc_space)
            units: Unit type (samples, objects, bytes)
        
        Query params:
            - name: app name with profile type and optional labels {key=value}
                   Format: app_name.profile_type{key=value,...}
                   e.g., acm.cpu{service_name=acm-pipeline,equipment=FD_FAN}
            - from: UNIX timestamp start
            - until: UNIX timestamp end
            - format: folded (collapsed)
            - sampleRate: 100 (default)
            - spyName: yappi (our Python profiler - NOT pyspy)
            - units: samples/objects/bytes
        """
        # Build labels dict (include trace context if available)
        labels = dict(self._tags)
        if self._current_trace_id:
            labels["trace_id"] = self._current_trace_id
        if self._current_span_id:
            labels["span_id"] = self._current_span_id
        
        # Build label string
        labels_str = ",".join(f"{k}={v}" for k, v in labels.items())
        
        # App name must include profile type: app_name.profile_type{labels}
        # Pyroscope expects: acm.cpu{service_name=acm-pipeline,equipment=FD_FAN}
        app_with_labels = f"{self._app_name}.{profile_type}{{{labels_str}}}" if labels_str else f"{self._app_name}.{profile_type}"
        
        # Duration in seconds for this profile window
        duration_secs = until_ts - from_ts
        if duration_secs <= 0:
            duration_secs = 60  # Default 1 minute if invalid
        
        params = {
            "name": app_with_labels,
            "from": str(from_ts),
            "until": str(until_ts),
            "format": "folded",
            "sampleRate": "100",
            # Use 'yappi' as spy name - this is what we're actually using
            # NOT 'pyspy' which is a different profiler (py-spy)
            "spyName": "yappi",
            "units": units,
            "aggregationType": "sum",
        }
        
        # Build URL with properly encoded query params
        import urllib.parse
        query_string = urllib.parse.urlencode(params)
        url = f"{self._endpoint}/ingest?{query_string}"
        
        # Profile data as newline-separated collapsed stacks
        data = "\n".join(collapsed_lines).encode("utf-8")
        
        profile_desc = f"{profile_type} ({len(collapsed_lines)} stacks)"
        Console.info(f"[PROFILE] Pushing {profile_desc} to Pyroscope...")
        
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "text/plain"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    Console.ok(f"{profile_type} profile pushed successfully", component="PROFILE")
        except urllib.error.HTTPError as e:
            if e.code != 200:
                try:
                    body = e.read().decode('utf-8', errors='ignore')
                    Console.warn(f"Pyroscope push failed: {e.code} - {body[:200]}", component="PROFILE", profile_type=profile_type, endpoint=self._endpoint, http_status=e.code, response=body[:100])
                except Exception:
                    Console.warn(f"Pyroscope push failed: {e.code}", component="PROFILE", profile_type=profile_type, endpoint=self._endpoint, http_status=e.code)
        except Exception as e:
            Console.warn(f"Pyroscope push error: {e}", component="PROFILE", profile_type=profile_type, endpoint=self._endpoint, error_type=type(e).__name__, error=str(e)[:200])


# =============================================================================
# SQL LOG SINK
# =============================================================================

class _SqlLogSink:
    """Batched SQL log sink for ACM_RunLogs table.
    
    v11.1.6: Fixed context serialization (now JSON) and error handling.
    """
    
    def __init__(self, sql_client, run_id: str, equip_id: int, batch_size: int = 50):
        self._sql_client = sql_client
        self._run_id = run_id
        self._equip_id = equip_id
        self._batch_size = batch_size
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._written = 0
        self._failures = 0  # v11.1.6: Track insert failures
        self._last_failure_warn = 0.0  # Rate-limit warnings
        
        # Background flush thread
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._thread.start()
    
    def log(self, level: str, message: str, **context) -> None:
        """Queue a log record with trace context."""
        # Capture trace context for correlation
        trace_id = None
        span_id = None
        if OTEL_AVAILABLE and otel_trace is not None:
            try:
                current_span = otel_trace.get_current_span()
                if current_span is not None:
                    span_ctx = current_span.get_span_context()
                    if span_ctx is not None and span_ctx.is_valid:
                        trace_id = format(span_ctx.trace_id, '032x')
                        span_id = format(span_ctx.span_id, '016x')
            except Exception:
                pass
        
        record = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message[:4000],
            "context": context,
            "trace_id": trace_id,
            "span_id": span_id,
        }
        self._queue.put(record)
    
    def _flush_loop(self) -> None:
        """Background thread that flushes logs to SQL."""
        while not self._stop.is_set():
            self._flush_batch()
            time.sleep(2.0)
        self._flush_batch()  # Final flush
    
    def _flush_batch(self) -> None:
        """Flush queued logs to SQL with proper JSON serialization."""
        import json
        
        batch = []
        while len(batch) < self._batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        
        if not batch:
            return
        
        try:
            with self._sql_client.cursor() as cur:
                for record in batch:
                    # Include trace context in the context dict for correlation
                    ctx = dict(record.get("context", {}))
                    if record.get("trace_id"):
                        ctx["trace_id"] = record["trace_id"]
                    if record.get("span_id"):
                        ctx["span_id"] = record["span_id"]
                    
                    # v11.1.6: Serialize as JSON, not str() - enables proper parsing/querying
                    try:
                        ctx_json = json.dumps(ctx, ensure_ascii=False, default=str)[:4000]
                    except Exception:
                        ctx_json = "{}"
                    
                    cur.execute(
                        """INSERT INTO ACM_RunLogs 
                           (RunID, EquipID, LoggedAt, Level, Message, Context)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            self._run_id,
                            self._equip_id,
                            record["timestamp"],
                            record["level"],
                            record["message"],
                            ctx_json,
                        )
                    )
            self._written += len(batch)
        except Exception as e:
            # v11.1.6: Don't silently swallow - track failures and warn periodically
            self._failures += len(batch)
            now = time.time()
            # Rate-limit warnings to once per 30 seconds
            if now - self._last_failure_warn > 30.0:
                Console.warn(
                    f"SQL log sink: {self._failures} total failures (latest: {e})", 
                    component="LOG",
                    error_type=type(e).__name__,
                    total_failures=self._failures,
                )
                self._last_failure_warn = now
    
    def close(self) -> None:
        """Stop background thread and flush remaining logs."""
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5.0)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "init",
    "shutdown",
    "set_context",
    "get_trace_context",  # Utility to get current trace_id/span_id
    "log",
    "Console",
    "Span",
    "traced",
    "record_batch",
    "record_batch_processed",
    "record_run",
    "record_health",
    "record_health_score",
    "record_rul",
    "record_active_defects",
    "record_episode",
    "record_error",
    "record_coldstart",
    "record_sql_op",
    "record_detector_scores",
    "record_regime",
    "record_data_quality",
    "record_model_refit",
    "record_memory",
    "record_cpu",
    "record_cpu_per_core",
    "record_gpu",
    "record_capacity",
    "record_disk_io",
    "record_section_resources",
    "log_timer",
    "start_profiling",
    "stop_profiling",
    "profile_section",
    "get_tracer",
    "get_meter",
    "OTEL_AVAILABLE",
]

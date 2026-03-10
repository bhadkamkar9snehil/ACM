# ACM Observability Stack

This document describes the consolidated observability architecture for ACM v10.3.x+.

## Overview

ACM uses a modern observability stack built on open standards, deployed entirely in Docker:

| Signal | Tool | Backend | Port | Purpose |
|--------|------|---------|------|---------|
| **Traces** | OpenTelemetry SDK | Grafana Tempo | 3200 | Distributed tracing, request flow |
| **Metrics** | OpenTelemetry SDK | Prometheus | 9090 | Performance metrics, counters |
| **Logs** | structlog | Grafana Loki | 3100 | Structured JSON logs |
| **CPU Profiling** | yappi + HTTP API | Grafana Pyroscope | 4040 | CPU flamegraphs |
| **Memory Profiling** | tracemalloc + HTTP API | Grafana Pyroscope | 4040 | Memory allocation flamegraphs |
| **Image Rendering** | Grafana remote renderer | Grafana Image Renderer | internal | Dashboard/panel image export |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  ACM Python Application (Host)                                   │
│  ┌─────────────────┐ ┌─────────────────┐ ┌────────────────────┐ │
│  │ OTel SDK        │ │ structlog+Loki  │ │ yappi + HTTP       │ │
│  │ (traces+metrics)│ │ (JSON logs)     │ │ (profiling)        │ │
│  └────────┬────────┘ └────────┬────────┘ └───────┬────────────┘ │
└───────────┼───────────────────┼──────────────────┼──────────────┘
            │ OTLP HTTP         │ HTTP             │ HTTP
            │ :4318             │ :3100            │ :4040
            ▼                   ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  Docker: acm-observability network                               │
│  ┌───────────────┐ ┌──────────────┐ ┌──────────────────────────┐│
│  │ acm-alloy     │ │ acm-loki     │ │ acm-pyroscope            ││
│  │ (collector)   │ │ (logs)       │ │ (profiles)               ││
│  │ 4317,4318     │ │ 3100         │ │ 4040                     ││
│  └───────┬───────┘ └──────────────┘ └──────────────────────────┘│
│          │                                                       │
│  ┌───────▼───────┐ ┌──────────────┐                             │
│  │ acm-tempo     │ │ acm-         │                             │
│  │ (traces)      │ │ prometheus   │                             │
│  │ 3200          │ │ (metrics)    │                             │
│  └───────────────┘ │ 9090         │                             │
│                    └──────────────┘                             │
│  ┌──────────────────────────────────────────────────────────────┤
│  │ acm-grafana (dashboards)  http://localhost:3000              │
│  │ admin/admin                                                   │
│  └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start the Docker Stack
```powershell
cd install/observability
docker compose up -d
```

### 2. Verify Services
```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### 3. Access Grafana
- URL: http://localhost:3000
- Username: `admin`
- Password: `admin`
- Dashboards: ACM folder contains pre-provisioned dashboards

### 4. Run ACM
```powershell
python scripts/sql_batch_runner.py --equip WFA_TURBINE_10 --tick-minutes 1440 --max-ticks 2
```

You should see:
```
[SUCCESS] [OTEL] Loki logs -> http://localhost:3100
[SUCCESS] [OTEL] Traces -> http://localhost:4318/v1/traces
[SUCCESS] [OTEL] Metrics -> http://localhost:4318/v1/metrics
[SUCCESS] [OTEL] Profiling -> http://localhost:4040
```

## Main Dashboards

The three primary ACM dashboards now treat SQL-native ACM observability as
first-class runtime truth alongside Loki/Prometheus.

### ACM — Complete Picture

File: `acm_master_complete.json`

Use this dashboard for one equipment at a time. The operations and log sections
now show:

- recent `ACM_Runs` with `ZeroDayStatus`, `ZeroDaySurfaceType`,
  `ZeroDayChannelCount`, `DataQualityScore`, `MaxFusedZ`, and per-run SQL
  warning/error counts from `ACM_RunLogs`
- zero-day status mix for the selected equipment over the active time range
- warning/error pressure by run
- side-by-side Loki logs and SQL-native latest-run log tail

### ACM — Fleet Overview

File: `acm_fleet_overview.json`

Use this dashboard to answer fleet-level operational questions. The current
status and run sections now show:

- per-equipment current health with latest `ZeroDayStatus`, channel count, and
  24-hour SQL warning/error pressure
- richer recent run history for all equipment
- a dedicated zero-day coverage row summarizing latest HDBSCAN / online proxy /
  global fallback usage across the fleet
- fleet-wide warnings/errors by equipment

### ACM — Observability

File: `acm_observability.json`

Use this dashboard to understand pipeline behavior rather than asset condition.
It now promotes ACM-native SQL surfaces instead of relying on Loki alone:

- recent `ACM_Runs` with zero-day fields and per-run SQL warning/error counts
- top-line stats for zero-day active runs, HDBSCAN runs, SQL warnings, and SQL
  errors
- SQL write visibility for `ACM_RunLogs`, `ACM_EWMBaseline`, and
  `ACM_RegimeBinnerState`
- recent SQL run-log tail plus SQL log-volume breakdowns by component and
  equipment

Operational rule:

- use `ACM_Runs` for durable run summary and explicit zero-day state
- use `ACM_RunLogs` for ordered SQL trace, warnings, and failure context
- use Loki/Prometheus/Tempo/Pyroscope for infrastructure and cross-system
  telemetry

## Installation

### Base (Required)
```bash
pip install structlog>=24.0 colorama
```

### Full Telemetry (Recommended)
```bash
# OpenTelemetry for traces + metrics
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http

# CPU profiling (pure Python, no Rust required)
pip install yappi

# Or install everything via extras
pip install -e ".[observability]"
```

## Docker Services

| Container | Image | Ports | Purpose |
|-----------|-------|-------|---------|
| `acm-grafana` | grafana/grafana:latest | 3000 | Dashboard UI |
| `acm-alloy` | grafana/alloy:latest | 4317, 4318, 12345 | OTLP collector |
| `acm-tempo` | grafana/tempo:2.9.0 | 3200, 9095 | Trace storage |
| `acm-loki` | grafana/loki:3.3.2 | 3100 | Log aggregation |
| `acm-prometheus` | prom/prometheus:v2.54.1 | 9090 | Metrics storage |
| `acm-pyroscope` | grafana/pyroscope:1.16.0 | 4040, 4041 | Profiling |
| `acm-grafana-renderer` | grafana/grafana-image-renderer:4.0.17 | internal | Remote dashboard and panel image rendering |

Grafana image export:

- ACM now uses Grafana's supported remote renderer service rather than the deprecated in-process image renderer plugin.
- The Docker stack wires Grafana to `acm-grafana-renderer` with `GF_RENDERING_SERVER_URL`, `GF_RENDERING_CALLBACK_URL`, and a shared renderer auth token.
- If image export still fails after updating the stack, restart the observability stack with `docker compose up -d` from `install/observability`.

## Configuration Files

```
install/observability/
├── docker-compose.yaml          # Main Docker Compose file
├── config-docker.alloy          # Alloy collector config (Docker)
├── config.alloy                  # Alloy config (Windows native, deprecated)
├── tempo-docker.yaml            # Tempo configuration
├── loki-docker.yaml             # Loki configuration
├── prometheus.yaml              # Prometheus configuration
├── pyroscope-docker.yaml        # Pyroscope configuration
├── provisioning/
│   ├── datasources/
│   │   └── datasources.yaml     # Auto-provisioned datasources
│   └── dashboards/
│       └── dashboards.yaml      # Dashboard provisioning config
└── dashboards/
    ├── acm_observability.json   # Observability dashboard
    └── acm_behavior.json        # Equipment behavior dashboard
```

## Log Categories

The `acm_log` object provides category-aware logging:

| Category | Method | Purpose |
|----------|--------|---------|
| RUN | `acm_log.run()` | Pipeline lifecycle |
| CFG | `acm_log.cfg()` | Configuration |
| DATA | `acm_log.data()` | Data loading/validation |
| FEAT | `acm_log.feat()` | Feature engineering |
| MODEL | `acm_log.model()` | Model training/caching |
| SCORE | `acm_log.score()` | Scoring/detection |
| FUSE | `acm_log.fuse()` | Fusion/episodes |
| PERF | `acm_log.perf()` | Performance metrics |
| HEALTH | `acm_log.health()` | Health tracking |
| RUL | `acm_log.rul()` | RUL estimation |
| FORECAST | `acm_log.forecast()` | Forecasting |
| SQL | `acm_log.sql()` | SQL operations |

## Built-in Metrics

Use the helper functions for common ACM metrics:

```python
from core.observability import (
    record_batch_processed,
    record_detector_duration,
    record_health_score,
)

# Record batch completion
record_batch_processed(
    equipment="FD_FAN",
    duration_seconds=12.5,
    rows=1500,
    status="success"
)

# Record detector timing
record_detector_duration(
    detector="omr",
    equipment="FD_FAN", 
    duration_seconds=2.3
)

# Record health score
record_health_score(equipment="FD_FAN", score=87.5)
```

## Log Cleanup

Clean up old logs from SQL:

```python
from core.observability import cleanup_old_logs
from core.sql_client import SQLClient

sql = SQLClient.from_config()
deleted = cleanup_old_logs(sql, retention_days=30)
print(f"Deleted {deleted} old log records")
```

## Grafana Stack Setup (Docker)

### docker-compose.yml
```yaml
version: '3.8'
services:
  alloy:
    image: grafana/alloy:latest
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
    volumes:
      - ./config.alloy:/etc/alloy/config.alloy
    command: run /etc/alloy/config.alloy

  tempo:
    image: grafana/tempo:latest
    ports:
      - "3200:3200"

  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"

  pyroscope:
    image: grafana/pyroscope:latest
    ports:
      - "4040:4040"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
```

### config.alloy (Grafana Alloy)
```hcl
// Receive OTLP from Python apps
otelcol.receiver.otlp "default" {
  grpc { endpoint = "0.0.0.0:4317" }
  http { endpoint = "0.0.0.0:4318" }

  output {
    traces  = [otelcol.processor.batch.default.input]
    metrics = [otelcol.processor.batch.default.input]
  }
}

otelcol.processor.batch "default" {
  output {
    traces  = [otelcol.exporter.otlp.tempo.input]
    metrics = [otelcol.exporter.prometheus.mimir.input]
  }
}

otelcol.exporter.otlp "tempo" {
  client { endpoint = "tempo:4317" }
}

otelcol.exporter.prometheus "mimir" {
  forward_to = [prometheus.remote_write.default.receiver]
}

prometheus.remote_write "default" {
  endpoint {
    url = "http://mimir:9009/api/v1/push"
  }
}
```

## Migration from Old Logging

### Before (Multiple Files)
```python
# Old way - multiple imports
from utils.logger import Console
from utils.acm_logger import ACMLog
from core.sql_logger_v2 import BatchedSqlLogSink

Console.info("message")
ACMLog.run("message")
```

### After (Consolidated)
```python
# New way - single module
from core.observability import init_observability, get_logger, acm_log

init_observability(sql_client=sql, run_id=run_id)

log = get_logger()
log.info("message")

acm_log.run("message")  # Same API, uses structlog under the hood
```

## File Consolidation

| Old File | Status | Replacement |
|----------|--------|-------------|
| `utils/logger.py` | Keep (base) | Still used internally |
| `utils/acm_logger.py` | Deprecated | `core/observability.ACMLogger` |
| `core/sql_logger.py` | **Delete** | `core/sql_logger_v2.py` |
| `core/sql_logger_v2.py` | Keep | SQL sink for logs |
| `core/resource_monitor.py` | Keep | Complements Pyroscope |

## Performance Considerations

1. **Sampling**: In production, set `OTEL_TRACES_SAMPLER_ARG=0.1` (10% sampling)
2. **Batch Export**: Uses `BatchSpanProcessor` by default (non-blocking)
3. **Metrics Interval**: Exports every 60s by default
4. **Profiling Rate**: Pyroscope samples at 100Hz by default

---

## Log Message Sequence (Pipeline Flow)

This section documents the sequence of log messages emitted during a typical ACM batch run, from startup to completion. Understanding this flow is essential for:
- Debugging pipeline issues
- Optimizing log verbosity
- Building Loki queries and alerts

### Console Method Reference

| Method | Loki | Purpose | Use Case |
|--------|------|---------|----------|
| `Console.info()` | ✅ Yes | Standard operational info | Data loaded, config applied |
| `Console.warn()` | ✅ Yes | Unexpected but non-fatal | Missing optional data |
| `Console.error()` | ✅ Yes | Failures | SQL errors, exceptions |
| `Console.ok()` | ✅ Yes | Success milestones | Batch complete, models saved |
| `Console.status()` | ❌ No | Progress/decorative | Section banners, separators |
| `Console.header()` | ❌ No | Major section headers | Pipeline phase start |
| `Console.section()` | ❌ No | Minor section markers | Timing summaries |
| `Console.debug()` | ✅ Yes | Verbose diagnostics | Schema defaults, SQL queries |

### Log Components (Categories)

Each log has a `component` tag for filtering in Loki:

| Component | Pipeline Phase | Description |
|-----------|----------------|-------------|
| `OTEL` | Startup | Observability stack initialization |
| `CFG` | Startup | Configuration loading and validation |
| `RUN` | Startup | Run lifecycle (start, end, RunID) |
| `SQL` | Startup | SQL connection and health checks |
| `OUTPUT` | Startup | OutputManager initialization |
| `DATA` | Load | Data loading from SQL historian |
| `COLDSTART` | Load | Coldstart detection and data splitting |
| `BASELINE` | Load | Baseline buffer management |
| `FEAT` | Features | Feature engineering (rolling windows) |
| `HASH` | Features | Feature hash computation for caching |
| `MODEL` | Fit | Model loading, fitting, caching |
| `AR1` | Fit/Score | AR1 detector status |
| `PCA` | Fit/Score | PCA detector status |
| `IFOREST` | Fit/Score | Isolation Forest status |
| `GMM` | Fit/Score | Gaussian Mixture Model status |
| `OMR` | Fit/Score | Overall Model Residual detector |
| `REGIME` | Regimes | Regime clustering and labeling |
| `REGIME_STATE` | Regimes | Regime state persistence |
| `CAL` | Calibration | Detector calibration and thresholds |
| `FUSE` | Fusion | Score fusion and episode detection |
| `THRESHOLD` | Thresholds | Adaptive threshold calculation |
| `TUNE` | Tuning | Detector weight auto-tuning |
| `DRIFT` | Drift | Concept drift monitoring |
| `ADAPTIVE` | Adaptive | Model health and parameter tuning |
| `ANALYTICS` | Output | Comprehensive analytics generation |
| `FORECAST` | Output | RUL/health forecasting |
| `PERF` | Output | Performance timing and metrics |
| `RUN_META` | Finalize | Run metadata persistence |
| `CULPRITS` | Finalize | Episode culprit analysis |

### Log Labels (Loki)

Each log pushed to Loki includes structured labels for filtering and correlation:

| Label | Description | Example |
|-------|-------------|---------|
| `app` | Application identifier | `acm` |
| `level` | Log level | `INFO`, `WARN`, `ERROR` |
| `component` | Pipeline component (see table above) | `FORECAST`, `DATA` |
| `equipment` | Equipment code being processed | `FD_FAN` |
| `equip_id` | Equipment database ID | `1` |
| `run_id` | Current run identifier | `abc123-def456` |
| `trace_id` | Active OpenTelemetry trace ID (32-char hex) | `a1b2c3d4e5f6...` |
| `span_id` | Active OpenTelemetry span ID (16-char hex) | `1234567890abcdef` |

### Logs-to-Traces Correlation

The `trace_id` and `span_id` labels enable seamless navigation between logs and traces in Grafana:

1. **From Logs to Traces**: In Grafana Loki Explore, click on a log line's `trace_id` label to jump directly to the corresponding trace in Tempo.

2. **From Traces to Logs**: In Grafana Tempo, view related logs by clicking "Logs for this span" (requires Loki derived field configuration).

3. **Cross-Process Tracing**: When ACM runs in batch mode via `sql_batch_runner.py`, trace context is propagated to subprocess runs via environment variables (`TRACEPARENT_TRACE_ID`, `TRACEPARENT_SPAN_ID`), enabling end-to-end trace correlation across the parent orchestrator and child equipment runs.

**Grafana Loki Derived Field Configuration (for trace link):**

In your Loki datasource settings, add a derived field:
- **Name**: `TraceID`  
- **Regex**: `"trace_id":"([a-f0-9]+)"`
- **Internal link**: Enable, select Tempo datasource
- **URL**: `${__value.raw}`

## Trace Coloring via Virtual Services (v10.3.0)

ACM spans are automatically color-coded in Grafana Tempo based on their **phase** (high-level pipeline stage). This provides immediate visual feedback about which part of the pipeline is executing and helps identify bottlenecks.

### How It Works

Each ACM span is tagged with:
1. **Resource service**: Always `acm-pipeline` (for correlation across logs/metrics/profiles)
2. **Virtual service attribute**: `acm-{phase}` (for Tempo coloring)
3. **Phase attribute**: The phase group (startup, features, fit, score, fusion, etc.)

Tempo automatically colors spans by the **service.name** attribute, so each phase appears in a distinct color on the trace timeline and service map.

### Virtual Services & Colors

| Virtual Service | Phase | Color | Example Spans | Purpose |
|-----------------|-------|-------|---------------|---------|
| **acm-startup** | startup | 🟣 Purple | `startup.load_data`, `startup.config` | Init, config loading, SQL connection |
| **acm-features** | features | 🟠 Orange | `features.build_features`, `features.normalize` | Feature engineering, data prep |
| **acm-fit** | fit | 🟢 Green | `fit.ar1`, `fit.pca`, `fit.iforest` | Model training and fitting |
| **acm-score** | score | 🟢 Green | `score.ar1`, `score.regimes`, `score.calibrate` | Model inference and scoring |
| **acm-fusion** | fusion | 🟡 Yellow | `fusion.thresholds`, `fusion.episodes` | Detector fusion, threshold calc |
| **acm-monitoring** | monitoring | 🟢 Green | `monitoring.drift`, `monitoring.adaptive` | Drift detection, adaptive tuning |
| **acm-forecast** | forecast | 🟠 Orange | `forecast.run`, `forecast.rul.simulate`, `forecast.rul.quantiles` | RUL estimation, health forecasting |
| **acm-analytics** | analytics | 🟠 Orange | `analytics.comprehensive`, `analytics.outputs` | Analytics generation, reporting |
| **acm-persist** | persist | 🔵 Blue | `persist.write`, `persist.save_model`, `persist.load_model` | SQL writes, model persistence |
| **acm-finalize** | finalize | 🟣 Purple | `finalize.cleanup`, `finalize.shutdown` | Cleanup and shutdown |

### Span Naming Convention

All ACM spans follow the pattern: `{phase}.{component}.{operation?}`

Examples:
- `startup.load_data` - Loading data during startup
- `fit.pca` - Fitting PCA detector (component = pca, no operation)
- `persist.write` - Generic write operation
- `sql.execute` - SQL execute operation
- `forecast.rul.simulate` - Monte Carlo simulation sub-operation

### Why Virtual Services?

- **Single Resource Service**: `acm-pipeline` remains the canonical service name for logs, metrics, profiles, and cross-tool correlation
- **Multi-Color Traces**: Virtual services enable per-phase coloring without breaking the unified service identity
- **Automatic Coloring**: No dashboard changes needed—Tempo auto-colors based on span attributes

### Viewing Colored Traces in Grafana

1. **Service Map**: Visit Grafana → Tempo → Service Map. You'll see `acm-pipeline` with colored nodes representing each phase encountered in recent traces.

2. **Trace Search**: Use TraceQL to search by virtual service:
   ```traceql
   { service.name =~ "acm-.*" }  # All ACM spans
   { service.name = "acm-forecast" }  # Only forecasting spans
   ```

3. **Timeline View**: In a trace detail view, each span shows its color based on its phase. Green spans (fit, score) are typically fast; orange spans (features, forecast, analytics) are longer. Blue spans (persist) indicate I/O operations.

### Message Sequence: Batch Run (Coldstart)

**Phase 1: Initialization**
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
1    OTEL       OK      Loki logs -> http://localhost:3100
2    OTEL       OK      Traces -> http://localhost:4318/v1/traces
3    OTEL       OK      Metrics -> http://localhost:4318/v1/metrics
4    CFG        INFO    Loaded config from SQL for {equipment} (EquipID={id})
5    CFG        INFO    Config deep-copied to prevent accidental mutations
6    CFG        INFO    Config signature: {hash}
7    RUN        INFO    Batch {n}/{total} | Equipment: {name}
8    CFG        INFO    storage_backend=SQL_ONLY | batch_mode=True | continuous_learning=True
9    CFG        INFO    model_update_interval={n} | threshold_update_interval={n}
10   RUN        INFO    SQL-only mode: run_{timestamp}
11   RUN        INFO    Using equipment from CLI argument: {name}
12   RUN        INFO    Starting run RunID={uuid} (tick={minutes})
13   RUN        INFO    Started RunID={uuid} window=[{start},{end}) equip='{code}' EquipID={id}
14   OUTPUT     INFO    Manager initialized (batch_size=5000, batching=ON, ...)
15   OUTPUT     INFO    Diagnostic: SQL client attached and health check passed
```

**Phase 2: Data Loading (Coldstart Path)**
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
16   COLDSTART  INFO    Detected data cadence: {n} seconds ({m} minutes)
17   COLDSTART  INFO    No existing models for {equipment} - coldstart required
18   DATA       INFO    Loading from SQL historian: {equipment}
19   DATA       INFO    Time range: {start} to {end}
20   DATA       INFO    Retrieved {n} rows from SQL historian
21   DATA       INFO    BATCH MODE: Train allocated {n} rows, Score allocated {m} rows
22   DATA       INFO    Kept {n} numeric columns, dropped {m} non-numeric
23   DATA       INFO    SQL historian load complete: {n} train + {m} score = {total} rows
24   DATA       INFO    Index integrity verified: BASELINE={n} unique, BATCH={m} unique
25   DATA       INFO    timestamp={col} cadence_ok=True kept={n} drop={m} ...
```

**Phase 3: Data Quality & Features**
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
26   BASELINE   INFO    Using adaptive baseline for TRAIN: {strategy}
27   FEAT       INFO    Building features with window={n} (fast_features)
28   FEAT       INFO    Computed {n} fill values from training data (prevents leakage)
29   FEAT       INFO    Using Polars for feature computation ({n} rows > {threshold})
30   FEAT       INFO    Building train features...
31   FEAT       INFO    Building score features (using train fill values)...
32   FEAT       INFO    Imputing non-finite values in features using train medians
33   HASH       INFO    Stable hash computed: {hash} (shape={rows}x{cols})
```

**Phase 4: Model Fitting**
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
34   MODEL      INFO    Continuous learning enabled - models will retrain on accumulated data
35   MODEL      INFO    Starting detector fitting...
36   MODEL      INFO    Fitting AR1 detector...
37   AR1        INFO    Detector fitted
38   MODEL      INFO    Fitting PCA detector...
39   PCA        INFO    Fit start: train shape=({rows}, {cols})
40   PCA        INFO    Fit complete in {t}s
41   PCA        INFO    Subspace detector fitted with {n} components
42   PCA        INFO    Cached train scores: SPE={n} samples, T²={m} samples
43   MODEL      INFO    Fitting IForest detector...
44   IFOREST    INFO    Detector fitted
45   MODEL      INFO    Fitting GMM detector (may take time with large data)...
46   GMM        INFO    BIC search selected k={n}
47   GMM        INFO    Fitted k={n}, cov=diag, reg=0.001
48   GMM        INFO    Detector fitted
49   MODEL      INFO    Fitting OMR detector...
50   OMR        INFO    Selected model type: {PLS|OLS}
51   OMR        INFO    Fitted {type} model: {n} samples, {m} features, {k} components
52   OMR        INFO    Diagnostics written: {type} model
53   OMR        INFO    Detector fitted
54   MODEL      INFO    All detectors fitted in {t}s
```

**Phase 5: Model Scoring**
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
55   ADAPTIVE   INFO    Checking model health...
56   ADAPTIVE   INFO    All model parameters within healthy ranges
57   REGIME     INFO    v10.1.0: Using {n} raw operational sensors for regime clustering: [...]
58   MODEL      INFO    Starting detector scoring...
59   AR1        INFO    Detector scored
60   PCA        INFO    Detector scored
61   IFOREST    INFO    Detector scored
62   GMM        INFO    Detector scored
63   OMR        INFO    Detector scored
64   MODEL      INFO    All detectors scored in {t}s
65   REGIME     INFO    Auto-k selection complete: k={n}, metric=silhouette, score={x}
66   REGIME_STATE INFO  Saved state v{n}: K={k}, quality_ok={bool}
```

**Phase 6: Model Persistence**
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
67   MODEL      INFO    Saving models to SQL ModelRegistry v{n}
68   MODEL-SQL  INFO    - Saved ar1_params ({n} bytes)
69   MODEL-SQL  INFO    - Saved pca_model ({n} bytes)
70   MODEL-SQL  INFO    - Saved iforest_model ({n} bytes)
71   MODEL-SQL  INFO    - Saved gmm_model ({n} bytes)
72   MODEL-SQL  INFO    - Saved omr_model ({n} bytes)
73   MODEL-SQL  INFO    - Saved feature_medians ({n} bytes)
74   MODEL-SQL  INFO    OK Committed {n}/{total} models to SQL ModelRegistry v{version}
75   MODEL      INFO    Saved all trained models to version v{n}
```

**Phase 7: Calibration & Fusion**
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
76   CAL        INFO    Scoring TRAIN data for calibration baseline...
77   CAL        INFO    Using cached PCA train scores (optimization)
78   CAL        INFO    Self-tuning enabled. Target FP rate {x}% -> q={q}, threshold={t}
79   CAL        INFO    Adaptive clip_z={z} (TRAIN P99 max={x})
80   CAL        INFO    Wrote thresholds table with {n} rows -> acm_thresholds
81   FUSE       INFO    Starting detector weight auto-tuning...
82   FUSE       INFO    Auto-tuned CUSUM parameters: k_sigma={k}, h_sigma={h}
83   TUNE       INFO    Detector weight auto-tuning (episode_separability): ...
84   TUNE       INFO    Using auto-tuned weights for final fusion
85   TUNE       INFO    Saved fusion metrics -> SQL:ACM_RunMetrics ({n} records)
86   FUSE       INFO    Computing final fusion and detecting episodes...
87   FUSE       INFO    Detected {n} anomaly episodes
```

**Phase 8: Threshold & Regime Labeling**
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
88   THRESHOLD  INFO    First threshold calculation after coldstart
89   THRESHOLD  INFO    Calculating thresholds on accumulated data (train + score)
90   THRESHOLD  INFO    Calculating adaptive thresholds from {n} samples...
91   THRESHOLD  INFO    Persisting to SQL: equip_id={id} | samples={n} | method={m}
92   THRESHOLD  INFO    Global thresholds: alert={a}, warn={w} (method={m}, conf={c})
93   REGIME     INFO    Starting regime health labeling and transient detection...
94   TRANSIENT  INFO    State distribution: {'steady': {n}}
95   DRIFT      INFO    Multi-feature: cusum_z P95={z}, trend={t}, fused_P95={f}
```

**Phase 9: Analytics Output**
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
96   OUTPUT     INFO    SQL insert to ACM_Scores_Wide: {n} rows
97   ANALYTICS  INFO    Generating comprehensive analytics tables...
98   OUTPUT     INFO    Starting batched transaction
99   OUTPUT     INFO    SQL insert to ACM_HealthTimeline: {n} rows
100  OUTPUT     INFO    SQL insert to ACM_RegimeTimeline: {n} rows
101  OUTPUT     INFO    SQL insert to ACM_OMRTimeline: {n} rows
102  OUTPUT     INFO    SQL insert to ACM_ContributionTimeline: {n} rows
103  OUTPUT     INFO    SQL insert to ACM_DriftSeries: {n} rows
104  OUTPUT     INFO    SQL insert to ACM_SensorNormalized_TS: {n} rows
... (more tables)
105  ANALYTICS  INFO    Generated {n} comprehensive analytics tables
106  ANALYTICS  INFO    Written {n} tables to SQL database
107  OUTPUT     INFO    Batched transaction committed ({t}s)
108  ANALYTICS  INFO    Successfully generated all comprehensive analytics tables
```

**Phase 10: Forecasting**
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
109  FORECAST   INFO    Running unified forecasting engine (v10.0.0)
110  HealthTracker INFO Data anchor: {date}, window cutoff: {date} ({n}h lookback)
111  HealthTracker INFO Loaded {n} health points from SQL (rolling window: {h}h)
112  ForecastEngine INFO Data summary: n_samples={n}, dt_hours={h}, window={w}h
113  StateManager INFO  No previous state for EquipID={id}; starting fresh
114  ForecastEngine INFO Loaded config: alpha={a}, beta={b}, failure_threshold={t}
115  DegradationModel INFO Detected {n} outliers (z > 3.0)
116  DegradationModel INFO Adaptive smoothing: alpha={a}, beta={b}
117  DegradationModel INFO Fitted: level={l}, trend={t}/hr, std_error={e}, n={n}
118  RULEstimator INFO  RUL estimate: P50={h}h, P10={l}h, P90={u}h, mean={m}h
119  ForecastDiag INFO  RUL_P50={h}h, RUL_Spread={s}h, Health={h}, Quality={q}
120  OUTPUT     INFO    SQL insert to ACM_HealthForecast: {n} rows
121  OUTPUT     INFO    SQL insert to ACM_FailureForecast: {n} rows
122  OUTPUT     INFO    SQL insert to ACM_RUL: 1 rows
123  ForecastEngine INFO Wrote 3 forecast tables to SQL
124  StateManager INFO  Saved state for EquipID={id}
125  FORECAST   INFO    RUL P50={h}h, P10={l}h, P90={u}h
126  FORECAST   INFO    Top sensors: {sensor1} ({pct}%), {sensor2} ({pct}%), ...
127  FORECAST   INFO    Wrote tables: ACM_HealthForecast, ACM_FailureForecast, ACM_RUL
```

**Phase 11: Final SQL Writes**
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
128  SQL        INFO    Starting batched artifact writes...
129  OUTPUT     INFO    SQL insert to ACM_Scores_Long: {n} rows
130  OUTPUT     INFO    SQL insert to ACM_Anomaly_Events: {n} rows
131  OUTPUT     INFO    SQL insert to ACM_Regime_Episodes: {n} rows
132  OUTPUT     INFO    SQL insert to ACM_PCA_Models: 1 rows
133  OUTPUT     INFO    SQL insert to ACM_PCA_Loadings: {n} rows
134  OUTPUT     INFO    SQL insert to ACM_Run_Stats: 1 rows
135  CULPRITS   INFO    Wrote {n} enhanced culprit records to ACM_EpisodeCulprits
136  CULPRITS   INFO    Successfully wrote episode culprits for RunID={uuid}
```

**Phase 12: Finalization**
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
137  PERF       DEBUG   Wrote {n} timer records to ACM_RunTimers
138  RUN_META   DEBUG   Data quality from SQL: avg_null={x}%, score={s}
139  RUN_META   INFO    Wrote run metadata to ACM_Runs: {uuid}
140  RUN_META   INFO    Wrote run metadata to ACM_Runs for RunID={uuid} (outcome=OK)
141  RUN        INFO    Finalized RunID={uuid} outcome=OK rows_in={n} rows_out={m}
142  OUTPUT     INFO    Finalized: {n} files, {m} SQL ops, {k} total rows, {t}s avg write
```

### Message Sequence: NOOP Run

When no data is available for processing, the sequence is much shorter:
```
Seq  Component  Level   Message Pattern
---  ---------  ------  ---------------
1-15 (same initialization as above)
16   COLDSTART  INFO    Detected data cadence: {n} seconds ({m} minutes)
17   COLDSTART  INFO    Models exist for {equipment}, coldstart not needed
18   DATA       INFO    Loading from SQL historian: {equipment}
19   DATA       INFO    Time range: {start} to {end}
20   DATA       ERROR   Failed to load from SQL historian: [DATA] No data returned
21   COLDSTART  ERROR   Failed to load data window: [DATA] No data returned
22   COLDSTART  WARN    Insufficient data in {h}h window - batch will NOOP
23   COLDSTART  INFO    Deferred to next job run - insufficient data for training
24   COLDSTART  INFO    Job will retry automatically when more data arrives
25   PERF       DEBUG   Wrote 2 timer records to ACM_RunTimers
26   RUN_META   INFO    Wrote run metadata to ACM_Runs for RunID={uuid} (outcome=NOOP)
27   RUN        INFO    Finalized RunID={uuid} outcome=NOOP rows_in=0 rows_out=0
28   OUTPUT     INFO    Finalized: 0 files, 0 SQL ops, 0 total rows, 0.000s avg write
```

### SQL Observability Surfaces

Current runtime uses two SQL observability surfaces with different roles:

- `ACM_RunLogs`: detailed ordered trace from the live `Console` SQL sink
- `ACM_Runs`: durable per-run summary, outcome, and explicit zero-day status

As of `v11.17.2-v11.17.3`, the `ACM_RunLogs` sink is active again through the batched
SQL writer in `core.observability.py`. Operators should use:

- `ACM_RunLogs` to inspect sequencing, warnings, and failure traces
- `ACM_Runs` to inspect run outcome and day-0 summary fields such as `ZeroDayStatus`

### Loki Query Examples

**Find all errors in last 24 hours:**
```logql
{app="acm"} |= "ERROR" | json | line_format "{{.message}}"
```

**Track specific equipment runs:**
```logql
{app="acm", equipment="FD_FAN"} | json | component="RUN"
```

**Monitor forecasting issues:**
```logql
{app="acm"} | json | component=~"FORECAST|RUL|HealthTracker"
```

**Find model retraining events:**
```logql
{app="acm"} |= "refit" or |= "retrain" | json
```

**Count runs by outcome:**
```logql
count_over_time({app="acm"} |= "outcome=" | json [24h])
```

---

## Profiling with yappi + tracemalloc + Pyroscope

ACM uses **yappi** (pure Python) for CPU profiling and **tracemalloc** (Python stdlib) for memory profiling, pushing profiles to Pyroscope via HTTP API. This avoids the Rust compilation requirements of `pyroscope-io`.

### Profile Types

| Type | Tool | Description | Pyroscope Label |
|------|------|-------------|-----------------|
| **CPU** | yappi | CPU time spent in functions | `acm.cpu` |
| **Memory Alloc (objects)** | tracemalloc | Number of allocations | `acm.alloc_objects` |
| **Memory Alloc (bytes)** | tracemalloc | Bytes allocated | `acm.alloc_space` |

### Profile Labels (for Correlation)

Profiles are tagged with consistent labels for correlation with traces, logs, and metrics:

| Label | Description | Example |
|-------|-------------|---------|
| `service_name` | Standard Grafana service name | `acm-pipeline` |
| `equipment` | Equipment being processed | `FD_FAN` |
| `equip_id` | Equipment database ID | `1` |
| `run_id` | Current run identifier | `abc-123` |
| `trace_id` | Active trace ID (when in span) | `1234...` |
| `span_id` | Active span ID (when in span) | `5678...` |

### How It Works

1. **yappi** samples the Python call stack for CPU time
2. **tracemalloc** tracks memory allocations (when available)
3. Profiles are labeled with trace context for correlation
4. On shutdown, samples are converted to "collapsed/folded" format
5. Profiles are pushed to Pyroscope's HTTP `/ingest` endpoint
6. View flamegraphs in Grafana (Pyroscope data source)

### Automatic Profiling (Recommended)

When `init()` is called with a reachable Pyroscope endpoint, profiling starts automatically:

```python
from core.observability import init, shutdown

# Profiling starts automatically if yappi is installed
init(equipment="FD_FAN", equip_id=1)

# ... your code runs here ...

# Profiling stops and pushes to Pyroscope on shutdown
shutdown()
```

### Manual Profiling (Specific Sections)

For profiling specific code sections:

```python
from core.observability import start_profiling, stop_profiling

# Profile a specific section
start_profiling()

# ... code to profile ...

# Stop and push to Pyroscope
stop_profiling()
```

### Context Manager for Scoped Profiling

```python
from core.observability import profile_section

with profile_section("heavy_computation"):
    # This code block will be profiled
    heavy_computation()
```

### Trace-to-Profile Correlation

Profiles taken during an active span are automatically labeled with the trace context:

```python
from core.observability import Span

with Span("fit.models"):  # trace_id and span_id are captured
    # CPU and memory profiles during this span will have
    # trace_id and span_id labels for correlation
    train_models()
```

In Grafana Tempo, clicking on a span provides a "Profiles" link to view the
CPU/memory profile for that exact time range.

### Viewing Profiles in Grafana

1. Open Grafana at http://localhost:3000
2. Go to **Explore** → Select **Pyroscope** data source
3. Select profile type:
   - CPU: `process_cpu:cpu:nanoseconds:cpu:nanoseconds`
   - Memory (objects): `memory:alloc_objects:count:space:bytes`
   - Memory (bytes): `memory:alloc_space:bytes:space:bytes`
4. Filter by labels:
   - `service_name = acm-pipeline`
   - `equipment = FD_FAN`
5. View flamegraph to identify CPU/memory hotspots

### Pyroscope Query Examples

```promql
# CPU profile for specific equipment
{service_name="acm-pipeline", equipment="FD_FAN"}

# Memory profile for all equipment
{service_name="acm-pipeline"}

# Profile correlated with a specific trace
{service_name="acm-pipeline", trace_id="abc123..."}
```

---

## Troubleshooting

### OpenTelemetry not sending data
```bash
# Check OTLP endpoint is reachable
curl -v http://localhost:4318/v1/traces

# Enable debug logging
export OTEL_LOG_LEVEL=debug
```

### structlog not producing JSON
```bash
# Force JSON format
export ACM_LOG_FORMAT=json
```

### Profiling not working

**Check yappi is installed:**
```python
import yappi
print(f"yappi version: {yappi.__version__}")
```

**Verify Pyroscope endpoint:**
```powershell
# Check Pyroscope is running
curl http://localhost:4040/ready

# Expected: "ready"
```

**Check for profiling success in logs:**
```
[SUCCESS] [OTEL] Profiling -> http://localhost:4040
```

**Manual test:**
```python
from core.observability import start_profiling, stop_profiling

start_profiling(equipment="TEST", equip_id=999)
import time
time.sleep(1)  # Some work
stop_profiling()
# Check Pyroscope UI for "acm" app with equipment=TEST label
```

**Time zone issues (Windows + Docker):**
If profiles don't appear, check `pyroscope-docker.yaml` has extended limits:
```yaml
limits:
  reject_older_than: 720h  # Handle time drift between host and Docker
```

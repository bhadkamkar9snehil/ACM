# ACM Observability Stack - Installation Guide

## Overview

This directory contains configuration files for the complete Grafana observability stack running in Docker.

| Component | Container | Port | Purpose |
|-----------|-----------|------|---------|
| **Grafana** | acm-grafana | 3000 | Dashboard UI (admin/admin) |
| **Alloy** | acm-alloy | 4317, 4318 | OTLP collector/router |
| **Tempo** | acm-tempo | 3200 | Distributed tracing |
| **Loki** | acm-loki | 3100 | Log aggregation |
| **Prometheus** | acm-prometheus | 9090 | Metrics storage |
| **Pyroscope** | acm-pyroscope | 4040 | Continuous profiling |
| **Image Renderer** | acm-grafana-renderer | internal only | Dashboard and panel image export |

## Quick Start

### Prerequisites

- **Docker Desktop** for Windows (https://www.docker.com/products/docker-desktop/)

### Step 1: Start the Stack

```powershell
cd C:\Users\bhadk\Documents\ACM V8 SQL\ACM\install\observability
docker compose up -d
```

### Step 2: Verify Services

```powershell
# Check all containers are healthy
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected output:
```
NAMES            STATUS           PORTS
acm-grafana      Up (healthy)     0.0.0.0:3000->3000/tcp
acm-alloy        Up (healthy)     0.0.0.0:4317-4318->4317-4318/tcp
acm-prometheus   Up (healthy)     0.0.0.0:9090->9090/tcp
acm-loki         Up (healthy)     0.0.0.0:3100->3100/tcp
acm-pyroscope    Up (healthy)     0.0.0.0:4040->4040/tcp
acm-tempo        Up (healthy)     0.0.0.0:3200->3200/tcp
acm-grafana-renderer Up          8081/tcp
```

### Step 3: Access Grafana

- **URL**: http://localhost:3000
- **Username**: `admin`
- **Password**: `admin`

Datasources are auto-provisioned via `provisioning/datasources/datasources.yaml`:
- **Prometheus** (prometheus-ds) - Metrics storage
- **Tempo** (tempo-ds) - Distributed tracing
- **Loki** (loki-ds) - Log aggregation
- **Pyroscope** (pyroscope-ds) - Continuous profiling
- **MSSQL** (mssql-ds) - SQL Server for ACM business data

Grafana image export:
- Dashboard and panel image export now uses the supported remote renderer service.
- If Grafana still shows "Image renderer plugin not installed", restart the stack with `docker compose up -d`.
- The renderer is internal to the Docker network; no extra host port is required.

## Dashboard Folder Structure & Tagging Philosophy

### Folder Organization

| Folder | UID | Purpose |
|--------|-----|---------|
| **ACM Observability** | `acm-observability-folder` | System monitoring: traces, logs, metrics, profiling |
| **ACM Business** | `acm-business-folder` | Equipment health, anomalies, RUL (SQL data) |

### Tagging Convention

Tags help categorize dashboards for filtering and discovery:

| Tag | Meaning |
|-----|---------|
| `acm` | All ACM-related dashboards |
| `observability` | System/pipeline monitoring |
| `business` | Equipment health & analytics |
| `prometheus` | Uses Prometheus metrics |
| `loki` | Uses Loki logs |
| `tempo` | Uses Tempo traces |
| `pyroscope` | Uses profiling data |
| `mssql` | Uses SQL Server data |

### Current Dashboards

| Dashboard | Folder | Tags | Purpose |
|-----------|--------|------|---------|
| ACM Observability | ACM Observability | acm, observability, prometheus, loki, tempo, pyroscope | Pipeline execution monitoring, resource usage, logs, traces |

### Importing Additional Dashboards

To import a dashboard from `grafana_dashboards/`:

```powershell
# Read dashboard JSON and prepare for import
$dashboard = Get-Content -Raw "grafana_dashboards/my_dashboard.json" | ConvertFrom-Json
$dashboard.id = $null  # Clear ID for new import
$dashboard.uid = "my-dashboard"  # Set unique UID
$dashboard.tags = @("acm", "business", "mssql")  # Set tags

# Create import payload
$payload = @{
    dashboard = $dashboard
    folderUid = "acm-business-folder"  # Target folder
    overwrite = $true
    message = "Imported from grafana_dashboards"
} | ConvertTo-Json -Depth 50

# Write without BOM (critical for curl)
[System.IO.File]::WriteAllText("import.json", $payload, [System.Text.UTF8Encoding]::new($false))

# Import via API
docker cp import.json acm-grafana:/tmp/import.json
docker exec acm-grafana curl -s -X POST -H 'Content-Type: application/json' \
  -u admin:admin -d @/tmp/import.json http://localhost:3000/api/dashboards/db
```

### Step 4: Configure SQL Server Connection

ACM dashboards (except Observability) require SQL Server connectivity for business data.

**Option A: Create SQL Login (Recommended)**

Run in SQL Server Management Studio (SSMS):
```sql
USE master;
CREATE LOGIN grafana_reader WITH PASSWORD = 'YourSecurePassword123!';
USE ACM;
CREATE USER grafana_reader FOR LOGIN grafana_reader;
ALTER ROLE db_datareader ADD MEMBER grafana_reader;
```

Then configure in Grafana:
```powershell
# From ACM project root
.\scripts\configure_grafana_mssql.ps1 -User "grafana_reader" -Password "YourSecurePassword123!"
```

**Option B: Configure Manually via Grafana UI**

1. Open http://localhost:3000/connections/datasources/mssql-ds
2. Update connection settings:
   - **Host**: `host.docker.internal:1433`
   - **Database**: `ACM`
   - **Authentication**: `SQL Server Authentication`
   - **User**: `grafana_reader`
   - **Password**: (your password)
   - **Encrypt**: `disable` (for local development)
3. Click **Save & Test**

### Step 5: Test with ACM

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

## Managing the Stack

```powershell
# Stop the stack
docker compose down

# View logs for a specific service
docker logs acm-alloy --tail 50
docker logs acm-tempo --tail 50

# Restart a service
docker compose restart alloy

# Remove all data (clean start)
docker compose down -v

# Rebuild and restart
docker compose down; docker compose up -d
```

## File Structure

```
install/observability/
├── docker-compose.yaml          # Main Docker Compose file
├── config-docker.alloy          # Alloy config for Docker networking
├── tempo-docker.yaml            # Tempo configuration
├── loki-docker.yaml             # Loki configuration
├── prometheus.yaml              # Prometheus configuration
├── pyroscope-docker.yaml        # Pyroscope configuration
├── provisioning/
│   └── datasources/
│       └── datasources.yaml     # Auto-provisioned Grafana datasources
└── README.md                    # This file

# Dashboards are stored in project root, NOT auto-provisioned:
grafana_dashboards/
├── acm_observability.json       # Pipeline monitoring (observability stack)
├── acm_behavior.json            # Equipment health (SQL data)
└── ...                          # Other business dashboards
```

> **Note**: Dashboards are NOT auto-provisioned. Import them manually via Grafana UI
> or API to maintain full control over dashboard versions.

## Volumes (Persistent Data)

All data is stored in Docker volumes:

| Volume | Service | Data |
|--------|---------|------|
| grafana-data | acm-grafana | Dashboard settings, preferences |
| tempo-data | acm-tempo | Trace storage |
| loki-data | acm-loki | Log storage |
| prometheus-data | acm-prometheus | Metrics time series |
| pyroscope-data | acm-pyroscope | Profiling data |

To view volumes:
```powershell
docker volume ls | Select-String "observability"
```

## Enabling Profiling

### Install pyroscope-io

```powershell
pip install pyroscope-io
```

Note: On Windows, `pyroscope-io` may require Rust toolchain. If installation fails:
1. Install Rust from https://rustup.rs/
2. Restart terminal and try again

### Verify Profiling

Check ACM output for:
```
[SUCCESS] [OTEL] Profiling -> http://localhost:4040
```

View profiles in Grafana:
1. Go to http://localhost:3000
2. Navigate to Explore → Pyroscope
3. Select `acm-pipeline` from application dropdown

## Troubleshooting

### Port Conflicts

If ports are already in use:
```powershell
netstat -an | Select-String ":4318"
```

Common conflicts:
- **4317/4318**: Windows Alloy service (uninstall with `sc.exe delete Alloy` as admin)
- **3000**: Local Grafana (change to different port in `grafana.ini`)

### Pyroscope Not Receiving Data

1. Ensure `pyroscope-io` is installed:
   ```powershell
   pip install pyroscope-io
   ```

2. Check if profiling is enabled in ACM output

3. Verify Pyroscope is healthy:
   ```powershell
   Invoke-RestMethod "http://localhost:4040/ready"
   ```

### Logs Not Appearing in Grafana

1. Check Loki is receiving data:
   ```powershell
   Invoke-RestMethod "http://localhost:3100/loki/api/v1/labels"
   ```

2. Check Alloy is forwarding:
   ```powershell
   docker logs acm-alloy --tail 30
   ```

3. Verify ACM shows Loki connection:
   ```
   [SUCCESS] [OTEL] Loki logs -> http://localhost:3100
   ```

### Container Not Starting

Check container logs:
```powershell
docker logs acm-alloy
docker logs acm-grafana
```

Common issues:
- **acm-alloy**: Config syntax error in `config-docker.alloy`
- **acm-grafana**: Provisioning YAML syntax error

## Architecture

```
Python ACM (Host)
    │
    ├─── OTLP HTTP (:4318) ──────► acm-alloy ───┬──► acm-tempo (traces)
    │                                           └──► acm-prometheus (metrics)
    │
    ├─── Loki HTTP (:3100) ──────► acm-loki (logs)
    │
    └─── Pyroscope HTTP (:4040) ─► acm-pyroscope (profiles)
                                          │
                                          ▼
                                    acm-grafana (:3000)
                                    (visualization)
```

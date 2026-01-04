# ACM Installation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ACM INSTALLATION FLOW                        │
│                                                                 │
│  Prerequisites (User Installs First):                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ SQL Server   │ │ Python 3.11+ │ │ ODBC Driver  │           │
│  │ (any edition)│ │              │ │ 18 for SQL   │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                 │
│  Optional:                                                      │
│  ┌──────────────┐                                              │
│  │ Docker       │  (for observability stack)                   │
│  │ Desktop      │                                              │
│  └──────────────┘                                              │
└─────────────────────────────────────────────────────────────────┘

                            ↓ Run Installer

┌─────────────────────────────────────────────────────────────────┐
│                    INSTALLER OPTIONS                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Option 1: Interactive (Easiest)                                │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  cd install                                               │ │
│  │  .\QuickInstall.bat                                       │ │
│  │                                                           │ │
│  │  → Prompts for SQL Server connection                     │ │
│  │  → Asks about authentication method                      │ │
│  │  → Runs Install-ACM.ps1 with correct params              │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Option 2: Direct PowerShell (Advanced)                         │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  .\Install-ACM.ps1 -Server "localhost\SQLEXPRESS" `      │ │
│  │                    -TrustedConnection                     │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Option 3: Manual Installation                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  See install/README.md for step-by-step guide            │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

                            ↓ Installation Steps

┌─────────────────────────────────────────────────────────────────┐
│                    INSTALLATION WORKFLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: Prerequisites Check                                    │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Test-Prerequisites.ps1                                   │ │
│  │  ✓ Python 3.11+                                           │ │
│  │  ✓ pip                                                    │ │
│  │  ✓ ODBC Driver 18                                         │ │
│  │  ✓ Docker (optional)                                      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                          ↓                                      │
│  Step 2: Virtual Environment                                    │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  python -m venv .venv                                     │ │
│  │  .venv\Scripts\Activate.ps1                               │ │
│  └───────────────────────────────────────────────────────────┘ │
│                          ↓                                      │
│  Step 3: Python Dependencies                                    │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  pip install --upgrade pip                                │ │
│  │  pip install -e .                                         │ │
│  │  pip install -e .[observability]                          │ │
│  │                                                           │ │
│  │  Installs: numpy, pandas, scikit-learn, pyodbc,          │ │
│  │           matplotlib, seaborn, statsmodels,               │ │
│  │           OpenTelemetry, yappi, structlog, rich           │ │
│  └───────────────────────────────────────────────────────────┘ │
│                          ↓                                      │
│  Step 4: SQL Connection Config                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Creates: configs/sql_connection.ini                      │ │
│  │                                                           │ │
│  │  [acm]                                                    │ │
│  │  server = localhost\SQLEXPRESS                            │ │
│  │  database = ACM                                           │ │
│  │  trusted_connection = yes                                 │ │
│  │  driver = ODBC Driver 18 for SQL Server                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                          ↓                                      │
│  Step 5: Database & Schema Installation                        │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  python install/install_acm.py --ini-section acm          │ │
│  │                                                           │ │
│  │  Runs SQL scripts in order:                               │ │
│  │  ✓ 00_create_database.sql    → Create ACM database        │ │
│  │  ✓ 10_tables.sql             → 87 tables                  │ │
│  │  ✓ 15_unique_constraints.sql → Unique constraints         │ │
│  │  ✓ 20_foreign_keys.sql       → 43 foreign keys            │ │
│  │  ✓ 30_indexes.sql            → Indexes                    │ │
│  │  ✓ 40_views.sql              → 14 views                   │ │
│  │  ✓ 50_procedures.sql         → 23 stored procedures       │ │
│  └───────────────────────────────────────────────────────────┘ │
│                          ↓                                      │
│  Step 6: Configuration Population                              │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  python scripts/sql/populate_acm_config.py                │ │
│  │                                                           │ │
│  │  Syncs configs/config_table.csv → ACM_Config table        │ │
│  │  238 configuration parameters loaded                      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                          ↓                                      │
│  Step 7: Observability Stack (Optional)                        │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  cd install/observability                                 │ │
│  │  docker compose up -d                                     │ │
│  │                                                           │ │
│  │  Starts Docker containers:                                │ │
│  │  ✓ Grafana       (port 3000) - Dashboards                 │ │
│  │  ✓ Tempo         (port 3200) - Traces                     │ │
│  │  ✓ Loki          (port 3100) - Logs                       │ │
│  │  ✓ Prometheus    (port 9090) - Metrics                    │ │
│  │  ✓ Pyroscope     (port 4040) - Profiling                  │ │
│  │  ✓ Alloy         (4317, 4318) - OTLP collector            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                          ↓                                      │
│  Step 8: Verification                                           │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  python install/verify_installation.py                    │ │
│  │                                                           │ │
│  │  ✓ Python dependencies                                    │ │
│  │  ✓ Core module imports                                    │ │
│  │  ✓ SQL connectivity                                       │ │
│  │  ✓ Database schema                                        │ │
│  │  ✓ Configuration files                                    │ │
│  │  ✓ Observability stack                                    │ │
│  └───────────────────────────────────────────────────────────┘ │
│                          ↓                                      │
│  Step 9: Success!                                               │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Installation Complete                                    │ │
│  │  Next Steps:                                              │ │
│  │  1. Run: python -m core.acm_main --equip YOUR_EQUIPMENT   │ │
│  │  2. View Grafana: http://localhost:3000                   │ │
│  │  3. See install/QUICKSTART.md                             │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

                            ↓ After Installation

┌─────────────────────────────────────────────────────────────────┐
│                    INSTALLED COMPONENTS                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  File System:                                                   │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  ACM/                                                     │ │
│  │  ├── .venv/              Virtual environment              │ │
│  │  ├── configs/                                             │ │
│  │  │   ├── config_table.csv                                 │ │
│  │  │   └── sql_connection.ini  ← Created by installer       │ │
│  │  ├── core/               ACM core modules                 │ │
│  │  ├── scripts/            Batch runners                    │ │
│  │  ├── grafana_dashboards/ Dashboard JSONs                  │ │
│  │  └── install/            Installer scripts                │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  SQL Server Database:                                           │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  ACM Database                                             │ │
│  │  ├── Tables (87)                                          │ │
│  │  │   ├── Equipment, ACM_Runs, ACM_Scores_Wide            │ │
│  │  │   ├── ACM_HealthTimeline, ACM_RUL                     │ │
│  │  │   ├── ACM_Anomaly_Events, ACM_Config                  │ │
│  │  │   └── ... and 80 more                                 │ │
│  │  ├── Views (14)                                           │ │
│  │  │   ├── vw_AnomalyEvents, vw_Scores                     │ │
│  │  │   └── vw_RunSummary, ...                              │ │
│  │  └── Stored Procedures (23)                              │ │
│  │      ├── usp_ACM_StartRun                                │ │
│  │      ├── usp_ACM_FinalizeRun                             │ │
│  │      └── usp_ACM_GetHistorianData_TEMP, ...              │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Docker Containers (Optional):                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  acm-grafana      http://localhost:3000                   │ │
│  │  acm-tempo        http://localhost:3200                   │ │
│  │  acm-loki         http://localhost:3100                   │ │
│  │  acm-prometheus   http://localhost:9090                   │ │
│  │  acm-pyroscope    http://localhost:4040                   │ │
│  │  acm-alloy        localhost:4317, 4318                    │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    INSTALLATION TIME                            │
├─────────────────────────────────────────────────────────────────┤
│  Prerequisites check:         ~30 seconds                       │
│  Virtual environment:         ~15 seconds                       │
│  Python dependencies:         ~2 minutes                        │
│  SQL connection config:       ~5 seconds                        │
│  Database + schema:           ~1 minute                         │
│  Configuration population:    ~10 seconds                       │
│  Observability stack:         ~1 minute                         │
│  Verification:               ~30 seconds                        │
│  ──────────────────────────────────────────                     │
│  TOTAL:                      ~5-7 minutes                       │
└─────────────────────────────────────────────────────────────────┘
```

## Supported Installation Scenarios

| Scenario | Command | Notes |
|----------|---------|-------|
| **Standard (Windows Auth)** | `.\Install-ACM.ps1 -Server "localhost\SQLEXPRESS" -TrustedConnection` | Recommended |
| **SQL Authentication** | `.\Install-ACM.ps1 -Server "server,1433" -SqlUser "sa" -SqlPassword "pass"` | For non-domain servers |
| **No Observability** | `.\Install-ACM.ps1 -Server "localhost" -TrustedConnection -SkipObservability` | Minimal install |
| **Custom Database** | `.\Install-ACM.ps1 -Server "localhost" -Database "MyACM" -TrustedConnection` | Non-standard DB name |
| **No VirtualEnv** | `.\Install-ACM.ps1 -Server "localhost" -TrustedConnection -SkipVenv` | Use global Python |
| **Skip Verification** | `.\Install-ACM.ps1 -Server "localhost" -TrustedConnection -SkipVerification` | Trust installation |

## Error Recovery

The installer is **idempotent** - running it multiple times is safe:
- Virtual environment: Prompts before recreating
- SQL scripts: Use `IF NOT EXISTS` / `CREATE OR ALTER`
- Configuration: Prompts before overwriting
- Docker: `docker compose up -d` updates existing containers

If installation fails partway through, simply run it again.

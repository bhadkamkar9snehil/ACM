# ACM Installation Guide

This folder contains everything needed to install ACM from scratch on a Windows environment.

## Quick Start (Recommended)

### Prerequisites
You must install these **before** running the ACM installer:

1. **SQL Server** (any edition: Express, Developer, Standard, Enterprise)
   - Download: https://www.microsoft.com/en-us/sql-server/sql-server-downloads
   - Note: Installation varies by edition; follow Microsoft's installation guide

2. **Python 3.11 or later**
   - Download: https://www.python.org/downloads/
   - ✅ Check "Add Python to PATH" during installation

3. **SQL Server ODBC Driver 18**
   - Download: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
   - Required for Python-to-SQL connectivity

4. **Docker Desktop** (optional, for observability stack)
   - Download: https://www.docker.com/products/docker-desktop
   - Required only if you want monitoring/tracing/profiling

### One-Command Installation

```powershell
# Run as Administrator (recommended)
.\Install-ACM.ps1 -Server "localhost\SQLEXPRESS" -TrustedConnection
```

That's it! The installer will:
- ✅ Verify prerequisites
- ✅ Create Python virtual environment
- ✅ Install all Python dependencies
- ✅ Create SQL connection configuration
- ✅ Create ACM database
- ✅ Install all tables, views, stored procedures
- ✅ Populate configuration from config_table.csv
- ✅ Start observability stack (if Docker available)
- ✅ Verify installation

### Installation Options

**With SQL Authentication:**
```powershell
.\Install-ACM.ps1 -Server "myserver,1433" -SqlUser "sa" -SqlPassword "MyP@ssw0rd"
```

**Skip observability stack:**
```powershell
.\Install-ACM.ps1 -Server "localhost" -TrustedConnection -SkipObservability
```

**Skip virtual environment (use global Python):**
```powershell
.\Install-ACM.ps1 -Server "localhost" -TrustedConnection -SkipVenv
```

**Custom database name:**
```powershell
.\Install-ACM.ps1 -Server "localhost" -Database "MyACM" -TrustedConnection
```

## Manual Installation (Advanced)

If you prefer to install components individually:

### Step 1: Check Prerequisites
```powershell
.\Test-Prerequisites.ps1
```

### Step 2: Create Virtual Environment
```powershell
cd <ACM_ROOT>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Python Dependencies
```powershell
python -m pip install --upgrade pip
pip install -e .

# Optional: Install observability packages
pip install -e ".[observability]"
```

### Step 4: Configure SQL Connection
Create `configs/sql_connection.ini`:
```ini
[acm]
server = localhost\SQLEXPRESS
database = ACM
trusted_connection = yes
driver = ODBC Driver 18 for SQL Server
TrustServerCertificate = yes
```

### Step 5: Install SQL Schema
```powershell
python install/install_acm.py --ini-section acm
```

### Step 6: Populate Configuration
```powershell
python scripts/sql/populate_acm_config.py
```

### Step 7: Start Observability Stack (Optional)
```powershell
cd install/observability
docker compose up -d
```

### Step 8: Verify Installation
```powershell
python install/verify_installation.py
```

## SQL Installation Details

### Contents (in `install/sql/`)
- `00_create_database.sql` – Creates `ACM` database if missing
- `10_tables.sql` – All 87 tables (matching `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md`)
- `15_unique_constraints.sql` – Unique constraints
- `20_foreign_keys.sql` – 43 foreign keys
- `30_indexes.sql` – Non-PK indexes
- `40_views.sql` – 14 views (`CREATE OR ALTER`)
- `50_procedures.sql` – 23 stored procedures (`CREATE OR ALTER`)

### Manual SQL Installation
```powershell
python install/install_acm.py --ini-section acm

# Or override connection:
python install/install_acm.py --server localhost\SQLEXPRESS --database ACM --trusted-connection
```

### Regenerating SQL Scripts (Advanced)
If you modify the database schema and need to update the installation scripts:
```powershell
python install/generate_install_scripts.py --ini-section acm
```

## Observability Stack

The observability stack provides monitoring, tracing, logging, and profiling via Docker containers.

### Start Stack
```powershell
cd install/observability
docker compose up -d
```

### Stop Stack
```powershell
cd install/observability
docker compose down
```

### Endpoints
- **Grafana**: http://localhost:3000 (admin/admin)
- **Tempo** (traces): http://localhost:3200
- **Loki** (logs): http://localhost:3100
- **Prometheus** (metrics): http://localhost:9090
- **Pyroscope** (profiling): http://localhost:4040
- **Alloy** (OTLP collector): localhost:4317 (gRPC), localhost:4318 (HTTP)

### Import Grafana Dashboards
1. Open Grafana at http://localhost:3000
2. Login with admin/admin
3. Go to Dashboards → Import
4. Upload JSON files from `grafana_dashboards/`

## Post-Installation

### Test ACM
```powershell
# Activate virtual environment (if using one)
.\.venv\Scripts\Activate.ps1

# Single equipment run
python -m core.acm_main --equip YOUR_EQUIPMENT_NAME

# Batch processing
python scripts/sql_batch_runner.py --equip EQUIP1 EQUIP2 --tick-minutes 1440
```

### Configuration Files
- `configs/sql_connection.ini` - SQL Server connection settings
- `configs/config_table.csv` - ACM runtime parameters (238 settings)

### Sync Configuration to Database
After editing `config_table.csv`:
```powershell
python scripts/sql/populate_acm_config.py
```

## Troubleshooting

### "ODBC Driver not found"
- Install ODBC Driver 18 from Microsoft
- Or modify `sql_connection.ini` to use Driver 17

### "Login failed for user"
**For Windows Authentication:**
```powershell
# Run SQL query to verify your Windows user has access:
sqlcmd -S "localhost\SQLEXPRESS" -E -Q "SELECT SYSTEM_USER"

# Grant access if needed (run as SA):
sqlcmd -S "localhost\SQLEXPRESS" -U sa -P YourPassword -Q "CREATE LOGIN [DOMAIN\Username] FROM WINDOWS; ALTER SERVER ROLE sysadmin ADD MEMBER [DOMAIN\Username];"
```

**For SQL Authentication:**
- Enable SQL Server authentication in SQL Server Configuration Manager
- Restart SQL Server service
- Create SQL user with appropriate permissions

### "Cannot open database 'ACM'"
```powershell
# Verify database exists:
sqlcmd -S "localhost\SQLEXPRESS" -E -Q "SELECT name FROM sys.databases"

# Create manually if needed:
sqlcmd -S "localhost\SQLEXPRESS" -E -Q "CREATE DATABASE ACM"

# Then rerun schema installer:
python install/install_acm.py --ini-section acm
```

### Docker containers not starting
```powershell
# Check Docker is running:
docker ps

# View container logs:
docker logs acm-grafana
docker logs acm-tempo
docker logs acm-loki

# Restart stack:
cd install/observability
docker compose down
docker compose up -d
```

### Python import errors
```powershell
# Reinstall dependencies:
pip install --force-reinstall -e ".[observability]"

# Verify installation:
python install/verify_installation.py
```

### Virtual environment activation fails
```powershell
# Enable script execution (run PowerShell as Administrator):
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then activate:
.\.venv\Scripts\Activate.ps1
```

## Getting Help

- **System Documentation**: `docs/ACM_SYSTEM_OVERVIEW.md`
- **SQL Schema Reference**: `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md`
- **Observability Guide**: `docs/OBSERVABILITY.md`
- **GitHub Issues**: https://github.com/bhadkamkar9snehil/ACM/issues

## Notes

- All SQL scripts are **idempotent** (`IF NOT EXISTS` for tables/FKs/indexes, `CREATE OR ALTER` for views/SPs)
- Running installation multiple times is safe
- Uses `configs/sql_connection.ini` by default; CLI flags override
- Virtual environment is created in `.venv/` (gitignored)
- Observability stack requires Docker Desktop

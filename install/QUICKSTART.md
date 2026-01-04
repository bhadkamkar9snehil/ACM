# ACM Quick Start Guide

## Installation (5 Minutes)

### Step 1: Install Prerequisites
Before running ACM installer, ensure you have:
- ✅ SQL Server (any edition) installed and running
- ✅ Python 3.11+ installed (https://www.python.org/downloads/)
- ✅ ODBC Driver 18 (https://aka.ms/downloadmsodbcsql)
- ✅ Docker Desktop (optional, for monitoring)

### Step 2: Run ACM Installer
```powershell
# Navigate to ACM install directory
cd C:\path\to\ACM\install

# Run the interactive installer
.\QuickInstall.bat
```

**OR** use PowerShell directly:
```powershell
.\Install-ACM.ps1 -Server "localhost\SQLEXPRESS" -TrustedConnection
```

The installer will:
- Create Python virtual environment
- Install all dependencies
- Create ACM database
- Install schema (tables, views, stored procedures)
- Configure connections
- Start monitoring stack
- Verify installation

### Step 3: Verify Installation
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run verification
python install\verify_installation.py
```

## First Run (2 Minutes)

### Test ACM with Sample Data
```powershell
# Activate environment (if not already active)
.\.venv\Scripts\Activate.ps1

# Run ACM on an equipment
python -m core.acm_main --equip YOUR_EQUIPMENT_NAME

# Example with FD_FAN
python -m core.acm_main --equip FD_FAN
```

### Run Batch Processing
```powershell
python scripts\sql_batch_runner.py --equip FD_FAN --tick-minutes 1440
```

## View Results

### Option 1: Grafana Dashboards (Recommended)
1. Open http://localhost:3000
2. Login: admin / admin
3. Go to Dashboards → Import
4. Upload dashboards from `grafana_dashboards/` folder
5. View equipment health, anomalies, forecasts

### Option 2: SQL Queries
```sql
-- View recent runs
SELECT TOP 10 * FROM ACM_Runs ORDER BY StartedAt DESC

-- View anomaly events
SELECT * FROM ACM_Anomaly_Events WHERE EquipID=1

-- View health timeline
SELECT * FROM ACM_HealthTimeline WHERE EquipID=1

-- View RUL predictions
SELECT * FROM ACM_RUL WHERE EquipID=1 ORDER BY CreatedAt DESC
```

## Configuration

### Edit Equipment Settings
```powershell
# Edit config file
notepad configs\config_table.csv

# Sync to database
python scripts\sql\populate_acm_config.py
```

### Common Settings to Adjust
- `data.sampling_secs` - Data cadence (30 min = 1800 sec)
- `data.timestamp_col` - Timestamp column name
- `thresholds.q` - Anomaly detection threshold (0.98 default)
- `forecasting.max_forecast_hours` - Forecast horizon (168h = 7 days)

## Troubleshooting

### "Login failed for user"
```powershell
# Verify SQL Server is running
Get-Service MSSQL*

# Test connection
sqlcmd -S "localhost\SQLEXPRESS" -E -Q "SELECT @@VERSION"
```

### "ODBC Driver not found"
- Install ODBC Driver 18 from https://aka.ms/downloadmsodbcsql
- OR edit `configs/sql_connection.ini` to use Driver 17

### "Module not found"
```powershell
# Reinstall dependencies
.\.venv\Scripts\Activate.ps1
pip install -e ".[observability]"
```

### Docker containers not starting
```powershell
# Check Docker is running
docker ps

# Restart observability stack
cd install\observability
docker compose down
docker compose up -d
```

## Next Steps

1. **Import your equipment data**
   - Add equipment to `Equipment` table in SQL
   - Populate historian data tables
   - Configure in `config_table.csv`

2. **Customize detectors**
   - Adjust detector weights in config
   - Tune thresholds for your data
   - Enable/disable specific detectors

3. **Setup scheduled runs**
   - Create Windows Task Scheduler job
   - Run batch runner daily/hourly
   - Monitor via Grafana

4. **Explore dashboards**
   - Equipment Health Overview
   - Anomaly Events
   - RUL Predictions
   - Detector Scores
   - Regime Timeline

## Documentation

- **Full System Guide**: `docs/ACM_SYSTEM_OVERVIEW.md`
- **Installation Guide**: `install/README.md`
- **SQL Schema**: `docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md`
- **Observability**: `docs/OBSERVABILITY.md`

## Support

- GitHub Issues: https://github.com/bhadkamkar9snehil/ACM/issues
- Documentation: `docs/` folder
- Configuration: `configs/config_table.csv`

---

**Installation Time**: ~5 minutes  
**First Run**: ~2 minutes  
**Total Time to Working ACM**: ~7 minutes

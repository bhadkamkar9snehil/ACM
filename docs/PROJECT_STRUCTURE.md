# ACM V8 Directory Structure

## Root Directory (Clean)
```
ACM V8 SQL/
├── configs/              # Configuration files
│   ├── config.yaml       # Main config (YAML)
│   ├── config_*.yaml     # Equipment-specific configs
│   ├── config_table.csv  # Config table (future: SQL-backed)
│   └── sql_connection.ini # SQL credentials (plain text)
├── core/                 # Pipeline modules
├── models/               # Detector implementations
├── utils/                # Utilities (config, logger, paths, timer)
├── scripts/              # Organized scripts (see below)
├── tests/                # Unit tests
├── docs/                 # Documentation
├── data/                 # Training/test data
├── artifacts/            # Run outputs
├── rust_bridge/          # Optional Rust acceleration
├── pyproject.toml        # Python project config
├── README.md             # Main documentation
├── CHANGELOG.md          # Version history
└── RUNBOOK.md            # Operational guide
```

## Scripts Organization

### scripts/analysis/
Analysis and batch processing tools:
- `analyze_episodes.py` - Episode analysis
- `analyze_batch_evolution.py` - Batch evolution tracking
- `check_zscore.py` - Z-score validation
- `create_chunked_data.py` - Data chunking utility
- `generate_evolution_proof.py` - Model evolution proof
- `run_batches.py` - Batch execution
- `simulate_batch_runs.py` - Batch simulation
- `analyze_latest_run.py` - Latest run analyzer
- `polars_benchmark.py` - Performance benchmarking

### scripts/demos/
Demo and example scripts:
- `demo_coldstart.py` - Cold-start mode demonstration

### scripts/testing/
Test scripts and validation:
- `test_coldstart.py` - Cold-start tests
- `test_coldstart_fd_fan.py` - FD Fan cold-start tests
- `test_coldstart_full.py` - Full cold-start tests
- `test_coldstart_gas_turbine.py` - Gas Turbine cold-start tests
- `test_config_dict.py` - Config dictionary tests

### scripts/sql/
SQL Server integration:
- `00_create_database.sql` - ACM database creation
- `10_core_tables.sql` - Core tables DDL
- `15_config_tables.sql` - Config tables DDL
- `20_stored_procs.sql` - Lifecycle stored procedures
- `25_equipment_discovery_procs.sql` - XStudio_DOW discovery procs
- `30_views.sql` - Analytics views
- `verify_acm_connection.py` - Connection verification script

### scripts/PowerShell/
- `run_file_mode.ps1` - File mode runner
- `run_V5.ps1` - V5 runner

## SQL Integration Architecture

```
┌─────────────────────────────────────────────┐
│   SQL Server (Same Instance)                │
├─────────────────────────────────────────────┤
│  XStudio_DOW (READ-ONLY)                    │
│  ├─ Equipment_Type_Mst_Tbl                  │
│  ├─ {Type}_Mst_Tbl (Pump, Fan, etc.)       │
│  └─ {Type}_Tag_Mapping_Tbl                 │
├─────────────────────────────────────────────┤
│  ACM (READ/WRITE)                           │
│  ├─ Equipments (synced from DOW)           │
│  ├─ RunLog, ScoresTS, DriftTS              │
│  ├─ AnomalyEvents, RegimeEpisodes          │
│  ├─ PCA_Model, PCA_Components, PCA_Metrics │
│  ├─ RunStats, ConfigLog                    │
│  └─ Discovery Procs (read DOW, write ACM)  │
└─────────────────────────────────────────────┘
```

## Configuration Files

### sql_connection.ini (Plain Text Credentials)
```ini
[sql]
server=localhost,1433
database=ACM
user=sa
password=YourPassword
driver=ODBC Driver 18 for SQL Server
encrypt=true
trust_server_certificate=true
```

### config.yaml (Application Config)
YAML-based configuration for pipeline parameters, detectors, fusion, etc.
SQL section can reference environment variables for security.

## Quick Commands

### Verify SQL Connection
```powershell
python scripts/sql/verify_acm_connection.py
```

### Run ACM in File Mode
```powershell
python -m core.acm_main --equip "FD_FAN" --artifact-root artifacts --config configs/config.yaml --mode batch --enable-report
```

### Install SQL Database
```powershell
# In SSMS or via Invoke-Sqlcmd:
scripts/sql/00_create_database.sql
scripts/sql/10_core_tables.sql
scripts/sql/15_config_tables.sql
scripts/sql/20_stored_procs.sql
scripts/sql/25_equipment_discovery_procs.sql
scripts/sql/30_views.sql
```

## Documentation

- **SQL Setup**: `docs/sql/SQL_SETUP.md`
- **Analytics Backbone**: `docs/Analytics Backbone.md`
- **Main README**: `README.md`
- **Runbook**: `RUNBOOK.md`
- **Changelog**: `CHANGELOG.md`

## Notes

- All analysis/test scripts moved out of root for cleaner structure
- SQL integration ready for deployment with complete DDL and discovery procs
- Connection credentials isolated in `sql_connection.ini` (keep out of source control)
- Per-equipment-instance execution model aligned with XStudio_DOW architecture

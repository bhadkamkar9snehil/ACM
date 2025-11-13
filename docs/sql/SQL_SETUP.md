# ACM SQL Server Setup

This guide creates the ACM database on Microsoft SQL Server with Latin1_General_CI_AI collation, installs tables, views, and stored procedures, and shows how to connect from the ACM Python project on your Windows machine.

## Prerequisites
- SQL Server 2019+ (Developer/Express/Standard) installed locally or accessible via network
- SQL Server Management Studio (SSMS) or Azure Data Studio
- A SQL Login with CREATE DATABASE and DDL permissions (e.g., sysadmin on local dev)
- Windows user has access to the new database

## What gets installed
- Database: ACM (collation Latin1_General_CI_AI)
- Schemas: dbo (default)
- Tables: core time-series (ScoresTS, DriftTS), events/episodes (AnomalyEvents, RegimeEpisodes), PCA (PCA_Model, PCA_Components, PCA_Metrics), run log (RunLog), config (ConfigLog, ACM_Config, ACM_ConfigHistory)
- Views: handy summaries for anomaly events, scores, run summary
- Stored procedures: run lifecycle helpers (Start/Finalize) and equipment registration

## Install steps
1) Open SSMS and connect to your local instance (e.g., (local) or localhost or .\\SQLEXPRESS)
2) Run the scripts in order:
   - scripts/sql/00_create_database.sql
   - scripts/sql/10_core_tables.sql
   - scripts/sql/15_config_tables.sql (optional but recommended)
   - scripts/sql/20_stored_procs.sql
   - scripts/sql/25_equipment_discovery_procs.sql (for XStudio_DOW integration)
   - scripts/sql/30_views.sql

If you prefer, you can run them via PowerShell:

```powershell
# Optional sample: change instance/db paths as needed
$sqlFiles = @(
  "scripts/sql/00_create_database.sql",
  "scripts/sql/10_core_tables.sql",
  "scripts/sql/15_config_tables.sql",
  "scripts/sql/20_stored_procs.sql",
  "scripts/sql/25_equipment_discovery_procs.sql",
  "scripts/sql/30_views.sql"
)
$instance = "."            # or ".\\SQLEXPRESS" or "localhost,1433"
foreach ($f in $sqlFiles) {
  Write-Host "Running $f..." -ForegroundColor Cyan
  Invoke-Sqlcmd -ServerInstance $instance -InputFile $f
}
Write-Host "ACM database setup complete!" -ForegroundColor Green
```

## Collation note
The ACM database is created with Latin1_General_CI_AI to match the requirement for case-insensitive, accent-insensitive searches.

## Connecting from Python

ACM already has a built-in SQL client (`core/sql_client.py`) that uses pyodbc. Configure it in `configs/config.yaml`:

### Simple credential file (preferred for this project)

Create `configs/sql_connection.ini` and put your server and SA credentials in plain text:

```ini
[sql]
server=localhost,1433        ; or SERVER\\INSTANCE
database=ACM
user=sa
password=YourPassword123
driver=ODBC Driver 18 for SQL Server
encrypt=true
trust_server_certificate=true
```

This file is automatically picked up by `core/sql_client.py` and overrides any values in `configs/config.yaml`.

### Alternative: config.yaml (if you prefer)

```yaml
sql:
    driver: "ODBC Driver 18 for SQL Server"
    server: "localhost,1433"
    database: "ACM"
    username: "${ACM_SQL_USER}"
    password: "${ACM_SQL_PASSWORD}"
    encrypt: true
    trust_server_certificate: true
    timeout_seconds: 30
```

### Setting Credentials

Use `configs/sql_connection.ini` for this project. If you prefer environment variables, you can still set:

```powershell
$env:ACM_SQL_USER = "sa"
$env:ACM_SQL_PASSWORD = "YourPassword123"
```

### Server Connection Formats

- **Default Instance**: `localhost` or `localhost,1433`
- **Named Instance**: `localhost\\SQLEXPRESS` or `SERVER\\INSTANCENAME`
- **Remote Server**: `192.168.1.100,1433` or `server.domain.com\\INSTANCE`
- **Azure SQL**: `yourserver.database.windows.net,1433`

### Prerequisites
- Install ODBC Driver 17 or 18 for SQL Server (download from Microsoft)
- Verify installation: Open "ODBC Data Sources (64-bit)" in Windows and check Drivers tab
- Ensure SQL Server allows SQL Authentication (mixed mode) if using SA account

The pipeline's SQL writers will:
- Register/ensure `Equipments` row exists (you can also call `dbo.usp_ACM_RegisterEquipment` yourself)
- Call `dbo.usp_ACM_StartRun` to create a RunLog row and clean prior data for the same RunID
- Bulk insert rows into ScoresTS, DriftTS, AnomalyEvents, RegimeEpisodes, PCA tables, RunStats, ConfigLog
- Call `dbo.usp_ACM_FinalizeRun` with outcome and row counts

## Equipment data in a separate database

### XStudio_DOW Integration (DOW Plant Database)

ACM runs on the **same SQL Server instance** as XStudio_DOW but in a **separate database** (`ACM`). The SA account is shared across all databases.

**Architecture**:
- **XStudio_DOW**: Contains equipment metadata (types, instances, tag mappings)
  - `Equipment_Type_Mst_Tbl` → Equipment types (Pump, Fan, Turbine, etc.)
  - `{EquipmentType}_Mst_Tbl` → Equipment instances (Pump_Mst_Tbl, Fan_Mst_Tbl, etc.)
  - `{EquipmentType}_Tag_Mapping_Tbl` → Tag-to-attribute mappings per equipment instance
- **ACM**: Contains analytics results (scores, anomalies, PCA, drift, episodes)
- **Historian**: Time-series data (queried by TagName from mappings)

**Access Pattern**:
- ACM has **READ-ONLY** access to XStudio_DOW (no writes to DOW tables)
- ACM discovers equipment instances and tag mappings from DOW dynamically
- ACM runs as **separate tasks per equipment instance** (one run per Pump-001, Pump-002, etc.)

### Stored Procedures for Equipment Discovery

Create these helper procs in the **ACM** database to read from XStudio_DOW:

#### 1. Get All Equipment Instances for a Type

```sql
USE [ACM];
GO

CREATE OR ALTER PROCEDURE dbo.usp_GetEquipmentInstances
    @EquipmentTypeName nvarchar(128)
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Get EquipmentTypeID from DOW
    DECLARE @TypeID int;
    SELECT @TypeID = ID 
    FROM [XStudio_DOW].[dbo].[Equipment_Type_Mst_Tbl]
    WHERE Name = @EquipmentTypeName AND IsDeleted = 0;
    
    IF @TypeID IS NULL
    BEGIN
        RAISERROR('Equipment type "%s" not found in XStudio_DOW', 16, 1, @EquipmentTypeName);
        RETURN;
    END
    
    -- Dynamic query to read from corresponding equipment master table
    DECLARE @sql nvarchar(max);
    SET @sql = N'SELECT ID AS EquipmentID, Name AS EquipmentName, 
                        AreaID, TemplateID, CreatedOn, ModifiedOn
                 FROM [XStudio_DOW].[dbo].[' + @EquipmentTypeName + '_Mst_Tbl]
                 WHERE IsDeleted = 0 AND EquipmentTypeID = @TypeID';
    
    EXEC sp_executesql @sql, N'@TypeID int', @TypeID;
END
GO
```

#### 2. Get Tag Mappings for an Equipment Instance

```sql
USE [ACM];
GO

CREATE OR ALTER PROCEDURE dbo.usp_GetEquipmentTagMappings
    @EquipmentTypeName nvarchar(128),
    @EquipmentID int
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Dynamic query to read tag mappings
    DECLARE @sql nvarchar(max);
    SET @sql = N'
    SELECT 
        EquipmentID,
        Attribute,
        TagName,
        InstrumentTag,
        HHRange, HRange, LRange, LLRange,
        Type,
        IsXBatchTag
    FROM [XStudio_DOW].[dbo].[' + @EquipmentTypeName + '_Tag_Mapping_Tbl]
    WHERE EquipmentID = @EquipID AND IsDeleted = 0';
    
    EXEC sp_executesql @sql, N'@EquipID int', @EquipmentID;
END
GO
```

#### 3. Sync Equipment Instance to ACM

```sql
USE [ACM];
GO

CREATE OR ALTER PROCEDURE dbo.usp_SyncEquipmentFromDOW
    @EquipmentTypeName nvarchar(128),
    @EquipmentID_DOW int,
    @EquipID_ACM int OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Get equipment instance details from DOW
    DECLARE @EquipName nvarchar(128);
    DECLARE @sql nvarchar(max);
    DECLARE @ParmDefinition nvarchar(500);
    
    SET @sql = N'SELECT @Name = Name 
                 FROM [XStudio_DOW].[dbo].[' + @EquipmentTypeName + '_Mst_Tbl]
                 WHERE ID = @ID AND IsDeleted = 0';
    SET @ParmDefinition = N'@ID int, @Name nvarchar(128) OUTPUT';
    
    EXEC sp_executesql @sql, @ParmDefinition, 
         @ID = @EquipmentID_DOW, 
         @Name = @EquipName OUTPUT;
    
    IF @EquipName IS NULL
    BEGIN
        RAISERROR('Equipment ID %d not found in %s_Mst_Tbl', 16, 1, @EquipmentID_DOW, @EquipmentTypeName);
        RETURN;
    END
    
    -- Build EquipCode as Type_Name (e.g., "Pump_PumpA-001")
    DECLARE @EquipCode nvarchar(64);
    SET @EquipCode = @EquipmentTypeName + '_' + @EquipName;
    
    -- Upsert into ACM.Equipments
    EXEC dbo.usp_ACM_RegisterEquipment 
        @EquipCode = @EquipCode,
        @ExternalDb = 'XStudio_DOW',
        @Active = 1,
        @EquipID = @EquipID_ACM OUTPUT;
    
    SELECT @EquipID_ACM AS EquipID_ACM, @EquipCode AS EquipCode, @EquipName AS EquipName;
END
GO
```

### Usage Pattern

**Workflow for running ACM on all Pumps**:

```sql
-- 1. Get all pump instances
EXEC ACM.dbo.usp_GetEquipmentInstances @EquipmentTypeName = 'Pump';

-- 2. For each pump, sync to ACM and get tag mappings
DECLARE @EquipID_ACM int;
EXEC ACM.dbo.usp_SyncEquipmentFromDOW 
    @EquipmentTypeName = 'Pump',
    @EquipmentID_DOW = 123,  -- from step 1
    @EquipID_ACM = @EquipID_ACM OUTPUT;

-- 3. Get tag mappings for this equipment
EXEC ACM.dbo.usp_GetEquipmentTagMappings 
    @EquipmentTypeName = 'Pump',
    @EquipmentID = 123;

-- 4. Python ACM pipeline uses these mappings to query historian by TagName
-- 5. ACM writes results to ACM database tables
```

**Python Integration Example**:
```python
from core.sql_client import SQLClient

sql = SQLClient(config["sql"]).connect()

# Discover all pumps
cursor = sql.cursor()
cursor.execute("EXEC ACM.dbo.usp_GetEquipmentInstances @EquipmentTypeName = ?", ("Pump",))
pumps = cursor.fetchall()

for pump in pumps:
    equip_id_dow = pump.EquipmentID
    equip_name = pump.EquipmentName
    
    # Sync to ACM
    cursor.execute("""
        DECLARE @acm_id int;
        EXEC ACM.dbo.usp_SyncEquipmentFromDOW 
            @EquipmentTypeName = ?, 
            @EquipmentID_DOW = ?, 
            @EquipID_ACM = @acm_id OUTPUT;
        SELECT @acm_id AS EquipID_ACM;
    """, ("Pump", equip_id_dow))
    
    acm_equip_id = cursor.fetchone().EquipID_ACM
    
    # Get tag mappings
    cursor.execute("EXEC ACM.dbo.usp_GetEquipmentTagMappings @EquipmentTypeName = ?, @EquipmentID = ?", 
                   ("Pump", equip_id_dow))
    tags = cursor.fetchall()
    
    # Build signal list for ACM run
    tag_names = [row.TagName for row in tags]
    
    # Run ACM pipeline for this equipment instance
    # ... (query historian, run analytics, write to ACM tables)
```

### Important Notes

- **No writes to XStudio_DOW**: ACM only reads equipment metadata; all analytics results go to ACM database
- **Dynamic table names**: The procs use dynamic SQL since equipment type determines table names (`Pump_Mst_Tbl`, `Fan_Mst_Tbl`, etc.)
- **EquipCode convention**: ACM uses `{EquipmentType}_{EquipmentName}` as the unique identifier
- **Automatic discovery**: ACM can detect new equipment instances and tag changes by re-running the sync procs

## Verifying installation
- Tables should appear under ACM > Tables
- Register equipment: `DECLARE @id int; EXEC dbo.usp_ACM_RegisterEquipment @EquipCode = N'FD_FAN', @EquipID = @id OUTPUT; SELECT @id AS EquipID;`
- Start a run: `DECLARE @rid uniqueidentifier; EXEC dbo.usp_ACM_StartRun @EquipID=1, @RunID=@rid OUTPUT, @Stage=N'started'; SELECT @rid AS RunID;`
- Insert a couple rows into ScoresTS manually to test, then finalize: `EXEC dbo.usp_ACM_FinalizeRun @RunID=@rid, @Outcome=N'success', @RowsWritten=2;`

## Maintenance
- Indexes: core tables are indexed by (RunID, EquipID, TimeUTC) where applicable
- Purge policy: delete old runs by date or keep-last-N per asset; implement a DBA task as needed
- Backups: use SIMPLE recovery for dev; FULL for prod with scheduled log backups

## Troubleshooting
- Login failed: verify SQL Server authentication mode and user permissions
- ODBC driver not found: install "ODBC Driver 17 for SQL Server" or newer
- Collation mismatch warnings: ensure client databases and tempdb uses compatible collations; ACM uses Latin1_General_CI_AI

## Stored procedure contracts
These procedures align with the `RunLog` table as defined in `10_core_tables.sql`:

1) `dbo.usp_ACM_RegisterEquipment(@EquipCode, @ExternalDb=NULL, @Active=1, @EquipID OUTPUT)`
  - Upserts into `Equipments(EquipCode, ExternalDb, Active)` and returns `EquipID`.

2) `dbo.usp_ACM_StartRun(@EquipID, @ConfigHash=NULL, @WindowStartEntryDateTime=NULL, @WindowEndEntryDateTime=NULL, @Stage=N'started', @Version=NULL, @TriggerReason=NULL, @RunID OUTPUT)`
  - Inserts a row into `RunLog` and deletes any existing artifacts for that `RunID` in core tables.

3) `dbo.usp_ACM_FinalizeRun(@RunID, @Outcome, @RowsRead=NULL, @RowsWritten=NULL, @ErrorJSON=NULL)`
  - Updates `RunLog` with end time, outcome, optional row counts, and error JSON.

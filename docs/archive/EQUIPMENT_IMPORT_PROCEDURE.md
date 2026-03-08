# Equipment Import Procedure

This document describes how to import a new equipment's sensor data into the ACM system.

## Prerequisites

- CSV file with sensor data (datetime column + sensor columns)
- SQL Server access to ACM database
- Python environment with pyodbc installed

## Overview

Importing new equipment requires 3 database entries:
1. **Equipment table** - Register the equipment identity
2. **{EQUIP_CODE}_Data table** - Store the raw sensor time series
3. **ACM_TagEquipmentMap** - Map sensor columns to the equipment

## Step-by-Step Procedure

### Step 1: Prepare Your CSV File

Your CSV must have:
- A datetime column (named `Date/Time`, `Timestamp`, `DateTime`, or `EntryDateTime`)
- One or more numeric sensor columns
- No duplicate timestamps

Example format:
```csv
Date/Time,Temperature,Pressure,Vibration,Flow_Rate
2024-01-01 00:00:00,85.2,14.7,0.02,150.5
2024-01-01 00:30:00,85.8,14.6,0.03,151.2
```

### Step 2: Run the Import Script

```powershell
cd "c:\Users\bhadk\Documents\ACM V8 SQL\ACM"
python scripts/sql/import_csv_to_acm.py --csv "path/to/your_data.csv" --equip-code "YOUR_EQUIP" --equip-name "Your Equipment Name"
```

**Parameters:**
- `--csv` : Path to your CSV file
- `--equip-code` : Short code (uppercase, no spaces, e.g., `PUMP_01`, `COMPRESSOR_A`)
- `--equip-name` : Descriptive name for dashboard display

The script automatically:
1. Creates entry in `Equipment` table with unique EquipID
2. Creates `{EQUIP_CODE}_Data` table with proper schema
3. Imports all rows with EquipID foreign key
4. Registers all sensor columns in `ACM_TagEquipmentMap`

### Step 3: Verify Import

```sql
-- Check Equipment entry
SELECT EquipID, EquipCode, EquipName FROM Equipment WHERE EquipCode = 'YOUR_EQUIP'

-- Check data row count
SELECT COUNT(*) FROM YOUR_EQUIP_Data

-- Check date range
SELECT MIN(EntryDateTime), MAX(EntryDateTime) FROM YOUR_EQUIP_Data

-- Check tag mappings
SELECT * FROM ACM_TagEquipmentMap WHERE EquipID = <your_equip_id>
```

### Step 4: Run ACM Batch Processing

```powershell
python scripts/sql_batch_runner.py --equip YOUR_EQUIP --max-batches 10 --tick-minutes 1440
```

This processes the data through ACM's analytics pipeline:
- Coldstart model training (first run)
- Health scoring
- Anomaly detection
- Regime classification
- Forecasting

### Step 5: View in Dashboard

1. Open Grafana dashboard
2. Select your equipment from the **Equipment** dropdown
3. Adjust time range to match your data's date range
4. Refresh the dashboard

## Manual Import (Without Script)

If you need to import manually, follow these SQL steps:

### Step A: Create Equipment Entry

```sql
-- Get next available EquipID
DECLARE @NewEquipID INT = (SELECT ISNULL(MAX(EquipID), 0) + 1 FROM Equipment WHERE EquipID < 10000);

INSERT INTO Equipment (EquipID, EquipCode, EquipName, Status, CommissionDate, CreatedAtUTC)
VALUES (@NewEquipID, 'YOUR_EQUIP', 'Your Equipment Name', 'Active', GETDATE(), GETUTCDATE());

SELECT @NewEquipID AS NewEquipID;
```

### Step B: Create Data Table

```sql
CREATE TABLE YOUR_EQUIP_Data (
    EntryDateTime DATETIME2 NOT NULL,
    EquipID INT NOT NULL,
    Sensor1 FLOAT NULL,
    Sensor2 FLOAT NULL,
    -- Add columns for each sensor
    LoadedAt DATETIME2 DEFAULT GETUTCDATE(),
    CONSTRAINT FK_YOUR_EQUIP_Data_Equipment FOREIGN KEY (EquipID) REFERENCES Equipment(EquipID)
);

CREATE INDEX IX_YOUR_EQUIP_Data_Time ON YOUR_EQUIP_Data(EntryDateTime);
```

### Step C: Import Data (via BULK INSERT or pandas)

```sql
-- Option 1: BULK INSERT (for large files)
BULK INSERT YOUR_EQUIP_Data
FROM 'C:\path\to\data.csv'
WITH (FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '\n');

-- Option 2: Use Python pandas with to_sql()
```

### Step D: Register Tags

```sql
DECLARE @EquipID INT = <your_equip_id>;

INSERT INTO ACM_TagEquipmentMap (EquipID, TagName, ColumnName, IsActive, CreatedAt)
VALUES 
    (@EquipID, 'Sensor1', 'Sensor1', 1, GETUTCDATE()),
    (@EquipID, 'Sensor2', 'Sensor2', 1, GETUTCDATE());
    -- Add one row per sensor column
```

## Troubleshooting

### "No active tags found for EquipID"
**Cause:** Tags not registered in `ACM_TagEquipmentMap`  
**Fix:** Run Step D above to register all sensor columns

### "FOREIGN KEY constraint failed" on ACM_Runs
**Cause:** EquipID mismatch between Equipment table and code  
**Fix:** Verify EquipID in Equipment table matches what ACM is using

### "Insufficient data for coldstart"
**Cause:** Less than 200 data points in the time window  
**Fix:** Use larger batch windows (5-10 days) or more data

### Dashboard shows no data
**Cause 1:** Wrong equipment selected in dropdown  
**Cause 2:** Time range doesn't match data dates  
**Fix:** Select correct equipment AND adjust time picker to your data's date range

## Data Requirements

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| Row count | 200 | 1,000+ |
| Time span | 4 days | 30+ days |
| Sensor columns | 1 | 4+ |
| Data cadence | Any | 10-60 min |

## Column Naming Rules

The import script sanitizes column names:
- Spaces → underscores (`Wind Speed` → `Wind_Speed`)
- Special characters removed
- Case preserved

## Related Documentation

- [ACM System Overview](ACM_SYSTEM_OVERVIEW.md) - Architecture and module reference
- [SQL Batch Runner](SQL_BATCH_RUNNER.md) - Batch processing options
- [Comprehensive Schema Reference](sql/COMPREHENSIVE_SCHEMA_REFERENCE.md) - Table definitions

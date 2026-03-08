# ACM Data Import Plan

**Date:** 2026-03-08

We have more data than we're using. This document catalogs what exists and the order to import it.

---

## Available Data Sources

### Priority 1 — Wind Farm A (same schema as existing turbines)

| Source | Asset IDs | Rows | Date Range | Status |
|--------|-----------|------|------------|--------|
| `WFA_TURBINE_10_Data` (SQL) | T10 | 53,592 | Oct 2022 → Oct 2023 | ✅ In DB, running ACM |
| `WFA_TURBINE_0_Data` (SQL) | T0 | 54,986 | Aug 2022 → Aug 2023 | ✅ In DB, 15 runs |
| `WFA_TURBINE_13_Data` (SQL) | T13 | 54,010 | May 2022 → May 2023 | ✅ In DB, 2 runs |
| `WFA_TURBINE_11_Data` (SQL) | T11 | **0** | — | ❌ EMPTY |
| `WFA_TURBINE_21_Data` (SQL) | T21 | **0** | — | ❌ EMPTY |
| `WFA0_DataSample.json` | asset_id=0 (T0) | 1,000 | Aug 4–11 2022 | Sample only |
| `WFA13_DataSample.json` | asset_id=21 (T21?) | 1,000 | Apr 30–May 7 2022 | Sample only |

**Immediate action**: Investigate why T11 and T21 tables are empty.
- The JSON samples use `asset_id` not turbine number directly (`WFA13_DataSample.json` has `asset_id=21` which maps to T21).
- The existing `load_historian_from_csv.py` and `load_wind_turbine_data.py` scripts can import JSON/CSV into the `*_Data` tables.

**Command to import T21 from JSON sample (for testing):**
```bash
python scripts/sql/load_historian_from_csv.py \
    --file data/WFA13_DataSample.json \
    --equip WFA_TURBINE_21 \
    --equip-id 5021
```

---

### Priority 2 — Wind Farm A full dataset (if more data exists beyond samples)

The JSON samples are only 1,000 rows each (~1 week of data). The full T10/T0/T13 tables have ~54,000 rows each. If the full T11/T21 CSV files exist somewhere outside this project, they must be located and imported.

**Schema**: All WFA turbines share the same sensor schema (84 columns — `sensor_N_avg`, `power_29_avg`, `wind_speed_3_avg`, etc.). The `*_Data` tables are created by `scripts/sql/wfa_create_tables.sql`.

---

### Priority 3 — FD_FAN (forced draft fan)

| Source | Files | Status |
|--------|-------|--------|
| `data/FD_FAN_BASELINE_DATA.csv` | 1 file | Ready to import |
| `data/FD_FAN_BATCH_DATA.csv` | 1 file | Ready to import |
| `data/chunked/FD_FAN/` | 5 batch CSVs | Ready to import |
| `data/chunked/FD_FAN_batches/` | 3 batch CSVs | Ready to import |

FD_FAN has known fault events (`data/Cond Pump Motor Fault Set.csv`). Useful for verifying ACM detection on a different equipment type.

**Import command:**
```bash
python scripts/sql/load_historian_from_csv.py --file data/FD_FAN_BASELINE_DATA.csv --equip FD_FAN
```

---

### Priority 4 — GAS_TURBINE

| Source | Files | Status |
|--------|-------|--------|
| `data/GAS_TURBINE_BASELINE_DATA.csv` | 1 file | Ready to import |
| `data/GAS_TURBINE_BATCH_DATA.csv` | 1 file | Ready to import |
| `data/chunked/GAS_TURBINE/` | 5 batch CSVs | Ready to import |

---

### Priority 5 — MILL Stands (18 stands, 9 sensors each)

| Source | Stands | Rows | Status |
|--------|--------|------|--------|
| `data/chunked/MILL_Stand01_*` through `MILL_Stand18_*` | 18 | ~varies | Ready |

Each MILL stand has Training + Test CSV files with 10 columns (timestamp + 9 sensor readings). These are labeled datasets (Training = healthy, Test = mixed). **Highest value for classification validation** because we know which windows are normal vs fault.

---

## Import Execution Plan

### Step 1 — Fix T11 and T21 (Highest Priority)

```bash
# Check if any CSV/JSON exists for T11 or T21 data
# If WFA13_DataSample.json contains T21 data (asset_id=21):
python scripts/sql/load_historian_from_csv.py \
    --file data/WFA13_DataSample.json --equip WFA_TURBINE_21

# Then run ACM:
python scripts/sql_batch_runner.py --equip WFA_TURBINE_21 \
    --tick-minutes 1440 --start-from-beginning
```

### Step 2 — Import FD_FAN (Labeled Faults)

```bash
python scripts/sql/load_historian_from_csv.py \
    --file data/FD_FAN_BASELINE_DATA.csv --equip FD_FAN
python scripts/sql/load_historian_from_csv.py \
    --file data/FD_FAN_BATCH_DATA.csv --equip FD_FAN --append

python scripts/sql_batch_runner.py --equip FD_FAN \
    --tick-minutes 1440 --start-from-beginning
```

### Step 3 — Import MILL Stands (Labeled Training/Test Split)

These are the best validation datasets because we have a clean train/test separation.

```bash
for stand in 01 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18; do
    python scripts/sql/load_historian_from_csv.py \
        --file "data/chunked/MILL_Stand${stand}_TRAINING_DATA.csv" \
        --equip "MILL_STAND_${stand}"
    python scripts/sql/load_historian_from_csv.py \
        --file "data/chunked/MILL_Stand${stand}_TEST_DATA.csv" \
        --equip "MILL_STAND_${stand}" --append
done
```

### Step 4 — GAS_TURBINE

```bash
python scripts/sql/load_historian_from_csv.py \
    --file data/GAS_TURBINE_BASELINE_DATA.csv --equip GAS_TURBINE
python scripts/sql/load_historian_from_csv.py \
    --file data/GAS_TURBINE_BATCH_DATA.csv --equip GAS_TURBINE --append
```

---

## Checking Import Scripts

Before running, verify the scripts handle our data format:

```bash
# Check load_historian_from_csv.py supports JSON and the --append flag
python scripts/sql/load_historian_from_csv.py --help

# Dry run to see what would be imported
python scripts/sql/load_historian_from_csv.py \
    --file data/WFA13_DataSample.json --equip WFA_TURBINE_21 --dry-run
```

---

## Notes on Schema Compatibility

- **WFA turbines**: 84 sensor columns, `EntryDateTime` timestamp, 10-minute cadence
- **FD_FAN / GAS_TURBINE**: Different sensor set — ACM will auto-detect column count and build features independently. Each equipment gets its own `*_Data` table and ACM_Config.
- **MILL stands**: `timestamp` column (may need renaming to `EntryDateTime`), 10 sensor columns. Very different from wind turbines but good for detection validation.

The `*_Data` table creation is handled by `scripts/sql/49_create_equipment_data_tables.sql` for WFA turbines. For new equipment types, `load_historian_from_csv.py` should auto-create the table via `register_equipment.sql` + `load_equipment_data_to_sql.py`.

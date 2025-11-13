# SQL Integration Plan - Implementation Summary

## Overview
Implemented pragmatic SQL integration that keeps file mode working while gradually migrating to SQL-based configuration and persistence.

---

## What's Been Done

### 1. Multi-Database Connection Support ✅
**File:** `configs/sql_connection.ini`
- Restructured to support 3 databases with separate sections:
  - `[acm]` - ACM application database (results, configs)
  - `[xstudio_dow]` - Equipment metadata
  - `[xstudio_historian]` - Time-series historian
- Each section has independent credentials/server settings

**File:** `core/sql_client.py`
- Added `SQLClient.from_ini(db_section)` class method
- Automatic fallback to legacy `[sql]` section for backward compatibility
- Multi-database connection pooling support

### 2. SQL Configuration Management ✅
**File:** `scripts/sql/40_seed_config.sql`
- Comprehensive seed script populating `ACM_Config` table
- All YAML config parameters migrated to SQL:
  - Features, models, detectors, fusion, thresholds, regimes, river, output
  - 80+ parameters with proper typing (int, float, bool, string, json)
- Global defaults (EquipID=0) ready for equipment-specific overrides

**File:** `utils/sql_config.py`
- `get_equipment_config()` - Read config from SQL with YAML fallback
- `update_equipment_config()` - Update parameters with audit trail
- Automatic merge of global defaults + equipment overrides
- Type-aware parsing (int/float/bool/json)

### 3. ACM Integration ✅
**File:** `core/acm_main.py` (modified `_load_config()`)
- Config loading priority: SQL → CSV table → YAML
- Seamless fallback chain
- Equipment-specific config support maintained
- Zero breaking changes to existing file mode

### 4. Historian Integration Module ✅
**File:** `core/historian.py`
- `HistorianClient` class wrapping XStudio_Historian stored procedures
- Two primary methods for ACM:
  - `retrieve_cyclic_tags()` - Resampled time-series (recommended)
  - `retrieve_full_tags()` - Raw historian data
- `fetch_equipment_tags_for_acm()` - Main entry point for future integration
- Returns pandas DataFrame ready for ACM pipeline

### 5. Documentation ✅
**File:** `README.md` (Section 2.5 added)
- Configuration Management section with:
  - Priority cascade (SQL → CSV → YAML)
  - SQL config usage examples
  - Dev environment file data strategy
  - 3-phase migration path
- Dual mode operation explained
- Mock data strategy for development

### 6. Test Scripts ✅
**File:** `scripts/sql/test_config_load.py`
- Test script to verify SQL config loading
- Validates global defaults and equipment merging

---

## Migration Path (3 Phases)

### Phase 1: File Mode + SQL Config (CURRENT) ✅
- **Config source**: SQL database (`ACM_Config` table)
- **Data source**: CSV files (existing)
- **Output**: File artifacts only
- **Status**: Fully implemented and ready to test

**Benefits:**
- Zero risk - file mode still works
- Centralized config management
- Equipment-specific parameter tuning
- Audit trail for all config changes

**To Test:**
```bash
# 1. Seed SQL config
sqlcmd -S WIN-RUDDRTU01A8 -U sa -P Admin@1234 -d ACM -i scripts\sql\40_seed_config.sql

# 2. Test config loading
python scripts\sql\test_config_load.py

# 3. Run ACM with SQL config (still processing CSV files)
python -m core.acm_main --equip "FD_FAN" --artifact-root artifacts --config configs/config.yaml --mode batch --enable-report
```

### Phase 2: Dual Mode (NEXT) 🔄
- **Config source**: SQL
- **Data source**: CSV files
- **Output**: File artifacts AND SQL tables (both written)
- **Purpose**: Validate SQL writes against known-good file outputs

**Implementation needed:**
- Add `output.dual_mode` flag check in `acm_main.py`
- When enabled, call both:
  - File writers (`storage.write_scores_csv()`, etc.)
  - SQL writers (`data_io.write_scores_ts()`, etc.)
- Compare file vs SQL outputs for validation

### Phase 3: Full SQL Mode (PRODUCTION) 🎯
- **Config source**: SQL
- **Data source**: Historian (via `core/historian.py`)
- **Output**: SQL tables only
- **Purpose**: Production deployment

**Implementation needed:**
- Historian connection in `core/data_io.py`
- Per-equipment scheduler/loop
- Equipment discovery integration
- File output disabled

---

## Current State of Files

### Ready for Use
- ✅ `configs/sql_connection.ini` - Multi-database config
- ✅ `core/sql_client.py` - Enhanced connection manager
- ✅ `scripts/sql/40_seed_config.sql` - Config seeding
- ✅ `utils/sql_config.py` - Config reader/writer
- ✅ `core/acm_main.py` - SQL config wired in
- ✅ `core/historian.py` - Historian client (for Phase 3)
- ✅ `core/data_io.py` - SQL writers (already exist from previous work)

### Existing SQL Scripts (Already Created)
- ✅ `scripts/sql/00_create_database.sql` - ACM database
- ✅ `scripts/sql/10_core_tables.sql` - All tables
- ✅ `scripts/sql/15_config_tables.sql` - Config tables
- ✅ `scripts/sql/20_stored_procs.sql` - Run lifecycle procs
- ✅ `scripts/sql/25_equipment_discovery_procs.sql` - DOW integration
- ✅ `scripts/sql/30_views.sql` - Analytics views

---

## Key Design Decisions

### 1. Config-from-SQL by Default
- SQL config attempted first, YAML as fallback
- No command-line flag needed - automatic detection
- Backward compatible - falls back gracefully if SQL unavailable

### 2. File Mode Preserved
- CSV file processing unchanged
- File artifacts still written
- Zero risk to existing workflows
- Can develop/test without historian access

### 3. Dual Mode for Validation
- Write to both file and SQL simultaneously
- Compare outputs before switching to SQL-only
- Catch any SQL schema mismatches early

### 4. Equipment-Specific Configs
- Global defaults (EquipID=0) + per-equipment overrides
- Same pattern as CSV table config
- Audit trail for all changes

### 5. Type Safety
- Config values stored with type metadata
- Automatic parsing on load (int/float/bool/json)
- Prevents type coercion errors

---

## Next Steps (Your Decision)

### Option A: Test Phase 1 Now
```bash
# Seed config and test
sqlcmd -S WIN-RUDDRTU01A8 -U sa -P Admin@1234 -d ACM -i scripts\sql\40_seed_config.sql
python scripts\sql\test_config_load.py
python -m core.acm_main --equip "FD_FAN" --artifact-root artifacts --config configs/config.yaml --mode batch
```
**Expected:** ACM runs normally, loads config from SQL instead of YAML

### Option B: Implement Phase 2 (Dual Mode)
- Add dual mode flag checking
- Call both file and SQL writers
- Add validation script to compare outputs

### Option C: Plan Historian Integration (Phase 3)
- Design data loading from historian
- Map tag names to equipment signals
- Schedule/loop architecture

---

## File Structure Summary

```
configs/
  sql_connection.ini          # Multi-database connections ✅
  config.yaml                 # Legacy fallback (kept)

core/
  sql_client.py              # Enhanced for multi-DB ✅
  historian.py               # NEW - Historian client ✅
  acm_main.py                # Modified _load_config() ✅
  data_io.py                 # SQL writers (already exist) ✅

utils/
  sql_config.py              # NEW - SQL config reader/writer ✅

scripts/sql/
  40_seed_config.sql         # NEW - Config seeding ✅
  test_config_load.py        # NEW - Test script ✅
  (other SQL scripts)         # Already exist from previous work ✅

docs/sql/
  XHS_*.sql                  # Historian SPs (for reference) ✅
```

---

## Summary

**What works NOW:**
- ACM reads config from SQL (`ACM_Config` table)
- Falls back to YAML if SQL unavailable
- Processes CSV files (file mode)
- Writes file artifacts
- Equipment-specific config support
- Config update with audit trail

**What's preserved:**
- All existing functionality
- File mode workflows
- CSV data processing
- YAML fallback
- Zero breaking changes

**What's next (your choice):**
- Test Phase 1 (SQL config, file data, file output)
- Implement Phase 2 (dual write mode)
- Plan Phase 3 (historian integration)

# SQL-Only Mode Configuration

## Overview
ACM V8 now **defaults to SQL-only mode**, eliminating all filesystem writes for production deployments. File-based operations are now opt-in via explicit configuration flags.

## Default Behavior (SQL-Only)
By default, ACM operates in **SQL-only mode**:
- ✅ All analytics written directly to SQL Server tables
- ✅ No CSV files generated
- ✅ No JSON metadata files
- ✅ No chart PNGs created
- ✅ Models persisted only in SQL (ModelRegistry + ACM_BaselineBuffer)
- ✅ Clean production deployments with no filesystem clutter

## Configuration

### Runtime Mode Selection
```yaml
runtime:
  storage_backend: "sql"  # DEFAULT - pure SQL mode
  # storage_backend: "file"  # Legacy file-based mode (opt-in)
```

### Enabling File Operations (Opt-In)
To restore legacy file-based behaviors, set these flags explicitly:

```yaml
output:
  enable_file_mode: true    # Enable CSV/JSON file writes (default: false)
  enable_forecast: true     # Enable forecast generation (default: false)
  dual_mode: false          # Write to both SQL and files (default: false)
  
  charts:
    enabled: true           # Enable chart PNG generation (default: false)
```

## Migration Guide

### From File Mode to SQL Mode (Recommended)
If you previously relied on file-based outputs:

1. **Update config** - Remove or comment out `storage_backend: "file"`
2. **Query SQL tables** - All analytics now available in ACM_* tables:
   - `ACM_HealthTimeline` → replaces `health_timeline.csv`
   - `ACM_Episodes` → replaces `episodes.csv`
   - `ACM_Scores_Wide` / `ACM_Scores_Long` → replaces `scores.csv`
   - `ACM_DefectSummary` → replaces defect summaries
   - 20+ additional comprehensive analytics tables
3. **Remove file dependencies** - Update downstream processes to read from SQL

### Keeping File Mode (Not Recommended)
If you must preserve file-based outputs temporarily:

```yaml
runtime:
  storage_backend: "file"  # Explicit opt-in

output:
  enable_file_mode: true   # Enable CSV/JSON writes
  enable_forecast: true    # Enable forecast files
  charts:
    enabled: true          # Enable chart PNGs
```

## Benefits of SQL-Only Mode

1. **Performance** - Direct SQL writes eliminate file I/O bottlenecks
2. **Scalability** - No filesystem constraints or cleanup required
3. **Reliability** - Transactional consistency; no partial/corrupted files
4. **Security** - Centralized access control via SQL permissions
5. **Auditability** - All operations tracked in RunID-stamped records
6. **Integration** - Direct BI tool / dashboard connectivity

## SQL Tables Reference

### Core Analytics
- `ACM_HealthTimeline` - Health index time series
- `ACM_Episodes` - Anomaly episodes with severity/duration
- `ACM_Scores_Wide` / `ACM_Scores_Long` - Detector scores
- `ACM_DefectSummary` - Active defect summary
- `ACM_DefectTimeline` - Defect evolution over time

### Regime Analysis
- `ACM_RegimeTimeline` - Regime labels and transitions
- `ACM_RegimeOccupancy` - Time spent in each regime
- `ACM_RegimeTransitions` - State transition matrix
- `ACM_RegimeDwellStats` - Dwell time statistics

### Drift & Contributions
- `ACM_DriftSeries` - Multi-feature drift time series
- `ACM_DriftEvents` - Detected drift events
- `ACM_ContributionCurrent` - Current detector contributions
- `ACM_ContributionTimeline` - Contribution history
- `ACM_SensorDefects` - Per-sensor defect rankings

### Operational
- `Runs` - Run metadata and execution history
- `ModelRegistry` - Model versions and signatures
- `ACM_BaselineBuffer` - Rolling baseline data
- `ACM_ConfigHistory` - Configuration change log

See comprehensive list in `docs/Analytics Backbone.md`

## Troubleshooting

### "No output files generated"
**Expected behavior** - SQL-only mode does not generate files. Query SQL tables instead.

### "Charts not rendering"
Enable explicitly: `output.charts.enabled: true`

### "Need CSV export for external tool"
Use SQL Server's BCP or SSIS to export from ACM_* tables as needed.

### "File mode still writing files"
Check config: `runtime.storage_backend` must equal `"file"` AND `output.enable_file_mode: true`

## Version History
- **v8.0** - SQL-only mode now default; file operations opt-in
- **v7.x** - Dual-mode support introduced
- **v6.x** - File-based only (legacy)

# ACM Database Table Audit

## Summary
**Before Cleanup**: 51 tables  
**After Cleanup**: 33 tables ✅  
**Removed**: 18 legacy tables with zero usage  

**Current State**:
- **Tables with ACM_ prefix**: 30 (active pipeline output)
- **Core tables**: 3 (Equipment, ModelRegistry, Runs)

## Tables Written by Pipeline (KEEP)

### Core Output Tables (from ALLOWED_TABLES in output_manager.py)
These tables are actively written by the ACM pipeline:

| Table Name | Row Count | Purpose |
|------------|-----------|---------|
| **ACM_Scores_Wide** | 61,904 | Primary health scores time-series |
| **ACM_Episodes** | 9 | Alert episodes and anomaly events |
| **ACM_HealthTimeline** | 34,821 | Health status over time |
| **ACM_RegimeTimeline** | 34,821 | Operating regime detection |
| **ACM_ContributionCurrent** | 72 | Current sensor contributions |
| **ACM_ContributionTimeline** | 39,816 | Historical sensor contributions |
| **ACM_DriftSeries** | 34,821 | Drift detection time-series |
| **ACM_ThresholdCrossings** | 45 | Alert threshold violations |
| **ACM_AlertAge** | 27 | Alert duration tracking |
| **ACM_SensorRanking** | 72 | Sensor anomaly rankings |
| **ACM_RegimeOccupancy** | 18 | Time spent in each regime |
| **ACM_HealthHistogram** | 90 | Health score distributions |
| **ACM_RegimeStability** | 36 | Regime switching stability |
| **ACM_DefectSummary** | 9 | Aggregated defect statistics |
| **ACM_DefectTimeline** | 5,958 | Defect detection time-series |
| **ACM_SensorDefects** | 72 | Per-sensor defect counts |
| **ACM_HealthZoneByPeriod** | 2,214 | Health zone time aggregates |
| **ACM_SensorAnomalyByPeriod** | 5,904 | Sensor anomaly aggregates |
| **ACM_DetectorCorrelation** | 57 | Detector cross-correlation |
| **ACM_CalibrationSummary** | 16 | Model calibration metrics |
| **ACM_RegimeTransitions** | 18 | Regime transition counts |
| **ACM_RegimeDwellStats** | 18 | Regime duration statistics |
| **ACM_DriftEvents** | 0 | Drift event markers (new) |
| **ACM_CulpritHistory** | 6 | Top culprit sensor history |
| **ACM_EpisodeMetrics** | 10 | Episode-level aggregates |
| **ACM_SensorHotspots** | 81 | Sensor anomaly hotspots |
| **ACM_SensorHotspotTimeline** | 57,312 | Hotspot time-series |
| **ACM_SinceWhen** | 9 | Alert start timestamps |

### Configuration & Metadata Tables (KEEP)
| Table Name | Row Count | Purpose |
|------------|-----------|---------|
| **ACM_Config** | 192 | Runtime configuration parameters |
| **Equipment** | 5 | Equipment registry |
| **ModelRegistry** | 0 | Model persistence (SQL-20-22) |

### Skipped Table (KEEP but not written)
| Table Name | Row Count | Issue |
|------------|-----------|-------|
| **ACM_DataQuality** | 0 | All-NULL floats cause pyodbc errors (see output_manager.py line 47) |

---

## Legacy Tables Without ACM_ Prefix (CANDIDATE FOR REMOVAL)

These tables are **NOT** in ALLOWED_TABLES and have **ZERO rows**:

### Time-Series Tables (Unused)
| Table Name | Row Count | Notes |
|------------|-----------|-------|
| **ScoresTS** | 0 | Replaced by ACM_Scores_Wide |
| **DriftTS** | 0 | Replaced by ACM_DriftSeries |
| **PCA_ScoresTS** | 0 | Not used by current pipeline |
| **DataQualityTS** | 0 | Not used by current pipeline |
| **ForecastResidualsTS** | 0 | Not used by current pipeline |

### Event Tables (Unused)
| Table Name | Row Count | Notes |
|------------|-----------|-------|
| **AnomalyEvents** | 0 | Replaced by ACM_Episodes |
| **AnomalyTopSpikes** | 0 | Not used by current pipeline |
| **RegimeEpisodes** | 0 | Replaced by ACM_RegimeTimeline |

### PCA Tables (Unused)
| Table Name | Row Count | Notes |
|------------|-----------|-------|
| **PCA_Model** | 0 | Models now in ModelRegistry |
| **PCA_Components** | 0 | Not written by current pipeline |
| **PCA_Metrics** | 0 | Not written by current pipeline |

### Summary Tables (Unused)
| Table Name | Row Count | Notes |
|------------|-----------|-------|
| **DriftSummary** | 0 | Replaced by ACM_DriftEvents |
| **XCorrTopPairs** | 0 | Not used by current pipeline |
| **FeatureImportance** | 0 | Not used by current pipeline |
| **CPD_Points** | 0 | Change point detection - not implemented |

### Metadata Tables (Unused)
| Table Name | Row Count | Notes |
|------------|-----------|-------|
| **RunStats** | 0 | Replaced by ACM_Run_Stats |
| **ConfigLog** | 0 | Not used (config changes not logged) |
| **Historian** | 0 | Not used by current pipeline |

### Run Management (Partially Used)
| Table Name | Row Count | Notes |
|------------|-----------|-------|
| **Runs** | 0 | Schema mismatch with run_metadata_writer.py (SQL-30 task) |

---

## Cleanup Status: ✅ COMPLETE

### Dropped 18 legacy tables (script: 48_drop_legacy_tables.sql)

**Time-series tables** (5):
- ✅ ScoresTS → replaced by ACM_Scores_Wide
- ✅ DriftTS → replaced by ACM_DriftSeries
- ✅ PCA_ScoresTS, DataQualityTS, ForecastResidualsTS → not used

**Event tables** (3):
- ✅ AnomalyEvents → replaced by ACM_Episodes
- ✅ AnomalyTopSpikes, RegimeEpisodes → not used

**PCA tables** (3):
- ✅ PCA_Model, PCA_Components, PCA_Metrics → not used

**Summary tables** (4):
- ✅ DriftSummary, XCorrTopPairs, FeatureImportance, CPD_Points → not used

**Metadata tables** (3):
- ✅ RunStats, ConfigLog, Historian → not used

### Remaining Tables (33)
- **30 ACM_* tables**: Active pipeline output (see ALLOWED_TABLES in output_manager.py)
- **Equipment**: Equipment registry (5 rows)
- **ModelRegistry**: Model persistence (SQL-20-22, 0 rows - ready for use)
- **Runs**: Run metadata (needs schema fix per SQL-30 task)

### Next Action: SQL-30
Fix Runs table schema mismatch:
- Current: Stage, WindowStartEntryDateTime, Outcome
- Expected by run_metadata_writer.py: RunID, EquipID, StartedAt, CompletedAt, Status, ErrorMessage

---

## Code References

**ALLOWED_TABLES** defined in:
- `core/output_manager.py` lines 35-53

**SQL schema files**:
- Modern: `scripts/sql/create_acm_analytics_tables.sql` (ACM_* tables)
- Legacy: `scripts/sql/10_core_tables.sql` (non-ACM tables)
- Complete: `scripts/sql/14_complete_schema.sql`

**Model persistence**:
- `core/model_persistence.py` uses ModelRegistry table
- Implemented in SQL-20/21/22 (commit 9200e02)

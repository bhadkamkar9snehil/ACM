# ACM Task Consolidation Summary

**Date:** 2025-11-13  
**Purpose:** Consolidate all audit findings and to-do items into a single master document

---

## Documents Consolidated

### Primary Target Document
**`Task Backlog.md`** (root directory) - **MASTER CONSOLIDATED BACKLOG**
- Most comprehensive and up-to-date
- Now includes 61 active tasks (up from 25)
- Added 36 new tasks from audit reviews

### Audit Documents Reviewed & Consolidated

1. **State Management Audit ACM Main.md** (root)
   - **Tasks Added:** ARCH-01 through ARCH-04 (4 tasks)
   - **Section:** 10.1 - State Management Improvements
   - **Key Issues:** 60+ stateful variables, temporal coupling, missing state guards

2. **Regime Audit.md** (root)
   - **Tasks Added:** REG-09 through REG-16 (8 tasks)
   - **Section:** 9 - Regime Clustering Enhancements
   - **Key Issues:** K=1 fallback, PCA preprocessing, smoothing, transient detection

3. **Forecast Audit.md** (root)
   - **Tasks Added:** FCST-01 through FCST-14 (14 tasks)
   - **Section:** 8 - Forecast & AR(1) Model
   - **Key Issues:** Growing forecast variance (CRITICAL), warm start bias, AR(1) documentation

4. **docs/Comprehensive Audit of acm main.md**
   - **Tasks Added:** QUAL-01 through QUAL-03 (3 tasks)
   - **Section:** 10.2 - Code Quality Fixes
   - **Key Issues:** God function complexity, O(n²) fallback, SQL connection limits

### Supporting Documents

- **Task Backlog.md** (root) - SQL integration focus, added cross-reference note
- **docs/To Do.md** - Marked as DEPRECATED with reference to root Task Backlog.md

---

## New Tasks Summary

### Critical Priority (3 tasks)
- FCST-01: Implement growing forecast variance for AR(1)
- FCST-02: Fix warm start bias in AR(1) scoring
- FCST-03: Exclude first residual from std dev calculation

### High Priority (15 tasks)
- 6 Forecast tasks (FCST-04 through FCST-06)
- 5 Regime tasks (REG-09, REG-10, REG-12, REG-13, REG-14)
- 2 Architecture tasks (ARCH-02, ARCH-03)
- 2 Quality tasks (QUAL-01, QUAL-02)

### Medium Priority (15 tasks)
- 5 Forecast tasks (FCST-07 through FCST-11)
- 3 Regime tasks (REG-08, REG-11, REG-15, REG-16)
- 2 Architecture tasks (ARCH-01, ARCH-04)
- 1 Quality task (QUAL-03)

### Low Priority (3 tasks)
- 3 Forecast tasks (FCST-12 through FCST-14)

---

## Consolidation Actions Taken

1. ✅ **Updated Task Backlog.md** with new sections:
   - Section 8: Forecast & AR(1) Model
   - Section 9: Regime Clustering Enhancements
   - Section 10: Architecture & Code Quality

2. ✅ **Updated Progress Summary**:
   - Active Tasks: 25 → 61
   - Added consolidation notes
   - Updated last modified date

3. ✅ **Added Consolidation Notices** to audit documents:
   - State Management Audit ACM Main.md
   - Regime Audit.md
   - Forecast Audit.md
   - docs/Comprehensive Audit of acm main.md

4. ✅ **Updated Supporting Documents**:
   - Task Backlog.md - Added note about master document
   - docs/To Do.md - Marked as DEPRECATED

---

## Benefits of Consolidation

1. **Single Source of Truth**: All tasks tracked in one master document
2. **No Duplication**: Eliminated redundant task tracking across multiple files
3. **Clear Priorities**: All tasks have assigned priorities (Critical → Low)
4. **Traceability**: Each task references its source audit document
5. **Status Tracking**: Clear status (Done/Pending/Planned/Deferred) for all tasks
6. **Better Organization**: Tasks grouped by functional area

---

## Recommended Next Steps

### Immediate (Critical Tasks)
1. **FCST-01**: Fix forecast variance calculation (CRITICAL - statistically incorrect)
2. **FCST-02**: Fix AR(1) warm start bias (causes false alarms)
3. **FCST-03**: Fix residual std dev calculation (biases uncertainty estimates)

### Short Term (High Priority)
1. Review and prioritize the 15 high-priority tasks
2. Address REG-09 through REG-14 (regime clustering improvements)
3. Implement ARCH-02 and ARCH-03 (pipeline architecture improvements)
4. Fix QUAL-01 and QUAL-02 (code quality and performance)

### Medium Term
1. Complete remaining forecast improvements (FCST-07 through FCST-11)
2. Finish regime enhancements (REG-15, REG-16)
3. Begin architecture refactoring (ARCH-01, ARCH-04)

---

## Document Structure

The consolidated `Task Backlog.md` now contains:

1. **Progress Summary** - Overall metrics and recent completions
2. **Sections 1-7** - Existing task categories (Analytics, Model Management, etc.)
3. **Section 8** - **NEW:** Forecast & AR(1) Model (14 tasks)
4. **Section 9** - **NEW:** Regime Clustering Enhancements (8 tasks)
5. **Section 10** - **NEW:** Architecture & Code Quality (7 tasks)
6. **Appendices** - Train/Test terminology cleanup, performance analysis, etc.

---

## Maintenance Guidelines

1. **Single Update Point**: Update only `Task Backlog.md` for task tracking
2. **Audit Documents**: Keep audit documents as historical reference, don't update
3. **Completed Tasks**: Move from Pending → Done with completion date
4. **New Audits**: Add new sections to `Task Backlog.md` following existing format
5. **Regular Reviews**: Update progress summary monthly

---

## 2025-11-14 Repository Delta Audit (SQL + Grafana)

This section records a light‑weight follow‑up audit after the first full consolidation, focusing on SQL integration outputs and Grafana dashboards.

### A. SQL Outputs & Run Logging

- **Status:** SQL integration still ~89% complete, but core dual‑write path is functioning correctly for FD_FAN and GAS_TURBINE.
- **Evidence:** `gas_turbine_test.log` and `fd_fan_coldstart.log` show successful inserts into all key analytics tables:
  - `ACM_HealthTimeline`, `ACM_RegimeTimeline`, `ACM_ContributionCurrent`, `ACM_ContributionTimeline`,
    `ACM_SensorHotspots`, `ACM_SensorHotspotTimeline`, `ACM_HealthZoneByPeriod`, `ACM_SensorAnomalyByPeriod`,
    `ACM_DefectSummary`, `ACM_DefectTimeline`, `ACM_SensorDefects`, `ACM_EpisodeMetrics`, `ACM_Episodes`, etc.
- **Run scoping:** Many Grafana queries previously ignored `RunID` and mixed historical runs. Panels for health, contributions, defect timeline, drift and anomaly rates have now been updated to consistently scope to the **latest RunID per EquipID** where appropriate.

### B. Grafana Dashboards & SQL Queries

- Created a new **ACM Operator View** dashboard (`grafana_dashboards/acm_operator_dashboard.json`) that reuses the same SQL tables but presents a simplified, run‑scoped story for operators.
- Tightened and documented queries in `grafana_dashboards/docs/SQL_QUERIES_REFERENCE.md`:
  - Clarified detector vs sensor semantics (`DetectorType` vs `SensorName`).
  - Added explicit `RunID` filters for “current/latest run” panels.
  - Pivoted `ACM_HealthZoneByPeriod` for stack‑bar views (GOOD/WATCH/ALERT per period).
  - Documented the `Detector Explanations` panel built from `ACM_SensorDefects` + `ACM_DetectorMetadata`.
- Added `scripts/sql/56_create_detector_metadata.sql` to define `ACM_DetectorMetadata` (per‑family explanations and operator hints).

### C. Files Archived as Non‑Essential

The following files were moved to `artifacts/archive/` as **non‑essential runtime artefacts** (logs/HTML exports). They can be deleted later without affecting code:

- Root logs / outputs:
  - `batch_run_fd_fan.log`, `batch_run_gas_turbine.log`
  - `fd_fan_coldstart.log`, `gas_turbine_final_test.log`, `gas_turbine_test.log`, `pipeline_run.log`
  - `cond_pump_output.txt`, `test_output.txt`
- HTML exports (redundant with markdown):
  - `docs/SQL_INTEGRATION_PLAN.html`
  - `docs/SQL_MODE_STATUS.html`
  - `Task Backlog.html`

These were left in place under `artifacts/archive/` for traceability; the canonical sources are the corresponding `.md` documents and the SQL tables.

### D. Open Follow‑ups (no new IDs added)

Rather than introducing new task IDs, the following should be tracked against existing sections in `Task Backlog.md`:

- Verify `ACM_DriftEvents` schema and populate it with rich drift event data (timestamps, values) so Grafana drift annotations become meaningful.
- Decide on a final visual for detector correlation (table with colored cells vs heatmap) and wire it to `ACM_DetectorCorrelation`.
- Consider adding per‑sensor anomaly‑rate aggregation if operators need a true “sensor × time” anomaly heatmap (new table derived from existing outputs).

No additional task IDs were added to the master backlog; these items can be recorded under the existing SQL/Visualization or Architecture sections as needed.

---

**Consolidation Completed:** 2025-11-13  
**Consolidated By:** GitHub Copilot Agent  
**Total Tasks Added:** 36 (from 4 audit documents)  
**Master Document:** `Task Backlog.md` (root directory)

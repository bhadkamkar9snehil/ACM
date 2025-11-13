# Chart Audit and Improvement Plan

**Date:** 2025-11-10  
**Status:** CRITICAL - Multiple chart reliability issues identified  
**Priority:** HIGH - Charts are primary operator interface

---

## Executive Summary

Comprehensive audit of ACM chart generation revealed **5 critical issues** affecting data integrity and operator trust:

1. **Forecast misalignment** - AR1 predictions disconnected from actual series tail
2. **Episode timestamp loss** - Datetime truncation hides incident onset
3. **OMR narrative overstates risk** - Saturated detector with zeroed fusion weight
4. **Timestamp convention drift** - Mixed ISO Z-suffix and naive local times
5. **Chart-table coupling gaps** - Missing validation between data and visualizations

**Impact:** Operators may misinterpret asset health, miss critical alerts, or distrust system outputs.

---

## Chart Inventory & Status

### Current Chart Generation (Both Assets)

| Chart | Source Table(s) | Status | Issues |
|-------|----------------|--------|--------|
| `contribution_bars.png` | `culprits.jsonl`, `scores.csv` | ⚠️ REVIEW | Needs fusion weight context |
| `defect_dashboard.png` | `defect_summary.csv`, `health_timeline.csv` | BROKEN | GAS_TURBINE shows healthy despite ALERT status |
| `defect_severity.png` | `episodes.csv` | ⚠️ CONDITIONAL | Missing for GAS_TURBINE (no episodes) |
| `detector_comparison.png` | `scores.csv` (detector z-scores) | OK | Validated against source |
| `episodes_timeline.png` | `episodes.csv` | BROKEN | Empty for GAS_TURBINE, timestamp truncation |
| `forecast_overlay.png` | `forecast_confidence.csv`, `scores.csv` | BROKEN | Major misalignment, wrong series |
| `health_distribution_over_time.png` | `health_timeline.csv` | ⚠️ REVIEW | Needs severity bands |
| `health_timeline.png` | `health_timeline.csv` | OK | Validated |
| `omr_contribution_heatmap.png` | `omr_contributions.csv` | MISLEADING | Overstates risk with zeroed weight |
| `omr_timeline.png` | `scores.csv` (omr_z) | MISLEADING | Should be hidden when weight=0 |
| `omr_top_contributors.png` | `omr_contributions.csv` | MISLEADING | Same as heatmap issue |
| `regime_distribution.png` | `scores.csv` (regime_label) | ⚠️ REVIEW | Single regime = not useful |
| `regime_scatter.png` | `scores.csv` | ⚠️ REVIEW | PCA projection may be invalid |
| `sensor_anomaly_heatmap.png` | `sensor_anomaly_by_period.csv` | ⚠️ REVIEW | Needs severity normalization |
| `sensor_daily_profile.png` | `sensor_anomaly_by_period.csv` | ⚠️ REVIEW | WATCH counts dominate |
| `sensor_defect_heatmap.png` | `sensor_defects.csv` | ⚠️ CONDITIONAL | Missing for GAS_TURBINE |

**Legend:**  
- OK - Chart validated against source data  
- ⚠️ REVIEW - Minor issues or context needed  
- BROKEN/MISLEADING - Critical fixes required

---

## Critical Issues (Detailed Analysis)

### ISSUE #1: Forecast Misalignment

**Symptom:** FD_FAN `forecast_overlay.png` shows large upward shift (0.5 → 12) disconnected from series tail.

**Root Cause:**
- AR1 fitted on `mhal_z` with historical mean ~16.36 (`forecast_metrics.csv`)
- Mean inflated by early spikes (Jan 13-30 episode with z>20)
- Last observed values ~0.5, but forecast reverts to mean of 16
- Confidence bands ±17 are unrealistically wide

**Evidence:**
```csv
# forecast_metrics.csv
ar1_phi,ar1_mu,ar1_sigma,series_used
0.9716665756845896,16.360816955566406,8.747004508972168,mhal_z

# scores.csv (last 10 rows)
2013-05-21 08:00:00, mhal_z=0.307
2013-05-21 08:30:00, mhal_z=0.318
2013-05-21 09:00:00, mhal_z=0.362
(avg ~0.3-0.4)

# forecast_confidence.csv (first 10 rows)
2013-05-21 09:30:00, forecast=0.464, ci_lower=-16.68, ci_upper=17.61
2013-05-21 10:00:00, forecast=0.914, ci_lower=-16.23, ci_upper=18.06
...
2013-05-22 09:00:00, forecast=12.243, ci_lower=-4.90, ci_upper=29.39
```

**Impact:** Operators see false alarm projection, lose trust in forecasts.

**Fix Priority:** CRITICAL

**Proposed Solutions:**
1. **Option A (Quick):** Switch forecast series from `mhal_z` to `fused` (more stable)
2. **Option B (Better):** Detrend series before AR1 fit, center predictions
3. **Option C (Best):** Add rolling-window AR1 that ignores outlier periods
4. **Immediate:** Hide forecast chart until fixed, add table `forecast_diagnostics.csv`

**Table Requirements:**
- `forecast_inputs.csv` - last N observed values used for projection
- `forecast_diagnostics.csv` - phi, mu, sigma, train_window, validation_error
- Validate forecast starts from last observed value ±10%

---

### ISSUE #2: Episode Timestamp Truncation

**Symptom:** FD_FAN `episodes.csv` shows `start_ts=2013-01-13` (date only).

**Root Cause:**
- Episode writer strips time component or uses date-only format
- Loses critical onset information for incident investigation

**Evidence:**
```csv
# episodes.csv
episode_id,start_ts,end_ts,duration_s,len,culprits,severity
1,2013-01-13,2013-01-30 15:30:00,1.5246e+06,848,gmm_z,info

# sensor_hotspots.csv shows MaxTimestamp with time
DEMO.SIM.06T32-1_1FD Fan Bearing Temperature,2013-01-24 16:30:00,,28.2387,...
```

**Impact:** 
- Operators cannot pinpoint incident start for log correlation
- Timeline charts show ambiguous start markers
- Severity marked "info" despite z>20 hotspots

**Fix Priority:** CRITICAL

**Proposed Solutions:**
1. Audit episode extraction code (`core/fuse.py` or `core/episode_culprits_writer.py`)
2. Ensure timestamps preserve full datetime with timezone
3. Add severity escalation rule: if any sensor z>10 → severity="critical"
4. Create `episodes_diagnostics.csv` with peak_z, dominant_sensor, escalation_reason

**Table Requirements:**
- `episodes.csv` - full timestamps (YYYY-MM-DD HH:MM:SS)
- `episodes_diagnostics.csv` - metadata explaining severity assignment
- Validate start_ts <= end_ts and duration matches timestamp diff

---

### ISSUE #3: OMR Narrative Overstates Risk

**Symptom:** FD_FAN OMR charts show z-scores 13-78, but fusion weight = 0.

**Root Cause:**
- OMR detector saturated (possibly due to feature scaling issues)
- Auto-tuner zeroed fusion weight (`fusion_metrics.csv`: all quality_score=0.0)
- Charts still generated and imply multivariate collapse

**Evidence:**
```csv
# fusion_metrics.csv
detector_name,weight,quality_score
omr_z,0.12535627464477178,0.0

# scores.csv
2012-12-31 18:00:00, omr_z=13.4486, fused=1.4569
2012-12-31 18:30:00, omr_z=21.9618, fused=0.8504
(OMR high, fused moderate)

# omr_contributions.csv
(All 72 features have similar contributions ~0.5-4.0)
```

**Impact:**
- Operators see alarming OMR heatmaps
- Fused score doesn't reflect OMR → confusion
- Loss of trust in multivariate detection

**Fix Priority:** CRITICAL

**Proposed Solutions:**
1. **Immediate:** Hide OMR charts when fusion weight < 0.05 or quality_score = 0
2. **Short-term:** Add `omr_diagnostics.csv` with calibration status, recommended_weight
3. **Long-term:** Fix OMR feature scaling (center/scale before PLS/Ridge/PCA)
4. Add validation: if weight < 0.05, write "OMR_DISABLED" flag and skip charts

**Table Requirements:**
- `omr_diagnostics.csv` - model_type, n_components, explained_variance, weight_status
- `fusion_quality_report.csv` - per-detector weight, quality, recommendation
- Chart precondition: Only generate OMR visuals if weight >= 0.05 AND quality > 0

---

### ISSUE #4: Timestamp Convention Drift

**Symptom:** Mixed ISO Z-suffix and naive local timestamps across files.

**Root Cause:**
- Despite OUT-04/DEBT-11 "local time everywhere" policy, some writers still emit UTC
- `scores.csv` has `2012-12-31T18:00:00.000000Z` (ISO with Z)
- `forecast_confidence.csv` has `2013-05-21 09:30:00` (naive local)
- Chart overlays misalign when mixing sources

**Evidence:**
```csv
# scores.csv
timestamp,ar1_raw,pca_spe,...
2012-12-31T18:00:00.000000Z,22.4628,413.82,...

# forecast_confidence.csv
timestamp,forecast,ci_lower,ci_upper
2013-05-21 09:30:00,0.46355796894882495,-16.68,...

# health_timeline.csv
Timestamp,HealthIndex,HealthZone,FusedZ
2012-12-31 18:00:00,32.02,ALERT,1.4569
```

**Impact:**
- Overlay charts may shift x-axis (timezone interpretation)
- Operators see misaligned timestamps in cross-chart comparisons
- Violates documented "local time everywhere" policy

**Fix Priority:** CRITICAL

**Proposed Solutions:**
1. Audit all CSV writers in `core/output_manager.py`, `core/forecast.py`
2. Enforce single format: `YYYY-MM-DD HH:MM:SS` (no T, no Z, no microseconds)
3. Add timestamp validation test in post-run QA
4. Update schema.json to document timestamp format

**Table Requirements:**
- All tables use identical timestamp format
- Schema metadata declares timezone policy ("local naive")
- Validation script checks for "T" or "Z" in timestamp columns

---

### ISSUE #5: Chart-Table Coupling Gaps

**Symptom:** Charts generated without validating source data existence/quality.

**Root Cause:**
- No precondition checks before chart generation
- GAS_TURBINE missing 2 charts, but no error/warning in logs
- Charts reference tables that may be empty or malformed

**Evidence:**
- FD_FAN has 16 charts, GAS_TURBINE has 14 (missing defect_severity, sensor_defect_heatmap)
- No logs indicating why charts were skipped
- `episodes.csv` empty for GAS_TURBINE but `episodes_timeline.png` still generated (blank axes)

**Impact:**
- Operators see blank charts without explanation
- Inconsistent chart counts between runs
- Cannot debug missing visualizations

**Fix Priority:** CRITICAL

**Proposed Solutions:**
1. Add chart precondition registry in `core/output_manager.py`
2. Before each chart, validate:
   - Required tables exist
   - Required columns present
   - Minimum row count met
3. Write `chart_generation_log.csv` with chart_name, status, skip_reason
4. Add annotation to blank charts: "No data available (reason)"

**Table Requirements:**
- `chart_generation_log.csv` - chart_name, generated, skip_reason, source_tables
- `chart_quality_report.json` - validation results per chart
- Each chart function returns (success: bool, reason: str)

---

## Improvement Tasks (Prioritized)

### Phase 1: Critical Fixes (Week 1)

| ID | Priority | Task | Module | Estimated Effort |
|----|----------|------|--------|------------------|
| **CHART-01** | Critical | Fix forecast series selection & alignment | `core/forecast.py` | 4h |
| **CHART-02** | Critical | Preserve full episode timestamps | `core/fuse.py`, `core/episode_culprits_writer.py` | 2h |
| **CHART-03** | Critical | Hide OMR charts when weight < 0.05 | `core/output_manager.py` | 2h |
| **CHART-04** | Critical | Enforce uniform timestamp format | All writers | 3h |
| **CHART-05** | Critical | Add chart precondition validation | `core/output_manager.py` | 4h |

**Total Phase 1:** 15 hours

### Phase 2: Enhanced Diagnostics (Week 2)

| ID | Priority | Task | Module | Estimated Effort |
|----|----------|------|--------|------------------|
| **CHART-06** | High | Create `forecast_diagnostics.csv` | `core/forecast.py` | 2h |
| **CHART-07** | High | Create `episodes_diagnostics.csv` | `core/fuse.py` | 2h |
| **CHART-08** | High | Create `omr_diagnostics.csv` | `models/omr.py` | 3h |
| **CHART-09** | High | Create `chart_generation_log.csv` | `core/output_manager.py` | 2h |
| **CHART-10** | High | Create `fusion_quality_report.csv` | `core/fuse.py` | 2h |

**Total Phase 2:** 11 hours

### Phase 3: Chart Enhancements (Week 3)

| ID | Priority | Task | Module | Estimated Effort |
|----|----------|------|--------|------------------|
| **CHART-11** | Medium | Add "No episodes detected" annotation | `core/output_manager.py` | 1h |
| **CHART-12** | Medium | Normalize sensor heatmap by severity | `core/output_manager.py` | 2h |
| **CHART-13** | Medium | Add fusion weight overlay to detector comparison | `core/output_manager.py` | 2h |
| **CHART-14** | Medium | Redesign defect dashboard to reconcile status | `core/output_manager.py` | 4h |
| **CHART-15** | Medium | Add regime quality flag to regime charts | `core/output_manager.py` | 1h |

**Total Phase 3:** 10 hours

### Phase 4: Validation & Testing (Week 4)

| ID | Priority | Task | Module | Estimated Effort |
|----|----------|------|--------|------------------|
| **CHART-16** | Medium | Create automated chart QA script | `scripts/validate_charts.py` | 4h |
| **CHART-17** | Medium | Add unit tests for chart preconditions | `tests/test_charts.py` | 3h |
| **CHART-18** | Medium | Document chart-to-table mapping matrix | `docs/CHART_SPEC.md` | 2h |
| **CHART-19** | Medium | Update README with chart troubleshooting | `README.md` | 1h |
| **CHART-20** | Medium | Validate all charts with both assets | Manual testing | 4h |

**Total Phase 4:** 14 hours

**Total Estimated Effort:** 50 hours (~2 weeks full-time)

---

## New Table Specifications

### 1. `forecast_diagnostics.csv`

**Purpose:** Document forecast model parameters and validation results

**Columns:**
- `series_name` (str) - Which detector stream was forecasted
- `ar1_phi` (float) - Autoregression coefficient
- `ar1_mu` (float) - Series mean
- `ar1_sigma` (float) - Series standard deviation
- `train_window_start` (datetime) - First timestamp in training window
- `train_window_end` (datetime) - Last timestamp in training window
- `train_n_points` (int) - Number of points used for fit
- `last_observed_value` (float) - Final value before forecast starts
- `forecast_start_value` (float) - First predicted value
- `forecast_divergence` (float) - Abs diff between last observed and first forecast
- `validation_mae` (float) - Mean absolute error on holdout set (if available)
- `recommendation` (str) - "VALID" / "DIVERGENT" / "UNSTABLE"

**Validation Rules:**
- `forecast_divergence < 10% of ar1_sigma` → VALID
- `forecast_divergence >= 10% and < 50%` → DIVERGENT (show warning)
- `forecast_divergence >= 50%` → UNSTABLE (hide chart)

---

### 2. `episodes_diagnostics.csv`

**Purpose:** Explain episode detection logic and severity assignment

**Columns:**
- `episode_id` (int)
- `start_ts` (datetime) - Full timestamp with time
- `end_ts` (datetime)
- `duration_hours` (float)
- `peak_fused_z` (float) - Maximum fused z-score during episode
- `dominant_sensor` (str) - Sensor with highest peak z
- `dominant_sensor_peak_z` (float)
- `dominant_detector` (str) - Detector contributing most to fusion
- `severity_assigned` (str) - "info" / "warning" / "critical"
- `severity_reason` (str) - Why this severity was chosen
- `escalation_triggered` (bool) - Was severity escalated from default?
- `escalation_reason` (str) - Rule that triggered escalation

**Severity Rules:**
- Default: Use CUSUM-derived severity
- Escalate to "critical" if: peak_z > 10 OR dominant_sensor_peak_z > 5
- Escalate to "warning" if: peak_z > 3 OR duration > 24h

---

### 3. `omr_diagnostics.csv`

**Purpose:** OMR detector health and calibration status

**Columns:**
- `model_type` (str) - "PLS" / "Ridge" / "PCA"
- `n_components` (int)
- `explained_variance_ratio` (float) - For PCA
- `train_n_samples` (int)
- `train_n_features` (int)
- `test_rmse` (float) - Root mean squared residual on test set
- `saturation_rate` (float) - % of z-scores > 10
- `fusion_weight` (float) - Current weight in fusion
- `weight_quality_score` (float) - Auto-tuner quality metric
- `calibration_status` (str) - "VALID" / "SATURATED" / "DISABLED"
- `recommended_action` (str) - Guidance for user

**Calibration Rules:**
- `saturation_rate > 20%` → SATURATED
- `fusion_weight < 0.05` OR `weight_quality_score = 0` → DISABLED
- Charts suppressed if status != "VALID"

---

### 4. `chart_generation_log.csv`

**Purpose:** Track chart creation success/failure with reasons

**Columns:**
- `chart_name` (str)
- `generated` (bool)
- `skip_reason` (str) - Empty if generated, else explanation
- `source_tables` (str) - Comma-separated list of required tables
- `validation_errors` (str) - Any precondition failures
- `generation_time_s` (float)
- `file_size_kb` (float)
- `timestamp` (datetime)

**Example Rows:**
```csv
chart_name,generated,skip_reason,source_tables,validation_errors,generation_time_s,file_size_kb,timestamp
forecast_overlay.png,false,Forecast divergence > 50%,forecast_confidence.csv|scores.csv,forecast_divergence=120.5,0,0,2025-11-10 16:25:30
episodes_timeline.png,true,,episodes.csv,,1.2,45.3,2025-11-10 16:25:31
omr_timeline.png,false,OMR disabled (weight=0),scores.csv,fusion_weight=0.0,0,0,2025-11-10 16:25:32
```

---

### 5. `fusion_quality_report.csv`

**Purpose:** Comprehensive fusion diagnostics per detector

**Columns:**
- `detector_name` (str)
- `weight_current` (float)
- `weight_previous` (float)
- `weight_delta` (float)
- `quality_score` (float)
- `tuning_method` (str)
- `saturation_rate` (float) - % samples where z > clip_z
- `correlation_with_fused` (float) - Pearson r
- `recommendation` (str) - "INCREASE" / "DECREASE" / "DISABLE" / "OK"
- `reasoning` (str) - Why recommendation given
- `timestamp` (datetime)

---

## Chart Specification Matrix

### Operator-Facing (Must be reliable)

| Chart | Source Tables | Preconditions | Validation Rules |
|-------|--------------|---------------|------------------|
| `defect_dashboard.png` | defect_summary.csv, health_timeline.csv, drift_events.csv | All tables exist, defect_summary has 1 row | Status from defect_summary matches health_timeline severity distribution |
| `episodes_timeline.png` | episodes.csv | episodes.csv exists | If empty, annotate "No episodes detected". All timestamps valid. |
| `health_timeline.png` | health_timeline.csv | Min 10 rows | HealthZone matches HealthIndex thresholds (GOOD>80, WATCH 60-80, ALERT<60) |
| `sensor_defect_heatmap.png` | sensor_defects.csv | Min 1 sensor | Suppress if no sensors have defects |

### ML/Engineering (Diagnostic)

| Chart | Source Tables | Preconditions | Validation Rules |
|-------|--------------|---------------|------------------|
| `detector_comparison.png` | scores.csv | Min 100 rows | All z-score columns present and numeric |
| `forecast_overlay.png` | forecast_confidence.csv, scores.csv | forecast_diagnostics.recommendation="VALID" | Forecast starts within 10% of last observed |
| `omr_timeline.png` | scores.csv, omr_diagnostics.csv | omr_diagnostics.calibration_status="VALID" | Suppress if weight < 0.05 |
| `regime_scatter.png` | scores.csv | regime_count >= 2 from meta.json | Suppress if only 1 regime (not meaningful) |

---

## Post-Run Validation Script

**File:** `scripts/validate_charts.py`

**Functions:**
1. Load `chart_generation_log.csv`
2. For each chart marked `generated=false`:
   - Log skip_reason
   - Validate source tables exist
   - Report missing tables
3. For each chart marked `generated=true`:
   - Check file exists and size > 0
   - Validate chart type matches expected format
   - Parse image metadata if possible
4. Compare chart count against expected baseline (15-16 per run)
5. Write summary to `chart_quality_report.json`

**Usage:**
```powershell
python scripts/validate_charts.py --run-dir artifacts/run_20251110_162456
```

**Output:**
```json
{
  "run_id": "run_20251110_162456",
  "equipment": "FD_FAN",
  "charts_generated": 16,
  "charts_expected": 16,
  "charts_skipped": 0,
  "validation_passed": true,
  "warnings": [
    "forecast_overlay.png: Forecast divergence 120.5% exceeds 50% threshold"
  ],
  "errors": []
}
```

---

## Documentation Updates Required

### README.md

**Section 5: Output Artifacts**

Add subsection:

```markdown
#### Chart Quality & Troubleshooting

**Chart Generation Log:** Every run produces `tables/chart_generation_log.csv` documenting which charts were created and why any were skipped.

**Common Issues:**
- **Blank episodes timeline:** No episodes detected. Check drift_events.csv and sensor_hotspots.csv for anomalies below episode threshold.
- **Missing OMR charts:** OMR detector disabled due to calibration issues. See omr_diagnostics.csv for details.
- **Forecast divergence warning:** AR1 model prediction disconnected from recent trend. Chart suppressed until recalibrated.

**Validation:** Run `python scripts/validate_charts.py --run-dir <path>` to audit chart quality.
```

### New Document: `docs/CHART_SPEC.md`

Comprehensive chart specification with:
- Visual examples (screenshots)
- Table mappings
- Interpretation guide
- Troubleshooting per chart

---

## Implementation Priority

**Week 1 (Critical):**
1. CHART-01: Fix forecast (switch to fused series, add diagnostics table)
2. CHART-02: Fix episode timestamps (preserve full datetime)
3. CHART-04: Enforce timestamp format (audit all writers)
4. CHART-05: Add chart preconditions (validation framework)

**Week 2 (High):**
5. CHART-03: Hide OMR when invalid (check weight/quality before generation)
6. CHART-06-10: Create diagnostic tables (forecast, episodes, OMR, chart log, fusion quality)

**Week 3 (Medium):**
7. CHART-11-15: Chart enhancements (annotations, normalization, dashboard redesign)

**Week 4 (Testing):**
8. CHART-16-20: Validation script, unit tests, documentation, full asset testing

---

## Success Metrics

**Correctness:**
- [ ] All charts have validated source tables
- [ ] Timestamps consistent across all files
- [ ] Forecast within 10% of last observed value
- [ ] Episodes preserve full timestamps
- [ ] OMR charts suppressed when weight < 0.05

**Reliability:**
- [ ] Chart generation log shows 0 unexpected failures
- [ ] Validation script passes for both FD_FAN and GAS_TURBINE
- [ ] Chart count matches expected baseline ±1

**Usability:**
- [ ] Blank charts annotated with reason
- [ ] Operator dashboard reconciles defect status
- [ ] Documentation includes chart-to-table mapping

**Auditability:**
- [ ] Every chart traceable to source table(s)
- [ ] Diagnostic tables explain model decisions
- [ ] Skip reasons logged for missing charts

---

## Risk Assessment

**High Risk:**
- Forecast fix may require AR1 model refactor (fallback: hide chart)
- Timestamp normalization touches many files (test thoroughly)

**Medium Risk:**
- OMR calibration may need feature engineering changes (interim: suppress charts)
- Defect dashboard redesign may conflict with existing operator expectations

**Low Risk:**
- Diagnostic table additions (new files, no breaking changes)
- Chart precondition framework (gradual rollout per chart)

---

## Rollback Plan

If Phase 1 fixes cause regressions:
1. Revert to commit before CHART-01
2. Re-enable old forecast logic with "EXPERIMENTAL" watermark
3. Document known issues in README
4. Prioritize validation script to catch future issues

---

## Next Steps

1. **Review this document** with stakeholders
2. **Prioritize tasks** based on operator feedback
3. **Create GitHub issues** for each CHART-XX task
4. **Assign Phase 1** to sprint (target: Nov 17)
5. **Set up staging environment** for chart validation testing

---

**Document Owner:** ACM Development Team  
**Last Reviewed:** 2025-11-10  
**Next Review:** After Phase 1 completion (Nov 17, 2025)

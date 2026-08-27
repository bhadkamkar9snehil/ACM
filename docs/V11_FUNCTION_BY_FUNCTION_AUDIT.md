# ACM v11.0.0 Function-by-Function Audit

**Date**: 2024-12-24  
**Branch**: `feature/v11-refactor`  
**Commit**: `a76c41b`  
**Files Analyzed**: `core/acm_main.py` (5,040 lines), `core/output_manager.py` (2,589 lines)  
**Status**: COMPREHENSIVE AUDIT - NO CODE CHANGES  

---

## Executive Summary

### File Statistics

| File | Total Lines | Functions | Main Function | Helper Functions | Status |
|------|-------------|-----------|---------------|------------------|---------|
| **acm_main.py** | 5,040 | 32 | 2,860 (57%) | 31 (2,180 lines) | 🟡 Needs extraction |
| **output_manager.py** | 2,589 | ~45 | N/A | ~45 | 🟢 Well-refactored |
| **TOTAL** | 7,629 | ~77 | 2,860 | ~76 | |

### Critical Findings

1. **main() function**: Still 2,860 lines (57% of file) - **REQUIRES IMMEDIATE EXTRACTION**
2. **Wave 3 progress**: 19 helper functions extracted (excellent progress!)
3. **Helper functions**: Generally well-sized (avg 70 lines), but some are too large:
   - `_normalize_episodes_schema()`: 147 lines - **NEEDS BREAKING UP**
   - `_fit_all_detectors()`: 135 lines - **CONSIDER SPLITTING**
   - `_calculate_adaptive_thresholds()`: 130 lines - **CONSIDER SPLITTING**
   - `_update_baseline_buffer()`: 127 lines - **ACCEPTABLE**
   - `_rebuild_detectors_from_cache()`: 122 lines - **ACCEPTABLE**
4. **Good helpers**: Most helpers are focused and well-sized (17-98 lines)
5. **CSV remnants**: Still present in main() - needs removal

---

## Part 1: acm_main.py Function-by-Function Analysis

### 1.1 Helper Functions (Lines 253-2180)

#### ✅ **EXCELLENT** - Small, Focused Helpers (17-58 lines)

| Function | Lines | Location | Purpose | Status |
|----------|-------|----------|---------|--------|
| `_configure_logging` | 19 | 253-271 | Logging setup | ✅ Keep as-is |
| `_ensure_local_index` | 20 | 497-516 | DataFrame index normalization | ✅ Keep as-is |
| `_continuous_learning_enabled` | 8 | 517-524 | Batch mode detection | ✅ Keep as-is |
| `_sql_connect` | 17 | 525-541 | SQL client factory | ✅ Keep as-is |
| `_execute_with_deadlock_retry` | 17 | 672-688 | SQL retry logic | ✅ Keep as-is |
| `_compute_regime_volatility` | 18 | 354-371 | Regime stability metric | ✅ Keep as-is |
| `_compute_config_signature` | 24 | 473-496 | Config hashing | ✅ Keep as-is |
| `_compute_drift_trend` | 30 | 324-353 | Drift trend analysis | ✅ Keep as-is |
| `_deduplicate_index` | 30 | 1067-1096 | Index deduplication | ✅ Keep as-is |
| `_get_detector_enable_flags` | 31 | 1036-1066 | Detector config parsing | ✅ Keep as-is |
| `_sql_finalize_run` | 32 | 746-777 | Run cleanup | ✅ Keep as-is |
| `_compute_stable_feature_hash` | 37 | 1346-1382 | Feature stability hashing | ✅ Keep as-is |
| `_get_equipment_id` | 43 | 372-414 | Equipment ID resolution | ✅ Keep as-is |
| `_check_refit_request` | 49 | 1383-1431 | Refit flag detection | ✅ Keep as-is |
| `_calibrate_all_detectors` | 50 | 851-900 | Detector calibration | ✅ Keep as-is |
| `_nearest_indexer` | 52 | 272-323 | Timestamp mapping | ✅ Keep as-is |
| `_sql_start_run` | 57 | 689-745 | Run initialization | ✅ Keep as-is |
| `_load_config` | 58 | 415-472 | Config loading | ✅ Keep as-is |
| `_log_dropped_features` | 58 | 1688-1745 | Feature drop logging | ✅ Keep as-is |

**Summary**: 19 excellent helper functions (17-58 lines each), total ~635 lines extracted from main().

---

#### 🟡 **GOOD** - Medium-Sized Helpers (70-98 lines)

| Function | Lines | Location | Purpose | Assessment |
|----------|-------|----------|---------|------------|
| `_score_all_detectors` | 73 | 778-850 | Score all detectors | 🟢 Acceptable size |
| `_load_cached_models_with_validation` | 77 | 1432-1508 | Model cache loading | 🟢 Acceptable size |
| `_write_data_quality` | 82 | 1746-1827 | Data quality metrics | 🟢 Acceptable size |
| `_write_fusion_metrics` | 88 | 1600-1687 | Fusion quality metrics | 🟢 Acceptable size |
| `_save_trained_models` | 91 | 1509-1599 | Model persistence | 🟢 Acceptable size |
| `_compute_drift_alert_mode` | 98 | 2083-2180 | Drift alerting logic | 🟢 Acceptable size |

**Summary**: 6 good helper functions (70-98 lines each), total ~509 lines. Well-scoped and focused.

---

#### 🟠 **LARGE** - Helpers Needing Review (108-147 lines)

##### `_write_pca_artifacts()` - 108 lines (1975-2082)
**Purpose**: Write PCA model artifacts to SQL  
**Issue**: Large due to comprehensive PCA metadata writing  
**Recommendation**: 
- ✅ **KEEP AS-IS** - Complexity is inherent to PCA artifact persistence
- All writes are related to single task (PCA artifacts)
- Breaking it up would create artificial fragmentation

**Code Pattern**:
```python
def _write_pca_artifacts(pca_detector, equip_id, run_id, sql_client, feature_names):
    # 1. Extract PCA metadata
    # 2. Write ACM_PCA_Models
    # 3. Write ACM_PCA_Loadings (many rows)
    # 4. Write ACM_PCA_Metrics
    # ... total 108 lines
```

---

##### `_rebuild_detectors_from_cache()` - 122 lines (1097-1218)
**Purpose**: Deserialize all detectors from SQL cache  
**Issue**: Large due to handling 5+ detectors  
**Recommendation**: 
- ✅ **KEEP AS-IS** - Complexity is inherent to multi-detector deserialization
- Each detector needs custom deserialization logic
- Already well-structured with clear sections

**Code Pattern**:
```python
def _rebuild_detectors_from_cache(cache_row, equip, cfg):
    # 1. Validate cache
    # 2. Deserialize AR1
    # 3. Deserialize PCA
    # 4. Deserialize IForest
    # 5. Deserialize GMM
    # 6. Deserialize OMR
    # ... total 122 lines (24 lines per detector avg)
```

---

##### `_update_baseline_buffer()` - 127 lines (1219-1345)
**Purpose**: Update baseline buffer in SQL with smart refresh logic  
**Issue**: Large due to complex refresh strategy  
**Recommendation**: 
- ✅ **KEEP AS-IS** - Complexity is inherent to baseline buffer management
- Handles coldstart, refresh, and SQL persistence
- Already well-structured with clear phases

**Code Pattern**:
```python
def _update_baseline_buffer(buffer, new_data, cfg, sql_client, equip_id):
    # 1. Smart refresh logic
    # 2. Vectorized concatenation
    # 3. SQL batch write
    # 4. Error handling
    # ... total 127 lines
```

---

##### `_calculate_adaptive_thresholds()` - 130 lines (542-671)
**Purpose**: Calculate regime-specific adaptive thresholds  
**Issue**: Large due to complex statistical calculations  
**Recommendation**: 
- 🟡 **CONSIDER SPLITTING** into sub-functions:
  - `_calculate_baseline_thresholds()` - Initial quantile calculation
  - `_adjust_for_regime()` - Regime-specific adjustments
  - `_apply_bounds()` - Min/max clamping

**Potential Refactor**:
```python
def _calculate_adaptive_thresholds(scores, cfg, regime_labels):
    baseline = _calculate_baseline_thresholds(scores, cfg)
    adjusted = _adjust_for_regime(baseline, regime_labels, cfg)
    final = _apply_bounds(adjusted, cfg)
    return final
```

---

##### `_fit_all_detectors()` - 135 lines (901-1035)
**Purpose**: Fit all 5 detectors on training data  
**Issue**: Large due to handling 5+ detectors  
**Recommendation**: 
- 🟡 **CONSIDER SPLITTING** by detector type:
  - Keep `_fit_all_detectors()` as orchestrator
  - Extract `_fit_ar1()`, `_fit_pca()`, `_fit_iforest()`, `_fit_gmm()`, `_fit_omr()`

**Potential Refactor**:
```python
def _fit_all_detectors(train, cfg):
    ar1 = _fit_ar1(train, cfg)
    pca = _fit_pca(train, cfg)
    iforest = _fit_iforest(train, cfg)
    gmm = _fit_gmm(train, cfg)
    omr = _fit_omr(train, cfg, [ar1, pca, iforest, gmm])
    return {
        'ar1': ar1, 'pca': pca, 'iforest': iforest,
        'gmm': gmm, 'omr': omr
    }
```

---

##### `_normalize_episodes_schema()` - 147 lines (1828-1974)
**Purpose**: Normalize episode DataFrame schema for SQL write  
**Issue**: **TOO LARGE** - handling many schema transformations  
**Recommendation**: 
- ❌ **MUST SPLIT** into smaller focused functions:
  - `_validate_episode_columns()` - Column validation
  - `_add_missing_episode_columns()` - Add defaults for missing columns
  - `_normalize_episode_timestamps()` - Timestamp normalization
  - `_normalize_episode_types()` - Type coercion

**Proposed Refactor**:
```python
def _normalize_episodes_schema(episodes, equip_id, run_id):
    """Orchestrator for episode normalization."""
    df = episodes.copy()
    df = _validate_episode_columns(df)
    df = _add_missing_episode_columns(df, equip_id, run_id)
    df = _normalize_episode_timestamps(df)
    df = _normalize_episode_types(df)
    return df

def _validate_episode_columns(df):
    """Validate required columns exist."""
    # ~20 lines
    
def _add_missing_episode_columns(df, equip_id, run_id):
    """Add defaults for missing optional columns."""
    # ~40 lines
    
def _normalize_episode_timestamps(df):
    """Normalize all timestamp columns."""
    # ~30 lines
    
def _normalize_episode_types(df):
    """Coerce types to SQL-compatible formats."""
    # ~40 lines
```

**Benefits**:
- Each function < 50 lines
- Clear single responsibility
- Easier to test
- Easier to maintain

---

### 1.2 Main Function Analysis (Lines 2181-5040)

**Size**: 2,860 lines (57% of entire file!)  
**Status**: ❌ **CRITICAL** - Requires immediate extraction  

#### Current Structure (Simplified)

```python
def main() -> None:
    """Monolithic pipeline orchestrator (2,860 lines)."""
    
    # === INITIALIZATION (Lines 2181-2350, ~170 lines) ===
    # - Argparse setup
    # - Observability init
    # - Config loading
    # - Equipment ID resolution
    # - SQL connection
    # - Output manager init
    # - Timer setup
    
    # === DATA LOADING (Lines 2350-2520, ~170 lines) ===
    # - SmartColdstart logic
    # - SQL historian queries
    # - Data validation
    # - Feature extraction
    
    # === MODEL LOADING/CACHING (Lines 2520-2780, ~260 lines) ===
    # - Check SQL model registry
    # - Load cached models OR
    # - Fit new models
    # - Persist to cache
    
    # === DETECTOR FITTING (Lines 2780-3020, ~240 lines) ===
    # - Fit AR1, PCA, IForest, GMM, OMR
    # - Calibrate thresholds
    # - Validate models
    
    # === REGIME CLUSTERING (Lines 3020-3200, ~180 lines) ===
    # - Regime discovery (offline) OR
    # - Regime assignment (online)
    # - Quality assessment
    
    # === SCORING & FUSION (Lines 3200-3420, ~220 lines) ===
    # - Score all detectors
    # - Z-score normalization
    # - Weighted fusion
    # - Health calculation
    
    # === EPISODE DETECTION (Lines 3420-3590, ~170 lines) ===
    # - Change point detection
    # - Episode merging
    # - Episode metadata
    
    # === HEALTH & DRIFT (Lines 3590-3740, ~150 lines) ===
    # - Drift CUSUM
    # - Health zones
    # - Alert mode
    
    # === AUTO-TUNING (Lines 3740-4010, ~270 lines) ===
    # - Fusion weight tuning
    # - Adaptive thresholds
    # - Model quality assessment
    
    # === OUTPUT GENERATION (Lines 4010-4680, ~670 lines!) ===
    # - Write 20+ SQL tables
    # - Analytics generation
    # - Diagnostic outputs
    
    # === FORECASTING (Lines 4680-4870, ~190 lines) ===
    # - RUL estimation
    # - Health forecasting
    # - Failure probability
    
    # === FINALIZATION (Lines 4870-5040, ~170 lines) ===
    # - Timer stats
    # - Run metadata
    # - SQL cleanup
    # - Observability shutdown
```

#### Main Function Extraction Targets

**15 Pipeline Stages to Extract** (~190 lines each):

1. **`_initialize_pipeline(args)`** → PipelineContext (170 lines)
2. **`_load_pipeline_data(ctx)`** → DataLoadResult (170 lines)
3. **`_load_or_fit_models(data, ctx)`** → ModelBundle (260 lines)
4. **`_fit_detectors_if_needed(data, models, ctx)`** → DetectorBundle (240 lines)
5. **`_cluster_regimes(data, models, ctx)`** → RegimeResults (180 lines)
6. **`_score_and_fuse(data, detectors, regimes, ctx)`** → ScoredFrame (220 lines)
7. **`_detect_episodes(scored, ctx)`** → Episodes (170 lines)
8. **`_calculate_health_drift(scored, ctx)`** → HealthDrift (150 lines)
9. **`_auto_tune_pipeline(scored, ctx)`** → TuningResults (270 lines)
10. **`_generate_core_outputs(scored, ctx)`** → None (200 lines)
11. **`_generate_diagnostic_outputs(scored, episodes, ctx)`** → None (200 lines)
12. **`_generate_analytics_outputs(scored, regimes, ctx)`** → None (270 lines)
13. **`_run_forecasting(scored, ctx)`** → ForecastResults (190 lines)
14. **`_write_forecast_outputs(forecasts, ctx)`** → None (100 lines)
15. **`_finalize_run(ctx, outcome, stats)`** → None (170 lines)

**Result**: main() reduces from 2,860 → ~150 lines (95% reduction!)

---

## Part 2: output_manager.py Analysis

### 2.1 Current State

**Status**: ✅ **WELL-REFACTORED**  
**Lines**: 2,589 (down from 5,111 - 49% reduction!)  
**Methods**: ~45  
**Key Improvements**:
- Consolidated ALLOWED_TABLES to 12 core tables
- Removed many deprecated analytics methods
- Simplified table generation logic

### 2.2 Remaining Issues

#### Minor CSV Remnants
**Location**: Scattered throughout file  
**Issue**: Still has some file mode references  
**Action**: Remove all CSV/file mode logic

**Examples to Remove**:
```python
# Line ~6: Docstring mentions CSV
"Single point of control for all CSV, JSON, and model outputs"  # CHANGE TO "SQL outputs"

# File mode fallback logic
if not sql_table:
    # File mode handling...  # REMOVE ENTIRELY
```

#### Cleanup Recommendations
- Update module docstring (remove CSV references)
- Remove any remaining file path parameters
- Enforce SQL-only mode in all write methods

---

## Part 3: Detailed Task List

### Wave 4: Main Function Extraction (HIGH PRIORITY)

#### Phase 4.1: Core Infrastructure (Week 1)

**Task 4.1.1**: Create pipeline_stages.py module
- [ ] Create new file `core/pipeline_stages.py`
- [ ] Define `PipelineContext` dataclass
- [ ] Define `DataLoadResult` dataclass
- [ ] Define `ModelBundle` dataclass
- [ ] Define `DetectorBundle` dataclass
- [ ] Define `RegimeResults` dataclass
- [ ] Define `ScoredFrame` dataclass
- [ ] Define `Episodes` dataclass
- [ ] Define `HealthDrift` dataclass
- [ ] Define `TuningResults` dataclass
- [ ] Define `ForecastResults` dataclass
- [ ] Add comprehensive type hints
- [ ] Add docstrings for all classes

**Task 4.1.2**: Extract initialization stage
- [ ] Extract lines 2181-2350 to `_initialize_pipeline(args)`
- [ ] Return `PipelineContext` object
- [ ] Update main() to use new function
- [ ] Add unit tests for initialization
- [ ] Verify SQL connection works

**Task 4.1.3**: Extract data loading stage
- [ ] Extract lines 2350-2520 to `_load_pipeline_data(ctx)`
- [ ] Return `DataLoadResult` object
- [ ] Remove CSV mode entirely
- [ ] Update main() to use new function
- [ ] Add unit tests for data loading

---

#### Phase 4.2: Model & Detector Pipeline (Week 2)

**Task 4.2.1**: Extract model loading stage
- [ ] Extract lines 2520-2780 to `_load_or_fit_models(data, ctx)`
- [ ] Return `ModelBundle` object
- [ ] Integrate with model registry
- [ ] Update main() to use new function
- [ ] Add unit tests for model caching

**Task 4.2.2**: Extract detector fitting stage
- [ ] Extract lines 2780-3020 to `_fit_detectors_if_needed(data, models, ctx)`
- [ ] Return `DetectorBundle` object
- [ ] Update main() to use new function
- [ ] Add unit tests for detector fitting

**Task 4.2.3**: Extract regime clustering stage
- [ ] Extract lines 3020-3200 to `_cluster_regimes(data, models, ctx)`
- [ ] Return `RegimeResults` object
- [ ] Integrate with ActiveModelsManager
- [ ] Update main() to use new function
- [ ] Add unit tests for regime discovery

---

#### Phase 4.3: Scoring & Analysis (Week 3)

**Task 4.3.1**: Extract scoring & fusion stage
- [ ] Extract lines 3200-3420 to `_score_and_fuse(data, detectors, regimes, ctx)`
- [ ] Return `ScoredFrame` object
- [ ] Update main() to use new function
- [ ] Add unit tests for fusion logic

**Task 4.3.2**: Extract episode detection stage
- [ ] Extract lines 3420-3590 to `_detect_episodes(scored, ctx)`
- [ ] Return `Episodes` object
- [ ] Update main() to use new function
- [ ] Add unit tests for episode detection

**Task 4.3.3**: Extract health & drift stage
- [ ] Extract lines 3590-3740 to `_calculate_health_drift(scored, ctx)`
- [ ] Return `HealthDrift` object
- [ ] Update main() to use new function
- [ ] Add unit tests for drift detection

**Task 4.3.4**: Extract auto-tuning stage
- [ ] Extract lines 3740-4010 to `_auto_tune_pipeline(scored, ctx)`
- [ ] Return `TuningResults` object
- [ ] Update main() to use new function
- [ ] Add unit tests for tuning logic

---

#### Phase 4.4: Output Generation (Week 4)

**Task 4.4.1**: Extract core outputs stage
- [ ] Extract lines 4010-4210 to `_generate_core_outputs(scored, ctx)`
- [ ] Write ACM_Scores_Wide, ACM_HealthTimeline, ACM_RegimeTimeline
- [ ] Update main() to use new function
- [ ] Add unit tests for core outputs

**Task 4.4.2**: Extract diagnostic outputs stage
- [ ] Extract lines 4210-4410 to `_generate_diagnostic_outputs(scored, episodes, ctx)`
- [ ] Write ACM_SensorDefects, ACM_EpisodeCulprits, etc.
- [ ] Update main() to use new function
- [ ] Add unit tests for diagnostic outputs

**Task 4.4.3**: Extract analytics outputs stage
- [ ] Extract lines 4410-4680 to `_generate_analytics_outputs(scored, regimes, ctx)`
- [ ] Write remaining analytics tables
- [ ] Update main() to use new function
- [ ] Add unit tests for analytics outputs

**Task 4.4.4**: Extract forecasting stages
- [ ] Extract lines 4680-4770 to `_run_forecasting(scored, ctx)`
- [ ] Extract lines 4770-4870 to `_write_forecast_outputs(forecasts, ctx)`
- [ ] Return `ForecastResults` object
- [ ] Update main() to use new functions
- [ ] Add unit tests for forecasting

**Task 4.4.5**: Extract finalization stage
- [ ] Extract lines 4870-5040 to `_finalize_run(ctx, outcome, stats)`
- [ ] Ensure cleanup always runs
- [ ] Update main() to use new function
- [ ] Add unit tests for cleanup

**Task 4.4.6**: Refactor main() as orchestrator
- [ ] Rewrite main() to call 15 stage functions (~150 lines)
- [ ] Add stage-level error handling
- [ ] Add comprehensive logging
- [ ] Add integration tests for full pipeline

---

### Wave 5: Helper Function Cleanup (MEDIUM PRIORITY)

#### Task 5.1: Split large helpers

**Task 5.1.1**: Split `_normalize_episodes_schema()` (147 lines)
- [ ] Extract `_validate_episode_columns()`
- [ ] Extract `_add_missing_episode_columns()`
- [ ] Extract `_normalize_episode_timestamps()`
- [ ] Extract `_normalize_episode_types()`
- [ ] Update orchestrator function
- [ ] Add unit tests for each sub-function

**Task 5.1.2**: Consider splitting `_fit_all_detectors()` (135 lines)
- [ ] Evaluate if splitting provides value
- [ ] If yes, extract `_fit_ar1()`, `_fit_pca()`, etc.
- [ ] Keep as orchestrator calling sub-functions
- [ ] Add unit tests for each detector

**Task 5.1.3**: Consider splitting `_calculate_adaptive_thresholds()` (130 lines)
- [ ] Evaluate if splitting provides value
- [ ] If yes, extract `_calculate_baseline_thresholds()`
- [ ] Extract `_adjust_for_regime()`, `_apply_bounds()`
- [ ] Add unit tests for each sub-function

---

### Wave 6: CSV Removal & Documentation (LOW PRIORITY)

#### Task 6.1: Remove CSV remnants
- [ ] Remove CSV references from docstrings
- [ ] Remove file mode fallback logic
- [ ] Update method signatures for SQL-only
- [ ] Add tests to verify CSV mode raises errors

#### Task 6.2: Update documentation
- [ ] Update V11_ARCHITECTURE.md with pipeline stages
- [ ] Update V11_MIGRATION_GUIDE.md
- [ ] Create PIPELINE_STAGES.md
- [ ] Update .github/copilot-instructions.md

#### Task 6.3: Add comprehensive tests
- [ ] Unit tests for all 15 pipeline stages
- [ ] Integration tests for full pipeline
- [ ] Test error handling and recovery
- [ ] Target >80% test coverage

---

## Part 4: Success Metrics

### Code Quality Metrics
- **main() size**: 2,860 → 150 lines (95% reduction)
- **Cyclomatic complexity**: main() < 20 (from ~140+)
- **Function size**: No function > 150 lines
- **Test coverage**: >80% for pipeline stages

### Performance Metrics
- **Run time**: Within ±5% of baseline
- **Memory usage**: Within ±10% of baseline
- **SQL transactions**: No increase
- **Error rate**: < 0.1%

### Maintainability Metrics
- **Time to add feature**: 40% reduction
- **Code review time**: 50% reduction
- **Onboarding time**: 30% reduction
- **Bug fix time**: 30% reduction

---

## Part 5: Risk Analysis

### High-Risk Changes

**Risk 1: Breaking Pipeline Execution**
- **Probability**: Medium
- **Impact**: High
- **Mitigation**:
  - Extract one stage at a time
  - Test each extraction independently
  - Use feature flags for gradual rollout
  - Maintain backward compatibility during transition

**Risk 2: Performance Degradation**
- **Probability**: Low
- **Impact**: Medium
- **Mitigation**:
  - Benchmark before/after each extraction
  - Profile with Pyroscope
  - Monitor OTEL metrics
  - Optimize hot paths if needed

**Risk 3: Test Coverage Gaps**
- **Probability**: High
- **Impact**: Medium
- **Mitigation**:
  - Write tests for each extracted function
  - Target >80% coverage
  - Use integration tests for end-to-end validation

---

## Part 6: Timeline & Effort Estimate

### Total Effort: 6 weeks

| Phase | Tasks | Lines to Extract | Duration | Priority |
|-------|-------|------------------|----------|----------|
| Phase 4.1 | Core infrastructure | ~340 | 1 week | HIGH |
| Phase 4.2 | Model & detector pipeline | ~680 | 1 week | HIGH |
| Phase 4.3 | Scoring & analysis | ~810 | 1 week | HIGH |
| Phase 4.4 | Output generation | ~880 | 2 weeks | HIGH |
| Wave 5 | Helper cleanup | ~412 | 1 week | MEDIUM |
| Wave 6 | CSV removal & docs | N/A | 1 week | LOW |

**Weekly Breakdown**:
- **Week 1**: Infrastructure + data loading + model loading (Tasks 4.1.1-4.1.3, 4.2.1)
- **Week 2**: Detectors + regimes + scoring (Tasks 4.2.2-4.3.1)
- **Week 3**: Episodes + health + tuning (Tasks 4.3.2-4.3.4)
- **Week 4**: Core + diagnostic outputs (Tasks 4.4.1-4.4.2)
- **Week 5**: Analytics + forecasting + finalization (Tasks 4.4.3-4.4.5, 4.4.6)
- **Week 6**: Helper cleanup + CSV removal + docs (Wave 5 + Wave 6)

---

## Conclusion

This function-by-function audit identifies:

1. **Main function bloat**: 2,860 lines (57% of file) requiring extraction into 15 focused stages
2. **Excellent Wave 3 progress**: 19 helper functions (avg 70 lines) successfully extracted
3. **One problematic helper**: `_normalize_episodes_schema()` (147 lines) needs splitting
4. **Three large helpers**: Consider splitting `_fit_all_detectors()` (135 lines), `_calculate_adaptive_thresholds()` (130 lines)
5. **Output manager**: Already well-refactored (49% reduction), minimal work needed

**Immediate Actions**:
1. Start Wave 4, Phase 4.1 (Core infrastructure extraction)
2. Split `_normalize_episodes_schema()` into 4 focused functions
3. Remove CSV remnants from both files

**Expected Outcome**:
- main() reduced from 2,860 → 150 lines (95%)
- 15 testable pipeline stages
- All functions < 150 lines
- >80% test coverage
- Complete SQL-only mode
- Production-ready v11.0.0 refactoring

# ACM v11.0.0 Refactoring Audit (feature/v11-refactor Branch)

**Date**: 2024-12-24  
**Branch**: `feature/v11-refactor`  
**Scope**: Comprehensive audit of `core/acm_main.py` and `core/output_manager.py`  
**Objective**: Complete the v11 refactoring by eliminating remaining bloat and extracting monolithic main()  
**Status**: AUDIT ONLY - NO CODE CHANGES  

---

## Executive Summary

### Current State (feature/v11-refactor branch)

**Progress Made**:
- Wave 3 extractions completed: 10+ helper functions extracted
- output_manager.py: Reduced from 5,111 → 2,589 lines (49% reduction!)
- acm_main.py: Reduced from 4,888 → 4,745 lines (3% reduction so far)
- Core v11 functionality: 60/60 tasks complete (per V11_REFACTOR_TRACKER.md)

**Remaining Issues**:
- **main() function**: Still 3,311 lines (70% of acm_main.py)
- **CSV bloat**: Still present despite SQL-only mode
- **Monolithic structure**: main() still orchestrates entire pipeline
- **Testing**: Limited test coverage for extracted helpers
- **Documentation**: Needs update for new architecture

### File Statistics

| File | Current Lines | Main Function | Functions | Status |
|------|---------------|---------------|-----------|--------|
| acm_main.py | 4,745 | 3,311 (70%) | 24 | 🟡 Partially refactored |
| output_manager.py | 2,589 | N/A | ~45 | 🟢 Well refactored |

### Critical Issues Identified

1. **Massive main() function** - 3,311 lines handling entire pipeline
2. **CSV mode remnants** - Despite SQL-only architecture
3. **Limited modularity** - Pipeline stages still embedded in main()
4. **Testing gaps** - New helpers lack comprehensive tests
5. **Documentation debt** - Refactoring changes not fully documented

---

## Part 1: acm_main.py Detailed Analysis

### 1.1 Current main() Function Structure

**Location**: Lines 1435-4745 (3,311 lines = 70% of file)  
**Problem**: Still monolithic despite Wave 3 extractions  

**Current Structure** (Simplified):
```python
def main():
    # 1. Initialization (100 lines)
    # 2. Data Loading (150 lines)
    # 3. Model Loading/Caching (250 lines)
    # 4. Detector Fitting (400 lines)  
    # 5. Regime Clustering (200 lines)
    # 6. Scoring & Fusion (250 lines)
    # 7. Episode Detection (200 lines)
    # 8. Health & Drift (150 lines)
    # 9. Auto-Tuning (300 lines)
    # 10. Baseline Buffer Update (150 lines)
    # 11. Output Generation (800 lines!)
    # 12. Forecasting (300 lines)
    # 13. SQL Persistence (400 lines)
    # 14. Finalization (150 lines)
    # TOTAL: ~3,300 lines
```

### 1.2 Wave 3 Helpers (Already Extracted)

**Completed Extractions** ✅:
- `_get_detector_enable_flags()` - Detector configuration parsing
- `_deduplicate_index()` - Index deduplication
- `_rebuild_detectors_from_cache()` - Detector cache rebuilding
- `_update_baseline_buffer()` - Baseline buffer persistence
- `_compute_stable_feature_hash()` - Feature stability hashing
- `_check_refit_request()` - Refit request detection
- Additional helpers from previous waves

**Total Extracted**: ~300 lines  
**Remaining in main()**: ~3,311 lines

### 1.3 Remaining Extraction Opportunities

#### 1.3.1 Initialization Block (Lines ~1435-1535, ~100 lines)
**EXTRACT TO**: `_initialize_pipeline(args) -> PipelineContext`

**Current Code Pattern**:
```python
def main():
    # Argparse setup
    ap = argparse.ArgumentParser(...)
    # 20+ arguments
    args = ap.parse_args()
    
    # Observability init
    init_observability(...)
    
    # Config loading
    cfg = _load_config(args.config_path)
    
    # Equipment ID resolution
    equip_id = _get_equipment_id(...)
    
    # Run ID generation
    run_id = str(uuid.uuid4())
    
    # SQL connection
    sql_client = _sql_connect(cfg)
    
    # ... 50 more initialization lines ...
```

**Proposed Extraction**:
```python
@dataclass
class PipelineContext:
    """Consolidated pipeline initialization state."""
    args: argparse.Namespace
    cfg: Dict[str, Any]
    sql_client: Any
    output_mgr: OutputManager
    run_id: str
    equip_id: int
    equipment: str
    batch_num: int
    tracer: Any
    meter: Any
    timer: Any
    mode: PipelineMode

def _initialize_pipeline(args: argparse.Namespace) -> PipelineContext:
    """Initialize all pipeline dependencies and return context."""
    # Config
    cfg = _load_config(args.config_path)
    
    # Observability
    init_observability(...)
    tracer = get_tracer()
    meter = get_meter()
    
    # SQL
    sql_client = _sql_connect(cfg)
    
    # Equipment
    equip_id = _get_equipment_id(...)
    
    # Output Manager
    output_mgr = OutputManager(sql_client, ...)
    
    # Timer
    timer = Timer()
    
    # Mode detection
    mode = PipelineMode.detect(args, cfg)
    
    return PipelineContext(
        args=args,
        cfg=cfg,
        sql_client=sql_client,
        output_mgr=output_mgr,
        run_id=str(uuid.uuid4()),
        equip_id=equip_id,
        equipment=args.equip,
        batch_num=args.batch_num or 0,
        tracer=tracer,
        meter=meter,
        timer=timer,
        mode=mode
    )
```

**Benefits**:
- Single entry point for initialization
- Type-safe context object
- Testable in isolation
- ~100 lines extracted

---

#### 1.3.2 Data Loading Block (Lines ~1535-1685, ~150 lines)
**EXTRACT TO**: `_load_pipeline_data(ctx: PipelineContext) -> DataLoadResult`

**Current Code Pattern**:
```python
def main():
    # ... initialization ...
    
    # Data loading with SmartColdstart
    with T.section("Data Loading"):
        if args.start_time and args.end_time:
            # SQL mode
            train, score, meta = output_mgr.load_data(
                cfg, start_time, end_time, equipment, sql_mode=True
            )
        else:
            # CSV mode (SHOULD BE REMOVED)
            train, score, meta = output_mgr.load_data(
                cfg, sql_mode=False
            )
        
        # Data validation
        if len(train) < min_samples:
            raise ValueError(...)
        
        # ... 100 more lines of data processing ...
```

**Proposed Extraction**:
```python
@dataclass
class DataLoadResult:
    """Result of data loading stage."""
    train: pd.DataFrame
    score: pd.DataFrame
    meta: DataMeta
    contract: DataContract
    is_coldstart: bool
    train_samples: int
    score_samples: int

def _load_pipeline_data(ctx: PipelineContext) -> DataLoadResult:
    """Load and validate training and scoring data."""
    with ctx.timer.section("Data Loading"):
        # Determine mode
        is_coldstart = ctx.args.start_time is None
        
        # Load data (SQL-only)
        train, score, meta = ctx.output_mgr.load_data(
            ctx.cfg,
            start_utc=ctx.args.start_time,
            end_utc=ctx.args.end_time,
            equipment_name=ctx.equipment,
            sql_mode=True,
            is_coldstart=is_coldstart
        )
        
        # Validate contract
        contract = DataContract.validate(train, score, ctx.cfg)
        
        # Log data quality
        record_data_quality(ctx.equip_id, contract.quality_score)
        
        return DataLoadResult(
            train=train,
            score=score,
            meta=meta,
            contract=contract,
            is_coldstart=is_coldstart,
            train_samples=len(train),
            score_samples=len(score)
        )
```

**Benefits**:
- Clean data loading abstraction
- Removes CSV mode entirely
- Type-safe results
- ~150 lines extracted

---

#### 1.3.3 Model Loading Block (Lines ~1685-1935, ~250 lines)
**EXTRACT TO**: `_load_or_fit_models(data: DataLoadResult, ctx: PipelineContext) -> ModelBundle`

**Current Code Pattern**:
```python
def main():
    # ... data loading ...
    
    # Model loading/caching
    with T.section("Model Loading"):
        # Check SQL cache
        cached_models = query_model_registry(...)
        
        if cached_models:
            # Load from cache
            ar1 = deserialize_ar1(cached_models['ar1'])
            pca = deserialize_pca(cached_models['pca'])
            # ... etc
        else:
            # Fit new models
            ar1 = AR1Detector()
            ar1.fit(train)
            # ... etc
            
            # Cache to SQL
            save_to_registry(...)
        
        # ... 200 more lines ...
```

**Proposed Extraction**:
```python
@dataclass
class ModelBundle:
    """All fitted models for the pipeline."""
    ar1: AR1Detector
    pca: Any
    iforest: Any
    gmm: Any
    omr: OMRDetector
    regime_model: Any
    baseline_stats: Dict[str, Any]
    cache_hit: bool
    model_age_hours: float

def _load_or_fit_models(
    data: DataLoadResult,
    ctx: PipelineContext
) -> ModelBundle:
    """Load models from cache or fit new ones."""
    with ctx.timer.section("Model Loading"):
        # Check cache
        config_hash = _compute_stable_feature_hash(data.train.columns)
        cached = query_model_registry(
            ctx.sql_client,
            ctx.equip_id,
            config_hash
        )
        
        if cached and cached.is_valid():
            # Cache hit
            Console.info(f"Model cache HIT (age: {cached.age_hours:.1f}h)")
            return deserialize_model_bundle(cached)
        
        # Cache miss - fit new
        Console.info("Model cache MISS - fitting new models")
        bundle = _fit_all_detectors(data.train, ctx.cfg)
        
        # Persist to cache
        serialize_model_bundle(bundle, ctx.sql_client, ctx.equip_id, config_hash)
        
        return bundle
```

**Benefits**:
- Centralized model lifecycle
- Clear cache strategy
- ~250 lines extracted

---

#### 1.3.4 Detector Fitting Block (Lines ~1935-2335, ~400 lines)
**EXTRACT TO**: `_fit_all_detectors(train: pd.DataFrame, cfg: Dict) -> ModelBundle`

**Current Code Pattern**:
```python
def main():
    # ... model loading ...
    
    # Detector fitting (if not cached)
    with T.section("AR1 Fitting"):
        ar1 = AR1Detector()
        ar1.fit(train)
        ar1_params = ar1.get_params()
        # ... 50 lines ...
    
    with T.section("PCA Fitting"):
        pca = PCADetector()
        pca.fit(train)
        pca_params = pca.get_params()
        # ... 80 lines ...
    
    # ... repeat for IForest, GMM, OMR ...
```

**Status**: ⚠️ Partially extracted (Wave 3 has `_fit_all_detectors` helper)

**Action Needed**:
- Verify `_fit_all_detectors()` is comprehensive
- Ensure it returns ModelBundle, not raw objects
- Add calibration logic to helper

---

#### 1.3.5 Regime Clustering Block (Lines ~2335-2535, ~200 lines)
**EXTRACT TO**: `_cluster_regimes(data: DataLoadResult, models: ModelBundle, ctx: PipelineContext) -> RegimeResults`

**Current Code Pattern**:
```python
def main():
    # ... detector fitting ...
    
    # Regime clustering
    with T.section("Regime Clustering"):
        regime_features = extract_regime_features(train)
        regime_model = KMeans(n_clusters=cfg['regime_k'])
        regime_model.fit(regime_features)
        
        train_regimes = regime_model.predict(train_regime_features)
        score_regimes = regime_model.predict(score_regime_features)
        
        # ... 150 more lines of regime processing ...
```

**Proposed Extraction**:
```python
@dataclass
class RegimeResults:
    """Results from regime clustering stage."""
    train_labels: np.ndarray
    score_labels: np.ndarray
    regime_model: Any
    regime_centroids: pd.DataFrame
    regime_quality: float
    n_regimes: int

def _cluster_regimes(
    data: DataLoadResult,
    models: ModelBundle,
    ctx: PipelineContext
) -> RegimeResults:
    """Perform regime discovery and assignment."""
    with ctx.timer.section("Regime Clustering"):
        # Extract features
        train_features = models.feature_extractor.transform(data.train)
        score_features = models.feature_extractor.transform(data.score)
        
        # Cluster (offline mode only)
        if ctx.mode == PipelineMode.OFFLINE:
            regime_model = discover_regimes(train_features, ctx.cfg)
        else:
            regime_model = load_active_regime_model(ctx.equip_id)
        
        # Assign labels
        train_labels = regime_model.predict(train_features)
        score_labels = regime_model.predict(score_features)
        
        # Quality assessment
        quality = assess_regime_quality(regime_model, score_features)
        
        return RegimeResults(
            train_labels=train_labels,
            score_labels=score_labels,
            regime_model=regime_model,
            regime_centroids=regime_model.cluster_centers_,
            regime_quality=quality,
            n_regimes=regime_model.n_clusters
        )
```

**Benefits**:
- Clean separation of regime logic
- Mode-aware (offline vs online)
- ~200 lines extracted

---

#### 1.3.6 Scoring & Fusion Block (Lines ~2535-2785, ~250 lines)
**EXTRACT TO**: `_score_and_fuse(data: DataLoadResult, models: ModelBundle, regimes: RegimeResults, ctx: PipelineContext) -> ScoredFrame`

**Current Code Pattern**:
```python
def main():
    # ... regime clustering ...
    
    # Scoring
    with T.section("Detector Scoring"):
        ar1_scores = ar1.score(score)
        pca_spe_scores = pca.score_spe(score)
        pca_t2_scores = pca.score_t2(score)
        # ... etc
        
        # Z-score normalization
        ar1_z = (ar1_scores - ar1_mean) / ar1_std
        # ... etc
    
    # Fusion
    with T.section("Fusion"):
        weights = cfg['fusion']['weights']
        fused_z = (
            weights['ar1'] * ar1_z +
            weights['pca_spe'] * pca_spe_z +
            # ... etc
        )
        
        # ... 150 more lines ...
```

**Proposed Extraction**:
```python
@dataclass
class ScoredFrame:
    """Scored and fused detector outputs."""
    df: pd.DataFrame  # Contains all detector z-scores + fused_z
    fused_z: pd.Series
    health_index: pd.Series
    detector_weights: Dict[str, float]
    fusion_quality: float

def _score_and_fuse(
    data: DataLoadResult,
    models: ModelBundle,
    regimes: RegimeResults,
    ctx: PipelineContext
) -> ScoredFrame:
    """Score all detectors and fuse into unified health metric."""
    with ctx.timer.section("Scoring & Fusion"):
        # Score all detectors
        scores_dict = {}
        for name, detector in models.detectors.items():
            scores_dict[f"{name}_z"] = detector.score(data.score)
        
        # Create scores DataFrame
        df = pd.DataFrame(scores_dict, index=data.score.index)
        df['regime_label'] = regimes.score_labels
        
        # Fusion
        weights = ctx.cfg['fusion']['weights']
        fused_z = fuse.weighted_fusion(df, weights)
        
        # Health index
        health_index = _health_index(fused_z)
        
        df['fused_z'] = fused_z
        df['health'] = health_index
        
        return ScoredFrame(
            df=df,
            fused_z=fused_z,
            health_index=health_index,
            detector_weights=weights,
            fusion_quality=assess_fusion_quality(df)
        )
```

**Benefits**:
- Unified scoring interface
- Clean fusion logic
- ~250 lines extracted

---

#### 1.3.7 Output Generation Block (Lines ~3135-3935, ~800 lines!)
**EXTRACT TO**: Multiple smaller functions

**Current Code Pattern**:
```python
def main():
    # ... scoring ...
    
    # Generate 20+ output tables
    with T.section("Output Generation"):
        # Health timeline
        health_df = pd.DataFrame(...)
        output_mgr.write_dataframe(health_df, sql_table="ACM_HealthTimeline")
        
        # Regime timeline
        regime_df = pd.DataFrame(...)
        output_mgr.write_dataframe(regime_df, sql_table="ACM_RegimeTimeline")
        
        # ... 18 more tables ...
        # ... 750 more lines ...
```

**Proposed Extraction**:
```python
def _generate_core_outputs(
    scored: ScoredFrame,
    ctx: PipelineContext
) -> None:
    """Generate TIER 1 core pipeline outputs."""
    with ctx.timer.section("Core Outputs"):
        # ACM_Scores_Wide
        ctx.output_mgr.write_scores(scored.df, enable_sql=True)
        
        # ACM_HealthTimeline
        health_df = _build_health_timeline(scored)
        ctx.output_mgr.write_dataframe(health_df, sql_table="ACM_HealthTimeline")
        
        # ACM_RegimeTimeline
        regime_df = _build_regime_timeline(scored, regimes)
        ctx.output_mgr.write_dataframe(regime_df, sql_table="ACM_RegimeTimeline")

def _generate_diagnostic_outputs(
    scored: ScoredFrame,
    episodes: Episodes,
    ctx: PipelineContext
) -> None:
    """Generate TIER 4 diagnostic outputs."""
    with ctx.timer.section("Diagnostic Outputs"):
        # ACM_SensorDefects
        defects_df = _build_sensor_defects(scored)
        ctx.output_mgr.write_dataframe(defects_df, sql_table="ACM_SensorDefects")
        
        # ACM_EpisodeCulprits
        write_episode_culprits_enhanced(episodes, scored, ctx.sql_client, ctx.run_id)
```

**Benefits**:
- Organized by tier
- Testable table builders
- ~800 lines extracted into 10+ focused functions

---

#### 1.3.8 Forecasting Block (Lines ~3935-4235, ~300 lines)
**EXTRACT TO**: `_run_forecasting(scored: ScoredFrame, ctx: PipelineContext) -> ForecastResults`

**Current Code Pattern**:
```python
def main():
    # ... output generation ...
    
    # Forecasting
    with T.section("Forecasting"):
        forecast_engine = ForecastEngine(cfg, sql_client, equip_id)
        
        # RUL estimation
        rul_results = forecast_engine.estimate_rul(...)
        output_mgr.write_dataframe(rul_results, sql_table="ACM_RUL")
        
        # Health forecasting
        health_forecast = forecast_engine.forecast_health(...)
        output_mgr.write_dataframe(health_forecast, sql_table="ACM_HealthForecast")
        
        # ... 250 more lines ...
```

**Proposed Extraction**:
```python
@dataclass
class ForecastResults:
    """Results from forecasting stage."""
    rul: pd.DataFrame
    health_forecast: pd.DataFrame
    failure_forecast: pd.DataFrame
    sensor_forecasts: pd.DataFrame
    confidence: float

def _run_forecasting(
    scored: ScoredFrame,
    ctx: PipelineContext
) -> ForecastResults:
    """Execute all forecasting models."""
    with ctx.timer.section("Forecasting"):
        engine = ForecastEngine(ctx.cfg, ctx.sql_client, ctx.equip_id)
        
        # RUL
        rul = engine.estimate_rul(
            health=scored.health_index,
            regimes=scored.df['regime_label']
        )
        
        # Health trajectory
        health_forecast = engine.forecast_health(scored.health_index)
        
        # Failure probability
        failure_forecast = engine.forecast_failure(scored.health_index)
        
        # Sensor forecasts
        sensor_forecasts = engine.forecast_sensors(scored.df)
        
        return ForecastResults(
            rul=rul,
            health_forecast=health_forecast,
            failure_forecast=failure_forecast,
            sensor_forecasts=sensor_forecasts,
            confidence=engine.get_confidence()
        )
```

**Benefits**:
- Clean forecasting interface
- All forecasts in one place
- ~300 lines extracted

---

#### 1.3.9 Finalization Block (Lines ~4535-4685, ~150 lines)
**EXTRACT TO**: `_finalize_run(ctx: PipelineContext, outcome: str, stats: Dict) -> None`

**Current Code Pattern**:
```python
def main():
    # ... forecasting ...
    
    # Finalization
    finally:
        # Timer stats
        timer_stats = T.get_stats()
        write_timer_stats(timer_stats, sql_client, run_id)
        
        # Run metadata
        _sql_finalize_run(sql_client, run_id, outcome)
        
        # SQL cleanup
        sql_client.commit()
        sql_client.close()
        
        # Observability shutdown
        shutdown_observability()
        
        # ... 100 more lines ...
```

**Proposed Extraction**:
```python
def _finalize_run(
    ctx: PipelineContext,
    outcome: str,
    stats: Dict[str, Any]
) -> None:
    """Finalize run with cleanup and logging."""
    try:
        # Log timer stats
        write_timer_stats(ctx.timer.get_stats(), ctx.sql_client, ctx.run_id)
        
        # Update run status
        _sql_finalize_run(ctx.sql_client, ctx.run_id, outcome, stats)
        
        # Commit transaction
        if ctx.sql_client:
            ctx.sql_client.commit()
        
    finally:
        # Cleanup
        if ctx.sql_client:
            ctx.sql_client.close()
        
        # Observability shutdown
        shutdown_observability()
        
        Console.info(f"Run {ctx.run_id} finalized: {outcome}")
```

**Benefits**:
- Clean shutdown logic
- Guaranteed cleanup
- ~150 lines extracted

---

### 1.4 Refactored main() Target

**After All Extractions**:
```python
def main() -> None:
    """
    ACM v11.0.0 Pipeline Orchestrator
    
    Coordinates 15 pipeline stages for anomaly detection and RUL estimation.
    Each stage is self-contained and testable.
    """
    ctx = None
    outcome = "FAIL"
    stats = {}
    
    try:
        # Stage 1: Initialization
        ctx = _initialize_pipeline(parse_args())
        
        # Stage 2: Data Loading
        data = _load_pipeline_data(ctx)
        
        # Stage 3: Model Loading
        models = _load_or_fit_models(data, ctx)
        
        # Stage 4: Regime Clustering
        regimes = _cluster_regimes(data, models, ctx)
        
        # Stage 5: Scoring & Fusion
        scored = _score_and_fuse(data, models, regimes, ctx)
        
        # Stage 6: Episode Detection
        episodes = _detect_episodes(scored, ctx)
        
        # Stage 7: Health & Drift
        health_drift = _calculate_health_drift(scored, ctx)
        
        # Stage 8: Auto-Tuning
        tuning = _auto_tune_pipeline(scored, ctx)
        
        # Stage 9: Baseline Buffer Update
        _update_baseline_buffer(scored, ctx)
        
        # Stage 10: Core Outputs
        _generate_core_outputs(scored, ctx)
        
        # Stage 11: Diagnostic Outputs
        _generate_diagnostic_outputs(scored, episodes, ctx)
        
        # Stage 12: Forecasting
        forecasts = _run_forecasting(scored, ctx)
        
        # Stage 13: Forecast Outputs
        _write_forecast_outputs(forecasts, ctx)
        
        # Stage 14: Run Statistics
        stats = _collect_run_stats(data, models, scored, episodes, forecasts)
        
        outcome = "OK"
        
    except KeyboardInterrupt:
        Console.warn("Pipeline interrupted by user")
        outcome = "INTERRUPTED"
        
    except Exception as e:
        Console.error(f"Pipeline failed: {e}")
        if ctx:
            record_error(ctx.equip_id, str(e), type(e).__name__)
        outcome = "FAIL"
        raise
        
    finally:
        # Stage 15: Finalization
        if ctx:
            _finalize_run(ctx, outcome, stats)
```

**Result**:
- main() reduced from 3,311 lines → ~150 lines (95% reduction!)
- 15 focused stage functions (~200-300 lines each)
- Type-safe data contracts between stages
- Comprehensive error handling
- Testable in isolation

---

## Part 2: output_manager.py Analysis

### 2.1 Current State

**Status**: ✅ Already well-refactored  
**Lines**: 2,589 (down from 5,111 - 49% reduction!)  
**Key Improvements Made**:
- Consolidated ALLOWED_TABLES (12 core tables vs 50+ previously)
- Removed many deprecated analytics methods
- Simplified table generation logic

### 2.2 Remaining Issues

#### 2.2.1 CSV Mode Remnants
**Location**: Throughout file  
**Issue**: Still has file mode support despite SQL-only architecture

**Evidence**:
```python
# Line 6: Docstring mentions CSV
"Single point of control for all CSV, JSON, and model outputs"

# File mode logic still present
if not sql_table:
    # File mode handling...
```

**Action Needed**:
- Remove all CSV references from docstrings
- Remove file mode fallback logic
- Enforce SQL-only mode

#### 2.2.2 Deprecated Analytics Methods
**Location**: Various  
**Issue**: Some analytics methods may still exist for deprecated tables

**Action Needed**:
- Audit all methods against ALLOWED_TABLES
- Remove methods for tables not in v11 schema
- Update method signatures to match v11 contracts

---

## Part 3: Detailed Task List

### 3.1 Wave 4: Main Function Extraction (High Priority)

#### Task 4.1: Initialize Pipeline Stage
- [ ] Create PipelineContext dataclass in core/pipeline_types.py
- [ ] Extract _initialize_pipeline() function (~100 lines)
- [ ] Update main() to use new function
- [ ] Add unit tests for initialization
- [ ] Test: Verify context object correctness

#### Task 4.2: Data Loading Stage
- [ ] Create DataLoadResult dataclass in core/pipeline_types.py
- [ ] Extract _load_pipeline_data() function (~150 lines)
- [ ] Remove CSV mode entirely
- [ ] Update main() to use new function
- [ ] Add unit tests for data loading
- [ ] Test: Verify SQL-only mode works

#### Task 4.3: Model Loading Stage
- [ ] Create ModelBundle dataclass in core/pipeline_types.py
- [ ] Extract _load_or_fit_models() function (~250 lines)
- [ ] Integrate with existing model registry
- [ ] Update main() to use new function
- [ ] Add unit tests for model caching
- [ ] Test: Verify cache hit/miss behavior

#### Task 4.4: Regime Clustering Stage
- [ ] Create RegimeResults dataclass in core/pipeline_types.py
- [ ] Extract _cluster_regimes() function (~200 lines)
- [ ] Integrate with ActiveModelsManager
- [ ] Update main() to use new function
- [ ] Add unit tests for regime discovery
- [ ] Test: Verify offline/online mode switching

#### Task 4.5: Scoring & Fusion Stage
- [ ] Create ScoredFrame dataclass in core/pipeline_types.py
- [ ] Extract _score_and_fuse() function (~250 lines)
- [ ] Standardize detector scoring interface
- [ ] Update main() to use new function
- [ ] Add unit tests for fusion logic
- [ ] Test: Verify weighted fusion correctness

#### Task 4.6: Output Generation Stages
- [ ] Extract _generate_core_outputs() function (~200 lines)
- [ ] Extract _generate_diagnostic_outputs() function (~200 lines)
- [ ] Extract _generate_forecasting_outputs() function (~100 lines)
- [ ] Create individual table builder functions
- [ ] Update main() to use new functions
- [ ] Add unit tests for table generation
- [ ] Test: Verify all ALLOWED_TABLES populated

#### Task 4.7: Forecasting Stage
- [ ] Create ForecastResults dataclass in core/pipeline_types.py
- [ ] Extract _run_forecasting() function (~300 lines)
- [ ] Integrate with ForecastEngine
- [ ] Update main() to use new function
- [ ] Add unit tests for forecasting
- [ ] Test: Verify RUL, health, failure forecasts

#### Task 4.8: Finalization Stage
- [ ] Extract _finalize_run() function (~150 lines)
- [ ] Ensure cleanup always runs
- [ ] Update main() to use new function
- [ ] Add unit tests for cleanup
- [ ] Test: Verify proper resource release

#### Task 4.9: Refactored Main Function
- [ ] Rewrite main() as orchestrator (~150 lines)
- [ ] Add stage-level error handling
- [ ] Add comprehensive logging
- [ ] Update documentation
- [ ] Add integration tests for full pipeline
- [ ] Test: End-to-end pipeline execution

---

### 3.2 Wave 5: CSV Removal (High Priority)

#### Task 5.1: Remove CSV from acm_main.py
- [ ] Remove --train-csv, --score-csv CLI arguments
- [ ] Remove CSV path override logic
- [ ] Remove file mode detection
- [ ] Update _sql_mode() to always return True
- [ ] Remove filesystem path variables
- [ ] Update docstrings to remove CSV references

#### Task 5.2: Remove CSV from output_manager.py
- [ ] Update module docstring (remove CSV mention)
- [ ] Remove file mode logic from write methods
- [ ] Remove file path parameters
- [ ] Update all method signatures for SQL-only
- [ ] Remove _read_csv_with_peek() function
- [ ] Update docstrings

#### Task 5.3: Validation
- [ ] Test: Verify CSV mode raises error
- [ ] Test: Verify all writes go to SQL
- [ ] Test: Verify no file artifacts created
- [ ] Update documentation

---

### 3.3 Wave 6: Documentation & Testing (Medium Priority)

#### Task 6.1: Update Documentation
- [ ] Update V11_ARCHITECTURE.md with new pipeline stages
- [ ] Update V11_MIGRATION_GUIDE.md with breaking changes
- [ ] Create PIPELINE_STAGES.md documenting each stage
- [ ] Update ACM_SYSTEM_OVERVIEW.md
- [ ] Update .github/copilot-instructions.md

#### Task 6.2: Unit Tests
- [ ] Test _initialize_pipeline()
- [ ] Test _load_pipeline_data()
- [ ] Test _load_or_fit_models()
- [ ] Test _cluster_regimes()
- [ ] Test _score_and_fuse()
- [ ] Test _run_forecasting()
- [ ] Test _finalize_run()
- [ ] Target: >80% coverage for new functions

#### Task 6.3: Integration Tests
- [ ] Test full pipeline (cold-start mode)
- [ ] Test full pipeline (online mode)
- [ ] Test error handling
- [ ] Test resource cleanup
- [ ] Test observability integration

---

## Part 4: Risk Analysis

### 4.1 High-Risk Changes

**Risk 1: Breaking Pipeline Execution**
- **Probability**: Medium
- **Impact**: High (pipeline fails completely)
- **Mitigation**:
  - Extract one stage at a time
  - Test each extraction independently
  - Use feature flags for gradual rollout

**Risk 2: Performance Degradation**
- **Probability**: Low
- **Impact**: Medium (slower run times)
- **Mitigation**:
  - Benchmark before/after each extraction
  - Profile with Pyroscope
  - Optimize hot paths

**Risk 3: SQL Schema Incompatibility**
- **Probability**: Very Low
- **Impact**: High (SQL writes fail)
- **Mitigation**:
  - Verify ALLOWED_TABLES matches actual schema
  - Test all table writes
  - Use transactions for rollback safety

---

## Part 5: Timeline & Prioritization

### Phase 1: Core Extractions (Week 1)
- Task 4.1: Initialize Pipeline
- Task 4.2: Data Loading
- Task 4.3: Model Loading
- Task 5.1: Remove CSV from acm_main.py

**Goal**: Foundation for modular pipeline

### Phase 2: Pipeline Stages (Week 2)
- Task 4.4: Regime Clustering
- Task 4.5: Scoring & Fusion
- Task 4.7: Forecasting
- Task 5.2: Remove CSV from output_manager.py

**Goal**: Core pipeline logic extracted

### Phase 3: Outputs & Finalization (Week 3)
- Task 4.6: Output Generation
- Task 4.8: Finalization
- Task 4.9: Refactored Main
- Task 5.3: CSV Removal Validation

**Goal**: Complete extraction, CSV removal

### Phase 4: Testing & Documentation (Week 4)
- Task 6.1: Update Documentation
- Task 6.2: Unit Tests
- Task 6.3: Integration Tests

**Goal**: Comprehensive validation, docs

---

## Part 6: Success Metrics

### Code Quality Metrics
- **acm_main.py main()**: 3,311 → 150 lines (95% reduction)
- **Cyclomatic Complexity**: main() <20 (from ~150+)
- **Test Coverage**: >80% for extracted functions
- **Function Size**: No function >200 lines

### Performance Metrics
- **Run Time**: Within ±5% of baseline
- **Memory Usage**: Within ±10% of baseline
- **SQL Writes**: No increase in transaction count
- **Error Rate**: <0.1% (same as baseline)

### Maintainability Metrics
- **Time to Add Feature**: 40% reduction (easier to locate logic)
- **Code Review Time**: 50% reduction (smaller functions)
- **Onboarding Time**: 30% reduction (clearer structure)
- **Bug Fix Time**: 30% reduction (isolated stages)

---

## Part 7: Implementation Examples

### 7.1 Pipeline Stage Pattern

```python
# core/pipeline_types.py
from dataclasses import dataclass
from typing import Any, Dict, Optional
import pandas as pd
from enum import Enum

class PipelineMode(Enum):
    """Pipeline execution mode."""
    OFFLINE = "offline"  # Regime discovery, full training
    ONLINE = "online"    # Regime assignment only, incremental

@dataclass
class PipelineContext:
    """Shared context for all pipeline stages."""
    args: Any
    cfg: Dict[str, Any]
    sql_client: Any
    output_mgr: Any
    run_id: str
    equip_id: int
    equipment: str
    batch_num: int
    tracer: Any
    meter: Any
    timer: Any
    mode: PipelineMode
    
    @staticmethod
    def detect_mode(args, cfg) -> PipelineMode:
        """Detect pipeline mode from args and config."""
        if args.batch_num == 0:
            return PipelineMode.OFFLINE
        return PipelineMode.ONLINE

@dataclass
class StageResult:
    """Base class for stage results."""
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
```

### 7.2 Error Handling Pattern

```python
def main() -> None:
    """Orchestrator with comprehensive error handling."""
    ctx = None
    outcome = "FAIL"
    
    try:
        # Critical stages (fail fast)
        ctx = _initialize_pipeline(parse_args())
        data = _load_pipeline_data(ctx)
        
        # Recoverable stages (graceful degradation)
        try:
            models = _load_or_fit_models(data, ctx)
        except Exception as e:
            Console.warn(f"Model loading failed, using defaults: {e}")
            models = create_default_models(data.train, ctx.cfg)
        
        # ... other stages ...
        
        outcome = "OK"
        
    except KeyboardInterrupt:
        outcome = "INTERRUPTED"
        Console.warn("Pipeline interrupted by user")
        
    except Exception as e:
        outcome = "FAIL"
        Console.error(f"Pipeline failed: {e}")
        if ctx:
            record_error(ctx.equip_id, str(e), type(e).__name__)
        raise
        
    finally:
        if ctx:
            _finalize_run(ctx, outcome, {})
```

### 7.3 Testing Pattern

```python
# tests/test_pipeline_stages.py
import pytest
from core.acm_main import _initialize_pipeline, _load_pipeline_data

class TestPipelineStages:
    
    @pytest.fixture
    def mock_args(self):
        """Create mock arguments."""
        return MockNamespace(
            equip="TEST_EQUIP",
            config_path="configs/config_table.csv",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-02T00:00:00"
        )
    
    def test_initialize_pipeline(self, mock_args):
        """Test pipeline initialization."""
        ctx = _initialize_pipeline(mock_args)
        
        assert ctx.equipment == "TEST_EQUIP"
        assert ctx.sql_client is not None
        assert ctx.run_id is not None
        assert ctx.mode in [PipelineMode.OFFLINE, PipelineMode.ONLINE]
    
    def test_load_pipeline_data(self, mock_args):
        """Test data loading stage."""
        ctx = _initialize_pipeline(mock_args)
        data = _load_pipeline_data(ctx)
        
        assert len(data.train) > 0
        assert len(data.score) > 0
        assert data.contract.is_valid
        assert data.meta.n_rows > 0
```

---

## Conclusion

This audit identifies **3,311 lines in main()** (70% of acm_main.py) that can be extracted into 15 focused pipeline stages. The refactoring plan provides:

1. **Wave 4**: Extract 15 pipeline stages from main() (~2,800 lines)
2. **Wave 5**: Remove all CSV remnants (~200 lines)
3. **Wave 6**: Add comprehensive testing and documentation

**Estimated effort**: 4 weeks with proper testing and validation.

**Expected outcome**:
- main() reduced from 3,311 → 150 lines (95% reduction)
- 15 testable pipeline stages
- Zero CSV dependencies
- Comprehensive test coverage (>80%)
- Complete v11.0.0 refactoring

**Current State Summary**:
- ✅ output_manager.py: Already well-refactored (49% reduction)
- ✅ Wave 3 helpers: 10+ functions extracted
- 🟡 main() function: Still needs extraction (3,311 lines)
- ❌ CSV mode: Still present, needs removal
- ❌ Testing: Gaps in coverage for new helpers

**Next Steps**:
1. Start with Wave 4, Task 4.1 (Initialize Pipeline)
2. Extract one stage at a time
3. Test each extraction independently
4. Remove CSV mode in parallel (Wave 5)
5. Add comprehensive tests (Wave 6)

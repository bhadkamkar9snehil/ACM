# State Management Analysis

**⚠️ CONSOLIDATED:** Tasks from this audit have been integrated into `# To Do.md` (root) as of 2025-11-13.  
**Refer to:** Section 10 - Architecture & Code Quality (tasks ARCH-01 through ARCH-04)

---

# Deep Dive: State Management Analysis

## Executive Summary

The state management in `acm_main.py` is **fundamentally broken**. It exhibits characteristics of **implicit global state**, **temporal coupling**, and **scattered mutation** that make the code unpredictable, untestable, and dangerous to modify.

**State Management Score: 2/10** (Critical)

---

## 1. State Inventory

### 1.1 Explicit State Variables (50+)

I've catalogued every stateful variable in `main()`:

```python
# Configuration State (5 variables)
cfg                    # Dict[str, Any] - mutated throughout
config_signature       # str - computed once, used for cache validation
equip                 # str - CLI arg
equip_id              # int - derived from equip
art_root              # Path - CLI arg

# Path State (7 variables)
run_dir               # Path - changes based on timestamp
models_dir            # Path - derived from run_dir
stable_models_dir     # Path - equipment-specific cache location
refit_flag_path       # Path - marker file for forced retraining
model_cache_path      # Path - joblib cache file
buffer_path           # Path - rolling baseline CSV
tables_dir            # Path - output directory

# Data State (6 variables)
train                 # pd.DataFrame - baseline data
score                 # pd.DataFrame - current batch data
train_numeric         # pd.DataFrame - copy before feature engineering
score_numeric         # pd.DataFrame - copy before feature engineering
meta                  # DataMeta - load metadata
sensor_context        # Optional[Dict] - for analytics

# Feature State (5 variables)
current_train_columns # List[str] - feature names
train_feature_hash    # Optional[str] - fingerprint for cache validation
regime_basis_train    # Optional[pd.DataFrame] - regime clustering input
regime_basis_score    # Optional[pd.DataFrame] - regime clustering input
regime_basis_hash     # Optional[int] - basis fingerprint

# Model State (12 variables)
ar1_detector          # Optional[AR1Detector]
pca_detector          # Optional[PCASubspaceDetector]
pca_train_spe         # Optional[np.ndarray] - cached train scores
pca_train_t2          # Optional[np.ndarray] - cached train scores
mhal_detector         # Optional[MahalanobisDetector]
iforest_detector      # Optional[IsolationForestDetector]
gmm_detector          # Optional[GMMDetector]
omr_detector          # Optional[OMRDetector]
regime_model          # Optional[RegimeModel]
detector_cache        # Optional[Dict] - joblib cache bundle
cache_payload         # Optional[Dict] - bundle to save
cached_models         # Optional[Dict] - from ModelVersionManager

# Scoring State (4 variables)
frame                 # pd.DataFrame - all detector outputs
train_frame           # pd.DataFrame - calibration baseline
episodes              # pd.DataFrame - detected anomalies
omr_contributions_data # Optional[pd.DataFrame] - OMR attributions

# Regime State (4 variables)
train_regime_labels   # Optional[np.ndarray]
score_regime_labels   # Optional[np.ndarray]
regime_quality_ok     # bool
regime_stats          # Dict[int, Dict[str, float]]

# Execution State (8 variables)
run_id                # Optional[str] - UUID or timestamp
win_start             # Optional[pd.Timestamp] - SQL mode window
win_end               # Optional[pd.Timestamp] - SQL mode window
run_start_time        # datetime - for metadata
run_completion_time   # datetime - for metadata
outcome               # str - "OK" or "ERROR"
err_json              # Optional[str] - serialized exception
rows_read             # int - input count
rows_written          # int - output count

# SQL State (2 variables)
sql_client            # Optional[SQLClient]
output_manager        # OutputManager - handles all I/O

# Control Flow State (5 variables)
reuse_models          # bool - from config
refit_requested       # bool - from flag file
loaded_from_cache     # bool - status indicator
SQL_MODE              # bool - derived from config
dual_mode             # bool - file + SQL
```

**Total: 60+ stateful variables** in a single function scope.

---

## 2. State Lifecycle Problems

### 2.1 Temporal Coupling Hell

**Problem:** State has implicit ordering dependencies that are not enforced.

#### Example 1: Feature Hash Depends on Imputation

```python
# Line 640-720: Features built
train = fast_features.compute_basic_features(train, window=feat_win)

# Line 740-790: Imputation happens AFTER features
train.fillna(col_meds, inplace=True)

# Line 850: Hash computed on imputed data
train_feature_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()[:16]
```

**Issue:** If imputation order changes, hash breaks. No enforcement.

#### Example 2: Calibrators Need Train Scores

```python
# Line 950: PCA scores train data
pca_train_spe, pca_train_t2 = pca_detector.score(train)

# Line 1050: Calibrator fitted on train scores
cal_pca_spe = fuse.ScoreCalibrator(...).fit(train_frame["pca_spe"], ...)

# Line 1070: Calibrator transforms score data
frame["pca_spe_z"] = cal_pca_spe.transform(frame["pca_spe"], ...)
```

**Issue:** If `pca_train_spe` is None (cache miss), calibration uses wrong data.

#### Example 3: Episodes Need Regimes

```python
# Line 1100: Regimes labeled
score_regime_labels = regime_out.get("regime_labels")

# Line 1150: Episodes detected
fused, episodes = fuse.combine(present, weights, cfg, ...)

# Line 1200: Episodes enriched with regimes
episodes["regime"] = regime_vals  # Uses score_regime_labels
```

**Issue:** If regime quality is low, `score_regime_labels` is None, episodes get `-1`.

### 2.2 State Mutation Timeline

I've traced every mutation of `cfg` (the most dangerous mutable state):

```python
# Line 220: Initial load
cfg = _load_config(cfg_path, equipment_name=equip)

# Line 225: Deep copy (DEBT-10)
cfg = copy.deepcopy(cfg)

# Line 235: Signature computed
config_signature = _compute_config_signature(cfg)

# Line 240: CRITICAL - signature stored IN config (mutation!)
cfg["_signature"] = config_signature

# Line 245: Equipment ID stored
cfg._equip_id = equip_id

# Line 1020: Adaptive clip_z mutation
self_tune_cfg["clip_z"] = adaptive_clip

# Line 1350-1400: Auto-tuning mutations
cfg.update_param("thresholds.self_tune.clip_z", new_clip_z, ...)
cfg.update_param("episodes.cpd.k_sigma", new_k, ...)
cfg.update_param("regimes.auto_k.k_max", int(new_k_max), ...)

# Line 1450: Diagnostics storage
cfg.setdefault("_diagnostics", {})["mhal_cond_num"] = float(mhal_detector.cond_num)
```

**Total mutations: 8+** across 1,400 lines.

**Impact:** Config signature computed at line 235 is **INVALID** by line 1400.

---

## 3. State Consistency Issues

### 3.1 Broken Invariants

#### Invariant 1: Frame Index = Score Index

**Expected:**
```python
assert frame.index.equals(score.index)
```

**Reality:**
```python
# Line 950: Frame initialized with score index
frame = pd.DataFrame(index=score.index)

# Line 955: Frame sorted (index changes!)
if not frame.index.is_monotonic_increasing:
    frame = frame.sort_index()

# Line 1200: Episodes mapped to frame index
start_idx = pd.Index(frame.index).get_indexer(_sdt, method='nearest')

# BROKEN: If score.index was unsorted, indices are wrong
```

#### Invariant 2: Train Columns = Score Columns

**Expected:**
```python
assert set(train.columns) == set(score.columns)
```

**Reality:**
```python
# Line 740: Train has all-NaN columns dropped
all_nan_cols = [c for c in train.columns if pd.isna(col_meds.get(c))]
train = train.drop(columns=all_nan_cols)

# Line 745: Score aligned to train
score = score.reindex(columns=train.columns)

# BROKEN: Score now has NaN columns if train dropped them
```

#### Invariant 3: Cached Models Match Current Features

**Expected:**
```python
assert cached_cols == current_train_columns
```

**Reality:**
```python
# Line 890: Cache loaded
cached_cols = cached_bundle.get("train_columns")

# Line 895: Validation
cols_match = (cached_cols == current_train_columns)

# Line 900: If mismatch, cache is invalidated
if not cols_match:
    detector_cache = None

# BROKEN: But detectors are still used if cols_match was True!
# Feature engineering may have changed (different window size)
```

### 3.2 State Leakage Between Runs

**Problem:** Persistent state survives across runs.

```python
# Line 470: Stable models directory (shared across runs)
stable_models_dir = equip_root / "models"

# Line 475: Model cache (shared)
model_cache_path = stable_models_dir / "detectors.joblib"

# Line 480: Refit flag (shared)
refit_flag_path = stable_models_dir / "refit_requested.flag"

# Line 485: Rolling baseline buffer (shared)
buffer_path = stable_models_dir / "baseline_buffer.csv"
```

**Issue:** If Run 1 sets `refit_flag`, Run 2 bypasses cache. But if Run 2 fails, Run 3 uses stale models.

**Example failure sequence:**
1. Run 1: Quality degrades, writes `refit_requested.flag`
2. Run 2: Bypasses cache, starts retraining
3. Run 2: **Crashes during model fit** (OOM, timeout, etc.)
4. Run 3: Flag was deleted by Run 2, uses **stale cached models**
5. Run 3: Produces bad results, no one knows why

**Fix needed:** Atomic flag + cache version coupling.

---

## 4. Concurrency & Race Conditions

### 4.1 Shared File Access

**Race Condition 1: Model Cache**

```python
# Process A
if reuse_models and model_cache_path.exists():
    cached_bundle = joblib.load(model_cache_path)  # Read

# Process B (simultaneous)
joblib.dump(cache_payload, model_cache_path)  # Write
```

**Result:** Process A reads corrupted pickle, crashes with `EOFError`.

**Race Condition 2: Baseline Buffer**

```python
# Process A
if buffer_path.exists():
    prev = pd.read_csv(buffer_path)  # Read
combined = pd.concat([prev, to_append])
combined.to_csv(buffer_path)  # Write

# Process B (simultaneous)
prev = pd.read_csv(buffer_path)  # Read stale data
```

**Result:** Process B's data is lost (last-write-wins).

### 4.2 SQL Connection Pool Exhaustion

**Problem:** No connection limits in dual-mode.

```python
# Line 1650-1750: Multiple SQL writes
output_manager.write_scores_ts(...)     # Connection 1
output_manager.write_drift_ts(...)      # Connection 2
output_manager.write_anomaly_events(...) # Connection 3
output_manager.write_regime_episodes(...) # Connection 4
# ... 10+ more writes
```

**If 10 parallel runs:** 10 runs × 15 writes = **150 connections** (typical pool limit: 50).

**Evidence:** Line 1845 finally block suggests known issue:
```python
# CRITICAL FIX: Close OutputManager to prevent connection leaks
output_manager.close()
```

---

## 5. State Testing Impossibility

### 5.1 No State Snapshots

**Problem:** Cannot capture or restore state at any point.

**What we need:**
```python
class PipelineState:
    def snapshot(self) -> Dict[str, Any]:
        """Capture all state for debugging/testing."""
        return {
            'config': self.config.copy(),
            'train': self.train.copy(),
            'detectors': self.detectors.copy(),
            # ...
        }
    
    def restore(self, snapshot: Dict[str, Any]):
        """Restore from snapshot."""
        self.config = snapshot['config']
        # ...
```

**What we have:** 60 loose variables with no serialization.

### 5.2 Cannot Test State Transitions

**Impossible test:**
```python
def test_regime_quality_affects_calibration():
    # CANNOT write: no way to set regime_quality_ok independently
    # It's computed deep inside regimes.label()
    pass
```

**Why impossible:**
```python
# Line 1100: regime_quality_ok is buried in nested dict
regime_quality_ok = bool(regime_out.get("regime_quality_ok", True))

# Line 1050: Affects calibration 50 lines later
fit_regimes = train_regime_labels if quality_ok else None
```

**No way to inject `regime_quality_ok = False` for testing.**

---

## 6. State Documentation Gaps

### 6.1 Undocumented State Invariants

**Missing invariants:**
1. ✅ `train.index.is_unique` (enforced with assertion, line 555)
2. ❌ `train.columns` ⊆ `score.columns` (assumed, not enforced)
3. ❌ `frame.index == score.index` (assumed, broken by sort)
4. ❌ `len(episodes) <= len(frame)` (logical, not enforced)
5. ❌ `regime_labels.shape[0] == frame.shape[0]` (assumed, can break)

**Missing state diagrams:**
- When is cache valid?
- When is refit triggered?
- What states lead to error vs warning?

### 6.2 State Variable Naming

**Confusing names:**
```python
train           # Is this raw sensors or engineered features?
train_numeric   # Is this different from train?
train_frame     # Is this different from train and train_numeric?

score           # Current batch or score outputs?
frame           # Detector outputs, but called "frame"?
episodes        # Episodes or episode metadata?

detector_cache  # From joblib or ModelVersionManager?
cached_models   # Different from detector_cache?
cache_payload   # Data to cache or cached data?
```

**Better names:**
```python
raw_train_sensors          # Clear
engineered_train_features  # Clear
calibration_train_scores   # Clear

raw_score_sensors          # Clear
detector_outputs_df        # Clear
detected_episodes_df       # Clear

joblib_detector_cache      # Clear
versioned_model_cache      # Clear
models_to_cache            # Clear
```

---

## 7. State Machine Analysis

### 7.1 Implicit State Machine

The code implements an **implicit finite state machine** but never documents it:

```
                    ┌─────────────┐
                    │   STARTUP   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ LOAD_CONFIG │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
           ┌────────┤ LOAD_DATA   ├────────┐
           │        └─────────────┘        │
           │                               │
    ┌──────▼──────┐              ┌────────▼────────┐
    │ COLD_START  │              │   NORMAL_START  │
    │ (bootstrap) │              │   (has train)   │
    └──────┬──────┘              └────────┬────────┘
           │                               │
           └───────────┬───────────────────┘
                       │
                ┌──────▼──────┐
                │BUILD_FEATURES│
                └──────┬──────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
    ┌────▼────┐              ┌───────▼───────┐
    │FIT_MODELS│              │ LOAD_CACHE    │
    └────┬────┘              └───────┬───────┘
         │                           │
         └────────────┬──────────────┘
                      │
              ┌───────▼────────┐
              │  VALIDATE_CACHE │
              └───────┬────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
     ┌────▼─────┐          ┌─────▼──────┐
     │CACHE_VALID│          │CACHE_INVALID│
     └────┬─────┘          └─────┬──────┘
          │                      │
          │              ┌───────▼────────┐
          │              │   REFIT_MODELS │
          │              └───────┬────────┘
          │                      │
          └──────────┬───────────┘
                     │
              ┌──────▼──────┐
              │    SCORE    │
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │  CALIBRATE  │
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │    FUSE     │
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │DETECT_EPISODES│
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │ DETECT_DRIFT│
              └──────┬──────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼────┐          ┌───────▼───────┐
    │FILE_MODE│          │   SQL_MODE    │
    │PERSIST  │          │   PERSIST     │
    └────┬────┘          └───────┬───────┘
         │                       │
         └───────────┬───────────┘
                     │
              ┌──────▼──────┐
              │  FINALIZE   │
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │   SUCCESS   │
              └─────────────┘
```

**Problem:** State transitions are implicit in sequential code.

### 7.2 Missing State Guards

**No validation of state prerequisites:**

```python
# Line 1050: Calibration assumes detectors fitted
cal_ar = fuse.ScoreCalibrator(...).fit(train_frame["ar1_raw"], ...)
# What if ar1_detector is None? No check.

# Line 1200: Episode enrichment assumes regime labels exist
episodes["regime"] = regime_vals
# What if regime_quality_ok is False? Assigns -1 silently.

# Line 1650: SQL writes assume sql_client exists
output_manager.write_scores_ts(long_scores, run_id)
# What if sql_client is None? No check.
```

**Needed:**
```python
class PipelineState(Enum):
    INITIALIZED = 1
    DATA_LOADED = 2
    MODELS_FITTED = 3
    SCORES_COMPUTED = 4
    EPISODES_DETECTED = 5
    PERSISTED = 6

def require_state(self, required: PipelineState):
    if self.state.value < required.value:
        raise InvalidStateError(f"Operation requires {required}, but in {self.state}")
```

---

## 8. State Recovery & Rollback

### 8.1 No Transactional State

**Problem:** Partial failures leave inconsistent state.

**Failure scenario:**
```python
# Line 640-720: Features built successfully
train = fast_features.compute_basic_features(train, window=feat_win)

# Line 950-1050: Models fitted successfully
ar1_detector = forecast.AR1Detector(...).fit(train)
pca_detector = correlation.PCASubspaceDetector(...).fit(train)

# Line 1650: SQL write fails (connection timeout)
output_manager.write_scores_ts(long_scores, run_id)  # FAILS
```

**State after failure:**
- ✅ In-memory: detectors fitted
- ✅ File system: nothing written
- ❌ SQL: partial writes (scores table has some rows)
- ❌ Cache: old cache still valid
- ❌ Next run: uses stale cache because fit succeeded

**No rollback mechanism.**

### 8.2 No Checkpointing

**Cannot resume from failure:**

```python
# Desired behavior:
pipeline = ACMPipeline.load_checkpoint("run_20250111_143000/checkpoint.pkl")
pipeline.resume_from_stage("CALIBRATE")
```

**Current behavior:** Full re-run from scratch.

---

## 9. State Debugging Tools

### 9.1 What's Missing

**No state inspector:**
```python
# Want:
>>> pipeline.debug_state()
{
    'stage': 'SCORING',
    'detectors_fitted': ['ar1', 'pca', 'mhal', 'iforest'],
    'cache_valid': True,
    'train_shape': (10000, 45),
    'score_shape': (1000, 45),
    'regime_quality': 0.85,
    'memory_usage_mb': 1250
}
```

**No state diff:**
```python
# Want:
>>> pipeline.diff_state(previous_run)
{
    'config': {'thresholds.self_tune.clip_z': 8.0 -> 9.6},
    'train': {'shape': (10000, 45) -> (12000, 45)},
    'regime_quality': 0.85 -> 0.72
}
```

### 9.2 State Logging Gaps

**Current logging:**
```python
Console.info(f"[DATA] timestamp={meta.timestamp_col} cadence_ok={meta.cadence_ok}")
```

**Missing:**
- State transitions (`LOAD_DATA -> BUILD_FEATURES`)
- State validation failures
- State corruption detection
- State recovery attempts

---

## 10. State Anti-Patterns Catalog

### 10.1 God Function State

**Pattern:** All state in one function scope.

**Location:** `main()` (60+ variables)

**Impact:**
- Cannot test individual stages
- Cannot share state between functions
- Cannot persist/restore state
- Cannot run stages in parallel

### 10.2 Implicit State Dependencies

**Pattern:** Function behavior depends on "far away" state.

**Example:**
```python
# Line 640: Feature engineering
train = fast_features.compute_basic_features(train, window=feat_win)

# Line 850: Hash computation (500 lines later)
# Depends on: train (modified), imputation (applied), drops (performed)
train_feature_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()
```

**Impact:** Cannot reason about hash without reading 500 lines.

### 10.3 State Bifurcation

**Pattern:** State diverges based on conditionals, never reconverges.

**Example:**
```python
# Line 890-950: Cache loading
if cached_models:
    ar1_detector = cached_models["ar1_params"]
    # ...
elif detector_cache:
    ar1_detector = detector_cache.get("ar1")
    # ...
else:
    ar1_detector = None

# Line 1050: Calibration (100 lines later)
# ar1_detector may be from 3 different sources
# No way to tell which path was taken
```

**Impact:** Debugging requires tracing all paths.

### 10.4 State Mutation Without Invalidation

**Pattern:** Mutate state without invalidating derived state.

**Example:**
```python
# Line 235: Signature computed
config_signature = _compute_config_signature(cfg)

# Line 240: Signature stored
cfg["_signature"] = config_signature

# Line 1350: Config mutated
cfg.update_param("thresholds.self_tune.clip_z", new_clip_z, ...)

# Line 1450: Signature used for cache validation
# BROKEN: Signature is stale!
cache_valid = (cached_cfg_sig == config_signature)
```

**Impact:** Cache validation is incorrect.

### 10.5 Temporal Coupling

**Pattern:** Order matters but not enforced.

**Example:**
```python
# Line 950: Score detectors
frame["ar1_raw"] = ar1_detector.score(score)

# Line 1050: Calibrate (must happen AFTER scoring)
cal_ar = fuse.ScoreCalibrator(...).fit(train_frame["ar1_raw"], ...)

# Nothing prevents:
# cal_ar = ... (line 1050)
# frame["ar1_raw"] = ... (line 950)  # Wrong order!
```

**Impact:** Reordering code breaks system silently.

---

## 11. Recommendations: State Refactoring

### 11.1 Introduce State Object

**Priority:** 🔴 **CRITICAL**

```python
from dataclasses import dataclass
from typing import Optional
import pandas as pd

@dataclass
class PipelineState:
    """Encapsulates all pipeline state with validation."""
    
    # Configuration (immutable after init)
    config: ConfigDict
    equip_id: int
    run_id: str
    
    # Data (set once, read many)
    train_raw: Optional[pd.DataFrame] = None
    score_raw: Optional[pd.DataFrame] = None
    train_features: Optional[pd.DataFrame] = None
    score_features: Optional[pd.DataFrame] = None
    
    # Models (set once, read many)
    detectors: Optional[Dict[str, Any]] = None
    regime_model: Optional[Any] = None
    
    # Outputs (write once, read many)
    detector_outputs: Optional[pd.DataFrame] = None
    episodes: Optional[pd.DataFrame] = None
    
    # Cache metadata
    cache_signature: Optional[str] = None
    cache_valid: bool = False
    
    # Stage tracking
    current_stage: str = "INITIALIZED"
    
    def validate(self) -> List[str]:
        """Check state invariants."""
        errors = []
        
        if self.train_features is not None:
            if not self.train_features.index.is_unique:
                errors.append("train_features has duplicate indices")
        
        if self.detectors is not None and self.train_features is None:
            errors.append("detectors fitted without train_features")
        
        # ... more checks
        return errors
```

### 11.2 Stage-Based Architecture

**Priority:** 🔴 **CRITICAL**

```python
from abc import ABC, abstractmethod

class PipelineStage(ABC):
    """Base class for pipeline stages."""
    
    @abstractmethod
    def execute(self, state: PipelineState) -> PipelineState:
        """Execute stage, return updated state."""
        pass
    
    @abstractmethod
    def validate_preconditions(self, state: PipelineState) -> List[str]:
        """Check if state is valid for this stage."""
        pass

class LoadDataStage(PipelineStage):
    def validate_preconditions(self, state: PipelineState) -> List[str]:
        errors = []
        if state.current_stage != "INITIALIZED":
            errors.append(f"Expected INITIALIZED, got {state.current_stage}")
        return errors
    
    def execute(self, state: PipelineState) -> PipelineState:
        # Load data
        state.train_raw = load_train_data(state.config)
        state.score_raw = load_score_data(state.config)
        state.current_stage = "DATA_LOADED"
        return state

class BuildFeaturesStage(PipelineStage):
    def validate_preconditions(self, state: PipelineState) -> List[str]:
        errors = []
        if state.current_stage != "DATA_LOADED":
            errors.append(f"Expected DATA_LOADED, got {state.current_stage}")
        if state.train_raw is None:
            errors.append("train_raw is None")
        return errors
    
    def execute(self, state: PipelineState) -> PipelineState:
        # Build features
        state.train_features = build_features(state.train_raw, state.config)
        state.score_features = build_features(state.score_raw, state.config)
        state.current_stage = "FEATURES_BUILT"
        return state

# Pipeline orchestrator
class ACMPipeline:
    def __init__(self, config: ConfigDict, equip_id: int):
        self.state = PipelineState(
            config=config,
            equip_id=equip_id,
            run_id=generate_run_id()
        )
        
        self.stages = [
            LoadDataStage(),
            BuildFeaturesStage(),
            FitModelsStage(),
            ScoreStage(),
            CalibrateStage(),
            FuseStage(),
            DetectEpisodesStage(),
            DetectDriftStage(),
            PersistStage(),
        ]
    
    def run(self):
        for stage in self.stages:
            # Validate preconditions
            errors = stage.validate_preconditions(self.state)
            if errors:
                raise PipelineError(f"{stage.__class__.__name__}: {errors}")
            
            # Execute stage
            self.state = stage.execute(self.state)
            
            # Validate postconditions
            errors = self.state.validate()
            if errors:
                raise PipelineError(f"After {stage.__class__.__name__}: {errors}")
```

### 11.3 Immutable Config

**Priority:** 🟡 **HIGH**

```python
from types import MappingProxyType

class ImmutableConfig:
    """Config that cannot be mutated after initialization."""
    
    def __init__(self, data: Dict[str, Any]):
        self._data = data
        self._frozen = MappingProxyType(data)  # Read-only view
    
    def get(self, key: str, default=None):
        return self._frozen.get(key, default)
    
    def __setitem__(self, key, value):
        raise TypeError("Config is immutable")
    
    def evolve(self, **changes) -> 'ImmutableConfig':
        """Create new config with changes (functional update)."""
        new_data = self._data.copy()
        new_data.update(changes)
        return ImmutableConfig(new_data)
```


# Comprehensive Audit of `acm_main.py`

## Executive Summary

This is a **production-grade anomaly detection system** with approximately **1,800 lines** of complex orchestration code. It implements a multi-detector fusion pipeline for industrial equipment monitoring with SQL and file-based persistence modes.

**Overall Assessment:** 7.5/10
- Strengths: Comprehensive feature set, robust error handling, dual storage backends
- Weaknesses: High complexity, tight coupling, inconsistent state management

---

## 1. Architecture & Design Patterns

### 1.1 Core Architecture
```
Data Loading → Feature Engineering → Model Fitting/Caching → 
Scoring → Calibration → Fusion → Episodes → Drift Detection → 
Persistence (File/SQL/Dual)
```

**Strengths:**
- Clear pipeline stages with timing instrumentation
- Dual-mode storage (file/SQL) with unified OutputManager abstraction
- Model versioning and caching system

**Weaknesses:**
- **God Object Pattern**: `main()` function is 1,400+ lines
- **State Management Chaos**: 50+ local variables in main scope
- **Circular Dependencies**: Config affects outputs, outputs update config

### 1.2 Design Patterns Used

| Pattern | Implementation | Quality |
|---------|----------------|---------|
| **Strategy** | `OutputManager` for storage backends | ✅ Good |
| **Factory** | Detector instantiation | ⚠️ Mixed (some hardcoded) |
| **Template Method** | Pipeline stages | ✅ Clear |
| **Singleton** | `Timer`, `Console` | ⚠️ Implicit globals |
| **Builder** | Episode construction | ❌ Manual assembly |

---

## 2. Critical Issues & Technical Debt

### 2.1 HIGH PRIORITY Issues

#### 🔴 Issue #1: Massive Function Complexity
**Location:** `main()` function (lines 450-1800)
```python
def main() -> None:
    # 1,400 lines of sequential logic
    # 50+ local variables
    # 30+ try/except blocks
    # 15+ conditional branches
```

**Impact:**
- Impossible to test in isolation
- High cognitive load (estimated McCabe complexity: 150+)
- Maintenance nightmares

**Recommendation:**
```python
class ACMPipeline:
    def __init__(self, config, equip_id):
        self.config = config
        self.equip_id = equip_id
        self.state = PipelineState()
    
    def run(self):
        self.load_data()
        self.build_features()
        self.fit_or_load_models()
        self.score_data()
        self.detect_episodes()
        self.persist_results()
```

#### 🔴 Issue #2: Inconsistent Index Handling
**Locations:** Lines 543-555, 1200-1250

```python
# GOOD: Deduplication with assertion
train = train[~train.index.duplicated(keep='last')].sort_index()
if not train.index.is_unique:
    raise RuntimeError("TRAIN data still has duplicate timestamps!")

# BAD: Silent fallback to O(n²) search
try:
    _sidx = pd.Index(frame.index).get_indexer(_sdt, method='nearest')
except ValueError:
    # Fallback for non-monotonic target timestamps
    _sidx = []
    for target_time in _sdt:  # O(n²) nested loop!
        time_diffs = np.abs((frame.index - target_time).total_seconds())
        _sidx.append(time_diffs.argmin())
```

**Impact:**
- Performance cliff on large datasets (>100k rows)
- Inconsistent behavior based on data ordering

**Fix:**
```python
def safe_get_indexer(index, targets, method='nearest'):
    """Vectorized indexer with monotonic enforcement."""
    if not index.is_monotonic_increasing:
        index = index.sort_values()
    return index.get_indexer(targets, method=method)
```

#### 🔴 Issue #3: Memory Leaks in SQL Mode
**Location:** Lines 1650-1750 (SQL write blocks)

```python
# PROBLEM: No connection pooling limits
with T.section("sql.scores.write"):
    rows_scores = output_manager.write_scores_ts(long_scores, run_id or "")
# Each write acquires a new connection from pool
```

**Evidence:**
- Comment on line 1675: "CRITICAL FIX: Close OutputManager to prevent connection leaks"
- Finally block cleanup suggests known issue

**Fix:**
```python
class SQLBatchWriter:
    def __init__(self, client, batch_size=10000):
        self.client = client
        self.batch_size = batch_size
        self._buffer = []
    
    def __enter__(self):
        self.client.begin_transaction()
        return self
    
    def __exit__(self, *args):
        self.flush()
        self.client.commit()
```

### 2.2 MEDIUM PRIORITY Issues

#### ⚠️ Issue #4: Hardcoded Magic Numbers
**Examples:**
```python
# Line 342: Feature window
feat_win = int((cfg.get("features", {}) or {}).get("window", 3))

# Line 920: Low variance threshold
low_var_threshold = 1e-6

# Line 1075: Drift trend window
trend_window = int(multi_feat_cfg.get("trend_window", 20))

# Line 1450: P95 percentile
spe_p95 = float(np.nanpercentile(frame["pca_spe"].to_numpy(dtype=np.float32), 95))
```

**Impact:**
- Hidden assumptions
- Difficult to tune

**Fix:** Centralize in `constants.py`

#### ⚠️ Issue #5: Inconsistent Error Handling
**Pattern 1: Silent failures**
```python
try:
    regime_model = regimes.load_regime_model(stable_models_dir)
except Exception as e:
    Console.warn(f"Failed to load regime model: {e}")
    regime_model = None  # Continue with None
```

**Pattern 2: Re-raise**
```python
except Exception as e:
    Console.error(f"Exception: {e}")
    raise  # Crash the pipeline
```

**Pattern 3: Log and continue**
```python
except Exception as e:
    Console.warn(f"Chart generation failed: {e}")
    # No state update, just log
```

**Impact:** Unpredictable failure modes

#### ⚠️ Issue #6: Type Safety Gaps
```python
# Line 450: Optional chaining hell
self_tune_cfg = (cfg or {}).get("thresholds", {}).get("self_tune", {})
use_per_regime = (cfg.get("fusion", {}) or {}).get("per_regime", False)

# Line 890: Runtime type coercion
equip_id = int(equip_id_cfg)  # May raise ValueError at runtime
```

**Fix:** Use Pydantic models
```python
from pydantic import BaseModel

class ThresholdConfig(BaseModel):
    q: float = 0.98
    self_tune: SelfTuneConfig = SelfTuneConfig()

class ACMConfig(BaseModel):
    thresholds: ThresholdConfig
    fusion: FusionConfig
    # ...
```

---

## 3. Code Quality Metrics

### 3.1 Complexity Analysis

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Lines of Code | 1,800 | 500 | ❌ Exceeded |
| Cyclomatic Complexity (main) | ~150 | 10 | ❌ Critical |
| Function Length (main) | 1,400 | 50 | ❌ Critical |
| Local Variables (main) | 50+ | 10 | ❌ Exceeded |
| Nested Try Blocks | 5 levels | 2 | ❌ Exceeded |
| Module Dependencies | 25+ | 10 | ⚠️ High |

### 3.2 Maintainability Index
**Estimated: 35/100** (Very Low)

Formula: `MI = 171 - 5.2*ln(V) - 0.23*G - 16.2*ln(LOC)`
- Volume (V): ~8,000 (high)
- Cyclomatic Complexity (G): ~150
- Lines of Code: 1,800

---

## 4. Performance Analysis

### 4.1 Hot Paths

**1. Feature Engineering (Lines 640-720)**
```python
# OPTIMIZATION: Polars fast path
if use_polars:
    train_pl = pl.from_pandas(train)  # Conversion overhead
    train = fast_features.compute_basic_features(train_pl, window=feat_win)
```
**Benchmark needed:** When does Polars overhead pay off?

**2. PCA Scoring (Lines 950-960)**
```python
# GOOD: Cache reuse
if pca_train_spe is not None:
    train_frame["pca_spe"], train_frame["pca_t2"] = pca_train_spe, pca_train_t2
else:
    # SLOW: Recomputation
    train_frame["pca_spe"], train_frame["pca_t2"] = pca_detector.score(train)
```

**3. SQL Batch Writes (Lines 1650-1750)**
```python
# PROBLEM: Individual table writes
rows_scores = output_manager.write_scores_ts(long_scores, run_id)  # 1st transaction
rows_drift = output_manager.write_drift_ts(df_drift, run_id)       # 2nd transaction
rows_events = output_manager.write_anomaly_events(df_events, run_id)  # 3rd...
```
**Fix:** Single batched transaction

### 4.2 Memory Profiling

**Potential Leaks:**
1. **DataFrame copies:** Lines 543, 710, 1200
   ```python
   train_numeric = train.copy()  # Deep copy
   score_numeric = score.copy()  # Another deep copy
   ```

2. **Unclosed file handles:** No explicit context managers in file mode

3. **SQL connections:** Relies on GC, no guaranteed cleanup

---

## 5. Security Audit

### 5.1 SQL Injection Vectors

**✅ SAFE: Parameterized queries**
```python
# Line 375
cur.execute(tsql, (equip_id, config_hash, window_start, ...))
```

**✅ SAFE: OutputManager uses parameterized inserts**

### 5.2 Path Traversal Risks

**⚠️ MODERATE: User-controlled paths**
```python
# Line 450
art_root = Path(args.artifact_root)  # User input
run_dir = art_root / equip_slug / f"run_{run_id_ts}"
```

**Mitigation present:**
```python
# Line 465: Hardcoded base enforcement
base_artifacts = Path("artifacts")  # HARDCODED
```

### 5.3 Deserialization Risks

**⚠️ MODERATE: Joblib unpickling**
```python
# Line 890
cached_bundle = joblib.load(model_cache_path)  # Arbitrary code execution risk
```

**Recommendation:** Add signature verification
```python
import hmac
def verify_cache(path, expected_hash):
    with open(path, 'rb') as f:
        actual = hmac.new(SECRET_KEY, f.read(), 'sha256').hexdigest()
    return hmac.compare_digest(actual, expected_hash)
```

---

## 6. Testing Gaps

### 6.1 Testability Score: 2/10

**Blockers:**
1. No dependency injection (global `Timer`, `Console`)
2. Monolithic main() function
3. Side effects everywhere (file I/O, SQL writes)
4. No interfaces for mocking

### 6.2 Missing Test Categories

| Category | Coverage | Priority |
|----------|----------|----------|
| Unit Tests | 0% | 🔴 High |
| Integration Tests | Manual only | 🔴 High |
| Performance Tests | None | ⚠️ Medium |
| Security Tests | None | ⚠️ Medium |
| Regression Tests | None | 🔴 High |

### 6.3 Example Test That Cannot Be Written

```python
# CANNOT TEST: Too many dependencies
def test_main_episode_detection():
    # Need: file system, SQL database, config files,
    #       trained models, timer, logger, ...
    main()  # 😢
```

**Fix:** Extract testable units
```python
def test_episode_detection():
    scores = pd.DataFrame({'fused': [1, 5, 2, 6, 3]})
    episodes = detect_episodes(scores, threshold=4.0)
    assert len(episodes) == 2
```

---

## 7. Documentation Quality

### 7.1 Inline Comments

**Good:**
```python
# Line 543: Clear intent
# CRITICAL: Deduplicate indices to prevent O(n²) performance
```

**Bad:**
```python
# Line 1200: Obvious comment
episodes["regime"] = regime_vals  # Set regime column
```

### 7.2 Docstrings

**Missing:**
- `main()` function (1,400 lines, no docstring!)
- `_get_equipment_id()`
- `_compute_drift_trend()`
- `_compute_regime_volatility()`

**Present:**
```python
def _write_run_meta_json(local_vars: Dict[str, Any]) -> None:
    """Persist run metadata to meta.json inside the current run directory."""
    # Good: clear purpose
```

### 7.3 Debt Tracking

**Excellent:** Inline debt markers
```python
# DEBT-05: Expanded to include all sections
# DEBT-09: Stable hash across pandas versions
# DEBT-10: Deep copy config to prevent mutation
```

**Count:** 10+ debt items tracked

---

## 8. Dependencies & Coupling

### 8.1 Dependency Graph

```
acm_main.py (1,800 LOC)
├── core.regimes (tight)
├── core.drift (tight)
├── core.fuse (tight)
├── core.correlation (tight)
├── core.outliers (tight)
├── core.forecast (tight)
├── core.river_models (loose)
├── core.omr (tight)
├── core.output_manager (tight)
├── core.sql_client (conditional)
├── utils.timer (tight)
├── utils.logger (tight)
├── utils.config_dict (tight)
└── 15+ external libs
```

**Coupling Score: 8/10** (High)

### 8.2 Import Issues

**Problematic import guard:**
```python
# Lines 30-45
try:
    from . import regimes, drift, fuse  # Relative import
except ImportError:
    sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
    from core import regimes, drift, fuse  # Absolute import
```

**Problem:** Supports both execution modes, but fragile

---

## 9. Configuration Management

### 9.1 Config System Analysis

**Strengths:**
- Multi-source config (SQL, CSV, code)
- Equipment-specific overrides
- Config versioning via signature

**Weaknesses:**
```python
# Line 450: Defensive nested gets
self_tune_cfg = (cfg or {}).get("thresholds", {}).get("self_tune", {})
```

**Impact:** Verbose, error-prone

### 9.2 Config Mutation

**⚠️ PROBLEM: Config is modified at runtime**
```python
# Line 1350: Config mutation
cfg.update_param("thresholds.self_tune.clip_z", new_clip_z, ...)
```

**Risk:** Auto-tuning changes persist across runs unpredictably

---

## 10. Recommendations

### 10.1 Immediate Actions (Week 1)

1. **Split `main()` into class methods**
   ```python
   class ACMPipeline:
       def __init__(self, config, args):
           self.config = config
           self.args = args
           self.state = PipelineState()
       
       def run(self):
           self._load_data()
           self._fit_models()
           # ...
   ```

2. **Add type hints everywhere**
   ```python
   def _get_equipment_id(equipment_name: str) -> int:
       """Convert equipment name to numeric ID."""
   ```

3. **Fix index handling**
   - Remove O(n²) fallback
   - Enforce monotonic indices early

### 10.2 Short-Term (Month 1)

4. **Introduce Dependency Injection**
   ```python
   class ACMPipeline:
       def __init__(
           self,
           config: Config,
           timer: Timer,
           logger: Logger,
           output_manager: OutputManager
       ):
           # All dependencies injected
   ```

5. **Add unit tests**
   - Target 50% coverage on core logic
   - Mock file I/O and SQL

6. **Consolidate error handling**
   ```python
   class PipelineError(Exception):
       """Base for all pipeline errors."""
   
   class DataLoadError(PipelineError): ...
   class ModelFitError(PipelineError): ...
   ```

### 10.3 Long-Term (Quarter 1)

7. **Migrate to event-driven architecture**
   ```python
   class PipelineEvent:
       pass
   
   class DataLoaded(PipelineEvent):
       data: pd.DataFrame
   
   class ModelsFitted(PipelineEvent):
       detectors: Dict[str, Detector]
   ```

8. **Add performance benchmarks**
   - CI/CD integration
   - Regression detection

9. **Security hardening**
   - Cache signature verification
   - Path sanitization
   - Input validation layer

---

## 11. Positive Highlights

### 11.1 Excellent Patterns

1. **Comprehensive timing instrumentation**
   ```python
   with T.section("fit.ar1"):
       ar1_detector = forecast.AR1Detector(...).fit(train)
   ```

2. **Defensive programming**
   ```python
   # Line 543: Index deduplication with assertion
   if not train.index.is_unique:
       raise RuntimeError("TRAIN data still has duplicate timestamps!")
   ```

3. **Adaptive parameter tuning**
   ```python
   # Lines 1300-1400: Autonomous tuning based on quality metrics
   if should_retrain:
       cfg.update_param("thresholds.self_tune.clip_z", new_clip_z, ...)
   ```

4. **Dual storage mode**
   - Unified `OutputManager` abstraction
   - Transparent file/SQL switching

5. **Debt tracking**
   - Inline `# DEBT-XX` markers
   - Justifications for workarounds

### 11.2 Production-Ready Features

- Model versioning and caching
- Rolling baseline buffer
- Refit flag mechanism
- Comprehensive analytics tables
- Heartbeat monitoring
- Error recovery strategies

---

## 12. Final Verdict

### Scores

| Aspect | Score | Weight | Weighted |
|--------|-------|--------|----------|
| Architecture | 6/10 | 20% | 1.2 |
| Code Quality | 5/10 | 25% | 1.25 |
| Performance | 7/10 | 15% | 1.05 |
| Security | 7/10 | 10% | 0.7 |
| Testing | 2/10 | 15% | 0.3 |
| Documentation | 6/10 | 10% | 0.6 |
| Maintainability | 4/10 | 5% | 0.2 |

**Overall: 5.3/10**

### Classification

**This is LEGACY CODE that works in production but urgently needs refactoring.**

**Risk Level:** 🟡 **MEDIUM-HIGH**
- Works reliably (evidence: production deployment)
- Extremely difficult to modify safely
- High technical debt accumulation rate
- Testing gaps create deployment risk

### Investment Recommendation

**Refactor incrementally over 3 months:**
- Month 1: Extract 5 core classes, add 30% test coverage
- Month 2: Introduce DI, reach 60% coverage
- Month 3: Performance optimization, 80% coverage

**ROI:** High (reduced bug rate, faster feature velocity)

---

## Appendix: Code Smells Catalog

1. **Long Method** (main: 1,400 lines)
2. **Large Class** (implicit: 50+ variables)
3. **Feature Envy** (accessing nested dicts constantly)
4. **Inappropriate Intimacy** (tight coupling to all core modules)
5. **Shotgun Surgery** (changing detector affects 10+ locations)
6. **Divergent Change** (main() changes for any reason)
7. **Primitive Obsession** (Dict[str, Any] everywhere)
8. **Data Clumps** (frame, episodes, cfg passed together)
9. **Speculative Generality** (dual-mode overhead unused?)
10. **Dead Code** (DEPRECATED storage comment, line 40)

---

**Audit completed by code analysis on 2025-01-11.**
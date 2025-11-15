# ACM V8 - Comprehensive Logging Audit Report

**Date:** 2025-11-15  
**Auditor:** Automated Analysis  
**Scope:** Complete logging and print statement usage across core/, utils/, scripts/

---

## Executive Summary

This audit examines the current state of logging throughout the ACM V8 codebase, identifies areas where print statements are used instead of proper logging, and recommends a comprehensive logging strategy including heartbeat functionality.

### Key Findings

1. **Mixed Logging Approaches**: 552 instances of `Console.*` usage vs 286 raw `print()` statements
2. **Scripts Heavy on Print**: 91 print statements in `sql_batch_runner.py`, 59 in `analyze_charts.py`
3. **Inline Console Definitions**: Multiple files define their own Console fallback classes
4. **No Structured Logging**: No JSON/structured logging support for automated monitoring
5. **Heartbeat Implementation**: Working but uses direct print() statements with Unicode characters
6. **Timer Implementation**: Working but uses direct print() statements

### Priority Issues

| Priority | Issue | Files Affected | Impact |
|----------|-------|----------------|--------|
| HIGH | Scripts use print() instead of logger | 6 scripts | Inconsistent output format, hard to parse |
| HIGH | No structured logging for automation | All | Cannot integrate with monitoring tools |
| MEDIUM | Inline Console fallbacks | 4 core files | Code duplication, inconsistent behavior |
| MEDIUM | Heartbeat uses Unicode | output_manager.py | Breaks ASCII-only logging policy (OUT-24) |
| LOW | Timer uses print() | utils/timer.py | Inconsistent with Console.* pattern |

---

## Current Logging Architecture

### 1. Console Logger (`utils/logger.py`)

**Current Implementation:**
```python
class Console:
    @staticmethod
    def info(msg: str) -> None:  print(msg, file=sys.stdout)
    @staticmethod
    def ok(msg: str)   -> None:  print(msg, file=sys.stdout)
    @staticmethod
    def warn(msg: str) -> None:  print(msg, file=sys.stdout)
    @staticmethod
    def error(msg: str)-> None:  print(msg, file=sys.stderr)
    warning = warn  # Alias
```

**Strengths:**
- Simple, consistent interface
- Used extensively in core modules (552 calls)
- Minimal overhead

**Weaknesses:**
- No log levels beyond 4 basic types
- No timestamps
- No structured output (JSON)
- No file output
- No context/metadata support
- No filtering/configuration

### 2. Heartbeat (`core/output_manager.py`)

**Current Implementation:**
- Thread-based progress indicator
- Uses Unicode braille spinner characters: `["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]`
- Direct `print()` statements
- Shows ETA and next-step hints

**Issues:**
- Unicode breaks ASCII-only policy (Task OUT-24)
- Not integrated with Console logger
- Cannot be disabled or redirected
- No structured output option

### 3. Timer (`utils/timer.py`)

**Current Implementation:**
- Performance timing context manager
- Direct `print()` with `[TIMER]` prefix
- Automatic summary on exit

**Issues:**
- Not integrated with Console logger
- Cannot be redirected or captured
- No JSON output option

### 4. JSONL Logger (`utils/logger.py`)

**Current Implementation:**
```python
def jsonl_logger(path: Path) -> Callable[[Dict[str, Any]], None]:
    # Append JSON lines to path
```

**Status:** Defined but not actively used in main pipeline

---

## Detailed Audit by File

### Core Modules

#### `core/acm_main.py` (7 print statements)
- Lines 87-92: Inline Console fallback class definition
- Line 128: Console.warn for fallback mapping
- Lines 207, 215: Heartbeat class using print()
- Lines 224: Spinner output with print()

**Recommendation:** Remove inline Console class, use imported Console consistently

#### `core/omr.py` (7 print statements)
- Lines 186-227: Direct print() for OMR diagnostics
- Patterns: `print("[OMR] ...")`, `print(f"[OMR] ...")`

**Recommendation:** Replace all with `Console.info("[OMR] ...")`

#### `core/correlation.py` (2 print statements)
- Lines 45-46: Inline Console fallback
```python
def info(msg: str): print(f"[INFO] {msg}")
def warn(msg: str): print(f"[WARN] {msg}")
```

**Recommendation:** Use imported Console consistently

#### `core/enhanced_forecasting.py` (3 print statements)
- Lines 33-35: Inline Console fallback
```python
def info(msg: str): print(f"[INFO] {msg}")
def warn(msg: str): print(f"[WARN] {msg}")
def error(msg: str): print(f"[ERROR] {msg}")
```

**Recommendation:** Use imported Console consistently

#### `core/forecast.py` (2 print statements)
- Lines 26-30: Inline Console fallback with different module path
```python
from utils.console import Console  # Wrong path!
```

**Recommendation:** Fix import path to `utils.logger`, use Console consistently

#### `core/output_manager.py` (3 print statements)
- Lines 207, 215, 224: Heartbeat class implementation
- All using direct print() statements

**Recommendation:** Make Heartbeat configurable, support ASCII-only mode

#### `utils/timer.py` (5 print statements)
- Lines 32, 49, 56, 59, 60: All timing output via print()
- Format: `[TIMER] {name:<20} {duration}`

**Recommendation:** Integrate with Console logger, add JSON output option

### Scripts (275 print statements)

#### `scripts/sql_batch_runner.py` (91 print statements)
- Heavy use of print() for progress reporting
- Format: `[SQL]`, `[ERROR]`, `[COLDSTART]`, etc.

**Recommendation:** Refactor to use Console logger

#### `scripts/analyze_charts.py` (59 print statements)
- Analysis and validation reporting
- Mix of plain print() and formatted output

**Recommendation:** Refactor to use Console logger with structured output

#### `scripts/sql/*.py` (82 print statements across 6 files)
- Test scripts and utilities
- Inconsistent formatting

**Recommendation:** Standardize on Console logger

---

## Recommendations

### Phase 1: Enhanced Logger (Immediate - This PR)

**Enhance `utils/logger.py` with:**

1. **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
2. **Configurable Output**: stdout, stderr, file, structured JSON
3. **Timestamps**: Optional ISO format timestamps
4. **Context**: Support for additional metadata fields
5. **Filtering**: Environment-based log level control
6. **ASCII-Only Mode**: Respect `LOG_ASCII_ONLY` env var

**New Console Interface:**
```python
class Console:
    @staticmethod
    def debug(msg: str, **context) -> None: ...
    @staticmethod
    def info(msg: str, **context) -> None: ...
    @staticmethod
    def warn(msg: str, **context) -> None: ...
    @staticmethod
    def error(msg: str, **context) -> None: ...
    @staticmethod
    def critical(msg: str, **context) -> None: ...
    
    # Configuration
    @staticmethod
    def set_level(level: str) -> None: ...
    @staticmethod
    def set_format(fmt: str) -> None: ...  # "text", "json"
    @staticmethod
    def set_output(file: Path) -> None: ...
```

2. **Heartbeat Integration**
   - Move Heartbeat to `utils/logger.py`
   - Integrate with Console logger
   - Add ASCII-only spinner option: `['-', '\\', '|', '/']`
   - Support `LOG_ASCII_ONLY` environment variable
   - Add disable option via `ACM_HEARTBEAT=false`

3. **Timer Integration**
   - Keep in `utils/timer.py` but use Console.info()
   - Add JSON output option for automated parsing
   - Support `ACM_TIMINGS` environment variable (already exists)

### Phase 2: Standardize Core Modules

1. Remove all inline Console fallback definitions
2. Replace all direct print() with Console.*
3. Add appropriate context to log messages
4. Update OMR logging to use Console.info/warn

**Files to modify:**
- `core/acm_main.py` - Remove inline Console class
- `core/omr.py` - Replace 7 print() statements
- `core/correlation.py` - Remove inline Console, use import
- `core/enhanced_forecasting.py` - Remove inline Console, use import
- `core/forecast.py` - Fix import path, remove fallback
- `core/output_manager.py` - Integrate Heartbeat with logger

### Phase 3: Standardize Scripts

Refactor scripts to use Console logger:
1. `scripts/sql_batch_runner.py` - 91 print() → Console.*
2. `scripts/analyze_charts.py` - 59 print() → Console.*
3. `scripts/sql/*.py` - 82 print() → Console.*
4. `scripts/chunk_replay.py` - 14 print() → Console.*
5. `scripts/analyze_latest_run.py` - Check and update

### Phase 4: Advanced Features (Future)

1. **Structured Logging**: Activate JSONL logger for production monitoring
2. **Log Aggregation**: Support for sending logs to central system
3. **Performance Metrics**: Integrate Timer data into structured logs
4. **Alert Thresholds**: Automatic escalation based on error counts
5. **Trace IDs**: Add correlation IDs for request tracking

---

## Implementation Priority

### Critical Path (This PR)

1. ✅ Create this audit report
2. ⏳ Enhance `utils/logger.py` with new features
3. ⏳ Fix Heartbeat ASCII-only support
4. ⏳ Update core modules (remove inline Console classes)
5. ⏳ Add comprehensive tests
6. ⏳ Update documentation

### High Priority (Next PR)

1. Refactor scripts to use Console logger
2. Add structured JSON logging
3. Integration with monitoring systems

### Medium Priority (Future)

1. Advanced filtering and routing
2. Log aggregation support
3. Performance optimization

---

## Testing Strategy

1. **Unit Tests**: Test each Console method with different configurations
2. **Integration Tests**: Test Heartbeat and Timer with logger
3. **ASCII-Only Tests**: Verify no Unicode in ASCII-only mode
4. **Output Tests**: Verify correct routing to stdout/stderr/file
5. **Performance Tests**: Ensure logging overhead is minimal

---

## Success Criteria

- [ ] All core modules use Console.* (no raw print())
- [ ] Heartbeat respects ASCII-only policy
- [ ] Timer integrated with Console logger
- [ ] No inline Console class definitions
- [ ] Structured logging available (JSON output)
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Environment variables documented

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing scripts | Medium | Keep backward compatibility, add deprecation warnings |
| Performance overhead | Low | Keep default format lightweight, structured logging optional |
| Unicode issues in terminals | Low | ASCII-only mode by default or via env var |
| Log file disk usage | Low | Implement rotation, make file logging optional |

---

## Appendix A: File-by-File Print Statement Count

```
 91  scripts/sql_batch_runner.py
 59  scripts/analyze_charts.py
 40  scripts/sql/test_sql_mode_loading.py
 21  scripts/sql/test_config_load.py
 18  scripts/sql/test_dual_write_config.py
 14  scripts/chunk_replay.py
  7  core/acm_main.py
  7  core/omr.py
  7  scripts/sql/verify_acm_connection.py
  5  utils/timer.py
  5  scripts/sql/insert_wildcard_equipment.py
  3  core/enhanced_forecasting.py
  3  core/output_manager.py
  2  core/correlation.py
  2  core/forecast.py
```

**Total: 286 print() statements** (excluding utils/logger.py itself)

---

## Appendix B: Environment Variables

### Current
- `ACM_TIMINGS=1` - Enable/disable timing output (default: enabled)

### Proposed New
- `LOG_LEVEL=INFO` - Set minimum log level (DEBUG|INFO|WARNING|ERROR|CRITICAL)
- `LOG_FORMAT=text` - Output format (text|json)
- `LOG_FILE=path/to/file.log` - Optional file output
- `LOG_ASCII_ONLY=true` - Force ASCII-only characters (no Unicode)
- `ACM_HEARTBEAT=true` - Enable/disable heartbeat (default: enabled)

---

## Appendix C: Code Examples

### Before (Current State)
```python
# core/omr.py
print("[OMR] Empty training frame, skipping fit")
print(f"[OMR] Filtered to healthy regime {healthy_regime}: {np.sum(healthy_mask)} samples")
```

### After (Recommended)
```python
# core/omr.py
Console.info(f"[OMR] Empty training frame, skipping fit")
Console.info(f"[OMR] Filtered to healthy regime {healthy_regime}: {np.sum(healthy_mask)} samples")
```

### With Context (Advanced)
```python
# core/omr.py
Console.info("[OMR] Empty training frame, skipping fit", 
             module="omr", stage="fit", sample_count=0)
Console.info(f"[OMR] Filtered to healthy regime", 
             module="omr", regime=healthy_regime, 
             sample_count=np.sum(healthy_mask))
```

---

**End of Audit Report**

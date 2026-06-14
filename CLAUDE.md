# ACM — Codebase Knowledge Base

> Maintained for future agents. Update this file whenever you learn something new about the codebase.
> Last updated: session 868c2988 (2026-06-14)

---

## Architecture Overview

ACM is a stateless, self-tuning anomaly scoring service for industrial assets. Three layers:

```
Data sources  →  SQLite buffer / parquet cache  →  Pipeline workers  →  SQL store  →  FastAPI UI
```

- **Source layer** (`scripts/acm_feed.py`): per-asset `source_kind` dispatch (csv / table / query / opcua / mqtt)
- **Cache layer**: one parquet file per asset, trailing window (default 180 days), atomic write (`os.replace`)
- **Pipeline** (`core/pipeline.py`): stateless re-fit on every tick — AR1, PCA-SPE, PCA-T2, IForest, GMM, OMR → correlation-discounted fusion → self-tuned alarm rules
- **Store** (`scripts/acm_store.py`): SQLite (default) or SQL Server, same schema, qmark params on both
- **Service** (`scripts/acm_service.py`): FastAPI + asyncio scheduler, ProcessPoolExecutor for scoring workers

---

## Key Files

| File | Role |
|---|---|
| `core/pipeline.py` | `score_asset()` — entire ML pipeline, stateless, DataFrames in → scored result out |
| `core/alarm_rules.py` | R1 sustained / R2 24h rate / R3 per-head 7d / R4 availability / self-distrust gate |
| `core/fast_features.py` | Rolling features via Polars (float32) |
| `core/fuse.py` | Correlation-discounted Z-score fusion |
| `core/ml_defaults.py` | All ML hyper-parameters — edit here, NEVER in config_table.csv |
| `scripts/acm_service.py` | FastAPI service + async tick scheduler; starts OPC UA / MQTT bridges on-demand |
| `scripts/acm_feed.py` | `load_increment()`, `update_cache()`, `readiness()`, `frame_sensors()` |
| `scripts/acm_store.py` | `Store` class (sqlite/mssql), DDL, `ingest_result()`, `sync_config()` |
| `scripts/acm_opcua_bridge.py` | Asyncio singleton polling OPC UA → `data_cache/opcua_buffer.db` |
| `scripts/acm_mqtt_bridge.py` | Thread singleton subscribing MQTT → `data_cache/mqtt_buffer.db` |
| `scripts/acm_seed_demo.py` | Idempotent seeder — INSERT OR IGNORE CARE CSVs + OPC UA endpoint into monitored_assets |
| `scripts/acm_run.py` | Batch CLI scorer — CSV/SQL → parquet cache → score → store |
| `scripts/download_care_dataset.py` | Partial Zenodo zip download via `remotezip`; `--count N` limits events per farm |
| `scripts/care_benchmark.py` | CARE wind-farm benchmark against ground-truth labels |
| `configs/config_table.csv` | Human-editable runtime config (151 rows, equipment IDs: 0/global, 1, 2621, 5000-5092, 8634). Categories: data, sql, runtime ONLY. |
| `setup_acm.ps1` | One-command Windows installer + updater |
| `static/index.html` | Single-page UI entry point (Operator / Engineer / Admin panels) |
| `static/app.js` | Client-side polling, chart rendering, API commands |
| `static/style.css` | 14 themes (5 dark, 9 light) |

---

## Data Source Kinds (`source_kind` per asset)

Each row in `monitored_assets` has its own `source_kind`. `acm_feed.load_increment()` dispatches:

| source_kind | source_ref | conn_ref | timestamp_col default |
|---|---|---|---|
| `csv` | file path | — | `time_stamp` |
| `table` | table name | pyodbc conn string | `time_stamp` |
| `query` | SQL SELECT | pyodbc conn string | `time_stamp` |
| `opcua` | OPC UA endpoint URL | path to `opcua_buffer.db` (optional) | `published_at` |
| `mqtt` | (unused — bridge is singleton) | path to `mqtt_buffer.db` (optional) | `published_at` |

**Critical:** ACM must support all source kinds with per-asset flexibility. OPC UA is NOT a preferred source — it is specifically the integration mechanism for the Simulator. Never characterize OPC UA as "ACM's preferred historian" or special-case it in UI/docs.

---

## Simulator ↔ ACM Integration

**Hard constraint: Simulator has ZERO knowledge of ACM.** All integration code lives in ACM only. This was an early mistake (MQTT-first integration added ACM references to Simulator) that was fully reverted. Never repeat it.

**How it works:**
1. Simulator publishes OPC UA at `opc.tcp://localhost:4840/simulator`, namespace `http://local/industrial-tag-simulator`, root folder `TagSimulator` under Objects
2. `acm_opcua_bridge.py` polls every 1 s, writes `{published_at, tag1: v1, ...}` rows to `data_cache/opcua_buffer.db`
3. The bridge runs as `asyncio.create_task` inside the service event loop — never in worker processes
4. `acm_feed._load_opcua_increment()` reads from that SQLite file (same pattern as CSV)
5. Worker processes (ProcessPoolExecutor) only read SQLite, never touch the OPC UA connection — this is the decoupling mechanism

**Seed the asset once (idempotent):**
```bash
python scripts/acm_seed_demo.py --opcua opc.tcp://localhost:4840/simulator --db acm_results.db
```

**MQTT is secondary:** same SQLite buffer pattern, `data_cache/mqtt_buffer.db`, topic `industrial-tag-simulator/flat`, payload `{published_at, tag1: 1.23, ...}`.

---

## SQLite Buffer Pattern (core decoupling mechanism)

Used by both OPC UA and MQTT bridges to decouple async/threaded network I/O from ProcessPoolExecutor workers:

```
Bridge (asyncio task OR daemon thread — parent process only)
    ↓  writes rows
data_cache/opcua_buffer.db  OR  data_cache/mqtt_buffer.db
    ↑  reads via _load_opcua_increment() / _load_mqtt_increment()
Scoring worker (ProcessPoolExecutor subprocess)
```

Schema: `(ts TEXT NOT NULL, payload_json TEXT NOT NULL)` + index on `ts`.
Bridges have a `prune(keep_hours=200)` method to bound file size.

---

## OPC UA Bridge Details (`scripts/acm_opcua_bridge.py`)

```python
async def get_or_start(
    endpoint: str = "opc.tcp://localhost:4840/simulator",
    ns_uri: str = "http://local/industrial-tag-simulator",
    root_folder: str = "TagSimulator",
    db_path: Optional[Path] = None,       # defaults to data_cache/opcua_buffer.db
    poll_seconds: float = 1.0,
) -> OpcUaBridge:
```

- Process-singleton via `asyncio.Lock` — one bridge per service process
- On connection: discovers all children of `Objects/TagSimulator`, builds browse-name map
- Poll loop: `asyncio.gather(*[c.read_value() for c in children])` → writes JSON row to SQLite
- Reconnects with 5s backoff; uses `asyncio.wait_for(asyncio.shield(self._stop.wait()), timeout=poll_seconds)` for the poll interval

**Started in `acm_service._tick_body()` — lazy, only when an `opcua` asset is registered:**
```python
opcua_specs = [s for s in specs.values() if s.source_kind == "opcua"]
if opcua_specs:
    await _opcua_start(endpoint=..., db_path=...)
```

---

## Store: `scripts/acm_store.py`

```python
store = Store("sqlite", db="acm_results.db")   # or Store("mssql", conn_str="...")
store.execute(sql, params)   # qmark params, works on both backends
store.fetch(sql, params)     # returns list[dict]
store.executemany(sql, rows)
store.commit()
store.t("tablename")         # adds "dbo.acm_" prefix for mssql, identity for sqlite
```

**`monitored_assets` table schema:**
```sql
asset_key TEXT PRIMARY KEY, grp TEXT DEFAULT 'fleet', enabled INTEGER DEFAULT 1,
source_kind TEXT, source_ref TEXT, conn_ref TEXT,
timestamp_col TEXT, status_col TEXT, added_at TEXT, retired_at TEXT,
state TEXT DEFAULT 'NEW', state_detail TEXT,
last_run_at TEXT, last_score_ts TEXT, last_runtime_s REAL
```

**INSERT pattern (used in `acm_service.py` onboard handler and `acm_seed_demo.py`):**
```python
"INSERT OR IGNORE INTO monitored_assets "
"(asset_key, grp, enabled, source_kind, source_ref, conn_ref, "
"timestamp_col, status_col, added_at, state) "
"VALUES (?,?,?,?,?,?,?,?,?,?)"
```

**`acm_seed_demo.py` asset keys:**
- CARE CSVs: `care/{farm_letter}/{csv_stem}` (e.g. `care/A/40`), group `care_demo`
- OPC UA: `simulator/opc_ua`, group `simulator`

---

## Test Suite

68 tests across 4 files. Run with `python -m pytest tests/`.

| File | Count | What it tests |
|---|---|---|
| `test_ml.py` | 16 | ML correctness, detector sensitivity, alarm rules — all in-memory synthetic data |
| `test_service.py` | 10 | Feed/cache behavior, readiness gate, scheduler ticks, API lifecycle |
| `test_store.py` | 6 | SQL round-trips, views, config sync, end-to-end runner (1 marked slow) |
| `test_performance.py` | 36 | SQL view correctness, cache fast-path, TTLCache semantics (3 marked slow) |

**`@pytest.mark.slow` on 4 tests** (excluded from setup self-test via `-m "not slow"`):
- `test_store.py::TestRunnerCSV::test_acm_run_csv_end_to_end` — full subprocess ML run, 600s timeout, ~5,000 rows
- `test_performance.py::TestTTLCache::test_miss_after_ttl_expires` — `time.sleep(0.06)`
- `test_performance.py::TestTTLCache::test_overwrite_resets_ttl` — `time.sleep(0.07)` × 2
- `test_performance.py::TestFleetCacheIntegration::test_fleet_cache_expires` — `time.sleep(1.1)`

**Self-test in setup_acm.ps1 is non-fatal.** Test failures print a yellow `!` warning with the pytest summary line and log path, then continue — a failing test does not undo a working install.

---

## Setup Script (`setup_acm.ps1`)

Single command: `irm https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup_acm.ps1 | iex`

Flow:
1. Prerequisites: Git, Python 3.11+ (auto-installs via winget or direct installer)
2. Install: clone/update ACM, pip packages (includes `asyncua`, `paho-mqtt` — see constraint below), verify imports, self-test (non-fatal)
3. Backend detection: tries SQL Server via pyodbc, falls back to SQLite
4. **[1/2] Optional: Simulator** — clone to `$HOME\Simulator`, validate bundled runtime at `runtime\python\python.exe`, run `ensure-env`, seed `simulator/opc_ua` asset
5. **[2/2] Optional: CARE demo** — download 3 events (~30 MB Farm A), seed as `care_demo` assets
6. Summary + context-aware next steps (adapts text based on what was seeded)

**Critical constraint: `asyncua` and `paho-mqtt` MUST stay in the pip install step.** The bridges catch `ImportError` silently, so if these packages are removed the bridges will fail at runtime with no visible error. Discovered when OPC UA seeding worked but the bridge never actually connected.

**PowerShell pattern used:** `Step "name" { scriptblock }` — throws on non-zero exit. For non-fatal steps, use a custom block that captures exit code and outputs warning instead.

---

## CARE-to-Compare Dataset

- Zenodo URL: `https://zenodo.org/records/15846963/files/CARE_To_Compare.zip?download=1`
- Farm A: 22 events × ~36 MB (~800 MB total), 86 sensor features per event, CSV per event
- Farm B: 37 events, 257 features; Farm C: 36 events, 957 features
- CSV columns: `time_stamp`, `status_type_id`, sensor columns, `train_test`
- Download: `python scripts/download_care_dataset.py --dest care_data --farms A --count 3`
  - `--count N` applies to CSV files only (keeps README); N=3 ≈ 30 MB
- Seed: `python scripts/acm_seed_demo.py --care-dir care_data --db acm_results.db`
- Asset key pattern: `care/{farm_letter}/{csv_stem}` e.g. `care/A/40`
- Group: `care_demo`

---

## Config Split (enforced by test)

- **Human config** (`configs/config_table.csv`, synced to `config` table): categories `data`, `sql`, `runtime` only
- **ML params** (`core/ml_defaults.py`): categories `models`, `thresholds`, `fusion`, `regimes` — NEVER in config_table.csv
- `test_store.py::TestConfigSync::test_acm_run_csv_end_to_end` enforces this: if ML categories appear in config_table.csv the test fails

---

## Windows Compatibility

- **Asyncio in tests:** Always `asyncio.run(coro)` — NEVER `asyncio.get_event_loop().run_until_complete(coro)`. On Windows Python 3.8+, `ProactorEventLoop` is stricter; `get_event_loop()` can return a closed loop after `TestClient` consumes it. This caused the one test failure on a fresh Windows install (`test_tick_clears_all_caches` in `test_performance.py`). Fixed by replacing with `asyncio.run()`.
- **Paths:** Always `pathlib.Path` or `os.path.join` — never hardcode `/`.
- **Subprocess:** Pass args as list with `sys.executable` first — never rely on `.py` being directly executable.

---

## Key Implementation Patterns

- **Atomic parquet write:** `df.to_parquet(tmp)` then `os.replace(tmp, path)` — crash-safe, file is never half-written
- **Column-pruning for `since`:** `_read_ts_column()` reads only the timestamp column via PyArrow — avoids loading all 600+ sensor columns just to find the max timestamp
- **Adaptive score window:** `score_eff = min(score_days, max(1.0, span_days / 3.0))` — prevents young assets from starving the train side of the split
- **ProcessPool pickling:** `score_cached()` takes plain strings/dicts, returns plain dicts — nothing unpicklable crosses process boundaries
- **Bridges in parent process only:** OPC UA and MQTT bridges live in the service process (asyncio task / daemon thread). Workers only read SQLite. Never start a bridge in a worker.
- **Timezone consistency:** OPC UA/MQTT bridges write UTC-aware timestamps (`datetime.now(timezone.utc).isoformat()`). CSV files may have naive local timestamps. Mixing sources for a single asset requires consistent UTC-aware timestamp columns.

---

## Mistakes Made in Earlier Sessions (Never Repeat)

1. **Added ACM references to Simulator** — `ACM_DIR` variable in `suite_runtime.py`, ACM chip in portal HTML, ACM port in launchPorts. All reverted. The constraint is absolute: zero ACM knowledge in Simulator.
2. **Built MQTT-first integration** — wrong priority order. OPC UA is priority 1 because it's already implemented in the Simulator. MQTT is secondary.
3. **Called OPC UA "ACM's preferred source"** — wrong framing. OPC UA is just the wire between Simulator and ACM. ACM has equal support for all source kinds.
4. **Self-test aborting the install** — a test failure ≠ broken install. Packages installed + imports verified = working install. Self-test must be non-fatal.
5. **`asyncio.get_event_loop().run_until_complete()` in tests** — fails on Windows. Always `asyncio.run()`.
6. **Omitting `asyncua`/`paho-mqtt` from pip install** — bridges silently fail with ImportError. Always include them.
7. **`Select-Object -Last 1` inside a scriptblock already redirected to log** — redundant, and the pipe can confuse PowerShell's `$LASTEXITCODE` tracking.

---

## Detailed Data Flow (per source kind)

### CSV
```
CSV File → load_increment(source_kind="csv")
  → pd.read_csv(), filter rows > since
  → return DataFrame with timestamp_col parsed as datetime
```

### OPC UA
```
Simulator OPC UA (Objects/TagSimulator)
  ↓ asyncua poll every 1s (acm_opcua_bridge)
  ↓ INSERT {published_at, tag1, tag2,...} → opcua_buffer.db
  ↓ load_increment(source_kind="opcua")
  → SELECT payload_json FROM opcua_buffer WHERE ts > since
  → json.loads each row → DataFrame
  → rename published_at to spec.timestamp_col
```

### MQTT
```
Simulator MQTT (industrial-tag-simulator/flat)
  ↓ paho on_message callback (acm_mqtt_bridge daemon thread)
  ↓ INSERT {ts, payload_json} → mqtt_buffer.db
  ↓ load_increment(source_kind="mqtt")
  → SELECT payload_json FROM mqtt_buffer WHERE ts > since
  → json.loads → DataFrame
```

### Scoring pipeline (all sources)
```
load_increment → update_cache (concat + trim to 180d, atomic parquet write)
  → readiness() → MATURING / STALE / READY
  → (if READY) score_cached() in ProcessPoolExecutor worker
    → read parquet → adaptive train/score split
    → frame_sensors() → score_asset() → 6 detector Z-scores + fused
  → ingest_result() → INSERT INTO scores, alarms
  → UI polls /api/fleet and /api/asset/{key}
```

---

## Debugging Asset Scoring Issues

- **No score being produced:** check `readiness()` — likely MATURING (< 14 days) or STALE (> 24h gap)
- **OPC UA data not arriving:** check `data_cache/opcua_buffer.db` for recent rows; if empty the bridge disconnected — check `acm_service` logs for `last_error`
- **MQTT data not arriving:** check `data_cache/mqtt_buffer.db`; verify broker is up and topic matches `industrial-tag-simulator/flat`
- **Wrong asset columns:** query `monitored_assets` — verify `timestamp_col`, `status_col`, `source_kind` are correct for the asset
- **Degenerate split error:** span too short for the adaptive window — wait for more data to accumulate (MATURING gate should catch this)
- **Inspect raw cache:** `pd.read_parquet("data_cache/{asset_key}.parquet")` — check columns, timestamps, NaN density

---

## Future-Agent Guidance

### If modifying Simulator:
- Keep ALL code ACM-agnostic — no ACM imports, no references to ACM directories or ports
- OPC UA server must stay at `opc.tcp://localhost:4840/simulator`, namespace `http://local/industrial-tag-simulator`
- MQTT must stay on topic `industrial-tag-simulator/flat` with `{published_at, tag_name: value}` payload shape
- Do NOT add ACM-aware callbacks, startup dependencies, or configuration

### If adding a new ACM source kind:
1. Add `_load_XXXX_increment(spec, since) → pd.DataFrame` to `acm_feed.py`
2. Add the name to `SOURCE_KINDS` tuple
3. Add dispatch in `load_increment()`
4. If it needs a bridge, follow the OPC UA (asyncio) or MQTT (daemon thread) pattern
5. Return empty DataFrame on missing data — never raise

### If modifying the setup script:
- Use `Step "Name" { scriptblock }` for fatal steps; use a custom warn block for non-fatal steps
- Log all output to `$Log` via `*>> $Log`; never pipe to `Select-Object` inside a scriptblock that is already redirected
- Two-stage prerequisite fallback: winget first, direct .exe download second; always call `Refresh-Path` after install
- `asyncua` and `paho-mqtt` must stay in the pip install step — do not make them conditional

### If adding a new PowerShell Step:
```powershell
# Fatal (aborts install on failure):
Step "Step name" { command-that-must-succeed }

# Non-fatal (warn and continue):
Write-Host "    $([char]0x00B7)  Step name" -NoNewline
$out = command 2>&1; $code = $LASTEXITCODE
$out | Out-File $Log -Append
if ($code -eq 0) {
    Write-Host "`r    $([char]0x2713)  Step name"
} else {
    Write-Host "`r    !  Step name (non-fatal)" -ForegroundColor Yellow
    Write-Host "       Run ... to investigate" -ForegroundColor DarkGray
}
```

---

## Git Workflow

- Development branch: `claude/upbeat-hopper-m39epw` (both repos)
- Pattern: commit to dev branch → push dev → `git checkout main` → `git merge dev --no-edit` → `git push origin main`
- If push fails due to diverged remote: `git pull origin main --no-rebase --no-edit` then push again
- Never force-push, never `--no-verify`

---

## User Working Style

- Expects things to work end-to-end after one command — not "technically correct but incomplete"
- Direct and blunt when something is wrong — correct course immediately, don't justify
- Wants resilient installers: warn on non-critical failures, never abort
- Expects knowledge base to be maintained proactively after every agent report
- "Single UI" is a stated long-term goal for both tools

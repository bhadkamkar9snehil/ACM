# ACM — Codebase Knowledge Base

> Maintained for future agents. Update this file whenever you learn something new about the codebase.
> Last updated: session 01UuCboiW9MAKb9AKYYoVt1J (2026-06-16)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Key Files](#key-files-table)
3. [Data Source Kinds](#data-source-kinds)
4. [Simulator ↔ ACM Integration](#simulator--acm-integration)
5. [SQLite Buffer Pattern](#sqlite-buffer-pattern-core-decoupling-mechanism)
6. [OPC UA Bridge Details](#opc-ua-bridge-details)
7. [Store: acm_store.py](#store-scriptsacm_storepy)
8. [Test Suite](#test-suite)
9. [Setup Scripts](#setup-scripts)
10. [CARE Dataset](#care-to-compare-dataset)
11. [Simulator Integration — sim/ Package](#simulator-integration--sim-package)
12. [Config Split](#config-split-enforced-by-test)
13. [Windows Compatibility](#windows-compatibility)
14. [Key Implementation Patterns](#key-implementation-patterns)
15. [UI Codebase Map](#ui-codebase-map--static-appjs--indexhtml--stylecss) ← **Start here for any UI work**
16. [API Endpoints](#api-endpoints--key-responses)
17. [Mistakes Made in Earlier Sessions](#mistakes-made-in-earlier-sessions-never-repeat) ← **Read before starting any task**
18. [Detailed Data Flow](#detailed-data-flow-per-source-kind)
19. [Debugging Asset Scoring Issues](#debugging-asset-scoring-issues)
20. [Future-Agent Guidance](#future-agent-guidance)
21. [Service Start Command](#service-start-command)
22. [UI Testing](#ui-testing)
23. [Fault Datasets](#fault-datasets-sim_datasample)
24. [Git Workflow](#git-workflow)
25. [UI Font Sizes](#ui-font-sizes-canonical-after-2026-06-15-upsize)
26. [Fleet Operations Matrix Performance Optimization](#fleet-operations-matrix-performance-optimization-2026-06-16)
27. [Per-Asset Scoring & SIM→ACM Flow (2026-06-16)](#per-asset-scoring--simacm-flow-2026-06-16) ← **Latest work session**
28. [User Working Style](#user-working-style)

---

## Architecture Overview
> *Added: 2026-06-14*

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
> *Added: 2026-06-14 · Last updated: 2026-06-16*

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
| `setup.sh` | One-command Linux/macOS installer (mirrors setup_acm.ps1) |
| `docs/ml-book.html` | Self-contained interactive ML reference book — 8 chapters, Chart.js demos, Forge Dark theme, print-optimised |
| `static/index.html` | Single-page UI entry point (Operator / Engineer / Admin / Simulate tabs) |
| `static/app.js` | Client-side polling, chart rendering, API commands; SIM IIFE module appended |
| `static/style.css` | 14 themes (5 dark, 9 light); sim/output panel rules appended |
| `sim/` | Vendored simulator package — generators, replay engine, BufferPublisher, SimAdapter |
| `scripts/acm_sim_routes.py` | FastAPI router `prefix="/api/sim"` — **15 routes** for generators, files, replay, onboard, register |

---

## Data Source Kinds (`source_kind` per asset)
> *Added: 2026-06-14*

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
> *Added: 2026-06-14*

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
> *Added: 2026-06-14*

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
> *Added: 2026-06-14*

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
> *Added: 2026-06-14*

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
last_run_at TEXT, last_score_ts TEXT, last_runtime_s REAL,
fast_track INTEGER DEFAULT 0
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
> *Added: 2026-06-14*

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

## Setup Scripts
> *Added: 2026-06-14 · Last updated: 2026-06-15*

### `setup_acm.ps1` (Windows)
Single command: `irm https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup_acm.ps1 | iex`

Flow:
1. Prerequisites: Git, Python 3.11+ (auto-installs via winget or direct installer)
2. Install: clone/update ACM, create directories, pip packages (full list below), detect SQL Server via pyodbc (pyodbc silent if no ODBC headers), verify imports (both core + sim), self-test (non-fatal), fault datasets (non-fatal)
3. **[1/2] Optional: Simulator** — clone to `$HOME\Simulator`, validate bundled runtime at `runtime\python\python.exe`, run `ensure-env`, seed `simulator/opc_ua` asset
4. **[2/2] Optional: CARE demo** — download 10 Farm A events (~360 MB) to `sim_data\sample\`, seed as `care_demo` assets
5. Summary + context-aware next steps (adapts text based on what was seeded)

**Full pip install list (both scripts):** `pandas numpy polars pyarrow scikit-learn scipy structlog matplotlib remotezip pytest httpx fastapi uvicorn python-multipart pydantic asyncua paho-mqtt openpyxl` + `pyodbc` (optional, silent on failure)

**Critical constraint: `asyncua` and `paho-mqtt` MUST stay in the pip install step.** The bridges catch `ImportError` silently, so if these packages are removed the bridges will fail at runtime with no visible error. Discovered when OPC UA seeding worked but the bridge never actually connected.

**PowerShell pattern used:** `Step "name" { scriptblock }` — throws on non-zero exit. For non-fatal steps, use a custom block that captures exit code and outputs warning instead.

### `setup.sh` (Linux / macOS)
Single command: `bash <(curl -fsSL https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup.sh)`

Mirror of the PowerShell script for Linux/macOS:
1. Python 3.11+ check (exits if not found — does not auto-install)
2. Clone / `git pull --ff-only` ACM
3. pip install (same list as PS1): all packages + pyodbc silent-optional
4. Create directories: `sim_data/sample`, `sim_data/generated`, `sim_data/uploads`, `data_cache`, `configs`
5. Verify imports: core.pipeline, acm_store, acm_service, list_generators(), BufferPublisher, SimAdapter, acm_sim_routes.router
6. Self-test (non-fatal): `pytest tests/ -m "not slow" -q --tb=no -p no:warnings`
7. Fault datasets (non-fatal): `python scripts/generate_fault_dataset.py`
8. **[1/2] Optional: Simulator** — if `~/Simulator` exists, offer to seed OPC UA asset
9. **[2/2] Optional: CARE demo** — download 10 Farm A events (`--farms A --count 10`, defaults dest to `sim_data/sample`), seed as `care_demo` assets
10. Summary: start command + URLs

**download_care_dataset.py**: `--dest` optional (defaults to `sim_data/sample`); `--farms A --count 10` is all you need. There is **no** `--sim-dir` flag — the `--dest` flag is the only path argument.

**`step` helper** — prints `·  name`, runs command, overwrites with `✓` (green) or `✗` (red) + exits.
**`warn_step` helper** — same but prints `!` (yellow) + continues on failure.

---

## CARE-to-Compare Dataset
> *Added: 2026-06-14 · Last updated: 2026-06-15*

- Zenodo URL: `https://zenodo.org/records/15846963/files/CARE_To_Compare.zip?download=1`
- Farm A: 22 events × ~36 MB (~800 MB total), 86 sensor features per event, CSV per event
- Farm B: 37 events, 257 features; Farm C: 36 events, 957 features
- CSV columns: `time_stamp`, `status_type_id`, sensor columns, `train_test`
- Download: `python scripts/download_care_dataset.py --dest sim_data/sample --farms A --count 10`
  - `--count N` applies to CSV files only (keeps README); N=10 ≈ 360 MB
  - `--dest sim_data/sample` puts files directly in the SIM sample dir (default; omit flag to use it)
  - **There is NO `--sim-dir` flag** — `--dest` is the only path argument
- Seed: `python scripts/acm_seed_demo.py --care-dir care_data --db acm_results.db`
- Asset key pattern: `care/{farm_letter}/{csv_stem}` e.g. `care/A/40`
- Group: `care_demo`
- CARE CSVs in `sim_data/sample/` appear in ACM's Simulate → Files tab for replay
- **CARE is not a separate flow** — it uses the same SIM Files tab as any other sample CSV

---

## Simulator Integration — `sim/` Package
> *Added: 2026-06-14 · Last updated: 2026-06-16*

The `sim/` package is a vendored copy of the Simulator's generator + replay engine, adapted to live inside ACM. It enables in-process CSV generation and data replay without any external services.

### Package layout
```
sim/
├── __init__.py
├── models.py             — GenerateRequest, GenerateResponse, ReplayConfig, ReplayStatus, CurrentValue, etc.
├── type_inference.py     — infer data types from CSV columns
├── csv_manager.py        — file I/O for sim_data/ dirs (generated/, sample/, uploads/)
├── generator_registry.py — registry of all 11 domain generators
├── generator_engine.py   — generate_csv(domain_id, request) → GenerateResponse
├── generators/           — 11 domain generators + base.py
│   └── (eaf_melting, gas_pipeline, petroleum_pipeline, power_plant, rotary_equipment,
│       steel_blast_furnace, steel_ccm, steel_coke_oven, steel_dri_plant, steel_lrf, steel_rolling_mill)
├── simulator.py          — SimulatorEngine (configure/start/stop/restart/get_status/get_current_values)
├── multi_simulator.py    — MultiSimulatorEngine (multi-file replay)
├── opcua_server.py       — OpcUaTagServer (external OPC UA publish for sim data)
├── mqtt_publisher.py     — MqttTagPublisher (external MQTT publish)
├── protocol_adapter.py   — DualProtocolAdapter / ProtocolChannelAdapter
├── config_store.py       — persistent replay config
├── buffer_publisher.py   — BufferPublisher: in-process bridge → mqtt_buffer.db
└── sim_adapter.py        — SimAdapter: facade holding engine + publisher, used by API routes
```

### Adaptation from Simulator source
All files copied from `Simulator/industrial_simulator/app/` with:
- All `from app.*` → `from sim.*` import rewrites
- `csv_manager.py`: `ROOT = Path(__file__).resolve().parents[1]` so `sim_data/` resolves inside ACM root

### BufferPublisher (key integration bridge)
Implements the ProtocolPublisher duck-type interface but writes directly to `data_cache/mqtt_buffer.db`:
```python
async def update_values(self, values, timestamp=None, current_values=None, mqtt_metadata=None):
    ts = timestamp or _utcnow()
    payload = {"published_at": ts}
    for node_id, (value, _dtype) in values.items():
        col_name = self._tag_names.get(node_id) or node_id.split(".")[-1]
        payload[col_name] = value
    with sqlite3.connect(self.db_path) as con:
        con.execute("INSERT INTO mqtt_buffer VALUES (?, ?)", (ts, json.dumps(payload, default=str)))
```
No broker needed. ACM's existing `_load_mqtt_increment()` reads these rows on the next tick.

### SimAdapter
Singleton held by `acm_service.Service`, exposes clean async API to routes:
- `generate(domain_id, request)` → calls generator_engine, returns GenerateResponse
- `configure_replay(config)` → passes to engine
- `start_replay() / stop_replay() / restart_replay()` → async engine control
- `get_status()` → `ReplayStatus.model_dump()` + `publisher_mode`
- `get_current_values()` → `CurrentValuesResponse.model_dump()`
- `list_files()` → CSV files from all `sim_data/` subdirs

Publisher modes: `buffer` (SDK-level default, writes to mqtt_buffer.db), `mqtt`, `opcua`, `both`
**Note:** The UI defaults `#sim-replay-publisher` to `opcua` — the SDK default `buffer` is never the effective default in practice.

### `/api/sim/*` Routes (`scripts/acm_sim_routes.py`)
**15 routes** under `APIRouter(prefix="/api/sim")`:
- `GET /generators` — list all 11 domains (id, label, description)
- `GET /generators/{id}/spec` — scenarios, parameters, default_output_filename
- `POST /generators/{id}/generate` — generate CSV; body: GenerateRequest
- `GET /files` — list files in sim_data/ (name, size, rows, columns, source)
- `GET /files/{filename}/metadata?source=generated` — column info, type inference, preview
- `DELETE /files/{filename}?source=generated`
- `POST /files/{filename}/register?source=generated` — register file as ACM monitored asset (auto-detects timestamp col) *(added 2026-06-16)*
- `POST /files/upload` — multipart upload
- `GET /status` — SimAdapter.get_status()
- `POST /replay/configure` — body: ReplayConfig
- `POST /replay/start`
- `POST /replay/stop`
- `POST /replay/restart`
- `GET /replay/current-values` — live tag values (poll at 1s in UI)
- `POST /onboard` — generate CSV + register as ACM monitored asset (fast_track supported)

### fast_track maturation bypass
`monitored_assets` gains a `fast_track INTEGER DEFAULT 0` column (migrated on service start):
```python
# In acm_service Service.__init__:
try:
    self.store.execute("ALTER TABLE monitored_assets ADD COLUMN fast_track INTEGER DEFAULT 0")
    self.store.commit()
except Exception:
    pass  # already exists
```
`readiness()` in `acm_feed.py` accepts `fast_track: bool = False`:
```python
effective_min = 0.0 if fast_track else min_train_days
if last_ts is None or span_days < effective_min:
    return "MATURING"
```
When True, assets score on the very first tick even with minutes of live data.

### Backdating (alternative to fast_track)
Generator produces data with timestamps shifted so the last row ≈ now.
`/api/sim/onboard` accepts `backdate_days` (default 45) — enough data for READY status on first tick.

### Simulate UI (4th tab — Frankenstein first pass)
- **Tab 04 Simulate** added to ACM's existing tab rail (additive HTML only)
- Inner sub-tabs: Generate | Files | Replay
- All sim UI uses ACM's existing CSS classes (`.card`, `.btn`, `.data`, `.term`, `.kpi`, `.badge`)
- SIM JavaScript IIFE appended to `app.js` — handles all `/api/sim/*` calls, sub-tab switching, output panel, live values polling at 1s
- 2 new header stat-cells: `#sim-pill` (Replay state), `#sim-file-pill` (Active File)
- 2 new SIM-specific header buttons: `▶ Replay` / `■ Stop` (toggle based on replay state)
- Output panel: fixed bottom strip (180px, collapsible) with All/Sim/ACM filter tabs and `<pre class="term">` log stream

### UI implementation rules (do not break)
- All existing `index.html` section HTML must remain untouched — only additive changes
- All existing `app.js` functions remain untouched — SIM code in its own IIFE appended at bottom
- All existing `style.css` rules remain untouched — only new rules appended
- API Studio UI from Simulator was NOT ported (deferred per user instruction)
- OPC UA settings panel: minimal (publisher mode selector in Replay sub-tab), not a full port

---

## UI Codebase Map — `static/` (app.js / index.html / style.css)
> *Added: 2026-06-14 · Last updated: 2026-06-16*

### app.js — Function Locations (approximate line numbers as of 2026-06-16)

| Function | ~Line | Purpose |
|---|---|---|
| `api(path, opts)` | 9 | Fetch wrapper — throws on non-2xx, returns JSON |
| `badge(state)` | 40 | Returns coloured `<span class="badge">` for asset state |
| `toast(msg, kind)` | 70 | Show bottom-right toast: `ok`/`warn`/`err` |
| `sparklineBar(points)` | 130 | HTML bar trend (div flex, last 10 days) — replaced SVG sparkline for performance |
| `updateCountdown()` | 237 | Updates next-tick countdown every second |
| `refreshOperator()` | 319 | Renders Operator tab: KPIs, fleet matrix, health history, alarm causes |
| `renderTimeline()` | inside refreshOperator | 24-hr alarm timeline blocks (lazy-loaded on expand) |
| `ackAlarm()` | 697 | Opens modal to acknowledge alarm via `POST /api/alarms/ack` |
| `openEngineer(key)` | 713 | Sets `selectedAsset` and switches to Engineer tab |
| `fillAssetSelectors()` | 718 | Fetches fleet, populates `#eng-asset` (scored only) and `#adm-runs-asset` (all) |
| `refreshEngineer()` | 799 | Renders Engineer tab — chart, culprits, heatmap, cofiring, daily, mttd |
| `refreshAdmin()` | 1552 | Renders Admin tab — health, assets table, run history, config, audit |
| `refresh()` | 1779 | Main poll loop called every 20s — calls per-tab refresh |
| SIM IIFE starts | ~2060 | `(function(){ ... })()` — all `/api/sim/*` UI code |
| `refreshFiles()` | 2064 | Renders Files sub-tab table with Preview/→Replay/→ACM/Delete buttons |
| `populateReplayFileList()` | 2124 | Fills `#sim-replay-file` select with files from `/api/sim/files` |
| `sendToReplay(fn, src)` | 2349 | Navigates to Replay sub-tab and pre-selects file |
| `onboardFile(fn, src)` | 2371 | Opens modal to register a SIM file as ACM monitored asset |
| `doUpdate()` | 2430 | Calls `POST /api/service/update`, streams output to log panel |

### app.js — Key Rendering Details

**Fleet Health History** (`refreshOperator`, ~line 484):
- Canvas-based stacked bar chart. `H_bars=130`, `GAP=2`, `barW = max(4, floor((W-16)/days)/GAP)`
- Data from `/api/fleet/sparklines` — `{asset_key: [[dayStr, fusedMax], ...]}`
- Day bucketed: `fusedMax ≥ 3.5 → alarm`, `≥ 2.0 → warn`, else ok
- Legend font 11px `Share Tech Mono`, legend uses CSS vars `--ok / --warn / --bad`

**Top Alarm Causes** (`refreshOperator`, ~line 549):
- 4 categories matched from `rules_fired` string: `sustained`, `rate`, `avail`, `heads:`
- Bar: `height:10px`, label `font-size:13px bold`, count `font-size:11px`
- Background `var(--bg2)`, fill `var(--bad)` at 80% opacity

**Fleet Operations Matrix** (`refreshOperator`, ~line 379):
- `#mega-matrix` div populated with `<div class="mega-hdr">` + per-asset `<div class="mega-asset-row collapsed">`
- Asset rows grouped by farm prefix (everything before first `_` in asset key)
- Double-click → `openEngineer(asset_key)`. Single click toggles alarm episode rows (lazy-loaded)
- Timeline: 24 one-hour blocks, `danger` if `peak_fused > 5.0`, else `warn`
- 8 columns: Asset Name · Status · Trend · Fused · Diagnosis · Timeline · State · Score

**Engineer Chart** (`refreshEngineer`, ~line 830):
- uPlot instance. Series: `[x, fused_z, alert_z, AR1, PCA-SPE, PCA-T2, IForest, GMM, OMR]`
- Series indices 3-8 (detectors) have `show: false` by default — toggled by `.det-toggle` buttons
- `.det-toggle` buttons get `btn.classList.remove("active")` on every render reset

**Co-firing Matrix** (`refreshEngineer`, ~line 1270):
- Canvas. `CELL=44, GAP=2, LABEL=44`, font `bold 11px "Barlow Condensed"`
- Only renders for alarm samples; `freq[r][c] = pct of r-active rows where c also active`
- Uses stored `alarm[i]` column (the rule engine's decision, including self-distrust gate)

**Alarm Pattern Heatmap** (`refreshEngineer`, ~line 1361):
- Canvas. `LABEL_W=42, LABEL_H=20, GAP=1, CELL_H=26`, `CELL_W = max(10, floor((containerW-LABEL_W-12)/24))`
- Day-of-week × hour grid, color = alarm fraction
- Uses stored `alarm[i]` column (same as co-firing matrix)

### index.html — Key Element IDs

| ID | Location | Purpose |
|---|---|---|
| `#mega-matrix` | Operator tab | Fleet operations matrix container |
| `#op-health-chart` | Operator tab | Fleet health history canvas parent |
| `#op-causes-body` | Operator tab | Alarm causes bar chart container |
| `#eng-asset` | Engineer tab | Asset selector dropdown (scored assets only) |
| `#eng-days` | Engineer tab | Days selector (7/30/90) |
| `#eng-chart` | Engineer tab | uPlot chart mount point |
| `#eng-pattern-body` | Engineer tab | Alarm pattern heatmap canvas parent |
| `#eng-cofiring-body` | Engineer tab (adv) | Co-firing matrix canvas parent |
| `#adm-health` | Admin tab | Service health grid (workers, tick, backend) |
| `#adm-assets tbody` | Admin tab | Monitored assets table rows |
| `#adm-runs-asset` | Admin tab | Asset filter for run history |
| `#btn-update-acm-hdr` | Header `.hdr-right` | **Primary Update button** — always visible, `btn-hdr btn-warn` |
| `#btn-runnow` | Header `.hdr-right` | **Score All** — `btn-hdr btn-ok` — triggers scoring on all assets |
| `#btn-sim-start` | Header `.hdr-right` | Replay Start — hidden unless replay configured |
| `#sim-pill` | Header stat strip | Replay state badge |
| `#sim-file-pill` | Header stat strip | Active replay file name |
| `#output-panel` | Page bottom | Log strip (expandable, 180px default) |
| `#output-log` | Inside output panel | `<pre class="term">` log content |
| `#sim-files-body` | Simulate → Files | Files table tbody |
| `#sim-replay-file` | Simulate → Replay | File selector for replay |
| `#sim-replay-source` | Simulate → Replay | Source selector (generated/sample/uploaded) |
| `#sim-replay-publisher` | Simulate → Replay | Publisher mode (opcua/mqtt/both) — defaults to `opcua` |

### style.css — Grid Layouts (advanced mode)

**Operator tab** (`.op-layout`, ~line 1216):
```
columns: 200px 1fr
rows:    auto auto 1fr
areas:   "kpis   health"
         "kpis   causes"    ← causes sits below health, kpis spans both rows
         "matrix matrix"    ← matrix fills 1fr height
```

**Engineer tab** (`.eng-layout`, ~line 1239):
```
columns: 3fr 2fr
rows:    auto auto auto auto auto auto
areas:   "topbar    topbar"
         "culprits  culprits"
         "chart     pattern"
         "mttd      cofiring"   ← mttd (Reliability Metrics) is row 4 — near the top
         "episodes  histogram"
         "daily     daily"
```

**Admin tab** (`.adm-layout`, ~line 1269):
```
columns: 1fr 1fr
rows:    auto auto auto auto
areas:   "health  health"
         "assets  runhist"
         "runs    runs"
         "config  audit"
         "log     log"
```

### style.css — Button Classes

| Class | Appearance | Use |
|---|---|---|
| `.btn` | Base 3-D button, `--brand` accent | General actions |
| `.btn-sm` | `font-size:14px, padding:3px 8px` | Small inline buttons in tables/cards |
| `.btn-hdr` | Semi-transparent, white text, `15px` | Header row buttons |
| `.btn-hdr.btn-ok` | Green, `--ok` | Positive header actions (Score All, Replay Start) |
| `.btn-hdr.btn-bad` | Red, `--bad` | Destructive header actions (Pause, Stop) |
| `.btn-hdr.btn-warn` | Amber, `--warn` | Notable header actions (Update) |
| `.btn-brand` | `--brand` fill | Primary CTA inside cards |
| `.btn-bad` | Red fill | Destructive inline (Delete) |
| `.btn-warn` | Amber fill | Warning inline (Ack alarm) |

---

## API Endpoints — Key Responses
> *Added: 2026-06-14 · Last updated: 2026-06-16*

### `GET /api/fleet`
Returns `list[dict]` — one entry per `monitored_assets` row that is enabled:
```json
{
  "asset_key": "care/A/40",
  "grp": "care_demo",
  "state": "ALARM",            // NEW|MATURING|READY|OK|WARN|ALARM|ERROR|STALE
  "state_detail": null,        // e.g. "Replaying: fault_power_condenser_fouling.csv"
  "last_fused": 3.82,          // null if no score yet
  "last_ts": "2025-10-28T12:48:00Z",
  "last_run_at": "2026-06-16T10:30:00Z",   // null if never scored; used for per-asset poll
  "rules_fired": "sustained deviation",
  "unacked_alarms": 98,
  "source_kind": "csv",
  "source_ref": "/path/to/file.csv"
}
```
`last_fused === null` means asset has never been scored (MATURING/NEW). `fillAssetSelectors()` filters to `last_fused !== null` for the Engineer dropdown. `last_run_at` is used by the per-asset Score button to detect when scoring of a specific asset completes.

### `GET /api/fleet/sparklines`
Returns `{asset_key: [[dayStr, fusedMax], ...]}` — 30-day daily max fused scores per asset.

### `GET /api/service`
```json
{
  "status": "TICKING",
  "backend": "sqlite",
  "workers": 4,
  "tick_minutes": 30,
  "last_tick_at": "2026-06-15T...",
  "last_tick_duration_s": 363.6,
  "runtimes": [...],
  "attention": [...]
}
```

### `POST /api/service/update`
Runs `git pull --ff-only` in ACM root + re-seeds CARE assets. Returns:
```json
{"lines": ["── Pulling...", "Already up to date.", "── Done ──"], "restart_required": true}
```
Output streamed to `#output-log` via `SIM.log()`. Service must be restarted for code to take effect.

### `GET /api/asset/{key}`
Full scored result for engineer view. Key fields: `rows` (list of score dicts), `columns` (list of column names), `idx` (column name → index map), `alert_z` (threshold line value).

### `POST /api/service/run-now`
Triggers immediate scoring. Body: `{}` (all assets) or `{"assets": ["key1", "key2"]}` (targeted). The per-asset Score button in the Fleet Matrix uses the targeted form.

---

## Config Split (enforced by test)
> *Added: 2026-06-14*

- **Human config** (`configs/config_table.csv`, synced to `config` table): categories `data`, `sql`, `runtime` only
- **ML params** (`core/ml_defaults.py`): categories `models`, `thresholds`, `fusion`, `regimes` — NEVER in config_table.csv
- `test_store.py::TestConfigSync::test_acm_run_csv_end_to_end` enforces this: if ML categories appear in config_table.csv the test fails

---

## Windows Compatibility
> *Added: 2026-06-14*

- **Asyncio in tests:** Always `asyncio.run(coro)` — NEVER `asyncio.get_event_loop().run_until_complete(coro)`. On Windows Python 3.8+, `ProactorEventLoop` is stricter; `get_event_loop()` can return a closed loop after `TestClient` consumes it. This caused the one test failure on a fresh Windows install (`test_tick_clears_all_caches` in `test_performance.py`). Fixed by replacing with `asyncio.run()`.
- **Paths:** Always `pathlib.Path` or `os.path.join` — never hardcode `/`.
- **Subprocess:** Pass args as list with `sys.executable` first — never rely on `.py` being directly executable.

---

## Key Implementation Patterns
> *Added: 2026-06-14*

- **Atomic parquet write:** `df.to_parquet(tmp)` then `os.replace(tmp, path)` — crash-safe, file is never half-written
- **Column-pruning for `since`:** `_read_ts_column()` reads only the timestamp column via PyArrow — avoids loading all 600+ sensor columns just to find the max timestamp
- **Adaptive score window:** `score_eff = min(score_days, max(1.0, span_days / 3.0))` — prevents young assets from starving the train side of the split
- **ProcessPool pickling:** `score_cached()` takes plain strings/dicts, returns plain dicts — nothing unpicklable crosses process boundaries
- **Bridges in parent process only:** OPC UA and MQTT bridges live in the service process (asyncio task / daemon thread). Workers only read SQLite. Never start a bridge in a worker.
- **Timezone consistency:** OPC UA/MQTT bridges write UTC-aware timestamps (`datetime.now(timezone.utc).isoformat()`). CSV files may have naive local timestamps. Mixing sources for a single asset requires consistent UTC-aware timestamp columns.

---

## Mistakes Made in Earlier Sessions (Never Repeat)
> *Added: 2026-06-14 · Last updated: 2026-06-16*

1. *(2026-06-14)* **Added ACM references to Simulator** — `ACM_DIR` variable in `suite_runtime.py`, ACM chip in portal HTML, ACM port in launchPorts. All reverted. The constraint is absolute: zero ACM knowledge in Simulator.
2. *(2026-06-14)* **Built MQTT-first integration** — wrong priority order. OPC UA is priority 1 because it's already implemented in the Simulator. MQTT is secondary.
3. *(2026-06-14)* **Called OPC UA "ACM's preferred source"** — wrong framing. OPC UA is just the wire between Simulator and ACM. ACM has equal support for all source kinds.
4. *(2026-06-14)* **Self-test aborting the install** — a test failure ≠ broken install. Packages installed + imports verified = working install. Self-test must be non-fatal.
5. *(2026-06-14)* **`asyncio.get_event_loop().run_until_complete()` in tests** — fails on Windows. Always `asyncio.run()`.
6. *(2026-06-14)* **Omitting `asyncua`/`paho-mqtt` from pip install** — bridges silently fail with ImportError. Always include them.
7. *(2026-06-14)* **`Select-Object -Last 1` inside a scriptblock already redirected to log** — redundant, and the pipe can confuse PowerShell's `$LASTEXITCODE` tracking.
8. *(2026-06-14)* **Launching agents with `isolation: "worktree"`** — fails because `/home/user` is not a git repo. Always omit isolation parameter; work directly in `/home/user/ACM/` or `/home/user/Simulator/`.
9. *(2026-06-14)* **Agents launching research sub-agents instead of doing the work** — wastes context. If the task is clear, do the implementation directly; only spawn agents for genuinely parallel independent work.
10. *(2026-06-14)* **`pd.to_datetime` without `format='ISO8601'`** — generators write timestamps with fractional seconds (`2026-01-01T00:00:00.100000Z`). Without `format="ISO8601", utc=True`, pandas raises a parse error. Always use `pd.to_datetime(df[col], format="ISO8601", utc=True)` in `acm_feed.py` for CSV timestamps.
11. *(2026-06-14)* **Replay pill not updating immediately** — `refreshSimStatus()` polls every 3 seconds. After `doStartReplay()` / `doStopReplay()` succeeds, call `refreshSimStatus()` immediately so the header stat-cell reflects the new state without a 3-second lag. Fixed in `app.js`.
12. *(2026-06-14)* **Playwright `wait_for_function` picks up stale DOM** — after a sub-tab switch, `wait_for_function("length > 0")` may fire on cached content before the async API fetch completes. Use `wait_for_function(f"length > {previous_count}")` when you expect the count to change, or `wait_for_selector` for a specific element.
13. *(2026-06-15)* **`Step "Fault datasets"` was fatal in `setup_acm.ps1`** — caused the whole installer to abort if `generate_fault_dataset.py` exited non-zero on Windows. Fixed by switching to the non-fatal warn pattern (same as self-test). The fault CSVs are pre-committed in `sim_data/sample/` so the step is "nice to regenerate" only.
14. *(2026-06-15)* **UI base font-size 13px is too small on standard Windows displays** — increased to 15px. All component pixel sizes scaled up proportionally (+2 to +3px). See "UI Font Sizes" section below for the canonical values.
15. *(2026-06-15)* **`--sim-dir` flag does not exist in `download_care_dataset.py`** — the script only has `--dest`, `--farms`, `--count`. The default `--dest` already points to `sim_data/sample` so no extra flag is needed. CLAUDE.md had the wrong flag; setup scripts now corrected. The CARE Dataset section has also been corrected.
16. *(2026-06-15)* **`setup.sh` had three bugs**: (a) duplicate pip install block (pyodbc optional then same packages again mandatory), (b) `warn_step "Self-test" ... | tail -3` pipe was applying to warn_step's own printf output, not pytest, (c) `step "Fault datasets"` was fatal. All fixed: single install block, pipe removed, fault step changed to `warn_step`.
17. *(2026-06-15)* **`setup_acm.ps1` missing packages**: `python-multipart`, `openpyxl`, `pydantic` were absent from the pip install list but required by FastAPI multipart upload and sim routes. Also missing `structlog`, `matplotlib`, `pytest`, `httpx` (were present but needed to stay). All added.
18. *(2026-06-15)* **OPC UA is now the default replay transport in the UI** — `#sim-replay-publisher` dropdown defaults to `opcua`. `BufferPublisher` (mqtt_buffer.db) is the SDK-level default but is never the effective default in practice. `_register_opcua_in_acm()` in `acm_sim_routes.py` auto-registers `simulator/opc_ua` asset and triggers run-now when replay starts in opcua/both mode.
19. *(2026-06-15)* **`fillAssetSelectors()` race condition** — calling it inside every `refreshEngineer()` caused concurrent poll calls to overwrite the dropdown during an async await, showing the wrong asset's chart. Fix: `fillAssetSelectors()` only in the `refresh()` poll loop, never inside `refreshEngineer()`. `cachedEngineerData = null` in the change handler forces fresh fetch.
20. *(2026-06-15)* **Files tab + Preview were slow** — `pd.read_csv` with `sep=None, engine='python'` scanned the entire file to detect delimiter. Fixed by replacing with `csv.Sniffer` reading only the first 8KB for dialect detection, then `csv.DictReader` for row reading. No pandas import for column count / preview in `sim/csv_manager.py`.
21. *(2026-06-15)* **Detector series hidden by default** — added `show: false` to all 6 detector series in uPlot config. `btn.classList.remove("active")` on every chart render resets toggle button states. Only fused z + alert_z are shown by default.
22. *(2026-06-15)* **Engineer tab grid layout** — `mttd` (Reliability Metrics) moved from last row to row 4 (beside cofiring), so it appears near the top-right after the chart. Layout: topbar → culprits → chart/pattern → mttd/cofiring → episodes/histogram → daily/daily.
23. *(2026-06-15)* **Co-firing matrix and alarm heatmap readability** — CELL increased to 44 (from 28), LABEL to 44 (from 32), font to 11px (from 7px). Alarm pattern CELL_H to 26 (from 20), LABEL_W to 42 (from 30), LABEL_H to 20 (from 16), fonts to 11px/10px.
24. *(2026-06-15)* **Files tab → Replay navigation** — `sendToReplay(filename, source)` added to SIM IIFE. Calls `populateReplayFileList()` then sets the replay file select to the target file. "→ Replay" button added in Files table Actions column.
25. *(2026-06-15)* **Operator tab layout overhaul** — "Top Alarm Causes" moved to right column directly below Fleet Health History (causes now in row 2 beside kpis, matrix takes full-width row 3 with `1fr` height). Fleet Health History bars increased 90→130px, legend font 9→11px. Alarm Causes bars 5→10px, label 11→13px bold, count 9→11px. Grid: `auto auto 1fr` rows with `kpis` spanning rows 1-2 via grid-template-areas.
26. *(2026-06-15)* **Update ACM button — made prominent** — moved to header as `#btn-update-acm-hdr` with class `btn-hdr btn-warn` (amber, always visible in header-right alongside Pause/Score All). The old Admin card button (`#btn-update-acm`) was removed. Both call the same `doUpdate()` helper. `POST /api/service/update` runs `git pull --ff-only` + re-seeds assets (line 674 in `acm_service.py`). Requires service restart to apply code changes.
27. *(2026-06-15 — SUPERSEDED by mistake #33)* **Alarm shading was temporarily switched to `fused > alertZ`** — this was done and then immediately reverted (`f85f293`). The stored `alarm[i]` column is the correct source. See mistake #33 for the definitive rule. Do not re-implement `fused > alertZ` for visual requests.
28. *(2026-06-15)* **Alarm shading opacity doubled** — all `--chart-alarm-fill` CSS vars increased from ~0.20-0.25 to ~0.40-0.50 across all 11 themes.
29. *(2026-06-15)* **Reliability Metrics whitespace fixed** — `align-self: start` added to `.eng-mttd`. Without this the grid item stretches to fill the co-firing matrix's tall cell, creating empty space below the 4 KPI tiles.
30. *(2026-06-15)* **sendToReplay race condition fixed** — clicking `[data-sim-pane="replay"]` triggered `populateReplayFileList()` concurrently with our explicit `await populateReplayFileList()` call, causing the auto-selected first file to overwrite our target. Fix: switch pane directly via DOM classList manipulation (no `.click()`), then `await populateReplayFileList()`, then set `sel.value` and call `loadTagPlan()`.
31. *(2026-06-15)* **Setup script Next Steps made unmissable** — both `setup_acm.ps1` and `setup.sh` now show a yellow double-line box (╔═╗ style) with START THE SERVICE, python command, URL, and RUN NOW instruction. Was previously easy to miss in the wall of install output.
32. *(2026-06-15)* **CLAUDE.md got a Table of Contents** — added at the top. Jump targets: "Start here for UI work" → UI Codebase Map; "Read before starting any task" → Mistakes Made.
33. *(2026-06-15)* **NEVER change alarm logic when asked for visual prominence** — when user says "make the shading more prominent", that means increase CSS opacity / color intensity ONLY. It does NOT mean change the data logic. The co-firing matrix, alarm pattern heatmap, and chart shading all intentionally use the stored `alarm[i]` column which reflects the rule engine's decision (including self-distrust gate). Changing the source data breaks the semantics. Only touch CSS (`--chart-alarm-fill` opacity) for prominence requests. The brief switch to `fused > alertZ` (see mistake #27) was reverted — `alarm[i]` is the permanent correct choice.
34. *(2026-06-16)* **Fleet Operations Matrix fonts were inherited and undersized** — the mega-matrix asset rows, headers, and episode details were using inherited `body` font-size (15px) instead of explicit larger sizes. This made dense table text difficult to read at standard monitor distance. Also, column widths (90px for Status, 130px for Trend, etc.) were too tight, causing header text like "STATUS /" to wrap awkwardly. Fixed by: (a) explicit font-size: 17px on .mega-hdr, .mega-asset-row, .mega-alarm-row, (b) expanding column widths by 20–30px, (c) increasing timeline block height from 16→20px, (d) padding rows more generously. The grid template should never have columns < 100px for text content — always reserve space for unwrapped labels.
35. *(2026-06-16)* **Polling `tick_in_progress` for per-asset completion** — this is a global flag; if any other asset finishes first, the poll terminates early. Always poll `last_run_at` for the SPECIFIC asset from `/api/fleet`.
36. *(2026-06-16)* **Constructing `source_ref` in the frontend** — `sim_data/sample/file.csv` is a relative path that works only if CWD = ACM root. Use the backend `/api/sim/files/{fn}/register` endpoint which calls `csv_manager.resolve_csv_path()` for the absolute path.
37. *(2026-06-16)* **Not adding `state_detail` to PATCH allowed fields** — silent 422 was swallowed by `catch (_) {}`. Always check PATCH endpoints have the fields you need before writing frontend code that PATCHes them.

---

## Detailed Data Flow (per source kind)
> *Added: 2026-06-14*

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
> *Added: 2026-06-14*

- **No score being produced:** check `readiness()` — likely MATURING (< 14 days) or STALE (> 24h gap)
- **OPC UA data not arriving:** check `data_cache/opcua_buffer.db` for recent rows; if empty the bridge disconnected — check `acm_service` logs for `last_error`
- **MQTT data not arriving:** check `data_cache/mqtt_buffer.db`; verify broker is up and topic matches `industrial-tag-simulator/flat`
- **Wrong asset columns:** query `monitored_assets` — verify `timestamp_col`, `status_col`, `source_kind` are correct for the asset
- **Degenerate split error:** span too short for the adaptive window — wait for more data to accumulate (MATURING gate should catch this)
- **Inspect raw cache:** `pd.read_parquet("data_cache/{asset_key}.parquet")` — check columns, timestamps, NaN density

---

## Future-Agent Guidance
> *Added: 2026-06-14*

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

### If modifying the `sim/` package:
- Keep the ProtocolPublisher duck-type interface: `configure_tags(config)`, `start()`, `stop()`, `update_values(values, timestamp, current_values, mqtt_metadata)`, `get_endpoint()`, `get_status()`
- `BufferPublisher` writes to `data_cache/mqtt_buffer.db` — the same file ACM's `_load_mqtt_increment()` reads
- All 11 generators follow the same contract: `generator.generate(GenerateRequest) -> list[dict]`
- `csv_manager.py` paths: `UPLOAD_DIR = ROOT/"sim_data"/"uploads"`, `GENERATED_DIR = ROOT/"sim_data"/"generated"`, `SAMPLE_DIR = ROOT/"sim_data"/"sample"` where `ROOT = Path(__file__).resolve().parents[1]` (ACM root)
- `sim_adapter.py` is the only file `acm_service.py` and `acm_sim_routes.py` import from `sim/`

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

## Service Start Command
> *Added: 2026-06-14*

```bash
cd ~/ACM
python scripts/acm_service.py
# Opens http://localhost:8765
```

**What this starts:**
- FastAPI service on port 8765
- Async tick scheduler (default 60-second interval) — **starts PAUSED** (user must click Score All or per-asset ▶ Score)
- SimAdapter (in-process: Generate + Replay + BufferPublisher)
- OPC UA bridge (lazy — only when an `opcua` asset is registered)
- MQTT bridge (lazy — only when an `mqtt` asset is registered)

**What this does NOT start:**
- The separate Simulator (`~/Simulator`) — that is a fully independent app with its own `RUN_SIMULATOR.bat` / `python suite_runtime.py`. ACM's embedded `sim/` package handles generation and replay without it.

Optional flags: `--port 8766`, `--backend mssql --conn "..."`, `--db custom.db`

---

## UI Testing
> *Added: 2026-06-14 · Last updated: 2026-06-15*

Playwright end-to-end tests live in `tests/ui/test_ui.py`. Run with:

```bash
cd ~/ACM
python tests/ui/test_ui.py
# Screenshots → /tmp/acm_screenshots_v2/
```

Requires: `pip install playwright && playwright install chromium`

**What the test covers (26 checks):**
1. Page loads, header stat-cells present (REPLAY pill, **Score All** button)
2. All 4 tabs switch correctly
3. Simulate → Generate: 11-domain dropdown populated, CSV generation produces preview
4. Files tab: 12 pre-seeded files listed (10 fault CSVs + any generated), count increases after generate
5. Replay tab: file dropdown populated, configure → start → live tag values (9 tags) → stop
6. Onboard: asset appears in Admin with correct key
7. RUN NOW: tick executes, Operator tab updates
8. Output panel: log content visible, [SIM] prefix present
9. Theme switcher: 11 themes, switching works

**Key element IDs to remember:**
- Preview card: `#sim-preview-card` (not `#sim-gen-preview-card`)
- Preview metadata: `#sim-preview-meta` (text: "36000 rows · 13 columns · filename.csv")
- Onboard key input: `#sim-onboard-key` (not `#sim-asset-key`)
- Files table body: `#sim-files-body`
- Replay file select: `#sim-replay-file`
- Domain select: `#sim-domain-sel`
- Scenario select: `#sim-scenario-sel`
- Output log: `#output-log`

---

## Fault Datasets (`sim_data/sample/`)
> *Added: 2026-06-15*

10 pre-generated CSV files with known fault signatures, committed to git:

| File | Domain | Scenario | Rows | Cols |
|---|---|---|---|---|
| `fault_rotary_bearing.csv` | rotary_equipment | bearing_fault | 72,000 | 13 |
| `fault_rotary_imbalance.csv` | rotary_equipment | rotor_imbalance | 72,000 | 13 |
| `fault_pipeline_small_leak.csv` | petroleum_pipeline | small_leak | 10,800 | 31 |
| `fault_pipeline_large_leak.csv` | petroleum_pipeline | large_leak | 7,200 | 31 |
| `fault_pipeline_pump_trip.csv` | petroleum_pipeline | pump_trip | 7,200 | 31 |
| `fault_pipeline_sensor_drift.csv` | petroleum_pipeline | sensor_drift | 10,800 | 31 |
| `fault_power_tube_leak.csv` | power_plant | tube_leak | 7,200 | 13 |
| `fault_power_condenser_fouling.csv` | power_plant | condenser_fouling | 10,800 | 13 |
| `fault_gas_compressor_trip.csv` | gas_pipeline | compressor_trip | 7,200 | 16 |
| `fault_gas_leak.csv` | gas_pipeline | leak | 10,800 | 16 |

**Fault injection structure:** First 40% of rows are `state=NORMAL` (ACM trains on this). Remaining 60% are the labeled fault state. The `state` column contains the scenario name string.

**Regenerate:** `python scripts/generate_fault_dataset.py` — overwrites `sim_data/sample/fault_*.csv`.

**Wrong scenario names discovered (use these):**
- power_plant: `tube_leak`, `condenser_fouling` (NOT `load_rejection`)
- gas_pipeline: `compressor_trip`, `leak` (NOT `compressor_surge`)
- Use `g.get_spec().scenarios` to list valid scenarios for any generator

---

## Git Workflow
> *Added: 2026-06-14 · Last updated: 2026-06-16*

- Session 013M57Jr3CpacwDMxVebD5r6 — pushed directly to `main`
- Session using `claude/upbeat-hopper-m39epw` — merged to main
- Session using `claude/epic-archimedes-7dkrwf` — merged to main
- Session 01Dkd7AbjS8Sd5ChfYiNa1yR: branch `claude/focused-albattani-t9876j` → merged to `main`
- Session 01UuCboiW9MAKb9AKYYoVt1J (2026-06-16): pushed directly to `main` (per-asset scoring, SIM→ACM flow, perf sprints)
- Pattern: commit to dev branch → push dev → `git checkout main` → `git merge dev --no-edit` → `git push origin main`
- If push fails due to diverged remote: `git pull origin main --rebase` then push again
- Never force-push, never `--no-verify`

---

## UI Font Sizes (canonical after 2026-06-15 upsize)
> *Added: 2026-06-15*

All sizes live in `static/style.css`. Changed from the original small-screen values to be readable on standard Windows displays.

| Element | Before | After |
|---|---|---|
| `body` base | 13px | 15px |
| `body` line-height | 1.45 | 1.50 |
| `input/select/textarea` | 12px | 14px |
| `.btn` | 12px | 13px |
| `.btn-sm` | 10px | 11px |
| `.btn-hdr` | 11px | 12px |
| `.tab` | 12px | 13px |
| `.tab-num` | 9px | 10px |
| `.card-title` | 12px | 13px |
| `table.data td` | 11.5px | 13px |
| `table.data th` | 10px | 11px |
| `[data-mode="advanced"] table.data td` | 11px | 12px |
| `[data-mode="advanced"] table.data th` | 9px | 10px |
| `.kpi-num` | 14px | 16px |
| `.kpi-cap` | 10px | 11px |
| `.stat-cell .lbl` | 8px | 9px |
| `.stat-cell .val` | 11px | 13px |
| `.badge` | 10px | 11px |
| `.chip` | 11px | 12px |
| `.hint` | 11px | 12px |
| `.term` | 11px | 13px |
| `.toast` | 12px | 13px |
| `.health-cell .v` | 14px | 16px |
| `.health-cell .k` | 10px | 11px |
| `.msgbar` | 11px | 12px |
| `.attn div` | 11px | 12px |
| `.mega-farm-hdr` | 12px | 17px |
| `.mega-hdr` | 15px (inherited) | 17px |
| `.mega-asset-row` | 15px (inherited) | 17px |
| `.mega-alarm-row` | 14px | 17px |
| `table.data` (general) | 12–14px | 16–18px |

---

## Fleet Operations Matrix (Operator Tab) — Styling Learnings (2026-06-16)
> *Added: 2026-06-16*

**Issue:** Text was "way too small" — asset names, status, diagnosis, episode details all difficult to read.

**Root causes:**
1. Font sizes inherited from body (15px) — too small for a dense data table
2. Column widths were too tight, causing header text to wrap awkwardly (e.g., "STATUS /" split across lines)
3. Episode expansion rows had no explicit font-size styling
4. Timeline blocks were 16px height — narrow and hard to click

**Fixes applied:**
1. **Font sizes:** All mega-matrix elements now 16–17px (headers 17px, data rows 17px, episodes 16–17px)
2. **Column widths (expanded by 20–30px total):**
   - Asset name: 180→200px min, 260→280px max
   - Status: 90→110px
   - Trend: 130→150px
   - Fused: 70→90px
   - Diagnosis: 220→240px
   - Timeline: 60→70px
   - Score: 80px (new 8th column added 2026-06-16)
3. **Row heights:** Header 33→38px, asset rows padding 10→12px vertical
4. **Timeline blocks:** 16px→20px height for better visibility
5. **Farm group header:** 12px→17px font, padding 6→8px

**Current grid template (8 columns):**
```css
grid-template-columns: minmax(200px, 280px) 110px 150px 90px 1fr 240px 70px 80px;
```
Applied to `.mega-hdr`, `.mega-asset-row`, `.mega-alarm-row`.

**Result:** Headers display cleanly without wrapping, all text readable at standard monitor distance, better visual hierarchy.

---

## Fleet Operations Matrix Performance Optimization (2026-06-16)
> *Added: 2026-06-16*

**Problem:** Matrix was taking 800-1200ms to render for 100-asset fleets (user reported "too slow for my liking")

**Diagnosis:** Six bottlenecks identified:
1. Sequential append() calls triggering 415+ reflows (300-400ms)
2. SVG sparkline creation with 22 DOM ops each, 100 assets = 2,200 operations (50-100ms)
3. Date constructor calls in nested loops (2,400+ Date objects) (30-50ms)
4. 200+ querySelector() calls to find DOM elements (20-30ms)
5. O(n²) farm grouping via repeated fleet.filter() calls (5-10ms)
6. Large API payloads (50-150KB) (50-100ms)

**Sprint 1: DOM Optimization (50-63% improvement, 4 hours)**
- `sparkline()` SVG → `sparklineBar()` HTML bars (simple div flex layout, 3 DOM ops vs 22)
- Pre-computed alarmsByAsset map (eliminates O(n²) renderTimeline lookups)
- Pre-parsed dates into dateCache (eliminates 2,400+ Date constructor calls in loops)
- Pre-computed farm groups (eliminates O(n²) filtering)
- DocumentFragment batching (reduces 415+ reflows → 1 reflow)
- Data attributes instead of querySelector (faster element access)
- **Result:** 380-550ms savings (total 1.0s → 500-600ms for 100 assets)

**Sprint 2: Debounce on data equality (10-24% additional, ~1 hour)**
- Added `_dataHash()` function for lightweight change detection
- Skip refreshOperator() DOM rebuild if fleet+alarms unchanged (200-500ms)
- Skip refreshAdmin() table rebuild if asset list unchanged (50-100ms)
- **Result:** Saves rendering work on ticks with no data changes (most ticks are stable)
- **Impact:** On-tick time for 100 assets with no changes: 500-600ms → 100-150ms

**Sprint 3.2: Lazy-load alarm episodes (40-60% reduction when many alarms, ~1 hour)**
- Don't render alarm detail rows on initial load
- Create alarm rows on-demand when user expands asset
- For 100 assets × 2 alarms = 200 alarm rows: saves 200 renderTimeline() calls
- **Result:** Initial page load 300-400ms faster
- **Impact:** Page becomes interactive faster, users see fleet matrix in ~200ms

**Combined Impact (all three sprints):**
- Initial page load: 50-80% faster (Sprint 1 + 3.2)
- Subsequent ticks with changes: 50-63% faster (Sprint 1)
- Subsequent ticks without changes: 70%+ faster (Sprint 1 + 2)
- For fleets with 50+ alarms: 80%+ faster overall

**Commits:**
- `0e73e1c` Sprint 1: Fleet Operations Matrix performance optimization
- `7aacba5` Sprint 2: Debounce refresh on data equality
- `c0c6488` Sprint 3.2: Lazy-load alarm episodes

**Implementation notes:**
- All optimizations are backward-compatible — no API changes
- Lazy-load uses closure to capture alarm state per asset
- Hash function is simple (length + character-sum), not cryptographic, sufficient for equality check
- `sparklineBar()` uses last 10 days of data (vs full 30-day trend in old SVG)

---

## Per-Asset Scoring & SIM→ACM Flow (2026-06-16)
> *Added: 2026-06-16*

### Two User Flows (architecture decision)
Only two valid flows for getting data into ACM:
1. **Admin Onboard tab** — register any source (SQL table, OPC UA endpoint, arbitrary CSV path) directly. Technical/raw, no guardrails. For power users.
2. **SIM flow** — pick/generate a CSV in Simulate tab → either stream via OPC UA or register as CSV asset → score from Operator tab.

CARE CSVs live in `sim_data/sample/` → they appear in SIM Files tab → they go through Flow 2 like any other file. CARE is not a separate flow.

### Per-Asset Score Button (Fleet Operations Matrix)
- Fleet Matrix now has 8 columns (was 7). 8th col: `Score` (80px)
- Each asset row has a `▶ Score` button that calls `POST /api/service/run-now {assets: [key]}`
- MATURING assets show disabled "Maturing" button with tooltip — don't hide the button
- **Completion detection**: polls `/api/fleet` for the specific asset's `last_run_at` to change (NOT global `tick_in_progress` — that's a false positive if other assets score simultaneously)
- CSS: `grid-template-columns: minmax(200px, 280px) 110px 150px 90px 1fr 240px 70px 80px` on all three selectors: `.mega-hdr`, `.mega-asset-row`, `.mega-alarm-row`

### Diagnosis Column — state_detail fallback
Matrix Diagnosis column shows (in order of priority):
1. `formatRulesForOperator(rules_fired)` — when asset has been scored
2. `state_detail` (italicised, muted) — when not yet scored (e.g., "Replaying: condenser_fouling.csv")
3. `—` — nothing to show

### PATCH /api/monitored-assets allows state_detail
Added `state_detail` to the allowed set (`acm_service.py:~534`). This enables the replay start/stop code to update what file is replaying on the `simulator/opc_ua` row. **Previously this silently returned 422.**

### SIM Files tab — "→ ACM" button
- New button `→ ACM` in Files tab per-row calls `POST /api/sim/files/{filename}/register?source={source}`
- **Why backend endpoint, not frontend path construction**: `source_ref` must be an absolute path — `csv_manager.resolve_csv_path()` does this server-side. Frontend cannot safely construct it.
- **Timestamp column auto-detection** in `_detect_timestamp_col()`: priority `timestamp → time_stamp → ts → first col with 'time'/'date'`
  - CARE CSVs: `time_stamp` (detected correctly)
  - SIM-generated CSVs: `timestamp` (detected correctly)
- **Conflict handling**: returns 409 if asset_key already exists → frontend shows "use a different key" warning
- `fast_track=True` is the default for Files → ACM onboard (bypasses 14-day gate so scoring works immediately)

### ACM Service Startup — PAUSED by default
`acm_store.py:get_service_state()` seeds `paused=1` on first run. Service starts idle; user must click "Score All" or per-asset "▶ Score" to begin scoring.

---

## User Working Style
> *Added: 2026-06-14*

- Expects things to work end-to-end after one command — not "technically correct but incomplete"
- Direct and blunt when something is wrong — correct course immediately, don't justify
- Wants resilient installers: warn on non-critical failures, never abort
- Expects knowledge base to be maintained proactively after every agent report
- "Single UI" is a stated long-term goal for both tools

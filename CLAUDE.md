# ACM — Codebase Knowledge Base

> Maintained for future agents. Update this file whenever you learn something new about the codebase.
> Last updated: session 0168vrVWFEf7duHxBcFHMkay (2026-06-16) — UI audit pass; font sizes corrected, element IDs expanded, Help tab documented, Simulate→ACM flow documented

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
25. [UI Font Sizes](#ui-font-sizes-actual-as-of-2026-06-16)
26. [Simulator → ACM UX Flow](#simulator--acm-ux-flow)
27. [User Working Style](#user-working-style)

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
| `setup.sh` | One-command Linux/macOS installer (mirrors setup_acm.ps1) |
| `docs/ml-book.html` | Self-contained interactive ML reference book — 8 chapters, Chart.js demos, Forge Dark theme, print-optimised |
| `static/index.html` | Single-page UI entry point (Operator / Engineer / Admin / Simulate tabs) |
| `static/app.js` | Client-side polling, chart rendering, API commands; SIM IIFE module appended |
| `static/style.css` | 14 themes (5 dark, 9 light); sim/output panel rules appended |
| `sim/` | Vendored simulator package — generators, replay engine, BufferPublisher, SimAdapter |
| `scripts/acm_sim_routes.py` | FastAPI router `prefix="/api/sim"` — 14 routes for generators, files, replay, onboard |

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

## Setup Scripts

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

**download_care_dataset.py**: `--dest` optional (defaults to `sim_data/sample`); `--farms A --count 10` is all you need.

**`step` helper** — prints `·  name`, runs command, overwrites with `✓` (green) or `✗` (red) + exits.
**`warn_step` helper** — same but prints `!` (yellow) + continues on failure.

---

## CARE-to-Compare Dataset

- Zenodo URL: `https://zenodo.org/records/15846963/files/CARE_To_Compare.zip?download=1`
- Farm A: 22 events × ~36 MB (~800 MB total), 86 sensor features per event, CSV per event
- Farm B: 37 events, 257 features; Farm C: 36 events, 957 features
- CSV columns: `time_stamp`, `status_type_id`, sensor columns, `train_test`
- Download: `python scripts/download_care_dataset.py --dest care_data --farms A --count 10 --sim-dir sim_data/sample`
  - `--count N` applies to CSV files only (keeps README); N=10 ≈ 360 MB
  - `--sim-dir` copies downloaded CSVs to that directory as `wind_turbine_farm{X}_{i:02d}.csv`
- Seed: `python scripts/acm_seed_demo.py --care-dir care_data --db acm_results.db`
- Asset key pattern: `care/{farm_letter}/{csv_stem}` e.g. `care/A/40`
- Group: `care_demo`
- CARE CSVs in `sim_data/sample/` appear in ACM's Simulate → Files tab for replay

---

## Simulator Integration — `sim/` Package

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

Publisher modes: `buffer` (default, writes to mqtt_buffer.db), `mqtt`, `opcua`, `both`

### `/api/sim/*` Routes (`scripts/acm_sim_routes.py`)
14 routes under `APIRouter(prefix="/api/sim")`:
- `GET /generators` — list all 11 domains (id, label, description)
- `GET /generators/{id}/spec` — scenarios, parameters, default_output_filename
- `POST /generators/{id}/generate` — generate CSV; body: GenerateRequest
- `GET /files` — list files in sim_data/ (name, size, rows, columns, source)
- `GET /files/{filename}/metadata?source=generated` — column info, type inference, preview
- `DELETE /files/{filename}?source=generated`
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
- 2 new header buttons: `▶ Replay` / `■ Stop` (toggle based on replay state)
- Output panel: fixed bottom strip (180px, collapsible) with All/Sim/ACM filter tabs and `<pre class="term">` log stream

### UI implementation rules (do not break)
- All existing `index.html` section HTML must remain untouched — only additive changes
- All existing `app.js` functions remain untouched — SIM code in its own IIFE appended at bottom
- All existing `style.css` rules remain untouched — only new rules appended
- API Studio UI from Simulator was NOT ported (deferred per user instruction)
- OPC UA settings panel: minimal (publisher mode selector in Replay sub-tab), not a full port

---

## UI Codebase Map — `static/` (app.js / index.html / style.css)

### app.js — Constants & Module Structure

- `POLL_MS = 20000` (line 7) — main tab refresh interval (20s)
- `activeTab` (line 169) — tracks which main tab is active; updated on `.tab` click
- Mode toggle: `applyMode(mode)` (line 202) — sets `document.documentElement.dataset.mode`, persists to `localStorage("acm-mode")`, re-renders active tab. Called by `#btn-mode` click.
- `SIM` IIFE: `const SIM = (() => { ... })()` (line 1690) — encapsulates all simulator UI state. Public API: `{ init, previewFile, deleteFile, sendToReplay, log }`. Called as `SIM.init()` on DOMContentLoaded.

### app.js — Function Locations (accurate line numbers)

| Function | Line | Purpose |
|---|---|---|
| `api(url, opts)` | 140 | Fetch wrapper — throws on non-2xx, returns JSON |
| `toast(msg, kind)` | 155 | Show bottom-right toast: `ok`/`warn`/`err` |
| `badge(state)` | 162 | Returns coloured `<span class="badge">` for asset state |
| `sparkline(data)` | 170 | Mini SVG trend line from sparkline array |
| `refreshService()` | 227 | Fetches `/api/service`, updates header stat-cells |
| `updateCountdown()` | 247 | Updates next-tick countdown every second |
| `applyMode(mode)` | 202 | Toggles basic/advanced, persists to localStorage, re-renders active tab |
| `refreshOperator()` | 321 | Renders Operator tab: KPIs, fleet matrix, health history, alarm causes |
| `renderTimeline()` | 348 | 24-hr alarm timeline blocks inside `refreshOperator` |
| `ackAlarm()` | 598 | Opens modal to acknowledge alarm via `POST /api/alarms/ack` |
| `openEngineer(key)` | 614 | Sets `selectedAsset` and switches to Engineer tab |
| `fillAssetSelectors()` | 619 | Fetches fleet, populates `#eng-asset` (scored only) and `#adm-runs-asset` (all) |
| `refreshEngineer()` | 696 | Renders Engineer tab — chart, culprits, heatmap, cofiring, daily, mttd |
| `refreshAdmin()` | 1443 | Renders Admin tab — health, assets table, run history, config, audit |
| `refresh()` | 1665 | Main poll loop: calls `refreshService()` + active-tab refresh every `POLL_MS` |
| SIM IIFE starts | 1690 | `const SIM = (() => { ... })()` — all `/api/sim/*` UI code |
| `doGenerate()` | 1876 | Calls `/api/sim/generators/{domain}/generate`, shows preview card |
| `doOnboard()` | 1920 | Posts to `/api/sim/onboard` then `/api/monitored-assets` to register asset |
| `refreshFiles()` | 1952 | Renders Files sub-tab table with Preview/→Replay/Delete buttons |
| `handleUpload(file)` | 1998 | Uploads file via `/api/sim/files/upload` multipart |
| `populateReplayFileList()` | 2012 | Fills `#sim-replay-file` select with files from `/api/sim/files` |
| `doConfigure()` | 2073 | POSTs replay config to `/api/sim/replay/configure`, enables Start button |
| `doStartReplay()` | 2103 | POSTs to `/api/sim/replay/start`, logs OPC UA/buffer flow note |
| `doStopReplay()` | 2122 | POSTs to `/api/sim/replay/stop` |
| `refreshLiveValues()` | 2138 | Polls `/api/sim/replay/current-values` every 1s when replay is running |
| `refreshSimStatus()` | 2160 | Polls `/api/sim/status` every 3s, updates `#sim-pill` + `#sim-file-pill` |
| `sendToReplay(fn, src)` | 2221 | Navigates to Replay sub-tab, sets file dropdown, calls `loadTagPlan()` |
| `doUpdate()` | ~2285 | POSTs to `/api/service/update`, streams lines to output panel via `SIM.log()` |

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
- Each row has `title="Double-click to open in Engineer tab"` and `ondblclick → openEngineer(asset_key)`
- Single click toggles alarm episode rows (chevron ► / ▼)
- State cell shows badge + `fmtRelTime(a.last_ts)` below it (shows how long ago the asset was last scored)
- Timeline: 24 one-hour blocks, `danger` if `peak_fused > 5.0`, else `warn`

**Engineer Chart** (`refreshEngineer`, ~line 830):
- uPlot instance. Series: `[x, fused_z, alert_z, AR1, PCA-SPE, PCA-T2, IForest, GMM, OMR]`
- Series indices 3-8 (detectors) have `show: false` by default — toggled by `.det-toggle` buttons
- `.det-toggle` buttons get `btn.classList.remove("active")` on every render reset

**Co-firing Matrix** (`refreshEngineer`, ~line 1270):
- Canvas. `CELL=44, GAP=2, LABEL=44`, font `bold 11px "Barlow Condensed"`
- Only renders for alarm samples; `freq[r][c] = pct of r-active rows where c also active`

**Alarm Pattern Heatmap** (`refreshEngineer`, ~line 1361):
- Canvas. `LABEL_W=42, LABEL_H=20, GAP=1, CELL_H=26`, `CELL_W = max(10, floor((containerW-LABEL_W-12)/24))`
- Day-of-week × hour grid, color = alarm fraction

### index.html — Key Element IDs

**Header:**

| ID | Purpose |
|---|---|
| `#svc-pill` | Engine status stat-cell (ok/warn/bad CSS class applied) |
| `#svc-pill-text` | Engine state text: WATCHING / TICKING / PAUSED |
| `#svc-tick-info` | Last run timestamp + duration |
| `#svc-next-tick` | Countdown to next tick (monospace) |
| `#inp-tick` | Tick interval number input (minutes) |
| `#sim-pill` | Replay state stat-cell |
| `#sim-pill-text` | Replay state: STOPPED / RUNNING |
| `#sim-file-pill` | Active replay file stat-cell |
| `#sim-file-text` | Active file name |
| `#btn-mode` | Basic/Advanced toggle — updates `data-mode` on `<html>` |
| `#btn-resume` | Resume service — hidden by default |
| `#btn-pause` | Pause service — visible by default, `btn-bad` |
| `#btn-runnow` | Run Now — `btn-hdr btn-ok` |
| `#btn-sim-start` | Header Replay Start — hidden unless configured, `btn-ok` |
| `#btn-sim-stop` | Header Replay Stop — hidden unless running, `btn-bad` |
| `#btn-update-acm-hdr` | **Primary Update button** — always visible, `btn-hdr btn-warn` |
| `#sel-theme` | Theme selector (11 options: 2 dark + 9 light) |

**Operator tab:**

| ID | Purpose |
|---|---|
| `#kpis` | KPI strip container (5 `.kpi` boxes: total/ok/alarm/attention/unacked) |
| `#mega-matrix` | Fleet operations matrix container |
| `#fleet-count` | Asset count label in matrix card title |
| `#fleet-empty` | Empty state shown when no assets |
| `#op-health-chart` | Fleet health history canvas parent (adv) |
| `#op-causes-body` | Top alarm causes bar chart container (adv) |

**Engineer tab:**

| ID | Purpose |
|---|---|
| `#eng-asset` | Asset selector dropdown (scored assets only) |
| `#eng-days` | Days selector (7/30/90/36500) |
| `#eng-chips` | Status chip strip (state, alert_z, persist, rules_fired) |
| `#eng-culprits` | Culprits message bar — hidden until notes contain "culprits: " |
| `#eng-chart` | uPlot chart mount point |
| `#eng-heatwrap` | Heatmap + labels wrapper |
| `#eng-heatlabels` | Detector name labels for heatmap (6 rows) |
| `#eng-heatmap` | 6-detector heatmap canvas |
| `#eng-state-wrap` | State-change lane wrapper (adv) |
| `#eng-statelabels` | Labels for state lane |
| `#eng-statelane` | State lane canvas (height: 14px) |
| `#eng-pattern-body` | Alarm pattern (day×hour) canvas parent (adv) |
| `#eng-cofiring-body` | Co-firing matrix canvas parent (adv) |
| `#eng-avail-chart` | Availability trend sparkline container (adv) |
| `#eng-episodes` | Alarm episodes table |
| `#eng-eps-empty` | Empty state for episodes table |
| `#eng-daily` | Daily stats table |
| `#eng-histogram-body` | Alarm duration histogram container (adv) |
| `#eng-mttd-body` | Reliability metrics (MTTD/MTTR) container |

**Admin tab:**

| ID | Purpose |
|---|---|
| `#adm-health` | Service health grid (workers, tick, backend) |
| `#btn-onboard` | "＋ Onboard asset" button — opens modal |
| `#adm-assets` | Monitored assets table |
| `#adm-assets-empty` | Empty state for assets table |
| `#adm-runhist-body` | Run duration sparkline (adv) |
| `#adm-runs-asset` | Asset filter for run history |
| `#adm-runs-status` | Status filter for run history (All/OK/ERROR) |
| `#adm-runs` | Run history table |
| `#cfg-filter` | Config table search input |
| `#adm-config` | Configuration table |
| `#adm-audit` | Config audit trail table |
| `#adm-audit-empty` | Empty state for audit table |
| `#adm-log-level` | Run log level filter (all/INFO/WARN/ERROR) |
| `#adm-runlog` | Run log terminal output |

**Simulate tab — Generate sub-tab:**

| ID | Purpose |
|---|---|
| `#sim-domain-sel` | Domain selector (11 generator domains) |
| `#sim-scenario-sel` | Scenario selector (populated from domain spec) |
| `#sim-domain-desc` | Domain description text |
| `#sim-output-filename` | Output filename input |
| `#sim-backdate` | Backdate checkbox (checked by default) |
| `#sim-backdate-days` | Backdate days input (default 45) |
| `#sim-params-card` | Parameters card container |
| `#sim-params-grid` | Parameters input grid (auto-generated) |
| `#btn-generate` | ⚡ Generate CSV button |
| `#sim-gen-status` | Generator status message |
| `#sim-preview-card` | Data preview card (hidden until generation) |
| `#sim-preview-meta` | Preview metadata: "N rows · M columns · filename.csv" |
| `#sim-preview-table` | Preview data table (first few rows) |
| `#sim-onboard-key` | Asset key input (auto-populated from filename) |
| `#sim-onboard-grp` | Group input (default: "sim") |
| `#sim-fast-track` | Fast-track checkbox — skips 14-day maturation gate |
| `#btn-sim-onboard` | ⊕ Onboard Asset button |
| `#sim-onboard-status` | Onboard status — shows "View in Admin →" link on success |

**Simulate tab — Files sub-tab:**

| ID | Purpose |
|---|---|
| `#btn-sim-upload-open` | Upload trigger button |
| `#sim-upload-input` | Hidden file input (accepts .csv, .xlsx) |
| `#btn-sim-files-refresh` | Refresh files list |
| `#sim-files-body` | Files table tbody |
| `#sim-file-preview-card` | File preview card (hidden until preview) |
| `#sim-file-preview-title` | Preview card title (set to filename) |
| `#sim-file-preview-table` | Preview data table |

**Simulate tab — Replay sub-tab:**

| ID | Purpose |
|---|---|
| `#sim-replay-file` | File selector dropdown |
| `#sim-replay-source` | Source display (generated/uploaded/sample) |
| `#sim-replay-hz` | Replay frequency (Hz) |
| `#sim-replay-loop` | Loop mode (loop_forever/once/hold_last/ping_pong) |
| `#sim-replay-tsmode` | Timestamp mode (wall_clock/csv_timestamp_ignore_rate/relative_from_csv) |
| `#sim-replay-publisher` | Publisher mode (opcua/mqtt/buffer/both) — defaults to `opcua` |
| `#sim-mqtt-card` | MQTT settings card (shown only when publisher = mqtt/both) |
| `#sim-mqtt-host` | MQTT broker host |
| `#sim-mqtt-port` | MQTT broker port |
| `#sim-mqtt-prefix` | MQTT topic prefix |
| `#sim-mqtt-device` | MQTT device ID |
| `#sim-tags-card` | Tag plan card |
| `#sim-tags-table` | Tag plan table |
| `#sim-tags-body` | Tag plan tbody (En checkbox, csv_column, tag_name, data_type) |
| `#sim-tag-count` | "N / M enabled" count display |
| `#btn-tags-all` | Enable all tags |
| `#btn-tags-none` | Disable all tags |
| `#btn-replay-configure` | ⚙ Configure button |
| `#btn-replay-start` | ▶ Start button (hidden until configured) |
| `#btn-replay-stop` | ■ Stop button (hidden until running) |
| `#btn-replay-restart` | ⟳ Restart button (hidden until running) |
| `#sim-replay-status-text` | Replay status text (▶ Running / ■ Stopped / Error…) |
| `#sim-live-card` | Live tag values card |
| `#sim-live-updated` | "Updated: HH:MM:SS" timestamp |
| `#sim-live-table` | Live values table |
| `#sim-live-body` | Live values tbody (tag, value, type, updated) |

**Help tab:**

| ID | Purpose |
|---|---|
| `#tab-help` | Help tab pane (5th tab) |
| `#help-tabs` | Help sub-tab rail |
| `#help-pane-guide` | Guide sub-tab — static prose cards for all 4 main tabs |
| `#help-pane-book` | ML Reference Book sub-tab — iframe to `/docs/ml-book.html` |

**Output panel (bottom):**

| ID | Purpose |
|---|---|
| `#output-panel` | Fixed bottom strip (200px, collapsible to 30px) |
| `#btn-output-toggle` | Collapse/expand toggle (∧/∨) |
| `#sel-output-level` | Log level filter (all/warn/error) |
| `#btn-output-clear` | Clear log |
| `#chk-autoscroll` | Auto-scroll checkbox |
| `#output-line-count` | "N lines" counter |
| `#output-log` | `<pre class="term">` log content (all SIM + ACM messages) |

**Modals:**

| ID | Purpose |
|---|---|
| `#modal-backdrop` | Semi-transparent modal overlay |
| `#modal` | Modal dialog (aria-modal="true") |
| `#modal-title` | Modal `<h3>` title |
| `#modal-form` | Modal form (dynamically populated) |

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

**Admin tab** (`.adm-layout`, ~line 1255):
```
columns: 1fr 1fr
rows:    auto auto auto auto auto auto
areas:   "health  health"
         "assets  runhist"    ← runhist (.adm-runhist.adv) hidden in basic mode
         "runs    runs"
         "config  config"     ← config is FULL WIDTH (wide table needs the space)
         "audit   audit"      ← audit is FULL WIDTH separately
         "log     log"
```

### style.css — Button Classes

| Class | Appearance | Use |
|---|---|---|
| `.btn` | Base 3-D button, `--brand` accent | General actions |
| `.btn-sm` | `font-size:14px, padding:3px 8px` | Small inline buttons in tables/cards |
| `.btn-hdr` | Semi-transparent, white text, `15px` | Header row buttons |
| `.btn-hdr.btn-ok` | Green, `--ok` | Positive header actions (Run Now, Replay Start) |
| `.btn-hdr.btn-bad` | Red, `--bad` | Destructive header actions (Pause, Stop) |
| `.btn-hdr.btn-warn` | Amber, `--warn` | Notable header actions (Update) |
| `.btn-brand` | `--brand` fill | Primary CTA inside cards |
| `.btn-bad` | Red fill | Destructive inline (Delete) |
| `.btn-warn` | Amber fill | Warning inline (Ack alarm) |

---

## API Endpoints — Key Responses

### `GET /api/fleet`
Returns `list[dict]` — one entry per `monitored_assets` row that is enabled:
```json
{
  "asset_key": "care/A/40",
  "grp": "care_demo",
  "state": "ALARM",            // NEW|MATURING|READY|OK|WARN|ALARM|ERROR|STALE
  "last_fused": 3.82,          // null if no score yet
  "last_ts": "2025-10-28T12:48:00Z",
  "rules_fired": "sustained deviation",
  "unacked_alarms": 98,
  "source_kind": "csv",
  "source_ref": "/path/to/file.csv"
}
```
`last_fused === null` means asset has never been scored (MATURING/NEW). `fillAssetSelectors()` filters to `last_fused !== null` for the Engineer dropdown.

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
8. **Launching agents with `isolation: "worktree"`** — fails because `/home/user` is not a git repo. Always omit isolation parameter; work directly in `/home/user/ACM/` or `/home/user/Simulator/`.
9. **Agents launching research sub-agents instead of doing the work** — wastes context. If the task is clear, do the implementation directly; only spawn agents for genuinely parallel independent work.
10. **`pd.to_datetime` without `format='ISO8601'`** — generators write timestamps with fractional seconds (`2026-01-01T00:00:00.100000Z`). Without `format="ISO8601", utc=True`, pandas raises a parse error. Always use `pd.to_datetime(df[col], format="ISO8601", utc=True)` in `acm_feed.py` for CSV timestamps.
11. **Replay pill not updating immediately** — `refreshSimStatus()` polls every 3 seconds. After `doStartReplay()` / `doStopReplay()` succeeds, call `refreshSimStatus()` immediately so the header stat-cell reflects the new state without a 3-second lag. Fixed in `app.js`.
12. **Playwright `wait_for_function` picks up stale DOM** — after a sub-tab switch, `wait_for_function("length > 0")` may fire on cached content before the async API fetch completes. Use `wait_for_function(f"length > {previous_count}")` when you expect the count to change, or `wait_for_selector` for a specific element.
13. **`Step "Fault datasets"` was fatal in `setup_acm.ps1`** — caused the whole installer to abort if `generate_fault_dataset.py` exited non-zero on Windows. Fixed by switching to the non-fatal warn pattern (same as self-test). The fault CSVs are pre-committed in `sim_data/sample/` so the step is "nice to regenerate" only.
14. **UI base font-size 13px is too small on standard Windows displays** — increased first to 15px, then to 18px in a later session. All component pixel sizes scaled up proportionally. See "UI Font Sizes" section below for the current actual values with CSS line numbers. (See also Mistake #35 for why this table drifted.)
15. **`--sim-dir` flag does not exist in `download_care_dataset.py`** — the script only has `--dest`, `--farms`, `--count`. The default `--dest` already points to `sim_data/sample` so no extra flag is needed. CLAUDE.md had the wrong flag; setup scripts now corrected.
16. **`setup.sh` had three bugs**: (a) duplicate pip install block (pyodbc optional then same packages again mandatory), (b) `warn_step "Self-test" ... | tail -3` pipe was applying to warn_step's own printf output, not pytest, (c) `step "Fault datasets"` was fatal. All fixed: single install block, pipe removed, fault step changed to `warn_step`.
17. **`setup_acm.ps1` missing packages**: `python-multipart`, `openpyxl`, `pydantic` were absent from the pip install list but required by FastAPI multipart upload and sim routes. Also missing `structlog`, `matplotlib`, `pytest`, `httpx` (were present but needed to stay). All added.
18. **OPC UA is now the default replay transport** — `sim-replay-publisher` dropdown defaults to `opcua`. `BufferPublisher` (mqtt_buffer.db) is no longer the default; it's only used if explicitly chosen. `_register_opcua_in_acm()` in `acm_sim_routes.py` auto-registers `simulator/opc_ua` asset and triggers run-now when replay starts in opcua/both mode.
19. **`fillAssetSelectors()` race condition** — calling it inside every `refreshEngineer()` caused concurrent poll calls to overwrite the dropdown during an async await, showing the wrong asset's chart. Fix: `fillAssetSelectors()` only in the `refresh()` poll loop, never inside `refreshEngineer()`. `cachedEngineerData = null` in the change handler forces fresh fetch.
20. **Files tab + Preview were slow** — `pd.read_csv` with `sep=None, engine='python'` scanned the entire file to detect delimiter. Fixed by replacing with `csv.Sniffer` reading only the first 8KB for dialect detection, then `csv.DictReader` for row reading. No pandas import for column count / preview in `sim/csv_manager.py`.
21. **Detector series hidden by default** — added `show: false` to all 6 detector series in uPlot config. `btn.classList.remove("active")` on every chart render resets toggle button states. Only fused z + alert_z are shown by default.
22. **Engineer tab grid layout** — `mttd` (Reliability Metrics) moved from last row to row 4 (beside cofiring), so it appears near the top-right after the chart. Layout: topbar → culprits → chart/pattern → mttd/cofiring → episodes/histogram → daily/daily.
23. **Co-firing matrix and alarm heatmap readability** — CELL increased to 44 (from 28), LABEL to 44 (from 32), font to 11px (from 7px). Alarm pattern CELL_H to 26 (from 20), LABEL_W to 42 (from 30), LABEL_H to 20 (from 16), fonts to 11px/10px.
24. **Files tab → Replay navigation** — `sendToReplay(filename, source)` added to SIM IIFE. Calls `populateReplayFileList()` then sets the replay file select to the target file. "→ Replay" button added in Files table Actions column.
25. **Operator tab layout overhaul** — "Top Alarm Causes" moved to right column directly below Fleet Health History (causes now in row 2 beside kpis, matrix takes full-width row 3 with `1fr` height). Fleet Health History bars increased 90→130px, legend font 9→11px. Alarm Causes bars 5→10px, label 11→13px bold, count 9→11px. Grid: `auto auto 1fr` rows with `kpis` spanning rows 1-2 via grid-template-areas.
26. **Update ACM button — made prominent** — moved to header as `#btn-update-acm-hdr` with class `btn-hdr btn-warn` (amber, always visible in header-right alongside Pause/Run Now). The old Admin card button (`#btn-update-acm`) was removed. Both call the same `doUpdate()` helper. `POST /api/service/update` runs `git pull --ff-only` + re-seeds assets (line 674 in `acm_service.py`). Requires service restart to apply code changes.
27. **Alarm shading / pattern / co-firing use `fused > alertZ`** — NOT the stored `alarm` boolean column from the DB. The per-row `alarm` column can be 0 even when `fused > alert_z` due to the self-distrust gate in the rule engine. Switching to `fused[i] > alertZ` makes all three visualisations consistent and always show exceedances: chart shading, alarm pattern heatmap, co-firing matrix. `alertZ` comes from `meta.asset.alert_z`.
28. **Alarm shading opacity doubled** — all `--chart-alarm-fill` CSS vars increased from ~0.20-0.25 to ~0.40-0.50 across all 11 themes.
29. **Reliability Metrics whitespace fixed** — `align-self: start` added to `.eng-mttd`. Without this the grid item stretches to fill the co-firing matrix's tall cell, creating empty space below the 4 KPI tiles.
30. **sendToReplay race condition fixed** — clicking `[data-sim-pane="replay"]` triggered `populateReplayFileList()` concurrently with our explicit `await populateReplayFileList()` call, causing the auto-selected first file to overwrite our target. Fix: switch pane directly via DOM classList manipulation (no `.click()`), then `await populateReplayFileList()`, then set `sel.value` and call `loadTagPlan()`.
31. **Setup script Next Steps made unmissable** — both `setup_acm.ps1` and `setup.sh` now show a yellow double-line box (╔═╗ style) with START THE SERVICE, python command, URL, and RUN NOW instruction. Was previously easy to miss in the wall of install output.
32. **CLAUDE.md got a Table of Contents** — added at the top. Jump targets: "Start here for UI work" → UI Codebase Map; "Read before starting any task" → Mistakes Made.
33. **NEVER change alarm logic when asked for visual prominence** — when user says "make the shading more prominent", that means increase CSS opacity / color intensity ONLY. It does NOT mean change the data logic from `alarm[i]` (stored DB boolean) to `fused[i] > alertZ`. The co-firing matrix, alarm pattern heatmap, and chart shading all intentionally use the stored `alarm` column which reflects the rule engine's decision (including self-distrust gate). Changing the source data breaks the semantics of all three visualisations. Only touch CSS (`--chart-alarm-fill` opacity) for prominence requests.
34. **Daily Stats table used to hardcode 21 days** — `daily.slice(0, 21)` in `refreshEngineer()` (line 1071 before 2026-06-16 fix). Fixed to `daily.slice(0, days)` and the daily API call now passes `?days=${days}`. If the backend `/api/assets/{key}/daily` endpoint doesn't accept `days`, the slice-only fix still limits the visible rows correctly.
35. **CLAUDE.md font size canonical table drifted 3px from reality** — a session after 2026-06-15 upsized everything from 15px body to 18px body without updating this file. Always read `style.css` line 654 (`body { font-size: ... }`) to find the actual base before doing UI work. The "UI Font Sizes" table is now corrected to reflect actual CSS values with line numbers.

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

```bash
cd ~/ACM
python scripts/acm_service.py
# Opens http://localhost:8765
```

**What this starts:**
- FastAPI service on port 8765
- Async tick scheduler (default 60-second interval)
- SimAdapter (in-process: Generate + Replay + BufferPublisher)
- OPC UA bridge (lazy — only when an `opcua` asset is registered)
- MQTT bridge (lazy — only when an `mqtt` asset is registered)

**What this does NOT start:**
- The separate Simulator (`~/Simulator`) — that is a fully independent app with its own `RUN_SIMULATOR.bat` / `python suite_runtime.py`. ACM's embedded `sim/` package handles generation and replay without it.

Optional flags: `--port 8766`, `--backend mssql --conn "..."`, `--db custom.db`

---

## UI Testing

Playwright end-to-end tests live in `tests/ui/test_ui.py`. Run with:

```bash
cd ~/ACM
python tests/ui/test_ui.py
# Screenshots → /tmp/acm_screenshots_v2/
```

Requires: `pip install playwright && playwright install chromium`

**What the test covers (26 checks):**
1. Page loads, header stat-cells present (REPLAY pill, RUN NOW button)
2. All 5 tabs switch correctly (Operator, Engineer, Admin, Simulate, Help)
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

- Development branch for session 01Dkd7AbjS8Sd5ChfYiNa1yR: `claude/focused-albattani-t9876j` → merged to `main`
- Previous sessions: 013M57Jr3CpacwDMxVebD5r6 pushed directly to `main`; earlier used `claude/upbeat-hopper-m39epw`, `claude/epic-archimedes-7dkrwf` (both merged to main)
- Pattern: commit to dev branch → push dev → `git checkout main` → `git merge dev --no-edit` → `git push origin main`
- If push fails due to diverged remote: `git pull origin main --rebase` then push again
- Never force-push, never `--no-verify`

---

## UI Font Sizes (actual as of 2026-06-16)

All sizes live in `static/style.css`. Read the file to confirm — do NOT trust this table blindly (see Mistake #35). The base was upsized twice: 13px → 15px (2026-06-15 session) → 18px (a later session that didn't update this file until 2026-06-16 audit).

| Element | Original | Actual Now | style.css location |
|---|---|---|---|
| `body` base | 13px | 18px | line 654 |
| `body` line-height | 1.45 | 1.50 | line 654 |
| `input/select/textarea` | 12px | 17px | line 868 |
| `.btn` | 12px | 16px | line 725 |
| `.btn-sm` | 10px | 14px | line 761 |
| `.btn-hdr` | 11px | 15px | line 762 |
| `.tab` | 12px | 16px | line 784 |
| `.tab-num` | 9px | 13px | line 824 |
| `.card-title` | 12px | 16px | line 850 |
| `table.data td` | 11.5px | 16px | line 894 |
| `table.data th` | 10px | 14px | line 886 |
| `[data-mode="advanced"] table.data td` | 11px | 15px | line 1195 |
| `[data-mode="advanced"] table.data th` | 9px | 13px | line 1197 |
| `.kpi-num` | 14px | 19px | line 918 |
| `.kpi-cap` | 10px | 14px | line 922 |
| `.stat-cell .lbl` | 8px | 13px | line 702 |
| `.stat-cell .val` | 11px | 16px | line 707 |
| `.badge` | 10px | 14px | line 934 |
| `.chip` | 11px | 15px | line 968 |
| `.hint` | 11px | 15px | line 973 |
| `.term` | 11px | 16px | line 1010 |
| `.toast` | 12px | 16px | line 1072 |
| `.health-cell .v` | 14px | 19px | line 995 |
| `.health-cell .k` | 10px | 14px | line 999 |
| `.msgbar` | 11px | 15px | line 1170 |
| `.attn div` | 11px | 15px | line 1003 |
| `.mega-farm-hdr` | 11px | 15px | line 1298 |
| `.mega-alarm-row` | 13px | 16px | line 1127 |

---

## Simulator → ACM UX Flow

The Simulate tab (04) is a developer tool — no basic/advanced gating. Full end-to-end path from data generation to ACM anomaly scoring:

### Path A: CSV → Immediate scoring

```
Simulate → Generate sub-tab
  1. Select domain (e.g. rotary_equipment) + scenario (e.g. bearing_fault)
  2. Set parameters + enable Backdate (45 days default)
  3. Click ⚡ Generate CSV → preview appears in #sim-preview-card
  4. Enter asset key in #sim-onboard-key (auto-populated from filename)
  5. Optionally check Fast-track to skip 14-day maturation gate
  6. Click ⊕ Onboard Asset → POSTs to /api/sim/onboard then /api/monitored-assets
  7. Status shows "✓ Onboarded (READY)" + "View in Admin →" link
  8. Click ⟳ Run now in header → ACM scores the asset immediately
  9. Navigate to Operator tab → asset appears in Mega Matrix
```

### Path B: CSV Replay → Live OPC UA scoring

```
Simulate → Files sub-tab
  1. Find the generated CSV (or a sample file) → click "→ Replay"
    (switches to Replay sub-tab, pre-selects the file)

Simulate → Replay sub-tab
  2. Verify file + source are correct
  3. Set publisher = opcua (default)
  4. Configure tag plan (enable/disable columns)
  5. Click ⚙ Configure → Start button appears
  6. Click ▶ Start → output panel shows:
     "OPC UA replay active — asset simulator/opc_ua auto-registered. Click ⟳ Run now to score immediately."
  7. Click ⟳ Run now → ACM ingests from opcua_buffer.db, scores simulator/opc_ua
  8. Watch Live Tag Values card update every 1s
  9. Navigate to Operator → simulator/opc_ua asset appears in Mega Matrix
  10. Navigate to Engineer → select simulator/opc_ua → see chart
```

### Path C: Manual asset onboarding (no Simulate tab)

```
Admin tab → "＋ Onboard asset" → fill modal:
  - asset_key, group, source_kind (csv/opcua/mqtt/table/query)
  - source_ref (file path or OPC UA endpoint or table name)
  - timestamp_col (default: time_stamp for CSV, published_at for OPC UA/MQTT)
  - conn_ref (only for table/query: pyodbc connection string)
→ Asset appears in Monitored Assets table with state NEW
→ Click ⟳ Run now → state transitions MATURING → READY → OK/ALARM
```

### Key integration details

- **`/api/sim/onboard`** (acm_sim_routes.py) — generates CSV + returns `suggested_onboard` dict. The UI then posts that dict directly to `/api/monitored-assets`.
- **`/api/monitored-assets` POST** — creates or updates a row in `monitored_assets` table. Returns `{asset_key, state}`.
- **OPC UA auto-registration** — when replay starts with publisher=opcua, `acm_sim_routes.py` calls `_register_opcua_in_acm()` to INSERT OR IGNORE the `simulator/opc_ua` asset. No manual step needed.
- **Fast-track** — sets `fast_track=1` in `monitored_assets`. `readiness()` in `acm_feed.py` returns READY immediately regardless of data span. Use when backdating is not possible or for quick demos. Expect higher false positive rates.
- **Publisher modes**: `opcua` → writes to OPC UA server → acm_opcua_bridge → opcua_buffer.db → scoring; `mqtt`/`buffer` → writes to mqtt_buffer.db → scoring; `both` → both simultaneously.

---

## User Working Style

- Expects things to work end-to-end after one command — not "technically correct but incomplete"
- Direct and blunt when something is wrong — correct course immediately, don't justify
- Wants resilient installers: warn on non-critical failures, never abort
- Expects knowledge base to be maintained proactively after every agent report
- "Single UI" is a stated long-term goal for both tools

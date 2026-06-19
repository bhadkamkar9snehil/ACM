# ACM — Codebase Knowledge Base

> Maintained for future agents. Update this file whenever you learn something new about the codebase.
> Last updated: 2026-06-19 — ML pipeline bug fixes (#61-#67) + research paper planning / CARE ablation session + GMM PCA pre-reduction fix (Farm C generality) + OMR in-sample-bias/premature-clip fix + targeted Farm C re-validation + self-distrust gate magnitude-saturation fix + paper draft (Markdown) + detector-enable ablation wiring fix + fusion auto-tuning wiring gap discovered + paper System Architecture section + full Farm C 58-event re-validation (omr_z over-sensitivity found) + OMR kurt/skew exclusion fix (#72) — Farm A exact-match, Farm C mixed result (precision/false-alarms up, recall down 2 events) + Farm B first full result (recall=0.333, worst of 3 farms) + TEP benchmark candidate feasibility confirmed + empty-rule_fired gap root-caused (two mechanisms, not yet fixed) + contamination-filter fix for rate/per-head threshold REJECTED (broke ACM's own false-alarm-resistance tests; cleanly reverted, zero net code change) + empty-rule_fired diagnosis CORRECTED (prior "two mechanisms / never crosses threshold" premise proven WRONG by multi-angle measurement: fused_max is above alert_z for 6/8 misses; fused score does NOT separate 6/8 misses from normal Farm C operation by any statistic; the 8 misses are 4 distinct situations — sub-cadence, availability-domain, genuinely-indistinguishable, separable-but-rule-shape — most NOT fixable at the alarm-rule layer; Farm C recall is bounded by event detectability mix, not pipeline quality) + self-distrust gate SATURATION_FRAC_FLOOR hardcoded-magic-number regression found and fixed (was a bare 0.2 constant eyeballed against 4 CARE events, violating the file's own "calculated from asset's own history" principle — replaced with a per-asset calculated floor; zero KPI regression on Farm A/C)

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
27. [Per-Asset Scoring & SIM→ACM Flow (2026-06-16)](#per-asset-scoring--simacm-flow-2026-06-16)
28. [Real-Time Log Streaming & Output Panel (2026-06-16)](#real-time-log-streaming--output-panel-2026-06-16)
29. [ML Pipeline Diagnostics (2026-06-17)](#ml-pipeline-diagnostics-2026-06-17)
30. [Research Paper Planning & CARE Ablation Experiments (2026-06-17)](#research-paper-planning--care-ablation-experiments-2026-06-17)
31. [Cross-Dataset Generality Testing (2026-06-17)](#cross-dataset-generality-testing-2026-06-17--skab-rejected-rule-established)
32. [GMM RobustScaler IQR-collapse fix (2026-06-17)](#gmm-robustscaler-iqr-collapse-fix--feature-z-clip-before-pca-2026-06-17)
33. [OMR in-sample-bias + premature-clip fix (2026-06-17)](#omr-in-sample-bias--premature-clip-fix--out-of-sample-recalibration-2026-06-17)
34. [Farm C targeted re-validation after the OMR fix (2026-06-17)](#farm-c-targeted-re-validation-after-the-omr-fix-2026-06-17)
35. [Self-distrust gate magnitude-saturation fix (2026-06-17)](#self-distrust-gate-magnitude-saturation-fix-2026-06-17)
36. [Paper draft + detector-enable ablation wiring fix + fusion auto-tuning wiring gap (2026-06-18)](#paper-draft--detector-enable-ablation-wiring-fix--fusion-auto-tuning-wiring-gap-2026-06-18)
37. [Farm C full 58-event re-validation after the OMR + self-distrust saturation fixes (2026-06-18)](#farm-c-full-58-event-re-validation-after-the-omr--self-distrust-saturation-fixes-2026-06-18)
38. [OMR kurt/skew exclusion fix (2026-06-18)](#omr-kurtskew-exclusion-fix--farm-a-exact-match-farm-c-mixed-result-2026-06-18)
39. [CARE Farm B — first full result (2026-06-18)](#care-farm-b--first-full-result-2026-06-18)
40. [New benchmark dataset research — TEP feasibility (2026-06-18)](#new-benchmark-dataset-research--tennessee-eastman-process-feasibility-confirmed-2026-06-18)
41. [Empty-rule_fired gap (two mechanisms) — SUPERSEDED (2026-06-18)](#empty-rule_fired-gap--root-caused-two-distinct-mechanisms-found-not-yet-fixed-open-decision-2026-06-18)
42. [Contamination-filter fix attempt — rejected (2026-06-18)](#contamination-filter-fix-attempt-for-the-empty-rule_fired-gap--rejected-2026-06-18)
43. [Empty-rule_fired gap — CORRECTED diagnosis (2026-06-18)](#empty-rule_fired-gap--corrected-diagnosis-the-premise-was-wrong-2026-06-18) ← **current correct understanding**
44. [Self-distrust gate SATURATION_FRAC_FLOOR magic-number regression — found and fixed (2026-06-19)](#self-distrust-gate-saturation_frac_floor-magic-number-regression--found-and-fixed-2026-06-19)
45. [Known Issues (Track as GitHub Issues)](#known-issues-track-as-github-issues)
46. [Standing Rule: Flag Architecture-Violating Suggestions](#standing-rule-flag-architecture-violating-suggestions-dont-suppress-them) ← **Read before giving any suggestion**
47. [User Working Style](#user-working-style)

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
> *Added: 2026-06-14 · Last updated: 2026-06-18*

- Zenodo URL: `https://zenodo.org/records/15846963/files/CARE_To_Compare.zip?download=1`
- Farm A: 22 events × ~36 MB (~800 MB total), 86 sensor features per event, CSV per event
- Farm B: **15 events (6 anomaly / 9 normal)**, 257 features, ~85-100 MB per event (~1.3 GB total)
  (corrected 2026-06-18 — prior "37 events" was wrong, never verified against actual `event_info.csv`;
  confirmed directly by downloading via `scripts/download_care_benchmark.py --dest care_data --farms B`
  and reading `care_data/Wind Farm B/event_info.csv`, which has exactly 15 rows)
- Farm C: 58 events (31 normal / 27 anomaly), 957 features
  (corrected 2026-06-17 — prior "36 events" was wrong, never verified against actual `event_info.csv`)
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
- As of 2026-06-16: all series always visible (detector toggle buttons removed from HTML). Previously series 3-8 defaulted to `show: false`.

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
38. *(2026-06-16)* **PowerShell `"$var.ext"` string interpolation parses `.ext` as member access, not a file extension** — `"$PID.out"` and `"$PID.err"` both evaluate `$PID.out` and `$PID.err` as property access on the `$PID` integer object. Since integers have no `.out` or `.err` property, both return null, making both strings **identical** — which then causes `Start-Process` to throw "RedirectStandardOutput and RedirectStandardError are same". Fix: use `Join-Path $env:TEMP ("prefix_" + $PID + ".out")` or `"prefix_$($PID).out"` to force variable-only expansion. Even better: drop `-RedirectStandard*` entirely when you don't need the output — with `-WindowStyle Hidden` the subprocess output goes to the hidden window's buffer.
39. *(2026-06-16)* **Test all PowerShell before committing** — PowerShell has strict constraints that differ from bash. Key rules: (a) stdout/stderr must always go to separate files in `Start-Process`; (b) `-NoNewline` and `-ForegroundColor` cannot be combined with newline tricks on the same `Write-Host` call — split them; (c) backtick line continuation `` ` `` must be the very last character on the line with nothing after, not even a space; (d) `$LASTEXITCODE` resets after every cmdlet, not just external programs — capture it immediately; (e) `Select-Object -Last 1` inside a redirected scriptblock loses exit codes — never pipe inside a Step/Warn scriptblock.
40. *(2026-06-17)* **Never describe OMR as "Orthogonal Moment Regression" or "per-sensor PCA"** — it's "Overall Model Residual": one multivariate model (PLS/Linear/PCA, auto-selected by data shape) reconstructs each sensor from the others; the score is the mean of the top-3 largest per-feature scaled residuals. Read `core/omr.py` before describing OMR in any doc or paper material — a prior planning draft got this wrong and it propagated into `docs/ml-book.html` Chapter 4 and `docs/architecture.md` until corrected this session.
41. *(2026-06-17)* **"No GPU required" is not, and has never been, a paper/product claim** — it was the user evaluating (and rejecting) a GPU-acceleration path for the pipeline. Do not infer marketing claims from infrastructure decisions mentioned in passing.
42. *(2026-06-17)* **Running N benchmark processes in parallel, each with its own `--workers` pool, multiplies total worker count** — 5 background `care_benchmark.py` runs × `--workers 4` = 20 processes on a 15GB container caused `BrokenProcessPool` from OOM (`free -h` showed 604MB available). Fix: `pkill -f care_benchmark.py`, then run sequentially (one `&&`-chained command) with `--workers 2` each. When running multiple independent benchmark/ablation configs, prefer sequential execution with a small worker count over parallel launches unless you've confirmed available memory.
43. *(2026-06-17)* **`scripts/download_care_dataset.py` output is NOT compatible with `scripts/care_benchmark.py`** — the former flattens to `care_farmA_40.csv` with no `event_info.csv` (built for the Simulate tab's flat file list); the latter requires `<farm_dir>/event_info.csv` + `<farm_dir>/datasets/{event_id}.csv`. Use the new `scripts/download_care_benchmark.py` for benchmark/ablation work — it preserves the Zenodo zip's original directory structure. Both scripts are intentionally kept (different consumers), not a duplicate to clean up.
44. *(2026-06-17)* **Unconstrained BLAS threads + `ProcessPoolExecutor` fork = silent permanent deadlock, not a slowdown.** A Farm C benchmark run (`--workers 2`) sat for 78 minutes with the main process and both workers parked in `futex_do_wait` at ~0% CPU, log frozen right after a `PCA Fit start` line. Root cause: no `OMP_NUM_THREADS`/`OPENBLAS_NUM_THREADS`/`MKL_NUM_THREADS` were set anywhere in the codebase, so each worker's OpenBLAS spun up 16 threads on a 4-core box (`ps -o pid,stat,wchan` showed `futex_do_wait`, `cat /proc/<pid>/status` showed `Threads: 16`). Forking a `ProcessPoolExecutor` worker while OpenBLAS holds an internal thread-pool lock in the parent can permanently deadlock the child — this is a known numpy/OpenBLAS-after-fork failure mode, not contention/slowness (true contention still burns CPU; a deadlock burns none). **Diagnostic signature to recognize this again:** process ELAPSED time large but TIME (cumulative CPU) tiny, `STAT`/`wchan` showing sleeping on a futex, log file mtime frozen far in the past. Fix applied: `os.environ.setdefault("OMP_NUM_THREADS", "1")` (+ `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`) inserted as the first import-time statement (before `numpy`/`pandas` import, before `ProcessPoolExecutor` is ever constructed) in all 6 scripts that use `ProcessPoolExecutor`: `acm_service.py` (production), `care_benchmark.py`, `smd_benchmark.py`, `skab_benchmark.py`, `acm_run.py`, `robustness_matrix.py`. Verified fix with a single-event rerun (workers=1): completed in 173.5s, no hang. This also benefits production — `acm_service.py`'s scoring pool was equally exposed.

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

## Git & GitHub Workflow
> *Added: 2026-06-14 · Last updated: 2026-06-17*

### MANDATORY: Issue-First Rule
**Every piece of work — bug fix, feature, refactor, infra — MUST have a GitHub issue before any code is written.**

Steps for any new task:
1. `gh issue create --title "..." --label "..." --milestone "..."` → note the issue number
2. Work on the fix/feature, referencing the issue in commits: `Fix #54 — debounce WS reconnect`
3. `gh issue close <N> --comment "Fixed in commit <sha>"` on completion
4. If the fix also belongs in a release, tag + `gh release create` after merge

**Never commit without a linked issue unless it's a docs-only or trivial whitespace change.**

### Labels (use these, not ad-hoc)
| Label | Colour | When to use |
|---|---|---|
| `bug` | red `#d73a4a` | Something is broken or produces wrong output |
| `enhancement` | cyan `#a2eeef` | New capability or improvement to existing feature |
| `performance` | orange `#FFA500` | Speed, memory, throughput |
| `ux` | pink `#E8A0BF` | UI polish, layout, usability |
| `infra` | purple `#5319E7` | CI, setup scripts, deployment |
| `refactor` | light blue `#BFD4F2` | Code cleanup, no behaviour change |
| `test` | green `#C2E0C6` | Test coverage additions |
| `ml` | blue `#1D76DB` | ML pipeline, detectors, alarm rules |
| `data` | teal `#006B75` | Data ingestion, feeds, source kinds |
| `security` | dark red `#B60205` | Security vulnerabilities or hardening |
| `documentation` | blue `#0075ca` | Docs, CLAUDE.md, README |

### Milestones & Versioning
Current milestones:
- **v0.1 — Core Scoring** (closed) — baseline ML pipeline, Fleet/Engineer/Admin UI
- **v0.2 — Simulator Integration** (closed) — SIM tab, SIM→ACM flow, per-asset scoring
- **v0.3 — Real-time Logs & UX Polish** (open, due 2026-06-30) — WebSocket logs, output panel, CI
- **v0.4 — CI/CD & Issue Workflow** (open, due 2026-07-15) — branch protection, README badge

When opening an issue, always assign it to the most appropriate open milestone. When closing a milestone:
```bash
gh api repos/bhadkamkar9snehil/ACM/milestones/<N> -X PATCH -f state=closed
gh release create v0.X.0-acm --title "v0.X — Title" --notes "..."
```

### Releases & Tags
Tag format: `v<major>.<minor>.<patch>-acm` (e.g. `v0.3.0-acm`)
- Patch bump (`v0.3.1-acm`): bug fixes only within a milestone
- Minor bump (`v0.4.0-acm`): milestone completed
- Major bump (`v1.0.0-acm`): production-ready, full feature set

```bash
git tag -a v0.X.0-acm <commit-sha> -m "Short description"
git push origin v0.X.0-acm
gh release create v0.X.0-acm --title "v0.X — Title" --notes "..."
```

### GitHub Actions CI
Workflow: `.github/workflows/ci.yml`
- **Fast tests** (`-m "not slow"`): runs on every push + every PR
- **Slow tests** (`-m slow`): runs only on push to `main`
- Public repo → unlimited free minutes

Check CI status: `gh run list` or `gh run watch`

### Useful gh CLI Commands
```bash
gh issue list --state open                        # see all open issues
gh issue create --title "" --label "" --milestone ""
gh issue close <N> --comment "Fixed in <sha>"
gh issue edit <N> --milestone "v0.4 — ..."        # reassign milestone
gh pr create --title "" --body ""                 # open a PR
gh run list                                        # CI run history
gh run watch                                       # watch active CI run
gh release list                                    # all releases
gh browse                                          # open repo in browser
```

### Commit History (sessions)
- Session 013M57Jr3CpacwDMxVebD5r6 — pushed directly to `main`
- Session `claude/upbeat-hopper-m39epw` — merged to main
- Session `claude/epic-archimedes-7dkrwf` — merged to main
- Session 01Dkd7AbjS8Sd5ChfYiNa1yR: branch `claude/focused-albattani-t9876j` → merged to `main`
- Session 01UuCboiW9MAKb9AKYYoVt1J (2026-06-16): per-asset scoring, SIM→ACM flow, perf sprints
- 2026-06-16 afternoon: WebSocket logs, output panel redesign, CI/issue workflow setup
- 2026-06-17: ML pipeline bug fixes (#61-#67) — `rules_diagnostic`, `calibration_json`, `data_quality_json`
- Branch `claude/research-paper-planning-ests5l` (2026-06-17): CARE ablation mechanism (`--override` flag,
  configurable `distrust_coverage`), `scripts/download_care_benchmark.py`, corrected OMR docs → merged to `main`
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

## Real-Time Log Streaming & Output Panel (2026-06-16)
> *Added: 2026-06-16 afternoon user sprint*

### Architecture

Real-time log delivery has two layers:

```
Parent process stdout/stderr
  → LineLogBuffer (wraps sys.stdout / sys.stderr)
      → writes to shared_lines deque (in-process)
      → sends UDP datagram to UDPLogServer (for child process workers)

Child scoring workers (ProcessPoolExecutor)
  → LineLogBuffer in worker subprocess
      → sends UDP datagrams to ACM_LOG_PORT (env var set by parent)

UDPLogServer (daemon thread in parent)
  → receives datagrams from workers
  → appends to shared_lines deque
  → broadcasts to all WebSocket clients via asyncio.run_coroutine_threadsafe()
```

### New API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/service/logs` | GET | Poll last N lines; `?limit=500&after=<id>` for incremental fetch |
| `/api/service/logs/ws` | WebSocket | Push new log lines in real-time to connected browser clients |
| `/api/service/logs/export` | POST | Body: list of log dicts → returns `acm_logs.xlsx` download |

### Key Classes (in `acm_service.py`)

**`UDPLogServer`** (starts in `lifespan`):
- Binds to random UDP port, sets `ACM_LOG_PORT` env var
- Daemon thread calls `sock.recvfrom(65535)` in a loop
- On each message: appends to `shared_lines`, broadcasts via `asyncio.run_coroutine_threadsafe(manager.broadcast(log_item), main_loop)`
- Port env var is the mechanism by which child processes know where to send logs

**`LineLogBuffer`** (replaces `sys.stdout` and `sys.stderr` at module load):
- Accumulates chars until `\n`, then strips ANSI escape codes and dispatches
- In parent process: writes directly to `shared_lines`
- In worker subprocess: sends UDP datagram to `ACM_LOG_PORT`

**`ConnectionManager`**: holds `list[WebSocket]`, broadcasts JSON `{id, text}` to all

### Frontend (app.js)

**WebSocket connection** (`connectWS()`):
- `ws = new WebSocket(proto + '//' + location.host + '/api/service/logs/ws')`
- On message: calls `parseBackendLogLine(text)` to extract ts/level/stage from structured log lines, pushes to `outputLines`, calls `renderOutputLog()`
- Reconnects with exponential backoff on close/error

**`parseBackendLogLine(text)`**:
- Strips ANSI codes, matches log patterns like `[INFO] stage: message` or `HH:MM:SS message`
- Returns `{ts, text, level}` for structured display in the table

**`loadInitialLogs()`**: calls `GET /api/service/logs` on startup to backfill logs from before WebSocket was opened

### Output Panel UI

**New controls** (index.html `#output-panel`):
- `#sel-output-source` — All Sources / Simulator / ACM (replaces old tab buttons)
- `#sel-output-level` — All Levels / DEBUG / INFO / WARN / ERROR
- `#sel-output-time` — All Time / Last 1m / Last 5m / Last 15m / Last 1h / Last 24h
- `#btn-output-export` — triggers POST to `/api/service/logs/export`, downloads `.xlsx`
- `#output-resizer` — drag handle at top of panel for vertical resize

**Resizable panel** (`initOutputPanel`):
- `mousedown` on `#output-resizer` → tracks drag → sets `panel.style.height`
- Min height ~80px, max height = bottom of tab rail (clamped so tabs stay visible)
- Dispatches `window.resize` on drag (triggers uPlot and canvas redraws)
- Persists height in `localStorage` key `acm_log_panel_height`

### UI Removals (2026-06-16)

- **Detector toggle buttons** removed from Engineer tab — the `.det-toggles` div and all 6 `<button class="det-toggle">` buttons are gone from `index.html`. Detectors are always shown in the heatmap; individual series toggling via buttons was removed.
- **Admin tab Run Log card** removed (`adm-log` div, `#adm-runlog` pre, `#adm-log-level` select). The output panel now serves this purpose.
- **Advanced Mode layout change**: in Advanced mode, Engineer tab cards stack vertically (one below another) instead of the 2-column grid.

### Important: det-toggle references in app.js

Since the `.det-toggle` buttons no longer exist in HTML, any code in `refreshEngineer()` that did `document.querySelectorAll('.det-toggle')` will silently no-op (empty NodeList). This is safe — the uPlot series are still defined, just always visible. Do NOT re-add the toggle buttons without also re-adding the JS wiring.

---

## ML Pipeline Diagnostics (2026-06-17)
> *Added: 2026-06-17 — fixes for issues #61–#67 (commit ea35fd4)*

### AlarmDecision.rules_diagnostic (fixes #61)
`AlarmDecision` now carries a `rules_diagnostic: Dict` populated by `apply_alarm_rules()`:
```python
{
  "rate": {"active": bool, "train_n": int, "thr": float},  # thr only when active
  "per_head": {
    "ar1_z": {"active": bool, "train_n": int, "thr": float},
    ...
  }
}
```
When a rule is disarmed (train_n < 500), `pipeline.py` logs a WARN via `_log()`. This appears in the output panel as `[rules] rate rule DISARMED: train_n=300 < 500`.

### PipelineResult new fields (fixes #65, #66)
`PipelineResult` has two new optional string fields:
- `calibration_json`: `{"weights_used": {...}, "auto_tuned": bool, "tuning": {...}}` from `fusion.weights_used`
- `data_quality_json`: `{"train_rows": N, "score_rows": N, "channels": N, "nan_density": 0.xxxx, "duplicate_ts": N, "cadence_s": N}`

### runs table new columns (fixes #64, #65, #66)
`acm_store.py` DDL adds to the `runs` table:
- `rules_diagnostic_json TEXT` — serialised `AlarmDecision.rules_diagnostic`
- `calibration_json TEXT` — detector weights + auto-tuning info
- `data_quality_json TEXT` — NaN density, duplicates, channel count, cadence

`_migrate_sqlite()` auto-adds these columns to existing DBs on startup — no manual migration needed.

### fuse.py fixes
- **#63** (`_filter_iterative_mad`): guard added at function entry — if `len(x) == 0`, returns immediately via `_apply_exclusion_with_guards` with empty arrays. Previously `np.median([])` crashed on first iteration.
- **#67** (weight drift clamping): `if old_weight > 0.01` condition removed; denominator is now `max(old_weight, 0.01)` so detectors bootstrapping from zero are clamped the same as established ones.

### acm_feed.py corrupt row logging (fixes #62)
MQTT/OPC-UA rows that fail JSON parsing are now counted and emitted as `warnings.warn("acm_feed: N/M rows dropped — corrupt JSON in 'table_name'")` instead of silent `pass`.

---

## Research Paper Planning & CARE Ablation Experiments (2026-06-17)
> *Added: 2026-06-17*

A research-paper planning session (target: arXiv preprint / workshop, ML-pipeline-design angle,
CARE-to-Compare leaderboard as baseline) produced a corrected understanding of OMR, a reusable
ablation mechanism, and real ablation results on CARE Farm A. This section is the durable record;
the working paper plan itself lives outside the repo at `~/.claude/plans/` and does not need to be
committed.

### OMR is "Overall Model Residual" — NOT "Orthogonal Moment Regression"

A prior planning draft misidentified OMR. The correct definition, read directly from `core/omr.py`:

- OMR fits **one multivariate model** (not one model per sensor) on the healthy training baseline
  to learn inter-sensor correlations. Model type is auto-selected by data shape
  (`OMRDetector._select_model_type`): **PCA** if `n_features > n_samples`, **Linear/Ridge** if
  `n_samples > 1000 and n_features < 20`, otherwise **PLS** (default — best for correlated sensor
  data at moderate sample sizes).
- At inference, each sensor is reconstructed from the others via the fitted model, producing a
  per-feature residual vector.
- The anomaly score is **the mean of the top-3 largest per-feature scaled residuals**
  (`np.partition(scaled, -k, axis=1)[:, -k:].mean()`, k=min(3, n_features)) — deliberately NOT a
  row-L2 norm and NOT a plain max:
  - **L2 norm** dilutes a single faulty channel by `sqrt(n_features)` — invisible on Farm A's 86
    sensors.
  - **Max** is an extreme-value statistic whose *healthy* tail grows with feature count, crushing
    calibration contrast on wide sensor sets.
  - **Top-3** requires three simultaneously elevated features; noise rarely produces that, but one
    physically faulty channel elevates ~11 of its engineered derivatives (median, MAD, mean, std,
    slope, skew, kurtosis, spectral bands), so real faults reliably clear the bar.
- Per-feature squared residuals (a separate, unrelated-to-scoring computation) feed the "culprit
  sensor" attribution shown in the UI and `core/pipeline.py`'s `culprits` list — this is the part
  that legitimately resembles "one number per sensor," but it is attribution, not the OMR score
  itself.
- `docs/ml-book.html` Chapter 4 and `docs/architecture.md` previously described OMR as "fits a
  model per sensor" / "per-sensor PCA" — both corrected in this session (see below).

### "No GPU required" was never a paper claim

A prior planning draft included "no GPU required" as a contribution. This was a misunderstanding —
the user was evaluating (and decided against) GPU-accelerating the pipeline; it has nothing to do
with the paper's claims. Do not reintroduce any GPU-related claim into paper materials.

### Ablation mechanism: `--override` flag on `care_benchmark.py`

`score_asset(cfg=...)` already accepted an optional config override — no pipeline refactor needed.
Added a CLI surface for it:

```bash
python scripts/care_benchmark.py --data-dir "care_data/Wind Farm A" --out results/full/ --workers 2
python scripts/care_benchmark.py --data-dir "care_data/Wind Farm A" --out results/no_contam/ --workers 2 \
  --override '{"thresholds": {"contamination_filter": {"enabled": false}}}'
```

`--override` JSON-deep-merges onto `dict(ML_DEFAULTS)` (`_deep_merge()` in `care_benchmark.py`) and
forces `--force` (cached/reused scores from a different config are never valid). `run_event()` and
the `_worker()` ProcessPoolExecutor entry point both thread `cfg` through to `score_asset()`.

**New: `distrust_coverage` is now configurable.** It was a hardcoded module constant
(`DISTRUST_COVERAGE = 0.5` in `core/alarm_rules.py`) with no way to disable the self-distrust gate
for ablation. `apply_alarm_rules()` gained a `distrust_coverage: float = DISTRUST_COVERAGE`
parameter; `core/pipeline.py` passes `cfg.get("alarm_rules", {}).get("distrust_coverage", 0.5)`.
Setting it to an unreachable value (e.g. `2.0`) via `--override` disables the gate without code
changes:
```bash
--override '{"alarm_rules": {"distrust_coverage": 2.0}}'
```

### New script: `scripts/download_care_benchmark.py`

The existing `scripts/download_care_dataset.py` flattens files into `care_farmA_40.csv` naming
with no `event_info.csv` — built for the Simulate tab's flat file list, NOT for
`care_benchmark.py`, which requires `<farm_dir>/event_info.csv` + `<farm_dir>/datasets/{event_id}.csv`.
`download_care_benchmark.py` preserves that directory structure:
```bash
python scripts/download_care_benchmark.py --dest care_data --farms A
python scripts/care_benchmark.py --data-dir "care_data/Wind Farm A" --out results/A/ --workers 4
```
Both scripts coexist — they serve different consumers. `care_data/` and `results/` are gitignored
(downloaded dataset + benchmark output, not source).

### Ablation results on CARE Farm A (22 events: 12 anomaly, 10 normal)

Five configs run: `full` (all defaults), `no_contam` (contamination filter disabled), `no_distrust`
(self-distrust gate disabled), `equal_weights` (fusion auto-tune off, all 6 weights = 1/6),
`no_omr` (OMR detector disabled). **Binary KPI is identical across all five**: recall=1.0,
precision=0.857, F1=0.923, KPI PASS — Farm A's 22-event set is too small/easy for these components
to change detection outcomes. The real signal is in score magnitude, calibration, and alarm
quality, where every component justified its presence:

- **Self-distrust gate** — on event 40, disabling it raised `alarm_frac` from 0.402 to 0.897 (a
  55% alarm-burden reduction when the gate is ON) by letting the per-head rate rule fire across the
  whole window instead of being discarded as a broken baseline. More tellingly: WITHOUT the gate,
  the reported lead time for event 40 looks far better (first alarm 60.7h after event_start vs.
  468.8h with the gate ON) — but that earlier "detection" is the broken-baseline symptom firing
  from t=0, not genuine onset detection. The gate trades an illusory early detection for an honest
  late one. Gate had zero effect on any normal event's false-alarm outcome on Farm A — its
  measurable effect here was alarm quality, not binary classification.
- **Contamination filter** — removing it lowered the self-tuned `alert_z` threshold by ~7% on
  anomaly events (4.293→3.977) and ~6% on normal events (3.964→3.718), and raised the false-alarm
  fraction on normal operation from 3.82% to 4.17%. Confirms the mechanism: a dirty calibration
  holdout inflates apparent "normal" spread, which lowers (not raises) the self-tuned threshold —
  the opposite of conservative.
- **OMR** — removing it raised mean fused_max by ~+0.5z on BOTH anomaly (5.548→6.070) and normal
  (5.275→5.779) events, with the self-tuned alert_z threshold rising in lockstep (so the binary KPI
  doesn't move). OMR's measured Farm-A contribution is fusion-scale stabilization/discounting, not
  raw separability — it compresses the whole ensemble's dynamic range rather than uniquely
  flagging events the other 5 detectors miss.
- **Equal vs. auto-tuned weights** — auto-tuning produced a modest systematic uplift in both fused
  score and self-tuned threshold (~4%) but no consistent win/loss pattern in detection outcomes on
  this event set. Honest finding: auto-tuning's value on Farm A is calibration sharpness, not
  recall/precision, and that should not be oversold in the paper.
- Runtime was flat across all 5 configs (45.5–47.2s mean per event) — none of these toggles
  meaningfully change compute cost.

**Framing for the paper:** Farm A alone (22 events) cannot demonstrate these components changing
binary detection outcomes — say so plainly rather than overclaiming. Farms B/C (more
events/sensors) are needed to test whether any ablation moves recall/F1.

### Farm C — corrected scale (58 events, not 36)

CLAUDE.md previously said Farm C has "36 events, 957 features." Corrected after actually
downloading the metadata: **58 events** (31 normal, 27 anomaly), 957 sensor columns, ~280-340MB
per event CSV (~16-17GB total for the farm). Farm B remains unverified/untouched.

**Resource profile (measured directly, single event, single worker):** ~157s wall-clock, ~4.5GB
peak RSS per event. For a full-farm `care_benchmark.py` run, use `--workers 2` (2×4.5GB ≈ 9GB,
safe on this 15GB container) — do not raise `--workers` without re-checking `free -h` first (see
mistake #42).

---

## Cross-Dataset Generality Testing (2026-06-17 — SKAB rejected, rule established)
> *Added: 2026-06-17*

Tracked in GitHub issue #70. Goal: prove ACM generalizes beyond CARE-tuned wind-farm SCADA by
running the *same* `ML_DEFAULTS` (zero per-dataset hand-tuning) against other public, label-backed
anomaly-detection benchmarks.

### The ML Improvement Loop (standing methodology — apply to every dataset)
> *Added: 2026-06-17*

The point of multi-dataset testing is not to win each benchmark individually — it's to learn
where ACM's *general* ML pipeline can genuinely be improved, irrespective of domain. Every
dataset run follows this loop:

1. **Run** ACM on the dataset with the SAME `ML_DEFAULTS` used everywhere else — zero
   per-dataset tuning (per issue #70's non-goal).
2. **If a result suggests a real pipeline gap, document it first.** Write down what was
   observed and why it looks like a genuine general limitation rather than a dataset-protocol
   mismatch (see the SKAB rule below for how to tell the difference — a dataset whose own
   protocol conflicts with ACM's domain assumptions is a dataset-selection failure, not a
   finding to act on).
3. **Plan before touching code.** Think through the change's impact on the *general* pipeline:
   does it help broadly across domains, or does it just patch this one dataset? Could it
   degrade the validated Farm A / CARE baseline?
4. **Only once satisfied it's a genuine general improvement, implement it.**
5. **Re-validate Farm A/CARE after every change** — an improvement that breaks the validated
   baseline is not acceptable, no exceptions.
6. **Repeat across datasets.** This is a cumulative credibility-building process — keep adding
   benchmarks until there's enough multi-dataset evidence to credibly claim ACM generalizes,
   not a single pass/fail check.

### SKAB (Skoltech Anomaly Benchmark) — tried, rejected as a benchmark target

Cloned `https://github.com/waico/SKAB.git` to `external_benchmarks/SKAB/`, built
`scripts/skab_benchmark.py` matching its own published train/test convention exactly (first 400
rows of each of the 34 experiment files = train, remainder = score; metrics = F1/FAR/MAR pooled
across files, matching SKAB's own README leaderboard table). Result: **zero alarms on all 34
files** (`results/skab/summary.json`: tp=0, recall=0, F1=0).

**Root cause (confirmed, not a bug):** two SCADA-domain design constants in
`core/alarm_rules.py` are structurally incompatible with SKAB's protocol:
1. `PERSIST_FLOOR_S = 3600.0` (1h) — the sustained-rule persistence floor is *never adaptively
   capped* to the scored window length (unlike `rate_window`/`head_window`, which are). At SKAB's
   1Hz cadence this is a hard 3600-sample requirement; SKAB's anomalies last minutes, not hours.
   The code comment at L151 calls this "ACM's declared detection floor for DEVELOPING faults — is
   never weakened" — i.e. intentional.
2. Rate/per-head rules require `train_n >= 500` calibration samples to arm. SKAB's 400-row
   training convention yields only ~64 post-split calibration samples — never arms.

**The detectors themselves DO transfer**: fused z-scores on `valve1/0.csv` show real separation
(mean 2.77 on true-anomaly rows vs 1.13 on normal rows). It is specifically the alarm-rule layer's
SCADA-scale assumptions, not the detector ensemble, that don't fit SKAB.

**User's explicit decision on this finding (standing rule — apply to all future dataset
selection):**
- **Do not change ACM's alarm-rule thresholds to fit a short-history/short-anomaly-duration
  dataset.** ACM's intended deployment is industrial assets where sufficient history *will*
  accumulate over time — the 1h persistence floor and 500-sample arming threshold are correct
  design choices for that domain, not bugs to patch around.
- **A dataset whose own canonical protocol (400-row training, sub-15-minute anomalies) conflicts
  with that domain assumption is the wrong dataset for proving generality** — this is a dataset
  *selection* failure, not an ACM limitation to fix.
- Exception: if a genuinely general mechanism is found that resolves this *without degrading
  Farm A/CARE performance*, it's worth considering — but do not chase one benchmark's protocol
  with a special case.
- SKAB is dropped. Do not revisit it or re-litigate the persistence-floor/arming-threshold design
  for SKAB's sake. `external_benchmarks/SKAB/` and `scripts/skab_benchmark.py` are left in the repo
  as-is (harmless, not deleted) but are not part of the paper's generality evidence.
- When searching for replacement datasets, do it directly (WebSearch/WebFetch), not via a research
  subagent — the user wants the candidate-vetting done first-hand.
- **Generality criterion going forward:** the dataset must match ACM's actual target domain —
  industrial/SCADA-style assets with enough accumulated history for hour-to-day-scale fault
  development — not generic point-anomaly or short-transient benchmarks from unrelated domains.

### CARE Farm C — full 58-event results (2026-06-17)

Same `ML_DEFAULTS` as Farm A, zero per-dataset tuning, `--workers 2`. Result:
`recall=0.556, precision=0.625, F1=0.588, KPI FAIL` (need recall>=0.80, F1>=0.75) — a real
regression from Farm A's `recall=1.0, F1=0.923`. 15/27 anomaly events detected; 22/31 normal
events stayed clean (9 false alarms).

**Root cause is concentrated in one detector, not the ensemble or the alarm-rule design**:
`gmm_z` (the per-head GMM rule) appears in the `rule_fired` string of 35/58 events (60%) and
is specifically implicated in:
- **8 of 9 false alarms** on normal operation (`+heads:gmm_z` or `+heads:pca_spe_z,gmm_z`)
- **5 of 12 missed anomalies** via the self-distrust gate (`(distrusted:heads:gmm_z)` etc. —
  GMM fires from window start, gets correctly discarded as a broken-baseline symptom, but the
  anomaly that triggered it goes uncredited)

The other 7 missed anomalies have an empty `rule_fired` (fused score never crossed `alert_z_eff`
at all — a separate, not-yet-diagnosed gap).

**Working hypothesis (not yet validated, not yet acted on per the ML Improvement Loop above)**:
GMM density estimation degrades with dimensionality — Farm C's feature matrix is ~3300+ engineered
columns (957 raw sensors) vs. Farm A's ~600 (86 raw sensors). A diagonal-covariance GMM's
log-likelihood estimate gets noisier as dimensionality grows (curse of dimensionality), which
would produce exactly this signature: chronic low-grade false positives on normal data, and
from-the-start firing that looks like a broken baseline. This has NOT been investigated or fixed
yet — per the standing methodology, it needs to be documented (done, here), then a fix needs to be
planned with explicit attention to whether it helps generally (not just Farm C) and whether it
degrades the validated Farm A result, before any code changes are made.

### SMD — full 28-machine results (2026-06-17)

Same `ML_DEFAULTS`, `--workers 3`. Pointwise: `precision=0.066, recall=0.633, F1=0.119`.
Point-adjusted (literature convention): `precision=0.074, recall=0.714, F1=0.133`. Segment
recall: `166/327 (0.508)` anomaly segments caught at least partially.

**Different failure signature than Farm C**: the dominant `rule_fired` string
(`sustained+rate(distrusted:heads:ar1_z,pca_spe_z,pca_t2_z,iforest_z,gmm_z)`, 7/28 machines) shows
nearly ALL detectors landing in the distrusted-heads list together, not one detector dominating
as on Farm C. Mean false-positive rate on normal-labelled points is high (~39%: mean fp=9466 vs
mean tn=14783 per machine) — this looks more like a threshold/calibration sensitivity issue than
a single-detector defect. Not yet investigated further.

**Framing for the paper**: both results are honest negative/mixed findings, not failures to hide.
Farm A was the validation baseline; Farm C and SMD are exactly the generality stress-tests that
were supposed to either confirm or complicate that result, and they complicate it usefully — Farm
C points at a specific, fixable-looking detector issue; SMD points at a broader calibration
question. Per the ML Improvement Loop, the next step is investigation and planning, not an
immediate code change.

### GMM PCA pre-reduction fix — implemented and validated (2026-06-17)

Per the ML Improvement Loop, the Farm C GMM root cause above was investigated, planned, implemented,
and re-validated against Farm A before being considered done.

**Root cause, confirmed with measured numbers** (not just hypothesized): Farm A and Farm C have
nearly identical training row counts post-subsample (~10,000, from `models.max_train_samples`)
but very different engineered feature counts — Farm A 616, Farm C 2,629 (4.3x more, driven by
957 raw sensors vs 86). `GMMDetector` uses `covariance_type="diag"`, which estimates 2 parameters
(mean, variance) per feature per component. At k=3 components this gives Farm A ~3.25
samples/feature/component vs Farm C's ~0.76 (less than 1) — severe parameter starvation that
produces unreliable likelihoods, confirmed as the dominant cause of Farm C's false alarms and
self-distrust-gated missed detections (see Farm C analysis above).

**Fix**: `GMMDetector.fit()` (`core/outliers.py`) now reduces the scaled feature matrix to a
**whitened PCA subspace** before fitting the mixture model, sized adaptively from training sample
count and the GMM's k budget (`d_budget = n_samples / (min_samples_per_param * k_for_budget * 2)`),
capped by a hard ceiling (`max_pca_components`). This decouples GMM reliability from raw
sensor/feature count entirely — a general fix, not a Farm-C-specific patch. Two independent
justifications: (1) caps the parameter count regardless of how many engineered features exist;
(2) PCA decorrelation makes the diagonal-covariance independence assumption more valid everywhere,
not just on wide-sensor assets (precedented: Tipping & Bishop 1999, Mixtures of Probabilistic PCA).
`score()` applies the same fitted PCA transform. New `ml_defaults.py` keys under `models.gmm`:
`max_pca_components: 25`, `min_samples_per_param: 10.0`.

**`whiten=True` is required, not optional** — discovered during validation, not anticipated in the
design. Unwhitened `PCA` leaves trailing low-variance components (decreasing eigenvalues by
construction); feeding those into a diag-covariance `GaussianMixture` caused outright fit failure
("ill-defined empirical covariance") on Farm A during the first validation pass. Whitening rescales
every component to unit variance before the GMM sees it, which is the standard, mathematically
correct pairing for "PCA + diagonal-covariance density model" and fixed the failure completely.

**Farm A re-validation (22 events) — improved, not just neutral:**
| Metric | Before | After |
|---|---|---|
| recall | 1.0 | 1.0 (unchanged, 12/12) |
| precision | 0.857 | 0.923 (false positives 2→1) |
| F1 | 0.923 | 0.960 |

**Farm C (58 events) — substantial improvement, KPI still FAIL:**
| Metric | Before | After |
|---|---|---|
| recall | 0.556 (15/27) | 0.593 (16/27) |
| precision | 0.625 | 0.842 |
| F1 | 0.588 | 0.696 |
| false alarms (of 31 normal) | 9 | 3 |
| KPI | FAIL | FAIL (need recall≥0.80, F1≥0.75) |

False alarms dropped 9→3 and the GMM-driven false-alarm/broken-baseline pattern that dominated the
prior failure signature (`+heads:gmm_z` in 8/9 false alarms, GMM in 5/12 distrust-gated misses) is
now almost entirely gone — only 1 of the 3 remaining false alarms involves `gmm_z`, and only 1 of
the 11 remaining missed anomalies is distrust-gated (`asset 23`, `iforest_z,gmm_z`). The fix did
exactly what it was designed to do.

**New dominant remaining gap on Farm C (not yet investigated)**: 10 of the 11 missed anomalies now
have an **empty `rule_fired`** — the fused score never crosses `alert_z_eff` at all. This is the
same "separate, not-yet-diagnosed gap" flagged in the original Farm C analysis above (previously
7 events, now the GMM fix has shifted several previously-distrusted events into this bucket
instead — e.g. event 67 went from `(distrusted:heads:gmm_z)` to empty). This is now Farm C's
primary blocker and the natural next ML Improvement Loop candidate, distinct from the GMM
dimensionality issue just fixed.

**Files changed**: `core/outliers.py` (`GMMDetector.__init__`/`.fit()`/`.score()`),
`core/ml_defaults.py` (`models.gmm.max_pca_components`, `models.gmm.min_samples_per_param`).
All 16 `test_ml.py` tests pass unchanged.

---

## GMM RobustScaler IQR-collapse fix — feature z-clip before PCA (2026-06-17)
> *Added: 2026-06-17 — follow-on to the GMM PCA pre-reduction fix above*

While investigating Farm C's remaining gap after the PCA pre-reduction fix, a deeper and more
general bug was found and fixed in the same `GMMDetector` scaling path.

### Root cause (confirmed with measured numbers, not hypothesized)

`GMMDetector.fit()`/`.score()` scale features with `RobustScaler` (median/IQR) before PCA — robust
to training data containing faults, per the existing `# ROBUST:` comments in `core/outliers.py`.
But for columns with heavy point-mass exactly at the median — common for engineered slope/skew-type
features during flat or non-operating regimes, or sparse/spiky features that are usually
zero — the 25th–75th percentile IQR can collapse to near-zero even though the column has genuine,
healthy spread. Confirmed directly with a diagnostic monkey-patch of `RobustScaler`/`PCA`
(`/tmp/pca_variance_check.py`, not committed):

- Farm A event 40, worst column: `scale_=4.31e-10`, but `raw_std=0.0107`, 17 distinct raw values.
- Farm C event 4, worst column: `scale_=3.27e-14`, but `raw_std=0.0394`, **1735** distinct raw
  values — proving this is not a degenerate/near-constant column, just one whose IQR happens to
  collapse.

Dividing by a near-zero IQR amplifies ordinary variation into z-magnitudes of 1e8–1e12+. Since PCA
selects components by variance, a handful of these exploded columns can swallow the entire
component budget with numerical noise instead of real inter-sensor structure — **even after** the
PCA pre-reduction fix above correctly capped the *component count*. Measured before the fix:
Farm A had `evr_first5=[1.0, 0, 0, 0, 0]` (PC1 = one exploded column, not real structure); Farm C
had **39 columns with variance >1e6** (max `1.449e24`), eating ~97% of the cumulative variance
across the first 5 PCs (`evr_first5=[0.8667, 0.0584, 0.0387, 0.0127, 0.0101]`). This explains why
Farm C's `gmm_z` calibration sanity (`frac≥3.0` on training data) was ~6x worse than Farm A's even
with the dimensionality fix already in place.

**Why "fall back to std when IQR is near-zero" is the wrong fix**: Farm A's worst column above is
mostly-zero with rare small spikes — its near-zero IQR correctly reflects that "normal" behavior is
tightly clustered at zero. A std-based fallback would under-penalize the legitimately rare-but-
meaningful spikes, defeating the purpose of choosing a robust (outlier-resistant) scaler in the
first place. The actual bug isn't that the scale is "wrong," it's that there's no bound on how
extreme the resulting z-magnitude becomes once divided by a near-zero IQR.

### Fix: clip, don't floor

`GMMDetector.fit()` and `.score()` now clip the RobustScaler-scaled matrix to a bounded per-feature
range (`±feature_z_clip`, default 8.0) immediately before PCA — identically in both methods, since
clipping is stateless and needs no fit/score-time bookkeeping:
```python
Xs = self.scaler.fit_transform(Xn).astype(np.float64, copy=False)   # fit()
np.clip(Xs, -feat_z_clip, feat_z_clip, out=Xs)
# ... same np.clip(Xs, ...) after self.scaler.transform(Xn) in score()
```
This is precedented by existing codebase conventions for bounding z-magnitude without suppressing
the underlying signal: AR1's `z_cap=8.0` (`models.ar1.z_cap`) and `ScoreCalibrator`'s `clip_z` +
hard ±10.0 clip in `core/fuse.py`. It preserves `RobustScaler`'s outlier-robust semantics for
well-behaved columns (values inside the clip range pass through untouched) while bounding
worst-case influence on PCA regardless of *why* a column's scale collapsed. New config key:
`models.gmm.feature_z_clip` (default 8.0) in `core/ml_defaults.py`.

### Validation

Diagnostic re-run after the fix (`n_cols_var_gt_1e6` is now **0** on both farms — was 39 on Farm C,
1 on Farm A):
| | Farm A event 40 | Farm C event 4 |
|---|---|---|
| `evr_first5` before | `[1.0, 0, 0, 0, 0]` | `[0.867, 0.058, 0.039, 0.013, 0.010]` |
| `evr_first5` after | `[0.132, 0.089, 0.052, 0.042, 0.035]` | `[0.107, 0.053, 0.052, 0.044, 0.036]` |
| `n_cols_var_gt_1e6` | 1 → 0 | 39 → 0 |
| `gmm_z` train `frac≥3.0` | (was ~6x worse on Farm C) | now 0.013 vs 0.011 — nearly identical |

Full Farm A re-validation (22 events, mandatory "no exceptions" re-check): **recall=1.0,
precision=0.923, F1=0.960 — identical to the pre-clip baseline, zero regression.** Full Farm C
58-event re-run was deferred (benchmark runtime); the per-event diagnostic and Farm A re-validation
were judged sufficient to ship the fix, given it only bounds an unbounded numerical pathology and
cannot make a previously-correct calibration worse. Re-run Farm C's full benchmark before citing
updated Farm C numbers in the paper.

**Files changed**: `core/outliers.py` (`GMMDetector.fit()`/`.score()` — `np.clip` calls before
PCA), `core/ml_defaults.py` (`models.gmm.feature_z_clip: 8.0`), `docs/ml-book.html` (GMM section —
added "Per-feature z-clip before PCA" subsection alongside the existing PCA pre-reduction
subsection).

---

## OMR in-sample-bias + premature-clip fix — out-of-sample recalibration (2026-06-17)
> *Added: 2026-06-17*

A direct investigation into Farm C's empty-`rule_fired` missed anomalies (a different gap than
the GMM one above) led to discovering OMR (`omr_z`) was structurally incapable of producing a
positive calibrated value on **either** farm — not just Farm C. Confirmed directly by reading
`res.scores['omr_z']` / `res.head_z_train['omr_z']` from `score_asset()` output with no
monkey-patching: `omr_z` was ≤0 almost everywhere on both the validated Farm A baseline and the
failing Farm C set.

**Root cause, two compounding bugs in `core/omr.py`:**
1. `OMRDetector.fit()` computed `feature_resid_med`/`feature_resid_scale` (and
   `train_residual_std`) from **in-sample** residuals — the same rows the model was just fit on.
   A model is optimized to minimize exactly those residuals, so in-sample residual scale is
   mechanically smaller than true/out-of-sample residual variance. Dividing later (genuinely
   out-of-sample) residuals by that understated scale inflated every raw z-score, including on
   healthy data.
2. A class constant `MAX_Z_SCORE = 10.0` clipped OMR's raw aggregate score BEFORE the shared
   `ScoreCalibrator` (`core/fuse.py`) ever saw it — the only one of the six detector heads
   (`ar1_raw`, `pca_spe_raw`, `pca_t2_raw`, `iforest_raw`, `gmm_raw`, `omr_raw`) that pre-clipped
   itself; every other head hands its raw score to the shared calibrator unclipped, and the
   calibrator's own self-tuned `clip_z` + a final hard ±10.0 clip in `fuse.py` is meant to be the
   sole place this bounding happens. Combined with bug #1, the inflated raw z saturated at exactly
   10.0 for the *majority* of even healthy training rows; `ScoreCalibrator` then centered its
   calibration at/near that saturated mode, so virtually every later calibrated `omr_z` came out
   ≤0 — the detector was contributing nothing on either farm, not just Farm C.

**Fix (`core/omr.py`):**
- Removed `MAX_Z_SCORE`/`self.max_z_score` entirely — `omr_raw` now reaches `ScoreCalibrator`
  unclipped, exactly like every other head.
- Added `OMRDetector.recalibrate_residual_scale(X_holdout)` — recomputes
  `feature_resid_med`/`feature_resid_scale`/`train_residual_std` from **out-of-sample** residuals,
  duplicating (not refactoring, to avoid disturbing `score()`'s explicit in-place memory
  optimizations — see its "Memory-optimized version v11.0.3" docstring) the same
  align/impute/scale/reconstruct logic `score()` uses. Falls back to keeping the in-sample
  estimates (never raises) if the holdout is smaller than `max(20, 2*n_features)` or columns don't
  align.
- `core/pipeline.py` calls `omr_det.recalibrate_residual_scale(calib_feat)` immediately after
  `orch.fit_all_detectors()` returns, reusing the pipeline's existing interleaved calibration
  holdout (`calib_feat` — the same out-of-sample block `ScoreCalibrator` itself uses downstream).
  Placed after `fit_all_detectors()` so it runs unconditionally regardless of whether OMR was
  freshly fit or restored from a cache — which also incidentally fixes a separate pre-existing gap
  where `OMRModel.to_dict()`/`from_dict()` never serialized `feature_resid_med`/`feature_resid_scale`
  at all (a cache-restored OMR model previously had no per-feature scale until first re-fit).

**Validation:** `tests/test_ml.py` 16/16 pass unchanged. Direct `score_asset()` checks confirm
`omr_z` is no longer pinned: Farm A event 40 score-side mean=4.21 (was ≤0, frac>0 now 0.74), Farm C
event 4 score-side mean=0.65 (frac>0 now 0.52). A clean Farm A event (3) shows score-side mean
≈ train-side mean (0.45 vs 0.46) — confirming the recalibrated z stays near baseline when an asset
genuinely matches its training distribution, not just trending positive everywhere.

**Full Farm A re-validation (22 events) — KPI still PASS, but precision/F1 regressed from the
most recent checkpoint, and this is expected, not a flaw:**
| Metric | Pre-OMR-fix checkpoint | After OMR fix |
|---|---|---|
| recall | 1.0 (12/12) | 1.0 (12/12, unchanged) |
| precision | 0.923 | 0.857 |
| F1 | 0.960 | 0.923 |
| false alarms (of 10 normal) | 1 (event 71, `sustained`) | 2 (adds event 17, `+heads:omr_z`) |

Event 17's score-window `omr_z` (mean 2.93, median 2.30, 43% of rows >3σ) is substantially elevated
relative to its own training baseline (mean 0.57, median 0.09, 7.8% >3σ) — a genuine,
previously-invisible signal, not noise from the new code: OMR was simply incapable of flagging
*anything* via the per-head rule before this fix (every calibrated value was ≤0), so this is the
first time OMR has ever been able to participate in that rule on Farm A. CARE labels event 17
"normal," so the benchmark counts this as a false positive — but un-breaking a detector that
previously contributed nothing is expected to surface signal exactly like this. This was not
chased further (e.g. by re-tuning the per-head rule's sensitivity to absorb event 17) because that
was explicitly out of scope for this fix.

**Files changed**: `core/omr.py` (`MAX_Z_SCORE` constant + `self.max_z_score` removed;
new `recalibrate_residual_scale()` method), `core/pipeline.py` (calls
`omr_det.recalibrate_residual_scale(calib_feat)` right after `fit_all_detectors()`).

---

## Farm C targeted re-validation after the OMR fix (2026-06-17)
> *Added: 2026-06-17*

After the OMR in-sample-bias fix above, Farm C's empty-`rule_fired` gap (documented in the GMM
PCA pre-reduction section: 10 of 11 missed anomalies had no rule fire at all, pre-OMR-fix) needed
re-checking. Rather than re-running the full 58-event farm (~75 min), only the 14 events known to
be problematic from the most recent full run (`results/farm_c_gmm_pca/`) were re-run: the 11
missed anomaly events (event_id 4, 9, 15, 35, 47, 55, 67, 70, 76, 78, 90) + the 3 false-alarm
normal events (54, 88, 94). `--force` was required since `try_reuse_event()` would otherwise
silently reuse pre-OMR-fix cached scores. Output: `results/farm_c_omr_fix/` (gitignored).

**Per-event outcome change (pre- vs. post-OMR-fix), all 14 events:**

| Event | Label | Before | After |
|---|---|---|---|
| 4 | anomaly | empty | empty (unchanged) |
| 9 | anomaly | empty | `(distrusted:heads:omr_z)` — still missed |
| 15 | anomaly | empty | empty (unchanged) |
| 35 | anomaly | empty | empty (unchanged) |
| 47 | anomaly | empty | `(distrusted:heads:omr_z)` — still missed |
| 55 | anomaly | empty | `+heads:omr_z` — **newly detected** |
| 67 | anomaly | empty | empty (unchanged) |
| 70 | anomaly | `(distrusted:heads:iforest_z,gmm_z)` | `(distrusted:heads:iforest_z,omr_z)` — still missed, `gmm_z`→`omr_z` in distrust set |
| 76 | anomaly | empty | empty (unchanged) |
| 78 | anomaly | empty | empty (unchanged) |
| 90 | anomaly | empty | `+rate` — **newly detected** |
| 54 | normal | `+heads:pca_spe_z` (false alarm) | `+heads:pca_spe_z` (still false alarm, unchanged) |
| 88 | normal | `sustained+rate` (false alarm) | `+rate` (still false alarm, unchanged) |
| 94 | normal | `+heads:ar1_z,gmm_z` (false alarm) | `+heads:ar1_z` (still false alarm, unchanged) |

**Net result on this 14-event subset:** anomaly recall 0/11 → 2/11. All 3 known false alarms
persist unchanged (none cleared, none newly introduced). `alert_z_eff` (self-tuned threshold) rose
on several events (e.g. event 35: 7.54→9.16, event 76: 8.25→8.91) — OMR now contributes real
variance to the fused score, pushing the auto-tuned threshold up in lockstep, the same dynamic
seen in the original Farm A ablation.

**New failure mode surfaced, not yet investigated or fixed:** on 3 of the 11 missed anomalies
(events 9, 47, 70), `omr_z` now appears in the self-distrust gate's discarded-heads list — OMR can
finally fire (it structurally could not before this fix) but on these events it fires from window
start and gets correctly discarded as a broken-baseline symptom. This is the same dynamic GMM
showed on Farm C before its own PCA pre-reduction fix. Per the standing ML Improvement Loop
methodology, this is documented here as an observation only — not yet planned or acted on. Do not
chase this without first checking whether a fix would risk regressing the now-clean GMM behavior
or the validated Farm A baseline.

**Read on the targeted-batch approach**: re-running only the previously-known-problematic events
(rather than the full farm) is a valid, faster way to check whether a fix changed an outcome
*for those specific events*, but it does NOT substitute for a full-farm KPI re-validation — false
alarms on previously-clean normal events, or new detections appearing only outside this 14-event
set, would not be visible. Re-run the full 58-event Farm C benchmark before citing updated
farm-wide recall/precision/F1 numbers in the paper.

**Files**: no code changes in this entry — diagnostic re-run only. `results/farm_c_omr_fix/`
(gitignored) holds the 14-event `results.csv`/`summary.json`.

---

## Self-distrust gate magnitude-saturation fix (2026-06-17)
> *Added: 2026-06-17 — fixes the exact bug surfaced in the "Farm C targeted re-validation" section above*

The previous section left a specific, named gap: on Farm C events 9, 47, and 70, OMR (and on
event 70, IForest) could finally fire after the OMR in-sample-bias fix, but the self-distrust gate
discarded all three as "broken baseline" symptoms — genuine anomalies suppressed as false
positives. This section documents the root-cause analysis, the corrected fix, and full validation.

### Why the gate's existing corroboration check was structurally wrong

`_broken_baseline()`'s score-side signature (coverage > 50% of the window AND first alarm within
5% of window start) is inherently ambiguous: it matches BOTH a broken/contaminated baseline AND a
genuine fault that was already fully developed when scoring began (CARE event labels sometimes
place `event_start` at the train/score boundary — zero observable lead time is possible by
construction). An earlier attempt at this session tried to resolve the ambiguity with a "Phase I"
check: would the rule's own training/calibration reference also have tripped the same derived
threshold (`calib_frac`, the training-side worst rolling-rate)? Measured directly against real
CARE events, this discriminated in the WRONG direction:

| Event | Label | `calib_frac` |
|---|---|---|
| Farm A 92 | confirmed false alarm (broken baseline) | 0.198 |
| Farm C 9 | confirmed genuine anomaly | 0.282 |
| Farm C 47 | confirmed genuine anomaly | 0.444 |
| Farm C 70 | confirmed genuine anomaly | 0.292 |

The false alarm had the LOWEST `calib_frac`, not the highest — the opposite of what the gate
needs to discard it correctly. It was also structurally tautological for the rate/per-head rules
specifically: their thresholds (`thr_h = base_h * SAFETY + 0.05`) are built with a 1.5x safety
margin above training's own observed maximum, so training can essentially never cross its own
derived threshold regardless of fit quality (`calib_frac` measured ~0.0000 in that framing). This
`calib_frac` approach was implemented, measured, and discarded entirely within this session — it
never shipped.

### The corrected discriminator: raw z-score saturation near the universal hard clip

`core/fuse.py`'s `ScoreCalibrator` clips every calibrated z-score twice: a per-run self-tuned
`clip_z` (observed values like 20.32, 33.46 — always well above 10 in practice), and then an
unconditional, dataset-independent hard clip to exactly **±10.0** (`np.clip(z, -10.0, 10.0)`,
appearing identically at multiple points in `core/fuse.py`). Because the self-tuned `clip_z` is
always looser than 10.0 in practice, the ±10.0 hard clip is the actual binding ceiling for every
detector on every asset — making "z >= 9.0" (90% of that ceiling) a principled, dataset-independent
threshold rather than a per-dataset magic number.

The intuition: a contaminated/mis-fit baseline drifts only moderately past its own derived
threshold (it takes the 1.5x safety margin just to fire at all) — it never saturates the shared
calibrated z-scale. A genuine catastrophic fault overwhelms the model's learned relationships
entirely, pegging the z-score near the universal ceiling. This is magnitude evidence, independent
of timing, so it doesn't inherit the "zero lead time is possible by construction" ambiguity that
sank the timing-only check.

Verified directly against the same 4 events (`/tmp/saturation_diag.py`, not committed) before
writing any fix code:

| Event | Label | `median_z_in_mask` | `frac_z>=9_in_mask` |
|---|---|---|---|
| Farm A 92 | false alarm | 4.17 | 0.051 |
| Farm C 9 | genuine anomaly | 8.03 | 0.465 |
| Farm C 47 | genuine anomaly | 10.00 | 1.000 |
| Farm C 70 | genuine anomaly | 10.00 | 1.000 |

A clean ~10x gap separates the false alarm from all three genuine faults, well clear of any
reasonable threshold.

### Fix (`core/alarm_rules.py`)

Two new module constants:
```python
SATURATION_Z = 9.0
SATURATION_FRAC_FLOOR = 0.2
```
`_broken_baseline()` signature changed from `(mask, eval_start, calib_frac)` to
`(mask, eval_start, z_values)` — it now takes the actual score-side z-score array (not a single
training-side scalar) and only discards when the timing signature is ambiguous AND the magnitude
evidence inside the masked region is also mild:
```python
def _broken_baseline(mask, eval_start, z_values):
    if mask.mean() <= distrust_coverage:
        return False
    first = int(np.argmax(mask))
    if first > eval_start + max(1, int(0.05 * n)):
        return False
    zv = np.asarray(z_values, dtype=np.float64)
    if zv.shape[0] != mask.shape[0]:
        return True
    z_in_mask = zv[mask]
    if z_in_mask.size == 0:
        return True
    near_sat = float(np.mean(z_in_mask >= SATURATION_Z))
    return near_sat < SATURATION_FRAC_FLOOR
```
Called with `fused` for the sustained/rate rules and with each head's own score-side z-array for
the per-head rule (evaluated per-head, not aggregated — one head saturating keeps firing even if
another head's signature looks like a broken baseline). The old `train_sustained_frac`/
`calib_frac` computation block was removed entirely; diagnostic dict keys renamed to
`train_max_rate` (was `calib_frac`) to reflect that it's purely informational now, not part of the
distrust decision.

### Validation

**1. Isolated 4-event diagnostic** (`/tmp/verify_fix.py`, direct `score_asset()` calls, not the
benchmark harness) — exact target behavior confirmed:
```
Wind Farm A event  92 (FALSE ALARM - must stay distrusted)        rule_fired='(distrusted:heads:omr_z)'
Wind Farm C event   9 (genuine anomaly - must NOT be distrusted)   rule_fired='+heads:omr_z'
Wind Farm C event  47 (genuine anomaly - must NOT be distrusted)   rule_fired='+heads:omr_z'
Wind Farm C event  70 (genuine anomaly - must NOT be distrusted)   rule_fired='+heads:iforest_z,omr_z'
```

**2. `tests/test_ml.py`** — the old calib_frac-based distrust tests were replaced with
`test_distrust_gate_discards_moderate_always_on` (moderate always-on head, median ~4, still
discarded) and `test_distrust_gate_keeps_saturated_always_on` (near-saturation always-on head,
median ~9.5, NOT discarded despite having zero quiet prefix). All 17 tests in the file pass.

**3. Full Farm A 22-event re-validation (zero-regression requirement, "no exceptions")** —
**exact match** to the pre-existing validated baseline:

| Metric | Before this fix | After this fix |
|---|---|---|
| recall | 1.0 (12/12) | 1.0 (12/12) |
| precision | 0.857 | 0.857 |
| F1 | 0.923 | 0.923 |
| false alarms | events 17, 71 | events 17, 71 (identical) |

Event 92 (the false alarm used in the diagnostic) is on Farm A but outside the 22-event labelled
benchmark set used for the KPI table — its `results.csv` row independently confirms
`detected=False, rule_fired='(distrusted:heads:omr_z)'`, i.e. the fix did not let it through.

**4. Farm C targeted 14-event re-validation** (`results/farm_c_satfix/`, the same event_id subset
used in the prior "Farm C targeted re-validation after the OMR fix" section: 11 missed anomalies +
3 known false alarms) — the target bug is fixed, with no new false alarms and no regressions on
the other events:

| Event | Label | Before this fix | After this fix |
|---|---|---|---|
| 4 | anomaly | empty | empty (unchanged) |
| 9 | anomaly | `(distrusted:heads:omr_z)` | **`+heads:omr_z` — newly detected** |
| 15 | anomaly | empty | empty (unchanged) |
| 35 | anomaly | empty | empty (unchanged) |
| 47 | anomaly | `(distrusted:heads:omr_z)` | **`+heads:omr_z` — newly detected** |
| 55 | anomaly | `+heads:omr_z` (detected) | `+heads:omr_z` (unchanged) |
| 67 | anomaly | empty | empty (unchanged) |
| 70 | anomaly | `(distrusted:heads:iforest_z,omr_z)` | **`+heads:iforest_z,omr_z` — newly detected** |
| 76 | anomaly | empty | empty (unchanged) |
| 78 | anomaly | empty | empty (unchanged) |
| 90 | anomaly | `+rate` (detected) | `+rate` (unchanged) |
| 54 | normal | `+heads:pca_spe_z` (false alarm) | `+heads:pca_spe_z` (unchanged false alarm) |
| 88 | normal | `+rate` (false alarm) | `+rate` (unchanged false alarm) |
| 94 | normal | `+heads:ar1_z` (false alarm) | `+heads:ar1_z` (unchanged false alarm) |

Subset recall: 2/11 → 5/11 (the exact +3 swing is events 9, 47, 70 — the events this fix targeted).
All 3 known false alarms persist unchanged: none cleared, none newly introduced. 6 events (4, 15,
35, 67, 76, 78) remain unchanged with an empty `rule_fired` — that is the separate, still-open
"fused score never crosses `alert_z_eff`" gap noted in the GMM PCA pre-reduction section, not this
fix's target, and was correctly left untouched.

**Read on scope**: this fix corrects how the self-distrust gate corroborates an ambiguous timing
signature. It does not and cannot fix events whose fused score never elevates in the first place
(events 4, 15, 35, 67, 76, 78) — that is a different, not-yet-investigated gap. Per the standing ML
Improvement Loop methodology, do not chase that gap by loosening this gate further; it needs its
own root-cause investigation.

**Files changed**: `core/alarm_rules.py` (`SATURATION_Z`/`SATURATION_FRAC_FLOOR` constants,
`_broken_baseline()` rewritten to take a z-value array instead of a training-side scalar, removed
`train_sustained_frac`/`calib_frac` computation, diagnostic key renamed to `train_max_rate`),
`tests/test_ml.py` (`test_distrust_gate_discards_moderate_always_on`,
`test_distrust_gate_keeps_saturated_always_on` replace the old calib_frac-based tests).

---

## Paper draft + detector-enable ablation wiring fix + fusion auto-tuning wiring gap (2026-06-18)
> *Added: 2026-06-18*

### Paper draft started

A Markdown-first paper draft now exists at `paper/draft.md` (not committed to `main`,
lives on `claude/research-paper-planning-ests5l`) per two explicit user decisions: draft
now and backfill numbers later (don't block writing on refreshing stale experiments), and
Markdown first, LaTeX (NeurIPS/ICML workshop style) only once content is stable — do not
set up a LaTeX project yet. The draft has a fully code-verified §3 Method and §4
Experimental Setup; §5 Results and everything downstream is explicitly marked
DRAFT/PLACEHOLDER/STALE per-section rather than silently presented as final. An
"Editorial note" section inside the draft (not part of the paper itself) tracks what's
verified vs. placeholder and records open findings for the maintainer — read it before
extending the draft further.

### Detector-enable ablation wiring fix — `no_omr` ablation leg was previously a no-op

While re-running the Farm A ablation suite for the paper, found that `core/pipeline.py`
hardcoded all five detector-enabled flags (`ar1_enabled=True, pca_enabled=True,
iforest_enabled=True, gmm_enabled=True, omr_enabled=True`) directly as kwargs to its one
`orch.fit_all_detectors()` call site — never reading them from `cfg` at all. This means
the original 2026-06-16 ablation run's `--override '{"models": {"omr": {"enabled":
false}}}'` silently did nothing: OMR still fit and scored exactly as in the full-system
config, so that "No OMR" result row in the prior ablation table was actually a duplicate
of the full system, not a real ablation. (The other four ablation legs — contamination
filter, self-distrust gate, fusion weights — were genuinely wired correctly via existing
`cfg` paths; only the detector-enable flags were the gap.)

**Fix**: each flag now reads `cfg.get("models", {}).get(<name>, {}).get("enabled", True)`
— defaulting to `True` so production behavior is byte-for-byte unchanged — instead of a
hardcoded literal. Verified directly on synthetic data: with `models.omr.enabled=False`,
the fit log shows `Fitted 4 detectors: AR1, PCA(5c), IForest(100), GMM(1)` (OMR genuinely
skipped) and the fusion stage logs `Missing streams: ['omr_z']`; without the override, 5
detectors fit including OMR and `omr_z` carries real (non-NaN) values end-to-end. All 17
`test_ml.py` tests still pass unchanged. This is additive/default-preserving and was not
treated as needing the ML Improvement Loop's decide-before-acting gate, since it only
makes an ablation knob that was already supposed to exist actually work, and cannot change
default behavior for any caller that doesn't set `models.<name>.enabled`.

**Files changed**: `core/pipeline.py` (`score_asset()` — the `fit_all_detectors()` call
site now derives all five `*_enabled` kwargs from `cfg["models"][<name>]["enabled"]`).

### Fusion auto-tuning wiring gap — found, documented, NOT yet fixed (open decision)

Separately (and NOT touched by the fix above), tracing `core/fuse.py`'s
`tune_detector_weights()` and its one call site in `run_fusion_pipeline()` while writing
the paper's §3.6 found that **`core/pipeline.py` never passes `episodes_df` into the
fusion auto-tuner** — neither in production scoring nor in `scripts/care_benchmark.py`.
Combined with `ml_defaults.py` setting `fusion.auto_tune.require_external_labels: False`
(overriding the function's own default of `True`), this means:
- `tuning_method` resolves to the configured default `"episode_separability"` rather than
  ever falling back to the label-free `"statistical_diversity"` method that exists
  specifically for the no-labels case.
- Inside `episode_separability`, with `labels=None`, every detector's `metric_value`
  resolves to the identical `"no_labels"` floor (`max(prior, 1e-3)` with all
  `detector_priors` defaulting to 1.0) — so the post-softmax "tuned" target is *exactly
  uniform* across whichever heads are present, regardless of any detector's actual
  separability.
- This uniform target is then EMA-blended into the current weights at
  `learning_rate=0.3`, drift-clamped to `±20%`/run, and renormalized — i.e. the
  auto-tuner's real, measured effect today is a bounded, repeated pull of the configured
  base weights toward `1/n_detectors`, not label-informed reweighting.

Confirmed against the actual deployed weight-tuning log line-by-line (e.g.
`pca_spe_z: 0.300 -> 0.267`, `gmm_z: 0.050 -> 0.062`, both moving toward `1/6 ≈ 0.167`;
manually recomputed the EMA+clamp math for `gmm_z` and it matches the observed log
exactly). This also explains the earlier ablation finding that "auto-tuning's value on
Farm A is calibration sharpness, not recall/precision, with no consistent win/loss
pattern vs. equal weights" — the "tuned" weights were mostly a damped pull toward equal
weighting in the first place, so of course they look similar to the equal-weights config.

**This has NOT been fixed.** Per the standing ML Improvement Loop methodology, a behavior
change to the production fusion-weight mechanism needs a deliberate decision before
implementation, not a unilateral fix discovered mid-paper-writing. The paper draft
documents the mechanism exactly as it behaves today (not as originally designed) and
flags this as the most important correction relative to the original project plan. Two
candidate fixes exist, neither implemented: (a) wire real held-out episode labels into
`tune_detector_weights()` where available, or (b) flip the default fallback trigger so
`statistical_diversity` (label-free, unaffected by this finding, already implemented) is
what actually fires in the no-labels case instead of `episode_separability` silently
degrading to uniform. Decide before `core/fuse.py`/`core/pipeline.py` are touched again
for this; do not fix opportunistically as a side effect of unrelated work.

**Files**: no production code changed for this finding — `core/fuse.py` (lines ~460-997,
`tune_detector_weights()`) and `core/pipeline.py` (the `fuse.run_fusion_pipeline()` call
site, which has no `episodes_df=` argument) were read and traced, not edited.

---

## Farm C full 58-event re-validation after the OMR + self-distrust saturation fixes (2026-06-18)
> *Added: 2026-06-18*

Both the OMR in-sample-bias fix and the self-distrust gate magnitude-saturation fix (above)
had only been checked against a **targeted 14-event subset** (the events already known to be
problematic from the prior full run). This session ran the genuine full 58-event Farm C
benchmark (`results/farm_c_v2/`, `--workers 2`, same `ML_DEFAULTS`) to get the real farm-wide
number — and the targeted-subset caveat already on record ("does NOT substitute for a full-farm
KPI re-validation — false alarms on previously-clean normal events... would not be visible")
turned out to be exactly right.

**Full-farm result:**
| Metric | GMM-fix checkpoint | OMR+saturation-fix checkpoint (this run) |
|---|---|---|
| recall | 0.593 (16/27) | **0.778 (21/27)** |
| precision | 0.842 | 0.656 |
| F1 | 0.696 | 0.712 |
| false alarms (of 31 normal) | 3 | **11** |
| KPI | FAIL | FAIL (recall now within 1 event of passing; F1 short) |

**What happened, precisely:**
- Recall jumped +5 events (16→21) — OMR firing at all (it structurally could not before the
  in-sample-bias fix) is now contributing real detections across the farm, not just the 3
  events checked in the targeted subset.
- But 7 of the 11 false alarms are newly-introduced `omr_z`-driven false positives on normal
  events that were **never part of the targeted 14-event subset** (event_ids 8, 48, 56, 58, 62,
  63, 75 — all `rule_fired = "+heads:omr_z"`). The targeted re-validation's own normal-event
  checks (54, 88, 94) were unaffected and remain false alarms exactly as before — the regression
  is entirely on previously-untested normal events, which is precisely the blind spot the
  targeted-subset method warned about.
- The 6 remaining missed anomalies (event_ids 4, 15, 35, 67, 76, 78) are **unchanged**, all with
  empty `rule_fired` — confirming this is the same distinct, still-uninvestigated "fused score
  never crosses `alert_z_eff`" gap flagged since the original GMM-fix checkpoint, not something
  either the OMR or saturation fix touches.

**Interpretation, not yet acted on (per the standing ML Improvement Loop methodology — document,
then plan, then decide before touching code):** OMR now behaves on Farm C the way GMM did before
its own PCA pre-reduction fix — newly capable of firing, and apparently over-sensitive on a subset
of normal Farm C operating conditions at 957-sensor / ~3300-engineered-feature scale. This looks
like the same family of dimensionality-driven calibration fragility already fixed once for GMM,
but has NOT been investigated for OMR specifically. Do not patch this opportunistically; it needs
its own root-cause pass (e.g. checking whether OMR's residual scale or top-3 aggregation degrades
similarly with feature count) and an explicit Farm-A zero-regression re-check before any change,
exactly like the GMM and OMR fixes above.

**Read on methodology**: this is the clearest demonstration yet, with real numbers, of why a
fix's validation scope matters — the 14-event targeted re-validation correctly confirmed its
*target* bug was fixed with no regression on the events it checked, but a fix's blast radius can
exceed the subset used to validate it. Full-farm (or full-dataset) re-validation is required
before any fix is considered farm-wide-safe, not just subset-safe.

**Per the user's explicit standing instruction this session, this farm-specific result is
recorded here (the durable knowledge base) but is deliberately NOT being written into
`paper/draft.md` as a standalone finding** — the paper's Results section is to be filled in once
findings are synthesized across many datasets, not per-dataset as each one completes.

**Files**: no code changes — `results/farm_c_v2/` (gitignored, local-only) holds the full
`results.csv`/`summary.json` for this run.

---

## OMR kurt/skew exclusion fix — Farm A exact-match, Farm C mixed result (2026-06-18)
> *Added: 2026-06-18 — fixes GitHub issue #72 (OMR-driven false alarms on CARE Farm C)*

Direct follow-on to the section immediately above. Diagnosed the newly-introduced `omr_z`
false-alarm cluster (events 8, 48, 56, 58, 62, 63, 75) with a targeted script
(`/tmp/diag_r2_inspect.py`, not committed) that computed in-sample R² per engineered feature
against OMR's fitted reconstruction model and ranked features by mean score-window scaled
residual. Result: the top features driving the false-alarm score on event 56 were
`sensor_95_avg_kurt` (mean_scaled=2003.5), `sensor_81_avg_kurt` (1276.2), `sensor_95_avg_skew`
(239.9), `sensor_81_avg_skew` (233.4), `sensor_88_avg_kurt` (94.0) — i.e. kurtosis/skewness
engineered features dominate the top-3 candidate pool almost completely, both on the calibration
holdout and on live scoring, regardless of true anomaly state. Root cause: kurtosis and skewness
are 3rd/4th-moment statistics computed over a `window=16` rolling window; their sampling variance
is inherently high even on perfectly healthy data (asymptotic var ≈24/n for kurtosis, ≈6/n for
skewness — a property of the estimator, not of the data or the dataset). OMR's global
reconstruction model also can't predict these higher-moment features well from other sensors'
mean/std-type features, so their residuals stay large and noisy under reconstruction regardless of
true health. Farm C merely has far more such columns (957 sensors → ~450 kurt/skew engineered
columns) than Farm A (86 sensors → ~40), giving this latent, dataset-independent bug many more
chances to dominate the top-3 vote.

**Fix** (`core/omr.py`, `OMRDetector.score()`): kurt/skew-suffixed feature columns are excluded
from the score's top-3 candidate pool entirely (`scaled[:, kurt_skew_mask] = -np.inf` before the
`np.partition` top-k step). The pre-existing, separate `contributions`/`culprits` attribution path
(its own `kurt_skew_weight=0.25` down-weighting) was left untouched — this only fixes the score
itself, not the attribution display. (The OMR score vs. contributions formula divergence this
surfaced is filed separately as issue #75, not bundled into this fix.)

### Farm A re-validation (22 events) — exact, unchanged match

| Metric | Pre-fix | Post-fix |
|---|---|---|
| recall | 1.0 (12/12) | 1.0 (12/12) |
| precision | 0.923 | 0.923 |
| F1 | 0.960 | 0.960 |
| false alarms | events 17, 71 | events 17, 71 (identical) |

Zero regression — exactly the signature expected from fixing a universal-but-rarely-triggered
estimator-variance bug rather than a Farm-C-specific patch (Farm A has far fewer kurt/skew columns
so the bug rarely won the top-3 vote there in the first place).

### Farm C full 58-event re-validation — mixed result, KPI still FAIL

| Metric | OMR+saturation-fix checkpoint | kurt/skew-fix checkpoint (this run) |
|---|---|---|
| recall | 0.778 (21/27) | **0.704 (19/27)** |
| precision | 0.656 | **0.792** |
| F1 | 0.712 | 0.745 |
| false alarms (of 31 normal) | 11 | **5** |
| KPI | FAIL | FAIL (recall short of 0.80; F1 short of 0.75 by 0.005) |

Row-level diff (`results/farm_c_v2/results.csv` vs. `results/farm_c_kurtskew_fix/results.csv`,
both gitignored/local):

- **6 of 7 `omr_z`-driven false alarms cleared** (event_ids 48, 56, 58, 62, 63, 75 — all flipped
  `+heads:omr_z` → no alarm). Zero new false alarms introduced anywhere; the 4 other pre-existing
  false alarms unrelated to `omr_z` (36 `gmm_z`, 54 `pca_spe_z`, 88 `rate`, 94 `ar1_z`) are
  byte-for-byte unchanged.
- **One `omr_z`-driven false alarm did NOT clear**: event 8 (`+heads:omr_z` both before and after,
  `fused_max` literally identical 7.409→7.409). This event's elevated `omr_z` is evidently coming
  from a different root cause than the kurt/skew noise — not yet investigated.
- **Two anomaly events flipped from detected → missed**:
  - Event 47: was `+heads:omr_z` (alarm_frac 0.831), now alarm_frac 0.000, empty `rule_fired`.
    `fused_max` barely moved (8.571→8.470) but the per-head `omr_z` rule itself no longer clears
    its threshold — this event's earlier detection was riding the same kurt/skew noise signal that
    drove the false alarms, just on an event where the timing happened to coincide with a genuine
    anomaly.
  - Event 90: was `+rate` (not `omr_z` per-head at all), now alarm_frac 0.000. `fused_max` dropped
    9.574→8.924 and the self-tuned `alert_z_eff` dropped in lockstep (8.180→7.400) — OMR's lower
    overall contribution to the fused ensemble score lowered the peak excursion needed to satisfy
    the rate-of-change persistence rule.
  - No anomaly events were newly detected by this fix.

**Honest framing**: this is a real, measured trade-off, not a clean win. The false-alarm/precision
improvement is substantial (11→5 false alarms, +0.136 precision) and directly validates the
root-cause diagnosis. But two of the previously-detected anomalies were detected *via the same
noisy mechanism* being fixed — removing the noise correctly suppressed the false alarms it caused
elsewhere, but also removed an accidental true-positive ride-along on events 47 and 90. F1 moved
in the right direction (0.712→0.745) but the farm-wide KPI remains FAIL on both legs. This was
reported to the user in full (false-alarm win + recall cost, not just one side) before any
merge-to-main decision was made, per the standing ML Improvement Loop "decide before act" rule —
a real recall regression on a benchmark farm is exactly the kind of trade-off only the user should
sign off on, not something to merge unilaterally because the headline F1 number moved up.

**Open items, not yet investigated**:
- Event 8's remaining `omr_z` false alarm has a non-kurt/skew root cause — separate from this fix.
- Events 47 and 90's lost detections — whether they're worth chasing (e.g. a less blunt instrument
  than full exclusion, such as down-weighting kurt/skew in the top-3 pool rather than removing them
  outright) is an open question, not yet planned.
- The 6 anomaly events with empty `rule_fired` on both checkpoints (4, 15, 35, 67, 76, 78) remain
  the same distinct, still-uninvestigated "fused score never crosses `alert_z_eff`" gap noted since
  the original GMM-fix checkpoint — untouched by this fix, as expected.

**Files changed**: `core/omr.py` (`OMRDetector.score()` — kurt/skew exclusion mask before top-3
`np.partition`). Committed `d6b5cd0`, pushed to `claude/research-paper-planning-ests5l`. Per-event
diff and summaries: `results/farm_a_kurtskew_fix/`, `results/farm_c_kurtskew_fix/` (both
gitignored/local).

---

## CARE Farm B — first full result (2026-06-18)
> *Added: 2026-06-18*

Farm B (15 events: 6 anomaly / 9 normal, 257 features) was downloaded for the first time this
session (`scripts/download_care_benchmark.py --dest care_data --farms B`) and benchmarked with the
same `ML_DEFAULTS` used everywhere else, post-kurt/skew-fix, `--workers 2`. Confirms the corrected
15-event count above (see CARE-to-Compare Dataset section).

**Result:** `recall=0.333 (2/6), precision=0.5, F1=0.4` — **KPI FAIL, and the worst of the three CARE
farms so far** (Farm A: recall 1.0/F1 0.960; Farm C: recall 0.704/F1 0.745).

**Per-event breakdown** (`results/farm_b/results.csv`, gitignored/local):
- **2 of 6 anomalies detected**, both bearing-damage faults: event 27 ("main bearing damage",
  `+avail+heads:pca_spe_z,omr_z`) and event 53 ("Rotor Bearing 2 - Damage",
  `+heads:ar1_z,pca_spe_z,iforest_z`).
- **4 of 6 anomalies missed, all with completely empty `rule_fired`** (fused score never crosses
  `alert_z_eff` at all) — events 7, 19, 34 (all "high temperature in transformer cell") and 77
  ("Turbine in standstill ... due to rotorbearing damage"). This is the **same empty-`rule_fired`
  failure signature already open and undiagnosed on Farm C** (6 events: 4, 15, 35, 67, 76, 78) —
  Farm B's result is the first cross-farm confirmation that this gap is general, not Farm-C-specific.
  Notably 3 of the 4 misses share one fault description ("high temperature in transformer cell"),
  suggesting a possible thermal-drift signature that current detectors don't separate well from
  normal variation — not yet investigated.
- **2 of 9 normal events false-alarmed**, both via `+heads:pca_spe_z` (events 23, frac=0.154; and
  87, frac=0.238) — `pca_spe_z` is implicated in both of Farm B's false alarms, same detector
  flagged in some of Farm C's false alarms historically.

**Not yet investigated or acted on** (per the standing ML Improvement Loop methodology — document
first): why Farm B's empty-`rule_fired` rate (4/6 = 67%) is even higher than Farm C's post-fix rate
(6/11 of originally-missed ≈ 35% of all 27 anomalies), and whether the thermal-fault pattern in 3 of
4 misses points to a specific, fixable gap (e.g. a detector class that's better suited to slow
thermal drift than the current ensemble) or is coincidental given the small (6-event) sample.

**Files**: no code changes. `results/farm_b/` (gitignored/local) holds `results.csv`/`summary.json`.
CARE-to-Compare Dataset section above corrected (37→15 events) in the same session.

---

## New benchmark dataset research — Tennessee Eastman Process feasibility confirmed (2026-06-18)
> *Added: 2026-06-18*

Per user request to find more benchmark datasets for validating ACM's accuracy (explicitly NOT a
public-leaderboard requirement — accuracy validation only), researched candidates directly via
WebSearch/WebFetch (no subagent, per explicit instruction) against the standing domain-fit
criterion established by the SKAB rejection (see "Cross-Dataset Generality Testing" section above):
industrial/SCADA-style assets, hour-to-day-scale fault persistence, sufficient pre-fault history.
**The user also clarified the adoption bar this session: structural closeness to CARE's file layout
is a loose requirement — any dataset that can be *transformed* into CARE's shape (`event_info.csv`
+ `datasets/{id}.csv`, train/prediction split, sensor columns) should be used, since the conversion
is a one-time cost while `care_benchmark.py` itself then runs completely unmodified. Minimize new
bespoke tooling; prefer reusable transforms over one-off harnesses.**

### Candidates checked and their domain-fit verdict

| Dataset | Verdict | Why |
|---|---|---|
| **CARE Farm B** | Done (see section above) | Same trusted dataset, zero new vetting |
| **Tennessee Eastman Process (TEP)** | **Strong candidate, feasibility confirmed end-to-end** | See below |
| **HAI (ICS security)** | **Rejected — same failure mode as SKAB** | Confirmed individual attacks last 2.5–48 minutes (not hours-to-days); the published "12/33/30/11/26 hour" figures are test-*file* spans containing many short attacks, not single attack durations |
| **SWaT (ICS security)** | **Rejected — same failure mode as SKAB** | Confirmed most of the 36 attacks last 2–4 minutes; a few extend to 9 hours, but the modal case is short-transient |
| **WADI (ICS security)** | **Rejected, same basis as SWaT** | Companion dataset to SWaT, same testbed design philosophy; also gated (iTrust request form, ~3 business days) — not pursued given the duration rejection on its sibling dataset |
| **DAMADICS** | Lower priority | Real sugar-factory actuator faults (good duration fit, sustained from specific fault-injection dates), but no built-in per-event train/test split (would need fully custom windowing) and only ~1 day of pre-fault history — higher engineering cost for a dataset that doesn't reuse the CARE-shape transform cleanly |
| **NASA SMAP/MSL** | Lower priority | Aerospace spacecraft telemetry, not SCADA/industrial; anomaly-duration fit vs. the criterion was not confirmed before TEP's feasibility check made it the clear next step |
| **Zenodo 10958775** | Not a new dataset | Identical farm/feature structure to CARE-to-Compare (86/257/957 features, 95 events) — this is the same underlying dataset, not a diversification opportunity |

**Standing-rule note**: HAI/SWaT/WADI all fail the exact same criterion that got SKAB rejected
(short-transient anomalies, not hour-to-day-scale fault development). This is now a 4-for-4
pattern across every ICS-*security* (cyberattack) benchmark checked — worth treating as a category
signal: attack-style ICS datasets are structurally mismatched with ACM's slow-fault-development
target domain, vs. process-simulation/SCADA-style datasets (CARE, TEP) which are not.

### TEP feasibility — confirmed via direct hands-on verification, not just literature

- **Source**: Harvard Dataverse `doi:10.7910/DVN/6C3JR1` (Rieth et al. 2017 deposit). Confirmed via
  the Dataverse JSON API (`https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/6C3JR1`)
  to be genuinely open-access — direct `curl`/`wget` against
  `https://dataverse.harvard.edu/api/access/datafile/{id}` works with **no auth, no API key, no
  Kaggle credentials needed** (Kaggle's CSV mirrors of the same dataset were checked as a fallback
  but would require credentials not present in this environment — the Dataverse RData files are the
  better path). Four files: `TEP_FaultFree_Training/Testing.RData`,
  `TEP_Faulty_Training/Testing.RData` (24 MB–837 MB).
- **Structure, confirmed by actually parsing the data** (not just the paper): `faultNumber` (0 = none,
  1–20 = fault type), `simulationRun` (1–500, independent simulations — directly analogous to a CARE
  "event"), `sample` (1–500 for Training files, 1–960 for Testing files), then 52 numeric process
  variables (`xmeas_1..41`, `xmv_1..11`) — clean, no missing-value markers, directly comparable in
  shape to CARE's sensor columns.
- **Fault timing, confirmed empirically (not assumed from literature)**: in `Faulty_Testing`, fault 1
  / run 1, `xmeas_1` mean jumps from 0.249 (samples 1–160) to 0.760 (samples 161–960) — confirms the
  fault is introduced at sample 161 and sustained through sample 960. At the dataset's documented
  3-minute sampling interval that is **fault onset at hour 8, persisting ~40 hours to the end of the
  48-hour test run** — squarely inside ACM's hour-to-day-scale domain-fit criterion, not a
  short-transient case like the rejected ICS-security datasets above.
- **A real engineering obstacle was found and resolved, not just a clean download**: `pyreadr`
  (the standard Python RData reader) was killed by the OOM killer (exit 137) twice while parsing the
  837 MB `Faulty_Testing.RData` on this 15 GB container — its cross-language conversion overhead is
  apparently too memory-hungry for this file size in Python. **Fix**: installed `r-base-core` via
  `apt-get install -y --no-install-recommends r-base-core` (plain `r-base-core` pulled in X11/Tk
  dependencies that 404'd; the `--no-install-recommends` flag avoids that) and used R's own native
  `load()` to parse the same file — this worked without incident, confirming the right production
  path is a one-time R-side conversion (RData → per-run CSV/parquet) rather than a Python-side
  `pyreadr` read of the full file. This is exactly the kind of one-time transform cost the user's
  "transform once, reuse the harness forever" principle anticipates.

### Recommended integration shape (not yet built — pending scope decision)

A converter (R for the RData→flat step, Python for the CARE-shape emission) would produce, per
selected `(faultNumber, simulationRun)` pair: a synthetic `time_stamp` (start + `sample * 3min`),
`status_type_id`, `train_test` (`train` for samples 1–160, `prediction` for 161–960, matching the
empirically-confirmed fault onset), and the 52 process variables as sensor columns — i.e. exactly
CARE's `datasets/{id}.csv` shape, plus a generated `event_info.csv` with `event_label` derived from
`faultNumber` (0 → normal, else anomaly) and `event_description` from the standard TEP fault-name
table (e.g. fault 1 = "A/C feed ratio step"). Once those two files exist, `care_benchmark.py` should
run completely unmodified — no new benchmark harness needed, per the user's stated preference.

**Open scope question, not yet decided**: TEP has 500 simulation runs × 20 fault types — far more
than CARE's 15–58 events per farm. A full cross-product benchmark (10,000 fault events + 500 normal
runs) would be a massive, likely unnecessary compute cost; a representative subsample (e.g. one or a
handful of runs per fault type, mirroring CARE's "tens of events" scale) is the obvious choice but
the exact sampling scheme has not been decided.

**Files**: no code changes yet — this section is feasibility research only, per the standing
"document → plan → decide before acting" methodology. `r-base-core` is now installed in this
container's apt state (not committed to the repo; irrelevant to the codebase itself, only to this
sandbox).

---

## Empty-`rule_fired` gap — root-caused, two distinct mechanisms found, NOT yet fixed (open decision) (2026-06-18)
> *Added: 2026-06-18 — investigation of the gap flagged since the GMM-fix checkpoint, now confirmed on both Farm C (6 events) and Farm B (4 events)*

> **⚠️ SUPERSEDED 2026-06-18 (later, multi-angle re-investigation) — the central premise of this
> section is WRONG and the "two mechanisms" framing is incomplete. Read
> "Empty-`rule_fired` gap — CORRECTED diagnosis (the premise was wrong)" below before acting on
> anything here.** Two specific claims in this section do not survive direct measurement:
> (1) "the fused score never crosses `alert_z_eff` at all" is FALSE for 6 of the 8 Farm C misses —
> their `fused_max` (8.1–9.6) sits *well above* `alert_z` (5.8–8.2); the peak crosses, the *shape*
> doesn't sustain. (2) "Mechanism 1 (rate threshold pinned at 0.9)" is not causal — the threshold is
> pinned at 0.9 on detected events and clean normals too. The genuinely decisive finding (below) is
> that **the fused score does not separate 6 of 8 missed anomalies from normal Farm C operation by
> ANY statistic** — magnitude, fraction, or run-length, at any bar — so no fused-score rule can
> recover them without a 1:1 false-alarm cost. The narrative below is preserved as the
> investigation record, not as a correct conclusion.

Per the standing ML Improvement Loop, this is the "document" step for the cross-farm gap where a
labelled anomaly's fused score never crosses `alert_z_eff` at all (`rule_fired=""`, `alarm_frac=0`).
Investigated directly by re-running `apply_alarm_rules()` against the saved `event_*_scores.csv` /
`event_*_train_fused.csv` for all 6 Farm C misses (events 4, 15, 35, 67, 76, 78) and all 4 Farm B
misses (events 7, 19, 34, 77), inspecting `rules_diagnostic` and the score-side z arrays directly —
not guessed at. Two distinct, well-evidenced mechanisms were found, not one:

### Mechanism 1 — rate/per-head threshold pinned at the hard 0.9 ceiling (pervasive, but not solely decisive)

`apply_alarm_rules()`'s rate rule (and each per-head rule) anchors its threshold to `base` — the
training data's own **worst** rolling-window rate of `fused >= 3.0` (`np.nanmax(rolling_rate(...))`,
`core/alarm_rules.py` line ~227) — then sets `thr = clip(base * 1.5 + 0.05, 0.05, 0.9)`. Measured
directly: `base` (`train_max_rate` in the diagnostic) is **0.58–1.0** for 9 of the 10 missed events
across both farms (e.g. Farm C event 35: `base=1.0`; Farm B event 19: `base=0.938`), which pins
`thr` at the 0.9 ceiling — meaning the rule needs ~90% of an entire 24h (rate) or 7d (per-head)
rolling window to read `z>=3.0` before it can fire at all, on top of the already-required
persistence floor.

This is real and pervasive — but checking the contrast set (Farm C's *detected* anomalies and a
sample of Farm A events) shows `rate_thr` pinned at 0.9 in MANY of those too (e.g. Farm C event 9,
detected via `+heads:omr_z`, also has `rate_thr=0.900`). So ceiling-saturation alone does not
explain misses; it explains why the **rate rule specifically** is largely dead weight on Farm B/C,
while detection in practice comes down to whether some *other* rule (sustained, availability, or a
per-head rule whose own threshold happens NOT to be saturated) clears its own bar.

**Why a naive "switch max to a quantile" fix doesn't actually work** (checked before proposing
anything): for event 35, even `quantile(rolling_rate, 0.99) == 1.0` — identical to the true max.
The elevated rolling-rate excursions in training aren't single-point outliers; they're **4 separate
contiguous blocks covering 7.4% of the entire rolling-rate trace** (measured directly). A simple
percentile swap would need to go above the 99th percentile to escape this, defeating the point of
using a quantile in the first place. For event 4, `base=0.583` and even `quantile(0.999)=0.569` —
still clips to 0.9 either way (`SAFETY=1.5` means anything above `~0.567` saturates), so a quantile
swap changes nothing there either. The contamination is too large a fraction of the calibration
window for an order-statistic swap to help; it would need genuine contamination *detection* (e.g.
routing this `base` computation through something resembling `core/fuse.py`'s existing
`CalibrationContaminationFilter`, which currently protects detector-level z-calibration but is
never applied to this alarm-rule-layer "worst healthy day" computation at all — a real
defense-in-depth gap between the two layers).

### Mechanism 2 — a distinct, more fundamental detection-power gap on the spikiest events

For Farm C event 4 specifically (and likely others), the per-head thresholds are NOT saturated
(0.10–0.37, comfortably room to fire) — yet still never fire. Checked the score-side z arrays
directly: every head DOES spike to the calibrated ceiling at times (raw z hits 10.0, `frac(z>=3.0)`
is 1–12% per head) — the signal is genuinely there — but those spikes are too **scattered** to
ever sustain a 7-day rolling rate above ~24% for any head (`ar1_z`'s 7d-rolling max is 0.242,
clearing only the lowest, not the typical, per-head threshold). Separately, the sustained rule's
longest actual run above `alert_z` is only 16 samples against a required persist of 49. This event's
real fault signature is "frequent brief spikes, never long-or-dense enough" — falling between the
cracks of both existing rule shapes (`sustained` wants a long contiguous plateau; `rate`/`per-head`
want a long-window-sustained elevated rate). Farm B event 34 shows the same shape: longest run 8
vs. required persist 34, and no per-head rolling rate reaches even its own (unsaturated) threshold.

### Why this is being documented, not fixed, this session

Both mechanisms point toward real fixes (contamination-aware "worst healthy day" estimation for
Mechanism 1; a shorter/adaptive rate window or a new "spike density" rule shape for Mechanism 2) —
but both would touch the same core alarm-rule calibration machinery that just passed a hard-won,
exact-match Farm A zero-regression validation (see "OMR kurt/skew exclusion fix" above), and
neither fix is a clear, low-risk, single-line correction the way the detector-enable wiring fix
was. Per the standing rule ("a behavior change to the production fusion/alarm-rule mechanism needs
a deliberate decision before implementation, not a unilateral fix discovered mid-investigation" —
the same posture already applied to the fusion auto-tuning wiring gap above), this is recorded as
an open decision point, not implemented. Candidate directions for whoever picks this up:
(a) route the rate/per-head `base` computation through a contamination-aware estimator instead of
a raw max — addresses Mechanism 1; (b) add a shorter, denser-spike-sensitive rolling-rate rule
alongside the existing 24h/7d windows — addresses Mechanism 2; both need their own
plan-before-implement pass and a full Farm A + Farm B + Farm C re-validation, no exceptions.

> **UPDATE 2026-06-18 (later same day) — candidate direction (a) above was tried and REJECTED.**
> Do not re-attempt "swap the rate/per-head `base` computation's raw `nanmax` for
> `CalibrationContaminationFilter`'s filtered max" without reading the full writeup below first —
> it was implemented, validated, and conclusively falsified by ACM's own synthetic test suite
> (`tests/test_ml.py`), not just a CARE-specific concern. See "Contamination-filter fix attempt for
> the empty-`rule_fired` gap — rejected" below for the evidence and root cause.

**Files**: no code changes — `core/alarm_rules.py` (`apply_alarm_rules()`, `rolling_rate()`,
`self_tune_alarm_rule()`) was read and diagnosed via direct re-invocation against saved score CSVs,
not edited.

---

## Contamination-filter fix attempt for the empty-`rule_fired` gap — rejected (2026-06-18)
> *Added: 2026-06-18 — direct follow-on to "Empty-`rule_fired` gap" above, same session*

Direct follow-on to Mechanism 1 above. The natural fix it points at — replace the rate/per-head
`base`/`base_h` computation's raw `np.nanmax(rolling_rate(...))` with a contamination-filtered max,
using the exact `CalibrationContaminationFilter` class `core/fuse.py` already has for detector
z-calibration — was implemented, empirically validated against real CARE events and ACM's own
synthetic test suite, and **rejected**. This section documents the full evidence trail and the
decision so nobody re-tries the same naive version of this fix without reading it first.

### What was implemented

`core/alarm_rules.py` gained a `_contamination_filtered_max_rate(z, z0, window)` helper that runs
`CalibrationContaminationFilter(method="hybrid")` over the raw z-series before computing
`rolling_rate(...)` and taking the max — replacing the two `base = float(np.nanmax(...))` /
`base_h = float(np.nanmax(...))` call sites in `apply_alarm_rules()`. `hybrid` (IQR pre-filter +
iterative MAD refinement) was chosen over the more aggressive `iterative_mad` after a side-by-side
comparison (below) showed `iterative_mad` recovers slightly more missed detections but at the cost
of materially more new false alarms.

### Validation steps run, in order, with results

1. **Self-distrust gate corroboration** — does the gate (see "Self-distrust gate
   magnitude-saturation fix" above) discard the newly-firing rules as broken-baseline symptoms?
   Checked directly against Farm C event 4 across every method/channel combination that newly
   fired: **no** — coverage never exceeded the gate's 50% threshold in any case, so the gate was
   never even evaluated. The fix's wins on this event are not undermined by the gate.
2. **Filter-method sensitivity** — re-ran the rate rule and all 6 per-head rules for Farm C event 4
   across `iterative_mad`, `iqr`, `hybrid`, `z_trim`. Materially different thresholds and different
   sets of per-head channels flip to firing depending on method (e.g. `pca_spe_z`/`iforest_z` flip
   under `iterative_mad` but not under `hybrid`). There is no single "obviously correct" method
   without an external validation signal to choose between them.
3. **False-alarm safety check, Farm A** (8 known-clean normal events: 3, 13, 14, 24, 25, 38, 69,
   92) — **zero regressions** under both `iterative_mad` and `hybrid`. All 8 stayed clean.
4. **False-alarm safety check, Farm B** (7 known-clean normal events: 2, 21, 52, 74, 82, 83, 86) —
   **regressions found.** Under `hybrid`: 1 new false alarm (event 83, `ar1_z`, alarm_frac=0.003 —
   marginal but real). Under `iterative_mad`: 5 of 7 events got new false alarms (events 2, 21, 74,
   82, 83) across `ar1_z`/`pca_t2_z`/`pca_spe_z`/`omr_z`. (One `omr_z` case on event 83 newly fired
   but was correctly discarded by the self-distrust gate — the gate did useful work there, but the
   other channels on the same and other events were not discarded and are genuine new false
   alarms.) This was reported to the user as "an ordinary precision/recall trade-off, not a clean
   bug fix" — ACM's farm-wide labelled benchmark alone made this trade-off visible before any
   external advice was needed.
5. **Decisive test — ACM's own synthetic test suite, `tests/test_ml.py`.** This is the step that
   actually settled the decision, not the CARE diagnostics above. Running the full suite with the
   fix in place produced 3 failures that were clean before the change:
   - `TestFalseAlarmResistance::test_clean_continuation_quiet` — alarm fraction on data with NO
     fault at all jumped to 5.3% (required: < 2%).
   - `TestFalseAlarmResistance::test_seasonal_shift_tolerated` — alarm fraction on an explained,
     non-faulty ambient shift jumped to 26.5% (required: < 10%).
   - `TestFaultSensitivity::test_bearing_style_drift_detected` — the alarm now fires *before* the
     injected fault begins (sample 193 vs. the required ≥ 375).
   These are exactly the tests built to catch this class of regression, and they caught it
   immediately — a faster and more conclusive signal than the farm-by-farm diagnostics above.

### Root cause of the rejection

`CalibrationContaminationFilter` does blanket statistical trimming of the upper tail of a value
distribution — it has no way to distinguish "this tail is genuine contamination" (Farm C event 4:
a real fault baked into the training window) from "this tail is legitimate, rare-but-normal
operation" (the synthetic clean-continuation and seasonal-shift tests, where there is no fault in
training at all). On a real contaminated asset, trimming the tail correctly de-poisons the
threshold. On a genuinely clean asset, trimming the same tail just deletes real, healthy variance
from the "worst healthy day" estimate — making the resulting threshold too sensitive and producing
exactly the false-alarm-on-clean-data failure mode the tests caught. This is the same
genuine-fault-vs-legitimate-rare-variation ambiguity the self-distrust gate and the OMR fixes both
had to solve with a *corroborating signal* (z-saturation magnitude for the gate; kurt/skew
exclusion for OMR) rather than a blanket statistical trim — this candidate fix had no corroborating
signal, which is exactly why it failed.

### Decision

**Rejected, not deferred.** `core/alarm_rules.py` was reverted to its pre-fix state via
`git checkout -- core/alarm_rules.py`. Confirmed clean: all 17 `tests/test_ml.py` tests pass
post-revert. The empty-`rule_fired` gap (both mechanisms, documented above) remains open and
unfixed — this session ruled out one specific candidate fix with hard evidence, it did not solve
the underlying gap.

**What a real fix needs, for whoever picks this up next**: a mechanism with its own corroborating
signal — e.g. detecting a *contiguous* elevated block in the rolling-rate trace (consistent with a
real fault baked into training) rather than trimming by value-distribution percentile (which can't
tell a contiguous contamination block from scattered legitimate tail values) — not a different
`CalibrationContaminationFilter` method or parameterization. Re-tuning this same filter's
parameters (z_threshold, iqr_multiplier, min_retained_ratio) is very unlikely to fix the underlying
issue, because the problem is the mechanism (percentile trimming) being applied to a question
(genuine contamination vs. legitimate tail) that percentile trimming structurally cannot answer.
This needs its own plan-before-implement pass, per the standing ML Improvement Loop methodology —
do not opportunistically retry a parameter sweep on the same mechanism.

**Files changed then reverted**: `core/alarm_rules.py` (`_contamination_filtered_max_rate()`
helper + both `base`/`base_h` call sites — implemented, tested, reverted; net diff is zero).
No files remain changed from this attempt.

---

## Empty-`rule_fired` gap — CORRECTED diagnosis (the premise was wrong) (2026-06-18)
> *Added: 2026-06-18 — multi-angle re-investigation that overturns the "Empty-`rule_fired` gap —
> two mechanisms" section above. This is the current, correct understanding; that section is
> SUPERSEDED and kept only as the investigation record.*

Prompted by "take a step back, are we missing something?", the missed-anomaly events were
re-investigated from angles the original write-up skipped: actual `fused_max` vs `alert_z`,
post-`event_start` (fault-region-only) statistics, contiguous run-length at multiple magnitude
bars, the fault DESCRIPTIONS from `event_info.csv`, and `status_type_id`. All numbers below are
from direct measurement against `results/farm_c_v2/event_*_scores.csv` + `care_data/Wind Farm
C/event_info.csv` (scripts run ad-hoc, not committed). **Three load-bearing claims in the prior
section turned out to be false or incomplete:**

### What was wrong

1. **"The fused score never crosses `alert_z_eff`" is FALSE.** For 6 of the 8 Farm C misses,
   `fused_max` is *well above* the self-tuned threshold:

   | event | fused_max | alert_z | crosses? |
   |---|---|---|---|
   | 4 | 8.10 | 5.84 | YES (peak) |
   | 15 | 8.18 | 5.66 | YES |
   | 35 | 8.70 | 9.16 | no (threshold inflated) |
   | 47 | 8.57 | 6.13 | YES |
   | 67 | 9.62 | 6.12 | YES |
   | 76 | 7.51 | 8.91 | no (threshold inflated) |
   | 78 | 9.34 | 6.52 | YES |
   | 90 | 9.57 | 8.18 | YES |

   The peak crosses; the *shape* doesn't sustain. The `sustained` rule needs a contiguous run of
   `persist` (26–70) samples above `alert_z`; the actual longest runs are 8–21. So this was never a
   "score too low" problem — it's a "score elevated but bursty, not a plateau" problem.

2. **"Mechanism 1 (rate threshold pinned at 0.9)" is not causal.** The 0.9 pin is real but pinned
   identically on *detected* anomalies and on *clean normals* — it does not discriminate misses
   from hits, so it cannot be the cause of the misses. The prior section half-acknowledged this
   ("not solely decisive") but still framed it as fixable Mechanism 1; the contamination-filter fix
   attempt (rejected, see section above) was aimed squarely at this non-causal knob.

3. **The fault is NOT diluted across the window** (a confound I worried about and checked):
   `event_start` sits near the start of each scored window (onset index 144–432 of windows
   586–8929 long), so post-onset statistics ≈ whole-window statistics. Dilution is not the issue.

### The decisive finding — the fused score does not SEPARATE these events from normal operation

Computed contiguous run-length and `frac(fused ≥ bar)` for all 31 Farm C normal events and the 8
misses, at bars z ≥ 6.0 / 6.5 / 7.0. **Normal Farm C operation routinely sustains longer, denser
high-fused excursions than the missed anomalies do:**

- At z ≥ 6.0: normal longest-run max = **36 samples**, normal `frac` max = **0.077**.
- The misses: ev4 run=16/frac=0.018, ev15 run=2, ev35 run=12, ev47 run=16/frac=0.065,
  ev67 run=21/frac=0.025, ev76 run=11, ev78 run=16/frac=0.097, ev90 run=48/frac=0.084.
- **Only ev90 clears the normal envelope on every statistic** (run 48 > 36, frac 0.084 > 0.077 at
  all three bars). ev78 partially separates on `frac`. The other 6 sit *inside* the normal
  envelope on magnitude, fraction, AND run-length.

This is now established from five independent angles (peak magnitude, fraction, run-length,
post-onset concentration, multi-bar), not one. **Conclusion: for 6 of 8 misses, no statistic of the
fused score distinguishes the fault from this farm's normal operation. Therefore no fused-score
rule — no threshold, no burst rule, no rate-window change — can recover them without an equal
false-alarm cost on the indistinguishable normals.** This is the same 1:1 seesaw that sank the
contamination-filter attempt, and it is now explained: it is not bad tuning luck, it is that the
signal genuinely is not there in fused-score space on these events.

### The events are FOUR different situations, not one gap (from the fault descriptions)

The `event_info.csv` descriptions — never consulted in the prior write-up — show the 8 misses are
not a single failure mode and most are not score-rule problems at all:

| Situation | Events | Why the score rules can't / shouldn't fire |
|---|---|---|
| **Sub-cadence / too short** | 35 ("several short standstills, max 8min"), likely 90 ("COMMUNICATION FAULT"), parts of 47 ("2h later back in production") | An 8-minute event at 600s (10-min) SCADA cadence is **< 1 sample**. Not fairly detectable at this cadence — a data/labeling reality, not an ACM defect. |
| **Standstill / availability-domain** | 15 ("longer standstill due to defect pitch encoder"), 35 | A *parked* turbine is the symptom — the availability rule (R4), not score magnitude, owns this. But `status_type_id` shows only scattered non-normal codes (ev35: 226 status-3 samples spread out, consistent with many sub-cadence stops), never a continuous 48h outage, so R4 correctly can't fire. Lowering R4's 48h floor to catch short standstills would fire on routine maintenance stops. |
| **Genuinely indistinguishable in fused-score space** | 4 ("Axis 3 not ready-to-operate"), 67 ("overpressure on main transformer"), 76 ("pitch battery issues"), 15 | Per the separation analysis above: no fused-score statistic separates these from normal Farm C operation. Hard detection-power limit at the feature/detector level, not a rule-layer bug. |
| **Separable but missed by rule shape** | 90 (clearly), 78 (partially) | The ONE/two events where the fused score genuinely exceeds the normal envelope. A rule keyed to "sustained run above a bar that clears the normal envelope with margin" *would* catch ev90 — and it was in fact detected via `+rate` before the kurt/skew fix lowered its fused magnitude. |

### What this means for "the fix" and for the paper

- **There is no single fix, and most of the gap is not fixable at the alarm-rule layer.** A perfect
  rule-shape fix recovers ≈1–2 events (ev90, maybe ev78): recall 19/27 → ~20–21/27 ≈ 0.78, still
  short of the 0.80 KPI. The KPI cannot be reached honestly by rule-layer work alone, because the
  dominant misses are sub-cadence, availability-domain, or genuinely indistinguishable.
- **Recall against CARE Farm C is bounded by the detectability MIX of its labelled events, not just
  by pipeline quality.** Several "anomaly" events are sub-cadence transients, communication faults,
  or short standstills that produce no sustained sensor-correlation anomaly at SCADA cadence. A fair
  evaluation should **categorize events by detectability** rather than treating 27/27 as the
  achievable ceiling. This is the most important correction for the paper: do not present Farm C
  recall as a pure measure of detector quality, and do not chase the indistinguishable events at the
  rule layer (that is precisely how the false-alarm regressions in this session were introduced).
- **If a rule-shape fix is pursued for the genuinely-separable case (ev90-style)**, the corroborating
  signal is "sustained run at a magnitude bar that exceeds the asset's own normal-operation
  envelope with margin" — and it MUST be validated with the full-label discriminator (separate every
  fixable anomaly from every normal, on the complete A+B+C label set) BEFORE coding, plus
  `tests/test_ml.py` 17/17 + two new burst/clean-baseline tests, plus Farm A exact-match, plus FULL
  (not subset) Farm B + Farm C re-validation. This is a production alarm-rule change and per the
  standing rule needs an explicit decision before `core/alarm_rules.py` is touched.

**Files**: no code changes — diagnostic-only re-investigation against saved score CSVs +
`event_info.csv`. The prior "two mechanisms" section is now SUPERSEDED (banner added inline there).

---

## Self-distrust gate SATURATION_FRAC_FLOOR magic-number regression — found and fixed (2026-06-19)
> *Added: 2026-06-19 — user-reported regression: "Why the fuck was threshold fixed at all??? We
> always wanted that calculated properly... Some commit in the last 1-2 days introduced this silent
> regression." Confirmed correct on investigation.*

### The regression

Commit `004c657` (2026-06-17, "Self-distrust gate magnitude-saturation fix" section above)
introduced two new module constants in `core/alarm_rules.py`:
```python
SATURATION_Z = 9.0
SATURATION_FRAC_FLOOR = 0.2
```
`SATURATION_Z` is structurally sound — it's anchored to `core/fuse.py`'s pre-existing,
architecture-wide ±10.0 hard z-clip (`np.clip(z, -10.0, 10.0)`, applies identically to every
detector on every asset), so 9.0 = 90% of a universal, dataset-independent ceiling.

`SATURATION_FRAC_FLOOR = 0.2` was different and wrong: a bare constant with **zero per-asset
derivation**, picked by eyeballing exactly 4 known CARE events (Farm A event 92 false alarm:
near_sat≈0.051; Farm C events 9/47/70 genuine anomalies: near_sat 0.465–1.0) and choosing 0.2 to
separate them. This violates `core/alarm_rules.py`'s own stated design principle, present in its
module docstring and consistently followed by every OTHER threshold in the file: "Every threshold
is derived from the asset's OWN unlabelled history; no labels, no per-site tuning." Every other
rule in the file follows the same idiom — calculate a per-asset baseline, then apply a fixed
SAFETY-margin proportion on top of it (e.g. `rate_thr = clip(base * SAFETY + 0.05, 0.05, 0.9)`,
`thr_h = clip(base_h * SAFETY + 0.05, 0.05, 0.9)`, with `SAFETY=1.5` a pre-existing structural
constant). `SATURATION_FRAC_FLOOR` was the one threshold that skipped the "calculate a baseline"
step entirely and went straight to a fixed number — silently re-introducing dataset-specific tuning
into a system whose entire premise is running unsupervised, with zero per-site/per-dataset tuning.

### Fix (`core/alarm_rules.py`)

Replaced the fixed floor with a calculated one, following the exact same idiom as the rest of the
file:
```python
SATURATION_FLOOR_MIN = 0.05   # additive headroom, same role as the "+ 0.05" in rate_thr/thr_h

def _train_saturation_rate(z_train: Optional[np.ndarray]) -> float:
    """Fraction of THIS asset's own training/calibration z-values that
    already sit at/above the saturation ceiling -- the calculated,
    per-asset baseline the score-side excursion must clear."""
    if z_train is None:
        return 0.0
    zt = np.asarray(z_train, dtype=np.float64)
    zt = zt[np.isfinite(zt)]
    if zt.size == 0:
        return 0.0
    return float(np.mean(zt >= SATURATION_Z))

def _broken_baseline(mask, eval_start, z_values, z_train) -> bool:
    ...
    near_sat = float(np.mean(z_in_mask >= SATURATION_Z))
    base_sat = _train_saturation_rate(z_train)
    floor = float(np.clip(base_sat * SAFETY + SATURATION_FLOOR_MIN, SATURATION_FLOOR_MIN, 1.0))
    return near_sat < floor
```
`_broken_baseline()` now takes the asset's own training-side z-array (`train_fused` for the
sustained/rate rules, each head's own `train` z-array for the per-head rule, already threaded
through `apply_alarm_rules()`'s existing call sites — no upstream signature changes needed since
`core/pipeline.py` already passes `train_fused`/`head_z_train` into `apply_alarm_rules()`). The
floor each asset must clear to be trusted now scales with how often THAT asset's own training data
already sits near the saturation ceiling — exactly the same calculated-baseline-plus-safety-margin
pattern as every other threshold in the file, not a constant tuned against CARE's answer key.

### Validation

1. **17/17 `tests/test_ml.py` pass unchanged.**
2. **Exact reproduction of the 4 events the original 0.2 was tuned against** — Farm A event 92
   stays distrusted, Farm C events 9/47/70 stay un-distrusted, confirmed via direct
   `apply_alarm_rules()` re-invocation against saved score CSVs.
3. **Full OLD-vs-NEW binary-detection diff, Farm A (22 events) + Farm C (58 events), 80 events
   total** — built a reusable comparison script
   (`results/saturation_floor_fix/validation_script.py`, re-evaluates saved score CSVs via
   `apply_alarm_rules()` exactly like `care_benchmark.py`'s own `try_reuse_event()`, so no full
   pipeline re-run was needed since this fix is isolated to the alarm-rule layer) and ran it once
   against the pre-fix code (via `git stash`) and once against the fix:
   - **Zero binary `detected` flips across all 80 events** — every single anomaly/normal
     classification is identical before and after.
   - Exactly **one diagnostic-string-only difference**: Farm C event 30 (a confirmed genuine
     anomaly, "Pitch failure - defect fan on pitch motor") goes from
     `sustained+rate+avail+heads:pca_t2_z,iforest_z(distrusted:heads:ar1_z,pca_spe_z,omr_z)` to
     `sustained+rate+avail+heads:ar1_z,pca_t2_z,iforest_z,omr_z(distrusted:heads:pca_spe_z)` — MORE
     heads correctly firing instead of being wrongly distrusted. `detected=True` under both old and
     new logic (the `sustained`/`rate` rules already fired either way) — a pure diagnostic-quality
     improvement, not a KPI change.
   - **Farm A: recall=1.0 (12/12), false_alarms=1/10 — identical, old and new.**
   - **Farm C: recall=0.704 (19/27), false_alarms=5/31 — identical, old and new.**

   Saved: `results/saturation_floor_fix/{old_logic,new_logic}_farmA_farmC.csv` + `summary.json`
   (gitignored/local, per the repo's established results/ convention — durable record is this
   section).

**Read on why this validation approach was sufficient without a full pipeline re-run**: this fix
is confined entirely to `apply_alarm_rules()`/`_broken_baseline()` — it does not touch detector
fitting, calibration, or fusion. Re-evaluating the alarm-rule layer against already-scored,
already-calibrated CSVs (the same crash-proof-resume pattern `care_benchmark.py` already uses in
`try_reuse_event()`) exercises the exact code path that changed, with the exact same inputs a full
pipeline run would produce. A full Farm A/B/C `score_asset()` re-run would re-verify the detector
layer too, but that layer was untouched by this fix.

**Files changed**: `core/alarm_rules.py` (`SATURATION_FRAC_FLOOR` constant removed, replaced by
`SATURATION_FLOOR_MIN` + new `_train_saturation_rate()` helper; `_broken_baseline()` signature
gains a `z_train` parameter; all three call sites updated to pass each rule's own training-side
z-array). Committed on `claude/research-paper-planning-ests5l`, merged to `main`.

---

## Known Issues (Track as GitHub Issues)
> *Added: 2026-06-16 · Updated: 2026-06-17 (ML issues #61-#67 all fixed)*

These are known deficiencies to be filed as GitHub issues. Use `gh issue create` to create them if not already tracked:

1. **Asset selection not restored after page refresh** — `#eng-asset` dropdown resets to first item on every page load. Should persist selected asset in `localStorage`.

2. **WebSocket reconnect spams the log** — each reconnect attempt logs "Connecting…" which pollutes the log panel with noise during brief network hiccups. Add debounce / silent retry for first N attempts.

3. **Output panel height not restored on cold start** ([#68](https://github.com/bhadkamkar9snehil/ACM/issues/68)) — `localStorage` persistence for panel height exists but may not survive service restarts if the browser reloads the page from scratch. Verify the key name and restore logic.

4. **Detector series always visible** — toggle buttons removed (see above) but all 6 detector series now always render on the Engineer chart. For assets with many detectors this can make the chart noisy. A future approach: legend-click toggle via uPlot's native API.

5. **Admin tab Run Log removed but `/api/assets/{key}/runlog` API still exists** — the endpoint returns per-asset run logs (with `stage`, `level`, `message` columns) that are no longer surfaced anywhere in the UI. Either surface them in the output panel (filter by asset) or deprecate the endpoint.

6. **Excel export sends client-side `outputLines` to server** — the export POSTs the current filtered log array to `/api/service/logs/export`. This means: (a) only what the client has buffered (≤2000 lines) is exported, (b) network cost scales with log size. Alternative: server-side export directly from `shared_lines` deque without client involvement.

7. **`runs` diagnostic JSON not yet surfaced in Engineer tab** ([#69](https://github.com/bhadkamkar9snehil/ACM/issues/69)) — `rules_diagnostic_json`, `calibration_json`, `data_quality_json` are stored in the `runs` table but not yet fetched or displayed in the UI. Future work: add a "Run Details" expandable row in the Engineer tab showing which rules were active, detector weights, and data quality.

**How to file issues from CLI:**
```bash
gh issue create --title "Title" --body "Description" --label "bug"
gh issue create --title "Title" --body "Description" --label "enhancement"
gh issue list --state open
gh issue view 50
```

---

## Standing Rule: Flag Architecture-Violating Suggestions, Don't Suppress Them
> *Added: 2026-06-18*

**When a suggestion (a fix, a design change, a new detector, a config knob) would violate an
established ACM principle — the Issue-First Rule, the config split (`ml_defaults.py` vs.
`config_table.csv`), a documented design decision in CLAUDE.md, a "Mistake Made in Earlier
Sessions" entry, the "no dataset-specific patches" rule, the OPC UA/Simulator boundary, etc. —
still give the suggestion. Do not self-censor a good idea because it conflicts with precedent.**

**But explicitly WARN, inline, before presenting it:** name the specific principle/rule it
conflicts with, and why that rule exists. State it as a researcher flagging a tradeoff, not as a
quiet rule-break. Example phrasing: *"This would work, but it breaks the rule that ML
hyperparameters live only in `ml_defaults.py` (see CLAUDE.md §Config Split) — flagging that before
you decide."*

**The decision to override the rule is the user's, not mine.** If the user says "do it anyway" (or
the rule was already overridden earlier in the session), proceed without re-litigating it. If they
don't address the warning, default to respecting the existing rule rather than silently breaking
it.

**ACM's design is not sacred for its own sake — results are.** The user has explicitly stated:
*"We are READY to break ACM or its principles IF the end goal is achieved demonstrably."* A
principle that's blocking a demonstrably better outcome is a candidate for revision, not a wall.
The warning exists so that tradeoff is visible and chosen deliberately, not so that precedent wins
by default.

**Why this rule exists:** earlier in this same research-paper session, a root-cause fix (OMR
per-feature reliability gating, see "Self-Distrust Gate" and "OMR" sections above and the
now-superseded reliability-gating attempt for issue #72) was implemented and only found to be
ineffective after the fact, via direct empirical measurement. Surfacing architecture tensions
*before* implementation — not after — is cheaper and lets the user weigh in on the tradeoff while
it's still a decision, not a sunk cost.

---

## User Working Style
> *Added: 2026-06-14*

- Expects things to work end-to-end after one command — not "technically correct but incomplete"
- Direct and blunt when something is wrong — correct course immediately, don't justify
- Wants resilient installers: warn on non-critical failures, never abort
- Expects knowledge base to be maintained proactively after every agent report
- "Single UI" is a stated long-term goal for both tools
- Willing to break ACM's own established principles/architecture if it demonstrably achieves the
  end goal — but wants to be warned first when a suggestion crosses one (see "Standing Rule: Flag
  Architecture-Violating Suggestions" above)

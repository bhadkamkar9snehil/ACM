# ACM — Codebase Knowledge Base

> Maintained for future agents. Update this file whenever you learn something new about the codebase.

---

## Architecture Overview

ACM is a stateless, self-tuning anomaly scoring service for industrial assets. Three layers:

```
Data sources  →  SQLite buffer / parquet cache  →  Pipeline workers  →  SQL store  →  FastAPI UI
```

- **Source layer** (`scripts/acm_feed.py`): per-asset `source_kind` dispatch (csv / table / query / opcua / mqtt)
- **Cache layer**: one parquet file per asset, trailing window (default 180 days), atomic write (`os.replace`)
- **Pipeline** (`core/pipeline.py`): stateless re-fit on every tick — AR1, PCA-SPE, PCA-T2, IForest, GMM, OMR detectors → correlation-discounted fusion → self-tuned alarm rules
- **Store** (`scripts/acm_store.py`): SQLite (default) or SQL Server, same schema, qmark params on both
- **Service** (`scripts/acm_service.py`): FastAPI + asyncio scheduler, ProcessPoolExecutor for scoring workers

---

## Key Files

| File | Role |
|---|---|
| `core/pipeline.py` | `score_asset()` — the entire ML pipeline, stateless, takes DataFrames in, returns scored result |
| `core/alarm_rules.py` | R1 sustained / R2 24h rate / R3 per-head 7d / R4 availability / self-distrust gate |
| `core/fast_features.py` | Rolling features via Polars (float32) |
| `core/fuse.py` | Correlation-discounted Z-score fusion |
| `core/ml_defaults.py` | All ML hyper-parameters — edit here, not config_table.csv |
| `scripts/acm_service.py` | FastAPI service + async tick scheduler; starts OPC UA / MQTT bridges on-demand |
| `scripts/acm_feed.py` | `load_increment()`, `update_cache()`, `readiness()`, `frame_sensors()` |
| `scripts/acm_store.py` | `Store` class (sqlite/mssql), DDL, `ingest_result()`, `sync_config()` |
| `scripts/acm_opcua_bridge.py` | Asyncio singleton polling OPC UA → `data_cache/opcua_buffer.db` |
| `scripts/acm_mqtt_bridge.py` | Thread singleton subscribing MQTT → `data_cache/mqtt_buffer.db` |
| `scripts/acm_feed.py` | `_load_opcua_increment()` / `_load_mqtt_increment()` read from those SQLite buffers |
| `scripts/acm_seed_demo.py` | Idempotent seeder — INSERT OR IGNORE CARE CSVs + OPC UA endpoint into monitored_assets |
| `scripts/acm_run.py` | Batch CLI scorer — CSV/SQL → parquet cache → score → store |
| `scripts/download_care_dataset.py` | Partial Zenodo zip download via `remotezip`; `--count N` limits events per farm |
| `scripts/care_benchmark.py` | CARE wind-farm benchmark against ground-truth labels |
| `configs/config_table.csv` | Human-editable runtime config (151 rows). Categories: data, sql, runtime. ML params must NOT go here. |
| `setup_acm.ps1` | One-command Windows installer + updater |

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

**Important:** ACM must support all source kinds with per-asset flexibility. OPC UA is NOT a preferred source — it is the integration bridge to the Simulator. Do not special-case it in the UI or docs.

---

## Simulator ↔ ACM Integration

**Hard constraint: Simulator has zero knowledge of ACM.** All integration code lives in ACM only.

**How it works:**
1. Simulator publishes OPC UA at `opc.tcp://localhost:4840/simulator`, namespace `http://local/industrial-tag-simulator`, root folder `TagSimulator` under Objects
2. `acm_opcua_bridge.py` polls every 1 s, writes `{published_at, tag1: v1, ...}` rows to `data_cache/opcua_buffer.db`
3. The bridge runs as `asyncio.create_task` inside the service event loop — never in worker processes
4. `acm_feed._load_opcua_increment()` reads from that SQLite file (same pattern as CSV)
5. Worker processes only read SQLite, never touch the OPC UA connection — decouples asyncio from ProcessPoolExecutor

**Seed the asset once:**
```bash
python scripts/acm_seed_demo.py --opcua opc.tcp://localhost:4840/simulator --db acm_results.db
```
This inserts `asset_key="simulator/opc_ua"` with `source_kind="opcua"` — idempotent, safe to re-run.

**MQTT is secondary:** same SQLite buffer pattern, `data_cache/mqtt_buffer.db`, topic `industrial-tag-simulator/flat`.

---

## SQLite Buffer Pattern

Used by both OPC UA and MQTT bridges to decouple async/threaded network I/O from ProcessPoolExecutor workers:

```
Bridge (asyncio task / daemon thread)
    ↓  writes rows
opcua_buffer.db / mqtt_buffer.db
    ↑  reads via load_increment()
Scoring worker (ProcessPoolExecutor, separate process)
```

Schema: `(ts TEXT NOT NULL, payload_json TEXT NOT NULL)` + index on `ts`.

---

## Store: `scripts/acm_store.py`

```python
store = Store("sqlite", db="acm_results.db")   # or Store("mssql", conn_str="...")
store.execute(sql, params)   # qmark params, works on both backends
store.fetch(sql, params)     # returns list[dict]
store.commit()
```

The `monitored_assets` table schema:
```sql
asset_key TEXT PRIMARY KEY, grp TEXT DEFAULT 'fleet', enabled INTEGER DEFAULT 1,
source_kind TEXT, source_ref TEXT, conn_ref TEXT,
timestamp_col TEXT, status_col TEXT, added_at TEXT, retired_at TEXT,
state TEXT DEFAULT 'NEW', state_detail TEXT,
last_run_at TEXT, last_score_ts TEXT, last_runtime_s REAL
```

INSERT pattern (used in `acm_service.py` onboard handler and `acm_seed_demo.py`):
```python
"INSERT OR IGNORE INTO monitored_assets "
"(asset_key, grp, enabled, source_kind, source_ref, conn_ref, "
"timestamp_col, status_col, added_at, state) "
"VALUES (?,?,?,?,?,?,?,?,?,?)"
```

---

## Test Suite

68 tests across 4 files. Run with `python -m pytest tests/`.

| File | Count | What it tests |
|---|---|---|
| `test_ml.py` | 16 | ML correctness, detector sensitivity, alarm rules — all in-memory synthetic data |
| `test_service.py` | 10 | Feed/cache behavior, readiness gate, scheduler ticks, API lifecycle |
| `test_store.py` | 6 | SQL round-trips, views, config sync, end-to-end runner (1 marked slow) |
| `test_performance.py` | 36 | SQL view correctness, cache fast-path, TTLCache semantics (3 marked slow) |

**Slow marker:** `@pytest.mark.slow` is on 4 tests — 1 subprocess end-to-end ML run (600s timeout) and 3 sleep-based TTL tests. The setup script excludes them with `-m "not slow"`.

**Self-test in setup_acm.ps1 is non-fatal.** Test failures show a yellow warning but do not abort the install — packages installed + imports verified = working install.

---

## Setup Script (`setup_acm.ps1`)

Single command: `irm https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup_acm.ps1 | iex`

Flow:
1. Prerequisites: Git, Python 3.11+
2. Install: clone/update, pip packages (including `asyncua`, `paho-mqtt`), verify imports
3. Self-test: 64 fast tests, non-fatal warning if any fail
4. Backend detection: SQL Server via pyodbc, falls back to SQLite
5. **[1/2] Optional: Simulator** — clone to `$HOME\Simulator`, run `ensure-env`, register `simulator/opc_ua` asset
6. **[2/2] Optional: CARE demo** — download 3 events (~30 MB Farm A), register as `care_demo` assets
7. Summary + context-aware next steps

**Key constraint:** `asyncua` and `paho-mqtt` MUST be in the pip install step or OPC UA/MQTT will silently fail at runtime (the bridges catch `ImportError` gracefully but won't work).

---

## CARE-to-Compare Dataset

- Zenodo URL: `https://zenodo.org/records/15846963/files/CARE_To_Compare.zip?download=1`
- Farm A: 22 events × ~36 MB, 86 features, CSV per event
- Columns: `time_stamp`, `status_type_id`, sensor columns, `train_test`
- Download: `python scripts/download_care_dataset.py --dest care_data --farms A --count 3`
- Seed: `python scripts/acm_seed_demo.py --care-dir care_data --db acm_results.db`
- Asset key pattern: `care/{farm_letter}/{csv_stem}` e.g. `care/A/40`
- Group: `care_demo`

---

## Config Split (enforced)

- **Human config** (`configs/config_table.csv`, synced to `config` table): data, sql, runtime categories only
- **ML params** (`core/ml_defaults.py`): models, thresholds, fusion, regimes — never in config_table.csv
- Test `test_store.py::TestConfigSync` enforces this split and will fail if ML categories appear in config_table.csv

---

## Windows Compatibility Notes

- **Asyncio:** Always use `asyncio.run(coro)` to drive coroutines in tests — never `asyncio.get_event_loop().run_until_complete()`. On Windows (Python 3.8+), the default `ProactorEventLoop` has stricter lifecycle management; `get_event_loop()` can return a closed or missing loop after `TestClient` has consumed it. `asyncio.run()` always creates a fresh loop. Correct pattern already used in `test_service.py` lines 171, 188, 222.
- **Paths:** Always use `pathlib.Path` or `os.path.join` — never hardcode `/` separators.
- **Subprocess:** Pass arguments as a list with `sys.executable` as the first element — never rely on `.py` files being executable directly.

---

## Key Patterns to Preserve

- **Atomic parquet write:** always `df.to_parquet(tmp)` then `os.replace(tmp, path)` — crash-safe
- **Column-pruning for `since`:** `_read_ts_column()` reads only the timestamp column via PyArrow to avoid loading all sensor columns just to find the max timestamp
- **Adaptive score window:** `score_eff = min(score_days, max(1.0, span_days / 3.0))` — prevents young assets from starving the train side
- **ProcessPool pickling:** `score_cached()` takes plain strings/dicts, returns plain dicts — no unpicklable objects cross process boundaries
- **Bridges are parent-process only:** OPC UA and MQTT bridges are started in the service (asyncio task / daemon thread). Worker processes only read SQLite.

---

## Development Branch

Active development branch: `claude/upbeat-hopper-m39epw` (both repos). Merge to `main` after each task.

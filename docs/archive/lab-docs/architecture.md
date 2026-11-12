# Architecture

## Overview

```
Data sources  →  Parquet cache  →  ML pipeline  →  SQLite store  →  FastAPI / UI
```

ACM has three layers:

1. **Source layer** — per-asset `source_kind` dispatch reads incremental data from CSV files, SQL tables, OPC UA servers, or MQTT brokers
2. **Cache layer** — one Parquet file per asset, trailing 180-day window, atomically updated
3. **Pipeline layer** — stateless re-fit on every tick: AR1, PCA-SPE, PCA-T2, IsolationForest, GMM, OMR (Overall Model Residual — a multivariate reconstruction detector, see `core/omr.py`) → correlation-discounted fusion → self-tuned alarm rules

---

## Data source kinds

| source_kind | What it connects to | timestamp column |
|---|---|---|
| `csv` | A CSV file on disk | `time_stamp` (auto-detected) |
| `table` | SQL table via pyodbc | `time_stamp` |
| `query` | Arbitrary SQL SELECT via pyodbc | `time_stamp` |
| `opcua` | OPC UA endpoint | `published_at` |
| `mqtt` | MQTT broker topic | `published_at` |

---

## Scoring pipeline

For each ready asset on every tick:

```
load_increment()        ← read new rows from source since last run
update_cache()          ← append to parquet, trim to 180 days, atomic write
readiness()             ← MATURING / STALE / READY
score_cached()          ← in worker process:
  adaptive train/score split (score window = min(30d, span/3, but ≥5% of span))
  frame_sensors()       ← normalise columns, drop non-numeric
  score_asset()         ← 6 detectors → fused Z-score
ingest_result()         ← write scores + alarms to SQLite
```

### Asset states

| State | Meaning |
|---|---|
| `NEW` | Just registered, never processed |
| `MATURING` | Not enough history yet (< 14 days by default) |
| `READY` | Has history, eligible to score |
| `OK` | Scored, no alarm |
| `WARN` | Fused Z-score elevated but below alarm threshold |
| `ALARM` | One or more alarm rules fired |
| `ERROR` | Scoring failed (see Diagnosis column for details) |
| `STALE` | No new data for > 24 hours |

### Alarm rules

| Rule | Trigger |
|---|---|
| R1 Sustained | Fused Z ≥ threshold for N consecutive hours |
| R2 Rate | Fused Z increased by X in 24 hours |
| R3 Per-head 7d | Individual detector Z elevated over 7-day window |
| R4 Availability | Data gaps > threshold |

All four rule horizons are defined in seconds and converted to sample counts from the asset's own
inferred cadence (median timestamp diff) — never hardcoded sample counts, so the same config works
across 1-second, 10-minute, or 1-hour historians without retuning.

**Self-distrust gate:** a fifth, cross-cutting check that discards R1/R2/R3's output (not R4 —
availability is exempt, a failed asset legitimately IS down most of the window) if the rule claims
alarm for more than `distrust_coverage` (default 50%) of the scored window AND the first alarm
falls within the rule's first 5% of evaluable samples — i.e. no quiet prefix. A genuine fault has
an onset; a drifted/corrupted baseline alarms from the start. `distrust_coverage` is configurable
via `cfg["alarm_rules"]["distrust_coverage"]` (see `core/alarm_rules.py: apply_alarm_rules()`),
primarily for ablation experiments.

---

## Worker pool

- `ProcessPoolExecutor` sized to `os.cpu_count()` (persistent, not per-tick)
- Workers are stateless: they read Parquet, compute scores, return plain dicts
- OPC UA and MQTT bridges live in the parent process only (never in workers)

---

## OPC UA / Simulator integration

The Simulator publishes an OPC UA server at `opc.tcp://localhost:4840/simulator`.
ACM's bridge polls it every second and writes rows to `data_cache/opcua_buffer.db`.
Workers read that SQLite file — zero direct OPC UA dependency in worker processes.

```
Simulator OPC UA → acm_opcua_bridge (asyncio, parent process)
                 → data_cache/opcua_buffer.db
                 → score_cached() reads it like any other CSV
```

---

## Key files

| File | Role |
|---|---|
| `core/pipeline.py` | `score_asset()` — entire ML pipeline |
| `core/omr.py` | OMR (Overall Model Residual) detector — multivariate reconstruction, top-3 residual scoring |
| `core/alarm_rules.py` | Alarm rule engine + self-distrust gate |
| `core/fuse.py` | Calibration (contamination filter) + correlation-discounted fusion |
| `scripts/acm_service.py` | FastAPI + async scheduler + worker pool |
| `scripts/acm_feed.py` | Per-source data loading + cache management |
| `scripts/acm_store.py` | SQLite / SQL Server abstraction |
| `scripts/acm_opcua_bridge.py` | OPC UA → SQLite bridge |
| `scripts/acm_mqtt_bridge.py` | MQTT → SQLite bridge |
| `scripts/care_benchmark.py` | CARE-to-Compare evaluation harness; `--override` JSON flag for ablation experiments |
| `scripts/download_care_benchmark.py` | Downloads CARE dataset preserving `event_info.csv` + `datasets/` layout for `care_benchmark.py` |
| `configs/config_table.csv` | Human-editable runtime config |
| `core/ml_defaults.py` | All ML hyperparameters (never in config CSV) |

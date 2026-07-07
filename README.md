# ACM - Asset Condition Monitor

ACM watches industrial assets and tells you when something is wrong - **with no labels, no training-data preparation, and no human tuning**. Point it at any asset's raw sensor history (CSV, SQL, OPC UA, or MQTT): it learns what normal looks like from the first tick, sets its own alarm thresholds, names the sensors driving every alarm, and retains everything in SQLite or SQL Server.

---

## ACM2 (the successor - active development)

The `acm2/` package is the ground-up successor built on lifetime memory,
conditional surprise scoring, and anytime-valid e-process detection with a
mathematically guaranteed false-alarm budget (one dial: alpha per
asset-year). Design: `docs/acm-gem-plan.md`; build guide:
`docs/acm2-implementation-plan.md`; factory: `docs/acm2-factory.md`.

```bash
cd acm2
./install.sh          # or: .\install.ps1 on Windows (installs uv, syncs, self-tests)
# manual equivalent:
uv sync                                   # environment (lockfile committed)
uv run pytest tests                       # full suite incl. statistical lane
uv run python -m acm2.service --root ../acm2_data --port 8899 --tick-seconds 300
# self-ticking fleet service + UI: open http://127.0.0.1:8899
```

Evidence lane (CARE replays through the production runtime path; results
are gitignored regression evidence, never tuning):

```bash
cd acm2
uv run python -m acm2.evidence.care_replay \
    --farm-dir "../care_data/Wind Farm A" --events 40 68 \
    --out ../results/acm2_care_A
# omit --events to replay every event in the farm's event_info.csv;
# --chunk-rows 288 (default) = one tick per 2 days at 10-min cadence
```

API: `GET /api/assets`, `GET /api/asset/{key}`, `GET /api/narrative/{key}`,
`POST /api/tick`, `GET /api/immune/{key}`, `POST /api/immune-pass/{key}`.
Verdicts: healthy | insufficient-history | watch | alarm | escalating
(with self-gated failure-time horizon) | change-not-fault. Every verdict
carries confidence, evidence trail, attribution, model epoch, and a
falsifiability statement. ACM2 never imports the legacy pipeline
(CI-enforced); the sections below describe legacy ACM.

---

## Quick Start

### Windows

```powershell
irm https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup_acm.ps1 | iex
```

### Linux / macOS

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup.sh)
```

Both scripts are interactive and handle everything automatically:

| Automatic | Optional prompts |
|---|---|
| Git + Python 3.11+ (Windows only - auto-installs via winget or direct installer) | **[1/1] CARE demo data** - download 10 real wind-turbine SCADA events (~360 MB) so ACM can score them immediately |
| Clone ACM to `~/ACM` | |
| Install all Python dependencies | |
| Create runtime directories | |
| Detect SQL Server (falls back to SQLite) | |
| Verify all imports, run self-test | |

After setup:

```bash
# Start the service
python scripts/acm_service.py
# Open http://localhost:8765  ->  Admin  ->  Onboard assets
```

### Updating

Run the same one-liner again. The script detects your existing clone, pulls the latest, and upgrades dependencies. Your local databases (`acm_results.db`) are Git-ignored and are never touched.

---

## ML Pipeline

ACM scores every asset statelessly on every tick using six independent detectors, all calibrated out-of-sample, fused with correlation discounting, and routed through cadence-aware alarm rules.

```mermaid
flowchart LR
    HIST[("CSV / SQL /<br/>OPC UA / MQTT")] -->|"new rows only"| CACHE["raw cache<br/>(trailing window,<br/>parquet per asset)"]
    CACHE --> GATE{"readiness"}
    GATE -->|MATURING / STALE| BOARD
    GATE -->|READY| SCORE["stateless re-learn + score<br/>(parallel workers)"]
    SCORE --> STORE[("SQLite /<br/>SQL Server")]
    STORE --> BOARD["control panel<br/>Operator * Engineer * Admin * Simulate"]
    BOARD -->|"run-now * pause * tick<br/>onboard * config * ack"| SVC["scheduler"]
    SVC -->|"every tick"| CACHE
```

### Detectors

```mermaid
flowchart LR
    subgraph pipeline [core.pipeline.score_asset]
        CR["channel roles"] --> FE["rolling features\n(Polars, float32)"]
        FE --> SPLIT["interleaved 80/20 split"]
        SPLIT --> DET["AR1 * PCA-SPE * PCA-T2\nIForest * GMM * OMR"]
        DET --> CAL["MAD/median calibration\n(out-of-sample)"]
        CAL --> FUS["correlation-discounted\nfusion"]
    end
    FUS --> R1[R1 sustained]
    FUS --> R2[R2 24h rate]
    FUS --> R3[R3 per-head 7d]
    ST["operating status"] --> R4[R4 availability]
    R1 & R2 & R3 & R4 --> DG["self-distrust gate"]
    DG --> SQL[("SQL store")]
```

| Detector | What it catches |
|---|---|
| **AR1** | Slow drift - residuals from an auto-regressive fit on each sensor |
| **PCA-SPE** | Structural novelty - reconstruction error across all sensors |
| **PCA-T2** | Regime shift - Hotelling's T2 in the principal component space |
| **IForest** | Transient spikes and outlier clusters |
| **GMM** | Mode changes - low-likelihood under the learned operating envelope |
| **OMR** | Per-sensor residuals - isolates which channel is misbehaving |

### Alarm Rules

ACM doesn't alert on every spike. The fused score is routed through four cadence-aware rules:

1. **R1 - Sustained anomaly**: score persistently high for a continuous duration (filters transient noise)
2. **R2 - 24-hour rate**: abnormal density of short-lived anomalies in a rolling 24-hour window
3. **R3 - Per-head 7-day rate**: one detector repeatedly firing over seven days (chronic degradation)
4. **R4 - Availability**: asset offline or silent for >= 48 hours
5. **Self-distrust gate**: fleet-wide simultaneous anomaly -> likely sensor-grid issue, suppress false alarms

All thresholds are self-tuned from the history. No human configuration required.

### Fused score versus alarm

`fused >= alert_z` means ACM's detector stack found anomaly evidence at that timestamp. It is the model saying "this point looks abnormal relative to this asset's learned history." `alarm = 1` is a stricter operational decision: the high fused evidence must also satisfy ACM's alarm rules, such as sustained duration, 24-hour abnormal-rate, 7-day per-detector/head rate, availability, and self-distrust gating.

Use both signals when diagnosing ACM:

| Signal | Meaning | Inference |
|---|---|---|
| Fused crosses `alert_z`, no alarm | Detectors saw abnormal evidence, but the decision layer did not promote it | Investigate alarm-rule shape, cadence normalization, persistence/rate windows, episode construction, or suppression gates |
| Fused stays below `alert_z`, no alarm | Detectors did not separate the event from learned normal behavior | Investigate features, calibration, detector sensitivity, data quality, or whether the label maps to sensor behavior |
| Alarm overlaps known event | ACM produced an actionable detection | Measure lag, duration, peak, and whether the alarm is specific or too broad |
| Alarm outside known event | ACM found abnormal behavior not covered by labels, or produced a false alarm | Inspect raw timeline before calling it false positive |

For public validation datasets, this distinction matters. In the event-aligned benchmark run, alarm recall was lower than fused-threshold indication: SMD had 89 alarm hits out of 136 labelled events, but 133/136 events crossed `alert_z`; BATADAL had 4 alarm hits out of 12 events, but 10/12 crossed `alert_z`; MetroPT-3 had 3 alarm hits out of 4 events, but all 4 crossed `alert_z`. That means many misses are not detector blindness. They are decision-layer misses where ACM saw the event but did not convert it into an operational alarm.

---

## Simulator Guide

ACM includes an embedded, in-process industrial data simulator. No external services are needed. The **Simulate** tab and the backend integrate seamlessly.

### 1. Generate Synthetic Data
- Go to the **Simulate > Generate** tab.
- Select from 11 domain generators (rotary equipment, petroleum pipeline, gas pipeline, power plant, and six steel-plant process units).
- Each generator produces a labeled CSV with realistic fault signatures (e.g. `fault_rotary_bearing.csv`).
- The generated CSVs are automatically placed in `sim_data/generated/`.

### 2. Replay Files Live
You can stream any CSV file into ACM line-by-line exactly as if it were a live MQTT or OPC UA feed:
- Go to the **Simulate > Files** tab.
- Click on any file (e.g., the downloaded CARE datasets or the generated fault datasets).
- A preview of the columns will load. Click the **Replay** button.
- Choose your replay speed and start the simulation. 
- The data is written to an internal buffer (`data_cache/mqtt_buffer.db`).

### 3. View Live Simulated Data
To watch the anomaly scores update live as your replay runs:
- Go to the **Reliability Engineer** tab.
- From the asset dropdown, select the `simulator/internal` asset (which listens to the replay buffer).
- Watch the Fused Anomaly Score and 6-detector heatmap update in real-time as the simulator pumps data in!

---

## Fault Datasets

Ten pre-generated CSVs in `sim_data/sample/` with known fault signatures:

| File | Domain | Scenario | Fault onset |
|---|---|---|---|
| `fault_rotary_bearing.csv` | Rotary equipment | Bearing fault | 40% mark |
| `fault_rotary_imbalance.csv` | Rotary equipment | Rotor imbalance | 40% mark |
| `fault_pipeline_small_leak.csv` | Petroleum pipeline | Small leak | 40% mark |
| `fault_pipeline_large_leak.csv` | Petroleum pipeline | Large leak | 40% mark |
| `fault_pipeline_pump_trip.csv` | Petroleum pipeline | Pump trip | 40% mark |
| `fault_pipeline_sensor_drift.csv` | Petroleum pipeline | Sensor drift | 40% mark |
| `fault_power_tube_leak.csv` | Power plant | Tube leak | 40% mark |
| `fault_power_condenser_fouling.csv` | Power plant | Condenser fouling | 40% mark |
| `fault_gas_compressor_trip.csv` | Gas pipeline | Compressor trip | 40% mark |
| `fault_gas_leak.csv` | Gas pipeline | Gas leak | 40% mark |

Each file has a `state` column: `NORMAL` for the first 40% of rows, then the fault label - making ground-truth evaluation trivial.

Regenerate at any time: `python scripts/generate_fault_dataset.py`

---

## CLI Usage

### Batch scoring

```bash
# Score one CSV, produce an HTML report
python scripts/acm_run.py --csv pump7.csv --timestamp-col time --score-days 30 --report pump7.html

# Score a fleet of CSVs in parallel
python scripts/acm_run.py --csv data/*.csv --score-days 30 --workers 4 --db acm_results.db --report fleet.html
```

### Generate a standalone HTML report

```bash
python scripts/acm_report.py --db acm_results.db --assets PUMP7 --out pump7.html
python scripts/acm_report.py --db acm_results.db --list
```

### CARE wind-farm benchmark

`care_benchmark.py` needs each farm's `event_info.csv` + `datasets/{id}.csv` structure - use
`download_care_benchmark.py` for this (not `download_care_dataset.py`, which flattens files for
the Simulate tab and has no `event_info.csv`):

```bash
# Download Farm A in the structure care_benchmark.py expects
python scripts/download_care_benchmark.py --dest care_data --farms A

# Run the benchmark against ground-truth labels
python scripts/care_benchmark.py --data-dir "care_data/Wind Farm A" --out results/A --workers 2
```

KPI: **PASS** requires event-level recall >= 0.80 and F1 >= 0.75. Output: `results/A/summary.json`
(recall, precision, F1, false alarms) plus per-event score/diagnostic CSVs.


### Public validation datasets

`scripts/download_validation_datasets.py` downloads and adapts public validation datasets into
ordinary ACM CSV inputs: one `timestamp` column plus numeric channels. Labels and event windows are
kept outside the model input as `labels*.csv` and `known_events.csv`.

Before adding or recommending any new public dataset, check ACM fit first. A valid benchmark needs at least 14 days of mature baseline before the first scored event, labelled events that occur after that baseline, enough rows after feature construction for calibration, and continuous multivariate telemetry rather than isolated tabular snapshots. Datasets that fail this gate can still be adapter tests or stress tests, but they are not evidence that ACM's ML failed.

Use the repeatable investigation harness for this gate and for per-dataset root-cause evidence:

```bash
python scripts/public_dataset_benchmark.py --datasets all --workers 2 --force --out results/public_dataset_benchmark
```

```bash
python scripts/download_validation_datasets.py --dataset metropt3
python scripts/download_validation_datasets.py --dataset batadal
python scripts/download_validation_datasets.py --dataset smd --max-assets 10
python scripts/download_validation_datasets.py --dataset secom
python scripts/download_validation_datasets.py --dataset ai4i
python scripts/download_validation_datasets.py --dataset cmapss --max-assets 10
python scripts/download_validation_datasets.py --dataset milling
python scripts/download_validation_datasets.py --dataset bearing --max-assets 3
python scripts/download_validation_datasets.py --dataset tep
```

Run adapted datasets through ACM with `acm_run.py` exactly like any other CSV:

```bash
python scripts/acm_run.py --csv data/public_datasets/adapted/metropt3/asset_metropt3.csv   --timestamp-col timestamp --score-days 30 --db results/public_dataset_smoke/metropt3.db   --report results/public_dataset_smoke/metropt3.html

python scripts/acm_run.py --csv data/public_datasets/adapted/smd/asset_smd_*.csv   --timestamp-col timestamp --score-days 7 --workers 2   --db results/public_dataset_smoke/smd.db --report results/public_dataset_smoke/smd.html
```

When matching `known_events.csv` files exist, `acm_report.py` now adds a **Validation Evidence**
section automatically: known events in the scored window, hits, misses, event recall, alarm episode
hours, and per-asset event match tables. Labels are not fed into scoring.

Current public-dataset smoke results from `results/public_dataset_smoke/`:

| Dataset | Known events in scored window | Hit | Missed | Event recall | Interpretation |
|---|---:|---:|---:|---:|---|
| MetroPT-3 | 0 | 0 | 0 | N/A | Inconclusive: ACM alarmed in Aug-Sep, but known failures are Apr-Jul. |
| BATADAL | 1 | 0 | 1 | 0.0% | Missed the scored attack window. |
| SMD sample (10 machines) | 74 | 28 | 46 | 37.8% | Best current cross-domain signal, but alarm episodes are broad and recall is uneven. |
| SECOM | 9 | 0 | 9 | 0.0% | Poor fit for current ACM shape; likely needs a batch-process adapter or should remain a stress dataset. |

Pending states: AI4I, C-MAPSS, and Milling are adapted but not yet represented by completed smoke
reports; Bearing raw data downloaded but the adapter currently emits no asset CSVs; TEP raw `.RData`
files download successfully but still need R/RData conversion before ACM scoring.


### Ablation Testing

Every detector and pipeline component (contamination filtering, the self-distrust gate, fusion
auto-tuning) can be switched off **with no source code changes**, to measure exactly what it
contributes to detection accuracy. `care_benchmark.py --override` takes a JSON string that's
deep-merged onto `core/ml_defaults.py`'s defaults at runtime - the same mechanism used internally
to validate every architectural decision in this codebase: run the labelled benchmark with and
without a component, diff the resulting `summary.json`.

| Disable... | `--override` JSON |
|---|---|
| AR1 detector | `{"models": {"ar1": {"enabled": false}}}` |
| PCA (drops both SPE and T2 scores) | `{"models": {"pca": {"enabled": false}}}` |
| Isolation Forest | `{"models": {"iforest": {"enabled": false}}}` |
| GMM | `{"models": {"gmm": {"enabled": false}}}` |
| OMR | `{"models": {"omr": {"enabled": false}}}` |
| Contamination-aware calibration filter | `{"thresholds": {"contamination_filter": {"enabled": false}}}` |
| Sustained alarm rule | `{"alarm_rules": {"sustained": {"enabled": false}}}` |
| 24-hour rate alarm rule | `{"alarm_rules": {"rate": {"enabled": false}}}` |
| Per-head 7-day alarm rule | `{"alarm_rules": {"per_head": {"enabled": false}}}` |
| Availability alarm rule | `{"alarm_rules": {"availability": {"enabled": false}}}` |
| Self-distrust gate (broken-baseline discard) | `{"alarm_rules": {"self_distrust": {"enabled": false}}}` |
| Fusion auto-tuning | `{"fusion": {"auto_tune": {"enabled": false}}}` |
| Equal detector weights, no auto-tune | `{"fusion": {"auto_tune": {"enabled": false}, "weights": {"ar1_z": 0.1667, "pca_spe_z": 0.1667, "pca_t2_z": 0.1667, "iforest_z": 0.1667, "gmm_z": 0.1667, "omr_z": 0.1667}}}` |

Combine any rows by merging their JSON objects into one override - e.g. disable OMR and the
contamination filter together in a single run. Rule switches are diagnostic ablations; production defaults
leave every rule enabled.

**Windows (PowerShell)** - single-quoted strings are literal here too, so the JSON needs no
escaping; use a trailing backtick for line continuation:

```powershell
# 1. Baseline - always run first, every ablation below is compared against this
python scripts\care_benchmark.py --data-dir "care_data\Wind Farm A" --out results\full --workers 2

# 2. Disable one component at a time (run sequentially, not in parallel - see note below)
python scripts\care_benchmark.py --data-dir "care_data\Wind Farm A" --out results\no_omr --workers 2 `
  --override '{"models": {"omr": {"enabled": false}}}'

python scripts\care_benchmark.py --data-dir "care_data\Wind Farm A" --out results\no_distrust --workers 2 `
  --override '{"alarm_rules": {"self_distrust": {"enabled": false}}}'

python scripts\care_benchmark.py --data-dir "care_data\Wind Farm A" --out results\equal_weights --workers 2 `
  --override '{"fusion": {"auto_tune": {"enabled": false}, "weights": {"ar1_z": 0.1667, "pca_spe_z": 0.1667, "pca_t2_z": 0.1667, "iforest_z": 0.1667, "gmm_z": 0.1667, "omr_z": 0.1667}}}'

# 3. Compare
Get-ChildItem results -Directory | ForEach-Object {
    Write-Host "== $($_.Name) =="
    Get-Content "$($_.FullName)\summary.json"
}
```

Linux/macOS: identical flags and JSON, `/` paths, `\` instead of the backtick for line
continuation.

`--override` implies `--force` - a cached score from a different configuration is never reused.
Run ablation configs **sequentially**: each spawns its own `--workers` pool, and concurrent runs
multiply total worker/memory usage. Farm A (22 events) is fast enough for quick iteration;
Farm B/C are larger and better for confirming an effect holds at scale.

### Ablation testing on any CSV (not just CARE)

`scripts/acm_run.py` takes the same `--override` flag, so ablation isn't tied to the CARE
benchmark - it works on any CSV/SQL source `acm_run.py` already accepts:

```bash
python scripts/acm_run.py --csv pump7.csv --timestamp-col time_stamp \
  --override '{"models": {"omr": {"enabled": false}}}' \
  --report pump7_no_omr.html --db acm_results.db
```

The override is carried all the way into the HTML report: any asset scored with `--override`
shows an **"Ablation Override"** box (same place as the Data Quality / Calibration boxes) listing
exactly which `ml_defaults` keys were patched for that run, and the "Scoring Operations" history
table shows it per-run too. Runs without `--override` show no such box - there's nothing to
distinguish a normal run from an ablation run except this label, by design, so you can mix
baseline and ablation runs in the same report/database and still tell them apart later. See
`docs/report-flow-testing.md` for the full report-flow walkthrough.

**Comparing several configs side-by-side in one report - give each one its own `--asset` key.**
`acm_run.py` ingests with `keep_history=False` (it's a one-shot batch runner, not the live
service - see `scripts/acm_store.py`'s `ingest_result()`): every invocation **replaces** that
asset's previous `runs`/`scores` rows in the database. Re-running the same `--asset` key with a
different `--override` does not accumulate a history - only the latest run survives. To compare a
baseline against several ablations (e.g. each detector on/off, or each detector run alone) in a
single report, give every config its own `--asset` key against the same CSV and `--db`:

```bash
python scripts/acm_run.py --csv pump7.csv --timestamp-col time_stamp --asset pump7_baseline --db acm_results.db

python scripts/acm_run.py --csv pump7.csv --timestamp-col time_stamp --asset pump7_no_ar1 --db acm_results.db \
  --override '{"models": {"ar1": {"enabled": false}}}'

python scripts/acm_run.py --csv pump7.csv --timestamp-col time_stamp --asset pump7_only_omr --db acm_results.db \
  --override '{"models": {"ar1": {"enabled": false}, "pca": {"enabled": false}, "iforest": {"enabled": false}, "gmm": {"enabled": false}}}'

python scripts/acm_report.py --db acm_results.db --assets pump7 --out pump7_ablation_report.html
```

`--assets pump7` substring-matches every `pump7_*` key, so all configs land in one report, each
showing its own Ablation Override box (baseline has none - that's the visual tell).

---

## Repository Map

```
ACM/
+-- core/
|   +-- pipeline.py          score_asset() - full ML pipeline, stateless, DataFrames in -> result out
|   +-- alarm_rules.py       R1/R2/R3/R4 cadence-aware rules + self-distrust gate
|   +-- fast_features.py     rolling features via Polars (float32)
|   +-- fuse.py              correlation-discounted Z-score fusion + ScoreCalibrator
|   `-- ml_defaults.py       all hyperparameters - edit here, never in config_table.csv
|
+-- scripts/
|   +-- acm_service.py       FastAPI service + asyncio tick scheduler
|   +-- acm_feed.py          load_increment(), update_cache(), readiness(), frame_sensors()
|   +-- acm_store.py         Store class (sqlite/mssql), DDL, ingest_result(), sync_config()
|   +-- acm_run.py           batch CLI scorer - CSV/SQL -> parquet cache -> score -> store
|   +-- acm_report.py        standalone HTML report generator
|   +-- acm_sim_routes.py    FastAPI router /api/sim/* - 14 routes for Simulate tab
|   +-- acm_seed_demo.py     idempotent seeder for CARE CSVs and OPC UA asset
|   +-- acm_opcua_bridge.py  asyncio singleton polling OPC UA -> opcua_buffer.db
|   +-- acm_mqtt_bridge.py   daemon thread subscribing MQTT -> mqtt_buffer.db
|   +-- download_care_dataset.py  partial Zenodo zip download via remotezip
|   +-- download_validation_datasets.py  public dataset adapters for ACM smoke testing
|   +-- public_dataset_benchmark.py  repeatable public dataset stress-test investigation
|   +-- care_benchmark.py    CARE wind-farm benchmark against ground-truth labels
|   +-- generate_fault_dataset.py  generates 10 labeled fault CSVs
|   `-- robustness_matrix.py       sensitivity / false-alarm matrix across fault types
|
+-- sim/                     vendored simulator package (in-process, no external service needed)
|   +-- generator_registry.py   11 domain generators
|   +-- generator_engine.py     generate_csv()
|   +-- generators/             domain-specific generators
|   +-- simulator.py            SimulatorEngine (replay)
|   +-- buffer_publisher.py     BufferPublisher -> mqtt_buffer.db (ACM reads this)
|   `-- sim_adapter.py          SimAdapter facade used by acm_service + acm_sim_routes
|
+-- static/
|   +-- index.html           single-page UI (Operator / Engineer / Admin / Simulate tabs)
|   +-- app.js               client-side polling, charts, API commands; SIM IIFE appended
|   `-- style.css            14 themes (5 dark, 9 light)
|
+-- configs/
|   `-- config_table.csv     human-editable runtime config (categories: data, sql, runtime)
|
+-- docs/
|   +-- ml-book.html         interactive ML reference book - every algorithm explained with demos
|   `-- screenshots/         UI screenshots (factory / forge / solarised x operator/engineer/admin)
|
+-- tests/                   pytest suite (68 tests across 4 files)
+-- sim_data/
|   `-- sample/              10 pre-generated fault CSVs + CARE wind-turbine events
|
+-- setup_acm.ps1            one-command Windows installer + updater
`-- setup.sh                 one-command Linux/macOS installer + updater
```

---

## SQL Schema Reference

| Table / View | Purpose |
|---|---|
| `monitored_assets` | Asset registry: source file/query, state (NEW/MATURING/READY/STALE), last runtime |
| `scores` | Full sensor timeline: fused score, six detector Z-scores, status, alarm flags |
| `alarms` | Contiguous alarm episodes: duration, peak, rule fired, acknowledgment comments |
| `assets` | Per-asset summary: current verdict, self-tuned thresholds, rules fired, alert stats |
| `runs` / `run_log` | Scheduler action log: processing speed, pipeline output, errors |
| `config` / `config_audit` | Live config and change history |
| `v_asset_now` | View: current state + unacknowledged alarms (Operator dashboard) |
| `v_daily_stats` | View: daily aggregates, availability rates, trends |

---

## Service Flags

```bash
python scripts/acm_service.py                          # SQLite default, port 8765
python scripts/acm_service.py --port 8766              # different port
python scripts/acm_service.py --db custom.db           # different database file
python scripts/acm_service.py \
    --backend mssql \
    --conn "DRIVER={ODBC Driver 18 for SQL Server};SERVER=host;DATABASE=ACM"
```

---

## Documentation

`docs/ml-book.html` - a self-contained interactive book covering every part of the ACM ML core: rolling features, all six detectors, calibration, fusion, and alarm rules, with working Chart.js demos and print-optimised layout. Open it in any browser.

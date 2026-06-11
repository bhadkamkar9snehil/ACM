# ACM — Autonomous Condition Monitoring

ACM watches industrial assets and tells you when something is wrong — **with no
labels, no training data preparation, and no human tuning**. Point it at an
asset's sensor history from t=0; it learns what normal looks like (faults in
the history included), sets its own alarm thresholds, distrusts its own
miscalibrated detectors, and reports in plain language with the full data
science substrate retained in SQL.

## Quick start — one command on any Windows machine

```powershell
irm https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup_acm.ps1 | iex
```

Installs Python/Git if missing, clones ACM, installs dependencies, runs the
test suite. **No Docker. No Grafana. SQL Server optional** — SQLite is the
default store and needs nothing installed.

## What it does

Six unsupervised detector heads score every sample:

| Head | Question it answers |
|---|---|
| AR1 | Is a sensor drifting or spiking against its own dynamics? |
| PCA-SPE | Have sensors decoupled from their learned correlation structure? |
| PCA-T2 | Is the operating point abnormal? |
| IForest | Is this a rare state? |
| GMM | Does this match any known operating mode? |
| OMR | Do sensors still predict each other? |

Calibrated z-scores are fused and passed to **self-tuned alarm rules** — every
threshold derived from the asset's own unlabelled history:

- **sustained** — fused score holds above a holdout-quantile level longer than
  the healthy history ever produced (step-change faults)
- **rate** — the trailing-24h fraction of high-z samples exceeds 1.5x the
  worst healthy day (intermittent faults that spike under load)
- **per-head rate** — each detector self-tunes its own rate rule over a 7-day
  window (faults that live in a single head)
- **availability** — continuous unplanned non-operation beyond 48h
  (a failed asset is parked; the outage *is* the symptom)
- **self-distrust gate** — any behaviour rule claiming the majority of a
  multi-week window is declared miscalibrated and discarded; ACM polices its
  own heads

## Benchmark — real faults, zero labels

Validated against the public CARE-to-Compare dataset (95 labelled events,
3 wind farms, [zenodo.org/records/15846963](https://zenodo.org/records/15846963)),
cold-start from t=0, one identical ruleset:

| Farm | Faults detected | Normal windows clean | F1 |
|---|---|---|---|
| A (onshore, 86 ch) | 12/12 | 6/10 | 0.86 |
| B (offshore, 257 ch) | 4/6 | 6/9 | 0.62 |

Reproduce everything:

```powershell
.\scripts\run_care_benchmark.ps1                      # Farm A end-to-end
.\scripts\run_care_benchmark.ps1 -Farms "A","B","C"   # entire dataset
```

## Results live in SQL — look inside ACM

Four tables + two views, identical on SQLite (default) and SQL Server
(`--backend mssql`):

| Table/View | What it holds |
|---|---|
| `assets` | one row per asset: verdict, self-tuned thresholds, rules fired |
| `scores` | full timeline: fused + all six detector z-scores, status, alarm |
| `alarms` | contiguous alarm episodes with duration and peak |
| `runs`, `run_log` | observability: what ACM did, stage by stage, decisions included |
| `v_asset_now` | **live monitor**: one row per asset, current state |
| `v_daily_stats` | **data science**: daily aggregates, rates, availability |

```powershell
# ingest a run's results, then visualise — all assets or any selection
python scripts\acm_store.py  ingest --results-dir results\farm_A --farm A --db acm_results.db
python scripts\acm_report.py --db acm_results.db --out report.html            # whole fleet
python scripts\acm_report.py --db acm_results.db --assets A/40 --out t10.html # one asset
python scripts\acm_report.py --db acm_results.db --list                       # what is available
```

The report is a single self-contained HTML file: per-asset fused timeline with
alarm shading, per-detector heat strip, fleet verdict table, and the
operations log (what ACM decided and why). Open it in a browser.

## Design principles

- **ML behaviour is code, not configuration.** `core/ml_defaults.py` holds the
  canonical, validated ML parameters. `configs/config_table.csv` contains only
  things a human should change: data sources, SQL connection, runtime
  scheduling, reporting.
- **No cowardly fallbacks.** A detector that cannot score a channel excludes
  it loudly; it never emits silent zeros or epsilon-scaled garbage.
- **Self-correction over operator intervention.** Calibration is out-of-sample
  (interleaved blocks across the whole history), thresholds are per-asset
  quantities, and information-free alarms are discarded by the distrust gate.
- **Channel roles are verified from data, not names.** Pre-derived statistic
  channels (`_min/_max/_std` exports) are detected by checking the maths holds
  on the samples, then passed through raw instead of being re-engineered.
  Raw-sensor feeds are untouched.
- **Polars only** in the feature pipeline. No engine selection, no fallback.

## Repository map

```
core/               ML pipeline: features, detectors, calibration, fusion, regimes
scripts/
  care_benchmark.py        unsupervised benchmark harness (parallel, crash-proof resume)
  download_care_dataset.py ranged download of CARE farms from Zenodo
  run_care_benchmark.ps1/.sh one-command benchmark reproduction
  acm_store.py             canonical SQL results store (SQLite / SQL Server)
  acm_report.py            self-contained HTML reports, any asset selection
  sql_batch_runner.py      production batch orchestration against SQL Server
configs/config_table.csv   human-operable settings ONLY
tests/                     258 tests, no live SQL Server required
setup_acm.ps1              one-command Windows setup
```

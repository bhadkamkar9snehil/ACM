# ACM Report Flow Testing

Use this workflow when the goal is to inspect ACM output through the generated HTML report only.
It exercises the same path as:

```bash
python scripts/acm_run.py --csv sim_data\generated\pump_bearing_wear_for_acm.csv --timestamp-col time_stamp --report pump_report.html
```

## 1. Pick a Dataset

Choose a CSV with enough history before the scoring window. When `--score-days` is omitted, `acm_run.py` infers a trailing score window from the dataset span and keeps the configured training baseline where possible.

Check the timestamp column and date span:

```powershell
@'
import pandas as pd
from pathlib import Path

p = Path(r"sim_data\generated\pump_bearing_wear_for_acm.csv")
ts_col = "time_stamp"
df = pd.read_csv(p, usecols=[ts_col])
ts = pd.to_datetime(df[ts_col], format="mixed")
print(f"rows={len(df):,}")
print(f"start={ts.min()}")
print(f"end={ts.max()}")
print(f"span_days={(ts.max() - ts.min()).total_seconds() / 86400:.1f}")
'@ | python -
```

## 2. Run the Report Flow

Use ACM's built-in SQLite DB by default. Do not pass `--db` unless you are deliberately doing an isolated developer test.

```powershell
New-Item -ItemType Directory -Force artifacts\report-flow | Out-Null
Remove-Item -Force artifacts\report-flow\acm_report.html -ErrorAction SilentlyContinue

python scripts/acm_run.py `
  --csv sim_data\generated\pump_bearing_wear_for_acm.csv `
  --timestamp-col time_stamp `
  --report artifacts\report-flow\acm_report.html
```

Expected result:

- CLI prints one row for the asset, either `ok` or `ALARM`.
- SQLite DB has rows in `assets`, `scores`, and `runs`.
- HTML report is written to the `--report` path.

## 3. Verify the Report Contents

```powershell
@'
import sqlite3
from pathlib import Path

db = Path(r"acm_results.db")
html = Path(r"artifacts\report-flow\acm_report.html")
con = sqlite3.connect(db)
cur = con.cursor()
for table in ["assets", "scores", "runs", "alarms"]:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    print(f"{table}={cur.fetchone()[0]}")
cur.execute("SELECT asset_key, verdict, alert_z, rules_fired FROM assets")
print(cur.fetchall())
con.close()
print(f"report={html} bytes={html.stat().st_size if html.exists() else 0}")
'@ | python -
```

## 4. Open the HTML Report

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory artifacts\report-flow
```

Then open:

```text
http://127.0.0.1:8765/acm_report.html
```

Visually check:

- Performance Summary renders.
- Assets Overview shows the scored asset.
- Detailed Analysis includes the interactive chart and detector heatmap.
- Diagnostic tables render: Asset Summary, Data Quality, Rule Diagnostics, Calibration, Detector Z-Scores, Alarm History.
- On narrow screens, long asset names wrap and wide tables scroll horizontally inside their table panels.

## Teammate Command Template

For a specific dataset, change only the CSV path, timestamp column, and report output name:

```powershell
python scripts/acm_run.py `
  --csv path\to\dataset.csv `
  --timestamp-col time_stamp `
  --report artifacts\report-flow\dataset_name.html
```

If the dataset uses `timestamp` instead of `time_stamp`, set `--timestamp-col timestamp`.

Only pass `--score-days N` when you deliberately want to override ACM's inferred split.

For local developer isolation only, add `--db artifacts\report-flow\scratch.db`. Do not use that for the standard teammate report-flow check.

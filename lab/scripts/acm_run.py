#!/usr/bin/env python3
"""
ACM production runner - score any assets, in parallel, straight into SQL.

Input per asset is ANY tabular sensor history: a CSV file (timestamp column +
numeric channels, optional status column) or a SQL Server table/query. The
history before --score-from is the asset's unlabelled baseline; everything
after is scored. Results (scores, alarms, runs, run_log) land in the
canonical store (SQLite by default, SQL Server with --backend mssql) and are
immediately visible in v_asset_now / the HTML report.

Examples:
  # one asset from CSV: train on everything before May, score May onward
  python scripts/acm_run.py --csv pump7.csv --asset PUMP7 \
      --timestamp-col time --status-col status --score-from 2026-05-01 \
      --db acm_results.db

  # a fleet in parallel (one CSV per asset, infer score window from each dataset)
  python scripts/acm_run.py --csv data/*.csv --workers 3 \
      --db acm_results.db --report fleet.html

  # from SQL Server historian, results back into SQL Server
  python scripts/acm_run.py --backend mssql --conn "DRIVER={...};SERVER=...;DATABASE=ACM" \
      --query "SELECT * FROM Historian WHERE EquipID=5010" --asset WFA_T10 \
      --timestamp-col EntryDateTime
"""
from __future__ import annotations

# Cap BLAS threads before numpy is imported anywhere in this process: forking
# a ProcessPoolExecutor worker while OpenBLAS holds a thread-pool lock in the
# parent can deadlock the child permanently. Must run before any numpy import.
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import warnings
warnings.filterwarnings("ignore", category=Warning, module="requests")
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_SEP = "  " + "-" * 53
_CYN = "\x1b[36m"
_GRN = "\x1b[32m"
_RED = "\x1b[31m"
_YLW = "\x1b[33m"
_DIM = "\x1b[2m"
_BLD = "\x1b[1m"
_RST = "\x1b[0m"

from core.ml_defaults import ML_DEFAULTS                            # noqa: E402
from core.pipeline import Z_COLS, score_asset                       # noqa: E402
from scripts.acm_feed import MIN_TRAIN_DAYS, frame_sensors          # noqa: E402
from scripts.acm_store import Store, alarm_episodes, ingest_result  # noqa: E402


def _deep_merge(base: dict, patch: dict) -> dict:
    result = dict(base)
    for k, v in patch.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def infer_score_days(ts: pd.Series, min_train_days: float = MIN_TRAIN_DAYS) -> float:
    """Infer a trailing score window when --score-days is omitted."""
    if len(ts) < 2:
        return 0.0
    span_days = (ts.iloc[-1] - ts.iloc[0]).total_seconds() / 86400.0
    if span_days <= 0:
        return 0.0

    raw_score_days = max(1.0, span_days / 3.0)
    available_after_baseline = span_days - float(min_train_days)
    if available_after_baseline > 0:
        return max(0.0, min(raw_score_days, available_after_baseline))
    return max(0.0, min(raw_score_days, span_days))


def parse_timestamp_col(values: pd.Series) -> pd.Series:
    """Parse common CSV timestamp columns, including mixed ISO precision.

    Tries dayfirst=False then dayfirst=True as whole-column-consistent
    formats and keeps whichever parses every row with no failures. A bare
    `pd.to_datetime(values)` lets pandas guess a single format from the
    first rows -- for ambiguous day<=12 values (e.g. "01-04-2018") it can
    silently guess month-first, then either corrupt every such row with no
    error at all, or raise once a day>12 row breaks that guess. format=
    "mixed" (per-row guessing) is used only as a last resort, when neither
    single consistent format covers every row -- that's the genuine
    mixed-precision case (e.g. some rows with fractional seconds, some
    without), not a day/month ambiguity.
    """
    n_missing = int(values.isna().sum())
    best = None
    for dayfirst in (False, True):
        parsed = pd.to_datetime(values, dayfirst=dayfirst, errors="coerce")
        n_bad = int(parsed.isna().sum()) - n_missing
        if n_bad == 0:
            return parsed
        if best is None or n_bad < best[0]:
            best = (n_bad, parsed)
    return pd.to_datetime(values, format="mixed")


def load_frame(args, source: str) -> pd.DataFrame:
    if args.query or args.table:
        import pyodbc
        con = pyodbc.connect(args.conn)
        sql = args.query or f"SELECT * FROM {args.table}"
        df = pd.read_sql(sql, con)
        con.close()
    else:
        df = pd.read_csv(source, sep=None, engine='python')
    if args.timestamp_col not in df.columns:
        raise SystemExit(f"timestamp column '{args.timestamp_col}' not in {source} "
                         f"(columns: {list(df.columns)[:8]}...)")
    df[args.timestamp_col] = parse_timestamp_col(df[args.timestamp_col])
    return df.sort_values(args.timestamp_col)


def run_one(args, source: str, asset_key: str, cfg: Optional[dict] = None) -> Dict:
    df = load_frame(args, source)
    ts = df[args.timestamp_col]
    if args.score_from:
        cut = pd.Timestamp(args.score_from)
        split_note = f"from={args.score_from}"
    else:
        score_days = args.score_days if args.score_days is not None else infer_score_days(ts)
        cut = ts.iloc[-1] - pd.Timedelta(days=score_days)
        split_note = f"score_days={score_days:.2f}" + (" auto" if args.score_days is None else "")
    train_df, score_df = df[ts < cut], df[ts >= cut]
    # Time-aware maturity gate: a baseline needs ENOUGH TIME behind it, not a
    # row count (1000 rows is a week at 10-min cadence but 17 minutes at 1Hz).
    span_days = ((cut - ts.iloc[0]).total_seconds() / 86400.0) if len(train_df) else 0.0
    if span_days < MIN_TRAIN_DAYS or not len(score_df):
        return {"asset_key": asset_key,
                "split_note": split_note,
                "error": f"MATURING (history span {span_days:.1f} d, "
                         f"need {MIN_TRAIN_DAYS:.0f} d)"}

    train_raw, train_status = frame_sensors(train_df, args.timestamp_col, args.status_col)
    score_raw, score_status = frame_sensors(score_df, args.timestamp_col, args.status_col)
    res = score_asset(train_raw=train_raw, score_raw=score_raw,
                      train_status=train_status, score_status=score_status, cfg=cfg)
    if args.override:
        res.override_json = args.override
    return {"asset_key": asset_key, "result": res, "split_note": split_note}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_argument_group("input")
    src.add_argument("--csv", nargs="*", default=None, help="CSV file(s); one asset per file (globs ok)")
    src.add_argument("--table", default=None, help="SQL table to read (mssql)")
    src.add_argument("--query", default=None, help="SQL query to read (mssql)")
    src.add_argument("--asset", default=None, help="asset key (default: CSV stem)")
    src.add_argument("--timestamp-col", default="time_stamp")
    src.add_argument("--status-col", default="status_type_id",
                     help="operating-status column (0/2=normal); enables the availability rule")
    split = ap.add_argument_group("train/score split")
    split.add_argument("--score-from", default=None, help="score everything from this timestamp")
    split.add_argument("--score-days", type=float, default=None,
                       help="score the trailing N days (default: infer from dataset span)")
    out = ap.add_argument_group("output")
    out.add_argument("--backend", choices=["sqlite", "mssql"], default="sqlite")
    out.add_argument("--db", default="acm_results.db")
    out.add_argument("--conn", default=None, help="pyodbc connection string (mssql)")
    out.add_argument("--group", default="fleet", help="asset group name in the store")
    out.add_argument("--report", default=None, help="also write an HTML report here")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--override", default=None, metavar="JSON",
                    help="JSON deep-merged onto core.ml_defaults.ML_DEFAULTS for ablation "
                         "testing, e.g. '{\"models\": {\"omr\": {\"enabled\": false}}}'")
    args = ap.parse_args()

    cfg: Optional[dict] = None
    if args.override:
        patch = json.loads(args.override)
        cfg = _deep_merge(dict(ML_DEFAULTS), patch)
        print(f"[ablation] ML_DEFAULTS patched with: {args.override}")

    sources: List[tuple] = []
    if args.csv:
        files = [f for pat in args.csv for f in sorted(glob.glob(pat))]
        if not files:
            raise SystemExit(f"no CSV files match {args.csv}")
        sources = [(f, args.asset or Path(f).stem) for f in files]
    elif args.query or args.table:
        sources = [(args.table or "query", args.asset or "asset")]
    else:
        raise SystemExit("provide --csv files or --table/--query with --conn")

    outputs: List[Dict] = []
    if args.workers > 1 and len(sources) > 1:
        import concurrent.futures as cf
        with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = [pool.submit(run_one, args, s, k, cfg) for s, k in sources]
            outputs = [f.result() for f in cf.as_completed(futs)]
    else:
        outputs = [run_one(args, s, k, cfg) for s, k in sources]

    # header
    print(flush=True)
    print(f"{_CYN}  ACM - one-shot run{_RST}", flush=True)
    print(f"{_DIM}{_SEP}{_RST}", flush=True)
    n = len(sources)
    backend_label = "SQL Server" if args.backend == "mssql" else "SQLite"
    print(f"{_DIM}  {n} asset{'s' if n != 1 else ''} - {backend_label} - {args.db}{_RST}", flush=True)
    print(flush=True)

    store = Store(args.backend, db=args.db, conn_str=args.conn)
    ok_count = skip_count = alarm_count = 0
    report_assets: List[str] = []
    try:
        for o in outputs:
            key = o["asset_key"]
            split_note = o.get("split_note")
            if "error" in o:
                skip_count += 1
                if split_note:
                    print(f"     split: {split_note}", flush=True)
                print(f"  {_YLW}!{_RST}  {_BLD}{key}{_RST}  {_DIM}skipped - {o['error']}{_RST}", flush=True)
                continue
            res = o["result"]
            ingest_result(store, args.group, key, res)
            report_assets.append(f"{args.group}/{key}")
            d = res.decision
            is_alarm = bool(d.alarm.any())
            if is_alarm:
                alarm_count += 1
                state_str = f"{_RED}ALARM{_RST}"
            else:
                ok_count += 1
                state_str = f"{_GRN}ok{_RST}"
            rule  = d.rule_fired or "-"
            if split_note:
                print(f"     split: {split_note}", flush=True)
            print(f"  {_GRN}+{_RST}  {_BLD}{key}{_RST}  {state_str}"
                  f"  {_DIM}z={d.alert_z:.2f}  rule={rule}  {res.runtime_s}s{_RST}", flush=True)
    finally:
        store.close()

    # footer
    print(flush=True)
    print(f"{_DIM}{_SEP}{_RST}", flush=True)
    parts = []
    if ok_count:    parts.append(f"{_GRN}{ok_count} ok{_RST}")
    if alarm_count: parts.append(f"{_RED}{alarm_count} alarm{_RST}")
    if skip_count:  parts.append(f"{_YLW}{skip_count} skipped{_RST}")
    print(f"  {' - '.join(parts)}", flush=True)

    if args.report and not report_assets:
        print(f"  {_YLW}Report skipped: no assets were scored{_RST}", flush=True)
        args.report = None

    if args.report:
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "scripts" / "acm_report.py"),
                        "--backend", args.backend, "--db", args.db,
                        *( ["--conn", args.conn] if args.conn else []),
                        "--out", args.report,
                        *(["--assets", *report_assets] if report_assets else [])], check=False)
        print(f"  {_DIM}Report - {args.report}{_RST}", flush=True)

    print(f"{_DIM}{_SEP}{_RST}", flush=True)
    print(flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

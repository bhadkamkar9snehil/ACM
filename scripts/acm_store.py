#!/usr/bin/env python3
"""
ACM canonical results store.

Retention layer for everything a human needs to SEE about ACM running on an
asset — four tables, one SQLite file, zero infrastructure. Grafana, Power BI,
Excel, pandas and plain sqlite3 can all read it directly. Production SQL
Server becomes just another writer of the SAME schema (EquipID maps to
asset_key); the 25-table ACM_* sprawl is not the retention contract, this is.

Tables
------
assets   one row per monitored asset/window:
         asset_key, farm, asset_id, label*, description*, verdict, lead_h,
         rules_fired, alert_z, persist, n_train, n_score
         (*label/description only exist when ground truth is known, i.e.
          benchmarks; production rows leave them NULL)
scores   the full scored timeline per asset:
         asset_key, ts, fused, ar1_z, pca_spe_z, pca_t2_z, iforest_z, gmm_z,
         omr_z, status, alarm
alarms   contiguous alarm episodes derived from scores:
         asset_key, start_ts, end_ts, duration_h, peak_fused
summary  one row per ingest batch: farm, ingested_at, metrics_json

Usage
-----
  python scripts/acm_store.py ingest --results-dir /path/care_final_A \
      --data-dir "/path/Wind Farm A" --farm A --db acm_results.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    asset_key   TEXT PRIMARY KEY,
    farm        TEXT,
    asset_id    INTEGER,
    label       TEXT,
    description TEXT,
    verdict     TEXT,
    lead_h      REAL,
    rules_fired TEXT,
    alert_z     REAL,
    persist     INTEGER,
    n_score     INTEGER
);
CREATE TABLE IF NOT EXISTS scores (
    asset_key TEXT,
    ts        TEXT,
    fused     REAL,
    ar1_z     REAL, pca_spe_z REAL, pca_t2_z REAL,
    iforest_z REAL, gmm_z REAL, omr_z REAL,
    status    INTEGER,
    alarm     INTEGER
);
CREATE INDEX IF NOT EXISTS ix_scores_asset_ts ON scores(asset_key, ts);
CREATE TABLE IF NOT EXISTS alarms (
    asset_key  TEXT,
    start_ts   TEXT,
    end_ts     TEXT,
    duration_h REAL,
    peak_fused REAL
);
CREATE TABLE IF NOT EXISTS summary (
    farm         TEXT,
    ingested_at  TEXT,
    metrics_json TEXT
);
"""

Z_COLS = ["ar1_z", "pca_spe_z", "pca_t2_z", "iforest_z", "gmm_z", "omr_z"]


def alarm_episodes(ts: pd.Series, alarm: np.ndarray, fused: np.ndarray) -> list[tuple]:
    """Contiguous alarm runs -> (start, end, duration_h, peak)."""
    out, start = [], None
    for i, a in enumerate(alarm):
        if a and start is None:
            start = i
        elif not a and start is not None:
            out.append((str(ts.iloc[start]), str(ts.iloc[i - 1]),
                        round((ts.iloc[i - 1] - ts.iloc[start]).total_seconds() / 3600, 2),
                        float(np.nanmax(fused[start:i]))))
            start = None
    if start is not None:
        out.append((str(ts.iloc[start]), str(ts.iloc[-1]),
                    round((ts.iloc[-1] - ts.iloc[start]).total_seconds() / 3600, 2),
                    float(np.nanmax(fused[start:]))))
    return out


def ingest(results_dir: Path, farm: str, db_path: Path) -> None:
    """Load a benchmark results directory into the store."""
    results = pd.read_csv(results_dir / "results.csv")
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)

    n_assets = 0
    for _, r in results.iterrows():
        if "error" in r and isinstance(r.get("error"), str) and r["error"]:
            continue
        eid = int(r["event_id"])
        key = f"{farm}/{eid}"
        s_path = results_dir / f"event_{eid}_scores.csv"
        if not s_path.exists():
            continue
        s = pd.read_csv(s_path, parse_dates=["time_stamp"])

        # Recreate the alarm mask exactly as evaluated (rules are eval-only):
        # stored result already carries the verdict; for the timeline we mark
        # alarm where fused exceeded the chosen threshold persistently OR the
        # asset was in the detected state — simplest faithful proxy is to
        # re-evaluate; to stay dependency-free here we shade by alert_z_eff.
        thr = float(r.get("alert_z_eff", 3.0))
        alarm = (s["fused"].to_numpy() >= thr).astype(int)

        verdict = ("DETECTED" if r.get("detected") else "MISSED") if r.get("label") == "anomaly" else \
                  ("FALSE_ALARM" if r.get("detected") else "CLEAN")
        con.execute("INSERT OR REPLACE INTO assets VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (key, farm, int(r.get("asset", -1)), r.get("label"),
                     r.get("description") if isinstance(r.get("description"), str) else "",
                     verdict, float(r["lead_time_h"]) if pd.notna(r.get("lead_time_h")) else None,
                     r.get("rule_fired", ""), float(r.get("alert_z_eff", np.nan)),
                     int(r.get("persist_eff", 0)), len(s)))

        score_rows = pd.DataFrame({
            "asset_key": key,
            "ts": s["time_stamp"].astype(str),
            "fused": s["fused"],
            **{z: (s[z] if z in s.columns else np.nan) for z in Z_COLS},
            "status": s["status_type_id"],
            "alarm": alarm,
        })
        con.execute("DELETE FROM scores WHERE asset_key = ?", (key,))
        score_rows.to_sql("scores", con, if_exists="append", index=False)

        con.execute("DELETE FROM alarms WHERE asset_key = ?", (key,))
        for ep in alarm_episodes(s["time_stamp"], alarm.astype(bool), s["fused"].to_numpy()):
            con.execute("INSERT INTO alarms VALUES (?,?,?,?,?)", (key, *ep))
        n_assets += 1

    summary_path = results_dir / "summary.json"
    metrics = summary_path.read_text() if summary_path.exists() else "{}"
    con.execute("INSERT INTO summary VALUES (?,?,?)",
                (farm, datetime.now(timezone.utc).isoformat(), metrics))
    con.commit()
    con.close()
    print(f"Ingested {n_assets} assets from {results_dir} into {db_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest")
    p.add_argument("--results-dir", required=True)
    p.add_argument("--farm", required=True)
    p.add_argument("--db", default="acm_results.db")
    args = ap.parse_args()
    if args.cmd == "ingest":
        ingest(Path(args.results_dir), args.farm, Path(args.db))
    return 0


if __name__ == "__main__":
    sys.exit(main())

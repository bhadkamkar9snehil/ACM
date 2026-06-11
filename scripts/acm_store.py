#!/usr/bin/env python3
"""
ACM canonical results store — SQL is the contract.

Retention layer for everything a human needs to SEE about ACM running on an
asset: four tables, one schema, two interchangeable SQL backends:

  sqlite     single file, zero infrastructure (laptop, benchmarks, dev)
  mssql      SQL Server via pyodbc (production), SAME tables

Tables
------
assets   one row per monitored asset/window:
         asset_key, farm, asset_id, label*, description*, verdict, lead_h,
         rules_fired, alert_z, persist, n_score
         (*label/description only exist when ground truth is known, i.e.
          benchmarks; production rows leave them NULL)
scores   the full scored timeline per asset (start to end):
         asset_key, ts, fused, ar1_z, pca_spe_z, pca_t2_z, iforest_z, gmm_z,
         omr_z, status, alarm
alarms   contiguous alarm episodes derived from scores:
         asset_key, start_ts, end_ts, duration_h, peak_fused
summary  one row per ingest batch: farm, ingested_at, metrics_json

Usage
-----
  # benchmark artifacts -> SQLite
  python scripts/acm_store.py ingest --results-dir /path/care_final_A \
      --farm A --db acm_results.db

  # same artifacts -> SQL Server (database must exist; tables auto-created)
  python scripts/acm_store.py ingest --results-dir /path/care_final_A \
      --farm A --backend mssql \
      --conn "DRIVER={ODBC Driver 18 for SQL Server};SERVER=host;DATABASE=ACM;Trusted_Connection=yes;TrustServerCertificate=yes"
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

Z_COLS = ["ar1_z", "pca_spe_z", "pca_t2_z", "iforest_z", "gmm_z", "omr_z"]

DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS assets (
    asset_key TEXT PRIMARY KEY, farm TEXT, asset_id INTEGER, label TEXT,
    description TEXT, verdict TEXT, lead_h REAL, rules_fired TEXT,
    alert_z REAL, persist INTEGER, n_score INTEGER);
CREATE TABLE IF NOT EXISTS scores (
    asset_key TEXT, ts TEXT, fused REAL,
    ar1_z REAL, pca_spe_z REAL, pca_t2_z REAL,
    iforest_z REAL, gmm_z REAL, omr_z REAL,
    status INTEGER, alarm INTEGER);
CREATE INDEX IF NOT EXISTS ix_scores_asset_ts ON scores(asset_key, ts);
CREATE TABLE IF NOT EXISTS alarms (
    asset_key TEXT, start_ts TEXT, end_ts TEXT, duration_h REAL, peak_fused REAL);
CREATE TABLE IF NOT EXISTS summary (
    farm TEXT, ingested_at TEXT, metrics_json TEXT);
"""

# T-SQL: no IF NOT EXISTS on CREATE TABLE; OBJECT_ID guards instead.
DDL_MSSQL = """
IF OBJECT_ID('dbo.acm_assets') IS NULL CREATE TABLE dbo.acm_assets (
    asset_key NVARCHAR(64) PRIMARY KEY, farm NVARCHAR(16), asset_id INT,
    label NVARCHAR(32), description NVARCHAR(256), verdict NVARCHAR(32),
    lead_h FLOAT, rules_fired NVARCHAR(256), alert_z FLOAT,
    persist INT, n_score INT);
IF OBJECT_ID('dbo.acm_scores') IS NULL CREATE TABLE dbo.acm_scores (
    asset_key NVARCHAR(64), ts DATETIME2, fused FLOAT,
    ar1_z FLOAT, pca_spe_z FLOAT, pca_t2_z FLOAT,
    iforest_z FLOAT, gmm_z FLOAT, omr_z FLOAT,
    status INT, alarm INT,
    INDEX ix_acm_scores_asset_ts (asset_key, ts));
IF OBJECT_ID('dbo.acm_alarms') IS NULL CREATE TABLE dbo.acm_alarms (
    asset_key NVARCHAR(64), start_ts DATETIME2, end_ts DATETIME2,
    duration_h FLOAT, peak_fused FLOAT);
IF OBJECT_ID('dbo.acm_summary') IS NULL CREATE TABLE dbo.acm_summary (
    farm NVARCHAR(16), ingested_at DATETIME2, metrics_json NVARCHAR(MAX));
"""


class Store:
    """Backend-agnostic store: same schema, qmark params on both drivers."""

    def __init__(self, backend: str, db: str | None = None, conn_str: str | None = None):
        self.backend = backend
        if backend == "sqlite":
            self.con = sqlite3.connect(db or "acm_results.db")
            self.con.executescript(DDL_SQLITE)
            self.prefix = ""
        elif backend == "mssql":
            import pyodbc
            self.con = pyodbc.connect(conn_str, autocommit=False)
            cur = self.con.cursor()
            for stmt in DDL_MSSQL.split(");"):
                if stmt.strip():
                    cur.execute(stmt + ");")
            self.con.commit()
            self.prefix = "dbo.acm_"
        else:
            raise ValueError(f"unknown backend {backend}")

    def t(self, name: str) -> str:
        return f"{self.prefix}{name}" if self.backend == "mssql" else name

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.con.cursor().execute(sql, params) if self.backend == "mssql" else self.con.execute(sql, params)

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        cur = self.con.cursor()
        if self.backend == "mssql":
            cur.fast_executemany = True
        cur.executemany(sql, rows)

    def commit(self) -> None:
        self.con.commit()

    def close(self) -> None:
        self.con.close()


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


def _none(v: Any) -> Any:
    return None if (v is None or (isinstance(v, float) and not np.isfinite(v)) or pd.isna(v)) else v


def ingest(results_dir: Path, farm: str, store: Store) -> None:
    """Load a benchmark/run results directory into the store."""
    results = pd.read_csv(results_dir / "results.csv")
    n_assets = 0
    for _, r in results.iterrows():
        if isinstance(r.get("error"), str) and r["error"]:
            continue
        eid = int(r["event_id"])
        key = f"{farm}/{eid}"
        s_path = results_dir / f"event_{eid}_scores.csv"
        if not s_path.exists():
            continue
        s = pd.read_csv(s_path, parse_dates=["time_stamp"])

        thr = float(r.get("alert_z_eff", 3.0))
        alarm = (s["fused"].to_numpy() >= thr).astype(int)
        verdict = ("DETECTED" if r.get("detected") else "MISSED") if r.get("label") == "anomaly" else \
                  ("FALSE_ALARM" if r.get("detected") else "CLEAN")

        store.execute(f"DELETE FROM {store.t('assets')} WHERE asset_key = ?", (key,))
        store.execute(
            f"INSERT INTO {store.t('assets')} VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (key, farm, int(r.get("asset", -1)), _none(r.get("label")),
             (r.get("description") if isinstance(r.get("description"), str) else ""),
             verdict, _none(r.get("lead_time_h")), r.get("rule_fired", ""),
             _none(r.get("alert_z_eff")), int(r.get("persist_eff", 0)), len(s)))

        rows = list(zip(
            [key] * len(s), s["time_stamp"].astype(str),
            s["fused"].astype(float),
            *[(s[z] if z in s.columns else pd.Series(np.nan, index=s.index)).astype(float).where(lambda x: np.isfinite(x), None) for z in Z_COLS],
            s["status_type_id"].astype(int), alarm.tolist(),
        ))
        store.execute(f"DELETE FROM {store.t('scores')} WHERE asset_key = ?", (key,))
        store.executemany(f"INSERT INTO {store.t('scores')} VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)

        store.execute(f"DELETE FROM {store.t('alarms')} WHERE asset_key = ?", (key,))
        eps = alarm_episodes(s["time_stamp"], alarm.astype(bool), s["fused"].to_numpy())
        if eps:
            store.executemany(f"INSERT INTO {store.t('alarms')} VALUES (?,?,?,?,?)",
                              [(key, *e) for e in eps])
        n_assets += 1

    summary_path = results_dir / "summary.json"
    metrics = summary_path.read_text() if summary_path.exists() else "{}"
    store.execute(f"INSERT INTO {store.t('summary')} VALUES (?,?,?)",
                  (farm, datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds"), metrics))
    store.commit()
    print(f"Ingested {n_assets} assets from {results_dir} ({store.backend})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest")
    p.add_argument("--results-dir", required=True)
    p.add_argument("--farm", required=True)
    p.add_argument("--backend", choices=["sqlite", "mssql"], default="sqlite")
    p.add_argument("--db", default="acm_results.db", help="SQLite file (sqlite backend)")
    p.add_argument("--conn", default=None, help="pyodbc connection string (mssql backend)")
    args = ap.parse_args()
    if args.cmd == "ingest":
        store = Store(args.backend, db=args.db, conn_str=args.conn)
        try:
            ingest(Path(args.results_dir), args.farm, store)
        finally:
            store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

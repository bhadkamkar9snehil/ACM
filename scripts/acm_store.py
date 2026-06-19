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
    asset_key TEXT, start_ts TEXT, end_ts TEXT, duration_h REAL, peak_fused REAL,
    ack_by TEXT, ack_at TEXT, ack_note TEXT);
CREATE TABLE IF NOT EXISTS summary (
    farm TEXT, ingested_at TEXT, metrics_json TEXT);
CREATE TABLE IF NOT EXISTS runs (
    asset_key TEXT, run_id TEXT, started_at TEXT, duration_s REAL,
    status TEXT, alert_z REAL, persist INTEGER, rules_fired TEXT, notes TEXT,
    rules_diagnostic_json TEXT, calibration_json TEXT, data_quality_json TEXT,
    override_json TEXT);
CREATE TABLE IF NOT EXISTS run_log (
    asset_key TEXT, ts TEXT, level TEXT, stage TEXT, message TEXT);
CREATE INDEX IF NOT EXISTS ix_runlog_asset     ON run_log(asset_key, ts);
CREATE INDEX IF NOT EXISTS ix_alarms_asset     ON alarms(asset_key);
CREATE INDEX IF NOT EXISTS ix_alarms_asset_ack ON alarms(asset_key, ack_at);

CREATE TABLE IF NOT EXISTS config (
    category TEXT, param_path TEXT, param_value TEXT, value_type TEXT,
    updated_at TEXT, PRIMARY KEY (category, param_path));

-- SERVICE LAYER: asset registry, single-row service state, config audit trail
CREATE TABLE IF NOT EXISTS monitored_assets (
    asset_key TEXT PRIMARY KEY, grp TEXT DEFAULT 'fleet', enabled INTEGER DEFAULT 1,
    source_kind TEXT, source_ref TEXT, conn_ref TEXT,
    timestamp_col TEXT, status_col TEXT, added_at TEXT, retired_at TEXT,
    state TEXT DEFAULT 'NEW', state_detail TEXT,
    last_run_at TEXT, last_score_ts TEXT, last_runtime_s REAL);
CREATE TABLE IF NOT EXISTS service_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    paused INTEGER DEFAULT 0, tick_minutes INTEGER DEFAULT 15,
    last_tick_at TEXT, last_tick_duration_s REAL, started_at TEXT);
CREATE TABLE IF NOT EXISTS config_audit (
    changed_at TEXT, changed_by TEXT, category TEXT, param_path TEXT,
    old_value TEXT, new_value TEXT, note TEXT);

-- LIVE MONITORING: one row per asset.
--
-- Design: keep ix_scores_asset_ts-indexed correlated subqueries for scores
-- (each seek is O(log N) and hits RAM in any warm DB) and replace the three
-- alarm subqueries — which had NO index and did full-table scans — with a
-- single GROUP BY pass over alarms using ix_alarms_asset_ack.
--
-- Net change: 3·N alarm full-scans → 1 alarm scan with index grouping.
DROP VIEW IF EXISTS v_asset_now;
CREATE VIEW v_asset_now AS
WITH alarm_agg AS (
    SELECT asset_key,
           COUNT(*)                                         AS alarm_episodes,
           SUM(CASE WHEN ack_at IS NULL THEN 1 ELSE 0 END) AS unacked_alarms,
           MAX(end_ts)                                      AS last_alarm_end
    FROM alarms GROUP BY asset_key
)
SELECT a.asset_key, a.farm, a.asset_id, a.verdict, a.rules_fired,
       m.state, m.enabled, m.last_run_at,
       (SELECT MAX(ts) FROM scores s WHERE s.asset_key = a.asset_key)  AS last_ts,
       (SELECT fused FROM scores s WHERE s.asset_key = a.asset_key
        ORDER BY ts DESC LIMIT 1)                                       AS last_fused,
       COALESCE(aa.alarm_episodes, 0)  AS alarm_episodes,
       COALESCE(aa.unacked_alarms, 0)  AS unacked_alarms,
       aa.last_alarm_end
FROM assets a
LEFT JOIN monitored_assets m ON a.asset_key = m.grp || '/' || m.asset_key
LEFT JOIN alarm_agg aa       ON a.asset_key = aa.asset_key;

-- DATA SCIENCE (daily aggregates): trend material per asset per day
CREATE VIEW IF NOT EXISTS v_daily_stats AS
SELECT asset_key, substr(ts, 1, 10) AS day,
       COUNT(*)    AS n,
       AVG(fused)  AS fused_mean,
       MAX(fused)  AS fused_max,
       AVG(CASE WHEN fused >= 3.0 THEN 1.0 ELSE 0.0 END) AS rate_z3,
       SUM(alarm)  AS alarm_samples,
       AVG(CASE WHEN status IN (0,2) THEN 1.0 ELSE 0.0 END) AS availability
FROM scores GROUP BY asset_key, substr(ts, 1, 10);
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
    duration_h FLOAT, peak_fused FLOAT,
    ack_by NVARCHAR(64), ack_at DATETIME2, ack_note NVARCHAR(MAX),
    INDEX ix_acm_alarms_asset     (asset_key),
    INDEX ix_acm_alarms_asset_ack (asset_key, ack_at));
IF OBJECT_ID('dbo.acm_summary') IS NULL CREATE TABLE dbo.acm_summary (
    farm NVARCHAR(16), ingested_at DATETIME2, metrics_json NVARCHAR(MAX));
IF OBJECT_ID('dbo.acm_runs') IS NULL CREATE TABLE dbo.acm_runs (
    asset_key NVARCHAR(64), run_id NVARCHAR(64), started_at DATETIME2,
    duration_s FLOAT, status NVARCHAR(16), alert_z FLOAT, persist INT,
    rules_fired NVARCHAR(256), notes NVARCHAR(MAX),
    rules_diagnostic_json NVARCHAR(MAX), calibration_json NVARCHAR(MAX),
    data_quality_json NVARCHAR(MAX), override_json NVARCHAR(MAX));
IF OBJECT_ID('dbo.acm_run_log') IS NULL CREATE TABLE dbo.acm_run_log (
    asset_key NVARCHAR(64), ts DATETIME2, level NVARCHAR(8),
    stage NVARCHAR(32), message NVARCHAR(MAX),
    INDEX ix_acm_runlog_asset (asset_key, ts));
IF OBJECT_ID('dbo.acm_config') IS NULL CREATE TABLE dbo.acm_config (
    category NVARCHAR(32), param_path NVARCHAR(128), param_value NVARCHAR(MAX),
    value_type NVARCHAR(16), updated_at DATETIME2,
    CONSTRAINT pk_acm_config PRIMARY KEY (category, param_path));
IF OBJECT_ID('dbo.acm_monitored_assets') IS NULL CREATE TABLE dbo.acm_monitored_assets (
    asset_key NVARCHAR(64) PRIMARY KEY, grp NVARCHAR(32) DEFAULT 'fleet',
    enabled INT DEFAULT 1, source_kind NVARCHAR(8), source_ref NVARCHAR(MAX),
    conn_ref NVARCHAR(MAX), timestamp_col NVARCHAR(64), status_col NVARCHAR(64),
    added_at DATETIME2, retired_at DATETIME2,
    state NVARCHAR(16) DEFAULT 'NEW', state_detail NVARCHAR(256),
    last_run_at DATETIME2, last_score_ts DATETIME2, last_runtime_s FLOAT);
IF OBJECT_ID('dbo.acm_service_state') IS NULL CREATE TABLE dbo.acm_service_state (
    id INT PRIMARY KEY CHECK (id = 1),
    paused INT DEFAULT 0, tick_minutes INT DEFAULT 15,
    last_tick_at DATETIME2, last_tick_duration_s FLOAT, started_at DATETIME2);
IF OBJECT_ID('dbo.acm_config_audit') IS NULL CREATE TABLE dbo.acm_config_audit (
    changed_at DATETIME2, changed_by NVARCHAR(64), category NVARCHAR(32),
    param_path NVARCHAR(128), old_value NVARCHAR(MAX), new_value NVARCHAR(MAX),
    note NVARCHAR(MAX));
"""

# Stores created before the ack columns existed get them added explicitly.
DDL_MSSQL_MIGRATIONS = [
    "IF COL_LENGTH('dbo.acm_alarms', 'ack_by') IS NULL "
    "ALTER TABLE dbo.acm_alarms ADD ack_by NVARCHAR(64), ack_at DATETIME2, ack_note NVARCHAR(MAX)",
    # Alarm indexes added in perf/performance-gains; idempotent on existing stores.
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='ix_acm_alarms_asset' "
    "AND object_id=OBJECT_ID('dbo.acm_alarms')) "
    "CREATE INDEX ix_acm_alarms_asset ON dbo.acm_alarms(asset_key)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='ix_acm_alarms_asset_ack' "
    "AND object_id=OBJECT_ID('dbo.acm_alarms')) "
    "CREATE INDEX ix_acm_alarms_asset_ack ON dbo.acm_alarms(asset_key, ack_at)",
]

# Views created separately on mssql (CREATE VIEW must be first in batch);
# CREATE OR ALTER so view upgrades reach existing stores.
DDL_MSSQL_VIEWS = [
    # Hybrid: keep ix_acm_scores_asset_ts-backed correlated subqueries for scores;
    # replace 3×N alarm full-scans with one GROUP BY via ix_acm_alarms_asset_ack.
    """EXEC('CREATE OR ALTER VIEW dbo.acm_v_asset_now AS
WITH alarm_agg AS (
    SELECT asset_key,
           COUNT(*)                                         AS alarm_episodes,
           SUM(CASE WHEN ack_at IS NULL THEN 1 ELSE 0 END) AS unacked_alarms,
           MAX(end_ts)                                      AS last_alarm_end
    FROM dbo.acm_alarms GROUP BY asset_key
)
SELECT a.asset_key, a.farm, a.asset_id, a.verdict, a.rules_fired,
       m.state, m.enabled, m.last_run_at,
       (SELECT MAX(ts) FROM dbo.acm_scores s WHERE s.asset_key = a.asset_key) AS last_ts,
       (SELECT TOP 1 fused FROM dbo.acm_scores s WHERE s.asset_key = a.asset_key ORDER BY ts DESC) AS last_fused,
       COALESCE(aa.alarm_episodes, 0) AS alarm_episodes,
       COALESCE(aa.unacked_alarms, 0) AS unacked_alarms,
       aa.last_alarm_end
FROM dbo.acm_assets a
LEFT JOIN dbo.acm_monitored_assets m ON a.asset_key = m.grp + ''/'' + m.asset_key
LEFT JOIN alarm_agg aa              ON a.asset_key = aa.asset_key')""",
    """EXEC('CREATE OR ALTER VIEW dbo.acm_v_daily_stats AS
SELECT asset_key, CAST(ts AS DATE) AS day, COUNT(*) AS n,
       AVG(fused) AS fused_mean, MAX(fused) AS fused_max,
       AVG(CASE WHEN fused >= 3.0 THEN 1.0 ELSE 0.0 END) AS rate_z3,
       SUM(CAST(alarm AS FLOAT)) AS alarm_samples,
       AVG(CASE WHEN status IN (0,2) THEN 1.0 ELSE 0.0 END) AS availability
FROM dbo.acm_scores GROUP BY asset_key, CAST(ts AS DATE)')""",
]


class Store:
    """Backend-agnostic store: same schema, qmark params on both drivers."""

    def __init__(self, backend: str, db: str | None = None, conn_str: str | None = None):
        self.backend = backend
        if backend == "sqlite":
            # check_same_thread=False: the service API may touch the store
            # from a worker thread; all writes are serialized by design
            # (single writer in the tick, API writes on the event loop).
            self.con = sqlite3.connect(db or "acm_results.db", check_same_thread=False)
            self._migrate_sqlite()
            self.con.executescript(DDL_SQLITE)
            self.prefix = ""
        elif backend == "mssql":
            import pyodbc
            self.con = pyodbc.connect(conn_str, autocommit=False)
            cur = self.con.cursor()
            for stmt in DDL_MSSQL.split(");"):
                if stmt.strip():
                    cur.execute(stmt + ");")
            for m in DDL_MSSQL_MIGRATIONS:
                cur.execute(m)
            for v in DDL_MSSQL_VIEWS:
                cur.execute(v)
            self.con.commit()
            self.prefix = "dbo.acm_"
        else:
            raise ValueError(f"unknown backend {backend}")

    def _migrate_sqlite(self) -> None:
        """Stores created before the ack columns existed get them added."""
        tables = {r[0] for r in self.con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "alarms" in tables:
            cols = {r[1] for r in self.con.execute("PRAGMA table_info(alarms)")}
            if "ack_by" not in cols:
                for col in ("ack_by TEXT", "ack_at TEXT", "ack_note TEXT"):
                    self.con.execute(f"ALTER TABLE alarms ADD COLUMN {col}")
                self.con.commit()
        if "runs" in tables:
            cols = {r[1] for r in self.con.execute("PRAGMA table_info(runs)")}
            for col in ("rules_diagnostic_json TEXT", "calibration_json TEXT", "data_quality_json TEXT",
                        "override_json TEXT"):
                if col.split()[0] not in cols:
                    self.con.execute(f"ALTER TABLE runs ADD COLUMN {col}")
            self.con.commit()

    def t(self, name: str) -> str:
        return f"{self.prefix}{name}" if self.backend == "mssql" else name

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.con.cursor().execute(sql, params) if self.backend == "mssql" else self.con.execute(sql, params)

    def fetch(self, sql: str, params: tuple = ()) -> list[dict]:
        """Rows as dicts — works identically on sqlite and pyodbc cursors."""
        cur = self.con.cursor()
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

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
            store.executemany(
                f"INSERT INTO {store.t('alarms')} "
                f"(asset_key, start_ts, end_ts, duration_h, peak_fused) VALUES (?,?,?,?,?)",
                [(key, *e) for e in eps])

        # Observability: every processing run is itself a record.
        store.execute(f"DELETE FROM {store.t('runs')} WHERE asset_key = ?", (key,))
        store.execute(
            f"INSERT INTO {store.t('runs')} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (key, f"{key}@ingest", datetime.now(timezone.utc).isoformat(sep=' ', timespec='seconds'),
             _none(r.get("runtime_s")), "OK", _none(r.get("alert_z_eff")),
             int(r.get("persist_eff", 0)) if pd.notna(r.get("persist_eff")) else None,
             r.get("rule_fired", ""), "", None, None, None, None))
        log_path = results_dir / f"event_{eid}_runlog.csv"
        store.execute(f"DELETE FROM {store.t('run_log')} WHERE asset_key = ?", (key,))
        if log_path.exists():
            lg = pd.read_csv(log_path)
            store.executemany(
                f"INSERT INTO {store.t('run_log')} VALUES (?,?,?,?,?)",
                [(key, str(row.ts), str(row.level), str(row.stage), str(row.message))
                 for row in lg.itertuples()])
        n_assets += 1

    summary_path = results_dir / "summary.json"
    metrics = summary_path.read_text() if summary_path.exists() else "{}"
    store.execute(f"INSERT INTO {store.t('summary')} VALUES (?,?,?)",
                  (farm, datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds"), metrics))
    store.commit()
    print(f"Ingested {n_assets} assets from {results_dir} ({store.backend})")


def ingest_result(store: "Store", group: str, asset_key: str, res,
                  keep_history: bool = False) -> None:
    """Write one core.pipeline.PipelineResult straight into the store.

    keep_history=False (batch/benchmark): each ingest replaces the asset's
    scores/alarms/runs/run_log wholesale — byte-identical to the original
    behaviour.
    keep_history=True (service, sliding windows): only the re-scored overlap
    (ts >= window start) is replaced; older scores, alarm episodes (with
    their acknowledgements, re-attached by start_ts) and the run history
    survive across ticks.
    """
    key = f"{group}/{asset_key}"
    d = res.decision
    now = datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")
    window_start = str(res.ts[0])

    store.execute(f"DELETE FROM {store.t('assets')} WHERE asset_key = ?", (key,))
    store.execute(
        f"INSERT INTO {store.t('assets')} VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (key, group, None, None, "", "ALARM" if d.alarm.any() else "OK", None,
         d.rule_fired, round(float(d.alert_z), 2), int(d.persist), len(res.fused)))

    rows = list(zip(
        [key] * len(res.fused), [str(t) for t in res.ts],
        [float(v) for v in res.fused],
        *[[None if not np.isfinite(v) else float(v) for v in res.scores[z]]
          for z in Z_COLS],
        ([int(v) for v in res.score_status] if res.score_status is not None
         else [None] * len(res.fused)),
        [int(v) for v in d.alarm],
    ))
    if keep_history:
        store.execute(f"DELETE FROM {store.t('scores')} WHERE asset_key = ? AND ts >= ?",
                      (key, window_start))
    else:
        store.execute(f"DELETE FROM {store.t('scores')} WHERE asset_key = ?", (key,))
    store.executemany(f"INSERT INTO {store.t('scores')} VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)

    acks = {}
    if keep_history:
        cur = store.con.cursor()
        cur.execute(f"SELECT start_ts, ack_by, ack_at, ack_note FROM {store.t('alarms')} "
                    f"WHERE asset_key = ? AND ack_at IS NOT NULL", (key,))
        acks = {str(r[0]): (r[1], r[2], r[3]) for r in cur.fetchall()}
        store.execute(f"DELETE FROM {store.t('alarms')} WHERE asset_key = ? AND start_ts >= ?",
                      (key, window_start))
    else:
        store.execute(f"DELETE FROM {store.t('alarms')} WHERE asset_key = ?", (key,))
    eps = alarm_episodes(pd.Series(res.ts), d.alarm, res.fused)
    if eps:
        store.executemany(
            f"INSERT INTO {store.t('alarms')} "
            f"(asset_key, start_ts, end_ts, duration_h, peak_fused, ack_by, ack_at, ack_note) "
            f"VALUES (?,?,?,?,?,?,?,?)",
            [(key, *e, *acks.get(str(e[0]), (None, None, None))) for e in eps])

    if not keep_history:
        store.execute(f"DELETE FROM {store.t('runs')} WHERE asset_key = ?", (key,))
        store.execute(f"DELETE FROM {store.t('run_log')} WHERE asset_key = ?", (key,))
    import json as _json_mod
    notes = ("culprits: " + ", ".join(res.culprits)) if getattr(res, "culprits", None) else ""
    rules_diag_json = _json_mod.dumps(d.rules_diagnostic, default=str) \
        if getattr(d, "rules_diagnostic", None) else None
    store.execute(
        f"INSERT INTO {store.t('runs')} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (key, f"{key}@{now}", now, float(res.runtime_s), "OK",
         round(float(d.alert_z), 2), int(d.persist), d.rule_fired, notes,
         rules_diag_json,
         getattr(res, "calibration_json", None),
         getattr(res, "data_quality_json", None),
         getattr(res, "override_json", None)))
    if res.runlog:
        store.executemany(f"INSERT INTO {store.t('run_log')} VALUES (?,?,?,?,?)",
                          [(key, r["ts"], r["level"], r["stage"], r["message"])
                           for r in res.runlog])
    store.commit()


def record_run_error(store: "Store", key: str, message: str) -> None:
    """A failed run is itself a record — visible in the runs/run_log tables."""
    now = datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")
    store.execute(f"INSERT INTO {store.t('runs')} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (key, f"{key}@{now}", now, None, "ERROR", None, None, "", message[:500],
                   None, None, None, None))
    store.execute(f"INSERT INTO {store.t('run_log')} VALUES (?,?,?,?,?)",
                  (key, now, "ERROR", "service", message[:2000]))
    store.commit()


def ack_alarm(store: "Store", asset_key: str, start_ts: str, by: str, note: str) -> int:
    """Acknowledge one alarm episode (identified by its start timestamp)."""
    now = datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")
    cur = store.con.cursor()
    cur.execute(f"UPDATE {store.t('alarms')} SET ack_by = ?, ack_at = ?, ack_note = ? "
                f"WHERE asset_key = ? AND start_ts = ?",
                (by, now, note, asset_key, start_ts))
    n = cur.rowcount
    store.commit()
    return n


def get_service_state(store: "Store", default_tick_minutes: int = 15) -> dict:
    """Single-row service state; seeded on first read (starts paused to require explicit user action)."""
    cur = store.con.cursor()
    cur.execute(f"SELECT paused, tick_minutes, last_tick_at, last_tick_duration_s, started_at "
                f"FROM {store.t('service_state')} WHERE id = 1")
    row = cur.fetchone()
    if row is None:
        now = datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")
        store.execute(f"INSERT INTO {store.t('service_state')} "
                      f"(id, paused, tick_minutes, started_at) VALUES (1, 1, ?, ?)",
                      (int(default_tick_minutes), now))
        store.commit()
        return {"paused": 1, "tick_minutes": int(default_tick_minutes),
                "last_tick_at": None, "last_tick_duration_s": None, "started_at": now}
    return {"paused": int(row[0]), "tick_minutes": int(row[1]),
            "last_tick_at": str(row[2]) if row[2] is not None else None,
            "last_tick_duration_s": float(row[3]) if row[3] is not None else None,
            "started_at": str(row[4]) if row[4] is not None else None}


def set_service_state(store: "Store", **fields) -> None:
    allowed = {"paused", "tick_minutes", "last_tick_at", "last_tick_duration_s", "started_at"}
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"unknown service_state fields: {bad}")
    sets = ", ".join(f"{k} = ?" for k in fields)
    store.execute(f"UPDATE {store.t('service_state')} SET {sets} WHERE id = 1",
                  tuple(fields.values()))
    store.commit()


def prune_history(store: "Store", retention_days: float) -> None:
    """Drop runs/run_log older than the retention horizon (service path only)."""
    cutoff = pd.Timestamp.now(tz=timezone.utc).tz_localize(None) - pd.Timedelta(days=retention_days)
    cut = cutoff.isoformat(sep=" ", timespec="seconds")
    store.execute(f"DELETE FROM {store.t('runs')} WHERE started_at < ?", (cut,))
    store.execute(f"DELETE FROM {store.t('run_log')} WHERE ts < ?", (cut,))
    store.commit()


def sync_config(store: "Store", csv_path: Path) -> None:
    """Sync the human config file (configs/config_table.csv) into SQL so what
    ACM runs with is visible next to its results."""
    import csv as _csv
    now = datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = [r for r in _csv.DictReader(f)]
    store.execute(f"DELETE FROM {store.t('config')}")
    dedup = {}
    for r in rows:
        if r.get("EquipID") in ("0", None):
            dedup[(r["Category"], r["ParamPath"])] = (r["ParamValue"], r["ValueType"])
    store.executemany(
        f"INSERT INTO {store.t('config')} VALUES (?,?,?,?,?)",
        [(c, p, v, t, now) for (c, p), (v, t) in dedup.items()])
    store.commit()
    print(f"\x1b[2m  ✓  Config synced  ·  {len(rows)} params  ·  {store.backend}\x1b[0m", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest", help="load benchmark artifacts into the store")
    p.add_argument("--results-dir", required=True)
    p.add_argument("--farm", required=True)
    c = sub.add_parser("sync-config", help="sync configs/config_table.csv into the store")
    c.add_argument("--config-csv", default=str(Path(__file__).resolve().parents[1] / "configs" / "config_table.csv"))
    for sp in (p, c):
        sp.add_argument("--backend", choices=["sqlite", "mssql"], default="sqlite")
        sp.add_argument("--db", default="acm_results.db")
        sp.add_argument("--conn", default=None, help="pyodbc connection string (mssql backend)")
    args = ap.parse_args()
    store = Store(args.backend, db=args.db, conn_str=args.conn)
    try:
        if args.cmd == "ingest":
            ingest(Path(args.results_dir), args.farm, store)
        elif args.cmd == "sync-config":
            sync_config(store, Path(args.config_csv))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

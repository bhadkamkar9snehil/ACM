# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
ACM Database Health Check
=========================
Queries all key ACM output tables for a given equipment and prints a
structured report: row counts, date ranges, and correctness checks.

Usage:
    python scripts/db_health_check.py                          # All WFA turbines
    python scripts/db_health_check.py --equip WFA_TURBINE_10   # One turbine
    python scripts/db_health_check.py --equip WFA_TURBINE_10 WFA_TURBINE_0
    python scripts/db_health_check.py --all                    # All equipment in DB

Output:
    Console table + optional --csv path for saving.
"""
from __future__ import annotations

import argparse
import configparser
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── path setup ─────────────────────────────────────────────────────────────
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

import pyodbc

# Force UTF-8 output on Windows so box-drawing characters don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ── connection ──────────────────────────────────────────────────────────────

def get_connection() -> pyodbc.Connection:
    cfg = configparser.ConfigParser()
    cfg.read(project_root / "configs" / "sql_connection.ini")
    s = cfg["acm"]
    conn_str = (
        f"DRIVER={s['driver']};"
        f"SERVER={s['server']};"
        f"DATABASE={s['database']};"
        f"Trusted_Connection=yes;"
        f"TrustServerCertificate=yes;"
        f"MARS_Connection=yes"
    )
    return pyodbc.connect(conn_str, timeout=30)


# ── helpers ─────────────────────────────────────────────────────────────────

def fmt_date(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    return str(v)[:16]


def fmt_int(v) -> str:
    if v is None:
        return "—"
    return f"{int(v):,}"


def col(width: int, text: str, right: bool = False) -> str:
    s = str(text)
    if right:
        return s.rjust(width)
    return s.ljust(width)


# ── per-equipment report ────────────────────────────────────────────────────

def check_equipment(cur: pyodbc.Cursor, equip_code: str, equip_id: int) -> None:
    sep = "─" * 100
    print(f"\n{'═' * 100}")
    print(f"  {equip_code}  (EquipID={equip_id})")
    print(f"{'═' * 100}")

    # ── 1. Run summary ──────────────────────────────────────────────────────
    cur.execute("""
        SELECT COUNT(*), MIN(StartedAt), MAX(StartedAt),
               MAX(CompletedAt), SUM(ScoreRowCount), SUM(EpisodeCount),
               AVG(AvgHealthIndex), MAX(MaxFusedZ)
        FROM ACM_Runs WHERE EquipID = ?
    """, equip_id)
    r = cur.fetchone()
    total_runs, first_run, last_run, last_complete, total_rows, total_eps, avg_h, max_z = r
    print(f"\n  RUNS")
    print(f"  {'Total runs:':<30} {fmt_int(total_runs)}")
    print(f"  {'First run:':<30} {fmt_date(first_run)}")
    print(f"  {'Last run:':<30} {fmt_date(last_run)}")
    print(f"  {'Last completed:':<30} {fmt_date(last_complete)}")
    print(f"  {'Total rows scored:':<30} {fmt_int(total_rows)}")
    print(f"  {'Total episodes:':<30} {fmt_int(total_eps)}")
    if avg_h is not None:
        print(f"  {'Avg health index:':<30} {avg_h:.1f}")
    if max_z is not None:
        print(f"  {'Max fused-Z (all time):':<30} {max_z:.2f}")

    # In-progress run?
    cur.execute("SELECT COUNT(*) FROM ACM_Runs WHERE EquipID=? AND CompletedAt IS NULL", equip_id)
    in_prog = cur.fetchone()[0]
    if in_prog:
        print(f"  {'🔄 Runs in progress:':<30} {in_prog}")

    # ── 2. Model lifecycle ──────────────────────────────────────────────────
    cur.execute("""
        SELECT TOP 1 RegimeMaturityState, ConsecutiveRuns, TotalRuns,
                     TrainingRows, SilhouetteScore, StabilityRatio,
                     RegimeQualityMetric, CreatedAt
        FROM ACM_ActiveModels WHERE EquipID=? ORDER BY CreatedAt DESC
    """, equip_id)
    r = cur.fetchone()
    print(f"\n  MODEL LIFECYCLE")
    if r:
        state, consec, total_r, train_rows, silh, stab, rqm, created = r
        state_icon = {"CONVERGED": "✅", "LEARNING": "🟡", "COLDSTART": "🔴", "INITIALIZING": "🔴"}.get(state, "?")
        print(f"  {'State:':<30} {state_icon} {state}  (created {fmt_date(created)})")
        print(f"  {'Consecutive runs:':<30} {consec}/{total_r}")
        print(f"  {'Training rows:':<30} {fmt_int(train_rows)}")
        if silh is not None:
            print(f"  {'Silhouette score:':<30} {silh:.4f}{'  ✅' if silh >= 0.15 else '  ⚠️ below 0.15'}")
        if stab is not None:
            print(f"  {'Stability ratio:':<30} {stab:.2f}{'  ✅' if stab >= 0.60 else '  ⚠️ below 0.60'}")
        if rqm is not None:
            print(f"  {'Regime quality metric:':<30} {rqm}")
    else:
        print(f"  {'State:':<30} ❌ No model record")

    # ── 3. Output tables ────────────────────────────────────────────────────
    print(f"\n  OUTPUT TABLES")
    hdr = f"  {'Table':<32} {'Rows':>10}  {'From':>16}  {'To':>16}  {'Notes'}"
    print(hdr)
    print(f"  {sep}")

    tables_ts = [
        ("ACM_HealthTimeline",      "Timestamp"),
        ("ACM_Scores_Wide",         "Timestamp"),
        ("ACM_RegimeTimeline",      "Timestamp"),
        ("ACM_ContributionTimeline","Timestamp"),
        ("ACM_DriftSeries",         "Timestamp"),
        ("ACM_SensorNormalized_TS", "Timestamp"),
    ]
    for tname, tcol_name in tables_ts:
        try:
            cur.execute(f"""
                SELECT COUNT(*), MIN({tcol_name}), MAX({tcol_name})
                FROM {tname} WHERE EquipID=?
            """, equip_id)
            cnt, t0, t1 = cur.fetchone()
            note = ""
            if cnt == 0:
                note = "⚠️ EMPTY"
            print(f"  {tname:<32} {fmt_int(cnt):>10}  {fmt_date(t0):>16}  {fmt_date(t1):>16}  {note}")
        except Exception as e:
            print(f"  {tname:<32} {'ERROR':>10}  {str(e)[:40]}")

    # Episode-based tables
    tables_ep = [
        ("ACM_Episodes",    "StartTime"),
        ("ACM_RunMetrics",  None),
    ]
    for tname, tcol_name in tables_ep:
        try:
            if tcol_name:
                cur.execute(f"""
                    SELECT COUNT(*), MIN({tcol_name}), MAX({tcol_name})
                    FROM {tname} WHERE EquipID=?
                """, equip_id)
                cnt, t0, t1 = cur.fetchone()
            else:
                cur.execute(f"SELECT COUNT(*) FROM {tname} WHERE EquipID=?", equip_id)
                cnt = cur.fetchone()[0]; t0 = t1 = None
            note = "⚠️ EMPTY" if cnt == 0 else ""
            print(f"  {tname:<32} {fmt_int(cnt):>10}  {fmt_date(t0):>16}  {fmt_date(t1):>16}  {note}")
        except Exception as e:
            print(f"  {tname:<32} {'ERROR':>10}  {str(e)[:40]}")

    # Row-only tables
    for tname in ["ACM_SensorDefects", "ACM_SensorHotspots", "ACM_DetectorCorrelation",
                  "ACM_CalibrationSummary", "ACM_SensorCorrelations"]:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {tname} WHERE EquipID=?", equip_id)
            cnt = cur.fetchone()[0]
            note = "⚠️ EMPTY" if cnt == 0 else ""
            print(f"  {tname:<32} {fmt_int(cnt):>10}  {'—':>16}  {'—':>16}  {note}")
        except Exception as e:
            print(f"  {tname:<32} {'ERROR':>10}  {str(e)[:40]}")

    # ── 4. Episodes breakdown ───────────────────────────────────────────────
    cur.execute("""
        SELECT COUNT(*), MAX(Severity) AS MaxSev,
               SUM(DurationHours) AS TotalHrs,
               MIN(StartTime), MAX(StartTime)
        FROM ACM_Episodes WHERE EquipID=?
    """, equip_id)
    r = cur.fetchone()
    if r and r[0]:
        cnt, max_sev, total_hrs, ep_first, ep_last = r
        print(f"\n  EPISODES")
        print(f"  {'Total episodes:':<30} {fmt_int(cnt)}")
        print(f"  {'Max severity:':<30} {max_sev or '—'}")
        total_hrs_val = total_hrs if total_hrs else 0
        print(f"  {'Total duration (hrs):':<30} {total_hrs_val:.1f}")
        print(f"  {'Date range:':<30} {fmt_date(ep_first)} → {fmt_date(ep_last)}")

        # Severity breakdown
        cur.execute("""
            SELECT Severity, COUNT(*) AS Cnt
            FROM ACM_Episodes WHERE EquipID=?
            GROUP BY Severity ORDER BY
            CASE Severity WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                          WHEN 'MEDIUM' THEN 3 WHEN 'LOW' THEN 4 ELSE 5 END
        """, equip_id)
        rows = cur.fetchall()
        sev_parts = [f"{sev}: {cnt2}" for sev, cnt2 in rows]
        print(f"  {'By severity:':<30} {', '.join(sev_parts)}")

        # Top detector
        cur.execute("""
            SELECT TOP 1 PrimaryDetector, COUNT(*) AS Cnt
            FROM ACM_Episodes WHERE EquipID=?
            GROUP BY PrimaryDetector ORDER BY Cnt DESC
        """, equip_id)
        r2 = cur.fetchone()
        if r2:
            print(f"  {'Top detector:':<30} {r2[0]} ({fmt_int(r2[1])} episodes)")

    # ── 5. Drift status ─────────────────────────────────────────────────────
    cur.execute("""
        SELECT TOP 1 ControllerState, CONVERT(varchar(19), CreatedAt, 120)
        FROM ACM_DriftController WHERE EquipID=? ORDER BY CreatedAt DESC
    """, equip_id)
    r = cur.fetchone()
    if r:
        drift_icon = {"NORMAL": "✅", "WARNING": "🟡", "FAULT": "🔴"}.get(r[0], "?")
        print(f"\n  DRIFT STATE:  {drift_icon} {r[0]}  (as of {r[1]})")

    # ── 6. Config ───────────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM ACM_Config WHERE EquipID=?", equip_id)
    cfg_cnt = cur.fetchone()[0]
    print(f"\n  ACM_Config params loaded: {fmt_int(cfg_cnt)}")

    # ── 7. Historian coverage ───────────────────────────────────────────────
    print(f"\n  HISTORIAN DATA")
    table_name = f"{equip_code}_Data"
    try:
        cur.execute(f"SELECT COUNT(*), MIN(EntryDateTime), MAX(EntryDateTime) FROM [{table_name}]")
        cnt, t0, t1 = cur.fetchone()
        if cnt == 0:
            print(f"  ⚠️  {table_name}: EMPTY — no historian data")
        else:
            print(f"  {table_name}: {fmt_int(cnt)} rows  |  {fmt_date(t0)} → {fmt_date(t1)}")
    except Exception:
        print(f"  ❌  {table_name}: table not found")

    # ── 8. Run logs ─────────────────────────────────────────────────────────
    cur.execute("""
        SELECT COUNT(*) FROM ACM_RunLogs rl
        JOIN ACM_Runs r ON r.RunID = rl.RunID
        WHERE r.EquipID = ?
    """, equip_id)
    log_cnt = cur.fetchone()[0]
    print(f"  ACM_RunLogs entries:  {fmt_int(log_cnt)}")

    # ── 9. Recent errors ────────────────────────────────────────────────────
    cur.execute("""
        SELECT TOP 5 CONVERT(varchar(19), rl.LoggedAt, 120), rl.Component, LEFT(rl.Message, 80)
        FROM ACM_RunLogs rl
        JOIN ACM_Runs r ON r.RunID = rl.RunID
        WHERE r.EquipID = ? AND rl.Level = 'ERROR'
        ORDER BY rl.LoggedAt DESC
    """, equip_id)
    errors = cur.fetchall()
    if errors:
        print(f"\n  RECENT ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    {e[0]}  [{e[1]}]  {e[2]}")
    else:
        print(f"\n  No errors in ACM_RunLogs.")


# ── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ACM Database Health Check")
    parser.add_argument("--equip", nargs="*", help="Equipment code(s) to check")
    parser.add_argument("--all", action="store_true", help="Check all equipment in DB")
    parser.add_argument("--csv", help="Save results to CSV file (future feature)")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Resolve equipment list
    if args.all or (not args.equip):
        # Default: equipment that has at least one ACM run (asset-agnostic)
        cur.execute("""
            SELECT DISTINCT e.EquipCode, e.EquipID
            FROM Equipment e
            WHERE EXISTS (SELECT 1 FROM ACM_Runs r WHERE r.EquipID = e.EquipID)
            ORDER BY e.EquipID
        """)
    else:
        placeholders = ",".join("?" * len(args.equip))
        cur.execute(f"""
            SELECT EquipCode, EquipID FROM Equipment
            WHERE EquipCode IN ({placeholders})
            ORDER BY EquipID
        """, *args.equip)

    equipment = cur.fetchall()
    if not equipment:
        print("No equipment found.")
        conn.close()
        return

    print(f"\nACM DATABASE HEALTH CHECK — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Checking {len(equipment)} equipment record(s)\n")

    for equip_code, equip_id in equipment:
        check_equipment(cur, equip_code, equip_id)

    print(f"\n{'═' * 100}")
    print(f"  Done. {len(equipment)} equipment checked.")
    print(f"{'═' * 100}\n")

    conn.close()


if __name__ == "__main__":
    main()

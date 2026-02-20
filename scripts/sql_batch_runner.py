"""SQL Batch Runner - Continuous ACM processing from SQL historian with smart coldstart.

This script runs ACM continuously from SQL mode, handling:
1. Cold start - repeatedly calls ACM until coldstart completes successfully
2. Batch processing - processes all available data in tick-sized windows
3. Progress tracking - resumes from last successful batch

Usage examples:
    # Process single equipment until all data analyzed
    python scripts/sql_batch_runner.py --equip FD_FAN
    
    # Process multiple equipment in parallel
    python scripts/sql_batch_runner.py --equip FD_FAN GAS_TURBINE --max-workers 2
    
    # Resume from last successful run
    python scripts/sql_batch_runner.py --equip FD_FAN --resume
    
    # Dry run to see what would be processed
    python scripts/sql_batch_runner.py --equip FD_FAN --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
import os
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pyodbc
import numpy as np

# Ensure project root is on sys.path so `core` imports work when running as a script
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.output_manager import ALLOWED_TABLES
from core.observability import (
    Console, 
    init as init_observability, 
    shutdown as shutdown_observability,
    record_run,
    record_error,
    start_profiling,
    stop_profiling,
    get_trace_context,  # For propagating trace context to subprocess
)


class SQLBatchRunner:
    """Manages continuous batch processing from SQL historian."""
    
    def __init__(self, 
                 sql_conn_string: str,
                 artifact_root: Path,
                 tick_minutes: int = 240,
                 max_coldstart_attempts: int = 10,
                 max_batches: Optional[int] = None,
                 start_from_beginning: bool = False,
                 ):
        """Initialize batch runner.

        Args:
            sql_conn_string: SQL Server connection string
            artifact_root: Root directory for artifacts
            tick_minutes: Window size in minutes (default: 30)
            max_coldstart_attempts: Max attempts to complete coldstart (default: 10)
        """
        self.sql_conn_string = sql_conn_string
        self.artifact_root = artifact_root
        self.tick_minutes = tick_minutes
        self.max_coldstart_attempts = max_coldstart_attempts
        self.progress_file = artifact_root / ".sql_batch_progress.json"
        self.max_batches = max_batches
        self.start_from_beginning = start_from_beginning

    def _log_historian_overview(self, equip_name: str) -> bool:
        """Preflight: Log historian table coverage and return True when data exists.

        This helps quickly diagnose cases where batch runs appear to succeed
        but no outputs are written because the historian query returns no rows.
        """
        try:
            table_name = f"{equip_name}_Data"
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT MIN(EntryDateTime), MAX(EntryDateTime), COUNT(*) FROM {table_name}")
                row = cur.fetchone()
                if not row:
                    Console.warn(f"{equip_name}: Historian table query returned no result", component="PRECHECK", equipment=equip_name)
                    return False
                min_ts, max_ts, total_rows = row[0], row[1], int(row[2]) if row[2] is not None else 0
                if not min_ts or not max_ts:
                    Console.warn(f"{equip_name}: Historian table has no min/max timestamps", component="PRECHECK", equipment=equip_name)
                    return False
                if total_rows <= 0:
                    Console.warn(
                        f"{equip_name}: Historian table has 0 rows; skipping processing",
                        component="PRECHECK", equipment=equip_name,
                    )
                    Console.info(
                        f"{equip_name}: Ensure raw table {table_name} is populated for the expected window",
                        component="PRECHECK", equipment=equip_name,
                        table=table_name,
                    )
                    return False
                Console.info(
                    f"{equip_name}: Historian coverage OK - range=[{min_ts},{max_ts}], rows={total_rows}",
                    component="PRECHECK", equipment=equip_name,
                    min_timestamp=min_ts,
                    max_timestamp=max_ts,
                    total_rows=total_rows,
                )
                return True
        except Exception as e:
            Console.warn(f"{equip_name}: Historian overview failed: {e}", component="PRECHECK", equipment=equip_name, error=str(e))
            return False
    
    def _get_sql_connection(self) -> pyodbc.Connection:
        """Create SQL connection with a short timeout."""
        # Use the pyodbc timeout parameter instead of a custom
        # connection-string attribute to avoid driver errors.
        return pyodbc.connect(self.sql_conn_string, timeout=10)

    def _test_sql_connection(self) -> bool:
        """Quick sanity check that SQL is reachable.

        This is used once per equipment run so that connection issues are
        clearly reported up front instead of being hit repeatedly inside the
        coldstart loop.
        """
        try:
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
            Console.info("Connection test OK", component="SQL")
            return True
        except Exception as exc:
            Console.error(f"SQL connection test failed: {exc}", component="SQL", error=str(exc), error_type=type(exc).__name__)
            return False

    # ------------------------
    # SQL helpers (config/progress)
    # ------------------------
    def _get_equip_id(self, equip_name: str) -> Optional[int]:
        """Resolve or register EquipID for a given equipment code.

        Prefers calling dbo.usp_ACM_RegisterEquipment to create/return a stable ID.
        Falls back to reading from dbo.Equipment when the procedure isn't available.
        """
        try:
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                # Try registration procedure first (preferred)
                try:
                    tsql = (
                        "DECLARE @EID INT;\n"
                        "EXEC dbo.usp_ACM_RegisterEquipment @EquipCode = ?, @EquipID = @EID OUTPUT;\n"
                        "SELECT @EID;"
                    )
                    cur.execute(tsql, (equip_name,))
                    row = cur.fetchone()
                    if row and row[0] is not None:
                        eid = int(row[0])
                        Console.info(f"Registered/Resolved EquipID={eid} for {equip_name}", component="ID", equipment=equip_name, equip_id=eid)
                        return eid
                except Exception:
                    # Fall back to direct lookup when SP missing or errors
                    pass

                # Fallback: direct lookup
                try:
                    cur.execute("SELECT EquipID FROM dbo.Equipment WHERE EquipCode = ?", (equip_name,))
                    row = cur.fetchone()
                    return int(row[0]) if row else None
                except Exception:
                    return None
        except Exception as e:
            Console.warn(f"Could not resolve EquipID for {equip_name}: {e}", component="ID", equipment=equip_name, error=str(e), error_type=type(e).__name__)
            return None

    def _get_config_int(self, equip_id: int, param_path: str, default_value: int) -> int:
        """Fetch integer config value from ACM_Config for an equipment, with default fallback."""
        try:
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT TOP 1 ParamValue FROM dbo.ACM_Config WHERE EquipID = ? AND ParamPath = ? ORDER BY UpdatedAt DESC",
                    (equip_id, param_path)
                )
                row = cur.fetchone()
                if row and row[0] is not None:
                    try:
                        return int(row[0])
                    except ValueError:
                        return default_value
        except Exception as e:
            Console.warn(f"Could not read config {param_path} for EquipID={equip_id}: {e}", component="CONFIG", equip_id=equip_id, param_path=param_path, error=str(e))
        return default_value

    def _set_tick_minutes(self, equip_id: int, minutes: int, log: bool = True) -> None:
        """Upsert runtime.tick_minutes in ACM_Config for the equipment (patched: no Category/ChangeReason)."""
        try:
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                # Try update first
                cur.execute(
                    "UPDATE dbo.ACM_Config SET ParamValue = ?, UpdatedAt = SYSUTCDATETIME() "
                    "WHERE EquipID = ? AND ParamPath = 'runtime.tick_minutes'",
                    (str(minutes), equip_id)
                )
                if cur.rowcount == 0:
                    # Insert (patched: only valid columns)
                    cur.execute(
                        "INSERT INTO dbo.ACM_Config (EquipID, ParamPath, ParamValue, ValueType, UpdatedBy, UpdatedAt) "
                        "VALUES (?, 'runtime.tick_minutes', ?, 'int', 'sql_batch_runner', SYSUTCDATETIME())",
                        (equip_id, str(minutes))
                    )
                conn.commit()
                if log:
                    Console.info(f"Set tick_minutes={minutes} for EquipID={equip_id}", component="CONFIG", tick_minutes=minutes, equip_id=equip_id)
        except Exception as e:
            Console.warn(f"Could not set tick_minutes for EquipID={equip_id}: {e}", component="CONFIG", equip_id=equip_id, error=str(e), error_type=type(e).__name__)

    def _infer_tick_minutes_from_raw(self, equip_name: str, target_rows_per_batch: int = 5000) -> int:
        """Infer a reasonable tick size (minutes) from historian stats."""
        try:
            table_name = f"{equip_name}_Data"
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"SELECT MIN(EntryDateTime), MAX(EntryDateTime), COUNT(*) FROM {table_name}"
                )
                row = cur.fetchone()
                cur.close()
            if not row or not row[0] or not row[1] or not row[2]:
                return self.tick_minutes

            min_ts, max_ts, total_rows = row[0], row[1], int(row[2])
            total_minutes = max((max_ts - min_ts).total_seconds() / 60.0, 1.0)
            rows_per_minute = total_rows / total_minutes if total_minutes > 0 else 0.0
            if rows_per_minute <= 0:
                return self.tick_minutes

            # Require a small but non-zero sample per batch so SQL loads don't NOOP.
            min_rows_per_batch = 12  # prevents ACM from bailing on <10-row windows
            cadence_minutes = 1.0 / rows_per_minute if rows_per_minute > 0 else 30.0
            min_tick = int(max(5, math.ceil(min_rows_per_batch * cadence_minutes)))

            inferred = int(max(1, round(target_rows_per_batch / rows_per_minute)))
            max_tick = int(os.getenv("ACM_SQL_MAX_TICK_MINUTES", "1440"))  # allow up to 24h windows
            inferred = max(min_tick, min(inferred, max_tick))

            clamped = inferred == max_tick
            Console.info(
                f"Inferred tick_minutes={inferred} for {equip_name} "
                f"(rows={total_rows}, minutes={total_minutes:.1f}, cadence={cadence_minutes:.2f}m)"
                + (f" [clamped to max={max_tick}]" if clamped else ""),
                component="CONFIG", tick_minutes=inferred, equipment=equip_name, total_rows=total_rows, clamped=clamped
            )
            return inferred
        except Exception as e:
            Console.warn(f"Could not infer tick_minutes from raw table for {equip_name}: {e}", component="CONFIG", equipment=equip_name, error=str(e), error_type=type(e).__name__)
            return self.tick_minutes

    def _truncate_outputs_for_equip(self, equip_id: int) -> None:
        """
        Development helper: delete existing outputs for an equipment from ACM
        analytical tables so a dev batch run starts from a clean slate.
        
        Uses batched deletes for large tables to avoid transaction log bloat.
        """
        try:
            tables_list = sorted(ALLOWED_TABLES)
            total_tables = len(tables_list)
            
            # Large tables that need batched deletion (can have millions of rows)
            large_tables = {
                'ACM_BaselineBuffer', 'ACM_SensorNormalized_TS', 'ACM_OMRContributionsLong',
                'ACM_PCA_Loadings', 'ACM_Scores_Long', 'ACM_ContributionTimeline',
                'ACM_RunLogs', 'ACM_SensorHotspotTimeline', 'ACM_HealthForecast',
                'ACM_FailureForecast', 'ACM_Scores_Wide'
            }
            
            # Track deletions for summary
            tables_cleared = 0
            total_rows_deleted = 0
            significant_deletions: list[tuple[str, int]] = []  # Tables with >100 rows
            
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                for idx, table in enumerate(tables_list, 1):
                    try:
                        # Check if table exists and has EquipID column
                        cur.execute(
                            f"SELECT CASE WHEN OBJECT_ID('dbo.{table}', 'U') IS NOT NULL "
                            f"AND COL_LENGTH('dbo.{table}', 'EquipID') IS NOT NULL THEN 1 ELSE 0 END"
                        )
                        can_delete = cur.fetchone()[0]
                        if not can_delete:
                            continue
                        
                        # For large tables, use batched delete to avoid massive transaction log
                        if table in large_tables:
                            batch_size = 50000
                            table_deleted = 0
                            while True:
                                cur.execute(
                                    f"DELETE TOP ({batch_size}) FROM dbo.{table} WHERE EquipID = ?",
                                    (equip_id,),
                                )
                                rows = cur.rowcount
                                table_deleted += rows
                                conn.commit()  # Commit each batch to release transaction log
                                if rows < batch_size:
                                    break
                            if table_deleted > 0:
                                tables_cleared += 1
                                total_rows_deleted += table_deleted
                                if table_deleted > 100:
                                    significant_deletions.append((table, table_deleted))
                        else:
                            # Small tables - single delete
                            cur.execute(
                                f"DELETE FROM dbo.{table} WHERE EquipID = ?",
                                (equip_id,),
                            )
                            rows_deleted = cur.rowcount
                            if rows_deleted > 0:
                                tables_cleared += 1
                                total_rows_deleted += rows_deleted
                                if rows_deleted > 100:
                                    significant_deletions.append((table, rows_deleted))
                            conn.commit()
                    except Exception as tbl_err:
                        Console.warn(f"Failed to truncate {table}: {tbl_err}", component="RESET", table=table, equip_id=equip_id, error=str(tbl_err), error_type=type(tbl_err).__name__)
            
            # Single summary message
            if significant_deletions:
                # Sort by row count descending, show top 5
                significant_deletions.sort(key=lambda x: x[1], reverse=True)
                top_tables = ", ".join(f"{t}={r:,}" for t, r in significant_deletions[:5])
                Console.ok(
                    f"Cold-start reset: cleared {tables_cleared} tables ({total_rows_deleted:,} rows) for EquipID={equip_id} [top: {top_tables}]",
                    component="RESET", equip_id=equip_id, tables_cleared=tables_cleared, total_rows=total_rows_deleted
                )
            else:
                Console.ok(
                    f"Cold-start reset: cleared {tables_cleared} tables ({total_rows_deleted:,} rows) for EquipID={equip_id}",
                    component="RESET", equip_id=equip_id, tables_cleared=tables_cleared, total_rows=total_rows_deleted
                )
        except Exception as e:
            Console.warn(f"Failed to truncate outputs for EquipID={equip_id}: {e}", component="RESET", equip_id=equip_id, error=str(e), error_type=type(e).__name__)

    def _delete_models_for_equip(self, equip_id: int) -> None:
        """
        Delete existing models for an equipment from SQL ModelRegistry
        so coldstart truly rebuilds from scratch (SQL-ONLY MODE).
        """
        try:
            # Delete from SQL ModelRegistry
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "IF OBJECT_ID('dbo.ModelRegistry', 'U') IS NOT NULL "
                    "DELETE FROM dbo.ModelRegistry WHERE EquipID = ?",
                    (equip_id,),
                )
                deleted_count = cur.rowcount
                conn.commit()
            Console.ok(f"Cold-start reset: deleted {deleted_count} cached models for EquipID={equip_id}", component="RESET", equip_id=equip_id, deleted_count=deleted_count)
                
        except Exception as e:
            Console.warn(f"Failed to delete models for EquipID={equip_id}: {e}", component="RESET", equip_id=equip_id, error=str(e), error_type=type(e).__name__)

    def _inspect_last_run_outputs(self, equip_name: str) -> None:
        """
        Lightweight QA: after a batch run, report row counts in key tables for
        the last RunID for this equipment so a dev can spot anomalies.
        """
        try:
            equip_id = self._get_equip_id(equip_name)
            if not equip_id:
                Console.warn(f"EquipID not found for {equip_name}, skipping output inspection", component="QA", equipment=equip_name)
                return
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                # Prefer deriving the latest RunID from freshly written forecast tables
                # to avoid mismatches when ACM_Runs ordering differs.
                run_id = None
                run_source = None
                # Try ACM_HealthForecast_TS first
                try:
                    cur.execute(
                        """
                        IF OBJECT_ID('dbo.ACM_HealthForecast_TS','U') IS NOT NULL
                        BEGIN
                          IF EXISTS(SELECT 1 FROM dbo.ACM_HealthForecast_TS WHERE EquipID = ?)
                          BEGIN
                            IF COL_LENGTH('dbo.ACM_HealthForecast_TS','CreatedAt') IS NOT NULL
                              SELECT TOP 1 RunID FROM dbo.ACM_HealthForecast_TS WHERE EquipID = ? GROUP BY RunID ORDER BY MAX(CreatedAt) DESC;
                            ELSE
                              SELECT TOP 1 RunID FROM dbo.ACM_HealthForecast_TS WHERE EquipID = ? GROUP BY RunID ORDER BY MAX([Timestamp]) DESC;
                          END
                          ELSE SELECT CAST(NULL AS UNIQUEIDENTIFIER);
                        END
                        ELSE SELECT CAST(NULL AS UNIQUEIDENTIFIER);
                        """,
                        (equip_id, equip_id, equip_id),
                    )
                    r = cur.fetchone()
                    if r and r[0]:
                        run_id = r[0]
                        run_source = "ACM_HealthForecast_TS"
                except Exception:
                    pass

                # Fallback: derive from ACM_FailureForecast_TS
                if run_id is None:
                    try:
                        cur.execute(
                            """
                            IF OBJECT_ID('dbo.ACM_FailureForecast_TS','U') IS NOT NULL
                            BEGIN
                              IF EXISTS(SELECT 1 FROM dbo.ACM_FailureForecast_TS WHERE EquipID = ?)
                              BEGIN
                                IF COL_LENGTH('dbo.ACM_FailureForecast_TS','CreatedAt') IS NOT NULL
                                  SELECT TOP 1 RunID FROM dbo.ACM_FailureForecast_TS WHERE EquipID = ? GROUP BY RunID ORDER BY MAX(CreatedAt) DESC;
                                ELSE
                                  SELECT TOP 1 RunID FROM dbo.ACM_FailureForecast_TS WHERE EquipID = ? GROUP BY RunID ORDER BY MAX([Timestamp]) DESC;
                              END
                              ELSE SELECT CAST(NULL AS UNIQUEIDENTIFIER);
                            END
                            ELSE SELECT CAST(NULL AS UNIQUEIDENTIFIER);
                            """,
                            (equip_id, equip_id, equip_id),
                        )
                        r = cur.fetchone()
                        if r and r[0]:
                            run_id = r[0]
                            run_source = "ACM_FailureForecast_TS"
                    except Exception:
                        pass

                # Final fallback: latest in ACM_Runs by StartedAt
                started_at = None
                completed_at = None
                if run_id is None:
                    cur.execute(
                        "SELECT TOP 1 RunID, StartedAt, CompletedAt FROM dbo.ACM_Runs WHERE EquipID = ? ORDER BY StartedAt DESC",
                        (equip_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        Console.warn(f"No ACM_Runs entry found for EquipID={equip_id}, skipping inspection", component="QA", equip_id=equip_id)
                        return
                    run_id, started_at, completed_at = row[0], row[1], row[2]
                    run_source = "ACM_Runs"

                # If we derived from forecast tables, try to enrich with window from ACM_Runs
                if started_at is None or completed_at is None:
                    try:
                        cur.execute(
                            "SELECT TOP 1 StartedAt, CompletedAt FROM dbo.ACM_Runs WHERE RunID = ?",
                            (run_id,),
                        )
                        rw = cur.fetchone()
                        if rw:
                            started_at, completed_at = rw[0], rw[1]
                    except Exception:
                        pass

                Console.info(
                    f"Inspecting outputs for EquipID={equip_id}, RunID={run_id} (from {run_source}), "
                    f"window=[{started_at},{completed_at})",
                    component="QA", equip_id=equip_id, run_id=str(run_id)
                )
                tables_to_check: List[Tuple[str, bool, bool]] = [
                    # (table, has_run_id, critical)
                    ("ACM_Scores_Wide", True, True),
                    ("ACM_HealthTimeline", True, True),
                    ("ACM_RegimeTimeline", True, True),
                    ("ACM_EpisodeDiagnostics", True, True),
                    ("ACM_Episodes", True, False),
                    ("ACM_EpisodeMetrics", True, False),
                    ("ACM_SensorNormalized_TS", True, True),
                    ("ACM_SensorCorrelations", True, False),
                    ("ACM_DetectorCorrelation", True, False),
                    ("ACM_SeasonalPatterns", True, False),
                    ("ACM_HealthForecast", True, True),
                    ("ACM_FailureForecast", True, True),
                    ("ACM_RUL", True, True),
                    ("ACM_DriftController", True, False),
                    ("ACM_RegimeDefinitions", True, False),
                    ("ACM_RegimeOccupancy", True, False),
                    ("ACM_Run_Stats", True, False),
                    ("ACM_PCA_Models", True, False),
                    ("ACM_PCA_Loadings", True, False),
                    ("ACM_PCA_Metrics", True, False),
                    ("ACM_SensorHotspots", True, False),
                    ("ACM_SensorDefects", True, False),
                ]
                for table_name, has_run, critical in tables_to_check:
                    try:
                        if has_run:
                            cur.execute(
                                f"IF OBJECT_ID('dbo.{table_name}', 'U') IS NOT NULL "
                                f"SELECT COUNT(*) FROM dbo.{table_name} WHERE EquipID = ? AND RunID = ? "
                                f"ELSE SELECT 0",
                                (equip_id, run_id),
                            )
                        else:
                            cur.execute(
                                f"IF OBJECT_ID('dbo.{table_name}', 'U') IS NOT NULL "
                                f"SELECT COUNT(*) FROM dbo.{table_name} WHERE EquipID = ? "
                                f"ELSE SELECT 0",
                                (equip_id,),
                            )
                        cnt_row = cur.fetchone()
                        count_val = int(cnt_row[0]) if cnt_row else 0
                        Console.info(
                            f"{table_name}: {count_val} row(s) for EquipID={equip_id} "
                            f"{'(RunID scoped)' if has_run else ''}",
                            component="QA", table=table_name, count=count_val, equip_id=equip_id
                        )
                        if critical and count_val == 0:
                            Console.warn(
                                f"QA check failed: {table_name} has 0 rows for EquipID={equip_id} (RunID scoped)",
                                component="QA", table=table_name, equip_id=equip_id, run_id=str(run_id)
                            )
                    except Exception as tbl_err:
                        Console.warn(f"Skipped {table_name}: {tbl_err}", component="QA", table=table_name, error=str(tbl_err), error_type=type(tbl_err).__name__)
                
                # ===== New QA Check 1: OMR Culprit Naming =====
                try:
                    # Check if there are any episodes first
                    cur.execute("SELECT COUNT(*) FROM ACM_EpisodeDiagnostics WHERE EquipID = ? AND RunID = ?", (equip_id, run_id))
                    episode_count = cur.fetchone()[0]
                    if episode_count > 0:
                        cur.execute("SELECT StartTime, EndTime, Culprits FROM ACM_EpisodeDiagnostics WHERE EquipID = ? AND RunID = ?", (equip_id, run_id))
                        episodes = cur.fetchall()
                        
                        for episode in episodes:
                            start_time, end_time, culprits = episode
                            
                            # Query scores for the episode window
                            cur.execute("""
                                SELECT AVG(ABS(ar1_z)), AVG(ABS(pca_spe_z)), AVG(ABS(pca_t2_z)), 
                                    AVG(ABS(iforest_z)), AVG(ABS(gmm_z)), AVG(ABS(omr_z))
                                FROM ACM_Scores_Wide
                                WHERE EquipID = ? AND RunID = ? AND Timestamp BETWEEN ? AND ?
                            """, (equip_id, run_id, start_time, end_time))
                            avg_scores = cur.fetchone()
                            
                            if avg_scores:
                                detector_scores = {
                                    'ar1_z': avg_scores[0], 'pca_spe_z': avg_scores[1], 'pca_t2_z': avg_scores[2],
                                    'iforest_z': avg_scores[3], 'gmm_z': avg_scores[4], 'omr_z': avg_scores[5]
                                }
                                # Filter out None values
                                detector_scores = {k: v for k, v in detector_scores.items() if v is not None}
                                if not detector_scores:
                                    continue

                                primary_detector = max(detector_scores, key=detector_scores.get)
                                
                                if primary_detector == 'omr_z' and (not culprits or not culprits.startswith('OMR')):
                                    Console.warn(
                                        f"QA check failed: OMR episode has incorrect culprit. Expected 'OMR(...)', got '{culprits}'",
                                        component="QA", table="ACM_EpisodeDiagnostics", equip_id=equip_id, run_id=str(run_id)
                                    )
                except Exception as e:
                    Console.warn(f"QA check for OMR culprit naming failed: {e}", component="QA")


                # ===== New QA Check 2: Hotspot Ranking Logic =====
                try:
                    cur.execute("SELECT RankingScore, MaxAbsZ, MaxAbsOMR FROM ACM_SensorHotspots WHERE EquipID = ? AND RunID = ? ORDER BY RankingScore DESC", (equip_id, run_id))
                    hotspots = cur.fetchall()
                    if hotspots:
                        # Check sorting
                        ranking_scores = [h.RankingScore for h in hotspots]
                        if not all(ranking_scores[i] >= ranking_scores[i+1] for i in range(len(ranking_scores)-1)):
                            Console.warn(
                                "QA check failed: ACM_SensorHotspots is not sorted by RankingScore.",
                                component="QA", table="ACM_SensorHotspots", equip_id=equip_id, run_id=str(run_id)
                            )
                        
                        # Check RankingScore calculation
                        for spot in hotspots:
                            max_abs_z = spot.MaxAbsZ if spot.MaxAbsZ is not None else 0.0
                            max_abs_omr = spot.MaxAbsOMR if spot.MaxAbsOMR is not None else 0.0
                            if not np.isclose(spot.RankingScore, max(max_abs_z, max_abs_omr)):
                                Console.warn(
                                    f"QA check failed: Hotspot RankingScore is incorrect. RankingScore={spot.RankingScore}, MaxAbsZ={spot.MaxAbsZ}, MaxAbsOMR={spot.MaxAbsOMR}",
                                    component="QA", table="ACM_SensorHotspots", equip_id=equip_id, run_id=str(run_id)
                                )
                except pyodbc.ProgrammingError as pe:
                    if "Invalid column name" in str(pe):
                        Console.warn("QA check for Hotspot Ranking skipped: RankingScore/MaxAbsOMR columns not in ACM_SensorHotspots.", component="QA")
                    else:
                        Console.warn(f"QA check for Hotspot Ranking failed: {pe}", component="QA")
                except Exception as e:
                    Console.warn(f"QA check for Hotspot Ranking failed: {e}", component="QA")

        except Exception as e:
            Console.error(f"Output inspection failed for {equip_name}: {e}", component="QA", equipment=equip_name, error=str(e), error_type=type(e).__name__)

    def _reset_progress_to_beginning(self, equip_id: int) -> None:
        """Optional: Clear Runs and Coldstart state to force start from earliest EntryDateTime."""
        try:
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                # Clear coldstart and runs for this equipment
                cur.execute("SET QUOTED_IDENTIFIER ON;")
                cur.execute("DELETE FROM dbo.ACM_ColdstartState WHERE EquipID = ?", (equip_id,))
                cur.execute("DELETE FROM dbo.ACM_Runs WHERE EquipID = ?", (equip_id,))
                conn.commit()
                Console.info(f"Cleared ACM_Runs and Coldstart for EquipID={equip_id}", component="RESET", equip_id=equip_id)
        except Exception as e:
            Console.warn(f"Could not reset progress for EquipID={equip_id}: {e}", component="RESET", equip_id=equip_id, error=str(e), error_type=type(e).__name__)
    
    def _load_progress(self) -> Dict[str, Dict]:
        """Load progress tracking state.
        
        Returns:
            Dictionary with equipment progress: {
                'FD_FAN': {
                    'coldstart_complete': True,
                    'last_batch_end': '2012-01-10 00:00:00',
                    'batches_completed': 15
                }
            }
        """
        if not self.progress_file.exists():
            return {}
        
        try:
            with open(self.progress_file, "r") as f:
                data = json.load(f)
                return data
        except (json.JSONDecodeError, OSError) as exc:
            Console.warn(f"Could not load progress file: {exc}", component="PROGRESS", error=str(exc), error_type=type(exc).__name__)
            return {}
    
    def _save_progress(self, progress: Dict[str, Dict]) -> None:
        """Save progress tracking state."""
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.progress_file, "w") as f:
                json.dump(progress, f, indent=2, default=str)
        except OSError as exc:
            Console.warn(f"Could not save progress file: {exc}", component="PROGRESS", error=str(exc), error_type=type(exc).__name__)
    
    def _get_data_range(self, equip_name: str) -> tuple[Optional[datetime], Optional[datetime]]:
        """Get the available data range from SQL historian.
        
        Args:
            equip_name: Equipment name (e.g., 'FD_FAN')
            
        Returns:
            Tuple of (min_timestamp, max_timestamp) or (None, None) if no data
        """
        try:
            conn = self._get_sql_connection()
            cur = conn.cursor()
            
            table_name = f"{equip_name}_Data"
            query = f"SELECT MIN(EntryDateTime), MAX(EntryDateTime) FROM {table_name}"
            cur.execute(query)
            row = cur.fetchone()
            
            cur.close()
            conn.close()
            
            if row and row[0] and row[1]:
                return row[0], row[1]
            return None, None
            
        except Exception as e:
            Console.error(f"Failed to get data range for {equip_name}: {e}", component="DATA", equipment=equip_name, error=str(e), error_type=type(e).__name__)
            return None, None
    
    def _check_coldstart_status(self, equip_name: str) -> tuple[bool, int, int]:
        """Check if coldstart is complete for equipment.
        
        Args:
            equip_name: Equipment name
            
        Returns:
            Tuple of (is_complete, accumulated_rows, required_rows)
        """
        Console.info(f"{equip_name}: Checking coldstart status in SQL (ModelRegistry/ACM_ColdstartState)...", component="COLDSTART", equipment=equip_name)
        try:
            conn = self._get_sql_connection()
            cur = conn.cursor()
            
            # Get EquipID from Equipment table
            cur.execute("SELECT EquipID FROM Equipment WHERE EquipCode = ?", (equip_name,))
            row = cur.fetchone()
            if not row:
                cur.close()
                conn.close()
                # When equip not found, use default min rows 50
                Console.warn(f"{equip_name}: Equipment not found in Equipment table; using default minimum rows=50", component="COLDSTART", equipment=equip_name)
                return False, 0, 50
            
            equip_id = row[0]
            
            # Check ModelRegistry for existing models
            cur.execute("""
                SELECT COUNT(*) FROM ModelRegistry 
                WHERE EquipID = ? AND ModelType IN ('pca_model', 'gmm_model', 'iforest_model')
            """, (equip_id,))
            _row_mc = cur.fetchone()
            model_count = int(_row_mc[0]) if _row_mc else 0
            
            # Check coldstart state
            cur.execute("""
                SELECT Status, AccumulatedRows, RequiredRows 
                FROM ACM_ColdstartState 
                WHERE EquipID = ? AND Stage = 'score'
            """, (equip_id,))
            row = cur.fetchone()
            
            cur.close()
            conn.close()
            
            # v11.6.4 FIX: Coldstart complete ONLY if BOTH:
            # 1. Models exist in ModelRegistry (actual proof models were trained)
            # 2. Status = COMPLETE in ACM_ColdstartState (accumulated rows >= required)
            # If Status=COMPLETE but NO models, coldstart actually failed (batch error)
            if model_count >= 3 and row and row[0] == 'COMPLETE':
                Console.info(f"{equip_name}: Detected existing models in ModelRegistry (count={model_count}) and Status=COMPLETE", component="COLDSTART", equipment=equip_name, model_count=model_count)
                return True, 0, 0
            
            # If Status=COMPLETE but NO models, log warning and treat as incomplete
            if row and row[0] == 'COMPLETE' and model_count < 3:
                Console.warn(
                    f"{equip_name}: Status=COMPLETE but only {model_count}/3 models in cache - coldstart batch likely failed",
                    component="COLDSTART", equipment=equip_name, model_count=model_count
                )
            
            # Determine required rows: prefer ColdstartState.RequiredRows, else config data.min_train_samples (default 500)
            min_required = self._get_config_int(equip_id, 'data.min_train_samples', 500)
            if row:
                status, accum_rows, req_rows = row
                required = req_rows or min_required
                is_complete = status == 'COMPLETE' and model_count >= 3  # Must have both!
                Console.info(
                    f"{equip_name}: Status={status}, "
                    f"AccumulatedRows={accum_rows or 0}, RequiredRows={required}, Models={model_count}/3",
                    component="COLDSTART", equipment=equip_name, status=status, accumulated=accum_rows or 0, required=required, model_count=model_count
                )
                return is_complete, accum_rows or 0, required
            Console.info(f"{equip_name}: No ACM_ColdstartState row; using default minimum rows={min_required}", component="COLDSTART", equipment=equip_name, min_required=min_required)
            return False, 0, min_required
            
        except Exception as e:
            Console.warn(f"Could not check coldstart status: {e}", component="COLDSTART", equipment=equip_name, error=str(e), error_type=type(e).__name__)
            return False, 0, 200  # Default minimum when SQL check fails
    
    def _run_acm_batch(self, equip_name: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None, *, dry_run: bool = False, batch_num: int = 0, is_post_coldstart: bool = False) -> tuple[bool, str]:
        """Run single ACM batch for equipment.
        
        Args:
            equip_name: Equipment name
            start_time: Optional start time override
            end_time: Optional end time override
            dry_run: If True, print command without running
            batch_num: Current batch number (for frequency control)
            is_post_coldstart: If True, coldstart already completed (use online/score-only mode)
            
        Returns:
            Tuple of (success, outcome) where outcome is 'OK', 'NOOP', or 'FAIL'
            
        v11.8.0: ADAPTIVE - No mode selection needed
        =============================================
        The pipeline automatically determines behavior based on model state and
        quality metrics. No ONLINE/OFFLINE mode distinction - acm_main decides
        adaptively whether to train or score.
        """
        cmd = [
            sys.executable, "-m", "core.acm_main",
            "--equip", equip_name,
        ]
        
        if start_time:
            cmd.extend(["--start-time", start_time.isoformat()])
        if end_time:
            cmd.extend(["--end-time", end_time.isoformat()])
        
        # v11.8.0: No mode argument - acm_main decides adaptively
        printable = " ".join(cmd)
        if dry_run:
            Console.info(f"{printable}", mode="dry-run", component="DRY")
            return True, "OK"
        
        Console.info(f"{printable}", component="RUN", command=printable)
        # Environment variables for ACM subprocess
        env = dict(os.environ)
        
        # Propagate trace context to subprocess for end-to-end trace correlation
        # This allows child process logs to be linked to the parent batch runner trace
        trace_ctx = get_trace_context()
        if trace_ctx.get("trace_id") is not None:
            env["TRACEPARENT_TRACE_ID"] = str(trace_ctx["trace_id"])
        if trace_ctx.get("span_id") is not None:
            env["TRACEPARENT_SPAN_ID"] = str(trace_ctx["span_id"])
        
        # Propagate start-from-beginning intent to forecasting layer (used to force full-history model init)
        # Note: batch_num is 0-indexed internally; display as 1-indexed for users
        display_batch = batch_num + 1
        # Only show coldstart message if this is truly a coldstart batch (not after coldstart already complete)
        is_coldstart_batch = self.start_from_beginning and batch_num == 0 and not is_post_coldstart
        if is_coldstart_batch:
            env["ACM_FORECAST_FULL_HISTORY_MODE"] = "1"
            Console.info(f"{equip_name}: Coldstart batch - training fresh models", component="BATCH", equipment=equip_name, batch_num=display_batch)
        else:
            Console.info(f"{equip_name}: Batch {display_batch} - scoring with existing models", component="BATCH", equipment=equip_name, batch_num=display_batch)

        # Track batch start time for metrics
        batch_start_time = time.time()

        # Stream child output live so devs can see progress (instead of buffering everything).
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        captured_lines: list[str] = []
        try:
            assert process.stdout is not None
            for line in process.stdout:
                # Stream child output directly to stdout (already has timestamp/level from ACMLog)
                # Don't use Console.info() which would add duplicate timestamp/level prefix
                print(line.rstrip("\n"), flush=True)
                captured_lines.append(line)
        except KeyboardInterrupt:
            process.kill()
            raise
        finally:
            if process.stdout:
                process.stdout.close()
        process.wait()

        stdout_text = "".join(captured_lines)
        # Parse outcome from logs
        outcome = "FAIL"
        if process.returncode == 0:
            for line in stdout_text.split('\n'):
                if 'outcome=OK' in line:
                    outcome = "OK"
                    break
                elif 'outcome=NOOP' in line:
                    outcome = "NOOP"
                    break
            else:
                outcome = "OK"
        
        success = process.returncode == 0

        # Calculate duration for metrics
        batch_duration = time.time() - batch_start_time if 'batch_start_time' in locals() else 0.0

        # If the batch failed or outcome was not OK/NOOP, surface logs so the
        # caller can see exactly what went wrong inside acm_main.
        if not success or outcome == "FAIL":
            Console.error(f"[RUN-DEBUG] {equip_name}: acm_main exited with code {process.returncode}", component="RUN", equipment=equip_name, return_code=process.returncode)
            if stdout_text:
                # Show only the last 20 lines to avoid duplicating the entire run output
                tail_lines = stdout_text.rstrip().splitlines()[-20:]
                Console.error(
                    f"[RUN-DEBUG] {equip_name}: --- acm_main stdout (last 20 lines) ---\n" + "\n".join(tail_lines),
                    component="RUN", equipment=equip_name,
                )
            # Record FAIL in Prometheus metrics (since acm_main didn't complete)
            record_run(equip_name, "FAIL", batch_duration)
            record_error(equip_name, f"Exit code {process.returncode}", "subprocess_failure")

        if success and outcome in ("OK", "NOOP"):
            # After a successful batch, inspect SQL outputs for this equipment
            self._inspect_last_run_outputs(equip_name)
        return success, outcome
    
    def _process_coldstart(self, equip_name: str, *, dry_run: bool = False) -> tuple[bool, Optional[datetime]]:
        """Process coldstart phase for equipment.
        
        Continuously runs ACM until coldstart completes or max attempts reached.
        
        Args:
            equip_name: Equipment name
            dry_run: If True, simulate without running
            
        Returns:
            True if coldstart completed successfully
        """
        # Use Console.header for visual separators (console-only, not logged to Loki)
        Console.header(f"[COLDSTART] Starting coldstart for {equip_name}", char="=")
        
        # Get earliest data timestamp for historical replay
        min_ts, max_ts = self._get_data_range(equip_name)
        if not min_ts or not max_ts:
            Console.error(f"{equip_name}: No data available in historian", component="COLDSTART", equipment=equip_name)
            return False, None
        
        Console.info(f"{equip_name}: Historical data range: {min_ts} to {max_ts}", component="COLDSTART", equipment=equip_name, min_ts=min_ts, max_ts=max_ts)
        
        # Start coldstart from earliest timestamp
        coldstart_start = min_ts
        # SP uses <= for end time, so we need to include the full last day
        # For a 24h window, we want [00:00:00, 23:59:59] not [00:00:00, 00:00:00]
        coldstart_end = min_ts + timedelta(minutes=self.tick_minutes) - timedelta(seconds=1)
        
        last_processed_end: Optional[datetime] = None
        for attempt in range(1, self.max_coldstart_attempts + 1):
            # Use header for attempt separators (console-only)
            Console.header(f"[COLDSTART] {equip_name}: Attempt {attempt}/{self.max_coldstart_attempts}", char="-", width=50)
            
            # Check current status
            is_complete, accum_rows, req_rows = self._check_coldstart_status(equip_name)
            if is_complete:
                Console.ok(f"{equip_name}: Coldstart COMPLETE!", component="COLDSTART", equipment=equip_name)
                # If models already existed before any processing this run, we may not
                # have a concrete window end; return whatever we last computed (likely None)
                return True, last_processed_end
            
            Console.info(f"{equip_name}: Status - {accum_rows}/{req_rows} rows accumulated", component="COLDSTART", equipment=equip_name, accumulated=accum_rows, required=req_rows)
            Console.info(f"{equip_name}: Processing window [{coldstart_start} to {coldstart_end})", component="COLDSTART", equipment=equip_name, start=coldstart_start, end=coldstart_end)
            
            # Run ACM batch with historical time window
            success, outcome = self._run_acm_batch(equip_name, start_time=coldstart_start, end_time=coldstart_end, dry_run=dry_run)
            # Track the last processed coldstart window end so batch phase can continue after it
            last_processed_end = coldstart_end
            
            if not success and outcome == "FAIL":
                Console.error(f"{equip_name}: Attempt {attempt} FAILED (error)", component="COLDSTART", equipment=equip_name, attempt=attempt)
                continue
            
            if outcome == "NOOP":
                Console.warn(f"{equip_name}: Deferred (insufficient data), will retry...", component="COLDSTART", equipment=equip_name)
                continue
            
            if outcome == "OK":
                # Check if coldstart completed
                is_complete, _, _ = self._check_coldstart_status(equip_name)
                if is_complete:
                    Console.ok(f"{equip_name}: Coldstart COMPLETE!", component="COLDSTART", equipment=equip_name)
                    return True, last_processed_end
                else:
                    Console.info(f"{equip_name}: Making progress, continuing...", component="COLDSTART", equipment=equip_name)
                    # Advance window for next coldstart attempt
                    # Add 1 second back to move to start of next day, then subtract 1 second for the end bound
                    coldstart_start = coldstart_end + timedelta(seconds=1)
                    coldstart_end = coldstart_start + timedelta(minutes=self.tick_minutes) - timedelta(seconds=1)
                    if coldstart_end > max_ts:
                        coldstart_end = max_ts
        
        Console.warn(f"{equip_name}: Max attempts ({self.max_coldstart_attempts}) reached without completion", component="COLDSTART", equipment=equip_name, max_attempts=self.max_coldstart_attempts)
        return False, last_processed_end
    
    def _process_batches(self, equip_name: str, start_from: Optional[datetime] = None, 
                        *, dry_run: bool = False, resume: bool = False) -> int:
        """Process all available data in batches.
        
        Args:
            equip_name: Equipment name
            start_from: Starting timestamp (if None, starts from beginning)
            dry_run: If True, simulate without running
            resume: If True, resume from last successful batch
            
        Returns:
            Number of batches successfully processed
        """
        Console.info(f"\n{'='*60}", component="BATCH")
        Console.info(f"Starting batch processing for {equip_name}", component="BATCH", equipment=equip_name)
        Console.info(f"{'='*60}", component="BATCH")
        
        # Get data range
        min_ts, max_ts = self._get_data_range(equip_name)
        if not min_ts or not max_ts:
            Console.warn(f"{equip_name}: No data available in historian", component="BATCH", equipment=equip_name)
            return 0
        
        Console.info(f"{equip_name}: Data available from {min_ts} to {max_ts}", component="BATCH", equipment=equip_name, min_timestamp=min_ts, max_timestamp=max_ts)
        
        # Load progress
        progress = self._load_progress()
        equip_progress = progress.get(equip_name, {})
        
        # Determine starting point
        if resume and 'last_batch_end' in equip_progress:
            current_ts = datetime.fromisoformat(equip_progress['last_batch_end'])
            batches_completed = equip_progress.get('batches_completed', 0)
            Console.info(f"{equip_name}: Resuming from {current_ts} ({batches_completed} batches already completed)", component="BATCH", equipment=equip_name, resume_from=current_ts, batches_completed=batches_completed)
        elif start_from:
            current_ts = start_from
            batches_completed = 0
        else:
            current_ts = min_ts
            batches_completed = 0
        
        # Calculate total batches
        total_minutes = max((max_ts - current_ts).total_seconds() / 60, 0)
        total_batches = int(total_minutes / self.tick_minutes) if self.tick_minutes > 0 else 0

        # If a demo cap is provided, automatically widen the batch window so
        # the full history fits in at most max_batches windows. This keeps
        # long histories from exploding into thousands of tiny batches.
        if self.max_batches is not None and self.max_batches > 0 and total_batches > self.max_batches:
            new_tick = int(math.ceil(total_minutes / self.max_batches)) or self.tick_minutes
            if new_tick > self.tick_minutes:
                Console.info(
                    f"{equip_name}: Adjusting tick_minutes from {self.tick_minutes} "
                    f"to {new_tick} to honor max-batches={self.max_batches}",
                    component="BATCH", equipment=equip_name, old_tick=self.tick_minutes, new_tick=new_tick, max_batches=self.max_batches
                )
                self.tick_minutes = new_tick
                total_batches = int(total_minutes / self.tick_minutes) if self.tick_minutes > 0 else 0
        
        Console.info(f"{equip_name}: Processing {total_batches} batch(es) ({self.tick_minutes}-minute windows)", component="BATCH", equipment=equip_name, total_batches=total_batches, tick_minutes=self.tick_minutes)
        
        # Store total for passing to child processes
        self._current_total_batches = total_batches
        
        # Process batches
        batch_num = 0
        while current_ts < max_ts:
            batch_num += 1
            # SP uses <= for end time, so subtract 1 second to get [start, end] inclusive of full last period
            next_ts = current_ts + timedelta(minutes=self.tick_minutes) - timedelta(seconds=1)
            
            # Don't go beyond available data
            if next_ts > max_ts:
                next_ts = max_ts
            
            Console.info(f"\n{equip_name}: Batch {batch_num}/{total_batches} - [{current_ts} to {next_ts}]", component="BATCH", equipment=equip_name, batch=batch_num, total=total_batches)
            
            # Run ACM (it will automatically use the current batch window from SQL)
            # Pass batches_completed (total count including previous runs) for frequency control
            # is_post_coldstart=True since _process_batches is called after coldstart completes
            success, outcome = self._run_acm_batch(equip_name, start_time=current_ts, end_time=next_ts, dry_run=dry_run, batch_num=batches_completed, is_post_coldstart=True)
            
            if not success:
                Console.error(f"{equip_name}: Batch {batch_num} FAILED", component="BATCH", equipment=equip_name, batch=batch_num)
                break
            
            batches_completed += 1
            
            # Update progress
            equip_progress['last_batch_end'] = next_ts.isoformat()
            equip_progress['batches_completed'] = batches_completed
            equip_progress['coldstart_complete'] = True
            progress[equip_name] = equip_progress
            
            if not dry_run:
                self._save_progress(progress)
            
            Console.ok(f"{equip_name}: Batch {batch_num} completed (outcome={outcome})", component="BATCH", equipment=equip_name, batch=batch_num, outcome=outcome)
            
            # Respect demo cap if provided
            if self.max_batches is not None and batch_num >= self.max_batches:
                Console.info(f"Reached max-batches cap ({self.max_batches}); stopping early", component="BATCH", max_batches=self.max_batches)
                break

            # Move to next window (add 1 second to move past the end of the current window)
            current_ts = next_ts + timedelta(seconds=1)
        
        Console.info(f"\n{equip_name}: Processed {batches_completed} batch(es)", component="BATCH", equipment=equip_name, batches_completed=batches_completed)
        return batches_completed
    
    def process_equipment(self, equip_name: str, *, dry_run: bool = False, 
                         resume: bool = False) -> bool:
        """Process single equipment through coldstart and batch phases.
        
        Args:
            equip_name: Equipment name
            dry_run: If True, simulate without running
            resume: If True, resume from last successful run
            
        Returns:
            True if processing completed successfully
        """
        import time
        start_time = time.time()
        
        # Use Console.header for visual separators (console-only, not logged to Loki)
        Console.header(f"Processing Equipment: {equip_name}", char="#")

        # Fail fast if SQL is unreachable so we do not appear hung
        if not self._test_sql_connection():
            Console.error(f"{equip_name}: Skipping processing due to SQL connection failure", component="PRECHECK", equipment=equip_name)
            return False
        
        # Load progress
        progress = self._load_progress()
        equip_progress = progress.get(equip_name, {})

        # Apply per-run configuration overrides
        equip_id = self._get_equip_id(equip_name)
        if equip_id:
            Console.info(f"{equip_name}: Resolved EquipID={equip_id}", component="PRECHECK", equipment=equip_name, equip_id=equip_id)
            # In dev mode, optionally infer tick size from raw data
            if self.start_from_beginning and not resume:
                Console.info(f"Starting from beginning for {equip_name} - performing full reset", component="RESET", equipment=equip_name)
                inferred = self._infer_tick_minutes_from_raw(equip_name)
                self.tick_minutes = inferred
                # Don't log here - will log final value after max_batches adjustment
                self._set_tick_minutes(equip_id, inferred, log=False)
                self._truncate_outputs_for_equip(equip_id)
                # CRITICAL: Delete ALL existing models from SQL ModelRegistry so first batch
                # starts with fresh coldstart training. This ensures batch 0 trains new models,
                # and subsequent batches evolve those models incrementally.
                self._delete_models_for_equip(equip_id)
                self._reset_progress_to_beginning(equip_id)
            else:
                self._set_tick_minutes(equip_id, self.tick_minutes)
            
            # CRITICAL: Adjust tick_minutes AFTER inference if max_batches specified
            # This ensures coldstart uses the same batch size as regular processing
            if self.max_batches is not None and self.max_batches > 0:
                min_ts, max_ts = self._get_data_range(equip_name)
                if min_ts and max_ts:
                    total_minutes = max((max_ts - min_ts).total_seconds() / 60, 0)
                    total_batches = int(total_minutes / self.tick_minutes) if self.tick_minutes > 0 else 0
                    if total_batches > self.max_batches:
                        new_tick = int(math.ceil(total_minutes / self.max_batches)) or self.tick_minutes
                        if new_tick > self.tick_minutes:
                            Console.info(
                                f"{equip_name}: Adjusted tick_minutes {self.tick_minutes} -> {new_tick} for max-batches={self.max_batches}",
                                component="CONFIG", equipment=equip_name, old_tick=self.tick_minutes, new_tick=new_tick, max_batches=self.max_batches
                            )
                            self.tick_minutes = new_tick
                            # Don't log again - already logged in the message above
                            self._set_tick_minutes(equip_id, new_tick, log=False)
                    else:
                        # Log final tick if no adjustment was needed
                        Console.info(f"{equip_name}: Using tick_minutes={self.tick_minutes}", component="CONFIG", equipment=equip_name, tick_minutes=self.tick_minutes)
            elif self.start_from_beginning and not resume:
                # Log final tick if no max_batches adjustment
                Console.info(f"{equip_name}: Using tick_minutes={self.tick_minutes}", component="CONFIG", equipment=equip_name, tick_minutes=self.tick_minutes)
        else:
            Console.warn(f"{equip_name}: EquipID not found in dbo.Equipment; downstream writes will fail", component="PRECHECK", equipment=equip_name)

        # Historian preflight: if no data rows, stop early with a clear message
        if not self._log_historian_overview(equip_name):
            Console.error(f"{equip_name}: Historian has no data — aborting this equipment run", component="PRECHECK", equipment=equip_name)
            return False
        
        # Check if coldstart already complete
        coldstart_complete = equip_progress.get('coldstart_complete', False)
        
        if resume and coldstart_complete:
            Console.info(f"{equip_name}: Coldstart already complete, skipping to batch processing", component="COLDSTART", equipment=equip_name)
            coldstart_last_end: Optional[datetime] = None
        else:
            # Phase 1: Coldstart
            cs_ok, coldstart_last_end = self._process_coldstart(equip_name, dry_run=dry_run)
            if not cs_ok:
                Console.error(f"{equip_name}: Coldstart failed", component="COLDSTART", equipment=equip_name)
                return False
            
            # Update progress
            equip_progress['coldstart_complete'] = True
            progress[equip_name] = equip_progress
            if not dry_run:
                self._save_progress(progress)
        
        # Phase 2: Batch processing
        # If we just completed coldstart during this run, start the batch phase
        # immediately after the coldstart window to avoid reprocessing the same window.
        start_from_ts: Optional[datetime] = None
        coldstart_ran_this_session = not (resume and coldstart_complete)
        try:
            # Only honor coldstart_last_end when we executed coldstart above and not in resume-fast path
            if coldstart_ran_this_session and 'coldstart_last_end' in locals() and coldstart_last_end is not None:
                start_from_ts = coldstart_last_end + timedelta(seconds=1)
        except Exception:
            start_from_ts = None

        batches = self._process_batches(equip_name, start_from=start_from_ts, dry_run=dry_run, resume=resume)
        
        elapsed_time = time.time() - start_time
        elapsed_minutes = int(elapsed_time / 60)
        elapsed_seconds = int(elapsed_time % 60)
        
        if batches > 0:
            Console.ok(f"{equip_name}: Completed - {batches} batch(es) processed", component="BATCH", equipment=equip_name, batches=batches)
            Console.info(f"{equip_name}: Total time = {elapsed_minutes}m {elapsed_seconds}s", component="TIMING", equipment=equip_name, minutes=elapsed_minutes, seconds=elapsed_seconds)
            return True
        elif coldstart_ran_this_session:
            # Coldstart consumed all available data - this is OK when using --max-batches 1
            # The processing was successful even though there's nothing left for batch phase
            Console.ok(f"{equip_name}: Completed via coldstart (no additional batches needed)", component="BATCH", equipment=equip_name)
            Console.info(f"{equip_name}: Total time = {elapsed_minutes}m {elapsed_seconds}s", component="TIMING", equipment=equip_name, minutes=elapsed_minutes, seconds=elapsed_seconds)
            return True
        else:
            Console.warn(f"{equip_name}: No batches processed", component="BATCH", equipment=equip_name)
            Console.info(f"{equip_name}: Total time = {elapsed_minutes}m {elapsed_seconds}s", component="TIMING", equipment=equip_name, minutes=elapsed_minutes, seconds=elapsed_seconds)
            return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SQL Batch Runner - Continuous ACM processing from SQL historian",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Processing Flow:
              1. COLDSTART PHASE: Repeatedly calls ACM until coldstart completes
                 - Auto-detects data cadence
                 - Loads from earliest available data
                 - Retries with exponential window expansion
                 - Tracks progress in ACM_ColdstartState table
              
              2. BATCH PHASE: Processes all available data in tick-sized windows
                 - Continues from coldstart end point
                 - Processes batches sequentially
                 - Tracks progress in .sql_batch_progress.json
              
            Notes:
              • Requires SQL mode: runtime.storage_backend='sql' in ACM_Config
              • Progress tracking allows resume after interruption
              • Use --dry-run to preview without execution
              • Use --resume to skip completed batches
        """),
    )
    parser.add_argument("--equip", nargs="+", required=True,
                        help="Equipment codes to process (e.g., FD_FAN GAS_TURBINE)")
    parser.add_argument("--sql-server", default="localhost\\B19CL3PCQLSERVER",
                        help="SQL Server instance (default: localhost\\B19CL3PCQLSERVER)")
    parser.add_argument("--sql-database", default="ACM",
                        help="SQL database name (default: ACM)")
    parser.add_argument("--tick-minutes", type=int, default=30,
                        help="Batch window size in minutes (default: 30)")
    parser.add_argument("--max-coldstart-attempts", type=int, default=10,
                        help="Max coldstart retry attempts (default: 10)")
    parser.add_argument("--max-workers", type=int, default=1,
                        help="Number of equipment to process in parallel (default: 1)")
    parser.add_argument("--max-batches", type=int, default=None,
                        help="For demos: cap number of batches per equipment (default: unlimited)")
    parser.add_argument("--start-from-beginning", action="store_true",
                        help="Development: reset Runs/Coldstart to begin at earliest data timestamp")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last successful batch")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print commands without running")
    args = parser.parse_args()

    # Build SQL connection string (login timeout is controlled via pyodbc.connect timeout)
    sql_conn_string = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={args.sql_server};"
        f"DATABASE={args.sql_database};"
        f"Trusted_Connection=yes;"
    )

    artifact_root = Path("artifacts").resolve()
    
    # Initialize observability for batch runner logging to Loki/Tempo/Prometheus
    # Note: acm_main.py will re-init with per-equipment context, but this enables
    # batch runner Console calls to also go to Loki before ACM invocation
    import os
    loki_url = os.environ.get("LOKI_URL", "http://localhost:3100")
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    
    init_observability(
        service_name="acm-batch-runner",
        equipment="batch_runner",
        equip_id=0,
        run_id="batch-runner-main",
        enable_loki=True,
        enable_tracing=True,
        enable_metrics=True,
        enable_profiling=True,
        loki_endpoint=loki_url,
        otlp_endpoint=otlp_endpoint,
    )
    
    # Start profiling (collect CPU samples for Pyroscope)
    start_profiling()
    
    # Create runner
    runner = SQLBatchRunner(
        sql_conn_string=sql_conn_string,
        artifact_root=artifact_root,
        tick_minutes=args.tick_minutes,
        max_coldstart_attempts=args.max_coldstart_attempts,
        max_batches=args.max_batches,
        start_from_beginning=args.start_from_beginning,
    )

    max_workers = max(1, args.max_workers)
    errors: List[str] = []

    Console.header("SQL BATCH RUNNER - Continuous ACM Processing")
    Console.info(f"Equipment: {', '.join(args.equip)}", component="MAIN", equipment=args.equip)
    Console.info(f"SQL Server: {args.sql_server}/{args.sql_database}", component="MAIN", server=args.sql_server, database=args.sql_database)
    Console.info(f"Tick Window: {args.tick_minutes} minutes", component="MAIN", tick_minutes=args.tick_minutes)
    Console.info(f"Max Workers: {max_workers}", component="MAIN", max_workers=max_workers)
    Console.info(f"Resume: {args.resume}", component="MAIN", resume=args.resume)
    Console.info(f"Dry Run: {args.dry_run}", component="MAIN", dry_run=args.dry_run)
    Console.info(f"Pipeline Mode: adaptive", component="MAIN", mode="adaptive")
    Console.status("="*60)

    import time
    overall_start_time = time.time()

    # Process equipment (sequentially or in parallel)
    if max_workers == 1:
        # Sequential processing
        for equip in args.equip:
            try:
                success = runner.process_equipment(equip, dry_run=args.dry_run, resume=args.resume)
                if not success:
                    errors.append(f"{equip}: Processing incomplete")
            except Exception as exc:
                errors.append(f"{equip}: {exc}")
                Console.error(f"{equip}: {exc}", component="MAIN", equipment=equip, error=str(exc))
    else:
        # Parallel processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(
                    runner.process_equipment,
                    equip,
                    dry_run=args.dry_run,
                    resume=args.resume
                ): equip for equip in args.equip
            }
            for future in as_completed(future_map):
                equip = future_map[future]
                try:
                    success = future.result()
                    if not success:
                        errors.append(f"{equip}: Processing incomplete")
                except Exception as exc:
                    # Sanitize exception text to ASCII to avoid Windows cp1252 encode errors
                    exc_text = str(exc)
                    try:
                        exc_text.encode("cp1252")
                    except Exception:
                        exc_text = exc_text.encode("ascii", "ignore").decode()
                    errors.append(f"{equip}: {exc_text}")
                    Console.error(f"{equip}: {exc_text}", component="MAIN", equipment=equip, error=exc_text)

    overall_elapsed = time.time() - overall_start_time
    overall_minutes = int(overall_elapsed / 60)
    overall_seconds = int(overall_elapsed % 60)

    Console.status("\n" + "="*60)
    Console.info(f"Overall execution time: {overall_minutes}m {overall_seconds}s", component="TIMING", minutes=overall_minutes, seconds=overall_seconds)
    Console.status("="*60)
    
    # Stop profiling and push samples to Pyroscope
    stop_profiling()
    
    # Shutdown observability to flush any pending logs
    shutdown_observability()
    
    if errors:
        Console.error("BATCH RUNNER COMPLETED WITH ERRORS:", component="MAIN")
        for line in errors:
            Console.error(f"  [FAIL] {line}", component="MAIN")
        Console.status("="*60)
        return 1
    else:
        Console.ok("BATCH RUNNER COMPLETED SUCCESSFULLY", component="MAIN")
        Console.status("="*60)
        return 0


if __name__ == "__main__":
    sys.exit(main())

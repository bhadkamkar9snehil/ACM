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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pyodbc

# Ensure project root is on sys.path so `core` imports work when running as a script
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.output_manager import ALLOWED_TABLES


class SQLBatchRunner:
    """Manages continuous batch processing from SQL historian."""
    
    def __init__(self, 
                 sql_conn_string: str,
                 artifact_root: Path,
                 tick_minutes: int = 240,
                 max_coldstart_attempts: int = 10,
                 max_batches: Optional[int] = None,
                 start_from_beginning: bool = False):
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
            print("[SQL] Connection test OK")
            return True
        except Exception as exc:
            print(f"[ERROR] SQL connection test failed: {exc}")
            return False

    # ------------------------
    # SQL helpers (config/progress)
    # ------------------------
    def _get_equip_id(self, equip_name: str) -> Optional[int]:
        try:
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT EquipID FROM dbo.Equipment WHERE EquipCode = ?", (equip_name,))
                row = cur.fetchone()
                return int(row[0]) if row else None
        except Exception as e:
            print(f"[WARN] Could not resolve EquipID for {equip_name}: {e}")
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
            print(f"[WARN] Could not read config {param_path} for EquipID={equip_id}: {e}")
        return default_value

    def _set_tick_minutes(self, equip_id: int, minutes: int) -> None:
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
                print(f"[CFG] Set runtime.tick_minutes={minutes} for EquipID={equip_id}")
        except Exception as e:
            print(f"[WARN] Could not set runtime.tick_minutes for EquipID={equip_id}: {e}")

    def _infer_tick_minutes_from_raw(self, equip_name: str, target_rows_per_batch: int = 5000) -> int:
        """
        Infer a reasonable tick size (minutes) from the raw historian table so
        that each batch processes roughly target_rows_per_batch samples.
        """
        try:
            table_name = f"{equip_name}_Data"
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT MIN(EntryDateTime), MAX(EntryDateTime), COUNT(*) FROM {table_name}")
                row = cur.fetchone()
                cur.close()
            if not row or not row[0] or not row[1] or not row[2]:
                return self.tick_minutes
            min_ts, max_ts, total_rows = row[0], row[1], int(row[2])
            total_minutes = max((max_ts - min_ts).total_seconds() / 60.0, 1.0)
            rows_per_minute = total_rows / total_minutes if total_minutes > 0 else 0.0
            if rows_per_minute <= 0:
                return self.tick_minutes
            inferred = int(max(1, round(target_rows_per_batch / rows_per_minute)))
            inferred = max(5, min(inferred, 240))  # clamp to sane range
            print(
                f"[CONFIG] Inferred tick_minutes={inferred} for {equip_name} "
                f"(rows={total_rows}, minutes={total_minutes:.1f})"
            )
            return inferred
        except Exception as e:
            print(f"[WARN] Could not infer tick_minutes from raw table for {equip_name}: {e}")
            return self.tick_minutes

    def _truncate_outputs_for_equip(self, equip_id: int) -> None:
        """
        Development helper: delete existing outputs for an equipment from ACM
        analytical tables so a dev batch run starts from a clean slate.
        """
        try:
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                for table in sorted(ALLOWED_TABLES):
                    try:
                        cur.execute(
                            f"IF OBJECT_ID('dbo.{table}', 'U') IS NOT NULL "
                            f"AND COL_LENGTH('dbo.{table}', 'EquipID') IS NOT NULL "
                            f"DELETE FROM dbo.{table} WHERE EquipID = ?",
                            (equip_id,),
                        )
                    except Exception as tbl_err:
                        print(f"[WARN] Failed to truncate {table} for EquipID={equip_id}: {tbl_err}")
                conn.commit()
            print(f"[DEV] Truncated SQL outputs for EquipID={equip_id}")
        except Exception as e:
            print(f"[WARN] Failed to truncate outputs for EquipID={equip_id}: {e}")

    def _delete_models_for_equip(self, equip_id: int) -> None:
        """
        Development helper: delete existing models for an equipment from
        ModelRegistry so a coldstart can truly rebuild from scratch.
        """
        try:
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "IF OBJECT_ID('dbo.ModelRegistry', 'U') IS NOT NULL "
                    "DELETE FROM dbo.ModelRegistry WHERE EquipID = ?",
                    (equip_id,),
                )
                conn.commit()
            print(f"[DEV] Deleted existing models from ModelRegistry for EquipID={equip_id}")
        except Exception as e:
            print(f"[WARN] Failed to delete models for EquipID={equip_id}: {e}")

    def _inspect_last_run_outputs(self, equip_name: str) -> None:
        """
        Lightweight QA: after a batch run, report row counts in key tables for
        the last RunID for this equipment so a dev can spot anomalies.
        """
        try:
            equip_id = self._get_equip_id(equip_name)
            if not equip_id:
                print(f"[QA] EquipID not found for {equip_name}, skipping output inspection")
                return
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                # ACM_Runs schema uses StartedAt/CompletedAt, not window columns.
                # For QA we just need the latest RunID for this EquipID.
                cur.execute(
                    "SELECT TOP 1 RunID, StartedAt, CompletedAt "
                    "FROM dbo.ACM_Runs WHERE EquipID = ? ORDER BY StartedAt DESC",
                    (equip_id,),
                )
                row = cur.fetchone()
                if not row:
                    print(f"[QA] No ACM_Runs entry found for EquipID={equip_id}, skipping inspection")
                    return
                run_id, started_at, completed_at = row[0], row[1], row[2]
                print(
                    f"[QA] Inspecting outputs for EquipID={equip_id}, RunID={run_id}, "
                    f"window=[{started_at},{completed_at})"
                )
                tables_to_check: List[Tuple[str, bool]] = [
                    ("ACM_HealthTimeline", True),
                    ("ACM_SensorHotspots", True),
                    ("ACM_DefectTimeline", True),
                    ("ACM_HealthForecast_TS", True),
                    ("ACM_FailureForecast_TS", True),
                    ("ACM_RUL_Summary", True),
                    ("ACM_RUL_Attribution", True),
                    ("ACM_EpisodeMetrics", True),
                ]
                for table_name, has_run in tables_to_check:
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
                        print(
                            f"[QA] {table_name}: {count_val} row(s) for EquipID={equip_id} "
                            f"{'(RunID scoped)' if has_run else ''}"
                        )
                    except Exception as tbl_err:
                        print(f"[QA] Skipped {table_name}: {tbl_err}")
        except Exception as e:
            print(f"[QA] Output inspection failed for {equip_name}: {e}")

    def _reset_progress_to_beginning(self, equip_id: int) -> None:
        """Optional: Clear Runs and Coldstart state to force start from earliest EntryDateTime."""
        try:
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                # Clear coldstart and runs for this equipment
                cur.execute("SET QUOTED_IDENTIFIER ON;")
                cur.execute("DELETE FROM dbo.ACM_ColdstartState WHERE EquipID = ?", (equip_id,))
                cur.execute("DELETE FROM dbo.Runs WHERE EquipID = ?", (equip_id,))
                conn.commit()
                print(f"[RESET] Cleared Runs and Coldstart for EquipID={equip_id}")
        except Exception as e:
            print(f"[WARN] Could not reset progress for EquipID={equip_id}: {e}")
    
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
            print(f"[WARN] Could not load progress file: {exc}")
            return {}
    
    def _save_progress(self, progress: Dict[str, Dict]) -> None:
        """Save progress tracking state."""
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.progress_file, "w") as f:
                json.dump(progress, f, indent=2, default=str)
        except OSError as exc:
            print(f"[WARN] Could not save progress file: {exc}")
    
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
            print(f"[ERROR] Failed to get data range for {equip_name}: {e}")
            return None, None
    
    def _check_coldstart_status(self, equip_name: str) -> tuple[bool, int, int]:
        """Check if coldstart is complete for equipment.
        
        Args:
            equip_name: Equipment name
            
        Returns:
            Tuple of (is_complete, accumulated_rows, required_rows)
        """
        print(f"[COLDSTART] {equip_name}: Checking coldstart status in SQL (ModelRegistry/ACM_ColdstartState)...")
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
                print(f"[COLDSTART] {equip_name}: Equipment not found in Equipment table; using default minimum rows=50")
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
            
            # Coldstart complete if models exist
            if model_count >= 3:
                print(f"[COLDSTART] {equip_name}: Detected existing models in ModelRegistry (count={model_count})")
                return True, 0, 0
            
            # Determine required rows: prefer ColdstartState.RequiredRows, else config runtime.coldstart_min_rows (default 50)
            min_required = self._get_config_int(equip_id, 'runtime.coldstart_min_rows', 50)
            if row:
                status, accum_rows, req_rows = row
                required = req_rows or min_required
                is_complete = status == 'COMPLETE'
                print(
                    f"[COLDSTART] {equip_name}: Status={status}, "
                    f"AccumulatedRows={accum_rows or 0}, RequiredRows={required}"
                )
                return is_complete, accum_rows or 0, required
            print(f"[COLDSTART] {equip_name}: No ACM_ColdstartState row; using default minimum rows={min_required}")
            return False, 0, min_required
            
        except Exception as e:
            print(f"[WARN] Could not check coldstart status: {e}")
            return False, 0, 50
    
    def _run_acm_batch(self, equip_name: str, *, dry_run: bool = False) -> tuple[bool, str]:
        """Run single ACM batch for equipment.
        
        Args:
            equip_name: Equipment name
            dry_run: If True, print command without running
            
        Returns:
            Tuple of (success, outcome) where outcome is 'OK', 'NOOP', or 'FAIL'
        """
        equip_artifact_root = self.artifact_root / equip_name
        cmd = [
            sys.executable, "-m", "core.acm_main",
            "--equip", equip_name,
            "--artifact-root", str(equip_artifact_root)
        ]
        
        printable = " ".join(cmd)
        if dry_run:
            print(f"[DRY] {printable}")
            return True, "OK"
        
        print(f"[RUN] {printable}")
        # Force SQL mode in acm_main so that SQL historian + stored procedures
        # are used instead of legacy CSV/file mode, regardless of older config.
        env = dict(os.environ)
        env["ACM_FORCE_SQL_MODE"] = "1"
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
        
        # Parse outcome from logs
        outcome = "FAIL"
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'outcome=OK' in line:
                    outcome = "OK"
                    break
                elif 'outcome=NOOP' in line:
                    outcome = "NOOP"
                    break
            else:
                outcome = "OK"
        
        success = result.returncode == 0

        # If the batch failed or outcome was not OK/NOOP, surface logs so the
        # caller can see exactly what went wrong inside acm_main.
        if not success or outcome == "FAIL":
            print(f"[RUN-DEBUG] {equip_name}: acm_main exited with code {result.returncode}")
            if result.stdout:
                print(f"[RUN-DEBUG] {equip_name}: --- acm_main stdout ---")
                print(result.stdout)
            if result.stderr:
                print(f"[RUN-DEBUG] {equip_name}: --- acm_main stderr ---", file=sys.stderr)
                print(result.stderr, file=sys.stderr)

        if success and outcome in ("OK", "NOOP"):
            # After a successful batch, inspect SQL outputs for this equipment
            self._inspect_last_run_outputs(equip_name)
        return success, outcome
    
    def _process_coldstart(self, equip_name: str, *, dry_run: bool = False) -> bool:
        """Process coldstart phase for equipment.
        
        Continuously runs ACM until coldstart completes or max attempts reached.
        
        Args:
            equip_name: Equipment name
            dry_run: If True, simulate without running
            
        Returns:
            True if coldstart completed successfully
        """
        print(f"\n{'='*60}")
        print(f"[COLDSTART] Starting coldstart for {equip_name}")
        print(f"{'='*60}")
        
        for attempt in range(1, self.max_coldstart_attempts + 1):
            print(f"\n[COLDSTART] {equip_name}: Attempt {attempt}/{self.max_coldstart_attempts}")
            
            # Check current status
            is_complete, accum_rows, req_rows = self._check_coldstart_status(equip_name)
            if is_complete:
                print(f"[COLDSTART] {equip_name}: Coldstart COMPLETE!")
                return True
            
            print(f"[COLDSTART] {equip_name}: Status - {accum_rows}/{req_rows} rows accumulated")
            
            # Run ACM batch
            success, outcome = self._run_acm_batch(equip_name, dry_run=dry_run)
            
            if not success and outcome == "FAIL":
                print(f"[COLDSTART] {equip_name}: Attempt {attempt} FAILED (error)")
                continue
            
            if outcome == "NOOP":
                print(f"[COLDSTART] {equip_name}: Deferred (insufficient data), will retry...")
                continue
            
            if outcome == "OK":
                # Check if coldstart completed
                is_complete, _, _ = self._check_coldstart_status(equip_name)
                if is_complete:
                    print(f"[COLDSTART] {equip_name}: Coldstart COMPLETE!")
                    return True
                else:
                    print(f"[COLDSTART] {equip_name}: Making progress, continuing...")
        
        print(f"[COLDSTART] {equip_name}: Max attempts ({self.max_coldstart_attempts}) reached without completion")
        return False
    
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
        print(f"\n{'='*60}")
        print(f"[BATCH] Starting batch processing for {equip_name}")
        print(f"{'='*60}")
        
        # Get data range
        min_ts, max_ts = self._get_data_range(equip_name)
        if not min_ts or not max_ts:
            print(f"[BATCH] {equip_name}: No data available in historian")
            return 0
        
        print(f"[BATCH] {equip_name}: Data available from {min_ts} to {max_ts}")
        
        # Load progress
        progress = self._load_progress()
        equip_progress = progress.get(equip_name, {})
        
        # Determine starting point
        if resume and 'last_batch_end' in equip_progress:
            current_ts = datetime.fromisoformat(equip_progress['last_batch_end'])
            batches_completed = equip_progress.get('batches_completed', 0)
            print(f"[BATCH] {equip_name}: Resuming from {current_ts} ({batches_completed} batches already completed)")
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
                print(
                    f"[BATCH] {equip_name}: Adjusting tick_minutes from {self.tick_minutes} "
                    f"to {new_tick} to honor max-batches={self.max_batches}"
                )
                self.tick_minutes = new_tick
                total_batches = int(total_minutes / self.tick_minutes) if self.tick_minutes > 0 else 0
        
        print(f"[BATCH] {equip_name}: Processing {total_batches} batch(es) ({self.tick_minutes}-minute windows)")
        
        # Process batches
        batch_num = 0
        while current_ts < max_ts:
            batch_num += 1
            next_ts = current_ts + timedelta(minutes=self.tick_minutes)
            
            # Don't go beyond available data
            if next_ts > max_ts:
                next_ts = max_ts
            
            print(f"\n[BATCH] {equip_name}: Batch {batch_num}/{total_batches} - [{current_ts} to {next_ts})")
            
            # Run ACM (it will automatically use the current batch window from SQL)
            success, outcome = self._run_acm_batch(equip_name, dry_run=dry_run)
            
            if not success:
                print(f"[BATCH] {equip_name}: Batch {batch_num} FAILED")
                break
            
            batches_completed += 1
            
            # Update progress
            equip_progress['last_batch_end'] = next_ts.isoformat()
            equip_progress['batches_completed'] = batches_completed
            equip_progress['coldstart_complete'] = True
            progress[equip_name] = equip_progress
            
            if not dry_run:
                self._save_progress(progress)
            
            print(f"[BATCH] {equip_name}: Batch {batch_num} completed (outcome={outcome})")
            
            # Respect demo cap if provided
            if self.max_batches is not None and batch_num >= self.max_batches:
                print(f"[BATCH] Reached max-batches cap ({self.max_batches}); stopping early")
                break

            # Move to next window
            current_ts = next_ts
        
        print(f"\n[BATCH] {equip_name}: Processed {batches_completed} batch(es)")
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
        
        print(f"\n{'#'*60}")
        print(f"# Processing Equipment: {equip_name}")
        print(f"{'#'*60}")

        # Fail fast if SQL is unreachable so we do not appear hung
        if not self._test_sql_connection():
            print(f"[ERROR] {equip_name}: Skipping processing due to SQL connection failure")
            return False
        
        # Load progress
        progress = self._load_progress()
        equip_progress = progress.get(equip_name, {})

        # Apply per-run configuration overrides
        equip_id = self._get_equip_id(equip_name)
        if equip_id:
            # In dev mode, optionally infer tick size from raw data
            if self.start_from_beginning and not resume:
                inferred = self._infer_tick_minutes_from_raw(equip_name)
                self.tick_minutes = inferred
                self._set_tick_minutes(equip_id, inferred)
                self._truncate_outputs_for_equip(equip_id)
                # For a true fresh coldstart, also remove existing models
                # so ModelRegistry does not short-circuit coldstart as complete.
                self._delete_models_for_equip(equip_id)
            else:
                self._set_tick_minutes(equip_id, self.tick_minutes)
            if self.start_from_beginning and not resume:
                self._reset_progress_to_beginning(equip_id)
        
        # Check if coldstart already complete
        coldstart_complete = equip_progress.get('coldstart_complete', False)
        
        if resume and coldstart_complete:
            print(f"[INFO] {equip_name}: Coldstart already complete, skipping to batch processing")
        else:
            # Phase 1: Coldstart
            if not self._process_coldstart(equip_name, dry_run=dry_run):
                print(f"[ERROR] {equip_name}: Coldstart failed")
                return False
            
            # Update progress
            equip_progress['coldstart_complete'] = True
            progress[equip_name] = equip_progress
            if not dry_run:
                self._save_progress(progress)
        
        # Phase 2: Batch processing
        batches = self._process_batches(equip_name, dry_run=dry_run, resume=resume)
        
        elapsed_time = time.time() - start_time
        elapsed_minutes = int(elapsed_time / 60)
        elapsed_seconds = int(elapsed_time % 60)
        
        if batches > 0:
            print(f"\n[SUCCESS] {equip_name}: Completed - {batches} batch(es) processed")
            print(f"[TIMING] {equip_name}: Total time = {elapsed_minutes}m {elapsed_seconds}s")
            return True
        else:
            print(f"\n[WARN] {equip_name}: No batches processed")
            print(f"[TIMING] {equip_name}: Total time = {elapsed_minutes}m {elapsed_seconds}s")
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
    parser.add_argument("--artifact-root", default="artifacts",
                        help="ACM artifact root directory (default: artifacts)")
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

    artifact_root = Path(args.artifact_root).resolve()
    
    # Create runner
    runner = SQLBatchRunner(
        sql_conn_string=sql_conn_string,
        artifact_root=artifact_root,
        tick_minutes=args.tick_minutes,
        max_coldstart_attempts=args.max_coldstart_attempts,
        max_batches=args.max_batches,
        start_from_beginning=args.start_from_beginning
    )

    max_workers = max(1, args.max_workers)
    errors: List[str] = []

    print("\n" + "="*60)
    print("SQL BATCH RUNNER - Continuous ACM Processing")
    print("="*60)
    print(f"Equipment: {', '.join(args.equip)}")
    print(f"SQL Server: {args.sql_server}/{args.sql_database}")
    print(f"Tick Window: {args.tick_minutes} minutes")
    print(f"Max Workers: {max_workers}")
    print(f"Resume: {args.resume}")
    print(f"Dry Run: {args.dry_run}")
    print("="*60)

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
                print(f"[ERROR] {equip}: {exc}", file=sys.stderr)
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
                    print(f"[ERROR] {equip}: {exc_text}", file=sys.stderr)

    overall_elapsed = time.time() - overall_start_time
    overall_minutes = int(overall_elapsed / 60)
    overall_seconds = int(overall_elapsed % 60)

    print("\n" + "="*60)
    print(f"[TIMING] Overall execution time: {overall_minutes}m {overall_seconds}s")
    print("="*60)
    if errors:
        print("BATCH RUNNER COMPLETED WITH ERRORS:")
        for line in errors:
            print(f"  [FAIL] {line}")
        print("="*60)
        return 1
    else:
        print("BATCH RUNNER COMPLETED SUCCESSFULLY")
        print("="*60)
        return 0


if __name__ == "__main__":
    sys.exit(main())

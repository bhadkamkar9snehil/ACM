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
import re
import subprocess
import sys
import textwrap
import os
import math
import time
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple
from datetime import datetime, timedelta
try:
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in lean environments
    class _NumpyCompat:
        @staticmethod
        def isclose(a: float, b: float, rtol: float = 1e-05, atol: float = 1e-08) -> bool:
            return abs(float(a) - float(b)) <= (atol + rtol * abs(float(b)))

    np = _NumpyCompat()

try:
    import pyodbc  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in dev/test environments
    pyodbc = None

# Ensure project root is on sys.path so `core` imports work when running as a script
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.output_contracts import ALLOWED_TABLES
from core.baseline_governor import resolve_coldstart_load_decision
try:
    from core.observability import (
        Console,
        init as init_observability,
        shutdown as shutdown_observability,
        resolve_runtime_observability_flags,
        record_run,
        record_error,
        start_profiling,
        stop_profiling,
        get_trace_context,  # For propagating trace context to subprocess
    )
except Exception:  # pragma: no cover - keeps runner usable without optional observability deps
    class _FallbackConsole:
        @staticmethod
        def info(msg: str, **kwargs: Any) -> None:
            _ = kwargs
            print(msg)

        @staticmethod
        def warn(msg: str, **kwargs: Any) -> None:
            _ = kwargs
            print(msg)

        @staticmethod
        def error(msg: str, **kwargs: Any) -> None:
            _ = kwargs
            print(msg)

        @staticmethod
        def ok(msg: str, **kwargs: Any) -> None:
            _ = kwargs
            print(msg)

        @staticmethod
        def header(msg: str, **kwargs: Any) -> None:
            _ = kwargs
            print(msg)

        @staticmethod
        def status(msg: str, **kwargs: Any) -> None:
            _ = kwargs
            print(msg)

        @staticmethod
        def debug(msg: str, **kwargs: Any) -> None:
            _ = kwargs
            print(msg)

    Console = _FallbackConsole()

    def init_observability(*args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)

    def shutdown_observability(*args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)

    def resolve_runtime_observability_flags() -> Dict[str, bool]:
        return {
            "enable_tracing": True,
            "enable_metrics": True,
            "enable_loki": True,
            "enable_profiling": True,
        }

    def record_run(*args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)

    def record_error(*args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)

    def start_profiling(*args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)

    def stop_profiling(*args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)

    def get_trace_context() -> Dict[str, Any]:
        return {}

@dataclass(frozen=True)
class BatchProcessingResult:
    """Summarizes the post-coldstart batch phase for one equipment run."""

    completed: int
    attempted: int
    failed: bool


@dataclass(frozen=True)
class RunInspectionSummary:
    """Structured summary of the latest ACM run for an equipment."""

    run_id: Optional[str]
    run_outcome: Optional[str] = None
    run_source: str = "unknown"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    source_window_start: Optional[datetime] = None
    source_window_end: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    train_row_count: Optional[int] = None
    score_row_count: Optional[int] = None
    episode_count: Optional[int] = None
    health_status: Optional[str] = None
    avg_health_index: Optional[float] = None
    min_health_index: Optional[float] = None
    max_fused_z: Optional[float] = None
    data_quality_score: Optional[float] = None
    refit_requested: Optional[bool] = None
    zero_day_scoring_active: Optional[bool] = None
    zero_day_status: Optional[str] = None
    zero_day_surface_type: Optional[str] = None
    zero_day_channel_count: Optional[int] = None
    representation_authoritative: Optional[bool] = None
    representation_score_allowed: Optional[bool] = None
    representation_learn_allowed: Optional[bool] = None
    representation_context_label: Optional[str] = None
    representation_runtime_mode: Optional[str] = None
    representation_schema_compatibility: Optional[str] = None
    representation_basis_compatibility: Optional[str] = None
    representation_baseline_compatibility: Optional[str] = None
    representation_suppressed_reasons: Optional[str] = None
    representation_degraded_reasons: Optional[str] = None
    forecast_outputs_required: bool = False
    table_counts: Dict[str, int] = field(default_factory=dict)
    run_log_total: Optional[int] = None
    run_log_warn: Optional[int] = None
    run_log_error: Optional[int] = None


_RUN_ID_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"Finalized RunID=([0-9A-Fa-f-]{36})"),
    re.compile(r"RUN START:\s+run_id=([0-9A-Fa-f-]{36})"),
)


def _extract_run_id_from_output(stdout_text: str) -> Optional[str]:
    for pattern in _RUN_ID_PATTERNS:
        match = pattern.search(stdout_text or "")
        if match:
            return str(match.group(1))
    return None


class SQLBatchRunner:
    """Manages continuous batch processing from SQL historian."""

    def __init__(self,
                 sql_conn_string: str,
                 artifact_root: Path,
                 tick_minutes: int = 240,
                 max_coldstart_attempts: int = 10,
                 max_batches: Optional[int] = None,
                 start_from_beginning: bool = False,
                 representation_authority: str = "shadow",
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
        self.progress_file = artifact_root / ".sql_batch_progress.json"
        self.max_batches = max_batches
        self.start_from_beginning = start_from_beginning
        # When a replay budget is provided, the full budget applies to the coldstart
        # progression. A fresh asset reaches ONLINE_SCORING only after model lifecycle
        # promotion (many batches); capping at 10 would abort a valid replay early.
        self.max_coldstart_attempts = max(max_coldstart_attempts, max_batches) if max_batches else max_coldstart_attempts
        self.representation_authority = str(representation_authority or "shadow").strip().lower()
        self._latest_run_inspection: Dict[str, RunInspectionSummary] = {}

    _VALIDATION_REQUIRED_TABLES: Tuple[str, ...] = (
        "ACM_RepresentationStatus",
        "ACM_SignalProfiles",
        "ACM_RepresentationSchemas",
        "ACM_BaselineGovernance",
    )
    _VALIDATION_REQUIRED_RUN_COLUMNS: Tuple[str, ...] = (
        "RepresentationAuthoritative",
        "RepresentationScoreAllowed",
        "RepresentationLearnAllowed",
        "RepresentationContextLabel",
        "RepresentationRuntimeMode",
        "RepresentationSchemaCompatibility",
        "RepresentationBasisCompatibility",
        "RepresentationBaselineCompatibility",
        "RepresentationSuppressedReasons",
        "RepresentationDegradedReasons",
    )

    @staticmethod
    def _expand_coldstart_window_end(
        start_time: datetime,
        end_time: datetime,
        max_time: datetime,
    ) -> datetime:
        """Expand a coldstart window geometrically when a NOOP run lacks enough rows."""
        current_span = (end_time - start_time) + timedelta(seconds=1)
        expanded_span = max(current_span * 2, timedelta(minutes=1))
        expanded_end = start_time + expanded_span - timedelta(seconds=1)
        if expanded_end > max_time:
            expanded_end = max_time
        return expanded_end

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
        if pyodbc is None:
            raise RuntimeError(
                "pyodbc is not installed. Install it to run SQLBatchRunner against SQL Server."
            )
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

    def _validate_representation_sql_contract(self) -> Tuple[bool, List[str]]:
        """Ensure validation-mode replay has the required SQL persistence contract."""
        if self.representation_authority != "validation":
            return True, []

        conn = None
        try:
            conn = self._get_sql_connection()
            cur = conn.cursor()

            table_list = ", ".join(f"'{name}'" for name in self._VALIDATION_REQUIRED_TABLES)
            cur.execute(
                f"SELECT name FROM sys.tables WHERE name IN ({table_list})"
            )
            existing_tables = {str(row[0]) for row in cur.fetchall() if row and row[0]}

            column_list = ", ".join(f"'{name}'" for name in self._VALIDATION_REQUIRED_RUN_COLUMNS)
            cur.execute(
                f"""
                SELECT c.name
                FROM sys.columns c
                JOIN sys.tables t ON c.object_id = t.object_id
                WHERE t.name = 'ACM_Runs'
                  AND c.name IN ({column_list})
                """
            )
            existing_columns = {str(row[0]) for row in cur.fetchall() if row and row[0]}

            missing_tables = [
                name for name in self._VALIDATION_REQUIRED_TABLES if name not in existing_tables
            ]
            missing_columns = [
                name for name in self._VALIDATION_REQUIRED_RUN_COLUMNS if name not in existing_columns
            ]

            issues: List[str] = []
            if missing_tables:
                issues.append(
                    "missing tables: " + ", ".join(missing_tables)
                )
            if missing_columns:
                issues.append(
                    "missing ACM_Runs columns: " + ", ".join(missing_columns)
                )

            if issues:
                return False, issues

            Console.info(
                "Representation SQL contract ready for validation authority",
                component="PRECHECK",
                required_tables=len(self._VALIDATION_REQUIRED_TABLES),
                required_run_columns=len(self._VALIDATION_REQUIRED_RUN_COLUMNS),
            )
            return True, []
        except Exception as exc:
            return False, [f"representation SQL readiness check failed: {exc}"]
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

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

    @staticmethod
    def _parse_bool_value(raw_value: Any) -> Optional[bool]:
        """Parse config values to bool. Returns None if parsing is not possible."""
        if raw_value is None:
            return None
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, (int, float)):
            return bool(raw_value)

        text = str(raw_value).strip().lower()
        if text in ("true", "1", "yes", "y", "on"):
            return True
        if text in ("false", "0", "no", "n", "off"):
            return False
        return None

    def _get_config_bool(self, equip_id: int, param_path: str, default_value: Optional[bool]) -> Optional[bool]:
        """
        Fetch boolean config from ACM_Config with equipment override + global fallback.

        Returns default_value if key is missing or cannot be parsed.
        """
        try:
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT TOP 1 ParamValue
                    FROM dbo.ACM_Config
                    WHERE EquipID IN (0, ?) AND ParamPath = ?
                    ORDER BY CASE WHEN EquipID = ? THEN 0 ELSE 1 END, UpdatedAt DESC
                    """,
                    (equip_id, param_path, equip_id),
                )
                row = cur.fetchone()
                if row:
                    parsed = self._parse_bool_value(row[0])
                    if parsed is not None:
                        return parsed
        except Exception as e:
            Console.warn(
                f"Could not read config {param_path} for EquipID={equip_id}: {e}",
                component="CONFIG",
                equip_id=equip_id,
                param_path=param_path,
                error=str(e),
            )
        return default_value

    def _should_expect_forecast_outputs(self, equip_id: int, run_id: Any) -> bool:
        """
        Determine whether QA should require forecast/RUL output tables.

        Priority:
        1) Explicit config switch to disable forecasting.
        2) Runtime log marker from current run (FORECASTING_DISABLED).
        3) Default to expecting forecast outputs.
        """
        # Explicit config switches (if present).
        disable_switch_paths = (
            "runtime.phases.forecast",
            "runtime.phases.forecasting",
            "runtime.phases.rul",
            "forecasting.enabled",
            "forecasting.enable_continuous",
            "rul.enabled",
        )
        for param_path in disable_switch_paths:
            switch_value = self._get_config_bool(equip_id, param_path, default_value=None)
            if switch_value is False:
                Console.info(
                    f"QA forecast expectation disabled by config: {param_path}=false",
                    component="QA",
                    equip_id=equip_id,
                    param_path=param_path,
                )
                return False

        # Runtime marker from ACM run logs.
        try:
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    IF OBJECT_ID('dbo.ACM_RunLogs','U') IS NOT NULL
                    BEGIN
                        SELECT ISNULL((
                            SELECT TOP 1 1
                            FROM dbo.ACM_RunLogs
                            WHERE EquipID = ? AND RunID = ?
                              AND (Message LIKE ? OR Message LIKE ?)
                            ORDER BY LoggedAt DESC
                        ), 0);
                    END
                    ELSE SELECT 0;
                    """,
                    (equip_id, run_id, "%FORECASTING_DISABLED%", "%Forecasting/RUL is disabled%"),
                )
                row = cur.fetchone()
                if row and int(row[0]) == 1:
                    Console.info(
                        "QA forecast expectation disabled by run marker (FORECASTING_DISABLED)",
                        component="QA",
                        equip_id=equip_id,
                        run_id=str(run_id),
                    )
                    return False
        except Exception as e:
            Console.warn(
                f"Could not determine forecast expectation from ACM_RunLogs: {e}",
                component="QA",
                equip_id=equip_id,
                run_id=str(run_id),
                error=str(e),
            )

        return True

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

    def _inspect_last_run_outputs(
        self,
        equip_name: str,
        *,
        prefer_run_id: Optional[str] = None,
        source_window_start: Optional[datetime] = None,
        source_window_end: Optional[datetime] = None,
        acm_outcome: Optional[str] = None,
    ) -> Optional[RunInspectionSummary]:
        """
        Lightweight QA: after a batch run, report row counts in key tables for
        the last RunID for this equipment so a dev can spot anomalies.
        """
        try:
            equip_id = self._get_equip_id(equip_name)
            if not equip_id:
                Console.warn(f"EquipID not found for {equip_name}, skipping output inspection", component="QA", equipment=equip_name)
                return None
            with self._get_sql_connection() as conn:
                cur = conn.cursor()
                run_id = str(prefer_run_id).strip() if prefer_run_id else None
                run_source = "explicit_run_id" if run_id else None
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
                        return None
                    run_id, started_at, completed_at = row[0], row[1], row[2]
                    run_source = "ACM_Runs"
                else:
                    try:
                        cur.execute(
                            "SELECT TOP 1 StartedAt, CompletedAt FROM dbo.ACM_Runs WHERE RunID = ?",
                            (run_id,),
                        )
                        row = cur.fetchone()
                        if row:
                            started_at, completed_at = row[0], row[1]
                    except Exception:
                        pass

                run_id_str = str(run_id) if run_id is not None else None
                run_outcome = str(acm_outcome).strip().upper() if acm_outcome else None

                Console.info(
                    f"Inspecting outputs for EquipID={equip_id}, RunID={run_id} (from {run_source}), "
                    f"exec_window=[{started_at},{completed_at})"
                    + (
                        f", source_data_window=[{source_window_start},{source_window_end})"
                        if source_window_start is not None or source_window_end is not None
                        else ""
                    ),
                    component="QA", equip_id=equip_id, run_id=run_id_str
                )
                forecast_outputs_required = self._should_expect_forecast_outputs(equip_id, run_id)
                if not forecast_outputs_required:
                    Console.info(
                        "Forecast/RUL outputs are optional for this run; zero-row checks are informational only.",
                        component="QA",
                        equip_id=equip_id,
                        run_id=run_id_str,
                    )
                runs_columns: Dict[str, Any] = {}
                try:
                    cur.execute(
                        """
                        SELECT COLUMN_NAME
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'ACM_Runs'
                        """
                    )
                    available_columns = {str(row[0]) for row in cur.fetchall()}
                    wanted_columns = [
                        "StartedAt",
                        "CompletedAt",
                        "DurationSeconds",
                        "TrainRowCount",
                        "ScoreRowCount",
                        "EpisodeCount",
                        "HealthStatus",
                        "AvgHealthIndex",
                        "MinHealthIndex",
                        "MaxFusedZ",
                        "DataQualityScore",
                        "RefitRequested",
                        "ZeroDayScoringActive",
                        "ZeroDayStatus",
                        "ZeroDaySurfaceType",
                        "ZeroDayChannelCount",
                    ]
                    selected_columns = [col for col in wanted_columns if col in available_columns]
                    if selected_columns:
                        select_sql = (
                            "SELECT TOP 1 "
                            + ", ".join(selected_columns)
                            + " FROM dbo.ACM_Runs WHERE RunID = ?"
                        )
                        cur.execute(select_sql, (run_id,))
                        meta_row = cur.fetchone()
                        if meta_row:
                            runs_columns = {
                                col: meta_row[idx]
                                for idx, col in enumerate(selected_columns)
                            }
                            started_at = runs_columns.get("StartedAt", started_at)
                            completed_at = runs_columns.get("CompletedAt", completed_at)
                except Exception as meta_err:
                    Console.warn(
                        f"Could not load ACM_Runs metadata for summary: {meta_err}",
                        component="QA",
                        equip_id=equip_id,
                        run_id=run_id_str,
                        error_type=type(meta_err).__name__,
                    )

                representation_columns: Dict[str, Any] = {}
                baseline_columns: Dict[str, Any] = {}
                try:
                    cur.execute(
                        """
                        IF OBJECT_ID('dbo.ACM_RepresentationStatus', 'U') IS NOT NULL
                            SELECT TOP 1
                                Authoritative,
                                ScoreAllowed,
                                LearnAllowed,
                                ContextLabel,
                                SchemaCompatibility,
                                BasisCompatibility,
                                BaselineCompatibility,
                                SuppressedReasonsJson,
                                DegradedReasonsJson
                            FROM dbo.ACM_RepresentationStatus
                            WHERE EquipID = ? AND RunID = ?
                            ORDER BY [Timestamp] DESC
                        ELSE
                            SELECT
                                CAST(NULL AS BIT),
                                CAST(NULL AS BIT),
                                CAST(NULL AS BIT),
                                CAST(NULL AS NVARCHAR(128)),
                                CAST(NULL AS NVARCHAR(64)),
                                CAST(NULL AS NVARCHAR(64)),
                                CAST(NULL AS NVARCHAR(64)),
                                CAST(NULL AS NVARCHAR(MAX)),
                                CAST(NULL AS NVARCHAR(MAX))
                        """,
                        (equip_id, run_id),
                    )
                    representation_row = cur.fetchone()
                    if representation_row:
                        representation_columns = {
                            "Authoritative": representation_row[0],
                            "ScoreAllowed": representation_row[1],
                            "LearnAllowed": representation_row[2],
                            "ContextLabel": representation_row[3],
                            "SchemaCompatibility": representation_row[4],
                            "BasisCompatibility": representation_row[5],
                            "BaselineCompatibility": representation_row[6],
                            "SuppressedReasonsJson": representation_row[7],
                            "DegradedReasonsJson": representation_row[8],
                        }
                except Exception as representation_err:
                    Console.warn(
                        f"Could not inspect ACM_RepresentationStatus for summary: {representation_err}",
                        component="QA",
                        equip_id=equip_id,
                        run_id=run_id_str,
                        error_type=type(representation_err).__name__,
                    )

                try:
                    cur.execute(
                        """
                        IF OBJECT_ID('dbo.ACM_BaselineGovernance', 'U') IS NOT NULL
                            SELECT TOP 1 RuntimeMode
                            FROM dbo.ACM_BaselineGovernance
                            WHERE EquipID = ? AND RunID = ?
                            ORDER BY [Timestamp] DESC
                        ELSE
                            SELECT CAST(NULL AS NVARCHAR(64))
                        """,
                        (equip_id, run_id),
                    )
                    baseline_row = cur.fetchone()
                    if baseline_row:
                        baseline_columns = {"RuntimeMode": baseline_row[0]}
                except Exception as baseline_err:
                    Console.warn(
                        f"Could not inspect ACM_BaselineGovernance for summary: {baseline_err}",
                        component="QA",
                        equip_id=equip_id,
                        run_id=run_id_str,
                        error_type=type(baseline_err).__name__,
                    )

                score_outputs_suppressed = (
                    representation_columns.get("Authoritative") is True
                    and representation_columns.get("ScoreAllowed") is False
                )
                noop_valid = run_outcome == "NOOP"
                deep_score_qa_enabled = not (noop_valid or score_outputs_suppressed)
                if noop_valid:
                    Console.info(
                        f"ACM outcome is NOOP for EquipID={equip_id}, RunID={run_id}. "
                        "Running row-count inspection only and skipping deep score QA.",
                        component="QA", equip_id=equip_id, run_id=run_id_str
                    )

                score_derived_tables = {
                    "ACM_Scores_Wide",
                    "ACM_HealthTimeline",
                    "ACM_RegimeTimeline",
                    "ACM_EpisodeDiagnostics",
                    "ACM_Episodes",
                    "ACM_DetectorCorrelation",
                    "ACM_DriftController",
                    "ACM_SensorHotspots",
                    "ACM_SensorDefects",
                }

                table_counts: Dict[str, int] = {}
                tables_to_check: List[Tuple[str, bool, bool]] = [
                    # (table, has_run_id, critical)
                    ("ACM_Scores_Wide", True, True),
                    ("ACM_HealthTimeline", True, True),
                    ("ACM_RegimeTimeline", True, True),
                    ("ACM_EpisodeDiagnostics", True, True),
                    ("ACM_Episodes", True, False),
                    ("ACM_SensorNormalized_TS", True, True),
                    ("ACM_SensorCorrelations", True, False),
                    ("ACM_DetectorCorrelation", True, False),
                    ("ACM_SeasonalPatterns", True, False),
                    ("ACM_HealthForecast", True, forecast_outputs_required),
                    ("ACM_FailureForecast", True, forecast_outputs_required),
                    ("ACM_RUL", True, forecast_outputs_required),
                    ("ACM_DriftController", True, False),
                    ("ACM_RegimeDefinitions", True, False),
                    ("ACM_RegimeOccupancy", True, False),
                    ("ACM_Run_Stats", True, False),
                    ("ACM_PCA_Models", True, False),
                    ("ACM_PCA_Loadings", True, False),
                    ("ACM_PCA_Metrics", True, False),
                    ("ACM_SensorHotspots", True, False),
                    ("ACM_SensorDefects", True, False),
                    ("ACM_RepresentationStatus", True, False),
                    ("ACM_SignalProfiles", True, False),
                    ("ACM_RepresentationSchemas", True, False),
                    ("ACM_BaselineGovernance", True, False),
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
                        table_counts[table_name] = count_val
                        Console.info(
                            f"{table_name}: {count_val} row(s) for EquipID={equip_id} "
                            f"{'(RunID scoped)' if has_run else ''}",
                            component="QA", table=table_name, count=count_val, equip_id=equip_id
                        )
                        if noop_valid:
                            if count_val == 0:
                                Console.info(
                                    f"QA expected: {table_name} has 0 rows because ACM outcome=NOOP produced no persisted batch outputs",
                                    component="QA",
                                    table=table_name,
                                    equip_id=equip_id,
                                    run_id=str(run_id),
                                )
                            elif critical:
                                Console.warn(
                                    f"QA note: {table_name} has {count_val} rows even though ACM outcome=NOOP usually produces no persisted batch outputs",
                                    component="QA",
                                    table=table_name,
                                    equip_id=equip_id,
                                    run_id=str(run_id),
                                )
                        elif score_outputs_suppressed and table_name in score_derived_tables:
                            if count_val == 0:
                                Console.info(
                                    f"QA expected: {table_name} has 0 rows because authoritative representation suppression disabled score-derived persistence",
                                    component="QA",
                                    table=table_name,
                                    equip_id=equip_id,
                                    run_id=str(run_id),
                                )
                            else:
                                Console.warn(
                                    f"QA check failed: {table_name} has {count_val} rows even though authoritative representation suppression should have skipped score-derived persistence",
                                    component="QA",
                                    table=table_name,
                                    equip_id=equip_id,
                                    run_id=str(run_id),
                                )
                        elif critical and count_val == 0:
                            Console.warn(
                                f"QA check failed: {table_name} has 0 rows for EquipID={equip_id} (RunID scoped)",
                                component="QA", table=table_name, equip_id=equip_id, run_id=str(run_id)
                            )
                    except Exception as tbl_err:
                        Console.warn(f"Skipped {table_name}: {tbl_err}", component="QA", table=table_name, error=str(tbl_err), error_type=type(tbl_err).__name__)

                if deep_score_qa_enabled:
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

                                    # Culprits are stored as human-readable labels via format_culprit_label().
                                    # OMR episodes become "Baseline Consistency (OMR)" or
                                    # "Baseline Consistency (OMR) -> <sensor>".
                                    omr_culprit_ok = (
                                        culprits
                                        and (
                                            culprits.startswith('OMR')
                                            or 'Baseline Consistency (OMR)' in culprits
                                        )
                                    )
                                    if primary_detector == 'omr_z' and not omr_culprit_ok:
                                        Console.warn(
                                            f"QA check failed: OMR episode has incorrect culprit. "
                                            f"Expected 'Baseline Consistency (OMR)...', got '{culprits}'",
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
                    except Exception as e:
                        programming_error = getattr(pyodbc, "ProgrammingError", None)
                        if programming_error is not None and isinstance(e, programming_error) and "Invalid column name" in str(e):
                            Console.warn("QA check for Hotspot Ranking skipped: RankingScore/MaxAbsOMR columns not in ACM_SensorHotspots.", component="QA")
                        else:
                            Console.warn(f"QA check for Hotspot Ranking failed: {e}", component="QA")
                else:
                    Console.info(
                        "Skipping deep score QA because row-level score outputs are intentionally absent for this run.",
                        component="QA",
                        equip_id=equip_id,
                        run_id=run_id_str,
                    )

                run_log_total = None
                run_log_warn = None
                run_log_error = None
                try:
                    cur.execute(
                        """
                        IF OBJECT_ID('dbo.ACM_RunLogs', 'U') IS NOT NULL
                            SELECT
                                COUNT(*) AS TotalLogs,
                                SUM(CASE WHEN UPPER(Level) IN ('WARN', 'WARNING') THEN 1 ELSE 0 END) AS WarnLogs,
                                SUM(CASE WHEN UPPER(Level) = 'ERROR' THEN 1 ELSE 0 END) AS ErrorLogs
                            FROM dbo.ACM_RunLogs
                            WHERE RunID = ?
                        ELSE
                            SELECT 0, 0, 0
                        """,
                        (run_id,),
                    )
                    log_row = cur.fetchone()
                    if log_row:
                        run_log_total = int(log_row[0] or 0)
                        run_log_warn = int(log_row[1] or 0)
                        run_log_error = int(log_row[2] or 0)
                except Exception as log_err:
                    Console.warn(
                        f"Could not inspect ACM_RunLogs for summary: {log_err}",
                        component="QA",
                        equip_id=equip_id,
                        run_id=run_id_str,
                        error_type=type(log_err).__name__,
                    )

                summary = RunInspectionSummary(
                    run_id=run_id_str,
                    run_outcome=run_outcome,
                    run_source=str(run_source or "unknown"),
                    started_at=started_at,
                    completed_at=completed_at,
                    source_window_start=source_window_start,
                    source_window_end=source_window_end,
                    duration_seconds=int(runs_columns["DurationSeconds"]) if runs_columns.get("DurationSeconds") is not None else None,
                    train_row_count=int(runs_columns["TrainRowCount"]) if runs_columns.get("TrainRowCount") is not None else None,
                    score_row_count=int(runs_columns["ScoreRowCount"]) if runs_columns.get("ScoreRowCount") is not None else None,
                    episode_count=int(runs_columns["EpisodeCount"]) if runs_columns.get("EpisodeCount") is not None else None,
                    health_status=str(runs_columns["HealthStatus"]) if runs_columns.get("HealthStatus") is not None else None,
                    avg_health_index=float(runs_columns["AvgHealthIndex"]) if runs_columns.get("AvgHealthIndex") is not None else None,
                    min_health_index=float(runs_columns["MinHealthIndex"]) if runs_columns.get("MinHealthIndex") is not None else None,
                    max_fused_z=float(runs_columns["MaxFusedZ"]) if runs_columns.get("MaxFusedZ") is not None else None,
                    data_quality_score=float(runs_columns["DataQualityScore"]) if runs_columns.get("DataQualityScore") is not None else None,
                    refit_requested=bool(runs_columns["RefitRequested"]) if runs_columns.get("RefitRequested") is not None else None,
                    zero_day_scoring_active=bool(runs_columns["ZeroDayScoringActive"]) if runs_columns.get("ZeroDayScoringActive") is not None else None,
                    zero_day_status=str(runs_columns["ZeroDayStatus"]) if runs_columns.get("ZeroDayStatus") is not None else None,
                    zero_day_surface_type=str(runs_columns["ZeroDaySurfaceType"]) if runs_columns.get("ZeroDaySurfaceType") is not None else None,
                    zero_day_channel_count=int(runs_columns["ZeroDayChannelCount"]) if runs_columns.get("ZeroDayChannelCount") is not None else None,
                    representation_authoritative=bool(representation_columns["Authoritative"]) if representation_columns.get("Authoritative") is not None else None,
                    representation_score_allowed=bool(representation_columns["ScoreAllowed"]) if representation_columns.get("ScoreAllowed") is not None else None,
                    representation_learn_allowed=bool(representation_columns["LearnAllowed"]) if representation_columns.get("LearnAllowed") is not None else None,
                    representation_context_label=str(representation_columns["ContextLabel"]) if representation_columns.get("ContextLabel") is not None else None,
                    representation_runtime_mode=str(baseline_columns["RuntimeMode"]) if baseline_columns.get("RuntimeMode") is not None else None,
                    representation_schema_compatibility=str(representation_columns["SchemaCompatibility"]) if representation_columns.get("SchemaCompatibility") is not None else None,
                    representation_basis_compatibility=str(representation_columns["BasisCompatibility"]) if representation_columns.get("BasisCompatibility") is not None else None,
                    representation_baseline_compatibility=str(representation_columns["BaselineCompatibility"]) if representation_columns.get("BaselineCompatibility") is not None else None,
                    representation_suppressed_reasons=str(representation_columns["SuppressedReasonsJson"]) if representation_columns.get("SuppressedReasonsJson") is not None else None,
                    representation_degraded_reasons=str(representation_columns["DegradedReasonsJson"]) if representation_columns.get("DegradedReasonsJson") is not None else None,
                    forecast_outputs_required=forecast_outputs_required,
                    table_counts=table_counts,
                    run_log_total=run_log_total,
                    run_log_warn=run_log_warn,
                    run_log_error=run_log_error,
                )
                self._latest_run_inspection[equip_name] = summary
                return summary
        except Exception as e:
            Console.error(f"Output inspection failed for {equip_name}: {e}", component="QA", equipment=equip_name, error=str(e), error_type=type(e).__name__)
        return None

    def _reset_progress_to_beginning(self, equip_id: int, equip_name: Optional[str] = None) -> None:
        """Clear SQL and local progress state to force restart from earliest EntryDateTime."""
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

        if equip_name:
            try:
                progress = self._load_progress()
                if equip_name in progress:
                    progress.pop(equip_name, None)
                    self._save_progress(progress)
                    Console.info(
                        f"Cleared local batch progress for {equip_name}",
                        component="RESET",
                        equipment=equip_name,
                        equip_id=equip_id,
                    )
            except Exception as e:
                Console.warn(
                    f"Could not clear local progress for {equip_name}: {e}",
                    component="RESET",
                    equipment=equip_name,
                    equip_id=equip_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )

    def _load_progress(self) -> Dict[str, Dict]:
        """Load progress tracking state.

        Returns:
            Dictionary with equipment progress: {
                'FD_FAN': {
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
        Console.info(
            f"{equip_name}: Checking coldstart status in SQL (ACM_BaselineGovernance/ACM_Runs/ACM_ColdstartState)...",
            component="COLDSTART",
            equipment=equip_name,
        )
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

            cur.execute(
                """
                IF OBJECT_ID('dbo.ACM_BaselineGovernance', 'U') IS NOT NULL
                BEGIN
                    SELECT TOP 1 RuntimeMode, BaselineCandidateState, ShadowRefreshState
                    FROM dbo.ACM_BaselineGovernance
                    WHERE EquipID = ?
                    ORDER BY Timestamp DESC, CreatedAt DESC
                END
                """,
                (equip_id,),
            )
            baseline_row = cur.fetchone()

            cur.execute("""
                IF COL_LENGTH('dbo.ACM_Runs', 'RepresentationRuntimeMode') IS NOT NULL
                BEGIN
                    SELECT TOP 1 RepresentationRuntimeMode
                    FROM dbo.ACM_Runs
                    WHERE EquipID = ?
                    ORDER BY CompletedAt DESC, CreatedAt DESC
                END
            """, (equip_id,))
            run_row = cur.fetchone()
            run_runtime_mode = None
            if run_row and run_row[0] is not None:
                run_runtime_mode = str(run_row[0]).strip().upper()

            # Check coldstart state
            cur.execute("""
                SELECT Status, AccumulatedRows, RequiredRows
                FROM ACM_ColdstartState
                WHERE EquipID = ? AND Stage = 'score'
            """, (equip_id,))
            row = cur.fetchone()

            cur.close()
            conn.close()

            # Determine required rows: prefer ColdstartState.RequiredRows, else config data.min_train_samples (default 500)
            min_required = self._get_config_int(equip_id, 'data.min_train_samples', 500)
            status = None
            accum_rows = 0
            required = min_required
            if row:
                status, accum_rows, req_rows = row
                required = req_rows or min_required

            runtime_mode = None
            baseline_candidate_state = None
            shadow_refresh_state = None
            if baseline_row:
                runtime_mode = str(baseline_row[0] or "").strip().upper() or None
                baseline_candidate_state = str(baseline_row[1] or "").strip().upper() or None
                shadow_refresh_state = str(baseline_row[2] or "").strip().upper() or None

            decision = resolve_coldstart_load_decision(
                runtime_mode_hint=runtime_mode,
                run_runtime_mode_hint=run_runtime_mode,
            )

            if decision.use_existing_models:
                Console.info(
                    f"{equip_name}: Coldstart is complete.",
                    component="COLDSTART",
                    equipment=equip_name,
                    runtime_mode=runtime_mode or "UNASSESSED",
                    run_runtime_mode=run_runtime_mode or "UNASSESSED",
                    baseline_candidate_state=baseline_candidate_state,
                    shadow_refresh_state=shadow_refresh_state,
                    status=status or "UNASSESSED",
                    accumulated=accum_rows or 0,
                    required=required,
                    gate_reason=decision.reason_code,
                )
                return True, accum_rows or 0, required

            if row or baseline_row:
                Console.info(
                    f"{equip_name}: Coldstart still forming baseline.",
                    component="COLDSTART",
                    equipment=equip_name,
                    runtime_mode=runtime_mode or "UNASSESSED",
                    run_runtime_mode=run_runtime_mode or "UNASSESSED",
                    baseline_candidate_state=baseline_candidate_state,
                    shadow_refresh_state=shadow_refresh_state,
                    status=status or "UNASSESSED",
                    accumulated=accum_rows or 0,
                    required=required,
                    gate_reason=decision.reason_code,
                )
                return False, accum_rows or 0, required

            Console.info(
                f"{equip_name}: No governed baseline-governance row and no governed ACM_Runs representation mode; "
                f"using default minimum rows={min_required}",
                component="COLDSTART",
                equipment=equip_name,
                runtime_mode=runtime_mode or "UNASSESSED",
                run_runtime_mode=run_runtime_mode or "UNASSESSED",
                min_required=min_required,
                gate_reason=decision.reason_code,
            )
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
            Tuple of (success, outcome) where outcome is 'OK', 'DEGRADED', 'NOOP', or 'FAIL'

        v11.8.0: ADAPTIVE - No mode selection needed
        =============================================
        The pipeline automatically determines behavior based on model state and
        quality metrics. No ONLINE/OFFLINE mode distinction - core.acm decides
        adaptively whether to train or score.
        """
        cmd = [
            sys.executable, "-m", "core.acm",
            "--equip", equip_name,
        ]

        if start_time:
            cmd.extend(["--start-time", start_time.isoformat()])
        if end_time:
            cmd.extend(["--end-time", end_time.isoformat()])
        if self.representation_authority != "shadow":
            cmd.extend(["--representation-authority", self.representation_authority])

        # v11.8.0: No mode argument - core.acm decides adaptively
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
        run_id = _extract_run_id_from_output(stdout_text)
        # Parse outcome from logs
        outcome = "FAIL"
        if process.returncode == 0:
            for line in stdout_text.split('\n'):
                if 'outcome=DEGRADED' in line:
                    outcome = "DEGRADED"
                    break
                if 'outcome=OK' in line:
                    outcome = "OK"
                    break
                if 'outcome=NOOP' in line:
                    outcome = "NOOP"
                    break
            else:
                outcome = "OK"

        success = process.returncode == 0

        # Calculate duration for metrics
        batch_duration = time.time() - batch_start_time if 'batch_start_time' in locals() else 0.0

        # If the batch failed or outcome was not OK/NOOP, surface logs so the
        # caller can see exactly what went wrong inside core.acm.
        if not success or outcome == "FAIL":
            Console.error(f"[RUN-DEBUG] {equip_name}: core.acm exited with code {process.returncode}", component="RUN", equipment=equip_name, return_code=process.returncode)
            if stdout_text:
                # Show only the last 20 lines to avoid duplicating the entire run output
                tail_lines = stdout_text.rstrip().splitlines()[-20:]
                Console.error(
                    f"[RUN-DEBUG] {equip_name}: --- core.acm stdout (last 20 lines) ---\n" + "\n".join(tail_lines),
                    component="RUN", equipment=equip_name,
                )
            # Record FAIL in Prometheus metrics (since core.acm did not complete)
            record_run(equip_name, "FAIL", batch_duration)
            record_error(equip_name, f"Exit code {process.returncode}", "subprocess_failure")

        if success and outcome in ("OK", "DEGRADED", "NOOP"):
            # After a successful batch, inspect SQL outputs for this equipment
            self._inspect_last_run_outputs(
                equip_name,
                prefer_run_id=run_id,
                source_window_start=start_time,
                source_window_end=end_time,
                acm_outcome=outcome,
            )
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
                expanded_end = self._expand_coldstart_window_end(
                    coldstart_start,
                    coldstart_end,
                    max_ts,
                )
                if expanded_end > coldstart_end:
                    Console.warn(
                        f"{equip_name}: Deferred (insufficient data), expanding coldstart window to [{coldstart_start} -> {expanded_end}]",
                        component="COLDSTART",
                        equipment=equip_name,
                        start=coldstart_start,
                        previous_end=coldstart_end,
                        expanded_end=expanded_end,
                    )
                    coldstart_end = expanded_end
                    continue
                Console.warn(
                    f"{equip_name}: Deferred (insufficient data) but full available history is exhausted at {coldstart_end}",
                    component="COLDSTART",
                    equipment=equip_name,
                    start=coldstart_start,
                    end=coldstart_end,
                    max_timestamp=max_ts,
                )
                return False, last_processed_end

            if outcome in ("OK", "DEGRADED"):
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
        # For --start-from-beginning historical replays the model may still be in
        # BASELINE_FORMATION after all coldstart batches -- the lifecycle transition to
        # ONLINE_SCORING requires many more runs than a typical max_batches budget.
        # All individual batches ran OK, so treat this as a successful baseline-building
        # phase and let the batch phase continue from where coldstart left off.
        if self.start_from_beginning and last_processed_end is not None:
            Console.info(
                f"{equip_name}: start-from-beginning replay -- treating max-attempts as baseline built; continuing to batch phase",
                component="COLDSTART",
                equipment=equip_name,
            )
            return True, last_processed_end
        return False, last_processed_end

    def _process_batches(self, equip_name: str, start_from: Optional[datetime] = None,
                        *, dry_run: bool = False, resume: bool = False) -> BatchProcessingResult:
        """Process all available data in batches.

        Args:
            equip_name: Equipment name
            start_from: Starting timestamp (if None, starts from beginning)
            dry_run: If True, simulate without running
            resume: If True, resume from last successful batch

        Returns:
            Summary of the batch phase, including whether any attempted batch failed.
        """
        Console.info(f"\n{'='*60}", component="BATCH")
        Console.info(f"Starting batch processing for {equip_name}", component="BATCH", equipment=equip_name)
        Console.info(f"{'='*60}", component="BATCH")

        # Get data range
        min_ts, max_ts = self._get_data_range(equip_name)
        if not min_ts or not max_ts:
            Console.warn(f"{equip_name}: No data available in historian", component="BATCH", equipment=equip_name)
            return BatchProcessingResult(completed=0, attempted=0, failed=False)

        Console.info(f"{equip_name}: Data available from {min_ts} to {max_ts}", component="BATCH", equipment=equip_name, min_timestamp=min_ts, max_timestamp=max_ts)

        # Load progress
        progress = self._load_progress()
        equip_progress = progress.get(equip_name, {})

        # Determine starting point
        if resume and 'last_batch_end' in equip_progress:
            last_batch_end = datetime.fromisoformat(equip_progress['last_batch_end'])
            current_ts = last_batch_end + timedelta(seconds=1)
            historical_batches_completed = int(equip_progress.get('batches_completed', 0) or 0)
            Console.info(
                f"{equip_name}: Resuming from {current_ts} ({historical_batches_completed} batches already completed)",
                component="BATCH",
                equipment=equip_name,
                resume_from=current_ts,
                previous_batch_end=last_batch_end,
                batches_completed=historical_batches_completed,
            )
        elif start_from:
            current_ts = start_from
            historical_batches_completed = 0
        else:
            current_ts = min_ts
            historical_batches_completed = 0

        batches_completed_total = historical_batches_completed
        batches_completed_session = 0

        # Calculate total batches
        total_minutes = max((max_ts - current_ts).total_seconds() / 60, 0)
        total_batches = int(math.ceil(total_minutes / self.tick_minutes)) if self.tick_minutes > 0 and total_minutes > 0 else 0

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
                total_batches = int(math.ceil(total_minutes / self.tick_minutes)) if self.tick_minutes > 0 and total_minutes > 0 else 0

        Console.info(f"{equip_name}: Processing {total_batches} batch(es) ({self.tick_minutes}-minute windows)", component="BATCH", equipment=equip_name, total_batches=total_batches, tick_minutes=self.tick_minutes)

        # Store total for passing to child processes
        self._current_total_batches = total_batches

        # Process batches
        batch_num = 0
        batch_failed = False
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
            success, outcome = self._run_acm_batch(
                equip_name,
                start_time=current_ts,
                end_time=next_ts,
                dry_run=dry_run,
                batch_num=batches_completed_total,
                is_post_coldstart=True,
            )

            if not success:
                Console.error(f"{equip_name}: Batch {batch_num} FAILED", component="BATCH", equipment=equip_name, batch=batch_num)
                batch_failed = True
                break

            batches_completed_total += 1
            batches_completed_session += 1

            # Update progress
            equip_progress['last_batch_end'] = next_ts.isoformat()
            equip_progress['batches_completed'] = batches_completed_total
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

        Console.info(
            f"\n{equip_name}: Processed {batches_completed_session} batch(es) this run "
            f"({batches_completed_total} total)",
            component="BATCH",
            equipment=equip_name,
            batches_completed=batches_completed_session,
            batches_completed_total=batches_completed_total,
        )
        return BatchProcessingResult(
            completed=batches_completed_session,
            attempted=batch_num,
            failed=batch_failed,
        )

    def _emit_equipment_summary(
        self,
        equip_name: str,
        *,
        success: bool,
        baseline_bootstrap_complete: bool,
        batches_processed: int,
        elapsed_seconds: float,
        note: str,
        inspection: Optional[RunInspectionSummary] = None,
    ) -> None:
        """Emit a single end-of-run summary line for this equipment."""
        elapsed_total = max(int(elapsed_seconds), 0)
        elapsed_minutes = elapsed_total // 60
        elapsed_remainder = elapsed_total % 60
        status = "SUCCESS" if success else "FAIL"
        log_fn = Console.ok if success else Console.error

        def _fmt_dt(value: Optional[datetime]) -> str:
            if value is None:
                return "?"
            try:
                return value.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return str(value)

        def _fmt_float(value: Optional[float], digits: int = 1) -> str:
            if value is None:
                return "?"
            return f"{float(value):.{digits}f}"

        def _fmt_int(value: Optional[int]) -> str:
            if value is None:
                return "?"
            return str(int(value))

        def _fmt_bool(value: Optional[bool]) -> str:
            if value is None:
                return "?"
            return "yes" if bool(value) else "no"

        def _fmt_reason_text(value: Optional[str]) -> str:
            if value in (None, "", "[]"):
                return "[]"
            try:
                parsed = json.loads(str(value))
                if isinstance(parsed, list):
                    cleaned = [str(item) for item in parsed if str(item).strip()]
                    return "[" + ", ".join(cleaned) + "]" if cleaned else "[]"
            except Exception:
                pass
            return str(value)

        Console.status("\n" + "-" * 60)
        log_fn(
            f"{equip_name}: Final summary | status={status} | baseline_bootstrap_complete={baseline_bootstrap_complete} "
            f"| batches_processed={batches_processed} | elapsed={elapsed_minutes}m {elapsed_remainder}s "
            f"| note={note}",
            component="SUMMARY",
            equipment=equip_name,
            status=status,
            baseline_bootstrap_complete=baseline_bootstrap_complete,
            batches_processed=batches_processed,
            elapsed_minutes=elapsed_minutes,
            elapsed_seconds=elapsed_remainder,
            note=note,
        )
        if inspection is not None and inspection.run_id:
            episode_display = inspection.episode_count
            if episode_display is None:
                episode_display = inspection.table_counts.get("ACM_EpisodeDiagnostics")
            Console.info(
                f"{equip_name}: ACM run | run_id={inspection.run_id} | source={inspection.run_source} "
                f"| exec_window=[{_fmt_dt(inspection.started_at)} -> {_fmt_dt(inspection.completed_at)}] "
                f"| source_data_window=[{_fmt_dt(inspection.source_window_start)} -> {_fmt_dt(inspection.source_window_end)}] "
                f"| duration_s={_fmt_int(inspection.duration_seconds)}",
                component="SUMMARY",
                equipment=equip_name,
                run_id=inspection.run_id,
            )
            Console.info(
                f"{equip_name}: ACM metrics | train_rows={_fmt_int(inspection.train_row_count)} "
                f"| score_rows={_fmt_int(inspection.score_row_count)} "
                f"| health_status={inspection.health_status or '?'} "
                f"| avg_health={_fmt_float(inspection.avg_health_index)} "
                f"| min_health={_fmt_float(inspection.min_health_index)} "
                f"| max_fused_z={_fmt_float(inspection.max_fused_z, digits=2)} "
                f"| data_quality={_fmt_float(inspection.data_quality_score)} "
                f"| refit_requested={_fmt_bool(inspection.refit_requested)}",
                component="SUMMARY",
                equipment=equip_name,
                run_id=inspection.run_id,
            )
            Console.info(
                f"{equip_name}: Zero-day | active={_fmt_bool(inspection.zero_day_scoring_active)} "
                f"| status={inspection.zero_day_status or '?'} "
                f"| surface={inspection.zero_day_surface_type or '?'} "
                f"| channels={_fmt_int(inspection.zero_day_channel_count)}",
                component="SUMMARY",
                equipment=equip_name,
                run_id=inspection.run_id,
            )
            Console.info(
                f"{equip_name}: Outputs | scores={inspection.table_counts.get('ACM_Scores_Wide', '?')} "
                f"| health_timeline={inspection.table_counts.get('ACM_HealthTimeline', '?')} "
                f"| regime_timeline={inspection.table_counts.get('ACM_RegimeTimeline', '?')} "
                f"| episodes={_fmt_int(episode_display)} "
                f"| hotspots={inspection.table_counts.get('ACM_SensorHotspots', '?')} "
                f"| forecast_required={'yes' if inspection.forecast_outputs_required else 'no'} "
                f"| health_forecast={inspection.table_counts.get('ACM_HealthForecast', '?')} "
                f"| failure_forecast={inspection.table_counts.get('ACM_FailureForecast', '?')} "
                f"| rul={inspection.table_counts.get('ACM_RUL', '?')}",
                component="SUMMARY",
                equipment=equip_name,
                run_id=inspection.run_id,
            )
            if (
                inspection.representation_runtime_mode is not None
                or inspection.representation_authoritative is not None
                or inspection.table_counts.get("ACM_RepresentationStatus", 0) > 0
            ):
                Console.info(
                    f"{equip_name}: Representation | mode={inspection.representation_runtime_mode or '?'} "
                    f"| authoritative={_fmt_bool(inspection.representation_authoritative)} "
                    f"| score_allowed={_fmt_bool(inspection.representation_score_allowed)} "
                    f"| learn_allowed={_fmt_bool(inspection.representation_learn_allowed)} "
                    f"| context={inspection.representation_context_label or '?'} "
                    f"| schema={inspection.representation_schema_compatibility or '?'} "
                    f"| basis={inspection.representation_basis_compatibility or '?'} "
                    f"| baseline={inspection.representation_baseline_compatibility or '?'} "
                    f"| suppressed={_fmt_reason_text(inspection.representation_suppressed_reasons)} "
                    f"| degraded={_fmt_reason_text(inspection.representation_degraded_reasons)}",
                    component="SUMMARY",
                    equipment=equip_name,
                    run_id=inspection.run_id,
                )
            Console.info(
                f"{equip_name}: Logs | run_logs={_fmt_int(inspection.run_log_total)} "
                f"| warnings={_fmt_int(inspection.run_log_warn)} "
                f"| errors={_fmt_int(inspection.run_log_error)}",
                component="SUMMARY",
                equipment=equip_name,
                run_id=inspection.run_id,
            )
        Console.status("-" * 60)

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
        baseline_bootstrap_completed_for_summary = False
        batches_processed_for_summary = 0
        final_note = "aborted_before_completion"
        result = False

        # Use Console.header for visual separators (console-only, not logged to Loki)
        Console.header(f"Processing Equipment: {equip_name}", char="#")
        try:
            # Fail fast if SQL is unreachable so we do not appear hung
            if not self._test_sql_connection():
                final_note = "sql_connection_failure"
                Console.error(f"{equip_name}: Skipping processing due to SQL connection failure", component="PRECHECK", equipment=equip_name)
                return False

            representation_sql_ok, representation_sql_issues = self._validate_representation_sql_contract()
            if not representation_sql_ok:
                final_note = "representation_sql_contract_missing"
                Console.error(
                    f"{equip_name}: Validation authority requires representation SQL contract from migrations 018-022",
                    component="PRECHECK",
                    equipment=equip_name,
                    representation_authority=self.representation_authority,
                )
                for issue in representation_sql_issues:
                    Console.error(
                        f"{equip_name}: {issue}",
                        component="PRECHECK",
                        equipment=equip_name,
                        representation_authority=self.representation_authority,
                    )
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
                    self._reset_progress_to_beginning(equip_id, equip_name=equip_name)
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
                final_note = "historian_no_data"
                Console.error(f"{equip_name}: Historian has no data — aborting this equipment run", component="PRECHECK", equipment=equip_name)
                return False

            # Check governed baseline-bootstrap status from SQL, not local runner state.
            baseline_bootstrap_complete, _, _ = self._check_coldstart_status(equip_name)

            if resume and baseline_bootstrap_complete:
                baseline_bootstrap_completed_for_summary = True
                final_note = "resume_skipped_coldstart"
                Console.info(
                    f"{equip_name}: Baseline bootstrap already complete, skipping to batch processing",
                    component="COLDSTART",
                    equipment=equip_name,
                )
                coldstart_last_end: Optional[datetime] = None
            else:
                # Phase 1: Coldstart
                cs_ok, coldstart_last_end = self._process_coldstart(equip_name, dry_run=dry_run)
                if not cs_ok:
                    final_note = "coldstart_failed"
                    Console.error(f"{equip_name}: Coldstart failed", component="COLDSTART", equipment=equip_name)
                    return False

                baseline_bootstrap_completed_for_summary = True
                final_note = "baseline_bootstrap_completed"

            # Phase 2: Batch processing
            # If we just completed coldstart during this run, start the batch phase
            # immediately after the coldstart window to avoid reprocessing the same window.
            start_from_ts: Optional[datetime] = None
            coldstart_ran_this_session = not (resume and baseline_bootstrap_complete)
            try:
                # Only honor coldstart_last_end when we executed coldstart above and not in resume-fast path
                if coldstart_ran_this_session and 'coldstart_last_end' in locals() and coldstart_last_end is not None:
                    start_from_ts = coldstart_last_end + timedelta(seconds=1)
            except Exception:
                start_from_ts = None

            batch_result = self._process_batches(equip_name, start_from=start_from_ts, dry_run=dry_run, resume=resume)
            batches_processed_for_summary = batch_result.completed

            elapsed_time = time.time() - start_time
            elapsed_minutes = int(elapsed_time / 60)
            elapsed_seconds = int(elapsed_time % 60)

            if batch_result.failed:
                final_note = "batch_failed"
                result = False
                Console.error(
                    f"{equip_name}: Batch processing failed after {batch_result.completed} successful batch(es)",
                    component="BATCH",
                    equipment=equip_name,
                    batches=batch_result.completed,
                    attempted_batches=batch_result.attempted,
                )
                Console.info(f"{equip_name}: Total time = {elapsed_minutes}m {elapsed_seconds}s", component="TIMING", equipment=equip_name, minutes=elapsed_minutes, seconds=elapsed_seconds)
                return False
            if batch_result.completed > 0:
                result = True
                final_note = "batches_processed"
                Console.ok(f"{equip_name}: Completed - {batch_result.completed} batch(es) processed", component="BATCH", equipment=equip_name, batches=batch_result.completed)
                Console.info(f"{equip_name}: Total time = {elapsed_minutes}m {elapsed_seconds}s", component="TIMING", equipment=equip_name, minutes=elapsed_minutes, seconds=elapsed_seconds)
                return True
            elif coldstart_ran_this_session and batch_result.attempted == 0:
                # Coldstart consumed all available data - this is OK when using --max-batches 1
                # The processing was successful even though there's nothing left for batch phase
                result = True
                final_note = "coldstart_only_no_batches"
                Console.ok(f"{equip_name}: Completed via coldstart (no additional batches needed)", component="BATCH", equipment=equip_name)
                Console.info(f"{equip_name}: Total time = {elapsed_minutes}m {elapsed_seconds}s", component="TIMING", equipment=equip_name, minutes=elapsed_minutes, seconds=elapsed_seconds)
                return True
            else:
                final_note = "no_batches_processed"
                Console.warn(f"{equip_name}: No batches processed", component="BATCH", equipment=equip_name)
                Console.info(f"{equip_name}: Total time = {elapsed_minutes}m {elapsed_seconds}s", component="TIMING", equipment=equip_name, minutes=elapsed_minutes, seconds=elapsed_seconds)
                return False
        except Exception as exc:
            final_note = f"exception:{type(exc).__name__}"
            raise
        finally:
            elapsed_time = time.time() - start_time
            inspection = self._latest_run_inspection.get(equip_name)
            if inspection is None and (baseline_bootstrap_completed_for_summary or batches_processed_for_summary > 0):
                inspection = self._inspect_last_run_outputs(equip_name)
            self._emit_equipment_summary(
                equip_name,
                success=result,
                baseline_bootstrap_complete=baseline_bootstrap_completed_for_summary,
                batches_processed=batches_processed_for_summary,
                elapsed_seconds=elapsed_time,
                note=final_note,
                inspection=inspection,
            )


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
    parser.add_argument(
        "--representation-authority",
        choices=["shadow", "validation"],
        default="shadow",
        help="Representation authority mode to pass to replayed ACM runs (default: shadow, replaces old --shadow flag).",
    )
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
    # Note: core.acm will re-init with per-equipment context, but this enables
    # batch runner Console calls to also go to Loki before ACM invocation
    import os
    loki_url = os.environ.get("LOKI_URL", "http://localhost:3100")
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    obs_flags = resolve_runtime_observability_flags()

    init_observability(
        service_name="acm-batch-runner",
        equipment="batch_runner",
        equip_id=0,
        run_id="batch-runner-main",
        enable_loki=obs_flags["enable_loki"],
        enable_tracing=obs_flags["enable_tracing"],
        enable_metrics=obs_flags["enable_metrics"],
        enable_profiling=obs_flags["enable_profiling"],
        loki_endpoint=loki_url,
        otlp_endpoint=otlp_endpoint,
    )

    # Start profiling (collect CPU samples for Pyroscope)
    if obs_flags["enable_profiling"]:
        start_profiling()

    # Create runner
    runner = SQLBatchRunner(
        sql_conn_string=sql_conn_string,
        artifact_root=artifact_root,
        tick_minutes=args.tick_minutes,
        max_coldstart_attempts=args.max_coldstart_attempts,
        max_batches=args.max_batches,
        start_from_beginning=args.start_from_beginning,
        representation_authority=args.representation_authority,
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
    Console.info(
        f"Representation Authority: {args.representation_authority}",
        component="MAIN",
        representation_authority=args.representation_authority,
    )
    Console.status("="*60)

    import time
    overall_start_time = time.time()

    exit_code = 1
    try:
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

        exit_code = 1 if errors else 0
        return exit_code
    finally:
        overall_elapsed = time.time() - overall_start_time
        overall_minutes = int(overall_elapsed / 60)
        overall_seconds = int(overall_elapsed % 60)
        succeeded = max(len(args.equip) - len(errors), 0)
        failed = len(errors)

        Console.status("\n" + "=" * 60)
        Console.info(
            f"Overall execution time: {overall_minutes}m {overall_seconds}s",
            component="TIMING",
            minutes=overall_minutes,
            seconds=overall_seconds,
        )
        summary_message = (
            f"BATCH RUNNER FINAL SUMMARY | status={'SUCCESS' if exit_code == 0 else 'FAIL'} "
            f"| equipment={len(args.equip)} | succeeded={succeeded} | failed={failed}"
        )
        if exit_code == 0:
            Console.ok(summary_message, component="MAIN", equipment_count=len(args.equip), succeeded=succeeded, failed=failed, status="SUCCESS")
        else:
            Console.error(summary_message, component="MAIN", equipment_count=len(args.equip), succeeded=succeeded, failed=failed, status="FAIL")
            for line in errors:
                Console.error(f"  [FAIL] {line}", component="MAIN")
        Console.status("=" * 60)

        # Stop profiling and push samples to Pyroscope
        stop_profiling()

        # Shutdown observability to flush any pending logs
        shutdown_observability()


if __name__ == "__main__":
    sys.exit(main())

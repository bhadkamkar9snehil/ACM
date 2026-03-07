# core/sql_client.py
# === ACM V5 SQL Edition ===
# File: core/sql_client.py
# Date: 2025-10-22
# Version: SQL-Wire v2 (pyodbc, fast_executemany, simple proc caller)
#
# Purpose:
# - Provide a tiny, reliable wrapper over pyodbc for:
#     * connect(): open a pooled connection to SQL Server
#     * cursor(): get a raw cursor (data_io uses this for executemany)
#     * call_proc(proc_name, params_dict): execute stored procedures with named params
# - No TVPs are required by your current data_io (executemany with regular INSERT).
#
# Config expected under cfg["sql"]:
#   {
#     "server": "YOUR_SQL_HOST\\INSTANCE or tcp:host,1433",
#     "database": "ACM",
#     "user": "sa",
#     "password": "*****",
#     "driver": "ODBC Driver 17 for SQL Server",   # or 18/SQL Server Native Client
#     "timeout": 30,
#     "trust_server_certificate": true,            # optional
#     "mars": false,                               # optional (MultipleActiveResultSets)
#     "autocommit": false                          # optional
#   }
#
from __future__ import annotations

import os
import re
from typing import Any, Callable, Dict, Optional, Tuple
from contextlib import contextmanager
import configparser
from pathlib import Path
from dataclasses import dataclass
try:
    import pandas as pd
except Exception:  # pragma: no cover - optional for SQL-only utility paths
    pd = None  # type: ignore

try:
    import pyodbc
except Exception as e:
    raise SystemExit("pyodbc is required. Install with: pip install pyodbc") from e

# Import tracing support (optional)
try:
    from core.observability import Span
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    Span = None


class SQLClient:
    """
    SQL Server client with support for multiple database connections.
    
    Can connect to one of three databases:
    - 'acm': ACM application database (anomaly results, run logs)
    - 'xstudio_dow': Equipment metadata database
    - 'xstudio_historian': Time-series historian database
    
    Usage:
        # Single database (legacy mode)
        client = SQLClient(cfg).connect()
        
        # Multiple databases
        acm_client = SQLClient.from_ini('acm').connect()
        dow_client = SQLClient.from_ini('xstudio_dow').connect()
        historian_client = SQLClient.from_ini('xstudio_historian').connect()
    """
    
    def __init__(self, cfg: Dict[str, Any], db_section: str = "acm"):
        self.cfg = dict(cfg or {})
        self.db_section = db_section  # Track which DB section this client uses
        self.conn: Optional[pyodbc.Connection] = None
        # Load external INI if present (overrides YAML for credentials/server)
        self._maybe_load_ini()

    @classmethod
    def from_ini(cls, db_section: str = "acm") -> "SQLClient":
        """
        Create SQLClient from INI config file section.
        
        Args:
            db_section: One of 'acm', 'xstudio_dow', 'xstudio_historian'
        
        Returns:
            SQLClient instance configured for the specified database
        """
        ini_path = Path(__file__).resolve().parents[1] / "configs" / "sql_connection.ini"
        if not ini_path.exists():
            raise FileNotFoundError(f"Config file not found: {ini_path}")
        
        parser = configparser.ConfigParser()
        parser.read(ini_path, encoding="utf-8")
        
        if not parser.has_section(db_section):
            raise ValueError(
                f"Section [{db_section}] not found in {ini_path}. "
                f"Available: {list(parser.sections())}"
            )
        
        # Convert INI section to dict
        cfg = dict(parser[db_section])
        return cls(cfg, db_section=db_section)

    def _maybe_load_ini(self) -> None:
        """Load INI config for this db_section (overrides YAML)."""
        try:
            ini_path = Path(__file__).resolve().parents[1] / "configs" / "sql_connection.ini"
            if ini_path.exists():
                parser = configparser.ConfigParser()
                parser.read(ini_path, encoding="utf-8")
                
                # Try to load the specific db_section first, fallback to legacy 'sql' section
                section = self.db_section if parser.has_section(self.db_section) else "sql"
                
                if parser.has_section(section):
                    sec = parser[section]
                    # Only override if present in INI
                    for k_ini, k_cfg in [
                        ("server", "server"),
                        ("database", "database"),
                        ("user", "user"),
                        ("password", "password"),
                        ("driver", "driver"),
                        ("encrypt", "encrypt"),
                        ("trust_server_certificate", "trust_server_certificate"),
                        ("trusted_connection", "trusted_connection"),
                        ("timeout", "timeout"),
                        ("mars", "mars"),
                        ("autocommit", "autocommit"),
                    ]:
                        if k_ini in sec and sec[k_ini] != "":
                            self.cfg[k_cfg] = sec.get(k_ini)
        except Exception:
            # Non-fatal: ignore INI loading issues
            pass

    # ---------- connection ----------
    def _build_conn_str(self, include_database: bool = True) -> str:
        server = self.cfg.get("server") or os.getenv("ACM_SQL_SERVER", "")
        database = self.cfg.get("database") or os.getenv("ACM_SQL_DATABASE", "ACM")
        user = self.cfg.get("user") or os.getenv("ACM_SQL_USER", "")
        password = self.cfg.get("password") or os.getenv("ACM_SQL_PASSWORD", "")
        trusted_conn = str(self.cfg.get("trusted_connection", "no")).strip().lower() in ("1","true","yes","y")
        driver_cfg = self.cfg.get("driver") or os.getenv("ACM_SQL_DRIVER", "ODBC Driver 18 for SQL Server")
        # Choose an installed ODBC driver (fallback gracefully)
        try:
            available = [d.strip().lower() for d in pyodbc.drivers()]
        except Exception:
            available = []
        candidates = [driver_cfg, "ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"]
        driver = None
        for cand in candidates:
            if cand and cand.strip().lower() in available:
                driver = cand
                break
        if not driver:
            # Use requested even if not detected; ODBC may still resolve it, but warn via environment
            driver = driver_cfg
        # normalize booleans and ints
        timeout = int(self.cfg.get("timeout") or self.cfg.get("timeout_seconds") or os.getenv("ACM_SQL_TIMEOUT", 30))
        trust = str(self.cfg.get("trust_server_certificate", "yes")).strip().lower() in ("1","true","yes","y")
        mars = str(self.cfg.get("mars", "no")).strip().lower() in ("1","true","yes","y")

        parts = [
            "DRIVER={%s}" % driver,
            f"SERVER={server}",
        ]
        
        # Windows Authentication vs SQL Server Authentication
        if trusted_conn:
            parts.append("Trusted_Connection=yes")
        else:
            parts.append(f"UID={user}")
            parts.append(f"PWD={password}")
        
        parts.append(f"Connection Timeout={timeout}")
        
        if include_database and database:
            parts.insert(2, f"DATABASE={database}")
        if trust:
            parts.append("TrustServerCertificate=yes")
        if mars:
            parts.append("MARS_Connection=yes")
        # If using Azure SQL or TLS, these flags are ok; leave others default.
        return ";".join(parts)

    def connect(self) -> "SQLClient":
        if self.conn is not None:
            return self
        autocommit = str(self.cfg.get("autocommit", "false")).strip().lower() in ("1","true","yes","y")
        # Try with database first
        try:
            conn_str = self._build_conn_str(include_database=True)
            self.conn = pyodbc.connect(conn_str, autocommit=autocommit)
        except Exception as e:
            s = str(e)
            # Fallback: connect without explicit database (e.g., ACM not created yet)
            if ("4060" in s) or ("Cannot open database" in s):
                conn_str2 = self._build_conn_str(include_database=False)
                self.conn = pyodbc.connect(conn_str2, autocommit=autocommit)
            else:
                raise
        # Conservative defaults; data_io toggles fast_executemany per cursor
        try:
            # lightweight keepalive
            self.conn.timeout = int(self.cfg.get("timeout", 30))
        except Exception:
            pass
        return self

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            finally:
                self.conn = None

    def commit(self) -> None:
        """Commit the current transaction. TASK-5-FIX: Expose commit() method on SQLClient."""
        if self.conn is not None and not self.conn.autocommit:
            self.conn.commit()

    def rollback(self) -> None:
        """Rollback the current transaction. TASK-5-FIX: Expose rollback() method on SQLClient."""
        if self.conn is not None and not self.conn.autocommit:
            self.conn.rollback()

    # ---------- basic primitives ----------
    def cursor(self) -> pyodbc.Cursor:
        if self.conn is None:
            raise RuntimeError("SQLClient.cursor() called before connect().")
        return self.conn.cursor()

    @contextmanager
    def get_cursor(self):
        """
        Context manager for cursor with automatic cleanup.
        
        Usage:
            with sql_client.get_cursor() as cur:
                cur.execute("SELECT ...")
                rows = cur.fetchall()
        """
        if self.conn is None:
            raise RuntimeError("SQLClient.get_cursor() called before connect().")
        cur = self.conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    # Simple proc invoker (without TVPs or OUTPUT capture).
    # Usage: call_proc("dbo.usp_ACM_FinalizeRun", {"RunID": "...", "Outcome": "OK", ...})
    def call_proc(self, proc_name: str, params: Optional[Dict[str, Any]] = None) -> Optional[int]:
        if self.conn is None:
            raise RuntimeError("SQLClient.call_proc() called before connect().")
        params = params or {}
        # Build "EXEC dbo.usp_X @A=?, @B=?, ..." with stable param order.
        names = list(params.keys())
        named = ", ".join([f"@{n} = ?" for n in names])
        tsql = f"EXEC {proc_name} {named}" if named else f"EXEC {proc_name}"
        cur = self.cursor()
        try:
            cur.execute(tsql, tuple(params[n] for n in names))
            # If proc returns a result set (rare here), consume first row count.
            try:
                _ = cur.fetchall()
            except Exception:
                pass
            # Commit for non-autocommit connections.
            if not self.conn.autocommit:
                self.conn.commit()
            # Return rows affected if available; pyodbc rowcount may be -1 depending on driver.
            return cur.rowcount if cur.rowcount is not None else None
        except Exception:
            if not self.conn.autocommit:
                self.conn.rollback()
            raise
        finally:
            cur.close()

    # Optional helpers if you ever need one-off SQL
    def execute(self, tsql: str, *args) -> int:
        """Execute a single T-SQL statement with optional span tracing."""
        # Extract table name and operation type for span attributes
        operation_type = "query"
        table_name = None
        if "INSERT" in tsql.upper():
            operation_type = "insert"
            match = re.search(r'INTO\s+(\w+)', tsql, re.IGNORECASE)
            if match:
                table_name = match.group(1)
        elif "UPDATE" in tsql.upper():
            operation_type = "update"
            match = re.search(r'UPDATE\s+(\w+)', tsql, re.IGNORECASE)
            if match:
                table_name = match.group(1)
        elif "DELETE" in tsql.upper():
            operation_type = "delete"
            match = re.search(r'FROM\s+(\w+)', tsql, re.IGNORECASE)
            if match:
                table_name = match.group(1)
        else:
            operation_type = "select"
            match = re.search(r'FROM\s+(\w+)', tsql, re.IGNORECASE)
            if match:
                table_name = match.group(1)
        
        # Use Span for tracing (optional, graceful fallback if not available)
        span_context = None
        if OTEL_AVAILABLE and Span is not None:
            span_context = Span(
                f"sql.execute",
                operation_type=operation_type,
                table=table_name or "unknown",
            )
            span_context.__enter__()
        
        try:
            cur = self.cursor()
            try:
                cur.execute(tsql, args)
                if not self.conn.autocommit:
                    self.conn.commit()
                rows_affected = cur.rowcount if cur.rowcount is not None else -1
                
                # Set span attributes for result
                if span_context is not None:
                    span_context._span.set_attribute("acm.rows_affected", rows_affected)
                
                return rows_affected
            except Exception:
                if not self.conn.autocommit:
                    self.conn.rollback()
                if span_context is not None:
                    span_context._span.set_attribute("acm.error", True)
                raise
            finally:
                cur.close()
        finally:
            if span_context is not None:
                span_context.__exit__(None, None, None)

    def executemany(self, tsql: str, seq_of_params) -> int:
        """Execute a batch of statements with optional span tracing."""
        # Extract table name for span attributes
        table_name = None
        if "INSERT" in tsql.upper():
            match = re.search(r'INTO\s+(\w+)', tsql, re.IGNORECASE)
            if match:
                table_name = match.group(1)
        
        # Use Span for tracing
        span_context = None
        if OTEL_AVAILABLE and Span is not None:
            span_context = Span(
                f"sql.executemany",
                operation_type="insert_batch",
                table=table_name or "unknown",
                batch_size=len(seq_of_params) if hasattr(seq_of_params, '__len__') else -1,
            )
            span_context.__enter__()
        
        try:
            cur = self.cursor()
            try:
                cur.fast_executemany = True
                cur.executemany(tsql, seq_of_params)
                if not self.conn.autocommit:
                    self.conn.commit()
                # len(seq_of_params) is generally a better inserted count than rowcount with ODBC
                try:
                    rows_affected = len(seq_of_params)
                except Exception:
                    rows_affected = cur.rowcount if cur.rowcount is not None else -1
                
                # Set span attributes for result
                if span_context is not None:
                    span_context._span.set_attribute("acm.rows_affected", rows_affected)
                
                return rows_affected
            except Exception:
                if not self.conn.autocommit:
                    self.conn.rollback()
                if span_context is not None:
                    span_context._span.set_attribute("acm.error", True)
                raise
            finally:
                cur.close()
        finally:
            if span_context is not None:
                span_context.__exit__(None, None, None)

    # ---------- ACM-specific methods ----------
    def get_equipment_id(self, equipment_name: str) -> int:
        """
        Convert equipment name to numeric ID from Equipment table.
        
        Args:
            equipment_name: Equipment code (e.g., 'FD_FAN', 'GAS_TURBINE')
        
        Returns:
            EquipID from Equipment table, or hash-based fallback (1-9999)
        """
        if not equipment_name:
            return 0
        
        # Query Equipment table for actual ID
        if self.conn is not None:
            try:
                with self.get_cursor() as cur:
                    cur.execute("SELECT EquipID FROM Equipment WHERE EquipCode = ?", (equipment_name,))
                    row = cur.fetchone()
                    if row:
                        return int(row[0])
            except Exception:
                pass  # Fall through to hash-based fallback
        
        # Fallback: Generate deterministic ID from equipment name (1-9999 range)
        import hashlib
        hash_val = int(hashlib.md5(equipment_name.encode()).hexdigest(), 16)
        equip_id = (hash_val % 9999) + 1  # Range: 1-9999
        return equip_id

    def start_run(
        self, 
        cfg: Dict[str, Any], 
        equip_code: str,
        deadlock_retry_func: Optional[Callable] = None
    ) -> Tuple[str, Any, Any, int]:
        """
        Start a run by inserting into ACM_Runs table.
        
        Args:
            cfg: Configuration dictionary (for tick_minutes, hash)
            equip_code: Equipment code string
            deadlock_retry_func: Function to execute SQL with deadlock retry
            
        Returns:
            Tuple of (run_id, window_start, window_end, equip_id)
        """
        import uuid
        import pandas as pd
        
        equip_id = self.get_equipment_id(equip_code)
        tick_minutes = cfg.get("runtime", {}).get("tick_minutes", 30)
        config_hash = cfg.get("hash", "")
        
        default_start = pd.Timestamp.utcnow() - pd.Timedelta(minutes=tick_minutes)
        
        # Generate RunID
        run_id = str(uuid.uuid4())
        window_start = default_start
        window_end = default_start + pd.Timedelta(minutes=tick_minutes)
        now = pd.Timestamp.utcnow()

        if self.conn is None:
            raise RuntimeError("SQLClient.start_run() called before connect().")
        
        # Use simple execute if no retry function provided
        if deadlock_retry_func is None:
            def deadlock_retry_func(cur, sql, params):
                cur.execute(sql, params)
            
        cur = self.cursor()
        try:
            # For idempotent re-runs, delete any prior run with same RunID
            deadlock_retry_func(cur, "DELETE FROM dbo.ACM_HealthForecast WHERE RunID = ?", (run_id,))
            deadlock_retry_func(cur, "DELETE FROM dbo.ACM_FailureForecast WHERE RunID = ?", (run_id,))
            deadlock_retry_func(cur, "DELETE FROM dbo.ACM_RUL WHERE RunID = ?", (run_id,))
            deadlock_retry_func(cur, "DELETE FROM dbo.ACM_Runs WHERE RunID = ?", (run_id,))
            
            # Direct INSERT into ACM_Runs
            deadlock_retry_func(
                cur,
                """
                SET QUOTED_IDENTIFIER ON;
                INSERT INTO dbo.ACM_Runs (RunID, EquipID, StartedAt, ConfigSignature)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, equip_id, now, config_hash)
            )
            
            self.conn.commit()
            return run_id, window_start, window_end, equip_id
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            raise
        finally:
            cur.close()

    def finalize_run(
        self,
        run_id: str,
        outcome: str,
        rows_read: int,
        rows_written: int,
        err_json: Optional[str] = None,
    ) -> None:
        """
        Finalize a run by updating ACM_Runs with completion status.
        Uses direct SQL to bypass stored procedure QUOTED_IDENTIFIER issues.
        
        Args:
            run_id: The run UUID
            outcome: Status string (e.g., "SUCCESS", "NOOP", "ERROR")
            rows_read: Count of rows loaded from historian
            rows_written: Count of rows written to output tables
            err_json: Optional error message JSON
        """
        try:
            cur = self.cursor()
            try:
                cur.execute(
                    """
                    SET QUOTED_IDENTIFIER ON;
                    UPDATE dbo.ACM_Runs
                    SET CompletedAt = GETUTCDATE(),
                        TrainRowCount = COALESCE(?, TrainRowCount),
                        ScoreRowCount = COALESCE(?, ScoreRowCount),
                        ErrorMessage = COALESCE(?, ErrorMessage)
                    WHERE RunID = ?
                    """,
                    (rows_read, rows_written, err_json, run_id)
                )
                self.conn.commit()
            finally:
                cur.close()
        except Exception as e:
            # Environments may lack the table/columns; do not fail the pipeline
            pass


def execute_with_deadlock_retry(
    cur: Any,
    sql: str,
    params: tuple = (),
    max_retries: int = 3,
    delay: float = 0.5,
) -> None:
    """
    Execute SQL with automatic retry on deadlock (SQL Server error 1205).
    
    This is a module-level function that can be passed to start_run() or 
    used directly when executing statements that may conflict with other
    concurrent transactions.
    
    Args:
        cur: Database cursor
        sql: SQL statement to execute
        params: Parameters for the SQL statement
        max_retries: Maximum number of retry attempts
        delay: Base delay between retries (exponential backoff applied)
    """
    import time
    for attempt in range(max_retries):
        try:
            cur.execute(sql, params)
            return
        except Exception as e:
            err_str = str(e)
            # SQL Server deadlock error code 1205
            if "1205" in err_str or "deadlock" in err_str.lower():
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))  # Exponential backoff
                    continue
            raise


# ============================================================================
# ACM pipeline helper functions (extracted from core/acm.py)
# ============================================================================

def connect_acm_sql(
    cfg: Dict[str, Any],
    logger: Optional[Any] = None,
) -> Optional[Any]:
    """
    Connect to ACM SQL using INI first, then fallback to cfg["sql"].
    """
    try:
        cli = SQLClient.from_ini("acm")
        cli.connect()
        # Validate the live connection before returning.
        cur = cli.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        return cli
    except Exception as ini_err:
        if logger is not None and hasattr(logger, "warn"):
            logger.warn(
                f"Failed to connect via INI, trying config dict: {ini_err}",
                component="SQL",
                error_type=type(ini_err).__name__,
                error=str(ini_err)[:200],
            )
        sql_cfg = cfg.get("sql", {}) or {}
        cli = SQLClient(sql_cfg)
        cli.connect()
        # Validate the fallback connection as well.
        cur = cli.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        return cli


def connect_acm_sql_failfast(
    cfg: Dict[str, Any],
    logger: Optional[Any] = None,
) -> Any:
    """
    Connect to ACM SQL and exit process on failure.

    This keeps fail-fast semantics centralized for ACM entrypoint startup.
    """
    if logger is not None and hasattr(logger, "info"):
        logger.info("Connecting to SQL Server...", component="SQL")
    try:
        sql_client = connect_acm_sql(cfg=cfg, logger=logger)
        if logger is not None and hasattr(logger, "ok"):
            logger.ok("SQL connection established", component="SQL")
        return sql_client
    except Exception as e:
        if logger is not None and hasattr(logger, "error"):
            logger.error(
                f"SQL connection failed: {e}",
                component="SQL",
                error_type=type(e).__name__,
                error=str(e)[:500],
            )
            logger.error(
                "Check configs/sql_connection.ini and ensure SQL Server is running.",
                component="SQL",
            )
        raise SystemExit(1)


def resolve_equipment_id_required(
    equipment_name: str,
    sql_client: Any,
) -> int:
    """
    Resolve EquipID from SQL. Raises if equipment name/client is missing.
    """
    if not equipment_name:
        raise RuntimeError("Equipment name is required")

    if sql_client is None:
        raise RuntimeError("SQL client is required to look up equipment ID")

    if hasattr(sql_client, "get_equipment_id"):
        equip_id = sql_client.get_equipment_id(equipment_name)
    else:
        cursor = sql_client.cursor()
        cursor.execute("SELECT EquipID FROM Equipment WHERE EquipCode = ?", (equipment_name,))
        row = cursor.fetchone()
        equip_id = row[0] if row else None

    if not equip_id or equip_id == 0:
        raise RuntimeError(
            f"Equipment '{equipment_name}' not found in database.\n"
            f"Add it to the Equipment table first:\n"
            f"  INSERT INTO Equipment (EquipCode, EquipName) VALUES ('{equipment_name}', '{equipment_name}')"
        )

    return int(equip_id)


def load_config_required_from_sql(
    sql_client: Any,
    equipment_name: str,
    logger: Optional[Any] = None,
) -> Any:
    """
    Load config from ACM_Config (global defaults + equipment overrides).
    """
    from utils.config_dict import ConfigDict
    import json

    if not equipment_name:
        raise RuntimeError("Equipment name is required to load config")

    equip_id = resolve_equipment_id_required(equipment_name, sql_client)

    try:
        cursor = sql_client.cursor()
        cursor.execute(
            """
            SELECT ParamPath, ParamValue, ValueType
            FROM ACM_Config
            WHERE EquipID IN (0, ?)
            ORDER BY EquipID ASC, ParamPath ASC
            """,
            (equip_id,),
        )
        rows = cursor.fetchall()
        if not rows:
            raise RuntimeError(
                f"No config found in ACM_Config for equipment '{equipment_name}' (EquipID={equip_id}).\n"
                f"Populate ACM_Config with global (EquipID=0) and/or equipment-specific settings before running ACM."
            )

        cfg_dict: Dict[str, Any] = {}
        for param_path, param_value, value_type in rows:
            if value_type == "int":
                value = int(param_value)
            elif value_type == "float":
                value = float(param_value)
            elif value_type == "bool":
                value = str(param_value).lower() in ("true", "1", "yes")
            elif value_type in ("list", "json"):
                value = json.loads(param_value)
            else:
                value = param_value

            parts = str(param_path).split(".")
            d = cfg_dict
            for part in parts[:-1]:
                if part not in d:
                    d[part] = {}
                d = d[part]
            d[parts[-1]] = value

        if logger is not None and hasattr(logger, "info"):
            logger.info(
                f"Config loaded from SQL for {equipment_name} (EquipID={equip_id}, {len(rows)} params)",
                component="CONFIG",
            )
        return ConfigDict(cfg_dict, mode="sql", equip_id=equip_id)

    except Exception as e:
        if logger is not None and hasattr(logger, "error"):
            logger.error(
                f"Failed to load config from SQL: {e}",
                component="CONFIG",
                equipment=equipment_name,
                equip_id=equip_id,
                error=str(e),
            )
        raise RuntimeError(f"Config loading failed: {e}. Ensure ACM_Config table is populated for EquipID={equip_id}.")


def start_acm_run(
    cli: Any,
    cfg: Dict[str, Any],
    equip_code: str,
    deadlock_retry_func: Optional[Callable] = None,
    logger: Optional[Any] = None,
) -> Tuple[str, Any, Any, int]:
    """
    Start a run in ACM_Runs and return (run_id, window_start, window_end, equip_id).
    """
    tick_minutes = cfg.get("runtime", {}).get("tick_minutes", 30)
    run_id, window_start, window_end, equip_id = cli.start_run(
        cfg=cfg,
        equip_code=equip_code,
        deadlock_retry_func=deadlock_retry_func,
    )
    if logger is not None and hasattr(logger, "info"):
        logger.info(
            f"Run started: {equip_code} (ID={equip_id}) | RunID={run_id[:8]} | window=[{window_start},{window_end}) | tick={tick_minutes}m",
            component="RUN",
        )
    return run_id, window_start, window_end, equip_id


@dataclass
class AcmRunBootstrapState:
    """Typed bootstrap payload for ACM run startup."""
    cfg: Dict[str, Any]
    equip_id: int
    config_signature: str
    run_count: int
    run_id: str
    win_start: Any
    win_end: Any
    cli_overrides: list[str]


@dataclass
class AcmRuntimePolicy:
    """Normalized runtime policy values for one ACM run."""
    force_retraining: bool


def get_acm_run_count(
    sql_client: Any,
    equip_id: int,
) -> int:
    """
    Return run count for an equipment from ACM_Runs.

    Falls back to 0 on query failure to preserve existing runtime behavior.
    """
    try:
        with sql_client.get_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM ACM_Runs WHERE EquipID = ?", (int(equip_id),))
            row = cur.fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0


def apply_cli_window_overrides(
    win_start: Any,
    win_end: Any,
    start_time_arg: Optional[str] = None,
    end_time_arg: Optional[str] = None,
    logger: Optional[Any] = None,
) -> Tuple[Any, Any, list[str]]:
    """
    Apply optional CLI window overrides and return updated bounds plus applied markers.
    """
    overrides: list[str] = []

    if start_time_arg:
        try:
            win_start = pd.Timestamp(start_time_arg)
            overrides.append(f"start={win_start}")
        except Exception as e:
            if logger is not None and hasattr(logger, "warn"):
                logger.warn(f"Failed to parse --start-time: {e}", component="RUN")

    if end_time_arg:
        try:
            win_end = pd.Timestamp(end_time_arg)
            overrides.append(f"end={win_end}")
        except Exception as e:
            if logger is not None and hasattr(logger, "warn"):
                logger.warn(f"Failed to parse --end-time: {e}", component="RUN")

    return win_start, win_end, overrides


def bootstrap_acm_run_state(
    *,
    sql_client: Any,
    equip: str,
    args: Any,
    deadlock_retry_func: Optional[Callable] = None,
    logger: Optional[Any] = None,
) -> AcmRunBootstrapState:
    """
    Build run bootstrap state: config, ids, signature, run window, and CLI overrides.
    """
    import copy
    from utils.config_dict import compute_config_signature

    cfg = load_config_required_from_sql(sql_client, equipment_name=equip, logger=logger)
    cfg = copy.deepcopy(cfg)

    equip_id = resolve_equipment_id_required(equip, sql_client)
    if not hasattr(cfg, "_equip_id") or cfg._equip_id == 0:
        cfg._equip_id = equip_id

    config_signature = compute_config_signature(cfg)
    cfg["_signature"] = config_signature

    run_count = get_acm_run_count(sql_client, equip_id)
    if "runtime" not in cfg:
        cfg["runtime"] = {}
    cfg["runtime"]["run_count"] = run_count

    deadlock_retry = deadlock_retry_func or execute_with_deadlock_retry
    run_id, win_start, win_end, equip_id = start_acm_run(
        cli=sql_client,
        cfg=cfg,
        equip_code=equip,
        deadlock_retry_func=deadlock_retry,
        logger=logger,
    )
    if equip_id <= 0:
        raise RuntimeError(
            f"EquipID is required and must be a positive integer. "
            f"Current value: {equip_id}. Equipment '{equip}' not found in Equipment table."
        )

    win_start, win_end, cli_overrides = apply_cli_window_overrides(
        win_start=win_start,
        win_end=win_end,
        start_time_arg=getattr(args, "start_time", None),
        end_time_arg=getattr(args, "end_time", None),
        logger=logger,
    )

    return AcmRunBootstrapState(
        cfg=cfg,
        equip_id=int(equip_id),
        config_signature=config_signature,
        run_count=int(run_count),
        run_id=str(run_id),
        win_start=win_start,
        win_end=win_end,
        cli_overrides=cli_overrides,
    )


def resolve_runtime_policy(
    args: Any,
) -> AcmRuntimePolicy:
    """
    Normalize runtime policy flags from CLI.
    """
    force_retraining = bool(getattr(args, "force_retrain", False))

    return AcmRuntimePolicy(
        force_retraining=force_retraining,
    )

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
from typing import Any, Dict, Optional
import configparser
from pathlib import Path

try:
    import pyodbc
except Exception as e:
    raise SystemExit("pyodbc is required. Install with: pip install pyodbc") from e


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
            f"UID={user}",
            f"PWD={password}",
            f"Connection Timeout={timeout}",
        ]
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

    # ---------- basic primitives ----------
    def cursor(self) -> pyodbc.Cursor:
        if self.conn is None:
            raise RuntimeError("SQLClient.cursor() called before connect().")
        return self.conn.cursor()

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
        cur = self.cursor()
        try:
            cur.execute(tsql, args)
            if not self.conn.autocommit:
                self.conn.commit()
            return cur.rowcount if cur.rowcount is not None else -1
        except Exception:
            if not self.conn.autocommit:
                self.conn.rollback()
            raise
        finally:
            cur.close()

    def executemany(self, tsql: str, seq_of_params) -> int:
        cur = self.cursor()
        try:
            cur.fast_executemany = True
            cur.executemany(tsql, seq_of_params)
            if not self.conn.autocommit:
                self.conn.commit()
            # len(seq_of_params) is generally a better inserted count than rowcount with ODBC
            try:
                return len(seq_of_params)
            except Exception:
                return cur.rowcount if cur.rowcount is not None else -1
        except Exception:
            if not self.conn.autocommit:
                self.conn.rollback()
            raise
        finally:
            cur.close()

"""
One-shot installer for ACM SQL schema.

Runs the generated SQL scripts in install/sql in order:
  00_create_database.sql
  10_tables.sql
  15_unique_constraints.sql
  20_foreign_keys.sql
  30_indexes.sql
  40_views.sql
  50_procedures.sql

Usage:
    python install/install_acm.py --ini-section acm
    python install/install_acm.py --server localhost\\SQLEXPRESS --database ACM --trusted-connection
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pyodbc

from core.sql_client import SQLClient
from core.observability import Console


SQL_DIR = ROOT / "install" / "sql"
DEFAULT_FILES = [
    "00_create_database.sql",
    "10_tables.sql",
    "15_unique_constraints.sql",
    "20_foreign_keys.sql",
    "30_indexes.sql",
    "40_views.sql",
    "50_procedures.sql",
]


def load_batches(sql_text: str) -> List[str]:
    """Split SQL script by GO batches and trim whitespace."""
    parts = re.split(r"^\s*GO\s*$", sql_text, flags=re.MULTILINE | re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def get_connection(cfg: dict, include_db: bool = True) -> pyodbc.Connection:
    """Build a pyodbc connection mirroring SQLClient config."""
    client = SQLClient(cfg)
    conn_str = client._build_conn_str(include_database=include_db)  # pylint: disable=protected-access
    return pyodbc.connect(conn_str, autocommit=True)


def run_file(path: Path, conn: pyodbc.Connection) -> None:
    sql_text = path.read_text(encoding="utf-8")
    batches = load_batches(sql_text)
    cur = conn.cursor()
    for batch in batches:
        cur.execute(batch)
    cur.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install ACM SQL schema from generated scripts.")
    parser.add_argument("--ini-section", default="acm", help="configs/sql_connection.ini section to use (default: acm)")
    parser.add_argument("--server", help="Override server name")
    parser.add_argument("--database", help="Override database name (default: ACM)")
    parser.add_argument("--user", help="SQL auth user (omit for trusted connection)")
    parser.add_argument("--password", help="SQL auth password")
    parser.add_argument("--trusted-connection", action="store_true", help="Use Windows authentication")
    parser.add_argument("--sql-dir", type=Path, default=SQL_DIR, help="Directory containing ordered SQL scripts")
    parser.add_argument("--files", nargs="+", help="Optional explicit list of SQL files to run (overrides default order)")
    return parser.parse_args()


def build_cfg(args: argparse.Namespace) -> dict:
    """Merge CLI overrides with configs/sql_connection.ini."""
    client = SQLClient.from_ini(args.ini_section)
    cfg = dict(client.cfg)  # type: ignore[attr-defined]
    if args.server:
        cfg["server"] = args.server
    if args.database:
        cfg["database"] = args.database
    if args.user:
        cfg["user"] = args.user
    if args.password:
        cfg["password"] = args.password
    if args.trusted_connection:
        cfg["trusted_connection"] = True
    # Ensure autocommit for DDL
    cfg["autocommit"] = True
    return cfg


def main() -> None:
    args = parse_args()
    cfg = build_cfg(args)

    sql_dir = args.sql_dir
    if not sql_dir.exists():
        raise SystemExit(f"SQL directory not found: {sql_dir}")

    files = args.files or DEFAULT_FILES
    paths = [sql_dir / f for f in files]
    missing = [p for p in paths if not p.exists()]
    if missing:
        missing_list = ", ".join(str(m) for m in missing)
        raise SystemExit(f"Missing SQL files: {missing_list}")

    # Create database first (connect without database to avoid 4060)
    Console.info("Connecting to SQL Server (without database) to ensure ACM exists")
    conn_master = get_connection(cfg, include_db=False)
    Console.info(f"Running {paths[0].name}")
    run_file(paths[0], conn_master)
    conn_master.close()

    # Run remaining scripts against the ACM database
    Console.info("Connecting to ACM database")
    conn_acm = get_connection(cfg, include_db=True)
    for p in paths[1:]:
        Console.info(f"Running {p.name}")
        run_file(p, conn_acm)
    conn_acm.close()
    Console.info("ACM installation completed successfully")


if __name__ == "__main__":
    main()

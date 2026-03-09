#!/usr/bin/env python3
"""
ACM SQL Query MCP Server

Exposes a single read-only tool: query_acm_db

Usage:
    python tools/mcp_sql_server.py

Registered in .claude/mcp.json as a stdio MCP server.
Reads connection config from configs/sql_connection.ini (gitignored).

Safety:
- SELECT only — rejects any statement containing INSERT/UPDATE/DELETE/DROP/EXEC/ALTER/CREATE/TRUNCATE
- Max 500 rows returned
- 30-second query timeout
- Windows Authentication via pyodbc (no credentials in code)
"""

from __future__ import annotations

import configparser
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Any

try:
    import pyodbc
except ImportError:
    print(
        json.dumps({"jsonrpc": "2.0", "error": {"code": -32603, "message": "pyodbc not installed. Run: pip install pyodbc"}}),
        flush=True,
    )
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "sql_connection.ini"
MAX_ROWS = 500
QUERY_TIMEOUT_SECONDS = 30

# Any statement that starts with (or contains as a keyword) these words is rejected.
_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|EXEC|EXECUTE|ALTER|CREATE|TRUNCATE|MERGE|GRANT|REVOKE|DENY)\b",
    re.IGNORECASE,
)


def _load_connection_string() -> str:
    cfg = configparser.ConfigParser()
    cfg.read(str(CONFIG_PATH))
    section = "acm"
    if section not in cfg:
        raise RuntimeError(f"[acm] section not found in {CONFIG_PATH}")
    s = cfg[section]
    server = s.get("server", "localhost")
    database = s.get("database", "ACM")
    driver = s.get("driver", "ODBC Driver 18 for SQL Server")
    trusted = s.get("trusted_connection", "yes").lower() in ("yes", "true", "1")
    trust_cert = s.get("trust_server_certificate", "yes").lower() in ("yes", "true", "1")

    parts = [f"DRIVER={{{driver}}}", f"SERVER={server}", f"DATABASE={database}"]
    if trusted:
        parts.append("Trusted_Connection=yes")
    if trust_cert:
        parts.append("TrustServerCertificate=yes")
    return ";".join(parts)


def _is_safe_query(sql: str) -> tuple[bool, str]:
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT") and not stripped.upper().startswith("WITH"):
        return False, "Only SELECT and WITH (CTE) statements are allowed."
    match = _WRITE_KEYWORDS.search(stripped)
    if match:
        return False, f"Statement contains disallowed keyword: {match.group().upper()}"
    return True, ""


def _execute_query(sql: str) -> dict[str, Any]:
    safe, reason = _is_safe_query(sql)
    if not safe:
        return {"error": reason}

    conn_str = _load_connection_string()
    try:
        conn = pyodbc.connect(conn_str, timeout=QUERY_TIMEOUT_SECONDS)
        conn.timeout = QUERY_TIMEOUT_SECONDS
        cursor = conn.cursor()
        cursor.execute(sql)

        columns = [col[0] for col in cursor.description] if cursor.description else []
        rows = []
        for row in cursor.fetchmany(MAX_ROWS):
            rows.append([str(v) if v is not None else None for v in row])

        total_fetched = len(rows)
        conn.close()

        result: dict[str, Any] = {
            "columns": columns,
            "rows": rows,
            "row_count": total_fetched,
        }
        if total_fetched == MAX_ROWS:
            result["warning"] = f"Result capped at {MAX_ROWS} rows. Add TOP {MAX_ROWS} or a WHERE clause to narrow results."
        return result

    except pyodbc.Error as e:
        return {"error": f"SQL error: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}


# ── MCP stdio protocol ────────────────────────────────────────────────────────

TOOL_SCHEMA = {
    "name": "query_acm_db",
    "description": textwrap.dedent("""\
        Run a read-only T-SQL SELECT query against the ACM SQL Server database.
        Returns columns, rows, and row_count. Capped at 500 rows.
        Use this to inspect ACM_HealthTimeline, ACM_Episodes, ACM_ActiveModels,
        ACM_Config, ACM_Scores_Wide, Equipment, and all other ACM tables.
        ONLY SELECT statements are allowed — no writes.
    """).strip(),
    "inputSchema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "A T-SQL SELECT statement. Must start with SELECT or WITH. No INSERT/UPDATE/DELETE/DROP.",
            },
            "description": {
                "type": "string",
                "description": "Brief description of what this query checks (for logging/context).",
            },
        },
        "required": ["sql"],
    },
}


def _send(obj: dict) -> None:
    line = json.dumps(obj)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _handle_request(req: dict) -> dict | None:
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "acm-sql-server", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": [TOOL_SCHEMA]},
        }

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name != "query_acm_db":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }

        sql = arguments.get("sql", "").strip()
        if not sql:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"error": "sql parameter is required"})}],
                    "isError": True,
                },
            }

        result = _execute_query(sql)
        is_error = "error" in result

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                "isError": is_error,
            },
        }

    if method == "notifications/initialized":
        return None  # notification — no response

    # Unknown method
    if req_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return None


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            _send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue

        response = _handle_request(req)
        if response is not None:
            _send(response)


if __name__ == "__main__":
    main()

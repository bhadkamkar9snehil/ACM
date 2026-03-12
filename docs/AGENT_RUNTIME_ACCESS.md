# Agent Runtime Access

This repo now includes a host-aware runner for agents that need to execute ACM tests,
SQL queries, DB health checks, and batch runs without relying on manual user help.

The entrypoint is:

```bash
python scripts/acm_agent_runtime.py doctor
```

## Why this exists

In this repo, the working ACM SQL toolchain is often Windows-side even when the agent shell
is WSL/Linux:

- `configs/sql_connection.ini` already exists locally and is the source of truth
- `sqlcmd.exe` may be installed on Windows but not on the Linux PATH
- Windows Python may already have the correct ODBC driver integration even when Linux
  `pyodbc` fails because `libodbc.so.2` is missing

The runner closes that gap by choosing the correct host automatically.

## Commands

Validate the environment:

```bash
python scripts/acm_agent_runtime.py doctor
```

Run pytest on the working host:

```bash
python scripts/acm_agent_runtime.py pytest tests/test_sql_batch_runner.py -q
```

Run a DB health check:

```bash
python scripts/acm_agent_runtime.py db-health --equip WFA_TURBINE_10
```

Run the batch runner:

```bash
python scripts/acm_agent_runtime.py batch --equip WFA_TURBINE_10 --dry-run --max-batches 1
```

Run a raw SQL query via `sqlcmd` using `configs/sql_connection.ini`:

```bash
python scripts/acm_agent_runtime.py sql -Q "SELECT TOP 5 RunID, EquipID FROM ACM_Runs ORDER BY StartedAt DESC"
```

## Host selection

Selection is automatic by default:

- on Windows: use the native Python and `sqlcmd`
- on WSL: prefer Windows Python and Windows `sqlcmd`
- on native Linux without Windows access: use the native host, but DB-backed commands
  require working native `pyodbc`

You can override host selection for Python-backed commands:

```bash
python scripts/acm_agent_runtime.py pytest --host native tests/test_sql_batch_runner.py -q
python scripts/acm_agent_runtime.py db-health --host windows --equip WFA_TURBINE_10
```

## Config contract

The runner expects `configs/sql_connection.ini` with section names that match the codebase:

- `[acm]`
- `[xstudio_historian]`
- `[xstudio_dow]`

See `configs/sql_connection.example.ini` for the expected shape.

## Relation to Claude Code

Claude uses `.claude/mcp.json` and `tools/mcp_sql_server.py` for read-only SQL inspection.

This runner is the shell-side equivalent for agents that need to:

- run pytest
- run ACM batch mode
- run `db_health_check.py`
- run `sqlcmd` queries

Both paths use the same `configs/sql_connection.ini`.

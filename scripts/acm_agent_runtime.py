#!/usr/bin/env python3
"""
Agent-facing ACM runtime helper.

Purpose:
- close the loop for agent-driven ACM work from mixed Windows/WSL environments
- pick a working host automatically for pytest, batch runs, DB health checks, and sqlcmd
- reuse configs/sql_connection.ini instead of ad hoc connection strings

Examples:
    python scripts/acm_agent_runtime.py doctor
    python scripts/acm_agent_runtime.py pytest tests/test_sql_batch_runner.py -q
    python scripts/acm_agent_runtime.py db-health --equip WFA_TURBINE_10
    python scripts/acm_agent_runtime.py batch --equip WFA_TURBINE_10 --dry-run --max-batches 1
    python scripts/acm_agent_runtime.py sql -Q "SELECT TOP 5 RunID FROM ACM_Runs ORDER BY StartedAt DESC"
"""

from __future__ import annotations

import argparse
import configparser
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "sql_connection.ini"
WINDOWS_PYTHON_ENV = "ACM_WINDOWS_PYTHON"
WINDOWS_SQLCMD_ENV = "ACM_SQLCMD_EXE"


@dataclass(frozen=True)
class SqlTarget:
    section: str
    server: str
    database: str
    driver: str
    trusted_connection: bool
    trust_server_certificate: bool
    user: str = ""
    password: str = ""


def _is_windows() -> bool:
    return platform.system() == "Windows"


def is_wsl_environment() -> bool:
    if _is_windows():
        return False
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    release = platform.release().lower()
    version = platform.version().lower()
    return "microsoft" in release or "microsoft" in version


def native_pyodbc_available() -> bool:
    if importlib.util.find_spec("pyodbc") is None:
        return False
    try:
        import pyodbc  # type: ignore
    except Exception:
        return False
    return pyodbc is not None


def _bool_from_ini(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def load_sql_target(config_path: Path = CONFIG_PATH, section: str = "acm") -> SqlTarget:
    parser = configparser.ConfigParser()
    if not config_path.exists():
        raise FileNotFoundError(f"SQL connection config not found: {config_path}")
    parser.read(config_path, encoding="utf-8")
    if not parser.has_section(section):
        available = ", ".join(parser.sections()) or "<none>"
        raise ValueError(
            f"Section [{section}] not found in {config_path}. Available sections: {available}"
        )

    data = parser[section]
    server = data.get("server", "").strip()
    database = data.get("database", "").strip()
    if not server or not database:
        raise ValueError(f"[{section}] in {config_path} must define server and database")

    return SqlTarget(
        section=section,
        server=server,
        database=database,
        driver=data.get("driver", "ODBC Driver 18 for SQL Server").strip(),
        trusted_connection=_bool_from_ini(data.get("trusted_connection"), default=False),
        trust_server_certificate=_bool_from_ini(
            data.get("trust_server_certificate"),
            default=True,
        ),
        user=data.get("user", "").strip(),
        password=data.get("password", "").strip(),
    )


def windows_python_available() -> bool:
    if _is_windows():
        return shutil.which(os.environ.get(WINDOWS_PYTHON_ENV, "python")) is not None
    return _windows_command_available(os.environ.get(WINDOWS_PYTHON_ENV, "python"), probe="-V")


def windows_sqlcmd_available() -> bool:
    if _is_windows():
        return shutil.which(os.environ.get(WINDOWS_SQLCMD_ENV, "sqlcmd")) is not None
    return _windows_command_available(os.environ.get(WINDOWS_SQLCMD_ENV, "sqlcmd"), probe="-?")


def _windows_command_available(command: str, probe: str) -> bool:
    cmd_exe = shutil.which("cmd.exe")
    if not cmd_exe:
        return False
    result = subprocess.run(
        [cmd_exe, "/C", command, probe],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def resolve_python_host(
    *,
    preferred: str = "auto",
    is_windows: bool | None = None,
    is_wsl: bool | None = None,
    windows_python_ok: bool | None = None,
    native_pyodbc_ok: bool | None = None,
    require_db: bool = False,
) -> str:
    is_windows = _is_windows() if is_windows is None else is_windows
    is_wsl = is_wsl_environment() if is_wsl is None else is_wsl
    windows_python_ok = windows_python_available() if windows_python_ok is None else windows_python_ok
    native_pyodbc_ok = native_pyodbc_available() if native_pyodbc_ok is None else native_pyodbc_ok

    if preferred not in {"auto", "native", "windows"}:
        raise ValueError(f"Unsupported host selection: {preferred}")

    if preferred == "native":
        if require_db and not (is_windows or native_pyodbc_ok):
            raise RuntimeError("Native host selected, but native pyodbc is not available.")
        return "native"

    if preferred == "windows":
        if not (is_windows or windows_python_ok):
            raise RuntimeError("Windows host selected, but Windows Python is not available.")
        return "windows"

    if is_windows:
        return "native"

    if is_wsl and windows_python_ok:
        return "windows"

    if require_db and not native_pyodbc_ok:
        raise RuntimeError(
            "DB-backed ACM commands require Windows Python in WSL or native pyodbc on this host."
        )

    return "native"


def default_pytest_args(args: Sequence[str]) -> list[str]:
    forwarded = list(args)
    if not any(arg.startswith("--capture") or arg == "-s" for arg in forwarded):
        forwarded.append("--capture=no")
    return forwarded


def build_sqlcmd_args(
    target: SqlTarget,
    *,
    query: str | None = None,
    input_file: str | None = None,
) -> list[str]:
    if not query and not input_file:
        raise ValueError("Either query or input_file must be provided.")
    if query and input_file:
        raise ValueError("query and input_file are mutually exclusive.")

    sqlcmd = os.environ.get(WINDOWS_SQLCMD_ENV, "sqlcmd")
    args = [sqlcmd, "-S", target.server, "-d", target.database]
    if target.trusted_connection:
        args.append("-E")
    else:
        if not target.user or not target.password:
            raise ValueError(
                f"[{target.section}] must define user and password when trusted_connection is disabled."
            )
        args.extend(["-U", target.user, "-P", target.password])
    if target.trust_server_certificate:
        args.append("-C")
    if query:
        args.extend(["-Q", query])
    if input_file:
        args.extend(["-i", input_file])
    return args


def _to_windows_path(path: Path) -> str:
    if _is_windows():
        return str(path)
    if not is_wsl_environment():
        raise RuntimeError(f"Cannot convert path to Windows form outside Windows/WSL: {path}")
    result = subprocess.run(
        ["wslpath", "-w", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _run_host_command(
    argv: Sequence[str],
    *,
    host: str,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    if host == "native":
        return subprocess.run(
            list(argv),
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=capture,
            check=False,
        )

    if host != "windows":
        raise ValueError(f"Unsupported host: {host}")

    if _is_windows():
        return subprocess.run(
            list(argv),
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=capture,
            check=False,
        )

    cmd_exe = shutil.which("cmd.exe")
    if not cmd_exe:
        raise RuntimeError("cmd.exe is not available from this environment.")
    return subprocess.run(
        [cmd_exe, "/C", *list(argv)],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=capture,
        check=False,
    )


def _repo_python_argv(script_relative: str, forwarded_args: Sequence[str], host: str) -> list[str]:
    python_cmd = os.environ.get(WINDOWS_PYTHON_ENV, "python") if host == "windows" else sys.executable
    return [python_cmd, script_relative, *forwarded_args]


def _pytest_argv(forwarded_args: Sequence[str], host: str) -> list[str]:
    python_cmd = os.environ.get(WINDOWS_PYTHON_ENV, "python") if host == "windows" else sys.executable
    return [python_cmd, "-m", "pytest", *default_pytest_args(forwarded_args)]


def _print_doctor_status(label: str, ok: bool, detail: str) -> None:
    marker = "OK" if ok else "FAIL"
    print(f"{label:<24} {marker:<5} {detail}")


def command_doctor(args: argparse.Namespace) -> int:
    print("ACM agent runtime doctor")
    print(f"repo_root               {REPO_ROOT}")
    print(f"config_path             {CONFIG_PATH}")

    config_ok = CONFIG_PATH.exists()
    _print_doctor_status("sql_connection.ini", config_ok, "present" if config_ok else "missing")
    if not config_ok:
        return 2

    parser = configparser.ConfigParser()
    parser.read(CONFIG_PATH, encoding="utf-8")
    sections = ", ".join(parser.sections()) or "<none>"
    print(f"config_sections         {sections}")

    native_pyodbc_ok = native_pyodbc_available()
    _print_doctor_status(
        "native pyodbc",
        native_pyodbc_ok,
        "importable" if native_pyodbc_ok else "missing or unusable",
    )

    win_python_ok = windows_python_available()
    _print_doctor_status(
        "windows python",
        win_python_ok,
        "available via cmd.exe" if win_python_ok else "not reachable",
    )

    win_sqlcmd_ok = windows_sqlcmd_available()
    _print_doctor_status(
        "windows sqlcmd",
        win_sqlcmd_ok,
        "available" if win_sqlcmd_ok else "not reachable",
    )

    try:
        host = resolve_python_host(
            preferred=args.host,
            require_db=False,
            windows_python_ok=win_python_ok,
            native_pyodbc_ok=native_pyodbc_ok,
        )
        print(f"selected_python_host    {host}")
    except Exception as exc:
        _print_doctor_status("host selection", False, str(exc))
        return 2

    if args.skip_db:
        return 0

    try:
        target = load_sql_target(section=args.section)
    except Exception as exc:
        _print_doctor_status("config section", False, str(exc))
        return 2

    if not win_sqlcmd_ok and not (_is_windows() or native_pyodbc_ok):
        _print_doctor_status(
            "db smoke query",
            False,
            "sqlcmd unavailable and native pyodbc unavailable",
        )
        return 2

    smoke_query = "SET NOCOUNT ON; SELECT TOP 1 name FROM sys.tables ORDER BY name;"
    result = _run_sqlcmd(target, query=smoke_query, capture=True)
    ok = result.returncode == 0
    detail = result.stdout.strip().splitlines()[-1] if ok and result.stdout.strip() else (
        result.stderr.strip() or f"exit_code={result.returncode}"
    )
    _print_doctor_status("db smoke query", ok, detail[:180])
    return 0 if ok else result.returncode or 1


def command_pytest(args: argparse.Namespace) -> int:
    host = resolve_python_host(preferred=args.host, require_db=False)
    argv = _pytest_argv(args.forwarded_args, host)
    result = _run_host_command(argv, host=host, capture=False)
    return result.returncode


def command_batch(args: argparse.Namespace) -> int:
    host = resolve_python_host(preferred=args.host, require_db=True)
    argv = _repo_python_argv("scripts/sql_batch_runner.py", args.forwarded_args, host)
    result = _run_host_command(argv, host=host, capture=False)
    return result.returncode


def command_db_health(args: argparse.Namespace) -> int:
    host = resolve_python_host(preferred=args.host, require_db=True)
    argv = _repo_python_argv("scripts/db_health_check.py", args.forwarded_args, host)
    result = _run_host_command(argv, host=host, capture=False)
    return result.returncode


def command_sql(args: argparse.Namespace) -> int:
    target = load_sql_target(section=args.section)
    input_file = args.input_file
    result = _run_sqlcmd(target, query=args.query, input_file=input_file, capture=False)
    return result.returncode


def _run_sqlcmd(
    target: SqlTarget,
    *,
    query: str | None = None,
    input_file: str | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    host = "windows" if not _is_windows() else "native"
    temp_path: Path | None = None
    effective_query = query
    effective_input = input_file

    try:
        if effective_input:
            input_path = Path(effective_input).resolve()
            effective_input = _to_windows_path(input_path) if host == "windows" and not _is_windows() else str(input_path)

        if effective_query and host == "windows" and not _is_windows():
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".sql",
                prefix="acm_agent_runtime_",
                dir=str(REPO_ROOT),
                delete=False,
                encoding="utf-8",
            ) as handle:
                handle.write(effective_query)
                handle.write("\n")
                temp_path = Path(handle.name)
            effective_input = _to_windows_path(temp_path)
            effective_query = None

        argv = build_sqlcmd_args(target, query=effective_query, input_file=effective_input)
        if host == "native":
            argv[0] = shutil.which(argv[0]) or argv[0]
        return _run_host_command(argv, host=host, capture=capture)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Host-aware ACM agent runtime helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Validate ACM agent runtime prerequisites.")
    doctor.add_argument("--section", default="acm", help="sql_connection.ini section to use.")
    doctor.add_argument(
        "--host",
        choices=["auto", "native", "windows"],
        default="auto",
        help="Force python host selection for diagnostic display.",
    )
    doctor.add_argument("--skip-db", action="store_true", help="Skip the DB smoke query.")
    doctor.set_defaults(func=command_doctor)

    pytest_parser = subparsers.add_parser("pytest", help="Run pytest on the working host.")
    pytest_parser.add_argument(
        "--host",
        choices=["auto", "native", "windows"],
        default="auto",
        help="Force python host selection.",
    )
    pytest_parser.set_defaults(func=command_pytest)

    batch = subparsers.add_parser("batch", help="Run scripts/sql_batch_runner.py on the DB-capable host.")
    batch.add_argument(
        "--host",
        choices=["auto", "native", "windows"],
        default="auto",
        help="Force python host selection.",
    )
    batch.set_defaults(func=command_batch)

    db_health = subparsers.add_parser("db-health", help="Run scripts/db_health_check.py on the DB-capable host.")
    db_health.add_argument(
        "--host",
        choices=["auto", "native", "windows"],
        default="auto",
        help="Force python host selection.",
    )
    db_health.set_defaults(func=command_db_health)

    sql = subparsers.add_parser("sql", help="Run a sqlcmd query using configs/sql_connection.ini.")
    sql.add_argument("--section", default="acm", help="sql_connection.ini section to use.")
    sql_group = sql.add_mutually_exclusive_group(required=True)
    sql_group.add_argument("-Q", "--query", help="T-SQL query to run.")
    sql_group.add_argument("-i", "--input-file", help="Path to a .sql file to run.")
    sql.set_defaults(func=command_sql)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args, extras = parser.parse_known_args(argv)
    if args.command in {"pytest", "batch", "db-health"}:
        setattr(args, "forwarded_args", list(extras))
    elif extras:
        parser.error(f"unrecognized arguments: {' '.join(extras)}")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

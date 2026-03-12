from pathlib import Path

from scripts import acm_agent_runtime as runtime


def test_load_sql_target_reads_trusted_connection(tmp_path: Path) -> None:
    config_path = tmp_path / "sql_connection.ini"
    config_path.write_text(
        "[acm]\n"
        "server=localhost\\SQLEXPRESS\n"
        "database=ACM\n"
        "trusted_connection=yes\n"
        "driver=ODBC Driver 18 for SQL Server\n"
        "trust_server_certificate=yes\n",
        encoding="utf-8",
    )

    target = runtime.load_sql_target(config_path=config_path, section="acm")

    assert target.section == "acm"
    assert target.server == "localhost\\SQLEXPRESS"
    assert target.database == "ACM"
    assert target.trusted_connection is True
    assert target.trust_server_certificate is True


def test_build_sqlcmd_args_for_trusted_connection() -> None:
    target = runtime.SqlTarget(
        section="acm",
        server="localhost\\SQLEXPRESS",
        database="ACM",
        driver="ODBC Driver 18 for SQL Server",
        trusted_connection=True,
        trust_server_certificate=True,
    )

    args = runtime.build_sqlcmd_args(target, query="SELECT TOP 1 1", input_file=None)

    assert args[:5] == ["sqlcmd", "-S", "localhost\\SQLEXPRESS", "-d", "ACM"]
    assert "-E" in args
    assert "-C" in args
    assert args[-2:] == ["-Q", "SELECT TOP 1 1"]


def test_build_sqlcmd_args_for_sql_auth() -> None:
    target = runtime.SqlTarget(
        section="acm",
        server="localhost,1433",
        database="ACM",
        driver="ODBC Driver 18 for SQL Server",
        trusted_connection=False,
        trust_server_certificate=False,
        user="sa",
        password="secret",
    )

    args = runtime.build_sqlcmd_args(target, query="SELECT TOP 1 1", input_file=None)

    assert "-E" not in args
    assert "-U" in args
    assert "-P" in args
    assert "sa" in args
    assert "secret" in args


def test_resolve_python_host_prefers_windows_for_wsl() -> None:
    host = runtime.resolve_python_host(
        preferred="auto",
        is_windows=False,
        is_wsl=True,
        windows_python_ok=True,
        native_pyodbc_ok=False,
        require_db=True,
    )

    assert host == "windows"


def test_default_pytest_args_adds_capture_no() -> None:
    forwarded = runtime.default_pytest_args(["tests/test_sql_batch_runner.py", "-q"])

    assert forwarded == ["tests/test_sql_batch_runner.py", "-q", "--capture=no"]


def test_default_pytest_args_keeps_explicit_capture() -> None:
    forwarded = runtime.default_pytest_args(["-q", "--capture=tee-sys"])

    assert forwarded == ["-q", "--capture=tee-sys"]


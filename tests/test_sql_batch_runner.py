from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

import scripts.sql_batch_runner as sql_batch_runner_module
from scripts.sql_batch_runner import BatchProcessingResult, SQLBatchRunner


class _DummyCursor:
    def __init__(self) -> None:
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((str(query), tuple(params) if params else ()))
        return self


class _DummyConn:
    def __init__(self) -> None:
        self.cursor_obj = _DummyCursor()
        self.committed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _SequenceCursor:
    def __init__(self, rows) -> None:
        self._rows = list(rows)
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((str(query), tuple(params) if params else ()))
        return self

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows.pop(0)

    def close(self):
        return None


class _SequenceConn:
    def __init__(self, rows) -> None:
        self.cursor_obj = _SequenceCursor(rows)

    def cursor(self):
        return self.cursor_obj

    def close(self):
        return None


def _make_runner(tmp_path: Path) -> SQLBatchRunner:
    return SQLBatchRunner(
        sql_conn_string="DRIVER={ODBC Driver 17 for SQL Server};SERVER=.;DATABASE=ACM;Trusted_Connection=yes;",
        artifact_root=tmp_path,
        tick_minutes=10,
        max_coldstart_attempts=2,
    )


def test_reset_progress_to_beginning_clears_local_progress_entry(tmp_path):
    runner = _make_runner(tmp_path)
    progress = {
        "FD_FAN": {"coldstart_complete": True, "last_batch_end": "2024-01-01T00:09:59", "batches_completed": 1},
        "GT_01": {"coldstart_complete": False, "batches_completed": 0},
    }
    runner.progress_file.write_text(json.dumps(progress), encoding="utf-8")

    dummy_conn = _DummyConn()
    runner._get_sql_connection = lambda: dummy_conn  # type: ignore[method-assign]

    runner._reset_progress_to_beginning(101, equip_name="FD_FAN")

    updated = json.loads(runner.progress_file.read_text(encoding="utf-8"))
    assert "FD_FAN" not in updated
    assert "GT_01" in updated
    assert dummy_conn.committed is True
    assert any("DELETE FROM dbo.ACM_ColdstartState" in q for q, _ in dummy_conn.cursor_obj.queries)
    assert any("DELETE FROM dbo.ACM_Runs" in q for q, _ in dummy_conn.cursor_obj.queries)


def test_process_batches_resume_starts_after_last_batch_end(tmp_path):
    runner = _make_runner(tmp_path)
    runner._get_data_range = lambda equip: (datetime(2024, 1, 1, 0, 0, 0), datetime(2024, 1, 1, 0, 19, 59))  # type: ignore[method-assign]
    runner._load_progress = lambda: {  # type: ignore[method-assign]
        "FD_FAN": {"last_batch_end": "2024-01-01T00:09:59", "batches_completed": 1}
    }
    runner._save_progress = lambda p: None  # type: ignore[method-assign]

    starts = []

    def _run_batch(equip_name, start_time=None, end_time=None, dry_run=False, batch_num=0, is_post_coldstart=False):
        starts.append(start_time)
        return True, "OK"

    runner._run_acm_batch = _run_batch  # type: ignore[method-assign]

    result = runner._process_batches("FD_FAN", resume=True)

    assert result.completed == 1
    assert result.attempted == 1
    assert result.failed is False
    assert starts
    assert starts[0] == datetime(2024, 1, 1, 0, 10, 0)


def test_check_coldstart_status_uses_active_model_maturity_state(tmp_path):
    runner = _make_runner(tmp_path)
    runner._get_config_int = lambda equip_id, path, default=500: 500  # type: ignore[method-assign]
    runner._get_sql_connection = lambda: _SequenceConn([  # type: ignore[method-assign]
        (101,),
        ("LEARNING",),
        ("PENDING", 120, 500),
    ])

    is_complete, accumulated, required = runner._check_coldstart_status("FD_FAN")

    assert is_complete is True
    assert accumulated == 120
    assert required == 500


def test_check_coldstart_status_does_not_trust_complete_without_maturity(tmp_path):
    runner = _make_runner(tmp_path)
    runner._get_config_int = lambda equip_id, path, default=500: 500  # type: ignore[method-assign]
    runner._get_sql_connection = lambda: _SequenceConn([  # type: ignore[method-assign]
        (101,),
        ("INITIALIZING",),
        ("COMPLETE", 500, 500),
    ])

    is_complete, accumulated, required = runner._check_coldstart_status("FD_FAN")

    assert is_complete is False
    assert accumulated == 500
    assert required == 500


def test_process_equipment_emits_final_summary_on_precheck_failure(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path)
    messages = []

    class _ConsoleCapture:
        @staticmethod
        def header(msg, **kwargs):
            messages.append(("header", msg))

        @staticmethod
        def info(msg, **kwargs):
            messages.append(("info", msg))

        @staticmethod
        def ok(msg, **kwargs):
            messages.append(("ok", msg))

        @staticmethod
        def warn(msg, **kwargs):
            messages.append(("warn", msg))

        @staticmethod
        def error(msg, **kwargs):
            messages.append(("error", msg))

        @staticmethod
        def status(msg, **kwargs):
            messages.append(("status", msg))

    monkeypatch.setattr(sql_batch_runner_module, "Console", _ConsoleCapture)
    runner._test_sql_connection = lambda: False  # type: ignore[method-assign]

    success = runner.process_equipment("FD_FAN")

    assert success is False
    assert any(
        "Final summary | status=FAIL" in msg and "note=sql_connection_failure" in msg
        for _, msg in messages
    )


def test_process_equipment_emits_final_summary_on_success(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path)
    messages = []

    class _ConsoleCapture:
        @staticmethod
        def header(msg, **kwargs):
            messages.append(("header", msg))

        @staticmethod
        def info(msg, **kwargs):
            messages.append(("info", msg))

        @staticmethod
        def ok(msg, **kwargs):
            messages.append(("ok", msg))

        @staticmethod
        def warn(msg, **kwargs):
            messages.append(("warn", msg))

        @staticmethod
        def error(msg, **kwargs):
            messages.append(("error", msg))

        @staticmethod
        def status(msg, **kwargs):
            messages.append(("status", msg))

    monkeypatch.setattr(sql_batch_runner_module, "Console", _ConsoleCapture)
    runner._test_sql_connection = lambda: True  # type: ignore[method-assign]
    runner._load_progress = lambda: {}  # type: ignore[method-assign]
    runner._get_equip_id = lambda equip_name: None  # type: ignore[method-assign]
    runner._log_historian_overview = lambda equip_name: True  # type: ignore[method-assign]
    runner._process_coldstart = lambda equip_name, dry_run=False: (True, None)  # type: ignore[method-assign]
    runner._process_batches = lambda equip_name, start_from=None, dry_run=False, resume=False: BatchProcessingResult(  # type: ignore[method-assign]
        completed=2,
        attempted=2,
        failed=False,
    )

    success = runner.process_equipment("FD_FAN")

    assert success is True
    assert any(
        "Final summary | status=SUCCESS" in msg and "batches_processed=2" in msg and "note=batches_processed" in msg
        for _, msg in messages
    )


def test_process_equipment_emits_final_summary_on_exception(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path)
    messages = []

    class _ConsoleCapture:
        @staticmethod
        def header(msg, **kwargs):
            messages.append(("header", msg))

        @staticmethod
        def info(msg, **kwargs):
            messages.append(("info", msg))

        @staticmethod
        def ok(msg, **kwargs):
            messages.append(("ok", msg))

        @staticmethod
        def warn(msg, **kwargs):
            messages.append(("warn", msg))

        @staticmethod
        def error(msg, **kwargs):
            messages.append(("error", msg))

        @staticmethod
        def status(msg, **kwargs):
            messages.append(("status", msg))

    monkeypatch.setattr(sql_batch_runner_module, "Console", _ConsoleCapture)
    runner._test_sql_connection = lambda: True  # type: ignore[method-assign]
    runner._load_progress = lambda: {}  # type: ignore[method-assign]
    runner._get_equip_id = lambda equip_name: None  # type: ignore[method-assign]
    runner._log_historian_overview = lambda equip_name: True  # type: ignore[method-assign]
    runner._process_coldstart = lambda equip_name, dry_run=False: (True, None)  # type: ignore[method-assign]

    def _raise_batches(*args, **kwargs):
        raise RuntimeError("batch exploded")

    runner._process_batches = _raise_batches  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="batch exploded"):
        runner.process_equipment("FD_FAN")

    assert any(
        "Final summary | status=FAIL" in msg and "note=exception:RuntimeError" in msg
        for _, msg in messages
    )


def test_process_equipment_fails_when_post_coldstart_batch_fails(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path)
    messages = []

    class _ConsoleCapture:
        @staticmethod
        def header(msg, **kwargs):
            messages.append(("header", msg))

        @staticmethod
        def info(msg, **kwargs):
            messages.append(("info", msg))

        @staticmethod
        def ok(msg, **kwargs):
            messages.append(("ok", msg))

        @staticmethod
        def warn(msg, **kwargs):
            messages.append(("warn", msg))

        @staticmethod
        def error(msg, **kwargs):
            messages.append(("error", msg))

        @staticmethod
        def status(msg, **kwargs):
            messages.append(("status", msg))

    monkeypatch.setattr(sql_batch_runner_module, "Console", _ConsoleCapture)
    runner._test_sql_connection = lambda: True  # type: ignore[method-assign]
    runner._load_progress = lambda: {}  # type: ignore[method-assign]
    runner._get_equip_id = lambda equip_name: None  # type: ignore[method-assign]
    runner._log_historian_overview = lambda equip_name: True  # type: ignore[method-assign]
    runner._process_coldstart = lambda equip_name, dry_run=False: (True, datetime(2024, 1, 1, 0, 9, 59))  # type: ignore[method-assign]
    runner._process_batches = lambda equip_name, start_from=None, dry_run=False, resume=False: BatchProcessingResult(  # type: ignore[method-assign]
        completed=0,
        attempted=1,
        failed=True,
    )

    success = runner.process_equipment("FD_FAN")

    assert success is False
    assert any(
        "Final summary | status=FAIL" in msg and "note=batch_failed" in msg
        for _, msg in messages
    )
    assert not any("note=coldstart_only_no_batches" in msg for _, msg in messages)


def test_process_equipment_marks_coldstart_only_when_no_batches_were_attempted(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path)
    messages = []

    class _ConsoleCapture:
        @staticmethod
        def header(msg, **kwargs):
            messages.append(("header", msg))

        @staticmethod
        def info(msg, **kwargs):
            messages.append(("info", msg))

        @staticmethod
        def ok(msg, **kwargs):
            messages.append(("ok", msg))

        @staticmethod
        def warn(msg, **kwargs):
            messages.append(("warn", msg))

        @staticmethod
        def error(msg, **kwargs):
            messages.append(("error", msg))

        @staticmethod
        def status(msg, **kwargs):
            messages.append(("status", msg))

    monkeypatch.setattr(sql_batch_runner_module, "Console", _ConsoleCapture)
    runner._test_sql_connection = lambda: True  # type: ignore[method-assign]
    runner._load_progress = lambda: {}  # type: ignore[method-assign]
    runner._get_equip_id = lambda equip_name: None  # type: ignore[method-assign]
    runner._log_historian_overview = lambda equip_name: True  # type: ignore[method-assign]
    runner._process_coldstart = lambda equip_name, dry_run=False: (True, datetime(2024, 1, 1, 0, 9, 59))  # type: ignore[method-assign]
    runner._process_batches = lambda equip_name, start_from=None, dry_run=False, resume=False: BatchProcessingResult(  # type: ignore[method-assign]
        completed=0,
        attempted=0,
        failed=False,
    )

    success = runner.process_equipment("FD_FAN")

    assert success is True
    assert any(
        "Final summary | status=SUCCESS" in msg and "note=coldstart_only_no_batches" in msg
        for _, msg in messages
    )


def test_main_emits_final_summary_on_runner_failure(monkeypatch, tmp_path):
    messages = []

    class _ConsoleCapture:
        @staticmethod
        def header(msg, **kwargs):
            messages.append(("header", msg))

        @staticmethod
        def info(msg, **kwargs):
            messages.append(("info", msg))

        @staticmethod
        def ok(msg, **kwargs):
            messages.append(("ok", msg))

        @staticmethod
        def warn(msg, **kwargs):
            messages.append(("warn", msg))

        @staticmethod
        def error(msg, **kwargs):
            messages.append(("error", msg))

        @staticmethod
        def status(msg, **kwargs):
            messages.append(("status", msg))

    class _StubRunner:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def process_equipment(self, equip_name: str, *, dry_run: bool = False, resume: bool = False) -> bool:
            _ = (dry_run, resume)
            return False

    monkeypatch.setattr(sql_batch_runner_module, "Console", _ConsoleCapture)
    monkeypatch.setattr(sql_batch_runner_module, "SQLBatchRunner", _StubRunner)
    monkeypatch.setattr(sql_batch_runner_module, "init_observability", lambda **kwargs: None)
    monkeypatch.setattr(sql_batch_runner_module, "start_profiling", lambda: None)
    monkeypatch.setattr(sql_batch_runner_module, "stop_profiling", lambda: None)
    monkeypatch.setattr(sql_batch_runner_module, "shutdown_observability", lambda: None)
    monkeypatch.setattr(sql_batch_runner_module, "Path", lambda *_args, **_kwargs: tmp_path)
    monkeypatch.setattr(
        sql_batch_runner_module.sys,
        "argv",
        ["sql_batch_runner.py", "--equip", "FD_FAN"],
    )

    exit_code = sql_batch_runner_module.main()

    assert exit_code == 1
    assert any(
        "BATCH RUNNER FINAL SUMMARY | status=FAIL | equipment=1 | succeeded=0 | failed=1" in msg
        for _, msg in messages
    )

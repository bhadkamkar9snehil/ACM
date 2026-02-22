from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from scripts.sql_batch_runner import SQLBatchRunner


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

    completed = runner._process_batches("FD_FAN", resume=True)

    assert completed == 1
    assert starts
    assert starts[0] == datetime(2024, 1, 1, 0, 10, 0)

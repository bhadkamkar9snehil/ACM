from __future__ import annotations

import json
import io
from datetime import datetime
from pathlib import Path

import pytest

import scripts.sql_batch_runner as sql_batch_runner_module
from scripts.sql_batch_runner import BatchProcessingResult, RunInspectionSummary, SQLBatchRunner


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

    def fetchall(self):
        rows = list(self._rows)
        self._rows.clear()
        return rows

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


def test_validate_representation_sql_contract_reports_missing_tables_and_columns(tmp_path):
    runner = SQLBatchRunner(
        sql_conn_string="DRIVER={ODBC Driver 17 for SQL Server};SERVER=.;DATABASE=ACM;Trusted_Connection=yes;",
        artifact_root=tmp_path,
        representation_authority="validation",
    )

    class _Cursor:
        def __init__(self):
            self.queries = []

        def execute(self, query, params=None):
            self.queries.append((str(query), tuple(params) if params else ()))
            return self

        def fetchall(self):
            query = self.queries[-1][0]
            if "FROM sys.tables" in query:
                return [("ACM_RepresentationStatus",), ("ACM_SignalProfiles",)]
            if "FROM sys.columns" in query:
                return [("RepresentationAuthoritative",), ("RepresentationScoreAllowed",)]
            return []

    class _Conn:
        def __init__(self):
            self.cursor_obj = _Cursor()

        def cursor(self):
            return self.cursor_obj

        def close(self):
            return None

    runner._get_sql_connection = lambda: _Conn()  # type: ignore[method-assign]

    ok, issues = runner._validate_representation_sql_contract()

    assert ok is False
    assert any("missing tables:" in issue and "ACM_RepresentationSchemas" in issue for issue in issues)
    assert any("missing ACM_Runs columns:" in issue and "RepresentationLearnAllowed" in issue for issue in issues)


def test_process_equipment_fails_fast_when_validation_sql_contract_is_missing(tmp_path, monkeypatch):
    runner = SQLBatchRunner(
        sql_conn_string="DRIVER={ODBC Driver 17 for SQL Server};SERVER=.;DATABASE=ACM;Trusted_Connection=yes;",
        artifact_root=tmp_path,
        representation_authority="validation",
    )
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
    runner._validate_representation_sql_contract = lambda: (False, ["missing tables: ACM_RepresentationStatus"])  # type: ignore[method-assign]

    success = runner.process_equipment("FD_FAN")

    assert success is False
    assert any("Validation authority requires representation SQL contract" in msg for _, msg in messages)
    assert any(
        "Final summary | status=FAIL" in msg and "note=representation_sql_contract_missing" in msg
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


def test_process_equipment_emits_acm_derived_summary_details_when_available(tmp_path, monkeypatch):
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
    runner._get_equip_id = lambda equip_name: 5010  # type: ignore[method-assign]
    runner._log_historian_overview = lambda equip_name: True  # type: ignore[method-assign]
    runner._process_coldstart = lambda equip_name, dry_run=False: (True, None)  # type: ignore[method-assign]
    runner._process_batches = lambda equip_name, start_from=None, dry_run=False, resume=False: BatchProcessingResult(  # type: ignore[method-assign]
        completed=14,
        attempted=14,
        failed=False,
    )
    runner._inspect_last_run_outputs = lambda equip_name: RunInspectionSummary(  # type: ignore[method-assign]
        run_id="run-123",
        run_source="ACM_Runs",
        started_at=datetime(2026, 3, 10, 0, 0, 0),
        completed_at=datetime(2026, 3, 10, 0, 20, 34),
        source_window_start=datetime(2023, 5, 21, 18, 16, 0),
        source_window_end=datetime(2023, 6, 15, 16, 39, 59),
        duration_seconds=1234,
        train_row_count=500,
        score_row_count=1781,
        episode_count=3,
        health_status="HEALTHY",
        avg_health_index=96.2,
        min_health_index=88.4,
        max_fused_z=2.37,
        data_quality_score=99.1,
        refit_requested=False,
        zero_day_scoring_active=True,
        zero_day_status="active_hdbscan",
        zero_day_surface_type="raw_numeric",
        zero_day_channel_count=79,
        representation_authoritative=True,
        representation_score_allowed=False,
        representation_learn_allowed=False,
        representation_context_label="UNKNOWN",
        representation_runtime_mode="ONLINE_SCORING",
        representation_schema_compatibility="COMPATIBLE",
        representation_basis_compatibility="COMPATIBLE",
        representation_baseline_compatibility="COMPATIBLE",
        representation_suppressed_reasons='["context_unknown"]',
        representation_degraded_reasons="[]",
        forecast_outputs_required=False,
        table_counts={
            "ACM_Scores_Wide": 1781,
            "ACM_HealthTimeline": 1781,
            "ACM_RegimeTimeline": 1781,
            "ACM_SensorHotspots": 12,
            "ACM_RepresentationStatus": 1,
            "ACM_HealthForecast": 0,
            "ACM_FailureForecast": 0,
            "ACM_RUL": 0,
        },
        run_log_total=245,
        run_log_warn=7,
        run_log_error=0,
    )

    success = runner.process_equipment("WFA_TURBINE_10")

    assert success is True
    assert any("Final summary | status=SUCCESS" in msg for _, msg in messages)
    assert any("ACM run | run_id=run-123" in msg for _, msg in messages)
    assert any("exec_window=[2026-03-10 00:00:00 -> 2026-03-10 00:20:34]" in msg for _, msg in messages)
    assert any("source_data_window=[2023-05-21 18:16:00 -> 2023-06-15 16:39:59]" in msg for _, msg in messages)
    assert any("ACM metrics | train_rows=500 | score_rows=1781 | health_status=HEALTHY" in msg for _, msg in messages)
    assert any("Zero-day | active=yes | status=active_hdbscan | surface=raw_numeric | channels=79" in msg for _, msg in messages)
    assert any("Outputs | scores=1781 | health_timeline=1781 | regime_timeline=1781 | episodes=3" in msg for _, msg in messages)
    assert any("Representation | mode=ONLINE_SCORING | authoritative=yes | score_allowed=no | learn_allowed=no" in msg for _, msg in messages)
    assert any("Logs | run_logs=245 | warnings=7 | errors=0" in msg for _, msg in messages)


def test_run_acm_batch_passes_representation_authority_cli(tmp_path, monkeypatch):
    runner = SQLBatchRunner(
        sql_conn_string="DRIVER={ODBC Driver 17 for SQL Server};SERVER=.;DATABASE=ACM;Trusted_Connection=yes;",
        artifact_root=tmp_path,
        tick_minutes=10,
        max_coldstart_attempts=2,
        representation_authority="validation",
    )
    runner._inspect_last_run_outputs = lambda equip_name, **kwargs: None  # type: ignore[method-assign]
    captured = {"cmd": None}

    class _FakeProcess:
        def __init__(self, cmd):
            captured["cmd"] = cmd
            self.returncode = 0
            self.stdout = io.StringIO("RUN END: outcome=OK\n")

        def wait(self):
            return 0

    monkeypatch.setattr(sql_batch_runner_module, "get_trace_context", lambda: {})
    monkeypatch.setattr(sql_batch_runner_module.subprocess, "Popen", lambda cmd, **kwargs: _FakeProcess(cmd))

    success, outcome = runner._run_acm_batch(
        "FD_FAN",
        start_time=datetime(2026, 1, 1, 0, 0, 0),
        end_time=datetime(2026, 1, 1, 0, 9, 59),
    )

    assert success is True
    assert outcome == "OK"
    assert captured["cmd"] is not None
    assert "--representation-authority" in captured["cmd"]
    assert "validation" in captured["cmd"]


def test_run_acm_batch_preserves_degraded_outcome_and_still_inspects_outputs(tmp_path, monkeypatch):
    runner = SQLBatchRunner(
        sql_conn_string="DRIVER={ODBC Driver 17 for SQL Server};SERVER=.;DATABASE=ACM;Trusted_Connection=yes;",
        artifact_root=tmp_path,
        tick_minutes=10,
        max_coldstart_attempts=2,
        representation_authority="validation",
    )
    inspected = []

    class _FakeProcess:
        def __init__(self):
            self.returncode = 0
            self.stdout = io.StringIO(
                "RUN START: run_id=11111111-2222-3333-4444-555555555555 equip=WFA_TURBINE_10\n"
                "RUN END: outcome=DEGRADED\n"
                "Finalized RunID=11111111-2222-3333-4444-555555555555 outcome=DEGRADED\n"
            )

        def wait(self):
            return 0

    monkeypatch.setattr(sql_batch_runner_module, "get_trace_context", lambda: {})
    monkeypatch.setattr(sql_batch_runner_module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    runner._inspect_last_run_outputs = lambda equip_name, **kwargs: inspected.append((equip_name, kwargs))  # type: ignore[method-assign]

    success, outcome = runner._run_acm_batch("WFA_TURBINE_10")

    assert success is True
    assert outcome == "DEGRADED"
    assert inspected == [
        (
            "WFA_TURBINE_10",
            {
                "acm_outcome": "DEGRADED",
                "prefer_run_id": "11111111-2222-3333-4444-555555555555",
                "source_window_start": None,
                "source_window_end": None,
            },
        )
    ]


def test_run_acm_batch_passes_source_window_to_output_inspection(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path)
    inspected = []

    class _FakeProcess:
        def __init__(self):
            self.returncode = 0
            self.stdout = io.StringIO(
                "RUN START: run_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee equip=FD_FAN\n"
                "RUN END: outcome=OK\n"
            )

        def wait(self):
            return 0

    monkeypatch.setattr(sql_batch_runner_module, "get_trace_context", lambda: {})
    monkeypatch.setattr(sql_batch_runner_module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    runner._inspect_last_run_outputs = lambda equip_name, **kwargs: inspected.append((equip_name, kwargs))  # type: ignore[method-assign]

    start_time = datetime(2026, 1, 1, 0, 0, 0)
    end_time = datetime(2026, 1, 1, 0, 9, 59)
    success, outcome = runner._run_acm_batch("FD_FAN", start_time=start_time, end_time=end_time)

    assert success is True
    assert outcome == "OK"
    assert inspected == [
        (
            "FD_FAN",
            {
                "acm_outcome": "OK",
                "prefer_run_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "source_window_start": start_time,
                "source_window_end": end_time,
            },
        )
    ]


def test_process_coldstart_treats_degraded_run_as_progress(tmp_path):
    runner = _make_runner(tmp_path)
    runner._get_data_range = lambda equip_name: (datetime(2024, 1, 1, 0, 0, 0), datetime(2024, 1, 3, 0, 0, 0))  # type: ignore[method-assign]
    statuses = iter([(False, 0, 500), (True, 500, 500)])
    runner._check_coldstart_status = lambda equip_name: next(statuses)  # type: ignore[method-assign]
    runner._run_acm_batch = lambda *args, **kwargs: (True, "DEGRADED")  # type: ignore[method-assign]

    success, last_processed_end = runner._process_coldstart("WFA_TURBINE_10")

    assert success is True
    assert last_processed_end is not None


def test_process_coldstart_expands_window_on_noop_until_progress(tmp_path):
    runner = _make_runner(tmp_path)
    runner._get_data_range = lambda equip_name: (  # type: ignore[method-assign]
        datetime(2024, 1, 1, 0, 0, 0),
        datetime(2024, 1, 8, 0, 0, 0),
    )
    statuses = iter([(False, 0, 500), (False, 0, 500), (True, 500, 500)])
    runner._check_coldstart_status = lambda equip_name: next(statuses)  # type: ignore[method-assign]

    calls = []

    def _run_batch(equip_name, start_time=None, end_time=None, **kwargs):
        calls.append((start_time, end_time))
        return (True, "NOOP") if len(calls) == 1 else (True, "DEGRADED")

    runner._run_acm_batch = _run_batch  # type: ignore[method-assign]

    success, last_processed_end = runner._process_coldstart("WFA_TURBINE_10")

    assert success is True
    assert last_processed_end == calls[-1][1]
    assert len(calls) == 2
    assert calls[1][0] == calls[0][0]
    assert calls[1][1] > calls[0][1]


def test_process_coldstart_stops_retrying_when_full_history_is_exhausted(tmp_path):
    runner = _make_runner(tmp_path)
    runner._get_data_range = lambda equip_name: (  # type: ignore[method-assign]
        datetime(2024, 1, 1, 0, 0, 0),
        datetime(2024, 1, 1, 0, 9, 59),
    )
    runner._check_coldstart_status = lambda equip_name: (False, 0, 500)  # type: ignore[method-assign]
    calls = []
    runner._run_acm_batch = lambda *args, **kwargs: (calls.append(1) or True, "NOOP")  # type: ignore[method-assign]

    success, _ = runner._process_coldstart("WFA_TURBINE_10")

    assert success is False
    assert len(calls) == 1


def test_inspect_outputs_treats_suppressed_score_tables_as_expected(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path)
    messages = []

    class _ConsoleCapture:
        @staticmethod
        def info(msg, **kwargs):
            messages.append(("info", msg))

        @staticmethod
        def warn(msg, **kwargs):
            messages.append(("warn", msg))

        @staticmethod
        def error(msg, **kwargs):
            messages.append(("error", msg))

    monkeypatch.setattr(sql_batch_runner_module, "Console", _ConsoleCapture)
    runner._get_equip_id = lambda equip_name: 5010  # type: ignore[method-assign]
    runner._should_expect_forecast_outputs = lambda equip_id, run_id: False  # type: ignore[method-assign]

    class _InterleavedCursor:
        def __init__(self, responses):
            self._responses = list(responses)

        def execute(self, query, params=None):
            _ = (query, params)
            return self

        def fetchone(self):
            if not self._responses:
                return None
            value = self._responses.pop(0)
            return value

        def fetchall(self):
            if not self._responses:
                return []
            value = self._responses.pop(0)
            return list(value)

        def close(self):
            return None

    class _InterleavedConn:
        def __init__(self, responses):
            self.cursor_obj = _InterleavedCursor(responses)

        def cursor(self):
            return self.cursor_obj

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def close(self):
            return None

    rows = [
        ("run-123", datetime(2026, 3, 12, 12, 0, 0), datetime(2026, 3, 12, 12, 10, 0)),
        [("StartedAt",), ("CompletedAt",), ("ScoreRowCount",)],
        (datetime(2026, 3, 12, 12, 0, 0), datetime(2026, 3, 12, 12, 10, 0), 1795),
        (True, False, False, "REGIME_-1", "COMPATIBLE", "INCOMPATIBLE", "PENDING", '["representation_score_suppressed"]', '["representation_score_suppressed"]'),
        ("ONLINE_SCORING",),
        (0,),
        (0,),
        (0,),
        (0,),
        (0,),
        (0,),
        (0,),
        (0,),
        (3160,),
        (0,),
        (63,),
        (0,),
        (0,),
        (0,),
        (0,),
        (1,),
        (2,),
        (1,),
        (1,),
        (3940,),
        (1,),
        (0,),
        (0,),
        (1,),
        (79,),
        (1,),
        (1,),
        (0,),
        [],
        [],
        (0, 0, 0),
    ]
    runner._get_sql_connection = lambda: _InterleavedConn(rows)  # type: ignore[method-assign]

    summary = runner._inspect_last_run_outputs("WFA_TURBINE_10")

    assert summary is not None
    assert summary.representation_authoritative is True
    assert summary.representation_score_allowed is False
    assert any(
        "QA expected: ACM_Scores_Wide has 0 rows because authoritative representation suppression disabled score-derived persistence"
        in msg
        for level, msg in messages
        if level == "info"
    )
    assert not any(
        "QA check failed: ACM_Scores_Wide has 0 rows" in msg
        for level, msg in messages
        if level == "warn"
    )


def test_inspect_outputs_treats_noop_runs_as_expected_zero_output(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path)
    messages = []

    class _ConsoleCapture:
        @staticmethod
        def info(msg, **kwargs):
            messages.append(("info", msg))

        @staticmethod
        def warn(msg, **kwargs):
            messages.append(("warn", msg))

        @staticmethod
        def error(msg, **kwargs):
            messages.append(("error", msg))

    monkeypatch.setattr(sql_batch_runner_module, "Console", _ConsoleCapture)
    runner._get_equip_id = lambda equip_name: 5010  # type: ignore[method-assign]
    runner._should_expect_forecast_outputs = lambda equip_id, run_id: False  # type: ignore[method-assign]

    class _InterleavedCursor:
        def __init__(self, responses):
            self._responses = list(responses)

        def execute(self, query, params=None):
            _ = (query, params)
            return self

        def fetchone(self):
            if not self._responses:
                return None
            return self._responses.pop(0)

        def fetchall(self):
            if not self._responses:
                return []
            value = self._responses.pop(0)
            return list(value)

        def close(self):
            return None

    class _InterleavedConn:
        def __init__(self, responses):
            self.cursor_obj = _InterleavedCursor(responses)

        def cursor(self):
            return self.cursor_obj

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def close(self):
            return None

    rows = [
        ("run-123", datetime(2026, 3, 12, 12, 0, 0), datetime(2026, 3, 12, 12, 0, 1)),
        [("StartedAt",), ("CompletedAt",), ("ScoreRowCount",), ("HealthStatus",)],
        (datetime(2026, 3, 12, 12, 0, 0), datetime(2026, 3, 12, 12, 0, 1), 0, "UNKNOWN"),
        (None, None, None, None, None, None, None, None, None),
        (None,),
        (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,),
        (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,),
        [],
        [],
        (0, 0, 0),
    ]
    runner._get_sql_connection = lambda: _InterleavedConn(rows)  # type: ignore[method-assign]

    summary = runner._inspect_last_run_outputs(
        "WFA_TURBINE_10",
        prefer_run_id="run-123",
        acm_outcome="NOOP",
    )

    assert summary is not None
    assert summary.run_outcome == "NOOP"
    assert any(
        "QA expected: ACM_Scores_Wide has 0 rows because ACM outcome=NOOP produced no persisted batch outputs"
        in msg
        for level, msg in messages
        if level == "info"
    )
    assert not any(
        "QA check failed: ACM_Scores_Wide has 0 rows" in msg
        for level, msg in messages
        if level == "warn"
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


def test_main_respects_env_observability_disable(monkeypatch, tmp_path):
    captured = {}
    profiled = {"count": 0}

    class _ConsoleCapture:
        @staticmethod
        def info(msg, **kwargs):
            _ = (msg, kwargs)

        @staticmethod
        def ok(msg, **kwargs):
            _ = (msg, kwargs)

        @staticmethod
        def warn(msg, **kwargs):
            _ = (msg, kwargs)

        @staticmethod
        def error(msg, **kwargs):
            _ = (msg, kwargs)

        @staticmethod
        def header(msg, **kwargs):
            _ = (msg, kwargs)

        @staticmethod
        def status(msg, **kwargs):
            _ = (msg, kwargs)

        @staticmethod
        def debug(msg, **kwargs):
            _ = (msg, kwargs)

    class _StubRunner:
        def __init__(self, **kwargs) -> None:
            _ = kwargs

        def process_equipment(self, equip_name: str, *, dry_run: bool = False, resume: bool = False) -> bool:
            _ = (equip_name, dry_run, resume)
            return True

    def _init_observability(**kwargs):
        captured.update(kwargs)

    def _start_profiling():
        profiled["count"] += 1

    monkeypatch.setenv("ACM_OBS_DISABLE", "1")
    monkeypatch.setattr(sql_batch_runner_module, "Console", _ConsoleCapture)
    monkeypatch.setattr(sql_batch_runner_module, "SQLBatchRunner", _StubRunner)
    monkeypatch.setattr(sql_batch_runner_module, "init_observability", _init_observability)
    monkeypatch.setattr(sql_batch_runner_module, "start_profiling", _start_profiling)
    monkeypatch.setattr(sql_batch_runner_module, "stop_profiling", lambda: None)
    monkeypatch.setattr(sql_batch_runner_module, "shutdown_observability", lambda: None)
    monkeypatch.setattr(sql_batch_runner_module, "Path", lambda *_args, **_kwargs: tmp_path)
    monkeypatch.setattr(
        sql_batch_runner_module.sys,
        "argv",
        ["sql_batch_runner.py", "--equip", "FD_FAN"],
    )

    exit_code = sql_batch_runner_module.main()

    assert exit_code == 0
    assert captured["enable_tracing"] is False
    assert captured["enable_metrics"] is False
    assert captured["enable_loki"] is False
    assert captured["enable_profiling"] is False
    assert profiled["count"] == 0

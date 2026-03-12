from __future__ import annotations

import pandas as pd

from core.pipeline_types import run_data_guardrails
from core.signal_profiler import (
    build_signal_profile_summary,
    detect_low_variance_signals,
    profile_signal_frame,
)


def _frame() -> pd.DataFrame:
    idx = pd.date_range("2026-01-01 00:00:00", periods=4, freq="h")
    return pd.DataFrame(
        {
            "good": [1.0, 2.0, 3.0, 4.0],
            "weak_missing": [1.0, None, None, 4.0],
            "flat": [5.0, 5.0, 5.0, 5.0],
            "nullish": [None, None, None, None],
        },
        index=idx,
    )


def test_profile_signal_frame_classifies_signal_monitorability() -> None:
    profiles = profile_signal_frame(_frame(), min_valid_fraction=0.75)
    profile_by_name = {profile.signal_name: profile for profile in profiles}

    assert profile_by_name["good"].monitorability_class == "MONITORABLE"
    assert profile_by_name["weak_missing"].monitorability_class == "WEAK"
    assert "low_valid_fraction" in profile_by_name["weak_missing"].reason_codes
    assert profile_by_name["flat"].monitorability_class == "WEAK"
    assert "low_variance" in profile_by_name["flat"].reason_codes
    assert profile_by_name["nullish"].monitorability_class == "UNTRUSTED"
    assert "all_null" in profile_by_name["nullish"].reason_codes


def test_build_signal_profile_summary_aggregates_profile_counts() -> None:
    summary = build_signal_profile_summary(_frame(), min_valid_fraction=0.75)

    assert summary.monitorable_signal_count == 1
    assert summary.weak_signal_count == 2
    assert summary.untrusted_signal_count == 1
    assert "profiled_numeric_signals" in summary.reason_codes


def test_detect_low_variance_signals_matches_guardrail_semantics() -> None:
    out = detect_low_variance_signals(_frame(), low_variance_threshold=1e-4)

    assert out == ["flat"]


def test_run_data_guardrails_uses_shared_low_variance_detection(tmp_path, monkeypatch) -> None:
    train = _frame()[["good", "flat"]]
    score = train.tail(2).copy()
    meta = type("Meta", (), {"dropped_cols": ["dropped_sensor"]})()
    monkeypatch.chdir(tmp_path)

    class _OutputManager:
        def __init__(self) -> None:
            self.writes = []

        def _build_data_quality_records(self, **kwargs):
            return [{"sensor": "_SUMMARY_2_SENSORS"}]

        def write_sql_table(self, **kwargs):
            self.writes.append(kwargs)

    out_mgr = _OutputManager()

    result = run_data_guardrails(
        train=train,
        score=score,
        meta=meta,
        cfg={},
        output_manager=out_mgr,
        run_id=123,
        equip_id=77,
        equip="FD_FAN",
    )

    assert result.low_var_features == ["flat"]
    assert result.data_quality_written is True
    assert result.dropped_sensors == ["dropped_sensor"]
    assert len(out_mgr.writes) == 1
    assert out_mgr.writes[0]["table_name"] == "ACM_DataQuality"

from dataclasses import replace

import pandas as pd

from core.representation_contracts import CompatibilityStatus, ContextAssignment
from core.representation_pipeline import enrich_representation_shadow, run_representation_pipeline
from core.representation_store import (
    build_baseline_governance_df,
    build_representation_schemas_df,
    build_representation_status_df,
    build_signal_profiles_df,
    persist_representation_artifacts,
)


def _frame(start: str, periods: int, values_a: list[float], values_b: list[float]) -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=periods, freq="1h", name="EntryDateTime")
    return pd.DataFrame({"sensor_a": values_a, "sensor_b": values_b}, index=idx)


def _shadow_result():
    train = _frame("2024-01-01T00:00:00", 3, [1.0, 2.0, 3.0], [10.0, 20.0, 30.0])
    score = _frame("2024-01-01T03:00:00", 2, [4.0, 5.0], [40.0, 50.0])
    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta={"sampling_seconds": 3600.0},
        cfg={},
        equip_id=42,
        run_id="run-42",
    )
    return enrich_representation_shadow(
        result,
        cfg={},
        context=ContextAssignment(
            context_id="regime:1",
            context_label="REGIME_1",
            context_confidence=0.95,
            context_stability="STABLE",
            transition_status="STEADY",
            is_novel=False,
            is_ambiguous=False,
        ),
        compatibility=CompatibilityStatus(
            schema_compatibility="COMPATIBLE",
            basis_compatibility="COMPATIBLE",
            baseline_compatibility="COMPATIBLE",
        ),
    ), score


def test_build_representation_status_df_contains_queryable_shadow_fields() -> None:
    result, _score = _shadow_result()

    df = build_representation_status_df(result)

    assert list(df["RunID"]) == ["run-42"]
    assert df.loc[0, "ContextLabel"] == "REGIME_1"
    assert bool(df.loc[0, "ScoreAllowed"]) is True
    assert df.loc[0, "SchemaCompatibility"] == "COMPATIBLE"
    assert "comparability_shadow_evaluated" in df.loc[0, "NotesJson"]


def test_build_signal_profiles_df_emits_per_signal_rows() -> None:
    result, score = _shadow_result()

    df = build_signal_profiles_df(result, score)

    assert set(df["SignalName"]) == {"sensor_a", "sensor_b"}
    assert set(df["SignalProfileVersion"]) == {result.refs.signal_profile_version}


def test_build_representation_schema_and_baseline_frames_are_singleton_rows() -> None:
    result, _score = _shadow_result()

    schema_df = build_representation_schemas_df(result)
    baseline_df = build_baseline_governance_df(result)

    assert len(schema_df) == 1
    assert len(baseline_df) == 1
    assert schema_df.loc[0, "BasisCompatibility"] == "COMPATIBLE"
    assert baseline_df.loc[0, "RuntimeMode"] == result.baseline_governance.runtime_mode.value


def test_persist_representation_artifacts_writes_all_control_plane_tables() -> None:
    result, score = _shadow_result()
    captured = {}

    class _OutputManager:
        def _can_write_dataframe(self, df, require_healthy_sql=True):
            return True

        def write_sql_table(self, **kwargs):
            captured[kwargs["table_name"]] = kwargs["df"].copy()
            return {"inserted": len(kwargs["df"])}

    persisted = persist_representation_artifacts(
        _OutputManager(),
        result,
        signal_source_df=score,
    )

    assert persisted.representation_status_rows == 1
    assert persisted.signal_profile_rows == 2
    assert persisted.representation_schema_rows == 1
    assert persisted.baseline_governance_rows == 1
    assert persisted.total_rows == 5
    assert set(captured) == {
        "ACM_RepresentationStatus",
        "ACM_SignalProfiles",
        "ACM_RepresentationSchemas",
        "ACM_BaselineGovernance",
    }


def test_persist_representation_artifacts_warns_when_no_rows_are_written() -> None:
    result, score = _shadow_result()
    captured = {"warn": []}

    class _OutputManager:
        def _can_write_dataframe(self, df, require_healthy_sql=True):
            return True

        def write_sql_table(self, **kwargs):
            return {"inserted": 0}

    class _Logger:
        def info(self, *args, **kwargs):
            raise AssertionError("info should not be used when nothing is written")

        def warn(self, message, **kwargs):
            captured["warn"].append((message, kwargs))

    persisted = persist_representation_artifacts(
        _OutputManager(),
        result,
        signal_source_df=score,
        logger=_Logger(),
    )

    assert persisted.total_rows == 0
    assert captured["warn"]
    assert "produced no SQL rows" in captured["warn"][0][0]

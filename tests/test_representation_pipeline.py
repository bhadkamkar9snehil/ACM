from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from core.data_loader import DataMeta
from core.representation_contracts import (
    CompatibilityStatus,
    ContextAssignment,
    RuntimeMode,
    SignalProfile,
)
from core.representation_pipeline import (
    apply_representation_authority,
    enrich_representation_shadow,
    refresh_representation_runtime_authority,
    resolve_representation_authority_policy,
    run_representation_pipeline,
)


def _frame(start: str, periods: int, freq: str = "1h") -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=periods, freq=freq, name="EntryDateTime")
    return pd.DataFrame(
        {
            "sensor_a": [1.0, 2.0, 3.0][:periods],
            "sensor_b": [10.0, None, 30.0][:periods],
        },
        index=idx,
    )


def test_representation_pipeline_builds_shadow_states_from_datameta() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = _frame("2024-01-01T03:00:00", 2)
    meta = DataMeta(
        timestamp_col="EntryDateTime",
        cadence_ok=True,
        kept_cols=["sensor_a", "sensor_b"],
        dropped_cols=[],
        start_ts=train.index.min(),
        end_ts=score.index.max(),
        n_rows=5,
        sampling_seconds=3600.0,
        dup_timestamps_removed=2,
        future_rows_dropped=1,
    )

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta=meta,
        cfg={},
        equip_id=42,
        run_id="run-42",
    )

    assert result.enabled is True
    assert result.authoritative is False
    assert result.score_state is not None
    assert result.train_state is not None
    assert result.score_state.integrity.expected_rows == 2
    assert result.score_state.integrity.observed_rows == 2
    assert result.score_state.integrity.duplicate_rows_removed == 2
    assert result.score_state.integrity.future_rows_dropped == 1
    assert result.eligibility.score_allowed is False
    assert "context_unassessed" in result.eligibility.suppressed_reason_codes
    assert result.baseline_governance.runtime_mode == RuntimeMode.ONLINE_SCORING
    assert result.notes == (
        "shadow_mode_not_authoritative",
        "contracts_slice",
        "comparability_shadow_evaluated",
    )


def test_representation_pipeline_uses_coldstart_meta_for_runtime_mode() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = _frame("2024-01-01T03:00:00", 2)
    meta = {
        "is_coldstart_run": True,
        "sampling_seconds": 3600.0,
        "dup_timestamps_removed": 0,
        "future_rows_dropped": 0,
    }

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta=meta,
        cfg={},
        equip_id=7,
        run_id="run-coldstart",
    )

    assert result.baseline_governance.runtime_mode == RuntimeMode.BASELINE_FORMATION
    assert result.baseline_governance.enough_history_to_proceed is True
    assert result.baseline_governance.baseline_ready is False
    assert result.baseline_governance.readiness_state == "FORMING"
    assert result.signal_summary.monitorable_signal_count == 2
    assert result.eligibility.score_allowed is False
    assert result.eligibility.learn_allowed is True


def test_representation_pipeline_accepts_bootstrap_runtime_mode_from_load_stage_hint() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = _frame("2024-01-01T03:00:00", 2)

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta={
            "is_coldstart_run": False,
            "sampling_seconds": 3600.0,
            "baseline_runtime_mode": "BOOTSTRAP_NOT_READY",
            "enough_history_to_proceed": False,
            "baseline_ready": False,
        },
        cfg={},
        equip_id=8,
        run_id="run-bootstrap",
    )

    assert result.baseline_governance.runtime_mode == RuntimeMode.BOOTSTRAP_NOT_READY
    assert result.baseline_governance.enough_history_to_proceed is False
    assert result.baseline_governance.baseline_ready is False
    assert result.baseline_governance.readiness_state == "NOT_READY"
    assert "runtime_mode_not_ready" in result.eligibility.suppressed_reason_codes


def test_representation_pipeline_marks_trusted_window_pending_as_not_ready_for_online_scoring() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = _frame("2024-01-01T03:00:00", 2)

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta={
            "sampling_seconds": 3600.0,
            "baseline_seed_source": "trusted_window_pending",
            "baseline_seed_authoritative": False,
        },
        cfg={},
        equip_id=8,
        run_id="run-score-fallback",
    )

    assert result.baseline_governance.runtime_mode == RuntimeMode.BASELINE_FORMATION
    assert result.baseline_governance.baseline_ready is False
    assert result.baseline_governance.baseline_candidate_state == "TRUSTED_WINDOW_PENDING"
    assert result.eligibility.learn_allowed is False
    assert "baseline_formation_scoring_disabled" in result.eligibility.suppressed_reason_codes
    assert "baseline_trusted_window_pending" in result.eligibility.degraded_reason_codes


def test_representation_pipeline_handles_empty_score_window() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = pd.DataFrame(index=pd.DatetimeIndex([], name="EntryDateTime"))

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta={"sampling_seconds": 3600.0},
        cfg={},
        equip_id=9,
        run_id="run-empty-score",
    )

    assert result.score_state is None
    assert result.eligibility.score_allowed is False
    assert "no_score_rows" in result.eligibility.suppressed_reason_codes


def test_representation_pipeline_uses_shared_signal_profiler_summary() -> None:
    idx = pd.date_range("2024-01-01T00:00:00", periods=4, freq="h", name="EntryDateTime")
    train = pd.DataFrame(
        {
            "good": [1.0, 2.0, 3.0, 4.0],
            "flat": [5.0, 5.0, 5.0, 5.0],
            "nullish": [None, None, None, None],
        },
        index=idx,
    )
    score = train.copy()

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta={"sampling_seconds": 3600.0},
        cfg={},
        equip_id=11,
        run_id="run-signal-summary",
    )

    assert result.signal_summary.monitorable_signal_count == 1
    assert result.signal_summary.weak_signal_count == 1
    assert result.signal_summary.untrusted_signal_count == 1
    assert "profiled_numeric_signals" in result.signal_summary.reason_codes
    assert {profile.signal_name for profile in result.signal_profiles} == {"good", "flat", "nullish"}


def test_representation_pipeline_carries_canonical_signal_profiles() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = _frame("2024-01-01T03:00:00", 2)

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta={"sampling_seconds": 3600.0},
        cfg={},
        equip_id=12,
        run_id="run-canonical-profiles",
    )

    assert result.signal_profiles
    assert all(isinstance(profile, SignalProfile) for profile in result.signal_profiles)
    assert {profile.signal_name for profile in result.signal_profiles} == {"sensor_a", "sensor_b"}


def test_enrich_representation_shadow_recomputes_eligibility_from_context() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = pd.DataFrame(
        {
            "sensor_a": [4.0, 5.0],
            "sensor_b": [40.0, 50.0],
        },
        index=pd.date_range("2024-01-01T03:00:00", periods=2, freq="1h", name="EntryDateTime"),
    )

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta={"sampling_seconds": 3600.0},
        cfg={},
        equip_id=77,
        run_id="run-context",
    )

    updated = enrich_representation_shadow(
        result,
        cfg={},
        context=ContextAssignment(
            context_id="regime:2",
            context_label="REGIME_2",
            context_confidence=0.9,
            context_stability="STABLE",
            transition_status="STEADY",
            is_novel=False,
            is_ambiguous=False,
        ),
    )

    assert updated.context.context_label == "REGIME_2"
    assert updated.eligibility.score_allowed is True
    assert updated.eligibility.learn_allowed is False
    assert "comparability_shadow_evaluated" in updated.notes


def test_enrich_representation_shadow_blocks_schema_drift_classes() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = pd.DataFrame(
        {
            "sensor_a": [4.0, 5.0],
            "sensor_b": [40.0, 50.0],
        },
        index=pd.date_range("2024-01-01T03:00:00", periods=2, freq="1h", name="EntryDateTime"),
    )

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta={"sampling_seconds": 3600.0},
        cfg={},
        equip_id=78,
        run_id="run-schema-drift",
    )

    updated = enrich_representation_shadow(
        result,
        cfg={},
        context=ContextAssignment(
            context_id="regime:2",
            context_label="REGIME_2",
            context_confidence=0.9,
            context_stability="STABLE",
            transition_status="STEADY",
            is_novel=False,
            is_ambiguous=False,
        ),
        compatibility=CompatibilityStatus(schema_compatibility="TEMPORARY_TAG_LOSS"),
    )

    assert updated.eligibility.score_allowed is False
    assert "schema_incompatible" in updated.eligibility.suppressed_reason_codes


def test_validation_authority_policy_requires_replay_by_default() -> None:
    policy = resolve_representation_authority_policy(
        cfg={"representation": {"authority": {"mode": "validation"}}},
        args=SimpleNamespace(start_time=None, representation_authority=None),
    )

    assert policy.mode == "validation"
    assert policy.active is False
    assert policy.reason == "validation_requires_replay_or_allow_live_validation"


def test_validation_authority_policy_activates_for_historical_replay() -> None:
    policy = resolve_representation_authority_policy(
        cfg={"representation": {"authority": {"mode": "validation"}}},
        args=SimpleNamespace(start_time="2026-01-01T00:00:00", representation_authority=None),
    )

    assert policy.mode == "validation"
    assert policy.active is True
    assert policy.reason == "historical_replay_validation"


def test_apply_representation_authority_marks_result_authoritative() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = _frame("2024-01-01T03:00:00", 2)
    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta={"sampling_seconds": 3600.0},
        cfg={},
        equip_id=99,
        run_id="run-authority",
    )

    updated = apply_representation_authority(
        result,
        policy=resolve_representation_authority_policy(
            cfg={"representation": {"authority": {"mode": "validation"}}},
            args=SimpleNamespace(start_time="2026-01-01T00:00:00", representation_authority=None),
        ),
    )

    assert updated.authoritative is True
    assert updated.eligibility.authoritative is True
    assert "validation_authority_active" in updated.notes


def test_refresh_representation_runtime_authority_reapplies_policy_with_drift() -> None:
    train = _frame("2024-01-01T00:00:00", 3)
    score = pd.DataFrame(
        {
            "sensor_a": [4.0, 5.0],
            "sensor_b": [40.0, 50.0],
        },
        index=pd.date_range("2024-01-01T03:00:00", periods=2, freq="1h", name="EntryDateTime"),
    )

    result = run_representation_pipeline(
        train_df=train,
        score_df=score,
        meta={"sampling_seconds": 3600.0},
        cfg={},
        equip_id=101,
        run_id="run-refresh-runtime",
    )
    policy = resolve_representation_authority_policy(
        cfg={"representation": {"authority": {"mode": "validation"}}},
        args=SimpleNamespace(start_time="2026-01-01T00:00:00", representation_authority=None),
    )

    feature_schema_drift = SimpleNamespace(
        schema_compatibility="COMPATIBLE",
        missing_signals=(),
        new_signals=(),
        invalidated_features=(),
    )
    basis_drift = SimpleNamespace(basis_compatibility="COMPATIBLE")

    updated = refresh_representation_runtime_authority(
        result,
        cfg={},
        policy=policy,
        context=ContextAssignment(
            context_id="regime:2",
            context_label="REGIME_2",
            context_confidence=0.2,
            context_stability="UNSTABLE",
            transition_status="STEADY",
            is_novel=False,
            is_ambiguous=True,
        ),
        meta={"sampling_seconds": 3600.0},
        feature_schema_drift=feature_schema_drift,
        basis_drift=basis_drift,
    )

    assert updated.authoritative is True
    assert updated.compatibility.schema_compatibility == "COMPATIBLE"
    assert updated.compatibility.basis_compatibility == "COMPATIBLE"
    assert updated.eligibility.score_allowed is False
    assert "context_ambiguous" in updated.eligibility.suppressed_reason_codes

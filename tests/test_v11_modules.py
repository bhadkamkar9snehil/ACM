"""
Tests for V11 core modules: confidence.py, model_lifecycle.py, acm.py

Run with: pytest tests/test_v11_modules.py -v
"""
import pytest
import numpy as np
import pandas as pd
import argparse
from datetime import datetime, timedelta


class TestConfidenceModule:
    """Test core/confidence.py functionality."""
    
    def test_reliability_status_enum(self):
        """ReliabilityStatus enum has all expected values."""
        from core.confidence import ReliabilityStatus
        
        assert ReliabilityStatus.RELIABLE.value == "RELIABLE"
        assert ReliabilityStatus.NOT_RELIABLE.value == "NOT_RELIABLE"
        assert ReliabilityStatus.LEARNING.value == "LEARNING"
        assert ReliabilityStatus.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"
    
    def test_confidence_factors_geometric_mean(self):
        """ConfidenceFactors.overall() computes geometric mean."""
        from core.confidence import ConfidenceFactors
        
        # All 1.0 should give 1.0
        cf = ConfidenceFactors(1.0, 1.0, 1.0, 1.0)
        assert cf.overall() == pytest.approx(1.0)
        
        # All 0.5 should give 0.5
        cf = ConfidenceFactors(0.5, 0.5, 0.5, 0.5)
        assert cf.overall() == pytest.approx(0.5)
        
        # Mixed values
        cf = ConfidenceFactors(0.8, 0.6, 1.0, 0.9)
        assert 0.7 < cf.overall() < 0.9
    
    def test_compute_maturity_confidence(self):
        """compute_maturity_confidence returns correct values for each state."""
        from core.confidence import compute_maturity_confidence
        
        assert compute_maturity_confidence("COLDSTART") == pytest.approx(0.2)
        assert compute_maturity_confidence("LEARNING") == pytest.approx(0.5)
        assert compute_maturity_confidence("CONVERGED") == pytest.approx(1.0)
        assert compute_maturity_confidence("DEPRECATED") == pytest.approx(0.3)
    
    def test_check_rul_reliability_coldstart(self):
        """COLDSTART state returns NOT_RELIABLE."""
        from core.confidence import check_rul_reliability, ReliabilityStatus
        
        status, reason = check_rul_reliability(
            maturity_state="COLDSTART",
            training_rows=1000,
            training_days=30,
            health_history_days=7
        )
        assert status == ReliabilityStatus.NOT_RELIABLE
        assert "COLDSTART" in reason
    
    def test_check_rul_reliability_learning(self):
        """LEARNING state returns LEARNING status."""
        from core.confidence import check_rul_reliability, ReliabilityStatus
        
        status, reason = check_rul_reliability(
            maturity_state="LEARNING",
            training_rows=1000,
            training_days=30,
            health_history_days=7
        )
        assert status == ReliabilityStatus.LEARNING
        assert "LEARNING" in reason
    
    def test_check_rul_reliability_converged_sufficient_data(self):
        """CONVERGED with sufficient data returns RELIABLE."""
        from core.confidence import check_rul_reliability, ReliabilityStatus
        
        status, reason = check_rul_reliability(
            maturity_state="CONVERGED",
            training_rows=1000,
            training_days=30,
            health_history_days=7
        )
        assert status == ReliabilityStatus.RELIABLE
        assert "prerequisites met" in reason.lower()
    
    def test_check_rul_reliability_converged_insufficient_rows(self):
        """CONVERGED with insufficient rows returns INSUFFICIENT_DATA."""
        from core.confidence import check_rul_reliability, ReliabilityStatus
        
        status, reason = check_rul_reliability(
            maturity_state="CONVERGED",
            training_rows=50,  # Too few
            training_days=30,
            health_history_days=7
        )
        assert status == ReliabilityStatus.INSUFFICIENT_DATA
        assert "training data" in reason.lower()


class TestModelLifecycleModule:
    """Test core/model_lifecycle.py functionality."""
    
    def test_maturity_state_enum(self):
        """MaturityState enum has all expected values."""
        from core.model_lifecycle import MaturityState
        
        assert MaturityState.COLDSTART.value == "COLDSTART"
        assert MaturityState.LEARNING.value == "LEARNING"
        assert MaturityState.CONVERGED.value == "CONVERGED"
        assert MaturityState.DEPRECATED.value == "DEPRECATED"
    
    def test_promotion_criteria_defaults(self):
        """PromotionCriteria fallback defaults are stable when config is missing."""
        from core.model_lifecycle import PromotionCriteria
        
        criteria = PromotionCriteria()
        assert criteria.min_training_days == 7
        assert criteria.min_silhouette_score == 0.40
        assert criteria.min_dbcv_score == 0.0
        assert criteria.min_stability_ratio == 0.75
        assert criteria.min_consecutive_runs == 5
        assert criteria.min_training_rows == 400

    def test_promotion_criteria_from_config_overrides(self):
        """PromotionCriteria.from_config applies SQL-style overrides used at runtime."""
        from core.model_lifecycle import PromotionCriteria

        cfg = {
            "lifecycle": {
                "promotion": {
                    "min_training_days": 7,
                    "min_silhouette_score": 0.15,
                    "min_dbcv_score": 0.0,
                    "min_stability_ratio": 0.6,
                    "min_consecutive_runs": 3,
                    "min_training_rows": 200,
                }
            }
        }
        criteria = PromotionCriteria.from_config(cfg)
        assert criteria.min_training_days == 7
        assert criteria.min_silhouette_score == 0.15
        assert criteria.min_dbcv_score == 0.0
        assert criteria.min_stability_ratio == 0.6
        assert criteria.min_consecutive_runs == 3
        assert criteria.min_training_rows == 200
    
    def test_model_state_creation(self):
        """ModelState can be created with all required fields."""
        from core.model_lifecycle import ModelState, MaturityState
        
        state = ModelState(
            equip_id=1,
            version=1,
            maturity=MaturityState.LEARNING,
            created_at=datetime.now(),
            training_rows=500,
            training_days=10.0,
        )
        assert state.equip_id == 1
        assert state.maturity == MaturityState.LEARNING
        assert state.training_rows == 500
        # Backward-compat alias: silhouette_score property maps to regime_quality_score.
        state.silhouette_score = 0.33
        assert state.regime_quality_score == pytest.approx(0.33)
    
    def test_check_promotion_eligibility_not_learning(self):
        """Non-LEARNING state is not eligible for promotion."""
        from core.model_lifecycle import ModelState, MaturityState, check_promotion_eligibility
        
        state = ModelState(
            equip_id=1,
            version=1,
            maturity=MaturityState.CONVERGED,  # Already CONVERGED
            created_at=datetime.now() - timedelta(days=30),
            training_rows=1000,
            training_days=30.0,
        )
        eligible, reasons = check_promotion_eligibility(state)
        assert eligible is False
        assert any("LEARNING" in r for r in reasons)
    
    def test_check_promotion_eligibility_learning_meets_criteria(self):
        """LEARNING state meeting all criteria is eligible."""
        from core.model_lifecycle import ModelState, MaturityState, check_promotion_eligibility
        
        state = ModelState(
            equip_id=1,
            version=1,
            maturity=MaturityState.LEARNING,
            created_at=datetime.now() - timedelta(days=10),
            training_rows=1500,
            training_days=10.0,
            regime_quality_score=0.5,
            regime_quality_metric="silhouette",
            stability_ratio=0.9,
            consecutive_runs=5,
        )
        eligible, reasons = check_promotion_eligibility(state)
        assert eligible is True
        assert len(reasons) == 0
    
    def test_check_promotion_eligibility_learning_fails_criteria(self):
        """LEARNING state not meeting criteria is not eligible."""
        from core.model_lifecycle import ModelState, MaturityState, check_promotion_eligibility
        
        state = ModelState(
            equip_id=1,
            version=1,
            maturity=MaturityState.LEARNING,
            created_at=datetime.now() - timedelta(days=3),
            training_rows=100,  # Too few (< 400)
            training_days=3.0,  # Too short (< 7)
            regime_quality_score=0.1,  # Too low (< 0.40)
            regime_quality_metric="silhouette",
            stability_ratio=0.5,  # Too low (< 0.75)
            consecutive_runs=1,  # Too few (< 5)
        )
        eligible, reasons = check_promotion_eligibility(state)
        assert eligible is False
        assert len(reasons) >= 4  # Multiple criteria failed

    def test_check_promotion_eligibility_bic_uses_quality_flag(self):
        """BIC metric uses regime_quality_ok boolean instead of raw score threshold."""
        from core.model_lifecycle import ModelState, MaturityState, check_promotion_eligibility

        state = ModelState(
            equip_id=1,
            version=1,
            maturity=MaturityState.LEARNING,
            created_at=datetime.now() - timedelta(days=10),
            training_rows=1500,
            training_days=10.0,
            regime_quality_score=-1234.0,  # Raw value is not thresholded for BIC.
            regime_quality_metric="bic",
            regime_quality_ok=False,
            stability_ratio=0.9,
            consecutive_runs=5,
        )
        eligible, reasons = check_promotion_eligibility(state)
        assert eligible is False
        assert any("regime_quality_ok=False" in r for r in reasons)
    
    def test_promote_model(self):
        """promote_model changes LEARNING to CONVERGED."""
        from core.model_lifecycle import ModelState, MaturityState, promote_model
        
        state = ModelState(
            equip_id=1,
            version=1,
            maturity=MaturityState.LEARNING,
            created_at=datetime.now() - timedelta(days=10),
            training_rows=1000,
            training_days=10.0,
        )
        promoted = promote_model(state)
        assert promoted.maturity == MaturityState.CONVERGED
        assert promoted.promoted_at is not None
    
    def test_deprecate_model(self):
        """deprecate_model changes state to DEPRECATED."""
        from core.model_lifecycle import ModelState, MaturityState, deprecate_model
        
        state = ModelState(
            equip_id=1,
            version=1,
            maturity=MaturityState.CONVERGED,
            created_at=datetime.now() - timedelta(days=30),
            training_rows=1000,
            training_days=10.0,
        )
        deprecated = deprecate_model(state, reason="Drift detected")
        assert deprecated.maturity == MaturityState.DEPRECATED
        assert deprecated.deprecated_at is not None

    def test_resolve_maturity_for_regime_stage_overrides_converged_on_refit(self, monkeypatch):
        """Regime-stage maturity helper should downgrade CONVERGED to LEARNING when refit is requested."""
        from core import model_lifecycle as ml
        from core.model_lifecycle import ModelState, MaturityState

        state = ModelState(
            equip_id=1,
            version=3,
            maturity=MaturityState.CONVERGED,
            created_at=datetime.now(),
            training_rows=1000,
            training_days=12.0,
        )

        monkeypatch.setattr(ml, "load_model_state_safe", lambda sql_client, equip_id, logger=None: state)
        maturity = ml.resolve_maturity_for_regime_stage(
            sql_client=object(),
            equip_id=1,
            refit_requested=True,
        )
        assert maturity == "LEARNING"


class TestRegimesUnknownLabel:
    """Test UNKNOWN_REGIME_LABEL in regimes.py."""
    
    def test_unknown_regime_label_value(self):
        """UNKNOWN_REGIME_LABEL is -1."""
        from core.regimes import UNKNOWN_REGIME_LABEL
        
        assert UNKNOWN_REGIME_LABEL == -1
    
    def test_smooth_labels_preserves_unknown(self):
        """smooth_labels with preserve_unknown=True keeps UNKNOWN labels."""
        import numpy as np
        from core.regimes import smooth_labels, UNKNOWN_REGIME_LABEL
        
        # Array with some UNKNOWN labels
        labels = np.array([0, 0, UNKNOWN_REGIME_LABEL, 1, 1, UNKNOWN_REGIME_LABEL, 2, 2])
        smoothed = smooth_labels(labels, passes=1, preserve_unknown=True)
        
        # UNKNOWN positions should still be UNKNOWN
        assert smoothed[2] == UNKNOWN_REGIME_LABEL
        assert smoothed[5] == UNKNOWN_REGIME_LABEL


class TestAcmEntryPoint:
    """Test core/acm.py entry point."""
    
    def test_acm_main_importable(self):
        """core.acm.main is importable."""
        from core.acm import main
        assert callable(main)
    
    def test_legacy_detect_mode_removed(self):
        """Legacy mode marker helper should be removed."""
        from core import acm
        assert not hasattr(acm, '_detect_mode')

    def test_run_pipeline_passes_namespace_to_main(self, monkeypatch):
        """run_pipeline should invoke main with provided Namespace."""
        from core import acm

        captured = {"args": None}

        def _main(args=None):
            captured["args"] = args

        monkeypatch.setattr(acm, "main", _main)
        args = argparse.Namespace(equip="FD_FAN")
        rc = acm.run_pipeline(args)

        assert rc == 0
        assert captured["args"] is args

    def test_representation_blocks_zero_day_scoring_on_structural_blockers(self):
        """Early zero-day skip should trigger only on authoritative structural blockers."""
        from core import acm
        from core.representation_contracts import EligibilityDecision

        representation_result = type(
            "RepresentationResult",
            (),
            {
                "authoritative": True,
                "eligibility": EligibilityDecision(
                    authoritative=True,
                    score_allowed=False,
                    learn_allowed=False,
                    suppressed_reason_codes=("basis_incompatible", "context_unknown"),
                ),
            },
        )()

        assert acm._representation_blocks_zero_day_scoring(representation_result) is True

    def test_representation_blocks_zero_day_scoring_ignores_context_only_precheck(self):
        """Context-only early suppression should not short-circuit zero-day scoring yet."""
        from core import acm
        from core.representation_contracts import EligibilityDecision

        representation_result = type(
            "RepresentationResult",
            (),
            {
                "authoritative": True,
                "eligibility": EligibilityDecision(
                    authoritative=True,
                    score_allowed=False,
                    learn_allowed=False,
                    suppressed_reason_codes=("context_unknown",),
                ),
            },
        )()

        assert acm._representation_blocks_zero_day_scoring(representation_result) is False

    def test_representation_learning_blocked_helper(self):
        """Learning-block helper should reflect authoritative learn_allowed=False."""
        from core import acm
        from core.representation_contracts import EligibilityDecision

        blocked = type(
            "RepresentationResult",
            (),
            {
                "authoritative": True,
                "eligibility": EligibilityDecision(
                    authoritative=True,
                    score_allowed=True,
                    learn_allowed=False,
                ),
            },
        )()
        allowed = type(
            "RepresentationResult",
            (),
            {
                "authoritative": True,
                "eligibility": EligibilityDecision(
                    authoritative=True,
                    score_allowed=True,
                    learn_allowed=True,
                ),
            },
        )()

        assert acm._representation_learning_blocked(blocked) is True
        assert acm._representation_learning_blocked(allowed) is False

    def test_initialize_zero_day_runtime_loads_state_lazily(self, monkeypatch):
        """Lazy zero-day initializer should load persisted EWM and proxy state only on demand."""
        from core import acm

        calls = []

        class _FakeEWM:
            def __init__(self, equip_id, alpha_fast, alpha_slow, anomaly_z):
                calls.append(("ewm.init", equip_id, alpha_fast, alpha_slow, anomaly_z))

            def load_from_sql(self, sql_client):
                calls.append(("ewm.load", sql_client))

        class _FakeBinner:
            def __init__(self, n_bins, min_rows_for_assignment, alpha, history_limit):
                calls.append(("binner.init", n_bins, min_rows_for_assignment, alpha, history_limit))

            def load_from_sql(self, sql_client, equip_id):
                calls.append(("binner.load", sql_client, equip_id))

        monkeypatch.setattr(acm, "EWMBaselineManager", _FakeEWM)
        monkeypatch.setattr(acm, "OnlinePCABinner", _FakeBinner)

        ewm_manager, binner = acm._initialize_zero_day_runtime(
            ewm_cfg={
                "alpha_fast": 0.1,
                "alpha_slow": 0.01,
                "anomaly_z": 4.0,
                "n_bins": 4,
                "min_rows_for_assignment": 7,
                "proxy_alpha": 0.2,
                "proxy_history_limit": 128,
            },
            sql_client="sql-client",
            equip_id=5010,
            enable_binner=True,
        )

        assert ewm_manager is not None
        assert binner is not None
        assert ("ewm.load", "sql-client") in calls
        assert ("binner.load", "sql-client", 5010) in calls


class TestRefactorHelpers:
    """Smoke and behavior checks for newly extracted helper functions."""

    def test_maybe_update_adaptive_thresholds_skips_without_fused(self):
        """Threshold update helper should no-op when train_frame has no fused column."""
        from core.adaptive_thresholds import maybe_update_adaptive_thresholds

        train_frame = pd.DataFrame({"x": [1.0, 2.0]})
        train_data = pd.DataFrame({"x": [1.0, 2.0]})
        cfg = {"runtime": {"run_count": 1}}

        class _Logger:
            def info(self, *_a, **_k):
                return None

        updated = maybe_update_adaptive_thresholds(
            train_frame=train_frame,
            train_data=train_data,
            cfg=cfg,
            equip_id=1,
            output_manager=None,
            coldstart_complete=False,
            regime_quality_ok=False,
            logger=_Logger(),
        )
        assert updated is False

    def test_build_threshold_calculator_from_config_is_verdict_aware(self):
        """Adaptive threshold calculator should only filter downstream when baseline was suspect."""
        from core.adaptive_thresholds import build_threshold_calculator_from_config

        cfg = {
            "thresholds": {
                "adaptive": {"min_samples": 75},
                "contamination_filter": {
                    "enabled": True,
                    "method": "hybrid",
                    "z_threshold": 5.0,
                },
            }
        }

        calc_clean = build_threshold_calculator_from_config(cfg, baseline_contamination_verdict="ok")
        calc_suspect = build_threshold_calculator_from_config(cfg, baseline_contamination_verdict="suspect")

        assert calc_clean.min_samples == 75
        assert calc_clean.contamination_filter_enabled is False
        assert calc_suspect.contamination_filter_enabled is True
        assert calc_suspect.contamination_filter_method == "hybrid"
        assert calc_suspect.contamination_filter_z_threshold == pytest.approx(5.0)

    def test_load_and_validate_data_stage_returns_noop_when_coldstart_incomplete(self, monkeypatch):
        """Data load stage helper should finalize NOOP and stop pipeline when coldstart is incomplete."""
        from core import smart_coldstart as sc

        class _ColdstartManager:
            def __init__(self, **kwargs):
                pass

            def load_with_retry(self, **kwargs):
                return None, None, {"noop_reason": "SCORING_NO_DATA"}, False

        monkeypatch.setattr(sc, "SmartColdstart", _ColdstartManager)
        finalize_calls = []
        log_calls = []

        def _finalize_noop(**kwargs):
            finalize_calls.append(kwargs)

        class _Logger:
            def info(self, message, **kwargs):
                log_calls.append((message, kwargs))

        out = sc.load_and_validate_data_stage(
            sql_client=object(),
            equip="FD_FAN",
            equip_id=1,
            cfg={},
            args=type("Args", (), {"start_time": None})(),
            output_manager=object(),
            win_start=None,
            win_end=None,
            ensure_local_index_fn=lambda df: df,
            deduplicate_index_fn=lambda df, kind, equip: (df, 0),
            validate_data_contract_fn=lambda **kwargs: None,
            finalize_noop_run_fn=_finalize_noop,
            record_coldstart_fn=lambda equip: None,
            refit_requested=False,
            run_id="r1",
            logger=_Logger(),
        )

        assert out.should_continue is False
        assert out.coldstart_complete is False
        assert len(finalize_calls) == 1
        assert finalize_calls[0]["zero_day_status"].status == "inactive_no_data"
        assert finalize_calls[0]["zero_day_status"].scoring_active is False
        assert len(log_calls) == 1
        assert "zero-day scoring inactive on this run" in log_calls[0][0]
        assert log_calls[0][1]["component"] == "COLDSTART"
        assert log_calls[0][1]["noop_reason"] == "SCORING_NO_DATA"
        assert log_calls[0][1]["zero_day_scoring_active"] is False

    def test_build_noop_observability_distinguishes_coldstart_deferred(self):
        """Coldstart defer should explicitly say scoring is inactive, not merely delayed."""
        from core import smart_coldstart as sc

        message, fields = sc.build_noop_observability("COLDSTART_DEFERRED")

        assert "coldstart deferred" in message.lower()
        assert "zero-day scoring is inactive on this run" in message.lower()
        assert fields["noop_reason"] == "COLDSTART_DEFERRED"
        assert fields["zero_day_scoring_active"] is False
        assert fields["legacy_fit_ready"] is False

    def test_zero_day_status_from_noop_reason_maps_known_reasons(self):
        """NOOP reasons should map to stable persisted day-0 run statuses."""
        from core.run_metadata_writer import zero_day_status_from_noop_reason

        no_data = zero_day_status_from_noop_reason("SCORING_NO_DATA")
        coldstart = zero_day_status_from_noop_reason("COLDSTART_DEFERRED")

        assert no_data.status == "inactive_no_data"
        assert no_data.scoring_active is False
        assert coldstart.status == "inactive_coldstart_deferred"
        assert coldstart.scoring_active is False

    def test_load_and_validate_data_stage_success_path_sets_dedup_counts(self, monkeypatch):
        """Data load stage helper should normalize, deduplicate, validate, and continue when data is ready."""
        from core import smart_coldstart as sc

        class _Meta:
            def __init__(self):
                self.timestamp_col = "Timestamp"
                self.cadence_ok = True
                self.kept_cols = ["sensor_a"]
                self.dropped_cols = []
                self.tz_stripped = 0
                self.future_rows_dropped = 0
                self.dup_timestamps_removed = 0

        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        train = pd.DataFrame({"sensor_a": [1.0, 2.0]}, index=idx)
        score = pd.DataFrame({"sensor_a": [1.1, 2.1]}, index=idx)
        meta = _Meta()

        class _ColdstartManager:
            def __init__(self, **kwargs):
                pass

            def load_with_retry(self, **kwargs):
                return train.copy(), score.copy(), meta, True

        monkeypatch.setattr(sc, "SmartColdstart", _ColdstartManager)
        validate_calls = []
        coldstart_calls = []

        def _validate_contract(**kwargs):
            validate_calls.append(kwargs)

        out = sc.load_and_validate_data_stage(
            sql_client=object(),
            equip="FD_FAN",
            equip_id=1,
            cfg={},
            args=type("Args", (), {"start_time": None})(),
            output_manager=object(),
            win_start=None,
            win_end=None,
            ensure_local_index_fn=lambda df: df,
            deduplicate_index_fn=lambda df, kind, equip: (df, 1 if kind == "TRAIN" else 2),
            validate_data_contract_fn=_validate_contract,
            finalize_noop_run_fn=lambda **kwargs: None,
            record_coldstart_fn=lambda equip: coldstart_calls.append(equip),
            refit_requested=False,
            run_id="r1",
        )

        assert out.should_continue is True
        assert out.train is not None
        assert out.score is not None
        assert out.meta.dup_timestamps_removed == 3
        assert len(validate_calls) == 1
        assert coldstart_calls == ["FD_FAN"]

    def test_write_drift_controller_state_no_output_manager(self):
        """Drift writer should safely no-op when output manager is missing."""
        from core.drift import write_drift_controller_state

        frame = pd.DataFrame({"drift_z": [0.1], "drift_mode": ["FAULT"]})
        rows = write_drift_controller_state(
            output_manager=None,
            frame=frame,
            cfg={},
            score_out={},
        )
        assert rows == 0

    def test_start_run_span_returns_none_without_tracer(self):
        """Run span helper should no-op when tracer is unavailable."""
        from core.observability import start_run_span

        span_ctx, root_span = start_run_span(
            tracer=None,
            equip="FD_FAN",
            equip_id=1,
            run_id="r1",
            run_count=1,
        )
        assert span_ctx is None
        assert root_span is None

    def test_start_run_span_builds_root_span_with_expected_attributes(self):
        """Run span helper should create span context with ACM run attributes."""
        from core.observability import start_run_span

        captured = {}

        class _SpanCtx:
            def __enter__(self):
                return {"root": "span"}

            def __exit__(self, exc_type, exc, tb):
                return False

        class _Tracer:
            def start_as_current_span(self, name, attributes=None):
                captured["name"] = name
                captured["attributes"] = attributes
                return _SpanCtx()

        span_ctx, root_span = start_run_span(
            tracer=_Tracer(),
            equip="FD_FAN",
            equip_id=1,
            run_id="r1",
            run_count=7,
        )

        assert span_ctx is not None
        assert root_span == {"root": "span"}
        assert captured["name"] == "acm.run:FD_FAN"
        assert captured["attributes"]["acm.run_id"] == "r1"
        assert captured["attributes"]["acm.equip_id"] == 1

    def test_init_run_observability_invokes_init_and_profiling(self, monkeypatch):
        """Observability startup helper should initialize and start profiling."""
        from core import observability as obs

        calls = {"init": 0, "profile": 0}

        def _init(**kwargs):
            calls["init"] += 1

        def _start_profiling():
            calls["profile"] += 1

        monkeypatch.setattr(obs, "init", _init)
        monkeypatch.setattr(obs, "start_profiling", _start_profiling)

        obs.init_run_observability(equip="FD_FAN", equip_id=1, logger=None)

        assert calls["init"] == 1
        assert calls["profile"] == 1

    def test_init_run_observability_warns_when_init_fails(self, monkeypatch):
        """Observability startup helper should warn and continue on init errors."""
        from core import observability as obs

        warns = []

        def _init(**kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(obs, "init", _init)

        class _Logger:
            def warn(self, msg, **kwargs):
                warns.append((msg, kwargs))

        obs.init_run_observability(equip="FD_FAN", equip_id=1, logger=_Logger())

        assert len(warns) == 1
        assert "Observability init failed" in warns[0][0]

    def test_connect_acm_sql_failfast_returns_sql_client(self, monkeypatch):
        """SQL fail-fast helper should return connected client on success."""
        from core import sql_client as sql

        class _Logger:
            def info(self, *args, **kwargs):
                pass

            def ok(self, *args, **kwargs):
                pass

            def error(self, *args, **kwargs):
                pass

        expected = object()
        monkeypatch.setattr(sql, "connect_acm_sql", lambda cfg, logger=None: expected)

        out = sql.connect_acm_sql_failfast(cfg={}, logger=_Logger())
        assert out is expected

    def test_connect_acm_sql_failfast_raises_system_exit_on_failure(self, monkeypatch):
        """SQL fail-fast helper should exit with code 1 when SQL connection fails."""
        from core import sql_client as sql

        errors = []

        class _Logger:
            def info(self, *args, **kwargs):
                pass

            def ok(self, *args, **kwargs):
                pass

            def error(self, *args, **kwargs):
                errors.append((args, kwargs))

        def _fail(cfg, logger=None):
            raise RuntimeError("db down")

        monkeypatch.setattr(sql, "connect_acm_sql", _fail)

        with pytest.raises(SystemExit) as ex:
            sql.connect_acm_sql_failfast(cfg={}, logger=_Logger())
        assert ex.value.code == 1
        assert len(errors) >= 1

    def test_bootstrap_acm_run_state_uses_default_deadlock_retry_when_omitted(self, monkeypatch):
        """Run bootstrap should pass module deadlock retry when no override is provided."""
        from core import sql_client as sql
        from utils.config_dict import ConfigDict

        captured = {}

        monkeypatch.setattr(
            sql,
            "load_config_required_from_sql",
            lambda sql_client, equipment_name, logger=None: ConfigDict({}, mode="sql", equip_id=10),
        )
        monkeypatch.setattr(sql, "resolve_equipment_id_required", lambda equip, sql_client: 10)
        monkeypatch.setattr(sql, "get_acm_run_count", lambda sql_client, equip_id: 3)

        def _start_acm_run(cli, cfg, equip_code, deadlock_retry_func=None, logger=None):
            captured["deadlock_retry_func"] = deadlock_retry_func
            return "run-1", pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02"), 10

        monkeypatch.setattr(sql, "start_acm_run", _start_acm_run)
        monkeypatch.setattr(
            sql,
            "apply_cli_window_overrides",
            lambda win_start, win_end, start_time_arg=None, end_time_arg=None, logger=None: (win_start, win_end, []),
        )

        args = type("Args", (), {"start_time": None, "end_time": None})()
        out = sql.bootstrap_acm_run_state(sql_client=object(), equip="FD_FAN", args=args, logger=None)

        assert out.equip_id == 10
        assert captured["deadlock_retry_func"] is sql.execute_with_deadlock_retry

    def test_cfg_get_reads_nested_value_and_casts_scalar_type(self):
        """Shared config getter should read nested paths and cast scalar defaults consistently."""
        from utils.config_dict import cfg_get

        cfg = {
            "runtime": {"future_grace_minutes": "7"},
            "models": {"enabled": "true"},
        }

        assert cfg_get(cfg, "runtime.future_grace_minutes", 0) == 7
        assert cfg_get(cfg, "runtime.missing", 5) == 5
        assert cfg_get(cfg, "models.enabled", False) is True

    def test_future_cutoff_ts_applies_non_negative_grace_minutes(self):
        """Shared future cutoff helper should clamp invalid/negative values and return Timestamp."""
        from utils.config_dict import future_cutoff_ts

        t0 = future_cutoff_ts({"runtime": {"future_grace_minutes": -10}})
        t1 = future_cutoff_ts({"runtime": {"future_grace_minutes": 0}})
        t2 = future_cutoff_ts({"runtime": {"future_grace_minutes": 5}})

        assert isinstance(t0, pd.Timestamp)
        assert isinstance(t1, pd.Timestamp)
        assert isinstance(t2, pd.Timestamp)
        assert t2 >= t1
        assert t1 >= t0 - pd.Timedelta(seconds=1)

    def test_run_drift_pipeline_smoke(self):
        """Drift pipeline wrapper should return frame and score_out keys."""
        from core.drift import run_drift_pipeline

        frame = pd.DataFrame({"fused": [0.1, 0.2, 0.3], "drift_z": [0.0, 0.0, 0.0]})
        score_data = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
        score_out = {"frame": frame.copy()}
        out = run_drift_pipeline(
            score_data=score_data,
            frame=frame,
            score_out=score_out,
            cfg={"drift": {}},
            regime_quality_ok=False,
            equip="FD_FAN",
            sql_client=None,
            equip_id=1,
            output_manager=None,
        )
        assert "frame" in out
        assert "score_out" in out
        assert "drift_controller_rows" in out
        assert isinstance(out["frame"], pd.DataFrame)

    def test_detect_and_adjust_safe_returns_inputs_on_error(self, monkeypatch):
        """Seasonality safe wrapper should return original data on internal errors."""
        from core import seasonality

        def _boom(*args, **kwargs):
            raise RuntimeError("seasonality fail")

        monkeypatch.setattr(seasonality, "detect_and_adjust", _boom)

        class _Logger:
            def info(self, *args, **kwargs):
                pass

            def warn(self, *args, **kwargs):
                pass

        idx = pd.date_range("2026-01-01", periods=3, freq="h")
        train = pd.DataFrame({"sensor": [1.0, 2.0, 3.0]}, index=idx)
        score = pd.DataFrame({"sensor": [1.5, 2.5]}, index=idx[:2])
        out_train, out_score, patterns, adjusted = seasonality.detect_and_adjust_safe(
            train=train,
            score=score,
            cfg={},
            logger=_Logger(),
            equip="FD_FAN",
        )
        assert out_train.equals(train)
        assert out_score.equals(score)
        assert patterns == {}
        assert adjusted is False

    def test_evaluate_and_maybe_refit_cached_models_no_cache(self):
        """Auto-retrain helper should return no-op when cached models are absent."""
        from core.model_evaluation import evaluate_and_maybe_refit_cached_models

        out = evaluate_and_maybe_refit_cached_models(
            cfg={},
            cached_models=None,
            cached_manifest=None,
            detectors_just_trained=False,
            score_out={},
            regime_quality_ok=True,
            current_model_maturity="LEARNING",
            boolean_only_metrics=[],
            equip="FD_FAN",
            logger=type("L", (), {"warn": lambda *a, **k: None})(),
            record_model_refit_fn=lambda *a, **k: None,
            fit_all_detectors_fn=lambda **k: {},
            train=pd.DataFrame({"a": [1.0, 2.0]}),
            det_flags={},
            output_manager=None,
            sql_client=None,
            run_id=None,
            equip_id=1,
            regime_model=None,
        )
        assert out.force_retrain is False
        assert out.cached_models is None
        assert out.retrain_result is None

    def test_run_auto_retrain_stage_applies_retrain_outputs(self, monkeypatch):
        """Auto-retrain stage helper should apply detector outputs from retrain payload."""
        from core import model_evaluation

        retrained_detector = object()

        def _eval_and_refit(**kwargs):
            return model_evaluation.AutoRetrainDecision(
                force_retrain=True,
                cached_models=None,
                regime_model=None,
                retrain_result={
                    "ar1_detector": retrained_detector,
                    "pca_detector": retrained_detector,
                    "iforest_detector": retrained_detector,
                    "gmm_detector": None,
                    "omr_detector": None,
                    "pca_train_spe": np.array([0.1, 0.2]),
                    "pca_train_t2": np.array([0.2, 0.3]),
                },
            )

        monkeypatch.setattr(model_evaluation, "evaluate_and_maybe_refit_cached_models", _eval_and_refit)
        out = model_evaluation.run_auto_retrain_stage(
            cfg={},
            cached_models={"k": "v"},
            cached_manifest={},
            detectors_just_trained=False,
            score_out={},
            regime_quality_ok=True,
            current_model_maturity="LEARNING",
            boolean_only_metrics=[],
            equip="FD_FAN",
            logger=type("L", (), {"warn": lambda *a, **k: None})(),
            record_model_refit_fn=lambda *a, **k: None,
            fit_all_detectors_fn=lambda **k: {},
            train=pd.DataFrame({"a": [1.0, 2.0]}),
            det_flags={},
            output_manager=None,
            sql_client=None,
            run_id="r1",
            equip_id=1,
            regime_model=None,
            detectors={
                "ar1_detector": None,
                "pca_detector": None,
                "iforest_detector": None,
                "gmm_detector": None,
                "omr_detector": None,
                "pca_train_spe": None,
                "pca_train_t2": None,
            },
        )
        assert out.force_retrain is True
        assert out.cached_models is None
        assert out.detectors["ar1_detector"] is retrained_detector
        assert out.detectors["pca_detector"] is retrained_detector
        assert out.detectors["iforest_detector"] is retrained_detector
        assert isinstance(out.detectors["pca_train_spe"], np.ndarray)
        assert isinstance(out.detectors["pca_train_t2"], np.ndarray)

    def test_run_auto_retrain_stage_honors_force_retrain_requested(self, monkeypatch):
        """Auto-retrain stage should fit detectors immediately when CLI force retrain is requested."""
        from core import model_evaluation

        def _should_not_run(**kwargs):
            raise AssertionError("quality trigger evaluation should be bypassed when force_retrain_requested=True")

        monkeypatch.setattr(model_evaluation, "evaluate_and_maybe_refit_cached_models", _should_not_run)

        retrained_detector = object()
        record_calls = []

        def _fit_all_detectors_fn(**kwargs):
            return {
                "ar1_detector": retrained_detector,
                "pca_detector": retrained_detector,
                "iforest_detector": retrained_detector,
                "gmm_detector": None,
                "omr_detector": None,
                "pca_train_spe": np.array([0.5]),
                "pca_train_t2": np.array([0.6]),
            }

        out = model_evaluation.run_auto_retrain_stage(
            cfg={},
            cached_models={"k": "v"},
            cached_manifest={},
            detectors_just_trained=False,
            score_out={},
            regime_quality_ok=True,
            current_model_maturity="LEARNING",
            boolean_only_metrics=[],
            equip="FD_FAN",
            logger=type("L", (), {"warn": lambda *a, **k: None})(),
            record_model_refit_fn=lambda *a, **k: record_calls.append((a, k)),
            fit_all_detectors_fn=_fit_all_detectors_fn,
            train=pd.DataFrame({"a": [1.0, 2.0]}),
            det_flags={"ar1_enabled": True, "pca_enabled": True, "iforest_enabled": True, "gmm_enabled": False, "omr_enabled": False},
            output_manager=None,
            sql_client=None,
            run_id="r1",
            equip_id=1,
            regime_model=None,
            detectors={
                "ar1_detector": None,
                "pca_detector": None,
                "iforest_detector": None,
                "gmm_detector": None,
                "omr_detector": None,
                "pca_train_spe": None,
                "pca_train_t2": None,
            },
            force_retrain_requested=True,
        )

        assert out.force_retrain is True
        assert out.cached_models is None
        assert out.detectors["ar1_detector"] is retrained_detector
        assert out.detectors["pca_detector"] is retrained_detector
        assert out.detectors["iforest_detector"] is retrained_detector
        assert len(record_calls) == 1

    def test_run_model_persistence_and_lifecycle_stage_trained_path(self):
        """Persistence stage helper should save models and update lifecycle when trained."""
        from core.model_persistence import run_model_persistence_and_lifecycle_stage

        captured = {"saved": False, "updated": False, "loaded": False}

        def _save_trained_models_fn(**kwargs):
            captured["saved"] = True
            return 7

        def _update_and_persist_model_lifecycle_fn(**kwargs):
            captured["updated"] = True
            return {"state": "updated"}

        def _load_model_state_safe_fn(**kwargs):
            captured["loaded"] = True
            return {"state": "loaded"}

        out = run_model_persistence_and_lifecycle_stage(
            cached_models=None,
            detector_cache=None,
            force_retrain=False,
            equip="FD_FAN",
            sql_client=object(),
            equip_id=1,
            cfg={},
            train=pd.DataFrame({"a": [1.0, 2.0]}),
            ar1_detector=object(),
            pca_detector=object(),
            iforest_detector=object(),
            gmm_detector=None,
            omr_detector=None,
            regime_model=None,
            col_meds={"a": 1.5},
            regime_quality_ok=True,
            timing_sections={},
            run_id="r1",
            model_state=None,
            output_manager=object(),
            regime_state_version=1,
            score_out={},
            update_and_persist_model_lifecycle_fn=_update_and_persist_model_lifecycle_fn,
            load_model_state_safe_fn=_load_model_state_safe_fn,
            save_trained_models_fn=_save_trained_models_fn,
            logger=type("L", (), {"warn": lambda *a, **k: None})(),
        )
        assert out.detectors_fitted_this_run is True
        assert out.models_were_trained is True
        assert out.saved_model_version == 7
        assert out.model_state == {"state": "updated"}
        assert captured["saved"] is True
        assert captured["updated"] is True
        assert captured["loaded"] is False

    def test_run_model_persistence_and_lifecycle_stage_scoring_only_loads_state(self):
        """Persistence stage helper should load lifecycle state when no training happened."""
        from core.model_persistence import run_model_persistence_and_lifecycle_stage

        captured = {"loaded": False}

        def _update_and_persist_model_lifecycle_fn(**kwargs):
            raise AssertionError("lifecycle update should not run when models were not trained")

        def _load_model_state_safe_fn(**kwargs):
            captured["loaded"] = True
            return {"state": "loaded"}

        out = run_model_persistence_and_lifecycle_stage(
            cached_models={"exists": True},
            detector_cache=None,
            force_retrain=False,
            equip="FD_FAN",
            sql_client=object(),
            equip_id=1,
            cfg={},
            train=pd.DataFrame({"a": [1.0, 2.0]}),
            ar1_detector=None,
            pca_detector=None,
            iforest_detector=None,
            gmm_detector=None,
            omr_detector=None,
            regime_model=None,
            col_meds=None,
            regime_quality_ok=True,
            timing_sections={},
            run_id="r1",
            model_state=None,
            output_manager=object(),
            regime_state_version=1,
            score_out={},
            update_and_persist_model_lifecycle_fn=_update_and_persist_model_lifecycle_fn,
            load_model_state_safe_fn=_load_model_state_safe_fn,
            logger=type("L", (), {"warn": lambda *a, **k: None})(),
        )
        assert out.detectors_fitted_this_run is False
        assert out.models_were_trained is False
        assert out.saved_model_version is None
        assert out.model_state == {"state": "loaded"}
        assert captured["loaded"] is True

    def test_run_model_adaptation_and_persistence_stage_orchestrates_two_stages(self):
        """Combined model stage helper should run auto-retrain stage then persistence stage."""
        from core.model_persistence import run_model_adaptation_and_persistence_stage, ModelPersistenceStageResult

        sections = []
        captured = {"force_retrain_requested": None}
        class _Section:
            def __init__(self, name):
                self.name = name
            def __enter__(self):
                sections.append(self.name)
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        def _section_fn(name):
            return _Section(name)

        retrain_detectors = {
            "ar1_detector": object(),
            "pca_detector": object(),
            "iforest_detector": object(),
            "gmm_detector": None,
            "omr_detector": None,
            "pca_train_spe": np.array([0.1]),
            "pca_train_t2": np.array([0.2]),
        }

        def _run_auto_retrain_stage_fn(**kwargs):
            captured["force_retrain_requested"] = kwargs.get("force_retrain_requested")
            return type(
                "AutoRetrainStageResult",
                (),
                {
                    "force_retrain": True,
                    "cached_models": None,
                    "regime_model": {"k": "v"},
                    "detectors": retrain_detectors,
                },
            )()

        def _run_model_persistence_and_lifecycle_stage_fn(**kwargs):
            return ModelPersistenceStageResult(
                detectors_fitted_this_run=True,
                models_were_trained=True,
                saved_model_version=12,
                model_state={"state": "ok"},
            )

        out = run_model_adaptation_and_persistence_stage(
            section_fn=_section_fn,
            run_auto_retrain_stage_fn=_run_auto_retrain_stage_fn,
            run_model_persistence_and_lifecycle_stage_fn=_run_model_persistence_and_lifecycle_stage_fn,
            cfg={},
            cached_models={"cached": True},
            cached_manifest={},
            detectors_just_trained=False,
            score_out={},
            regime_quality_ok=True,
            current_model_maturity="LEARNING",
            boolean_only_metrics=[],
            equip="FD_FAN",
            logger=type("L", (), {"warn": lambda *a, **k: None})(),
            record_model_refit_fn=lambda *a, **k: None,
            fit_all_detectors_fn=lambda **k: {},
            train=pd.DataFrame({"a": [1.0, 2.0]}),
            det_flags={},
            output_manager=object(),
            sql_client=object(),
            run_id="r1",
            equip_id=1,
            regime_model=None,
            detectors={
                "ar1_detector": None,
                "pca_detector": None,
                "iforest_detector": None,
                "gmm_detector": None,
                "omr_detector": None,
                "pca_train_spe": None,
                "pca_train_t2": None,
            },
            detector_cache=None,
            col_meds=None,
            timing_sections={},
            model_state=None,
            regime_state_version=1,
            update_and_persist_model_lifecycle_fn=lambda **k: None,
            load_model_state_safe_fn=lambda **k: None,
        )

        assert out.force_retrain is True
        assert out.saved_model_version == 12
        assert out.model_state == {"state": "ok"}
        assert out.regime_model == {"k": "v"}
        assert isinstance(out.detectors["pca_train_spe"], np.ndarray)
        assert sections == ["models.auto_retrain", "models.persistence.save"]
        assert captured["force_retrain_requested"] is False

    def test_load_manifest_protected_columns_returns_none_when_cache_skipped(self):
        """Manifest protection helper should no-op when cache is disabled or run is coldstart."""
        from core.model_persistence import load_manifest_protected_columns

        out_disabled = load_manifest_protected_columns(
            sql_client=object(),
            equip="FD_FAN",
            equip_id=1,
            cfg={"models": {"use_cache": False}},
            is_coldstart_run=False,
        )
        out_coldstart = load_manifest_protected_columns(
            sql_client=object(),
            equip="FD_FAN",
            equip_id=1,
            cfg={"models": {"use_cache": True}},
            is_coldstart_run=True,
        )

        assert out_disabled is None
        assert out_coldstart is None

    def test_load_manifest_protected_columns_returns_sensors(self, monkeypatch):
        """Manifest protection helper should return train_sensors from manifest-only load."""
        from core import model_persistence

        class _Manager:
            def __init__(self, equip, sql_client, equip_id):
                self.equip = equip
                self.sql_client = sql_client
                self.equip_id = equip_id

            def load_manifest_only(self):
                return {"train_sensors": ["a", "b", "c"]}

        monkeypatch.setattr(model_persistence, "ModelVersionManager", _Manager)
        out = model_persistence.load_manifest_protected_columns(
            sql_client=object(),
            equip="FD_FAN",
            equip_id=1,
            cfg={"models": {"use_cache": True}},
            is_coldstart_run=False,
        )
        assert out == ["a", "b", "c"]

    def test_initialize_detectors_for_run_trains_when_required_detectors_missing(self):
        """Detector init helper should fit detectors when enabled models are missing."""
        from core.detector_orchestrator import _initialize_detectors_for_run

        train = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [2.0, 3.0, 4.0]})
        score = pd.DataFrame({"a": [1.5, 2.5], "b": [2.5, 3.5]})

        def _load_and_rebuild_detectors_fn(**kwargs):
            raise AssertionError("cache load should not be called for coldstart batch")

        def _restore_detectors_from_runtime_cache_fn(**kwargs):
            return {}

        def _load_quality_regime_state_if_needed_fn(**kwargs):
            return None, 0, False

        fitted = object()

        def _fit_all_detectors_fn(**kwargs):
            return {
                "ar1_detector": fitted,
                "pca_detector": fitted,
                "iforest_detector": fitted,
                "gmm_detector": None,
                "omr_detector": None,
                "pca_train_spe": np.array([0.1, 0.2, 0.3]),
                "pca_train_t2": np.array([0.2, 0.3, 0.4]),
            }

        def _reconcile_detector_flags_fn(**kwargs):
            return {
                "ar1_enabled": True,
                "pca_enabled": True,
                "iforest_enabled": True,
                "gmm_enabled": False,
                "omr_enabled": False,
            }

        class _Logger:
            def info(self, *args, **kwargs):
                pass

            def warn(self, *args, **kwargs):
                pass

            def error(self, *args, **kwargs):
                pass

        out = _initialize_detectors_for_run(
            train=train,
            score=score,
            cfg={
                "models": {"use_cache": True},
                "fusion": {"weights": {"ar1_z": 1.0, "pca_spe_z": 1.0, "iforest_z": 1.0}},
            },
            meta={"is_coldstart_run": True},
            detector_cache=None,
            output_manager=None,
            sql_client=None,
            run_id="r1",
            equip_id=1,
            equip="FD_FAN",
            load_and_rebuild_detectors_fn=_load_and_rebuild_detectors_fn,
            restore_detectors_from_runtime_cache_fn=_restore_detectors_from_runtime_cache_fn,
            load_quality_regime_state_if_needed_fn=_load_quality_regime_state_if_needed_fn,
            fit_all_detectors_fn=_fit_all_detectors_fn,
            reconcile_detector_flags_fn=_reconcile_detector_flags_fn,
            logger=_Logger(),
        )

        assert out.detectors_just_trained is True
        assert out.use_cache is False
        assert out.ar1_detector is fitted
        assert out.pca_detector is fitted
        assert out.iforest_detector is fitted
        assert out.gmm_detector is None
        assert out.omr_detector is None
        assert isinstance(out.pca_train_spe, np.ndarray)
        assert isinstance(out.pca_train_t2, np.ndarray)

    def test_initialize_detectors_for_run_uses_sql_cache_without_refit(self):
        """Detector init helper should reuse cached detectors when cache payload is valid."""
        from core.detector_orchestrator import _initialize_detectors_for_run

        train = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        score = pd.DataFrame({"a": [1.5, 2.5]})
        cached_detector = object()

        def _load_and_rebuild_detectors_fn(**kwargs):
            return {
                "train": kwargs["train"],
                "score": kwargs["score"],
                "cached_models": {"pca_model": "ok"},
                "cached_manifest": {"train_sensors": ["a"]},
                "cached_calibration_params": {"ar1_z": {"med": 0.0}},
                "ar1_detector": cached_detector,
                "pca_detector": cached_detector,
                "iforest_detector": cached_detector,
                "gmm_detector": None,
                "omr_detector": None,
                "regime_model": None,
                "col_meds": {"a": 1.5},
            }

        def _restore_detectors_from_runtime_cache_fn(**kwargs):
            return {}

        def _load_quality_regime_state_if_needed_fn(**kwargs):
            return None, 0, False

        def _fit_all_detectors_fn(**kwargs):
            raise AssertionError("fit should not be called when cache has required detectors")

        def _reconcile_detector_flags_fn(**kwargs):
            return {
                "ar1_enabled": True,
                "pca_enabled": True,
                "iforest_enabled": True,
                "gmm_enabled": False,
                "omr_enabled": False,
            }

        class _Logger:
            def info(self, *args, **kwargs):
                pass

            def warn(self, *args, **kwargs):
                pass

            def error(self, *args, **kwargs):
                pass

        out = _initialize_detectors_for_run(
            train=train,
            score=score,
            cfg={
                "models": {"use_cache": True},
                "fusion": {"weights": {"ar1_z": 1.0, "pca_spe_z": 1.0, "iforest_z": 1.0}},
            },
            meta={"is_coldstart_run": False},
            detector_cache=None,
            output_manager=None,
            sql_client=object(),
            run_id="r1",
            equip_id=1,
            equip="FD_FAN",
            load_and_rebuild_detectors_fn=_load_and_rebuild_detectors_fn,
            restore_detectors_from_runtime_cache_fn=_restore_detectors_from_runtime_cache_fn,
            load_quality_regime_state_if_needed_fn=_load_quality_regime_state_if_needed_fn,
            fit_all_detectors_fn=_fit_all_detectors_fn,
            reconcile_detector_flags_fn=_reconcile_detector_flags_fn,
            logger=_Logger(),
        )

        assert out.use_cache is True
        assert out.detectors_just_trained is False
        assert out.cached_models is not None
        assert out.cached_manifest is not None
        assert out.cached_calibration_params is not None
        assert out.ar1_detector is cached_detector
        assert out.pca_detector is cached_detector
        assert out.iforest_detector is cached_detector

    def test_run_detector_initialization_stage_wraps_models_load_and_train_fit_sections(self):
        """Stage wrapper should always time models.load and time train.detector_fit when fitting occurs."""
        from core.detector_orchestrator import run_detector_initialization_stage

        train = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        score = pd.DataFrame({"a": [1.5, 2.5]})
        section_calls = []

        class _Section:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def _section_fn(name):
            section_calls.append(name)
            return _Section()

        fitted = object()

        def _fit_all_detectors_fn(**kwargs):
            return {
                "ar1_detector": fitted,
                "pca_detector": fitted,
                "iforest_detector": fitted,
                "gmm_detector": None,
                "omr_detector": None,
                "pca_train_spe": np.array([0.1, 0.2, 0.3]),
                "pca_train_t2": np.array([0.2, 0.3, 0.4]),
            }

        out = run_detector_initialization_stage(
            section_fn=_section_fn,
            fit_all_detectors_fn=_fit_all_detectors_fn,
            train=train,
            score=score,
            cfg={
                "models": {"use_cache": True},
                "fusion": {"weights": {"ar1_z": 1.0, "pca_spe_z": 1.0, "iforest_z": 1.0}},
            },
            meta={"is_coldstart_run": True},
            detector_cache=None,
            output_manager=None,
            sql_client=None,
            run_id="r1",
            equip_id=1,
            equip="FD_FAN",
            load_and_rebuild_detectors_fn=lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("cache load should not run for coldstart")
            ),
            restore_detectors_from_runtime_cache_fn=lambda **kwargs: {},
            load_quality_regime_state_if_needed_fn=lambda **kwargs: (None, 0, False),
            reconcile_detector_flags_fn=lambda **kwargs: {
                "ar1_enabled": True,
                "pca_enabled": True,
                "iforest_enabled": True,
                "gmm_enabled": False,
                "omr_enabled": False,
            },
            logger=type("L", (), {"info": lambda *a, **k: None, "warn": lambda *a, **k: None, "error": lambda *a, **k: None})(),
        )

        assert section_calls == ["models.load", "train.detector_fit"]
        assert out.detectors_just_trained is True
        assert out.ar1_detector is fitted
        assert out.pca_detector is fitted
        assert out.iforest_detector is fitted

    def test_run_detector_initialization_stage_skips_train_fit_section_when_cache_is_valid(self):
        """Stage wrapper should not open train.detector_fit section when cache provides required detectors."""
        from core.detector_orchestrator import run_detector_initialization_stage

        train = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        score = pd.DataFrame({"a": [1.5, 2.5]})
        section_calls = []

        class _Section:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def _section_fn(name):
            section_calls.append(name)
            return _Section()

        cached_detector = object()

        out = run_detector_initialization_stage(
            section_fn=_section_fn,
            fit_all_detectors_fn=lambda **kwargs: (_ for _ in ()).throw(AssertionError("fit should not run")),
            train=train,
            score=score,
            cfg={
                "models": {"use_cache": True},
                "fusion": {"weights": {"ar1_z": 1.0, "pca_spe_z": 1.0, "iforest_z": 1.0}},
            },
            meta={"is_coldstart_run": False},
            detector_cache=None,
            output_manager=None,
            sql_client=object(),
            run_id="r1",
            equip_id=1,
            equip="FD_FAN",
            load_and_rebuild_detectors_fn=lambda **kwargs: {
                "train": kwargs["train"],
                "score": kwargs["score"],
                "cached_models": {"ok": True},
                "cached_manifest": {"train_sensors": ["a"]},
                "cached_calibration_params": {"ar1_z": {"med": 0.0}},
                "ar1_detector": cached_detector,
                "pca_detector": cached_detector,
                "iforest_detector": cached_detector,
                "gmm_detector": None,
                "omr_detector": None,
                "regime_model": None,
                "col_meds": {"a": 2.0},
            },
            restore_detectors_from_runtime_cache_fn=lambda **kwargs: {},
            load_quality_regime_state_if_needed_fn=lambda **kwargs: (None, 0, False),
            reconcile_detector_flags_fn=lambda **kwargs: {
                "ar1_enabled": True,
                "pca_enabled": True,
                "iforest_enabled": True,
                "gmm_enabled": False,
                "omr_enabled": False,
            },
            logger=type("L", (), {"info": lambda *a, **k: None, "warn": lambda *a, **k: None, "error": lambda *a, **k: None})(),
        )

        assert section_calls == ["models.load"]
        assert out.detectors_just_trained is False
        assert out.ar1_detector is cached_detector
        assert out.pca_detector is cached_detector
        assert out.iforest_detector is cached_detector

    def test_load_and_rebuild_detectors_from_sql_cache_uses_local_rebuild(self, monkeypatch):
        """SQL cache loader in detector orchestrator should rebuild detectors directly without callback injection."""
        from core import detector_orchestrator as orch

        train = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        score = pd.DataFrame({"a": [1.5, 2.5]})
        cached_models = {"calibration_params": {"ar1_z": {"med": 0.0, "scale": 1.0}}}
        cached_manifest = {"train_sensors": ["a"]}

        monkeypatch.setattr(
            orch,
            "load_cached_models_with_validation",
            lambda **kwargs: (cached_models, cached_manifest),
        )
        monkeypatch.setattr(
            orch,
            "align_current_features_to_cached_manifest",
            lambda **kwargs: (kwargs["train"], kwargs["score"], ["a"], True),
        )

        sentinel = object()
        rebuild_called = {"called": False}

        def _rebuild_detectors_from_cache(**kwargs):
            rebuild_called["called"] = True
            return {
                "ar1_detector": sentinel,
                "pca_detector": sentinel,
                "iforest_detector": sentinel,
                "gmm_detector": None,
                "omr_detector": None,
                "regime_model": None,
                "feature_medians": {"a": 2.0},
                "validation_warnings": [],
            }

        monkeypatch.setattr(orch, "rebuild_detectors_from_cache", _rebuild_detectors_from_cache)

        class _Logger:
            def info(self, *args, **kwargs):
                pass

            def warn(self, *args, **kwargs):
                pass

        out = orch.load_and_rebuild_detectors_from_sql_cache(
            train=train,
            score=score,
            equip="FD_FAN",
            sql_client=object(),
            equip_id=1,
            cfg={},
            logger=_Logger(),
        )

        assert rebuild_called["called"] is True
        assert out["ar1_detector"] is sentinel
        assert out["pca_detector"] is sentinel
        assert out["iforest_detector"] is sentinel
        assert out["cached_calibration_params"] == cached_models["calibration_params"]
        assert out["col_meds"] == {"a": 2.0}

    def test_model_version_manager_requires_connected_sql_context(self):
        """ModelVersionManager should fail fast when SQL context invariants are not satisfied."""
        from core.model_persistence import ModelVersionManager

        with pytest.raises(ValueError):
            ModelVersionManager(equip="FD_FAN", sql_client=None, equip_id=1)

        class _SqlNoConn:
            conn = None

        with pytest.raises(ValueError):
            ModelVersionManager(equip="FD_FAN", sql_client=_SqlNoConn(), equip_id=1)

    def test_initialize_detectors_for_run_requires_reconcile_fn(self):
        """Detector init should fail fast when reconcile callback is not provided."""
        from core.detector_orchestrator import _initialize_detectors_for_run

        train = pd.DataFrame({"a": [1.0, 2.0]})
        score = pd.DataFrame({"a": [1.5]})

        def _load_and_rebuild_detectors_fn(**kwargs):
            return {
                "train": kwargs["train"],
                "score": kwargs["score"],
                "cached_models": None,
                "cached_manifest": None,
                "cached_calibration_params": None,
                "ar1_detector": None,
                "pca_detector": None,
                "iforest_detector": None,
                "gmm_detector": None,
                "omr_detector": None,
                "regime_model": None,
                "col_meds": None,
            }

        def _restore_detectors_from_runtime_cache_fn(**kwargs):
            return {}

        def _load_quality_regime_state_if_needed_fn(**kwargs):
            return None, 0, False

        with pytest.raises(ValueError):
            _initialize_detectors_for_run(
                train=train,
                score=score,
                cfg={"models": {"use_cache": False}, "fusion": {"weights": {"ar1_z": 0, "pca_spe_z": 0, "iforest_z": 0}}},
                meta={"is_coldstart_run": False},
                detector_cache=None,
                output_manager=None,
                sql_client=None,
                run_id="r1",
                equip_id=1,
                equip="FD_FAN",
                load_and_rebuild_detectors_fn=_load_and_rebuild_detectors_fn,
                restore_detectors_from_runtime_cache_fn=_restore_detectors_from_runtime_cache_fn,
                load_quality_regime_state_if_needed_fn=_load_quality_regime_state_if_needed_fn,
                reconcile_detector_flags_fn=None,
            )

    def test_update_and_persist_model_lifecycle_safe_no_deps(self):
        """Lifecycle safe wrapper should return None when SQL/output manager are unavailable."""
        from core.model_lifecycle import update_and_persist_model_lifecycle_safe

        state = update_and_persist_model_lifecycle_safe(
            sql_client=None,
            output_manager=None,
            equip_id=1,
            regime_state_version=1,
            cfg={},
            train_data=pd.DataFrame({"a": [1.0, 2.0]}),
            run_id="r1",
            regime_model=None,
            score_out={},
            regime_quality_ok=True,
        )
        assert state is None

    def test_load_model_state_safe_no_sql_client(self):
        """Model lifecycle safe loader should return None without SQL client."""
        from core.model_lifecycle import load_model_state_safe

        state = load_model_state_safe(sql_client=None, equip_id=1)
        assert state is None

    def test_validate_data_contract_at_entry_passes_and_writes(self):
        """Data contract entry helper should pass and persist validation payload."""
        from core.pipeline_types import validate_data_contract_at_entry

        class _OutputManager:
            def __init__(self):
                self.rows = []

            def write_data_contract_validation(self, payload):
                self.rows.append(payload)

        class _Logger:
            def warn(self, *args, **kwargs):
                pass

            def error(self, *args, **kwargs):
                pass

        meta = type(
            "Meta",
            (),
            {"kept_cols": ["sensor_a"], "timestamp_col": "Timestamp", "is_coldstart_run": False},
        )()
        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        train = pd.DataFrame({"sensor_a": [1.0, 2.0]}, index=idx)
        score = pd.DataFrame({"sensor_a": [1.1]}, index=idx[:1])
        out = _OutputManager()

        validation = validate_data_contract_at_entry(
            train=train,
            score=score,
            meta=meta,
            refit_requested=False,
            cfg={},
            output_manager=out,
            equip_id=1,
            equip="FD_FAN",
            run_id="r1",
            logger=_Logger(),
        )

        assert validation.passed is True
        assert len(out.rows) == 1
        assert out.rows[0]["Passed"] is True

    def test_validate_data_contract_at_entry_raises_on_insufficient_rows(self):
        """Data contract entry helper should raise when minimum score rows are not met."""
        from core.pipeline_types import validate_data_contract_at_entry

        class _Logger:
            def warn(self, *args, **kwargs):
                pass

            def error(self, *args, **kwargs):
                pass

        meta = type(
            "Meta",
            (),
            {"kept_cols": ["sensor_a"], "timestamp_col": "Timestamp", "is_coldstart_run": False},
        )()
        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        train = pd.DataFrame({"sensor_a": [1.0, 2.0]}, index=idx)
        score = pd.DataFrame({"sensor_a": [1.1]}, index=idx[:1])

        with pytest.raises(ValueError, match="DataContract validation FAILED"):
            validate_data_contract_at_entry(
                train=train,
                score=score,
                meta=meta,
                refit_requested=False,
                cfg={"data": {"min_score_samples": 5}},
                output_manager=None,
                equip_id=1,
                equip="FD_FAN",
                run_id="r1",
                logger=_Logger(),
            )

    def test_run_data_guardrails_safe_returns_default_on_error(self, monkeypatch):
        """Guardrails safe wrapper should return default low_var_threshold on errors."""
        from core import pipeline_types

        def _boom(*args, **kwargs):
            raise RuntimeError("guardrail fail")

        monkeypatch.setattr(pipeline_types, "run_data_guardrails", _boom)

        class _Logger:
            def warn(self, *args, **kwargs):
                pass

        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        train = pd.DataFrame({"sensor": [1.0, 1.0]}, index=idx)
        score = pd.DataFrame({"sensor": [1.0]}, index=idx[:1])
        meta = type("Meta", (), {"dropped_cols": []})()

        out = pipeline_types.run_data_guardrails_safe(
            train=train,
            score=score,
            meta=meta,
            cfg={},
            output_manager=None,
            run_id=1,
            equip_id=1,
            equip="FD_FAN",
            logger=_Logger(),
        )
        assert out.low_var_threshold == pytest.approx(1e-4)
        assert out.low_var_features == []

    def test_apply_regime_health_labels_sets_unknown_when_quality_bad(self):
        """Regime health helper should mark unknown when quality is not acceptable."""
        from core.regimes import apply_regime_health_labels

        frame = pd.DataFrame({"regime_label": np.array([0, 1, -1]), "fused": [0.1, 0.2, 0.3]})
        out_frame, stats = apply_regime_health_labels(
            frame=frame,
            regime_model=None,
            regime_quality_ok=False,
            cfg={},
            output_manager=None,
        )
        assert "regime_state" in out_frame.columns
        assert set(out_frame["regime_state"].unique().tolist()) == {"unknown"}
        assert stats == {}

    def test_update_health_labels_applies_per_regime_threshold_overrides(self):
        """Per-regime health thresholds should override global warn/alert values when provided."""
        from core.regimes import update_health_labels

        idx = pd.date_range("2026-01-01", periods=6, freq="h")
        labels = np.array([0, 0, 1, 1, 1, 2], dtype=int)
        fused = pd.Series([2.6, 2.7, 3.1, 3.2, 3.3, 4.2], index=idx)
        cfg = {
            "regimes": {
                "health": {
                    "fused_warn_z": 2.5,
                    "fused_alert_z": 4.0,
                    "per_regime_thresholds": {
                        "0": {"warn": 2.8, "alert": 3.5},
                        "1": {"warn": 2.9, "alert": 3.0},
                    },
                }
            }
        }

        class _Model:
            def __init__(self):
                self.health_labels = {}
                self.stats = {}
                self.meta = {}
                self.normal_regime_label_ = None
                self.regime_semantic_labels_ = {}

        model = _Model()
        stats = update_health_labels(model=model, labels=labels, fused_series=fused, cfg=cfg)

        assert model.health_labels[0] == "healthy"  # 2.65 < per-regime warn 2.8
        assert model.health_labels[1] == "critical"  # 3.2 >= per-regime alert 3.0
        assert model.health_labels[2] == "critical"  # 4.2 >= global alert 4.0
        assert stats[0]["warn_threshold"] == pytest.approx(2.8)
        assert stats[1]["alert_threshold"] == pytest.approx(3.0)
        assert stats[2]["warn_threshold"] == pytest.approx(2.5)
        assert model.meta.get("health_threshold_mode") == "per_regime_overrides"

    def test_build_regime_feature_basis_stage_success(self, monkeypatch):
        """Regime basis helper should return basis payload without degradation on success."""
        from core import regimes

        idx = pd.date_range("2026-01-01", periods=3, freq="h")
        train = pd.DataFrame({"a": [1.0, 2.0, 3.0]}, index=idx)
        score = pd.DataFrame({"a": [1.5, 2.5]}, index=idx[:2])
        basis_train = pd.DataFrame({"r_a": [0.1, 0.2, 0.3]}, index=idx)
        basis_score = pd.DataFrame({"r_a": [0.15, 0.25]}, index=idx[:2])

        def _build_feature_basis(**kwargs):
            return basis_train, basis_score, {"source": "ok"}

        monkeypatch.setattr(regimes, "build_feature_basis", _build_feature_basis)
        regime_model = type("M", (), {"feature_columns": ["r_a"]})()

        class _Logger:
            def warn(self, *args, **kwargs):
                pass

        out = regimes.build_regime_feature_basis_stage(
            train_features=train,
            score_features=score,
            raw_train=train,
            raw_score=score,
            pca_detector=None,
            cfg={"regimes": {"method": "hdbscan"}},
            regime_model=regime_model,
            equip="FD_FAN",
            logger=_Logger(),
        )

        assert out.degraded is False
        assert out.regime_basis_train.equals(basis_train)
        assert out.regime_basis_score.equals(basis_score)
        assert out.regime_basis_meta == {"source": "ok"}
        assert out.regime_basis_hash is not None
        assert out.regime_model is regime_model

    def test_build_regime_feature_basis_stage_marks_degraded_and_resets_model(self, monkeypatch):
        """Regime basis helper should mark degraded and clear cached model when basis build fails."""
        from core import regimes

        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        train = pd.DataFrame({"a": [1.0, 2.0]}, index=idx)
        score = pd.DataFrame({"a": [1.5, 2.5]}, index=idx)

        def _boom(**kwargs):
            raise RuntimeError("basis failed")

        monkeypatch.setattr(regimes, "build_feature_basis", _boom)
        regime_model = type("M", (), {"feature_columns": ["r_a"]})()

        class _Logger:
            def warn(self, *args, **kwargs):
                pass

        out = regimes.build_regime_feature_basis_stage(
            train_features=train,
            score_features=score,
            raw_train=train,
            raw_score=score,
            pca_detector=None,
            cfg={},
            regime_model=regime_model,
            equip="FD_FAN",
            logger=_Logger(),
        )

        assert out.degraded is True
        assert out.regime_basis_train is None
        assert out.regime_basis_score is None
        assert out.regime_basis_meta == {}
        assert out.regime_basis_hash is None
        assert out.regime_model is None

    def test_regime_module_no_longer_exports_classify_tag(self):
        """Active regime logic should not expose the old tag-taxonomy helper."""
        from core import regimes

        assert not hasattr(regimes, "_classify_tag")

    def test_select_tag_agnostic_numeric_surface_prefers_variable_generic_columns(self):
        """Surface selector should work on generic names without PCA or taxonomy metadata."""
        from core import regimes

        idx = pd.date_range("2026-01-01", periods=4, freq="h")
        train = pd.DataFrame(
            {
                "sensor_1_avg": [1.0, 2.0, 3.0, 4.0],
                "sensor_2_avg": [0.0, 10.0, 0.0, 10.0],
                "sensor_3_avg": [5.0, 5.0, 5.0, 5.0],
                "text_tag": ["a", "b", "c", "d"],
            },
            index=idx,
        )
        score = pd.DataFrame(
            {
                "sensor_1_avg": [1.5, 2.5],
                "sensor_2_avg": [5.0, 7.5],
                "sensor_3_avg": [5.0, 5.0],
                "text_tag": ["x", "y"],
            },
            index=idx[:2],
        )

        cols, train_numeric, score_numeric, meta = regimes.select_tag_agnostic_numeric_surface(train, score, cfg={})

        assert cols == ["sensor_2_avg", "sensor_1_avg"]
        assert list(train_numeric.columns) == cols
        assert list(score_numeric.columns) == cols
        assert meta["surface_type"] == "tag_agnostic_numeric"
        assert meta["selected_count"] == 2
        assert meta["dropped_low_iqr_count"] >= 1

    def test_select_tag_agnostic_numeric_surface_respects_config_thresholds(self):
        """Surface selector should honor runtime config for max_cols and validity thresholds."""
        from core import regimes

        idx = pd.date_range("2026-01-01", periods=5, freq="h")
        train = pd.DataFrame(
            {
                "sensor_1_avg": [1.0, 2.0, 3.0, 4.0, 5.0],
                "sensor_2_avg": [0.0, 10.0, 0.0, 10.0, 0.0],
                "sensor_3_avg": [1.0, np.nan, np.nan, np.nan, 5.0],
            },
            index=idx,
        )
        score = pd.DataFrame(
            {
                "sensor_1_avg": [1.5, 2.5],
                "sensor_2_avg": [5.0, 7.5],
                "sensor_3_avg": [1.5, 2.5],
            },
            index=idx[:2],
        )

        cols, train_numeric, score_numeric, meta = regimes.select_tag_agnostic_numeric_surface(
            train,
            score,
            cfg={
                "regimes": {
                    "feature_basis": {
                        "max_cols": 1,
                        "min_valid_fraction": 0.60,
                        "min_iqr": 1e-6,
                    }
                }
            },
        )

        assert cols == ["sensor_2_avg"]
        assert list(train_numeric.columns) == cols
        assert list(score_numeric.columns) == cols
        assert meta["max_cols"] == 1
        assert meta["min_valid_fraction"] == 0.60
        assert meta["truncated"] is True

    def test_build_feature_basis_uses_tag_agnostic_surface_and_ignores_pca_fallback(self):
        """Regime basis should come from shared numeric surface, not naming heuristics or PCA fallback."""
        from core import regimes

        idx = pd.date_range("2026-01-01", periods=4, freq="h")
        train_features = pd.DataFrame({"feat": [0.1, 0.2, 0.3, 0.4]}, index=idx)
        score_features = pd.DataFrame({"feat": [0.15, 0.25]}, index=idx[:2])
        raw_train = pd.DataFrame(
            {
                "sensor_1_avg": [1.0, 2.0, 3.0, 4.0],
                "sensor_2_avg": [0.0, 10.0, 0.0, 10.0],
                "sensor_3_avg": [5.0, 5.0, 5.0, 5.0],
            },
            index=idx,
        )
        raw_score = pd.DataFrame(
            {
                "sensor_1_avg": [1.5, 2.5],
                "sensor_2_avg": [6.0, 8.0],
                "sensor_3_avg": [5.0, 5.0],
            },
            index=idx[:2],
        )

        class _BoomScaler:
            def transform(self, _):
                raise AssertionError("PCA fallback should not be used")

        pca_detector = type("PcaDetector", (), {"pca": object(), "scaler": _BoomScaler()})()

        basis_train, basis_score, meta = regimes.build_feature_basis(
            train_features=train_features,
            score_features=score_features,
            raw_train=raw_train,
            raw_score=raw_score,
            pca_detector=pca_detector,
            cfg={},
        )

        assert list(basis_train.columns) == ["sensor_2_avg", "sensor_1_avg"]
        assert list(basis_score.columns) == ["sensor_2_avg", "sensor_1_avg"]
        assert meta["feature_surface_type"] == "tag_agnostic_numeric"
        assert meta["n_pca"] == 0
        assert meta["raw_tags"] == ["sensor_2_avg", "sensor_1_avg"]

    def test_build_regime_feature_basis_stage_invalidates_cached_model_on_version_mismatch(self, monkeypatch):
        """Cached regime models should refit when the basis contract version changes."""
        from core import regimes

        idx = pd.date_range("2026-01-01", periods=3, freq="h")
        train = pd.DataFrame({"a": [1.0, 2.0, 3.0]}, index=idx)
        score = pd.DataFrame({"a": [1.5, 2.5]}, index=idx[:2])
        basis_train = pd.DataFrame({"sensor_1_avg": [0.1, 0.2, 0.3]}, index=idx)
        basis_score = pd.DataFrame({"sensor_1_avg": [0.15, 0.25]}, index=idx[:2])

        def _build_feature_basis(**kwargs):
            return basis_train, basis_score, {"source": "ok"}

        monkeypatch.setattr(regimes, "build_feature_basis", _build_feature_basis)
        regime_model = type(
            "M",
            (),
            {"feature_columns": ["sensor_1_avg"], "meta": {"model_version": "4.0"}},
        )()

        class _Logger:
            def warn(self, *args, **kwargs):
                pass

        out = regimes.build_regime_feature_basis_stage(
            train_features=train,
            score_features=score,
            raw_train=train,
            raw_score=score,
            pca_detector=None,
            cfg={"regimes": {"method": "hdbscan"}},
            regime_model=regime_model,
            equip="FD_FAN",
            logger=_Logger(),
        )

        assert out.regime_basis_train.equals(basis_train)
        assert out.regime_model is None

    def test_build_regime_feature_basis_stage_reuses_cached_basis_contract(self):
        """Cached regime basis contracts should stabilize replay batches when raw tags remain available."""
        from core import regimes

        idx = pd.date_range("2026-01-01", periods=4, freq="h")
        train_features = pd.DataFrame({"feat": [0.1, 0.2, 0.3, 0.4]}, index=idx)
        score_features = pd.DataFrame({"feat": [0.15, 0.25]}, index=idx[:2])
        raw_train = pd.DataFrame(
            {
                "sensor_1_avg": [10.0, 11.0, 12.0, 13.0],
                "sensor_2_avg": [1.0, 3.0, 5.0, 7.0],
                "sensor_3_avg": [0.0, 100.0, 0.0, 100.0],
            },
            index=idx,
        )
        raw_score = pd.DataFrame(
            {
                "sensor_1_avg": [10.5, 12.5],
                "sensor_2_avg": [2.0, 6.0],
                "sensor_3_avg": [100.0, 0.0],
            },
            index=idx[:2],
        )
        regime_model = type(
            "M",
            (),
            {
                "feature_columns": ["sensor_1_avg", "sensor_2_avg"],
                "meta": {
                    "model_version": regimes.REGIME_MODEL_VERSION,
                    "basis_signature": "stable_basis_sig",
                    "basis_scaler_cols": ["sensor_1_avg", "sensor_2_avg"],
                    "basis_scaler_mean": [11.5, 4.0],
                    "basis_scaler_var": [1.25, 5.0],
                    "basis_fill_values": {"sensor_1_avg": 11.5, "sensor_2_avg": 4.0},
                },
            },
        )()

        class _Logger:
            def info(self, *args, **kwargs):
                pass

            def warn(self, *args, **kwargs):
                pass

        out = regimes.build_regime_feature_basis_stage(
            train_features=train_features,
            score_features=score_features,
            raw_train=raw_train,
            raw_score=raw_score,
            pca_detector=None,
            cfg={"regimes": {"method": "hdbscan"}},
            regime_model=regime_model,
            equip="FD_FAN",
            logger=_Logger(),
        )

        assert list(out.regime_basis_train.columns) == ["sensor_1_avg", "sensor_2_avg"]
        assert out.regime_basis_meta["basis_contract_reused"] is True
        assert out.basis_drift_decision.basis_compatibility == "COMPATIBLE"
        assert out.regime_model is regime_model

    def test_apply_transient_state_labels_no_regime_label(self):
        """Transient helper should no-op when regime_label column is absent."""
        from core.regimes import apply_transient_state_labels

        frame = pd.DataFrame({"fused": [0.1, 0.2, 0.3]})
        score_data = pd.DataFrame({"sensor": [1.0, 2.0, 3.0]})
        out_frame, counts = apply_transient_state_labels(frame=frame, score_data=score_data, cfg={})
        assert out_frame.equals(frame)
        assert counts == {}

    def test_detect_transient_states_handles_generic_numeric_columns(self):
        """Transient detection should work on generic numeric names without taxonomy metadata."""
        from core.regimes import detect_transient_states

        idx = pd.date_range("2026-01-01", periods=5, freq="h")
        data = pd.DataFrame(
            {
                "sensor_1_avg": [1.0, 1.2, 1.8, 2.6, 2.7],
                "sensor_2_avg": [5.0, 5.1, 5.0, 5.4, 5.5],
            },
            index=idx,
        )
        regime_labels = np.array([0, 0, 0, 1, 1])

        states = detect_transient_states(data=data, regime_labels=regime_labels, cfg={})

        assert len(states) == len(data)
        assert set(states.tolist()) <= {"steady", "transient", "trip"}

    def test_detect_transient_states_marks_step_change_without_labeling_full_batch_trip(self):
        """A sharp operating change should create a bounded transient window, not a near-all-trip batch."""
        from core.regimes import detect_transient_states

        idx = pd.date_range("2026-01-01", periods=40, freq="h")
        data = pd.DataFrame(
            {
                "sensor_1_avg": np.r_[np.ones(20), np.full(20, 3.5)],
                "sensor_2_avg": np.r_[np.full(20, 2.0), np.full(20, 2.8)],
                "sensor_3_avg": np.r_[np.linspace(10.0, 10.3, 20), np.linspace(12.0, 12.2, 20)],
            },
            index=idx,
        )
        regime_labels = np.array([0] * 20 + [1] * 20)

        states = detect_transient_states(data=data, regime_labels=regime_labels, cfg={})
        counts = pd.Series(states).value_counts().to_dict()

        assert counts.get("trip", 0) < 12
        assert counts.get("steady", 0) > counts.get("trip", 0)
        assert counts.get("transient", 0) > 0

    def test_detect_transient_states_ignores_legacy_low_thresholds_for_normalized_index(self):
        """Legacy sub-unit thresholds should be upgraded to conservative normalized defaults."""
        from core.regimes import detect_transient_states

        idx = pd.date_range("2026-01-01", periods=24, freq="h")
        data = pd.DataFrame(
            {
                "sensor_1_avg": np.linspace(1.0, 2.0, len(idx)),
                "sensor_2_avg": np.linspace(5.0, 5.5, len(idx)),
            },
            index=idx,
        )
        regime_labels = np.zeros(len(idx), dtype=int)
        cfg = {
            "regimes": {
                "transient_detection": {
                    "roc_threshold_high": 0.15,
                    "roc_threshold_trip": 0.30,
                }
            }
        }

        states = detect_transient_states(data=data, regime_labels=regime_labels, cfg=cfg)
        counts = pd.Series(states).value_counts().to_dict()

        assert counts.get("trip", 0) == 0
        assert counts.get("steady", 0) >= len(idx) - 4

    def test_select_ewm_monitoring_surface_keeps_all_eligible_generic_channels(self):
        """EWM monitoring surface should keep every eligible generic raw channel without a regime cap."""
        from core import regimes

        idx = pd.date_range("2026-01-01", periods=6, freq="h")
        train = pd.DataFrame(
            {
                f"sensor_{i:02d}_avg": np.linspace(float(i), float(i + 5), len(idx))
                for i in range(30)
            },
            index=idx,
        )
        train["constant_sensor"] = 1.0
        score = pd.DataFrame(
            {
                f"sensor_{i:02d}_avg": np.linspace(float(i) + 0.5, float(i) + 2.5, 3)
                for i in range(30)
            },
            index=idx[:3],
        )
        score.loc[idx[0], "sensor_00_avg"] = np.nan

        cols, train_numeric, score_numeric, meta = regimes.select_ewm_monitoring_surface(
            train,
            score,
            cfg={},
        )

        assert len(cols) == 30
        assert "constant_sensor" not in cols
        assert list(train_numeric.columns) == cols
        assert list(score_numeric.columns) == cols
        assert bool(pd.isna(score_numeric["sensor_00_avg"].iloc[0]))
        assert meta["surface_type"] == "ewm_monitoring_raw_numeric"
        assert meta["selected_count"] == 30
        assert meta["max_cols"] == 0
        assert meta["truncated"] is False

    def test_select_ewm_monitoring_surface_respects_surface_config(self):
        """EWM monitoring surface should honor its dedicated config thresholds."""
        from core import regimes

        idx = pd.date_range("2026-01-01", periods=5, freq="h")
        train = pd.DataFrame(
            {
                "sensor_1_avg": [1.0, 2.0, 3.0, 4.0, 5.0],
                "sensor_2_avg": [0.0, 10.0, 0.0, 10.0, 0.0],
                "sensor_3_avg": [1.0, np.nan, np.nan, np.nan, 5.0],
                "sensor_4_avg": [7.0, 7.0, 7.0, 7.0, 7.0],
            },
            index=idx,
        )
        score = pd.DataFrame(
            {
                "sensor_1_avg": [1.5, 2.5],
                "sensor_2_avg": [5.0, 7.5],
                "sensor_3_avg": [1.5, 2.5],
                "sensor_4_avg": [7.0, 7.0],
            },
            index=idx[:2],
        )

        cols, train_numeric, score_numeric, meta = regimes.select_ewm_monitoring_surface(
            train,
            score,
            cfg={
                "models": {
                    "ewm_baseline": {
                        "surface": {
                            "min_valid_fraction": 0.80,
                            "min_iqr": 1e-6,
                        }
                    }
                }
            },
        )

        assert cols == ["sensor_2_avg", "sensor_1_avg"]
        assert list(train_numeric.columns) == cols
        assert list(score_numeric.columns) == cols
        assert meta["surface_type"] == "ewm_monitoring_raw_numeric"
        assert meta["min_valid_fraction"] == 0.80

    def test_ewm_save_skips_without_state_version_column(self, monkeypatch):
        """EWM persistence must not reuse legacy schema without StateVersion."""
        from core.ewm_baseline import EWMBaselineManager, _SensorState

        manager = EWMBaselineManager(equip_id=5010)
        manager._state[(-1, "sensor_1_avg")] = _SensorState(mean_fast=1.0, mean_slow=1.0, n_samples=5)

        monkeypatch.setattr(manager, "_has_state_version_column", lambda sql_client: False)
        called = {"upsert": False}

        def _boom(*args, **kwargs):
            called["upsert"] = True
            raise AssertionError("save_to_sql should skip when StateVersion column is missing")

        monkeypatch.setattr(manager, "_upsert_rows", _boom)

        assert manager.save_to_sql(object()) == 0
        assert called["upsert"] is False

    def test_ewm_save_persists_state_version_two(self, monkeypatch):
        """EWM save path should stamp the explicit monitoring-surface state version."""
        from core.ewm_baseline import EWM_STATE_VERSION, EWMBaselineManager, _SensorState

        manager = EWMBaselineManager(equip_id=5010)
        manager._state[(-1, "sensor_1_avg")] = _SensorState(
            mean_fast=1.0,
            var_fast=0.5,
            mean_slow=1.2,
            var_slow=0.7,
            n_samples=12,
        )

        monkeypatch.setattr(manager, "_has_state_version_column", lambda sql_client: True)
        captured = {}

        def _capture(sql_client, df):
            captured["df"] = df.copy()
            return len(df)

        monkeypatch.setattr(manager, "_upsert_rows", _capture)

        assert manager.save_to_sql(object()) == 1
        assert int(captured["df"]["StateVersion"].iloc[0]) == EWM_STATE_VERSION
        assert captured["df"]["SensorName"].iloc[0] == "sensor_1_avg"

    def test_ewm_load_skips_without_state_version_column(self, monkeypatch):
        """EWM load path should ignore legacy schema until the versioning migration is applied."""
        from core.ewm_baseline import EWMBaselineManager

        manager = EWMBaselineManager(equip_id=5010)
        monkeypatch.setattr(manager, "_has_state_version_column", lambda sql_client: False)

        assert manager.load_from_sql(object()) == 0

    def test_online_pca_binner_warms_then_assigns_generic_channels(self):
        """OnlinePCABinner should become active on generic raw channels without tag metadata."""
        from core.regime_binner import OnlinePCABinner

        idx = pd.date_range("2026-01-01", periods=6, freq="h")
        df = pd.DataFrame(
            {
                "sensor_00_avg": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
                "sensor_01_avg": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5],
                "sensor_02_avg": [5.0, 4.2, 3.4, 2.6, 1.8, 1.0],
            },
            index=idx,
        )

        binner = OnlinePCABinner(n_bins=3, min_rows_for_assignment=5, history_limit=64)
        binner.observe_batch(df.iloc[:3])
        early = binner.assign_batch(df.iloc[:3])
        assert np.all(early == -1)

        seen_before = binner._n_rows_seen
        binner.observe_batch(df.iloc[3:])
        assigned = binner.assign_batch(df)

        assert binner.sensor_cols == ["sensor_00_avg", "sensor_01_avg", "sensor_02_avg"]
        assert binner._n_rows_seen > seen_before
        assert np.any(assigned >= 0)
        assert set(assigned[assigned >= 0].tolist()) <= {0, 1, 2}

        seen_after = binner._n_rows_seen
        _ = binner.assign_batch(df.iloc[:2])
        assert binner._n_rows_seen == seen_after

    def test_online_pca_binner_load_skips_legacy_control_variable_state(self):
        """Legacy control-variable JSON should be discarded rather than reinterpreted."""
        from core.regime_binner import OnlinePCABinner

        class _Cursor:
            def __init__(self, state_json):
                self._state_json = state_json

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, query, params):
                self.description = [("StateJson",)]

            def fetchone(self):
                return (self._state_json,)

        class _Conn:
            def __init__(self, state_json):
                self._state_json = state_json

            def cursor(self):
                return _Cursor(self._state_json)

        legacy_json = '{"control_vars": ["power_output"], "n_bins": 3, "n_seen": 25, "edges": {"power_output": [1.0, 2.0]}}'
        sql_client = type("SQLClient", (), {"conn": _Conn(legacy_json)})()

        binner = OnlinePCABinner()
        assert binner.load_from_sql(sql_client, equip_id=5010) is False
        assert binner.sensor_cols == []

    def test_online_pca_binner_sql_round_trip_preserves_remap_state(self):
        """OnlinePCABinner should persist/load its tag-agnostic latent state on the existing SQL table."""
        from core.regime_binner import ONLINE_PCA_BINNER_TYPE, OnlinePCABinner

        class _Cursor:
            def __init__(self, conn):
                self._conn = conn
                self.description = []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, query, params):
                sql = " ".join(str(query).split()).upper()
                if "MERGE ACM_REGIMEBINNERSTATE" in sql:
                    self._conn.state_json = params[1]
                elif "SELECT STATEJSON FROM ACM_REGIMEBINNERSTATE" in sql:
                    self.description = [("StateJson",)]
                else:
                    raise AssertionError(f"Unexpected SQL in test: {query}")

            def fetchone(self):
                if self._conn.state_json is None:
                    return None
                return (self._conn.state_json,)

        class _Conn:
            def __init__(self):
                self.state_json = None
                self.commits = 0

            def cursor(self):
                return _Cursor(self)

            def commit(self):
                self.commits += 1

        idx = pd.date_range("2026-01-01", periods=8, freq="h")
        df = pd.DataFrame(
            {
                "sensor_00_avg": np.linspace(0.0, 7.0, len(idx)),
                "sensor_01_avg": np.linspace(1.0, 4.5, len(idx)),
                "sensor_02_avg": np.linspace(8.0, 2.0, len(idx)),
            },
            index=idx,
        )
        sql_client = type("SQLClient", (), {"conn": _Conn()})()

        binner = OnlinePCABinner(n_bins=3, min_rows_for_assignment=5, history_limit=64)
        binner.observe_batch(df)
        binner.mark_remapped()
        assert binner.save_to_sql(sql_client, equip_id=5010) is True
        assert sql_client.conn.commits == 1
        assert ONLINE_PCA_BINNER_TYPE in sql_client.conn.state_json

        restored = OnlinePCABinner()
        assert restored.load_from_sql(sql_client, equip_id=5010) is True
        assert restored.sensor_cols == ["sensor_00_avg", "sensor_01_avg", "sensor_02_avg"]
        assert restored.can_assign_fallback is False
        assigned = restored.assign_batch(df)
        assert np.any(assigned >= 0)
        assert set(assigned[assigned >= 0].tolist()) <= {0, 1, 2}

    def test_online_pca_binner_align_to_surface_invalidates_incompatible_state(self):
        """Persisted proxy state must be rebuilt cold when the monitoring surface changes."""
        from core.regime_binner import OnlinePCABinner

        idx = pd.date_range("2026-01-01", periods=8, freq="h")
        df = pd.DataFrame(
            {
                "sensor_00_avg": np.linspace(0.0, 7.0, len(idx)),
                "sensor_01_avg": np.linspace(1.0, 4.5, len(idx)),
                "sensor_02_avg": np.linspace(8.0, 2.0, len(idx)),
            },
            index=idx,
        )

        binner = OnlinePCABinner(n_bins=3, min_rows_for_assignment=5, history_limit=64)
        binner.observe_batch(df)
        assert binner.is_ready
        assert np.any(binner.assign_batch(df) >= 0)

        kept = binner.align_to_surface(["sensor_00_avg", "sensor_03_avg"])

        assert kept is False
        assert binner.sensor_cols == ["sensor_00_avg", "sensor_03_avg"]
        assert binner.is_ready is False
        assert binner._n_rows_seen == 0
        assert np.all(binner.assign_batch(df[["sensor_00_avg"]]) == -1)

    def test_online_pca_binner_align_to_surface_keeps_compatible_state(self):
        """Compatible monitoring surfaces should preserve latent proxy state."""
        from core.regime_binner import OnlinePCABinner

        idx = pd.date_range("2026-01-01", periods=8, freq="h")
        df = pd.DataFrame(
            {
                "sensor_00_avg": np.linspace(0.0, 7.0, len(idx)),
                "sensor_01_avg": np.linspace(1.0, 4.5, len(idx)),
                "sensor_02_avg": np.linspace(8.0, 2.0, len(idx)),
            },
            index=idx,
        )

        binner = OnlinePCABinner(n_bins=3, min_rows_for_assignment=5, history_limit=64)
        binner.observe_batch(df)
        seen = binner._n_rows_seen
        history_len = len(binner._pc1_history)

        kept = binner.align_to_surface(["sensor_00_avg", "sensor_01_avg", "sensor_02_avg"])

        assert kept is True
        assert binner._n_rows_seen == seen
        assert len(binner._pc1_history) == history_len

    def test_run_regime_labeling_stage_returns_labels_and_records_regime(self, monkeypatch):
        """Regime labeling stage helper should return labels and emit current regime metric."""
        from core import regimes

        class _Model:
            def __init__(self):
                self.cluster_labels_ = {0: "regime_0", 1: "regime_1"}
                self.model = object()

        def _fake_label(score_df, ctx, score_out, cfg):
            out_frame = score_out["frame"].copy()
            out_frame["regime_label"] = np.array([0, 1])
            return {
                "frame": out_frame,
                "regime_model": ctx["regime_model"],
                "regime_labels": np.array([0, 1]),
                "regime_labels_train": np.array([0, 0]),
                "regime_quality_ok": True,
            }

        definitions_calls = []

        def _fake_write_defs(**kwargs):
            definitions_calls.append(kwargs)
            return 1

        monkeypatch.setattr(regimes, "label", _fake_label)
        monkeypatch.setattr(regimes, "write_regime_definitions_for_audit", _fake_write_defs)

        recorded = []

        def _record_regime(equip, regime_id, regime_label):
            recorded.append((equip, regime_id, regime_label))

        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        score_df = pd.DataFrame({"sensor": [1.0, 2.0]}, index=idx)
        train_df = pd.DataFrame({"sensor": [1.0, 1.5]}, index=idx)
        frame = pd.DataFrame({"fused": [0.1, 0.2]}, index=idx)
        model = _Model()

        result = regimes.run_regime_labeling_stage(
            score_df=score_df,
            frame=frame,
            train_df=train_df,
            cfg={},
            regime_basis_train=train_df,
            regime_basis_score=score_df,
            regime_basis_meta={},
            regime_basis_hash=123,
            regime_model=model,
            regime_loaded_from_state=False,
            regime_state=None,
            regime_state_version=5,
            raw_train=train_df,
            output_manager=object(),
            current_model_maturity="LEARNING",
            equip="FD_FAN",
            equip_id=1,
            sql_client=None,
            record_regime_fn=_record_regime,
        )

        assert result.regime_model is model
        assert result.regime_quality_ok is True
        assert result.regime_state_version == 5
        assert result.train_regime_labels is not None
        assert result.score_regime_labels is not None
        assert recorded == [("FD_FAN", 1, "regime_1")]
        assert len(definitions_calls) == 1

    def test_run_regime_postprocess_stage_composes_health_and_transient(self, monkeypatch):
        """Regime postprocess stage should compose health and transient helpers and return final frame."""
        from core import regimes

        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        base_frame = pd.DataFrame({"regime_label": [0, 1], "fused": [0.1, 0.2]}, index=idx)

        def _fake_apply_health_labels(**kwargs):
            frame = kwargs["frame"].copy()
            frame["regime_state"] = ["steady", "transient"]
            return frame, {0: {"mean": 0.1}}

        def _fake_apply_transient_labels(**kwargs):
            frame = kwargs["frame"].copy()
            frame["transient_state"] = ["steady", "startup"]
            return frame, {"steady": 1, "startup": 1}

        monkeypatch.setattr(regimes, "apply_regime_health_labels", _fake_apply_health_labels)
        monkeypatch.setattr(regimes, "apply_transient_state_labels", _fake_apply_transient_labels)

        result = regimes.run_regime_postprocess_stage(
            frame=base_frame,
            score_data=base_frame[["fused"]],
            regime_model=None,
            regime_quality_ok=True,
            cfg={},
            output_manager=None,
        )

        assert "regime_state" in result.frame.columns
        assert "transient_state" in result.frame.columns
        assert result.transient_counts == {"steady": 1, "startup": 1}
        assert result.context_assignment.context_label == "REGIME_1"
        assert result.context_assignment.transition_status == "STARTUP"
        assert result.context_assignment.is_ambiguous is True

    def test_run_scoring_regime_stage_orchestrates_basis_score_label_and_occupancy(self, monkeypatch):
        """Scoring-regime stage should orchestrate basis build, detector score, regime label, and occupancy writes."""
        from core import regimes

        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        train_df = pd.DataFrame({"a": [1.0, 2.0]}, index=idx)
        score_df = pd.DataFrame({"a": [1.5, 2.5]}, index=idx)
        base_frame = pd.DataFrame({"a": [1.5, 2.5]}, index=idx)

        def _basis_stage(**kwargs):
            return regimes.RegimeBasisBuildResult(
                regime_basis_train=train_df,
                regime_basis_score=score_df,
                regime_basis_meta={},
                regime_basis_hash=101,
                regime_model=kwargs["regime_model"],
                degraded=False,
            )

        def _score_all_detectors_fn(**kwargs):
            frame = base_frame.copy()
            frame["ar1_raw"] = [0.1, 0.2]
            return frame, pd.DataFrame({"contrib": [0.4, 0.6]}, index=idx)

        def _resolve_maturity(**kwargs):
            return "LEARNING"

        def _run_regime_labeling_stage(**kwargs):
            frame = kwargs["frame"].copy()
            frame["regime_label"] = [0, 1]
            return regimes.RegimeLabelingStageResult(
                frame=frame,
                score_out={"frame": frame, "regime_quality_ok": True},
                regime_model=kwargs["regime_model"],
                train_regime_labels=np.array([0, 0]),
                score_regime_labels=np.array([0, 1]),
                regime_quality_ok=True,
                regime_state_version=kwargs["regime_state_version"],
                regime_loaded_from_state=kwargs["regime_loaded_from_state"],
            )

        occupancy_called = {"called": False}
        def _write_occupancy(**kwargs):
            occupancy_called["called"] = True
            return 1, 1

        sections = []
        class _Section:
            def __init__(self, name):
                self.name = name
            def __enter__(self):
                sections.append(self.name)
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        def _section_fn(name):
            return _Section(name)

        monkeypatch.setattr(regimes, "build_regime_feature_basis_stage", _basis_stage)
        monkeypatch.setattr(regimes, "run_regime_labeling_stage", _run_regime_labeling_stage)
        monkeypatch.setattr(regimes, "write_regime_occupancy_and_transitions", _write_occupancy)

        result = regimes.run_scoring_regime_stage(
            train_df=train_df,
            score_df=score_df,
            raw_train=train_df,
            raw_score=score_df,
            cfg={},
            pca_detector=None,
            regime_model=None,
            regime_state=None,
            regime_state_version=3,
            regime_loaded_from_state=False,
            det_flags={"ar1_enabled": True, "pca_enabled": False, "iforest_enabled": False, "gmm_enabled": False, "omr_enabled": False},
            detectors={"ar1_detector": object(), "pca_detector": None, "iforest_detector": None, "gmm_detector": None, "omr_detector": None},
            equip="FD_FAN",
            equip_id=1,
            sql_client=object(),
            output_manager=object(),
            refit_requested=False,
            section_fn=_section_fn,
            score_all_detectors_fn=_score_all_detectors_fn,
            resolve_maturity_for_regime_stage_fn=_resolve_maturity,
            record_regime_fn=None,
        )

        assert "regime_label" in result.frame.columns
        assert result.regime_quality_ok is True
        assert result.current_model_maturity == "LEARNING"
        assert result.degraded_regime_basis is False
        assert occupancy_called["called"] is True
        assert sections == ["score.detector_score", "regimes.label", "regimes.occupancy"]

    def test_run_drift_postprocess_stage_orchestrates_drift_and_episode_normalization(self, monkeypatch):
        """Drift postprocess stage should run drift pipeline and normalize episode schema."""
        from core import drift

        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        frame = pd.DataFrame({"fused": [0.1, 0.2]}, index=idx)
        score_out = {"k": "v"}
        episodes = pd.DataFrame({"episode_id": [1]}, index=[0])

        sections = []
        class _Section:
            def __init__(self, name):
                self.name = name
            def __enter__(self):
                sections.append(self.name)
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        def _section_fn(name):
            return _Section(name)

        def _run_drift_pipeline(**kwargs):
            out_frame = kwargs["frame"].copy()
            out_frame["drift_mode"] = ["FAULT", "DRIFT"]
            return {"frame": out_frame, "score_out": {"updated": True}}

        def _normalize_episodes_schema_fn(**kwargs):
            out_episodes = kwargs["episodes"].copy()
            out_episodes["severity"] = [0.9]
            out_frame = kwargs["frame"].copy()
            out_frame["normalized"] = [1, 1]
            return out_episodes, out_frame

        monkeypatch.setattr(drift, "run_drift_pipeline", _run_drift_pipeline)

        result = drift.run_drift_postprocess_stage(
            section_fn=_section_fn,
            score_data=frame[["fused"]],
            frame=frame,
            score_out=score_out,
            episodes=episodes,
            cfg={},
            regime_quality_ok=True,
            equip="FD_FAN",
            sql_client=object(),
            equip_id=1,
            output_manager=object(),
            logger=type("L", (), {"warn": lambda *a, **k: None})(),
            normalize_episodes_schema_fn=_normalize_episodes_schema_fn,
        )

        assert "drift_mode" in result.frame.columns
        assert "normalized" in result.frame.columns
        assert "severity" in result.episodes.columns
        assert result.score_out == {"updated": True}
        assert sections == ["drift"]

    def test_release_persist_memory_clears_raw_frames_and_detector_models(self):
        """Output manager persist cleanup helper should clear raw frames and detector model pointers."""
        from core.output_manager import OutputManager

        class _Detector:
            def __init__(self):
                self.model = object()

        output_manager = OutputManager.__new__(OutputManager)
        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        raw_train = pd.DataFrame({"sensor": [1.0, 2.0]}, index=idx)
        raw_score = pd.DataFrame({"sensor": [1.1, 2.1]}, index=idx)
        iforest_detector = _Detector()
        omr_detector = _Detector()

        out_train, out_score = output_manager.release_persist_memory(
            raw_train=raw_train,
            raw_score=raw_score,
            iforest_detector=iforest_detector,
            omr_detector=omr_detector,
        )

        assert out_train is None
        assert out_score is None
        assert iforest_detector.model is None
        assert omr_detector.model is None

    def test_persist_additional_artifacts_aggregates_counts(self):
        """Output manager helper should aggregate optional artifact write counts."""
        from core.output_manager import OutputManager

        output_manager = OutputManager.__new__(OutputManager)
        output_manager.write_detector_correlation_from_scores = lambda _df: 2
        output_manager.write_sensor_correlations_from_raw = lambda _df: 3
        output_manager.write_sensor_normalized_ts_from_raw = lambda _df, max_total_rows=10000: 4
        output_manager.write_seasonal_patterns_from_detected = lambda _p: 5

        frame = pd.DataFrame({"ar1_z": [0.1, 0.2], "iforest_z": [0.3, 0.4]})
        raw_score = pd.DataFrame({"sensor": [1.0, 2.0]})
        result = output_manager.persist_additional_artifacts(
            scores_df=frame,
            raw_score=raw_score,
            seasonal_patterns={"sensor": []},
        )

        assert result.detector_correlation_rows == 2
        assert result.sensor_correlation_rows == 3
        assert result.sensor_normalized_ts_rows == 4
        assert result.seasonal_pattern_rows == 5

    def test_persist_core_outputs_aggregates_insert_counts(self):
        """Output manager helper should aggregate inserted counts from scores and episodes writes."""
        from core.output_manager import OutputManager

        output_manager = OutputManager.__new__(OutputManager)
        output_manager.write_scores = lambda _df: {"inserted": 11}
        output_manager.write_episodes = lambda _df: {"inserted": 7}

        scores_df = pd.DataFrame({"fused": [0.1, 0.2]})
        episodes_df = pd.DataFrame({"episode_id": [1, 2, 3]})
        result = output_manager.persist_core_outputs(scores_df=scores_df, episodes_df=episodes_df)

        assert result.scores_inserted == 11
        assert result.episodes_inserted == 7
        assert result.episode_count == 3
        assert result.rows_written_delta == 18

    def test_populate_standard_metadata_fills_all_three_columns(self):
        """Payload generation helper should always populate RunID, EquipID, CreatedAt."""
        from core.output_manager import OutputManager

        out_mgr = OutputManager.__new__(OutputManager)
        out_mgr.run_id = "r-meta"
        out_mgr.equip_id = 99
        df = pd.DataFrame({"Timestamp": [pd.Timestamp("2026-01-01T00:00:00")], "x": [1.0]})

        out = out_mgr._populate_standard_metadata(df)
        assert out.loc[0, "RunID"] == "r-meta"
        assert int(out.loc[0, "EquipID"]) == 99
        assert pd.notna(out.loc[0, "CreatedAt"])

    def test_populate_standard_metadata_uses_fallbacks(self):
        """Payload generation helper should use stable fallbacks when context is missing."""
        from core.output_manager import OutputManager

        out_mgr = OutputManager.__new__(OutputManager)
        out_mgr.run_id = None
        out_mgr.equip_id = None
        df = pd.DataFrame({"x": [1.0]})

        out = out_mgr._populate_standard_metadata(df)
        assert out.loc[0, "RunID"] == "00000000-0000-0000-0000-000000000000"
        assert int(out.loc[0, "EquipID"]) == 0
        assert pd.notna(out.loc[0, "CreatedAt"])

    def test_prepare_dataframe_for_sql_uses_schema_datetime_columns(self):
        """Datetime coercion should follow schema-derived datetime columns."""
        from core.output_manager import OutputManager

        out_mgr = OutputManager.__new__(OutputManager)
        out_mgr._get_datetime_columns_for_table = lambda _table: {"ObservedAt"}

        df = pd.DataFrame(
            {
                "ObservedAt": ["2026-01-01 00:00:00", "2026-01-01 00:05:00"],
                "value": [1.0, 2.0],
            }
        )
        prepared = out_mgr._prepare_dataframe_for_sql(
            df,
            non_numeric_cols=set(),
            sql_table="ACM_Scores_Wide",
        )

        assert isinstance(prepared.loc[0, "ObservedAt"], datetime)
        assert isinstance(prepared.loc[1, "ObservedAt"], datetime)

    def test_audit_allowed_tables_write_coverage_returns_shape(self):
        """Write coverage audit should return expected keys and list payloads."""
        from core.output_manager import OutputManager

        out = OutputManager.__new__(OutputManager)
        report = out.audit_allowed_tables_write_coverage()

        assert isinstance(report, dict)
        assert "allowed_count" in report
        assert "referenced_count" in report
        assert "missing_write_paths" in report
        assert "referenced_not_allowed" in report
        assert isinstance(report["missing_write_paths"], list)
        assert isinstance(report["referenced_not_allowed"], list)

    def test_audit_allowed_tables_write_integrity_requires_sql_client(self):
        """Write integrity audit should require SQL client context."""
        from core.output_manager import OutputManager

        out = OutputManager.__new__(OutputManager)
        out.sql_client = None
        with pytest.raises(RuntimeError):
            out.audit_allowed_tables_write_integrity()

    def test_write_dataframe_uses_explicit_upsert_policy_handler(self):
        """write_dataframe should use generator-declared upsert policy instead of static table map."""
        from core.output_manager import OutputManager, WritePolicy

        output_manager = OutputManager(
            sql_client=None,
            run_id="r-policy",
            equip_id=1,
            enable_batching=False,
        )
        captured = {}

        def _upsert_handler(df):
            captured["columns"] = list(df.columns)
            captured["rows"] = len(df)
            return 5

        df = pd.DataFrame({"Timestamp": [pd.Timestamp("2026-01-01T00:00:00")], "value": [1.0]})
        result = output_manager.write_dataframe(
            df=df,
            artifact_name="policy-test",
            sql_table="ACM_PCA_Metrics",
            write_policy=WritePolicy(mode="upsert", upsert_handler=_upsert_handler),
        )

        assert result["inserted"] == 5
        assert result["sql_written"] is True
        assert captured["rows"] == 1
        assert "RunID" in captured["columns"]
        assert "EquipID" in captured["columns"]
        assert "CreatedAt" in captured["columns"]

    def test_build_replace_policy_derives_keys_from_contract(self):
        """build_replace_policy should derive key columns from centralized table contract map."""
        from core.output_manager import OutputManager

        output_manager = OutputManager(
            sql_client=None,
            run_id="r-policy",
            equip_id=1,
            enable_batching=False,
        )
        captured = {}
        output_manager._replace_by_keys = (
            lambda table_name, payload, keys: captured.update(
                {"table": table_name, "keys": list(keys), "rows": len(payload)}
            ) or len(payload)
        )
        policy = output_manager.build_replace_policy("ACM_HealthForecast")
        assert policy.mode == "upsert"
        assert callable(policy.upsert_handler)
        written = policy.upsert_handler(pd.DataFrame({"RunID": ["r"], "EquipID": [1], "Timestamp": [datetime.now()]}))
        assert written == 1
        assert captured["table"] == "ACM_HealthForecast"
        assert captured["keys"] == ["RunID", "EquipID", "Timestamp"]

    def test_audit_replace_policy_contract_is_valid(self):
        """Centralized replace-policy contract should resolve only allowed tables with non-empty keys."""
        from core.output_manager import OutputManager

        report = OutputManager.audit_replace_policy_contract()
        assert report["is_valid"] is True
        assert report["invalid_tables"] == []
        assert report["empty_key_tables"] == []

    def test_audit_table_write_contracts_is_valid(self):
        """Canonical table write contract registry should be complete and internally consistent."""
        from core.output_manager import OutputManager

        report = OutputManager.audit_table_write_contracts()
        assert report["is_valid"] is True
        assert report["missing_contracts"] == []
        assert report["invalid_contracts"] == []
        assert report["replace_without_keys"] == []

    def test_write_dataframe_injects_metadata_before_sql_for_representative_tables(self):
        """Representative SQL payloads should include RunID, EquipID, and CreatedAt before insert."""
        from core.output_manager import OutputManager

        output_manager = OutputManager(
            sql_client=None,
            run_id="r-meta-integrated",
            equip_id=777,
            enable_batching=False,
        )
        captured = {}

        def _capture_bulk_insert(table, frame):
            captured[table] = frame.copy()
            return len(frame)

        output_manager._bulk_insert_sql = _capture_bulk_insert

        scores_df = pd.DataFrame({"timestamp": [pd.Timestamp("2026-01-01T00:00:00")], "fused": [0.5]})
        output_manager.write_dataframe(
            scores_df,
            "scores-meta",
            sql_table="ACM_Scores_Wide",
            sql_columns={"timestamp": "Timestamp", "fused": "fused"},
            write_policy=output_manager.build_insert_policy(),
        )

        episodes_df = pd.DataFrame({"episode_id": [1], "start_ts": [pd.Timestamp("2026-01-01T00:00:00")]})
        output_manager.write_dataframe(
            episodes_df,
            "episodes-meta",
            sql_table="ACM_EpisodeDiagnostics",
            sql_columns={"episode_id": "EpisodeID", "start_ts": "StartTime"},
            write_policy=output_manager.build_insert_policy(),
        )

        dq_df = pd.DataFrame({"sensor": ["s1"], "CheckName": ["data_quality"], "CheckResult": ["OK"]})
        output_manager.write_dataframe(
            dq_df,
            "dq-meta",
            sql_table="ACM_DataQuality",
            write_policy=output_manager.build_insert_policy(),
        )

        for table in ("ACM_Scores_Wide", "ACM_EpisodeDiagnostics", "ACM_DataQuality"):
            assert table in captured
            out = captured[table]
            assert "RunID" in out.columns
            assert "EquipID" in out.columns
            assert "CreatedAt" in out.columns
            assert str(out["RunID"].iloc[0]) == "r-meta-integrated"
            assert int(out["EquipID"].iloc[0]) == 777
            assert pd.notna(out["CreatedAt"].iloc[0])

    def test_write_sql_table_derives_replace_policy_from_contract(self):
        """write_sql_table should route replace-mode tables through contract-derived key semantics."""
        from core.output_manager import OutputManager

        output_manager = OutputManager(
            sql_client=None,
            run_id="r-contract",
            equip_id=44,
            enable_batching=False,
        )
        captured = {}
        output_manager._replace_by_keys = (
            lambda table_name, payload, keys: captured.update(
                {"table": table_name, "keys": list(keys), "rows": len(payload)}
            ) or len(payload)
        )

        df = pd.DataFrame(
            {
                "RunID": ["r-contract"],
                "EquipID": [44],
                "Timestamp": [datetime.now()],
                "ForecastHealth": [95.0],
            }
        )
        result = output_manager.write_sql_table(
            table_name="ACM_HealthForecast",
            df=df,
            artifact_name="health_fcst",
        )
        assert result["inserted"] == 1
        assert captured["table"] == "ACM_HealthForecast"
        assert captured["keys"] == ["RunID", "EquipID", "Timestamp"]

    def test_write_dataframe_sql_requires_explicit_policy(self):
        """Low-level write_dataframe SQL path should require explicit policy declaration."""
        from core.output_manager import OutputManager

        output_manager = OutputManager(
            sql_client=None,
            run_id="r-policy-enforced",
            equip_id=1,
            enable_batching=False,
        )
        result = output_manager.write_dataframe(
            pd.DataFrame({"Timestamp": [datetime.now()], "v": [1.0]}),
            artifact_name="no-policy",
            sql_table="ACM_Scores_Wide",
        )
        assert result["sql_written"] is False
        assert "requires explicit write_policy" in str(result.get("error", ""))

    def test_write_sql_table_unknown_table_falls_back_with_error_result(self):
        """Unknown/non-contracted tables should return a non-written result with explicit contract error."""
        from core.output_manager import OutputManager

        output_manager = OutputManager(
            sql_client=None,
            run_id="r-unknown",
            equip_id=1,
            enable_batching=False,
        )
        df = pd.DataFrame({"x": [1.0]})
        result = output_manager.write_sql_table(
            table_name="ACM_UnknownTable",
            df=df,
            artifact_name="unknown",
        )
        assert result["sql_written"] is False
        assert result["inserted"] == 0
        assert "no write contract" in str(result.get("error", "")).lower()

    def test_persist_episode_rows_uses_write_dataframe_pipeline(self):
        """Episode row persistence should route through write_dataframe and include metadata columns."""
        from core.output_manager import OutputManager

        output_manager = OutputManager(
            sql_client=None,
            run_id="r-episodes",
            equip_id=12,
            enable_batching=False,
        )
        captured = {}

        def _capture_bulk_insert(table, frame):
            captured[table] = frame.copy()
            return len(frame)

        output_manager._bulk_insert_sql = _capture_bulk_insert
        episodes = pd.DataFrame(
            [
                {
                    "episode_id": 5,
                    "start_ts": pd.Timestamp("2026-01-01T00:00:00"),
                    "duration_s": 3600.0,
                    "culprits": "A -> B",
                    "dominant_sensor": "A",
                    "severity": "HIGH",
                }
            ]
        )
        inserted = output_manager._persist_episode_rows(episodes)
        assert inserted == 1
        assert "ACM_Episodes" in captured
        out = captured["ACM_Episodes"]
        assert "RunID" in out.columns
        assert "EquipID" in out.columns
        assert "CreatedAt" in out.columns
        assert str(out.loc[0, "RunID"]) == "r-episodes"
        assert int(out.loc[0, "EquipID"]) == 12

    def test_normalize_episodes_sanitizes_invalid_episode_ids(self):
        """Episode normalization should coerce invalid episode_id values to stable sequential fallbacks."""
        from core.output_manager import OutputManager

        output_manager = OutputManager(
            sql_client=None,
            run_id="r-episodes",
            equip_id=12,
            enable_batching=False,
        )
        episodes = pd.DataFrame(
            {
                "episode_id": [np.nan, "bad", 7.0, -1, 3.5],
                "start_ts": pd.to_datetime(
                    [
                        "2026-01-01 00:00:00",
                        "2026-01-01 01:00:00",
                        "2026-01-01 02:00:00",
                        "2026-01-01 03:00:00",
                        "2026-01-01 04:00:00",
                    ]
                ),
            }
        )

        normalized, repairs = output_manager._normalize_episodes_for_diagnostics(episodes)
        assert normalized["episode_id"].tolist() == [1, 2, 7, 4, 5]
        assert any(r.startswith("episode_id_sanitized:") for r in repairs)

    def test_normalize_active_models_payload_sanitizes_fields(self):
        """Active model payload should normalize maturity and numeric version fields."""
        from core.output_manager import OutputManager

        output_manager = OutputManager(
            sql_client=None,
            run_id="r-active",
            equip_id=8,
            enable_batching=False,
        )
        df = output_manager._normalize_active_models_payload(
            {
                "RegimeMaturityState": "MaturityState.learning",
                "ActiveRegimeVersion": "12",
                "ActiveThresholdVersion": "bad",
                "ActiveForecastVersion": 14.0,
            }
        )
        assert df is not None
        assert int(df.loc[0, "EquipID"]) == 8
        assert str(df.loc[0, "RegimeMaturityState"]) == "LEARNING"
        assert int(df.loc[0, "ActiveRegimeVersion"]) == 12
        assert pd.isna(df.loc[0, "ActiveThresholdVersion"])
        assert int(df.loc[0, "ActiveForecastVersion"]) == 14
        assert str(df.loc[0, "LastUpdatedBy"]) == "r-active"

    def test_normalize_active_models_payload_rejects_invalid_equip_id(self):
        """Active model payload normalization should reject missing/non-positive EquipID."""
        from core.output_manager import OutputManager

        output_manager = OutputManager(
            sql_client=None,
            run_id="r-active",
            equip_id=None,
            enable_batching=False,
        )
        assert output_manager._normalize_active_models_payload({"ActiveRegimeVersion": 1}) is None
        assert output_manager._normalize_active_models_payload({"EquipID": 0, "ActiveRegimeVersion": 1}) is None

    def test_write_threshold_metadata_routes_to_contract_writer(self):
        """Threshold metadata writer should use contract-based write_sql_table path."""
        from core.output_manager import OutputManager

        output_manager = OutputManager.__new__(OutputManager)
        output_manager.sql_client = object()
        output_manager.equip_id = 12
        output_manager.run_id = "r-th"
        captured = {}
        output_manager.write_sql_table = lambda **kwargs: captured.update(kwargs) or {"inserted": 1}

        inserted = output_manager.write_threshold_metadata(
            equip_id=12,
            threshold_type="fused_alert_z",
            threshold_value=3.2,
            calculation_method="quantile",
            sample_count=500,
        )

        assert inserted == 1
        assert captured["table_name"] == "ACM_AdaptiveConfig"
        assert "ConfigKey" in captured["df"].columns
        assert "ConfigValue" in captured["df"].columns

    def test_write_refit_request_routes_to_contract_writer(self):
        """Refit request writer should use contract-based write_sql_table path."""
        from core.output_manager import OutputManager

        output_manager = OutputManager.__new__(OutputManager)
        output_manager.sql_client = object()
        output_manager.equip_id = 7
        output_manager.run_id = "r-refit"
        captured = {}
        output_manager.write_sql_table = lambda **kwargs: captured.update(kwargs) or {"inserted": 1}

        inserted = output_manager.write_refit_request(
            reasons=["drift rising", "anomaly burst"],
            anomaly_rate=0.2,
            drift_score=3.1,
            regime_quality=0.4,
        )

        assert inserted == 1
        assert captured["table_name"] == "ACM_RefitRequests"
        assert "Reason" in captured["df"].columns
        assert "AnomalyRate" in captured["df"].columns
        assert "DriftScore" in captured["df"].columns
        assert "RegimeQuality" in captured["df"].columns

    def test_write_fusion_metrics_routes_to_contract_writer(self):
        """Fusion metrics writer should emit EAV rows via write_sql_table."""
        from core.output_manager import OutputManager

        output_manager = OutputManager.__new__(OutputManager)
        output_manager.sql_client = object()
        output_manager.equip_id = 9
        output_manager.run_id = "r-fusion"
        output_manager.equipment = "FD_FAN"
        captured = {}
        output_manager.write_sql_table = lambda **kwargs: captured.update(kwargs) or {"inserted": len(kwargs["df"])}

        inserted = output_manager.write_fusion_metrics(
            fusion_weights={"ar1_z": 0.6, "iforest_z": 0.4},
            tuning_diagnostics={
                "method": "meta_learner",
                "detector_metrics": {
                    "ar1_z": {"n_samples": 10, "quality_score": 0.8},
                    "iforest_z": {"n_samples": 10, "quality_score": 0.7},
                },
            },
            previous_weights=None,
        )

        assert inserted == 6
        assert captured["table_name"] == "ACM_RunMetrics"
        assert set(["MetricName", "MetricValue"]).issubset(set(captured["df"].columns))

    def test_write_feature_drop_log_routes_to_contract_writer(self):
        """Feature-drop writer should use contract-based write_sql_table path."""
        from core.output_manager import OutputManager

        output_manager = OutputManager.__new__(OutputManager)
        output_manager.sql_client = object()
        output_manager.equip_id = 9
        output_manager.run_id = "r-feature-drop"
        captured = {}
        output_manager.write_sql_table = lambda **kwargs: captured.update(kwargs) or {"inserted": 2}

        inserted = output_manager.write_feature_drop_log(
            [
                {"FeatureName": "S01", "DropReason": "low_variance", "DropValue": 0.0, "Threshold": 1e-6},
                {"FeatureName": "S02", "DropReason": "missingness", "DropValue": 0.95, "Threshold": 0.90},
            ]
        )

        assert inserted == 2
        assert captured["table_name"] == "ACM_FeatureDropLog"
        assert set(["RunID", "EquipID", "FeatureName", "DropReason"]).issubset(set(captured["df"].columns))

    def test_write_regime_transitions_routes_to_contract_writer(self):
        """Regime transition writer should emit rows via write_sql_table."""
        from core.output_manager import OutputManager

        output_manager = OutputManager.__new__(OutputManager)
        output_manager.sql_client = object()
        output_manager.equip_id = 4
        output_manager.run_id = "r-regime-trans"
        captured = {}
        output_manager.write_sql_table = lambda **kwargs: captured.update(kwargs) or {"inserted": len(kwargs["df"])}

        inserted = output_manager.write_regime_transitions({"0": {"0": 8, "1": 2}, "1": {"1": 5}})

        assert inserted == 3
        assert captured["table_name"] == "ACM_RegimeTransitions"
        assert set(["FromRegime", "ToRegime", "TransitionCount", "TransitionProbability"]).issubset(
            set(captured["df"].columns)
        )
        probs = captured["df"].set_index(["FromRegime", "ToRegime"])["TransitionProbability"].to_dict()
        assert probs[("0", "0")] == 0.8
        assert probs[("0", "1")] == 0.2
        assert probs[("1", "1")] == 1.0

    def test_write_active_models_routes_to_contract_writer(self):
        """Active-model writer should use contract-based write_sql_table path."""
        from core.output_manager import OutputManager

        output_manager = OutputManager.__new__(OutputManager)
        output_manager.sql_client = object()
        output_manager.equip_id = 31
        output_manager.run_id = "r-active-models"
        output_manager.maturity_state = "LEARNING"
        captured = {}
        output_manager.write_sql_table = lambda **kwargs: captured.update(kwargs) or {"inserted": 1}

        inserted = output_manager.write_active_models(
            {
                "ActiveRegimeVersion": "2",
                "ActiveThresholdVersion": 5,
                "ActiveForecastVersion": "7",
                "RegimeMaturityState": "MaturityState.converged",
            }
        )

        assert inserted == 1
        assert captured["table_name"] == "ACM_ActiveModels"
        out = captured["df"]
        assert int(out.loc[0, "EquipID"]) == 31
        assert str(out.loc[0, "RegimeMaturityState"]) == "CONVERGED"
        assert int(out.loc[0, "ActiveRegimeVersion"]) == 2

    def test_write_seasonal_patterns_routes_to_contract_writer(self):
        """Seasonal-pattern writer should use contract-based write_sql_table path."""
        from core.output_manager import OutputManager

        output_manager = OutputManager.__new__(OutputManager)
        output_manager.sql_client = object()
        output_manager.equip_id = 12
        output_manager.run_id = "r-seasonal"
        captured = {}
        output_manager.write_sql_table = lambda **kwargs: captured.update(kwargs) or {"inserted": len(kwargs["df"])}

        inserted = output_manager.write_seasonal_patterns(
            [
                {"SensorName": "S1", "PatternType": "DAILY", "PeriodHours": 24.0, "Amplitude": 0.6},
                {"SensorName": "S2", "PatternType": "WEEKLY", "PeriodHours": 168.0, "Amplitude": 0.3},
            ]
        )

        assert inserted == 2
        assert captured["table_name"] == "ACM_SeasonalPatterns"
        assert set(["RunID", "EquipID", "DetectedAt", "SensorName"]).issubset(set(captured["df"].columns))

    def test_replace_policy_contract_covers_standardized_optional_writers(self):
        """Contract map should own replace semantics for standardized optional writers."""
        from core.output_contracts import TABLE_WRITE_CONTRACTS

        tables = [
            "ACM_Anomaly_Events",
            "ACM_Regime_Episodes",
            "ACM_PCA_Models",
            "ACM_DetectorCorrelation",
            "ACM_DriftSeries",
            "ACM_DriftController",
            "ACM_DataContractValidation",
            "ACM_SeasonalPatterns",
            "ACM_FeatureDropLog",
            "ACM_CalibrationSummary",
            "ACM_RegimeOccupancy",
            "ACM_RegimeTransitions",
            "ACM_ContributionTimeline",
        ]
        for table_name in tables:
            contract = TABLE_WRITE_CONTRACTS[table_name]
            assert contract.mode == "replace"
            assert tuple(contract.key_columns) == ("RunID", "EquipID")

    def test_regime_conditioned_estimate_excludes_legacy_hazard_payload(self, monkeypatch):
        """Regime-conditioned estimate should not emit legacy ACM_RegimeHazard payload keys."""
        from core import forecast_engine as fe

        class _FakeRul:
            def __init__(self, p50):
                self.p10_lower_bound = p50 - 2.0
                self.p50_median = p50
                self.p90_upper_bound = p50 + 2.0
                self.confidence_level = 0.9

        class _FakeEstimator:
            def __init__(self, **kwargs):
                _ = kwargs

            def estimate_rul(self, current_health, dt_hours, max_horizon_hours):
                _ = (current_health, dt_hours, max_horizon_hours)
                return _FakeRul(24.0)

        monkeypatch.setattr(fe, "RULEstimator", _FakeEstimator)

        forecaster = fe.RegimeConditionedForecaster(
            sql_client=None,
            output_manager=None,
            equip_id=1,
            run_id="r-test",
            config={"failure_threshold": 70.0},
        )
        forecaster.compute_regime_stats = lambda lookback_days=90: {
            1: fe.RegimeStats(
                regime_label=1,
                health_state="healthy",
                degradation_rate=0.2,
                degradation_rate_lower=0.1,
                degradation_rate_upper=0.3,
                degradation_r_squared=0.8,
                health_mean=85.0,
                health_std=3.0,
                dwell_fraction=0.6,
                transition_count=3,
                failure_threshold=70.0,
                sample_count=120,
            )
        }

        out = forecaster.estimate_rul_by_regime(
            current_health=88.0,
            degradation_model=object(),
            current_regime=1,
            forecast_config={"dt_hours": 1.0, "max_forecast_hours": 48.0},
        )

        assert "rul_global" in out
        assert "rul_by_regime" in out
        assert "rul_conditioned" in out
        assert "regime_hazards" not in out

    def test_generate_all_analytics_with_context_injects_fusion_weights(self):
        """Analytics helper should inject fusion weights and delegate to analytics writer."""
        from core.output_manager import OutputManager

        output_manager = OutputManager.__new__(OutputManager)
        captured = {}

        def _fake_generate(scores_df, cfg, sensor_context):
            captured["scores_df"] = scores_df
            captured["cfg"] = cfg
            captured["sensor_context"] = sensor_context
            return {"sql_tables": 7}

        output_manager.generate_all_analytics_tables = _fake_generate

        scores_df = pd.DataFrame({"fused": [0.1, 0.2]})
        cfg = {}
        sensor_context = {"values": pd.DataFrame({"sensor": [1.0]})}
        result = output_manager.generate_all_analytics_with_context(
            scores_df=scores_df,
            cfg=cfg,
            sensor_context=sensor_context,
            fusion_weights_used={"ar1_z": 0.6, "iforest_z": 0.4},
        )

        assert result["sql_tables"] == 7
        assert "fusion" in cfg
        assert cfg["fusion"]["weights"]["ar1_z"] == pytest.approx(0.6)
        assert captured["scores_df"] is scores_df
        assert captured["cfg"] is cfg
        assert captured["sensor_context"] is sensor_context

    def test_persist_pipeline_outputs_orchestrates_writes_and_cleanup(self):
        """Persist pipeline helper should orchestrate writes, analytics, and memory cleanup."""
        from core.output_manager import OutputManager, PersistCoreOutputsResult

        output_manager = OutputManager.__new__(OutputManager)
        output_manager.persist_core_outputs = lambda scores_df, episodes_df: PersistCoreOutputsResult(
            scores_inserted=5,
            episodes_inserted=2,
            episode_count=3,
        )
        output_manager.persist_additional_artifacts = (
            lambda scores_df, raw_score, seasonal_patterns, max_total_rows=10000: None
        )
        output_manager.release_persist_memory = (
            lambda raw_train, raw_score, iforest_detector=None, omr_detector=None: (None, None)
        )
        output_manager.generate_all_analytics_with_context = (
            lambda scores_df, cfg, sensor_context, fusion_weights_used=None: {"sql_tables": 9}
        )

        record_calls = []

        def _record_episode(equip, count, severity):
            record_calls.append((equip, count, severity))

        scores_df = pd.DataFrame({"fused": [0.1, 0.2]})
        episodes_df = pd.DataFrame({"episode_id": [1, 2, 3]})
        result = output_manager.persist_pipeline_outputs(
            scores_df=scores_df,
            episodes_df=episodes_df,
            raw_train=pd.DataFrame({"sensor": [1.0]}),
            raw_score=pd.DataFrame({"sensor": [1.1]}),
            iforest_detector=object(),
            omr_detector=object(),
            seasonal_patterns={},
            cfg={},
            sensor_context={"k": "v"},
            fusion_weights_used={"ar1_z": 0.7},
            record_episode_fn=_record_episode,
            equip="FD_FAN",
        )

        assert result.rows_written_delta == 7
        assert result.episode_count == 3
        assert result.analytics_table_count == 9
        assert result.raw_train is None
        assert result.raw_score is None
        assert result.sensor_context is None
        assert record_calls == [("FD_FAN", 3, "info")]

    def test_persist_pipeline_outputs_skips_score_derived_outputs_when_scores_are_suppressed(self):
        """Score-suppressed frames should not persist score-derived tables or analytics."""
        from core.output_manager import OutputManager, PersistCoreOutputsResult

        output_manager = OutputManager.__new__(OutputManager)
        output_manager.equip_id = 5010
        output_manager.run_id = "run-1"
        captured = {
            "scores_rows": None,
            "episodes_rows": None,
            "analytics_called": False,
            "contribution_called": False,
            "additional_rows": None,
        }

        def _persist_core_outputs(scores_df, episodes_df):
            captured["scores_rows"] = len(scores_df)
            captured["episodes_rows"] = len(episodes_df)
            return PersistCoreOutputsResult(
                scores_inserted=0,
                episodes_inserted=0,
                episode_count=0,
            )

        output_manager.persist_core_outputs = _persist_core_outputs
        output_manager.write_contribution_timeline_from_frame = (
            lambda **kwargs: captured.__setitem__("contribution_called", True)
        )
        output_manager.persist_additional_artifacts = (
            lambda scores_df, raw_score, seasonal_patterns, max_total_rows=10000:
            captured.__setitem__("additional_rows", len(scores_df))
        )
        output_manager.release_persist_memory = (
            lambda raw_train, raw_score, iforest_detector=None, omr_detector=None: (None, None)
        )
        output_manager.generate_all_analytics_with_context = (
            lambda **kwargs: captured.__setitem__("analytics_called", True)
        )

        scores_df = pd.DataFrame(
            {
                "fused": [np.nan, np.nan],
                "ar1_z": [np.nan, np.nan],
                "regime_label": ["R1", "R1"],
            }
        )
        episodes_df = pd.DataFrame({"episode_id": [1, 2]})
        result = output_manager.persist_pipeline_outputs(
            scores_df=scores_df,
            episodes_df=episodes_df,
            raw_train=pd.DataFrame({"sensor": [1.0]}),
            raw_score=pd.DataFrame({"sensor": [1.1]}),
            iforest_detector=object(),
            omr_detector=object(),
            seasonal_patterns={},
            cfg={},
            sensor_context={"k": "v"},
            fusion_weights_used={"ar1_z": 0.7},
            record_episode_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("record_episode_fn should not run")),
            equip="FD_FAN",
        )

        assert result.rows_written_delta == 0
        assert result.episode_count == 0
        assert result.analytics_table_count == 0
        assert captured["scores_rows"] == 0
        assert captured["episodes_rows"] == 0
        assert captured["contribution_called"] is False
        assert captured["analytics_called"] is False
        assert captured["additional_rows"] == 0

    def test_run_persistence_stage_orchestrates_pipeline_outputs_and_sql_artifacts(self, monkeypatch):
        """Output manager persistence stage should run pipeline outputs and SQL artifact writes in order."""
        from core import output_manager as om_module
        from core.output_manager import OutputManager, PersistPipelineOutputsResult

        out = OutputManager.__new__(OutputManager)
        calls = {"sections": [], "pipeline": False, "sql": False}

        class _Section:
            def __init__(self, name):
                self.name = name
            def __enter__(self):
                calls["sections"].append(self.name)
                return self
            def __exit__(self, exc_type, exc, tb):
                return False

        def _section_fn(name):
            return _Section(name)

        class _Txn:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False

        out.batched_transaction = lambda: _Txn()
        out.persist_pipeline_outputs = lambda **kwargs: PersistPipelineOutputsResult(
            rows_written_delta=9,
            episode_count=2,
            analytics_table_count=11,
            raw_train=None,
            raw_score=None,
            sensor_context=None,
        )
        def _fake_write_sql_artifacts(**kwargs):
            calls["sql"] = True
            return 88
        monkeypatch.setattr(om_module, "write_sql_artifacts", _fake_write_sql_artifacts)

        class _Logger:
            def info(self, *args, **kwargs):
                pass

        frame = pd.DataFrame({"fused": [0.1, 0.2]})
        episodes = pd.DataFrame({"episode_id": [1, 2]})
        train = pd.DataFrame({"sensor": [1.0, 2.0]})

        result = out.run_persistence_stage(
            section_fn=_section_fn,
            logger=_Logger(),
            scores_df=frame,
            episodes_df=episodes,
            train_df=train,
            raw_train=train,
            raw_score=train.copy(),
            iforest_detector=None,
            omr_detector=None,
            seasonal_patterns={},
            cfg={},
            sensor_context={},
            fusion_weights_used={"ar1_z": 1.0},
            record_episode_fn=None,
            equip="FD_FAN",
            pca_detector=None,
            sql_client=object(),
            run_id="r1",
            equip_id=1,
            meta={},
            win_start=pd.Timestamp("2026-01-01T00:00:00"),
            win_end=pd.Timestamp("2026-01-01T01:00:00"),
            rows_read=2,
            spe_p95_train=0.1,
            t2_p95_train=0.2,
            anomaly_count=2,
            timer=object(),
            culprit_writer_func=None,
        )

        assert result.rows_written == 97
        assert result.analytics_table_count == 11
        assert calls["sql"] is True
        assert calls["sections"] == ["persist", "persist.pipeline_outputs"]

    def test_prepare_persistence_inputs_updates_baseline_and_builds_sensor_context(self):
        """Persistence input preparation should update baseline buffer and build sensor context."""
        from core.output_manager import OutputManager

        out = OutputManager.__new__(OutputManager)
        calls = {"sections": [], "baseline": False, "sensor": False}

        class _Section:
            def __init__(self, name):
                self.name = name
            def __enter__(self):
                calls["sections"].append(self.name)
                return self
            def __exit__(self, exc_type, exc, tb):
                return False

        def _section_fn(name):
            return _Section(name)

        def _update_baseline_buffer(**kwargs):
            calls["baseline"] = True

        def _build_sensor_context(**kwargs):
            calls["sensor"] = True
            return {"ctx": 1}

        out.update_baseline_buffer = _update_baseline_buffer

        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        raw_train = pd.DataFrame({"a": [1.0, 2.0]}, index=idx)
        raw_score = pd.DataFrame({"a": [1.5, 2.5]}, index=idx)
        frame = pd.DataFrame({"fused": [0.1, 0.2]}, index=idx)

        result = out.prepare_persistence_inputs(
            section_fn=_section_fn,
            raw_train=raw_train,
            raw_score=raw_score,
            frame=frame,
            omr_contributions_data=None,
            regime_model=None,
            cfg={},
            coldstart_complete=True,
            build_sensor_analytics_context_fn=_build_sensor_context,
            logger=type("L", (), {"warn": lambda *a, **k: None})(),
            equip="FD_FAN",
        )

        assert result.sensor_context == {"ctx": 1}
        assert calls["baseline"] is True
        assert calls["sensor"] is True
        assert calls["sections"] == ["baseline.buffer_write", "sensor.context"]

    def test_prepare_persistence_inputs_skips_baseline_buffer_when_representation_blocks_learning(self):
        """Persistence input preparation should not mutate the baseline buffer when learning is blocked."""
        from core.output_manager import OutputManager
        from core.representation_contracts import EligibilityDecision

        out = OutputManager.__new__(OutputManager)
        out.equip_id = 5010
        out.run_id = "run-1"
        calls = {"sections": [], "baseline": False, "sensor": False}

        class _Section:
            def __init__(self, name):
                self.name = name

            def __enter__(self):
                calls["sections"].append(self.name)
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def _section_fn(name):
            return _Section(name)

        def _update_baseline_buffer(**kwargs):
            calls["baseline"] = True

        def _build_sensor_context(**kwargs):
            calls["sensor"] = True
            return {"ctx": 1}

        out.update_baseline_buffer = _update_baseline_buffer

        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        raw_train = pd.DataFrame({"a": [1.0, 2.0]}, index=idx)
        raw_score = pd.DataFrame({"a": [1.5, 2.5]}, index=idx)
        frame = pd.DataFrame({"fused": [float("nan"), float("nan")]}, index=idx)

        result = out.prepare_persistence_inputs(
            section_fn=_section_fn,
            raw_train=raw_train,
            raw_score=raw_score,
            frame=frame,
            omr_contributions_data=None,
            regime_model=None,
            cfg={},
            coldstart_complete=True,
            build_sensor_analytics_context_fn=_build_sensor_context,
            logger=type("L", (), {"warn": lambda *a, **k: None, "info": lambda *a, **k: None})(),
            equip="FD_FAN",
            representation_result=type(
                "RepresentationResult",
                (),
                {
                    "authoritative": True,
                    "eligibility": EligibilityDecision(
                        authoritative=True,
                        score_allowed=False,
                        learn_allowed=False,
                        suppressed_reason_codes=("context_unknown",),
                    ),
                },
            )(),
            representation_authority_active=True,
        )

        assert result.sensor_context == {"ctx": 1}
        assert calls["baseline"] is False
        assert calls["sensor"] is True
        assert calls["sections"] == ["baseline.buffer_write", "sensor.context"]

    def test_resolve_run_outcome_from_degradations(self):
        """Run metadata helper should map degradation list to DEGRADED outcome and payload."""
        from core.run_metadata_writer import resolve_run_outcome_from_degradations

        outcome, err_json = resolve_run_outcome_from_degradations(["regime_feature_basis"])
        assert outcome == "DEGRADED"
        assert isinstance(err_json, str)
        assert "degraded_steps" in err_json

        outcome_ok, err_json_ok = resolve_run_outcome_from_degradations([])
        assert outcome_ok == "OK"
        assert err_json_ok is None

    def test_serialize_run_exception_returns_json(self):
        """Run metadata helper should serialize exceptions into stable JSON payload."""
        from core.run_metadata_writer import serialize_run_exception

        payload = serialize_run_exception(RuntimeError("boom"))
        assert isinstance(payload, str)
        assert "RuntimeError" in payload
        assert "boom" in payload

    def test_finalize_noop_run_calls_sql_finalize(self):
        """NOOP finalization helper should write fixed NOOP status payload."""
        from core.run_metadata_writer import finalize_noop_run

        class _SQL:
            def __init__(self):
                self.calls = []

            def finalize_run(self, **kwargs):
                self.calls.append(kwargs)

        sql = _SQL()
        finalize_noop_run(sql_client=sql, run_id="r1")

        assert len(sql.calls) == 1
        assert sql.calls[0]["run_id"] == "r1"
        assert sql.calls[0]["outcome"] == "NOOP"
        assert sql.calls[0]["rows_read"] == 0
        assert sql.calls[0]["rows_written"] == 0

    def test_finalize_noop_run_writes_zero_day_status_when_provided(self, monkeypatch):
        """NOOP helper should persist day-0 status before final SQL finalization."""
        from core import run_metadata_writer as rmw

        class _SQL:
            def __init__(self):
                self.calls = []

            def finalize_run(self, **kwargs):
                self.calls.append(kwargs)

        captured = {}

        def _capture(**kwargs):
            captured.update(kwargs)
            return True

        monkeypatch.setattr(rmw, "write_zero_day_run_status", _capture)

        sql = _SQL()
        status = rmw.build_zero_day_run_status(
            scoring_active=False,
            status="inactive_no_data",
        )
        rmw.finalize_noop_run(
            sql_client=sql,
            run_id="r1",
            zero_day_status=status,
            equip_id=5010,
        )

        assert captured["run_id"] == "r1"
        assert captured["zero_day_status"].status == "inactive_no_data"
        assert captured["equip_id"] == 5010
        assert sql.calls[0]["outcome"] == "NOOP"

    def test_finalize_noop_run_skips_without_run_id(self):
        """NOOP finalization helper should no-op when run_id is missing."""
        from core.run_metadata_writer import finalize_noop_run

        class _SQL:
            def __init__(self):
                self.calls = 0

            def finalize_run(self, **kwargs):
                self.calls += 1

        sql = _SQL()
        finalize_noop_run(sql_client=sql, run_id=None)
        assert sql.calls == 0

    def test_finalize_pipeline_teardown_orchestrates_summary_finalize_and_observability(self, monkeypatch):
        """Teardown helper should call summary, SQL finalization, span close, and observability shutdown."""
        from core import run_metadata_writer as rmw

        calls = []

        monkeypatch.setattr(rmw, "emit_batch_summary", lambda **kwargs: calls.append("summary"))
        monkeypatch.setattr(rmw, "finalize_run_with_metadata", lambda **kwargs: calls.append("finalize"))

        def _close_run_span_fn(**kwargs):
            calls.append("close_span")

        def _shutdown_run_observability_fn(enabled):
            calls.append(("shutdown", bool(enabled)))

        rmw.finalize_pipeline_teardown(
            rmw.PipelineTeardownState(
                console=type("L", (), {"info": lambda *a, **k: None})(),
                equip="FD_FAN",
                run_id="r1",
                win_start=None,
                win_end=None,
                outcome="OK",
                frame=None,
                episodes=None,
                score_out=None,
                regime_quality_ok=True,
                model_state=None,
                rows_read=10,
                train=None,
                degradations=[],
                refit_requested=False,
                timer=None,
                sql_client=object(),
                output_manager=None,
                equip_id=1,
                equip_name="FD_FAN",
                started_at=datetime.now(),
                rows_written=5,
                err_json=None,
                meta=None,
                config_signature="sig",
                per_regime_enabled=False,
                regime_count=0,
                observability_enabled=True,
                record_data_quality_fn=None,
                record_run_fn=None,
                record_batch_processed_fn=None,
                record_health_score_fn=None,
                record_error_fn=None,
                zero_day_status=None,
                representation_status=None,
                span_ctx=None,
                root_span=None,
                close_run_span_fn=_close_run_span_fn,
                shutdown_run_observability_fn=_shutdown_run_observability_fn,
            )
        )

        assert calls[0] == "summary"
        assert calls[1] == "finalize"
        assert calls[2] == "close_span"
        assert calls[3] == ("shutdown", True)

    def test_write_run_metadata_includes_zero_day_fields_when_columns_exist(self, monkeypatch):
        """ACM_Runs metadata write should persist explicit day-0 status when migration 017 exists."""
        from core import run_metadata_writer as rmw

        class _Cursor:
            def __init__(self, conn):
                self.conn = conn

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, query, params):
                self.conn.query = query
                self.conn.params = params

        class _Conn:
            def __init__(self):
                self.query = None
                self.params = None
                self.commits = 0

            def cursor(self):
                return _Cursor(self)

            def commit(self):
                self.commits += 1

            def rollback(self):
                pass

        sql_client = type("SQL", (), {"conn": _Conn(), "cursor": lambda self=None: sql_client.conn.cursor()})()
        monkeypatch.setattr(rmw, "_acm_runs_has_zero_day_columns", lambda sql_client: True)

        ok = rmw.write_run_metadata(
            sql_client=sql_client,
            run_id="r1",
            equip_id=5010,
            equip_name="WFA_TURBINE_10",
            started_at=datetime(2026, 3, 9, 10, 0, 0),
            completed_at=datetime(2026, 3, 9, 10, 5, 0),
            config_signature="sig",
            train_row_count=100,
            score_row_count=50,
            episode_count=2,
            health_status="ALERT",
            avg_health_index=25.0,
            min_health_index=10.0,
            max_fused_z=6.5,
            data_quality_score=99.0,
            refit_requested=False,
            kept_columns="sensor_1_avg,sensor_2_avg",
            error_message=None,
            zero_day_status=rmw.build_zero_day_run_status(
                scoring_active=True,
                status="active_hdbscan",
                surface_type="ewm_monitoring_raw_numeric",
                channel_count=17,
            ),
        )

        assert ok is True
        assert "ZeroDayStatus" in sql_client.conn.query
        assert "ZeroDayChannelCount" in sql_client.conn.query
        assert "active_hdbscan" in sql_client.conn.params
        assert "ewm_monitoring_raw_numeric" in sql_client.conn.params
        assert 17 in sql_client.conn.params
        assert sql_client.conn.commits == 1

    def test_write_run_metadata_includes_representation_fields_when_columns_exist(self, monkeypatch):
        """ACM_Runs metadata write should persist representation summary when migration 022 exists."""
        from core import run_metadata_writer as rmw

        class _Cursor:
            def __init__(self, conn):
                self.conn = conn

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, query, params):
                self.conn.query = query
                self.conn.params = params

        class _Conn:
            def __init__(self):
                self.query = None
                self.params = None
                self.commits = 0

            def cursor(self):
                return _Cursor(self)

            def commit(self):
                self.commits += 1

            def rollback(self):
                pass

        sql_client = type("SQL", (), {"conn": _Conn(), "cursor": lambda self=None: sql_client.conn.cursor()})()
        monkeypatch.setattr(rmw, "_acm_runs_has_zero_day_columns", lambda sql_client: False)
        monkeypatch.setattr(rmw, "_acm_runs_has_representation_columns", lambda sql_client: True)

        ok = rmw.write_run_metadata(
            sql_client=sql_client,
            run_id="r1",
            equip_id=5010,
            equip_name="WFA_TURBINE_10",
            started_at=datetime(2026, 3, 9, 10, 0, 0),
            completed_at=datetime(2026, 3, 9, 10, 5, 0),
            config_signature="sig",
            train_row_count=100,
            score_row_count=50,
            episode_count=2,
            health_status="DEGRADED",
            avg_health_index=25.0,
            min_health_index=10.0,
            max_fused_z=6.5,
            data_quality_score=99.0,
            refit_requested=False,
            kept_columns="sensor_1_avg,sensor_2_avg",
            error_message='{"degraded_steps":["score_suppressed"]}',
            representation_status=rmw.RepresentationRunStatus(
                authoritative=True,
                score_allowed=False,
                learn_allowed=False,
                context_label="unknown",
                runtime_mode="ONLINE_SCORING",
                schema_compatibility="COMPATIBLE",
                basis_compatibility="PENDING_REQUALIFICATION",
                baseline_compatibility="BLOCKED",
                suppressed_reasons_json='["comparability_failed"]',
                degraded_reasons_json='["schema_drift"]',
            ),
        )

        assert ok is True
        assert "RepresentationAuthoritative" in sql_client.conn.query
        assert "RepresentationScoreAllowed" in sql_client.conn.query
        assert "RepresentationSuppressedReasons" in sql_client.conn.query
        assert "ONLINE_SCORING" in sql_client.conn.params
        assert "PENDING_REQUALIFICATION" in sql_client.conn.params
        assert '["comparability_failed"]' in sql_client.conn.params
        assert '["schema_drift"]' in sql_client.conn.params
        assert sql_client.conn.commits == 1

    def test_write_run_metadata_sanitizes_nan_float_fields(self, monkeypatch):
        """ACM_Runs writes should convert NaN float metrics into NULL-safe parameters."""
        from core import run_metadata_writer as rmw

        class _Cursor:
            def __init__(self, conn):
                self.conn = conn

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, query, params):
                self.conn.query = query
                self.conn.params = params

        class _Conn:
            def __init__(self):
                self.query = None
                self.params = None
                self.commits = 0

            def cursor(self):
                return _Cursor(self)

            def commit(self):
                self.commits += 1

            def rollback(self):
                pass

        sql_client = type("SQL", (), {"conn": _Conn(), "cursor": lambda self=None: sql_client.conn.cursor()})()
        monkeypatch.setattr(rmw, "_acm_runs_has_zero_day_columns", lambda sql_client: False)
        monkeypatch.setattr(rmw, "_acm_runs_has_representation_columns", lambda sql_client: False)

        ok = rmw.write_run_metadata(
            sql_client=sql_client,
            run_id="r1",
            equip_id=5010,
            equip_name="WFA_TURBINE_10",
            started_at=datetime(2026, 3, 9, 10, 0, 0),
            completed_at=datetime(2026, 3, 9, 10, 5, 0),
            config_signature="sig",
            train_row_count=100,
            score_row_count=50,
            episode_count=0,
            health_status="UNKNOWN",
            avg_health_index=np.nan,
            min_health_index=np.inf,
            max_fused_z=-np.inf,
            data_quality_score=np.nan,
            refit_requested=False,
            kept_columns="sensor_1_avg,sensor_2_avg",
            error_message=None,
        )

        assert ok is True
        assert sql_client.conn.params[7] is None
        assert sql_client.conn.params[8] is None
        assert sql_client.conn.params[9] is None
        assert sql_client.conn.params[10] is None
        assert sql_client.conn.commits == 1

    def test_extract_run_metadata_from_scores_returns_unknown_when_fused_scores_are_nan(self):
        """Run metadata extraction should degrade cleanly when all fused scores are NaN."""
        from core import run_metadata_writer as rmw

        scores = pd.DataFrame(
            {
                "fused": [np.nan, np.nan],
                "__health": [np.nan, np.nan],
            }
        )

        metadata = rmw.extract_run_metadata_from_scores(scores)

        assert metadata["health_status"] == "UNKNOWN"
        assert metadata["avg_health_index"] is None
        assert metadata["min_health_index"] is None
        assert metadata["max_fused_z"] is None

    def test_apply_contamination_filter_config_disables_filter_for_clean_baseline(self):
        """Calibration helper should disable downstream filtering when baseline is clean."""
        from core.fuse import apply_contamination_filter_config

        cfg = {"clip_z": 8.0}
        out = apply_contamination_filter_config(
            self_tune_cfg=cfg,
            thresholds_cfg={},
            baseline_contamination_verdict="ok",
        )
        assert out is cfg
        assert "contamination_filter" in cfg
        assert cfg["contamination_filter"]["method"] == "iterative_mad"
        assert cfg["contamination_filter"]["enabled"] is False

    def test_apply_contamination_filter_config_respects_config_for_suspect_baseline(self):
        """Calibration helper should keep configured filter settings for suspect baselines."""
        from core.fuse import apply_contamination_filter_config

        cfg = {"clip_z": 8.0}
        out = apply_contamination_filter_config(
            self_tune_cfg=cfg,
            thresholds_cfg={
                "contamination_filter": {
                    "enabled": True,
                    "method": "hybrid",
                    "z_threshold": 5.0,
                    "max_iterations": 7,
                    "min_retained_ratio": 0.8,
                }
            },
            baseline_contamination_verdict="suspect",
        )
        assert out is cfg
        assert cfg["contamination_filter"]["enabled"] is True
        assert cfg["contamination_filter"]["method"] == "hybrid"
        assert cfg["contamination_filter"]["z_threshold"] == pytest.approx(5.0)
        assert cfg["contamination_filter"]["max_iterations"] == 7
        assert cfg["contamination_filter"]["min_retained_ratio"] == pytest.approx(0.8)

    def test_apply_contamination_filter_config_keeps_filter_when_verdict_unknown(self):
        """Calibration helper should stay conservative when no baseline verdict exists."""
        from core.fuse import apply_contamination_filter_config

        cfg = {"clip_z": 8.0}
        out = apply_contamination_filter_config(self_tune_cfg=cfg, thresholds_cfg={})
        assert out is cfg
        assert cfg["contamination_filter"]["enabled"] is True

    def test_choose_pca_cache_for_calibration_length_match(self):
        """PCA cache helper should return cache only when lengths match."""
        from core.fuse import choose_pca_cache_for_calibration

        spe = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        t2 = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        out = choose_pca_cache_for_calibration(
            pca_train_spe=spe,
            pca_train_t2=t2,
            train_len=3,
        )
        assert out is not None
        assert np.array_equal(out[0], spe)
        assert np.array_equal(out[1], t2)

    def test_compute_and_set_adaptive_clip_updates_clip(self):
        """Adaptive clip helper should raise clip_z when train P99 exceeds default."""
        from core.fuse import compute_and_set_adaptive_clip

        train_frame = pd.DataFrame(
            {
                "ar1_raw": np.linspace(0.0, 100.0, 200),
                "iforest_raw": np.linspace(0.0, 50.0, 200),
            }
        )
        self_tune_cfg = {"clip_z": 1.0}
        adaptive = compute_and_set_adaptive_clip(
            train_frame=train_frame,
            self_tune_cfg=self_tune_cfg,
            omr_enabled=False,
        )
        assert adaptive >= 1.0
        assert self_tune_cfg["clip_z"] == pytest.approx(adaptive)

    def test_collect_enabled_calibrators_and_compute_pca_percentiles(self):
        """Calibration helper should filter enabled calibrators and compute PCA train percentiles."""
        from core.fuse import collect_enabled_calibrators, compute_pca_train_percentiles

        class _Cal:
            def __init__(self, offset: float = 0.0):
                self.offset = offset

            def transform(self, x, regime_labels=None):
                return np.asarray(x, dtype=np.float32) + self.offset

        calibrators_dict = {
            "ar1_z": _Cal(),
            "pca_spe_z": _Cal(offset=1.0),
            "pca_t2_z": _Cal(offset=2.0),
            "iforest_z": _Cal(),
            "gmm_z": _Cal(),
            "omr_z": _Cal(),
        }
        frame = pd.DataFrame({"omr_raw": [1.0, 2.0]})
        calibrators = collect_enabled_calibrators(
            calibrators_dict=calibrators_dict,
            frame=frame,
            ar1_enabled=True,
            pca_enabled=True,
            iforest_enabled=False,
            gmm_enabled=False,
            omr_enabled=True,
        )
        names = [name for name, _ in calibrators]
        assert names == ["ar1_z", "pca_spe_z", "pca_t2_z", "omr_z"]

        train_frame = pd.DataFrame(
            {
                "pca_spe": np.array([1.0, 2.0, 3.0, 4.0]),
                "pca_t2": np.array([2.0, 3.0, 4.0, 5.0]),
            }
        )
        spe_p95, t2_p95 = compute_pca_train_percentiles(
            train_frame=train_frame,
            fit_regimes=None,
            pca_enabled=True,
            calibrators_dict=calibrators_dict,
        )
        assert spe_p95 > 0.0
        assert t2_p95 > 0.0

    def test_write_calibration_summary_safe_writes_rows(self):
        """Calibration summary helper should write rows and return count."""
        from core.fuse import write_calibration_summary_safe

        class _Cal:
            def __init__(self):
                self.q_z = 2.0
                self.med = 1.0
                self.scale = 0.5
                self.regime_thresh_ = {0: 1.5}

        class _Out:
            def __init__(self):
                self.rows = []

            def write_calibration_summary(self, rows):
                self.rows.extend(rows)
                return len(rows)

        out = _Out()
        count = write_calibration_summary_safe(
            output_manager=out,
            calibrators=[("ar1_z", _Cal())],
        )
        assert count == 1
        assert len(out.rows) == 1
        assert out.rows[0]["DetectorType"] == "ar1_z"

    def test_persist_calibration_params_safe_uses_model_manager(self, monkeypatch):
        """Model persistence helper should call ModelVersionManager.save_calibration_params."""
        from core import model_persistence

        captured = {"called": False, "version": None}

        class _Mgr:
            def __init__(self, equip, sql_client, equip_id):
                self.equip = equip
                self.sql_client = sql_client
                self.equip_id = equip_id

            def save_calibration_params(self, calibrators_dict, version):
                captured["called"] = True
                captured["version"] = version

        monkeypatch.setattr(model_persistence, "ModelVersionManager", _Mgr)
        ok = model_persistence.persist_calibration_params_safe(
            equip="FD_FAN",
            sql_client=object(),
            equip_id=1,
            saved_model_version=7,
            calibrators_dict={"ar1_z": {"med": 1.0}},
        )
        assert ok is True
        assert captured["called"] is True
        assert captured["version"] == 7

    def test_persist_threshold_artifacts_writes_expected_tables(self):
        """Threshold artifact helper should write both thresholds artifacts when available."""
        from core.fuse import persist_threshold_artifacts

        class _Cal:
            def __init__(self):
                self.med = 1.0
                self.scale = 0.5
                self.q_z = 2.0
                self.q_thresh = 2.0
                self.regime_thresh_ = {0: 1.5}
                self.regime_params_ = {0: (1.0, 0.5)}

        class _Out:
            def __init__(self):
                self.writes = []

            def write_dataframe(self, df, artifact_name):
                self.writes.append((artifact_name, len(df)))

        out = _Out()
        per_regime_count, threshold_count = persist_threshold_artifacts(
            output_manager=out,
            calibrators=[("ar1_z", _Cal())],
            quality_ok=True,
            use_per_regime=True,
        )
        assert per_regime_count == 1
        assert threshold_count == 2
        assert ("per_regime_thresholds", 1) in out.writes
        assert ("acm_thresholds", 2) in out.writes

    def test_run_calibration_stage_orchestrates_and_returns_result(self):
        """Calibration stage helper should orchestrate scoring, calibration, and artifact writes."""
        from core.fuse import run_calibration_stage

        train = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
        frame = pd.DataFrame(
            {
                "ar1_raw": [0.1, 0.2, 0.3, 0.4],
                "pca_spe": [0.1, 0.1, 0.2, 0.3],
                "pca_t2": [0.2, 0.2, 0.3, 0.4],
                "iforest_raw": [0.3, 0.4, 0.5, 0.6],
                "gmm_raw": [0.2, 0.3, 0.4, 0.5],
                "omr_raw": [0.1, 0.2, 0.3, 0.4],
            }
        )

        class _Cal:
            def __init__(self):
                self.med = 0.0
                self.scale = 1.0
                self.q_z = 2.0
                self.q_thresh = 2.0
                self.regime_thresh_ = {}
                self.regime_params_ = {}

            def transform(self, x, regime_labels=None):
                return np.asarray(x, dtype=np.float32)

        def _score_all_detectors_fn(**kwargs):
            return kwargs["data"].assign(
                ar1_raw=np.array([0.1, 0.2, 0.3, 0.4]),
                pca_spe=np.array([0.2, 0.3, 0.4, 0.5]),
                pca_t2=np.array([0.3, 0.4, 0.5, 0.6]),
                iforest_raw=np.array([0.4, 0.5, 0.6, 0.7]),
                gmm_raw=np.array([0.5, 0.6, 0.7, 0.8]),
                omr_raw=np.array([0.6, 0.7, 0.8, 0.9]),
            ), None

        captured = {"self_tune_cfg": None}

        def _calibrate_all_detectors_fn(**kwargs):
            captured["self_tune_cfg"] = kwargs["self_tune_cfg"]
            score_frame = kwargs["score_frame"].copy()
            score_frame["ar1_z"] = score_frame["ar1_raw"]
            score_frame["pca_spe_z"] = score_frame["pca_spe"]
            score_frame["pca_t2_z"] = score_frame["pca_t2"]
            score_frame["iforest_z"] = score_frame["iforest_raw"]
            score_frame["gmm_z"] = score_frame["gmm_raw"]
            score_frame["omr_z"] = score_frame["omr_raw"]
            return score_frame, {
                "ar1_z": _Cal(),
                "pca_spe_z": _Cal(),
                "pca_t2_z": _Cal(),
                "iforest_z": _Cal(),
                "gmm_z": _Cal(),
                "omr_z": _Cal(),
            }

        persisted = {"called": False}

        def _persist(version, calibrators_dict):
            persisted["called"] = True
            return True

        class _Out:
            def __init__(self):
                self.df_writes = 0
                self.summary_writes = 0

            def write_dataframe(self, df, artifact_name):
                self.df_writes += 1

            def write_calibration_summary(self, rows):
                self.summary_writes += 1
                return len(rows)

        class _Logger:
            def info(self, *args, **kwargs):
                pass

            def warn(self, *args, **kwargs):
                pass

        out = _Out()
        result = run_calibration_stage(
            train=train,
            frame=frame,
            cfg={"thresholds": {"q": 0.98, "self_tune": {}}, "fusion": {"per_regime": True}},
            regime_quality_ok=True,
            train_regime_labels=np.array([0, 0, 0, 0]),
            score_regime_labels=np.array([0, 0, 0, 0]),
            pca_train_spe=None,
            pca_train_t2=None,
            detectors={},
            detector_flags={
                "ar1_enabled": True,
                "pca_enabled": True,
                "iforest_enabled": True,
                "gmm_enabled": True,
                "omr_enabled": True,
            },
            cached_calibration_params=None,
            saved_model_version=1,
            score_all_detectors_fn=_score_all_detectors_fn,
            calibrate_all_detectors_fn=_calibrate_all_detectors_fn,
            persist_calibration_params_fn=_persist,
            output_manager=out,
            logger=_Logger(),
            equip="FD_FAN",
            baseline_contamination_verdict="ok",
        )

        assert isinstance(result.frame, pd.DataFrame)
        assert isinstance(result.train_frame, pd.DataFrame)
        assert "per_regime_active" in result.frame.columns
        assert result.quality_ok is True
        assert result.use_per_regime is True
        assert persisted["called"] is True
        assert out.df_writes >= 1
        assert out.summary_writes == 1
        assert captured["self_tune_cfg"]["contamination_filter"]["enabled"] is False

    def test_apply_fusion_result_and_record_metrics_updates_frames(self):
        """Fusion result helper should apply fused columns and emit detector metrics."""
        from core.fuse import FusionResult, apply_fusion_result_and_record_metrics

        frame = pd.DataFrame(
            {
                "ar1_z": [0.1, 0.2],
                "pca_spe_z": [0.2, 0.3],
                "pca_t2_z": [0.3, 0.4],
                "iforest_z": [0.4, 0.5],
                "gmm_z": [0.5, 0.6],
                "omr_z": [0.6, 0.7],
            }
        )
        train_frame = pd.DataFrame({"x": [1.0, 2.0]})
        fusion_result = FusionResult(
            fused_scores=np.array([1.1, 1.2], dtype=np.float32),
            episodes=pd.DataFrame({"episode_id": [1]}),
            weights_used={"ar1_z": 1.0},
            auto_tuned=False,
            train_fused=np.array([0.9, 1.0], dtype=np.float32),
        )

        captured = {"detector_scores": None, "episode": None}

        def _record_detector_scores(equip, detector_scores):
            captured["detector_scores"] = (equip, detector_scores)

        def _record_episode(equip, count, severity):
            captured["episode"] = (equip, count, severity)

        out_frame, out_train, episodes, weights = apply_fusion_result_and_record_metrics(
            frame=frame,
            train_frame=train_frame,
            fusion_result=fusion_result,
            equip="FD_FAN",
            record_detector_scores_fn=_record_detector_scores,
            record_episode_fn=_record_episode,
        )

        assert "fused" in out_frame.columns
        assert "fused" in out_train.columns
        assert len(episodes) == 1
        assert weights == {"ar1_z": 1.0}
        assert captured["detector_scores"] is not None
        assert captured["episode"] == ("FD_FAN", 1, "warning")

    def test_run_fusion_stage_orchestrates_pipeline_and_apply(self, monkeypatch):
        """Fusion stage helper should compose pipeline run and result application."""
        from core import fuse
        from core.fuse import FusionResult

        frame = pd.DataFrame({"ar1_z": [0.1, 0.2]})
        train_frame = pd.DataFrame({"ar1_z": [0.05, 0.06]})
        score_data = pd.DataFrame({"x": [1.0, 2.0]})
        train_data = pd.DataFrame({"x": [0.8, 0.9]})
        episodes_df = pd.DataFrame({"episode_id": [1]})

        def _fake_run_fusion_pipeline(**kwargs):
            return FusionResult(
                fused_scores=np.array([1.0, 1.1], dtype=np.float32),
                episodes=episodes_df,
                weights_used={"ar1_z": 1.0},
                auto_tuned=False,
                train_fused=np.array([0.7, 0.8], dtype=np.float32),
            )

        def _fake_apply_fusion_result_and_record_metrics(**kwargs):
            out_frame = kwargs["frame"].copy()
            out_frame["fused"] = [1.0, 1.1]
            out_train = kwargs["train_frame"].copy()
            out_train["fused"] = [0.7, 0.8]
            return out_frame, out_train, episodes_df, {"ar1_z": 1.0}

        monkeypatch.setattr(fuse, "run_fusion_pipeline", _fake_run_fusion_pipeline)
        monkeypatch.setattr(fuse, "apply_fusion_result_and_record_metrics", _fake_apply_fusion_result_and_record_metrics)

        result = fuse.run_fusion_stage(
            frame=frame,
            train_frame=train_frame,
            score_data=score_data,
            train_data=train_data,
            cfg={},
            equip="FD_FAN",
        )

        assert "fused" in result.frame.columns
        assert result.train_frame is not None and "fused" in result.train_frame.columns
        assert len(result.episodes) == 1
        assert result.fusion_weights_used == {"ar1_z": 1.0}

    def test_run_health_stage_orchestrates_calibration_fusion_thresholds_postprocess_and_autotune(self, monkeypatch):
        """Health stage helper should orchestrate calibration, fusion, thresholds, postprocess, and auto-tune."""
        from core import fuse

        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        train = pd.DataFrame({"a": [1.0, 2.0]}, index=idx)
        score = pd.DataFrame({"a": [1.5, 2.5]}, index=idx)
        frame = pd.DataFrame({"ar1_raw": [0.1, 0.2]}, index=idx)

        sections = []
        class _Section:
            def __init__(self, name):
                self.name = name
            def __enter__(self):
                sections.append(self.name)
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        def _section_fn(name):
            return _Section(name)

        forwarded = {"calibration_verdict": None, "adaptive_verdict": None}

        def _run_calibration_stage(**kwargs):
            forwarded["calibration_verdict"] = kwargs["baseline_contamination_verdict"]
            out_frame = kwargs["frame"].copy()
            out_frame["ar1_z"] = [0.3, 0.4]
            out_train = kwargs["train"].copy()
            out_train["ar1_z"] = [0.1, 0.2]
            return type(
                "CalibrationStageResult",
                (),
                {
                    "frame": out_frame,
                    "train_frame": out_train,
                    "spe_p95_train": 1.1,
                    "t2_p95_train": 2.2,
                    "quality_ok": True,
                    "use_per_regime": True,
                },
            )()

        def _run_fusion_stage(**kwargs):
            out_frame = kwargs["frame"].copy()
            out_frame["fused"] = [1.0, 1.1]
            out_train = kwargs["train_frame"].copy()
            out_train["fused"] = [0.8, 0.9]
            return fuse.FusionStageResult(
                frame=out_frame,
                train_frame=out_train,
                episodes=pd.DataFrame({"episode_id": [1]}),
                fusion_weights_used={"ar1_z": 1.0},
            )

        monkeypatch.setattr(fuse, "run_calibration_stage", _run_calibration_stage)
        monkeypatch.setattr(fuse, "run_fusion_stage", _run_fusion_stage)

        threshold_calls = {"called": False}
        def _maybe_update_adaptive_thresholds_fn(**kwargs):
            threshold_calls["called"] = True
            forwarded["adaptive_verdict"] = kwargs["baseline_contamination_verdict"]

        def _run_regime_postprocess_stage_fn(**kwargs):
            out_frame = kwargs["frame"].copy()
            out_frame["regime_state"] = ["steady", "steady"]
            return type(
                "RegimePostprocessResult",
                (),
                {
                    "frame": out_frame,
                    "transient_counts": {"steady": 2},
                    "context_assignment": fuse.ContextAssignment(
                        context_id="regime:0",
                        context_label="REGIME_0",
                        context_confidence=0.7,
                        context_stability="STABLE",
                        transition_status="STEADY",
                        is_novel=False,
                        is_ambiguous=False,
                    ),
                },
            )()

        auto_tune_calls = {"called": False}
        def _auto_tune_parameters_fn(**kwargs):
            auto_tune_calls["called"] = True

        result = fuse.run_health_stage(
            section_fn=_section_fn,
            train=train,
            score=score,
            frame=frame,
            cfg={},
            regime_quality_ok=True,
            train_regime_labels=np.array([0, 0]),
            score_regime_labels=np.array([0, 1]),
            pca_train_spe=None,
            pca_train_t2=None,
            detectors={"ar1_detector": object(), "pca_detector": None, "iforest_detector": None, "gmm_detector": None, "omr_detector": None},
            detector_flags={"ar1_enabled": True, "pca_enabled": False, "iforest_enabled": False, "gmm_enabled": False, "omr_enabled": False},
            cached_calibration_params=None,
            saved_model_version=1,
            score_all_detectors_fn=lambda **kwargs: (pd.DataFrame(), None),
            calibrate_all_detectors_fn=lambda **kwargs: (pd.DataFrame(), {}),
            persist_calibration_params_fn=lambda *args, **kwargs: True,
            output_manager=object(),
            logger=type("L", (), {"info": lambda *a, **k: None, "warn": lambda *a, **k: None})(),
            equip="FD_FAN",
            previous_weights=None,
            omr_contributions_data=None,
            record_detector_scores_fn=None,
            record_episode_fn=None,
            maybe_update_adaptive_thresholds_fn=_maybe_update_adaptive_thresholds_fn,
            coldstart_complete=True,
            equip_id=1,
            run_regime_postprocess_stage_fn=_run_regime_postprocess_stage_fn,
            regime_model=None,
            auto_tune_parameters_fn=_auto_tune_parameters_fn,
            score_out={},
            sql_client=object(),
            run_id="r1",
            cached_manifest={},
            baseline_contamination_verdict="suspect",
        )

        assert "fused" in result.frame.columns
        assert "regime_state" in result.frame.columns
        assert result.spe_p95_train == pytest.approx(1.1)
        assert result.t2_p95_train == pytest.approx(2.2)
        assert result.context_assignment.context_label == "REGIME_0"
        assert result.quality_ok is True
        assert result.use_per_regime is True
        assert threshold_calls["called"] is True
        assert auto_tune_calls["called"] is True
        assert forwarded["calibration_verdict"] == "suspect"
        assert forwarded["adaptive_verdict"] == "suspect"
        assert sections == ["calibrate", "fusion", "thresholds.adaptive", "regimes.postprocess"]

    def test_run_health_stage_skips_learning_side_effects_when_representation_blocks_learning(self, monkeypatch):
        """Health stage should skip adaptive thresholds and auto-tune when validation authority blocks learning."""
        from core import fuse
        from core.representation_contracts import EligibilityDecision

        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        train = pd.DataFrame({"a": [1.0, 2.0]}, index=idx)
        score = pd.DataFrame({"a": [1.5, 2.5]}, index=idx)
        frame = pd.DataFrame({"ar1_raw": [0.1, 0.2]}, index=idx)

        sections = []

        class _Section:
            def __init__(self, name):
                self.name = name

            def __enter__(self):
                sections.append(self.name)
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def _section_fn(name):
            return _Section(name)

        def _run_calibration_stage(**kwargs):
            out_frame = kwargs["frame"].copy()
            out_frame["ar1_z"] = [0.3, 0.4]
            out_train = kwargs["train"].copy()
            out_train["ar1_z"] = [0.1, 0.2]
            return type(
                "CalibrationStageResult",
                (),
                {
                    "frame": out_frame,
                    "train_frame": out_train,
                    "spe_p95_train": 1.1,
                    "t2_p95_train": 2.2,
                    "quality_ok": True,
                    "use_per_regime": True,
                },
            )()

        def _run_fusion_stage(**kwargs):
            out_frame = kwargs["frame"].copy()
            out_frame["fused"] = [1.0, 1.1]
            out_train = kwargs["train_frame"].copy()
            out_train["fused"] = [0.8, 0.9]
            return fuse.FusionStageResult(
                frame=out_frame,
                train_frame=out_train,
                episodes=pd.DataFrame({"episode_id": [1]}),
                fusion_weights_used={"ar1_z": 1.0},
            )

        monkeypatch.setattr(fuse, "run_calibration_stage", _run_calibration_stage)
        monkeypatch.setattr(fuse, "run_fusion_stage", _run_fusion_stage)

        threshold_calls = {"called": False}

        def _maybe_update_adaptive_thresholds_fn(**kwargs):
            threshold_calls["called"] = True

        def _run_regime_postprocess_stage_fn(**kwargs):
            return type(
                "RegimePostprocessResult",
                (),
                {
                    "frame": kwargs["frame"],
                    "transient_counts": {"steady": 2},
                    "context_assignment": fuse.ContextAssignment(
                        context_id="regime:0",
                        context_label="REGIME_0",
                        context_confidence=0.7,
                        context_stability="STABLE",
                        transition_status="STEADY",
                        is_novel=False,
                        is_ambiguous=False,
                    ),
                },
            )()

        auto_tune_calls = {"called": False}

        def _auto_tune_parameters_fn(**kwargs):
            auto_tune_calls["called"] = True

        representation_result = type(
            "RepresentationResult",
            (),
            {
                "authoritative": True,
                "eligibility": EligibilityDecision(
                    authoritative=True,
                    score_allowed=False,
                    learn_allowed=False,
                    suppressed_reason_codes=("context_unknown",),
                ),
            },
        )()

        result = fuse.run_health_stage(
            section_fn=_section_fn,
            train=train,
            score=score,
            frame=frame,
            cfg={},
            regime_quality_ok=True,
            train_regime_labels=np.array([0, 0]),
            score_regime_labels=np.array([0, 1]),
            pca_train_spe=None,
            pca_train_t2=None,
            detectors={"ar1_detector": object(), "pca_detector": None, "iforest_detector": None, "gmm_detector": None, "omr_detector": None},
            detector_flags={"ar1_enabled": True, "pca_enabled": False, "iforest_enabled": False, "gmm_enabled": False, "omr_enabled": False},
            cached_calibration_params=None,
            saved_model_version=1,
            score_all_detectors_fn=lambda **kwargs: (pd.DataFrame(), None),
            calibrate_all_detectors_fn=lambda **kwargs: (pd.DataFrame(), {}),
            persist_calibration_params_fn=lambda *args, **kwargs: True,
            output_manager=object(),
            logger=type("L", (), {"info": lambda *a, **k: None, "warn": lambda *a, **k: None})(),
            equip="FD_FAN",
            previous_weights=None,
            omr_contributions_data=None,
            record_detector_scores_fn=None,
            record_episode_fn=None,
            maybe_update_adaptive_thresholds_fn=_maybe_update_adaptive_thresholds_fn,
            coldstart_complete=True,
            equip_id=1,
            run_regime_postprocess_stage_fn=_run_regime_postprocess_stage_fn,
            regime_model=None,
            auto_tune_parameters_fn=_auto_tune_parameters_fn,
            score_out={},
            sql_client=object(),
            run_id="r1",
            cached_manifest={},
            baseline_contamination_verdict="clear",
            representation_result=representation_result,
            representation_authority_active=True,
        )

        assert result.context_assignment.context_label == "REGIME_0"
        assert threshold_calls["called"] is False
        assert auto_tune_calls["called"] is False
        assert sections == ["calibrate", "fusion", "regimes.postprocess"]

    def test_suppress_representation_scoring_clears_authoritative_scores_and_episodes(self):
        """Score suppression helper should blank score columns and remove episodes."""
        from core import fuse
        from core.representation_contracts import EligibilityDecision

        idx = pd.date_range("2026-01-01", periods=2, freq="h")
        frame = pd.DataFrame(
            {
                "fused": [1.0, 2.0],
                "ar1_z": [0.4, 0.5],
                "health": [95.0, 90.0],
                "regime_label": ["R0", "R0"],
            },
            index=idx,
        )
        episodes = pd.DataFrame({"episode_id": [1], "peak_fused_z": [2.0]})
        representation_result = type(
            "RepresentationResult",
            (),
            {
                "authoritative": True,
                "run_id": "r1",
                "equip_id": 1,
                "eligibility": EligibilityDecision(
                    authoritative=True,
                    score_allowed=False,
                    learn_allowed=False,
                    suppressed_reason_codes=("context_unknown",),
                ),
            },
        )()

        out_frame, out_episodes, suppressed = fuse.suppress_representation_scoring(
            frame=frame,
            episodes=episodes,
            representation_result=representation_result,
        )

        assert suppressed is True
        assert out_frame["fused"].isna().all()
        assert out_frame["ar1_z"].isna().all()
        assert out_frame["health"].isna().all()
        assert out_frame["regime_label"].tolist() == ["R0", "R0"]
        assert out_episodes.empty

    def test_run_feature_preparation_stage_orchestrates_pipeline(self, monkeypatch):
        """Feature preparation stage should orchestrate seasonality, guardrails, build, impute, hash, and refit flag."""
        from core import fast_features

        idx = pd.date_range("2026-01-01", periods=3, freq="h")
        train = pd.DataFrame({"a": [1.0, 2.0, 3.0]}, index=idx)
        score = pd.DataFrame({"a": [1.5, 2.5, 3.5]}, index=idx)

        calls = {"sections": [], "impute": None}

        class _Section:
            def __init__(self, name):
                self.name = name
            def __enter__(self):
                calls["sections"].append(self.name)
                return self
            def __exit__(self, exc_type, exc, tb):
                return False

        def _section_fn(name):
            return _Section(name)

        def _detect_and_adjust_fn(**kwargs):
            return kwargs["train"], kwargs["score"], {"sensor_a": []}, False

        def _run_data_guardrails_fn(**kwargs):
            return type("GuardrailResult", (), {"low_var_threshold": 0.25})()

        def _load_manifest_protected_columns_fn(**kwargs):
            return ["a"]

        def _build_features_for_pipeline(**kwargs):
            out_train = kwargs["train"].copy()
            out_score = kwargs["score"].copy()
            out_train["a_feat"] = out_train["a"] * 2.0
            out_score["a_feat"] = out_score["a"] * 2.0
            return out_train, out_score

        def _impute_features(**kwargs):
            calls["impute"] = {
                "low_var_threshold": kwargs["low_var_threshold"],
                "protected_columns": kwargs["protected_columns"],
            }
            return kwargs["train"], kwargs["score"], []

        monkeypatch.setattr(fast_features, "build_features_for_pipeline", _build_features_for_pipeline)
        monkeypatch.setattr(fast_features, "impute_features", _impute_features)

        class _OutputManager:
            def check_refit_request(self):
                return True

        result = fast_features.run_feature_preparation_stage(
            train=train,
            score=score,
            cfg={},
            meta={"is_coldstart_run": False},
            output_manager=_OutputManager(),
            sql_client=object(),
            run_id="r1",
            equip_id=1,
            equip="FD_FAN",
            section_fn=_section_fn,
            detect_and_adjust_fn=_detect_and_adjust_fn,
            run_data_guardrails_fn=_run_data_guardrails_fn,
            load_manifest_protected_columns_fn=_load_manifest_protected_columns_fn,
        )

        assert "a_feat" in result.train.columns
        assert "a_feat" in result.score.columns
        assert result.raw_train.equals(train)
        assert result.raw_score.equals(score)
        assert result.seasonal_patterns == {"sensor_a": []}
        assert result.refit_requested is True
        assert calls["impute"]["low_var_threshold"] == pytest.approx(0.25)
        assert calls["impute"]["protected_columns"] == ["a"]
        assert calls["sections"] == [
            "seasonality.detect",
            "data.guardrails",
            "features.build",
            "features.impute",
            "models.refit_flag",
        ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

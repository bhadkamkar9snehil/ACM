"""
Tests for V11 core modules: confidence.py, model_lifecycle.py, acm.py

Run with: pytest tests/test_v11_modules.py -v
"""
import pytest
import numpy as np
import pandas as pd
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
    
    def test_detect_mode_function_exists(self):
        """_detect_mode function exists."""
        from core import acm
        assert hasattr(acm, '_detect_mode')


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
            continuous_learning=False,
            threshold_update_interval=1,
            regime_quality_ok=False,
            logger=_Logger(),
        )
        assert updated is False

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
        assert out["force_retrain"] is False
        assert out["cached_models"] is None
        assert out["retrain_result"] is None

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

    def test_apply_transient_state_labels_no_regime_label(self):
        """Transient helper should no-op when regime_label column is absent."""
        from core.regimes import apply_transient_state_labels

        frame = pd.DataFrame({"fused": [0.1, 0.2, 0.3]})
        score_data = pd.DataFrame({"sensor": [1.0, 2.0, 3.0]})
        out_frame, counts = apply_transient_state_labels(frame=frame, score_data=score_data, cfg={})
        assert out_frame.equals(frame)
        assert counts == {}

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

    def test_write_sql_artifacts_for_run_delegates_to_module_function(self, monkeypatch):
        """Output manager wrapper should delegate SQL artifact writing to module helper."""
        from core import output_manager as om_module
        from core.output_manager import OutputManager

        captured = {}

        def _fake_write_sql_artifacts(**kwargs):
            captured.update(kwargs)
            return 123

        monkeypatch.setattr(om_module, "write_sql_artifacts", _fake_write_sql_artifacts)
        out = OutputManager.__new__(OutputManager)

        result = out.write_sql_artifacts_for_run(
            frame=pd.DataFrame({"fused": [0.1]}),
            episodes=pd.DataFrame({"episode_id": [1]}),
            train=pd.DataFrame({"sensor": [1.0]}),
            pca_detector=object(),
            sql_client=object(),
            run_id="r1",
            equip_id=1,
            equip="FD_FAN",
            cfg={},
            meta=object(),
            win_start=pd.Timestamp("2026-01-01"),
            win_end=pd.Timestamp("2026-01-02"),
            rows_read=10,
            spe_p95_train=1.1,
            t2_p95_train=2.2,
            anomaly_count=3,
            T=object(),
            culprit_writer_func=lambda *_a, **_k: None,
        )

        assert result == 123
        assert captured["output_manager"] is out
        assert captured["equip"] == "FD_FAN"
        assert captured["rows_read"] == 10

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

    def test_apply_contamination_filter_config_sets_defaults(self):
        """Calibration config helper should always set contamination_filter with defaults."""
        from core.fuse import apply_contamination_filter_config

        cfg = {"clip_z": 8.0}
        out = apply_contamination_filter_config(self_tune_cfg=cfg, thresholds_cfg={})
        assert out is cfg
        assert "contamination_filter" in cfg
        assert cfg["contamination_filter"]["method"] == "iterative_mad"
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

        def _calibrate_all_detectors_fn(**kwargs):
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
        )

        assert isinstance(result.frame, pd.DataFrame)
        assert isinstance(result.train_frame, pd.DataFrame)
        assert "per_regime_active" in result.frame.columns
        assert result.quality_ok is True
        assert result.use_per_regime is True
        assert persisted["called"] is True
        assert out.df_writes >= 1
        assert out.summary_writes == 1

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

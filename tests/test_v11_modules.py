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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

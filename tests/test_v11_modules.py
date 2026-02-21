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

        def _finalize_noop(**kwargs):
            finalize_calls.append(kwargs)

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
        )

        assert out.should_continue is False
        assert out.coldstart_complete is False
        assert len(finalize_calls) == 1

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

    def test_run_auto_retrain_stage_applies_retrain_outputs(self, monkeypatch):
        """Auto-retrain stage helper should apply detector outputs from retrain payload."""
        from core import model_evaluation

        retrained_detector = object()

        def _eval_and_refit(**kwargs):
            return {
                "force_retrain": True,
                "cached_models": None,
                "regime_model": None,
                "retrain_result": {
                    "ar1_detector": retrained_detector,
                    "pca_detector": retrained_detector,
                    "iforest_detector": retrained_detector,
                    "gmm_detector": None,
                    "omr_detector": None,
                    "pca_train_spe": np.array([0.1, 0.2]),
                    "pca_train_t2": np.array([0.2, 0.3]),
                },
            }

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
        assert out["force_retrain"] is True
        assert out["cached_models"] is None
        assert out["detectors"]["ar1_detector"] is retrained_detector
        assert out["detectors"]["pca_detector"] is retrained_detector
        assert out["detectors"]["iforest_detector"] is retrained_detector
        assert isinstance(out["detectors"]["pca_train_spe"], np.ndarray)
        assert isinstance(out["detectors"]["pca_train_t2"], np.ndarray)

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
        assert out["detectors_fitted_this_run"] is True
        assert out["models_were_trained"] is True
        assert out["saved_model_version"] == 7
        assert out["model_state"] == {"state": "updated"}
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
        assert out["detectors_fitted_this_run"] is False
        assert out["models_were_trained"] is False
        assert out["saved_model_version"] is None
        assert out["model_state"] == {"state": "loaded"}
        assert captured["loaded"] is True

    def test_run_model_adaptation_and_persistence_stage_orchestrates_two_stages(self):
        """Combined model stage helper should run auto-retrain stage then persistence stage."""
        from core.model_persistence import run_model_adaptation_and_persistence_stage, ModelPersistenceStageResult

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
        from core.detector_orchestrator import initialize_detectors_for_run

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

        out = initialize_detectors_for_run(
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

        assert out["detectors_just_trained"] is True
        assert out["use_cache"] is False
        assert out["ar1_detector"] is fitted
        assert out["pca_detector"] is fitted
        assert out["iforest_detector"] is fitted
        assert out["gmm_detector"] is None
        assert out["omr_detector"] is None
        assert isinstance(out["pca_train_spe"], np.ndarray)
        assert isinstance(out["pca_train_t2"], np.ndarray)

    def test_initialize_detectors_for_run_uses_sql_cache_without_refit(self):
        """Detector init helper should reuse cached detectors when cache payload is valid."""
        from core.detector_orchestrator import initialize_detectors_for_run

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

        out = initialize_detectors_for_run(
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

        assert out["use_cache"] is True
        assert out["detectors_just_trained"] is False
        assert out["cached_models"] is not None
        assert out["cached_manifest"] is not None
        assert out["cached_calibration_params"] is not None
        assert out["ar1_detector"] is cached_detector
        assert out["pca_detector"] is cached_detector
        assert out["iforest_detector"] is cached_detector

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
        from core.detector_orchestrator import initialize_detectors_for_run

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
            initialize_detectors_for_run(
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

    def test_apply_transient_state_labels_no_regime_label(self):
        """Transient helper should no-op when regime_label column is absent."""
        from core.regimes import apply_transient_state_labels

        frame = pd.DataFrame({"fused": [0.1, 0.2, 0.3]})
        score_data = pd.DataFrame({"sensor": [1.0, 2.0, 3.0]})
        out_frame, counts = apply_transient_state_labels(frame=frame, score_data=score_data, cfg={})
        assert out_frame.equals(frame)
        assert counts == {}

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

    def test_run_persistence_stage_orchestrates_pipeline_outputs_and_sql_artifacts(self):
        """Output manager persistence stage should run pipeline outputs and SQL artifact writes in order."""
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
        out.write_sql_artifacts_for_run = lambda **kwargs: 88

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

        assert result.rows_written == 88
        assert result.analytics_table_count == 11
        assert calls["sections"] == ["persist", "persist.pipeline_outputs"]

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

        def _compute_feature_hash_fn(_train, _equip):
            return "hash-123"

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
            compute_feature_hash_fn=_compute_feature_hash_fn,
        )

        assert "a_feat" in result.train.columns
        assert "a_feat" in result.score.columns
        assert result.raw_train.equals(train)
        assert result.raw_score.equals(score)
        assert result.seasonal_patterns == {"sensor_a": []}
        assert result.train_feature_hash == "hash-123"
        assert result.refit_requested is True
        assert calls["impute"]["low_var_threshold"] == pytest.approx(0.25)
        assert calls["impute"]["protected_columns"] == ["a"]
        assert calls["sections"] == [
            "seasonality.detect",
            "data.guardrails",
            "features.build",
            "features.impute",
            "features.hash",
            "models.refit_flag",
        ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

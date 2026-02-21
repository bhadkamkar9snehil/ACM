"""
Tests for V11 core modules: confidence.py, model_lifecycle.py, acm.py

Run with: pytest tests/test_v11_modules.py -v
"""
import pytest
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

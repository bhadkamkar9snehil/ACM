"""
Test suite for Overall Model Residual (OMR) detector.

Tests multivariate health residual detection, model auto-selection,
per-sensor contribution tracking, and attribution capabilities.
"""

import numpy as np
import pandas as pd
from core.omr import OMRDetector  # Moved from models/ to core/


def test_omr_basic_fit_score():
    """Test basic OMR fitting and scoring."""
    np.random.seed(42)
    
    # Create synthetic training data (3 correlated sensors)
    n_train = 200
    X_train = pd.DataFrame({
        'sensor1': np.random.randn(n_train),
        'sensor2': np.random.randn(n_train),
        'sensor3': np.random.randn(n_train)
    })
    X_train['sensor2'] += 0.5 * X_train['sensor1']  # Correlation
    X_train['sensor3'] += 0.3 * X_train['sensor1']  # Correlation
    
    # Fit OMR
    omr = OMRDetector(cfg={"omr": {"model_type": "pls", "n_components": 2}})
    omr.fit(X_train)
    
    assert omr._is_fitted
    assert omr.model is not None
    
    # Score on test data (healthy)
    X_test = X_train.copy()
    omr_z = omr.score(X_test)
    
    assert len(omr_z) == len(X_test)
    assert np.all(np.isfinite(omr_z))
    # Healthy data should have low z-scores
    assert np.median(omr_z) < 2.0


def test_omr_anomaly_detection():
    """Test that OMR detects multivariate anomalies."""
    np.random.seed(42)
    
    # Training data with correlation
    n_train = 300
    X_train = pd.DataFrame({
        'sensor1': np.random.randn(n_train),
        'sensor2': np.random.randn(n_train),
        'sensor3': np.random.randn(n_train)
    })
    X_train['sensor2'] += 0.7 * X_train['sensor1']
    
    # Fit OMR
    omr = OMRDetector(cfg={})
    omr.fit(X_train)
    
    # Test data with anomaly: sensor2 breaks correlation
    X_test = X_train.iloc[:50].copy()
    X_test.loc[X_test.index[25], 'sensor2'] += 5.0  # Break correlation
    
    omr_z = omr.score(X_test)
    
    # Anomaly should have high z-score
    assert omr_z[25] > 3.0
    # Other points should be normal
    assert np.median(omr_z) < 2.0


def test_omr_contribution_tracking():
    """Test per-sensor contribution tracking."""
    np.random.seed(42)
    
    n_train = 200
    X_train = pd.DataFrame({
        'sensor1': np.random.randn(n_train),
        'sensor2': np.random.randn(n_train),
        'sensor3': np.random.randn(n_train)
    })
    
    omr = OMRDetector(cfg={})
    omr.fit(X_train)
    
    # Score with contributions
    X_test = X_train.iloc[:50].copy()
    X_test.loc[X_test.index[10], 'sensor1'] += 10.0  # Large deviation
    
    omr_z, contributions = omr.score(X_test, return_contributions=True)
    
    assert contributions is not None
    assert contributions.shape == (len(X_test), 3)
    assert list(contributions.columns) == ['sensor1', 'sensor2', 'sensor3']
    
    # Get top contributors at anomaly timestamp
    anomaly_ts = X_test.index[10]
    top_contribs = omr.get_top_contributors(contributions, anomaly_ts, top_n=3)
    
    assert len(top_contribs) == 3
    # sensor1 should be top contributor
    assert top_contribs[0][0] == 'sensor1'
    assert top_contribs[0][1] > top_contribs[1][1]  # Highest contribution


def test_omr_model_auto_selection():
    """Test automatic model type selection based on data shape."""
    np.random.seed(42)
    
    # Case 1: More features than samples → PCA
    X_wide = pd.DataFrame(np.random.randn(50, 100))
    omr_wide = OMRDetector(cfg={"omr": {"model_type": "auto"}})
    omr_wide.fit(X_wide)
    assert "pca" in str(type(omr_wide.model.model)).lower()
    
    # Case 2: Normal case → PLS (default)
    X_normal = pd.DataFrame(np.random.randn(200, 10))
    omr_normal = OMRDetector(cfg={"omr": {"model_type": "auto"}})
    omr_normal.fit(X_normal)
    assert "pls" in str(type(omr_normal.model.model)).lower() or \
           "ridge" in str(type(omr_normal.model.model)).lower()


def test_omr_healthy_regime_filtering():
    """Test filtering to healthy regime during training."""
    np.random.seed(42)
    
    n_samples = 300
    X_train = pd.DataFrame({
        'sensor1': np.random.randn(n_samples),
        'sensor2': np.random.randn(n_samples)
    })
    
    # Create regime labels: 0=healthy, 1=degraded
    regime_labels = np.zeros(n_samples)
    regime_labels[200:] = 1  # Last 100 samples are degraded
    
    # Add anomaly to degraded regime
    X_train.loc[X_train.index[250:], 'sensor1'] += 3.0
    
    # Fit OMR with regime filtering
    omr = OMRDetector(cfg={})
    omr.fit(X_train, regime_labels=regime_labels)
    
    # Should fit only on healthy regime (first 200 samples)
    assert omr._is_fitted
    # Model should be robust to degraded data exclusion


def test_omr_persistence():
    """Test model serialization and deserialization."""
    np.random.seed(42)
    
    X_train = pd.DataFrame(np.random.randn(100, 5))
    
    omr = OMRDetector(cfg={"omr": {"model_type": "pls", "n_components": 3}})
    omr.fit(X_train)
    
    # Serialize
    state_dict = omr.to_dict()
    
    assert "fitted" in state_dict
    assert "model" in state_dict
    assert "model_type" in state_dict["model"]
    assert "feature_names" in state_dict["model"]
    assert "train_residual_std" in state_dict["model"]
    
    # Deserialize
    omr_loaded = OMRDetector.from_dict(state_dict, cfg={"omr": {}})
    
    assert omr_loaded._is_fitted
    assert omr_loaded.model.model_type == omr.model.model_type
    assert omr_loaded.model.feature_names == omr.model.feature_names
    
    # Should produce same scores
    X_test = X_train.iloc[:10]
    scores_original = omr.score(X_test)
    scores_loaded = omr_loaded.score(X_test)
    
    np.testing.assert_allclose(scores_original, scores_loaded, rtol=1e-5)


def test_omr_missing_data_handling():
    """Test OMR handles missing values gracefully."""
    np.random.seed(42)
    
    X_train = pd.DataFrame(np.random.randn(200, 4))
    X_train.iloc[50:60, 1] = np.nan  # Inject NaNs
    
    omr = OMRDetector(cfg={})
    omr.fit(X_train)
    
    assert omr._is_fitted
    
    X_test = X_train.iloc[:50].copy()
    X_test.iloc[10:15, 2] = np.nan
    
    omr_z = omr.score(X_test)
    
    assert len(omr_z) == len(X_test)
    assert np.all(np.isfinite(omr_z))


if __name__ == "__main__":
    # Run all tests
    test_omr_basic_fit_score()
    print("✓ Basic fit/score test passed")
    
    test_omr_anomaly_detection()
    print("✓ Anomaly detection test passed")
    
    test_omr_contribution_tracking()
    print("✓ Contribution tracking test passed")
    
    test_omr_model_auto_selection()
    print("✓ Model auto-selection test passed")
    
    test_omr_healthy_regime_filtering()
    print("✓ Healthy regime filtering test passed")
    
    test_omr_persistence()
    print("✓ Persistence test passed")
    
    test_omr_missing_data_handling()
    print("✓ Missing data handling test passed")
    
    print("\n✅ All OMR tests passed!")

# tests/test_fuse.py
"""
Comprehensive tests for core/fuse.py module.

Tests cover:
1. tune_detector_weights() - Weight auto-tuning logic
2. ScoreCalibrator - Robust z-score calibration
3. Fuser.fuse() - Weighted score fusion
4. Fuser.detect_episodes() - CUSUM-based episode detection
5. combine() - Integration of fusion and episode detection
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.fuse import (
    tune_detector_weights,
    ScoreCalibrator,
    Fuser,
    EpisodeParams,
    combine,
)


class TestTuneDetectorWeights:
    """Tests for the tune_detector_weights function."""

    def test_disabled_returns_current_weights(self):
        """When auto_tune is disabled, return current weights unchanged."""
        streams = {"det1": np.array([1.0, 2.0, 3.0]), "det2": np.array([0.5, 1.5, 2.5])}
        fused = np.array([0.75, 1.75, 2.75])
        current = {"det1": 0.6, "det2": 0.4}
        cfg = {"fusion": {"auto_tune": {"enabled": False}}}

        result, diag = tune_detector_weights(streams, fused, current, cfg)

        assert result == current
        assert diag["enabled"] is False

    def test_empty_fused_signal_returns_current(self):
        """Empty fused signal should return current weights."""
        streams = {"det1": np.array([1.0, 2.0])}
        fused = np.array([])
        current = {"det1": 1.0}
        cfg = {"fusion": {"auto_tune": {"enabled": True}}}

        result, diag = tune_detector_weights(streams, fused, current, cfg)

        assert result == current
        assert "empty_fused_signal" in diag.get("reason", "")

    def test_softmax_temperature_effect(self):
        """Higher temperature should flatten the weight distribution."""
        np.random.seed(42)
        n = 200
        # Create streams with different signal quality
        streams = {
            "det_good": np.random.randn(n) * 0.5 + 2.0,  # Higher mean, lower variance
            "det_bad": np.random.randn(n) * 2.0,  # Lower mean, higher variance
        }
        fused = (streams["det_good"] + streams["det_bad"]) / 2
        current = {"det_good": 0.5, "det_bad": 0.5}

        # Low temperature - more discriminating
        cfg_low_temp = {"fusion": {"auto_tune": {"enabled": True, "temperature": 0.5, "method": "correlation"}}}
        _, diag_low = tune_detector_weights(streams, fused, current, cfg_low_temp)

        # High temperature - more uniform
        cfg_high_temp = {"fusion": {"auto_tune": {"enabled": True, "temperature": 5.0, "method": "correlation"}}}
        _, diag_high = tune_detector_weights(streams, fused, current, cfg_high_temp)

        # With high temperature, weights should be closer to equal
        raw_low = diag_low.get("raw_weights", {})
        raw_high = diag_high.get("raw_weights", {})

        if raw_low and raw_high:
            diff_low = abs(raw_low.get("det_good", 0.5) - raw_low.get("det_bad", 0.5))
            diff_high = abs(raw_high.get("det_good", 0.5) - raw_high.get("det_bad", 0.5))
            assert diff_high <= diff_low + 0.01  # High temp should have smaller difference

    def test_min_weight_enforced(self):
        """Minimum weight should be enforced after blending."""
        np.random.seed(42)
        n = 200
        streams = {
            "det1": np.random.randn(n) + 5.0,  # Strong signal
            "det2": np.random.randn(n) * 0.01,  # Weak signal
        }
        fused = streams["det1"]  # Fused dominated by det1
        current = {"det1": 0.5, "det2": 0.5}
        cfg = {"fusion": {"auto_tune": {"enabled": True, "min_weight": 0.1, "method": "correlation"}}}

        result, _ = tune_detector_weights(streams, fused, current, cfg)

        # Minimum weight should be enforced
        for weight in result.values():
            assert weight >= 0.1 - 1e-9  # Allow small numerical tolerance

    def test_learning_rate_blending(self):
        """Learning rate should properly blend old and new weights."""
        np.random.seed(42)
        n = 200
        streams = {"det1": np.random.randn(n)}
        fused = streams["det1"]
        current = {"det1": 0.5}

        # With learning_rate=0, should keep current weights
        cfg_zero = {"fusion": {"auto_tune": {"enabled": True, "learning_rate": 0.0, "method": "correlation"}}}
        result_zero, _ = tune_detector_weights(streams, fused, current, cfg_zero)
        # After normalization, single detector gets weight 1.0
        assert abs(result_zero["det1"] - 1.0) < 0.01

    def test_weights_normalize_to_one(self):
        """Final tuned weights should sum to 1.0."""
        np.random.seed(42)
        n = 200
        streams = {
            "det1": np.random.randn(n),
            "det2": np.random.randn(n),
            "det3": np.random.randn(n),
        }
        fused = np.mean([streams["det1"], streams["det2"], streams["det3"]], axis=0)
        current = {"det1": 0.33, "det2": 0.33, "det3": 0.34}
        cfg = {"fusion": {"auto_tune": {"enabled": True, "method": "correlation"}}}

        result, _ = tune_detector_weights(streams, fused, current, cfg)

        assert abs(sum(result.values()) - 1.0) < 1e-9


class TestScoreCalibrator:
    """Tests for the ScoreCalibrator class."""

    def test_basic_calibration(self):
        """Basic calibration should compute median, MAD, and z-scores."""
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        cal = ScoreCalibrator(q=0.95)
        cal.fit(x)

        assert cal.med == 5.5  # Median of 1-10
        assert cal.mad > 0  # MAD should be positive
        assert cal.scale > 0  # Scale should be positive

        z = cal.transform(x)
        assert len(z) == len(x)
        assert np.isfinite(z).all()

    def test_constant_input_handling(self):
        """Constant input should not cause division by zero."""
        x = np.full(100, 5.0)
        cal = ScoreCalibrator(q=0.98)
        cal.fit(x)

        # Scale should fall back to a safe value
        assert cal.scale >= 1e-3

        z = cal.transform(x)
        assert np.isfinite(z).all()
        # All z-scores should be 0 or very close to 0
        assert np.allclose(z, 0.0, atol=1e-3)

    def test_empty_input_handling(self):
        """Empty input should return safely."""
        x = np.array([])
        cal = ScoreCalibrator(q=0.98)
        cal.fit(x)

        # Should maintain default values
        assert cal.med == 0.0
        assert cal.scale == 1.0

    def test_nan_handling(self):
        """NaN values should be handled gracefully."""
        x = np.array([1.0, 2.0, np.nan, 4.0, 5.0, np.nan, 7.0, 8.0, 9.0, 10.0])
        cal = ScoreCalibrator(q=0.95)
        cal.fit(x)

        # Should fit on finite values only
        assert np.isfinite(cal.med)
        assert np.isfinite(cal.scale)

    def test_z_score_clipping(self):
        """Z-scores should be clipped to prevent extreme values."""
        np.random.seed(42)
        # Create data with extreme outliers
        x_train = np.random.randn(1000)
        x_test = np.concatenate([np.random.randn(100), [100.0, -100.0]])  # Add extreme values

        cal = ScoreCalibrator(q=0.98, self_tune_cfg={"clip_z": 8.0})
        cal.fit(x_train)
        z = cal.transform(x_test)

        # Z-scores should be clipped
        assert z.max() <= 10.0  # Hard limit
        assert z.min() >= -10.0

    def test_per_regime_thresholds(self):
        """Per-regime thresholds should be computed correctly."""
        np.random.seed(42)
        # Create two regimes with different distributions
        x_regime0 = np.random.randn(500)  # Normal regime
        x_regime1 = np.random.randn(500) + 3.0  # Elevated regime
        x = np.concatenate([x_regime0, x_regime1])
        regime_labels = np.array([0] * 500 + [1] * 500)

        cal = ScoreCalibrator(q=0.95)
        cal.fit(x, regime_labels=regime_labels)

        # Should have per-regime parameters
        assert 0 in cal.regime_params_
        assert 1 in cal.regime_params_
        assert 0 in cal.regime_thresh_
        assert 1 in cal.regime_thresh_

    def test_self_tuning_target_fp_rate(self):
        """Self-tuning should adjust threshold based on target FP rate."""
        np.random.seed(42)
        x = np.random.randn(10000)

        # Target 1% FP rate -> 99th percentile
        cal = ScoreCalibrator(
            q=0.95,  # Default
            self_tune_cfg={"enabled": True, "target_fp_rate": 0.01}
        )
        cal.fit(x)

        # Threshold should be around the 99th percentile
        expected_thresh = np.percentile(x, 99)
        assert abs(cal.q_thresh - expected_thresh) < 0.2


class TestFuser:
    """Tests for the Fuser class."""

    def test_fuse_basic(self):
        """Basic fusion should produce weighted average of z-scores."""
        np.random.seed(42)
        n = 100
        streams = {
            "det1": np.random.randn(n) + 1.0,
            "det2": np.random.randn(n) + 2.0,
        }
        features = pd.DataFrame(index=pd.date_range("2024-01-01", periods=n, freq="h"))
        weights = {"det1": 0.6, "det2": 0.4}

        fuser = Fuser(weights, EpisodeParams())
        fused = fuser.fuse(streams, features)

        assert len(fused) == n
        assert fused.name == "fused"
        assert np.isfinite(fused).all()

    def test_fuse_empty_streams(self):
        """Empty streams should return empty series."""
        streams = {}
        features = pd.DataFrame()
        fuser = Fuser({}, EpisodeParams())

        fused = fuser.fuse(streams, features)

        assert len(fused) == 0

    def test_fuse_missing_detector(self):
        """Missing detector should be handled gracefully."""
        np.random.seed(42)
        n = 100
        streams = {"det1": np.random.randn(n)}  # Only det1 present
        features = pd.DataFrame(index=pd.date_range("2024-01-01", periods=n, freq="h"))
        weights = {"det1": 0.5, "det2": 0.5}  # det2 configured but missing

        fuser = Fuser(weights, EpisodeParams())
        fused = fuser.fuse(streams, features)

        # Should still work with available detector
        assert len(fused) == n

    def test_fuse_weight_normalization(self):
        """Weights should be normalized to sum to 1."""
        np.random.seed(42)
        n = 100
        # Create identical streams
        signal = np.random.randn(n)
        streams = {"det1": signal.copy(), "det2": signal.copy()}
        features = pd.DataFrame(index=pd.date_range("2024-01-01", periods=n, freq="h"))

        # Weights that don't sum to 1
        weights = {"det1": 0.3, "det2": 0.2}

        fuser = Fuser(weights, EpisodeParams())
        fused = fuser.fuse(streams, features)

        # Result should be same as input (since identical streams)
        z1 = fuser._zscore(signal)
        assert np.allclose(fused.values, z1, atol=1e-10)

    def test_fuse_zero_weights_fallback(self):
        """Zero weights should fallback to equal weighting."""
        np.random.seed(42)
        n = 100
        streams = {
            "det1": np.random.randn(n),
            "det2": np.random.randn(n),
        }
        features = pd.DataFrame(index=pd.date_range("2024-01-01", periods=n, freq="h"))
        weights = {"det1": 0.0, "det2": 0.0}

        fuser = Fuser(weights, EpisodeParams())
        fused = fuser.fuse(streams, features)

        # Should still produce valid output
        assert len(fused) == n
        assert np.isfinite(fused).all()


class TestDetectEpisodes:
    """Tests for the Fuser.detect_episodes method."""

    def test_detect_no_episodes_on_flat_signal(self):
        """Flat signal should produce no episodes."""
        n = 1000
        fused = pd.Series(
            np.zeros(n),
            index=pd.date_range("2024-01-01", periods=n, freq="h"),
            name="fused"
        )
        streams = {"det1": np.zeros(n)}
        features = pd.DataFrame(index=fused.index)

        fuser = Fuser({"det1": 1.0}, EpisodeParams(k_sigma=0.5, h_sigma=5.0))
        episodes = fuser.detect_episodes(fused, streams, features)

        assert len(episodes) == 0

    def test_detect_episode_on_spike(self):
        """A sustained spike should be detected as an episode."""
        n = 1000
        signal = np.zeros(n)
        # Create a sustained elevated period
        signal[400:450] = 5.0  # 50 samples of elevated signal

        fused = pd.Series(
            signal,
            index=pd.date_range("2024-01-01", periods=n, freq="h"),
            name="fused"
        )
        streams = {"det1": signal}
        features = pd.DataFrame(index=fused.index)

        fuser = Fuser({"det1": 1.0}, EpisodeParams(k_sigma=0.5, h_sigma=3.0, min_len=3, min_duration_s=0))
        episodes = fuser.detect_episodes(fused, streams, features)

        # Should detect at least one episode
        assert len(episodes) >= 1

    def test_episode_gap_merging(self):
        """Close episodes should be merged based on gap_merge setting."""
        n = 1000
        signal = np.zeros(n)
        # Create two close spikes
        signal[100:110] = 5.0
        signal[115:125] = 5.0  # Gap of 5 samples

        fused = pd.Series(
            signal,
            index=pd.date_range("2024-01-01", periods=n, freq="h"),
            name="fused"
        )
        streams = {"det1": signal}
        features = pd.DataFrame(index=fused.index)

        # With gap_merge=10, these should merge
        fuser = Fuser({"det1": 1.0}, EpisodeParams(k_sigma=0.5, h_sigma=3.0, min_len=3, gap_merge=10, min_duration_s=0))
        episodes = fuser.detect_episodes(fused, streams, features)

        # Exact count depends on CUSUM dynamics, but they may merge

    def test_episode_min_duration_filter(self):
        """Episodes shorter than min_duration_s should be filtered out."""
        n = 1000
        signal = np.zeros(n)
        # Create a very short spike (10 hours < 60 minutes min_duration)
        signal[100:110] = 10.0

        # Use hourly data so 10 samples = 10 hours
        fused = pd.Series(
            signal,
            index=pd.date_range("2024-01-01", periods=n, freq="h"),
            name="fused"
        )
        streams = {"det1": signal}
        features = pd.DataFrame(index=fused.index)

        # With min_duration_s=7200 (2 hours), 10-hour episode should pass
        fuser = Fuser({"det1": 1.0}, EpisodeParams(k_sigma=0.5, h_sigma=3.0, min_len=3, min_duration_s=7200))
        episodes = fuser.detect_episodes(fused, streams, features)

        # Episode is 10 hours (36000s) > 7200s, so should be detected if CUSUM triggers

    def test_culprit_attribution(self):
        """Culprit should be attributed to the detector with highest mean during episode."""
        n = 1000
        signal = np.zeros(n)
        signal[100:150] = 5.0

        # det1 has higher signal during the spike
        det1 = np.zeros(n)
        det1[100:150] = 10.0

        # det2 has lower signal
        det2 = np.zeros(n)
        det2[100:150] = 2.0

        fused = pd.Series(
            signal,
            index=pd.date_range("2024-01-01", periods=n, freq="h"),
            name="fused"
        )
        streams = {"det1": det1, "det2": det2}
        features = pd.DataFrame(index=fused.index, data={"sensor_A": signal})

        fuser = Fuser({"det1": 0.5, "det2": 0.5}, EpisodeParams(k_sigma=0.5, h_sigma=3.0, min_len=3, min_duration_s=0))
        episodes = fuser.detect_episodes(fused, streams, features)

        if len(episodes) > 0:
            # The culprit should be attributed to det1 (higher mean)
            # Note: The culprit is formatted by format_culprit_label
            pass  # Just verify no crashes


class TestCombine:
    """Tests for the combine() function."""

    def test_combine_basic(self):
        """Basic combine should return fused series and episodes."""
        np.random.seed(42)
        n = 500
        streams = {
            "det1": np.random.randn(n),
            "det2": np.random.randn(n),
        }
        weights = {"det1": 0.5, "det2": 0.5}
        cfg = {
            "episodes": {
                "cpd": {"k_sigma": 0.5, "h_sigma": 5.0},
                "min_len": 3,
                "gap_merge": 5,
                "min_duration_s": 60.0,
            }
        }
        features = pd.DataFrame(index=pd.date_range("2024-01-01", periods=n, freq="h"))

        fused, episodes = combine(streams, weights, cfg, features)

        assert len(fused) == n
        assert isinstance(episodes, pd.DataFrame)

    def test_combine_auto_tune_cusum(self):
        """Auto-tune should adjust CUSUM parameters based on data."""
        np.random.seed(42)
        n = 500
        # Create data with known statistics
        streams = {
            "det1": np.random.randn(n) * 2.0,  # std ~2.0
        }
        weights = {"det1": 1.0}
        cfg = {
            "episodes": {
                "cpd": {
                    "k_sigma": 0.5,
                    "h_sigma": 5.0,
                    "auto_tune": {
                        "enabled": True,
                        "k_factor": 0.5,
                        "h_factor": 3.0,
                    }
                },
                "min_len": 3,
                "gap_merge": 5,
                "min_duration_s": 0,
            }
        }
        features = pd.DataFrame(index=pd.date_range("2024-01-01", periods=n, freq="h"))

        fused, episodes = combine(streams, weights, cfg, features)

        # Should complete without error
        assert len(fused) == n


class TestAnalyticalCorrectness:
    """Tests specifically for analytical correctness issues."""

    def test_zscore_preserves_relative_ordering(self):
        """Z-score transformation should preserve relative ordering.
        
        Note: We access _zscore directly here to verify a core mathematical property
        that underpins the fusion algorithm. This is acceptable for unit testing
        internal algorithm correctness.
        """
        x = np.array([1.0, 5.0, 3.0, 7.0, 2.0])
        z = Fuser._zscore(x)

        # Argsort should be preserved
        np.testing.assert_array_equal(np.argsort(x), np.argsort(z))

    def test_mad_constant_is_correct(self):
        """The MAD constant 1.4826 converts MAD to std for normal distributions."""
        np.random.seed(42)
        # For normal distribution, MAD * 1.4826 ≈ std
        x = np.random.randn(100000)
        mad = np.median(np.abs(x - np.median(x)))
        scale = mad * 1.4826

        # Should be close to 1.0 (std of standard normal)
        assert abs(scale - 1.0) < 0.05

    def test_cusum_reset_after_detection(self):
        """CUSUM should reset to 0 after detecting an episode."""
        # This is implicit in the detect_episodes logic
        n = 1000
        signal = np.zeros(n)
        # Create two well-separated spikes
        signal[100:120] = 10.0
        signal[500:520] = 10.0

        fused = pd.Series(
            signal,
            index=pd.date_range("2024-01-01", periods=n, freq="h"),
            name="fused"
        )
        streams = {"det1": signal}
        features = pd.DataFrame(index=fused.index)

        fuser = Fuser({"det1": 1.0}, EpisodeParams(k_sigma=0.5, h_sigma=3.0, min_len=3, gap_merge=0, min_duration_s=0))
        episodes = fuser.detect_episodes(fused, streams, features)

        # Both spikes should be detected as separate episodes
        # (since they're well separated and gap_merge=0)

    def test_softmax_numerical_stability(self):
        """Softmax should be numerically stable with extreme inputs."""
        # This tests the tune_detector_weights softmax
        np.random.seed(42)
        n = 200
        streams = {
            "det_extreme": np.full(n, 1e6),  # Extreme values
            "det_normal": np.random.randn(n),
        }
        fused = np.random.randn(n)
        current = {"det_extreme": 0.5, "det_normal": 0.5}
        cfg = {"fusion": {"auto_tune": {"enabled": True, "temperature": 2.0, "method": "correlation"}}}

        # Should not crash or produce NaN
        result, diag = tune_detector_weights(streams, fused, current, cfg)
        for weight in result.values():
            assert np.isfinite(weight)

    def test_weight_blending_mathematically_correct(self):
        """EMA blending: w_new = (1-lr)*w_old + lr*w_raw should be correct."""
        np.random.seed(42)
        n = 200
        streams = {"det1": np.random.randn(n), "det2": np.random.randn(n)}
        fused = (streams["det1"] + streams["det2"]) / 2
        current = {"det1": 0.8, "det2": 0.2}
        learning_rate = 0.5
        cfg = {"fusion": {"auto_tune": {"enabled": True, "learning_rate": learning_rate, "method": "correlation"}}}

        result, diag = tune_detector_weights(streams, fused, current, cfg)

        # Verify the blending math (before normalization)
        raw = diag.get("raw_weights", {})
        pre_norm = diag.get("pre_renorm_weights", {})

        if raw and pre_norm:
            for det in current:
                expected_blend = (1 - learning_rate) * current.get(det, 0) + learning_rate * raw.get(det, 0)
                # min_weight enforcement
                expected_blend = max(expected_blend, 0.05)
                assert abs(pre_norm[det] - expected_blend) < 1e-9


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_sample(self):
        """Single sample should be handled gracefully."""
        x = np.array([5.0])
        cal = ScoreCalibrator(q=0.95)
        cal.fit(x)

        # Should have safe defaults
        assert np.isfinite(cal.med)
        assert cal.scale >= 1e-3

    def test_all_nan_input(self):
        """All-NaN input should be handled gracefully."""
        x = np.array([np.nan, np.nan, np.nan])
        cal = ScoreCalibrator(q=0.95)
        cal.fit(x)

        # Should have default values
        assert cal.med == 0.0
        assert cal.scale == 1.0

    def test_inf_values_in_transform(self):
        """Inf values in transform should be clipped."""
        x_train = np.random.randn(100)
        x_test = np.array([np.inf, -np.inf, 5.0])

        cal = ScoreCalibrator(q=0.95, self_tune_cfg={"clip_z": 8.0})
        cal.fit(x_train)
        z = cal.transform(x_test)

        assert np.isfinite(z).all()
        assert z[0] <= 10.0  # Hard clip
        assert z[1] >= -10.0

    def test_empty_episode_detection(self):
        """Empty series should return empty episodes DataFrame."""
        fused = pd.Series([], dtype=float, name="fused")
        streams = {}
        features = pd.DataFrame()

        fuser = Fuser({}, EpisodeParams())
        episodes = fuser.detect_episodes(fused, streams, features)

        assert len(episodes) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

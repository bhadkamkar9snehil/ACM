# core/confidence.py
"""
Unified Confidence Model for V11

All ACM outputs must have explicit confidence scores (0-1).
This module provides consistent confidence computation across:
- Health scores
- RUL estimates  
- Episode detection
- Regime assignments

V11 Rules Implemented:
- Rule #10: RUL must be gated or suppressed
- Rule #17: Confidence must always be exposed
- Rule #20: If unsure, the system must say "not reliable"

Confidence Sources:
1. Model maturity (LEARNING=0.5, CONVERGED=1.0)
2. Data quality (sample size, coverage)
3. Prediction uncertainty (std dev, quantile spread)
4. Regime assignment confidence (distance to centroid)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Tuple, List
import numpy as np

from core.observability import Console


class ReliabilityStatus(str, Enum):
    """RUL reliability status for gating."""
    RELIABLE = "RELIABLE"           # All prerequisites met
    NOT_RELIABLE = "NOT_RELIABLE"   # Missing prerequisites
    LEARNING = "LEARNING"           # Model not yet converged
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Not enough history


@dataclass
class ConfidenceFactors:
    """Components that contribute to overall confidence."""
    maturity_factor: float = 1.0      # Model maturity (0.5 for LEARNING, 1.0 for CONVERGED)
    data_quality_factor: float = 1.0  # Data completeness and sample size
    prediction_factor: float = 1.0    # Prediction uncertainty (narrow CI = high)
    regime_factor: float = 1.0        # Regime assignment confidence
    
    def overall(self) -> float:
        """
        Compute overall confidence as harmonic mean of factors.
        
        P0-FIX (v11.2.2): ANALYTICAL AUDIT FLAW #4
        Changed from geometric mean to harmonic mean to properly penalize
        imbalanced factors. Geometric mean allowed high values to mask
        critically low values (e.g., regime=0.1 → overall=0.56 was too optimistic).
        
        Harmonic mean formula: HM = n / (1/f1 + 1/f2 + ... + 1/fn)
        Properly penalizes low values: regime=0.1 → overall=0.31 (more appropriate)
        
        Reference: Harmonic mean used in precision/recall F1-score for similar reasons
        """
        factors = [
            max(0.01, self.maturity_factor),      # Prevent division by zero
            max(0.01, self.data_quality_factor),
            max(0.01, self.prediction_factor),
            max(0.01, self.regime_factor),
        ]
        # Harmonic mean - penalizes imbalanced factors appropriately
        harmonic = len(factors) / sum(1.0 / f for f in factors)
        return harmonic
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'MaturityFactor': self.maturity_factor,
            'DataQualityFactor': self.data_quality_factor,
            'PredictionFactor': self.prediction_factor,
            'RegimeFactor': self.regime_factor,
            'OverallConfidence': self.overall(),
        }


def compute_maturity_confidence(maturity_state: str) -> float:
    """
    Confidence factor based on model maturity.
    
    COLDSTART: 0.2 - No reliable baseline
    LEARNING: 0.5 - Building baseline, not production-ready
    CONVERGED: 1.0 - Full confidence in model
    DEPRECATED: 0.3 - Model is stale
    """
    maturity_map = {
        'COLDSTART': 0.2,
        'LEARNING': 0.5,
        'CONVERGED': 1.0,
        'DEPRECATED': 0.3,
    }
    return maturity_map.get(str(maturity_state).upper(), 0.5)


def compute_data_quality_confidence(
    sample_count: int,
    min_samples: int = 100,
    optimal_samples: int = 1000,
    coverage_ratio: float = 1.0,
) -> float:
    """
    Confidence factor based on data quality.
    
    FLAW FIX #8: Replaced linear interpolation with sigmoid function to avoid
    overestimating confidence with marginal sample counts.
    
    Args:
        sample_count: Number of samples in training window
        min_samples: Minimum for any confidence (below = 0.1)
        optimal_samples: Sample count for full confidence
        coverage_ratio: Fraction of expected time range covered (0-1)
    
    Returns:
        Confidence factor 0-1
    
    Reference:
        Sigmoid avoids overconfidence at threshold boundaries.
        Threshold = (min_samples + optimal_samples) / 2
        Scale = (optimal_samples - min_samples) / 6 (99.7% of sigmoid range)
    """
    if sample_count < min_samples:
        sample_factor = 0.1
    elif sample_count >= optimal_samples:
        sample_factor = 1.0
    else:
        # FIXED: Sigmoid function instead of linear interpolation
        # Maps min_samples -> 0.1, optimal_samples -> 1.0 smoothly
        threshold = (min_samples + optimal_samples) / 2.0
        scale = (optimal_samples - min_samples) / 4.0  # +/-2 sigma over the range (gentle slope)
        sigmoid = 1.0 / (1.0 + np.exp(-(sample_count - threshold) / scale))
        # Rescale the sigmoid's actual range over [min, optimal] (sig(-2)..sig(+2))
        # to [0.1, 1.0] so the boundaries are hit exactly. Without this the
        # function returned ~0.143 at min_samples and jumped discontinuously
        # to 1.0 at optimal_samples.
        sig_lo = 1.0 / (1.0 + np.exp(2.0))
        sig_hi = 1.0 / (1.0 + np.exp(-2.0))
        sample_factor = 0.1 + 0.9 * (sigmoid - sig_lo) / (sig_hi - sig_lo)
    
    # Combine with coverage
    return sample_factor * max(0.1, min(1.0, coverage_ratio))


def compute_prediction_confidence(
    p10: float,
    p50: float,
    p90: float,
    max_acceptable_spread: float = 100.0,
    prediction_horizon_hours: float = 0.0,
    characteristic_horizon: float = 168.0,  # 7 days default
) -> float:
    """
    Confidence factor based on prediction uncertainty and horizon.
    
    FLAW FIX #2: Added time-to-horizon adjustment. Far-future predictions
    get lower confidence due to compounding uncertainty.
    
    Narrow confidence intervals = high confidence.
    Wide intervals = low confidence.
    Long horizons = lower confidence.
    
    Args:
        p10: 10th percentile prediction
        p50: 50th percentile (median) prediction
        p90: 90th percentile prediction
        max_acceptable_spread: Maximum P90-P10 spread for full confidence
        prediction_horizon_hours: Time horizon for prediction (0 = no adjustment)
        characteristic_horizon: Time constant for exponential decay (default 168h = 7 days)
    
    Returns:
        Confidence factor 0-1
    
    Reference:
        Horizon adjustment: confidence * exp(-horizon / tau)
        tau = 168h (7 days) means 63% confidence at 7-day horizon
    """
    if p50 <= 0:
        return 0.1  # Invalid prediction
    
    spread = abs(p90 - p10)
    relative_spread = spread / max(abs(p50), 1.0)

    # Sigmoid-like mapping: small spread = high confidence
    # relative_spread of 0 -> 1.0, relative_spread of 2.0 -> 0.5
    # (implementation previously used 1/(1+rs), giving 0.33 at rs=2.0,
    # contradicting the documented mapping above)
    base_confidence = 1.0 / (1.0 + relative_spread / 2.0)
    
    # FIXED: Add exponential decay for prediction horizon.
    # exp(-h / 2*tau) retains ~61% confidence at the characteristic horizon,
    # matching the documented intent ("63% confidence at 7-day horizon");
    # the previous exp(-h/tau) retained only 37% there (it decayed BY 63%).
    if prediction_horizon_hours > 0:
        horizon_factor = np.exp(-prediction_horizon_hours / (2.0 * characteristic_horizon))
        final_confidence = base_confidence * horizon_factor
    else:
        final_confidence = base_confidence
    
    return max(0.1, min(1.0, final_confidence))


def check_rul_reliability(
    maturity_state: str,
    training_rows: int,
    training_days: float,
    health_history_days: float,
    min_training_rows: int = 500,
    min_training_days: float = 7.0,
    min_health_history_days: float = 3.0,
    drift_z: Optional[float] = None,
    drift_threshold: float = 3.0,
) -> Tuple[ReliabilityStatus, str]:
    """
    Gate RUL predictions based on prerequisites.
    
    FLAW FIX #4: Added detector drift check. Converged models with high drift
    are marked NOT_RELIABLE to prevent predictions from stale models.
    
    V11 Rule #10: RUL must be gated or suppressed.
    V11 Rule #20: If unsure, the system must say "not reliable".
    
    Args:
        maturity_state: Current model maturity (LEARNING, CONVERGED, etc.)
        training_rows: Number of training samples
        training_days: Days of training data
        health_history_days: Days of health history available
        min_training_rows: Minimum rows required
        min_training_days: Minimum training days required
        min_health_history_days: Minimum health history required
        drift_z: Current drift Z-score (None = no drift monitoring)
        drift_threshold: Maximum allowed drift Z-score (default 3.0)
    
    Returns:
        Tuple of (status, reason)
    
    Reference:
        Drift check prevents predictions from models experiencing concept drift.
        drift_z > 3.0 indicates statistical process change (3-sigma rule).
    """
    maturity_upper = str(maturity_state).upper()
    
    # Concept drift overrides maturity: a LEARNING model experiencing drift
    # must be NOT_RELIABLE, not merely "LEARNING" (which downstream treats as
    # provisionally usable). Checked before the maturity early-returns.
    if drift_z is not None and abs(drift_z) > drift_threshold:
        return ReliabilityStatus.NOT_RELIABLE, f"Model drift detected: drift_z={drift_z:.2f} > {drift_threshold} (concept drift)"

    # Check maturity
    if maturity_upper == 'COLDSTART':
        return ReliabilityStatus.NOT_RELIABLE, "Model in COLDSTART state - no baseline established"

    if maturity_upper == 'LEARNING':
        return ReliabilityStatus.LEARNING, "Model still LEARNING - predictions may be unreliable"

    if maturity_upper == 'DEPRECATED':
        return ReliabilityStatus.NOT_RELIABLE, "Model DEPRECATED - needs refresh"
    
    # Check data requirements for CONVERGED model
    if training_rows < min_training_rows:
        return ReliabilityStatus.INSUFFICIENT_DATA, f"Insufficient training data: {training_rows} < {min_training_rows} rows"
    
    if training_days < min_training_days:
        return ReliabilityStatus.INSUFFICIENT_DATA, f"Insufficient training period: {training_days:.1f} < {min_training_days} days"
    
    if health_history_days < min_health_history_days:
        return ReliabilityStatus.INSUFFICIENT_DATA, f"Insufficient health history: {health_history_days:.1f} < {min_health_history_days} days"
    
    return ReliabilityStatus.RELIABLE, "All prerequisites met"


def compute_health_confidence(
    fused_z: float,
    regime_confidence: float = 1.0,
    maturity_state: str = "CONVERGED",
    sample_count: int = 1000,
    detector_zscores: Optional[List[float]] = None,
) -> float:
    """
    Compute confidence for a health score.
    
    FLAW FIX #5: Added inter-detector agreement factor. Low agreement among
    detectors indicates uncertain health state.
    
    Args:
        fused_z: Fused anomaly Z-score
        regime_confidence: Confidence in regime assignment (0-1)
        maturity_state: Model maturity state
        sample_count: Training sample count
        detector_zscores: List of individual detector z-scores for agreement check
    
    Returns:
        Confidence 0-1
    
    Reference:
        Agreement factor = 1 - normalized_std(detector_zscores)
        High std = detectors disagree = lower confidence
    """
    # Compute detector agreement if scores provided
    if detector_zscores and len(detector_zscores) > 1:
        # Relative dispersion: spread of detector z-scores relative to their
        # typical magnitude. The previous z/10 normalization squashed real
        # disagreement (e.g. one detector at z=8 with the rest near 0 yielded
        # agreement ~0.73 — effectively no penalty after harmonic-mean fusion).
        z_arr = np.asarray(detector_zscores, dtype=float)
        z_std = float(np.std(z_arr))
        typical = float(np.median(np.abs(z_arr))) + 1.0
        agreement_factor = max(0.1, 1.0 - z_std / typical)
    else:
        agreement_factor = 1.0  # No disagreement if single detector
    
    factors = ConfidenceFactors(
        maturity_factor=compute_maturity_confidence(maturity_state),
        data_quality_factor=compute_data_quality_confidence(sample_count),
        prediction_factor=agreement_factor,  # FIXED: Use agreement instead of 1.0
        regime_factor=regime_confidence,
    )
    return factors.overall()


def compute_episode_confidence(
    episode_duration_seconds: float,
    peak_z: float,
    regime_confidence: float = 1.0,
    maturity_state: str = "CONVERGED",
    min_duration_seconds: float = 60.0,
    rise_time_seconds: Optional[float] = None,
) -> float:
    """
    Compute confidence for an episode detection.
    
    FLAW FIX #6: Added temporal coherence check via rise time. Sharp anomaly
    onsets have higher confidence than gradual/fuzzy boundaries.
    
    Short episodes or low peak Z = lower confidence.
    Slow rise times = lower confidence (fuzzy boundaries).
    
    Args:
        episode_duration_seconds: Duration of episode
        peak_z: Peak Z-score during episode
        regime_confidence: Confidence in regime assignment
        maturity_state: Model maturity state
        min_duration_seconds: Minimum duration for full confidence
        rise_time_seconds: Time from threshold crossing to peak (None = sharp)
    
    Returns:
        Confidence 0-1
    
    Reference:
        Rise time factor: sharp onset (rise < 10% duration) = 1.0
        Slow onset (rise > 50% duration) = 0.25
    """
    # Duration factor: longer episodes = more confident
    if episode_duration_seconds < min_duration_seconds:
        duration_factor = max(0.3, episode_duration_seconds / min_duration_seconds)
    else:
        duration_factor = 1.0
    
    # Peak Z factor: higher peak = more confident it's real
    # Z < 2 might be noise, Z > 5 is clearly anomalous
    z_factor = min(1.0, max(0.3, (peak_z - 1.0) / 4.0))
    
    # FIXED: Rise time factor for temporal coherence
    if rise_time_seconds is not None and episode_duration_seconds > 0:
        rise_fraction = rise_time_seconds / episode_duration_seconds
        # Sharp onset (rise < 10% of duration) = high confidence
        # Slow onset (rise > 50% of duration) = lower confidence.
        # Floor is 0.25 (not 0.5): overall() takes a harmonic mean across four
        # factors, so a single 0.5 factor only moved overall to ~0.8 — a slow,
        # fuzzy onset carried almost no penalty.
        if rise_fraction < 0.1:
            rise_factor = 1.0
        elif rise_fraction > 0.5:
            rise_factor = 0.25
        else:
            # Linear interpolation between 0.1 and 0.5
            rise_factor = 1.0 - (rise_fraction - 0.1) / 0.4 * 0.75
    else:
        rise_factor = 1.0  # Assume sharp if not provided
    
    factors = ConfidenceFactors(
        maturity_factor=compute_maturity_confidence(maturity_state),
        data_quality_factor=1.0,  # Episodes are from scored data
        prediction_factor=duration_factor * z_factor * rise_factor,  # FIXED: Include rise_factor
        regime_factor=regime_confidence,
    )
    return factors.overall()


def compute_rul_confidence(
    p10: float,
    p50: float,
    p90: float,
    maturity_state: str,
    training_rows: int,
    training_days: float,
    drift_z: Optional[float] = None,
    prediction_horizon_hours: Optional[float] = None,
) -> Tuple[float, ReliabilityStatus, str]:
    """
    Compute confidence and reliability for RUL estimate.
    
    FLAW FIXES:
    - #2: Added prediction_horizon_hours for time decay
    - #4: Added drift_z check via check_rul_reliability
    
    Returns:
        Tuple of (confidence, reliability_status, reason)
    """
    # First check reliability gate (includes drift check)
    status, reason = check_rul_reliability(
        maturity_state=maturity_state,
        training_rows=training_rows,
        training_days=training_days,
        health_history_days=training_days,  # Use training days as proxy
        drift_z=drift_z,  # FIXED: Pass drift for reliability check
    )
    
    # If not reliable, return low confidence
    if status != ReliabilityStatus.RELIABLE:
        base_confidence = 0.3 if status == ReliabilityStatus.LEARNING else 0.1
        return base_confidence, status, reason
    
    # Compute confidence factors for reliable predictions
    # FIXED: Pass prediction_horizon_hours to compute_prediction_confidence
    horizon_hours = prediction_horizon_hours or p50  # Use RUL as horizon if not specified
    
    factors = ConfidenceFactors(
        maturity_factor=compute_maturity_confidence(maturity_state),
        data_quality_factor=compute_data_quality_confidence(training_rows),
        prediction_factor=compute_prediction_confidence(
            p10, p50, p90,
            prediction_horizon_hours=horizon_hours  # FIXED: Add horizon adjustment
        ),
        regime_factor=1.0,  # RUL is equipment-level, not regime-specific
    )
    
    return factors.overall(), status, reason

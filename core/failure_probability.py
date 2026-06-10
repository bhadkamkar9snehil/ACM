"""
Failure Probability Estimation (v10.0.0)

Pure functions for converting health forecasts to failure probabilities.
Replaces duplicate logic from forecasting.py (lines 238-290, 1044-1104).

Key Features:
- Health-to-failure probability mapping via normal CDF
- Survival curve computation (reliability function)
- Hazard rate (instantaneous failure rate)
- Mean Time To Failure (MTTF) estimation
- Research-backed thresholds and transformations

References:
- Jardine & Tsang (2013): "Maintenance, Replacement, and Reliability" - failure modeling
- ISO 13381-1:2015: Prognostics and health management - failure threshold definitions
- Reliability Theory (Barlow & Proschan 1975): Survival/hazard relationships
"""

from typing import Optional
import numpy as np
from scipy import stats
from scipy import integrate


def health_to_failure_probability(
    health_forecast: np.ndarray,
    failure_threshold: float = 70.0,
    health_std: float = 10.0
) -> np.ndarray:
    """
    Convert health forecast to failure probability via normal CDF.
    
    Mathematical Model:
    - P(failure | health) = P(health < threshold)
    - Assume health ~ Normal(μ_forecast, σ_health)
    - P(failure) = Φ((threshold - μ_forecast) / σ_health)
    
    Where Φ is the standard normal CDF.
    
    Interpretation:
    - health >> threshold → P(failure) ≈ 0 (healthy)
    - health ≈ threshold → P(failure) ≈ 0.5 (marginal)
    - health << threshold → P(failure) ≈ 1 (critical)
    
    References:
    - ISO 13381-1:2015: Failure threshold typically 40-80% of nominal health
    - Normal approximation valid when health variance is moderate
    
    Args:
        health_forecast: Forecasted health values (0-100 scale)
        failure_threshold: Health level below which failure is imminent (default 70.0)
        health_std: Standard deviation of health noise (default 10.0)
    
    Returns:
        Failure probabilities (0-1 scale), same shape as health_forecast
    """
    if health_std <= 0:
        health_std = 10.0  # Guard against invalid std
    
    # Z-score: (threshold - forecast) / std
    # Positive z-score means forecast is below threshold (higher failure risk)
    z_scores = (failure_threshold - health_forecast) / health_std
    
    # CDF gives P(X < threshold) = P(failure)
    failure_probs = stats.norm.cdf(z_scores)
    
    # Clamp to [0, 1]
    failure_probs = np.clip(failure_probs, 0.0, 1.0)
    
    return failure_probs


def compute_survival_curve(failure_probabilities: np.ndarray) -> np.ndarray:
    """
    Compute survival curve (reliability function) from failure probabilities.

    Mathematical Definition:
    - S(t) = 1 - F(t) = P(T > t)
    - Where F(t) is cumulative failure probability
    - S(t) represents probability equipment survives to time t

    NOTE: monotonicity is intentionally NOT enforced. The curve is derived
    from a health FORECAST, not from time-to-event data — when the forecast
    improves (transient passed, maintenance reset, recovery), survival is
    allowed to rise so RUL can recover. The old in-place flattening locked
    every transient spike into a permanently pessimistic curve.

    Args:
        failure_probabilities: Cumulative failure probabilities F(t)

    Returns:
        Survival probabilities S(t) = 1 - F(t)
    """
    return np.clip(1.0 - failure_probabilities, 0.0, 1.0)


def compute_hazard_rate(
    failure_probabilities: np.ndarray,
    dt_hours: float = 1.0
) -> np.ndarray:
    """
    Compute discrete hazard rate (instantaneous failure rate) from cumulative failure probabilities.
    
    Mathematical Derivation:
    - Continuous: λ(t) = f(t) / S(t) = -d[ln S(t)] / dt
    - Discrete: λ[i] = [F[i] - F[i-1]] / [S[i-1] * dt]
    - Where F = cumulative failure prob, S = survival prob
    
    Physical Interpretation:
    - λ(t) = probability of failure in next dt, given survival to t
    - Units: failures per hour
    - Increasing λ(t) indicates accelerating degradation (wear-out phase)
    - Constant λ(t) indicates random failures (useful life phase)
    
    References:
    - Reliability Engineering (Ebeling 2010): Hazard rate fundamentals
    - ISO 13381-1:2015: Prognostics terminology
    
    Args:
        failure_probabilities: Cumulative failure probabilities F(t)
        dt_hours: Time interval between observations (hours)
    
    Returns:
        Hazard rates λ(t) in failures per hour
    """
    n = len(failure_probabilities)
    if n == 0:
        return np.array([])
    
    # Compute survival probabilities
    survival_probs = compute_survival_curve(failure_probabilities)
    
    # Initialize hazard rate array
    hazard_rates = np.zeros(n)
    
    # First point: use forward difference
    if n > 1:
        delta_f = failure_probabilities[1] - failure_probabilities[0]
        s_prev = max(survival_probs[0], 1e-6)  # Guard against division by zero
        hazard_rates[0] = max(0.0, delta_f / (s_prev * dt_hours))
    
    # Subsequent points: use backward difference
    for i in range(1, n):
        delta_f = failure_probabilities[i] - failure_probabilities[i - 1]
        s_prev = max(survival_probs[i - 1], 1e-6)
        hazard_rates[i] = max(0.0, delta_f / (s_prev * dt_hours))
    
    # Clamp extreme values (hazard rate should be reasonable)
    hazard_rates = np.clip(hazard_rates, 0.0, 1.0)  # Max 1 failure/hour
    
    return hazard_rates


def mean_time_to_failure(
    survival_probabilities: np.ndarray,
    dt_hours: float = 1.0
) -> float:
    """
    Estimate Mean Time To Failure (MTTF) from survival curve.
    
    Mathematical Definition:
    - MTTF = ∫[0,∞] S(t) dt
    - Discrete approximation: MTTF ≈ Σ S[i] * dt
    
    Physical Interpretation:
    - Expected remaining lifetime in hours
    - Area under survival curve
    - Lower MTTF indicates imminent failure
    
    Limitations:
    - Assumes survival curve extends to S(t) ≈ 0
    - Truncated forecasts underestimate MTTF
    - Use with caution for short forecast horizons
    
    References:
    - Reliability Engineering (Ebeling 2010): MTTF definition
    - Jardine & Tsang (2013): MTTF estimation from prognostics
    
    Args:
        survival_probabilities: Survival curve S(t)
        dt_hours: Time interval between observations (hours)
    
    Returns:
        Mean Time To Failure in hours
    """
    if len(survival_probabilities) == 0:
        return 0.0
    
    # Trapezoidal integration: MTTF = ∫ S(t) dt
    mttf = float(integrate.trapezoid(survival_probabilities, dx=dt_hours))
    
    # Guard against negative/invalid values
    mttf = max(0.0, mttf)
    
    return mttf


def compute_failure_statistics(
    health_forecast: np.ndarray,
    failure_threshold: float = 70.0,
    health_std: float = 10.0,
    dt_hours: float = 1.0
) -> dict:
    """
    Compute comprehensive failure statistics from health forecast.
    
    Aggregates all failure probability metrics in one pass:
    - Failure probabilities F(t)
    - Survival probabilities S(t)
    - Hazard rates λ(t)
    - Mean Time To Failure (MTTF)
    - Time to 50% failure probability (median RUL proxy)
    
    Args:
        health_forecast: Forecasted health values
        failure_threshold: Health threshold for failure definition
        health_std: Standard deviation of health noise
        dt_hours: Time interval between observations (hours)
    
    Returns:
        Dictionary with keys:
        - 'failure_probs': F(t) array
        - 'survival_probs': S(t) array
        - 'hazard_rates': λ(t) array
        - 'mttf_hours': Mean Time To Failure
        - 'median_rul_hours': Time to 50% failure probability
        - 'max_failure_prob': Maximum failure probability in forecast horizon
    """
    # Compute failure probabilities
    failure_probs = health_to_failure_probability(
        health_forecast,
        failure_threshold=failure_threshold,
        health_std=health_std
    )
    
    # Compute survival curve
    survival_probs = compute_survival_curve(failure_probs)
    
    # Compute hazard rates
    hazard_rates = compute_hazard_rate(failure_probs, dt_hours=dt_hours)
    
    # Compute MTTF
    mttf = mean_time_to_failure(survival_probs, dt_hours=dt_hours)
    
    # Find median RUL (time to 50% failure probability)
    median_rul_hours = 0.0
    for i, fp in enumerate(failure_probs):
        if fp >= 0.5:
            median_rul_hours = i * dt_hours
            break
    if median_rul_hours == 0.0 and len(failure_probs) > 0:
        # If never exceeds 50%, use last index
        median_rul_hours = len(failure_probs) * dt_hours
    
    # Maximum failure probability
    max_failure_prob = float(np.max(failure_probs)) if len(failure_probs) > 0 else 0.0
    
    return {
        'failure_probs': failure_probs,
        'survival_probs': survival_probs,
        'hazard_rates': hazard_rates,
        'mttf_hours': mttf,
        'median_rul_hours': median_rul_hours,
        'max_failure_prob': max_failure_prob
    }


def health_to_rul_simple(
    current_health: float,
    failure_threshold: float = 70.0,
    degradation_rate: float = 0.1
) -> float:
    """
    Simple linear RUL estimate (no uncertainty).
    
    Formula:
    - RUL = (current_health - failure_threshold) / degradation_rate
    
    Assumptions:
    - Linear degradation at constant rate
    - No uncertainty quantification
    - Deterministic model
    
    Use Case:
    - Quick RUL estimate for dashboards
    - Fallback when Monte Carlo simulation unavailable
    
    Args:
        current_health: Current health index value
        failure_threshold: Health threshold for failure
        degradation_rate: Health degradation per hour (positive = declining)
    
    Returns:
        Remaining Useful Life in hours (0 if already below threshold)
    """
    if current_health <= failure_threshold:
        return 0.0
    
    if degradation_rate <= 0:
        return float('inf')  # Not degrading
    
    rul_hours = (current_health - failure_threshold) / degradation_rate
    
    return max(0.0, rul_hours)


# =============================================================================
# WEIBULL HAZARD MODEL (v10.1.0)
# =============================================================================
# Replaces heuristic hazard = rate/margin with proper survival analysis
# Reference: Reliability Engineering (Ebeling 2010), Lawless (2003) Statistical Models
# =============================================================================

class WeibullHazardModel:
    """
    Weibull-based hazard rate model for proper survival analysis.
    
    The Weibull distribution is the standard choice for reliability modeling because:
    1. Can model increasing (wear-out), constant (random), or decreasing (infant mortality) hazard
    2. Has closed-form expressions for hazard, survival, and MTTF
    3. Widely used in prognostics and health management (ISO 13381-1)
    
    Hazard Function:
        λ(t) = (β/η) * (t/η)^(β-1)
    
    Where:
        β (shape): β < 1: decreasing failure rate (infant mortality)
                   β = 1: constant failure rate (random failures, equals exponential)
                   β > 1: increasing failure rate (wear-out, degradation)
        η (scale): characteristic life (time at which 63.2% have failed)
    
    Survival Function:
        S(t) = exp(-(t/η)^β)
    
    Mean Time To Failure:
        MTTF = η * Γ(1 + 1/β)
    
    References:
        - Ebeling (2010): Reliability Engineering, Chapter 3
        - Lawless (2003): Statistical Models and Methods for Lifetime Data
        - ISO 13381-1:2015: Prognostics terminology
    """
    
    def __init__(
        self,
        shape: float = 2.0,
        scale: float = 168.0,
        min_shape: float = 0.5,
        max_shape: float = 5.0
    ):
        """
        Initialize Weibull hazard model.
        
        Args:
            shape: Weibull shape parameter β (default 2.0 = typical wear-out)
            scale: Weibull scale parameter η in hours (default 168 = 7 days)
            min_shape: Minimum shape parameter for fitting (default 0.5)
            max_shape: Maximum shape parameter for fitting (default 5.0)
        """
        self.shape = np.clip(shape, min_shape, max_shape)
        self.scale = max(scale, 1.0)
        self.min_shape = min_shape
        self.max_shape = max_shape
        self.is_fitted = False
    
    def fit_from_degradation(
        self,
        health_series: np.ndarray,
        failure_threshold: float = 70.0,
        dt_hours: float = 1.0
    ) -> 'WeibullHazardModel':
        """
        Estimate Weibull parameters from health degradation data.
        
        Method: 
        1. Estimate time-to-failure from health trajectory extrapolation
        2. Use method of moments to estimate shape and scale
        3. Fallback to heuristic if insufficient variation
        
        This avoids the problem of arbitrary hazard = rate/margin formula.
        
        Args:
            health_series: Time series of health values
            failure_threshold: Health level defining failure
            dt_hours: Time interval between observations (hours)
        
        Returns:
            Self (for chaining)
        """
        if len(health_series) < 5:
            # Insufficient data - use defaults
            self.is_fitted = False
            return self
        
        try:
            # Use Theil-Sen robust regression for degradation rate
            # This is more robust to outliers than simple point-to-point rates
            from scipy.stats import theilslopes
            
            n = len(health_series)
            times = np.arange(n) * dt_hours
            slope, intercept, _, _ = theilslopes(health_series, times)
            
            # degradation_rate = slope (should be negative if degrading)
            degradation_rate = -slope  # Make positive for degradation
            
            if degradation_rate <= 0.01:
                # Not degrading significantly - very long MTTF
                self.scale = 720.0  # 30 days
                self.shape = 1.0    # Constant failure rate
                self.is_fitted = True
                return self
            
            # Estimate time to failure from current health
            current_health = health_series[-1]
            if current_health <= failure_threshold:
                estimated_ttf = 1.0  # Already failed
            else:
                estimated_ttf = (current_health - failure_threshold) / degradation_rate
            
            # Set scale to estimated TTF (characteristic life)
            self.scale = max(estimated_ttf, 1.0)
            
            # Estimate shape from variability
            # Higher variability → lower shape (more uncertainty)
            health_std = np.std(health_series)
            health_range = np.max(health_series) - np.min(health_series)
            
            if health_range > 0:
                cv = health_std / max(health_range, 1.0)  # Coefficient of variation
                # Map CV to shape: low CV → high shape (predictable wear-out)
                # high CV → low shape (more random)
                self.shape = np.clip(2.5 - cv * 3.0, self.min_shape, self.max_shape)
            else:
                self.shape = 2.0  # Default wear-out shape
            
            self.is_fitted = True
            
        except Exception:
            # Fallback to defaults
            self.is_fitted = False
        
        return self
    
    def hazard_rate(self, t: np.ndarray) -> np.ndarray:
        """
        Compute Weibull hazard rate at time t.
        
        Formula: λ(t) = (β/η) * (t/η)^(β-1)
        
        Args:
            t: Time values (hours from now)
        
        Returns:
            Hazard rates (failures per hour)
        """
        t = np.asarray(t, dtype=float)
        t = np.maximum(t, 1e-6)  # Avoid t=0 issues
        
        hazard = (self.shape / self.scale) * (t / self.scale) ** (self.shape - 1)
        
        # Clamp to reasonable range (max 1 failure/hour)
        return np.clip(hazard, 0.0, 1.0)
    
    def survival_probability(self, t: np.ndarray) -> np.ndarray:
        """
        Compute Weibull survival probability at time t.
        
        Formula: S(t) = exp(-(t/η)^β)
        
        Args:
            t: Time values (hours from now)
        
        Returns:
            Survival probabilities (0-1)
        """
        t = np.asarray(t, dtype=float)
        t = np.maximum(t, 0.0)
        
        survival = np.exp(-((t / self.scale) ** self.shape))
        
        return np.clip(survival, 0.0, 1.0)
    
    def failure_probability(self, t: np.ndarray) -> np.ndarray:
        """
        Compute cumulative failure probability at time t.
        
        Formula: F(t) = 1 - S(t) = 1 - exp(-(t/η)^β)
        
        Args:
            t: Time values (hours from now)
        
        Returns:
            Cumulative failure probabilities (0-1)
        """
        return 1.0 - self.survival_probability(t)
    
    def mttf(self) -> float:
        """
        Compute Mean Time To Failure.
        
        Formula: MTTF = η * Γ(1 + 1/β)
        
        Returns:
            MTTF in hours
        """
        from scipy.special import gamma
        return self.scale * gamma(1.0 + 1.0 / self.shape)
    
    def median_life(self) -> float:
        """
        Compute median life (time at which 50% have failed).
        
        Formula: t_50 = η * (ln(2))^(1/β)
        
        Returns:
            Median life in hours
        """
        return self.scale * (np.log(2.0) ** (1.0 / self.shape))
    
    def get_parameters(self) -> dict:
        """Export Weibull parameters for persistence."""
        return {
            'shape': self.shape,
            'scale': self.scale,
            'is_fitted': self.is_fitted
        }
    
    def set_parameters(self, params: dict) -> None:
        """Restore Weibull parameters from saved state."""
        self.shape = params.get('shape', 2.0)
        self.scale = params.get('scale', 168.0)
        self.is_fitted = params.get('is_fitted', False)


def compute_weibull_hazard_curve(
    health_forecast: np.ndarray,
    failure_threshold: float = 70.0,
    dt_hours: float = 1.0,
    weibull_shape: float = 2.0,
    weibull_scale: float = 168.0
) -> dict:
    """
    Compute hazard/survival curves using proper Weibull model.
    
    This replaces the heuristic hazard = rate/margin formula with
    a statistically grounded Weibull model.
    
    Args:
        health_forecast: Forecasted health values
        failure_threshold: Health threshold for failure
        dt_hours: Time interval between observations
        weibull_shape: Weibull β parameter (default 2.0 = wear-out)
        weibull_scale: Weibull η parameter in hours
    
    Returns:
        Dictionary with 'hazard_rates', 'survival_probs', 'failure_probs', 'mttf_hours'
    """
    model = WeibullHazardModel(shape=weibull_shape, scale=weibull_scale)
    
    # Fit model from health data if we have enough
    if len(health_forecast) >= 5:
        model.fit_from_degradation(
            health_forecast,
            failure_threshold=failure_threshold,
            dt_hours=dt_hours
        )
    
    # Generate time grid
    n = len(health_forecast)
    times = np.arange(1, n + 1) * dt_hours
    
    # Compute curves from Weibull model
    hazard_rates = model.hazard_rate(times)
    survival_probs = model.survival_probability(times)
    failure_probs = model.failure_probability(times)
    mttf_hours = model.mttf()
    
    return {
        'hazard_rates': hazard_rates,
        'survival_probs': survival_probs,
        'failure_probs': failure_probs,
        'mttf_hours': mttf_hours,
        'weibull_shape': model.shape,
        'weibull_scale': model.scale
    }


# =============================================================================
# BOOTSTRAP UNCERTAINTY QUANTIFICATION (v10.1.0)
# =============================================================================
# Provides confidence intervals for regime statistics via resampling
# =============================================================================

def bootstrap_degradation_rate(
    health_series: np.ndarray,
    dt_hours: float = 1.0,
    n_bootstrap: int = 500,
    confidence_level: float = 0.95
) -> dict:
    """
    Compute degradation rate with bootstrap confidence intervals.
    
    Uses Theil-Sen robust regression (median of pairwise slopes) which is:
    1. Robust to outliers (breakdown point ~29%)
    2. Efficient for non-Gaussian errors
    3. Provides R² for fit quality assessment
    
    Then applies bootstrap resampling to get confidence intervals.
    
    This replaces the naive median of point-to-point rates which amplifies noise.
    
    Reference:
        - Theil (1950): A rank-invariant method of linear regression
        - Sen (1968): Estimates of regression coefficients based on Kendall's tau
        - Efron & Tibshirani (1993): Bootstrap methods
    
    Args:
        health_series: Time series of health values
        dt_hours: Time interval between observations
        n_bootstrap: Number of bootstrap samples (default 500)
        confidence_level: Confidence level for intervals (default 0.95)
    
    Returns:
        Dictionary with:
        - 'rate': Point estimate of degradation rate (health points/hour)
        - 'rate_lower': Lower bound of confidence interval
        - 'rate_upper': Upper bound of confidence interval
        - 'r_squared': R² goodness of fit (0-1)
        - 'intercept': Regression intercept
        - 'method': 'theil_sen' or 'ols' (fallback)
    """
    n = len(health_series)
    if n < 5:
        return {
            'rate': 0.0,
            'rate_lower': 0.0,
            'rate_upper': 0.0,
            'r_squared': 0.0,
            'intercept': float(health_series[-1]) if n > 0 else 0.0,
            'method': 'insufficient_data'
        }
    
    times = np.arange(n) * dt_hours
    health = np.asarray(health_series, dtype=float)
    
    try:
        from scipy.stats import theilslopes
        
        # Primary estimate using Theil-Sen
        slope, intercept, _, _ = theilslopes(health, times)
        degradation_rate = -slope  # Make positive for degradation
        
        # Compute R² for fit quality
        y_pred = intercept + slope * times
        ss_res = np.sum((health - y_pred) ** 2)
        ss_tot = np.sum((health - np.mean(health)) ** 2)
        r_squared = 1.0 - (ss_res / max(ss_tot, 1e-10)) if ss_tot > 0 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))
        
        # Bootstrap for confidence intervals
        bootstrap_rates = []
        rng = np.random.default_rng(42)  # Reproducible
        
        for _ in range(n_bootstrap):
            # Resample with replacement
            indices = rng.choice(n, size=n, replace=True)
            t_boot = times[indices]
            h_boot = health[indices]
            
            # Fit Theil-Sen on bootstrap sample
            try:
                slope_boot, _, _, _ = theilslopes(h_boot, t_boot)
                bootstrap_rates.append(-slope_boot)
            except Exception:
                continue
        
        if len(bootstrap_rates) > 10:
            alpha = (1 - confidence_level) / 2.0
            rate_lower = float(np.percentile(bootstrap_rates, 100 * alpha))
            rate_upper = float(np.percentile(bootstrap_rates, 100 * (1 - alpha)))
        else:
            # Not enough bootstrap samples - use point estimate +/- 50%
            rate_lower = degradation_rate * 0.5
            rate_upper = degradation_rate * 1.5
        
        return {
            'rate': float(degradation_rate),
            'rate_lower': float(rate_lower),
            'rate_upper': float(rate_upper),
            'r_squared': float(r_squared),
            'intercept': float(intercept),
            'method': 'theil_sen'
        }
        
    except ImportError:
        # Fallback to simple OLS
        from scipy.stats import linregress
        slope, intercept, r_value, _, std_err = linregress(times, health)
        degradation_rate = -slope
        
        # Use standard error for approximate CI
        from scipy.stats import t as t_dist
        t_crit = t_dist.ppf((1 + confidence_level) / 2.0, n - 2)
        margin = t_crit * std_err
        
        return {
            'rate': float(degradation_rate),
            'rate_lower': float(degradation_rate - margin),
            'rate_upper': float(degradation_rate + margin),
            'r_squared': float(r_value ** 2),
            'intercept': float(intercept),
            'method': 'ols'
        }

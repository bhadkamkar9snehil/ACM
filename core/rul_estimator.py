"""
RUL Estimator with Monte Carlo Simulation (v10.4.0)

Remaining Useful Life estimation via Monte Carlo degradation simulations.
Replaces logic from rul_engine.py (lines 248-394) and forecasting.py RUL sections.

Key Features:
- Monte Carlo simulation with stochastic degradation paths
- Semi-Markov regime transition model for multi-step RUL (v10.1.0)
- P10/P50/P90 quantile-based confidence intervals
- Agresti-Coull confidence interval adjustment
- Time-to-failure distribution via survival analysis
- Integration with degradation models and failure probability functions
- **v10.4.0: RUL reliability gating - returns NOT_RELIABLE when prerequisites fail**

References:
- Saxena et al. (2008) IEEE Trans: Monte Carlo RUL estimation with 500-5000 simulations
- Agresti & Coull (1998): Approximate confidence intervals for binomial proportions
- ISO 13381-1:2015: RUL estimation terminology and methods
- Limnios & Oprisan (2001): Semi-Markov Processes and Reliability (regime transitions)
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from enum import Enum
import numpy as np
from scipy import stats

from core.degradation_model import BaseDegradationModel, DegradationForecast
from core.failure_probability import compute_failure_statistics
from core.observability import Console, Heartbeat, Span


class RULStatus(Enum):
    """
    RUL reliability status (v10.4.0).
    
    Indicates whether RUL prediction meets reliability prerequisites.
    """
    RELIABLE = "RELIABLE"               # All prerequisites met, RUL is trustworthy
    NOT_RELIABLE = "NOT_RELIABLE"      # Prerequisites failed, RUL should not be used
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Not enough data to estimate RUL


@dataclass
class RULEstimate:
    """RUL estimate with uncertainty quantification and reliability status (v10.4.0)"""
    # Quantiles
    p10_lower_bound: float    # 10th percentile (pessimistic)
    p50_median: float         # 50th percentile (most likely)
    p90_upper_bound: float    # 90th percentile (optimistic)
    mean_rul: float           # Mean RUL across simulations
    std_rul: float            # Standard deviation of RUL
    
    # Reliability metadata (v10.4.0)
    status: RULStatus         # Reliability status
    status_reason: str        # Human-readable reason for status
    
    # Uncertainty metrics
    confidence_level: float   # Confidence level used (e.g., 0.80)
    n_simulations: int        # Number of Monte Carlo runs
    failure_probability: float  # Probability of failure within forecast horizon
    simulation_times: np.ndarray  # Full distribution of time-to-failure


class RULEstimator:
    """
    Monte Carlo-based RUL estimator with uncertainty quantification.
    
    Algorithm:
    1. Load degradation model (LinearTrendModel or other BaseDegradationModel)
    2. Run N Monte Carlo simulations:
       - For each simulation:
         a. Add stochastic noise to degradation trajectory
         b. Project forward until health crosses failure threshold
         c. Record time-to-failure
    3. Compute quantiles (P10, P50, P90) from time-to-failure distribution
    4. Apply Agresti-Coull adjustment for small sample confidence intervals
    
    References:
    - Saxena et al. (2008): Monte Carlo RUL with 1000+ simulations
    - Agresti & Coull (1998): Binomial confidence intervals
    
    Usage:
        estimator = RULEstimator(
            degradation_model=fitted_model,
            failure_threshold=70.0,
            n_simulations=1000
        )
        rul_est = estimator.estimate_rul(
            current_health=85.0,
            dt_hours=1.0,
            max_horizon_hours=720
        )
        print(f"RUL P50: {rul_est.p50_median:.1f} hours")
    """
    
    def __init__(
        self,
        degradation_model: BaseDegradationModel,
        failure_threshold: float = 70.0,
        n_simulations: int = 1000,
        confidence_level: float = 0.80,
        noise_factor: float = 1.0
    ):
        """
        Initialize RUL estimator.
        
        Args:
            degradation_model: Fitted degradation model (e.g., LinearTrendModel)
            failure_threshold: Health threshold defining failure (default 70.0)
            n_simulations: Number of Monte Carlo runs (500-5000 per Saxena 2008)
            confidence_level: Confidence level for intervals (default 0.80)
            noise_factor: Multiplier for degradation noise (default 1.0)
        """
        self.degradation_model = degradation_model
        self.failure_threshold = failure_threshold
        self.n_simulations = n_simulations
        self.confidence_level = confidence_level
        self.noise_factor = noise_factor
    
    def check_prerequisites(
        self,
        data_quality: str = "OK",
        regime_label: int = 0,
        regime_confidence: float = 1.0,
        degradation_trend: float = 0.0,
        n_batches_degrading: int = 0,
        drift_level: float = 0.0
    ) -> Tuple[RULStatus, str]:
        """
        Check if prerequisites for reliable RUL estimation are met (v10.4.0).
        
        v11 Rule #7: Add explicit "RUL NOT RELIABLE" outcome and prevent numeric RUL
        from being written when prerequisites fail.
        
        Prerequisites for RELIABLE RUL:
        1. Data quality must be OK or GAPPY (not SPARSE, FLAT, NOISY)
        2. Regime must be stable (not UNKNOWN, confidence > 0.6)
        3. Persistent degradation trend (slope < 0 for >= 3 batches)
        4. Low drift (drift_level < 0.5)
        
        Args:
            data_quality: Health timeline quality flag (OK, SPARSE, GAPPY, FLAT, NOISY)
            regime_label: Current regime label (-1 = UNKNOWN)
            regime_confidence: Confidence in regime assignment (0-1)
            degradation_trend: Health degradation slope (negative = degrading)
            n_batches_degrading: Number of consecutive batches with negative trend
            drift_level: Concept drift level (0-1, higher = more drift)
        
        Returns:
            (status, reason) tuple:
                - RELIABLE: All prerequisites met
                - NOT_RELIABLE: One or more prerequisites failed (includes reason)
                - INSUFFICIENT_DATA: Not enough data to assess
        """
        from core.regimes import REGIME_UNKNOWN
        
        # Check 1: Data quality
        if data_quality in ["SPARSE", "FLAT", "MISSING"]:
            return (
                RULStatus.INSUFFICIENT_DATA,
                f"Insufficient data quality: {data_quality}"
            )
        
        if data_quality in ["NOISY"]:
            return (
                RULStatus.NOT_RELIABLE,
                f"Data quality too poor for reliable RUL: {data_quality}"
            )
        
        # Check 2: Stable regime
        if regime_label == REGIME_UNKNOWN:
            return (
                RULStatus.NOT_RELIABLE,
                "Operating regime unknown - cannot reliably predict degradation"
            )
        
        if regime_confidence < 0.6:
            return (
                RULStatus.NOT_RELIABLE,
                f"Regime confidence too low: {regime_confidence:.2f} < 0.6"
            )
        
        # Check 3: Persistent degradation
        if degradation_trend >= 0:
            return (
                RULStatus.NOT_RELIABLE,
                "No degradation trend detected (health stable or improving)"
            )
        
        if n_batches_degrading < 3:
            return (
                RULStatus.NOT_RELIABLE,
                f"Degradation not persistent ({n_batches_degrading} batches < 3 required)"
            )
        
        # Check 4: Low drift
        if drift_level > 0.5:
            return (
                RULStatus.NOT_RELIABLE,
                f"Concept drift too high: {drift_level:.2f} > 0.5 (model assumptions may be invalid)"
            )
        
        # All checks passed
        return (RULStatus.RELIABLE, "All prerequisites met")
    
    def estimate_rul(
        self,
        current_health: float,
        dt_hours: float = 1.0,
        max_horizon_hours: float = 720.0,
        # v10.4.0: RUL reliability gating parameters
        data_quality: str = "OK",
        regime_label: int = 0,
        regime_confidence: float = 1.0,
        degradation_trend: float = 0.0,
        n_batches_degrading: int = 0,
        drift_level: float = 0.0
    ) -> RULEstimate:
        """
        Estimate RUL via Monte Carlo simulation with reliability gating (v10.4.0).
        
        Process:
        1. **v10.4.0: Check prerequisites for reliable RUL estimation**
        2. Generate baseline degradation forecast from model
        3. Run N Monte Carlo simulations with stochastic noise
        4. For each simulation, find time when health < failure_threshold
        5. Compute quantiles (P10, P50, P90) from time-to-failure distribution
        6. Apply Agresti-Coull adjustment for confidence intervals
        
        Args:
            current_health: Current health index value
            dt_hours: Time step for simulation (hours)
            max_horizon_hours: Maximum simulation horizon (hours)
            data_quality: Health timeline quality flag (v10.4.0)
            regime_label: Current regime label (v10.4.0, -1 = UNKNOWN)
            regime_confidence: Confidence in regime assignment (v10.4.0)
            degradation_trend: Health degradation slope (v10.4.0)
            n_batches_degrading: Number of consecutive degrading batches (v10.4.0)
            drift_level: Concept drift level 0-1 (v10.4.0)
        
        Returns:
            RULEstimate with P10/P50/P90 quantiles, uncertainty metrics, and reliability status
        """
        # v10.4.0: Check prerequisites BEFORE computing RUL
        status, reason = self.check_prerequisites(
            data_quality=data_quality,
            regime_label=regime_label,
            regime_confidence=regime_confidence,
            degradation_trend=degradation_trend,
            n_batches_degrading=n_batches_degrading,
            drift_level=drift_level
        )
        
        if status != RULStatus.RELIABLE:
            # Return NOT_RELIABLE or INSUFFICIENT_DATA without numeric RUL
            Console.warn(
                f"RUL estimation not reliable: {reason}",
                component="RUL",
                status=status.value,
                reason=reason
            )
            return RULEstimate(
                p10_lower_bound=np.nan,
                p50_median=np.nan,
                p90_upper_bound=np.nan,
                mean_rul=np.nan,
                std_rul=np.nan,
                status=status,
                status_reason=reason,
                confidence_level=self.confidence_level,
                n_simulations=0,
                failure_probability=np.nan,
                simulation_times=np.array([])
            )
        
        # Quick check: already below threshold
        if current_health <= self.failure_threshold:
            return RULEstimate(
                p10_lower_bound=0.0,
                p50_median=0.0,
                p90_upper_bound=0.0,
                mean_rul=0.0,
                std_rul=0.0,
                status=RULStatus.RELIABLE,
                status_reason="Equipment already below failure threshold",
                confidence_level=self.confidence_level,
                n_simulations=self.n_simulations,
                failure_probability=1.0,
                simulation_times=np.array([0.0])
            )
        
        # Generate baseline forecast from degradation model
        max_steps = int(max_horizon_hours / dt_hours)
        baseline_forecast = self.degradation_model.predict(
            steps=max_steps,
            dt_hours=dt_hours,
            confidence_level=self.confidence_level
        )
        
        # Extract model uncertainty (std_error)
        model_std = baseline_forecast.std_error * self.noise_factor
        
        # Run Monte Carlo simulations with detailed span tracking (v10.3.0)
        with Span("forecast.rul.simulate", n_simulations=self.n_simulations, max_steps=max_steps):
            simulation_times = self._run_monte_carlo_simulations(
                baseline_forecast=baseline_forecast.point_forecast,
                model_std=model_std,
                dt_hours=dt_hours,
                max_steps=max_steps
            )
        
        # Compute quantiles with sub-span for analytics (v10.3.0)
        with Span("forecast.rul.quantiles"):
            p10 = float(np.percentile(simulation_times, 10))
            p50 = float(np.percentile(simulation_times, 50))
            p90 = float(np.percentile(simulation_times, 90))
            mean_rul = float(np.mean(simulation_times))
            std_rul = float(np.std(simulation_times))
            
            # Compute failure probability within forecast horizon
            failures_within_horizon = np.sum(simulation_times < max_horizon_hours)
            failure_prob = float(failures_within_horizon / len(simulation_times))
            
            # Agresti-Coull adjustment for binomial confidence intervals
            # Reference: Agresti & Coull (1998)
            if self.n_simulations >= 10:
                p10, p50, p90 = self._agresti_coull_adjustment(
                    p10, p50, p90, self.n_simulations, self.confidence_level
                )
        
        Console.info(
            f"RUL estimate: P50={p50:.1f}h, P10={p10:.1f}h, P90={p90:.1f}h, "
            f"mean={mean_rul:.1f}h, std={std_rul:.1f}h, failure_prob={failure_prob:.3f}",
            component="RUL"
        )
        
        return RULEstimate(
            p10_lower_bound=p10,
            p50_median=p50,
            p90_upper_bound=p90,
            mean_rul=mean_rul,
            std_rul=std_rul,
            status=RULStatus.RELIABLE,  # v10.4.0
            status_reason="All prerequisites met",  # v10.4.0
            confidence_level=self.confidence_level,
            n_simulations=self.n_simulations,
            failure_probability=failure_prob,
            simulation_times=simulation_times
        )
    
    def _run_monte_carlo_simulations(
        self,
        baseline_forecast: np.ndarray,
        model_std: float,
        dt_hours: float,
        max_steps: int,
        regime_transition_matrix: Optional[np.ndarray] = None,
        regime_degradation_rates: Optional[Dict[int, float]] = None,
        current_regime: Optional[int] = None
    ) -> np.ndarray:
        """
        Run Monte Carlo simulations with stochastic noise and regime transitions.
        
        VECTORIZED IMPLEMENTATION (v10.2.1):
        - Generates all N simulations in parallel using numpy broadcasting
        - Reduces time from O(N * steps) Python loops to O(1) numpy operations
        - Only falls back to per-simulation loop when regime transitions are needed
        
        For each simulation:
        1. Add Gaussian noise to baseline forecast: health[t] = baseline[t] + N(0, σ²)
        2. If regime transition model provided, simulate regime jumps using semi-Markov
        3. Adjust degradation rate based on current regime
        4. Find first time step where health < failure_threshold
        5. Record time-to-failure
        
        Semi-Markov Model (v10.1.0):
        - At each time step, sample from transition probability matrix
        - Each regime has its own degradation rate
        - This captures the reality that equipment transitions between operating regimes
        
        Reference: Limnios & Oprisan (2001) "Semi-Markov Processes and Reliability"
        
        Args:
            baseline_forecast: Deterministic forecast from degradation model
            model_std: Standard deviation of forecast errors
            dt_hours: Time step (hours)
            max_steps: Maximum simulation steps
            regime_transition_matrix: Optional NxN transition probability matrix
            regime_degradation_rates: Optional dict mapping regime -> degradation rate
            current_regime: Optional starting regime (0-indexed)
        
        Returns:
            Array of time-to-failure values (hours) from N simulations
        """
        n_steps = len(baseline_forecast)
        n_regimes = regime_transition_matrix.shape[0] if regime_transition_matrix is not None else 0
        
        # FAST PATH: No regime transitions - fully vectorized
        if regime_transition_matrix is None or regime_degradation_rates is None or n_regimes == 0:
            # Generate all noise at once: (n_simulations, n_steps)
            noise_matrix = np.random.normal(0, model_std, size=(self.n_simulations, n_steps))
            
            # Broadcast baseline to all simulations and add noise
            health_trajectories = baseline_forecast[np.newaxis, :] + noise_matrix
            
            # Clamp to valid range [0, 100]
            health_trajectories = np.clip(health_trajectories, 0.0, 100.0)
            
            # Vectorized time-to-failure: find first crossing of threshold
            # Create boolean mask where health < threshold
            below_threshold = health_trajectories < self.failure_threshold
            
            # Find first True index per simulation (argmax on boolean gives first True)
            # If no True, argmax returns 0, so we need to check
            has_failure = np.any(below_threshold, axis=1)
            first_failure_idx = np.argmax(below_threshold, axis=1)
            
            # Convert to time (hours)
            # For simulations with failure: (idx + 1) * dt_hours
            # For simulations without failure: max_steps * dt_hours
            simulation_times = np.where(
                has_failure,
                (first_failure_idx + 1) * dt_hours,
                max_steps * dt_hours
            )
            
            return simulation_times.astype(float)
        
        # SLOW PATH: With regime transitions (requires per-simulation loop)
        simulation_times = []
        
        for _ in range(self.n_simulations):
            # Initialize regime for this simulation
            sim_regime = current_regime if current_regime is not None else 0
            
            # Add stochastic noise to baseline forecast
            noise = np.random.normal(0, model_std, len(baseline_forecast))
            health_trajectory = baseline_forecast.copy()
            
            # Simulate with regime transitions if model provided
            if regime_transition_matrix is not None and regime_degradation_rates is not None and n_regimes > 0:
                for t in range(1, len(health_trajectory)):
                    # Apply regime-specific degradation adjustment
                    regime_rate = regime_degradation_rates.get(sim_regime, 0.0)
                    baseline_rate = (baseline_forecast[t] - baseline_forecast[t-1]) / dt_hours if t > 0 else 0.0
                    
                    # Blend baseline with regime-specific rate
                    if abs(regime_rate) > 1e-6:
                        health_trajectory[t] = health_trajectory[t-1] + regime_rate * dt_hours + noise[t]
                    else:
                        health_trajectory[t] = baseline_forecast[t] + noise[t]
                    
                    # Sample regime transition (semi-Markov)
                    if sim_regime < n_regimes:
                        transition_probs = regime_transition_matrix[sim_regime]
                        sim_regime = np.random.choice(n_regimes, p=transition_probs)
            else:
                health_trajectory = baseline_forecast + noise
            
            # Clamp health trajectory to valid range [0, 100]
            health_trajectory = np.clip(health_trajectory, 0.0, 100.0)
            
            # Find time-to-failure (first crossing of threshold)
            time_to_failure = self._find_time_to_failure(
                health_trajectory,
                dt_hours,
                max_steps
            )
            
            simulation_times.append(time_to_failure)
        
        return np.array(simulation_times)
    
    def _find_time_to_failure(
        self,
        health_trajectory: np.ndarray,
        dt_hours: float,
        max_steps: int
    ) -> float:
        """
        Find time when health first crosses failure threshold.
        
        VECTORIZED (v10.2.1): Uses np.argmax on boolean array for O(1) numpy op.
        
        Args:
            health_trajectory: Simulated health trajectory
            dt_hours: Time step (hours)
            max_steps: Maximum steps
        
        Returns:
            Time to failure (hours), or max_horizon if never fails
        """
        # Vectorized threshold crossing detection
        below_threshold = health_trajectory < self.failure_threshold
        if np.any(below_threshold):
            first_idx = np.argmax(below_threshold)
            return float((first_idx + 1) * dt_hours)
        
        # Never crosses threshold within forecast horizon
        return float(max_steps * dt_hours)
    
    def _agresti_coull_adjustment(
        self,
        p10: float,
        p50: float,
        p90: float,
        n_samples: int,
        confidence_level: float
    ) -> Tuple[float, float, float]:
        """
        Apply Agresti-Coull adjustment for small-sample confidence intervals.
        
        Agresti-Coull method adjusts binomial proportions for better coverage
        when sample sizes are small (n < 100).
        
        Formula:
        - n_tilde = n + z^2
        - p_tilde = (x + z^2/2) / n_tilde
        - CI = p_tilde +/- z * sqrt(p_tilde(1-p_tilde) / n_tilde)
        
        Reference:
        - Agresti & Coull (1998): "Approximate is better than 'exact' for interval
          estimation of binomial proportions"
        
        Args:
            p10, p50, p90: Unadjusted quantiles
            n_samples: Number of simulations
            confidence_level: Confidence level (e.g., 0.80)
        
        Returns:
            (adjusted_p10, adjusted_p50, adjusted_p90)
        """
        # Z-score for confidence level
        z = stats.norm.ppf((1 + confidence_level) / 2.0)
        
        # Adjusted sample size
        n_tilde = n_samples + z**2
        
        # Apply adjustment to each quantile
        # (Simplification: treat quantiles as proportions for adjustment)
        adjustment_factor = z * np.sqrt(0.25 / n_tilde)  # Conservative: p=0.5
        
        p10_adj = max(0.0, p10 - adjustment_factor * p10)
        p50_adj = p50  # Median less sensitive to adjustment
        p90_adj = p90 + adjustment_factor * p90
        
        return p10_adj, p50_adj, p90_adj


# =============================================================================
# REGIME TRANSITION MODEL (v10.1.0)
# =============================================================================
# Builds semi-Markov transition matrix from ACM_RegimeTimeline data
# Reference: Limnios & Oprisan (2001) "Semi-Markov Processes and Reliability"
# =============================================================================

def build_regime_transition_matrix(
    regime_sequence: np.ndarray,
    n_regimes: Optional[int] = None
) -> np.ndarray:
    """
    Build regime transition probability matrix from observed sequence.
    
    This creates a first-order Markov transition matrix where P[i,j] is the
    probability of transitioning from regime i to regime j.
    
    For semi-Markov extension, we count actual transitions (not self-loops).
    
    Args:
        regime_sequence: Array of regime labels (chronological order)
        n_regimes: Number of regimes (inferred if None)
    
    Returns:
        NxN transition probability matrix (rows sum to 1)
    """
    if len(regime_sequence) < 2:
        # Return identity matrix (stay in current regime)
        n = n_regimes or 2
        return np.eye(n)
    
    regime_sequence = np.asarray(regime_sequence, dtype=int)
    
    if n_regimes is None:
        n_regimes = int(np.max(regime_sequence)) + 1
    
    # Count transitions
    transition_counts = np.zeros((n_regimes, n_regimes), dtype=float)
    
    for i in range(len(regime_sequence) - 1):
        from_regime = regime_sequence[i]
        to_regime = regime_sequence[i + 1]
        
        if 0 <= from_regime < n_regimes and 0 <= to_regime < n_regimes:
            transition_counts[from_regime, to_regime] += 1
    
    # Convert counts to probabilities (row-normalize)
    row_sums = transition_counts.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums > 0, row_sums, 1.0)  # Avoid division by zero
    
    transition_matrix = transition_counts / row_sums
    
    # Fill rows with no transitions with uniform distribution
    for i in range(n_regimes):
        if transition_matrix[i].sum() < 0.01:
            transition_matrix[i] = np.ones(n_regimes) / n_regimes
    
    return transition_matrix


def compute_regime_residual_variance(
    health_series: np.ndarray,
    regime_labels: np.ndarray,
    dt_hours: float = 1.0
) -> Dict[int, float]:
    """
    Compute residual variance for each regime (scientific noise factor).
    
    This replaces the arbitrary noise_factor = 1 + rate * 10 formula with
    empirical residual variance: sigma^2 = Var(health - fitted_trend).
    
    Args:
        health_series: Health values (same length as regime_labels)
        regime_labels: Regime assignments for each time point
        dt_hours: Time interval between observations
    
    Returns:
        Dict mapping regime_label -> residual_std (standard deviation)
    """
    regime_variances = {}
    unique_regimes = np.unique(regime_labels)
    
    for regime in unique_regimes:
        mask = regime_labels == regime
        health_in_regime = health_series[mask]
        
        if len(health_in_regime) < 5:
            regime_variances[int(regime)] = 1.0  # Default
            continue
        
        # Fit linear trend and compute residuals
        times = np.arange(len(health_in_regime)) * dt_hours
        
        try:
            from scipy.stats import theilslopes
            slope, intercept, _, _ = theilslopes(health_in_regime, times)
            trend = intercept + slope * times
            residuals = health_in_regime - trend
            
            residual_std = float(np.std(residuals))
            if not np.isfinite(residual_std) or residual_std < 0.1:
                residual_std = 1.0
                
            regime_variances[int(regime)] = residual_std
            
        except Exception:
            regime_variances[int(regime)] = 1.0
    
    return regime_variances

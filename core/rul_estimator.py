"""
RUL Estimator with Monte Carlo Simulation (v10.1.0)

Remaining Useful Life estimation via Monte Carlo degradation simulations.
Replaces logic from rul_engine.py (lines 248-394) and forecasting.py RUL sections.

Key Features:
- Monte Carlo simulation with stochastic degradation paths
- Semi-Markov regime transition model for multi-step RUL (v10.1.0)
- P10/P50/P90 quantile-based confidence intervals
- Agresti-Coull confidence interval adjustment
- Time-to-failure distribution via survival analysis
- Integration with degradation models and failure probability functions

References:
- Saxena et al. (2008) IEEE Trans: Monte Carlo RUL estimation with 500-5000 simulations
- Agresti & Coull (1998): Approximate confidence intervals for binomial proportions
- ISO 13381-1:2015: RUL estimation terminology and methods
- Limnios & Oprisan (2001): Semi-Markov Processes and Reliability (regime transitions)
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import numpy as np
from scipy import stats

from core.degradation_model import BaseDegradationModel, DegradationForecast
from core.failure_probability import compute_failure_statistics
from core.observability import Console, Span


@dataclass
class RULEstimate:
    """RUL estimate with uncertainty quantification"""
    p10_lower_bound: float    # 10th percentile (pessimistic)
    p50_median: float         # 50th percentile (most likely)
    p90_upper_bound: float    # 90th percentile (optimistic)
    mean_rul: float           # Mean RUL across simulations
    std_rul: float            # Standard deviation of RUL
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
    
    def estimate_rul(
        self,
        current_health: float,
        dt_hours: float = 1.0,
        max_horizon_hours: float = 720.0,
        regime_transition_matrix: Optional[np.ndarray] = None,
        regime_degradation_rates: Optional[Dict[int, float]] = None,
        current_regime: Optional[int] = None
    ) -> RULEstimate:
        """
        Estimate RUL via Monte Carlo simulation.
        
        Process:
        1. Generate baseline degradation forecast from model
        2. Run N Monte Carlo simulations with stochastic noise
        3. For each simulation, find time when health < failure_threshold
        4. Compute quantiles (P10, P50, P90) from time-to-failure distribution
        5. Apply Agresti-Coull adjustment for confidence intervals
        
        Args:
            current_health: Current health index value
            dt_hours: Time step for simulation (hours)
            max_horizon_hours: Maximum simulation horizon (hours)
        
        Returns:
            RULEstimate with P10/P50/P90 quantiles and uncertainty metrics
        """
        # Guard invalid simulation cadence to avoid zero/negative step counts.
        if not np.isfinite(dt_hours) or dt_hours <= 0:
            dt_hours = 1.0
        if not np.isfinite(max_horizon_hours) or max_horizon_hours <= 0:
            max_horizon_hours = 720.0

        # Quick check: already below threshold
        if current_health <= self.failure_threshold:
            return RULEstimate(
                p10_lower_bound=0.0,
                p50_median=0.0,
                p90_upper_bound=0.0,
                mean_rul=0.0,
                std_rul=0.0,
                confidence_level=self.confidence_level,
                n_simulations=self.n_simulations,
                failure_probability=1.0,
                simulation_times=np.array([0.0])
            )
        
        # Generate baseline forecast from degradation model
        max_steps = max(1, int(max_horizon_hours / dt_hours))
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
                max_steps=max_steps,
                regime_transition_matrix=regime_transition_matrix,
                regime_degradation_rates=regime_degradation_rates,
                current_regime=current_regime,
                current_health=current_health
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
            
            # RUL quantiles must remain physically feasible and ordered.
            # Do not apply binomial-proportion adjustments to time quantiles.
            p10 = float(np.clip(p10, 0.0, max_horizon_hours))
            p50 = float(np.clip(p50, 0.0, max_horizon_hours))
            p90 = float(np.clip(p90, 0.0, max_horizon_hours))
            p50 = max(p10, min(p50, p90))
        
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
        current_regime: Optional[int] = None,
        current_health: Optional[float] = None
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
            # Simulate temporally coherent trajectories by perturbing per-step
            # increments (not independent absolute points). This preserves
            # realistic path continuity and crossing behavior.
            start_health = float(current_health) if current_health is not None else float(baseline_forecast[0])
            baseline_increments = np.empty(n_steps, dtype=float)
            baseline_increments[0] = float(baseline_forecast[0] - start_health)
            if n_steps > 1:
                baseline_increments[1:] = np.diff(baseline_forecast)

            noise_matrix = np.random.normal(0, model_std, size=(self.n_simulations, n_steps))
            health_increments = baseline_increments[np.newaxis, :] + noise_matrix
            health_trajectories = start_health + np.cumsum(health_increments, axis=1)
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
        
        # VECTORIZED PATH: With regime transitions.
        # Instead of a Python loop over n_simulations × n_steps (was O(N*S) ≈ 4M iterations
        # for 1000 sims × 4310 steps at 10-min cadence → ~430s), we simulate all regimes
        # simultaneously: only O(n_steps) Python iterations, numpy does the cross-simulation work.
        n_steps = len(baseline_forecast)
        start_health = float(current_health) if current_health is not None else float(baseline_forecast[0])
        init_regime = int(current_regime) if current_regime is not None else 0

        # Build rate lookup array indexed by regime label
        rates_arr = np.array([
            regime_degradation_rates.get(r, 0.0) for r in range(n_regimes)
        ], dtype=float)

        # Baseline increments per step (fallback when regime rate is near-zero)
        baseline_increments = np.empty(n_steps, dtype=float)
        baseline_increments[0] = 0.0
        baseline_increments[1:] = np.diff(baseline_forecast) / dt_hours  # rate in health/hour

        # Pre-generate all noise: (n_simulations, n_steps)
        noise_matrix = np.random.normal(0, model_std, size=(self.n_simulations, n_steps))

        # Cumulative health increments: (n_simulations, n_steps)
        # health_increments[sim, t] = applied_rate[sim, t] * dt_hours + noise[sim, t]
        health_increments = np.empty((self.n_simulations, n_steps), dtype=float)
        health_increments[:, 0] = (baseline_forecast[0] - start_health) + noise_matrix[:, 0]

        # Simulate regime chains for all simulations simultaneously.
        # At each step t, regimes[:] holds the CURRENT regime for each simulation;
        # we apply its rate, then sample the next regime (transition after rate applied).
        regimes = np.full(self.n_simulations, init_regime, dtype=np.int32)
        tm = np.asarray(regime_transition_matrix, dtype=float)  # (n_regimes, n_regimes)

        for t in range(1, n_steps):
            # Regime rate for each simulation's current regime
            regime_rates_t = rates_arr[regimes]  # (n_simulations,)

            # Fallback to baseline rate where regime rate is near-zero
            applied_rates_t = np.where(
                np.abs(regime_rates_t) > 1e-6,
                regime_rates_t,
                baseline_increments[t]
            )
            health_increments[:, t] = applied_rates_t * dt_hours + noise_matrix[:, t]

            # Vectorized Markov transition: cumulative CDF sampling
            # tm[regimes] → (n_simulations, n_regimes) transition probs
            cum_probs = np.cumsum(tm[regimes], axis=1)  # (n_simulations, n_regimes)
            u = np.random.uniform(size=(self.n_simulations, 1))
            # argmax finds first regime where cumulative prob >= u
            regimes = np.argmax(cum_probs >= u, axis=1).astype(np.int32)
            regimes = np.clip(regimes, 0, n_regimes - 1)

        # Build health trajectories via cumulative sum of increments
        health_trajectories = start_health + np.cumsum(health_increments, axis=1)
        health_trajectories = np.clip(health_trajectories, 0.0, 100.0)

        # Vectorized time-to-failure (same as fast path)
        below_threshold = health_trajectories < self.failure_threshold
        has_failure = np.any(below_threshold, axis=1)
        first_failure_idx = np.argmax(below_threshold, axis=1)
        simulation_times = np.where(
            has_failure,
            (first_failure_idx + 1) * dt_hours,
            max_steps * dt_hours
        )
        return simulation_times.astype(float)
    
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

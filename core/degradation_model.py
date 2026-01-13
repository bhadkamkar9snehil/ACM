"""
Degradation Models for Health Forecasting (v10.0.0)

Implements trend-based degradation models with uncertainty quantification.
Replaces duplicate logic from forecasting.py (lines 2095-2749).

Key Features:
- Abstract base class for pluggable degradation models
- Holt's linear trend with adaptive smoothing
- Uncertainty growth via residual analysis
- Incremental updates for online learning
- Research-backed parameter bounds

References:
- Holt (1957): Exponential smoothing with trend
- Hyndman & Athanasopoulos (2018): "Forecasting: Principles and Practice" - alpha/beta bounds
- Box & Jenkins (1970): Forecast uncertainty quantification
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import optimize

from core.observability import Console


@dataclass
class DegradationForecast:
    """Degradation forecast with uncertainty bounds"""
    timestamps: pd.DatetimeIndex
    point_forecast: np.ndarray      # Point estimates
    lower_bound: np.ndarray          # Lower confidence bound
    upper_bound: np.ndarray          # Upper confidence bound
    std_error: float                 # Residual standard error
    level: float                     # Final level estimate
    trend: float                     # Final trend estimate (per hour)


class BaseDegradationModel(ABC):
    """
    Abstract base class for degradation models.
    
    Design Contract:
    - fit(): Train model on historical health data
    - predict(): Generate multi-step ahead forecasts with uncertainty
    - update_incremental(): Update model with new observations (online learning)
    - get_parameters(): Export model state for persistence
    - set_parameters(): Restore model state from saved parameters
    """
    
    @abstractmethod
    def fit(self, health_series: pd.Series) -> None:
        """
        Train model on historical health data.
        
        Args:
            health_series: Time-indexed health values
        """
        pass
    
    @abstractmethod
    def predict(
        self,
        steps: int,
        dt_hours: float,
        confidence_level: float = 0.95
    ) -> DegradationForecast:
        """
        Generate multi-step ahead forecast with uncertainty bounds.
        
        Args:
            steps: Number of forecast steps
            dt_hours: Time interval per step (hours)
            confidence_level: Confidence level for bounds (default 0.95)
        
        Returns:
            DegradationForecast with timestamps, point forecast, and uncertainty bounds
        """
        pass
    
    @abstractmethod
    def update_incremental(self, new_observation: float) -> None:
        """
        Update model with new observation (online learning).
        
        Args:
            new_observation: Latest health value
        """
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, float]:
        """Export model state for persistence"""
        pass
    
    @abstractmethod
    def set_parameters(self, params: Dict[str, float]) -> None:
        """Restore model state from saved parameters"""
        pass


class LinearTrendModel(BaseDegradationModel):
    """
    Holt's linear trend model with adaptive exponential smoothing.
    
    Mathematical Formulation:
    - Level equation: L[t] = α*y[t] + (1-α)*(L[t-1] + T[t-1])
    - Trend equation: T[t] = β*(L[t] - L[t-1]) + (1-β)*T[t-1]
    - Forecast: ŷ[t+h] = L[t] + h*T[t]
    - Uncertainty: σ[h] = σ_residual * sqrt(1 + h*(α^2 + h*β^2/2))
    
    Features:
    - Adaptive alpha/beta via grid search (minimize MAE)
    - Trend clamping to prevent unrealistic projections
    - Flatline detection and handling
    - Robust to outliers via median imputation
    - Warm-start from previous model state
    
    References:
    - Holt (1957): Original exponential smoothing with trend
    - Hyndman & Athanasopoulos (2018): Alpha ∈ [0.05, 0.95], Beta ∈ [0.01, 0.30]
    """
    
    def __init__(
        self,
        alpha: float = 0.3,
        beta: float = 0.1,
        max_trend_per_hour: float = 5.0,
        flatline_epsilon: float = 1e-3,
        enable_adaptive: bool = True,
        min_samples_for_adaptive: int = 30
    ):
        """
        Initialize Holt's linear trend model.
        
        Args:
            alpha: Level smoothing parameter (0.05-0.95, per Hyndman & Athanasopoulos 2018)
            beta: Trend smoothing parameter (0.01-0.30, per Hyndman & Athanasopoulos 2018)
            max_trend_per_hour: Maximum allowable trend rate (health points/hour)
            flatline_epsilon: Threshold for detecting flat/constant signal
            enable_adaptive: Enable adaptive alpha/beta tuning
            min_samples_for_adaptive: Minimum samples required for adaptive tuning
        """
        self.alpha = np.clip(alpha, 0.05, 0.95)
        self.beta = np.clip(beta, 0.01, 0.30)
        self.max_trend_per_hour = max_trend_per_hour
        self.flatline_epsilon = flatline_epsilon
        self.enable_adaptive = enable_adaptive
        self.min_samples_for_adaptive = min_samples_for_adaptive
        
        # Model state (fitted parameters)
        self.level: float = 0.0
        self.trend: float = 0.0
        self.std_error: float = 1.0
        self.dt_hours: float = 1.0
        self.last_timestamp: Optional[pd.Timestamp] = None
        self.n_fitted: int = 0
        
        # Diagnostic metrics
        self.level_history: List[float] = []
        self.trend_history: List[float] = []
        self.residuals: List[float] = []
    
    def fit(self, health_series: pd.Series) -> None:
        """
        Fit Holt's linear trend model to historical health data.
        
        Process:
        1. Detect and handle outliers (robust median imputation)
        2. **v11.1.4: Detect health jumps (maintenance resets) and use post-jump data only**
        3. Compute time intervals (dt_hours)
        4. Detect flatline/low-variance signals
        5. Initialize level and trend
        6. Adaptive alpha/beta tuning (if enabled and sufficient samples)
        7. Forward pass: update level and trend with exponential smoothing
        8. Compute residual standard error for uncertainty quantification
        
        Args:
            health_series: Time-indexed health values (pd.Series with DatetimeIndex)
        """
        if health_series is None or len(health_series) == 0:
            Console.warn("Empty health series provided", component="DEGRADE")
            return
        
        # v11.1.4: HEALTH-JUMP FIX - Detect maintenance resets before fitting
        # A health jump is a sudden increase in health (>15% in one period)
        # This indicates maintenance was performed, so we should only use post-jump data
        health_series = self._detect_and_handle_health_jumps(health_series)
        
        # Prepare series (robust median imputation)
        health_values = health_series.copy().astype(float)
        health_values = self._detect_and_remove_outliers(health_values)
        median_val = float(np.nanmedian(health_values)) if len(health_values) > 0 else 0.0
        if not np.isfinite(median_val):
            median_val = 0.0
        health_values = health_values.fillna(median_val)
        
        n = len(health_values)
        self.n_fitted = n
        
        # Compute time intervals
        if isinstance(health_series.index, pd.DatetimeIndex):
            time_diffs = health_series.index.to_series().diff().dt.total_seconds() / 3600.0
            self.dt_hours = float(time_diffs.median()) if len(time_diffs) > 0 else 1.0
            if not np.isfinite(self.dt_hours) or self.dt_hours <= 0:
                self.dt_hours = 1.0
            self.last_timestamp = health_series.index[-1]
        else:
            self.dt_hours = 1.0
            self.last_timestamp = None
        
        # Detect flatline/low-variance series
        span = float(np.nanmax(health_values) - np.nanmin(health_values))
        variance = float(np.nanvar(health_values))
        is_flatline = (span < self.flatline_epsilon) or (variance < self.flatline_epsilon ** 2)
        
        # Initialize level and trend
        self.level = float(health_values.iloc[0])
        self.trend = (float(health_values.iloc[1]) - float(health_values.iloc[0])) / self.dt_hours if n > 1 else 0.0
        
        if is_flatline:
            self.trend = 0.0
            Console.info("Flatline detected; zeroing trend", component="DEGRADE")
        
        # Adaptive smoothing (if enabled and sufficient samples)
        if self.enable_adaptive and n >= self.min_samples_for_adaptive:
            try:
                self.alpha, self.beta = self._adaptive_smoothing(health_values)
                Console.info(f"Adaptive smoothing: alpha={self.alpha:.3f}, beta={self.beta:.3f}", component="DEGRADE")
            except Exception as e:
                Console.warn(f"Adaptive smoothing failed: {e}", component="DEGRADE", error_type=type(e).__name__, error=str(e)[:200])
        
        # Forward pass (Holt's equations)
        self.level_history = [self.level]
        self.trend_history = [self.trend]
        self.residuals = []
        
        for i in range(1, n):
            obs = float(health_values.iloc[i])
            prev_level = self.level
            prev_trend = self.trend
            
            # Level update
            self.level = self.alpha * obs + (1 - self.alpha) * (prev_level + prev_trend)
            
            # Trend update with clamping
            self.trend = self.beta * (self.level - prev_level) + (1 - self.beta) * prev_trend
            self.trend = np.clip(self.trend, -self.max_trend_per_hour * self.dt_hours, self.max_trend_per_hour * self.dt_hours)
            
            # Track history and residuals
            self.level_history.append(self.level)
            self.trend_history.append(self.trend)
            
            # One-step-ahead forecast error
            forecast_error = obs - (prev_level + prev_trend)
            self.residuals.append(forecast_error)
        
        # Zero trend if flatline
        if is_flatline:
            self.trend = 0.0
            self.trend_history = [0.0] * len(self.trend_history)
            self.residuals = [0.0]
        
        # Compute residual standard error using ROBUST statistics (MAD * 1.4826)
        # v11.1.2: Use MAD instead of std to be robust to outliers in training data
        if len(self.residuals) > 0:
            residual_median = float(np.median(self.residuals))
            residual_mad = float(np.median(np.abs(np.array(self.residuals) - residual_median)))
            self.std_error = residual_mad * 1.4826  # Scale MAD to be consistent with std
        else:
            self.std_error = 1.0
        if not np.isfinite(self.std_error) or self.std_error < 1e-6:
            self.std_error = 1.0
        
        Console.info(
            f"Fitted: level={self.level:.2f}, trend={self.trend:.4f}/hr, "
            f"std_error={self.std_error:.2f}, n={n}",
            component="DEGRADE"
        )
    
    def predict(
        self,
        steps: int,
        dt_hours: Optional[float] = None,
        confidence_level: float = 0.95
    ) -> DegradationForecast:
        """
        Generate multi-step ahead forecast with properly widening uncertainty bounds.
        
        Forecast Equation (Holt's linear trend):
        - y_hat[t+h] = L[t] + h*T[t]
        
        Uncertainty Growth (per Hyndman & Athanasopoulos 2018, Chapter 8.1):
        The exact variance formula for Holt's method h-step-ahead forecast is:
        
        Var[e_t(h)] = sigma^2 * [1 + sum_{j=1}^{h-1}(alpha + alpha*beta*j)^2]
        
        Where:
        - sigma^2 = residual variance from training
        - alpha = level smoothing parameter  
        - beta = trend smoothing parameter
        - h = forecast horizon
        
        This creates proper "cone-shaped" prediction intervals that widen over time,
        reflecting increasing uncertainty in longer-range forecasts.
        
        Reference: Hyndman, R.J. & Athanasopoulos, G. (2018) Forecasting: 
        Principles and Practice, Chapter 8.1, otexts.com/fpp2/prediction-intervals.html
        
        Args:
            steps: Number of forecast steps
            dt_hours: Time interval per step (uses fitted dt_hours if None)
            confidence_level: Confidence level for bounds (default 0.95 = +/-1.96 sigma)
        
        Returns:
            DegradationForecast with timestamps, point forecast, and widening uncertainty bounds
        """
        if dt_hours is None:
            dt_hours = self.dt_hours
        
        # Generate forecast timestamps
        if self.last_timestamp is not None:
            forecast_timestamps = pd.date_range(
                start=self.last_timestamp + pd.Timedelta(hours=dt_hours),
                periods=steps,
                freq=pd.Timedelta(hours=dt_hours)
            )
        else:
            forecast_timestamps = pd.date_range(
                start=pd.Timestamp.now(),
                periods=steps,
                freq=pd.Timedelta(hours=dt_hours)
            )
        
        # Point forecast: y_hat[t+h] = L[t] + h*T[t]
        horizons = np.arange(1, steps + 1)
        point_forecast = self.level + horizons * self.trend
        
        # PROPER WIDENING PREDICTION INTERVALS (Hyndman & Athanasopoulos 2018)
        # Var[e_t(h)] = sigma^2 * [1 + sum_{j=1}^{h-1}(alpha + alpha*beta*j)^2]
        # This creates cone-shaped intervals that widen with forecast horizon
        #
        # VECTORIZED IMPLEMENTATION (v10.2.1):
        # For h=1..steps, we need cumsum_h = sum_{j=1}^{h-1} (alpha + alpha*beta*j)^2
        # Let c_j = alpha + alpha*beta*j = alpha*(1 + beta*j)
        # Then c_j^2 = alpha^2 * (1 + beta*j)^2
        # cumsum_h = sum_{j=1}^{h-1} alpha^2 * (1 + beta*j)^2
        # Use np.cumsum for O(steps) instead of O(steps^2)
        if steps > 0:
            j_vals = np.arange(1, steps)  # j = 1, 2, ..., steps-1
            coeffs_sq = (self.alpha * (1 + self.beta * j_vals)) ** 2
            cumsum_arr = np.cumsum(coeffs_sq)  # cumsum[k] = sum_{j=1}^{k+1} c_j^2
            # variance_multiplier[h-1] = 1 + sum_{j=1}^{h-1} c_j^2
            # For h=1: 1 + 0 = 1
            # For h=2: 1 + c_1^2 = 1 + cumsum_arr[0]
            # For h=k: 1 + cumsum_arr[k-2] (k >= 2)
            variance_multiplier = np.ones(steps)
            if steps > 1:
                variance_multiplier[1:] = 1.0 + cumsum_arr
        else:
            variance_multiplier = np.array([1.0])
        
        # Standard error at each horizon (widening cone)
        std_forecast = self.std_error * np.sqrt(variance_multiplier)
        
        # Confidence bounds (z-score for confidence level)
        from scipy import stats as sp_stats
        z_score = sp_stats.norm.ppf((1 + confidence_level) / 2.0)
        lower_bound = point_forecast - z_score * std_forecast
        upper_bound = point_forecast + z_score * std_forecast
        
        # CRITICAL: Clamp all forecast values to valid health range [0, 100]
        # Health index cannot exceed 100% or go below 0%
        point_forecast = np.clip(point_forecast, 0.0, 100.0)
        lower_bound = np.clip(lower_bound, 0.0, 100.0)
        upper_bound = np.clip(upper_bound, 0.0, 100.0)
        
        return DegradationForecast(
            timestamps=forecast_timestamps,
            point_forecast=point_forecast,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            std_error=self.std_error,
            level=self.level,
            trend=self.trend
        )
    
    def update_incremental(self, new_observation: float) -> None:
        """
        Update model with new observation (online learning).
        
        Applies one iteration of Holt's equations to incorporate new data
        without full retraining. Useful for continuous model updates.
        
        Args:
            new_observation: Latest health value
        """
        if not np.isfinite(new_observation):
            return
        
        prev_level = self.level
        prev_trend = self.trend
        
        # Level update
        self.level = self.alpha * new_observation + (1 - self.alpha) * (prev_level + prev_trend)
        
        # Trend update with clamping
        self.trend = self.beta * (self.level - prev_level) + (1 - self.beta) * prev_trend
        self.trend = np.clip(self.trend, -self.max_trend_per_hour * self.dt_hours, self.max_trend_per_hour * self.dt_hours)
        
        # Update residual (one-step-ahead error)
        forecast_error = new_observation - (prev_level + prev_trend)
        self.residuals.append(forecast_error)
        
        # Update std_error using ROBUST statistics (MAD * 1.4826)
        # v11.1.2: Use MAD instead of std to be robust to outliers
        if len(self.residuals) > 0:
            recent_residuals = np.array(self.residuals[-100:])  # Use last 100 residuals
            residual_median = float(np.median(recent_residuals))
            residual_mad = float(np.median(np.abs(recent_residuals - residual_median)))
            self.std_error = residual_mad * 1.4826  # Scale MAD to be consistent with std
            if not np.isfinite(self.std_error) or self.std_error < 1e-6:
                self.std_error = 1.0
        
        self.n_fitted += 1
    
    def get_parameters(self) -> Dict[str, float]:
        """Export model state for persistence to ACM_ForecastingState"""
        return {
            "alpha": self.alpha,
            "beta": self.beta,
            "level": self.level,
            "trend": self.trend,
            "std_error": self.std_error,
            "dt_hours": self.dt_hours,
            "n_fitted": float(self.n_fitted)
        }
    
    def set_parameters(self, params: Dict[str, float]) -> None:
        """Restore model state from saved parameters"""
        self.alpha = params.get("alpha", 0.3)
        self.beta = params.get("beta", 0.1)
        self.level = params.get("level", 0.0)
        self.trend = params.get("trend", 0.0)
        self.std_error = params.get("std_error", 1.0)
        self.dt_hours = params.get("dt_hours", 1.0)
        self.n_fitted = int(params.get("n_fitted", 0))
        
        Console.info(
            f"Restored state: level={self.level:.2f}, trend={self.trend:.4f}/hr, "
            f"std_error={self.std_error:.2f}",
            component="DEGRADE"
        )
    
    def _detect_and_remove_outliers(self, series: pd.Series, n_std: float = 3.0) -> pd.Series:
        """
        Detect and remove outliers using ROBUST statistics (median/MAD).
        
        v11.1.1 FIX: Uses Median Absolute Deviation (MAD) instead of std.
        MAD is robust to outliers in the training data, which is critical when
        the historical data may contain faults. This allows ACM to work even when
        training data is contaminated with anomalies.
        
        Modified Z-score = 0.6745 * (x - median) / MAD
        (0.6745 is the consistency constant for normal distribution)
        """
        if len(series) < 10:
            return series  # Too few samples for robust outlier detection
        
        # v11.1.1: Use median and MAD (robust estimators) instead of mean/std
        median = series.median()
        mad = np.median(np.abs(series - median))  # Median Absolute Deviation
        
        if mad < 1e-6:
            # Near-constant signal - fall back to std-based check
            std = series.std()
            if std < 1e-6:
                return series  # Near-constant, no outliers
            z_scores = np.abs((series - series.mean()) / std)
        else:
            # Modified Z-score using MAD (robust to contaminated data)
            # Scale factor 0.6745 makes MAD comparable to std for normal distribution
            z_scores = 0.6745 * np.abs(series - median) / mad
        
        outliers = z_scores > n_std
        
        if outliers.sum() > 0:
            Console.info(f"Detected {outliers.sum()} outliers (robust z > {n_std})", component="DEGRADE")
            series = series.copy()
            series[outliers] = np.nan
        
        return series
    
    def _detect_and_handle_health_jumps(
        self,
        health_series: pd.Series,
        jump_threshold: float = 5.0,  # P2-FIX (v11.2.3): Lowered from 15.0 to 5.0
        min_post_jump_samples: int = 10,
        min_jump_duration_hours: float = 1.0
    ) -> pd.Series:
        """
        Detect maintenance resets (sudden health improvements) and reset forecast baseline.
        
        P2-FIX (v11.2.3): ANALYTICAL AUDIT FLAW #12 - Lower health jump threshold
        Changed default from 15% to 5% to capture incremental maintenance:
        - Bearing lubrication: ~8% health improvement
        - Filter replacement: ~5% health improvement
        - Sensor calibration: ~3% health improvement
        
        Previous 15% threshold only caught major overhauls, missing routine maintenance
        that significantly resets degradation trajectory.
        
        ANALYTICAL PRINCIPLE:
        Degradation models assume monotonic decline. After maintenance:
        - Health jumps from 70% to 95% (major) or 70% to 75% (incremental)
        - If we don't detect this, the model uses stale declining trend
        - RUL predictions become unreliable (false alarms)
        
        A "health jump" is defined as:
        - Health increase > jump_threshold (default 5%) in one time period
        - Sustained for > min_jump_duration_hours (not just measurement noise)
        - This indicates external intervention (maintenance, repair, replacement)
        
        When detected:
        - Use only post-jump data for trend fitting
        - This gives accurate degradation rate for current equipment state
        
        Args:
            health_series: Time-indexed health values
            jump_threshold: Minimum health increase (%) to be considered a jump
            min_post_jump_samples: Minimum samples required after jump for fitting
            min_jump_duration_hours: Minimum duration for jump to be sustained (filters noise)
        
        Returns:
            pd.Series: Truncated to post-jump data, or original if no jumps detected
        """
        if len(health_series) < min_post_jump_samples + 2:
            return health_series  # Too few samples to detect jumps
        
        # Calculate period-over-period health changes
        health_diff = health_series.diff()
        
        # Find positive jumps (health improvements) above threshold
        jump_candidates = health_diff > jump_threshold
        jump_candidate_indices = health_series.index[jump_candidates]
        
        if len(jump_candidate_indices) == 0:
            return health_series  # No jumps detected
        
        # Validate jumps are sustained (not just measurement noise)
        # Check if improvement persists for at least min_jump_duration_hours
        validated_jumps = []
        
        if isinstance(health_series.index, pd.DatetimeIndex):
            for jump_idx in jump_candidate_indices:
                jump_loc = health_series.index.get_loc(jump_idx)
                health_at_jump = health_series.iloc[jump_loc]
                
                # Look ahead to check if improvement is sustained
                future_end = jump_idx + pd.Timedelta(hours=min_jump_duration_hours)
                future_window = health_series[jump_idx:future_end]
                
                if len(future_window) > 1:
                    # Check if health stays elevated (within 2% of jump level)
                    if future_window.mean() > health_at_jump - 2.0:
                        validated_jumps.append(jump_idx)
                        Console.info(
                            f"HEALTH-JUMP: Validated sustained jump at {jump_idx} "
                            f"(+{health_diff[jump_idx]:.1f}%)",
                            component="DEGRADE"
                        )
                else:
                    # Near end of series, accept the jump
                    validated_jumps.append(jump_idx)
        else:
            # Non-datetime index, can't validate duration
            validated_jumps = list(jump_candidate_indices)
        
        if len(validated_jumps) == 0:
            Console.info(
                f"HEALTH-JUMP: {len(jump_candidate_indices)} candidate jumps found but none sustained",
                component="DEGRADE"
            )
            return health_series  # No sustained jumps
        
        # Use the LAST jump (most recent maintenance)
        last_jump_idx = validated_jumps[-1]
        last_jump_loc = health_series.index.get_loc(last_jump_idx)
        
        # Check if we have enough post-jump samples
        post_jump_samples = len(health_series) - last_jump_loc - 1
        
        if post_jump_samples < min_post_jump_samples:
            # Not enough post-jump data, use second-to-last jump or full data
            if len(validated_jumps) > 1:
                # Try second-to-last jump
                second_last_jump_idx = validated_jumps[-2]
                second_last_loc = health_series.index.get_loc(second_last_jump_idx)
                post_second_samples = len(health_series) - second_last_loc - 1
                if post_second_samples >= min_post_jump_samples:
                    Console.info(
                        f"HEALTH-JUMP: Using second-to-last jump at {second_last_jump_idx} "
                        f"({post_second_samples} post-jump samples)",
                        component="DEGRADE"
                    )
                    return health_series.iloc[second_last_loc + 1:]
            
            Console.warn(
                f"HEALTH-JUMP: Jump detected at {last_jump_idx} but only {post_jump_samples} "
                f"post-jump samples (need {min_post_jump_samples}). Using full data.",
                component="DEGRADE"
            )
            return health_series
        
        # Log the detected jump
        pre_jump_health = float(health_series.iloc[last_jump_loc - 1]) if last_jump_loc > 0 else 0.0
        post_jump_health = float(health_series.iloc[last_jump_loc])
        jump_magnitude = post_jump_health - pre_jump_health
        
        Console.info(
            f"HEALTH-JUMP: Maintenance reset detected at {last_jump_idx}. "
            f"Health jumped {pre_jump_health:.1f}% -> {post_jump_health:.1f}% (+{jump_magnitude:.1f}%). "
            f"Using {post_jump_samples} post-jump samples for trend fitting.",
            component="DEGRADE"
        )
        
        # Return only post-jump data
        return health_series.iloc[last_jump_loc + 1:]

    def _adaptive_smoothing(self, health_values: pd.Series) -> Tuple[float, float]:
        """
        Adaptive alpha/beta tuning via expanding-window time-series cross-validation.
        
        OPTIMIZED (v10.2.1):
        - Coarse-to-fine grid search: 4x4 initial grid, then refine around best
        - Max 10 CV folds (not n//20) for speed
        - Vectorized Holt's inner loop using numpy
        
        This implements proper time-series CV (not simple grid search) per
        Hyndman & Athanasopoulos (2018), Section 5.4: "Evaluating forecast accuracy".
        
        Grid bounds per Hyndman & Athanasopoulos (2018):
        - Alpha: [0.05, 0.95] (level smoothing)
        - Beta: [0.01, 0.30] (trend smoothing)
        
        Returns:
            (optimal_alpha, optimal_beta)
        """
        n = len(health_values)
        
        # CV parameters - cap folds for speed
        min_train_size = max(20, n // 4)  # At least 20 or 25% of data
        forecast_horizon = min(12, n // 10)  # Forecast horizon (cap at 12 steps)
        max_cv_folds = 10  # Cap CV folds for speed
        step_size = max(1, (n - min_train_size - forecast_horizon) // max_cv_folds)
        
        if n < min_train_size + forecast_horizon + 5:
            # Insufficient data for CV - fall back to simple grid search
            return self._simple_grid_search(health_values)
        
        # Convert to numpy for speed - ensure ndarray type
        health_arr: np.ndarray = np.asarray(health_values.values, dtype=float)
        
        # PHASE 1: Coarse grid search (4x4 = 16 combinations)
        alpha_grid = np.array([0.1, 0.3, 0.6, 0.9])
        beta_grid = np.array([0.02, 0.08, 0.15, 0.25])
        
        best_alpha = self.alpha
        best_beta = self.beta
        best_cv_error = float("inf")
        
        for alpha_candidate in alpha_grid:
            for beta_candidate in beta_grid:
                cv_error = self._compute_cv_error_vectorized(
                    health_arr, alpha_candidate, beta_candidate,
                    min_train_size, forecast_horizon, step_size, n
                )
                if cv_error < best_cv_error:
                    best_cv_error = cv_error
                    best_alpha = alpha_candidate
                    best_beta = beta_candidate
        
        # PHASE 2: Fine-tune around best (3x3 = 9 combinations)
        alpha_fine = np.clip([best_alpha - 0.1, best_alpha, best_alpha + 0.1], 0.05, 0.95)
        beta_fine = np.clip([best_beta - 0.05, best_beta, best_beta + 0.05], 0.01, 0.30)
        
        for alpha_candidate in alpha_fine:
            for beta_candidate in beta_fine:
                cv_error = self._compute_cv_error_vectorized(
                    health_arr, alpha_candidate, beta_candidate,
                    min_train_size, forecast_horizon, step_size, n
                )
                if cv_error < best_cv_error:
                    best_cv_error = cv_error
                    best_alpha = alpha_candidate
                    best_beta = beta_candidate
        
        return best_alpha, best_beta
    
    def _compute_cv_error_vectorized(
        self, 
        health_arr: np.ndarray, 
        alpha: float, 
        beta: float,
        min_train_size: int,
        forecast_horizon: int,
        step_size: int,
        n: int
    ) -> float:
        """Compute CV error using vectorized Holt's filter"""
        cv_errors = []
        trend_clamp = self.max_trend_per_hour * self.dt_hours
        
        for train_end in range(min_train_size, n - forecast_horizon, step_size):
            train_data = health_arr[:train_end]
            
            # Vectorized Holt's exponential smoothing
            level = train_data[0]
            trend = (train_data[1] - train_data[0]) / self.dt_hours if len(train_data) > 1 else 0.0
            
            # Process all observations (can't fully vectorize due to recursive nature)
            # But we use numpy scalar ops which are faster
            for i in range(1, len(train_data)):
                obs = train_data[i]
                prev_level = level
                prev_trend = trend
                level = alpha * obs + (1.0 - alpha) * (prev_level + prev_trend)
                trend = beta * (level - prev_level) + (1.0 - beta) * prev_trend
                if trend > trend_clamp:
                    trend = trend_clamp
                elif trend < -trend_clamp:
                    trend = -trend_clamp
            
            # Forecast h steps ahead
            forecast = level + forecast_horizon * trend
            actual = health_arr[train_end + forecast_horizon - 1]
            cv_errors.append(abs(forecast - actual))
        
        return float(np.mean(cv_errors)) if cv_errors else float("inf")
    
    def _simple_grid_search(self, health_values: pd.Series) -> Tuple[float, float]:
        """
        Fallback simple grid search when insufficient data for proper CV.
        Minimizes one-step-ahead MAE.
        """
        alpha_grid = np.linspace(0.05, 0.95, 10)
        beta_grid = np.linspace(0.01, 0.30, 10)
        
        best_alpha = self.alpha
        best_beta = self.beta
        best_mae = float("inf")
        
        for alpha_candidate in alpha_grid:
            for beta_candidate in beta_grid:
                mae = self._evaluate_smoothing_params(health_values, alpha_candidate, beta_candidate)
                
                if mae < best_mae:
                    best_mae = mae
                    best_alpha = alpha_candidate
                    best_beta = beta_candidate
        
        return best_alpha, best_beta
    
    def _evaluate_smoothing_params(self, health_values: pd.Series, alpha: float, beta: float) -> float:
        """Evaluate MAE for given alpha/beta parameters"""
        n = len(health_values)
        if n < 2:
            return float("inf")
        
        # Initialize
        level = float(health_values.iloc[0])
        trend = (float(health_values.iloc[1]) - float(health_values.iloc[0])) / self.dt_hours if n > 1 else 0.0
        
        errors = []
        
        # Forward pass
        for i in range(1, n):
            obs = float(health_values.iloc[i])
            prev_level = level
            prev_trend = trend
            
            # One-step-ahead forecast
            forecast = prev_level + prev_trend
            errors.append(abs(obs - forecast))
            
            # Update level and trend
            level = alpha * obs + (1 - alpha) * (prev_level + prev_trend)
            trend = beta * (level - prev_level) + (1 - beta) * prev_trend
            trend = np.clip(trend, -self.max_trend_per_hour * self.dt_hours, self.max_trend_per_hour * self.dt_hours)
        
        mae = float(np.mean(errors)) if len(errors) > 0 else float("inf")
        return mae


class RegimeConditionedDegradationModel(BaseDegradationModel):
    """
    Regime-conditioned degradation model that fits separate trends per operating regime.
    
    P0-FIX (v11.2.3): ANALYTICAL AUDIT FLAW #3 - Regime-conditioned degradation
    
    PROBLEM:
    Equipment degrades at different rates in different operating regimes:
    - High-load regime: Fast degradation (-0.05 health/hour)
    - Low-load regime: Slow degradation (-0.01 health/hour)
    - Startup/shutdown: Thermal cycling stress (-0.20 health/hour)
    
    Fitting a single global trend averages these out, leading to:
    - Overly pessimistic RUL when equipment operates mostly in low-load
    - Overly optimistic RUL when equipment switches to high-load
    - Incorrect uncertainty bounds (residuals include regime-switching variance)
    
    SOLUTION:
    Fit separate LinearTrendModel per regime, then:
    - Forecast by simulating regime sequence
    - Weight degradation rate by time spent in each regime
    - Compute uncertainty from both within-regime and regime-transition variance
    
    Reference:
    - Jardine, Lin & Banjevic (2006): "A review on machinery diagnostics and prognostics"
    - ISO 13381-1:2015: "Condition monitoring and diagnostics of machines - Prognostics"
    
    Requirements:
    - Minimum 10 samples per regime for reliable trend estimation
    - Regime labels must be stable (from CONVERGED model)
    - Regime transition probabilities from historical data
    """
    
    def __init__(
        self,
        regime_labels: np.ndarray,
        min_samples_per_regime: int = 10,
        alpha: float = 0.3,
        beta: float = 0.1,
        max_trend_per_hour: float = 5.0,
        enable_adaptive: bool = True
    ):
        """
        Initialize regime-conditioned degradation model.
        
        Args:
            regime_labels: Array of regime labels aligned with health series
            min_samples_per_regime: Minimum samples required to fit a regime-specific model
            alpha: Default level smoothing parameter (passed to per-regime models)
            beta: Default trend smoothing parameter (passed to per-regime models)
            max_trend_per_hour: Maximum allowable trend rate
            enable_adaptive: Enable adaptive alpha/beta tuning per regime
        """
        self.regime_labels = regime_labels
        self.min_samples_per_regime = min_samples_per_regime
        self.alpha = alpha
        self.beta = beta
        self.max_trend_per_hour = max_trend_per_hour
        self.enable_adaptive = enable_adaptive
        
        # Per-regime models (Dict[regime_label, LinearTrendModel])
        self.regime_models: Dict[int, LinearTrendModel] = {}
        
        # Regime statistics
        self.regime_time_fractions: Dict[int, float] = {}  # % of time in each regime
        self.regime_transition_matrix: Optional[np.ndarray] = None  # P[i,j] = prob(j | i)
        
        # Fallback global model (when regime-specific data insufficient)
        self.global_model = LinearTrendModel(
            alpha=alpha,
            beta=beta,
            max_trend_per_hour=max_trend_per_hour,
            enable_adaptive=enable_adaptive
        )
        
        # Model state
        self.level: float = 0.0
        self.trend: float = 0.0  # Weighted average trend across regimes
        self.std_error: float = 1.0
        self.dt_hours: float = 1.0
        self.last_timestamp: Optional[pd.Timestamp] = None
        self.n_fitted: int = 0
        self.current_regime: int = -1  # Last observed regime
    
    def fit(self, health_series: pd.Series) -> None:
        """
        Fit separate degradation models per regime.
        
        Process:
        1. Group health data by regime
        2. For each regime with >= min_samples_per_regime:
           - Fit LinearTrendModel
        3. Compute regime statistics (time fractions, transition matrix)
        4. Compute weighted average trend for summary
        
        Args:
            health_series: Time-indexed health values aligned with regime_labels
        """
        if health_series is None or len(health_series) == 0:
            Console.warn("Empty health series provided", component="DEGRADE")
            return
        
        if len(health_series) != len(self.regime_labels):
            Console.warn(
                f"Health series length ({len(health_series)}) != regime labels length ({len(self.regime_labels)}). "
                "Falling back to global model.",
                component="DEGRADE"
            )
            self.global_model.fit(health_series)
            self.level = self.global_model.level
            self.trend = self.global_model.trend
            self.std_error = self.global_model.std_error
            self.dt_hours = self.global_model.dt_hours
            self.last_timestamp = self.global_model.last_timestamp
            self.n_fitted = self.global_model.n_fitted
            return
        
        # Group health by regime
        regime_health_groups = {}
        for regime in np.unique(self.regime_labels):
            if regime == -1:  # Skip UNKNOWN regime
                continue
            mask = self.regime_labels == regime
            regime_health = health_series[mask]
            if len(regime_health) >= self.min_samples_per_regime:
                regime_health_groups[regime] = regime_health
        
        if len(regime_health_groups) == 0:
            Console.warn(
                f"No regimes with >= {self.min_samples_per_regime} samples. "
                "Falling back to global model.",
                component="DEGRADE"
            )
            self.global_model.fit(health_series)
            self.level = self.global_model.level
            self.trend = self.global_model.trend
            self.std_error = self.global_model.std_error
            self.dt_hours = self.global_model.dt_hours
            self.last_timestamp = self.global_model.last_timestamp
            self.n_fitted = self.global_model.n_fitted
            return
        
        # Fit per-regime models
        Console.info(
            f"Fitting {len(regime_health_groups)} regime-specific degradation models",
            component="DEGRADE",
            regimes=list(regime_health_groups.keys())
        )
        
        for regime, regime_health in regime_health_groups.items():
            model = LinearTrendModel(
                alpha=self.alpha,
                beta=self.beta,
                max_trend_per_hour=self.max_trend_per_hour,
                enable_adaptive=self.enable_adaptive,
                min_samples_for_adaptive=max(10, self.min_samples_per_regime)
            )
            model.fit(regime_health)
            self.regime_models[regime] = model
            Console.info(
                f"Regime {regime}: trend={model.trend:.4f} health/dt, level={model.level:.2f}, "
                f"n={len(regime_health)}",
                component="DEGRADE"
            )
        
        # Compute regime time fractions
        total_samples = len(health_series)
        for regime, regime_health in regime_health_groups.items():
            self.regime_time_fractions[regime] = len(regime_health) / total_samples
        
        # Compute regime transition matrix (first-order Markov)
        self.regime_transition_matrix = self._compute_transition_matrix(self.regime_labels)
        
        # Weighted average trend for summary
        self.trend = sum(
            model.trend * self.regime_time_fractions[regime]
            for regime, model in self.regime_models.items()
        )
        
        # Use most recent regime's level as current level
        self.current_regime = int(self.regime_labels[-1])
        if self.current_regime in self.regime_models:
            self.level = self.regime_models[self.current_regime].level
            self.dt_hours = self.regime_models[self.current_regime].dt_hours
            self.last_timestamp = self.regime_models[self.current_regime].last_timestamp
        else:
            # Fallback to global model values
            self.level = float(health_series.iloc[-1])
            self.dt_hours = 1.0
            self.last_timestamp = health_series.index[-1] if isinstance(health_series.index, pd.DatetimeIndex) else None
        
        # Compute pooled std_error across regimes
        all_residuals = []
        for model in self.regime_models.values():
            all_residuals.extend(model.residuals)
        self.std_error = float(np.std(all_residuals)) if len(all_residuals) > 0 else 1.0
        
        self.n_fitted = total_samples
        Console.info(
            f"Regime-conditioned model fitted: weighted_trend={self.trend:.4f}, "
            f"pooled_std_error={self.std_error:.3f}",
            component="DEGRADE"
        )
    
    def predict(
        self,
        steps: int,
        dt_hours: Optional[float] = None,
        confidence_level: float = 0.95,
        regime_sequence: Optional[List[int]] = None
    ) -> DegradationForecast:
        """
        Generate multi-step forecast using regime-specific degradation rates.
        
        Two modes:
        1. If regime_sequence provided: Use exact sequence
        2. If not provided: Simulate regime transitions using transition matrix
        
        Args:
            steps: Number of forecast steps
            dt_hours: Time interval per step (uses fitted dt_hours if None)
            confidence_level: Confidence level for bounds (default 0.95)
            regime_sequence: Optional predetermined regime sequence (length = steps)
        
        Returns:
            DegradationForecast with regime-aware predictions
        """
        if dt_hours is None:
            dt_hours = self.dt_hours
        
        # If no regime-specific models, fall back to global model
        if len(self.regime_models) == 0:
            return self.global_model.predict(steps, dt_hours, confidence_level)
        
        # Generate forecast timestamps
        if self.last_timestamp is not None:
            forecast_timestamps = pd.date_range(
                start=self.last_timestamp + pd.Timedelta(hours=dt_hours),
                periods=steps,
                freq=pd.Timedelta(hours=dt_hours)
            )
        else:
            forecast_timestamps = pd.date_range(
                start=pd.Timestamp.now(),
                periods=steps,
                freq=pd.Timedelta(hours=dt_hours)
            )
        
        # Generate regime sequence
        if regime_sequence is None:
            regime_sequence = self._simulate_regime_sequence(steps)
        elif len(regime_sequence) != steps:
            Console.warn(
                f"Regime sequence length ({len(regime_sequence)}) != steps ({steps}). "
                "Simulating instead.",
                component="DEGRADE"
            )
            regime_sequence = self._simulate_regime_sequence(steps)
        
        # Forecast using regime-specific models
        point_forecast = np.zeros(steps)
        current_level = self.level
        
        for step, regime in enumerate(regime_sequence):
            if regime in self.regime_models:
                model = self.regime_models[regime]
                step_forecast = current_level + model.trend
            else:
                # Unknown regime - use weighted average trend
                step_forecast = current_level + self.trend
            
            point_forecast[step] = step_forecast
            current_level = step_forecast
        
        # Uncertainty bounds (conservative: use pooled std_error with widening)
        z_score = 1.96 if confidence_level >= 0.95 else 1.645
        horizons = np.arange(1, steps + 1)
        # Simplified widening: std_error * sqrt(horizon)
        std_at_horizon = self.std_error * np.sqrt(horizons)
        lower_bound = point_forecast - z_score * std_at_horizon
        upper_bound = point_forecast + z_score * std_at_horizon
        
        return DegradationForecast(
            timestamps=forecast_timestamps,
            point_forecast=point_forecast,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            std_error=self.std_error,
            level=self.level,
            trend=self.trend
        )
    
    def update_incremental(self, new_observation: float) -> None:
        """
        Update model with new observation.
        
        Note: This is complex for regime-conditioned models as we need to know
        which regime the new observation belongs to. For now, update global model only.
        """
        self.global_model.update_incremental(new_observation)
        self.level = self.global_model.level
        self.trend = self.global_model.trend
    
    def get_parameters(self) -> Dict[str, float]:
        """Export model state for persistence"""
        params = {
            'level': self.level,
            'trend': self.trend,
            'std_error': self.std_error,
            'dt_hours': self.dt_hours,
            'n_fitted': self.n_fitted,
            'current_regime': self.current_regime,
            'n_regimes': len(self.regime_models),
        }
        
        # Add per-regime parameters
        for regime, model in self.regime_models.items():
            regime_params = model.get_parameters()
            for key, value in regime_params.items():
                params[f'regime_{regime}_{key}'] = value
        
        return params
    
    def set_parameters(self, params: Dict[str, float]) -> None:
        """Restore model state from saved parameters"""
        self.level = params.get('level', 0.0)
        self.trend = params.get('trend', 0.0)
        self.std_error = params.get('std_error', 1.0)
        self.dt_hours = params.get('dt_hours', 1.0)
        self.n_fitted = int(params.get('n_fitted', 0))
        self.current_regime = int(params.get('current_regime', -1))
        
        # Restore per-regime models
        n_regimes = int(params.get('n_regimes', 0))
        for regime in range(n_regimes):
            regime_params = {
                k.replace(f'regime_{regime}_', ''): v
                for k, v in params.items()
                if k.startswith(f'regime_{regime}_')
            }
            if regime_params:
                model = LinearTrendModel()
                model.set_parameters(regime_params)
                self.regime_models[regime] = model
    
    def _compute_transition_matrix(self, regime_labels: np.ndarray) -> np.ndarray:
        """
        Compute first-order Markov regime transition matrix.
        
        Returns:
            matrix[i, j] = P(regime j | currently regime i)
        """
        unique_regimes = sorted([r for r in np.unique(regime_labels) if r >= 0])
        n_regimes = len(unique_regimes)
        
        if n_regimes == 0:
            return np.array([[1.0]])
        
        # Count transitions
        transition_counts = np.zeros((n_regimes, n_regimes))
        regime_to_idx = {regime: idx for idx, regime in enumerate(unique_regimes)}
        
        for i in range(len(regime_labels) - 1):
            current_regime = regime_labels[i]
            next_regime = regime_labels[i + 1]
            
            if current_regime >= 0 and next_regime >= 0:
                current_idx = regime_to_idx[current_regime]
                next_idx = regime_to_idx[next_regime]
                transition_counts[current_idx, next_idx] += 1
        
        # Normalize to probabilities
        row_sums = transition_counts.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1  # Avoid division by zero
        transition_matrix = transition_counts / row_sums
        
        return transition_matrix
    
    def _simulate_regime_sequence(self, steps: int) -> List[int]:
        """
        Simulate regime sequence using Markov transition matrix.
        
        Args:
            steps: Number of steps to simulate
        
        Returns:
            List of regime labels
        """
        if self.regime_transition_matrix is None or len(self.regime_models) == 0:
            # Fallback: stay in current regime
            return [self.current_regime] * steps
        
        unique_regimes = sorted(list(self.regime_models.keys()))
        regime_to_idx = {regime: idx for idx, regime in enumerate(unique_regimes)}
        idx_to_regime = {idx: regime for regime, idx in regime_to_idx.items()}
        
        # Start from current regime
        if self.current_regime in regime_to_idx:
            current_idx = regime_to_idx[self.current_regime]
        else:
            # Fallback: most common regime
            current_idx = 0
        
        sequence = []
        for _ in range(steps):
            # Sample next regime from transition probabilities
            next_idx = np.random.choice(
                len(unique_regimes),
                p=self.regime_transition_matrix[current_idx, :]
            )
            sequence.append(idx_to_regime[next_idx])
            current_idx = next_idx
        
        return sequence

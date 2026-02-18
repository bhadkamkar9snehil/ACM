"""
Degradation Models for Health Forecasting (v11.3.0)

Centralizes degradation trend fitting and forecast uncertainty used by
ForecastEngine. This module provides pluggable model implementations, with
regime-conditioned defaults, and keeps the forecasting pipeline free of
duplicate model logic.

Key Features:
- Abstract base class for pluggable degradation models
- Holt's linear trend with adaptive smoothing
- Regime-conditioned degradation modeling (per-regime Holt + global fallback)
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
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

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
    def get_parameters(self) -> Dict[str, Any]:
        """Export model state for persistence"""
        pass
    
    @abstractmethod
    def set_parameters(self, params: Dict[str, Any]) -> None:
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
        min_samples_for_adaptive: int = 30,
        max_gap_hours: float = 720.0
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
            max_gap_hours: Maximum time gap before data is truncated for fitting
        """
        self.alpha = np.clip(alpha, 0.05, 0.95)
        self.beta = np.clip(beta, 0.01, 0.30)
        self.max_trend_per_hour = max_trend_per_hour
        self.flatline_epsilon = flatline_epsilon
        self.enable_adaptive = enable_adaptive
        self.min_samples_for_adaptive = min_samples_for_adaptive
        self.max_gap_hours = max_gap_hours
        
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
        self._is_warmed: bool = False
    
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
        health_series = self._detect_and_handle_data_gaps(health_series)
        
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
        # v11.3.1 FIX: Track first gap separately for accurate trend initialization
        first_gap_hours: float = 1.0
        if isinstance(health_series.index, pd.DatetimeIndex):
            time_diffs = health_series.index.to_series().diff().dt.total_seconds() / 3600.0
            self.dt_hours = float(time_diffs.median()) if len(time_diffs) > 0 else 1.0
            if not np.isfinite(self.dt_hours) or self.dt_hours <= 0:
                self.dt_hours = 1.0
            self.last_timestamp = health_series.index[-1]
            # v11.3.1: Use ACTUAL first gap for trend initialization (not median)
            # The first two observations may have different spacing than the median
            if n > 1:
                first_gap_seconds = (health_series.index[1] - health_series.index[0]).total_seconds()
                first_gap_hours = first_gap_seconds / 3600.0
                if not np.isfinite(first_gap_hours) or first_gap_hours <= 0:
                    first_gap_hours = self.dt_hours
        else:
            self.dt_hours = 1.0
            self.last_timestamp = None
        
        # Detect flatline/low-variance series
        span = float(np.nanmax(health_values) - np.nanmin(health_values))
        variance = float(np.nanvar(health_values))
        is_flatline = (span < self.flatline_epsilon) or (variance < self.flatline_epsilon ** 2)
        
        # Initialize level and trend
        # v11.3.1 FIX: Use actual first gap, not median dt_hours
        # This prevents Nx errors when first interval differs from median
        self.level = float(health_values.iloc[0])
        self.trend = (float(health_values.iloc[1]) - float(health_values.iloc[0])) / first_gap_hours if n > 1 else 0.0
        
        if is_flatline:
            self.trend = 0.0
            Console.info("Flatline detected; zeroing trend", component="DEGRADE")
        
        # Adaptive smoothing (if enabled, not warm-started, and sufficient samples)
        if self.enable_adaptive and not self._is_warmed and n >= self.min_samples_for_adaptive:
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
    
    def get_parameters(self) -> Dict[str, Any]:
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
    
    def set_parameters(self, params: Dict[str, Any]) -> None:
        """Restore model state from saved parameters"""
        self.alpha = params.get("alpha", 0.3)
        self.beta = params.get("beta", 0.1)
        self.level = params.get("level", 0.0)
        self.trend = params.get("trend", 0.0)
        self.std_error = params.get("std_error", 1.0)
        self.dt_hours = params.get("dt_hours", 1.0)
        self.n_fitted = int(params.get("n_fitted", 0))
        
        self._is_warmed = True
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
            # v11.3.1 FIX: Use consistent MAD-to-sigma scaling
            # For normal distribution: sigma = MAD * 1.4826
            # This makes z-scores comparable to standard z-scores
            # Previously used 0.6745 * |x - median| / MAD which inverts the scaling
            sigma_robust = mad * 1.4826
            z_scores = np.abs(series - median) / sigma_robust
        
        outliers = z_scores > n_std
        
        if outliers.sum() > 0:
            Console.info(f"Detected {outliers.sum()} outliers (robust z > {n_std})", component="DEGRADE")
            series = series.copy()
            series[outliers] = np.nan
        
        return series
    
    def _detect_and_handle_health_jumps(
        self,
        health_series: pd.Series,
        jump_threshold: float = 15.0,
        min_post_jump_samples: int = 10
    ) -> pd.Series:
        """
        v11.1.4: Detect maintenance resets (sudden health improvements) and reset forecast baseline.
        
        ANALYTICAL PRINCIPLE:
        Degradation models assume monotonic decline. After maintenance:
        - Health jumps from 70% to 95% 
        - If we don't detect this, the model uses stale declining trend
        - RUL predictions become unreliable (false alarms)
        
        A "health jump" is defined as:
        - Health increase > jump_threshold (default 15%) in one time period
        - This indicates external intervention (maintenance, repair, replacement)
        
        When detected:
        - Use only post-jump data for trend fitting
        - This gives accurate degradation rate for current equipment state
        
        Args:
            health_series: Time-indexed health values
            jump_threshold: Minimum health increase (%) to be considered a jump
            min_post_jump_samples: Minimum samples required after jump for fitting
        
        Returns:
            pd.Series: Truncated to post-jump data, or original if no jumps detected
        """
        if len(health_series) < min_post_jump_samples + 2:
            return health_series  # Too few samples to detect jumps
        
        # Calculate period-over-period health changes
        health_diff = health_series.diff()
        
        # Find positive jumps (health improvements) above threshold
        jump_mask = health_diff > jump_threshold
        jump_indices = health_series.index[jump_mask]
        
        if len(jump_indices) == 0:
            return health_series  # No jumps detected
        
        # Use the LAST jump (most recent maintenance)
        last_jump_idx = jump_indices[-1]
        last_jump_loc = int(health_series.index.get_indexer(pd.Index([last_jump_idx]))[0])
        if last_jump_loc < 0:
            return health_series
        
        # Check if we have enough post-jump samples
        post_jump_samples = len(health_series) - last_jump_loc - 1
        
        if post_jump_samples < min_post_jump_samples:
            # Not enough post-jump data, use second-to-last jump or full data
            if len(jump_indices) > 1:
                # Try second-to-last jump
                second_last_jump_idx = jump_indices[-2]
                second_last_loc = int(health_series.index.get_indexer(pd.Index([second_last_jump_idx]))[0])
                if second_last_loc < 0:
                    return health_series
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
            f"Using {post_jump_samples + 1} post-jump samples for trend fitting.",
            component="DEGRADE"
        )
        
        # v11.3.1 FIX: Include the post-jump value (the new high health reading)
        # diff() places the jump flag at the DESTINATION index, so iloc[last_jump_loc]
        # is the new high value we want to keep as baseline for trend fitting
        return health_series.iloc[last_jump_loc:]

    def _detect_and_handle_data_gaps(self, health_series: pd.Series) -> pd.Series:
        """
        v11.9.1: Detect large data gaps and use only post-gap data for fitting.
        
        This prevents the model from fitting a trend across a long period of missing data,
        which can lead to an inaccurate trend estimate.
        """
        if len(health_series) < 2 or not isinstance(health_series.index, pd.DatetimeIndex):
            return health_series

        time_diffs = health_series.index.to_series().diff().dt.total_seconds() / 3600.0
        max_gap_hours = time_diffs.max()

        if max_gap_hours > self.max_gap_hours:
            last_gap_loc = time_diffs.idxmax()
            
            Console.info(
                f"DATA-GAP: Large data gap of {max_gap_hours:.1f}h detected before {last_gap_loc}. "
                f"Using {len(health_series.loc[last_gap_loc:])} post-gap samples for trend fitting.",
                component="DEGRADE"
            )
            return health_series.loc[last_gap_loc:]
        
        return health_series
        
    def _adaptive_smoothing(self, health_values: pd.Series) -> Tuple[float, float]:
        """
        Adaptive alpha/beta tuning via expanding-window time-series cross-validation.

        Uses a compact single-phase 3×3 = 9-combination grid to keep per-regime
        runtime bounded. Previous two-phase (4×4 + 3×3 = 25) design caused 241s
        forecasting times when run across 6 regimes on large datasets.

        Grid: alpha ∈ {0.1, 0.4, 0.8} × beta ∈ {0.01, 0.08, 0.20}
        Folds: max 5 (was 10) — sufficient for stable MAE estimates on health series.

        This implements proper time-series CV per Hyndman & Athanasopoulos (2018),
        Section 5.4: "Evaluating forecast accuracy".

        Returns:
            (optimal_alpha, optimal_beta)
        """
        n = len(health_values)

        # CV parameters
        min_train_size = max(20, n // 4)  # At least 20 or 25% of data
        forecast_horizon = min(12, n // 10)  # Forecast horizon (cap at 12 steps)
        max_cv_folds = 5  # 5 folds is sufficient for stable MAE; was 10 (too slow)
        step_size = max(1, (n - min_train_size - forecast_horizon) // max_cv_folds)

        if n < min_train_size + forecast_horizon + 5:
            # Insufficient data for CV - fall back to simple grid search
            return self._simple_grid_search(health_values)

        # Convert to numpy for speed
        health_arr: np.ndarray = np.asarray(health_values.values, dtype=float)

        # Compact 3×3 = 9-combination grid covering the practical range:
        #   low/mid/high level smoothing × low/mid/high trend smoothing
        alpha_grid = np.array([0.1, 0.4, 0.8])
        beta_grid = np.array([0.01, 0.08, 0.20])

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
        """
        Compute CV error using vectorized Holt's filter.
        
        v11.3.1 FIX: Evaluate at multiple horizons with decay weighting.
        RUL depends on trajectory accuracy (when health crosses threshold),
        not just endpoint accuracy. Short-term horizons are weighted more heavily
        since early errors compound into later forecasts.
        """
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
            
            # v11.3.1 FIX: Evaluate at multiple horizons with decay weighting
            # Short-term accuracy matters more for RUL trajectory estimation
            # Weights: h=1 (40%), h=h/4 (30%), h=h/2 (20%), h=h (10%)
            horizons_to_check = [
                1,
                max(1, forecast_horizon // 4),
                max(1, forecast_horizon // 2),
                forecast_horizon
            ]
            weights = [0.4, 0.3, 0.2, 0.1]
            
            weighted_error = 0.0
            total_weight = 0.0
            for h, w in zip(horizons_to_check, weights):
                target_idx = train_end + h - 1
                if target_idx < n:
                    forecast_h = level + h * trend
                    actual_h = health_arr[target_idx]
                    weighted_error += w * abs(forecast_h - actual_h)
                    total_weight += w
            
            if total_weight > 0:
                cv_errors.append(weighted_error / total_weight)
        
        return float(np.mean(cv_errors)) if cv_errors else float("inf")
    
    def _simple_grid_search(self, health_values: pd.Series) -> Tuple[float, float]:
        """
        Fallback simple grid search when insufficient data for proper CV.
        Minimizes one-step-ahead MAE. Uses the same compact 3×3 grid as
        _adaptive_smoothing to keep runtime bounded on short series.
        """
        alpha_grid = np.array([0.1, 0.4, 0.8])
        beta_grid = np.array([0.01, 0.08, 0.20])

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


class RegimeConditionedTrendModel(BaseDegradationModel):
    """
    Regime-conditioned degradation model.

    Fits a LinearTrendModel per regime and keeps a global fallback model.
    The active regime model is selected by `current_regime` at prediction time.
    """

    def __init__(
        self,
        alpha: float = 0.3,
        beta: float = 0.1,
        max_trend_per_hour: float = 5.0,
        enable_adaptive: bool = True,
        min_samples_for_adaptive: int = 30,
        min_samples_per_regime: int = 30,
        include_unknown: bool = False
    ):
        self.alpha = alpha
        self.beta = beta
        self.max_trend_per_hour = max_trend_per_hour
        self.enable_adaptive = enable_adaptive
        self.min_samples_for_adaptive = min_samples_for_adaptive
        self.min_samples_per_regime = min_samples_per_regime
        self.include_unknown = include_unknown

        self.global_model = LinearTrendModel(
            alpha=alpha,
            beta=beta,
            max_trend_per_hour=max_trend_per_hour,
            enable_adaptive=enable_adaptive,
            min_samples_for_adaptive=min_samples_for_adaptive
        )
        self.regime_models: Dict[int, LinearTrendModel] = {}
        self.current_regime: Optional[int] = None

    def set_current_regime(self, regime_label: Optional[int]) -> None:
        self.current_regime = regime_label

    def _get_active_model(self) -> LinearTrendModel:
        if self.current_regime is not None and self.current_regime in self.regime_models:
            return self.regime_models[self.current_regime]
        return self.global_model

    @property
    def level(self) -> float:
        return self._get_active_model().level

    @property
    def trend(self) -> float:
        return self._get_active_model().trend

    @property
    def std_error(self) -> float:
        return self._get_active_model().std_error

    @property
    def dt_hours(self) -> float:
        return self._get_active_model().dt_hours

    def fit(self, health_series: pd.Series, regime_series: Optional[pd.Series] = None) -> None:
        """
        Fit global model and per-regime models.

        Args:
            health_series: Time-indexed health values
            regime_series: Regime label series aligned to health_series
        """
        self.global_model.fit(health_series)

        if regime_series is None:
            Console.warn("No regime series provided; using global degradation model only", component="DEGRADE")
            return

        if len(regime_series) != len(health_series):
            Console.warn(
                "Regime series length mismatch; using global degradation model only",
                component="DEGRADE",
                health_len=len(health_series),
                regime_len=len(regime_series)
            )
            return

        self.regime_models = {}

        regime_series = pd.Series(regime_series.values, index=health_series.index)
        valid_mask = regime_series.notna()
        if not self.include_unknown:
            valid_mask &= (regime_series != -1)

        for regime_label in regime_series[valid_mask].unique():
            regime_mask = (regime_series == regime_label)
            if not self.include_unknown:
                regime_mask &= (regime_series != -1)

            if int(regime_label) == -1 and not self.include_unknown:
                continue

            if regime_mask.sum() < self.min_samples_per_regime:
                continue

            # v11.3.1 FIX: Use longest contiguous segment instead of scattered samples
            # Holt's method assumes sequential data; non-contiguous samples create
            # artificial jumps that inflate trend estimates
            regime_health = self._get_longest_contiguous_segment(health_series, regime_mask)
            
            if len(regime_health) < self.min_samples_per_regime:
                Console.info(
                    f"Regime {regime_label}: longest contiguous segment too short "
                    f"({len(regime_health)} < {self.min_samples_per_regime}), skipping",
                    component="DEGRADE"
                )
                continue
            
            model = LinearTrendModel(
                alpha=self.alpha,
                beta=self.beta,
                max_trend_per_hour=self.max_trend_per_hour,
                enable_adaptive=self.enable_adaptive,
                min_samples_for_adaptive=self.min_samples_for_adaptive
            )
            model.fit(regime_health)
            self.regime_models[int(regime_label)] = model

        Console.info(
            f"Fitted regime-conditioned model with {len(self.regime_models)} regimes",
            component="DEGRADE",
            regimes=len(self.regime_models)
        )

    def predict(
        self,
        steps: int,
        dt_hours: float,
        confidence_level: float = 0.95
    ) -> DegradationForecast:
        return self._get_active_model().predict(
            steps=steps,
            dt_hours=dt_hours,
            confidence_level=confidence_level
        )

    def update_incremental(self, new_observation: float) -> None:
        self.global_model.update_incremental(new_observation)
        active_model = self._get_active_model()
        if active_model is not self.global_model:
            active_model.update_incremental(new_observation)

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "version": "regime_conditioned_v1",
            "global": self.global_model.get_parameters(),
            "regimes": {str(k): v.get_parameters() for k, v in self.regime_models.items()},
            "current_regime": self.current_regime,
            "min_samples_per_regime": self.min_samples_per_regime,
            "include_unknown": self.include_unknown
        }

    def set_parameters(self, params: Dict[str, Any]) -> None:
        # Backward-compatible: if params look like LinearTrendModel, load into global model
        if "global" not in params and "regimes" not in params:
            self.global_model.set_parameters(params)
            self.regime_models = {}
            self.current_regime = None
            return

        global_params = params.get("global", {})
        if isinstance(global_params, dict):
            self.global_model.set_parameters(global_params)

        regime_params = params.get("regimes", {})
        if not isinstance(regime_params, dict):
            regime_params = {}
        self.regime_models = {}
        for key, model_params in regime_params.items():
            try:
                label = int(key)
            except ValueError:
                continue
            model = LinearTrendModel(
                alpha=self.alpha,
                beta=self.beta,
                max_trend_per_hour=self.max_trend_per_hour,
                enable_adaptive=self.enable_adaptive,
                min_samples_for_adaptive=self.min_samples_for_adaptive
            )
            model.set_parameters(model_params)
            self.regime_models[label] = model

        current_regime = params.get("current_regime", None)
        self.current_regime = int(current_regime) if current_regime is not None else None
        self.min_samples_per_regime = int(params.get("min_samples_per_regime", self.min_samples_per_regime))
        self.include_unknown = bool(params.get("include_unknown", self.include_unknown))

    def get_regime_degradation_rates(self) -> Dict[int, float]:
        """Return per-regime degradation rates (trend per hour)."""
        rates = {label: model.trend for label, model in self.regime_models.items()}
        return rates

    def _get_longest_contiguous_segment(
        self, 
        health_series: pd.Series, 
        regime_mask: pd.Series
    ) -> pd.Series:
        """
        v11.3.1 FIX: Extract longest contiguous run where regime_mask is True.
        
        ANALYTICAL PRINCIPLE:
        Holt's exponential smoothing assumes sequential observations:
            L[t] = α*y[t] + (1-α)*(L[t-1] + T[t-1])
            T[t] = β*(L[t] - L[t-1]) + (1-β)*T[t-1]
        
        The term (L[t] - L[t-1]) represents the ONE-STEP level change.
        When filtering by regime, we get scattered, non-contiguous samples.
        
        Example of the problem:
            t=1: health=95%, regime=0  (included)
            t=2: health=94%, regime=1  (excluded)
            t=3: health=85%, regime=0  (included)
        
        Holt sees [95%, 85%] as "adjacent" → computes -10%/step trend
        But actual regime 0 trend might be -1%/step (the 10% drop was during regime 1!)
        
        SOLUTION:
        Use only the longest contiguous segment of the regime.
        This ensures all observations are truly sequential.
        
        Args:
            health_series: Full time-indexed health series
            regime_mask: Boolean mask indicating regime membership
        
        Returns:
            Longest contiguous segment of health_series where regime_mask is True
        """
        if len(health_series) == 0 or regime_mask.sum() == 0:
            return pd.Series(dtype=float)
        
        mask_arr = regime_mask.values.astype(bool)
        n = len(mask_arr)
        
        # Find contiguous segments using run-length encoding
        # A segment starts where mask changes from False to True
        # A segment ends where mask changes from True to False
        best_start = 0
        best_length = 0
        current_start = -1
        current_length = 0
        
        for i in range(n):
            if mask_arr[i]:
                if current_start < 0:
                    current_start = i
                current_length += 1
            else:
                if current_length > best_length:
                    best_length = current_length
                    best_start = current_start
                current_start = -1
                current_length = 0
        
        # Check final segment
        if current_length > best_length:
            best_length = current_length
            best_start = current_start
        
        if best_length == 0:
            return pd.Series(dtype=float)
        
        return health_series.iloc[best_start:best_start + best_length]

"""Fast feature builder (Polars-only API).

This module provides rolling feature building-blocks used by the analytic backbone:
rolling median, MAD, mean/std, OLS slope, skew/kurtosis, and spectral energy.
All core rolling functions require Polars DataFrame input and return Polars DataFrames.
No pandas fallback paths exist in the main pipeline functions.
"""
from __future__ import annotations

import warnings
from typing import Any, List, Optional, Tuple, Literal, Dict
import inspect
from dataclasses import dataclass
import numpy as np
import pandas as pd

# Suppress NumPy divide-by-zero warnings from correlation calculations on constant columns
# These are expected when sensors have zero variance (constant values) and produce NaN correlations
warnings.filterwarnings("ignore", message="invalid value encountered in divide", category=RuntimeWarning)
from core.observability import Span, Console

# Polars is a hard dependency — no fallback
import polars as pl

_ROLLING_SUPPORTS_MIN_SAMPLES = "min_samples" in inspect.signature(pl.Expr.rolling_median).parameters

def _rolling_kwargs(min_periods: int) -> Dict[str, int]:
    return {"min_samples": min_periods} if _ROLLING_SUPPORTS_MIN_SAMPLES else {"min_periods": min_periods}


FillMethod = Literal["median", "ffill", "bfill", "interpolate", "none"]


def _apply_fill(df: pl.DataFrame, method: FillMethod = "median", fill_values: Optional[dict] = None) -> pl.DataFrame:
    """Apply fill strategy to handle missing values. Requires Polars DataFrame input.

    Parameters
    ----------
    df : pl.DataFrame
    method : FillMethod
        Fill strategy: "median", "ffill", "bfill", "interpolate", or "none"
    fill_values : dict, optional
        Pre-computed fill values {column_name: fill_value}. If provided, used instead
        of computing from the data (prevents data leakage when filling score data with
        train-derived statistics).
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("_apply_fill requires a Polars DataFrame")

    if method == "median":
        numeric_cols = [c for c, t in df.schema.items() if t in pl.NUMERIC_DTYPES]
        if fill_values is not None:
            return df.with_columns([
                pl.col(c).fill_null(fill_values.get(c, pl.col(c).median()))
                for c in numeric_cols
            ])
        return df.with_columns([pl.col(c).fill_null(pl.col(c).median()) for c in numeric_cols])

    if method == "ffill":
        return df.with_columns([pl.col(c).fill_null(strategy="forward") for c in df.columns])

    if method == "bfill":
        return df.with_columns([pl.col(c).fill_null(strategy="backward") for c in df.columns])

    if method == "interpolate":
        return df.with_columns([
            pl.when(pl.col(c).is_numeric())
              .then(pl.col(c).interpolate())
              .otherwise(pl.col(c))
              .alias(c)
            for c in df.columns
        ])

    return df  # method == "none"


# ========================================================================
# Data Utilities (moved from acm_main.py)
# ========================================================================

def ensure_local_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure the DataFrame index is a timezone-naive local DatetimeIndex.

    Simplified policy: treat all timestamps as local time and drop any tz info.
    This is the canonical function for normalizing timestamp indices throughout ACM.
    
    Args:
        df: DataFrame with any index type
        
    Returns:
        DataFrame with timezone-naive DatetimeIndex
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors="coerce")
    else:
        # If timezone-aware, strip tz information and keep local wall-clock times
        try:
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
        except Exception:
            # Fallback: coerce to naive datetimes
            df.index = pd.to_datetime(df.index, errors="coerce")
    return df


def deduplicate_index(
    df: pd.DataFrame,
    name: str,
    equip: str = "",
) -> Tuple[pd.DataFrame, int]:
    """
    Remove duplicate timestamps from DataFrame index, keeping the last occurrence.
    
    Args:
        df: DataFrame with potentially duplicate index
        name: Dataset name for logging (e.g., "TRAIN", "SCORE")
        equip: Equipment name for logging context
    
    Returns:
        Tuple of (deduplicated DataFrame, count of duplicates removed)
    
    Raises:
        RuntimeError: If duplicates remain after deduplication (should never happen)
    """
    dup_count = df.index.duplicated(keep='last').sum()
    
    if dup_count > 0:
        Console.warn(
            f"Removing {dup_count} duplicate timestamps from {name} data",
            component="DATA",
            equip=equip,
            duplicates=dup_count,
            dataset=name,
        )
        df = df[~df.index.duplicated(keep='last')].sort_index()
    
    # Assert uniqueness after deduplication
    if not df.index.is_unique:
        raise RuntimeError(
            f"[DATA] {name} data still has duplicate timestamps after deduplication! "
            f"Total: {len(df)}, Unique: {df.index.nunique()}"
        )
    
    return df, dup_count


def rolling_median(df: pl.DataFrame, window: int, cols: Optional[List[str]] = None, min_periods: int = 1) -> pl.DataFrame:
    """Compute rolling median for specified columns. Requires Polars DataFrame input."""
    if not isinstance(df, pl.DataFrame):
        raise TypeError("rolling_median requires a Polars DataFrame input")
    if cols is None:
        cols = list(df.columns)
    return df.select([
        pl.col(c).rolling_median(window, **_rolling_kwargs(min_periods)).alias(f"{c}_med")
        for c in cols
    ])


def rolling_mad(df: pl.DataFrame, window: int, cols: Optional[List[str]] = None, min_periods: int = 1) -> pl.DataFrame:
    """Rolling median absolute deviation (MAD) per column. Requires Polars DataFrame input."""
    if not isinstance(df, pl.DataFrame):
        raise TypeError("rolling_mad requires a Polars DataFrame input")
    if cols is None:
        cols = list(df.columns)
    exprs = []
    for c in cols:
        col_expr = pl.col(c)
        median_expr = col_expr.rolling_median(window, **_rolling_kwargs(min_periods))
        mad_expr = (col_expr - median_expr).abs().rolling_median(window, **_rolling_kwargs(min_periods))
        exprs.append(mad_expr.alias(f"{c}_mad"))
    return df.select(exprs)


def rolling_mean_std(df: pl.DataFrame, window: int, cols: Optional[List[str]] = None, min_periods: int = 1) -> pl.DataFrame:
    """Rolling mean and std per column. Requires Polars DataFrame input."""
    if not isinstance(df, pl.DataFrame):
        raise TypeError("rolling_mean_std requires a Polars DataFrame input")
    if cols is None:
        cols = list(df.columns)
    exprs = []
    for c in cols:
        exprs.append(pl.col(c).rolling_mean(window, **_rolling_kwargs(min_periods)).alias(f"{c}_mean"))
        exprs.append(pl.col(c).rolling_std(window, **_rolling_kwargs(min_periods)).alias(f"{c}_std"))
    return df.select(exprs)


def rolling_skew_kurt(df: pl.DataFrame, window: int, cols: Optional[List[str]] = None, min_periods: int = 1,
                      skew_clip: float = 100.0, kurt_clip: float = 1000.0) -> pl.DataFrame:
    """Compute rolling skewness and kurtosis per column. Requires Polars DataFrame input.

    Note: Kurtosis clipping prevents overflow (e.g., AR1 detector) when near-constant
    sensor windows produce kurtosis ~1e50.
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("rolling_skew_kurt requires a Polars DataFrame input")
    if cols is None:
        cols = list(df.columns)
    exprs = []
    for c in cols:
        exprs.append(pl.col(c).rolling_skew(window, bias=False).clip(-skew_clip, skew_clip).alias(f"{c}_skew"))
        exprs.append(pl.col(c).rolling_kurtosis(window, fisher=True).clip(-kurt_clip, kurt_clip).alias(f"{c}_kurt"))
    return df.select(exprs)


def rolling_ols_slope(df: pl.DataFrame, window: int, cols: Optional[List[str]] = None, min_periods: int = 1) -> pl.DataFrame:
    """Rolling OLS slope via covariance formula. Requires Polars DataFrame input."""
    if not isinstance(df, pl.DataFrame):
        raise TypeError("rolling_ols_slope requires a Polars DataFrame input")
    if cols is None:
        cols = list(df.columns)
    if not cols:
        return pl.DataFrame()
    df_idx = df.with_columns(pl.arange(0, pl.len()).alias("_t").cast(pl.Float64))
    exprs = []
    for c in cols:
        x = pl.col(c).cast(pl.Float64)
        t = pl.col("_t")
        num = ( (t * x).rolling_mean(window, min_periods=min_periods)
              - t.rolling_mean(window, min_periods=min_periods) * x.rolling_mean(window, min_periods=min_periods) )
        den = ( (t.pow(2)).rolling_mean(window, min_periods=min_periods)
              - (t.rolling_mean(window, min_periods=min_periods)).pow(2) )
        exprs.append((num / pl.when(den.abs() > 1e-12).then(den).otherwise(1.0)).alias(f"{c}_slope"))
    return df_idx.select(exprs)

def ols_slope(x):
    """Legacy helper kept for reference. Not used in Polars-first pipeline."""
    if len(x) < 2:
        return 0.0
    try:
        t = np.arange(len(x))
        t_mean = t.mean()
        x_mean = x.mean()
        numerator = np.sum((t - t_mean) * (x - x_mean))
        denominator = np.sum((t - t_mean) ** 2)
        return numerator / denominator if denominator != 0 else 0.0
    except:
        return 0.0



def rolling_spectral_energy(df: pl.DataFrame, window: int, cols: Optional[List[str]] = None,
                          bands: Optional[List[Tuple[float, float]]] = None,
                          fs: float = 1.0, min_periods: int = 1) -> pl.DataFrame:
    """Rolling spectral energy in frequency bands. Requires Polars DataFrame input.

    Uses vectorized sliding-window FFT (stride tricks + batch rfft) — ~50-100x faster
    than per-row callbacks. Returns pl.DataFrame with columns <col>_energy_<band_idx>.

    Parameters
    ----------
    df : pl.DataFrame
    window : int
    cols : List[str], optional — defaults to all columns
    bands : List[Tuple[float, float]], optional — (lo, hi) Hz pairs, defaults to low/mid/high
    fs : float — sampling frequency in Hz (default 1.0)
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("rolling_spectral_energy requires a Polars DataFrame input")
    if len(df) < window // 2:
        return pl.DataFrame()
    if cols is None:
        cols = list(df.columns)
    nyq = 0.5 * fs
    if bands is None:
        bands = [(0.0, 0.1 * nyq), (0.1 * nyq, 0.3 * nyq), (0.3 * nyq, nyq)]

    # PERF-FIX (v11.15.2): batch FFT over all windows at once via stride tricks.
    def _vectorized_spectral_energy(arr1d: np.ndarray) -> np.ndarray:
        """Return shape (n_rows, n_bands) float32 energy array."""
        n = len(arr1d)
        out = np.zeros((n, len(bands)), dtype=np.float32)
        if n < window:
            return out
        shape = (n - window + 1, window)
        strides = (arr1d.strides[0], arr1d.strides[0])
        wins = np.lib.stride_tricks.as_strided(arr1d, shape=shape, strides=strides)
        wins = wins - wins.mean(axis=1, keepdims=True)
        spec = np.abs(np.fft.rfft(wins, axis=1)) ** 2
        freqs = np.fft.rfftfreq(window, d=1.0 / fs)
        start = window - 1
        for b_idx, (lo, hi) in enumerate(bands):
            mask = (freqs >= lo) & (freqs < hi)
            # log1p compression: raw band power scales with signal amplitude
            # SQUARED, giving features a dynamic range of 1e12+ on physical
            # units (kW, kvar). StandardScaler-based consumers (PCA, GMM)
            # saturated on these columns — PCA-SPE's median exceeded its 1e6
            # clip even on TRAIN data, flattening the detector to a constant.
            out[start:, b_idx] = np.log1p(spec[:, mask].sum(axis=1))
        return out

    n_rows = len(df)
    pl_cols: dict = {}
    for c in cols:
        arr = np.asarray(df[c].to_numpy(allow_copy=False), dtype=np.float64)
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        try:
            energy = _vectorized_spectral_energy(arr)
        except Exception:
            energy = np.zeros((n_rows, len(bands)), dtype=np.float32)
        for b_idx in range(len(bands)):
            pl_cols[f"{c}_energy_{b_idx}"] = energy[:, b_idx].astype(np.float64)
    return pl.DataFrame(pl_cols) if pl_cols else pl.DataFrame()


def compute_basic_features_pl(df: 'pl.DataFrame', window: int = 3, cols: Optional[List[str]] = None, 
                               fill_values: Optional[dict] = None) -> 'pl.DataFrame':
    """Polars-native version of `compute_basic_features`.

    Mirrors the pandas pipeline but stays in Polars and returns a `pl.DataFrame`.
    Computes the same features as compute_basic_features() but uses Polars expressions
    for better performance. The robust z-score computation is done using Polars
    expressions to avoid intermediate conversions.

    Parameters
    ----------
    df : pl.DataFrame
        Input Polars DataFrame.
    window : int, default=3
        Window size for rolling computations.
    cols : List[str], optional
        Columns to process. Defaults to all columns.
    fill_values : dict, optional
        Pre-computed fill values {column_name: fill_value}. If provided, these values
        are used for imputation instead of computing from the data. This prevents data
        leakage when processing score data (use training-derived fill values).

    Returns
    -------
    pl.DataFrame
        DataFrame containing computed features.
        Missing values and infinities are replaced with 0.0.

    Examples
    --------
    >>> import polars as pl
    >>> import numpy as np
    >>> # Create sample data with trends and outliers
    >>> n = 1000
    >>> df = pl.DataFrame({
    ...     'normal': np.random.randn(n),
    ...     'spiky': np.random.randn(n) + (np.random.rand(n) > 0.95) * 10,
    ...     'trend': np.cumsum(np.random.randn(n) * 0.1)
    ... })
    >>> # Compute features with 10-point window
    >>> features = compute_basic_features_pl(df, window=10)
    >>> # Show robust z-scores and slopes
    >>> features.select([
    ...     pl.col("*").filter(pl.col("*").str.contains("_rz|_slope"))
    ... ])
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("compute_basic_features_pl requires a Polars DataFrame")

    if cols is None:
        cols = list(df.columns)

    # Only compute features for numeric columns in the active frame.
    numeric_cols = {c for c, t in df.schema.items() if t in pl.NUMERIC_DTYPES}
    cols = [c for c in cols if c in numeric_cols]
    if not cols:
        return pl.DataFrame()

    # Polars rolling ops can panic on empty frames; short-circuit deterministically.
    if df.height == 0:
        return pl.DataFrame(schema=[(f"{c}_med", pl.Float64) for c in cols])

    # Fill missing values (Polars path) - use provided fill_values if available
    pl_filled = _apply_fill(df, method="median", fill_values=fill_values)

    # Rolling building blocks — all return pl.DataFrame (Polars-only)
    med    = rolling_median(pl_filled, window, cols, min_periods=1)
    mad    = rolling_mad(pl_filled, window, cols, min_periods=1)
    ms     = rolling_mean_std(pl_filled, window, cols, min_periods=1)
    slopes = rolling_ols_slope(pl_filled, window, cols, min_periods=1)
    sk     = rolling_skew_kurt(pl_filled, window, cols, min_periods=1)
    se     = rolling_spectral_energy(pl_filled, window, cols, min_periods=1)

    # Combine all parts first, then compute robust z-score. Polars ONLY —
    # every rolling helper returns pl.DataFrame or raises.
    parts = [med, mad, ms, slopes, sk, se]
    parts = [p for p in parts if p is not None and len(p.columns) > 0]
    if not parts:
        return pl.DataFrame()

    # Horizontally concatenate the base features with the original data to make all columns available
    combined_df = pl.concat([pl_filled, *parts], how="horizontal")

    # Now build and apply robust z expressions
    # FIX: Match Pandas behavior - create rz columns even if med/mad missing (use fallback values)
    eps = 1e-9
    rz_exprs = []
    global_rz_cols = []
    for c in cols:
        med_col = f"{c}_med"
        mad_col = f"{c}_mad"
        if med_col in combined_df.columns and mad_col in combined_df.columns:
            # Normal case: both rolling med and mad exist
            denom = (pl.col(mad_col) * 1.4826)
            denom_safe = pl.when(denom > eps).then(denom).otherwise(eps)
            rz = ((pl.col(c) - pl.col(med_col)) / (denom_safe + eps)).clip(-1e2, 1e2).alias(f"{c}_rz")
        else:
            # Rolling stats unavailable: fall back to GLOBAL robust z over the
            # available history (median/MAD broadcast as scalars). The old
            # pl.lit(0.0) fallback silently fed detectors a dead column —
            # signal loss with no error.
            g_med = pl.col(c).median()
            g_mad = (pl.col(c) - pl.col(c).median()).abs().median() * 1.4826
            g_denom = pl.when(g_mad > eps).then(g_mad).otherwise(eps)
            rz = ((pl.col(c) - g_med) / (g_denom + eps)).clip(-1e2, 1e2).alias(f"{c}_rz")
            global_rz_cols.append(c)
        rz_exprs.append(rz)

    if global_rz_cols:
        Console.warn(
            f"{len(global_rz_cols)} robust z-score feature(s) using global (non-rolling) stats: "
            f"{global_rz_cols[:5]}{'...' if len(global_rz_cols) > 5 else ''}",
            component="FEATURES",
        )

    # Select all original feature columns and the new rz columns
    final_cols = [p.columns for p in parts]
    out = combined_df.select([item for sublist in final_cols for item in sublist] + rz_exprs)

    # Sanitize infinities / nulls
    # Polars: replace infinite with null then fill_null(0.0)
    # Use a single with_columns expression for efficiency and compatibility.
    out = out.with_columns([
        pl.when(pl.col(col).is_infinite()).then(pl.lit(None)).otherwise(pl.col(col)).alias(col)
        for col in out.columns
    ]).fill_null(0.0)
    return out


def spectral_energy(series: np.ndarray, fs: float = 1.0, bands: Optional[List[Tuple[float, float]]] = None) -> np.ndarray:
    """Compute spectral energy in specified frequency bands for a 1D numpy array.
    Returns energy per band. Default bands if None: low/mid/high fractions of Nyquist.
    """
    n = len(series)
    if n == 0:
        return np.array([])
    x = np.asarray(series, dtype=float)
    # detrend
    x = x - np.mean(x)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    spec = np.abs(np.fft.rfft(x)) ** 2
    nyq = 0.5 * fs
    if bands is None:
        bands = [(0.0, 0.1 * nyq), (0.1 * nyq, 0.3 * nyq), (0.3 * nyq, nyq)]
    energies = []
    for (a, b) in bands:
        mask = (freqs >= a) & (freqs < b)
        energies.append(float(np.sum(spec[mask])))
    return np.array(energies, dtype=float)


def goertzel_energy(series: np.ndarray, fs: float = 1.0, bands: Optional[List[Tuple[float, float]]] = None) -> np.ndarray:
    """Compute spectral energy per band using the Goertzel algorithm per band.
    Useful for short windows where full FFT per-window is expensive.
    bands is list of (low, high) in Hz; we'll compute energy by summing power at frequencies inside band.
    This implementation evaluates the FFT-equivalent at discrete rfftfreq bins using Goertzel per-bin.
    """
    x = np.asarray(series, dtype=float)
    n = len(x)
    if n == 0:
        return np.array([])
    # detrend
    x = x - np.mean(x)
    # frequency bins for rfft
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    # precompute Goertzel for each bin needed
    spec = np.zeros(len(freqs), dtype=float)
    for k in range(len(freqs)):
        # Goertzel implementation for bin k
        # normalized frequency
        omega = 2.0 * np.pi * k / n
        coeff = 2.0 * np.cos(omega)
        s_prev = 0.0
        s_prev2 = 0.0
        for sample in x:
            s = sample + coeff * s_prev - s_prev2
            s_prev2 = s_prev
            s_prev = s
        real = s_prev - s_prev2 * np.cos(omega)
        imag = s_prev2 * np.sin(omega)
        spec[k] = real * real + imag * imag
    if bands is None:
        nyq = 0.5 * fs
        bands = [(0.0, 0.1 * nyq), (0.1 * nyq, 0.3 * nyq), (0.3 * nyq, nyq)]
    energies = []
    for (a, b) in bands:
        mask = (freqs >= a) & (freqs < b)
        energies.append(float(np.sum(spec[mask])))
    return np.array(energies, dtype=float)


# =============================================================================
# P2.11: CONFIDENCE-GATED NORMALIZATION
# =============================================================================
#
# This module provides regime-conditioned normalization with confidence gating.
# When regime assignment confidence is below threshold, falls back to global
# normalization to avoid unstable regime-specific statistics.
#
# Usage:
#   normalizer = ConfidenceGatedNormalizer(confidence_threshold=0.7)
#   normalizer.fit_global(train_df, sensor_cols)
#   normalizer.fit_regime(regime_label=0, train_subset_df, sensor_cols)
#   z_scores = normalizer.normalize(score_df, regime_labels, confidences)
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class RegimeNormStats:
    """Normalization statistics for a single regime."""
    regime_label: int
    mean: pd.Series
    std: pd.Series
    p05: pd.Series
    p95: pd.Series
    sample_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "regime_label": self.regime_label,
            "mean": self.mean.to_dict(),
            "std": self.std.to_dict(),
            "p05": self.p05.to_dict(),
            "p95": self.p95.to_dict(),
            "sample_count": self.sample_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegimeNormStats":
        """Create from dictionary."""
        return cls(
            regime_label=data["regime_label"],
            mean=pd.Series(data["mean"]),
            std=pd.Series(data["std"]),
            p05=pd.Series(data["p05"]),
            p95=pd.Series(data["p95"]),
            sample_count=data["sample_count"]
        )


@dataclass
class NormalizationResult:
    """Result of confidence-gated normalization."""
    z_scores: pd.DataFrame
    method_used: pd.Series  # 'global' or 'regime_{label}'
    confidence_values: pd.Series
    regime_labels: pd.Series


class ConfidenceGatedNormalizer:
    """
    Confidence-gated normalization with regime conditioning.
    
    When regime assignment confidence is below threshold, falls back to global
    normalization. Otherwise uses regime-specific statistics.
    
    Parameters
    ----------
    confidence_threshold : float
        Minimum confidence required to use regime-specific normalization.
        Default is 0.7 (70% confidence).
    min_regime_samples : int
        Minimum samples required for a regime to have valid statistics.
        Default is 50.
    epsilon : float
        Small constant to prevent division by zero.
        Default is 1e-10.
    
    Example
    -------
    >>> normalizer = ConfidenceGatedNormalizer(confidence_threshold=0.7)
    >>> normalizer.fit_global(train_df, sensor_cols=['temp', 'pressure'])
    >>> normalizer.fit_regime(0, train_regime_0, sensor_cols)
    >>> normalizer.fit_regime(1, train_regime_1, sensor_cols)
    >>> result = normalizer.normalize(score_df, regime_labels, confidences)
    >>> z_scores = result.z_scores  # Confidence-gated z-scores
    """
    
    GLOBAL_LABEL = -1  # Special label for global statistics
    
    def __init__(
        self,
        confidence_threshold: float = 0.7,
        min_regime_samples: int = 50,
        epsilon: float = 1e-10
    ):
        self.confidence_threshold = confidence_threshold
        self.min_regime_samples = min_regime_samples
        self.epsilon = epsilon
        
        # Statistics storage
        self._global_stats: Optional[RegimeNormStats] = None
        self._regime_stats: Dict[int, RegimeNormStats] = {}
        self._sensor_cols: List[str] = []
        self._is_fitted = False
    
    def fit_global(self, df: pd.DataFrame, sensor_cols: List[str]) -> "ConfidenceGatedNormalizer":
        """
        Fit global normalization statistics from training data.
        
        This must be called before fit_regime() and normalize().
        
        Parameters
        ----------
        df : pd.DataFrame
            Training data with sensor columns.
        sensor_cols : list of str
            Column names to compute statistics for.
        
        Returns
        -------
        self
            For method chaining.
        """
        if df.empty:
            raise ValueError("Cannot fit on empty DataFrame")
        
        valid_cols = [c for c in sensor_cols if c in df.columns]
        if not valid_cols:
            raise ValueError(f"No valid sensor columns found. Expected: {sensor_cols}")
        
        self._sensor_cols = valid_cols
        numeric_df = df[valid_cols].apply(pd.to_numeric, errors='coerce')
        
        # ROBUST STATISTICS: Use median/MAD instead of mean/std
        # This makes normalization robust to training data containing faults
        # MAD * 1.4826 approximates std for normal distributions
        median = numeric_df.median()
        mad = (numeric_df - median).abs().median()
        # Convert MAD to std-equivalent scale (for normal distribution)
        robust_std = (mad * 1.4826).replace(0.0, np.nan).fillna(self.epsilon)
        p05 = numeric_df.quantile(0.05)
        p95 = numeric_df.quantile(0.95)
        
        self._global_stats = RegimeNormStats(
            regime_label=self.GLOBAL_LABEL,
            mean=median,  # Use median as robust center
            std=robust_std,  # Use MAD-based std
            p05=p05,
            p95=p95,
            sample_count=len(df)
        )
        self._is_fitted = True
        
        return self
    
    def fit_regime(
        self,
        regime_label: int,
        df: pd.DataFrame,
        sensor_cols: Optional[List[str]] = None
    ) -> "ConfidenceGatedNormalizer":
        """
        Fit normalization statistics for a specific regime.
        
        fit_global() must be called first.
        
        Parameters
        ----------
        regime_label : int
            Regime cluster label (0, 1, 2, ...).
        df : pd.DataFrame
            Training data subset for this regime.
        sensor_cols : list of str, optional
            Column names. If None, uses columns from fit_global().
        
        Returns
        -------
        self
            For method chaining.
        """
        if not self._is_fitted:
            raise RuntimeError("Must call fit_global() before fit_regime()")
        
        if regime_label < 0:
            raise ValueError(f"Regime label must be non-negative, got {regime_label}")
        
        cols = sensor_cols or self._sensor_cols
        valid_cols = [c for c in cols if c in df.columns]
        
        if len(df) < self.min_regime_samples:
            # Insufficient samples - skip this regime, will fall back to global
            return self
        
        numeric_df = df[valid_cols].apply(pd.to_numeric, errors='coerce')
        
        # ROBUST STATISTICS: Use median/MAD instead of mean/std
        # This makes normalization robust to training data containing faults
        median = numeric_df.median()
        mad = (numeric_df - median).abs().median()
        robust_std = (mad * 1.4826).replace(0.0, np.nan).fillna(self.epsilon)
        p05 = numeric_df.quantile(0.05)
        p95 = numeric_df.quantile(0.95)
        
        self._regime_stats[regime_label] = RegimeNormStats(
            regime_label=regime_label,
            mean=median,  # Use median as robust center
            std=robust_std,  # Use MAD-based std
            p05=p05,
            p95=p95,
            sample_count=len(df)
        )
        
        return self
    
    def has_regime_stats(self, regime_label: int) -> bool:
        """Check if regime-specific statistics are available."""
        return regime_label in self._regime_stats
    
    def normalize(
        self,
        df: pd.DataFrame,
        regime_labels: pd.Series,
        confidences: pd.Series
    ) -> NormalizationResult:
        """
        Normalize sensor values with confidence-gated regime conditioning.
        
        For each row:
        - If confidence < threshold OR regime stats unavailable: use global stats
        - Otherwise: use regime-specific stats
        
        Parameters
        ----------
        df : pd.DataFrame
            Data to normalize with sensor columns.
        regime_labels : pd.Series
            Regime assignment for each row (aligned with df index).
        confidences : pd.Series
            Assignment confidence for each row (0.0 to 1.0).
        
        Returns
        -------
        NormalizationResult
            Contains z_scores DataFrame, method_used Series, and input metadata.
        """
        if not self._is_fitted:
            raise RuntimeError("Normalizer not fitted. Call fit_global() first.")
        
        if df.empty:
            return NormalizationResult(
                z_scores=pd.DataFrame(columns=self._sensor_cols),
                method_used=pd.Series(dtype=str),
                confidence_values=pd.Series(dtype=float),
                regime_labels=pd.Series(dtype=int)
            )
        
        # Ensure alignment
        regime_labels = regime_labels.reindex(df.index).fillna(-1).astype(int)
        confidences = confidences.reindex(df.index).fillna(0.0)
        
        valid_cols = [c for c in self._sensor_cols if c in df.columns]
        numeric_df = df[valid_cols].apply(pd.to_numeric, errors='coerce')
        
        # Initialize output
        z_scores = pd.DataFrame(index=df.index, columns=valid_cols, dtype=float)
        method_used = pd.Series(index=df.index, dtype=str)
        
        # Determine which rows use regime vs global normalization
        use_regime_mask = (
            (confidences >= self.confidence_threshold) &
            (regime_labels >= 0) &
            (regime_labels.isin(self._regime_stats.keys()))
        )
        
        # Global normalization for low-confidence or unknown regime rows
        global_mask = ~use_regime_mask
        if global_mask.any():
            global_stats = self._global_stats
            for col in valid_cols:
                mean_val = global_stats.mean.get(col, 0.0)
                std_val = global_stats.std.get(col, self.epsilon)
                z_scores.loc[global_mask, col] = (
                    (numeric_df.loc[global_mask, col] - mean_val) / std_val
                )
            method_used.loc[global_mask] = 'global'
        
        # Regime-specific normalization for high-confidence rows
        for regime_label in regime_labels[use_regime_mask].unique():
            if regime_label not in self._regime_stats:
                continue
            
            regime_mask = use_regime_mask & (regime_labels == regime_label)
            if not regime_mask.any():
                continue
            
            regime_stats = self._regime_stats[regime_label]
            for col in valid_cols:
                mean_val = regime_stats.mean.get(col, 0.0)
                std_val = regime_stats.std.get(col, self.epsilon)
                z_scores.loc[regime_mask, col] = (
                    (numeric_df.loc[regime_mask, col] - mean_val) / std_val
                )
            method_used.loc[regime_mask] = f'regime_{regime_label}'
        
        # Clean up infinities and NaNs
        z_scores = z_scores.replace([np.inf, -np.inf], np.nan)
        
        return NormalizationResult(
            z_scores=z_scores,
            method_used=method_used,
            confidence_values=confidences,
            regime_labels=regime_labels
        )
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get summary of fitted statistics for logging/debugging."""
        summary = {
            "is_fitted": self._is_fitted,
            "confidence_threshold": self.confidence_threshold,
            "min_regime_samples": self.min_regime_samples,
            "sensor_cols": self._sensor_cols,
            "global_samples": self._global_stats.sample_count if self._global_stats else 0,
            "regime_count": len(self._regime_stats),
            "regime_samples": {
                k: v.sample_count for k, v in self._regime_stats.items()
            }
        }
        return summary
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize normalizer for persistence."""
        return {
            "confidence_threshold": self.confidence_threshold,
            "min_regime_samples": self.min_regime_samples,
            "epsilon": self.epsilon,
            "sensor_cols": self._sensor_cols,
            "global_stats": self._global_stats.to_dict() if self._global_stats else None,
            "regime_stats": {k: v.to_dict() for k, v in self._regime_stats.items()},
            "is_fitted": self._is_fitted
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfidenceGatedNormalizer":
        """Deserialize normalizer from persistence."""
        normalizer = cls(
            confidence_threshold=data["confidence_threshold"],
            min_regime_samples=data["min_regime_samples"],
            epsilon=data.get("epsilon", 1e-10)
        )
        normalizer._sensor_cols = data["sensor_cols"]
        normalizer._is_fitted = data["is_fitted"]
        
        if data["global_stats"]:
            normalizer._global_stats = RegimeNormStats.from_dict(data["global_stats"])
        
        normalizer._regime_stats = {
            int(k): RegimeNormStats.from_dict(v)
            for k, v in data["regime_stats"].items()
        }
        
        return normalizer


def normalize_with_confidence_gating(
    df: pd.DataFrame,
    sensor_cols: List[str],
    regime_labels: pd.Series,
    confidences: pd.Series,
    global_mean: pd.Series,
    global_std: pd.Series,
    regime_means: Optional[Dict[int, pd.Series]] = None,
    regime_stds: Optional[Dict[int, pd.Series]] = None,
    confidence_threshold: float = 0.7
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Convenience function for one-shot confidence-gated normalization.
    
    Parameters
    ----------
    df : pd.DataFrame
        Data to normalize.
    sensor_cols : list of str
        Columns to normalize.
    regime_labels : pd.Series
        Regime assignment per row.
    confidences : pd.Series
        Assignment confidence per row.
    global_mean : pd.Series
        Global mean for each sensor.
    global_std : pd.Series
        Global std for each sensor.
    regime_means : dict, optional
        Regime-specific means: {regime_label: pd.Series}.
    regime_stds : dict, optional
        Regime-specific stds: {regime_label: pd.Series}.
    confidence_threshold : float
        Minimum confidence for regime-specific normalization.
    
    Returns
    -------
    z_scores : pd.DataFrame
        Normalized z-scores.
    method_used : pd.Series
        'global' or 'regime_{label}' for each row.
    
    Example
    -------
    >>> z_scores, methods = normalize_with_confidence_gating(
    ...     score_df, sensor_cols, regime_labels, confidences,
    ...     global_mean, global_std,
    ...     regime_means={0: r0_mean, 1: r1_mean},
    ...     regime_stds={0: r0_std, 1: r1_std}
    ... )
    """
    epsilon = 1e-10
    regime_means = regime_means or {}
    regime_stds = regime_stds or {}
    
    if df.empty:
        return pd.DataFrame(columns=sensor_cols), pd.Series(dtype=str)
    
    # Ensure alignment
    regime_labels = regime_labels.reindex(df.index).fillna(-1).astype(int)
    confidences = confidences.reindex(df.index).fillna(0.0)
    
    valid_cols = [c for c in sensor_cols if c in df.columns]
    numeric_df = df[valid_cols].apply(pd.to_numeric, errors='coerce')
    
    # Initialize output
    z_scores = pd.DataFrame(index=df.index, columns=valid_cols, dtype=float)
    method_used = pd.Series(index=df.index, dtype=str)
    
    # Determine which rows use regime vs global normalization
    use_regime_mask = (
        (confidences >= confidence_threshold) &
        (regime_labels >= 0) &
        (regime_labels.isin(regime_means.keys()))
    )
    
    # Global normalization
    global_mask = ~use_regime_mask
    if global_mask.any():
        for col in valid_cols:
            mean_val = global_mean.get(col, 0.0)
            std_val = max(global_std.get(col, epsilon), epsilon)
            z_scores.loc[global_mask, col] = (
                (numeric_df.loc[global_mask, col] - mean_val) / std_val
            )
        method_used.loc[global_mask] = 'global'
    
    # Regime-specific normalization
    for regime_label in regime_labels[use_regime_mask].unique():
        if regime_label not in regime_means:
            continue
        
        regime_mask = use_regime_mask & (regime_labels == regime_label)
        if not regime_mask.any():
            continue
        
        r_mean = regime_means[regime_label]
        r_std = regime_stds.get(regime_label, global_std)
        
        for col in valid_cols:
            mean_val = r_mean.get(col, 0.0)
            std_val = max(r_std.get(col, epsilon), epsilon)
            z_scores.loc[regime_mask, col] = (
                (numeric_df.loc[regime_mask, col] - mean_val) / std_val
            )
        method_used.loc[regime_mask] = f'regime_{regime_label}'
    
    # Clean up
    z_scores = z_scores.replace([np.inf, -np.inf], np.nan)
    
    return z_scores, method_used


# =============================================================================
# Pipeline feature build wrapper (moved from core/acm.py)
# =============================================================================

# Common historian suffixes for pre-derived window statistics. These are only
# HINTS — a channel is treated as derived ONLY when the mathematical
# relationship is verified on the actual data below.
_DERIVED_SUFFIXES = {
    "min": ("_min", "_minimum"),
    "max": ("_max", "_maximum"),
    "std": ("_std", "_stddev", "_sd", "_stdev"),
}
_BASE_SUFFIXES = ("_avg", "_average", "_mean", "")


def detect_channel_roles(df: pd.DataFrame, sample_rows: int = 5000) -> Dict[str, List[str]]:
    """Classify channels as PRIMARY (engineer rolling features) or DERIVED
    (pre-computed window statistics of a sibling channel; include raw only).

    Generic and data-driven — works for any historian, any asset:
      1. Group channels by name stem (suffix conventions are only candidates).
      2. VERIFY the claimed relationship on the data itself:
         min:  x_min <= base  for ~all samples
         max:  x_max >= base  for ~all samples
         std:  x_std >= 0     for ~all samples, and median(x_std) < spread(base)
      3. Anything unverified — no sibling base channel, relation does not
         hold — is PRIMARY. The safe default is to engineer a channel, never
         to silently drop information based on its name.

    Why this exists: computing rolling statistics ON TOP of channels that are
    already window statistics (std-of-std, spectral energy of a min trace)
    multiplies dimensionality with redundant noise — 957 raw channels became
    10,472 columns on one wind farm, degrading the high-capacity detectors
    and quadrupling runtime. Real-world raw-sensor feeds have no derived
    channels and pass through this function untouched.
    """
    cols = list(df.columns)
    sample = df.iloc[:: max(1, len(df) // sample_rows)] if len(df) > sample_rows else df

    def _stem(name: str) -> Tuple[str, str]:
        low = name.lower()
        for role, suffixes in _DERIVED_SUFFIXES.items():
            for suf in suffixes:
                if low.endswith(suf):
                    return name[: len(name) - len(suf)], role
        for suf in _BASE_SUFFIXES:
            if suf and low.endswith(suf):
                return name[: len(name) - len(suf)], "base"
        return name, "base"

    groups: Dict[str, Dict[str, str]] = {}
    for c in cols:
        stem, role = _stem(c)
        groups.setdefault(stem, {})[c] = role

    derived: List[str] = []
    for stem, members in groups.items():
        bases = [c for c, r in members.items() if r == "base"]
        if not bases:
            continue  # no base sibling -> everything in the group is primary
        base = pd.to_numeric(sample[bases[0]], errors="coerce")
        base_spread = float(np.nanstd(base.to_numpy(dtype=np.float64)))
        for c, role in members.items():
            if role == "base":
                continue
            v = pd.to_numeric(sample[c], errors="coerce")
            both = base.notna() & v.notna()
            if both.sum() < 50:
                continue  # not enough overlap to verify -> stay primary
            vb, bb = v[both].to_numpy(np.float64), base[both].to_numpy(np.float64)
            eps = 1e-6 + 1e-3 * max(base_spread, 1.0)
            ok = False
            if role == "min":
                ok = float(np.mean(vb <= bb + eps)) > 0.98
            elif role == "max":
                ok = float(np.mean(vb >= bb - eps)) > 0.98
            elif role == "std":
                ok = float(np.mean(vb >= -eps)) > 0.99 and float(np.nanmedian(vb)) <= max(base_spread * 3.0, eps)
            if ok:
                derived.append(c)

    primary = [c for c in cols if c not in set(derived)]
    return {"primary": primary, "derived": derived}


def build_features_for_pipeline(
    train: pd.DataFrame,
    score: pd.DataFrame,
    cfg: Dict[str, Any],
    equip: str = "",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build engineered features for ACM pipeline train/score frames.

    Keeps fill-value derivation strictly from TRAIN data to avoid leakage.
    """
    feat_win = int((cfg.get("features", {}) or {}).get("window", 16))
    Console.info(f"Building features with window={feat_win}", component="FEAT", equip=equip)

    idx_train = train.index
    idx_score = score.index

    # TRAIN-only fill values prevent leakage to SCORE.
    train_fill_values = train.select_dtypes(include=[np.number]).median().to_dict()
    Console.info(f"Computed {len(train_fill_values)} fill values from training data", component="FEAT")

    train_feat = compute_basic_features_pl(
        pl.from_pandas(train),
        window=feat_win,
    )
    score_feat = compute_basic_features_pl(
        pl.from_pandas(score),
        window=feat_win,
        fill_values=train_fill_values,
    )

    if not isinstance(train_feat, pd.DataFrame):
        train_feat = train_feat.to_pandas() if hasattr(train_feat, "to_pandas") else pd.DataFrame(train_feat)
    if not isinstance(score_feat, pd.DataFrame):
        score_feat = score_feat.to_pandas() if hasattr(score_feat, "to_pandas") else pd.DataFrame(score_feat)

    train_feat.index = idx_train
    score_feat.index = idx_score

    # Cast only stray object columns (rare) to avoid full-frame conversion overhead.
    obj_cols_train = train_feat.select_dtypes(include="object").columns
    if len(obj_cols_train):
        train_feat[obj_cols_train] = train_feat[obj_cols_train].apply(pd.to_numeric, errors="coerce")
    obj_cols_score = score_feat.select_dtypes(include="object").columns
    if len(obj_cols_score):
        score_feat[obj_cols_score] = score_feat[obj_cols_score].apply(pd.to_numeric, errors="coerce")

    Console.info(f"Features built: train={train_feat.shape}, score={score_feat.shape}", component="FEAT")
    return train_feat, score_feat


# =============================================================================
# P4.1: FEATURE IMPUTATION (moved from acm_main.py)
# =============================================================================

def impute_features(
    train: pd.DataFrame,
    score: pd.DataFrame,
    low_var_threshold: float,
    output_manager: Optional[Any] = None,
    run_id: Optional[str] = None,
    equip_id: int = 0,
    equip: str = "",
    protected_columns: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    """
    Impute missing values and drop unusable columns from feature DataFrames.

    Handles:
    - Replace inf with NaN
    - Fill NaN with train column medians
    - Align score columns to train columns
    - Drop all-NaN and low-variance columns (unless protected)
    - Log dropped features via output_manager

    Args:
        train: Training features DataFrame
        score: Scoring features DataFrame
        low_var_threshold: Minimum std deviation to keep a column
        output_manager: OutputManager instance for logging dropped features
        run_id: Run identifier
        equip_id: Equipment ID
        equip: Equipment name for logging
        protected_columns: Feature columns that must NOT be dropped regardless of
            variance.  Pass the ``train_sensors`` list from the cached model
            manifest so that scoring batches always present the same feature
            space to the loaded detectors, even when the baseline-derived train
            split happens to produce near-zero variance for a feature.

    Returns:
        Tuple of (train_imputed, score_imputed, dropped_cols)
    """
    # PERF-FIX (v11.15.2): Avoid full-DataFrame .copy() + .replace() which was
    # costing ~40s per batch on 632-column DataFrames.
    # Strategy:
    #   1. Convert to float64 numpy arrays (one allocation, contiguous memory).
    #   2. Zero inf/nan mask in-place with np.copyto / boolean indexing.
    #   3. Compute medians on numpy arrays (faster than pandas column-wise).
    #   4. Broadcast-fill NaNs via np.where (vectorized, no Python loops).
    #   5. Reconstruct pandas DataFrames only at the end.

    train_idx = train.index
    score_idx = score.index
    train_cols = list(train.columns)

    # Align score columns to train before converting to numpy
    score = score.reindex(columns=train_cols)

    # Convert to contiguous float64 arrays (copy happens here — exactly once each)
    tr = train.values.astype(np.float64, copy=True)
    sc = score.values.astype(np.float64, copy=True)

    # Replace ±inf with NaN (in-place, no DataFrame overhead)
    tr[~np.isfinite(tr)] = np.nan
    sc[~np.isfinite(sc)] = np.nan

    # Compute column medians from train (nanmedian ignores NaN, shape: n_cols)
    col_meds_np = np.nanmedian(tr, axis=0)  # faster than pd.DataFrame.median()

    # Fill NaN in train with column medians (broadcast over rows)
    nan_mask_tr = np.isnan(tr)
    if nan_mask_tr.any():
        np.copyto(tr, np.broadcast_to(col_meds_np, tr.shape), where=nan_mask_tr)

    # Fill NaN in score: first use train medians, then fall back to score medians
    nan_mask_sc = np.isnan(sc)
    if nan_mask_sc.any():
        np.copyto(sc, np.broadcast_to(col_meds_np, sc.shape), where=nan_mask_sc)
        # Any remaining NaN means train median was also NaN → use score column median
        nan_mask_sc2 = np.isnan(sc)
        if nan_mask_sc2.any():
            score_col_meds = np.nanmedian(sc, axis=0)
            score_col_meds = np.where(np.isnan(score_col_meds), 0.0, score_col_meds)
            np.copyto(sc, np.broadcast_to(score_col_meds, sc.shape), where=nan_mask_sc2)

    # Reconstruct pandas DataFrames (index preserved)
    train = pd.DataFrame(tr, index=train_idx, columns=train_cols)
    score = pd.DataFrame(sc, index=score_idx, columns=train_cols)

    # col_meds as Series for downstream compatibility (all_nan_cols check)
    col_meds = pd.Series(col_meds_np, index=train_cols)
    
    # Find columns to drop: all-NaN or low-variance.
    # protected_columns (the saved model's train_sensors) are NEVER dropped — the
    # baseline-derived train split used in scoring batches can temporarily produce
    # near-zero variance for features that were perfectly fine at training time.
    # Dropping them here causes a feature-count mismatch that forces an unnecessary
    # full retrain every scoring batch.
    _protected: set = set(protected_columns) if protected_columns else set()

    all_nan_cols = [
        c for c in train.columns
        if pd.isna(col_meds.get(c)) and c not in _protected
    ]
    # PERF-FIX: train is a clean float64 DataFrame after numpy reconstruction —
    # np.std (ddof=1) is faster than pd.DataFrame.std(numeric_only=True) here.
    feat_stds_np = np.std(tr, axis=0, ddof=1)  # shape (n_cols,)
    feat_stds = pd.Series(feat_stds_np, index=train_cols)
    low_var_cols = [
        c for c in feat_stds[feat_stds < low_var_threshold].index
        if c not in _protected
    ]
    cols_to_drop = list(set(all_nan_cols + low_var_cols))

    # Separately surface how many protected columns were spared (diagnostic only).
    protected_spared = [
        c for c in train.columns
        if c in _protected and (
            pd.isna(col_meds.get(c)) or (c in feat_stds.index and feat_stds[c] < low_var_threshold)
        )
    ]
    if protected_spared:
        Console.info(
            f"Retained {len(protected_spared)} low-var/NaN columns because they are "
            f"in the cached model feature set (protected from drop)",
            component="FEAT", equip=equip, protected_count=len(protected_spared),
        )

    if cols_to_drop:
        Console.warn(
            f"Dropping {len(cols_to_drop)} columns ({len(all_nan_cols)} NaN, {len(low_var_cols)} low-var)",
            component="FEAT", equip=equip, dropped=len(cols_to_drop)
        )
        train = train.drop(columns=cols_to_drop)
        score = score.drop(columns=cols_to_drop)

        # Log to SQL via output_manager
        if output_manager:
            drop_records = []
            for col in cols_to_drop:
                reason = "all_NaN" if col in all_nan_cols else "low_variance"
                std_val = feat_stds.get(col) if col in feat_stds.index else None
                drop_value = float(std_val) if std_val is not None and not pd.isna(std_val) else None
                drop_records.append({
                    "FeatureName": str(col),
                    "DropReason": reason,
                    "DropValue": drop_value,
                    "Threshold": None
                })
            output_manager.write_feature_drop_log(drop_records)
    
    if train.shape[1] == 0:
        raise RuntimeError("[FEAT] No usable feature columns after imputation")
    
    return train, score, cols_to_drop


@dataclass
class FeaturePreparationResult:
    """Result bundle for feature preparation stage."""
    train: pd.DataFrame
    score: pd.DataFrame
    raw_train: pd.DataFrame
    raw_score: pd.DataFrame
    seasonal_patterns: Dict[str, List[Any]]
    refit_requested: bool


def _is_coldstart_meta(meta: Any) -> bool:
    """Return True if current run meta indicates coldstart run."""
    if isinstance(meta, dict):
        return bool(meta.get("is_coldstart_run", False))
    return bool(getattr(meta, "is_coldstart_run", False))


def run_feature_preparation_stage(
    *,
    train: pd.DataFrame,
    score: pd.DataFrame,
    cfg: Dict[str, Any],
    meta: Any,
    output_manager: Any,
    sql_client: Any,
    run_id: str,
    equip_id: int,
    equip: str,
    section_fn: Any,
    detect_and_adjust_fn: Any,
    run_data_guardrails_fn: Any,
    load_manifest_protected_columns_fn: Any,
) -> FeaturePreparationResult:
    """
    Execute feature preparation sequence used by ACM pipeline.

    Stage order:
    1. Seasonality detect/adjust
    2. Data guardrails
    3. Preserve raw train/score copies
    4. Feature build
    5. Manifest-protected feature resolve
    6. Feature imputation and pruning
    7. Refit flag read
    """
    seasonal_patterns: Dict[str, List[Any]] = {}
    with section_fn("seasonality.detect"):
        train, score, seasonal_patterns, _ = detect_and_adjust_fn(
            train=train,
            score=score,
            cfg=cfg,
            logger=Console,
            equip=equip,
        )

    low_var_threshold = 1e-4
    with section_fn("data.guardrails"):
        guardrail_result = run_data_guardrails_fn(
            train=train,
            score=score,
            meta=meta,
            cfg=cfg,
            output_manager=output_manager,
            run_id=run_id,
            equip_id=equip_id,
            equip=equip,
            logger=Console,
        )
        low_var_threshold = guardrail_result.low_var_threshold

    raw_train = train.copy()
    raw_score = score.copy()

    with section_fn("features.build"):
        train, score = build_features_for_pipeline(train=train, score=score, cfg=cfg, equip=equip)

    manifest_protected_columns = load_manifest_protected_columns_fn(
        sql_client=sql_client,
        equip=equip,
        equip_id=equip_id,
        cfg=cfg,
        is_coldstart_run=_is_coldstart_meta(meta),
        logger=Console,
    )

    with section_fn("features.impute"):
        train, score, _ = impute_features(
            train=train,
            score=score,
            low_var_threshold=low_var_threshold,
            output_manager=output_manager,
            run_id=run_id,
            equip_id=equip_id,
            equip=equip,
            protected_columns=manifest_protected_columns,
        )

    with section_fn("models.refit_flag"):
        refit_requested = output_manager.check_refit_request()

    return FeaturePreparationResult(
        train=train,
        score=score,
        raw_train=raw_train,
        raw_score=raw_score,
        seasonal_patterns=seasonal_patterns,
        refit_requested=bool(refit_requested),
    )

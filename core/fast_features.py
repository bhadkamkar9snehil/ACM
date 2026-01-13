"""Fast feature builder (Polars-first API with pandas fallback).

This module provides a small set of building-block functions used by the analytic
backbone: rolling median, rolling MAD, rolling mean/std, and a simple spectral-energy
calculator. It prefers polars when available for performance; falls back to pandas.

Note: This is a PO C-level feature builder meant to integrate quickly with the
existing pipeline. We'll extend it iteratively.
"""
from __future__ import annotations

import warnings
from typing import Any, List, Optional, Tuple, Literal, Dict
import inspect
import numpy as np
import pandas as pd

# Suppress NumPy divide-by-zero warnings from correlation calculations on constant columns
# These are expected when sensors have zero variance (constant values) and produce NaN correlations
warnings.filterwarnings("ignore", message="invalid value encountered in divide", category=RuntimeWarning)
from utils.timer import Timer
from core.observability import Span, Console

# Try polars
try:
    import polars as pl
    HAS_POLARS = True
except Exception:
    HAS_POLARS = False

if HAS_POLARS:
    _ROLLING_SUPPORTS_MIN_SAMPLES = "min_samples" in inspect.signature(pl.Expr.rolling_median).parameters
else:
    _ROLLING_SUPPORTS_MIN_SAMPLES = False

# Module-level timer for tracking performance
_timer = Timer()


def _rolling_kwargs(min_periods: int) -> Dict[str, int]:
    return {"min_samples": min_periods} if _ROLLING_SUPPORTS_MIN_SAMPLES else {"min_periods": min_periods}


def _to_pandas(df) -> pd.DataFrame:
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        return df.to_pandas()
    if isinstance(df, pd.DataFrame):
        return df
    raise TypeError("Unsupported dataframe type")


FillMethod = Literal["median", "ffill", "bfill", "interpolate", "none"]


def _apply_fill(
    df, 
    method: FillMethod = "median", 
    fill_values: Optional[dict] = None,
    mode: str = "train"
):
    """Apply fill strategy to handle missing values. Supports both Polars and pandas.
    
    P1-FIX (v11.2.3): ANALYTICAL AUDIT FLAW #6 - Feature imputation validation
    Added mandatory 'mode' parameter to enforce correct usage patterns:
    - mode="train": Can compute fill values from data (self-imputation is OK)
    - mode="score": MUST provide fill_values from training set (prevents data leakage)
    
    CRITICAL DATA LEAKAGE PATTERN:
    If score data computes its own median/mean for imputation, the model is using
    future information that wouldn't be available in production. This inflates
    performance metrics and creates unrealistic predictions.
    
    Parameters
    ----------
    df : DataFrame
        Input dataframe (Polars or pandas)
    method : FillMethod
        Fill strategy: "median", "ffill", "bfill", "interpolate", or "none"
    fill_values : dict, optional
        Pre-computed fill values {column_name: fill_value}. If provided, these values
        are used instead of computing from the data (prevents data leakage when filling
        score data with train-derived statistics).
    mode : str
        Execution mode: "train" or "score". Enforces correct usage.
        
    Returns
    -------
    DataFrame
        Filled dataframe (same type as input)
    
    Raises
    ------
    ValueError
        If mode="score" and fill_values is None (would cause data leakage)
    """
    # P1-FIX: Validation guard for data leakage prevention
    if mode == "score" and fill_values is None and method in ("median", "mean"):
        raise ValueError(
            "CRITICAL DATA LEAKAGE PREVENTION: mode='score' requires fill_values from training set. "
            "Passing None would cause the model to compute statistics on test data, "
            "which inflates performance and creates unrealistic predictions. "
            "Fix: Pass fill_values={col: train_median} computed from training data."
        )
    
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        if method == "median":
            # Use with_columns to keep non-numeric columns
            # Corrected: Use the robust schema-based method to get numeric columns
            numeric_cols = [c for c, t in df.schema.items() if t in pl.NUMERIC_DTYPES]
            
            if fill_values is not None:
                # Use provided fill values (train-derived for score data)
                return df.with_columns([
                    pl.col(c).fill_null(fill_values.get(c, pl.col(c).median())) 
                    for c in numeric_cols
                ])
            else:
                # Compute from data (for train data)
                return df.with_columns([pl.col(c).fill_null(pl.col(c).median()) for c in numeric_cols])

        if method == "ffill":
            # Keep all columns; forward-fill wherever nulls appear
            return df.with_columns([pl.col(c).fill_null(strategy="forward") for c in df.columns])

        if method == "bfill":
            # Keep all columns; backward-fill wherever nulls appear
            return df.with_columns([pl.col(c).fill_null(strategy="backward") for c in df.columns])

        if method == "interpolate":
            # Interpolate is defined for numeric columns; keep non-numeric untouched.
            # Note: with_columns is correct here. select would drop non-numerics.
            return df.with_columns([
                pl.when(pl.col(c).is_numeric())
                  .then(pl.col(c).interpolate())
                  .otherwise(pl.col(c))
                  .alias(c)
                for c in df.columns
            ])

        return df  # method == "none"

    # --- Pandas path ---
    pdf = _to_pandas(df)
    if method == "median":
        if fill_values is not None:
            # Use provided fill values (train-derived for score data)
            return pdf.fillna(fill_values)
        else:
            # Compute from data (for train data)
            meds = pdf.select_dtypes(np.number).median()
            return pdf.fillna(meds)
    if method == "ffill":
        return pdf.fillna(method="ffill")
    if method == "bfill":
        return pdf.fillna(method="bfill")
    if method == "interpolate":
        return pdf.interpolate(limit_direction="both")
    return pdf


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


def rolling_median(df: pd.DataFrame, window: int, cols: Optional[List[str]] = None, min_periods: int = 1,
                   return_type: Literal["pandas", "polars"] = "pandas") -> pd.DataFrame:
    """Compute rolling median for specified columns. Returns DataFrame of medians.
    Prefers Polars if available and input is polars.
    """
    if cols is None:
        cols = list(df.columns)
    # Polars path
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        exprs = [
            pl.col(c).rolling_median(window, **_rolling_kwargs(min_periods)).alias(f"{c}_med")
            for c in cols
        ]
        pl_out = df.select(exprs)
        return pl_out if return_type == "polars" else pl_out.to_pandas()

    # pandas path
    pdf = _to_pandas(df)
    res = pdf[cols].rolling(window=window, min_periods=min_periods, center=False).median()
    res.columns = [c + "_med" for c in res.columns]
    return res


def rolling_mad(df: pd.DataFrame, window: int, cols: Optional[List[str]] = None, min_periods: int = 1,
                return_type: Literal["pandas", "polars"] = "pandas") -> pd.DataFrame:
    """Rolling median absolute deviation (MAD) per column."""
    if cols is None:
        cols = list(df.columns)
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        # Polars path: Use expressions for performance and correctness.
        exprs = []
        for c in cols:
            col_expr = pl.col(c)
            # Rolling median of the original series
            median_expr = col_expr.rolling_median(window, **_rolling_kwargs(min_periods))
            # Rolling MAD: rolling median of the absolute deviation from the rolling median
            mad_expr = (col_expr - median_expr).abs().rolling_median(window, **_rolling_kwargs(min_periods))
            exprs.append(mad_expr.alias(f"{c}_mad"))
        
        pl_out = df.select(exprs)
        return pl_out if return_type == "polars" else pl_out.to_pandas()

    pdf = _to_pandas(df)
    def mad(x):
        return np.median(np.abs(x - np.median(x)))
    res = pdf[cols].rolling(window=window, min_periods=min_periods).apply(mad, raw=True)
    res.columns = [c + "_mad" for c in res.columns]
    return res


def rolling_mean_std(df: pd.DataFrame, window: int, cols: Optional[List[str]] = None, min_periods: int = 1,
                    return_type: Literal["pandas", "polars"] = "pandas") -> pd.DataFrame:
    if cols is None:
        cols = list(df.columns)
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        exprs = []
        for c in cols:
            exprs.append(pl.col(c).rolling_mean(window, **_rolling_kwargs(min_periods)).alias(f"{c}_mean"))
            exprs.append(pl.col(c).rolling_std(window, **_rolling_kwargs(min_periods)).alias(f"{c}_std"))
        
        pl_out = df.select(exprs)
        return pl_out if return_type == "polars" else pl_out.to_pandas()

    pdf = _to_pandas(df)
    mean = pdf[cols].rolling(window=window, min_periods=min_periods).mean()
    std = pdf[cols].rolling(window=window, min_periods=min_periods).std()
    mean.columns = [c + "_mean" for c in mean.columns]
    std.columns = [c + "_std" for c in std.columns]
    return pd.concat([mean, std], axis=1)


def rolling_skew_kurt(df: pd.DataFrame, window: int, cols: Optional[List[str]] = None, min_periods: int = 1,
                      return_type: Literal["pandas", "polars"] = "pandas") -> pd.DataFrame:
    """Compute rolling skewness and kurtosis for specified columns.
    Returns DataFrame with both metrics per column.
    """
    if cols is None:
        cols = list(df.columns)
    
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        # Refactor to use the idiomatic Polars expression API.
        exprs = []
        for c in cols:
            # Corrected: Use positional argument for window size
            exprs.append(pl.col(c).rolling_skew(window, bias=False).alias(f"{c}_skew"))
            exprs.append(pl.col(c).rolling_kurtosis(window, fisher=True).alias(f"{c}_kurt"))
        pl_out = df.select(exprs)
        return pl_out if return_type == "polars" else pl_out.to_pandas()

    pdf = _to_pandas(df)
    skew = pdf[cols].rolling(window=window, min_periods=min_periods).skew()
    kurt = pdf[cols].rolling(window=window, min_periods=min_periods).kurt()
    skew.columns = [c + "_skew" for c in skew.columns]
    kurt.columns = [c + "_kurt" for c in kurt.columns]
    return pd.concat([skew, kurt], axis=1)


def rolling_ols_slope(df: pd.DataFrame, window: int, cols: Optional[List[str]] = None, min_periods: int = 1,
                      return_type: Literal["pandas", "polars"] = "pandas") -> pd.DataFrame:
    """Compute rolling OLS slope for specified columns using proper linear regression.
    More robust than simple differencing, especially for noisy data.
    """
    if cols is None:
        cols = list(df.columns)
    
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        # Polars native implementation of rolling OLS slope. This is significantly
        # faster than using rolling_apply with a Python function. Robust fix using covariance.
        df_idx = df.with_columns(pl.arange(0, pl.len()).alias("_t").cast(pl.Float64))
        exprs = []
        for c in cols:
            x = pl.col(c).cast(pl.Float64)
            t = pl.col("_t")
            # slope = Cov(t,x) / Var(t)
            num = ( (t * x).rolling_mean(window, min_periods=min_periods)
                  - t.rolling_mean(window, min_periods=min_periods) * x.rolling_mean(window, min_periods=min_periods) )
            den = ( (t.pow(2)).rolling_mean(window, min_periods=min_periods)
                  - (t.rolling_mean(window, min_periods=min_periods)).pow(2) )
            slope_expr = (num / pl.when(den.abs() > 1e-12).then(den).otherwise(1.0)).alias(f"{c}_slope")
            exprs.append(slope_expr)
        
        if not exprs:
            return pl.DataFrame() if return_type == "polars" else pd.DataFrame()

        pl_out = df_idx.select(exprs)
        return pl_out if return_type == "polars" else pl_out.to_pandas()
    
    pdf = _to_pandas(df)
    slopes = pd.DataFrame(index=pdf.index)
    for c in cols:
        slopes[c + "_slope"] = pdf[c].rolling(window=window, min_periods=min_periods).apply(
            ols_slope, raw=True
        )
    return slopes

def ols_slope(x):
    """Helper function for pandas rolling apply. Not used by Polars."""
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



def rolling_spectral_energy(df: pd.DataFrame, window: int, cols: Optional[List[str]] = None, 
                          bands: Optional[List[Tuple[float, float]]] = None,
                          fs: float = 1.0, min_periods: int = 1,
                          return_type: Literal["pandas", "polars"] = "pandas",
                          method: Literal["auto", "fft", "goertzel"] = "auto") -> pd.DataFrame:
    """Compute rolling spectral energy in frequency bands for specified columns.
    For each window, computes FFT and returns energy in specified frequency bands.
    Returns DataFrame with band energies per column.

    Parameters
    ----------
    df : DataFrame
        Input dataframe (polars or pandas)
    window : int
        Window size for rolling computation
    cols : List[str], optional
        Columns to process. Defaults to all columns.
    bands : List[Tuple[float, float]], optional
        List of (low, high) frequency pairs defining bands.
        Frequencies in Hz relative to sampling rate fs.
        Defaults to [(0, 0.1*nyq), (0.1*nyq, 0.3*nyq), (0.3*nyq, nyq)]
    fs : float, default=1.0
        Sampling frequency in Hz. Used to scale frequency bands.
    min_periods : int, default=1
        Minimum number of observations required to calculate statistic

    Returns
    -------
    DataFrame
        DataFrame with columns named <col>_energy_<band_idx>
    """
    # Early exit for empty/small data
    if len(df) < window // 2:
        if return_type == "polars" and HAS_POLARS:
            return pl.DataFrame()
        return pd.DataFrame(index=df.index)
    if cols is None:
        cols = list(df.columns)

    nyq = 0.5 * fs
    if bands is None:
        bands = [(0.0, 0.1*nyq), (0.1*nyq, 0.3*nyq), (0.3*nyq, nyq)]
    
    def compute_band_energies(x):
        if len(x) < window // 2:  # need enough points for meaningful FFT
            return np.zeros(len(bands))
        try:
                # Prefer FFT for moderately-sized windows. The Goertzel per-bin
                # implementation is only beneficial for very small windows. Reduce
                # the Goertzel threshold so windows like 64 use FFT (much faster).
            if method == "goertzel" or (method == "auto" and window <= 32):
                return goertzel_energy(x, fs=fs, bands=bands)
            return spectral_energy(x, fs=fs, bands=bands)
        except:
            return np.zeros(len(bands))
    
    # Polars path
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        # Pre-allocate output expressions
        energy_exprs = []
        
        def compute_all_bands_np(x: np.ndarray) -> list[float]:
            if len(x) < max(min_periods, window // 2): return [0.0]*len(bands)
            x = x - np.mean(x)
            freqs = np.fft.rfftfreq(len(x), d=1.0/fs)
            spec  = np.abs(np.fft.rfft(x))**2
            out = []
            for lo, hi in bands:
                mask = (freqs >= lo) & (freqs < hi)
                out.append(float(np.sum(spec[mask])))
            return out

        for c in cols:
            # Version-gate the implementation. rolling_list is a more recent addition.
            if hasattr(pl.Expr, "rolling_list"):
                # Use rolling_list + map_elements to avoid version-specific .rolling().apply() signatures
                lst = pl.col(c).rolling_list(window_size=window, min_periods=min_periods)
                arr = lst.map_elements(
                    lambda v: compute_all_bands_np(np.asarray(v, float)),
                    return_dtype=pl.List(pl.Float64)
                )
            else:
                # Fallback for older Polars: use rolling apply with the correct 'period' keyword
                try:
                    arr = (pl.col(c)
                           .rolling(period=window, min_periods=min_periods)
                           .apply(
                               lambda s: compute_all_bands_np(np.asarray(s, dtype=float)),
                               return_dtype=pl.List(pl.Float64)
                           ))
                except Exception:
                    # If even that fails, this version of Polars is too old for this feature.
                    # We will let it produce an empty expression list, which will be handled downstream.
                    continue
            for i in range(len(bands)):
                energy_exprs.append(
                    arr.arr.get(i).fill_null(0.0).alias(f"{c}_energy_{i}")
                )

        pl_out = df.select(energy_exprs)
        if return_type == "polars":
            return pl_out
        return pl_out.to_pandas()
    
    # Pandas path (fixed: compute each band as scalar to avoid returning arrays to .apply)
    pdf = _to_pandas(df)
    results = []
    for c in cols:
        # create a DataFrame to hold per-band scalar series for this column
        energy_df = pd.DataFrame(index=pdf.index)
        for band_idx in range(len(bands)):
            idx = band_idx  # capture loop variable

            def band_scalar(x, _idx=idx):
                # x will be a numpy array when raw=True
                try:
                    if len(x) < window // 2:
                        return 0.0
                    # Align the pandas-side heuristic with the Polars/pandas
                    # decision above: only use Goertzel for small windows.
                    if method == "goertzel" or (method == "auto" and window <= 32):
                        return float(goertzel_energy(x, fs=fs, bands=bands)[_idx])
                    return float(spectral_energy(x, fs=fs, bands=bands)[_idx])
                except:
                    return 0.0

            series = pdf[c].rolling(window=window, min_periods=min_periods).apply(
                band_scalar, raw=True
            )
            energy_df[f"{c}_energy_{band_idx}"] = series.astype(float)
        # only append if we produced any columns (defensive)
        if len(energy_df.columns) > 0:
            results.append(energy_df)

    # return a concatenated frame; if no results, return empty frame with same index
    if results:
        out = pd.concat(results, axis=1)
        return out
    return pd.DataFrame(index=pdf.index)


def rolling_xcorr(df: pd.DataFrame, window: int, target_col: str, ref_cols: Optional[List[str]] = None,
                min_periods: int = 1, standardize: bool = True,
                return_type: Literal["pandas", "polars"] = "pandas") -> pd.DataFrame:
    """Compute rolling cross-correlation between target column and reference columns.
    
    Parameters
    ----------
    df : DataFrame
        Input dataframe (polars or pandas)
    window : int
        Window size for rolling computation
    target_col : str
        Name of target column to correlate against
    ref_cols : List[str], optional
        List of reference columns to correlate with target. Defaults to all columns except target.
    min_periods : int, default=1
        Minimum number of observations required to calculate correlation
    standardize : bool, default=True
        Whether to standardize (z-score) values before correlation. More robust but slower.
        When False, uses raw values which is faster but more sensitive to scaling.

    Returns
    -------
    DataFrame
        DataFrame with columns named <ref_col>_xcorr containing correlation coefficients
    """
    if ref_cols is None:
        ref_cols = [c for c in df.columns if c != target_col]
    
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataframe")
    
    # Polars path (safe expression building and early return)
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        exprs = []
        tgt = pl.col(target_col)
        for ref in ref_cols:
            # Corrected: Use positional window argument
            exprs.append(pl.rolling_corr(tgt, pl.col(ref), window, min_periods=min_periods).alias(f"{ref}_xcorr"))

        pl_out = df.select(exprs)
        return pl_out if return_type == "polars" else pl_out.to_pandas()
    
    # Pandas path
    pdf = _to_pandas(df)
    result = pd.DataFrame(index=pdf.index)
    target = pdf[target_col]
    for ref in ref_cols:
        result[f"{ref}_xcorr"] = target.rolling(window=window, min_periods=min_periods).corr(pdf[ref])
    if return_type == "polars" and HAS_POLARS:
        return pl.from_pandas(result)
    return result


def rolling_spectral_energy_pl(df: 'pl.DataFrame', window: int, cols: Optional[List[str]] = None,
                              bands: Optional[List[Tuple[float, float]]] = None,
                              fs: float = 1.0, min_periods: int = 1) -> 'pl.DataFrame':
    """Polars-native wrapper for `rolling_spectral_energy` that returns a pl.DataFrame.
    Requires Polars to be installed and a Polars DataFrame input.
    """
    if not HAS_POLARS:
        raise RuntimeError("Polars is not available in this environment")
    if not isinstance(df, pl.DataFrame):
        raise TypeError("df must be a Polars DataFrame for rolling_spectral_energy_pl")
    return rolling_spectral_energy(df, window, cols=cols, bands=bands, fs=fs, min_periods=min_periods, return_type="polars")


def rolling_pairwise_lag(df: pd.DataFrame, max_lag: int = 3, cols: Optional[List[str]] = None,
                         window: Optional[int] = None, min_periods: int = 1,
                         return_type: Literal["pandas", "polars"] = "pandas") -> pd.DataFrame:
    """Generate rolling pairwise lag features between all ordered column pairs.

    For each ordered pair (a, b) where a != b, and for each lag in [0, max_lag],
    compute the rolling correlation between a and b shifted by `lag`. Name columns
    as `<a>__<b>_lag<lag>_corr`.

    Note: For large numbers of columns, consider using batched_pairwise_lag() which
    provides memory-efficient batching and correlation thresholding.

    Parameters
    ----------
    df : DataFrame
        Input dataframe (polars or pandas)
    max_lag : int, default=3
        Maximum lag to compute (inclusive). Will generate features for lags 0...max_lag.
    cols : List[str], optional
        Columns to process. Defaults to all columns.
    window : int, optional
        Window size for rolling correlation. If None, uses max_lag + 1.
    min_periods : int, default=1
        Minimum number of valid observations required to calculate correlation.
    return_type : Literal["pandas", "polars"], default="pandas"
        Whether to return a pandas or polars DataFrame.

    Returns
    -------
    DataFrame
        DataFrame with columns named <a>__<b>_lag<lag>_corr containing correlations.
        The number of features is len(cols) * (len(cols)-1) * (max_lag+1).

    Examples
    --------
    >>> import polars as pl
    >>> import numpy as np
    >>> # Create sample data with time-lagged relationships
    >>> df = pl.DataFrame({
    ...     'sensor1': np.random.randn(100),
    ...     'sensor2': np.roll(np.random.randn(100), 2)  # lags sensor1 by 2
    ... })
    >>> # Compute pairwise lags up to lag 3
    >>> lag_feats = rolling_pairwise_lag(df, max_lag=3, window=10,
    ...                                 return_type="polars")
    >>> # Show correlation at lag 2 (should be strongest)
    >>> lag_feats.select("sensor1__sensor2_lag2_corr")
    """
    if cols is None:
        cols = list(df.columns)
    if window is None:
        window = max_lag + 1

    # Polars native path
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        exprs = []
        for i, a in enumerate(cols):
            for b in cols:
                if a == b:
                    continue
                for lag in range(0, max_lag + 1):
                    # Check for modern Polars API first
                    if hasattr(pl.Expr, "rolling_corr"):
                        # Corrected: Use positional window argument to avoid keyword friction
                        exprs.append(pl.col(a).rolling_corr(
                            pl.col(b).shift(lag), window, min_periods=min_periods
                        ).alias(f"{a}__{b}_lag{lag}_corr"))
                    # Fallback for older Polars versions that had pl.rolling_corr
                    elif hasattr(pl, "rolling_corr"):
                        exprs.append(
                            pl.rolling_corr(pl.col(a), pl.col(b).shift(lag), window, min_periods=min_periods).alias(f"{a}__{b}_lag{lag}_corr")
                        )
        pl_out = df.select(exprs)
        return pl_out if return_type == "polars" else pl_out.to_pandas()

    # Pandas path (stream pair-by-pair to limit peak memory)
    pdf = _to_pandas(df)
    out = pd.DataFrame(index=pdf.index)
    for a in cols:
        for b in cols:
            if a == b:
                continue
            for lag in range(0, max_lag + 1):
                series = pdf[a].rolling(window=window, min_periods=min_periods).corr(pdf[b].shift(lag))
                out[f"{a}__{b}_lag{lag}_corr"] = series
    if return_type == "polars" and HAS_POLARS:
        return pl.from_pandas(out)
    return out


def batched_pairwise_lag(df: pd.DataFrame, max_lag: int = 3, cols: Optional[List[str]] = None,
                        window: Optional[int] = None, min_periods: int = 1, batch_size: int = 100,
                        min_corr: float = 0.0, unique_pairs: bool = True,
                        return_type: Literal["pandas", "polars"] = "pandas") -> pd.DataFrame:
    """Generate rolling pairwise lag features between column pairs with optional batching and pruning.

    For each unique (unordered) pair (a, b) where a != b, compute rolling correlation between a and b
    shifted by lags 0...max_lag. Optional correlation threshold and unique-pairs mode reduce memory use.
    Features are named as '<a>__<b>_lag<lag>_corr' or vice versa depending on ordering in unique mode.
    
    Parameters
    ----------
    df : DataFrame
        Input dataframe (polars or pandas)
    max_lag : int, default=3
        Maximum lag to compute (inclusive). Will generate features for lags 0...max_lag.
    cols : List[str], optional
        Columns to process. Defaults to all columns.
    window : int, optional
        Window size for rolling correlation. If None, uses max_lag + 1.
    min_periods : int, default=1
        Minimum number of valid observations required to calculate correlation.
    batch_size : int, default=100
        Maximum number of column pairs to process at once. Lower this if memory is tight.
    min_corr : float, default=0.0
        Minimum absolute correlation threshold. Only pairs reaching this threshold
        (for any lag) are included in output. Set to 0 to keep all pairs.
    unique_pairs : bool, default=True
        If True, only compute each unordered pair once and use consistent column ordering.
        If False, compute all ordered pairs (a,b) and (b,a) separately.
    return_type : Literal["pandas", "polars"], default="pandas"
        Whether to return a pandas or polars DataFrame.
    
    Returns
    -------
    DataFrame
        DataFrame with columns named <a>__<b>_lag<lag>_corr containing correlations
        above min_corr threshold. With unique_pairs=True, a < b lexicographically.
    
    Examples
    --------
    >>> import polars as pl
    >>> import numpy as np
    >>> np.random.seed(42)
    >>> n = 1000
    >>> # Create sample data with time-lagged relationships
    >>> df = pl.DataFrame({
    ...     'x': np.random.randn(n),
    ...     'y': np.roll(np.random.randn(n), 2),  # y lags x by 2
    ...     'z': np.random.randn(n)  # independent
    ... })
    >>> # Compute pairwise lags, keeping only stronger correlations
    >>> lag_feats = batched_pairwise_lag(df, max_lag=3, min_corr=0.2,
    ...                                  return_type="polars")
    >>> # Show non-zero correlations
    >>> lag_feats.select([
    ...     pl.col("*").filter(pl.col("*").abs() > 0.2)
    ... ])
    """
    if cols is None:
        cols = list(df.columns)
    if window is None:
        window = max_lag + 1

    # Sort column names for consistent ordering in unique mode
    cols = sorted(cols)
    
    # Generate pairs to process
    pairs = []
    for i, a in enumerate(cols):
        for j, b in enumerate(cols):
            if unique_pairs:
                # Only process each unordered pair once, maintaining lexicographic order
                if i >= j:  # Skip if we've seen this pair or it's the same column
                    continue
            else:
                # Process all ordered pairs except self-pairs
                if a == b:
                    continue
            pairs.append((a, b))
    
    # Process pairs in batches to limit memory use
    all_results = []
    for batch_start in range(0, len(pairs), batch_size):
        batch_pairs = pairs[batch_start:batch_start + batch_size]
        
        # Polars path with expression batching
        if HAS_POLARS and isinstance(df, pl.DataFrame):
            # Pre-compute correlations for this batch
            exprs = []
            for a, b in batch_pairs:
                for lag in range(max_lag + 1):
                    exprs.append(
                        pl.col(a)
                        .rolling_corr(pl.col(b).shift(lag), window, min_periods=min_periods)
                        .alias(f"{a}__{b}_lag{lag}_corr")
                    )
            
            # Compute correlations for this batch
            batch_result = df.select(exprs)
            
            # If thresholding, only keep columns with any correlation above threshold
            if min_corr > 0:
                keep_cols = []
                for col in batch_result.columns:
                    if batch_result.select(pl.col(col).abs().max()).item() >= min_corr:
                        keep_cols.append(col)
                batch_result = batch_result.select(keep_cols) if keep_cols else None
            
            if batch_result is not None and len(batch_result.columns) > 0:
                all_results.append(batch_result)
        
        # Pandas path
        else:
            pdf = _to_pandas(df)
            batch_result = pd.DataFrame(index=pdf.index)
            
            for a, b in batch_pairs:
                # Compute all lags for this pair
                pair_results = []
                for lag in range(max_lag + 1):
                    series = pdf[a].rolling(window=window, min_periods=min_periods).corr(
                        pdf[b].shift(lag)
                    )
                    pair_results.append((f"{a}__{b}_lag{lag}_corr", series))
                
                # If thresholding, check if any lag correlation exceeds threshold
                if min_corr > 0:
                    max_corr = max(abs(s).max() for _, s in pair_results)
                    if max_corr < min_corr:
                        continue
                
                # Add correlations that passed threshold
                for name, series in pair_results:
                    batch_result[name] = series
            
            if len(batch_result.columns) > 0:
                all_results.append(batch_result)
    
    # Combine results
    if not all_results:
        # Return empty frame with correct type
        return (pl.DataFrame() if return_type == "polars" and HAS_POLARS
                else pd.DataFrame())
    
    if HAS_POLARS and isinstance(df, pl.DataFrame):
        out = pl.concat(all_results, how="horizontal")
        return out if return_type == "polars" else out.to_pandas()
    else:
        out = pd.concat(all_results, axis=1)
        if return_type == "polars" and HAS_POLARS:
            return pl.from_pandas(out)
        return out


@_timer.wrap("compute_basic_features_pl")
def compute_basic_features_pl(
    df: 'pl.DataFrame', 
    window: int = 3, 
    cols: Optional[List[str]] = None, 
    fill_values: Optional[dict] = None,
    mode: str = "train"
) -> 'pl.DataFrame':
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
    mode : str, default="train"
        Execution mode: "train" or "score". Enforces correct fill_values usage.

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
    if not HAS_POLARS:
        raise RuntimeError("Polars is not available in this environment")
    if not isinstance(df, pl.DataFrame):
        raise TypeError("df must be a Polars DataFrame for compute_basic_features_pl")

    if cols is None:
        cols = list(df.columns)

    # Fill missing values (Polars path) - use provided fill_values if available
    pl_filled = _apply_fill(df, method="median", fill_values=fill_values, mode=mode)

    # Rolling building blocks (request Polars outputs)
    med = rolling_median(pl_filled, window, cols, min_periods=1, return_type="polars")
    mad = rolling_mad(pl_filled, window, cols, min_periods=1, return_type="polars")
    ms = rolling_mean_std(pl_filled, window, cols, min_periods=1, return_type="polars")
    slopes = rolling_ols_slope(pl_filled, window, cols, min_periods=1, return_type="polars")
    sk = rolling_skew_kurt(pl_filled, window, cols, min_periods=1, return_type="polars")
    se = rolling_spectral_energy(pl_filled, window, cols, min_periods=1, return_type="polars")

    # Combine all parts first, then compute robust z-score
    parts = [med, mad, ms, slopes, sk, se]
    parts = [p for p in parts if p is not None and len(p.columns) > 0]
    if not parts:
        return pl.DataFrame()

    # Horizontally concatenate the base features with the original data to make all columns available
    combined_df = pl.concat([pl_filled, *parts], how="horizontal")

    # Now build and apply robust z expressions
    eps = 1e-9
    rz_exprs = []
    for c in cols:
        med_col = f"{c}_med"
        mad_col = f"{c}_mad"
        if med_col in combined_df.columns and mad_col in combined_df.columns:
            denom = (pl.col(mad_col) * 1.4826)
            denom_safe = pl.when(denom > eps).then(denom).otherwise(eps)
            rz = ((pl.col(c) - pl.col(med_col)) / (denom_safe + eps)).clip(-1e2, 1e2).alias(f"{c}_rz")
            rz_exprs.append(rz)

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


@_timer.wrap("compute_basic_features")
def compute_basic_features(
    pdf: pd.DataFrame, 
    window: int = 3, 
    cols: Optional[List[str]] = None, 
    fill_values: Optional[dict] = None,
    mode: str = "train"
) -> pd.DataFrame:
    """Compute a compact set of features for each timestamp using pandas input.
    Returns a pandas DataFrame aligned with input index.

    Features computed:
    - rolling_median: robust central tendency
    - rolling_mad: scale/variability (robust to outliers)
    - rolling_mean_std: classical location and scale
    - rolling_ols_slope: local trend (more stable than differencing)
    - rolling_skew_kurt: distribution shape
    - rolling_spectral_energy: frequency-domain energy in low/mid/high bands
    - robust_z: (x - rolling_median) / (rolling_mad * 1.4826)

    Parameters
    ----------
    pdf : pd.DataFrame
        Input pandas DataFrame. Will be converted if Polars input.
    window : int, default=3
        Window size for rolling computations.
    cols : List[str], optional
        Columns to process. Defaults to all columns.
    fill_values : dict, optional
        Pre-computed fill values {column_name: fill_value}. If provided, these values
        are used for imputation instead of computing from the data. This prevents data
        leakage when processing score data (use training-derived fill values).
    mode : str, default="train"
        Execution mode: "train" or "score". Enforces correct fill_values usage.

    Returns
    -------
    pd.DataFrame
        DataFrame containing computed features, aligned with input index.
        Missing values and infinities are replaced with 0.0.

    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> # Create sample data with different patterns
    >>> n = 1000
    >>> df = pd.DataFrame({
    ...     'normal': np.random.randn(n),
    ...     'spiky': np.random.randn(n) + (np.random.rand(n) > 0.95) * 10,
    ...     'trend': np.cumsum(np.random.randn(n) * 0.1)
    ... })
    >>> # Compute basic features with 10-point window
    >>> features = compute_basic_features(df, window=10)
    >>> # Show robust z-scores for spiky series
    >>> features['spiky_rz']  # Should highlight outliers
    """
    with Span("features.compute", n_samples=len(pdf), n_features=pdf.shape[1] if len(pdf) > 0 else 0, window=window):
        # =================================================================================
        # OPTIMIZATION: Use Polars-native implementation for all inputs when available.
        # Auto-convert pandas to Polars for significant performance gains (5-10x faster).
        # =================================================================================
        if HAS_POLARS:
            # Convert pandas to Polars if needed
            if isinstance(pdf, pd.DataFrame):
                try:
                    pdf_pl = pl.from_pandas(pdf)
                    features_pl = compute_basic_features_pl(pdf_pl, window=window, cols=cols, fill_values=fill_values, mode=mode)
                    return features_pl.to_pandas()
                except Exception:
                    pass  # Fall through to pandas implementation
            elif isinstance(pdf, pl.DataFrame):
                features_pl = compute_basic_features_pl(pdf, window=window, cols=cols, fill_values=fill_values, mode=mode)
                return features_pl.to_pandas()

        # --- Fallback to pandas implementation if Polars unavailable or failed ---
        pdf = _to_pandas(pdf)
        if cols is None:
            cols = list(pdf.columns)
        
        _timer.log("feature_params", window=window, n_cols=len(cols), n_rows=len(pdf))
        
        # default fill policy: median-based imputation for small windows
        # Use provided fill_values if available (prevents data leakage for score data)
        with _timer.section("fill_missing"):
            pdf_filled = _apply_fill(pdf, method="median", fill_values=fill_values, mode=mode)

        # --- Refactored Logic: Delegate to individual feature functions ---
        # This simplifies the orchestrator and removes redundant logic.
        med = rolling_median(pdf_filled, window, cols, min_periods=1, return_type="pandas")
        mad = rolling_mad(pdf_filled, window, cols, min_periods=1, return_type="pandas")
        ms = rolling_mean_std(pdf_filled, window, cols, min_periods=1, return_type="pandas")
        slopes = rolling_ols_slope(pdf_filled, window, cols, min_periods=1, return_type="pandas")
        sk = rolling_skew_kurt(pdf_filled, window, cols, min_periods=1, return_type="pandas")
        se = rolling_spectral_energy(pdf_filled, window, cols, min_periods=1, return_type="pandas")

        # robust z: (x - rolling_median) / (rolling_mad + eps)
        eps = 1e-9

        rz_df = pd.DataFrame(index=pdf_filled.index)

        for c in cols:
            m = med[f"{c}_med"] if f"{c}_med" in med.columns else 0.0
            md = mad[f"{c}_mad"] if f"{c}_mad" in mad.columns else pd.Series(np.full(len(pdf_filled), eps), index=pdf_filled.index)
            # clamp mad to avoid division by zero
            md_clamped = md.copy()
            md_clamped = md_clamped.where(md_clamped.abs() > eps, other=eps)
            # scale MAD to approximate std
            md_scaled = md_clamped * 1.4826
            # compute robust z and clamp
            rz = (pdf_filled[c] - m) / (md_scaled + eps)
            rz = rz.clip(lower=-1e2, upper=1e2)
            # replace infs/nans
            rz = rz.replace([np.inf, -np.inf], np.nan).fillna(0.0)
            rz_df[c + "_rz"] = rz

        # Concatenate all feature parts
        parts = [p for p in [med, mad, ms, slopes, sk, se, rz_df] if p is not None and not p.empty]
        if not parts:
            return pd.DataFrame(index=pdf.index)

        out = pd.concat(parts, axis=1)
        # ensure no infs/nans in final feature table
        out = out.replace([np.inf, -np.inf], np.nan)
        out = out.fillna(0.0)
        return out


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
) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    """
    Impute missing values and drop unusable columns from feature DataFrames.
    
    Handles:
    - Replace inf with NaN
    - Fill NaN with train column medians
    - Align score columns to train columns
    - Drop all-NaN and low-variance columns
    - Log dropped features via output_manager
    
    Args:
        train: Training features DataFrame
        score: Scoring features DataFrame
        low_var_threshold: Minimum std deviation to keep a column
        output_manager: OutputManager instance for logging dropped features
        run_id: Run identifier
        equip_id: Equipment ID
        equip: Equipment name for logging
        
    Returns:
        Tuple of (train_imputed, score_imputed, dropped_cols)
    """
    # Replace inf with NaN
    train = train.copy()
    score = score.copy()
    train.replace([np.inf, -np.inf], np.nan, inplace=True)
    score.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    col_meds = train.median(numeric_only=True)
    train.fillna(col_meds, inplace=True)
    
    # Align score to train columns
    score = score.reindex(columns=train.columns)
    score.fillna(col_meds, inplace=True)
    
    # Fill remaining NaNs with score medians
    nan_cols = score.columns[score.isna().any()].tolist()
    for c in nan_cols:
        if score[c].dtype.kind in "if":
            score[c].fillna(score[c].median(), inplace=True)
    
    # Find columns to drop: all-NaN or low-variance
    all_nan_cols = [c for c in train.columns if pd.isna(col_meds.get(c))]
    feat_stds = train.std(numeric_only=True)
    low_var_cols = list(feat_stds[feat_stds < low_var_threshold].index)
    cols_to_drop = list(set(all_nan_cols + low_var_cols))
    
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

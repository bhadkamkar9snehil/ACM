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
from core.time_normalizer import (
    deduplicate_index as _deduplicate_index,
    ensure_local_index as _ensure_local_index,
)

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
    """Backward-compatible wrapper around core.time_normalizer.ensure_local_index."""
    return _ensure_local_index(df)


def deduplicate_index(
    df: pd.DataFrame,
    name: str,
    equip: str = "",
) -> Tuple[pd.DataFrame, int]:
    """Backward-compatible wrapper around core.time_normalizer.deduplicate_index."""
    return _deduplicate_index(df, name, equip)


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
            out[start:, b_idx] = spec[:, mask].sum(axis=1)
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


def rolling_xcorr(df: pl.DataFrame, window: int, target_col: str, ref_cols: Optional[List[str]] = None,
                min_periods: int = 1) -> pl.DataFrame:
    """Compute rolling cross-correlation between target column and reference columns.
    Requires Polars DataFrame input. Returns pl.DataFrame with <ref_col>_xcorr columns.
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("rolling_xcorr requires a Polars DataFrame input")
    if ref_cols is None:
        ref_cols = [c for c in df.columns if c != target_col]
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataframe")
    exprs = [
        pl.rolling_corr(pl.col(target_col), pl.col(ref), window_size=window, min_samples=min_periods).alias(f"{ref}_xcorr")
        for ref in ref_cols
    ]
    return df.select(exprs)


# rolling_spectral_energy_pl is identical to rolling_spectral_energy (kept for call-site compat)
rolling_spectral_energy_pl = rolling_spectral_energy


def rolling_pairwise_lag(df: pl.DataFrame, max_lag: int = 3, cols: Optional[List[str]] = None,
                         window: Optional[int] = None, min_periods: int = 1) -> pl.DataFrame:
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

    if not isinstance(df, pl.DataFrame):
        raise TypeError("rolling_pairwise_lag requires a Polars DataFrame input")
    exprs = []
    for a in cols:
        for b in cols:
            if a == b:
                continue
            for lag in range(0, max_lag + 1):
                exprs.append(
                    pl.rolling_corr(pl.col(a), pl.col(b).shift(lag), window_size=window, min_samples=min_periods)
                    .alias(f"{a}__{b}_lag{lag}_corr")
                )
    return df.select(exprs)


def batched_pairwise_lag(df: pl.DataFrame, max_lag: int = 3, cols: Optional[List[str]] = None,
                        window: Optional[int] = None, min_periods: int = 1, batch_size: int = 100,
                        min_corr: float = 0.0, unique_pairs: bool = True) -> pl.DataFrame:
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
    
    if not isinstance(df, pl.DataFrame):
        raise TypeError("batched_pairwise_lag requires a Polars DataFrame input")

    # Process pairs in batches to limit memory use
    all_results: list = []
    for batch_start in range(0, len(pairs), batch_size):
        batch_pairs = pairs[batch_start:batch_start + batch_size]
        exprs = []
        for a, b in batch_pairs:
            for lag in range(max_lag + 1):
                exprs.append(
                    pl.rolling_corr(pl.col(a), pl.col(b).shift(lag), window_size=window, min_samples=min_periods)
                    .alias(f"{a}__{b}_lag{lag}_corr")
                )
        batch_result = df.select(exprs)
        if min_corr > 0:
            keep_cols = [
                col for col in batch_result.columns
                if batch_result.select(pl.col(col).abs().max()).item() >= min_corr
            ]
            if not keep_cols:
                continue
            batch_result = batch_result.select(keep_cols)
        if len(batch_result.columns) > 0:
            all_results.append(batch_result)

    if not all_results:
        return pl.DataFrame()

    return pl.concat(all_results, how="horizontal")


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

    # Combine all parts first, then compute robust z-score
    parts = [med, mad, ms, slopes, sk, se]
    # Defensive normalization while migration is in progress:
    # avoid pl.concat failures if any helper accidentally returns pandas.
    parts = [pl.from_pandas(p) if isinstance(p, pd.DataFrame) else p for p in parts]
    parts = [p for p in parts if p is not None and len(p.columns) > 0]
    if not parts:
        return pl.DataFrame()

    # Horizontally concatenate the base features with the original data to make all columns available
    combined_df = pl.concat([pl_filled, *parts], how="horizontal")

    # Now build and apply robust z expressions
    # FIX: Match Pandas behavior - create rz columns even if med/mad missing (use fallback values)
    eps = 1e-9
    rz_exprs = []
    for c in cols:
        med_col = f"{c}_med"
        mad_col = f"{c}_mad"
        # Check if columns exist, otherwise use fallback values
        if med_col in combined_df.columns and mad_col in combined_df.columns:
            # Normal case: both med and mad exist
            denom = (pl.col(mad_col) * 1.4826)
            denom_safe = pl.when(denom > eps).then(denom).otherwise(eps)
            rz = ((pl.col(c) - pl.col(med_col)) / (denom_safe + eps)).clip(-1e2, 1e2).alias(f"{c}_rz")
        else:
            # Fallback case: med or mad missing - create zero-valued rz column to match Pandas
            # This ensures deterministic feature count across Polars/Pandas implementations
            rz = pl.lit(0.0).alias(f"{c}_rz")
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

def build_features_for_pipeline(
    train: pd.DataFrame,
    score: pd.DataFrame,
    cfg: Dict[str, Any],
    equip: str = "",
    raw_fill_values_override: Optional[Dict[str, float]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build engineered features for ACM pipeline train/score frames.

    Keeps fill-value derivation strictly from TRAIN data to avoid leakage.
    """
    feat_win = int((cfg.get("features", {}) or {}).get("window", 3))
    Console.info(f"Building features with window={feat_win}", component="FEAT", equip=equip)

    idx_train = train.index
    idx_score = score.index

    # TRAIN-only fill values prevent leakage to SCORE. Empty-train scoring paths
    # can reuse cached raw training medians instead of borrowing from score data.
    train_fill_values: Optional[Dict[str, float]] = None
    if raw_fill_values_override:
        train_fill_values = dict(raw_fill_values_override)
        Console.info(
            f"Using {len(train_fill_values)} cached raw fill values from training reference",
            component="FEAT",
            equip=equip,
        )
    elif len(train) > 0:
        train_fill_values = train.select_dtypes(include=[np.number]).median().to_dict()
        Console.info(
            f"Computed {len(train_fill_values)} fill values from training data",
            component="FEAT",
            equip=equip,
        )
    else:
        Console.warn(
            "Train is empty and no cached raw fill values are available; "
            "score feature build will fall back to score-derived fill values",
            component="FEAT",
            equip=equip,
        )

    if len(train) > 0:
        train_feat = compute_basic_features_pl(
            pl.from_pandas(train),
            window=feat_win,
        )
    else:
        train_feat = pd.DataFrame(index=idx_train)
    score_feat = compute_basic_features_pl(
        pl.from_pandas(score),
        window=feat_win,
        fill_values=train_fill_values,
    )

    if not isinstance(train_feat, pd.DataFrame):
        train_feat = train_feat.to_pandas() if hasattr(train_feat, "to_pandas") else pd.DataFrame(train_feat)
    if not isinstance(score_feat, pd.DataFrame):
        score_feat = score_feat.to_pandas() if hasattr(score_feat, "to_pandas") else pd.DataFrame(score_feat)

    if len(train) > 0:
        train_feat.index = idx_train
    else:
        train_feat = pd.DataFrame(index=idx_train, columns=score_feat.columns, dtype=float)
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
    median_values_override: Optional[Dict[str, float]] = None,
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

    # Compute column medians from train (nanmedian ignores NaN, shape: n_cols).
    # Empty-train scoring paths can reuse cached feature medians instead of
    # deriving them from score data.
    if tr.shape[0] == 0 and train_cols:
        if median_values_override:
            col_meds = pd.Series(median_values_override, index=train_cols, dtype=float).reindex(train_cols)
            col_meds_np = col_meds.to_numpy(dtype=np.float64, copy=True)
            Console.info(
                f"Using {int(col_meds.notna().sum())} cached feature medians for score-only imputation",
                component="FEAT",
                equip=equip,
            )
        else:
            col_meds_np = np.full(len(train_cols), np.nan, dtype=np.float64)
            col_meds = pd.Series(col_meds_np, index=train_cols)
            Console.warn(
                "Train feature frame is empty and no cached feature medians are available; "
                "score imputation will fall back to score-derived medians",
                component="FEAT",
                equip=equip,
            )
    else:
        col_meds_np = np.nanmedian(tr, axis=0)  # faster than pd.DataFrame.median()
        col_meds = pd.Series(col_meds_np, index=train_cols)

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


@dataclass
class SeasonalityPreparationResult:
    """Result bundle for the raw seasonality-adjustment stage."""
    train: pd.DataFrame
    score: pd.DataFrame
    seasonal_patterns: Dict[str, List[Any]]


def _is_coldstart_meta(meta: Any) -> bool:
    """Return True if current run meta indicates coldstart run."""
    if isinstance(meta, dict):
        return bool(meta.get("is_coldstart_run", False))
    return bool(getattr(meta, "is_coldstart_run", False))


def run_seasonality_preparation_stage(
    *,
    train: pd.DataFrame,
    score: pd.DataFrame,
    cfg: Dict[str, Any],
    equip: str,
    section_fn: Any,
    detect_and_adjust_fn: Any,
) -> SeasonalityPreparationResult:
    """Run only the seasonality-detect/adjust stage used ahead of feature prep."""
    seasonal_patterns: Dict[str, List[Any]] = {}
    with section_fn("seasonality.detect"):
        train, score, seasonal_patterns, _ = detect_and_adjust_fn(
            train=train,
            score=score,
            cfg=cfg,
            logger=Console,
            equip=equip,
        )
    return SeasonalityPreparationResult(
        train=train,
        score=score,
        seasonal_patterns=seasonal_patterns,
    )


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
    load_cached_raw_signal_medians_fn: Optional[Any] = None,
    load_cached_feature_medians_fn: Optional[Any] = None,
    seasonality_result: Optional[SeasonalityPreparationResult] = None,
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
    if seasonality_result is None:
        seasonality_result = run_seasonality_preparation_stage(
            train=train,
            score=score,
            cfg=cfg,
            equip=equip,
            section_fn=section_fn,
            detect_and_adjust_fn=detect_and_adjust_fn,
        )
    train = seasonality_result.train
    score = seasonality_result.score
    seasonal_patterns = seasonality_result.seasonal_patterns

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

    cached_raw_fill_values = None
    if (
        train.empty
        and not _is_coldstart_meta(meta)
        and load_cached_raw_signal_medians_fn is not None
    ):
        cached_raw_fill_values = load_cached_raw_signal_medians_fn(
            equip=equip,
            sql_client=sql_client,
            equip_id=equip_id,
            cfg=cfg,
            input_columns=list(score.columns),
            logger=Console,
        )

    with section_fn("features.build"):
        train, score = build_features_for_pipeline(
            train=train,
            score=score,
            cfg=cfg,
            equip=equip,
            raw_fill_values_override=cached_raw_fill_values,
        )

    cached_feature_medians = None
    if (
        train.empty
        and not _is_coldstart_meta(meta)
        and load_cached_feature_medians_fn is not None
    ):
        cached_feature_medians = load_cached_feature_medians_fn(
            equip=equip,
            sql_client=sql_client,
            equip_id=equip_id,
            cfg=cfg,
            feature_columns=list(score.columns),
            logger=Console,
        )

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
            median_values_override=cached_feature_medians,
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

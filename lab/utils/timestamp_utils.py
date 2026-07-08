"""
FOR-DQ-02: Centralized timestamp normalization utilities.

All ACM timestamps are stored as timezone-naive local time (not UTC).
This module provides consistent helpers to strip timezone info from
various pandas timestamp structures.

Policy: "All timestamps are stored as naive local time"
- No UTC conversions
- Strip timezone info before SQL writes
- Apply consistently across all modules
"""

from typing import Optional, Union, List
import pandas as pd


def normalize_timestamp_scalar(ts) -> Optional[pd.Timestamp]:
    """
    Convert a scalar timestamp to timezone-naive local time.
    
    Args:
        ts: Timestamp-like value (pd.Timestamp, datetime, string, or None)
    
    Returns:
        Timezone-naive pd.Timestamp or None if invalid
    
    Examples:
        >>> normalize_timestamp_scalar("2024-01-01 12:00:00+00:00")
        Timestamp('2024-01-01 12:00:00')
        >>> normalize_timestamp_scalar(None)
        None
    """
    if ts is None or (isinstance(ts, float) and pd.isna(ts)):
        return None
    try:
        result = pd.to_datetime(ts, errors='coerce')
        if pd.isna(result):
            return None
        # Strip timezone info if present
        if hasattr(result, 'tz') and result.tz is not None:
            return result.tz_localize(None)
        return result
    except Exception:
        return None


def normalize_timestamp_series(
    idx_or_series: Union[pd.Index, pd.Series]
) -> pd.Series:
    """
    Convert an Index or Series to timezone-naive local timestamps.
    
    Args:
        idx_or_series: pandas Index or Series with datetime values
    
    Returns:
        Series of timezone-naive timestamps with original index
    
    Examples:
        >>> idx = pd.DatetimeIndex(['2024-01-01+00:00'], tz='UTC')
        >>> normalize_timestamp_series(idx)
        0   2024-01-01
        dtype: datetime64[ns]
    """
    if isinstance(idx_or_series, pd.Index):
        series = pd.Series(idx_or_series, index=idx_or_series)
    else:
        series = idx_or_series.copy()
    
    # Convert to datetime if not already
    series = pd.to_datetime(series, errors='coerce')
    
    # Strip timezone if present
    if hasattr(series.dt, 'tz') and series.dt.tz is not None:
        series = series.dt.tz_localize(None)
    
    return series


def normalize_timestamps(
    df: pd.DataFrame,
    cols: Optional[List[str]] = None,
    inplace: bool = False
) -> pd.DataFrame:
    """
    Convert specified DataFrame columns to timezone-naive local time.
    
    Args:
        df: DataFrame with timestamp columns
        cols: List of column names to normalize. If None, normalizes all datetime columns.
        inplace: If True, modifies df in-place. If False, returns a copy.
    
    Returns:
        DataFrame with normalized timestamp columns
    
    Examples:
        >>> df = pd.DataFrame({'Timestamp': ['2024-01-01+00:00']})
        >>> normalize_timestamps(df, cols=['Timestamp'])
        # Returns df with Timestamp column as naive datetime
    """
    df_out = df if inplace else df.copy()
    
    # If no columns specified, find all datetime columns
    if cols is None:
        cols = [col for col in df_out.columns if pd.api.types.is_datetime64_any_dtype(df_out[col])]
    
    for col in cols:
        if col not in df_out.columns:
            continue
        
        # Convert to datetime if not already
        df_out[col] = pd.to_datetime(df_out[col], errors="coerce")
        
        # Strip timezone if present
        try:
            if df_out[col].dt.tz is not None:
                df_out[col] = df_out[col].dt.tz_localize(None)
        except (AttributeError, TypeError):
            # Column is not datetime or already naive; skip
            pass
    
    return df_out


def normalize_index(df: pd.DataFrame, inplace: bool = False) -> pd.DataFrame:
    """
    Normalize DataFrame index to timezone-naive local time if it's a DatetimeIndex.
    
    Args:
        df: DataFrame with DatetimeIndex
        inplace: If True, modifies df in-place. If False, returns a copy.
    
    Returns:
        DataFrame with normalized index
    
    Examples:
        >>> df = pd.DataFrame({'value': [1]}, index=pd.DatetimeIndex(['2024-01-01+00:00']))
        >>> normalize_index(df)
        # Returns df with naive datetime index
    """
    df_out = df if inplace else df.copy()
    
    if isinstance(df_out.index, pd.DatetimeIndex):
        if df_out.index.tz is not None:
            df_out.index = df_out.index.tz_localize(None)
    
    return df_out


# =======================
# Index Mapping Utilities
# =======================

def nearest_indexer(index: pd.Index, targets, label: str = "indexer"):
    """Map target timestamps to index positions using nearest matches.

    Returns an array of index locations where ``-1`` denotes missing targets.
    Handles non-monotonic indexes by operating on a sorted view and falls back
    to a NumPy search path when Pandas raises for complex target shapes.
    
    Args:
        index: pandas Index (typically DatetimeIndex) to map against
        targets: Sequence of timestamps to find nearest matches for
        label: Debug label for logging (default: "indexer")
        
    Returns:
        numpy array of int positions (-1 for missing)
    """
    import numpy as np
    from core.observability import Console
    
    if index.empty:
        return np.full(len(targets), -1, dtype=int) if hasattr(targets, "__len__") else np.array([], dtype=int)

    if not hasattr(targets, "__len__"):
        targets = list(targets)

    if len(targets) == 0:
        return np.empty(0, dtype=int)

    target_dt = pd.to_datetime(targets, errors="coerce")
    if isinstance(target_dt, pd.Series):
        target_dt = target_dt.to_numpy()
    target_idx = pd.DatetimeIndex(target_dt)
    result = np.full(target_idx.shape[0], -1, dtype=int)

    valid_mask = ~target_idx.isna()
    if not valid_mask.any():
        return result

    work_index = pd.DatetimeIndex(index)
    if not work_index.is_monotonic_increasing:
        work_index = work_index.sort_values()

    try:
        locs = work_index.get_indexer(target_idx, method="nearest")
    except (ValueError, TypeError) as err:
        Console.warn(f"[{label}] Falling back to manual nearest mapping: {err}", component="DATA",
                     indexer_label=label, error_type=type(err).__name__, error=str(err)[:200])
        idx_values = work_index.asi8
        target_values = target_idx.asi8[valid_mask]
        if target_values.size and idx_values.size:
            pos = np.searchsorted(idx_values, target_values, side="left")
            right_idx = np.clip(pos, 0, len(idx_values) - 1)
            left_idx = np.clip(pos - 1, 0, len(idx_values) - 1)
            right_dist = np.abs(idx_values[right_idx] - target_values)
            left_dist = np.abs(idx_values[left_idx] - target_values)
            chosen = np.where(right_dist < left_dist, right_idx, left_idx)
            result[valid_mask] = chosen.astype(int)
        return result

    locs = np.asarray(locs, dtype=int)
    result[valid_mask] = locs[valid_mask]
    return result

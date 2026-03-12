"""
Shared timestamp and index normalization helpers for ACM.

This module centralizes the observation-normalization primitives that were
previously split across data loading, feature preparation, and output shaping.
The functions here intentionally preserve current behavior so callers can move
to a single owner without changing runtime semantics.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple, cast

import numpy as np
import pandas as pd

from core.observability import Console


def parse_ts_index(df: pd.DataFrame, ts_col: str) -> pd.DataFrame:
    """Parse a timestamp column and promote it to the sorted index."""
    if ts_col not in df.columns:
        raise ValueError(f"Timestamp column '{ts_col}' not found")
    df = df.copy()
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
    return df.set_index(ts_col).sort_index()


def ensure_local_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure the DataFrame index is a timezone-naive local DatetimeIndex.

    ACM currently treats timestamps as local wall-clock time once loaded and
    strips timezone metadata if present.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors="coerce")
    else:
        try:
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
        except Exception:
            df.index = pd.to_datetime(df.index, errors="coerce")
    return df


def deduplicate_index(
    df: pd.DataFrame,
    name: str,
    equip: str = "",
) -> Tuple[pd.DataFrame, int]:
    """Remove duplicate timestamps from the index, keeping the last value."""
    dup_count = int(df.index.duplicated(keep="last").sum())

    if dup_count > 0:
        Console.warn(
            f"Removing {dup_count} duplicate timestamps from {name} data",
            component="DATA",
            equip=equip,
            duplicates=dup_count,
            dataset=name,
        )
        df = df[~df.index.duplicated(keep="last")].sort_index()

    if not df.index.is_unique:
        raise RuntimeError(
            f"[DATA] {name} data still has duplicate timestamps after deduplication! "
            f"Total: {len(df)}, Unique: {df.index.nunique()}"
        )

    return df, dup_count


def coerce_local_and_filter_future(
    df: pd.DataFrame,
    label: str,
    now_cutoff: pd.Timestamp,
) -> Tuple[pd.DataFrame, int, int]:
    """Normalize index timestamps and drop rows beyond the configured cutoff."""
    tz_stripped = 0
    if not isinstance(df.index, pd.DatetimeIndex):
        coerced_index = pd.to_datetime(df.index, errors="coerce")
        try:
            if getattr(coerced_index, "tz", None) is not None:
                tz_stripped = len(df)
                coerced_index = coerced_index.tz_localize(None)
        except Exception:
            coerced_index = pd.to_datetime(coerced_index, errors="coerce")
        df.index = coerced_index
    else:
        try:
            if df.index.tz is not None:
                tz_stripped = len(df)
                df.index = df.index.tz_localize(None)
        except Exception:
            df.index = pd.to_datetime(df.index, errors="coerce")

    before_drop = len(df)
    df = df[~df.index.isna()]
    if before_drop and len(df) != before_drop:
        Console.warn(
            f"Dropped {before_drop - len(df)} rows with invalid timestamps from {label}",
            component="DATA",
            label=label,
            rows_dropped=before_drop - len(df),
            rows_remaining=len(df),
        )

    future_mask = df.index > now_cutoff
    future_rows = int(future_mask.sum())
    if future_rows:
        Console.warn(
            f"Dropping {future_rows} future timestamp row(s) from {label} (cutoff={now_cutoff:%Y-%m-%d %H:%M:%S})",
            component="DATA",
            label=label,
            future_rows=future_rows,
            cutoff=str(now_cutoff),
        )
        df = df[~future_mask]

    return df, tz_stripped, future_rows


def native_cadence_secs(idx: pd.DatetimeIndex) -> float:
    """Estimate native cadence in seconds from index deltas."""
    if len(idx) < 2:
        return float("inf")
    diffs = idx.to_series().diff().dropna()
    med = diffs.median()
    try:
        return float(getattr(med, "total_seconds", lambda: float(med))())
    except Exception:
        try:
            return float(np.median(diffs))
        except Exception:
            return float("inf")


def check_cadence(
    idx: pd.DatetimeIndex,
    sampling_secs: Optional[int],
    jitter_ratio: float = 0.05,
) -> bool:
    """Check whether an index is regular enough for the expected cadence."""
    if sampling_secs is None or len(idx) < 2:
        return True
    diffs = idx.to_series().diff().dropna()
    expected = pd.Timedelta(seconds=sampling_secs)
    tolerance = expected * jitter_ratio
    return bool(((diffs - expected).abs() <= tolerance).mean() >= 0.9)


def resample_df(
    df: pd.DataFrame,
    sampling_secs: int,
    interp_method: str = "linear",
    strict: bool = False,
    max_gap_secs: int = 300,
    max_fill_ratio: float = 0.2,
) -> pd.DataFrame:
    """Resample a DataFrame to regular intervals using the current ACM policy."""
    if df.empty:
        return df
    if df.index.min() == df.index.max():
        return df

    freq = f"{sampling_secs}s"
    regular_idx = pd.date_range(start=df.index.min(), end=df.index.max(), freq=freq)
    df_resampled = df.reindex(regular_idx)

    if interp_method != "none":
        max_gap_periods = max_gap_secs // sampling_secs
        df_resampled = df_resampled.interpolate(
            method=cast(Any, interp_method),
            limit=max_gap_periods,
            limit_direction="both",
        )

    if strict:
        fill_ratio = df_resampled.isnull().sum().sum() / (
            len(df_resampled) * len(df_resampled.columns)
        )
        if fill_ratio > max_fill_ratio:
            raise ValueError(
                f"Too much missing data after resample: {fill_ratio:.1%} > {max_fill_ratio:.1%}"
            )

    return df_resampled

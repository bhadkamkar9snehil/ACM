"""
Governed state snapshot construction for shadow representation.

This module owns the asset-time state primitives that sit in front of the
representation pipeline. The implementation is intentionally a pure extraction
of the current shadow-state behavior so ownership changes without changing
authority.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd

from core.representation_contracts import ObservationIntegrity, StateSnapshot, meta_get
from core.time_normalizer import native_cadence_secs


def _coerce_dt(value: Any) -> Optional[datetime]:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, datetime):
        return value
    try:
        return pd.Timestamp(value).to_pydatetime()
    except Exception:
        return None


def _infer_sampling_seconds(df: pd.DataFrame, meta: Any) -> Optional[float]:
    meta_sampling = meta_get(meta, "sampling_seconds", None)
    if meta_sampling not in (None, 0):
        try:
            return float(meta_sampling)
        except Exception:
            pass
    if len(df.index) < 2 or not isinstance(df.index, pd.DatetimeIndex):
        return None
    cadence = native_cadence_secs(df.index)
    if not np.isfinite(cadence) or cadence <= 0:
        return None
    return float(cadence)


def _expected_rows(df: pd.DataFrame, sampling_seconds: Optional[float]) -> int:
    if df.empty:
        return 0
    if sampling_seconds is None or sampling_seconds <= 0:
        return int(len(df))
    if not isinstance(df.index, pd.DatetimeIndex):
        return int(len(df))
    span_seconds = max(0.0, (df.index.max() - df.index.min()).total_seconds())
    return max(1, int(round(span_seconds / sampling_seconds)) + 1)


def _missingness_grade(missing_ratio: float) -> str:
    if missing_ratio <= 0.05:
        return "GOOD"
    if missing_ratio <= 0.20:
        return "FAIR"
    return "POOR"


def build_observation_integrity(df: pd.DataFrame, meta: Any) -> ObservationIntegrity:
    """Build the current shadow observation-integrity contract for one window."""
    observed_rows = int(len(df))
    numeric = df.select_dtypes(include=[np.number]) if not df.empty else pd.DataFrame(index=df.index)
    expected_rows = _expected_rows(df, _infer_sampling_seconds(df, meta))
    coverage_ratio = float(observed_rows / expected_rows) if expected_rows > 0 else 0.0
    coverage_ratio = max(0.0, min(1.0, coverage_ratio))

    if numeric.shape[1] > 0 and observed_rows > 0:
        missing_ratio = float(numeric.isna().mean().mean())
        effective_signal_count = int((numeric.notna().any(axis=0)).sum())
    else:
        missing_ratio = 1.0 if observed_rows else 0.0
        effective_signal_count = 0

    return ObservationIntegrity(
        coverage_ratio=coverage_ratio,
        stale_ratio=0.0,
        missingness_grade=_missingness_grade(missing_ratio),
        effective_signal_count=effective_signal_count,
        expected_rows=expected_rows,
        observed_rows=observed_rows,
        duplicate_rows_removed=int(meta_get(meta, "dup_timestamps_removed", 0) or 0),
        future_rows_dropped=int(meta_get(meta, "future_rows_dropped", 0) or 0),
    )


def build_state_snapshot(
    *,
    df: pd.DataFrame,
    meta: Any,
    equip_id: int,
    run_id: str,
    window_label: str,
) -> Optional[StateSnapshot]:
    """Build a shadow state snapshot for a train or score window."""
    if df is None or df.empty:
        return None
    if isinstance(df.index, pd.DatetimeIndex):
        source_start = _coerce_dt(df.index.min())
        source_end = _coerce_dt(df.index.max())
    else:
        source_start = _coerce_dt(meta_get(meta, "start_ts", None))
        source_end = _coerce_dt(meta_get(meta, "end_ts", None))

    return StateSnapshot(
        asset_id=int(equip_id),
        batch_end_time=source_end,
        run_id=str(run_id),
        source_window_start=source_start,
        source_window_end=source_end,
        window_label=window_label,
        integrity=build_observation_integrity(df, meta),
    )


__all__ = [
    "build_observation_integrity",
    "build_state_snapshot",
]

"""
Reusable signal-quality profiling for ACM representation governance.

This module centralizes numeric-signal qualification so the same profiling
semantics can be reused by shadow representation logic and existing guardrails
without moving score authority.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from core.representation_contracts import SignalProfile, SignalProfileSummary
from core.time_normalizer import native_cadence_secs


def _numeric_signal_columns(df: pd.DataFrame) -> List[str]:
    if df is None or df.empty:
        return []
    cols: List[str] = []
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_bool_dtype(series):
            continue
        if pd.api.types.is_numeric_dtype(series):
            cols.append(str(col))
            continue
        coerced = pd.to_numeric(series, errors="coerce")
        if coerced.notna().any() or series.isna().all():
            cols.append(str(col))
    return cols


def _series_flatline_ratio(series: pd.Series, epsilon: float = 1e-12) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
    if values.size == 0:
        return 0.0
    if values.size == 1:
        return 1.0
    diffs = np.diff(values)
    return float(np.isclose(diffs, 0.0, atol=epsilon, rtol=0.0).mean())


def _effective_cadence_seconds(df: pd.DataFrame) -> Optional[float]:
    if df is None or df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return None
    cadence = native_cadence_secs(df.index)
    if not np.isfinite(cadence):
        return None
    return float(cadence)


def _reason_codes_for_signal(
    *,
    missing_ratio: float,
    low_variance: bool,
    flatline_ratio: float,
    valid_count: int,
    min_valid_fraction: float,
) -> tuple[str, ...]:
    reasons: List[str] = []
    valid_fraction = 0.0 if valid_count == 0 and missing_ratio >= 1.0 else 1.0 - missing_ratio

    if valid_count == 0:
        reasons.append("all_null")
    elif valid_fraction < min_valid_fraction:
        reasons.append("low_valid_fraction")

    if low_variance:
        reasons.append("low_variance")
    if valid_count > 1 and flatline_ratio >= 0.95:
        reasons.append("flatline_prone")

    return tuple(reasons)


def _monitorability_class(
    *,
    missing_ratio: float,
    low_variance: bool,
    valid_count: int,
    min_valid_fraction: float,
) -> str:
    if valid_count == 0 or missing_ratio >= 1.0:
        return "UNTRUSTED"

    valid_fraction = 1.0 - missing_ratio
    if valid_fraction < min_valid_fraction or low_variance:
        return "WEAK"

    return "MONITORABLE"


def profile_signal_frame(
    df: pd.DataFrame,
    *,
    low_variance_threshold: float = 1e-4,
    min_valid_fraction: float = 0.5,
) -> List[SignalProfile]:
    """Build per-signal quality profiles for a numeric DataFrame."""
    if df is None or df.empty:
        return []

    cadence = _effective_cadence_seconds(df)
    profiles: List[SignalProfile] = []

    for col in _numeric_signal_columns(df):
        series = pd.to_numeric(df[col], errors="coerce")
        valid_count = int(series.notna().sum())
        missing_ratio = float(series.isna().mean()) if len(series) else 0.0
        std = series.std()
        low_variance = bool(valid_count >= 2 and not pd.isna(std) and std < low_variance_threshold)
        flatline_ratio = _series_flatline_ratio(series)
        reason_codes = _reason_codes_for_signal(
            missing_ratio=missing_ratio,
            low_variance=low_variance,
            flatline_ratio=flatline_ratio,
            valid_count=valid_count,
            min_valid_fraction=min_valid_fraction,
        )
        profiles.append(
            SignalProfile(
                signal_name=col,
                missing_ratio=missing_ratio,
                flatline_ratio=flatline_ratio,
                effective_cadence_seconds=cadence,
                monitorability_class=_monitorability_class(
                    missing_ratio=missing_ratio,
                    low_variance=low_variance,
                    valid_count=valid_count,
                    min_valid_fraction=min_valid_fraction,
                ),
                reason_codes=reason_codes,
            )
        )

    return profiles


def summarize_signal_profiles(profiles: Sequence[SignalProfile]) -> SignalProfileSummary:
    """Collapse per-signal profiles into the current shadow summary contract."""
    if not profiles:
        return SignalProfileSummary(
            monitorable_signal_count=0,
            weak_signal_count=0,
            untrusted_signal_count=0,
            reason_codes=("no_numeric_signals",),
        )

    monitorable = 0
    weak = 0
    untrusted = 0
    aggregated_reasons: List[str] = []

    for profile in profiles:
        if profile.monitorability_class == "MONITORABLE":
            monitorable += 1
        elif profile.monitorability_class == "UNTRUSTED":
            untrusted += 1
        else:
            weak += 1
        aggregated_reasons.extend(profile.reason_codes)

    reason_codes = tuple(dict.fromkeys(["profiled_numeric_signals", *aggregated_reasons]))
    return SignalProfileSummary(
        monitorable_signal_count=monitorable,
        weak_signal_count=weak,
        untrusted_signal_count=untrusted,
        reason_codes=reason_codes,
    )


def build_signal_profile_summary(
    df: pd.DataFrame,
    *,
    low_variance_threshold: float = 1e-4,
    min_valid_fraction: float = 0.5,
) -> SignalProfileSummary:
    """Convenience wrapper to profile a frame and summarize it in one call."""
    return summarize_signal_profiles(
        profile_signal_frame(
            df,
            low_variance_threshold=low_variance_threshold,
            min_valid_fraction=min_valid_fraction,
        )
    )


def detect_low_variance_signals(
    df: pd.DataFrame,
    *,
    low_variance_threshold: float = 1e-4,
    columns: Optional[Iterable[str]] = None,
) -> List[str]:
    """
    Detect low-variance numeric signals using the current guardrail semantics.

    This intentionally matches the legacy behavior used in `run_data_guardrails`:
    numeric columns with `std < threshold` or `NaN` standard deviation are
    treated as low variance.
    """
    if df is None or df.empty:
        return []

    target_columns = list(columns) if columns is not None else _numeric_signal_columns(df)
    if not target_columns:
        return []

    stds = df[target_columns].apply(pd.to_numeric, errors="coerce").std()
    low_var = stds[stds < low_variance_threshold]
    return [str(col) for col in low_var.index.tolist()]


__all__ = [
    "build_signal_profile_summary",
    "detect_low_variance_signals",
    "profile_signal_frame",
    "summarize_signal_profiles",
]

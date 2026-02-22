"""
Pure DataFrame builder helpers extracted from OutputManager.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd


def build_data_quality_records(
    train_numeric: pd.DataFrame,
    score_numeric: pd.DataFrame,
    cfg: Dict[str, Any],
    low_var_threshold: float = 1e-4,
) -> List[Dict[str, Any]]:
    """Build one summary data-quality record for SQL persistence."""
    interp_method = str((cfg.get("data", {}) or {}).get("interp_method", "linear"))
    sampling_secs_raw = (cfg.get("data", {}) or {}).get("sampling_secs", None)
    try:
        sampling_secs = float(sampling_secs_raw) if sampling_secs_raw not in (None, "auto", "") else None
    except (ValueError, TypeError):
        sampling_secs = None

    common_cols: List[str] = []
    if hasattr(train_numeric, "columns") and hasattr(score_numeric, "columns"):
        common_cols = [c for c in train_numeric.columns if c in score_numeric.columns]
    if not common_cols:
        return []

    total_sensors = len(common_cols)
    tr_total_rows = len(train_numeric)
    sc_total_rows = len(score_numeric)

    low_var_count = 0
    flatline_count = 0
    all_null_train_count = 0
    all_null_score_count = 0
    tr_null_pcts: List[float] = []
    sc_null_pcts: List[float] = []

    for col in common_cols:
        tr_series = train_numeric[col]
        sc_series = score_numeric[col]
        tr_nulls = int(tr_series.isna().sum())
        sc_nulls = int(sc_series.isna().sum())

        tr_null_pct = (100.0 * tr_nulls / tr_total_rows) if tr_total_rows else 0.0
        sc_null_pct = (100.0 * sc_nulls / sc_total_rows) if sc_total_rows else 0.0
        tr_null_pcts.append(tr_null_pct)
        sc_null_pcts.append(sc_null_pct)

        tr_std = pd.to_numeric(tr_series, errors="coerce").std()
        if tr_total_rows > 0 and (pd.isna(tr_std) or tr_std < low_var_threshold):
            low_var_count += 1

        if tr_total_rows > 0 and tr_nulls == tr_total_rows:
            all_null_train_count += 1
        if sc_total_rows > 0 and sc_nulls == sc_total_rows:
            all_null_score_count += 1

        sc_std = pd.to_numeric(sc_series, errors="coerce").std()
        if sc_total_rows > 10 and (pd.isna(sc_std) or sc_std < low_var_threshold):
            flatline_count += 1

    avg_train_null_pct = float(np.mean(tr_null_pcts)) if tr_null_pcts else 0.0
    max_train_null_pct = float(np.max(tr_null_pcts)) if tr_null_pcts else 0.0
    avg_score_null_pct = float(np.mean(sc_null_pcts)) if sc_null_pcts else 0.0
    max_score_null_pct = float(np.max(sc_null_pcts)) if sc_null_pcts else 0.0

    tr_min_ts = pd.Timestamp(train_numeric.index.min()).strftime("%Y-%m-%d %H:%M:%S") if tr_total_rows > 0 else None
    tr_max_ts = pd.Timestamp(train_numeric.index.max()).strftime("%Y-%m-%d %H:%M:%S") if tr_total_rows > 0 else None
    sc_min_ts = pd.Timestamp(score_numeric.index.min()).strftime("%Y-%m-%d %H:%M:%S") if sc_total_rows > 0 else None
    sc_max_ts = pd.Timestamp(score_numeric.index.max()).strftime("%Y-%m-%d %H:%M:%S") if sc_total_rows > 0 else None

    note_bits: List[str] = []
    if low_var_count > 0:
        note_bits.append(f"low_var:{low_var_count}")
    if all_null_train_count > 0:
        note_bits.append(f"null_train:{all_null_train_count}")
    if all_null_score_count > 0:
        note_bits.append(f"null_score:{all_null_score_count}")
    if flatline_count > 0:
        note_bits.append(f"flatline:{flatline_count}")

    return [
        {
            "sensor": f"_SUMMARY_{total_sensors}_SENSORS",
            "train_count": tr_total_rows,
            "train_nulls": int(avg_train_null_pct * tr_total_rows / 100) if tr_total_rows else 0,
            "train_null_pct": avg_train_null_pct,
            "train_std": max_train_null_pct,
            "train_longest_gap": low_var_count,
            "train_flatline_span": all_null_train_count,
            "train_min_ts": tr_min_ts,
            "train_max_ts": tr_max_ts,
            "score_count": sc_total_rows,
            "score_nulls": int(avg_score_null_pct * sc_total_rows / 100) if sc_total_rows else 0,
            "score_null_pct": avg_score_null_pct,
            "score_std": max_score_null_pct,
            "score_longest_gap": flatline_count,
            "score_flatline_span": all_null_score_count,
            "score_min_ts": sc_min_ts,
            "score_max_ts": sc_max_ts,
            "interp_method": interp_method,
            "sampling_secs": sampling_secs,
            "notes": ",".join(note_bits) if note_bits else f"sensors:{total_sensors}",
        }
    ]

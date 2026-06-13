#!/usr/bin/env python3
"""
ACM data feed — incremental ingestion, raw cache, readiness gate.

The shared data layer between the batch runner (acm_run) and the always-on
service (acm_service). The historian is precious: per tick only rows NEWER
than the cache are pulled (one small delta query per asset), and a trailing
window of raw history is kept in one parquet file per asset. score_asset
always reads from the cache, never hammers the source.

No FastAPI here, no store writes — pure data functions, picklable for
ProcessPoolExecutor workers on Windows (spawn).
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import pyarrow.parquet as _pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_KINDS = ("csv", "table", "query")

# Readiness gate horizons — TIME-defined, like the alarm-rule horizons. A
# baseline needs enough elapsed time behind it for the interleaved
# calibration split and the 7-day per-head windows to mean anything.
MIN_TRAIN_DAYS = 14.0
STALE_AFTER_HOURS = 24.0


@dataclass
class SourceSpec:
    """Where one asset's raw data comes from."""
    asset_key: str
    source_kind: str            # csv | table | query
    source_ref: str             # file path, table name, or SQL query
    conn_ref: Optional[str] = None      # pyodbc connection string (table/query)
    timestamp_col: str = "time_stamp"
    status_col: Optional[str] = "status_type_id"

    def __post_init__(self) -> None:
        if self.source_kind not in SOURCE_KINDS:
            raise ValueError(f"source_kind must be one of {SOURCE_KINDS}, "
                             f"got '{self.source_kind}'")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CacheInfo:
    """State of one asset's raw cache after an update."""
    last_ts: Optional[pd.Timestamp]
    n_rows: int
    span_days: float
    pulled_rows: int


def load_increment(spec: SourceSpec, since: Optional[pd.Timestamp]) -> pd.DataFrame:
    """Pull rows newer than `since` from the source (everything when None)."""
    if spec.source_kind == "csv":
        df = pd.read_csv(spec.source_ref, sep=None, engine='python')
        if spec.timestamp_col not in df.columns:
            raise ValueError(f"timestamp column '{spec.timestamp_col}' not in "
                             f"{spec.source_ref} (columns: {list(df.columns)[:8]}...)")
        df[spec.timestamp_col] = pd.to_datetime(df[spec.timestamp_col])
        if since is not None:
            df = df[df[spec.timestamp_col] > since]
    else:
        import pyodbc
        if spec.source_kind == "table":
            sql = f"SELECT * FROM {spec.source_ref}"
            if since is not None:
                sql += f" WHERE {spec.timestamp_col} > ?"
        else:
            sql = f"SELECT * FROM ({spec.source_ref}) acm_src"
            if since is not None:
                sql += f" WHERE {spec.timestamp_col} > ?"
        con = pyodbc.connect(spec.conn_ref)
        try:
            df = pd.read_sql(sql, con, params=[since.to_pydatetime()] if since is not None else None)
        finally:
            con.close()
        if spec.timestamp_col not in df.columns:
            raise ValueError(f"timestamp column '{spec.timestamp_col}' not in source "
                             f"(columns: {list(df.columns)[:8]}...)")
        df[spec.timestamp_col] = pd.to_datetime(df[spec.timestamp_col])
    return df.sort_values(spec.timestamp_col).reset_index(drop=True)


def cache_path(cache_dir: Path | str, asset_key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", asset_key)
    return Path(cache_dir) / f"{safe}.parquet"


def _read_ts_column(path: Path, ts_col: str) -> Optional[pd.Series]:
    """Read only the timestamp column from a parquet file via column pruning.

    Parquet's columnar storage means we load a single column's byte range
    rather than all N sensor channels — O(rows) instead of O(rows × cols).
    Returns None when the file is missing or empty.
    """
    if not path.exists():
        return None
    try:
        tbl = _pq.read_table(str(path), columns=[ts_col])
        if len(tbl) == 0:
            return None
        return pd.to_datetime(tbl.column(ts_col).to_pandas())
    except Exception:
        return None


def update_cache(spec: SourceSpec, cache_dir: Path | str,
                 train_window_days: float = 180.0) -> CacheInfo:
    """Incremental pull into the asset's parquet cache.

    First call pulls everything; afterwards only rows newer than the cached
    last timestamp. The cache keeps a trailing `train_window_days` window —
    older rows fall off, so the file is bounded regardless of asset age.
    Atomic write (tmp + os.replace): a crash mid-write never corrupts.

    Performance: the timestamp column is read with column-pruning (PyArrow)
    to find `since` without loading all sensor channels.  When no new data
    arrives (most ticks for mature assets), the full parquet read and write
    are skipped entirely.
    """
    path = cache_path(cache_dir, spec.asset_key)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Fast path: read only the timestamp column — avoids loading 600+ sensor
    # columns just to find the maximum timestamp.
    ts_series = _read_ts_column(path, spec.timestamp_col)
    since = ts_series.max() if ts_series is not None else None

    inc = load_increment(spec, since)

    if not len(inc):
        # No new data — skip the expensive full read and atomic write.
        if ts_series is not None and len(ts_series):
            last_ts = since
            window_start = last_ts - pd.Timedelta(days=train_window_days)
            n_rows = int((ts_series >= window_start).sum())
            span_days = float((last_ts - ts_series.min()).total_seconds() / 86400.0)
            return CacheInfo(last_ts=last_ts, n_rows=n_rows,
                             span_days=span_days, pulled_rows=0)
        return CacheInfo(last_ts=None, n_rows=0, span_days=0.0, pulled_rows=0)

    # New data available — full read, merge, trim, write.
    cached = pd.read_parquet(path) if path.exists() else None
    df = pd.concat([cached, inc], ignore_index=True) if cached is not None else inc
    if not len(df):
        return CacheInfo(last_ts=None, n_rows=0, span_days=0.0, pulled_rows=0)
    df = df.drop_duplicates(subset=spec.timestamp_col, keep="last") \
           .sort_values(spec.timestamp_col).reset_index(drop=True)
    last_ts = df[spec.timestamp_col].iloc[-1]
    df = df[df[spec.timestamp_col] >= last_ts - pd.Timedelta(days=train_window_days)]
    df = df.reset_index(drop=True)

    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)
    span_days = float((last_ts - df[spec.timestamp_col].iloc[0]).total_seconds() / 86400.0)
    return CacheInfo(last_ts=last_ts, n_rows=len(df), span_days=span_days,
                     pulled_rows=len(inc))


def readiness(span_days: float, last_ts: Optional[pd.Timestamp], now: pd.Timestamp,
              min_train_days: float = MIN_TRAIN_DAYS,
              stale_after_hours: float = STALE_AFTER_HOURS) -> str:
    """Time-aware gate: is this asset's history fit to score?

    MATURING  less than min_train_days of history — the baseline is not
              trustworthy yet; scoring would self-calibrate on noise.
    STALE     the source stopped delivering — last sample older than
              stale_after_hours; scoring a dead feed is meaningless.
    READY     score it.
    """
    if last_ts is None or span_days < min_train_days:
        return "MATURING"
    if (now - last_ts).total_seconds() > stale_after_hours * 3600.0:
        return "STALE"
    return "READY"


def frame_sensors(df: pd.DataFrame, timestamp_col: str,
                  status_col: Optional[str]) -> tuple[pd.DataFrame, Optional[np.ndarray]]:
    """Raw frame -> (numeric sensor frame with DatetimeIndex, status array)."""
    status_col = status_col if status_col and status_col in df.columns else None
    drop = [timestamp_col] + ([status_col] if status_col else [])
    out = df.drop(columns=drop).apply(pd.to_numeric, errors="coerce")
    out.index = pd.DatetimeIndex(df[timestamp_col], name="EntryDateTime")
    out = out.replace([np.inf, -np.inf], np.nan).dropna(axis=1, how="all")
    status = df[status_col].to_numpy() if status_col else None
    return out, status


def score_cached(cache_file: str, spec_dict: dict, score_days: float) -> Dict:
    """ProcessPool worker: score one asset from its cache file.

    Plain-string/dict arguments and a module-level function so Windows spawn
    can pickle it. Returns {"asset_key", "result"} or {"asset_key", "error"}.
    """
    spec = SourceSpec(**spec_dict)
    try:
        from core.pipeline import score_asset
        df = pd.read_parquet(cache_file)
        df[spec.timestamp_col] = pd.to_datetime(df[spec.timestamp_col])
        ts = df[spec.timestamp_col]
        # Adaptive split: the score window never takes more than a third of
        # the history. A fixed 30-day window on a young asset starved the
        # train side until the calibration holdout fell under the alarm
        # rules' 500-sample minimum — silently disarming the rate and
        # per-head rules, the ones that catch single-channel faults.
        span_days = (ts.iloc[-1] - ts.iloc[0]).total_seconds() / 86400.0
        score_eff = min(score_days, max(1.0, span_days / 3.0))
        cut = ts.iloc[-1] - pd.Timedelta(days=score_eff)
        train_df, score_df = df[ts < cut], df[ts >= cut]
        if not len(train_df) or not len(score_df):
            return {"asset_key": spec.asset_key,
                    "error": f"degenerate split (train={len(train_df)}, score={len(score_df)})"}
        train_raw, train_status = frame_sensors(train_df, spec.timestamp_col, spec.status_col)
        score_raw, score_status = frame_sensors(score_df, spec.timestamp_col, spec.status_col)
        res = score_asset(train_raw=train_raw, score_raw=score_raw,
                          train_status=train_status, score_status=score_status)
        return {"asset_key": spec.asset_key, "result": res}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"asset_key": spec.asset_key, "error": f"{type(e).__name__}: {e}"[:300]}

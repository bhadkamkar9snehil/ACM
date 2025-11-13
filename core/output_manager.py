"""
Unified Output Manager for ACM
==============================

Consolidates all scattered output generation into a single, efficient system:
- Batched file writes with intelligent buffering
- Smart SQL/file dual-write coordination with caching
- Single point of control for all CSV, JSON, and model outputs
- Performance optimizations: vectorized operations, reduced I/O
- Unified error handling and logging

This replaces scattered to_csv() calls throughout the codebase and provides
consistent behavior for all output operations.
"""

from __future__ import annotations

import json
import time
import math
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Union, Tuple, TypeVar, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np
from datetime import datetime, timezone

from utils.logger import Console

# whitelist of SQL tables we will write to (defined early so class methods can use it)
ALLOWED_TABLES = {
    'ACM_Scores_Wide','ACM_Episodes',
    'ACM_HealthTimeline','ACM_RegimeTimeline',
    'ACM_ContributionCurrent','ACM_ContributionTimeline',
    'ACM_DriftSeries','ACM_ThresholdCrossings',
    'ACM_AlertAge','ACM_SensorRanking','ACM_RegimeOccupancy',
    'ACM_HealthHistogram','ACM_RegimeStability',
    'ACM_DefectSummary','ACM_DefectTimeline','ACM_SensorDefects',
    'ACM_HealthZoneByPeriod','ACM_SensorAnomalyByPeriod',
    'ACM_DetectorCorrelation','ACM_CalibrationSummary',
    'ACM_RegimeTransitions','ACM_RegimeDwellStats',
    'ACM_DriftEvents','ACM_CulpritHistory','ACM_EpisodeMetrics',
    'ACM_DataQuality','ACM_Scores_Long','ACM_Drift_TS',
    'ACM_Anomaly_Events','ACM_Regime_Episodes',
    'ACM_PCA_Models','ACM_PCA_Loadings','ACM_PCA_Metrics',
    'ACM_Run_Stats', 'ACM_SinceWhen',
    'ACM_SensorHotspots','ACM_SensorHotspotTimeline',
}

def _table_exists(cursor_factory: Callable[[], Any], name: str) -> bool:
    cur = None
    try:
        cur = cursor_factory()
        cur.execute(f"SELECT TOP 0 * FROM dbo.[{name}]")
        return True
    except Exception:
        return False
    finally:
        try:
            if cur is not None:
                cur.close()
        except Exception:
            pass

def _get_table_columns(cursor_factory: Callable[[], Any], name: str) -> List[str]:
    """Return the list of column names for a table by probing TOP 0."""
    cur = cursor_factory()
    try:
        cur.execute(f"SELECT TOP 0 * FROM dbo.[{name}]")
        return [d[0] for d in (cur.description or [])]
    finally:
        try:
            cur.close()
        except Exception:
            pass

def _get_insertable_columns(cursor_factory: Callable[[], Any], name: str) -> List[str]:
    """Return columns excluding identity columns for safe INSERT.
    Uses sys.columns joined via OBJECT_ID('schema.table') without square brackets.
    """
    cur = cursor_factory()
    try:
        # OBJECT_ID expects a schema-qualified name without brackets
        cur.execute(
            "SELECT c.name, c.is_identity FROM sys.columns c WHERE c.object_id = OBJECT_ID(?)",
            (f"dbo.{name}",)
        )
        rows = cur.fetchall() or []
        return [r[0] for r in rows if not getattr(r, 'is_identity', r[1])]
    finally:
        try:
            cur.close()
        except Exception:
            pass

# constants for analytics & guardrails
class AnalyticsConstants:
    DRIFT_EVENT_THRESHOLD = 3.0
    DEFAULT_CLIP_Z = 30.0
    TARGET_SAMPLING_POINTS = 500
    HEALTH_ALERT_THRESHOLD = 70.0
    HEALTH_WATCH_THRESHOLD = 85.0

# CHART-12: Centralized severity color palette
SEVERITY_COLORS = {
    "CRITICAL": "#dc2626",  # Red - immediate action required
    "HIGH": "#f97316",      # Orange - urgent attention
    "MEDIUM": "#f59e0b",    # Amber - monitor closely
    "LOW": "#10b981",       # Green - informational
    "INFO": "#10b981",      # Alias for LOW
    "WARNING": "#f59e0b",   # Alias for MEDIUM
}

# Enhanced config getter with typing
T = TypeVar("T")

def _cfg_get(cfg: Dict[str, Any], path: str, default: T) -> T:
    """Get config value by dot path with type preservation."""
    keys = path.split('.')
    current: Any = cfg
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current  # type: ignore[return-value]

# Safe datetime cast helpers - local time policy
def _to_naive(ts) -> Optional[pd.Timestamp]:
    """Convert to timezone-naive local timestamp or None."""
    if ts is None or (isinstance(ts, float) and pd.isna(ts)):
        return None
    try:
        result = pd.to_datetime(ts, errors='coerce')
        # Strip timezone info if present
        if hasattr(result, 'tz') and result.tz is not None:
            return result.tz_localize(None)
        return result
    except Exception:
        return None

def _to_naive_series(idx_or_series: Union[pd.Index, pd.Series]) -> pd.Series:
    """Return a Series of tz-naive local timestamps from an index/series.
    Always returns a Series indexed by the original labels (usually timestamps).
    """
    s = pd.to_datetime(idx_or_series, errors='coerce')
    if isinstance(s, pd.Series):
        # Strip timezone if present
        try:
            if hasattr(s.dt, 'tz') and s.dt.tz is not None:
                s2 = s.dt.tz_localize(None)
            else:
                s2 = s
        except Exception:
            s2 = s
        return s2
    else:
        # DatetimeIndex → tz-naive and wrap as Series
        try:
            if hasattr(s, 'tz') and s.tz is not None:
                idx = s.tz_localize(None)
            else:
                idx = s
        except Exception:
            idx = s
        return pd.Series(idx, index=idx)

# ==================== DATA LOADING SUPPORT ====================
# Progress indicator for long operations
class Heartbeat:
    def __init__(self, label: str, next_hint: Optional[str] = None, eta_hint: Optional[float] = None, interval: float = 2.0):
        self.label, self.next_hint, self.eta_hint, self.interval = label, next_hint, eta_hint, interval
        self._stop = threading.Event()
        self._t0 = time.perf_counter()
        self._thr = threading.Thread(target=self._run, daemon=True)

    def start(self):
        print(f"[..] {self.label} ...")
        self._thr.start()
        return self

    def stop(self):
        self._stop.set()
        self._thr.join(timeout=0.1)
        took = time.perf_counter() - self._t0
        print(f"[OK] {self.label} done in {took:.2f}s")

    def _run(self):
        dots = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        i = 0
        while not self._stop.wait(self.interval):
            spent = time.perf_counter() - self._t0
            eta = f" | ~{max(0.0, self.eta_hint - spent):0.0f}s left" if self.eta_hint else ""
            nxt = f" | next: {self.next_hint}" if self.next_hint else ""
            print(f"[..] {dots[i % len(dots)]} {self.label}{eta}{nxt}")
            i += 1

@dataclass
class DataMeta:
    """Metadata about loaded dataset."""
    timestamp_col: str
    cadence_ok: bool
    kept_cols: List[str]
    dropped_cols: List[str]
    start_ts: pd.Timestamp
    end_ts: pd.Timestamp
    n_rows: int
    sampling_seconds: float
    tz_stripped: int = 0
    future_rows_dropped: int = 0
    dup_timestamps_removed: int = 0

# (duplicate removed; use the typed _cfg_get defined above)

def _parse_ts_index(df: pd.DataFrame, ts_col: str) -> pd.DataFrame:
    """Parse timestamp column and set as index."""
    if ts_col not in df.columns:
        raise ValueError(f"Timestamp column '{ts_col}' not found")
    df = df.copy()
    df[ts_col] = pd.to_datetime(df[ts_col], errors='coerce')
    df = df.set_index(ts_col).sort_index()
    return df


def _coerce_local_and_filter_future(df: pd.DataFrame, label: str, now_cutoff: pd.Timestamp) -> Tuple[pd.DataFrame, int, int]:
    """Convert timestamp index to naive local time and drop future rows.

    Returns the sanitized DataFrame along with counts for timezone stripping and
    future-dated rows that were removed.
    """
    tz_stripped = 0
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors="coerce")
    else:
        try:
            if df.index.tz is not None:
                tz_stripped = len(df)
                df.index = df.index.tz_localize(None)
        except Exception:
            df.index = pd.to_datetime(df.index, errors="coerce")

    # Drop NaT entries created during coercion
    before_drop = len(df)
    df = df[~df.index.isna()]
    if before_drop and len(df) != before_drop:
        Console.warn(f"[DATA] Dropped {before_drop - len(df)} rows with invalid timestamps from {label}")

    future_mask = df.index > now_cutoff
    future_rows = int(future_mask.sum())
    if future_rows:
        Console.warn(
            f"[DATA] Dropping {future_rows} future timestamp row(s) from {label} (cutoff={now_cutoff:%Y-%m-%d %H:%M:%S})"
        )
        df = df[~future_mask]

    return df, tz_stripped, future_rows

def _infer_numeric_cols(df: pd.DataFrame) -> List[str]:
    """Get list of numeric columns."""
    return df.select_dtypes(include=[np.number]).columns.tolist()

def _native_cadence_secs(idx: pd.DatetimeIndex) -> float:
    """Estimate native cadence in seconds."""
    if len(idx) < 2:
        return float('inf')
    diffs = idx.to_series().diff().dropna()
    return diffs.median().total_seconds()

def _check_cadence(idx: pd.DatetimeIndex, sampling_secs: Optional[int], jitter_ratio: float = 0.05) -> bool:
    """Check if timestamps have regular cadence."""
    if sampling_secs is None or len(idx) < 2:
        return True
    diffs = idx.to_series().diff().dropna()
    expected = pd.Timedelta(seconds=sampling_secs)
    tolerance = expected * jitter_ratio
    return ((diffs - expected).abs() <= tolerance).mean() >= 0.9

def _resample(df: pd.DataFrame, sampling_secs: int, interp_method: str = "linear", strict: bool = False, max_gap_secs: int = 300, max_fill_ratio: float = 0.2) -> pd.DataFrame:
    """Resample DataFrame to regular intervals."""
    if df.empty:
        return df
    if df.index.min() == df.index.max():
        return df  # single-point; nothing to resample
    freq = f"{sampling_secs}s"
    start = df.index.min()
    end = df.index.max()
    regular_idx = pd.date_range(start=start, end=end, freq=freq)
    df_resampled = df.reindex(regular_idx)
    if interp_method != "none":
        max_gap_periods = max_gap_secs // sampling_secs
        df_resampled = df_resampled.interpolate(method=interp_method, limit=max_gap_periods, limit_direction='both')
    if strict:
        fill_ratio = df_resampled.isnull().sum().sum() / (len(df_resampled) * len(df_resampled.columns))
        if fill_ratio > max_fill_ratio:
            raise ValueError(f"Too much missing data after resample: {fill_ratio:.1%} > {max_fill_ratio:.1%}")
    return df_resampled

def _read_csv_with_peek(path: Union[str, Path], ts_col_hint: Optional[str], engine: Optional[str] = None) -> Tuple[pd.DataFrame, str]:
    """Read CSV and auto-detect timestamp column."""
    path = Path(path)
    try:
        df = pd.read_csv(path, engine=engine)
    except Exception as e:
        raise ValueError(f"Failed to read CSV {path}: {e}")
    if df.empty:
        raise ValueError(f"Empty CSV: {path}")
    
    # Auto-detect timestamp column if not provided
    ts_col = ts_col_hint
    if not ts_col:
        candidates = ['timestamp', 'time', 'datetime', 'date']
        for candidate in candidates:
            if candidate in df.columns:
                ts_col = candidate
                break
        if not ts_col:
            for col in df.columns:
                if df[col].dtype == 'object':
                    try:
                        pd.to_datetime(df[col].iloc[:10], errors='raise')
                        ts_col = col
                        break
                    except:
                        continue
    if not ts_col:
        raise ValueError(f"Could not find timestamp column in {path}")
    return df, ts_col


def _health_index(fused_z):
    """
    Calculate health index from fused z-score.
    
    Health = 100 / (1 + z^2)
    
    Higher values indicate healthier state (closer to 0 z-score).
    Lower values indicate degradation (higher absolute z-score).
    
    Args:
        fused_z: Fused z-score (scalar, array, or Series)
    
    Returns:
        Health index 0-100 (same type as input)
    """
    return 100.0 / (1.0 + fused_z ** 2)


# ==================== MAIN OUTPUT MANAGER CLASS ====================


@dataclass
@dataclass
class OutputBatch:
    """Represents a batch of outputs to be written together."""
    csv_files: Dict[Path, pd.DataFrame] = field(default_factory=dict)
    json_files: Dict[Path, Dict[str, Any]] = field(default_factory=dict)
    sql_operations: List[Tuple[str, pd.DataFrame, Dict[str, Any]]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # OUT-18: Batch tracking for flush triggers
    created_at: float = field(default_factory=time.time)
    total_rows: int = 0


class OutputManager:
    """
    Unified output manager that consolidates all scattered output generation.
    
    Features:
    - Batched writes for improved I/O performance
    - Smart SQL health checking with caching
    - Automatic file/SQL dual-write coordination
    - Thread-safe operations with connection pooling
    - Intelligent error handling and fallback strategies
    """
    
    def __init__(self, 
                 sql_client=None, 
                 run_id: Optional[str] = None,
                 equip_id: Optional[int] = None,
                 batch_size: int = 5000,
                 enable_batching: bool = True,
                 sql_health_cache_seconds: float = 60.0,
                 max_io_workers: int = 8,
                 base_output_dir: Optional[Union[str, Path]] = None,
                 batch_flush_rows: int = 1000,
                 batch_flush_seconds: float = 30.0,
                 max_in_flight_futures: int = 50):
        self.sql_client = sql_client
        self.run_id = run_id
        self.equip_id = equip_id
        self.batch_size = batch_size
        self._batched_transaction_active = False
        self.enable_batching = enable_batching
        self.max_io_workers = max_io_workers
        self.base_output_dir = Path(base_output_dir).resolve() if base_output_dir else None
        
        # OUT-18: Batch flush triggers and backpressure
        self.batch_flush_rows = batch_flush_rows  # Flush after N rows
        self.batch_flush_seconds = batch_flush_seconds  # Flush after N seconds
        self.max_in_flight_futures = max_in_flight_futures  # Max concurrent operations

        self.stats = {
            'files_written': 0,
            'sql_writes': 0,
            'total_rows': 0,
            'sql_health_checks': 0,
            'sql_failures': 0,
            'write_time': 0.0
        }

        self._sql_health_cache: Tuple[float, bool] = (0.0, False)
        self._sql_health_cache_duration = sql_health_cache_seconds

        self._current_batch = OutputBatch()
        self._batch_lock = threading.Lock()
        
        # OUT-18: Track in-flight operations for backpressure
        self._in_flight_futures: List[Any] = []  # List of active futures
        self._futures_lock = threading.Lock()

        # lightweight caches for table probes
        self._table_exists_cache: Dict[str, bool] = {}
        self._table_columns_cache: Dict[str, set] = {}
        self._table_insertable_cache: Dict[str, set] = {}

        # Minimal per-table NOT NULL requirements with safe defaults
        # 'ts' indicates we should use a sentinel timestamp (1900-01-01 00:00:00)
        self._sql_required_defaults: Dict[str, Dict[str, Any]] = {
            'ACM_DefectTimeline': {
                'Timestamp': 'ts', 'FusedZ': 0.0, 'HealthIndex': 0.0, 'HealthZone': 'UNKNOWN',
                'EventType': 'ZONE_CHANGE', 'FromZone': 'START', 'ToZone': 'GOOD'
            },
            'ACM_HealthTimeline': {
                'Timestamp': 'ts', 'HealthIndex': 0.0, 'HealthZone': 'GOOD', 'FusedZ': 0.0
            },
            'ACM_ThresholdCrossings': {
                'Timestamp': 'ts', 'DetectorType': 'fused', 'ZScore': 0.0, 'Threshold': 0.0, 'Direction': 'up'
            },
            'ACM_HealthZoneByPeriod': {
                'PeriodStart': 'ts', 'PeriodType': 'DAY', 'HealthZone': 'GOOD', 'ZonePct': 0.0,
                'ZoneCount': 0, 'TotalPoints': 0
            },
            'ACM_SensorAnomalyByPeriod': {
                'PeriodStart': 'ts', 'PeriodType': 'DAY', 'DetectorType': 'UNKNOWN', 'AnomalyRatePct': 0.0
            },
            'ACM_ContributionCurrent': {
                'DetectorType': 'UNKNOWN', 'ContributionPct': 0.0, 'ZScore': 0.0
            },
            'ACM_ContributionTimeline': {
                'Timestamp': 'ts', 'DetectorType': 'UNKNOWN', 'ContributionPct': 0.0
            },
            'ACM_SensorDefects': {
                'DetectorType': 'UNKNOWN', 'Severity': 'LOW', 'ViolationCount': 0, 'ViolationPct': 0.0,
                'MaxZ': 0.0, 'AvgZ': 0.0, 'CurrentZ': 0.0, 'ActiveDefect': 0
            },
            'ACM_DriftSeries': {
                'Timestamp': 'ts', 'DriftValue': 0.0
            },
            'ACM_DriftEvents': {
                'Timestamp': 'ts', 'SegmentStart': 'ts', 'SegmentEnd': 'ts', 'Value': 0.0
            },
            'ACM_RegimeTransitions': {
                'FromLabel': -1, 'ToLabel': -1, 'Count': 0, 'Prob': 0.0
            },
            'ACM_RegimeDwellStats': {
                'RegimeLabel': -1, 'Runs': 0, 'MeanSeconds': 0.0, 'MedianSeconds': 0.0, 'MinSeconds': 0.0, 'MaxSeconds': 0.0
            },
            'ACM_RegimeTimeline': {
                'Timestamp': 'ts', 'RegimeLabel': -1, 'RegimeState': 'unknown'
            },
            'ACM_RegimeOccupancy': {
                'RegimeLabel': -1, 'RecordCount': 0, 'Percentage': 0.0
            },
            'ACM_HealthHistogram': {
                'HealthBin': '0-10', 'RecordCount': 0, 'Percentage': 0.0
            },
            'ACM_CalibrationSummary': {
                'DetectorType': 'UNKNOWN', 'ClipZ': AnalyticsConstants.DEFAULT_CLIP_Z
            },
            'ACM_CulpritHistory': {
                'StartTimestamp': 'ts', 'EndTimestamp': 'ts', 'DurationHours': 0.0, 'Culprits': 'unknown'
            },
            'ACM_EpisodeMetrics': {
                'TotalEpisodes': 0, 'TotalDurationHours': 0.0, 'AvgDurationHours': 0.0, 'MedianDurationHours': 0.0,
                'MaxDurationHours': 0.0, 'MinDurationHours': 0.0, 'RatePerDay': 0.0, 'MeanInterarrivalHours': 0.0
            },
            'ACM_SensorHotspots': {
                'SensorName': 'UNKNOWN', 'MaxTimestamp': 'ts', 'LatestTimestamp': 'ts',
                'MaxAbsZ': 0.0, 'MaxSignedZ': 0.0, 'LatestAbsZ': 0.0, 'LatestSignedZ': 0.0,
                'ValueAtPeak': 0.0, 'LatestValue': 0.0, 'TrainMean': 0.0, 'TrainStd': 0.0,
                'AboveWarnCount': 0, 'AboveAlertCount': 0
            },
            'ACM_SensorHotspotTimeline': {
                'Timestamp': 'ts', 'SensorName': 'UNKNOWN', 'Rank': 0, 'AbsZ': 0.0,
                'SignedZ': 0.0, 'Value': 0.0, 'Level': 'GOOD'
            },
            'ACM_SinceWhen': {
                'AlertZone': 'GOOD', 'DurationHours': 0.0, 'StartTimestamp': 'ts', 'RecordCount': 0
            }
            ,
            'ACM_AlertAge': {
                'AlertZone': 'GOOD', 'DurationHours': 0.0, 'StartTimestamp': 'ts', 'RecordCount': 0
            }
        }

        Console.info(f"[OUTPUT] Manager initialized (batch_size={batch_size}, batching={'ON' if enable_batching else 'OFF'}, sql_cache={sql_health_cache_seconds}s, io_workers={max_io_workers}, flush={batch_flush_rows} rows/{batch_flush_seconds}s, max_futures={max_in_flight_futures})")
    
    @contextmanager
    def batched_transaction(self):
        """
        Context manager for writing multiple tables in a single transaction.
        Improves performance by reducing commit overhead when writing many tables.
        
        Usage:
            with output_mgr.batched_transaction():
                output_mgr.write_table("Table1", df1, "sql")
                output_mgr.write_table("Table2", df2, "sql")
                # Single commit after all writes
        """
        if self._batched_transaction_active:
            # Nested transaction - just pass through
            yield
            return
        
        if self.sql_client is None:
            # No SQL client - just pass through
            yield
            return
        
        self._batched_transaction_active = True
        start_time = time.time()
        
        try:
            Console.info("[OUTPUT] Starting batched transaction")
            yield
            # Commit at end of transaction
            try:
                if hasattr(self.sql_client, "commit"):
                    self.sql_client.commit()
                elif hasattr(self.sql_client, "conn") and hasattr(self.sql_client.conn, "commit"):
                    if not getattr(self.sql_client.conn, "autocommit", True):
                        self.sql_client.conn.commit()
                elapsed = time.time() - start_time
                Console.info(f"[OUTPUT] Batched transaction committed ({elapsed:.2f}s)")
            except Exception as e:
                Console.error(f"[OUTPUT] Batched transaction commit failed: {e}")
                raise
        except Exception as e:
            # Rollback on error
            try:
                if hasattr(self.sql_client, "rollback"):
                    self.sql_client.rollback()
                elif hasattr(self.sql_client, "conn") and hasattr(self.sql_client.conn, "rollback"):
                    self.sql_client.conn.rollback()
                Console.error(f"[OUTPUT] Batched transaction rolled back: {e}")
            except:
                pass
            raise
        finally:
            self._batched_transaction_active = False
    
    # ==================== DATA LOADING METHOD ====================
    
    def load_data(self, cfg: Dict[str, Any], start_utc: Optional[pd.Timestamp] = None, end_utc: Optional[pd.Timestamp] = None):
        """
        Load training and scoring data from CSV files.
        
        Consolidates data loading into OutputManager since it's part of the I/O pipeline.
        """
        # Use consistent config access with fallback
        data_cfg = cfg.get("data", {})
        train_path = data_cfg.get("train_csv")
        score_path = data_cfg.get("score_csv")
        
        # Cold-start mode: If no training data, use first N% of score data for training
        cold_start_mode = False
        if not train_path and score_path:
            Console.info("[DATA] Cold-start mode: No training data provided, will split score data")
            cold_start_mode = True
        elif not train_path or not score_path:
            raise ValueError("[DATA] Please set data.train_csv and data.score_csv in config.")

        _sampling = data_cfg.get("sampling_secs", 1)
        if _sampling in (None, "auto", "null"):
            sampling_secs: Optional[int] = None
        else:
            sampling_secs = int(_sampling)

        allow_resample = bool(_cfg_get(data_cfg, "allow_resample", True))
        resample_strict = bool(_cfg_get(data_cfg, "resample_strict", False))
        interp_method = str(_cfg_get(data_cfg, "interp_method", "linear"))
        ts_col_cfg = _cfg_get(data_cfg, "timestamp_col", None)
        io_engine = _cfg_get(data_cfg, "io_engine", None)
        # Allow override in data.max_fill_ratio (preferred), fallback to runtime.max_fill_ratio
        max_fill_ratio = float(_cfg_get(data_cfg, "max_fill_ratio", _cfg_get(cfg, "runtime.max_fill_ratio", 0.20)))
        
        # COLD-02: Configurable cold-start split ratio (default 0.6 = 60% train, 40% score)
        cold_start_split_ratio = float(_cfg_get(data_cfg, "cold_start_split_ratio", 0.6))
        if not (0.1 <= cold_start_split_ratio <= 0.9):
            Console.warn(f"[DATA] Invalid cold_start_split_ratio={cold_start_split_ratio}, using default 0.6")
            cold_start_split_ratio = 0.6
        
        # COLD-03: Minimum samples validation (default 500)
        min_train_samples = int(_cfg_get(data_cfg, "min_train_samples", 500))

        # Read CSVs (with heartbeat)
        if cold_start_mode:
            hb = Heartbeat("Reading CSV (cold-start: will split data)", next_hint="parse timestamps", eta_hint=10).start()
            score_raw, ts_score = _read_csv_with_peek(score_path, ts_col_cfg, engine=io_engine)
            
            # COLD-03: Validate sufficient data for cold-start
            if len(score_raw) < 10:
                raise ValueError(f"[DATA] Cold-start requires at least 10 rows, got {len(score_raw)}")
            
            ts_col = ts_col_cfg or ts_score
            split_idx = int(len(score_raw) * cold_start_split_ratio)
            train_raw = score_raw.iloc[:split_idx].copy()
            score_raw = score_raw.iloc[split_idx:].copy()
            ts_train = ts_score
            
            # COLD-03: Warn if training samples below recommended minimum
            if len(train_raw) < min_train_samples:
                Console.warn(f"[DATA] Cold-start training data ({len(train_raw)} rows) is below recommended minimum ({min_train_samples} rows)")
                Console.warn(f"[DATA] Model quality may be degraded. Consider: more data, higher split_ratio (current: {cold_start_split_ratio:.2f})")
            
            Console.info(f"[DATA] Cold-start split ({cold_start_split_ratio:.1%}): {len(train_raw)} train rows, {len(score_raw)} score rows")
            hb.stop()
        else:
            hb = Heartbeat("Reading CSVs (train & score)", next_hint="parse timestamps", eta_hint=10).start()
            train_raw, ts_train = _read_csv_with_peek(train_path, ts_col_cfg, engine=io_engine)
            score_raw, ts_score = _read_csv_with_peek(score_path, ts_col_cfg, engine=io_engine)
            hb.stop()
            ts_col = ts_col_cfg or ts_train or ts_score

        # Apply window constraints if provided (for SQL mode)
        if start_utc:
            train_raw = train_raw[pd.to_datetime(train_raw[ts_col], errors='coerce') >= start_utc]
        if end_utc:
            score_raw = score_raw[pd.to_datetime(score_raw[ts_col], errors='coerce') < end_utc]

        # Parse timestamps / index
        hb = Heartbeat("Parsing timestamps & indexing", next_hint="numeric pruning", eta_hint=8).start()
        train = _parse_ts_index(train_raw, ts_col)
        score = _parse_ts_index(score_raw, ts_col)
        hb.stop()

        now_cutoff = pd.Timestamp.now()
        train, tz_stripped_train, future_train = _coerce_local_and_filter_future(train, "TRAIN", now_cutoff)
        score, tz_stripped_score, future_score = _coerce_local_and_filter_future(score, "SCORE", now_cutoff)
        tz_stripped_total = tz_stripped_train + tz_stripped_score
        future_rows_total = future_train + future_score
        
        # COLD-03: Validate training sample count (both cold-start and normal modes)
        if len(train) < min_train_samples:
            if cold_start_mode:
                # Already warned during split
                pass
            else:
                Console.warn(f"[DATA] Training data ({len(train)} rows) is below recommended minimum ({min_train_samples} rows)")
                Console.warn(f"[DATA] Model quality may be degraded. Consider providing more training data.")

        # Keep numeric only (same set across train/score)
        hb = Heartbeat("Selecting numeric sensor columns", next_hint="cadence check", eta_hint=4).start()
        train_num = _infer_numeric_cols(train)
        score_num = _infer_numeric_cols(score)
        kept = sorted(list(set(train_num).intersection(score_num)))
        dropped = [c for c in train.columns if c not in kept]
        train = train[kept]
        score = score[kept]
        train = train.astype(np.float32)
        score = score.astype(np.float32)
        hb.stop()

        # Cadence check + guardrails
        hb = Heartbeat("Cadence check / resample / fill small gaps", next_hint="finalize", eta_hint=15).start()
        cad_ok_train = _check_cadence(train.index, sampling_secs)
        cad_ok_score = _check_cadence(score.index, sampling_secs)
        cadence_ok = bool(cad_ok_train and cad_ok_score)

        native_train = _native_cadence_secs(train.index)
        if sampling_secs and math.isfinite(native_train) and sampling_secs < native_train:
            Console.warn(f"[WARN] Requested resample ({sampling_secs}s) < native cadence ({native_train:.1f}s) — skipping to avoid upsample.")
            sampling_secs = None

        if sampling_secs is not None:
            base_secs = float(sampling_secs)
        else:
            base_secs = native_train if math.isfinite(native_train) else 1.0
        max_gap_secs = int(_cfg_get(data_cfg, "max_gap_secs", base_secs * 3))

        explode_guard_factor = float(_cfg_get(data_cfg, "explode_guard_factor", 2.0))
        will_resample = allow_resample and (not cadence_ok) and (sampling_secs is not None)
        if will_resample:
            span_secs = (train.index[-1].value - train.index[0].value) / 1e9 if len(train.index) else 0.0
            approx_rows = int(span_secs / max(1.0, float(sampling_secs))) + 1
            if len(train) and approx_rows > explode_guard_factor * len(train):
                Console.warn(f"[WARN] Resample would expand rows from {len(train)} -> ~{approx_rows} (>x{explode_guard_factor:.1f}). Skipping resample.")
                will_resample = False

        if will_resample:
            train = _resample(train, int(sampling_secs), interp_method, resample_strict, max_gap_secs, max_fill_ratio)
            score = _resample(score, int(sampling_secs), interp_method, resample_strict, max_gap_secs, max_fill_ratio)
            train = train.astype(np.float32)
            score = score.astype(np.float32)
            cadence_ok = True
        hb.stop()

        meta = DataMeta(
            timestamp_col=ts_col,
            cadence_ok=cadence_ok,
            kept_cols=kept,
            dropped_cols=dropped,
            start_ts=train.index.min() if len(train) else pd.Timestamp.now(),
            end_ts=score.index.max() if len(score) else pd.Timestamp.now(),
            n_rows=len(train) + len(score),
            sampling_seconds=sampling_secs or native_train,
            tz_stripped=tz_stripped_total,
            future_rows_dropped=future_rows_total,
            dup_timestamps_removed=0
        )
        return train, score, meta
    
    def _check_sql_health(self) -> bool:
        """Check SQL availability with caching for performance."""
        if self.sql_client is None:
            return False
        
        now = time.time()
        last_check, last_result = self._sql_health_cache
        
        # Use cached result if fresh
        if now - last_check < self._sql_health_cache_duration:
            return last_result
        
        # Perform health check
        try:
            cur = self.sql_client.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            self._sql_health_cache = (now, True)
            self.stats['sql_health_checks'] += 1
            return True
        except Exception as e:
            self._sql_health_cache = (now, False)
            self.stats['sql_health_checks'] += 1
            self.stats['sql_failures'] += 1
            Console.error(f"[OUTPUT] SQL health check failed: {e}")
            return False
        finally:
            try:
                if 'cur' in locals():
                    cur.close()
            except Exception:
                pass
    
    def _prepare_dataframe_for_sql(self, df: pd.DataFrame, non_numeric_cols: set = None) -> pd.DataFrame:
        """Prepare DataFrame for SQL insertion with proper type coercion."""
        if df.empty:
            return df
            
        out = df.copy()
        non_numeric_cols = non_numeric_cols or set()

        # Timestamps → UTC naive
        for col in out.columns:
            if pd.api.types.is_datetime64_any_dtype(out[col]):
                out[col] = pd.to_datetime(out[col]).dt.tz_localize(None)

        # Count infs before replace
        num_only = out.select_dtypes(include=[np.number])
        inf_count = (np.isinf(num_only)).to_numpy().sum() if not num_only.empty else 0
        if inf_count > 0:
            Console.warn(f"[OUTPUT] Replaced {int(inf_count)} Inf/-Inf values with None for SQL compatibility")

        # Replace in one pass
        out = out.replace({np.inf: None, -np.inf: None})
        out = out.where(pd.notnull(out), None)

        # Convert numpy scalars to Python types
        for col in out.columns:
            if col in non_numeric_cols:
                continue
            if pd.api.types.is_bool_dtype(out[col]):
                out[col] = out[col].astype(object).where(pd.isna(out[col]), out[col].astype(int))
            elif pd.api.types.is_numeric_dtype(out[col]):
                out[col] = out[col].astype(float)

        return out
    
    def _write_csv_optimized(self, df: pd.DataFrame, path: Path, **kwargs) -> None:
        """Optimized CSV writing with consistent parameters."""
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # CHART-04: Use optimized parameters for performance and consistency
        # Default date_format ensures uniform timestamp format across all CSVs
        default_kwargs = {
            'index': False,
            'float_format': '%.6g',
            'lineterminator': '\n',
            'encoding': 'utf-8',
            'date_format': '%Y-%m-%d %H:%M:%S'  # OUT-13: Uniform timestamp format
        }
        default_kwargs.update(kwargs)
        
        df.to_csv(path, **default_kwargs)
        self.stats['files_written'] += 1
        self.stats['total_rows'] += len(df)
    
    def _should_auto_flush(self) -> bool:
        """OUT-18: Check if batch should be automatically flushed based on triggers."""
        with self._batch_lock:
            # Size-based trigger
            if self._current_batch.total_rows >= self.batch_flush_rows:
                return True
            
            # Time-based trigger
            batch_age = time.time() - self._current_batch.created_at
            if batch_age >= self.batch_flush_seconds:
                return True
            
            return False
    
    def _wait_for_futures_capacity(self) -> None:
        """OUT-18: Block if too many in-flight operations (backpressure)."""
        while True:
            with self._futures_lock:
                # Clean up completed futures
                self._in_flight_futures = [f for f in self._in_flight_futures if not f.done()]
                
                # If we have capacity, proceed
                if len(self._in_flight_futures) < self.max_in_flight_futures:
                    break
            
            # Wait a bit before checking again
            time.sleep(0.1)
    
    def write_dataframe(self, 
                       df: pd.DataFrame, 
                       file_path: Path,
                       sql_table: Optional[str] = None,
                       sql_columns: Optional[Dict[str, str]] = None,
                       non_numeric_cols: Optional[set] = None,
                       add_created_at: bool = False,
                       allow_repair: bool = True,
                       **csv_kwargs) -> Dict[str, Any]:
        """
        Write DataFrame to CSV and optionally to SQL with dual-write coordination.
        
        Args:
            df: DataFrame to write
            file_path: Path for CSV file
            sql_table: Optional SQL table name for dual-write
            sql_columns: Optional column mapping for SQL (df_col -> sql_col)
            non_numeric_cols: Set of columns to treat as non-numeric for SQL
            add_created_at: Whether to add CreatedAt timestamp column for SQL
            allow_repair: OUT-17: If False, block SQL write when required fields missing instead of auto-repairing
            **csv_kwargs: Additional arguments for CSV writing
            
        Returns:
            Dictionary with write results and metadata
        """
        start_time = time.time()
        
        # path normalization and optional base dir enforcement
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        resolved_path = file_path.resolve()
        if self.base_output_dir and not str(resolved_path).startswith(str(self.base_output_dir)):
            raise ValueError(f"[OUTPUT] Path outside base_output_dir: {resolved_path}")
        
        result = {
            'file_written': False,
            'sql_written': False,
            'rows': len(df),
            'error': None
        }
        
        # OUT-18: Check if auto-flush needed before write
        if self._should_auto_flush():
            Console.info(f"[OUTPUT] Auto-flushing batch (rows={self._current_batch.total_rows}, age={time.time() - self._current_batch.created_at:.1f}s)")
            self.flush()
        
        # OUT-18: Apply backpressure if too many in-flight operations
        self._wait_for_futures_capacity()
        
        try:
            # Attach metadata identifiers to file outputs for future SQL ingestion
            df_out = df.copy()
            try:
                run_id_val = self.run_id or ""
                equip_id_val = int(self.equip_id) if self.equip_id is not None else 0
            except Exception:
                run_id_val, equip_id_val = "", 0

            # Normalize metadata columns eagerly to avoid dtype warnings under pandas >=2.2
            run_id_str = str(run_id_val) if run_id_val is not None else ""
            if "RunID" not in df_out.columns:
                df_out["RunID"] = run_id_str
            else:
                # Cast once to a flexible dtype before filling
                df_out["RunID"] = df_out["RunID"].astype("string")
                mask = df_out["RunID"].isna() | (df_out["RunID"].str.strip() == "")
                if mask.any():
                    df_out.loc[mask, "RunID"] = run_id_str

            if "EquipID" not in df_out.columns:
                df_out["EquipID"] = equip_id_val
            else:
                # Ensure numeric dtype prior to filling to prevent incompatible assignment warnings
                df_out["EquipID"] = pd.to_numeric(df_out["EquipID"], errors="coerce")
                mask_e = df_out["EquipID"].isna()
                if mask_e.any():
                    df_out.loc[mask_e, "EquipID"] = equip_id_val

            # Always write file first (guaranteed fallback)
            self._write_csv_optimized(df_out, file_path, **csv_kwargs)
            result['file_written'] = True
            
            # OUT-18: Update batch row tracking
            with self._batch_lock:
                self._current_batch.total_rows += len(df)
            
            # Attempt SQL write if configured
            if sql_table and self._check_sql_health():
                try:
                    # Prepare data for SQL
                    sql_df = self._prepare_dataframe_for_sql(df, non_numeric_cols or set())
                    
                    # Apply column mapping if provided
                    if sql_columns:
                        sql_df = sql_df.rename(columns=sql_columns)
                    
                    # Add metadata columns (required for all SQL tables)
                    sql_df["RunID"] = self.run_id
                    sql_df["EquipID"] = self.equip_id or 0
                    # OUT-17: Apply per-table required NOT NULL defaults with repair policy
                    sql_df, repair_info = self._apply_sql_required_defaults(sql_table, sql_df, allow_repair)
                    
                    # OUT-17: Block write if repairs needed but not allowed
                    if not allow_repair and repair_info['repairs_needed']:
                        raise ValueError(f"Required fields missing and allow_repair=False: {repair_info['missing_fields']}")
                    
                    # Add CreatedAt timestamp only if requested
                    if add_created_at:
                        sql_df["CreatedAt"] = pd.Timestamp.now().tz_localize(None)
                    
                    # Bulk insert with batching
                    inserted = self._bulk_insert_sql(sql_table, sql_df)
                    result['sql_written'] = inserted > 0
                    if result['sql_written']: 
                        self.stats['sql_writes'] += 1
                    
                except Exception as e:
                    Console.warn(f"[OUTPUT] SQL write failed for {sql_table}, file fallback succeeded: {e}")
                    result['error'] = str(e)
                    self.stats['sql_failures'] += 1
            
        except Exception as e:
            Console.error(f"[OUTPUT] Failed to write {file_path}: {e}")
            result['error'] = str(e)
            raise
        
        finally:
            elapsed = time.time() - start_time
            self.stats['write_time'] += elapsed
        
        return result

    def _apply_sql_required_defaults(self, table_name: str, df: pd.DataFrame, allow_repair: bool = True) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Fill required columns with safe defaults to satisfy NOT NULL constraints.
        Only applies to known analytics tables; unknown tables pass through.
        
        OUT-17: Now returns tuple of (repaired_df, repair_info) with audit columns added.
        
        Args:
            table_name: SQL table name
            df: DataFrame to repair
            allow_repair: If False, don't apply defaults but still report missing fields
            
        Returns:
            Tuple of (repaired DataFrame, repair_info dict with keys:
                      'repairs_needed', 'missing_fields', 'repaired_count')
        """
        repair_info = {
            'repairs_needed': False,
            'missing_fields': [],
            'repaired_count': 0
        }
        
        if df is None or df.empty:
            return df, repair_info
            
        req = self._sql_required_defaults.get(table_name)
        if not req:
            return df, repair_info
            
        out = df.copy()
        sentinel_ts = pd.Timestamp(year=1900, month=1, day=1)
        filled = {}
        missing_fields = []
        
        # OUT-17: Add repair audit column
        repair_flag_col = f"{table_name}_RepairFlag"
        out[repair_flag_col] = 0  # 0 = no repair, 1 = repaired
        
        for col, default in req.items():
            if default == 'ts':
                val = sentinel_ts
            else:
                val = default
                
            needs_repair = False
            
            if col not in out.columns:
                missing_fields.append(col)
                needs_repair = True
                if allow_repair:
                    out[col] = val
                    filled[col] = 'added'
                    out[repair_flag_col] = 1
            else:
                # Check for nulls
                try:
                    null_mask = out[col].isna()
                except Exception:
                    null_mask = None
                    
                if null_mask is not None and getattr(null_mask, 'any', lambda: False)():
                    count = int(null_mask.sum())
                    missing_fields.append(f"{col}({count} nulls)")
                    needs_repair = True
                    if allow_repair:
                        out.loc[null_mask, col] = val
                        out.loc[null_mask, repair_flag_col] = 1
                        filled[col] = count
                        
            if needs_repair:
                repair_info['repairs_needed'] = True
                repair_info['repaired_count'] += 1
        
        repair_info['missing_fields'] = missing_fields
        
        if filled:
            Console.info(f"[SCHEMA] {table_name}: applied defaults {filled}")
        if not allow_repair and repair_info['repairs_needed']:
            Console.warn(f"[SCHEMA] {table_name}: repairs blocked (allow_repair=False), missing: {missing_fields}")
            
        return out, repair_info

    def _bulk_insert_sql(self, table_name: str, df: pd.DataFrame) -> int:
        """Perform bulk SQL insert with optimized batching and robust commit."""
        if df.empty:
            return 0
        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Invalid table name: {table_name}")
        if self.sql_client is None:
            return 0

        inserted = 0
        cursor_factory = lambda: self.sql_client.cursor()

        # Optional: skip if the table doesn't exist (avoids noisy logs on dev DBs)
        exists = self._table_exists_cache.get(table_name)
        if exists is None:
            exists = _table_exists(cursor_factory, table_name)
            self._table_exists_cache[table_name] = bool(exists)
        if not exists:
            Console.warn(f"[OUTPUT] Skipping write: table dbo.[{table_name}] not found")
            return 0

        cur = cursor_factory()
        try:
            try:
                cur.fast_executemany = True
            except Exception:
                pass

            # discover table columns and scope delete by RunID only when present
            # determine insertable columns (exclude identity)
            table_cols: set
            try:
                if table_name in self._table_insertable_cache:
                    table_cols = self._table_insertable_cache[table_name]
                else:
                    cols = set(_get_insertable_columns(cursor_factory, table_name))
                    if not cols:
                        cols = set(_get_table_columns(cursor_factory, table_name))
                    self._table_insertable_cache[table_name] = cols
                    table_cols = cols
            except Exception:
                if table_name in self._table_columns_cache:
                    table_cols = self._table_columns_cache[table_name]
                else:
                    cols_all = set(_get_table_columns(cursor_factory, table_name))
                    self._table_columns_cache[table_name] = cols_all
                    table_cols = cols_all
            if "RunID" in df.columns and self.run_id and "RunID" in table_cols:
                # Prefer scoping by (RunID, EquipID) when possible
                if "EquipID" in df.columns and "EquipID" in table_cols and self.equip_id is not None:
                    cur.execute(f"DELETE FROM dbo.[{table_name}] WHERE RunID = ? AND EquipID = ?", (self.run_id, int(self.equip_id or 0)))
                else:
                    cur.execute(f"DELETE FROM dbo.[{table_name}] WHERE RunID = ?", (self.run_id,))

            # only insert columns that actually exist in the table
            columns = [c for c in df.columns if c in table_cols]
            cols_str = ", ".join(f"[{c}]" for c in columns)
            placeholders = ", ".join(["?"] * len(columns))
            insert_sql = f"INSERT INTO dbo.[{table_name}] ({cols_str}) VALUES ({placeholders})"

            records = [tuple(row) for row in df[columns].itertuples(index=False, name=None)]
            for i in range(0, len(records), self.batch_size):
                batch = records[i:i+self.batch_size]
                cur.executemany(insert_sql, batch)
                inserted += len(batch)
        except Exception as e:
            Console.error(f"[OUTPUT] SQL insert failed for {table_name}: {e}")
            raise
        finally:
            try:
                cur.close()
            except Exception:
                pass

        # Only commit if not in batched transaction mode
        if not self._batched_transaction_active:
            try:
                if hasattr(self.sql_client, "commit"):
                    self.sql_client.commit()
                elif hasattr(self.sql_client, "conn") and hasattr(self.sql_client.conn, "commit"):
                    # some wrappers expose .conn
                    if not getattr(self.sql_client.conn, "autocommit", True):
                        self.sql_client.conn.commit()
            except Exception as e:
                Console.error(f"[OUTPUT] SQL commit failed for {table_name}: {e}")
                raise

        Console.info(f"[OUTPUT] SQL insert to {table_name}: {inserted} rows")
        return inserted

    def write_json(self, data: Dict[str, Any], file_path: Path) -> None:
        """Write JSON data to file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with file_path.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.stats['files_written'] += 1
        Console.info(f"[OUTPUT] JSON written: {file_path}")
    
    def write_jsonl(self, records: List[Dict[str, Any]], file_path: Path) -> None:
        """Write JSON Lines format."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with file_path.open('w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        self.stats['files_written'] += 1
        self.stats['total_rows'] += len(records)
        Console.info(f"[OUTPUT] JSONL written: {file_path} ({len(records)} records)")
    
    # ==================== DATA TRANSFORMATION METHODS ====================
    
    def melt_scores_long(self, df_wide: pd.DataFrame, equip_id: int, run_id: str, source: str = "ACM") -> pd.DataFrame:
        """
        Convert a wide sensor frame (index = timestamps, columns = sensors) to
        the canonical long format for dbo.ScoresTS.
        """
        if not isinstance(df_wide.index, pd.DatetimeIndex):
            raise ValueError("melt_scores_long expects a DatetimeIndex.")
        out = df_wide.copy()
        out.index = pd.to_datetime(out.index)
        out = out.reset_index().rename(columns={"index": "EntryDateTime"})
        long = out.melt(id_vars=["EntryDateTime"], var_name="Sensor", value_name="Value")
        long["EquipID"] = int(equip_id)
        long["Source"] = source
        long["RunID"] = run_id
        return long

    # ==================== SPECIALIZED SQL WRITE FUNCTIONS ====================
    # These replace all the scattered write functions from data_io.py, storage.py, 
    # and sql_analytics_writer.py with a unified interface
    
    def write_scores_ts(self, df: pd.DataFrame, run_id: str) -> int:
        """Write scores timeseries to ACM_Scores_Long table."""
        if not self._check_sql_health():
            return 0
            
        try:
            sql_df = df.copy()

            if sql_df.empty:
                return 0

            # Case A: already long from melt_scores_long
            if {'EntryDateTime', 'Sensor', 'Value'}.issubset(set(sql_df.columns)):
                sql_df = sql_df.rename(columns={
                    'EntryDateTime': 'Timestamp',
                    'Sensor': 'DetectorType',
                    'Value': 'ZScore'
                })
                # Ensure required metadata exists
                if 'RunID' not in sql_df.columns:
                    sql_df['RunID'] = run_id
                if 'EquipID' not in sql_df.columns:
                    sql_df['EquipID'] = self.equip_id or 0
                sql_df['Timestamp'] = pd.to_datetime(sql_df['Timestamp']).dt.tz_localize(None)
                sql_df = sql_df.dropna(subset=['ZScore'])
                return self._bulk_insert_sql('ACM_Scores_Long', sql_df)

            # Case B: wide — melt to long
            if sql_df.index.name == 'timestamp' or isinstance(sql_df.index, pd.DatetimeIndex):
                sql_df = sql_df.reset_index().rename(columns={sql_df.columns[0]: 'Timestamp'})
            detector_cols = [c for c in sql_df.columns if c.endswith('_z') or c.startswith('ACM_')]
            if not detector_cols:
                return 0
            long_df = sql_df.melt(
                id_vars=['Timestamp'],
                value_vars=detector_cols,
                var_name='DetectorType',
                value_name='ZScore'
            )
            # Normalize names
            long_df['DetectorType'] = long_df['DetectorType'].str.replace('_z', '', regex=False)
            long_df['Timestamp'] = pd.to_datetime(long_df['Timestamp']).dt.tz_localize(None)
            long_df['RunID'] = run_id
            long_df['EquipID'] = self.equip_id or 0
            long_df = long_df.dropna(subset=['ZScore'])
            return self._bulk_insert_sql('ACM_Scores_Long', long_df)
            
        except Exception as e:
            Console.warn(f"[OUTPUT] write_scores_ts failed: {e}")
            return 0
    
    def write_drift_ts(self, df: pd.DataFrame, run_id: str) -> int:
        """Write drift timeseries to ACM_Drift_TS table."""
        if not self._check_sql_health():
            return 0
            
        try:
            sql_df = df.copy()
            
            # Expected columns: Timestamp, DriftValue, RunID, EquipID
            if 'drift_z' in sql_df.columns:
                sql_df['DriftValue'] = sql_df['drift_z']
            elif 'cusum_z' in sql_df.columns:
                sql_df['DriftValue'] = sql_df['cusum_z']
            elif 'value' in sql_df.columns:
                sql_df['DriftValue'] = sql_df['value']
            else:
                return 0
            
            # Prepare timestamp
            if sql_df.index.name == 'timestamp' or isinstance(sql_df.index, pd.DatetimeIndex):
                sql_df = sql_df.reset_index()
                timestamp_col = sql_df.columns[0]
                sql_df = sql_df.rename(columns={timestamp_col: 'Timestamp'})
            
            # Add metadata
            sql_df['RunID'] = run_id
            sql_df['EquipID'] = self.equip_id or 0
            
            # Select final columns
            sql_df = sql_df[['RunID', 'EquipID', 'Timestamp', 'DriftValue']].copy()
            sql_df['Timestamp'] = pd.to_datetime(sql_df['Timestamp']).dt.tz_localize(None)
            sql_df = sql_df.dropna(subset=['DriftValue'])
            
            return self._bulk_insert_sql('ACM_Drift_TS', sql_df)
            
        except Exception as e:
            Console.warn(f"[OUTPUT] write_drift_ts failed: {e}")
            return 0
    
    def write_anomaly_events(self, df: pd.DataFrame, run_id: str) -> int:
        """Write anomaly events to ACM_Anomaly_Events table."""
        if not self._check_sql_health() or df.empty:
            return 0
            
        try:
            sql_df = df.copy()
            
            # Map columns for ACM_Anomaly_Events
            column_map = {
                'episode_id': 'EpisodeID',
                'start_ts': 'StartTs',
                'end_ts': 'EndTs',
                'peak_fused_z': 'PeakScore',
                'severity': 'Severity',
                'status': 'Status'
            }
            
            for old_col, new_col in column_map.items():
                if old_col in sql_df.columns:
                    sql_df[new_col] = sql_df[old_col]
            
            # Add metadata
            sql_df['RunID'] = run_id
            sql_df['EquipID'] = self.equip_id or 0
            
            # Add defaults
            if 'Severity' not in sql_df.columns:
                sql_df['Severity'] = 'MEDIUM'
            if 'Status' not in sql_df.columns:
                sql_df['Status'] = 'OPEN'
            
            # Handle timestamps
            for ts_col in ['StartTs', 'EndTs']:
                if ts_col in sql_df.columns:
                    sql_df[ts_col] = pd.to_datetime(sql_df[ts_col]).dt.tz_localize(None)
            
            # Select final columns
            final_cols = ['RunID', 'EquipID', 'StartTs', 'EndTs', 'PeakScore', 'Severity', 'Status']
            sql_df = sql_df[[c for c in final_cols if c in sql_df.columns]]
            
            return self._bulk_insert_sql('ACM_Anomaly_Events', sql_df)
            
        except Exception as e:
            Console.warn(f"[OUTPUT] write_anomaly_events failed: {e}")
            return 0
    
    def write_regime_episodes(self, df: pd.DataFrame, run_id: str) -> int:
        """Write regime episodes to ACM_Regime_Episodes table."""
        if not self._check_sql_health() or df.empty:
            return 0
            
        try:
            sql_df = df.copy()
            
            # Map columns for ACM_Regime_Episodes
            column_map = {
                'start_ts': 'StartTs',
                'end_ts': 'EndTs',
                'regime_label': 'RegimeLabel',
                'duration_s': 'DurationSeconds',
                'stability_score': 'StabilityScore'
            }
            
            for old_col, new_col in column_map.items():
                if old_col in sql_df.columns:
                    sql_df[new_col] = sql_df[old_col]
            
            # Add metadata
            sql_df['RunID'] = run_id
            sql_df['EquipID'] = self.equip_id or 0
            
            # Handle timestamps
            for ts_col in ['StartTs', 'EndTs']:
                if ts_col in sql_df.columns:
                    sql_df[ts_col] = pd.to_datetime(sql_df[ts_col]).dt.tz_localize(None)
            
            # Select final columns
            final_cols = ['RunID', 'EquipID', 'StartTs', 'EndTs', 'RegimeLabel', 'DurationSeconds', 'StabilityScore']
            sql_df = sql_df[[c for c in final_cols if c in sql_df.columns]]
            
            return self._bulk_insert_sql('ACM_Regime_Episodes', sql_df)
            
        except Exception as e:
            Console.warn(f"[OUTPUT] write_regime_episodes failed: {e}")
            return 0
    
    def write_pca_model(self, model_data: Dict[str, Any]) -> int:
        """Write PCA model metadata to ACM_PCA_Models table."""
        if not self._check_sql_health():
            return 0
            
        try:
            # Accept caller-provided schema and add common metadata when missing
            row = dict(model_data)
            row.setdefault('RunID', self.run_id)
            row.setdefault('EquipID', self.equip_id or 0)
            # Provide CreatedAt if not present
            if 'CreatedAt' not in row:
                row['CreatedAt'] = pd.Timestamp.now().tz_localize(None)
            sql_df = pd.DataFrame([row])
            
            return self._bulk_insert_sql('ACM_PCA_Models', sql_df)
            
        except Exception as e:
            Console.warn(f"[OUTPUT] write_pca_model failed: {e}")
            return 0
    
    def write_pca_loadings(self, df: pd.DataFrame, run_id: str) -> int:
        """Write PCA loadings to ACM_PCA_Loadings table."""
        if not self._check_sql_health() or df.empty:
            return 0
            
        try:
            sql_df = df.copy()
            
            # Normalize possible caller column names
            sql_df['RunID'] = sql_df.get('RunID', run_id)
            sql_df['EquipID'] = sql_df.get('EquipID', self.equip_id or 0)
            if 'ComponentID' not in sql_df.columns and 'ComponentNo' in sql_df.columns:
                sql_df['ComponentID'] = sql_df['ComponentNo']
            if 'FeatureName' not in sql_df.columns and 'Sensor' in sql_df.columns:
                sql_df['FeatureName'] = sql_df['Sensor']
            # Keep common columns; _bulk_insert_sql will filter to table cols
            
            return self._bulk_insert_sql('ACM_PCA_Loadings', sql_df)
            
        except Exception as e:
            Console.warn(f"[OUTPUT] write_pca_loadings failed: {e}")
            return 0
    
    def write_pca_metrics(self, df: pd.DataFrame, run_id: str) -> int:
        """Write PCA metrics to ACM_PCA_Metrics table."""
        if not self._check_sql_health() or df.empty:
            return 0
            
        try:
            sql_df = df.copy()
            
            # Add metadata if missing
            if 'RunID' not in sql_df.columns:
                sql_df['RunID'] = run_id
            if 'EquipID' not in sql_df.columns:
                sql_df['EquipID'] = self.equip_id or 0
            
            # Expected columns vary - just pass through with metadata
            return self._bulk_insert_sql('ACM_PCA_Metrics', sql_df)
            
        except Exception as e:
            Console.warn(f"[OUTPUT] write_pca_metrics failed: {e}")
            return 0
    
    def write_run_stats(self, stats_data: Dict[str, Any]) -> int:
        """Write run statistics to ACM_Run_Stats table."""
        if not self._check_sql_health():
            return 0
        try:
            row = dict(stats_data)
            # Normalize key variants
            if 'StartTime' not in row and 'WindowStartEntryDateTime' in row:
                row['StartTime'] = _to_naive(row.get('WindowStartEntryDateTime'))
            if 'EndTime' not in row and 'WindowEndEntryDateTime' in row:
                row['EndTime'] = _to_naive(row.get('WindowEndEntryDateTime'))
            row.setdefault('RunID', self.run_id)
            row.setdefault('EquipID', self.equip_id or 0)
            sql_df = pd.DataFrame([row])
            return self._bulk_insert_sql('ACM_Run_Stats', sql_df)
        except Exception as e:
            Console.error(f"[OUTPUT] write_run_stats failed: {e}")
            return 0
    
    def write_scores(self, 
                    scores_df: pd.DataFrame, 
                    run_dir: Path,
                    enable_sql: bool = True) -> Dict[str, Any]:
        """
        Write scores with optimized dual-write coordination.
        
        Replaces storage.write_scores_csv() with better performance.
        """
        # Prepare scores for output
        scores_for_output = scores_df.copy()
        scores_for_output.index.name = "timestamp"
        
        # Convert index to UTC naive timestamps
        if len(scores_for_output.index):
            try:
                scores_for_output.index = pd.to_datetime(scores_for_output.index).tz_localize(None)
            except Exception:
                scores_for_output.index = pd.to_datetime(scores_for_output.index).tz_localize(None)
        
        # Write with SQL dual-write if enabled
        sql_table = "ACM_Scores_Wide" if enable_sql else None
        score_columns = {
            "timestamp": "Timestamp",
            "ar1_z": "ar1_z", "pca_spe_z": "pca_spe_z", "pca_t2_z": "pca_t2_z",
            "mhal_z": "mhal_z", "iforest_z": "iforest_z", "gmm_z": "gmm_z",
            "cusum_z": "cusum_z", "drift_z": "drift_z", "hst_z": "hst_z", "river_hst_z": "river_hst_z", "fused": "fused",
            "regime_label": "regime_label"
        }
        
        # CHART-04: Use uniform timestamp format without 'T' or 'Z' suffixes
        return self.write_dataframe(
            scores_for_output.reset_index(),
            run_dir / "scores.csv",
            sql_table=sql_table,
            sql_columns=score_columns,
            non_numeric_cols={"RunID", "EquipID", "Timestamp", "regime_label"},
            index=False,
            date_format="%Y-%m-%d %H:%M:%S"
        )
    
    def write_episodes(self, 
                      episodes_df: pd.DataFrame, 
                      run_dir: Path,
                      enable_sql: bool = True) -> Dict[str, Any]:
        """
        Write episodes with optimized dual-write coordination.
        
        Replaces storage.write_episodes_csv() with better performance.
        """
        if episodes_df.empty:
            # Write empty file
            empty_df = pd.DataFrame(columns=['episode_id', 'start_ts', 'end_ts', 'duration_s'])
            return self.write_dataframe(empty_df, run_dir / "episodes.csv")
        
        # Prepare episodes for output
        episodes_for_output = episodes_df.copy().reset_index(drop=True)
        
        # SQL column mapping
        sql_table = "ACM_Episodes" if enable_sql else None
        episode_columns = {
            'start_ts': 'StartTs', 
            'end_ts': 'EndTs',
            'duration_s': 'DurationSeconds',
            'duration_hours': 'DurationHours',
            'len': 'RecordCount',
            'peak_fused_z': 'PeakFusedZ',
            'avg_fused_z': 'AvgFusedZ',
            'min_health_index': 'MinHealthIndex',
            'peak_timestamp': 'PeakTimestamp',
            'culprits': 'Culprits',
            'alert_mode': 'AlertMode',
            'severity': 'Severity',
            'status': 'Status',
            'MaxRegimeLabel': 'MaxRegimeLabel'
        }
        
        # Map regime_label to MaxRegimeLabel
        if 'regime_label' in episodes_for_output.columns:
            episodes_for_output['MaxRegimeLabel'] = episodes_for_output['regime_label']
        elif 'regime' in episodes_for_output.columns:
            episodes_for_output['MaxRegimeLabel'] = episodes_for_output['regime']
        
        # Add defaults for SQL
        if enable_sql:
            if 'severity' not in episodes_for_output.columns:
                episodes_for_output['severity'] = 'MEDIUM'
            if 'status' not in episodes_for_output.columns:
                episodes_for_output['status'] = 'CLOSED'
        
        result = self.write_dataframe(
            episodes_for_output,
            run_dir / "episodes.csv",
            sql_table=sql_table,
            sql_columns=episode_columns,
            non_numeric_cols={
                "RunID", "EquipID", "StartTs", "EndTs", "PeakTimestamp",
                "MaxRegimeLabel", "Culprits", "AlertMode", "Severity", "Status"
            }
        )
        
        # OUT-28: Emit episodes severity mapping JSON
        try:
            severity_mapping = self._generate_episode_severity_mapping(episodes_for_output)
            tables_dir = run_dir / "tables"
            tables_dir.mkdir(exist_ok=True)
            severity_path = tables_dir / "episodes_severity_mapping.json"
            with open(severity_path, 'w') as f:
                import json
                json.dump(severity_mapping, f, indent=2)
            Console.info(f"[EPISODES] Generated severity mapping: {severity_path}")
        except Exception as e:
            Console.warn(f"[EPISODES] Failed to generate severity mapping: {e}")
        
        return result
    
    def batch_write_csvs(self, csv_data: Dict[Path, pd.DataFrame]) -> Dict[Path, Dict[str, Any]]:
        """
        Write multiple CSVs efficiently using threading for I/O parallelization.
        
        Args:
            csv_data: Dictionary mapping file paths to DataFrames
            
        Returns:
            Dictionary mapping paths to write results
        """
        if not csv_data:
            return {}
        
        results = {}
        
        if not self.enable_batching or len(csv_data) == 1:
            # Sequential writes for small batches or when batching disabled
            for path, df in csv_data.items():
                results[path] = self.write_dataframe(df, path)
        else:
            # Parallel writes for better I/O performance
            import os
            with ThreadPoolExecutor(max_workers=min(self.max_io_workers, len(csv_data), (os.cpu_count() or 1))) as executor:
                future_to_path = {
                    executor.submit(self.write_dataframe, df, path): path
                    for path, df in csv_data.items()
                }
                
                for future in as_completed(future_to_path):
                    path = future_to_path[future]
                    try:
                        results[path] = future.result()
                    except Exception as e:
                        Console.error(f"[OUTPUT] Batch write failed for {path}: {e}")
                        results[path] = {'error': str(e), 'file_written': False, 'sql_written': False}
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            **self.stats,
            'avg_write_time': self.stats['write_time'] / max(1, self.stats['files_written']),
            'sql_success_rate': 1.0 - (self.stats['sql_failures'] / max(1, self.stats['sql_health_checks']))
        }
    
    def flush(self) -> None:
        """OUT-18: Flush current batch without finalizing (for auto-flush triggers)."""
        with self._batch_lock:
            if self._current_batch.csv_files:
                self.batch_write_csvs(self._current_batch.csv_files)
                self._current_batch.csv_files.clear()
            
            if self._current_batch.json_files:
                for path, data in self._current_batch.json_files.items():
                    self.write_json(data, path)
                self._current_batch.json_files.clear()
            
            # Reset batch for next accumulation
            self._current_batch = OutputBatch()
    
    def flush_and_finalize(self) -> Dict[str, Any]:
        """Flush any pending operations and return final statistics."""
        self.flush()  # OUT-18: Use flush() for DRY
        
        stats = self.get_stats()
        Console.info(f"[OUTPUT] Finalized: {stats['files_written']} files, "
                    f"{stats['sql_writes']} SQL ops, "
                    f"{stats['total_rows']} total rows, "
                    f"{stats['avg_write_time']:.3f}s avg write time")
        
        return stats

    def close(self) -> None:
        """Gracefully finalize outstanding work. Compatible with acm_main finally block."""
        try:
            self.flush_and_finalize()
        except Exception:
            pass

    # ==================== COMPREHENSIVE ANALYTICS TABLES ====================
    
    def generate_all_analytics_tables(self, 
                                     scores_df: pd.DataFrame, 
                                     episodes_df: pd.DataFrame, 
                                     cfg: Dict[str, Any],
                                     tables_dir: Path,
                                     enable_sql: bool = True,
                                     sensor_context: Optional[Dict[str, Any]] = None) -> Dict[str, int]:  # Default to TRUE for SQL mode
        """
        Generate all 26 comprehensive analytics tables for complete analytical coverage.
        
        MANDATES that ALL data is written to SQL database - no exceptions!
        This provides the rock-solid analytical basis required by operators and engineers.
        
        PERFORMANCE: Uses batched transaction for all SQL writes to minimize commit overhead.
        """
        Console.info("[ANALYTICS] Generating comprehensive analytics tables...")
        table_count = 0
        sql_count = 0
        
        # FORCE SQL WRITES - this is mandatory in SQL mode
        force_sql = enable_sql or (self.sql_client is not None)

        sensor_values = None
        sensor_zscores = None
        sensor_train_mean = None
        sensor_train_std = None
        omr_contributions = None
        if sensor_context:
            values_candidate = sensor_context.get('values')
            zscores_candidate = sensor_context.get('z_scores')
            if isinstance(values_candidate, pd.DataFrame) and len(values_candidate.columns):
                sensor_values = values_candidate.reindex(scores_df.index)
            if isinstance(zscores_candidate, pd.DataFrame) and len(zscores_candidate.columns):
                sensor_zscores = zscores_candidate.reindex(scores_df.index)
            mean_candidate = sensor_context.get('train_mean')
            std_candidate = sensor_context.get('train_std')
            if isinstance(mean_candidate, pd.Series):
                sensor_train_mean = mean_candidate
            if isinstance(std_candidate, pd.Series):
                sensor_train_std = std_candidate
            omni = sensor_context.get('omr_contributions') if isinstance(sensor_context, dict) else None
            if isinstance(omni, pd.DataFrame) and len(omni.index):
                try:
                    omr_contributions = omni.reindex(scores_df.index)
                except Exception:
                    omr_contributions = omni
        
        # ANA-12: Tiered analytics - check fused availability
        has_fused = 'fused' in scores_df.columns
        has_regimes = 'regime_label' in scores_df.columns
        
        # Use batched transaction for all SQL writes (58s → <15s target)
        with self.batched_transaction():
            try:
                # TIER-A & TIER-B: Write detector-level and regime tables even if fused missing
                # These provide diagnostic value independent of fused scores
                
                # TIER-B: Detector correlation (no fused dependency)
                detector_corr_df = self._generate_detector_correlation(scores_df)
                result = self.write_dataframe(detector_corr_df, tables_dir / "detector_correlation.csv",
                                            sql_table="ACM_DetectorCorrelation" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1
                
                # TIER-B: Calibration summary (no fused dependency)
                calibration_df = self._generate_calibration_summary(scores_df, cfg)
                result = self.write_dataframe(calibration_df, tables_dir / "calibration_summary.csv",
                                              sql_table="ACM_CalibrationSummary" if force_sql else None,
                                              add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1

                # Write OMR per-sensor contributions (long format) when available
                if omr_contributions is not None and not omr_contributions.empty:
                    try:
                        omr_long = self._generate_omr_contributions_long(scores_df, omr_contributions)
                        self.write_dataframe(omr_long, tables_dir / "omr_contributions_long.csv",
                                             sql_table=None,
                                             add_created_at=False)
                        table_count += 1
                    except Exception as e:
                        Console.warn(f"[ANALYTICS] Failed to write omr_contributions_long.csv: {e}")

                # Fusion quality snapshot (weights + basic stats)
                try:
                    fusion_q_df = self._generate_fusion_quality_report(scores_df, cfg)
                    result = self.write_dataframe(fusion_q_df, tables_dir / "fusion_quality_report.csv",
                                                  sql_table=None,
                                                  add_created_at=False)
                    table_count += 1
                except Exception as e:
                    Console.warn(f"[ANALYTICS] Failed to write fusion_quality_report.csv: {e}")
                
                # TIER-A: Regime tables (if available, no fused dependency)
                if has_regimes:
                    Console.info("[ANALYTICS] Writing Tier-A regime tables...")
                    regime_occ_df = self._generate_regime_occupancy(scores_df)
                    result = self.write_dataframe(regime_occ_df, tables_dir / "regime_occupancy.csv",
                                                sql_table="ACM_RegimeOccupancy" if force_sql else None,
                                                add_created_at=True)
                    table_count += 1
                    if result.get('sql_written'): sql_count += 1
                    
                    regime_trans_df = self._generate_regime_transition_matrix(scores_df)
                    result = self.write_dataframe(regime_trans_df, tables_dir / "regime_transition_matrix.csv",
                                                sql_table="ACM_RegimeTransitions" if force_sql else None,
                                                add_created_at=True)
                    table_count += 1
                    if result.get('sql_written'): sql_count += 1
                    
                    regime_dwell_df = self._generate_regime_dwell_stats(scores_df)
                    result = self.write_dataframe(regime_dwell_df, tables_dir / "regime_dwell_stats.csv",
                                                sql_table="ACM_RegimeDwellStats" if force_sql else None,
                                                add_created_at=True)
                    table_count += 1
                    if result.get('sql_written'): sql_count += 1
                
                # ANA-12: If fused missing, return after Tier-A/B tables
                if not has_fused:
                    Console.warn("[ANALYTICS] No fused scores - Tier-C (health, defects, episodes) tables skipped")
                    Console.info(f"[ANALYTICS] Wrote {table_count} Tier-A/B tables ({sql_count} to SQL)")
                    return {"csv_tables": table_count, "sql_tables": sql_count}
                
                # TIER-C: Fused-dependent tables (all below require 'fused' column)
                Console.info("[ANALYTICS] Writing Tier-C fused-dependent tables...")
                
                # 1. Health Timeline (enhanced)
                health_df = self._generate_health_timeline(scores_df)
                result = self.write_dataframe(health_df, tables_dir / "health_timeline.csv", 
                                            sql_table="ACM_HealthTimeline" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1

                # 1b. Health distribution over time (hourly buckets)
                try:
                    hdist_df = self._generate_health_distribution_over_time(scores_df)
                    result = self.write_dataframe(hdist_df, tables_dir / "health_distribution_over_time.csv",
                                                 sql_table=None,
                                                 add_created_at=False)
                    table_count += 1
                except Exception as e:
                    Console.warn(f"[ANALYTICS] Failed to write health_distribution_over_time.csv: {e}")
                
                # 2. Regime Timeline (enhanced)  
                if 'regime_label' in scores_df.columns:
                    regime_df = self._generate_regime_timeline(scores_df)
                    result = self.write_dataframe(regime_df, tables_dir / "regime_timeline.csv",
                                                sql_table="ACM_RegimeTimeline" if force_sql else None,
                                                add_created_at=True)
                    table_count += 1
                    if result.get('sql_written'): sql_count += 1

                # 2b. OMR timeline (if available)
                if 'omr_z' in scores_df.columns:
                    try:
                        omr_tl_df = self._generate_omr_timeline(scores_df, cfg)
                        result = self.write_dataframe(omr_tl_df, tables_dir / "omr_timeline.csv",
                                                     sql_table=None,
                                                     add_created_at=False)
                        table_count += 1
                    except Exception as e:
                        Console.warn(f"[ANALYTICS] Failed to write omr_timeline.csv: {e}")

                    # Compact regime stats for dashboards
                    try:
                        regime_stats_df = self._generate_regime_stats(scores_df)
                        self.write_dataframe(regime_stats_df, tables_dir / "regime_stats.csv",
                                             sql_table=None,
                                             add_created_at=False)
                        table_count += 1
                    except Exception as e:
                        Console.warn(f"[ANALYTICS] Failed to write regime_stats.csv: {e}")
                
                # 3. Contribution Now (current sensor importance)
                contrib_now_df = self._generate_contrib_now(scores_df)
                result = self.write_dataframe(contrib_now_df, tables_dir / "contrib_now.csv",
                                            sql_table="ACM_ContributionCurrent" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1
                
                # 4. Contribution Timeline (historical contributions)
                contrib_timeline_df = self._generate_contrib_timeline(scores_df)
                result = self.write_dataframe(contrib_timeline_df, tables_dir / "contrib_timeline.csv",
                                            sql_table="ACM_ContributionTimeline" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1
                
                # 5. Drift Series (CUSUM/drift detection)
                if 'drift_z' in scores_df.columns or 'cusum_z' in scores_df.columns:
                    drift_df = self._generate_drift_series(scores_df)
                    result = self.write_dataframe(drift_df, tables_dir / "drift_series.csv",
                                                sql_table="ACM_DriftSeries" if force_sql else None,
                                                add_created_at=True)
                    table_count += 1
                    if result.get('sql_written'): sql_count += 1
                
                # 6. Threshold Crossings (anomaly events)
                threshold_df = self._generate_threshold_crossings(scores_df)
                result = self.write_dataframe(threshold_df, tables_dir / "threshold_crossings.csv",
                                            sql_table="ACM_ThresholdCrossings" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1
                
                # 7. Since When (alert start times)
                since_when_df = self._generate_since_when(scores_df)
                result = self.write_dataframe(since_when_df, tables_dir / "since_when.csv",
                                            sql_table="ACM_SinceWhen" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1
                
                # 8. Sensor Rank Now (current importance ranking)
                sensor_rank_df = self._generate_sensor_rank_now(scores_df)
                result = self.write_dataframe(sensor_rank_df, tables_dir / "sensor_rank_now.csv",
                                            sql_table="ACM_SensorRanking" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1
                
                # 9. Health Histogram (distribution)
                health_hist_df = self._generate_health_histogram(scores_df)
                result = self.write_dataframe(health_hist_df, tables_dir / "health_hist.csv",
                                            sql_table="ACM_HealthHistogram" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1

                # Daily fused profile (hour x weekday) for simplified dashboards
                try:
                    daily_profile_df = self._generate_daily_fused_profile(scores_df)
                    if not daily_profile_df.empty:
                        self.write_dataframe(daily_profile_df, tables_dir / "daily_fused_profile.csv",
                                             sql_table=None,
                                             add_created_at=False)
                        table_count += 1
                except Exception as e:
                    Console.warn(f"[ANALYTICS] Failed to write daily_fused_profile.csv: {e}")
                
                # 11. Alert Age (duration tracking)
                alert_age_df = self._generate_alert_age(scores_df)
                result = self.write_dataframe(alert_age_df, tables_dir / "alert_age.csv",
                                            sql_table="ACM_AlertAge" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1
                
                # 12. Regime Stability (churn metrics)
                if 'regime_label' in scores_df.columns:
                    regime_stab_df = self._generate_regime_stability(scores_df)
                    result = self.write_dataframe(regime_stab_df, tables_dir / "regime_stability.csv",
                                                sql_table="ACM_RegimeStability" if force_sql else None,
                                                add_created_at=True)
                    table_count += 1
                    if result.get('sql_written'): sql_count += 1
                
                # 13-15. Defect-Focused Tables (operator-friendly)
                defect_summary_df = self._generate_defect_summary(scores_df, episodes_df)
                result = self.write_dataframe(defect_summary_df, tables_dir / "defect_summary.csv",
                                            sql_table="ACM_DefectSummary" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1
                
                defect_timeline_df = self._generate_defect_timeline(scores_df)
                result = self.write_dataframe(defect_timeline_df, tables_dir / "defect_timeline.csv",
                                            sql_table="ACM_DefectTimeline" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1
                
                sensor_defects_df = self._generate_sensor_defects(scores_df)
                result = self.write_dataframe(sensor_defects_df, tables_dir / "sensor_defects.csv",
                                            sql_table="ACM_SensorDefects" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1
                
                # 16-17. Health Zone Analysis
                health_zone_df = self._generate_health_zone_by_period(scores_df)
                result = self.write_dataframe(health_zone_df, tables_dir / "health_zone_by_period.csv",
                                            sql_table="ACM_HealthZoneByPeriod" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1
                
                sensor_anomaly_df = self._generate_sensor_anomaly_by_period(scores_df)
                result = self.write_dataframe(sensor_anomaly_df, tables_dir / "sensor_anomaly_by_period.csv",
                                            sql_table="ACM_SensorAnomalyByPeriod" if force_sql else None,
                                            add_created_at=True)
                table_count += 1
                if result.get('sql_written'): sql_count += 1

                sensor_ready = sensor_zscores is not None and sensor_values is not None
                if sensor_ready:
                    warn_threshold = float((cfg.get('regimes', {}) or {}).get('health', {}).get('fused_warn_z', 1.5) or 1.5)
                    alert_threshold = float((cfg.get('regimes', {}) or {}).get('health', {}).get('fused_alert_z', 3.0) or 3.0)
                    top_n = int((cfg.get('output', {}) or {}).get('sensor_hotspot_top_n', 25))

                    sensor_hotspots_df = self._generate_sensor_hotspots_table(
                        sensor_zscores,
                        sensor_values,
                        sensor_train_mean,
                        sensor_train_std,
                        warn_threshold,
                        alert_threshold,
                        top_n
                    )
                    result = self.write_dataframe(
                        sensor_hotspots_df,
                        tables_dir / "sensor_hotspots.csv",
                        sql_table="ACM_SensorHotspots" if force_sql else None,
                        non_numeric_cols={"SensorName"},
                        add_created_at=True
                    )
                    table_count += 1
                    if result.get('sql_written'): sql_count += 1

                    sensor_timeline_df = self._generate_sensor_hotspot_timeline(
                        sensor_zscores,
                        sensor_values,
                        warn_threshold,
                        alert_threshold,
                        top_k=3
                    )
                    result = self.write_dataframe(
                        sensor_timeline_df,
                        tables_dir / "sensor_hotspot_timeline.csv",
                        sql_table="ACM_SensorHotspotTimeline" if force_sql else None,
                        non_numeric_cols={"SensorName", "Level"},
                        add_created_at=True
                    )
                    table_count += 1
                    if result.get('sql_written'): sql_count += 1
                
                # 18. Already generated: data_quality.csv
                
                # 19. Drift Events
                if 'drift_z' in scores_df.columns or 'cusum_z' in scores_df.columns:
                    drift_events_df = self._generate_drift_events(scores_df)
                    result = self.write_dataframe(drift_events_df, tables_dir / "drift_events.csv",
                                                sql_table="ACM_DriftEvents" if force_sql else None,
                                                add_created_at=True)
                    table_count += 1
                    if result.get('sql_written'): sql_count += 1
                
                # 24. Culprit History (episode-based sensor culprit tracking)
                if episodes_df is not None and not episodes_df.empty:
                    culprit_hist_df = self._generate_culprit_history(scores_df, episodes_df)
                    result = self.write_dataframe(culprit_hist_df, tables_dir / "culprit_history.csv",
                                                sql_table="ACM_CulpritHistory" if force_sql else None,
                                                add_created_at=True)
                    table_count += 1
                    if result.get('sql_written'): sql_count += 1

                    # 25. Episode Metrics (episode statistical summary)
                    episode_metrics_df = self._generate_episode_metrics(episodes_df)
                    result = self.write_dataframe(episode_metrics_df, tables_dir / "episode_metrics.csv",
                                                sql_table="ACM_EpisodeMetrics" if force_sql else None,
                                                add_created_at=True)
                    table_count += 1
                    if result.get('sql_written'): sql_count += 1

                    # 25b. Episode Diagnostics (per-episode troubleshooting metrics)
                    episode_diagnostics_df = self._generate_episode_diagnostics(episodes_df, scores_df)
                    result = self.write_dataframe(episode_diagnostics_df, tables_dir / "episode_diagnostics.csv",
                                                sql_table="ACM_EpisodeDiagnostics" if force_sql else None,
                                                add_created_at=True)
                    table_count += 1
                    if result.get('sql_written'): sql_count += 1

                    # 25c. Episodes QC (run-level quality summary)
                    try:
                        episodes_qc_df = self._generate_episodes_qc(scores_df, episodes_df)
                        self.write_dataframe(episodes_qc_df, tables_dir / "episodes_qc.csv",
                                             sql_table=None,
                                             add_created_at=False)
                        table_count += 1
                    except Exception as e:
                        Console.warn(f"[ANALYTICS] Failed to write episodes_qc.csv: {e}")
                
                # 26. Data Quality (already written separately, but ensure SQL write)
                if force_sql:
                    try:
                        data_quality_path = tables_dir / "data_quality.csv"
                        if data_quality_path.exists():
                            dq_df = pd.read_csv(data_quality_path)
                            # Ensure required SQL columns exist with safe defaults
                            if 'CheckName' not in dq_df.columns:
                                dq_df['CheckName'] = 'NullsBySensor'
                            # Provide a likely-cased Sensor column if only lowercase exists
                            if 'sensor' in dq_df.columns and 'Sensor' not in dq_df.columns:
                                dq_df['Sensor'] = dq_df['sensor']
                            # Derive a CheckResult when missing based on null percentages and notes
                            if 'CheckResult' not in dq_df.columns:
                                def _derive_result(row):
                                    try:
                                        notes = str(row.get('notes', '') or '').lower()
                                        tr_pct = float(row.get('train_null_pct', 0) or 0)
                                        sc_pct = float(row.get('score_null_pct', 0) or 0)
                                        if 'all_nulls_train' in notes or 'all_nulls_score' in notes:
                                            return 'FAIL'
                                        if max(tr_pct, sc_pct) >= 80:
                                            return 'FAIL'
                                        if max(tr_pct, sc_pct) >= 10:
                                            return 'WARN'
                                        if 'low_variance_train' in notes:
                                            return 'WARN'
                                        return 'OK'
                                    except Exception:
                                        return 'OK'
                                dq_df['CheckResult'] = dq_df.apply(_derive_result, axis=1)
                            result = self.write_dataframe(
                                dq_df,
                                data_quality_path,
                                sql_table="ACM_DataQuality",
                                add_created_at=True
                            )
                            if result.get('sql_written'): sql_count += 1
                    except Exception as e:
                        Console.warn(f"[ANALYTICS] Failed to write data_quality to SQL: {e}")
                
                # OUT-20: Generate schema descriptor JSON after all tables are written
                try:
                    schema_descriptor = self._generate_schema_descriptor(tables_dir)
                    schema_path = tables_dir / "schema_descriptor.json"
                    with open(schema_path, 'w') as f:
                        import json
                        json.dump(schema_descriptor, f, indent=2)
                    Console.info(f"[ANALYTICS] Generated schema descriptor: {schema_path}")
                except Exception as e:
                    Console.warn(f"[ANALYTICS] Failed to generate schema descriptor: {e}")
                    
                Console.info(f"[ANALYTICS] Generated {table_count} comprehensive analytics tables")
                Console.info(f"[ANALYTICS] Written {sql_count} tables to SQL database")
                return {"csv_tables": table_count, "sql_tables": sql_count}
                
            except Exception as e:
                Console.warn(f"[ANALYTICS] Comprehensive table generation failed: {e}")
                import traceback
                Console.warn(f"[ANALYTICS] Error traceback: {traceback.format_exc()}")
                return {"csv_tables": table_count, "sql_tables": sql_count}
    
    def generate_default_charts(
        self,
        scores_df: pd.DataFrame,
        episodes_df: pd.DataFrame,
        cfg: Dict[str, Any],
        charts_dir: Union[str, Path],
        sensor_context: Optional[Dict[str, Any]] = None
    ) -> List[Path]:
        """Render baseline charts that operators rely on for quick triage."""
        try:
            import matplotlib.pyplot as plt  # type: ignore
            from matplotlib import dates as mdates  # type: ignore
        except Exception as exc:
            Console.warn(f"[CHARTS] Matplotlib unavailable: {exc}")
            return []

        charts_path = Path(charts_dir)
        charts_path.mkdir(parents=True, exist_ok=True)
        generated: List[Path] = []
        
        # OUT-14: Chart generation log for tracking rendered/skipped charts
        chart_log: List[Dict[str, Any]] = []
        
        # OUT-25: Standardize chart timestamp formatter
        CHART_DATE_FORMAT = '%Y-%m-%d\n%H:%M'

        scores = scores_df.copy()
        if 'fused' not in scores.columns and 'fused_z' in scores.columns:
            scores['fused'] = pd.to_numeric(scores['fused_z'], errors='coerce')
        else:
            scores['fused'] = pd.to_numeric(scores.get('fused'), errors='coerce')

        fused_series = scores['fused'] if 'fused' in scores else pd.Series(dtype=float)
        ts_index = pd.to_datetime(scores.index, errors='coerce')
        # Timestamps are already local naive, no conversion needed
        ts_local = ts_index.tz_localize(None) if ts_index.tz is not None else ts_index
        detector_cols = [c for c in scores.columns if c.endswith('_z') and c not in ('fused', 'fused_z')]

        sensor_ctx = sensor_context or {}
        sensor_values = sensor_ctx.get('values') if isinstance(sensor_ctx.get('values'), pd.DataFrame) else None
        sensor_zscores = sensor_ctx.get('z_scores') if isinstance(sensor_ctx.get('z_scores'), pd.DataFrame) else None
        if sensor_values is not None:
            sensor_values = sensor_values.reindex(scores.index)
        if sensor_zscores is not None:
            sensor_zscores = sensor_zscores.reindex(scores.index)
            sensor_abs_z = sensor_zscores.abs()
        else:
            sensor_abs_z = None

        episodes = episodes_df.copy() if episodes_df is not None else pd.DataFrame()
        # Convert timestamp columns to proper datetime objects for plotting
        for col in ('start_ts', 'StartTs'):
            if col in episodes.columns:
                episodes[col] = pd.to_datetime(episodes[col], errors='coerce')
        for col in ('end_ts', 'EndTs'):
            if col in episodes.columns:
                episodes[col] = pd.to_datetime(episodes[col], errors='coerce')
        severity_col = next((c for c in ('severity', 'Severity') if c in episodes.columns), None)
        start_col = next((c for c in ('start_ts', 'StartTs') if c in episodes.columns), None)
        end_col = next((c for c in ('end_ts', 'EndTs') if c in episodes.columns), None)

        clip_z = float(((cfg.get('thresholds', {}) or {}).get('self_tune', {}) or {}).get('clip_z', 30.0) or 30.0)
        fusion_weights = ((cfg.get('fusion', {}) or {}).get('weights', {}) or {})
        omr_series = pd.to_numeric(scores.get('omr_z'), errors='coerce') if 'omr_z' in scores.columns else pd.Series(dtype=float)
        omr_saturation_pct = float(((omr_series.abs() >= clip_z).mean() * 100.0) if len(omr_series) else 0.0)

        ts_series = pd.Series(ts_local, index=scores.index)
        regime_markers: List[Tuple[pd.Timestamp, Any]] = []
        if 'regime_label' in scores.columns:
            regime_series = scores['regime_label']
            if regime_series.notna().any():
                transitions = regime_series[regime_series != regime_series.shift()].dropna()
                for idx, regime_val in transitions.items():
                    ts_val = ts_series.get(idx, None)
                    if ts_val is not None and not pd.isna(ts_val):
                        regime_markers.append((pd.to_datetime(ts_val), regime_val))

        drift_events_df = self._generate_drift_events(scores) if hasattr(self, '_generate_drift_events') else pd.DataFrame()
        episode_id_col = next((c for c in ('episode_id', 'EpisodeID', 'EpisodeId') if c in episodes.columns), None)

        health_cfg = (cfg.get('regimes', {}) or {}).get('health', {})
        warn_z = float(health_cfg.get('fused_warn_z', 1.5) or 1.5)
        alert_z = float(health_cfg.get('fused_alert_z', 3.0) or 3.0)

        # OUT-14: Chart preconditions check helper
        def _can_render(chart_name: str, condition: bool, reason: str = "") -> bool:
            """Check if chart should be rendered and log decision."""
            if condition:
                chart_log.append({
                    'chart_name': chart_name,
                    'status': 'rendered',
                    'reason': '',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                return True
            else:
                chart_log.append({
                    'chart_name': chart_name,
                    'status': 'skipped',
                    'reason': reason,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                Console.info(f"[CHARTS] Skipped {chart_name}: {reason}")
                return False
        
        def _safe_save(fig_obj, name: str) -> None:
            try:
                out = charts_path / name
                fig_obj.savefig(out, dpi=150)
                generated.append(out)
            except Exception as save_exc:
                Console.warn(f"[CHARTS] Failed to save {name}: {save_exc}")
            finally:
                plt.close(fig_obj)

        # contribution_bars.png
        try:
            # OUT-14: Check preconditions before rendering
            if _can_render('contribution_bars.png', 
                          bool(detector_cols), 
                          "No detector columns available"):
                contrib_df = self._generate_contrib_now(scores)
                if not contrib_df.empty and contrib_df.iloc[0, 0] != 'No detectors':
                    fig, ax = plt.subplots(figsize=(8, 4.5))
                    ax.barh(contrib_df['DetectorType'], contrib_df['ContributionPct'], color='#0ea5e9')
                    ax.set_xlabel('Contribution (%)')
                    ax.set_title('Detector Contribution Snapshot')
                    ax.set_xlim(0, max(100.0, float(contrib_df['ContributionPct'].max()) + 5))
                    ax.grid(axis='x', alpha=0.3, linestyle='--', linewidth=0.5)
                    ax.invert_yaxis()
                    fig.tight_layout()
                    _safe_save(fig, 'contribution_bars.png')
                else:
                    chart_log[-1]['status'] = 'skipped'
                    chart_log[-1]['reason'] = 'Empty contribution data'
        except Exception as exc:
            Console.warn(f"[CHARTS] contribution_bars failed: {exc}")

        # defect_dashboard.png
        try:
            fig, ax = plt.subplots(figsize=(10, 4.5))
            ax.axis('off')
            total_points = len(scores)
            total_episodes = len(episodes)
            max_fused = float(pd.to_numeric(fused_series, errors='coerce').max()) if not fused_series.empty else float('nan')
            recent = float(pd.to_numeric(fused_series.iloc[-1], errors='coerce')) if len(fused_series) else float('nan')
            durations = []
            if start_col and end_col:
                durations = (episodes[end_col] - episodes[start_col]).dt.total_seconds().dropna() / 3600.0
            anomaly_pct = float((np.abs(fused_series) > warn_z).mean()) * 100 if len(fused_series) else 0.0
            avg_hours = np.mean(durations) if len(durations) else float('nan')
            lines = [
                f"Total points        : {total_points:,}",
                f"Episodes detected    : {total_episodes:,}",
                f"Current fused z      : {recent:.2f}" if not np.isnan(recent) else "Current fused z      : N/A",
                f"Max fused z          : {max_fused:.2f}" if not np.isnan(max_fused) else "Max fused z          : N/A",
                f"Pct above warn ({warn_z:.2f}) : {anomaly_pct:.1f}%",
                f"Avg episode hours    : {avg_hours:.1f}" if not np.isnan(avg_hours) else "Avg episode hours    : N/A"
            ]
            ax.text(0.05, 0.95, '\n'.join(lines), fontsize=12, va='top', fontfamily='monospace')
            ax.set_title('Defect Overview Dashboard', loc='left', fontsize=14, fontweight='bold')
            _safe_save(fig, 'defect_dashboard.png')
        except Exception as exc:
            Console.warn(f"[CHARTS] defect_dashboard failed: {exc}")

        # defect_severity.png
        try:
            # OUT-14: Check preconditions before rendering
            has_severity = severity_col is not None and not episodes.empty
            if _can_render('defect_severity.png',
                          has_severity,
                          "No episodes with severity information"):
                # OUT-30: Map severity levels to categorical order for proper visualization
                severity_order = ['low', 'medium', 'high', 'critical', 'info', 'warn', 'alert']
                episodes_with_sev = episodes[episodes[severity_col].notna()].copy()
                episodes_with_sev['severity_lower'] = episodes_with_sev[severity_col].astype(str).str.lower()
                
                counts = episodes_with_sev['severity_lower'].value_counts()
                if not counts.empty:
                    # Order by severity_order if matches, otherwise alphabetical
                    ordered_sevs = [s for s in severity_order if s in counts.index]
                    other_sevs = sorted([s for s in counts.index if s not in severity_order])
                    all_sevs = ordered_sevs + other_sevs
                    ordered_counts = counts[all_sevs]
                    
                    # Color map: low=green, medium=yellow, high=orange, critical=red
                    color_map = {
                        'low': '#10b981', 'medium': '#fbbf24', 'high': '#f97316', 
                        'critical': '#dc2626', 'info': '#3b82f6', 'warn': '#f59e0b', 'alert': '#ef4444'
                    }
                    colors = [color_map.get(s, '#6b7280') for s in ordered_counts.index]
                    
                    fig, ax = plt.subplots(figsize=(8, max(4, len(ordered_counts) * 0.4)))
                    ax.barh(range(len(ordered_counts)), ordered_counts.values, color=colors)
                    ax.set_yticks(range(len(ordered_counts)))
                    ax.set_yticklabels(ordered_counts.index)
                    ax.set_xlabel('Episode Count', fontweight='bold')
                    ax.set_title('Episodes by Severity (see episodes.csv, episode_metrics.csv)', fontweight='bold', pad=10)
                    ax.grid(axis='x', alpha=0.3)
                    fig.tight_layout()
                    _safe_save(fig, 'defect_severity.png')
        except Exception as exc:
            Console.warn(f"[CHARTS] defect_severity failed: {exc}")

        # detector_comparison.png
        try:
            if detector_cols and len(ts_local):
                detector_stats = scores[detector_cols].std().abs().sort_values(ascending=False)
                top_detectors = detector_stats.index[:4].tolist()
                if top_detectors:
                    step = max(1, len(scores) // 2000)
                    fig, ax = plt.subplots(figsize=(11, 4))
                    for col in top_detectors:
                        series = pd.to_numeric(scores[col], errors='coerce').iloc[::step]
                        base_name = col.replace('_z', '')
                        weight = fusion_weights.get(base_name, fusion_weights.get(col, None))
                        pretty_name = base_name.upper() if len(base_name) <= 5 else base_name.replace('_', ' ').title()
                        label = pretty_name
                        if weight is not None:
                            try:
                                label = f"{pretty_name} (w={float(weight):.2f})"
                            except Exception:
                                label = f"{pretty_name} (w={weight})"
                        color = '#b91c1c' if col == 'omr_z' else None
                        ax.plot(ts_local[::step], series, label=label, linewidth=1.2, color=color)
                    ax.set_title('Detector Comparison (see calibration_summary.csv, detector_correlation.csv)')
                    ax.set_ylabel('Z-Score')
                    ax.legend(loc='upper right')
                    ax.grid(alpha=0.3, linestyle='--', linewidth=0.5)
                    ax.axhline(10, color='red', linestyle='--', alpha=0.3, linewidth=1)
                    ax.axhline(-10, color='red', linestyle='--', alpha=0.3, linewidth=1)
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M'))
                    if omr_saturation_pct >= 30.0:
                        warning_text = f"OMR saturation {omr_saturation_pct:.1f}% >= 30% (clip +/-{clip_z:g})"
                        ax.text(
                            0.01,
                            1.05,
                            warning_text,
                            transform=ax.transAxes,
                            fontsize=10,
                            fontweight='bold',
                            color='#b91c1c',
                            ha='left',
                            va='bottom',
                            bbox=dict(boxstyle='round,pad=0.35', facecolor='#fee2e2', edgecolor='#b91c1c', alpha=0.8)
                        )
                    fig.tight_layout()
                    _safe_save(fig, 'detector_comparison.png')
        except Exception as exc:
            Console.warn(f"[CHARTS] detector_comparison failed: {exc}")

        # sensor_values_timeline.png - Raw sensor values for top culprits
        try:
            # OUT-14: Check preconditions before rendering
            has_sensor_data = sensor_values is not None and not sensor_values.empty and len(ts_local) > 0
            if _can_render('sensor_values_timeline.png',
                          has_sensor_data,
                          "No sensor data available"):
                # Get top 5 sensors by maximum absolute z-score
                if sensor_abs_z is not None and not sensor_abs_z.empty:
                    sensor_max_z = sensor_abs_z.max().sort_values(ascending=False)
                    top_sensors = sensor_max_z.index[:5].tolist()
                else:
                    # Fallback: use sensors with highest variance
                    sensor_std = sensor_values.std().abs().sort_values(ascending=False)
                    top_sensors = sensor_std.index[:5].tolist()
                
                if top_sensors:
                    step = max(1, len(sensor_values) // 2000)
                    fig, ax = plt.subplots(figsize=(11, 5))
                    
                    # Plot each sensor on normalized scale (0-1) for visibility
                    for col in top_sensors:
                        if col in sensor_values.columns:
                            series = pd.to_numeric(sensor_values[col], errors='coerce').iloc[::step]
                            # Normalize to 0-1 scale for comparison
                            min_val = series.min()
                            max_val = series.max()
                            if max_val > min_val:
                                normalized = (series - min_val) / (max_val - min_val)
                                # Clean up sensor name for legend
                                label = col.replace('_med', '').replace('DEMO.SIM.', '')
                                ax.plot(ts_local[::step], normalized, label=label, alpha=0.8, linewidth=1.2)
                    
                    ax.set_title('Top 5 Sensor Values (Normalized 0-1)', fontsize=12, fontweight='bold')
                    ax.set_ylabel('Normalized Value', fontsize=10)
                    ax.set_xlabel('Timestamp', fontsize=10)
                    ax.set_ylim(-0.05, 1.05)
                    ax.legend(loc='upper left', fontsize=8, framealpha=0.9)
                    ax.grid(alpha=0.3, linestyle='--', linewidth=0.5)
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M'))
                    
                    # Add episode overlays if available (CHART-12: severity-based colors)
                    if start_col and end_col and len(episodes) > 0:
                        for idx, row in episodes.iterrows():
                            start_ts = row.get(start_col)
                            end_ts = row.get(end_col)
                            severity = str(row.get('severity', 'HIGH')).upper()
                            color = SEVERITY_COLORS.get(severity, SEVERITY_COLORS['HIGH'])
                            
                            if pd.notna(start_ts) and pd.notna(end_ts):
                                if not isinstance(start_ts, pd.Timestamp):
                                    start_ts = pd.to_datetime(start_ts, errors='coerce')
                                if not isinstance(end_ts, pd.Timestamp):
                                    end_ts = pd.to_datetime(end_ts, errors='coerce')
                                if pd.notna(start_ts) and pd.notna(end_ts):
                                    ax.axvspan(start_ts, end_ts, alpha=0.15, color=color, label='Episode' if idx == 0 else '')
                    
                    fig.tight_layout()
                    _safe_save(fig, 'sensor_values_timeline.png')
        except Exception as exc:
            Console.warn(f"[CHARTS] sensor_values_timeline failed: {exc}")

        # episodes_timeline.png
        try:
            if start_col and end_col and len(episodes) > 0:
                fig, ax = plt.subplots(figsize=(10, 4))
                severity_palette = {
                    'critical': '#7f1d1d',
                    'high': '#b91c1c',
                    'medium': '#f97316',
                    'info': '#38bdf8',
                    'low': '#cbd5f5'
                }
                plotted = 0
                yt_labels: List[str] = []
                for _, row in episodes.iterrows():
                    start_ts = row.get(start_col)
                    end_ts = row.get(end_col)
                    if pd.isna(start_ts) or pd.isna(end_ts):
                        continue
                    if not isinstance(start_ts, pd.Timestamp):
                        start_ts = pd.to_datetime(start_ts, errors='coerce')
                    if not isinstance(end_ts, pd.Timestamp):
                        end_ts = pd.to_datetime(end_ts, errors='coerce')
                    if pd.isna(start_ts) or pd.isna(end_ts):
                        continue
                    sev = str(row.get(severity_col, 'info')).lower() if severity_col else 'info'
                    y_level = plotted
                    color = severity_palette.get(sev, '#94a3b8')
                    ax.plot([start_ts, end_ts], [y_level, y_level], color=color, linewidth=8, alpha=0.8)
                    if episode_id_col:
                        ep_val = row.get(episode_id_col)
                        if pd.notna(ep_val):
                            try:
                                ep_int = int(ep_val)
                                label = f"EP-{ep_int:03d}"
                            except Exception:
                                label = f"EP-{ep_val}"
                        else:
                            label = f"EP-{y_level + 1}"
                    else:
                        label = f"EP-{y_level + 1}"
                    if severity_col:
                        label = f"{label} / {sev.upper()}"
                    yt_labels.append(label)
                    # Place annotation at the midpoint for quick scanning
                    try:
                        midpoint = start_ts + (end_ts - start_ts) / 2
                        ax.text(midpoint, y_level + 0.12, label, ha='center', va='bottom', fontsize=8, color='#1e3a8a')
                    except Exception:
                        pass
                    plotted += 1
                if plotted > 0:
                    ax.set_title('Episodes Timeline (see episodes.csv, episode_diagnostics.csv)')
                    ax.set_xlabel('Timestamp')
                    ax.set_ylabel('Episode')
                    ax.set_ylim(-0.5, max(plotted - 0.5, 0.5))
                    ax.set_yticks(range(plotted))
                    ax.set_yticklabels(yt_labels)
                    ax.grid(alpha=0.2, linestyle='--', linewidth=0.4)
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M'))
                    fig.tight_layout()
                    _safe_save(fig, 'episodes_timeline.png')
                else:
                    plt.close(fig)
        except Exception as exc:
            Console.warn(f"[CHARTS] episodes_timeline failed: {exc}")

        # health_distribution_over_time.png
        try:
            if len(ts_local) and 'fused' in scores.columns:
                tmp = pd.DataFrame({'timestamp': ts_local, 'fused': fused_series})
                tmp['date'] = tmp['timestamp'].dt.date
                tmp['hour'] = tmp['timestamp'].dt.hour
                heat = tmp.pivot_table(index='date', columns='hour', values='fused', aggfunc='mean')
                if not heat.empty:
                    fig, ax = plt.subplots(figsize=(11, 4.5))
                    im = ax.imshow(heat.values, aspect='auto', cmap='RdYlGn_r', vmin=-3, vmax=3)
                    ax.set_title('Health Distribution Over Time (mean fused z)')
                    ax.set_ylabel('Date')
                    ax.set_xlabel('Hour of day')
                    ax.set_xticks(range(len(heat.columns)))
                    ax.set_xticklabels([str(h) for h in heat.columns])
                    ax.set_yticks(range(len(heat.index)))
                    ax.set_yticklabels([str(d) for d in heat.index])
                    fig.colorbar(im, ax=ax, label='Mean fused z')
                    fig.tight_layout()
                    _safe_save(fig, 'health_distribution_over_time.png')
        except Exception as exc:
            Console.warn(f"[CHARTS] health_distribution_over_time failed: {exc}")

        # health_timeline.png
        try:
            # OUT-14: Check preconditions before rendering
            has_fused_data = len(ts_local) > 0 and 'fused' in scores.columns and not fused_series.empty
            if _can_render('health_timeline.png',
                          has_fused_data,
                          "No fused anomaly scores available"):
                health_idx = _health_index(fused_series)
                fig, ax = plt.subplots(figsize=(11, 4))
                ax.plot(ts_local, health_idx, color='#2563eb', linewidth=1.6, label='Health Index')
                ax.axhline(AnalyticsConstants.HEALTH_ALERT_THRESHOLD, color='#dc2626', linestyle='--', linewidth=1.0, alpha=0.7, label='Alert threshold')
                ax.axhline(AnalyticsConstants.HEALTH_WATCH_THRESHOLD, color='#f59e0b', linestyle='--', linewidth=1.0, alpha=0.7, label='Watch threshold')
                ax.set_ylim(0, 100)
                ax.set_ylabel('Health Index')
                ax.set_title('Health Timeline (see health_timeline.csv)')
                ax.grid(alpha=0.3, linestyle='--', linewidth=0.5)
                episode_span_added = False
                if start_col and end_col and len(episodes) > 0:
                    for _, row in episodes.iterrows():
                        start_ts = row.get(start_col)
                        end_ts = row.get(end_col)
                        if pd.isna(start_ts) or pd.isna(end_ts):
                            continue
                        if not isinstance(start_ts, pd.Timestamp):
                            start_ts = pd.to_datetime(start_ts, errors='coerce')
                        if not isinstance(end_ts, pd.Timestamp):
                            end_ts = pd.to_datetime(end_ts, errors='coerce')
                        if pd.isna(start_ts) or pd.isna(end_ts):
                            continue
                        sev = str(row.get(severity_col, 'HIGH')).upper() if severity_col else 'HIGH'
                        color = SEVERITY_COLORS.get(sev, '#f97316')
                        label = 'Episode window' if not episode_span_added else ''
                        ax.axvspan(start_ts, end_ts, color=color, alpha=0.08, label=label)
                        episode_span_added = True

                if regime_markers:
                    y_min, y_max = ax.get_ylim()
                    first_ts, first_regime = regime_markers[0]
                    if pd.notna(first_ts):
                        try:
                            ax.text(first_ts, y_max * 0.98, f"R{first_regime}", fontsize=8, color='#475569', ha='left', va='top')
                        except Exception:
                            pass
                    for ts_marker, regime_val in regime_markers[1:]:
                        if pd.isna(ts_marker):
                            continue
                        try:
                            ax.axvline(ts_marker, color='#94a3b8', linestyle=':', linewidth=0.9, alpha=0.6, label='Regime change')
                            ax.text(ts_marker, y_max * 0.98, f"R{regime_val}", rotation=90, fontsize=8, color='#475569', ha='right', va='top')
                        except Exception:
                            continue

                if not drift_events_df.empty:
                    y_min, y_max = ax.get_ylim()
                    drift_label_added = False
                    for _, event in drift_events_df.iterrows():
                        start_ts = pd.to_datetime(event.get('SegmentStart')) if event.get('SegmentStart') is not None else None
                        end_ts = pd.to_datetime(event.get('SegmentEnd')) if event.get('SegmentEnd') is not None else None
                        peak_ts = pd.to_datetime(event.get('Timestamp')) if event.get('Timestamp') is not None else start_ts
                        if start_ts is None or pd.isna(start_ts) or end_ts is None or pd.isna(end_ts):
                            continue
                        label = 'Drift segment' if not drift_label_added else ''
                        ax.axvspan(start_ts, end_ts, color='#fde68a', alpha=0.18, label=label)
                        drift_label_added = True
                        try:
                            drift_value = float(event.get('Value', 0.0))
                        except Exception:
                            drift_value = 0.0
                        if peak_ts is not None and not pd.isna(peak_ts):
                            annotate_y = max(y_min + (y_max - y_min) * 0.05, 5)
                            ax.annotate(
                                f"Drift {drift_value:.1f} sigma",
                                xy=(peak_ts, annotate_y),
                                xytext=(0, 18),
                                textcoords='offset points',
                                fontsize=8,
                                color='#b45309',
                                arrowprops=dict(arrowstyle='->', color='#b45309', lw=0.8)
                            )

                handles, labels = ax.get_legend_handles_labels()
                if labels:
                    unique = {}
                    for handle, label in zip(handles, labels):
                        if label and label not in unique:
                            unique[label] = handle
                    ax.legend(unique.values(), unique.keys(), loc='upper right')
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M'))
                fig.tight_layout()
                _safe_save(fig, 'health_timeline.png')
        except Exception as exc:
            Console.warn(f"[CHARTS] health_timeline failed: {exc}")

        # regime_distribution.png
        try:
            # OUT-14: Check preconditions before rendering
            has_regimes = 'regime_label' in scores.columns and scores['regime_label'].notna().any()
            if _can_render('regime_distribution.png',
                          has_regimes,
                          "No regime labels detected"):
                counts = scores['regime_label'].dropna().astype('Int64').value_counts().sort_index()
                if not counts.empty:
                    fig, ax = plt.subplots(figsize=(7, 4))
                    ax.bar(counts.index.astype(str), counts.values, color='#60a5fa')
                    # Extract regime info from sensor_context if available
                    regime_info = ""
                    if sensor_ctx and 'regime_meta' in sensor_ctx:
                        meta = sensor_ctx['regime_meta']
                        k = meta.get('best_k', len(counts))
                        score = meta.get('fit_score', 0.0)
                        metric = meta.get('fit_metric', 'unknown')
                        regime_info = f" (k={k}, {metric}={score:.3f})"
                    ax.set_title(f'Regime Distribution{regime_info} (see regime_timeline.csv)')
                    ax.set_xlabel('Regime label')
                    ax.set_ylabel('Count')
                    fig.tight_layout()
                    _safe_save(fig, 'regime_distribution.png')
        except Exception as exc:
            Console.warn(f"[CHARTS] regime_distribution failed: {exc}")

        # regime_scatter.png
        try:
            if 'regime_label' in scores.columns and len(ts_local):
                fig, ax = plt.subplots(figsize=(10, 4))
                scatter = ax.scatter(ts_local, fused_series, c=scores['regime_label'], cmap='tab20', s=12, alpha=0.7)
                # HIGH PRIORITY FIX: Surface clip_z in title
                ax.set_title('Fused Z by Regime (see regime_timeline.csv, regime_stability.csv)')
                ax.set_ylabel('Fused Z')
                ax.set_xlabel('Timestamp')
                # OUT-FIX-02: Cap y-axis to ±10 for z-score plots
                ax.set_ylim(-10, 10)
                ax.grid(alpha=0.2, linestyle='--', linewidth=0.4)
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M'))
                fig.colorbar(scatter, ax=ax, label='Regime label')
                fig.tight_layout()
                _safe_save(fig, 'regime_scatter.png')
        except Exception as exc:
            Console.warn(f"[CHARTS] regime_scatter failed: {exc}")

        # sensor_anomaly_heatmap.png
        try:
            if sensor_abs_z is not None and len(sensor_abs_z.columns):
                top_sensors = sensor_abs_z.max().sort_values(ascending=False).head(20).index.tolist()
                if top_sensors:
                    binary = (sensor_abs_z[top_sensors] > warn_z).astype(float)
                    if not binary.empty:
                        heat = binary.rolling(window=24, min_periods=1).mean()
                        step = max(1, len(heat) // 200) if len(heat) else 1
                        sample = heat.iloc[::step] if len(heat) else heat
                        if not sample.empty:
                            fig, ax = plt.subplots(figsize=(10, 5))
                            im = ax.imshow(sample.T, aspect='auto', cmap='Reds', vmin=0, vmax=1)
                            ax.set_title('Sensor Anomaly Heatmap (rolling proportion > warn)')
                            ax.set_xlabel('Sample index (windowed)')
                            ax.set_ylabel('Sensor')
                            ax.set_yticks(range(len(top_sensors)))
                            ax.set_yticklabels(top_sensors)
                            fig.colorbar(im, ax=ax, label='Proportion > warn')
                            fig.tight_layout()
                            _safe_save(fig, 'sensor_anomaly_heatmap.png')
            elif detector_cols:
                key_detectors = detector_cols[:20]
                binary = (scores[key_detectors].abs() > warn_z).astype(float)
                if not binary.empty:
                    heat = binary.rolling(window=24, min_periods=1).mean()
                    step = max(1, len(heat) // 200) if len(heat) else 1
                    sample = heat.iloc[::step] if len(heat) else heat
                    if not sample.empty:
                        fig, ax = plt.subplots(figsize=(10, 5))
                        im = ax.imshow(sample.T, aspect='auto', cmap='Reds', vmin=0, vmax=1)
                        ax.set_title('Detector Anomaly Heatmap (rolling proportion > warn)')
                        ax.set_xlabel('Sample index (windowed)')
                        ax.set_ylabel('Detector')
                        ax.set_yticks(range(len(key_detectors)))
                        ax.set_yticklabels(key_detectors)
                        fig.colorbar(im, ax=ax, label='Proportion > warn')
                        fig.tight_layout()
                        _safe_save(fig, 'sensor_anomaly_heatmap.png')
        except Exception as exc:
            Console.warn(f"[CHARTS] sensor_anomaly_heatmap failed: {exc}")

        # sensor_daily_profile.png
        try:
            if len(ts_local):
                tmp = pd.DataFrame({'timestamp': ts_local, 'fused': fused_series})
                tmp['hour'] = tmp['timestamp'].dt.hour
                profile = tmp.groupby('hour')['fused'].mean()
                if not profile.empty:
                    fig, ax = plt.subplots(figsize=(9, 4))
                    ax.plot(profile.index, profile.values, marker='o', color='#22c55e')
                    tick_step = max(1, int(np.ceil(len(profile) / 12)))
                    ax.set_xticks(profile.index[::tick_step])
                    ax.set_xlabel('Hour of day')
                    ax.set_ylabel('Mean fused z')
                    ax.set_title('Daily Fused Profile')
                    ax.grid(alpha=0.3, linestyle='--', linewidth=0.5)
                    fig.tight_layout()
                    _safe_save(fig, 'sensor_daily_profile.png')
        except Exception as exc:
            Console.warn(f"[CHARTS] sensor_daily_profile failed: {exc}")

        # sensor_defect_heatmap.png
        try:
            if not episodes.empty and 'culprits' in episodes.columns:
                # OUT-29: Filter out detector scores - only show real sensors
                detector_suffixes = ('_z', '_raw', '_score', '_flag', '_prob', '_anomaly')
                detector_names = ('gmm', 'pca_spe', 'iforest', 'mhal', 'cusum', 'omr', 'fused')
                
                counts: Dict[str, Dict[str, int]] = {}
                for _, row in episodes.iterrows():
                    sev = str(row.get(severity_col, 'info')).lower() if severity_col else 'info'
                    culprits = str(row.get('culprits') or '').split(',')
                    for culprit in culprits:
                        name = culprit.strip()
                        if not name:
                            continue
                        # OUT-29: Skip detector scores
                        name_lower = name.lower()
                        if any(name_lower.endswith(suffix) for suffix in detector_suffixes):
                            continue
                        if any(det in name_lower for det in detector_names):
                            continue
                        counts.setdefault(name, {})
                        counts[name][sev] = counts[name].get(sev, 0) + 1
                if counts:
                    severities = sorted({sev for val in counts.values() for sev in val.keys()})
                    sensors = sorted(counts.keys())
                    data = np.zeros((len(sensors), len(severities)))
                    for i, sensor in enumerate(sensors):
                        for j, sev in enumerate(severities):
                            data[i, j] = counts[sensor].get(sev, 0)
                    fig, ax = plt.subplots(figsize=(max(8, len(severities) * 1.5), max(4, len(sensors) * 0.3)))
                    im = ax.imshow(data, aspect='auto', cmap='OrRd')
                    ax.set_xticks(range(len(severities)))
                    ax.set_xticklabels(severities)
                    ax.set_yticks(range(len(sensors)))
                    ax.set_yticklabels(sensors)
                    ax.set_title('Sensor Defect Heatmap (severity counts)')
                    fig.colorbar(im, ax=ax, label='Count')
                    fig.tight_layout()
                    _safe_save(fig, 'sensor_defect_heatmap.png')
        except Exception as exc:
            Console.warn(f"[CHARTS] sensor_defect_heatmap failed: {exc}")

        # sensor_hotspots.png - DISABLED (redundant with heatmap, saves ~0.2s)
        # try:
        #     if sensor_zscores is not None and len(sensor_zscores.columns) and len(ts_local):
        #         top_sensors = sensor_abs_z.max().sort_values(ascending=False).head(4).index.tolist() if sensor_abs_z is not None else []
        #         if top_sensors:
        #             fig, ax = plt.subplots(figsize=(11, 4))
        #             step = max(1, len(sensor_zscores) // 2000)
        #             for sensor_name in top_sensors:
        #                 series = sensor_zscores[sensor_name].iloc[::step]
        #                 ax.plot(ts_local[::step], series, linewidth=1.1, label=sensor_name)
        #             ax.axhline(warn_z, color='#f97316', linestyle='--', linewidth=1.0, alpha=0.7, label=f'Warn {warn_z:.1f}')
        #             if alert_z > warn_z:
        #                 ax.axhline(alert_z, color='#b91c1c', linestyle='--', linewidth=1.0, alpha=0.7, label=f'Alert {alert_z:.1f}')
        #             if start_col and end_col:
        #                 for _, row in episodes.iterrows():
        #                     start_ts = row.get(start_col)
        #                     end_ts = row.get(end_col)
        #                     if pd.isna(start_ts) or pd.isna(end_ts):
        #                         continue
        #                     sev = str(row.get(severity_col, 'info')).lower() if severity_col else 'info'
        #                     color = {'critical': '#7f1d1d', 'high': '#b91c1c', 'medium': '#f97316', 'info': '#38bdf8', 'low': '#fde68a'}.get(sev, '#cbd5f5')
        #                     ax.axvspan(start_ts, end_ts, color=color, alpha=0.12)
        #             ax.set_title('Top Sensor Z-Scores')
        #             ax.set_ylabel('Sensor Z')
        #             ax.set_xlabel('Timestamp')
        #             ax.legend(loc='upper left')
        #             ax.grid(alpha=0.3, linestyle='--', linewidth=0.5)
        #             ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M'))
        #             fig.tight_layout()
        #             _safe_save(fig, 'sensor_hotspots.png')
        # except Exception as exc:
        #     Console.warn(f"[CHARTS] sensor_hotspots failed: {exc}")

        # sensor_sparklines.png - DISABLED (too small to read, saves ~0.2s)
        # try:
        #     if sensor_zscores is not None and len(sensor_zscores.columns) and len(ts_local):
        #         variability = sensor_abs_z.max().sort_values(ascending=False) if sensor_abs_z is not None else pd.Series(dtype=float)
        #         top_cols = variability.index[:6].tolist()
        #         n_cols = len(top_cols)
        #         if n_cols:
        #             cols_per_row = 3
        #             n_rows = int(np.ceil(n_cols / cols_per_row))
        #             fig, axes = plt.subplots(n_rows, cols_per_row, figsize=(cols_per_row * 4, n_rows * 2.2), sharex=True)
        #             axes = np.atleast_2d(axes)
        #             step = max(1, len(sensor_zscores) // 1000)
        #             for idx, col in enumerate(top_cols):
        #                 r, c = divmod(idx, cols_per_row)
        #                 ax = axes[r, c]
        #                 series = sensor_zscores[col].iloc[::step]
        #                 ax.plot(ts_local[::step], series, color='#3b82f6', linewidth=0.9)
        #                 ax.axhline(0, color='#9ca3af', linewidth=0.6)
        #                 ax.set_title(col)
        #                 ax.grid(alpha=0.2, linestyle='--', linewidth=0.4)
        #             for idx in range(n_cols, n_rows * cols_per_row):
        #                 r, c = divmod(idx, cols_per_row)
        #                 axes[r, c].axis('off')
        #             fig.autofmt_xdate()
        #             fig.tight_layout()
        #             _safe_save(fig, 'sensor_sparklines.png')
        #     elif detector_cols and len(ts_local):
        #         det_stats = scores[detector_cols].std().abs().sort_values(ascending=False)
        #         top_cols = det_stats.index[:6].tolist()
        #         n_cols = len(top_cols)
        #         if n_cols:
        #             cols_per_row = 3
        #             n_rows = int(np.ceil(n_cols / cols_per_row))
        #             fig, axes = plt.subplots(n_rows, cols_per_row, figsize=(cols_per_row * 4, n_rows * 2.2), sharex=True)
        #             axes = np.atleast_2d(axes)
        #             step = max(1, len(scores) // 1000)
        #             for idx, col in enumerate(top_cols):
        #                 r, c = divmod(idx, cols_per_row)
        #                 ax = axes[r, c]
        #                 series = pd.to_numeric(scores[col], errors='coerce').iloc[::step]
        #                 ax.plot(ts_local[::step], series, color='#3b82f6', linewidth=0.9)
        #                 ax.axhline(0, color='#9ca3af', linewidth=0.6)
        #                 ax.set_title(col)
        #                 ax.grid(alpha=0.2, linestyle='--', linewidth=0.4)
        #             for idx in range(n_cols, n_rows * cols_per_row):
        #                 r, c = divmod(idx, cols_per_row)
        #                 axes[r, c].axis('off')
        #             fig.autofmt_xdate()
        #             fig.tight_layout()
        #             _safe_save(fig, 'sensor_sparklines.png')
        # except Exception as exc:
        #     Console.warn(f"[CHARTS] sensor_sparklines failed: {exc}")

        # sensor_timeseries_events.png - DISABLED (slow, often unclear, saves ~0.5s)
        # try:
        #     if len(ts_local):
        #         fig, ax = plt.subplots(figsize=(11, 4))
        #         step = max(1, len(scores) // 4000)
        #         ax.plot(ts_local[::step], fused_series.iloc[::step], color='#ef4444', linewidth=1.2, label='Fused z')
        #         ax.axhline(warn_z, color='#f97316', linestyle='--', linewidth=1.0, alpha=0.7, label=f'Warn {warn_z:.1f}')
        #         ax.axhline(alert_z, color='#b91c1c', linestyle='--', linewidth=1.0, alpha=0.7, label=f'Alert {alert_z:.1f}')
        #         if start_col and end_col:
        #             for _, row in episodes.iterrows():
        #                 start_ts = row.get(start_col)
        #                 end_ts = row.get(end_col)
        #                 if pd.isna(start_ts) or pd.isna(end_ts):
        #                     continue
        #                 sev = str(row.get(severity_col, 'info')).lower() if severity_col else 'info'
        #                 color = {'critical': '#7f1d1d', 'high': '#b91c1c', 'medium': '#f97316', 'info': '#38bdf8', 'low': '#fde68a'}.get(sev, '#cbd5f5')
        #                 ax.axvspan(start_ts, end_ts, color=color, alpha=0.18)
        #         ax.set_title('Fused Timeseries with Episodes')
        #         ax.set_ylabel('Fused Z')
        #         ax.set_xlabel('Timestamp')
        #         ax.legend(loc='upper left')
        #         ax.grid(alpha=0.3, linestyle='--', linewidth=0.5)
        #         ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M'))
        #         fig.tight_layout()
        #         _safe_save(fig, 'sensor_timeseries_events.png')
        # except Exception as exc:
        #     Console.warn(f"[CHARTS] sensor_timeseries_events failed: {exc}")

        # === OMR CHARTS (OMR-04) ===
        # Add 3 OMR visualization charts if OMR detector is active
        # CHART-03: Skip OMR charts if fusion weight < 0.05 (detector effectively disabled)
        # OUT-15: Fallback to config weight when fusion_metrics.csv missing
        try:
            omr_col = next((c for c in scores.columns if 'omr' in c.lower() and 'z' in c.lower()), None)
            
            # Check OMR fusion weight before generating charts
            omr_weight = 0.0
            weight_source = "default"
            fusion_metrics_path = charts_path.parent / "tables" / "fusion_metrics.csv"
            if fusion_metrics_path.exists():
                try:
                    fusion_df = pd.read_csv(fusion_metrics_path)
                    omr_row = fusion_df[fusion_df['detector_name'].str.contains('omr', case=False, na=False)]
                    if not omr_row.empty:
                        omr_weight = float(omr_row.iloc[0]['weight'])
                        weight_source = "fusion_metrics"
                except Exception as e:
                    Console.warn(f"[CHARTS] Could not read OMR weight from fusion_metrics: {e}")
            
            # OUT-15 & CHART-03: Fallback to config weight if metrics file missing/failed
            if omr_weight == 0.0 and cfg:
                config_weight = cfg.get("fusion", {}).get("weights", {}).get("omr_z", 0.0)
                if config_weight > 0:
                    omr_weight = float(config_weight)
                    weight_source = "config"
                    Console.info(f"[CHARTS] OMR weight from config: {omr_weight:.4f} (source: {weight_source})")
            
            # CHART-03: Skip OMR charts if weight too low
            if omr_weight < 0.05:
                skip_reason = f"OMR fusion weight={omr_weight:.4f} < 0.05 (detector disabled)"
                Console.info(f"[CHARTS] Skipping OMR charts: {skip_reason}")
                
                # Log skip for omr_timeline.png and omr_contributions.png
                for omr_chart in ['omr_timeline.png', 'omr_contributions.png']:
                    chart_log.append({
                        'chart_name': omr_chart,
                        'status': 'skipped',
                        'reason': skip_reason,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                
                omr_col = None  # Force skip by clearing omr_col
            
            if omr_col:
                import seaborn as sns
                
                # 1. OMR Timeline (z-score with thresholds)
                try:
                    fig, ax = plt.subplots(figsize=(14, 6))
                    omr_series = pd.to_numeric(scores[omr_col], errors='coerce')
                    ax.plot(ts_local, omr_series, color='#2E86AB', linewidth=1.5, label='OMR Z-Score', alpha=0.8)
                    
                    # Threshold lines based on health config (HIGH PRIORITY FIX)
                    # Use regime health configuration for warn/alert thresholds
                    thresholds = [warn_z, alert_z, 10.0]
                    colors = ['#f59e0b', '#dc2626', '#7f1d1d']
                    labels = [f'Watch ({warn_z:.1f}σ)', f'Alert ({alert_z:.1f}σ)', 'Critical (10σ)']
                    for thresh, color, label in zip(thresholds, colors, labels):
                        ax.axhline(y=thresh, color=color, linestyle='--', linewidth=1, alpha=0.6, label=label)
                    
                    # Mark episodes with proper datetime conversion (CHART-12: severity-based colors)
                    if start_col and end_col:
                        for idx, row in episodes.iterrows():
                            start_ts = row.get(start_col)
                            end_ts = row.get(end_col)
                            severity = str(row.get('severity', 'HIGH')).upper()
                            color = SEVERITY_COLORS.get(severity, SEVERITY_COLORS['HIGH'])
                            
                            if pd.isna(start_ts) or pd.isna(end_ts):
                                continue
                            # Ensure datetime objects for axvspan
                            if not isinstance(start_ts, pd.Timestamp):
                                start_ts = pd.to_datetime(start_ts, errors='coerce')
                            if not isinstance(end_ts, pd.Timestamp):
                                end_ts = pd.to_datetime(end_ts, errors='coerce')
                            if pd.notna(start_ts) and pd.notna(end_ts):
                                ax.axvspan(start_ts, end_ts, alpha=0.2, color=color, label='Episode' if idx == 0 else '')
                    
                    ax.set_xlabel('Time', fontsize=11, fontweight='bold')
                    ax.set_ylabel('OMR Z-Score (σ)', fontsize=11, fontweight='bold')
                    # HIGH PRIORITY FIX: Surface clip_z in title so operators know saturation point
                    ax.set_title('Overall Model Residual Timeline (clipped to ±10σ)', fontsize=13, fontweight='bold', pad=15)
                    # OUT-FIX-02: Cap y-axis to ±10 for z-score interpretability
                    ax.set_ylim(-10, 10)
                    ax.grid(True, alpha=0.3, linestyle='--')
                    ax.legend(loc='upper right', framealpha=0.95, fontsize=9)
                    # MEDIUM PRIORITY FIX: Use AutoDateLocator to prevent tick collisions
                    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=10))
                    ax.xaxis.set_major_formatter(mdates.DateFormatter(CHART_DATE_FORMAT))
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
                    fig.tight_layout()
                    _safe_save(fig, 'omr_timeline.png')
                except Exception as exc:
                    Console.warn(f"[CHARTS] omr_timeline failed: {exc}")
                
                # 2. OMR Contribution Heatmap (if omr_contributions available in sensor_context)
                try:
                    omr_contribs = sensor_ctx.get('omr_contributions')
                    if omr_contribs is not None and isinstance(omr_contribs, pd.DataFrame) and len(omr_contribs) > 0:
                        df = omr_contribs.copy()
                        
                        # Ensure datetime index
                        if not isinstance(df.index, pd.DatetimeIndex):
                            if 'timestamp' in df.columns:
                                df['timestamp'] = pd.to_datetime(df['timestamp'])
                                df = df.set_index('timestamp')
                            elif 'TS' in df.columns:
                                df['TS'] = pd.to_datetime(df['TS'])
                                df = df.set_index('TS')
                        
                        # Get numeric columns
                        numeric_cols = df.select_dtypes(include=[np.number]).columns
                        df = df[numeric_cols]
                        
                        if len(df.columns) > 0:
                            # Find top contributors
                            total_contributions = df.sum().sort_values(ascending=False)
                            top_sensors = total_contributions.head(15).index.tolist()
                            df_top = df[top_sensors]
                            
                            # Downsample for readability
                            if len(df_top) > 100:
                                step = len(df_top) // 100
                                df_top = df_top.iloc[::step]
                            
                            # OUT-FIX-01: Normalize each sensor column by its std dev to unit variance
                            # This shows relative contribution patterns, not absolute magnitude
                            sensor_stds = df_top.std(axis=0)
                            sensor_stds = sensor_stds.replace(0, 1.0)  # Prevent division by zero
                            df_norm = df_top / sensor_stds
                            
                            fig, ax = plt.subplots(figsize=(14, 8))
                            sns.heatmap(df_norm.T, cmap='YlOrRd', ax=ax, cbar_kws={'label': 'Normalized Contribution'}, 
                                       linewidths=0.5, linecolor='white')
                            ax.set_xlabel('Time', fontsize=11, fontweight='bold')
                            ax.set_ylabel('Sensor', fontsize=11, fontweight='bold')
                            ax.set_title('OMR Sensor Contribution Heatmap (Top 15)', fontsize=13, fontweight='bold', pad=15)
                            
                            # Format x-axis labels (show fewer timestamps)
                            n_ticks = min(10, len(df_top))
                            tick_positions = np.linspace(0, len(df_top)-1, n_ticks, dtype=int)
                            ax.set_xticks(tick_positions)
                            ax.set_xticklabels([df_top.index[i].strftime('%m-%d %H:%M') if isinstance(df_top.index[i], pd.Timestamp) else str(df_top.index[i]) for i in tick_positions], rotation=45, ha='right')
                            
                            fig.tight_layout()
                            _safe_save(fig, 'omr_contribution_heatmap.png')
                except Exception as exc:
                    Console.warn(f"[CHARTS] omr_contribution_heatmap failed: {exc}")
                
                # 3. Top Contributors Bar Chart (MEDIUM PRIORITY FIX: align with heatmap)
                try:
                    omr_contribs = sensor_ctx.get('omr_contributions')
                    if omr_contribs is not None and isinstance(omr_contribs, pd.DataFrame) and len(omr_contribs) > 0:
                        df = omr_contribs.copy()
                        numeric_cols = df.select_dtypes(include=[np.number]).columns
                        
                        if len(numeric_cols) > 0:
                            # Use same sensor set as heatmap (top 15) for consistency
                            total_contributions = df[numeric_cols].sum().sort_values(ascending=False).head(15)
                            
                            fig, ax = plt.subplots(figsize=(10, 8))
                            colors_map = plt.cm.YlOrRd(np.linspace(0.4, 0.9, len(total_contributions)))
                            bars = ax.barh(range(len(total_contributions)), total_contributions.values, color=colors_map, edgecolor='black', linewidth=0.5)
                            ax.set_yticks(range(len(total_contributions)))
                            ax.set_yticklabels(total_contributions.index)
                            ax.set_xlabel('Cumulative Contribution', fontsize=11, fontweight='bold')
                            ax.set_title('OMR Top 15 Contributing Sensors (matches heatmap)', fontsize=13, fontweight='bold', pad=15)
                            ax.invert_yaxis()
                            ax.grid(axis='x', alpha=0.3, linestyle='--')
                            
                            # Add value labels
                            for i, (bar, val) in enumerate(zip(bars, total_contributions.values)):
                                ax.text(val, i, f'  {val:.2e}', va='center', fontsize=9)
                            
                            fig.tight_layout()
                            _safe_save(fig, 'omr_top_contributors.png')
                except Exception as exc:
                    Console.warn(f"[CHARTS] omr_top_contributors failed: {exc}")
                    
        except Exception as exc:
            Console.warn(f"[CHARTS] OMR chart generation failed: {exc}")

        # OUT-14: Write chart generation log
        if chart_log:
            try:
                log_df = pd.DataFrame(chart_log)
                tables_dir = charts_path.parent / "tables"
                tables_dir.mkdir(parents=True, exist_ok=True)
                log_path = tables_dir / "chart_generation_log.csv"
                log_df.to_csv(log_path, index=False)
                
                rendered_count = len([c for c in chart_log if c['status'] == 'rendered'])
                skipped_count = len([c for c in chart_log if c['status'] == 'skipped'])
                Console.info(f"[CHARTS] Chart summary: {rendered_count} rendered, {skipped_count} skipped")
                
                # Log skip reasons breakdown
                if skipped_count > 0:
                    skip_reasons = {}
                    for entry in chart_log:
                        if entry['status'] == 'skipped':
                            reason = entry['reason'] or 'unknown'
                            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                    reason_str = ', '.join([f"{reason}={count}" for reason, count in skip_reasons.items()])
                    Console.info(f"[CHARTS] Skip breakdown: {reason_str}")
            except Exception as log_exc:
                Console.warn(f"[CHARTS] Failed to write chart_generation_log.csv: {log_exc}")
        
        # OUT-27: Derive count from registry for deterministic logging
        total_charts = len(chart_log)
        rendered_count = len([c for c in chart_log if c['status'] == 'rendered'])
        
        if generated:
            Console.info(f"[CHARTS] Generated {rendered_count}/{total_charts} chart(s) in {charts_path}")
        else:
            Console.warn('[CHARTS] No charts generated — check fused scores or detector outputs')

        return generated

    # ==================== INDIVIDUAL TABLE GENERATORS ====================
    
    def _safe_timestamp_format(self, timestamp_series):
        """Safely format timestamps; prefer vector ops."""
        s = pd.to_datetime(timestamp_series, errors='coerce')
        try:
            s = s.tz_convert(None)
        except Exception:
            s = s.tz_localize(None)
        return s.dt.strftime('%Y-%m-%d %H:%M:%S').fillna('N/A').tolist()
    
    def _safe_single_timestamp(self, timestamp):
        """Safely format a single timestamp."""
        try:
            if pd.isna(timestamp):
                return 'N/A'
            else:
                return timestamp.strftime('%Y-%m-%d %H:%M:%S')
        except (AttributeError, ValueError, TypeError):
            return str(timestamp)
    
    def _generate_schema_descriptor(self, tables_dir: Path) -> Dict[str, Any]:
        """
        Generate schema descriptor JSON for all CSV tables.
        
        OUT-20: Provides schema metadata for downstream consumers to validate
        column names, types, formats, and nullability.
        
        Returns:
            Dict with table_name -> schema info mapping
        """
        schema = {
            "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "tables": {}
        }
        
        # Scan all CSV files in tables directory
        csv_files = sorted(tables_dir.glob("*.csv"))
        
        for csv_path in csv_files:
            table_name = csv_path.stem
            try:
                # Read CSV and infer schema
                df = pd.read_csv(csv_path, nrows=100)  # Sample first 100 rows for efficiency
                
                # Build column info
                columns = []
                dtypes = {}
                nullable = []
                
                for col in df.columns:
                    col_type = str(df[col].dtype)
                    has_nulls = df[col].isna().any()
                    
                    columns.append(col)
                    dtypes[col] = col_type
                    nullable.append(col if has_nulls else None)
                
                # Remove None values from nullable list
                nullable = [col for col in nullable if col is not None]
                
                # Detect datetime format if Timestamp column exists
                datetime_format = None
                if 'Timestamp' in columns or 'timestamp' in columns:
                    datetime_format = '%Y-%m-%d %H:%M:%S'
                
                schema["tables"][table_name] = {
                    "columns": columns,
                    "dtypes": dtypes,
                    "datetime_format": datetime_format,
                    "nullable_columns": nullable,
                    "row_count_sampled": len(df)
                }
                
            except Exception as e:
                Console.warn(f"[SCHEMA] Failed to read schema for {table_name}: {e}")
                schema["tables"][table_name] = {"error": str(e)}
        
        return schema
    
    def _generate_episode_severity_mapping(self, episodes_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate episodes severity mapping JSON with counts and color palette.
        
        OUT-28: Provides severity level metadata for downstream consumers
        to understand severity distribution and rendering.
        
        Returns:
            Dict with severity levels, color mapping, and counts
        """
        # CHART-12: Use centralized severity color palette
        severity_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        color_map = SEVERITY_COLORS  # Centralized constant from top of file
        
        # Count episodes by severity
        counts = {}
        total_episodes = len(episodes_df)
        
        if 'severity' in episodes_df.columns:
            severity_counts = episodes_df['severity'].str.upper().value_counts().to_dict()
            for level in severity_levels:
                counts[level] = severity_counts.get(level, 0)
        else:
            # No severity column - all defaults
            for level in severity_levels:
                counts[level] = 0
        
        # Validate counts sum
        count_sum = sum(counts.values())
        validation_status = "VALID" if count_sum == total_episodes else "MISMATCH"
        
        return {
            "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "severity_levels": severity_levels,
            "color_map": color_map,
            "counts": counts,
            "total_episodes": total_episodes,
            "validation_status": validation_status,
            "count_sum": count_sum
        }

    def _generate_health_timeline(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate enhanced health timeline with zones."""
        health_index = _health_index(scores_df['fused'])
        zones = pd.cut(
            health_index,
            bins=[0, AnalyticsConstants.HEALTH_ALERT_THRESHOLD, AnalyticsConstants.HEALTH_WATCH_THRESHOLD, 100],
            labels=['ALERT', 'WATCH', 'GOOD']
        )
        ts_values = _to_naive_series(scores_df.index).to_list()
        return pd.DataFrame({
            'Timestamp': ts_values,
            'HealthIndex': health_index.round(2).to_list(),
            'HealthZone': zones.astype(str).to_list(),
            'FusedZ': scores_df['fused'].round(4).to_list()
        })
    
    def _generate_regime_timeline(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate regime timeline with confidence."""
        regimes = pd.to_numeric(scores_df['regime_label'], errors='coerce').astype('Int64')
        ts_values = _to_naive_series(scores_df.index).to_list()
        return pd.DataFrame({
            'Timestamp': ts_values,
            'RegimeLabel': regimes.to_list(),
            'RegimeState': scores_df.get('regime_state', 'unknown').astype(str).to_list()
        })
    
    def _generate_contrib_now(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate current sensor contributions."""
        # Get latest z-scores for detectors
        detector_cols = [c for c in scores_df.columns if c.endswith('_z') and c != 'fused_z']
        if not detector_cols:
            return pd.DataFrame({'DetectorType': ['No detectors'], 'ContributionPct': [0.0], 'ZScore': [0.0]})
        
        latest_scores = scores_df[detector_cols].iloc[-1].abs()
        total = latest_scores.sum()
        if total == 0:
            contributions = pd.Series([100.0 / len(detector_cols)] * len(detector_cols), index=detector_cols)
        else:
            contributions = (latest_scores / total * 100).round(2)
        
        return pd.DataFrame({
            'DetectorType': contributions.index,
            'ContributionPct': contributions.values,
            'ZScore': latest_scores.values
        }).sort_values('ContributionPct', ascending=False)
    
    def _generate_contrib_timeline(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate historical sensor contributions over time."""
        detector_cols = [c for c in scores_df.columns if c.endswith('_z') and c not in ('fused', 'fused_z')]
        if not detector_cols:
            return pd.DataFrame({'Timestamp': [], 'DetectorType': [], 'ContributionPct': []})

        # dynamic sampling to ~target points
        n = len(scores_df)
        step = max(1, n // AnalyticsConstants.TARGET_SAMPLING_POINTS)
        sampled = scores_df[detector_cols].iloc[::step].abs()

        totals = sampled.sum(axis=1)
        valid = totals > 0
        normalized = sampled[valid].div(totals[valid], axis=0) * 100

        tmp = normalized.reset_index()
        idx_col = tmp.columns[0]
        long_df = tmp.melt(id_vars=idx_col, var_name='DetectorType', value_name='ContributionPct')
        long_df.rename(columns={idx_col: 'Timestamp'}, inplace=True)
        long_df['Timestamp'] = _to_naive_series(long_df['Timestamp'])
        long_df['ContributionPct'] = long_df['ContributionPct'].round(2)
        return long_df[['Timestamp', 'DetectorType', 'ContributionPct']]
    
    def _generate_defect_summary(self, scores_df: pd.DataFrame, episodes_df: pd.DataFrame) -> pd.DataFrame:
        """Generate executive defect summary."""
        health_index = _health_index(scores_df['fused'])
        current_health = health_index.iloc[-1]
        avg_health = health_index.mean()
        min_health = health_index.min()
        
        # Determine status
        if current_health >= 85:
            status = "HEALTHY"
            severity = "LOW"
        elif current_health >= 70:
            status = "CAUTION"
            severity = "MEDIUM"
        else:
            status = "ALERT"
            severity = "HIGH"
        
        # Count episodes
        episode_count = len(episodes_df) if episodes_df is not None and not episodes_df.empty else 0
        
        # Find worst sensor
        detector_cols = [c for c in scores_df.columns if c.endswith('_z') and c != 'fused_z']
        if detector_cols:
            latest_scores = scores_df[detector_cols].iloc[-1].abs()
            worst_sensor = latest_scores.idxmax().replace('_z', '')
        else:
            worst_sensor = "Unknown"
        
        # Count health zones
        zones = pd.cut(health_index, bins=[0, 70, 85, 100], labels=['ALERT', 'WATCH', 'GOOD'])
        zone_counts = zones.value_counts()
        
        return pd.DataFrame({
            'Status': [status],
            'Severity': [severity], 
            'CurrentHealth': [round(current_health, 1)],
            'AvgHealth': [round(avg_health, 1)],
            'MinHealth': [round(min_health, 1)],
            'EpisodeCount': [episode_count],
            'WorstSensor': [worst_sensor],
            'GoodCount': [zone_counts.get('GOOD', 0)],
            'WatchCount': [zone_counts.get('WATCH', 0)],
            'AlertCount': [zone_counts.get('ALERT', 0)]
        })
    
    def _generate_defect_timeline(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate defect event timeline."""
        health_index = _health_index(scores_df['fused'])
        zones = pd.cut(health_index, bins=[0, 70, 85, 100], labels=['ALERT', 'WATCH', 'GOOD'])
        
        # Find zone transitions
        zone_changes = zones != zones.shift()
        transitions = []
        
        zones_shifted = zones.shift()
        
        for idx in scores_df[zone_changes].index:
            from_zone_val = zones_shifted.loc[idx]
            # Handle scalar value properly
            try:
                from_zone = str(from_zone_val) if not pd.isna(from_zone_val) else 'START'
            except (ValueError, TypeError):
                from_zone = 'START'

            # Use tz-naive UTC datetime for SQL compatibility
            ts_naive = _to_naive(idx)
            to_zone = str(zones.loc[idx])
            # FusedZ at this timestamp if available
            fused_val = None
            try:
                if 'fused' in scores_df.columns:
                    val = scores_df.loc[idx, 'fused']
                    fused_val = round(float(val), 4) if pd.notna(val) else 0.0
            except Exception:
                fused_val = 0.0

            transitions.append({
                'Timestamp': ts_naive,
                'EventType': 'ZONE_CHANGE',
                'FromZone': from_zone,
                'ToZone': to_zone,
                'HealthZone': to_zone,
                'HealthAtEvent': round(health_index.loc[idx], 2),
                'HealthIndex': round(health_index.loc[idx], 2),
                'FusedZ': fused_val if fused_val is not None else 0.0
            })
        
        return pd.DataFrame(transitions)
    
    def _generate_sensor_defects(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate per-sensor defect analysis."""
        detector_cols = [c for c in scores_df.columns if c.endswith('_z') and c != 'fused_z']
        defect_data = []
        
        for detector in detector_cols:
            # Defensive: validate detector column name
            if detector is None or (isinstance(detector, float) and pd.isna(detector)):
                Console.warn("[DEFECTS] Skipping NULL detector column name")
                continue
            detector_col = str(detector)
            channel_name = detector_col.replace('_z', '').strip() if detector_col else 'UNKNOWN'
            if not channel_name:
                channel_name = f"UNKNOWN_{detector_col[:10]}"
            family = channel_name.split('_')[0] if '_' in channel_name else channel_name

            # Safely access values; skip if column missing unexpectedly
            if detector not in scores_df.columns:
                Console.warn(f"[DEFECTS] Missing detector column: {detector}")
                continue
            values = pd.to_numeric(scores_df[detector], errors='coerce').abs()
            violations = values > 2.0
            violation_count = int(violations.sum())
            total_points = int(len(values)) if len(values) else 0
            violation_pct = (violation_count / total_points * 100) if total_points > 0 else 0.0
            
            # Determine severity
            if violation_pct > 20:
                severity = "CRITICAL"
            elif violation_pct > 10:
                severity = "HIGH"
            elif violation_pct > 5:
                severity = "MEDIUM"
            else:
                severity = "LOW"
            
            defect_data.append({
                'DetectorType': channel_name,
                'DetectorFamily': family,
                'Severity': severity,
                'ViolationCount': violation_count,
                'ViolationPct': round(violation_pct, 2),
                'MaxZ': round(float(values.max()) if len(values) else 0.0, 4),
                'AvgZ': round(float(values.mean()) if len(values) else 0.0, 4),
                'CurrentZ': round(float(values.iloc[-1]) if len(values) else 0.0, 4),
                'ActiveDefect': bool(violations.iloc[-1]) if len(violations) else False
            })
        
        return pd.DataFrame(defect_data).sort_values('ViolationPct', ascending=False)
    
    def _generate_health_zone_by_period(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate health zone distribution by time period (long format).
        Emits one row per period per zone with required HealthZone.
        """
        health_index = _health_index(scores_df['fused'])
        zones = pd.cut(health_index, bins=[0, 70, 85, 100], labels=['ALERT', 'WATCH', 'GOOD'])

        daily_zones = pd.DataFrame({'date': scores_df.index.date, 'zone': zones})
        zone_summary = daily_zones.groupby(['date', 'zone'], observed=False).size().unstack(fill_value=0)
        totals = zone_summary.sum(axis=1)

        rows = []
        for date, counts in zone_summary.iterrows():
            period_start = pd.Timestamp(date).to_pydatetime()
            total_points = int(totals.loc[date]) if date in totals.index else 0
            for hz in ['GOOD', 'WATCH', 'ALERT']:
                cnt = int(counts.get(hz, 0))
                pct = (cnt / total_points * 100.0) if total_points > 0 else 0.0
                rows.append({
                    'PeriodStart': period_start,
                    'PeriodType': 'DAY',
                    'HealthZone': hz,
                    'ZonePct': round(pct, 1),
                    'ZoneCount': cnt,
                    'TotalPoints': total_points,
                    'Date': str(date),  # CSV readability; SQL will ignore if no column
                })
        return pd.DataFrame(rows)
    
    def _generate_sensor_anomaly_by_period(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate per-sensor anomaly rates by time period."""
        detector_cols = [c for c in scores_df.columns if c.endswith('_z') and c != 'fused_z']
        results = []
        
        # Group by day
        daily_data = scores_df.groupby(scores_df.index.date)
        
        for date, day_data in daily_data:
            for detector in detector_cols:
                values = day_data[detector].abs()
                anomaly_rate = (values > 2.0).mean() * 100
                # PeriodStart: start of the day (tz-naive) to satisfy SQL NOT NULL
                period_start = pd.Timestamp(date).to_pydatetime()
                
                results.append({
                    'Date': str(date),  # For CSV readability
                    'PeriodStart': period_start,
                    'PeriodType': 'DAY',
                    'PeriodSeconds': 86400,
                    'DetectorType': detector.replace('_z', ''),
                    'AnomalyRatePct': round(anomaly_rate, 2),
                    'MaxZ': round(values.max(), 4),
                    'AvgZ': round(values.mean(), 4),
                    'Points': len(values)
                })
        
        return pd.DataFrame(results)

    def _generate_sensor_hotspots_table(
        self,
        sensor_zscores: pd.DataFrame,
        sensor_values: pd.DataFrame,
        train_mean: Optional[pd.Series],
        train_std: Optional[pd.Series],
        warn_z: float,
        alert_z: float,
        top_n: int
    ) -> pd.DataFrame:
        """Summarize top sensors by peak z-score deviation."""
        empty_schema = {
            'SensorName': [], 'MaxTimestamp': [], 'LatestTimestamp': [], 'MaxAbsZ': [],
            'MaxSignedZ': [], 'LatestAbsZ': [], 'LatestSignedZ': [], 'ValueAtPeak': [],
            'LatestValue': [], 'TrainMean': [], 'TrainStd': [], 'AboveWarnCount': [],
            'AboveAlertCount': []
        }

        if sensor_zscores is None or sensor_zscores.empty:
            return pd.DataFrame(empty_schema)

        records: List[Dict[str, Any]] = []
        for sensor in sensor_zscores.columns:
            series = sensor_zscores[sensor].dropna()
            if series.empty:
                continue
            abs_series = series.abs()
            max_idx = abs_series.idxmax()
            max_abs = float(abs_series.loc[max_idx])
            max_signed = float(series.loc[max_idx])
            latest_ts = series.index[-1]
            latest_signed = float(series.iloc[-1])
            latest_abs = abs(latest_signed)
            above_warn = int((abs_series >= warn_z).sum())
            above_alert = int((abs_series >= alert_z).sum()) if alert_z > 0 else 0

            value_at_peak = None
            latest_value = None
            if sensor in sensor_values.columns:
                try:
                    value_at_peak = sensor_values.loc[max_idx, sensor]
                except Exception:
                    value_at_peak = sensor_values[sensor].reindex([max_idx]).iloc[-1]
                try:
                    latest_value = sensor_values.loc[latest_ts, sensor]
                except Exception:
                    latest_value = sensor_values[sensor].iloc[-1]

            train_mean_val = float(train_mean.get(sensor)) if isinstance(train_mean, pd.Series) and sensor in train_mean.index else None
            train_std_val = float(train_std.get(sensor)) if isinstance(train_std, pd.Series) and sensor in train_std.index else None

            records.append({
                'SensorName': sensor,
                'MaxTimestamp': _to_naive(max_idx),
                'LatestTimestamp': _to_naive(latest_ts),
                'MaxAbsZ': round(max_abs, 4),
                'MaxSignedZ': round(max_signed, 4),
                'LatestAbsZ': round(latest_abs, 4),
                'LatestSignedZ': round(latest_signed, 4),
                'ValueAtPeak': float(value_at_peak) if value_at_peak is not None and pd.notna(value_at_peak) else None,
                'LatestValue': float(latest_value) if latest_value is not None and pd.notna(latest_value) else None,
                'TrainMean': train_mean_val,
                'TrainStd': train_std_val,
                'AboveWarnCount': above_warn,
                'AboveAlertCount': above_alert
            })

        if not records:
            return pd.DataFrame(empty_schema)

        df = pd.DataFrame(records)
        df = df[df['MaxAbsZ'] >= warn_z]
        if df.empty:
            return pd.DataFrame(empty_schema)
        df = df.sort_values('MaxAbsZ', ascending=False)
        if top_n > 0:
            df = df.head(top_n)
        return df.reset_index(drop=True)

    def _generate_sensor_hotspot_timeline(
        self,
        sensor_zscores: pd.DataFrame,
        sensor_values: Optional[pd.DataFrame],
        warn_z: float,
        alert_z: float,
        top_k: int = 3
    ) -> pd.DataFrame:
        """Produce timestamped rows for the strongest sensor deviations."""
        if sensor_zscores is None or sensor_zscores.empty:
            return pd.DataFrame({
                'Timestamp': [], 'SensorName': [], 'Rank': [], 'AbsZ': [],
                'SignedZ': [], 'Value': [], 'Level': []
            })

        records: List[Dict[str, Any]] = []
        abs_df = sensor_zscores.abs()
        for ts, row in abs_df.iterrows():
            top = row.nlargest(top_k)
            for rank, (sensor, abs_val) in enumerate(top.items(), start=1):
                if pd.isna(abs_val) or abs_val < warn_z:
                    continue
                signed_z = sensor_zscores.at[ts, sensor]
                value = None
                if sensor_values is not None and sensor in sensor_values.columns:
                    try:
                        value = sensor_values.at[ts, sensor]
                    except Exception:
                        value = sensor_values[sensor].reindex([ts]).iloc[-1]
                level = 'ALERT' if abs_val >= alert_z else 'WARN'
                records.append({
                    'Timestamp': _to_naive(ts),
                    'SensorName': sensor,
                    'Rank': rank,
                    'AbsZ': round(float(abs_val), 4),
                    'SignedZ': round(float(signed_z), 4) if pd.notna(signed_z) else None,
                    'Value': float(value) if value is not None and pd.notna(value) else None,
                    'Level': level
                })

        if not records:
            return pd.DataFrame({
                'Timestamp': [], 'SensorName': [], 'Rank': [], 'AbsZ': [],
                'SignedZ': [], 'Value': [], 'Level': []
            })

        df = pd.DataFrame(records).sort_values(['Timestamp', 'Rank']).reset_index(drop=True)
        return df
    
    def _generate_detector_correlation(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate detector correlation matrix with SQL schema columns."""
        detector_cols = [c for c in scores_df.columns if c.endswith('_z') and c != 'fused_z']
        if len(detector_cols) < 2:
            return pd.DataFrame({'DetectorA': [], 'DetectorB': [], 'PearsonR': []})
        
        correlations = []
        for i, det_a in enumerate(detector_cols):
            for det_b in detector_cols[i+1:]:
                sa = pd.to_numeric(scores_df[det_a], errors='coerce')
                sb = pd.to_numeric(scores_df[det_b], errors='coerce')
                std_a = float(sa.std(skipna=True))
                std_b = float(sb.std(skipna=True))
                if std_a == 0.0 or std_b == 0.0:
                    r = 0.0
                else:
                    r = sa.corr(sb)
                    r = 0.0 if pd.isna(r) else float(round(r, 4))
                correlations.append({
                    'DetectorA': det_a,
                    'DetectorB': det_b,
                    'PearsonR': r
                })
        
        return pd.DataFrame(correlations)
    
    def _generate_calibration_summary(self, scores_df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
        """Generate detector calibration and saturation summary with SQL schema columns."""
        detector_cols = [c for c in scores_df.columns if c.endswith('_z') and c != 'fused_z']
        calibration_data = []
        
        clip_z = cfg.get('thresholds', {}).get('self_tune', {}).get('clip_z', 30.0)
        # ANA-07: Get mhal condition number from diagnostics
        mhal_cond_num = cfg.get("_diagnostics", {}).get("mhal_cond_num", None)
        
        for detector in detector_cols:
            values = scores_df[detector].abs()
            saturation_pct = (values >= clip_z).mean() * 100
            
            row = {
                'DetectorType': detector,
                'MeanZ': round(values.mean(), 4),
                'StdZ': round(values.std(), 4),
                'P95Z': round(values.quantile(0.95), 4),
                'P99Z': round(values.quantile(0.99), 4),
                'ClipZ': clip_z,
                'SaturationPct': round(saturation_pct, 2)
            }
            
            # ANA-07: Add mhal_cond_num column (only populated for mhal_z row)
            if detector == 'mhal_z' and mhal_cond_num is not None:
                row['MahalCondNum'] = round(mhal_cond_num, 2)
            else:
                row['MahalCondNum'] = None
            
            calibration_data.append(row)
        
        return pd.DataFrame(calibration_data)
    
    def _generate_regime_transition_matrix(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate regime transition counts and probabilities."""
        regime_col = scores_df['regime_label']
        transitions = []
        
        for i in range(1, len(regime_col)):
            from_regime = regime_col.iloc[i-1]
            to_regime = regime_col.iloc[i]
            if from_regime != to_regime:  # Exclude self-transitions
                transitions.append({'FromLabel': from_regime, 'ToLabel': to_regime})
        
        if not transitions:
            return pd.DataFrame({'FromLabel': [], 'ToLabel': [], 'Count': [], 'Prob': []})
        
        # Count transitions
        transition_df = pd.DataFrame(transitions)
        transition_counts = transition_df.groupby(['FromLabel', 'ToLabel']).size().reset_index(name='Count')
        
        # Calculate probabilities
        total_transitions = transition_counts['Count'].sum()
        transition_counts['Prob'] = (transition_counts['Count'] / total_transitions).round(4)
        
        return transition_counts
    
    def _generate_regime_dwell_stats(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate regime dwell time statistics using real timestamps."""
        rl = pd.Series(scores_df['regime_label'])
        ts = pd.to_datetime(scores_df.index)
        group = rl.ne(rl.shift()).cumsum()
        runs = (pd.DataFrame({'regime': rl, 'ts': ts})
                  .groupby(group)
                  .agg(regime=('regime','first'), start=('ts','first'), end=('ts','last')))
        runs['seconds'] = (runs['end'] - runs['start']).dt.total_seconds().clip(lower=0)
        out = (runs.groupby('regime')['seconds']
                  .agg(runs='count',
                       mean_seconds='mean',
                       median_seconds='median',
                       min_seconds='min',
                       max_seconds='max')
                  .reset_index())
        
        # Rename columns for SQL compatibility
        out = out.rename(columns={
            'regime': 'RegimeLabel',
            'runs': 'Runs',
            'mean_seconds': 'MeanSeconds',
            'median_seconds': 'MedianSeconds',
            'min_seconds': 'MinSeconds',
            'max_seconds': 'MaxSeconds'
        })
        
        return out
    
    def _generate_drift_events(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate significant drift events from CUSUM series."""
        drift_col = 'cusum_z' if 'cusum_z' in scores_df.columns else 'drift_z'
        if drift_col not in scores_df.columns:
            return pd.DataFrame({'Timestamp': [], 'Value': [], 'SegmentStart': [], 'SegmentEnd': []})
        
        drift_values = scores_df[drift_col].abs()
        threshold = 3.0  # Threshold for significant drift events
        
        # Find peaks above threshold
        peaks = drift_values > threshold
        peak_events = []
        
        if peaks.any():
            # Find continuous segments above threshold
            in_segment = False
            segment_start = None
            
            for idx, is_peak in peaks.items():
                if is_peak and not in_segment:
                    segment_start = idx
                    in_segment = True
                elif not is_peak and in_segment:
                    peak_events.append({
                        'Timestamp': _to_naive(idx),
                        'Value': round(drift_values.loc[segment_start:idx].max(), 4),
                        'SegmentStart': _to_naive(segment_start),
                        'SegmentEnd': _to_naive(idx)
                    })
                    in_segment = False
            
            # Handle final segment if it ends with a peak
            if in_segment:
                final_idx = scores_df.index[-1]
                peak_events.append({
                    'Timestamp': _to_naive(final_idx),
                    'Value': round(drift_values.loc[segment_start:final_idx].max(), 4),
                    'SegmentStart': _to_naive(segment_start),
                    'SegmentEnd': _to_naive(final_idx)
                })
        
        return pd.DataFrame(peak_events)
    
    def _generate_drift_series(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate drift series timeline."""
        drift_col = 'cusum_z' if 'cusum_z' in scores_df.columns else 'drift_z'
        if drift_col not in scores_df.columns:
            return pd.DataFrame({'Timestamp': [], 'DriftValue': []})
        ts_values = _to_naive_series(scores_df.index).to_list()
        drift_values = scores_df[drift_col].round(4).to_list()
        return pd.DataFrame({
            'Timestamp': ts_values,
            'DriftValue': drift_values
        })
    
    def _generate_threshold_crossings(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate threshold crossing events."""
        threshold = 2.0  # Standard threshold
        crossings = []
        
        # Check fused score crossings
        fused_high = scores_df['fused'] > threshold
        crossing_points = fused_high != fused_high.shift()
        
        for idx in scores_df[crossing_points].index:
            crossings.append({
                'Timestamp': _to_naive(idx),
                'DetectorType': 'fused',
                'Threshold': threshold,
                'ZScore': round(scores_df.loc[idx, 'fused'], 4),
                'Direction': 'up' if scores_df.loc[idx, 'fused'] > threshold else 'down'
            })
        
        return pd.DataFrame(crossings)
    
    def _generate_since_when(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate alert start times summary."""
        first_alert = scores_df[scores_df['fused'] > 2.0].index.min() if len(scores_df[scores_df['fused'] > 2.0]) > 0 else None
        
        if first_alert:
            duration_hours = (scores_df.index.max() - first_alert).total_seconds() / 3600
            return pd.DataFrame({
                'RunID': [self.run_id],
                'EquipID': [int(self.equip_id) if self.equip_id else 0],
                'AlertZone': ['ALERT'],
                'DurationHours': [round(duration_hours, 2)],
                'StartTimestamp': [_to_naive(first_alert)],
                'RecordCount': [len(scores_df[scores_df['fused'] > 2.0])]
            })
        else:
            return pd.DataFrame({
                'RunID': [self.run_id],
                'EquipID': [int(self.equip_id) if self.equip_id else 0],
                'AlertZone': ['GOOD'],
                'DurationHours': [0.0],
                'StartTimestamp': [None],
                'RecordCount': [0]
            })

    def _generate_episodes_qc(self, scores_df: pd.DataFrame, episodes_df: pd.DataFrame) -> pd.DataFrame:
        """Summarize episode quality for batch-to-batch tracking.

        Columns: RunID, EquipID, EpisodeCount, MedianDurationMinutes, CoveragePct,
                 TimeInAlertPct, MaxFusedZ, AvgFusedZ
        """
        if episodes_df is None or episodes_df.empty:
            return pd.DataFrame({
                'RunID': [self.run_id],
                'EquipID': [int(self.equip_id) if self.equip_id else 0],
                'EpisodeCount': [0],
                'MedianDurationMinutes': [0.0],
                'CoveragePct': [0.0],
                'TimeInAlertPct': [0.0],
                'MaxFusedZ': [float('nan')],
                'AvgFusedZ': [float('nan')],
            })

        ep_count = int(len(episodes_df))
        durations_h = pd.to_numeric(episodes_df.get('duration_hours'), errors='coerce') if 'duration_hours' in episodes_df.columns else pd.Series([], dtype=float)
        median_minutes = float(np.nanmedian(durations_h) * 60.0) if len(durations_h) else 0.0

        # Coverage: fraction of timeline covered by episodes (approx using start/end)
        if {'start_ts','end_ts'}.issubset(set(episodes_df.columns)) and len(scores_df.index):
            t0 = scores_df.index.min()
            t1 = scores_df.index.max()
            total_secs = max(1.0, (t1 - t0).total_seconds())
            covered = 0.0
            for _, ep in episodes_df.iterrows():
                try:
                    s = pd.to_datetime(ep['start_ts'], errors='coerce')
                    e = pd.to_datetime(ep['end_ts'], errors='coerce')
                    if pd.notna(s) and pd.notna(e):
                        s = max(s, t0); e = min(e, t1)
                        if e > s:
                            covered += (e - s).total_seconds()
                except Exception:
                    pass
            coverage_pct = float(covered / total_secs * 100.0)
        else:
            coverage_pct = 0.0

        fused = pd.to_numeric(scores_df.get('fused'), errors='coerce') if 'fused' in scores_df.columns else pd.Series(dtype=float)
        if len(fused):
            time_in_alert_pct = float((fused > 2.0).mean() * 100.0)
            max_fused = float(np.nanmax(fused))
            avg_fused = float(np.nanmean(fused))
        else:
            time_in_alert_pct = 0.0
            max_fused = float('nan')
            avg_fused = float('nan')

        return pd.DataFrame([{
            'RunID': self.run_id,
            'EquipID': int(self.equip_id) if self.equip_id else 0,
            'EpisodeCount': ep_count,
            'MedianDurationMinutes': round(median_minutes, 2),
            'CoveragePct': round(coverage_pct, 2),
            'TimeInAlertPct': round(time_in_alert_pct, 2),
            'MaxFusedZ': max_fused,
            'AvgFusedZ': avg_fused,
        }])
    def _generate_sensor_rank_now(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate current sensor importance ranking."""
        detector_cols = [c for c in scores_df.columns if c.endswith('_z') and c != 'fused_z']
        if not detector_cols:
            return pd.DataFrame({'DetectorType': [], 'RankPosition': [], 'ContributionPct': [], 'ZScore': []})
        
        # Use latest values for ranking
        latest_scores = scores_df[detector_cols].iloc[-1].abs()
        ranked = latest_scores.sort_values(ascending=False)
        
        # Calculate contributions as percentages
        total = ranked.sum()
        contributions = (ranked / total * 100).round(2) if total > 0 else pd.Series([0] * len(ranked), index=ranked.index)
        
        return pd.DataFrame({
            'DetectorType': ranked.index,
            'RankPosition': range(1, len(ranked) + 1),
            'ContributionPct': contributions.values,
            'ZScore': ranked.values
        })
    
    def _generate_regime_occupancy(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate regime time occupancy statistics with consistent label typing.

        Ensures labels are numeric (Int64) to align with timeline outputs and
        includes all observed labels present in the frame.
        """
        if 'regime_label' not in scores_df.columns or len(scores_df) == 0:
            return pd.DataFrame({'RegimeLabel': [], 'RecordCount': [], 'Percentage': []})

        regimes = pd.to_numeric(scores_df['regime_label'], errors='coerce').dropna().astype('Int64')
        if regimes.empty:
            return pd.DataFrame({'RegimeLabel': [], 'RecordCount': [], 'Percentage': []})

        counts = regimes.value_counts().sort_index()
        total = int(len(regimes))

        occupancy = pd.DataFrame({
            'RegimeLabel': counts.index.to_list(),
            'RecordCount': counts.values.astype(int)
        })
        occupancy['Percentage'] = (occupancy['RecordCount'] / total * 100.0).round(2)
        return occupancy
    
    def _generate_health_histogram(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate health index distribution histogram."""
        health_index = _health_index(scores_df['fused'])
        bins = np.arange(0, 101, 10)
        hist, bin_edges = np.histogram(health_index, bins=bins)
        
        histogram_data = []
        for i in range(len(hist)):
            bin_label = f"{int(bin_edges[i])}-{int(bin_edges[i+1])}"
            histogram_data.append({
                'HealthBin': bin_label,
                'RecordCount': hist[i],
                'Percentage': round(hist[i] / len(health_index) * 100, 2)
            })
        
        return pd.DataFrame(histogram_data)
    
    def _generate_alert_age(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate alert age tracking using segmented zones."""
        # Build a tz-naive Python datetime list aligned to rows for robust math and ODBC
        ts_series = _to_naive_series(scores_df.index)
        # Convert to Python datetime objects (fix pandas FutureWarning)
        ts_values = [ts.to_pydatetime() for ts in ts_series]
        hi = _health_index(scores_df['fused'])
        zones = pd.cut(
            hi,
            bins=[0, AnalyticsConstants.HEALTH_ALERT_THRESHOLD, AnalyticsConstants.HEALTH_WATCH_THRESHOLD, 100],
            labels=['ALERT','WATCH','GOOD']
        )
        res = []
        for z in ['ALERT','WATCH','GOOD']:
            mask = zones.eq(z)
            if not mask.any():
                continue
            cuts = mask.ne(mask.shift()).cumsum()
            groups = cuts[mask].groupby(cuts[mask]).groups
            for _, idx in groups.items():
                # Convert label index to positional index to avoid tz-awareness mismatches
                pos = scores_df.index.get_indexer(idx)
                if len(pos) == 0:
                    continue
                i0, i1 = int(pos.min()), int(pos.max())
                start = ts_values[i0]
                end = ts_values[i1]
                res.append({
                    'AlertZone': z,
                    'StartTimestamp': start,
                    'DurationHours': round((end - start).total_seconds()/3600, 2),
                    'RecordCount': int(i1 - i0 + 1)
                })
        if not res:
            return pd.DataFrame({
                'AlertZone': ['NONE'],
                'StartTimestamp': [ts_values[0] if ts_values else None],
                'DurationHours': [0.0],
                'RecordCount': [0]
            })
        df = pd.DataFrame(res)
        # Aggregate to one row per zone to satisfy PK (RunID, EquipID, AlertZone)
        try:
            agg = (df.groupby('AlertZone', as_index=False)
                     .agg(StartTimestamp=('StartTimestamp', 'min'),
                          DurationHours=('DurationHours', 'sum'),
                          RecordCount=('RecordCount', 'sum')))
            return agg
        except Exception:
            return df
    
    def _generate_regime_stability(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate regime stability and churn metrics.

        Outputs columns aligned to SQL schema: MetricName, MetricValue.
        """
        regime_changes = (scores_df['regime_label'] != scores_df['regime_label'].shift()).sum()
        total_points = len(scores_df)

        # Calculate dwell times
        regime_runs = []
        current_regime = scores_df['regime_label'].iloc[0]
        run_start = 0

        for i, regime in enumerate(scores_df['regime_label']):
            if regime != current_regime:
                regime_runs.append({'regime': current_regime, 'duration': i - run_start})
                current_regime = regime
                run_start = i

        # Add final run
        regime_runs.append({'regime': current_regime, 'duration': len(scores_df) - run_start})

        if regime_runs:
            avg_duration = float(np.mean([r['duration'] for r in regime_runs]))
            median_duration = float(np.median([r['duration'] for r in regime_runs]))
        else:
            avg_duration = float(total_points)
            median_duration = float(total_points)

        # Guard against divide-by-zero (shouldn't happen with non-empty frame)
        churn_rate = float(round((regime_changes / total_points) * 100, 2)) if total_points > 0 else 0.0

        return pd.DataFrame({
            'MetricName': ['churn_rate', 'total_transitions', 'avg_dwell_periods', 'median_dwell_periods'],
            'MetricValue': [
                churn_rate,
                float(regime_changes),
                float(round(avg_duration, 1)),
                float(round(median_duration, 1))
            ]
        })
    
    def _generate_culprit_history(self, scores_df: pd.DataFrame, episodes_df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate enhanced culprit sensor history from episodes.
        Includes lead/lag temporal context and contribution-weighted ranking.
        """
        culprit_history = []
        
        # Detector columns available for analysis
        detector_cols = [c for c in scores_df.columns if c.endswith('_z') and c != 'fused_z']
        if not detector_cols:
            # Fallback to basic implementation
            return self._generate_culprit_history_basic(scores_df, episodes_df)
        
        # Standard fusion weights (from fuse.py defaults)
        default_weights = {
            'ar1_z': 1.5,
            'pca_spe_z': 1.0,
            'pca_t2_z': 0.8,
            'mhal_z': 1.2,
            'iforest_z': 1.0,
            'gmm_z': 0.9
        }
        
        for _, episode in episodes_df.iterrows():
            # Use actual column names from episodes.csv
            start_ts = episode.get('start_ts', episode.get('start_time', episode.get('timestamp', None)))
            end_ts = episode.get('end_ts', episode.get('end_time', None))
            
            if start_ts is None:
                continue
                
            # Calculate duration
            if end_ts is not None and not pd.isna(end_ts):
                try:
                    if isinstance(start_ts, str):
                        start_time = pd.to_datetime(start_ts)
                    else:
                        start_time = start_ts
                    
                    if isinstance(end_ts, str):
                        end_time = pd.to_datetime(end_ts)
                    else:
                        end_time = end_ts
                        
                    duration_hours = (end_time - start_time).total_seconds() / 3600
                except Exception:
                    duration_hours = 0.0
            else:
                # Use duration_s if available, or duration_hours
                duration_s = episode.get('duration_s', 0)
                duration_hours_col = episode.get('duration_hours', 0)
                if duration_s and not pd.isna(duration_s):
                    duration_hours = duration_s / 3600
                elif duration_hours_col and not pd.isna(duration_hours_col):
                    duration_hours = duration_hours_col
                else:
                    duration_hours = 0.0
            
            # Find episode window in scores_df
            try:
                # Convert to datetime for comparison
                start_dt = pd.to_datetime(start_ts) if not isinstance(start_ts, pd.Timestamp) else start_ts
                end_dt = pd.to_datetime(end_ts) if not isinstance(end_ts, pd.Timestamp) else end_ts
                
                # Get episode mask
                episode_mask = (scores_df.index >= start_dt) & (scores_df.index <= end_dt)
                episode_data = scores_df.loc[episode_mask, detector_cols]
                
                if episode_data.empty:
                    # Fallback to basic attribution
                    culprits = episode.get('culprits', 'unknown')
                    culprit_history.append({
                        'StartTimestamp': self._safe_single_timestamp(start_ts),
                        'EndTimestamp': self._safe_single_timestamp(end_ts),
                        'DurationHours': round(duration_hours, 1),
                        'PrimaryDetector': str(culprits),
                        'WeightedContribution': 'N/A',
                        'LeadMeanZ': 'N/A',
                        'DuringMeanZ': 'N/A',
                        'LagMeanZ': 'N/A'
                    })
                    continue
                
                # Compute weighted contributions for each detector
                contributions = {}
                for col in detector_cols:
                    if col in episode_data.columns:
                        mean_z = episode_data[col].mean()
                        weight = default_weights.get(col, 1.0)
                        contributions[col] = mean_z * weight
                
                # Rank by contribution
                ranked = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
                primary_detector = ranked[0][0].replace('_z', '') if ranked else 'unknown'
                weighted_contrib = round(ranked[0][1], 2) if ranked else 0.0
                
                # Lead/lag temporal context (1 hour before and after, or 10 samples)
                lead_window = 10
                lag_window = 10
                
                # Get indices
                episode_start_idx = scores_df.index.get_loc(episode_mask.idxmax()) if episode_mask.any() else 0
                episode_end_idx = len(scores_df) - 1 - scores_df.index[::-1].get_loc(episode_mask[::-1].idxmax()) if episode_mask.any() else len(scores_df) - 1
                
                lead_start = max(0, episode_start_idx - lead_window)
                lag_end = min(len(scores_df), episode_end_idx + lag_window + 1)
                
                # Compute lead/lag means for the primary detector
                lead_mean = scores_df.iloc[lead_start:episode_start_idx][primary_detector + '_z'].mean() if episode_start_idx > lead_start else np.nan
                during_mean = episode_data[primary_detector + '_z'].mean()
                lag_mean = scores_df.iloc[episode_end_idx+1:lag_end][primary_detector + '_z'].mean() if lag_end > episode_end_idx + 1 else np.nan
                
                culprit_history.append({
                    'StartTimestamp': self._safe_single_timestamp(start_ts),
                    'EndTimestamp': self._safe_single_timestamp(end_ts),
                    'DurationHours': round(duration_hours, 1),
                    'PrimaryDetector': primary_detector,
                    'WeightedContribution': weighted_contrib,
                    'LeadMeanZ': round(lead_mean, 2) if not pd.isna(lead_mean) else 'N/A',
                    'DuringMeanZ': round(during_mean, 2) if not pd.isna(during_mean) else 'N/A',
                    'LagMeanZ': round(lag_mean, 2) if not pd.isna(lag_mean) else 'N/A'
                })
                
            except Exception as e:
                # Fallback to basic attribution on error
                culprits = episode.get('culprits', 'unknown')
                culprit_history.append({
                    'StartTimestamp': self._safe_single_timestamp(start_ts),
                    'EndTimestamp': self._safe_single_timestamp(end_ts),
                    'DurationHours': round(duration_hours, 1),
                    'PrimaryDetector': str(culprits),
                    'WeightedContribution': 'N/A',
                    'LeadMeanZ': 'N/A',
                    'DuringMeanZ': 'N/A',
                    'LagMeanZ': 'N/A'
                })
        
        return pd.DataFrame(culprit_history)
    
    def _generate_culprit_history_basic(self, scores_df: pd.DataFrame, episodes_df: pd.DataFrame) -> pd.DataFrame:
        """Basic fallback for culprit history when detector columns unavailable."""
        culprit_history = []
        
        for _, episode in episodes_df.iterrows():
            start_ts = episode.get('start_ts', episode.get('start_time', episode.get('timestamp', None)))
            end_ts = episode.get('end_ts', episode.get('end_time', None))
            
            if start_ts is None:
                continue
            
            # Calculate duration
            duration_s = episode.get('duration_s', 0)
            duration_hours = duration_s / 3600 if duration_s else 0.0
            
            culprits = episode.get('culprits', 'unknown')
            if pd.isna(culprits) or culprits == '':
                culprits = 'unknown'
            
            culprit_history.append({
                'StartTimestamp': self._safe_single_timestamp(start_ts),
                'EndTimestamp': self._safe_single_timestamp(end_ts) if end_ts and not pd.isna(end_ts) else 'N/A',
                'DurationHours': round(duration_hours, 1),
                'Culprits': str(culprits)
            })
        
        return pd.DataFrame(culprit_history)
    
    def _generate_episode_metrics(self, episodes_df: pd.DataFrame) -> pd.DataFrame:
        """Generate episode-level statistical metrics."""
        if episodes_df.empty:
            return pd.DataFrame({
                'TotalEpisodes': [0],
                'TotalDurationHours': [0],
                'AvgDurationHours': [0],
                'MedianDurationHours': [0],
                'MaxDurationHours': [0],
                'MinDurationHours': [0],
                'RatePerDay': [0],
                'MeanInterarrivalHours': [0]
            })
        
        total_episodes = len(episodes_df)
        
        # Calculate durations for episodes using actual column names
        durations = []
        
        for _, episode in episodes_df.iterrows():
            # Use actual column names from episodes.csv
            start_ts = episode.get('start_ts', episode.get('start_time', episode.get('timestamp', None)))
            end_ts = episode.get('end_ts', episode.get('end_time', None))
            
            duration_hours = 0.0
            
            # Try to get duration from various sources
            if start_ts is not None and end_ts is not None and not pd.isna(end_ts):
                try:
                    if isinstance(start_ts, str):
                        start_time = pd.to_datetime(start_ts)
                    else:
                        start_time = start_ts
                    
                    if isinstance(end_ts, str):
                        end_time = pd.to_datetime(end_ts)
                    else:
                        end_time = end_ts
                        
                    duration_hours = (end_time - start_time).total_seconds() / 3600
                except Exception:
                    duration_hours = 0.0
            
            # Fallback to duration columns
            if duration_hours == 0.0:
                duration_s = episode.get('duration_s', 0)
                duration_hours_col = episode.get('duration_hours', 0)
                if duration_s and not pd.isna(duration_s):
                    duration_hours = duration_s / 3600
                elif duration_hours_col and not pd.isna(duration_hours_col):
                    duration_hours = duration_hours_col
            
            if duration_hours > 0:
                durations.append(duration_hours)
        
        if durations:
            total_duration = sum(durations)
            avg_duration = total_duration / len(durations)
            median_duration = pd.Series(durations).median()
            max_duration = max(durations)
            min_duration = min(durations)
        else:
            total_duration = avg_duration = median_duration = max_duration = min_duration = 0.0
        
        # Calculate rate per day and interarrival time
        if total_episodes > 1 and durations:
            # Estimate observation period from episode spans
            observation_days = max(30, total_duration / 24)  # At least 30 days or span of episodes
            rate_per_day = total_episodes / observation_days
            mean_interarrival_hours = total_duration / (total_episodes - 1) if total_episodes > 1 else 0
        else:
            rate_per_day = total_episodes / 30.0  # Default 30-day observation
            mean_interarrival_hours = 0
        
        return pd.DataFrame({
            'TotalEpisodes': [total_episodes],
            'TotalDurationHours': [round(total_duration, 1)],
            'AvgDurationHours': [round(avg_duration, 1)],
            'MedianDurationHours': [round(median_duration, 1)],
            'MaxDurationHours': [round(max_duration, 1)],
            'MinDurationHours': [round(min_duration, 1)],
            'RatePerDay': [round(rate_per_day, 3)],
            'MeanInterarrivalHours': [round(mean_interarrival_hours, 1)]
        })
    
    def _generate_episode_diagnostics(self, episodes_df: pd.DataFrame, scores_df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate per-episode diagnostic metrics for troubleshooting and severity analysis.
        
        Returns detailed diagnostics for each episode including:
        - Peak z-score and timestamp
        - Duration in hours
        - Dominant contributing sensor
        - Severity level and reason
        - Average z-score and minimum health index
        """
        if episodes_df.empty:
            return pd.DataFrame(columns=[
                'episode_id', 'peak_z', 'peak_timestamp', 'duration_h', 
                'dominant_sensor', 'severity', 'severity_reason', 
                'avg_z', 'min_health_index'
            ])
        
        diagnostics = []
        
        for _, episode in episodes_df.iterrows():
            episode_id = episode.get('episode_id', episode.name)
            
            # Extract metrics from episode (already computed in write_episodes)
            peak_z = episode.get('peak_fused_z', episode.get('peak_z', 0.0))
            peak_ts = episode.get('peak_timestamp', episode.get('start_ts', ''))
            avg_z = episode.get('avg_fused_z', episode.get('avg_z', 0.0))
            min_health = episode.get('min_health_index', _health_index(peak_z))
            
            # Duration in hours
            duration_h = episode.get('duration_hours', 0.0)
            if duration_h == 0.0 and 'duration_s' in episode:
                duration_h = episode['duration_s'] / 3600.0
            
            # Dominant sensor from culprits
            culprits_str = episode.get('culprits', '')
            dominant_sensor = 'Unknown'
            if culprits_str and isinstance(culprits_str, str):
                # Parse culprits format: "sensor1(0.85), sensor2(0.12)"
                culprits_list = culprits_str.split(',')
                if culprits_list:
                    first_culprit = culprits_list[0].strip()
                    dominant_sensor = first_culprit.split('(')[0].strip() if '(' in first_culprit else first_culprit
            
            # Severity and reason
            severity = episode.get('severity', 'MEDIUM')
            
            # Generate severity reason based on metrics
            if peak_z >= 3.0:
                severity_reason = f"Extreme anomaly (z={peak_z:.1f})"
            elif peak_z >= 2.5:
                severity_reason = f"High anomaly (z={peak_z:.1f})"
            elif duration_h >= 24:
                severity_reason = f"Extended duration ({duration_h:.1f}h)"
            elif duration_h >= 4:
                severity_reason = f"Moderate duration ({duration_h:.1f}h)"
            else:
                severity_reason = f"Brief anomaly ({duration_h:.1f}h, z={peak_z:.1f})"
            
            diagnostics.append({
                'episode_id': episode_id,
                'peak_z': round(peak_z, 3),
                'peak_timestamp': peak_ts,
                'duration_h': round(duration_h, 2),
                'dominant_sensor': dominant_sensor,
                'severity': severity,
                'severity_reason': severity_reason,
                'avg_z': round(avg_z, 3),
                'min_health_index': round(min_health, 2)
            })
        
        return pd.DataFrame(diagnostics)


    # -------------------- Dashboard-oriented helpers (appended) --------------------

    def _generate_omr_contributions_long(self, scores_df: pd.DataFrame, omr_contribs: pd.DataFrame) -> pd.DataFrame:
        """Long-format OMR contributions with per-timestamp percentage and OMR z.

        Columns: Timestamp, Sensor, ContributionScore, ContributionPct, OMR_Z
        """
        if omr_contribs is None or omr_contribs.empty:
            return pd.DataFrame(columns=["Timestamp", "Sensor", "ContributionScore", "ContributionPct", "OMR_Z"])  # empty schema

        wide = omr_contribs.reindex(scores_df.index).copy()
        wide = wide.apply(pd.to_numeric, errors='coerce').fillna(0.0)
        totals = wide.sum(axis=1)
        tmp = wide.reset_index()
        idx_col = tmp.columns[0]
        long = tmp.melt(id_vars=idx_col, var_name='Sensor', value_name='ContributionScore')
        long.rename(columns={idx_col: 'Timestamp'}, inplace=True)
        # Compute percentage safely
        total_map = totals.to_dict()
        def _pct(ts, val):
            t = total_map.get(ts, 0.0)
            return float(val) / t * 100.0 if t and np.isfinite(t) else 0.0
        long['ContributionPct'] = [
            _pct(ts, v) for ts, v in zip(pd.to_datetime(long['Timestamp']), long['ContributionScore'])
        ]
        # Attach OMR z when available
        if 'omr_z' in scores_df.columns:
            omr_map = pd.to_numeric(scores_df['omr_z'], errors='coerce').to_dict()
            long['OMR_Z'] = [float(omr_map.get(pd.to_datetime(ts), np.nan)) for ts in long['Timestamp']]
        else:
            long['OMR_Z'] = np.nan
        # Normalize timestamp to naive string for CSV
        long['Timestamp'] = _to_naive_series(long['Timestamp']).astype(str)
        long['ContributionScore'] = pd.to_numeric(long['ContributionScore'], errors='coerce').fillna(0.0)
        long['ContributionPct'] = pd.to_numeric(long['ContributionPct'], errors='coerce').fillna(0.0).clip(0.0, 100.0)
        return long[['Timestamp', 'Sensor', 'ContributionScore', 'ContributionPct', 'OMR_Z']]

    def _generate_daily_fused_profile(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate fused z by hour and weekday for simple dashboards."""
        if 'fused' not in scores_df.columns or scores_df.empty:
            return pd.DataFrame(columns=['DayOfWeek', 'Hour', 'FusedMean', 'FusedP90', 'FusedP95', 'Count'])
        idx = pd.to_datetime(scores_df.index)
        series = pd.to_numeric(scores_df['fused'], errors='coerce')
        df = pd.DataFrame({'fused': series, 'DayOfWeek': idx.dayofweek, 'Hour': idx.hour})
        df = df.dropna(subset=['fused'])
        if df.empty:
            return pd.DataFrame(columns=['DayOfWeek', 'Hour', 'FusedMean', 'FusedP90', 'FusedP95', 'Count'])
        # Group using explicit columns to prevent duplicate index-name collisions during reset_index
        grp = df.groupby(['DayOfWeek', 'Hour'])['fused']
        out = grp.agg(FusedMean='mean',
                      FusedP90=lambda s: np.nanpercentile(s, 90),
                      FusedP95=lambda s: np.nanpercentile(s, 95),
                      Count='count').reset_index()
        out['DayOfWeek'] = out['DayOfWeek'].astype(int)
        out['Hour'] = out['Hour'].astype(int)
        out['Count'] = out['Count'].astype(int)
        return out[['DayOfWeek', 'Hour', 'FusedMean', 'FusedP90', 'FusedP95', 'Count']]

    def _generate_regime_stats(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Compact per-regime summary table."""
        if 'regime_label' not in scores_df.columns or scores_df.empty:
            return pd.DataFrame(columns=['RegimeLabel', 'OccupancyPct', 'AvgDwellSeconds', 'FusedMean', 'FusedP90'])
        idx = pd.DatetimeIndex(scores_df.index)
        labels = pd.to_numeric(scores_df['regime_label'], errors='coerce')
        counts = labels.value_counts(dropna=True)
        total = counts.sum() if len(counts) else 0
        # Dwell approximation
        runs = []
        cur = None
        start = None
        for ts, lab in zip(idx, labels):
            if pd.isna(lab):
                continue
            if cur is None:
                cur, start = lab, ts
                continue
            if lab != cur:
                runs.append((int(cur), (ts - start).total_seconds()))
                cur, start = lab, ts
        if cur is not None and start is not None and len(idx):
            runs.append((int(cur), (idx[-1] - start).total_seconds()))
        dwell = pd.DataFrame(runs, columns=['RegimeLabel', 'DwellSeconds']) if runs else pd.DataFrame(columns=['RegimeLabel', 'DwellSeconds'])
        stats = []
        for lab, cnt in counts.items():
            try:
                lab_int = int(lab)
            except Exception:
                continue
            sel = scores_df['regime_label'] == lab
            fvals = pd.to_numeric(scores_df.loc[sel, 'fused'], errors='coerce') if 'fused' in scores_df.columns else pd.Series(dtype=float)
            fused_mean = float(fvals.mean()) if len(fvals) else float('nan')
            fused_p90 = float(np.nanpercentile(fvals, 90)) if len(fvals) else float('nan')
            avg_dwell = float(dwell[dwell['RegimeLabel'] == lab_int]['DwellSeconds'].mean()) if not dwell.empty else float('nan')
            occ = float(cnt / total * 100.0) if total > 0 else 0.0
            stats.append({
                'RegimeLabel': lab_int,
                'OccupancyPct': round(occ, 2),
                'AvgDwellSeconds': round(avg_dwell, 1) if np.isfinite(avg_dwell) else None,
                'FusedMean': fused_mean,
                'FusedP90': fused_p90,
            })
        return pd.DataFrame(stats).sort_values('RegimeLabel')


    def _generate_fusion_quality_report(self, scores_df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
        """Produce a simple fusion quality snapshot.

        Columns: Detector, Weight, Present, MeanZ, MaxZ, Points
        """
        rows: List[Dict[str, Any]] = []
        weights = ((cfg.get('fusion', {}) or {}).get('weights', {}) or {})
        # Detector columns typically end with _z (including fused)
        zcols = [c for c in scores_df.columns if c.endswith('_z') or c == 'fused']
        stats = {}
        for c in zcols:
            s = pd.to_numeric(scores_df[c], errors='coerce')
            stats[c] = {
                'MeanZ': float(np.nanmean(s)) if len(s) else float('nan'),
                'MaxZ': float(np.nanmax(s)) if len(s) else float('nan'),
                'Points': int(len(s))
            }
        # Normalize common keys (e.g., omr_z vs omr)
        def _norm_key(k: str) -> str:
            return k if k in zcols else (k + '_z' if (k + '_z') in zcols else k)
        for det, w in weights.items():
            key = _norm_key(str(det))
            present = key in zcols
            det_stats = stats.get(key, {'MeanZ': float('nan'), 'MaxZ': float('nan'), 'Points': 0})
            rows.append({
                'Detector': key,
                'Weight': float(w) if w is not None else 0.0,
                'Present': bool(present),
                **det_stats
            })
        # Add any present detectors not listed in weights for visibility
        for c in zcols:
            if c not in [r['Detector'] for r in rows]:
                rows.append({'Detector': c, 'Weight': 0.0, 'Present': True, **stats.get(c, {})})
        return pd.DataFrame(rows)

    def _generate_health_distribution_over_time(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Hourly health distribution percentiles to align with heatmaps.

        Columns: BucketStart, BucketSeconds, FusedP50, FusedP75, FusedP90, FusedP95,
                 HealthP50, HealthP10, Count
        """
        if 'fused' not in scores_df.columns or scores_df.empty:
            return pd.DataFrame(columns=['BucketStart','BucketSeconds','FusedP50','FusedP75','FusedP90','FusedP95','HealthP50','HealthP10','Count'])
        idx = pd.DatetimeIndex(scores_df.index)
        fused = pd.to_numeric(scores_df['fused'], errors='coerce')
        health = _health_index(fused)
        df = pd.DataFrame({'fused': fused, 'health': health}, index=idx)
        df = df[~df.index.isna()]
        if df.empty:
            return pd.DataFrame(columns=['BucketStart','BucketSeconds','FusedP50','FusedP75','FusedP90','FusedP95','HealthP50','HealthP10','Count'])
        hourly = df.groupby([idx.year, idx.month, idx.day, idx.hour])
        rows = []
        for (y, m, d, h), grp in hourly:
            bucket_start = pd.Timestamp(year=int(y), month=int(m), day=int(d), hour=int(h))
            fvals = pd.to_numeric(grp['fused'], errors='coerce').dropna()
            hvals = pd.to_numeric(grp['health'], errors='coerce').dropna()
            rows.append({
                'BucketStart': bucket_start,
                'BucketSeconds': 3600,
                'FusedP50': float(np.nanpercentile(fvals, 50)) if len(fvals) else float('nan'),
                'FusedP75': float(np.nanpercentile(fvals, 75)) if len(fvals) else float('nan'),
                'FusedP90': float(np.nanpercentile(fvals, 90)) if len(fvals) else float('nan'),
                'FusedP95': float(np.nanpercentile(fvals, 95)) if len(fvals) else float('nan'),
                'HealthP50': float(np.nanpercentile(hvals, 50)) if len(hvals) else float('nan'),
                'HealthP10': float(np.nanpercentile(hvals, 10)) if len(hvals) else float('nan'),
                'Count': int(len(grp))
            })
        out = pd.DataFrame(rows)
        if not out.empty:
            out['BucketStart'] = _to_naive_series(out['BucketStart'])
        return out

    def _generate_omr_timeline(self, scores_df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
        """Generate OMR timeline with weight annotation when available."""
        ts_values = _to_naive_series(scores_df.index).to_list()
        omr_series = pd.to_numeric(scores_df.get('omr_z'), errors='coerce') if 'omr_z' in scores_df.columns else pd.Series(dtype=float)
        try:
            weights = (cfg.get('fusion', {}) or {}).get('weights', {})
            omr_weight = float(weights.get('omr_z', weights.get('omr', 0.0)))
        except Exception:
            omr_weight = 0.0
        return pd.DataFrame({
            'Timestamp': ts_values,
            'OMR_Z': omr_series.round(4).to_list(),
            'OMR_Weight': [omr_weight] * len(ts_values)
        })

def create_output_manager(sql_client=None, run_id: str = None, equip_id: int = None, **kwargs) -> OutputManager:
    """Factory function for creating OutputManager instances."""
    return OutputManager(
        sql_client=sql_client,
        run_id=run_id,
        equip_id=equip_id,
        **kwargs
    )




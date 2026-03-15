"""
Data Loader for ACM
====================

Handles all data loading from SQL Server historian tables.
Extracted from output_manager.py as part of Phase 2 debloating.

Key responsibilities:
- Load historian data via stored procedure
- Parse timestamps and set as index
- Filter future timestamps
- Infer numeric columns
- Check and resample cadence
- Cold-start train/score splitting

Usage:
    from core.data_loader import DataLoader, DataMeta
    
    loader = DataLoader(sql_client)
    train, score, meta = loader.load_from_sql(cfg, "FD_FAN", start, end, is_coldstart=True)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, cast
import os
import json

import numpy as np
import pandas as pd

from core.observability import Console
from core.time_normalizer import (
    check_cadence,
    coerce_local_and_filter_future,
    native_cadence_secs,
    parse_ts_index,
    resample_df,
)
from utils.config_dict import cfg_get as _cfg_get, future_cutoff_ts as _future_cutoff_ts


# ============================================================================
# DATA METADATA
# ============================================================================
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


def infer_numeric_cols(df: pd.DataFrame) -> List[str]:
    """Get list of numeric columns."""
    return df.select_dtypes(include=[np.number]).columns.tolist()


# ============================================================================
# DATA LOADER CLASS
# ============================================================================
class DataLoader:
    """
    Handles data loading from SQL Server historian tables.
    
    This class encapsulates all data loading logic previously embedded in OutputManager.
    """
    
    def __init__(self, sql_client: Any):
        """
        Initialize the DataLoader.
        
        Args:
            sql_client: SQL client instance (core.sql_client.SQLClient)
        """
        self.sql_client = sql_client
    
    def load_from_sql(
        self,
        cfg: Dict[str, Any],
        equipment_name: str,
        start_utc: Optional[pd.Timestamp],
        end_utc: Optional[pd.Timestamp],
        is_coldstart: bool = False
    ) -> Tuple[pd.DataFrame, pd.DataFrame, DataMeta]:
        """
        Load training and scoring data from SQL historian using stored procedure.

        Key behavioral rules:
        - If no rows returned: raise ValueError("No data returned...") (caller may NOOP).
        - Scoring with cached models (is_coldstart=False): allow small batches
          using data.min_score_samples (default 1).
        - Coldstart training (is_coldstart=True): enforce min_train_samples.
        """
        data_cfg = cfg.get("data", {}) or {}
        ts_col = _cfg_get(data_cfg, "timestamp_col", "EntryDateTime")

        # NOTE: Keep min_train_samples consistent; do NOT overwrite it later.
        min_train_samples = int(_cfg_get(data_cfg, "min_train_samples", 500))

        # NEW: explicit minimum rows for online scoring
        min_score_samples = int(_cfg_get(data_cfg, "min_score_samples", 1))
        min_score_samples = max(1, min_score_samples)

        # SQL mode requires explicit time windows
        if not start_utc or not end_utc:
            raise ValueError("SQL mode requires start_utc and end_utc parameters")

        # COLDSTART split ratio (only used when is_coldstart=True)
        cold_start_split_ratio = float(_cfg_get(data_cfg, "cold_start_split_ratio", 0.6))
        if not (0.1 <= cold_start_split_ratio <= 0.9):
            Console.warn(
                f"Invalid cold_start_split_ratio={cold_start_split_ratio}, using default 0.6",
                component="DATA", invalid_value=cold_start_split_ratio, equipment=equipment_name
            )
            cold_start_split_ratio = 0.6

        Console.info(f"Loading from SQL historian: {equipment_name}", component="DATA")
        Console.info(f"Time range: {start_utc} to {end_utc}", component="DATA")

        cur = None
        try:
            if self.sql_client is None:
                raise ValueError("SQL mode requested but no SQL client available")

            cur = cast(Any, self.sql_client).cursor()
            cur.execute(
                "EXEC dbo.usp_ACM_GetHistorianData_TEMP @StartTime=?, @EndTime=?, @EquipmentName=?",
                (start_utc, end_utc, equipment_name)
            )

            rows = cur.fetchall()
            if not rows:
                # This is the canonical "NO DATA" signal; caller can treat as NOOP.
                raise ValueError(f"No data returned from SQL historian for {equipment_name} in time range")

            columns = [desc[0] for desc in cur.description]
            df_all = pd.DataFrame.from_records(rows, columns=columns)

            Console.info(f"Retrieved {len(df_all)} rows from SQL historian", component="DATA")

            # Exclude persisted low-variance sensors
            try:
                import os
                import json
                equip_id_cur = self.sql_client.cursor()
                equip_id_cur.execute("SELECT EquipID FROM Equipment WHERE EquipCode = ?", (equipment_name,))
                equip_id_row = equip_id_cur.fetchone()
                equip_id = equip_id_row[0] if equip_id_row else None
                equip_id_cur.close()

                if equip_id:
                    exclusion_file = f"artifacts/equip_{equip_id}/low_variance_sensors.json"
                    if os.path.exists(exclusion_file):
                        with open(exclusion_file, 'r') as f:
                            try:
                                excluded_sensors = json.load(f)
                            except json.JSONDecodeError:
                                excluded_sensors = []
                        
                        if excluded_sensors:
                            original_cols = set(df_all.columns)
                            cols_to_drop = [s for s in excluded_sensors if s in original_cols]
                            if cols_to_drop:
                                df_all = df_all.drop(columns=cols_to_drop, errors='ignore')
                                Console.warn(f"Permanently excluded {len(cols_to_drop)} low-variance sensors based on persisted list.", component="DATA")
            except Exception as ex_err:
                Console.warn(f"Failed to process sensor exclusion list: {ex_err}", component="DATA")

        except Exception as e:
            Console.error(
                f"Failed to load from SQL historian: {e}",
                component="DATA", equipment=equipment_name, error_type=type(e).__name__, error=str(e)[:200]
            )
            raise
        finally:
            try:
                if cur is not None:
                    # Drain any pending result sets from usp_ACM_GetHistorianData_TEMP
                    # before closing. SQL Server SPs can emit extra result sets (PRINT
                    # messages, rowcount tokens, etc.). Without draining, pyodbc leaves
                    # the connection in state HY007 ("Associated statement is not
                    # prepared"), which corrupts the next cursor opened on the same
                    # connection -- including the _check_sql_health() SELECT 1 in
                    # batched_transaction(). Same fix as 2026.2.6 for usp_CleanupBaselineBuffer.
                    try:
                        while cur.nextset():
                            pass
                    except Exception:
                        pass
                    cur.close()
            except Exception:
                pass

        # Validate sufficient data:
        # - Coldstart: enforce min_train_samples
        # - Online scoring: enforce min_score_samples (default 1)
        required_minimum = min_train_samples if is_coldstart else min_score_samples
        if len(df_all) < required_minimum:
            raise ValueError(
                f"Insufficient data from SQL historian: {len(df_all)} rows "
                f"(minimum {required_minimum} required; is_coldstart={is_coldstart})"
            )

        # Robust timestamp column fallback
        if ts_col not in df_all.columns and "EntryDateTime" in df_all.columns:
            Console.warn(
                f"Timestamp column '{ts_col}' not found; falling back to 'EntryDateTime'.",
                component="DATA", configured_col=ts_col, fallback_col="EntryDateTime", equipment=equipment_name
            )
            ts_col = "EntryDateTime"

        # Split train/score
        if is_coldstart:
            total = len(df_all)
            if total < min_train_samples:
                Console.warn(
                    f"Coldstart total rows below minimum: {total} < {min_train_samples}",
                    component="DATA", equipment=equipment_name
                )
                # Let caller decide retry strategy
                meta = DataMeta(
                    timestamp_col=ts_col,
                    cadence_ok=False,
                    kept_cols=[],
                    dropped_cols=[],
                    start_ts=pd.Timestamp.now(),
                    end_ts=pd.Timestamp.now(),
                    n_rows=0,
                    sampling_seconds=0.0,
                    tz_stripped=0,
                    future_rows_dropped=0,
                    dup_timestamps_removed=0
                )
                return pd.DataFrame(), pd.DataFrame(), meta

            # Ensure train has at least min_train_samples
            train_n = max(min_train_samples, int(total * cold_start_split_ratio))
            train_n = min(train_n, total)  # safety

            # If train_n consumes all rows, keep at least 1 for scoring if possible
            if train_n == total and total > min_train_samples:
                train_n = total - 1

            train_raw = df_all.iloc[:train_n].copy()
            score_raw = df_all.iloc[train_n:].copy()
            Console.info(
                f"COLDSTART Split: {len(train_raw)} train rows, {len(score_raw)} score rows (required train: {min_train_samples})",
                component="DATA", equipment=equipment_name
            )
        else:
            train_raw = pd.DataFrame()
            score_raw = df_all.copy()
            Console.info(
                f"BATCH MODE: All {len(score_raw)} rows allocated to scoring (baseline from cache)",
                component="DATA"
            )

        # Parse timestamps / index
        if len(train_raw) == 0 and not is_coldstart:
            train = pd.DataFrame(columns=train_raw.columns)
            train.index = pd.DatetimeIndex([], name=ts_col)
        else:
            train = parse_ts_index(train_raw, ts_col)

        score = parse_ts_index(score_raw, ts_col)

        # Filter future timestamps
        now_cutoff = _future_cutoff_ts(cfg)
        train, tz_stripped_train, future_train = coerce_local_and_filter_future(train, "TRAIN", now_cutoff)
        score, tz_stripped_score, future_score = coerce_local_and_filter_future(score, "SCORE", now_cutoff)
        tz_stripped_total = tz_stripped_train + tz_stripped_score
        future_rows_total = future_train + future_score

        # Keep numeric only
        if len(train) == 0 and not is_coldstart:
            score_num = infer_numeric_cols(score)
            kept = sorted(score_num)
            dropped = [c for c in score.columns if c not in kept]
            train = pd.DataFrame(columns=kept)
            score = score[kept].astype(np.float32)
            Console.info(
                f"BATCH MODE: Train empty (baseline_buffer later), using {len(kept)} score columns",
                component="DATA"
            )
        else:
            train_num = infer_numeric_cols(train)
            score_num = infer_numeric_cols(score)
            kept = sorted(list(set(train_num).intersection(score_num)))
            dropped = [c for c in train.columns if c not in kept]
            train = train[kept].astype(np.float32)
            score = score[kept].astype(np.float32)

        Console.info(f"Kept {len(kept)} numeric columns, dropped {len(dropped)} non-numeric", component="DATA")

        # Cadence / resample
        _sampling = data_cfg.get("sampling_secs", 1)
        try:
            if _sampling in (None, "", "auto", "null"):
                sampling_secs: Optional[int] = None
            else:
                sampling_secs = int(_sampling)
        except (TypeError, ValueError):
            sampling_secs = None

        allow_resample = bool(_cfg_get(data_cfg, "allow_resample", True))
        resample_strict = bool(_cfg_get(data_cfg, "resample_strict", False))
        interp_method = str(_cfg_get(data_cfg, "interp_method", "linear"))
        max_fill_ratio = float(_cfg_get(data_cfg, "max_fill_ratio", _cfg_get(cfg, "runtime.max_fill_ratio", 0.20)))

        cad_ok_train = check_cadence(cast(pd.DatetimeIndex, train.index), sampling_secs)
        cad_ok_score = check_cadence(cast(pd.DatetimeIndex, score.index), sampling_secs)
        cadence_ok = bool(cad_ok_train and cad_ok_score)

        native_train = native_cadence_secs(cast(pd.DatetimeIndex, train.index))
        native_score = native_cadence_secs(cast(pd.DatetimeIndex, score.index))
        native_cadence = min(
            native_train if math.isfinite(native_train) else float('inf'),
            native_score if math.isfinite(native_score) else float('inf')
        )

        if sampling_secs is not None and math.isfinite(native_cadence):
            if sampling_secs < native_cadence * 0.9:
                Console.warn(
                    f"ANTI-UPSAMPLE: Requested ({sampling_secs}s) < native ({native_cadence:.1f}s). Using native.",
                    component="DATA", requested_secs=sampling_secs, native_secs=native_cadence, equipment=equipment_name
                )
                sampling_secs = None
                cadence_ok = True

        Console.info(
            f"Cadence: native={native_cadence:.1f}s, requested={sampling_secs or 'auto'}, "
            f"will_resample={sampling_secs is not None and not cadence_ok}",
            component="DATA", native_cadence=native_cadence, equipment=equipment_name
        )

        if sampling_secs is not None:
            base_secs = float(sampling_secs)
        else:
            base_secs = native_cadence if math.isfinite(native_cadence) else 1.0
        max_gap_secs = int(_cfg_get(data_cfg, "max_gap_secs", base_secs * 3))

        explode_guard_factor = float(_cfg_get(data_cfg, "explode_guard_factor", 2.0))
        will_resample = allow_resample and (not cadence_ok) and (sampling_secs is not None)
        if will_resample:
            span_secs = (train.index[-1].value - train.index[0].value) / 1e9 if len(train.index) else 0.0
            safe_sampling = float(sampling_secs) if sampling_secs is not None else 1.0
            approx_rows = int(span_secs / max(1.0, safe_sampling)) + 1
            if len(train) and approx_rows > explode_guard_factor * len(train):
                Console.warn(
                    f"Resample would expand rows {len(train)} -> ~{approx_rows} (>x{explode_guard_factor:.1f}). Skipping.",
                    component="DATA"
                )
                will_resample = False

        if will_resample:
            assert sampling_secs is not None
            train = resample_df(train, int(sampling_secs), interp_method, resample_strict, max_gap_secs, max_fill_ratio).astype(np.float32)
            score = resample_df(score, int(sampling_secs), interp_method, resample_strict, max_gap_secs, max_fill_ratio).astype(np.float32)
            cadence_ok = True

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

        Console.info(
            f"SQL historian load complete: {len(train)} train + {len(score)} score = {len(train) + len(score)} total rows",
            component="DATA"
        )
        return train, score, meta

"""
ACM Smart Coldstart Module

Current responsibilities:
1. read SQL-backed coldstart progress and legacy lifecycle hints
2. choose the scoring-window or baseline-window load path
3. track coldstart progress across batches
4. never fall back to file mode

Runtime-mode and readiness meaning are owned by `core.baseline_governor`.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, Callable
from dataclasses import dataclass
import pandas as pd
from core.baseline_governor import (
    annotate_load_stage_governance_meta,
    resolve_coldstart_load_decision,
)
from core.observability import Console
from core.run_metadata_writer import zero_day_status_from_noop_reason


def classify_noop_reason(
    train: Optional[pd.DataFrame],
    score: Optional[pd.DataFrame],
    meta: Optional[Any] = None,
) -> str:
    """
    Deterministic NOOP classification used by the ACM pipeline.

    Priority:
    1) Explicit reason from meta.noop_reason / meta['noop_reason']
    2) Fallback inference from train/score and governed load-stage hints
    """
    if meta is not None:
        try:
            if isinstance(meta, dict):
                reason = str(meta.get("noop_reason", "")).strip()
            else:
                reason = str(getattr(meta, "noop_reason", "")).strip()
            if reason:
                return reason
        except Exception:
            pass

    enough_history_to_proceed = True
    if meta is not None:
        try:
            if isinstance(meta, dict):
                enough_history_to_proceed = bool(meta.get("enough_history_to_proceed", True))
            else:
                enough_history_to_proceed = bool(getattr(meta, "enough_history_to_proceed", True))
        except Exception:
            enough_history_to_proceed = True

    if train is None or score is None:
        if not enough_history_to_proceed:
            return "COLDSTART_DEFERRED"
        return "SCORING_NO_DATA"

    if hasattr(score, "__len__") and len(score) == 0:
        return "SCORING_NO_DATA"

    return "UNKNOWN_NOOP"


def build_noop_observability(reason: str) -> Tuple[str, Dict[str, Any]]:
    """
    Build an operator-facing NOOP message with explicit scoring semantics.

    This keeps two situations distinct:
    - `COLDSTART_DEFERRED`: insufficient history, so this run does not score at all
    - `SCORING_NO_DATA`: models may exist, but there is no new historian window to score
    """
    normalized = str(reason or "UNKNOWN_NOOP").strip().upper() or "UNKNOWN_NOOP"

    if normalized == "SCORING_NO_DATA":
        return (
            "NOOP - no new data in historian window (models exist); zero-day scoring inactive on this run",
            {
                "noop_reason": normalized,
                "zero_day_scoring_active": False,
                "legacy_fit_ready": True,
            },
        )

    if normalized == "COLDSTART_DEFERRED":
        return (
            "NOOP - coldstart deferred; insufficient history for governed baseline formation and zero-day scoring is inactive on this run",
            {
                "noop_reason": normalized,
                "zero_day_scoring_active": False,
                "legacy_fit_ready": False,
            },
        )

    return (
        "NOOP - load stage stopped before scoring",
        {
            "noop_reason": normalized,
            "zero_day_scoring_active": False,
        },
    )


@dataclass
class DataLoadStageResult:
    """Result bundle for load-data stage orchestration."""
    train: Optional[pd.DataFrame]
    score: Optional[pd.DataFrame]
    meta: Optional[Any]
    should_continue: bool
    noop_reason: Optional[str] = None


_COLDSTART_PROGRESS_STAGE = "score"


def load_and_validate_data_stage(
    *,
    sql_client: Any,
    equip: str,
    equip_id: int,
    cfg: Dict[str, Any],
    args: Any,
    output_manager: Any,
    win_start: Optional[pd.Timestamp],
    win_end: Optional[pd.Timestamp],
    ensure_local_index_fn: Callable[[pd.DataFrame], pd.DataFrame],
    deduplicate_index_fn: Callable[[pd.DataFrame, str, str], Tuple[pd.DataFrame, int]],
    validate_data_contract_fn: Callable[..., Any],
    finalize_noop_run_fn: Callable[..., None],
    record_coldstart_fn: Callable[[str], None],
    refit_requested: bool,
    run_id: Optional[str],
    logger: Any = Console,
) -> DataLoadStageResult:
    """
    Load data window, handle coldstart/NOOP, normalize index, deduplicate, and validate contract.
    """
    coldstart_manager = SmartColdstart(
        sql_client=sql_client,
        equip_id=equip_id,
        equip_name=equip,
    )
    train, score, meta, can_proceed = coldstart_manager.load_window(
        cfg=cfg,
        output_manager=output_manager,
        start_time=win_start,
        end_time=win_end,
    )
    gate_reason = getattr(coldstart_manager.state, "gate_reason", "") if getattr(coldstart_manager, "state", None) is not None else ""

    if not can_proceed:
        meta = annotate_load_stage_governance_meta(
            meta,
            can_proceed=False,
            is_coldstart_run=True,
            gate_reason=gate_reason,
        )
        reason = classify_noop_reason(
            train,
            score,
            meta=meta,
        )
        noop_message, noop_fields = build_noop_observability(reason)
        logger.info(noop_message, component="COLDSTART", **noop_fields)
        finalize_noop_run_fn(
            sql_client=sql_client,
            run_id=run_id,
            logger=logger,
            zero_day_status=zero_day_status_from_noop_reason(reason),
            equip_id=equip_id,
        )
        return DataLoadStageResult(
            train=train,
            score=score,
            meta=meta,
            should_continue=False,
            noop_reason=reason,
        )

    record_coldstart_fn(equip)
    train = ensure_local_index_fn(train)
    score = ensure_local_index_fn(score)

    is_coldstart_run = bool(
        meta.get("is_coldstart_run", False) if isinstance(meta, dict) else getattr(meta, "is_coldstart_run", False)
    )
    meta = annotate_load_stage_governance_meta(
        meta,
        can_proceed=True,
        is_coldstart_run=is_coldstart_run,
        gate_reason=gate_reason,
    )

    train, train_dups = deduplicate_index_fn(train, "TRAIN", equip)
    score, score_dups = deduplicate_index_fn(score, "SCORE", equip)
    if isinstance(meta, dict):
        meta["dup_timestamps_removed"] = int(train_dups + score_dups)
    else:
        setattr(meta, "dup_timestamps_removed", int(train_dups + score_dups))

    validate_data_contract_fn(
        train=train,
        score=score,
        meta=meta,
        refit_requested=refit_requested,
        cfg=cfg,
        output_manager=output_manager,
        equip_id=equip_id,
        equip=equip,
        run_id=run_id,
        logger=logger,
    )

    if len(score) == 0:
        logger.warn(
            "SCORE window empty after cleaning; marking run as NOOP",
            component="DATA",
            equip=equip,
            run_id=run_id,
        )
        finalize_noop_run_fn(
            sql_client=sql_client,
            run_id=run_id,
            logger=logger,
            zero_day_status=zero_day_status_from_noop_reason("SCORING_NO_DATA"),
            equip_id=equip_id,
        )
        return DataLoadStageResult(
            train=train,
            score=score,
            meta=meta,
            should_continue=False,
            noop_reason="SCORING_NO_DATA",
        )

    logger.info(
        f"[DATA] timestamp={meta.timestamp_col} cadence_ok={meta.cadence_ok} "
        f"kept={len(meta.kept_cols)} drop={len(meta.dropped_cols)} "
        f"tz_stripped={getattr(meta, 'tz_stripped', 0)} "
        f"future_drop={getattr(meta, 'future_rows_dropped', 0)} "
        f"dup_removed={getattr(meta, 'dup_timestamps_removed', 0)}"
    )
    return DataLoadStageResult(
        train=train,
        score=score,
        meta=meta,
        should_continue=True,
        noop_reason=None,
    )


@dataclass
class ColdstartState:
    """SQL-backed coldstart progress and load-path state for one equipment."""
    equip_id: int
    use_existing_models: bool = False
    attempt_count: int = 0
    accumulated_rows: int = 0
    required_rows: int = 500
    gate_reason: Optional[str] = None


class SmartColdstart:
    """
    Smart coldstart helper that manages SQL-backed progress and load-window selection.

    Current responsibilities:
    - auto-detect historian cadence
    - calculate earliest-data coldstart windows when needed
    - track progress across multiple job runs
    - never fail the pipeline when the current window is not ready yet
    """
    
    def __init__(self, sql_client, equip_id: int, equip_name: str):
        self.sql_client = sql_client
        self.equip_id = equip_id
        self.equip_name = equip_name
        self.state: Optional[ColdstartState] = None
        
    def check_status(self, required_rows: int = 500) -> ColdstartState:
        """
        Check current coldstart status from database.

        Transitional behavior:
        - SQL access stays here
        - readiness/load-path meaning now comes from governed runtime-mode rows

        The old SP-based gate (ModelRegistry >= 3) was wrong: stale/corrupt models
        with 3+ model types in ModelRegistry would bypass coldstart indefinitely.

        Args:
            required_rows: Minimum rows needed to complete coldstart

        Returns:
            ColdstartState with current status
        """
        state = ColdstartState(self.equip_id)
        state.required_rows = required_rows
        try:
            with self.sql_client.cursor() as cur:
                cur.execute(
                    """
                    IF OBJECT_ID('dbo.ACM_BaselineGovernance', 'U') IS NOT NULL
                    BEGIN
                        SELECT TOP 1 RuntimeMode
                        FROM dbo.ACM_BaselineGovernance
                        WHERE EquipID = ?
                        ORDER BY Timestamp DESC, CreatedAt DESC
                    END
                    """,
                    (self.equip_id,),
                )
                governed_row = cur.fetchone()
                cur.execute(
                    """
                    IF COL_LENGTH('dbo.ACM_Runs', 'RepresentationRuntimeMode') IS NOT NULL
                    BEGIN
                        SELECT TOP 1 RepresentationRuntimeMode
                        FROM dbo.ACM_Runs
                        WHERE EquipID = ?
                        ORDER BY CompletedAt DESC, CreatedAt DESC
                    END
                    """,
                    (self.equip_id,)
                )
                run_row = cur.fetchone()

            decision = resolve_coldstart_load_decision(
                runtime_mode_hint=governed_row[0] if governed_row is not None else None,
                run_runtime_mode_hint=run_row[0] if run_row is not None else None,
            )
            state.use_existing_models = decision.use_existing_models
            state.gate_reason = decision.reason_code
            if not state.use_existing_models:
                accumulated, attempts = self._load_progress()
                state.accumulated_rows = accumulated
                state.attempt_count = attempts

        except Exception as e:
            Console.warn(
                f"check_status failed, defaulting to coldstart: {e}",
                component="COLDSTART",
                equip_id=self.equip_id,
                equip_name=self.equip_name,
                stage=_COLDSTART_PROGRESS_STAGE,
                error_type=type(e).__name__,
                error=str(e)[:200],
            )
            state.use_existing_models = False  # safe default
            state.gate_reason = "check_status_failed_safe_default"

        self.state = state
        return state

    def _load_progress(self) -> Tuple[int, int]:
        """
        Load accumulated_rows and attempt_count from ACM_ColdstartState.

        Separated from the load-path gate so that progress tracking is
        independent of the model-existence check.

        Returns:
            (accumulated_rows, attempt_count) — both default to 0 on error or no row.
        """
        try:
            with self.sql_client.cursor() as cur:
                cur.execute(
                    "SELECT AccumulatedRows, AttemptCount FROM dbo.ACM_ColdstartState "
                    "WHERE EquipID = ? AND Stage = ?",
                    (self.equip_id, _COLDSTART_PROGRESS_STAGE)
                )
                row = cur.fetchone()
            if row:
                return int(row[0] or 0), int(row[1] or 0)
        except Exception as e:
            Console.warn(
                f"Could not read coldstart progress from ACM_ColdstartState: {e}. "
                "Progress counters will reset to zero for this batch.",
                component="COLDSTART",
                equip_id=self.equip_id,
                stage=_COLDSTART_PROGRESS_STAGE,
                error_type=type(e).__name__,
            )
        return 0, 0
    
    def detect_data_cadence(self, table_name: str, sample_hours: int = 24) -> Optional[int]:
        """
        Detect cadence using RECENT data (not earliest). Uses last `sample_hours` of data
        and computes the most common positive interval (mode) in seconds.

        Returns:
            cadence_seconds or None
        """
        cur = None
        try:
            cur = self.sql_client.cursor()

            # Find recent window anchored on MAX timestamp
            cur.execute(f"SELECT MAX(EntryDateTime) FROM dbo.{table_name}")
            row = cur.fetchone()
            if not row or not row[0]:
                Console.warn(
                    "Cadence detection: no MAX timestamp found",
                    component="COLDSTART", equip_id=self.equip_id, equip_name=self.equip_name, table=table_name
                )
                return None

            max_ts = row[0]
            min_ts = max_ts - timedelta(hours=int(sample_hours))

            # Pull a dense sample from the recent window; DESC first then reverse
            cur.execute(
                f"""
                SELECT TOP 500 EntryDateTime
                FROM dbo.{table_name}
                WHERE EntryDateTime >= ? AND EntryDateTime <= ?
                ORDER BY EntryDateTime DESC
                """,
                (min_ts, max_ts)
            )
            rows = cur.fetchall()
            if not rows or len(rows) < 10:
                Console.warn(
                    f"Cadence detection: insufficient recent rows ({len(rows) if rows else 0})",
                    component="COLDSTART", equip_id=self.equip_id, equip_name=self.equip_name,
                    table=table_name, sample_hours=sample_hours
                )
                return None

            timestamps = [r[0] for r in rows][::-1]  # ascending
            intervals = []
            for i in range(1, len(timestamps)):
                delta = (timestamps[i] - timestamps[i - 1]).total_seconds()
                if delta > 0:
                    intervals.append(delta)

            if not intervals:
                return None

            from collections import Counter
            most_common = Counter(intervals).most_common(1)[0][0]
            cadence_s = int(most_common)

            Console.info(
                f"Detected data cadence: {cadence_s} seconds ({cadence_s/60:.1f} minutes)",
                component="COLDSTART", equip_id=self.equip_id, equip_name=self.equip_name, table=table_name
            )
            return cadence_s

        except Exception as e:
            Console.error(
                f"Failed to detect cadence: {e}",
                component="COLDSTART", equip_id=self.equip_id, equip_name=self.equip_name,
                table=table_name, sample_hours=sample_hours, error_type=type(e).__name__, error=str(e)[:200]
            )
            return None
        finally:
            try:
                if cur:
                    cur.close()
            except Exception:
                pass



    def calculate_optimal_window(self, 
                                current_window_end: datetime,
                                required_rows: int = 500,
                                data_cadence_seconds: Optional[int] = None,
                                expansion_factor: float = 1.0) -> Tuple[datetime, datetime]:
        """
        Calculate optimal lookback window to get required_rows of data.
        For coldstart, we want to load the EARLIEST available data, not recent data.
        
        Args:
            current_window_end: End time for the data window (batch end time) - not used for coldstart
            required_rows: Target number of rows needed
            data_cadence_seconds: Detected data cadence, or None to auto-detect
            expansion_factor: Multiplier to expand window (>1.0 for retries with sparse data)
            
        Returns:
            Tuple of (start_time, end_time) for expanded window
        """
        # Auto-detect cadence if not provided
        if data_cadence_seconds is None:
            table_name = f"{self.equip_name}_Data"
            data_cadence_seconds = self.detect_data_cadence(table_name)
            
            if data_cadence_seconds is None:
                # Fallback: assume 1 minute cadence
                data_cadence_seconds = 60
                Console.warn(
                    f"Data cadence could not be auto-detected from {table_name}. "
                    f"Assuming {data_cadence_seconds}s ({data_cadence_seconds/60:.0f} min) per reading. "
                    "If this is wrong, the coldstart window will be incorrectly sized.",
                    component="COLDSTART",
                    equip_id=self.equip_id,
                    equip_name=self.equip_name,
                    table=table_name,
                    default_cadence_s=data_cadence_seconds,
                )
        
        # Calculate how many minutes needed to get required_rows
        cadence_minutes = data_cadence_seconds / 60
        # Formula: if cadence is 30min per row, need 500 rows * 30min = 15000 minutes
        required_minutes = required_rows * cadence_minutes
        
        # Add 20% buffer for safety
        required_minutes = int(required_minutes * 1.2)
        
        # Apply expansion factor (for retries with sparse data)
        required_minutes = int(required_minutes * expansion_factor)
        
        # For coldstart, get the EARLIEST data available
        # Query the database for the earliest timestamp
        table_name = f"{self.equip_name}_Data"
        cur = None
        try:
            cur = self.sql_client.conn.cursor()
            query = f"SELECT MIN(EntryDateTime) FROM {table_name}"
            cur.execute(query)
            row = cur.fetchone()
            
            if row and row[0]:
                start_time = row[0]
                # Add required minutes to get end time
                end_time = start_time + timedelta(minutes=required_minutes)
                
                Console.info(
                    f"Coldstart window: {start_time} → +{required_minutes} min ({required_minutes/60:.1f} h). "
                    f"Expected ~{int(required_minutes / cadence_minutes)} rows at {cadence_minutes:.1f} min/row (target: {required_rows}).",
                    component="COLDSTART",
                )
                
                return start_time, end_time
            else:
                # Fallback: use lookback from current time if no data found
                Console.warn(
                    f"No data found in {table_name}. Falling back to lookback from current batch end "
                    f"({required_minutes} min / {required_minutes/60:.1f} h). "
                    "Coldstart may fail if the historian table is empty.",
                    component="COLDSTART",
                    equip_id=self.equip_id,
                    equip_name=self.equip_name,
                    table=table_name,
                    required_rows=required_rows,
                    lookback_minutes=required_minutes,
                )
                end_time = current_window_end
                start_time = end_time - timedelta(minutes=required_minutes)
                return start_time, end_time
                
        except Exception as e:
            Console.error(
                f"Failed to query earliest timestamp from {table_name}: {e}. "
                "Falling back to lookback window from current batch end.",
                component="COLDSTART",
                equip_id=self.equip_id,
                equip_name=self.equip_name,
                table=table_name,
                required_rows=required_rows,
                error_type=type(e).__name__,
                error=str(e)[:200],
            )
            # Fallback: lookback from current time
            end_time = current_window_end
            start_time = end_time - timedelta(minutes=required_minutes)
            return start_time, end_time
        finally:
            if cur:
                try:
                    cur.close()
                except:
                    pass
    def load_window(
        self,
        cfg: Dict[str, Any],
        start_time: Optional[pd.Timestamp],
        end_time: Optional[pd.Timestamp],
        output_manager,
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[Any], bool]:
        """
        Returns (train, score, meta, can_proceed).

        Contract:
        - can_proceed=True  => train/score/meta are valid and downstream scoring should run.
        - can_proceed=False => NOOP. meta will contain meta.noop_reason (or dict key) describing why.
        """
        required_rows = int(cfg.get("runtime", {}).get("coldstart_required_rows", 500))
        state = self.check_status(required_rows=required_rows)

        # ---------------------------------------------------------------------
        # Scoring path: models exist -> load data for scoring (not coldstart)
        # ---------------------------------------------------------------------
        if state.use_existing_models:
            train, score, meta, ok = self._load_data_window(
                output_manager=output_manager,
                cfg=cfg,
                start=start_time,
                end=end_time,
                is_coldstart=False,
            )
            if ok and train is not None and score is not None:
                if meta is None:
                    meta = {}
                if isinstance(meta, dict):
                    meta["noop_reason"] = ""
                    meta["is_coldstart_run"] = False
                else:
                    setattr(meta, "noop_reason", "")
                    setattr(meta, "is_coldstart_run", False)
                return train, score, meta, True

            # NOOP: models exist but no usable data
            if meta is None:
                meta = {}
            if isinstance(meta, dict):
                meta["noop_reason"] = "SCORING_NO_DATA"
                meta["is_coldstart_run"] = False
            else:
                setattr(meta, "noop_reason", "SCORING_NO_DATA")
                setattr(meta, "is_coldstart_run", False)
            return None, None, meta, False

        # ---------------------------------------------------------------------
        # COLDSTART path: Sequential windowing respecting batch windows
        # Load data WITHIN the provided time window, accumulating across batches
        # When max_batches is set, each batch processes one sequential chunk
        # Do NOT go back to earliest data - use the provided window!
        # ---------------------------------------------------------------------
        
        # Use the BATCH WINDOW provided, not earliest-based calculation
        # The batch runner already divided data into chunks; respect that!
        cs_start = start_time
        cs_end = end_time
        
        if cs_start is None or cs_end is None:
            # Fallback if no window provided
            window_end_dt = (
                end_time.to_pydatetime()
                if isinstance(end_time, pd.Timestamp)
                else pd.Timestamp.utcnow().to_pydatetime()
            )
            cs_start_dt, cs_end_dt = self.calculate_optimal_window(
                current_window_end=window_end_dt,
                required_rows=required_rows,
                data_cadence_seconds=None,
                expansion_factor=1.0,
            )
            cs_start = pd.Timestamp(cs_start_dt)
            cs_end = pd.Timestamp(cs_end_dt)
        else:
            # Convert to datetime for _update_progress
            cs_start_dt = cs_start.to_pydatetime() if isinstance(cs_start, pd.Timestamp) else cs_start
            cs_end_dt = cs_end.to_pydatetime() if isinstance(cs_end, pd.Timestamp) else cs_end

        # COLDSTART path — single attempt for this batch window.
        # The batch runner drives batch-to-batch progression; this helper
        # should not retry internally.
        train, score, meta, ok = self._load_data_window(
            output_manager=output_manager,
            cfg=cfg,
            start=cs_start,
            end=cs_end,
            is_coldstart=True,
        )

        if not ok or train is None or score is None:
            self._update_progress(
                rows_received=0,
                data_start=cs_start_dt,
                data_end=cs_end_dt,
                error_message="COLDSTART_WINDOW_NOT_USABLE",
                success=False,
            )
            meta_out = {"noop_reason": "COLDSTART_DEFERRED", "is_coldstart_run": True}
            return None, None, meta_out, False

        rows_in_window = int(len(train) + len(score))

        # Delta to avoid double-counting if the batch window overlaps prior progress
        delta_rows = max(0, rows_in_window - int(state.accumulated_rows or 0))
        self._update_progress(
            rows_received=delta_rows,
            data_start=cs_start_dt,
            data_end=cs_end_dt,
            error_message=None if rows_in_window >= required_rows else "INSUFFICIENT_ROWS",
            success=(rows_in_window >= required_rows),
        )

        if rows_in_window >= required_rows:
            if meta is None:
                meta = {}
            if isinstance(meta, dict):
                meta["noop_reason"] = ""
                meta["is_coldstart_run"] = True
                meta["coldstart_rows"] = rows_in_window
                meta["coldstart_required_rows"] = required_rows
                meta["coldstart_window_start"] = str(cs_start)
                meta["coldstart_window_end"] = str(cs_end)
            else:
                setattr(meta, "noop_reason", "")
                setattr(meta, "is_coldstart_run", True)
            return train, score, meta, True

        # Insufficient rows in this batch window — defer to next batch
        meta_out = {
            "noop_reason": "COLDSTART_DEFERRED",
            "is_coldstart_run": True,
            "coldstart_rows": rows_in_window,
            "coldstart_required_rows": required_rows,
            "coldstart_window_start": str(cs_start),
            "coldstart_window_end": str(cs_end),
        }
        return None, None, meta_out, False

    def _load_data_window(
        self,
        output_manager,
        cfg: Dict[str, Any],
        start: Optional[pd.Timestamp],
        end: Optional[pd.Timestamp],
        is_coldstart: bool = False,
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[Any], bool]:
        """
        Helper to load a specific window.

        Returns (train, score, meta, ok) where:
        - ok=True  => load succeeded and train/score/meta are present
        - ok=False => expected NOOP (no data / insufficient data) OR unexpected failure

        IMPORTANT:
        - Expected "no data"/"insufficient data" should be WARN (not ERROR),
        because they are valid NOOP conditions during scoring/coldstart.
        """
        try:
            train, score, meta = output_manager._load_data_from_sql(
                cfg, self.equip_name, start, end, is_coldstart=is_coldstart
            )
            return train, score, meta, True

        except ValueError as e:
            # Expected: no data / insufficient data in this window
            msg = str(e)
            Console.warn(
                f"Data window not usable: {msg}",
                component="COLDSTART",
                equip_id=self.equip_id,
                equip_name=self.equip_name,
                start_time=str(start),
                end_time=str(end),
                is_coldstart=is_coldstart,
            )
            return None, None, None, False

        except Exception as e:
            # Unexpected: real failure
            Console.error(
                f"Failed to load data window: {e}",
                component="COLDSTART",
                equip_id=self.equip_id,
                equip_name=self.equip_name,
                start_time=str(start),
                end_time=str(end),
                is_coldstart=is_coldstart,
                error_type=type(e).__name__,
                error=str(e)[:200],
            )
            return None, None, None, False

    #End Load Data Window Here    
    def _update_progress(self, 
                            rows_received: int,
                            data_start: datetime,
                            data_end: datetime,
                            error_message: Optional[str] = None,
                            success: bool = False):
            """Update coldstart progress in database."""
            try:
                cur = self.sql_client.cursor()
                cur.execute(
                    "EXEC dbo.usp_ACM_UpdateColdstartProgress @EquipID=?, @Stage=?, @RowsReceived=?, "
                    "@DataStartTime=?, @DataEndTime=?, @ErrorMessage=?, @Success=?",
                    (
                        self.equip_id,
                        _COLDSTART_PROGRESS_STAGE,
                        rows_received,
                        data_start,
                        data_end,
                        error_message,
                        success,
                    )
                )
                self.sql_client.conn.commit()
            except Exception as e:
                Console.error(
                    f"Failed to persist coldstart progress to ACM_ColdstartState: {e}. "
                    "Row accumulation count will not be saved; next batch will re-count from scratch.",
                    component="COLDSTART",
                    equip_id=self.equip_id,
                    stage=_COLDSTART_PROGRESS_STAGE,
                    rows_received=rows_received,
                    error_type=type(e).__name__,
                    error=str(e)[:200],
                )
            finally:
                try:
                    cur.close()
                except:
                    pass

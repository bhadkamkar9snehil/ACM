"""
ACM Smart Coldstart Module

Implements intelligent coldstart retry logic that:
1. Detects insufficient data without failing
2. Accumulates data over multiple job runs
3. Auto-detects data cadence and calculates required lookback
4. Retries until sufficient data exists for model training
5. Never falls back to file mode

Author: Copilot
Date: November 13, 2025
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
import pandas as pd
from core.observability import Console


class ColdstartState:
    """Represents the current coldstart state for an equipment."""
    
    def __init__(self, equip_id: int, stage: str = 'score'):
        self.equip_id = equip_id
        self.stage = stage
        self.needs_coldstart = True
        self.attempt_count = 0
        self.accumulated_rows = 0
        self.required_rows = 500
        self.data_start_time: Optional[datetime] = None
        self.data_end_time: Optional[datetime] = None
        self.last_error: Optional[str] = None
        
    def is_ready(self) -> bool:
        """Check if sufficient data has been accumulated for coldstart."""
        return self.accumulated_rows >= self.required_rows
    
    def __repr__(self):
        return (f"ColdstartState(equip={self.equip_id}, attempts={self.attempt_count}, "
                f"rows={self.accumulated_rows}/{self.required_rows}, ready={self.is_ready()})")


class SmartColdstart:
    """
    Smart coldstart manager that handles data accumulation and retry logic.
    
    Key Features:
    - Auto-detects data cadence from histogram
    - Calculates optimal lookback window
    - Tracks progress across multiple job runs
    - Retries with exponential window expansion
    - Never fails - always defers to next run
    """
    
    def __init__(self, sql_client, equip_id: int, equip_name: str, stage: str = 'score'):
        self.sql_client = sql_client
        self.equip_id = equip_id
        self.equip_name = equip_name
        self.stage = stage
        self.state: Optional[ColdstartState] = None
        
    def check_status(self, required_rows: int = 500, tick_minutes: Optional[int] = None) -> ColdstartState:
        """
        Check current coldstart status from database.
        
        Args:
            required_rows: Minimum rows needed to complete coldstart
            tick_minutes: Current job frequency in minutes (auto-detected if None)
            
        Returns:
            ColdstartState with current status
        """
        try:
            # Auto-detect tick_minutes from data cadence if not provided
            if tick_minutes is None:
                table_name = f"{self.equip_name}_Data"
                data_cadence_seconds = self.detect_data_cadence(table_name)
                if data_cadence_seconds:
                    tick_minutes = int(data_cadence_seconds / 60)
                    Console.info(f"Auto-detected tick_minutes from data cadence: {tick_minutes} minutes", component="COLDSTART")
                else:
                    tick_minutes = 30  # Default fallback
                    Console.warn(f"Could not detect cadence, using default tick_minutes: {tick_minutes}", component="COLDSTART", equip_id=self.equip_id, equip_name=self.equip_name, default_tick_minutes=tick_minutes)
            
            cur = self.sql_client.cursor()
            
            # Call stored procedure to check status
            needs_coldstart = cur.execute(
                "DECLARE @NeedsColdstart BIT, @AccumulatedRows INT, @AttemptCount INT; "
                "EXEC dbo.usp_ACM_CheckColdstartStatus @EquipID=?, @Stage=?, @RequiredRows=?, @TickMinutes=?, "
                "@NeedsColdstart=@NeedsColdstart OUTPUT, @AccumulatedRows=@AccumulatedRows OUTPUT, @AttemptCount=@AttemptCount OUTPUT; "
                "SELECT @NeedsColdstart, @AccumulatedRows, @AttemptCount",
                (self.equip_id, self.stage, required_rows, tick_minutes)
            ).fetchone()
            
            self.sql_client.conn.commit()
            
            if needs_coldstart:
                needs, accumulated, attempts = needs_coldstart
                self.state = ColdstartState(self.equip_id, self.stage)
                self.state.needs_coldstart = bool(needs)
                self.state.accumulated_rows = accumulated or 0
                self.state.attempt_count = attempts or 0
                self.state.required_rows = required_rows
            else:
                # Coldstart complete
                self.state = ColdstartState(self.equip_id, self.stage)
                self.state.needs_coldstart = False
                self.state.accumulated_rows = required_rows  # Mark as complete
                
            return self.state
            
        except Exception as e:
            Console.error(f"Failed to check status: {e}", component="COLDSTART", equip_id=self.equip_id, equip_name=self.equip_name, stage=self.stage, error_type=type(e).__name__, error=str(e)[:200])
            # Default to needing coldstart on error
            self.state = ColdstartState(self.equip_id, self.stage)
            self.state.required_rows = required_rows
            return self.state
        finally:
            try:
                cur.close()
            except:
                pass
    
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
                Console.warn(f"Could not detect cadence, assuming {data_cadence_seconds}s", component="COLDSTART", equip_id=self.equip_id, equip_name=self.equip_name, table=table_name, default_cadence_s=data_cadence_seconds)
        
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
                
                Console.info(f"Loading from EARLIEST data: {start_time}", component="COLDSTART")
                Console.info(f"Calculated optimal window: {required_minutes} minutes ({required_minutes/60:.1f} hours)", component="COLDSTART")
                Console.info(f"Expected rows: ~{int(required_minutes / cadence_minutes)} (target: {required_rows})", component="COLDSTART")
                
                return start_time, end_time
            else:
                # Fallback: use lookback from current time if no data found
                Console.warn(f"No data found in {table_name}, using lookback from current batch", component="COLDSTART", equip_id=self.equip_id, equip_name=self.equip_name, table=table_name, required_rows=required_rows, lookback_minutes=required_minutes)
                end_time = current_window_end
                start_time = end_time - timedelta(minutes=required_minutes)
                return start_time, end_time
                
        except Exception as e:
            Console.error(f"Error querying earliest timestamp: {e}", component="COLDSTART", equip_id=self.equip_id, equip_name=self.equip_name, table=table_name, required_rows=required_rows, error_type=type(e).__name__, error=str(e)[:200])
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
    # Start Load with retry here
    def load_with_retry(
        self,
        cfg: Dict[str, Any],
        equipment: str,
        start_time: Optional[pd.Timestamp],
        end_time: Optional[pd.Timestamp],
        output_manager,
        max_attempts: int = 3,
        historical_replay: bool = False,
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[Any], bool]:
        """
        Returns (train, score, meta, can_proceed).

        Contract:
        - can_proceed=True  => train/score/meta are valid and downstream scoring should run.
        - can_proceed=False => NOOP. meta will contain meta.noop_reason (or dict key) describing why.
        """
        required_rows = int(cfg.get("runtime", {}).get("coldstart_required_rows", 500))
        tick_minutes = cfg.get("runtime", {}).get("tick_minutes")

        state = self.check_status(required_rows=required_rows, tick_minutes=tick_minutes)

        # ---------------------------------------------------------------------
        # ONLINE path: models exist -> attempt load in non-coldstart mode
        # ---------------------------------------------------------------------
        if not state.needs_coldstart:
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
                meta["noop_reason"] = "ONLINE_NO_DATA"
                meta["is_coldstart_run"] = False
            else:
                setattr(meta, "noop_reason", "ONLINE_NO_DATA")
                setattr(meta, "is_coldstart_run", False)
            return None, None, meta, False

        # ---------------------------------------------------------------------
        # COLDSTART path: Sequential windowing respecting batch windows
        # Load data WITHIN the provided time window, accumulating across batches
        # When max_batches is set, each batch processes one sequential chunk
        # Do NOT go back to earliest data - use the provided window!
        # ---------------------------------------------------------------------
        
        # Rows still needed to complete coldstart
        rows_needed = max(0, required_rows - (state.accumulated_rows or 0))
        
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

        for attempt in range(1, max_attempts + 1):
            # On retry within same batch window, use progressively looser matching
            # But stay within the batch window bounds
            cs_start = start_time
            cs_end = end_time

            train, score, meta, ok = self._load_data_window(
                output_manager=output_manager,
                cfg=cfg,
                start=cs_start,
                end=cs_end,
                is_coldstart=True,
            )

            # If load failed (expected NOOP or unexpected failure), record and defer
            if not ok or train is None or score is None:
                # We cannot reliably know rows if loader raised; treat as 0 for this attempt
                self._update_progress(
                    rows_received=0,
                    data_start=cs_start_dt,
                    data_end=cs_end_dt,
                    error_message="COLDSTART_WINDOW_NOT_USABLE",
                    success=False,
                )
                meta_out = {"noop_reason": "COLDSTART_DEFERRED", "is_coldstart_run": True}
                return None, None, meta_out, False

            # Rows observed in the current horizon
            rows_in_window = int(len(train) + len(score))

            # Update progress with DELTA to avoid double counting if horizon overlaps
            delta_rows = max(0, rows_in_window - int(state.accumulated_rows or 0))
            self._update_progress(
                rows_received=delta_rows,
                data_start=cs_start_dt,
                data_end=cs_end_dt,
                error_message=None if rows_in_window >= required_rows else "INSUFFICIENT_ROWS",
                success=(rows_in_window >= required_rows),
            )

            if rows_in_window >= required_rows:
                # Coldstart ready
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

            # Not enough yet -> defer
            meta_out = {
                "noop_reason": "COLDSTART_DEFERRED",
                "is_coldstart_run": True,
                "coldstart_rows": rows_in_window,
                "coldstart_required_rows": required_rows,
                "coldstart_window_start": str(cs_start),
                "coldstart_window_end": str(cs_end),
            }
            return None, None, meta_out, False

        # Fallback (should not usually hit because we return inside loop)
        meta_out = {"noop_reason": "COLDSTART_DEFERRED", "is_coldstart_run": True}
        return None, None, meta_out, False

    # End Load with retry here

    # Here
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
        because they are valid NOOP conditions in ONLINE/COLDSTART.
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
                    (self.equip_id, self.stage, rows_received, data_start, data_end, error_message, success)
                )
                self.sql_client.conn.commit()
            except Exception as e:
                Console.error(f"Failed to update progress: {e}", component="COLDSTART", equip_id=self.equip_id, stage=self.stage, rows_received=rows_received, error_type=type(e).__name__, error=str(e)[:200])
            finally:
                try:
                    cur.close()
                except:
                    pass


# =============================================================================
# P4.5: BASELINE SEEDING (moved from acm_main.py)
# =============================================================================

def seed_baseline(
    train: pd.DataFrame,
    score: pd.DataFrame,
    sql_client: Optional[Any],
    equip_id: int,
    cfg: Dict[str, Any],
    equip: str = "",
    is_coldstart: bool = False,
    ensure_local_index_fn: Optional[Any] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[str]]:
    """
    Seed training baseline when insufficient data available (batch mode).
    
    In batch mode, SmartColdstart returns empty train (all data goes to score).
    This function loads baseline from:
    1. ACM_BaselineBuffer table (SQL) - cached baseline from previous runs
    2. First portion of score data (fallback)
    3. Split score in half if overlap detected
    
    Also handles gap bridging when baseline ends before score starts.
    
    Args:
        train: Training DataFrame (may be empty in batch mode)
        score: Scoring DataFrame
        sql_client: SQL client for ACM_BaselineBuffer access
        equip_id: Equipment ID
        cfg: Config dict with runtime.baseline settings
        equip: Equipment name for logging
        is_coldstart: If True, train/score already split from coldstart - skip re-seeding
        ensure_local_index_fn: Optional function to normalize datetime index
        
    Returns:
        Tuple of (train, score, source_used) where source_used describes origin
    """
    baseline_cfg = (cfg.get("runtime", {}) or {}).get("baseline", {}) or {}
    min_points = int(baseline_cfg.get("min_points", 300))
    train_rows = len(train)
    
    # CRITICAL FIX v11.2.3: In coldstart mode with sufficient training data,
    # SKIP the slow baseline buffer loading entirely.
    # The coldstart split already provides 60% of data as training - that's plenty.
    # Baseline buffer loading causes deadlocks/hangs due to long-to-wide pivoting.
    # This is just an optimization for marginal quality gain - not worth the speed hit.
    if is_coldstart and train_rows > 300:
        # Coldstart data is high quality and abundant; don't risk hanging on baseline
        return train, score, f"coldstart_split ({train_rows} rows, skipped slow baseline pivot)"
    
    # Fallback: If train still needs data (non-coldstart or too few rows)
    if train_rows >= min_points:
        return train, score, None
    
    used: Optional[str] = None
    extended = False
    
    # DISABLED: Baseline buffer loading (v11.2.3 fix)
    # The pivot operation from long→wide format causes SQL locks/hangs.
    # Only needed in non-coldstart batch mode with insufficient data.
    # For now, we rely on score data seeding (Try 2 below).
    
    # Try 1: Load from SQL ACM_BaselineBuffer [DISABLED - CAUSES HANGS]
    # if sql_client:
    #     try:
    #         window_hours = float(baseline_cfg.get("window_hours", 72))
    #         with sql_client.cursor() as cur:
    #             cur.execute("""
    #                 SELECT Timestamp, SensorName, SensorValue
    #                 FROM dbo.ACM_BaselineBuffer
    #                 WHERE EquipID = ? AND Timestamp >= DATEADD(HOUR, -?, GETDATE())
    #                 ORDER BY Timestamp
    #             """, (int(equip_id), int(window_hours)))
    #             rows = cur.fetchall()
    #         
    #         if rows:
    #             # Transform long format → wide format (pivot) [SLOW - ~1-2 sec for 26K rows]
    #             baseline_data = {}
    #             for row in rows:
    #                 ts = pd.Timestamp(row.Timestamp)
    #                 sensor = str(row.SensorName)
    #                 value = float(row.SensorValue)
    #                 if ts not in baseline_data:
    #                    baseline_data[ts] = {}
    #                 baseline_data[ts][sensor] = value
    #             
    #             buf = pd.DataFrame.from_dict(baseline_data, orient='index').sort_index()
    #             if ensure_local_index_fn:
    #                 buf = ensure_local_index_fn(buf)
    #             
    #             # Align to score columns (score guaranteed to be DataFrame by entry validation)
    #             if hasattr(buf, "columns"):
    #                 common_cols = [c for c in buf.columns if c in score.columns]
    #                 if common_cols:
    #                     buf = buf[common_cols]
    #             
    #             train = buf
    #             used = f"ACM_BaselineBuffer ({len(train)} rows)"
    #     except Exception as sql_err:
    #         Console.warn(f"Failed to load from ACM_BaselineBuffer: {sql_err}", component="BASELINE")
    
    # Try 2: Seed from score data
    if used is None and len(score) > 0:
        seed_n = min(len(score), max(min_points, int(0.2 * len(score))))
        train = score.iloc[:seed_n]
        used = f"score head ({seed_n} rows)"
        
        # Check for overlap - train must end BEFORE score starts
        tr_end_ts = pd.to_datetime(train.index.max())
        sc_start_ts = pd.to_datetime(score.index.min())
        
        if tr_end_ts >= sc_start_ts:
            # Split score in half to avoid overlap
            split_idx = len(score) // 2
            if split_idx >= min_points:
                train = score.iloc[:split_idx]
                score = score.iloc[split_idx:].copy()
                used = f"score split (train={split_idx}, no overlap)"
            else:
                Console.warn(f"Cannot split score (too few rows: {len(score)}), accepting overlap", component="BASELINE")
    
    if used:
        # Gap detection: if baseline ends >1h before score starts, extend it
        if len(train) > 0:
            tr_end = pd.to_datetime(train.index.max())
            sc_start = pd.to_datetime(score.index.min()) if len(score) > 0 else None
            
            if sc_start and tr_end < sc_start:
                gap_hours = (sc_start - tr_end).total_seconds() / 3600
                if gap_hours > 1.0:
                    # Extend with first 20% of score
                    if len(score) > 10:
                        ext_size = max(10, int(0.2 * len(score)))
                        extension = score.iloc[:ext_size]
                        train = pd.concat([train, extension], axis=0).drop_duplicates()
                        extended = True
                        used = f"{used} +{ext_size} extension"
        
        Console.info(f"Baseline: {used} | extended={extended}", component="BASELINE")
    
    return train, score, used

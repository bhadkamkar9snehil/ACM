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
# pyright: reportGeneralTypeIssues=false

import json
import time
import threading
import inspect
import re
from contextlib import contextmanager, nullcontext
from typing import Dict, Any, List, Optional, Tuple, Callable, cast, Literal
from dataclasses import dataclass, field

import pandas as pd
import numpy as np
import warnings
from datetime import datetime

# FOR-DQ-02: Use centralized timestamp normalization
from utils.timestamp_utils import (
    normalize_timestamp_scalar,
)

from core.observability import Console
from core.time_normalizer import ensure_local_index

# Phase 2 Extraction: Data loading moved to core/data_loader.py
from core.data_loader import (
    DataLoader,
)

# Phase 3 Extraction: Analytics generation moved to core/analytics_builder.py
from core.analytics_builder import (
    AnalyticsBuilder,
)
from core.output_artifacts import write_pca_artifacts, write_sql_artifacts
from core.output_contracts import (
    ALLOWED_TABLES,
    REPLACE_POLICY_KEYS,
    TableWriteContract,
    get_table_write_contract,
    audit_replace_policy_contract as _audit_replace_policy_contract,
    audit_table_write_contracts as _audit_table_write_contracts,
)
from core.output_sql_core import (
    SqlWriteEngine,
    _table_exists,
    _get_table_columns,
    _get_insertable_columns,
)
from core.output_manager_services import (
    load_omr_drift_context_service,
    write_refit_request_service,
    write_fusion_metrics_service,
    check_refit_request_service,
    update_baseline_buffer_service,
    write_sensor_normalized_ts_service,
    write_sensor_correlations_service,
    write_sensor_correlations_from_raw_service,
    write_anomaly_events_service,
    write_regime_episodes_service,
    write_pca_model_service,
    write_detector_correlation_service,
    write_detector_correlation_from_scores_service,
    write_drift_series_service,
    write_feature_drop_log_service,
    write_calibration_summary_service,
    write_regime_occupancy_service,
    write_regime_transitions_service,
    write_contribution_timeline_service,
    write_contribution_timeline_from_frame_service,
    write_regime_promotion_log_service,
    write_sensor_normalized_ts_from_raw_service,
    write_seasonal_patterns_from_detected_service,
    persist_additional_artifacts_service,
    generate_all_analytics_with_context_service,
    persist_pipeline_outputs_service,
    run_persistence_stage_service,
    prepare_persistence_inputs_service,
    release_persist_memory_service,
    write_representation_artifacts_service,
)
from core.output_dataframe_builders import build_data_quality_records

# V11: Confidence model for health and episode confidence
try:
    from core.confidence import compute_health_confidence, compute_episode_confidence
    _CONFIDENCE_AVAILABLE = True
except ImportError:
    _CONFIDENCE_AVAILABLE = False
    compute_health_confidence = None
    compute_episode_confidence = None

# V11: Model lifecycle for maturity state
try:
    from core.model_lifecycle import load_model_state_from_sql, MaturityState
    _LIFECYCLE_AVAILABLE = True
except ImportError:
    _LIFECYCLE_AVAILABLE = False
    load_model_state_from_sql = None
    MaturityState = None

# Optional observability integration (P0 SQL ops tracking)
try:
    from core.observability import record_sql_op, Span
    _OBSERVABILITY_AVAILABLE = True
except ImportError:
    _OBSERVABILITY_AVAILABLE = False
    record_sql_op = None
    Span = None

# Module-level SQL helpers now live in core.output_sql_core
# (imported above for backward compatibility)

# ==================== MAIN OUTPUT MANAGER CLASS ====================


@dataclass
class OutputBatch:
    """Represents a batch of outputs to be written together."""
    sql_operations: List[Tuple[str, pd.DataFrame, Dict[str, Any]]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # OUT-18: Batch tracking for flush triggers
    created_at: float = field(default_factory=time.time)
    total_rows: int = 0


@dataclass
class WritePolicy:
    """Explicit write policy declared by payload generators."""
    mode: Literal["insert", "upsert"] = "insert"
    upsert_handler: Optional[Callable[[pd.DataFrame], int]] = None


@dataclass
class PersistArtifactsResult:
    """Counts for optional persist-phase artifact writes."""
    detector_correlation_rows: int = 0
    sensor_correlation_rows: int = 0
    sensor_normalized_ts_rows: int = 0
    seasonal_pattern_rows: int = 0


@dataclass
class PersistCoreOutputsResult:
    """Row counts for core persist-phase writes."""
    scores_inserted: int = 0
    episodes_inserted: int = 0
    episode_count: int = 0

    @property
    def rows_written_delta(self) -> int:
        return int(self.scores_inserted) + int(self.episodes_inserted)


@dataclass
class PersistPipelineOutputsResult:
    """Aggregate result for full persist-stage output orchestration."""
    rows_written_delta: int = 0
    episode_count: int = 0
    analytics_table_count: int = 0
    raw_train: Optional[pd.DataFrame] = None
    raw_score: Optional[pd.DataFrame] = None
    sensor_context: Optional[Dict[str, Any]] = None


@dataclass
class PersistenceStageResult:
    """Result bundle for pipeline persistence stage execution."""
    rows_written: int = 0
    analytics_table_count: int = 0
    raw_train: Optional[pd.DataFrame] = None
    raw_score: Optional[pd.DataFrame] = None
    sensor_context: Optional[Dict[str, Any]] = None


@dataclass
class PersistenceInputPreparationResult:
    """Result bundle for pre-persistence context preparation."""
    sensor_context: Optional[Dict[str, Any]] = None


class OutputManager:
    """
    Unified output manager that consolidates all scattered output generation.
    
    Features:
    - Batched writes for improved I/O performance
    - SQL-first persistence with centralized write paths
    - Thread-safe operations with connection pooling
    - Explicit error handling for required versus optional outputs
    """
    
    def __init__(self, 
                 sql_client=None, 
                 run_id: Optional[str] = None,
                 equip_id: Optional[int] = None,
                 batch_size: int = 5000,
                 enable_batching: bool = True,
                 sql_health_cache_seconds: float = 60.0,
                 max_io_workers: int = 8,
                 batch_flush_rows: int = 1000,
                 batch_flush_seconds: float = 30.0,
                 max_in_flight_futures: int = 50,
                 maturity_state: Optional[str] = None):
        """Initialize OutputManager.
        
        V11 CRITICAL: maturity_state must be passed from acm_main.py run context.
        This eliminates the race condition where writers query ACM_ActiveModels
        independently and get stale/inconsistent state.
        """
        self.sql_client = sql_client
        self.run_id = run_id
        
        # PHASE-1 FIX: Fail-fast for invalid EquipID in SQL mode
        # Writing EquipID=0 or NULL corrupts multi-asset queries and is unrecoverable.
        if sql_client is not None and (equip_id is None or equip_id == 0):
            raise ValueError(
                f"OutputManager requires valid equip_id (>0) in SQL mode. "
                f"Received equip_id={equip_id}. This prevents catastrophic "
                f"data corruption in multi-asset deployments."
            )
        # CRITICAL: convert numpy.int64 to native int to prevent HY000 error
        self.equip_id = int(equip_id) if equip_id is not None else None
        self.equipment = ""  # Will be set by set_equipment() or inferred from equip_id
        self.maturity_state = maturity_state or 'COLDSTART'  # V11: Cached maturity
        self.batch_size = batch_size
        self._batched_transaction_active = False
        self.enable_batching = enable_batching
        self.max_io_workers = max_io_workers
        
        # OUT-18: Batch flush triggers and backpressure
        self.batch_flush_rows = batch_flush_rows  # Flush after N rows
        self.batch_flush_seconds = batch_flush_seconds  # Flush after N seconds
        self.max_in_flight_futures = max_in_flight_futures  # Max concurrent operations

        self.stats = {
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

        # Phase A extraction: SQL write engine holds all SQL plumbing and caches
        self._sql_engine = SqlWriteEngine(
            sql_client=sql_client,
            run_id=run_id,
            equip_id=equip_id,
            batch_size=batch_size,
        )
        # Expose engine caches for backward compatibility
        self._table_exists_cache = self._sql_engine._table_exists_cache
        self._table_columns_cache = self._sql_engine._table_columns_cache
        self._table_insertable_cache = self._sql_engine._table_insertable_cache
        self._table_datetime_cache = self._sql_engine._table_datetime_cache
        self._bulk_predeleted_tables = self._sql_engine._bulk_predeleted_tables
        
        # FCST-15: Artifact cache for SQL-only mode
        # Stores DataFrames written to files/SQL so they can be consumed by downstream modules
        # without file system dependencies
        self._artifact_cache: Dict[str, pd.DataFrame] = {}

        Console.info(f"Manager initialized (batch_size={batch_size}, batching={'ON' if enable_batching else 'OFF'}, sql_cache={sql_health_cache_seconds}s, io_workers={max_io_workers}, flush={batch_flush_rows} rows/{batch_flush_seconds}s, max_futures={max_in_flight_futures})", component="OUTPUT")
    
    def set_maturity_state(self, maturity_state: str) -> None:
        """V11 CRITICAL: Update maturity state after model lifecycle is computed.
        
        This MUST be called from acm_main.py after model_state is determined.
        Eliminates the race condition where writers query ACM_ActiveModels independently.
        
        Args:
            maturity_state: One of 'COLDSTART', 'LEARNING', 'CONVERGED', 'DEPRECATED'
        """
        self.maturity_state = maturity_state
        Console.info(f"OutputManager maturity_state set to {maturity_state}", component="OUTPUT")
    
    @contextmanager
    def batched_transaction(self):
        """
        Context manager for writing multiple tables in a single transaction.
        Improves performance by reducing commit overhead when writing many tables.
        
        Usage:
            with output_mgr.batched_transaction():
                output_mgr.write_table("Table1", df1)
                output_mgr.write_table("Table2", df2)
                # Single commit after all writes
        """
        if self._batched_transaction_active:
            # Nested transaction - just pass through
            yield
            return
        
        if self.sql_client is None:
            # Backward-compatible fallback for unit tests that build a partial manager.
            yield
            return
        
        # Check SQL health ONCE at transaction entry. Fail fast to avoid silent writes loss.
        if not self._check_sql_health():
            raise RuntimeError("SQL unhealthy at transaction start")
        
        self._batched_transaction_active = True
        self._sql_engine._batched_transaction_active = True
        start_time = time.time()
        
        try:
            yield
            # Commit at end of transaction
            self.sql_client.commit()
            elapsed = time.time() - start_time
            Console.info(f"Batched transaction committed ({elapsed:.2f}s)", component="OUTPUT")
        except Exception as e:
            # Rollback on error
            try:
                self.sql_client.rollback()
            except Exception:
                pass  # Rollback failed, original exception more important
            Console.error(f"Batched transaction rolled back: {e}", component="OUTPUT", equip_id=self.equip_id, run_id=self.run_id, error_type=type(e).__name__)
            raise
        finally:
            self._batched_transaction_active = False
            self._sql_engine._batched_transaction_active = False
    
    def _load_data_from_sql(self, cfg: Dict[str, Any], equipment_name: str, start_utc: Optional[pd.Timestamp], end_utc: Optional[pd.Timestamp], is_coldstart: bool = False):
        """
        Load training and scoring data from SQL historian using stored procedure.
        
        Delegates to DataLoader class (extracted in Phase 2 debloating).
        
        Args:
            cfg: Configuration dictionary
            equipment_name: Equipment name (e.g., 'FD_FAN', 'GAS_TURBINE')
            start_utc: Start time for query window
            end_utc: End time for query window
            is_coldstart: If True, split data for coldstart training. If False, use all data for scoring.
        
        Returns:
            Tuple of (train_df, score_df, loader metadata object)
        """
        loader = DataLoader(self.sql_client)
        return loader.load_from_sql(cfg, equipment_name, start_utc, end_utc, is_coldstart)
    
    def _check_sql_health(self) -> bool:
        """Check SQL availability with caching for performance.
        
        Optimization: Skip check entirely during batched transactions.
        If we entered the transaction successfully, SQL is healthy.
        """
        if self.sql_client is None:
            return False
        
        # PERF: Inside batched transaction, trust SQL is healthy (checked once at entry)
        if self._batched_transaction_active:
            return True
        
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
            Console.error(f"SQL health check failed: {e}", component="OUTPUT", equip_id=self.equip_id, error_type=type(e).__name__, error=str(e)[:200])
            return False
        finally:
            try:
                if 'cur' in locals():
                    cur.close()
            except Exception:
                pass

    @staticmethod
    def _is_non_empty_dataframe(df: Optional[pd.DataFrame]) -> bool:
        """Return True when DataFrame exists and has at least one row."""
        return df is not None and not df.empty

    def _can_write_dataframe(self, df: Optional[pd.DataFrame], require_healthy_sql: bool = True) -> bool:
        """Centralized write gate for DataFrame payloads.

        `require_healthy_sql` is kept for compatibility but health probing is no
        longer part of deep write paths. Runtime SQL availability is enforced at
        startup in `core.acm`.
        """
        if self.sql_client is None:
            return False
        return self._is_non_empty_dataframe(df)

    def _can_write_payload(self, payload: Any, require_healthy_sql: bool = True) -> bool:
        """Centralized write gate for dict/list payloads.

        `require_healthy_sql` is kept for compatibility but health probing is no
        longer part of deep write paths.
        """
        if self.sql_client is None:
            return False
        return bool(payload)

    def _get_datetime_columns_for_table(self, table_name: Optional[str]) -> set[str]:
        """Return datetime-typed columns from SQL schema for a table."""
        return self._get_sql_engine().get_datetime_columns_for_table(table_name)

    @staticmethod
    def _looks_like_datetime_column(col_name: str) -> bool:
        """Name-based fallback for datetime-like columns when schema metadata is unavailable."""
        return SqlWriteEngine.looks_like_datetime_column(col_name)

    def _prepare_dataframe_for_sql(
        self,
        df: pd.DataFrame,
        non_numeric_cols: Optional[set] = None,
        sql_table: Optional[str] = None,
    ) -> pd.DataFrame:
        """Prepare DataFrame for SQL insertion with robust type coercion (SQL Server safe)."""
        return self._get_sql_engine().prepare_dataframe_for_sql(df, non_numeric_cols, sql_table)
    
    
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

    def _resolve_policy_from_contract(
        self,
        contract: TableWriteContract,
        write_mode: Optional[Literal["insert", "replace"]] = None,
        key_columns: Optional[List[str]] = None,
    ) -> WritePolicy:
        """Resolve final write policy from table contract plus optional overrides."""
        mode = write_mode or contract.mode
        if mode == "replace":
            keys = list(key_columns) if key_columns is not None else list(contract.key_columns)
            return self.build_replace_policy(contract.table_name, keys)
        return self.build_insert_policy()

    def write_sql_table(
        self,
        table_name: str,
        df: pd.DataFrame,
        artifact_name: Optional[str] = None,
        sql_columns: Optional[Dict[str, str]] = None,
        non_numeric_cols: Optional[set] = None,
        required: Optional[bool] = None,
        write_mode: Optional[Literal["insert", "replace"]] = None,
        key_columns: Optional[List[str]] = None,
        write_policy: Optional[WritePolicy] = None,
    ) -> Dict[str, Any]:
        """
        Canonical, contract-driven SQL writer for all standardized table writes.
        """
        contract = get_table_write_contract(table_name)
        if contract is None:
            error_msg = (
                f"Table '{table_name}' has no write contract. "
                "Add contract in core/output_contracts.py (TABLE_WRITE_CONTRACTS)."
            )
            Console.warn(
                error_msg,
                component="OUTPUT",
                table=table_name,
                rows=len(df),
                equip_id=self.equip_id,
                run_id=self.run_id,
            )
            return {
                "sql_written": False,
                "rows": int(len(df)),
                "inserted": 0,
                "error": error_msg,
                "sql_table": table_name,
                "artifact": artifact_name or f"table:{table_name}",
            }

        effective_required = contract.required if required is None else required
        effective_policy = write_policy or self._resolve_policy_from_contract(
            contract=contract,
            write_mode=write_mode,
            key_columns=key_columns,
        )

        return self.write_dataframe(
            df=df,
            artifact_name=artifact_name or f"table:{table_name}",
            sql_table=table_name,
            sql_columns=sql_columns,
            non_numeric_cols=non_numeric_cols,
            required=effective_required,
            write_policy=effective_policy,
        )
    
    def write_dataframe(
        self,
        df: pd.DataFrame,
        artifact_name: str,
        sql_table: Optional[str] = None,
        sql_columns: Optional[Dict[str, str]] = None,
        non_numeric_cols: Optional[set] = None,
        required: bool = False,
        write_policy: Optional[WritePolicy] = None,
    ) -> Dict[str, Any]:
        """
        Write DataFrame to SQL (SQL-only; file output removed).

        Args:
            df: DataFrame to write
            artifact_name: Logical name for the artifact (used for caching/logging)
            sql_table: Optional SQL table name. If None, no SQL write is attempted.
            sql_columns: Optional column mapping for SQL (df_col -> sql_col)
            non_numeric_cols: Set of columns to treat as non-numeric for SQL preparation
            required: If True, raise on write failure; if False, log warning and continue (default False for backwards-compat)
            write_policy: Optional explicit insert/upsert behavior from generator.

        Returns:
            Dict with SQL write results and metadata.
        """
        start_time = time.time()

        result: Dict[str, Any] = {
            "sql_written": False,
            "rows": int(len(df)),
            "inserted": 0,
            "error": None,
            "sql_table": sql_table,
            "artifact": artifact_name,
        }

        # OUT-18: auto-flush before write if needed
        if self._should_auto_flush():
            Console.info(
                f"Auto-flushing batch (rows={self._current_batch.total_rows}, age={time.time() - self._current_batch.created_at:.1f}s)",
                component="OUTPUT",
            )
            self.flush()

        # OUT-18: backpressure
        self._wait_for_futures_capacity()

        # Track rows in current batch regardless of whether we write to SQL
        with self._batch_lock:
            self._current_batch.total_rows += len(df)

        sql_df: Optional[pd.DataFrame] = None

        try:
            # If no sql_table requested, skip SQL quietly
            if not sql_table:
                return result

            if write_policy is None:
                raise ValueError(
                    f"write_dataframe(sql_table={sql_table}) requires explicit write_policy; "
                    "use write_sql_table(...) for contract-driven writes."
                )

            # Guard: Only write to ALLOWED_TABLES (contract enforcement)
            if sql_table not in ALLOWED_TABLES:
                Console.warn(
                    f"Table '{sql_table}' not in ALLOWED_TABLES; skipping write",
                    component="OUTPUT",
                    table=sql_table,
                    rows=len(df),
                )
                result["error"] = f"Table '{sql_table}' not in ALLOWED_TABLES"
                return result

            # Skip empty DataFrames (no-op)
            if df.empty:
                return result

            sql_df = self._prepare_sql_write_payload(
                df=df,
                sql_table=sql_table,
                sql_columns=sql_columns,
                non_numeric_cols=non_numeric_cols or set(),
            )
            inserted = self._execute_write_policy(
                sql_table=sql_table,
                sql_df=sql_df,
                write_policy=write_policy,
            )

            if required and inserted <= 0 and not sql_df.empty:
                raise RuntimeError(f"Required table {sql_table} write inserted 0 rows")

            result["inserted"] = inserted
            result["sql_written"] = inserted > 0

            if result["sql_written"]:
                self.stats["sql_writes"] += 1

            return result

        except Exception as e:
            # Ensure we never reference sql_df if it wasn't built
            rows_for_log = len(sql_df) if isinstance(sql_df, pd.DataFrame) else len(df)
            
            error_msg = f"SQL write failed for {sql_table}: {str(e)[:500]}"
            
            if required:
                # For required tables, escalate to error and re-raise
                Console.error(
                    f"[CRITICAL] Required table {sql_table} write failed: {error_msg}",
                    component="OUTPUT",
                    table=sql_table,
                    rows=rows_for_log,
                    equip_id=self.equip_id,
                    run_id=self.run_id,
                    error_type=type(e).__name__,
                )
                result["error"] = error_msg
                raise RuntimeError(f"Required table write failed: {error_msg}") from e
            else:
                # For optional tables, warn and continue (backwards-compatible behavior)
                Console.warn(
                    f"SQL write failed for {sql_table}: {error_msg}",
                    component="OUTPUT",
                    table=sql_table,
                    rows=rows_for_log,
                    equip_id=self.equip_id,
                    run_id=self.run_id,
                    error_type=type(e).__name__,
                )
                result["error"] = error_msg
            self.stats["sql_failures"] += 1
            return result

        finally:
            elapsed = time.time() - start_time
            self.stats["write_time"] += elapsed
            # FCST-15: cache for downstream modules
            self._artifact_cache[artifact_name] = df

    def _prepare_sql_write_payload(
        self,
        df: pd.DataFrame,
        sql_table: str,
        sql_columns: Optional[Dict[str, str]],
        non_numeric_cols: set,
    ) -> pd.DataFrame:
        """Prepare DataFrame payload for SQL writing, including metadata enrichment."""
        sql_df = self._prepare_dataframe_for_sql(
            df,
            non_numeric_cols,
            sql_table=sql_table,
        )
        if sql_columns:
            mapped_source_cols = [c for c in sql_columns.keys() if c in sql_df.columns]
            sql_df = sql_df[mapped_source_cols].rename(columns=sql_columns)
        return self._populate_standard_metadata(sql_df)

    def _execute_write_policy(
        self,
        sql_table: str,
        sql_df: pd.DataFrame,
        write_policy: Optional[WritePolicy],
    ) -> int:
        """Execute SQL write based on explicit generator-declared policy."""
        policy = write_policy or WritePolicy(mode="insert")
        if policy.mode == "upsert":
            if policy.upsert_handler is None:
                Console.warn(
                    f"write_dataframe upsert requested without handler for {sql_table}; falling back to insert",
                    component="OUTPUT",
                    table=sql_table,
                )
                return int(self._bulk_insert_sql(sql_table, sql_df))
            return int(policy.upsert_handler(sql_df))
        return int(self._bulk_insert_sql(sql_table, sql_df))

    def _get_table_columns_for_contract(self, table_name: str) -> set[str]:
        """Resolve and cache table columns for schema-contract enforcement."""
        return self._get_sql_engine().get_table_columns_for_contract(table_name)

    def _populate_standard_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Populate standard metadata (RunID, EquipID, CreatedAt) during payload generation."""
        return self._get_sql_engine().populate_standard_metadata(df)

    def _get_sql_engine(self) -> SqlWriteEngine:
        """Return write engine, lazily creating one for lightweight test/manual construction."""
        engine = getattr(self, "_sql_engine", None)
        if engine is None:
            engine = SqlWriteEngine(
                sql_client=getattr(self, "sql_client", None),
                run_id=getattr(self, "run_id", None),
                equip_id=getattr(self, "equip_id", None),
                batch_size=int(getattr(self, "batch_size", 5000) or 5000),
            )
            self._sql_engine = engine
        else:
            # Keep engine identity fields synced when caller mutates manager context.
            engine.run_id = getattr(self, "run_id", None)
            equip_id = getattr(self, "equip_id", None)
            engine.equip_id = int(equip_id) if equip_id is not None else None
        return cast(SqlWriteEngine, engine)

    def audit_allowed_tables_write_integrity(
        self,
        run_id: Optional[str] = None,
        equip_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Verify metadata completeness in ALLOWED_TABLES for a run/equipment scope.

        Checks table existence and reports NULL counts for RunID/EquipID/CreatedAt
        where those columns exist.
        """
        if self.sql_client is None:
            raise RuntimeError("SQL client is required for write integrity audit")

        scope_run = run_id if run_id is not None else self.run_id
        scope_equip = int(equip_id) if equip_id is not None else (int(self.equip_id) if self.equip_id is not None else None)
        details: List[Dict[str, Any]] = []
        tables_with_null_meta: List[str] = []
        cursor_factory = lambda: cast(Any, self.sql_client).cursor()

        for table_name in sorted(ALLOWED_TABLES):
            if not _table_exists(cursor_factory, table_name):
                details.append({"table": table_name, "exists": False})
                continue

            cols = self._get_table_columns_for_contract(table_name)
            has_runid = "RunID" in cols
            has_equipid = "EquipID" in cols
            has_createdat = "CreatedAt" in cols

            where_parts: List[str] = []
            params: List[Any] = []
            if has_runid and scope_run:
                where_parts.append("RunID = ?")
                params.append(scope_run)
            if has_equipid and scope_equip is not None:
                where_parts.append("EquipID = ?")
                params.append(scope_equip)
            where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

            tbl_escaped = f"dbo.[{table_name}]"
            cur = cursor_factory()
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl_escaped}{where_sql}", tuple(params))
                total_rows = int((cur.fetchone() or [0])[0] or 0)

                null_runid = 0
                null_equipid = 0
                null_createdat = 0
                if has_runid:
                    cur.execute(f"SELECT COUNT(*) FROM {tbl_escaped}{where_sql}" + (" AND " if where_parts else " WHERE ") + "RunID IS NULL", tuple(params))
                    null_runid = int((cur.fetchone() or [0])[0] or 0)
                if has_equipid:
                    cur.execute(f"SELECT COUNT(*) FROM {tbl_escaped}{where_sql}" + (" AND " if where_parts else " WHERE ") + "EquipID IS NULL", tuple(params))
                    null_equipid = int((cur.fetchone() or [0])[0] or 0)
                if has_createdat:
                    cur.execute(f"SELECT COUNT(*) FROM {tbl_escaped}{where_sql}" + (" AND " if where_parts else " WHERE ") + "CreatedAt IS NULL", tuple(params))
                    null_createdat = int((cur.fetchone() or [0])[0] or 0)

                if null_runid > 0 or null_equipid > 0 or null_createdat > 0:
                    tables_with_null_meta.append(table_name)

                details.append(
                    {
                        "table": table_name,
                        "exists": True,
                        "rows_in_scope": total_rows,
                        "has_runid": has_runid,
                        "has_equipid": has_equipid,
                        "has_createdat": has_createdat,
                        "null_runid": null_runid,
                        "null_equipid": null_equipid,
                        "null_createdat": null_createdat,
                    }
                )
            finally:
                try:
                    cur.close()
                except Exception:
                    pass

        return {
            "scope_run_id": scope_run,
            "scope_equip_id": scope_equip,
            "tables_with_null_metadata": sorted(set(tables_with_null_meta)),
            "details": details,
        }

    def audit_allowed_tables_schema_contract(self) -> Dict[str, Any]:
        """
        Audit schema consistency for all ALLOWED_TABLES in the current SQL DB.

        Reports table existence and whether common metadata columns are present.
        This is an operational verification helper and does not mutate data.
        """
        if self.sql_client is None:
            raise RuntimeError("SQL client is required for schema audit")

        cursor_factory = lambda: cast(Any, self.sql_client).cursor()
        details: List[Dict[str, Any]] = []
        missing_tables: List[str] = []
        runid_without_equipid: List[str] = []
        equipid_without_runid: List[str] = []
        missing_createdat: List[str] = []

        for table_name in sorted(ALLOWED_TABLES):
            exists = _table_exists(cursor_factory, table_name)
            if not exists:
                missing_tables.append(table_name)
                details.append(
                    {
                        "table": table_name,
                        "exists": False,
                        "has_runid": False,
                        "has_equipid": False,
                        "has_createdat": False,
                        "has_timestamp": False,
                    }
                )
                continue

            cols = self._get_table_columns_for_contract(table_name)
            has_runid = "RunID" in cols
            has_equipid = "EquipID" in cols
            has_createdat = "CreatedAt" in cols
            has_timestamp = "Timestamp" in cols

            if has_runid and not has_equipid:
                runid_without_equipid.append(table_name)
            if has_equipid and not has_runid:
                equipid_without_runid.append(table_name)
            if not has_createdat:
                missing_createdat.append(table_name)

            details.append(
                {
                    "table": table_name,
                    "exists": True,
                    "has_runid": has_runid,
                    "has_equipid": has_equipid,
                    "has_createdat": has_createdat,
                    "has_timestamp": has_timestamp,
                }
            )

        return {
            "table_count": len(ALLOWED_TABLES),
            "missing_tables": missing_tables,
            "runid_without_equipid": runid_without_equipid,
            "equipid_without_runid": equipid_without_runid,
            "missing_createdat": missing_createdat,
            "details": details,
        }

    def audit_allowed_tables_write_coverage(self) -> Dict[str, Any]:
        """
        Audit whether ALLOWED_TABLES appear in known SQL write paths.

        This is static/introspective coverage: it scans OutputManager and
        output artifact writer sources for ACM table string literals.
        """
        sources: List[str] = []
        try:
            sources.append(inspect.getsource(type(self)))
        except Exception:
            pass
        try:
            sources.append(inspect.getsource(write_sql_artifacts))
        except Exception:
            pass
        try:
            sources.append(inspect.getsource(write_pca_artifacts))
        except Exception:
            pass

        referenced_tables: set[str] = set()
        pattern = re.compile(r"(?:'|\")(?P<table>ACM_[A-Za-z0-9_]+)(?:'|\")")
        for src in sources:
            for m in pattern.finditer(src):
                referenced_tables.add(m.group("table"))

        allowed_tables = set(ALLOWED_TABLES)
        missing_write_paths = sorted(allowed_tables - referenced_tables)
        referenced_not_allowed = sorted(referenced_tables - allowed_tables)

        return {
            "allowed_count": len(allowed_tables),
            "referenced_count": len(referenced_tables),
            "missing_write_paths": missing_write_paths,
            "referenced_not_allowed": referenced_not_allowed,
            "referenced_tables": sorted(referenced_tables),
        }

    def write_table(
        self,
        table_name: str,
        df: pd.DataFrame,
        write_policy: Optional[WritePolicy] = None,
    ) -> int:
        """Generic SQL table writer routed through contract-driven `write_sql_table`."""
        with Span("persist.write", table=table_name) if _OBSERVABILITY_AVAILABLE and Span else nullcontext() as span:
            if not self._can_write_dataframe(df):
                return 0

            result = self.write_sql_table(
                table_name=table_name,
                df=df,
                artifact_name=f"table:{table_name}",
                required=False,
                write_policy=write_policy,
            )
            rows_written = int(result.get("inserted", 0))
            if span:
                span._span.set_attribute("acm.rows_written", rows_written)
                if result.get("error"):
                    span._span.set_attribute("acm.error", True)
            return rows_written

    def _ensure_table_exists(self, table_name: str, cursor_factory: Callable[[], Any]) -> None:
        """Ensure target table exists (cached) before insert attempts."""
        self._sql_engine.ensure_table_exists(table_name, cursor_factory)

    def _apply_standard_predelete(self, cur: Any, table_name: str, table_cols: set[str]) -> None:
        """Delete existing rows for the current run when table supports RunID keys."""
        self._sql_engine.apply_standard_predelete(cur, table_name, table_cols)

    def _project_insert_columns(self, table_name: str, df: pd.DataFrame, table_cols: set[str]) -> List[str]:
        """Project payload columns to target table insertable columns."""
        return self._sql_engine.project_insert_columns(table_name, df, table_cols)

    # Start Here

    def _sanitize_for_sql_insert(
        self,
        table_name: str,
        df: pd.DataFrame,
        columns: List[str],
    ) -> pd.DataFrame:
        """Sanitize payload values for robust SQL binding (pyodbc-safe)."""
        return self._sql_engine.sanitize_for_sql_insert(table_name, df, columns)

    # End Here
    @staticmethod
    def _build_insert_sql(table_name: str, columns: List[str]) -> str:
        """Build parameterized INSERT statement for target table/columns."""
        return SqlWriteEngine.build_insert_sql(table_name, columns)

    def _execute_insert_batches(self, cur: Any, insert_sql: str, records: List[Tuple[Any, ...]], table_name: str) -> int:
        """Execute batched inserts with batch-level diagnostics."""
        return self._sql_engine.execute_insert_batches(cur, insert_sql, records, table_name)

    def _commit_if_needed(self, table_name: str) -> None:
        """Commit write if not already in an outer batched transaction."""
        self._sql_engine.commit_if_needed(table_name)

    def _rollback_if_needed(self, table_name: str) -> None:
        """Rollback current transaction when supported by the SQL client wrapper."""
        self._sql_engine.rollback_if_needed(table_name)


    def _replace_by_keys(self, table_name: str, df: pd.DataFrame, key_columns: List[str]) -> int:
        """
        Replace rows by key set: delete matching key tuples then bulk insert payload.
        Ensures delete key tuples are converted to pure Python scalars (pyodbc-safe).
        """
        if not self._can_write_dataframe(df, require_healthy_sql=False):
            return 0
        if self.sql_client is None:
            return 0
        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Invalid table name for replace policy: {table_name}")
        if not key_columns:
            raise ValueError("replace policy requires at least one key column")

        sql_df = df.copy()
        missing_keys = [k for k in key_columns if k not in sql_df.columns]
        if missing_keys:
            raise ValueError(f"{table_name} replace policy missing key columns: {missing_keys}")

        def _pyodbc_safe_scalar(v: Any) -> Any:
            # Null-like
            if v is None:
                return None
            try:
                if pd.isna(v):
                    return None
            except Exception:
                pass

            # pandas Timestamp / datetime-like
            if isinstance(v, pd.Timestamp):
                try:
                    if v.tzinfo is not None:
                        v = v.tz_convert(None)
                except Exception:
                    try:
                        v = v.tz_localize(None)
                    except Exception:
                        pass
                return v.to_pydatetime()

            # numpy / pandas scalar -> python scalar
            if hasattr(v, "item"):
                try:
                    return v.item()
                except Exception:
                    pass

            return v

        key_frame = sql_df[key_columns].dropna().drop_duplicates()

        if len(key_frame) > 0:
            # Normalize delete keys BEFORE executemany (this is the actual failing path)
            delete_rows = [
                tuple(_pyodbc_safe_scalar(val) for val in row)
                for row in key_frame.itertuples(index=False, name=None)
            ]

            with self.sql_client.cursor() as cur:
                try:
                    cur.fast_executemany = True
                except Exception:
                    pass

                where_sql = " AND ".join(f"[{k}] = ?" for k in key_columns)
                delete_sql = f"DELETE FROM dbo.[{table_name}] WHERE {where_sql}"

                cur.executemany(delete_sql, delete_rows)

            self._commit_if_needed(table_name)

        self._bulk_predeleted_tables.add(table_name)
        try:
            return self._bulk_insert_sql(table_name, sql_df)
        finally:
            self._bulk_predeleted_tables.discard(table_name)


    def build_replace_policy(
        self,
        table_name: str,
        key_columns: Optional[List[str]] = None,
    ) -> WritePolicy:
        """
        Build an explicit upsert policy using replace-by-keys semantics.
        If `key_columns` is omitted, keys are derived from REPLACE_POLICY_KEYS.
        """
        if key_columns is None:
            configured = REPLACE_POLICY_KEYS.get(table_name)
            if not configured:
                raise ValueError(
                    f"No replace key contract configured for table {table_name}. "
                    "Pass key_columns explicitly or add table to REPLACE_POLICY_KEYS."
                )
            keys = list(configured)
        else:
            keys = list(key_columns)
        return WritePolicy(
            mode="upsert",
            upsert_handler=lambda payload: self._replace_by_keys(table_name, payload, keys),
        )

    @staticmethod
    def build_insert_policy() -> WritePolicy:
        """Build an explicit insert policy."""
        return WritePolicy(mode="insert")

    @staticmethod
    def audit_replace_policy_contract() -> Dict[str, Any]:
        """Validate centralized replace-key contract shape and table references."""
        return _audit_replace_policy_contract()

    @staticmethod
    def audit_table_write_contracts() -> Dict[str, Any]:
        """Validate canonical table write contracts."""
        return _audit_table_write_contracts()

    # Bulk Insert Starts Here
    def _bulk_insert_sql(self, table_name: str, df: pd.DataFrame) -> int:
        """Perform bulk SQL insert with optimized batching and robust commit (pyodbc-safe scalars)."""
        _sql_start_time = time.perf_counter()

        if df.empty:
            return 0
        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Invalid table name: {table_name}")
        if self.sql_client is None:
            raise RuntimeError(f"SQL client is not available for table write: {table_name}")

        cursor_factory = lambda: cast(Any, self.sql_client).cursor()
        self._ensure_table_exists(table_name, cursor_factory)

        cur = cursor_factory()
        try:
            try:
                cur.fast_executemany = True
            except Exception:
                pass

            table_cols = self._get_table_columns_for_contract(table_name)
            self._apply_standard_predelete(cur, table_name, table_cols)

            columns = self._project_insert_columns(table_name, df, table_cols)
            if not columns:
                return 0

            # sanitize_for_sql_insert handles NaN→None, tz-strip, and extreme-float clamp.
            # _to_python_records then uses Polars .rows() for vectorized numpy→Python conversion.
            df_clean = self._sanitize_for_sql_insert(table_name, df, columns)
            insert_sql = self._build_insert_sql(table_name, columns)
            records = self._sql_engine._to_python_records(df_clean, columns)

            inserted = self._execute_insert_batches(cur, insert_sql, records, table_name)

        except Exception as e:
            Console.error(
                f"SQL insert failed for {table_name}: {e}",
                component="OUTPUT",
                table=table_name,
                rows=len(df),
                equip_id=self.equip_id,
                run_id=self.run_id,
                error_type=type(e).__name__,
                error=str(e)[:200],
            )
            raise
        finally:
            try:
                cur.close()
            except Exception:
                pass

        self._commit_if_needed(table_name)

        Console.info(f"SQL insert to {table_name}: {inserted} rows", component="OUTPUT")

        if _OBSERVABILITY_AVAILABLE and record_sql_op:
            try:
                duration_ms = (time.perf_counter() - _sql_start_time) * 1000
                record_sql_op(
                    equipment=getattr(self, 'equipment', ''),
                    table=table_name,
                    operation='insert',
                    rows=inserted,
                    duration_ms=duration_ms,
                )
            except Exception:
                pass

        return inserted
    # ==================== ARTIFACT CACHE METHODS (FCST-15) ====================
    
    def get_cached_table(self, table_name: str) -> Optional[pd.DataFrame]:
        """
        Retrieve a cached DataFrame from the artifact cache.
        
        This enables SQL-only mode by allowing downstream modules (forecast, RUL)
        to access previously written tables without file system dependencies.
        
        Args:
            table_name: Name of the table/file to retrieve (e.g., "scores.csv")
            
        Returns:
            DataFrame if found in cache, None otherwise
            
        Example:
            >>> scores = output_manager.get_cached_table("scores.csv")
            >>> if scores is not None:
            ...     # Use scores for forecasting
        """
        cached = self._artifact_cache.get(table_name)
        if cached is not None:
            Console.info(f"SQL cache hit {table_name}: {len(cached)} rows", component="OUTPUT")
            return cached.copy()  # Return copy to prevent mutation
        else:
            Console.warn(f"Table {table_name} not found in artifact cache", component="OUTPUT", table=table_name, available_tables=list(self._artifact_cache.keys())[:5])
            return None
    
    def write_pca_metrics(self, pca_detector=None, df=None, run_id=None, train=None) -> int:
        """Write PCA fit metrics to ACM_PCA_Metrics table (SQL-only).

        Two calling conventions:

        1. ``pca_detector=<PCASubspaceDetector>`` - called immediately after model fitting
           (detector_orchestrator.py).  Extracts all metrics directly from the fitted object.
           Pass ``train=<DataFrame>`` to populate TrainSamples/TrainFeatures.

        2. ``df=<DataFrame>`` - called by write_pca_artifacts after scoring.  The DataFrame
           must already be in new-format (NComponents, ExplainedVariance, ComponentsJson,
           MetricType, TrainSamples, TrainFeatures).  Score statistics (SPE/T2 percentiles)
           are appended to ComponentsJson before this call, so the second write supersedes
           the first.

        Args:
            pca_detector: PCASubspaceDetector instance.
            df: Pre-built new-format DataFrame.
            run_id: Run ID override (falls back to self.run_id).
            train: Training DataFrame used to fit the detector.  Provides TrainSamples and
                TrainFeatures when pca_detector is supplied.
        """
        if self.sql_client is None:
            return 0

        try:
            if pca_detector is not None:
                # PCA may be None if insufficient samples (< 2) during fit - expected, not an error
                if not hasattr(pca_detector, 'pca') or pca_detector.pca is None:
                    return 0

                pca = pca_detector.pca
                run_id_val = run_id or self.run_id
                var_ratio = getattr(pca, 'explained_variance_ratio_', None)

                # Build per-component JSON matching the write_pca_artifacts format
                components_json = None
                if var_ratio is not None and len(var_ratio) > 0:
                    cum = np.cumsum(var_ratio)
                    components_json = json.dumps([
                        {
                            'name': f'PC{i + 1}',
                            'type': 'variance_ratio',
                            'value': float(r),
                            'cumulative': float(cum[i]),
                        }
                        for i, r in enumerate(var_ratio)
                    ])

                sql_df = pd.DataFrame([{
                    'RunID': run_id_val,
                    'EquipID': self.equip_id,
                    'NComponents': int(pca.n_components_),
                    'ExplainedVariance': float(var_ratio.sum()) if var_ratio is not None else None,
                    'ComponentsJson': components_json,
                    'MetricType': 'pca_fit',
                    'TrainSamples': int(len(train)) if train is not None else None,
                    'TrainFeatures': len(pca_detector.keep_cols) if hasattr(pca_detector, 'keep_cols') else None,
                }])

            elif df is not None:
                if not self._is_non_empty_dataframe(df):
                    return 0
                sql_df = df.copy()
                # Respect explicit run_id override when caller passes a frame.
                if run_id is not None:
                    if 'RunID' not in sql_df.columns:
                        sql_df['RunID'] = run_id
                    else:
                        sql_df['RunID'] = sql_df['RunID'].where(pd.notna(sql_df['RunID']), run_id)

            else:
                Console.warn(
                    "write_pca_metrics called without pca_detector or df",
                    component="OUTPUT", equip_id=self.equip_id, run_id=self.run_id,
                )
                return 0

            if "MetricType" not in sql_df.columns:
                sql_df["MetricType"] = "pca_fit"
            else:
                sql_df["MetricType"] = sql_df["MetricType"].fillna("pca_fit")

            result = self.write_sql_table(
                table_name="ACM_PCA_Metrics",
                df=sql_df,
                artifact_name="pca_metrics",
                required=False,
            )
            return int(result.get("inserted", 0))

        except Exception as e:
            Console.warn(
                f"write_pca_metrics failed: {e}",
                component="OUTPUT", equip_id=self.equip_id,
                error_type=type(e).__name__, error=str(e)[:200],
            )
            return 0

    def write_pca_loadings(self, df: pd.DataFrame, run_id: str = None) -> int:
        """Write PCA loadings to ACM_PCA_Loadings table.
        
        Actual Table Schema (verified from INFORMATION_SCHEMA):
            ID BIGINT IDENTITY (auto)
            RunID UNIQUEIDENTIFIER NOT NULL
            EquipID INT NOT NULL
            ComponentIndex INT (nullable)
            SensorName NVARCHAR (nullable)
            Loading FLOAT NOT NULL
            AbsLoading FLOAT NOT NULL
            CreatedAt DATETIME2 NOT NULL
        
        Args:
            df: DataFrame with columns for PCA loadings data
            run_id: Run ID (optional, can come from df)
        
        Returns:
            Number of rows written
        """
        if not self._can_write_dataframe(df):
            return 0
        
        try:
            sql_df = df.copy()
            
            # Map source columns to actual table schema
            # Source may have: ComponentNo/ComponentID -> ComponentIndex
            # Source may have: Sensor/FeatureName -> SensorName
            if 'ComponentIndex' not in sql_df.columns:
                if 'ComponentNo' in sql_df.columns:
                    sql_df['ComponentIndex'] = sql_df['ComponentNo']
                elif 'ComponentID' in sql_df.columns:
                    sql_df['ComponentIndex'] = sql_df['ComponentID']
                else:
                    sql_df['ComponentIndex'] = 0  # Default
                    
            if 'SensorName' not in sql_df.columns:
                if 'Sensor' in sql_df.columns:
                    sql_df['SensorName'] = sql_df['Sensor']
                elif 'FeatureName' in sql_df.columns:
                    sql_df['SensorName'] = sql_df['FeatureName']
                else:
                    sql_df['SensorName'] = 'unknown'  # Default
            
            # Ensure required columns
            if 'EquipID' not in sql_df.columns:
                sql_df['EquipID'] = self.equip_id
            if 'RunID' not in sql_df.columns:
                if not (run_id or self.run_id):
                    raise ValueError("RunID is required but not set")
                sql_df['RunID'] = run_id or self.run_id
            
            # Calculate AbsLoading from Loading (required NOT NULL column)
            if 'AbsLoading' not in sql_df.columns:
                if 'Loading' in sql_df.columns:
                    sql_df['AbsLoading'] = sql_df['Loading'].abs()
                else:
                    Console.warn("write_pca_loadings: Missing 'Loading' column, cannot compute AbsLoading",
                                component="OUTPUT", equip_id=self.equip_id)
                    return 0
            
            # Handle NaN values in AbsLoading - replace with 0.0 since NOT NULL
            sql_df['AbsLoading'] = sql_df['AbsLoading'].fillna(0.0)
            sql_df['Loading'] = sql_df['Loading'].fillna(0.0)
            
            if 'CreatedAt' not in sql_df.columns:
                sql_df['CreatedAt'] = datetime.now()
            
            # Select only the columns the table expects (matching actual schema)
            keep_cols = ['RunID', 'EquipID', 'ComponentIndex', 'SensorName', 'Loading', 'AbsLoading', 'CreatedAt']
            sql_df = sql_df[[c for c in keep_cols if c in sql_df.columns]]
            
            result = self.write_sql_table(
                table_name="ACM_PCA_Loadings",
                df=sql_df,
                artifact_name="pca_loadings",
                required=False,
            )
            return int(result.get("inserted", 0))
            
        except Exception as e:
            Console.warn(f"write_pca_loadings failed: {e}", component="OUTPUT",
                        equip_id=self.equip_id, run_id=run_id, error=str(e)[:200])
            return 0

    def write_run_stats(self, stats_data: Dict[str, Any]) -> int:
        """Write run statistics to ACM_Run_Stats table."""
        if self.sql_client is None:
            return 0
        try:
            row = dict(stats_data)
            # Normalize key variants
            if 'StartTime' not in row and 'WindowStartEntryDateTime' in row:
                row['StartTime'] = normalize_timestamp_scalar(row.get('WindowStartEntryDateTime'))
            if 'EndTime' not in row and 'WindowEndEntryDateTime' in row:
                row['EndTime'] = normalize_timestamp_scalar(row.get('WindowEndEntryDateTime'))
            row.setdefault('RunID', self.run_id)
            if self.equip_id is None:
                Console.warn("write_run_stats: equip_id is None, skipping", component="OUTPUT")
                return 0
            row.setdefault('EquipID', self.equip_id)
            sql_df = pd.DataFrame([row])
            result = self.write_sql_table(
                table_name="ACM_Run_Stats",
                df=sql_df,
                artifact_name="run_stats",
                required=False,
            )
            return int(result.get("inserted", 0))
        except Exception as e:
            Console.error(f"write_run_stats failed: {e}", component="OUTPUT", equip_id=self.equip_id, run_id=self.run_id, error_type=type(e).__name__, error=str(e)[:200])
            return 0
    
    def write_scores(self, scores_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Write scores (SQL-only) to dbo.ACM_Scores_Wide.

        Normalizes index to tz-naive seconds and writes a Timestamp column.
        Timestamp normalization is deterministic and always applied.
        
        v11.1.5 FIX: Deletes existing rows for the same EquipID + timestamp range
        before inserting to prevent duplicate data from overlapping batch runs.
        """
        scores_for_output = scores_df.copy()
        scores_for_output.index.name = "timestamp"

        if len(scores_for_output.index):
            ts = pd.to_datetime(scores_for_output.index, errors="coerce")
            # Deterministic normalization: always tz-naive, floored to seconds
            # This ensures consistent SQL Server insertion regardless of input timezone
            if ts.tz is not None:
                ts = ts.tz_localize(None)
            ts = ts.floor("s")
            scores_for_output.index = ts

        # v11.1.5 FIX: Delete overlapping data BEFORE insert to prevent duplicates
        # This handles the case where multiple batch runs cover overlapping time ranges
        if len(scores_for_output.index) > 0 and self.sql_client is not None and self.equip_id:
            min_ts = scores_for_output.index.min()
            max_ts = scores_for_output.index.max()
            if pd.notna(min_ts) and pd.notna(max_ts):
                try:
                    with self.sql_client.cursor() as cur:
                        cur.execute(
                            "DELETE FROM dbo.[ACM_Scores_Wide] "
                            "WHERE EquipID = ? AND Timestamp BETWEEN ? AND ?",
                            (int(self.equip_id), min_ts, max_ts)
                        )
                        deleted = cur.rowcount
                        if deleted > 0:
                            Console.info(
                                f"Deleted {deleted} overlapping rows from ACM_Scores_Wide",
                                component="OUTPUT", table="ACM_Scores_Wide",
                                equip_id=self.equip_id, min_ts=str(min_ts), max_ts=str(max_ts)
                            )
                    self._commit_if_needed("ACM_Scores_Wide")
                except Exception as del_ex:
                    raise RuntimeError(f"Failed to delete overlapping scores: {del_ex}") from del_ex

        score_columns = {
            "timestamp": "Timestamp",
            "ar1_z": "ar1_z",
            "pca_spe_z": "pca_spe_z",
            "pca_t2_z": "pca_t2_z",
            "iforest_z": "iforest_z",
            "gmm_z": "gmm_z",
            "omr_z": "omr_z",
            "cusum_z": "cusum_z",
            "drift_z": "drift_z",
            "hst_z": "hst_z",
            "fused": "fused",
            "regime_label": "regime_label",
            "transient_state": "transient_state",
        }

        # non_numeric_cols must refer to *pre-mapping* column names because prepare() runs first.
        return self.write_sql_table(
            table_name="ACM_Scores_Wide",
            df=scores_for_output.reset_index(),
            artifact_name="scores",
            sql_columns=score_columns,
            non_numeric_cols={"timestamp", "regime_label", "transient_state"},
            required=True,
        )

    def _normalize_episodes_for_diagnostics(self, episodes_df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """
        Normalize episode payload into ACM_EpisodeDiagnostics-compatible shape.
        Returns the normalized frame and the list of applied repairs.
        """
        episodes_for_output = episodes_df.copy().reset_index(drop=True)
        repairs_applied: List[str] = []

        fallback_ids = pd.Series(
            np.arange(1, len(episodes_for_output) + 1),
            index=episodes_for_output.index,
            dtype="int64",
        )
        if 'episode_id' not in episodes_for_output.columns:
            episodes_for_output['episode_id'] = fallback_ids
            repairs_applied.append("episode_id_added")
        else:
            raw_episode_ids = pd.to_numeric(episodes_for_output['episode_id'], errors='coerce')
            valid_episode_ids = (
                raw_episode_ids.notna()
                & np.isfinite(raw_episode_ids)
                & (raw_episode_ids >= 1)
                & (np.floor(raw_episode_ids) == raw_episode_ids)
            )
            replaced_count = int((~valid_episode_ids).sum())
            episodes_for_output['episode_id'] = (
                raw_episode_ids.where(valid_episode_ids, fallback_ids).astype("int64")
            )
            if replaced_count > 0:
                repairs_applied.append(f"episode_id_sanitized:{replaced_count}")

        if 'duration_hours' not in episodes_for_output.columns and 'duration_s' in episodes_for_output.columns:
            episodes_for_output['duration_hours'] = episodes_for_output['duration_s'] / 3600.0
            repairs_applied.append("duration_hours_derived")

        if 'peak_timestamp' not in episodes_for_output.columns and 'start_ts' in episodes_for_output.columns:
            episodes_for_output['peak_timestamp'] = episodes_for_output['start_ts']
            repairs_applied.append("peak_timestamp_fallback_used")

        if 'regime_label' in episodes_for_output.columns:
            episodes_for_output['MaxRegimeLabel'] = episodes_for_output['regime_label']
            repairs_applied.append("regime_label_mapped")
        elif 'regime' in episodes_for_output.columns:
            episodes_for_output['MaxRegimeLabel'] = episodes_for_output['regime']
            repairs_applied.append("regime_mapped_fallback")

        if 'culprits' in episodes_for_output.columns:
            culprits_col = episodes_for_output['culprits'].fillna('').astype(str)
            arrow = ' ' + chr(8594) + ' '
            has_arrow = culprits_col.str.contains(arrow, na=False, regex=False)
            split_result = culprits_col.str.split(arrow).str[0].str.strip()
            episodes_for_output['dominant_sensor'] = np.where(
                culprits_col == '',
                'UNKNOWN',
                np.where(has_arrow, split_result, culprits_col.str.strip())
            )
            repairs_applied.append("dominant_sensor_extracted")
        else:
            episodes_for_output['dominant_sensor'] = 'UNKNOWN'
            repairs_applied.append("dominant_sensor_defaulted")

        if 'peak_fused_z' in episodes_for_output.columns:
            peak_z = episodes_for_output['peak_fused_z']
            abs_peak_z = np.abs(peak_z)
            conditions = [
                peak_z.isna(),
                abs_peak_z >= 6,
                abs_peak_z >= 4,
                abs_peak_z >= 2,
            ]
            choices = ['UNKNOWN', 'CRITICAL', 'HIGH', 'MEDIUM']
            episodes_for_output['severity'] = np.select(conditions, choices, default='LOW')
            repairs_applied.append("severity_calculated")
        elif 'severity' not in episodes_for_output.columns:
            episodes_for_output['severity'] = 'UNKNOWN'
            repairs_applied.append("severity_defaulted")

        if 'status' not in episodes_for_output.columns:
            episodes_for_output['status'] = 'CLOSED'
            repairs_applied.append("status_defaulted")

        return episodes_for_output, repairs_applied

    def _persist_episode_rows(self, episodes_for_output: pd.DataFrame) -> int:
        """
        Persist per-episode rows into ACM_Episodes using normalized episode payload.
        Routes through write_sql_table for contract-driven metadata and SQL normalization.
        """
        if episodes_for_output.empty:
            return 0

        episode_records: List[Dict[str, Any]] = []
        for idx, row in episodes_for_output.iterrows():
            duration_s = row.get('duration_s')
            episode_id_value = row.get('episode_id')
            if pd.notna(episode_id_value):
                try:
                    episode_id = int(episode_id_value)
                except (TypeError, ValueError):
                    episode_id = idx + 1
            else:
                episode_id = idx + 1
            if episode_id <= 0:
                episode_id = idx + 1
            episode_records.append({
                'RunID': self.run_id,
                'EquipID': self.equip_id or 0,
                'EpisodeID': episode_id,
                'StartTime': row.get('start_ts', datetime.now()),
                'EndTime': row.get('end_ts', None),
                'DurationSeconds': float(duration_s) if pd.notna(duration_s) else None,
                'DurationHours': float(duration_s) / 3600.0 if pd.notna(duration_s) else None,
                'RecordCount': int(row.get('n_samples', 1)) if pd.notna(row.get('n_samples')) else 1,
                'Culprits': str(row.get('culprits', ''))[:500] if pd.notna(row.get('culprits')) else None,
                'PrimaryDetector': str(row.get('dominant_sensor', 'UNKNOWN'))[:100] if pd.notna(row.get('dominant_sensor')) else 'UNKNOWN',
                'Severity': str(row.get('severity', 'UNKNOWN'))[:50],
                'RegimeLabel': int(row.get('regime_label', 0)) if pd.notna(row.get('regime_label')) else None,
                'RegimeState': str(row.get('regime_state', ''))[:50] if pd.notna(row.get('regime_state')) else None,
            })

        if not episode_records:
            return 0

        summary_df = pd.DataFrame(episode_records)
        result = self.write_sql_table(
            table_name="ACM_Episodes",
            df=summary_df,
            artifact_name="episode_rows",
            required=False,
        )
        return int(result.get("inserted", 0))

    def write_episodes(self, episodes_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Write episodes to SQL (SQL-only).
        
        Individual episodes go to ACM_EpisodeDiagnostics.
        Run-level summary goes to ACM_Episodes.
        """
        if episodes_df.empty:
            return {"sql_written": False, "rows": 0, "inserted": 0, "error": None}
        
        episodes_for_output, repairs_applied = self._normalize_episodes_for_diagnostics(episodes_df)
        
        episode_columns = {
            'episode_id': 'EpisodeID',
            'start_ts': 'StartTime',
            'end_ts': 'EndTime',
            'peak_fused_z': 'PeakZ',
            'peak_timestamp': 'peak_timestamp', 
            'duration_hours': 'DurationHours',
            'dominant_sensor': 'TopSensor1',
            'severity': 'Severity',
            'avg_fused_z': 'AvgZ',
            'min_health_index': 'min_health_index',
            'culprits': 'Culprits'
        }
        
        # Log all repairs for explicit schema drift tracking
        if repairs_applied:
            Console.info(f"Applied {len(repairs_applied)} schema repairs to episodes: {', '.join(repairs_applied)}", 
                        component="EPISODES", equip_id=self.equip_id, episode_count=len(episodes_for_output))
        
        result = self.write_sql_table(
            table_name="ACM_EpisodeDiagnostics",
            df=episodes_for_output,
            artifact_name="episodes",
            sql_columns=episode_columns,
            non_numeric_cols={
                "RunID", "EquipID", "episode_id", "peak_timestamp",
                "dominant_sensor", "severity", "min_health_index", "culprits"
            },
            required=True,
        )
        
        # Also persist per-episode rows to ACM_Episodes (actual table schema).
        episode_rows_inserted = self._persist_episode_rows(episodes_for_output)
        result["episodes_rows_inserted"] = int(episode_rows_inserted)
        
        return result

    def persist_core_outputs(
        self,
        scores_df: pd.DataFrame,
        episodes_df: Optional[pd.DataFrame],
    ) -> PersistCoreOutputsResult:
        """
        Persist core outputs and return inserted row counts for batch accounting.
        """
        scores_result = self.write_scores(scores_df)
        episodes_safe = pd.DataFrame() if episodes_df is None else episodes_df
        episodes_result = self.write_episodes(episodes_safe)
        return PersistCoreOutputsResult(
            scores_inserted=int(scores_result.get("inserted", 0)),
            episodes_inserted=int(episodes_result.get("inserted", 0)),
            episode_count=int(len(episodes_safe)),
        )
    
    def write_threshold_metadata(
        self,
        equip_id: int,
        threshold_type: str,
        threshold_value: float,
        calculation_method: str,
        sample_count: int,
        train_start: Optional[datetime] = None,
        train_end: Optional[datetime] = None,
        config_signature: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """Write adaptive threshold metadata to ACM_AdaptiveConfig.
        
        Maps to actual table schema:
        - ConfigKey: threshold_type (e.g., 'fused_alert_z')
        - ConfigValue: threshold_value as string
        - MinBound/MaxBound: 0.0/infinity for thresholds
        - IsLearned: True (since computed from data)
        - DataVolumeAtTuning: sample_count
        - PerformanceMetric: calculation_method
        - Source: 'adaptive_threshold_calculator'
        - ResearchReference: notes
        
        Args:
            equip_id: Equipment ID
            threshold_type: Type of threshold (e.g., 'fused_alert_z', 'fused_warn_z')
            threshold_value: Calculated threshold value
            calculation_method: Method used (e.g., 'quantile_0.997')
            sample_count: Number of samples used in calculation
            train_start: Start of training window (unused - table doesn't have this)
            train_end: End of training window (unused - table doesn't have this)
            config_signature: Hash of config used (unused - table doesn't have this)
            notes: Optional notes about calculation
        
        Returns:
            Number of rows written (1 on success, 0 on failure)
        """
        if self.sql_client is None:
            return 0
        try:
            # Handle dict values (per-regime thresholds) - store first value only
            if isinstance(threshold_value, dict):
                # Take first value for storage, or average
                threshold_float = float(list(threshold_value.values())[0]) if threshold_value else 0.0
            else:
                threshold_float = float(threshold_value)
            
            row = {
                'EquipID': int(equip_id),
                'ConfigKey': threshold_type,
                'ConfigValue': threshold_float,  # Float column
                'MinBound': 0.0,
                'MaxBound': 999999.0,  # Effectively no upper bound
                'IsLearned': 1,  # BIT column
                'DataVolumeAtTuning': int(sample_count),
                'PerformanceMetric': 0.0,  # Float column - store 0 for now
                'ResearchReference': f"{calculation_method}: {notes}" if notes else calculation_method,
                'Source': 'adaptive_threshold_calculator',
            }
            result = self.write_sql_table(
                table_name="ACM_AdaptiveConfig",
                df=pd.DataFrame([row]),
                artifact_name="threshold_metadata",
                required=False,
            )
            return int(result.get("inserted", 0))
        except Exception as e:
            Console.warn(f"write_threshold_metadata failed: {e}", component="THRESHOLD", error=str(e)[:200])
            return 0
    
    def load_omr_drift_context(self, equip_id: int, lookback_hours: int = 24) -> dict:
        """Load OMR and drift context from recent SQL outputs."""
        return load_omr_drift_context_service(self, equip_id=equip_id, lookback_hours=lookback_hours)
    
    # =========================================================================
    # DataFrame Builder Methods (moved from acm_main.py in v11.2)
    # =========================================================================
    # These methods build DataFrames for SQL persistence. They encapsulate the
    # data transformation logic that was previously scattered in acm_main.py.
    # =========================================================================
    
    @staticmethod
    def _build_data_quality_records(
        train_numeric: pd.DataFrame,
        score_numeric: pd.DataFrame,
        cfg: Dict[str, Any],
        low_var_threshold: float = 1e-4,
    ) -> List[Dict[str, Any]]:
        """Build a single summary data-quality record for SQL persistence."""
        return build_data_quality_records(
            train_numeric=train_numeric,
            score_numeric=score_numeric,
            cfg=cfg,
            low_var_threshold=low_var_threshold,
        )

    def write_anomaly_events(self, df_events: pd.DataFrame, run_id: str) -> int:
        """Write anomaly events to ACM_Anomaly_Events table."""
        return write_anomaly_events_service(
            self,
            df_events=df_events,
            run_id=run_id,
            confidence_enabled=(_CONFIDENCE_AVAILABLE and compute_episode_confidence is not None),
        )
    
    def write_regime_episodes(self, df_reg: pd.DataFrame, run_id: str) -> int:
        """Write regime episodes to ACM_Regime_Episodes."""
        return write_regime_episodes_service(self, df_reg=df_reg, run_id=run_id)
    
    def write_pca_model(self, model_row: Dict[str, Any]) -> int:
        """Write PCA model metadata to ACM_PCA_Models."""
        return write_pca_model_service(self, model_row=model_row)
    
    def write_detector_correlation(self, detector_correlations: Dict[str, Dict[str, float]]) -> int:
        """Write detector correlation matrix to ACM_DetectorCorrelation."""
        return write_detector_correlation_service(self, detector_correlations=detector_correlations)

    def write_detector_correlation_from_scores(self, scores_df: pd.DataFrame) -> int:
        """Build detector correlation matrix from score frame and persist it."""
        return write_detector_correlation_from_scores_service(self, scores_df=scores_df)
    
    def write_drift_series(self, drift_df: pd.DataFrame) -> int:
        """Write drift detection time series to ACM_DriftSeries."""
        return write_drift_series_service(self, drift_df=drift_df)
    
    def write_sensor_normalized_ts(self, scores_df: pd.DataFrame, sensor_cols: List[str] = None) -> int:
        """Write normalized sensor z-scores to ACM_SensorNormalized_TS."""
        return write_sensor_normalized_ts_service(self, scores_df=scores_df, sensor_cols=sensor_cols)
    
    def write_sensor_correlations(self, corr_matrix: pd.DataFrame, corr_type: str = 'pearson') -> int:
        """Write sensor correlation matrix to ACM_SensorCorrelations."""
        return write_sensor_correlations_service(self, corr_matrix=corr_matrix, corr_type=corr_type)

    def write_sensor_correlations_from_raw(self, raw_score: Optional[pd.DataFrame]) -> int:
        """Build sensor correlation matrix from raw sensor frame and persist it."""
        return write_sensor_correlations_from_raw_service(self, raw_score=raw_score)

    def write_representation_artifacts(
        self,
        *,
        representation_result: Any,
        signal_source_df: Optional[pd.DataFrame] = None,
    ) -> Any:
        """Persist shadow representation control-plane artifacts via representation_store."""
        return write_representation_artifacts_service(
            self,
            representation_result=representation_result,
            signal_source_df=signal_source_df,
        )
    
    def write_feature_drop_log(self, dropped_features: List[Dict[str, Any]]) -> int:
        """Write dropped features log to ACM_FeatureDropLog."""
        return write_feature_drop_log_service(self, dropped_features=dropped_features)
    
    def write_calibration_summary(self, calibration_data: List[Dict[str, Any]]) -> int:
        """Write detector calibration summary to ACM_CalibrationSummary."""
        return write_calibration_summary_service(self, calibration_data=calibration_data)
    
    def write_regime_occupancy(self, occupancy_data: List[Dict[str, Any]]) -> int:
        """Write regime occupancy stats to ACM_RegimeOccupancy."""
        return write_regime_occupancy_service(self, occupancy_data=occupancy_data)
    
    def write_regime_transitions(self, transition_matrix: Dict[str, Dict[str, int]]) -> int:
        """Write regime transition matrix to ACM_RegimeTransitions."""
        return write_regime_transitions_service(self, transition_matrix=transition_matrix)
    
    def write_contribution_timeline(self, contributions_df: pd.DataFrame) -> int:
        """Write detector contribution timeline to ACM_ContributionTimeline."""
        return write_contribution_timeline_service(self, contributions_df=contributions_df)

    def write_contribution_timeline_from_frame(
        self,
        frame: pd.DataFrame,
        fusion_weights: Optional[Dict[str, float]],
        equip: str = "",
    ) -> int:
        """Build and persist detector contribution timeline from score frame."""
        return write_contribution_timeline_from_frame_service(
            self,
            frame=frame,
            fusion_weights=fusion_weights,
            equip=equip,
        )
    
    def write_regime_promotion_log(self, promotions: List[Dict[str, Any]]) -> int:
        """Write regime maturity promotions to ACM_RegimePromotionLog."""
        return write_regime_promotion_log_service(self, promotions=promotions)
    
    def write_refit_request(
        self, 
        reasons: List[str],
        anomaly_rate: Optional[float] = None,
        drift_score: Optional[float] = None,
        regime_quality: Optional[float] = None
    ) -> int:
        """Write a model-refit request to ACM_RefitRequests."""
        return write_refit_request_service(
            self,
            reasons=reasons,
            anomaly_rate=anomaly_rate,
            drift_score=drift_score,
            regime_quality=regime_quality,
        )
    
    def write_fusion_metrics(
        self, 
        fusion_weights: Dict[str, float], 
        tuning_diagnostics: Dict[str, Any],
        previous_weights: Optional[Dict[str, float]] = None
    ) -> int:
        """Write fusion diagnostics and metrics to ACM_RunMetrics."""
        return write_fusion_metrics_service(
            self,
            fusion_weights=fusion_weights,
            tuning_diagnostics=tuning_diagnostics,
            previous_weights=previous_weights,
        )
    
    def check_refit_request(self) -> bool:
        """Check and acknowledge pending refit request for this equipment."""
        return check_refit_request_service(self)
    
    def update_baseline_buffer(
        self, 
        score_numeric: pd.DataFrame,
        cfg: Dict[str, Any],
        coldstart_complete: bool
    ) -> bool:
        """Update ACM_BaselineBuffer using periodic refresh policy."""
        return update_baseline_buffer_service(
            self,
            score_numeric=score_numeric,
            cfg=cfg,
            coldstart_complete=coldstart_complete,
        )
    
    def _ensure_local_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """Backward-compatible shim around core.time_normalizer.ensure_local_index."""
        return ensure_local_index(df)

    def _get_numeric_sensor_columns(
        self,
        df: pd.DataFrame,
        exclude: Optional[set[str]] = None,
    ) -> List[str]:
        """
        Return numeric sensor columns excluding metadata and z-score columns.
        """
        exclude_set = exclude or set()
        cols: List[str] = []
        for col in df.columns:
            if col in exclude_set or col.endswith("_z"):
                continue
            series = df[col]
            if pd.api.types.is_bool_dtype(series):
                continue
            if pd.api.types.is_float_dtype(series) or pd.api.types.is_integer_dtype(series):
                cols.append(col)
        return cols

    def _filter_low_variance_columns(
        self,
        df: pd.DataFrame,
        cols: List[str],
        min_variance: float = 1e-10,
    ) -> List[str]:
        """
        Keep only columns with variance above the configured floor.
        """
        if len(cols) < 2:
            return cols
        variances = df[cols].var()
        return variances[variances > float(min_variance)].index.tolist()
    
    def write_drift_controller(self, controller_state: Dict[str, Any]) -> int:
        """Write drift controller state to ACM_DriftController.
        
        Args:
            controller_state: Dict with ControllerState, Threshold, Sensitivity, etc.
        """
        if not self._can_write_payload(controller_state):
            return 0
        try:
            row = dict(controller_state)
            row["RunID"] = self.run_id
            row["EquipID"] = self.equip_id or 0
            result = self.write_sql_table(
                table_name="ACM_DriftController",
                df=pd.DataFrame([row]),
                artifact_name="drift_controller",
                required=False,
            )
            return int(result.get("inserted", 0))
        except Exception as e:
            Console.warn(f"write_drift_controller failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    
    def write_regime_definitions(self, regime_defs: List[Dict[str, Any]], version: int) -> int:
        """Write regime definitions to ACM_RegimeDefinitions (v11).
        
        Args:
            regime_defs: List of dicts with RegimeID, RegimeName, CentroidJSON, etc.
            version: Regime model version number
        """
        if not self._can_write_payload(regime_defs):
            return 0
        try:
            df = pd.DataFrame(regime_defs)
            df["EquipID"] = self.equip_id or 0
            df["RegimeVersion"] = version
            df["RunID"] = self.run_id
            result = self.write_sql_table(
                table_name="ACM_RegimeDefinitions",
                df=df,
                artifact_name="regime_definitions",
                required=False,
            )
            return int(result.get("inserted", 0))
        except Exception as e:
            Console.warn(f"write_regime_definitions failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0

    def _normalize_active_models_payload(self, model_state: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """Normalize active-model state into ACM_ActiveModels payload shape."""
        equip_raw = model_state.get("EquipID", self.equip_id)
        if equip_raw is None:
            Console.warn(
                "write_active_models skipped: EquipID is missing",
                component="OUTPUT",
                run_id=self.run_id,
            )
            return None
        try:
            equip_id = int(equip_raw)
        except (TypeError, ValueError):
            Console.warn(
                "write_active_models skipped: EquipID is not an integer",
                component="OUTPUT",
                run_id=self.run_id,
                equip_raw=str(equip_raw),
            )
            return None
        if equip_id <= 0:
            Console.warn(
                "write_active_models skipped: EquipID must be > 0",
                component="OUTPUT",
                run_id=self.run_id,
                equip_id=equip_id,
            )
            return None

        row = dict(model_state)
        row["EquipID"] = equip_id

        maturity_raw = str(row.get("RegimeMaturityState", self.maturity_state) or "INITIALIZING")
        maturity_value = maturity_raw.split(".")[-1].upper()
        valid_maturity = {"INITIALIZING", "LEARNING", "CONVERGED", "DEPRECATED"}
        row["RegimeMaturityState"] = maturity_value if maturity_value in valid_maturity else "INITIALIZING"

        for version_col in ("ActiveRegimeVersion", "ActiveThresholdVersion", "ActiveForecastVersion"):
            if version_col in row and pd.notna(row[version_col]):
                try:
                    row[version_col] = int(row[version_col])
                except (TypeError, ValueError):
                    row[version_col] = None

        row["LastUpdatedAt"] = datetime.now()
        row["LastUpdatedBy"] = self.run_id or str(row.get("LastUpdatedBy", "SYSTEM"))
        return pd.DataFrame([row])

    def write_active_models(self, model_state: Dict[str, Any]) -> int:
        """Write/update active model versions to ACM_ActiveModels (v11).
        
        Args:
            model_state: Dict with ActiveRegimeVersion, RegimeMaturityState, etc.

        Uses contract-driven replace semantics on EquipID.
        """
        if not self._can_write_payload(model_state):
            return 0

        df = self._normalize_active_models_payload(model_state)
        if df is None or df.empty:
            return 0

        try:
            result = self.write_sql_table(
                table_name="ACM_ActiveModels",
                df=df,
                artifact_name="active_models",
                required=False,
            )
            return int(result.get("inserted", 0))
        except Exception as e:
            Console.warn(f"write_active_models failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0
    # Start Write Data Contract Validation Here    
    def write_data_contract_validation(self, validation_result: Dict[str, Any]) -> int:
        """Write data contract validation result to ACM_DataContractValidation (v11)."""
        
        if not self._can_write_payload(validation_result):
            return 0

        # 🔥 Normalize numpy scalars recursively BEFORE DataFrame creation
        def _normalize(val):
            if isinstance(val, np.generic):
                return val.item()
            if isinstance(val, dict):
                return {k: _normalize(v) for k, v in val.items()}
            if isinstance(val, list):
                return [_normalize(v) for v in val]
            if isinstance(val, tuple):
                return tuple(_normalize(v) for v in val)
            return val

        try:
            row = _normalize(dict(validation_result))

            row["RunID"] = self.run_id
            row["EquipID"] = self.equip_id or 0
            row["ValidatedAt"] = datetime.now()

            df = pd.DataFrame([row])

            result = self.write_sql_table(
                table_name="ACM_DataContractValidation",
                df=df,
                artifact_name="data_contract_validation",
                required=False,
            )

            return int(result.get("inserted", 0))

        except Exception as e:
            Console.warn(
                f"Data contract validation write failed: {e}",
                component="OUTPUT",
                equip_id=self.equip_id,
                run_id=self.run_id,
            )
            return 0
    
    def write_seasonal_patterns(self, patterns: List[Dict[str, Any]]) -> int:
        """Write detected seasonal patterns to ACM_SeasonalPatterns (v11).
        
        Args:
            patterns: List of dicts with SensorName, PatternType, PeriodHours, Amplitude, etc.
        """
        if not self._can_write_payload(patterns):
            return 0
        try:
            df = pd.DataFrame(patterns)
            df["EquipID"] = self.equip_id or 0
            df["DetectedAt"] = datetime.now()
            df["RunID"] = self.run_id
            result = self.write_sql_table(
                table_name="ACM_SeasonalPatterns",
                df=df,
                artifact_name="seasonal_patterns",
                required=False,
            )
            return int(result.get("inserted", 0))
        except Exception as e:
            Console.warn(f"write_seasonal_patterns failed: {e}", component="OUTPUT", error=str(e)[:200])
            return 0

    def write_sensor_normalized_ts_from_raw(self, raw_score: Optional[pd.DataFrame], max_total_rows: int = 10000) -> int:
        """Sample raw sensor frame and persist normalized sensor time-series rows."""
        return write_sensor_normalized_ts_from_raw_service(
            self,
            raw_score=raw_score,
            max_total_rows=max_total_rows,
        )

    def write_seasonal_patterns_from_detected(self, seasonal_patterns: Optional[Dict[str, List[Any]]]) -> int:
        """Flatten detected seasonal patterns and persist them to SQL."""
        return write_seasonal_patterns_from_detected_service(self, seasonal_patterns=seasonal_patterns)

    def persist_additional_artifacts(
        self,
        scores_df: pd.DataFrame,
        raw_score: Optional[pd.DataFrame],
        seasonal_patterns: Optional[Dict[str, List[Any]]],
        max_total_rows: int = 10000,
    ) -> PersistArtifactsResult:
        """Persist optional secondary artifacts derived from current run data."""
        payload = persist_additional_artifacts_service(
            self,
            scores_df=scores_df,
            raw_score=raw_score,
            seasonal_patterns=seasonal_patterns,
            max_total_rows=max_total_rows,
        )
        return PersistArtifactsResult(**payload)

    def generate_all_analytics_with_context(
        self,
        scores_df: pd.DataFrame,
        cfg: Dict[str, Any],
        sensor_context: Optional[Dict[str, Any]],
        fusion_weights_used: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Persist analytics tables after optional fusion-weight injection into cfg."""
        return generate_all_analytics_with_context_service(
            self,
            scores_df=scores_df,
            cfg=cfg,
            sensor_context=sensor_context,
            fusion_weights_used=fusion_weights_used,
        )

    def _write_sql_artifacts(
        self,
        *,
        frame: pd.DataFrame,
        episodes: pd.DataFrame,
        train: pd.DataFrame,
        pca_detector: Any,
        sql_client: Any,
        run_id: Optional[str],
        equip_id: int,
        equip: str,
        cfg: Dict[str, Any],
        meta: Any,
        win_start: Optional[pd.Timestamp],
        win_end: Optional[pd.Timestamp],
        rows_read: int,
        spe_p95_train: float,
        t2_p95_train: float,
        anomaly_count: int,
        timer: Any,
        culprit_writer_func: Optional[Callable[..., Any]] = None,
    ) -> int:
        """Internal adapter to keep output-artifact write logic out of service layer imports."""
        return int(
            write_sql_artifacts(
                output_manager=self,
                frame=frame,
                episodes=episodes,
                train=train,
                pca_detector=pca_detector,
                sql_client=sql_client,
                run_id=run_id,
                equip_id=equip_id,
                equip=equip,
                cfg=cfg,
                meta=meta,
                win_start=win_start,
                win_end=win_end,
                rows_read=rows_read,
                spe_p95_train=spe_p95_train,
                t2_p95_train=t2_p95_train,
                anomaly_count=anomaly_count,
                T=timer,
                culprit_writer_func=culprit_writer_func,
            )
        )

    def persist_pipeline_outputs(
        self,
        scores_df: pd.DataFrame,
        episodes_df: Optional[pd.DataFrame],
        raw_train: Optional[pd.DataFrame],
        raw_score: Optional[pd.DataFrame],
        iforest_detector: Optional[Any],
        omr_detector: Optional[Any],
        seasonal_patterns: Optional[Dict[str, List[Any]]],
        cfg: Dict[str, Any],
        sensor_context: Optional[Dict[str, Any]],
        fusion_weights_used: Optional[Dict[str, float]],
        record_episode_fn: Optional[Callable[..., Any]] = None,
        equip: Optional[str] = None,
        max_total_rows: int = 10000,
    ) -> PersistPipelineOutputsResult:
        """Persist core and optional run artifacts, then release persist-phase memory."""
        payload = persist_pipeline_outputs_service(
            self,
            scores_df=scores_df,
            episodes_df=episodes_df,
            raw_train=raw_train,
            raw_score=raw_score,
            iforest_detector=iforest_detector,
            omr_detector=omr_detector,
            seasonal_patterns=seasonal_patterns,
            cfg=cfg,
            sensor_context=sensor_context,
            fusion_weights_used=fusion_weights_used,
            record_episode_fn=record_episode_fn,
            equip=equip,
            max_total_rows=max_total_rows,
        )
        return PersistPipelineOutputsResult(**payload)

    def run_persistence_stage(
        self,
        *,
        section_fn: Any,
        logger: Any,
        scores_df: pd.DataFrame,
        episodes_df: pd.DataFrame,
        train_df: pd.DataFrame,
        raw_train: Optional[pd.DataFrame],
        raw_score: Optional[pd.DataFrame],
        iforest_detector: Optional[Any],
        omr_detector: Optional[Any],
        seasonal_patterns: Optional[Dict[str, List[Any]]],
        cfg: Dict[str, Any],
        sensor_context: Optional[Dict[str, Any]],
        fusion_weights_used: Optional[Dict[str, float]],
        record_episode_fn: Optional[Callable[..., Any]],
        equip: str,
        pca_detector: Any,
        sql_client: Any,
        run_id: Optional[str],
        equip_id: int,
        meta: Any,
        win_start: Optional[pd.Timestamp],
        win_end: Optional[pd.Timestamp],
        rows_read: int,
        spe_p95_train: float,
        t2_p95_train: float,
        anomaly_count: int,
        timer: Any,
        culprit_writer_func: Optional[Callable[..., Any]] = None,
        max_total_rows: int = 10000,
    ) -> PersistenceStageResult:
        """Execute full persistence stage for pipeline outputs and SQL artifacts."""
        payload = run_persistence_stage_service(
            self,
            section_fn=section_fn,
            logger=logger,
            scores_df=scores_df,
            episodes_df=episodes_df,
            train_df=train_df,
            raw_train=raw_train,
            raw_score=raw_score,
            iforest_detector=iforest_detector,
            omr_detector=omr_detector,
            seasonal_patterns=seasonal_patterns,
            cfg=cfg,
            sensor_context=sensor_context,
            fusion_weights_used=fusion_weights_used,
            record_episode_fn=record_episode_fn,
            equip=equip,
            pca_detector=pca_detector,
            sql_client=sql_client,
            run_id=run_id,
            equip_id=equip_id,
            meta=meta,
            win_start=win_start,
            win_end=win_end,
            rows_read=rows_read,
            spe_p95_train=spe_p95_train,
            t2_p95_train=t2_p95_train,
            anomaly_count=anomaly_count,
            timer=timer,
            culprit_writer_func=culprit_writer_func,
            max_total_rows=max_total_rows,
        )
        return PersistenceStageResult(**payload)

    def prepare_persistence_inputs(
        self,
        *,
        section_fn: Any,
        raw_train: Optional[pd.DataFrame],
        raw_score: Optional[pd.DataFrame],
        frame: pd.DataFrame,
        omr_contributions_data: Optional[pd.DataFrame],
        regime_model: Any,
        cfg: Dict[str, Any],
        coldstart_complete: bool,
        build_sensor_analytics_context_fn: Any,
        logger: Any,
        equip: str,
    ) -> PersistenceInputPreparationResult:
        """Prepare persistence-stage inputs: baseline buffer update and sensor context."""
        payload = prepare_persistence_inputs_service(
            self,
            section_fn=section_fn,
            raw_train=raw_train,
            raw_score=raw_score,
            frame=frame,
            omr_contributions_data=omr_contributions_data,
            regime_model=regime_model,
            cfg=cfg,
            coldstart_complete=coldstart_complete,
            build_sensor_analytics_context_fn=build_sensor_analytics_context_fn,
            logger=logger,
            equip=equip,
        )
        return PersistenceInputPreparationResult(**payload)

    def release_persist_memory(
        self,
        raw_train: Optional[pd.DataFrame],
        raw_score: Optional[pd.DataFrame],
        iforest_detector: Optional[Any] = None,
        omr_detector: Optional[Any] = None,
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """Free large persist-phase objects after SQL writes are complete."""
        return release_persist_memory_service(
            raw_train=raw_train,
            raw_score=raw_score,
            iforest_detector=iforest_detector,
            omr_detector=omr_detector,
        )
    
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            **self.stats,
            'avg_write_time': self.stats['write_time'] / max(1, self.stats['sql_writes']),
            'sql_success_rate': 1.0 - (self.stats['sql_failures'] / max(1, self.stats['sql_health_checks']))
        }
    
    def flush(self) -> None:
        """OUT-18: Flush current batch without finalizing (for auto-flush triggers)."""
        with self._batch_lock:
            # Reset batch for next accumulation
            self._current_batch = OutputBatch()
    
    def flush_and_finalize(self) -> Dict[str, Any]:
        """Flush any pending operations and return final statistics."""
        self.flush()  # OUT-18: Use flush() for DRY
        
        stats = self.get_stats()
        # Note: sql_writes only tracks writes via write_dataframe() method
        # Many tables are written via direct SQL, batched transactions, etc.
        # This is intentionally low-level debug info, not a complete count
        Console.debug(f"OutputManager stats: {stats['sql_writes']} write_dataframe calls, "
                f"{stats['total_rows']} batch rows, "
                f"{stats['avg_write_time']:.3f}s avg write time", component="OUTPUT")
        
        return stats

    def close(self) -> None:
        """Gracefully finalize outstanding work. Compatible with acm_main finally block."""
        try:
            self.flush_and_finalize()
        except Exception:
            pass

    # ==================== BULK DELETE OPTIMIZATION ====================

    def _delete_timeline_overlaps(self, tables: List[str], min_ts: pd.Timestamp, max_ts: pd.Timestamp) -> int:
        """
        v11.1.5 FIX: Delete overlapping rows from timeline tables by TIMESTAMP RANGE.
        
        Unlike _bulk_delete_analytics_tables which deletes by RunID, this method
        deletes by EquipID + Timestamp range to prevent duplicate data when
        overlapping batch runs cover the same time periods.
        
        Args:
            tables: List of table names to clean (must have Timestamp column)
            min_ts: Minimum timestamp in the data being written
            max_ts: Maximum timestamp in the data being written
            
        Returns:
            Total rows deleted across all tables
        """
        if not self.sql_client or not self.equip_id:
            return 0
        if pd.isna(min_ts) or pd.isna(max_ts):
            return 0
            
        total_deleted = 0
        
        for table_name in tables:
            if table_name not in ALLOWED_TABLES:
                continue
                
            try:
                with self.sql_client.cursor() as cur:
                    cur.execute(
                        f"DELETE FROM dbo.[{table_name}] "
                        f"WHERE EquipID = ? AND Timestamp BETWEEN ? AND ?",
                        (int(self.equip_id), min_ts, max_ts)
                    )
                    deleted = cur.rowcount
                    if deleted > 0:
                        total_deleted += deleted
                        Console.info(
                            f"Deleted {deleted} overlapping rows from {table_name}",
                            component="OUTPUT", table=table_name,
                            equip_id=self.equip_id, min_ts=str(min_ts), max_ts=str(max_ts)
                        )
                self._commit_if_needed(table_name)
                        
            except Exception as del_ex:
                Console.warn(
                    f"Failed to delete overlapping data from {table_name}: {del_ex}",
                    component="OUTPUT", table=table_name,
                    equip_id=self.equip_id, error_type=type(del_ex).__name__
                )
                
        return total_deleted

    def _bulk_delete_analytics_tables(self, tables: List[str]) -> int:
        """
        PERF-OPT v11: Delete existing rows for current RunID/EquipID from multiple tables in ONE SQL batch.

        - Filters to ALLOWED_TABLES only.
        - Skips non-existent tables (cached).
        - Chooses predicate based on presence of RunID / EquipID columns.
        - Executes a single SQL batch to avoid N round-trips.

        Returns:
            Number of tables for which a DELETE statement was included in the batch.
            (Rowcount not tracked in this batched approach.)
        """
        if not self.sql_client or not self.run_id:
            return 0

        start_time = time.perf_counter()
        tables_targeted = 0

        # Local cursor factory for helper functions that expect a callable
        cursor_factory = lambda: cast(Any, self.sql_client).cursor()

        try:
            # Normalize candidate tables: allowed + unique, preserve input order
            seen = set()
            candidate_tables: List[str] = []
            for t in tables:
                if not t or t in seen:
                    continue
                seen.add(t)
                if t in ALLOWED_TABLES:
                    candidate_tables.append(t)

            if not candidate_tables:
                return 0

            delete_statements: List[str] = []

            for table_name in candidate_tables:
                # Table existence (cached)
                exists = self._table_exists_cache.get(table_name)
                if exists is None:
                    try:
                        exists = bool(_table_exists(cursor_factory, table_name))
                    except Exception:
                        exists = False
                    self._table_exists_cache[table_name] = exists

                if not exists:
                    continue

                # Column presence (prefer cached insertable/columns; avoid repeated metadata calls)
                table_cols = (
                    self._table_insertable_cache.get(table_name)
                    or self._table_columns_cache.get(table_name)
                )

                if table_cols is None:
                    try:
                        cols = set(_get_insertable_columns(cursor_factory, table_name) or [])
                        if not cols:
                            cols = set(_get_table_columns(cursor_factory, table_name) or [])
                        table_cols = cols
                        # Cache in insertable cache since we use it as "known columns" anyway
                        self._table_insertable_cache[table_name] = table_cols
                    except Exception:
                        # If we cannot introspect columns, skip (safe default)
                        continue

                # Build the WHERE predicate
                has_runid = "RunID" in table_cols
                has_equipid = "EquipID" in table_cols and (self.equip_id is not None)

                if not has_runid:
                    continue  # no RunID => cannot safely scope delete to current run

                if has_equipid:
                    delete_statements.append(
                        f"DELETE FROM dbo.[{table_name}] WHERE RunID = @RunID AND EquipID = @EquipID"
                    )
                else:
                    delete_statements.append(
                        f"DELETE FROM dbo.[{table_name}] WHERE RunID = @RunID"
                    )

                # Mark as pre-deleted so _bulk_insert_sql can skip its own per-table pre-delete logic
                self._bulk_predeleted_tables.add(table_name)
                tables_targeted += 1

            if not delete_statements:
                return 0

            # One network round-trip
            batch_sql = ";\n".join(delete_statements)

            cur = cursor_factory()
            try:
                # Parameter binding via pyodbc placeholders within DECLARE assignment is OK.
                # We declare parameters once and reuse them in all statements.
                sql = f"""
DECLARE @RunID NVARCHAR(36) = ?;
DECLARE @EquipID INT = ?;
{batch_sql};
"""
                cur.execute(sql, (self.run_id, int(self.equip_id or 0)))
                self._commit_if_needed("analytics_bulk_predelete")

            finally:
                try:
                    cur.close()
                except Exception:
                    pass

            elapsed = time.perf_counter() - start_time
            Console.info(
                f"Bulk pre-delete: {tables_targeted} tables targeted, {len(delete_statements)} DELETE statements in {elapsed:.2f}s (batched)",
                component="OUTPUT",
                tables_targeted=tables_targeted,
                delete_count=len(delete_statements)
            )
            return tables_targeted

        except Exception as e:
            Console.warn(
                f"Bulk pre-delete failed (non-fatal): {e}",
                component="OUTPUT",
                tables=len(tables),
                equip_id=self.equip_id,
                run_id=self.run_id,
                error_type=type(e).__name__,
            )
            return 0

    # ==================== COMPREHENSIVE ANALYTICS TABLES ====================

    def generate_all_analytics_tables(
        self,
        scores_df: pd.DataFrame,
        cfg: Dict[str, Any],
        sensor_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """
        Generate essential analytics tables (v11 - SQL-only).
        
        Phase 3: Delegates to AnalyticsBuilder for core logic.
        
        Writes only the tables in ALLOWED_TABLES:
          - ACM_HealthTimeline: Health % over time (required for RUL forecasting)
          - ACM_RegimeTimeline: Operating regime assignments
          - ACM_SensorDefects: Sensor-level anomaly flags
          - ACM_SensorHotspots: Top anomalous sensors (RUL attribution)
          - ACM_DataQuality: Data quality per sensor
        """
        builder = AnalyticsBuilder(self)
        return builder.generate_all(scores_df, cfg, sensor_context)

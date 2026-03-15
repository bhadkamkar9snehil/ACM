"""
SQL Write Engine — extracted from OutputManager (Phase A modularization).

All SQL write plumbing lives here so OutputManager stays a thin façade.
The engine owns:
  • schema introspection (table existence, column lists, datetime columns)
  • DataFrame preparation and sanitization for pyodbc
  • Bulk insert orchestration with batching
  • Transaction commit / rollback
  • Replace-by-keys (upsert) logic
  • Standard metadata population (RunID, EquipID, CreatedAt)
"""

from __future__ import annotations

import json
import time
import warnings
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, cast

import numpy as np
import pandas as pd

try:
    import polars as pl
    _POLARS_AVAILABLE = True
except ImportError:
    _POLARS_AVAILABLE = False

from core.observability import Console
from core.output_contracts import ALLOWED_TABLES, REPLACE_POLICY_KEYS

# Optional observability integration
try:
    from core.observability import record_sql_op
    _OBSERVABILITY_AVAILABLE = True
except ImportError:
    _OBSERVABILITY_AVAILABLE = False
    record_sql_op = None


# ===================== Module-Level Helpers =====================

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
    """Return columns excluding identity columns for safe INSERT."""
    cur = cursor_factory()
    try:
        cur.execute(
            "SELECT c.name, c.is_identity FROM sys.columns c WHERE c.object_id = OBJECT_ID(?)",
            (f"dbo.{name}",),
        )
        rows = cur.fetchall() or []
        return [r[0] for r in rows if not getattr(r, "is_identity", r[1])]
    finally:
        try:
            cur.close()
        except Exception:
            pass


# ===================== SqlWriteEngine =====================

class SqlWriteEngine:
    """Encapsulates all SQL write plumbing for OutputManager.

    Holds only SQL-specific state (client, caches, batch config, identity).
    OutputManager composes an instance and delegates write operations to it.
    """

    def __init__(
        self,
        sql_client: Any,
        run_id: Optional[str],
        equip_id: Optional[int],
        batch_size: int = 5000,
    ) -> None:
        self.sql_client = sql_client
        self.run_id = run_id
        # CRITICAL: convert numpy.int64 to native int to prevent HY000 error
        self.equip_id = int(equip_id) if equip_id is not None else None
        self.batch_size = batch_size
        self.equipment: str = ""

        # Lightweight caches for table probes
        self._table_exists_cache: Dict[str, bool] = {}
        self._table_columns_cache: Dict[str, set] = {}
        self._table_insertable_cache: Dict[str, set] = {}
        self._table_datetime_cache: Dict[str, set] = {}

        # Track tables bulk pre-deleted (skip individual DELETE)
        self._bulk_predeleted_tables: set = set()

        # Transaction state (owned by OutputManager, synced via property)
        self._batched_transaction_active: bool = False

    # -------------------- Schema Introspection --------------------

    def _cursor_factory(self) -> Any:
        return cast(Any, self.sql_client).cursor()

    def get_table_columns_for_contract(self, table_name: str) -> Set[str]:
        """Resolve and cache table columns for schema-contract enforcement."""
        if table_name in self._table_insertable_cache:
            return set(self._table_insertable_cache[table_name])
        try:
            cols = set(_get_insertable_columns(self._cursor_factory, table_name))
            if not cols:
                cols = set(_get_table_columns(self._cursor_factory, table_name))
            self._table_insertable_cache[table_name] = set(cols)
            return cols
        except Exception:
            if table_name in self._table_columns_cache:
                return set(self._table_columns_cache[table_name])
            cols_all = set(_get_table_columns(self._cursor_factory, table_name))
            self._table_columns_cache[table_name] = set(cols_all)
            return cols_all

    def get_datetime_columns_for_table(self, table_name: Optional[str]) -> Set[str]:
        """Return datetime-typed columns from SQL schema for a table."""
        if not table_name or self.sql_client is None:
            return set()
        if table_name in self._table_datetime_cache:
            return set(self._table_datetime_cache[table_name])
        try:
            cur = self._cursor_factory()
            try:
                cur.execute(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = 'dbo'
                      AND TABLE_NAME = ?
                      AND DATA_TYPE IN ('datetime', 'datetime2', 'smalldatetime', 'date', 'time', 'datetimeoffset')
                    """,
                    (table_name,),
                )
                cols = {str(r[0]) for r in (cur.fetchall() or []) if r and r[0]}
                self._table_datetime_cache[table_name] = set(cols)
                return cols
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
        except Exception:
            return set()

    @staticmethod
    def looks_like_datetime_column(col_name: str) -> bool:
        """Name-based fallback for datetime-like columns when schema metadata is unavailable."""
        c = (col_name or "").lower()
        if c in {"timestamp", "time", "ts", "datetime", "date"}:
            return True
        if "timestamp" in c or "datetime" in c:
            return True
        if c.endswith("_ts") or c.startswith("ts_"):
            return True
        if c.endswith("_time") or c.endswith("_date"):
            return True
        if c.startswith("start_") or c.startswith("end_"):
            return True
        if c.startswith("windowstart") or c.startswith("windowend"):
            return True
        return (
            c.endswith("createdat")
            or c.endswith("updatedat")
            or c.endswith("modifiedat")
            or c.endswith("completedat")
            or c.endswith("startedat")
            or c.endswith("loggedat")
            or c.endswith("detectedat")
            or c.endswith("lastupdate")
            or c.endswith("validfrom")
            or c.endswith("validto")
        )

    # -------------------- DataFrame Preparation --------------------

    def prepare_dataframe_for_sql(
        self,
        df: pd.DataFrame,
        non_numeric_cols: Optional[set] = None,
        sql_table: Optional[str] = None,
    ) -> pd.DataFrame:
        """Prepare DataFrame for SQL insertion with robust type coercion (SQL Server safe)."""
        if df.empty:
            return df

        out = df.copy()
        non_numeric_cols = set(non_numeric_cols or set())
        schema_dt_cols = self.get_datetime_columns_for_table(sql_table)

        # 1) Normalize datetime columns
        for col in out.columns:
            is_dt = pd.api.types.is_datetime64_any_dtype(out[col])
            is_schema_dt = col in schema_dt_cols
            is_obj_ts = (
                (not is_dt)
                and (not is_schema_dt)
                and self.looks_like_datetime_column(col)
                and out[col].dtype == object
            )

            if is_dt or is_schema_dt or is_obj_ts:
                ts_series = pd.to_datetime(out[col], errors="coerce")
                try:
                    ts_series = ts_series.dt.tz_localize(None)
                except Exception:
                    pass
                ts_series = ts_series.dt.floor("s")

                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=".*to_pydatetime.*", category=FutureWarning)
                    out[col] = np.array(ts_series.dt.to_pydatetime())

        # 2) Replace Inf/-Inf and NaNs
        float_only = out.select_dtypes(include=[np.floating])
        inf_count = 0
        if not float_only.empty:
            try:
                inf_count = int(np.isinf(float_only.values).sum())
            except TypeError:
                for col in float_only.columns:
                    col_vals = float_only[col].dropna()
                    if len(col_vals) > 0:
                        try:
                            inf_count += int(np.isinf(col_vals.values).sum())
                        except TypeError:
                            pass
        if inf_count > 0:
            Console.warn(
                f"Replaced {inf_count} Inf/-Inf values with None for SQL compatibility",
                component="OUTPUT",
                inf_count=inf_count,
                columns=len(float_only.columns),
            )

        out = out.replace({np.inf: np.nan, -np.inf: np.nan})

        # 3) Preserve integer types for known ID-like columns
        integer_columns_ci = {c.lower() for c in {"EquipID", "equip_id", "episode_id", "EpisodeID", "RegimeLabel", "regime_label"}}

        for col in out.columns:
            col_l = col.lower()
            if pd.api.types.is_bool_dtype(out[col]):
                out[col] = out[col].astype("Int64")
                continue
            if col_l in integer_columns_ci and pd.api.types.is_numeric_dtype(out[col]):
                out[col] = out[col].astype("Int64")
                continue
            if col in non_numeric_cols:
                continue
            if pd.api.types.is_numeric_dtype(out[col]):
                out[col] = out[col].astype(float)

        # 4) Normalize NaN/NaT to None
        out = out.where(pd.notnull(out), None)
        return out

    def populate_standard_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Populate standard metadata (RunID, EquipID, CreatedAt) during payload generation."""
        out = df.copy()
        run_fallback = self.run_id if self.run_id else "00000000-0000-0000-0000-000000000000"
        equip_fallback = int(self.equip_id) if self.equip_id is not None and int(self.equip_id) > 0 else 0
        now_utc_naive = pd.Timestamp.now(tz="UTC").tz_localize(None)

        if "RunID" not in out.columns:
            out["RunID"] = run_fallback
        else:
            out["RunID"] = out["RunID"].where(pd.notna(out["RunID"]), run_fallback)

        if "EquipID" not in out.columns:
            out["EquipID"] = equip_fallback
        else:
            out["EquipID"] = out["EquipID"].where(pd.notna(out["EquipID"]), equip_fallback)

        if "CreatedAt" not in out.columns:
            out["CreatedAt"] = now_utc_naive
        else:
            out["CreatedAt"] = out["CreatedAt"].where(pd.notna(out["CreatedAt"]), now_utc_naive)
        return out

    # -------------------- Sanitization --------------------

    def sanitize_for_sql_insert(
        self,
        table_name: str,
        df: pd.DataFrame,
        columns: List[str],
    ) -> pd.DataFrame:
        """Sanitize payload values for robust SQL binding (pyodbc-safe)."""
        df_clean = df[columns].copy()

        # 1. Replace common NA-like strings in object columns
        na_strings = {"N/A", "n/a", "NA", "na", "#N/A"}
        for col in df_clean.select_dtypes(include="object").columns:
            mask = df_clean[col].isin(na_strings)
            if mask.any():
                df_clean.loc[mask, col] = None

        # 2. Convert datetime columns (schema-driven preferred)
        schema_dt_cols = self.get_datetime_columns_for_table(table_name)
        if schema_dt_cols:
            ts_cols = [c for c in df_clean.columns if c in schema_dt_cols]
        else:
            ts_cols = [c for c in df_clean.columns if self.looks_like_datetime_column(c)]

        for col in ts_cols:
            try:
                pre_null = int(df_clean[col].isna().sum())
                df_clean[col] = pd.to_datetime(df_clean[col], format="mixed", errors="coerce")
                try:
                    df_clean[col] = df_clean[col].dt.tz_localize(None)
                except Exception:
                    pass
                post_null = int(df_clean[col].isna().sum())
                # Only warn when new NULLs appeared (parse failures on previously non-null values).
                # Pre-existing NULLs (e.g. RegimePromotedAt=None for LEARNING models) are expected.
                new_failures = post_null - pre_null
                if new_failures > 0:
                    Console.warn(
                        f"{new_failures} timestamps failed to parse in column {col}",
                        component="OUTPUT",
                        table=table_name,
                        column=col,
                        failed_count=new_failures,
                    )
            except Exception as ex:
                Console.warn(
                    f"Timestamp conversion failed for {col}: {ex}",
                    component="OUTPUT",
                    table=table_name,
                    column=col,
                    error_type=type(ex).__name__,
                )

        # 3. Float sanitization (clamp extremes, remove inf)
        float_cols = df_clean.select_dtypes(include=[np.float64, np.float32]).columns
        if len(float_cols):
            float_arr = df_clean[float_cols].to_numpy(dtype=float)
            extreme = np.abs(float_arr) > 1e38
            if extreme.any():
                n_extreme = int(extreme.sum())
                Console.warn(
                    f"Clamping {n_extreme} extreme float values in {table_name}",
                    component="OUTPUT",
                    table=table_name,
                    extreme_count=n_extreme,
                )
                float_arr[extreme] = np.nan
            np.copyto(float_arr, np.nan, where=~np.isfinite(float_arr))
            df_clean[float_cols] = float_arr

        # 4. Preserve native dtypes — DO NOT convert to object here.
        #    _to_python_records() handles numpy→Python type conversion via
        #    Polars pl.from_pandas().rows(), which requires seeing the original
        #    int64/float64/datetime64 dtypes to produce clean Python int/float/datetime.
        #    Only normalize NaN/NaT to None for proper SQL NULL handling.
        df_clean = df_clean.where(pd.notnull(df_clean), None)
        return df_clean

    # -------------------- Insert Helpers --------------------

    def ensure_table_exists(self, table_name: str, cursor_factory: Callable[[], Any]) -> None:
        """Ensure target table exists (cached) before insert attempts."""
        exists = self._table_exists_cache.get(table_name)
        if exists is None:
            exists = _table_exists(cursor_factory, table_name)
            self._table_exists_cache[table_name] = bool(exists)
        if not exists:
            raise RuntimeError(f"Target table dbo.[{table_name}] not found")

    def apply_standard_predelete(self, cur: Any, table_name: str, table_cols: Set[str]) -> None:
        """Delete existing rows for the current run when table supports RunID keys."""
        if table_name in self._bulk_predeleted_tables:
            return
        try:
            if "RunID" in table_cols and self.run_id:
                if "EquipID" in table_cols and self.equip_id is not None:
                    rows_deleted = cur.execute(
                        f"DELETE FROM dbo.[{table_name}] WHERE RunID = ? AND EquipID = ?",
                        (self.run_id, int(self.equip_id or 0)),
                    ).rowcount
                else:
                    rows_deleted = cur.execute(
                        f"DELETE FROM dbo.[{table_name}] WHERE RunID = ?",
                        (self.run_id,),
                    ).rowcount
                if rows_deleted and rows_deleted > 0:
                    Console.info(f"SQL delete from {table_name}: {rows_deleted} rows", component="OUTPUT")
        except Exception as del_ex:
            raise RuntimeError(f"Standard pre-delete for {table_name} failed: {del_ex}") from del_ex

    def project_insert_columns(self, table_name: str, df: pd.DataFrame, table_cols: Set[str]) -> List[str]:
        """Project payload columns to target table insertable columns."""
        columns = [c for c in df.columns if c in table_cols]
        if not columns:
            Console.warn(
                f"No matching insertable columns for {table_name}; skipping insert",
                component="OUTPUT",
                table=table_name,
                rows=len(df),
                equip_id=self.equip_id,
                run_id=self.run_id,
            )
        return columns

    @staticmethod
    def build_insert_sql(table_name: str, columns: List[str]) -> str:
        """Build parameterized INSERT statement for target table/columns."""
        cols_str = ", ".join(f"[{c}]" for c in columns)
        placeholders = ", ".join(["?"] * len(columns))
        return f"INSERT INTO dbo.[{table_name}] ({cols_str}) VALUES ({placeholders})"

    def execute_insert_batches(
        self, cur: Any, insert_sql: str, records: List[Tuple[Any, ...]], table_name: str
    ) -> int:
        """Execute batched inserts with batch-level diagnostics."""
        inserted = 0
        for i in range(0, len(records), self.batch_size):
            batch = records[i : i + self.batch_size]
            try:
                cur.executemany(insert_sql, batch)
                inserted += len(batch)
            except Exception as batch_error:
                sample = batch[:3] if len(batch) > 3 else batch
                Console.error(
                    f"Batch insert failed for {table_name} (sample: {sample}): {batch_error}",
                    component="OUTPUT",
                    table=table_name,
                    batch_size=len(batch),
                    equip_id=self.equip_id,
                    run_id=self.run_id,
                    error_type=type(batch_error).__name__,
                    error=str(batch_error)[:200],
                )
                raise
        return inserted

    # -------------------- Transaction Management --------------------

    def commit_if_needed(self, table_name: str) -> None:
        """Commit write if not already in an outer batched transaction."""
        if self._batched_transaction_active:
            return
        try:
            if hasattr(self.sql_client, "commit"):
                self.sql_client.commit()
            elif hasattr(self.sql_client, "conn") and hasattr(self.sql_client.conn, "commit"):
                if not getattr(self.sql_client.conn, "autocommit", True):
                    self.sql_client.conn.commit()
        except Exception as e:
            Console.error(
                f"SQL commit failed for {table_name}: {e}",
                component="OUTPUT",
                table=table_name,
                equip_id=self.equip_id,
                run_id=self.run_id,
                error_type=type(e).__name__,
                error=str(e)[:200],
            )
            raise

    def rollback_if_needed(self, table_name: str) -> None:
        """Rollback current transaction when supported by the SQL client wrapper."""
        try:
            if hasattr(self.sql_client, "rollback"):
                self.sql_client.rollback()
            elif hasattr(self.sql_client, "conn") and hasattr(self.sql_client.conn, "rollback"):
                self.sql_client.conn.rollback()
        except Exception as e:
            Console.warn(
                f"SQL rollback failed for {table_name}: {e}",
                component="OUTPUT",
                table=table_name,
                equip_id=self.equip_id,
                run_id=self.run_id,
                error_type=type(e).__name__,
                error=str(e)[:200],
            )

    # -------------------- Record Conversion --------------------

    @staticmethod
    def _to_python_records(df_clean: pd.DataFrame, columns: List[str]) -> List[Tuple[Any, ...]]:
        """Convert DataFrame rows to pyodbc-safe Python-native tuples.

        Uses Polars for vectorized type conversion — strips timezone info from
        datetime columns and lets Polars .rows() return Python-native values
        directly. sanitize_for_sql_insert() has already done NaN→None and
        extreme-float clamping, so no per-cell scalar callback is needed.
        """
        if _POLARS_AVAILABLE:
            try:
                pl_df = pl.from_pandas(df_clean[columns])
                # Strip timezone from any Datetime columns so pyodbc receives
                # tz-naive Python datetime objects (SQL Server doesn't accept tz-aware).
                cast_exprs = []
                for col_name, dtype in zip(pl_df.columns, pl_df.dtypes):
                    if isinstance(dtype, pl.Datetime) and dtype.time_zone is not None:
                        cast_exprs.append(
                            pl.col(col_name).dt.replace_time_zone(None).alias(col_name)
                        )
                if cast_exprs:
                    pl_df = pl_df.with_columns(cast_exprs)
                return pl_df.rows()
            except Exception:
                pass  # Fall through to pandas path

        # Pandas fallback (no Polars or conversion failed)
        def _normalize(val: Any) -> Any:
            if val is None:
                return None
            if isinstance(val, np.generic):
                return val.item()
            if isinstance(val, pd.Timestamp):
                if pd.isna(val):
                    return None
                try:
                    if val.tz is not None:
                        val = val.tz_convert(None)
                except Exception:
                    try:
                        val = val.tz_localize(None)
                    except Exception:
                        pass
                return val.to_pydatetime()
            if isinstance(val, (dict, list, tuple, set)):
                try:
                    return json.dumps(val, default=str)
                except Exception:
                    return str(val)
            try:
                if pd.isna(val):
                    return None
            except Exception:
                pass
            return val

        return [
            tuple(_normalize(v) for v in row)
            for row in df_clean[columns].itertuples(index=False, name=None)
        ]

    # -------------------- Bulk Insert Orchestrator --------------------

    def bulk_insert_sql(self, table_name: str, df: pd.DataFrame) -> int:
        """Perform bulk SQL insert with optimized batching and robust commit."""
        _sql_start_time = time.perf_counter()

        if df.empty:
            return 0
        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Invalid table name: {table_name}")
        if self.sql_client is None:
            raise RuntimeError(f"SQL client is not available for table write: {table_name}")

        cursor_factory = self._cursor_factory
        self.ensure_table_exists(table_name, cursor_factory)

        cur = cursor_factory()
        inserted = 0
        try:
            try:
                cur.fast_executemany = True
            except Exception:
                pass

            table_cols = self.get_table_columns_for_contract(table_name)
            self.apply_standard_predelete(cur, table_name, table_cols)

            columns = self.project_insert_columns(table_name, df, table_cols)
            if not columns:
                return 0

            df_clean = self.sanitize_for_sql_insert(table_name, df, columns)
            insert_sql = self.build_insert_sql(table_name, columns)

            records = self._to_python_records(df_clean, columns)
            if not records:
                return 0

            inserted = self.execute_insert_batches(cur, insert_sql, records, table_name)

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

        self.commit_if_needed(table_name)

        Console.info(f"SQL insert to {table_name}: {inserted} rows", component="OUTPUT")

        if _OBSERVABILITY_AVAILABLE and record_sql_op:
            try:
                duration_ms = (time.perf_counter() - _sql_start_time) * 1000
                record_sql_op(
                    equipment=self.equipment,
                    table=table_name,
                    operation="insert",
                    rows=inserted,
                    duration_ms=duration_ms,
                )
            except Exception:
                pass

        return inserted

    # -------------------- Replace-by-Keys (Upsert) --------------------

    def replace_by_keys(
        self,
        table_name: str,
        df: pd.DataFrame,
        key_columns: List[str],
        can_write_check: Callable[[Optional[pd.DataFrame]], bool],
    ) -> int:
        """Replace rows by key set: delete matching key tuples then bulk insert payload."""
        if not can_write_check(df):
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

        key_frame = sql_df[key_columns].dropna().drop_duplicates()
        if len(key_frame) > 0:
            with self.sql_client.cursor() as cur:
                try:
                    cur.fast_executemany = True
                except Exception:
                    pass
                where_sql = " AND ".join(f"[{k}] = ?" for k in key_columns)
                delete_sql = f"DELETE FROM dbo.[{table_name}] WHERE {where_sql}"
                delete_rows = [tuple(row) for row in key_frame.itertuples(index=False, name=None)]
                cur.executemany(delete_sql, delete_rows)
            self.commit_if_needed(table_name)

        self._bulk_predeleted_tables.add(table_name)
        try:
            return self.bulk_insert_sql(table_name, sql_df)
        finally:
            self._bulk_predeleted_tables.discard(table_name)

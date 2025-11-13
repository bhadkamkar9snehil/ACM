from __future__ import annotations

import time
from typing import Iterator, Optional, Sequence

import numpy as np
import pandas as pd

__all__ = [
    "to_naive",
    "coerce_for_sql",
    "iter_batches",
    "delete_and_bulk_insert",
    "is_sql_healthy",
]


# Simple SQL health cache (module scope)
_sql_health_cache: tuple[float, bool] = (0.0, False)
_SQL_HEALTH_CACHE_TTL = 60.0


def is_sql_healthy(sql_client, ttl_seconds: float = _SQL_HEALTH_CACHE_TTL) -> bool:
    """Fast SQL availability check with caching.

    Returns True if SQL is available, False otherwise.
    Avoids repeated round-trips by caching the result for ``ttl_seconds``.
    """
    global _sql_health_cache
    if sql_client is None:
        return False
    now = time.time()
    last_ts, last_ok = _sql_health_cache
    if now - last_ts < ttl_seconds:
        return last_ok
    try:
        cur = sql_client.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        _sql_health_cache = (now, True)
        return True
    except Exception:
        _sql_health_cache = (now, False)
        return False
    finally:
        try:
            if 'cur' in locals():
                cur.close()
        except Exception:
            pass


def to_naive(ts: pd.Series | pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Convert timestamps to UTC-naive DatetimeIndex.

    Treats naive inputs as UTC, converts aware inputs to UTC, then strips tz.
    """
    s = pd.to_datetime(ts, errors="coerce")
    return pd.DatetimeIndex(s.dt.tz_convert(None).dt.tz_localize(None))


def coerce_for_sql(df: pd.DataFrame, non_numeric: set[str] | None = None) -> pd.DataFrame:
    """Coerce DataFrame for SQL insert: replace NaN/Inf, convert numpy scalars to Python types.

    - Replaces ``np.inf``/``-np.inf`` with ``None`` (NULL)
    - Converts NaNs to ``None``
    - Casts numeric dtypes to float64, bool to int (0/1) while preserving NULLs
    """
    non_numeric = non_numeric or set()
    out = df.copy()
    out = out.replace({np.inf: None, -np.inf: None})
    out = out.where(pd.notnull(out), None)
    for c in out.columns:
        if c in non_numeric:
            continue
        ser = out[c]
        try:
            if pd.api.types.is_bool_dtype(ser):
                out[c] = ser.astype(object).where(ser.isna(), ser.astype(int))
            elif pd.api.types.is_numeric_dtype(ser):
                out[c] = ser.astype(float)
        except Exception:
            # Best-effort; leave column as-is on failure
            pass
    return out


def iter_batches(df: pd.DataFrame, batch_size: int) -> Iterator[tuple]:
    """Yield batches of tuples from a DataFrame using itertuples.

    Avoids materializing all rows at once in Python lists.
    """
    if batch_size <= 0:
        batch_size = 1000
    it = df.itertuples(index=False, name=None)
    while True:
        batch = []
        try:
            for _ in range(batch_size):
                batch.append(next(it))
        except StopIteration:
            if batch:
                yield tuple(batch)
            break
        if batch:
            yield tuple(batch)


def delete_and_bulk_insert(
    sql_client,
    table: str,
    df: pd.DataFrame,
    *,
    delete_where: Optional[tuple[str, Sequence]] = None,
    batch_size: int = 1000,
) -> int:
    """DELETE existing rows (optional WHERE) then INSERT df rows in chunks.

    Parameters
    ----------
    sql_client : SQL client with ``cursor()`` and ``conn``/``commit`` semantics
    table : target table name (optionally schema-qualified)
    df : DataFrame to write (column order used for INSERT)
    delete_where : optional pair (where_sql, params), e.g. ("RunID = ?", [run_id])
    batch_size : rows per executemany chunk
    """
    if df is None or df.empty:
        return 0

    cols = df.columns.tolist()
    placeholders = ", ".join(["?" for _ in cols])
    insert_sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"

    cur = sql_client.cursor()
    try:
        # delete phase
        if delete_where is not None:
            where_sql, params = delete_where
            cur.execute(f"DELETE FROM {table} WHERE {where_sql}", params)

        # enable fast executemany if supported
        try:
            cur.fast_executemany = True
        except Exception:
            pass

        # chunked insert
        total = 0
        for batch in iter_batches(df, batch_size=batch_size):
            cur.executemany(insert_sql, batch)
            total += len(batch)

        # commit on connection if present, else via cursor
        try:
            sql_client.conn.commit()
        except Exception:
            try:
                cur.commit()
            except Exception:
                pass
        return total
    except Exception:
        # rollback best-effort
        try:
            sql_client.conn.rollback()
        except Exception:
            try:
                cur.rollback()
            except Exception:
                pass
        raise
    finally:
        try:
            cur.close()
        except Exception:
            pass


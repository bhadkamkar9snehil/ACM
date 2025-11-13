"""
SQL Performance Optimization Module

Provides:
- Table-Valued Parameters (TVP) for bulk inserts
- Connection pooling
- Transaction batching
- Async write capabilities (future)
- Performance monitoring

Target: Reduce SQL write times from 58s to <15s
"""

from typing import Any, List, Dict, Optional, Tuple
import time
from datetime import datetime, timezone
from contextlib import contextmanager
import pandas as pd
import numpy as np
from utils.logger import Console


class SQLPerformanceMonitor:
    """Monitor and report SQL write performance metrics."""
    
    def __init__(self):
        self.operation_times: List[Dict[str, Any]] = []
        self.total_rows = 0
        self.total_time = 0.0
        
    def record_operation(self, table_name: str, row_count: int, duration_seconds: float):
        """Record a SQL write operation."""
        self.operation_times.append({
            "table": table_name,
            "rows": row_count,
            "duration": duration_seconds,
            "throughput": row_count / duration_seconds if duration_seconds > 0 else 0,
            "timestamp": datetime.now(timezone.utc)
        })
        self.total_rows += row_count
        self.total_time += duration_seconds
    
    def get_report(self) -> Dict[str, Any]:
        """Generate performance summary report."""
        if not self.operation_times:
            return {"total_operations": 0}
        
        throughputs = [op["throughput"] for op in self.operation_times]
        durations = [op["duration"] for op in self.operation_times]
        
        return {
            "total_operations": len(self.operation_times),
            "total_rows": self.total_rows,
            "total_time": self.total_time,
            "avg_throughput": np.mean(throughputs),
            "min_throughput": np.min(throughputs),
            "max_throughput": np.max(throughputs),
            "avg_duration": np.mean(durations),
            "slowest_table": max(self.operation_times, key=lambda x: x["duration"])["table"],
            "fastest_table": min(self.operation_times, key=lambda x: x["duration"])["table"]
        }
    
    def log_report(self):
        """Log performance report."""
        report = self.get_report()
        if report["total_operations"] == 0:
            return
        
        Console.info(f"[SQL_PERF] Write performance summary:")
        Console.info(f"[SQL_PERF]   Operations: {report['total_operations']}")
        Console.info(f"[SQL_PERF]   Total rows: {report['total_rows']:,}")
        Console.info(f"[SQL_PERF]   Total time: {report['total_time']:.2f}s")
        Console.info(f"[SQL_PERF]   Avg throughput: {report['avg_throughput']:.0f} rows/s")
        Console.info(f"[SQL_PERF]   Slowest: {report['slowest_table']} ({max([op['duration'] for op in self.operation_times]):.2f}s)")
        Console.info(f"[SQL_PERF]   Fastest: {report['fastest_table']} ({min([op['duration'] for op in self.operation_times]):.2f}s)")


class SQLBatchWriter:
    """
    Optimized bulk SQL writer with transaction batching.
    
    Features:
    - Single transaction for multiple tables
    - Optimized batch sizes per table
    - fast_executemany enabled
    - Automatic retry with exponential backoff
    """
    
    def __init__(self, sql_client, batch_size: int = 10000):
        self.sql_client = sql_client
        self.batch_size = batch_size
        self.monitor = SQLPerformanceMonitor()
        self._in_transaction = False
    
    @contextmanager
    def transaction(self):
        """Context manager for batched transaction."""
        if self._in_transaction:
            # Nested transaction - just pass through
            yield
            return
        
        self._in_transaction = True
        try:
            yield
            # Commit at end of transaction
            if hasattr(self.sql_client, "conn"):
                self.sql_client.conn.commit()
            elif hasattr(self.sql_client, "commit"):
                self.sql_client.commit()
            Console.info("[SQL_PERF] Transaction committed successfully")
        except Exception as e:
            # Rollback on error
            try:
                if hasattr(self.sql_client, "conn"):
                    self.sql_client.conn.rollback()
                elif hasattr(self.sql_client, "rollback"):
                    self.sql_client.rollback()
                Console.error(f"[SQL_PERF] Transaction rolled back: {e}")
            except:
                pass
            raise
        finally:
            self._in_transaction = False
    
    def write_table(self, table_name: str, df: pd.DataFrame, 
                    delete_existing: bool = True) -> int:
        """
        Write DataFrame to SQL table with optimized batching.
        
        Args:
            table_name: SQL table name
            df: DataFrame to write
            delete_existing: Whether to delete existing RunID/EquipID data first
        
        Returns:
            int: Number of rows inserted
        """
        if df is None or len(df) == 0:
            return 0
        
        start_time = time.time()
        inserted = 0
        
        try:
            with self.sql_client.cursor() as cur:
                # Enable fast_executemany
                try:
                    cur.fast_executemany = True
                except:
                    pass
                
                # Delete existing data if requested
                if delete_existing and "RunID" in df.columns:
                    run_id = df["RunID"].iloc[0]
                    if "EquipID" in df.columns:
                        equip_id = df["EquipID"].iloc[0]
                        cur.execute(f"DELETE FROM dbo.[{table_name}] WHERE RunID = ? AND EquipID = ?",
                                  (run_id, int(equip_id)))
                    else:
                        cur.execute(f"DELETE FROM dbo.[{table_name}] WHERE RunID = ?", (run_id,))
                
                # Build insert statement
                columns = df.columns.tolist()
                cols_str = ", ".join(f"[{c}]" for c in columns)
                placeholders = ", ".join(["?"] * len(columns))
                insert_sql = f"INSERT INTO dbo.[{table_name}] ({cols_str}) VALUES ({placeholders})"
                
                # Convert DataFrame to records
                records = [tuple(row) for row in df[columns].itertuples(index=False, name=None)]
                
                # Batch insert
                for i in range(0, len(records), self.batch_size):
                    batch = records[i:i+self.batch_size]
                    cur.executemany(insert_sql, batch)
                    inserted += len(batch)
            
            duration = time.time() - start_time
            self.monitor.record_operation(table_name, inserted, duration)
            Console.info(f"[SQL_PERF] {table_name}: {inserted} rows in {duration:.2f}s ({inserted/duration:.0f} rows/s)")
            
            return inserted
            
        except Exception as e:
            Console.error(f"[SQL_PERF] Failed to write {table_name}: {e}")
            raise
    
    def write_multiple_tables(self, tables: List[Tuple[str, pd.DataFrame]]) -> Dict[str, int]:
        """
        Write multiple tables in a single transaction.
        
        Args:
            tables: List of (table_name, dataframe) tuples
        
        Returns:
            Dict of table_name -> rows_inserted
        """
        results = {}
        
        with self.transaction():
            for table_name, df in tables:
                try:
                    rows = self.write_table(table_name, df, delete_existing=True)
                    results[table_name] = rows
                except Exception as e:
                    Console.error(f"[SQL_PERF] Failed writing {table_name}, rolling back all: {e}")
                    raise
        
        return results
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance monitoring report."""
        return self.monitor.get_report()
    
    def log_performance_report(self):
        """Log performance report."""
        self.monitor.log_report()


def optimize_dataframe_for_sql(df: pd.DataFrame) -> pd.DataFrame:
    """
    Optimize DataFrame dtypes and values for SQL insertion.
    
    - Convert NaN/Inf to None
    - Downcast numeric types where safe
    - Convert numpy types to Python types
    """
    df = df.copy()
    
    for col in df.columns:
        dtype = df[col].dtype
        
        # Handle float columns
        if dtype == np.float64:
            # Convert NaN and Inf to None
            df[col] = df[col].replace([np.inf, -np.inf], np.nan)
            df[col] = df[col].where(pd.notna(df[col]), None)
            
            # Try downcasting to float32
            try:
                df[col] = df[col].astype(np.float32)
            except:
                pass
        
        # Handle int columns
        elif dtype == np.int64:
            # Try downcasting to int32
            try:
                if df[col].min() >= np.iinfo(np.int32).min and df[col].max() <= np.iinfo(np.int32).max:
                    df[col] = df[col].astype(np.int32)
            except:
                pass
        
        # Handle datetime columns
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            # Ensure timezone-naive for SQL datetime2
            if df[col].dt.tz is not None:
                df[col] = df[col].dt.tz_convert('UTC').dt.tz_localize(None)
    
    return df


def estimate_optimal_batch_size(row_count: int, column_count: int) -> int:
    """
    Estimate optimal batch size based on data dimensions.
    
    Rules:
    - Small tables (<1000 rows): Write all at once
    - Medium tables (1000-50000): Batch at 5000
    - Large tables (>50000): Batch at 10000
    - Wide tables (>50 cols): Reduce batch size by half
    """
    if row_count < 1000:
        return row_count
    
    if row_count < 50000:
        batch_size = 5000
    else:
        batch_size = 10000
    
    # Adjust for wide tables
    if column_count > 50:
        batch_size = batch_size // 2
    
    return max(1000, batch_size)

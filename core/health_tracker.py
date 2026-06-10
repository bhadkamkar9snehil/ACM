"""
Health Timeline Loader and Quality Assessment (v10.0.0)

Replaces scattered health loading logic from rul_engine.py and forecasting.py.
Provides unified interface for loading health data with comprehensive quality checks.

Key Features:
- SQL-first loading from ACM_HealthTimeline
- Rolling window enforcement (configurable history_window_hours, default 90 days)
- 5-level quality assessment (OK, SPARSE, GAPPY, FLAT, NOISY)
- Regime shift detection via Kolmogorov-Smirnov test
- Robust statistics and gap analysis
- DataSummary for ForecastEngine consumption (dt_hours, n_samples, start/end, quality)
- Research-backed thresholds

References:
- Box & Jenkins (1970): Time series diagnostics
- Cleveland (1979): Robust statistics for time series
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats

from core.observability import Console


class HealthQuality(Enum):
    """Data quality classification based on statistical properties"""
    OK = "OK"              # Sufficient data, good coverage, reasonable variance
    SPARSE = "SPARSE"      # Insufficient samples (< min_train_samples)
    GAPPY = "GAPPY"        # Large time gaps (> max_gap_hours)
    FLAT = "FLAT"          # Near-zero variance (std < min_std_dev)
    NOISY = "NOISY"        # Excessive variance (std > max_std_dev)
    MISSING = "MISSING"    # No data available


@dataclass
class HealthStatistics:
    """Comprehensive health timeline statistics"""
    n_samples: int
    mean: float
    std: float
    min: float
    max: float
    median: float
    q25: float
    q75: float
    iqr: float
    max_gap_hours: float
    mean_gap_hours: float
    total_duration_hours: float
    quality: HealthQuality
    quality_reason: str


@dataclass
class DataSummary:
    """
    Compact data summary for ForecastEngine consumption.
    
    Provides essential metadata without requiring ForecastEngine to recompute.
    All fields are pre-calculated by HealthTimeline for efficiency.
    
    Attributes:
        dt_hours: Data cadence in hours (median gap between samples)
        n_samples: Number of valid health samples
        start_time: First timestamp in window
        end_time: Last timestamp in window
        quality: HealthQuality enum (OK, SPARSE, GAPPY, FLAT, NOISY, MISSING)
        quality_reason: Human-readable explanation of quality flag
        window_hours: Effective window size (end_time - start_time)
    """
    dt_hours: float
    n_samples: int
    start_time: Optional['datetime'] = None
    end_time: Optional['datetime'] = None
    quality: HealthQuality = HealthQuality.MISSING
    quality_reason: str = "Not computed"
    window_hours: float = 0.0


class HealthTimeline:
    """
    Loads and validates health timeline data with quality assessment.
    
    Design Philosophy:
    - SQL-first (ACM_HealthTimeline) with rolling window enforcement (M3.1)
    - Fail-fast quality checks before expensive forecasting operations (M3.2)
    - DataSummary provides dt_hours, n_samples, start/end for ForecastEngine (M3.3)
    - Regime shift detection to trigger model retraining
    - Configurable thresholds from ACM_AdaptiveConfig
    
    Usage:
        tracker = HealthTimeline(
            sql_client=sql_client,
            equip_id=1,
            run_id="run_123",
            output_manager=output_mgr,
            min_train_samples=200,
            max_gap_hours=720.0,  # 30 days for historical replay
            history_window_hours=2160.0  # 90 days rolling window
        )
        df, quality = tracker.load_from_sql()
        if quality != HealthQuality.OK:
            Console.warn(f"Poor data quality: {quality.value}", component="HEALTH")
            return
        
        # Use DataSummary for ForecastEngine consumption
        summary = tracker.get_data_summary(df)
        Console.info(f"dt_hours={summary.dt_hours}, n_samples={summary.n_samples}", component="HEALTH")
        
        stats = tracker.get_statistics(df)
        shift_detected = tracker.detect_regime_shift(df, prev_health_df)
    """
    
    def __init__(
        self,
        sql_client: Optional[Any],
        equip_id: int,
        run_id: str,
        output_manager: Optional[Any] = None,
        min_train_samples: int = 200,
        max_gap_hours: float = 720.0,  # 30 days for historical replay
        # GRADUAL-DEGRADE-FIX (v11.14.1): Raised from 0.01 to 1.0.
        # HealthIndex is in the [0, 100] range. The old threshold of 0.01 meant
        # a signal had to vary by < 0.01 percentage points to be called FLAT —
        # essentially requiring bit-identical values. In practice this let through
        # nearly-constant signals (std ≈ 0.5 %) that carry no trend information
        # and cannot be reliably forecast. A threshold of 1.0 correctly flags
        # signals with less than 1 % standard deviation as insufficiently dynamic
        # for degradation trend fitting.
        min_std_dev: float = 1.0,
        max_std_dev: float = 50.0,
        max_timeline_rows: int = 10000,
        downsample_freq: str = "15min",
        history_window_hours: float = 2160.0  # 90 days rolling window (M3.1)
    ):
        """
        Initialize health timeline loader.
        
        Args:
            sql_client: Database connection (pyodbc)
            equip_id: Equipment ID from Equipment table
            run_id: ACM run identifier
            output_manager: OutputManager instance for cache access
            min_train_samples: Minimum rows for SPARSE check (default 200)
            max_gap_hours: Maximum time gap for GAPPY check (default 720 hours = 30 days)
            min_std_dev: Minimum std for FLAT check (default 0.01)
            max_std_dev: Maximum std for NOISY check (default 50.0)
            max_timeline_rows: Downsample threshold (default 10000)
            downsample_freq: Resample frequency when over limit (default "15min")
            history_window_hours: Rolling window size in hours (default 2160 = 90 days)
                                 Research-backed: avoids full-history overfitting
        """
        self.sql_client = sql_client
        self.equip_id = equip_id
        self.run_id = run_id
        self.output_manager = output_manager
        self.min_train_samples = min_train_samples
        self.max_gap_hours = max_gap_hours
        self.min_std_dev = min_std_dev
        self.max_std_dev = max_std_dev
        self.max_timeline_rows = max_timeline_rows
        self.downsample_freq = downsample_freq
        self.history_window_hours = history_window_hours
    
    def load_from_sql(self) -> Tuple[Optional[pd.DataFrame], HealthQuality]:
        """
        Load health timeline with SQL-first priority.
        
        Priority:
        1. SQL query (ACM_HealthTimeline) - ALWAYS for forecasting to get full history
        2. OutputManager cache (in-memory artifact) - DISABLED for forecasting
        NO CSV FALLBACK (v10.0.0 is SQL-only).
        
        Returns:
            (DataFrame, HealthQuality): Health data with Timestamp, HealthIndex, FusedZ columns
                                       and quality assessment
        """
        # CRITICAL: Skip cache for forecasting - must load ALL historical data
        # Cache contains only current run's data, forecasting needs multi-run history
        # if self.output_manager is not None:
        #     df = self.output_manager.get_cached_table("health_timeline.csv")
        #     if df is not None:
        #         Console.info(f"[HealthTracker] Using cached health_timeline ({len(df)} rows)")
        #         df = self._normalize_columns(df)
        #         df = self._apply_row_limit(df)
        #         quality = self.quality_check(df)
        #         return df, quality
        
        # SQL path
        if self.sql_client is None:
            Console.warn("No SQL client provided; cannot load health timeline", component="HEALTH")
            return None, HealthQuality.MISSING
        
        try:
            cur = self.sql_client.cursor()
            
            # M3.1: Rolling window enforcement (FIXED in v10.1.0)
            # CRITICAL FIX: Use MAX(Timestamp) from actual data, NOT datetime.now()
            # datetime.now() fails when data is historical/stale (e.g., batch replay)
            # Research shows rolling windows (30-90 days) produce better degradation models.
            
            # First, get the latest timestamp from actual data for this equipment
            cur.execute(
                """
                SELECT MAX(Timestamp) AS LatestTimestamp
                FROM dbo.ACM_HealthTimeline
                WHERE EquipID = ?
                """,
                (self.equip_id,),
            )
            row = cur.fetchone()
            
            if row is None or row[0] is None:
                cur.close()
                Console.warn(
                    f"[HealthTracker] No health timeline found for EquipID={self.equip_id} (empty table)"
                )
                return None, HealthQuality.MISSING
            
            latest_timestamp = row[0]
            window_cutoff = latest_timestamp - timedelta(hours=self.history_window_hours)
            
            Console.info(
                f"[HealthTracker] Data anchor: {latest_timestamp}, "
                f"window cutoff: {window_cutoff} ({self.history_window_hours:.0f}h lookback)"
            )
            
            cur.execute(
                """
                SELECT Timestamp, HealthIndex, FusedZ
                FROM dbo.ACM_HealthTimeline
                WHERE EquipID = ?
                  AND Timestamp >= ?
                ORDER BY Timestamp
                """,
                (self.equip_id, window_cutoff),
            )
            rows = cur.fetchall()
            cur.close()
            
            if not rows:
                Console.warn(
                    f"[HealthTracker] No health timeline found for EquipID={self.equip_id} "
                    f"in window {window_cutoff} to {latest_timestamp}"
                )
                return None, HealthQuality.MISSING
            
            df = pd.DataFrame.from_records(rows, columns=["Timestamp", "HealthIndex", "FusedZ"])
            Console.info(
                f"[HealthTracker] Loaded {len(df)} health points from SQL "
                f"(rolling window: {self.history_window_hours:.0f}h)"
            )
            
            df = self._normalize_columns(df)
            df = self._apply_row_limit(df)
            quality = self.quality_check(df)
            
            return df, quality
            
        except Exception as e:
            Console.warn(f"Failed to load health timeline from SQL: {e}", component="HEALTH")
            return None, HealthQuality.MISSING
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names and timestamps to standard format"""
        if df is None or df.empty:
            return df
        
        # Find timestamp column (case-insensitive)
        ts_col = None
        for col in ["Timestamp", "timestamp", "ts", "time"]:
            if col in df.columns:
                ts_col = col
                break
        if ts_col is None:
            ts_col = df.columns[0]  # Assume first column
        
        # Convert to datetime and strip timezone (ACM uses local-naive)
        df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
        if df[ts_col].dt.tz is not None:
            df[ts_col] = df[ts_col].dt.tz_localize(None)
        
        # Sort and drop invalid timestamps
        df = df.dropna(subset=[ts_col]).sort_values(ts_col).reset_index(drop=True)
        df = df.rename(columns={ts_col: "Timestamp"})
        
        return df
    
    def _apply_row_limit(self, df: pd.DataFrame) -> pd.DataFrame:
        """Downsample if timeline exceeds maximum rows"""
        if df is None or len(df) <= self.max_timeline_rows:
            return df
        
        Console.warn(
            f"Health timeline has {len(df)} rows (limit={self.max_timeline_rows}); "
            f"downsampling to {self.downsample_freq}",
            component="HEALTH"
        )
        
        df = df.set_index("Timestamp").resample(self.downsample_freq).mean().dropna().reset_index()
        return df
    
    def quality_check(self, df: pd.DataFrame) -> HealthQuality:
        """
        Assess data quality and return classification.
        
        Quality checks (fail-fast order):
        1. MISSING: No data
        2. SPARSE: Fewer than min_train_samples
        3. GAPPY: Time gaps exceed max_gap_hours
        4. FLAT: Std dev below min_std_dev (near-constant signal)
        5. NOISY: Std dev above max_std_dev (extreme variance)
        6. OK: Passes all checks
        
        Args:
            df: Health DataFrame with Timestamp, HealthIndex columns
        
        Returns:
            HealthQuality enum value
        """
        if df is None or df.empty:
            return HealthQuality.MISSING
        
        # Check 1: Sufficient samples
        if len(df) < self.min_train_samples:
            return HealthQuality.SPARSE
        
        # Check 2: Time gaps (detect missing data periods)
        if "Timestamp" in df.columns:
            time_diffs = df["Timestamp"].diff().dt.total_seconds() / 3600.0  # hours
            max_gap = time_diffs.max()
            if max_gap > self.max_gap_hours:
                return HealthQuality.GAPPY
        
        # Check 3: Signal variance (flat vs noisy)
        if "HealthIndex" in df.columns:
            std = df["HealthIndex"].std()
            if std < self.min_std_dev:
                # Low variance does NOT mean unforecastable: slow degradation
                # (e.g. -0.5%/week bearing wear) has tiny std but a steady,
                # fittable drift — exactly when prediction matters most.
                # Classify FLAT only when there is also no usable trend over
                # the window.
                trend_total = 0.0
                if "Timestamp" in df.columns and len(df) >= 10:
                    vals = pd.to_numeric(df["HealthIndex"], errors="coerce").to_numpy(dtype=float)
                    hours = (df["Timestamp"] - df["Timestamp"].iloc[0]).dt.total_seconds().to_numpy() / 3600.0
                    finite = np.isfinite(vals) & np.isfinite(hours)
                    if finite.sum() >= 10 and hours[finite][-1] > 0:
                        slope = float(np.polyfit(hours[finite], vals[finite], 1)[0])
                        trend_total = abs(slope) * float(hours[finite][-1] - hours[finite][0])
                if trend_total < self.min_std_dev:
                    return HealthQuality.FLAT
            if std > self.max_std_dev:
                return HealthQuality.NOISY

        return HealthQuality.OK
    
    def get_statistics(self, df: pd.DataFrame) -> HealthStatistics:
        """
        Compute comprehensive health timeline statistics.
        
        Includes:
        - Distributional stats (mean, std, quantiles)
        - Gap analysis (max gap, mean gap)
        - Duration metrics
        - Quality assessment with reason
        
        Args:
            df: Health DataFrame with Timestamp, HealthIndex columns
        
        Returns:
            HealthStatistics dataclass with all metrics
        """
        if df is None or df.empty:
            return HealthStatistics(
                n_samples=0, mean=0.0, std=0.0, min=0.0, max=0.0,
                median=0.0, q25=0.0, q75=0.0, iqr=0.0,
                max_gap_hours=0.0, mean_gap_hours=0.0, total_duration_hours=0.0,
                quality=HealthQuality.MISSING, quality_reason="No data available"
            )
        
        health = df["HealthIndex"] if "HealthIndex" in df.columns else df.iloc[:, 1]
        
        # Distributional statistics
        n_samples = len(df)
        mean = float(health.mean())
        std = float(health.std())
        min_val = float(health.min())
        max_val = float(health.max())
        median = float(health.median())
        q25 = float(health.quantile(0.25))
        q75 = float(health.quantile(0.75))
        iqr = q75 - q25
        
        # Gap analysis
        if "Timestamp" in df.columns and len(df) > 1:
            time_diffs = df["Timestamp"].diff().dt.total_seconds() / 3600.0
            max_gap_hours = float(time_diffs.max())
            mean_gap_hours = float(time_diffs.mean())
            total_duration_hours = (df["Timestamp"].iloc[-1] - df["Timestamp"].iloc[0]).total_seconds() / 3600.0
        else:
            max_gap_hours = 0.0
            mean_gap_hours = 0.0
            total_duration_hours = 0.0
        
        # Quality assessment with reason
        quality = self.quality_check(df)
        quality_reason = self._get_quality_reason(df, quality, std, max_gap_hours)
        
        return HealthStatistics(
            n_samples=n_samples,
            mean=mean,
            std=std,
            min=min_val,
            max=max_val,
            median=median,
            q25=q25,
            q75=q75,
            iqr=iqr,
            max_gap_hours=max_gap_hours,
            mean_gap_hours=mean_gap_hours,
            total_duration_hours=total_duration_hours,
            quality=quality,
            quality_reason=quality_reason
        )
    
    def _get_quality_reason(self, df: pd.DataFrame, quality: HealthQuality, std: float, max_gap: float) -> str:
        """Generate human-readable quality reason"""
        if quality == HealthQuality.MISSING:
            return "No data available"
        elif quality == HealthQuality.SPARSE:
            return f"Only {len(df)} samples (need {self.min_train_samples})"
        elif quality == HealthQuality.GAPPY:
            return f"Max gap {max_gap:.1f} hours (threshold {self.max_gap_hours} hours)"
        elif quality == HealthQuality.FLAT:
            return f"Std dev {std:.4f} (threshold {self.min_std_dev})"
        elif quality == HealthQuality.NOISY:
            return f"Std dev {std:.2f} (threshold {self.max_std_dev})"
        else:
            return f"{len(df)} samples, std={std:.2f}, max_gap={max_gap:.1f}h"
    
    def get_data_summary(self, df: pd.DataFrame) -> DataSummary:
        """
        Generate compact data summary for ForecastEngine consumption (M3.3).
        
        This provides pre-calculated metadata so ForecastEngine doesn't need to
        recompute statistics. Key fields:
        - dt_hours: Data cadence (median gap between consecutive samples)
        - n_samples: Number of valid health samples
        - start_time/end_time: Time boundaries of the data window
        - quality: HealthQuality enum
        - window_hours: Effective duration of the data window
        
        Args:
            df: Health DataFrame with Timestamp, HealthIndex columns
        
        Returns:
            DataSummary dataclass with essential metadata
        """
        if df is None or df.empty:
            return DataSummary(
                dt_hours=1.0,  # Default to hourly if unknown
                n_samples=0,
                start_time=None,
                end_time=None,
                quality=HealthQuality.MISSING,
                quality_reason="No data available",
                window_hours=0.0
            )
        
        n_samples = len(df)
        quality = self.quality_check(df)
        
        # Extract timestamps
        if "Timestamp" in df.columns:
            timestamps = pd.to_datetime(df["Timestamp"])
            start_time = timestamps.iloc[0].to_pydatetime()
            end_time = timestamps.iloc[-1].to_pydatetime()
            window_hours = (end_time - start_time).total_seconds() / 3600.0
            
            # Compute dt_hours as median gap (robust to outliers)
            if len(df) > 1:
                time_diffs = timestamps.diff().dt.total_seconds() / 3600.0
                dt_hours = float(time_diffs.median())
            else:
                dt_hours = 1.0  # Default if only one sample
        else:
            start_time = None
            end_time = None
            window_hours = 0.0
            dt_hours = 1.0
        
        # Generate quality reason
        std = df["HealthIndex"].std() if "HealthIndex" in df.columns else 0.0
        max_gap = time_diffs.max() if "Timestamp" in df.columns and len(df) > 1 else 0.0
        quality_reason = self._get_quality_reason(df, quality, std, max_gap)
        
        return DataSummary(
            dt_hours=dt_hours,
            n_samples=n_samples,
            start_time=start_time,
            end_time=end_time,
            quality=quality,
            quality_reason=quality_reason,
            window_hours=window_hours
        )

    def detect_regime_shift(
        self,
        current_df: pd.DataFrame,
        previous_df: pd.DataFrame,
        alpha: float = 0.05
    ) -> bool:
        """
        Detect regime shift between current and previous health data.
        
        Uses two-sample Kolmogorov-Smirnov test to detect distribution changes.
        Triggers model retraining when operational regime changes significantly.
        
        References:
        - Kolmogorov (1933): Distribution-free two-sample test
        - Massey (1951): KS test for goodness of fit
        
        Args:
            current_df: Current health timeline
            previous_df: Previous health timeline (from last model fit)
            alpha: Significance level (default 0.05)
        
        Returns:
            True if regime shift detected (p-value < alpha), False otherwise
        """
        if current_df is None or previous_df is None:
            return False
        
        if current_df.empty or previous_df.empty:
            return False
        
        if "HealthIndex" not in current_df.columns or "HealthIndex" not in previous_df.columns:
            return False
        
        try:
            current_health = current_df["HealthIndex"].dropna().values
            previous_health = previous_df["HealthIndex"].dropna().values
            
            if len(current_health) < 10 or len(previous_health) < 10:
                return False  # Insufficient data for reliable test
            
            # Two-sample KS test
            statistic, p_value = stats.ks_2samp(current_health, previous_health)
            
            shift_detected = p_value < alpha
            
            if shift_detected:
                Console.info(
                    f"Regime shift detected: KS statistic={statistic:.3f}, "
                    f"p-value={p_value:.4f} (threshold={alpha})",
                    component="HEALTH"
                )
            
            return shift_detected
            
        except Exception as e:
            Console.warn(f"Regime shift detection failed: {e}", component="HEALTH")
            return False

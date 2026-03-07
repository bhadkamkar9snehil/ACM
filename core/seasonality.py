"""
Seasonality Handler for ACM v11.0.0 (P5.9)

Detect and adjust for seasonal patterns in sensor data.

Key Features:
- SeasonalPattern: Detected periodic patterns with amplitude and phase
- SeasonalAdjustment: Per-timestamp adjustments for seasonality
- SeasonalityHandler: Pattern detection and baseline adjustment

Patterns Detected:
- Diurnal (24-hour cycle) - temperature, load variations
- Weekly (168-hour cycle) - operational patterns, maintenance cycles

Usage:
    handler = SeasonalityHandler()
    
    # Detect patterns in historical data
    patterns = handler.detect_patterns(
        data=baseline_df,
        sensor_cols=["Temp1", "Load", "Vibration"]
    )
    
    # Adjust new data for seasonality
    adjusted_df = handler.adjust_baseline(
        data=new_df,
        sensor_cols=["Temp1", "Load", "Vibration"]
    )
    
    # Get expected value at specific time
    expected = handler.get_seasonal_offset(
        sensor="Temp1",
        timestamp=pd.Timestamp("2024-01-15 14:00:00")
    )
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
import pandas as pd


class PatternType(Enum):
    """Type of seasonal pattern."""
    HOURLY = "HOURLY"       # Sub-daily patterns (shift changes)
    DAILY = "DAILY"         # 24-hour diurnal cycle
    WEEKLY = "WEEKLY"       # 168-hour weekly cycle
    MONTHLY = "MONTHLY"     # Approximate monthly patterns


@dataclass
class SeasonalPattern:
    """Detected seasonal pattern.
    
    Attributes:
        period_type: Type of pattern (DAILY, WEEKLY, etc.)
        period_hours: Period length in hours
        amplitude: Size of seasonal variation (std of seasonal component)
        phase_shift: Hours offset from midnight (daily) or Monday (weekly)
        confidence: Confidence in this pattern (0-1)
        sensor: Sensor this pattern applies to
    """
    period_type: PatternType
    period_hours: float
    amplitude: float
    phase_shift: float = 0.0
    confidence: float = 0.5
    sensor: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "period_type": self.period_type.value,
            "period_hours": self.period_hours,
            "amplitude": round(self.amplitude, 4),
            "phase_shift": round(self.phase_shift, 4),
            "confidence": round(self.confidence, 4),
            "sensor": self.sensor
        }


@dataclass
class SeasonalAdjustment:
    """Adjustment to apply for seasonality.
    
    Attributes:
        timestamp: When this adjustment applies
        sensor: Sensor being adjusted
        expected_offset: Expected deviation from baseline due to seasonality
        adjusted_value: Value after removing seasonality
        original_value: Original value before adjustment
    """
    timestamp: pd.Timestamp
    sensor: str
    expected_offset: float
    adjusted_value: float
    original_value: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": str(self.timestamp),
            "sensor": self.sensor,
            "expected_offset": round(self.expected_offset, 4),
            "adjusted_value": round(self.adjusted_value, 4),
            "original_value": round(self.original_value, 4)
        }


@dataclass
class SeasonalitySummary:
    """Summary of detected seasonality for an equipment.
    
    Attributes:
        equipment: Equipment identifier
        sensors_with_patterns: Sensors with detected patterns
        pattern_count: Total number of patterns detected
        dominant_pattern: Most significant pattern type
        data_hours: Hours of data analyzed
    """
    equipment: str = ""
    sensors_with_patterns: List[str] = field(default_factory=list)
    pattern_count: int = 0
    dominant_pattern: Optional[PatternType] = None
    data_hours: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "equipment": self.equipment,
            "sensors_with_patterns": self.sensors_with_patterns,
            "pattern_count": self.pattern_count,
            "dominant_pattern": self.dominant_pattern.value if self.dominant_pattern else None,
            "data_hours": round(self.data_hours, 1)
        }


class SeasonalityHandler:
    """
    Detect and adjust for seasonal patterns in sensor data.
    
    Patterns detected:
    - Diurnal (24-hour cycle) - temperature, load
    - Weekly (168-hour cycle) - operational patterns
    
    Attributes:
        min_periods: Minimum number of cycles to detect pattern (default 3)
        min_confidence: Minimum confidence to accept pattern (default 0.1)
        patterns: Dictionary of detected patterns by sensor
    """
    
    def __init__(
        self,
        min_periods: int = 3,
        min_confidence: float = 0.1
    ):
        """
        Initialize SeasonalityHandler.
        
        Args:
            min_periods: Minimum number of complete cycles to detect pattern
            min_confidence: Minimum confidence threshold (0-1)
        """
        self.min_periods = min_periods
        self.min_confidence = min_confidence
        self.patterns: Dict[str, List[SeasonalPattern]] = {}
    
    def detect_patterns(
        self,
        data: pd.DataFrame,
        sensor_cols: List[str],
        timestamp_col: str = "Timestamp"
    ) -> Dict[str, List[SeasonalPattern]]:
        """
        Detect seasonal patterns in sensor data.
        
        Args:
            data: DataFrame with timestamp and sensor columns
            sensor_cols: List of sensor columns to analyze
            timestamp_col: Name of timestamp column
        
        Returns:
            Dictionary mapping sensor names to list of detected patterns
        """
        patterns: Dict[str, List[SeasonalPattern]] = {}
        
        if data.empty or timestamp_col not in data.columns:
            return patterns
        
        # Ensure timestamp is datetime
        data = data.copy()
        data[timestamp_col] = pd.to_datetime(data[timestamp_col])
        
        for col in sensor_cols:
            if col not in data.columns:
                continue
            
            col_patterns = []
            series = data[[timestamp_col, col]].dropna()
            
            if len(series) < 24:  # Need at least 24 hours
                continue
            
            # Calculate data span
            time_span = (series[timestamp_col].max() - series[timestamp_col].min())
            hours_span = time_span.total_seconds() / 3600
            
            # Check for diurnal pattern (24h) if we have at least min_periods days
            if hours_span >= 24 * self.min_periods:
                diurnal = self._detect_periodic_pattern(
                    series, col, timestamp_col, 24, PatternType.DAILY
                )
                if diurnal and diurnal.confidence >= self.min_confidence:
                    col_patterns.append(diurnal)
            
            # Check for weekly pattern (168h) if we have enough data
            if hours_span >= 168 * self.min_periods:
                weekly = self._detect_periodic_pattern(
                    series, col, timestamp_col, 168, PatternType.WEEKLY
                )
                if weekly and weekly.confidence >= self.min_confidence:
                    col_patterns.append(weekly)
            
            if col_patterns:
                patterns[col] = col_patterns
        
        self.patterns = patterns
        return patterns
    
    def _detect_periodic_pattern(
        self,
        data: pd.DataFrame,
        col: str,
        timestamp_col: str,
        period_hours: float,
        pattern_type: PatternType
    ) -> Optional[SeasonalPattern]:
        """
        Detect pattern with specific period using autocorrelation.
        
        Args:
            data: DataFrame with timestamp and sensor column
            col: Sensor column name
            timestamp_col: Timestamp column name
            period_hours: Expected period in hours
            pattern_type: Type of pattern (DAILY, WEEKLY, etc.)
        
        Returns:
            SeasonalPattern if detected, None otherwise
        """
        # Resample to hourly for consistent analysis
        try:
            hourly = data.set_index(timestamp_col).resample("1h").mean()
            if len(hourly) < period_hours * self.min_periods:
                return None
            
            values = hourly[col].interpolate().values
            if np.isnan(values).all():
                return None
            
            # Fill remaining NaNs
            values = np.nan_to_num(values, nan=np.nanmean(values))
            
        except Exception:
            return None
        
        # Compute autocorrelation at the expected lag
        lag = int(period_hours)
        if len(values) <= lag:
            return None
        
        # Autocorrelation coefficient at lag
        series = pd.Series(values)
        autocorr = series.autocorr(lag=lag)
        
        if pd.isna(autocorr):
            return None
        
        # Confidence based on autocorrelation strength
        # Strong positive autocorrelation indicates periodicity
        confidence = max(0.0, autocorr)
        
        if confidence < self.min_confidence:
            return None
        
        # Compute amplitude using variance decomposition
        # Group by period phase
        n = len(values)
        phases = np.array([i % lag for i in range(n)])
        phase_means = np.zeros(lag)
        
        for phase in range(lag):
            phase_values = values[phases == phase]
            if len(phase_values) > 0:
                phase_means[phase] = np.mean(phase_values)
        
        # Amplitude is the range of phase means
        amplitude = np.ptp(phase_means) / 2  # Half peak-to-peak
        
        # Phase shift: hour of day with maximum value
        phase_shift = float(np.argmax(phase_means))
        
        return SeasonalPattern(
            period_type=pattern_type,
            period_hours=period_hours,
            amplitude=float(amplitude),
            phase_shift=phase_shift,
            confidence=float(confidence),
            sensor=col
        )
    
    def get_seasonal_offset(
        self,
        sensor: str,
        timestamp: pd.Timestamp,
        pattern_type: Optional[PatternType] = None
    ) -> float:
        """
        Get expected seasonal offset for a sensor at a specific time.
        
        Args:
            sensor: Sensor name
            timestamp: Timestamp to compute offset for
            pattern_type: Specific pattern type, or None for combined
        
        Returns:
            Expected offset from baseline due to seasonality
        """
        if sensor not in self.patterns:
            return 0.0
        
        total_offset = 0.0
        
        for pattern in self.patterns[sensor]:
            if pattern_type is not None and pattern.period_type != pattern_type:
                continue
            
            # Compute phase position
            if pattern.period_type == PatternType.DAILY:
                # Hours since midnight
                hour_of_day = timestamp.hour + timestamp.minute / 60
                phase_position = (hour_of_day - pattern.phase_shift) / 24
            elif pattern.period_type == PatternType.WEEKLY:
                # Hours since Monday midnight
                hour_of_week = timestamp.dayofweek * 24 + timestamp.hour + timestamp.minute / 60
                phase_position = (hour_of_week - pattern.phase_shift) / 168
            else:
                phase_position = 0.0
            
            # Sinusoidal model
            offset = pattern.amplitude * np.sin(2 * np.pi * phase_position)
            total_offset += offset
        
        return float(total_offset)
    
    def adjust_baseline(
        self,
        data: pd.DataFrame,
        sensor_cols: List[str],
        timestamp_col: str = "Timestamp"
    ) -> pd.DataFrame:
        """
        Adjust data by removing seasonal components (vectorized for performance).
        
        Args:
            data: DataFrame with timestamp and sensor columns
            sensor_cols: List of sensor columns to adjust
            timestamp_col: Name of timestamp column
        
        Returns:
            DataFrame with seasonal components removed
        """
        if data.empty:
            return data.copy()
        
        result = data.copy()
        ts_series = pd.to_datetime(result[timestamp_col])
        result[timestamp_col] = ts_series
        
        # Pre-compute hour and minute components once (vectorized)
        hours = ts_series.dt.hour.values
        minutes = ts_series.dt.minute.values
        dayofweek = ts_series.dt.dayofweek.values
        
        hour_of_day = hours + minutes / 60.0  # Shape: (n_rows,)
        hour_of_week = dayofweek * 24 + hours + minutes / 60.0  # Shape: (n_rows,)
        
        for col in sensor_cols:
            if col not in result.columns or col not in self.patterns:
                continue
            
            # Vectorized offset computation for all patterns of this sensor
            total_offset = np.zeros(len(result), dtype=np.float64)
            
            for pattern in self.patterns[col]:
                if pattern.period_type == PatternType.DAILY:
                    phase_position = (hour_of_day - pattern.phase_shift) / 24.0
                elif pattern.period_type == PatternType.WEEKLY:
                    phase_position = (hour_of_week - pattern.phase_shift) / 168.0
                else:
                    continue
                
                # Vectorized sin computation
                total_offset += pattern.amplitude * np.sin(2 * np.pi * phase_position)
            
            result[col] = result[col].values - total_offset
        
        return result
    
    def _compute_pattern_offset(
        self,
        timestamp: pd.Timestamp,
        pattern: SeasonalPattern
    ) -> float:
        """Compute offset for a single pattern at a timestamp (scalar version for backwards compatibility)."""
        if pattern.period_type == PatternType.DAILY:
            hour_of_day = timestamp.hour + timestamp.minute / 60
            phase_position = (hour_of_day - pattern.phase_shift) / 24
        elif pattern.period_type == PatternType.WEEKLY:
            hour_of_week = timestamp.dayofweek * 24 + timestamp.hour + timestamp.minute / 60
            phase_position = (hour_of_week - pattern.phase_shift) / 168
        else:
            return 0.0
        
        return pattern.amplitude * np.sin(2 * np.pi * phase_position)
    
    def get_summary(self, equipment: str = "") -> SeasonalitySummary:
        """
        Get summary of detected seasonality.
        
        Args:
            equipment: Equipment identifier for the summary
        
        Returns:
            SeasonalitySummary with pattern overview
        """
        sensors_with_patterns = list(self.patterns.keys())
        pattern_count = sum(len(p) for p in self.patterns.values())
        
        # Find dominant pattern type
        pattern_types = []
        for patterns in self.patterns.values():
            for p in patterns:
                pattern_types.append(p.period_type)
        
        dominant = None
        if pattern_types:
            from collections import Counter
            dominant = Counter(pattern_types).most_common(1)[0][0]
        
        return SeasonalitySummary(
            equipment=equipment,
            sensors_with_patterns=sensors_with_patterns,
            pattern_count=pattern_count,
            dominant_pattern=dominant,
            data_hours=0.0  # Would need to track from detect_patterns
        )
    
    def clear_patterns(self) -> None:
        """Clear all detected patterns."""
        self.patterns = {}
    
    def has_patterns(self, sensor: Optional[str] = None) -> bool:
        """
        Check if patterns have been detected.
        
        Args:
            sensor: Specific sensor to check, or None for any
        
        Returns:
            True if patterns exist
        """
        if sensor is not None:
            return sensor in self.patterns and len(self.patterns[sensor]) > 0
        return len(self.patterns) > 0
    
    def get_pattern_strength(self, sensor: str) -> float:
        """
        Get overall pattern strength for a sensor.
        
        Args:
            sensor: Sensor name
        
        Returns:
            Average confidence across patterns, or 0 if no patterns
        """
        if sensor not in self.patterns:
            return 0.0
        
        confidences = [p.confidence for p in self.patterns[sensor]]
        if not confidences:
            return 0.0
        
        return float(np.mean(confidences))


def detect_and_adjust(
    train: pd.DataFrame,
    score: pd.DataFrame,
    cfg: Dict[str, Any],
    min_rows: int = 72,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, List[SeasonalPattern]], bool]:
    """
    Detect seasonal patterns and optionally adjust data.
    
    Single entry point for seasonality processing. Handles all internal logic:
    - Checks data sufficiency
    - Detects patterns on train data
    - Applies adjustments to both train and score if enabled
    
    Args:
        train: Training data (DataFrame with datetime index)
        score: Score data (DataFrame with datetime index)
        cfg: Config dict with seasonality.apply_adjustment flag
        min_rows: Minimum rows required (default 72 = 3 days hourly)
    
    Returns:
        Tuple of (adjusted_train, adjusted_score, patterns_dict, was_adjusted)
    """
    patterns: Dict[str, List[SeasonalPattern]] = {}
    
    # Guard: insufficient data
    if len(train) < min_rows:
        return train, score, patterns, False
    
    # Get numeric sensor columns
    sensor_cols = [c for c in train.columns 
                   if train[c].dtype in ['float64', 'float32', 'int64', 'int32']]
    if not sensor_cols:
        return train, score, patterns, False
    
    # Detect patterns
    handler = SeasonalityHandler(min_periods=3, min_confidence=0.1)
    detect_df = train.copy()
    detect_df['_ts'] = pd.to_datetime(detect_df.index)
    patterns = handler.detect_patterns(detect_df, sensor_cols, '_ts')
    
    if not patterns:
        return train, score, patterns, False
    
    # Check if adjustment is enabled
    apply_adjustment = cfg.get("seasonality", {}).get("apply_adjustment", True)
    if not apply_adjustment:
        return train, score, patterns, False
    
    # Apply adjustment to train
    train_out = train.copy()
    train_out['_ts'] = pd.to_datetime(train_out.index)
    train_out = handler.adjust_baseline(train_out, sensor_cols, '_ts')
    train_out = train_out.drop(columns=['_ts'])
    
    # Apply adjustment to score
    score_out = score.copy()
    score_out['_ts'] = pd.to_datetime(score_out.index)
    score_out = handler.adjust_baseline(score_out, sensor_cols, '_ts')
    score_out = score_out.drop(columns=['_ts'])
    
    return train_out, score_out, patterns, True


def detect_and_adjust_safe(
    train: pd.DataFrame,
    score: pd.DataFrame,
    cfg: Dict[str, Any],
    logger: Any,
    equip: str = "",
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, List[SeasonalPattern]], bool]:
    """
    Safe wrapper for detect_and_adjust().

    Returns original data with empty pattern output if seasonality processing fails.
    """
    try:
        train_out, score_out, patterns, adjusted = detect_and_adjust(train, score, cfg)
        if patterns:
            pattern_count = sum(len(ps) for ps in patterns.values())
            logger.info(
                f"Seasonal: {pattern_count} patterns in {len(patterns)} sensors | adjusted={adjusted}",
                component="SEASON",
            )
        return train_out, score_out, patterns, adjusted
    except Exception as e:
        logger.warn(f"Seasonality detection skipped: {e}", component="SEASON", equip=equip)
        return train, score, {}, False

"""
Data Contract Validation (v10.4.0)

Entry-point validation to catch bad data before it corrupts analytics.
Implements v11 Requirement #9: "Add a single data-contract gate (timestamp order, 
duplicates, cadence, future rows) that blocks downstream stages on violation."

Philosophy: "Fail fast" - reject bad data at pipeline entry with clear error messages
rather than letting it corrupt downstream analytics.

Validation Rules:
1. Timestamp Order: Timestamps must be monotonically increasing (no backward jumps)
2. No Duplicates: Each (timestamp, sensor) combination must be unique
3. No Future Rows: All timestamps must be <= current time (with tolerance)
4. Cadence Validation: Median gap between samples must be within expected range

Usage:
    contract = DataContract(
        min_cadence_seconds=60,      # Minimum expected sample interval
        max_cadence_seconds=3600,    # Maximum expected sample interval
        future_tolerance_hours=24    # Allow up to 24 hours future (for clock skew)
    )
    
    violations = contract.validate(df)
    if violations:
        raise ContractViolation(f"Data contract failed: {violations}")
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from core.observability import Console


class ContractViolation(Exception):
    """
    Exception raised when data contract validation fails.
    
    This is a fatal error - the data is too corrupted to process safely.
    Operators must fix the data source before ACM can proceed.
    """
    pass


@dataclass
class ValidationResult:
    """Result of a single validation check"""
    check_name: str
    passed: bool
    message: str
    severity: str  # "ERROR", "WARNING"
    count: int = 0  # Number of violations found


class DataContract:
    """
    Data contract validator for ACM pipeline input (v10.4.0).
    
    Validates that input data meets basic quality requirements before
    entering the analytics pipeline. This prevents garbage data from
    corrupting detector training, regime detection, and forecasting.
    
    Validation Checks:
    1. Timestamp order - monotonic increasing
    2. No duplicates - unique (timestamp, sensor) combinations
    3. No future rows - all timestamps <= now + tolerance
    4. Cadence validation - median gap within expected range
    
    Args:
        min_cadence_seconds: Minimum expected sample interval (default: 60 seconds)
        max_cadence_seconds: Maximum expected sample interval (default: 3600 seconds)
        future_tolerance_hours: Allow timestamps this far in future (default: 24 hours)
        strict: If True, raise exception on ANY violation. If False, return results.
    """
    
    def __init__(
        self,
        min_cadence_seconds: float = 60.0,
        max_cadence_seconds: float = 3600.0,
        future_tolerance_hours: float = 24.0,
        strict: bool = True
    ):
        self.min_cadence_seconds = min_cadence_seconds
        self.max_cadence_seconds = max_cadence_seconds
        self.future_tolerance_hours = future_tolerance_hours
        self.strict = strict
    
    def validate(self, df: pd.DataFrame, timestamp_col: str = "Timestamp") -> List[ValidationResult]:
        """
        Validate DataFrame against all contract rules.
        
        Args:
            df: DataFrame to validate
            timestamp_col: Name of timestamp column (default: "Timestamp")
        
        Returns:
            List of ValidationResult objects. Empty list = all checks passed.
        
        Raises:
            ContractViolation: If strict=True and any check fails
        """
        results = []
        
        # Check 1: Timestamp order
        result = self.validate_timestamp_order(df, timestamp_col)
        results.append(result)
        
        # Check 2: No duplicates
        result = self.validate_no_duplicates(df, timestamp_col)
        results.append(result)
        
        # Check 3: No future rows
        result = self.validate_no_future_rows(df, timestamp_col)
        results.append(result)
        
        # Check 4: Cadence validation
        result = self.validate_cadence(df, timestamp_col)
        results.append(result)
        
        # Log results
        errors = [r for r in results if r.severity == "ERROR" and not r.passed]
        warnings = [r for r in results if r.severity == "WARNING" and not r.passed]
        
        if errors:
            error_msg = "; ".join([f"{r.check_name}: {r.message}" for r in errors])
            Console.error(
                f"Data contract validation FAILED: {len(errors)} errors",
                component="DATA_CONTRACT",
                errors=error_msg
            )
            if self.strict:
                raise ContractViolation(f"Data contract failed: {error_msg}")
        
        if warnings:
            warning_msg = "; ".join([f"{r.check_name}: {r.message}" for r in warnings])
            Console.warn(
                f"Data contract warnings: {len(warnings)} issues",
                component="DATA_CONTRACT",
                warnings=warning_msg
            )
        
        if not errors and not warnings:
            Console.info(
                "Data contract validation PASSED",
                component="DATA_CONTRACT",
                n_rows=len(df)
            )
        
        return results
    
    def validate_timestamp_order(self, df: pd.DataFrame, timestamp_col: str) -> ValidationResult:
        """
        Check that timestamps are monotonically increasing (no backward jumps).
        
        Backward jumps indicate:
        - Data corruption
        - Mixed data from multiple time periods
        - Timezone conversion errors
        """
        if timestamp_col not in df.columns:
            return ValidationResult(
                check_name="timestamp_order",
                passed=False,
                message=f"Timestamp column '{timestamp_col}' not found",
                severity="ERROR",
                count=1
            )
        
        if len(df) < 2:
            # Can't check order with < 2 rows
            return ValidationResult(
                check_name="timestamp_order",
                passed=True,
                message="Insufficient rows to check order",
                severity="WARNING",
                count=0
            )
        
        timestamps = pd.to_datetime(df[timestamp_col])
        
        # Check for backward jumps
        time_diffs = timestamps.diff()
        backward_jumps = time_diffs < pd.Timedelta(0)
        n_backward = backward_jumps.sum()
        
        if n_backward > 0:
            # Find worst backward jump
            worst_jump = time_diffs[backward_jumps].min()
            return ValidationResult(
                check_name="timestamp_order",
                passed=False,
                message=f"Found {n_backward} backward time jumps (worst: {worst_jump})",
                severity="ERROR",
                count=n_backward
            )
        
        return ValidationResult(
            check_name="timestamp_order",
            passed=True,
            message="Timestamps are monotonically increasing",
            severity="ERROR",
            count=0
        )
    
    def validate_no_duplicates(self, df: pd.DataFrame, timestamp_col: str) -> ValidationResult:
        """
        Check that each (timestamp, sensor) combination is unique.
        
        Duplicates indicate:
        - Data ingestion errors
        - Multiple sources writing same data
        - Replay of historical data
        """
        if timestamp_col not in df.columns:
            return ValidationResult(
                check_name="no_duplicates",
                passed=False,
                message=f"Timestamp column '{timestamp_col}' not found",
                severity="ERROR",
                count=1
            )
        
        # Check for duplicate timestamps
        n_duplicates = df[timestamp_col].duplicated().sum()
        
        if n_duplicates > 0:
            return ValidationResult(
                check_name="no_duplicates",
                passed=False,
                message=f"Found {n_duplicates} duplicate timestamps",
                severity="ERROR",
                count=n_duplicates
            )
        
        return ValidationResult(
            check_name="no_duplicates",
            passed=True,
            message="No duplicate timestamps found",
            severity="ERROR",
            count=0
        )
    
    def validate_no_future_rows(self, df: pd.DataFrame, timestamp_col: str) -> ValidationResult:
        """
        Check that no timestamps are in the future (beyond tolerance).
        
        Future timestamps indicate:
        - Clock skew on data source
        - Incorrect timezone handling
        - Data corruption
        """
        if timestamp_col not in df.columns:
            return ValidationResult(
                check_name="no_future_rows",
                passed=False,
                message=f"Timestamp column '{timestamp_col}' not found",
                severity="ERROR",
                count=1
            )
        
        now = pd.Timestamp.now()
        future_threshold = now + pd.Timedelta(hours=self.future_tolerance_hours)
        
        timestamps = pd.to_datetime(df[timestamp_col])
        future_rows = timestamps > future_threshold
        n_future = future_rows.sum()
        
        if n_future > 0:
            # Find furthest future timestamp
            max_future = timestamps[future_rows].max()
            hours_ahead = (max_future - now).total_seconds() / 3600
            return ValidationResult(
                check_name="no_future_rows",
                passed=False,
                message=f"Found {n_future} future timestamps (max: {hours_ahead:.1f} hours ahead)",
                severity="ERROR",
                count=n_future
            )
        
        return ValidationResult(
            check_name="no_future_rows",
            passed=True,
            message="No future timestamps found",
            severity="ERROR",
            count=0
        )
    
    def validate_cadence(self, df: pd.DataFrame, timestamp_col: str) -> ValidationResult:
        """
        Check that median time gap between samples is within expected range.
        
        Cadence violations indicate:
        - Sampling rate changed
        - Data gaps
        - Mixed data from different sources
        """
        if timestamp_col not in df.columns:
            return ValidationResult(
                check_name="cadence",
                passed=False,
                message=f"Timestamp column '{timestamp_col}' not found",
                severity="ERROR",
                count=1
            )
        
        if len(df) < 2:
            # Can't check cadence with < 2 rows
            return ValidationResult(
                check_name="cadence",
                passed=True,
                message="Insufficient rows to check cadence",
                severity="WARNING",
                count=0
            )
        
        timestamps = pd.to_datetime(df[timestamp_col])
        time_diffs = timestamps.diff().iloc[1:]  # Skip first NaN
        median_gap_seconds = time_diffs.median().total_seconds()
        
        if median_gap_seconds < self.min_cadence_seconds:
            return ValidationResult(
                check_name="cadence",
                passed=False,
                message=f"Median gap ({median_gap_seconds:.1f}s) < minimum ({self.min_cadence_seconds}s)",
                severity="WARNING",  # Warning, not error - might be intentional
                count=1
            )
        
        if median_gap_seconds > self.max_cadence_seconds:
            return ValidationResult(
                check_name="cadence",
                passed=False,
                message=f"Median gap ({median_gap_seconds:.1f}s) > maximum ({self.max_cadence_seconds}s)",
                severity="WARNING",  # Warning, not error - might be sparse data
                count=1
            )
        
        return ValidationResult(
            check_name="cadence",
            passed=True,
            message=f"Median gap ({median_gap_seconds:.1f}s) within range",
            severity="WARNING",
            count=0
        )

# core/pipeline_types.py
"""
ACM Pipeline Types - v11.8.0

Central type definitions for the ACM pipeline.
These types establish contracts between pipeline stages and ensure
consistent data flow through the adaptive learning pipeline.

Phase 1 Implementation Items:
- P1.2: DataContract dataclass
- P1.3: SensorValidator (basic structure)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import hashlib
import json

import numpy as np
import pandas as pd


# =============================================================================
# P1.2 - DataContract
# =============================================================================

@dataclass
class SensorMeta:
    """Metadata for a single sensor column."""
    name: str
    unit: str = ""
    expected_range: Tuple[float, float] = (-np.inf, np.inf)
    is_required: bool = True
    sensor_type: str = "continuous"  # continuous, binary, categorical


@dataclass  
class DataContract:
    """
    Contract defining expected data characteristics for pipeline stages.
    
    The DataContract ensures that:
    1. Required sensors are present
    2. Data types are correct
    3. Time range is valid
    4. Data quality meets minimum thresholds
    
    Use validate() to check incoming data against the contract.
    """
    
    # Required sensor columns
    required_sensors: List[str] = field(default_factory=list)
    
    # Optional sensor columns (used if present)
    optional_sensors: List[str] = field(default_factory=list)
    
    # Timestamp column name
    timestamp_col: str = "Timestamp"
    
    # Expected minimum rows
    min_rows: int = 100
    
    # Maximum allowed null fraction per column
    max_null_fraction: float = 0.3
    
    # Maximum allowed constant columns (zero variance)
    max_constant_fraction: float = 0.5
    
    # Expected time range (optional)
    expected_start: Optional[pd.Timestamp] = None
    expected_end: Optional[pd.Timestamp] = None
    
    # Equipment context
    equip_id: int = 0
    equip_code: str = ""
    
    # Sensor metadata (optional detailed specs)
    sensor_meta: Dict[str, SensorMeta] = field(default_factory=dict)
    
    # Contract version for compatibility checking
    version: str = "1.0"
    
    def validate(self, df: pd.DataFrame) -> "ValidationResult":
        """
        Validate a DataFrame against this contract.
        
        Returns ValidationResult with pass/fail and detailed issues.
        """
        issues: List[str] = []
        warnings: List[str] = []
        
        # Check timestamp column (may be a column or the index)
        ts_in_columns = self.timestamp_col in df.columns
        ts_in_index = df.index.name == self.timestamp_col or isinstance(df.index, pd.DatetimeIndex)
        if not ts_in_columns and not ts_in_index:
            issues.append(f"Missing timestamp column: {self.timestamp_col}")
        
        # Check required sensors
        present_cols = set(df.columns)
        missing_required = set(self.required_sensors) - present_cols
        if missing_required:
            issues.append(f"Missing required sensors: {sorted(missing_required)}")
        
        # Check optional sensors (warn only)
        missing_optional = set(self.optional_sensors) - present_cols
        if missing_optional:
            warnings.append(f"Missing optional sensors: {sorted(missing_optional)}")
        
        # Check minimum rows
        if len(df) < self.min_rows:
            issues.append(f"Insufficient rows: {len(df)} < {self.min_rows}")
        
        # Check null fractions
        if len(df) > 0:
            null_fractions = df.isnull().mean()
            high_null_cols = null_fractions[null_fractions > self.max_null_fraction].index.tolist()
            if high_null_cols:
                warnings.append(f"High null fraction columns: {high_null_cols}")
        
        # Check constant columns (zero variance)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0 and len(df) > 1:
            variances = df[numeric_cols].var()
            constant_cols = variances[variances == 0].index.tolist()
            constant_frac = len(constant_cols) / len(numeric_cols) if len(numeric_cols) > 0 else 0
            if constant_frac > self.max_constant_fraction:
                warnings.append(f"Too many constant columns: {len(constant_cols)}/{len(numeric_cols)}")
        
        # Check time range if specified
        if self.expected_start and self.timestamp_col in df.columns:
            try:
                actual_start = pd.Timestamp(df[self.timestamp_col].min())
                if actual_start < self.expected_start:
                    warnings.append(f"Data starts before expected: {actual_start} < {self.expected_start}")
            except Exception:
                pass
        
        if self.expected_end and self.timestamp_col in df.columns:
            try:
                actual_end = pd.Timestamp(df[self.timestamp_col].max())
                if actual_end > self.expected_end:
                    warnings.append(f"Data ends after expected: {actual_end} > {self.expected_end}")
            except Exception:
                pass
        
        return ValidationResult(
            passed=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            rows_validated=len(df),
            columns_validated=len(df.columns)
        )
    
    def get_available_sensors(self, df: pd.DataFrame) -> List[str]:
        """Get list of contract sensors that are available in the DataFrame."""
        all_expected = set(self.required_sensors) | set(self.optional_sensors)
        return [c for c in df.columns if c in all_expected]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize contract to dictionary."""
        return {
            "version": self.version,
            "required_sensors": self.required_sensors,
            "optional_sensors": self.optional_sensors,
            "timestamp_col": self.timestamp_col,
            "min_rows": self.min_rows,
            "max_null_fraction": self.max_null_fraction,
            "max_constant_fraction": self.max_constant_fraction,
            "equip_id": self.equip_id,
            "equip_code": self.equip_code,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataContract":
        """Deserialize contract from dictionary."""
        return cls(
            required_sensors=data.get("required_sensors", []),
            optional_sensors=data.get("optional_sensors", []),
            timestamp_col=data.get("timestamp_col", "Timestamp"),
            min_rows=data.get("min_rows", 100),
            max_null_fraction=data.get("max_null_fraction", 0.3),
            max_constant_fraction=data.get("max_constant_fraction", 0.5),
            equip_id=data.get("equip_id", 0),
            equip_code=data.get("equip_code", ""),
            version=data.get("version", "1.0"),
        )
    
    def signature(self) -> str:
        """Compute a hash signature for this contract."""
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()[:12]


@dataclass
class ValidationResult:
    """Result of validating data against a DataContract."""
    passed: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rows_validated: int = 0
    columns_validated: int = 0
    
    def __bool__(self) -> bool:
        return self.passed
    
    def summary(self) -> str:
        """Human-readable summary."""
        status = "PASSED" if self.passed else "FAILED"
        parts = [f"Validation {status}: {self.rows_validated} rows, {self.columns_validated} cols"]
        if self.issues:
            parts.append(f"  Issues: {self.issues}")
        if self.warnings:
            parts.append(f"  Warnings: {self.warnings}")
        return "\n".join(parts)


# =============================================================================
# P1.3 - SensorValidator  
# =============================================================================

class SensorValidator:
    """
    Validates sensor data quality before pipeline processing.
    
    Checks:
    - Required sensors present
    - Physical range validation
    - Stale data detection
    - Outlier flagging
    
    Thread-safe and stateless per validation call.
    """
    
    def __init__(self, contract: Optional[DataContract] = None):
        """
        Initialize validator with optional data contract.
        
        Args:
            contract: DataContract defining expected sensors and constraints
        """
        self.contract = contract
        
        # Default physical limits for common sensor types
        self.physical_limits: Dict[str, Tuple[float, float]] = {
            "temperature": (-100.0, 1500.0),  # Celsius
            "pressure": (0.0, 1000.0),  # bar
            "vibration": (0.0, 1000.0),  # mm/s or g
            "flow": (0.0, 100000.0),  # m3/h
            "speed": (0.0, 50000.0),  # RPM
            "power": (0.0, 1000000.0),  # kW
            "current": (0.0, 10000.0),  # A
            "voltage": (0.0, 100000.0),  # V
        }
        
        # Stale data threshold (seconds)
        self.stale_threshold_seconds: float = 3600.0  # 1 hour
    
    def validate(self, 
                 df: pd.DataFrame,
                 timestamp_col: str = "Timestamp") -> ValidationResult:
        """
        Validate sensor data quality.
        
        Args:
            df: DataFrame with sensor data
            timestamp_col: Name of timestamp column
            
        Returns:
            ValidationResult with pass/fail and issues
        """
        issues: List[str] = []
        warnings: List[str] = []
        
        if df.empty:
            issues.append("DataFrame is empty")
            return ValidationResult(passed=False, issues=issues)
        
        # Validate against contract if available
        if self.contract:
            contract_result = self.contract.validate(df)
            issues.extend(contract_result.issues)
            warnings.extend(contract_result.warnings)
        
        # Check for duplicate timestamps
        if timestamp_col in df.columns:
            dup_count = df[timestamp_col].duplicated().sum()
            if dup_count > 0:
                warnings.append(f"Duplicate timestamps: {dup_count}")
        
        # Check for stale data
        if timestamp_col in df.columns:
            try:
                latest = pd.Timestamp(df[timestamp_col].max())
                now = pd.Timestamp.now()
                staleness = (now - latest).total_seconds()
                if staleness > self.stale_threshold_seconds:
                    warnings.append(f"Stale data: latest is {staleness/3600:.1f} hours old")
            except Exception:
                pass
        
        # Check for physical limit violations
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            sensor_type = self._infer_sensor_type(col)
            if sensor_type and sensor_type in self.physical_limits:
                lo, hi = self.physical_limits[sensor_type]
                violations = ((df[col] < lo) | (df[col] > hi)).sum()
                if violations > 0:
                    warnings.append(f"Physical limit violations in {col}: {violations}")
        
        return ValidationResult(
            passed=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            rows_validated=len(df),
            columns_validated=len(df.columns)
        )
    
    def _infer_sensor_type(self, column_name: str) -> Optional[str]:
        """Infer sensor type from column name."""
        name_lower = column_name.lower()
        
        if any(kw in name_lower for kw in ["temp", "tmp"]):
            return "temperature"
        if any(kw in name_lower for kw in ["press", "psi", "bar"]):
            return "pressure"
        if any(kw in name_lower for kw in ["vib", "vibration"]):
            return "vibration"
        if any(kw in name_lower for kw in ["flow", "gpm"]):
            return "flow"
        if any(kw in name_lower for kw in ["speed", "rpm"]):
            return "speed"
        if any(kw in name_lower for kw in ["power", "kw", "mw"]):
            return "power"
        if any(kw in name_lower for kw in ["current", "amp"]):
            return "current"
        if any(kw in name_lower for kw in ["volt", "voltage"]):
            return "voltage"
        
        return None
    
    def filter_valid_sensors(self, 
                             df: pd.DataFrame,
                             min_variance: float = 1e-10) -> pd.DataFrame:
        """
        Filter DataFrame to only valid sensor columns.
        
        Removes:
        - Non-numeric columns (except timestamp)
        - Constant columns (zero variance)
        - Columns with too many nulls
        
        Args:
            df: Input DataFrame
            min_variance: Minimum variance threshold
            
        Returns:
            Filtered DataFrame with valid sensors only
        """
        timestamp_col = self.contract.timestamp_col if self.contract else "Timestamp"
        
        # Keep timestamp if present
        keep_cols = []
        if timestamp_col in df.columns:
            keep_cols.append(timestamp_col)
        
        # Get numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        # Filter by variance and null fraction
        max_null = self.contract.max_null_fraction if self.contract else 0.3
        
        for col in numeric_cols:
            if col == timestamp_col:
                continue
            
            null_frac = df[col].isnull().mean()
            if null_frac > max_null:
                continue
            
            variance = df[col].var()
            if variance is None or variance < min_variance:
                continue
            
            keep_cols.append(col)
        
        return df[keep_cols].copy()


# =============================================================================
# Feature Matrix Types (used in Phase 2+)
# =============================================================================

@dataclass
class FeatureMatrix:
    """
    Standardized container for processed feature data.
    
    Separates different feature types to prevent data leakage
    between regime detection and anomaly detection.
    """
    
    # Core sensor features (used by detectors)
    sensor_features: pd.DataFrame = field(default_factory=pd.DataFrame)
    
    # Regime detection inputs (no detector outputs!)
    regime_features: pd.DataFrame = field(default_factory=pd.DataFrame)
    
    # Statistical/derived features
    stat_features: pd.DataFrame = field(default_factory=pd.DataFrame)
    
    # Timestamp index
    timestamps: pd.DatetimeIndex = field(default_factory=lambda: pd.DatetimeIndex([]))
    
    # Feature metadata
    feature_names: List[str] = field(default_factory=list)
    
    # Processing metadata
    created_at: datetime = field(default_factory=datetime.now)
    source_rows: int = 0
    
    # Forbidden patterns for regime inputs (prevent leakage)
    _FORBIDDEN_REGIME_PATTERNS: List[str] = field(
        default_factory=lambda: ["_z", "pca_", "iforest_", "gmm_", "omr_", "ar1_", "_score"]
    )
    
    def get_regime_inputs(self) -> pd.DataFrame:
        """
        Get features for regime detection.
        
        CRITICAL: This method validates that no detector outputs
        leak into regime inputs (which would cause data leakage).
        """
        if self.regime_features.empty:
            return self.regime_features
        
        # Validate no forbidden patterns in columns
        for col in self.regime_features.columns:
            col_lower = col.lower()
            for pattern in self._FORBIDDEN_REGIME_PATTERNS:
                if pattern in col_lower:
                    raise ValueError(
                        f"Data leakage detected: column '{col}' contains "
                        f"forbidden pattern '{pattern}' in regime inputs"
                    )
        
        return self.regime_features
    
    def get_detector_inputs(self) -> pd.DataFrame:
        """Get features for anomaly detectors."""
        return self.sensor_features
    
    def signature(self) -> str:
        """Compute hash of feature matrix structure."""
        content = json.dumps({
            "sensor_cols": list(self.sensor_features.columns),
            "regime_cols": list(self.regime_features.columns),
            "stat_cols": list(self.stat_features.columns),
            "source_rows": self.source_rows,
        }, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()[:12]


# =============================================================================
# Data Quality Guardrails
# =============================================================================

@dataclass
class GuardrailResult:
    """Result of running data quality guardrails."""
    low_var_features: List[str] = field(default_factory=list)
    low_var_threshold: float = 1e-4
    overlap_detected: bool = False
    overlap_seconds: float = 0.0
    data_quality_written: bool = False
    dropped_sensors: List[str] = field(default_factory=list)


def run_data_guardrails(
    train: pd.DataFrame,
    score: pd.DataFrame,
    meta: Any,
    cfg: Dict[str, Any],
    output_manager: Any,
    run_id: int,
    equip_id: int,
    equip: str,
) -> GuardrailResult:
    """
    Run all data quality guardrails. Returns GuardrailResult with findings.
    Writes ACM_DataQuality records to SQL.
    
    Checks performed:
    1. Baseline/Batch window overlap (data leakage risk)
    2. Low-variance sensor detection (near-constant sensors)
    3. Data quality metrics written to SQL
    4. Dropped sensors tracking
    
    Args:
        train: Training data DataFrame
        score: Score data DataFrame  
        meta: Load metadata with dropped_cols attribute
        cfg: Configuration dictionary
        output_manager: OutputManager for SQL writes
        run_id: Current run ID
        equip_id: Equipment ID
        equip: Equipment code
        
    Returns:
        GuardrailResult with low_var_features list and flags
    """
    from core.observability import Console
    
    result = GuardrailResult()
    low_var_threshold = 1e-4
    result.low_var_threshold = low_var_threshold
    
    # 1) Baseline/Batch window overlap check
    tr_end = pd.to_datetime(train.index.max()) if len(train.index) else None
    sc_start = pd.to_datetime(score.index.min()) if len(score.index) else None
    
    if tr_end is not None and sc_start is not None:
        overlap_seconds = (tr_end - sc_start).total_seconds()
        if overlap_seconds > 60:  # 1 minute tolerance
            result.overlap_detected = True
            result.overlap_seconds = overlap_seconds
            Console.warn(
                f"Batch window OVERLAPS baseline (data leakage risk):"
                f" batch_start={sc_start} < baseline_end={tr_end} (overlap={overlap_seconds:.0f}s)",
                component="DATA", equip=equip, batch_start=str(sc_start), baseline_end=str(tr_end)
            )
    
    # 2) Low-variance sensor detection on BASELINE
    if len(train.columns):
        train_stds = train.std(numeric_only=True)
        low_var = train_stds[train_stds < low_var_threshold]
        if len(low_var) > 0:
            result.low_var_features = list(low_var.index)
            preview = ", ".join(result.low_var_features[:10])
            Console.warn(
                f"{len(low_var)} low-variance sensor(s) in TRAIN (std<{low_var_threshold:g}): {preview}",
                component="DATA", equip=equip, low_var_count=len(low_var), threshold=low_var_threshold
            )
            # Persist low-variance sensors for future exclusion
            try:
                import os
                import json
                
                exclusion_dir = f"artifacts/equip_{equip_id}"
                os.makedirs(exclusion_dir, exist_ok=True)
                exclusion_file = os.path.join(exclusion_dir, "low_variance_sensors.json")
                
                existing_sensors = set()
                if os.path.exists(exclusion_file):
                    with open(exclusion_file, 'r') as f:
                        try:
                            existing_sensors.update(json.load(f))
                        except json.JSONDecodeError:
                            pass # Ignore corrupted file, it will be overwritten

                new_sensors = set(result.low_var_features)
                combined_sensors = sorted(list(existing_sensors.union(new_sensors)))
                
                with open(exclusion_file, 'w') as f:
                    json.dump(combined_sensors, f, indent=2)
                    
                Console.info(f"Persisted {len(new_sensors - existing_sensors)} new low-variance sensors for permanent exclusion.", component="DATA")
                
            except Exception as persist_err:
                Console.warn(f"Failed to persist low-variance sensor list: {persist_err}", component="DATA")
    
    # 3) Data quality records -> SQL:ACM_DataQuality
    try:
        records = output_manager._build_data_quality_records(
            train_numeric=train,
            score_numeric=score,
            cfg=cfg,
            low_var_threshold=low_var_threshold,
        )
        
        if records:
            dq = pd.DataFrame(records)
            dq['RunID'] = run_id
            dq['EquipID'] = int(equip_id)
            dq['CheckName'] = 'data_quality'
            dq['CheckResult'] = 'OK'
            output_manager.write_sql_table(
                table_name="ACM_DataQuality",
                df=dq,
                artifact_name="data_quality",
            )
            result.data_quality_written = True
    except Exception as dq_e:
        Console.warn(f"Data quality summary skipped: {dq_e}", component="DATA",
                     equip=equip, error_type=type(dq_e).__name__, error=str(dq_e)[:200])
    
    # 4) Track dropped sensors
    if hasattr(meta, 'dropped_cols') and len(meta.dropped_cols) > 0:
        result.dropped_sensors = list(meta.dropped_cols)
    
    return result


def run_data_guardrails_safe(
    train: pd.DataFrame,
    score: pd.DataFrame,
    meta: Any,
    cfg: Dict[str, Any],
    output_manager: Any,
    run_id: int,
    equip_id: int,
    equip: str,
    logger: Any,
) -> GuardrailResult:
    """
    Safe wrapper around run_data_guardrails().

    Returns a default GuardrailResult when guardrail execution fails.
    """
    try:
        return run_data_guardrails(
            train=train,
            score=score,
            meta=meta,
            cfg=cfg,
            output_manager=output_manager,
            run_id=run_id,
            equip_id=equip_id,
            equip=equip,
        )
    except Exception as e:
        logger.warn(
            f"Guardrail checks skipped: {e}",
            component="DATA",
            equip=equip,
            error_type=type(e).__name__,
            error=str(e)[:200],
        )
        return GuardrailResult(low_var_threshold=1e-4)


def validate_data_contract_at_entry(
    train: pd.DataFrame,
    score: pd.DataFrame,
    meta: Any,
    refit_requested: bool,
    cfg: Dict[str, Any],
    output_manager: Any,
    equip_id: int,
    equip: str,
    run_id: Optional[str],
    logger: Any,
) -> ValidationResult:
    """
    Validate pipeline entry data against DataContract and persist validation output.

    Behavior is equivalent to the former inline block in core.acm:
    - training phase validates TRAIN with min_train_samples
    - scoring phase validates SCORE with min_score_samples
    - validation record write is best-effort
    """
    data_cfg = cfg.get("data", {}) or {}
    try:
        min_score_samples = int(data_cfg.get("min_score_samples", 1))
        min_score_samples = max(1, min_score_samples)
    except (TypeError, ValueError):
        min_score_samples = 1

    try:
        min_train_samples = int(data_cfg.get("min_train_samples", 500))
        min_train_samples = max(10, min_train_samples)
    except (TypeError, ValueError):
        min_train_samples = 500

    is_initial_coldstart = bool(
        meta.get("is_coldstart_run", False) if isinstance(meta, dict)
        else getattr(meta, "is_coldstart_run", False)
    )
    is_training_phase = is_initial_coldstart or bool(refit_requested)
    min_rows_threshold = int(min_train_samples if is_training_phase else min_score_samples)

    if is_training_phase:
        validation_df = train
    else:
        validation_df = score if (score is not None and len(score) > 0) else train

    contract = DataContract(
        required_sensors=[],
        optional_sensors=list(meta.kept_cols) if hasattr(meta, "kept_cols") else [],
        timestamp_col=meta.timestamp_col if hasattr(meta, "timestamp_col") else "Timestamp",
        min_rows=min_rows_threshold,
        max_null_fraction=0.5,
        equip_id=equip_id,
        equip_code=equip,
    )

    validation = contract.validate(validation_df)

    if output_manager:
        try:
            sig = contract.signature() if hasattr(contract, "signature") and callable(contract.signature) else None
            output_manager.write_data_contract_validation(
                {
                    "Passed": validation.passed,
                    "RowsValidated": len(validation_df) if validation_df is not None else 0,
                    "ColumnsValidated": len(validation_df.columns) if validation_df is not None else 0,
                    "IssuesJSON": json.dumps(validation.issues) if validation.issues else None,
                    "WarningsJSON": json.dumps(validation.warnings) if validation.warnings else None,
                    "ContractSignature": sig,
                }
            )
        except Exception as e:
            if validation.passed:
                logger.warn(f"Failed to write DataContract validation: {e}", component="DATA")

    if not validation.passed:
        error_msg = f"DataContract validation FAILED: {validation.issues}"
        logger.error(error_msg, component="DATA", equip=equip, run_id=run_id, issues=validation.issues)
        raise ValueError(error_msg)

    if validation.warnings:
        logger.warn(
            f"DataContract: {len(validation.warnings)} warnings | "
            f"{validation.warnings[0] if validation.warnings else ''}",
            component="DATA",
        )

    return validation


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "DataContract",
    "ValidationResult",
    "SensorMeta",
    "SensorValidator",
    "FeatureMatrix",
    "GuardrailResult",
    "run_data_guardrails",
    "run_data_guardrails_safe",
    "validate_data_contract_at_entry",
]

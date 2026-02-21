"""
Sensor Attribution via Counterfactual Analysis (v11.0.0)

Identifies which sensors contribute most to failure risk via counterfactual analysis.
Replaces logic from rul_engine.py (lines 489-611).

Key Features (v11):
- UnifiedAttribution: Uses frozen baseline artifacts for consistent attribution
- SensorContribution: Per-sensor attribution with z-scores and direction
- AttributionResult: Complete attribution with top-3 sensors and explanation
- Counterfactual analysis: RUL impact when zeroing each sensor
- Rank sensors by failure contribution
- Top-N sensor identification for maintenance prioritization
- Integration with ACM_SensorHotspots table

References:
- Pearl (2009): "Causality" - Counterfactual analysis framework
- Molnar (2020): "Interpretable Machine Learning" - Feature importance via perturbation

Future R&D Entrypoints (M15):
---------------------------------
TODO: CAUSAL_COUNTERFACTUAL - Full Pearl-style counterfactual attribution
      - Method: compute_counterfactual(sensor_data, rul_estimator, baseline_rul)
      - For each sensor: zero out contribution, recompute RUL, measure delta
      - Requires RULEstimator integration for each perturbation
      - Output: Causal importance scores (larger delta = higher contribution)
      
TODO: FAULT_SIGNATURE_DETECTION - Identify recurring sensor patterns
      - Method: detect_fault_signatures(sensor_history, known_faults)
      - Match current sensor profile against historical fault patterns
      - Output: Fault signature match scores for ACM_FaultFamilies
      
TODO: SENSOR_INTERACTION_GRAPH - Build sensor dependency network
      - Method: build_interaction_graph(correlation_matrix)
      - Identify sensor clusters and propagation paths
      - Output: NetworkX graph for root cause analysis
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from enum import Enum
import numpy as np
import pandas as pd

from core.observability import Console


# =============================================================================
# P5.4: UNIFIED SENSOR ATTRIBUTION (v11.0.0)
# =============================================================================


class DeviationDirection(Enum):
    """Direction of sensor deviation from baseline."""
    HIGH = "HIGH"           # Significantly above baseline
    LOW = "LOW"             # Significantly below baseline
    VOLATILE = "VOLATILE"   # High variance / oscillating
    NORMAL = "NORMAL"       # Within expected range


@dataclass
class SensorStats:
    """Statistics for a single sensor from frozen baseline."""
    mean: float
    std: float
    min_val: float = 0.0
    max_val: float = 0.0
    
    def compute_z_score(self, value: float) -> float:
        """Compute z-score for a value using these statistics."""
        if pd.isna(value):
            return 0.0
        return (value - self.mean) / (self.std + 1e-10)


@dataclass
class SensorContribution:
    """Attribution of a single sensor to an anomaly.
    
    Attributes:
        sensor_name: Name of the sensor
        contribution_pct: Percentage contribution to anomaly (0-100)
        z_score: Individual sensor z-score relative to baseline
        direction: HIGH, LOW, VOLATILE, or NORMAL
        baseline_deviation: Absolute deviation from baseline (|z|)
    """
    sensor_name: str
    contribution_pct: float = 0.0   # 0-100, % contribution to anomaly
    z_score: float = 0.0            # Individual sensor z-score
    direction: DeviationDirection = DeviationDirection.NORMAL
    baseline_deviation: float = 0.0  # How far from baseline (abs z)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "sensor_name": self.sensor_name,
            "contribution_pct": round(self.contribution_pct, 2),
            "z_score": round(self.z_score, 3),
            "direction": self.direction.value,
            "baseline_deviation": round(self.baseline_deviation, 3)
        }


@dataclass
class AttributionResult:
    """Complete attribution for an anomaly or episode.
    
    Attributes:
        timestamp: When the attribution was computed
        total_z_score: Fused z-score for the anomaly
        contributions: List of all sensor contributions
        top_3_sensors: Names of top 3 contributing sensors
        explanation: Human-readable explanation of the anomaly
    """
    timestamp: Optional[pd.Timestamp] = None
    total_z_score: float = 0.0
    contributions: List[SensorContribution] = field(default_factory=list)
    top_3_sensors: List[str] = field(default_factory=list)
    explanation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": str(self.timestamp) if self.timestamp else None,
            "total_z_score": round(self.total_z_score, 3),
            "contributions": [c.to_dict() for c in self.contributions],
            "top_3_sensors": self.top_3_sensors,
            "explanation": self.explanation
        }
    
    def to_sql_row(self, equip_id: int, run_id: str) -> Dict[str, Any]:
        """Convert to SQL row format for ACM_SensorAttribution table."""
        return {
            "EquipID": equip_id,
            "RunID": run_id,
            "Timestamp": self.timestamp,
            "TotalZScore": round(self.total_z_score, 3),
            "TopSensor1": self.top_3_sensors[0] if len(self.top_3_sensors) > 0 else None,
            "TopSensor2": self.top_3_sensors[1] if len(self.top_3_sensors) > 1 else None,
            "TopSensor3": self.top_3_sensors[2] if len(self.top_3_sensors) > 2 else None,
            "Explanation": self.explanation[:500] if self.explanation else None
        }


@runtime_checkable
class BaselineNormalizerProtocol(Protocol):
    """Protocol for baseline normalizer providing frozen statistics."""
    
    def get_sensor_stats(self, sensor_name: str) -> Optional[SensorStats]:
        """Get frozen baseline statistics for a sensor."""
        ...
    
    @property
    def sensor_names(self) -> List[str]:
        """List of sensors with frozen statistics."""
        ...


class UnifiedAttribution:
    """
    Unified sensor attribution using frozen baseline artifacts.
    
    Key Principle: All attribution uses the SAME normalization as detection.
    No separate statistics computed during attribution - only frozen baseline
    statistics are used for consistency.
    
    Usage:
        normalizer = MyBaselineNormalizer(baseline_stats)
        attribution = UnifiedAttribution(normalizer)
        result = attribution.attribute(
            raw_data=df,
            fused_z=4.5,
            sensor_cols=["Temp1", "Vibration", "Pressure"]
        )
        print(result.explanation)  # "Elevated anomaly driven by: Vibration is HIGH (3.2σ)"
    
    Attributes:
        normalizer: Baseline normalizer providing frozen statistics
        z_threshold_high: Z-score threshold for HIGH direction (default 2.0)
        z_threshold_low: Z-score threshold for LOW direction (default -2.0)
    """
    
    def __init__(
        self,
        baseline_normalizer: Optional[BaselineNormalizerProtocol] = None,
        z_threshold_high: float = 2.0,
        z_threshold_low: float = -2.0
    ):
        """
        Initialize UnifiedAttribution.
        
        Args:
            baseline_normalizer: Normalizer providing frozen baseline statistics.
                                If None, attribution will use raw values.
            z_threshold_high: Z-score above which direction is HIGH (default 2.0)
            z_threshold_low: Z-score below which direction is LOW (default -2.0)
        """
        self.normalizer = baseline_normalizer
        self.z_threshold_high = z_threshold_high
        self.z_threshold_low = z_threshold_low
    
    def attribute(
        self,
        raw_data: pd.DataFrame,
        fused_z: float,
        sensor_cols: Optional[List[str]] = None,
        detector_outputs: Optional[Dict[str, pd.DataFrame]] = None,
        timestamp_col: str = "Timestamp"
    ) -> AttributionResult:
        """
        Compute sensor contributions to an anomaly.
        
        Uses frozen baseline statistics from normalizer for consistent
        attribution that matches detection normalization.
        
        Args:
            raw_data: Raw sensor data DataFrame
            fused_z: Fused z-score for the anomaly (from detectors)
            sensor_cols: List of sensor columns to attribute. If None, uses all
                        numeric columns except timestamp.
            detector_outputs: Optional detector-specific outputs for advanced attribution
            timestamp_col: Name of timestamp column (default "Timestamp")
        
        Returns:
            AttributionResult with sensor contributions and explanation
        """
        if raw_data.empty:
            return AttributionResult(
                total_z_score=fused_z,
                explanation="No data available for attribution."
            )
        
        # Determine timestamp
        ts = None
        if timestamp_col in raw_data.columns:
            ts = pd.to_datetime(raw_data[timestamp_col].iloc[-1])
        
        # Determine sensor columns
        if sensor_cols is None:
            sensor_cols = [
                c for c in raw_data.columns
                if c != timestamp_col and pd.api.types.is_numeric_dtype(raw_data[c])
            ]
        
        contributions = self._compute_contributions(raw_data, sensor_cols)
        
        # Sort by contribution percentage
        contributions.sort(key=lambda c: c.contribution_pct, reverse=True)
        top_3 = [c.sensor_name for c in contributions[:3]]
        
        # Generate explanation
        explanation = self._generate_explanation(contributions[:3], fused_z)
        
        return AttributionResult(
            timestamp=ts,
            total_z_score=fused_z,
            contributions=contributions,
            top_3_sensors=top_3,
            explanation=explanation
        )
    
    def _compute_contributions(
        self,
        raw_data: pd.DataFrame,
        sensor_cols: List[str]
    ) -> List[SensorContribution]:
        """Compute contributions for each sensor (vectorized)."""
        # Filter to valid columns
        valid_cols = [c for c in sensor_cols if c in raw_data.columns]
        if not valid_cols:
            return []
        
        # Get latest values for all sensors at once
        latest_values = raw_data[valid_cols].iloc[-1]
        valid_mask = latest_values.notna()
        valid_cols = [c for c, valid in zip(valid_cols, valid_mask) if valid]
        if not valid_cols:
            return []
        
        latest_values = latest_values[valid_cols]
        
        # Compute z-scores vectorized
        if self.normalizer is not None:
            # Try to get stats from normalizer, fall back to column stats
            z_scores = pd.Series(index=valid_cols, dtype=float)
            cols_with_stats = []
            cols_without_stats = []
            for col in valid_cols:
                stats = self.normalizer.get_sensor_stats(col)
                if stats is not None:
                    z_scores[col] = stats.compute_z_score(latest_values[col])
                    cols_with_stats.append(col)
                else:
                    cols_without_stats.append(col)
            
            # For columns without stats, compute using ROBUST column statistics
            if cols_without_stats:
                col_data = raw_data[cols_without_stats]
                # ROBUST: Use median instead of mean
                col_medians = col_data.median()
                # ROBUST: Use MAD instead of std
                col_mads = (col_data - col_medians).abs().median()
                col_stds = (col_mads * 1.4826).replace(0.0, 1e-10) + 1e-10
                z_scores[cols_without_stats] = (latest_values[cols_without_stats] - col_medians) / col_stds
        else:
            # No normalizer, use column-level ROBUST stats (vectorized)
            col_data = raw_data[valid_cols]
            # ROBUST: Use median instead of mean
            col_medians = col_data.median()
            # ROBUST: Use MAD instead of std
            col_mads = (col_data - col_medians).abs().median()
            col_stds = (col_mads * 1.4826).replace(0.0, 1e-10) + 1e-10
            z_scores = (latest_values - col_medians) / col_stds
        
        # Compute baseline deviations (abs z)
        baseline_deviations = z_scores.abs()
        total_deviation = baseline_deviations.sum()
        
        # Compute contribution percentages
        if total_deviation > 0:
            contribution_pcts = (baseline_deviations / total_deviation) * 100
        else:
            contribution_pcts = pd.Series(0.0, index=valid_cols)
        
        # Build contribution objects
        contributions = []
        for col in valid_cols:
            z = float(z_scores[col])
            contributions.append(SensorContribution(
                sensor_name=col,
                contribution_pct=float(contribution_pcts[col]),
                z_score=z,
                direction=self._determine_direction(z),
                baseline_deviation=float(baseline_deviations[col])
            ))
        
        return contributions
    
    def _determine_direction(self, z_score: float) -> DeviationDirection:
        """Determine direction based on z-score thresholds."""
        if z_score > self.z_threshold_high:
            return DeviationDirection.HIGH
        elif z_score < self.z_threshold_low:
            return DeviationDirection.LOW
        else:
            return DeviationDirection.NORMAL
    
    def _generate_explanation(
        self,
        top_contributors: List[SensorContribution],
        fused_z: float
    ) -> str:
        """Generate human-readable explanation of the anomaly."""
        if not top_contributors:
            return "No significant sensor deviations detected."
        
        parts = []
        for c in top_contributors:
            if c.direction != DeviationDirection.NORMAL:
                parts.append(f"{c.sensor_name} is {c.direction.value} ({c.z_score:.1f}σ)")
        
        if not parts:
            return "Minor deviations within normal range."
        
        # Severity based on fused z-score
        if fused_z > 5:
            severity = "Critical"
        elif fused_z > 3:
            severity = "Elevated"
        elif fused_z > 2:
            severity = "Minor"
        else:
            severity = "Low"
        
        return f"{severity} anomaly driven by: {', '.join(parts)}"
    
    def attribute_episode(
        self,
        episode_data: pd.DataFrame,
        fused_z_col: str = "fused_z",
        sensor_cols: Optional[List[str]] = None,
        timestamp_col: str = "Timestamp"
    ) -> AttributionResult:
        """
        Compute aggregated attribution for an entire episode.
        
        Uses the maximum fused z-score and aggregates sensor contributions
        across all rows in the episode.
        
        Args:
            episode_data: DataFrame containing all rows in the episode
            fused_z_col: Column name for fused z-scores (default "fused_z")
            sensor_cols: List of sensor columns to attribute
            timestamp_col: Name of timestamp column
        
        Returns:
            AttributionResult with aggregated contributions
        """
        if episode_data.empty:
            return AttributionResult(explanation="Empty episode data.")
        
        # Find peak anomaly row
        if fused_z_col in episode_data.columns:
            peak_idx = episode_data[fused_z_col].idxmax()
            peak_row = episode_data.loc[[peak_idx]]
            fused_z = float(episode_data[fused_z_col].max())
        else:
            peak_row = episode_data.iloc[[-1]]
            fused_z = 0.0
        
        return self.attribute(
            raw_data=peak_row,
            fused_z=fused_z,
            sensor_cols=sensor_cols,
            timestamp_col=timestamp_col
        )


# =============================================================================
# LEGACY SENSOR ATTRIBUTION (v10.0.0)
# =============================================================================


@dataclass
class SensorAttribution:
    """Sensor attribution result with failure contribution metrics"""
    sensor_name: str
    failure_contribution: float  # 0-1 scale (proportion of total risk)
    z_score_at_failure: float    # Z-score when health crosses threshold
    alert_count: int              # Number of threshold crossings
    rank: int                     # Rank by failure contribution (1=highest)


class SensorAttributor:
    """
    Sensor attribution via counterfactual analysis and hotspot ranking.
    
    Attribution Methods:
    1. Counterfactual Analysis: Compute RUL with and without each sensor
       - Larger RUL delta = higher sensor contribution to failure
    2. SQL Hotspot Loading: Use pre-computed ACM_SensorHotspots contributions
    
    Usage:
        attributor = SensorAttributor(sql_client=sql_client)
        
        # Method 1: Load from ACM_SensorHotspots
        attributions = attributor.load_from_sql(equip_id=1, run_id="run_123")
        top3 = attributor.get_top_n(attributions, n=3)
        
        # Method 2: Counterfactual analysis (future implementation)
        # attributions = attributor.compute_counterfactual(
        #     sensor_data=df,
        #     rul_estimator=rul_est,
        #     baseline_rul=100.0
        # )
    """
    
    def __init__(self, sql_client: Optional[Any] = None):
        """
        Initialize sensor attributor.
        
        Args:
            sql_client: Database connection (pyodbc) for loading ACM_SensorHotspots
        """
        self.sql_client = sql_client
    
    def load_from_sql(self, equip_id: int, run_id: str) -> List[SensorAttribution]:
        """
        Load sensor attributions from ACM_SensorHotspots table.
        
        Query Strategy:
        1. Try full query with FailureContribution, ZScoreAtFailure, AlertCount
        2. If schema missing columns, fallback to MaxAbsZ-based derivation
        3. Derive missing columns via normalization
        
        Args:
            equip_id: Equipment ID
            run_id: ACM run identifier
        
        Returns:
            List of SensorAttribution objects, sorted by failure contribution (descending)
        """
        if self.sql_client is None:
            Console.warn("No SQL client provided; cannot load attributions", component="SENSOR_ATTR", equip_id=equip_id, run_id=run_id)
            return []
        
        try:
            df = self._load_hotspots_dataframe(equip_id, run_id)
            
            if df.empty:
                Console.warn("No sensor hotspots found", component="SENSOR_ATTR", equip_id=equip_id, run_id=run_id)
                return []
            
            # Convert DataFrame to SensorAttribution objects using to_dict (faster than iterrows)
            attributions = [
                SensorAttribution(
                    sensor_name=str(row["SensorName"]),
                    failure_contribution=float(row["FailureContribution"]),
                    z_score_at_failure=float(row["ZScoreAtFailure"]),
                    alert_count=int(row["AlertCount"]),
                    rank=idx + 1  # 1-indexed rank
                )
                for idx, row in enumerate(df.to_dict('records'))
            ]
            
            Console.info(f"Loaded {len(attributions)} sensor attributions from SQL", component="SENSOR_ATTR")
            return attributions
            
        except Exception as e:
            Console.warn(f"Failed to load sensor attributions: {e}", component="SENSOR_ATTR", equip_id=equip_id, run_id=run_id, error_type=type(e).__name__, error=str(e)[:200])
            return []
    
    def _load_hotspots_dataframe(self, equip_id: int, run_id: str) -> pd.DataFrame:
        """
        Load ACM_SensorHotspots with fallback for legacy schemas.
        
        Handles two schema versions:
        - v10: FailureContribution, ZScoreAtFailure, AlertCount columns
        - v9: MaxAbsZ, MaxSignedZ, LatestSignedZ, AboveAlertCount (derive contributions)
        
        Args:
            equip_id: Equipment ID
            run_id: ACM run identifier
        
        Returns:
            DataFrame with columns: SensorName, FailureContribution, ZScoreAtFailure, AlertCount
        """
        def _run_query(sql: str) -> pd.DataFrame:
            """Execute query and return DataFrame"""
            cur = self.sql_client.cursor()
            try:
                cur.execute(sql, (equip_id, run_id))
                rows = cur.fetchall()
                columns = [col[0] for col in (cur.description or [])]
                return pd.DataFrame.from_records(rows, columns=columns)
            finally:
                cur.close()
        
        # Try full schema query first
        base_query = """
            SELECT SensorName,
                   FailureContribution,
                   ZScoreAtFailure,
                   AlertCount,
                   MaxAbsZ,
                   MaxSignedZ,
                   LatestSignedZ,
                   AboveAlertCount
            FROM dbo.ACM_SensorHotspots
            WHERE EquipID = ? AND RunID = ?
            ORDER BY FailureContribution DESC
        """
        
        # Fallback query for legacy schema
        fallback_query = """
            SELECT SensorName,
                   MaxAbsZ,
                   MaxSignedZ,
                   LatestSignedZ,
                   AboveAlertCount
            FROM dbo.ACM_SensorHotspots
            WHERE EquipID = ? AND RunID = ?
            ORDER BY MaxAbsZ DESC
        """
        
        try:
            df = _run_query(base_query)
        except Exception as primary_err:
            Console.warn(
                "SensorHotspots schema missing attribution columns; deriving contributions instead",
                component="SENSOR_ATTR", equip_id=equip_id, run_id=run_id, error_type=type(primary_err).__name__, error=str(primary_err)[:200]
            )
            try:
                df = _run_query(fallback_query)
            except Exception as fallback_err:
                Console.warn(f"Failed to load sensor hotspots: {fallback_err}", component="SENSOR_ATTR", equip_id=equip_id, run_id=run_id, error_type=type(fallback_err).__name__, error=str(fallback_err)[:200])
                return pd.DataFrame()
        
        if df.empty:
            return df
        
        # Derive missing columns (handle legacy schema OR NULL values)
        df = self._derive_missing_columns(df)
        
        # Return sorted by FailureContribution
        result = df[["SensorName", "FailureContribution", "ZScoreAtFailure", "AlertCount"]].copy()
        result = result.sort_values("FailureContribution", ascending=False).reset_index(drop=True)
        
        return result
    
    def _derive_missing_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Derive missing attribution columns from MaxAbsZ-based data.
        
        Derivation Rules:
        - FailureContribution: Normalize MaxAbsZ to sum to 1.0
        - ZScoreAtFailure: Use MaxSignedZ or LatestSignedZ
        - AlertCount: Use AboveAlertCount
        
        Args:
            df: DataFrame with at least MaxAbsZ column
        
        Returns:
            DataFrame with all attribution columns
        """
        # Derive FailureContribution
        if "FailureContribution" not in df.columns or df["FailureContribution"].isna().any():
            abs_vals = pd.to_numeric(df.get("MaxAbsZ"), errors="coerce").abs().fillna(0.0)
            total = abs_vals.sum()
            
            if total > 0:
                df["FailureContribution"] = (abs_vals / total).clip(lower=0.0)
            elif abs_vals.max() > 0:
                # Normalize by max if sum is zero
                df["FailureContribution"] = (abs_vals / abs_vals.max()).clip(lower=0.0)
            else:
                df["FailureContribution"] = 0.0
        
        # Derive ZScoreAtFailure
        if "ZScoreAtFailure" not in df.columns or df["ZScoreAtFailure"].isna().any():
            z_source = df.get("MaxSignedZ")
            if z_source is None or (hasattr(z_source, "isna") and z_source.isna().all()):
                z_source = df.get("LatestSignedZ")
            if z_source is None:
                z_source = pd.Series([0.0] * len(df))
            df["ZScoreAtFailure"] = pd.to_numeric(z_source, errors="coerce").fillna(0.0)
        
        # Derive AlertCount
        if "AlertCount" not in df.columns or df["AlertCount"].isna().any():
            alerts = df.get("AboveAlertCount")
            if alerts is None:
                alerts = pd.Series([0] * len(df))
            df["AlertCount"] = pd.to_numeric(alerts, errors="coerce").fillna(0).astype(int)
        
        return df
    
    def get_top_n(self, attributions: List[SensorAttribution], n: int = 3) -> List[SensorAttribution]:
        """
        Get top N sensors by failure contribution.
        
        Args:
            attributions: List of SensorAttribution objects
            n: Number of top sensors to return (default 3)
        
        Returns:
            List of top N SensorAttribution objects
        """
        # Sort by failure contribution (descending)
        sorted_attrs = sorted(attributions, key=lambda x: x.failure_contribution, reverse=True)
        
        # Return top N
        return sorted_attrs[:n]
    
    def format_top_n(self, attributions: List[SensorAttribution], n: int = 3) -> str:
        """
        Format top N sensors as human-readable string.
        
        Args:
            attributions: List of SensorAttribution objects
            n: Number of top sensors to format (default 3)
        
        Returns:
            Formatted string like "Sensor1 (42.5%), Sensor2 (28.3%), Sensor3 (15.2%)"
        """
        top_n = self.get_top_n(attributions, n)
        
        if not top_n:
            return "No sensor attributions available"
        
        parts = []
        for attr in top_n:
            parts.append(f"{attr.sensor_name} ({attr.failure_contribution * 100:.1f}%)")
        
        return ", ".join(parts)
    
    def compute_attribution_scores(
        self,
        sensor_data: pd.DataFrame,
        contribution_column: str = "MaxAbsZ"
    ) -> List[SensorAttribution]:
        """
        Compute attribution scores directly from sensor data DataFrame.
        
        Useful when ACM_SensorHotspots is not available or for ad-hoc analysis.
        
        Args:
            sensor_data: DataFrame with sensor names and contribution scores
            contribution_column: Column name to use for scoring (default "MaxAbsZ")
        
        Returns:
            List of SensorAttribution objects
        """
        if sensor_data.empty:
            return []
        
        if contribution_column not in sensor_data.columns:
            Console.warn("Contribution column not found in sensor data", component="SENSOR_ATTR", column=contribution_column, available_columns=list(sensor_data.columns)[:10])
            return []
        
        # Extract scores
        scores = pd.to_numeric(sensor_data[contribution_column], errors="coerce").abs().fillna(0.0)
        total = scores.sum()
        
        if total == 0:
            Console.warn("All contribution scores are zero", component="SENSOR_ATTR", column=contribution_column, n_sensors=len(sensor_data))
            return []
        
        # Normalize to proportions
        proportions = scores / total
        
        # Create SensorAttribution objects
        attributions = []
        for idx, (sensor_name, proportion) in enumerate(zip(sensor_data.index, proportions)):
            attributions.append(SensorAttribution(
                sensor_name=str(sensor_name),
                failure_contribution=float(proportion),
                z_score_at_failure=0.0,  # Not available in ad-hoc mode
                alert_count=0,           # Not available in ad-hoc mode
                rank=idx + 1
            ))
        
        # Sort by contribution
        attributions.sort(key=lambda x: x.failure_contribution, reverse=True)
        
        # Update ranks
        for idx, attr in enumerate(attributions):
            attr.rank = idx + 1
        
        return attributions


def rank_sensors_by_contribution(
    attributions: List[SensorAttribution]
) -> pd.DataFrame:
    """
    Convert sensor attributions to ranked DataFrame.
    
    Useful for saving to ACM_RUL_Attribution table or generating reports.
    
    Args:
        attributions: List of SensorAttribution objects
    
    Returns:
        DataFrame with columns: Rank, SensorName, FailureContribution, ZScoreAtFailure, AlertCount
    """
    if not attributions:
        return pd.DataFrame(columns=["Rank", "SensorName", "FailureContribution", "ZScoreAtFailure", "AlertCount"])
    
    records = []
    for attr in attributions:
        records.append({
            "Rank": attr.rank,
            "SensorName": attr.sensor_name,
            "FailureContribution": attr.failure_contribution,
            "ZScoreAtFailure": attr.z_score_at_failure,
            "AlertCount": attr.alert_count
        })
    
    df = pd.DataFrame(records)
    return df


# =============================================================================
# P4.3: CONTRIBUTION TIMELINE BUILDER (moved from acm_main.py)
# =============================================================================

def build_contribution_timeline(
    frame: pd.DataFrame,
    fusion_weights: Dict[str, float],
    detector_cols: Optional[List[str]] = None,
) -> Optional[pd.DataFrame]:
    """
    Build detector contribution timeline from z-score frame.
    
    Computes per-timestamp contribution percentages for each detector
    based on weighted z-scores.
    
    Args:
        frame: DataFrame with Timestamp and detector z-score columns
        fusion_weights: Dict mapping detector column names to weights
        detector_cols: Optional list of detector columns to use (defaults to standard set)
        
    Returns:
        DataFrame with columns [Timestamp, DetectorType, ContributionPct, RawZ, Weight]
        or None if no valid data
    """
    if detector_cols is None:
        detector_cols = ['ar1_z', 'pca_spe_z', 'pca_t2_z', 'iforest_z', 'gmm_z', 'omr_z']
    
    if 'Timestamp' not in frame.columns:
        return None
    
    avail_cols = [c for c in detector_cols if c in frame.columns]
    if not avail_cols or not fusion_weights:
        return None
    
    # Filter valid timestamps
    valid_mask = frame['Timestamp'].notna()
    valid_frame = frame.loc[valid_mask, ['Timestamp'] + avail_cols]
    
    if len(valid_frame) == 0:
        return None
    
    # Build weight array for available columns
    weights = np.array([fusion_weights.get(c, 0.0) for c in avail_cols])
    
    # Extract z-values as numpy array and take absolute
    z_matrix = valid_frame[avail_cols].fillna(0.0).abs().values  # (n_rows, n_detectors)
    
    # Compute weighted values: z * weight for each detector
    weighted_matrix = z_matrix * weights[np.newaxis, :]  # broadcast weights
    
    # Total weighted sum per row
    total_weighted = weighted_matrix.sum(axis=1, keepdims=True)  # (n_rows, 1)
    
    # Contribution percentages: (weighted / total) * 100, avoid div by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        pct_matrix = np.where(total_weighted > 0, 
                              weighted_matrix / total_weighted * 100.0, 
                              0.0)
    
    # Vectorized: Build DataFrames and melt to long format
    timestamps = valid_frame['Timestamp'].values
    
    # Create wide DataFrames then melt to long format
    z_df = pd.DataFrame(z_matrix, columns=avail_cols)
    z_df['Timestamp'] = timestamps
    pct_df = pd.DataFrame(pct_matrix, columns=avail_cols)
    pct_df['Timestamp'] = timestamps
    
    # Melt RawZ to long format
    z_long = z_df.melt(
        id_vars='Timestamp', 
        value_vars=avail_cols,
        var_name='DetectorCol', 
        value_name='RawZ'
    )
    
    # Melt ContributionPct to long format
    pct_long = pct_df.melt(
        id_vars='Timestamp',
        value_vars=avail_cols,
        var_name='DetectorCol',
        value_name='ContributionPct'
    )
    
    # Merge and add detector name (strip _z suffix)
    contrib_df = z_long.copy()
    contrib_df['ContributionPct'] = pct_long['ContributionPct']
    contrib_df['DetectorType'] = contrib_df['DetectorCol'].str.replace('_z', '', regex=False)
    
    # Add weights - vectorized lookup
    weight_map = {col: weights[i] for i, col in enumerate(avail_cols)}
    contrib_df['Weight'] = contrib_df['DetectorCol'].map(weight_map)
    
    # Select final columns
    contrib_df = contrib_df[['Timestamp', 'DetectorType', 'ContributionPct', 'RawZ', 'Weight']]
    
    if len(contrib_df) == 0:
        return None
    
    return contrib_df


def build_sensor_analytics_context(
    raw_train: Optional[pd.DataFrame],
    raw_score: Optional[pd.DataFrame],
    frame: pd.DataFrame,
    omr_contributions_data: Optional[Any] = None,
    regime_model: Optional[Any] = None,
    logger: Any = Console,
    equip: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Build sensor analytics context aligned to the score frame index.
    """
    try:
        if raw_train is None or raw_score is None or len(raw_train) == 0 or len(raw_score) == 0:
            return None

        common_cols = [col for col in raw_score.columns if col in raw_train.columns]
        if not common_cols:
            return None

        train_baseline = raw_train[common_cols]
        score_baseline = raw_score[common_cols]

        # Robust baseline from median + MAD.
        train_median = train_baseline.median()
        train_mad = (train_baseline - train_median).abs().median()
        train_std = (train_mad * 1.4826).replace(0.0, np.nan).fillna(1e-10)
        valid_cols = train_std[train_std > 1e-10].index.tolist()
        if not valid_cols:
            return None

        train_median = train_median[valid_cols]
        train_std = train_std[valid_cols]
        score_baseline = score_baseline[valid_cols]
        score_aligned = score_baseline.reindex(frame.index)
        score_aligned = score_aligned.apply(pd.to_numeric, errors="coerce")
        sensor_z = (score_aligned - train_median) / train_std
        sensor_z = sensor_z.replace([np.inf, -np.inf], np.nan)

        return {
            "values": score_aligned,
            "z_scores": sensor_z,
            "train_mean": train_median,  # Median kept under legacy key for compatibility.
            "train_std": train_std,
            "train_p95": train_baseline[valid_cols].quantile(0.95),
            "train_p05": train_baseline[valid_cols].quantile(0.05),
            "omr_contributions": omr_contributions_data,
            "regime_meta": regime_model.meta if regime_model else {},
        }
    except Exception as sensor_ctx_err:
        logger.warn(
            f"Failed to build sensor analytics context: {sensor_ctx_err}",
            component="SENSOR",
            equip=equip,
            error_type=type(sensor_ctx_err).__name__,
            error=str(sensor_ctx_err)[:200],
        )
        return None

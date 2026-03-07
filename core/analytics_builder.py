"""
Analytics Builder for ACM
===========================

Generates analytics tables from scored data:
- ACM_HealthTimeline: Health % over time
- ACM_RegimeTimeline: Operating regime assignments  
- ACM_SensorDefects: Sensor-level anomaly flags
- ACM_SensorHotspots: Top anomalous sensors

Extracted from output_manager.py as part of Phase 3 debloating.

Usage:
    from core.analytics_builder import AnalyticsBuilder
    
    builder = AnalyticsBuilder(output_manager)
    result = builder.generate_all(scores_df, cfg, sensor_context)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

import numpy as np
import pandas as pd

from core.observability import Console
from utils.timestamp_utils import normalize_timestamp_scalar, normalize_timestamp_series
from utils.detector_labels import get_detector_label

if TYPE_CHECKING:
    from core.output_manager import OutputManager

# V11: Confidence model for health and episode confidence
try:
    from core.confidence import compute_health_confidence, compute_episode_confidence
    _CONFIDENCE_AVAILABLE = True
except ImportError:
    _CONFIDENCE_AVAILABLE = False
    compute_health_confidence = None
    compute_episode_confidence = None


# ============================================================================
# CONSTANTS
# ============================================================================
class AnalyticsConstants:
    """Constants for analytics generation."""
    DRIFT_EVENT_THRESHOLD = 3.0
    DEFAULT_CLIP_Z = 30.0
    TARGET_SAMPLING_POINTS = 500
    HEALTH_ALERT_THRESHOLD = 70.0
    HEALTH_CAUTION_THRESHOLD = 85.0
    HEALTH_WATCH_THRESHOLD = HEALTH_CAUTION_THRESHOLD  # backward compat

    @staticmethod
    def anomaly_level(abs_z: float, warn: float, alert: float) -> str:
        try:
            if abs_z >= float(alert):
                return "ALERT"
            if abs_z >= float(warn):
                return "CAUTION"
        except Exception:
            pass
        return "GOOD"


# ============================================================================
# HEALTH INDEX FUNCTION
# ============================================================================
def health_index(fused_z, z_threshold: float = 5.0, steepness: float = 1.5):
    """
    Calculate health index from fused z-score using a softer sigmoid mapping.
    
    v10.1.0: Replaced overly aggressive 100/(1+Z^2) formula.
    
    Args:
        fused_z: Fused z-score (scalar, array, or Series)
        z_threshold: Z-score at which health should be very low (default 5.0)
        steepness: Controls sigmoid slope (default 1.5, higher=sharper transition)
    
    Returns:
        Health index 0-100 (same type as input)
    """
    abs_z = np.abs(fused_z)
    normalized = (abs_z - z_threshold / 2) / (z_threshold / 4)
    sigmoid = 1 / (1 + np.exp(-normalized * steepness))
    health = 100.0 * (1 - sigmoid)
    return np.clip(health, 0.0, 100.0)


# ============================================================================
# ANALYTICS BUILDER CLASS
# ============================================================================
class AnalyticsBuilder:
    """
    Generates analytics tables from scored data.
    
    This class encapsulates analytics generation logic previously embedded in OutputManager.
    It delegates actual SQL writes to the OutputManager but owns the data generation logic.
    """
    
    def __init__(self, output_manager: "OutputManager"):
        """
        Initialize the AnalyticsBuilder.
        
        Args:
            output_manager: OutputManager instance for SQL writes
        """
        self.output_manager = output_manager
    
    @property
    def equip_id(self) -> Optional[int]:
        return self.output_manager.equip_id
    
    @property
    def run_id(self) -> Optional[str]:
        return self.output_manager.run_id
    
    @property
    def sql_client(self) -> Any:
        return self.output_manager.sql_client
    
    def generate_all(
        self,
        scores_df: pd.DataFrame,
        cfg: Dict[str, Any],
        sensor_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """
        Generate essential analytics tables for this run.

        Writes:
          - ACM_HealthTimeline: Health % over time (required for RUL forecasting)
          - ACM_RegimeTimeline: Operating regime assignments
          - ACM_SensorDefects: Sensor-level anomaly flags
          - ACM_SensorHotspots: Top anomalous sensors (RUL attribution)
          - ACM_DataQuality: Data quality per sensor

        Returns:
            Dict with 'sql_tables' count
        """
        Console.info(
            "Building analytics tables: HealthTimeline, RegimeTimeline, "
            "SensorDefects, SensorHotspots, DataQuality...",
            component="ANALYTICS",
        )

        sql_count = 0

        if (self.sql_client is None) or (not self.run_id):
            Console.warn(
                "Analytics table generation skipped (SQL not ready).",
                component="ANALYTICS",
                equip_id=self.equip_id,
                run_id=self.run_id,
            )
            return {"sql_tables": 0}

        has_fused = "fused" in scores_df.columns
        has_regimes = "regime_label" in scores_df.columns

        # Extract sensor context
        sensor_values = None
        sensor_zscores = None
        sensor_train_mean = None
        sensor_train_std = None
        data_quality_df = None
        omr_contributions = None

        if sensor_context:
            v = sensor_context.get("values")
            z = sensor_context.get("z_scores")
            omr_contributions = sensor_context.get("omr_contributions")

            if isinstance(v, pd.DataFrame) and len(v.columns):
                sensor_values = v.reindex(scores_df.index)

            if isinstance(z, pd.DataFrame) and len(z.columns):
                sensor_zscores = z.reindex(scores_df.index)

            m = sensor_context.get("train_mean")
            s = sensor_context.get("train_std")

            if isinstance(m, pd.Series):
                sensor_train_mean = m
            if isinstance(s, pd.Series):
                sensor_train_std = s

            dq = sensor_context.get("data_quality_df")
            if isinstance(dq, pd.DataFrame) and len(dq.columns):
                data_quality_df = dq.copy()

        # Timeline tables need timestamp-range deletion
        timeline_tables = ["ACM_HealthTimeline", "ACM_RegimeTimeline"]
        non_timeline_tables = ["ACM_SensorDefects", "ACM_SensorHotspots", "ACM_DataQuality"]

        # Get timestamp range for deduplication
        min_ts = None
        max_ts = None
        if isinstance(scores_df.index, pd.DatetimeIndex):
            min_ts = scores_df.index.min()
            max_ts = scores_df.index.max()
        elif 'Timestamp' in scores_df.columns:
            min_ts = pd.to_datetime(scores_df['Timestamp']).min()
            max_ts = pd.to_datetime(scores_df['Timestamp']).max()

        with self.output_manager.batched_transaction():
            try:
                # Delete timeline tables by TIMESTAMP RANGE
                if pd.notna(min_ts) and pd.notna(max_ts):
                    self.output_manager._delete_timeline_overlaps(timeline_tables, min_ts, max_ts)
                
                # Delete non-timeline tables by RunID
                self.output_manager._bulk_delete_analytics_tables(non_timeline_tables)

                # 1) ACM_HealthTimeline
                if has_fused:
                    health_df = self.generate_health_timeline(scores_df, cfg)
                    result = self.output_manager.write_sql_table(
                        table_name="ACM_HealthTimeline",
                        df=health_df,
                        artifact_name="health_timeline",
                    )
                    if result.get("sql_written"):
                        sql_count += 1

                # 2) ACM_RegimeTimeline
                if has_regimes:
                    regime_df = self.generate_regime_timeline(scores_df)
                    result = self.output_manager.write_sql_table(
                        table_name="ACM_RegimeTimeline",
                        df=regime_df,
                        artifact_name="regime_timeline",
                    )
                    if result.get("sql_written"):
                        sql_count += 1

                # 3) ACM_SensorDefects
                if has_fused:
                    sensor_defects_df = self.generate_sensor_defects(scores_df)
                    result = self.output_manager.write_sql_table(
                        table_name="ACM_SensorDefects",
                        df=sensor_defects_df,
                        artifact_name="sensor_defects",
                    )
                    if result.get("sql_written"):
                        sql_count += 1

                # 4) ACM_SensorHotspots
                sensor_ready = (sensor_zscores is not None) and (sensor_values is not None)
                if sensor_ready:
                    warn_threshold = float(
                        ((cfg.get("regimes", {}) or {}).get("health", {}) or {}).get("fused_warn_z", 1.5) or 1.5
                    )
                    alert_threshold = float(
                        ((cfg.get("regimes", {}) or {}).get("health", {}) or {}).get("fused_alert_z", 3.0) or 3.0
                    )
                    top_n = int((cfg.get("output", {}) or {}).get("sensor_hotspot_top_n", 25))

                    sensor_hotspots_df = self.generate_sensor_hotspots(
                        sensor_zscores=sensor_zscores,
                        sensor_values=sensor_values,
                        train_mean=sensor_train_mean,
                        train_std=sensor_train_std,
                        warn_z=warn_threshold,
                        alert_z=alert_threshold,
                        top_n=top_n,
                        omr_contributions=omr_contributions
                    )

                    result = self.output_manager.write_sql_table(
                        table_name="ACM_SensorHotspots",
                        df=sensor_hotspots_df,
                        artifact_name="sensor_hotspots",
                        non_numeric_cols={"SensorName"},
                    )
                    if result.get("sql_written"):
                        sql_count += 1

                # 5) ACM_DataQuality
                if isinstance(data_quality_df, pd.DataFrame) and len(data_quality_df.columns):
                    dq_df = self._prepare_data_quality(data_quality_df)
                    result = self.output_manager.write_sql_table(
                        table_name="ACM_DataQuality",
                        df=dq_df,
                        artifact_name="data_quality",
                    )
                    if result.get("sql_written"):
                        sql_count += 1

                Console.info(
                    f"Generated analytics tables (SQL written: {sql_count})",
                    component="ANALYTICS",
                    equip_id=self.equip_id,
                    run_id=self.run_id,
                )
                return {"sql_tables": sql_count}

            except Exception as e:
                Console.warn(
                    f"Analytics table generation failed: {e}",
                    component="ANALYTICS",
                    equip_id=self.equip_id,
                    run_id=self.run_id,
                    error_type=type(e).__name__,
                    error=str(e)[:200],
                )
                import traceback
                Console.warn(f"Traceback: {traceback.format_exc()}", component="ANALYTICS")
                return {"sql_tables": sql_count}
    
    def generate_health_timeline(self, scores_df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
        """
        Generate enhanced health timeline with smoothing, quality flags, and V11 confidence.

        Args:
            scores_df: DataFrame with fused Z-scores and timestamp index
            cfg: Configuration dictionary with health smoothing parameters

        GRADUAL-DEGRADE-FIX (v11.14.1):
        The previous approach applied EMA smoothing AFTER the sigmoid
        (sigmoid → smooth), which means weak persistent z-score elevations
        were already compressed to near-100% health before smoothing could
        accumulate them. A machine slowly drifting at z≈0.8 every batch
        would show health ≈ 99.9% indefinitely.

        The corrected approach pre-smooths fused_z BEFORE the sigmoid
        (smooth → sigmoid). Persistent small deviations accumulate in the
        EWM signal, then the nonlinearity amplifies them into visible health
        decline only once they are sustained. Step-change spikes still spike
        the instantaneous score and are preserved in RawHealthIndex.
        """
        # Load config parameters
        health_cfg = cfg.get('health', {})
        smoothing_alpha = health_cfg.get('smoothing_alpha', 0.3)
        # gradient_smoothing_alpha: EMA applied to fused_z BEFORE the sigmoid.
        # Lower alpha → longer memory → more sensitive to slow sustained drift.
        # Default 0.1 ≈ half-life of ~6.5 samples (≈ 3 h at 30-min cadence).
        gradient_alpha = float(health_cfg.get('gradient_smoothing_alpha', 0.1))
        extreme_volatility_threshold = health_cfg.get('extreme_volatility_threshold', 30.0)
        extreme_anomaly_z_threshold = health_cfg.get('extreme_anomaly_z_threshold', 10.0)

        # Instantaneous health: sigmoid of raw fused_z — preserved as RawHealthIndex.
        # Captures acute spikes. Does NOT accumulate gradual drift.
        raw_health = health_index(scores_df['fused'])

        # Gradient health: EMA of abs(fused_z) → then sigmoid.
        # Persistent weak elevations accumulate in the EWM before the nonlinearity,
        # so gradual degradation becomes visible as a steady health decline rather
        # than being compressed to ~100% and then smoothed out.
        # NOTE: abs() is taken BEFORE the EWM so that bilateral oscillations
        # around zero (normal baseline noise) do NOT cancel each other out.
        # Applying EWM to the signed value would make z=+1 / z=-1 alternation
        # average to EWM≈0 → health≈97%, masking real weak degradation.
        fused_gradient = scores_df['fused'].abs().ewm(alpha=gradient_alpha, adjust=False).mean()
        gradient_health = health_index(fused_gradient)

        # Post-smooth gradient health for visual noise reduction (display only).
        smoothed_health = gradient_health.ewm(alpha=smoothing_alpha, adjust=False).mean()
        
        # Calculate rate of change for quality flagging
        health_change = smoothed_health.diff().abs()
        
        # Initialize quality flags
        quality_flag = pd.Series(['NORMAL'] * len(scores_df), index=scores_df.index)
        
        # Flag extreme volatility
        volatile_mask = health_change > extreme_volatility_threshold
        quality_flag[volatile_mask] = 'EXTREME_VOLATILITY'
        
        # Flag extreme anomalies
        extreme_mask = scores_df['fused'].abs() > extreme_anomaly_z_threshold
        quality_flag[extreme_mask] = 'EXTREME_ANOMALY'
        
        quality_flag.iloc[0] = 'NORMAL'
        
        # Log quality issues
        volatile_count = (quality_flag == 'EXTREME_VOLATILITY').sum()
        extreme_count = (quality_flag == 'EXTREME_ANOMALY').sum()
        if volatile_count > 0:
            Console.warn(
                f"{volatile_count} volatile health transitions detected",
                component="HEALTH", equip_id=self.equip_id, volatile_count=volatile_count
            )
        if extreme_count > 0:
            Console.warn(
                f"{extreme_count} extreme anomaly scores detected",
                component="HEALTH", equip_id=self.equip_id, extreme_count=extreme_count
            )
        
        # Calculate health zones.
        # include_lowest=True: closes the left edge of the first bin so that
        # health=0.0 maps to 'ALERT' rather than producing NaN (pd.cut default
        # is left-exclusive, so bins=[0,70,85,100] would exclude 0 exactly).
        zones = pd.cut(
            smoothed_health,
            bins=[0, AnalyticsConstants.HEALTH_ALERT_THRESHOLD,
                  AnalyticsConstants.HEALTH_WATCH_THRESHOLD, 100],
            labels=['ALERT', 'WATCH', 'GOOD'],
            include_lowest=True,
        )
        
        # V11: Compute confidence vectorized
        confidence_values = self._compute_health_confidence_vectorized(scores_df)
        
        ts_series = normalize_timestamp_series(scores_df.index)
        result_df = pd.DataFrame({
            'Timestamp': ts_series.values,
            'HealthIndex': smoothed_health.round(2).values,
            'RawHealthIndex': raw_health.round(2).values,
            'QualityFlag': quality_flag.astype(str).values,
            'HealthZone': zones.astype(str).values,
            'FusedZ': scores_df['fused'].round(4).values,
        })
        
        if confidence_values is not None:
            result_df['Confidence'] = confidence_values
        else:
            result_df['Confidence'] = np.nan
            
        return result_df
    
    def _compute_health_confidence_vectorized(self, scores_df: pd.DataFrame) -> Optional[List[float]]:
        """Compute health confidence values in a vectorized manner."""
        if not _CONFIDENCE_AVAILABLE or compute_health_confidence is None:
            return None
            
        try:
            maturity_state = getattr(self.output_manager, 'maturity_state', 'COLDSTART')
            n_rows = len(scores_df)
            fused_z_array = scores_df['fused'].values
            sample_counts = np.arange(1, n_rows + 1)
            
            # Base confidence from maturity state
            maturity_base = {
                'COLDSTART': 0.3, 'LEARNING': 0.6, 
                'CONVERGED': 0.85, 'DEPRECATED': 0.7
            }.get(maturity_state, 0.5)
            
            fused_z_abs = np.abs(fused_z_array)
            signal_conf = np.minimum(fused_z_abs / 6.0, 1.0) * 0.3
            sample_conf = np.minimum(sample_counts / 1000.0, 1.0) * 0.2
            raw_conf = maturity_base * 0.5 + signal_conf + sample_conf
            
            return np.round(np.clip(raw_conf, 0.1, 0.95), 3).tolist()
        except Exception as e:
            Console.warn(f"Failed to compute health confidence: {e}", component="HEALTH")
            return None
    
    def generate_regime_timeline(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate regime timeline with confidence and novelty flag.
        
        v11.3.1: Added IsNovel column for points that are in sparse/novel regions.
        These points have valid regime assignments but lower confidence.
        """
        regimes = pd.to_numeric(scores_df['regime_label'], errors='coerce').astype('Int64')
        ts_series = normalize_timestamp_series(scores_df.index)
        
        result = pd.DataFrame({
            'Timestamp': ts_series.values,
            'RegimeLabel': regimes.values,
            'RegimeState': (scores_df['regime_state'].astype(str).values 
                          if 'regime_state' in scores_df.columns else 'unknown')
        })
        
        if 'regime_confidence' in scores_df.columns:
            result['AssignmentConfidence'] = scores_df['regime_confidence'].round(3).values
        
        # v11.3.1: Add novelty flag - indicates point is in sparse/novel region
        if 'regime_is_novel' in scores_df.columns:
            result['IsNovel'] = scores_df['regime_is_novel'].astype(bool).values
        else:
            # Backward compatibility: default to False
            result['IsNovel'] = False
        
        if 'regime_version' in scores_df.columns:
            result['RegimeVersion'] = scores_df['regime_version'].values
            
        return result
    
    def generate_sensor_defects(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """Generate per-sensor defect analysis."""
        detector_cols = [c for c in scores_df.columns if c.endswith('_z') and c != 'fused_z']
        defect_data = []
        
        for detector in detector_cols:
            if detector is None or (isinstance(detector, float) and pd.isna(detector)):
                continue
            detector_col = str(detector)
            detector_label = get_detector_label(detector_col, sql_safe=True)
            
            family_parts = detector_label.split(' ')[0] if ' ' in detector_label else detector_label.split('(')[0]
            family = family_parts.strip()

            if detector not in scores_df.columns:
                continue
                
            values = pd.to_numeric(scores_df[detector], errors='coerce').abs()
            violations = values > 2.0
            violation_count = int(violations.sum())
            total_points = int(len(values)) if len(values) else 0
            violation_pct = (violation_count / total_points * 100) if total_points > 0 else 0.0
            
            if violation_pct > 20:
                severity = "CRITICAL"
            elif violation_pct > 10:
                severity = "HIGH"
            elif violation_pct > 5:
                severity = "MEDIUM"
            else:
                severity = "LOW"
            
            defect_data.append({
                'DetectorType': detector_label,
                'DetectorFamily': family,
                'Severity': severity,
                'ViolationCount': violation_count,
                'ViolationPct': round(violation_pct, 2),
                'MaxZ': round(float(values.max()) if len(values) else 0.0, 4),
                'AvgZ': round(float(values.mean()) if len(values) else 0.0, 4),
                'CurrentZ': round(float(values.iloc[-1]) if len(values) else 0.0, 4),
                'ActiveDefect': bool(violations.iloc[-1]) if len(violations) else False
            })
        
        return pd.DataFrame(defect_data).sort_values('ViolationPct', ascending=False)
    
    def generate_sensor_hotspots(
        self,
        sensor_zscores: pd.DataFrame,
        sensor_values: pd.DataFrame,
        train_mean: Optional[pd.Series],
        train_std: Optional[pd.Series],
        warn_z: float,
        alert_z: float,
        top_n: int,
        omr_contributions: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """Summarize top sensors by peak z-score deviation (vectorized)."""
        empty_schema = {
            'SensorName': [], 'MaxTimestamp': [], 'LatestTimestamp': [], 'MaxAbsZ': [],
            'MaxSignedZ': [], 'LatestAbsZ': [], 'LatestSignedZ': [], 'ValueAtPeak': [],
            'LatestValue': [], 'TrainMean': [], 'TrainStd': [], 'AboveWarnCount': [],
            'AboveAlertCount': [], 'MaxAbsOMR': [], 'RankingScore': []
        }

        if sensor_zscores is None or sensor_zscores.empty:
            return pd.DataFrame(empty_schema)

        valid_cols = sensor_zscores.columns[sensor_zscores.notna().any()]
        if len(valid_cols) == 0:
            return pd.DataFrame(empty_schema)
        
        zs = sensor_zscores[valid_cols]
        abs_zs = zs.abs()
        
        max_abs = abs_zs.max()
        max_idx = abs_zs.idxmax()
        
        latest_ts = pd.Series(index=valid_cols, dtype=object)
        for c in valid_cols:
            col_notna = zs[c].dropna()
            latest_ts[c] = col_notna.index[-1] if len(col_notna) > 0 else pd.NaT
        
        max_signed = pd.Series({c: zs.loc[max_idx[c], c] if pd.notna(max_idx[c]) else np.nan for c in valid_cols})
        latest_signed = zs.iloc[-1] if not zs.empty else pd.Series(index=valid_cols, dtype=float)
        latest_abs = latest_signed.abs()
        
        above_warn = (abs_zs >= warn_z).sum()
        above_alert = (abs_zs >= alert_z).sum() if alert_z > 0 else pd.Series(0, index=valid_cols)
        
        value_at_peak = pd.Series(index=valid_cols, dtype=float)
        latest_value = pd.Series(index=valid_cols, dtype=float)
        common_cols = valid_cols.intersection(sensor_values.columns)
        for c in common_cols:
            if pd.notna(max_idx[c]) and max_idx[c] in sensor_values.index:
                value_at_peak[c] = sensor_values.loc[max_idx[c], c]
            if pd.notna(latest_ts[c]) and latest_ts[c] in sensor_values.index:
                latest_value[c] = sensor_values.loc[latest_ts[c], c]
        
        train_mean_vals = pd.Series(index=valid_cols, dtype=float)
        train_std_vals = pd.Series(index=valid_cols, dtype=float)
        if isinstance(train_mean, pd.Series):
            common = valid_cols.intersection(train_mean.index)
            train_mean_vals[common] = train_mean[common]
        if isinstance(train_std, pd.Series):
            common = valid_cols.intersection(train_std.index)
            train_std_vals[common] = train_std[common]
        
        df = pd.DataFrame({
            'SensorName': valid_cols,
            'MaxTimestamp': [normalize_timestamp_scalar(max_idx[c]) for c in valid_cols],
            'LatestTimestamp': [normalize_timestamp_scalar(latest_ts[c]) for c in valid_cols],
            'MaxAbsZ': max_abs.round(4).values,
            'MaxSignedZ': max_signed.round(4).values,
            'LatestAbsZ': latest_abs.round(4).values,
            'LatestSignedZ': latest_signed.round(4).values,
            'ValueAtPeak': value_at_peak.values,
            'LatestValue': latest_value.values,
            'TrainMean': train_mean_vals.values,
            'TrainStd': train_std_vals.values,
            'AboveWarnCount': above_warn.astype(int).values,
            'AboveAlertCount': above_alert.astype(int).values
        })
        
        sort_by = 'MaxAbsZ'
        if omr_contributions is not None and not omr_contributions.empty:
            aligned_omr = omr_contributions.reindex(zs.index).reindex(columns=zs.columns)
            max_abs_omr = aligned_omr.abs().max()
            df['MaxAbsOMR'] = df['SensorName'].map(max_abs_omr).fillna(0)
            df['RankingScore'] = df[['MaxAbsZ', 'MaxAbsOMR']].max(axis=1)
            sort_by = 'RankingScore'
        else:
            df['MaxAbsOMR'] = 0.0
            df['RankingScore'] = df['MaxAbsZ']

        df = df[df[sort_by] >= warn_z]
        if df.empty:
            return pd.DataFrame(empty_schema)
        df = df.sort_values(sort_by, ascending=False)

        if top_n > 0:
            df = df.head(top_n)
        return df.reset_index(drop=True)
    
    def _prepare_data_quality(self, data_quality_df: pd.DataFrame) -> pd.DataFrame:
        """Prepare data quality DataFrame for SQL insert."""
        dq_df = data_quality_df.copy()

        if "CheckName" not in dq_df.columns:
            dq_df["CheckName"] = "NullsBySensor"

        if "CheckResult" not in dq_df.columns:
            notes_col = dq_df.get("Notes", dq_df.get("notes", pd.Series([""] * len(dq_df), index=dq_df.index)))
            notes_lower = notes_col.fillna("").astype(str).str.lower()
            
            tr_pct = pd.to_numeric(dq_df.get("TrainNullPct", dq_df.get("train_null_pct", 0)), errors='coerce').fillna(0)
            sc_pct = pd.to_numeric(dq_df.get("ScoreNullPct", dq_df.get("score_null_pct", 0)), errors='coerce').fillna(0)
            max_pct = np.maximum(tr_pct, sc_pct)
            
            has_all_nulls = notes_lower.str.contains("all_nulls_train|all_nulls_score", regex=True)
            has_low_var = notes_lower.str.contains("low_variance_train", regex=False)
            
            check_result = pd.Series("OK", index=dq_df.index)
            check_result = check_result.where(~((max_pct >= 10) | has_low_var), "CAUTION")
            check_result = check_result.where(~((max_pct >= 80) | has_all_nulls), "FAIL")
            
            dq_df["CheckResult"] = check_result

        if "RunID" not in dq_df.columns:
            dq_df["RunID"] = self.run_id
        if "EquipID" not in dq_df.columns:
            dq_df["EquipID"] = self.equip_id
        if "Sensor" in dq_df.columns and "sensor" not in dq_df.columns:
            dq_df = dq_df.rename(columns={"Sensor": "sensor"})

        col_mapping = {
            "sensor": "sensor",
            "train_count": "TrainCount",
            "train_nulls": "TrainNulls",
            "train_null_pct": "TrainNullPct",
            "train_std": "TrainStd",
            "train_longest_gap": "TrainLongestGap",
            "train_flatline_span": "TrainFlatlineSpan",
            "train_min_ts": "TrainMinTs",
            "train_max_ts": "TrainMaxTs",
            "score_count": "ScoreCount",
            "score_nulls": "ScoreNulls",
            "score_null_pct": "ScoreNullPct",
            "score_std": "ScoreStd",
            "score_longest_gap": "ScoreLongestGap",
            "score_flatline_span": "ScoreFlatlineSpan",
            "score_min_ts": "ScoreMinTs",
            "score_max_ts": "ScoreMaxTs",
            "interp_method": "InterpMethod",
            "sampling_secs": "SamplingSecs",
            "notes": "Notes",
        }
        dq_df = dq_df.rename(columns={k: v for k, v in col_mapping.items() if k in dq_df.columns})

        expected_cols = [
            "sensor", "TrainCount", "TrainNulls", "TrainNullPct", "TrainStd",
            "TrainLongestGap", "TrainFlatlineSpan", "TrainMinTs", "TrainMaxTs",
            "ScoreCount", "ScoreNulls", "ScoreNullPct", "ScoreStd",
            "ScoreLongestGap", "ScoreFlatlineSpan", "ScoreMinTs", "ScoreMaxTs",
            "InterpMethod", "SamplingSecs", "Notes",
            "RunID", "EquipID", "CheckName", "CheckResult",
        ]
        cols_to_keep = [c for c in expected_cols if c in dq_df.columns]
        return dq_df[cols_to_keep]

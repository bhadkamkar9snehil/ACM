#!/usr/bin/env python3
"""
ACM Distilled - Analytics-Only Focus

A simplified ACM pipeline that focuses PURELY on answering the fundamental 
analytical questions about equipment health:

1. What is wrong? (Multi-detector anomaly detection)
2. When did it start? (Episode detection with timestamps)
3. Which sensors? (Culprit attribution)
4. Which operating mode? (Regime identification)
5. What will happen? (RUL forecast)
6. How severe? (Health scoring)

This script:
- Takes equipment ID and date range as input
- Runs the full analytical pipeline
- Outputs a comprehensive text report
- Does NOT write everything back to SQL (minimal persistence)
- Focuses on insights, not product engineering

Usage:
    python acm_distilled.py --equip FD_FAN --start-time "2024-01-01T00:00:00" --end-time "2024-01-31T23:59:59"
"""

from __future__ import annotations

import argparse
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Core ACM modules
from core import regimes, drift, fuse, fast_features
from core.ar1_detector import AR1Detector
from core.omr import OMRDetector
from core.sql_client import SQLClient
from core.detector_orchestrator import (
    fit_all_detectors,
    score_all_detectors,
    calibrate_all_detectors,
    get_detector_enable_flags,
    compute_stable_feature_hash,
    reconcile_detector_flags_with_loaded_models,
)
from core.pipeline_types import DataContract
from core.forecast_engine import ForecastEngine
from core.output_manager import OutputManager
from utils.config_dict import ConfigDict


def compute_health_from_z(z_score: float, smoothing_alpha: float = 0.3) -> float:
    """
    Convert fused Z-score to health index (0-100).
    Higher Z-score = lower health.
    
    Uses exponential decay: health = 100 * exp(-z^2 / k)
    where k controls sensitivity (default k=8 gives 50% health at z=2.4)
    """
    k = 8.0
    health = 100.0 * np.exp(-z_score**2 / k)
    return max(0.0, min(100.0, health))


class AnalyticsReport:
    """Container for analytical findings"""
    
    def __init__(self):
        self.equipment = ""
        self.analysis_window = {"start": None, "end": None}
        self.data_summary = {}
        self.detector_scores = {}
        self.episodes = []
        self.regimes = {}
        self.health = {}
        self.drift = {}
        self.rul_forecast = {}
        self.top_culprits = []
        self.recommendations = []
    
    def to_text(self) -> str:
        """Generate human-readable report"""
        lines = []
        lines.append("=" * 80)
        lines.append(f"ACM ANALYTICS REPORT - {self.equipment}")
        lines.append("=" * 80)
        lines.append(f"Analysis Period: {self.analysis_window['start']} to {self.analysis_window['end']}")
        lines.append("")
        
        # Data Summary
        lines.append("1. DATA SUMMARY")
        lines.append("-" * 80)
        for key, val in self.data_summary.items():
            lines.append(f"  {key}: {val}")
        lines.append("")
        
        # Detector Scores
        lines.append("2. DETECTOR SCORES (Z-Scores)")
        lines.append("-" * 80)
        if self.detector_scores:
            for det, stats in self.detector_scores.items():
                lines.append(f"  {det:15s} - Mean: {stats['mean']:6.2f} | Max: {stats['max']:6.2f} | P95: {stats['p95']:6.2f}")
        lines.append("")
        
        # Episodes
        lines.append("3. ANOMALY EPISODES")
        lines.append("-" * 80)
        if self.episodes:
            lines.append(f"  Total Episodes: {len(self.episodes)}")
            for i, ep in enumerate(self.episodes[:5], 1):  # Show top 5
                lines.append(f"  Episode {i}:")
                lines.append(f"    Start: {ep.get('start_time', 'N/A')}")
                lines.append(f"    Duration: {ep.get('duration_hours', 0):.1f} hours")
                lines.append(f"    Max Z-Score: {ep.get('max_z', 0):.2f}")
                lines.append(f"    Severity: {ep.get('severity', 'UNKNOWN')}")
        else:
            lines.append("  No significant anomaly episodes detected")
        lines.append("")
        
        # Operating Regimes
        lines.append("4. OPERATING REGIMES")
        lines.append("-" * 80)
        if self.regimes:
            lines.append(f"  Total Regimes: {self.regimes.get('n_regimes', 0)}")
            lines.append(f"  Current Regime: {self.regimes.get('current_regime', 'UNKNOWN')}")
            lines.append(f"  Quality Score: {self.regimes.get('silhouette', 0):.3f}")
            if 'occupancy' in self.regimes:
                lines.append("  Time in Each Regime:")
                for regime_id, pct in self.regimes['occupancy'].items():
                    lines.append(f"    Regime {regime_id}: {pct:.1f}%")
        lines.append("")
        
        # Health Status
        lines.append("5. EQUIPMENT HEALTH")
        lines.append("-" * 80)
        if self.health:
            lines.append(f"  Current Health Index: {self.health.get('current', 0):.1f}%")
            lines.append(f"  Average Health: {self.health.get('average', 0):.1f}%")
            lines.append(f"  Trend: {self.health.get('trend', 'UNKNOWN')}")
            lines.append(f"  Status: {self.health.get('status', 'UNKNOWN')}")
        lines.append("")
        
        # Drift Detection
        lines.append("6. DRIFT ANALYSIS")
        lines.append("-" * 80)
        if self.drift:
            lines.append(f"  Drift Status: {self.drift.get('status', 'UNKNOWN')}")
            lines.append(f"  Drift Z-Score: {self.drift.get('drift_z', 0):.2f}")
            lines.append(f"  Multi-Feature Drift: {self.drift.get('multi_drift', 'STABLE')}")
        lines.append("")
        
        # RUL Forecast
        lines.append("7. REMAINING USEFUL LIFE (RUL) FORECAST")
        lines.append("-" * 80)
        if self.rul_forecast:
            lines.append(f"  RUL P10 (Pessimistic): {self.rul_forecast.get('p10', 0):.0f} hours")
            lines.append(f"  RUL P50 (Expected):    {self.rul_forecast.get('p50', 0):.0f} hours")
            lines.append(f"  RUL P90 (Optimistic):  {self.rul_forecast.get('p90', 0):.0f} hours")
            lines.append(f"  Confidence: {self.rul_forecast.get('confidence', 0):.2f}")
            lines.append(f"  Reliability: {self.rul_forecast.get('reliability', 'UNKNOWN')}")
        lines.append("")
        
        # Top Culprits
        lines.append("8. TOP CONTRIBUTING SENSORS")
        lines.append("-" * 80)
        if self.top_culprits:
            for i, sensor in enumerate(self.top_culprits[:10], 1):
                lines.append(f"  {i:2d}. {sensor['name']:30s} - Contribution: {sensor['contribution']:.3f}")
        lines.append("")
        
        # Recommendations
        lines.append("9. RECOMMENDATIONS")
        lines.append("-" * 80)
        if self.recommendations:
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"  {i}. {rec}")
        else:
            lines.append("  No specific recommendations at this time")
        lines.append("")
        
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)


def load_data(sql_client: SQLClient, equip_code: str, start_time: pd.Timestamp, end_time: pd.Timestamp) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """Load training and scoring data from SQL"""
    print(f"Loading data from {start_time} to {end_time}...")
    
    # Use 60/40 split: first 60% for training, last 40% for scoring
    total_duration = end_time - start_time
    train_end = start_time + total_duration * 0.6
    
    # Data table name is {EquipCode}_Data
    data_table = f"{equip_code}_Data"
    
    cursor = sql_client.cursor()
    
    # Load training data - use parameterized query for dates only (table name can't be parameterized)
    cursor.execute(
        f"""
        SELECT TOP 10000 * 
        FROM dbo.[{data_table}]
        WHERE EntryDateTime >= ? AND EntryDateTime < ?
        ORDER BY EntryDateTime ASC
        """,
        (start_time, train_end)
    )
    
    train_cols = [col[0] for col in cursor.description]
    train_rows = cursor.fetchall()
    train = pd.DataFrame.from_records(train_rows, columns=train_cols)
    
    # Load scoring data
    cursor.execute(
        f"""
        SELECT TOP 10000 * 
        FROM dbo.[{data_table}]
        WHERE EntryDateTime >= ? AND EntryDateTime <= ?
        ORDER BY EntryDateTime ASC
        """,
        (train_end, end_time)
    )
    
    score_cols = [col[0] for col in cursor.description]
    score_rows = cursor.fetchall()
    score = pd.DataFrame.from_records(score_rows, columns=score_cols)
    
    # Set timestamp as index
    if 'EntryDateTime' in train.columns:
        train = train.set_index('EntryDateTime')
    if 'EntryDateTime' in score.columns:
        score = score.set_index('EntryDateTime')
    
    # Drop non-numeric columns (keep only sensor values)
    train_numeric = train.select_dtypes(include=[np.number])
    score_numeric = score.select_dtypes(include=[np.number])
    
    # Common columns only
    common_cols = sorted(set(train_numeric.columns) & set(score_numeric.columns))
    train = train_numeric[common_cols]
    score = score_numeric[common_cols]
    
    meta = {
        'timestamp_col': 'EntryDateTime',
        'kept_cols': common_cols,
        'dropped_cols': [],
        'cadence_ok': True,
    }
    
    print(f"  Train: {len(train)} rows x {len(train.columns)} sensors")
    print(f"  Score: {len(score)} rows x {len(score.columns)} sensors")
    
    return train, score, meta


def run_analytics(equip: str, start_time: str, end_time: str) -> AnalyticsReport:
    """Run complete analytics pipeline and return report"""
    
    report = AnalyticsReport()
    report.equipment = equip
    
    # Parse timestamps
    start_ts = pd.Timestamp(start_time)
    end_ts = pd.Timestamp(end_time)
    report.analysis_window = {"start": start_ts, "end": end_ts}
    
    # Connect to SQL
    print("Connecting to SQL Server...")
    sql_client = SQLClient.from_ini('acm')
    sql_client.connect()
    
    # Load config
    print(f"Loading config for {equip}...")
    cursor = sql_client.cursor()
    cursor.execute("SELECT EquipID FROM Equipment WHERE EquipCode = ?", (equip,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Equipment '{equip}' not found in database")
    equip_id = row[0]
    
    # Create a new RunID by inserting into ACM_Runs
    print("Creating new ACM run...")
    cursor.execute("""
        INSERT INTO ACM_Runs (RunID, EquipID, EquipName, StartedAt, HealthStatus)
        OUTPUT INSERTED.RunID
        VALUES (NEWID(), ?, ?, GETDATE(), 'RUNNING')
    """, (equip_id, equip))
    run_row = cursor.fetchone()
    run_id = str(run_row[0]) if run_row else None
    cursor.connection.commit()
    print(f"  RunID: {run_id}")
    
    # Load configuration from SQL
    cfg_dict = ConfigDict.from_sql(sql_client, equip)
    cfg = dict(cfg_dict)
    
    # Ensure default fusion weights if not loaded
    if "fusion" not in cfg or "weights" not in cfg.get("fusion", {}):
        cfg["fusion"] = {
            "weights": {
                "ar1_z": 0.20,
                "pca_spe_z": 0.30,
                "pca_t2_z": 0.20,
                "iforest_z": 0.15,
                "gmm_z": 0.05,
                "omr_z": 0.10,
            }
        }
    
    # Load data (using equip code for table name)
    train, score, meta = load_data(sql_client, equip, start_ts, end_ts)
    
    report.data_summary = {
        "Train Rows": len(train),
        "Score Rows": len(score),
        "Sensors": len(train.columns),
        "Train Period": f"{train.index.min()} to {train.index.max()}",
        "Score Period": f"{score.index.min()} to {score.index.max()}",
    }
    
    # Data Contract Validation
    print("\nValidating data contract...")
    contract = DataContract(
        required_sensors=[],
        optional_sensors=list(meta['kept_cols']),
        timestamp_col='EntryDateTime',
        min_rows=10,
        max_null_fraction=0.5,
        equip_id=equip_id,
        equip_code=equip,
    )
    validation = contract.validate(score)
    if not validation.passed:
        raise ValueError(f"Data contract validation failed: {validation.issues}")
    
    # Store raw data for regime detection
    raw_train = train.copy()
    raw_score = score.copy()
    
    # Build features
    print("\nBuilding features...")
    window = cfg.get('feature_window', 16)
    train_features = fast_features.compute_basic_features_pl(
        fast_features.pl.from_pandas(train),
        window=window,
    ).to_pandas()
    score_features = fast_features.compute_basic_features_pl(
        fast_features.pl.from_pandas(score),
        window=window,
    ).to_pandas()
    
    # Impute missing values
    low_var_threshold = 1e-4
    train_features, score_features, _ = fast_features.impute_features(
        train_features, score_features, low_var_threshold, None, None, equip_id, equip
    )
    
    print(f"  Train features: {train_features.shape}")
    print(f"  Score features: {score_features.shape}")
    
    # Fit detectors
    print("\nFitting detectors...")
    det_flags = get_detector_enable_flags(cfg)
    fit_result = fit_all_detectors(
        train=train_features,
        cfg=cfg,
        **det_flags,
        output_manager=None,
        sql_client=sql_client,
        run_id=run_id,
        equip_id=equip_id,
        equip=equip,
    )
    
    ar1_detector = fit_result["ar1_detector"]
    pca_detector = fit_result["pca_detector"]
    iforest_detector = fit_result["iforest_detector"]
    gmm_detector = fit_result["gmm_detector"]
    omr_detector = fit_result["omr_detector"]
    
    print(f"  Detectors fitted: AR1, PCA, IForest, GMM, OMR")
    
    # Score data with detectors
    print("\nScoring with detectors...")
    print(f"  det_flags: {det_flags}")
    frame, omr_contributions = score_all_detectors(
        data=score_features,
        ar1_detector=ar1_detector,
        pca_detector=pca_detector,
        iforest_detector=iforest_detector,
        gmm_detector=gmm_detector,
        omr_detector=omr_detector,
        **det_flags,
    )
    print(f"  Frame columns after scoring: {list(frame.columns)}")
    
    # Build regime basis
    print("\nDetecting operating regimes...")
    regime_basis_train, regime_basis_score, regime_basis_meta = regimes.build_feature_basis(
        train_features=train_features,
        score_features=score_features,
        raw_train=raw_train,
        raw_score=raw_score,
        pca_detector=pca_detector,
        cfg=cfg,
    )
    
    # Fit regime model
    regime_ctx = {
        "regime_basis_train": regime_basis_train,
        "regime_basis_score": regime_basis_score,
        "basis_meta": regime_basis_meta,
        "regime_model": None,
        "regime_basis_hash": None,
        "X_train": train_features,
        "allow_discovery": True,
    }
    
    regime_out = regimes.label(score_features, regime_ctx, {"frame": frame}, cfg)
    frame = regime_out.get("frame", frame)
    regime_model = regime_out.get("regime_model")
    score_regime_labels = regime_out.get("regime_labels")
    train_regime_labels = regime_out.get("regime_labels_train")
    regime_quality_ok = regime_out.get("regime_quality_ok", False)
    
    if regime_model:
        n_regimes = len(regime_model.cluster_centers_)
        current_regime = int(score_regime_labels[-1]) if score_regime_labels is not None else -1
        silhouette = regime_model.meta.get('fit_score', 0.0)
        
        # Compute regime occupancy
        if score_regime_labels is not None:
            regime_counts = pd.Series(score_regime_labels).value_counts()
            total_points = len(score_regime_labels)
            occupancy = {int(r): (count / total_points * 100) for r, count in regime_counts.items()}
        else:
            occupancy = {}
        
        report.regimes = {
            'n_regimes': n_regimes,
            'current_regime': current_regime,
            'silhouette': silhouette,
            'occupancy': occupancy,
            'quality_ok': regime_quality_ok,
        }
        print(f"  Regimes detected: {n_regimes} (silhouette: {silhouette:.3f})")
    
    # Calibrate scores
    print("\nCalibrating detector scores...")
    
    # Score train data for calibration
    train_frame, _ = score_all_detectors(
        data=train_features,
        ar1_detector=ar1_detector,
        pca_detector=pca_detector,
        iforest_detector=iforest_detector,
        gmm_detector=gmm_detector,
        omr_detector=omr_detector,
        **det_flags,
    )
    
    cal_q = cfg.get("thresholds", {}).get("q", 0.98)
    self_tune_cfg = cfg.get("thresholds", {}).get("self_tune", {})
    use_per_regime = cfg.get("fusion", {}).get("per_regime", False) and regime_quality_ok
    
    fit_regimes = train_regime_labels if use_per_regime else None
    transform_regimes = score_regime_labels if use_per_regime else None
    
    frame, calibrators_dict = calibrate_all_detectors(
        train_frame=train_frame,
        score_frame=frame,
        cal_q=cal_q,
        self_tune_cfg=self_tune_cfg,
        fit_regimes=fit_regimes,
        transform_regimes=transform_regimes,
        omr_enabled=det_flags.get('omr_enabled', False),
    )
    
    # Compute detector statistics
    detector_cols = ['ar1_z', 'pca_spe_z', 'pca_t2_z', 'iforest_z', 'gmm_z', 'omr_z']
    for det_col in detector_cols:
        if det_col in frame.columns:
            vals = frame[det_col].dropna()
            if len(vals) > 0:
                report.detector_scores[det_col] = {
                    'mean': float(vals.mean()),
                    'max': float(vals.max()),
                    'p95': float(vals.quantile(0.95)),
                }
    
    # Fusion
    print("\nRunning fusion pipeline...")
    from core.fuse import run_fusion_pipeline
    
    fusion_result = run_fusion_pipeline(
        frame=frame,
        train_frame=train_frame,
        score_data=score_features,
        train_data=train_features,
        cfg=cfg,
        score_regime_labels=score_regime_labels,
        train_regime_labels=train_regime_labels,
        output_manager=None,
        previous_weights=None,
        equip=equip,
    )
    
    frame["fused"] = fusion_result.fused_scores
    episodes = fusion_result.episodes
    fusion_weights = fusion_result.weights_used
    
    print(f"  Episodes detected: {len(episodes)}")
    
    # Extract episode info
    if len(episodes) > 0:
        for _, ep_row in episodes.head(5).iterrows():
            episode_info = {
                'start_time': ep_row.get('start_time', 'N/A'),
                'end_time': ep_row.get('end_time', 'N/A'),
                'duration_hours': ep_row.get('duration_h', 0),
                'max_z': ep_row.get('max_z', 0),
                'severity': 'CRITICAL' if ep_row.get('max_z', 0) > 5 else 'WARNING',
            }
            report.episodes.append(episode_info)
    
    # Drift detection
    print("\nComputing drift metrics...")
    score_out = {"frame": frame}
    score_out = drift.compute(score_features, score_out, cfg)
    frame = score_out["frame"]
    
    if 'drift_z' in frame.columns:
        drift_z = frame['drift_z'].iloc[-1] if len(frame) > 0 else 0
        drift_status = 'DRIFTING' if drift_z > 2.0 else 'STABLE'
        report.drift = {
            'status': drift_status,
            'drift_z': float(drift_z),
            'multi_drift': 'STABLE',  # Simplified for distilled version
        }
    
    # Health computation
    print("\nComputing health scores...")
    
    if 'fused' in frame.columns:
        health_scores = []
        for z_score in frame['fused']:
            health = compute_health_from_z(z_score)
            health_scores.append(health)
        
        frame['health'] = health_scores
        
        current_health = health_scores[-1] if health_scores else 0
        avg_health = np.mean(health_scores) if health_scores else 0
        
        # Determine trend (simple: last 10% vs first 10%)
        if len(health_scores) > 10:
            early = np.mean(health_scores[:len(health_scores)//10])
            late = np.mean(health_scores[-len(health_scores)//10:])
            trend = 'IMPROVING' if late > early else 'DEGRADING' if late < early else 'STABLE'
        else:
            trend = 'STABLE'
        
        status = 'CRITICAL' if current_health < 50 else 'WARNING' if current_health < 70 else 'GOOD'
        
        report.health = {
            'current': current_health,
            'average': avg_health,
            'trend': trend,
            'status': status,
        }
    
    # RUL Forecasting (simplified - just use ForecastEngine)
    print("\nForecasting RUL...")
    
    # Create minimal OutputManager for forecast engine
    output_mgr = OutputManager(sql_client=sql_client, run_id=run_id, equip_id=equip_id)
    output_mgr.equipment = equip
    
    forecast_engine = ForecastEngine(
        sql_client=sql_client,
        output_manager=output_mgr,
        equip_id=equip_id,
        run_id=run_id,
        config=cfg,
        model_state=None,
    )
    
    try:
        forecast_results = forecast_engine.run_forecast()
        if forecast_results.get('success'):
            report.rul_forecast = {
                'p10': forecast_results.get('rul_p10', 0),
                'p50': forecast_results.get('rul_p50', 0),
                'p90': forecast_results.get('rul_p90', 0),
                'confidence': forecast_results.get('confidence', 0),
                'reliability': 'RELIABLE' if forecast_results.get('confidence', 0) > 0.5 else 'NOT_RELIABLE',
            }
            print(f"  RUL P50: {report.rul_forecast['p50']:.0f} hours")
    except Exception as e:
        print(f"  Warning: RUL forecast failed: {e}")
        report.rul_forecast = {
            'p10': 0, 'p50': 0, 'p90': 0,
            'confidence': 0, 'reliability': 'NOT_RELIABLE'
        }
    
    # Top contributing sensors
    print("\nIdentifying top contributing sensors...")
    
    if omr_contributions is not None and len(omr_contributions) > 0:
        # Use OMR contributions
        for sensor, contrib in list(omr_contributions.items())[:10]:
            # Handle both scalar and Series values
            if isinstance(contrib, pd.Series):
                contrib_val = float(contrib.iloc[0]) if len(contrib) > 0 else 0.0
            else:
                contrib_val = float(contrib) if contrib is not None else 0.0
            report.top_culprits.append({
                'name': sensor,
                'contribution': contrib_val,
            })
    else:
        # Fallback: use sensor z-scores from raw data
        if len(raw_score) > 0:
            sensor_means = {}
            for col in raw_score.columns:
                if raw_score[col].dtype in [np.float64, np.float32]:
                    train_median = raw_train[col].median()
                    train_mad = (raw_train[col] - train_median).abs().median()
                    train_std = train_mad * 1.4826 if train_mad > 0 else raw_train[col].std()
                    if train_std > 1e-6:
                        z_scores = (raw_score[col] - train_median) / train_std
                        sensor_means[col] = np.abs(z_scores).mean()
            
            sorted_sensors = sorted(sensor_means.items(), key=lambda x: x[1], reverse=True)
            for sensor, contrib in sorted_sensors[:10]:
                report.top_culprits.append({
                    'name': sensor,
                    'contribution': float(contrib),
                })
    
    # Generate recommendations
    print("\nGenerating recommendations...")
    
    if report.health.get('status') == 'CRITICAL':
        report.recommendations.append("URGENT: Equipment health is CRITICAL - schedule immediate inspection")
    
    if len(report.episodes) > 5:
        report.recommendations.append(f"High anomaly activity detected ({len(report.episodes)} episodes) - investigate root cause")
    
    if report.drift.get('status') == 'DRIFTING':
        report.recommendations.append("Equipment behavior is drifting from baseline - consider recalibration")
    
    if report.rul_forecast.get('p50', 0) < 168:  # Less than 1 week
        report.recommendations.append(f"Low RUL forecast ({report.rul_forecast['p50']:.0f}h) - plan maintenance window")
    
    if report.top_culprits:
        top_sensor = report.top_culprits[0]['name']
        report.recommendations.append(f"Monitor sensor '{top_sensor}' - highest anomaly contributor")
    
    if not report.recommendations:
        report.recommendations.append("Equipment operating normally - continue routine monitoring")
    
    # Cleanup
    sql_client.close()
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    
    return report


def main():
    parser = argparse.ArgumentParser(
        description="ACM Distilled - Analytics-Only Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python acm_distilled.py --equip FD_FAN --start-time "2024-01-01T00:00:00" --end-time "2024-01-31T23:59:59"
  python acm_distilled.py --equip GAS_TURBINE --start-time "2024-10-01T00:00:00" --end-time "2024-10-31T23:59:59"
        """
    )
    
    parser.add_argument(
        '--equip',
        required=True,
        help='Equipment code (e.g., FD_FAN, GAS_TURBINE)'
    )
    parser.add_argument(
        '--start-time',
        required=True,
        help='Analysis start time (ISO format: 2024-01-01T00:00:00)'
    )
    parser.add_argument(
        '--end-time',
        required=True,
        help='Analysis end time (ISO format: 2024-01-31T23:59:59)'
    )
    parser.add_argument(
        '--output',
        help='Output file path (default: print to console)'
    )
    
    args = parser.parse_args()
    
    # Run analytics
    try:
        report = run_analytics(args.equip, args.start_time, args.end_time)
        
        # Generate text report
        text_report = report.to_text()
        
        # Output to file or console
        if args.output:
            with open(args.output, 'w') as f:
                f.write(text_report)
            print(f"\nReport written to: {args.output}")
        else:
            print("\n" + text_report)
        
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

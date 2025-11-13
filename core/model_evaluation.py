"""
Autonomous Model Re-evaluation Module
=====================================
Monitors model quality and triggers retraining when performance degrades.

Quality Metrics Monitored:
1. Detector Saturation: % of z-scores hitting clip limits
2. Anomaly Rate: % of fused_z > threshold
3. Regime Quality: Silhouette score, stability metrics
4. Episode Validity: Duration, frequency, coverage
5. Sensor Coverage: % of sensors contributing to detections

Retraining Triggers:
- Saturation > 5% → Model underfitting, recalibrate
- Anomaly rate > 10% or < 0.01% → Miscalibration
- Regime silhouette < 0.15 → Poor clustering
- Episode coverage > 80% → Excessive false positives
- Config signature changed → Parameter update

Actions:
- Auto-retrains models when degradation detected
- Increments model version
- Logs reasoning to manifest
- Falls back to cached model if retraining fails
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from datetime import datetime, timezone
from utils.logger import Console


class ModelQualityMonitor:
    """Monitors model performance and triggers retraining decisions."""
    
    def __init__(self, cfg: Dict[str, Any]):
        """
        Initialize quality monitor.
        
        Args:
            cfg: Configuration dictionary
        """
        self.cfg = cfg
        self.thresholds = {
            "max_saturation": 0.05,  # 5% saturation triggers retraining
            "max_anomaly_rate": 0.10,  # 10% anomaly rate (too many FPs)
            "min_anomaly_rate": 0.0001,  # 0.01% anomaly rate (too few detections)
            "min_silhouette": 0.15,  # Minimum acceptable regime quality
            "max_episode_coverage": 0.80,  # 80% of data in episodes is suspicious
            "max_episode_duration_days": 30,  # Episodes > 30 days are suspicious
        }
        
        # Override thresholds from config
        if "model_quality" in cfg:
            self.thresholds.update(cfg["model_quality"])
    
    def assess_detector_quality(
        self,
        scores: pd.DataFrame,
        detector_names: List[str],
        clip_z: float = 12.0
    ) -> Dict[str, Any]:
        """
        Assess detector quality by measuring saturation.
        
        Args:
            scores: DataFrame with detector z-scores
            detector_names: List of detector column names
            clip_z: Clipping limit used
        
        Returns:
            Dictionary with saturation metrics
        """
        saturation = {}
        
        for det_name in detector_names:
            z_col = f"{det_name}_z"
            if z_col not in scores.columns:
                continue
            
            z_vals = scores[z_col].values
            # Count values at clip limits
            saturated = (np.abs(z_vals) >= (clip_z * 0.95)).sum()  # 95% of clip limit
            total = len(z_vals)
            saturation_pct = (saturated / total) * 100 if total > 0 else 0.0
            
            saturation[det_name] = {
                "saturated_count": int(saturated),
                "total_count": int(total),
                "saturation_pct": float(saturation_pct)
            }
        
        # Overall saturation
        max_saturation_pct = max([s["saturation_pct"] for s in saturation.values()], default=0.0)
        
        return {
            "per_detector": saturation,
            "max_saturation_pct": max_saturation_pct,
            "is_acceptable": max_saturation_pct < (self.thresholds["max_saturation"] * 100)
        }
    
    def assess_anomaly_rate(
        self,
        scores: pd.DataFrame,
        threshold_col: str = "fused"
    ) -> Dict[str, Any]:
        """
        Assess anomaly detection rate.
        
        Args:
            scores: DataFrame with fused z-scores
            threshold_col: Column name with fused scores
        
        Returns:
            Dictionary with anomaly rate metrics
        """
        active_col = threshold_col
        if active_col not in scores.columns:
            # Backward compatibility: prior builds used "fused_z"
            fallback_col = "fused_z"
            if fallback_col in scores.columns:
                active_col = fallback_col
            else:
                return {
                    "anomaly_rate": 0.0,
                    "is_acceptable": False,
                    "reason": "Missing fused score column"
                }
        
        fused_series = pd.to_numeric(scores[active_col], errors="coerce")
        fused_values = fused_series.to_numpy(dtype=float, copy=False)
        valid_mask = ~np.isnan(fused_values)
        if not valid_mask.any():
            return {
                "anomaly_rate": 0.0,
                "is_acceptable": False,
                "reason": "Fused score column has no numeric values"
            }

        fused_z = fused_values[valid_mask]
        threshold = 1.0  # Assuming z > 1.0 is anomalous
        
        anomalies = (fused_z > threshold).sum()
        total = len(fused_z)
        anomaly_rate = (anomalies / total) if total > 0 else 0.0
        
        is_acceptable = (
            anomaly_rate >= self.thresholds["min_anomaly_rate"] and
            anomaly_rate <= self.thresholds["max_anomaly_rate"]
        )
        
        return {
            "anomaly_count": int(anomalies),
            "total_count": int(total),
            "anomaly_rate": float(anomaly_rate),
            "is_acceptable": is_acceptable,
            "reason": (
                "Anomaly rate too high" if anomaly_rate > self.thresholds["max_anomaly_rate"] else
                "Anomaly rate too low" if anomaly_rate < self.thresholds["min_anomaly_rate"] else
                "OK"
            )
        }
    
    def assess_regime_quality(
        self,
        regime_quality: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess regime clustering quality.
        
        Args:
            regime_quality: Regime quality metrics from regimes module
        
        Returns:
            Dictionary with regime quality assessment
        """
        silhouette = regime_quality.get("silhouette", 0.0)
        is_acceptable = silhouette >= self.thresholds["min_silhouette"]
        
        return {
            "silhouette": float(silhouette),
            "min_threshold": float(self.thresholds["min_silhouette"]),
            "is_acceptable": is_acceptable,
            "reason": "Silhouette score too low" if not is_acceptable else "OK"
        }
    
    def assess_episode_quality(
        self,
        episodes: pd.DataFrame,
        total_rows: int
    ) -> Dict[str, Any]:
        """
        Assess episode detection quality.
        
        Args:
            episodes: DataFrame with detected episodes
            total_rows: Total number of timesteps
        
        Returns:
            Dictionary with episode quality metrics
        """
        if episodes.empty:
            return {
                "episode_count": 0,
                "coverage": 0.0,
                "max_duration_days": 0.0,
                "is_acceptable": True,
                "reason": "No episodes detected"
            }
        
        # Calculate coverage
        episode_rows = episodes["duration"].sum() if "duration" in episodes.columns else 0
        coverage = (episode_rows / total_rows) if total_rows > 0 else 0.0
        
        # Calculate max duration (in days if timestamps available)
        if "start_dt" in episodes.columns and "end_dt" in episodes.columns:
            durations = (episodes["end_dt"] - episodes["start_dt"]).dt.total_seconds() / 86400
            max_duration_days = float(durations.max())
        else:
            max_duration_days = 0.0
        
        is_acceptable = (
            coverage <= self.thresholds["max_episode_coverage"] and
            max_duration_days <= self.thresholds["max_episode_duration_days"]
        )
        
        return {
            "episode_count": len(episodes),
            "coverage": float(coverage),
            "max_duration_days": float(max_duration_days),
            "is_acceptable": is_acceptable,
            "reason": (
                "Episode coverage too high" if coverage > self.thresholds["max_episode_coverage"] else
                f"Episode duration too long ({max_duration_days:.1f} days)" if max_duration_days > self.thresholds["max_episode_duration_days"] else
                "OK"
            )
        }
    
    def should_retrain(
        self,
        quality_metrics: Dict[str, Any],
        config_changed: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Decide if models should be retrained based on quality metrics.
        
        Args:
            quality_metrics: Aggregated quality metrics
            config_changed: Whether configuration signature changed
        
        Returns:
            Tuple of (should_retrain, reasons)
        """
        reasons = []
        
        # Check config change
        if config_changed:
            reasons.append("Configuration changed")
        
        # Check detector saturation
        detector_quality = quality_metrics.get("detector_quality", {})
        if not detector_quality.get("is_acceptable", True):
            reasons.append(
                f"Detector saturation too high: {detector_quality.get('max_saturation_pct', 0):.1f}%"
            )
        
        # Check anomaly rate
        anomaly_metrics = quality_metrics.get("anomaly_metrics", {})
        if not anomaly_metrics.get("is_acceptable", True):
            reasons.append(anomaly_metrics.get("reason", "Anomaly rate issue"))
        
        # Check regime quality
        regime_metrics = quality_metrics.get("regime_metrics", {})
        if not regime_metrics.get("is_acceptable", True):
            reasons.append(regime_metrics.get("reason", "Regime quality issue"))
        
        # Check episode quality
        episode_metrics = quality_metrics.get("episode_metrics", {})
        if not episode_metrics.get("is_acceptable", True):
            reasons.append(episode_metrics.get("reason", "Episode quality issue"))
        
        should_retrain = len(reasons) > 0
        
        return should_retrain, reasons
    
    def create_quality_report(
        self,
        quality_metrics: Dict[str, Any],
        should_retrain: bool,
        reasons: List[str]
    ) -> Dict[str, Any]:
        """
        Create comprehensive quality report for logging.
        
        Args:
            quality_metrics: All quality metrics
            should_retrain: Retraining decision
            reasons: Reasons for retraining
        
        Returns:
            Quality report dictionary
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "should_retrain": should_retrain,
            "retraining_reasons": reasons,
            "metrics": quality_metrics,
            "thresholds": self.thresholds
        }


def assess_model_quality(
    scores: pd.DataFrame,
    episodes: pd.DataFrame,
    regime_quality: Dict[str, Any],
    cfg: Dict[str, Any],
    cached_manifest: Optional[Dict[str, Any]] = None
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Main entry point for model quality assessment.
    
    Args:
        scores: Scores dataframe with detector outputs
        episodes: Episodes dataframe
        regime_quality: Regime quality metrics
        cfg: Configuration dictionary
        cached_manifest: Cached model manifest (for config comparison)
    
    Returns:
        Tuple of (should_retrain, reasons, quality_report)
    """
    monitor = ModelQualityMonitor(cfg)
    
    # Assess detector quality
    detector_names = ["ar1", "pca_spe", "pca_t2", "mhal", "iforest", "gmm"]
    clip_z = cfg.get("thresholds", {}).get("self_tune", {}).get("clip_z", 12.0)
    detector_quality = monitor.assess_detector_quality(scores, detector_names, clip_z)
    
    # Assess anomaly rate
    anomaly_metrics = monitor.assess_anomaly_rate(scores)
    
    # Assess regime quality
    regime_metrics = monitor.assess_regime_quality(regime_quality)
    
    # Assess episode quality
    episode_metrics = monitor.assess_episode_quality(episodes, len(scores))
    
    # Check if config changed
    config_changed = False
    if cached_manifest:
        cached_sig = cached_manifest.get("config_signature", "")
        current_sig = cfg.get("_signature", "unknown")
        config_changed = (cached_sig != current_sig)
    
    # Aggregate metrics
    quality_metrics = {
        "detector_quality": detector_quality,
        "anomaly_metrics": anomaly_metrics,
        "regime_metrics": regime_metrics,
        "episode_metrics": episode_metrics
    }
    
    # Decide on retraining
    should_retrain, reasons = monitor.should_retrain(quality_metrics, config_changed)
    
    # Create report
    quality_report = monitor.create_quality_report(quality_metrics, should_retrain, reasons)
    
    return should_retrain, reasons, quality_report


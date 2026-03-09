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
- Saturation > 5% -> Model underfitting, recalibrate
- Anomaly rate > 10% or < 0.01% -> Miscalibration
- Regime silhouette < 0.15 -> Poor clustering
- Episode coverage > 80% -> Excessive false positives
- Config signature changed -> Parameter update

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
from dataclasses import dataclass
from core.observability import Console


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
        threshold_col: str = "fused",
        cfg: Optional[Dict[str, Any]] = None,
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
        # Use the configured alert z-score as the anomaly threshold.
        # Hardcoding z=1.0 flagged 30-40% of healthy data (1 std dev above mean),
        # causing perpetual refit loops. The actual alert threshold is ~3.0.
        _cfg = cfg if cfg is not None else self.cfg
        _thresh_cfg = (_cfg or {}).get("thresholds", {})
        threshold = float(
            _thresh_cfg.get("alert_z")
            or _thresh_cfg.get("alert")
            or 3.0
        )
        
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
    
    # Assess anomaly rate (pass cfg so threshold uses alert_z from config, not hardcoded 1.0)
    anomaly_metrics = monitor.assess_anomaly_rate(scores, cfg=cfg)
    
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


def evaluate_force_retrain_triggers(
    cfg: Dict[str, Any],
    cached_manifest: Optional[Dict[str, Any]],
    score_out: Dict[str, Any],
    regime_quality_ok: bool,
    current_model_maturity: Optional[str],
    boolean_only_metrics: List[str],
    equip: str = "",
    logger: Any = Console,
) -> Dict[str, Any]:
    """
    Evaluate force-retrain triggers for cached models.

    This function centralizes policy logic for:
    - config signature changes
    - model age threshold
    - regime-quality threshold by metric type
    """
    config_changed = False
    if cached_manifest:
        cached_sig = cached_manifest.get("config_signature", "")
        current_sig = cfg.get("_signature", "unknown")
        config_changed = (cached_sig != current_sig)

    auto_retrain_cfg = cfg.get("models", {}).get("auto_retrain", {})
    if isinstance(auto_retrain_cfg, bool):
        auto_retrain_cfg = {}

    model_age_trigger = False
    model_age_hours = 0.0
    max_age_hours = float(auto_retrain_cfg.get("max_model_age_hours", 720))
    if cached_manifest:
        created_at_str = cached_manifest.get("created_at")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
                model_age_hours = (datetime.now() - created_at).total_seconds() / 3600.0
                if model_age_hours > max_age_hours:
                    model_age_trigger = True
            except Exception:
                pass

    regime_quality_trigger = False
    current_regime_score = float(score_out.get("regime_score", 0.0))
    regime_metric_name = str(score_out.get("regime_metric", "silhouette"))
    min_regime_quality = float(auto_retrain_cfg.get("min_regime_quality", 0.3))
    min_dbcv_quality = float(auto_retrain_cfg.get("min_dbcv_quality", 0.0))

    if regime_metric_name in ("silhouette", "silhouette_non_noise"):
        regime_quality_trigger = current_regime_score < min_regime_quality
    elif regime_metric_name in ("dbcv", "persistence"):
        # For HDBSCAN-style metrics use the raw DBCV/persistence threshold.
        regime_quality_trigger = current_regime_score < min_dbcv_quality
    elif regime_metric_name not in boolean_only_metrics:
        # Unknown numeric metric: fallback to quality_ok boolean.
        regime_quality_trigger = not regime_quality_ok
    # boolean_only_metrics: no threshold trigger.

    force_retrain = config_changed or model_age_trigger or regime_quality_trigger

    reasons: List[str] = []
    if config_changed:
        reasons.append("config_changed")
    if model_age_trigger:
        reasons.append(f"age={model_age_hours:.0f}h>{max_age_hours:.0f}h")
    if regime_quality_trigger:
        if not regime_quality_ok:
            reasons.append(
                f"regime_quality_ok=False (metric={regime_metric_name}, score={current_regime_score:.3f})"
            )
        else:
            threshold_used = min_dbcv_quality if regime_metric_name in ("dbcv", "persistence") else min_regime_quality
            reasons.append(f"{regime_metric_name}={current_regime_score:.3f}<{threshold_used}")

    if force_retrain and reasons:
        logger.warn(f"Forcing retraining: {' | '.join(reasons)}", component="MODEL", equip=equip)

    retrain_reason = "config_changed" if config_changed else (
        "model_age" if model_age_trigger else (
            "regime_quality" if regime_quality_trigger else "forced"
        )
    )

    clear_regime_model = bool(
        regime_quality_trigger and current_model_maturity in (None, "COLDSTART", "LEARNING")
    )

    return {
        "force_retrain": force_retrain,
        "reasons": reasons,
        "retrain_reason": retrain_reason,
        "config_changed": config_changed,
        "model_age_trigger": model_age_trigger,
        "model_age_hours": model_age_hours,
        "max_age_hours": max_age_hours,
        "regime_quality_trigger": regime_quality_trigger,
        "regime_metric_name": regime_metric_name,
        "current_regime_score": current_regime_score,
        "clear_regime_model": clear_regime_model,
    }


def evaluate_and_maybe_refit_cached_models(
    *,
    cfg: Dict[str, Any],
    cached_models: Optional[Dict[str, Any]],
    cached_manifest: Optional[Dict[str, Any]],
    detectors_just_trained: bool,
    score_out: Dict[str, Any],
    regime_quality_ok: bool,
    current_model_maturity: Optional[str],
    boolean_only_metrics: List[str],
    equip: str,
    logger: Any,
    record_model_refit_fn: Any,
    fit_all_detectors_fn: Any,
    train: pd.DataFrame,
    det_flags: Dict[str, Any],
    output_manager: Any,
    sql_client: Any,
    run_id: Optional[str],
    equip_id: int,
    regime_model: Optional[Any],
) -> "AutoRetrainDecision":
    """
    Evaluate auto-retrain triggers for cached models and optionally refit detectors.
    """
    force_retrain = False
    retrain_result = None
    cached_models_out = cached_models
    regime_model_out = regime_model

    if not (cached_models and not detectors_just_trained):
        return AutoRetrainDecision(
            force_retrain=force_retrain,
            cached_models=cached_models_out,
            regime_model=regime_model_out,
            retrain_result=retrain_result,
        )

    try:
        trigger_eval = evaluate_force_retrain_triggers(
            cfg=cfg,
            cached_manifest=cached_manifest,
            score_out=score_out,
            regime_quality_ok=regime_quality_ok,
            current_model_maturity=current_model_maturity,
            boolean_only_metrics=boolean_only_metrics,
            equip=equip,
            logger=logger,
        )
        force_retrain = bool(trigger_eval["force_retrain"])

        if force_retrain:
            cached_models_out = None
            if bool(trigger_eval["clear_regime_model"]):
                regime_model_out = None

            retrain_reason = str(trigger_eval["retrain_reason"])
            record_model_refit_fn(equip, reason=retrain_reason, detector="all")

            retrain_result = fit_all_detectors_fn(
                train=train,
                cfg=cfg,
                **det_flags,
                output_manager=output_manager,
                sql_client=sql_client,
                run_id=run_id,
                equip_id=equip_id,
                equip=equip,
            )
    except Exception as e:
        raise RuntimeError(f"Quality assessment failed: {e}") from e

    return AutoRetrainDecision(
        force_retrain=force_retrain,
        cached_models=cached_models_out,
        regime_model=regime_model_out,
        retrain_result=retrain_result,
    )


@dataclass
class AutoRetrainDecision:
    """Internal decision payload for cached-model retrain evaluation."""
    force_retrain: bool
    cached_models: Optional[Dict[str, Any]]
    regime_model: Optional[Any]
    retrain_result: Optional[Dict[str, Any]]


def run_auto_retrain_stage(
    *,
    cfg: Dict[str, Any],
    cached_models: Optional[Dict[str, Any]],
    cached_manifest: Optional[Dict[str, Any]],
    detectors_just_trained: bool,
    score_out: Dict[str, Any],
    regime_quality_ok: bool,
    current_model_maturity: Optional[str],
    boolean_only_metrics: List[str],
    equip: str,
    logger: Any,
    record_model_refit_fn: Any,
    fit_all_detectors_fn: Any,
    train: pd.DataFrame,
    det_flags: Dict[str, Any],
    output_manager: Any,
    sql_client: Any,
    run_id: Optional[str],
    equip_id: int,
    regime_model: Optional[Any],
    detectors: Dict[str, Any],
    force_retrain_requested: bool = False,
) -> "AutoRetrainStageResult":
    """
    Run auto-retrain evaluation and apply retrain detector outputs when triggered.
    """
    if force_retrain_requested:
        logger.warn(
            "Force retrain requested from CLI - fitting detectors unconditionally",
            component="MODEL",
            equip=equip,
        )
        record_model_refit_fn(equip, reason="force_retrain_cli", detector="all")
        retrain_result = fit_all_detectors_fn(
            train=train,
            cfg=cfg,
            **det_flags,
            output_manager=output_manager,
            sql_client=sql_client,
            run_id=run_id,
            equip_id=equip_id,
            equip=equip,
        )
        retrain_out = AutoRetrainDecision(
            force_retrain=True,
            cached_models=None,
            regime_model=regime_model,
            retrain_result=retrain_result,
        )
    else:
        retrain_out = evaluate_and_maybe_refit_cached_models(
            cfg=cfg,
            cached_models=cached_models,
            cached_manifest=cached_manifest,
            detectors_just_trained=detectors_just_trained,
            score_out=score_out,
            regime_quality_ok=regime_quality_ok,
            current_model_maturity=current_model_maturity,
            boolean_only_metrics=boolean_only_metrics,
            equip=equip,
            logger=logger,
            record_model_refit_fn=record_model_refit_fn,
            fit_all_detectors_fn=fit_all_detectors_fn,
            train=train,
            det_flags=det_flags,
            output_manager=output_manager,
            sql_client=sql_client,
            run_id=run_id,
            equip_id=equip_id,
            regime_model=regime_model,
        )

    retrain_result = retrain_out.retrain_result
    detectors_out = dict(detectors)
    if retrain_result is not None:
        detectors_out["ar1_detector"] = retrain_result["ar1_detector"]
        detectors_out["pca_detector"] = retrain_result["pca_detector"]
        detectors_out["iforest_detector"] = retrain_result["iforest_detector"]
        detectors_out["gmm_detector"] = retrain_result["gmm_detector"]
        detectors_out["omr_detector"] = retrain_result["omr_detector"]
        detectors_out["pca_train_spe"] = retrain_result["pca_train_spe"]
        detectors_out["pca_train_t2"] = retrain_result["pca_train_t2"]

    return AutoRetrainStageResult(
        force_retrain=bool(retrain_out.force_retrain),
        cached_models=retrain_out.cached_models,
        regime_model=retrain_out.regime_model,
        detectors=detectors_out,
    )


@dataclass
class AutoRetrainStageResult:
    """Typed result payload for auto-retrain stage."""
    force_retrain: bool
    cached_models: Optional[Dict[str, Any]]
    regime_model: Optional[Any]
    detectors: Dict[str, Any]


def auto_tune_parameters(
    frame: pd.DataFrame,
    episodes: pd.DataFrame,
    score_out: Dict[str, Any],
    regime_quality_ok: bool,
    cfg: Dict[str, Any],
    sql_client: Any,
    run_id: Optional[str],
    equip_id: int,
    equip: str,
    output_manager: Optional[Any] = None,
    cached_manifest: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Perform autonomous parameter tuning based on model quality assessment.
    
    Evaluates model quality metrics (anomaly rate, drift score, regime quality) and
    proposes parameter adjustments. Records tuning actions to ACM_ConfigHistory and
    creates refit requests in ACM_RefitRequests when quality degrades.
    
    Args:
        frame: Scored DataFrame with detector z-scores and fused output
        episodes: Detected anomaly episodes
        score_out: Score output dict with silhouette score etc.
        regime_quality_ok: Whether regime clustering met quality threshold
        cfg: Configuration dictionary
        sql_client: SQL client for database writes
        run_id: Current run identifier
        equip_id: Equipment ID
        equip: Equipment name for logging
        output_manager: Optional OutputManager for refit request persistence
        cached_manifest: Optional cached model manifest for age checks
        
    v11.5.0 / v11.8.0: Refit Request Guard
    =======================================
    Refit requests are quality-gated to prevent feedback loops during
    historical batch processing:

    1. Batch N scores data, metrics look poor (expected during calibration)
    2. auto_tune writes refit request
    3. Batch N+1 checks refit_request, triggers full refit
    4. Models change, thresholds shift
    5. Repeat - models never stabilize

    Guard: CONVERGED models skip refit evaluation entirely (v11.6.0).
    Quality thresholds (silhouette, drift, anomaly rate) gate refit requests.
    """
    # v11.6.0 FIX #3: Skip refit evaluation entirely for CONVERGED models
    # CONVERGED models are stable and should NOT trigger refit requests.
    # This prevents 170+ spurious refit requests for stable equipment.
    model_maturity = cfg.get("runtime", {}).get("model_maturity_state", "LEARNING")
    if model_maturity == "CONVERGED":
        Console.info(
            "Auto-tune: Skipping refit evaluation - model is CONVERGED (stable)",
            component="AUTO-TUNE", equip=equip, maturity=model_maturity
        )
        return
    
    # v11.8.0 ADAPTIVE: Refit requests always allowed - quality metrics decide
    allow_refit_requests = True

    try:
        from core.config_history_writer import log_auto_tune_changes
        
        # Build regime quality metrics
        regime_quality_metrics = {
            "silhouette": score_out.get("silhouette", 0.0),
            "quality_ok": regime_quality_ok
        }
        
        # Perform full quality assessment
        should_retrain, reasons, quality_report = assess_model_quality(
            scores=frame,
            episodes=episodes,
            regime_quality=regime_quality_metrics,
            cfg=cfg,
            cached_manifest=cached_manifest
        )
        
        # Extract metrics for additional retrain triggers
        auto_retrain_cfg = cfg.get("models", {}).get("auto_retrain", {})
        if isinstance(auto_retrain_cfg, bool):
            auto_retrain_cfg = {}
        
        # Check anomaly rate trigger
        anomaly_rate_trigger = False
        anomaly_metrics = quality_report.get("metrics", {}).get("anomaly_metrics", {})
        current_anomaly_rate = anomaly_metrics.get("anomaly_rate", 0.0)
        max_anomaly_rate = auto_retrain_cfg.get("max_anomaly_rate", 0.25)
        if current_anomaly_rate > max_anomaly_rate:
            anomaly_rate_trigger = True
            if not should_retrain:
                reasons = []
            reasons.append(f"anomaly_rate={current_anomaly_rate:.2%} > {max_anomaly_rate:.2%}")
            Console.warn(f"Anomaly rate {current_anomaly_rate:.2%} exceeds threshold {max_anomaly_rate:.2%}", 
                        component="RETRAIN-TRIGGER", equip=equip, 
                        anomaly_rate=round(current_anomaly_rate, 4), threshold=max_anomaly_rate)
        
        # Check drift score trigger
        drift_score_trigger = False
        drift_score = quality_report.get("metrics", {}).get("drift_score", 0.0)
        max_drift_score = auto_retrain_cfg.get("max_drift_score", 2.0)
        if drift_score > max_drift_score:
            drift_score_trigger = True
            if not should_retrain and not anomaly_rate_trigger:
                reasons = []
            reasons.append(f"drift_score={drift_score:.2f} > {max_drift_score:.2f}")
        
        # Aggregate all retrain triggers
        needs_retraining = should_retrain or anomaly_rate_trigger or drift_score_trigger
        
        if not needs_retraining:
            return
        
        # Auto-tune parameters based on specific issues
        tuning_actions = []
        
        # Issue 1: High detector saturation - Increase clip_z
        detector_quality = quality_report.get("metrics", {}).get("detector_quality", {})
        if detector_quality.get("max_saturation_pct", 0) > 5.0:
            self_tune_cfg = cfg.get("thresholds", {}).get("self_tune", {})
            raw_clip_z = self_tune_cfg.get("clip_z", 12.0)
            try:
                current_clip_z = float(raw_clip_z)
            except (TypeError, ValueError):
                current_clip_z = 12.0
            
            clip_caps = [
                self_tune_cfg.get("max_clip_z"),
                cfg.get("model_quality", {}).get("max_clip_z"),
                50.0,
            ]
            clip_cap = max((float(c) for c in clip_caps if c is not None), default=50.0)
            clip_cap = max(clip_cap, current_clip_z, 20.0)
            
            proposed_clip = round(current_clip_z * 1.2, 2)
            if proposed_clip <= current_clip_z + 0.05:
                proposed_clip = current_clip_z + 2.0
            new_clip_z = min(proposed_clip, clip_cap)
            
            if new_clip_z > current_clip_z + 0.05:
                tuning_actions.append(f"clip_z: {current_clip_z:.2f}->{new_clip_z:.2f}")
        
        # Issue 2: High anomaly rate - Increase k_sigma
        if anomaly_metrics.get("anomaly_rate", 0) > 0.10:
            raw_k_sigma = cfg.get("episodes", {}).get("cpd", {}).get("k_sigma", 2.0)
            try:
                current_k = float(raw_k_sigma)
            except (TypeError, ValueError):
                current_k = 2.0
            new_k = min(round(current_k * 1.1, 3), 4.0)
            if new_k > current_k + 0.05:
                tuning_actions.append(f"k_sigma: {current_k:.3f}->{new_k:.3f}")
        
        # Issue 3: Low regime quality - Increase k_max
        regime_metrics = quality_report.get("metrics", {}).get("regime_metrics", {})
        if regime_metrics.get("silhouette", 1.0) < 0.15:
            auto_k_cfg = cfg.get("regimes", {}).get("auto_k", {})
            raw_k_max = auto_k_cfg.get("k_max", cfg.get("regimes", {}).get("k_max", 8))
            try:
                current_k_max = int(raw_k_max)
            except (TypeError, ValueError):
                current_k_max = 8
            new_k_max = min(current_k_max + 2, 12)
            if new_k_max > current_k_max:
                tuning_actions.append(f"k_max: {current_k_max}->{int(new_k_max)}")
        
        if tuning_actions:
            # Log config changes to ACM_ConfigHistory
            refit_triggered = False
            try:
                if sql_client and run_id:
                    # v11.5.0: Only trigger refit if allowed by pipeline mode
                    trigger_refit_on_tune = auto_retrain_cfg.get("on_tuning_change", False) and allow_refit_requests
                    log_auto_tune_changes(
                        sql_client=sql_client,
                        equip_id=int(equip_id),
                        tuning_actions=tuning_actions,
                        run_id=run_id,
                        trigger_refit=trigger_refit_on_tune
                    )
                    refit_triggered = trigger_refit_on_tune
            except Exception as log_err:
                Console.warn(f"Failed to log auto-tune changes: {log_err}", component="CONFIG_HIST",
                            equip=equip, error=str(log_err)[:200])
            
            # Consolidated auto-tune log
            Console.info(f"Auto-tune: {len(tuning_actions)} adjustments ({', '.join(tuning_actions)}) | refit={'triggered' if refit_triggered else 'next_run'}", component="AUTO-TUNE")

        # Persist refit request only for CONVERGED models where quality has
        # regressed from a known-stable baseline. LEARNING models score high
        # anomaly rates by definition (contaminated training data, calibration
        # still settling) — writing a refit request here causes a refit-every-
        # batch feedback loop: refit → new auto-tune values in ACM_Config →
        # config hash changes → cache invalid → refit again next batch.
        if output_manager and allow_refit_requests and needs_retraining and model_maturity == "CONVERGED":
            output_manager.write_refit_request(
                reasons=reasons,
                anomaly_rate=current_anomaly_rate if anomaly_rate_trigger else None,
                drift_score=drift_score if drift_score_trigger else None,
                regime_quality=regime_metrics.get("silhouette", 0.0),
            )
    
    except Exception as e:
        raise RuntimeError(f"Autonomous tuning failed: {e}") from e

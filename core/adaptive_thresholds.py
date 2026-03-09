"""
Adaptive Threshold Calculator for Dynamic FusedZ Thresholds

This module calculates data-driven thresholds for anomaly detection scores,
replacing hardcoded values with quantile-based or MAD-based calculations.

Key Features:
- Quantile-based thresholds (e.g., 99.7th percentile)
- MAD-based thresholds (Median Absolute Deviation)
- Hybrid approach combining both methods
- Per-regime threshold calculation
- Robust to outliers and non-normal distributions
- v11.3.3: Contamination filtering before threshold calculation

Usage:
    calc = AdaptiveThresholdCalculator()
    threshold = calc.calculate_fused_threshold(
        train_fused_z=train_scores,
        method='quantile',
        confidence=0.997
    )
"""

import numpy as np
import pandas as pd
from typing import Any, Dict, Optional, Union, Tuple
import logging

logger = logging.getLogger(__name__)

# v11.3.3: Import contamination filter for consistent filtering
from core.fuse import (
    CalibrationContaminationFilter,
    ContaminationFilterResult,
    resolve_contamination_filter_policy,
)


class AdaptiveThresholdCalculator:
    """
    Calculate adaptive anomaly detection thresholds from training data.
    
    Replaces hardcoded thresholds (e.g., FusedZ >= 3.0) with data-driven values
    that adapt to each equipment's actual operating distribution.
    
    v11.3.3: Now applies contamination filtering before threshold calculation
    to address Analytics Audit Finding #6.
    """
    
    def __init__(
        self,
        min_samples: int = 100,
        contamination_filter_enabled: bool = True,
        contamination_filter_method: str = 'iterative_mad',
        contamination_filter_z_threshold: float = 4.0,
    ):
        """
        Initialize the threshold calculator.
        
        Args:
            min_samples: Minimum number of samples required for reliable calculation.
                        If fewer samples, fallback to default threshold.
            contamination_filter_enabled: Whether to filter contaminated samples (v11.3.3)
            contamination_filter_method: Method for contamination filtering
            contamination_filter_z_threshold: Z-threshold for contamination filtering
        """
        self.min_samples = min_samples
        self.contamination_filter_enabled = contamination_filter_enabled
        self.contamination_filter_method = contamination_filter_method
        self.contamination_filter_z_threshold = contamination_filter_z_threshold
        # Track last filter result for diagnostics
        self.last_filter_result_: Optional[ContaminationFilterResult] = None
        
    def calculate_fused_threshold(
        self,
        train_fused_z: Union[np.ndarray, pd.Series],
        method: str = 'quantile',
        confidence: float = 0.997,
        regime_labels: Optional[Union[np.ndarray, pd.Series]] = None,
        fallback_threshold: float = 3.0
    ) -> Union[float, Dict[int, float]]:
        """
        Calculate adaptive threshold for FusedZ scores.
        
        Args:
            train_fused_z: Training FusedZ scores (clean, non-anomalous data)
            method: Calculation method - 'quantile', 'mad', or 'hybrid'
            confidence: Confidence level (0.997 = 99.7% = 3-sigma equivalent)
            regime_labels: Optional regime assignments for per-regime thresholds
            fallback_threshold: Default value if calculation fails
            
        Returns:
            float: Global threshold if regime_labels is None
            Dict[int, float]: Per-regime thresholds if regime_labels provided
            
        Example:
            # Global threshold
            threshold = calc.calculate_fused_threshold(train_fused_z)
            
            # Per-regime thresholds
            thresholds = calc.calculate_fused_threshold(
                train_fused_z, 
                regime_labels=regime_labels
            )
            # Returns: {0: 2.8, 1: 3.5, 2: 2.3}
        """
        # Input validation
        if train_fused_z is None or len(train_fused_z) == 0:
            logger.warning("Empty training data - using fallback threshold")
            return fallback_threshold
            
        # Convert to numpy array
        if isinstance(train_fused_z, pd.Series):
            train_fused_z = train_fused_z.values
        
        # Remove NaN/inf
        train_fused_z = train_fused_z[np.isfinite(train_fused_z)]
        
        if len(train_fused_z) < self.min_samples:
            logger.warning(
                f"Insufficient samples ({len(train_fused_z)} < {self.min_samples}) - "
                f"using fallback threshold"
            )
            return fallback_threshold
        
        # =========================================================================
        # v11.3.3: CONTAMINATION FILTERING (Analytics Audit Finding #6)
        # Filter anomalous samples BEFORE calculating thresholds to prevent
        # contaminated training windows from producing permissive thresholds.
        # =========================================================================
        if self.contamination_filter_enabled and len(train_fused_z) >= 50:
            contam_filter = CalibrationContaminationFilter(
                method=self.contamination_filter_method,
                z_threshold=self.contamination_filter_z_threshold,
            )
            filter_result = contam_filter.filter(train_fused_z)
            self.last_filter_result_ = filter_result
            train_fused_z = filter_result.filtered_data
            
            if filter_result.n_excluded > 0:
                logger.info(
                    f"Contamination filter ({self.contamination_filter_method}): excluded "
                    f"{filter_result.n_excluded}/{filter_result.n_original} samples "
                    f"({filter_result.exclusion_rate:.1%})"
                )
        else:
            self.last_filter_result_ = None
        # =========================================================================
        # END CONTAMINATION FILTERING
        # =========================================================================
            
        # Per-regime calculation
        if regime_labels is not None:
            return self._calculate_per_regime(
                train_fused_z, 
                regime_labels, 
                method, 
                confidence, 
                fallback_threshold
            )
        
        # Global calculation
        try:
            if method == 'quantile':
                threshold = self._quantile_threshold(train_fused_z, confidence)
            elif method == 'mad':
                threshold = self._mad_threshold(train_fused_z, n_sigma=3.0)
            elif method == 'hybrid':
                threshold = self._hybrid_threshold(train_fused_z, confidence)
            else:
                raise ValueError(f"Unknown method: {method}")
                
            # Validation
            is_valid, reason = self.validate_threshold(threshold, train_fused_z)
            if not is_valid:
                logger.warning(
                    f"Calculated threshold {threshold:.3f} failed validation: {reason}. "
                    f"Using fallback {fallback_threshold}"
                )
                return fallback_threshold
                
            logger.info(
                f"Calculated {method} threshold: {threshold:.3f} "
                f"(samples={len(train_fused_z)}, confidence={confidence})"
            )
            return threshold
            
        except Exception as e:
            logger.error(f"Threshold calculation failed: {e}. Using fallback.")
            return fallback_threshold
    
    def _calculate_per_regime(
        self,
        train_fused_z: np.ndarray,
        regime_labels: Union[np.ndarray, pd.Series],
        method: str,
        confidence: float,
        fallback_threshold: float
    ) -> Dict[int, float]:
        """
        Calculate separate thresholds for each operating regime.
        
        Args:
            train_fused_z: Training FusedZ scores
            regime_labels: Regime assignments (same length as train_fused_z)
            method: Calculation method
            confidence: Confidence level
            fallback_threshold: Default value
            
        Returns:
            Dict mapping regime_id -> threshold value
        """
        if isinstance(regime_labels, pd.Series):
            regime_labels = regime_labels.values
            
        if len(train_fused_z) != len(regime_labels):
            raise ValueError(
                f"Length mismatch: train_fused_z={len(train_fused_z)}, "
                f"regime_labels={len(regime_labels)}"
            )
        
        thresholds = {}
        unique_regimes = np.unique(regime_labels[~pd.isna(regime_labels)])
        
        for regime_id in unique_regimes:
            regime_mask = (regime_labels == regime_id)
            regime_scores = train_fused_z[regime_mask]
            
            # Calculate threshold for this regime
            regime_threshold = self.calculate_fused_threshold(
                train_fused_z=regime_scores,
                method=method,
                confidence=confidence,
                regime_labels=None,  # Prevent recursion
                fallback_threshold=fallback_threshold
            )
            
            thresholds[int(regime_id)] = regime_threshold
            logger.info(
                f"Regime {regime_id}: threshold={regime_threshold:.3f}, "
                f"samples={len(regime_scores)}"
            )
        
        # Add global threshold for unassigned points
        if -1 not in thresholds:
            thresholds[-1] = fallback_threshold
            logger.info(f"Global/unassigned threshold: {fallback_threshold}")
        
        return thresholds
    
    def _quantile_threshold(
        self, 
        data: np.ndarray, 
        confidence: float
    ) -> float:
        """
        Calculate threshold as quantile of training distribution.
        
        Args:
            data: Training scores
            confidence: Quantile level (e.g., 0.997 for 99.7th percentile)
            
        Returns:
            Threshold value at specified quantile
            
        Notes:
            - Directly uses empirical distribution
            - No assumptions about normality
            - Confidence 0.997 ≈ 3-sigma for normal distributions
        """
        threshold = np.percentile(data, confidence * 100)
        return float(threshold)
    
    def _mad_threshold(
        self, 
        data: np.ndarray, 
        n_sigma: float = 3.0
    ) -> float:
        """
        Calculate threshold using Median Absolute Deviation (MAD).
        
        Args:
            data: Training scores
            n_sigma: Number of "sigma" (MAD units) above median
            
        Returns:
            Threshold = median + n_sigma * (1.4826 * MAD)
            
        Notes:
            - Robust to outliers (uses median instead of mean)
            - MAD * 1.4826 ≈ standard deviation for normal data
            - n_sigma=3.0 gives ~99.7% coverage for normal distributions
        """
        median = np.median(data)
        mad = np.median(np.abs(data - median))
        
        # Scale MAD to approximate standard deviation
        # 1.4826 = 1 / (Φ^(-1)(0.75)) where Φ is normal CDF
        sigma_equivalent = 1.4826 * mad
        
        threshold = median + n_sigma * sigma_equivalent
        return float(threshold)
    
    def _hybrid_threshold(
        self, 
        data: np.ndarray, 
        confidence: float
    ) -> float:
        """
        Hybrid approach: average of quantile and MAD methods.
        
        Args:
            data: Training scores
            confidence: Confidence level
            
        Returns:
            Average of quantile and MAD thresholds
            
        Notes:
            - Combines benefits of both methods
            - More stable than single method
            - Good default choice
        """
        quantile_thresh = self._quantile_threshold(data, confidence)
        mad_thresh = self._mad_threshold(data, n_sigma=3.0)
        
        # Average the two methods
        threshold = (quantile_thresh + mad_thresh) / 2.0
        
        logger.debug(
            f"Hybrid threshold: quantile={quantile_thresh:.3f}, "
            f"mad={mad_thresh:.3f}, avg={threshold:.3f}"
        )
        
        return float(threshold)
    
    def validate_threshold(
        self, 
        threshold: float, 
        data: np.ndarray
    ) -> Tuple[bool, str]:
        """
        Validate calculated threshold for reasonableness.
        
        Args:
            threshold: Calculated threshold value
            data: Training data used for calculation
            
        Returns:
            (is_valid, reason) tuple
            - is_valid: True if threshold passes all checks
            - reason: Explanation if invalid
            
        Checks:
            1. Threshold is positive
            2. Threshold is finite
            3. Threshold is above median (catches calculation errors)
            4. Threshold is below max (catches extreme outliers)
            5. Alert rate is reasonable (1-5% of training data)
        """
        # Check 1: Positive
        if threshold <= 0:
            return False, "Threshold must be positive"
        
        # Check 2: Finite
        if not np.isfinite(threshold):
            return False, "Threshold is not finite"
        
        # Check 3: Above median
        median = np.median(data)
        if threshold < median:
            return False, f"Threshold {threshold:.3f} below median {median:.3f}"
        
        # Check 4: Below max
        data_max = np.max(data)
        if threshold > data_max * 1.5:
            return False, f"Threshold {threshold:.3f} exceeds 1.5x max {data_max:.3f}"
        
        # Check 5: Alert rate
        alert_rate = np.mean(data >= threshold)
        if alert_rate > 0.10:  # More than 10% alerts
            return False, f"Alert rate {alert_rate:.1%} too high (>10%)"
        if alert_rate < 0.001:  # Less than 0.1% alerts
            return False, f"Alert rate {alert_rate:.1%} too low (<0.1%)"
        
        # All checks passed
        return True, f"Valid (alert_rate={alert_rate:.2%})"
    
    def calculate_warn_threshold(
        self,
        alert_threshold: float,
        method: str = 'fraction'
    ) -> float:
        """
        Calculate warning threshold based on alert threshold.
        
        Args:
            alert_threshold: Calculated alert threshold (e.g., 3.5)
            method: Calculation method:
                - 'fraction': warn = 0.5 * alert (default)
                - 'fixed': warn = 1.5 (hardcoded)
                
        Returns:
            Warning threshold value
            
        Notes:
            Warning threshold should trigger before alert threshold to provide
            early warning of degrading conditions.
        """
        if method == 'fraction':
            warn_threshold = alert_threshold * 0.5
        elif method == 'fixed':
            warn_threshold = 1.5
        else:
            raise ValueError(f"Unknown warn method: {method}")
            
        logger.debug(
            f"Warning threshold: {warn_threshold:.3f} "
            f"(alert={alert_threshold:.3f}, method={method})"
        )
        
        return float(warn_threshold)


def build_threshold_calculator_from_config(
    cfg: Dict[str, Any],
    baseline_contamination_verdict: str = "unknown",
) -> AdaptiveThresholdCalculator:
    """
    Build the adaptive-threshold calculator with verdict-aware filter policy.
    """
    adaptive_cfg = cfg.get("thresholds", {}).get("adaptive", {})
    filter_cfg = resolve_contamination_filter_policy(
        thresholds_cfg=cfg.get("thresholds", {}),
        baseline_contamination_verdict=baseline_contamination_verdict,
    )
    return AdaptiveThresholdCalculator(
        min_samples=int(adaptive_cfg.get("min_samples", 100)),
        contamination_filter_enabled=bool(filter_cfg.get("enabled", False)),
        contamination_filter_method=str(filter_cfg.get("method", "iterative_mad")),
        contamination_filter_z_threshold=float(filter_cfg.get("z_threshold", 4.0)),
    )


def calculate_thresholds_from_config(
    train_fused_z: Union[np.ndarray, pd.Series],
    cfg: dict,
    regime_labels: Optional[Union[np.ndarray, pd.Series]] = None,
    baseline_contamination_verdict: str = "unknown",
) -> Dict[str, Union[float, Dict[int, float]]]:
    """
    Convenience function to calculate thresholds from config dict.
    
    Args:
        train_fused_z: Training FusedZ scores
        cfg: Configuration dictionary (from ConfigDict)
        regime_labels: Optional regime assignments
        
    Returns:
        Dictionary with keys:
            - 'fused_alert_z': Alert threshold(s)
            - 'fused_warn_z': Warning threshold(s)
            - 'method': Method used
            - 'confidence': Confidence level
            
    Example:
        thresholds = calculate_thresholds_from_config(
            train_fused_z=train_scores,
            cfg=config_dict,
            regime_labels=regimes
        )
        alert_threshold = thresholds['fused_alert_z']
    """
    # Extract config parameters
    adaptive_cfg = cfg.get('thresholds', {}).get('adaptive', {})

    method = adaptive_cfg.get('method', 'quantile')
    confidence = adaptive_cfg.get('confidence', 0.997)
    fallback = adaptive_cfg.get('fallback_threshold', 3.0)
    
    # Calculate thresholds
    calc = build_threshold_calculator_from_config(
        cfg=cfg,
        baseline_contamination_verdict=baseline_contamination_verdict,
    )
    
    regime_input = regime_labels
    
    alert_threshold = calc.calculate_fused_threshold(
        train_fused_z=train_fused_z,
        method=method,
        confidence=confidence,
        regime_labels=regime_input,
        fallback_threshold=fallback
    )
    
    # Calculate warning threshold
    if isinstance(alert_threshold, dict):
        # Per-regime: calculate warning for each regime
        warn_threshold = {
            regime_id: calc.calculate_warn_threshold(thresh)
            for regime_id, thresh in alert_threshold.items()
        }
    else:
        # Global: single warning threshold
        warn_threshold = calc.calculate_warn_threshold(alert_threshold)
    
    return {
        'fused_alert_z': alert_threshold,
        'fused_warn_z': warn_threshold,
        'method': method,
        'confidence': confidence
    }


# =============================================================================
# P4.4: ADAPTIVE THRESHOLD ORCHESTRATION (moved from acm_main.py)
# =============================================================================

def calculate_and_persist_thresholds(
    fused_scores: np.ndarray,
    cfg: Dict[str, Any],
    equip_id: int,
    output_manager: Optional[Any],
    train_index: Optional[pd.Index] = None,
    regime_labels: Optional[np.ndarray] = None,
    regime_quality_ok: bool = False,
    baseline_contamination_verdict: str = "unknown",
) -> Dict[str, Any]:
    """
    Calculate adaptive thresholds and persist to SQL.
    
    Wrapper that orchestrates threshold calculation and SQL persistence.
    Updates cfg in-place with calculated threshold values for downstream use.
    
    Args:
        fused_scores: Array of fused z-scores to calculate thresholds from
        cfg: Configuration dictionary (updated in-place with threshold values)
        equip_id: Equipment ID for SQL persistence
        output_manager: OutputManager instance for writing to SQL
        train_index: Optional datetime index for train data (for metadata)
        regime_labels: Optional regime labels for per-regime thresholds
        regime_quality_ok: Whether regime clustering quality is acceptable
    
    Returns:
        Dictionary with threshold results including 'fused_alert_z', 'fused_warn_z', 'method', 'confidence'
    """
    import hashlib
    import json
    from core.observability import Console
    
    try:
        threshold_cfg = cfg.get("thresholds", {}).get("adaptive", {})
        use_regime_labels = regime_labels if regime_quality_ok and regime_labels is not None else None
        
        # Calculate thresholds
        threshold_results = calculate_thresholds_from_config(
            train_fused_z=fused_scores,
            cfg=cfg,
            regime_labels=use_regime_labels,
            baseline_contamination_verdict=baseline_contamination_verdict,
        )
        
        # Store in SQL via OutputManager if available
        if output_manager is not None and output_manager.sql_client is not None:
            config_sig = hashlib.md5(json.dumps(threshold_cfg, sort_keys=True).encode()).hexdigest()[:16]
            
            output_manager.write_threshold_metadata(
                equip_id=equip_id,
                threshold_type='fused_alert_z',
                threshold_value=threshold_results['fused_alert_z'],
                calculation_method=f"{threshold_results['method']}_{threshold_results['confidence']}",
                sample_count=len(fused_scores),
                train_start=train_index.min() if train_index is not None and len(train_index) > 0 else None,
                train_end=train_index.max() if train_index is not None and len(train_index) > 0 else None,
                config_signature=config_sig,
                notes=f"Auto-calculated from {len(fused_scores)} accumulated samples"
            )
            
            output_manager.write_threshold_metadata(
                equip_id=equip_id,
                threshold_type='fused_warn_z',
                threshold_value=threshold_results['fused_warn_z'],
                calculation_method=f"{threshold_results['method']}_{threshold_results['confidence']}",
                sample_count=len(fused_scores),
                train_start=train_index.min() if train_index is not None and len(train_index) > 0 else None,
                train_end=train_index.max() if train_index is not None and len(train_index) > 0 else None,
                config_signature=config_sig,
                notes=f"Auto-calculated warning threshold (50% of alert)"
            )
            
            # Update cfg to use adaptive thresholds in downstream modules
            is_per_regime = isinstance(threshold_results['fused_alert_z'], dict)
            if is_per_regime:
                # Store in cfg for regimes.update_health_labels() to use
                if "regimes" not in cfg:
                    cfg["regimes"] = {}
                if "health" not in cfg["regimes"]:
                    cfg["regimes"]["health"] = {}
                cfg["regimes"]["health"]["fused_alert_z_per_regime"] = threshold_results['fused_alert_z']
                cfg["regimes"]["health"]["fused_warn_z_per_regime"] = threshold_results['fused_warn_z']
            else:
                # Override static config values with adaptive ones
                if "regimes" not in cfg:
                    cfg["regimes"] = {}
                if "health" not in cfg["regimes"]:
                    cfg["regimes"]["health"] = {}
                cfg["regimes"]["health"]["fused_alert_z"] = threshold_results['fused_alert_z']
                cfg["regimes"]["health"]["fused_warn_z"] = threshold_results['fused_warn_z']
            
            # Consolidated threshold log
            if is_per_regime:
                regime_count = len(threshold_results['fused_alert_z']) if isinstance(threshold_results['fused_alert_z'], dict) else 0
                Console.info(f"Thresholds calculated: per_regime=True | regimes={regime_count} | samples={len(fused_scores)} | method={threshold_results.get('method')}", component="THRESHOLD")
            else:
                Console.info(f"Thresholds calculated: alert={threshold_results['fused_alert_z']:.3f} | warn={threshold_results['fused_warn_z']:.3f} | samples={len(fused_scores)} | method={threshold_results.get('method')}", component="THRESHOLD")
        else:
            Console.warn(f"SQL client unavailable - thresholds not persisted (om={'set' if output_manager else 'None'}, sql={'set' if getattr(output_manager, 'sql_client', None) else 'None'})", component="THRESHOLD")
        
        return threshold_results
        
    except Exception as threshold_e:
        import traceback
        from core.observability import Console
        Console.error(f"Adaptive threshold calculation failed: {threshold_e} | fallback=static | trace={traceback.format_exc()[:200]}", component="THRESHOLD",
                      equip_id=equip_id, error_type=type(threshold_e).__name__)
        return {}


def maybe_update_adaptive_thresholds(
    *,
    train_frame: pd.DataFrame,
    train_data: pd.DataFrame,
    cfg: Dict[str, Any],
    equip_id: int,
    output_manager: Optional[Any],
    coldstart_complete: bool,
    regime_quality_ok: bool,
    baseline_contamination_verdict: str = "unknown",
    logger: Any,
) -> bool:
    """
    Decide whether thresholds should be refreshed this run and persist if needed.

    Returns:
        True when thresholds were recalculated and persisted, otherwise False.
    """
    run_count = cfg.get("runtime", {}).get("run_count", 0)
    # Continuous threshold updates are part of normal runtime behavior.
    should_update = True

    if not should_update or "fused" not in train_frame.columns:
        return False

    train_fused_np = train_frame["fused"].to_numpy(copy=False)
    regime_labels_for_thresh = (
        train_data["regime_label"].to_numpy(copy=False)
        if "regime_label" in train_data.columns
        else None
    )

    calculate_and_persist_thresholds(
        fused_scores=train_fused_np,
        cfg=cfg,
        equip_id=equip_id,
        output_manager=output_manager,
        train_index=train_data.index,
        regime_labels=regime_labels_for_thresh,
        regime_quality_ok=regime_quality_ok,
        baseline_contamination_verdict=baseline_contamination_verdict,
    )
    cfg._thresholds_calculated = True
    logger.info(f"Threshold: updated at run {run_count}", component="THRESHOLD")
    return True

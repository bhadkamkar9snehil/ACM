"""
Detector Orchestrator Module

Provides unified interfaces for fitting, scoring, and calibrating all ACM detectors:
- AR1 (autoregressive residual)
- PCA-SPE/T2 (subspace projection)
- IForest (isolation forest)
- GMM (Gaussian mixture model)
- OMR (overall model residual)

Extracted from acm_main.py v11.2 to reduce main pipeline file size.

Author: Copilot
Date: January 2026
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from core.observability import Console
from core.ar1_detector import AR1Detector
from core.omr import OMRDetector
from core import correlation, outliers, fuse


def score_all_detectors(
    data: pd.DataFrame,
    ar1_detector: Optional[Any],
    pca_detector: Optional[Any],
    iforest_detector: Optional[Any],
    gmm_detector: Optional[Any],
    omr_detector: Optional[Any],
    ar1_enabled: bool = True,
    pca_enabled: bool = True,
    iforest_enabled: bool = True,
    gmm_enabled: bool = True,
    omr_enabled: bool = True,
    pca_cached: Optional[Tuple[np.ndarray, np.ndarray]] = None,
    return_omr_contributions: bool = True,
) -> Tuple[pd.DataFrame, Optional[Any]]:
    """
    Score all enabled detectors and return raw scores frame.
    
    Args:
        data: DataFrame with numeric features to score
        *_detector: Detector instances (or None if not fitted)
        *_enabled: Whether each detector is enabled
        pca_cached: Optional tuple of (pca_spe, pca_t2) cached scores
        return_omr_contributions: Whether to return OMR contributions
    
    Returns:
        Tuple of (frame with raw scores, omr_contributions or None)
    """
    frame = pd.DataFrame(index=data.index)
    omr_contributions_data = None
    scored_detectors = []
    
    # AR1 Detector
    if ar1_enabled and ar1_detector:
        res = ar1_detector.score(data)
        frame["ar1_raw"] = pd.Series(res, index=frame.index).fillna(0)
        scored_detectors.append("AR1")
    
    # PCA Subspace Detector
    if pca_enabled and pca_detector:
        if pca_cached is not None:
            pca_spe, pca_t2 = pca_cached
            scored_detectors.append("PCA(cached)")
        else:
            pca_spe, pca_t2 = pca_detector.score(data)
            scored_detectors.append("PCA")
        frame["pca_spe"] = pd.Series(pca_spe, index=frame.index).fillna(0)
        frame["pca_t2"] = pd.Series(pca_t2, index=frame.index).fillna(0)
    
    # Isolation Forest Detector
    if iforest_enabled and iforest_detector:
        res = iforest_detector.score(data)
        frame["iforest_raw"] = pd.Series(res, index=frame.index).fillna(0)
        scored_detectors.append("IForest")
    
    # GMM Detector
    if gmm_enabled and gmm_detector:
        res = gmm_detector.score(data)
        frame["gmm_raw"] = pd.Series(res, index=frame.index).fillna(0)
        scored_detectors.append("GMM")
    
    # OMR Detector
    if omr_enabled and omr_detector:
        if return_omr_contributions:
            omr_z, omr_contributions = omr_detector.score(data, return_contributions=True)
            omr_contributions_data = omr_contributions
        else:
            omr_z = omr_detector.score(data, return_contributions=False)
        frame["omr_raw"] = pd.Series(omr_z, index=frame.index).fillna(0)
        scored_detectors.append("OMR")
    
    # Consolidated scoring log
    if scored_detectors:
        Console.info(f"Scored {len(scored_detectors)} detectors: {', '.join(scored_detectors)} | samples={len(data)}", 
                    component="SCORE", samples=len(data), detectors=len(scored_detectors))
    
    return frame, omr_contributions_data


def calibrate_all_detectors(
    train_frame: pd.DataFrame,
    score_frame: pd.DataFrame,
    cal_q: float,
    self_tune_cfg: Dict[str, Any],
    fit_regimes: Optional[np.ndarray],
    transform_regimes: Optional[np.ndarray],
    omr_enabled: bool = True,
    cached_calibration_params: Optional[Dict[str, Any]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Fit calibrators on TRAIN data and transform SCORE data.

    v11.9.0: If cached_calibration_params is provided, rebuild calibrators from
    persisted params instead of refitting. This ensures scoring batches use the
    same normalization baseline as the training batch.

    Args:
        train_frame: DataFrame with raw scores from train data
        score_frame: DataFrame with raw scores from score data (will be modified)
        cal_q: Calibration quantile (e.g., 0.98)
        self_tune_cfg: Self-tuning configuration dict
        fit_regimes: Regime labels for training (or None)
        transform_regimes: Regime labels for scoring (or None)
        omr_enabled: Whether OMR detector is enabled
        cached_calibration_params: Persisted calibrator params from previous training

    Returns:
        Tuple of (score_frame with z-scores added, dict of calibrators)
    """
    calibrators = {}

    # Define calibration mappings: (raw_col, z_col, name)
    calibration_spec = [
        ("ar1_raw", "ar1_z", "ar1_z"),
        ("pca_spe", "pca_spe_z", "pca_spe_z"),
        ("pca_t2", "pca_t2_z", "pca_t2_z"),
        ("iforest_raw", "iforest_z", "iforest_z"),
        ("gmm_raw", "gmm_z", "gmm_z"),
    ]
    if omr_enabled:
        calibration_spec.append(("omr_raw", "omr_z", "omr_z"))

    # v11.9.0: Reuse cached calibration when available (scoring batches)
    if cached_calibration_params:
        restored = 0
        for raw_col, z_col, name in calibration_spec:
            if name in cached_calibration_params and raw_col in score_frame.columns:
                cal = fuse.ScoreCalibrator.from_dict(cached_calibration_params[name], name=name)
                score_frame[z_col] = cal.transform(
                    score_frame[raw_col].to_numpy(copy=False), regime_labels=transform_regimes
                )
                calibrators[name] = cal
                restored += 1
        if restored > 0:
            Console.info(
                f"Using cached calibration for {restored} detectors (training-anchored)",
                component="CAL"
            )
            return score_frame, calibrators

    for raw_col, z_col, name in calibration_spec:
        if raw_col in train_frame.columns and raw_col in score_frame.columns:
            cal = fuse.ScoreCalibrator(q=cal_q, self_tune_cfg=self_tune_cfg, name=name).fit(
                train_frame[raw_col].to_numpy(copy=False), regime_labels=fit_regimes
            )
            score_frame[z_col] = cal.transform(
                score_frame[raw_col].to_numpy(copy=False), regime_labels=transform_regimes
            )
            calibrators[name] = cal

    return score_frame, calibrators


def fit_all_detectors(
    train: pd.DataFrame,
    cfg: Dict[str, Any],
    ar1_enabled: bool,
    pca_enabled: bool,
    iforest_enabled: bool,
    gmm_enabled: bool,
    omr_enabled: bool,
    ar1_detector: Optional[Any] = None,
    pca_detector: Optional[Any] = None,
    iforest_detector: Optional[Any] = None,
    gmm_detector: Optional[Any] = None,
    omr_detector: Optional[Any] = None,
    output_manager: Optional[Any] = None,
    sql_client: Optional[Any] = None,
    run_id: Optional[str] = None,
    equip_id: int = 0,
    equip: str = "",
) -> Dict[str, Any]:
    """
    Fit all enabled detectors that haven't been loaded from cache.
    
    Args:
        train: Training data DataFrame
        cfg: Configuration dict
        ar1_enabled..omr_enabled: Whether each detector is enabled
        ar1_detector..omr_detector: Existing detectors (skip fitting if not None)
        output_manager: OutputManager for writing PCA metrics
        sql_client: SQL client for OMR diagnostics
        run_id, equip_id, equip: Identifiers for logging/SQL
    
    Returns:
        Dict with keys:
            - ar1_detector, pca_detector, iforest_detector, gmm_detector, omr_detector
            - pca_train_spe, pca_train_t2 (cached PCA scores)
            - fit_time_sec (total fitting time)
    
    v11.6.0 FIX #5: Training data subsampling
    ==========================================
    Large training datasets (26K+ rows) cause 2+ hour runs due to O(n²) operations
    in PCA/HDBSCAN. This function now subsamples to max_train_samples (default 10K)
    using stratified sampling that preserves time distribution.
    """
    # v11.6.0 FIX #5: Subsample training data to prevent 2+ hour runs
    max_train_samples = cfg.get("models", {}).get("max_train_samples", 10000)
    original_train_size = len(train)
    
    if len(train) > max_train_samples:
        # Use stratified sampling that preserves temporal distribution
        # Take evenly spaced samples to maintain time coverage
        sample_indices = np.linspace(0, len(train) - 1, max_train_samples, dtype=int)
        train = train.iloc[sample_indices].copy()
        Console.info(
            f"Subsampled training data: {original_train_size:,} -> {len(train):,} rows (max_train_samples={max_train_samples:,})",
            component="TRAIN", original=original_train_size, sampled=len(train)
        )
    
    result = {
        "ar1_detector": ar1_detector,
        "pca_detector": pca_detector,
        "iforest_detector": iforest_detector,
        "gmm_detector": gmm_detector,
        "omr_detector": omr_detector,
        "pca_train_spe": None,
        "pca_train_t2": None,
        "fit_time_sec": 0.0,
    }
    
    fit_start_time = time.perf_counter()
    fitted_detectors = []
    pca_components = 0
    
    # AR1 Detector
    if ar1_enabled and result["ar1_detector"] is None:
        ar1_cfg = cfg.get("models", {}).get("ar1", {}) or {}
        result["ar1_detector"] = AR1Detector(ar1_cfg=ar1_cfg).fit(train)
        fitted_detectors.append("AR1")
    
    # PCA Subspace Detector
    if pca_enabled and result["pca_detector"] is None:
        pca_cfg = cfg.get("models", {}).get("pca", {}) or {}
        result["pca_detector"] = correlation.PCASubspaceDetector(pca_cfg=pca_cfg).fit(train)
        pca_components = result["pca_detector"].pca.n_components_
        # Cache TRAIN raw PCA scores to eliminate double computation in calibration
        result["pca_train_spe"], result["pca_train_t2"] = result["pca_detector"].score(train)
        fitted_detectors.append(f"PCA({pca_components}c)")
        if output_manager is not None:
            output_manager.write_pca_metrics(pca_detector=result["pca_detector"], train=train)
    
    # Isolation Forest Detector
    if iforest_enabled and result["iforest_detector"] is None:
        if_cfg = cfg.get("models", {}).get("iforest", {}) or {}
        result["iforest_detector"] = outliers.IsolationForestDetector(if_cfg=if_cfg).fit(train)
        fitted_detectors.append(f"IForest({if_cfg.get('n_estimators', 100)})")
    
    # GMM Detector
    if gmm_enabled and result["gmm_detector"] is None:
        gmm_cfg = cfg.get("models", {}).get("gmm", {}) or {}
        gmm_cfg.setdefault("covariance_type", "full")
        gmm_cfg.setdefault("reg_covar", 1e-3)
        gmm_cfg.setdefault("n_init", 3)
        gmm_cfg.setdefault("random_state", 42)
        result["gmm_detector"] = outliers.GMMDetector(gmm_cfg=gmm_cfg).fit(train)
        fitted_detectors.append(f"GMM({gmm_cfg.get('n_components', 1)})")
    
    # OMR Detector
    if omr_enabled and result["omr_detector"] is None:
        omr_cfg = cfg.get("models", {}).get("omr", {}) or {}
        result["omr_detector"] = OMRDetector(cfg=omr_cfg).fit(train)
        # OMR-UPGRADE: Capture diagnostics and write to SQL
        if result["omr_detector"]._is_fitted and sql_client is not None:
            try:
                omr_diagnostics = result["omr_detector"].get_diagnostics()
                if omr_diagnostics.get("fitted") and output_manager is not None:
                    diag_df = pd.DataFrame([{
                        "RunID": run_id,
                        "EquipID": equip_id,
                        "ModelType": omr_diagnostics["model_type"],
                        "NComponents": omr_diagnostics["n_components"],
                        "TrainSamples": omr_diagnostics["n_samples"],
                        "TrainFeatures": omr_diagnostics["n_features"],
                        "TrainResidualStd": omr_diagnostics["train_residual_std"],
                        "CalibrationStatus": "VALID",
                        "FitTimestamp": pd.Timestamp.now()
                    }])
                    output_manager.write_dataframe(
                        diag_df,
                        "omr_diagnostics",
                        sql_table="ACM_OMR_Diagnostics",
                        add_created_at=True
                    )
            except Exception as e:
                Console.warn(f"OMR diagnostics write failed: {e}", component="OMR", equip=equip, error=str(e)[:200])
        fitted_detectors.append(f"OMR({train.shape[1]}f)")
    
    result["fit_time_sec"] = time.perf_counter() - fit_start_time
    
    # Consolidated fitting log
    if fitted_detectors:
        Console.info(f"Fitted {len(fitted_detectors)} detectors in {result['fit_time_sec']:.2f}s: {', '.join(fitted_detectors)} | samples={len(train)}", 
                    component="FIT", samples=len(train), detectors=len(fitted_detectors), fit_time=result['fit_time_sec'])
    
    return result


def get_detector_enable_flags(cfg: Dict[str, Any]) -> Dict[str, bool]:
    """
    Determine which detectors are enabled based on fusion weights.
    
    A detector is enabled if its weight in fusion.weights is > 0.
    
    Args:
        cfg: Configuration dict
    
    Returns:
        Dict with keys: ar1_enabled, pca_enabled, iforest_enabled, gmm_enabled, omr_enabled
    """
    fusion_cfg = (cfg or {}).get("fusion", {})
    fusion_weights = fusion_cfg.get("weights", {})
    
    return {
        "ar1_enabled": fusion_weights.get("ar1_z", 0.0) > 0,
        "pca_enabled": fusion_weights.get("pca_spe_z", 0.0) > 0 or fusion_weights.get("pca_t2_z", 0.0) > 0,
        "iforest_enabled": fusion_weights.get("iforest_z", 0.0) > 0,
        "gmm_enabled": fusion_weights.get("gmm_z", 0.0) > 0,
        "omr_enabled": fusion_weights.get("omr_z", 0.0) > 0,
    }


def reconcile_detector_flags_with_loaded_models(
    enable_flags: Dict[str, bool],
    ar1_detector: Optional[Any],
    pca_detector: Optional[Any],
    iforest_detector: Optional[Any],
    gmm_detector: Optional[Any],
    omr_detector: Optional[Any],
    equip: str = "",
) -> Dict[str, bool]:
    """
    Reconcile detector enable flags with actually loaded detectors.
    
    This fixes the audit finding where enable flags could be True but detector
    failed to load, causing downstream inconsistencies.
    
    Args:
        enable_flags: Original enable flags from config
        *_detector: Loaded detector instances (None if failed to load)
        equip: Equipment name for logging
    
    Returns:
        Updated enable flags where flag is False if detector is None
    """
    reconciled = enable_flags.copy()
    discrepancies = []
    
    # Check each detector - if enabled but None, disable it
    if reconciled.get("ar1_enabled") and ar1_detector is None:
        reconciled["ar1_enabled"] = False
        discrepancies.append("ar1")
    
    if reconciled.get("pca_enabled") and pca_detector is None:
        reconciled["pca_enabled"] = False
        discrepancies.append("pca")
    
    if reconciled.get("iforest_enabled") and iforest_detector is None:
        reconciled["iforest_enabled"] = False
        discrepancies.append("iforest")
    
    if reconciled.get("gmm_enabled") and gmm_detector is None:
        reconciled["gmm_enabled"] = False
        discrepancies.append("gmm")
    
    if reconciled.get("omr_enabled") and omr_detector is None:
        reconciled["omr_enabled"] = False
        discrepancies.append("omr")
    
    if discrepancies:
        Console.warn(
            f"Disabled {len(discrepancies)} detector(s) that failed to load: {discrepancies}",
            component="DETECTOR", equip=equip, disabled_detectors=discrepancies
        )
    
    return reconciled


def validate_model_feature_compatibility(
    model: Any,
    model_name: str,
    current_columns: list,
    cached_manifest: Optional[Dict[str, Any]],
    equip: str = "",
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a cached model is compatible with current feature columns.
    
    This addresses the audit finding where regime/detector models could be
    reused even when features changed (different columns, order, or count).
    
    Args:
        model: The loaded model object
        model_name: Name of the model (for logging)
        current_columns: Current feature column names
        cached_manifest: Cached model manifest with train_sensors
        equip: Equipment name for logging
    
    Returns:
        Tuple of (is_compatible, reason_if_incompatible)
    """
    if model is None:
        return False, "Model is None"
    
    if cached_manifest is None:
        # No manifest to validate against - allow but warn
        Console.warn(
            f"No manifest for {model_name} validation - assuming compatible",
            component="MODEL", equip=equip, model_name=model_name
        )
        return True, None
    
    # Get cached feature columns
    cached_columns = cached_manifest.get("train_sensors", [])
    
    if not cached_columns:
        # Manifest doesn't have sensor info - allow but warn
        Console.warn(
            f"No train_sensors in manifest for {model_name} - assuming compatible",
            component="MODEL", equip=equip, model_name=model_name
        )
        return True, None
    
    # Check 1: Column count must match
    if len(cached_columns) != len(current_columns):
        reason = f"Column count mismatch: cached={len(cached_columns)}, current={len(current_columns)}"
        return False, reason
    
    # Check 2: Column names must match (order-independent for robustness)
    cached_set = set(cached_columns)
    current_set = set(current_columns)
    
    if cached_set != current_set:
        missing_in_current = cached_set - current_set
        extra_in_current = current_set - cached_set
        
        reasons = []
        if missing_in_current:
            reasons.append(f"missing: {list(missing_in_current)[:3]}...")
        if extra_in_current:
            reasons.append(f"new: {list(extra_in_current)[:3]}...")
        
        reason = f"Column mismatch - {'; '.join(reasons)}"
        return False, reason
    
    # Check 3: For order-sensitive models, verify column order matches
    # This is critical for PCA, IForest, etc. where feature order matters
    if model_name in ["pca", "iforest", "gmm", "omr", "regime"]:
        if cached_columns != current_columns:
            # Find first differing position
            for i, (c, cur) in enumerate(zip(cached_columns, current_columns)):
                if c != cur:
                    reason = f"Column order mismatch at position {i}: cached='{c}', current='{cur}'"
                    return False, reason
    
    return True, None


def rebuild_detectors_from_cache(
    cached_models: Dict[str, Any],
    cached_manifest: Optional[Dict[str, Any]],
    cfg: Dict[str, Any],
    equip: str = "",
    current_columns: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Reconstruct detector objects from cached model data with feature validation.
    
    This helper consolidates the logic for rebuilding fitted detector objects
    from serialized cache data (new persistence system).
    
    AUDIT FIX: Now validates feature compatibility before loading regime models.
    
    Args:
        cached_models: Dictionary containing serialized model data
        cached_manifest: Manifest with metadata about cached models
        cfg: Configuration dictionary for model settings
        equip: Equipment name for logging context
        current_columns: Current feature columns for compatibility validation
    
    Returns:
        Dictionary containing:
            - ar1_detector, pca_detector, iforest_detector, gmm_detector, omr_detector
            - regime_model, regime_quality_ok
            - feature_medians (col_meds)
            - success: bool indicating if all critical models loaded
            - validation_warnings: list of any compatibility warnings
    """
    from core.regimes import RegimeModel
    
    result = {
        "ar1_detector": None,
        "pca_detector": None,
        "iforest_detector": None,
        "gmm_detector": None,
        "omr_detector": None,
        "regime_model": None,
        "regime_quality_ok": True,
        "feature_medians": None,
        "success": False,
        "validation_warnings": [],
    }
    
    try:
        # AR1 detector
        if "ar1_params" in cached_models and cached_models["ar1_params"]:
            ar1_detector = AR1Detector(ar1_cfg={})
            ar1_detector.phimap = cached_models["ar1_params"]["phimap"]
            ar1_detector.sdmap = cached_models["ar1_params"]["sdmap"]
            ar1_detector._is_fitted = True
            
            # Validate AR1 feature compatibility (phimap keys are column names)
            if current_columns:
                ar1_columns = list(ar1_detector.phimap.keys())
                if set(ar1_columns) != set(current_columns):
                    result["validation_warnings"].append(
                        f"AR1 column mismatch: cached={len(ar1_columns)}, current={len(current_columns)}"
                    )
                    Console.warn(
                        f"AR1 detector columns don't match current features - will retrain",
                        component="MODEL", equip=equip, 
                        cached_cols=len(ar1_columns), current_cols=len(current_columns)
                    )
                    ar1_detector = None
            
            result["ar1_detector"] = ar1_detector
        
        # PCA detector
        if "pca_model" in cached_models and cached_models["pca_model"]:
            pca_detector = correlation.PCASubspaceDetector(pca_cfg={})
            pca_detector.pca = cached_models["pca_model"]
            pca_detector._is_fitted = True
            
            # Validate PCA feature compatibility
            if current_columns and hasattr(pca_detector.pca, 'n_features_in_'):
                n_features_cached = pca_detector.pca.n_features_in_
                n_features_current = len(current_columns)
                if n_features_cached != n_features_current:
                    result["validation_warnings"].append(
                        f"PCA feature count mismatch: cached={n_features_cached}, current={n_features_current}"
                    )
                    Console.warn(
                        f"PCA detector feature count doesn't match - will retrain",
                        component="MODEL", equip=equip,
                        cached_features=n_features_cached, current_features=n_features_current
                    )
                    pca_detector = None
            
            result["pca_detector"] = pca_detector
        
        # IForest detector
        if "iforest_model" in cached_models and cached_models["iforest_model"]:
            iforest_detector = outliers.IsolationForestDetector(if_cfg={})
            iforest_detector.model = cached_models["iforest_model"]
            iforest_detector._is_fitted = True
            
            # Validate IForest feature compatibility
            if current_columns and hasattr(iforest_detector.model, 'n_features_in_'):
                n_features_cached = iforest_detector.model.n_features_in_
                n_features_current = len(current_columns)
                if n_features_cached != n_features_current:
                    result["validation_warnings"].append(
                        f"IForest feature count mismatch: cached={n_features_cached}, current={n_features_current}"
                    )
                    Console.warn(
                        f"IForest detector feature count doesn't match - will retrain",
                        component="MODEL", equip=equip,
                        cached_features=n_features_cached, current_features=n_features_current
                    )
                    iforest_detector = None
            
            result["iforest_detector"] = iforest_detector
        
        # GMM detector
        if "gmm_model" in cached_models and cached_models["gmm_model"]:
            gmm_detector = outliers.GMMDetector(gmm_cfg={})
            gmm_detector.model = cached_models["gmm_model"]
            gmm_detector._is_fitted = True
            
            # Validate GMM feature compatibility
            if current_columns and hasattr(gmm_detector.model, 'n_features_in_'):
                n_features_cached = gmm_detector.model.n_features_in_
                n_features_current = len(current_columns)
                if n_features_cached != n_features_current:
                    result["validation_warnings"].append(
                        f"GMM feature count mismatch: cached={n_features_cached}, current={n_features_current}"
                    )
                    Console.warn(
                        f"GMM detector feature count doesn't match - will retrain",
                        component="MODEL", equip=equip,
                        cached_features=n_features_cached, current_features=n_features_current
                    )
                    gmm_detector = None
            
            result["gmm_detector"] = gmm_detector
        
        # OMR detector
        if "omr_model" in cached_models and cached_models["omr_model"]:
            omr_cfg = (cfg.get("models", {}).get("omr", {}) or {})
            omr_detector = OMRDetector.from_dict(cached_models["omr_model"], cfg=omr_cfg)
            
            # Validate OMR feature compatibility
            if current_columns and omr_detector and hasattr(omr_detector, 'n_features_'):
                n_features_cached = omr_detector.n_features_
                n_features_current = len(current_columns)
                if n_features_cached != n_features_current:
                    result["validation_warnings"].append(
                        f"OMR feature count mismatch: cached={n_features_cached}, current={n_features_current}"
                    )
                    Console.warn(
                        f"OMR detector feature count doesn't match - will retrain",
                        component="MODEL", equip=equip,
                        cached_features=n_features_cached, current_features=n_features_current
                    )
                    omr_detector = None
            
            result["omr_detector"] = omr_detector
        
        # Regime model - AUDIT FIX: Enhanced validation
        # v11.6.1 FIX: cached_models["regime_model"] is already a serialized RegimeModel instance
        # Don't try to create a new one - just use the deserialized object directly
        if "regime_model" in cached_models and cached_models["regime_model"]:
            regime_model = cached_models["regime_model"]  # Already a RegimeModel (joblib deserialized)
            
            if cached_manifest:
                result["regime_quality_ok"] = cached_manifest.get("models", {}).get("regimes", {}).get("quality", {}).get("quality_ok", True)
            
            # AUDIT FIX: Validate regime model is not None
            if regime_model is None:
                Console.warn("Cached regime model is None; discarding.", component="REGIME", equip=equip)
            
            # AUDIT FIX: Validate regime model feature compatibility
            # Regime models use cluster centers which have n_features dimensions
            elif current_columns and hasattr(regime_model, 'cluster_centers_'):
                n_features_cached = regime_model.cluster_centers_.shape[1]
                # Regime basis might be a subset of all columns - get from manifest
                regime_n_features = cached_manifest.get("models", {}).get("regimes", {}).get("n_features")
                
                if regime_n_features and regime_n_features != n_features_cached:
                    # Manifest disagrees with model - corruption
                    result["validation_warnings"].append(
                        f"Regime model corruption: manifest says {regime_n_features} features but model has {n_features_cached}"
                    )
                    Console.warn(
                        f"Regime model feature mismatch with manifest - discarding",
                        component="REGIME", equip=equip
                    )
                    regime_model = None
            
            result["regime_model"] = regime_model
        
        # Feature medians
        if "feature_medians" in cached_models and cached_models["feature_medians"] is not None:
            feature_medians = cached_models["feature_medians"]
            
            # Validate feature medians match current columns
            if current_columns:
                median_columns = set(feature_medians.keys())
                current_set = set(current_columns)
                if median_columns != current_set:
                    # Some column mismatch - try to salvage what we can
                    missing = current_set - median_columns
                    if missing:
                        Console.info(
                            f"Feature medians missing {len(missing)} columns - will recompute",
                            component="MODEL", equip=equip, missing_cols=len(missing)
                        )
                        # Don't use partial medians - force recomputation
                        feature_medians = None
            
            result["feature_medians"] = feature_medians
        
        # Validate all critical models loaded
        if all([result["ar1_detector"], result["pca_detector"], result["iforest_detector"]]):
            result["success"] = True
            if result["validation_warnings"]:
                Console.info(
                    f"Model cache loaded with {len(result['validation_warnings'])} warnings",
                    component="MODEL", equip=equip, warning_count=len(result["validation_warnings"])
                )
        else:
            missing = []
            if not result["ar1_detector"]: missing.append("ar1")
            if not result["pca_detector"]: missing.append("pca")
            if not result["iforest_detector"]: missing.append("iforest")
            Console.warn(f"Incomplete model cache, missing: {missing}, retraining required", component="MODEL",
                         equip=equip, missing_models=missing)
            # Clear all on failure to ensure consistent state
            result["ar1_detector"] = None
            result["pca_detector"] = None
            result["iforest_detector"] = None
            result["gmm_detector"] = None
            result["omr_detector"] = None
            
    except Exception as e:
        import traceback
        Console.warn(f"Failed to reconstruct detectors: {e} | trace={traceback.format_exc()[:300]}", component="MODEL",
                     equip=equip, error_type=type(e).__name__)
        # Clear all on exception
        result["ar1_detector"] = None
        result["pca_detector"] = None
        result["iforest_detector"] = None
        result["gmm_detector"] = None
        result["omr_detector"] = None
    
    return result


def compute_stable_feature_hash(train: pd.DataFrame, equip: str = "") -> Optional[str]:
    """
    Compute a stable hash for training features.
    
    Hash is stable across pandas versions and OS by including:
    - Shape (rows x cols)
    - Sorted column dtypes
    - SHA256 of sorted column data bytes
    
    Args:
        train: Training DataFrame to hash
        equip: Equipment name for logging
        
    Returns:
        16-character hex hash string, or None if computation fails
    """
    import hashlib
    
    try:
        # Shape + dtypes for cross-platform consistency
        shape_str = f"{train.shape[0]}x{train.shape[1]}"
        dtype_str = "|".join(f"{col}:{train[col].dtype}" for col in sorted(train.columns))
        
        # Sort columns for deterministic hashing
        train_sorted = train[sorted(train.columns)]
        data_bytes = train_sorted.to_numpy(dtype=np.float64, copy=False).tobytes()
        data_hash = hashlib.sha256(data_bytes).hexdigest()
        
        # Combine all fingerprints
        combined = f"{shape_str}|{dtype_str}|{data_hash}"
        feature_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()[:16]
        return feature_hash
    except Exception as e:
        Console.warn(f"Hash computation failed: {e}", component="HASH",
                     equip=equip, error_type=type(e).__name__, error=str(e)[:200])
        return None

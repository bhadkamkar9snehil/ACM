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
from contextlib import nullcontext
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.schema_drift_manager import (
    SchemaDriftDecision,
    classify_feature_schema_drift,
    validate_cached_model_schema_drift,
)
from core.observability import Console
from core.ar1_detector import AR1Detector
from core.omr import OMRDetector
from core import correlation, outliers, fuse
from core.model_persistence import (
    align_current_features_to_cached_manifest,
    load_cached_models_with_validation,
    restore_detectors_from_runtime_cache,
    load_quality_regime_state_if_needed,
)


@dataclass
class DetectorInitState:
    """Typed return payload for detector initialization stage."""
    train: pd.DataFrame
    score: pd.DataFrame
    det_flags: Dict[str, bool]
    ar1_enabled: bool
    pca_enabled: bool
    iforest_enabled: bool
    gmm_enabled: bool
    omr_enabled: bool
    ar1_detector: Optional[Any]
    pca_detector: Optional[Any]
    iforest_detector: Optional[Any]
    gmm_detector: Optional[Any]
    omr_detector: Optional[Any]
    pca_train_spe: Optional[np.ndarray]
    pca_train_t2: Optional[np.ndarray]
    regime_model: Optional[Any]
    regime_state: Optional[Any]
    regime_state_version: int
    regime_loaded_from_state: bool
    col_meds: Optional[Any]
    cached_models: Optional[Dict[str, Any]]
    cached_manifest: Optional[Dict[str, Any]]
    cached_calibration_params: Optional[Dict[str, Any]]
    detectors_just_trained: bool
    use_cache: bool
    # Baseline contamination assessment (only set when detectors_just_trained=True)
    baseline_contamination_rate: float = 0.0   # fraction of train rows with raw fused z > alert_z
    baseline_sustained_block: float = 0.0       # longest sustained high-z run / total train rows
    baseline_contamination_verdict: str = "unknown"  # "unknown" | "ok" | "suspect" | "contaminated"
    schema_drift_decision: Optional[SchemaDriftDecision] = None

    def enabled_flags(self) -> Dict[str, bool]:
        """Return detector enabled-flag mapping."""
        return {
            "ar1_enabled": self.ar1_enabled,
            "pca_enabled": self.pca_enabled,
            "iforest_enabled": self.iforest_enabled,
            "gmm_enabled": self.gmm_enabled,
            "omr_enabled": self.omr_enabled,
        }

    def detector_payload(self) -> Dict[str, Any]:
        """Return detector objects plus cached PCA train outputs."""
        return {
            "ar1_detector": self.ar1_detector,
            "pca_detector": self.pca_detector,
            "iforest_detector": self.iforest_detector,
            "gmm_detector": self.gmm_detector,
            "omr_detector": self.omr_detector,
            "pca_train_spe": self.pca_train_spe,
            "pca_train_t2": self.pca_train_t2,
        }


def run_detector_initialization_stage(
    *,
    section_fn: Any,
    train: pd.DataFrame,
    score: pd.DataFrame,
    cfg: Dict[str, Any],
    meta: Any,
    detector_cache: Optional[Dict[str, Any]],
    output_manager: Any,
    sql_client: Any,
    run_id: Optional[str],
    equip_id: int,
    equip: str,
    fit_all_detectors_fn: Optional[Any] = None,
    load_and_rebuild_detectors_fn: Optional[Any] = None,
    restore_detectors_from_runtime_cache_fn: Optional[Any] = None,
    load_quality_regime_state_if_needed_fn: Optional[Any] = None,
    reconcile_detector_flags_fn: Optional[Any] = None,
    logger: Any = Console,
) -> DetectorInitState:
    """
    Execute detector initialization with stage-aware timing sections.
    """
    fit_fn = fit_all_detectors_fn or fit_all_detectors
    load_and_rebuild_fn = load_and_rebuild_detectors_fn or load_and_rebuild_detectors_from_sql_cache
    restore_from_runtime_fn = restore_detectors_from_runtime_cache_fn or restore_detectors_from_runtime_cache
    load_quality_regime_fn = load_quality_regime_state_if_needed_fn or load_quality_regime_state_if_needed
    reconcile_flags_fn = reconcile_detector_flags_fn or reconcile_detector_flags_with_loaded_models

    def _fit_with_section(**kwargs: Any) -> Dict[str, Any]:
        fit_ctx = section_fn("train.detector_fit") if section_fn is not None else nullcontext()
        with fit_ctx:
            return fit_fn(**kwargs)

    load_ctx = section_fn("models.load") if section_fn is not None else nullcontext()
    with load_ctx:
        return _initialize_detectors_for_run(
            train=train,
            score=score,
            cfg=cfg,
            meta=meta,
            detector_cache=detector_cache,
            output_manager=output_manager,
            sql_client=sql_client,
            run_id=run_id,
            equip_id=equip_id,
            equip=equip,
            load_and_rebuild_detectors_fn=load_and_rebuild_fn,
            restore_detectors_from_runtime_cache_fn=restore_from_runtime_fn,
            load_quality_regime_state_if_needed_fn=load_quality_regime_fn,
            fit_all_detectors_fn=_fit_with_section,
            reconcile_detector_flags_fn=reconcile_flags_fn,
            logger=logger,
        )


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


def assess_baseline_contamination(
    train: pd.DataFrame,
    ar1_detector: Optional[Any],
    pca_detector: Optional[Any],
    iforest_detector: Optional[Any],
    gmm_detector: Optional[Any],
    omr_detector: Optional[Any],
    ar1_enabled: bool,
    pca_enabled: bool,
    iforest_enabled: bool,
    gmm_enabled: bool,
    omr_enabled: bool,
    pca_train_spe: Optional[np.ndarray],
    pca_train_t2: Optional[np.ndarray],
    alert_z: float = 3.0,
    suspect_rate: float = 0.15,
    contaminated_rate: float = 0.40,
    sustained_block_threshold: float = 0.20,
    equip: str = "",
) -> Tuple[float, float, str]:
    """
    Assess whether the training window is contaminated with fault data.

    Scores the training data using the just-fitted detectors (raw z-scores,
    no calibration). If the model was trained on a fault period, it will
    produce elevated, temporally-clustered scores on its own training window.

    Healthy training data → low, noise-distributed scores (contamination_rate < 15%).
    Fault in training window → elevated scores concentrated in a time block.

    Design principle: the model self-reports the quality of its own training data.
    No external ground truth required.

    Args:
        train: Training DataFrame (DatetimeIndex)
        *_detector: Fitted detector instances
        *_enabled: Whether each detector is enabled
        pca_train_spe, pca_train_t2: Cached PCA scores on train (avoids re-scoring)
        alert_z: Z-score threshold above which a point is "anomalous" (default 3.0)
        suspect_rate: contamination_rate above which baseline is SUSPECT (default 0.15)
        contaminated_rate: contamination_rate above which baseline is CONTAMINATED (default 0.40)
        sustained_block_threshold: sustained_block above which contamination is confirmed (default 0.20)
        equip: Equipment name for logging

    Returns:
        Tuple of (contamination_rate, sustained_block, verdict)
            contamination_rate: fraction of train rows where mean raw z > alert_z
            sustained_block: longest run of consecutive high-z rows / total rows
            verdict: "ok" | "suspect" | "contaminated"
    """
    n = len(train)
    if n < 30:
        return 0.0, 0.0, "ok"

    # Collect raw z-scores from each enabled fitted detector.
    # Use cached PCA scores to avoid double computation.
    z_series: list[np.ndarray] = []

    if ar1_enabled and ar1_detector is not None:
        try:
            z_series.append(np.asarray(ar1_detector.score(train), dtype=float))
        except Exception:
            pass

    if pca_enabled and pca_detector is not None:
        # Only use cached PCA scores when they match the train frame length.
        # Cached scores come from the subsampled fit frame; if train was not
        # subsampled identically the lengths differ and column_stack will fail.
        _pca_cache_valid = (
            pca_train_spe is not None
            and pca_train_t2 is not None
            and len(pca_train_spe) == n
            and len(pca_train_t2) == n
        )
        if _pca_cache_valid:
            z_series.append(np.asarray(pca_train_spe, dtype=float))
            z_series.append(np.asarray(pca_train_t2, dtype=float))
        else:
            try:
                spe, t2 = pca_detector.score(train)
                z_series.append(np.asarray(spe, dtype=float))
                z_series.append(np.asarray(t2, dtype=float))
            except Exception:
                pass

    if iforest_enabled and iforest_detector is not None:
        try:
            z_series.append(np.asarray(iforest_detector.score(train), dtype=float))
        except Exception:
            pass

    if gmm_enabled and gmm_detector is not None:
        try:
            z_series.append(np.asarray(gmm_detector.score(train), dtype=float))
        except Exception:
            pass

    if omr_enabled and omr_detector is not None:
        try:
            z_series.append(np.asarray(omr_detector.score(train, return_contributions=False), dtype=float))
        except Exception:
            pass

    if not z_series:
        return 0.0, 0.0, "ok"

    # Normalize each detector's raw scores to z-scale using robust statistics
    # (median/MAD) before fusing. Raw scores from IForest, GMM, OMR, and AR1
    # are not z-distributed — comparing them directly against alert_z=3.0 produces
    # 100% false contamination on every fresh fit. Normalizing per-detector first
    # makes the threshold meaningful: healthy residuals on a good fit are centered
    # near 0 with SD~1; contaminated windows have a sustained cluster above the median.
    normalized: list[np.ndarray] = []
    for raw in z_series:
        arr = np.nan_to_num(np.asarray(raw, dtype=float), nan=0.0)
        med = float(np.median(arr))
        mad = float(np.median(np.abs(arr - med)))
        std_robust = mad * 1.4826
        if std_robust > 0:
            normalized.append((arr - med) / std_robust)
        else:
            # Constant signal — no variance, treat as zero z-score (not anomalous)
            normalized.append(np.zeros_like(arr))

    stacked = np.column_stack(normalized)
    fused = np.nanmean(stacked, axis=1)

    # Contamination rate: fraction of rows above alert_z
    high_mask = fused > alert_z
    contamination_rate = float(np.mean(high_mask))

    # Sustained block: longest consecutive run of high-z rows, normalised to window length.
    # Fault contamination produces a contiguous block; random noise produces scattered hits.
    max_run = 0
    current_run = 0
    for flag in high_mask:
        if flag:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 0
    sustained_block = max_run / n

    # Verdict
    if contamination_rate >= contaminated_rate and sustained_block >= sustained_block_threshold:
        verdict = "contaminated"
    elif contamination_rate >= suspect_rate:
        verdict = "suspect"
    else:
        verdict = "ok"

    Console.info(
        f"Baseline contamination assessment: rate={contamination_rate:.1%} "
        f"block={sustained_block:.1%} verdict={verdict} | train_rows={n}",
        component="BASELINE",
        equip=equip,
        contamination_rate=round(contamination_rate, 4),
        sustained_block=round(sustained_block, 4),
        verdict=verdict,
        train_rows=n,
    )

    if verdict == "contaminated":
        Console.warn(
            f"Training window appears contaminated with fault data "
            f"({contamination_rate:.0%} of rows elevated, {sustained_block:.0%} sustained block). "
            f"Model will NOT be promoted to LEARNING this batch. "
            f"Lifecycle will request more data for a cleaner baseline.",
            component="BASELINE",
            equip=equip,
        )
    elif verdict == "suspect":
        Console.warn(
            f"Training window may contain some fault data "
            f"({contamination_rate:.0%} elevated rows). "
            f"Model promoted with suspect flag -- calibration filter will be more aggressive.",
            component="BASELINE",
            equip=equip,
        )

    return contamination_rate, sustained_block, verdict


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
                    output_manager.write_sql_table(
                        table_name="ACM_OMR_Diagnostics",
                        df=diag_df,
                        artifact_name="omr_diagnostics",
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


def _initialize_detectors_for_run(
    *,
    train: pd.DataFrame,
    score: pd.DataFrame,
    cfg: Dict[str, Any],
    meta: Optional[Any],
    detector_cache: Optional[Dict[str, Any]],
    output_manager: Optional[Any],
    sql_client: Optional[Any],
    run_id: Optional[str],
    equip_id: int,
    equip: str,
    load_and_rebuild_detectors_fn: Any,
    restore_detectors_from_runtime_cache_fn: Any,
    load_quality_regime_state_if_needed_fn: Any,
    fit_all_detectors_fn: Any = fit_all_detectors,
    reconcile_detector_flags_fn: Any = None,
    logger: Any = Console,
) -> DetectorInitState:
    """
    Initialize detector runtime state for the current run.

    This helper centralizes the model phase decision flow:
    1. Resolve config enable flags
    2. Load from SQL cache or runtime cache when available
    3. Load regime state when no regime model is loaded
    4. Fit detectors when required detectors are missing
    5. Reconcile enable flags with loaded detectors
    6. Validate all enabled detectors exist
    """
    if reconcile_detector_flags_fn is None:
        raise ValueError("reconcile_detector_flags_fn is required for detector initialization")

    ar1_detector = pca_detector = iforest_detector = gmm_detector = omr_detector = None
    pca_train_spe = pca_train_t2 = None
    regime_model = None
    regime_state = None
    regime_state_version = 0
    regime_loaded_from_state = False
    col_meds = None
    cached_models = None
    cached_manifest = None
    cached_calibration_params = None
    schema_drift_decision: Optional[SchemaDriftDecision] = None

    det_flags = get_detector_enable_flags(cfg)
    ar1_enabled = det_flags["ar1_enabled"]
    pca_enabled = det_flags["pca_enabled"]
    iforest_enabled = det_flags["iforest_enabled"]
    gmm_enabled = det_flags["gmm_enabled"]
    omr_enabled = det_flags["omr_enabled"]

    is_coldstart_batch = (
        meta.get("is_coldstart_run", False)
        if isinstance(meta, dict)
        else getattr(meta, "is_coldstart_run", False)
    )
    use_cache = cfg.get("models", {}).get("use_cache", True) and not is_coldstart_batch

    if use_cache and detector_cache is None:
        cache_restore = load_and_rebuild_detectors_fn(
            train=train,
            score=score,
            equip=equip,
            sql_client=sql_client,
            equip_id=equip_id,
            cfg=cfg,
            logger=logger,
        )
        train = cache_restore["train"]
        score = cache_restore["score"]
        cached_models = cache_restore["cached_models"]
        cached_manifest = cache_restore["cached_manifest"]
        cached_calibration_params = cache_restore["cached_calibration_params"]
        schema_drift_decision = cache_restore.get("schema_drift_decision")
        ar1_detector = cache_restore["ar1_detector"]
        pca_detector = cache_restore["pca_detector"]
        iforest_detector = cache_restore["iforest_detector"]
        gmm_detector = cache_restore["gmm_detector"]
        omr_detector = cache_restore["omr_detector"]
        regime_model = cache_restore["regime_model"]
        col_meds = cache_restore["col_meds"]
    elif detector_cache:
        restored = restore_detectors_from_runtime_cache_fn(
            detector_cache=detector_cache,
            logger=logger,
        )
        ar1_detector = restored["ar1_detector"]
        pca_detector = restored["pca_detector"]
        iforest_detector = restored["iforest_detector"]
        gmm_detector = restored["gmm_detector"]
        omr_detector = restored["omr_detector"]
        regime_model = restored["regime_model"]

    regime_state_loaded, loaded_state_version, loaded_from_state = load_quality_regime_state_if_needed_fn(
        regime_model=regime_model,
        equip=equip,
        equip_id=equip_id,
        sql_client=sql_client,
        logger=logger,
    )
    if regime_state_loaded is not None:
        regime_state = regime_state_loaded
    if loaded_from_state:
        regime_state_version = loaded_state_version
        regime_loaded_from_state = True

    detectors_missing = not all(
        [
            ar1_detector or not ar1_enabled,
            pca_detector or not pca_enabled,
            iforest_detector or not iforest_enabled,
        ]
    )

    detectors_just_trained = False
    baseline_contamination_rate: float = 0.0
    baseline_sustained_block: float = 0.0
    baseline_contamination_verdict: str = "unknown"
    if detectors_missing:
        logger.info(
            "Required models missing or invalid - training fresh models",
            component="MODEL",
            equip=equip,
            reason="missing_detectors" if not cached_models else "validation_failed",
        )
        fit_result = fit_all_detectors_fn(
            train=train,
            cfg=cfg,
            **det_flags,
            output_manager=output_manager,
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
        pca_train_spe = fit_result["pca_train_spe"]
        pca_train_t2 = fit_result["pca_train_t2"]
        detectors_just_trained = True

        # Baseline contamination self-assessment: score the training window with
        # the just-fitted detectors to detect if training data contained faults.
        # A clean baseline → low scattered scores. A contaminated one → elevated,
        # temporally-clustered scores. This runs immediately post-fit at ~1-2s cost.
        _contamination_cfg = (cfg.get("models", {}) or {}).get("baseline_contamination", {}) or {}
        _alert_z = float(_contamination_cfg.get("alert_z", cfg.get("thresholds", {}).get("alert_z", 3.0)))
        _suspect_rate = float(_contamination_cfg.get("suspect_rate", 0.15))
        _contaminated_rate = float(_contamination_cfg.get("contaminated_rate", 0.40))
        _sustained_block_threshold = float(_contamination_cfg.get("sustained_block_threshold", 0.20))

        baseline_contamination_rate, baseline_sustained_block, baseline_contamination_verdict = (
            assess_baseline_contamination(
                train=train,
                ar1_detector=ar1_detector,
                pca_detector=pca_detector,
                iforest_detector=iforest_detector,
                gmm_detector=gmm_detector,
                omr_detector=omr_detector,
                ar1_enabled=det_flags.get("ar1_enabled", True),
                pca_enabled=det_flags.get("pca_enabled", True),
                iforest_enabled=det_flags.get("iforest_enabled", True),
                gmm_enabled=det_flags.get("gmm_enabled", True),
                omr_enabled=det_flags.get("omr_enabled", True),
                pca_train_spe=pca_train_spe,
                pca_train_t2=pca_train_t2,
                alert_z=_alert_z,
                suspect_rate=_suspect_rate,
                contaminated_rate=_contaminated_rate,
                sustained_block_threshold=_sustained_block_threshold,
                equip=equip,
            )
        )

    reconciled_flags = reconcile_detector_flags_fn(
        enable_flags=det_flags,
        ar1_detector=ar1_detector,
        pca_detector=pca_detector,
        iforest_detector=iforest_detector,
        gmm_detector=gmm_detector,
        omr_detector=omr_detector,
        equip=equip,
    )
    ar1_enabled = reconciled_flags["ar1_enabled"]
    pca_enabled = reconciled_flags["pca_enabled"]
    iforest_enabled = reconciled_flags["iforest_enabled"]
    gmm_enabled = reconciled_flags["gmm_enabled"]
    omr_enabled = reconciled_flags["omr_enabled"]

    missing = []
    if ar1_enabled and not ar1_detector:
        missing.append("ar1")
    if pca_enabled and not pca_detector:
        missing.append("pca")
    if iforest_enabled and not iforest_detector:
        missing.append("iforest")
    if gmm_enabled and not gmm_detector:
        missing.append("gmm")
    if omr_enabled and not omr_detector:
        missing.append("omr")
    if missing:
        logger.error(f"Detector initialization failed: {missing}", component="MODEL", equip=equip)
        raise RuntimeError(f"Required detector initialization failed: {missing}")

    return DetectorInitState(
        train=train,
        score=score,
        det_flags=det_flags,
        ar1_enabled=ar1_enabled,
        pca_enabled=pca_enabled,
        iforest_enabled=iforest_enabled,
        gmm_enabled=gmm_enabled,
        omr_enabled=omr_enabled,
        ar1_detector=ar1_detector,
        pca_detector=pca_detector,
        iforest_detector=iforest_detector,
        gmm_detector=gmm_detector,
        omr_detector=omr_detector,
        pca_train_spe=pca_train_spe,
        pca_train_t2=pca_train_t2,
        regime_model=regime_model,
        regime_state=regime_state,
        regime_state_version=regime_state_version,
        regime_loaded_from_state=regime_loaded_from_state,
        col_meds=col_meds,
        cached_models=cached_models,
        cached_manifest=cached_manifest,
        cached_calibration_params=cached_calibration_params,
        detectors_just_trained=detectors_just_trained,
        use_cache=use_cache,
        baseline_contamination_rate=baseline_contamination_rate,
        baseline_sustained_block=baseline_sustained_block,
        baseline_contamination_verdict=baseline_contamination_verdict,
        schema_drift_decision=schema_drift_decision,
    )


def load_and_rebuild_detectors_from_sql_cache(
    *,
    train: pd.DataFrame,
    score: pd.DataFrame,
    equip: str,
    sql_client: Optional[Any],
    equip_id: int,
    cfg: Dict[str, Any],
    logger: Any = Console,
) -> Dict[str, Any]:
    """
    Load cached models from SQL, align features, and rebuild detector instances.
    """
    current_sensors = list(train.columns) if hasattr(train, "columns") else []
    cached_models, cached_manifest = load_cached_models_with_validation(
        equip=equip,
        sql_client=sql_client,
        equip_id=equip_id,
        cfg=cfg,
        train_columns=current_sensors,
    )
    schema_drift_decision = classify_feature_schema_drift(current_sensors, cached_manifest)

    if cached_models:
        train, score, current_sensors, cache_compatible = align_current_features_to_cached_manifest(
            train=train,
            score=score,
            cached_manifest=cached_manifest,
            equip=equip,
            logger=logger,
        )
        if not cache_compatible:
            cached_models = None
            cached_manifest = None

    ar1_detector = pca_detector = iforest_detector = gmm_detector = omr_detector = None
    regime_model = None
    col_meds = None
    cached_calibration_params = None

    if cached_models:
        rebuild_result = rebuild_detectors_from_cache(
            cached_models=cached_models,
            cached_manifest=cached_manifest,
            cfg=cfg,
            equip=equip,
            current_columns=current_sensors,
        )
        ar1_detector = rebuild_result["ar1_detector"]
        pca_detector = rebuild_result["pca_detector"]
        iforest_detector = rebuild_result["iforest_detector"]
        gmm_detector = rebuild_result["gmm_detector"]
        omr_detector = rebuild_result["omr_detector"]
        regime_model = rebuild_result.get("regime_model")
        col_meds = rebuild_result.get("feature_medians")

        cached_calibration_params = cached_models.get("calibration_params")
        if cached_calibration_params:
            logger.info(
                f"Loaded cached calibration params ({len(cached_calibration_params)} detectors)",
                component="CAL",
            )

        if rebuild_result.get("validation_warnings"):
            for warn in rebuild_result["validation_warnings"]:
                logger.info(f"Model validation: {warn}", component="MODEL", equip=equip)

    return {
        "train": train,
        "score": score,
        "current_sensors": current_sensors,
        "cached_models": cached_models,
        "cached_manifest": cached_manifest,
        "cached_calibration_params": cached_calibration_params,
        "schema_drift_decision": schema_drift_decision,
        "ar1_detector": ar1_detector,
        "pca_detector": pca_detector,
        "iforest_detector": iforest_detector,
        "gmm_detector": gmm_detector,
        "omr_detector": omr_detector,
        "regime_model": regime_model,
        "col_meds": col_meds,
    }


def load_cached_regime_preview_from_sql_cache(
    *,
    train: pd.DataFrame,
    score: pd.DataFrame,
    equip: str,
    sql_client: Optional[Any],
    equip_id: int,
    cfg: Dict[str, Any],
    logger: Any = Console,
) -> Dict[str, Any]:
    """
    Load the minimum cached regime preview payload needed for validation gating.

    This intentionally avoids deserializing the full detector set. It loads only
    the cached regime model plus manifest metadata, aligns the feature frame to
    the cached manifest when possible, and restores persisted regime state if it
    is needed for preview.
    """
    current_sensors = list(train.columns) if hasattr(train, "columns") else []
    cached_models, cached_manifest = load_cached_models_with_validation(
        equip=equip,
        sql_client=sql_client,
        equip_id=equip_id,
        cfg=cfg,
        train_columns=current_sensors,
        model_types=["regime_model"],
    )
    schema_drift_decision = classify_feature_schema_drift(current_sensors, cached_manifest)

    if cached_models:
        train, score, current_sensors, cache_compatible = align_current_features_to_cached_manifest(
            train=train,
            score=score,
            cached_manifest=cached_manifest,
            equip=equip,
            logger=logger,
        )
        if not cache_compatible:
            cached_models = None
            cached_manifest = None

    regime_model = cached_models.get("regime_model") if cached_models else None
    regime_state, regime_state_version, regime_loaded_from_state = load_quality_regime_state_if_needed(
        regime_model=regime_model,
        equip=equip,
        equip_id=equip_id,
        sql_client=sql_client,
        logger=logger,
    )

    return {
        "train": train,
        "score": score,
        "current_sensors": current_sensors,
        "cached_manifest": cached_manifest,
        "schema_drift_decision": schema_drift_decision,
        "regime_model": regime_model,
        "regime_state": regime_state,
        "regime_state_version": regime_state_version,
        "regime_loaded_from_state": regime_loaded_from_state,
    }


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
    ok, reason, _ = validate_cached_model_schema_drift(
        model,
        model_name,
        current_columns,
        cached_manifest,
    )
    return ok, reason


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
            pca_data = cached_models["pca_model"]
            # v11.7.1 FIX: Handle new dict format (with keep_cols, scaler, col_medians)
            # and legacy format (raw sklearn PCA object)
            if isinstance(pca_data, dict):
                pca_detector.pca = pca_data.get("pca")
                pca_detector.keep_cols = pca_data.get("keep_cols", [])
                if pca_data.get("scaler") is not None:
                    pca_detector.scaler = pca_data["scaler"]
                if pca_data.get("col_medians") is not None:
                    pca_detector.col_medians = pca_data["col_medians"]
            else:
                # Legacy format: raw sklearn PCA object
                pca_detector.pca = pca_data
            pca_detector._is_fitted = True
            
            # Validate PCA feature compatibility
            # v11.7.1 FIX: PCA internally filters constant/low-variance columns via keep_cols,
            # so pca.n_features_in_ reflects the post-filtering count (e.g., 786) while
            # current_columns has the pre-filtering count (e.g., 790). PCA.score() already
            # handles column selection via keep_cols, so we validate against keep_cols
            # membership rather than raw n_features_in_ count.
            if current_columns and hasattr(pca_detector, 'keep_cols') and pca_detector.keep_cols:
                missing_keep = set(pca_detector.keep_cols) - set(current_columns)
                if missing_keep:
                    result["validation_warnings"].append(
                        f"PCA keep_cols missing from current features: {len(missing_keep)} columns"
                    )
                    Console.warn(
                        f"PCA detector keep_cols not in current features - will retrain",
                        component="MODEL", equip=equip,
                        missing_count=len(missing_keep), missing_cols=list(missing_keep)[:5]
                    )
                    pca_detector = None
            elif current_columns and hasattr(pca_detector.pca, 'n_features_in_'):
                # Fallback: no keep_cols available (legacy cache), use n_features_in_
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
            gmm_data = cached_models["gmm_model"]
            # v11.7.1 FIX: Handle new dict format (with _var_mask, _columns_, scaler)
            # and legacy format (raw sklearn GaussianMixture object)
            if isinstance(gmm_data, dict):
                gmm_detector.model = gmm_data.get("model")
                gmm_detector._var_mask = gmm_data.get("_var_mask")
                gmm_detector._columns_ = gmm_data.get("_columns_")
                if gmm_data.get("scaler") is not None:
                    gmm_detector.scaler = gmm_data["scaler"]
                gmm_detector._score_mu_ = gmm_data.get("_score_mu_")
                gmm_detector._score_sd_ = gmm_data.get("_score_sd_")
            else:
                # Legacy format: raw sklearn GaussianMixture object
                gmm_detector.model = gmm_data
            gmm_detector._is_fitted = True
            
            # Validate GMM feature compatibility
            # v11.7.1 FIX: GMM internally drops constant features via _var_mask during fit(),
            # so model.n_features_in_ reflects the post-filtering count (e.g., 786) while
            # current_columns has the pre-filtering count (e.g., 790). GMM.score() already
            # handles column selection via _columns_ and _var_mask, so we validate against
            # _columns_ membership rather than raw n_features_in_ count.
            if current_columns and hasattr(gmm_detector, '_columns_') and gmm_detector._columns_:
                missing_cols = set(gmm_detector._columns_) - set(current_columns)
                if missing_cols:
                    result["validation_warnings"].append(
                        f"GMM _columns_ missing from current features: {len(missing_cols)} columns"
                    )
                    Console.warn(
                        f"GMM detector columns not in current features - will retrain",
                        component="MODEL", equip=equip,
                        missing_count=len(missing_cols), missing_cols=list(missing_cols)[:5]
                    )
                    gmm_detector = None
            elif current_columns and hasattr(gmm_detector.model, 'n_features_in_'):
                # Fallback: no _columns_ available (legacy cache), use n_features_in_
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

            # NOTE: Do NOT propagate regime_quality_ok from the cached manifest.
            # The manifest quality flag is set at fit time and reflects a past batch.
            # Propagating it here caused scoring batches to inherit quality_ok=False from
            # the previous run, forcing all score points to "unknown" and blocking health
            # labeling every batch. The pipeline default (regime_quality_ok=True) holds
            # until the live regime labeling phase (label_regimes / discover_regimes)
            # sets it correctly from current data.
            
            # AUDIT FIX: Validate regime model is not None
            if regime_model is None:
                Console.warn(
                    "Cached regime model is None. Regime clustering will be re-fit this batch.",
                    component="REGIME",
                    equip=equip,
                )
            
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
                        f"Regime model discarded: manifest expects {regime_n_features} features "
                        f"but cached model has {n_features_cached}. "
                        "Regime clustering will be re-fit this batch.",
                        component="REGIME",
                        equip=equip,
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
                    f"Model cache loaded with {len(result['validation_warnings'])} validation warning(s): "
                    f"{result['validation_warnings']}",
                    component="MODEL", equip=equip, warning_count=len(result["validation_warnings"])
                )
        else:
            missing = []
            if not result["ar1_detector"]: missing.append("ar1")
            if not result["pca_detector"]: missing.append("pca")
            if not result["iforest_detector"]: missing.append("iforest")
            Console.warn(
                f"Cached model cache is incomplete (missing: {missing}). "
                "All detectors will be retrained from scratch this batch.",
                component="MODEL",
                equip=equip,
                missing_models=missing,
            )
            # Clear all on failure to ensure consistent state
            result["ar1_detector"] = None
            result["pca_detector"] = None
            result["iforest_detector"] = None
            result["gmm_detector"] = None
            result["omr_detector"] = None
            
    except Exception as e:
        import traceback
        Console.warn(
            f"Failed to reconstruct detectors from cache: {e}. "
            "All detectors will be retrained from scratch this batch.",
            component="MODEL",
            equip=equip,
            error_type=type(e).__name__,
            trace=traceback.format_exc()[:300],
        )
        # Clear all on exception
        result["ar1_detector"] = None
        result["pca_detector"] = None
        result["iforest_detector"] = None
        result["gmm_detector"] = None
        result["omr_detector"] = None
    
    return result

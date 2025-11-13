# core/fuse.py
"""
Score fusion, calibration (global or per-regime), and episode detection.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple
from utils.logger import Console

import numpy as np
import pandas as pd
from scipy.stats import pearsonr  # type: ignore
from sklearn.metrics import average_precision_score, roc_curve  # type: ignore


def tune_detector_weights(
    streams: Dict[str, np.ndarray],
    fused: np.ndarray,
    current_weights: Dict[str, float],
    cfg: Optional[Dict[str, Any]] = None,
    episodes_df: Optional[pd.DataFrame] = None,
    fused_index: Optional[pd.Index] = None,
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """
    FUSE-07/08/09: Auto-tune detector weights using episode separability metrics.
    
    Improvements over correlation-based tuning:
    1. FUSE-07: Uses episode detection quality (NOT circular correlation to fused)
    2. FUSE-08: Proportional sample check: max(10, 0.1*len)
    3. FUSE-09: Configurable softmax parameters (temperature, min_weight, detector_priors)
    
    Strategy:
    - Split data into train/validation folds
    - For each detector, compute episode separability metrics:
      * Defect episode detection rate (% of known defects captured)
      * False positive rate (% of normal data flagged)
      * Mean separation (difference between defect and normal z-scores)
    - Convert metrics to weights using configurable softmax with priors
    - Blend with existing weights using learning rate
    
    Args:
        streams: Dict of detector z-scores (e.g., {"pca_spe_z": array, "ar1_z": array})
    fused: Current fused z-score array (used only for validation splits, NOT for correlation)
        current_weights: Existing weights from config or previous run
        cfg: Configuration dict with tuning parameters
    episodes_df: Optional DataFrame with detected episodes for validation/labeling
    fused_index: Optional DatetimeIndex aligned to `fused` for episode window labeling
        
    Returns:
        Tuple of (tuned_weights, diagnostics)
    """
    tune_cfg = (cfg or {}).get("fusion", {}).get("auto_tune", {}) if cfg else {}
    enabled = tune_cfg.get("enabled", False)
    
    if not enabled:
        return current_weights, {"enabled": False, "reason": "auto_tune.enabled=False in config"}
    
    # FUSE-09: Configurable parameters
    learning_rate = float(tune_cfg.get("learning_rate", 0.3))
    min_weight = float(tune_cfg.get("min_weight", 0.05))
    temperature = float(tune_cfg.get("temperature", 2.0))
    detector_priors = tune_cfg.get("detector_priors", {})  # Dict[str, float] for per-detector biases

    # ANA-02: Enforce episode_separability as default and log requested method
    requested_method_raw = tune_cfg.get("method", "episode_separability")
    requested_method = str(requested_method_raw).strip().lower()
    valid_methods = {"episode_separability", "correlation"}
    method_fallback_reason: Optional[str] = None
    if requested_method not in valid_methods:
        Console.warn(f"[TUNE] Unknown tuning method '{requested_method_raw}', defaulting to episode_separability")
        tuning_method = "episode_separability"
        method_fallback_reason = "unknown_method"
    else:
        tuning_method = requested_method
    
    diagnostics = {
        "enabled": True,
        "method": tuning_method,
        "requested_method": requested_method,
        "learning_rate": learning_rate,
        "temperature": temperature,
        "min_weight": min_weight,
        "detector_priors": dict(detector_priors),
        "detector_metrics": {},
        "config_weights": dict(current_weights),  # ANA-01: Capture original config weights
        "raw_weights": {},
        "tuned_weights": {},
        "present_detectors": sorted(list(streams.keys()))  # ANA-03: Track which detectors were available
    }

    fused_signal = np.asarray(fused, dtype=np.float32).reshape(-1)
    n_total = len(fused_signal)
    if n_total == 0:
        diagnostics["reason"] = "empty_fused_signal"
        return current_weights, diagnostics

    min_samples_required = max(10, int(0.1 * n_total))

    if method_fallback_reason:
        diagnostics["fallback_reason"] = method_fallback_reason

    # Construct binary labels from episode windows when available.
    labels: Optional[np.ndarray] = None
    if episodes_df is not None and not episodes_df.empty:
        if fused_index is None or len(fused_index) != n_total:
            Console.warn("[TUNE] Episodes provided but fused_index missing or misaligned; skipping PR-AUC labeling")
        else:
            try:
                fused_dt_index = pd.DatetimeIndex(fused_index)
            except Exception:
                fused_dt_index = pd.to_datetime(fused_index)

            positive_mask = np.zeros(n_total, dtype=bool)
            for _, episode_row in episodes_df.iterrows():
                start_ts = pd.to_datetime(episode_row.get("start_ts"), errors="coerce")
                end_ts = pd.to_datetime(episode_row.get("end_ts"), errors="coerce")
                if pd.isna(start_ts) or pd.isna(end_ts):
                    continue
                if end_ts < fused_dt_index[0] or start_ts > fused_dt_index[-1]:
                    continue
                window_mask = (fused_dt_index >= start_ts) & (fused_dt_index <= end_ts)
                if window_mask.any():
                    positive_mask |= window_mask

            diagnostics["label_source"] = {
                "label_type": "episodes_window",
                "episodes_count": int(len(episodes_df)),
                "positive_samples": int(positive_mask.sum()),
                "negative_samples": int(n_total - positive_mask.sum())
            }

            if positive_mask.any():
                labels = positive_mask.astype(np.int8)
            else:
                diagnostics["label_source"]["warning"] = "no_samples_marked_positive"

    if "label_source" not in diagnostics:
        diagnostics["label_source"] = {
            "label_type": "unavailable",
            "episodes_count": int(len(episodes_df)) if episodes_df is not None else 0
        }

    diagnostics["primary_metric"] = "pr_auc"

    if tuning_method == "episode_separability":
        quality_scores: Dict[str, float] = {}

        for detector_name, detector_signal in streams.items():
            det_diag: Dict[str, Any] = {}
            try:
                mask = np.isfinite(detector_signal)
                n_valid = int(np.sum(mask))
                det_diag["n_samples"] = n_valid

                if n_valid < min_samples_required:
                    Console.warn(f"[TUNE] {detector_name}: under-sampled ({n_valid}/{min_samples_required}) - using prior")
                    prior = float(detector_priors.get(detector_name, 1.0 / max(len(streams), 1)))
                    fallback_score = prior
                    quality_scores[detector_name] = fallback_score
                    det_diag.update({
                        "status": "under_sampled",
                        "metric_type": "prior_only",
                        "metric_value": 0.0,
                        "prior": prior,
                        "final_score": float(fallback_score)
                    })
                    diagnostics["detector_metrics"][detector_name] = det_diag
                    continue

                det_clean = detector_signal[mask].astype(np.float64)

                # Degenerate signal guards
                if np.allclose(det_clean, 0.0, atol=1e-6):
                    Console.warn(f"[TUNE] {detector_name}: all zeros - limited separability")
                    prior = float(detector_priors.get(detector_name, 1.0))
                    fallback_score = prior * 0.01
                    quality_scores[detector_name] = fallback_score
                    det_diag.update({
                        "status": "degenerate_zeros",
                        "metric_type": "prior_only",
                        "metric_value": 0.0,
                        "prior": prior,
                        "final_score": float(fallback_score)
                    })
                    diagnostics["detector_metrics"][detector_name] = det_diag
                    continue

                finite_signal = det_clean[np.abs(det_clean) > 1e-6]
                if finite_signal.size > 0 and np.unique(np.sign(finite_signal)).size == 1:
                    Console.warn(f"[TUNE] {detector_name}: all same sign - limited separability")
                    prior = float(detector_priors.get(detector_name, 1.0))
                    fallback_score = prior * 0.1
                    quality_scores[detector_name] = fallback_score
                    det_diag.update({
                        "status": "degenerate_same_sign",
                        "metric_type": "prior_only",
                        "metric_value": 0.0,
                        "prior": prior,
                        "final_score": float(fallback_score)
                    })
                    diagnostics["detector_metrics"][detector_name] = det_diag
                    continue

                metric_type: Optional[str] = None
                metric_value: Optional[float] = None
                metric_details: Dict[str, Any] = {}

                if labels is not None:
                    labels_clean = labels[mask]
                    pos_valid = int(labels_clean.sum())
                    neg_valid = int(len(labels_clean) - pos_valid)
                    det_diag["positive_samples"] = pos_valid
                    det_diag["negative_samples"] = neg_valid

                    if pos_valid > 0 and neg_valid > 0:
                        try:
                            pr_auc = float(average_precision_score(labels_clean, det_clean))
                            if np.isfinite(pr_auc):
                                metric_type = "pr_auc"
                                metric_value = float(np.clip(pr_auc, 0.0, 1.0))
                        except Exception as pr_err:
                            det_diag["pr_auc_error"] = str(pr_err)

                        if metric_value is None:
                            try:
                                fpr, tpr, thresholds = roc_curve(labels_clean, det_clean)
                                if tpr.size:
                                    youden = tpr - fpr
                                    if not np.all(np.isnan(youden)):
                                        idx_best = int(np.nanargmax(youden))
                                        metric_type = "youden_j"
                                        metric_value = float(np.clip(youden[idx_best], 0.0, 1.0))
                                        metric_details = {
                                            "best_threshold": float(thresholds[idx_best]),
                                            "tpr": float(tpr[idx_best]),
                                            "fpr": float(fpr[idx_best])
                                        }
                            except Exception as roc_err:
                                det_diag["youden_error"] = str(roc_err)
                    else:
                        det_diag["status"] = "imbalanced_labels"
                else:
                    det_diag["status"] = det_diag.get("status", "no_labels")

                if metric_value is None or not np.isfinite(metric_value):
                    metric_value = 0.0
                    metric_type = metric_type or ("no_labels" if labels is None else "insufficient_data")

                prior = float(detector_priors.get(detector_name, 1.0))
                final_score = float(max(metric_value, 0.0)) * prior
                if final_score <= 0:
                    final_score = max(prior * 1e-3, 1e-6)

                quality_scores[detector_name] = final_score
                det_diag.setdefault("status", "ok")
                det_diag.update({
                    "metric_type": metric_type,
                    "metric_value": float(metric_value),
                    "prior": prior,
                    "final_score": float(final_score)
                })
                det_diag.update(metric_details)
                diagnostics["detector_metrics"][detector_name] = det_diag

            except Exception as e:
                Console.warn(f"[TUNE] {detector_name}: metric calculation failed - {e}")
                prior = float(detector_priors.get(detector_name, 0.1))
                fallback_score = prior
                quality_scores[detector_name] = fallback_score
                diagnostics["detector_metrics"][detector_name] = {
                    "status": "error",
                    "error": str(e),
                    "metric_type": "prior_only",
                    "metric_value": 0.0,
                    "prior": prior,
                    "final_score": float(fallback_score)
                }

        if not quality_scores:
            diagnostics["reason"] = "no_valid_quality_scores"
            return current_weights, diagnostics

        score_array = np.array(list(quality_scores.values()), dtype=np.float64)
        exp_scores = np.exp(score_array / temperature)
        softmax_weights = exp_scores / np.sum(exp_scores)

        raw_weights = {}
        for i, detector_name in enumerate(quality_scores.keys()):
            weight_val = float(softmax_weights[i])
            raw_weights[detector_name] = weight_val
            diagnostics["raw_weights"][detector_name] = weight_val
    
    else:
        diagnostics["primary_metric"] = "abs_correlation"
        # Fallback: correlation-based tuning (LEGACY - circular but retained for compatibility)
        Console.warn("[TUNE] Using legacy correlation-based tuning (circular dependency)")
        correlations = {}
        
        for detector_name, detector_signal in streams.items():
            try:
                mask = np.isfinite(detector_signal) & np.isfinite(fused_signal)
                n_valid = int(np.sum(mask))
                
                if n_valid < min_samples_required:
                    Console.warn(f"[TUNE] {detector_name}: under-sampled ({n_valid}/{min_samples_required})")
                    correlations[detector_name] = 0.0
                    diagnostics["detector_metrics"][detector_name] = {
                        "n_samples": n_valid,
                        "status": "under_sampled",
                        "metric_type": "abs_correlation",
                        "metric_value": 0.0
                    }
                    continue
                
                det_clean = detector_signal[mask]
                fused_clean = fused_signal[mask]
                
                corr, p_value = pearsonr(det_clean, fused_clean)
                correlations[detector_name] = abs(corr) if np.isfinite(corr) else 0.0
                
                diagnostics["detector_metrics"][detector_name] = {
                    "pearson_r": float(corr),
                    "abs_r": float(abs(corr)),
                    "p_value": float(p_value),
                    "n_samples": n_valid,
                    "status": "ok",
                    "metric_type": "abs_correlation",
                    "metric_value": float(abs(corr))
                }
            except Exception as e:
                Console.warn(f"[TUNE] {detector_name}: correlation failed - {e}")
                correlations[detector_name] = 0.0
                diagnostics["detector_metrics"][detector_name] = {
                    "status": "error",
                    "error": str(e),
                    "metric_type": "abs_correlation",
                    "metric_value": 0.0
                }
        
        if not correlations:
            return current_weights, {**diagnostics, "reason": "no_valid_correlations"}
        
        corr_array = np.array(list(correlations.values()))
        exp_corr = np.exp(corr_array / temperature)
        softmax_weights = exp_corr / np.sum(exp_corr)
        
        raw_weights = {}
        for i, detector_name in enumerate(correlations.keys()):
            raw_weights[detector_name] = float(softmax_weights[i])
            diagnostics["raw_weights"][detector_name] = float(softmax_weights[i])
    
    # ANA-01: Capture pre_tune_weights before any modifications
    diagnostics["pre_tune_weights"] = dict(current_weights)
    
    # Blend with existing weights using learning rate
    tuned_weights = {}
    for detector_name in streams.keys():
        old_weight = current_weights.get(detector_name, 0.0)
        new_weight = raw_weights.get(detector_name, 0.0)
        
        # Exponential moving average
        blended = (1 - learning_rate) * old_weight + learning_rate * new_weight
        
        # Enforce minimum weight
        tuned_weights[detector_name] = max(blended, min_weight)
    
    # ANA-01: Capture pre-normalization weights (ANA-04)
    diagnostics["pre_renorm_weights"] = dict(tuned_weights)
    
    # Normalize to sum to 1.0
    total = sum(tuned_weights.values())
    if total > 0:
        tuned_weights = {k: v / total for k, v in tuned_weights.items()}
    
    # ANA-01: Capture final post-tune weights after normalization
    diagnostics["post_tune_weights"] = dict(tuned_weights)
    diagnostics["tuned_weights"] = tuned_weights  # Keep for backward compatibility
    
    # Log tuning results
    Console.info(f"[TUNE] Detector weight auto-tuning ({tuning_method}):")
    for detector_name in sorted(tuned_weights.keys()):
        old = current_weights.get(detector_name, 0.0)
        new = tuned_weights[detector_name]
        delta = new - old
        det_diag = diagnostics["detector_metrics"].get(detector_name, {})
        metric_type = det_diag.get("metric_type", "n/a")
        metric_val = det_diag.get("metric_value", 0.0)
        Console.info(
            f"  {detector_name:15s}: {old:.3f} -> {new:.3f} (Delta{delta:+.3f}, {metric_type}={metric_val:.3f})"
        )
    
    return tuned_weights, diagnostics


class ScoreCalibrator:
    """
    Calibrates a raw score to a robust z-score using median and MAD,
    and computes a threshold at a given quantile `q`.
    Can compute either a single global threshold or per-regime thresholds.
    """
    def __init__(self, q: float = 0.98, self_tune_cfg: Optional[Dict[str, Any]] = None):
        self.q = float(q)
        self.self_tune_cfg = self_tune_cfg or {}
        self.med = 0.0
        self.mad = 1.0
        self.scale = 1.0
        self.q_thresh = 0.0
        self.q_z = 0.0
        self.regime_thresh_: Dict[int, float] = {}
        self.regime_params_: Dict[int, Tuple[float, float]] = {}

    def fit(self, x: np.ndarray, regime_labels: Optional[np.ndarray] = None) -> "ScoreCalibrator":
        x_finite = x[np.isfinite(x)]
        if x_finite.size == 0:
            return self

        self.med = float(np.median(x_finite))
        self.mad = float(np.median(np.abs(x_finite - self.med)))
        if not np.isfinite(self.mad) or self.mad < 1e-9:
            self.mad = float(np.nanmedian(np.abs(x_finite - self.med)))
        self.scale = float(self.mad) * 1.4826
        # FUSE-FIX-01: Enforce minimum scale to prevent z-score explosion
        if not np.isfinite(self.scale) or self.scale < 1e-3:
            fallback_sd = float(np.nanstd(x_finite))
            self.scale = fallback_sd if np.isfinite(fallback_sd) and fallback_sd > 1e-3 else 1.0
        # Additional safety: ensure scale is at least 1e-3
        self.scale = max(self.scale, 1e-3)
        self.regime_thresh_.clear()
        self.regime_params_.clear()

        # Self-tuning path: find threshold that matches target FP rate
        if self.self_tune_cfg.get("enabled", False):
            target_fp_rate = float(self.self_tune_cfg.get("target_fp_rate", 0.001))
            # The quantile for the target FP rate is (1 - rate)
            auto_q = float(np.clip(1.0 - target_fp_rate, 0.9, 0.995))
            try:
                q_val = float(np.quantile(x_finite, auto_q))
            except Exception:
                q_val = float(np.quantile(x_finite, min(0.99, self.q)))
            spread = abs(q_val - self.med)
            if spread < 1e-6 or spread > 1e6 or not np.isfinite(spread):
                fallback_q = min(0.99, max(self.q, 0.95))
                q_val = float(np.quantile(x_finite, fallback_q))
            self.q_thresh = float(q_val)
            Console.info(f"[CAL] Self-tuning enabled. Target FP rate {target_fp_rate:.3%} -> q={auto_q:.4f}, threshold={self.q_thresh:.4f}")
        else:
            # Standard quantile-based threshold
            self.q_thresh = float(np.quantile(x_finite, self.q))
        self.q_z = (self.q_thresh - self.med) / self.scale if self.scale > 1e-9 else 1.0

        # Per-regime thresholding
        if regime_labels is not None and regime_labels.size == x.size:
            unique_regimes = np.unique(regime_labels)
            Console.info(f"[CAL] Fitting per-regime thresholds for {len(unique_regimes)} regimes.")
            for r in unique_regimes:
                mask = (regime_labels == r)
                x_regime = x[mask]
                x_regime_finite = x_regime[np.isfinite(x_regime)]
                if x_regime_finite.size > 10:  # Require a minimum number of points
                    med_r = float(np.median(x_regime_finite))
                    mad_r = float(np.median(np.abs(x_regime_finite - med_r)))
                    if not np.isfinite(mad_r) or mad_r < 1e-9:
                        mad_r = float(np.nanmedian(np.abs(x_regime_finite - med_r)))
                    scale_r = float(mad_r) * 1.4826
                    if not np.isfinite(scale_r) or scale_r < 1e-9:
                        sd_r = float(np.nanstd(x_regime_finite))
                        scale_r = sd_r if np.isfinite(sd_r) and sd_r > 1e-9 else self.scale
                    thresh_r = float(np.quantile(x_regime_finite, self.q))
                    self.regime_params_[int(r)] = (med_r, scale_r)
                    self.regime_thresh_[int(r)] = (thresh_r - med_r) / max(scale_r, 1e-9)
                else:
                    # Fallback to global threshold if regime has too few points
                    self.regime_params_[int(r)] = (self.med, self.scale)
                    self.regime_thresh_[int(r)] = self.q_z
        return self

    def transform(self, x: np.ndarray, regime_labels: Optional[np.ndarray] = None) -> np.ndarray:
        clip_z = float(self.self_tune_cfg.get("clip_z", 8.0))
        # DET-07: Per-regime sensitivity multipliers
        # Allows fine-tuning sensitivity per regime (e.g., higher sensitivity in steady state, lower in transient)
        regime_multipliers = self.self_tune_cfg.get("regime_sensitivity", {})  # Dict[int, float]
        
        # If per-regime thresholds are available and labels are provided, use them
        if self.regime_params_ and regime_labels is not None and regime_labels.size == x.size:
            z = np.zeros_like(x, dtype=np.float32)
            for r, thresh in self.regime_thresh_.items():
                mask = (regime_labels == r)
                if not np.any(mask):
                    continue
                med_r, scale_r = self.regime_params_.get(int(r), (self.med, self.scale))
                
                # Apply regime-specific sensitivity multiplier
                # multiplier > 1.0 = higher sensitivity (lower threshold, more anomalies detected)
                # multiplier < 1.0 = lower sensitivity (higher threshold, fewer anomalies)
                sensitivity_mult = float(regime_multipliers.get(int(r), 1.0))
                adjusted_scale = scale_r / sensitivity_mult if sensitivity_mult > 0 else scale_r
                
                denom = max(adjusted_scale, 1e-9)
                z_vals = (x[mask] - med_r) / denom
                z[mask] = z_vals
            z = np.nan_to_num(z, nan=0.0, posinf=clip_z, neginf=-clip_z)
            if clip_z > 0:
                z = np.clip(z, -clip_z, clip_z)
            return z.astype(np.float32)

        # Fallback to global thresholding
        denom = max(self.scale, 1e-9)
        z = (x - self.med) / denom
        z = np.nan_to_num(z, nan=0.0, posinf=clip_z, neginf=-clip_z)
        # FUSE-FIX-02: Apply global z-score clipping to ±10
        if clip_z > 0:
            z = np.clip(z, -clip_z, clip_z)
        z = np.clip(z, -10.0, 10.0)  # Enforce hard limit for all fused z-scores
        return z.astype(np.float32)


@dataclass
class EpisodeParams:
    k_sigma: float = 0.5
    h_sigma: float = 5.0
    min_len: int = 3
    gap_merge: int = 5
    min_duration_s: float = 60.0  # Minimum episode duration in seconds


class Fuser:
    def __init__(self, weights: Mapping[str, float], ep: EpisodeParams):
        self.weights = dict(weights)
        self.ep = ep

    @staticmethod
    def _zscore(s: np.ndarray) -> np.ndarray:
        mu = np.nanmean(s)
        sd = np.nanstd(s)
        sd = sd if sd > 1e-9 else 1.0
        return (s - mu) / sd

    @staticmethod
    def _get_base_sensor(feature_name: str) -> str:
        """Simple utility to strip common feature suffixes to find the base sensor name."""
        # This is a heuristic; for a more robust system, a feature metadata mapping would be ideal.
        parts = feature_name.split('_')
        return parts[0]

    def fuse(self, streams: Dict[str, np.ndarray], original_features: pd.DataFrame) -> pd.Series:
        # ANA-03: normalize weights over PRESENT keys only (robust to missing detectors)
        keys = [k for k, v in streams.items() if v is not None]
        if not keys:
            return pd.Series(dtype=float)
        
        # Track which detectors from config are missing
        missing = [k for k in self.weights.keys() if k not in keys]
        if missing:
            Console.info(f"[FUSE] {len(missing)} detector(s) absent at fusion time: {missing}")
        
        n = None
        zs = {}
        for k in keys:
            arr = np.asarray(list(streams[k]), dtype=float)
            n = len(arr) if n is None else n
            zs[k] = self._zscore(arr)
        wsum = sum(self.weights.get(k, 0.0) for k in keys)
        if wsum <= 0:
            w = {k: 1.0 / len(keys) for k in keys}
        else:
            w = {k: float(self.weights.get(k, 0.0)) / wsum for k in keys}
        fused = np.zeros(n, dtype=float)
        for k in keys:
            fused += w[k] * zs[k]
        return pd.Series(fused, index=original_features.index[:n], name="fused")

    def detect_episodes(self, series: pd.Series, streams: Dict[str, np.ndarray], original_features: pd.DataFrame) -> pd.DataFrame:
        """CUSUM-like episode builder on z-series."""
        x = series.values.astype(float)
        mu = np.nanmean(x)
        sd = np.nanstd(x)
        sd = sd if sd > 1e-9 else 1.0
        k = self.ep.k_sigma * sd
        h = self.ep.h_sigma * sd

        s_pos = 0.0
        active = False
        start = None
        episodes = []
        for i, xi in enumerate(x):
            s_pos = max(0.0, s_pos + (xi - mu - k))
            if (not active) and s_pos > 0:
                active = True
                start = i
            if active and s_pos > h:
                # close episode
                end = i
                if end - start + 1 >= self.ep.min_len:
                    episodes.append((start, end))
                s_pos = 0.0
                active = False
                start = None
        # merge gaps
        merged = []
        for s, e in episodes:
            if not merged:
                merged.append([s, e])
                continue
            ps, pe = merged[-1]
            if s - pe - 1 <= self.ep.gap_merge:
                merged[-1][1] = e
            else:
                merged.append([s, e])

        # Use the original DatetimeIndex to get real timestamps
        idx = series.index if isinstance(series.index, pd.DatetimeIndex) else pd.to_datetime(series.index)
        rows = []
        for i, (s, e) in enumerate(merged):
            start_ts = idx[max(0, s)]
            end_ts = idx[min(len(idx) - 1, e)]
            duration_s = (end_ts - start_ts).total_seconds() if pd.notna(start_ts) and pd.notna(end_ts) else 0.0
            
            # Filter out short-duration episodes
            if duration_s < self.ep.min_duration_s:
                continue
            
            # --- Culprit Attribution Logic ---
            episode_streams = {k: v[s:e+1] for k, v in streams.items()}
            
            # Find the detector with the highest mean score during the episode
            max_mean_score = -1
            primary_detector = "unknown"
            for name, scores in episode_streams.items():
                mean_score = np.nanmean(scores)
                if mean_score > max_mean_score:
                    max_mean_score = mean_score
                    primary_detector = name

            # For multivariate models, find the top contributing sensor
            culprits = primary_detector
            if 'pca' in primary_detector or 'mhal' in primary_detector:
                # Simple attribution: find sensor with max mean value in the episode window
                episode_features = original_features.iloc[s:e+1]
                top_feature = episode_features.mean().idxmax()
                culprit_sensor = Fuser._get_base_sensor(str(top_feature))
                culprits = f"{primary_detector}({culprit_sensor})"

            rows.append({"start_ts": start_ts, "end_ts": end_ts, "duration_s": duration_s, "len": int(e - s + 1), "culprits": culprits})
        return pd.DataFrame(rows)


def combine(streams: Dict[str, np.ndarray], weights: Dict[str, float], cfg: Dict[str, Any], original_features: pd.DataFrame) -> Tuple[pd.Series, pd.DataFrame]:
    epcfg = (cfg or {}).get("episodes", {})
    cpd = epcfg.get("cpd", {}) if isinstance(epcfg, dict) else {}
    
    # FUSE-06: Auto-tune k_sigma and h_sigma based on training data statistics
    auto_tune_cfg = cpd.get("auto_tune", {})
    auto_tune_enabled = auto_tune_cfg.get("enabled", False)
    
    base_k_sigma = float(cpd.get("k_sigma", 0.5))
    base_h_sigma = float(cpd.get("h_sigma", 5.0))
    
    k_sigma = base_k_sigma
    h_sigma = base_h_sigma
    
    min_len = int(epcfg.get("min_len", 3))
    gap_merge = int(epcfg.get("gap_merge", 5))
    min_duration_s = float(epcfg.get("min_duration_s", 60.0))

    if auto_tune_enabled:
        try:
            preview_params = EpisodeParams(
                k_sigma=base_k_sigma,
                h_sigma=base_h_sigma,
                min_len=min_len,
                gap_merge=gap_merge,
                min_duration_s=min_duration_s,
            )
            preview_fused = Fuser(weights=weights, ep=preview_params).fuse(streams, original_features)
            fused_vals = preview_fused.to_numpy(dtype=float)
            fused_vals = fused_vals[np.isfinite(fused_vals)]

            stats_source = "fused"
            statistic_vals: np.ndarray
            if fused_vals.size >= max(10, int(0.05 * max(len(fused_vals), 1))):
                statistic_vals = fused_vals
            else:
                all_values = []
                for stream in streams.values():
                    finite_mask = np.isfinite(stream)
                    if finite_mask.any():
                        all_values.append(stream[finite_mask])
                if all_values:
                    statistic_vals = np.concatenate(all_values)
                    stats_source = "detectors"
                else:
                    statistic_vals = np.array([], dtype=float)

            if statistic_vals.size:
                std = float(np.nanstd(statistic_vals))
                std = max(std, 1e-3)
                p50 = float(np.nanpercentile(statistic_vals, 50))
                p95 = float(np.nanpercentile(statistic_vals, 95))
                spread = max(p95 - p50, 1e-3)

                k_factor = float(auto_tune_cfg.get("k_factor", 0.5))
                h_factor = float(auto_tune_cfg.get("h_factor", 3.0))
                k_min = float(auto_tune_cfg.get("k_min", 0.25))
                k_max = float(auto_tune_cfg.get("k_max", max(base_k_sigma, 4.0)))
                h_min = float(auto_tune_cfg.get("h_min", 2.0))
                h_max = float(auto_tune_cfg.get("h_max", max(base_h_sigma, 12.0)))

                k_candidate = k_factor * std
                h_candidate = h_factor * spread

                if np.isfinite(k_candidate):
                    k_sigma = float(np.clip(k_candidate, k_min, k_max))
                else:
                    k_sigma = base_k_sigma

                if np.isfinite(h_candidate):
                    h_sigma = float(np.clip(h_candidate, h_min, h_max))
                else:
                    h_sigma = base_h_sigma

                Console.info("[FUSE] Auto-tuned CUSUM parameters (source=%s):" % stats_source)
                Console.info(f"  k_sigma: {base_k_sigma:.3f} -> {k_sigma:.3f} (std={std:.3f})")
                Console.info(f"  h_sigma: {base_h_sigma:.3f} -> {h_sigma:.3f} (p50={p50:.3f}, p95={p95:.3f})")
            else:
                Console.warn("[FUSE] Auto-tune skipped: insufficient data for statistics")
        except Exception as tune_e:
            Console.warn(f"[FUSE] Auto-tune failed: {tune_e}")
    
    params = EpisodeParams(
        k_sigma=k_sigma,
        h_sigma=h_sigma,
        min_len=min_len,
        gap_merge=gap_merge,
        min_duration_s=min_duration_s,
    )
    fuser = Fuser(weights=weights, ep=params)
    fused = fuser.fuse(streams, original_features)
    episodes = fuser.detect_episodes(fused, streams, original_features)
    return fused, episodes

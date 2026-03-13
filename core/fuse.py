# core/fuse.py
"""
Score fusion, calibration (global or per-regime), and episode detection.

v11.3.3 (2026-01-19): Added CalibrationContaminationFilter for robust calibration.
- Implements anomaly-exclusion from calibration windows
- Multiple filtering strategies: IQR, iterative MAD, z-score trim, hybrid
- Addresses analytics audit finding #6: contaminated training windows
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, cast
from core.observability import Console, Span
from core.representation_contracts import ContextAssignment
from utils.detector_labels import format_culprit_label

import numpy as np
import pandas as pd
from scipy.stats import spearmanr  # type: ignore
from sklearn.metrics import average_precision_score, roc_curve  # type: ignore

_SUPPRESSED_SCORE_COLUMNS = {
    "ar1_z",
    "pca_spe_z",
    "pca_t2_z",
    "iforest_z",
    "gmm_z",
    "omr_z",
    "cusum_z",
    "drift_z",
    "hst_z",
    "river_hst_z",
    "ewm_z",
    "fused",
    "health",
    "HealthIndex",
    "RawHealthIndex",
}


# =============================================================================
# CALIBRATION CONTAMINATION FILTER (v11.3.3 - Analytics Audit Finding #6)
# =============================================================================

@dataclass
class ContaminationFilterResult:
    """Result from contamination filtering."""
    filtered_data: np.ndarray      # Cleaned data for calibration
    excluded_mask: np.ndarray      # Boolean mask of excluded points (True = excluded)
    n_original: int                # Original sample count
    n_filtered: int                # Samples after filtering
    n_excluded: int                # Samples excluded
    exclusion_rate: float          # Proportion excluded (n_excluded / n_original)
    method: str                    # Filtering method used
    threshold_used: float          # Threshold value used for exclusion
    iterations: int                # Number of iterations (for iterative methods)
    converged: bool                # Whether iterative method converged
    diagnostics: Dict[str, Any]    # Additional method-specific diagnostics


class CalibrationContaminationFilter:
    """
    Filters anomalous/contaminated samples from calibration data.
    
    Analytics Audit Finding #6: Training windows can contain anomalies.
    Calibration and thresholds derived from contaminated windows become
    too permissive, leading to increased false negatives and delayed detection.
    
    Mitigation: Introduce anomaly-exclusion for calibration windows using
    robust statistics (median/MAD) consistently for scaling.
    
    Supported methods:
        - 'iqr': Interquartile Range exclusion (robust, fast)
        - 'iterative_mad': Iterative MAD-based trimming (most robust)
        - 'z_trim': Single-pass z-score trimming using MAD
        - 'hybrid': Combination of IQR pre-filter + iterative MAD refinement
        - 'none': No filtering (bypass, for testing)
    
    Usage:
        filter = CalibrationContaminationFilter(method='iterative_mad')
        result = filter.filter(raw_scores)
        # Use result.filtered_data for calibration
    """
    
    # Default exclusion bounds (z-score equivalent)
    DEFAULT_Z_THRESHOLD = 4.0  # Exclude points > 4 MAD-sigma from median
    
    # Maximum exclusion rate - if exceeded, warn and use fallback
    MAX_EXCLUSION_RATE = 0.30  # Don't exclude more than 30%
    
    # Minimum samples to retain after filtering
    MIN_RETAINED_SAMPLES = 50
    
    def __init__(
        self,
        method: str = 'iterative_mad',
        z_threshold: float = 4.0,
        iqr_multiplier: float = 2.5,
        max_iterations: int = 10,
        convergence_tol: float = 0.001,
        min_retained_ratio: float = 0.70,
    ):
        """
        Initialize the contamination filter.
        
        Args:
            method: Filtering method ('iqr', 'iterative_mad', 'z_trim', 'hybrid', 'none')
            z_threshold: Z-score threshold for exclusion (MAD-scaled)
            iqr_multiplier: IQR multiplier for IQR method (default 2.5 = about 3.5 std for normal)
            max_iterations: Maximum iterations for iterative methods
            convergence_tol: Convergence tolerance (median change) for iterative methods
            min_retained_ratio: Minimum ratio of samples to retain (0.70 = keep at least 70%)
        """
        valid_methods = {'iqr', 'iterative_mad', 'z_trim', 'hybrid', 'none'}
        if method not in valid_methods:
            Console.warn(
                f"Unknown contamination filter method '{method}', using 'iterative_mad'",
                component="CAL.FILTER", requested=method, valid=list(valid_methods)
            )
            method = 'iterative_mad'
        
        self.method = method
        self.z_threshold = float(z_threshold)
        self.iqr_multiplier = float(iqr_multiplier)
        self.max_iterations = int(max_iterations)
        self.convergence_tol = float(convergence_tol)
        self.min_retained_ratio = float(min_retained_ratio)
    
    def filter(self, x: np.ndarray) -> ContaminationFilterResult:
        """
        Filter contaminated samples from calibration data.
        
        Args:
            x: Raw score array to filter
            
        Returns:
            ContaminationFilterResult with filtered data and diagnostics
        """
        # Clean input: remove NaN/Inf
        x = np.asarray(x, dtype=np.float64)
        finite_mask = np.isfinite(x)
        x_finite = x[finite_mask]
        n_original = len(x_finite)
        
        if n_original < self.MIN_RETAINED_SAMPLES:
            Console.warn(
                f"Too few samples ({n_original}) for contamination filtering - bypassing",
                component="CAL.FILTER", n_samples=n_original, min_required=self.MIN_RETAINED_SAMPLES
            )
            return self._bypass_result(x_finite, "insufficient_samples")
        
        if self.method == 'none':
            return self._bypass_result(x_finite, "disabled")
        
        # Dispatch to method
        if self.method == 'iqr':
            return self._filter_iqr(x_finite)
        elif self.method == 'iterative_mad':
            return self._filter_iterative_mad(x_finite)
        elif self.method == 'z_trim':
            return self._filter_z_trim(x_finite)
        elif self.method == 'hybrid':
            return self._filter_hybrid(x_finite)
        else:
            return self._bypass_result(x_finite, "unknown_method")
    
    def _bypass_result(self, x: np.ndarray, reason: str) -> ContaminationFilterResult:
        """Create a bypass result (no filtering)."""
        return ContaminationFilterResult(
            filtered_data=x,
            excluded_mask=np.zeros(len(x), dtype=bool),
            n_original=len(x),
            n_filtered=len(x),
            n_excluded=0,
            exclusion_rate=0.0,
            method='none',
            threshold_used=0.0,
            iterations=0,
            converged=True,
            diagnostics={'bypass_reason': reason},
        )
    
    def _filter_iqr(self, x: np.ndarray) -> ContaminationFilterResult:
        """
        IQR-based contamination filter.
        
        Excludes points outside [Q1 - k*IQR, Q3 + k*IQR] where k = iqr_multiplier.
        For normal data, k=1.5 excludes ~0.7%, k=2.5 excludes ~0.035%.
        
        Pros: Very fast, no iterations, well-understood
        Cons: May not handle heavy-tailed distributions well
        """
        q1 = np.percentile(x, 25)
        q3 = np.percentile(x, 75)
        iqr = q3 - q1
        
        # Handle degenerate case
        if iqr < 1e-9:
            Console.warn(
                "IQR near zero - distribution is constant, bypassing filter",
                component="CAL.FILTER", method="iqr", iqr=iqr
            )
            return self._bypass_result(x, "degenerate_iqr")
        
        lower_bound = q1 - self.iqr_multiplier * iqr
        upper_bound = q3 + self.iqr_multiplier * iqr
        
        # Create exclusion mask (True = excluded)
        excluded_mask = (x < lower_bound) | (x > upper_bound)
        
        # Check exclusion rate
        result = self._apply_exclusion_with_guards(
            x, excluded_mask, method='iqr',
            threshold_used=self.iqr_multiplier,
            diagnostics={
                'q1': float(q1), 'q3': float(q3), 'iqr': float(iqr),
                'lower_bound': float(lower_bound), 'upper_bound': float(upper_bound),
            }
        )
        return result
    
    def _filter_z_trim(self, x: np.ndarray) -> ContaminationFilterResult:
        """
        Single-pass z-score trimming using MAD.
        
        Excludes points where |z_mad| > z_threshold.
        Uses median and MAD for robustness.
        """
        median = np.median(x)
        mad = np.median(np.abs(x - median))
        
        # MAD to sigma conversion (1.4826 for normal distribution)
        sigma_mad = mad * 1.4826 if mad > 1e-9 else np.std(x)
        
        if sigma_mad < 1e-9:
            return self._bypass_result(x, "degenerate_scale")
        
        # Compute z-scores
        z_scores = (x - median) / sigma_mad
        
        # Create exclusion mask
        excluded_mask = np.abs(z_scores) > self.z_threshold
        
        result = self._apply_exclusion_with_guards(
            x, excluded_mask, method='z_trim',
            threshold_used=self.z_threshold,
            diagnostics={
                'median': float(median), 'mad': float(mad), 'sigma_mad': float(sigma_mad),
                'max_z': float(np.max(np.abs(z_scores))),
            }
        )
        return result
    
    def _filter_iterative_mad(self, x: np.ndarray) -> ContaminationFilterResult:
        """
        Iterative MAD-based trimming (most robust).
        
        Iteratively removes outliers and recomputes median/MAD until convergence.
        This prevents outliers from inflating the scale estimate.
        
        Algorithm:
        1. Compute median and MAD on current data
        2. Exclude points > z_threshold MAD-sigmas from median
        3. Recompute median/MAD on retained data
        4. Repeat until median converges or max_iterations reached
        """
        current_data = x.copy()
        current_mask = np.ones(len(x), dtype=bool)  # True = included
        prev_median = np.inf
        
        iterations = 0
        converged = False
        
        for i in range(self.max_iterations):
            iterations = i + 1
            
            # Compute robust statistics on current data
            median = np.median(current_data)
            mad = np.median(np.abs(current_data - median))
            sigma_mad = mad * 1.4826 if mad > 1e-9 else np.std(current_data)
            
            if sigma_mad < 1e-9:
                break  # Degenerate - stop
            
            # Compute z-scores on ORIGINAL data using CURRENT statistics
            z_scores = np.abs(x - median) / sigma_mad
            
            # Update mask: exclude points above threshold
            new_mask = (z_scores <= self.z_threshold) & np.isfinite(z_scores)
            
            # Check minimum retention
            if np.sum(new_mask) < len(x) * self.min_retained_ratio:
                Console.debug(
                    f"Iterative MAD: stopping early to preserve min retention ratio",
                    component="CAL.FILTER", iteration=i, retained=np.sum(new_mask),
                    min_required=int(len(x) * self.min_retained_ratio)
                )
                break
            
            current_mask = new_mask
            current_data = x[current_mask]
            
            # Check convergence
            if abs(median - prev_median) < self.convergence_tol:
                converged = True
                break
            
            prev_median = median
        
        # Final exclusion mask (True = excluded)
        excluded_mask = ~current_mask
        
        # Final statistics
        final_median = np.median(x[current_mask]) if np.any(current_mask) else np.median(x)
        final_mad = np.median(np.abs(x[current_mask] - final_median)) if np.any(current_mask) else np.median(np.abs(x - final_median))
        
        result = self._apply_exclusion_with_guards(
            x, excluded_mask, method='iterative_mad',
            threshold_used=self.z_threshold,
            iterations=iterations,
            converged=converged,
            diagnostics={
                'final_median': float(final_median),
                'final_mad': float(final_mad),
                'final_sigma_mad': float(final_mad * 1.4826) if final_mad > 1e-9 else 0.0,
                'iterations': iterations,
                'converged': converged,
            }
        )
        return result
    
    def _filter_hybrid(self, x: np.ndarray) -> ContaminationFilterResult:
        """
        Hybrid filtering: IQR pre-filter + iterative MAD refinement.
        
        Two-stage approach:
        1. IQR filter removes extreme outliers (fast, conservative)
        2. Iterative MAD refines on pre-filtered data
        
        This combines the speed of IQR with the robustness of iterative MAD.
        """
        # Stage 1: IQR pre-filter (looser threshold)
        iqr_result = CalibrationContaminationFilter(
            method='iqr',
            iqr_multiplier=3.0,  # More conservative first pass
        ).filter(x)
        
        pre_filtered = iqr_result.filtered_data
        iqr_excluded = iqr_result.n_excluded
        
        # Stage 2: Iterative MAD on pre-filtered data
        mad_result = CalibrationContaminationFilter(
            method='iterative_mad',
            z_threshold=self.z_threshold,
            max_iterations=self.max_iterations,
            convergence_tol=self.convergence_tol,
            min_retained_ratio=self.min_retained_ratio,
        ).filter(pre_filtered)
        
        # Combine exclusion masks
        # We need to track which original indices were excluded
        # Stage 1 excluded some, stage 2 excluded some of the remainder
        
        # Build final filtered data and total exclusion count
        final_data = mad_result.filtered_data
        total_excluded = iqr_excluded + mad_result.n_excluded
        
        # Build combined mask on original data (approximation)
        # True = excluded
        excluded_mask = np.zeros(len(x), dtype=bool)
        excluded_mask[iqr_result.excluded_mask] = True
        # For the MAD stage, we need to map back - simplify by just counting
        
        return ContaminationFilterResult(
            filtered_data=final_data,
            excluded_mask=excluded_mask,  # Approximate
            n_original=len(x),
            n_filtered=len(final_data),
            n_excluded=total_excluded,
            exclusion_rate=total_excluded / len(x) if len(x) > 0 else 0.0,
            method='hybrid',
            threshold_used=self.z_threshold,
            iterations=mad_result.iterations,
            converged=mad_result.converged,
            diagnostics={
                'iqr_excluded': iqr_excluded,
                'mad_excluded': mad_result.n_excluded,
                'iqr_diagnostics': iqr_result.diagnostics,
                'mad_diagnostics': mad_result.diagnostics,
            }
        )
    
    def _apply_exclusion_with_guards(
        self,
        x: np.ndarray,
        excluded_mask: np.ndarray,
        method: str,
        threshold_used: float,
        iterations: int = 1,
        converged: bool = True,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> ContaminationFilterResult:
        """
        Apply exclusion mask with safety guards.
        
        Guards:
        1. Maximum exclusion rate check
        2. Minimum retained samples check
        """
        n_original = len(x)
        n_excluded = int(np.sum(excluded_mask))
        exclusion_rate = n_excluded / n_original if n_original > 0 else 0.0
        
        # Guard 1: Maximum exclusion rate
        if exclusion_rate > self.MAX_EXCLUSION_RATE:
            Console.warn(
                f"Contamination filter excluded {exclusion_rate:.1%} > max {self.MAX_EXCLUSION_RATE:.1%}. "
                f"Training data may be heavily contaminated. Capping exclusion.",
                component="CAL.FILTER", method=method, exclusion_rate=exclusion_rate,
                max_allowed=self.MAX_EXCLUSION_RATE
            )
            # Cap exclusion: keep the least extreme points up to max exclusion
            n_to_keep = int(n_original * (1.0 - self.MAX_EXCLUSION_RATE))
            # Sort by distance from median and keep closest
            median = np.median(x)
            distances = np.abs(x - median)
            keep_indices = np.argsort(distances)[:n_to_keep]
            excluded_mask = np.ones(n_original, dtype=bool)
            excluded_mask[keep_indices] = False
            n_excluded = int(np.sum(excluded_mask))
            exclusion_rate = n_excluded / n_original
            if diagnostics:
                diagnostics['capped_exclusion'] = True
        
        # Guard 2: Minimum retained samples
        n_retained = n_original - n_excluded
        if n_retained < self.MIN_RETAINED_SAMPLES:
            Console.warn(
                f"Contamination filter would retain only {n_retained} samples < min {self.MIN_RETAINED_SAMPLES}. "
                f"Relaxing filter to retain minimum samples.",
                component="CAL.FILTER", method=method, n_retained=n_retained,
                min_required=self.MIN_RETAINED_SAMPLES
            )
            # Keep at least MIN_RETAINED_SAMPLES closest to median
            median = np.median(x)
            distances = np.abs(x - median)
            keep_indices = np.argsort(distances)[:self.MIN_RETAINED_SAMPLES]
            excluded_mask = np.ones(n_original, dtype=bool)
            excluded_mask[keep_indices] = False
            n_excluded = int(np.sum(excluded_mask))
            exclusion_rate = n_excluded / n_original
            if diagnostics:
                diagnostics['forced_min_retention'] = True
        
        filtered_data = x[~excluded_mask]
        
        return ContaminationFilterResult(
            filtered_data=filtered_data,
            excluded_mask=excluded_mask,
            n_original=n_original,
            n_filtered=len(filtered_data),
            n_excluded=n_excluded,
            exclusion_rate=exclusion_rate,
            method=method,
            threshold_used=threshold_used,
            iterations=iterations,
            converged=converged,
            diagnostics=diagnostics or {},
        )


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

    with Span("fusion.tune_weights", n_detectors=len(streams), n_samples=len(fused) if isinstance(fused, np.ndarray) else 0):
        # FUSE-09: Configurable parameters
        learning_rate = float(tune_cfg.get("learning_rate", 0.3))
        min_weight = float(tune_cfg.get("min_weight", 0.05))
        temperature = float(tune_cfg.get("temperature", 2.0))
        detector_priors = tune_cfg.get("detector_priors", {})  # Dict[str, float] for per-detector biases
    
        # P0-FIX (v11.2.2): Circular tuning guard - DEFAULT TO TRUE
        # ANALYTICAL AUDIT FLAW #1: Circular weight tuning causes self-reinforcing feedback
        # Using same-run episodes to tune weights creates mode collapse risk
        # CHANGE: Default to True (was False) to enforce external validation
        require_external = tune_cfg.get("require_external_labels", True)
    
        # Check if episodes_df has a "source" column or attribute indicating origin
        episode_source = "unknown"
        if episodes_df is not None and not episodes_df.empty:
            if hasattr(episodes_df, 'attrs') and 'source' in episodes_df.attrs:
                episode_source = episodes_df.attrs.get('source', 'unknown')
            elif 'source' in episodes_df.columns:
                episode_source = episodes_df['source'].iloc[0] if len(episodes_df) > 0 else 'unknown'
    
        # v11.4.0: If require_external is True but no external labels, fall back to 
        # statistical_diversity method which doesn't use episode labels at all.
        # This method weights detectors based on:
        # 1. Signal variance (more variance = more informative)
        # 2. Low correlation with other detectors (diversity bonus)
        # 3. Tail behavior (detectors that catch extreme events)
        use_statistical_fallback = False
        if require_external and episode_source in ("current_run", "same_run", "unknown"):
            fallback_method = tune_cfg.get("fallback_method", "statistical_diversity")
            if fallback_method == "statistical_diversity":
                Console.info(
                    f"No external episodes (source='{episode_source}'). "
                    f"Using statistical_diversity method for weight tuning.",
                    component="TUNE", episode_source=episode_source
                )
                use_statistical_fallback = True
            else:
                # Use explicit fallback method
                Console.info(
                    f"No external episodes. Using fallback_method='{fallback_method}'",
                    component="TUNE"
                )
                use_statistical_fallback = fallback_method == "statistical_diversity"

        # ANA-02: Enforce episode_separability as default and log requested method
        requested_method_raw = tune_cfg.get("method", "episode_separability")
        requested_method = str(requested_method_raw).strip().lower()
        # v11.4.0: Added statistical_diversity method for when no external labels available
        valid_methods = {"episode_separability", "statistical_diversity", "correlation"}
        method_fallback_reason: Optional[str] = None
        if requested_method not in valid_methods:
            Console.warn(f"Unknown tuning method '{requested_method_raw}', defaulting to episode_separability", component="TUNE", requested_method=requested_method_raw, valid_methods=list(valid_methods))
            tuning_method = "episode_separability"
            method_fallback_reason = "unknown_method"
        else:
            tuning_method = requested_method
    
        # Warn about potential circularity even when guard is disabled
        if tuning_method == "episode_separability" and episode_source in ("current_run", "same_run"):
            Console.warn(
                f"Weight tuning using episode_separability with same-run episodes (source='{episode_source}'). "
                "This may cause self-reinforcing weight drift. Consider require_external_labels=True.",
                component="TUNE", episode_source=episode_source
            )
    
        diagnostics = {
            "enabled": True,
            "method": tuning_method,
            "requested_method": requested_method,
            "episode_source": episode_source,  # v11.1.6: Track episode source
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
                Console.warn("Episodes provided but fused_index missing or misaligned; skipping PR-AUC labeling", component="TUNE", episodes_count=len(episodes_df), fused_index_len=len(fused_index) if fused_index is not None else 0, n_total=n_total)
            else:
                try:
                    fused_dt_index = pd.DatetimeIndex(fused_index)
                except Exception:
                    fused_dt_index = pd.to_datetime(cast(Any, fused_index))

                # Normalize tz to avoid tz-aware/naive comparison errors
                try:
                    if getattr(fused_dt_index, "tz", None) is not None:
                        fused_dt_index = fused_dt_index.tz_localize(None)
                except Exception:
                    pass

                # PERF-OPT: Vectorized episode mask construction
                positive_mask = np.zeros(n_total, dtype=bool)
            
                # Pre-parse all episode timestamps at once
                start_ts_col = episodes_df["start_ts"] if "start_ts" in episodes_df.columns else pd.Series(dtype="datetime64[ns]")
                end_ts_col = episodes_df["end_ts"] if "end_ts" in episodes_df.columns else pd.Series(dtype="datetime64[ns]")
                start_times = pd.to_datetime(start_ts_col, errors="coerce")
                end_times = pd.to_datetime(end_ts_col, errors="coerce")
            
                # Remove timezone info if present
                if hasattr(start_times, 'tz') and start_times.tz is not None:
                    start_times = start_times.tz_localize(None)
                if hasattr(end_times, 'tz') and end_times.tz is not None:
                    end_times = end_times.tz_localize(None)
            
                # Build mask for valid episodes
                valid_mask = (
                    pd.notna(start_times) & 
                    pd.notna(end_times) & 
                    (end_times >= start_times) &
                    (end_times >= fused_dt_index[0]) &
                    (start_times <= fused_dt_index[-1])
                )
            
                # Create positive mask using numpy broadcasting for valid episodes
                fused_values = fused_dt_index.values
            
                # PERF-OPT: Pre-extract valid episode boundaries as numpy arrays
                valid_indices = valid_mask[valid_mask].index.tolist()
                n_valid_episodes = len(valid_indices)
            
                if n_valid_episodes > 0:
                    valid_starts = start_times.loc[valid_indices].values
                    valid_ends = end_times.loc[valid_indices].values
                
                    # Vectorized interval check - loop over episodes (typically <100)
                    for start_ts, end_ts in zip(valid_starts, valid_ends):
                        window_mask = (fused_values >= start_ts) & (fused_values <= end_ts)
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
                        Console.warn(f"{detector_name}: under-sampled ({n_valid}/{min_samples_required}) - using prior", component="TUNE", detector=detector_name, n_valid=n_valid, min_required=min_samples_required, method=tuning_method)
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
                        Console.warn(f"{detector_name}: all zeros - limited separability", component="TUNE", detector=detector_name, n_samples=len(det_clean), method=tuning_method)
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
                        Console.warn(f"{detector_name}: all same sign - limited separability", component="TUNE", detector=detector_name, n_samples=len(finite_signal), method=tuning_method)
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
                    raise RuntimeError(
                        f"{detector_name}: metric calculation failed for method={tuning_method}: {e}"
                    ) from e

            if not quality_scores:
                diagnostics["reason"] = "no_valid_quality_scores"
                return current_weights, diagnostics

            # BUGFIX v11.1.5: Numerically stable softmax (subtract max before exp)
            # Prevents overflow when quality scores are large relative to temperature
            score_array = np.array(list(quality_scores.values()), dtype=np.float64)
            scaled_scores = score_array / temperature
            shifted_scores = scaled_scores - np.max(scaled_scores)  # Stability: max becomes 0
            exp_scores = np.exp(shifted_scores)
            softmax_weights = exp_scores / np.sum(exp_scores)

            raw_weights = {}
            for i, detector_name in enumerate(quality_scores.keys()):
                weight_val = float(softmax_weights[i])
                raw_weights[detector_name] = weight_val
                diagnostics["raw_weights"][detector_name] = weight_val
    
        elif use_statistical_fallback or tuning_method == "statistical_diversity":
            # v11.4.0: Statistical diversity weighting - no external labels needed
            # This method computes weights based on:
            # 1. Signal informativeness: higher variance = more informative detector
            # 2. Diversity bonus: low correlation with other detectors = unique signal
            # 3. Tail sensitivity: P95/P50 ratio indicates extreme event sensitivity
            #
            # Research basis: Ensemble diversity is well-established in ML literature
            # (Kuncheva & Whitaker 2003, "Measures of Diversity in Classifier Ensembles")
            quality_scores: Dict[str, float] = {}
            
            # Compute correlation matrix for diversity scoring
            detector_names = list(streams.keys())
            n_det = len(detector_names)
            signals = []
            valid_detectors = []
            
            for det_name in detector_names:
                signal = np.asarray(streams[det_name], dtype=np.float64)
                mask = np.isfinite(signal)
                if mask.sum() >= min_samples_required:
                    signals.append(signal)
                    valid_detectors.append(det_name)
            
            if len(signals) < 2:
                Console.warn("Insufficient valid detectors for diversity scoring", component="TUNE")
                diagnostics["reason"] = "insufficient_valid_detectors"
                return current_weights, diagnostics
            
            # Stack signals and compute correlation
            signal_matrix = np.vstack(signals)
            try:
                corr_matrix = np.corrcoef(signal_matrix)
            except Exception:
                corr_matrix = np.eye(len(signals))
            
            for idx, det_name in enumerate(valid_detectors):
                det_diag: Dict[str, Any] = {}
                signal = signals[idx]
                mask = np.isfinite(signal)
                det_clean = signal[mask]
                n_valid = len(det_clean)
                
                # 1. Variance score (normalized by MAD for robustness)
                med = np.median(det_clean)
                mad = np.median(np.abs(det_clean - med)) * 1.4826
                variance_score = min(1.0, mad / 3.0) if mad > 0 else 0.1
                
                # 2. Diversity score: 1 - mean(|correlation| with others)
                other_corrs = [abs(corr_matrix[idx, j]) for j in range(len(signals)) if j != idx]
                mean_corr = np.mean(other_corrs) if other_corrs else 0.0
                diversity_score = 1.0 - mean_corr
                
                # 3. Tail sensitivity: P95 / P50 ratio (capped)
                p50 = np.percentile(np.abs(det_clean), 50)
                p95 = np.percentile(np.abs(det_clean), 95)
                tail_ratio = min(5.0, p95 / max(p50, 1e-6))
                tail_score = min(1.0, tail_ratio / 5.0)
                
                # Combined score with weights
                combined = 0.4 * variance_score + 0.4 * diversity_score + 0.2 * tail_score
                prior = float(detector_priors.get(det_name, 1.0))
                final_score = float(combined * prior)
                
                quality_scores[det_name] = float(max(final_score, 1e-6))
                det_diag.update({
                    "status": "ok",
                    "metric_type": "statistical_diversity",
                    "variance_score": float(variance_score),
                    "diversity_score": float(diversity_score),
                    "tail_score": float(tail_score),
                    "combined_score": float(combined),
                    "mean_correlation": float(mean_corr),
                    "prior": prior,
                    "final_score": float(final_score),
                    "n_samples": n_valid
                })
                diagnostics["detector_metrics"][det_name] = det_diag
            
            # Handle detectors that weren't in valid_detectors
            for det_name in detector_names:
                if det_name not in quality_scores:
                    prior = float(detector_priors.get(det_name, 0.1))
                    quality_scores[det_name] = prior * 0.1
                    diagnostics["detector_metrics"][det_name] = {
                        "status": "insufficient_samples",
                        "metric_type": "prior_only",
                        "prior": prior,
                        "final_score": prior * 0.1
                    }
            
            # Softmax to get weights
            score_array = np.array([quality_scores[d] for d in detector_names], dtype=np.float64)
            scaled_scores = score_array / temperature
            shifted_scores = scaled_scores - np.max(scaled_scores)
            exp_scores = np.exp(shifted_scores)
            softmax_weights = exp_scores / np.sum(exp_scores)
            
            raw_weights = {}
            for i, det_name in enumerate(detector_names):
                weight_val = float(softmax_weights[i])
                raw_weights[det_name] = weight_val
                diagnostics["raw_weights"][det_name] = weight_val
            
            diagnostics["method"] = "statistical_diversity"
            Console.info("Statistical diversity weights computed:", component="TUNE")
            for det_name in sorted(raw_weights.keys()):
                det_diag = diagnostics["detector_metrics"].get(det_name, {})
                Console.info(
                    f"  {det_name:15s}: weight={raw_weights[det_name]:.3f} "
                    f"(var={det_diag.get('variance_score', 0):.2f}, "
                    f"div={det_diag.get('diversity_score', 0):.2f}, "
                    f"tail={det_diag.get('tail_score', 0):.2f})"
                )
    
        else:
            # Legacy correlation method removed in v11.2 - was circular and deprecated
            # If someone explicitly configures method=correlation, fall back to episode_separability
            Console.error("Correlation tuning method removed. Using episode_separability instead.", component="TUNE")
            diagnostics["reason"] = "correlation_method_removed"
            return current_weights, diagnostics
    
        # ANA-01: Capture pre_tune_weights before any modifications
        diagnostics["pre_tune_weights"] = dict(current_weights)
    
        # Blend with existing weights using learning rate
        # P0-FIX (v11.2.2): Add weight stability guard
        tuned_weights = {}
        max_drift_threshold = tune_cfg.get("max_weight_drift", 0.20)  # 20% max change
        
        for detector_name in streams.keys():
            old_weight = current_weights.get(detector_name, 0.0)
            new_weight = raw_weights.get(detector_name, 0.0)
        
            # Exponential moving average
            blended = (1 - learning_rate) * old_weight + learning_rate * new_weight
            
            # P0-FIX: Check for excessive drift (FLAW #1 stability guard)
            if old_weight > 0.01:  # Only check if old_weight is meaningful
                drift = abs(blended - old_weight) / old_weight
                if drift > max_drift_threshold:
                    Console.warn(
                        f"Excessive weight drift for {detector_name}: {old_weight:.3f} -> {blended:.3f} "
                        f"(drift={drift:.1%} > {max_drift_threshold:.1%}). Rejecting tune.",
                        component="TUNE", detector=detector_name, old_weight=old_weight, 
                        new_weight=blended, drift=drift
                    )
                    diagnostics["reason"] = "excessive_drift"
                    diagnostics["excessive_drift_detector"] = detector_name
                    return current_weights, diagnostics
        
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
        Console.info(f"Detector weight auto-tuning ({tuning_method}):", component="TUNE")
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
    
    v11.3.3: Integrated CalibrationContaminationFilter for anomaly exclusion.
    """
    def __init__(self, q: float = 0.98, self_tune_cfg: Optional[Dict[str, Any]] = None, name: str = "detector"):
        self.q = float(q)
        self.self_tune_cfg = self_tune_cfg or {}
        self.name = name
        self.med = 0.0
        self.mad = 1.0
        self.scale = 1.0
        self.q_thresh = 0.0
        self.q_z = 0.0
        self.regime_thresh_: Dict[int, float] = {}
        self.regime_params_: Dict[int, Tuple[float, float]] = {}
        # v11.3.3: Track contamination filtering diagnostics
        self.contamination_filter_result_: Optional[ContaminationFilterResult] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize calibration params for persistence across batches (v11.9.0)."""
        return {
            "med": self.med, "scale": self.scale, "mad": self.mad,
            "q": self.q, "q_z": self.q_z, "q_thresh": self.q_thresh,
            "regime_params": {str(k): list(v) for k, v in self.regime_params_.items()},
            "regime_thresh": {str(k): v for k, v in self.regime_thresh_.items()},
        }

    @classmethod
    def from_dict(cls, params: Dict[str, Any], name: str = "detector") -> "ScoreCalibrator":
        """Rebuild calibrator from persisted params (v11.9.0)."""
        cal = cls(q=params.get("q", 0.98), name=name)
        cal.med = float(params["med"])
        cal.scale = float(params["scale"])
        cal.mad = float(params.get("mad", cal.scale / 1.4826))
        cal.q_z = float(params["q_z"])
        cal.q_thresh = float(params["q_thresh"])
        cal.regime_params_ = {int(k): tuple(v) for k, v in params.get("regime_params", {}).items()}
        cal.regime_thresh_ = {int(k): float(v) for k, v in params.get("regime_thresh", {}).items()}
        return cal

    def fit(self, x: np.ndarray, regime_labels: Optional[np.ndarray] = None) -> "ScoreCalibrator":
        """
        Fit calibration parameters from training data.
        
        v11.3.3: Now applies contamination filtering BEFORE computing statistics.
        This addresses Analytics Audit Finding #6: calibration/thresholds from
        contaminated windows become too permissive.
        """
        x_finite = x[np.isfinite(x)]
        if x_finite.size == 0:
            Console.warn("No finite values in calibration data - using defaults", component="CAL", calibrator=self.name, input_size=len(x))
            return self

        # FUSE-FIX-03: Validate input data has reasonable variation
        if x_finite.size < 10:
            Console.warn(f"Insufficient samples ({x_finite.size}) for reliable calibration - using defaults", component="CAL", calibrator=self.name, n_samples=x_finite.size, min_required=10)
            return self

        # =========================================================================
        # v11.3.3: CONTAMINATION FILTERING (Analytics Audit Finding #6)
        # Filter anomalous samples BEFORE computing calibration statistics.
        # This prevents contaminated training windows from inflating thresholds.
        # =========================================================================
        contamination_cfg = self.self_tune_cfg.get("contamination_filter", {})
        filter_enabled = contamination_cfg.get("enabled", True)  # Default: ON
        filter_method = contamination_cfg.get("method", "iterative_mad")
        filter_z_threshold = float(contamination_cfg.get("z_threshold", 4.0))
        
        if filter_enabled and x_finite.size >= 50:  # Need enough samples for reliable filtering
            contam_filter = CalibrationContaminationFilter(
                method=filter_method,
                z_threshold=filter_z_threshold,
                max_iterations=int(contamination_cfg.get("max_iterations", 10)),
                convergence_tol=float(contamination_cfg.get("convergence_tol", 0.001)),
                min_retained_ratio=float(contamination_cfg.get("min_retained_ratio", 0.70)),
            )
            
            filter_result = contam_filter.filter(x_finite)
            self.contamination_filter_result_ = filter_result
            
            # Use filtered data for calibration
            x_clean = filter_result.filtered_data
            
            if filter_result.n_excluded > 0:
                Console.info(
                    f"Contamination filter ({filter_method}): excluded {filter_result.n_excluded}/{filter_result.n_original} "
                    f"samples ({filter_result.exclusion_rate:.1%}) | retained={filter_result.n_filtered}",
                    component="CAL", calibrator=self.name, method=filter_method,
                    excluded=filter_result.n_excluded, retained=filter_result.n_filtered
                )
        else:
            x_clean = x_finite
            self.contamination_filter_result_ = None
            if filter_enabled and x_finite.size < 50:
                Console.debug(
                    f"Contamination filter bypassed: insufficient samples ({x_finite.size} < 50)",
                    component="CAL", calibrator=self.name
                )
        # =========================================================================
        # END CONTAMINATION FILTERING
        # =========================================================================

        # Compute statistics on CLEANED data
        self.med = float(np.median(x_clean))
        self.mad = float(np.median(np.abs(x_clean - self.med)))
        if not np.isfinite(self.mad) or self.mad < 1e-9:
            self.mad = float(np.nanmedian(np.abs(x_clean - self.med)))
        self.scale = float(self.mad) * 1.4826
        # FUSE-FIX-01: Enforce minimum scale to prevent z-score explosion
        if not np.isfinite(self.scale) or self.scale < 1e-3:
            fallback_sd = float(np.nanstd(x_clean))
            self.scale = fallback_sd if np.isfinite(fallback_sd) and fallback_sd > 1e-3 else 1.0
        # Additional safety: ensure scale is at least 1e-3
        self.scale = max(self.scale, 1e-3)
        self.regime_thresh_.clear()
        self.regime_params_.clear()

        # Self-tuning path is always active.
        target_fp_rate = float(self.self_tune_cfg.get("target_fp_rate", 0.001))
        auto_q = float(np.clip(1.0 - target_fp_rate, 0.9, 0.995))
        try:
            q_val = float(np.quantile(x_clean, auto_q))
        except Exception:
            q_val = float(np.quantile(x_clean, min(0.99, self.q)))
        spread = abs(q_val - self.med)
        if spread < 1e-6 or spread > 1e6 or not np.isfinite(spread):
            fallback_q = min(0.99, max(self.q, 0.95))
            q_val = float(np.quantile(x_clean, fallback_q))
        self.q_thresh = float(q_val)
        Console.info(
            f"Self-tuning active. Target FP rate {target_fp_rate:.3%} -> q={auto_q:.4f}, threshold={self.q_thresh:.4f}",
            component="CAL",
        )
        
        # FUSE-FIX-04: Validate and clamp threshold to reasonable range
        # Thresholds should be in a sensible range for z-scores/raw anomaly metrics
        min_thresh = float(self.self_tune_cfg.get("min_threshold", 0.001))
        max_thresh = float(self.self_tune_cfg.get("max_threshold", 1000.0))
        
        if not np.isfinite(self.q_thresh):
            Console.warn(f"Non-finite threshold computed ({self.q_thresh}) - using fallback 3.0", component="CAL", calibrator=self.name, computed_threshold=self.q_thresh, fallback=3.0)
            self.q_thresh = 3.0
        elif self.q_thresh <= 0:
            Console.debug(f"Non-positive threshold ({self.q_thresh:.6f}) - clamping to {min_thresh}", component="CAL", calibrator=self.name)
            self.q_thresh = min_thresh
        elif self.q_thresh > max_thresh:
            Console.debug(f"Extreme threshold ({self.q_thresh:.2f}) - clamping to {max_thresh}", component="CAL", calibrator=self.name)
            self.q_thresh = max_thresh
        
        self.q_z = (self.q_thresh - self.med) / self.scale if self.scale > 1e-9 else 1.0
        
        # FUSE-FIX-05: Clamp q_z to reasonable z-score range
        if not np.isfinite(self.q_z) or abs(self.q_z) > 20.0:
            Console.debug(f"Extreme q_z ({self.q_z:.2f}) - clamping to +/-20", component="CAL", calibrator=self.name)
            self.q_z = float(np.clip(self.q_z, -20.0, 20.0)) if np.isfinite(self.q_z) else 3.0

        # Per-regime thresholding
        # v11.3.3: Also apply contamination filtering per-regime
        if regime_labels is not None and regime_labels.size == x.size:
            unique_regimes = np.unique(regime_labels)
            Console.info(f"Fitting per-regime thresholds for {len(unique_regimes)} regimes.", component="CAL")
            for r in unique_regimes:
                mask = (regime_labels == r)
                x_regime = x[mask]
                x_regime_finite = x_regime[np.isfinite(x_regime)]
                
                if x_regime_finite.size > 10:  # Require a minimum number of points
                    # Apply contamination filtering per-regime
                    if filter_enabled and x_regime_finite.size >= 30:
                        regime_filter = CalibrationContaminationFilter(
                            method=filter_method,
                            z_threshold=filter_z_threshold,
                            min_retained_ratio=0.60,  # More lenient for smaller regime subsets
                        )
                        regime_filter_result = regime_filter.filter(x_regime_finite)
                        x_regime_clean = regime_filter_result.filtered_data
                    else:
                        x_regime_clean = x_regime_finite
                    
                    med_r = float(np.median(x_regime_clean))
                    mad_r = float(np.median(np.abs(x_regime_clean - med_r)))
                    if not np.isfinite(mad_r) or mad_r < 1e-9:
                        mad_r = float(np.nanmedian(np.abs(x_regime_clean - med_r)))
                    scale_r = float(mad_r) * 1.4826
                    if not np.isfinite(scale_r) or scale_r < 1e-9:
                        sd_r = float(np.nanstd(x_regime_clean))
                        scale_r = sd_r if np.isfinite(sd_r) and sd_r > 1e-9 else self.scale
                    thresh_r = float(np.quantile(x_regime_clean, self.q))
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
        # FUSE-FIX-02: Apply global z-score clipping to +/-10
        if clip_z > 0:
            z = np.clip(z, -clip_z, clip_z)
        z = np.clip(z, -10.0, 10.0)  # Enforce hard limit for all fused z-scores
        return z.astype(np.float32)

    def transform_with_raw(self, x: np.ndarray, regime_labels: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        """P3-FIX (v11.1.6): Return both clipped (for UI) and unclipped (for analytics) z-scores.
        
        The unclipped z_raw preserves severity dynamics for RUL trending and ranking,
        while z_clipped is safe for dashboard display.
        
        Returns:
            Tuple of (z_clipped, z_raw)
        """
        clip_z = float(self.self_tune_cfg.get("clip_z", 8.0))
        regime_multipliers = self.self_tune_cfg.get("regime_sensitivity", {})
        
        # Compute raw z-scores first
        if self.regime_params_ and regime_labels is not None and regime_labels.size == x.size:
            z_raw = np.zeros_like(x, dtype=np.float32)
            for r, thresh in self.regime_thresh_.items():
                mask = (regime_labels == r)
                if not np.any(mask):
                    continue
                med_r, scale_r = self.regime_params_.get(int(r), (self.med, self.scale))
                sensitivity_mult = float(regime_multipliers.get(int(r), 1.0))
                adjusted_scale = scale_r / sensitivity_mult if sensitivity_mult > 0 else scale_r
                denom = max(adjusted_scale, 1e-9)
                z_vals = (x[mask] - med_r) / denom
                z_raw[mask] = z_vals
        else:
            denom = max(self.scale, 1e-9)
            z_raw = (x - self.med) / denom
        
        z_raw = np.nan_to_num(z_raw, nan=0.0, posinf=50.0, neginf=-50.0)
        z_raw = z_raw.astype(np.float32)
        
        # Clipped version for UI
        z_clipped = z_raw.copy()
        if clip_z > 0:
            z_clipped = np.clip(z_clipped, -clip_z, clip_z)
        z_clipped = np.clip(z_clipped, -10.0, 10.0)
        
        return z_clipped, z_raw


def build_per_regime_threshold_rows(
    calibrators: List[Tuple[str, "ScoreCalibrator"]],
) -> List[Dict[str, Any]]:
    """
    Build per-regime threshold transparency rows from fitted calibrators.
    """
    rows: List[Dict[str, Any]] = []
    for detector_name, calibrator in calibrators:
        for regime_id in sorted(calibrator.regime_thresh_.keys()):
            med_r, scale_r = calibrator.regime_params_[regime_id]
            thresh_z = calibrator.regime_thresh_[regime_id]
            rows.append(
                {
                    "detector": detector_name,
                    "regime": int(regime_id),
                    "median": float(med_r),
                    "scale": float(scale_r),
                    "z_threshold": float(thresh_z),
                    "global_median": float(calibrator.med),
                    "global_scale": float(calibrator.scale),
                }
            )
    return rows


def build_threshold_rows(
    calibrators: List[Tuple[str, "ScoreCalibrator"]],
) -> List[Dict[str, Any]]:
    """
    Build global + per-regime threshold rows for ACM thresholds artifact.
    """
    rows: List[Dict[str, Any]] = []
    for detector_name, calibrator in calibrators:
        rows.append(
            {
                "detector": detector_name,
                "regime": "GLOBAL",
                "median": float(calibrator.med),
                "scale": float(calibrator.scale),
                "z_threshold": float(calibrator.q_z),
                "raw_threshold": float(calibrator.q_thresh),
            }
        )
        for regime_id, regime_thresh in calibrator.regime_thresh_.items():
            med_r, scale_r = calibrator.regime_params_.get(regime_id, (calibrator.med, calibrator.scale))
            rows.append(
                {
                    "detector": detector_name,
                    "regime": int(regime_id),
                    "median": float(med_r),
                    "scale": float(scale_r),
                    "z_threshold": float(regime_thresh),
                    "raw_threshold": float(med_r + regime_thresh * max(scale_r, 1e-9)),
                }
            )
    return rows


def build_calibration_summary_rows(
    calibrators: List[Tuple[str, "ScoreCalibrator"]],
) -> List[Dict[str, Any]]:
    """
    Build calibration summary payload rows for SQL write.
    """
    rows: List[Dict[str, Any]] = []
    for detector_name, calibrator in calibrators:
        rows.append(
            {
                "DetectorType": detector_name,
                "CalibrationScore": float(calibrator.q_z) if hasattr(calibrator, "q_z") else 0.0,
                "Median": float(calibrator.med) if hasattr(calibrator, "med") else 0.0,
                "Scale": float(calibrator.scale) if hasattr(calibrator, "scale") else 0.0,
                "NumRegimes": len(calibrator.regime_thresh_) if hasattr(calibrator, "regime_thresh_") else 0,
            }
        )
    return rows


def persist_threshold_artifacts(
    output_manager: Optional[Any],
    calibrators: List[Tuple[str, "ScoreCalibrator"]],
    quality_ok: bool,
    use_per_regime: bool,
) -> Tuple[int, int]:
    """
    Persist per-regime and global threshold artifacts.

    Returns:
        Tuple of (per_regime_row_count, threshold_row_count)
    """
    if output_manager is None:
        return 0, 0

    per_regime_count = 0
    if quality_ok and use_per_regime:
        per_regime_rows = build_per_regime_threshold_rows(calibrators)
        if per_regime_rows:
            per_regime_df = pd.DataFrame(per_regime_rows)
            output_manager.write_dataframe(per_regime_df, "per_regime_thresholds")
            per_regime_count = len(per_regime_rows)

    threshold_rows = build_threshold_rows(calibrators)
    if threshold_rows:
        thresholds_df = pd.DataFrame(threshold_rows)
        output_manager.write_dataframe(thresholds_df, "acm_thresholds")

    return per_regime_count, len(threshold_rows)


def apply_contamination_filter_config(
    self_tune_cfg: Dict[str, Any],
    thresholds_cfg: Optional[Dict[str, Any]],
    baseline_contamination_verdict: str = "unknown",
) -> Dict[str, Any]:
    """
    Apply contamination-filter settings into calibration self-tune config.

    Mutates and returns self_tune_cfg to preserve existing runtime behavior.
    """
    self_tune_cfg["contamination_filter"] = resolve_contamination_filter_policy(
        thresholds_cfg=thresholds_cfg,
        baseline_contamination_verdict=baseline_contamination_verdict,
    )
    return self_tune_cfg


def resolve_contamination_filter_policy(
    thresholds_cfg: Optional[Dict[str, Any]],
    baseline_contamination_verdict: str = "unknown",
) -> Dict[str, Any]:
    """
    Resolve the effective contamination-filter policy for downstream consumers.

    Clean baselines should not be filtered a second time during calibration or
    adaptive-threshold fitting. Suspect or contaminated baselines retain the
    configured downstream filter, if enabled.
    """
    contam_filter_cfg = dict((thresholds_cfg or {}).get("contamination_filter", {}) or {})
    configured_enabled = bool(contam_filter_cfg.get("enabled", True))
    verdict = str(baseline_contamination_verdict or "ok").strip().lower()

    if verdict == "ok":
        effective_enabled = False
    elif verdict in {"suspect", "contaminated"}:
        effective_enabled = configured_enabled
    else:
        effective_enabled = configured_enabled

    return {
        "enabled": effective_enabled,
        "method": contam_filter_cfg.get("method", "iterative_mad"),
        "z_threshold": float(contam_filter_cfg.get("z_threshold", 4.0)),
        "max_iterations": int(contam_filter_cfg.get("max_iterations", 10)),
        "min_retained_ratio": float(contam_filter_cfg.get("min_retained_ratio", 0.70)),
        "configured_enabled": configured_enabled,
        "baseline_contamination_verdict": verdict,
    }


def choose_pca_cache_for_calibration(
    pca_train_spe: Optional[np.ndarray],
    pca_train_t2: Optional[np.ndarray],
    train_len: int,
    logger: Any = Console,
) -> Optional[Tuple[np.ndarray, Optional[np.ndarray]]]:
    """
    Return cached PCA scores only when cache length exactly matches train length.
    """
    if pca_train_spe is not None and len(pca_train_spe) == train_len:
        return (pca_train_spe, pca_train_t2)

    if pca_train_spe is not None:
        logger.info(
            f"PCA cache length mismatch: cached={len(pca_train_spe)}, train={train_len} - re-scoring",
            component="CALIBRATE",
        )
    return None


def compute_and_set_adaptive_clip(
    train_frame: pd.DataFrame,
    self_tune_cfg: Dict[str, Any],
    omr_enabled: bool,
) -> float:
    """
    Compute adaptive z-clip from TRAIN raw detector scores and update self_tune_cfg.
    """
    default_clip = float(self_tune_cfg.get("clip_z", 8.0))
    train_z_p99: Dict[str, float] = {}
    det_raw_cols = [
        ("ar1", "ar1_raw"),
        ("pca_spe", "pca_spe"),
        ("pca_t2", "pca_t2"),
        ("iforest", "iforest_raw"),
        ("gmm", "gmm_raw"),
    ]
    if omr_enabled:
        det_raw_cols.append(("omr", "omr_raw"))

    for det_name, raw_col in det_raw_cols:
        if raw_col not in train_frame.columns:
            continue
        raw_vals = train_frame[raw_col].to_numpy(copy=False)
        finite_vals = raw_vals[np.isfinite(raw_vals)]
        if len(finite_vals) <= 10:
            continue
        med = float(np.median(finite_vals))
        mad = float(np.median(np.abs(finite_vals - med)))
        scale = mad * 1.4826 if mad > 1e-9 else float(np.nanstd(finite_vals))
        scale = max(scale, 1e-3)
        z_vals = (finite_vals - med) / scale
        p99 = float(np.percentile(z_vals, 99))
        if 0 < p99 < 100:
            train_z_p99[det_name] = p99

    adaptive_clip = default_clip
    if train_z_p99:
        max_train_p99 = max(train_z_p99.values())
        adaptive_clip = max(default_clip, min(max_train_p99 * 1.5, 50.0))
        self_tune_cfg["clip_z"] = adaptive_clip
    return adaptive_clip


def compute_pca_train_percentiles(
    train_frame: pd.DataFrame,
    fit_regimes: Optional[np.ndarray],
    pca_enabled: bool,
    calibrators_dict: Dict[str, Any],
) -> Tuple[float, float]:
    """
    Compute P95 TRAIN z-scores for PCA SPE and T2 calibrators.
    """
    spe_p95_train = 0.0
    t2_p95_train = 0.0
    cal_pca_spe = calibrators_dict.get("pca_spe_z")
    cal_pca_t2 = calibrators_dict.get("pca_t2_z")

    if pca_enabled and cal_pca_spe is not None and "pca_spe" in train_frame.columns:
        pca_train_spe_z = cal_pca_spe.transform(
            train_frame["pca_spe"].to_numpy(dtype=np.float32), regime_labels=fit_regimes
        )
        spe_p95_train = float(np.nanpercentile(pca_train_spe_z, 95))

    if pca_enabled and cal_pca_t2 is not None and "pca_t2" in train_frame.columns:
        pca_train_t2_z = cal_pca_t2.transform(
            train_frame["pca_t2"].to_numpy(dtype=np.float32), regime_labels=fit_regimes
        )
        t2_p95_train = float(np.nanpercentile(pca_train_t2_z, 95))

    return spe_p95_train, t2_p95_train


def collect_enabled_calibrators(
    calibrators_dict: Dict[str, Any],
    frame: pd.DataFrame,
    ar1_enabled: bool,
    pca_enabled: bool,
    iforest_enabled: bool,
    gmm_enabled: bool,
    omr_enabled: bool,
) -> List[Tuple[str, "ScoreCalibrator"]]:
    """
    Collect active calibrator objects in detector output order.
    """
    calibrators: List[Tuple[str, "ScoreCalibrator"]] = []
    cal_ar = calibrators_dict.get("ar1_z")
    cal_pca_spe = calibrators_dict.get("pca_spe_z")
    cal_pca_t2 = calibrators_dict.get("pca_t2_z")
    cal_if = calibrators_dict.get("iforest_z")
    cal_gmm = calibrators_dict.get("gmm_z")
    cal_omr = calibrators_dict.get("omr_z")

    if ar1_enabled and cal_ar is not None:
        calibrators.append(("ar1_z", cal_ar))
    if pca_enabled and cal_pca_spe is not None:
        calibrators.append(("pca_spe_z", cal_pca_spe))
    if pca_enabled and cal_pca_t2 is not None:
        calibrators.append(("pca_t2_z", cal_pca_t2))
    if iforest_enabled and cal_if is not None:
        calibrators.append(("iforest_z", cal_if))
    if gmm_enabled and cal_gmm is not None:
        calibrators.append(("gmm_z", cal_gmm))
    if omr_enabled and cal_omr is not None and "omr_raw" in frame.columns:
        calibrators.append(("omr_z", cal_omr))
    return calibrators


def write_calibration_summary_safe(
    output_manager: Optional[Any],
    calibrators: List[Tuple[str, "ScoreCalibrator"]],
    logger: Any = Console,
    equip: str = "",
) -> int:
    """
    Write calibration summary payload and return written row count.
    """
    if output_manager is None or not calibrators:
        return 0

    try:
        calibration_summary = build_calibration_summary_rows(calibrators)
        if not calibration_summary:
            return 0
        return int(output_manager.write_calibration_summary(calibration_summary))
    except Exception as e:
        logger.warn(
            f"Calibration summary write failed: {e}",
            component="CAL",
            equip=equip,
            error=str(e)[:200],
        )
        return 0


@dataclass
class CalibrationStageResult:
    """Result payload from calibration stage orchestration."""
    frame: pd.DataFrame
    train_frame: pd.DataFrame
    calibrators_dict: Dict[str, Any]
    calibrators: List[Tuple[str, "ScoreCalibrator"]]
    spe_p95_train: float
    t2_p95_train: float
    quality_ok: bool
    use_per_regime: bool


def run_calibration_stage(
    *,
    train: pd.DataFrame,
    frame: pd.DataFrame,
    cfg: Dict[str, Any],
    regime_quality_ok: bool,
    train_regime_labels: Optional[np.ndarray],
    score_regime_labels: Optional[np.ndarray],
    pca_train_spe: Optional[np.ndarray],
    pca_train_t2: Optional[np.ndarray],
    detectors: Dict[str, Any],
    detector_flags: Dict[str, bool],
    cached_calibration_params: Optional[Dict[str, Any]],
    saved_model_version: Optional[int],
    score_all_detectors_fn: Callable[..., Tuple[pd.DataFrame, Optional[Any]]],
    calibrate_all_detectors_fn: Callable[..., Tuple[pd.DataFrame, Dict[str, Any]]],
    persist_calibration_params_fn: Optional[Callable[..., bool]] = None,
    output_manager: Optional[Any] = None,
    logger: Any = Console,
    equip: str = "",
    baseline_contamination_verdict: str = "unknown",
) -> CalibrationStageResult:
    """
    Run calibration stage end-to-end while keeping behavior parity with acm.py.
    """
    cal_q = float((cfg or {}).get("thresholds", {}).get("q", 0.98))
    self_tune_cfg = (cfg or {}).get("thresholds", {}).get("self_tune", {})
    use_per_regime = (cfg.get("fusion", {}) or {}).get("per_regime", False)
    quality_ok = bool(
        use_per_regime
        and regime_quality_ok
        and train_regime_labels is not None
        and score_regime_labels is not None
    )

    apply_contamination_filter_config(
        self_tune_cfg=self_tune_cfg,
        thresholds_cfg=(cfg or {}).get("thresholds", {}),
        baseline_contamination_verdict=baseline_contamination_verdict,
    )

    pca_cached_for_train = choose_pca_cache_for_calibration(
        pca_train_spe=pca_train_spe,
        pca_train_t2=pca_train_t2,
        train_len=len(train),
        logger=logger,
    )

    train_frame, _ = score_all_detectors_fn(
        data=train,
        ar1_detector=detectors.get("ar1_detector"),
        pca_detector=detectors.get("pca_detector"),
        iforest_detector=detectors.get("iforest_detector"),
        gmm_detector=detectors.get("gmm_detector"),
        omr_detector=detectors.get("omr_detector"),
        ar1_enabled=bool(detector_flags.get("ar1_enabled", True)),
        pca_enabled=bool(detector_flags.get("pca_enabled", True)),
        iforest_enabled=bool(detector_flags.get("iforest_enabled", True)),
        gmm_enabled=bool(detector_flags.get("gmm_enabled", True)),
        omr_enabled=bool(detector_flags.get("omr_enabled", True)),
        pca_cached=pca_cached_for_train,
        return_omr_contributions=False,
    )

    adaptive_clip = compute_and_set_adaptive_clip(
        train_frame=train_frame,
        self_tune_cfg=self_tune_cfg,
        omr_enabled=bool(detector_flags.get("omr_enabled", True)),
    )

    fit_regimes = train_regime_labels if quality_ok else None
    transform_regimes = score_regime_labels if quality_ok else None
    frame["per_regime_active"] = 1 if quality_ok else 0

    frame, calibrators_dict = calibrate_all_detectors_fn(
        train_frame=train_frame,
        score_frame=frame,
        cal_q=cal_q,
        self_tune_cfg=self_tune_cfg,
        fit_regimes=fit_regimes,
        transform_regimes=transform_regimes,
        omr_enabled=bool(detector_flags.get("omr_enabled", True)),
        cached_calibration_params=cached_calibration_params,
    )

    if persist_calibration_params_fn is not None:
        persist_calibration_params_fn(saved_model_version, calibrators_dict)

    spe_p95_train, t2_p95_train = compute_pca_train_percentiles(
        train_frame=train_frame,
        fit_regimes=fit_regimes,
        pca_enabled=bool(detector_flags.get("pca_enabled", True)),
        calibrators_dict=calibrators_dict,
    )

    calibrators = collect_enabled_calibrators(
        calibrators_dict=calibrators_dict,
        frame=frame,
        ar1_enabled=bool(detector_flags.get("ar1_enabled", True)),
        pca_enabled=bool(detector_flags.get("pca_enabled", True)),
        iforest_enabled=bool(detector_flags.get("iforest_enabled", True)),
        gmm_enabled=bool(detector_flags.get("gmm_enabled", True)),
        omr_enabled=bool(detector_flags.get("omr_enabled", True)),
    )

    per_regime_count, threshold_count = persist_threshold_artifacts(
        output_manager=output_manager,
        calibrators=calibrators,
        quality_ok=quality_ok,
        use_per_regime=use_per_regime,
    )

    cal_summary_count = write_calibration_summary_safe(
        output_manager=output_manager,
        calibrators=calibrators,
        logger=logger,
        equip=equip,
    )

    logger.info(
        f"Calibration complete: q={cal_q} | clip_z={adaptive_clip:.2f} | detectors={len(calibrators)} | "
        f"thresholds={threshold_count} | per_regime={per_regime_count} | summary={cal_summary_count}",
        component="CAL",
    )

    return CalibrationStageResult(
        frame=frame,
        train_frame=train_frame,
        calibrators_dict=calibrators_dict,
        calibrators=calibrators,
        spe_p95_train=spe_p95_train,
        t2_p95_train=t2_p95_train,
        quality_ok=quality_ok,
        use_per_regime=use_per_regime,
    )


@dataclass
class EpisodeParams:
    """Parameters for episode detection with hysteresis.
    
    v11.1.6: Added proper hysteresis-based detection parameters:
    - z_on: Onset threshold (|z| must exceed this to start episode)
    - z_off: Release threshold (|z| must fall below this to end episode)
    - min_onset: Consecutive samples above z_on to confirm start
    - min_release: Consecutive samples below z_off to confirm end
    
    k_sigma and h_sigma are now dimensionless multipliers (not score units).
    """
    k_sigma: float = 0.5           # CUSUM slack parameter (dimensionless multiplier)
    h_sigma: float = 5.0           # CUSUM threshold (dimensionless multiplier)
    min_len: int = 3               # Minimum episode length in samples
    gap_merge: int = 5             # Maximum gap to merge adjacent episodes
    min_duration_s: float = 60.0   # Minimum episode duration in seconds
    # v11.1.6: Hysteresis parameters for proper episode boundaries
    z_on: float = 2.0              # Onset threshold (sigma units)
    z_off: float = 1.0             # Release threshold (sigma units, must be < z_on)
    min_onset: int = 2             # Samples above z_on to confirm start
    min_release: int = 3           # Samples below z_off to confirm end
    # v11.1.6: Per-regime threshold multipliers for rotary equipment transients
    # Keys are regime IDs, values are multipliers (>1 = relaxed threshold)
    # Default: UNKNOWN regime (-1) gets 50% higher thresholds to reduce false positives
    regime_threshold_mult: Dict[int, float] = field(default_factory=lambda: {-1: 1.5})


class Fuser:
    def __init__(self, weights: Mapping[str, float], ep: EpisodeParams):
        self.weights = dict(weights)
        self.ep = ep

    @staticmethod
    def _sanitize(s: np.ndarray) -> np.ndarray:
        """Clean calibrated z-scores for fusion (NaN/inf handling only).

        v11.9.0: Input z-scores are already training-anchored via ScoreCalibrator.
        Do NOT re-center or re-scale; that destroys cross-batch comparability.
        Previous _zscore() re-normalized against the current batch, making health
        scores incomparable between batches (e.g., 39% vs 94% on same data).
        """
        s = np.asarray(s, dtype=float)
        return np.nan_to_num(s, nan=0.0, posinf=10.0, neginf=-10.0)

    @staticmethod
    def _get_base_sensor(feature_name: str) -> str:
        """Simple utility to strip common feature suffixes to find the base sensor name."""
        # This is a heuristic; for a more robust system, a feature metadata mapping would be ideal.
        parts = feature_name.split('_')
        return parts[0]

    def fuse(
        self,
        streams: Dict[str, np.ndarray],
        original_features: pd.DataFrame,
        discounted_weights: Dict[str, float],
    ) -> pd.Series:
        """Fuse detector streams into a single weighted z-score series.

        Args:
            streams: Dict of detector_name -> z-score array.
            original_features: Score-window feature DataFrame (provides index).
            discounted_weights: Pre-computed correlation-discounted weights from
                compute_discounted_weights(). Compute once upstream and pass in,
                never compute inside fuse() per call.
        """
        # ANA-03: normalize weights over PRESENT keys only (robust to missing detectors)
        keys = [k for k, v in streams.items() if v is not None]
        if not keys:
            return pd.Series(dtype=float)

        missing = [k for k in self.weights.keys() if k not in keys]
        if missing:
            Console.info(f"{len(missing)} detector(s) absent at fusion time: {missing}", component="FUSE")

        lengths = []
        zs: Dict[str, np.ndarray] = {}
        for k in keys:
            arr = np.asarray(streams[k], dtype=float)
            lengths.append(len(arr))
            zs[k] = self._sanitize(arr)
        n = min(lengths) if lengths else 0
        if len(original_features.index) > 0:
            n = min(n, len(original_features.index))
        if n == 0:
            return pd.Series(dtype=float)

        zs = {k: v[:n] for k, v in zs.items()}

        w_raw = {k: float(discounted_weights.get(k, self.weights.get(k, 0.0))) for k in keys}

        wsum = sum(w_raw.values())
        if wsum <= 0:
            w = {k: 1.0 / len(keys) for k in keys}
        else:
            w = {k: v / wsum for k, v in w_raw.items()}
        fused = np.zeros(n, dtype=float)
        for k in keys:
            fused += w[k] * zs[k]
        return pd.Series(fused, index=original_features.index[:n], name="fused")

    def detect_episodes(
        self, 
        series: pd.Series, 
        streams: Dict[str, np.ndarray], 
        original_features: pd.DataFrame, 
        regime_labels: Optional[np.ndarray] = None,
        omr_contributions: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """CUSUM-like episode builder on z-series.
        
        v10.1.0: Added regime_labels parameter for episode-regime correlation.
        Episodes now include:
        - start_regime: Dominant regime at episode start
        - end_regime: Dominant regime at episode end  
        - spans_transition: True if episode crosses regime boundary
        - regime_context: Regime context flag for filtering false positives
        """
        with Span("episodes.detect", n_samples=len(series), n_detectors=len(streams)):
            if len(series) == 0:
                return pd.DataFrame()

            x = np.asarray(series, dtype=float)
            finite_mask = np.isfinite(x)
            if not finite_mask.any():
                return pd.DataFrame()

            # ROBUST BASELINE: Use median/MAD instead of mean/std
            # This makes episode detection robust to training data containing faults
            mu = float(np.nanmedian(x))
            if not np.isfinite(mu):
                mu = 0.0
            mad = float(np.nanmedian(np.abs(x - mu)))
            sd = mad * 1.4826  # Scale MAD to std-equivalent
            if not np.isfinite(sd) or sd <= 1e-9:
                sd = 1.0
            # NOTE: k_sigma/h_sigma are retained in EpisodeParams for potential future CUSUM mode,
            # but current implementation uses hysteresis (z_on/z_off) exclusively.
            # Hysteresis is preferred for rotary equipment where full fault envelope matters.
            
            # P0-FIX (v11.1.6): Proper hysteresis-based episode detection
            # Episode semantics for rotary equipment:
            #   START: |z| exceeds onset threshold (z_on) for min_onset samples
            #   END:   |z| falls below release threshold (z_off) for min_release samples
            # This captures the full fault envelope, not just alarm onset
            
            # Base hysteresis thresholds (configurable via EpisodeParams)
            base_z_on = getattr(self.ep, 'z_on', 2.0)      # Onset threshold (sigma units)
            base_z_off = getattr(self.ep, 'z_off', 1.0)    # Release threshold (sigma units)
            min_onset = getattr(self.ep, 'min_onset', 2)    # Samples above z_on to start
            min_release = getattr(self.ep, 'min_release', 3)  # Samples below z_off to end
            
            # P3-FIX (v11.1.6): Per-regime threshold adaptation
            # Transient regimes (regime=-1 or UNKNOWN) get relaxed thresholds to reduce false positives
            # This is critical for rotary equipment with startup/shutdown transients
            regime_threshold_multipliers = self.ep.regime_threshold_mult
            
            # Define n_samples for array allocation
            n_samples = len(x)
            
            # Pre-compute per-sample thresholds based on regime
            z_on_arr = np.full(n_samples, base_z_on, dtype=np.float64)
            z_off_arr = np.full(n_samples, base_z_off, dtype=np.float64)
            
            if regime_labels is not None and len(regime_labels) == n_samples:
                for regime_id, mult in regime_threshold_multipliers.items():
                    regime_mask = (regime_labels == regime_id)
                    if regime_mask.any():
                        z_on_arr[regime_mask] = base_z_on * mult
                        z_off_arr[regime_mask] = base_z_off * mult
                        Console.debug(
                            f"Regime {regime_id}: threshold multiplier {mult:.2f} applied to "
                            f"{regime_mask.sum()} samples", component="EPISODES"
                        )
            
            # Normalize x to z-scores for threshold comparison
            z = (x - mu) / sd
            z = np.nan_to_num(z, nan=0.0, posinf=10.0, neginf=-10.0)
            abs_z = np.abs(z)
            
            # Track episode state with hysteresis
            # State machine: IDLE -> ONSET_PENDING -> ACTIVE -> RELEASE_PENDING -> IDLE
            STATE_IDLE = 0
            STATE_ONSET_PENDING = 1
            STATE_ACTIVE = 2
            STATE_RELEASE_PENDING = 3
            
            state = STATE_IDLE
            onset_count = 0
            release_count = 0
            episode_start_idx = 0
            pending_start_idx = 0
            
            episodes = []
            episode_directions = []  # Track if episode is positive or negative deviation
            
            for i in range(n_samples):
                z_val = abs_z[i]
                z_signed = z[i]
                
                # P3-FIX: Use per-sample thresholds (regime-aware)
                z_on = z_on_arr[i]
                z_off = z_off_arr[i]
                
                if state == STATE_IDLE:
                    if z_val >= z_on:
                        state = STATE_ONSET_PENDING
                        onset_count = 1
                        pending_start_idx = i
                        
                elif state == STATE_ONSET_PENDING:
                    if z_val >= z_on:
                        onset_count += 1
                        if onset_count >= min_onset:
                            # Confirmed episode start
                            state = STATE_ACTIVE
                            episode_start_idx = pending_start_idx
                    else:
                        # False alarm, reset
                        state = STATE_IDLE
                        onset_count = 0
                        
                elif state == STATE_ACTIVE:
                    if z_val < z_off:
                        state = STATE_RELEASE_PENDING
                        release_count = 1
                        pending_end_idx = i - 1  # Last sample still in episode
                    # Stay active if above release threshold
                    
                elif state == STATE_RELEASE_PENDING:
                    if z_val < z_off:
                        release_count += 1
                        if release_count >= min_release:
                            # Confirmed episode end
                            episode_end_idx = i - min_release  # End before release period
                            episode_end_idx = max(episode_start_idx, episode_end_idx)
                            length = episode_end_idx - episode_start_idx + 1
                            if length >= self.ep.min_len:
                                episodes.append((episode_start_idx, episode_end_idx))
                                # Determine direction: positive or negative deviation
                                episode_z = z[episode_start_idx:episode_end_idx+1]
                                direction = "high" if np.nanmean(episode_z) > 0 else "low"
                                episode_directions.append(direction)
                            state = STATE_IDLE
                            release_count = 0
                    else:
                        # Back above release threshold, stay active
                        state = STATE_ACTIVE
                        release_count = 0
            
            # Handle episode still active at end of data
            if state in (STATE_ACTIVE, STATE_RELEASE_PENDING):
                episode_end_idx = n_samples - 1
                length = episode_end_idx - episode_start_idx + 1
                if length >= self.ep.min_len:
                    episodes.append((episode_start_idx, episode_end_idx))
                    episode_z = z[episode_start_idx:episode_end_idx+1]
                    direction = "high" if np.nanmean(episode_z) > 0 else "low"
                    episode_directions.append(direction)
            
            # Gap-merge nearby episodes (same direction only for correctness)
            merged = []
            merged_directions = []
            for idx, (s, e) in enumerate(episodes):
                direction = episode_directions[idx] if idx < len(episode_directions) else "unknown"
                if not merged:
                    merged.append([s, e])
                    merged_directions.append(direction)
                    continue
                ps, pe = merged[-1]
                prev_direction = merged_directions[-1] if merged_directions else "unknown"
                # Only merge episodes with same direction (high/high or low/low)
                if s - pe - 1 <= self.ep.gap_merge and direction == prev_direction:
                    merged[-1][1] = e
                else:
                    merged.append([s, e])
                    merged_directions.append(direction)

            raw_idx = series.index
            has_dt_index = isinstance(raw_idx, pd.DatetimeIndex)
            idx = raw_idx
            if not has_dt_index:
                try:
                    inferred_type = getattr(raw_idx, "inferred_type", "") or ""
                    if "date" in inferred_type:
                        dt_idx = pd.to_datetime(raw_idx, errors="coerce")
                        if isinstance(dt_idx, pd.DatetimeIndex) and not dt_idx.isna().all():
                            idx = dt_idx
                            has_dt_index = True
                except Exception:
                    pass

            # PERF-FIX (v11.1.7): Precompute global baseline statistics for feature attribution
            # This avoids recomputing median/MAD for each episode (was causing 700s+ overhead)
            # PERF-FIX (v11.15.2): Precompute the FULL feature z-score matrix as numpy array once.
            # Per-episode attribution then just slices rows and calls np.nanmean(abs, axis=0),
            # eliminating the 5789 pandas Series.fillna() calls that caused 191s in coldstart.
            global_feature_medians: Optional[pd.Series] = None
            global_feature_mads: Optional[pd.Series] = None
            global_feature_z_np: Optional[np.ndarray] = None   # shape (n_samples, n_numeric_cols)
            global_numeric_cols_list: Optional[list] = None    # column names aligned to z_np axis-1
            if original_features is not None and not original_features.empty:
                _numeric_df = original_features.select_dtypes(include=[np.number])
                if not _numeric_df.empty:
                    global_feature_medians = _numeric_df.median()
                    global_feature_mads = (_numeric_df - global_feature_medians).abs().median()
                    global_feature_mads = global_feature_mads.replace(0, 1e-6)  # Avoid div by zero
                    # Precompute z-score matrix as contiguous float32 array for fast row-slicing
                    _z_np = ((_numeric_df.values - global_feature_medians.values) /
                             global_feature_mads.values).astype(np.float32)
                    global_feature_z_np = np.nan_to_num(_z_np, nan=0.0, posinf=0.0, neginf=0.0)
                    global_numeric_cols_list = list(_numeric_df.columns)

            rows = []
            for i, (s, e) in enumerate(merged):
                start_ts = idx[max(0, s)]
                end_ts = idx[min(len(idx) - 1, e)]
                if has_dt_index and pd.notna(start_ts) and pd.notna(end_ts):
                    duration_s = (end_ts - start_ts).total_seconds()
                else:
                    duration_s = float(e - s + 1)
                
                # Filter out short-duration episodes (only when real timestamps are available)
                if has_dt_index and duration_s < self.ep.min_duration_s:
                    continue
                
                # Get episode direction from merged_directions
                episode_direction = merged_directions[i] if i < len(merged_directions) else "unknown"
                
                # --- Culprit Attribution Logic (P1-FIX: Two-sided) ---
                episode_streams = {k: v[s:e+1] for k, v in streams.items()}
                
                # P1-FIX (v11.1.6): Find detector with highest ABSOLUTE mean score
                # This correctly handles both positive (above-normal) and negative (below-normal) episodes
                max_abs_score = -np.inf
                primary_detector = "unknown"
                detector_direction = "unknown"
                for name, scores in episode_streams.items():
                    mean_score = np.nanmean(scores)
                    if not np.isfinite(mean_score):
                        continue
                    abs_score = abs(mean_score)
                    if abs_score > max_abs_score:
                        max_abs_score = abs_score
                        primary_detector = name
                        detector_direction = "high" if mean_score > 0 else "low"

                # For multivariate models, find the top contributing sensor
                culprits_raw = primary_detector
                if 'pca' in primary_detector or 'mhal' in primary_detector:
                    # P2-FIX (v11.1.6): Improved PCA attribution using absolute deviation
                    # PERF-FIX (v11.15.2): Use precomputed numpy z-score matrix; slice rows for
                    # the episode window and call np.nanmean(abs, axis=0) once.  Eliminates
                    # 5789 pandas Series.fillna() calls that were costing 191s in coldstart.
                    top_feature: Optional[str] = None
                    if global_feature_z_np is not None and global_numeric_cols_list is not None:
                        ep_slice = global_feature_z_np[s:e+1]          # shape (ep_len, n_cols)
                        if ep_slice.shape[0] > 0:
                            abs_mean_z = np.abs(ep_slice).mean(axis=0)  # shape (n_cols,)
                            best_idx = int(np.argmax(abs_mean_z))
                            top_feature = global_numeric_cols_list[best_idx]
                    if top_feature:
                        culprit_sensor = Fuser._get_base_sensor(top_feature)
                        culprits_raw = f"{primary_detector}({culprit_sensor})"
                
                # P3-FIX: OMR Attribution (Pure ML Context)
                elif 'omr' in primary_detector and omr_contributions is not None:
                    # OMR contributions are model residuals (actual - predicted)
                    # We find the sensor with the highest mean contribution during the episode
                    try:
                        # Slice contributions to episode window
                        ep_contrib = omr_contributions.iloc[s:e+1]
                        if not ep_contrib.empty:
                            # Find column with max absolute mean contribution
                            top_sensor = ep_contrib.abs().mean().idxmax()
                            culprits_raw = f"{primary_detector}({top_sensor})"
                    except Exception:
                        pass  # Fallback to generic label if lookup fails

                # Format culprit with human-readable label
                culprits = format_culprit_label(culprits_raw, use_short=False)
                
                # Calculate fused score statistics for the episode
                episode_fused = x[s:e+1]
                # P1-FIX: Track both positive and negative peaks for two-sided analysis
                peak_fused_z = float(np.nanmax(np.abs(episode_fused))) if len(episode_fused) > 0 else 0.0
                avg_fused_z = float(np.nanmean(episode_fused)) if len(episode_fused) > 0 else 0.0
                min_fused_z = float(np.nanmin(episode_fused)) if len(episode_fused) > 0 else 0.0
                max_fused_z = float(np.nanmax(episode_fused)) if len(episode_fused) > 0 else 0.0
                
                # v10.1.0: Episode-Regime Correlation
                # Extract regime context for this episode
                start_regime = -1
                end_regime = -1
                spans_transition = False
                regime_context = "unknown"
                severity_multiplier = 1.0  # v11.3.0: Severity adjustment factor
                
                if regime_labels is not None and len(regime_labels) > e:
                    episode_regimes = regime_labels[s:e+1]
                    
                    # Get dominant regime at start and end
                    start_regime = int(episode_regimes[0]) if len(episode_regimes) > 0 else -1
                    end_regime = int(episode_regimes[-1]) if len(episode_regimes) > 0 else -1
                    
                    # Check if episode spans multiple regimes
                    unique_regimes = np.unique(episode_regimes)
                    spans_transition = len(unique_regimes) > 1
                    
                    # v11.3.0: Classify transition type instead of dismissing as false positive
                    # Rule R3: Pre-fault and post-fault are DISTINCT regimes
                    if spans_transition:
                        # Episode spans regime change - determine what kind
                        if peak_fused_z > 5.0:
                            # High z-score during transition = health state change (fault)
                            regime_context = "health_degradation"
                            severity_multiplier = 1.2  # BOOST severity - this is important!
                        elif avg_fused_z < 2.5:
                            # Low average z-score during transition = normal mode switch
                            regime_context = "operating_mode"
                            severity_multiplier = 0.9  # REDUCE severity - expected behavior
                        else:
                            # Moderate z-score = ambiguous, classify as health transition
                            regime_context = "health_transition"
                            severity_multiplier = 1.1
                    elif len(unique_regimes) == 1:
                        # Single regime - genuine anomaly within stable operating mode
                        regime_context = "stable"
                        severity_multiplier = 1.0
                    else:
                        regime_context = "unknown"
                        severity_multiplier = 1.0
                    
                    # Apply severity adjustment to peak and average z-scores
                    peak_fused_z = peak_fused_z * severity_multiplier
                    avg_fused_z = avg_fused_z * severity_multiplier
                
                rows.append({
                    "start_ts": start_ts, 
                    "end_ts": end_ts, 
                    "duration_s": duration_s, 
                    "len": int(e - s + 1), 
                    "culprits": culprits,
                    "peak_fused_z": peak_fused_z,
                    "avg_fused_z": avg_fused_z,
                    "min_fused_z": min_fused_z,  # v11.1.6: Added for two-sided analysis
                    "max_fused_z": max_fused_z,  # v11.1.6: Added for two-sided analysis
                    "fault_direction": episode_direction,  # v11.1.6: P1-FIX high/low deviation
                    "start_regime": start_regime,
                    "end_regime": end_regime,
                    "spans_transition": spans_transition,
                    "regime_context": regime_context
                })
            return pd.DataFrame(rows)


def compute_episode_params(streams: Dict[str, np.ndarray], cfg: Dict[str, Any]) -> EpisodeParams:
    """Compute CUSUM episode detection parameters from current stream statistics.

    Computed once in run_fusion_pipeline() and shared across baseline, train, and
    score passes to avoid redundant computation and duplicate logging.
    """
    epcfg = (cfg or {}).get("episodes", {})
    cpd = epcfg.get("cpd", {}) if isinstance(epcfg, dict) else {}

    base_k_sigma = float(cpd.get("k_sigma", 0.5))
    base_h_sigma = float(cpd.get("h_sigma", 5.0))
    k_sigma = base_k_sigma
    h_sigma = base_h_sigma

    min_len = int(epcfg.get("min_len", 3))
    gap_merge = int(epcfg.get("gap_merge", 5))
    min_duration_s = float(epcfg.get("min_duration_s", 60.0))
    z_on = float(epcfg.get("z_on", 2.0))
    z_off = float(epcfg.get("z_off", 1.0))
    min_onset = int(epcfg.get("min_onset", 2))
    min_release = int(epcfg.get("min_release", 3))

    auto_tune_cfg = cpd.get("auto_tune", {})
    all_values: List[np.ndarray] = []
    for stream in streams.values():
        finite_mask = np.isfinite(stream)
        if finite_mask.any():
            all_values.append(stream[finite_mask])

    statistic_vals = np.concatenate(all_values) if all_values else np.array([], dtype=float)

    if statistic_vals.size:
        statistic_median = float(np.nanmedian(statistic_vals))
        statistic_mad = float(np.nanmedian(np.abs(statistic_vals - statistic_median)))
        std = max(statistic_mad * 1.4826, 1e-3)
        p50 = float(np.nanpercentile(statistic_vals, 50))
        p95 = float(np.nanpercentile(statistic_vals, 95))
        spread = max(p95 - p50, 1e-3)

        # k_factor and h_factor are dimensionless multipliers; detect_episodes()
        # applies the actual scale based on stream dispersion.
        k_factor = float(auto_tune_cfg.get("k_factor", 0.5))
        h_factor = float(auto_tune_cfg.get("h_factor", 5.0))
        k_min = float(auto_tune_cfg.get("k_min", 0.25))
        k_max = float(auto_tune_cfg.get("k_max", max(base_k_sigma, 2.0)))
        h_min = float(auto_tune_cfg.get("h_min", 3.0))
        h_max = float(auto_tune_cfg.get("h_max", max(base_h_sigma, 10.0)))

        spread_ratio = spread / std if std > 1e-6 else 1.0
        adaptive_h_factor = h_factor * min(1.5, max(0.8, spread_ratio / 2.0))
        k_sigma = float(np.clip(k_factor, k_min, k_max))
        h_sigma = float(np.clip(adaptive_h_factor, h_min, h_max))

        Console.info(
            f"CUSUM auto-tuned: k_sigma={base_k_sigma:.3f}->{k_sigma:.3f}, "
            f"h_sigma={base_h_sigma:.3f}->{h_sigma:.3f} (spread_ratio={spread_ratio:.2f})",
            component="FUSE",
        )
    else:
        Console.warn(
            "CUSUM auto-tune skipped: no finite stream values",
            component="FUSE",
            n_streams=len(streams),
        )

    return EpisodeParams(
        k_sigma=k_sigma,
        h_sigma=h_sigma,
        min_len=min_len,
        gap_merge=gap_merge,
        min_duration_s=min_duration_s,
        z_on=z_on,
        z_off=z_off,
        min_onset=min_onset,
        min_release=min_release,
    )

def compute_discounted_weights(
    weights: Dict[str, float],
    streams: Dict[str, np.ndarray],
    quiet: bool = False,
    omr_correlation_disable_threshold: float = 0.95,
) -> Dict[str, float]:
    """Apply Spearman-based correlation discount to detector weights.

    Detectors that are strongly correlated (|r| > 0.5) with others receive
    a downward weight adjustment to prevent double-counting of redundant signal.

    v11.15.15: If GMM or IForest has Spearman |r| >= omr_correlation_disable_threshold
    with OMR, and OMR is present and enabled, the correlated detector is fully disabled
    (weight set to 0.0) rather than just discounted. This prevents near-identical signals
    from inflating the ensemble's effective count.

    Computed once in run_fusion_pipeline() and passed into Fuser.fuse();
    never computed inside fuse() per-call.

    Returns a new dict of (unnormalized) discounted weights keyed by detector name.
    Normalization happens inside Fuser.fuse() over the detectors actually present.
    """
    keys = [k for k in streams if streams[k] is not None]
    w_raw = {k: float(weights.get(k, 0.0)) for k in keys}

    if len(keys) < 2:
        return w_raw

    correlation_count: Dict[str, int] = {k: 0 for k in keys}
    correlation_sum: Dict[str, float] = {k: 0.0 for k in keys}
    # v11.15.15: Track per-pair correlations for OMR disable logic
    pair_corr: Dict[tuple, float] = {}  # (k1, k2) -> abs(spearman_r)
    pairs_checked = 0
    pairs_correlated = 0

    zs = {k: Fuser._sanitize(np.asarray(streams[k], dtype=float)) for k in keys}
    sorted_keys = sorted(keys)
    for i, k1 in enumerate(sorted_keys):
        for k2 in sorted_keys[i + 1:]:
            arr1, arr2 = zs[k1], zs[k2]
            valid_mask = np.isfinite(arr1) & np.isfinite(arr2)
            if valid_mask.sum() > 10:
                # P3-FIX (v11.1.6): Spearman over Pearson - robust to outliers.
                valid_1, valid_2 = arr1[valid_mask], arr2[valid_mask]
                if np.unique(valid_1).size < 2 or np.unique(valid_2).size < 2:
                    continue
                pairs_checked += 1
                spearman_result = spearmanr(valid_1, valid_2)
                corr = float(spearman_result.correlation)  # type: ignore[union-attr]
                if np.isfinite(corr) and abs(corr) > 0.5:
                    pairs_correlated += 1
                    correlation_count[k1] += 1
                    correlation_count[k2] += 1
                    correlation_sum[k1] += abs(corr)
                    correlation_sum[k2] += abs(corr)
                    pair_corr[(k1, k2)] = abs(corr)
                    if not quiet:
                        Console.debug(
                            f"Detector Spearman correlation {k1}<->{k2}: {corr:.2f}",
                            component="FUSE",
                        )

    for k in keys:
        if correlation_count[k] > 0:
            avg_corr = correlation_sum[k] / correlation_count[k]
            # At avg_corr=0.8, discount=15%; capped at 30%
            discount_factor = min(0.3, (avg_corr - 0.5) * 0.5)
            w_raw[k] *= (1 - discount_factor)
            if not quiet:
                Console.debug(
                    f"Detector {k}: correlated with {correlation_count[k]} others, "
                    f"avg_corr={avg_corr:.2f}, discount={discount_factor:.1%}",
                    component="FUSE",
                )

    # v11.15.15: Full disable for GMM/IForest when nearly identical to OMR.
    # When Spearman |r| >= omr_correlation_disable_threshold, the redundant detector
    # contributes nothing new — set its weight to 0 instead of a small discount.
    _DISABLE_CANDIDATES = {"gmm", "iforest"}
    _OMR_KEY = "omr"
    if _OMR_KEY in keys and omr_correlation_disable_threshold < 1.0:
        for candidate in _DISABLE_CANDIDATES:
            if candidate not in keys:
                continue
            pair = tuple(sorted([candidate, _OMR_KEY]))
            r = pair_corr.get(pair, 0.0)
            if r >= omr_correlation_disable_threshold:
                if not quiet:
                    Console.info(
                        f"Disabling {candidate}: Spearman r={r:.3f} with OMR "
                        f">= threshold {omr_correlation_disable_threshold:.2f} "
                        f"— OMR already captures this signal",
                        component="FUSE",
                        disabled_detector=candidate,
                        omr_correlation=r,
                        threshold=omr_correlation_disable_threshold,
                    )
                w_raw[candidate] = 0.0

    if pairs_correlated > 0 and not quiet:
        Console.info(
            f"{pairs_correlated}/{pairs_checked} detector pairs correlated, "
            f"weight adjustments applied",
            component="FUSE",
            pairs_checked=pairs_checked,
            pairs_correlated=pairs_correlated,
        )

    return w_raw


# ============================================================================
# Episode Schema Normalization (moved from acm_main.py v11.2)
# ============================================================================

def normalize_episodes_schema(
    episodes: pd.DataFrame,
    frame: pd.DataFrame,
    equip: str = "",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize episodes DataFrame schema for report/export.
    
    This helper ensures episodes have consistent columns and computes:
    - episode_id (if missing)
    - start_ts/end_ts from frame index
    - regime labels (majority vote per episode)
    - regime_state (majority state per episode)
    - severity (based on regime_state)
    - duration_s and duration_hours
    
    Args:
        episodes: Raw episodes DataFrame from fusion
        frame: Scored frame DataFrame with datetime index
        equip: Equipment name for logging
        
    Returns:
        Tuple of (normalized_episodes, sorted_frame)
    """
    from utils.timestamp_utils import nearest_indexer
    
    # Create defensive copy to avoid modifying caller's data
    episodes = episodes.copy()
    
    # Ensure required columns exist
    if "episode_id" not in episodes.columns:
        episodes.insert(0, "episode_id", np.arange(1, len(episodes) + 1, dtype=int))
    if "severity" not in episodes.columns:
        episodes["severity"] = "info"
    if "regime" not in episodes.columns:
        episodes["regime"] = ""
    if "start_ts" not in episodes.columns:
        episodes["start_ts"] = pd.NaT
    if "end_ts" not in episodes.columns:
        episodes["end_ts"] = pd.NaT
    
    # Get index series from episodes
    start_idx_series = episodes.get("start")
    end_idx_series = episodes.get("end")
    
    # Ensure frame is sorted before any indexing operations
    if not frame.index.is_monotonic_increasing:
        Console.warn("Sorting frame index for timestamp mapping", component="EPISODE",
                     equip=equip)
        frame = frame.sort_index()
    idx_array = frame.index.to_numpy()

    # Prefer nearest mapping; preserve NaT (avoid clip-to-zero artefacts)
    if start_idx_series is None:
        # Deduplicate frame index before episode mapping to prevent aggregation errors
        if not frame.index.is_unique:
            Console.warn(f"Deduplicating {len(frame)} - {frame.index.nunique()} = {len(frame) - frame.index.nunique()} duplicate timestamps", component="EPISODES",
                         equip=equip)
            frame = frame.groupby(frame.index).first()
            idx_array = frame.index.to_numpy()

        start_positions = nearest_indexer(frame.index, episodes["start_ts"], label="EPISODE.start")
        start_idx_series = pd.Series(start_positions, index=episodes.index, dtype="int64")
    if end_idx_series is None:
        end_positions = nearest_indexer(frame.index, episodes["end_ts"], label="EPISODE.end")
        end_idx_series = pd.Series(end_positions, index=episodes.index, dtype="int64")
    
    start_idx_series = start_idx_series.fillna(-1).astype(int)
    end_idx_series = end_idx_series.fillna(-1).astype(int)
    
    if len(idx_array):
        start_idx = start_idx_series.clip(-1, len(idx_array) - 1).to_numpy()
        end_idx = end_idx_series.clip(-1, len(idx_array) - 1).to_numpy()
        s_idx_safe = np.where(start_idx >= 0, start_idx, 0)
        e_idx_safe = np.where(end_idx >= 0, end_idx, 0)
        # Create datetime arrays, use pd.NaT for invalid indices
        start_times = idx_array[s_idx_safe]
        end_times = idx_array[e_idx_safe]
        episodes["start_ts"] = pd.Series(start_times, index=episodes.index, dtype='datetime64[ns]')
        episodes["end_ts"] = pd.Series(end_times, index=episodes.index, dtype='datetime64[ns]')
        # Set NaT for invalid indices
        episodes.loc[start_idx < 0, "start_ts"] = pd.NaT
        episodes.loc[end_idx < 0, "end_ts"] = pd.NaT
    else:
        start_idx = np.zeros(len(episodes), dtype=int)
        end_idx = np.zeros(len(episodes), dtype=int)
        episodes["start_ts"] = pd.NaT
        episodes["end_ts"] = pd.NaT

    # Map regime labels to episodes (majority vote)
    label_series = frame.get("regime_label")
    state_series = frame.get("regime_state")
    if label_series is not None:
        label_array = label_series.to_numpy()
        state_array = state_series.to_numpy() if state_series is not None else None
        regime_vals: List[Any] = []
        regime_states: List[str] = []
        for s_idx, e_idx in zip(start_idx, end_idx):
            if len(label_array) == 0:
                regime_vals.append(-1)
                regime_states.append("unknown")
                continue
            s_clamped = int(np.clip(s_idx, 0, len(label_array) - 1))
            e_clamped = int(np.clip(e_idx, 0, len(label_array) - 1))
            if e_clamped < s_clamped:
                e_clamped = s_clamped
            slice_labels = label_array[s_clamped:e_clamped + 1]
            if slice_labels.size:
                # Filter out negative labels (UNKNOWN regime = -1) for bincount
                valid_labels = slice_labels[slice_labels >= 0]
                if valid_labels.size > 0:
                    counts = np.bincount(valid_labels.astype(int))
                    majority_label = int(np.argmax(counts))
                else:
                    # All labels are UNKNOWN (-1)
                    majority_label = -1
            else:
                majority_label = -1
            regime_vals.append(majority_label)
            if state_array is not None and slice_labels.size:
                slice_states = state_array[s_clamped:e_clamped + 1]
                values, counts_arr = np.unique(slice_states, return_counts=True)
                majority_state = str(values[np.argmax(counts_arr)])
            else:
                majority_state = "unknown"
            regime_states.append(majority_state)
        episodes["regime"] = regime_vals
        episodes["regime_state"] = regime_states
    else:
        episodes["regime_state"] = "unknown"

    # Map regime_state to severity
    severity_map = {"critical": "critical", "suspect": "warning", "warning": "warning"}
    severity_override = episodes["regime_state"].map(lambda s: severity_map.get(str(s)))
    episodes["severity"] = severity_override.fillna(episodes["severity"])

    # Calculate duration
    start_ts = pd.to_datetime(episodes["start_ts"], errors="coerce")
    end_ts = pd.to_datetime(episodes["end_ts"], errors="coerce")
    episodes["duration_s"] = (end_ts - start_ts).dt.total_seconds()
    episodes["duration_hours"] = (
        pd.to_numeric(episodes["duration_s"], errors="coerce").fillna(0.0).astype(float) / 3600.0
    )
    
    # Sort and finalize
    episodes = episodes.sort_values(["start_ts", "end_ts", "episode_id"]).reset_index(drop=True)
    episodes["regime"] = episodes["regime"].astype(str)
    
    return episodes, frame


# ============================================================================
# Fusion Pipeline Orchestration (v11.2)
# ============================================================================

@dataclass
class FusionResult:
    """Result of fusion pipeline execution."""
    fused_scores: np.ndarray
    episodes: pd.DataFrame
    weights_used: Dict[str, float]
    auto_tuned: bool
    tuning_diagnostics: Optional[Dict[str, Any]] = None
    train_fused: Optional[np.ndarray] = None


DEFAULT_WEIGHTS = {
    "pca_spe_z": 0.28,
    "pca_t2_z": 0.18,
    "ar1_z": 0.18,
    "iforest_z": 0.14,
    "gmm_z": 0.05,
    "omr_z": 0.09,
    "ewm_z": 0.08,   # v11.16.0: EWM zero-day baseline (always-on from observation 2)
}


def prepare_fusion_inputs(
    frame: pd.DataFrame,
    cfg: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, np.ndarray], Dict[str, float], List[str]]:
    """
    Prepare and validate fusion inputs.
    
    Returns:
        (present_streams, normalized_weights, missing_detectors)
    """
    weights = (cfg or {}).get("fusion", {}).get("weights", DEFAULT_WEIGHTS)
    
    # Validate weight keys
    invalid_keys = [k for k in weights.keys() if not k.endswith('_z')]
    if invalid_keys:
        raise ValueError(f"Invalid detector keys in fusion.weights: {invalid_keys}")
    
    # Find available streams
    avail = set(frame.columns)
    missing = [k for k in weights.keys() if k not in avail]
    present = {k: frame[k].to_numpy(copy=False) for k in weights.keys() if k in avail}
    
    if not present:
        raise RuntimeError("No valid input streams for fusion")
    
    # Renormalize weights for present streams only
    if missing:
        present_weights = {k: weights[k] for k in present.keys()}
        total = sum(present_weights.values())
        if total > 0:
            weights = {k: v / total for k, v in present_weights.items()}
        else:
            weights = {k: 1.0 / len(present) for k in present.keys()}
    
    return present, dict(weights), missing


def run_fusion_pipeline(
    frame: pd.DataFrame,
    train_frame: Optional[pd.DataFrame],
    score_data: pd.DataFrame,
    train_data: Optional[pd.DataFrame],
    cfg: Optional[Dict[str, Any]],
    score_regime_labels: Optional[np.ndarray] = None,
    train_regime_labels: Optional[np.ndarray] = None,
    output_manager: Optional[Any] = None,
    previous_weights: Optional[Dict[str, float]] = None,
    omr_contributions: Optional[pd.DataFrame] = None,
    equip: str = "",
) -> FusionResult:
    """
    Execute complete fusion pipeline: validate -> auto-tune -> fuse -> detect episodes.
    
    Args:
        frame: Score data with detector z-score columns
        train_frame: Train data with detector z-score columns (for threshold calc)
        score_data: Original score features
        train_data: Original train features
        cfg: Configuration
        score_regime_labels: Regime labels for score data
        train_regime_labels: Regime labels for train data
        output_manager: For writing fusion metrics
        previous_weights: Previous run's weights for comparison
        equip: Equipment name for logging
    
    Returns:
        FusionResult with fused scores, episodes, weights used, and diagnostics
    """
    # 1. Prepare inputs
    present, weights, missing = prepare_fusion_inputs(frame, cfg)
    if missing:
        Console.warn(f"Missing streams: {missing}", component="FUSE", equip=equip)

    effective_cfg: Dict[str, Any] = cfg if cfg is not None else {}

    # 2. Pre-compute episode params and correlation-discounted weights ONCE.
    episode_params = compute_episode_params(present, effective_cfg)
    _omr_disable_thresh = float(
        (effective_cfg.get("fusion", {}) or {}).get("omr_correlation_disable_threshold", 0.95)
    )
    discounted_weights = compute_discounted_weights(
        weights, present, omr_correlation_disable_threshold=_omr_disable_thresh
    )

    # 3. Auto-tune detector weights (baseline fuse pass, no episodes)
    auto_tuned = False
    tuning_diagnostics = None
    with Span("fusion.baseline", n_detectors=len(present), n_samples=len(score_data)):
        fused_baseline = Fuser(weights=weights, ep=episode_params).fuse(
            present, score_data, discounted_weights=discounted_weights
        )
    fused_baseline_np = np.asarray(fused_baseline, dtype=np.float32).reshape(-1)

    tuned, diagnostics = tune_detector_weights(
        streams=present, fused=fused_baseline_np,
        current_weights=weights, cfg=cfg,
    )

    if diagnostics.get("enabled"):
        weights = tuned
        auto_tuned = True
        tuning_diagnostics = diagnostics
        # Recompute discounted weights with the newly tuned base weights
        discounted_weights = compute_discounted_weights(
            weights, present, quiet=True,
            omr_correlation_disable_threshold=_omr_disable_thresh,
        )

        if output_manager:
            output_manager.write_fusion_metrics(
                fusion_weights=weights,
                tuning_diagnostics=diagnostics,
                previous_weights=previous_weights,
            )

    # 4. Fuse training data (for threshold baseline, no episodes needed)
    train_fused = None
    if train_frame is not None and train_data is not None and not train_data.empty:
        train_present = {k: train_frame[k].to_numpy(copy=False)
                        for k in present.keys() if k in train_frame.columns}
        if train_present:
            # Train uses its own discounted weights; Spearman correlations may
            # differ on the training population vs the current scoring window.
            train_discounted = compute_discounted_weights(
                weights, train_present,
                omr_correlation_disable_threshold=_omr_disable_thresh,
            )
            with Span("fusion.train", n_detectors=len(train_present), n_samples=len(train_data)):
                train_fused_series = Fuser(weights=weights, ep=episode_params).fuse(
                    train_present, train_data, discounted_weights=train_discounted
                )
            train_fused = np.asarray(train_fused_series, dtype=np.float32).reshape(-1)

    # 5. Score fusion with episode detection
    with Span("fusion.score", n_detectors=len(present), n_samples=len(score_data)):
        score_fuser = Fuser(weights=weights, ep=episode_params)
        fused = score_fuser.fuse(present, score_data, discounted_weights=discounted_weights)
        episodes = score_fuser.detect_episodes(
            fused, present, score_data, regime_labels=score_regime_labels, omr_contributions=omr_contributions
        )
    fused_np = np.asarray(fused, dtype=np.float32).reshape(-1)

    if fused_np.shape[0] != len(frame.index):
        raise RuntimeError(f"Fused length {fused_np.shape[0]} != frame length {len(frame.index)}")
    
    Console.info(
        f"Fusion: detectors={len(present)} | episodes={len(episodes)} | auto_tuned={auto_tuned}",
        component="FUSE"
    )
    
    return FusionResult(
        fused_scores=fused_np,
        episodes=episodes,
        weights_used=weights,
        auto_tuned=auto_tuned,
        tuning_diagnostics=tuning_diagnostics,
        train_fused=train_fused,
    )


def apply_fusion_result_and_record_metrics(
    frame: pd.DataFrame,
    train_frame: Optional[pd.DataFrame],
    fusion_result: "FusionResult",
    equip: str = "",
    record_detector_scores_fn: Optional[Callable[..., None]] = None,
    record_episode_fn: Optional[Callable[..., None]] = None,
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], pd.DataFrame, Dict[str, float]]:
    """
    Apply fusion outputs to score/train frames and emit observability metrics.
    """
    frame["fused"] = fusion_result.fused_scores
    episodes = fusion_result.episodes
    fusion_weights_used = fusion_result.weights_used

    if train_frame is not None and fusion_result.train_fused is not None:
        train_frame["fused"] = fusion_result.train_fused

    detector_scores = {
        "fused_z": float(fusion_result.fused_scores[-1]) if len(fusion_result.fused_scores) > 0 else 0.0
    }
    for det in ["ar1_z", "pca_spe_z", "pca_t2_z", "iforest_z", "gmm_z", "omr_z", "ewm_z"]:
        if det in frame.columns:
            detector_scores[det] = float(frame[det].iloc[-1])

    if record_detector_scores_fn is not None:
        record_detector_scores_fn(equip, detector_scores)
    if record_episode_fn is not None and len(episodes) > 0:
        record_episode_fn(equip, count=len(episodes), severity="warning")

    return frame, train_frame, episodes, fusion_weights_used


@dataclass
class FusionStageResult:
    """Result bundle for the full fusion stage."""
    frame: pd.DataFrame
    train_frame: Optional[pd.DataFrame]
    episodes: pd.DataFrame
    fusion_weights_used: Dict[str, float]


def run_fusion_stage(
    *,
    frame: pd.DataFrame,
    train_frame: Optional[pd.DataFrame],
    score_data: pd.DataFrame,
    train_data: Optional[pd.DataFrame],
    cfg: Optional[Dict[str, Any]],
    score_regime_labels: Optional[np.ndarray] = None,
    train_regime_labels: Optional[np.ndarray] = None,
    output_manager: Optional[Any] = None,
    previous_weights: Optional[Dict[str, float]] = None,
    omr_contributions: Optional[pd.DataFrame] = None,
    equip: str = "",
    record_detector_scores_fn: Optional[Callable[..., None]] = None,
    record_episode_fn: Optional[Callable[..., None]] = None,
) -> FusionStageResult:
    """
    Execute fusion pipeline and apply outputs to score/train frames.
    """
    fusion_result = run_fusion_pipeline(
        frame=frame,
        train_frame=train_frame,
        score_data=score_data,
        train_data=train_data,
        cfg=cfg,
        score_regime_labels=score_regime_labels,
        train_regime_labels=train_regime_labels,
        output_manager=output_manager,
        previous_weights=previous_weights,
        omr_contributions=omr_contributions,
        equip=equip,
    )

    frame, train_frame, episodes, fusion_weights_used = apply_fusion_result_and_record_metrics(
        frame=frame,
        train_frame=train_frame,
        fusion_result=fusion_result,
        equip=equip,
        record_detector_scores_fn=record_detector_scores_fn,
        record_episode_fn=record_episode_fn,
    )

    return FusionStageResult(
        frame=frame,
        train_frame=train_frame,
        episodes=episodes,
        fusion_weights_used=fusion_weights_used,
    )


@dataclass
class HealthStageResult:
    """Result bundle for calibration, fusion, thresholds, and regime postprocess stages."""
    frame: pd.DataFrame
    train_frame: pd.DataFrame
    episodes: pd.DataFrame
    fusion_weights_used: Dict[str, float]
    spe_p95_train: float
    t2_p95_train: float
    quality_ok: bool
    use_per_regime: bool
    context_assignment: ContextAssignment = field(default_factory=ContextAssignment)


def _representation_learning_blocked(
    *,
    representation_result: Optional[Any],
    representation_authority_active: bool,
) -> bool:
    if not representation_authority_active or representation_result is None:
        return False
    eligibility = getattr(representation_result, "eligibility", None)
    if eligibility is None:
        return False
    return bool(getattr(representation_result, "authoritative", False) and eligibility.learn_allowed is False)


def suppress_representation_scoring(
    *,
    frame: pd.DataFrame,
    episodes: pd.DataFrame,
    representation_result: Optional[Any],
    logger: Any = Console,
) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    if representation_result is None:
        return frame, episodes, False
    eligibility = getattr(representation_result, "eligibility", None)
    if eligibility is None:
        return frame, episodes, False
    if not bool(getattr(representation_result, "authoritative", False)):
        return frame, episodes, False
    if eligibility.score_allowed is not False:
        return frame, episodes, False

    suppressed_frame = frame.copy()
    for col in _SUPPRESSED_SCORE_COLUMNS:
        if col in suppressed_frame.columns:
            suppressed_frame[col] = np.nan

    suppressed_episodes = episodes.iloc[0:0].copy()
    logger.warn(
        "Representation authority suppressed downstream scoring outputs",
        component="REPRESENTATION",
        equip_id=getattr(representation_result, "equip_id", None),
        run_id=getattr(representation_result, "run_id", None),
        suppressed_reasons=list(getattr(eligibility, "suppressed_reason_codes", ()) or ()),
    )
    return suppressed_frame, suppressed_episodes, True


def run_health_stage(
    *,
    section_fn: Any,
    train: pd.DataFrame,
    score: pd.DataFrame,
    frame: pd.DataFrame,
    cfg: Dict[str, Any],
    regime_quality_ok: bool,
    train_regime_labels: Optional[np.ndarray],
    score_regime_labels: Optional[np.ndarray],
    pca_train_spe: Optional[np.ndarray],
    pca_train_t2: Optional[np.ndarray],
    detectors: Dict[str, Any],
    detector_flags: Dict[str, bool],
    cached_calibration_params: Optional[Dict[str, Any]],
    saved_model_version: Optional[int],
    output_manager: Any,
    logger: Any,
    equip: str,
    previous_weights: Optional[Dict[str, float]],
    omr_contributions_data: Optional[pd.DataFrame],
    record_detector_scores_fn: Optional[Callable[..., None]],
    record_episode_fn: Optional[Callable[..., None]],
    coldstart_complete: bool,
    equip_id: int,
    regime_model: Any,
    score_out: Dict[str, Any],
    sql_client: Any,
    run_id: Optional[str],
    cached_manifest: Optional[Dict[str, Any]],
    baseline_contamination_verdict: str = "unknown",
    score_all_detectors_fn: Optional[Any] = None,
    calibrate_all_detectors_fn: Optional[Any] = None,
    persist_calibration_params_fn: Optional[Any] = None,
    maybe_update_adaptive_thresholds_fn: Optional[Any] = None,
    run_regime_postprocess_stage_fn: Optional[Any] = None,
    auto_tune_parameters_fn: Optional[Any] = None,
    representation_result: Optional[Any] = None,
    representation_authority_active: bool = False,
) -> HealthStageResult:
    """
    Execute post-model health stages in pipeline order.
    """
    score_detectors_fn = score_all_detectors_fn
    calibrate_detectors_fn = calibrate_all_detectors_fn
    adaptive_thresholds_fn = maybe_update_adaptive_thresholds_fn
    regime_postprocess_fn = run_regime_postprocess_stage_fn
    auto_tune_fn = auto_tune_parameters_fn

    if score_detectors_fn is None or calibrate_detectors_fn is None:
        from core.detector_orchestrator import score_all_detectors as _score_all_detectors
        from core.detector_orchestrator import calibrate_all_detectors as _calibrate_all_detectors
        score_detectors_fn = score_detectors_fn or _score_all_detectors
        calibrate_detectors_fn = calibrate_detectors_fn or _calibrate_all_detectors

    if adaptive_thresholds_fn is None:
        from core.adaptive_thresholds import maybe_update_adaptive_thresholds as _adaptive_thresholds
        adaptive_thresholds_fn = _adaptive_thresholds

    if regime_postprocess_fn is None:
        from core.regimes import run_regime_postprocess_stage as _run_regime_postprocess_stage
        regime_postprocess_fn = _run_regime_postprocess_stage

    if auto_tune_fn is None:
        from core.model_evaluation import auto_tune_parameters as _auto_tune_parameters
        auto_tune_fn = _auto_tune_parameters

    learn_blocked = _representation_learning_blocked(
        representation_result=representation_result,
        representation_authority_active=representation_authority_active,
    )

    with section_fn("calibrate"):
        calibration_result = run_calibration_stage(
            train=train,
            frame=frame,
            cfg=cfg,
            regime_quality_ok=regime_quality_ok,
            train_regime_labels=train_regime_labels,
            score_regime_labels=score_regime_labels,
            pca_train_spe=pca_train_spe,
            pca_train_t2=pca_train_t2,
            detectors=detectors,
            detector_flags=detector_flags,
            cached_calibration_params=cached_calibration_params,
            saved_model_version=saved_model_version,
            score_all_detectors_fn=score_detectors_fn,
            calibrate_all_detectors_fn=calibrate_detectors_fn,
            persist_calibration_params_fn=persist_calibration_params_fn,
            output_manager=output_manager,
            logger=logger,
            equip=equip,
            baseline_contamination_verdict=baseline_contamination_verdict,
        )
        frame = calibration_result.frame
        train_frame = calibration_result.train_frame
        spe_p95_train = calibration_result.spe_p95_train
        t2_p95_train = calibration_result.t2_p95_train
        quality_ok = calibration_result.quality_ok
        use_per_regime = calibration_result.use_per_regime

    with section_fn("fusion"):
        fusion_stage = run_fusion_stage(
            frame=frame,
            train_frame=train_frame,
            score_data=score,
            train_data=train,
            cfg=cfg,
            score_regime_labels=score_regime_labels,
            train_regime_labels=train_regime_labels,
            output_manager=output_manager,
            previous_weights=previous_weights,
            omr_contributions=omr_contributions_data,
            equip=equip,
            record_detector_scores_fn=record_detector_scores_fn,
            record_episode_fn=record_episode_fn,
        )
        frame = fusion_stage.frame
        train_frame = fusion_stage.train_frame
        episodes = fusion_stage.episodes
        fusion_weights_used = fusion_stage.fusion_weights_used

    if learn_blocked:
        logger.info(
            "Representation authority skipped adaptive threshold update",
            component="REPRESENTATION",
            equip_id=equip_id,
            run_id=run_id,
        )
    else:
        with section_fn("thresholds.adaptive"):
            adaptive_thresholds_fn(
                train_frame=train_frame,
                train_data=train,
                cfg=cfg,
                equip_id=equip_id,
                output_manager=output_manager,
                regime_quality_ok=regime_quality_ok,
                baseline_contamination_verdict=baseline_contamination_verdict,
                logger=logger,
            )

    with section_fn("regimes.postprocess"):
        regime_post = regime_postprocess_fn(
            frame=frame,
            score_data=score,
            regime_model=regime_model,
            regime_quality_ok=regime_quality_ok,
            cfg=cfg,
            output_manager=output_manager,
            logger=logger,
        )
        frame = regime_post.frame
        context_assignment = getattr(regime_post, "context_assignment", ContextAssignment())

    if learn_blocked:
        logger.info(
            "Representation authority skipped auto tuning",
            component="REPRESENTATION",
            equip_id=equip_id,
            run_id=run_id,
        )
    else:
        auto_tune_fn(
            frame=frame,
            episodes=episodes,
            score_out=score_out,
            regime_quality_ok=regime_quality_ok,
            cfg=cfg,
            sql_client=sql_client,
            run_id=run_id,
            equip_id=equip_id,
            equip=equip,
            output_manager=output_manager,
            cached_manifest=cached_manifest,
        )

    return HealthStageResult(
        frame=frame,
        train_frame=train_frame,
        episodes=episodes,
        fusion_weights_used=fusion_weights_used,
        spe_p95_train=spe_p95_train,
        t2_p95_train=t2_p95_train,
        quality_ok=quality_ok,
        use_per_regime=use_per_regime,
        context_assignment=context_assignment,
    )

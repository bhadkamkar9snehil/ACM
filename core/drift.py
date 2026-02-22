# core/drift.py
"""
Change-point and drift detection module.

Implements online detectors to identify subtle but persistent shifts in a time series,
typically the fused anomaly score.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from typing import Any, Dict, Optional

from . import fuse


class CUSUMDetector:
    """
    Online change-point detection using the CUSUM algorithm.
    Detects small, sustained drifts from a baseline mean.
    """
    def __init__(self, threshold: float = 2.0, drift: float = 0.1):
        self.threshold = threshold
        self.drift = drift
        self.mean = 0.0
        self.std = 1.0
        self.sum_pos = 0.0
        self.sum_neg = 0.0

    def fit(self, x: np.ndarray) -> "CUSUMDetector":
        # v11.1.2: Use robust statistics (median/MAD) for CUSUM baseline
        # This allows CUSUM to work correctly even when training data contains faults
        self.mean = float(np.nanmedian(x))
        mad = float(np.nanmedian(np.abs(x - self.mean)))
        self.std = mad * 1.4826  # Scale MAD to be consistent with std for normal distribution

        # DRIFT-AUDIT-01: Guard against non-finite mean (e.g., all-NaN input)
        if not np.isfinite(self.mean):
            self.mean = 0.0
        if not np.isfinite(self.std) or self.std < 1e-9:
            self.std = 1.0
        # Reset accumulators so score() always starts from a clean state,
        # regardless of whether the detector object is reused across calls.
        self.sum_pos = 0.0
        self.sum_neg = 0.0
        return self

    def score(self, x: np.ndarray) -> np.ndarray:
        scores = np.zeros_like(x, dtype=np.float32)
        x_norm = (x - self.mean) / self.std
        # DRIFT-AUDIT-02: Handle NaN/inf in normalized values to prevent accumulation errors
        x_norm = np.nan_to_num(x_norm, nan=0.0, posinf=0.0, neginf=0.0)
        for i, val in enumerate(x_norm):
            self.sum_pos = max(0.0, self.sum_pos + val - self.drift)
            self.sum_neg = max(0.0, self.sum_neg - val - self.drift)
            scores[i] = max(self.sum_pos, self.sum_neg)
        return scores


# ============================================================================
# DRIFT-01: Multi-Feature Drift Detection Helpers (moved from acm_main.py)
# ============================================================================

def compute_drift_trend(
    drift_series: np.ndarray,
    window: int = 20,
    timestamps=None,
    min_hours: float = 24.0,
) -> float:
    """
    Compute drift trend as the slope of linear regression over recent points.

    GRADUAL-DEGRADE-FIX (v11.14.1):
    The previous implementation used a hard-coded 20-sample window regardless
    of data cadence. For 30-min data, 20 samples = 10 hours — far too short to
    detect multi-day or multi-week wear trends. For daily batches, 20 samples
    = 20 days which is reasonable but over-shoots for faster cadences.

    When `timestamps` is provided, the window is expanded so it covers at
    least `min_hours` of actual clock time. The sample-count window is used
    as a floor, not a ceiling, so short-cadence data uses longer windows.

    Positive slope indicates upward drift (degradation), negative = recovery.

    Args:
        drift_series: Array of drift/CUSUM z-scores.
        window: Minimum number of recent points (floor).
        timestamps: Optional datetime-like array aligned with drift_series.
                    When provided, window is stretched to cover min_hours.
        min_hours: Minimum clock-time coverage for the regression window.
                   Default 24 h ensures at least one full day of trend signal.

    Returns:
        Slope of linear regression fit (units: z-score per sample).
        Positive = worsening, negative = improving.
    """
    if len(drift_series) < 2:
        return 0.0

    # GRADUAL-DEGRADE-FIX: expand window to cover at least min_hours of data.
    effective_window = window
    if timestamps is not None and len(timestamps) >= 2:
        try:
            t = np.asarray(timestamps, dtype="datetime64[s]")
            diffs = np.diff(t).astype(np.float64)  # seconds
            dt_secs = float(np.nanmedian(diffs[diffs > 0])) if len(diffs) > 0 else 0.0
            if dt_secs > 0:
                min_samples = int(np.ceil((min_hours * 3600.0) / dt_secs))
                effective_window = min(max(window, min_samples), len(drift_series))
        except Exception:
            pass  # Fall back to sample-count window on any parse failure

    # Use last `effective_window` points
    recent = drift_series[-effective_window:] if len(drift_series) >= effective_window else drift_series
    if len(recent) < 2:
        return 0.0

    # Remove NaNs
    valid_mask = ~np.isnan(recent)
    if valid_mask.sum() < 2:
        return 0.0

    x = np.arange(len(recent))[valid_mask]
    y = recent[valid_mask]

    # Linear regression: y = slope * x + intercept
    try:
        slope, _ = np.polyfit(x, y, 1)
        return float(slope)
    except Exception:
        return 0.0


def compute_regime_volatility(regime_labels: np.ndarray, window: int = 20) -> float:
    """
    Compute regime volatility as the fraction of regime transitions in the last `window` points.
    
    High volatility suggests unstable operating conditions or noisy regime assignments.
    
    Args:
        regime_labels: Array of regime label assignments (integers)
        window: Number of recent points to analyze
    
    Returns:
        Value in [0, 1] where 0 = completely stable, 1 = regime changes every step.
    """
    if len(regime_labels) < 2:
        return 0.0
    
    # Use last `window` points
    recent = regime_labels[-window:] if len(regime_labels) >= window else regime_labels
    if len(recent) < 2:
        return 0.0
    
    # Count transitions (label changes)
    transitions = np.sum(recent[1:] != recent[:-1])
    return float(transitions) / (len(recent) - 1)


def compute(score_df: pd.DataFrame, score_out: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes drift and change-point scores on the fused anomaly score.
    """
    frame = score_out["frame"]
    if "fused" not in frame.columns:
        return score_out

    fused_score = frame["fused"].to_numpy(copy=False)

    # CUSUM detector for online change-point detection
    drift_cfg = cfg.get("drift", {}) or {}
    cusum_cfg = (drift_cfg.get("cusum", {}) or {})
    
    # BUGFIX v11.1.5: Split calibration and scoring to avoid data leakage
    # Fit CUSUM on first 50% of data, score on all data
    # This prevents the detector from "seeing" future data during calibration
    n = len(fused_score)
    calibration_end = max(10, n // 2)  # At least 10 points for calibration
    calibration_window = fused_score[:calibration_end]
    
    detector = CUSUMDetector(
        threshold=float(cusum_cfg.get("threshold", 2.0)),
        drift=float(cusum_cfg.get("drift", 0.1)),
    ).fit(calibration_window)  # Calibrate on first half only

    frame["cusum_raw"] = detector.score(fused_score)

    # Apply exponential smoothing to reduce stepped appearance
    smoothing_alpha = float(cusum_cfg.get("smoothing_alpha", 0.3))
    cusum_smooth = pd.Series(frame["cusum_raw"]).ewm(alpha=smoothing_alpha, adjust=False).mean().to_numpy()
    
    # Calibrate the smoothed CUSUM score to a z-score for fusion/reporting
    cal_cusum = fuse.ScoreCalibrator(q=0.98).fit(cusum_smooth)
    frame["cusum_z"] = cal_cusum.transform(cusum_smooth)

    score_out["frame"] = frame
    return score_out


# ============================================================================
# DRIFT-02: Alert Mode Classification (moved from acm_main.py v11.2)
# ============================================================================

def compute_drift_alert_mode(
    frame: pd.DataFrame,
    cfg: Dict[str, Any],
    regime_quality_ok: bool = False,
    equip: str = "",
    prev_alert_mode: str = "FAULT",
) -> pd.DataFrame:
    """Compute drift alert mode using multi-feature detection or simple threshold.

    This helper determines whether the system is in DRIFT mode (gradual degradation
    requiring retraining) or FAULT mode (transient anomaly) using:
    - Multi-feature detection: drift trend, fused level, regime volatility with hysteresis
    - Simple threshold: P95 drift exceeds configured threshold

    Args:
        frame: Scored frame DataFrame with drift_z, cusum_z, fused columns
        cfg: Config dictionary with drift settings
        regime_quality_ok: Whether regime clustering is of sufficient quality
        equip: Equipment name for logging
        prev_alert_mode: Alert mode from the previous batch run ('DRIFT' or 'FAULT').
            Used for hysteresis: when already in DRIFT, the lower hysteresis_off
            threshold is applied to sustain the mode. Callers should persist the
            returned frame['drift_mode'] value and pass it back on the next call.
            Defaults to 'FAULT' (no hysteresis on first call).

    Returns:
        Frame with drift_mode column added ('DRIFT' or 'FAULT')
    """
    from .observability import Console
    
    # Find the drift column
    drift_col = "cusum_z" if "cusum_z" in frame.columns else ("drift_z" if "drift_z" in frame.columns else None)
    
    # Retrieve multi-feature drift configuration
    drift_cfg = (cfg or {}).get("drift", {})
    multi_feat_cfg = drift_cfg.get("multi_feature", {})
    multi_feat_enabled = bool(multi_feat_cfg.get("enabled", False))
    
    if drift_col is None:
        frame["drift_mode"] = "FAULT"
        return frame
    
    try:
        drift_array = frame[drift_col].to_numpy(dtype=np.float32)
        
        if multi_feat_enabled:
            # DRIFT-01: Multi-feature logic with hysteresis
            trend_window = int(multi_feat_cfg.get("trend_window", 20))
            trend_threshold = float(multi_feat_cfg.get("trend_threshold", 0.05))
            fused_drift_min = float(multi_feat_cfg.get("fused_drift_min", 2.0))
            regime_volatility_max = float(multi_feat_cfg.get("regime_volatility_max", 0.3))
            hysteresis_on = float(multi_feat_cfg.get("hysteresis_on", 3.0))
            hysteresis_off = float(multi_feat_cfg.get("hysteresis_off", 1.5))
            
            # GRADUAL-DEGRADE-FIX: pass timestamps so compute_drift_trend can
            # expand the regression window to cover at least 24 h of clock time.
            timestamps_arr = frame.index.to_numpy() if isinstance(frame.index, pd.DatetimeIndex) else None

            # Compute features (using local helpers)
            drift_trend = compute_drift_trend(drift_array, window=trend_window, timestamps=timestamps_arr)
            fused_p95 = float(np.nanpercentile(frame["fused"].to_numpy(dtype=np.float32), 95)) if "fused" in frame.columns else 0.0

            # Compute regime volatility if regime labels exist.
            # Use the same cadence-expanded window as compute_drift_trend so both
            # conditions in the 2-of-3 vote measure over the same time span.
            # Without this, drift_trend uses ~100 samples (24 h at 15-min cadence)
            # while regime_volatility used only trend_window=20 samples (~5 h) —
            # inconsistent temporal coverage making cond_regime unreliable.
            volatility_window = trend_window
            if timestamps_arr is not None and len(timestamps_arr) >= 2:
                try:
                    t = np.asarray(timestamps_arr, dtype="datetime64[s]")
                    diffs = np.diff(t).astype(np.float64)
                    dt_secs = float(np.nanmedian(diffs[diffs > 0])) if len(diffs) > 0 else 0.0
                    if dt_secs > 0:
                        min_samples = int(np.ceil((24.0 * 3600.0) / dt_secs))
                        volatility_window = min(max(trend_window, min_samples), len(drift_array))
                except Exception:
                    pass
            regime_volatility = 0.0
            if "regime_label" in frame.columns and regime_quality_ok:
                regime_labels = frame["regime_label"].to_numpy()
                regime_volatility = compute_regime_volatility(regime_labels, window=volatility_window)

            drift_p95 = float(np.nanpercentile(drift_array, 95))

            # GRADUAL-DEGRADE-FIX (v11.14.1): Changed from strict AND to 2-of-3.
            # The previous rule required ALL three conditions simultaneously, which
            # missed real gradual degradation scenarios where one condition is
            # marginally outside bounds (e.g., elevated regime volatility during a
            # regime transition that accompanies degradation).
            # 2-of-3 retains meaningful signal combinations without requiring
            # simultaneous perfection across all dimensions.
            #
            # cond_fused is a floor-only check: any fused_p95 >= fused_drift_min
            # counts, including severe faults well above the minimum. An upper cap
            # (fused_drift_max) was previously used but is analytically wrong —
            # it penalised genuine severe degradation by dropping the DRIFT vote.
            cond_trend = abs(drift_trend) > trend_threshold
            cond_fused = fused_p95 >= fused_drift_min
            cond_regime = regime_volatility < regime_volatility_max
            conditions_met = int(cond_trend) + int(cond_fused) + int(cond_regime)
            is_drift_condition = conditions_met >= 2

            # Hysteresis logic
            if prev_alert_mode == "DRIFT":
                alert_mode = "DRIFT" if drift_p95 > hysteresis_off else "FAULT"
            else:
                alert_mode = "DRIFT" if (drift_p95 > hysteresis_on and is_drift_condition) else "FAULT"

            frame["drift_mode"] = alert_mode
            Console.info(
                f"Drift: {drift_col} P95={drift_p95:.3f} | trend={drift_trend:.4f} | "
                f"fused={fused_p95:.3f} | regime_vol={regime_volatility:.3f} | "
                f"conditions={conditions_met}/3 | mode={alert_mode}",
                component="DRIFT",
            )
        else:
            # Fallback to legacy simple threshold
            drift_p95 = float(np.nanpercentile(drift_array, 95))
            drift_threshold = float(drift_cfg.get("p95_threshold", 2.0))
            frame["drift_mode"] = "DRIFT" if drift_p95 > drift_threshold else "FAULT"
            Console.info(f"Drift: {drift_col} P95={drift_p95:.3f} | threshold={drift_threshold:.1f} | mode={frame['drift_mode'].iloc[-1]}", component="DRIFT")
    except Exception as e:
        Console.warn(f"Detection failed: {e}", component="DRIFT",
                     equip=equip, error_type=type(e).__name__, error=str(e)[:200])
        frame["drift_mode"] = "FAULT"
    
    return frame


def load_previous_drift_mode(
    sql_client: Optional[Any],
    equip_id: int,
    default_mode: str = "FAULT",
) -> str:
    """
    Load last persisted drift controller mode for hysteresis continuity.
    """
    prev_mode = default_mode
    if not sql_client or not equip_id:
        return prev_mode

    try:
        with sql_client.get_cursor() as cur:
            cur.execute(
                "SELECT TOP 1 ControllerState FROM dbo.ACM_DriftController "
                "WHERE EquipID = ? ORDER BY CreatedAt DESC",
                (equip_id,),
            )
            row = cur.fetchone()
        if row:
            mode = str(row[0]).strip().upper()
            if mode in ("DRIFT", "FAULT"):
                prev_mode = mode
    except Exception:
        pass  # Missing table/rows -> keep default.
    return prev_mode


def build_drift_controller_state(
    frame: pd.DataFrame,
    cfg: Dict[str, Any],
    score_out: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build payload for ACM_DriftController write.
    """
    score_out = score_out or {}
    drift_state = score_out.get("drift_state", {})
    if drift_state:
        return drift_state

    drift_mode = frame.get("drift_mode", ["STABLE"])[-1] if "drift_mode" in frame.columns else "STABLE"
    drift_z = frame.get("drift_z", [0.0])
    return {
        "ControllerState": str(drift_mode) if isinstance(drift_mode, str) else "STABLE",
        "CurrentDriftZ": float(drift_z.iloc[-1]) if hasattr(drift_z, "iloc") else 0.0,
        "Threshold": float(cfg.get("drift", {}).get("threshold", 3.0)),
        "Sensitivity": float(cfg.get("drift", {}).get("sensitivity", 1.0)),
    }


def write_drift_controller_state(
    *,
    output_manager: Optional[Any],
    frame: pd.DataFrame,
    cfg: Dict[str, Any],
    score_out: Optional[Dict[str, Any]] = None,
    logger: Optional[Any] = None,
    equip: str = "",
) -> int:
    """
    Build and persist drift-controller payload.

    Returns number of rows written when available, otherwise 0.
    """
    if logger is None:
        from .observability import Console as _Console
        logger = _Console

    if output_manager is None:
        return 0

    try:
        drift_state = build_drift_controller_state(
            frame=frame,
            cfg=cfg,
            score_out=score_out,
        )
        if drift_state:
            rows = output_manager.write_drift_controller(drift_state)
            return int(rows) if rows is not None else 0
    except Exception as e:
        logger.warn(
            f"Drift controller write failed: {e}",
            component="DRIFT",
            equip=equip,
            error=str(e)[:200],
        )
    return 0


def run_drift_pipeline(
    *,
    score_data: pd.DataFrame,
    frame: pd.DataFrame,
    score_out: Dict[str, Any],
    cfg: Dict[str, Any],
    regime_quality_ok: bool,
    equip: str,
    sql_client: Optional[Any],
    equip_id: int,
    output_manager: Optional[Any],
    logger: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Execute drift compute, alert-mode classification, and controller persistence.

    Returns:
        Dict with updated frame/score_out and rows written to drift controller.
    """
    if logger is None:
        from .observability import Console as _Console
        logger = _Console

    score_out["frame"] = frame
    score_out = compute(score_data, score_out, cfg)
    frame = score_out["frame"]

    prev_mode = load_previous_drift_mode(
        sql_client=sql_client,
        equip_id=equip_id,
        default_mode="FAULT",
    )

    frame = compute_drift_alert_mode(
        frame=frame,
        cfg=cfg,
        regime_quality_ok=regime_quality_ok,
        equip=equip,
        prev_alert_mode=prev_mode,
    )

    rows_written = write_drift_controller_state(
        output_manager=output_manager,
        frame=frame,
        cfg=cfg,
        score_out=score_out,
        logger=logger,
        equip=equip,
    )

    return {
        "frame": frame,
        "score_out": score_out,
        "drift_controller_rows": rows_written,
        "prev_mode": prev_mode,
    }


@dataclass
class DriftPostprocessStageResult:
    """Result bundle for drift stage plus episode schema normalization."""
    frame: pd.DataFrame
    score_out: Dict[str, Any]
    episodes: pd.DataFrame


def run_drift_postprocess_stage(
    *,
    section_fn: Any,
    score_data: pd.DataFrame,
    frame: pd.DataFrame,
    score_out: Dict[str, Any],
    episodes: pd.DataFrame,
    cfg: Dict[str, Any],
    regime_quality_ok: bool,
    equip: str,
    sql_client: Optional[Any],
    equip_id: int,
    output_manager: Optional[Any],
    logger: Optional[Any] = None,
    normalize_episodes_schema_fn: Any = None,
) -> DriftPostprocessStageResult:
    """
    Execute drift pipeline and normalize episodes schema for persistence/reporting.
    """
    if normalize_episodes_schema_fn is None:
        normalize_episodes_schema_fn = fuse.normalize_episodes_schema

    with section_fn("drift"):
        drift_out = run_drift_pipeline(
            score_data=score_data,
            frame=frame,
            score_out=score_out,
            cfg=cfg,
            regime_quality_ok=regime_quality_ok,
            equip=equip,
            sql_client=sql_client,
            equip_id=equip_id,
            output_manager=output_manager,
            logger=logger,
        )
        frame = drift_out["frame"]
        score_out = drift_out["score_out"]

    episodes, frame = normalize_episodes_schema_fn(
        episodes=episodes,
        frame=frame,
        equip=equip,
    )

    return DriftPostprocessStageResult(
        frame=frame,
        score_out=score_out,
        episodes=episodes,
    )

# core/forecast.py
"""
Per-sensor forecasting and residual analysis module.
Implements an AR(1) baseline model for each sensor to generate residuals.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import re
from typing import Any, Dict, Tuple, Optional, Literal, List
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Import Console for logging (optional - will work without it)
try:
    from utils.console import Console
except ImportError:
    # Fallback if Console not available
    class Console:
        @staticmethod
        def warn(msg):
            print(f"WARNING: {msg}")

        @staticmethod
        def info(msg):
            print(f"INFO: {msg}")


class AR1Detector:
    """
    Per-sensor AR(1) baseline model for residual scoring.
    Calculates AR(1) coefficients (phi) and mean (mu) for each sensor.
    Scores new data by calculating the absolute z-score of the residuals, normalized
    by the TRAIN-time residual standard deviation (important for anomaly sensitivity).
    """
    def __init__(self, ar1_cfg: Dict[str, Any] | None = None):
        """
        Initializes the AR(1) detector.

        Args:
            ar1_cfg (Dict[str, Any]): Configuration for the AR(1) model.
                                      Currently not used, but can be extended for smoothing etc.
        """
        self.cfg = ar1_cfg or {}
        # numeric guards
        self._eps: float = float(self.cfg.get("eps", 1e-9))
        self._phi_cap: float = float(self.cfg.get("phi_cap", 0.999))  # stability clamp
        self._sd_floor: float = float(self.cfg.get("sd_floor", 1e-6))
        # fuse strategy
        self._fuse: Literal["mean","median","p95"] = self.cfg.get("fuse", "mean")
        # trained params per column: (phi, mu)
        self.phimap: Dict[str, Tuple[float, float]] = {}
        # TRAIN residual std per column for normalization
        self.sdmap: Dict[str, float] = {}
        self._is_fitted = False

    def fit(self, X: pd.DataFrame) -> "AR1Detector":
        """
        Fits the AR(1) model for each column in the training data.

        Args:
            X (pd.DataFrame): The training feature matrix.
        """
        self.phimap = {}
        self.sdmap = {}
        if not isinstance(X, pd.DataFrame) or X.shape[0] == 0:
            # nothing to fit; leave maps empty but mark fitted for graceful no-op scoring
            self._is_fitted = True
            return self

        for c in X.columns:
            col = X[c].to_numpy(copy=False, dtype=np.float32)
            finite = np.isfinite(col)
            x = col[finite]
            if x.size < 3:
                mu = float(np.nanmean(col)) if x.size else 0.0
                if not np.isfinite(mu):
                    mu = 0.0
                phi = 0.0
                self.phimap[c] = (phi, mu)
                # residuals are deviations from mu here
                resid = (x - mu) if x.size else np.array([0.0], dtype=np.float32)
                sd = float(np.std(resid)) if resid.size else self._sd_floor
                self.sdmap[c] = max(sd, self._sd_floor)
                continue
            mu = float(np.nanmean(x))
            if not np.isfinite(mu):
                mu = 0.0
            xc = x - mu
            var_xc = float(np.var(xc)) if xc.size else 0.0
            phi = 0.0
            if np.isfinite(var_xc) and var_xc >= 1e-8:
                num = float(np.dot(xc[1:], xc[:-1]))
                den = float(np.dot(xc[:-1], xc[:-1]))
                if abs(den) >= 1e-9:
                    phi = num / den
            else:
                Console.warn(f"[AR1] Column '{c}': near-constant signal detected; using phi=0")
            if abs(phi) > self._phi_cap:
                original_phi = phi
                phi = float(np.sign(phi) * self._phi_cap)
                Console.warn(f"[AR1] Column '{c}': phi={original_phi:.3f} clamped to {phi:.3f} for stability")
            if len(x) < 20:
                Console.warn(f"[AR1] Column '{c}': only {len(x)} samples; coefficients may be unstable")
            self.phimap[c] = (phi, mu)
            # compute TRAIN residuals & std for normalization during score()
            # use one-step AR(1) with warm start at mu
            x_shift = np.empty_like(x, dtype=np.float32)
            x_shift[0] = mu
            x_shift[1:] = x[:-1]
            pred = (x_shift - mu) * phi + mu
            resid = x - pred
            resid_for_sd = resid[1:] if resid.size > 1 else resid
            sd = float(np.std(resid_for_sd))
            self.sdmap[c] = max(sd, self._sd_floor)
        self._is_fitted = True
        return self

    def score(self, X: pd.DataFrame, return_per_sensor: bool = False) -> np.ndarray | Tuple[np.ndarray, pd.DataFrame]:
        """
        Calculates absolute z-scores of residuals using TRAIN-time residual std.

        Args:
            X (pd.DataFrame): The scoring feature matrix.
            return_per_sensor (bool): If True, also returns a DataFrame of per-sensor |z|.

        Returns:
            np.ndarray: fused absolute z-scores of residuals (len == len(X));
            optionally with (per_sensor_df) when return_per_sensor=True.
        """
        if not self._is_fitted:
            return np.zeros(len(X), dtype=np.float32)

        per_cols: Dict[str, np.ndarray] = {}
        n = len(X)
        if n == 0 or X.shape[1] == 0:
            return (np.zeros(0, dtype=np.float32), pd.DataFrame(index=X.index)) if return_per_sensor else np.zeros(0, dtype=np.float32)

        for c in X.columns:
            series = X[c].to_numpy(copy=False, dtype=np.float32)
            # trained params or sensible defaults
            ph, mu = self.phimap.get(c, (0.0, float(np.nanmean(series))))
            if not np.isfinite(mu):
                mu = 0.0
            sd_train = self.sdmap.get(c, self._sd_floor)
            if not np.isfinite(sd_train) or sd_train <= self._sd_floor:
                sd_train = self._sd_floor

            # Impute only for prediction path; keep original NaNs in residuals
            series_finite = series.copy()
            # fast impute NaNs to mu for lagging/prediction
            if np.isnan(series_finite).any():
                series_finite = np.where(np.isfinite(series_finite), series_finite, mu).astype(np.float32, copy=False)

            # one-step AR(1) prediction with warm start at mu
            pred = np.empty_like(series_finite, dtype=np.float32)
            first_obs = series_finite[0] if series_finite.size else mu
            pred[0] = first_obs if np.isfinite(first_obs) else mu
            if n > 1:
                pred[1:] = (series_finite[:-1] - mu) * ph + mu

            resid = series - pred  # keep NaNs where original series had NaNs
            # normalize using TRAIN residual std
            z = np.abs(resid) / sd_train
            per_cols[c] = z.astype(np.float32, copy=False)

        if not per_cols:
            return (np.zeros(n, dtype=np.float32), pd.DataFrame(index=X.index)) if return_per_sensor else np.zeros(n, dtype=np.float32)

        col_names = list(per_cols.keys())
        matrix = np.column_stack([per_cols[name] for name in col_names]) if col_names else np.zeros((n, 0), dtype=np.float32)
        with np.errstate(all="ignore"):
            if self._fuse == "median":
                fused = np.nanmedian(matrix, axis=1).astype(np.float32)
            elif self._fuse == "p95":
                fused = np.nanpercentile(matrix, 95, axis=1).astype(np.float32)
            else:
                fused = np.nanmean(matrix, axis=1).astype(np.float32)

        if return_per_sensor:
            Z = pd.DataFrame({name: matrix[:, i] for i, name in enumerate(col_names)}, index=X.index)
            return fused, Z
        return fused

    # ---- tiny helpers for persistence (optional) ----
    def to_dict(self) -> Dict[str, Any]:
        return {"phimap": self.phimap, "sdmap": self.sdmap, "cfg": self.cfg}

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AR1Detector":
        inst = cls(payload.get("cfg"))
        inst.phimap = dict(payload.get("phimap", {}))
        inst.sdmap = dict(payload.get("sdmap", {}))
        inst._is_fitted = True
        return inst


# ------------------------------------------------
# Reporting hook: run(ctx)
# ------------------------------------------------
def _to_datetime_mixed(s):
    try:
        return pd.to_datetime(s, format="mixed", errors="coerce")
    except TypeError:
        return pd.to_datetime(s, errors="coerce")

def _read_scores(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p, dtype={"timestamp": "string"})
    timestamps = _to_datetime_mixed(df["timestamp"])
    try:
        tz_info = getattr(timestamps.dt, "tz", None)
    except AttributeError:
        tz_info = None
    if tz_info is not None:
        try:
            timestamps = timestamps.dt.tz_convert(None)
        except (TypeError, AttributeError):
            timestamps = timestamps.dt.tz_localize(None)
    df["timestamp"] = timestamps
    df = df.set_index("timestamp")
    if getattr(df.index, "tz", None) is not None:
        try:
            df.index = df.index.tz_convert(None)
        except (TypeError, AttributeError):
            df.index = df.index.tz_localize(None)
    df = df[~df.index.isna()]
    # ensure monotonic, drop duplicates (keep last)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    # guard against junk/future dates that blow up ns range
    lo = pd.Timestamp("1970-01-01")
    hi = pd.Timestamp.now() + pd.Timedelta(days=1)
    return df[(df.index >= lo) & (df.index <= hi)]

_FREQ_RE = re.compile(r"^(\d+)([A-Za-z]+)$")
_VALID_FREQ_UNITS = {"s", "sec", "min", "h", "hour", "d", "day", "w", "week", "ms"}
_UNIT_NORMALIZATION = {
    "sec": "s",
    "second": "s",
    "seconds": "s",
    "min": "min",
    "minute": "min",
    "minutes": "min",
    "hour": "h",
    "hours": "h",
    "day": "d",
    "days": "d",
    "week": "w",
    "weeks": "w",
    "ms": "ms",
}


def _normalize_freq_token(freq: str) -> str:
    freq = (freq or "").strip().replace("T", "min")
    if not freq:
        return "1min"

    match = _FREQ_RE.fullmatch(freq.lower())
    if not match:
        Console.warn(f"[FORECAST] Invalid frequency format '{freq}', using '1min'")
        return "1min"

    magnitude_str, unit_raw = match.groups()
    magnitude = int(magnitude_str)
    if magnitude <= 0:
        Console.warn(f"[FORECAST] Non-positive frequency '{freq}', using '1min'")
        return "1min"

    unit = _UNIT_NORMALIZATION.get(unit_raw.rstrip("s"), unit_raw.rstrip("s"))
    if unit not in _VALID_FREQ_UNITS:
        Console.warn(f"[FORECAST] Unknown time unit '{unit_raw}', using '1min'")
        return "1min"

    return f"{magnitude}{unit}"


def _freq_to_seconds(freq: str) -> float:
    offset = pd.tseries.frequencies.to_offset(freq)
    nanos = getattr(offset, "nanos", 0)
    if nanos:
        return float(nanos / 1e9)
    delta = getattr(offset, "delta", None)
    if delta is not None:
        return float(pd.to_timedelta(delta).total_seconds())
    raise ValueError(f"Unsupported frequency '{freq}' for duration inference")


def _safe_freq(idx: pd.DatetimeIndex, config: Dict[str, Any]) -> Tuple[str, str]:
    """
    Infer frequency with fallback chain and source tracking.
    
    Returns:
        Tuple[str, str]: (frequency, source) where source is "config_override", "inferred", or "config_default"
    """
    # Fallback 1: config override
    if "freq_override" in config:
        return _normalize_freq_token(str(config["freq_override"])), "config_override"
    
    # Fallback 2: infer from data
    if len(idx) >= 2:
        inferred = pd.infer_freq(idx)
        if inferred is not None:
            return _normalize_freq_token(str(inferred)), "inferred"
        # fallback to diff - calculate from actual timestamps
        delta = idx[1] - idx[0]
        total_seconds = delta.total_seconds()
        if total_seconds >= 86400:
            days = max(int(round(total_seconds / 86400)), 1)
            return _normalize_freq_token(f"{days}d"), "inferred"
        elif total_seconds >= 3600:
            hours = max(int(round(total_seconds / 3600)), 1)
            return _normalize_freq_token(f"{hours}h"), "inferred"
        elif total_seconds >= 60:
            minutes = max(int(round(total_seconds / 60)), 1)
            return _normalize_freq_token(f"{minutes}min"), "inferred"
        else:
            seconds = max(int(round(total_seconds)), 1)
            return _normalize_freq_token(f"{seconds}s"), "inferred"
    
    # Fallback 3: config default or hardcoded
    default_freq = config.get("default_freq", "1min")
    return _normalize_freq_token(str(default_freq)), "config_default"

def _safe_forecast_index(
    last_ts: pd.Timestamp,
    freq: str,
    horizon: int,
    samples_per_hour: float,
) -> Tuple[pd.DatetimeIndex, int, bool]:
    if getattr(last_ts, "tzinfo", None) is not None:
        try:
            last_ts = last_ts.tz_convert(None)
        except (TypeError, AttributeError):
            last_ts = last_ts.tz_localize(None)
    freq = _normalize_freq_token(freq)
    step = pd.tseries.frequencies.to_offset(freq)
    start = last_ts + step
    # clamp horizon so we don't exceed pandas ns limits
    max_ts = pd.Timestamp.max - pd.Timedelta(days=1)
    clamped = False
    original_horizon = horizon
    while horizon > 1 and start + (horizon - 1) * step > max_ts:
        horizon //= 2
        clamped = True
    idx = pd.date_range(start=start, periods=horizon, freq=freq)
    if clamped:
        hours = horizon / max(samples_per_hour, 1e-9)
        Console.warn(
            f"[FORECAST] Requested horizon {original_horizon} exceeded timestamp limits; clamped to {horizon} samples (~{hours:.1f} hours)"
        )
    return idx, horizon, clamped


def _score_series_for_ar1(series: pd.Series) -> Tuple[float, Dict[str, Any]]:
    """Score series suitability for AR(1); lower scores are better."""

    y = series.dropna()
    n_total = len(series)
    if len(y) < 20 or n_total == 0:
        return float("inf"), {}

    nan_rate = float((n_total - len(y)) / n_total)

    values = y.to_numpy(dtype=float, copy=False)
    variance = float(np.nanvar(values, ddof=1)) if values.size else 0.0
    if not np.isfinite(variance) or variance <= 1e-9:
        return float("inf"), {"nan_rate": nan_rate, "variance": variance, "n_points": len(y)}

    try:
        acf1 = y.autocorr(lag=1)
        if not np.isfinite(acf1):
            acf1 = 0.0
    except Exception:
        acf1 = 0.0

    mid = len(y) // 2
    if mid == 0:
        trend_strength = 0.0
    else:
        mean_first = float(y.iloc[:mid].mean())
        mean_last = float(y.iloc[mid:].mean())
        std = float(np.nanstd(values, ddof=1)) + 1e-9
        trend_strength = abs(mean_last - mean_first) / std

    score = (
        nan_rate * 2.0
        + max(0.0, 1.0 - abs(acf1)) * 1.5
        + min(trend_strength, 1.0)
    )

    metrics = {
        "nan_rate": nan_rate,
        "variance": variance,
        "acf1": float(acf1),
        "trend_strength": trend_strength,
        "n_points": len(y),
    }

    return score, metrics

def _select_best_series(df: pd.DataFrame, config: Dict[str, Any], candidates: List[str]) -> Tuple[Optional[pd.Series], Dict[str, Any]]:
    """Select the best forecast series with quality scoring and graceful fallbacks."""

    config = config or {}
    preferred = config.get("series_override", "fused")

    def _prepare_series(name: str) -> Optional[pd.Series]:
        if name not in df.columns:
            return None
        return df[name].astype(float)

    preferred_series = _prepare_series(preferred)
    if preferred_series is not None:
        score, metrics = _score_series_for_ar1(preferred_series)
        if np.isfinite(score) and score < 3.0:
            y_pref = preferred_series.dropna()
            metrics.update({
                "series_used": preferred,
                "score": score,
                "selection_method": "preferred",
            })
            return y_pref, metrics
        Console.warn(
            f"[FORECAST] Preferred series '{preferred}' has poor quality (score={score:.2f}); searching for better candidate"
        )

    candidate_pool = candidates or list(df.columns)
    scored: List[Tuple[float, str, Dict[str, Any]]] = []
    for name in candidate_pool:
        series = _prepare_series(name)
        if series is None:
            continue
        score, metrics = _score_series_for_ar1(series)
        if not metrics or not np.isfinite(score):
            continue
        metrics.update({"series_used": name, "score": score})
        scored.append((score, name, metrics))

    if not scored:
        return None, {}

    best_score, best_name, best_metrics = min(scored, key=lambda item: item[0])
    y_best = _prepare_series(best_name)
    if y_best is None:
        return None, {}

    return y_best.dropna(), {**best_metrics, "selection_method": "stability_scoring"}


def _check_stationarity(y: pd.Series, window: int = 50) -> Dict[str, Any]:
    """Compute lightweight stationarity diagnostics."""

    results: Dict[str, Any] = {}
    if len(y) <= window * 2:
        return results

    rolling_mean = y.rolling(window).mean()
    mean_var = float(rolling_mean.var()) if hasattr(rolling_mean, "var") else 0.0
    overall_var = float(y.var()) if hasattr(y, "var") else 0.0
    stability_ratio = float(mean_var / (overall_var + 1e-9)) if overall_var > 0 else float("inf")
    results["mean_stability_ratio"] = stability_ratio
    results["likely_stationary"] = stability_ratio < 0.1
    return results


def _validate_forecast(
    series: pd.Series,
    holdout_pct: float = 0.2,
) -> Dict[str, float]:
    """Backtest AR(1) forecast accuracy on a holdout split."""

    n = len(series)
    if n < 40:
        return {}

    split = int(n * (1 - holdout_pct))
    if split < 20 or n - split < 5:
        return {}

    train = series.iloc[:split]
    test = series.iloc[split:]

    detector = AR1Detector().fit(train.to_frame())
    phi, mu = detector.phimap.get(train.name, (0.0, float(train.mean())))
    if not np.isfinite(mu):
        mu = 0.0

    forecasts: List[float] = []
    last_val = float(train.iloc[-1]) if len(train) else mu
    for _ in range(len(test)):
        fc = mu + phi * (last_val - mu)
        forecasts.append(fc)
        last_val = fc

    if not forecasts:
        return {}

    actuals = test.to_numpy(dtype=float, copy=False)
    forecast_arr = np.asarray(forecasts, dtype=float)
    errors = forecast_arr - actuals

    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    mape = float(np.mean(np.abs(errors / (np.abs(actuals) + 1e-9))) * 100)

    return {
        "validation_mae": mae,
        "validation_rmse": rmse,
        "validation_mape": mape,
        "validation_n": float(len(test)),
    }

def run(ctx: Dict[str, Any]):
    """
    Enhanced forecast module with intelligent series selection, dynamic horizon,
    uncertainty bands, robust frequency inference, and optional plotting.
    """
    run_dir = ctx.get("run_dir", Path("."))
    plots_dir = ctx.get("plots_dir", run_dir / "plots")
    tables_dir = ctx.get("tables_dir", run_dir / "tables")
    config = ctx.get("config", {}).get("forecast", {})
    # Identifiers for stamping outputs
    run_id = ctx.get("run_id")
    equip_id = ctx.get("equip_id")
    
    p = run_dir / "scores.csv"
    if not p.exists():
        return {"module":"forecast","tables":[],"plots":[],"metrics":{},
                "error":{"type":"MissingFile","message":"scores.csv not found"}}

    df = _read_scores(p)

    # FCST-01: Intelligent series selection with fallbacks
    candidates = ["fused", "cusum_z", "pca_spe_z", "ar1_z", "iforest_z", "gmm_z", "mhal_z"]
    y, selection_metrics = _select_best_series(df, config, candidates)
    
    if y is None or len(y) < 20:
        return {"module":"forecast","tables":[],"plots":[],"metrics":{},
                "error":{"type":"NoSeries","message":"No suitable series to forecast"}}

    # Ensure the series has a name for phimap/sdmap keys
    if y.name is None:
        y.name = "target"
    series_name = str(y.name)

    stationarity_metrics = _check_stationarity(y)
    validation_metrics = _validate_forecast(y)

    # --- Use AR1Detector for forecasting ---
    ar1_detector = AR1Detector().fit(y.to_frame())
    ph, mu = ar1_detector.phimap.get(series_name, (0.0, float(np.nanmean(y))))
    if not np.isfinite(mu): mu = 0.0
    sd_train = ar1_detector.sdmap.get(series_name, 1.0)
    if not np.isfinite(sd_train) or sd_train <= 1e-9: sd_train = 1.0

    # FCST-04: Robust frequency inference
    y_idx = pd.DatetimeIndex(y.index) if not isinstance(y.index, pd.DatetimeIndex) else y.index
    freq, freq_source = _safe_freq(y_idx, config)
    
    # FCST-02: Dynamic horizon calculation
    horizon_hours = float(config.get("horizon_hours", 24.0))
    # Parse frequency to get time per sample - handle various frequency formats robustly
    try:
        sample_duration_seconds = _freq_to_seconds(freq)
        samples_per_hour = 3600.0 / sample_duration_seconds if sample_duration_seconds > 0 else 60.0
    except Exception as e:
        Console.warn(f"[FORECAST] Failed to parse frequency '{freq}': {e}, using 1min default")
        freq = "1min"
        sample_duration_seconds = 60.0
        samples_per_hour = 60.0
    horizon = max(1, int(np.ceil(horizon_hours * samples_per_hour)))
    
    # FCST-03: Confidence intervals
    confidence_k = float(config.get("confidence_k", 1.96))  # 95% CI default
    
    # Generate forecast with uncertainty
    last_val = y.iloc[-1] if not y.empty else mu
    
    try:
        idx_fore, horizon, _ = _safe_forecast_index(y.index[-1], freq, horizon, samples_per_hour)
    except Exception:
        freq, horizon = "1min", min(horizon, 12)
        freq_source = "fallback_emergency"
        idx_fore, horizon, _ = _safe_forecast_index(y.index[-1], freq, horizon, samples_per_hour)

    # FCST-06: Vectorized AR(1) forecast with growing uncertainty
    h_steps = np.arange(1, len(idx_fore) + 1, dtype=int)
    h_values = h_steps.astype(float)
    if abs(ph) > 1e-9:
        log_phi = np.log(abs(ph))
        sign_sequence = np.where(h_steps % 2 == 0, 1.0, np.sign(ph))
        phi_powers = sign_sequence * np.exp(log_phi * h_values)
    else:
        phi_powers = np.zeros_like(h_values)

    yhat_values = mu + phi_powers * (last_val - mu)
    yhat = pd.Series(yhat_values, index=idx_fore, name="forecast")

    if abs(ph) < 0.9999:
        phi_squared = ph ** 2
        phi_sq_powers = np.power(phi_squared, h_steps)
        var_ratio = (1 - phi_sq_powers) / (1 - phi_squared + 1e-9)
    else:
        var_ratio = h_values.copy()
    var_ratio = np.clip(var_ratio, 1.0, 100.0)
    forecast_std = sd_train * np.sqrt(var_ratio)

    ci_lower = yhat - confidence_k * forecast_std
    ci_upper = yhat + confidence_k * forecast_std
    
    # FCST-07: Export forecast metrics CSV
    tables = []
    forecast_confidence_df = pd.DataFrame({
        "timestamp": idx_fore,
        "forecast": yhat.values,
        "ci_lower": ci_lower.values,
        "ci_upper": ci_upper.values,
        "forecast_std": forecast_std
    })
    if run_id is not None:
        forecast_confidence_df.insert(0, "RunID", run_id)
    if equip_id is not None:
            forecast_confidence_df.insert(1, "EquipID", int(equip_id))
    fc_path = tables_dir / "forecast_confidence.csv"
    forecast_confidence_df.to_csv(fc_path, index=False)
    tables.append({"name": "forecast_confidence", "path": str(fc_path)})
    
    # Metrics export
    metrics_df = pd.DataFrame([{
        "ar1_phi": ph,
        "ar1_mu": mu,
        "ar1_sigma": sd_train,
        "horizon": len(idx_fore),
        "horizon_hours": horizon_hours,
        "freq": freq,
        "freq_source": freq_source,
        "confidence_k": confidence_k,
        "forecast_std_first": float(forecast_std[0]) if forecast_std.size else np.nan,
        "forecast_std_last": float(forecast_std[-1]) if forecast_std.size else np.nan,
        **selection_metrics,
        **stationarity_metrics,
        **validation_metrics,
    }])
    if run_id is not None:
        metrics_df.insert(0, "RunID", run_id)
    if equip_id is not None:
        try:
            metrics_df.insert(1, "EquipID", int(equip_id))
        except Exception:
            pass
    fm_path = tables_dir / "forecast_metrics.csv"
    metrics_df.to_csv(fm_path, index=False)
    tables.append({"name": "forecast_metrics", "path": str(fm_path)})
    
    # Diagnostic measures focused on mean reversion and persistence
    distance_from_mean = float(abs(last_val - mu))
    actual_reversion = float(abs(yhat.iloc[0] - last_val)) if len(yhat) > 0 else 0.0
    mean_reversion_strength = max(0.0, 1.0 - abs(ph))
    expected_reversion = mean_reversion_strength * distance_from_mean
    reversion_error = abs(actual_reversion - expected_reversion)
    forecast_drift = float(abs(yhat.iloc[-1] - yhat.iloc[0])) if len(yhat) > 1 else 0.0
    first_ci_width = float(2 * confidence_k * forecast_std[0]) if forecast_std.size else 0.0
    last_ci_width = float(2 * confidence_k * forecast_std[-1]) if forecast_std.size else 0.0

    recommendation_notes: List[str] = []
    if abs(ph) > 0.98:
        recommendation_notes.append("CRITICAL: Near unit-root (phi > 0.98) - forecast unreliable for long horizons")
    elif abs(ph) > 0.95:
        recommendation_notes.append("WARNING: High persistence (phi > 0.95) - slow mean reversion")

    if ph < -0.5:
        recommendation_notes.append("WARNING: Negative autocorrelation (phi < -0.5) - series may oscillate")

    nan_rate = selection_metrics.get("nan_rate", 0.0)
    if nan_rate > 0.2:
        recommendation_notes.append("WARNING: High missing data rate (>20%) - forecast may be unstable")

    if sd_train > abs(mu) * 2:
        recommendation_notes.append("INFO: High noise-to-signal ratio - consider smoothing or alternative models")

    if selection_metrics.get("n_points", 0) < 50:
        recommendation_notes.append("WARNING: Limited training data (<50 points) - AR coefficients may be unstable")

    likely_stationary = stationarity_metrics.get("likely_stationary") if stationarity_metrics else None
    if likely_stationary is False:
        recommendation_notes.append("WARNING: Rolling mean variance suggests non-stationarity")

    validation_mape = validation_metrics.get("validation_mape") if validation_metrics else None
    if validation_mape is not None and validation_mape > 25.0:
        recommendation_notes.append(f"INFO: Holdout MAPE {validation_mape:.1f}% exceeds 25%; consider richer model")

    recommendation = "; ".join(recommendation_notes) if recommendation_notes else "OK - Model diagnostics within normal ranges"

    diagnostics_df = pd.DataFrame([{
        "series_name": series_name,
        "ar1_phi": ph,
        "ar1_mu": mu,
        "ar1_sigma": sd_train,
        "last_observed": last_val,
        "first_forecast": yhat.iloc[0] if len(yhat) > 0 else np.nan,
        "distance_from_mean": distance_from_mean,
        "mean_reversion_strength": mean_reversion_strength,
        "expected_reversion": expected_reversion,
        "actual_reversion": actual_reversion,
        "reversion_error": reversion_error,
        "forecast_drift": forecast_drift,
        "ci_width_first": first_ci_width,
        "ci_width_last": last_ci_width,
        "recommendation": recommendation,
        "selection_method": selection_metrics.get("selection_method", "unknown"),
        "nan_rate": selection_metrics.get("nan_rate", 0.0),
        "variance": selection_metrics.get("variance", 0.0),
        "acf1": selection_metrics.get("acf1"),
        "trend_strength": selection_metrics.get("trend_strength"),
        "score": selection_metrics.get("score"),
        **stationarity_metrics,
        **validation_metrics,
    }])
    if run_id is not None:
        diagnostics_df.insert(0, "RunID", run_id)
    if equip_id is not None:
        try:
            diagnostics_df.insert(1, "EquipID", int(equip_id))
        except Exception:
            pass
    
    fd_path = tables_dir / "forecast_diagnostics.csv"
    diagnostics_df.to_csv(fd_path, index=False)
    tables.append({"name": "forecast_diagnostics", "path": str(fd_path)})

    # FCST-05: Optional plotting
    plots = []
    
    fig = plt.figure(figsize=(12,4)); ax = plt.gca()
    y.plot(ax=ax, linewidth=1, label="Actual", color="steelblue")
    yhat.plot(ax=ax, linewidth=1.2, linestyle="--", label=f"AR(1) Forecast (+{len(yhat)})", color="darkorange")
    # FCST-03: Plot confidence intervals
    ax.fill_between(idx_fore, ci_lower, ci_upper, alpha=0.2, color="darkorange", label=f"{int(confidence_k*100/1.96)}% CI")
    ax.legend(loc="best")
    if False:
        ax.set_title(f"Forecast on {series_name} (φ={ph:.3f}, μ={mu:.2f}, σ={sd_train:.3f})")
    ax.set_title(f"Forecast on {series_name} (phi={ph:.3f}, mu={mu:.2f}, sd={sd_train:.3f})")
    ax.set_xlabel("")
    ax.grid(True, alpha=0.3)
    # Optimize chart naming to identify equip/run/series
    suffix = []
    if equip_id is not None:
        suffix.append(f"eq{int(equip_id)}")
    if run_id is not None:
        suffix.append(str(run_id)[:8])
    suffix_str = ("_" + "_".join(suffix)) if suffix else ""
    safe_series = series_name.replace("/", "-")
    try:
        safe_series = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(series_name)).strip("_") or "series"
    except Exception:
        pass
    outp = plots_dir / f"forecast_overlay__{safe_series}{suffix_str}.png"
    fig.savefig(outp, dpi=144, bbox_inches="tight"); plt.close(fig)
    plots.append({"title":"Forecast overlay","path":str(outp), 
                     "caption":f"{series_name} — AR(1) forecast with {int(confidence_k*100/1.96)}% confidence bands"})

    try:
        plots[-1]["caption"] = f"{series_name} - AR(1) forecast with {int(confidence_k*100/1.96)}% confidence bands"
    except Exception:
        pass

    metrics = {
        "ar1_phi": ph,
        "ar1_mu": mu,
        "ar1_sigma": sd_train,
        "horizon": int(len(yhat)),
        "horizon_hours": horizon_hours,
        "freq": freq,
        "freq_source": freq_source,
        "confidence_k": confidence_k,
        "forecast_std_first": float(forecast_std[0]) if forecast_std.size else np.nan,
        "forecast_std_last": float(forecast_std[-1]) if forecast_std.size else np.nan,
        **selection_metrics,
        **stationarity_metrics,
        **validation_metrics,
    }
    
    return {"module":"forecast", "tables":tables, "plots":plots, "metrics":metrics}


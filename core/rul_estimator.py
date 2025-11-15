"""
RUL and failure-forecast estimator
==================================

Consumes health timeline and forecast outputs and produces:
- Health forecast time series suitable for SQL (`ACM_HealthForecast_TS`)
- Failure probability over time (`ACM_FailureForecast_TS`)
- RUL time series and summary (`ACM_RUL_TS`, `ACM_RUL_Summary`)
- Sensor attribution at predicted failure time (`ACM_RUL_Attribution`)

This module is intentionally numerically simple (AR(1)-style trend + Gaussian
uncertainty); it can be replaced with richer models later without changing
the SQL/Grafana contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import numpy as np
import pandas as pd
from math import erf, sqrt

from utils.logger import Console


def _norm_cdf(x: np.ndarray) -> np.ndarray:
    """Standard normal CDF that accepts scalars or numpy arrays."""
    arr = np.asarray(x, dtype=float)
    scaled = arr / sqrt(2.0)
    # math.erf only supports scalars; vectorize to handle numpy arrays.
    erf_vec = np.vectorize(erf, otypes=[float])
    return 0.5 * (1.0 + erf_vec(scaled))


@dataclass
class RULConfig:
    health_threshold: float = 70.0
    min_points: int = 20
    max_forecast_hours: float = 24.0
    maintenance_risk_low: float = 0.2
    maintenance_risk_high: float = 0.5


def _load_health_timeline(
    tables_dir: Path,
    sql_client: Optional[Any] = None,
    equip_id: Optional[int] = None,
    run_id: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Load health timeline for RUL estimation.

    Priority:
    1. If sql_client and identifiers are available, read from ACM_HealthTimeline.
    2. Fallback to health_timeline.csv in tables_dir (legacy file mode).
    """
    # Prefer SQL when possible (SQL-only mode)
    if sql_client is not None and equip_id is not None and run_id:
        try:
            cur = sql_client.cursor()
            cur.execute(
                """
                SELECT Timestamp, HealthIndex
                FROM dbo.ACM_HealthTimeline
                WHERE EquipID = ? AND RunID = ?
                ORDER BY Timestamp
                """,
                (equip_id, run_id),
            )
            rows = cur.fetchall()
            cur.close()
            if rows:
                df = pd.DataFrame.from_records(rows, columns=["Timestamp", "HealthIndex"])
                df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True)
                df = df.dropna(subset=["Timestamp"]).sort_values("Timestamp")
                Console.info(
                    f"[RUL] Loaded {len(df)} health points from SQL for EquipID={equip_id}, RunID={run_id}"
                )
                return df
            else:
                Console.warn(
                    f"[RUL] No rows in ACM_HealthTimeline for EquipID={equip_id}, RunID={run_id}"
                )
        except Exception as e:
            Console.warn(f"[RUL] Failed to load health timeline from SQL: {e}")

    # Fallback: legacy CSV path (file mode)
    p = tables_dir / "health_timeline.csv"
    if not p.exists():
        Console.warn(f"[RUL] health_timeline.csv not found in {tables_dir}")
        return None
    df = pd.read_csv(p)
    if "Timestamp" in df.columns:
        ts_col = "Timestamp"
    elif "timestamp" in df.columns:
        ts_col = "timestamp"
    else:
        ts_col = df.columns[0]
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    df = df.sort_values(ts_col).dropna(subset=[ts_col])
    df = df.rename(columns={ts_col: "Timestamp"})
    return df


def _simple_ar1_forecast(
    ts: pd.Series, cfg: RULConfig
) -> Tuple[pd.Series, np.ndarray, np.ndarray]:
    """
    Fit a simple AR(1) on the last window of HealthIndex and forecast forward with
    growing uncertainty. Returns (forecast_series, forecast_std, horizons_hours).
    """
    y = ts.dropna().astype(float)
    if y.size < cfg.min_points:
        Console.warn(f"[RUL] Only {y.size} health points available; skipping RUL.")
        return pd.Series(dtype=float), np.array([]), np.array([])

    # Use last window (all for now)
    x = y.to_numpy(copy=False)
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

    # TRAIN residual std
    x_shift = np.empty_like(x, dtype=np.float64)
    x_shift[0] = mu
    x_shift[1:] = x[:-1]
    pred_train = (x_shift - mu) * phi + mu
    resid = x - pred_train
    resid_for_sd = resid[1:] if resid.size > 1 else resid
    sd_train = float(np.std(resid_for_sd)) or 1.0

    # infer cadence
    idx = y.index
    if not isinstance(idx, pd.DatetimeIndex):
        Console.warn("[RUL] HealthIndex index is not DateTimeIndex; cannot forecast.")
        return pd.Series(dtype=float), np.array([]), np.array([])
    idx = idx.sort_values()
    if len(idx) < 2:
        return pd.Series(dtype=float), np.array([]), np.array([])
    deltas = np.diff(idx.values.astype("int64")) / 1e9  # seconds
    step_sec = float(np.median(deltas))
    if step_sec <= 0:
        step_sec = 60.0
    samples_per_hour = 3600.0 / step_sec
    max_steps = int(np.ceil(cfg.max_forecast_hours * samples_per_hour))

    # build forecast index
    last_ts = idx[-1]
    freq = pd.to_timedelta(step_sec, unit="s")
    idx_fore = pd.date_range(last_ts + freq, periods=max_steps, freq=freq)
    h_steps = np.arange(1, len(idx_fore) + 1, dtype=int)
    h_hours = h_steps * (step_sec / 3600.0)

    last_val = float(x[-1])
    if abs(phi) > 1e-9:
        log_phi = np.log(abs(phi))
        sign_sequence = np.where(h_steps % 2 == 0, 1.0, np.sign(phi))
        phi_powers = sign_sequence * np.exp(log_phi * h_steps.astype(float))
    else:
        phi_powers = np.zeros_like(h_steps, dtype=float)
    yhat_values = mu + phi_powers * (last_val - mu)

    # growing variance
    if abs(phi) < 0.9999:
        phi_squared = phi ** 2
        phi_sq_powers = np.power(phi_squared, h_steps)
        var_ratio = (1 - phi_sq_powers) / (1 - phi_squared + 1e-9)
    else:
        var_ratio = h_steps.astype(float)
    var_ratio = np.clip(var_ratio, 1.0, 100.0)
    forecast_std = sd_train * np.sqrt(var_ratio)

    forecast = pd.Series(yhat_values, index=idx_fore, name="ForecastHealth")
    return forecast, forecast_std, h_hours


def estimate_rul_and_failure(
    tables_dir: Path,
    equip_id: Optional[int],
    run_id: Optional[str],
    health_threshold: float = 70.0,
    cfg: Optional[RULConfig] = None,
    sql_client: Optional[Any] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Main entrypoint used by acm_main.

    Returns a dict of DataFrames keyed by SQL table name:
    - ACM_HealthForecast_TS
    - ACM_FailureForecast_TS
    - ACM_RUL_TS
    - ACM_RUL_Summary
    - ACM_RUL_Attribution
    - ACM_MaintenanceRecommendation
    """
    cfg = cfg or RULConfig(health_threshold=health_threshold)
    health_df = _load_health_timeline(
        tables_dir, sql_client=sql_client, equip_id=equip_id, run_id=run_id
    )
    if health_df is None:
        Console.warn("[RUL] Health timeline not available; skipping RUL/forecast outputs.")
        return {}
    if "HealthIndex" not in health_df.columns or "Timestamp" not in health_df.columns:
        Console.warn(
            f"[RUL] Health timeline missing required columns (have={list(health_df.columns)})"
        )
        return {}

    # Prepare health time series
    hi = health_df["HealthIndex"].astype(float)
    hi.index = pd.to_datetime(health_df["Timestamp"], utc=True)
    hi = hi.sort_index()
    if hi.size < cfg.min_points:
        Console.warn(
            f"[RUL] Not enough health points ({hi.size}, min={cfg.min_points}) for robust AR(1) RUL; "
            "falling back to naive flat forecast."
        )

    # Forecast health
    forecast, forecast_std, h_hours = _simple_ar1_forecast(hi, cfg)
    if forecast.empty:
        Console.warn("[RUL] Forecast series is empty; falling back to naive flat forecast.")
        # Naive fallback: hold last value flat over the forecast horizon
        last_ts = hi.index[-1]
        last_val = float(hi.iloc[-1])
        step_hours = 1.0
        max_h = max(float(cfg.max_forecast_hours), step_hours)
        h_hours = np.arange(step_hours, max_h + step_hours, step_hours, dtype=float)
        idx_fore = last_ts + pd.to_timedelta(h_hours, unit="h")
        forecast_values = np.full_like(h_hours, last_val, dtype=float)
        # Use empirical std of history as uncertainty; default to 1.0 if degenerate
        hist_std = float(np.nanstd(hi.values)) if hi.size > 1 else 1.0
        if not np.isfinite(hist_std) or hist_std <= 0:
            hist_std = 1.0
        forecast_std = np.full_like(h_hours, hist_std, dtype=float)
        forecast = pd.Series(forecast_values, index=idx_fore, name="ForecastHealth")

    ci_k = 1.96
    ci_lower = forecast - ci_k * forecast_std
    ci_upper = forecast + ci_k * forecast_std

    # Failure probability by horizon (prob HealthIndex <= threshold)
    z = (health_threshold - forecast.values) / (forecast_std + 1e-9)
    failure_prob = _norm_cdf(z)

    # Determine RUL: earliest horizon where central forecast crosses threshold
    below = forecast.values <= health_threshold
    if below.any():
        first_idx = int(np.argmax(below))
        rul_hours = float(h_hours[first_idx])
        failure_time = forecast.index[first_idx]
    else:
        # no crossing in horizon -> treat as large RUL
        rul_hours = float(h_hours[-1])
        failure_time = forecast.index[-1]

    # Bounds: use CI crossing points
    lower_cross = ci_lower.values <= health_threshold
    upper_cross = ci_upper.values <= health_threshold
    lower_bound_hours = float(h_hours[np.argmax(lower_cross)]) if lower_cross.any() else float(h_hours[-1])
    upper_bound_hours = float(h_hours[np.argmax(upper_cross)]) if upper_cross.any() else float(h_hours[-1])

    # Confidence: narrower CI => higher confidence
    ci_width_norm = (ci_upper.values - ci_lower.values) / (health_threshold + 1e-9)
    conf = float(np.clip(1.0 - np.nanmean(ci_width_norm), 0.0, 1.0))

    # Build DataFrames for SQL
    run_id_val = run_id or ""
    equip_id_val = int(equip_id) if equip_id is not None else None

    def _insert_ids(df: pd.DataFrame) -> pd.DataFrame:
        if run_id_val:
            df.insert(0, "RunID", run_id_val)
        if equip_id_val is not None:
            df.insert(1 if run_id_val else 0, "EquipID", equip_id_val)
        return df

    # Health forecast TS
    health_forecast_df = pd.DataFrame(
        {
            "Timestamp": forecast.index,
            "ForecastHealth": forecast.values,
            "CiLower": ci_lower.values,
            "CiUpper": ci_upper.values,
            "ForecastStd": forecast_std,
            "Method": "AR1_Health",
        }
    )
    health_forecast_df = _insert_ids(health_forecast_df)

    # Failure probability TS
    failure_ts_df = pd.DataFrame(
        {
            "Timestamp": forecast.index,
            "FailureProb": failure_prob,
            "ThresholdUsed": health_threshold,
            "Method": "AR1_Health",
        }
    )
    failure_ts_df = _insert_ids(failure_ts_df)

    # RUL TS: from each forecast point, remaining hours until predicted failure
    remaining_hours = np.maximum(rul_hours - h_hours, 0.0)
    rul_ts_df = pd.DataFrame(
        {
            "Timestamp": forecast.index,
            "RUL_Hours": remaining_hours,
            "LowerBound": np.maximum(lower_bound_hours - h_hours, 0.0),
            "UpperBound": np.maximum(upper_bound_hours - h_hours, 0.0),
            "Confidence": conf,
            "Method": "AR1_Health",
        }
    )
    rul_ts_df = _insert_ids(rul_ts_df)

    # RUL summary
    now_ts = hi.index[-1]
    rul_summary_df = pd.DataFrame(
        [
            {
                "RUL_Hours": rul_hours,
                "LowerBound": lower_bound_hours,
                "UpperBound": upper_bound_hours,
                "Confidence": conf,
                "Method": "AR1_Health",
                "LastUpdate": now_ts,
            }
        ]
    )
    rul_summary_df = _insert_ids(rul_summary_df)

    # Sensor attribution at predicted failure time: use current hotspots as proxy
    attribution_df = _build_sensor_attribution(
        tables_dir=tables_dir,
        equip_id=equip_id_val,
        run_id=run_id_val,
        failure_time=failure_time,
        sql_client=sql_client,
    )

    # Maintenance recommendation window based on failure probability curve
    maint_df = _build_maintenance_recommendation(
        forecast_index=forecast.index,
        failure_prob=failure_prob,
        cfg=cfg,
        run_id=run_id_val,
        equip_id=equip_id_val,
    )

    return {
        "ACM_HealthForecast_TS": health_forecast_df,
        "ACM_FailureForecast_TS": failure_ts_df,
        "ACM_RUL_TS": rul_ts_df,
        "ACM_RUL_Summary": rul_summary_df,
        "ACM_RUL_Attribution": attribution_df,
        "ACM_MaintenanceRecommendation": maint_df,
    }


def _build_sensor_attribution(
    tables_dir: Path,
    equip_id: Optional[int],
    run_id: str,
    failure_time: pd.Timestamp,
    sql_client: Optional[Any] = None,
) -> pd.DataFrame:
    """
    Heuristic sensor attribution: use current SensorHotspots as proxy for which
    sensors are most likely to be responsible at predicted failure time.
    """
    # Prefer SQL when available
    if sql_client is not None and equip_id is not None and run_id:
        try:
            cur = sql_client.cursor()
            cur.execute(
                """
                SELECT TOP 10 SensorName, LatestAbsZ, AboveAlertCount
                FROM dbo.ACM_SensorHotspots
                WHERE EquipID = ? AND RunID = ?
                ORDER BY LatestAbsZ DESC
                """,
                (equip_id, run_id),
            )
            rows = cur.fetchall()
            cur.close()
            if rows:
                df = pd.DataFrame.from_records(rows, columns=["SensorName", "Z", "AlertCount"])
                df["Z"] = pd.to_numeric(df["Z"], errors="coerce").clip(lower=0.0)
                df = df.dropna(subset=["Z"])
                if df["Z"].sum() > 0:
                    df["FailureContribution"] = df["Z"] / df["Z"].sum()
                    df = df.sort_values("FailureContribution", ascending=False).head(10)
                else:
                    df = pd.DataFrame(columns=["SensorName", "FailureContribution", "Z", "AlertCount"])
            else:
                df = pd.DataFrame(columns=["SensorName", "FailureContribution", "Z", "AlertCount"])
        except Exception as e:
            Console.warn(f"[RUL] Failed to load sensor hotspots from SQL: {e}")
            df = pd.DataFrame(columns=["SensorName", "FailureContribution", "Z", "AlertCount"])
    else:
        # Fallback to CSV (file mode)
        p = tables_dir / "sensor_hotspots.csv"
        if not p.exists():
            Console.warn(f"[RUL] sensor_hotspots.csv not found in {tables_dir}")
            return pd.DataFrame(columns=["RunID", "EquipID", "FailureTime", "SensorName",
                                         "FailureContribution", "ZScoreAtFailure", "AlertCount", "Comment"])
        df = pd.read_csv(p)
        if "SensorName" not in df.columns or "LatestAbsZ" not in df.columns:
            return pd.DataFrame(columns=["RunID", "EquipID", "FailureTime", "SensorName",
                                         "FailureContribution", "ZScoreAtFailure", "AlertCount", "Comment"])
        df = df.rename(columns={"LatestAbsZ": "Z"})
        df["Z"] = df["Z"].astype(float).clip(lower=0.0)
        if df["Z"].sum() <= 0:
            return pd.DataFrame(columns=["RunID", "EquipID", "FailureTime", "SensorName",
                                         "FailureContribution", "ZScoreAtFailure", "AlertCount", "Comment"])
        df["FailureContribution"] = df["Z"] / df["Z"].sum()
        df = df.sort_values("FailureContribution", ascending=False).head(10)

    result = pd.DataFrame(
        {
            "FailureTime": failure_time,
            "SensorName": df["SensorName"],
            "FailureContribution": df["FailureContribution"],
            "ZScoreAtFailure": df["Z"],
            "AlertCount": df.get("AboveAlertCount", pd.Series([None] * len(df))),
            "Comment": [None] * len(df),
        }
    )
    if run_id:
        result.insert(0, "RunID", run_id)
    if equip_id is not None:
        result.insert(1 if run_id else 0, "EquipID", equip_id)
    return result


def _build_maintenance_recommendation(
    forecast_index: pd.DatetimeIndex,
    failure_prob: np.ndarray,
    cfg: RULConfig,
    run_id: str,
    equip_id: Optional[int],
) -> pd.DataFrame:
    """
    Construct a simple maintenance window recommendation from the failure
    probability time series.

    Heuristic:
    - EarliestMaintenance: first time failure probability exceeds maintenance_risk_low.
    - PreferredWindowStart: same as EarliestMaintenance.
    - PreferredWindowEnd: first time failure probability exceeds maintenance_risk_high
      (or the last forecast point if never exceeded).
    """
    if forecast_index.empty or failure_prob.size == 0:
        return pd.DataFrame(
            columns=[
                "RunID",
                "EquipID",
                "EarliestMaintenance",
                "PreferredWindowStart",
                "PreferredWindowEnd",
                "FailureProbAtWindowEnd",
                "Comment",
            ]
        )

    fp = np.asarray(failure_prob, dtype=float)
    times = forecast_index

    low_mask = fp >= float(cfg.maintenance_risk_low)
    high_mask = fp >= float(cfg.maintenance_risk_high)

    if low_mask.any():
        first_low_idx = int(np.argmax(low_mask))
    else:
        first_low_idx = fp.size - 1

    if high_mask.any():
        first_high_idx = int(np.argmax(high_mask))
    else:
        first_high_idx = fp.size - 1

    earliest_ts = times[first_low_idx]
    window_start = earliest_ts
    window_end = times[first_high_idx]
    prob_at_end = float(fp[first_high_idx])

    df = pd.DataFrame(
        [
            {
                "EarliestMaintenance": earliest_ts,
                "PreferredWindowStart": window_start,
                "PreferredWindowEnd": window_end,
                "FailureProbAtWindowEnd": prob_at_end,
                "Comment": None,
            }
        ]
    )
    if run_id:
        df.insert(0, "RunID", run_id)
    if equip_id is not None:
        df.insert(1 if run_id else 0, "EquipID", equip_id)
    return df

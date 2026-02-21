# ACM Forecasting — Rethink from Scratch

Date: 2026-02-21
Owner: Snehil
Status: Design — replaces TIMESFM_INTEGRATION_DESIGN.md

---

## 0. The Real Goals (Unchanged)

What we actually want out of forecasting, in plain language:

1. **When will this equipment need attention?** — Give maintenance a time horizon.
2. **Which sensors are driving the degradation?** — Tell them what to inspect.
3. **How confident are we?** — Do not mislead with false precision.
4. **Run on N assets in parallel without killing the server.**

Nothing about those goals requires a 2GB foundation model.

---

## 1. Why TimesFM Is Wrong for This Problem

TimesFM is designed to zero-shot forecast general time series (finance, weather, retail demand). It is excellent at that. It is the wrong tool here for several reasons:

**Weight cost is prohibitive at scale.**
2GB of weights loaded into RAM per process. If you run ACM for 20 turbines in parallel, that is 40GB of RAM just for the forecasting layer, assuming you can even share the model across processes cleanly (you cannot easily across subprocess boundaries). On a normal industrial server this is a non-starter.

**It adds no value over statistics for smooth monotonic degradation.**
Health degradation in industrial equipment is not like stock prices or retail demand — it is not chaotic. It follows patterns that are well-modeled by robust trend extrapolation: Theil-Sen slope, Holt-Winters damped trend, or exponential smoothing. These methods run in microseconds, not 200ms, and require zero memory beyond the series itself.

**It cannot model what actually matters here: the physics-informed constraints.**
TimesFM does not know that HealthIndex is bounded between 0 and 100. It does not know that a positive slope in health is an improvement (maintenance happened), not a continuation of a trend. It does not know that regime transitions invalidate extrapolation across them. A statistical model explicitly encodes these constraints; a foundation model has to infer them from data it may never have seen for this equipment type.

**The cross-batch calibration problem applies to any learned model.**
As shown in the Grafana analysis, z-scores and even health indices have discontinuities at batch boundaries due to per-batch re-calibration. Any model trained or prompted on this history is ingesting a non-stationary signal. Statistical methods that work on a single run's continuous window sidestep this entirely.

---

## 2. What We Should Build Instead

The right architecture is three lightweight, composable components running in pure numpy/scipy — no large dependencies, no GPU, no model weights:

```
A. TrendEstimator        — "what is the degradation rate right now?"
B. HorizonProjector      — "when does the trend cross each threshold?"
C. BreachConfidence      — "how wide is the uncertainty band?"
```

Total implementation: ~300 lines. Runtime per asset: < 5ms. Memory: < 1MB per asset.

---

## 3. Component A — TrendEstimator

**What it does:** Fits a robust trend line to the recent health series and returns a slope (health units / hour).

**Why Theil-Sen, not linear regression:**
Theil-Sen is the median of all pairwise slopes. It is maximally resistant to outliers (up to 29% of points can be anomalous without corrupting the slope estimate). This matters because an episode of poor health followed by recovery should not dominate the slope estimate. `scipy.stats.theilslopes` runs in O(n²) on the pairs but for n=200 points this is ~5ms — negligible.

**Regime conditioning:**
The slope must only be computed on data from the current regime. If equipment switched regime 12 hours ago, the slope from 3 days ago is meaningless. The estimator takes a `regime_label` filter parameter and computes slope only on points where `RegimeLabel == current_regime`. If there are fewer than `min_regime_samples` (default 20) points in the current regime, it falls back to an unfiltered slope with a `confidence_penalty`.

**Maintenance reset detection:**
A positive health jump > 15% in a single step (defined in Statistical Rules) signals maintenance. The estimator only uses data after the most recent jump. This prevents "we improved last week so we forecast improvement forever."

**Output:**
```python
@dataclass
class TrendResult:
    slope_per_hour: float          # Theil-Sen slope, negative = degrading
    slope_low: float               # 95% CI lower (scipy provides this)
    slope_high: float              # 95% CI upper
    fit_window_hours: float        # How much history was used
    n_points: int                  # Points in the fit
    regime_filtered: bool          # Whether regime filter was applied
    maintenance_reset_at: Optional[datetime]  # If data was truncated
    confidence: float              # 0-1, degrades with sparse/short window
```

---

## 4. Component B — HorizonProjector

**What it does:** Given a trend and the current health value, compute when the P10/P50/P90 trend trajectories cross each alarm threshold.

**The math is trivial:**
```
current_health = h0
slope = m  (units/hour, negative for degrading)
threshold = T

time_to_breach = (T - h0) / m     # positive = hours until breach
                                    # negative = already below threshold
                                    # inf = slope zero or positive (no breach)
```

For the P10 (pessimistic) trajectory, use `slope_low`. For P90 (optimistic), use `slope_high`.

**Non-linear extension:**
Linear extrapolation is accurate for early-stage degradation. For late-stage (HealthIndex < 50 and slope steepening over recent windows), we fit a quadratic using the last three slope estimates (computed over 6h, 24h, 72h windows). If the quadratic fit R² > 0.85, we use quadratic extrapolation; otherwise we stay linear. This catches accelerating degradation without overfitting.

**Output per threshold:**
```python
@dataclass
class BreachProjection:
    series_name: str               # 'HealthIndex', 'gmm_z', 'bearing_temp_z'
    threshold_name: str            # 'WARNING', 'ALERT', 'FAILURE'
    threshold_value: float
    breach_at_p50: Optional[datetime]   # None = no breach in horizon
    breach_at_p10: Optional[datetime]   # Pessimistic (earliest)
    breach_at_p90: Optional[datetime]   # Optimistic (latest)
    hours_to_breach_p50: Optional[float]
    confidence_width_hours: Optional[float]  # P90 - P10 spread
    trend_is_linear: bool          # False = quadratic used
```

---

## 5. Component C — BreachConfidence

**What it does:** Produces a single confidence score (0-1) for the breach projection. This determines whether we show the forecast at all in Grafana, and whether we page the operator.

**Confidence degrades when:**
- Short fit window (< 24h of data → low confidence)
- High slope uncertainty (slope_high - slope_low is wide)
- Recent regime switch (data used for fit spans a boundary)
- Data quality was GAPPY or NOISY
- Health is currently improving (positive slope → no credible failure projection)
- The P10/P90 spread in hours-to-breach exceeds 7 days (too uncertain to act on)

**Confidence formula (harmonic mean of sub-scores, per Statistical Rules):**
```python
window_score    = min(1.0, fit_window_hours / 168)   # saturates at 1 week
slope_score     = 1.0 - min(1.0, ci_width / abs(slope))  # normalized CI width
quality_score   = {'OK': 1.0, 'SPARSE': 0.5, 'GAPPY': 0.3, 'NOISY': 0.1}[quality]
regime_score    = 1.0 if not recent_regime_switch else 0.4
spread_score    = max(0.0, 1.0 - confidence_width_hours / (7 * 24))

confidence = harmonic_mean([window_score, slope_score, quality_score,
                            regime_score, spread_score])
```

**Suppression rule:** If `confidence < 0.25`, no forecast is written. The SQL row gets `QualityOK = 0` and `ProjectedBreachAt = NULL`.

---

## 6. What Series We Forecast

### 6.1 HealthIndex — Always, first

Load from `ACM_HealthTimeline` for the current run (single-run window, no cross-batch concatenation). Apply maintenance reset detection. Fit Theil-Sen slope. Project against:

- WARNING zone boundary (e.g. HealthIndex = 70)
- ALERT zone boundary (e.g. HealthIndex = 50)
- FAILURE threshold (from DataContract)

This is the only series needed for Phase 1. It answers the operator's primary question.

### 6.2 Stable Detector Z-Scores — Phase 2

After z-score cross-batch continuity is fixed, add `gmm_z` and `omr_z` (the two detectors with stable per-batch behavior, confirmed from the Grafana data coverage analysis). Project against `thresholds.alert = 3.0`.

Skip `ar1_z` and `cusum_z` until their state persistence across batches is implemented.

### 6.3 Top-K Sensor Z-Scores — Phase 3

Take the top-K sensors from `ACM_SensorHotspots` by `MaxAbsZ`. Their z-scores are in `ACM_Scores_Wide` (implicitly via the detector attribution) or in the raw historian normalized form. Forecast each independently. This is the drill-down layer.

---

## 7. What the Outputs Mean in Practice

The outputs of this system are not numbers — they are maintenance decisions. Frame them that way:

| Confidence | Health breach in | Action |
|---|---|---|
| > 0.7 | < 48h | Page on-call technician |
| > 0.7 | 2–7 days | Schedule next maintenance window |
| > 0.7 | > 7 days | No action, monitor |
| 0.25–0.7 | Any | Show in dashboard, do not page |
| < 0.25 | Any | Suppress — insufficient data |

The maintenance scheduling use case requires `ProjectedBreachAt` to have a real calendar timestamp, not just "N hours from now." The projector anchors to the last actual data point timestamp and adds `hours_to_breach` to get a wall-clock datetime.

---

## 8. Why Not Use Holt-Winters / Prophet / ARIMA

**Holt-Winters:** Good for seasonal data. Industrial equipment health is not seasonal — it degrades monotonically (or improves after maintenance). Seasonality modeling adds noise here.

**Prophet (Facebook):** Excellent model, but it is a large dependency (~50MB), requires pandas, and its additive/multiplicative seasonality model is again designed for business time series with weekly/annual patterns. Overkill and wrong shape for the problem.

**ARIMA:** Requires stationarity. Degrading health is definitionally non-stationary. You would need to difference the series first, which destroys the trend information you are trying to capture. The correct formulation is ARIMA(0,1,0) which is just a random walk — equivalent to "last observed value + noise." That is less informative than Theil-Sen slope extrapolation.

**ETS / exponential smoothing:** Reasonable, but the `statsmodels` ETS is slow and heavyweight for this use case, and its uncertainty intervals are symmetric which is wrong for bounded series near the floor.

**Conclusion:** Theil-Sen with quadratic acceleration detection is the right method. It is the industrial standard for condition-based prognostics (referenced in ISO 13381-1), requires no fitting, and runs in microseconds.

---

## 9. Full Architecture (Clean)

```
core/
  degradation_trend.py      ← TrendEstimator (Theil-Sen, regime-conditioned)
  horizon_projector.py      ← HorizonProjector (linear/quadratic extrapolation)
  breach_confidence.py      ← BreachConfidence (harmonic confidence score)
  forecast_coordinator.py   ← thin orchestrator: load → estimate → project → write

install/sql/
  20_forecast_tables.sql    ← ACM_HealthForecast, ACM_BreachProjections

configs/config_table.csv    ← new keys (all disabled by default)
```

The old `core/forecast_engine.py`, `core/degradation_model.py`, `core/rul_estimator.py`, `core/health_tracker.py`, `core/state_manager.py`, `core/multivariate_forecast.py` are **left in place but remain disabled**. We do not delete code mid-refactor. They can be removed after Phase 1 is validated.

---

## 10. SQL Schema

### `ACM_HealthForecast` — trajectory per run

```sql
CREATE TABLE dbo.ACM_HealthForecast (
    ForecastID       BIGINT IDENTITY(1,1) NOT NULL,
    RunID            NVARCHAR(64)  NOT NULL,
    EquipID          INT           NOT NULL,
    ForecastAt       DATETIME2(3)  NOT NULL,  -- absolute calendar timestamp
    StepIndex        INT           NOT NULL,  -- 0-based
    ValueP50         FLOAT         NULL,      -- Theil-Sen slope extrapolated
    ValueP10         FLOAT         NULL,      -- pessimistic slope
    ValueP90         FLOAT         NULL,      -- optimistic slope
    CreatedAt        DATETIME2(3)  NOT NULL DEFAULT GETDATE(),
    CONSTRAINT PK_ACM_HealthForecast PRIMARY KEY (ForecastID)
);
CREATE INDEX IX_ACM_HealthForecast_Equip ON dbo.ACM_HealthForecast (EquipID, ForecastAt DESC);
```

### `ACM_BreachProjections` — when does each threshold get hit

```sql
CREATE TABLE dbo.ACM_BreachProjections (
    ProjectionID          BIGINT IDENTITY(1,1) NOT NULL,
    RunID                 NVARCHAR(64)  NOT NULL,
    EquipID               INT           NOT NULL,
    SeriesName            NVARCHAR(128) NOT NULL,  -- 'HealthIndex', 'gmm_z', etc.
    ThresholdName         NVARCHAR(64)  NOT NULL,  -- 'WARNING', 'ALERT', 'FAILURE'
    ThresholdValue        FLOAT         NOT NULL,
    SlopePerHour          FLOAT         NULL,      -- the fitted slope
    SlopeCI_Low           FLOAT         NULL,
    SlopeCI_High          FLOAT         NULL,
    FitWindowHours        FLOAT         NULL,
    FitPoints             INT           NULL,
    TrendIsLinear         BIT           NOT NULL DEFAULT 1,
    BreachAt_P50          DATETIME2(3)  NULL,      -- NULL = no breach in horizon
    BreachAt_P10          DATETIME2(3)  NULL,
    BreachAt_P90          DATETIME2(3)  NULL,
    HoursToBreachP50      FLOAT         NULL,
    ConfidenceWidthHours  FLOAT         NULL,
    Confidence            FLOAT         NULL,      -- 0-1 harmonic score
    QualityOK             BIT           NOT NULL DEFAULT 1,
    HorizonHours          FLOAT         NOT NULL,
    CreatedAt             DATETIME2(3)  NOT NULL DEFAULT GETDATE(),
    CONSTRAINT PK_ACM_BreachProjections PRIMARY KEY (ProjectionID)
);
CREATE INDEX IX_ACM_BreachProjections_Equip_Breach
    ON dbo.ACM_BreachProjections (EquipID, BreachAt_P50 ASC);
```

---

## 11. Config Keys

| Key | Default | Description |
|---|---|---|
| `forecasting.enabled` | `false` | Master switch |
| `runtime.phases.forecast` | `false` | QA gate |
| `forecasting.horizon_hours` | `168` | How far ahead to project (7 days) |
| `forecasting.min_history_hours` | `24` | Min history in current run before forecasting |
| `forecasting.min_fit_points` | `20` | Min points for Theil-Sen fit |
| `forecasting.confidence_threshold` | `0.25` | Below this → suppress output |
| `forecasting.use_quadratic` | `true` | Enable quadratic acceleration detection |
| `forecasting.step_hours` | `1.0` | Granularity of forecast trajectory (1h steps) |
| `forecasting.series.include_detectors` | `false` | Phase 2 |
| `forecasting.series.include_sensors` | `false` | Phase 3 |
| `forecasting.series.max_sensors` | `5` | Top-K sensors |

---

## 12. Implementation Phases

### Phase 1 — HealthIndex Forecast (core value, minimal risk)

Files to create:
- `core/degradation_trend.py` — TrendEstimator
- `core/horizon_projector.py` — HorizonProjector + BreachProjection
- `core/breach_confidence.py` — BreachConfidence scorer
- `core/forecast_coordinator.py` — orchestrator (< 100 lines)
- `install/sql/20_forecast_tables.sql` — two new tables
- Config keys added and synced

Dependencies added: **zero** (scipy already in requirements for `health_tracker.py`)

What gets written each run: `ACM_HealthForecast` rows + `ACM_BreachProjections` rows for WARNING/ALERT/FAILURE thresholds.

### Phase 2 — Stable Detector Z-Scores

Extend `ForecastCoordinator.run()` to include `gmm_z` and `omr_z`. Load their series from `ACM_Scores_Wide` within the current run window. Add `ForecastCoordinator._load_zscore_series()`. Gated behind `forecasting.series.include_detectors = true`.

Precondition: cross-batch z-score continuity is not required here because we only use data within the current single run window. The batch-boundary discontinuity problem does not apply if we never concatenate across runs.

### Phase 3 — Top-K Sensor Z-Scores

Load top-K sensors from `ACM_SensorHotspots`. Their z-scores exist as normalized values in `ACM_SensorNormalized_TS`. Gated behind `forecasting.series.include_sensors = true`.

---

## 13. Grafana Integration

### Panel: Health Forecast Fan

Historical `HealthIndex` + P10/P50/P90 extrapolation lines. Threshold lines drawn as static rules at WARNING/ALERT/FAILURE values. Fan generated from `ACM_HealthForecast`.

```sql
SELECT ForecastAt AS time, ValueP50 AS value, 'Forecast P50' AS metric
FROM dbo.ACM_HealthForecast
WHERE EquipID = $equipment
  AND RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)
ORDER BY ForecastAt ASC
-- (plus two more UNION ALL for P10 and P90)
```

### Panel: Breach Timeline (Table)

The primary operational output. Shows what will alarm and when.

```sql
SELECT
    SeriesName,
    ThresholdName,
    CASE WHEN BreachAt_P50 IS NULL THEN 'No breach in ' + CAST(CAST(HorizonHours AS INT) AS NVARCHAR) + 'h'
         ELSE CAST(CAST(DATEDIFF(hour, GETDATE(), BreachAt_P50) AS INT) AS NVARCHAR) + 'h (P50)'
    END AS TimeToBreachP50,
    CASE WHEN BreachAt_P10 IS NULL THEN NULL
         ELSE CAST(CAST(DATEDIFF(hour, GETDATE(), BreachAt_P10) AS INT) AS NVARCHAR) + 'h'
    END AS Earliest,
    CAST(CAST(ROUND(ConfidenceWidthHours, 0) AS INT) AS NVARCHAR) + 'h' AS Uncertainty,
    CAST(ROUND(Confidence * 100, 0) AS INT) AS ConfidencePct
FROM dbo.ACM_BreachProjections
WHERE EquipID = $equipment
  AND RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)
  AND QualityOK = 1
ORDER BY BreachAt_P50 ASC
```

---

## 14. Explicit Non-Goals

These are out of scope and should not creep in:

- **RUL (Remaining Useful Life) in hours** — dropped. RUL implies a known failure threshold and a reliable degradation model fitted on failure-to-failure history. We do not have failure-to-failure training data. What we have is `hours_to_breach_p50` which is technically a conditional RUL given the current trend, but we call it what it is: "projected time to threshold."
- **Foundation models** — not for this problem at this scale.
- **Seasonality modeling** — industrial health is not seasonal.
- **Cross-asset fleet-level modeling** — different assets degrade differently. Fleet averaging destroys the signal.
- **Classification ("will fail: yes/no")** — we do trend extrapolation. Binary classification requires labeled failure data we do not have.

---

## 15. Open Questions Before Coding

1. **What are the actual zone boundaries?** What HealthIndex value separates HEALTHY from WARNING, WARNING from ALERT, ALERT from FAILURE? These need to come from `DataContract` or config — confirm where they are stored.

2. **Single-run only or multi-run concatenation?** The analysis showed 12-day gaps between runs for WFA_TURBINE_0. Using only the current run's health data keeps things clean but limits context to the current batch window. For equipment with short batches (< 6h), the fit window may be too short for reliable slope estimation. Decision needed: do we allow loading the previous N runs for slope fitting, accepting the risk of cross-batch discontinuity?

3. **Step resolution of the trajectory:** At what interval do we write `ACM_HealthForecast` rows? 1-hour steps over 7 days = 168 rows per run. That is fine. At 10-minute steps it would be 1008 rows — heavier but gives a smoother Grafana chart. Suggest 1-hour steps for Phase 1.

4. **Where are zone boundaries stored?** `DataContract`, `ACM_Config`, or hardcoded in the fuser? This determines how `HorizonProjector` gets the threshold values to project against.

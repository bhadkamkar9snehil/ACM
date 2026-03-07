# TimesFM Multivariate Forecasting — Integration Design

Date: 2026-02-21
Owner: Snehil
Status: Design — not yet implemented

---

## 0. The Central Question: What Are We Forecasting?

Before any code, you need to be clear about this. There are three completely different things we could forecast, and they are not interchangeable:

---

### Option A — Forecast Raw Sensor Values

**What:** Feed the historian time series for each sensor into TimesFM and predict their future values (e.g. temperature in 48h, vibration in 7 days).

**What you get:** "Sensor X will read 87°C in 3 days."

**What you do NOT automatically get:** Any understanding of whether that is healthy or anomalous. You would need to re-run the detector ensemble on the forecasted sensor values to derive a health implication.

**The hard problem:** We have potentially hundreds of sensors. TimesFM is univariate — each sensor gets its own inference call (or they are batched). The sensor values exist in raw physical units (RPM, °C, bar) that are not normalized to a common scale. Forecasting them in raw form gives you future readings, not future health.

**The useful case:** Early warning for individual sensor threshold breaches (e.g. bearing temperature projected to exceed OEM limit in 36h). This is actionable on its own without re-running detectors.

---

### Option B — Forecast Detector Z-Scores

**What:** Take the historical z-score time series for each detector head (ar1_z, pca_spe_z, gmm_z, etc.) from `ACM_Scores_Wide` and forecast their future values.

**What you get:** "GMM z-score will cross 3.0 in approximately 5 days."

**Why this is interesting:** Z-scores are already normalized, bounded in a meaningful range, and directly map to alarm thresholds. Forecasting z-scores directly gives you an expected alarm timeline without needing to re-run the full detector ensemble.

**The hard problem:** Z-scores between batches have discontinuities because each batch re-calibrates with `ScoreCalibrator`. A z-score of 2.0 in batch 1 is not the same as 2.0 in batch 3 if calibration shifted. We established this in the Grafana analysis. Feeding raw z-score series across batches to TimesFM would train it on a non-stationary signal.

**The useful case:** If we fix the CUSUM/AR1 cross-batch continuity bugs first, z-score forecasting becomes viable and directly answers "when will each detector alarm?"

---

### Option C — Forecast the Fused Health Index

**What:** Take the `HealthIndex` column from `ACM_HealthTimeline` and forecast its future trajectory.

**What you get:** A single number — projected health in N days, with uncertainty bounds (P10/P50/P90).

**Why this is the cleanest starting point:** `HealthIndex` is:
- Already a single bounded scalar (0–100 or similar)
- Computed by the fuser which absorbs all detector disagreement
- Stable across batches relative to raw z-scores
- Directly human-interpretable ("health will drop from 82 to 65 in 10 days")

**What you do NOT get:** Per-sensor or per-detector early warning. You get aggregate health trajectory only.

**The useful case:** Maintenance scheduling ("book the team for day 8-10"), spare parts lead time, shift supervisor communication.

---

### The Recommended Approach: Option C now, Option A later

Start with forecasting the fused `HealthIndex` because it is:
- Stationary within a run
- Already available in SQL
- Directly meaningful to operators

Add sensor-level (Option A) later as a drill-down layer once the health forecast is working. Option B (z-score forecasting) requires fixing the cross-batch calibration bugs first.

---

## 1. What TimesFM Actually Does (and Doesn't Do)

TimesFM is a **univariate** foundation model. One call forecasts one time series. Despite the word "multivariate" in some descriptions, the API is:

```python
point_forecast, quantile_forecast = model.forecast(
    horizon=H,
    inputs=[series_1, series_2, series_3, ...]  # batch of univariate series
)
# output shapes: (batch, horizon) and (batch, horizon, 10)
```

"Multivariate" in the TimesFM context means: run multiple univariate series in one batched GPU call. The model does **not** model cross-series dependencies — each series is forecasted independently.

If you want to model the fact that "when bearing temperature rises, vibration follows 2 hours later", TimesFM alone cannot do that. That requires the VAR (Vector Autoregression) approach that `core/multivariate_forecast.py` was building toward, or a multivariate transformer like Lag-Llama or Chronos-Bolt (not TimesFM).

**What TimesFM gives us:**
- Zero-shot, high-quality univariate extrapolation with uncertainty
- Works on any length series (up to 16k steps)
- No training required
- Runs in ~200ms per batch on CPU

**What it cannot do:**
- Model cross-sensor causal dependencies
- Detect anomalies in the forecast (that's still the detector ensemble's job)
- Produce RUL estimates directly (that requires a failure threshold and a slope model)

---

## 2. The Full Forecasting Chain

Here is what a complete forecasting layer looks like with TimesFM at its core:

```
ACM Batch Run (scoring complete)
│
├── [INPUT] ACM_HealthTimeline: HealthIndex time series (past N hours)
├── [INPUT] ACM_Scores_Wide: per-detector z-score series (past N hours)
├── [INPUT] Historian raw sensor data (past N hours) — optional
│
▼
TimesFM Batch Inference
├── Series 1: HealthIndex → forecast H hours forward → health_P10, P50, P90
├── Series 2–8: ar1_z, pca_spe_z, pca_t2_z, gmm_z, cusum_z, iforest_z, omr_z
│                  → each gets its own P10/P50/P90 trajectory
│                  (these cross-batch continuity issues apply here)
└── Series N+: raw sensor values for top-K sensors (from SensorHotspots)
               → e.g. bearing_temp, shaft_vibration_x, lube_pressure
│
▼
Post-processing Layer
├── Health trajectory → "health will reach [warning zone] in ~X hours" (P50)
│                     → earliest breach time = P10 trajectory crossing 70
├── Detector z-scores → "GMM will cross 3.0 in ~Y hours" (P50 trajectory)
├── Sensor forecasts  → "bearing_temp will exceed 90°C in ~Z hours" (P50)
│
▼
ACM_TimesFMForecast table (per-step P10/P50/P90 for each series)
│
▼
Derived Alarm Forecast table (ACM_ForecastAlarms)
│  RunID, EquipID, SeriesType (health/detector/sensor), SeriesName
│  ProjectedBreachAt (datetime), ConfidenceP10, ConfidenceP90
│  ThresholdUsed, HorizonHours, QualityOK
│
▼
Grafana Dashboard
├── Health Forecast panel: actual + P10/P50/P90 fan chart
├── Detector Forecast panel: z-score trajectories with threshold lines
├── Sensor Forecast panel: top-3 sensors with projected breach markers
└── Alarm Horizon panel: table of "what will alarm and when"
```

The key insight is that TimesFM does the extrapolation, and a thin post-processing layer converts trajectories into **projected alarm times** — which is what maintenance engineers actually need.

---

## 3. What "Forecasting Failures and Defects" Means

You asked specifically about forecasting failures and defects. Here is what that means precisely:

### Forecasting failures

A "failure" in ACM is when `HealthIndex` drops below the configured failure threshold (typically 20–30). TimesFM forecasts the `HealthIndex` trajectory. A failure is forecast when the P50 trajectory is projected to cross the failure threshold within the horizon. The P10 (pessimistic) trajectory crossing threshold gives the earliest credible failure time; P90 gives the latest.

This is **not** a classification model predicting "will fail: yes/no". It is extrapolation: "if current degradation trend continues, threshold will be breached in approximately X hours."

**Condition:** Only meaningful when `HealthIndex` is actually declining. If health is flat or improving, no failure horizon exists within the forecast window.

### Forecasting defects

A "defect" in ACM is when a detector z-score persistently exceeds the alert threshold (3.0 by default). TimesFM can forecast individual detector z-scores forward. A defect is projected when the P50 z-score trajectory is projected to exceed 3.0 and stay above it for more than `defect_min_duration` consecutive steps.

**Condition:** Requires cross-batch z-score continuity. Currently broken for AR1 and CUSUM (see known drift bugs). GMM and OMR are more stable across batches and are viable candidates for z-score forecasting immediately.

### Forecasting health zones

`HealthZone` in `ACM_HealthTimeline` is derived from `HealthIndex` thresholds (HEALTHY/WARNING/CRITICAL/FAILURE). Forecasting zone transitions is equivalent to finding where the P10/P50/P90 health trajectories cross the zone boundaries. No additional model is needed — it is pure threshold arithmetic on the health forecast.

---

## 4. Architecture Design

### 4.1 Module Structure

```
core/
  timesfm_forecaster.py    ← NEW: TimesFM adapter + singleton model management
  forecast_coordinator.py  ← NEW: orchestrates series selection, inference, post-processing
  alarm_projector.py       ← NEW: converts trajectories to projected alarm times

install/sql/
  20_timesfm_tables.sql    ← NEW: ACM_TimesFMForecast, ACM_ForecastAlarms tables

configs/config_table.csv
  forecasting.enabled = false
  forecasting.timesfm.*
  forecasting.series.*
```

The existing `core/forecast_engine.py` (RUL-based) is left untouched and remains disabled. The new layer is completely independent.

### 4.2 Data Flow in Detail

```
ForecastCoordinator.run(equip_id, run_id, sql_client, config)
│
├── 1. Load series
│     ├── health_series   ← SELECT HealthIndex, Timestamp FROM ACM_HealthTimeline
│     │                      WHERE RunID IN (last N runs) ORDER BY Timestamp
│     ├── zscore_series   ← SELECT ar1_z, gmm_z, omr_z FROM ACM_Scores_Wide
│     │                      (only detectors with stable cross-batch behavior)
│     └── sensor_series   ← SELECT SensorName, MaxAbsZ FROM ACM_SensorHotspots
│                            → pick top-K sensors → load from historian (optional)
│
├── 2. Validate series
│     ├── min_length check (< 24 points → skip that series)
│     ├── variance check (flatline → skip)
│     └── gap check (> 20% missing → forward-fill or skip)
│
├── 3. TimesFM batch inference
│     inputs = [health_array, gmm_z_array, omr_z_array, ...]
│     point_fc, quantile_fc = model.forecast(horizon=H, inputs=inputs)
│
├── 4. Post-processing per series
│     └── AlarmProjector.project(series_name, forecast_array, threshold, step_hours)
│           → ProjectedAlarm(breach_at_p10, breach_at_p50, breach_at_p90)
│
└── 5. Write to SQL
      ├── ACM_TimesFMForecast: full per-step trajectories (for charts)
      └── ACM_ForecastAlarms:  projected breach times (for operational use)
```

### 4.3 Series Selection Logic

Not all series should be forecast. The coordinator applies this selection:

| Series | Include? | Condition |
|---|---|---|
| `HealthIndex` | Always | If >= 24 history points exist |
| `ar1_z` | No | Cross-batch reset artifact makes it non-stationary |
| `cusum_z` | No | Cross-batch state loss makes it non-stationary |
| `pca_spe_z` | Conditional | Only if > 50% non-sentinel rows exist in history |
| `pca_t2_z` | Conditional | Same as pca_spe_z |
| `gmm_z` | Yes | Generally stable |
| `iforest_z` | Conditional | Only if data coverage > 50% |
| `omr_z` | Yes | 100% coverage, stable |
| Raw sensors | Yes (top-K) | Top K sensors by `MaxAbsZ` from `ACM_SensorHotspots` |

The config key `forecasting.series.max_sensors` controls K (default 5).

---

## 5. What the Projected Alarm Tells Operators

The output of `AlarmProjector` is a projected breach time — not a binary alarm. It answers:

> "If the current trend continues, **bearing_temp** will exceed the WARNING threshold in approximately **36 hours** (earliest: 18h, latest: 72h)."

This is expressed as:
- `ProjectedBreachAt` (P50 trajectory crossing) — best estimate
- `ProjectedBreachAt_P10` — pessimistic (earliest)
- `ProjectedBreachAt_P90` — optimistic (latest)
- `ConfidenceWidth` = P90 − P10 in hours — wider = less certain

When `ConfidenceWidth` is large (e.g. the P10/P90 spread is 5 days), the forecast is telling you "something is changing but we can not say exactly when." When it is narrow, the trend is strong and consistent.

If the P50 trajectory does **not** cross the threshold within the forecast horizon, no `ProjectedBreachAt` exists — the field is NULL, meaning "no alarm expected in the next N hours at current trend."

---

## 6. SQL Tables

### 6.1 `ACM_TimesFMForecast` — Full trajectory storage

```sql
CREATE TABLE dbo.ACM_TimesFMForecast (
    ForecastID       BIGINT IDENTITY(1,1) NOT NULL,
    RunID            NVARCHAR(64)  NOT NULL,
    EquipID          INT           NOT NULL,
    SeriesType       NVARCHAR(32)  NOT NULL,  -- 'health', 'detector', 'sensor'
    SeriesName       NVARCHAR(128) NOT NULL,  -- 'HealthIndex', 'gmm_z', 'bearing_temp'
    StepIndex        INT           NOT NULL,  -- 0-based horizon step
    ForecastAt       DATETIME2(3)  NOT NULL,  -- calendar datetime of this step
    ValueP10         FLOAT         NULL,
    ValueP50         FLOAT         NULL,
    ValueP90         FLOAT         NULL,
    ContextLength    INT           NULL,      -- how many history points were used
    QualityOK        BIT           NOT NULL DEFAULT 1,
    CreatedAt        DATETIME2(3)  NOT NULL DEFAULT GETDATE(),
    CONSTRAINT PK_ACM_TimesFMForecast PRIMARY KEY CLUSTERED (ForecastID),
);
CREATE INDEX IX_ACM_TimesFMForecast_Equip_Series
    ON dbo.ACM_TimesFMForecast (EquipID, SeriesName, ForecastAt DESC);
```

### 6.2 `ACM_ForecastAlarms` — Projected breach times

```sql
CREATE TABLE dbo.ACM_ForecastAlarms (
    AlarmID               BIGINT IDENTITY(1,1) NOT NULL,
    RunID                 NVARCHAR(64)  NOT NULL,
    EquipID               INT           NOT NULL,
    SeriesType            NVARCHAR(32)  NOT NULL,
    SeriesName            NVARCHAR(128) NOT NULL,
    ThresholdName         NVARCHAR(64)  NOT NULL,  -- 'WARNING', 'ALERT', 'FAILURE', 'OEM_LIMIT'
    ThresholdValue        FLOAT         NOT NULL,
    ProjectedBreachAt     DATETIME2(3)  NULL,       -- NULL = no breach in horizon
    ProjectedBreachAt_P10 DATETIME2(3)  NULL,       -- earliest (pessimistic)
    ProjectedBreachAt_P90 DATETIME2(3)  NULL,       -- latest (optimistic)
    ConfidenceWidthHours  FLOAT         NULL,       -- P90-P10 spread
    HorizonHours          FLOAT         NOT NULL,
    CreatedAt             DATETIME2(3)  NOT NULL DEFAULT GETDATE(),
    CONSTRAINT PK_ACM_ForecastAlarms PRIMARY KEY CLUSTERED (AlarmID),
);
CREATE INDEX IX_ACM_ForecastAlarms_Equip_Breach
    ON dbo.ACM_ForecastAlarms (EquipID, ProjectedBreachAt ASC);
```

---

## 7. Grafana Panels

### Panel 1: Health Forecast Fan Chart

Overlays actual `HealthIndex` history with the P10/P50/P90 forecast fan.

```sql
-- Historical (last 14 days)
SELECT h.Timestamp AS time, h.HealthIndex AS value, 'Actual Health' AS metric
FROM dbo.ACM_HealthTimeline h
WHERE h.EquipID = $equipment
  AND h.Timestamp >= DATEADD(day, -14, GETDATE())
  AND h.RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)
UNION ALL
-- Forecast P50
SELECT ForecastAt AS time, ValueP50 AS value, 'Forecast (P50)' AS metric
FROM dbo.ACM_TimesFMForecast
WHERE EquipID = $equipment AND SeriesName = 'HealthIndex'
  AND RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)
  AND QualityOK = 1
UNION ALL
-- Confidence band lower
SELECT ForecastAt AS time, ValueP10 AS value, 'Forecast (P10)' AS metric
FROM dbo.ACM_TimesFMForecast
WHERE EquipID = $equipment AND SeriesName = 'HealthIndex'
  AND RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)
  AND QualityOK = 1
UNION ALL
-- Confidence band upper
SELECT ForecastAt AS time, ValueP90 AS value, 'Forecast (P90)' AS metric
FROM dbo.ACM_TimesFMForecast
WHERE EquipID = $equipment AND SeriesName = 'HealthIndex'
  AND RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)
  AND QualityOK = 1
ORDER BY time ASC
```

Series overrides: P10/P90 as shaded area fill pair; P50 as dashed green; Actual as solid blue.

### Panel 2: Projected Alarm Horizon (Table)

```sql
SELECT
    SeriesName,
    SeriesType,
    ThresholdName,
    CASE
        WHEN ProjectedBreachAt IS NULL THEN 'No breach in horizon'
        ELSE CAST(DATEDIFF(hour, GETDATE(), ProjectedBreachAt) AS NVARCHAR) + 'h'
    END AS TimeToBreachP50,
    CASE
        WHEN ProjectedBreachAt_P10 IS NULL THEN NULL
        ELSE CAST(DATEDIFF(hour, GETDATE(), ProjectedBreachAt_P10) AS NVARCHAR) + 'h'
    END AS EarliestBreach,
    CAST(ROUND(ConfidenceWidthHours, 0) AS NVARCHAR) + 'h' AS ConfidenceRange
FROM dbo.ACM_ForecastAlarms
WHERE EquipID = $equipment
  AND RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)
ORDER BY ProjectedBreachAt ASC
```

This table is the operational output — what the shift engineer looks at. It says: "bearing_temp WARNING in 18h (±12h)".

---

## 8. Limitations and Honest Expectations

### What TimesFM cannot tell you

1. **Root cause.** It extrapolates trends. It does not know why health is declining. That is the detector ensemble's job.
2. **Step changes.** If a bearing seizes suddenly, no trend model predicts it. TimesFM only works on gradual degradation patterns.
3. **Cross-sensor causality.** "Bearing temperature rising will cause vibration to rise in 4 hours" requires a multivariate model (VAR or similar). TimesFM gives independent per-sensor forecasts.
4. **Non-stationary regimes.** If the equipment switches operating regime mid-forecast window, the forecast becomes unreliable. The confidence width will be large, which is the signal to distrust it.

### When forecasts should be suppressed (QualityOK = 0)

- History shorter than `forecasting.min_history_hours` (default 72h)
- Health is flat (< 2 units variance in history) — nothing to extrapolate
- Health is increasing (improving) — no degradation alarm is valid
- Data gaps > 20% of context window
- TimesFM model not loaded (weights not cached)
- Forecast range exceeds 3× historical range (wild extrapolation)

---

## 9. Implementation Phases

### Phase 1 — Health Index Forecast Only

Scope: forecast `HealthIndex` only. Write full P10/P50/P90 trajectory to `ACM_TimesFMForecast`. No alarm projection yet. Enable Grafana fan chart. Validate against known degradation episodes in historical data.

Files:
- `core/timesfm_forecaster.py` — model singleton + inference adapter
- `core/forecast_coordinator.py` — health series load + inference call
- `install/sql/20_timesfm_tables.sql` — create tables
- `configs/config_table.csv` — new keys, all disabled by default

### Phase 2 — Alarm Projection

Scope: add `AlarmProjector` that converts P10/P50/P90 trajectories to `ProjectedBreachAt` rows. Write to `ACM_ForecastAlarms`. Enable Grafana alarm horizon table panel.

Files:
- `core/alarm_projector.py`
- `core/output_manager.py` — two new write methods

### Phase 3 — Detector Z-Score Forecasting (after fixing cross-batch bugs)

Scope: extend series selection to include stable detectors (GMM, OMR). Feed their z-score history. Project breach of the `thresholds.alert` value (3.0). Write per-detector alarm projections.

Precondition: the AR1/CUSUM cross-batch continuity bugs must be fixed first, otherwise the z-score time series fed to TimesFM is non-stationary garbage.

### Phase 4 — Top-K Sensor Forecasting (Optional)

Scope: take the top-5 sensors from `ACM_SensorHotspots` by `MaxAbsZ`. Load their normalized values from `ACM_SensorNormalized_TS`. Forecast each independently. Project breach of the per-sensor warning threshold. Write to both tables.

---

## 10. Config Keys

Add to `configs/config_table.csv`:

| Key | Default | Description |
|---|---|---|
| `forecasting.enabled` | `false` | Master switch |
| `runtime.phases.forecast` | `false` | QA gate — enable after Phase 1 validated |
| `forecasting.timesfm.model_id` | `google/timesfm-2.5-200m-pytorch` | HuggingFace model ID |
| `forecasting.timesfm.max_context` | `512` | Max history steps (at 10-min intervals = 85h) |
| `forecasting.timesfm.max_horizon` | `128` | Max forecast steps (at 10-min = 21h; at 1h = 5.3 days) |
| `forecasting.timesfm.device` | `cpu` | `cpu` or `cuda` |
| `forecasting.horizon_hours` | `168` | How far ahead to forecast (7 days) |
| `forecasting.min_history_hours` | `72` | Min history before forecasting |
| `forecasting.series.include_detectors` | `false` | Enable z-score series (Phase 3) |
| `forecasting.series.include_sensors` | `false` | Enable raw sensor series (Phase 4) |
| `forecasting.series.max_sensors` | `5` | How many top sensors to forecast |

---

## 11. Open Questions to Resolve Before Coding

1. **Historian step interval**: Is historian data always at a fixed interval (10 min? 1 min? variable)? TimesFM assumes uniform time steps. If variable, we need to resample to a fixed grid before feeding.

2. **How many history runs to use for context**: The `max_context` of 512 steps must cover enough history to capture a degradation trend. At 10-min intervals, 512 steps = ~85 hours. Is that enough? For slow equipment degradation (weeks), we need longer context or hourly resampling.

3. **Quantile tensor exact layout**: TimesFM 2.5 output is described as "mean plus decile quantiles." Whether the mean is index 0 and P10 is index 1 must be confirmed with a one-line test before any production code is written. Do not assume.

4. **Cross-batch health continuity**: `ACM_HealthTimeline` spans multiple runs. When we load health history across runs (to get 72+ hours of context), are there gaps between runs? The data showed 12-day gaps for WFA_TURBINE_0. Do we concatenate runs ignoring gaps, or only use data from the current run?

5. **Failure threshold value**: The `AlarmProjector` needs to know the failure threshold for each series. For `HealthIndex` this comes from `DataContract` (default ~20). For detector z-scores it is `thresholds.alert` (default 3.0). For raw sensors it is the OEM limit (not stored in ACM currently — would need a new table or config).

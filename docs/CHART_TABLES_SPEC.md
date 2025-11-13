# Chart Tables Specification

**Purpose:** Define the exact CSV schema for each chart's data table. These tables will be generated in `{run_dir}/tables/` and eventually migrated to SQL storage.

**Design Principles:**
1. **SQL-ready schema** - All tables use SQL-compatible column names and types
2. **Timestamp consistency** - All timestamps in UTC ISO format (`YYYY-MM-DD HH:MM:SS+00:00`)
3. **Denormalized for charting** - Optimized for direct chart rendering, not normalization
4. **Metadata included** - Each table includes context columns (EquipID, RunID where applicable)

---

## 1. Overall Health Trend

### `tables/health_timeline.csv`

**Purpose:** Time series of overall health index with zone classification

**Schema:**
```csv
timestamp,health_index,zone,fused_z,regime_id,regime_state
```

**Columns:**
- `timestamp` (datetime): UTC timestamp
- `health_index` (float): 0-100 scale (100=perfect, 0=critical)
- `zone` (string): `GOOD` | `WATCH` | `ALERT`
- `fused_z` (float): Raw fused z-score
- `regime_id` (int): Active regime label
- `regime_state` (string): `healthy` | `degraded` | `faulty` | `unknown`

**Example:**
```csv
timestamp,health_index,zone,fused_z,regime_id,regime_state
2013-01-01 00:00:00+00:00,95.2,GOOD,-0.14,2,healthy
2013-01-01 01:00:00+00:00,94.8,GOOD,0.23,2,healthy
2013-01-01 02:00:00+00:00,87.3,WATCH,1.52,2,healthy
```

---

### `tables/health_forecast.csv` (OPTIONAL - requires TODO #20)

**Purpose:** Short-term forecast of health index

**Schema:**
```csv
timestamp,yhat,yhat_lo,yhat_hi
```

**Columns:**
- `timestamp` (datetime): Future timestamp
- `yhat` (float): Point forecast
- `yhat_lo` (float): Lower confidence bound (e.g., 80% CI)
- `yhat_hi` (float): Upper confidence bound

---

## 2. Regime Ribbon

### `tables/regime_timeline.csv`

**Purpose:** Regime state over time (timeline strip visualization)

**Schema:**
```csv
timestamp,regime_id,regime_name,regime_state,confidence
```

**Columns:**
- `timestamp` (datetime): UTC timestamp
- `regime_id` (int): Cluster label (0, 1, 2, ...)
- `regime_name` (string): Human-readable name (e.g., "High Load", "Idle")
- `regime_state` (string): `healthy` | `degraded` | `faulty` | `unknown`
- `confidence` (float): Regime assignment confidence (0-1)

**Example:**
```csv
timestamp,regime_id,regime_name,regime_state,confidence
2013-01-01 00:00:00+00:00,2,Normal Operation,healthy,0.89
2013-01-01 01:00:00+00:00,2,Normal Operation,healthy,0.91
2013-01-01 02:00:00+00:00,1,High Load,healthy,0.76
```

---

## 3. Sensors vs Learned Normal

### `tables/sensor_norm_bands.csv`

**Purpose:** Raw sensor values with normal range bands (3-5 key sensors)

**Schema:**
```csv
timestamp,sensor,value,norm_lo,norm_hi,breached
```

**Columns:**
- `timestamp` (datetime): UTC timestamp
- `sensor` (string): Sensor name (e.g., `DEMO.SIM.FSAB`)
- `value` (float): Actual sensor reading
- `norm_lo` (float): Lower normal bound (e.g., P5 or μ-2σ)
- `norm_hi` (float): Upper normal bound (e.g., P95 or μ+2σ)
- `breached` (int): 0=normal, 1=breached

**Example:**
```csv
timestamp,sensor,value,norm_lo,norm_hi,breached
2013-01-01 00:00:00+00:00,DEMO.SIM.FSAB,23.5,20.0,30.0,0
2013-01-01 00:00:00+00:00,DEMO.SIM.FGAB,45.2,40.0,50.0,0
2013-01-01 01:00:00+00:00,DEMO.SIM.FSAB,32.1,20.0,30.0,1
```

---

## 4. Contribution Now

### `tables/contrib_now.csv`

**Purpose:** Current sensor contribution to anomaly score (single snapshot)

**Schema:**
```csv
sensor,contribution_pct,rank,value,deviation_z
```

**Columns:**
- `sensor` (string): Sensor name
- `contribution_pct` (float): % contribution to fused score (sums to 100)
- `rank` (int): Contribution rank (1=highest)
- `value` (float): Current sensor value
- `deviation_z` (float): Sensor's z-score deviation

**Example:**
```csv
sensor,contribution_pct,rank,value,deviation_z
DEMO.SIM.FSAB,42.3,1,32.5,3.2
DEMO.SIM.FGAB,28.1,2,48.1,2.1
DEMO.SIM.FJAB,18.5,3,15.2,1.4
```

---

## 5. Contribution Over Time

### `tables/contrib_timeline.csv`

**Purpose:** Sensor contributions over time (stacked area/line chart)

**Schema:**
```csv
timestamp,sensor,contribution_pct,detector
```

**Columns:**
- `timestamp` (datetime): UTC timestamp
- `sensor` (string): Sensor name
- `contribution_pct` (float): % contribution at this timestamp
- `detector` (string): Primary detector (e.g., `mhal_z`, `iforest_z`)

**Example:**
```csv
timestamp,sensor,contribution_pct,detector
2013-01-01 00:00:00+00:00,DEMO.SIM.FSAB,35.2,mhal_z
2013-01-01 00:00:00+00:00,DEMO.SIM.FGAB,25.8,iforest_z
2013-01-01 01:00:00+00:00,DEMO.SIM.FSAB,42.1,mhal_z
```

---

## 6. Anomaly Timeline

### `tables/anomaly_events.csv`

**Purpose:** Discrete anomaly events (episodes) with severity

**Schema:**
```csv
episode_id,start_ts,end_ts,duration_s,severity,sensor,note,regime_id,regime_state
```

**Columns:**
- `episode_id` (int): Unique episode ID
- `start_ts` (datetime): Episode start timestamp
- `end_ts` (datetime): Episode end timestamp
- `duration_s` (float): Duration in seconds
- `severity` (string): `low` | `medium` | `high` | `critical`
- `sensor` (string): Primary culprit sensor
- `note` (string): Descriptive text (e.g., "High residual error")
- `regime_id` (int): Regime during episode
- `regime_state` (string): Regime state

**Example:**
```csv
episode_id,start_ts,end_ts,duration_s,severity,sensor,note,regime_id,regime_state
1,2013-01-05 10:00:00+00:00,2013-01-05 12:30:00+00:00,9000.0,medium,DEMO.SIM.FSAB,Sustained elevation,2,healthy
```

---

## 7. Seasonality Overlay

### `tables/seasonality_hour.csv`

**Purpose:** Typical sensor behavior by hour-of-day (baseline)

**Schema:**
```csv
hour,sensor,mean,lo,hi
```

**Columns:**
- `hour` (int): Hour of day (0-23)
- `sensor` (string): Sensor name
- `mean` (float): Typical mean value for this hour
- `lo` (float): Lower bound (P10 or μ-σ)
- `hi` (float): Upper bound (P90 or μ+σ)

**Example:**
```csv
hour,sensor,mean,lo,hi
0,DEMO.SIM.FSAB,22.5,20.0,25.0
1,DEMO.SIM.FSAB,23.1,20.5,25.5
2,DEMO.SIM.FSAB,24.0,21.0,27.0
```

---

### `tables/seasonality_today.csv`

**Purpose:** Current sensor values with hour-of-day for comparison

**Schema:**
```csv
timestamp,sensor,value,hour
```

**Columns:**
- `timestamp` (datetime): UTC timestamp
- `sensor` (string): Sensor name
- `value` (float): Actual value
- `hour` (int): Hour of day (0-23)

---

## 8. Drift Indicator

### `tables/drift_series.csv`

**Purpose:** Slow baseline shift detection (CUSUM or EWMA)

**Schema:**
```csv
timestamp,sensor,drift_value,drift_flag
```

**Columns:**
- `timestamp` (datetime): UTC timestamp
- `sensor` (string): Sensor name (or `fused` for composite)
- `drift_value` (float): CUSUM/EWMA statistic
- `drift_flag` (int): 0=stable, 1=drift detected

**Example:**
```csv
timestamp,sensor,drift_value,drift_flag
2013-01-01 00:00:00+00:00,fused,0.12,0
2013-01-01 01:00:00+00:00,fused,0.45,0
2013-01-01 02:00:00+00:00,fused,2.31,1
```

---

## 9. Threshold Crossings Summary

### `tables/threshold_crossings.csv`

**Purpose:** Summary of breaches per sensor

**Schema:**
```csv
sensor,crossings_count,first_breach_ts,last_breach_ts,total_breach_duration_sec,breach_active
```

**Columns:**
- `sensor` (string): Sensor name
- `crossings_count` (int): Total number of threshold breaches
- `first_breach_ts` (datetime): First breach timestamp
- `last_breach_ts` (datetime): Most recent breach timestamp
- `total_breach_duration_sec` (float): Cumulative breach duration
- `breach_active` (int): 0=cleared, 1=active breach

**Example:**
```csv
sensor,crossings_count,first_breach_ts,last_breach_ts,total_breach_duration_sec,breach_active
DEMO.SIM.FSAB,3,2013-01-05 10:00:00+00:00,2013-01-12 15:00:00+00:00,18000.0,0
DEMO.SIM.FGAB,1,2013-01-10 08:00:00+00:00,2013-01-10 09:00:00+00:00,3600.0,0
```

---

## 10. Since-When Status

### `tables/since_when.csv`

**Purpose:** Single-row status table for dashboard tiles

**Schema:**
```csv
first_sustained_breach_ts,breach_active,current_zone,current_health_index,time_in_current_zone_hours
```

**Columns:**
- `first_sustained_breach_ts` (datetime): When current alert started (NULL if healthy)
- `breach_active` (int): 0=healthy, 1=alert active
- `current_zone` (string): `GOOD` | `WATCH` | `ALERT`
- `current_health_index` (float): Current health (0-100)
- `time_in_current_zone_hours` (float): Hours in current zone

**Example:**
```csv
first_sustained_breach_ts,breach_active,current_zone,current_health_index,time_in_current_zone_hours
2013-01-10 08:00:00+00:00,1,ALERT,45.2,12.5
```

---

## 11. Top Sensors Ranked

### `tables/sensor_rank_now.csv`

**Purpose:** Current sensor ranking by deviation (single snapshot)

**Schema:**
```csv
rank,sensor,deviation_score,breached,contribution_pct
```

**Columns:**
- `rank` (int): Rank by deviation (1=worst)
- `sensor` (string): Sensor name
- `deviation_score` (float): Composite deviation metric (z-score or anomaly score)
- `breached` (int): 0=normal, 1=breached
- `contribution_pct` (float): % contribution to fused score

**Example:**
```csv
rank,sensor,deviation_score,breached,contribution_pct
1,DEMO.SIM.FSAB,3.42,1,42.3
2,DEMO.SIM.FGAB,2.18,1,28.1
3,DEMO.SIM.FJAB,1.45,0,18.5
```

---

## 12. Per-Sensor Short Forecast

### `tables/sensor_forecast.csv` (OPTIONAL - requires TODO #20)

**Purpose:** Short-term forecast for top 1-2 driver sensors

**Schema:**
```csv
timestamp,sensor,yhat,yhat_lo,yhat_hi
```

**Columns:**
- `timestamp` (datetime): Future timestamp
- `sensor` (string): Sensor name
- `yhat` (float): Point forecast
- `yhat_lo` (float): Lower confidence bound
- `yhat_hi` (float): Upper confidence bound

---

## 13. Operating Mix (Regime Occupancy)

### `tables/regime_occupancy.csv`

**Purpose:** Time spent in each regime (recent window)

**Schema:**
```csv
window_start,window_end,regime_id,regime_name,pct_time,avg_health_index
```

**Columns:**
- `window_start` (datetime): Window start timestamp
- `window_end` (datetime): Window end timestamp
- `regime_id` (int): Regime label
- `regime_name` (string): Regime name
- `pct_time` (float): % of window in this regime
- `avg_health_index` (float): Average health during this regime

**Example:**
```csv
window_start,window_end,regime_id,regime_name,pct_time,avg_health_index
2013-01-01 00:00:00+00:00,2013-01-31 23:59:59+00:00,2,Normal Operation,85.3,94.2
2013-01-01 00:00:00+00:00,2013-01-31 23:59:59+00:00,1,High Load,12.1,88.5
2013-01-01 00:00:00+00:00,2013-01-31 23:59:59+00:00,0,Idle,2.6,97.8
```

---

## 14. Health Histogram

### `tables/health_hist.csv`

**Purpose:** Distribution of health index (context visualization)

**Schema:**
```csv
bin_left,bin_right,count
```

**Columns:**
- `bin_left` (float): Left edge of bin
- `bin_right` (float): Right edge of bin
- `count` (int): Number of observations in bin

**Example:**
```csv
bin_left,bin_right,count
0.0,10.0,5
10.0,20.0,12
20.0,30.0,48
...
90.0,100.0,2341
```

---

## 15. Alert Age

### `tables/alert_age.csv`

**Purpose:** Time since last clear state per sensor

**Schema:**
```csv
sensor,age_seconds,active,last_clear_ts,current_severity
```

**Columns:**
- `sensor` (string): Sensor name
- `age_seconds` (float): Seconds since last clear (0 if currently clear)
- `active` (int): 0=clear, 1=alert active
- `last_clear_ts` (datetime): Last time sensor was normal (NULL if never breached)
- `current_severity` (string): `low` | `medium` | `high` | `critical` | `none`

**Example:**
```csv
sensor,age_seconds,active,last_clear_ts,current_severity
DEMO.SIM.FSAB,45000.0,1,2013-01-09 10:00:00+00:00,high
DEMO.SIM.FGAB,0.0,0,2013-01-12 15:00:00+00:00,none
DEMO.SIM.FJAB,7200.0,1,2013-01-12 13:00:00+00:00,medium
```

---

## Implementation Plan

### Phase 1: Core Tables (CRITICAL - TODO #5)
1. **Health Timeline** - Derive from fused_z + regime states
2. **Regime Timeline** - Direct from regime labels
3. **Anomaly Events** - Map from episodes.csv
4. **Sensor Norm Bands** - Use calibration P5/P95 bounds
5. **Contribution Now** - Feature importance attribution

### Phase 2: Aggregations (HIGH Priority)
6. **Threshold Crossings** - Aggregate from norm bands breaches
7. **Since When** - Single-row summary from current state
8. **Sensor Rank Now** - Sort by deviation_score
9. **Regime Occupancy** - Group by regime_id, compute % time

### Phase 3: Advanced Analytics (MEDIUM Priority)
10. **Drift Series** - CUSUM from scores.csv
11. **Contribution Timeline** - Temporal attribution
12. **Seasonality Hour** - Hour-of-day statistics from training
13. **Seasonality Today** - Current window with hour labels

### Phase 4: Forecasting (FUTURE - TODO #20)
14. **Health Forecast** - ARIMA/Prophet on health_index
15. **Sensor Forecast** - Per-sensor forecasts

---

## SQL Migration Notes

When transitioning to SQL:
1. Each table becomes a SQL table with schema matching CSV columns
2. Add `RunID` (BIGINT) and `EquipID` (INT) to all tables
3. Create indexes on `timestamp`, `sensor`, `regime_id`
4. Use TVPs for bulk inserts (core/data_io.py patterns)
5. Create views for dashboard queries (e.g., `vw_latest_health_timeline`)

---

**Status:** Specification complete. Ready for implementation in `report/analytics.py`.

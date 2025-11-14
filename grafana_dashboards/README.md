# ACM Grafana Dashboards

This folder contains production-ready Grafana dashboards for visualizing ACM (Autonomous Condition Monitoring) analytics and asset health data stored in SQL Server.

## Overview

The ACM system generates comprehensive condition monitoring data across ~30 SQL tables covering:
- **Health metrics**: Overall equipment health index, zones (GOOD/WATCH/ALERT)
- **Episodes**: Anomaly detection events with duration and severity
- **Sensor analysis**: Detector/head contributions, hotspots, and anomaly rates
- **Regimes**: Operating mode detection and transitions
- **Drift detection**: Baseline shift identification
- **Calibration**: ML model quality metrics

These dashboards transform this technical data into operator-friendly visualizations that tell a clear story about equipment condition.

## Available Dashboards

### 1. Asset Health Dashboard (`asset_health_dashboard.json`)

**Purpose**: Comprehensive asset condition monitoring dashboard for operations and engineering users.

**Highlights**:
- Executive summary strip (health score, status, days since alert, active episodes, worst sensor, current regime).
- Detailed **Health Index Timeline** and **Operating Regime Timeline**.
- Detector‑based root cause panels: **Current Detector Contributions**, **Sensor Hotspots**, **Sensor Anomaly Rates by Period**.
- Diagnostics: **Detector Correlation**, **Health Zone Distribution by Period**, **Defect Event Timeline**, **Drift Detection**, **Calibration Summary**, **Regime Stability**.

This dashboard is ideal for investigations and engineering analysis.

### 2. ACM Operator View (`acm_operator_dashboard.json`)

**Purpose**: Simplified, run‑scoped view for plant operators that focuses on “Is it healthy?”, “What is wrong?”, and “What should I do?”.

**Highlights**:
- Top strip with health gauge, status badge, days since last alert, episodes, worst sensor.
- Single‑run **Health Index Timeline** aligned with **Operating Regime Timeline**.
- Detector‑centric views: **Current Detector Contributions** and **Detector Contributions Over Time**.
- **Sensor Hotspots** and **Health Zone Distribution by Period** for quick context.
- **Defect Event Timeline** and **Episode Metrics** for event history.
- **Detector Explanations** table that joins detector families to human‑readable explanations using `ACM_DetectorMetadata`.

This dashboard is safe to reuse across assets; it relies only on generic ACM tables and the `EquipID` parameter.

## Prerequisites

- SQL Server database with ACM analytics tables created (see `scripts/sql/create_acm_analytics_tables.sql`).
- Detector metadata table created and seeded (see `scripts/sql/56_create_detector_metadata.sql`).
- ACM pipeline configured to write outputs to SQL (see `core/output_manager.py`).
- Grafana with MSSQL data source configured.

## Importing Dashboards

1. In Grafana, go to **Dashboards → Import**.
2. Import `asset_health_dashboard.json` and/or `acm_operator_dashboard.json` from this folder.
3. Select the appropriate SQL Server data source for `$datasource`.
4. Save the dashboards under a folder (e.g., `ACM Dashboards`).

## Key SQL Tables Used

Both dashboards primarily query the following tables:

- `ACM_HealthTimeline` – Time‑series health index (and fused z‑score).
- `ACM_RegimeTimeline` – Operating regime labels over time.
- `ACM_ContributionCurrent` – Current detector/head contribution summary.
- `ACM_ContributionTimeline` – Detector contribution time‑series.
- `ACM_SensorHotspots` – Ranked sensor deviation metrics.
- `ACM_DetectorCorrelation` – Detector correlation matrix.
- `ACM_HealthZoneByPeriod` – Periodic health zone distribution.
- `ACM_DefectTimeline` – Zone transitions and defect events.
- `ACM_EpisodeMetrics` – Episode statistics summary.
- `ACM_RegimeOccupancy` – Regime occupancy percentages.
- `ACM_DriftSeries` – Drift detection metrics over time.
- `ACM_SensorAnomalyByPeriod` – Sensor anomaly rate aggregation.
- `ACM_CalibrationSummary` – Detector calibration metrics.
- `ACM_RegimeStability` – Regime stability KPIs.
- `ACM_SensorDefects` – Per‑detector defect and severity metrics.
- `ACM_DetectorMetadata` – Detector family explanations and operator hints.

Refer to `docs/SQL_QUERIES_REFERENCE.md` for the exact queries used by each panel in both dashboards.


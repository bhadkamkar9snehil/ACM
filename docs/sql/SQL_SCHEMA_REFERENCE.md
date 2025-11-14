# ACM SQL Schema Reference
_Generated automatically on 2025-11-14 18:26:23_

This document is produced by `python scripts/sql/export_schema_doc.py` and reflects the live structure
of the `ACM` database. Re-run the script whenever tables change.

| Table | Column Count | Primary Key |
| --- | ---: | --- |
| dbo.ACM_AlertAge | 6 | — |
| dbo.ACM_CalibrationSummary | 10 | — |
| dbo.ACM_ColdstartState | 17 | EquipID, Stage |
| dbo.ACM_Config | 7 | ConfigID |
| dbo.ACM_ContributionCurrent | 5 | — |
| dbo.ACM_ContributionTimeline | 5 | — |
| dbo.ACM_CulpritHistory | 10 | — |
| dbo.ACM_DataQuality | 24 | — |
| dbo.ACM_DefectSummary | 12 | — |
| dbo.ACM_DefectTimeline | 10 | — |
| dbo.ACM_DetectorCorrelation | 5 | — |
| dbo.ACM_DetectorMetadata | 5 | DetectorFamily |
| dbo.ACM_DriftEvents | 2 | — |
| dbo.ACM_DriftSeries | 4 | — |
| dbo.ACM_EpisodeMetrics | 10 | — |
| dbo.ACM_Episodes | 8 | — |
| dbo.ACM_FailureForecast_TS | 7 | RunID, EquipID, Timestamp |
| dbo.ACM_HealthForecast_TS | 9 | RunID, EquipID, Timestamp |
| dbo.ACM_HealthHistogram | 5 | — |
| dbo.ACM_HealthTimeline | 6 | — |
| dbo.ACM_HealthZoneByPeriod | 9 | — |
| dbo.ACM_MaintenanceRecommendation | 8 | RunID, EquipID |
| dbo.ACM_RegimeDwellStats | 8 | — |
| dbo.ACM_RegimeOccupancy | 5 | — |
| dbo.ACM_RegimeStability | 4 | — |
| dbo.ACM_RegimeTimeline | 5 | — |
| dbo.ACM_RegimeTransitions | 6 | — |
| dbo.ACM_RUL_Attribution | 9 | RunID, EquipID, FailureTime, SensorName |
| dbo.ACM_RUL_Summary | 9 | RunID, EquipID |
| dbo.ACM_RUL_TS | 9 | RunID, EquipID, Timestamp |
| dbo.ACM_Runs | 19 | RunID |
| dbo.ACM_Scores_Wide | 15 | — |
| dbo.ACM_SensorAnomalyByPeriod | 11 | — |
| dbo.ACM_SensorDefects | 11 | — |
| dbo.ACM_SensorForecast_TS | 10 | RunID, EquipID, SensorName, Timestamp |
| dbo.ACM_SensorHotspots | 15 | — |
| dbo.ACM_SensorHotspotTimeline | 9 | — |
| dbo.ACM_SensorRanking | 6 | — |
| dbo.ACM_SinceWhen | 6 | — |
| dbo.ACM_TagEquipmentMap | 10 | TagID |
| dbo.ACM_ThresholdCrossings | 7 | — |
| dbo.Equipment | 8 | EquipID |
| dbo.FD_FAN_Data | 11 | EntryDateTime |
| dbo.GAS_TURBINE_Data | 18 | EntryDateTime |
| dbo.ModelRegistry | 8 | ModelType, EquipID, Version |
| dbo.Runs | 14 | RunID |

## dbo.ACM_AlertAge
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| AlertZone | nvarchar | NO | 50 | — |
| StartTimestamp | datetime2 | NO | — | — |
| DurationHours | float | NO | 53 | — |
| RecordCount | int | NO | 10 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_CalibrationSummary
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| DetectorType | nvarchar | NO | 50 | — |
| MeanZ | float | NO | 53 | — |
| StdZ | float | NO | 53 | — |
| P95Z | float | NO | 53 | — |
| P99Z | float | NO | 53 | — |
| ClipZ | float | NO | 53 | — |
| SaturationPct | float | NO | 53 | — |
| MahalCondNum | float | YES | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_ColdstartState
- **Primary Key:** EquipID, Stage

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EquipID | int | NO | 10 | — |
| Stage | varchar | NO | 20 | ('score') |
| Status | varchar | NO | 20 | — |
| AttemptCount | int | NO | 10 | ((0)) |
| FirstAttemptAt | datetime2 | NO | — | (getutcdate()) |
| LastAttemptAt | datetime2 | NO | — | (getutcdate()) |
| CompletedAt | datetime2 | YES | — | — |
| AccumulatedRows | int | NO | 10 | ((0)) |
| RequiredRows | int | NO | 10 | ((500)) |
| DataStartTime | datetime2 | YES | — | — |
| DataEndTime | datetime2 | YES | — | — |
| TickMinutes | int | NO | 10 | — |
| ColdstartSplitRatio | float | NO | 53 | ((0.6)) |
| LastError | nvarchar | YES | 2000 | — |
| ErrorCount | int | NO | 10 | ((0)) |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |
| UpdatedAt | datetime2 | NO | — | (getutcdate()) |

## dbo.ACM_Config
- **Primary Key:** ConfigID

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ConfigID | int | NO | 10 | — |
| EquipID | int | NO | 10 | — |
| ParamPath | nvarchar | NO | 500 | — |
| ParamValue | nvarchar | NO | -1 | — |
| ValueType | varchar | NO | 50 | — |
| UpdatedAt | datetime2 | NO | — | (getutcdate()) |
| UpdatedBy | nvarchar | YES | 100 | (suser_sname()) |

## dbo.ACM_ContributionCurrent
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| DetectorType | nvarchar | NO | 50 | — |
| ContributionPct | float | NO | 53 | — |
| ZScore | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_ContributionTimeline
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Timestamp | datetime2 | NO | — | — |
| DetectorType | nvarchar | NO | 50 | — |
| ContributionPct | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_CulpritHistory
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| StartTimestamp | datetime2 | NO | — | — |
| EndTimestamp | datetime2 | NO | — | — |
| DurationHours | float | NO | 53 | — |
| PrimaryDetector | nvarchar | NO | 50 | — |
| WeightedContribution | float | YES | 53 | — |
| LeadMeanZ | float | YES | 53 | — |
| DuringMeanZ | float | YES | 53 | — |
| LagMeanZ | float | YES | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_DataQuality
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| sensor | nvarchar | NO | 255 | — |
| train_count | int | YES | 10 | — |
| train_nulls | int | YES | 10 | — |
| train_null_pct | float | YES | 53 | — |
| train_std | float | YES | 53 | — |
| train_longest_gap | int | YES | 10 | — |
| train_flatline_span | int | YES | 10 | — |
| train_min_ts | datetime2 | YES | — | — |
| train_max_ts | datetime2 | YES | — | — |
| score_count | int | YES | 10 | — |
| score_nulls | int | YES | 10 | — |
| score_null_pct | float | YES | 53 | — |
| score_std | float | YES | 53 | — |
| score_longest_gap | int | YES | 10 | — |
| score_flatline_span | int | YES | 10 | — |
| score_min_ts | datetime2 | YES | — | — |
| score_max_ts | datetime2 | YES | — | — |
| interp_method | nvarchar | YES | 50 | — |
| sampling_secs | float | YES | 53 | — |
| notes | nvarchar | YES | -1 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| CheckName | nvarchar | NO | 100 | — |
| CheckResult | nvarchar | NO | 50 | — |

## dbo.ACM_DefectSummary
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Status | nvarchar | NO | 50 | — |
| Severity | nvarchar | NO | 50 | — |
| CurrentHealth | float | NO | 53 | — |
| AvgHealth | float | NO | 53 | — |
| MinHealth | float | NO | 53 | — |
| EpisodeCount | int | NO | 10 | — |
| WorstSensor | nvarchar | YES | 255 | — |
| GoodCount | int | NO | 10 | — |
| WatchCount | int | NO | 10 | — |
| AlertCount | int | NO | 10 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_DefectTimeline
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Timestamp | datetime2 | NO | — | — |
| EventType | nvarchar | NO | 50 | — |
| FromZone | nvarchar | YES | 50 | — |
| ToZone | nvarchar | YES | 50 | — |
| HealthZone | nvarchar | NO | 50 | — |
| HealthAtEvent | float | NO | 53 | — |
| HealthIndex | float | NO | 53 | — |
| FusedZ | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_DetectorCorrelation
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| DetectorA | nvarchar | NO | 50 | — |
| DetectorB | nvarchar | NO | 50 | — |
| PearsonR | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_DetectorMetadata
- **Primary Key:** DetectorFamily

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| DetectorFamily | nvarchar | NO | 50 | — |
| ShortName | nvarchar | NO | 50 | — |
| Explanation | nvarchar | NO | 400 | — |
| OperatorHint | nvarchar | YES | 400 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

## dbo.ACM_DriftEvents
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_DriftSeries
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Timestamp | datetime2 | NO | — | — |
| DriftValue | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_EpisodeMetrics
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| TotalEpisodes | int | NO | 10 | — |
| TotalDurationHours | float | NO | 53 | — |
| AvgDurationHours | float | NO | 53 | — |
| MedianDurationHours | float | NO | 53 | — |
| MaxDurationHours | float | NO | 53 | — |
| MinDurationHours | float | NO | 53 | — |
| RatePerDay | float | NO | 53 | — |
| MeanInterarrivalHours | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_Episodes
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| EpisodeCount | int | YES | 10 | — |
| MedianDurationMinutes | float | YES | 53 | — |
| CoveragePct | float | YES | 53 | — |
| TimeInAlertPct | float | YES | 53 | — |
| MaxFusedZ | float | YES | 53 | — |
| AvgFusedZ | float | YES | 53 | — |

## dbo.ACM_FailureForecast_TS
- **Primary Key:** RunID, EquipID, Timestamp

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| Timestamp | datetime2 | NO | — | — |
| FailureProb | float | NO | 53 | — |
| ThresholdUsed | float | NO | 53 | — |
| Method | nvarchar | NO | 50 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

## dbo.ACM_HealthForecast_TS
- **Primary Key:** RunID, EquipID, Timestamp

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| Timestamp | datetime2 | NO | — | — |
| ForecastHealth | float | YES | 53 | — |
| CiLower | float | YES | 53 | — |
| CiUpper | float | YES | 53 | — |
| ForecastStd | float | YES | 53 | — |
| Method | nvarchar | NO | 50 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

## dbo.ACM_HealthHistogram
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| HealthBin | nvarchar | NO | 50 | — |
| RecordCount | int | NO | 10 | — |
| Percentage | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_HealthTimeline
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Timestamp | datetime2 | NO | — | — |
| HealthIndex | float | NO | 53 | — |
| HealthZone | nvarchar | NO | 50 | — |
| FusedZ | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_HealthZoneByPeriod
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| PeriodStart | datetime2 | NO | — | — |
| PeriodType | nvarchar | NO | 20 | — |
| HealthZone | nvarchar | NO | 50 | — |
| ZonePct | float | NO | 53 | — |
| ZoneCount | int | NO | 10 | — |
| TotalPoints | int | NO | 10 | — |
| Date | date | NO | — | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_MaintenanceRecommendation
- **Primary Key:** RunID, EquipID

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| EarliestMaintenance | datetime2 | NO | — | — |
| PreferredWindowStart | datetime2 | NO | — | — |
| PreferredWindowEnd | datetime2 | NO | — | — |
| FailureProbAtWindowEnd | float | NO | 53 | — |
| Comment | nvarchar | YES | 400 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

## dbo.ACM_RegimeDwellStats
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RegimeLabel | nvarchar | NO | 50 | — |
| Runs | int | NO | 10 | — |
| MeanSeconds | float | NO | 53 | — |
| MedianSeconds | float | NO | 53 | — |
| MinSeconds | float | NO | 53 | — |
| MaxSeconds | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_RegimeOccupancy
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RegimeLabel | nvarchar | NO | 50 | — |
| RecordCount | int | NO | 10 | — |
| Percentage | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_RegimeStability
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| MetricName | nvarchar | NO | 100 | — |
| MetricValue | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_RegimeTimeline
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Timestamp | datetime2 | NO | — | — |
| RegimeLabel | nvarchar | NO | 50 | — |
| RegimeState | nvarchar | NO | 50 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_RegimeTransitions
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| FromLabel | nvarchar | NO | 50 | — |
| ToLabel | nvarchar | NO | 50 | — |
| Count | int | NO | 10 | — |
| Prob | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_RUL_Attribution
- **Primary Key:** RunID, EquipID, FailureTime, SensorName

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| FailureTime | datetime2 | NO | — | — |
| SensorName | nvarchar | NO | 255 | — |
| FailureContribution | float | NO | 53 | — |
| ZScoreAtFailure | float | YES | 53 | — |
| AlertCount | int | YES | 10 | — |
| Comment | nvarchar | YES | 400 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

## dbo.ACM_RUL_Summary
- **Primary Key:** RunID, EquipID

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| RUL_Hours | float | NO | 53 | — |
| LowerBound | float | YES | 53 | — |
| UpperBound | float | YES | 53 | — |
| Confidence | float | YES | 53 | — |
| Method | nvarchar | NO | 50 | — |
| LastUpdate | datetime2 | NO | — | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

## dbo.ACM_RUL_TS
- **Primary Key:** RunID, EquipID, Timestamp

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| Timestamp | datetime2 | NO | — | — |
| RUL_Hours | float | NO | 53 | — |
| LowerBound | float | YES | 53 | — |
| UpperBound | float | YES | 53 | — |
| Confidence | float | YES | 53 | — |
| Method | nvarchar | NO | 50 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

## dbo.ACM_Runs
- **Primary Key:** RunID

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| EquipName | nvarchar | YES | 200 | — |
| StartedAt | datetime2 | NO | — | — |
| CompletedAt | datetime2 | YES | — | — |
| DurationSeconds | int | YES | 10 | — |
| ConfigSignature | varchar | YES | 64 | — |
| TrainRowCount | int | YES | 10 | — |
| ScoreRowCount | int | YES | 10 | — |
| EpisodeCount | int | YES | 10 | — |
| HealthStatus | varchar | YES | 50 | — |
| AvgHealthIndex | float | YES | 53 | — |
| MinHealthIndex | float | YES | 53 | — |
| MaxFusedZ | float | YES | 53 | — |
| DataQualityScore | float | YES | 53 | — |
| RefitRequested | bit | YES | — | ((0)) |
| ErrorMessage | nvarchar | YES | 1000 | — |
| KeptColumns | nvarchar | YES | -1 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |

## dbo.ACM_Scores_Wide
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Timestamp | datetime2 | NO | — | — |
| ar1_z | float | YES | 53 | — |
| pca_spe_z | float | YES | 53 | — |
| pca_t2_z | float | YES | 53 | — |
| mhal_z | float | YES | 53 | — |
| iforest_z | float | YES | 53 | — |
| gmm_z | float | YES | 53 | — |
| cusum_z | float | YES | 53 | — |
| drift_z | float | YES | 53 | — |
| hst_z | float | YES | 53 | — |
| river_hst_z | float | YES | 53 | — |
| fused | float | YES | 53 | — |
| regime_label | nvarchar | YES | 50 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_SensorAnomalyByPeriod
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Date | date | NO | — | — |
| PeriodStart | datetime2 | NO | — | — |
| PeriodType | nvarchar | NO | 20 | — |
| PeriodSeconds | float | NO | 53 | — |
| DetectorType | nvarchar | NO | 50 | — |
| AnomalyRatePct | float | NO | 53 | — |
| MaxZ | float | NO | 53 | — |
| AvgZ | float | NO | 53 | — |
| Points | int | NO | 10 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_SensorDefects
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| DetectorType | nvarchar | NO | 50 | — |
| DetectorFamily | nvarchar | NO | 50 | — |
| Severity | nvarchar | NO | 50 | — |
| ViolationCount | int | NO | 10 | — |
| ViolationPct | float | NO | 53 | — |
| MaxZ | float | NO | 53 | — |
| AvgZ | float | NO | 53 | — |
| CurrentZ | float | NO | 53 | — |
| ActiveDefect | nvarchar | NO | 10 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_SensorForecast_TS
- **Primary Key:** RunID, EquipID, SensorName, Timestamp

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| SensorName | nvarchar | NO | 255 | — |
| Timestamp | datetime2 | NO | — | — |
| ForecastValue | float | NO | 53 | — |
| CiLower | float | YES | 53 | — |
| CiUpper | float | YES | 53 | — |
| ForecastStd | float | YES | 53 | — |
| Method | nvarchar | NO | 50 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

## dbo.ACM_SensorHotspots
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| SensorName | nvarchar | NO | 255 | — |
| MaxTimestamp | datetime2 | NO | — | — |
| LatestTimestamp | datetime2 | NO | — | — |
| MaxAbsZ | float | NO | 53 | — |
| MaxSignedZ | float | NO | 53 | — |
| LatestAbsZ | float | NO | 53 | — |
| LatestSignedZ | float | NO | 53 | — |
| ValueAtPeak | float | NO | 53 | — |
| LatestValue | float | NO | 53 | — |
| TrainMean | float | NO | 53 | — |
| TrainStd | float | NO | 53 | — |
| AboveWarnCount | int | NO | 10 | — |
| AboveAlertCount | int | NO | 10 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_SensorHotspotTimeline
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Timestamp | datetime2 | NO | — | — |
| SensorName | nvarchar | NO | 255 | — |
| Rank | int | NO | 10 | — |
| AbsZ | float | NO | 53 | — |
| SignedZ | float | NO | 53 | — |
| Value | float | NO | 53 | — |
| Level | nvarchar | NO | 50 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_SensorRanking
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| DetectorType | nvarchar | NO | 50 | — |
| RankPosition | int | NO | 10 | — |
| ContributionPct | float | NO | 53 | — |
| ZScore | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.ACM_SinceWhen
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| AlertZone | nvarchar | NO | 50 | — |
| DurationHours | float | NO | 53 | — |
| StartTimestamp | datetime2 | NO | — | — |
| RecordCount | int | NO | 10 | — |

## dbo.ACM_TagEquipmentMap
- **Primary Key:** TagID

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| TagID | int | NO | 10 | — |
| TagName | varchar | NO | 255 | — |
| EquipmentName | varchar | NO | 50 | — |
| EquipID | int | NO | 10 | — |
| TagDescription | varchar | YES | 500 | — |
| TagUnit | varchar | YES | 50 | — |
| TagType | varchar | YES | 50 | — |
| IsActive | bit | YES | — | ((1)) |
| CreatedAt | datetime2 | YES | — | (getutcdate()) |
| UpdatedAt | datetime2 | YES | — | (getutcdate()) |

## dbo.ACM_ThresholdCrossings
- **Primary Key:** —

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Timestamp | datetime2 | NO | — | — |
| DetectorType | nvarchar | NO | 50 | — |
| Threshold | float | NO | 53 | — |
| ZScore | float | NO | 53 | — |
| Direction | nvarchar | NO | 10 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |

## dbo.Equipment
- **Primary Key:** EquipID

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EquipID | int | NO | 10 | — |
| EquipCode | nvarchar | NO | 100 | — |
| EquipName | nvarchar | YES | 200 | — |
| Area | nvarchar | YES | 100 | — |
| Unit | nvarchar | YES | 100 | — |
| Status | tinyint | YES | 3 | — |
| CommissionDate | datetime2 | YES | — | — |
| CreatedAtUTC | datetime2 | NO | — | (sysutcdatetime()) |

## dbo.FD_FAN_Data
- **Primary Key:** EntryDateTime

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| DEMO.SIM.06G31_1FD Fan Damper Position | float | YES | 53 | — |
| DEMO.SIM.06I03_1FD Fan Motor Current | float | YES | 53 | — |
| DEMO.SIM.06GP34_1FD Fan Outlet Pressure | float | YES | 53 | — |
| DEMO.SIM.06T31_1FD Fan Inlet Temperature | float | YES | 53 | — |
| DEMO.SIM.06T32-1_1FD Fan Bearing Temperature | float | YES | 53 | — |
| DEMO.SIM.06T33-1_1FD Fan Winding Temperature | float | YES | 53 | — |
| DEMO.SIM.06T34_1FD Fan Outlet Termperature | float | YES | 53 | — |
| DEMO.SIM.FSAA_1FD Fan Left Inlet Flow | float | YES | 53 | — |
| DEMO.SIM.FSAB_1FD Fan Right Inlet Flow | float | YES | 53 | — |
| LoadedAt | datetime2 | YES | — | (getutcdate()) |

## dbo.GAS_TURBINE_Data
- **Primary Key:** EntryDateTime

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| DWATT | float | YES | 53 | — |
| B1VIB1 | float | YES | 53 | — |
| B1VIB2 | float | YES | 53 | — |
| B1RADVIBX | float | YES | 53 | — |
| B1RADVIBY | float | YES | 53 | — |
| B2VIB1 | float | YES | 53 | — |
| B2VIB2 | float | YES | 53 | — |
| B2RADVIBX | float | YES | 53 | — |
| B2RADVIBY | float | YES | 53 | — |
| TURBAXDISP1 | float | YES | 53 | — |
| TURBAXDISP2 | float | YES | 53 | — |
| B1TEMP1 | float | YES | 53 | — |
| B2TEMP1 | float | YES | 53 | — |
| ACTTBTEMP1 | float | YES | 53 | — |
| INACTTBTEMP1 | float | YES | 53 | — |
| LOTEMP1 | float | YES | 53 | — |
| LoadedAt | datetime2 | YES | — | (getutcdate()) |

## dbo.ModelRegistry
- **Primary Key:** ModelType, EquipID, Version

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ModelType | varchar | NO | 16 | — |
| EquipID | int | NO | 10 | — |
| Version | int | NO | 10 | — |
| EntryDateTime | datetime2 | NO | — | (sysutcdatetime()) |
| ParamsJSON | nvarchar | YES | -1 | — |
| StatsJSON | nvarchar | YES | -1 | — |
| RunID | uniqueidentifier | YES | — | — |
| ModelBytes | varbinary | YES | -1 | — |

## dbo.Runs
- **Primary Key:** RunID

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | (newid()) |
| EquipID | int | NO | 10 | — |
| Stage | varchar | NO | 10 | — |
| EntryDateTime | datetime2 | NO | — | — |
| EndEntryDateTime | datetime2 | YES | — | — |
| WindowStartEntryDateTime | datetime2 | NO | — | — |
| WindowEndEntryDateTime | datetime2 | NO | — | — |
| Outcome | varchar | NO | 16 | — |
| Version | varchar | YES | 50 | — |
| ConfigHash | varchar | YES | 128 | — |
| TriggerReason | varchar | YES | 64 | — |
| RowsRead | int | YES | 10 | — |
| RowsWritten | int | YES | 10 | — |
| ErrorJSON | nvarchar | YES | -1 | — |
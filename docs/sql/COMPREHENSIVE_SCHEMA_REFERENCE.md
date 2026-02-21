# ACM Comprehensive Database Schema Reference

_Generated automatically on 2026-02-21 12:00:40_

This document provides detailed information about all tables in the ACM database:
- Schema (columns, data types, nullability, defaults)
- Primary keys
- Row counts and date ranges
- Top 10 and bottom 10 records per table

**Generation Command:**
```bash
python scripts/sql/export_comprehensive_schema.py --output docs/sql/COMPREHENSIVE_SCHEMA_REFERENCE.md
```

---

## Table of Contents

- [dbo.ACM_ActiveModels](#dboacmactivemodels)
- [dbo.ACM_AdaptiveConfig](#dboacmadaptiveconfig)
- [dbo.ACM_Anomaly_Events](#dboacmanomalyevents)
- [dbo.ACM_AssetProfiles](#dboacmassetprofiles)
- [dbo.ACM_BaselineBuffer](#dboacmbaselinebuffer)
- [dbo.ACM_CalibrationSummary](#dboacmcalibrationsummary)
- [dbo.ACM_ColdstartState](#dboacmcoldstartstate)
- [dbo.ACM_Config](#dboacmconfig)
- [dbo.ACM_ConfigHistory](#dboacmconfighistory)
- [dbo.ACM_ContributionTimeline](#dboacmcontributiontimeline)
- [dbo.ACM_DataContractValidation](#dboacmdatacontractvalidation)
- [dbo.ACM_DataQuality](#dboacmdataquality)
- [dbo.ACM_DetectorCorrelation](#dboacmdetectorcorrelation)
- [dbo.ACM_DriftController](#dboacmdriftcontroller)
- [dbo.ACM_DriftSeries](#dboacmdriftseries)
- [dbo.ACM_EpisodeCulprits](#dboacmepisodeculprits)
- [dbo.ACM_EpisodeDiagnostics](#dboacmepisodediagnostics)
- [dbo.ACM_Episodes](#dboacmepisodes)
- [dbo.ACM_FailureForecast](#dboacmfailureforecast)
- [dbo.ACM_FeatureDropLog](#dboacmfeaturedroplog)
- [dbo.ACM_ForecastState](#dboacmforecaststate)
- [dbo.ACM_Forecast_QualityMetrics](#dboacmforecastqualitymetrics)
- [dbo.ACM_ForecastingState](#dboacmforecastingstate)
- [dbo.ACM_HealthForecast](#dboacmhealthforecast)
- [dbo.ACM_HealthTimeline](#dboacmhealthtimeline)
- [dbo.ACM_HistorianData](#dboacmhistoriandata)
- [dbo.ACM_MultivariateForecast](#dboacmmultivariateforecast)
- [dbo.ACM_OMR_Diagnostics](#dboacmomrdiagnostics)
- [dbo.ACM_PCA_Loadings](#dboacmpcaloadings)
- [dbo.ACM_PCA_Metrics](#dboacmpcametrics)
- [dbo.ACM_PCA_Models](#dboacmpcamodels)
- [dbo.ACM_RUL](#dboacmrul)
- [dbo.ACM_RefitRequests](#dboacmrefitrequests)
- [dbo.ACM_RegimeDefinitions](#dboacmregimedefinitions)
- [dbo.ACM_RegimeOccupancy](#dboacmregimeoccupancy)
- [dbo.ACM_RegimePromotionLog](#dboacmregimepromotionlog)
- [dbo.ACM_RegimeState](#dboacmregimestate)
- [dbo.ACM_RegimeTimeline](#dboacmregimetimeline)
- [dbo.ACM_RegimeTransitions](#dboacmregimetransitions)
- [dbo.ACM_Regime_Episodes](#dboacmregimeepisodes)
- [dbo.ACM_RunLogs](#dboacmrunlogs)
- [dbo.ACM_RunMetadata](#dboacmrunmetadata)
- [dbo.ACM_RunMetrics](#dboacmrunmetrics)
- [dbo.ACM_Run_Stats](#dboacmrunstats)
- [dbo.ACM_Runs](#dboacmruns)
- [dbo.ACM_SchemaVersion](#dboacmschemaversion)
- [dbo.ACM_Scores_Wide](#dboacmscoreswide)
- [dbo.ACM_SeasonalPatterns](#dboacmseasonalpatterns)
- [dbo.ACM_SensorCorrelations](#dboacmsensorcorrelations)
- [dbo.ACM_SensorDefects](#dboacmsensordefects)
- [dbo.ACM_SensorForecast](#dboacmsensorforecast)
- [dbo.ACM_SensorHotspots](#dboacmsensorhotspots)
- [dbo.ACM_SensorNormalized_TS](#dboacmsensornormalizedts)
- [dbo.ACM_TagEquipmentMap](#dboacmtagequipmentmap)
- [dbo.COND_PUMP_MOTOR_Data](#dbocondpumpmotordata)
- [dbo.ELECTRIC_MOTOR_Data](#dboelectricmotordata)
- [dbo.ELECTRIC_MOTOR_Data_RAW](#dboelectricmotordataraw)
- [dbo.Equipment](#dboequipment)
- [dbo.FD_FAN_Data](#dbofdfandata)
- [dbo.GAS_TURBINE_Data](#dbogasturbinedata)
- [dbo.ModelRegistry](#dbomodelregistry)
- [dbo.WFA_TURBINE_0_Data](#dbowfaturbine0data)
- [dbo.WFA_TURBINE_10_Data](#dbowfaturbine10data)
- [dbo.WFA_TURBINE_11_Data](#dbowfaturbine11data)
- [dbo.WFA_TURBINE_13_Data](#dbowfaturbine13data)
- [dbo.WFA_TURBINE_14_Data](#dbowfaturbine14data)
- [dbo.WFA_TURBINE_17_Data](#dbowfaturbine17data)
- [dbo.WFA_TURBINE_21_Data](#dbowfaturbine21data)
- [dbo.WFA_TURBINE_22_Data](#dbowfaturbine22data)
- [dbo.WFA_TURBINE_24_Data](#dbowfaturbine24data)
- [dbo.WFA_TURBINE_25_Data](#dbowfaturbine25data)
- [dbo.WFA_TURBINE_26_Data](#dbowfaturbine26data)
- [dbo.WFA_TURBINE_38_Data](#dbowfaturbine38data)
- [dbo.WFA_TURBINE_3_Data](#dbowfaturbine3data)
- [dbo.WFA_TURBINE_40_Data](#dbowfaturbine40data)
- [dbo.WFA_TURBINE_42_Data](#dbowfaturbine42data)
- [dbo.WFA_TURBINE_45_Data](#dbowfaturbine45data)
- [dbo.WFA_TURBINE_51_Data](#dbowfaturbine51data)
- [dbo.WFA_TURBINE_68_Data](#dbowfaturbine68data)
- [dbo.WFA_TURBINE_69_Data](#dbowfaturbine69data)
- [dbo.WFA_TURBINE_71_Data](#dbowfaturbine71data)
- [dbo.WFA_TURBINE_72_Data](#dbowfaturbine72data)
- [dbo.WFA_TURBINE_73_Data](#dbowfaturbine73data)
- [dbo.WFA_TURBINE_84_Data](#dbowfaturbine84data)
- [dbo.WFA_TURBINE_92_Data](#dbowfaturbine92data)
- [dbo.WIND_TURBINE_Data](#dbowindturbinedata)


## Summary

| Table | Columns | Rows | Primary Key |
| --- | ---: | ---: | --- |
| dbo.ACM_ActiveModels | 20 | 10 | ID |
| dbo.ACM_AdaptiveConfig | 13 | 15 | ConfigID |
| dbo.ACM_Anomaly_Events | 7 | 0 | Id |
| dbo.ACM_AssetProfiles | 11 | 1 | ID |
| dbo.ACM_BaselineBuffer | 7 | 212,655 | Id |
| dbo.ACM_CalibrationSummary | 10 | 414 | ID |
| dbo.ACM_ColdstartState | 18 | 10 | EquipID, Stage |
| dbo.ACM_Config | 7 | 359 | ConfigID |
| dbo.ACM_ConfigHistory | 9 | 92 | ID |
| dbo.ACM_ContributionTimeline | 7 | 0 | ID |
| dbo.ACM_DataContractValidation | 10 | 73 | ID |
| dbo.ACM_DataQuality | 25 | 165 | — |
| dbo.ACM_DetectorCorrelation | 7 | 1,449 | ID |
| dbo.ACM_DriftController | 10 | 69 | ID |
| dbo.ACM_DriftSeries | 7 | 0 | ID |
| dbo.ACM_EpisodeCulprits | 9 | 21,225 | ID |
| dbo.ACM_EpisodeDiagnostics | 17 | 3,213 | ID |
| dbo.ACM_Episodes | 15 | 3,213 | ID |
| dbo.ACM_FailureForecast | 10 | 104,832 | EquipID, RunID, Timestamp |
| dbo.ACM_FeatureDropLog | 8 | 1,677 | ID |
| dbo.ACM_ForecastState | 13 | 0 | EquipID, StateVersion |
| dbo.ACM_Forecast_QualityMetrics | 15 | 0 | MetricID |
| dbo.ACM_ForecastingState | 13 | 7 | EquipID, StateVersion |
| dbo.ACM_HealthForecast | 11 | 104,832 | EquipID, RunID, Timestamp |
| dbo.ACM_HealthTimeline | 11 | 163,035 | — |
| dbo.ACM_HistorianData | 6 | 0 | ID |
| dbo.ACM_MultivariateForecast | 10 | 28,560 | ID |
| dbo.ACM_OMR_Diagnostics | 15 | 44 | DiagnosticID |
| dbo.ACM_PCA_Loadings | 8 | 142,910 | ID |
| dbo.ACM_PCA_Metrics | 10 | 69 | ID |
| dbo.ACM_PCA_Models | 12 | 68 | ID |
| dbo.ACM_RUL | 33 | 52 | EquipID, RunID |
| dbo.ACM_RefitRequests | 10 | 68 | RequestID |
| dbo.ACM_RegimeDefinitions | 12 | 306 | ID |
| dbo.ACM_RegimeOccupancy | 9 | 314 | ID |
| dbo.ACM_RegimePromotionLog | 9 | 2 | ID |
| dbo.ACM_RegimeState | 15 | 10 | EquipID, StateVersion |
| dbo.ACM_RegimeTimeline | 9 | 163,035 | — |
| dbo.ACM_RegimeTransitions | 8 | 974 | ID |
| dbo.ACM_Regime_Episodes | 8 | 0 | ID |
| dbo.ACM_RunLogs | 8 | 0 | ID |
| dbo.ACM_RunMetadata | 11 | 0 | ID |
| dbo.ACM_RunMetrics | 7 | 1,026 | ID |
| dbo.ACM_Run_Stats | 13 | 68 | RecordID |
| dbo.ACM_Runs | 20 | 77 | RunID |
| dbo.ACM_SchemaVersion | 5 | 2 | VersionID |
| dbo.ACM_Scores_Wide | 17 | 163,035 | — |
| dbo.ACM_SeasonalPatterns | 10 | 2,754 | ID |
| dbo.ACM_SensorCorrelations | 8 | 15,637 | ID |
| dbo.ACM_SensorDefects | 12 | 476 | — |
| dbo.ACM_SensorForecast | 12 | 71,400 | RunID, EquipID, Timestamp, SensorName |
| dbo.ACM_SensorHotspots | 21 | 1,225 | — |
| dbo.ACM_SensorNormalized_TS | 8 | 483,412 | ID |
| dbo.ACM_TagEquipmentMap | 10 | 2,001 | TagID |
| dbo.COND_PUMP_MOTOR_Data | 16 | 17,619 | — |
| dbo.ELECTRIC_MOTOR_Data | 14 | 17,477 | — |
| dbo.ELECTRIC_MOTOR_Data_RAW | 14 | 1,048,575 | — |
| dbo.Equipment | 8 | 30 | EquipID |
| dbo.FD_FAN_Data | 11 | 17,499 | EntryDateTime |
| dbo.GAS_TURBINE_Data | 18 | 2,911 | EntryDateTime |
| dbo.ModelRegistry | 8 | 184 | ModelType, EquipID, Version |
| dbo.WFA_TURBINE_0_Data | 87 | 54,986 | EntryDateTime |
| dbo.WFA_TURBINE_10_Data | 87 | 53,592 | EntryDateTime |
| dbo.WFA_TURBINE_11_Data | 87 | 0 | EntryDateTime |
| dbo.WFA_TURBINE_13_Data | 87 | 54,010 | EntryDateTime |
| dbo.WFA_TURBINE_14_Data | 87 | 54,197 | EntryDateTime |
| dbo.WFA_TURBINE_17_Data | 87 | 55,090 | EntryDateTime |
| dbo.WFA_TURBINE_21_Data | 87 | 0 | EntryDateTime |
| dbo.WFA_TURBINE_22_Data | 87 | 53,036 | EntryDateTime |
| dbo.WFA_TURBINE_24_Data | 87 | 55,003 | EntryDateTime |
| dbo.WFA_TURBINE_25_Data | 87 | 54,712 | EntryDateTime |
| dbo.WFA_TURBINE_26_Data | 87 | 53,702 | EntryDateTime |
| dbo.WFA_TURBINE_38_Data | 87 | 54,835 | EntryDateTime |
| dbo.WFA_TURBINE_3_Data | 87 | 55,487 | EntryDateTime |
| dbo.WFA_TURBINE_40_Data | 87 | 56,158 | EntryDateTime |
| dbo.WFA_TURBINE_42_Data | 87 | 53,886 | EntryDateTime |
| dbo.WFA_TURBINE_45_Data | 87 | 53,739 | EntryDateTime |
| dbo.WFA_TURBINE_51_Data | 87 | 54,436 | EntryDateTime |
| dbo.WFA_TURBINE_68_Data | 87 | 54,358 | EntryDateTime |
| dbo.WFA_TURBINE_69_Data | 87 | 54,813 | EntryDateTime |
| dbo.WFA_TURBINE_71_Data | 87 | 54,744 | EntryDateTime |
| dbo.WFA_TURBINE_72_Data | 87 | 54,082 | EntryDateTime |
| dbo.WFA_TURBINE_73_Data | 87 | 54,042 | EntryDateTime |
| dbo.WFA_TURBINE_84_Data | 87 | 53,772 | EntryDateTime |
| dbo.WFA_TURBINE_92_Data | 87 | 54,067 | EntryDateTime |
| dbo.WIND_TURBINE_Data | 5 | 50,530 | — |

---



## Detailed Table Information



## dbo.ACM_ActiveModels

**Primary Key:** ID  
**Row Count:** 10  
**Date Range:** 2026-02-12 19:22:29 to 2026-02-16 14:18:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| EquipID | int | NO | 10 | — |
| ActiveRegimeVersion | int | YES | 10 | — |
| RegimeMaturityState | nvarchar | YES | 30 | — |
| RegimePromotedAt | datetime2 | YES | — | — |
| ActiveThresholdVersion | int | YES | 10 | — |
| ThresholdPromotedAt | datetime2 | YES | — | — |
| ActiveForecastVersion | int | YES | 10 | — |
| ForecastPromotedAt | datetime2 | YES | — | — |
| LastUpdatedAt | datetime2 | NO | — | (getutcdate()) |
| LastUpdatedBy | nvarchar | YES | 100 | — |
| SilhouetteScore | float | YES | 53 | — |
| StabilityRatio | float | YES | 53 | — |
| TrainingRows | int | NO | 10 | ((0)) |
| TrainingDays | float | NO | 53 | ((0.0)) |
| ConsecutiveRuns | int | NO | 10 | ((0)) |
| TotalRuns | int | NO | 10 | ((0)) |
| ForecastMAPE | float | YES | 53 | — |
| ForecastRMSE | float | YES | 53 | — |
| CreatedAt | datetime2 | YES | — | — |

### Top 10 Records

| ID | EquipID | ActiveRegimeVersion | RegimeMaturityState | RegimePromotedAt | ActiveThresholdVersion | ThresholdPromotedAt | ActiveForecastVersion | ForecastPromotedAt | LastUpdatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 56 | 8632 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-01-19 16:45:30 |
| 68 | 5013 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-01-19 18:05:44 |
| 77 | 8635 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-01-19 18:52:07 |
| 267 | 5022 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-01-22 09:53:00 |
| 356 | 5014 | 1 | CONVERGED | 2026-02-12 19:22:29 | 1 | NULL | 1 | NULL | 2026-02-12 20:17:52 |
| 516 | 5073 | 1 | CONVERGED | 2026-02-16 14:18:00 | 1 | NULL | 1 | NULL | 2026-02-16 15:42:41 |
| 556 | 1 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-02-19 11:00:49 |
| 557 | 2621 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-02-19 13:51:22 |
| 575 | 5010 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-02-20 18:43:05 |
| 576 | 5000 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-02-20 18:47:10 |

---


## dbo.ACM_AdaptiveConfig

**Primary Key:** ConfigID  
**Row Count:** 15  
**Date Range:** 2025-12-04 10:46:47 to 2026-01-01 12:04:51  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ConfigID | int | NO | 10 | — |
| EquipID | int | YES | 10 | — |
| ConfigKey | nvarchar | NO | 100 | — |
| ConfigValue | float | NO | 53 | — |
| MinBound | float | NO | 53 | — |
| MaxBound | float | NO | 53 | — |
| IsLearned | bit | NO | — | ((0)) |
| DataVolumeAtTuning | bigint | YES | 19 | — |
| PerformanceMetric | float | YES | 53 | — |
| ResearchReference | nvarchar | YES | 500 | — |
| Source | nvarchar | NO | 50 | — |
| CreatedAt | datetime2 | NO | — | (getdate()) |
| UpdatedAt | datetime2 | NO | — | (getdate()) |

### Top 10 Records

| ConfigID | EquipID | ConfigKey | ConfigValue | MinBound | MaxBound | IsLearned | DataVolumeAtTuning | PerformanceMetric | ResearchReference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | NULL | alpha | 0.3 | 0.05 | 0.95 | False | NULL | NULL | Hyndman & Athanasopoulos (2018) - Exponential smoothing level |
| 2 | NULL | beta | 0.1 | 0.01 | 0.3 | False | NULL | NULL | Hyndman & Athanasopoulos (2018) - Exponential smoothing trend |
| 3 | NULL | training_window_hours | 168.0 | 72.0 | 720.0 | False | NULL | NULL | NIST SP 1225 - 3-30 day training window |
| 4 | NULL | failure_threshold | 70.0 | 40.0 | 80.0 | False | NULL | NULL | ISO 13381-1:2015 - Health index threshold |
| 5 | NULL | confidence_min | 0.8 | 0.5 | 0.95 | False | NULL | NULL | Agresti & Coull (1998) - Statistical confidence |
| 6 | NULL | max_forecast_hours | 168.0 | 168.0 | 720.0 | False | NULL | NULL | Industry standard - 7-30 day horizon |
| 7 | NULL | monte_carlo_simulations | 1000.0 | 500.0 | 5000.0 | False | NULL | NULL | Saxena et al. (2008) - RUL simulation count |
| 8 | NULL | blend_tau_hours | 12.0 | 6.0 | 48.0 | False | NULL | NULL | Expert tuning - Warm-start alpha blending |
| 9 | NULL | auto_tune_data_threshold | 10000.0 | 5000.0 | 50000.0 | False | NULL | NULL | Expert tuning - Auto-tuning trigger |
| 18 | 5003 | fused_alert_z | 1.4688166379928589 | 0.0 | 999999.0 | True | 129 | 0.0 | quantile_0.997: Auto-calculated from 129 accumulated samples |

### Bottom 10 Records

| ConfigID | EquipID | ConfigKey | ConfigValue | MinBound | MaxBound | IsLearned | DataVolumeAtTuning | PerformanceMetric | ResearchReference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 85 | 5040 | fused_warn_z | 1.5 | 0.0 | 999999.0 | True | 49 | 0.0 | quantile_0.997: Auto-calculated warning threshold (50% of alert) |
| 84 | 5040 | fused_alert_z | 3.0 | 0.0 | 999999.0 | True | 49 | 0.0 | quantile_0.997: Auto-calculated from 49 accumulated samples |
| 55 | 5092 | fused_warn_z | 0.5271811485290527 | 0.0 | 999999.0 | True | 2717 | 0.0 | quantile_0.997: Auto-calculated warning threshold (50% of alert) |
| 54 | 5092 | fused_alert_z | 1.0543622970581055 | 0.0 | 999999.0 | True | 2717 | 0.0 | quantile_0.997: Auto-calculated from 2717 accumulated samples |
| 19 | 5003 | fused_warn_z | 0.7344083189964294 | 0.0 | 999999.0 | True | 129 | 0.0 | quantile_0.997: Auto-calculated warning threshold (50% of alert) |
| 18 | 5003 | fused_alert_z | 1.4688166379928589 | 0.0 | 999999.0 | True | 129 | 0.0 | quantile_0.997: Auto-calculated from 129 accumulated samples |
| 9 | NULL | auto_tune_data_threshold | 10000.0 | 5000.0 | 50000.0 | False | NULL | NULL | Expert tuning - Auto-tuning trigger |
| 8 | NULL | blend_tau_hours | 12.0 | 6.0 | 48.0 | False | NULL | NULL | Expert tuning - Warm-start alpha blending |
| 7 | NULL | monte_carlo_simulations | 1000.0 | 500.0 | 5000.0 | False | NULL | NULL | Saxena et al. (2008) - RUL simulation count |
| 6 | NULL | max_forecast_hours | 168.0 | 168.0 | 720.0 | False | NULL | NULL | Industry standard - 7-30 day horizon |

---


## dbo.ACM_Anomaly_Events

**Primary Key:** Id  
**Row Count:** 0  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Id | bigint | NO | 19 | — |
| RunID | uniqueidentifier | YES | — | — |
| EquipID | int | YES | 10 | — |
| StartTime | datetime2 | YES | — | — |
| EndTime | datetime2 | YES | — | — |
| Severity | nvarchar | YES | 32 | — |
| Confidence | float | YES | 53 | — |

---


## dbo.ACM_AssetProfiles

**Primary Key:** ID  
**Row Count:** 1  
**Date Range:** 2026-01-02 22:43:05 to 2026-01-02 22:43:05  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| EquipID | int | NO | 10 | — |
| EquipType | nvarchar | NO | 100 | — |
| SensorNamesJSON | nvarchar | NO | -1 | — |
| SensorMeansJSON | nvarchar | NO | -1 | — |
| SensorStdsJSON | nvarchar | NO | -1 | — |
| RegimeCount | int | YES | 10 | — |
| TypicalHealth | float | YES | 53 | — |
| DataHours | float | YES | 53 | — |
| LastUpdatedAt | datetime2 | NO | — | (getutcdate()) |
| RunID | nvarchar | YES | 50 | — |

### Top 10 Records

| ID | EquipID | EquipType | SensorNamesJSON | SensorMeansJSON | SensorStdsJSON | RegimeCount | TypicalHealth | DataHours | LastUpdatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 5010 | WFA_TURBINE_10 | ["power_29_avg", "power_29_max", "power_29_min", "power_29_std", "power_30_avg", "power_30_max", ... | {"power_29_avg": 0.27795690212598545, "power_29_max": 0.4237643052903167, "power_29_min": 0.04104... | {"power_29_avg": 0.35138767809240373, "power_29_max": 0.39163233970897193, "power_29_min": 0.0886... | 1 | 85.0 | 539.3333333333334 | 2026-01-02 22:43:05 |

---


## dbo.ACM_BaselineBuffer

**Primary Key:** Id  
**Row Count:** 212,655  
**Date Range:** 2022-11-02 19:10:00 to 2025-09-14 23:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Id | int | NO | 10 | — |
| EquipID | int | NO | 10 | — |
| Timestamp | datetime | NO | — | — |
| SensorName | nvarchar | NO | 128 | — |
| SensorValue | float | NO | 53 | — |
| DataQuality | nvarchar | YES | 64 | — |
| CreatedAt | datetime | NO | — | (getdate()) |

### Top 10 Records

| Id | EquipID | Timestamp | SensorName | SensorValue | DataQuality | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- |
| 3239310 | 5014 | 2023-03-08 04:50:00 | power_29_avg | 0.0373186424353477 | NULL | 2026-02-12 20:20:29 |
| 3239311 | 5014 | 2023-03-08 05:00:00 | power_29_avg | 0.030514543158860884 | NULL | 2026-02-12 20:20:29 |
| 3239312 | 5014 | 2023-03-08 05:10:00 | power_29_avg | 0.03375270481218061 | NULL | 2026-02-12 20:20:29 |
| 3239313 | 5014 | 2023-03-08 05:20:00 | power_29_avg | 0.03843881139541634 | NULL | 2026-02-12 20:20:29 |
| 3239314 | 5014 | 2023-03-08 05:30:00 | power_29_avg | 0.05032013292577808 | NULL | 2026-02-12 20:20:29 |
| 3239315 | 5014 | 2023-03-08 05:40:00 | power_29_avg | 0.05211968890570073 | NULL | 2026-02-12 20:20:29 |
| 3239316 | 5014 | 2023-03-08 05:50:00 | power_29_avg | 0.07978016603569568 | NULL | 2026-02-12 20:20:29 |
| 3239317 | 5014 | 2023-03-08 06:00:00 | power_29_avg | 0.08563466556370258 | NULL | 2026-02-12 20:20:29 |
| 3239318 | 5014 | 2023-03-08 06:10:00 | power_29_avg | 0.09621160354422542 | NULL | 2026-02-12 20:20:29 |
| 3239319 | 5014 | 2023-03-08 06:20:00 | power_29_avg | 0.10164934558479782 | NULL | 2026-02-12 20:20:29 |

### Bottom 10 Records

| Id | EquipID | Timestamp | SensorName | SensorValue | DataQuality | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- |
| 6058575 | 2621 | 2024-06-16 01:59:00 | TURBAXDISP2 | -31.45999747468933 | NULL | 2026-02-19 14:08:28 |
| 6058574 | 2621 | 2024-06-16 00:59:00 | TURBAXDISP2 | -28.921371092325963 | NULL | 2026-02-19 14:08:28 |
| 6058573 | 2621 | 2024-06-15 23:59:00 | TURBAXDISP2 | -26.678055324474933 | NULL | 2026-02-19 14:08:28 |
| 6058572 | 2621 | 2024-06-15 22:59:00 | TURBAXDISP2 | -23.831995476279783 | NULL | 2026-02-19 14:08:28 |
| 6058571 | 2621 | 2024-06-15 21:59:00 | TURBAXDISP2 | -20.523790305205587 | NULL | 2026-02-19 14:08:28 |
| 6058570 | 2621 | 2024-06-15 20:59:00 | TURBAXDISP2 | 13.499795097126004 | NULL | 2026-02-19 14:08:28 |
| 6058569 | 2621 | 2024-06-15 19:59:00 | TURBAXDISP2 | 16.076105661343256 | NULL | 2026-02-19 14:08:28 |
| 6058568 | 2621 | 2024-06-15 18:59:00 | TURBAXDISP2 | 17.805125208663554 | NULL | 2026-02-19 14:08:28 |
| 6058567 | 2621 | 2024-06-15 17:59:00 | TURBAXDISP2 | 18.96011387724741 | NULL | 2026-02-19 14:08:28 |
| 6058566 | 2621 | 2024-06-15 16:59:00 | TURBAXDISP2 | 19.309059866209772 | NULL | 2026-02-19 14:08:28 |

---


## dbo.ACM_CalibrationSummary

**Primary Key:** ID  
**Row Count:** 414  
**Date Range:** 2026-01-19 10:49:14 to 2026-02-20 13:38:38  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | YES | — | — |
| EquipID | int | NO | 10 | — |
| DetectorType | nvarchar | NO | 50 | — |
| CalibrationScore | float | YES | 53 | — |
| TrainR2 | float | YES | 53 | — |
| MeanAbsError | float | YES | 53 | — |
| P95Error | float | YES | 53 | — |
| DatapointsUsed | int | YES | 10 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |

### Top 10 Records

| ID | RunID | EquipID | DetectorType | CalibrationScore | TrainR2 | MeanAbsError | P95Error | DatapointsUsed | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 211 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | ar1_z | 20.0 | NULL | NULL | NULL | NULL | 2026-01-19 10:49:14 |
| 212 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | pca_spe_z | -20.0 | NULL | NULL | NULL | NULL | 2026-01-19 10:49:14 |
| 213 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | pca_t2_z | 20.0 | NULL | NULL | NULL | NULL | 2026-01-19 10:49:14 |
| 214 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | iforest_z | 6.287645903658517 | NULL | NULL | NULL | NULL | 2026-01-19 10:49:14 |
| 215 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | gmm_z | 0.001 | NULL | NULL | NULL | NULL | 2026-01-19 10:49:14 |
| 216 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | omr_z | 5.954904164551856 | NULL | NULL | NULL | NULL | 2026-01-19 10:49:14 |
| 217 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | ar1_z | 20.0 | NULL | NULL | NULL | NULL | 2026-01-19 10:51:47 |
| 218 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | pca_spe_z | -20.0 | NULL | NULL | NULL | NULL | 2026-01-19 10:51:47 |
| 219 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | pca_t2_z | 20.0 | NULL | NULL | NULL | NULL | 2026-01-19 10:51:47 |
| 220 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | iforest_z | 6.287645903658517 | NULL | NULL | NULL | NULL | 2026-01-19 10:51:47 |

### Bottom 10 Records

| ID | RunID | EquipID | DetectorType | CalibrationScore | TrainR2 | MeanAbsError | P95Error | DatapointsUsed | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4044 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | omr_z | 3.6038953306883004 | NULL | NULL | NULL | NULL | 2026-02-20 13:38:38 |
| 4043 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | gmm_z | -0.2608216382157131 | NULL | NULL | NULL | NULL | 2026-02-20 13:38:38 |
| 4042 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | iforest_z | 3.922874731416588 | NULL | NULL | NULL | NULL | 2026-02-20 13:38:38 |
| 4041 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | pca_t2_z | -3.791948396377141 | NULL | NULL | NULL | NULL | 2026-02-20 13:38:38 |
| 4040 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | pca_spe_z | -20.0 | NULL | NULL | NULL | NULL | 2026-02-20 13:38:38 |
| 4039 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | ar1_z | 5.8529895053075345 | NULL | NULL | NULL | NULL | 2026-02-20 13:38:38 |
| 4038 | 0EACE1D8-97FC-4C9B-87CD-D1826B224B15 | 5000 | omr_z | 3.6038953306883004 | NULL | NULL | NULL | NULL | 2026-02-20 13:35:16 |
| 4037 | 0EACE1D8-97FC-4C9B-87CD-D1826B224B15 | 5000 | gmm_z | -0.2608216382157131 | NULL | NULL | NULL | NULL | 2026-02-20 13:35:16 |
| 4036 | 0EACE1D8-97FC-4C9B-87CD-D1826B224B15 | 5000 | iforest_z | 3.922874731416588 | NULL | NULL | NULL | NULL | 2026-02-20 13:35:16 |
| 4035 | 0EACE1D8-97FC-4C9B-87CD-D1826B224B15 | 5000 | pca_t2_z | -3.791948396377141 | NULL | NULL | NULL | NULL | 2026-02-20 13:35:16 |

---


## dbo.ACM_ColdstartState

**Primary Key:** EquipID, Stage  
**Row Count:** 10  
**Date Range:** 2026-01-19 10:47:02 to 2026-02-20 13:12:39  

### Schema

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
| ID | bigint | NO | 19 | — |

### Top 10 Records

| EquipID | Stage | Status | AttemptCount | FirstAttemptAt | LastAttemptAt | CompletedAt | AccumulatedRows | RequiredRows | DataStartTime |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | score | COMPLETE | 1 | 2026-02-19 05:29:41 | 2026-02-19 05:29:42 | 2026-02-19 05:29:42 | 1006 | 500 | 2023-10-15 00:00:00 |
| 2621 | score | COMPLETE | 1 | 2026-02-19 08:19:55 | 2026-02-19 08:19:56 | 2026-02-19 08:19:56 | 589 | 500 | 2023-10-15 00:00:00 |
| 5000 | score | COMPLETE | 1 | 2026-02-20 13:12:39 | 2026-02-20 13:12:46 | 2026-02-20 13:12:46 | 3696 | 500 | 2022-08-04 06:10:00 |
| 5010 | score | COMPLETE | 1 | 2026-02-20 13:06:41 | 2026-02-20 13:06:59 | 2026-02-20 13:06:59 | 10751 | 500 | 2022-10-09 08:40:00 |
| 5013 | score | COMPLETE | 2 | 2026-01-19 12:30:41 | 2026-01-19 12:33:25 | 2026-01-19 12:33:25 | 1202 | 500 | 2022-04-30 13:20:00 |
| 5014 | score | COMPLETE | 1 | 2026-02-12 12:53:39 | 2026-02-12 12:53:48 | 2026-02-12 12:53:48 | 5437 | 500 | 2022-03-03 14:00:00 |
| 5022 | score | COMPLETE | 1 | 2026-01-22 04:12:06 | 2026-01-22 04:12:08 | 2026-01-22 04:12:08 | 601 | 500 | 2022-08-12 09:50:00 |
| 5073 | score | COMPLETE | 1 | 2026-02-16 08:32:39 | 2026-02-16 08:32:47 | 2026-02-16 08:32:47 | 4522 | 500 | 2022-06-07 11:40:00 |
| 8632 | score | COMPLETE | 2 | 2026-01-19 10:47:02 | 2026-01-19 10:50:47 | 2026-01-19 10:50:47 | 1202 | 500 | 2024-01-01 00:00:00 |
| 8635 | score | COMPLETE | 1 | 2026-01-19 12:52:29 | 2026-01-19 12:52:33 | 2026-01-19 12:52:33 | 7799 | 500 | 2018-12-01 00:00:00 |

---


## dbo.ACM_Config

**Primary Key:** ConfigID  
**Row Count:** 359  
**Date Range:** 2025-12-09 12:47:06 to 2026-02-21 06:30:10  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ConfigID | int | NO | 10 | — |
| EquipID | int | NO | 10 | — |
| ParamPath | nvarchar | NO | 500 | — |
| ParamValue | nvarchar | NO | -1 | — |
| ValueType | varchar | NO | 50 | — |
| UpdatedAt | datetime2 | NO | — | (getutcdate()) |
| UpdatedBy | nvarchar | YES | 100 | (suser_sname()) |

### Top 10 Records

| ConfigID | EquipID | ParamPath | ParamValue | ValueType | UpdatedAt | UpdatedBy |
| --- | --- | --- | --- | --- | --- | --- |
| 492 | 0 | data.train_csv | data/FD_FAN_BASELINE_DATA.csv | string | 2026-02-20 13:01:47 | B19cl3pc\bhadk |
| 493 | 0 | data.score_csv | data/FD_FAN_BATCH_DATA.csv | string | 2026-02-20 13:01:47 | B19cl3pc\bhadk |
| 494 | 0 | data.data_dir | data | string | 2026-02-20 13:01:47 | B19cl3pc\bhadk |
| 495 | 0 | data.timestamp_col | EntryDateTime | string | 2026-02-20 13:01:47 | B19cl3pc\bhadk |
| 496 | 0 | data.tag_columns | [] | list | 2026-02-20 13:01:47 | B19cl3pc\bhadk |
| 497 | 0 | data.sampling_secs | auto | string | 2026-02-20 13:01:47 | B19cl3pc\bhadk |
| 498 | 0 | data.max_rows | 100000 | int | 2026-02-20 13:01:47 | B19cl3pc\bhadk |
| 499 | 0 | features.window | 16 | int | 2026-02-20 13:01:47 | B19cl3pc\bhadk |
| 500 | 0 | features.fft_bands | [0.0, 0.1, 0.3, 0.5] | list | 2026-02-20 13:01:47 | B19cl3pc\bhadk |
| 501 | 0 | features.top_k_tags | 5 | int | 2026-02-20 13:01:47 | B19cl3pc\bhadk |

### Bottom 10 Records

| ConfigID | EquipID | ParamPath | ParamValue | ValueType | UpdatedAt | UpdatedBy |
| --- | --- | --- | --- | --- | --- | --- |
| 1229 | 5000 | runtime.tick_minutes | 36960 | int | 2026-02-20 13:12:34 | sql_batch_runner |
| 1228 | 5010 | runtime.tick_minutes | 107712 | int | 2026-02-20 13:06:36 | sql_batch_runner |
| 1227 | 5073 | data.tag_columns | ["sensor_0_avg","sensor_1_avg","sensor_2_avg","wind_speed_3_avg","wind_speed_4_avg","wind_speed_3... | list | 2026-02-20 13:01:48 | B19cl3pc\bhadk |
| 1226 | 5073 | data.sampling_secs | 600 | int | 2026-02-20 13:01:48 | B19cl3pc\bhadk |
| 1225 | 5073 | data.timestamp_col | EntryDateTime | string | 2026-02-20 13:01:48 | B19cl3pc\bhadk |
| 1224 | 5022 | data.tag_columns | ["sensor_0_avg","sensor_1_avg","sensor_2_avg","wind_speed_3_avg","wind_speed_4_avg","wind_speed_3... | list | 2026-02-20 13:01:48 | B19cl3pc\bhadk |
| 1223 | 5022 | data.sampling_secs | 600 | int | 2026-02-20 13:01:48 | B19cl3pc\bhadk |
| 1222 | 5022 | data.timestamp_col | EntryDateTime | string | 2026-02-20 13:01:48 | B19cl3pc\bhadk |
| 1221 | 5014 | data.tag_columns | ["sensor_0_avg","sensor_1_avg","sensor_2_avg","wind_speed_3_avg","wind_speed_4_avg","wind_speed_3... | list | 2026-02-20 13:01:48 | B19cl3pc\bhadk |
| 1220 | 5014 | data.sampling_secs | 600 | int | 2026-02-20 13:01:48 | B19cl3pc\bhadk |

---


## dbo.ACM_ConfigHistory

**Primary Key:** ID  
**Row Count:** 92  
**Date Range:** 2026-01-19 16:19:23 to 2026-02-20 19:08:50  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| Timestamp | datetime2 | NO | — | (sysutcdatetime()) |
| EquipID | int | NO | 10 | — |
| ParameterPath | nvarchar | NO | 256 | — |
| OldValue | nvarchar | YES | -1 | — |
| NewValue | nvarchar | YES | -1 | — |
| ChangedBy | nvarchar | YES | 64 | — |
| ChangeReason | nvarchar | YES | 256 | — |
| RunID | nvarchar | YES | 64 | — |

### Top 10 Records

| ID | Timestamp | EquipID | ParameterPath | OldValue | NewValue | ChangedBy | ChangeReason | RunID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 51 | 2026-01-19 16:19:23 | 8632 | k_sigma | 2.0 | 2.2 | AUTO_TUNE | Auto-tuning based on quality assessment | 248f1325-7537-4843-acfe-e559c458b2a9 |
| 52 | 2026-01-19 16:19:23 | 8632 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 248f1325-7537-4843-acfe-e559c458b2a9 |
| 53 | 2026-01-19 16:21:55 | 8632 | k_sigma | 2.0 | 2.2 | AUTO_TUNE | Auto-tuning based on quality assessment | 173dd810-96e8-4e3f-af4b-7a0b97723d70 |
| 54 | 2026-01-19 16:21:55 | 8632 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 173dd810-96e8-4e3f-af4b-7a0b97723d70 |
| 57 | 2026-01-19 16:24:28 | 8632 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 3bb10529-b16e-4893-826b-73584fec01c8 |
| 58 | 2026-01-19 16:27:38 | 8632 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 496202d1-c512-4d13-93b6-8ad2f15e7c24 |
| 61 | 2026-01-19 16:31:42 | 8632 | k_sigma | 2.0 | 2.2 | AUTO_TUNE | Auto-tuning based on quality assessment | c2cfa54f-fb33-4f66-8340-9a1a0dcec544 |
| 62 | 2026-01-19 16:31:42 | 8632 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | c2cfa54f-fb33-4f66-8340-9a1a0dcec544 |
| 64 | 2026-01-19 16:35:00 | 8632 | k_sigma | 2.0 | 2.2 | AUTO_TUNE | Auto-tuning based on quality assessment | d80354e0-96f4-4a76-9f2a-c73f9c36f66f |
| 65 | 2026-01-19 16:35:00 | 8632 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | d80354e0-96f4-4a76-9f2a-c73f9c36f66f |

### Bottom 10 Records

| ID | Timestamp | EquipID | ParameterPath | OldValue | NewValue | ChangedBy | ChangeReason | RunID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 933 | 2026-02-20 19:08:50 | 5000 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb |
| 932 | 2026-02-20 19:05:28 | 5000 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 0eace1d8-97fc-4c9b-87cd-d1826b224b15 |
| 931 | 2026-02-20 19:04:14 | 5010 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 01ce2248-c8af-4a56-94c5-0ae6e66b28d0 |
| 930 | 2026-02-20 19:01:59 | 5000 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | aff0599e-29d4-4520-8db4-3bd7caf4ab5e |
| 929 | 2026-02-20 18:59:12 | 5010 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 404d97d6-230f-43c6-913f-ec0d799e4bc6 |
| 928 | 2026-02-20 18:58:30 | 5000 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 8d4519cd-86ca-4d65-9cc3-07b3ae05b223 |
| 927 | 2026-02-20 18:55:03 | 5000 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | b9c1087c-33d4-4350-b158-6ed21f66ce31 |
| 926 | 2026-02-20 18:54:06 | 5010 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 9146a69a-7d32-4ceb-a2c6-8ec02a9a0119 |
| 925 | 2026-02-20 18:51:38 | 5000 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | b26fcae5-217f-4fcf-92dc-18ee489a7c8b |
| 924 | 2026-02-20 18:49:09 | 5010 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 6eece164-3196-4815-80a5-15df9a07d39d |

---


## dbo.ACM_ContributionTimeline

**Primary Key:** ID  
**Row Count:** 0  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | nvarchar | NO | 50 | — |
| EquipID | int | NO | 10 | — |
| Timestamp | datetime2 | NO | — | — |
| DetectorType | nvarchar | NO | 50 | — |
| ContributionPct | float | NO | 53 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |

---


## dbo.ACM_DataContractValidation

**Primary Key:** ID  
**Row Count:** 73  
**Date Range:** 2026-01-19 16:17:04 to 2026-02-20 19:10:18  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | nvarchar | NO | 50 | — |
| EquipID | int | NO | 10 | — |
| Passed | bit | NO | — | — |
| RowsValidated | int | NO | 10 | — |
| ColumnsValidated | int | NO | 10 | — |
| IssuesJSON | nvarchar | YES | -1 | — |
| WarningsJSON | nvarchar | YES | -1 | — |
| ContractSignature | nvarchar | YES | 100 | — |
| ValidatedAt | datetime2 | NO | — | (getutcdate()) |

### Top 10 Records

| ID | RunID | EquipID | Passed | RowsValidated | ColumnsValidated | IssuesJSON | WarningsJSON | ContractSignature | ValidatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 69 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | True | 241 | 4 | NULL | NULL | 2e80d3754f96 | 2026-01-19 16:17:04 |
| 72 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | True | 241 | 4 | NULL | NULL | 2e80d3754f96 | 2026-01-19 16:20:48 |
| 73 | 3bb10529-b16e-4893-826b-73584fec01c8 | 8632 | True | 1431 | 4 | NULL | NULL | 6f48bb6392d0 | 2026-01-19 16:23:16 |
| 76 | 496202d1-c512-4d13-93b6-8ad2f15e7c24 | 8632 | True | 1431 | 4 | NULL | NULL | 6f48bb6392d0 | 2026-01-19 16:26:31 |
| 77 | c2cfa54f-fb33-4f66-8340-9a1a0dcec544 | 8632 | True | 1431 | 4 | NULL | NULL | 6f48bb6392d0 | 2026-01-19 16:30:29 |
| 78 | d80354e0-96f4-4a76-9f2a-c73f9c36f66f | 8632 | True | 1431 | 4 | NULL | NULL | 6f48bb6392d0 | 2026-01-19 16:33:45 |
| 81 | 09e1e60f-7f6a-4c79-84cd-a752f45cae94 | 8632 | True | 1431 | 4 | NULL | NULL | 6f48bb6392d0 | 2026-01-19 16:37:29 |
| 82 | c2880e7a-ea1f-47cf-9883-370175810ed0 | 8632 | True | 1431 | 4 | NULL | NULL | 6f48bb6392d0 | 2026-01-19 16:40:50 |
| 84 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | True | 1431 | 4 | NULL | NULL | 6f48bb6392d0 | 2026-01-19 16:44:29 |
| 95 | 1ab0a7d6-007c-458f-a0fb-1592b9c02695 | 5013 | True | 241 | 81 | NULL | NULL | b575e5dcc188 | 2026-01-19 18:00:44 |

### Bottom 10 Records

| ID | RunID | EquipID | Passed | RowsValidated | ColumnsValidated | IssuesJSON | WarningsJSON | ContractSignature | ValidatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10762 | 9a0f444e-c812-45fc-b2a0-74e36cbdb29b | 5000 | True | 3686 | 79 | NULL | NULL | 31ae67006634 | 2026-02-20 19:10:18 |
| 10761 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | True | 3696 | 79 | NULL | NULL | 31ae67006634 | 2026-02-20 19:06:51 |
| 10760 | 0eace1d8-97fc-4c9b-87cd-d1826b224b15 | 5000 | True | 3696 | 79 | NULL | NULL | 31ae67006634 | 2026-02-20 19:03:27 |
| 10759 | 01ce2248-c8af-4a56-94c5-0ae6e66b28d0 | 5010 | True | 10738 | 79 | NULL | NULL | 207b37f7ae5e | 2026-02-20 19:01:20 |
| 10758 | aff0599e-29d4-4520-8db4-3bd7caf4ab5e | 5000 | True | 3696 | 79 | NULL | NULL | 31ae67006634 | 2026-02-20 18:59:59 |
| 10757 | 8d4519cd-86ca-4d65-9cc3-07b3ae05b223 | 5000 | True | 3668 | 79 | NULL | NULL | 31ae67006634 | 2026-02-20 18:56:30 |
| 10756 | 404d97d6-230f-43c6-913f-ec0d799e4bc6 | 5010 | True | 10615 | 79 | NULL | NULL | 207b37f7ae5e | 2026-02-20 18:56:10 |
| 10755 | b9c1087c-33d4-4350-b158-6ed21f66ce31 | 5000 | True | 3663 | 79 | NULL | NULL | 31ae67006634 | 2026-02-20 18:53:01 |
| 10754 | 9146a69a-7d32-4ceb-a2c6-8ec02a9a0119 | 5010 | True | 10765 | 79 | NULL | NULL | 207b37f7ae5e | 2026-02-20 18:51:17 |
| 10753 | b26fcae5-217f-4fcf-92dc-18ee489a7c8b | 5000 | True | 3529 | 79 | NULL | NULL | 31ae67006634 | 2026-02-20 18:49:39 |

---


## dbo.ACM_DataQuality

**Primary Key:** No primary key  
**Row Count:** 165  
**Date Range:** 2022-04-30 13:20:00 to 2023-02-13 19:40:00  

### Schema

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
| ID | bigint | NO | 19 | — |

### Top 10 Records

| sensor | train_count | train_nulls | train_null_pct | train_std | train_longest_gap | train_flatline_span | train_min_ts | train_max_ts | score_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| power_29_avg | 360 | 0 | 0.0 | 0.3859456777572632 | 0 | 2 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_29_max | 360 | 0 | 0.0 | 0.38467156887054443 | 0 | 135 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_29_min | 360 | 0 | 0.0 | 0.31863832473754883 | 0 | 11 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_29_std | 360 | 0 | 0.0 | 0.05088800936937332 | 0 | 2 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_30_avg | 360 | 0 | 0.0 | 0.38848280906677246 | 0 | 1 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_30_max | 360 | 0 | 0.0 | 0.4074581563472748 | 0 | 3 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_30_min | 360 | 0 | 0.0 | 0.3305765986442566 | 0 | 1 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_30_std | 360 | 0 | 0.0 | 0.05145198851823807 | 0 | 2 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| reactive_power_27_avg | 360 | 0 | 0.0 | 0.15000765025615692 | 0 | 9 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| reactive_power_27_max | 360 | 0 | 0.0 | 0.14279618859291077 | 0 | 83 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |

### Bottom 10 Records

| sensor | train_count | train_nulls | train_null_pct | train_std | train_longest_gap | train_flatline_span | train_min_ts | train_max_ts | score_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _SUMMARY_81_SENSORS | 144 | 0 | 0.0 | 0.0 | 2 | 0 | 2022-08-14 09:50:00 | 2022-08-15 09:40:00 | 144 |
| reactive_power_27_min | 360 | 0 | 0.0 | 0.1373654305934906 | 0 | 135 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| reactive_power_27_max | 360 | 0 | 0.0 | 0.14279618859291077 | 0 | 83 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| reactive_power_27_avg | 360 | 0 | 0.0 | 0.15000765025615692 | 0 | 9 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_30_std | 360 | 0 | 0.0 | 0.05145198851823807 | 0 | 2 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_30_min | 360 | 0 | 0.0 | 0.3305765986442566 | 0 | 1 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_30_max | 360 | 0 | 0.0 | 0.4074581563472748 | 0 | 3 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_30_avg | 360 | 0 | 0.0 | 0.38848280906677246 | 0 | 1 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_29_std | 360 | 0 | 0.0 | 0.05088800936937332 | 0 | 2 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |
| power_29_min | 360 | 0 | 0.0 | 0.31863832473754883 | 0 | 11 | 2022-04-30 13:20:00 | 2022-05-03 01:10:00 | 241 |

---


## dbo.ACM_DetectorCorrelation

**Primary Key:** ID  
**Row Count:** 1,449  
**Date Range:** 2026-01-19 10:49:33 to 2026-02-20 13:39:06  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | nvarchar | NO | 50 | — |
| EquipID | int | NO | 10 | — |
| Detector1 | nvarchar | NO | 50 | — |
| Detector2 | nvarchar | NO | 50 | — |
| Correlation | float | NO | 53 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |

### Top 10 Records

| ID | RunID | EquipID | Detector1 | Detector2 | Correlation | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- |
| 1167 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | ar1_z | ar1_z | 1.0 | 2026-01-19 10:49:33 |
| 1168 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | ar1_z | pca_t2_z | 0.7017595194319508 | 2026-01-19 10:49:33 |
| 1169 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | ar1_z | iforest_z | 0.6837614531127288 | 2026-01-19 10:49:33 |
| 1170 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | ar1_z | omr_z | 0.7390021356079014 | 2026-01-19 10:49:33 |
| 1171 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | ar1_z | cusum_z | 0.18211485813911704 | 2026-01-19 10:49:33 |
| 1172 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | pca_t2_z | ar1_z | 0.7017595194319508 | 2026-01-19 10:49:33 |
| 1173 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | pca_t2_z | pca_t2_z | 1.0 | 2026-01-19 10:49:33 |
| 1174 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | pca_t2_z | iforest_z | 0.6809679966270342 | 2026-01-19 10:49:33 |
| 1175 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | pca_t2_z | omr_z | 0.7205900302147022 | 2026-01-19 10:49:33 |
| 1176 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | pca_t2_z | cusum_z | 0.10933954214041454 | 2026-01-19 10:49:33 |

### Bottom 10 Records

| ID | RunID | EquipID | Detector1 | Detector2 | Correlation | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- |
| 17312 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | cusum_z | cusum_z | 1.0 | 2026-02-20 13:39:06 |
| 17311 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | cusum_z | omr_z | 0.11703680722501235 | 2026-02-20 13:39:06 |
| 17310 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | cusum_z | ar1_z | -0.02417149674333299 | 2026-02-20 13:39:06 |
| 17309 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | omr_z | cusum_z | 0.11703680722501235 | 2026-02-20 13:39:06 |
| 17308 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | omr_z | omr_z | 1.0 | 2026-02-20 13:39:06 |
| 17307 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | omr_z | ar1_z | -0.03290041352611893 | 2026-02-20 13:39:06 |
| 17306 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | ar1_z | cusum_z | -0.02417149674333299 | 2026-02-20 13:39:06 |
| 17305 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | ar1_z | omr_z | -0.03290041352611893 | 2026-02-20 13:39:06 |
| 17304 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | ar1_z | ar1_z | 1.0 | 2026-02-20 13:39:06 |
| 17303 | 0eace1d8-97fc-4c9b-87cd-d1826b224b15 | 5000 | cusum_z | cusum_z | 1.0 | 2026-02-20 13:35:41 |

---


## dbo.ACM_DriftController

**Primary Key:** ID  
**Row Count:** 69  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | nvarchar | NO | 50 | — |
| EquipID | int | NO | 10 | — |
| ControllerState | nvarchar | NO | 30 | — |
| Threshold | float | YES | 53 | — |
| Sensitivity | float | YES | 53 | — |
| LastDriftValue | float | YES | 53 | — |
| LastDriftTime | datetime2 | YES | — | — |
| ResetCount | int | YES | 10 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |

### Top 10 Records

| ID | RunID | EquipID | ControllerState | Threshold | Sensitivity | LastDriftValue | LastDriftTime | ResetCount | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | STABLE | 3.0 | 1.0 | NULL | NULL | NULL | 2026-01-19 10:49:24 |
| 32 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | STABLE | 3.0 | 1.0 | NULL | NULL | NULL | 2026-01-19 10:51:56 |
| 35 | 3bb10529-b16e-4893-826b-73584fec01c8 | 8632 | STABLE | 3.0 | 1.0 | NULL | NULL | NULL | 2026-01-19 10:54:29 |
| 36 | 496202d1-c512-4d13-93b6-8ad2f15e7c24 | 8632 | STABLE | 3.0 | 1.0 | NULL | NULL | NULL | 2026-01-19 10:57:39 |
| 38 | c2cfa54f-fb33-4f66-8340-9a1a0dcec544 | 8632 | STABLE | 3.0 | 1.0 | NULL | NULL | NULL | 2026-01-19 11:01:43 |
| 40 | d80354e0-96f4-4a76-9f2a-c73f9c36f66f | 8632 | STABLE | 3.0 | 1.0 | NULL | NULL | NULL | 2026-01-19 11:05:01 |
| 41 | 09e1e60f-7f6a-4c79-84cd-a752f45cae94 | 8632 | STABLE | 3.0 | 1.0 | NULL | NULL | NULL | 2026-01-19 11:08:40 |
| 44 | c2880e7a-ea1f-47cf-9883-370175810ed0 | 8632 | STABLE | 3.0 | 1.0 | NULL | NULL | NULL | 2026-01-19 11:12:05 |
| 45 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | STABLE | 3.0 | 1.0 | NULL | NULL | NULL | 2026-01-19 11:15:51 |
| 54 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a | 8635 | STABLE | 3.0 | 1.0 | NULL | NULL | NULL | 2026-01-19 12:55:40 |

### Bottom 10 Records

| ID | RunID | EquipID | ControllerState | Threshold | Sensitivity | LastDriftValue | LastDriftTime | ResetCount | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 665 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-02-20 13:38:52 |
| 664 | 0eace1d8-97fc-4c9b-87cd-d1826b224b15 | 5000 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-02-20 13:35:30 |
| 663 | 01ce2248-c8af-4a56-94c5-0ae6e66b28d0 | 5010 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-02-20 13:34:17 |
| 662 | aff0599e-29d4-4520-8db4-3bd7caf4ab5e | 5000 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-02-20 13:32:00 |
| 661 | 404d97d6-230f-43c6-913f-ec0d799e4bc6 | 5010 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-02-20 13:29:14 |
| 660 | 8d4519cd-86ca-4d65-9cc3-07b3ae05b223 | 5000 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-02-20 13:28:32 |
| 659 | b9c1087c-33d4-4350-b158-6ed21f66ce31 | 5000 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-02-20 13:25:04 |
| 658 | 9146a69a-7d32-4ceb-a2c6-8ec02a9a0119 | 5010 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-02-20 13:24:08 |
| 657 | b26fcae5-217f-4fcf-92dc-18ee489a7c8b | 5000 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-02-20 13:21:40 |
| 656 | 6eece164-3196-4815-80a5-15df9a07d39d | 5010 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-02-20 13:19:11 |

---


## dbo.ACM_DriftSeries

**Primary Key:** ID  
**Row Count:** 0  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | nvarchar | NO | 50 | — |
| EquipID | int | NO | 10 | — |
| Timestamp | datetime2 | NO | — | — |
| DriftValue | float | NO | 53 | — |
| DriftState | nvarchar | YES | 20 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |

---


## dbo.ACM_EpisodeCulprits

**Primary Key:** ID  
**Row Count:** 21,225  
**Date Range:** 2026-01-19 10:50:09 to 2026-02-20 13:39:45  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | NO | — | — |
| EpisodeID | int | NO | 10 | — |
| DetectorType | nvarchar | YES | 64 | — |
| SensorName | nvarchar | YES | 200 | — |
| ContributionPct | float | YES | 53 | — |
| Rank | int | YES | 10 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |
| EquipID | int | NO | 10 | ((1)) |

### Top 10 Records

| ID | RunID | EpisodeID | DetectorType | SensorName | ContributionPct | Rank | CreatedAt | EquipID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 14853 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 1 | Multivariate Outlier (PCA-T2) | NULL | 55.33710861206055 | 1 | 2026-01-19 10:50:09 | 8632 |
| 14854 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 1 | Baseline Consistency (OMR) | NULL | 15.293468475341797 | 2 | 2026-01-19 10:50:09 | 8632 |
| 14855 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 1 | Time-Series Anomaly (AR1) | NULL | 14.22865104675293 | 3 | 2026-01-19 10:50:09 | 8632 |
| 14856 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 1 | Rare State (IsolationForest) | NULL | 7.650896072387695 | 4 | 2026-01-19 10:50:09 | 8632 |
| 14857 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 1 | cusum_z | NULL | 7.48988151550293 | 5 | 2026-01-19 10:50:09 | 8632 |
| 14858 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 2 | Multivariate Outlier (PCA-T2) | NULL | 68.26260375976562 | 1 | 2026-01-19 10:50:09 | 8632 |
| 14859 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 2 | Time-Series Anomaly (AR1) | NULL | 12.530649185180664 | 2 | 2026-01-19 10:50:09 | 8632 |
| 14860 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 2 | Baseline Consistency (OMR) | NULL | 11.532170295715332 | 3 | 2026-01-19 10:50:09 | 8632 |
| 14861 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 2 | Rare State (IsolationForest) | NULL | 4.738776206970215 | 4 | 2026-01-19 10:50:09 | 8632 |
| 14862 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 2 | cusum_z | NULL | 2.9357926845550537 | 5 | 2026-01-19 10:50:09 | 8632 |

### Bottom 10 Records

| ID | RunID | EpisodeID | DetectorType | SensorName | ContributionPct | Rank | CreatedAt | EquipID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 106073 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 8 | cusum_z | NULL | 6.42793083190918 | 7 | 2026-02-20 13:39:45 | 5000 |
| 106072 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 8 | Density Anomaly (GMM) | NULL | 7.207720756530762 | 6 | 2026-02-20 13:39:45 | 5000 |
| 106071 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 8 | Baseline Consistency (OMR) | NULL | 8.101943969726562 | 5 | 2026-02-20 13:39:45 | 5000 |
| 106070 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 8 | Multivariate Outlier (PCA-T2) | NULL | 11.881040573120117 | 4 | 2026-02-20 13:39:45 | 5000 |
| 106069 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 8 | Time-Series Anomaly (AR1) | NULL | 16.29985237121582 | 3 | 2026-02-20 13:39:45 | 5000 |
| 106068 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 8 | Rare State (IsolationForest) | NULL | 25.04075813293457 | 2 | 2026-02-20 13:39:45 | 5000 |
| 106067 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 8 | Correlation Break (PCA-SPE) | NULL | 25.04075813293457 | 1 | 2026-02-20 13:39:45 | 5000 |
| 106066 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 7 | cusum_z | NULL | 1.9890131950378418 | 7 | 2026-02-20 13:39:45 | 5000 |
| 106065 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 7 | Density Anomaly (GMM) | NULL | 7.0548014640808105 | 6 | 2026-02-20 13:39:45 | 5000 |
| 106064 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 7 | Multivariate Outlier (PCA-T2) | NULL | 11.628971099853516 | 5 | 2026-02-20 13:39:45 | 5000 |

---


## dbo.ACM_EpisodeDiagnostics

**Primary Key:** ID  
**Row Count:** 3,213  
**Date Range:** 2019-03-08 12:00:00 to 2025-09-12 00:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | nvarchar | NO | 50 | — |
| EquipID | int | NO | 10 | — |
| EpisodeID | int | YES | 10 | — |
| StartTime | datetime2 | NO | — | — |
| EndTime | datetime2 | YES | — | — |
| DurationHours | float | YES | 53 | — |
| PeakZ | float | YES | 53 | — |
| AvgZ | float | YES | 53 | — |
| Severity | nvarchar | YES | 20 | — |
| TopSensor1 | nvarchar | YES | 200 | — |
| TopSensor2 | nvarchar | YES | 200 | — |
| TopSensor3 | nvarchar | YES | 200 | — |
| RegimeAtStart | nvarchar | YES | 50 | — |
| AlertMode | nvarchar | YES | 50 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |
| Culprits | nvarchar | YES | 512 | — |

### Top 10 Records

| ID | RunID | EquipID | EpisodeID | StartTime | EndTime | DurationHours | PeakZ | AvgZ | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2654 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | 1 | 2024-01-03 16:00:00 | 2024-01-03 19:10:00 | 3.1666666666666665 | 4.003376867351939 | 2.210012267334677 | HIGH |
| 2655 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | 2 | 2024-01-04 09:30:00 | 2024-01-04 11:10:00 | 1.6666666666666667 | 3.6685015649190733 | 1.5168384331813252 | MEDIUM |
| 2656 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | 3 | 2024-01-04 15:30:00 | 2024-01-05 02:20:00 | 10.833333333333334 | 6.3449162606992315 | 2.3335400351828364 | CRITICAL |
| 2657 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | 1 | 2024-01-03 16:00:00 | 2024-01-03 19:10:00 | 3.1666666666666665 | 4.003376867351939 | 2.210012267334677 | HIGH |
| 2658 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | 2 | 2024-01-04 09:30:00 | 2024-01-04 11:10:00 | 1.6666666666666667 | 3.6685015649190733 | 1.5168384331813252 | MEDIUM |
| 2659 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | 3 | 2024-01-04 15:30:00 | 2024-01-05 02:20:00 | 10.833333333333334 | 6.3449162606992315 | 2.3335400351828364 | CRITICAL |
| 2664 | 3bb10529-b16e-4893-826b-73584fec01c8 | 8632 | 1 | 2024-01-03 11:57:00 | 2024-01-03 12:15:00 | 0.3 | 1.283380530777237 | 0.3234437611619254 | LOW |
| 2665 | 3bb10529-b16e-4893-826b-73584fec01c8 | 8632 | 2 | 2024-01-03 12:43:00 | 2024-01-03 12:45:00 | 0.03333333333333333 | 1.020508406256921 | 0.07309081859020174 | LOW |
| 2666 | 3bb10529-b16e-4893-826b-73584fec01c8 | 8632 | 3 | 2024-01-03 13:53:00 | 2024-01-03 14:07:00 | 0.23333333333333334 | 0.9677896088947029 | 0.14628346161628306 | LOW |
| 2667 | 3bb10529-b16e-4893-826b-73584fec01c8 | 8632 | 4 | 2024-01-03 15:44:00 | 2024-01-03 15:49:00 | 0.08333333333333333 | 0.9120422951788767 | 0.7245108861860307 | LOW |

### Bottom 10 Records

| ID | RunID | EquipID | EpisodeID | StartTime | EndTime | DurationHours | PeakZ | AvgZ | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 14963 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 8 | 2023-01-29 20:20:00 | 2023-01-29 21:40:00 | 1.3333333333333333 | 3.902492249011993 | -3.1739519953727724 | MEDIUM |
| 14962 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 7 | 2023-01-26 11:00:00 | 2023-01-26 12:10:00 | 1.1666666666666667 | 3.4436679089069364 | -2.7160619151592256 | MEDIUM |
| 14961 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 6 | 2023-01-25 16:10:00 | 2023-01-25 17:00:00 | 0.8333333333333334 | 4.00665580034256 | -3.472523033618927 | HIGH |
| 14960 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 5 | 2023-01-24 15:30:00 | 2023-01-24 16:40:00 | 1.1666666666666667 | 4.195594906806946 | -3.193463000655174 | HIGH |
| 14959 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 4 | 2023-01-23 17:10:00 | 2023-01-23 18:10:00 | 1.0 | 4.148783576488495 | -3.6075063926833018 | HIGH |
| 14958 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 3 | 2023-01-19 05:30:00 | 2023-01-19 05:50:00 | 0.3333333333333333 | 3.6411296963691706 | -3.604898885885874 | MEDIUM |
| 14957 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 2 | 2023-01-19 02:40:00 | 2023-01-19 04:00:00 | 1.3333333333333333 | 3.849806940555572 | -3.3053170323371885 | MEDIUM |
| 14956 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 1 | 2023-01-18 02:10:00 | 2023-01-18 04:30:00 | 2.3333333333333335 | 4.627344214916229 | -3.5083789149920146 | HIGH |
| 14955 | 01ce2248-c8af-4a56-94c5-0ae6e66b28d0 | 5010 | 37 | 2023-10-17 18:50:00 | 2023-10-17 21:40:00 | 2.8333333333333335 | 4.936287590488791 | -4.310804426069889 | HIGH |
| 14954 | 01ce2248-c8af-4a56-94c5-0ae6e66b28d0 | 5010 | 36 | 2023-10-17 04:50:00 | 2023-10-17 05:10:00 | 0.3333333333333333 | 4.778376519680023 | -4.470960303147634 | HIGH |

---


## dbo.ACM_Episodes

**Primary Key:** ID  
**Row Count:** 3,213  
**Date Range:** 2019-03-08 12:00:00 to 2025-09-12 00:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| EpisodeID | int | NO | 10 | — |
| StartTime | datetime2 | NO | — | — |
| EndTime | datetime2 | YES | — | — |
| DurationSeconds | float | YES | 53 | — |
| DurationHours | float | YES | 53 | — |
| RecordCount | int | YES | 10 | — |
| Culprits | nvarchar | YES | 512 | — |
| PrimaryDetector | nvarchar | YES | 64 | — |
| Severity | nvarchar | YES | 16 | — |
| RegimeLabel | int | YES | 10 | — |
| RegimeState | nvarchar | YES | 32 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

### Top 10 Records

| ID | RunID | EquipID | EpisodeID | StartTime | EndTime | DurationSeconds | DurationHours | RecordCount | Culprits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2537 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 1 | 2024-01-03 16:00:00 | 2024-01-03 19:10:00 | 11400.0 | 3.1666666666666665 | 1 | Multivariate Outlier (PCA-T2) -> Theoretical |
| 2538 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 2 | 2024-01-04 09:30:00 | 2024-01-04 11:10:00 | 6000.0 | 1.6666666666666667 | 1 | Multivariate Outlier (PCA-T2) -> LV |
| 2539 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 3 | 2024-01-04 15:30:00 | 2024-01-05 02:20:00 | 39000.0 | 10.833333333333334 | 1 | Multivariate Outlier (PCA-T2) -> Theoretical |
| 2540 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 1 | 2024-01-03 16:00:00 | 2024-01-03 19:10:00 | 11400.0 | 3.1666666666666665 | 1 | Multivariate Outlier (PCA-T2) -> Theoretical |
| 2541 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 2 | 2024-01-04 09:30:00 | 2024-01-04 11:10:00 | 6000.0 | 1.6666666666666667 | 1 | Multivariate Outlier (PCA-T2) -> LV |
| 2542 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 3 | 2024-01-04 15:30:00 | 2024-01-05 02:20:00 | 39000.0 | 10.833333333333334 | 1 | Multivariate Outlier (PCA-T2) -> Theoretical |
| 2547 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | 1 | 2024-01-03 11:57:00 | 2024-01-03 12:15:00 | 1080.0 | 0.3 | 1 | Density Anomaly (GMM) |
| 2548 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | 2 | 2024-01-03 12:43:00 | 2024-01-03 12:45:00 | 120.0 | 0.03333333333333333 | 1 | Density Anomaly (GMM) |
| 2549 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | 3 | 2024-01-03 13:53:00 | 2024-01-03 14:07:00 | 840.0 | 0.23333333333333334 | 1 | Density Anomaly (GMM) |
| 2550 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | 4 | 2024-01-03 15:44:00 | 2024-01-03 15:49:00 | 300.0 | 0.08333333333333333 | 1 | Density Anomaly (GMM) |

### Bottom 10 Records

| ID | RunID | EquipID | EpisodeID | StartTime | EndTime | DurationSeconds | DurationHours | RecordCount | Culprits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 14846 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 8 | 2023-01-29 20:20:00 | 2023-01-29 21:40:00 | 4800.0 | 1.3333333333333333 | 1 | Rare State (IsolationForest) |
| 14845 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 7 | 2023-01-26 11:00:00 | 2023-01-26 12:10:00 | 4200.0 | 1.1666666666666667 | 1 | Rare State (IsolationForest) |
| 14844 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 6 | 2023-01-25 16:10:00 | 2023-01-25 17:00:00 | 3000.0 | 0.8333333333333334 | 1 | Rare State (IsolationForest) |
| 14843 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 5 | 2023-01-24 15:30:00 | 2023-01-24 16:40:00 | 4200.0 | 1.1666666666666667 | 1 | Rare State (IsolationForest) |
| 14842 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 4 | 2023-01-23 17:10:00 | 2023-01-23 18:10:00 | 3600.0 | 1.0 | 1 | Rare State (IsolationForest) |
| 14841 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 3 | 2023-01-19 05:30:00 | 2023-01-19 05:50:00 | 1200.0 | 0.3333333333333333 | 1 | Rare State (IsolationForest) |
| 14840 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 2 | 2023-01-19 02:40:00 | 2023-01-19 04:00:00 | 4800.0 | 1.3333333333333333 | 1 | Rare State (IsolationForest) |
| 14839 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 1 | 2023-01-18 02:10:00 | 2023-01-18 04:30:00 | 8400.0 | 2.3333333333333335 | 1 | Rare State (IsolationForest) |
| 14838 | 01CE2248-C8AF-4A56-94C5-0AE6E66B28D0 | 5010 | 37 | 2023-10-17 18:50:00 | 2023-10-17 21:40:00 | 10200.0 | 2.8333333333333335 | 1 | Rare State (IsolationForest) |
| 14837 | 01CE2248-C8AF-4A56-94C5-0AE6E66B28D0 | 5010 | 36 | 2023-10-17 04:50:00 | 2023-10-17 05:10:00 | 1200.0 | 0.3333333333333333 | 1 | Rare State (IsolationForest) |

---


## dbo.ACM_FailureForecast

**Primary Key:** EquipID, RunID, Timestamp  
**Row Count:** 104,832  
**Date Range:** 2019-05-12 11:30:00 to 2025-09-21 23:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EquipID | int | NO | 10 | — |
| RunID | uniqueidentifier | NO | — | — |
| Timestamp | datetime2 | NO | — | — |
| FailureProb | float | NO | 53 | — |
| SurvivalProb | float | YES | 53 | — |
| HazardRate | float | YES | 53 | — |
| ThresholdUsed | float | NO | 53 | — |
| Method | nvarchar | NO | 50 | ('GaussianCDF') |
| CreatedAt | datetime2 | NO | — | (getdate()) |
| ID | bigint | NO | 19 | — |

### Top 10 Records

| EquipID | RunID | Timestamp | FailureProb | SurvivalProb | HazardRate | ThresholdUsed | Method | CreatedAt | ID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 00:30:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 11:08:02 | 802793 |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 01:30:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 11:08:02 | 802794 |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 02:30:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 11:08:02 | 802795 |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 03:30:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 11:08:02 | 802796 |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 04:30:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 11:08:02 | 802797 |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 05:30:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 11:08:02 | 802798 |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 06:30:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 11:08:02 | 802799 |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 07:30:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 11:08:02 | 802800 |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 08:30:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 11:08:02 | 802801 |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 09:30:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 11:08:02 | 802802 |

### Bottom 10 Records

| EquipID | RunID | Timestamp | FailureProb | SurvivalProb | HazardRate | ThresholdUsed | Method | CreatedAt | ID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 11:00:00 | 4.1071356005783956e-58 | 1.0 | 1.3511784165858986e-59 | 70.0 | RegimeConditionedHolt | 2026-01-19 18:26:33 | 202440 |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 10:30:00 | 4.039576679749101e-58 | 1.0 | 1.3290367861796716e-59 | 70.0 | RegimeConditionedHolt | 2026-01-19 18:26:33 | 202439 |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 10:00:00 | 3.973124840440117e-58 | 1.0 | 1.307256599428759e-59 | 70.0 | RegimeConditionedHolt | 2026-01-19 18:26:33 | 202438 |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 09:30:00 | 3.907762010468679e-58 | 1.0 | 1.2858319789106e-59 | 70.0 | RegimeConditionedHolt | 2026-01-19 18:26:33 | 202437 |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 09:00:00 | 3.843470411523149e-58 | 1.0 | 1.26475714243357e-59 | 70.0 | RegimeConditionedHolt | 2026-01-19 18:26:33 | 202436 |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 08:30:00 | 3.780232554401471e-58 | 1.0 | 1.244026401451048e-59 | 70.0 | RegimeConditionedHolt | 2026-01-19 18:26:33 | 202435 |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 08:00:00 | 3.718031234328918e-58 | 1.0 | 1.2236341595310495e-59 | 70.0 | RegimeConditionedHolt | 2026-01-19 18:26:33 | 202434 |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 07:30:00 | 3.656849526352366e-58 | 1.0 | 1.203574910955313e-59 | 70.0 | RegimeConditionedHolt | 2026-01-19 18:26:33 | 202433 |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 07:00:00 | 3.5966707808046e-58 | 1.0 | 1.1838432391882532e-59 | 70.0 | RegimeConditionedHolt | 2026-01-19 18:26:33 | 202432 |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 06:30:00 | 3.5374786188451875e-58 | 1.0 | 1.164433815465747e-59 | 70.0 | RegimeConditionedHolt | 2026-01-19 18:26:33 | 202431 |

---


## dbo.ACM_FeatureDropLog

**Primary Key:** ID  
**Row Count:** 1,677  
**Date Range:** 2026-01-19 10:53:30 to 2026-02-20 13:41:26  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | YES | — | — |
| EquipID | int | NO | 10 | — |
| FeatureName | nvarchar | NO | 200 | — |
| DropReason | nvarchar | NO | 100 | — |
| DropValue | float | YES | 53 | — |
| Threshold | float | YES | 53 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |

### Top 10 Records

| ID | RunID | EquipID | FeatureName | DropReason | DropValue | Threshold | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1118 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | LV_ActivePower_kurt | low_variance | 0.0 | NULL | 2026-01-19 10:53:30 |
| 1119 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | LV_ActivePower_rz | low_variance | 0.0 | NULL | 2026-01-19 10:53:30 |
| 1120 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | LV_ActivePower_mean | low_variance | 0.0 | NULL | 2026-01-19 10:53:30 |
| 1121 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | LV_ActivePower_slope | low_variance | 0.0 | NULL | 2026-01-19 10:53:30 |
| 1122 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | LV_ActivePower_med | low_variance | 0.0 | NULL | 2026-01-19 10:53:30 |
| 1123 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | LV_ActivePower_std | low_variance | 0.0 | NULL | 2026-01-19 10:53:30 |
| 1124 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | LV_ActivePower_mad | low_variance | 0.0 | NULL | 2026-01-19 10:53:30 |
| 1125 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | LV_ActivePower_skew | low_variance | 0.0 | NULL | 2026-01-19 10:53:30 |
| 1126 | 496202D1-C512-4D13-93B6-8AD2F15E7C24 | 8632 | Theoretical_Power_Curve_slope | low_variance | 0.0 | NULL | 2026-01-19 10:56:44 |
| 1127 | 496202D1-C512-4D13-93B6-8AD2F15E7C24 | 8632 | Theoretical_Power_Curve_skew | low_variance | 0.0 | NULL | 2026-01-19 10:56:44 |

### Bottom 10 Records

| ID | RunID | EquipID | FeatureName | DropReason | DropValue | Threshold | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 16476 | 9A0F444E-C812-45FC-B2A0-74E36CBDB29B | 5000 | sensor_52_std_energy_0 | low_variance | 0.0 | NULL | 2026-02-20 13:41:26 |
| 16475 | 9A0F444E-C812-45FC-B2A0-74E36CBDB29B | 5000 | sensor_31_min_energy_0 | low_variance | 0.0 | NULL | 2026-02-20 13:41:26 |
| 16474 | 9A0F444E-C812-45FC-B2A0-74E36CBDB29B | 5000 | sensor_35_avg_energy_0 | low_variance | 2.5166559662725e-27 | NULL | 2026-02-20 13:41:26 |
| 16473 | 9A0F444E-C812-45FC-B2A0-74E36CBDB29B | 5000 | sensor_21_avg_energy_0 | low_variance | 1.840818822192907e-27 | NULL | 2026-02-20 13:41:26 |
| 16472 | 9A0F444E-C812-45FC-B2A0-74E36CBDB29B | 5000 | sensor_53_avg_energy_0 | low_variance | 5.819272206505073e-28 | NULL | 2026-02-20 13:41:26 |
| 16471 | 9A0F444E-C812-45FC-B2A0-74E36CBDB29B | 5000 | sensor_18_max_energy_0 | low_variance | 0.0 | NULL | 2026-02-20 13:41:26 |
| 16470 | 9A0F444E-C812-45FC-B2A0-74E36CBDB29B | 5000 | sensor_52_max_energy_0 | low_variance | 0.0 | NULL | 2026-02-20 13:41:26 |
| 16469 | 9A0F444E-C812-45FC-B2A0-74E36CBDB29B | 5000 | sensor_8_avg_energy_0 | low_variance | 0.0 | NULL | 2026-02-20 13:41:26 |
| 16468 | 9A0F444E-C812-45FC-B2A0-74E36CBDB29B | 5000 | reactive_power_28_max_energy_0 | low_variance | 0.0 | NULL | 2026-02-20 13:41:26 |
| 16467 | 9A0F444E-C812-45FC-B2A0-74E36CBDB29B | 5000 | sensor_50_energy_0 | low_variance | 0.0 | NULL | 2026-02-20 13:41:26 |

---


## dbo.ACM_ForecastState

**Primary Key:** EquipID, StateVersion  
**Row Count:** 0  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| EquipID | int | NO | 10 | — |
| StateVersion | int | NO | 10 | — |
| ModelType | nvarchar | YES | 50 | — |
| ModelParamsJson | nvarchar | YES | -1 | — |
| ResidualVariance | float | YES | 53 | — |
| LastForecastHorizonJson | nvarchar | YES | -1 | — |
| HazardBaseline | float | YES | 53 | — |
| LastRetrainTime | datetime2 | YES | — | — |
| TrainingDataHash | nvarchar | YES | 64 | — |
| TrainingWindowHours | int | YES | 10 | — |
| ForecastQualityJson | nvarchar | YES | -1 | — |
| CreatedAt | datetime2 | YES | — | (getdate()) |

---


## dbo.ACM_Forecast_QualityMetrics

**Primary Key:** MetricID  
**Row Count:** 0  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| MetricID | int | NO | 10 | — |
| RunID | varchar | NO | 100 | — |
| EquipID | int | NO | 10 | — |
| RMSE | float | YES | 53 | — |
| MAE | float | YES | 53 | — |
| MAPE | float | YES | 53 | — |
| R2Score | float | YES | 53 | — |
| DataHash | varchar | YES | 32 | — |
| ModelVersion | int | YES | 10 | — |
| RetrainTriggered | bit | NO | — | ((0)) |
| RetrainReason | varchar | YES | 200 | — |
| ForecastHorizonHours | float | NO | 53 | — |
| SampleCount | int | YES | 10 | — |
| ComputeTimestamp | datetime2 | NO | — | (getdate()) |
| CreatedAt | datetime2 | NO | — | (getdate()) |

---


## dbo.ACM_ForecastingState

**Primary Key:** EquipID, StateVersion  
**Row Count:** 7  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| EquipID | int | NO | 10 | — |
| StateVersion | int | NO | 10 | — |
| ModelCoefficientsJson | nvarchar | YES | -1 | — |
| LastForecastJson | nvarchar | YES | -1 | — |
| LastRetrainTime | datetime2 | YES | — | — |
| TrainingDataHash | nvarchar | YES | 64 | — |
| DataVolumeAnalyzed | bigint | YES | 19 | — |
| RecentMAE | float | YES | 53 | — |
| RecentRMSE | float | YES | 53 | — |
| RetriggerReason | nvarchar | YES | 200 | — |
| CreatedAt | datetime2 | NO | — | (getdate()) |
| UpdatedAt | datetime2 | NO | — | (getdate()) |

### Top 10 Records

| ID | EquipID | StateVersion | ModelCoefficientsJson | LastForecastJson | LastRetrainTime | TrainingDataHash | DataVolumeAnalyzed | RecentMAE | RecentRMSE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 17 | 8632 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.2, "beta": 0.03, "level": 88.761191261... | {"forecast_mean": 7.240821912614943, "forecast_std": 19.388388038997423, "forecast_range": 88.707... | NULL |  | 21281 | 19.388388038997423 | NULL |
| 23 | 8635 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.05, "beta": 0.01, "level": 47.64524147... | {"forecast_mean": 1.4423215554806277, "forecast_std": 6.570960912590737, "forecast_range": 46.502... | NULL |  | 10269 | 6.570960912590737 | NULL |
| 30 | 5022 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.95, "beta": 0.01, "level": 92.80989910... | {"forecast_mean": 86.75207713346725, "forecast_std": 3.4940171390585113, "forecast_range": 12.091... | NULL |  | 626 | 3.4940171390585113 | NULL |
| 51 | 5014 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.95, "beta": 0.01, "level": 94.05357420... | {"forecast_mean": 91.29142771024733, "forecast_std": 1.593144736470478, "forecast_range": 5.51334... | NULL |  | 66748 | 1.593144736470478 | NULL |
| 57 | 5073 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.8, "beta": 0.01, "level": 93.255194410... | {"forecast_mean": 90.49732762782227, "forecast_std": 1.5906762937486225, "forecast_range": 5.5048... | NULL |  | 93858 | 1.5906762937486225 | NULL |
| 66 | 1 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.8, "beta": 0.2, "level": 67.9728237708... | {"forecast_mean": 88.02482876451488, "forecast_std": 10.61779170302212, "forecast_range": 31.9564... | NULL |  | 14089 | 10.61779170302212 | NULL |
| 67 | 2621 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.4, "beta": 0.08, "level": 64.176364882... | {"forecast_mean": 84.15697351600969, "forecast_std": 11.140963439847333, "forecast_range": 35.398... | NULL |  | 4576 | 11.140963439847333 | NULL |

---


## dbo.ACM_HealthForecast

**Primary Key:** EquipID, RunID, Timestamp  
**Row Count:** 104,832  
**Date Range:** 2019-05-12 11:30:00 to 2025-09-21 23:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EquipID | int | NO | 10 | — |
| RunID | uniqueidentifier | NO | — | — |
| Timestamp | datetime2 | NO | — | — |
| ForecastHealth | float | NO | 53 | — |
| CiLower | float | YES | 53 | — |
| CiUpper | float | YES | 53 | — |
| ForecastStd | float | YES | 53 | — |
| Method | nvarchar | NO | 50 | ('LinearTrend') |
| CreatedAt | datetime2 | NO | — | (getdate()) |
| RegimeLabel | int | YES | 10 | — |
| ID | bigint | NO | 19 | — |

### Top 10 Records

| EquipID | RunID | Timestamp | ForecastHealth | CiLower | CiUpper | ForecastStd | Method | CreatedAt | RegimeLabel |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 00:30:00 | 55.40627741882604 | 54.27084221588731 | 56.54171262176477 | 0.567717601469365 | RegimeConditionedHolt | 2026-02-19 11:08:00 | NULL |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 01:30:00 | 55.444368455187714 | 53.984610282941965 | 56.90412662743346 | 0.567717601469365 | RegimeConditionedHolt | 2026-02-19 11:08:00 | NULL |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 02:30:00 | 55.482459491549385 | 53.75349326880235 | 57.21142571429642 | 0.567717601469365 | RegimeConditionedHolt | 2026-02-19 11:08:00 | NULL |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 03:30:00 | 55.52055052791105 | 53.55467439925111 | 57.486426656570984 | 0.567717601469365 | RegimeConditionedHolt | 2026-02-19 11:08:00 | NULL |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 04:30:00 | 55.55864156427272 | 53.3775654073677 | 57.73971772117774 | 0.567717601469365 | RegimeConditionedHolt | 2026-02-19 11:08:00 | NULL |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 05:30:00 | 55.59673260063439 | 53.21623644108472 | 57.97722876018406 | 0.567717601469365 | RegimeConditionedHolt | 2026-02-19 11:08:00 | NULL |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 06:30:00 | 55.63482363699606 | 53.06697623834768 | 58.20267103564444 | 0.567717601469365 | RegimeConditionedHolt | 2026-02-19 11:08:00 | NULL |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 07:30:00 | 55.67291467335773 | 52.92728303148732 | 58.41854631522814 | 0.567717601469365 | RegimeConditionedHolt | 2026-02-19 11:08:00 | NULL |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 08:30:00 | 55.7110057097194 | 52.79537789821949 | 58.62663352121931 | 0.567717601469365 | RegimeConditionedHolt | 2026-02-19 11:08:00 | NULL |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 2024-05-11 09:30:00 | 55.749096746081065 | 52.669943851358674 | 58.828249640803456 | 0.567717601469365 | RegimeConditionedHolt | 2026-02-19 11:08:00 | NULL |

### Bottom 10 Records

| EquipID | RunID | Timestamp | ForecastHealth | CiLower | CiUpper | ForecastStd | Method | CreatedAt | RegimeLabel |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 11:00:00 | 90.65028362386016 | 87.62209703485105 | 93.67847021286927 | 0.5421848476920346 | RegimeConditionedHolt | 2026-01-19 18:26:31 | NULL |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 10:30:00 | 90.65161177429563 | 87.6326237646227 | 93.67059978396856 | 0.5421848476920346 | RegimeConditionedHolt | 2026-01-19 18:26:31 | NULL |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 10:00:00 | 90.6529399247311 | 87.64313616994663 | 93.66274367951557 | 0.5421848476920346 | RegimeConditionedHolt | 2026-01-19 18:26:31 | NULL |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 09:30:00 | 90.65426807516658 | 87.6536342172587 | 93.65490193307447 | 0.5421848476920346 | RegimeConditionedHolt | 2026-01-19 18:26:31 | NULL |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 09:00:00 | 90.65559622560205 | 87.6641178727896 | 93.6470745784145 | 0.5421848476920346 | RegimeConditionedHolt | 2026-01-19 18:26:31 | NULL |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 08:30:00 | 90.65692437603752 | 87.67458710256344 | 93.63926164951161 | 0.5421848476920346 | RegimeConditionedHolt | 2026-01-19 18:26:31 | NULL |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 08:00:00 | 90.658252526473 | 87.68504187239611 | 93.6314631805499 | 0.5421848476920346 | RegimeConditionedHolt | 2026-01-19 18:26:31 | NULL |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 07:30:00 | 90.65958067690848 | 87.69548214789374 | 93.62367920592321 | 0.5421848476920346 | RegimeConditionedHolt | 2026-01-19 18:26:31 | NULL |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 07:00:00 | 90.66090882734395 | 87.70590789445123 | 93.61590976023666 | 0.5421848476920346 | RegimeConditionedHolt | 2026-01-19 18:26:31 | NULL |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 2019-05-19 06:30:00 | 90.66223697777941 | 87.7163190772506 | 93.60815487830823 | 0.5421848476920346 | RegimeConditionedHolt | 2026-01-19 18:26:31 | NULL |

---


## dbo.ACM_HealthTimeline

**Primary Key:** No primary key  
**Row Count:** 163,035  
**Date Range:** 2019-03-08 11:30:00 to 2025-09-14 23:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Timestamp | datetime2 | NO | — | — |
| HealthIndex | float | NO | 53 | — |
| HealthZone | nvarchar | NO | 50 | — |
| FusedZ | float | NO | 53 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| RawHealthIndex | float | YES | 53 | — |
| QualityFlag | nvarchar | YES | 50 | — |
| Confidence | float | YES | 53 | — |
| ConfidenceFactors | nvarchar | YES | 200 | — |
| ID | bigint | NO | 19 | — |

### Top 10 Records

| Timestamp | HealthIndex | HealthZone | FusedZ | RunID | EquipID | RawHealthIndex | QualityFlag | Confidence | ConfidenceFactors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2019-03-08 11:30:00 | 93.7 | GOOD | -0.25 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 93.69999694824219 | NORMAL | 0.313 | NULL |
| 2019-03-08 12:00:00 | 81.32 | WATCH | 2.4191999435424805 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 52.41999816894531 | NORMAL | 0.421 | NULL |
| 2019-03-08 12:30:00 | 72.06 | WATCH | 2.4846999645233154 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 50.459999084472656 | NORMAL | 0.425 | NULL |
| 2019-03-08 13:00:00 | 75.8 | WATCH | 1.0860999822616577 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 84.51000213623047 | NORMAL | 0.355 | NULL |
| 2019-03-08 13:30:00 | 80.02 | WATCH | 0.6816999912261963 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 89.86000061035156 | NORMAL | 0.335 | NULL |
| 2019-03-08 14:00:00 | 82.61 | WATCH | 0.7849000096321106 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 88.68000030517578 | NORMAL | 0.34 | NULL |
| 2019-03-08 14:30:00 | 85.27 | GOOD | 0.5228999853134155 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 91.47000122070312 | NORMAL | 0.328 | NULL |
| 2019-03-08 15:00:00 | 86.84 | GOOD | 0.6220999956130981 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 90.5 | NORMAL | 0.333 | NULL |
| 2019-03-08 15:30:00 | 87.51 | GOOD | 0.7512999773025513 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 89.08000183105469 | NORMAL | 0.339 | NULL |
| 2019-03-08 16:00:00 | 88.62 | GOOD | 0.550599992275238 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 91.20999908447266 | NORMAL | 0.33 | NULL |

### Bottom 10 Records

| Timestamp | HealthIndex | HealthZone | FusedZ | RunID | EquipID | RawHealthIndex | QualityFlag | Confidence | ConfidenceFactors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-09-14 23:00:00 | 67.14 | ALERT | -2.0933001041412354 | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 61.970001220703125 | NORMAL | 0.326 | NULL |
| 2025-09-14 22:30:00 | 69.35 | ALERT | -2.044800043106079 | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 63.33000183105469 | NORMAL | 0.324 | NULL |
| 2025-09-14 22:00:00 | 71.94 | WATCH | -1.520300030708313 | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 76.41999816894531 | NORMAL | 0.297 | NULL |
| 2025-09-14 21:30:00 | 70.02 | WATCH | -1.5996999740600586 | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 74.66000366210938 | NORMAL | 0.301 | NULL |
| 2025-09-14 21:00:00 | 68.03 | ALERT | -1.1567000150680542 | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 83.37000274658203 | NORMAL | 0.279 | NULL |
| 2025-09-14 20:30:00 | 61.46 | ALERT | -1.9437999725341797 | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 66.08999633789062 | NORMAL | 0.318 | NULL |
| 2025-09-14 20:00:00 | 59.47 | ALERT | -2.1245999336242676 | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 61.06999969482422 | NORMAL | 0.327 | NULL |
| 2025-09-14 19:30:00 | 58.78 | ALERT | -2.313800096511841 | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 55.560001373291016 | NORMAL | 0.336 | NULL |
| 2025-09-14 19:00:00 | 60.16 | ALERT | -2.0394999980926514 | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 63.470001220703125 | NORMAL | 0.322 | NULL |
| 2025-09-14 18:30:00 | 58.74 | ALERT | -2.2288999557495117 | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 58.060001373291016 | NORMAL | 0.331 | NULL |

---


## dbo.ACM_HistorianData

**Primary Key:** ID  
**Row Count:** 0  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| EquipID | int | NO | 10 | — |
| EntryDateTime | datetime2 | NO | — | — |
| SensorName | nvarchar | NO | 128 | — |
| SensorValue | float | YES | 53 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

---


## dbo.ACM_MultivariateForecast

**Primary Key:** ID  
**Row Count:** 28,560  
**Date Range:** 2022-08-16 14:50:00 to 2025-09-21 23:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| ForecastTime | datetime2 | NO | — | — |
| SensorName | nvarchar | NO | 128 | — |
| ForecastValue | float | YES | 53 | — |
| CI_Lower | float | YES | 53 | — |
| CI_Upper | float | YES | 53 | — |
| CorrelationGroup | int | YES | 10 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

### Top 10 Records

| ID | RunID | EquipID | ForecastTime | SensorName | ForecastValue | CI_Lower | CI_Upper | CorrelationGroup | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 53089 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | 2022-08-16 14:50:00 | power_30_avg | 47.504585034214166 | NULL | NULL | NULL | 2026-01-22 09:49:10 |
| 53090 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | 2022-08-16 15:50:00 | power_30_avg | 95.00523340852564 | NULL | NULL | NULL | 2026-01-22 09:49:10 |
| 53091 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | 2022-08-16 16:50:00 | power_30_avg | 142.50588178283712 | NULL | NULL | NULL | 2026-01-22 09:49:10 |
| 53092 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | 2022-08-16 17:50:00 | power_30_avg | 190.0065301571486 | NULL | NULL | NULL | 2026-01-22 09:49:10 |
| 53093 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | 2022-08-16 18:50:00 | power_30_avg | 237.50717853146008 | NULL | NULL | NULL | 2026-01-22 09:49:10 |
| 53094 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | 2022-08-16 19:50:00 | power_30_avg | 285.0078269057716 | NULL | NULL | NULL | 2026-01-22 09:49:10 |
| 53095 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | 2022-08-16 20:50:00 | power_30_avg | 332.5084752800831 | NULL | NULL | NULL | 2026-01-22 09:49:10 |
| 53096 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | 2022-08-16 21:50:00 | power_30_avg | 380.00912365439456 | NULL | NULL | NULL | 2026-01-22 09:49:10 |
| 53097 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | 2022-08-16 22:50:00 | power_30_avg | 427.50977202870604 | NULL | NULL | NULL | 2026-01-22 09:49:10 |
| 53098 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | 2022-08-16 23:50:00 | power_30_avg | 475.0104204030175 | NULL | NULL | NULL | 2026-01-22 09:49:10 |

### Bottom 10 Records

| ID | RunID | EquipID | ForecastTime | SensorName | ForecastValue | CI_Lower | CI_Upper | CorrelationGroup | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 443776 | F3F9203B-865B-4FDF-B62D-D3A57D23FD92 | 2621 | 2024-06-23 01:59:00 | B2VIB2 | 0.05010448540657442 | NULL | NULL | NULL | 2026-02-19 14:10:02 |
| 443775 | F3F9203B-865B-4FDF-B62D-D3A57D23FD92 | 2621 | 2024-06-23 01:59:00 | B1VIB1 | 0.1423070333497061 | NULL | NULL | NULL | 2026-02-19 14:10:02 |
| 443774 | F3F9203B-865B-4FDF-B62D-D3A57D23FD92 | 2621 | 2024-06-23 01:59:00 | INACTTBTEMP1 | 126.32611871569902 | NULL | NULL | NULL | 2026-02-19 14:10:02 |
| 443773 | F3F9203B-865B-4FDF-B62D-D3A57D23FD92 | 2621 | 2024-06-23 01:59:00 | B2RADVIBX | 1.1061321779096993 | NULL | NULL | NULL | 2026-02-19 14:10:02 |
| 443772 | F3F9203B-865B-4FDF-B62D-D3A57D23FD92 | 2621 | 2024-06-23 01:59:00 | B1TEMP1 | 162.5268143874294 | NULL | NULL | NULL | 2026-02-19 14:10:02 |
| 443771 | F3F9203B-865B-4FDF-B62D-D3A57D23FD92 | 2621 | 2024-06-23 01:59:00 | B2TEMP1 | 185.91684864976656 | NULL | NULL | NULL | 2026-02-19 14:10:02 |
| 443770 | F3F9203B-865B-4FDF-B62D-D3A57D23FD92 | 2621 | 2024-06-23 01:59:00 | B2RADVIBY | 0.6195062079673828 | NULL | NULL | NULL | 2026-02-19 14:10:02 |
| 443769 | F3F9203B-865B-4FDF-B62D-D3A57D23FD92 | 2621 | 2024-06-23 01:59:00 | ACTTBTEMP1 | 169.8573845979231 | NULL | NULL | NULL | 2026-02-19 14:10:02 |
| 443768 | F3F9203B-865B-4FDF-B62D-D3A57D23FD92 | 2621 | 2024-06-23 01:59:00 | LOTEMP1 | 129.93256130129345 | NULL | NULL | NULL | 2026-02-19 14:10:02 |
| 443767 | F3F9203B-865B-4FDF-B62D-D3A57D23FD92 | 2621 | 2024-06-23 00:59:00 | B2VIB2 | 0.0424636411347397 | NULL | NULL | NULL | 2026-02-19 14:10:02 |

---


## dbo.ACM_OMR_Diagnostics

**Primary Key:** DiagnosticID  
**Row Count:** 44  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| DiagnosticID | int | NO | 10 | — |
| RunID | varchar | NO | 100 | — |
| EquipID | int | NO | 10 | — |
| ModelType | varchar | NO | 20 | — |
| NComponents | int | NO | 10 | — |
| TrainSamples | int | NO | 10 | — |
| TrainFeatures | int | NO | 10 | — |
| TrainResidualStd | float | NO | 53 | — |
| TrainStartTime | datetime2 | YES | — | — |
| TrainEndTime | datetime2 | YES | — | — |
| CalibrationStatus | varchar | NO | 20 | — |
| SaturationRate | float | YES | 53 | — |
| FusionWeight | float | YES | 53 | — |
| FitTimestamp | datetime2 | NO | — | (getdate()) |
| CreatedAt | datetime2 | NO | — | (getdate()) |

### Top 10 Records

| DiagnosticID | RunID | EquipID | ModelType | NComponents | TrainSamples | TrainFeatures | TrainResidualStd | TrainStartTime | TrainEndTime |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 41 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | pls | 5 | 360 | 32 | 0.8067308429970524 | NULL | NULL |
| 44 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | pls | 5 | 360 | 32 | 0.8067308429970524 | NULL | NULL |
| 45 | 3bb10529-b16e-4893-826b-73584fec01c8 | 8632 | pls | 5 | 715 | 24 | 0.9147919717361664 | NULL | NULL |
| 46 | 496202d1-c512-4d13-93b6-8ad2f15e7c24 | 8632 | pls | 5 | 715 | 24 | 0.9294624429769549 | NULL | NULL |
| 49 | c2cfa54f-fb33-4f66-8340-9a1a0dcec544 | 8632 | pls | 5 | 715 | 32 | 0.8141382877405972 | NULL | NULL |
| 50 | d80354e0-96f4-4a76-9f2a-c73f9c36f66f | 8632 | pls | 5 | 715 | 32 | 0.7420540748762706 | NULL | NULL |
| 52 | 09e1e60f-7f6a-4c79-84cd-a752f45cae94 | 8632 | pls | 5 | 715 | 32 | 0.9371872586845428 | NULL | NULL |
| 54 | c2880e7a-ea1f-47cf-9883-370175810ed0 | 8632 | pls | 5 | 715 | 32 | 0.6653145755973883 | NULL | NULL |
| 55 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | pls | 5 | 715 | 32 | 0.8494126461538997 | NULL | NULL |
| 67 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a | 8635 | pls | 5 | 4679 | 112 | 1.2097412743237341 | NULL | NULL |

### Bottom 10 Records

| DiagnosticID | RunID | EquipID | ModelType | NComponents | TrainSamples | TrainFeatures | TrainResidualStd | TrainStartTime | TrainEndTime |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 593 | a1c1db6b-39c3-4926-943d-a5b597be3e12 | 5000 | pls | 5 | 2217 | 790 | 5.633201874253126 | NULL | NULL |
| 592 | b496d61c-e3a3-4c21-a2b2-a6555510a0fc | 5010 | pls | 5 | 6450 | 790 | 4.812900723548848 | NULL | NULL |
| 566 | b2f3a6c1-b13d-4b25-85da-1074cfe5ad41 | 2621 | pls | 5 | 500 | 128 | 1.0382164579010493 | NULL | NULL |
| 565 | 2488646c-6a91-4c84-9bd9-dfe360765af5 | 1 | pls | 5 | 603 | 72 | 1.112074952704745 | NULL | NULL |
| 517 | 98fb9e34-22a9-4b46-9c60-98237def121c | 5073 | pls | 5 | 2262 | 632 | 3.7040788928564456 | NULL | NULL |
| 516 | 471b19a1-2521-40b7-a20b-f9c2c6950d96 | 5073 | pls | 5 | 2257 | 632 | 3.830826652970209 | NULL | NULL |
| 515 | af435408-e910-48a8-b7a7-fb7d927517da | 5073 | pls | 5 | 2257 | 632 | 3.830826652970209 | NULL | NULL |
| 514 | e752afbf-d494-4bb4-b865-f4fe4703ee97 | 5073 | pls | 5 | 2262 | 632 | 3.6878333186711005 | NULL | NULL |
| 513 | f1b4bf44-6ae1-4731-8a8d-5652b482a9e9 | 5073 | pls | 5 | 2262 | 632 | 3.6878333186711005 | NULL | NULL |
| 512 | 66ec2d87-e50b-4eeb-9229-5868c19cdbe2 | 5073 | pls | 5 | 2262 | 632 | 3.438576423276252 | NULL | NULL |

---


## dbo.ACM_PCA_Loadings

**Primary Key:** ID  
**Row Count:** 142,910  
**Date Range:** 2026-01-19 16:20:07 to 2026-02-20 19:09:40  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| ComponentIndex | int | YES | 10 | — |
| SensorName | nvarchar | YES | 100 | — |
| Loading | float | NO | 53 | — |
| AbsLoading | float | NO | 53 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

### Top 10 Records

| ID | RunID | EquipID | ComponentIndex | SensorName | Loading | AbsLoading | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 81256 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 1 | LV_ActivePower_med | -1.1972149752980147e-07 | 1.1972149752980147e-07 | 2026-01-19 16:20:07 |
| 81257 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 1 | Theoretical_Power_Curve_med | -1.0935867114962319e-06 | 1.0935867114962319e-06 | 2026-01-19 16:20:07 |
| 81258 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 1 | Wind_Direction_med | -7.786322562638761e-06 | 7.786322562638761e-06 | 2026-01-19 16:20:07 |
| 81259 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 1 | Wind_Speed_med | -1.842462552764948e-06 | 1.842462552764948e-06 | 2026-01-19 16:20:07 |
| 81260 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 1 | LV_ActivePower_mad | -1.649254302490244e-06 | 1.649254302490244e-06 | 2026-01-19 16:20:07 |
| 81261 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 1 | Theoretical_Power_Curve_mad | -1.4055486489367238e-06 | 1.4055486489367238e-06 | 2026-01-19 16:20:07 |
| 81262 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 1 | Wind_Direction_mad | 5.307781227344659e-06 | 5.307781227344659e-06 | 2026-01-19 16:20:07 |
| 81263 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 1 | Wind_Speed_mad | -2.9218720608582487e-07 | 2.9218720608582487e-07 | 2026-01-19 16:20:07 |
| 81264 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 1 | LV_ActivePower_mean | -1.0446096105371298e-07 | 1.0446096105371298e-07 | 2026-01-19 16:20:07 |
| 81265 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 1 | LV_ActivePower_std | -1.931601913651609e-06 | 1.931601913651609e-06 | 2026-01-19 16:20:07 |

### Bottom 10 Records

| ID | RunID | EquipID | ComponentIndex | SensorName | Loading | AbsLoading | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1803900 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 5 | wind_speed_4_avg_rz | 4.478362636417164e-05 | 4.478362636417164e-05 | 2026-02-20 19:09:40 |
| 1803899 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 5 | wind_speed_3_std_rz | 4.797015465004035e-05 | 4.797015465004035e-05 | 2026-02-20 19:09:40 |
| 1803898 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 5 | wind_speed_3_min_rz | -1.6774746448240657e-05 | 1.6774746448240657e-05 | 2026-02-20 19:09:40 |
| 1803897 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 5 | wind_speed_3_max_rz | 1.7236269830601326e-05 | 1.7236269830601326e-05 | 2026-02-20 19:09:40 |
| 1803896 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 5 | wind_speed_3_avg_rz | 4.719632632892986e-05 | 4.719632632892986e-05 | 2026-02-20 19:09:40 |
| 1803895 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 5 | sensor_9_avg_rz | 8.596233528986205e-05 | 8.596233528986205e-05 | 2026-02-20 19:09:40 |
| 1803894 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 5 | sensor_8_avg_rz | 0.00022813910422761586 | 0.00022813910422761586 | 2026-02-20 19:09:40 |
| 1803893 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 5 | sensor_7_avg_rz | 5.458249974510825e-05 | 5.458249974510825e-05 | 2026-02-20 19:09:40 |
| 1803892 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 5 | sensor_6_avg_rz | 7.50084062203169e-05 | 7.50084062203169e-05 | 2026-02-20 19:09:40 |
| 1803891 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 5 | sensor_5_std_rz | 0.00031813362758887384 | 0.00031813362758887384 | 2026-02-20 19:09:40 |

---


## dbo.ACM_PCA_Metrics

**Primary Key:** ID  
**Row Count:** 69  
**Date Range:** 2026-01-19 10:47:24 to 2026-02-20 13:39:43  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| NComponents | int | NO | 10 | — |
| ExplainedVariance | float | YES | 53 | — |
| ComponentsJson | nvarchar | YES | -1 | — |
| MetricType | nvarchar | YES | 50 | — |
| TrainSamples | int | YES | 10 | — |
| TrainFeatures | int | YES | 10 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

### Top 10 Records

| ID | RunID | EquipID | NComponents | ExplainedVariance | ComponentsJson | MetricType | TrainSamples | TrainFeatures | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 5 | NULL | [{"name": "PCA", "type": "n_components", "value": 5.0}, {"name": "PCA", "type": "variance_explain... | pca_fit | NULL | NULL | 2026-01-19 10:47:24 |
| 45 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 5 | NULL | [{"name": "PCA", "type": "n_components", "value": 5.0}, {"name": "PCA", "type": "variance_explain... | pca_fit | NULL | NULL | 2026-01-19 10:51:03 |
| 46 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | 5 | NULL | [{"name": "PCA", "type": "n_components", "value": 5.0}, {"name": "PCA", "type": "variance_explain... | pca_fit | NULL | NULL | 2026-01-19 10:53:32 |
| 47 | 496202D1-C512-4D13-93B6-8AD2F15E7C24 | 8632 | 5 | NULL | [{"name": "PCA", "type": "n_components", "value": 5.0}, {"name": "PCA", "type": "variance_explain... | pca_fit | NULL | NULL | 2026-01-19 10:56:46 |
| 50 | C2CFA54F-FB33-4F66-8340-9A1A0DCEC544 | 8632 | 5 | NULL | [{"name": "PCA", "type": "n_components", "value": 5.0}, {"name": "PCA", "type": "variance_explain... | pca_fit | NULL | NULL | 2026-01-19 11:00:44 |
| 51 | D80354E0-96F4-4A76-9F2A-C73F9C36F66F | 8632 | 5 | NULL | [{"name": "PCA", "type": "n_components", "value": 5.0}, {"name": "PCA", "type": "variance_explain... | pca_fit | NULL | NULL | 2026-01-19 11:04:00 |
| 54 | 09E1E60F-7F6A-4C79-84CD-A752F45CAE94 | 8632 | 5 | NULL | [{"name": "PCA", "type": "n_components", "value": 5.0}, {"name": "PCA", "type": "variance_explain... | pca_fit | NULL | NULL | 2026-01-19 11:07:44 |
| 55 | C2880E7A-EA1F-47CF-9883-370175810ED0 | 8632 | 5 | NULL | [{"name": "PCA", "type": "n_components", "value": 5.0}, {"name": "PCA", "type": "variance_explain... | pca_fit | NULL | NULL | 2026-01-19 11:11:06 |
| 56 | E211FDF4-2C57-4DD6-8AAE-F0E0802F21F8 | 8632 | 5 | NULL | [{"name": "PCA", "type": "n_components", "value": 5.0}, {"name": "PCA", "type": "variance_explain... | pca_fit | NULL | NULL | 2026-01-19 11:14:44 |
| 68 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 5 | NULL | [{"name": "PCA", "type": "n_components", "value": 5.0}, {"name": "PCA", "type": "variance_explain... | pca_fit | NULL | NULL | 2026-01-19 12:53:14 |

### Bottom 10 Records

| ID | RunID | EquipID | NComponents | ExplainedVariance | ComponentsJson | MetricType | TrainSamples | TrainFeatures | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11003 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 5 | 0.9999997444123878 | [{"name": "PC1", "type": "variance_ratio", "value": 0.7301259683363418, "cumulative": 0.730125968... | pca_fit | 1848 | 790 | 2026-02-20 13:39:43 |
| 11002 | 0EACE1D8-97FC-4C9B-87CD-D1826B224B15 | 5000 | 5 | 0.9999997444123878 | [{"name": "PC1", "type": "variance_ratio", "value": 0.7301259683363418, "cumulative": 0.730125968... | pca_fit | 1848 | 790 | 2026-02-20 13:36:18 |
| 11001 | 01CE2248-C8AF-4A56-94C5-0AE6E66B28D0 | 5010 | 5 | 0.9856713143839054 | [{"name": "PC1", "type": "variance_ratio", "value": 0.7115981618094107, "cumulative": 0.711598161... | pca_fit | 5369 | 790 | 2026-02-20 13:35:20 |
| 11000 | AFF0599E-29D4-4520-8DB4-3BD7CAF4AB5E | 5000 | 5 | 0.9999997444123878 | [{"name": "PC1", "type": "variance_ratio", "value": 0.7301259683363418, "cumulative": 0.730125968... | pca_fit | 1848 | 790 | 2026-02-20 13:32:52 |
| 10999 | 404D97D6-230F-43C6-913F-EC0D799E4BC6 | 5010 | 5 | 0.9856713143839054 | [{"name": "PC1", "type": "variance_ratio", "value": 0.7115981618094107, "cumulative": 0.711598161... | pca_fit | 5307 | 790 | 2026-02-20 13:30:20 |
| 10998 | 8D4519CD-86CA-4D65-9CC3-07B3AE05B223 | 5000 | 5 | 0.9999997444123878 | [{"name": "PC1", "type": "variance_ratio", "value": 0.7301259683363418, "cumulative": 0.730125968... | pca_fit | 1834 | 790 | 2026-02-20 13:29:23 |
| 10997 | B9C1087C-33D4-4350-B158-6ED21F66CE31 | 5000 | 5 | 0.9999997444123878 | [{"name": "PC1", "type": "variance_ratio", "value": 0.7301259683363418, "cumulative": 0.730125968... | pca_fit | 1831 | 790 | 2026-02-20 13:25:55 |
| 10996 | 9146A69A-7D32-4CEB-A2C6-8EC02A9A0119 | 5010 | 5 | 0.9856713143839054 | [{"name": "PC1", "type": "variance_ratio", "value": 0.7115981618094107, "cumulative": 0.711598161... | pca_fit | 5382 | 790 | 2026-02-20 13:25:12 |
| 10995 | B26FCAE5-217F-4FCF-92DC-18EE489A7C8B | 5000 | 5 | 0.9999997444123878 | [{"name": "PC1", "type": "variance_ratio", "value": 0.7301259683363418, "cumulative": 0.730125968... | pca_fit | 1764 | 790 | 2026-02-20 13:22:27 |
| 10994 | 6EECE164-3196-4815-80A5-15DF9A07D39D | 5010 | 5 | 0.9856713143839054 | [{"name": "PC1", "type": "variance_ratio", "value": 0.7115981618094107, "cumulative": 0.711598161... | pca_fit | 5361 | 790 | 2026-02-20 13:20:17 |

---


## dbo.ACM_PCA_Models

**Primary Key:** ID  
**Row Count:** 68  
**Date Range:** 2026-01-19 16:20:06 to 2026-02-20 19:09:37  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| ModelVersion | int | NO | 10 | ((1)) |
| NComponents | int | NO | 10 | — |
| ExplainedVarianceRatio | float | YES | 53 | — |
| TrainSamples | int | YES | 10 | — |
| TrainFeatures | int | YES | 10 | — |
| ScalerMeanJson | nvarchar | YES | -1 | — |
| ScalerScaleJson | nvarchar | YES | -1 | — |
| ComponentsJson | nvarchar | YES | -1 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

### Top 10 Records

| ID | RunID | EquipID | ModelVersion | NComponents | ExplainedVarianceRatio | TrainSamples | TrainFeatures | ScalerMeanJson | ScalerScaleJson |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 22 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 10 | 5 | 0.9999999991060334 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 23 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 10 | 5 | 0.9999999991060334 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 26 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | 10 | 5 | 0.9772128494046145 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 27 | 496202D1-C512-4D13-93B6-8AD2F15E7C24 | 8632 | 10 | 5 | 0.9984694256613802 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 29 | C2CFA54F-FB33-4F66-8340-9A1A0DCEC544 | 8632 | 10 | 5 | 0.9850308412298165 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 31 | D80354E0-96F4-4A76-9F2A-C73F9C36F66F | 8632 | 10 | 5 | 0.9065275015432626 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 32 | 09E1E60F-7F6A-4C79-84CD-A752F45CAE94 | 8632 | 10 | 5 | 0.9558765322288089 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 35 | C2880E7A-EA1F-47CF-9883-370175810ED0 | 8632 | 10 | 5 | 0.8734165131529826 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 36 | E211FDF4-2C57-4DD6-8AAE-F0E0802F21F8 | 8632 | 10 | 5 | 0.9354914302853435 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 45 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 10 | 5 | 0.8803694555756729 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |

### Bottom 10 Records

| ID | RunID | EquipID | ModelVersion | NComponents | ExplainedVarianceRatio | TrainSamples | TrainFeatures | ScalerMeanJson | ScalerScaleJson |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10651 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 10 | 5 | 0.9999997444123878 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10650 | 0EACE1D8-97FC-4C9B-87CD-D1826B224B15 | 5000 | 10 | 5 | 0.9999997444123878 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10649 | 01CE2248-C8AF-4A56-94C5-0AE6E66B28D0 | 5010 | 10 | 5 | 0.9856713143839054 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10648 | AFF0599E-29D4-4520-8DB4-3BD7CAF4AB5E | 5000 | 10 | 5 | 0.9999997444123878 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10647 | 404D97D6-230F-43C6-913F-EC0D799E4BC6 | 5010 | 10 | 5 | 0.9856713143839054 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10646 | 8D4519CD-86CA-4D65-9CC3-07B3AE05B223 | 5000 | 10 | 5 | 0.9999997444123878 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10645 | B9C1087C-33D4-4350-B158-6ED21F66CE31 | 5000 | 10 | 5 | 0.9999997444123878 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10644 | 9146A69A-7D32-4CEB-A2C6-8EC02A9A0119 | 5010 | 10 | 5 | 0.9856713143839054 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10643 | B26FCAE5-217F-4FCF-92DC-18EE489A7C8B | 5000 | 10 | 5 | 0.9999997444123878 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10642 | 6EECE164-3196-4815-80A5-15DF9A07D39D | 5010 | 10 | 5 | 0.9856713143839054 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |

---


## dbo.ACM_RUL

**Primary Key:** EquipID, RunID  
**Row Count:** 52  
**Date Range:** 2026-01-19 18:14:31 to 2026-02-26 11:25:19  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EquipID | int | NO | 10 | — |
| RunID | uniqueidentifier | NO | — | — |
| RUL_Hours | float | NO | 53 | — |
| P10_LowerBound | float | YES | 53 | — |
| P50_Median | float | YES | 53 | — |
| P90_UpperBound | float | YES | 53 | — |
| Confidence | float | YES | 53 | — |
| FailureTime | datetime2 | YES | — | — |
| Method | nvarchar | NO | 50 | ('MonteCarlo') |
| NumSimulations | int | YES | 10 | — |
| TopSensor1 | nvarchar | YES | 255 | — |
| TopSensor2 | nvarchar | YES | 255 | — |
| TopSensor3 | nvarchar | YES | 255 | — |
| CreatedAt | datetime2 | NO | — | (getdate()) |
| DriftZ | float | YES | 53 | — |
| CurrentRegime | int | YES | 10 | — |
| RegimeState | nvarchar | YES | 32 | — |
| OMR_Z | float | YES | 53 | — |
| RUL_Status | nvarchar | YES | 50 | — |
| MaturityState | nvarchar | YES | 50 | — |
| MeanRUL | float | YES | 53 | — |
| StdRUL | float | YES | 53 | — |
| MTTF_Hours | float | YES | 53 | — |
| FailureProbability | float | YES | 53 | — |
| CurrentHealth | float | YES | 53 | — |
| HealthLevel | nvarchar | YES | 50 | — |
| TrendSlope | float | YES | 53 | — |
| DataQuality | nvarchar | YES | 50 | — |
| ForecastStd | float | YES | 53 | — |
| TopSensor1Contribution | float | YES | 53 | — |
| TopSensor2Contribution | float | YES | 53 | — |
| TopSensor3Contribution | float | YES | 53 | — |
| ID | bigint | NO | 19 | — |

### Top 10 Records

| EquipID | RunID | RUL_Hours | P10_LowerBound | P50_Median | P90_UpperBound | Confidence | FailureTime | Method | NumSimulations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 5A655C74-6986-4BEE-B1FB-241F24203F01 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 11:08:04 | Multipath | 1000 |
| 1 | 0E76E9C9-6D37-43A6-BBF0-61C46E1F4FE3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 11:15:11 | Multipath | 1000 |
| 1 | 1361CADB-62B9-4E8B-92C8-65FCB8446BBB | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 11:11:34 | Multipath | 1000 |
| 1 | 2D3BF2C5-0C40-410D-B58F-88CFDFEE4808 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 11:18:44 | Multipath | 1000 |
| 1 | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 11:31:00 | Multipath | 1000 |
| 1 | 651A10EA-534E-428E-84D4-95B553CDBC1E | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 11:22:05 | Multipath | 1000 |
| 1 | DC657641-AA25-4A95-A9F4-AB863592A687 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 11:04:50 | Multipath | 1000 |
| 1 | 1301FC10-8521-477B-98CA-B57E744986B1 | 168.0 | 0.9702967484240079 | 168.0 | 172.99014626476665 | 0.1 | 2026-02-26 11:25:19 | Multipath | 1000 |
| 1 | AD3D7248-F140-44C6-8223-C63B4C512B12 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 11:28:18 | Multipath | 1000 |
| 1 | 2488646C-6A91-4C84-9BD9-DFE360765AF5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.3 | 2026-02-19 11:01:40 | Multipath | 1000 |

### Bottom 10 Records

| EquipID | RunID | RUL_Hours | P10_LowerBound | P50_Median | P90_UpperBound | Confidence | FailureTime | Method | NumSimulations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8635 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 168.0 | 163.00985373523335 | 168.0 | 172.99014626476665 | 0.3 | 2026-01-26 18:26:35 | Multipath | 1000 |
| 8632 | E211FDF4-2C57-4DD6-8AAE-F0E0802F21F8 | 4.2 | 3.5399659705002557 | 4.2 | 4.753796678109163 | 0.3 | 2026-01-19 20:59:28 | Multipath | 1000 |
| 8632 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 168.0 | 163.00985373523335 | 168.0 | 172.99014626476665 | 0.3 | 2026-01-26 16:19:56 | Multipath | 1000 |
| 8632 | D80354E0-96F4-4A76-9F2A-C73F9C36F66F | 1.6333333333333333 | 1.423101897688545 | 1.6333333333333333 | 1.8363041319771856 | 0.3 | 2026-01-19 18:14:31 | Multipath | 1000 |
| 8632 | 09E1E60F-7F6A-4C79-84CD-A752F45CAE94 | 168.0 | 163.00985373523335 | 168.0 | 172.99014626476665 | 0.3 | 2026-01-26 16:39:55 | Multipath | 1000 |
| 8632 | 496202D1-C512-4D13-93B6-8AD2F15E7C24 | 168.0 | 163.00985373523335 | 168.0 | 172.99014626476665 | 0.3 | 2026-01-26 16:29:37 | Multipath | 1000 |
| 8632 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 168.0 | 163.00985373523335 | 168.0 | 172.99014626476665 | 0.3 | 2026-01-26 16:22:27 | Multipath | 1000 |
| 8632 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 168.0 | 163.00985373523335 | 168.0 | 172.99014626476665 | 0.3 | 2026-01-26 16:25:37 | Multipath | 1000 |
| 5073 | AF435408-E910-48A8-B7A7-FB7D927517DA | 168.0 | 163.00985373523335 | 168.0 | 172.99014626476665 | 0.6802992460187132 | 2026-02-23 15:36:32 | Multipath | 1000 |
| 5073 | 471B19A1-2521-40B7-A20B-F9C2C6950D96 | 168.0 | 163.00985373523335 | 168.0 | 172.99014626476665 | 0.6802992460187132 | 2026-02-23 15:37:42 | Multipath | 1000 |

---


## dbo.ACM_RefitRequests

**Primary Key:** RequestID  
**Row Count:** 68  
**Date Range:** 2026-01-19 10:49:23 to 2026-02-20 19:08:50  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RequestID | int | NO | 10 | — |
| EquipID | int | NO | 10 | — |
| RequestedAt | datetime2 | NO | — | (sysutcdatetime()) |
| Reason | nvarchar | YES | -1 | — |
| AnomalyRate | float | YES | 53 | — |
| DriftScore | float | YES | 53 | — |
| ModelAgeHours | float | YES | 53 | — |
| RegimeQuality | float | YES | 53 | — |
| Acknowledged | bit | NO | — | ((0)) |
| AcknowledgedAt | datetime2 | YES | — | — |

### Top 10 Records

| RequestID | EquipID | RequestedAt | Reason | AnomalyRate | DriftScore | ModelAgeHours | RegimeQuality | Acknowledged | AcknowledgedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 32 | 8632 | 2026-01-19 10:49:23 | Anomaly rate too high; Silhouette score too low; anomaly_rate=29.88% > 25.00% | 0.2987551867219917 | NULL | NULL | 0.0 | True | 2026-01-19 10:51:01 |
| 33 | 8632 | 2026-01-19 10:51:55 | Anomaly rate too high; Silhouette score too low; anomaly_rate=29.88% > 25.00% | 0.2987551867219917 | NULL | NULL | 0.0 | True | 2026-01-19 10:53:30 |
| 36 | 8632 | 2026-01-19 10:54:28 | Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-01-19 10:56:45 |
| 37 | 8632 | 2026-01-19 10:57:38 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-01-19 11:00:42 |
| 39 | 8632 | 2026-01-19 11:01:42 | Anomaly rate too high; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-01-19 11:03:58 |
| 41 | 8632 | 2026-01-19 11:05:00 | Anomaly rate too high; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-01-19 11:07:42 |
| 42 | 8632 | 2026-01-19 11:08:39 | Anomaly rate too high; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-01-19 11:11:04 |
| 45 | 8632 | 2026-01-19 11:12:04 | Anomaly rate too high; Silhouette score too low; anomaly_rate=25.56% > 25.00% | 0.25558659217877094 | NULL | NULL | 0.0 | True | 2026-01-19 11:14:42 |
| 46 | 8632 | 2026-01-19 11:15:50 | Anomaly rate too high; Silhouette score too low; anomaly_rate=29.19% > 25.00% | 0.2918994413407821 | NULL | NULL | 0.0 | True | 2026-01-21 14:04:11 |
| 55 | 8635 | 2026-01-19 12:55:38 | Anomaly rate too high; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-01-19 12:59:22 |

### Bottom 10 Records

| RequestID | EquipID | RequestedAt | Reason | AnomalyRate | DriftScore | ModelAgeHours | RegimeQuality | Acknowledged | AcknowledgedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 605 | 5000 | 2026-02-20 19:08:50 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-02-20 19:11:30 |
| 604 | 5000 | 2026-02-20 19:05:29 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-02-20 19:08:04 |
| 603 | 5010 | 2026-02-20 19:04:14 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | False | NULL |
| 602 | 5000 | 2026-02-20 19:01:59 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-02-20 19:04:42 |
| 601 | 5010 | 2026-02-20 18:59:12 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-02-20 19:02:52 |
| 600 | 5000 | 2026-02-20 18:58:30 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-02-20 19:01:13 |
| 599 | 5000 | 2026-02-20 18:55:03 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-02-20 18:57:44 |
| 598 | 5010 | 2026-02-20 18:54:06 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-02-20 18:57:49 |
| 597 | 5000 | 2026-02-20 18:51:38 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-02-20 18:54:16 |
| 596 | 5010 | 2026-02-20 18:49:09 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-02-20 18:52:46 |

---


## dbo.ACM_RegimeDefinitions

**Primary Key:** ID  
**Row Count:** 306  
**Date Range:** 2026-01-19 10:47:55 to 2026-02-20 13:42:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| EquipID | int | NO | 10 | — |
| RegimeVersion | int | NO | 10 | — |
| RegimeID | int | NO | 10 | — |
| RegimeName | nvarchar | NO | 100 | — |
| CentroidJSON | nvarchar | NO | -1 | — |
| FeatureColumns | nvarchar | NO | -1 | — |
| DataPointCount | int | NO | 10 | — |
| SilhouetteScore | float | YES | 53 | — |
| MaturityState | nvarchar | YES | 30 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |
| RunID | nvarchar | YES | 50 | — |

### Top 10 Records

| ID | EquipID | RegimeVersion | RegimeID | RegimeName | CentroidJSON | FeatureColumns | DataPointCount | SilhouetteScore | MaturityState |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 110 | 8632 | 1 | 0 | Regime_0 | [0.948499785301586, 0.9552237543794844, 0.8738549309730944] | [] | 180 | NULL | LEARNING |
| 111 | 8632 | 1 | 1 | Regime_1 | [-0.9118687691895858, -0.9644612864307736, -0.7803304972855941] | [] | 46 | NULL | LEARNING |
| 112 | 8632 | 1 | 2 | Regime_2 | [-1.2726918048545963, -1.2925520627225031, -1.1799565143272526] | [] | 61 | NULL | LEARNING |
| 119 | 8632 | 1 | 0 | Regime_0 | [0.948499785301586, 0.9552237543794844, 0.8738549309730944] | [] | 180 | NULL | LEARNING |
| 120 | 8632 | 1 | 1 | Regime_1 | [-0.9118687691895858, -0.9644612864307736, -0.7803304972855941] | [] | 46 | NULL | LEARNING |
| 121 | 8632 | 1 | 2 | Regime_2 | [-1.2726918048545963, -1.2925520627225031, -1.1799565143272526] | [] | 61 | NULL | LEARNING |
| 128 | 8632 | 1 | 0 | Regime_0 | [0.0, 2.7324802684783935, 1.8926220631599426] | [] | 50 | NULL | LEARNING |
| 129 | 8632 | 1 | 1 | Regime_1 | [0.0, -0.8308982849121094, -1.6683903472764152] | [] | 70 | NULL | LEARNING |
| 130 | 8632 | 1 | 2 | Regime_2 | [0.0, -0.8308982849121094, -2.0916311780611676] | [] | 30 | NULL | LEARNING |
| 131 | 8632 | 1 | 3 | Regime_3 | [0.0, 1.484239833171551, 1.3057178735733033] | [] | 65 | NULL | LEARNING |

### Bottom 10 Records

| ID | EquipID | RegimeVersion | RegimeID | RegimeName | CentroidJSON | FeatureColumns | DataPointCount | SilhouetteScore | MaturityState |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1575 | 5000 | 0 | 5 | Regime_5 | [-1.1847483831293442, -1.2710348063824224, -0.9581021269162496, -0.6632413379117554, -0.848247958... | ["power_29_avg", "power_29_max", "power_29_min", "power_29_std", "power_30_avg", "power_30_max", ... | 51 | 0.3604093581658322 | LEARNING |
| 1574 | 5000 | 0 | 4 | Regime_4 | [-1.2776317172580296, -1.1967499997880724, -1.1613041158075685, -0.18823861533741432, -0.98169643... | ["power_29_avg", "power_29_max", "power_29_min", "power_29_std", "power_30_avg", "power_30_max", ... | 135 | 0.3604093581658322 | LEARNING |
| 1573 | 5000 | 0 | 3 | Regime_3 | [-0.7280665743467095, -0.5499734071328293, -0.6849720618361003, 0.13958287826820895, -0.336081371... | ["power_29_avg", "power_29_max", "power_29_min", "power_29_std", "power_30_avg", "power_30_max", ... | 154 | 0.3604093581658322 | LEARNING |
| 1572 | 5000 | 0 | 2 | Regime_2 | [-1.1912176636478784, -1.3545813398897801, -1.0758836371514497, -0.722798644962823, -1.0808550252... | ["power_29_avg", "power_29_max", "power_29_min", "power_29_std", "power_30_avg", "power_30_max", ... | 391 | 0.3604093581658322 | LEARNING |
| 1571 | 5000 | 0 | 1 | Regime_1 | [0.8953612930874769, 0.878133013385262, 0.8247231340490941, 0.22391354911031103, 1.04437560334754... | ["power_29_avg", "power_29_max", "power_29_min", "power_29_std", "power_30_avg", "power_30_max", ... | 941 | 0.3604093581658322 | LEARNING |
| 1570 | 5000 | 0 | 0 | Regime_0 | [0.773748241008094, 0.7502562434316795, 0.7396146740256286, 0.07784502328564978, -0.9603771525565... | ["power_29_avg", "power_29_max", "power_29_min", "power_29_std", "power_30_avg", "power_30_max", ... | 214 | 0.3604093581658322 | LEARNING |
| 1569 | 5000 | 0 | 5 | Regime_5 | [-1.1847483831293442, -1.2710348063824224, -0.9581021269162496, -0.6632413379117554, -0.848247958... | ["power_29_avg", "power_29_max", "power_29_min", "power_29_std", "power_30_avg", "power_30_max", ... | 51 | 0.3604093581658322 | LEARNING |
| 1568 | 5000 | 0 | 4 | Regime_4 | [-1.2776317172580296, -1.1967499997880724, -1.1613041158075685, -0.18823861533741432, -0.98169643... | ["power_29_avg", "power_29_max", "power_29_min", "power_29_std", "power_30_avg", "power_30_max", ... | 135 | 0.3604093581658322 | LEARNING |
| 1567 | 5000 | 0 | 3 | Regime_3 | [-0.7280665743467095, -0.5499734071328293, -0.6849720618361003, 0.13958287826820895, -0.336081371... | ["power_29_avg", "power_29_max", "power_29_min", "power_29_std", "power_30_avg", "power_30_max", ... | 154 | 0.3604093581658322 | LEARNING |
| 1566 | 5000 | 0 | 2 | Regime_2 | [-1.1912176636478784, -1.3545813398897801, -1.0758836371514497, -0.722798644962823, -1.0808550252... | ["power_29_avg", "power_29_max", "power_29_min", "power_29_std", "power_30_avg", "power_30_max", ... | 391 | 0.3604093581658322 | LEARNING |

---


## dbo.ACM_RegimeOccupancy

**Primary Key:** ID  
**Row Count:** 314  
**Date Range:** 2026-01-19 10:47:56 to 2026-02-20 13:42:01  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | nvarchar | NO | 50 | — |
| EquipID | int | NO | 10 | — |
| RegimeLabel | nvarchar | NO | 50 | — |
| DwellTimeHours | float | NO | 53 | — |
| DwellFraction | float | NO | 53 | — |
| EntryCount | int | YES | 10 | — |
| AvgDwellMinutes | float | YES | 53 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |

### Top 10 Records

| ID | RunID | EquipID | RegimeLabel | DwellTimeHours | DwellFraction | EntryCount | AvgDwellMinutes | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 138 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | 0 | 146.0 | 0.6058091286307054 | NULL | NULL | 2026-01-19 10:47:56 |
| 139 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | 2 | 68.0 | 0.2821576763485477 | NULL | NULL | 2026-01-19 10:47:56 |
| 140 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | 1 | 27.0 | 0.11203319502074689 | NULL | NULL | 2026-01-19 10:47:56 |
| 146 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | 0 | 146.0 | 0.6058091286307054 | NULL | NULL | 2026-01-19 10:51:34 |
| 147 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | 2 | 68.0 | 0.2821576763485477 | NULL | NULL | 2026-01-19 10:51:34 |
| 148 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | 1 | 27.0 | 0.11203319502074689 | NULL | NULL | 2026-01-19 10:51:34 |
| 154 | 3bb10529-b16e-4893-826b-73584fec01c8 | 8632 | 6 | 503.0 | 0.702513966480447 | NULL | NULL | 2026-01-19 10:54:11 |
| 155 | 3bb10529-b16e-4893-826b-73584fec01c8 | 8632 | 5 | 68.0 | 0.09497206703910614 | NULL | NULL | 2026-01-19 10:54:11 |
| 156 | 3bb10529-b16e-4893-826b-73584fec01c8 | 8632 | 3 | 51.0 | 0.0712290502793296 | NULL | NULL | 2026-01-19 10:54:11 |
| 157 | 3bb10529-b16e-4893-826b-73584fec01c8 | 8632 | 4 | 27.0 | 0.03770949720670391 | NULL | NULL | 2026-01-19 10:54:11 |

### Bottom 10 Records

| ID | RunID | EquipID | RegimeLabel | DwellTimeHours | DwellFraction | EntryCount | AvgDwellMinutes | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1648 | 9a0f444e-c812-45fc-b2a0-74e36cbdb29b | 5000 | 2 | 3.0 | 0.0016277807921866521 | NULL | NULL | 2026-02-20 13:42:01 |
| 1647 | 9a0f444e-c812-45fc-b2a0-74e36cbdb29b | 5000 | 0 | 891.0 | 0.4834508952794357 | NULL | NULL | 2026-02-20 13:42:01 |
| 1646 | 9a0f444e-c812-45fc-b2a0-74e36cbdb29b | 5000 | 5 | 949.0 | 0.5149213239283776 | NULL | NULL | 2026-02-20 13:42:01 |
| 1645 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 1 | 9.0 | 0.00487012987012987 | NULL | NULL | 2026-02-20 13:38:35 |
| 1644 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 2 | 23.0 | 0.012445887445887446 | NULL | NULL | 2026-02-20 13:38:35 |
| 1643 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 0 | 194.0 | 0.10497835497835498 | NULL | NULL | 2026-02-20 13:38:35 |
| 1642 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 5 | 1622.0 | 0.8777056277056277 | NULL | NULL | 2026-02-20 13:38:35 |
| 1641 | 0eace1d8-97fc-4c9b-87cd-d1826b224b15 | 5000 | 5 | 470.0 | 0.25432900432900435 | NULL | NULL | 2026-02-20 13:35:13 |
| 1640 | 0eace1d8-97fc-4c9b-87cd-d1826b224b15 | 5000 | 0 | 671.0 | 0.3630952380952381 | NULL | NULL | 2026-02-20 13:35:13 |
| 1639 | 0eace1d8-97fc-4c9b-87cd-d1826b224b15 | 5000 | 2 | 707.0 | 0.38257575757575757 | NULL | NULL | 2026-02-20 13:35:13 |

---


## dbo.ACM_RegimePromotionLog

**Primary Key:** ID  
**Row Count:** 2  
**Date Range:** 2026-02-12 19:22:29 to 2026-02-16 14:18:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | nvarchar | NO | 50 | — |
| EquipID | int | NO | 10 | — |
| RegimeLabel | nvarchar | NO | 50 | — |
| FromState | nvarchar | NO | 30 | — |
| ToState | nvarchar | NO | 30 | — |
| Reason | nvarchar | YES | 200 | — |
| DataPointsAtPromotion | int | YES | 10 | — |
| PromotedAt | datetime2 | NO | — | (getutcdate()) |

### Top 10 Records

| ID | RunID | EquipID | RegimeLabel | FromState | ToState | Reason | DataPointsAtPromotion | PromotedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | f3a31632-7341-45e5-ac7b-165608c75055 | 5014 | ALL | LEARNING | CONVERGED | met_promotion_criteria | NULL | 2026-02-12 19:22:29 |
| 15 | 67f4ea1e-839c-404d-a0f9-f0244f7c9ce0 | 5073 | ALL | LEARNING | CONVERGED | met_promotion_criteria | NULL | 2026-02-16 14:18:00 |

---


## dbo.ACM_RegimeState

**Primary Key:** EquipID, StateVersion  
**Row Count:** 10  
**Date Range:** 2026-01-19 11:15:21 to 2026-02-20 13:16:56  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EquipID | int | NO | 10 | — |
| StateVersion | int | NO | 10 | — |
| NumClusters | int | NO | 10 | — |
| ClusterCentersJson | nvarchar | YES | -1 | — |
| ScalerMeanJson | nvarchar | YES | -1 | — |
| ScalerScaleJson | nvarchar | YES | -1 | — |
| PCAComponentsJson | nvarchar | YES | -1 | — |
| PCAExplainedVarianceJson | nvarchar | YES | -1 | — |
| NumPCAComponents | int | NO | 10 | ((0)) |
| SilhouetteScore | float | YES | 53 | — |
| QualityOk | bit | NO | — | ((0)) |
| LastTrainedTime | datetime2 | NO | — | — |
| ConfigHash | nvarchar | YES | 64 | — |
| RegimeBasisHash | nvarchar | YES | 64 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

### Top 10 Records

| EquipID | StateVersion | NumClusters | ClusterCentersJson | ScalerMeanJson | ScalerScaleJson | PCAComponentsJson | PCAExplainedVarianceJson | NumPCAComponents | SilhouetteScore |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | [[-0.08694770807550455, -0.09141248766583249, -0.11219805674595142, -0.08987947218606339, -0.0755... | [] | [] | [] | [] | 0 | 0.40263278046615 |
| 2621 | 1 | 2 | [[-2.3927035908545218, -2.2698907544535976, -2.208915356666811, -2.495260569357103, -2.2201025485... | [] | [] | [] | [] | 0 | 0.3629990738412058 |
| 5000 | 1 | 6 | [[0.773748241008094, 0.7502562434316795, 0.7396146740256286, 0.07784502328564978, -0.960377152556... | [] | [] | [] | [] | 0 | 0.3604093581658322 |
| 5010 | 1 | 1 | [[-0.18974936322776845, -0.20610659920707092, -0.16402017478611333, -0.18101597766190602, -0.1881... | [] | [] | [] | [] | 0 | 0.32403123880160145 |
| 5013 | 1 | 1 | [[0.02366724705652279, 0.004787324942127966, 0.033540855823701025, -0.05247809441318489, 0.024372... | [] | [] | [] | [] | 0 | 0.46297012722095376 |
| 5014 | 1 | 1 | [[-0.20023603674552864, -0.2140056704724666, -0.17770929907437402, -0.21086075964598006, -0.19976... | [] | [] | [] | [] | 0 | 0.3435195568636159 |
| 5022 | 1 | 6 | [[0.1579588728662056, 0.07203454524278641, -0.582069956732879, 0.2650839024640961, 0.175274254362... | [] | [] | [] | [] | 0 | 13964.492082195597 |
| 5073 | 1 | 1 | [[-0.13235348313119744, -0.12717771616026602, -0.1262806180613999, -0.11270656806343875, -0.12995... | [] | [] | [] | [] | 0 | 0.3236908270493521 |
| 8632 | 1 | 4 | [[-1.2725832563492852, -1.2852776817266303, -1.2611694904838422], [1.0826237901397373, 0.80368454... | [] | [] | [] | [] | 0 | 0.31570874719918407 |
| 8635 | 1 | 149 | [[1.8034518665510186, 1.8035551232201859, 1.8032345950859299, 1.8034807627165266, -0.648410913382... | [] | [] | [] | [] | 0 | 0.5734027175979401 |

---


## dbo.ACM_RegimeTimeline

**Primary Key:** No primary key  
**Row Count:** 163,035  
**Date Range:** 2019-03-08 11:30:00 to 2025-09-14 23:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| Timestamp | datetime2 | NO | — | — |
| RegimeLabel | nvarchar | NO | 50 | — |
| RegimeState | nvarchar | NO | 50 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| AssignmentConfidence | float | YES | 53 | — |
| RegimeVersion | int | YES | 10 | — |
| ID | bigint | NO | 19 | — |
| IsNovel | bit | NO | — | ((0)) |

### Top 10 Records

| Timestamp | RegimeLabel | RegimeState | RunID | EquipID | AssignmentConfidence | RegimeVersion | ID | IsNovel |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2019-03-08 11:30:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360034 | False |
| 2019-03-08 12:00:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360035 | False |
| 2019-03-08 12:30:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360036 | False |
| 2019-03-08 13:00:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360037 | False |
| 2019-03-08 13:30:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360038 | False |
| 2019-03-08 14:00:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360039 | False |
| 2019-03-08 14:30:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360040 | False |
| 2019-03-08 15:00:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360041 | False |
| 2019-03-08 15:30:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360042 | False |
| 2019-03-08 16:00:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360043 | False |

### Bottom 10 Records

| Timestamp | RegimeLabel | RegimeState | RunID | EquipID | AssignmentConfidence | RegimeVersion | ID | IsNovel |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-09-14 23:00:00 | 0 | unknown | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 0.5 | NULL | 1195269 | True |
| 2025-09-14 22:30:00 | 0 | unknown | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 0.5 | NULL | 1195268 | True |
| 2025-09-14 22:00:00 | 0 | unknown | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 0.5 | NULL | 1195267 | True |
| 2025-09-14 21:30:00 | 0 | unknown | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 0.5 | NULL | 1195266 | True |
| 2025-09-14 21:00:00 | 0 | unknown | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 0.5 | NULL | 1195265 | True |
| 2025-09-14 20:30:00 | 0 | unknown | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 0.5 | NULL | 1195264 | True |
| 2025-09-14 20:00:00 | 0 | unknown | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 0.5 | NULL | 1195263 | True |
| 2025-09-14 19:30:00 | 0 | unknown | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 0.5 | NULL | 1195262 | True |
| 2025-09-14 19:00:00 | 0 | unknown | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 0.5 | NULL | 1195261 | True |
| 2025-09-14 18:30:00 | 0 | unknown | E4AB25D3-6F39-49CA-B617-8A7F353081B5 | 1 | 0.5 | NULL | 1195260 | True |

---


## dbo.ACM_RegimeTransitions

**Primary Key:** ID  
**Row Count:** 974  
**Date Range:** 2026-01-19 10:47:57 to 2026-02-20 13:42:02  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | nvarchar | NO | 50 | — |
| EquipID | int | NO | 10 | — |
| FromRegime | nvarchar | NO | 50 | — |
| ToRegime | nvarchar | NO | 50 | — |
| TransitionCount | int | NO | 10 | — |
| TransitionProbability | float | YES | 53 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |

### Top 10 Records

| ID | RunID | EquipID | FromRegime | ToRegime | TransitionCount | TransitionProbability | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 341 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | 2 | 1 | 4 | 0.6666666666666666 | 2026-01-19 10:47:57 |
| 342 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | 2 | 0 | 2 | 0.3333333333333333 | 2026-01-19 10:47:57 |
| 343 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | 1 | 2 | 5 | 0.8333333333333334 | 2026-01-19 10:47:57 |
| 344 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | 1 | 0 | 1 | 0.16666666666666666 | 2026-01-19 10:47:57 |
| 345 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | 0 | 1 | 2 | 0.6666666666666666 | 2026-01-19 10:47:57 |
| 346 | 248f1325-7537-4843-acfe-e559c458b2a9 | 8632 | 0 | 2 | 1 | 0.3333333333333333 | 2026-01-19 10:47:57 |
| 359 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | 2 | 1 | 4 | 0.6666666666666666 | 2026-01-19 10:51:35 |
| 360 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | 2 | 0 | 2 | 0.3333333333333333 | 2026-01-19 10:51:35 |
| 361 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | 1 | 2 | 5 | 0.8333333333333334 | 2026-01-19 10:51:35 |
| 362 | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | 8632 | 1 | 0 | 1 | 0.16666666666666666 | 2026-01-19 10:51:35 |

### Bottom 10 Records

| ID | RunID | EquipID | FromRegime | ToRegime | TransitionCount | TransitionProbability | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3025 | 9a0f444e-c812-45fc-b2a0-74e36cbdb29b | 5000 | 2 | 5 | 1 | 1.0 | 2026-02-20 13:42:02 |
| 3024 | 9a0f444e-c812-45fc-b2a0-74e36cbdb29b | 5000 | 0 | 5 | 19 | 1.0 | 2026-02-20 13:42:02 |
| 3023 | 9a0f444e-c812-45fc-b2a0-74e36cbdb29b | 5000 | 5 | 2 | 1 | 0.05 | 2026-02-20 13:42:02 |
| 3022 | 9a0f444e-c812-45fc-b2a0-74e36cbdb29b | 5000 | 5 | 0 | 19 | 0.95 | 2026-02-20 13:42:02 |
| 3021 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 1 | 0 | 1 | 0.2 | 2026-02-20 13:38:36 |
| 3020 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 1 | 5 | 4 | 0.8 | 2026-02-20 13:38:36 |
| 3019 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 2 | 0 | 3 | 0.6 | 2026-02-20 13:38:36 |
| 3018 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 2 | 5 | 2 | 0.4 | 2026-02-20 13:38:36 |
| 3017 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 0 | 2 | 1 | 0.04 | 2026-02-20 13:38:36 |
| 3016 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | 0 | 5 | 24 | 0.96 | 2026-02-20 13:38:36 |

---


## dbo.ACM_Regime_Episodes

**Primary Key:** ID  
**Row Count:** 0  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| RegimeLabel | int | NO | 10 | — |
| EpisodeStart | datetime2 | NO | — | — |
| EpisodeEnd | datetime2 | YES | — | — |
| DurationMinutes | float | YES | 53 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

---


## dbo.ACM_RunLogs

**Primary Key:** ID  
**Row Count:** 0  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | YES | — | — |
| EquipID | int | YES | 10 | — |
| LoggedAt | datetime2 | NO | — | (sysutcdatetime()) |
| Level | nvarchar | NO | 16 | — |
| Component | nvarchar | YES | 64 | — |
| Message | nvarchar | NO | -1 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

---


## dbo.ACM_RunMetadata

**Primary Key:** ID  
**Row Count:** 0  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| BatchNumber | int | YES | 10 | — |
| WindowStart | datetime2 | YES | — | — |
| WindowEnd | datetime2 | YES | — | — |
| RowsIn | int | YES | 10 | — |
| RowsOut | int | YES | 10 | — |
| ConfigSignature | nvarchar | YES | 64 | — |
| PipelineMode | nvarchar | YES | 32 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

---


## dbo.ACM_RunMetrics

**Primary Key:** ID  
**Row Count:** 1,026  
**Date Range:** 2026-01-22 09:47:11 to 2026-02-20 19:08:39  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| MetricName | nvarchar | NO | 128 | — |
| MetricValue | float | YES | 53 | — |
| MetricUnit | nvarchar | YES | 32 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

### Top 10 Records

| ID | RunID | EquipID | MetricName | MetricValue | MetricUnit | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- |
| 721 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | fusion.weight.ar1_z | 0.2 | NULL | 2026-01-22 09:47:11 |
| 722 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | fusion.weight.gmm_z | 0.05 | NULL | 2026-01-22 09:47:11 |
| 723 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | fusion.weight.iforest_z | 0.15 | NULL | 2026-01-22 09:47:11 |
| 724 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | fusion.weight.omr_z | 0.1 | NULL | 2026-01-22 09:47:11 |
| 725 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | fusion.weight.pca_spe_z | 0.3 | NULL | 2026-01-22 09:47:11 |
| 726 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | fusion.weight.pca_t2_z | 0.2 | NULL | 2026-01-22 09:47:11 |
| 727 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | fusion.quality.ar1_z | 0.0 | NULL | 2026-01-22 09:47:11 |
| 728 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | fusion.quality.gmm_z | 0.0 | NULL | 2026-01-22 09:47:11 |
| 729 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | fusion.quality.iforest_z | 0.0 | NULL | 2026-01-22 09:47:11 |
| 730 | DD255B8B-1A8F-4BBE-AAAE-8E8C9A7771AF | 5022 | fusion.quality.omr_z | 0.0 | NULL | 2026-01-22 09:47:11 |

### Bottom 10 Records

| ID | RunID | EquipID | MetricName | MetricValue | MetricUnit | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- |
| 8316 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | fusion.n_samples.pca_t2_z | 1848.0 | NULL | 2026-02-20 19:08:39 |
| 8315 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | fusion.n_samples.pca_spe_z | 1848.0 | NULL | 2026-02-20 19:08:39 |
| 8314 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | fusion.n_samples.omr_z | 1848.0 | NULL | 2026-02-20 19:08:39 |
| 8313 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | fusion.n_samples.iforest_z | 1848.0 | NULL | 2026-02-20 19:08:39 |
| 8312 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | fusion.n_samples.gmm_z | 1848.0 | NULL | 2026-02-20 19:08:39 |
| 8311 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | fusion.n_samples.ar1_z | 1848.0 | NULL | 2026-02-20 19:08:39 |
| 8310 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | fusion.quality.pca_t2_z | 0.0 | NULL | 2026-02-20 19:08:39 |
| 8309 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | fusion.quality.pca_spe_z | 0.0 | NULL | 2026-02-20 19:08:39 |
| 8308 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | fusion.quality.omr_z | 0.0 | NULL | 2026-02-20 19:08:39 |
| 8307 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | fusion.quality.iforest_z | 0.0 | NULL | 2026-02-20 19:08:39 |

---


## dbo.ACM_Run_Stats

**Primary Key:** RecordID  
**Row Count:** 68  
**Date Range:** 2018-12-01 00:00:00 to 2025-07-06 21:09:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RecordID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| WindowStartEntryDateTime | datetime2 | YES | — | — |
| WindowEndEntryDateTime | datetime2 | YES | — | — |
| SamplesIn | int | YES | 10 | — |
| SamplesKept | int | YES | 10 | — |
| SensorsKept | int | YES | 10 | — |
| CadenceOKPct | float | YES | 53 | — |
| DriftP95 | float | YES | 53 | — |
| ReconRMSE | float | YES | 53 | — |
| AnomalyCount | int | YES | 10 | — |
| CreatedAt | datetime2 | YES | — | (getdate()) |

### Top 10 Records

| RecordID | RunID | EquipID | WindowStartEntryDateTime | WindowEndEntryDateTime | SamplesIn | SamplesKept | SensorsKept | CadenceOKPct | DriftP95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 248F1325-7537-4843-ACFE-E559C458B2A9 | 8632 | 2024-01-01 00:00:00 | 2024-01-01 23:59:59 | 241 | 241 | 4 | 0.0 | NULL |
| 32 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 2024-01-02 00:00:00 | 2024-01-02 23:59:59 | 241 | 241 | 4 | 0.0 | NULL |
| 35 | 3BB10529-B16E-4893-826B-73584FEC01C8 | 8632 | 2024-01-03 00:00:00 | 2024-01-03 23:59:59 | 716 | 716 | 4 | 100.0 | NULL |
| 36 | 496202D1-C512-4D13-93B6-8AD2F15E7C24 | 8632 | 2024-01-04 00:00:00 | 2024-01-04 23:59:59 | 716 | 716 | 4 | 100.0 | NULL |
| 38 | C2CFA54F-FB33-4F66-8340-9A1A0DCEC544 | 8632 | 2024-01-05 00:00:00 | 2024-01-05 23:59:59 | 716 | 716 | 4 | 100.0 | NULL |
| 40 | D80354E0-96F4-4A76-9F2A-C73F9C36F66F | 8632 | 2024-01-06 00:00:00 | 2024-01-06 23:59:59 | 716 | 716 | 4 | 100.0 | NULL |
| 41 | 09E1E60F-7F6A-4C79-84CD-A752F45CAE94 | 8632 | 2024-01-07 00:00:00 | 2024-01-07 23:59:59 | 716 | 716 | 4 | 100.0 | NULL |
| 44 | C2880E7A-EA1F-47CF-9883-370175810ED0 | 8632 | 2024-01-08 00:00:00 | 2024-01-08 23:59:59 | 716 | 716 | 4 | 100.0 | NULL |
| 45 | E211FDF4-2C57-4DD6-8AAE-F0E0802F21F8 | 8632 | 2024-01-09 00:00:00 | 2024-01-09 23:59:59 | 716 | 716 | 4 | 100.0 | NULL |
| 54 | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 2018-12-01 00:00:00 | 2019-05-12 11:03:59 | 3120 | 3120 | 14 | 0.0 | NULL |

### Bottom 10 Records

| RecordID | RunID | EquipID | WindowStartEntryDateTime | WindowEndEntryDateTime | SamplesIn | SamplesKept | SensorsKept | CadenceOKPct | DriftP95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10660 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 2023-01-05 06:10:00 | 2023-01-30 22:09:59 | 1848 | 1848 | 79 | 100.0 | NULL |
| 10659 | 0EACE1D8-97FC-4C9B-87CD-D1826B224B15 | 5000 | 2022-12-10 14:10:00 | 2023-01-05 06:09:59 | 1848 | 1848 | 79 | 100.0 | NULL |
| 10658 | 01CE2248-C8AF-4A56-94C5-0AE6E66B28D0 | 5010 | 2023-08-04 13:28:00 | 2023-10-18 08:39:59 | 5369 | 5369 | 79 | 100.0 | NULL |
| 10657 | AFF0599E-29D4-4520-8DB4-3BD7CAF4AB5E | 5000 | 2022-11-14 22:10:00 | 2022-12-10 14:09:59 | 1848 | 1848 | 79 | 100.0 | NULL |
| 10656 | 404D97D6-230F-43C6-913F-EC0D799E4BC6 | 5010 | 2023-05-21 18:16:00 | 2023-08-04 13:27:59 | 5308 | 5308 | 79 | 100.0 | NULL |
| 10655 | 8D4519CD-86CA-4D65-9CC3-07B3AE05B223 | 5000 | 2022-10-20 06:10:00 | 2022-11-14 22:09:59 | 1834 | 1834 | 79 | 100.0 | NULL |
| 10654 | B9C1087C-33D4-4350-B158-6ED21F66CE31 | 5000 | 2022-09-24 14:10:00 | 2022-10-20 06:09:59 | 1832 | 1832 | 79 | 100.0 | NULL |
| 10653 | 9146A69A-7D32-4CEB-A2C6-8EC02A9A0119 | 5010 | 2023-03-07 23:04:00 | 2023-05-21 18:15:59 | 5383 | 5383 | 79 | 100.0 | NULL |
| 10652 | B26FCAE5-217F-4FCF-92DC-18EE489A7C8B | 5000 | 2022-08-29 22:10:00 | 2022-09-24 14:09:59 | 1765 | 1765 | 79 | 100.0 | NULL |
| 10651 | 6EECE164-3196-4815-80A5-15DF9A07D39D | 5010 | 2022-12-23 03:52:00 | 2023-03-07 23:03:59 | 5361 | 5361 | 79 | 100.0 | NULL |

---


## dbo.ACM_Runs

**Primary Key:** RunID  
**Row Count:** 77  
**Date Range:** 2026-01-19 10:47:02 to 2026-02-20 13:40:11  

### Schema

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
| ID | bigint | NO | 19 | — |

### Top 10 Records

| RunID | EquipID | EquipName | StartedAt | CompletedAt | DurationSeconds | ConfigSignature | TrainRowCount | ScoreRowCount | EpisodeCount |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8D4519CD-86CA-4D65-9CC3-07B3AE05B223 | 5000 | WFA_TURBINE_0 | 2026-02-20 13:26:23 | 2026-02-20 13:29:26 | 182 |  | 1834 | 3952 | 10 |
| B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C | 5073 | WFA_TURBINE_73 | 2026-02-16 08:32:39 | 2026-02-16 08:42:25 | 584 |  | 1809 | 3152 | 19 |
| 01CE2248-C8AF-4A56-94C5-0AE6E66B28D0 | 5010 | WFA_TURBINE_10 | 2026-02-20 13:31:02 | 2026-02-20 13:35:28 | 265 |  | 5369 | 3952 | 37 |
| B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2621 | GAS_Turbine | 2026-02-19 08:19:55 | 2026-02-19 08:22:34 | 158 |  | 89 | 642 | 2 |
| CB9C3AA5-411D-4730-A12A-10771C81D03D | 5014 | WFA_TURBINE_14 | 2026-02-12 14:02:48 | 2026-02-12 14:11:57 | 549 |  | 2706 | 3162 | 5 |
| C238BAB0-1834-486E-BDAF-11662D8EDEF9 | 2621 | GAS_Turbine | 2026-02-19 08:33:55 | 2026-02-19 08:33:55 | 0 |  | 0 | 0 | 0 |
| 426D1667-856F-4574-B325-148A97D172A0 | 5073 | WFA_TURBINE_73 | 2026-02-16 08:51:43 | 2026-02-16 09:03:27 | 703 |  | 2179 | 3152 | 22 |
| 1AB0A7D6-007C-458F-A0FB-1592B9C02695 | 5013 | WFA_TURBINE_13 | 2026-01-19 12:30:41 | 2026-01-19 12:33:01 | 139 |  | 0 | 0 | 0 |
| 6EECE164-3196-4815-80A5-15DF9A07D39D | 5010 | WFA_TURBINE_10 | 2026-02-20 13:15:44 | 2026-02-20 13:20:34 | 288 |  | 5361 | 3952 | 92 |
| F3A31632-7341-45E5-AC7B-165608C75055 | 5014 | WFA_TURBINE_14 | 2026-02-12 13:46:48 | 2026-02-12 14:02:11 | 918 |  | 2634 | 3162 | 27 |

### Bottom 10 Records

| RunID | EquipID | EquipName | StartedAt | CompletedAt | DurationSeconds | ConfigSignature | TrainRowCount | ScoreRowCount | EpisodeCount |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AF435408-E910-48A8-B7A7-FB7D927517DA | 5073 | WFA_TURBINE_73 | 2026-02-16 09:56:56 | 2026-02-16 10:07:00 | 603 |  | 2257 | 3162 | 1 |
| 471B19A1-2521-40B7-A20B-F9C2C6950D96 | 5073 | WFA_TURBINE_73 | 2026-02-16 10:07:32 | 2026-02-16 10:07:43 | 10 |  | 2257 | 3162 | 26 |
| E752AFBF-D494-4BB4-B865-F4FE4703EE97 | 5073 | WFA_TURBINE_73 | 2026-02-16 09:56:38 | 2026-02-16 09:56:49 | 11 |  | 2262 | 3162 | 24 |
| 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | WFA_TURBINE_0 | 2026-02-20 13:36:43 | 2026-02-20 13:39:46 | 181 |  | 1848 | 3952 | 8 |
| E211FDF4-2C57-4DD6-8AAE-F0E0802F21F8 | 8632 | WIND_TURBINE | 2026-01-19 11:14:27 | 2026-01-19 11:17:50 | 203 |  | 716 | 161 | 16 |
| 67F4EA1E-839C-404D-A0F9-F0244F7C9CE0 | 5073 | WFA_TURBINE_73 | 2026-02-16 08:43:13 | 2026-02-16 08:50:54 | 460 |  | 2262 | 3152 | 33 |
| 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | COND_PUMP_MOTOR | 2026-01-19 12:52:29 | 2026-01-19 12:57:08 | 278 |  | 3120 | 561 | 26 |
| 404D97D6-230F-43C6-913F-EC0D799E4BC6 | 5010 | WFA_TURBINE_10 | 2026-02-20 13:25:53 | 2026-02-20 13:30:37 | 283 |  | 5308 | 3952 | 91 |
| 6DE2F842-1E91-43EA-9376-EA40C0C42AD6 | 2621 | GAS_Turbine | 2026-02-19 08:33:43 | 2026-02-19 08:33:43 | 0 |  | 0 | 0 | 0 |
| 7FDC39ED-D4A5-415A-B7BA-E750CD7F1A07 | 5014 | WFA_TURBINE_14 | 2026-02-12 12:53:39 | 2026-02-12 13:03:54 | 614 |  | 2175 | 3162 | 4 |

---


## dbo.ACM_SchemaVersion

**Primary Key:** VersionID  
**Row Count:** 2  
**Date Range:** 2025-12-03 11:06:16 to 2025-12-03 11:06:16  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| VersionID | int | NO | 10 | — |
| VersionNumber | varchar | NO | 20 | — |
| Description | varchar | YES | 500 | — |
| AppliedAt | datetime2 | NO | — | (getutcdate()) |
| AppliedBy | varchar | NO | 100 | (suser_sname()) |

### Top 10 Records

| VersionID | VersionNumber | Description | AppliedAt | AppliedBy |
| --- | --- | --- | --- | --- |
| 1 | 1.0.0 | Initial ACM schema with core tables | 2025-12-03 11:06:16 | SYSTEM |
| 2 | 1.1.0 | Added ACM_SinceWhen and ACM_BaselineBuffer tables | 2025-12-03 11:06:16 | B19cl3pc\bhadk |

---


## dbo.ACM_Scores_Wide

**Primary Key:** No primary key  
**Row Count:** 163,035  
**Date Range:** 2019-03-08 11:30:00 to 2025-09-14 23:00:00  

### Schema

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
| ID | bigint | NO | 19 | — |
| omr_z | float | YES | 53 | — |

### Top 10 Records

| Timestamp | ar1_z | pca_spe_z | pca_t2_z | mhal_z | iforest_z | gmm_z | cusum_z | drift_z | hst_z |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2019-03-08 11:30:00 | -4.915918827056885 | 0.5677775144577026 | 5.556007385253906 | NULL | 1.4185539484024048 | 1.455339789390564 | -1.6657534837722778 | NULL | NULL |
| 2019-03-08 12:00:00 | 6.285232067108154 | 2.540839672088623 | 5.719286918640137 | NULL | 1.9063403606414795 | 4.999181270599365 | -1.6648991107940674 | NULL | NULL |
| 2019-03-08 12:30:00 | 3.8552751541137695 | 3.259634017944336 | 8.583819389343262 | NULL | 2.054279088973999 | 5.183332443237305 | -1.6633033752441406 | NULL | NULL |
| 2019-03-08 13:00:00 | 1.4135876893997192 | 1.023044466972351 | 5.766311168670654 | NULL | 1.6390749216079712 | 2.05597186088562 | -1.661797285079956 | NULL | NULL |
| 2019-03-08 13:30:00 | -0.6671119928359985 | 0.9975553154945374 | 5.685469150543213 | NULL | 1.6151043176651 | 1.944324016571045 | -1.6605300903320312 | NULL | NULL |
| 2019-03-08 14:00:00 | -0.5961621999740601 | 1.1556227207183838 | 5.9558186531066895 | NULL | 1.7234927415847778 | 2.194479465484619 | -1.6593852043151855 | NULL | NULL |
| 2019-03-08 14:30:00 | -1.1752383708953857 | 0.9891328811645508 | 5.380992412567139 | NULL | 1.4820927381515503 | 1.8163001537322998 | -1.6584398746490479 | NULL | NULL |
| 2019-03-08 15:00:00 | -0.806196928024292 | 1.2904822826385498 | 5.157268524169922 | NULL | 1.4928051233291626 | 1.9685007333755493 | -1.6575911045074463 | NULL | NULL |
| 2019-03-08 15:30:00 | -0.4940938949584961 | 1.523603081703186 | 5.398274898529053 | NULL | 1.332189917564392 | 2.361905336380005 | -1.656753659248352 | NULL | NULL |
| 2019-03-08 16:00:00 | -0.7767990827560425 | 1.3269500732421875 | 4.694003582000732 | NULL | 1.2735432386398315 | 2.0969417095184326 | -1.6560115814208984 | NULL | NULL |

### Bottom 10 Records

| Timestamp | ar1_z | pca_spe_z | pca_t2_z | mhal_z | iforest_z | gmm_z | cusum_z | drift_z | hst_z |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-09-14 23:00:00 | 1.1263951063156128 | -2.5521023273468018 | -1.3041017055511475 | NULL | -8.0 | -4.725759506225586 | 1.938767433166504 | NULL | NULL |
| 2025-09-14 22:30:00 | 1.3922604322433472 | -2.5521023273468018 | -1.3041017055511475 | NULL | -8.0 | -4.725759506225586 | 1.9379647970199585 | NULL | NULL |
| 2025-09-14 22:00:00 | 4.032149791717529 | -2.5521023273468018 | -1.3041017055511475 | NULL | -8.0 | -4.725759506225586 | 1.933273196220398 | NULL | NULL |
| 2025-09-14 21:30:00 | 3.7980754375457764 | -2.5521023273468018 | -1.3041017055511475 | NULL | -8.0 | -4.725759506225586 | 1.9239238500595093 | NULL | NULL |
| 2025-09-14 21:00:00 | 5.948091983795166 | -2.5521023273468018 | -1.3041017055511475 | NULL | -8.0 | -4.725759506225586 | 1.917624831199646 | NULL | NULL |
| 2025-09-14 20:30:00 | 1.6419620513916016 | -2.5521023273468018 | -1.3041017055511475 | NULL | -8.0 | -4.725759506225586 | 1.9142136573791504 | NULL | NULL |
| 2025-09-14 20:00:00 | 0.9681769013404846 | -2.5521023273468018 | -1.3041017055511475 | NULL | -8.0 | -4.725759506225586 | 1.92312490940094 | NULL | NULL |
| 2025-09-14 19:30:00 | 0.32974040508270264 | -2.5521023273468018 | -1.3041017055511475 | NULL | -8.0 | -4.725759506225586 | 1.9350764751434326 | NULL | NULL |
| 2025-09-14 19:00:00 | 1.7939090728759766 | -2.5521023273468018 | -1.3041017055511475 | NULL | -8.0 | -4.725759506225586 | 1.9480247497558594 | NULL | NULL |
| 2025-09-14 18:30:00 | 1.2450298070907593 | -2.5521023273468018 | -1.3041017055511475 | NULL | -8.0 | -4.725759506225586 | 1.9588963985443115 | NULL | NULL |

---


## dbo.ACM_SeasonalPatterns

**Primary Key:** ID  
**Row Count:** 2,754  
**Date Range:** 2026-01-19 18:26:03 to 2026-02-20 19:09:20  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| EquipID | int | NO | 10 | — |
| SensorName | nvarchar | NO | 200 | — |
| PatternType | nvarchar | NO | 30 | — |
| PeriodHours | float | NO | 53 | — |
| Amplitude | float | NO | 53 | — |
| PhaseShift | float | YES | 53 | — |
| Confidence | float | YES | 53 | — |
| DetectedAt | datetime2 | NO | — | (getutcdate()) |
| RunID | nvarchar | YES | 50 | — |

### Top 10 Records

| ID | EquipID | SensorName | PatternType | PeriodHours | Amplitude | PhaseShift | Confidence | DetectedAt | RunID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1853 | 8635 | JAVG_CURRENT_AVG | DAILY | 24.0 | 1.3147 | 15.0 | 0.732 | 2026-01-19 18:26:03 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a |
| 1854 | 8635 | JAVG_CURRENT_AVG | WEEKLY | 168.0 | 5.2059 | 39.0 | 0.199 | 2026-01-19 18:26:03 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a |
| 1855 | 8635 | JPH1_CURRENT_PH_A | DAILY | 24.0 | 1.305 | 15.0 | 0.7333 | 2026-01-19 18:26:03 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a |
| 1856 | 8635 | JPH1_CURRENT_PH_A | WEEKLY | 168.0 | 5.1691 | 135.0 | 0.2001 | 2026-01-19 18:26:03 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a |
| 1857 | 8635 | JPH2_CURRENT_PH_B | DAILY | 24.0 | 1.3444 | 15.0 | 0.7304 | 2026-01-19 18:26:03 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a |
| 1858 | 8635 | JPH2_CURRENT_PH_B | WEEKLY | 168.0 | 5.2537 | 135.0 | 0.1969 | 2026-01-19 18:26:03 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a |
| 1859 | 8635 | JPH3_CURRENT_PH_C | DAILY | 24.0 | 1.3247 | 15.0 | 0.7322 | 2026-01-19 18:26:03 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a |
| 1860 | 8635 | JPH3_CURRENT_PH_C | WEEKLY | 168.0 | 5.2206 | 69.0 | 0.2001 | 2026-01-19 18:26:03 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a |
| 1861 | 8635 | PF1_POWER_FACTOR | DAILY | 24.0 | 0.0132 | 16.0 | 0.2858 | 2026-01-19 18:26:03 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a |
| 1862 | 8635 | PWR1_POWER | DAILY | 24.0 | 8278.6875 | 15.0 | 0.7326 | 2026-01-19 18:26:03 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a |

### Bottom 10 Records

| ID | EquipID | SensorName | PatternType | PeriodHours | Amplitude | PhaseShift | Confidence | DetectedAt | RunID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 23228 | 5000 | wind_speed_4_avg | DAILY | 24.0 | 1.2212 | 9.0 | 0.2868 | 2026-02-20 19:09:20 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb |
| 23227 | 5000 | wind_speed_3_std | DAILY | 24.0 | 0.2378 | 8.0 | 0.3441 | 2026-02-20 19:09:20 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb |
| 23226 | 5000 | wind_speed_3_min | DAILY | 24.0 | 0.3154 | 14.0 | 0.157 | 2026-02-20 19:09:20 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb |
| 23225 | 5000 | wind_speed_3_max | DAILY | 24.0 | 3.4686 | 8.0 | 0.3503 | 2026-02-20 19:09:20 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb |
| 23224 | 5000 | wind_speed_3_avg | DAILY | 24.0 | 1.2071 | 9.0 | 0.2879 | 2026-02-20 19:09:20 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb |
| 23223 | 5000 | sensor_9_avg | DAILY | 24.0 | 2.9936 | 10.0 | 0.4837 | 2026-02-20 19:09:20 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb |
| 23222 | 5000 | sensor_8_avg | DAILY | 24.0 | 14.0962 | 11.0 | 0.303 | 2026-02-20 19:09:20 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb |
| 23221 | 5000 | sensor_7_avg | DAILY | 24.0 | 2.2756 | 11.0 | 0.4664 | 2026-02-20 19:09:20 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb |
| 23220 | 5000 | sensor_6_avg | DAILY | 24.0 | 3.2436 | 9.0 | 0.7263 | 2026-02-20 19:09:20 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb |
| 23219 | 5000 | sensor_5_min | DAILY | 24.0 | 5.5077 | 4.0 | 0.1703 | 2026-02-20 19:09:20 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb |

---


## dbo.ACM_SensorCorrelations

**Primary Key:** ID  
**Row Count:** 15,637  
**Date Range:** 2026-01-19 11:16:02 to 2026-02-20 13:39:09  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | nvarchar | NO | 50 | — |
| EquipID | int | NO | 10 | — |
| Sensor1 | nvarchar | NO | 200 | — |
| Sensor2 | nvarchar | NO | 200 | — |
| Correlation | float | NO | 53 | — |
| CorrelationType | nvarchar | YES | 20 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |

### Top 10 Records

| ID | RunID | EquipID | Sensor1 | Sensor2 | Correlation | CorrelationType | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 101430 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | LV_ActivePower | LV_ActivePower | 1.0 | pearson | 2026-01-19 11:16:02 |
| 101431 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | LV_ActivePower | Theoretical_Power_Curve | 0.9702838567737232 | pearson | 2026-01-19 11:16:02 |
| 101432 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | LV_ActivePower | Wind_Direction | 0.909036168066834 | pearson | 2026-01-19 11:16:02 |
| 101433 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | LV_ActivePower | Wind_Speed | 0.9721052940281959 | pearson | 2026-01-19 11:16:02 |
| 101434 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | Theoretical_Power_Curve | Theoretical_Power_Curve | 1.0 | pearson | 2026-01-19 11:16:02 |
| 101435 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | Theoretical_Power_Curve | Wind_Direction | 0.9420822452629578 | pearson | 2026-01-19 11:16:02 |
| 101436 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | Theoretical_Power_Curve | Wind_Speed | 0.913033698848238 | pearson | 2026-01-19 11:16:02 |
| 101437 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | Wind_Direction | Wind_Direction | 1.0 | pearson | 2026-01-19 11:16:02 |
| 101438 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | Wind_Direction | Wind_Speed | 0.8492377086721246 | pearson | 2026-01-19 11:16:02 |
| 101439 | e211fdf4-2c57-4dd6-8aae-f0e0802f21f8 | 8632 | Wind_Speed | Wind_Speed | 1.0 | pearson | 2026-01-19 11:16:02 |

### Bottom 10 Records

| ID | RunID | EquipID | Sensor1 | Sensor2 | Correlation | CorrelationType | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1736473 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | wind_speed_4_avg | wind_speed_4_avg | 1.0 | pearson | 2026-02-20 13:39:09 |
| 1736472 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | wind_speed_3_std | wind_speed_4_avg | 0.8666619362979279 | pearson | 2026-02-20 13:39:09 |
| 1736471 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | wind_speed_3_std | wind_speed_3_std | 1.0 | pearson | 2026-02-20 13:39:09 |
| 1736470 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | wind_speed_3_min | wind_speed_4_avg | 0.7592941698320155 | pearson | 2026-02-20 13:39:09 |
| 1736469 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | wind_speed_3_min | wind_speed_3_std | 0.47666885966212663 | pearson | 2026-02-20 13:39:09 |
| 1736468 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | wind_speed_3_min | wind_speed_3_min | 1.0 | pearson | 2026-02-20 13:39:09 |
| 1736467 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | wind_speed_3_max | wind_speed_4_avg | 0.737223625155797 | pearson | 2026-02-20 13:39:09 |
| 1736466 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | wind_speed_3_max | wind_speed_3_std | 0.8307263350974781 | pearson | 2026-02-20 13:39:09 |
| 1736465 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | wind_speed_3_max | wind_speed_3_min | 0.3643445638471594 | pearson | 2026-02-20 13:39:09 |
| 1736464 | 8dfe547b-f660-49c6-a8fb-f194e91d4dfb | 5000 | wind_speed_3_max | wind_speed_3_max | 1.0 | pearson | 2026-02-20 13:39:09 |

---


## dbo.ACM_SensorDefects

**Primary Key:** No primary key  
**Row Count:** 476  

### Schema

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
| ID | bigint | NO | 19 | — |

### Top 10 Records

| DetectorType | DetectorFamily | Severity | ViolationCount | ViolationPct | MaxZ | AvgZ | CurrentZ | ActiveDefect | RunID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Correlation Break (PCA-SPE) | Correlation | CRITICAL | 1834 | 100.0 | 8.0 | 8.0 | 8.0 | 1 | 8D4519CD-86CA-4D65-9CC3-07B3AE05B223 |
| Multivariate Outlier (PCA-T2) | Multivariate | CRITICAL | 1834 | 100.0 | 3.7957 | 3.7957 | 3.7957 | 1 | 8D4519CD-86CA-4D65-9CC3-07B3AE05B223 |
| Rare State (IsolationForest) | Rare | CRITICAL | 1834 | 100.0 | 8.0 | 8.0 | 8.0 | 1 | 8D4519CD-86CA-4D65-9CC3-07B3AE05B223 |
| Density Anomaly (GMM) | Density | CRITICAL | 1834 | 100.0 | 2.3027 | 2.3027 | 2.3027 | 1 | 8D4519CD-86CA-4D65-9CC3-07B3AE05B223 |
| Time-Series Anomaly (AR1) | Time-Series | CRITICAL | 1769 | 96.46 | 8.0 | 6.7368 | 8.0 | 1 | 8D4519CD-86CA-4D65-9CC3-07B3AE05B223 |
| Baseline Consistency (OMR) | Baseline | CRITICAL | 1545 | 84.24 | 6.8528 | 4.8251 | 6.8528 | 1 | 8D4519CD-86CA-4D65-9CC3-07B3AE05B223 |
| cusum_z | cusum_z | MEDIUM | 122 | 6.65 | 3.1106 | 0.8205 | 3.1106 | 1 | 8D4519CD-86CA-4D65-9CC3-07B3AE05B223 |
| Time-Series Anomaly (AR1) | Time-Series | CRITICAL | 1643 | 90.82 | 10.0 | 9.0513 | 10.0 | 1 | B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C |
| Multivariate Outlier (PCA-T2) | Multivariate | CRITICAL | 1615 | 89.28 | 10.0 | 5.5176 | 3.6223 | 1 | B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C |
| Correlation Break (PCA-SPE) | Correlation | CRITICAL | 1556 | 86.01 | 10.0 | 8.4448 | 10.0 | 1 | B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C |

### Bottom 10 Records

| DetectorType | DetectorFamily | Severity | ViolationCount | ViolationPct | MaxZ | AvgZ | CurrentZ | ActiveDefect | RunID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Rare State (IsolationForest) | Rare | CRITICAL | 2257 | 100.0 | 10.0 | 10.0 | 10.0 | 1 | AF435408-E910-48A8-B7A7-FB7D927517DA |
| Density Anomaly (GMM) | Density | CRITICAL | 2257 | 100.0 | 6.6964 | 6.6964 | 6.6964 | 1 | AF435408-E910-48A8-B7A7-FB7D927517DA |
| Baseline Consistency (OMR) | Baseline | CRITICAL | 968 | 42.89 | 5.4811 | 2.4419 | 0.8186 | 0 | AF435408-E910-48A8-B7A7-FB7D927517DA |
| cusum_z | cusum_z | CRITICAL | 690 | 30.57 | 7.5645 | 1.7377 | 7.5645 | 1 | AF435408-E910-48A8-B7A7-FB7D927517DA |
| Time-Series Anomaly (AR1) | Time-Series | MEDIUM | 175 | 7.75 | 10.0 | 1.0305 | 0.8286 | 0 | AF435408-E910-48A8-B7A7-FB7D927517DA |
| Multivariate Outlier (PCA-T2) | Multivariate | LOW | 0 | 0.0 | 1.3469 | 1.3469 | 1.3469 | 0 | AF435408-E910-48A8-B7A7-FB7D927517DA |
| Correlation Break (PCA-SPE) | Correlation | LOW | 0 | 0.0 | 1.6996 | 1.6996 | 1.6996 | 0 | AF435408-E910-48A8-B7A7-FB7D927517DA |
| Rare State (IsolationForest) | Rare | CRITICAL | 2257 | 100.0 | 10.0 | 10.0 | 10.0 | 1 | 471B19A1-2521-40B7-A20B-F9C2C6950D96 |
| Density Anomaly (GMM) | Density | CRITICAL | 2257 | 100.0 | 6.6964 | 6.6964 | 6.6964 | 1 | 471B19A1-2521-40B7-A20B-F9C2C6950D96 |
| Baseline Consistency (OMR) | Baseline | HIGH | 381 | 16.88 | 5.4811 | 1.1899 | 0.6292 | 0 | 471B19A1-2521-40B7-A20B-F9C2C6950D96 |

---


## dbo.ACM_SensorForecast

**Primary Key:** RunID, EquipID, Timestamp, SensorName  
**Row Count:** 71,400  
**Date Range:** 2019-05-12 10:30:00 to 2025-09-21 23:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | uniqueidentifier | NO | — | — |
| EquipID | int | NO | 10 | — |
| Timestamp | datetime2 | NO | — | — |
| SensorName | nvarchar | NO | 255 | — |
| ForecastValue | float | NO | 53 | — |
| CiLower | float | YES | 53 | — |
| CiUpper | float | YES | 53 | — |
| ForecastStd | float | YES | 53 | — |
| Method | nvarchar | NO | 50 | — |
| RegimeLabel | int | YES | 10 | — |
| CreatedAt | datetime2 | NO | — | (getdate()) |
| ID | bigint | NO | 19 | — |

### Top 10 Records

| RunID | EquipID | Timestamp | SensorName | ForecastValue | CiLower | CiUpper | ForecastStd | Method | RegimeLabel |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C | 5073 | 2022-07-08 21:00:00 | reactive_power_27_std | 0.07742499192040411 | -0.04315997733047984 | 0.19800996117128805 | 0.05892829242402089 | ExponentialSmoothing | 0 |
| B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C | 5073 | 2022-07-08 21:00:00 | reactive_power_28_std | 0.0778177737428676 | -0.03309337929604082 | 0.188728926781776 | 0.0542008253596185 | ExponentialSmoothing | 0 |
| B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C | 5073 | 2022-07-08 21:00:00 | sensor_18_std | 216.94860922281447 | 89.3233610856769 | 344.57385735995206 | 62.36878434878681 | ExponentialSmoothing | 0 |
| B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C | 5073 | 2022-07-08 21:00:00 | sensor_2_avg | -27.398987808291796 | -72.41614359921225 | 17.61816798262866 | 21.999293419611828 | ExponentialSmoothing | 0 |
| B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C | 5073 | 2022-07-08 21:00:00 | sensor_31_max | 302.22279130714963 | 46.156550023241834 | 558.2890325910574 | 125.13621258138186 | ExponentialSmoothing | 0 |
| B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C | 5073 | 2022-07-08 21:00:00 | sensor_31_min | -204.90943593466565 | -395.15447096080277 | -14.664400908528563 | 92.97025264329221 | ExponentialSmoothing | 0 |
| B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C | 5073 | 2022-07-08 21:00:00 | sensor_31_std | 78.28786209277052 | 38.88779242925357 | 117.68793175628747 | 19.254297124112767 | ExponentialSmoothing | 0 |
| B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C | 5073 | 2022-07-08 21:00:00 | sensor_5_min | 6.872308495705204 | -24.418115181664145 | 38.16273217307455 | 15.291219527495226 | ExponentialSmoothing | 0 |
| B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C | 5073 | 2022-07-08 21:00:00 | sensor_5_std | 6.550266507684202 | 3.6432853277435013 | 9.457247687624903 | 1.4206035636685719 | ExponentialSmoothing | 0 |
| B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C | 5073 | 2022-07-08 21:00:00 | sensor_52_std | 1.9504477121590458 | 0.7096214075775131 | 3.1912740167405786 | 0.6063755356744991 | ExponentialSmoothing | 0 |

### Bottom 10 Records

| RunID | EquipID | Timestamp | SensorName | ForecastValue | CiLower | CiUpper | ForecastStd | Method | RegimeLabel |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AF435408-E910-48A8-B7A7-FB7D927517DA | 5073 | 2023-02-20 18:00:00 | sensor_5_std | 2.4664640841947607 | -15.222840062607467 | 20.15576823099699 | 2.2478750093273963 | ExponentialSmoothing | 0 |
| AF435408-E910-48A8-B7A7-FB7D927517DA | 5073 | 2023-02-20 18:00:00 | sensor_47 | -781.5291785645746 | -2574.6349865721922 | 1011.5766294430429 | 227.85959817581488 | ExponentialSmoothing | 0 |
| AF435408-E910-48A8-B7A7-FB7D927517DA | 5073 | 2023-02-20 18:00:00 | sensor_41_avg | -56.10612594372181 | -75.9806785442058 | -36.23157334323781 | 2.525566282394832 | ExponentialSmoothing | 0 |
| AF435408-E910-48A8-B7A7-FB7D927517DA | 5073 | 2023-02-20 18:00:00 | sensor_40_avg | -47.708333431440295 | -92.22670784258253 | -3.189959020298062 | 5.657189252002164 | ExponentialSmoothing | 0 |
| AF435408-E910-48A8-B7A7-FB7D927517DA | 5073 | 2023-02-20 18:00:00 | sensor_39_avg | -68.80663284296747 | -113.43534072321602 | -24.177924962718933 | 5.671209919284393 | ExponentialSmoothing | 0 |
| AF435408-E910-48A8-B7A7-FB7D927517DA | 5073 | 2023-02-20 18:00:00 | sensor_26_avg | 50.0380718034033 | 49.99600204029233 | 50.080141566514264 | 0.005346031045690259 | ExponentialSmoothing | 0 |
| AF435408-E910-48A8-B7A7-FB7D927517DA | 5073 | 2023-02-20 18:00:00 | sensor_18_std | 770.7118088274703 | 274.8989921216783 | 1266.5246255332625 | 63.00560105291946 | ExponentialSmoothing | 0 |
| AF435408-E910-48A8-B7A7-FB7D927517DA | 5073 | 2023-02-20 18:00:00 | power_30_std | -0.6845524682616051 | -1.0488663609426716 | -0.32023857558053853 | 0.046295325588406176 | ExponentialSmoothing | 0 |
| AF435408-E910-48A8-B7A7-FB7D927517DA | 5073 | 2023-02-20 18:00:00 | power_30_min | -2.7854409776456976 | -3.721015830694588 | -1.849866124596807 | 0.11888852800939208 | ExponentialSmoothing | 0 |
| AF435408-E910-48A8-B7A7-FB7D927517DA | 5073 | 2023-02-20 18:00:00 | power_29_min | -2.7267692952381504 | -3.6834335290333735 | -1.7701050614429272 | 0.12156846903750998 | ExponentialSmoothing | 0 |

---


## dbo.ACM_SensorHotspots

**Primary Key:** No primary key  
**Row Count:** 1,225  
**Date Range:** 2019-03-08 20:30:00 to 2025-09-12 00:00:00  

### Schema

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
| FailureContribution | float | YES | 53 | — |
| ZScoreAtFailure | float | YES | 53 | — |
| AlertCount | int | YES | 10 | — |
| ID | bigint | NO | 19 | — |
| MaxAbsOMR | float | YES | 53 | — |
| RankingScore | float | YES | 53 | — |

### Top 10 Records

| SensorName | MaxTimestamp | LatestTimestamp | MaxAbsZ | MaxSignedZ | LatestAbsZ | LatestSignedZ | ValueAtPeak | LatestValue | TrainMean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| JPH3_CURRENT_PH_C | 2019-03-08 20:30:00 | 2019-05-12 11:00:00 | 4.2485 | -4.2485 | 0.3935 | 0.3935 | -6.423842930017303 | 49.77748518410861 | 45.01290458469124 |
| VTIBX_MOTOR_IB_BRG_VIB_X | 2019-03-08 20:30:00 | 2019-05-12 11:00:00 | 3.8288 | -3.8288 | 0.7338 | 0.7338 | -0.02028817744955037 | 0.17180542356708253 | 0.140912769978008 |
| VTOBY_MOTOR_OB_BRG_VIB_Y | 2019-03-08 22:00:00 | 2019-05-12 11:00:00 | 4.0753 | -4.0753 | 0.575 | 0.575 | -0.025816451518819554 | 0.19694190859651642 | 0.16939614495492009 |
| JPH1_CURRENT_PH_A | 2019-03-10 22:00:00 | 2019-05-12 11:00:00 | 4.219 | -4.219 | 0.1555 | 0.1555 | -5.99830525003829 | 46.53988304379406 | 44.672794667881206 |
| PWR1_POWER | 2019-03-10 22:00:00 | 2019-05-12 11:00:00 | 4.2128 | -4.2128 | 0.1211 | 0.1211 | -37980.66483106831 | 291966.393120181 | 282748.2139915821 |
| JPH2_CURRENT_PH_B | 2019-03-10 22:00:00 | 2019-05-12 11:00:00 | 4.1686 | -4.1686 | 0.1139 | 0.1139 | -6.11386923651885 | 46.54128040980959 | 45.14102953230049 |
| JAVG_CURRENT_AVG | 2019-03-20 22:00:00 | 2019-05-12 11:00:00 | 4.3762 | -4.3762 | 0.8376 | 0.8376 | -6.041446223585915 | 54.95484850020283 | 45.1554974452275 |
| PF1_POWER_FACTOR | 2019-03-27 12:30:00 | 2019-05-12 11:00:00 | 57.0834 | -57.0834 | 0.3007 | 0.3007 | -0.7039294791829935 | 0.8858850329059698 | 0.8775555538522848 |
| VTOBX_MOTOR_OB_BRG_VIB_X | 2019-03-31 23:30:00 | 2019-05-12 11:00:00 | 3.6662 | -3.6662 | 0.1573 | 0.1573 | -0.021214335297639407 | 0.1536575568851214 | 0.14646330152301043 |
| TIPH1_WINDING_TEMP_A | 2019-04-02 23:00:00 | 2019-05-12 11:00:00 | 5.7357 | -5.7357 | 0.6446 | 0.6446 | 55.685944571961635 | 132.07617680940118 | 124.3589872478183 |

### Bottom 10 Records

| SensorName | MaxTimestamp | LatestTimestamp | MaxAbsZ | MaxSignedZ | LatestAbsZ | LatestSignedZ | ValueAtPeak | LatestValue | TrainMean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEMO.SIM.06GP34_1FD Fan Outlet Pressure | 2025-09-12 00:00:00 | 2025-09-14 23:00:00 | 3.027 | 3.027 | 1.2832 | 1.2832 | 2.390000104904175 | 1.3300000429153442 | 0.550000011920929 |
| DEMO.SIM.FSAB_1FD Fan Right Inlet Flow | 2025-09-11 18:00:00 | 2025-09-14 23:00:00 | 3.605 | -3.605 | 1.6446 | 1.6446 | -58.28133592428182 | 405.40179443359375 | 260.13893536778664 |
| DEMO.SIM.FSAA_1FD Fan Left Inlet Flow | 2025-09-11 17:00:00 | 2025-09-14 23:00:00 | 3.3819 | -3.3819 | 1.4122 | 1.4122 | -63.029998779296875 | 383.5799865722656 | 252.02499389648438 |
| DEMO.SIM.06T32-1_1FD Fan Bearing Temperature | 2025-09-11 16:30:00 | 2025-09-14 23:00:00 | 10.2043 | -10.2043 | 1.0845 | 1.0845 | -0.1599999964237213 | 63.439998626708984 | 57.33000183105469 |
| DEMO.SIM.06T34_1FD Fan Outlet Termperature | 2025-09-11 15:30:00 | 2025-09-14 23:00:00 | 3.3103 | -3.3103 | 0.8268 | 0.8268 | 5.269999980926514 | 33.2400016784668 | 27.649999618530273 |
| DEMO.SIM.06T31_1FD Fan Inlet Temperature | 2025-09-11 15:00:00 | 2025-09-14 23:00:00 | 3.6422 | -3.6422 | 1.9395 | 1.9395 | 4.3516764640808105 | 48.44167709350586 | 33.121226169243926 |
| DEMO.SIM.06G31_1FD Fan Damper Position | 2025-09-11 07:00:00 | 2025-09-14 23:00:00 | 2.5014 | -2.5014 | 1.5311 | 1.5311 | -0.30247581005096436 | 48.581236839294434 | 30.0205256890997 |
| DEMO.SIM.06T33-1_1FD Fan Winding Temperature | 2025-09-11 04:00:00 | 2025-09-14 23:00:00 | 3.4426 | -3.4426 | 1.5794 | 1.5794 | 9.498389959592574 | 55.02000045776367 | 40.70372840068221 |
| DEMO.SIM.06I03_1FD Fan Motor Current | 2025-09-11 03:00:00 | 2025-09-14 23:00:00 | 7.5279 | -7.5279 | 2.1642 | 2.1642 | 0.11999999731779099 | 45.2400016784668 | 35.165000915527344 |
| DEMO.SIM.06G31_1FD Fan Damper Position | 2025-06-12 23:30:00 | 2025-06-15 23:30:00 | 5.0631 | -5.0631 | 0.7911 | 0.7911 | -5.446577767001559 | 41.41941107210072 | 35.08649031577727 |

---


## dbo.ACM_SensorNormalized_TS

**Primary Key:** ID  
**Row Count:** 483,412  
**Date Range:** 2019-03-08 11:30:00 to 2025-09-14 23:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ID | bigint | NO | 19 | — |
| RunID | uniqueidentifier | YES | — | — |
| EquipID | int | NO | 10 | — |
| Timestamp | datetime2 | NO | — | — |
| SensorName | nvarchar | NO | 200 | — |
| RawValue | float | YES | 53 | — |
| NormalizedValue | float | YES | 53 | — |
| CreatedAt | datetime2 | NO | — | (getutcdate()) |

### Top 10 Records

| ID | RunID | EquipID | Timestamp | SensorName | RawValue | NormalizedValue | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 275016 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 2024-01-04 00:00:00 | LV_ActivePower | NULL | 3603.64306640625 | 2026-01-19 10:52:08 |
| 275017 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 2024-01-04 00:10:00 | LV_ActivePower | NULL | 3603.221923828125 | 2026-01-19 10:52:08 |
| 275018 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 2024-01-04 00:20:00 | LV_ActivePower | NULL | 3603.364990234375 | 2026-01-19 10:52:08 |
| 275019 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 2024-01-04 00:30:00 | LV_ActivePower | NULL | 3603.152099609375 | 2026-01-19 10:52:08 |
| 275020 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 2024-01-04 00:40:00 | LV_ActivePower | NULL | 3603.032958984375 | 2026-01-19 10:52:08 |
| 275021 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 2024-01-04 00:50:00 | LV_ActivePower | NULL | 3603.011962890625 | 2026-01-19 10:52:08 |
| 275022 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 2024-01-04 01:00:00 | LV_ActivePower | NULL | 3602.926025390625 | 2026-01-19 10:52:08 |
| 275023 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 2024-01-04 01:10:00 | LV_ActivePower | NULL | 3603.052978515625 | 2026-01-19 10:52:08 |
| 275024 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 2024-01-04 01:20:00 | LV_ActivePower | NULL | 3603.001953125 | 2026-01-19 10:52:08 |
| 275025 | 173DD810-96E8-4E3F-AF4B-7A0B97723D70 | 8632 | 2024-01-04 01:30:00 | LV_ActivePower | NULL | 3602.820068359375 | 2026-01-19 10:52:08 |

### Bottom 10 Records

| ID | RunID | EquipID | Timestamp | SensorName | RawValue | NormalizedValue | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5865506 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 2023-01-30 19:50:00 | wind_speed_4_avg | NULL | 3.7327918582497017 | 2026-02-20 13:39:20 |
| 5865505 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 2023-01-30 17:30:00 | wind_speed_4_avg | NULL | 2.3311934621856345 | 2026-02-20 13:39:20 |
| 5865504 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 2023-01-30 15:10:00 | wind_speed_4_avg | NULL | 2.6800085079283686 | 2026-02-20 13:39:20 |
| 5865503 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 2023-01-30 12:50:00 | wind_speed_4_avg | NULL | 1.4700892843984878 | 2026-02-20 13:39:20 |
| 5865502 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 2023-01-30 10:30:00 | wind_speed_4_avg | NULL | 3.5326846511988292 | 2026-02-20 13:39:20 |
| 5865501 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 2023-01-30 08:10:00 | wind_speed_4_avg | NULL | 3.9643061166890234 | 2026-02-20 13:39:20 |
| 5865500 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 2023-01-30 05:50:00 | wind_speed_4_avg | NULL | 4.000328966921109 | 2026-02-20 13:39:20 |
| 5865499 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 2023-01-30 03:30:00 | wind_speed_4_avg | NULL | 3.5107066671238747 | 2026-02-20 13:39:20 |
| 5865498 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 2023-01-30 01:10:00 | wind_speed_4_avg | NULL | 3.6831766032821225 | 2026-02-20 13:39:20 |
| 5865497 | 8DFE547B-F660-49C6-A8FB-F194E91D4DFB | 5000 | 2023-01-29 22:50:00 | wind_speed_4_avg | NULL | 2.86386605155866 | 2026-02-20 13:39:20 |

---


## dbo.ACM_TagEquipmentMap

**Primary Key:** TagID  
**Row Count:** 2,001  
**Date Range:** 2025-12-01 04:53:29 to 2026-01-19 18:22:04  

### Schema

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

### Top 10 Records

| TagID | TagName | EquipmentName | EquipID | TagDescription | TagUnit | TagType | IsActive | CreatedAt | UpdatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 51 | DEMO.SIM.06G31_1FD Fan Damper Position | FD_FAN | 1 | FD Fan Damper Position | % | Analog | True | 2025-12-01 04:53:29 | 2025-12-01 04:53:29 |
| 52 | DEMO.SIM.06I03_1FD Fan Motor Current | FD_FAN | 1 | FD Fan Motor Current | A | Analog | True | 2025-12-01 04:53:29 | 2025-12-01 04:53:29 |
| 53 | DEMO.SIM.06GP34_1FD Fan Outlet Pressure | FD_FAN | 1 | FD Fan Outlet Pressure | inH2O | Analog | True | 2025-12-01 04:53:29 | 2025-12-01 04:53:29 |
| 54 | DEMO.SIM.06T31_1FD Fan Inlet Temperature | FD_FAN | 1 | FD Fan Inlet Temperature | F | Analog | True | 2025-12-01 04:53:29 | 2025-12-01 04:53:29 |
| 55 | DEMO.SIM.06T32-1_1FD Fan Bearing Temperature | FD_FAN | 1 | FD Fan Bearing Temperature | F | Analog | True | 2025-12-01 04:53:29 | 2025-12-01 04:53:29 |
| 56 | DEMO.SIM.06T33-1_1FD Fan Winding Temperature | FD_FAN | 1 | FD Fan Winding Temperature | F | Analog | True | 2025-12-01 04:53:29 | 2025-12-01 04:53:29 |
| 57 | DEMO.SIM.06T34_1FD Fan Outlet Termperature | FD_FAN | 1 | FD Fan Outlet Temperature | F | Analog | True | 2025-12-01 04:53:29 | 2025-12-01 04:53:29 |
| 58 | DEMO.SIM.FSAA_1FD Fan Left Inlet Flow | FD_FAN | 1 | FD Fan Left Inlet Flow | KPPH | Analog | True | 2025-12-01 04:53:29 | 2025-12-01 04:53:29 |
| 59 | DEMO.SIM.FSAB_1FD Fan Right Inlet Flow | FD_FAN | 1 | FD Fan Right Inlet Flow | KPPH | Analog | True | 2025-12-01 04:53:29 | 2025-12-01 04:53:29 |
| 60 | DWATT | GAS_TURBINE | 2621 | Generator Power Output | MW | Analog | True | 2025-12-01 04:53:29 | 2025-12-01 04:53:29 |

### Bottom 10 Records

| TagID | TagName | EquipmentName | EquipID | TagDescription | TagUnit | TagType | IsActive | CreatedAt | UpdatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2051 | VTOBY_MOTOR_OB_BRG_VIB_Y | COND_PUMP_MOTOR | 8635 | VTOBY MOTOR OB BRG VIB Y | NULL | Analog | True | 2026-01-19 18:22:04 | 2026-01-19 12:52:04 |
| 2050 | VTOBX_MOTOR_OB_BRG_VIB_X | COND_PUMP_MOTOR | 8635 | VTOBX MOTOR OB BRG VIB X | NULL | Analog | True | 2026-01-19 18:22:04 | 2026-01-19 12:52:04 |
| 2049 | VTIBY_MOTOR_IB_BRG_VIB_Y | COND_PUMP_MOTOR | 8635 | VTIBY MOTOR IB BRG VIB Y | NULL | Analog | True | 2026-01-19 18:22:04 | 2026-01-19 12:52:04 |
| 2048 | VTIBX_MOTOR_IB_BRG_VIB_X | COND_PUMP_MOTOR | 8635 | VTIBX MOTOR IB BRG VIB X | NULL | Analog | True | 2026-01-19 18:22:04 | 2026-01-19 12:52:04 |
| 2047 | TTOB_MOTOR_OB_BRG_TEMP | COND_PUMP_MOTOR | 8635 | TTOB MOTOR OB BRG TEMP | NULL | Analog | True | 2026-01-19 18:22:04 | 2026-01-19 12:52:04 |
| 2046 | TTIB_MOTOR_IB_BRG_TEMP | COND_PUMP_MOTOR | 8635 | TTIB MOTOR IB BRG TEMP | NULL | Analog | True | 2026-01-19 18:22:04 | 2026-01-19 12:52:04 |
| 2045 | TIPH3_WINDING_TEMP_C | COND_PUMP_MOTOR | 8635 | TIPH3 WINDING TEMP C | NULL | Analog | True | 2026-01-19 18:22:04 | 2026-01-19 12:52:04 |
| 2044 | TIPH2_WINDING_TEMP_B | COND_PUMP_MOTOR | 8635 | TIPH2 WINDING TEMP B | NULL | Analog | True | 2026-01-19 18:22:04 | 2026-01-19 12:52:04 |
| 2043 | TIPH1_WINDING_TEMP_A | COND_PUMP_MOTOR | 8635 | TIPH1 WINDING TEMP A | NULL | Analog | True | 2026-01-19 18:22:04 | 2026-01-19 12:52:04 |
| 2042 | JPH3_CURRENT_PH_C | COND_PUMP_MOTOR | 8635 | JPH3 CURRENT PH C | NULL | Analog | True | 2026-01-19 18:22:04 | 2026-01-19 12:52:04 |

---


## dbo.COND_PUMP_MOTOR_Data

**Primary Key:** No primary key  
**Row Count:** 17,619  
**Date Range:** 2018-12-01 00:00:00 to 2020-04-01 09:10:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| PWR1_POWER | float | YES | 53 | — |
| PF1_POWER_FACTOR | float | YES | 53 | — |
| JAVG_CURRENT_AVG | float | YES | 53 | — |
| JPH1_CURRENT_PH_A | float | YES | 53 | — |
| JPH2_CURRENT_PH_B | float | YES | 53 | — |
| JPH3_CURRENT_PH_C | float | YES | 53 | — |
| TIPH1_WINDING_TEMP_A | float | YES | 53 | — |
| TIPH2_WINDING_TEMP_B | float | YES | 53 | — |
| TIPH3_WINDING_TEMP_C | float | YES | 53 | — |
| TTIB_MOTOR_IB_BRG_TEMP | float | YES | 53 | — |
| TTOB_MOTOR_OB_BRG_TEMP | float | YES | 53 | — |
| VTIBX_MOTOR_IB_BRG_VIB_X | float | YES | 53 | — |
| VTIBY_MOTOR_IB_BRG_VIB_Y | float | YES | 53 | — |
| VTOBX_MOTOR_OB_BRG_VIB_X | float | YES | 53 | — |
| VTOBY_MOTOR_OB_BRG_VIB_Y | float | YES | 53 | — |

### Top 10 Records

| EntryDateTime | PWR1_POWER | PF1_POWER_FACTOR | JAVG_CURRENT_AVG | JPH1_CURRENT_PH_A | JPH2_CURRENT_PH_B | JPH3_CURRENT_PH_C | TIPH1_WINDING_TEMP_A | TIPH2_WINDING_TEMP_B | TIPH3_WINDING_TEMP_C |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2018-12-01 00:00:00 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 76.17407227 | 76.40065765 | 75.94750214 |
| 2018-12-01 00:30:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 75.94750214 | 76.28833008 | 75.72093964 |
| 2018-12-01 01:00:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 75.80420685 | 76.17407227 | 75.72093964 |
| 2018-12-01 01:30:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 75.72093964 | 75.94750214 | 75.4943924 |
| 2018-12-01 02:00:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 75.4943924 | 75.94750214 | 75.29108429 |
| 2018-12-01 02:30:00 | 0.0 | 0.025641026 | 0.0 | 0.0 | 0.0 | 0.0 | 75.4943924 | 75.72093964 | 75.26784515 |
| 2018-12-01 03:00:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 75.26784515 | 75.4943924 | 75.04130554 |
| 2018-12-01 03:30:00 | 0.0 | 0.282051295 | 0.0 | 0.0 | 0.0 | 0.0 | 75.20394897 | 75.4943924 | 74.97741699 |
| 2018-12-01 04:00:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 75.04130554 | 75.26784515 | 74.81478119 |
| 2018-12-01 04:30:00 | 0.0 | 0.534482777 | 0.0 | 0.0 | 0.0 | 0.0 | 74.81478119 | 75.26784515 | 74.81478119 |

### Bottom 10 Records

| EntryDateTime | PWR1_POWER | PF1_POWER_FACTOR | JAVG_CURRENT_AVG | JPH1_CURRENT_PH_A | JPH2_CURRENT_PH_B | JPH3_CURRENT_PH_C | TIPH1_WINDING_TEMP_A | TIPH2_WINDING_TEMP_B | TIPH3_WINDING_TEMP_C |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2020-04-01 09:10:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 84.79042053 | 85.01734161 | 84.56351471 |
| 2020-04-01 09:00:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 84.82863617 | 85.24427795 | 84.79042053 |
| 2020-04-01 08:50:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 85.01734161 | 85.47121429 | 85.01734161 |
| 2020-04-01 08:40:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 85.24427795 | 85.64321136 | 85.24427795 |
| 2020-04-01 08:30:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 85.47121429 | 85.7148819 | 85.24427795 |
| 2020-04-01 08:20:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 85.69815826 | 85.92511749 | 85.47121429 |
| 2020-04-01 08:10:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 85.92511749 | 86.15208435 | 85.69815826 |
| 2020-04-01 08:00:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 86.15208435 | 86.37905884 | 85.92511749 |
| 2020-04-01 07:50:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 86.37905884 | 86.60604095 | 86.15208435 |
| 2020-04-01 07:40:00 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 86.37905884 | 86.8330307 | 86.37905884 |

---


## dbo.ELECTRIC_MOTOR_Data

**Primary Key:** No primary key  
**Row Count:** 17,477  
**Date Range:** 2024-01-01 00:00:00 to 2024-12-01 23:59:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| u_q | float | YES | 53 | — |
| coolant | float | YES | 53 | — |
| stator_winding | float | YES | 53 | — |
| u_d | float | YES | 53 | — |
| stator_tooth | float | YES | 53 | — |
| motor_speed | float | YES | 53 | — |
| i_d | float | YES | 53 | — |
| i_q | float | YES | 53 | — |
| pm | float | YES | 53 | — |
| stator_yoke | float | YES | 53 | — |
| ambient | float | YES | 53 | — |
| torque | float | YES | 53 | — |
| profile_id | bigint | YES | 19 | — |

### Top 10 Records

| EntryDateTime | u_q | coolant | stator_winding | u_d | stator_tooth | motor_speed | i_d | i_q | pm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-01-01 00:00:00 | 48.378386286166666 | 18.900812435 | 19.361286926000002 | -43.17679374463333 | 18.451467990333338 | 2311.6027119875334 | -63.28096596180001 | 29.90897307461666 | 24.585809103833338 |
| 2024-01-01 00:01:00 | 91.34201901700003 | 18.897907416333336 | 25.64166495033333 | -92.01435012816667 | 21.45641950016667 | 4999.943725566666 | -142.82388814666666 | 52.83300215416664 | 26.36999613433333 |
| 2024-01-01 00:02:00 | 91.1145528155 | 18.91490360850001 | 32.93693752266667 | -92.23500722199998 | 26.474174785333332 | 4999.956746416667 | -142.35288645666665 | 52.887767536833344 | 28.736558691500004 |
| 2024-01-01 00:03:00 | 90.86030057283334 | 18.994687843666668 | 38.51075560316666 | -92.53561503099999 | 30.74385830500001 | 4999.9565837499995 | -141.90893859666667 | 52.92798016816666 | 30.93217407866666 |
| 2024-01-01 00:04:00 | 90.70566151933333 | 19.10296223966667 | 43.49067993133335 | -92.70875523816667 | 34.10806763916666 | 4999.956079150001 | -141.6960528066667 | 52.94287637083333 | 33.0365564985 |
| 2024-01-01 00:05:00 | 90.47746200599998 | 19.161996460333334 | 47.097871653333314 | -92.94932467099999 | 37.19874865233333 | 4999.955940799998 | -141.4490150466667 | 52.98018754316669 | 35.018084462333334 |
| 2024-01-01 00:06:00 | 90.30193456049997 | 19.209312978666667 | 51.04982903816666 | -93.19797770199999 | 39.2428047815 | 4999.955851216666 | -141.24095255833333 | 53.027876091166675 | 36.90033461233334 |
| 2024-01-01 00:07:00 | 90.17929255133335 | 19.242657598 | 53.6280256903333 | -93.34241714483332 | 41.46424528800001 | 4999.956014016667 | -141.08919804833334 | 53.058543268833326 | 38.65695915233334 |
| 2024-01-01 00:08:00 | 89.95980161050001 | 19.236234633000006 | 56.21492614716668 | -93.55297711766667 | 43.65091775233334 | 4999.957389366666 | -140.8591430666667 | 53.06756922349999 | 40.33262329116666 |
| 2024-01-01 00:09:00 | 89.84458618133333 | 19.1955741885 | 58.23025868683329 | -93.72211799616666 | 45.23047421716665 | 4999.956494133333 | -140.74482015666666 | 53.09469763416668 | 41.95414447783334 |

### Bottom 10 Records

| EntryDateTime | u_q | coolant | stator_winding | u_d | stator_tooth | motor_speed | i_d | i_q | pm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-12-01 23:59:00 | 1.1721619141333333 | 28.186712892666662 | 28.08523399083333 | 0.3652682746333333 | 27.701225878499997 | 0.0009566072166666668 | -2.0005455226499995 | 1.0970678800000002 | 35.299491783666674 |
| 2024-12-01 23:58:00 | 1.164350336366667 | 28.172085320333327 | 28.104769323166668 | 0.3524907381000001 | 27.70104749266667 | 9.413821666666666e-05 | -2.00056689405 | 1.0972193864166664 | 35.37197066249999 |
| 2024-12-01 23:57:00 | 1.1713139229833331 | 28.159938034 | 28.107086791333337 | 0.35682004373333337 | 27.663690461499996 | 0.0001793159333333334 | -2.0006962553166665 | 1.0970444282833336 | 35.4505278965 |
| 2024-12-01 23:56:00 | 1.1680835715000002 | 28.18664423383333 | 28.102322523166663 | 0.3647678287666667 | 27.669372358500002 | 0.0001553014166666668 | -2.0003284368000003 | 1.0971704809333336 | 35.52268177966666 |
| 2024-12-01 23:55:00 | 1.1703049006166668 | 28.178678517333335 | 28.090460950500002 | 0.3640781494499999 | 27.7156685265 | -1.569796666666673e-05 | -2.0004054199166665 | 1.0969923302666666 | 35.59825376333333 |
| 2024-12-01 23:54:00 | 1.1704963194 | 28.172214498000002 | 28.131948800166672 | 0.3631390080166667 | 27.72754888733333 | 0.0001639094333333333 | -2.0005341474166665 | 1.0970136549166665 | 35.67296063933335 |
| 2024-12-01 23:53:00 | 1.1699569248666668 | 28.177647645999993 | 28.099683289 | 0.35316880525000005 | 27.693439247499995 | -0.00018186781666666666 | -2.0005412548166666 | 1.0968460292666664 | 35.756014847833335 |
| 2024-12-01 23:52:00 | 1.1608535779 | 28.170571701499988 | 28.136193458166677 | 0.3571568778166668 | 27.540225634500008 | 0.0008304430666666668 | -2.0004174596500004 | 1.0972237057333334 | 35.83020165100001 |
| 2024-12-01 23:51:00 | 1.1752969764499999 | 28.176263269 | 28.14836788033332 | 0.3677545190166666 | 27.682216454166667 | -0.0007401398500000002 | -2.0005444712 | 1.0970086890166664 | 35.913733745333325 |
| 2024-12-01 23:50:00 | 1.1749393239333332 | 28.176702847999998 | 28.24717568383334 | 0.36633154763333325 | 27.717695598166657 | -0.00020579585000000004 | -2.0004473565333334 | 1.0970381099000002 | 35.99464184800001 |

---


## dbo.ELECTRIC_MOTOR_Data_RAW

**Primary Key:** No primary key  
**Row Count:** 1,048,575  
**Date Range:** 2024-01-01 00:00:00 to 2024-12-01 23:59:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| u_q | float | YES | 53 | — |
| coolant | float | YES | 53 | — |
| stator_winding | float | YES | 53 | — |
| u_d | float | YES | 53 | — |
| stator_tooth | float | YES | 53 | — |
| motor_speed | float | YES | 53 | — |
| i_d | float | YES | 53 | — |
| i_q | float | YES | 53 | — |
| pm | float | YES | 53 | — |
| stator_yoke | float | YES | 53 | — |
| ambient | float | YES | 53 | — |
| torque | float | YES | 53 | — |
| profile_id | bigint | YES | 19 | — |

### Top 10 Records

| EntryDateTime | u_q | coolant | stator_winding | u_d | stator_tooth | motor_speed | i_d | i_q | pm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-01-01 00:00:00 | -0.450681508 | 18.80517197 | 19.08666992 | -0.350054592 | 18.29321861 | 0.002865568 | 0.004419137 | 0.000328102 | 24.55421448 |
| 2024-01-01 00:00:00 | -0.325737 | 18.81857109 | 19.09239006 | -0.305803001 | 18.29480743 | 0.000256782 | 0.000605872 | -0.000785353 | 24.53807831 |
| 2024-01-01 00:00:00 | -0.440864027 | 18.82876968 | 19.08938026 | -0.372502625 | 18.29409409 | 0.002354971 | 0.001289587 | 0.000386468 | 24.54469299 |
| 2024-01-01 00:00:00 | -0.327025682 | 18.83556747 | 19.0830307 | -0.316198707 | 18.2925415 | 0.006104666 | 2.56e-05 | 0.002045661 | 24.55401802 |
| 2024-01-01 00:00:00 | -0.47115013 | 18.85703278 | 19.08252525 | -0.332272142 | 18.29142761 | 0.003132823 | -0.064316779 | 0.037183776 | 24.56539726 |
| 2024-01-01 00:00:00 | -0.538972616 | 18.90154839 | 19.07710838 | 0.009147473 | 18.29062843 | 0.009636124 | -0.613635242 | 0.336747348 | 24.57360077 |
| 2024-01-01 00:00:00 | -0.653148472 | 18.94171143 | 19.07458305 | 0.238889694 | 18.29252434 | 0.001337012 | -1.005647302 | 0.554211259 | 24.57657814 |
| 2024-01-01 00:00:00 | -0.758391559 | 18.96086121 | 19.08249855 | 0.395099252 | 18.29404068 | 0.001421958 | -1.288383722 | 0.706369996 | 24.57494926 |
| 2024-01-01 00:00:00 | -0.727128446 | 18.97354507 | 19.08553314 | 0.546622515 | 18.29196358 | 0.000576553 | -1.490530491 | 0.81733948 | 24.56707954 |
| 2024-01-01 00:00:00 | -0.874307454 | 18.98781204 | 19.07602501 | 0.578943968 | 18.28723335 | -0.00124788 | -1.634463549 | 0.898012877 | 24.55324173 |

### Bottom 10 Records

| EntryDateTime | u_q | coolant | stator_winding | u_d | stator_tooth | motor_speed | i_d | i_q | pm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-12-01 23:59:00 | 1.137114022 | 28.13785325 | 28.09149068 | 0.347978841 | 27.70218009 | 0.007293692 | -2.001524275 | 1.097026618 | 35.25571142 |
| 2024-12-01 23:59:00 | 1.212985191 | 28.15191758 | 28.08352885 | 0.325080895 | 27.69210776 | -0.00248922 | -2.000248251 | 1.096491804 | 35.2537029 |
| 2024-12-01 23:59:00 | 1.131010044 | 28.1875456 | 28.09089738 | 0.380257415 | 27.67168962 | -0.006319263 | -2.001364778 | 1.097398743 | 35.25990047 |
| 2024-12-01 23:59:00 | 1.21948531 | 28.22228993 | 28.08972825 | 0.340979721 | 27.64104971 | -0.001454695 | -2.00143121 | 1.096344035 | 35.26434707 |
| 2024-12-01 23:59:00 | 1.137752435 | 28.22954785 | 28.11811227 | 0.367792107 | 27.60556824 | 0.002287588 | -2.001507436 | 1.097547149 | 35.27352702 |
| 2024-12-01 23:59:00 | 1.23980985 | 28.24267235 | 28.1445875 | 0.297356804 | 27.64451354 | 0.008019502 | -2.001208195 | 1.097788805 | 35.28422604 |
| 2024-12-01 23:59:00 | 1.128303649 | 28.25044137 | 28.12256643 | 0.357707544 | 27.64212944 | 0.002806887 | -1.999326862 | 1.098612936 | 35.27906876 |
| 2024-12-01 23:59:00 | 1.239920079 | 28.25659208 | 28.11138549 | 0.293788543 | 27.62084437 | 0.003575936 | -2.001055169 | 1.097157751 | 35.27650155 |
| 2024-12-01 23:59:00 | 1.136833857 | 28.24703663 | 28.11280315 | 0.369323379 | 27.69073599 | 0.005486384 | -2.001329434 | 1.09705893 | 35.28160367 |
| 2024-12-01 23:59:00 | 1.232331681 | 28.23297177 | 28.10448049 | 0.310092131 | 27.71307039 | 0.005195291 | -2.000172126 | 1.097474372 | 35.2798471 |

---


## dbo.Equipment

**Primary Key:** EquipID  
**Row Count:** 30  
**Date Range:** 2025-01-01 00:00:00 to 2025-01-01 00:00:00  

### Schema

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

### Top 10 Records

| EquipID | EquipCode | EquipName | Area | Unit | Status | CommissionDate | CreatedAtUTC |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | * | Default/Wildcard Config | Global | All Plants | 1 | 2025-01-01 00:00:00 | 2025-11-13 09:21:41 |
| 1 | FD_FAN | Forced Draft Fan | Boiler Section | Plant A | 1 | 2025-01-01 00:00:00 | 2025-11-13 07:54:36 |
| 2621 | GAS_TURBINE | Gas Turbine Generator | Power Generation | Plant A | 1 | 2025-01-01 00:00:00 | 2025-11-13 07:54:36 |
| 5000 | WFA_TURBINE_0 | Wind Farm A Turbine 0 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |
| 5003 | WFA_TURBINE_3 | Wind Farm A Turbine 3 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |
| 5010 | WFA_TURBINE_10 | Wind Farm A Turbine 10 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |
| 5011 | WFA_TURBINE_11 | Wind Farm A Turbine 11 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |
| 5013 | WFA_TURBINE_13 | Wind Farm A Turbine 13 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |
| 5014 | WFA_TURBINE_14 | Wind Farm A Turbine 14 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |
| 5017 | WFA_TURBINE_17 | Wind Farm A Turbine 17 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |

### Bottom 10 Records

| EquipID | EquipCode | EquipName | Area | Unit | Status | CommissionDate | CreatedAtUTC |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8635 | COND_PUMP_MOTOR | Cond Pump Motor | NULL | NULL | 1 | NULL | 2026-01-19 12:52:04 |
| 8634 | ELECTRIC_MOTOR | Electric Motor | NULL | NULL | 1 | NULL | 2025-12-11 12:57:37 |
| 8632 | WIND_TURBINE | Wind Turbine SCADA | Renewable Energy | Wind Farm | 1 | NULL | 2025-12-11 11:34:08 |
| 5092 | WFA_TURBINE_92 | Wind Farm A Turbine 92 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |
| 5084 | WFA_TURBINE_84 | Wind Farm A Turbine 84 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |
| 5073 | WFA_TURBINE_73 | Wind Farm A Turbine 73 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |
| 5072 | WFA_TURBINE_72 | Wind Farm A Turbine 72 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |
| 5071 | WFA_TURBINE_71 | Wind Farm A Turbine 71 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |
| 5069 | WFA_TURBINE_69 | Wind Farm A Turbine 69 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |
| 5068 | WFA_TURBINE_68 | Wind Farm A Turbine 68 | Wind Farm A | Turbine | 1 | 2025-01-01 00:00:00 | 2025-12-13 04:26:58 |

---


## dbo.FD_FAN_Data

**Primary Key:** EntryDateTime  
**Row Count:** 17,499  
**Date Range:** 2023-10-15 00:00:00 to 2025-09-14 23:30:00  

### Schema

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

### Top 10 Records

| EntryDateTime | DEMO.SIM.06G31_1FD Fan Damper Position | DEMO.SIM.06I03_1FD Fan Motor Current | DEMO.SIM.06GP34_1FD Fan Outlet Pressure | DEMO.SIM.06T31_1FD Fan Inlet Temperature | DEMO.SIM.06T32-1_1FD Fan Bearing Temperature | DEMO.SIM.06T33-1_1FD Fan Winding Temperature | DEMO.SIM.06T34_1FD Fan Outlet Termperature | DEMO.SIM.FSAA_1FD Fan Left Inlet Flow | DEMO.SIM.FSAB_1FD Fan Right Inlet Flow |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-10-15 00:00:00 | 32.78 | 35.86 | 0.52 | 36.37 | 61.05 | 44.09 | 22.0 | 294.7 | 301.38 |
| 2023-10-15 00:30:00 | 31.6 | 35.03 | 0.39 | 36.46 | 60.42 | 44.56 | 22.81 | 264.18 | 272.99 |
| 2023-10-15 01:00:00 | 30.18 | 35.1 | 0.57 | 37.24 | 61.17 | 45.0 | 23.01 | 263.76 | 269.35 |
| 2023-10-15 01:30:00 | 27.8 | 34.89 | 0.23 | 36.93 | 61.13 | 45.63 | 24.24 | 245.16 | 251.28 |
| 2023-10-15 02:00:00 | 28.22 | 34.33 | 0.28 | 37.42 | 62.29 | 45.92 | 25.56 | 239.65 | 235.69 |
| 2023-10-15 02:30:00 | 30.71 | 35.08 | 0.6 | 38.89 | 61.96 | 46.62 | 26.04 | 273.33 | 272.12 |
| 2023-10-15 03:00:00 | 31.8 | 36.22 | 0.54 | 39.0 | 62.04 | 47.15 | 27.25 | 290.31 | 287.79 |
| 2023-10-15 03:30:00 | 33.36 | 36.47 | 0.57 | 39.83 | 62.56 | 47.99 | 27.8 | 305.63 | 298.89 |
| 2023-10-15 04:00:00 | 29.94 | 35.16 | 0.65 | 40.24 | 62.82 | 48.34 | 28.83 | 271.35 | 271.9 |
| 2023-10-15 04:30:00 | 28.39 | 34.86 | 0.68 | 40.89 | 63.11 | 48.71 | 28.19 | 261.49 | 261.95 |

### Bottom 10 Records

| EntryDateTime | DEMO.SIM.06G31_1FD Fan Damper Position | DEMO.SIM.06I03_1FD Fan Motor Current | DEMO.SIM.06GP34_1FD Fan Outlet Pressure | DEMO.SIM.06T31_1FD Fan Inlet Temperature | DEMO.SIM.06T32-1_1FD Fan Bearing Temperature | DEMO.SIM.06T33-1_1FD Fan Winding Temperature | DEMO.SIM.06T34_1FD Fan Outlet Termperature | DEMO.SIM.FSAA_1FD Fan Left Inlet Flow | DEMO.SIM.FSAB_1FD Fan Right Inlet Flow |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-09-14 23:30:00 | 52.05 | 47.83 | 1.38 | 48.64 | 63.56 | 55.66 | 34.29 | 399.31 | 417.34 |
| 2025-09-14 23:00:00 | 48.12 | 45.24 | 1.33 | 48.11 | 63.44 | 55.02 | 33.24 | 383.58 | 397.95 |
| 2025-09-14 22:30:00 | 46.54 | 44.42 | 1.19 | 47.4 | 63.45 | 54.46 | 32.21 | 373.67 | 393.27 |
| 2025-09-14 22:00:00 | 48.93 | 45.3 | 1.49 | 46.7 | 62.59 | 53.56 | 32.26 | 379.2 | 396.8 |
| 2025-09-14 21:30:00 | 45.28 | 42.38 | 1.12 | 46.03 | 62.87 | 53.1 | 30.98 | 347.54 | 359.95 |
| 2025-09-14 21:00:00 | 45.39 | 42.78 | 1.41 | 46.04 | 62.29 | 53.25 | 30.63 | 365.25 | 378.35 |
| 2025-09-14 20:30:00 | 50.7 | 46.65 | 1.45 | 44.96 | 62.04 | 52.78 | 30.08 | 399.45 | 418.41 |
| 2025-09-14 20:00:00 | 48.6 | 45.26 | 1.45 | 44.28 | 61.37 | 51.3 | 28.84 | 381.99 | 395.47 |
| 2025-09-14 19:30:00 | 44.23 | 41.86 | 1.49 | 43.57 | 60.16 | 50.85 | 28.18 | 358.22 | 373.61 |
| 2025-09-14 19:00:00 | 46.91 | 44.4 | 1.61 | 42.74 | 60.53 | 50.2 | 26.88 | 375.07 | 390.55 |

---


## dbo.GAS_TURBINE_Data

**Primary Key:** EntryDateTime  
**Row Count:** 2,911  
**Date Range:** 2023-10-15 00:00:00 to 2024-06-16 01:59:00  

### Schema

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

### Top 10 Records

| EntryDateTime | DWATT | B1VIB1 | B1VIB2 | B1RADVIBX | B1RADVIBY | B2VIB1 | B2VIB2 | B2RADVIBX | B2RADVIBY |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-10-15 00:00:00 | 0.046386719 | 0.003474951 | 0.003582239 | 0.088310242 | 0.073814392 | 0.00166893 | 0.001722574 | 0.102710724 | 0.080680847 |
| 2023-10-15 01:00:00 | 0.048736572 | 0.003510714 | 0.003516674 | 0.089359283 | 0.078964233 | 0.001817942 | 0.002282858 | 0.092029572 | 0.074386597 |
| 2023-10-15 02:00:00 | 0.058380127 | 0.003516674 | 0.003367662 | 0.064277649 | 0.08058548 | 0.001698732 | 0.001859665 | 0.089359283 | 0.07276535 |
| 2023-10-15 03:00:00 | 0.056243896 | 0.003319979 | 0.003421307 | 0.096035004 | 0.103378296 | 0.001847744 | 0.001585484 | 0.132274628 | 0.107097626 |
| 2023-10-15 04:00:00 | 0.046020508 | 0.003510714 | 0.003546476 | 0.154399872 | 0.11920929 | 0.00193119 | 0.001746416 | 0.091648102 | 0.066566467 |
| 2023-10-15 05:00:00 | 0.05670166 | 0.003254414 | 0.003486872 | 0.121307373 | 0.084114075 | 0.001633167 | 0.001603365 | 0.071239471 | 0.0623703 |
| 2023-10-15 06:00:00 | 0.050323486 | 0.003314018 | 0.00346899 | 0.225830078 | 0.125312805 | 0.002282858 | 0.002169609 | 0.082397461 | 0.074291229 |
| 2023-10-15 07:00:00 | 0.04699707 | 0.003361702 | 0.00321269 | 0.080394745 | 0.089740753 | 0.001698732 | 0.001680851 | 0.078964233 | 0.091552734 |
| 2023-10-15 08:00:00 | 0.037811279 | 0.003302097 | 0.003272295 | 0.083351135 | 0.112819672 | 0.001722574 | 0.001704693 | 0.123596191 | 0.109767914 |
| 2023-10-15 09:00:00 | 0.025543213 | 0.003635883 | 0.003671646 | 0.121593475 | 0.103569031 | 0.001752377 | 0.001722574 | 0.095081329 | 0.086212158 |

### Bottom 10 Records

| EntryDateTime | DWATT | B1VIB1 | B1VIB2 | B1RADVIBX | B1RADVIBY | B2VIB1 | B2VIB2 | B2RADVIBX | B2RADVIBY |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-06-16 01:59:00 | 0.032104492 | 0.004428625 | 0.004589558 | 0.102615356 | 0.086212158 | 0.001949072 | 0.002008677 | 0.090408325 | 0.135612488 |
| 2024-06-16 00:59:00 | 0.035583496 | 0.004279613 | 0.004172325 | 0.120735168 | 0.075054169 | 0.002062321 | 0.002026558 | 0.067615509 | 0.069141388 |
| 2024-06-15 23:59:00 | 0.032012939 | 0.004637241 | 0.004476309 | 0.09727478 | 0.063991547 | 0.002026558 | 0.001955032 | 0.098609924 | 0.094413757 |
| 2024-06-15 22:59:00 | 0.033325195 | 0.00398159 | 0.004124641 | 0.101089478 | 0.080966949 | 0.001943111 | 0.001806021 | 0.108337402 | 0.105381012 |
| 2024-06-15 21:59:00 | 0.030883789 | 0.004047155 | 0.004076958 | 0.125312805 | 0.113677979 | 0.002080202 | 0.00205636 | 0.074005127 | 0.077819824 |
| 2024-06-15 20:59:00 | 154.3208008 | 0.207543373 | 0.206416845 | 3.847885132 | 3.883361816 | 0.089865923 | 0.08701086 | 1.396083832 | 1.22385025 |
| 2024-06-15 19:59:00 | 160.8225708 | 0.213122368 | 0.2125144 | 3.946208954 | 3.966903687 | 0.087571144 | 0.085371733 | 1.428318024 | 1.244831085 |
| 2024-06-15 18:59:00 | 159.7585144 | 0.221902132 | 0.220447779 | 4.005908966 | 4.01468277 | 0.088727474 | 0.08649826 | 1.43699646 | 1.271915436 |
| 2024-06-15 17:59:00 | 157.7884216 | 0.211650133 | 0.207263231 | 3.846263885 | 3.898620605 | 0.086086988 | 0.08571744 | 1.389503479 | 1.257705688 |
| 2024-06-15 16:59:00 | 156.4640808 | 0.214719772 | 0.211650133 | 3.853225708 | 3.888607025 | 0.098234415 | 0.089746714 | 1.364040375 | 1.244735718 |

---


## dbo.ModelRegistry

**Primary Key:** ModelType, EquipID, Version  
**Row Count:** 184  
**Date Range:** 2025-12-27 06:26:16 to 2026-02-20 13:17:49  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| ModelType | varchar | NO | 32 | — |
| EquipID | int | NO | 10 | — |
| Version | int | NO | 10 | — |
| EntryDateTime | datetime2 | NO | — | (sysutcdatetime()) |
| ParamsJSON | nvarchar | YES | -1 | — |
| StatsJSON | nvarchar | YES | -1 | — |
| RunID | uniqueidentifier | YES | — | — |
| ModelBytes | varbinary | YES | -1 | — |

### Top 10 Records

| ModelType | EquipID | Version | EntryDateTime | ParamsJSON | StatsJSON | RunID | ModelBytes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ar1_params | 1 | 1 | 2026-02-19 05:30:44 | {"n_sensors": 72, "mean_autocorr": 12.8572, "mean_residual_std": 0.4433, "params_count": 144} | {"train_rows": 603, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06G... | NULL | <binary 5677 bytes> |
| calibration_params | 1 | 1 | 2026-02-19 05:30:56 | NULL | NULL | NULL | <binary 600 bytes> |
| gmm_model | 1 | 1 | 2026-02-19 05:30:48 | {"n_components": 3, "covariance_type": "diag", "bic": 262029554.49, "aic": 262027644.06, "lower_b... | {"train_rows": 603, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06G... | NULL | <binary 8199 bytes> |
| iforest_model | 1 | 1 | 2026-02-19 05:30:48 | {"n_estimators": 100, "contamination": 0.01, "max_features": 1.0, "max_samples": 2048} | {"train_rows": 603, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06G... | NULL | <binary 2016153 bytes> |
| omr_model | 1 | 1 | 2026-02-19 05:30:48 | NULL | {"train_rows": 603, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06G... | NULL | <binary 166393 bytes> |
| pca_model | 1 | 1 | 2026-02-19 05:30:44 | {"n_components": 5, "variance_ratio_sum": 0.6037, "variance_ratio_first_component": 0.1854, "vari... | {"train_rows": 603, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06G... | NULL | <binary 4511 bytes> |
| regime_model | 1 | 1 | 2026-02-19 05:30:49 | NULL | {"train_rows": 603, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06G... | NULL | <binary 160243 bytes> |
| ar1_params | 2621 | 1 | 2026-02-19 08:21:17 | {"n_sensors": 128, "mean_autocorr": 4.385, "mean_residual_std": 0.3402, "params_count": 256} | {"train_rows": 500, "train_sensors": ["ACTTBTEMP1_med", "B1RADVIBX_med", "B1RADVIBY_med", "B1TEMP... | NULL | <binary 6012 bytes> |
| calibration_params | 2621 | 1 | 2026-02-19 08:21:31 | NULL | NULL | NULL | <binary 600 bytes> |
| gmm_model | 2621 | 1 | 2026-02-19 08:21:21 | {"n_components": 3, "covariance_type": "diag", "bic": 259996949.44, "aic": 259993704.19, "lower_b... | {"train_rows": 500, "train_sensors": ["ACTTBTEMP1_med", "B1RADVIBX_med", "B1RADVIBY_med", "B1TEMP... | NULL | <binary 13594 bytes> |

### Bottom 10 Records

| ModelType | EquipID | Version | EntryDateTime | ParamsJSON | StatsJSON | RunID | ModelBytes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| regime_model | 8635 | 3 | 2026-01-19 13:22:07 | NULL | {"train_rows": 43475, "train_sensors": ["JAVG_CURRENT_AVG_med", "JPH1_CURRENT_PH_A_med", "JPH2_CU... | NULL | <binary 2481067 bytes> |
| pca_model | 8635 | 3 | 2026-01-19 13:22:02 | {"n_components": 5, "variance_ratio_sum": 0.8803, "variance_ratio_first_component": 0.5156, "vari... | {"train_rows": 43475, "train_sensors": ["JAVG_CURRENT_AVG_med", "JPH1_CURRENT_PH_A_med", "JPH2_CU... | NULL | <binary 6431 bytes> |
| omr_model | 8635 | 3 | 2026-01-19 13:22:06 | NULL | {"train_rows": 43475, "train_sensors": ["JAVG_CURRENT_AVG_med", "JPH1_CURRENT_PH_A_med", "JPH2_CU... | NULL | <binary 7096941 bytes> |
| iforest_model | 8635 | 3 | 2026-01-19 13:22:05 | {"n_estimators": 100, "contamination": 0.01, "max_features": 1.0, "max_samples": 2048} | {"train_rows": 43475, "train_sensors": ["JAVG_CURRENT_AVG_med", "JPH1_CURRENT_PH_A_med", "JPH2_CU... | NULL | <binary 4802553 bytes> |
| gmm_model | 8635 | 3 | 2026-01-19 13:22:06 | {"n_components": 3, "covariance_type": "diag", "bic": 449877130008816.44, "aic": 449877130002966.... | {"train_rows": 43475, "train_sensors": ["JAVG_CURRENT_AVG_med", "JPH1_CURRENT_PH_A_med", "JPH2_CU... | NULL | <binary 12343 bytes> |
| ar1_params | 8635 | 3 | 2026-01-19 13:22:02 | {"n_sensors": 112, "mean_autocorr": 133.1998, "mean_residual_std": 12.6471, "params_count": 224} | {"train_rows": 43475, "train_sensors": ["JAVG_CURRENT_AVG_med", "JPH1_CURRENT_PH_A_med", "JPH2_CU... | NULL | <binary 6505 bytes> |
| regime_model | 8635 | 2 | 2026-01-19 13:03:31 | NULL | {"train_rows": 16935, "train_sensors": ["JAVG_CURRENT_AVG_med", "JPH1_CURRENT_PH_A_med", "JPH2_CU... | NULL | <binary 2310651 bytes> |
| pca_model | 8635 | 2 | 2026-01-19 13:03:26 | {"n_components": 5, "variance_ratio_sum": 0.7874, "variance_ratio_first_component": 0.3732, "vari... | {"train_rows": 16935, "train_sensors": ["JAVG_CURRENT_AVG_med", "JPH1_CURRENT_PH_A_med", "JPH2_CU... | NULL | <binary 6047 bytes> |
| omr_model | 8635 | 2 | 2026-01-19 13:03:30 | NULL | {"train_rows": 16935, "train_sensors": ["JAVG_CURRENT_AVG_med", "JPH1_CURRENT_PH_A_med", "JPH2_CU... | NULL | <binary 2833979 bytes> |
| iforest_model | 8635 | 2 | 2026-01-19 13:03:30 | {"n_estimators": 100, "contamination": 0.01, "max_features": 1.0, "max_samples": 2048} | {"train_rows": 16935, "train_sensors": ["JAVG_CURRENT_AVG_med", "JPH1_CURRENT_PH_A_med", "JPH2_CU... | NULL | <binary 3650041 bytes> |

---


## dbo.WFA_TURBINE_0_Data

**Primary Key:** EntryDateTime  
**Row Count:** 54,986  
**Date Range:** 2022-08-04 06:10:00 to 2023-08-24 06:10:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-08-04 06:10:00 | 0 | 0 | train | 0 | 22.0 | 302.9 | 129.4 | 1.7000000000000002 | 1.7000000000000002 |
| 2022-08-04 06:20:00 | 0 | 1 | train | 0 | 22.0 | 307.1 | 133.6 | 1.7000000000000002 | 1.7000000000000002 |
| 2022-08-04 06:30:00 | 0 | 2 | train | 0 | 22.0 | 340.6 | 167.1 | 0.9 | 0.9 |
| 2022-08-04 06:40:00 | 0 | 3 | train | 0 | 22.0 | 124.4 | -49.1 | 1.5 | 1.5 |
| 2022-08-04 06:50:00 | 0 | 4 | train | 0 | 22.0 | 66.2 | -107.3 | 1.0 | 1.0 |
| 2022-08-04 07:00:00 | 0 | 5 | train | 0 | 22.0 | 92.0 | -81.4 | 1.1 | 1.1 |
| 2022-08-04 07:10:00 | 0 | 6 | train | 0 | 22.0 | 286.9 | 113.4 | 0.7000000000000001 | 0.7000000000000001 |
| 2022-08-04 07:20:00 | 0 | 7 | train | 0 | 22.0 | 154.4 | -19.1 | 1.5 | 1.5 |
| 2022-08-04 07:30:00 | 0 | 8 | train | 0 | 22.0 | 128.7 | -44.8 | 1.7000000000000002 | 1.7000000000000002 |
| 2022-08-04 07:40:00 | 0 | 9 | train | 0 | 22.0 | 126.6 | -46.9 | 1.8 | 1.8 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-08-24 06:10:00 | 0 | 54985 | prediction | 3 | 25.0 | 101.8 | 5.4 | 3.4 | 0.0 |
| 2023-08-24 06:00:00 | 0 | 54984 | prediction | 3 | 25.0 | 104.4 | 8.0 | 3.1 | 0.0 |
| 2023-08-24 05:50:00 | 0 | 54983 | prediction | 3 | 25.0 | 114.5 | 18.2 | 2.7 | 0.0 |
| 2023-08-24 05:40:00 | 0 | 54982 | prediction | 3 | 25.0 | 117.2 | 20.9 | 2.8 | 0.0 |
| 2023-08-24 05:30:00 | 0 | 54981 | prediction | 3 | 25.0 | 121.0 | 24.6 | 3.3 | 0.0 |
| 2023-08-24 05:20:00 | 0 | 54980 | prediction | 3 | 25.0 | 120.9 | 24.6 | 4.4 | 0.0 |
| 2023-08-24 05:10:00 | 0 | 54979 | prediction | 3 | 25.0 | 117.8 | 21.4 | 5.2 | 0.0 |
| 2023-08-24 05:00:00 | 0 | 54978 | prediction | 3 | 25.0 | 110.8 | 14.5 | 6.0 | 0.0 |
| 2023-08-24 04:50:00 | 0 | 54977 | prediction | 3 | 25.0 | 106.0 | 9.6 | 6.3 | 0.0 |
| 2023-08-24 04:40:00 | 0 | 54976 | prediction | 3 | 25.0 | 101.0 | 4.6 | 5.8 | 0.0 |

---


## dbo.WFA_TURBINE_10_Data

**Primary Key:** EntryDateTime  
**Row Count:** 53,592  
**Date Range:** 2022-10-09 08:40:00 to 2023-10-18 08:40:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-10-09 08:40:00 | 10 | 0 | train | 4 | 20.0 | 265.7 | 19.4 | 2.6 | 2.6 |
| 2022-10-09 08:50:00 | 10 | 1 | train | 4 | 20.0 | 244.9 | -11.8 | 2.6 | 2.6 |
| 2022-10-09 09:00:00 | 10 | 2 | train | 4 | 20.0 | 299.5 | 42.7 | 2.5 | 2.5 |
| 2022-10-09 09:10:00 | 10 | 3 | train | 4 | 20.0 | 280.2 | 23.5 | 2.5 | 2.5 |
| 2022-10-09 09:20:00 | 10 | 4 | train | 4 | 20.0 | 281.1 | 24.3 | 2.7 | 2.7 |
| 2022-10-09 09:30:00 | 10 | 5 | train | 4 | 20.0 | 251.5 | -5.2 | 3.0 | 3.0 |
| 2022-10-09 09:40:00 | 10 | 6 | train | 4 | 20.0 | 246.2 | -25.6 | 2.9 | 2.9 |
| 2022-10-09 09:50:00 | 10 | 7 | train | 4 | 21.0 | 294.0 | 9.2 | 2.5 | 2.5 |
| 2022-10-09 10:00:00 | 10 | 8 | train | 4 | 20.0 | 301.6 | 16.8 | 2.4 | 2.4 |
| 2022-10-09 10:10:00 | 10 | 9 | train | 4 | 21.0 | 285.7 | 0.8 | 2.2 | 2.2 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-10-18 08:40:00 | 10 | 53591 | prediction | 3 | 19.0 | 272.4 | 6.0 | 3.5 | 3.5 |
| 2023-10-18 08:30:00 | 10 | 53590 | prediction | 4 | 18.0 | 279.1 | -6.3 | 7.6 | 6.9 |
| 2023-10-18 08:20:00 | 10 | 53589 | prediction | 4 | 19.0 | 285.9 | 5.9 | 9.2 | 9.0 |
| 2023-10-18 08:10:00 | 10 | 53588 | prediction | 4 | 19.0 | 260.8 | 2.8 | 9.7 | 9.6 |
| 2023-10-18 08:00:00 | 10 | 53587 | prediction | 4 | 20.0 | 261.6 | -3.8 | 7.9 | 7.7 |
| 2023-10-18 07:50:00 | 10 | 53586 | prediction | 4 | 21.0 | 269.2 | -1.9 | 7.8 | 7.7 |
| 2023-10-18 07:40:00 | 10 | 53585 | prediction | 4 | 21.0 | 271.1 | 0.0 | 7.4 | 7.4 |
| 2023-10-18 07:30:00 | 10 | 53584 | prediction | 4 | 21.0 | 268.7 | 0.0 | 8.1 | 8.1 |
| 2023-10-18 07:20:00 | 10 | 53583 | prediction | 4 | 21.0 | 263.5 | 0.4 | 7.0 | 7.2 |
| 2023-10-18 07:10:00 | 10 | 53582 | prediction | 4 | 21.0 | 262.6 | 2.3 | 6.2 | 6.2 |

---


## dbo.WFA_TURBINE_11_Data

**Primary Key:** EntryDateTime  
**Row Count:** 0  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

---


## dbo.WFA_TURBINE_13_Data

**Primary Key:** EntryDateTime  
**Row Count:** 54,010  
**Date Range:** 2022-04-30 13:20:00 to 2023-05-25 10:20:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-04-30 13:20:00 | 21 | 0 | train | 0 | 22.0 | 57.4 | -75.5 | 2.5 | 2.5 |
| 2022-04-30 13:30:00 | 21 | 1 | train | 0 | 23.0 | 93.0 | 31.4 | 2.2 | 2.2 |
| 2022-04-30 13:40:00 | 21 | 2 | train | 0 | 24.0 | 119.9 | 58.3 | 1.7000000000000002 | 1.7000000000000002 |
| 2022-04-30 13:50:00 | 21 | 3 | train | 0 | 24.0 | 65.2 | 3.6 | 1.2 | 1.2 |
| 2022-04-30 14:00:00 | 21 | 4 | train | 0 | 25.0 | 53.7 | -7.8 | 1.5 | 1.5 |
| 2022-04-30 14:10:00 | 21 | 5 | train | 0 | 22.0 | 36.5 | -24.8 | 5.7 | 5.6 |
| 2022-04-30 14:20:00 | 21 | 6 | train | 0 | 22.0 | 274.8 | -11.8 | 5.0 | 5.3 |
| 2022-04-30 14:30:00 | 21 | 7 | train | 0 | 22.0 | 247.2 | -17.3 | 5.4 | 5.5 |
| 2022-04-30 14:40:00 | 21 | 8 | train | 0 | 22.0 | 264.5 | -3.1 | 5.6 | 5.8 |
| 2022-04-30 14:50:00 | 21 | 9 | train | 0 | 22.0 | 249.5 | -20.2 | 4.8 | 4.9 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-05-25 10:20:00 | 21 | 54009 | prediction | 0 | 23.0 | 87.5 | -14.3 | 5.3 | 5.5 |
| 2023-05-25 10:10:00 | 21 | 54008 | prediction | 0 | 23.0 | 100.2 | -8.4 | 6.0 | 6.2 |
| 2023-05-25 10:00:00 | 21 | 54007 | prediction | 0 | 23.0 | 122.3 | 13.7 | 6.1 | 6.3 |
| 2023-05-25 09:50:00 | 21 | 54006 | prediction | 0 | 23.0 | 94.2 | -5.6 | 5.9 | 6.1 |
| 2023-05-25 09:40:00 | 21 | 54005 | prediction | 0 | 22.0 | 104.9 | 5.1 | 5.5 | 5.7 |
| 2023-05-25 09:30:00 | 21 | 54004 | prediction | 0 | 22.0 | 94.9 | 2.5 | 5.6 | 5.8 |
| 2023-05-25 09:20:00 | 21 | 54003 | prediction | 0 | 22.0 | 91.6 | -8.5 | 6.3 | 6.4 |
| 2023-05-25 09:10:00 | 21 | 54002 | prediction | 0 | 22.0 | 100.0 | -6.4 | 7.5 | 7.5 |
| 2023-05-25 09:00:00 | 21 | 54001 | prediction | 0 | 22.0 | 92.2 | 2.9 | 6.5 | 6.6 |
| 2023-05-25 08:50:00 | 21 | 54000 | prediction | 0 | 21.0 | 91.0 | 1.3 | 6.5 | 6.7 |

---


## dbo.WFA_TURBINE_14_Data

**Primary Key:** EntryDateTime  
**Row Count:** 54,197  
**Date Range:** 2022-03-03 14:00:00 to 2023-03-16 18:40:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-03-03 14:00:00 | 13 | 0 | train | 4 | 14.0 | 273.7 | -46.4 | 6.0 | 6.0 |
| 2022-03-03 14:10:00 | 13 | 1 | train | 4 | 14.0 | 259.5 | -60.6 | 6.0 | 0.0 |
| 2022-03-03 14:40:00 | 13 | 2 | train | 4 | 14.0 | 251.8 | -68.3 | 5.5 | 0.3 |
| 2022-03-03 14:50:00 | 13 | 3 | train | 4 | 14.0 | 263.3 | -56.7 | 5.4 | 5.4 |
| 2022-03-03 15:00:00 | 13 | 4 | train | 4 | 14.0 | 271.5 | 24.2 | 4.6 | 4.6 |
| 2022-03-03 15:10:00 | 13 | 5 | train | 4 | 14.0 | 230.1 | -17.1 | 4.7 | 4.7 |
| 2022-03-03 15:20:00 | 13 | 6 | train | 4 | 14.0 | 229.0 | -18.2 | 5.1 | 5.1 |
| 2022-03-03 15:30:00 | 13 | 7 | train | 4 | 14.0 | 268.9 | 21.7 | 4.3 | 4.3 |
| 2022-03-03 15:40:00 | 13 | 8 | train | 4 | 15.0 | 281.4 | 34.1 | 3.5 | 3.5 |
| 2022-03-03 15:50:00 | 13 | 9 | train | 4 | 14.0 | 245.5 | -1.7000000000000002 | 3.7 | 3.7 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-03-16 18:40:00 | 13 | 54196 | prediction | 0 | 16.0 | 108.0 | -1.8 | 10.0 | 10.3 |
| 2023-03-16 18:30:00 | 13 | 54195 | prediction | 0 | 16.0 | 111.7 | 1.8 | 11.1 | 11.2 |
| 2023-03-16 18:20:00 | 13 | 54194 | prediction | 0 | 16.0 | 105.6 | -4.3 | 9.6 | 9.9 |
| 2023-03-16 18:10:00 | 13 | 54193 | prediction | 0 | 16.0 | 130.7 | 14.5 | 9.3 | 9.5 |
| 2023-03-16 18:00:00 | 13 | 54192 | prediction | 0 | 16.0 | 118.1 | 3.7 | 8.9 | 9.1 |
| 2023-03-16 17:50:00 | 13 | 54191 | prediction | 0 | 16.0 | 104.1 | -5.4 | 8.5 | 8.7 |
| 2023-03-16 17:40:00 | 13 | 54190 | prediction | 0 | 16.0 | 129.1 | 19.6 | 8.5 | 8.7 |
| 2023-03-16 17:30:00 | 13 | 54189 | prediction | 0 | 16.0 | 95.3 | -14.1 | 8.9 | 9.2 |
| 2023-03-16 17:20:00 | 13 | 54188 | prediction | 0 | 16.0 | 122.1 | 13.3 | 9.9 | 10.1 |
| 2023-03-16 17:10:00 | 13 | 54187 | prediction | 0 | 16.0 | 76.0 | -32.7 | 8.5 | 8.6 |

---


## dbo.WFA_TURBINE_17_Data

**Primary Key:** EntryDateTime  
**Row Count:** 55,090  
**Date Range:** 2022-10-31 15:20:00 to 2023-11-20 00:40:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-10-31 15:20:00 | 10 | 0 | train | 0 | 23.0 | 91.8 | -23.0 | 11.9 | 11.0 |
| 2022-10-31 15:30:00 | 10 | 1 | train | 0 | 23.0 | 113.6 | 6.8 | 11.3 | 10.7 |
| 2022-10-31 15:40:00 | 10 | 2 | train | 0 | 23.0 | 120.8 | 14.0 | 12.0 | 11.5 |
| 2022-10-31 15:50:00 | 10 | 3 | train | 0 | 23.0 | 103.1 | -3.6 | 11.1 | 10.6 |
| 2022-10-31 16:00:00 | 10 | 4 | train | 0 | 23.0 | 106.3 | -0.4 | 11.1 | 10.6 |
| 2022-10-31 16:10:00 | 10 | 5 | train | 0 | 23.0 | 111.5 | 4.8 | 10.7 | 10.1 |
| 2022-10-31 16:20:00 | 10 | 6 | train | 0 | 23.0 | 89.7 | -14.5 | 11.3 | 10.7 |
| 2022-10-31 16:30:00 | 10 | 7 | train | 0 | 23.0 | 99.3 | -12.7 | 12.2 | 11.4 |
| 2022-10-31 16:40:00 | 10 | 8 | train | 0 | 23.0 | 100.0 | -12.0 | 9.6 | 9.3 |
| 2022-10-31 16:50:00 | 10 | 9 | train | 0 | 23.0 | 102.2 | -9.8 | 9.6 | 9.2 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-11-20 00:40:00 | 10 | 55089 | prediction | 0 | 17.0 | 98.2 | -3.0 | 9.5 | 9.1 |
| 2023-11-20 00:30:00 | 10 | 55088 | prediction | 0 | 17.0 | 100.2 | 4.1 | 10.1 | 9.7 |
| 2023-11-20 00:20:00 | 10 | 55087 | prediction | 0 | 17.0 | 97.6 | 4.5 | 9.3 | 9.4 |
| 2023-11-20 00:10:00 | 10 | 55086 | prediction | 0 | 17.0 | 97.4 | 4.3 | 10.1 | 10.0 |
| 2023-11-20 00:00:00 | 10 | 55085 | prediction | 0 | 17.0 | 93.4 | 0.4 | 10.5 | 10.3 |
| 2023-11-19 23:50:00 | 10 | 55084 | prediction | 0 | 17.0 | 93.3 | 0.2 | 10.8 | 10.9 |
| 2023-11-19 23:40:00 | 10 | 55083 | prediction | 0 | 17.0 | 96.1 | 3.0 | 11.1 | 11.0 |
| 2023-11-19 23:30:00 | 10 | 55082 | prediction | 0 | 17.0 | 90.9 | -2.1 | 10.9 | 10.8 |
| 2023-11-19 23:20:00 | 10 | 55081 | prediction | 0 | 17.0 | 90.8 | -2.0 | 10.6 | 10.4 |
| 2023-11-19 23:10:00 | 10 | 55080 | prediction | 0 | 17.0 | 88.6 | -4.1 | 10.4 | 10.1 |

---


## dbo.WFA_TURBINE_21_Data

**Primary Key:** EntryDateTime  
**Row Count:** 0  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

---


## dbo.WFA_TURBINE_22_Data

**Primary Key:** EntryDateTime  
**Row Count:** 53,036  
**Date Range:** 2022-08-12 09:50:00 to 2023-08-20 09:50:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-08-12 09:50:00 | 21 | 0 | train | 0 | 25.0 | 105.9 | 7.5 | 18.4 | 17.2 |
| 2022-08-12 10:00:00 | 21 | 1 | train | 0 | 25.0 | 107.9 | 9.5 | 18.6 | 17.5 |
| 2022-08-12 10:10:00 | 21 | 2 | train | 0 | 25.0 | 124.8 | 26.4 | 18.3 | 17.2 |
| 2022-08-12 10:20:00 | 21 | 3 | train | 0 | 25.0 | 114.1 | 15.8 | 18.8 | 17.6 |
| 2022-08-12 10:30:00 | 21 | 4 | train | 0 | 26.0 | 100.9 | 2.5 | 18.7 | 17.5 |
| 2022-08-12 10:40:00 | 21 | 5 | train | 0 | 26.0 | 85.8 | -12.9 | 17.6 | 16.5 |
| 2022-08-12 10:50:00 | 21 | 6 | train | 0 | 26.0 | 91.9 | -6.5 | 18.3 | 17.1 |
| 2022-08-12 11:00:00 | 21 | 7 | train | 0 | 26.0 | 99.5 | -5.9 | 18.7 | 17.8 |
| 2022-08-12 11:10:00 | 21 | 8 | train | 0 | 26.0 | 103.2 | -1.5 | 19.3 | 18.1 |
| 2022-08-12 11:20:00 | 21 | 9 | train | 0 | 26.0 | 109.4 | 12.4 | 18.0 | 17.0 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-08-20 09:50:00 | 21 | 53035 | prediction | 3 | 27.0 | 89.2 | -1.1 | 10.7 | 10.4 |
| 2023-08-20 09:40:00 | 21 | 53034 | prediction | 3 | 27.0 | 86.5 | -3.8 | 10.6 | 10.4 |
| 2023-08-20 09:30:00 | 21 | 53033 | prediction | 3 | 26.0 | 87.3 | -3.0 | 11.8 | 11.4 |
| 2023-08-20 09:20:00 | 21 | 53032 | prediction | 3 | 26.0 | 89.0 | -1.3 | 10.7 | 10.4 |
| 2023-08-20 09:10:00 | 21 | 53031 | prediction | 3 | 26.0 | 90.4 | 0.1 | 10.4 | 10.1 |
| 2023-08-20 09:00:00 | 21 | 53030 | prediction | 3 | 26.0 | 89.2 | -1.1 | 11.3 | 10.9 |
| 2023-08-20 08:50:00 | 21 | 53029 | prediction | 3 | 26.0 | 88.9 | -1.4 | 11.2 | 10.8 |
| 2023-08-20 08:40:00 | 21 | 53028 | prediction | 3 | 26.0 | 88.2 | -2.1 | 10.4 | 10.2 |
| 2023-08-20 08:30:00 | 21 | 53027 | prediction | 3 | 26.0 | 88.9 | -1.4 | 9.6 | 9.4 |
| 2023-08-20 08:20:00 | 21 | 53026 | prediction | 3 | 26.0 | 89.7 | -0.6000000000000001 | 9.4 | 9.3 |

---


## dbo.WFA_TURBINE_24_Data

**Primary Key:** EntryDateTime  
**Row Count:** 55,003  
**Date Range:** 2022-04-24 15:00:00 to 2023-05-13 11:20:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-04-24 15:00:00 | 0 | 0 | train | 4 | 25.0 | 317.8 | -1.9 | 3.2 | 3.2 |
| 2022-04-24 15:10:00 | 0 | 1 | train | 4 | 25.0 | 2.5 | 15.5 | 4.0 | 3.9 |
| 2022-04-24 15:20:00 | 0 | 2 | train | 4 | 26.0 | 17.3 | 13.9 | 3.1 | 2.9 |
| 2022-04-24 15:30:00 | 0 | 3 | train | 4 | 26.0 | 47.1 | 67.8 | 4.2 | 4.3 |
| 2022-04-24 15:40:00 | 0 | 4 | train | 4 | 26.0 | 329.3 | -9.6 | 3.1 | 3.0 |
| 2022-04-24 15:50:00 | 0 | 5 | train | 4 | 26.0 | 11.1 | 28.3 | 4.6 | 4.5 |
| 2022-04-24 16:00:00 | 0 | 6 | train | 4 | 25.0 | 329.3 | 6.6 | 5.1 | 4.9 |
| 2022-04-24 16:10:00 | 0 | 7 | train | 4 | 25.0 | 281.2 | -11.8 | 6.2 | 6.0 |
| 2022-04-24 16:20:00 | 0 | 8 | train | 4 | 24.0 | 286.7 | -27.6 | 7.5 | 7.3 |
| 2022-04-24 16:30:00 | 0 | 9 | train | 4 | 24.0 | 288.7 | 2.4 | 9.1 | 9.0 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-05-13 11:20:00 | 0 | 55002 | prediction | 0 | 20.0 | 204.7 | -3.5 | 4.8 | 5.0 |
| 2023-05-13 11:10:00 | 0 | 55001 | prediction | 0 | 20.0 | 208.2 | 4.2 | 4.5 | 4.6 |
| 2023-05-13 11:00:00 | 0 | 55000 | prediction | 0 | 20.0 | 203.1 | -16.3 | 5.8 | 5.8 |
| 2023-05-13 10:50:00 | 0 | 54999 | prediction | 0 | 20.0 | 202.0 | -4.1 | 4.5 | 4.7 |
| 2023-05-13 10:40:00 | 0 | 54998 | prediction | 0 | 20.0 | 241.7 | 22.3 | 3.3 | 3.4 |
| 2023-05-13 10:30:00 | 0 | 54997 | prediction | 0 | 19.0 | 256.9 | 42.4 | 2.6 | 2.6 |
| 2023-05-13 10:20:00 | 0 | 54996 | prediction | 0 | 19.0 | 221.7 | 7.2 | 2.3 | 2.3 |
| 2023-05-13 10:10:00 | 0 | 54995 | prediction | 0 | 19.0 | 247.1 | 16.5 | 2.4 | 2.4 |
| 2023-05-13 10:00:00 | 0 | 54994 | prediction | 0 | 18.0 | 233.1 | 22.8 | 2.8 | 2.8 |
| 2023-05-13 09:50:00 | 0 | 54993 | prediction | 0 | 18.0 | 197.7 | 1.5 | 2.8 | 2.8 |

---


## dbo.WFA_TURBINE_25_Data

**Primary Key:** EntryDateTime  
**Row Count:** 54,712  
**Date Range:** 2022-05-23 06:50:00 to 2023-06-09 02:30:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-05-23 06:50:00 | 11 | 0 | train | 0 | 18.0 | 161.3 | 156.2 | 2.4 | 2.4 |
| 2022-05-23 07:00:00 | 11 | 1 | train | 0 | 18.0 | 172.3 | 167.1 | 2.8 | 2.8 |
| 2022-05-23 07:10:00 | 11 | 2 | train | 0 | 18.0 | 173.0 | 41.0 | 3.1 | 3.1 |
| 2022-05-23 07:20:00 | 11 | 3 | train | 0 | 18.0 | 168.4 | 5.6 | 2.4 | 2.4 |
| 2022-05-23 07:30:00 | 11 | 4 | train | 0 | 18.0 | 155.4 | -18.6 | 2.3 | 2.3 |
| 2022-05-23 07:40:00 | 11 | 5 | train | 0 | 18.0 | 190.8 | 16.8 | 2.4 | 2.4 |
| 2022-05-23 07:50:00 | 11 | 6 | train | 0 | 17.0 | 135.2 | -38.7 | 2.8 | 2.8 |
| 2022-05-23 08:00:00 | 11 | 7 | train | 0 | 16.0 | 149.3 | -2.6 | 2.9 | 2.9 |
| 2022-05-23 08:10:00 | 11 | 8 | train | 0 | 16.0 | 133.2 | -16.2 | 2.6 | 2.6 |
| 2022-05-23 08:20:00 | 11 | 9 | train | 0 | 16.0 | 144.0 | -6.8 | 2.7 | 2.7 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-06-09 02:30:00 | 11 | 54711 | prediction | 0 | 23.0 | 103.5 | -8.8 | 4.3 | 4.1 |
| 2023-06-09 02:20:00 | 11 | 54710 | prediction | 0 | 23.0 | 108.7 | -1.5 | 5.0 | 4.8 |
| 2023-06-09 02:10:00 | 11 | 54709 | prediction | 0 | 23.0 | 112.0 | 1.8 | 6.5 | 6.3 |
| 2023-06-09 02:00:00 | 11 | 54708 | prediction | 0 | 23.0 | 123.1 | 12.9 | 5.9 | 5.8 |
| 2023-06-09 01:50:00 | 11 | 54707 | prediction | 0 | 23.0 | 97.8 | -12.3 | 7.0 | 6.8 |
| 2023-06-09 01:40:00 | 11 | 54706 | prediction | 0 | 23.0 | 107.9 | 5.8 | 8.1 | 7.9 |
| 2023-06-09 01:30:00 | 11 | 54705 | prediction | 0 | 23.0 | 104.8 | 2.7 | 8.9 | 8.6 |
| 2023-06-09 01:20:00 | 11 | 54704 | prediction | 0 | 23.0 | 104.1 | 2.0 | 8.8 | 8.7 |
| 2023-06-09 01:10:00 | 11 | 54703 | prediction | 0 | 23.0 | 96.2 | -5.9 | 9.0 | 8.7 |
| 2023-06-09 01:00:00 | 11 | 54702 | prediction | 0 | 23.0 | 105.8 | 3.7 | 9.2 | 9.0 |

---


## dbo.WFA_TURBINE_26_Data

**Primary Key:** EntryDateTime  
**Row Count:** 53,702  
**Date Range:** 2022-10-12 10:20:00 to 2023-10-22 10:20:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-10-12 10:20:00 | 0 | 0 | train | 0 | 17.0 | 184.0 | -10.8 | 13.2 | 13.4 |
| 2022-10-12 10:30:00 | 0 | 1 | train | 0 | 17.0 | 188.3 | -6.2 | 13.6 | 14.0 |
| 2022-10-12 10:40:00 | 0 | 2 | train | 0 | 17.0 | 186.0 | -8.4 | 12.7 | 13.2 |
| 2022-10-12 10:50:00 | 0 | 3 | train | 0 | 18.0 | 190.8 | -3.7 | 13.4 | 13.8 |
| 2022-10-12 11:00:00 | 0 | 4 | train | 0 | 17.0 | 205.0 | 10.5 | 12.7 | 12.9 |
| 2022-10-12 11:10:00 | 0 | 5 | train | 0 | 17.0 | 192.7 | -1.8 | 12.4 | 12.9 |
| 2022-10-12 11:20:00 | 0 | 6 | train | 0 | 17.0 | 177.5 | -17.3 | 12.3 | 12.8 |
| 2022-10-12 11:30:00 | 0 | 7 | train | 0 | 17.0 | 177.1 | -17.7 | 13.1 | 13.3 |
| 2022-10-12 11:40:00 | 0 | 8 | train | 0 | 16.0 | 198.1 | 3.2 | 13.2 | 13.4 |
| 2022-10-12 11:50:00 | 0 | 9 | train | 0 | 17.0 | 221.3 | 32.8 | 12.6 | 13.1 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-10-22 10:20:00 | 0 | 53701 | prediction | 0 | 20.0 | 59.6 | 7.4 | 1.4 | 1.4 |
| 2023-10-22 10:10:00 | 0 | 53700 | prediction | 3 | 19.0 | 34.8 | -17.3 | 1.7000000000000002 | 1.7000000000000002 |
| 2023-10-22 10:00:00 | 0 | 53699 | prediction | 3 | 20.0 | 40.0 | -12.2 | 2.0 | 2.0 |
| 2023-10-22 09:50:00 | 0 | 53698 | prediction | 3 | 20.0 | 88.5 | 36.3 | 1.6 | 1.6 |
| 2023-10-22 09:40:00 | 0 | 53697 | prediction | 3 | 21.0 | 117.8 | 65.6 | 1.4 | 1.4 |
| 2023-10-22 09:30:00 | 0 | 53696 | prediction | 3 | 21.0 | 110.5 | 58.3 | 0.9 | 0.9 |
| 2023-10-22 09:20:00 | 0 | 53695 | prediction | 3 | 21.0 | 261.4 | -150.7 | 0.7000000000000001 | 0.7000000000000001 |
| 2023-10-22 09:10:00 | 0 | 53694 | prediction | 3 | 20.0 | 283.8 | -128.3 | 1.0 | 1.0 |
| 2023-10-22 09:00:00 | 0 | 53693 | prediction | 3 | 22.0 | 200.4 | 148.2 | 1.0 | 1.0 |
| 2023-10-22 08:50:00 | 0 | 53692 | prediction | 3 | 20.0 | 190.9 | 138.7 | 1.0 | 1.0 |

---


## dbo.WFA_TURBINE_38_Data

**Primary Key:** EntryDateTime  
**Row Count:** 54,835  
**Date Range:** 2022-06-28 15:40:00 to 2023-07-17 07:40:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-06-28 15:40:00 | 13 | 0 | train | 0 | 28.0 | 95.7 | -21.4 | 5.7 | 5.9 |
| 2022-06-28 15:50:00 | 13 | 1 | train | 0 | 28.0 | 95.1 | -15.1 | 7.2 | 7.4 |
| 2022-06-28 16:00:00 | 13 | 2 | train | 0 | 28.0 | 118.3 | 7.7 | 6.2 | 6.3 |
| 2022-06-28 16:10:00 | 13 | 3 | train | 0 | 28.0 | 124.7 | 3.3 | 6.6 | 6.4 |
| 2022-06-28 16:20:00 | 13 | 4 | train | 0 | 27.0 | 104.4 | -0.8 | 7.3 | 7.2 |
| 2022-06-28 16:30:00 | 13 | 5 | train | 0 | 27.0 | 82.4 | -13.4 | 7.1 | 7.1 |
| 2022-06-28 16:40:00 | 13 | 6 | train | 0 | 27.0 | 101.4 | 5.6 | 7.1 | 7.0 |
| 2022-06-28 16:50:00 | 13 | 7 | train | 0 | 28.0 | 93.4 | -2.4 | 6.3 | 6.1 |
| 2022-06-28 17:00:00 | 13 | 8 | train | 0 | 28.0 | 91.6 | 3.4 | 6.4 | 6.6 |
| 2022-06-28 17:10:00 | 13 | 9 | train | 0 | 28.0 | 90.5 | -4.9 | 6.9 | 6.9 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-07-17 07:40:00 | 13 | 54834 | prediction | 0 | 25.0 | 105.9 | -0.7000000000000001 | 7.3 | 7.3 |
| 2023-07-17 07:30:00 | 13 | 54833 | prediction | 0 | 25.0 | 94.6 | 0.6000000000000001 | 3.9 | 3.9 |
| 2023-07-17 07:20:00 | 13 | 54832 | prediction | 0 | 25.0 | 101.6 | 7.6 | 9.1 | 9.0 |
| 2023-07-17 07:10:00 | 13 | 54831 | prediction | 0 | 25.0 | 92.6 | -1.4 | 8.4 | 8.3 |
| 2023-07-17 07:00:00 | 13 | 54830 | prediction | 0 | 25.0 | 92.5 | -8.8 | 7.5 | 7.1 |
| 2023-07-17 06:50:00 | 13 | 54829 | prediction | 0 | 25.0 | 100.8 | 6.4 | 6.2 | 6.0 |
| 2023-07-17 06:40:00 | 13 | 54828 | prediction | 0 | 25.0 | 92.0 | -2.4 | 6.3 | 6.1 |
| 2023-07-17 06:30:00 | 13 | 54827 | prediction | 0 | 25.0 | 99.4 | -1.6 | 6.3 | 5.9 |
| 2023-07-17 06:20:00 | 13 | 54826 | prediction | 0 | 25.0 | 95.1 | 3.2 | 5.4 | 5.3 |
| 2023-07-17 06:10:00 | 13 | 54825 | prediction | 0 | 25.0 | 106.5 | 14.6 | 5.5 | 5.4 |

---


## dbo.WFA_TURBINE_3_Data

**Primary Key:** EntryDateTime  
**Row Count:** 55,487  
**Date Range:** 2022-04-27 03:00:00 to 2023-05-20 01:10:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-04-27 03:00:00 | 10 | 0 | train | 0 | 18.0 | 75.0 | 89.9 | 1.0 | 1.0 |
| 2022-04-27 03:10:00 | 10 | 1 | train | 0 | 18.0 | 154.6 | 169.5 | 1.5 | 1.5 |
| 2022-04-27 03:20:00 | 10 | 2 | train | 0 | 18.0 | 248.8 | -96.3 | 1.3 | 1.3 |
| 2022-04-27 03:30:00 | 10 | 3 | train | 0 | 18.0 | 234.7 | -110.4 | 1.6 | 1.6 |
| 2022-04-27 03:40:00 | 10 | 4 | train | 0 | 18.0 | 334.6 | -10.5 | 2.0 | 2.0 |
| 2022-04-27 03:50:00 | 10 | 5 | train | 0 | 18.0 | 233.0 | -112.1 | 2.3 | 2.3 |
| 2022-04-27 04:00:00 | 10 | 6 | train | 0 | 18.0 | 270.8 | -74.2 | 2.7 | 2.7 |
| 2022-04-27 04:10:00 | 10 | 7 | train | 0 | 18.0 | 299.1 | 22.3 | 2.5 | 2.5 |
| 2022-04-27 04:20:00 | 10 | 8 | train | 0 | 18.0 | 291.4 | 14.7 | 2.3 | 2.3 |
| 2022-04-27 04:30:00 | 10 | 9 | train | 0 | 17.0 | 245.5 | -31.2 | 2.0 | 2.0 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-05-20 01:10:00 | 10 | 55486 | prediction | 0 | 19.0 | 96.7 | 0.2 | 8.4 | 8.3 |
| 2023-05-20 01:00:00 | 10 | 55485 | prediction | 0 | 19.0 | 111.2 | 14.6 | 8.3 | 8.2 |
| 2023-05-20 00:50:00 | 10 | 55484 | prediction | 0 | 19.0 | 83.3 | -13.2 | 8.3 | 8.1 |
| 2023-05-20 00:40:00 | 10 | 55483 | prediction | 0 | 19.0 | 91.5 | -5.0 | 9.3 | 8.9 |
| 2023-05-20 00:30:00 | 10 | 55482 | prediction | 0 | 19.0 | 97.3 | 0.7000000000000001 | 8.4 | 8.2 |
| 2023-05-20 00:20:00 | 10 | 55481 | prediction | 0 | 19.0 | 95.1 | -1.4 | 8.2 | 7.9 |
| 2023-05-20 00:10:00 | 10 | 55480 | prediction | 0 | 19.0 | 91.5 | -13.1 | 5.9 | 5.8 |
| 2023-05-20 00:00:00 | 10 | 55479 | prediction | 0 | 19.0 | 102.3 | -1.3 | 5.3 | 5.2 |
| 2023-05-19 23:50:00 | 10 | 55478 | prediction | 0 | 19.0 | 101.8 | -1.8 | 5.4 | 5.2 |
| 2023-05-19 23:40:00 | 10 | 55477 | prediction | 0 | 19.0 | 110.2 | 6.6 | 5.8 | 5.6 |

---


## dbo.WFA_TURBINE_40_Data

**Primary Key:** EntryDateTime  
**Row Count:** 56,158  
**Date Range:** 2022-01-01 00:00:00 to 2023-01-28 13:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-01-01 00:00:00 | 10 | 0 | train | 0 | 18.0 | 220.1 | 6.1 | 5.2 | 5.1 |
| 2022-01-01 00:10:00 | 10 | 1 | train | 0 | 18.0 | 218.7 | 4.7 | 5.7 | 5.3 |
| 2022-01-01 00:20:00 | 10 | 2 | train | 0 | 18.0 | 216.7 | 2.7 | 6.2 | 5.8 |
| 2022-01-01 00:30:00 | 10 | 3 | train | 0 | 18.0 | 197.9 | -16.1 | 6.3 | 6.2 |
| 2022-01-01 00:40:00 | 10 | 4 | train | 0 | 18.0 | 217.2 | 3.2 | 6.6 | 6.1 |
| 2022-01-01 00:50:00 | 10 | 5 | train | 0 | 18.0 | 215.1 | 1.1 | 6.7 | 6.5 |
| 2022-01-01 01:00:00 | 10 | 6 | train | 0 | 18.0 | 219.6 | 5.6 | 5.5 | 5.3 |
| 2022-01-01 01:10:00 | 10 | 7 | train | 0 | 18.0 | 212.8 | -1.2 | 4.2 | 4.4 |
| 2022-01-01 01:20:00 | 10 | 8 | train | 0 | 18.0 | 230.9 | 11.3 | 5.2 | 5.1 |
| 2022-01-01 01:30:00 | 10 | 9 | train | 0 | 18.0 | 228.2 | 15.6 | 4.6 | 4.6 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-01-28 13:00:00 | 10 | 56157 | prediction | 3 | 15.0 | 318.3 | 38.4 | 10.3 | 10.3 |
| 2023-01-28 12:50:00 | 10 | 56156 | prediction | 3 | 14.0 | 317.3 | 37.4 | 6.9 | 6.9 |
| 2023-01-28 12:40:00 | 10 | 56155 | prediction | 3 | 13.0 | 318.5 | 38.6 | 6.0 | 6.0 |
| 2023-01-28 12:30:00 | 10 | 56154 | prediction | 3 | 13.0 | 325.6 | 45.7 | 7.9 | 7.9 |
| 2023-01-28 12:20:00 | 10 | 56153 | prediction | 3 | 12.0 | 337.5 | 57.5 | 9.3 | 9.3 |
| 2023-01-28 12:10:00 | 10 | 56152 | prediction | 3 | 13.0 | 332.0 | 52.1 | 8.9 | 8.9 |
| 2023-01-28 12:00:00 | 10 | 56151 | prediction | 3 | 15.0 | 282.8 | 2.9 | 7.9 | 7.9 |
| 2023-01-28 11:50:00 | 10 | 56150 | prediction | 3 | 15.0 | 292.8 | 12.8 | 9.8 | 9.8 |
| 2023-01-28 11:40:00 | 10 | 56149 | prediction | 3 | 15.0 | 286.5 | 6.5 | 10.9 | 10.9 |
| 2023-01-28 11:30:00 | 10 | 56148 | prediction | 3 | 16.0 | 283.5 | 3.6 | 10.1 | 10.1 |

---


## dbo.WFA_TURBINE_42_Data

**Primary Key:** EntryDateTime  
**Row Count:** 53,886  
**Date Range:** 2022-09-09 15:50:00 to 2023-09-20 15:50:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-09-09 15:50:00 | 10 | 0 | train | 0 | 28.0 | 298.4 | 21.7 | 5.4 | 5.1 |
| 2022-09-09 16:00:00 | 10 | 1 | train | 0 | 28.0 | 261.6 | -11.9 | 4.2 | 4.1 |
| 2022-09-09 16:10:00 | 10 | 2 | train | 0 | 28.0 | 278.1 | 23.3 | 5.1 | 5.1 |
| 2022-09-09 16:20:00 | 10 | 3 | train | 0 | 28.0 | 260.2 | -19.0 | 5.4 | 5.1 |
| 2022-09-09 16:30:00 | 10 | 4 | train | 0 | 27.0 | 243.5 | -38.5 | 5.1 | 4.9 |
| 2022-09-09 16:40:00 | 10 | 5 | train | 0 | 27.0 | 267.4 | -16.7 | 5.7 | 5.5 |
| 2022-09-09 16:50:00 | 10 | 6 | train | 0 | 27.0 | 287.3 | 3.2 | 5.2 | 5.1 |
| 2022-09-09 17:00:00 | 10 | 7 | train | 0 | 26.0 | 270.7 | -4.7 | 5.7 | 5.5 |
| 2022-09-09 17:10:00 | 10 | 8 | train | 0 | 26.0 | 310.9 | 28.5 | 5.7 | 5.4 |
| 2022-09-09 17:20:00 | 10 | 9 | train | 0 | 26.0 | 278.8 | -18.2 | 5.1 | 5.0 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-09-20 15:50:00 | 10 | 53885 | prediction | 0 | 29.0 | 128.3 | 3.1 | 5.9 | 5.8 |
| 2023-09-20 15:40:00 | 10 | 53884 | prediction | 0 | 29.0 | 124.4 | -6.9 | 6.3 | 5.9 |
| 2023-09-20 15:30:00 | 10 | 53883 | prediction | 0 | 29.0 | 137.0 | 1.4 | 7.0 | 6.9 |
| 2023-09-20 15:20:00 | 10 | 53882 | prediction | 0 | 29.0 | 130.1 | -1.2 | 7.0 | 6.7 |
| 2023-09-20 15:10:00 | 10 | 53881 | prediction | 0 | 29.0 | 130.8 | 0.0 | 7.5 | 7.1 |
| 2023-09-20 15:00:00 | 10 | 53880 | prediction | 0 | 29.0 | 134.1 | 3.8 | 7.9 | 7.7 |
| 2023-09-20 14:50:00 | 10 | 53879 | prediction | 0 | 29.0 | 125.7 | -1.0 | 7.1 | 6.8 |
| 2023-09-20 14:40:00 | 10 | 53878 | prediction | 0 | 29.0 | 141.5 | -1.1 | 7.1 | 6.8 |
| 2023-09-20 14:30:00 | 10 | 53877 | prediction | 0 | 29.0 | 140.1 | 3.0 | 6.6 | 6.3 |
| 2023-09-20 14:20:00 | 10 | 53876 | prediction | 0 | 29.0 | 129.9 | -2.6 | 6.7 | 6.4 |

---


## dbo.WFA_TURBINE_45_Data

**Primary Key:** EntryDateTime  
**Row Count:** 53,739  
**Date Range:** 2022-04-16 18:10:00 to 2023-04-26 18:10:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-04-16 18:10:00 | 13 | 0 | train | 0 | 18.0 | 216.1 | -15.7 | 10.0 | 10.2 |
| 2022-04-16 18:20:00 | 13 | 1 | train | 0 | 18.0 | 240.3 | 7.4 | 9.8 | 9.9 |
| 2022-04-16 18:30:00 | 13 | 2 | train | 0 | 18.0 | 223.8 | -9.1 | 10.5 | 10.6 |
| 2022-04-16 18:40:00 | 13 | 3 | train | 0 | 18.0 | 216.8 | -9.1 | 9.4 | 9.6 |
| 2022-04-16 18:50:00 | 13 | 4 | train | 0 | 18.0 | 239.8 | 5.1 | 8.8 | 9.1 |
| 2022-04-16 19:00:00 | 13 | 5 | train | 0 | 18.0 | 222.1 | -10.4 | 8.8 | 9.1 |
| 2022-04-16 19:10:00 | 13 | 6 | train | 0 | 18.0 | 248.2 | 15.7 | 9.5 | 9.7 |
| 2022-04-16 19:20:00 | 13 | 7 | train | 0 | 18.0 | 257.0 | 24.5 | 9.3 | 9.7 |
| 2022-04-16 19:30:00 | 13 | 8 | train | 0 | 18.0 | 235.3 | 2.8 | 9.4 | 9.6 |
| 2022-04-16 19:40:00 | 13 | 9 | train | 0 | 18.0 | 232.3 | -0.2 | 9.1 | 9.4 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-04-26 18:10:00 | 13 | 53738 | prediction | 3 | 19.0 | 287.4 | 32.8 | 5.5 | 5.5 |
| 2023-04-26 18:00:00 | 13 | 53737 | prediction | 4 | 19.0 | 264.9 | 10.3 | 5.8 | 5.8 |
| 2023-04-26 17:50:00 | 13 | 53736 | prediction | 4 | 19.0 | 255.9 | 1.3 | 6.0 | 6.0 |
| 2023-04-26 17:40:00 | 13 | 53735 | prediction | 4 | 18.0 | 267.1 | 12.4 | 6.0 | 6.0 |
| 2023-04-26 17:30:00 | 13 | 53734 | prediction | 4 | 19.0 | 235.7 | -18.9 | 5.4 | 5.4 |
| 2023-04-26 17:20:00 | 13 | 53733 | prediction | 4 | 19.0 | 248.5 | -6.0 | 5.5 | 5.5 |
| 2023-04-26 17:10:00 | 13 | 53732 | prediction | 4 | 19.0 | 262.6 | 8.0 | 6.1 | 6.1 |
| 2023-04-26 17:00:00 | 13 | 53731 | prediction | 4 | 19.0 | 238.6 | -16.0 | 6.4 | 6.4 |
| 2023-04-26 16:50:00 | 13 | 53730 | prediction | 4 | 19.0 | 261.9 | 7.3 | 5.9 | 5.9 |
| 2023-04-26 16:40:00 | 13 | 53729 | prediction | 4 | 19.0 | 242.8 | -11.8 | 6.4 | 6.4 |

---


## dbo.WFA_TURBINE_51_Data

**Primary Key:** EntryDateTime  
**Row Count:** 54,436  
**Date Range:** 2022-10-04 01:30:00 to 2023-10-20 16:10:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-10-04 01:30:00 | 21 | 0 | train | 3 | 23.0 | 113.8 | 11.6 | 5.0 | 5.2 |
| 2022-10-04 01:40:00 | 21 | 1 | train | 3 | 23.0 | 106.5 | 4.2 | 4.7 | 4.7 |
| 2022-10-04 01:50:00 | 21 | 2 | train | 3 | 23.0 | 104.9 | -4.0 | 5.9 | 5.9 |
| 2022-10-04 02:00:00 | 21 | 3 | train | 3 | 23.0 | 109.2 | 15.7 | 5.8 | 5.9 |
| 2022-10-04 02:10:00 | 21 | 4 | train | 3 | 23.0 | 87.4 | 2.0 | 6.1 | 6.1 |
| 2022-10-04 02:20:00 | 21 | 5 | train | 3 | 23.0 | 95.0 | 9.6 | 5.9 | 6.0 |
| 2022-10-04 02:30:00 | 21 | 6 | train | 3 | 23.0 | 78.6 | -6.8 | 5.9 | 6.0 |
| 2022-10-04 02:40:00 | 21 | 7 | train | 3 | 23.0 | 85.1 | -0.3 | 6.4 | 6.6 |
| 2022-10-04 02:50:00 | 21 | 8 | train | 3 | 23.0 | 101.1 | 8.3 | 7.1 | 7.3 |
| 2022-10-04 03:00:00 | 21 | 9 | train | 3 | 23.0 | 84.4 | -8.4 | 7.5 | 7.7 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-10-20 16:10:00 | 21 | 54435 | prediction | 0 | 24.0 | 292.4 | -3.6 | 4.8 | 5.0 |
| 2023-10-20 16:00:00 | 21 | 54434 | prediction | 0 | 24.0 | 289.2 | 3.6 | 4.6 | 4.8 |
| 2023-10-20 15:50:00 | 21 | 54433 | prediction | 0 | 24.0 | 287.4 | -2.4 | 3.6 | 3.8 |
| 2023-10-20 15:40:00 | 21 | 54432 | prediction | 0 | 24.0 | 286.5 | 0.3 | 4.0 | 4.2 |
| 2023-10-20 15:30:00 | 21 | 54431 | prediction | 0 | 24.0 | 296.0 | 1.1 | 4.5 | 4.6 |
| 2023-10-20 15:20:00 | 21 | 54430 | prediction | 0 | 24.0 | 289.5 | -2.7 | 3.1 | 3.1 |
| 2023-10-20 15:10:00 | 21 | 54429 | prediction | 0 | 24.0 | 288.2 | 5.1 | 3.5 | 3.6 |
| 2023-10-20 15:00:00 | 21 | 54428 | prediction | 0 | 24.0 | 292.1 | -1.1 | 3.9 | 4.0 |
| 2023-10-20 14:50:00 | 21 | 54427 | prediction | 0 | 24.0 | 288.0 | -4.7 | 3.2 | 3.2 |
| 2023-10-20 14:40:00 | 21 | 54426 | prediction | 0 | 24.0 | 301.6 | 2.5 | 3.6 | 3.7 |

---


## dbo.WFA_TURBINE_68_Data

**Primary Key:** EntryDateTime  
**Row Count:** 54,358  
**Date Range:** 2022-07-28 13:20:00 to 2023-08-13 13:20:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-07-28 13:20:00 | 11 | 0 | train | 0 | 31.0 | 152.0 | 48.7 | 3.9 | 3.9 |
| 2022-07-28 13:30:00 | 11 | 1 | train | 0 | 31.0 | 86.1 | 150.9 | 6.0 | 6.0 |
| 2022-07-28 13:40:00 | 11 | 2 | train | 0 | 31.0 | 115.2 | 69.6 | 6.3 | 6.3 |
| 2022-07-28 13:50:00 | 11 | 3 | train | 0 | 32.0 | 129.3 | -29.1 | 6.0 | 5.9 |
| 2022-07-28 14:00:00 | 11 | 4 | train | 0 | 32.0 | 137.7 | 26.4 | 7.1 | 6.9 |
| 2022-07-28 14:10:00 | 11 | 5 | train | 0 | 32.0 | 123.7 | 1.6 | 8.1 | 7.8 |
| 2022-07-28 14:20:00 | 11 | 6 | train | 0 | 32.0 | 114.2 | -11.4 | 7.5 | 7.2 |
| 2022-07-28 14:30:00 | 11 | 7 | train | 0 | 32.0 | 137.2 | 3.2 | 8.0 | 7.7 |
| 2022-07-28 14:40:00 | 11 | 8 | train | 0 | 32.0 | 132.9 | -0.4 | 8.4 | 8.1 |
| 2022-07-28 14:50:00 | 11 | 9 | train | 0 | 32.0 | 129.4 | -11.3 | 9.3 | 8.8 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-08-13 13:20:00 | 11 | 54357 | prediction | 3 | 28.0 | 118.3 | 21.4 | 14.2 | 13.4 |
| 2023-08-13 13:10:00 | 11 | 54356 | prediction | 3 | 28.0 | 105.0 | -6.2 | 15.2 | 14.1 |
| 2023-08-13 13:00:00 | 11 | 54355 | prediction | 3 | 28.0 | 98.2 | -6.0 | 14.6 | 13.5 |
| 2023-08-13 12:50:00 | 11 | 54354 | prediction | 3 | 27.0 | 99.8 | -10.7 | 15.7 | 14.2 |
| 2023-08-13 12:40:00 | 11 | 54353 | prediction | 3 | 27.0 | 94.7 | -9.5 | 16.2 | 14.8 |
| 2023-08-13 12:30:00 | 11 | 54352 | prediction | 3 | 27.0 | 111.4 | -0.5 | 17.4 | 16.1 |
| 2023-08-13 12:20:00 | 11 | 54351 | prediction | 3 | 27.0 | 107.3 | 4.5 | 17.1 | 15.7 |
| 2023-08-13 12:10:00 | 11 | 54350 | prediction | 3 | 27.0 | 101.0 | -8.4 | 16.9 | 15.5 |
| 2023-08-13 12:00:00 | 11 | 54349 | prediction | 3 | 27.0 | 113.4 | 10.9 | 15.3 | 14.3 |
| 2023-08-13 11:50:00 | 11 | 54348 | prediction | 3 | 27.0 | 101.0 | -1.5 | 15.3 | 14.0 |

---


## dbo.WFA_TURBINE_69_Data

**Primary Key:** EntryDateTime  
**Row Count:** 54,813  
**Date Range:** 2022-09-03 00:50:00 to 2023-09-21 00:50:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-09-03 00:50:00 | 11 | 0 | train | 0 | 26.0 | 111.8 | -8.1 | 5.4 | 5.4 |
| 2022-09-03 01:00:00 | 11 | 1 | train | 0 | 26.0 | 114.0 | -6.0 | 6.0 | 5.6 |
| 2022-09-03 01:10:00 | 11 | 2 | train | 0 | 26.0 | 98.8 | -13.5 | 6.6 | 6.2 |
| 2022-09-03 01:20:00 | 11 | 3 | train | 0 | 26.0 | 112.9 | 0.6000000000000001 | 6.4 | 6.2 |
| 2022-09-03 01:30:00 | 11 | 4 | train | 0 | 26.0 | 114.6 | 2.3 | 6.5 | 6.2 |
| 2022-09-03 01:40:00 | 11 | 5 | train | 0 | 26.0 | 107.9 | -3.3 | 7.3 | 7.0 |
| 2022-09-03 01:50:00 | 11 | 6 | train | 0 | 26.0 | 106.8 | -4.4 | 5.6 | 5.6 |
| 2022-09-03 02:00:00 | 11 | 7 | train | 0 | 26.0 | 100.8 | -17.1 | 5.5 | 5.6 |
| 2022-09-03 02:10:00 | 11 | 8 | train | 0 | 26.0 | 121.9 | 4.0 | 6.6 | 6.2 |
| 2022-09-03 02:20:00 | 11 | 9 | train | 0 | 26.0 | 111.5 | 0.6000000000000001 | 7.7 | 7.2 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-09-21 00:50:00 | 11 | 54812 | prediction | 0 | 22.0 | 102.0 | -1.1 | 6.1 | 5.9 |
| 2023-09-21 00:40:00 | 11 | 54811 | prediction | 0 | 22.0 | 103.0 | -0.2 | 6.9 | 6.7 |
| 2023-09-21 00:30:00 | 11 | 54810 | prediction | 0 | 22.0 | 104.4 | 1.2 | 6.5 | 6.4 |
| 2023-09-21 00:20:00 | 11 | 54809 | prediction | 0 | 23.0 | 104.1 | 0.9 | 6.4 | 6.2 |
| 2023-09-21 00:10:00 | 11 | 54808 | prediction | 0 | 23.0 | 100.6 | -2.5 | 5.5 | 5.3 |
| 2023-09-21 00:00:00 | 11 | 54807 | prediction | 0 | 23.0 | 99.6 | -3.7 | 5.7 | 5.6 |
| 2023-09-20 23:50:00 | 11 | 54806 | prediction | 0 | 23.0 | 100.9 | -2.6 | 5.5 | 5.6 |
| 2023-09-20 23:40:00 | 11 | 54805 | prediction | 0 | 23.0 | 102.3 | -1.7000000000000002 | 6.7 | 6.6 |
| 2023-09-20 23:30:00 | 11 | 54804 | prediction | 0 | 23.0 | 105.4 | -5.8 | 6.8 | 6.3 |
| 2023-09-20 23:20:00 | 11 | 54803 | prediction | 0 | 23.0 | 110.3 | -0.9 | 5.6 | 5.4 |

---


## dbo.WFA_TURBINE_71_Data

**Primary Key:** EntryDateTime  
**Row Count:** 54,744  
**Date Range:** 2022-01-01 00:00:00 to 2023-01-18 00:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-01-01 00:00:00 | 0 | 0 | train | 0 | 18.0 | 178.7 | -18.6 | 4.1 | 4.4 |
| 2022-01-01 00:10:00 | 0 | 1 | train | 0 | 18.0 | 191.8 | -12.2 | 4.1 | 4.3 |
| 2022-01-01 00:20:00 | 0 | 2 | train | 0 | 18.0 | 213.8 | 16.8 | 4.1 | 4.4 |
| 2022-01-01 00:30:00 | 0 | 3 | train | 0 | 18.0 | 199.3 | -4.6 | 4.4 | 4.6 |
| 2022-01-01 00:40:00 | 0 | 4 | train | 0 | 18.0 | 199.9 | -4.0 | 5.5 | 5.7 |
| 2022-01-01 00:50:00 | 0 | 5 | train | 0 | 18.0 | 203.6 | 6.7 | 5.4 | 5.7 |
| 2022-01-01 01:00:00 | 0 | 6 | train | 0 | 18.0 | 193.4 | -9.8 | 4.9 | 5.2 |
| 2022-01-01 01:10:00 | 0 | 7 | train | 0 | 18.0 | 215.1 | 11.8 | 4.0 | 4.2 |
| 2022-01-01 01:20:00 | 0 | 8 | train | 0 | 18.0 | 227.0 | 17.8 | 4.4 | 4.6 |
| 2022-01-01 01:30:00 | 0 | 9 | train | 0 | 18.0 | 205.5 | 2.5 | 4.4 | 4.6 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-01-18 00:00:00 | 0 | 54743 | prediction | 0 | 12.0 | 342.7 | -2.5 | 2.9 | 2.9 |
| 2023-01-17 23:50:00 | 0 | 54742 | prediction | 0 | 13.0 | 331.5 | -13.7 | 3.5 | 3.6 |
| 2023-01-17 23:40:00 | 0 | 54741 | prediction | 0 | 13.0 | 343.1 | -2.1 | 4.1 | 4.0 |
| 2023-01-17 23:30:00 | 0 | 54740 | prediction | 0 | 12.0 | 345.5 | 7.6 | 4.0 | 4.0 |
| 2023-01-17 23:20:00 | 0 | 54739 | prediction | 0 | 12.0 | 314.6 | -24.0 | 3.4 | 3.5 |
| 2023-01-17 23:10:00 | 0 | 54738 | prediction | 0 | 12.0 | 328.6 | -3.2 | 4.4 | 4.1 |
| 2023-01-17 23:00:00 | 0 | 54737 | prediction | 0 | 12.0 | 348.5 | 9.2 | 4.9 | 4.7 |
| 2023-01-17 22:50:00 | 0 | 54736 | prediction | 0 | 12.0 | 324.4 | -14.8 | 4.6 | 4.6 |
| 2023-01-17 22:40:00 | 0 | 54735 | prediction | 0 | 12.0 | 331.9 | -7.4 | 4.3 | 4.3 |
| 2023-01-17 22:30:00 | 0 | 54734 | prediction | 0 | 12.0 | 323.6 | 0.4 | 5.1 | 5.1 |

---


## dbo.WFA_TURBINE_72_Data

**Primary Key:** EntryDateTime  
**Row Count:** 54,082  
**Date Range:** 2022-10-07 08:40:00 to 2023-10-21 08:40:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-10-07 08:40:00 | 21 | 0 | train | 0 | 18.0 | 171.6 | 61.3 | 2.1 | 2.1 |
| 2022-10-07 08:50:00 | 21 | 1 | train | 0 | 18.0 | 166.0 | 55.7 | 1.6 | 1.6 |
| 2022-10-07 09:00:00 | 21 | 2 | train | 0 | 18.0 | 179.5 | 69.2 | 1.7000000000000002 | 1.7000000000000002 |
| 2022-10-07 09:10:00 | 21 | 3 | train | 0 | 18.0 | 168.3 | 58.0 | 1.8 | 1.8 |
| 2022-10-07 09:20:00 | 21 | 4 | train | 0 | 19.0 | 173.6 | 63.3 | 1.7000000000000002 | 1.7000000000000002 |
| 2022-10-07 09:30:00 | 21 | 5 | train | 0 | 19.0 | 166.1 | 55.8 | 1.1 | 1.1 |
| 2022-10-07 09:40:00 | 21 | 6 | train | 0 | 19.0 | 209.6 | 99.3 | 1.3 | 1.3 |
| 2022-10-07 09:50:00 | 21 | 7 | train | 0 | 19.0 | 212.8 | 102.5 | 1.5 | 1.5 |
| 2022-10-07 10:00:00 | 21 | 8 | train | 0 | 19.0 | 129.6 | 19.2 | 0.9 | 0.9 |
| 2022-10-07 10:10:00 | 21 | 9 | train | 0 | 19.0 | 172.5 | 62.2 | 0.9 | 0.9 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-10-21 08:40:00 | 21 | 54081 | prediction | 0 | 20.0 | 346.6 | -0.7000000000000001 | 1.4 | 1.4 |
| 2023-10-21 08:30:00 | 21 | 54080 | prediction | 0 | 20.0 | 356.8 | 9.5 | 1.4 | 1.4 |
| 2023-10-21 08:20:00 | 21 | 54079 | prediction | 0 | 20.0 | 348.8 | 1.5 | 1.8 | 1.8 |
| 2023-10-21 08:10:00 | 21 | 54078 | prediction | 0 | 20.0 | 339.7 | -7.6 | 1.6 | 1.6 |
| 2023-10-21 08:00:00 | 21 | 54077 | prediction | 0 | 19.0 | 352.3 | 5.0 | 2.0 | 2.0 |
| 2023-10-21 07:50:00 | 21 | 54076 | prediction | 0 | 19.0 | 356.9 | 9.6 | 2.3 | 2.3 |
| 2023-10-21 07:40:00 | 21 | 54075 | prediction | 0 | 19.0 | 344.1 | -2.8 | 2.6 | 2.6 |
| 2023-10-21 07:30:00 | 21 | 54074 | prediction | 0 | 20.0 | 329.9 | -35.2 | 2.6 | 2.6 |
| 2023-10-21 07:20:00 | 21 | 54073 | prediction | 0 | 19.0 | 301.2 | -63.9 | 1.8 | 1.8 |
| 2023-10-21 07:10:00 | 21 | 54072 | prediction | 0 | 19.0 | 270.5 | -94.6 | 1.4 | 1.4 |

---


## dbo.WFA_TURBINE_73_Data

**Primary Key:** EntryDateTime  
**Row Count:** 54,042  
**Date Range:** 2022-06-07 11:40:00 to 2023-06-19 11:40:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-06-07 11:40:00 | 0 | 0 | train | 0 | 26.0 | 79.6 | -7.2 | 9.4 | 9.3 |
| 2022-06-07 11:50:00 | 0 | 1 | train | 0 | 26.0 | 72.7 | -14.2 | 9.8 | 9.8 |
| 2022-06-07 12:00:00 | 0 | 2 | train | 0 | 26.0 | 75.4 | -11.4 | 10.3 | 10.0 |
| 2022-06-07 12:10:00 | 0 | 3 | train | 0 | 26.0 | 97.7 | 10.4 | 10.9 | 10.6 |
| 2022-06-07 12:20:00 | 0 | 4 | train | 0 | 26.0 | 96.8 | 16.9 | 10.1 | 10.0 |
| 2022-06-07 12:30:00 | 0 | 5 | train | 0 | 27.0 | 85.4 | 5.5 | 10.3 | 10.1 |
| 2022-06-07 12:40:00 | 0 | 6 | train | 0 | 27.0 | 66.2 | -14.0 | 10.4 | 10.3 |
| 2022-06-07 12:50:00 | 0 | 7 | train | 0 | 28.0 | 111.7 | 23.7 | 9.8 | 9.5 |
| 2022-06-07 13:00:00 | 0 | 8 | train | 0 | 28.0 | 78.8 | -11.2 | 10.6 | 10.3 |
| 2022-06-07 13:10:00 | 0 | 9 | train | 0 | 27.0 | 95.1 | 5.0 | 11.7 | 11.4 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-06-19 11:40:00 | 0 | 54041 | prediction | 3 | 29.0 | 123.2 | 2.9 | 11.3 | 10.8 |
| 2023-06-19 11:30:00 | 0 | 54040 | prediction | 3 | 28.0 | 106.7 | -19.4 | 11.5 | 10.9 |
| 2023-06-19 11:20:00 | 0 | 54039 | prediction | 3 | 29.0 | 160.4 | 31.8 | 10.8 | 10.3 |
| 2023-06-19 11:10:00 | 0 | 54038 | prediction | 3 | 28.0 | 127.0 | 4.4 | 10.6 | 10.0 |
| 2023-06-19 11:00:00 | 0 | 54037 | prediction | 3 | 28.0 | 114.8 | -7.8 | 9.8 | 9.4 |
| 2023-06-19 10:50:00 | 0 | 54036 | prediction | 3 | 28.0 | 103.3 | -19.4 | 10.3 | 9.9 |
| 2023-06-19 10:40:00 | 0 | 54035 | prediction | 3 | 28.0 | 95.8 | -12.1 | 9.2 | 9.0 |
| 2023-06-19 10:30:00 | 0 | 54034 | prediction | 3 | 28.0 | 121.6 | 12.6 | 10.1 | 9.7 |
| 2023-06-19 10:20:00 | 0 | 54033 | prediction | 3 | 28.0 | 136.3 | 20.3 | 11.1 | 10.5 |
| 2023-06-19 10:10:00 | 0 | 54032 | prediction | 3 | 28.0 | 120.0 | 11.4 | 11.2 | 10.9 |

---


## dbo.WFA_TURBINE_84_Data

**Primary Key:** EntryDateTime  
**Row Count:** 53,772  
**Date Range:** 2022-09-03 15:30:00 to 2023-09-13 15:30:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-09-03 15:30:00 | 13 | 0 | train | 0 | 31.0 | 81.6 | -2.2 | 13.5 | 13.4 |
| 2022-09-03 15:40:00 | 13 | 1 | train | 0 | 31.0 | 89.8 | 13.3 | 13.1 | 12.8 |
| 2022-09-03 15:50:00 | 13 | 2 | train | 0 | 31.0 | 68.7 | -6.7 | 13.3 | 13.2 |
| 2022-09-03 16:00:00 | 13 | 3 | train | 0 | 31.0 | 76.2 | -6.6 | 13.2 | 13.0 |
| 2022-09-03 16:10:00 | 13 | 4 | train | 0 | 31.0 | 70.5 | -5.7 | 12.4 | 12.3 |
| 2022-09-03 16:20:00 | 13 | 5 | train | 0 | 32.0 | 99.0 | 16.9 | 11.2 | 11.0 |
| 2022-09-03 16:30:00 | 13 | 6 | train | 0 | 32.0 | 93.7 | 10.9 | 12.3 | 12.2 |
| 2022-09-03 16:40:00 | 13 | 7 | train | 0 | 32.0 | 84.8 | 2.0 | 12.4 | 11.9 |
| 2022-09-03 16:50:00 | 13 | 8 | train | 0 | 32.0 | 69.7 | -13.1 | 11.4 | 11.2 |
| 2022-09-03 17:00:00 | 13 | 9 | train | 0 | 32.0 | 69.4 | -13.5 | 10.6 | 10.3 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-09-13 15:30:00 | 13 | 53771 | prediction | 3 | 30.0 | 96.7 | 1.3 | 8.1 | 8.2 |
| 2023-09-13 15:20:00 | 13 | 53770 | prediction | 3 | 30.0 | 92.4 | -3.6 | 9.1 | 8.8 |
| 2023-09-13 15:10:00 | 13 | 53769 | prediction | 3 | 30.0 | 89.1 | -0.3 | 8.9 | 8.9 |
| 2023-09-13 15:00:00 | 13 | 53768 | prediction | 3 | 30.0 | 89.1 | -1.7000000000000002 | 10.3 | 9.9 |
| 2023-09-13 14:50:00 | 13 | 53767 | prediction | 3 | 30.0 | 85.2 | -1.5 | 9.4 | 9.3 |
| 2023-09-13 14:40:00 | 13 | 53766 | prediction | 3 | 30.0 | 89.7 | 3.9 | 8.5 | 8.6 |
| 2023-09-13 14:30:00 | 13 | 53765 | prediction | 3 | 29.0 | 84.0 | 0.1 | 10.3 | 10.2 |
| 2023-09-13 14:20:00 | 13 | 53764 | prediction | 3 | 29.0 | 87.5 | 2.5 | 10.0 | 9.8 |
| 2023-09-13 14:10:00 | 13 | 53763 | prediction | 3 | 29.0 | 87.0 | -3.8 | 10.1 | 9.9 |
| 2023-09-13 14:00:00 | 13 | 53762 | prediction | 3 | 29.0 | 88.0 | 2.4 | 10.1 | 10.0 |

---


## dbo.WFA_TURBINE_92_Data

**Primary Key:** EntryDateTime  
**Row Count:** 54,067  
**Date Range:** 2022-04-04 02:30:00 to 2023-04-16 10:00:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| asset_id | int | NO | 10 | — |
| id | int | NO | 10 | — |
| train_test | varchar | YES | 16 | — |
| status_type_id | int | YES | 10 | — |
| sensor_0_avg | float | YES | 53 | — |
| sensor_1_avg | float | YES | 53 | — |
| sensor_2_avg | float | YES | 53 | — |
| wind_speed_3_avg | float | YES | 53 | — |
| wind_speed_4_avg | float | YES | 53 | — |
| wind_speed_3_max | float | YES | 53 | — |
| wind_speed_3_min | float | YES | 53 | — |
| wind_speed_3_std | float | YES | 53 | — |
| sensor_5_avg | float | YES | 53 | — |
| sensor_5_max | float | YES | 53 | — |
| sensor_5_min | float | YES | 53 | — |
| sensor_5_std | float | YES | 53 | — |
| sensor_6_avg | float | YES | 53 | — |
| sensor_7_avg | float | YES | 53 | — |
| sensor_8_avg | float | YES | 53 | — |
| sensor_9_avg | float | YES | 53 | — |
| sensor_10_avg | float | YES | 53 | — |
| sensor_11_avg | float | YES | 53 | — |
| sensor_12_avg | float | YES | 53 | — |
| sensor_13_avg | float | YES | 53 | — |
| sensor_14_avg | float | YES | 53 | — |
| sensor_15_avg | float | YES | 53 | — |
| sensor_16_avg | float | YES | 53 | — |
| sensor_17_avg | float | YES | 53 | — |
| sensor_18_avg | float | YES | 53 | — |
| sensor_18_max | float | YES | 53 | — |
| sensor_18_min | float | YES | 53 | — |
| sensor_18_std | float | YES | 53 | — |
| sensor_19_avg | float | YES | 53 | — |
| sensor_20_avg | float | YES | 53 | — |
| sensor_21_avg | float | YES | 53 | — |
| sensor_22_avg | float | YES | 53 | — |
| sensor_23_avg | float | YES | 53 | — |
| sensor_24_avg | float | YES | 53 | — |
| sensor_25_avg | float | YES | 53 | — |
| sensor_26_avg | float | YES | 53 | — |
| reactive_power_27_avg | float | YES | 53 | — |
| reactive_power_27_max | float | YES | 53 | — |
| reactive_power_27_min | float | YES | 53 | — |
| reactive_power_27_std | float | YES | 53 | — |
| reactive_power_28_avg | float | YES | 53 | — |
| reactive_power_28_max | float | YES | 53 | — |
| reactive_power_28_min | float | YES | 53 | — |
| reactive_power_28_std | float | YES | 53 | — |
| power_29_avg | float | YES | 53 | — |
| power_29_max | float | YES | 53 | — |
| power_29_min | float | YES | 53 | — |
| power_29_std | float | YES | 53 | — |
| power_30_avg | float | YES | 53 | — |
| power_30_max | float | YES | 53 | — |
| power_30_min | float | YES | 53 | — |
| power_30_std | float | YES | 53 | — |
| sensor_31_avg | float | YES | 53 | — |
| sensor_31_max | float | YES | 53 | — |
| sensor_31_min | float | YES | 53 | — |
| sensor_31_std | float | YES | 53 | — |
| sensor_32_avg | float | YES | 53 | — |
| sensor_33_avg | float | YES | 53 | — |
| sensor_34_avg | float | YES | 53 | — |
| sensor_35_avg | float | YES | 53 | — |
| sensor_36_avg | float | YES | 53 | — |
| sensor_37_avg | float | YES | 53 | — |
| sensor_38_avg | float | YES | 53 | — |
| sensor_39_avg | float | YES | 53 | — |
| sensor_40_avg | float | YES | 53 | — |
| sensor_41_avg | float | YES | 53 | — |
| sensor_42_avg | float | YES | 53 | — |
| sensor_43_avg | float | YES | 53 | — |
| sensor_44 | float | YES | 53 | — |
| sensor_45 | float | YES | 53 | — |
| sensor_46 | float | YES | 53 | — |
| sensor_47 | float | YES | 53 | — |
| sensor_48 | float | YES | 53 | — |
| sensor_49 | float | YES | 53 | — |
| sensor_50 | float | YES | 53 | — |
| sensor_51 | float | YES | 53 | — |
| sensor_52_avg | float | YES | 53 | — |
| sensor_52_max | float | YES | 53 | — |
| sensor_52_min | float | YES | 53 | — |
| sensor_52_std | float | YES | 53 | — |
| sensor_53_avg | float | YES | 53 | — |
| QualityFlag | int | NO | 10 | ((0)) |

### Top 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022-04-04 02:30:00 | 11 | 0 | train | 0 | 15.0 | 257.0 | -1.8 | 2.7 | 2.7 |
| 2022-04-04 02:40:00 | 11 | 1 | train | 0 | 15.0 | 267.3 | 13.4 | 2.6 | 2.6 |
| 2022-04-04 02:50:00 | 11 | 2 | train | 0 | 15.0 | 280.9 | 27.0 | 3.0 | 3.0 |
| 2022-04-04 03:00:00 | 11 | 3 | train | 0 | 15.0 | 256.5 | 6.8 | 2.8 | 2.8 |
| 2022-04-04 03:10:00 | 11 | 4 | train | 0 | 15.0 | 260.2 | 7.4 | 3.4 | 3.4 |
| 2022-04-04 03:20:00 | 11 | 5 | train | 0 | 15.0 | 240.2 | -9.5 | 3.8 | 3.9 |
| 2022-04-04 03:30:00 | 11 | 6 | train | 0 | 15.0 | 249.7 | 0.0 | 3.7 | 3.7 |
| 2022-04-04 03:40:00 | 11 | 7 | train | 0 | 15.0 | 228.7 | -18.9 | 4.1 | 4.0 |
| 2022-04-04 03:50:00 | 11 | 8 | train | 0 | 15.0 | 243.3 | -7.0 | 3.7 | 3.6 |
| 2022-04-04 04:00:00 | 11 | 9 | train | 0 | 15.0 | 254.1 | 18.7 | 3.8 | 3.8 |

### Bottom 10 Records

| EntryDateTime | asset_id | id | train_test | status_type_id | sensor_0_avg | sensor_1_avg | sensor_2_avg | wind_speed_3_avg | wind_speed_4_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-04-16 10:00:00 | 11 | 54066 | prediction | 0 | 16.0 | 91.9 | 17.8 | 3.1 | 3.1 |
| 2023-04-16 09:50:00 | 11 | 54065 | prediction | 0 | 16.0 | 63.5 | -10.6 | 2.4 | 2.4 |
| 2023-04-16 09:40:00 | 11 | 54064 | prediction | 0 | 16.0 | 69.8 | -16.9 | 2.8 | 2.8 |
| 2023-04-16 09:30:00 | 11 | 54063 | prediction | 0 | 16.0 | 69.7 | -32.0 | 2.3 | 2.3 |
| 2023-04-16 09:20:00 | 11 | 54062 | prediction | 0 | 15.0 | 117.8 | 4.8 | 2.7 | 2.7 |
| 2023-04-16 09:10:00 | 11 | 54061 | prediction | 0 | 15.0 | 98.2 | 0.2 | 2.8 | 2.8 |
| 2023-04-16 09:00:00 | 11 | 54060 | prediction | 0 | 15.0 | 79.9 | -21.2 | 3.3 | 3.3 |
| 2023-04-16 08:50:00 | 11 | 54059 | prediction | 0 | 15.0 | 106.3 | -149.1 | 3.7 | 3.7 |
| 2023-04-16 08:40:00 | 11 | 54058 | prediction | 0 | 15.0 | 82.5 | -176.3 | 2.2 | 2.2 |
| 2023-04-16 08:30:00 | 11 | 54057 | prediction | 0 | 15.0 | 98.7 | -160.1 | 1.7000000000000002 | 1.7000000000000002 |

---


## dbo.WIND_TURBINE_Data

**Primary Key:** No primary key  
**Row Count:** 50,530  
**Date Range:** 2024-01-01 00:00:00 to 2024-12-31 23:50:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EntryDateTime | datetime2 | NO | — | — |
| LV_ActivePower | float | YES | 53 | — |
| Wind_Speed | float | YES | 53 | — |
| Theoretical_Power_Curve | float | YES | 53 | — |
| Wind_Direction | float | YES | 53 | — |

### Top 10 Records

| EntryDateTime | LV_ActivePower | Wind_Speed | Theoretical_Power_Curve | Wind_Direction |
| --- | --- | --- | --- | --- |
| 2024-01-01 00:00:00 | 380.0477905 | 5.31133604 | 416.3289078 | 259.9949036 |
| 2024-01-01 00:10:00 | 453.7691956 | 5.672166824 | 519.9175111 | 268.6411133 |
| 2024-01-01 00:20:00 | 306.3765869 | 5.216036797 | 390.9000158 | 272.5647888 |
| 2024-01-01 00:30:00 | 419.6459045 | 5.659674168 | 516.127569 | 271.2580872 |
| 2024-01-01 00:40:00 | 380.6506958 | 5.577940941 | 491.702972 | 265.6742859 |
| 2024-01-01 00:50:00 | 402.3919983 | 5.604052067 | 499.436385 | 264.5786133 |
| 2024-01-01 01:00:00 | 447.6057129 | 5.793007851 | 557.3723633 | 266.1636047 |
| 2024-01-01 01:10:00 | 387.2421875 | 5.306049824 | 414.8981788 | 257.9494934 |
| 2024-01-01 01:20:00 | 463.6512146 | 5.584629059 | 493.6776521 | 253.4806976 |
| 2024-01-01 01:30:00 | 439.725708 | 5.523228168 | 475.7067828 | 258.7237854 |

### Bottom 10 Records

| EntryDateTime | LV_ActivePower | Wind_Speed | Theoretical_Power_Curve | Wind_Direction |
| --- | --- | --- | --- | --- |
| 2024-12-31 23:50:00 | 2820.466064 | 9.97933197 | 2779.184096 | 82.27462006 |
| 2024-12-31 23:40:00 | 2515.694092 | 9.421365738 | 2418.382503 | 84.2979126 |
| 2024-12-31 23:30:00 | 2201.106934 | 8.435358047 | 1788.284755 | 84.74250031 |
| 2024-12-31 23:20:00 | 1684.353027 | 7.3326478 | 1173.055771 | 84.06259918 |
| 2024-12-31 23:10:00 | 2963.980957 | 11.40402985 | 3397.190793 | 80.50272369 |
| 2024-12-31 23:00:00 | 3514.269043 | 12.55916977 | 3583.288363 | 80.49526215 |
| 2024-12-31 22:50:00 | 3429.021973 | 12.49250984 | 3578.567804 | 82.11186981 |
| 2024-12-31 22:40:00 | 3455.282959 | 12.19565964 | 3549.150371 | 82.21061707 |
| 2024-12-31 22:30:00 | 3333.819092 | 12.06766033 | 3532.081496 | 81.98590088 |
| 2024-12-31 22:20:00 | 2771.110107 | 10.1545496 | 2884.512812 | 82.33519745 |

---

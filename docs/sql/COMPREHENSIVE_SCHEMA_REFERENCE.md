# ACM Comprehensive Database Schema Reference

_Generated automatically on 2026-03-13 08:27:24_

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
- [dbo.ACM_BaselineGovernance](#dboacmbaselinegovernance)
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
- [dbo.ACM_EWMBaseline](#dboacmewmbaseline)
- [dbo.ACM_EpisodeCulprits](#dboacmepisodeculprits)
- [dbo.ACM_EpisodeDiagnostics](#dboacmepisodediagnostics)
- [dbo.ACM_Episodes](#dboacmepisodes)
- [dbo.ACM_FailureForecast](#dboacmfailureforecast)
- [dbo.ACM_FeatureDropLog](#dboacmfeaturedroplog)
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
- [dbo.ACM_RegimeBinnerState](#dboacmregimebinnerstate)
- [dbo.ACM_RegimeDefinitions](#dboacmregimedefinitions)
- [dbo.ACM_RegimeOccupancy](#dboacmregimeoccupancy)
- [dbo.ACM_RegimePromotionLog](#dboacmregimepromotionlog)
- [dbo.ACM_RegimeState](#dboacmregimestate)
- [dbo.ACM_RegimeTimeline](#dboacmregimetimeline)
- [dbo.ACM_RegimeTransitions](#dboacmregimetransitions)
- [dbo.ACM_Regime_Episodes](#dboacmregimeepisodes)
- [dbo.ACM_RepresentationSchemas](#dboacmrepresentationschemas)
- [dbo.ACM_RepresentationStatus](#dboacmrepresentationstatus)
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
- [dbo.ACM_SignalProfiles](#dboacmsignalprofiles)
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
| dbo.ACM_ActiveModels | 22 | 12 | ID |
| dbo.ACM_AdaptiveConfig | 14 | 13 | ConfigID |
| dbo.ACM_Anomaly_Events | 8 | 445 | Id |
| dbo.ACM_AssetProfiles | 11 | 1 | ID |
| dbo.ACM_BaselineBuffer | 8 | 458,224 | Id |
| dbo.ACM_BaselineGovernance | 12 | 20 | RunID, EquipID, Timestamp |
| dbo.ACM_CalibrationSummary | 10 | 552 | ID |
| dbo.ACM_ColdstartState | 18 | 12 | EquipID, Stage |
| dbo.ACM_Config | 9 | 388 | ConfigID |
| dbo.ACM_ConfigHistory | 10 | 96 | ID |
| dbo.ACM_ContributionTimeline | 7 | 374,814 | ID |
| dbo.ACM_DataContractValidation | 11 | 114 | ID |
| dbo.ACM_DataQuality | 26 | 7 | — |
| dbo.ACM_DetectorCorrelation | 7 | 2,685 | ID |
| dbo.ACM_DriftController | 10 | 92 | ID |
| dbo.ACM_DriftSeries | 7 | 0 | ID |
| dbo.ACM_EWMBaseline | 13 | 7,583 | EquipID, RegimeID, SensorName |
| dbo.ACM_EpisodeCulprits | 9 | 20,910 | ID |
| dbo.ACM_EpisodeDiagnostics | 17 | 3,189 | ID |
| dbo.ACM_Episodes | 15 | 3,189 | ID |
| dbo.ACM_FailureForecast | 10 | 103,152 | EquipID, RunID, Timestamp |
| dbo.ACM_FeatureDropLog | 8 | 3,494 | ID |
| dbo.ACM_ForecastingState | 14 | 6 | EquipID, StateVersion |
| dbo.ACM_HealthForecast | 11 | 103,152 | EquipID, RunID, Timestamp |
| dbo.ACM_HealthTimeline | 12 | 178,438 | — |
| dbo.ACM_HistorianData | 7 | 0 | ID |
| dbo.ACM_MultivariateForecast | 10 | 14,280 | ID |
| dbo.ACM_OMR_Diagnostics | 15 | 65 | DiagnosticID |
| dbo.ACM_PCA_Loadings | 8 | 169,700 | ID |
| dbo.ACM_PCA_Metrics | 10 | 85 | ID |
| dbo.ACM_PCA_Models | 12 | 91 | ID |
| dbo.ACM_RUL | 33 | 42 | EquipID, RunID |
| dbo.ACM_RefitRequests | 12 | 91 | RequestID |
| dbo.ACM_RegimeBinnerState | 3 | 1 | EquipID |
| dbo.ACM_RegimeDefinitions | 12 | 353 | ID |
| dbo.ACM_RegimeOccupancy | 9 | 356 | ID |
| dbo.ACM_RegimePromotionLog | 10 | 3 | ID |
| dbo.ACM_RegimeState | 17 | 12 | EquipID, StateVersion |
| dbo.ACM_RegimeTimeline | 10 | 178,438 | — |
| dbo.ACM_RegimeTransitions | 8 | 1,022 | ID |
| dbo.ACM_Regime_Episodes | 8 | 0 | ID |
| dbo.ACM_RepresentationSchemas | 14 | 20 | RunID, EquipID, Timestamp |
| dbo.ACM_RepresentationStatus | 47 | 20 | RunID, EquipID, Timestamp |
| dbo.ACM_RunLogs | 8 | 950 | ID |
| dbo.ACM_RunMetadata | 11 | 0 | ID |
| dbo.ACM_RunMetrics | 7 | 1,440 | ID |
| dbo.ACM_Run_Stats | 13 | 95 | RecordID |
| dbo.ACM_Runs | 34 | 122 | RunID |
| dbo.ACM_SchemaVersion | 5 | 2 | VersionID |
| dbo.ACM_Scores_Wide | 18 | 178,438 | — |
| dbo.ACM_SeasonalPatterns | 11 | 3,711 | ID |
| dbo.ACM_SensorCorrelations | 8 | 18,797 | ID |
| dbo.ACM_SensorDefects | 13 | 682 | — |
| dbo.ACM_SensorForecast | 12 | 57,120 | RunID, EquipID, Timestamp, SensorName |
| dbo.ACM_SensorHotspots | 22 | 1,689 | — |
| dbo.ACM_SensorNormalized_TS | 8 | 678,874 | ID |
| dbo.ACM_SignalProfiles | 11 | 1,302 | RunID, EquipID, Timestamp, SignalName |
| dbo.ACM_TagEquipmentMap | 10 | 2,001 | TagID |
| dbo.COND_PUMP_MOTOR_Data | 16 | 17,619 | — |
| dbo.ELECTRIC_MOTOR_Data | 14 | 17,477 | — |
| dbo.ELECTRIC_MOTOR_Data_RAW | 14 | 1,048,575 | — |
| dbo.Equipment | 8 | 30 | EquipID |
| dbo.FD_FAN_Data | 11 | 17,499 | EntryDateTime |
| dbo.GAS_TURBINE_Data | 18 | 2,911 | EntryDateTime |
| dbo.ModelRegistry | 8 | 272 | ModelType, EquipID, Version |
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
**Row Count:** 12  
**Date Range:** 2026-02-12 19:22:29 to 2026-03-08 12:46:57  

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
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |
| RunID | uniqueidentifier | YES | — | — |
| RegimeQualityMetric | nvarchar | YES | 30 | — |

### Top 10 Records

| ID | EquipID | ActiveRegimeVersion | RegimeMaturityState | RegimePromotedAt | ActiveThresholdVersion | ThresholdPromotedAt | ActiveForecastVersion | ForecastPromotedAt | LastUpdatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 56 | 8632 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-01-19 16:45:30 |
| 77 | 8635 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-01-19 18:52:07 |
| 267 | 5022 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-01-22 09:53:00 |
| 356 | 5014 | 1 | CONVERGED | 2026-02-12 19:22:29 | 1 | NULL | 1 | NULL | 2026-02-12 20:17:52 |
| 516 | 5073 | 1 | CONVERGED | 2026-02-16 14:18:00 | 1 | NULL | 1 | NULL | 2026-02-16 15:42:41 |
| 557 | 2621 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-02-19 13:51:22 |
| 604 | 1 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-03-07 11:35:46 |
| 610 | 5040 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-03-07 12:20:28 |
| 651 | 5013 | 1 | CONVERGED | 2026-03-08 12:46:57 | 1 | NULL | 1 | NULL | 2026-03-08 13:05:08 |
| 687 | 5038 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-03-12 23:04:08 |

### Bottom 10 Records

| ID | EquipID | ActiveRegimeVersion | RegimeMaturityState | RegimePromotedAt | ActiveThresholdVersion | ThresholdPromotedAt | ActiveForecastVersion | ForecastPromotedAt | LastUpdatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 689 | 5010 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-03-13 08:05:35 |
| 688 | 5000 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-03-13 08:05:35 |
| 687 | 5038 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-03-12 23:04:08 |
| 651 | 5013 | 1 | CONVERGED | 2026-03-08 12:46:57 | 1 | NULL | 1 | NULL | 2026-03-08 13:05:08 |
| 610 | 5040 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-03-07 12:20:28 |
| 604 | 1 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-03-07 11:35:46 |
| 557 | 2621 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-02-19 13:51:22 |
| 516 | 5073 | 1 | CONVERGED | 2026-02-16 14:18:00 | 1 | NULL | 1 | NULL | 2026-02-16 15:42:41 |
| 356 | 5014 | 1 | CONVERGED | 2026-02-12 19:22:29 | 1 | NULL | 1 | NULL | 2026-02-12 20:17:52 |
| 267 | 5022 | 1 | LEARNING | NULL | 1 | NULL | 1 | NULL | 2026-01-22 09:53:00 |

---


## dbo.ACM_AdaptiveConfig

**Primary Key:** ConfigID  
**Row Count:** 13  
**Date Range:** 2025-12-04 10:46:47 to 2025-12-31 09:54:45  

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
| RunID | uniqueidentifier | YES | — | — |

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
| 55 | 5092 | fused_warn_z | 0.5271811485290527 | 0.0 | 999999.0 | True | 2717 | 0.0 | quantile_0.997: Auto-calculated warning threshold (50% of alert) |
| 54 | 5092 | fused_alert_z | 1.0543622970581055 | 0.0 | 999999.0 | True | 2717 | 0.0 | quantile_0.997: Auto-calculated from 2717 accumulated samples |
| 19 | 5003 | fused_warn_z | 0.7344083189964294 | 0.0 | 999999.0 | True | 129 | 0.0 | quantile_0.997: Auto-calculated warning threshold (50% of alert) |
| 18 | 5003 | fused_alert_z | 1.4688166379928589 | 0.0 | 999999.0 | True | 129 | 0.0 | quantile_0.997: Auto-calculated from 129 accumulated samples |
| 9 | NULL | auto_tune_data_threshold | 10000.0 | 5000.0 | 50000.0 | False | NULL | NULL | Expert tuning - Auto-tuning trigger |
| 8 | NULL | blend_tau_hours | 12.0 | 6.0 | 48.0 | False | NULL | NULL | Expert tuning - Warm-start alpha blending |
| 7 | NULL | monte_carlo_simulations | 1000.0 | 500.0 | 5000.0 | False | NULL | NULL | Saxena et al. (2008) - RUL simulation count |
| 6 | NULL | max_forecast_hours | 168.0 | 168.0 | 720.0 | False | NULL | NULL | Industry standard - 7-30 day horizon |
| 5 | NULL | confidence_min | 0.8 | 0.5 | 0.95 | False | NULL | NULL | Agresti & Coull (1998) - Statistical confidence |
| 4 | NULL | failure_threshold | 70.0 | 40.0 | 80.0 | False | NULL | NULL | ISO 13381-1:2015 - Health index threshold |

---


## dbo.ACM_Anomaly_Events

**Primary Key:** Id  
**Row Count:** 445  
**Date Range:** 2022-01-16 16:50:00 to 2025-09-12 18:00:00  

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
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

### Top 10 Records

| Id | RunID | EquipID | StartTime | EndTime | Severity | Confidence | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1092 | 3432CDEB-C8DC-4B88-9826-FE8108973C5F | 1 | 2023-11-19 01:00:00 | 2023-11-19 04:30:00 | info | 0.612 | 2026-03-07 05:47:57 |
| 1093 | 3432CDEB-C8DC-4B88-9826-FE8108973C5F | 1 | 2023-11-21 00:00:00 | 2023-11-21 07:30:00 | info | 0.612 | 2026-03-07 05:47:57 |
| 1126 | 5E8005D5-E9D9-4062-97A8-00550C2E74A7 | 1 | 2023-12-20 23:00:00 | 2024-01-14 07:30:00 | info | 0.612 | 2026-03-07 05:50:04 |
| 1127 | B7940000-0429-4372-833C-2B7718DC8950 | 1 | 2024-02-17 03:00:00 | 2024-02-17 07:00:00 | info | 0.612 | 2026-03-07 05:51:43 |
| 1128 | B7940000-0429-4372-833C-2B7718DC8950 | 1 | 2024-02-19 00:00:00 | 2024-02-19 08:00:00 | info | 0.612 | 2026-03-07 05:51:43 |
| 1129 | B7940000-0429-4372-833C-2B7718DC8950 | 1 | 2024-02-28 14:00:00 | 2024-03-01 02:00:00 | info | 0.612 | 2026-03-07 05:51:43 |
| 1130 | 76A312C0-C5E4-4699-9A03-63F6F4DF60CB | 1 | 2024-03-26 14:00:00 | 2024-03-26 16:00:00 | info | 0.512 | 2026-03-07 05:53:20 |
| 1131 | 76A312C0-C5E4-4699-9A03-63F6F4DF60CB | 1 | 2024-03-27 02:00:00 | 2024-03-27 06:30:00 | info | 0.512 | 2026-03-07 05:53:20 |
| 1132 | 76A312C0-C5E4-4699-9A03-63F6F4DF60CB | 1 | 2024-03-28 00:00:00 | 2024-03-28 22:00:00 | info | 0.512 | 2026-03-07 05:53:20 |
| 1133 | 76A312C0-C5E4-4699-9A03-63F6F4DF60CB | 1 | 2024-03-29 08:30:00 | 2024-03-29 14:30:00 | info | 0.512 | 2026-03-07 05:53:20 |

### Bottom 10 Records

| Id | RunID | EquipID | StartTime | EndTime | Severity | Confidence | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2529 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 2023-05-25 09:20:00 | 2023-05-25 10:10:00 | info | 0.479 | 2026-03-08 07:58:28 |
| 2528 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 2023-05-22 20:00:00 | 2023-05-22 20:50:00 | info | 0.479 | 2026-03-08 07:58:28 |
| 2527 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 2023-05-22 16:40:00 | 2023-05-22 18:30:00 | info | 0.512 | 2026-03-08 07:58:28 |
| 2526 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 2023-05-22 13:40:00 | 2023-05-22 14:40:00 | info | 0.512 | 2026-03-08 07:58:28 |
| 2525 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 2023-05-22 10:30:00 | 2023-05-22 11:40:00 | info | 0.512 | 2026-03-08 07:58:28 |
| 2524 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 2023-05-22 05:00:00 | 2023-05-22 05:30:00 | info | 0.413 | 2026-03-08 07:58:28 |
| 2523 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 2023-05-21 10:00:00 | 2023-05-21 10:30:00 | info | 0.413 | 2026-03-08 07:58:28 |
| 2522 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 2023-05-19 09:50:00 | 2023-05-19 11:40:00 | info | 0.512 | 2026-03-08 07:58:28 |
| 2521 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 2023-05-19 02:50:00 | 2023-05-19 05:40:00 | info | 0.512 | 2026-03-08 07:58:28 |
| 2520 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 2023-05-18 10:10:00 | 2023-05-18 11:20:00 | info | 0.512 | 2026-03-08 07:58:28 |

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
**Row Count:** 458,224  
**Date Range:** 2022-09-07 00:20:00 to 2025-01-24 07:30:00  

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
| RunID | uniqueidentifier | YES | — | — |

### Top 10 Records

| Id | EquipID | Timestamp | SensorName | SensorValue | DataQuality | CreatedAt | RunID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3239310 | 5014 | 2023-03-08 04:50:00 | power_29_avg | 0.0373186424353477 | NULL | 2026-02-12 20:20:29 | NULL |
| 3239311 | 5014 | 2023-03-08 05:00:00 | power_29_avg | 0.030514543158860884 | NULL | 2026-02-12 20:20:29 | NULL |
| 3239312 | 5014 | 2023-03-08 05:10:00 | power_29_avg | 0.03375270481218061 | NULL | 2026-02-12 20:20:29 | NULL |
| 3239313 | 5014 | 2023-03-08 05:20:00 | power_29_avg | 0.03843881139541634 | NULL | 2026-02-12 20:20:29 | NULL |
| 3239314 | 5014 | 2023-03-08 05:30:00 | power_29_avg | 0.05032013292577808 | NULL | 2026-02-12 20:20:29 | NULL |
| 3239315 | 5014 | 2023-03-08 05:40:00 | power_29_avg | 0.05211968890570073 | NULL | 2026-02-12 20:20:29 | NULL |
| 3239316 | 5014 | 2023-03-08 05:50:00 | power_29_avg | 0.07978016603569568 | NULL | 2026-02-12 20:20:29 | NULL |
| 3239317 | 5014 | 2023-03-08 06:00:00 | power_29_avg | 0.08563466556370258 | NULL | 2026-02-12 20:20:29 | NULL |
| 3239318 | 5014 | 2023-03-08 06:10:00 | power_29_avg | 0.09621160354422542 | NULL | 2026-02-12 20:20:29 | NULL |
| 3239319 | 5014 | 2023-03-08 06:20:00 | power_29_avg | 0.10164934558479782 | NULL | 2026-02-12 20:20:29 | NULL |

### Bottom 10 Records

| Id | EquipID | Timestamp | SensorName | SensorValue | DataQuality | CreatedAt | RunID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10348677 | 5013 | 2023-01-15 11:10:00 | wind_speed_4_avg | 3.6524412066584917 | NULL | 2026-03-08 07:44:16 | E08EBBE9-824E-4B56-A270-1365F6282276 |
| 10348676 | 5013 | 2023-01-15 11:00:00 | wind_speed_4_avg | 3.2082370907460738 | NULL | 2026-03-08 07:44:16 | E08EBBE9-824E-4B56-A270-1365F6282276 |
| 10348675 | 5013 | 2023-01-15 10:50:00 | wind_speed_4_avg | 3.065921042271328 | NULL | 2026-03-08 07:44:16 | E08EBBE9-824E-4B56-A270-1365F6282276 |
| 10348674 | 5013 | 2023-01-15 10:40:00 | wind_speed_4_avg | 2.8255735170517196 | NULL | 2026-03-08 07:44:16 | E08EBBE9-824E-4B56-A270-1365F6282276 |
| 10348673 | 5013 | 2023-01-15 10:30:00 | wind_speed_4_avg | 2.8872709377880543 | NULL | 2026-03-08 07:44:16 | E08EBBE9-824E-4B56-A270-1365F6282276 |
| 10348672 | 5013 | 2023-01-15 10:20:00 | wind_speed_4_avg | 2.7510866922725583 | NULL | 2026-03-08 07:44:16 | E08EBBE9-824E-4B56-A270-1365F6282276 |
| 10348671 | 5013 | 2023-01-15 10:10:00 | wind_speed_4_avg | 3.117089468719822 | NULL | 2026-03-08 07:44:16 | E08EBBE9-824E-4B56-A270-1365F6282276 |
| 10348670 | 5013 | 2023-01-15 10:00:00 | wind_speed_4_avg | 3.385343601488966 | NULL | 2026-03-08 07:44:16 | E08EBBE9-824E-4B56-A270-1365F6282276 |
| 10348669 | 5013 | 2023-01-15 09:50:00 | wind_speed_4_avg | 3.5559104737722844 | NULL | 2026-03-08 07:44:16 | E08EBBE9-824E-4B56-A270-1365F6282276 |
| 10348668 | 5013 | 2023-01-15 09:40:00 | wind_speed_4_avg | 3.6288451600715517 | NULL | 2026-03-08 07:44:16 | E08EBBE9-824E-4B56-A270-1365F6282276 |

---


## dbo.ACM_BaselineGovernance

**Primary Key:** RunID, EquipID, Timestamp  
**Row Count:** 20  
**Date Range:** 2022-08-08 06:00:00 to 2025-09-14 23:30:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | varchar | NO | 64 | — |
| EquipID | int | NO | 10 | — |
| Timestamp | datetime2 | NO | — | — |
| RuntimeMode | nvarchar | NO | 64 | — |
| ReadinessState | nvarchar | YES | 64 | — |
| BaselineCandidateState | nvarchar | YES | 128 | — |
| ContaminationVerdict | nvarchar | YES | 64 | — |
| FreezeState | nvarchar | YES | 64 | — |
| ShadowRefreshState | nvarchar | YES | 64 | — |
| PromotedPackageVersion | nvarchar | YES | 128 | — |
| ReasonCodesJson | nvarchar | YES | -1 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

### Top 10 Records

| RunID | EquipID | Timestamp | RuntimeMode | ReadinessState | BaselineCandidateState | ContaminationVerdict | FreezeState | ShadowRefreshState | PromotedPackageVersion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| 4cf9f1c6-f55a-4f84-ad66-a924d05c5fbf | 1 | 2025-09-14 23:30:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | 2023-07-17 07:40:00 | BASELINE_FORMATION | FORMING | COLLECTING_TRUSTED_WINDOW | CONTAMINATED | UNASSESSED | LEARNING_ALLOWED | NULL |
| 5f4d313f-19f2-4278-893d-cb5a04cd420e | 1 | 2025-09-14 23:30:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| 6704067f-df3c-43d1-a482-960b73e96e62 | 5000 | 2022-08-13 06:00:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| 70631f62-1a62-4302-9ab9-14fec0643b88 | 5010 | 2022-10-16 08:30:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| 7bee3349-151f-40ee-af7e-194eb9eece87 | 5010 | 2022-10-14 08:30:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| 7f16ac41-d523-4b03-b7dc-0d35b69b37b6 | 1 | 2025-09-14 23:30:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| 80581aa0-39ef-4330-b9ea-832c443fe4b2 | 5000 | 2022-08-14 06:00:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 2022-10-13 08:30:00 | BASELINE_FORMATION | FORMING | COLLECTING_TRUSTED_WINDOW | CONTAMINATED | UNASSESSED | LEARNING_ALLOWED | NULL |

### Bottom 10 Records

| RunID | EquipID | Timestamp | RuntimeMode | ReadinessState | BaselineCandidateState | ContaminationVerdict | FreezeState | ShadowRefreshState | PromotedPackageVersion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| fdab2ed7-7571-4f1c-b5da-875410c0d8d8 | 1 | 2025-09-14 23:30:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| e569dc4d-c2d6-4be4-b48e-54f8bd7dd83e | 5000 | 2022-08-12 06:00:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| d3fe0f8c-8b2a-453a-86c0-b8e068c1685d | 5010 | 2022-10-18 08:30:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| b71d3cf5-c462-4873-ad6a-7eef33a45f15 | 5000 | 2022-08-10 06:00:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| b59dd1ea-fe94-485c-a27c-24c3a7395f74 | 5010 | 2022-10-15 08:30:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| b53a0140-d75c-4746-87b9-c90db65a50a6 | 5010 | 2022-10-17 08:30:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| a4a7ad70-2697-453a-958f-26cfc649fe05 | 5010 | 2022-10-19 08:30:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| 9c8134da-b2bf-48f3-8489-8728aaabea22 | 5000 | 2022-08-09 06:00:00 | ONLINE_SCORING | READY | ACTIVE_PACKAGE | UNKNOWN | UNASSESSED | UNASSESSED | NULL |
| 8aad982a-390e-4991-b900-87e771fcbb68 | 5000 | 2022-08-08 06:00:00 | BASELINE_FORMATION | FORMING | COLLECTING_TRUSTED_WINDOW | CONTAMINATED | UNASSESSED | LEARNING_ALLOWED | NULL |

---


## dbo.ACM_CalibrationSummary

**Primary Key:** ID  
**Row Count:** 552  
**Date Range:** 2026-01-19 10:49:14 to 2026-03-08 07:58:27  

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
| 5604 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | omr_z | 3.3236067199257944 | NULL | NULL | NULL | NULL | 2026-03-08 07:58:27 |
| 5603 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | gmm_z | -0.21040324600157118 | NULL | NULL | NULL | NULL | 2026-03-08 07:58:27 |
| 5602 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | iforest_z | 3.53310209238405 | NULL | NULL | NULL | NULL | 2026-03-08 07:58:27 |
| 5601 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | pca_t2_z | -20.0 | NULL | NULL | NULL | NULL | 2026-03-08 07:58:27 |
| 5600 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | pca_spe_z | -20.0 | NULL | NULL | NULL | NULL | 2026-03-08 07:58:27 |
| 5599 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | ar1_z | 3.8473275968492064 | NULL | NULL | NULL | NULL | 2026-03-08 07:58:27 |
| 5598 | 442AA522-4B2A-4068-ADAE-D8F7B0F8C297 | 5013 | omr_z | 3.3236067199257944 | NULL | NULL | NULL | NULL | 2026-03-08 07:56:35 |
| 5597 | 442AA522-4B2A-4068-ADAE-D8F7B0F8C297 | 5013 | gmm_z | -0.21040324600157118 | NULL | NULL | NULL | NULL | 2026-03-08 07:56:35 |
| 5596 | 442AA522-4B2A-4068-ADAE-D8F7B0F8C297 | 5013 | iforest_z | 3.53310209238405 | NULL | NULL | NULL | NULL | 2026-03-08 07:56:35 |
| 5595 | 442AA522-4B2A-4068-ADAE-D8F7B0F8C297 | 5013 | pca_t2_z | -20.0 | NULL | NULL | NULL | NULL | 2026-03-08 07:56:35 |

---


## dbo.ACM_ColdstartState

**Primary Key:** EquipID, Stage  
**Row Count:** 12  
**Date Range:** 2026-01-19 10:47:02 to 2026-03-13 02:30:42  

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
| 1 | score | COMPLETE | 1 | 2026-03-07 05:46:40 | 2026-03-07 05:46:40 | NULL | 672 | 500 | 2023-10-15 00:00:00 |
| 2621 | score | COMPLETE | 1 | 2026-02-19 08:19:55 | 2026-02-19 08:19:56 | 2026-02-19 08:19:56 | 589 | 500 | 2023-10-15 00:00:00 |
| 5000 | score | COMPLETE | 3 | 2026-03-13 02:30:42 | 2026-03-13 02:31:05 | 2026-03-13 02:31:05 | 576 | 500 | 2022-08-04 06:10:00 |
| 5010 | score | COMPLETE | 3 | 2026-03-13 02:30:42 | 2026-03-13 02:31:05 | 2026-03-13 02:31:05 | 575 | 500 | 2022-10-09 08:40:00 |
| 5013 | score | COMPLETE | 1 | 2026-03-08 07:05:49 | 2026-03-08 07:05:49 | NULL | 3718 | 500 | 2022-04-30 13:20:00 |
| 5014 | score | COMPLETE | 1 | 2026-02-12 12:53:39 | 2026-02-12 12:53:48 | 2026-02-12 12:53:48 | 5437 | 500 | 2022-03-03 14:00:00 |
| 5022 | score | COMPLETE | 1 | 2026-01-22 04:12:06 | 2026-01-22 04:12:08 | 2026-01-22 04:12:08 | 601 | 500 | 2022-08-12 09:50:00 |
| 5038 | score | COMPLETE | 1 | 2026-03-12 17:33:54 | 2026-03-12 17:33:54 | NULL | 3445 | 500 | 2023-06-22 07:40:00 |
| 5040 | score | COMPLETE | 1 | 2026-03-07 06:43:25 | 2026-03-07 06:43:25 | NULL | 3769 | 500 | 2022-01-01 00:00:00 |
| 5073 | score | COMPLETE | 1 | 2026-02-16 08:32:39 | 2026-02-16 08:32:47 | 2026-02-16 08:32:47 | 4522 | 500 | 2022-06-07 11:40:00 |

### Bottom 10 Records

| EquipID | Stage | Status | AttemptCount | FirstAttemptAt | LastAttemptAt | CompletedAt | AccumulatedRows | RequiredRows | DataStartTime |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8635 | score | COMPLETE | 1 | 2026-01-19 12:52:29 | 2026-01-19 12:52:33 | 2026-01-19 12:52:33 | 7799 | 500 | 2018-12-01 00:00:00 |
| 8632 | score | COMPLETE | 2 | 2026-01-19 10:47:02 | 2026-01-19 10:50:47 | 2026-01-19 10:50:47 | 1202 | 500 | 2024-01-01 00:00:00 |
| 5073 | score | COMPLETE | 1 | 2026-02-16 08:32:39 | 2026-02-16 08:32:47 | 2026-02-16 08:32:47 | 4522 | 500 | 2022-06-07 11:40:00 |
| 5040 | score | COMPLETE | 1 | 2026-03-07 06:43:25 | 2026-03-07 06:43:25 | NULL | 3769 | 500 | 2022-01-01 00:00:00 |
| 5038 | score | COMPLETE | 1 | 2026-03-12 17:33:54 | 2026-03-12 17:33:54 | NULL | 3445 | 500 | 2023-06-22 07:40:00 |
| 5022 | score | COMPLETE | 1 | 2026-01-22 04:12:06 | 2026-01-22 04:12:08 | 2026-01-22 04:12:08 | 601 | 500 | 2022-08-12 09:50:00 |
| 5014 | score | COMPLETE | 1 | 2026-02-12 12:53:39 | 2026-02-12 12:53:48 | 2026-02-12 12:53:48 | 5437 | 500 | 2022-03-03 14:00:00 |
| 5013 | score | COMPLETE | 1 | 2026-03-08 07:05:49 | 2026-03-08 07:05:49 | NULL | 3718 | 500 | 2022-04-30 13:20:00 |
| 5010 | score | COMPLETE | 3 | 2026-03-13 02:30:42 | 2026-03-13 02:31:05 | 2026-03-13 02:31:05 | 575 | 500 | 2022-10-09 08:40:00 |
| 5000 | score | COMPLETE | 3 | 2026-03-13 02:30:42 | 2026-03-13 02:31:05 | 2026-03-13 02:31:05 | 576 | 500 | 2022-08-04 06:10:00 |

---


## dbo.ACM_Config

**Primary Key:** ConfigID  
**Row Count:** 388  
**Date Range:** 2025-12-09 12:47:06 to 2026-03-10 17:02:10  

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
| RunID | uniqueidentifier | YES | — | — |
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

### Top 10 Records

| ConfigID | EquipID | ParamPath | ParamValue | ValueType | UpdatedAt | UpdatedBy | RunID | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 492 | 0 | data.train_csv | data/FD_FAN_BASELINE_DATA.csv | string | 2026-03-10 17:02:08 | B19cl3pc\bhadk | NULL | NULL |
| 493 | 0 | data.score_csv | data/FD_FAN_BATCH_DATA.csv | string | 2026-03-10 17:02:08 | B19cl3pc\bhadk | NULL | NULL |
| 494 | 0 | data.data_dir | data | string | 2026-03-10 17:02:08 | B19cl3pc\bhadk | NULL | NULL |
| 495 | 0 | data.timestamp_col | EntryDateTime | string | 2026-03-10 17:02:08 | B19cl3pc\bhadk | NULL | NULL |
| 496 | 0 | data.tag_columns | [] | list | 2026-03-10 17:02:08 | B19cl3pc\bhadk | NULL | NULL |
| 497 | 0 | data.sampling_secs | auto | string | 2026-03-10 17:02:08 | B19cl3pc\bhadk | NULL | NULL |
| 498 | 0 | data.max_rows | 100000 | int | 2026-03-10 17:02:08 | B19cl3pc\bhadk | NULL | NULL |
| 499 | 0 | features.window | 16 | int | 2026-03-10 17:02:08 | B19cl3pc\bhadk | NULL | NULL |
| 500 | 0 | features.fft_bands | [0.0, 0.1, 0.3, 0.5] | list | 2026-03-10 17:02:08 | B19cl3pc\bhadk | NULL | NULL |
| 501 | 0 | features.top_k_tags | 5 | int | 2026-03-10 17:02:08 | B19cl3pc\bhadk | NULL | NULL |

### Bottom 10 Records

| ConfigID | EquipID | ParamPath | ParamValue | ValueType | UpdatedAt | UpdatedBy | RunID | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1448 | 0 | regimes.health.per_regime_thresholds | {} | string | 2026-03-10 17:02:09 | B19cl3pc\bhadk | NULL | 2026-03-10 14:03:20 |
| 1416 | 5011 | data.tag_columns | ["sensor_0_avg","sensor_1_avg","sensor_2_avg","wind_speed_3_avg","wind_speed_4_avg","wind_speed_3... | list | 2026-03-10 17:02:10 | B19cl3pc\bhadk | NULL | 2026-03-09 13:11:23 |
| 1415 | 5011 | data.sampling_secs | 600 | int | 2026-03-10 17:02:10 | B19cl3pc\bhadk | NULL | 2026-03-09 13:11:23 |
| 1414 | 5011 | data.timestamp_col | EntryDateTime | string | 2026-03-10 17:02:10 | B19cl3pc\bhadk | NULL | 2026-03-09 13:11:23 |
| 1402 | 0 | models.ewm_baseline.surface.min_iqr | 1e-06 | float | 2026-03-10 17:02:10 | B19cl3pc\bhadk | NULL | 2026-03-09 10:13:40 |
| 1401 | 0 | models.ewm_baseline.surface.min_valid_fraction | 0.60 | float | 2026-03-10 17:02:10 | B19cl3pc\bhadk | NULL | 2026-03-09 10:13:40 |
| 1400 | 0 | models.ewm_baseline.proxy_history_limit | 512 | int | 2026-03-10 17:02:10 | B19cl3pc\bhadk | NULL | 2026-03-09 10:13:40 |
| 1399 | 0 | models.ewm_baseline.proxy_alpha | 0.05 | float | 2026-03-10 17:02:10 | B19cl3pc\bhadk | NULL | 2026-03-09 10:13:40 |
| 1398 | 0 | models.ewm_baseline.min_rows_for_assignment | 20 | int | 2026-03-10 17:02:10 | B19cl3pc\bhadk | NULL | 2026-03-09 10:13:40 |
| 1394 | 0 | regimes.feature_basis.min_iqr | 1e-06 | float | 2026-03-10 17:02:09 | B19cl3pc\bhadk | NULL | 2026-03-09 10:13:40 |

---


## dbo.ACM_ConfigHistory

**Primary Key:** ID  
**Row Count:** 96  
**Date Range:** 2026-01-19 16:19:23 to 2026-03-08 13:01:04  

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
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

### Top 10 Records

| ID | Timestamp | EquipID | ParameterPath | OldValue | NewValue | ChangedBy | ChangeReason | RunID | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 51 | 2026-01-19 16:19:23 | 8632 | k_sigma | 2.0 | 2.2 | AUTO_TUNE | Auto-tuning based on quality assessment | 248f1325-7537-4843-acfe-e559c458b2a9 | NULL |
| 52 | 2026-01-19 16:19:23 | 8632 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 248f1325-7537-4843-acfe-e559c458b2a9 | NULL |
| 53 | 2026-01-19 16:21:55 | 8632 | k_sigma | 2.0 | 2.2 | AUTO_TUNE | Auto-tuning based on quality assessment | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | NULL |
| 54 | 2026-01-19 16:21:55 | 8632 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 173dd810-96e8-4e3f-af4b-7a0b97723d70 | NULL |
| 57 | 2026-01-19 16:24:28 | 8632 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 3bb10529-b16e-4893-826b-73584fec01c8 | NULL |
| 58 | 2026-01-19 16:27:38 | 8632 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 496202d1-c512-4d13-93b6-8ad2f15e7c24 | NULL |
| 61 | 2026-01-19 16:31:42 | 8632 | k_sigma | 2.0 | 2.2 | AUTO_TUNE | Auto-tuning based on quality assessment | c2cfa54f-fb33-4f66-8340-9a1a0dcec544 | NULL |
| 62 | 2026-01-19 16:31:42 | 8632 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | c2cfa54f-fb33-4f66-8340-9a1a0dcec544 | NULL |
| 64 | 2026-01-19 16:35:00 | 8632 | k_sigma | 2.0 | 2.2 | AUTO_TUNE | Auto-tuning based on quality assessment | d80354e0-96f4-4a76-9f2a-c73f9c36f66f | NULL |
| 65 | 2026-01-19 16:35:00 | 8632 | k_max | 6.0 | 8.0 | AUTO_TUNE | Auto-tuning based on quality assessment | d80354e0-96f4-4a76-9f2a-c73f9c36f66f | NULL |

### Bottom 10 Records

| ID | Timestamp | EquipID | ParameterPath | OldValue | NewValue | ChangedBy | ChangeReason | RunID | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1259 | 2026-03-08 13:01:04 | 5013 | k_sigma | 2.928 | 3.221 | AUTO_TUNE | Auto-tuning based on quality assessment | 228a2c70-9dd9-4fa3-88a1-221eb648e918 | 2026-03-08 07:31:04 |
| 1258 | 2026-03-08 13:01:04 | 5013 | clip_z | 41.47 | 49.76 | AUTO_TUNE | Auto-tuning based on quality assessment | 228a2c70-9dd9-4fa3-88a1-221eb648e918 | 2026-03-08 07:31:04 |
| 1257 | 2026-03-08 12:56:41 | 5013 | k_sigma | 2.662 | 2.928 | AUTO_TUNE | Auto-tuning based on quality assessment | 50de5c8e-e820-4706-8929-51f362d8e88e | 2026-03-08 07:26:41 |
| 1256 | 2026-03-08 12:56:41 | 5013 | clip_z | 34.56 | 41.47 | AUTO_TUNE | Auto-tuning based on quality assessment | 50de5c8e-e820-4706-8929-51f362d8e88e | 2026-03-08 07:26:41 |
| 1255 | 2026-03-08 12:52:09 | 5013 | k_sigma | 2.42 | 2.662 | AUTO_TUNE | Auto-tuning based on quality assessment | fea26c14-286c-4479-a544-b5ac307d99e4 | 2026-03-08 07:22:09 |
| 1254 | 2026-03-08 12:52:09 | 5013 | clip_z | 28.8 | 34.56 | AUTO_TUNE | Auto-tuning based on quality assessment | fea26c14-286c-4479-a544-b5ac307d99e4 | 2026-03-08 07:22:09 |
| 1252 | 2026-03-08 12:47:29 | 5013 | k_max | 10.0 | 12.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 3841a482-2bff-43f8-8d6b-40cc8e00b8c9 | 2026-03-08 07:17:29 |
| 1251 | 2026-03-08 12:47:29 | 5013 | k_sigma | 2.2 | 2.42 | AUTO_TUNE | Auto-tuning based on quality assessment | 3841a482-2bff-43f8-8d6b-40cc8e00b8c9 | 2026-03-08 07:17:29 |
| 1250 | 2026-03-08 12:47:29 | 5013 | clip_z | 24.0 | 28.8 | AUTO_TUNE | Auto-tuning based on quality assessment | 3841a482-2bff-43f8-8d6b-40cc8e00b8c9 | 2026-03-08 07:17:29 |
| 1248 | 2026-03-08 12:43:22 | 5013 | k_max | 8.0 | 10.0 | AUTO_TUNE | Auto-tuning based on quality assessment | 8fedfa1f-e5e2-4902-8007-29409a9a8d08 | 2026-03-08 07:13:22 |

---


## dbo.ACM_ContributionTimeline

**Primary Key:** ID  
**Row Count:** 374,814  
**Date Range:** 2022-01-16 16:50:00 to 2025-09-14 23:00:00  

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

### Top 10 Records

| ID | RunID | EquipID | Timestamp | DetectorType | ContributionPct | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- |
| 540163 | 3432cdeb-c8dc-4b88-9826-fe8108973c5f | 1 | 2023-11-18 10:00:00 | ar1 | 48.635563241821 | 2026-03-07 05:48:00 |
| 540164 | 3432cdeb-c8dc-4b88-9826-fe8108973c5f | 1 | 2023-11-18 10:30:00 | ar1 | 23.526175385738448 | 2026-03-07 05:48:00 |
| 540165 | 3432cdeb-c8dc-4b88-9826-fe8108973c5f | 1 | 2023-11-18 11:00:00 | ar1 | 37.923729640416084 | 2026-03-07 05:48:00 |
| 540166 | 3432cdeb-c8dc-4b88-9826-fe8108973c5f | 1 | 2023-11-18 11:30:00 | ar1 | 38.50617031710893 | 2026-03-07 05:48:00 |
| 540167 | 3432cdeb-c8dc-4b88-9826-fe8108973c5f | 1 | 2023-11-18 12:00:00 | ar1 | 39.9764069130033 | 2026-03-07 05:48:00 |
| 540168 | 3432cdeb-c8dc-4b88-9826-fe8108973c5f | 1 | 2023-11-18 12:30:00 | ar1 | 42.756393904794535 | 2026-03-07 05:48:00 |
| 540169 | 3432cdeb-c8dc-4b88-9826-fe8108973c5f | 1 | 2023-11-18 13:00:00 | ar1 | 42.913556682713306 | 2026-03-07 05:48:00 |
| 540170 | 3432cdeb-c8dc-4b88-9826-fe8108973c5f | 1 | 2023-11-18 13:30:00 | ar1 | 34.25400752792112 | 2026-03-07 05:48:00 |
| 540171 | 3432cdeb-c8dc-4b88-9826-fe8108973c5f | 1 | 2023-11-18 14:00:00 | ar1 | 23.51052758618753 | 2026-03-07 05:48:00 |
| 540172 | 3432cdeb-c8dc-4b88-9826-fe8108973c5f | 1 | 2023-11-18 14:30:00 | ar1 | 16.908643816536483 | 2026-03-07 05:48:00 |

### Bottom 10 Records

| ID | RunID | EquipID | Timestamp | DetectorType | ContributionPct | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- |
| 1779744 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 2023-05-25 10:10:00 | omr | 8.168300370775457 | 2026-03-08 07:58:28 |
| 1779743 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 2023-05-25 10:00:00 | omr | 8.441319235124276 | 2026-03-08 07:58:28 |
| 1779742 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 2023-05-25 09:50:00 | omr | 5.677881205208905 | 2026-03-08 07:58:28 |
| 1779741 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 2023-05-25 09:40:00 | omr | 8.340876184635142 | 2026-03-08 07:58:28 |
| 1779740 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 2023-05-25 09:30:00 | omr | 9.22207045084621 | 2026-03-08 07:58:28 |
| 1779739 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 2023-05-25 09:20:00 | omr | 9.207123841575964 | 2026-03-08 07:58:28 |
| 1779738 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 2023-05-25 09:10:00 | omr | 7.559354411491446 | 2026-03-08 07:58:28 |
| 1779737 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 2023-05-25 09:00:00 | omr | 5.4737678612189065 | 2026-03-08 07:58:28 |
| 1779736 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 2023-05-25 08:50:00 | omr | 11.243105262642558 | 2026-03-08 07:58:28 |
| 1779735 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 2023-05-25 08:40:00 | omr | 10.00397508462626 | 2026-03-08 07:58:28 |

---


## dbo.ACM_DataContractValidation

**Primary Key:** ID  
**Row Count:** 114  
**Date Range:** 2026-01-19 16:17:04 to 2026-03-13 08:09:58  

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
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

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
| 101 | 6899a3b2-fb5b-4bb7-8c52-ed27857a3f7a | 8635 | True | 3120 | 14 | NULL | NULL | 7221316bc1f6 | 2026-01-19 18:22:34 |

### Bottom 10 Records

| ID | RunID | EquipID | Passed | RowsValidated | ColumnsValidated | IssuesJSON | WarningsJSON | ContractSignature | ValidatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11253 | a4a7ad70-2697-453a-958f-26cfc649fe05 | 5010 | True | 144 | 79 | NULL | NULL | 207b37f7ae5e | 2026-03-13 08:09:58 |
| 11252 | 80581aa0-39ef-4330-b9ea-832c443fe4b2 | 5000 | True | 144 | 79 | NULL | NULL | 31ae67006634 | 2026-03-13 08:09:58 |
| 11251 | d3fe0f8c-8b2a-453a-86c0-b8e068c1685d | 5010 | True | 144 | 79 | NULL | NULL | 207b37f7ae5e | 2026-03-13 08:09:14 |
| 11250 | 6704067f-df3c-43d1-a482-960b73e96e62 | 5000 | True | 144 | 79 | NULL | NULL | 31ae67006634 | 2026-03-13 08:09:14 |
| 11249 | e569dc4d-c2d6-4be4-b48e-54f8bd7dd83e | 5000 | True | 144 | 79 | NULL | NULL | 31ae67006634 | 2026-03-13 08:08:33 |
| 11248 | b53a0140-d75c-4746-87b9-c90db65a50a6 | 5010 | True | 144 | 79 | NULL | NULL | 207b37f7ae5e | 2026-03-13 08:08:33 |
| 11247 | ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | True | 144 | 79 | NULL | NULL | 31ae67006634 | 2026-03-13 08:07:51 |
| 11246 | 70631f62-1a62-4302-9ab9-14fec0643b88 | 5010 | True | 144 | 79 | NULL | NULL | 207b37f7ae5e | 2026-03-13 08:07:51 |
| 11245 | b59dd1ea-fe94-485c-a27c-24c3a7395f74 | 5010 | True | 132 | 79 | NULL | NULL | 207b37f7ae5e | 2026-03-13 08:07:08 |
| 11244 | b71d3cf5-c462-4873-ad6a-7eef33a45f15 | 5000 | True | 144 | 79 | NULL | NULL | 31ae67006634 | 2026-03-13 08:07:08 |

---


## dbo.ACM_DataQuality

**Primary Key:** No primary key  
**Row Count:** 7  
**Date Range:** 2022-08-04 06:10:00 to 2025-09-10 00:00:00  

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
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

### Top 10 Records

| sensor | train_count | train_nulls | train_null_pct | train_std | train_longest_gap | train_flatline_span | train_min_ts | train_max_ts | score_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _SUMMARY_81_SENSORS | 2067 | 0 | 0.0 | 0.0 | 2 | 0 | 2023-06-22 07:40:00 | 2023-07-07 18:00:00 | 1378 |
| _SUMMARY_79_SENSORS | 1722 | 0 | 0.0 | 0.0 | 0 | 0 | 2023-06-22 07:40:00 | 2023-07-04 08:20:00 | 1723 |
| _SUMMARY_79_SENSORS | 500 | 0 | 0.0 | 0.0 | 0 | 0 | 2022-08-04 06:10:00 | 2022-08-07 17:20:00 | 76 |
| _SUMMARY_81_SENSORS | 2262 | 0 | 0.0 | 0.0 | 2 | 0 | 2023-02-13 19:40:00 | 2023-03-01 12:30:00 | 2262 |
| _SUMMARY_9_SENSORS | 240 | 0 | 0.0 | 0.0 | 0 | 0 | 2025-09-10 00:00:00 | 2025-09-14 23:30:00 | 0 |
| _SUMMARY_79_SENSORS | 500 | 0 | 0.0 | 0.0 | 0 | 0 | 2022-10-09 08:40:00 | 2022-10-12 20:00:00 | 75 |
| _SUMMARY_81_SENSORS | 144 | 0 | 0.0 | 0.0 | 2 | 0 | 2022-08-14 09:50:00 | 2022-08-15 09:40:00 | 144 |

---


## dbo.ACM_DetectorCorrelation

**Primary Key:** ID  
**Row Count:** 2,685  
**Date Range:** 2026-01-19 10:49:33 to 2026-03-08 07:58:29  

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
| 24484 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | cusum_z | cusum_z | 1.0 | 2026-03-08 07:58:29 |
| 24483 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | cusum_z | omr_z | -0.04945928564112261 | 2026-03-08 07:58:29 |
| 24482 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | cusum_z | gmm_z | -0.05489769100452518 | 2026-03-08 07:58:29 |
| 24481 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | cusum_z | pca_t2_z | 0.07356097224523904 | 2026-03-08 07:58:29 |
| 24480 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | cusum_z | ar1_z | -0.13499739149878565 | 2026-03-08 07:58:29 |
| 24479 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | omr_z | cusum_z | -0.04945928564112261 | 2026-03-08 07:58:29 |
| 24478 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | omr_z | omr_z | 1.0 | 2026-03-08 07:58:29 |
| 24477 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | omr_z | gmm_z | 0.9352625958580746 | 2026-03-08 07:58:29 |
| 24476 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | omr_z | pca_t2_z | 0.04167058763671378 | 2026-03-08 07:58:29 |
| 24475 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | omr_z | ar1_z | 0.20049093425341968 | 2026-03-08 07:58:29 |

---


## dbo.ACM_DriftController

**Primary Key:** ID  
**Row Count:** 92  

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
| 925 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-03-08 07:58:28 |
| 924 | 442aa522-4b2a-4068-adae-d8f7b0f8c297 | 5013 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-03-08 07:56:45 |
| 923 | 76197100-b482-4094-8e64-f3df8ca194c3 | 5013 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-03-08 07:53:54 |
| 922 | 0159a32a-354a-456f-ac02-58e7930ec60f | 5013 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-03-08 07:51:10 |
| 921 | 183fa102-0939-470e-a8ea-c8513ad4d894 | 5013 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-03-08 07:48:12 |
| 919 | e08ebbe9-824e-4b56-a270-1365f6282276 | 5013 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-03-08 07:44:05 |
| 917 | 76b00271-2ea6-4477-9ed7-7890e5a219ec | 5013 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-03-08 07:41:16 |
| 916 | 7d450cab-83c9-4039-ad50-2633e4b67642 | 5013 | FAULT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-03-08 07:38:28 |
| 914 | f50286f4-235d-4511-b1c1-7daf37418f49 | 5013 | DRIFT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-03-08 07:35:41 |
| 912 | 228a2c70-9dd9-4fa3-88a1-221eb648e918 | 5013 | DRIFT | 3.0 | 1.0 | NULL | NULL | NULL | 2026-03-08 07:31:05 |

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


## dbo.ACM_EWMBaseline

**Primary Key:** EquipID, RegimeID, SensorName  
**Row Count:** 7,583  
**Date Range:** 2026-03-10 06:48:22 to 2026-03-12 11:44:18  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EquipID | int | NO | 10 | — |
| RegimeID | int | NO | 10 | — |
| SensorName | varchar | NO | 200 | — |
| EWMMean_Fast | float | YES | 53 | — |
| EWMVar_Fast | float | YES | 53 | — |
| EWMMean_Slow | float | YES | 53 | — |
| EWMVar_Slow | float | YES | 53 | — |
| NSamples | int | NO | 10 | ((0)) |
| BaselineIntegrity | varchar | NO | 20 | ('ok') |
| ScoreP50 | float | YES | 53 | — |
| ScoreP95 | float | YES | 53 | — |
| UpdatedAt | datetime2 | NO | — | (sysutcdatetime()) |
| StateVersion | smallint | YES | 5 | — |

### Top 10 Records

| EquipID | RegimeID | SensorName | EWMMean_Fast | EWMVar_Fast | EWMMean_Slow | EWMVar_Slow | NSamples | BaselineIntegrity | ScoreP50 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5000 | -1 | power_29_avg | 0.015443351954748318 | 0.00506587665230174 | 0.2945875118799131 | 0.09320999404129127 | 21974 | ok | 1.161732608353097 |
| 5000 | -1 | power_29_max | 0.025958601350179675 | 0.014214600583277037 | 0.4535384832107714 | 0.17695925960056486 | 21974 | ok | 1.3167289725330127 |
| 5000 | -1 | power_29_min | 0.006385123732024936 | 0.0009356485071976638 | 0.12676040543325007 | 0.025645447525235624 | 21974 | ok | 0.9413296205893895 |
| 5000 | -1 | power_29_std | 0.01419394099633168 | 0.0003515731465585381 | 0.07268408665863305 | 0.0043952334317855345 | 21974 | ok | 1.094075302000822 |
| 5000 | -1 | power_30_avg | 0.010139495136049137 | 0.0033722476943462035 | 0.016153042243865344 | 0.02113275542594601 | 21974 | ok | 0.3670630969256842 |
| 5000 | -1 | power_30_max | 0.07959950688486642 | 0.008273600764081719 | 0.03996832199784475 | 0.037530651159627386 | 21974 | ok | 0.4202067974998092 |
| 5000 | -1 | power_30_min | 0.004707131933023739 | 0.0008682968313762277 | 0.005400813221607658 | 0.009889744069780843 | 21974 | frozen | 0.27501388645462654 |
| 5000 | -1 | power_30_std | 0.013637494396787507 | 0.000238627766590604 | 0.00617064045201607 | 0.0007339706189788503 | 21974 | ok | 0.512505967415105 |
| 5000 | -1 | reactive_power_27_avg | 0.0333389936149836 | 0.0038476592860741065 | 0.01799037780040415 | 0.012885393687034301 | 21974 | ok | 0.4855988047864298 |
| 5000 | -1 | reactive_power_27_max | 0.3976521140877409 | 0.005326789354961771 | 0.3968655913207932 | 0.020173797230128594 | 17459 | frozen | 0.24684580238965964 |

### Bottom 10 Records

| EquipID | RegimeID | SensorName | EWMMean_Fast | EWMVar_Fast | EWMMean_Slow | EWMVar_Slow | NSamples | BaselineIntegrity | ScoreP50 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5010 | 25 | wind_speed_4_avg | 3.8047852986420474 | 2.201990317300862 | 1.873001994526341 | 3.3342143667501234 | 147 | ok | 1.1433547170254998 |
| 5010 | 25 | wind_speed_3_std | 0.42351238472187436 | 0.07644964217766338 | 0.32280961305266503 | 0.7615301868725965 | 58 | frozen | 0.15967580302321072 |
| 5010 | 25 | wind_speed_3_min | 0.455786619646287 | 0.2560274164981182 | 0.24988069017711348 | 0.7872938929539522 | 58 | frozen | 0.11887933293211439 |
| 5010 | 25 | wind_speed_3_max | 7.884625254422771 | 11.690699656393297 | 4.72346836259416 | 9.854978571762148 | 147 | ok | 0.613918798788089 |
| 5010 | 25 | wind_speed_3_avg | 3.3365838953306977 | 2.528760386340137 | 1.7605346524844196 | 3.121215251279976 | 147 | ok | 0.6558455660564516 |
| 5010 | 25 | sensor_9_avg | 36.57530500864404 | 9.813222521677273 | 32.047362645926135 | 9.105740513148769 | 147 | ok | 2.2083747424126394 |
| 5010 | 25 | sensor_8_avg | 45.86478215020306 | 508.81450003571825 | 36.78638549100946 | 385.2350211744751 | 147 | ok | 0.329074915076774 |
| 5010 | 25 | sensor_7_avg | 34.52054693551189 | 4.217981406552992 | 31.527987054721507 | 6.000137912151783 | 147 | ok | 1.543126255037404 |
| 5010 | 25 | sensor_6_avg | 30.239855706760675 | 30.711738526195184 | 25.676100165015903 | 14.843355771463571 | 147 | ok | 2.297884217795026 |
| 5010 | 25 | sensor_53_avg | 23.09688661056689 | 26.246964330511364 | 18.791152826350956 | 13.119317039763061 | 147 | ok | 1.9550262459581185 |

---


## dbo.ACM_EpisodeCulprits

**Primary Key:** ID  
**Row Count:** 20,910  
**Date Range:** 2026-01-19 10:50:09 to 2026-03-08 07:58:32  

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
| 131045 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 19 | Density Anomaly (GMM) | NULL | 2.934554100036621 | 6 | 2026-03-08 07:58:32 | 5013 |
| 131044 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 19 | Time-Series Anomaly (AR1) | NULL | 3.9774603843688965 | 5 | 2026-03-08 07:58:32 | 5013 |
| 131043 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 19 | Baseline Consistency (OMR) | NULL | 5.369368076324463 | 4 | 2026-03-08 07:58:32 | 5013 |
| 131042 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 19 | cusum_z | NULL | 26.394861221313477 | 3 | 2026-03-08 07:58:32 | 5013 |
| 131041 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 19 | drift_z | NULL | 26.394861221313477 | 2 | 2026-03-08 07:58:32 | 5013 |
| 131040 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 19 | Rare State (IsolationForest) | NULL | 34.928897857666016 | 1 | 2026-03-08 07:58:32 | 5013 |
| 131039 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 18 | Density Anomaly (GMM) | NULL | 3.306692123413086 | 6 | 2026-03-08 07:58:32 | 5013 |
| 131038 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 18 | Baseline Consistency (OMR) | NULL | 6.002578258514404 | 5 | 2026-03-08 07:58:32 | 5013 |
| 131037 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 18 | Time-Series Anomaly (AR1) | NULL | 6.670596599578857 | 4 | 2026-03-08 07:58:32 | 5013 |
| 131036 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 18 | cusum_z | NULL | 20.888200759887695 | 3 | 2026-03-08 07:58:32 | 5013 |

---


## dbo.ACM_EpisodeDiagnostics

**Primary Key:** ID  
**Row Count:** 3,189  
**Date Range:** 2019-03-08 12:00:00 to 2025-09-12 18:00:00  

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
| 19124 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 19 | 2023-05-25 09:20:00 | 2023-05-25 10:10:00 | 0.8333333333333334 | 1.1943674131674442 | -0.9479675507531932 | LOW |
| 19123 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 18 | 2023-05-22 20:00:00 | 2023-05-22 20:50:00 | 0.8333333333333334 | 1.0288007889742143 | -0.8589176862836094 | LOW |
| 19122 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 17 | 2023-05-22 16:40:00 | 2023-05-22 18:30:00 | 1.8333333333333333 | 1.0075906129600811 | -0.6970079100859445 | LOW |
| 19121 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 16 | 2023-05-22 13:40:00 | 2023-05-22 14:40:00 | 1.0 | 1.1437276831948402 | -0.11068612950366973 | LOW |
| 19120 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 15 | 2023-05-22 10:30:00 | 2023-05-22 11:40:00 | 1.1666666666666667 | 1.2644748625668032 | 0.03475311309549639 | LOW |
| 19119 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 14 | 2023-05-22 05:00:00 | 2023-05-22 05:30:00 | 0.5 | 0.9560587860703715 | -0.9122935741442889 | LOW |
| 19118 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 13 | 2023-05-21 10:00:00 | 2023-05-21 10:30:00 | 0.5 | 1.9312581491462633 | -1.9221054615679505 | LOW |
| 19117 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 12 | 2023-05-19 09:50:00 | 2023-05-19 11:40:00 | 1.8333333333333333 | 1.28387122919997 | 0.32697006227007197 | LOW |
| 19116 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 11 | 2023-05-19 02:50:00 | 2023-05-19 05:40:00 | 2.8333333333333335 | 1.2771441690157848 | -0.5590734194606983 | LOW |
| 19115 | d41c8634-b66d-43ab-9a39-82df56fd6409 | 5013 | 10 | 2023-05-18 10:10:00 | 2023-05-18 11:20:00 | 1.1666666666666667 | 1.28387122919997 | -0.4469961897236718 | LOW |

---


## dbo.ACM_Episodes

**Primary Key:** ID  
**Row Count:** 3,189  
**Date Range:** 2019-03-08 12:00:00 to 2025-09-12 18:00:00  

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
| 19007 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 19 | 2023-05-25 09:20:00 | 2023-05-25 10:10:00 | 3000.0 | 0.8333333333333334 | 1 | Rare State (IsolationForest) |
| 19006 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 18 | 2023-05-22 20:00:00 | 2023-05-22 20:50:00 | 3000.0 | 0.8333333333333334 | 1 | Rare State (IsolationForest) |
| 19005 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 17 | 2023-05-22 16:40:00 | 2023-05-22 18:30:00 | 6600.0 | 1.8333333333333333 | 1 | Rare State (IsolationForest) |
| 19004 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 16 | 2023-05-22 13:40:00 | 2023-05-22 14:40:00 | 3600.0 | 1.0 | 1 | Rare State (IsolationForest) |
| 19003 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 15 | 2023-05-22 10:30:00 | 2023-05-22 11:40:00 | 4200.0 | 1.1666666666666667 | 1 | Rare State (IsolationForest) |
| 19002 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 14 | 2023-05-22 05:00:00 | 2023-05-22 05:30:00 | 1800.0 | 0.5 | 1 | Rare State (IsolationForest) |
| 19001 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 13 | 2023-05-21 10:00:00 | 2023-05-21 10:30:00 | 1800.0 | 0.5 | 1 | Density Anomaly (GMM) |
| 19000 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 12 | 2023-05-19 09:50:00 | 2023-05-19 11:40:00 | 6600.0 | 1.8333333333333333 | 1 | Density Anomaly (GMM) |
| 18999 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 11 | 2023-05-19 02:50:00 | 2023-05-19 05:40:00 | 10200.0 | 2.8333333333333335 | 1 | Rare State (IsolationForest) |
| 18998 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 10 | 2023-05-18 10:10:00 | 2023-05-18 11:20:00 | 4200.0 | 1.1666666666666667 | 1 | Rare State (IsolationForest) |

---


## dbo.ACM_FailureForecast

**Primary Key:** EquipID, RunID, Timestamp  
**Row Count:** 103,152  
**Date Range:** 2019-05-12 11:30:00 to 2024-06-23 01:59:00  

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
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 12:59:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 13:52:05 | 804137 |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 13:59:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 13:52:05 | 804138 |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 14:59:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 13:52:05 | 804139 |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 15:59:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 13:52:05 | 804140 |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 16:59:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 13:52:05 | 804141 |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 17:59:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 13:52:05 | 804142 |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 18:59:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 13:52:05 | 804143 |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 19:59:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 13:52:05 | 804144 |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 20:59:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 13:52:05 | 804145 |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 21:59:00 | 1.0 | 0.0 | 0.0 | 70.0 | RegimeConditionedHolt | 2026-02-19 13:52:05 | 804146 |

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
**Row Count:** 3,494  
**Date Range:** 2026-01-19 10:53:30 to 2026-03-13 02:32:36  

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
| 51858 | 8AAD982A-390E-4991-B900-87E771FCBB68 | 5000 | sensor_52_std_energy_0 | low_variance | 3.47019279992338e-30 | NULL | 2026-03-13 02:32:36 |
| 51857 | 8AAD982A-390E-4991-B900-87E771FCBB68 | 5000 | sensor_15_avg_energy_0 | low_variance | 2.603151244761963e-26 | NULL | 2026-03-13 02:32:36 |
| 51856 | 8AAD982A-390E-4991-B900-87E771FCBB68 | 5000 | sensor_18_std_energy_0 | low_variance | 3.7211951887518724e-26 | NULL | 2026-03-13 02:32:36 |
| 51855 | 8AAD982A-390E-4991-B900-87E771FCBB68 | 5000 | power_30_avg_energy_0 | low_variance | 1.0185226721596936e-30 | NULL | 2026-03-13 02:32:36 |
| 51854 | 8AAD982A-390E-4991-B900-87E771FCBB68 | 5000 | sensor_35_avg_energy_0 | low_variance | 1.4715747161732081e-27 | NULL | 2026-03-13 02:32:36 |
| 51853 | 8AAD982A-390E-4991-B900-87E771FCBB68 | 5000 | sensor_1_avg_energy_0 | low_variance | 9.647468183861862e-26 | NULL | 2026-03-13 02:32:36 |
| 51852 | 8AAD982A-390E-4991-B900-87E771FCBB68 | 5000 | wind_speed_4_avg_energy_0 | low_variance | 1.8699317299356682e-28 | NULL | 2026-03-13 02:32:36 |
| 51851 | 8AAD982A-390E-4991-B900-87E771FCBB68 | 5000 | sensor_23_avg_energy_0 | low_variance | 2.496220766006614e-24 | NULL | 2026-03-13 02:32:36 |
| 51850 | 8AAD982A-390E-4991-B900-87E771FCBB68 | 5000 | reactive_power_27_std_energy_0 | low_variance | 1.3511794786077708e-32 | NULL | 2026-03-13 02:32:36 |
| 51849 | 8AAD982A-390E-4991-B900-87E771FCBB68 | 5000 | sensor_0_avg_energy_0 | low_variance | 1.0888968588970987e-27 | NULL | 2026-03-13 02:32:36 |

---


## dbo.ACM_ForecastingState

**Primary Key:** EquipID, StateVersion  
**Row Count:** 6  

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
| RunID | uniqueidentifier | YES | — | — |

### Top 10 Records

| ID | EquipID | StateVersion | ModelCoefficientsJson | LastForecastJson | LastRetrainTime | TrainingDataHash | DataVolumeAnalyzed | RecentMAE | RecentRMSE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 17 | 8632 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.2, "beta": 0.03, "level": 88.761191261... | {"forecast_mean": 7.240821912614943, "forecast_std": 19.388388038997423, "forecast_range": 88.707... | NULL |  | 21281 | 19.388388038997423 | NULL |
| 23 | 8635 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.05, "beta": 0.01, "level": 47.64524147... | {"forecast_mean": 1.4423215554806277, "forecast_std": 6.570960912590737, "forecast_range": 46.502... | NULL |  | 10269 | 6.570960912590737 | NULL |
| 30 | 5022 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.95, "beta": 0.01, "level": 92.80989910... | {"forecast_mean": 86.75207713346725, "forecast_std": 3.4940171390585113, "forecast_range": 12.091... | NULL |  | 626 | 3.4940171390585113 | NULL |
| 51 | 5014 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.95, "beta": 0.01, "level": 94.05357420... | {"forecast_mean": 91.29142771024733, "forecast_std": 1.593144736470478, "forecast_range": 5.51334... | NULL |  | 66748 | 1.593144736470478 | NULL |
| 57 | 5073 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.8, "beta": 0.01, "level": 93.255194410... | {"forecast_mean": 90.49732762782227, "forecast_std": 1.5906762937486225, "forecast_range": 5.5048... | NULL |  | 93858 | 1.5906762937486225 | NULL |
| 67 | 2621 | 1 | {"version": "regime_conditioned_v1", "global": {"alpha": 0.4, "beta": 0.08, "level": 64.176364882... | {"forecast_mean": 84.15697351600969, "forecast_std": 11.140963439847333, "forecast_range": 35.398... | NULL |  | 4576 | 11.140963439847333 | NULL |

---


## dbo.ACM_HealthForecast

**Primary Key:** EquipID, RunID, Timestamp  
**Row Count:** 103,152  
**Date Range:** 2019-05-12 11:30:00 to 2024-06-23 01:59:00  

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
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 12:59:00 | 0.3436910488279369 | 0.3165151342633392 | 0.37086696339253455 | 0.013587957282298835 | RegimeConditionedHolt | 2026-02-19 13:52:04 | NULL |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 13:59:00 | 0.3426391593607467 | 0.30770078218937724 | 0.3775775365321161 | 0.013587957282298835 | RegimeConditionedHolt | 2026-02-19 13:52:04 | NULL |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 14:59:00 | 0.3415872698935565 | 0.300205570407017 | 0.38296896938009595 | 0.013587957282298835 | RegimeConditionedHolt | 2026-02-19 13:52:04 | NULL |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 15:59:00 | 0.3405353804263663 | 0.293483394034918 | 0.3875873668178145 | 0.013587957282298835 | RegimeConditionedHolt | 2026-02-19 13:52:04 | NULL |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 16:59:00 | 0.33948349095917607 | 0.2872808296839907 | 0.39168615223436143 | 0.013587957282298835 | RegimeConditionedHolt | 2026-02-19 13:52:04 | NULL |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 17:59:00 | 0.33843160149198587 | 0.28145595014187913 | 0.3954072528420926 | 0.013587957282298835 | RegimeConditionedHolt | 2026-02-19 13:52:04 | NULL |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 18:59:00 | 0.33737971202479566 | 0.2759199287276254 | 0.39883949532196594 | 0.013587957282298835 | RegimeConditionedHolt | 2026-02-19 13:52:04 | NULL |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 19:59:00 | 0.33632782255760546 | 0.2706128872339446 | 0.4020427578812663 | 0.013587957282298835 | RegimeConditionedHolt | 2026-02-19 13:52:04 | NULL |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 20:59:00 | 0.33527593309041526 | 0.2654922482950073 | 0.40505961788582323 | 0.013587957282298835 | RegimeConditionedHolt | 2026-02-19 13:52:04 | NULL |
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2023-11-08 21:59:00 | 0.33422404362322505 | 0.2605264906657933 | 0.4079215965806568 | 0.013587957282298835 | RegimeConditionedHolt | 2026-02-19 13:52:04 | NULL |

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
**Row Count:** 178,438  
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
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

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
| 2025-09-14 23:00:00 | 63.32 | ALERT | 3.3034000396728516 | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 27.610000610351562 | NORMAL | 0.351 | NULL |
| 2025-09-14 22:30:00 | 65.28 | ALERT | 3.046999931335449 | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 34.15999984741211 | NORMAL | 0.338 | NULL |
| 2025-09-14 22:00:00 | 66.57 | ALERT | 2.240799903869629 | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 57.709999084472656 | NORMAL | 0.297 | NULL |
| 2025-09-14 21:30:00 | 67.14 | ALERT | 2.1868999004364014 | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 59.279998779296875 | NORMAL | 0.295 | NULL |
| 2025-09-14 21:00:00 | 67.61 | ALERT | 2.6960999965667725 | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 44.150001525878906 | NORMAL | 0.32 | NULL |
| 2025-09-14 20:30:00 | 67.99 | ALERT | 2.827500104904175 | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 40.29999923706055 | NORMAL | 0.326 | NULL |
| 2025-09-14 20:00:00 | 67.55 | ALERT | 1.7128000259399414 | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 72.0 | NORMAL | 0.27 | NULL |
| 2025-09-14 19:30:00 | 65.74 | ALERT | 1.1124000549316406 | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 84.08999633789062 | NORMAL | 0.24 | NULL |
| 2025-09-14 19:00:00 | 63.17 | ALERT | 2.201200008392334 | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 58.869998931884766 | NORMAL | 0.294 | NULL |
| 2025-09-14 18:30:00 | 60.21 | ALERT | 0.2718999981880188 | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 93.55000305175781 | NORMAL | 0.198 | NULL |

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
| RunID | uniqueidentifier | YES | — | — |

---


## dbo.ACM_MultivariateForecast

**Primary Key:** ID  
**Row Count:** 14,280  
**Date Range:** 2022-08-16 14:50:00 to 2024-06-23 01:59:00  

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
**Row Count:** 65  

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
| 746 | 8aad982a-390e-4991-b900-87e771fcbb68 | 5000 | pca | 5 | 500 | 790 | 4.663680276071255 | NULL | NULL |
| 745 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | pca | 5 | 500 | 788 | 4.638329479045257 | NULL | NULL |
| 744 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | pls | 5 | 2067 | 790 | 4.625547177975389 | NULL | NULL |
| 743 | a097c3f5-720d-408f-be4f-99dc16e56e12 | 1 | pls | 5 | 240 | 90 | 1.0070371235288889 | NULL | NULL |
| 696 | f50286f4-235d-4511-b1c1-7daf37418f49 | 5013 | pls | 5 | 1803 | 790 | 5.356561210694018 | NULL | NULL |
| 694 | 228a2c70-9dd9-4fa3-88a1-221eb648e918 | 5013 | pls | 5 | 1871 | 788 | 4.51626175709523 | NULL | NULL |
| 692 | 50de5c8e-e820-4706-8929-51f362d8e88e | 5013 | pls | 5 | 1787 | 788 | 6.803779071912991 | NULL | NULL |
| 690 | fea26c14-286c-4479-a544-b5ac307d99e4 | 5013 | pls | 5 | 1553 | 788 | 5.06703728858633 | NULL | NULL |
| 688 | 3841a482-2bff-43f8-8d6b-40cc8e00b8c9 | 5013 | pls | 5 | 1391 | 790 | 4.866499603053593 | NULL | NULL |
| 686 | 8fedfa1f-e5e2-4902-8007-29409a9a8d08 | 5013 | pls | 5 | 1870 | 788 | 5.6335311054954715 | NULL | NULL |

---


## dbo.ACM_PCA_Loadings

**Primary Key:** ID  
**Row Count:** 169,700  
**Date Range:** 2026-01-19 16:20:07 to 2026-03-08 13:28:32  

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
| 2974300 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 5 | wind_speed_4_avg_rz | -3.6220905080606546e-06 | 3.6220905080606546e-06 | 2026-03-08 13:28:32 |
| 2974299 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 5 | wind_speed_3_std_rz | -9.168593494259199e-07 | 9.168593494259199e-07 | 2026-03-08 13:28:32 |
| 2974298 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 5 | wind_speed_3_min_rz | -7.930679882274505e-06 | 7.930679882274505e-06 | 2026-03-08 13:28:32 |
| 2974297 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 5 | wind_speed_3_max_rz | 1.4916448913465901e-06 | 1.4916448913465901e-06 | 2026-03-08 13:28:32 |
| 2974296 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 5 | wind_speed_3_avg_rz | -3.6563804979242456e-06 | 3.6563804979242456e-06 | 2026-03-08 13:28:32 |
| 2974295 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 5 | sensor_9_avg_rz | -1.621307712250229e-06 | 1.621307712250229e-06 | 2026-03-08 13:28:32 |
| 2974294 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 5 | sensor_8_avg_rz | -8.696826063718618e-07 | 8.696826063718618e-07 | 2026-03-08 13:28:32 |
| 2974293 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 5 | sensor_7_avg_rz | -7.255132589005572e-07 | 7.255132589005572e-07 | 2026-03-08 13:28:32 |
| 2974292 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 5 | sensor_6_avg_rz | 1.188942356144307e-06 | 1.188942356144307e-06 | 2026-03-08 13:28:32 |
| 2974291 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 5 | sensor_5_std_rz | 4.809298433633986e-05 | 4.809298433633986e-05 | 2026-03-08 13:28:32 |

---


## dbo.ACM_PCA_Metrics

**Primary Key:** ID  
**Row Count:** 85  
**Date Range:** 2026-01-19 10:47:24 to 2026-03-13 02:32:57  

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
| 11547 | 8AAD982A-390E-4991-B900-87E771FCBB68 | 5000 | 5 | 0.9999979338395736 | [{"name": "PC1", "type": "variance_ratio", "value": 0.746731457226648, "cumulative": 0.7467314572... | pca_fit | 500 | 790 | 2026-03-13 02:32:57 |
| 11546 | 81FC5E21-957E-49F9-BA8D-C7C22044ADAF | 5010 | 5 | 0.9999983827731812 | [{"name": "PC1", "type": "variance_ratio", "value": 0.5121021111579053, "cumulative": 0.512102111... | pca_fit | 500 | 788 | 2026-03-13 02:32:56 |
| 11545 | 5AF5C5EB-B83F-4453-B30F-3ABBAB80E376 | 5038 | 5 | 0.9999965246354436 | [{"name": "PC1", "type": "variance_ratio", "value": 0.7715643562212764, "cumulative": 0.771564356... | pca_fit | 2067 | 790 | 2026-03-12 17:33:57 |
| 11544 | A097C3F5-720D-408F-BE4F-99DC16E56E12 | 1 | 5 | 0.9962869206405607 | [{"name": "PC1", "type": "variance_ratio", "value": 0.8718312155650458, "cumulative": 0.871831215... | pca_fit | 240 | 90 | 2026-03-12 17:30:09 |
| 11311 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 5 | 0.9999995743767165 | [{"name": "PC1", "type": "variance_ratio", "value": 0.8898301778578616, "cumulative": 0.889830177... | pca_fit | 1871 | 790 | 2026-03-08 07:58:32 |
| 11310 | 442AA522-4B2A-4068-ADAE-D8F7B0F8C297 | 5013 | 5 | 0.9999995743767165 | [{"name": "PC1", "type": "variance_ratio", "value": 0.8898301778578616, "cumulative": 0.889830177... | pca_fit | 1870 | 790 | 2026-03-08 07:57:28 |
| 11309 | 76197100-B482-4094-8E64-F3DF8CA194C3 | 5013 | 5 | 0.9999995743767165 | [{"name": "PC1", "type": "variance_ratio", "value": 0.8898301778578616, "cumulative": 0.889830177... | pca_fit | 1868 | 790 | 2026-03-08 07:54:34 |
| 11308 | 0159A32A-354A-456F-AC02-58E7930EC60F | 5013 | 5 | 0.9999995743767165 | [{"name": "PC1", "type": "variance_ratio", "value": 0.8898301778578616, "cumulative": 0.889830177... | pca_fit | 1871 | 790 | 2026-03-08 07:51:49 |
| 11307 | 183FA102-0939-470E-A8EA-C8513AD4D894 | 5013 | 5 | 0.9999995743767165 | [{"name": "PC1", "type": "variance_ratio", "value": 0.8898301778578616, "cumulative": 0.889830177... | pca_fit | 1871 | 790 | 2026-03-08 07:48:59 |
| 11305 | E08EBBE9-824E-4B56-A270-1365F6282276 | 5013 | 5 | 0.9999995743767165 | [{"name": "PC1", "type": "variance_ratio", "value": 0.8898301778578616, "cumulative": 0.889830177... | pca_fit | 1871 | 790 | 2026-03-08 07:45:42 |

---


## dbo.ACM_PCA_Models

**Primary Key:** ID  
**Row Count:** 91  
**Date Range:** 2026-01-19 16:20:06 to 2026-03-08 07:58:32  

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
| 10911 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 10 | 5 | 0.9999995743767165 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10910 | 442AA522-4B2A-4068-ADAE-D8F7B0F8C297 | 5013 | 10 | 5 | 0.9999995743767165 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10909 | 76197100-B482-4094-8E64-F3DF8CA194C3 | 5013 | 10 | 5 | 0.9999995743767165 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10908 | 0159A32A-354A-456F-AC02-58E7930EC60F | 5013 | 10 | 5 | 0.9999995743767165 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10907 | 183FA102-0939-470E-A8EA-C8513AD4D894 | 5013 | 10 | 5 | 0.9999995743767165 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10905 | E08EBBE9-824E-4B56-A270-1365F6282276 | 5013 | 10 | 5 | 0.9999995743767165 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10903 | 76B00271-2EA6-4477-9ED7-7890E5A219EC | 5013 | 10 | 5 | 0.9999995743767165 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10902 | 7D450CAB-83C9-4039-AD50-2633E4B67642 | 5013 | 10 | 5 | 0.9999995743767165 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10900 | F50286F4-235D-4511-B1C1-7DAF37418F49 | 5013 | 10 | 5 | 0.9999995743767165 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |
| 10898 | 228A2C70-9DD9-4FA3-88A1-221EB648E918 | 5013 | 10 | 5 | 0.9999990350314018 | NULL | NULL | NULL | {"scaler": "RobustStandardScaler", "with_mean": true, "with_std": true} |

---


## dbo.ACM_RUL

**Primary Key:** EquipID, RunID  
**Row Count:** 42  
**Date Range:** 2026-01-19 18:14:31 to 2026-02-23 15:37:42  

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
| 2621 | B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 0.0 | 0.0 | 0.0 | 0.0 | 0.3 | 2026-02-19 13:52:07 | Multipath | 1000 |
| 2621 | 00ABD2ED-842D-460B-8349-365C553C2EA5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 13:54:55 | Multipath | 1000 |
| 2621 | 92FDD807-E680-4DEB-AE14-8C7F79C9B9CD | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 14:05:58 | Multipath | 1000 |
| 2621 | E8F6AFC3-C5E5-4C26-A7BB-A6A0D748CF4F | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 14:01:57 | Multipath | 1000 |
| 2621 | F3F9203B-865B-4FDF-B62D-D3A57D23FD92 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 14:09:08 | Multipath | 1000 |
| 2621 | 92F4BBCF-C282-4499-831C-DE0E917C5507 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 2026-02-19 13:58:31 | Multipath | 1000 |
| 5014 | CB9C3AA5-411D-4730-A12A-10771C81D03D | 168.0 | 163.00985373523335 | 168.0 | 172.99014626476665 | 0.6802992460187132 | 2026-02-19 19:41:28 | Multipath | 1000 |
| 5014 | F3A31632-7341-45E5-AC7B-165608C75055 | 168.0 | 163.00985373523335 | 168.0 | 172.99014626476665 | 0.6802992460187132 | 2026-02-19 19:31:38 | Multipath | 1000 |
| 5014 | 511CBFD0-74F2-44AE-BFD3-1B905FB141EF | 0.0 | 0.0 | 0.0 | 0.0 | 0.3 | 2026-02-12 18:57:01 | Multipath | 1000 |
| 5014 | A2B144B6-98AF-4671-8268-4D6777E46DE9 | 168.0 | 163.00985373523335 | 168.0 | 172.99014626476665 | 0.6802992460187132 | 2026-02-19 20:25:37 | Multipath | 1000 |

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
**Row Count:** 91  
**Date Range:** 2026-01-19 10:49:23 to 2026-03-08 13:28:28  

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
| RunID | uniqueidentifier | YES | — | — |
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

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
| 992 | 5013 | 2026-03-08 13:28:28 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | False | NULL |
| 991 | 5013 | 2026-03-08 13:26:44 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-03-08 13:28:26 |
| 990 | 5013 | 2026-03-08 13:23:53 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-03-08 13:26:02 |
| 989 | 5013 | 2026-03-08 13:21:09 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-03-08 13:23:13 |
| 988 | 5013 | 2026-03-08 13:18:10 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-03-08 13:20:30 |
| 986 | 5013 | 2026-03-08 13:14:04 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-03-08 13:17:29 |
| 984 | 5013 | 2026-03-08 13:11:15 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-03-08 13:13:26 |
| 983 | 5013 | 2026-03-08 13:08:27 | Anomaly rate too low; Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-03-08 13:10:32 |
| 981 | 5013 | 2026-03-08 13:05:40 | Silhouette score too low | NULL | NULL | NULL | 0.0 | True | 2026-03-08 13:07:45 |
| 979 | 5013 | 2026-03-08 13:01:04 | Detector saturation too high: 50.7%; Anomaly rate too high; Silhouette score too low; anomaly_rat... | 0.5505077498663816 | NULL | NULL | 0.0 | True | 2026-03-08 13:03:21 |

---


## dbo.ACM_RegimeBinnerState

**Primary Key:** EquipID  
**Row Count:** 1  
**Date Range:** 2026-03-12 12:40:20 to 2026-03-12 12:40:20  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| EquipID | int | NO | 10 | — |
| StateJson | nvarchar | NO | -1 | — |
| UpdatedAt | datetime2 | NO | — | (sysutcdatetime()) |

### Top 10 Records

| EquipID | StateJson | UpdatedAt |
| --- | --- | --- |
| 5010 | {"binner_type": "OnlinePCABinner", "state_version": 1, "n_bins": 3, "min_rows_for_assignment": 20... | 2026-03-12 12:40:20 |

---


## dbo.ACM_RegimeDefinitions

**Primary Key:** ID  
**Row Count:** 353  
**Date Range:** 2026-01-19 10:47:55 to 2026-03-13 02:35:18  

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
| 5323 | 5010 | 1 | 10 | Regime_10 | [-0.3754312800509589, -0.37367005007607595, 0.9433671448911939, 0.7847548169749123, -0.1701092954... | ["sensor_50", "sensor_45", "sensor_48", "sensor_51", "sensor_18_max", "sensor_18_avg", "sensor_18... | 14 | 0.15363219435529885 | UNKNOWN |
| 5322 | 5010 | 1 | 9 | Regime_9 | [-0.1304461478509686, -0.1282733123410832, 0.5503682480617003, 0.769108306277882, -0.309219836511... | ["sensor_50", "sensor_45", "sensor_48", "sensor_51", "sensor_18_max", "sensor_18_avg", "sensor_18... | 22 | 0.15363219435529885 | UNKNOWN |
| 5321 | 5010 | 1 | 8 | Regime_8 | [-0.0980145496626695, -0.09624076262116432, 0.4543054269419776, 0.7754338582356771, -0.5374726918... | ["sensor_50", "sensor_45", "sensor_48", "sensor_51", "sensor_18_max", "sensor_18_avg", "sensor_18... | 18 | 0.15363219435529885 | UNKNOWN |
| 5320 | 5010 | 1 | 7 | Regime_7 | [-0.670539517151682, -0.6660881701268648, 1.1858231017464085, 0.7774874599356401, -0.302868968954... | ["sensor_50", "sensor_45", "sensor_48", "sensor_51", "sensor_18_max", "sensor_18_avg", "sensor_18... | 19 | 0.15363219435529885 | UNKNOWN |
| 5319 | 5010 | 1 | 6 | Regime_6 | [-0.1785080378705805, -0.1709699942307039, 0.24757643856785513, 0.712625427679582, -0.83715070377... | ["sensor_50", "sensor_45", "sensor_48", "sensor_51", "sensor_18_max", "sensor_18_avg", "sensor_18... | 11 | 0.15363219435529885 | UNKNOWN |
| 5318 | 5010 | 1 | 5 | Regime_5 | [-0.2660481562981239, -0.2635182050558237, 0.8131271738272446, 0.7818228098062369, -0.42845284251... | ["sensor_50", "sensor_45", "sensor_48", "sensor_51", "sensor_18_max", "sensor_18_avg", "sensor_18... | 13 | 0.15363219435529885 | UNKNOWN |
| 5317 | 5010 | 1 | 4 | Regime_4 | [-0.8278393699572637, -0.8236213143055255, 1.2657776429102972, 0.7860096876437848, -0.39324810986... | ["sensor_50", "sensor_45", "sensor_48", "sensor_51", "sensor_18_max", "sensor_18_avg", "sensor_18... | 13 | 0.15363219435529885 | UNKNOWN |
| 5316 | 5010 | 1 | 3 | Regime_3 | [-1.0200830479462941, -1.012015203634898, 1.2153875907262166, 0.7677746653556824, -0.892588198184... | ["sensor_50", "sensor_45", "sensor_48", "sensor_51", "sensor_18_max", "sensor_18_avg", "sensor_18... | 15 | 0.15363219435529885 | UNKNOWN |
| 5315 | 5010 | 1 | 2 | Regime_2 | [-0.987086155696919, -0.9858956634998322, 0.9913156275686464, 0.8884640367407548, -1.470223912675... | ["sensor_50", "sensor_45", "sensor_48", "sensor_51", "sensor_18_max", "sensor_18_avg", "sensor_18... | 76 | 0.15363219435529885 | UNKNOWN |
| 5314 | 5010 | 1 | 1 | Regime_1 | [0.7466706434111299, 0.743096326832814, -0.9847607903909189, -0.9572239154323334, 0.8449615409447... | ["sensor_50", "sensor_45", "sensor_48", "sensor_51", "sensor_18_max", "sensor_18_avg", "sensor_18... | 223 | 0.15363219435529885 | UNKNOWN |

---


## dbo.ACM_RegimeOccupancy

**Primary Key:** ID  
**Row Count:** 356  
**Date Range:** 2026-01-19 10:47:56 to 2026-03-13 02:35:19  

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
| 3727 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 5 | 4.0 | 0.05333333333333334 | NULL | NULL | 2026-03-13 02:35:19 |
| 3726 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | -1 | 5.0 | 0.06666666666666667 | NULL | NULL | 2026-03-13 02:35:19 |
| 3725 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 2 | 6.0 | 0.08 | NULL | NULL | 2026-03-13 02:35:19 |
| 3724 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 0 | 7.0 | 0.09333333333333334 | NULL | NULL | 2026-03-13 02:35:19 |
| 3723 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 8 | 18.0 | 0.24 | NULL | NULL | 2026-03-13 02:35:19 |
| 3722 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 1 | 35.0 | 0.4666666666666667 | NULL | NULL | 2026-03-13 02:35:19 |
| 3721 | 8aad982a-390e-4991-b900-87e771fcbb68 | 5000 | 7 | 18.0 | 0.23684210526315788 | NULL | NULL | 2026-03-13 02:35:19 |
| 3720 | 8aad982a-390e-4991-b900-87e771fcbb68 | 5000 | 11 | 24.0 | 0.3157894736842105 | NULL | NULL | 2026-03-13 02:35:19 |
| 3719 | 8aad982a-390e-4991-b900-87e771fcbb68 | 5000 | 10 | 34.0 | 0.4473684210526316 | NULL | NULL | 2026-03-13 02:35:19 |
| 3718 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | 0 | 38.0 | 0.027576197387518143 | NULL | NULL | 2026-03-12 17:34:07 |

---


## dbo.ACM_RegimePromotionLog

**Primary Key:** ID  
**Row Count:** 3  
**Date Range:** 2026-02-12 19:22:29 to 2026-03-08 12:46:58  

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
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

### Top 10 Records

| ID | RunID | EquipID | RegimeLabel | FromState | ToState | Reason | DataPointsAtPromotion | PromotedAt | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | f3a31632-7341-45e5-ac7b-165608c75055 | 5014 | ALL | LEARNING | CONVERGED | met_promotion_criteria | NULL | 2026-02-12 19:22:29 | NULL |
| 15 | 67f4ea1e-839c-404d-a0f9-f0244f7c9ce0 | 5073 | ALL | LEARNING | CONVERGED | met_promotion_criteria | NULL | 2026-02-16 14:18:00 | NULL |
| 26 | 3841a482-2bff-43f8-8d6b-40cc8e00b8c9 | 5013 | ALL | LEARNING | CONVERGED | met_promotion_criteria | NULL | 2026-03-08 12:46:58 | 2026-03-08 07:16:58 |

---


## dbo.ACM_RegimeState

**Primary Key:** EquipID, StateVersion  
**Row Count:** 12  
**Date Range:** 2026-01-19 11:15:21 to 2026-03-13 02:35:18  

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
| RunID | uniqueidentifier | YES | — | — |
| TrainingDistanceThreshold | float | YES | 53 | — |

### Top 10 Records

| EquipID | StateVersion | NumClusters | ClusterCentersJson | ScalerMeanJson | ScalerScaleJson | PCAComponentsJson | PCAExplainedVarianceJson | NumPCAComponents | SilhouetteScore |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 6 | [[0.1646979027339826, -0.03554037309126265, 0.04162685526904867, 0.18204991352100733, 0.181057056... | [] | [] | [] | [] | 0 | -4145.147672980784 |
| 2621 | 1 | 2 | [[-2.3927035908545218, -2.2698907544535976, -2.208915356666811, -2.495260569357103, -2.2201025485... | [] | [] | [] | [] | 0 | 0.3629990738412058 |
| 5000 | 1 | 12 | [[-0.9886413704265248, -0.9850806241685693, 1.1612387868491085, 1.168316906148737, -1.22235801003... | [] | [] | [] | [] | 0 | 0.22157529406247406 |
| 5010 | 1 | 11 | [[-0.7096360509212201, -0.7084470574672406, 0.9449254881877166, 0.7124604638665915, 0.89055572564... | [] | [] | [] | [] | 0 | 0.15363219435529885 |
| 5013 | 1 | 1 | [[-0.033614975009559206, -0.07584260027186072, 0.002345370437925587, -0.10521073375249083, -0.029... | [] | [] | [] | [] | 0 | 0.31079908156021396 |
| 5014 | 1 | 1 | [[-0.20023603674552864, -0.2140056704724666, -0.17770929907437402, -0.21086075964598006, -0.19976... | [] | [] | [] | [] | 0 | 0.3435195568636159 |
| 5022 | 1 | 6 | [[0.1579588728662056, 0.07203454524278641, -0.582069956732879, 0.2650839024640961, 0.175274254362... | [] | [] | [] | [] | 0 | 13964.492082195597 |
| 5038 | 1 | 1 | [[0.022938467029341103, 0.022814275224376394, -0.028869937926329307, -0.0283872287305105, 0.02683... | [] | [] | [] | [] | 0 | 0.28942691991305536 |
| 5040 | 1 | 1 | [[-0.3941072882770908, -0.4446593098880631, -0.3873493754165497, -0.44196369945213804, -0.3994147... | [] | [] | [] | [] | 0 | 0.34386520771131646 |
| 5073 | 1 | 1 | [[-0.13235348313119744, -0.12717771616026602, -0.1262806180613999, -0.11270656806343875, -0.12995... | [] | [] | [] | [] | 0 | 0.3236908270493521 |

### Bottom 10 Records

| EquipID | StateVersion | NumClusters | ClusterCentersJson | ScalerMeanJson | ScalerScaleJson | PCAComponentsJson | PCAExplainedVarianceJson | NumPCAComponents | SilhouetteScore |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8635 | 1 | 149 | [[1.8034518665510186, 1.8035551232201859, 1.8032345950859299, 1.8034807627165266, -0.648410913382... | [] | [] | [] | [] | 0 | 0.5734027175979401 |
| 8632 | 1 | 4 | [[-1.2725832563492852, -1.2852776817266303, -1.2611694904838422], [1.0826237901397373, 0.80368454... | [] | [] | [] | [] | 0 | 0.31570874719918407 |
| 5073 | 1 | 1 | [[-0.13235348313119744, -0.12717771616026602, -0.1262806180613999, -0.11270656806343875, -0.12995... | [] | [] | [] | [] | 0 | 0.3236908270493521 |
| 5040 | 1 | 1 | [[-0.3941072882770908, -0.4446593098880631, -0.3873493754165497, -0.44196369945213804, -0.3994147... | [] | [] | [] | [] | 0 | 0.34386520771131646 |
| 5038 | 1 | 1 | [[0.022938467029341103, 0.022814275224376394, -0.028869937926329307, -0.0283872287305105, 0.02683... | [] | [] | [] | [] | 0 | 0.28942691991305536 |
| 5022 | 1 | 6 | [[0.1579588728662056, 0.07203454524278641, -0.582069956732879, 0.2650839024640961, 0.175274254362... | [] | [] | [] | [] | 0 | 13964.492082195597 |
| 5014 | 1 | 1 | [[-0.20023603674552864, -0.2140056704724666, -0.17770929907437402, -0.21086075964598006, -0.19976... | [] | [] | [] | [] | 0 | 0.3435195568636159 |
| 5013 | 1 | 1 | [[-0.033614975009559206, -0.07584260027186072, 0.002345370437925587, -0.10521073375249083, -0.029... | [] | [] | [] | [] | 0 | 0.31079908156021396 |
| 5010 | 1 | 11 | [[-0.7096360509212201, -0.7084470574672406, 0.9449254881877166, 0.7124604638665915, 0.89055572564... | [] | [] | [] | [] | 0 | 0.15363219435529885 |
| 5000 | 1 | 12 | [[-0.9886413704265248, -0.9850806241685693, 1.1612387868491085, 1.168316906148737, -1.22235801003... | [] | [] | [] | [] | 0 | 0.22157529406247406 |

---


## dbo.ACM_RegimeTimeline

**Primary Key:** No primary key  
**Row Count:** 178,438  
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
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

### Top 10 Records

| Timestamp | RegimeLabel | RegimeState | RunID | EquipID | AssignmentConfidence | RegimeVersion | ID | IsNovel | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2019-03-08 11:30:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360034 | False | NULL |
| 2019-03-08 12:00:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360035 | False | NULL |
| 2019-03-08 12:30:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360036 | False | NULL |
| 2019-03-08 13:00:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360037 | False | NULL |
| 2019-03-08 13:30:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360038 | False | NULL |
| 2019-03-08 14:00:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360039 | False | NULL |
| 2019-03-08 14:30:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360040 | False | NULL |
| 2019-03-08 15:00:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360041 | False | NULL |
| 2019-03-08 15:30:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360042 | False | NULL |
| 2019-03-08 16:00:00 | 2 | unknown | 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | 1.0 | NULL | 360043 | False | NULL |

### Bottom 10 Records

| Timestamp | RegimeLabel | RegimeState | RunID | EquipID | AssignmentConfidence | RegimeVersion | ID | IsNovel | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-09-14 23:00:00 | 4 | unknown | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 0.994 | NULL | 1970317 | False | 2026-03-07 06:11:15 |
| 2025-09-14 22:30:00 | 4 | unknown | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 0.999 | NULL | 1970316 | False | 2026-03-07 06:11:15 |
| 2025-09-14 22:00:00 | 4 | unknown | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 0.987 | NULL | 1970315 | False | 2026-03-07 06:11:15 |
| 2025-09-14 21:30:00 | 4 | unknown | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 1.0 | NULL | 1970314 | False | 2026-03-07 06:11:15 |
| 2025-09-14 21:00:00 | 4 | unknown | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 1.0 | NULL | 1970313 | False | 2026-03-07 06:11:15 |
| 2025-09-14 20:30:00 | 4 | unknown | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 0.72 | NULL | 1970312 | False | 2026-03-07 06:11:15 |
| 2025-09-14 20:00:00 | 4 | unknown | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 0.993 | NULL | 1970311 | False | 2026-03-07 06:11:15 |
| 2025-09-14 19:30:00 | 4 | unknown | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 1.0 | NULL | 1970310 | False | 2026-03-07 06:11:15 |
| 2025-09-14 19:00:00 | 4 | unknown | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 0.998 | NULL | 1970309 | False | 2026-03-07 06:11:15 |
| 2025-09-14 18:30:00 | 4 | unknown | DEE1203B-4721-4CBE-9E8E-19303624A28A | 1 | 1.0 | NULL | 1970308 | False | 2026-03-07 06:11:15 |

---


## dbo.ACM_RegimeTransitions

**Primary Key:** ID  
**Row Count:** 1,022  
**Date Range:** 2026-01-19 10:47:57 to 2026-03-13 02:35:21  

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
| 8518 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 2 | 8 | 1 | 1.0 | 2026-03-13 02:35:21 |
| 8517 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 0 | 2 | 1 | 1.0 | 2026-03-13 02:35:21 |
| 8516 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | -1 | 0 | 1 | 0.3333333333333333 | 2026-03-13 02:35:21 |
| 8515 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | -1 | 8 | 2 | 0.6666666666666666 | 2026-03-13 02:35:21 |
| 8514 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 8 | 5 | 1 | 0.25 | 2026-03-13 02:35:21 |
| 8513 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 8 | -1 | 3 | 0.75 | 2026-03-13 02:35:21 |
| 8512 | 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 1 | 8 | 1 | 1.0 | 2026-03-13 02:35:21 |
| 8511 | 8aad982a-390e-4991-b900-87e771fcbb68 | 5000 | 7 | 11 | 1 | 1.0 | 2026-03-13 02:35:20 |
| 8510 | 8aad982a-390e-4991-b900-87e771fcbb68 | 5000 | 10 | 7 | 1 | 1.0 | 2026-03-13 02:35:20 |
| 8509 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | 0 | -1 | 10 | 1.0 | 2026-03-12 17:34:07 |

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


## dbo.ACM_RepresentationSchemas

**Primary Key:** RunID, EquipID, Timestamp  
**Row Count:** 20  
**Date Range:** 2022-08-08 06:00:00 to 2025-09-14 23:30:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | varchar | NO | 64 | — |
| EquipID | int | NO | 10 | — |
| Timestamp | datetime2 | NO | — | — |
| RepresentationVersion | nvarchar | NO | 64 | — |
| SchemaVersion | nvarchar | NO | 64 | — |
| BasisSignature | nvarchar | NO | 128 | — |
| BaselinePackageVersion | nvarchar | NO | 128 | — |
| SignalProfileVersion | nvarchar | NO | 64 | — |
| SchemaCompatibility | nvarchar | YES | 64 | — |
| BasisCompatibility | nvarchar | YES | 64 | — |
| MissingSignalsJson | nvarchar | YES | -1 | — |
| NewSignalsJson | nvarchar | YES | -1 | — |
| InvalidatedFeaturesJson | nvarchar | YES | -1 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

### Top 10 Records

| RunID | EquipID | Timestamp | RepresentationVersion | SchemaVersion | BasisSignature | BaselinePackageVersion | SignalProfileVersion | SchemaCompatibility | BasisCompatibility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | COMPATIBLE | COMPATIBLE |
| 4cf9f1c6-f55a-4f84-ad66-a924d05c5fbf | 1 | 2025-09-14 23:30:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | 2023-07-17 07:40:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | UNASSESSED |
| 5f4d313f-19f2-4278-893d-cb5a04cd420e | 1 | 2025-09-14 23:30:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| 6704067f-df3c-43d1-a482-960b73e96e62 | 5000 | 2022-08-13 06:00:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| 70631f62-1a62-4302-9ab9-14fec0643b88 | 5010 | 2022-10-16 08:30:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| 7bee3349-151f-40ee-af7e-194eb9eece87 | 5010 | 2022-10-14 08:30:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| 7f16ac41-d523-4b03-b7dc-0d35b69b37b6 | 1 | 2025-09-14 23:30:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| 80581aa0-39ef-4330-b9ea-832c443fe4b2 | 5000 | 2022-08-14 06:00:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 2022-10-13 08:30:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | UNASSESSED |

### Bottom 10 Records

| RunID | EquipID | Timestamp | RepresentationVersion | SchemaVersion | BasisSignature | BaselinePackageVersion | SignalProfileVersion | SchemaCompatibility | BasisCompatibility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| fdab2ed7-7571-4f1c-b5da-875410c0d8d8 | 1 | 2025-09-14 23:30:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| e569dc4d-c2d6-4be4-b48e-54f8bd7dd83e | 5000 | 2022-08-12 06:00:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| d3fe0f8c-8b2a-453a-86c0-b8e068c1685d | 5010 | 2022-10-18 08:30:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| b71d3cf5-c462-4873-ad6a-7eef33a45f15 | 5000 | 2022-08-10 06:00:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| b59dd1ea-fe94-485c-a27c-24c3a7395f74 | 5010 | 2022-10-15 08:30:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| b53a0140-d75c-4746-87b9-c90db65a50a6 | 5010 | 2022-10-17 08:30:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| a4a7ad70-2697-453a-958f-26cfc649fe05 | 5010 | 2022-10-19 08:30:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| 9c8134da-b2bf-48f3-8489-8728aaabea22 | 5000 | 2022-08-09 06:00:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | PENDING |
| 8aad982a-390e-4991-b900-87e771fcbb68 | 5000 | 2022-08-08 06:00:00 | 2026.2.0-draft | unbound | pending | pending | shadow-v0 | PENDING | UNASSESSED |

---


## dbo.ACM_RepresentationStatus

**Primary Key:** RunID, EquipID, Timestamp  
**Row Count:** 20  
**Date Range:** 2022-08-08 06:00:00 to 2025-09-14 23:30:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | varchar | NO | 64 | — |
| EquipID | int | NO | 10 | — |
| Timestamp | datetime2 | NO | — | — |
| SourceWindowStart | datetime2 | YES | — | — |
| SourceWindowEnd | datetime2 | YES | — | — |
| WindowLabel | nvarchar | YES | 32 | — |
| Enabled | bit | NO | — | ((1)) |
| Authoritative | bit | NO | — | ((0)) |
| RepresentationVersion | nvarchar | NO | 64 | — |
| SchemaVersion | nvarchar | NO | 64 | — |
| BasisSignature | nvarchar | NO | 128 | — |
| BaselinePackageVersion | nvarchar | NO | 128 | — |
| SignalProfileVersion | nvarchar | NO | 64 | — |
| CoverageRatio | float | YES | 53 | — |
| StaleRatio | float | YES | 53 | — |
| MissingnessGrade | nvarchar | YES | 32 | — |
| EffectiveSignalCount | int | YES | 10 | — |
| ExpectedRows | int | YES | 10 | — |
| ObservedRows | int | YES | 10 | — |
| DuplicateRowsRemoved | int | YES | 10 | — |
| FutureRowsDropped | int | YES | 10 | — |
| MonitorableSignalCount | int | YES | 10 | — |
| WeakSignalCount | int | YES | 10 | — |
| UntrustedSignalCount | int | YES | 10 | — |
| SignalSummaryReasonsJson | nvarchar | YES | -1 | — |
| ContextID | nvarchar | YES | 128 | — |
| ContextLabel | nvarchar | YES | 128 | — |
| ContextConfidence | float | YES | 53 | — |
| ContextStability | nvarchar | YES | 32 | — |
| TransitionStatus | nvarchar | YES | 32 | — |
| ContextIsNovel | bit | NO | — | ((0)) |
| ContextIsAmbiguous | bit | NO | — | ((1)) |
| SchemaCompatibility | nvarchar | YES | 64 | — |
| BasisCompatibility | nvarchar | YES | 64 | — |
| BaselineCompatibility | nvarchar | YES | 64 | — |
| ScoreAllowed | bit | YES | — | — |
| LearnAllowed | bit | YES | — | — |
| RepresentationConfidence | float | YES | 53 | — |
| InputIntegrityGrade | nvarchar | YES | 32 | — |
| ContextStabilityGrade | nvarchar | YES | 32 | — |
| DegradedReasonsJson | nvarchar | YES | -1 | — |
| SuppressedReasonsJson | nvarchar | YES | -1 | — |
| MissingSignalsJson | nvarchar | YES | -1 | — |
| NewSignalsJson | nvarchar | YES | -1 | — |
| InvalidatedFeaturesJson | nvarchar | YES | -1 | — |
| NotesJson | nvarchar | YES | -1 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

### Top 10 Records

| RunID | EquipID | Timestamp | SourceWindowStart | SourceWindowEnd | WindowLabel | Enabled | Authoritative | RepresentationVersion | SchemaVersion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | 2023-07-04 08:30:00 | 2023-07-17 07:40:00 | score | True | True | 2026.2.0-draft | unbound |
| 4cf9f1c6-f55a-4f84-ad66-a924d05c5fbf | 1 | 2025-09-14 23:30:00 | 2025-09-10 00:00:00 | 2025-09-14 23:30:00 | train | True | True | 2026.2.0-draft | unbound |
| 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | 2023-07-17 07:40:00 | 2023-07-07 18:10:00 | 2023-07-17 07:40:00 | score | True | True | 2026.2.0-draft | unbound |
| 5f4d313f-19f2-4278-893d-cb5a04cd420e | 1 | 2025-09-14 23:30:00 | 2025-09-10 00:00:00 | 2025-09-14 23:30:00 | train | True | True | 2026.2.0-draft | unbound |
| 6704067f-df3c-43d1-a482-960b73e96e62 | 5000 | 2022-08-13 06:00:00 | 2022-08-12 06:10:00 | 2022-08-13 06:00:00 | train | True | True | 2026.2.0-draft | unbound |
| 70631f62-1a62-4302-9ab9-14fec0643b88 | 5010 | 2022-10-16 08:30:00 | 2022-10-15 08:40:00 | 2022-10-16 08:30:00 | train | True | True | 2026.2.0-draft | unbound |
| 7bee3349-151f-40ee-af7e-194eb9eece87 | 5010 | 2022-10-14 08:30:00 | 2022-10-13 08:40:00 | 2022-10-14 08:30:00 | train | True | True | 2026.2.0-draft | unbound |
| 7f16ac41-d523-4b03-b7dc-0d35b69b37b6 | 1 | 2025-09-14 23:30:00 | 2025-09-10 00:00:00 | 2025-09-14 23:30:00 | train | True | True | 2026.2.0-draft | unbound |
| 80581aa0-39ef-4330-b9ea-832c443fe4b2 | 5000 | 2022-08-14 06:00:00 | 2022-08-13 06:10:00 | 2022-08-14 06:00:00 | train | True | True | 2026.2.0-draft | unbound |
| 81fc5e21-957e-49f9-ba8d-c7c22044adaf | 5010 | 2022-10-13 08:30:00 | 2022-10-12 20:10:00 | 2022-10-13 08:30:00 | score | True | True | 2026.2.0-draft | unbound |

### Bottom 10 Records

| RunID | EquipID | Timestamp | SourceWindowStart | SourceWindowEnd | WindowLabel | Enabled | Authoritative | RepresentationVersion | SchemaVersion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | 2022-08-10 06:10:00 | 2022-08-11 06:00:00 | train | True | True | 2026.2.0-draft | unbound |
| fdab2ed7-7571-4f1c-b5da-875410c0d8d8 | 1 | 2025-09-14 23:30:00 | 2025-09-10 00:00:00 | 2025-09-14 23:30:00 | train | True | True | 2026.2.0-draft | unbound |
| e569dc4d-c2d6-4be4-b48e-54f8bd7dd83e | 5000 | 2022-08-12 06:00:00 | 2022-08-11 06:10:00 | 2022-08-12 06:00:00 | train | True | True | 2026.2.0-draft | unbound |
| d3fe0f8c-8b2a-453a-86c0-b8e068c1685d | 5010 | 2022-10-18 08:30:00 | 2022-10-17 08:40:00 | 2022-10-18 08:30:00 | train | True | True | 2026.2.0-draft | unbound |
| b71d3cf5-c462-4873-ad6a-7eef33a45f15 | 5000 | 2022-08-10 06:00:00 | 2022-08-09 06:10:00 | 2022-08-10 06:00:00 | train | True | True | 2026.2.0-draft | unbound |
| b59dd1ea-fe94-485c-a27c-24c3a7395f74 | 5010 | 2022-10-15 08:30:00 | 2022-10-14 10:30:00 | 2022-10-15 08:30:00 | train | True | True | 2026.2.0-draft | unbound |
| b53a0140-d75c-4746-87b9-c90db65a50a6 | 5010 | 2022-10-17 08:30:00 | 2022-10-16 08:40:00 | 2022-10-17 08:30:00 | train | True | True | 2026.2.0-draft | unbound |
| a4a7ad70-2697-453a-958f-26cfc649fe05 | 5010 | 2022-10-19 08:30:00 | 2022-10-18 08:40:00 | 2022-10-19 08:30:00 | train | True | True | 2026.2.0-draft | unbound |
| 9c8134da-b2bf-48f3-8489-8728aaabea22 | 5000 | 2022-08-09 06:00:00 | 2022-08-08 06:10:00 | 2022-08-09 06:00:00 | train | True | True | 2026.2.0-draft | unbound |
| 8aad982a-390e-4991-b900-87e771fcbb68 | 5000 | 2022-08-08 06:00:00 | 2022-08-07 17:30:00 | 2022-08-08 06:00:00 | score | True | True | 2026.2.0-draft | unbound |

---


## dbo.ACM_RunLogs

**Primary Key:** ID  
**Row Count:** 950  
**Date Range:** 2026-03-10 09:06:17 to 2026-03-13 08:10:16  

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

### Top 10 Records

| ID | RunID | EquipID | LoggedAt | Level | Component | Message | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | NULL | NULL | 2026-03-10 09:06:17 | INFO | CONFIG | Config loaded from SQL for WFA_TURBINE_10 (EquipID=5010, 292 params) | 2026-03-10 09:06:27 |
| 2 | NULL | NULL | 2026-03-10 09:06:17 | INFO | RUN | Run started: WFA_TURBINE_10 (ID=5010) \| RunID=d9a5c548 \| window=[2026-02-13 05:12:17.572448+00:00... | 2026-03-10 09:06:27 |
| 126 | NULL | NULL | 2026-03-10 09:10:54 | INFO | CONFIG | Config loaded from SQL for WFA_TURBINE_10 (EquipID=5010, 292 params) | 2026-03-10 09:10:54 |
| 127 | NULL | NULL | 2026-03-10 09:10:54 | INFO | RUN | Run started: WFA_TURBINE_10 (ID=5010) \| RunID=a66a6b25 \| window=[2026-02-13 05:16:44.308239+00:00... | 2026-03-10 09:10:54 |
| 316 | NULL | NULL | 2026-03-10 09:16:26 | INFO | CONFIG | Config loaded from SQL for WFA_TURBINE_10 (EquipID=5010, 292 params) | 2026-03-10 09:16:26 |
| 317 | NULL | NULL | 2026-03-10 09:16:26 | INFO | RUN | Run started: WFA_TURBINE_10 (ID=5010) \| RunID=c8edba41 \| window=[2026-02-13 05:22:16.224031+00:00... | 2026-03-10 09:16:26 |
| 436 | NULL | NULL | 2026-03-10 09:20:37 | INFO | CONFIG | Config loaded from SQL for WFA_TURBINE_10 (EquipID=5010, 292 params) | 2026-03-10 09:20:37 |
| 437 | NULL | NULL | 2026-03-10 09:20:37 | INFO | RUN | Run started: WFA_TURBINE_10 (ID=5010) \| RunID=bac19837 \| window=[2026-02-13 05:26:27.468665+00:00... | 2026-03-10 09:20:37 |
| 488 | NULL | NULL | 2026-03-10 09:54:35 | INFO | CONFIG | Config loaded from SQL for WFA_TURBINE_10 (EquipID=5010, 289 params) | 2026-03-10 09:54:35 |
| 489 | NULL | NULL | 2026-03-10 09:54:35 | INFO | RUN | Run started: WFA_TURBINE_10 (ID=5010) \| RunID=f803081b \| window=[2026-02-13 06:00:25.877731+00:00... | 2026-03-10 09:54:35 |

### Bottom 10 Records

| ID | RunID | EquipID | LoggedAt | Level | Component | Message | CreatedAt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 15512 | A4A7AD70-2697-453A-958F-26CFC649FE05 | 5010 | 2026-03-13 08:10:16 | INFO | OUTPUT | SQL insert to ACM_RepresentationStatus: 1 rows | 2026-03-13 08:10:16 |
| 15511 | A4A7AD70-2697-453A-958F-26CFC649FE05 | 5010 | 2026-03-13 08:10:16 | INFO | REPRESENTATION | Representation authority short-circuited feature, detector, regime, zero-day, and health stages a... | 2026-03-13 08:10:16 |
| 15510 | A4A7AD70-2697-453A-958F-26CFC649FE05 | 5010 | 2026-03-13 08:10:16 | INFO | REPRESENTATION | Representation validation authority activated | 2026-03-13 08:10:16 |
| 15509 | A4A7AD70-2697-453A-958F-26CFC649FE05 | 5010 | 2026-03-13 08:10:16 | INFO | REPRESENTATION | Representation shadow pipeline completed | 2026-03-13 08:10:16 |
| 15508 | A4A7AD70-2697-453A-958F-26CFC649FE05 | 5010 | 2026-03-13 08:10:16 | INFO | REPRESENTATION | Representation shadow comparability evaluated | 2026-03-13 08:10:16 |
| 15507 | A4A7AD70-2697-453A-958F-26CFC649FE05 | 5010 | 2026-03-13 08:10:16 | INFO | BASELINE | Baseline: score head (144 rows) \| extended=False | 2026-03-13 08:10:16 |
| 15506 | A4A7AD70-2697-453A-958F-26CFC649FE05 | 5010 | 2026-03-13 08:10:16 | WARNING | BASELINE | Cannot do 50/50 split (too few rows: 144), using first 144 for baseline. | 2026-03-13 08:10:16 |
| 15505 | A4A7AD70-2697-453A-958F-26CFC649FE05 | 5010 | 2026-03-13 08:10:16 | INFO | TIMER | data_split_complete  train_rows=0 train_cols=79 score_rows=144 score_cols=79 | 2026-03-13 08:10:16 |
| 15504 | A4A7AD70-2697-453A-958F-26CFC649FE05 | 5010 | 2026-03-13 08:10:16 | INFO | REPRESENTATION | Representation validation authority activated | 2026-03-13 08:10:16 |
| 15503 | A4A7AD70-2697-453A-958F-26CFC649FE05 | 5010 | 2026-03-13 08:10:16 | INFO | REPRESENTATION | Representation shadow pipeline completed | 2026-03-13 08:10:16 |

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
**Row Count:** 1,440  
**Date Range:** 2026-01-22 09:47:11 to 2026-03-08 13:28:28  

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
| 15300 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | fusion.n_samples.pca_t2_z | 1871.0 | NULL | 2026-03-08 13:28:28 |
| 15299 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | fusion.n_samples.pca_spe_z | 1871.0 | NULL | 2026-03-08 13:28:28 |
| 15298 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | fusion.n_samples.omr_z | 1871.0 | NULL | 2026-03-08 13:28:28 |
| 15297 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | fusion.n_samples.iforest_z | 1871.0 | NULL | 2026-03-08 13:28:28 |
| 15296 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | fusion.n_samples.gmm_z | 1871.0 | NULL | 2026-03-08 13:28:28 |
| 15295 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | fusion.n_samples.ar1_z | 1871.0 | NULL | 2026-03-08 13:28:28 |
| 15294 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | fusion.quality.pca_t2_z | 0.0 | NULL | 2026-03-08 13:28:28 |
| 15293 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | fusion.quality.pca_spe_z | 0.0 | NULL | 2026-03-08 13:28:28 |
| 15292 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | fusion.quality.omr_z | 0.0 | NULL | 2026-03-08 13:28:28 |
| 15291 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | fusion.quality.iforest_z | 0.0 | NULL | 2026-03-08 13:28:28 |

---


## dbo.ACM_Run_Stats

**Primary Key:** RecordID  
**Row Count:** 95  
**Date Range:** 2018-12-01 00:00:00 to 2025-07-30 05:56:00  

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
| 11241 | 81FC5E21-957E-49F9-BA8D-C7C22044ADAF | 5010 | 2022-10-09 08:40:00 | 2022-10-13 08:39:59 | 75 | 75 | 79 | 100.0 | NULL |
| 11240 | 8AAD982A-390E-4991-B900-87E771FCBB68 | 5000 | 2022-08-04 06:10:00 | 2022-08-08 06:09:59 | 76 | 76 | 79 | 100.0 | NULL |
| 11236 | 240FD3C1-4BEC-4739-A91E-6C777703F7DF | 5038 | 2023-06-22 07:40:00 | 2023-07-17 07:40:00 | 1723 | 1723 | 79 | 100.0 | NULL |
| 11234 | 5AF5C5EB-B83F-4453-B30F-3ABBAB80E376 | 5038 | 2023-06-22 07:40:00 | 2023-07-17 07:40:00 | 1378 | 1378 | 81 | 100.0 | NULL |
| 11041 | D41C8634-B66D-43AB-9A39-82DF56FD6409 | 5013 | 2023-04-29 10:32:00 | 2023-05-25 10:19:59 | 1871 | 1871 | 79 | 100.0 | 5.730353355407715 |
| 11040 | 442AA522-4B2A-4068-ADAE-D8F7B0F8C297 | 5013 | 2023-04-03 10:44:00 | 2023-04-29 10:31:59 | 1871 | 1871 | 79 | 100.0 | 1.6453566551208496 |
| 11039 | 76197100-B482-4094-8E64-F3DF8CA194C3 | 5013 | 2023-03-08 10:56:00 | 2023-04-03 10:43:59 | 1869 | 1869 | 79 | 100.0 | 1.9471795558929443 |
| 11038 | 0159A32A-354A-456F-AC02-58E7930EC60F | 5013 | 2023-02-10 11:08:00 | 2023-03-08 10:55:59 | 1872 | 1872 | 79 | 100.0 | 2.5092036724090576 |
| 11037 | 183FA102-0939-470E-A8EA-C8513AD4D894 | 5013 | 2023-01-15 11:20:00 | 2023-02-10 11:07:59 | 1872 | 1872 | 79 | 100.0 | 1.5903555154800415 |
| 11035 | E08EBBE9-824E-4B56-A270-1365F6282276 | 5013 | 2022-12-20 11:32:00 | 2023-01-15 11:19:59 | 1871 | 1871 | 79 | 100.0 | 2.138697385787964 |

---


## dbo.ACM_Runs

**Primary Key:** RunID  
**Row Count:** 122  
**Date Range:** 2026-01-19 10:47:02 to 2026-03-13 02:39:56  

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
| ZeroDayScoringActive | bit | YES | — | — |
| ZeroDayStatus | nvarchar | YES | 64 | — |
| ZeroDaySurfaceType | nvarchar | YES | 64 | — |
| ZeroDayChannelCount | int | YES | 10 | — |
| RepresentationAuthoritative | bit | YES | — | — |
| RepresentationScoreAllowed | bit | YES | — | — |
| RepresentationLearnAllowed | bit | YES | — | — |
| RepresentationContextLabel | nvarchar | YES | 128 | — |
| RepresentationRuntimeMode | nvarchar | YES | 64 | — |
| RepresentationSchemaCompatibility | nvarchar | YES | 64 | — |
| RepresentationBasisCompatibility | nvarchar | YES | 64 | — |
| RepresentationBaselineCompatibility | nvarchar | YES | 64 | — |
| RepresentationSuppressedReasons | nvarchar | YES | -1 | — |
| RepresentationDegradedReasons | nvarchar | YES | -1 | — |

### Top 10 Records

| RunID | EquipID | EquipName | StartedAt | CompletedAt | DurationSeconds | ConfigSignature | TrainRowCount | ScoreRowCount | EpisodeCount |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5E8005D5-E9D9-4062-97A8-00550C2E74A7 | 1 | FD_FAN | 2026-03-07 05:48:49 | 2026-03-07 05:50:20 | 90 |  | 153 | 606 | 1 |
| 964366C3-6C10-4F6A-BFA9-0466763F6688 | 5000 | WFA_TURBINE_0 | 2026-03-13 02:30:41 | 2026-03-13 02:30:43 | 0 |  | 0 | 0 | 0 |
| 13E09A70-A9E1-4546-A883-067F4DCD1861 | 5040 | WFA_TURBINE_40 | 2026-03-07 07:10:53 | 2026-03-07 07:13:00 | 127 |  | 1870 | 1872 | 1 |
| B4DCBEC9-3EC2-4F5D-A774-095F4F2A387C | 5073 | WFA_TURBINE_73 | 2026-02-16 08:32:39 | 2026-02-16 08:42:25 | 584 |  | 1809 | 3152 | 19 |
| 7F16AC41-D523-4B03-B7DC-0D35B69B37B6 | 1 | FD_FAN | 2026-03-13 02:17:11 | 2026-03-13 02:17:11 | 0 |  | 0 | 0 | 0 |
| B2F3A6C1-B13D-4B25-85DA-1074CFE5AD41 | 2621 | GAS_Turbine | 2026-02-19 08:19:55 | 2026-02-19 08:22:34 | 158 |  | 89 | 642 | 2 |
| CB9C3AA5-411D-4730-A12A-10771C81D03D | 5014 | WFA_TURBINE_14 | 2026-02-12 14:02:48 | 2026-02-12 14:11:57 | 549 |  | 2706 | 3162 | 5 |
| C238BAB0-1834-486E-BDAF-11662D8EDEF9 | 2621 | GAS_Turbine | 2026-02-19 08:33:55 | 2026-02-19 08:33:55 | 0 |  | 0 | 0 | 0 |
| E08EBBE9-824E-4B56-A270-1365F6282276 | 5013 | WFA_TURBINE_13 | 2026-03-08 07:42:41 | 2026-03-08 07:45:46 | 185 |  | 1871 | 5841 | 18 |
| 426D1667-856F-4574-B325-148A97D172A0 | 5073 | WFA_TURBINE_73 | 2026-02-16 08:51:43 | 2026-02-16 09:03:27 | 703 |  | 2179 | 3152 | 22 |

### Bottom 10 Records

| RunID | EquipID | EquipName | StartedAt | CompletedAt | DurationSeconds | ConfigSignature | TrainRowCount | ScoreRowCount | EpisodeCount |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3432CDEB-C8DC-4B88-9826-FE8108973C5F | 1 | FD_FAN | 2026-03-07 05:46:39 | 2026-03-07 05:48:20 | 100 |  | 172 | 626 | 2 |
| AF435408-E910-48A8-B7A7-FB7D927517DA | 5073 | WFA_TURBINE_73 | 2026-02-16 09:56:56 | 2026-02-16 10:07:00 | 603 |  | 2257 | 3162 | 1 |
| 471B19A1-2521-40B7-A20B-F9C2C6950D96 | 5073 | WFA_TURBINE_73 | 2026-02-16 10:07:32 | 2026-02-16 10:07:43 | 10 |  | 2257 | 3162 | 26 |
| BAA6A63F-E11C-4B7C-9069-F7E222CDE784 | 1 | FD_FAN | 2026-03-07 06:09:40 | 2026-03-07 06:10:22 | 41 |  | 53 | 506 | 1 |
| E752AFBF-D494-4BB4-B865-F4FE4703EE97 | 5073 | WFA_TURBINE_73 | 2026-02-16 09:56:38 | 2026-02-16 09:56:49 | 11 |  | 2262 | 3162 | 24 |
| 76197100-B482-4094-8E64-F3DF8CA194C3 | 5013 | WFA_TURBINE_13 | 2026-03-08 07:52:26 | 2026-03-08 07:54:38 | 131 |  | 1869 | 5843 | 22 |
| E211FDF4-2C57-4DD6-8AAE-F0E0802F21F8 | 8632 | WIND_TURBINE | 2026-01-19 11:14:27 | 2026-01-19 11:17:50 | 203 |  | 716 | 161 | 16 |
| 67F4EA1E-839C-404D-A0F9-F0244F7C9CE0 | 5073 | WFA_TURBINE_73 | 2026-02-16 08:43:13 | 2026-02-16 08:50:54 | 460 |  | 2262 | 3152 | 33 |
| D368144C-EAEC-4F8F-85DB-ED8134627F8A | 5040 | WFA_TURBINE_40 | 2026-03-07 07:23:31 | 2026-03-07 07:25:35 | 122 |  | 1882 | 1884 | 1 |
| 6899A3B2-FB5B-4BB7-8C52-ED27857A3F7A | 8635 | COND_PUMP_MOTOR | 2026-01-19 12:52:29 | 2026-01-19 12:57:08 | 278 |  | 3120 | 561 | 26 |

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
**Row Count:** 178,438  
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
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

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
| 2025-09-14 23:00:00 | 2.779062509536743 | 7.489570140838623 | 6.457658290863037 | NULL | -8.0 | 5.906191825866699 | 0.5057986378669739 | 0.5057986378669739 | NULL |
| 2025-09-14 22:30:00 | 3.6076278686523438 | 6.576656341552734 | 5.659628391265869 | NULL | -8.0 | 5.054296970367432 | 0.5021318197250366 | 0.5021318197250366 | NULL |
| 2025-09-14 22:00:00 | 4.222054481506348 | 4.788454532623291 | 4.063197135925293 | NULL | -8.0 | 3.718498706817627 | 0.49188485741615295 | 0.49188485741615295 | NULL |
| 2025-09-14 21:30:00 | 4.59639310836792 | 5.019598484039307 | 3.0566396713256836 | NULL | -8.0 | 3.2421276569366455 | 0.47490596771240234 | 0.47490596771240234 | NULL |
| 2025-09-14 21:00:00 | 6.2233381271362305 | 5.2877888679504395 | 3.3739864826202393 | NULL | -8.0 | 3.4745900630950928 | 0.45669737458229065 | 0.45669737458229065 | NULL |
| 2025-09-14 20:30:00 | 3.5467286109924316 | 6.872095108032227 | 4.07279634475708 | NULL | -8.0 | 5.274816036224365 | 0.4372928738594055 | 0.4372928738594055 | NULL |
| 2025-09-14 20:00:00 | 2.0639095306396484 | 5.421901226043701 | 2.5613322257995605 | NULL | -8.0 | 3.9844560623168945 | 0.4108825623989105 | 0.4108825623989105 | NULL |
| 2025-09-14 19:30:00 | 2.0119292736053467 | 4.476516246795654 | 1.3124407529830933 | NULL | -8.0 | 3.235093116760254 | 0.37309637665748596 | 0.37309637665748596 | NULL |
| 2025-09-14 19:00:00 | 3.9428489208221436 | 5.273157119750977 | 2.7707035541534424 | NULL | -8.0 | 4.628175258636475 | 0.3306559920310974 | 0.3306559920310974 | NULL |
| 2025-09-14 18:30:00 | 2.196481943130493 | 1.4479789733886719 | 1.7440979480743408 | NULL | -8.0 | 2.6327853202819824 | 0.2878144383430481 | 0.2878144383430481 | NULL |

---


## dbo.ACM_SeasonalPatterns

**Primary Key:** ID  
**Row Count:** 3,711  
**Date Range:** 2026-01-19 18:26:03 to 2026-03-12 23:04:10  

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
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

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
| 46388 | 5038 | wind_speed_4_avg | DAILY | 24.0 | 1.6059 | 9.0 | 0.4738 | 2026-03-12 23:04:10 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 |
| 46387 | 5038 | wind_speed_3_std | DAILY | 24.0 | 0.4531 | 9.0 | 0.5772 | 2026-03-12 23:04:10 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 |
| 46386 | 5038 | wind_speed_3_min | DAILY | 24.0 | 0.4258 | 19.0 | 0.2794 | 2026-03-12 23:04:10 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 |
| 46385 | 5038 | wind_speed_3_max | DAILY | 24.0 | 5.3 | 9.0 | 0.5505 | 2026-03-12 23:04:10 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 |
| 46384 | 5038 | wind_speed_3_avg | DAILY | 24.0 | 1.6725 | 9.0 | 0.4803 | 2026-03-12 23:04:10 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 |
| 46383 | 5038 | sensor_9_avg | DAILY | 24.0 | 2.7109 | 10.0 | 0.4112 | 2026-03-12 23:04:10 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 |
| 46382 | 5038 | sensor_8_avg | DAILY | 24.0 | 9.8629 | 10.0 | 0.3822 | 2026-03-12 23:04:10 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 |
| 46381 | 5038 | sensor_7_avg | DAILY | 24.0 | 2.6583 | 12.0 | 0.4527 | 2026-03-12 23:04:10 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 |
| 46380 | 5038 | sensor_6_avg | DAILY | 24.0 | 3.3932 | 10.0 | 0.7368 | 2026-03-12 23:04:10 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 |
| 46379 | 5038 | sensor_5_std | DAILY | 24.0 | 1.6828 | 5.0 | 0.3043 | 2026-03-12 23:04:10 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 |

---


## dbo.ACM_SensorCorrelations

**Primary Key:** ID  
**Row Count:** 18,797  
**Date Range:** 2026-01-19 11:16:02 to 2026-03-12 17:34:08  

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
| 3466343 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | wind_speed_4_avg | wind_speed_4_avg | 1.0 | pearson | 2026-03-12 17:34:08 |
| 3466342 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | wind_speed_3_std | wind_speed_4_avg | 0.8469701495433046 | pearson | 2026-03-12 17:34:08 |
| 3466341 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | wind_speed_3_std | wind_speed_3_std | 1.0 | pearson | 2026-03-12 17:34:08 |
| 3466340 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | wind_speed_3_min | wind_speed_4_avg | 0.7347394249361165 | pearson | 2026-03-12 17:34:08 |
| 3466339 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | wind_speed_3_min | wind_speed_3_std | 0.4542540286017113 | pearson | 2026-03-12 17:34:08 |
| 3466338 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | wind_speed_3_min | wind_speed_3_min | 1.0 | pearson | 2026-03-12 17:34:08 |
| 3466337 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | wind_speed_3_max | wind_speed_4_avg | 0.7787189977919777 | pearson | 2026-03-12 17:34:08 |
| 3466336 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | wind_speed_3_max | wind_speed_3_std | 0.8147173296880812 | pearson | 2026-03-12 17:34:08 |
| 3466335 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | wind_speed_3_max | wind_speed_3_min | 0.46311546631658396 | pearson | 2026-03-12 17:34:08 |
| 3466334 | 5af5c5eb-b83f-4453-b30f-3abbab80e376 | 5038 | wind_speed_3_max | wind_speed_3_max | 1.0 | pearson | 2026-03-12 17:34:08 |

---


## dbo.ACM_SensorDefects

**Primary Key:** No primary key  
**Row Count:** 682  
**Date Range:** 2026-03-07 05:48:10 to 2026-03-08 07:58:31  

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
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

### Top 10 Records

| DetectorType | DetectorFamily | Severity | ViolationCount | ViolationPct | MaxZ | AvgZ | CurrentZ | ActiveDefect | RunID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Rare State (IsolationForest) | Rare | CRITICAL | 58 | 37.91 | 8.8585 | 2.1424 | 0.0976 | 0 | 5E8005D5-E9D9-4062-97A8-00550C2E74A7 |
| Density Anomaly (GMM) | Density | CRITICAL | 58 | 37.91 | 10.0 | 2.5058 | 0.3542 | 0 | 5E8005D5-E9D9-4062-97A8-00550C2E74A7 |
| Baseline Consistency (OMR) | Baseline | CRITICAL | 58 | 37.91 | 6.1188 | 1.9849 | 0.1387 | 0 | 5E8005D5-E9D9-4062-97A8-00550C2E74A7 |
| Correlation Break (PCA-SPE) | Correlation | CRITICAL | 40 | 26.14 | 10.0 | 2.1251 | 0.3094 | 0 | 5E8005D5-E9D9-4062-97A8-00550C2E74A7 |
| Multivariate Outlier (PCA-T2) | Multivariate | CRITICAL | 38 | 24.84 | 10.0 | 2.1256 | 2.2055 | 1 | 5E8005D5-E9D9-4062-97A8-00550C2E74A7 |
| Time-Series Anomaly (AR1) | Time-Series | HIGH | 30 | 19.61 | 10.0 | 1.5881 | 0.6422 | 0 | 5E8005D5-E9D9-4062-97A8-00550C2E74A7 |
| cusum_z | cusum_z | LOW | 0 | 0.0 | 1.8924 | 0.849 | 0.055 | 0 | 5E8005D5-E9D9-4062-97A8-00550C2E74A7 |
| drift_z | drift_z | LOW | 0 | 0.0 | 1.8924 | 0.849 | 0.055 | 0 | 5E8005D5-E9D9-4062-97A8-00550C2E74A7 |
| Rare State (IsolationForest) | Rare | CRITICAL | 1870 | 100.0 | 8.0 | 8.0 | 8.0 | 1 | 13E09A70-A9E1-4546-A883-067F4DCD1861 |
| Time-Series Anomaly (AR1) | Time-Series | CRITICAL | 1869 | 99.95 | 8.0 | 7.9961 | 8.0 | 1 | 13E09A70-A9E1-4546-A883-067F4DCD1861 |

### Bottom 10 Records

| DetectorType | DetectorFamily | Severity | ViolationCount | ViolationPct | MaxZ | AvgZ | CurrentZ | ActiveDefect | RunID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Density Anomaly (GMM) | Density | HIGH | 20 | 11.63 | 10.0 | 1.5573 | 0.1279 | 0 | 3432CDEB-C8DC-4B88-9826-FE8108973C5F |
| Time-Series Anomaly (AR1) | Time-Series | HIGH | 27 | 15.7 | 10.0 | 1.4058 | 0.0079 | 0 | 3432CDEB-C8DC-4B88-9826-FE8108973C5F |
| Correlation Break (PCA-SPE) | Correlation | HIGH | 31 | 18.02 | 10.0 | 1.5062 | 0.2861 | 0 | 3432CDEB-C8DC-4B88-9826-FE8108973C5F |
| Baseline Consistency (OMR) | Baseline | HIGH | 32 | 18.6 | 7.5736 | 1.3614 | 0.1017 | 0 | 3432CDEB-C8DC-4B88-9826-FE8108973C5F |
| Rare State (IsolationForest) | Rare | CRITICAL | 36 | 20.93 | 6.883 | 1.4166 | 0.2298 | 0 | 3432CDEB-C8DC-4B88-9826-FE8108973C5F |
| cusum_z | cusum_z | CRITICAL | 58 | 33.72 | 8.0 | 2.6013 | 8.0 | 1 | 3432CDEB-C8DC-4B88-9826-FE8108973C5F |
| drift_z | drift_z | CRITICAL | 58 | 33.72 | 8.0 | 2.6013 | 8.0 | 1 | 3432CDEB-C8DC-4B88-9826-FE8108973C5F |
| Multivariate Outlier (PCA-T2) | Multivariate | CRITICAL | 61 | 35.47 | 10.0 | 2.4809 | 1.2803 | 0 | 3432CDEB-C8DC-4B88-9826-FE8108973C5F |
| Correlation Break (PCA-SPE) | Correlation | LOW | 0 | 0.0 | 1.6996 | 1.6996 | 1.6996 | 0 | AF435408-E910-48A8-B7A7-FB7D927517DA |
| Multivariate Outlier (PCA-T2) | Multivariate | LOW | 0 | 0.0 | 1.3469 | 1.3469 | 1.3469 | 0 | AF435408-E910-48A8-B7A7-FB7D927517DA |

---


## dbo.ACM_SensorForecast

**Primary Key:** RunID, EquipID, Timestamp, SensorName  
**Row Count:** 57,120  
**Date Range:** 2019-05-12 10:30:00 to 2024-06-23 01:00:00  

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
**Row Count:** 1,689  
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
| CreatedAt | datetime2 | YES | — | (sysutcdatetime()) |

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
| DEMO.SIM.06GP34_1FD Fan Outlet Pressure | 2025-09-12 00:00:00 | 2025-09-14 23:00:00 | 2.5342 | 2.5342 | 0.4901 | 0.4901 | 2.565234590842834 | 1.1760110537029163 | 0.8429525401393916 |
| DEMO.SIM.FSAB_1FD Fan Right Inlet Flow | 2025-09-11 18:30:00 | 2025-09-14 23:00:00 | 4.8372 | -4.8372 | 1.2149 | 1.2149 | -61.099998474121094 | 397.95001220703125 | 305.79998779296875 |
| DEMO.SIM.FSAA_1FD Fan Left Inlet Flow | 2025-09-11 17:00:00 | 2025-09-14 23:00:00 | 4.6779 | -4.6779 | 1.2096 | 1.2096 | -63.029998779296875 | 383.5799865722656 | 291.82000732421875 |
| DEMO.SIM.06T32-1_1FD Fan Bearing Temperature | 2025-09-11 16:30:00 | 2025-09-14 23:00:00 | 14.483 | -14.483 | 1.2882 | 1.2882 | -0.1599999964237213 | 63.439998626708984 | 58.24500274658203 |
| DEMO.SIM.06T34_1FD Fan Outlet Termperature | 2025-09-11 15:30:00 | 2025-09-14 23:00:00 | 3.7093 | -3.7093 | 0.6226 | 0.6226 | 5.269999980926514 | 33.2400016784668 | 29.219999313354492 |
| DEMO.SIM.06T31_1FD Fan Inlet Temperature | 2025-09-11 15:00:00 | 2025-09-14 23:00:00 | 5.098 | -5.098 | 2.3913 | 2.3913 | 4.598111185014535 | 48.11000061035156 | 34.21683553293165 |
| DEMO.SIM.06G31_1FD Fan Damper Position | 2025-09-11 12:00:00 | 2025-09-14 23:00:00 | 3.5448 | -3.5448 | 1.436 | 1.436 | -0.6224882006645203 | 49.29117257364498 | 34.900771772030225 |
| DEMO.SIM.06T33-1_1FD Fan Winding Temperature | 2025-09-11 06:30:00 | 2025-09-14 23:00:00 | 5.264 | -5.264 | 1.7352 | 1.7352 | 9.393949649668848 | 55.02000045776367 | 43.70866849065639 |
| DEMO.SIM.06I03_1FD Fan Motor Current | 2025-09-11 06:00:00 | 2025-09-14 23:00:00 | 9.6299 | -9.6299 | 2.258 | 2.258 | 0.11999999731779099 | 45.2400016784668 | 36.66999816894531 |
| DEMO.SIM.06T34_1FD Fan Outlet Termperature | 2025-07-15 14:00:00 | 2025-07-15 23:30:00 | 2.5164 | -2.5164 | 1.0364 | 1.0364 | 17.450000762939453 | 32.90999984741211 | 28.399999618530273 |

---


## dbo.ACM_SensorNormalized_TS

**Primary Key:** ID  
**Row Count:** 678,874  
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
| 11631506 | 5AF5C5EB-B83F-4453-B30F-3ABBAB80E376 | 5038 | 2023-07-17 07:20:00 | wind_speed_4_avg | NULL | 9.678683795686762 | 2026-03-12 17:34:09 |
| 11631505 | 5AF5C5EB-B83F-4453-B30F-3ABBAB80E376 | 5038 | 2023-07-17 05:30:00 | wind_speed_4_avg | NULL | 11.674047867396501 | 2026-03-12 17:34:09 |
| 11631504 | 5AF5C5EB-B83F-4453-B30F-3ABBAB80E376 | 5038 | 2023-07-17 03:40:00 | wind_speed_4_avg | NULL | 13.781505211050549 | 2026-03-12 17:34:09 |
| 11631503 | 5AF5C5EB-B83F-4453-B30F-3ABBAB80E376 | 5038 | 2023-07-17 01:50:00 | wind_speed_4_avg | NULL | 8.831576790095708 | 2026-03-12 17:34:09 |
| 11631502 | 5AF5C5EB-B83F-4453-B30F-3ABBAB80E376 | 5038 | 2023-07-17 00:00:00 | wind_speed_4_avg | NULL | 8.03554476453268 | 2026-03-12 17:34:09 |
| 11631501 | 5AF5C5EB-B83F-4453-B30F-3ABBAB80E376 | 5038 | 2023-07-16 22:10:00 | wind_speed_4_avg | NULL | 11.182904056119003 | 2026-03-12 17:34:09 |
| 11631500 | 5AF5C5EB-B83F-4453-B30F-3ABBAB80E376 | 5038 | 2023-07-16 20:20:00 | wind_speed_4_avg | NULL | 9.22113792752905 | 2026-03-12 17:34:09 |
| 11631499 | 5AF5C5EB-B83F-4453-B30F-3ABBAB80E376 | 5038 | 2023-07-16 18:30:00 | wind_speed_4_avg | NULL | 9.022388394657607 | 2026-03-12 17:34:09 |
| 11631498 | 5AF5C5EB-B83F-4453-B30F-3ABBAB80E376 | 5038 | 2023-07-16 16:40:00 | wind_speed_4_avg | NULL | 8.14455828478177 | 2026-03-12 17:34:09 |
| 11631497 | 5AF5C5EB-B83F-4453-B30F-3ABBAB80E376 | 5038 | 2023-07-16 14:50:00 | wind_speed_4_avg | NULL | 7.295625410220978 | 2026-03-12 17:34:09 |

---


## dbo.ACM_SignalProfiles

**Primary Key:** RunID, EquipID, Timestamp, SignalName  
**Row Count:** 1,302  
**Date Range:** 2022-08-08 06:00:00 to 2025-09-14 23:30:00  

### Schema

| Column | Data Type | Nullable | Length/Precision | Default |
| --- | --- | --- | --- | --- |
| RunID | varchar | NO | 64 | — |
| EquipID | int | NO | 10 | — |
| Timestamp | datetime2 | NO | — | — |
| SignalName | nvarchar | NO | 200 | — |
| MissingRatio | float | YES | 53 | — |
| FlatlineRatio | float | YES | 53 | — |
| EffectiveCadenceSeconds | float | YES | 53 | — |
| MonitorabilityClass | nvarchar | YES | 32 | — |
| ReasonCodesJson | nvarchar | YES | -1 | — |
| SignalProfileVersion | nvarchar | NO | 64 | — |
| CreatedAt | datetime2 | NO | — | (sysutcdatetime()) |

### Top 10 Records

| RunID | EquipID | Timestamp | SignalName | MissingRatio | FlatlineRatio | EffectiveCadenceSeconds | MonitorabilityClass | ReasonCodesJson | SignalProfileVersion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | power_29_avg | 0.0 | 0.08362369337979095 | 600.0 | MONITORABLE | [] | shadow-v0 |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | power_29_max | 0.0 | 0.16550522648083624 | 600.0 | MONITORABLE | [] | shadow-v0 |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | power_29_min | 0.0 | 0.4181184668989547 | 600.0 | MONITORABLE | [] | shadow-v0 |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | power_29_std | 0.0 | 0.08072009291521487 | 600.0 | MONITORABLE | [] | shadow-v0 |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | power_30_avg | 0.0 | 0.027874564459930314 | 600.0 | MONITORABLE | [] | shadow-v0 |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | power_30_max | 0.0 | 0.11788617886178862 | 600.0 | MONITORABLE | [] | shadow-v0 |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | power_30_min | 0.0 | 0.02264808362369338 | 600.0 | MONITORABLE | [] | shadow-v0 |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | power_30_std | 0.0 | 0.01916376306620209 | 600.0 | MONITORABLE | [] | shadow-v0 |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | reactive_power_27_avg | 0.0 | 0.2677119628339141 | 600.0 | MONITORABLE | [] | shadow-v0 |
| 240fd3c1-4bec-4739-a91e-6c777703f7df | 5038 | 2023-07-17 07:40:00 | reactive_power_27_max | 0.0 | 0.7508710801393729 | 600.0 | MONITORABLE | [] | shadow-v0 |

### Bottom 10 Records

| RunID | EquipID | Timestamp | SignalName | MissingRatio | FlatlineRatio | EffectiveCadenceSeconds | MonitorabilityClass | ReasonCodesJson | SignalProfileVersion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | wind_speed_4_avg | 0.0 | 0.03496503496503497 | 600.0 | MONITORABLE | [] | shadow-v0 |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | wind_speed_3_std | 0.0 | 0.11888111888111888 | 600.0 | MONITORABLE | [] | shadow-v0 |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | wind_speed_3_min | 0.0 | 0.04195804195804196 | 600.0 | MONITORABLE | [] | shadow-v0 |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | wind_speed_3_max | 0.0 | 0.0 | 600.0 | MONITORABLE | [] | shadow-v0 |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | wind_speed_3_avg | 0.0 | 0.07692307692307693 | 600.0 | MONITORABLE | [] | shadow-v0 |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | sensor_9_avg | 0.0 | 0.7902097902097902 | 600.0 | MONITORABLE | [] | shadow-v0 |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | sensor_8_avg | 0.0 | 0.4125874125874126 | 600.0 | MONITORABLE | [] | shadow-v0 |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | sensor_7_avg | 0.0 | 0.8251748251748252 | 600.0 | MONITORABLE | [] | shadow-v0 |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | sensor_6_avg | 0.0 | 0.8951048951048951 | 600.0 | MONITORABLE | [] | shadow-v0 |
| ff182cc0-0e06-4ed2-a844-2b46e7fe9996 | 5000 | 2022-08-11 06:00:00 | sensor_53_avg | 0.0 | 0.8671328671328671 | 600.0 | MONITORABLE | [] | shadow-v0 |

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
**Row Count:** 272  
**Date Range:** 2025-12-27 06:26:16 to 2026-03-13 02:35:35  

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
| ar1_params | 1 | 5 | 2026-03-07 05:54:45 | {"n_sensors": 90, "mean_autocorr": 569.6498, "mean_residual_std": 214.0618, "params_count": 180} | {"train_rows": 1001, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06... | NULL | <binary 7167 bytes> |
| calibration_params | 1 | 5 | 2026-03-07 05:54:51 | NULL | NULL | NULL | <binary 600 bytes> |
| gmm_model | 1 | 5 | 2026-03-07 05:54:47 | {"n_components": 3, "covariance_type": "diag", "bic": 2992512204751.83, "aic": 2992512202091.28, ... | {"train_rows": 1001, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06... | NULL | <binary 16253 bytes> |
| iforest_model | 1 | 5 | 2026-03-07 05:54:47 | {"n_estimators": 100, "contamination": 0.01, "max_features": 1.0, "max_samples": 2048} | {"train_rows": 1001, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06... | NULL | <binary 2177353 bytes> |
| omr_model | 1 | 5 | 2026-03-07 05:54:47 | NULL | {"train_rows": 1001, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06... | NULL | <binary 259985 bytes> |
| pca_model | 1 | 5 | 2026-03-07 05:54:45 | {"n_components": 5, "variance_ratio_sum": 0.7636, "variance_ratio_first_component": 0.3633, "vari... | {"train_rows": 1001, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06... | NULL | <binary 22553 bytes> |
| regime_model | 1 | 5 | 2026-03-07 05:54:47 | NULL | {"train_rows": 1001, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06... | NULL | <binary 260643 bytes> |
| ar1_params | 1 | 6 | 2026-03-07 05:56:28 | {"n_sensors": 90, "mean_autocorr": 1871.6606, "mean_residual_std": 872.3882, "params_count": 180} | {"train_rows": 881, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06G... | NULL | <binary 7167 bytes> |
| calibration_params | 1 | 6 | 2026-03-07 05:56:35 | NULL | NULL | NULL | <binary 600 bytes> |
| gmm_model | 1 | 6 | 2026-03-07 05:56:31 | {"n_components": 3, "covariance_type": "diag", "bic": 85875345990661.78, "aic": 85875345988070.45... | {"train_rows": 881, "train_sensors": ["DEMO.SIM.06G31_1FD Fan Damper Position_med", "DEMO.SIM.06G... | NULL | <binary 16525 bytes> |

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

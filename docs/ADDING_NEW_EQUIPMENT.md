# Adding New Equipment to ACM - Checklist

## Prerequisites
- Training data CSV (historical "healthy" data for model fitting)
- Test/Score data CSV (data to analyze for anomalies)
- Both files must have:
  - Timestamp column (will be auto-detected or can be specified)
  - Numeric sensor columns (3+ sensors recommended)
  - Regular sampling cadence (e.g., 30min, 1hr intervals)

## Step-by-Step Process

### 1. Data Preparation
**Location:** `data/` directory

**Required:**
- [ ] Training CSV: `data/{EQUIPMENT}_TRAINING_DATA.csv`
- [ ] Test CSV: `data/{EQUIPMENT}_TEST_DATA.csv`

**Format:**
```csv
timestamp,sensor1,sensor2,sensor3,...
2025-01-01 00:00:00,100.5,25.3,1500,...
2025-01-01 00:30:00,101.2,25.1,1505,...
```

**Notes:**
- Column names should be descriptive (e.g., "Motor_Current", "Bearing_Temp")
- Missing values will be interpolated (small gaps only)
- Timestamp format: ISO8601 or common formats (auto-parsed)

---

### 2. Configuration (MANDATORY)
**Location:** `configs/config_table.csv`

**Get Next EquipID:**
```python
import pandas as pd
df = pd.read_csv('configs/config_table.csv')
next_id = df['EquipID'].max() + 1
```

**Add These Configs:**

#### A. Data Paths (Required)
```csv
EquipID,Category,ParamPath,ParamValue,ValueType,LastUpdated,UpdatedBy,ChangeReason
{ID},data,train_csv,data/{EQUIPMENT}_TRAINING_DATA.csv,string,2025-11-05 00:00:00,USER,new_equipment
{ID},data,score_csv,data/{EQUIPMENT}_TEST_DATA.csv,string,2025-11-05 00:00:00,USER,new_equipment
{ID},data,timestamp_col,,string,2025-11-05 00:00:00,USER,new_equipment
```

#### B. Feature Engineering (Recommended Defaults)
```csv
{ID},features,window,16,int,2025-11-05 00:00:00,USER,new_equipment
{ID},features,fft_bands,"[0.0, 0.1, 0.3, 0.5]",list,2025-11-05 00:00:00,USER,new_equipment
```

#### C. Model Configuration (Recommended)
```csv
{ID},models,ar1.enabled,true,bool,2025-11-05 00:00:00,USER,new_equipment
{ID},models,pca.n_components,5,int,2025-11-05 00:00:00,USER,new_equipment
{ID},models,gmm.enabled,true,bool,2025-11-05 00:00:00,USER,new_equipment
{ID},models,iforest.contamination,0.001,float,2025-11-05 00:00:00,USER,new_equipment
```

#### D. Fusion Weights (Default - will auto-tune)
```csv
{ID},fusion,weights.ar1_z,0.20,float,2025-11-05 00:00:00,USER,new_equipment
{ID},fusion,weights.gmm_z,0.10,float,2025-11-05 00:00:00,USER,new_equipment
{ID},fusion,weights.iforest_z,0.20,float,2025-11-05 00:00:00,USER,new_equipment
{ID},fusion,weights.pca_spe_z,0.20,float,2025-11-05 00:00:00,USER,new_equipment
{ID},fusion,weights.mhal_z,0.20,float,2025-11-05 00:00:00,USER,new_equipment
{ID},fusion,weights.omr_z,0.10,float,2025-11-05 00:00:00,USER,new_equipment_with_omr
```

#### E. Calibration Settings
```csv
{ID},calibration,target_fp_rate,0.001,float,2025-11-05 00:00:00,USER,new_equipment
{ID},calibration,regime_aware,true,bool,2025-11-05 00:00:00,USER,new_equipment
```

#### F. Episode Detection
```csv
{ID},episodes,min_duration,2,int,2025-11-05 00:00:00,USER,new_equipment
{ID},episodes,min_severity,3.0,float,2025-11-05 00:00:00,USER,new_equipment
```

#### G. Outputs
```csv
{ID},outputs,charts.enabled,true,bool,2025-11-05 00:00:00,USER,new_equipment
{ID},outputs,forecast.enabled,true,bool,2025-11-05 00:00:00,USER,new_equipment
```

#### H. Metadata (Optional but Recommended)
```csv
{ID},metadata,equipment_name,{EQUIPMENT},string,2025-11-05 00:00:00,USER,new_equipment
{ID},metadata,equipment_type,{TYPE},string,2025-11-05 00:00:00,USER,new_equipment
{ID},metadata,description,{DESCRIPTION},string,2025-11-05 00:00:00,USER,new_equipment
```

---

### 3. OMR Configuration (Optional - for Multivariate Health)
**Add only if you want OMR enabled:**

```csv
{ID},fusion,weights.omr_z,0.10,float,2025-11-05 00:00:00,USER,omr_enable
{ID},models,omr.model_type,auto,string,2025-11-05 00:00:00,USER,omr_model_selection
{ID},models,omr.n_components,5,int,2025-11-05 00:00:00,USER,omr_latent_dims
{ID},models,omr.min_samples,100,int,2025-11-05 00:00:00,USER,omr_min_train_size
```

**OMR is automatically enabled when `weights.omr_z > 0` (lazy evaluation)**

---

### 4. Running ACM

**Command:**
```bash
python core/acm_main.py \
  --equip "{EQUIPMENT}" \
  --artifact-root "artifacts/{EQUIPMENT}" \
  --mode batch
```

**The script will:**
1. Look up EquipID by matching `metadata.equipment_name == {EQUIPMENT}`
2. Load config from `config_table.csv` for that EquipID
3. Read train/score CSV paths from config
4. Run full pipeline with configured models

**First Run:**
- Models will be fitted on training data
- Cached to `artifacts/{EQUIPMENT}/models/`
- Subsequent runs reuse cached models (unless `--clear-cache`)

---

### 5. Directory Structure Created

```
artifacts/{EQUIPMENT}/
├── models/                          # Cached fitted models
│   ├── ar1_model.joblib
│   ├── pca_model.joblib
│   ├── gmm_model.joblib
│   ├── omr_model.joblib            # If OMR enabled
│   └── regime_model.joblib
├── run_YYYYMMDD_HHMMSS/            # Timestamped run directory
│   ├── tables/                      # 30+ CSV analytics tables
│   │   ├── scores.csv
│   │   ├── episodes.csv
│   │   ├── omr_contributions.csv   # If OMR enabled
│   │   ├── health_timeline.csv
│   │   ├── sensor_hotspots.csv
│   │   └── ...
│   ├── charts/                      # 12+ visualization PNGs
│   │   ├── fused_score_timeline.png
│   │   ├── detector_comparison.png
│   │   ├── episode_heatmap.png
│   │   └── ...
│   └── schema.json                  # Run metadata
```

---

## Quick Start Template

**For rapid equipment addition, copy-paste this into Excel/CSV:**

```csv
EquipID,Category,ParamPath,ParamValue,ValueType,LastUpdated,UpdatedBy,ChangeReason
X,data,train_csv,data/NEW_EQUIP_TRAINING_DATA.csv,string,2025-11-05,USER,init
X,data,score_csv,data/NEW_EQUIP_TEST_DATA.csv,string,2025-11-05,USER,init
X,features,window,16,int,2025-11-05,USER,init
X,models,pca.n_components,5,int,2025-11-05,USER,init
X,fusion,weights.ar1_z,0.20,float,2025-11-05,USER,init
X,fusion,weights.gmm_z,0.10,float,2025-11-05,USER,init
X,fusion,weights.iforest_z,0.20,float,2025-11-05,USER,init
X,fusion,weights.pca_spe_z,0.20,float,2025-11-05,USER,init
X,fusion,weights.mhal_z,0.20,float,2025-11-05,USER,init
X,fusion,weights.omr_z,0.10,float,2025-11-05,USER,init
X,metadata,equipment_name,NEW_EQUIP,string,2025-11-05,USER,init
```

Replace `X` with next EquipID, `NEW_EQUIP` with equipment name.

---

## Validation Checklist

After adding equipment:

- [ ] Config rows added to `config_table.csv`
- [ ] Training CSV exists and has 500+ rows (minimum)
- [ ] Test CSV exists and has 100+ rows (minimum)
- [ ] Both CSVs have same sensor columns (order doesn't matter)
- [ ] Timestamp column exists in both files
- [ ] Run ACM command - should complete without errors
- [ ] Check `artifacts/{EQUIPMENT}/run_*/tables/scores.csv` exists
- [ ] Check `artifacts/{EQUIPMENT}/run_*/charts/` has PNG files
- [ ] If OMR enabled: check `omr_contributions.csv` exists

---

## Troubleshooting

**Error: "Equipment not found in config"**
→ Check `metadata.equipment_name` matches `--equip` argument exactly

**Error: "File not found: data/..."**
→ Check CSV paths in config match actual file locations

**Error: "Not enough samples for training"**
→ Need 100+ rows minimum (500+ recommended) in training data

**Error: "OMR contributions not exported"**
→ Ensure `fusion.weights.omr_z > 0` in config

**Poor anomaly detection:**
→ Adjust fusion weights (increase weights for better-performing detectors)
→ Check `weight_tuning.json` to see auto-tuned weights
→ Increase `calibration.target_fp_rate` if too sensitive (default 0.001 = 0.1%)

---

## Advanced: SQL Mode

To write outputs to SQL database instead of CSV files:

1. Configure SQL connection in `configs/sql_connection.ini`
2. Create ACM tables (see `docs/sql/SQL_SCHEMA_DESIGN.md`)
3. ACM will auto-detect SQL mode and write to database

**Note:** File mode (CSV) is default and works without any SQL setup.

---

## Equipment-Specific Tuning

After initial runs, optimize per equipment:

1. **Review `weight_tuning.json`** - see which detectors work best
2. **Adjust fusion weights** - increase weights for good detectors
3. **Tune `calibration.target_fp_rate`** - lower = fewer alarms (more specific)
4. **Adjust `episodes.min_severity`** - higher = only severe episodes reported
5. **PCA components** - increase if many sensors (rule of thumb: sqrt(n_sensors))
6. **OMR components** - increase if complex correlations (5-10 typical)

---

**Last Updated:** 2025-11-05

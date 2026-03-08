# ACM Accuracy Assessment — Wind Farm A vs Known Defects

**Date:** 2026-03-08
**ACM Version:** v11.15.x
**Status:** Living document — updated as batches complete

---

## Why ACM Keeps Failing to Detect Faults

This is the blunt answer before the data.

**There are three compounding problems that have kept us at 0% detection for months:**

### Problem 1 — Contaminated Training Baselines
ACM trains a "healthy normal" model from the first window of data it sees. If that window contains a fault, the model learns the fault as normal. Every subsequent anomaly score is measured *relative to the contaminated baseline* — so a real fault looks like nothing.

- **T0**: Trained on Aug–Nov 2022 data. That period already had `MinHealth=27–35` and `MaxFusedZ=3.8`. The Aug 2023 generator bearing fault registered `AvgHealth=87.8, MaxFusedZ=1.27` because the baseline *expected* bad data.
- **T10 (batch 1, Oct 2022)**: First batch immediately produced 12 CRITICAL episodes and `MaxFusedZ=13.9, DriftState=FAULT`. This is before the Dec 2022 bearing fault — the turbine was already in distress when ACM started seeing it. So the model learned distressed behavior as baseline.

**The fix is not a code change — it is data strategy**: we need to identify and train only on clean healthy periods, or source clean pre-fault data.

### Problem 2 — Too Few Batches / LEARNING State Never Advances
Models need ≥3 consecutive clean scoring batches to reach CONVERGED. With 1–2 batches total on most turbines, the model never gets promoted. In LEARNING state, CUSUM thresholds haven't stabilized, calibration is noisy, and fusion weights are unreliable.

| Turbine | Batches Run | Model State | Fault Coverage |
|---------|-------------|-------------|----------------|
| T0      | 15          | CONVERGED   | Aug 2023 only  |
| T10     | 1 complete  | LEARNING    | Oct 2022 only  |
| T13     | 15          | LEARNING    | Apr 2023 only  |

### Problem 3 — Missing Historian Data
T11 and T21 have zero rows in their data tables. These turbines have 4 known fault events between them and ACM has never touched them.

---

## Data Coverage vs Known Faults

| Turbine | Historian Range | ACM Scored | Fault Events |
|---------|----------------|------------|-------------|
| T0 (5000) | 2022-08-04 → 2023-08-24 | ✅ 15 runs | 3 |
| T10 (5010) | 2022-10-09 → 2023-10-18 | ⚠️ 1 batch done, running | 3 |
| T13 (5013) | 2022-04-30 → 2023-05-25 | ✅ 15 runs | 2 (only Apr covered) |
| T11 (5011) | **EMPTY** | ❌ 0 runs | 1 |
| T21 (5021) | **EMPTY** | ❌ 0 runs | 3 |

---

## Fault-by-Fault Detection Results

### T0 — WFA_TURBINE_0 (CONVERGED, 15 runs)

| Fault | Window | Data Available | Episodes in Window | MaxFusedZ | AvgHealth | Verdict |
|-------|--------|:-:|-----|-----------|-----------|---------|
| Hydraulic group | 2023-06-10–17 | ❌ No | — | — | — | NO DATA |
| **Generator bearing** | **2023-08-06–20** | **✅ Yes** | **15 MEDIUM** | **1.27** | **87.8** | **MISSED** |
| Hydraulic group | 2023-10-12–19 | ❌ No | — | — | — | NO DATA |

**Root cause of missed detection (T0, Aug 2023):**
Training data (Aug–Nov 2022) contained severe anomalous behavior (`MinHealth=27`, `MaxFusedZ=3.8`). The model normalized to a degraded state. During the Aug 2023 bearing fault, `AvgHealth=87.8` (actually *higher* than training average) and `MaxFusedZ=1.27` — the fault produced no statistical contrast.

**Comparison — fault vs normal periods (T0):**
| Period | AvgHealth | MaxFusedZ |
|--------|-----------|-----------|
| Normal Jan 2023 | 87.5 | 1.24 |
| Normal Apr–May 2023 | 82.2 | 1.24 |
| **Fault Aug 2023** | **87.8** | **1.27** |

The fault window is *statistically indistinguishable from normal*. This is a baseline contamination problem.

---

### T13 — WFA_TURBINE_13 (LEARNING, 2 runs, 15 batches per run)

| Fault | Window | Data Available | Episodes in Window | MaxFusedZ | AvgHealth | Verdict |
|-------|--------|:-:|-----|-----------|-----------|---------|
| **Hydraulic group** | **2023-04-19–26** | **✅ Yes** | **8 LOW** | **1.34** | **90.9** | **MISSED** |
| Hydraulic group | 2023-09-05–12 | ❌ No | — | — | — | NO DATA |

**Root cause of missed detection (T13, Apr 2023):**
Model is LEARNING (2 runs, `SilhouetteScore=0.33`). Calibration thresholds are not stable. `MaxFusedZ=1.34` during the fault — only marginally above baseline. Episodes are LOW severity and not fault-driven. Need more runs + cleaner training baseline.

---

### T10 — WFA_TURBINE_10 (LEARNING, 1 batch complete, running now)

**Batch 1 results (2022-10-24 → 2022-11-03):**
- 12 CRITICAL episodes, all `Density Anomaly (GMM)`
- `MaxFusedZ = 13.9`
- `DriftState = FAULT`
- 77 extreme anomaly scores
- **This is the pre-fault period** — T10 was already abnormal in Oct 2022

| Fault | Window | Data Available | Status |
|-------|--------|:-:|--------|
| **Generator bearing** | **2022-12-26 → 2023-01-26** | **✅ Yes** | 🔄 Running |
| Hydraulic group | 2023-09-09–16 | ✅ Yes | 🔄 Running |
| Gearbox failure | 2023-10-11–18 | ✅ Yes | 🔄 Running |

**Observation**: The Oct 2022 data is already in FAULT state. This means the model will train on pre-fault distressed data as its baseline — same contamination problem as T0. The detection verdict for the Dec 2022 bearing fault will likely be "not discriminable from training noise."

**Key calibration warnings from batch 1 log:**
- `Contamination filter excluded 37.8% > max 30%` — training data heavily contaminated
- Self-tuning clamping threshold to 1000.0 repeatedly — calibration unable to converge on meaningful thresholds
- `gmm_z ↔ iforest_z: 0.97`, `gmm_z ↔ omr_z: 0.99` — three detectors nearly identical, effective ensemble is 3 detectors not 6

---

### T11 — WFA_TURBINE_11
**Historian: EMPTY.** No data imported. Transformer failure (2023-07-28 → 2023-08-11) never evaluated.

### T21 — WFA_TURBINE_21
**Historian: EMPTY.** No data imported. Hydraulic (Aug 2023), Gearbox (Oct 2023), Gearbox bearings (Oct 2023) never evaluated.

---

## Overall Detection Scorecard

| Metric | Count |
|--------|-------|
| Known fault events (all turbines) | 11 |
| Events with data in historian | 5 (T0×1, T10×3, T13×1) |
| Events with ACM scoring completed | 2 (T0 gen bearing, T13 hydraulic) |
| **True detections** | **0** |
| **False negatives (missed)** | **2** |
| **No data / not yet scored** | **9** |

**Detection rate on scored events: 0/2 = 0%**
**Detection rate if all data existed: 0/5 = 0% (so far)**

---

## What Needs to Happen (Priority Order)

### Immediate — Data
1. **Investigate T11 and T21 empty historian tables.** These turbines have 4 known faults — we can't assess anything without data. Check if CSV source files exist.
2. **Source clean baseline data for T0 and T10.** Both trained on contaminated windows. Need healthy-only periods from before fault onset.

### Short-term — Classification Correctness
3. **Fix baseline contamination detection.** ACM needs to detect when training data is unhealthy and refuse to set a contaminated baseline. The `37.8% contamination` warning already fires — it just doesn't stop training.
4. **Validate T10 as more batches complete.** The generator bearing fault (Dec 2022–Jan 2023) should produce a detectable signal if the baseline model was trained on pre-contamination data. Watch batches 2–15 closely.
5. **Regime clustering — T10 has only 1 cluster.** HDBSCAN found 1 cluster across the entire operating range. Wind turbines should have multiple operating regimes (low/medium/high wind, startup, shutdown). Single cluster = the regime system is not discriminating properly.

### Medium-term — More Data
6. **Import additional turbines.** WFA0_DataSample.json and WFA13_DataSample.json exist. The `chunked/` folder has FD_FAN, GAS_TURBINE, MILL data. Use the existing `load_wind_turbine_data.py` and `load_historian_from_csv.py` scripts.
7. **Cross-validate on labeled fault data.** The `event_info.csv` normal/anomaly labels should be used as a ground-truth test set, not just for post-hoc checking.

---

## T10 Live Progress (updated each batch)

| Batch | Window | Episodes | MaxFusedZ | Regime OK | Status |
|-------|--------|----------|-----------|-----------|--------|
| 1 | Oct 24 – Nov 03 2022 | 12 CRITICAL | 13.9 | ✅ | ✅ Done |
| 2 | Nov 03 – Dec 13 2022 | — | — | — | 🔄 Running |
| ... | ... | ... | ... | ... | ... |
| Target | Dec 26 2022 – Jan 26 2023 | ? | ? | ? | Fault window |

---

*Update this table after each batch completes. Run `python scripts/db_health_check.py --equip WFA_TURBINE_10` to get latest.*

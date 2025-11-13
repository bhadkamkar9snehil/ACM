# ACM EXPLAINER – How the Autonomous Condition Monitoring System Thinks

**Version:** 2025-11-11
**Purpose:** Explain, in human terms, what ACM does, why it uses many detectors, what “fusion” means, and how to interpret the outcomes.

---

## 1. Purpose

ACM (Autonomous Condition Monitoring) is not a single algorithm — it is a **multi-view analytical system** that watches every asset from several perspectives simultaneously.

Each *detector head* captures a unique kind of abnormality.
The goal is **not just to flag “something’s wrong”**, but to **understand what kind of deviation** is happening, when it began, and which sensors are responsible.

---

## 2. The Multi-Head Framework

### 2.1 Detector Heads – Core Idea

| Head                             | Method                                          | Focus                                 | What It Detects                                                 |
| -------------------------------- | ----------------------------------------------- | ------------------------------------- | --------------------------------------------------------------- |
| **AR1**                          | 1-step autoregression                           | Temporal self-consistency             | Detects control oscillations, instability, erratic noise bursts |
| **PCA (SPE/T²)**                 | Principal Component projection & reconstruction | Statistical variance structure        | Detects broad data shape change, abnormal spread or new cluster |
| **Mahalanobis Distance**         | Multivariate covariance distance                | Geometric distance from normal cloud  | Detects uniform multi-sensor drift or scaling                   |
| **GMM (Gaussian Mixture Model)** | Probabilistic cluster membership                | Regime membership probability         | Detects entry into new operating condition or unseen regime     |
| **Isolation Forest**             | Tree-based isolation                            | Local density outliers                | Detects rare, abrupt or localized deviations                    |
| **OMR (Overall Model Residual)** | PLS / PCA / Ridge reconstruction                | Cross-sensor functional relationships | Detects broken coupling among process variables                 |
| **CUSUM / Drift Monitor**        | Sequential residual tracking                    | Slow trend evolution                  | Detects gradual degradation, fouling, efficiency loss           |

---

## 3. What Each Detector Identifies in Physical Terms

Below is a *fault-mapping layer* — how each head translates to physical conditions commonly observed in rotating and process equipment.

### 3.1 AR1 – **Dynamic Instability & Control Oscillation**

| Fault Type                 | Example Physical Behavior                             |
| -------------------------- | ----------------------------------------------------- |
| PID tuning error           | Pressure, temperature, or flow oscillating cyclically |
| Sensor noise or chattering | Sudden erratic spikes uncorrelated to process load    |
| Mechanical looseness       | Vibration amplitude oscillations, alternating sign    |
| Electrical instability     | Current or speed jitter, fluctuating torque feedback  |

**Interpretation:**
High AR1 z-score means **temporal predictability broke** — the signal no longer follows its own historical inertia.

---

### 3.2 PCA (SPE/T²) – **Shape and Variance Anomalies**

| Fault Type                   | Example Physical Behavior                   |
| ---------------------------- | ------------------------------------------- |
| Process fluctuation increase | Flow, pressure, or temp spread widening     |
| Nonlinearity introduction    | Process deviating from established manifold |
| Regime overlap               | System operating between two steady states  |
| Data saturation              | Sensor range limiting → compressed variance |

**Interpretation:**
High PCA-SPE or T² indicates the **overall “cloud” of normal operation deformed** — e.g., more scattered, tilted, or squashed.
Usually an *early symptom* of control loss, valve sticking, or feed variability.

---

### 3.3 Mahalanobis Distance – **Global Shift or Scaling**

| Fault Type               | Example Physical Behavior                      |
| ------------------------ | ---------------------------------------------- |
| Uniform temperature rise | All temperatures increase proportionally       |
| Common-mode bias         | Pressure and flow both rise together by offset |
| Calibration shift        | Sensor zero drift or scaling error             |
| Step change in baseline  | Operation under a new global condition         |

**Interpretation:**
High Mahalanobis z means the **entire operating point shifted**, but internal relationships remain mostly consistent.
Useful for catching *load changes, bias drifts, or setpoint moves*.

---

### 3.4 GMM – **Regime Recognition / Novel Condition**

| Fault Type                    | Example Physical Behavior                               |
| ----------------------------- | ------------------------------------------------------- |
| Startup vs steady operation   | Transitions between regimes not seen before             |
| Ambient or seasonal variation | Conditions outside historical distribution              |
| Process reconfiguration       | Valve sequencing changed, new product grade             |
| Major load change             | Flow, current, and temperature cluster into new pattern |

**Interpretation:**
Low GMM probability indicates **the system entered a new statistical regime**.
Not always a fault — often an *operating-mode change*.
Helps isolate “new but healthy” vs “new and abnormal” contexts.

---

### 3.5 Isolation Forest – **Localized, Sparse Outliers**

| Fault Type           | Example Physical Behavior          |
| -------------------- | ---------------------------------- |
| Momentary spikes     | Sensor dropout or EMI noise        |
| One-time pulse       | Transient process upset or blowoff |
| Sudden discontinuity | Step fault (valve jam, trip event) |
| Sensor saturation    | Out-of-range single-sensor spike   |

**Interpretation:**
High IForest score means **“this sample stands alone”** — rare behavior not repeated nearby in time.
Acts as a *spike detector* or *transient marker* complementing drift detectors.

---

### 3.6 OMR – **Cross-Sensor Coupling Breaks**

| Fault Type         | Example Physical Behavior                                          |
| ------------------ | ------------------------------------------------------------------ |
| Process decoupling | Flow and pressure no longer move in sync                           |
| Efficiency loss    | Temperature and load diverge (e.g., fouling, heat loss)            |
| Sensor drift       | One variable stops tracking others though both change slowly       |
| Partial failure    | Vibration increases while power constant, or torque–speed mismatch |
| Valve sticking     | Pressure–flow response slope changes abnormally                    |

**Interpretation:**
High OMR score means **the physical relationships between variables are no longer consistent with healthy physics**.
It’s the detector that senses **“behavioral inconsistency,” not just appearance change.**

---

### 3.7 CUSUM / Drift Detector – **Slow Degradation**

| Fault Type                 | Example Physical Behavior                        |
| -------------------------- | ------------------------------------------------ |
| Bearing wear               | Slow rising vibration baseline                   |
| Heat exchanger fouling     | Gradual temp differential increase               |
| Filter choking             | Pressure drop creep                              |
| Sensor bias drift          | Output offset growing over time                  |
| Process loss of efficiency | Gradual divergence of expected vs achieved value |

**Interpretation:**
Positive drift slope = **slow degradation**, often before any alarm is triggered.
CUSUM provides early-warning of persistent bias trends.

---

## 4. Fusion – The Consensus Layer

### 4.1 Why We Fuse

Fusion builds a **stable consensus** of these detectors instead of replacing them.
It smooths noise, balances strengths, and adapts automatically.

* If *all* rise → clear fault.
* If *only one or two* rise → partial degradation.
* If they conflict → investigate whether a sensor or regime shift is occurring.

Fusion z-score = *“how confident we are something truly changed.”*

### 4.2 What Head Contributions Mean

| Dominant Head         | Interpretation         | Typical Fault Signature                 |
| --------------------- | ---------------------- | --------------------------------------- |
| **AR1**               | Dynamic instability    | Fast oscillations, control loop hunting |
| **PCA / Mahalanobis** | Statistical distortion | Process spread or baseline shift        |
| **GMM / IForest**     | Novel regime           | Startup, untrained operating zone       |
| **OMR**               | Broken coupling        | Process decoupling, loss of efficiency  |
| **CUSUM / Drift**     | Slow degradation       | Wear, fouling, or drift buildup         |

---

## 5. Reading ACM Outputs – The Human Hierarchy

```
Fused Health (Is it abnormal?)
   ↓
Dominant Head(s) (What kind of deviation?)
   ↓
Top Sensors (Where is it happening?)
```

| Level                    | Role           | Interpretation                                                     |
| ------------------------ | -------------- | ------------------------------------------------------------------ |
| **Fusion Score / Zone**  | Overall health | Red = consensus fault, Yellow = watch, Green = healthy             |
| **Head Mix / Type**      | Fault nature   | OMR↑ = physical decoupling; PCA↑ = variability; AR1↑ = instability |
| **Sensor Contributions** | Fault source   | OMR residuals show responsible sensors                             |
| **Regime Context**       | Operating mode | Helps confirm process state                                        |
| **Drift Metrics**        | Persistence    | Determines trend vs transient                                      |

---

## 6. Physical Example: Gas Turbine Case

| Observation               | Detector Reaction         | Interpretation                        |
| ------------------------- | ------------------------- | ------------------------------------- |
| Sudden speed oscillation  | AR1 ↑, PCA ↑              | Control loop oscillation              |
| Gradual exhaust temp rise | Drift ↑, OMR ↑            | Efficiency degradation, fouling       |
| Flow-pressure decoupling  | OMR ↑↑, PCA normal        | Broken thermodynamic coupling         |
| Global temperature shift  | Mahalanobis ↑, OMR stable | Load or ambient condition change      |
| Noise spike in vibration  | IForest ↑ only            | Transient event, likely not sustained |
| Operation in startup mode | GMM ↓ probability         | Entered new regime; re-learn required |

---

## 7. Operator-Facing Summary

| Display                  | Shows                           | Takeaway                    |
| ------------------------ | ------------------------------- | --------------------------- |
| **Health Gauge**         | Fused health (Green/Yellow/Red) | Is asset normal?            |
| **Deviation Type Chart** | Head contributions              | What kind of deviation?     |
| **Sensor Hotspot Map**   | OMR top contributors            | Which sensors or subsystem? |
| **Regime Tracker**       | Operating mode context          | Was it steady or transient? |
| **Drift Trend Graph**    | Slow degradation path           | Is this trending worse?     |

---

## 8. Why Multiple Heads Are Still Needed

Even if several detectors correlate on healthy data, they **diverge under fault conditions** — and that divergence *defines* the fault character.

| Healthy State | All heads ≈ correlated (0.9+) → stable ensemble |
| Fault State | Different heads spike differently → diagnostic fingerprint |

This fingerprint enables automatic **fault typing** and better RCA (Root Cause Analysis).

---

## 9. Summary Takeaways

1. **ACM doesn’t just detect change — it categorizes it.**
2. **Fusion = confidence; head contributions = explanation.**
3. **OMR = relational truth detector** — tells whether physics between signals still holds.
4. **Operators see one score**, but **engineers can unpack the anatomy of deviation.**
5. The combination of **distributional, temporal, relational, and drift-based views** allows ACM to detect and classify almost every kind of degradation seen in rotating and process equipment.

---

**End of Document**

# RUL Backbnone

## 🔩 1. Conceptual Framing — RUL Without Failure Labels

Because you don’t have labelled failure timestamps, the system must **infer degradation indirectly** using trends in health indicators.
RUL here will therefore be **relative** (how much “useful state” remains compared to normal) rather than absolute time-to-failure.

We’ll estimate this using a combination of:

1. **Health Index trajectory analysis** (unsupervised)
2. **Trend extrapolation / probabilistic decay**
3. **Survival modelling under uncertainty**
4. **Cross-detector fusion for confidence weighting**

---

## ⚙️ 2. Analytical Backbone for RUL Estimation

| Layer                             | Role                                                     | Algorithm / Model Candidates                                                       | Notes                                                     |
| --------------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **1. Health Score Generator**     | Aggregate multivariate sensors → single `HealthIndex(t)` | PCA-T² / SPE, Mahalanobis Distance, IsolationForest score, AE reconstruction error | Already implemented in ACM — reuse `ACM_Scores_Wide`      |
| **2. Degradation Modelling**      | Fit curve to historical health deterioration             | Exponential decay, Weibull, piecewise linear, Gaussian Process Regression          | Auto-select based on best fit (AIC/BIC)                   |
| **3. RUL Extrapolation**          | Predict time until HealthIndex crosses alarm threshold   | Time-to-threshold prediction                                                       | Threshold dynamically learned via quantile drift analysis |
| **4. Uncertainty Quantification** | Estimate confidence bounds for RUL                       | Monte-Carlo dropout, Bayesian GPR, bootstrapped regressors                         | Needed to avoid false alarms                              |
| **5. Adaptive Update Loop**       | Re-fit when health regime changes                        | Drift detector triggers retrain                                                    | Uses existing ACM drift signals                           |

---

## 🧠 3. Key Mathematical Formulations

1. **Normalized Health Index (HI):**
   [
   HI_t = 1 - \frac{score_t - score_{min}}{score_{max} - score_{min}}
   ]
   where `score_t` is any anomaly or distance metric (lower = healthy).

2. **Exponential degradation model:**
   [
   HI_t = \exp(-\lambda t)
   \Rightarrow RUL = \frac{1}{\lambda}\ln\frac{HI_t}{HI_{threshold}}
   ]
   where `λ` is estimated from recent slope.

3. **Piecewise linear regression:**
   Use `segmented regression` to find slow vs fast degradation phases.

4. **Probabilistic RUL (Bayesian):**
   Maintain posterior over λ and compute distribution of RUL.

---

## 🔬 4. Feature Engineering Specifics

- **Health index smoothing:** Apply robust EWMA or LOWESS on fused z-score prior to normalization to suppress detector noise while preserving trend slope.
- **Derivative features:** Track first/second derivative of the health index; sign changes highlight acceleration of degradation and trigger model re-fit.
- **Stability guardrails:** Require minimum variance and monotonic decline over configurable lookback (e.g., Pearson r < -0.4) before surfacing numeric RUL to avoid false alarms during steady-state.
- **Regime-aware baselining:** Normalize per regime so transitions between operating modes do not masquerade as degradation; fall back to global baseline when regime confidence < 0.6.

---

## 📐 5. Model Selection Heuristics

1. **Candidate models:** {Exponential, Weibull, Piecewise Linear (2 segments), Gaussian Process Regression}.
2. **Fit windows:** Evaluate on sliding windows (24h, 7d, configurable) and score with AIC/BIC + out-of-window residual checks.
3. **Plateau detection:** If the best model explains <40% variance or residuals are white-noise, emit qualitative state (`"Stable"`, `"Warming"`) instead of numeric RUL.
4. **Ensemble fusion:** Weight model forecasts by inverse MAE on validation window; expose fused RUL + spread.

---

## 🧪 6. Evaluation & Monitoring

- **Backtesting:** Replay historical episodes, compute error between predicted RUL and observed alarm onset; track precision at horizons (24h, 72h) and early-warning lead time.
- **Calibration diagnostics:** Reliability diagram for probability that failure occurs before predicted RUL; maintain rolling Brier score.
- **Alert governance:** Require consistent degradation signal across two successive windows before emitting severity ≥ Alert to operators.
- **Drift interplay:** When drift detector fires or clips change, flag RUL output as `retrain_pending` and suppress until models refresh.

---

## 🧩 4. Implementation Plan (Inside ACM)

| Step | Module               | Implementation                                             | Output                                                               |
| ---- | -------------------- | ---------------------------------------------------------- | -------------------------------------------------------------------- |
| 1    | `rul_estimator.py`   | New module reading from `ACM_Scores_Wide`                  | Adds `ACM_RUL_TS` table                                              |
| 2    | Health normalization | Use fused anomaly score → normalize 0–1                    | `HealthIndex`                                                        |
| 3    | Model fitting        | Rolling window (last 24h/7d) fit to degradation model      | `λ`, `fit_quality`, `predicted_HI`                                   |
| 4    | Forecast             | Project `HI(t)` forward until `HI_th = 0.3` (configurable) | `PredictedRUL_Hours`                                                 |
| 5    | Fusion               | Combine multiple detectors’ RUL via weighted median        | `FusedRUL`                                                           |
| 6    | Output               | Save to SQL & charts                                       | `ACM_RUL_TS` (time series), `ACM_RUL_Summary` (latest RUL per asset) |

---

## 📊 5. Example Outputs

**ACM_RUL_TS Table:**

| Timestamp (UTC)  | EquipID | HealthIndex | RUL_Hours | LowerBound | UpperBound | Method      | RunID        |
| ---------------- | ------- | ----------- | --------- | ---------- | ---------- | ----------- | ------------ |
| 2025-11-03 10:00 | 5396    | 0.87        | 240       | 190        | 310        | exponential | a2230467-... |
| 2025-11-03 10:10 | 5396    | 0.85        | 226       | 180        | 295        | exponential | a2230467-... |

**ACM_RUL_Summary Table:**

| EquipID | RunID        | RUL_Hours | Confidence | Method      | LastUpdate       |
| ------- | ------------ | --------- | ---------- | ----------- | ---------------- |
| 5396    | a2230467-... | 226       | 0.88       | exponential | 2025-11-03 10:10 |

---

## 🔍 6. Charts for HTML UI

1. **Health Index vs Time** (smoothed)
2. **Fitted degradation curve + forecast band**
3. **RUL trajectory (hours left vs time)**
4. **Confidence interval gauge (0–1)**
5. **Drift/Regime markers overlayed**

---

## 🔁 7. Integration Hooks

- **Config additions:**
   - `rul.enabled`: toggles the estimator.
   - `rul.windows`: list of window lengths for rolling fits.
   - `rul.threshold`: health index cut-off that defines "end-of-life".
   - `rul.min_confidence`: suppress output when uncertainty > threshold.
- **Pipeline inserts:** After fusion outputs are generated, pass fused score & drift metrics to `rul_estimator` prior to OutputManager write.
- **Output contracts:**
   - `tables/rul_timeseries.csv` with columns `[timestamp, health_index, rul_hours, lower, upper, method, confidence]`.
   - `tables/rul_summary.csv` keyed by equipment/run with latest RUL.
   - Optional SQL tables `ACM_RUL_TS`, `ACM_RUL_Summary` for service mode.
- **Monitoring artifacts:** Append RUL-specific notes to `run_metadata.json` and include in analytics tables (`rul_status.csv`).

---

## 🔄 8. Model Updating Strategy

- **Trigger**: When drift detected or new run starts.
- **Windowed fitting**: Fit model on last *N* hours of health data.
- **Decay reset**: If regime change → reset RUL baseline.
- **Learning mode**: If equipment never degraded yet, return `"Stable"` with no numeric RUL.

---

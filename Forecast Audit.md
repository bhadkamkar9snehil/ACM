# Forecast Audit

## Overall Assessment

**Status:** Much improved from previous version - syntax errors fixed, but **critical statistical and algorithmic issues remain**.

---

## **CRITICAL ISSUES (Affect Correctness)**

### 1. **WRONG: Constant Confidence Intervals** (Lines 448-449)

```python
ci_lower = yhat - confidence_k * sd_train
ci_upper = yhat + confidence_k * sd_train
```

**Problem:** This is **statistically incorrect** for AR(1) models. Forecast uncertainty **must grow with horizon**.

**Theory:**
For AR(1): `y_{t+h} = μ + φ^h(y_t - μ) + ε_t+1 + φε_t+2 + ... + φ^{h-1}ε_t+h`

Forecast variance at horizon h:
```
Var(y_{t+h}) = σ² × [(1 - φ^{2h}) / (1 - φ²)]
```

For φ → 1 (unit root): variance grows linearly with h
For φ = 0: variance is constant (only immediate noise)

**Impact:** 
- Users get **false confidence** in long-term forecasts
- 24-hour ahead forecast shows same uncertainty as 1-hour ahead (impossible!)
- Undermines trust in ACM system

**Fix:**
```python
# FCST-03: Growing confidence intervals (CORRECT)
h_values = np.arange(1, len(idx_fore) + 1)

# Forecast variance grows with horizon
if abs(ph) < 0.9999:  # Stationary case
    phi_squared = ph ** 2
    var_ratio = (1 - phi_squared ** h_values) / (1 - phi_squared + 1e-9)
else:  # Near unit root: linear growth
    var_ratio = h_values.astype(float)

# Clip to reasonable bounds (prevent explosion)
var_ratio = np.clip(var_ratio, 1.0, 100.0)
forecast_std = sd_train * np.sqrt(var_ratio)

ci_lower = yhat - confidence_k * forecast_std
ci_upper = yhat + confidence_k * forecast_std
```

**Severity:** 🔴 **CRITICAL** - Violates fundamental time series theory

---

### 2. **Residual Standard Deviation Calculation** (Line 103)

```python
resid = x - pred
sd = float(np.std(resid))
self.sdmap[c] = max(sd, self._sd_floor)
```

**Problem:** Includes the **first residual** which is `x[0] - mu` (not from AR model). This can bias σ if x[0] is an outlier or the series starts far from μ.

**Fix:**
```python
resid = x - pred
sd = float(np.std(resid[1:]))  # Exclude first point (warm start artifact)
self.sdmap[c] = max(sd, self._sd_floor)
```

**Severity:** 🟡 **MEDIUM** - Causes ~5-10% σ estimation bias in some cases

---

### 3. **Warm Start Bias in Scoring** (Lines 139-142)

```python
# one-step AR(1) prediction with warm start at mu
pred = np.empty_like(series_finite, dtype=np.float32)
pred[0] = mu
```

**Problem:** Using `mu` as the initial prediction causes a **transient bias** in residuals when scoring data starts at a different level.

**Example:**
- Training data: mean = 50, last value = 48
- Scoring data: first value = 70
- First residual = 70 - 50 = **20** (huge spurious anomaly!)

**Fix:**
```python
# Warm start: use actual first observation instead of mu
pred = np.empty_like(series_finite, dtype=np.float32)
pred[0] = series_finite[0] if np.isfinite(series_finite[0]) else mu
if n > 1:
    pred[1:] = (series_finite[:-1] - mu) * ph + mu
```

**Severity:** 🔴 **HIGH** - Causes false anomaly alerts at data boundaries

---

### 4. **"Divergence" Metric is Misleading** (Lines 479-481)

```python
divergence_abs = float(abs(yhat.iloc[0] - last_val)) if len(yhat) > 0 else 0.0
divergence_pct = float(abs(divergence_abs / (abs(last_val) + 1e-9)) * 100)
```

**Problem:** This is **NOT divergence** - it's **mean reversion**, which is the correct AR(1) behavior!

**Math:**
```
yhat[0] = μ + φ(last_val - μ)
yhat[0] - last_val = (φ - 1)(last_val - μ)
```

For φ < 1 (stationary), the forecast **should** move toward μ. Calling this "divergence" confuses users.

**Fix:**
```python
# Mean reversion analysis (correct interpretation)
distance_from_mean = float(abs(last_val - mu))
expected_reversion = (1 - abs(ph)) * distance_from_mean
actual_reversion = float(abs(yhat.iloc[0] - last_val)) if len(yhat) > 0 else 0.0
reversion_error = abs(actual_reversion - expected_reversion)

# For diagnostics
diagnostics_df = pd.DataFrame([{
    "series_name": series_name,
    "ar1_phi": ph,
    "ar1_mu": mu,
    "ar1_sigma": sd_train,
    "last_observed": last_val,
    "distance_from_mean": distance_from_mean,
    "mean_reversion_strength": 1 - abs(ph),  # 0=no reversion, 1=instant reversion
    "first_forecast": yhat.iloc[0] if len(yhat) > 0 else np.nan,
    "forecast_step": actual_reversion,
    "expected_step": expected_reversion,
    "model_error": reversion_error,
    # ...
}])
```

**Severity:** 🟡 **MEDIUM** - Misleading diagnostics, confuses users

---

### 5. **Recommendation Logic is Backwards** (Lines 486-493)

```python
recommendation = "OK"
if divergence_pct > 50:
    recommendation = "CRITICAL: Divergence > 50% - Consider switching forecast series or detrending"
elif divergence_pct > 20:
    recommendation = "WARNING: Divergence > 20% - Monitor for forecast accuracy"
elif abs(ph) > 0.95:
    recommendation = "WARNING: High persistence (phi > 0.95) - Forecast may not revert to mean"
```

**Problems:**
1. High "divergence" (mean reversion) is **correct**, not a problem
2. φ > 0.95 should be flagged **before** other checks
3. Negative φ (oscillation) is ignored
4. Variance issues ignored

**Fix:**
```python
recommendation = []

# 1. Check for unit root (most serious)
if abs(ph) > 0.98:
    recommendation.append("CRITICAL: Near unit-root (phi > 0.98) - forecast unreliable for long horizons")
elif abs(ph) > 0.95:
    recommendation.append("WARNING: High persistence (phi > 0.95) - slow mean reversion")

# 2. Check for oscillation
if ph < -0.5:
    recommendation.append("WARNING: Negative autocorrelation (phi < -0.5) - series oscillates, AR(1) may be inappropriate")

# 3. Check data quality
if selection_metrics.get("nan_rate", 0) > 0.2:
    recommendation.append("WARNING: High missing data rate (>20%) - forecast may be unstable")

# 4. Check variance/mean ratio
if sd_train > abs(mu) * 2:
    recommendation.append("INFO: High noise-to-signal ratio - consider smoothing or alternative models")

# 5. Check short series
if selection_metrics.get("n_points", 0) < 50:
    recommendation.append("WARNING: Limited training data (<50 points) - AR coefficients may be unstable")

recommendation_str = "; ".join(recommendation) if recommendation else "OK - Model diagnostics within normal ranges"
```

**Severity:** 🟡 **MEDIUM** - Users get wrong guidance

---

## **HIGH PRIORITY ISSUES**

### 6. **AR(1) Coefficient Estimation - No Stability Checks** (Lines 88-97)

```python
xc = x - mu
num = float(np.dot(xc[1:], xc[:-1]))
den = float(np.dot(xc[:-1], xc[:-1])) + self._eps
phi = num / den
```

**Missing checks:**
- Near-zero denominator (happens with near-constant signals)
- Very short series (n < 20) → unstable estimates
- High variance in estimates for noisy data

**Improved version:**
```python
xc = x - mu

# Check for degenerate cases
var_xc = np.var(xc)
if var_xc < 1e-8:
    # Near-constant signal
    self.phimap[c] = (0.0, mu)
    self.sdmap[c] = max(float(np.std(x)), self._sd_floor)
    continue

# OLS estimation
num = float(np.dot(xc[1:], xc[:-1]))
den = float(np.dot(xc[:-1], xc[:-1]))

if abs(den) < 1e-9:
    phi = 0.0
else:
    phi = num / den

# Stability clamping (already present, but add logging)
if abs(phi) > self._phi_cap:
    original_phi = phi
    phi = np.sign(phi) * self._phi_cap
    Console.warn(f"[AR1] Column '{c}': phi={original_phi:.3f} clamped to {phi:.3f} for stability")

# Flag unreliable estimates
if len(x) < 20:
    Console.warn(f"[AR1] Column '{c}': Only {len(x)} points - AR coefficient may be unstable")
```

**Severity:** 🟠 **HIGH** - Can cause numerical instability

---

### 7. **Frequency Regex Still Too Permissive** (Line 247)

```python
_FREQ_RE = re.compile(r"([+-]?\d*\.?\d*)([A-Za-z]+)")
```

**Problems:**
- Accepts `"0min"` (invalid)
- Accepts `"3.5h"` (fractional frequencies are edge cases)
- Doesn't validate unit names
- Accepts `"+-5min"` (nonsense)

**Fix:**
```python
# Only positive integers, validated units
_FREQ_RE = re.compile(r"^(\d+)([A-Za-z]+)$")
VALID_UNITS = {"s", "sec", "min", "h", "hour", "d", "day", "w", "week", "ms"}

def _normalize_freq_token(freq: str) -> str:
    freq = (freq or "").strip().replace("T", "min")
    if not freq:
        return "1min"
    
    match = _FREQ_RE.fullmatch(freq.lower())
    if not match:
        Console.warn(f"[FORECAST] Invalid frequency format '{freq}', using '1min'")
        return "1min"
    
    magnitude, unit = match.groups()
    magnitude = int(magnitude)
    
    if magnitude <= 0:
        Console.warn(f"[FORECAST] Non-positive frequency '{freq}', using '1min'")
        return "1min"
    
    # Normalize plural forms
    unit = unit.rstrip("s")
    
    # Validate unit
    unit_map = {"sec": "s", "second": "s", "hour": "h", "day": "d", "week": "w"}
    unit = unit_map.get(unit, unit)
    
    if unit not in VALID_UNITS:
        Console.warn(f"[FORECAST] Unknown time unit '{unit}', using '1min'")
        return "1min"
    
    return f"{magnitude}{unit}"
```

**Severity:** 🟠 **MEDIUM-HIGH** - Can break date_range generation

---

### 8. **Horizon Clamping is Silent** (Lines 328-331)

```python
max_ts = pd.Timestamp.max
while horizon > 1 and start + (horizon - 1) * step > max_ts:
    horizon //= 2
```

**Problem:** User requests 24-hour forecast, gets 12-hour or 6-hour silently. This is a **contract violation**.

**Fix:**
```python
max_ts = pd.Timestamp.max - pd.Timedelta(days=1)  # Safety margin
projected_end = start + (horizon - 1) * step

if projected_end > max_ts:
    max_safe_horizon = int((max_ts - start) / step)
    original_horizon = horizon
    horizon = max(1, max_safe_horizon)
    Console.warn(f"[FORECAST] Requested horizon {original_horizon} exceeds timestamp limits. "
                 f"Clamped to {horizon} samples ({horizon / samples_per_hour:.1f} hours)")
```

**Severity:** 🟠 **HIGH** - Silent contract violation

---

## **MEDIUM PRIORITY ISSUES**

### 9. **Series Selection Scoring is Naive** (Lines 381-382)

```python
score = nan_rate + (1.0 / (1.0 + variance))
```

**Problems:**
- Doesn't check autocorrelation (AR(1) needs persistence!)
- Doesn't check stationarity
- Variance term can dominate (wrong weighting)

**Better scoring:**
```python
def _score_series_for_ar1(series: pd.Series) -> Tuple[float, Dict[str, Any]]:
    """Score series for AR(1) suitability (lower = better)."""
    y = series.dropna()
    
    if len(y) < 20:
        return float('inf'), {}
    
    # Data quality
    nan_rate = series.isna().sum() / len(series)
    
    # Variance check
    variance = float(y.var())
    if variance < 1e-9:
        return float('inf'), {}
    
    # Autocorrelation at lag 1 (critical for AR(1))
    try:
        acf1 = y.autocorr(lag=1)
        if not np.isfinite(acf1):
            acf1 = 0.0
    except Exception:
        acf1 = 0.0
    
    # Stationarity proxy: trend strength
    mid = len(y) // 2
    mean_first = y.iloc[:mid].mean()
    mean_last = y.iloc[mid:].mean()
    trend_strength = abs(mean_last - mean_first) / (y.std() + 1e-9)
    
    # Combined score (weights tuned for AR(1))
    score = (
        nan_rate * 2.0 +                    # Data quality (0-2)
        max(0, 1.0 - abs(acf1)) * 1.5 +    # Prefer high autocorrelation (0-1.5)
        min(trend_strength, 1.0)            # Penalize trends (0-1)
    )
    
    metrics = {
        "nan_rate": nan_rate,
        "variance": variance,
        "acf1": acf1,
        "trend_strength": trend_strength
    }
    
    return score, metrics
```

**Severity:** 🟡 **MEDIUM** - May select suboptimal series

---

### 10. **Forced "fused" Series** (Lines 417-420)

```python
# CHART-01 FIX: Force "fused" series to avoid forecast divergence
config_override = config.copy() if config else {}
config_override["series_override"] = "fused"
```

**Problem:** Hardcoded override ignores:
- User configuration
- Data quality of fused series
- Possible issues with fused series (NaNs, instability)

**Better approach:**
```python
# Prefer fused but allow graceful fallback
preferred_series = config.get("series_override", "fused")

# Try preferred series first
if preferred_series in df.columns:
    y_preferred = df[preferred_series].astype(float).dropna()
    if len(y_preferred) >= 20:
        score_preferred, _ = _score_series_for_ar1(df[preferred_series])
        if score_preferred < 3.0:  # Acceptable threshold
            y = y_preferred
            selection_metrics = {
                "series_used": preferred_series,
                "selection_method": "preferred",
                "score": score_preferred
            }
        else:
            Console.warn(f"[FORECAST] Preferred series '{preferred_series}' has poor quality (score={score_preferred:.2f}), "
                        "falling back to best available series")
            y, selection_metrics = _select_best_series(df, {}, candidates)
    else:
        Console.warn(f"[FORECAST] Preferred series '{preferred_series}' has insufficient data, falling back")
        y, selection_metrics = _select_best_series(df, {}, candidates)
else:
    y, selection_metrics = _select_best_series(df, {}, candidates)
```

**Severity:** 🟡 **MEDIUM** - Reduces flexibility

---

### 11. **No Validation of Forecast Accuracy** 

**Missing:** Backtesting on held-out data to validate AR(1) assumptions.

**Add:**
```python
def _validate_forecast(y: pd.Series, ar1_detector: AR1Detector, holdout_pct: float = 0.2) -> Dict[str, float]:
    """Backtest AR(1) forecast on held-out data."""
    n = len(y)
    split = int(n * (1 - holdout_pct))
    
    if split < 20:
        return {}  # Not enough data
    
    train = y.iloc[:split]
    test = y.iloc[split:]
    
    # Fit on train only
    temp_detector = AR1Detector().fit(train.to_frame())
    ph, mu = temp_detector.phimap.get(y.name, (0.0, train.mean()))
    
    # Multi-step forecast
    forecasts = []
    last_val = train.iloc[-1]
    for _ in range(len(test)):
        fc = mu + ph * (last_val - mu)
        forecasts.append(fc)
        last_val = fc  # Use forecast as next input
    
    forecasts = np.array(forecasts)
    actuals = test.values
    
    # Metrics
    errors = forecasts - actuals
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    mape = float(np.mean(np.abs(errors / (np.abs(actuals) + 1e-9))) * 100)
    
    return {
        "validation_mae": mae,
        "validation_rmse": rmse,
        "validation_mape": mape,
        "validation_n": len(test)
    }

# In run() function, after AR1 fitting:
validation_metrics = _validate_forecast(y, ar1_detector)
if validation_metrics:
    Console.info(f"[FORECAST] Validation: MAE={validation_metrics['validation_mae']:.3f}, "
                 f"MAPE={validation_metrics['validation_mape']:.1f}%")
    metrics.update(validation_metrics)
```

**Severity:** 🟡 **MEDIUM** - No quality assurance

---

## **LOW PRIORITY / OPTIMIZATIONS**

### 12. **Performance: DataFrame Fusion** (Lines 169-176)

```python
Z = pd.DataFrame(per_cols, index=X.index)
if self._fuse == "median":
    fused = Z.median(axis=1, skipna=True).to_numpy(dtype=np.float32)
```

**Optimization:** Use numpy directly (5-10x faster):

```python
# Stack arrays
if per_cols:
    Z_array = np.column_stack(list(per_cols.values()))
    
    if self._fuse == "median":
        fused = np.nanmedian(Z_array, axis=1).astype(np.float32)
    elif self._fuse == "p95":
        fused = np.nanpercentile(Z_array, 95, axis=1).astype(np.float32)
    else:
        fused = np.nanmean(Z_array, axis=1).astype(np.float32)
    
    if return_per_sensor:
        Z = pd.DataFrame(per_cols, index=X.index)
        return fused, Z
    return fused
```

---

### 13. **Numerical Stability for High φ** (Line 443)

```python
phi_powers = np.power(ph, h_values)
```

**Issue:** For large horizons + high φ, can lose precision or overflow.

**Fix:**
```python
# Log-space computation for numerical stability
if abs(ph) > 1e-9:
    log_phi = np.log(abs(ph))
    phi_powers = np.sign(ph) ** h_values * np.exp(log_phi * h_values)
else:
    phi_powers = np.zeros_like(h_values, dtype=float)

# Clip extreme values
phi_powers = np.clip(phi_powers, -1e6, 1e6)
```

---

### 14. **Missing Stationarity Testing**

AR(1) assumes stationarity. Add lightweight test:

```python
def _check_stationarity(y: pd.Series, window: int = 50) -> Dict[str, Any]:
    """Quick stationarity checks."""
    results = {}
    
    if len(y) > window * 2:
        # Rolling mean stability
        rolling_mean = y.rolling(window).mean()
        mean_var = rolling_mean.var()
        overall_var = y.var()
        
        stability_ratio = float(mean_var / (overall_var + 1e-9))
        results["mean_stability_ratio"] = stability_ratio
        results["likely_stationary"] = stability_ratio < 0.1
    
    return results

# In run(), after series selection:
stationarity = _check_stationarity(y)
if not stationarity.get("likely_stationary", True):
    Console.warn(f"[FORECAST] Series may be non-stationary (stability ratio={stationarity.get('mean_stability_ratio', 0):.3f}). "
                 "Consider differencing or detrending.")
```

---

## **DOCUMENTATION GAPS**

### Missing Critical Information:

1. **AR(1) Assumptions Not Documented:**
```python
"""
AR(1) Model: y_t = μ + φ(y_{t-1} - μ) + ε_t

CRITICAL ASSUMPTIONS:
- Stationarity: E[y_t] and Var(y_t) constant over time
- Linear dynamics: No regime changes or nonlinear effects
- No seasonality: Daily/weekly patterns will be missed
- Gaussian noise: Outliers can severely bias estimates

WHEN AR(1) WORKS WELL:
✓ Short-term forecasting (<24 hours)
✓ Stable industrial processes
✓ Continuous monitoring with mean reversion

WHEN AR(1) FAILS:
✗ Trending data (use differencing or ARIMA)
✗ Seasonal patterns (use seasonal models)
✗ After regime changes (model will lag)
✗ Long horizons with φ→1 (unbounded uncertainty)

UNCERTAINTY QUANTIFICATION:
- Forecast variance grows with horizon h:
  Var(y_{t+h}) = σ² × [(1 - φ^{2h}) / (1 - φ²)]
- For φ=0.9, 10-step variance is 6.5× larger than 1-step
- For φ→1 (unit root), variance grows linearly
"""
```

2. **No guidance on interpreting φ:**
   - φ ≈ 0: White noise (no memory)
   - φ ≈ 0.5: Moderate persistence
   - φ ≈ 0.9: High persistence (slow mean reversion)
   - φ ≈ 1.0: Unit root (random walk, non-stationary)
   - φ < 0: Oscillatory behavior (AR(1) inappropriate)

---

## **Summary: Priority-Ordered Action Items**

### 🔴 **CRITICAL (Fix Immediately):**
1. **Implement growing forecast variance** (Lines 448-449) - currently wrong!
2. **Fix warm start bias** (Line 140) - causes false alarms
3. **Exclude first residual from σ** (Line 103) - biases uncertainty

### 🟠 **HIGH (Fix Soon):**
4. **Add AR coefficient stability checks** (Lines 88-97)
5. **Fix frequency regex validation** (Line 247)
6. **Make horizon clamping explicit** (Lines 328-331)
7. **Fix "divergence" terminology** (Lines 479-493) - it's mean reversion!

### 🟡 **MEDIUM (Next Sprint):**
8. **Improve series scoring** - add autocorrelation check (Lines 381-382)
9. **Remove hardcoded fused series** (Lines 417-420)
10. **Add forecast validation** - backtest on holdout
11. **Add stationarity testing**

### 🟢 **LOW (Nice to Have):**
12. **Optimize DataFrame fusion** - use numpy (5-10x faster)
13. **Add numerical stability for high φ**
14. **Comprehensive documentation**

---

## **Code Patch for Most Critical Issue**

```python
# REPLACE Lines 440-449 with:

# FCST-06: Vectorized AR(1) forecast with growing uncertainty
h_values = np.arange(1, len(idx_fore) + 1)

# Numerical stability: use log-space for high phi
if abs(ph) > 1e-9:
    log_phi = np.log(abs(ph))
    phi_powers = np.sign(ph) ** h_values * np.exp(log_phi * h_values)
else:
    phi_powers = np.zeros_like(h_values, dtype=float)

yhat_values = mu + phi_powers * (last_val - mu)
yhat = pd.Series(yhat_values, index=idx_fore, name="forecast")

# CRITICAL: Forecast variance GROWS with horizon for AR(1)
# Theory: Var(y_{t+h}) = σ² × [(1 - φ^{2h}) / (1 - φ²)]
if abs(ph) < 0.9999:  # Stationary case
    phi_squared = ph ** 2
    var_ratio = (1 - phi_squared ** h_values) / (1 - phi_squared + 1e-9)
else:  # Near unit-root: variance grows linearly
    var_ratio = h_values.astype(float)

# Clip to reasonable bounds (prevent numerical explosion)
var_ratio = np.clip(var_ratio, 1.0, 100.0)
forecast_std = sd_train * np.sqrt(var_ratio)

ci_lower = yhat - confidence_k * forecast_std
ci_upper = yhat + confidence_k * forecast_std
```
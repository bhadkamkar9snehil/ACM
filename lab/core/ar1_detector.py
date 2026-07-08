"""
AR(1) Baseline Detector
=======================

Per-sensor AR(1) baseline model for residual scoring.
Extracted from core/forecasting.py for modularity.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple, Literal, Optional
import numpy as np
import pandas as pd
from core.observability import Console, Span

# Minimum samples required for AR(1) model coefficient estimation
MIN_AR1_SAMPLES = 3
# Minimum samples for stable forecast generation (used for warnings)
MIN_FORECAST_SAMPLES = 20

class AR1Detector:
    """
    Per-sensor AR(1) baseline model for residual scoring.
    
    Calculates AR(1) coefficients (phi) and mean (mu) for each sensor.
    Scores new data by calculating the absolute z-score of the residuals, 
    normalized by the TRAIN-time residual standard deviation.
    
    Usage:
        detector = AR1Detector(ar1_cfg={})
        detector.fit(train_df)
        scores = detector.score(test_df)
    """
    
    def __init__(self, ar1_cfg: Dict[str, Any] | None = None):
        """
        Initialize the AR(1) detector.
        
        Args:
            ar1_cfg: Configuration dict with optional keys:
                - eps (float): Numeric stability epsilon (default: 1e-9)
                - phi_cap (float): Max absolute phi value (default: 0.999)
                - sd_floor (float): Min std dev (default: 1e-6)
                - fuse (str): Fusion strategy "mean"|"median"|"p95" (default: "mean")
        """
        self.cfg = ar1_cfg or {}
        self._eps: float = float(self.cfg.get("eps", 1e-9))
        self._phi_cap: float = float(self.cfg.get("phi_cap", 0.999))
        self._sd_floor: float = float(self.cfg.get("sd_floor", 1e-6))
        # Residual scale floor as a fraction of the sensor's operational range.
        # An absolute 1e-6 floor let near-constant channels turn sub-LSB wiggles
        # into z ~ 1e6, pegging the fused score on healthy data.
        self._sd_floor_rel: float = float(self.cfg.get("sd_floor_rel", 0.01))
        # p95 across per-sensor z: a single faulty sensor among hundreds must
        # surface; the mean diluted it by 1/n_features.
        self._fuse: Literal["mean", "median", "p95"] = self.cfg.get("fuse", "p95")
        
        # Trained parameters per column: (phi, mu)
        self.phimap: Dict[str, Tuple[float, float]] = {}
        # TRAIN residual std per column for normalization
        self.sdmap: Dict[str, float] = {}
        self._is_fitted = False
    
    def fit(self, X: pd.DataFrame) -> "AR1Detector":
        """
        Fit the AR(1) model for each column in the training data.
        
        Args:
            X: Training feature matrix
            
        Returns:
            self for chaining
        """
        with Span("fit.ar1", n_samples=len(X), n_features=X.shape[1] if len(X) > 0 else 0):
            self.phimap = {}
            self.sdmap = {}
        
        if not isinstance(X, pd.DataFrame) or X.shape[0] == 0:
            self._is_fitted = True
            return self
        
        # Collect warnings to batch-report at end (avoid 100s of individual SQL inserts)
        near_constant_cols = []
        clamped_cols = []
        insufficient_cols = []
        overflow_cols = []  # Track columns with values that would overflow variance
        degenerate_cols = []  # Zero residual spread: excluded from scoring entirely
        
        # Maximum value threshold for safe variance computation in float64
        # Values > 1e150 will overflow when squared (1e300 > float64 max ~1.8e308)
        MAX_SAFE_VALUE = 1e150
        
        for c in X.columns:
            col = X[c].to_numpy(copy=False, dtype=np.float64)  # Use float64 for stability
            finite = np.isfinite(col)
            x = col[finite]
            
            # Detect and handle extreme values that would cause overflow
            max_abs_val = np.abs(x).max() if x.size > 0 else 0.0
            if max_abs_val > MAX_SAFE_VALUE:
                overflow_cols.append((c, max_abs_val))
                # Clip values to prevent overflow, but still fit the model
                x = np.clip(x, -MAX_SAFE_VALUE, MAX_SAFE_VALUE)
            
            # Floor for the residual scale, RELATIVE to the channel's
            # operational range (robust p2.5..p97.5 span). A fully constant
            # channel (zero range) carries no usable signal — excluded.
            col_range = float(np.subtract(*np.percentile(x, [97.5, 2.5]))) if x.size >= MIN_AR1_SAMPLES else 0.0
            sd_floor_c = max(self._sd_floor, self._sd_floor_rel * col_range)

            if x.size < MIN_AR1_SAMPLES:
                # ROBUST: Use median instead of mean for baseline
                mu = float(np.nanmedian(col)) if x.size else 0.0
                if not np.isfinite(mu):
                    mu = 0.0
                phi = 0.0
                resid = (x - mu) if x.size else np.array([0.0], dtype=np.float64)
                # ROBUST: Use MAD instead of std
                mad = float(np.median(np.abs(resid - np.median(resid)))) if resid.size > 0 else 0.0
                rng = float(np.max(x) - np.min(x)) if x.size else 0.0
                if mad <= 0 and rng <= 0:
                    degenerate_cols.append(c)
                    continue
                self.phimap[c] = (phi, mu)
                self.sdmap[c] = max(mad * 1.4826, max(self._sd_floor, self._sd_floor_rel * rng))
                continue
            
            # ROBUST: Use median instead of mean for baseline
            mu = float(np.nanmedian(x))
            if not np.isfinite(mu):
                mu = 0.0
            xc = x - mu
            var_xc = float(np.var(xc)) if xc.size else 0.0
            phi = 0.0
            
            if np.isfinite(var_xc) and var_xc >= 1e-8:
                num = float(np.dot(xc[1:], xc[:-1]))
                den = float(np.dot(xc[:-1], xc[:-1]))
                if abs(den) >= 1e-9:
                    phi = num / den
            else:
                near_constant_cols.append(c)
            
            if abs(phi) > self._phi_cap:
                original_phi = phi
                phi = float(np.sign(phi) * self._phi_cap)
                clamped_cols.append((c, original_phi, phi))
            
            if len(x) < MIN_FORECAST_SAMPLES:
                insufficient_cols.append((c, len(x)))

            # Compute TRAIN residuals & std for normalization during score()
            x_shift = np.empty_like(x, dtype=np.float64)
            x_shift[0] = mu
            x_shift[1:] = x[:-1]
            pred = (x_shift - mu) * phi + mu
            resid = x - pred
            resid_for_sd = resid[1:] if resid.size > 1 else resid
            # ROBUST: Use MAD instead of std for residual normalization
            # This makes AR1 scoring robust to training data containing faults
            mad = float(np.median(np.abs(resid_for_sd - np.median(resid_for_sd))))
            if mad <= 0 and col_range <= 0:
                # Fully constant channel: no operational range, no residual
                # spread — nothing to score. With the old absolute 1e-6 floor,
                # 3 such columns out of 891 produced median |z| ~1e6 on healthy
                # data and pegged the fused AR1 score at its clip.
                degenerate_cols.append(c)
                continue
            self.phimap[c] = (phi, mu)
            self.sdmap[c] = max(mad * 1.4826, sd_floor_c)
        
        # Emit batched warnings (single SQL insert instead of 100s)
        if overflow_cols:
            n = len(overflow_cols)
            sample = [(c, f"{v:.1e}") for c, v in overflow_cols[:3]]
            Console.warn(f"{n} columns with extreme values (clipped to +/-1e150): {sample}{'...' if n > 3 else ''}", component="AR1")
        if near_constant_cols:
            n = len(near_constant_cols)
            sample = near_constant_cols[:3]
            Console.warn(f"{n} near-constant columns (phi=0): {sample}{'...' if n > 3 else ''}", component="AR1")
        if clamped_cols:
            n = len(clamped_cols)
            Console.warn(f"{n} columns with phi clamped to +/-{self._phi_cap}", component="AR1")
        if insufficient_cols:
            n = len(insufficient_cols)
            Console.warn(f"{n} columns with <{MIN_FORECAST_SAMPLES} samples (unstable coefficients)", component="AR1")
        if degenerate_cols:
            n = len(degenerate_cols)
            Console.warn(f"{n} columns with zero residual spread excluded from AR1 scoring: {degenerate_cols[:3]}{'...' if n > 3 else ''}", component="AR1")
        
        self._is_fitted = True
        return self
    
    def score(self, X: pd.DataFrame, return_per_sensor: bool = False) -> np.ndarray | Tuple[np.ndarray, pd.DataFrame]:
        """
        Calculate absolute z-scores of residuals using TRAIN-time residual std.
        
        Args:
            X: Scoring feature matrix
            return_per_sensor: If True, also return DataFrame of per-sensor |z|
            
        Returns:
            Fused absolute z-scores (len == len(X))
            Optionally: (fused_scores, per_sensor_df) when return_per_sensor=True
        """
        with Span("score.ar1", n_samples=len(X), n_features=X.shape[1] if len(X) > 0 else 0):
            if not self._is_fitted:
                return np.zeros(len(X), dtype=np.float32)
        
        n = len(X)
        
        if n == 0 or X.shape[1] == 0:
            return (np.zeros(0, dtype=np.float32), pd.DataFrame(index=X.index)) if return_per_sensor else np.zeros(0, dtype=np.float32)
        
        # EARLY EXIT: If >80% of columns are near-constant, return zeros to prevent hang on pathological data
        near_constant_count = sum(1 for (phi, _) in self.phimap.values() if abs(phi) < 1e-6)
        total_count = len(self.phimap)
        if total_count > 0 and near_constant_count > total_count * 0.8:
            Console.warn(f"Early exit: {near_constant_count}/{total_count} columns near-constant (>{80}%) - returning zero scores to prevent hang", component="AR1")
            return (np.zeros(n, dtype=np.float32), pd.DataFrame(index=X.index)) if return_per_sensor else np.zeros(n, dtype=np.float32)
        
        # Vectorized AR(1) scoring
        # Filter columns that exist in phimap
        valid_cols = [c for c in X.columns if c in self.phimap]
        if not valid_cols:
            return (np.zeros(n, dtype=np.float32), pd.DataFrame(index=X.index)) if return_per_sensor else np.zeros(n, dtype=np.float32)
        
        # Check NaN fraction and filter high-NaN columns
        X_valid = X[valid_cols].to_numpy(dtype=np.float32, copy=True)
        nan_fractions = np.isnan(X_valid).sum(axis=0) / n
        good_cols_mask = nan_fractions <= 0.5
        
        # Warn about high-NaN columns
        high_nan_cols = [c for c, frac, good in zip(valid_cols, nan_fractions, good_cols_mask) if not good]
        if high_nan_cols:
            Console.warn(f"{len(high_nan_cols)} columns with >50% NaN skipped", component="AR1")
        
        valid_cols = [c for c, good in zip(valid_cols, good_cols_mask) if good]
        if not valid_cols:
            return (np.zeros(n, dtype=np.float32), pd.DataFrame(index=X.index)) if return_per_sensor else np.zeros(n, dtype=np.float32)
        
        # Extract phi, mu, sd for valid columns (vectorized lookup)
        phis = np.array([self.phimap[c][0] for c in valid_cols], dtype=np.float32)
        mus = np.array([self.phimap[c][1] for c in valid_cols], dtype=np.float32)
        sds = np.array([max(self.sdmap.get(c, self._sd_floor), self._sd_floor) for c in valid_cols], dtype=np.float32)
        
        # Get data matrix for valid columns
        X_mat = X[valid_cols].to_numpy(dtype=np.float32, copy=True)  # (n, n_cols)
        
        # Impute NaNs to mu (vectorized: broadcast mus across rows)
        nan_mask = np.isnan(X_mat)
        X_mat = np.where(nan_mask, mus, X_mat)
        
        # Vectorized AR(1) prediction: pred[t] = (x[t-1] - mu) * phi + mu
        pred = np.empty_like(X_mat, dtype=np.float32)
        pred[0, :] = X_mat[0, :]  # First row: use actual values
        if n > 1:
            # (x[:-1] - mu) * phi + mu, broadcasting over columns
            pred[1:, :] = (X_mat[:-1, :] - mus) * phis + mus
        
        # Compute residuals and z-scores
        resid = X[valid_cols].to_numpy(dtype=np.float32) - pred  # Keep NaNs from original
        z_matrix = np.abs(resid) / sds  # (n, n_cols), broadcasting sds over rows
        
        # Fuse across columns
        with np.errstate(all="ignore"):
            if self._fuse == "median":
                fused = np.nanmedian(z_matrix, axis=1).astype(np.float32)
            elif self._fuse == "p95":
                fused = np.nanpercentile(z_matrix, 95, axis=1).astype(np.float32)
            else:
                fused = np.nanmean(z_matrix, axis=1).astype(np.float32)
        
        if return_per_sensor:
            Z = pd.DataFrame(z_matrix, index=X.index, columns=valid_cols)
            return fused, Z
        return fused
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize detector state for persistence."""
        return {"phimap": self.phimap, "sdmap": self.sdmap, "cfg": self.cfg}
    
    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AR1Detector":
        """Deserialize detector state from dict."""
        inst = cls(payload.get("cfg"))
        inst.phimap = dict(payload.get("phimap", {}))
        inst.sdmap = dict(payload.get("sdmap", {}))
        # A restored detector with coefficients is fitted; without this flag
        # score() silently returns all-zero scores.
        inst._is_fitted = bool(inst.phimap)
        return inst

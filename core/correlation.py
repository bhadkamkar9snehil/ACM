# core/correlation.py
"""
Multivariate correlation-break detection module.

- PCASubspaceDetector: stable PCA monitoring that drops constant/non-finite
  columns, scales in float64, and returns finite SPE (Q) and Hotelling T².
"""
from __future__ import annotations

from typing import Any, Dict, Tuple, List, Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler
from sklearn.decomposition import PCA

try:
    from core.observability import Console, Span
except ImportError as e:
    # If logger import fails, something is seriously wrong - fail fast
    raise SystemExit(f"FATAL: Cannot import utils.logger.Console: {e}") from e


# ──────────────────────────────────────────────────────────────────────────────
# Robust Scaler with scale floor
# ──────────────────────────────────────────────────────────────────────────────
class RobustStandardScaler(RobustScaler):
    """RobustScaler (median/IQR) with scale floor to prevent division-by-zero.
    
    v11.1.2: Changed from StandardScaler (mean/std) to RobustScaler (median/IQR).
    RobustScaler is robust to outliers in training data, which is critical when
    the historical data may contain faults.
    
    Prevents catastrophic Z-score spikes when batch variance collapses.
    Critical fix for batch continuity: per-batch standardization on narrow slices
    can create near-zero scale, exploding Z-scores at batch boundaries.
    
    Parameters
    ----------
    epsilon : float, default=1e-6
        Minimum allowed scale. Values below this are clamped.
    with_centering : bool, default=True
        If True, center the data before scaling (subtract median).
    with_scaling : bool, default=True
        If True, scale the data to IQR (divide by IQR).
    """
    def __init__(self, epsilon: float = 1e-6, with_centering: bool = True, 
                 with_scaling: bool = True, **kwargs):
        # Use RobustScaler's native parameter names (with_centering, with_scaling)
        super().__init__(with_centering=with_centering, with_scaling=with_scaling, **kwargs)
        self.epsilon = epsilon
    
    def fit(self, X, y=None):
        super().fit(X, y)
        if self.with_scaling and hasattr(self, 'scale_') and self.scale_ is not None:
            # Degenerate-IQR fallback: quantized channels (>=75% identical
            # values, e.g. power at standstill) have IQR == 0 while std >> 0.
            # Clamping their scale to epsilon (1e-6) divided real spread by a
            # millionth — every scaled row landed 1e4-1e6 units out and the
            # PCA-SPE statistic saturated its clip on 100% of samples,
            # flattening the detector. Fall back to the column's std, then to
            # its robust range, before resorting to epsilon.
            degenerate = self.scale_ <= self.epsilon
            if np.any(degenerate):
                X_arr = np.asarray(X, dtype=np.float64)
                col_std = np.nanstd(X_arr, axis=0)
                col_range = np.nanmax(X_arr, axis=0) - np.nanmin(X_arr, axis=0)
                fallback = np.where(col_std > self.epsilon, col_std, col_range)
                self.scale_ = np.where(degenerate, np.maximum(fallback, self.epsilon), self.scale_)
            self.scale_ = np.maximum(self.scale_, self.epsilon)
        return self

# ──────────────────────────────────────────────────────────────────────────────
# PCA Subspace
# ──────────────────────────────────────────────────────────────────────────────
class PCASubspaceDetector:
    """
    PCA subspace monitoring returning:
      - SPE (Q): squared prediction error (distance to principal subspace)
      - T²     : Hotelling's T-squared (distance within the subspace)
    """

    def __init__(self, pca_cfg: Dict[str, Any] | None = None):
        self.cfg: Dict[str, Any] = (pca_cfg or {})
        # Use RobustStandardScaler to prevent variance collapse
        # Note: RobustScaler uses with_centering/with_scaling (not with_mean/with_std)
        self.scaler = RobustStandardScaler(epsilon=1e-6, with_centering=True, with_scaling=True)
        self.pca: Optional[PCA] | Any = None  # Allow IncrementalPCA too

        # Winsorize scaled values to +/- this many robust units before PCA
        # (fit AND score). Heavy-tailed features (_rz spikes to +/-100,
        # rolling kurtosis to 1000s) put single cells at 1e3-1e4 scaled units;
        # SPE squares and sums them, saturating its 1e6 clip on healthy data.
        # Beyond ~8 robust sigma, magnitude adds nothing to a correlation-
        # structure detector — but it destroys the subspace geometry.
        self.scaled_clip: float = float(self.cfg.get("scaled_clip", 8.0))

        self.keep_cols: List[str] = []
        self.col_medians: Optional[pd.Series] = None

    def fit(self, X: pd.DataFrame) -> "PCASubspaceDetector":
        """Fit scaler + PCA on TRAIN safely. Memory-optimized."""
        with Span("fit.pca", n_samples=len(X), n_features=X.shape[1] if len(X) > 0 else 0):
            from core.observability import Console
            Console.info(f"Fit start: train shape={X.shape}", component="PCA")
            
            # MEMORY OPT: Work with numpy arrays directly, avoid DataFrame copies
            # First, identify columns to keep (non-constant, finite)
            arr = X.values.astype(np.float64, copy=True)  # Need copy for in-place ops
            arr = np.where(np.isinf(arr), np.nan, arr)
            
            # Find columns with non-NaN values and variance > epsilon
            col_mask = ~np.all(np.isnan(arr), axis=0)  # Has at least one finite value
            col_std = np.nanstd(arr[:, col_mask], axis=0) if col_mask.any() else np.array([])
            var_mask = col_std > 1e-6
            
            # Build final keep_cols list
            orig_cols = X.columns.tolist()
            kept_indices = np.where(col_mask)[0][var_mask]
            self.keep_cols = [orig_cols[i] for i in kept_indices]
            
            # If everything got dropped, use dummy
            if len(self.keep_cols) == 0:
                self.keep_cols = ["_dummy"]
                arr = np.zeros((len(X), 1), dtype=np.float64)
            else:
                arr = arr[:, kept_indices]
            
            # Compute medians for kept columns and impute in-place.
            # Impute by NaN mask directly — the old nan_to_num(0.0) +
            # "replace zeros with median" corrupted every LEGITIMATE zero
            # reading (power at standstill, closed valves) into the median.
            self.col_medians = pd.Series(np.nanmedian(arr, axis=0), index=self.keep_cols)
            nan_rows, nan_cols = np.where(np.isnan(arr))
            if nan_rows.size:
                arr[nan_rows, nan_cols] = np.take(self.col_medians.values, nan_cols)
            np.nan_to_num(arr, copy=False, nan=0.0)  # medians can be NaN if all-NaN col
            # Clip in-place
            np.clip(arr, -1e6, 1e6, out=arr)
            
            # COR-02: Guard against insufficient samples for PCA after feature filtering
            # PCA requires at least 2 samples to compute meaningful components
            n_samples, n_features = arr.shape
            if n_samples < 2:
                Console.warn(
                    f"Insufficient samples after feature filtering (n={n_samples}). "
                    f"Skipping PCA fit - score() will return zeros.", component="PCA"
                )
                # Set PCA to None to signal fallback mode
                self.pca = None
                self.keep_cols = []
                return self

            # Scale - fit_transform modifies in-place when possible
            Xs = self.scaler.fit_transform(arr)
            del arr  # Free original array
            if self.scaled_clip > 0:
                np.clip(Xs, -self.scaled_clip, self.scaled_clip, out=Xs)

            # Choose a safe n_components
            user_nc = self.cfg.get("n_components", 5)
            try:
                user_nc = int(user_nc)
            except Exception:
                user_nc = 5
            k = int(max(1, min(user_nc, n_features, max(1, n_samples - 1))))
            
            # Incremental path (CPU only)
            if self.cfg.get("incremental", False):
                from sklearn.decomposition import IncrementalPCA
                self.pca = IncrementalPCA(  # type: ignore[assignment]
                    n_components=k,
                    batch_size=max(256, int(self.cfg.get("batch_size", 4096))),
                )
                # partial_fit in batches
                bs = self.pca.batch_size or 256  # type: ignore[attr-defined]
                for i in range(0, n_samples, bs):
                    batch_end = min(i+bs, n_samples)
                    self.pca.partial_fit(Xs[i:batch_end])  # type: ignore[attr-defined]
            else:
                # Default batch path
                self.pca = PCA(n_components=k, svd_solver="full", random_state=17)
                self.pca.fit(Xs)
                
            Console.info(f"Fit complete in {Span.__name__}: {k} components, {n_samples} samples, {n_features} features", component="PCA" if "skip_loki" not in locals() else None, skip_loki=True)
            return self

    def score(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Return (SPE, T²) as float32 arrays. Memory-optimized."""
        with Span("score.pca", n_samples=len(X), n_features=X.shape[1] if len(X) > 0 else 0):
            n = len(X)
            if self.pca is None or self.col_medians is None:
                return np.zeros(n, dtype=np.float32), np.zeros(n, dtype=np.float32)
            
            # MEMORY OPT: Work with numpy arrays, avoid DataFrame copies
            # Reindex to keep_cols by extracting only needed columns
            keep_set = set(self.keep_cols)
            col_indices = [X.columns.get_loc(c) for c in self.keep_cols if c in X.columns]
            
            if len(col_indices) == len(self.keep_cols):
                # Fast path: all columns present
                arr = X.values[:, col_indices].astype(np.float64, copy=True)
            else:
                # Slow path: need to build array with missing columns filled
                arr = np.empty((n, len(self.keep_cols)), dtype=np.float64)
                for i, c in enumerate(self.keep_cols):
                    if c in X.columns:
                        arr[:, i] = X[c].values
                    else:
                        arr[:, i] = self.col_medians.iloc[i]
            
            # Replace inf with nan, then fill with medians (in-place)
            arr[np.isinf(arr)] = np.nan
            for i, med in enumerate(self.col_medians.values):
                col = arr[:, i]
                mask = np.isnan(col)
                col[mask] = med
            
            # Scale (+ same winsorization as fit — keeps SPE on the same scale)
            Xs = self.scaler.transform(arr)
            del arr  # Free input array
            if getattr(self, "scaled_clip", 0) > 0:
                np.clip(Xs, -self.scaled_clip, self.scaled_clip, out=Xs)

            # Project to latent space
            Z = self.pca.transform(Xs)
            
            # MEMORY OPT: Compute SPE without storing full reconstruction
            # SPE = ||Xs - Xs_reconstructed||^2 = ||Xs||^2 - ||Z||^2 (for orthonormal basis)
            # But sklearn PCA may not be orthonormal after scaling, so we compute in chunks
            # Actually: SPE = sum((Xs - PC @ Z.T).T ** 2) - use einsum for memory efficiency
            components = self.pca.components_  # (k, n_features)
            
            # Reconstruct: X_hat = Z @ components + mean (in PCA space)
            # But we need Xs - X_hat where Xs is already centered by scaler
            # X_hat = Z @ components (since PCA is fitted on scaled data which is centered)
            # SPE = sum((Xs - Z @ components) ** 2, axis=1)
            # Use einsum to avoid materializing full X_hat matrix
            # SPE = sum(Xs**2) - 2*sum(Xs*(Z@comp)) + sum((Z@comp)**2)
            # Simpler: compute in blocks if data is large
            
            if n > 10000:
                # Block processing for large data
                spe = np.zeros(n, dtype=np.float64)
                block_size = 5000
                for start in range(0, n, block_size):
                    end = min(start + block_size, n)
                    X_hat_block = Z[start:end] @ components
                    diff = Xs[start:end] - X_hat_block
                    spe[start:end] = np.sum(diff ** 2, axis=1)
                    del X_hat_block, diff
            else:
                # Small data: direct computation
                X_hat = Z @ components
                spe = np.sum((Xs - X_hat) ** 2, axis=1)
                del X_hat
            
            del Xs  # Free scaled data
            
            # Clip SPE
            np.clip(spe, 0.0, 1e6, out=spe)

            # Hotelling T² (guard tiny eigenvalues)
            ev = getattr(self.pca, "explained_variance_", None)
            if ev is None:
                t2 = np.sum(Z ** 2, axis=1)
            else:
                ev = np.maximum(np.asarray(ev, dtype=np.float64), 1e-12)
                # MEMORY OPT: In-place operations
                Z_sq = Z ** 2  # (n, k) - small since k is typically 5
                Z_sq /= ev  # In-place divide
                np.clip(Z_sq, 0.0, 1e6, out=Z_sq)
                t2 = np.sum(Z_sq, axis=1)
                del Z_sq
            
            del Z  # Free latent projections

            # Final sanitization
            np.nan_to_num(spe, copy=False, nan=0.0, posinf=1e6, neginf=0.0)
            np.nan_to_num(t2, copy=False, nan=0.0, posinf=1e6, neginf=0.0)
            np.clip(t2, 0.0, 1e6, out=t2)

            return spe.astype(np.float32, copy=False), t2.astype(np.float32, copy=False)

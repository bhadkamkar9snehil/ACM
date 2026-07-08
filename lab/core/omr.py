# core/omr.py
"""
Overall Model Residual (OMR) - Multivariate health indicator.

The OMR captures equipment health by modeling the normal relationships between
all sensors and detecting when actual behavior deviates from the learned baseline.
Unlike univariate detectors (AR1, PCA SPE), OMR captures multivariate correlations.

Key features:
- Fits a multivariate model (PLS, Linear, or PCA) on healthy baseline data
- Computes reconstruction error as health indicator
- Tracks per-sensor contributions to identify root causes
- Supports multiple model architectures with auto-selection
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, List, Literal
from enum import Enum

import numpy as np
import pandas as pd
from sklearn.cross_decomposition import PLSRegression
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


class ModelType(str, Enum):
    """Supported model types for OMR."""
    PLS = "pls"
    LINEAR = "linear"
    PCA = "pca"
    AUTO = "auto"


@dataclass
class OMRModel:
    """Container for trained OMR model and metadata."""
    model: Any  # PLSRegression, Ridge, or PCA (None when using stored linear ensemble)
    scaler: StandardScaler
    model_type: str  # "pls", "linear", "pca"
    feature_names: List[str]
    train_residual_std: float  # For z-score normalization (legacy row-L2 scale)
    n_components: int  # Number of latent components (PLS/PCA)
    feature_resid_med: Optional[np.ndarray] = None    # per-feature residual median
    feature_resid_scale: Optional[np.ndarray] = None  # per-feature residual MAD*1.4826
    linear_models: Optional[List[Dict[str, Any]]] = None  # Stored ridge sub-models for linear mode
    train_samples: int = 0  # Track training sample count
    train_features: int = 0  # Track training feature count
    train_medians: Optional[np.ndarray] = None  # For consistent imputation
    var_mask: Optional[np.ndarray] = None  # Feature variance mask for zero-variance drop
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        import joblib
        from io import BytesIO
        
        # Serialize sklearn model to bytes
        model_bytes = BytesIO()
        joblib.dump(self.model, model_bytes)
        model_bytes.seek(0)
        
        # Serialize scaler to bytes
        scaler_bytes = BytesIO()
        joblib.dump(self.scaler, scaler_bytes)
        scaler_bytes.seek(0)
        
        payload = {
            "model_type": self.model_type,
            "feature_names": self.feature_names,
            "train_residual_std": self.train_residual_std,
            "n_components": self.n_components,
            "model_bytes": model_bytes.read(),
            "scaler_bytes": scaler_bytes.read(),
            "train_samples": self.train_samples,
            "train_features": self.train_features,
            "train_medians": self.train_medians.tolist() if self.train_medians is not None else None,
            "var_mask": self.var_mask.tolist() if self.var_mask is not None else None,
        }
        if self.linear_models is not None:
            payload["linear_models"] = [
                {
                    "indices": model_entry["indices"].tolist(),
                    "coef": model_entry["coef"].tolist(),
                    "intercept": model_entry["intercept"],
                }
                for model_entry in self.linear_models
            ]
        return payload


class OMRDetector:
    """
    Overall Model Residual detector using multivariate modeling.
    
    Strategy:
    1. Fit a multivariate model (PLS/Linear/PCA) on healthy training data
    2. For each timestep, predict sensor values from all other sensors
    3. Compute reconstruction error: ||x - x_reconstructed||
    4. Normalize by training residual std to get z-score
    5. Track per-sensor squared contributions to identify culprits
    
    Model Selection:
    - PLS: Best for high correlation, moderate sample size (default)
    - Linear: Fast, works well with sufficient samples
    - PCA: Best for dimensionality reduction, captures variance
    """
    
    # Constants
    MIN_RESIDUAL_STD = 1e-6  # Prevent division by zero
    DEFAULT_N_COMPONENTS = 5
    DEFAULT_ALPHA = 1.0
    DEFAULT_MIN_SAMPLES = 100
    VARIANCE_FLOOR = 1e-9  # Drop near-constant features
    MISSINGNESS_DROP = 0.5  # Drop columns with >50% missing
    HEALTHY_REGIME_DEFAULT = None  # Use configured label or majority regime
    
    def __init__(self, cfg: Optional[Dict[str, Any]] = None):
        """
        Initialize OMR detector.
        
        Args:
            cfg: Configuration dict with omr section
        """
        self.cfg = cfg or {}
        omr_cfg = self.cfg.get("omr", {})
        
        # Model selection
        self.model_type = omr_cfg.get("model_type", "auto")
        self.n_components = int(omr_cfg.get("n_components", self.DEFAULT_N_COMPONENTS))
        self.alpha = float(omr_cfg.get("alpha", self.DEFAULT_ALPHA))
        
        # Minimum samples for training
        self.min_samples = int(omr_cfg.get("min_samples", self.DEFAULT_MIN_SAMPLES))
        
        self.variance_floor = float(omr_cfg.get("variance_floor", self.VARIANCE_FLOOR))
        self.missingness_drop = float(omr_cfg.get("missingness_drop", self.MISSINGNESS_DROP))
        self.healthy_regime_label = omr_cfg.get("healthy_regime", self.HEALTHY_REGIME_DEFAULT)
        
        self._is_fitted = False
        self.model: Optional[OMRModel] = None
    
    def _select_model_type(self, n_samples: int, n_features: int) -> str:
        """
        Auto-select model type based on data characteristics.
        
        Args:
            n_samples: Number of training samples
            n_features: Number of features
            
        Returns:
            Model type: "pls", "linear", or "pca"
        """
        if self.model_type != "auto":
            return self.model_type
        
        # Decision tree for model selection
        if n_features > n_samples:
            # More features than samples - use PCA for dimensionality reduction
            return ModelType.PCA.value
        elif n_samples > 1000 and n_features < 20:
            # Large samples, moderate features - linear is fast
            return ModelType.LINEAR.value
        else:
            # Default: PLS works well for correlated sensor data
            return ModelType.PLS.value
    
    def _validate_input(self, X: pd.DataFrame) -> Tuple[bool, Optional[str]]:
        """
        Validate input data.
        
        Args:
            X: Input DataFrame
            
        Returns:
            (is_valid, error_message)
        """
        if X.empty:
            return False, "Empty input DataFrame"
        
        if X.shape[1] == 0:
            return False, "No features in input DataFrame"
        
        # Check for all-NaN columns
        all_nan_cols = X.columns[X.isna().all()].tolist()
        if all_nan_cols:
            return False, f"All-NaN columns detected: {all_nan_cols}"
        
        return True, None
    
    def _prepare_data(self, X: pd.DataFrame, medians: Optional[pd.Series] = None, var_mask: Optional[np.ndarray] = None) -> Tuple[np.ndarray, List[str]]:
        """
        Prepare data for modeling (handle missing values).
        
        Args:
            X: Input DataFrame
            medians: Optional precomputed medians to reuse for imputation
            var_mask: Optional variance mask to select columns
            
        Returns:
            (cleaned_array, feature_names)
        """
        # Drop columns with excessive missingness.
        # Vectorised: compute notna fraction across all columns at once via numpy
        # to avoid 632 per-column Series.__init__ / notna() calls (major bottleneck).
        if self.missingness_drop > 0:
            notna_frac = X.notna().mean()  # single vectorised pass over the whole frame
            keep_mask = notna_frac >= (1.0 - self.missingness_drop)
            X = X.loc[:, keep_mask]
        # Use provided medians or compute
        medians_to_use = medians if medians is not None else X.median()
        X_clean = X.fillna(medians_to_use)
        
        # For remaining NaNs (e.g., all-NaN columns), fill with 0
        X_clean = X_clean.fillna(0)
        
        # Apply variance mask if provided
        if var_mask is not None and len(var_mask) == X_clean.shape[1]:
            X_clean = X_clean.iloc[:, var_mask]
            feature_names = list(X_clean.columns)
        else:
            feature_names = list(X_clean.columns)
        
        return X_clean.values, feature_names
    
    def _compute_optimal_components(
        self, 
        n_samples: int, 
        n_features: int,
        model_type: str
    ) -> int:
        """
        Compute optimal number of components based on data dimensions.
        
        Args:
            n_samples: Number of samples
            n_features: Number of features
            model_type: Selected model type
            
        Returns:
            Optimal number of components
        """
        if model_type not in {ModelType.PLS.value, ModelType.PCA.value}:
            return 0  # Not applicable for linear models
        
        # Start with configured components
        max_components = self.n_components
        
        # Constrain by data dimensions
        max_components = min(max_components, n_features, n_samples - 1)
        
        # For PLS/PCA, need at least 2 features
        if n_features > 1:
            max_components = min(max_components, n_features - 1)
        
        # Ensure at least 1 component
        return max(1, max_components)
    
    def _fit_pls_model(self, X_scaled: np.ndarray, n_components: int) -> Tuple[Any, np.ndarray]:
        """Fit PLS model and return model + reconstructions."""
        model = PLSRegression(n_components=n_components, scale=False)
        model.fit(X_scaled, X_scaled)
        X_recon = model.predict(X_scaled)
        return model, X_recon
    
    def _fit_linear_model(self, X_scaled: np.ndarray, n_features: int) -> Tuple[None, np.ndarray, List[Dict[str, Any]]]:
        """Fit linear ensemble model and return reconstructions + metadata."""
        reconstructions = []
        linear_models = []
        col_indices = np.arange(n_features)
        
        for target_idx in range(n_features):
            other_idx = np.delete(col_indices, target_idx)
            X_others = X_scaled[:, other_idx]
            y_target = X_scaled[:, target_idx]
            
            ridge = Ridge(alpha=self.alpha)
            ridge.fit(X_others, y_target)
            y_pred = ridge.predict(X_others)
            
            reconstructions.append(y_pred)
            linear_models.append({
                "indices": other_idx.astype(np.int32),
                "coef": ridge.coef_.astype(np.float32),
                "intercept": float(ridge.intercept_),
            })
        
        X_recon = np.column_stack(reconstructions)
        return None, X_recon, linear_models
    
    def _fit_pca_model(self, X_scaled: np.ndarray, n_components: int) -> Tuple[Any, np.ndarray]:
        """Fit PCA model and return model + reconstructions."""
        model = PCA(n_components=n_components, random_state=42)
        X_latent = model.fit_transform(X_scaled)
        X_recon = model.inverse_transform(X_latent)
        return model, X_recon
    
    def fit(self, X: pd.DataFrame, regime_labels: Optional[np.ndarray] = None) -> "OMRDetector":
        """
        Fit OMR model on healthy training data.
        
        Args:
            X: Training data (n_samples, n_features)
            regime_labels: Optional regime labels to filter healthy data
            
        Returns:
            self (fitted)
        """
        from core.observability import Console, Span
        
        with Span("fit.omr", n_samples=len(X), n_features=X.shape[1] if len(X) > 0 else 0):
            # Validate input
            is_valid, error_msg = self._validate_input(X)
            if not is_valid:
                Console.info(f"Skipping fit: {error_msg}", component="OMR")
                return self
        
        # Filter to healthy regime if labels provided
        if regime_labels is not None and len(regime_labels) == len(X):
            if self.healthy_regime_label is not None:
                healthy_regime = self.healthy_regime_label
            else:
                # Choose majority regime as healthy if not specified.
                # mode() returns an empty Series when labels are empty/all-NaN;
                # in that case skip regime filtering instead of crashing.
                mode_vals = pd.Series(regime_labels).mode()
                healthy_regime = mode_vals.iloc[0] if len(mode_vals) > 0 else None
            if healthy_regime is not None:
                healthy_mask = regime_labels == healthy_regime
                n_healthy = int(np.sum(healthy_mask))

                if n_healthy >= self.min_samples:
                    X = X.iloc[healthy_mask]
                    Console.info(f"Filtered to healthy regime {healthy_regime}: {n_healthy} samples", component="OMR")
        
        # Prepare data
        X_clean, feature_names = self._prepare_data(X)
        n_samples, n_features = X_clean.shape

        # Drop zero-variance columns and store mask for scoring alignment
        var = np.var(X_clean, axis=0)
        var_mask = var > self.variance_floor
        if not var_mask.any():
            Console.warn("All features constant; skipping fit", component="OMR")
            return self
        X_clean = X_clean[:, var_mask]
        feature_names = [name for name, keep in zip(feature_names, var_mask) if keep]
        n_features = len(feature_names)
        
        # Check minimum samples
        min_required = max(20, min(self.min_samples // 2, n_features))
        if n_samples < min_required:
            Console.warn(f"Insufficient samples ({n_samples}/{min_required}), skipping fit", component="OMR")
            return self
        
        if n_samples < self.min_samples:
            Console.info(f"Proceeding with reduced sample count ({n_samples} < {self.min_samples})", component="OMR")
        
        # Auto-select model type
        selected_model = self._select_model_type(n_samples, n_features)
        Console.info(f"Selected model type: {selected_model.upper()}", component="OMR")
        
        # Fit scaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_clean)
        
        # Compute optimal components
        n_components = self._compute_optimal_components(n_samples, n_features, selected_model)
        
        linear_models: Optional[List[Dict[str, Any]]] = None
        model = None
        
        try:
            if selected_model == ModelType.PLS.value:
                model, X_recon = self._fit_pls_model(X_scaled, n_components)
                
            elif selected_model == ModelType.LINEAR.value:
                model, X_recon, linear_models = self._fit_linear_model(X_scaled, n_features)
                
            elif selected_model == ModelType.PCA.value:
                model, X_recon = self._fit_pca_model(X_scaled, n_components)
                
            else:
                raise ValueError(f"Unknown model type: {selected_model}")
            
            # Compute residuals
            residuals = X_scaled - X_recon
            residual_norm = np.linalg.norm(residuals, axis=1)
            # Robust scale to reduce heavy-tail sensitivity
            mad = float(np.median(np.abs(residual_norm - np.median(residual_norm)))) if residual_norm.size else 0.0
            robust_scale = mad * 1.4826 if mad > 0 else np.std(residual_norm)
            train_residual_std = float(robust_scale)
            
            # Enforce lower bound to prevent division by zero
            train_residual_std = max(train_residual_std, self.MIN_RESIDUAL_STD)

            # PER-FEATURE residual scales (median + MAD per column). The row-L2
            # statistic dilutes a single faulty channel by sqrt(n_features):
            # one bearing temperature at 8 sigma among 88 features moved the
            # row norm ~30% — invisible. Scoring uses the MAX per-feature
            # scaled residual instead: "which sensor stopped following the
            # others, and how badly". Floor each scale at 1% of the feature's
            # robust spread so quantized channels cannot explode.
            feat_med = np.median(residuals, axis=0)
            feat_mad = np.median(np.abs(residuals - feat_med), axis=0) * 1.4826
            feat_spread = np.subtract(*np.percentile(X_scaled, [97.5, 2.5], axis=0)) * -1.0
            feat_scale = np.maximum(feat_mad, np.maximum(0.01 * np.abs(feat_spread),
                                                         self.MIN_RESIDUAL_STD))
            
            self.model = OMRModel(
                model=model,
                scaler=scaler,
                model_type=selected_model,
                feature_names=feature_names,
                train_residual_std=train_residual_std,
                feature_resid_med=feat_med,
                feature_resid_scale=feat_scale,
                n_components=n_components,
                linear_models=linear_models if selected_model == ModelType.LINEAR.value else None,
                train_samples=n_samples,
                train_features=n_features,
                train_medians=np.median(X_clean, axis=0),
                var_mask=var_mask.astype(bool),
            )
            self._is_fitted = True
            
            Console.info(
                f"Fitted {selected_model.upper()} model: "
                f"{n_samples} samples, {n_features} features, "
                f"{n_components} components, std={train_residual_std:.3f}", component="OMR"
            )
            
        except Exception as e:
            Console.error(f"Model fitting failed: {e}", component="OMR")
            import traceback
            Console.error(traceback.format_exc(), component="OMR")
            return self

        return self

    def recalibrate_residual_scale(self, X_holdout: pd.DataFrame) -> "OMRDetector":
        """
        Recompute feature_resid_med/feature_resid_scale/train_residual_std from
        OUT-OF-SAMPLE residuals (the pipeline's interleaved calibration holdout),
        replacing the in-sample estimates fit() necessarily produces.

        fit() can only measure residuals on the rows it trained on; a model is
        optimized to minimize exactly those residuals, so in-sample residual
        scale is mechanically smaller than true residual variance. That bias
        understates feature_resid_scale and inflates every later (genuinely
        out-of-sample) per-feature z-score — including on healthy data. Calling
        this once, after fit(), on a held-out block fixes that bias at its
        source instead of compensating for it downstream.

        Falls back to keeping the in-sample (fit-time) estimates — never raises
        — if the holdout is too small, columns don't align, or reconstruction
        fails for any reason.
        """
        from core.observability import Console

        if not self._is_fitted or self.model is None:
            return self
        min_holdout = max(20, 2 * len(self.model.feature_names or []))
        if X_holdout is None or len(X_holdout) < min_holdout:
            return self

        try:
            feature_names = self.model.feature_names
            X = X_holdout
            if feature_names:
                X = X.reindex(feature_names, axis=1)
            if self.model.train_medians is not None:
                X_arr = X.to_numpy(dtype=float, na_value=np.nan)
                nan_mask = np.isnan(X_arr)
                if nan_mask.any():
                    medians_arr = self.model.train_medians
                    X_arr = np.where(nan_mask, medians_arr[np.newaxis, :], X_arr)
                var_mask = self.model.var_mask
                if var_mask is not None and len(var_mask) == X_arr.shape[1]:
                    X_arr = X_arr[:, var_mask]
                X_clean = X_arr
            else:
                X_clean, _ = self._prepare_data(X, medians=None, var_mask=self.model.var_mask)

            X_scaled = self.model.scaler.transform(X_clean)
            X_recon = self._reconstruct_data(X_scaled)
            residuals = X_scaled - X_recon

            if residuals.shape[1] != len(self.model.feature_resid_med
                                          if self.model.feature_resid_med is not None
                                          else feature_names):
                return self

            residual_norm = np.linalg.norm(residuals, axis=1)
            mad = float(np.median(np.abs(residual_norm - np.median(residual_norm)))) if residual_norm.size else 0.0
            robust_scale = mad * 1.4826 if mad > 0 else np.std(residual_norm)
            train_residual_std = max(float(robust_scale), self.MIN_RESIDUAL_STD)

            feat_med = np.median(residuals, axis=0)
            feat_mad = np.median(np.abs(residuals - feat_med), axis=0) * 1.4826
            feat_spread = np.subtract(*np.percentile(X_scaled, [97.5, 2.5], axis=0)) * -1.0
            feat_scale = np.maximum(feat_mad, np.maximum(0.01 * np.abs(feat_spread),
                                                          self.MIN_RESIDUAL_STD))

            self.model.train_residual_std = train_residual_std
            self.model.feature_resid_med = feat_med
            self.model.feature_resid_scale = feat_scale
            Console.info(
                f"Recalibrated residual scale from {len(X_holdout)} out-of-sample "
                f"holdout rows, std={train_residual_std:.3f}", component="OMR"
            )
        except Exception as e:
            Console.error(f"Out-of-sample recalibration failed, keeping in-sample "
                          f"estimates: {e}", component="OMR")

        return self

    def _reconstruct_data(self, X_scaled: np.ndarray) -> np.ndarray:
        """
        Reconstruct data using fitted model.
        
        Args:
            X_scaled: Scaled input data
            
        Returns:
            Reconstructed data
        """
        if self.model is None:
            return X_scaled.copy()
        
        if self.model.model_type == ModelType.PLS.value:
            return self.model.model.predict(X_scaled)
            
        elif self.model.model_type == ModelType.LINEAR.value:
            if not self.model.linear_models:
                return X_scaled.copy()
            
            reconstructions = []
            for model_entry in self.model.linear_models:
                other_idx = model_entry["indices"]
                X_others = X_scaled[:, other_idx]
                y_pred = X_others @ model_entry["coef"] + model_entry["intercept"]
                reconstructions.append(y_pred)
            
            return np.column_stack(reconstructions) if reconstructions else X_scaled.copy()
            
        elif self.model.model_type == ModelType.PCA.value:
            X_latent = self.model.model.transform(X_scaled)
            return self.model.model.inverse_transform(X_latent)
        
        return X_scaled.copy()
    
    def score(
        self, 
        X: pd.DataFrame, 
        return_contributions: bool = False
    ) -> np.ndarray | Tuple[np.ndarray, pd.DataFrame]:
        """
        Compute OMR z-scores (reconstruction error normalized by training std).
        
        Memory-optimized version v11.0.3: Uses in-place operations and explicit
        cleanup to minimize peak memory usage.
        
        Args:
            X: Scoring data (n_samples, n_features)
            return_contributions: If True, also return per-sensor contributions
            
        Returns:
            omr_z: OMR z-scores (n_samples,)
            contributions: Optional DataFrame of per-sensor squared residuals (n_samples, n_features)
        """
        from core.observability import Console, Span
        import gc
        
        with Span("score.omr", n_samples=len(X), n_features=X.shape[1] if len(X) > 0 else 0):
            n_samples = len(X)
            
            if not self._is_fitted or self.model is None:
                zeros = np.zeros(n_samples, dtype=np.float32)
                if return_contributions:
                    empty_contrib = pd.DataFrame(
                        np.zeros((n_samples, len(X.columns)), dtype=np.float32),
                        index=X.index,
                        columns=X.columns
                    )
                    return zeros, empty_contrib
                return zeros
            
            # Minimal validation only: empty input cannot be scored. Do NOT
            # reject on all-NaN columns here — the alignment below reindexes
            # to training feature_names and imputes from train_medians, so a
            # dead sensor is handled per-column. The old _validate_input gate
            # zeroed the ENTIRE detector when any one column was all-NaN,
            # which also poisoned downstream calibration (calibrators fitted
            # on an all-zero baseline turn every later raw score into a huge
            # z — the "chronic OMR elevation" seen on CARE holdouts).
            if X.empty or X.shape[1] == 0:
                zeros = np.zeros(n_samples, dtype=np.float32)
                if return_contributions:
                    empty_contrib = pd.DataFrame(
                        np.zeros((n_samples, len(X.columns)), dtype=np.float32),
                        index=X.index,
                        columns=X.columns
                    )
                    return zeros, empty_contrib
                return zeros

            # Store index for later use
            X_index = X.index
            feature_names = self.model.feature_names
            
            # Align columns to training feature order and mask.
            # Use numpy directly for imputation to avoid repeated pd.Series construction:
            # train_medians is already a numpy array aligned to feature_names.
            if feature_names:
                X = X.reindex(feature_names, axis=1)
            if self.model.train_medians is not None:
                # Fast path: fill NaNs using precomputed numpy medians (no Series alloc).
                X_arr = X.to_numpy(dtype=float, na_value=np.nan)
                nan_mask = np.isnan(X_arr)
                if nan_mask.any():
                    medians_arr = self.model.train_medians  # aligned to feature_names
                    X_arr = np.where(nan_mask, medians_arr[np.newaxis, :], X_arr)
                # Apply variance mask
                var_mask = self.model.var_mask
                if var_mask is not None and len(var_mask) == X_arr.shape[1]:
                    X_arr = X_arr[:, var_mask]
                X_clean = X_arr
                del X, X_arr
            else:
                X_clean, _ = self._prepare_data(X, medians=None, var_mask=self.model.var_mask)
                del X
            
            # Scale directly (returns a view or copy depending on sklearn)
            X_scaled = self.model.scaler.transform(X_clean)
            del X_clean  # Free cleaned data
            
            # Reconstruct
            try:
                X_recon = self._reconstruct_data(X_scaled)
            except Exception as e:
                Console.error(f"Reconstruction failed: {e}", component="OMR")
                del X_scaled
                gc.collect()
                zeros = np.zeros(n_samples, dtype=np.float32)
                if return_contributions:
                    empty_contrib = pd.DataFrame(
                        np.zeros((n_samples, len(feature_names)), dtype=np.float32),
                        index=X_index,
                        columns=feature_names
                    )
                    return zeros, empty_contrib
                return zeros
            
            # Compute residuals IN-PLACE by subtracting reconstruction from scaled
            # This avoids allocating a separate residuals array
            X_scaled -= X_recon
            del X_recon  # Free reconstruction immediately
            
            # Now X_scaled contains residuals
            residuals = X_scaled  # Just an alias, no copy

            # Z-SCORE: top-3 mean of per-feature scaled residuals ("which
            # sensors stopped following the others, and how badly").
            # - row-L2 diluted a single faulty channel by sqrt(n_features);
            # - a plain max is an extreme-value statistic whose HEALTHY tail
            #   grows with feature count, crushing calibration contrast.
            # Top-3 needs three simultaneously elevated features: noise rarely
            # provides that, while one faulty channel elevates all ~11 of its
            # engineered descendants.
            if (self.model.feature_resid_scale is not None
                    and len(self.model.feature_resid_scale) == residuals.shape[1]):
                scaled = np.abs(residuals - self.model.feature_resid_med) / self.model.feature_resid_scale
                # Kurtosis/skewness features are 3rd/4th-moment statistics over a
                # small rolling window (window=16); their sampling variance is
                # inherently high even on perfectly healthy data (asymptotic
                # var ~24/n for kurtosis, ~6/n for skewness), and OMR can't
                # reconstruct them well from other sensors' mean/std-type
                # features. Confirmed directly (CARE Farm C event 56): these
                # columns dominate the top-3 vote on 70-80%+ of rows on BOTH
                # the calibration holdout and live data alike, with the score
                # saturating at the candidate-pool ceiling regardless of true
                # anomaly state -- noise from unstable moment estimators, not a
                # genuine cross-sensor breakdown. Excluded from the score's
                # top-k candidate pool entirely (contributions below already
                # down-weight them at kurt_skew_weight=0.25 for the same
                # underlying reason; this closes the gap for the score itself).
                kurt_skew_mask = np.array(
                    [fn.endswith('_kurt') or fn.endswith('_skew') for fn in feature_names])
                if kurt_skew_mask.any() and kurt_skew_mask.shape[0] == scaled.shape[1]:
                    scaled[:, kurt_skew_mask] = -np.inf
                    k = min(3, int((~kurt_skew_mask).sum()))
                else:
                    k = min(3, scaled.shape[1])
                omr_z = np.mean(np.partition(scaled, -k, axis=1)[:, -k:], axis=1)
                del scaled
            else:
                omr_z = np.linalg.norm(residuals, axis=1) / self.model.train_residual_std

            # Contributions (per-sensor attribution)
            if return_contributions:
                # Need squared residuals for contributions - compute in-place
                squared_residuals = np.square(residuals)  # residuals ** 2
                
                # Normalize contributions by feature variance
                feature_variances = np.var(squared_residuals, axis=0) + 1e-9
                np.divide(squared_residuals, feature_variances, out=squared_residuals)
                
                # Apply weight reduction for kurtosis/skewness features
                kurt_skew_weight = 0.25
                for i, fname in enumerate(feature_names):
                    if fname.endswith('_kurt') or fname.endswith('_skew'):
                        squared_residuals[:, i] *= kurt_skew_weight
                
                # Free residuals (X_scaled) now that we have squared_residuals
                del residuals, X_scaled
                
                # Convert to DataFrame (uses normalized squared residuals)
                contrib_df = pd.DataFrame(
                    squared_residuals.astype(np.float32, copy=False),
                    index=X_index,
                    columns=feature_names
                )
                del squared_residuals
            else:
                del residuals, X_scaled

            omr_z = omr_z.astype(np.float32, copy=False)
            
            # Force garbage collection for large datasets
            if n_samples > 50000:
                gc.collect()
            
            if return_contributions:
                return omr_z, contrib_df
            
            return omr_z
    
    def get_top_contributors(
        self,
        contributions: pd.DataFrame,
        timestamp: pd.Timestamp,
        top_n: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Get top N sensor contributors for a specific timestamp.
        
        Args:
            contributions: Per-sensor squared residuals DataFrame
            timestamp: Timestamp to analyze
            top_n: Number of top contributors to return
            
        Returns:
            List of (sensor_name, contribution) tuples sorted by contribution
        """
        if timestamp not in contributions.index:
            return []
        
        row = contributions.loc[timestamp]
        top_sensors = row.nlargest(n=top_n)
        
        return [(str(sensor), float(value)) for sensor, value in top_sensors.items()]
    
    def get_diagnostics(self) -> Dict[str, Any]:
        """
        Get diagnostic information about the fitted model.
        
        Returns:
            Dictionary with model diagnostics
        """
        if not self._is_fitted or self.model is None:
            return {"fitted": False}
        
        return {
            "fitted": True,
            "model_type": self.model.model_type,
            "n_features": self.model.train_features,
            "n_samples": self.model.train_samples,
            "n_components": self.model.n_components,
            "train_residual_std": self.model.train_residual_std,
            "feature_names": self.model.feature_names,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        if self.model is None:
            return {"fitted": False}
        return {
            "fitted": True,
            "model": self.model.to_dict()
        }
    
    @classmethod
    def from_dict(cls, payload: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None) -> "OMRDetector":
        """Deserialize from dict."""
        import joblib
        from io import BytesIO
        
        inst = cls(cfg)
        if payload.get("fitted"):
            model_dict = payload["model"]
            
            # Deserialize sklearn model and scaler
            model_obj = joblib.load(BytesIO(model_dict["model_bytes"]))
            scaler_obj = joblib.load(BytesIO(model_dict["scaler_bytes"]))
            
            # Reconstruct OMRModel
            linear_models = None
            if "linear_models" in model_dict:
                linear_models = [
                    {
                        "indices": np.array(entry["indices"], dtype=np.int32),
                        "coef": np.array(entry["coef"], dtype=np.float32),
                        "intercept": float(entry["intercept"]),
                    }
                    for entry in model_dict["linear_models"]
                ]

            inst.model = OMRModel(
                model=model_obj,
                scaler=scaler_obj,
                model_type=model_dict["model_type"],
                feature_names=model_dict["feature_names"],
                train_residual_std=model_dict["train_residual_std"],
                n_components=model_dict["n_components"],
                linear_models=linear_models,
                train_samples=model_dict.get("train_samples", 0),
                train_features=model_dict.get("train_features", 0),
                train_medians=np.array(model_dict["train_medians"]) if model_dict.get("train_medians") is not None else None,
                var_mask=np.array(model_dict["var_mask"], dtype=bool) if model_dict.get("var_mask") is not None else None,
            )
            inst._is_fitted = True
        return inst

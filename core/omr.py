# models/omr.py
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

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd
from sklearn.cross_decomposition import PLSRegression
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


@dataclass
class OMRModel:
    """Container for trained OMR model and metadata."""
    model: Any  # PLSRegression, Ridge, or PCA (None when using stored linear ensemble)
    scaler: StandardScaler
    model_type: str  # "pls", "linear", "pca"
    feature_names: list[str]
    train_residual_std: float  # For z-score normalization
    n_components: int  # Number of latent components (PLS/PCA)
    linear_models: Optional[List[Dict[str, Any]]] = None  # Stored ridge sub-models for linear mode
    
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
    
    def __init__(self, cfg: Optional[Dict[str, Any]] = None):
        """
        Initialize OMR detector.
        
        Args:
            cfg: Configuration dict with omr section
        """
        self.cfg = cfg or {}
        omr_cfg = self.cfg.get("omr", {})
        
        # Model selection
        self.model_type = omr_cfg.get("model_type", "auto")  # "pls", "linear", "pca", "auto"
        self.n_components = int(omr_cfg.get("n_components", 5))  # Latent components
        self.alpha = float(omr_cfg.get("alpha", 1.0))  # Ridge regularization
        
        # Minimum samples for training
        self.min_samples = int(omr_cfg.get("min_samples", 100))
        
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
            return "pca"
        elif n_samples > 1000 and n_features < 20:
            # Large samples, moderate features - linear is fast
            return "linear"
        else:
            # Default: PLS works well for correlated sensor data
            return "pls"
    
    def fit(self, X: pd.DataFrame, regime_labels: Optional[np.ndarray] = None) -> "OMRDetector":
        """
        Fit OMR model on healthy training data.
        
        Args:
            X: Training data (n_samples, n_features)
            regime_labels: Optional regime labels to filter healthy data
            
        Returns:
            self (fitted)
        """
        if X.empty:
            print("[OMR] Empty training frame, skipping fit")
            return self
        
        # Filter to healthy regime if labels provided
        if regime_labels is not None and len(regime_labels) == len(X):
            # Assume regime 0 or lowest label is "healthy"
            healthy_regime = int(np.min(regime_labels))
            healthy_mask = regime_labels == healthy_regime
            if np.sum(healthy_mask) >= self.min_samples:
                X = X.iloc[healthy_mask]
                print(f"[OMR] Filtered to healthy regime {healthy_regime}: {np.sum(healthy_mask)} samples")
        
        # Handle missing values
        X_clean = X.fillna(X.median()).values
        feature_names = list(X.columns)
        n_samples, n_features = X_clean.shape

        if n_samples < self.min_samples:
            # Allow training when dimensionality is high despite fewer samples, but guard tiny samples
            if n_samples < max(20, min(self.min_samples // 2, n_features)):
                print(f"[OMR] Insufficient samples ({n_samples}/{self.min_samples}), skipping fit")
                return self
            print(f"[OMR] Proceeding with reduced sample count ({n_samples} < {self.min_samples}) for high-dimensional data")
        
        # Auto-select model type
        selected_model = self._select_model_type(n_samples, n_features)
        
        # Fit scaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_clean)
        
        # Adjust n_components to data constraints
        max_components = min(self.n_components, n_features, n_samples - 1)
        if selected_model in {"pls", "pca"} and n_features > 1:
            max_components = min(max_components, n_features - 1)
        if max_components < 1:
            max_components = 1
        
        linear_models: Optional[List[Dict[str, Any]]] = None

        try:
            if selected_model == "pls":
                # Partial Least Squares - models x = f(x) by finding latent components
                model = PLSRegression(n_components=max_components, scale=False)
                model.fit(X_scaled, X_scaled)  # Self-prediction
                X_recon = model.predict(X_scaled)
                
            elif selected_model == "linear":
                # Ridge regression - each sensor predicted from others
                # Use mean prediction across all leave-one-out models
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
                model = None  # Stored via linear_models metadata
                
            elif selected_model == "pca":
                # PCA reconstruction - projects to low-dim and back
                model = PCA(n_components=max_components, random_state=42)
                X_latent = model.fit_transform(X_scaled)
                X_recon = model.inverse_transform(X_latent)
                
            else:
                raise ValueError(f"Unknown model type: {selected_model}")
            
            # Compute residuals
            residuals = X_scaled - X_recon
            residual_norm = np.linalg.norm(residuals, axis=1)  # L2 norm per sample
            train_residual_std = float(np.std(residual_norm))
            
            # OMR-FIX-01: Enforce lower bound to prevent division by zero without muting anomalies
            train_residual_std = max(train_residual_std, 1e-6)
            
            self.model = OMRModel(
                model=model,
                scaler=scaler,
                model_type=selected_model,
                feature_names=feature_names,
                train_residual_std=train_residual_std,
                n_components=max_components,
                linear_models=linear_models if selected_model == "linear" else None
            )
            self._is_fitted = True
            
            print(f"[OMR] Fitted {selected_model.upper()} model: "
                  f"{n_samples} samples, {n_features} features, "
                  f"{max_components} components, std={train_residual_std:.3f}")
            
        except Exception as e:
            print(f"[OMR] Model fitting failed: {e}")
            return self
        
        return self
    
    def score(
        self, 
        X: pd.DataFrame, 
        return_contributions: bool = False
    ) -> np.ndarray | Tuple[np.ndarray, pd.DataFrame]:
        """
        Compute OMR z-scores (reconstruction error normalized by training std).
        
        Args:
            X: Scoring data (n_samples, n_features)
            return_contributions: If True, also return per-sensor contributions
            
        Returns:
            omr_z: OMR z-scores (n_samples,)
            contributions: Optional DataFrame of per-sensor squared residuals (n_samples, n_features)
        """
        if not self._is_fitted or self.model is None:
            zeros = np.zeros(len(X), dtype=np.float32)
            if return_contributions:
                return zeros, pd.DataFrame(index=X.index, columns=X.columns)
            return zeros
        
        # Handle missing values
        X_clean = X.fillna(X.median()).values
        
        # Scale
        X_scaled = self.model.scaler.transform(X_clean)
        
        # Reconstruct
        try:
            if self.model.model_type == "pls":
                X_recon = self.model.model.predict(X_scaled)
                
            elif self.model.model_type == "linear":
                if not self.model.linear_models:
                    X_recon = X_scaled.copy()
                else:
                    recon = []
                    for model_entry in self.model.linear_models:
                        other_idx = model_entry["indices"]
                        X_others = X_scaled[:, other_idx]
                        y_pred = X_others @ model_entry["coef"] + model_entry["intercept"]
                        recon.append(y_pred)
                    X_recon = np.column_stack(recon) if recon else X_scaled.copy()
                
            elif self.model.model_type == "pca":
                X_latent = self.model.model.transform(X_scaled)
                X_recon = self.model.model.inverse_transform(X_latent)
                
            else:
                X_recon = X_scaled  # Fallback
                
        except Exception as e:
            print(f"[OMR] Reconstruction failed: {e}")
            zeros = np.zeros(len(X), dtype=np.float32)
            if return_contributions:
                return zeros, pd.DataFrame(index=X.index, columns=X.columns)
            return zeros
        
        # Compute residuals
        residuals = X_scaled - X_recon
        
        # Per-sensor squared contributions (for root cause analysis)
        squared_residuals = residuals ** 2
        
        # Overall residual norm (L2)
        residual_norm = np.linalg.norm(residuals, axis=1)
        
        # Normalize by training std to get z-score
        omr_z = residual_norm / self.model.train_residual_std
        
        # OMR-FIX-01: Clip z-scores to ±10 to prevent extreme values in charts
        omr_z = np.clip(omr_z, -10.0, 10.0)
        omr_z = omr_z.astype(np.float32)
        
        if return_contributions:
            # Return per-sensor contributions (squared residuals)
            contrib_df = pd.DataFrame(
                squared_residuals,
                index=X.index,
                columns=self.model.feature_names
            )
            return omr_z, contrib_df
        
        return omr_z
    
    def get_top_contributors(
        self,
        contributions: pd.DataFrame,
        timestamp: pd.Timestamp,
        top_n: int = 5
    ) -> list[Tuple[str, float]]:
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
        # nlargest works on Series (row is already Series after .loc)
        top_sensors = row.nlargest(n=top_n)  # type: ignore[call-arg]
        
        return [(str(sensor), float(value)) for sensor, value in top_sensors.items()]
    
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
                linear_models=linear_models
            )
            inst._is_fitted = True
        return inst

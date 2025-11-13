"""
Model Versioning & Persistence Module
=====================================
Manages trained model storage, versioning, and loading with cold-start resolution.

Architecture:
- artifacts/{EQUIP}/models/v{N}/*.joblib - Versioned model artifacts
- artifacts/{EQUIP}/models/v{N}/manifest.json - Model metadata
- Config tracks active model version
- Auto-increments version on retraining
- Loads cached models on cold-start

Models persisted:
- AR1: fitted parameters (alpha, sigma)
- PCA: fitted model (sklearn.decomposition.PCA)
- IForest: fitted model (sklearn.ensemble.IsolationForest)
- GMM: fitted model (sklearn.mixture.GaussianMixture)
- Regimes: KMeans model (sklearn.cluster.KMeans)
- Scalers: StandardScaler for each detector
- Feature medians: Imputation values

Manifest structure:
{
    "version": 1,
    "created_at": "2025-10-27T16:04:37Z",
    "equip": "FD_FAN",
    "config_signature": "2ede5b7b43512a27",
    "train_rows": 10770,
    "train_sensors": ["sensor1", "sensor2", ...],
    "models": {
        "ar1": {"params": {...}, "quality": {...}},
        "pca": {"n_components": 5, "variance_ratio": 0.85, ...},
        "iforest": {"contamination": 0.001, "n_estimators": 100, ...},
        "gmm": {"n_components": 5, "bic": 12345.67, ...},
        "regimes": {"n_clusters": 4, "silhouette": 0.42, ...}
    },
    "feature_stats": {
        "n_features": 72,
        "imputation_medians": {...}
    }
}
"""

import joblib
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from utils.logger import Console


class ModelVersionManager:
    """Manages model versioning, persistence, and loading."""
    
    def __init__(self, equip: str, artifact_root: Path):
        """
        Initialize model version manager.
        
        Args:
            equip: Equipment name (e.g., "FD_FAN")
            artifact_root: Root artifacts directory (may or may not include equipment name)
        """
        self.equip = equip
        self.artifact_root = Path(artifact_root)
        
        # Check if artifact_root already includes equipment name to avoid duplication
        # (e.g., artifacts/COND_PUMP vs artifacts)
        if self.artifact_root.name == equip:
            # Path already includes equipment name (e.g., artifacts/COND_PUMP)
            self.models_root = self.artifact_root / "models"
        else:
            # Generic path, need to append equipment (e.g., artifacts -> artifacts/COND_PUMP/models)
            self.models_root = self.artifact_root / equip / "models"
        
        self.models_root.mkdir(parents=True, exist_ok=True)
    
    def get_latest_version(self) -> Optional[int]:
        """
        Get the latest model version number.
        
        Returns:
            Latest version number, or None if no models exist
        """
        versions = []
        for v_dir in self.models_root.glob("v*"):
            if v_dir.is_dir():
                try:
                    v_num = int(v_dir.name[1:])  # Extract number from "v123"
                    versions.append(v_num)
                except ValueError:
                    continue
        
        return max(versions) if versions else None
    
    def get_next_version(self) -> int:
        """Get the next version number (latest + 1, or 1 if none exist)."""
        latest = self.get_latest_version()
        return 1 if latest is None else latest + 1
    
    def get_version_path(self, version: int) -> Path:
        """Get the directory path for a specific version."""
        return self.models_root / f"v{version}"
    
    def save_models(
        self,
        models: Dict[str, Any],
        metadata: Dict[str, Any],
        version: Optional[int] = None
    ) -> int:
        """
        Save trained models with versioning.
        
        Args:
            models: Dictionary of model artifacts to save
                {
                    "ar1_params": {...},
                    "pca_model": PCA(...),
                    "iforest_model": IsolationForest(...),
                    "gmm_model": GaussianMixture(...),
                    "regime_model": KMeans(...),
                    "scalers": {...},
                    "feature_medians": pd.Series(...)
                }
            metadata: Model metadata for manifest.json
            version: Explicit version number, or None to auto-increment
        
        Returns:
            Version number used
        """
        # Determine version
        if version is None:
            version = self.get_next_version()
        
        version_dir = self.get_version_path(version)
        version_dir.mkdir(parents=True, exist_ok=True)
        
        Console.info(f"[MODEL] Saving models to version v{version}")
        
        # Save each model artifact with atomic writes to prevent corruption
        saved_files = []
        for model_name, model_obj in models.items():
            if model_obj is None:
                Console.warn(f"[MODEL] Skipping None model: {model_name}")
                continue
            
            filepath = version_dir / f"{model_name}.joblib"
            temp_fd = None
            temp_path = None
            try:
                # Use atomic write pattern: write to temp file, then replace
                temp_fd, temp_path = tempfile.mkstemp(
                    dir=version_dir,
                    prefix=f".{model_name}_",
                    suffix=".tmp"
                )
                # Close the file descriptor and write using joblib
                os.close(temp_fd)
                temp_fd = None
                
                # Write to temporary file
                joblib.dump(model_obj, temp_path)
                
                # Atomic replace (works on Windows & POSIX)
                os.replace(temp_path, filepath)
                temp_path = None  # Prevent cleanup since replace succeeded
                
                saved_files.append(model_name)
                Console.info(f"[MODEL]   - Saved {model_name}.joblib")
            except Exception as e:
                Console.warn(f"[MODEL]   - Failed to save {model_name}: {e}")
                # Clean up temp file if it still exists
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass
            finally:
                # Ensure file descriptor is closed if still open
                if temp_fd is not None:
                    try:
                        os.close(temp_fd)
                    except Exception:
                        pass
        
        # Create manifest with atomic write
        manifest = {
            "version": version,
            "created_at": datetime.now().isoformat(),
            "equip": self.equip,
            "saved_models": saved_files,
            **metadata
        }
        
        manifest_path = version_dir / "manifest.json"
        temp_fd = None
        temp_path = None
        try:
            # Atomic write for manifest
            temp_fd, temp_path = tempfile.mkstemp(
                dir=version_dir,
                prefix=".manifest_",
                suffix=".tmp"
            )
            # Write JSON to temp file
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(manifest, f, indent=2)
            temp_fd = None  # Already closed by fdopen context manager
            
            # Atomic replace
            os.replace(temp_path, manifest_path)
            temp_path = None  # Prevent cleanup since replace succeeded
        except Exception as e:
            Console.warn(f"[MODEL] Failed to save manifest: {e}")
            # Clean up temp file if it still exists
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            raise
        finally:
            # Ensure file descriptor is closed if still open
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except Exception:
                    pass
        
        Console.info(f"[MODEL] Saved {len(saved_files)} models to v{version}")
        Console.info(f"[MODEL] Manifest: {manifest_path}")
        
        return version
    
    def load_models(
        self,
        version: Optional[int] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Load models from a specific version.
        
        Args:
            version: Version to load, or None to load latest
        
        Returns:
            Tuple of (models_dict, manifest_dict), or (None, None) if not found
        """
        # Determine version to load
        if version is None:
            version = self.get_latest_version()
            if version is None:
                Console.info("[MODEL] No cached models found - will train from scratch")
                return None, None
        
        version_dir = self.get_version_path(version)
        if not version_dir.exists():
            Console.warn(f"[MODEL] Version v{version} not found")
            return None, None
        
        Console.info(f"[MODEL] Loading models from version v{version}")
        
        # Load manifest
        manifest_path = version_dir / "manifest.json"
        if not manifest_path.exists():
            Console.warn(f"[MODEL] Manifest not found for v{version}")
            return None, None
        
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        
        # Load all model files
        models = {}
        for model_name in manifest.get("saved_models", []):
            filepath = version_dir / f"{model_name}.joblib"
            if not filepath.exists():
                Console.warn(f"[MODEL]   - Missing {model_name}.joblib")
                continue
            
            try:
                models[model_name] = joblib.load(filepath)
                Console.info(f"[MODEL]   - Loaded {model_name}.joblib")
            except Exception as e:
                Console.warn(f"[MODEL]   - Failed to load {model_name}: {e}")
        
        Console.info(f"[MODEL] Loaded {len(models)} models from v{version}")
        
        return models, manifest
    
    def update_models_incremental(
        self,
        models: Dict[str, Any],
        new_data: pd.DataFrame,
        version: Optional[int] = None
    ) -> Tuple[Dict[str, Any], int]:
        """
        Update models incrementally with new data using partial_fit where available.
        
        This method supports incremental learning for compatible models:
        - PCA: Not directly supported, but can be approximated with IncrementalPCA
        - IsolationForest: Not supported (batch-only)
        - GMM: Not supported (batch-only)
        - Scalers: Can be updated with partial_fit
        
        For unsupported models, this returns the original models unchanged.
        
        Args:
            models: Dictionary of current model artifacts
            new_data: New data batch for incremental update
            version: Version to save updated models, or None to auto-increment
        
        Returns:
            Tuple of (updated_models, version_number)
        """
        from sklearn.preprocessing import StandardScaler
        
        updated_models = models.copy()
        updated_count = 0
        
        Console.info(f"[MODEL] Updating models incrementally with {len(new_data)} new samples")
        
        # Update scalers if present and new data is available
        if "scalers" in models and models["scalers"] is not None and not new_data.empty:
            scalers = models["scalers"]
            updated_scalers = {}
            
            for detector_name, scaler in scalers.items():
                if isinstance(scaler, StandardScaler):
                    try:
                        # Extract relevant features for this scaler
                        # Assume scaler was fitted on all columns or subset
                        available_features = [col for col in new_data.columns if col in scaler.feature_names_in_]
                        
                        if available_features:
                            scaler_data = new_data[available_features].dropna()
                            if not scaler_data.empty:
                                scaler.partial_fit(scaler_data)
                                updated_scalers[detector_name] = scaler
                                updated_count += 1
                                Console.info(f"[MODEL]   - Updated scaler for {detector_name}")
                        else:
                            updated_scalers[detector_name] = scaler
                    except Exception as e:
                        Console.warn(f"[MODEL]   - Failed to update scaler for {detector_name}: {e}")
                        updated_scalers[detector_name] = scaler
                else:
                    updated_scalers[detector_name] = scaler
            
            updated_models["scalers"] = updated_scalers
        
        # Note: PCA, IsolationForest, GMM, and KMeans don't support incremental updates
        # They would require full retraining or replacement with incremental variants:
        # - IncrementalPCA for PCA
        # - MiniBatchKMeans for KMeans
        # - No incremental equivalent for IsolationForest or GMM
        
        if updated_count > 0:
            Console.info(f"[MODEL] Successfully updated {updated_count} model components")
            
            # Save updated models to new version
            metadata = {
                "update_type": "incremental",
                "updated_components": updated_count,
                "new_samples": len(new_data),
                "updated_at": datetime.now().isoformat()
            }
            
            if version is None:
                version = self.get_next_version()
            
            version = self.save_models(updated_models, metadata, version=version)
            
            return updated_models, version
        else:
            Console.info("[MODEL] No models support incremental updates, returning original models")
            return models, self.get_latest_version() or 1
    
    def check_model_validity(
        self,
        manifest: Dict[str, Any],
        current_config_signature: str,
        current_sensors: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Check if cached models are valid for current run.
        
        Args:
            manifest: Loaded manifest dictionary
            current_config_signature: Current config signature
            current_sensors: Current sensor list
        
        Returns:
            Tuple of (is_valid, reasons_for_invalidity)
        """
        reasons = []
        
        # Check config signature
        cached_sig = manifest.get("config_signature", "")
        if cached_sig != current_config_signature:
            reasons.append(f"Config changed (cached: {cached_sig[:8]}, current: {current_config_signature[:8]})")
        
        # Check sensors
        cached_sensors = manifest.get("train_sensors", [])
        if set(cached_sensors) != set(current_sensors):
            reasons.append(f"Sensor list changed (cached: {len(cached_sensors)}, current: {len(current_sensors)})")
        
        is_valid = len(reasons) == 0
        return is_valid, reasons
    
    def list_versions(self) -> List[Dict[str, Any]]:
        """
        List all available model versions with metadata.
        
        Returns:
            List of version metadata dicts
        """
        versions = []
        for v_dir in sorted(self.models_root.glob("v*")):
            if not v_dir.is_dir():
                continue
            
            try:
                v_num = int(v_dir.name[1:])
            except ValueError:
                continue
            
            manifest_path = v_dir / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                    versions.append({
                        "version": v_num,
                        "path": v_dir,
                        "manifest": manifest
                    })
        
        return versions


def create_model_metadata(
    config_signature: str,
    train_data: pd.DataFrame,
    models_dict: Dict[str, Any],
    regime_quality: Optional[Dict[str, float]] = None,
    training_duration_s: Optional[float] = None
) -> Dict[str, Any]:
    """
    Create enhanced metadata dictionary for model manifest.
    
    Args:
        config_signature: Config signature hash
        train_data: Training dataframe (for stats)
        models_dict: Dictionary of trained models
        regime_quality: Optional regime quality metrics
        training_duration_s: Total training time in seconds
    
    Returns:
        Enhanced metadata dictionary with training duration, quality metrics, and data stats
    """
    # Base metadata
    metadata = {
        "config_signature": config_signature,
        "train_rows": len(train_data),
        "train_sensors": train_data.columns.tolist() if hasattr(train_data, 'columns') else [],
        "models": {}
    }
    
    # Training duration
    if training_duration_s is not None:
        metadata["training_duration_s"] = round(training_duration_s, 2)
        metadata["training_duration_minutes"] = round(training_duration_s / 60, 2)
    
    # Data quality statistics
    if hasattr(train_data, 'values'):
        try:
            values = train_data.values
            metadata["data_stats"] = {
                "n_rows": len(train_data),
                "n_columns": len(train_data.columns) if hasattr(train_data, 'columns') else 0,
                "nan_count": int(np.isnan(values).sum()),
                "nan_percentage": round(float(np.isnan(values).sum() / values.size * 100), 2) if values.size > 0 else 0,
                "inf_count": int(np.isinf(values).sum()),
                "mean": round(float(np.nanmean(values)), 4),
                "std": round(float(np.nanstd(values)), 4),
                "min": round(float(np.nanmin(values)), 4),
                "max": round(float(np.nanmax(values)), 4)
            }
        except Exception as e:
            Console.warn(f"[META] Failed to compute data stats: {e}")
            metadata["data_stats"] = {"error": str(e)}
    
    # AR1 metadata
    if "ar1_params" in models_dict and models_dict["ar1_params"]:
        params = models_dict["ar1_params"]
        # ar1_params is {"phimap": {sensor: phi, ...}, "sdmap": {sensor: sd, ...}}
        phimap = params.get("phimap", {})
        sdmap = params.get("sdmap", {})
        metadata["models"]["ar1"] = {
            "n_sensors": len(phimap) if phimap else len(sdmap) if sdmap else 0,
            "mean_autocorr": round(float(np.mean(list(phimap.values()))), 4) if phimap else 0.0,
            "mean_residual_std": round(float(np.mean(list(sdmap.values()))), 4) if sdmap else 0.0,
            "params_count": len(phimap) + len(sdmap) if phimap or sdmap else 0
        }
    
    # PCA metadata with enhanced quality metrics
    if "pca_model" in models_dict and models_dict["pca_model"]:
        pca = models_dict["pca_model"]
        explained_var_ratio = pca.explained_variance_ratio_
        metadata["models"]["pca"] = {
            "n_components": pca.n_components_,
            "variance_ratio_sum": round(float(explained_var_ratio.sum()), 4),
            "variance_ratio_first_component": round(float(explained_var_ratio[0]), 4),
            "variance_ratio_top3": round(float(explained_var_ratio[:3].sum()), 4) if len(explained_var_ratio) >= 3 else round(float(explained_var_ratio.sum()), 4),
            "explained_variance": [round(float(v), 4) for v in pca.explained_variance_],
            "singular_values": [round(float(v), 4) for v in pca.singular_values_]
        }
    
    # IForest metadata
    if "iforest_model" in models_dict and models_dict["iforest_model"]:
        iforest = models_dict["iforest_model"]
        metadata["models"]["iforest"] = {
            "n_estimators": iforest.n_estimators,
            "contamination": float(iforest.contamination) if hasattr(iforest, 'contamination') else None,
            "max_features": iforest.max_features if hasattr(iforest, 'max_features') else None,
            "max_samples": iforest.max_samples if hasattr(iforest, 'max_samples') else None
        }
    
    # GMM metadata with BIC and AIC
    if "gmm_model" in models_dict and models_dict["gmm_model"]:
        gmm = models_dict["gmm_model"]
        gmm_meta = {
            "n_components": gmm.n_components,
            "covariance_type": gmm.covariance_type
        }
        
        # Compute BIC and AIC if possible
        if hasattr(train_data, 'values'):
            try:
                gmm_meta["bic"] = round(float(gmm.bic(train_data.values)), 2)
                gmm_meta["aic"] = round(float(gmm.aic(train_data.values)), 2)
                gmm_meta["lower_bound"] = round(float(gmm.lower_bound_), 2)
            except Exception as e:
                Console.warn(f"[META] Failed to compute GMM quality metrics: {e}")
        
        metadata["models"]["gmm"] = gmm_meta
    
    # Regime metadata with enhanced quality metrics
    if "regime_model" in models_dict and models_dict["regime_model"]:
        regime = models_dict["regime_model"]
        regime_meta = {
            "n_clusters": regime.n_clusters,
            "quality": regime_quality or {}
        }
        
        # Add silhouette scores if available in quality metrics
        if regime_quality:
            if "silhouette_score" in regime_quality:
                regime_meta["silhouette_score"] = round(float(regime_quality["silhouette_score"]), 4)
            if "calinski_harabasz_score" in regime_quality:
                regime_meta["calinski_harabasz_score"] = round(float(regime_quality["calinski_harabasz_score"]), 2)
            if "davies_bouldin_score" in regime_quality:
                regime_meta["davies_bouldin_score"] = round(float(regime_quality["davies_bouldin_score"]), 4)
        
        # Add inertia
        if hasattr(regime, 'inertia_'):
            regime_meta["inertia"] = round(float(regime.inertia_), 2)
        
        # Add iterations
        if hasattr(regime, 'n_iter_'):
            regime_meta["n_iterations"] = int(regime.n_iter_)
        
        metadata["models"]["regimes"] = regime_meta
    
    # Feature stats
    if "feature_medians" in models_dict and models_dict["feature_medians"] is not None:
        medians = models_dict["feature_medians"]
        metadata["feature_stats"] = {
            "n_features": len(medians) if hasattr(medians, '__len__') else 0
        }
        
        # Add median statistics if it's a pandas Series
        if hasattr(medians, 'values'):
            try:
                median_vals = medians.values
                metadata["feature_stats"]["imputation_median_mean"] = round(float(np.nanmean(median_vals)), 4)
                metadata["feature_stats"]["imputation_median_std"] = round(float(np.nanstd(median_vals)), 4)
                metadata["feature_stats"]["imputation_zero_count"] = int(np.sum(median_vals == 0))
            except Exception:
                pass
    
    return metadata



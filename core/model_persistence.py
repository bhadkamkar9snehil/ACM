"""
Model Versioning & Persistence Module
=====================================
Manages trained model storage, versioning, and loading with cold-start resolution.

Architecture:
- SQL-ONLY MODE: All models stored in dbo.ModelRegistry table
- No filesystem artifacts - models serialized to VARBINARY(MAX) in SQL
- Config tracks active model version
- Auto-increments version on retraining
- Loads cached models on cold-start from SQL

Models persisted:
- AR1: fitted parameters (alpha, sigma)
- PCA: fitted model (sklearn.decomposition.PCA)
- IForest: fitted model (sklearn.ensemble.IsolationForest)
- GMM: fitted model (sklearn.mixture.GaussianMixture)
- Regimes: HDBSCAN or GMM model (v11.1.0: K-Means removed)
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
from typing import Dict, Any, Optional, List, Tuple, TYPE_CHECKING
from datetime import datetime, timezone
from io import BytesIO
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np
from core.schema_drift_manager import (
    apply_feature_schema_alignment,
    classify_feature_schema_drift,
)
from core.observability import Console

if TYPE_CHECKING:
    from core.fuse import ScoreCalibrator

# Import tracing support (optional)
try:
    from core.observability import Span
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    Span = None


# ============================================================================
# Forecast State Persistence (FORECAST-STATE-01)
# ============================================================================

@dataclass
class ForecastState:
    """
    Persistent state for continuous forecasting between batches.
    Enables temporal continuity and conditional retraining.
    
    Attributes:
        equip_id: Equipment ID
        state_version: Incremental version number
        model_type: Forecasting model type (AR1, ARIMA, ETS)
        model_params: **DEPRECATED** - Kept for schema compatibility, always empty dict {}
        residual_variance: **DEPRECATED** - Kept for schema compatibility, always 0.0
        last_forecast_horizon_json: JSON string of last forecast DataFrame
        hazard_baseline: EWMA smoothed hazard rate for probability continuity
        last_retrain_time: Timestamp of last full retrain
        training_data_hash: Hash of training window for change detection
        training_window_hours: Length of training window in hours
        forecast_quality: Dict with rmse, mae, mape metrics
        
    Note:
        model_params and residual_variance are retained only for legacy forecast-state
        schema compatibility. They are not populated or used in runtime logic.
    """
    equip_id: int
    state_version: int
    model_type: str
    model_params: Dict[str, Any]  # DEPRECATED: always {}
    residual_variance: float  # DEPRECATED: always 0.0
    last_forecast_horizon_json: str  # JSON array of {Timestamp, ForecastHealth, CI_Lower, CI_Upper}
    hazard_baseline: float
    last_retrain_time: str  # ISO format datetime string
    training_data_hash: str
    training_window_hours: int
    forecast_quality: Dict[str, float]  # {rmse, mae, mape}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastState":
        """Create ForecastState from dictionary."""
        return cls(**data)
    
    def get_last_forecast_horizon(self) -> pd.DataFrame:
        """Deserialize forecast horizon from JSON string."""
        try:
            import json
            horizon_data = json.loads(self.last_forecast_horizon_json)
            df = pd.DataFrame(horizon_data)
            if not df.empty and "Timestamp" in df.columns:
                df["Timestamp"] = pd.to_datetime(df["Timestamp"])
            return df
        except Exception as e:
            Console.warn(f"Failed to deserialize forecast horizon: {e}", component="FORECAST_STATE", equip_id=self.equip_id, state_version=self.state_version, error_type=type(e).__name__)
            return pd.DataFrame()
    
    @staticmethod
    def serialize_forecast_horizon(df: pd.DataFrame) -> str:
        """Serialize forecast horizon DataFrame to JSON string."""
        try:
            import json
            if df.empty:
                return "[]"
            # Convert Timestamp to ISO string for JSON compatibility
            df_copy = df.copy()
            if "Timestamp" in df_copy.columns:
                df_copy["Timestamp"] = df_copy["Timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
            return json.dumps(df_copy.to_dict(orient="records"))
        except Exception as e:
            Console.warn(f"Failed to serialize forecast horizon: {e}", component="FORECAST_STATE", rows=len(df), error_type=type(e).__name__)
            return "[]"


# ============================================================================
# Regime State Persistence (REGIME-STATE-01)
# ============================================================================

@dataclass
class RegimeState:
    """
    Persistent state for regime clustering between batches.
    Enables label continuity and conditional retraining.
    
    Attributes:
        equip_id: Equipment ID
        state_version: Incremental version number
        n_clusters: Number of regime clusters
        cluster_centers_json: JSON string of cluster centers (serialized numpy array)
        scaler_mean_json: JSON string of scaler mean values
        scaler_scale_json: JSON string of scaler scale values
        pca_components_json: JSON string of PCA components (if used)
        pca_explained_variance_json: JSON string of PCA explained variance ratios
        n_pca_components: Number of PCA components (0 if not used)
        silhouette_score: Clustering quality metric
        quality_ok: Boolean indicating if regime model passes quality checks
        last_trained_time: Timestamp of last training
        config_hash: Hash of regime config for change detection
        regime_basis_hash: Hash of regime basis features for change detection
    """
    equip_id: int
    state_version: int
    n_clusters: int
    cluster_centers_json: str
    scaler_mean_json: str
    scaler_scale_json: str
    pca_components_json: str
    pca_explained_variance_json: str
    n_pca_components: int
    silhouette_score: float
    quality_ok: bool
    last_trained_time: str  # ISO format datetime string
    config_hash: str
    regime_basis_hash: str
    training_distance_threshold: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegimeState":
        """Create RegimeState from dictionary."""
        return cls(**data)
    
    def get_cluster_centers(self) -> np.ndarray:
        """Deserialize cluster centers from JSON string."""
        try:
            centers = json.loads(self.cluster_centers_json)
            return np.array(centers)
        except Exception as e:
            Console.warn(f"Failed to deserialize cluster centers: {e}", component="REGIME_STATE", equip_id=self.equip_id, state_version=self.state_version, error_type=type(e).__name__)
            return np.array([])
    
    def get_scaler_params(self) -> Tuple[np.ndarray, np.ndarray]:
        """Deserialize scaler mean and scale from JSON strings."""
        try:
            mean = np.array(json.loads(self.scaler_mean_json))
            scale = np.array(json.loads(self.scaler_scale_json))
            return mean, scale
        except Exception as e:
            Console.warn(f"Failed to deserialize scaler params: {e}", component="REGIME_STATE", equip_id=self.equip_id, state_version=self.state_version, error_type=type(e).__name__)
            return np.array([]), np.array([])
    
    def get_pca_params(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Deserialize PCA components and explained variance."""
        if self.n_pca_components == 0:
            return None, None
        try:
            components = np.array(json.loads(self.pca_components_json))
            explained_var = np.array(json.loads(self.pca_explained_variance_json))
            return components, explained_var
        except Exception as e:
            Console.warn(f"Failed to deserialize PCA params: {e}", component="REGIME_STATE", equip_id=self.equip_id, state_version=self.state_version, error_type=type(e).__name__)
            return None, None
    
    @staticmethod
    def serialize_array(arr: np.ndarray) -> str:
        """Serialize numpy array to JSON string."""
        try:
            return json.dumps(arr.tolist())
        except Exception as e:
            Console.warn(f"Failed to serialize array: {e}", component="REGIME_STATE", array_shape=arr.shape if hasattr(arr, 'shape') else 'unknown', error_type=type(e).__name__)
            return "[]"


def save_regime_state(state: RegimeState, equip: str, sql_client=None) -> None:
    """
    Save RegimeState to SQL.
    
    Args:
        state: RegimeState object to persist
        equip: Equipment name (for logging)
        sql_client: SQL client (REQUIRED)
    """
    if sql_client is None:
        Console.error(
            f"Cannot persist regime state for {equip}: sql_client is None. "
            "Regime state will not survive across batches.",
            component="REGIME_STATE",
            equipment=equip,
        )
        return
    
    try:
        cur = sql_client.cursor()
        
        # Upsert into ACM_RegimeState
        cur.execute("""
            MERGE INTO dbo.ACM_RegimeState AS target
            USING (SELECT ? AS EquipID, ? AS StateVersion) AS source
            ON target.EquipID = source.EquipID AND target.StateVersion = source.StateVersion
            WHEN MATCHED THEN
                UPDATE SET
                    NumClusters = ?,
                    ClusterCentersJson = ?,
                    ScalerMeanJson = ?,
                    ScalerScaleJson = ?,
                    PCAComponentsJson = ?,
                    PCAExplainedVarianceJson = ?,
                    NumPCAComponents = ?,
                    SilhouetteScore = ?,
                    QualityOk = ?,
                    LastTrainedTime = ?,
                    ConfigHash = ?,
                    RegimeBasisHash = ?,
                    TrainingDistanceThreshold = ?
            WHEN NOT MATCHED THEN
                INSERT (EquipID, StateVersion, NumClusters, ClusterCentersJson,
                        ScalerMeanJson, ScalerScaleJson, PCAComponentsJson,
                        PCAExplainedVarianceJson, NumPCAComponents, SilhouetteScore,
                        QualityOk, LastTrainedTime, ConfigHash, RegimeBasisHash,
                        TrainingDistanceThreshold)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            state.equip_id, state.state_version,  # MERGE match
            state.n_clusters, state.cluster_centers_json,
            state.scaler_mean_json, state.scaler_scale_json,
            state.pca_components_json, state.pca_explained_variance_json,
            state.n_pca_components, state.silhouette_score, state.quality_ok,
            state.last_trained_time, state.config_hash, state.regime_basis_hash,
            state.training_distance_threshold,  # UPDATE values
            state.equip_id, state.state_version, state.n_clusters,
            state.cluster_centers_json, state.scaler_mean_json,
            state.scaler_scale_json, state.pca_components_json,
            state.pca_explained_variance_json, state.n_pca_components,
            state.silhouette_score, state.quality_ok,
            state.last_trained_time, state.config_hash, state.regime_basis_hash,
            state.training_distance_threshold  # INSERT values
        ))
        
        if not sql_client.conn.autocommit:
            sql_client.conn.commit()
        
    except Exception as e:
        Console.warn(f"Failed to save state to SQL: {e}", component="REGIME_STATE", equip_id=state.equip_id, state_version=state.state_version, error_type=type(e).__name__, error=str(e)[:200])


def load_regime_state(equip: str, equip_id: Optional[int] = None, sql_client=None) -> Optional[RegimeState]:
    """
    Load latest RegimeState from SQL.
    
    Args:
        equip: Equipment name (for logging)
        equip_id: Equipment ID (REQUIRED)
        sql_client: SQL client (REQUIRED)
    
    Returns:
        RegimeState object or None if not found
    """
    if sql_client is None or equip_id is None:
        Console.error("SQL client and equip_id required", component="REGIME_STATE", equipment=equip, equip_id=equip_id)
        return None
    
    try:
        cur = sql_client.cursor()
        cur.execute("""
            SELECT TOP 1
                EquipID, StateVersion, NumClusters, ClusterCentersJson,
                ScalerMeanJson, ScalerScaleJson, PCAComponentsJson,
                PCAExplainedVarianceJson, NumPCAComponents, SilhouetteScore,
                QualityOk, LastTrainedTime, ConfigHash, RegimeBasisHash,
                TrainingDistanceThreshold
            FROM dbo.ACM_RegimeState
            WHERE EquipID = ?
            ORDER BY StateVersion DESC
        """, (equip_id,))
        
        row = cur.fetchone()
        cur.close()
        
        if row:
            state = RegimeState(
                equip_id=row[0],
                state_version=row[1],
                n_clusters=int(row[2]) if row[2] is not None else 0,
                cluster_centers_json=row[3] or "[]",
                scaler_mean_json=row[4] or "[]",
                scaler_scale_json=row[5] or "[]",
                pca_components_json=row[6] or "[]",
                pca_explained_variance_json=row[7] or "[]",
                n_pca_components=int(row[8]) if row[8] is not None else 0,
                silhouette_score=float(row[9]) if row[9] is not None else 0.0,
                quality_ok=bool(row[10]) if row[10] is not None else False,
                last_trained_time=row[11].isoformat() if row[11] else datetime.now(timezone.utc).isoformat(),
                config_hash=row[12] or "",
                regime_basis_hash=row[13] or "",
                training_distance_threshold=float(row[14]) if row[14] is not None else None,
            )
            Console.info(f"Loaded state v{state.state_version} from SQL (EquipID={equip_id})", component="REGIME_STATE")
            return state
        else:
            Console.info(f"No existing state found in SQL for EquipID={equip_id}", component="REGIME_STATE")
            return None
    except Exception as e:
        Console.warn(f"Failed to load state from SQL: {e}", component="REGIME_STATE", equip_id=equip_id, equipment=equip, error_type=type(e).__name__, error=str(e)[:200])
        return None


# ============================================================================
# Model Version Manager
# ============================================================================

class ModelVersionManager:
    """Manages model versioning, persistence, and loading via SQL."""
    
    def __init__(self, equip: str, sql_client=None, equip_id: Optional[int] = None):
        """
        Initialize model version manager.
        
        Args:
            equip: Equipment name (e.g., "FD_FAN")
            sql_client: SQL client for model storage (REQUIRED)
            equip_id: Equipment ID for SQL operations (REQUIRED)
        """
        self.equip = equip
        self.sql_client = sql_client
        self.equip_id = equip_id

        if sql_client is None or equip_id is None:
            raise ValueError(
                f"ModelVersionManager requires sql_client and equip_id. "
                f"Received sql_client={type(sql_client).__name__}, equip_id={equip_id}."
            )
        if getattr(sql_client, "conn", None) is None:
            raise ValueError(
                "ModelVersionManager requires an active SQL connection (sql_client.conn is None). "
                "Connect SQL before constructing manager."
            )
    
    def get_latest_version(self) -> Optional[int]:
        """Get the latest model version number from SQL ModelRegistry."""
        return self._get_latest_version_from_sql()
    
    def get_next_version(self) -> int:
        """Get the next version number (latest + 1, or 1 if none exist)."""
        latest = self.get_latest_version()
        return 1 if latest is None else latest + 1
    
    def save_models(
        self,
        models: Dict[str, Any],
        metadata: Dict[str, Any],
        version: Optional[int] = None
    ) -> int:
        """
        Save trained models to SQL ModelRegistry (SQL-ONLY MODE).
        
        Args:
            models: Dictionary of model artifacts to save
            metadata: Model metadata
            version: Explicit version number, or None to auto-increment
        
        Returns:
            Version number used
        """
        # Start span for model persistence (v10.3.0 tracing enhancement)
        span_context = None
        if OTEL_AVAILABLE and Span is not None:
            span_context = Span(
                f"persist.save_model",
                model_count=len(models) if models else 0,
                equipment=self.equip,
            )
            span_context.__enter__()
        
        try:
            # Determine version
            if version is None:
                version = self.get_next_version()
            
            if span_context and hasattr(span_context, '_span') and span_context._span:
                span_context._span.set_attribute("acm.model_version", version)
            
            Console.info(f"Saving models to SQL ModelRegistry v{version}", component="MODEL")
            
            # Create manifest
            manifest = {
                "version": version,
                "created_at": datetime.now().isoformat(),
                "equip": self.equip,
                "saved_models": list(models.keys()),
                **metadata
            }
            
            # Save to SQL
            try:
                saved_count = self._save_models_to_sql(models, metadata, version)
                Console.info(f"Saved {saved_count} models to SQL ModelRegistry v{version}", component="MODEL")
                if span_context and hasattr(span_context, '_span') and span_context._span:
                    span_context._span.set_attribute("acm.models_saved", saved_count)
                return version
            except Exception as e:
                Console.error(f"Failed to save models to SQL: {e}", component="MODEL-SQL", equip_id=self.equip_id, version=version, error_type=type(e).__name__, error=str(e)[:200])
                if span_context and hasattr(span_context, '_span') and span_context._span:
                    span_context._span.set_attribute("acm.error", True)
                raise
        finally:
            if span_context:
                span_context.__exit__(None, None, None)
        
        return version
    
    def _save_models_to_sql(self, models: Dict[str, Any], metadata: Dict[str, Any], version: int) -> int:
        """
        Save models to SQL ModelRegistry table with atomic transaction handling.
        
        SQL-20 Implementation:
        - Serializes all model types to binary using joblib
        - Stores comprehensive metadata as JSON
        - Uses atomic transactions (rollback on any failure)
        - Handles special model types (ar1_params, omr_model)
        - Note: mhal_params removed v9.1.0 (MHAL deprecated)
        """
        Console.info(f"Saving models to SQL ModelRegistry v{version}...", component="MODEL-SQL")

        cursor = self.sql_client.conn.cursor()
        saved_count = 0
        errors = []
        
        try:
            # Begin transaction - will rollback if any model fails
            # (SQL Server auto-starts transaction on first command)
            
            # Delete existing models for this version if they exist (replace strategy)
            delete_sql = "DELETE FROM ModelRegistry WHERE EquipID = ? AND Version = ?"
            cursor.execute(delete_sql, (self.equip_id, version))
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                Console.info(f"Replaced {deleted_count} existing models for v{version}", component="MODEL-SQL")
            
            for model_name, model_obj in models.items():
                if model_obj is None:
                    Console.debug(f"- Skipping None model: {model_name}", component="MODEL-SQL")
                    continue
                
                try:
                    # Serialize model to bytes using joblib
                    buffer = BytesIO()
                    joblib.dump(model_obj, buffer)
                    model_bytes = buffer.getvalue()
                    
                    # Extract model-specific metadata
                    model_meta = metadata.get("models", {}).get(model_name.replace("_params", "").replace("_model", ""), {})
                    params_json = json.dumps(model_meta) if model_meta else None
                    
                    # Get overall stats (include full metadata for reconstruction)
                    stats_meta = {
                        "train_rows": metadata.get("train_rows"),
                        "train_sensors": metadata.get("train_sensors"),
                        "config_signature": metadata.get("config_signature"),
                        "created_at": metadata.get("created_at"),
                        "training_duration_s": metadata.get("training_duration_s"),
                        "data_stats": metadata.get("data_stats"),
                        "feature_stats": metadata.get("feature_stats")
                    }
                    stats_json = json.dumps(stats_meta)
                    
                    # Insert into ModelRegistry
                    insert_sql = """
                    INSERT INTO ModelRegistry 
                    (ModelType, EquipID, Version, EntryDateTime, ParamsJSON, StatsJSON, ModelBytes, RunID)
                    VALUES (?, ?, ?, SYSUTCDATETIME(), ?, ?, ?, NULL)
                    """
                    
                    cursor.execute(insert_sql, (
                        model_name,
                        self.equip_id,
                        version,
                        params_json,
                        stats_json,
                        model_bytes
                    ))
                    
                    saved_count += 1
                    Console.info(f"- Saved {model_name} ({len(model_bytes):,} bytes)", component="MODEL-SQL")
                    
                except Exception as e:
                    error_msg = f"Failed to save {model_name}: {e}"
                    errors.append(error_msg)
                    Console.warn(f"- {error_msg}", component="MODEL-SQL", model_name=model_name, equip_id=self.equip_id, version=version, error_type=type(e).__name__)
                    # Don't break - try to save other models, but will rollback all if any fail
            
            # Commit transaction if all successful
            if errors:
                Console.warn(f"Rolling back transaction due to {len(errors)} error(s)", component="MODEL-SQL", error_count=len(errors), equip_id=self.equip_id, version=version)
                self.sql_client.conn.rollback()
                Console.warn(f"Transaction rolled back - no models saved", component="MODEL-SQL", equip_id=self.equip_id, version=version)
                saved_count = 0
            else:
                self.sql_client.conn.commit()
                Console.info(f"OK Committed {saved_count}/{len(models)} models to SQL ModelRegistry v{version}", component="MODEL-SQL")
                
        except Exception as e:
            Console.warn(f"Critical error during save, rolling back: {e}", component="MODEL-SQL", equip_id=self.equip_id, version=version, error_type=type(e).__name__, error=str(e)[:200])
            try:
                self.sql_client.conn.rollback()
            except Exception:
                pass
            raise
        
        # v11.6.0 FIX #2: Cleanup old model versions to prevent accumulation
        # WFA_TURBINE_22 had 171 copies of each model type due to no retention
        self._cleanup_old_versions(keep_n=5)
        return saved_count

    def save_calibration_params(self, calibrators_dict: Dict[str, Any], version: int):
        """Append calibration params to an existing model version.

        v11.9.0: Calibration runs AFTER model save in the pipeline, so we
        persist calibration as a separate INSERT to the same version.
        This ensures scoring batches reuse training-time normalization.
        """
        if not calibrators_dict:
            return
        try:
            cal_dict = {}
            for name, cal in calibrators_dict.items():
                if hasattr(cal, "to_dict") and callable(getattr(cal, "to_dict")):
                    cal_dict[name] = cal.to_dict()
                elif isinstance(cal, dict):
                    cal_dict[name] = cal
            if not cal_dict:
                return

            buffer = BytesIO()
            joblib.dump(cal_dict, buffer)
            cal_bytes = buffer.getvalue()

            cursor = self.sql_client.conn.cursor()
            # Remove old calibration_params for this version (if re-running)
            cursor.execute(
                "DELETE FROM ModelRegistry WHERE EquipID = ? AND Version = ? AND ModelType = 'calibration_params'",
                (self.equip_id, version),
            )
            cursor.execute(
                """INSERT INTO ModelRegistry
                   (ModelType, EquipID, Version, EntryDateTime, ParamsJSON, StatsJSON, ModelBytes, RunID)
                   VALUES ('calibration_params', ?, ?, SYSUTCDATETIME(), NULL, NULL, ?, NULL)""",
                (self.equip_id, version, cal_bytes),
            )
            self.sql_client.conn.commit()
            Console.info(f"Saved calibration params ({len(cal_dict)} detectors, {len(cal_bytes):,} bytes) to v{version}", component="CAL")
        except Exception as e:
            Console.error(
                f"Failed to save calibration params: {e}",
                component="CAL", equip=self.equip,
                error_type=type(e).__name__, error=str(e)[:300],
            )
            try:
                self.sql_client.conn.rollback()
            except Exception:
                pass

    def _cleanup_old_versions(self, keep_n: int = 5) -> int:
        """
        Delete old model versions to prevent unbounded accumulation.
        
        v11.6.0 FIX #2: Model Accumulation Prevention
        =============================================
        Without cleanup, each run creates a new version and models accumulate:
        - Run 1 → Version 1 (saves 6 models)
        - Run 171 → Version 171 (171 × 6 = 1026 rows per equipment!)
        
        This method keeps only the latest N versions, deleting older ones.
        
        Args:
            keep_n: Number of recent versions to keep (default: 5)
            
        Returns:
            Number of rows deleted
        """
        try:
            cur = self.sql_client.cursor()
            
            # Delete all versions except the latest N
            # Uses a subquery to find versions to keep
            delete_sql = """
            DELETE FROM ModelRegistry 
            WHERE EquipID = ? 
            AND Version NOT IN (
                SELECT DISTINCT TOP (?) Version 
                FROM ModelRegistry 
                WHERE EquipID = ?
                ORDER BY Version DESC
            )
            """
            cur.execute(delete_sql, (self.equip_id, keep_n, self.equip_id))
            deleted_count = cur.rowcount
            self.sql_client.conn.commit()
            cur.close()
            
            if deleted_count > 0:
                Console.info(
                    f"Cleaned up {deleted_count} old model rows (keeping latest {keep_n} versions)",
                    component="MODEL-SQL", equip_id=self.equip_id, deleted=deleted_count, keep_n=keep_n
                )
            
            return deleted_count
            
        except Exception as e:
            Console.warn(
                f"Failed to cleanup old model versions: {e}",
                component="MODEL-SQL", equip_id=self.equip_id, error_type=type(e).__name__
            )
            return 0

    def _get_latest_version_from_sql(self) -> Optional[int]:
        """Fetch the latest Version for this EquipID from ModelRegistry."""
        try:
            cur = self.sql_client.cursor()
            cur.execute(
                "SELECT MAX(Version) FROM ModelRegistry WHERE EquipID = ?",
                (self.equip_id,)
            )
            row = cur.fetchone()
            cur.close()
            if row and row[0] is not None:
                return int(row[0])
            return None
        except Exception as e:
            Console.warn(f"Failed to get latest version from SQL: {e}", component="MODEL", equip_id=self.equip_id, error_type=type(e).__name__)
            return None
    
    def load_manifest_only(self) -> Optional[Dict[str, Any]]:
        """
        Load ONLY the manifest metadata for the latest model version — no model blobs.

        This is a cheap single-row SQL query used early in the pipeline (before
        feature imputation) so that we can extract ``train_sensors`` and protect
        those columns from being dropped by the low-variance filter.  Loading the
        full model objects (joblib deserialization of 5-10 MB blobs) is deferred
        until the normal ``models.load`` phase.

        Returns:
            manifest dict with at least ``train_sensors`` list, or None if no
            models exist for this equipment.
        """
        try:
            version = self._get_latest_version_from_sql()
            if version is None:
                return None
            cur = self.sql_client.cursor()
            # Fetch StatsJSON from ANY row for this version — they all share the
            # same stats block (written once per training run).
            cur.execute(
                "SELECT TOP 1 StatsJSON FROM ModelRegistry "
                "WHERE EquipID = ? AND Version = ? AND StatsJSON IS NOT NULL",
                (self.equip_id, version),
            )
            row = cur.fetchone()
            cur.close()
            if not row or not row[0]:
                return None
            stats = json.loads(row[0])
            manifest = {"version": version, "source": "sql_manifest_only", **stats}
            return manifest
        except Exception as e:
            Console.warn(
                f"load_manifest_only failed: {e}",
                component="MODEL-SQL",
                equip_id=self.equip_id,
                error_type=type(e).__name__,
            )
            return None

    def _load_models_from_sql(
        self,
        version: int,
        model_types: Optional[List[str]] = None,
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Load models from SQL ModelRegistry table with metadata reconstruction.

        SQL-21 Implementation:
        - Retrieves all model types for equipment + version
        - Deserializes binary model data using joblib
        - Reconstructs manifest from StatsJSON and ParamsJSON
        - Returns (models_dict, manifest_dict) tuple
        
        Returns:
            Tuple of (models_dict, manifest_dict) or None if not found
        """
        selected_model_types = sorted({str(model_type) for model_type in (model_types or []) if str(model_type).strip()})
        selected_model_suffix = (
            f" ({', '.join(selected_model_types)})"
            if selected_model_types
            else ""
        )
        Console.info(
            f"Loading models from SQL ModelRegistry v{version}{selected_model_suffix}...",
            component="MODEL-SQL",
        )

        try:
            cursor = self.sql_client.conn.cursor()
            
            # Query to get all models and their metadata
            sql = """
            SELECT ModelType, ModelBytes, ParamsJSON, StatsJSON, EntryDateTime
            FROM ModelRegistry 
            WHERE EquipID = ? AND Version = ?
            """
            params: List[Any] = [self.equip_id, version]
            if selected_model_types:
                placeholders = ",".join("?" for _ in selected_model_types)
                sql += f" AND ModelType IN ({placeholders})"
                params.extend(selected_model_types)
            sql += " ORDER BY ModelType"

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            if not rows:
                Console.info(f"No models found for EquipID={self.equip_id} Version={version}", component="MODEL-SQL")
                return None
            
            models = {}
            all_params = {}
            all_stats = {}
            entry_datetime = None
            
            for row in rows:
                model_type = row[0]
                model_bytes = row[1]
                params_json = row[2]
                stats_json = row[3]
                entry_dt = row[4]
                
                if entry_datetime is None and entry_dt:
                    entry_datetime = entry_dt
                
                # Deserialize model bytes
                if model_bytes:
                    try:
                        buffer = BytesIO(model_bytes)
                        model_obj = joblib.load(buffer)
                        models[model_type] = model_obj
                        Console.info(f"- Loaded {model_type} ({len(model_bytes):,} bytes)", component="MODEL-SQL")
                    except Exception as e:
                        Console.warn(f"- Failed to deserialize {model_type}: {e}", component="MODEL-SQL", model_type=model_type, equip_id=self.equip_id, version=version, error_type=type(e).__name__)
                        continue
                
                # Collect metadata
                if params_json:
                    try:
                        params = json.loads(params_json)
                        # Store with normalized key (remove _params/_model suffix)
                        key = model_type.replace("_params", "").replace("_model", "")
                        all_params[key] = params
                    except Exception as e:
                        Console.warn(f"- Failed to parse ParamsJSON for {model_type}: {e}", component="MODEL-SQL", model_type=model_type, equip_id=self.equip_id, version=version, error_type=type(e).__name__)
                
                if stats_json:
                    try:
                        stats = json.loads(stats_json)
                        all_stats.update(stats)  # Merge stats from all models
                    except Exception as e:
                        Console.warn(f"- Failed to parse StatsJSON for {model_type}: {e}", component="MODEL-SQL", model_type=model_type, equip_id=self.equip_id, version=version, error_type=type(e).__name__)
            
            if not models:
                Console.warn(f"No models successfully deserialized", component="MODEL-SQL", equip_id=self.equip_id, version=version, rows_found=len(rows))
                return None
            
            # Reconstruct manifest from SQL metadata
            manifest = {
                "version": version,
                "source": "sql",
                "equip": self.equip,
                "saved_models": list(models.keys()),
                "loaded_from_sql": True,
                "models": all_params,
                **all_stats  # Include train_rows, config_signature, created_at, etc.
            }
            
            if entry_datetime:
                manifest["entry_datetime"] = str(entry_datetime)
            
            Console.info(f"[OK] Loaded {len(models)}/{len(rows)} models from SQL ModelRegistry v{version}", component="MODEL-SQL")
            return models, manifest
            
        except Exception as e:
            Console.warn(f"Failed to load models from SQL: {e}", component="MODEL-SQL", equip_id=self.equip_id, version=version, error_type=type(e).__name__, error=str(e)[:200])
            import traceback
            traceback.print_exc()
            return None
    
    def load_models(
        self,
        version: Optional[int] = None,
        prefer_sql: bool = True,
        model_types: Optional[List[str]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Load models from a specific version (SQL first, then filesystem fallback).
        
        Args:
            version: Version to load, or None to load latest
            prefer_sql: If True and SQL client available, try SQL first
        
        Returns:
            Tuple of (models_dict, manifest_dict), or (None, None) if not found
        """
        # Start span for model loading (v10.3.0 tracing enhancement)
        span_context = None
        if OTEL_AVAILABLE and Span is not None:
            span_context = Span(
                f"persist.load_model",
                equipment=self.equip,
            )
            span_context.__enter__()
        
        try:
            # Determine version to load
            if version is None:
                version = self.get_latest_version()
                if version is None:
                    Console.info("No cached models found - will train from scratch", component="MODEL")
                    if span_context and hasattr(span_context, '_span') and span_context._span:
                        span_context._span.set_attribute("acm.models_loaded", 0)
                    return None, None
            
            if span_context and hasattr(span_context, '_span') and span_context._span:
                span_context._span.set_attribute("acm.model_version", version)

            result = self._load_models_from_sql(version, model_types=model_types)
            if result:
                sql_models, sql_manifest = result
                if span_context and hasattr(span_context, '_span') and span_context._span:
                    span_context._span.set_attribute("acm.models_loaded", len(sql_models))
                return sql_models, sql_manifest
            else:
                Console.warn(f"Failed to load models from SQL ModelRegistry", component="MODEL", equipment=self.equip, equip_id=self.equip_id, version=version)
                if span_context and hasattr(span_context, '_span') and span_context._span:
                    span_context._span.set_attribute("acm.error", True)
                return None, None
        finally:
            if span_context:
                span_context.__exit__(None, None, None)
    
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
        
        Console.info(f"Updating models incrementally with {len(new_data)} new samples", component="MODEL")
        
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
                                Console.info(f"- Updated scaler for {detector_name}", component="MODEL")
                        else:
                            updated_scalers[detector_name] = scaler
                    except Exception as e:
                        Console.warn(f"- Failed to update scaler for {detector_name}: {e}", component="MODEL", detector=detector_name, equip_id=self.equip_id, error_type=type(e).__name__)
                        updated_scalers[detector_name] = scaler
                else:
                    updated_scalers[detector_name] = scaler
            
            updated_models["scalers"] = updated_scalers
        
        # Note: PCA, IsolationForest, GMM, and HDBSCAN don't support incremental updates
        # They would require full retraining or replacement with incremental variants:
        # - IncrementalPCA for PCA
        # - No incremental equivalent for IsolationForest, GMM, or HDBSCAN
        
        if updated_count > 0:
            Console.info(f"Successfully updated {updated_count} model components", component="MODEL")
            
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
            Console.info("No models support incremental updates, returning original models", component="MODEL")
            return models, self.get_latest_version() or 1
    
    def check_model_validity(
        self,
        manifest: Dict[str, Any],
        current_config_signature: str,
        current_sensors: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Check if cached models are valid for current run.
        Task 5: Extended with temporal validation (model age threshold).
        
        Args:
            manifest: Loaded manifest dictionary
            current_config_signature: Current config signature
            current_sensors: Current sensor list
        
        Returns:
            Tuple of (is_valid, reasons_for_invalidity)
        """
        reasons = []
        warnings = []  # Soft issues - logged but don't cause rejection
        
        # Check config signature - ONLY reject if signatures are known and different
        cached_sig = manifest.get("config_signature", "")
        if cached_sig and current_config_signature and current_config_signature != "unknown":
            if cached_sig != current_config_signature:
                reasons.append(f"Config changed (cached: {cached_sig[:8]}, current: {current_config_signature[:8]})")
        
        # v11.6.1 FIX: Check sensor overlap, not exact match
        # Feature engineering can drop different low-variance columns run-to-run,
        # so exact match is too strict. Use 70% overlap threshold instead.
        cached_sensors = set(manifest.get("train_sensors", []))
        current_sensors_set = set(current_sensors)
        
        if cached_sensors and current_sensors_set:
            # Calculate overlap percentage
            common = cached_sensors & current_sensors_set
            overlap_ratio = len(common) / len(cached_sensors) if cached_sensors else 0
            
            if overlap_ratio < 0.7:
                # Less than 70% of cached features are present - major mismatch
                reasons.append(f"Sensor overlap too low: {overlap_ratio:.1%} (need 70%+), cached={len(cached_sensors)}, current={len(current_sensors_set)}")
            elif overlap_ratio < 1.0:
                # Partial mismatch - warn but don't reject
                missing_count = len(cached_sensors) - len(common)
                warnings.append(f"Minor sensor mismatch: {missing_count} of {len(cached_sensors)} cached features not in current data ({overlap_ratio:.1%} overlap)")
        elif cached_sensors and not current_sensors_set:
            # No current sensors passed - skip validation (legacy compatibility)
            warnings.append("Sensor validation skipped (no current sensors provided)")
        
        # Log warnings without failing
        for warn in warnings:
            Console.warn(warn, component="MODEL-CACHE")
        
        # Task 5: Temporal validation - reject models exceeding max_model_age_days
        from datetime import datetime, timedelta
        created_at_str = manifest.get("created_at")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
                age_days = (datetime.now() - created_at).total_seconds() / 86400
                max_age_days = manifest.get("max_model_age_days", 30)  # Default 30 days
                if age_days > max_age_days:
                    reasons.append(f"Model too old: {age_days:.1f}d > {max_age_days}d threshold")
            except Exception:
                pass
        
        is_valid = len(reasons) == 0
        return is_valid, reasons
    
    def list_versions(self) -> List[Dict[str, Any]]:
        """
        List all available model versions with metadata from SQL ModelRegistry.
        
        Returns:
            List of version metadata dicts
        """
        versions = []

        try:
            cur = self.sql_client.cursor()
            cur.execute("""
                SELECT DISTINCT Version, MIN(EntryDateTime) AS FirstSaved, COUNT(*) AS ModelCount
                FROM ModelRegistry 
                WHERE EquipID = ?
                GROUP BY Version
                ORDER BY Version DESC
            """, (self.equip_id,))
            
            rows = cur.fetchall()
            cur.close()
            
            for row in rows:
                versions.append({
                    "version": int(row[0]),
                    "saved_at": str(row[1]) if row[1] else None,
                    "model_count": int(row[2]),
                    "source": "sql"
                })
            
            Console.info(f"Found {len(versions)} versions in SQL ModelRegistry", component="MODEL")
        except Exception as e:
            Console.warn(f"Failed to list versions from SQL: {e}", component="MODEL", equip_id=self.equip_id, error_type=type(e).__name__)
        
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
    Task 5: Extended with temporal fields (train_start, train_end, train_hash).
    
    Args:
        config_signature: Config signature hash
        train_data: Training dataframe (for stats)
        models_dict: Dictionary of trained models
        regime_quality: Optional regime quality metrics
        training_duration_s: Total training time in seconds
    
    Returns:
        Enhanced metadata dictionary with training duration, quality metrics, and data stats
    """
    import hashlib
    
    # Base metadata
    metadata = {
        "config_signature": config_signature,
        "train_rows": len(train_data),
        "train_sensors": train_data.columns.tolist() if hasattr(train_data, 'columns') else [],
        "models": {}
    }
    
    # Task 5: Add temporal fields for drift/age validation
    if hasattr(train_data, 'index') and len(train_data):
        try:
            metadata["train_start"] = str(train_data.index.min())
            metadata["train_end"] = str(train_data.index.max())
        except Exception:
            pass
    
    # Task 5: Add train_hash for data fingerprint validation
    if hasattr(train_data, 'values'):
        try:
            data_bytes = train_data.values.tobytes()
            metadata["train_hash"] = hashlib.sha256(data_bytes).hexdigest()[:16]
        except Exception:
            pass
    
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
            Console.warn(f"Failed to compute data stats: {e}", component="META", train_rows=len(train_data), error_type=type(e).__name__)
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
        pca_data = models_dict["pca_model"]
        # v11.7.1: Handle new dict format and legacy raw PCA object
        pca = pca_data.get("pca") if isinstance(pca_data, dict) else pca_data
        if pca is None:
            pca = pca_data  # Fallback
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
        gmm_data = models_dict["gmm_model"]
        # v11.7.1: Handle new dict format and legacy raw GMM object
        gmm = gmm_data.get("model") if isinstance(gmm_data, dict) else gmm_data
        if gmm is None:
            gmm = gmm_data  # Fallback
        gmm_meta = {
            "n_components": gmm.n_components,
            "covariance_type": gmm.covariance_type
        }
        
        # Compute BIC and AIC if possible
        if hasattr(train_data, 'values'):
            try:
                gmm_n_features = getattr(gmm, "n_features_in_", None)
                if gmm_n_features is not None and train_data.shape[1] != gmm_n_features:
                    X_eval = train_data.values[:, :gmm_n_features]
                else:
                    X_eval = train_data.values
                gmm_meta["bic"] = round(float(gmm.bic(X_eval)), 2)
                gmm_meta["aic"] = round(float(gmm.aic(X_eval)), 2)
                gmm_meta["lower_bound"] = round(float(gmm.lower_bound_), 2)
            except Exception as e:
                Console.warn(f"Failed to compute GMM quality metrics: {e}", component="META", n_components=gmm.n_components, error_type=type(e).__name__)
        
        metadata["models"]["gmm"] = gmm_meta
    
    # Regime metadata with enhanced quality metrics
    if "regime_model" in models_dict and models_dict["regime_model"]:
        regime = models_dict["regime_model"]
        
        # Handle different types of regime models
        # Could be RegimeModel dataclass (has n_clusters property) or raw model (HDBSCAN/GMM)
        n_clusters = 0
        if hasattr(regime, 'n_clusters'):
            # RegimeModel dataclass
            if callable(getattr(regime, 'n_clusters', None)):
                n_clusters = regime.n_clusters()  # In case it's a method
            else:
                n_clusters = regime.n_clusters  # Property or attribute
        elif hasattr(regime, 'n_components'):
            # GMM
            n_clusters = regime.n_components
        elif hasattr(regime, 'labels_'):
            # HDBSCAN - count unique non-noise labels
            labels = regime.labels_
            unique_labels = np.unique(labels)
            n_clusters = len(unique_labels[unique_labels >= 0])
        
        regime_meta = {
            "n_clusters": int(n_clusters),
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


def load_cached_models_with_validation(
    equip: str,
    sql_client: Optional[Any],
    equip_id: int,
    cfg: Dict[str, Any],
    train_columns: List[str],
    model_types: Optional[List[str]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Load cached models from SQL and validate them.
    
    High-level wrapper around ModelVersionManager that handles:
    - Creating manager instance with appropriate storage config
    - Loading cached models
    - Validating cache against current config and sensors
    - Logging cache status
    
    Args:
        equip: Equipment name
        sql_client: SQL client connection
        equip_id: Equipment ID
        cfg: Configuration dictionary
        train_columns: Current training column names for validation
        
    Returns:
        Tuple of (cached_models dict, cached_manifest dict) or (None, None) if invalid
    """
    if sql_client is None:
        return None, None

    try:
        Console.info(f"Loading cached models for equip={equip}, equip_id={equip_id}", component="MODEL-LOAD")
        model_manager = ModelVersionManager(
            equip=equip, 
            sql_client=sql_client,
            equip_id=equip_id
        )
        cached_models, cached_manifest = model_manager.load_models(model_types=model_types)
        Console.info(f"Models loaded: {'OK' if cached_models and cached_manifest else 'MISSING'} (models={bool(cached_models)}, manifest={bool(cached_manifest)})", component="MODEL-LOAD")

        if cached_models and cached_manifest:
            # v11.7.0 FIX: Validate manifest-model consistency
            # Check if manifest's train_sensors count matches actual model n_features_in_
            # This prevents using corrupted cache where manifest and models are desynchronized
            manifest_feature_count = len(cached_manifest.get("train_sensors", []))

            # v11.7.1 FIX: PCA and GMM have internal feature filtering (keep_cols, _var_mask)
            # so their n_features_in_ will be LESS than the manifest's train_sensors count.
            # This is expected behavior, not cache corruption. Only IForest operates on the
            # full feature set, so it's the correct one to validate against manifest count.

            # Check IForest model feature count (if exists) - IForest uses full feature set
            if "iforest_model" in cached_models:
                iforest_model = cached_models["iforest_model"]
                if hasattr(iforest_model, 'n_features_in_'):
                    iforest_features = iforest_model.n_features_in_
                    if manifest_feature_count != iforest_features:
                        Console.error(
                            f"Manifest-model desync: manifest={manifest_feature_count}, IForest model={iforest_features}",
                            component="MODEL-LOAD",
                            equip=equip,
                            hint="Cache corrupted - delete models and retrain"
                        )
                        return None, None

            # Validate cache
            current_config_sig = cfg.get("_signature", "unknown")
            current_sensors = train_columns
            
            is_valid, invalid_reasons = model_manager.check_model_validity(
                manifest=cached_manifest,
                current_config_signature=current_config_sig,
                current_sensors=current_sensors
            )
            
            if is_valid:
                # Consolidated model cache info
                model_info = {
                    "version": cached_manifest['version'],
                    "created_at": cached_manifest.get('created_at', 'unknown'),
                    "config_sig": current_config_sig[:16],
                    "sensor_count": len(current_sensors),
                }
                if 'created_at' in cached_manifest:
                    from datetime import datetime
                    try:
                        created_at = datetime.fromisoformat(cached_manifest['created_at'])
                        model_info["age_hours"] = (datetime.now() - created_at).total_seconds() / 3600
                    except Exception:
                        pass
                age_str = f" | age={model_info['age_hours']:.1f}h" if 'age_hours' in model_info else ""
                Console.info(f"Using cached models v{model_info['version']}: sensors={model_info['sensor_count']} | sig={model_info['config_sig']}...{age_str}", component="MODEL")
                return cached_models, cached_manifest
            else:
                # Log retrain reasons in single message
                Console.warn(f"Cache invalid ({len(invalid_reasons)} reasons): {'; '.join(invalid_reasons[:3])}", component="MODEL",
                             equip=equip, invalid_reason_count=len(invalid_reasons))
                return None, None
        return None, None
    except Exception as e:
        Console.warn(f"Failed to load cached models: {e}", component="MODEL",
                     equip=equip, error_type=type(e).__name__, error=str(e)[:200])
        return None, None


def load_cached_raw_signal_medians(
    *,
    equip: str,
    sql_client: Optional[Any],
    equip_id: int,
    cfg: Dict[str, Any],
    input_columns: List[str],
    logger: Any = Console,
) -> Optional[Dict[str, float]]:
    """
    Load cached training-time raw signal medians for empty-train scoring paths.

    Unlike ``load_cached_models_with_validation()``, this loader validates
    against raw input columns rather than feature-space ``train_sensors``.
    """
    if sql_client is None:
        return None

    normalized_columns = [str(col) for col in input_columns if str(col).strip()]
    if not normalized_columns:
        return None

    try:
        model_manager = ModelVersionManager(
            equip=equip,
            sql_client=sql_client,
            equip_id=equip_id,
        )
        cached_models, cached_manifest = model_manager.load_models(model_types=["raw_signal_medians"])
        if not cached_models:
            return None

        raw_signal_medians = cached_models.get("raw_signal_medians")
        if raw_signal_medians is None:
            return None
        if hasattr(raw_signal_medians, "to_dict"):
            raw_signal_medians = raw_signal_medians.to_dict()
        if not isinstance(raw_signal_medians, dict):
            logger.info(
                "Cached raw signal medians are not usable - ignoring",
                component="MODEL",
                equip=equip,
            )
            return None

        current_config_sig = str(cfg.get("_signature", "unknown") or "unknown")
        cached_config_sig = str((cached_manifest or {}).get("config_signature", "") or "")
        if (
            current_config_sig
            and current_config_sig != "unknown"
            and cached_config_sig
            and cached_config_sig != current_config_sig
        ):
            logger.info(
                "Cached raw signal medians config signature mismatch - ignoring",
                component="MODEL",
                equip=equip,
            )
            return None

        missing = [col for col in normalized_columns if col not in raw_signal_medians]
        if missing:
            logger.info(
                f"Cached raw signal medians missing {len(missing)} current columns - ignoring",
                component="MODEL",
                equip=equip,
                missing_cols=len(missing),
            )
            return None

        return {
            col: float(raw_signal_medians[col])
            for col in normalized_columns
            if raw_signal_medians.get(col) is not None and not pd.isna(raw_signal_medians.get(col))
        }
    except Exception as e:
        logger.warn(
            f"Failed to load cached raw signal medians: {e}",
            component="MODEL",
            equip=equip,
            error_type=type(e).__name__,
            error=str(e)[:200],
        )
        return None


def load_cached_feature_medians(
    *,
    equip: str,
    sql_client: Optional[Any],
    equip_id: int,
    cfg: Dict[str, Any],
    feature_columns: List[str],
    logger: Any = Console,
) -> Optional[Dict[str, float]]:
    """Load cached feature-space medians aligned to the current feature columns."""
    normalized_columns = [str(col) for col in feature_columns if str(col).strip()]
    if not normalized_columns:
        return None

    cached_models, _ = load_cached_models_with_validation(
        equip=equip,
        sql_client=sql_client,
        equip_id=equip_id,
        cfg=cfg,
        train_columns=normalized_columns,
        model_types=["feature_medians"],
    )
    if not cached_models:
        return None

    feature_medians = cached_models.get("feature_medians")
    if feature_medians is None:
        return None
    if hasattr(feature_medians, "to_dict"):
        feature_medians = feature_medians.to_dict()
    if not isinstance(feature_medians, dict):
        logger.info(
            "Cached feature medians are not usable - ignoring",
            component="MODEL",
            equip=equip,
        )
        return None

    missing = [col for col in normalized_columns if col not in feature_medians]
    if missing:
        logger.info(
            f"Cached feature medians missing {len(missing)} feature columns - ignoring",
            component="MODEL",
            equip=equip,
            missing_cols=len(missing),
        )
        return None

    return {
        col: float(feature_medians[col])
        for col in normalized_columns
        if feature_medians.get(col) is not None and not pd.isna(feature_medians.get(col))
    }


def align_current_features_to_cached_manifest(
    train: pd.DataFrame,
    score: pd.DataFrame,
    cached_manifest: Optional[Dict[str, Any]],
    equip: str = "",
    logger: Any = Console,
) -> Tuple[pd.DataFrame, pd.DataFrame, List[str], bool]:
    """
    Align current feature matrices to cached manifest feature schema.

    Returns:
        (train_aligned, score_aligned, current_sensors, cache_compatible)
    """
    decision = classify_feature_schema_drift(list(train.columns), cached_manifest)

    if decision.operator_summary:
        logger.info(
            decision.operator_summary,
            component="MODEL",
            equip=equip,
            schema_compatibility=decision.schema_compatibility,
            missing_count=len(decision.missing_signals),
            new_count=len(decision.new_signals),
        )

    if decision.new_signals:
        logger.warn(
            f"Current data has {len(decision.new_signals)} features not in cache - cannot use cached models",
            component="MODEL",
            equip=equip,
            extra_features=list(decision.new_signals)[:5],
        )
    elif decision.missing_signals and decision.use_intersection:
        logger.warn(
            f"Using feature subset: {len(decision.missing_signals)} cached features missing in current data",
            component="MODEL",
            equip=equip,
            missing_features=list(decision.missing_signals)[:5],
        )

    return apply_feature_schema_alignment(train, score, decision)


def restore_detectors_from_runtime_cache(
    detector_cache: Optional[Dict[str, Any]],
    logger: Any = Console,
) -> Dict[str, Any]:
    """
    Restore detector instances from in-memory runtime cache payload.
    """
    result: Dict[str, Any] = {
        "ar1_detector": None,
        "pca_detector": None,
        "iforest_detector": None,
        "gmm_detector": None,
        "omr_detector": None,
        "regime_model": None,
        "cache_complete": False,
    }

    if not detector_cache:
        return result

    ar1_detector = detector_cache.get("ar1")
    pca_detector = detector_cache.get("pca")
    iforest_detector = detector_cache.get("iforest")
    gmm_detector = detector_cache.get("gmm")
    regime_model = detector_cache.get("regime_model")

    if regime_model is not None and detector_cache.get("regime_basis_hash"):
        # Preserve fit-time quality flags in model metadata; only attach basis hash.
        regime_model.train_hash = detector_cache["regime_basis_hash"]

    cache_complete = all([ar1_detector, pca_detector, iforest_detector])
    if not cache_complete:
        logger.warn("Cached detectors incomplete; will re-fit", component="MODEL")
        return result

    result["ar1_detector"] = ar1_detector
    result["pca_detector"] = pca_detector
    result["iforest_detector"] = iforest_detector
    result["gmm_detector"] = gmm_detector
    result["regime_model"] = regime_model
    result["cache_complete"] = True
    return result


def load_quality_regime_state_if_needed(
    regime_model: Optional[Any],
    equip: str,
    equip_id: int,
    sql_client: Any,
    logger: Any = Console,
) -> Tuple[Optional[RegimeState], int, bool]:
    """
    Load regime state from SQL when no regime model is currently available.
    """
    if regime_model is not None:
        return None, 0, False

    regime_state = load_regime_state(equip=equip, equip_id=equip_id, sql_client=sql_client)
    if regime_state is not None and regime_state.quality_ok:
        regime_state_version = regime_state.state_version
        logger.info(
            f"Regime loaded from state_v{regime_state_version} | K={regime_state.n_clusters}",
            component="REGIME",
        )
        return regime_state, regime_state_version, True

    return regime_state, 0, False


def save_trained_models(
    equip: str,
    sql_client: Optional[Any],
    equip_id: int,
    cfg: Dict[str, Any],
    train: "pd.DataFrame",
    ar1_detector: Any,
    pca_detector: Any,
    iforest_detector: Any,
    gmm_detector: Any,
    omr_detector: Any,
    regime_model: Any,
    col_meds: Optional[Dict[str, float]],
    regime_quality_ok: bool,
    timing_sections: Optional[Dict[str, Any]] = None,
    run_id: str = "",
    calibrators_dict: Optional[Dict[str, Any]] = None,
    raw_signal_medians: Optional[Dict[str, float]] = None,
) -> Optional[int]:
    """Save all trained models with versioning and metadata.
    
    High-level wrapper around ModelVersionManager that:
    - Collects all detector models into save dict
    - Computes training duration from timing sections
    - Creates metadata with quality metrics
    - Persists to SQL
    
    Args:
        equip: Equipment name
        sql_client: SQL client connection
        equip_id: Equipment ID
        cfg: Configuration dictionary
        train: Training DataFrame
        ar1_detector: Fitted AR1 detector
        pca_detector: Fitted PCA detector
        iforest_detector: Fitted IForest detector
        gmm_detector: Fitted GMM detector
        omr_detector: Fitted OMR detector
        regime_model: Fitted regime model
        col_meds: Feature medians for imputation
        raw_signal_medians: Raw training-signal medians for score-only feature prep
        regime_quality_ok: Whether regime quality passed threshold
        timing_sections: Optional timing dict with fit section durations
        run_id: Current run identifier
    
    Returns:
        Model version number if successful, None on failure.
    """
    try:
        model_manager = ModelVersionManager(
            equip=equip,
            sql_client=sql_client,
            equip_id=equip_id
        )
        
        # Collect all models for persistence
        # v11.6.1 FIX: Save the FULL RegimeModel object, not just regime_model.model
        # RegimeModel contains feature_columns, scaler, etc. which are needed for scoring
        models_to_save = {
            "ar1_params": {"phimap": ar1_detector.phimap, "sdmap": ar1_detector.sdmap} if hasattr(ar1_detector, 'phimap') else None,
            # v11.7.1 FIX: Save full PCA detector state (includes keep_cols, scaler, col_medians)
            # so that scoring batches can properly filter to the same columns PCA was trained on.
            # Previously only pca_detector.pca was saved, losing keep_cols and causing
            # n_features_in_ vs current_columns mismatch on reload.
            "pca_model": {
                "pca": pca_detector.pca,
                "keep_cols": getattr(pca_detector, 'keep_cols', []),
                "scaler": getattr(pca_detector, 'scaler', None),
                "col_medians": getattr(pca_detector, 'col_medians', None),
            } if hasattr(pca_detector, 'pca') and pca_detector.pca is not None else (
                pca_detector.pca if hasattr(pca_detector, 'pca') else None
            ),
            "iforest_model": iforest_detector.model if hasattr(iforest_detector, 'model') else None,
            # v11.7.1 FIX: Save full GMM detector state (includes _var_mask, _columns_, scaler)
            # so that scoring batches can properly apply the same variance mask.
            # Previously only gmm_detector.model was saved, losing _var_mask and causing
            # score() to return all zeros on reload.
            "gmm_model": {
                "model": gmm_detector.model,
                "_var_mask": getattr(gmm_detector, '_var_mask', None),
                "_columns_": getattr(gmm_detector, '_columns_', None),
                "scaler": getattr(gmm_detector, 'scaler', None),
                "_score_mu_": getattr(gmm_detector, '_score_mu_', None),
                "_score_sd_": getattr(gmm_detector, '_score_sd_', None),
            } if hasattr(gmm_detector, 'model') and gmm_detector.model is not None else (
                gmm_detector.model if hasattr(gmm_detector, 'model') else None
            ),
            "omr_model": omr_detector.to_dict() if omr_detector and omr_detector._is_fitted else None,
            "regime_model": regime_model,  # Full RegimeModel object, not just .model
            "feature_medians": col_meds,
            "raw_signal_medians": raw_signal_medians,
            # v11.9.0: Persist calibration params so scoring batches reuse training-time normalization
            "calibration_params": {
                name: cal.to_dict() for name, cal in calibrators_dict.items()
            } if calibrators_dict else None,
        }
        
        # Calculate training duration from timing sections
        training_duration_s = None
        if timing_sections:
            try:
                fit_sections = ["fit.ar1", "fit.pca_subspace", "fit.iforest", "fit.gmm", "fit.omr", "regimes.fit"]
                total_fit_time = sum([timing_sections.get(sec, {}).get("elapsed", 0.0) for sec in fit_sections])
                if total_fit_time > 0:
                    training_duration_s = total_fit_time
            except Exception:
                pass
        
        # Create metadata
        regime_quality_metrics = {
            "quality_ok": regime_quality_ok,
            "n_regimes": regime_model.n_clusters if regime_model else 0
        }
        
        metadata = create_model_metadata(
            config_signature=cfg.get("_signature", "unknown"),
            train_data=train,
            models_dict=models_to_save,
            regime_quality=regime_quality_metrics,
            training_duration_s=training_duration_s
        )
        
        # Save models
        model_version = model_manager.save_models(
            models=models_to_save,
            metadata=metadata
        )
        
        Console.info(f"Saved all trained models to version v{model_version}", component="MODEL")
        return model_version
        
    except Exception as e:
        import traceback
        Console.warn(f"Failed to save models: {e}", component="MODEL",
                     equip=equip, run_id=run_id, error_type=type(e).__name__, error=str(e)[:500])
        traceback.print_exc()
        return None


def run_model_persistence_and_lifecycle_stage(
    *,
    cached_models: Optional[Dict[str, Any]],
    detector_cache: Optional[Dict[str, Any]],
    force_retrain: bool,
    equip: str,
    sql_client: Optional[Any],
    equip_id: int,
    cfg: Dict[str, Any],
    train: "pd.DataFrame",
    ar1_detector: Any,
    pca_detector: Any,
    iforest_detector: Any,
    gmm_detector: Any,
    omr_detector: Any,
    regime_model: Any,
    col_meds: Optional[Dict[str, float]],
    regime_quality_ok: bool,
    timing_sections: Optional[Dict[str, Any]],
    run_id: Optional[str],
    model_state: Optional[Any],
    output_manager: Any,
    regime_state_version: int,
    score_out: Dict[str, Any],
    update_and_persist_model_lifecycle_fn: Optional[Any] = None,
    load_model_state_safe_fn: Optional[Any] = None,
    logger: Any = Console,
    save_trained_models_fn: Any = save_trained_models,
    raw_signal_medians: Optional[Dict[str, float]] = None,
    baseline_contamination_verdict: str = "unknown",
) -> "ModelPersistenceStageResult":
    """
    Persist trained models and update lifecycle state for the current run.
    """
    update_lifecycle_fn = update_and_persist_model_lifecycle_fn
    if update_lifecycle_fn is None:
        from core.model_lifecycle import update_and_persist_model_lifecycle_safe as update_lifecycle_fn

    load_state_fn = load_model_state_safe_fn
    if load_state_fn is None:
        from core.model_lifecycle import load_model_state_safe as load_state_fn

    detectors_fitted_this_run = (not cached_models and detector_cache is None) or force_retrain
    models_were_trained = bool(detectors_fitted_this_run)
    saved_model_version = None
    model_state_out = model_state

    if models_were_trained:
        saved_model_version = save_trained_models_fn(
            equip=equip,
            sql_client=sql_client,
            equip_id=equip_id,
            cfg=cfg,
            train=train,
            ar1_detector=ar1_detector,
            pca_detector=pca_detector,
            iforest_detector=iforest_detector,
            gmm_detector=gmm_detector,
            omr_detector=omr_detector,
            regime_model=regime_model,
            col_meds=col_meds,
            raw_signal_medians=raw_signal_medians,
            regime_quality_ok=regime_quality_ok,
            timing_sections=timing_sections,
            run_id=run_id or "",
        )
        model_state_out = update_lifecycle_fn(
            sql_client=sql_client,
            output_manager=output_manager,
            equip_id=int(equip_id),
            regime_state_version=regime_state_version,
            cfg=cfg,
            train_data=train,
            run_id=run_id,
            regime_model=regime_model,
            score_out=score_out,
            regime_quality_ok=regime_quality_ok,
            logger=logger,
            baseline_contamination_verdict=baseline_contamination_verdict,
        )

    if model_state_out is None:
        model_state_out = load_state_fn(
            sql_client=sql_client,
            equip_id=int(equip_id),
            logger=logger,
        )

    return ModelPersistenceStageResult(
        detectors_fitted_this_run=detectors_fitted_this_run,
        models_were_trained=models_were_trained,
        saved_model_version=saved_model_version,
        model_state=model_state_out,
    )


@dataclass
class ModelPersistenceStageResult:
    """Typed result payload for model persistence stage."""
    detectors_fitted_this_run: bool
    models_were_trained: bool
    saved_model_version: Optional[int]
    model_state: Optional[Any]


@dataclass
class ModelAdaptationPersistenceResult:
    """Typed result payload for combined auto-retrain and persistence stages."""
    force_retrain: bool
    cached_models: Optional[Dict[str, Any]]
    regime_model: Any
    detectors: Dict[str, Any]
    saved_model_version: Optional[int]
    model_state: Optional[Any]


def run_model_adaptation_and_persistence_stage(
    *,
    section_fn: Any,
    cfg: Dict[str, Any],
    cached_models: Optional[Dict[str, Any]],
    cached_manifest: Optional[Dict[str, Any]],
    detectors_just_trained: bool,
    score_out: Dict[str, Any],
    regime_quality_ok: bool,
    current_model_maturity: Optional[str],
    boolean_only_metrics: List[str],
    equip: str,
    logger: Any,
    record_model_refit_fn: Any,
    fit_all_detectors_fn: Any,
    train: "pd.DataFrame",
    det_flags: Dict[str, bool],
    output_manager: Any,
    sql_client: Any,
    run_id: Optional[str],
    equip_id: int,
    regime_model: Any,
    detectors: Dict[str, Any],
    detector_cache: Optional[Dict[str, Any]],
    col_meds: Optional[Dict[str, float]],
    timing_sections: Optional[Dict[str, Any]],
    model_state: Optional[Any],
    regime_state_version: int,
    run_auto_retrain_stage_fn: Optional[Any] = None,
    run_model_persistence_and_lifecycle_stage_fn: Optional[Any] = None,
    update_and_persist_model_lifecycle_fn: Optional[Any] = None,
    load_model_state_safe_fn: Optional[Any] = None,
    force_retrain_requested: bool = False,
    raw_signal_medians: Optional[Dict[str, float]] = None,
    baseline_contamination_verdict: str = "unknown",
) -> ModelAdaptationPersistenceResult:
    """
    Execute auto-retrain decision and model persistence/lifecycle stages.
    """
    auto_retrain_stage_fn = run_auto_retrain_stage_fn
    if auto_retrain_stage_fn is None:
        from core.model_evaluation import run_auto_retrain_stage as auto_retrain_stage_fn

    persistence_stage_fn = run_model_persistence_and_lifecycle_stage_fn or run_model_persistence_and_lifecycle_stage

    with section_fn("models.auto_retrain"):
        retrain_out = auto_retrain_stage_fn(
            cfg=cfg,
            cached_models=cached_models,
            cached_manifest=cached_manifest,
            detectors_just_trained=detectors_just_trained,
            score_out=score_out,
            regime_quality_ok=regime_quality_ok,
            current_model_maturity=current_model_maturity,
            boolean_only_metrics=list(boolean_only_metrics),
            equip=equip,
            logger=logger,
            record_model_refit_fn=record_model_refit_fn,
            fit_all_detectors_fn=fit_all_detectors_fn,
            train=train,
            det_flags=det_flags,
            output_manager=output_manager,
            sql_client=sql_client,
            run_id=run_id,
            equip_id=equip_id,
            regime_model=regime_model,
            detectors=detectors,
            force_retrain_requested=force_retrain_requested,
        )

    force_retrain = bool(retrain_out.force_retrain)
    cached_models_out = retrain_out.cached_models
    regime_model_out = retrain_out.regime_model
    detectors_out = retrain_out.detectors

    with section_fn("models.persistence.save"):
        persistence_out = persistence_stage_fn(
            cached_models=cached_models_out,
            detector_cache=detector_cache,
            force_retrain=force_retrain,
            equip=equip,
            sql_client=sql_client,
            equip_id=equip_id,
            cfg=cfg,
            train=train,
            ar1_detector=detectors_out["ar1_detector"],
            pca_detector=detectors_out["pca_detector"],
            iforest_detector=detectors_out["iforest_detector"],
            gmm_detector=detectors_out["gmm_detector"],
            omr_detector=detectors_out["omr_detector"],
            regime_model=regime_model_out,
            col_meds=col_meds,
            raw_signal_medians=raw_signal_medians,
            regime_quality_ok=regime_quality_ok,
            timing_sections=timing_sections,
            run_id=run_id,
            model_state=model_state,
            output_manager=output_manager,
            regime_state_version=regime_state_version,
            score_out=score_out,
            update_and_persist_model_lifecycle_fn=update_and_persist_model_lifecycle_fn,
            load_model_state_safe_fn=load_model_state_safe_fn,
            logger=logger,
            baseline_contamination_verdict=baseline_contamination_verdict,
        )

    return ModelAdaptationPersistenceResult(
        force_retrain=force_retrain,
        cached_models=cached_models_out,
        regime_model=regime_model_out,
        detectors=detectors_out,
        saved_model_version=persistence_out.saved_model_version,
        model_state=persistence_out.model_state,
    )


def persist_calibration_params_safe(
    saved_model_version: Optional[int],
    calibrators_dict: Optional[Dict[str, Any]],
    equip: str,
    sql_client: Optional[Any],
    equip_id: int,
    logger: Any = Console,
) -> bool:
    """
    Persist calibration parameters for cross-batch consistency.

    Returns:
        True when persistence succeeds, otherwise False.
    """
    if saved_model_version is None or not calibrators_dict:
        return False

    try:
        cal_manager = ModelVersionManager(equip=equip, sql_client=sql_client, equip_id=equip_id)
        cal_manager.save_calibration_params(calibrators_dict, version=saved_model_version)
        return True
    except Exception as e:
        logger.warn(
            f"Failed to persist calibration params: {e}",
            component="CAL",
            equip=equip,
            error=str(e)[:200],
        )
        return False


def load_manifest_protected_columns(
    *,
    sql_client: Any,
    equip: str,
    equip_id: int,
    cfg: Dict[str, Any],
    is_coldstart_run: bool,
    logger: Any = Console,
) -> Optional[List[str]]:
    """
    Load protected feature columns from latest cached model manifest when cache is enabled.
    """
    if is_coldstart_run:
        return None

    manifest = load_cached_manifest_only(
        sql_client=sql_client,
        equip=equip,
        equip_id=equip_id,
        cfg=cfg,
        logger=logger,
    )
    if not manifest:
        return None
    protected = manifest.get("train_sensors") or None
    if protected:
        logger.info(
            f"Feature protection: {len(protected)} columns from cached model manifest will not be dropped by low-var filter",
            component="FEAT",
            equip=equip,
        )
    return protected


def load_cached_manifest_only(
    *,
    sql_client: Any,
    equip: str,
    equip_id: int,
    cfg: Dict[str, Any],
    logger: Any = Console,
) -> Optional[Dict[str, Any]]:
    """Load only the latest cached model manifest using the shared SQL owner."""
    use_cache = bool(cfg.get("models", {}).get("use_cache", True))
    if not use_cache or sql_client is None:
        return None

    try:
        manager = ModelVersionManager(
            equip=equip,
            sql_client=sql_client,
            equip_id=equip_id,
        )
        return manager.load_manifest_only()
    except Exception as e:
        logger.warn(
            f"Cheap manifest load failed (non-fatal): {e}",
            component="FEAT",
            equip=equip,
        )
        return None

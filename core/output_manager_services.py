"""
Operational service functions extracted from OutputManager.
"""

from __future__ import annotations

import gc
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
import json

from core.observability import Console
from core.sensor_attribution import build_contribution_timeline


def _trend_from_recent(values: List[float]) -> str:
    """Compute coarse trend using first-half vs second-half averages."""
    if len(values) < 3:
        return "unknown"
    mid = len(values) // 2
    if mid <= 0 or (len(values) - mid) <= 0:
        return "unknown"
    first_avg = sum(values[:mid]) / mid
    second_avg = sum(values[mid:]) / (len(values) - mid)
    if second_avg > first_avg * 1.1:
        return "increasing"
    if second_avg < first_avg * 0.9:
        return "decreasing"
    return "stable"


def _write_optional_contract_table(
    output_manager: Any,
    table_name: str,
    df: Optional[pd.DataFrame],
    artifact_name: str,
) -> int:
    """Best-effort contract-driven write helper for optional artifacts."""
    if not output_manager._can_write_dataframe(df):
        return 0
    result = output_manager.write_sql_table(
        table_name=table_name,
        df=df,
        artifact_name=artifact_name,
        required=False,
    )
    return int(result.get("inserted", 0))


def load_omr_drift_context_service(output_manager: Any, equip_id: int, lookback_hours: int = 24) -> dict:
    """Load OMR and drift context from recent SQL outputs."""
    _ = lookback_hours  # kept for API compatibility
    result = {
        "omr_z": None,
        "omr_trend": "unknown",
        "top_contributors": [],
        "drift_z": None,
        "drift_trend": "unknown",
    }
    if output_manager.sql_client is None:
        return result

    try:
        with output_manager.sql_client.cursor() as cursor:
            cursor.execute(
                """
                SELECT TOP 1 fused
                FROM ACM_Scores_Wide
                WHERE EquipID = ? AND fused IS NOT NULL
                ORDER BY Timestamp DESC
                """,
                (equip_id,),
            )
            row = cursor.fetchone()
            if row:
                result["omr_z"] = float(row[0]) if row[0] is not None else None

            cursor.execute(
                """
                SELECT fused
                FROM (
                    SELECT TOP 10 fused, Timestamp
                    FROM ACM_Scores_Wide
                    WHERE EquipID = ? AND fused IS NOT NULL
                    ORDER BY Timestamp DESC
                ) sub
                ORDER BY Timestamp ASC
                """,
                (equip_id,),
            )
            omr_values = [float(r[0]) for r in cursor.fetchall() if r[0] is not None]
            result["omr_trend"] = _trend_from_recent(omr_values)

            cursor.execute(
                """
                SELECT TOP 3 SensorName
                FROM ACM_SensorHotspots
                WHERE EquipID = ?
                ORDER BY MaxAbsZ DESC
                """,
                (equip_id,),
            )
            result["top_contributors"] = [r[0] for r in cursor.fetchall() if r[0]]

            cursor.execute(
                """
                SELECT TOP 1 DriftValue
                FROM ACM_DriftSeries
                WHERE EquipID = ?
                ORDER BY Timestamp DESC
                """,
                (equip_id,),
            )
            row = cursor.fetchone()
            if row:
                result["drift_z"] = float(row[0]) if row[0] is not None else None

            cursor.execute(
                """
                SELECT DriftValue
                FROM (
                    SELECT TOP 10 DriftValue, Timestamp
                    FROM ACM_DriftSeries
                    WHERE EquipID = ?
                    ORDER BY Timestamp DESC
                ) sub
                ORDER BY Timestamp ASC
                """,
                (equip_id,),
            )
            drift_values = [float(r[0]) for r in cursor.fetchall() if r[0] is not None]
            result["drift_trend"] = _trend_from_recent(drift_values)
    except Exception as e:
        Console.debug(f"load_omr_drift_context failed: {e}", component="OUTPUT", error=str(e)[:200])

    return result


def write_refit_request_service(
    output_manager: Any,
    reasons: List[str],
    anomaly_rate: Optional[float] = None,
    drift_score: Optional[float] = None,
    regime_quality: Optional[float] = None,
) -> int:
    """Write a model-refit request to ACM_RefitRequests."""
    if output_manager.sql_client is None:
        return 0
    try:
        df = pd.DataFrame(
            [
                {
                    "EquipID": int(output_manager.equip_id or 0),
                    "RequestedAt": datetime.now(),
                    "Reason": "; ".join(reasons) if reasons else None,
                    "AnomalyRate": float(anomaly_rate) if anomaly_rate is not None else None,
                    "DriftScore": float(drift_score) if drift_score is not None else None,
                    "RegimeQuality": float(regime_quality) if regime_quality is not None else None,
                    "Acknowledged": 0,
                }
            ]
        )
        result = output_manager.write_sql_table(
            table_name="ACM_RefitRequests",
            df=df,
            artifact_name="refit_request",
            required=False,
        )
        return int(result.get("inserted", 0))
    except Exception as e:
        Console.warn(f"write_refit_request failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_fusion_metrics_service(
    output_manager: Any,
    fusion_weights: Dict[str, float],
    tuning_diagnostics: Dict[str, Any],
    previous_weights: Optional[Dict[str, float]] = None,
) -> int:
    """Write fusion metrics to ACM_RunMetrics in EAV form."""
    if not output_manager._can_write_payload(tuning_diagnostics):
        return 0
    try:
        tuning_diagnostics["timestamp"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        tuning_diagnostics["warm_started"] = previous_weights is not None
        if previous_weights:
            tuning_diagnostics["previous_weights"] = previous_weights

        metrics_rows = []
        for detector_name, weight in fusion_weights.items():
            det_metrics = tuning_diagnostics.get("detector_metrics", {}).get(detector_name, {})
            metrics_rows.append(
                {
                    "detector_name": detector_name,
                    "weight": weight,
                    "n_samples": det_metrics.get("n_samples", 0),
                    "quality_score": det_metrics.get("quality_score", 0.0),
                }
            )
        if not metrics_rows:
            return 0

        now_ts = pd.Timestamp.now()
        metric_records = [
            {
                "RunID": output_manager.run_id,
                "EquipID": int(output_manager.equip_id or 0),
                "MetricName": f"fusion.weight.{row['detector_name']}",
                "MetricValue": float(row["weight"]),
                "CreatedAt": now_ts,
            }
            for row in metrics_rows
        ] + [
            {
                "RunID": output_manager.run_id,
                "EquipID": int(output_manager.equip_id or 0),
                "MetricName": f"fusion.quality.{row['detector_name']}",
                "MetricValue": float(row["quality_score"]),
                "CreatedAt": now_ts,
            }
            for row in metrics_rows
        ] + [
            {
                "RunID": output_manager.run_id,
                "EquipID": int(output_manager.equip_id or 0),
                "MetricName": f"fusion.n_samples.{row['detector_name']}",
                "MetricValue": float(row["n_samples"]),
                "CreatedAt": now_ts,
            }
            for row in metrics_rows
        ]

        result = output_manager.write_sql_table(
            table_name="ACM_RunMetrics",
            df=pd.DataFrame(metric_records),
            artifact_name="fusion_metrics",
            required=False,
        )
        return int(result.get("inserted", 0))
    except Exception as e:
        Console.warn(
            f"write_fusion_metrics failed: {e}",
            component="OUTPUT",
            equip=getattr(output_manager, "equipment", ""),
            error=str(e)[:200],
        )
        return 0


def check_refit_request_service(output_manager: Any) -> bool:
    """Check and acknowledge pending refit request for the current equipment."""
    if output_manager.sql_client is None:
        return False
    try:
        with output_manager.sql_client.cursor() as cur:
            cur.execute(
                """
                IF OBJECT_ID(N'[dbo].[ACM_RefitRequests]', N'U') IS NOT NULL
                BEGIN
                    SELECT TOP 1 RequestID, RequestedAt, Reason
                    FROM [dbo].[ACM_RefitRequests]
                    WHERE EquipID = ? AND Acknowledged = 0
                    ORDER BY RequestedAt DESC
                END
                """,
                (int(output_manager.equip_id),),
            )
            row = cur.fetchone()
            if row:
                Console.info(
                    f"Pending model refit request found (id={row[0]}, requested at {row[1]}). "
                    "Acknowledging and triggering refit this batch.",
                    component="MODEL",
                    equip=output_manager.equipment,
                    refit_request_id=row[0],
                )
                cur.execute(
                    "UPDATE [dbo].[ACM_RefitRequests] "
                    "SET Acknowledged = 1, AcknowledgedAt = SYSDATETIME() "
                    "WHERE RequestID = ?",
                    (int(row[0]),),
                )
                output_manager._commit_if_needed("ACM_RefitRequests")
                return True
    except Exception as e:
        Console.warn(
            f"Refit check failed: {e}",
            component="MODEL",
            equip=output_manager.equipment,
            error_type=type(e).__name__,
            error=str(e)[:200],
        )
    return False


def update_baseline_buffer_service(
    output_manager: Any,
    score_numeric: pd.DataFrame,
    cfg: Dict[str, Any],
    coldstart_complete: bool,
) -> bool:
    """Update ACM_BaselineBuffer using periodic refresh policy."""
    if output_manager.sql_client is None:
        return False

    baseline_cfg = (cfg.get("runtime", {}) or {}).get("baseline", {}) or {}
    window_hours = float(baseline_cfg.get("window_hours", 72))
    max_points = int(baseline_cfg.get("max_points", 100000))
    refresh_interval = int(baseline_cfg.get("refresh_interval_batches", 10))

    should_write_buffer = False
    write_reason = ""
    recent_run_count = 0

    if not coldstart_complete:
        should_write_buffer = True
        write_reason = "coldstart"
    else:
        try:
            with output_manager.sql_client.cursor() as cur:
                run_count_result = cur.execute(
                    "SELECT COUNT(*) FROM ACM_Runs WHERE EquipID = ? AND CreatedAt > DATEADD(DAY, -7, GETDATE())",
                    (int(output_manager.equip_id),),
                ).fetchone()
                recent_run_count = run_count_result[0] if run_count_result else 0
                if recent_run_count == 0 or (recent_run_count % refresh_interval == 0):
                    should_write_buffer = True
                    write_reason = f"periodic_refresh (batch {recent_run_count})"
        except Exception:
            should_write_buffer = True
            write_reason = "fallback"

    if not should_write_buffer:
        batches_until_refresh = refresh_interval - (recent_run_count % refresh_interval) if refresh_interval > 0 else 0
        Console.info(
            f"Skipping buffer write (models exist, next refresh in {batches_until_refresh} batches)",
            component="BASELINE",
        )
        return False

    if len(score_numeric) == 0:
        return False

    to_append = output_manager._ensure_local_index(score_numeric.copy())
    try:
        to_append_reset = to_append.reset_index()
        ts_col = to_append_reset.columns[0]
        long_df = to_append_reset.melt(id_vars=[ts_col], var_name="SensorName", value_name="SensorValue")
        long_df = long_df.dropna(subset=["SensorValue"])
        long_df["EquipID"] = int(output_manager.equip_id)
        long_df["DataQuality"] = None
        long_df = output_manager._ensure_local_index(long_df.set_index(ts_col))
        long_df = long_df.reset_index().rename(columns={ts_col: "Timestamp"})
        long_df = long_df[["EquipID", "Timestamp", "SensorName", "SensorValue", "DataQuality"]]
        if len(long_df) <= 0:
            return False

        insert_result = output_manager.write_sql_table(
            table_name="ACM_BaselineBuffer",
            df=long_df,
            artifact_name="baseline_buffer",
            required=False,
        )
        inserted_rows = int(insert_result.get("inserted", 0))
        if inserted_rows <= 0:
            return False

        Console.info(
            f"SQL insert to ACM_BaselineBuffer: {inserted_rows} rows ({write_reason})",
            component="OUTPUT",
        )

        try:
            with output_manager.sql_client.cursor() as cur:
                cur.execute(
                    "EXEC dbo.usp_CleanupBaselineBuffer @EquipID=?, @RetentionHours=?, @MaxRowsPerEquip=?",
                    (int(output_manager.equip_id), int(window_hours), max_points),
                )
            output_manager._commit_if_needed("ACM_BaselineBuffer")
        except Exception as cleanup_err:
            Console.warn(
                f"Cleanup procedure failed: {cleanup_err}",
                component="BASELINE",
                equip=output_manager.equipment,
                equip_id=output_manager.equip_id,
                error=str(cleanup_err)[:200],
            )
        return True
    except Exception as sql_err:
        Console.warn(
            f"SQL write to ACM_BaselineBuffer failed: {sql_err}",
            component="BASELINE",
            equip=output_manager.equipment,
            equip_id=output_manager.equip_id,
            error=str(sql_err)[:200],
        )
        output_manager._rollback_if_needed("ACM_BaselineBuffer")
        return False


def write_sensor_normalized_ts_service(
    output_manager: Any,
    scores_df: pd.DataFrame,
    sensor_cols: Optional[List[str]] = None,
) -> int:
    """Write normalized sensor time series to ACM_SensorNormalized_TS."""
    if not output_manager._can_write_dataframe(scores_df):
        return 0
    try:
        df = scores_df.copy()
        if "Timestamp" not in df.columns:
            if isinstance(df.index, pd.DatetimeIndex) or df.index.name in ("Timestamp", "EntryDateTime"):
                df = df.reset_index()
                if "EntryDateTime" in df.columns:
                    df["Timestamp"] = df["EntryDateTime"]
                elif df.columns[0] != "Timestamp" and pd.api.types.is_datetime64_any_dtype(df[df.columns[0]]):
                    df["Timestamp"] = df.iloc[:, 0]
            elif "EntryDateTime" in df.columns:
                df["Timestamp"] = df["EntryDateTime"]
            else:
                dt_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
                if dt_cols:
                    df["Timestamp"] = df[dt_cols[0]]
                else:
                    Console.warn("write_sensor_normalized_ts: No Timestamp column found", component="OUTPUT")
                    return 0

        if sensor_cols is None:
            exclude = {
                "Timestamp",
                "RunID",
                "EquipID",
                "regime_label",
                "fused",
                "health",
                "ar1_z",
                "pca_spe_z",
                "pca_t2_z",
                "iforest_z",
                "gmm_z",
                "omr_z",
                "mhal_z",
                "cusum_z",
                "drift_z",
                "hst_z",
                "river_hst_z",
            }
            sensor_cols = output_manager._get_numeric_sensor_columns(df, exclude=exclude)

        sensor_cols = [c for c in sensor_cols if c in df.columns]
        if not sensor_cols:
            Console.debug("write_sensor_normalized_ts: No sensor columns found", component="OUTPUT")
            return 0

        long_df = df[["Timestamp"] + sensor_cols].melt(
            id_vars=["Timestamp"],
            value_vars=sensor_cols,
            var_name="SensorName",
            value_name="NormalizedValue",
        )
        long_df = long_df.dropna(subset=["NormalizedValue"])
        if long_df.empty:
            return 0

        long_df["RunID"] = output_manager.run_id or ""
        long_df["EquipID"] = output_manager.equip_id or 0
        long_df["RawValue"] = None
        long_df = long_df[["RunID", "EquipID", "Timestamp", "SensorName", "RawValue", "NormalizedValue"]]

        min_ts = long_df["Timestamp"].min()
        max_ts = long_df["Timestamp"].max()
        if pd.notna(min_ts) and pd.notna(max_ts) and output_manager.sql_client and output_manager.equip_id:
            try:
                with output_manager.sql_client.cursor() as cur:
                    cur.execute(
                        "DELETE FROM dbo.[ACM_SensorNormalized_TS] "
                        "WHERE EquipID = ? AND Timestamp BETWEEN ? AND ?",
                        (int(output_manager.equip_id), min_ts, max_ts),
                    )
                    deleted = cur.rowcount
                    if deleted > 0:
                        Console.info(
                            f"Deleted {deleted} overlapping rows from ACM_SensorNormalized_TS",
                            component="OUTPUT",
                            table="ACM_SensorNormalized_TS",
                            equip_id=output_manager.equip_id,
                            min_ts=str(min_ts),
                            max_ts=str(max_ts),
                        )
                output_manager._commit_if_needed("ACM_SensorNormalized_TS")
            except Exception as del_ex:
                Console.warn(
                    f"Failed to delete overlapping sensor data: {del_ex}",
                    component="OUTPUT",
                    table="ACM_SensorNormalized_TS",
                    equip_id=output_manager.equip_id,
                    error_type=type(del_ex).__name__,
                )

        result = output_manager.write_sql_table(
            table_name="ACM_SensorNormalized_TS",
            df=long_df,
            artifact_name="sensor_normalized_ts",
            required=False,
        )
        return int(result.get("inserted", 0))
    except Exception as e:
        Console.warn(
            f"write_sensor_normalized_ts failed: {e}",
            component="OUTPUT",
            error=str(e)[:200],
            sensor_count=len(sensor_cols) if sensor_cols else 0,
        )
        return 0


def write_sensor_correlations_service(
    output_manager: Any,
    corr_matrix: pd.DataFrame,
    corr_type: str = "pearson",
) -> int:
    """Write sensor correlation matrix to ACM_SensorCorrelations."""
    if not output_manager._can_write_dataframe(corr_matrix):
        return 0
    try:
        sensors = list(corr_matrix.columns)
        n = len(sensors)
        mask = np.triu(np.ones((n, n), dtype=bool))
        rows_idx, cols_idx = np.where(mask)
        corr_values = corr_matrix.values[rows_idx, cols_idx]

        df = pd.DataFrame(
            {
                "RunID": output_manager.run_id,
                "EquipID": output_manager.equip_id or 0,
                "Sensor1": [sensors[i] for i in rows_idx],
                "Sensor2": [sensors[j] for j in cols_idx],
                "Correlation": corr_values,
                "CorrelationType": corr_type,
            }
        )
        df = df.dropna(subset=["Correlation"])
        if df.empty:
            return 0

        try:
            with output_manager.sql_client.cursor() as cur:
                cur.execute(
                    "DELETE FROM dbo.[ACM_SensorCorrelations] WHERE EquipID = ?",
                    (int(output_manager.equip_id or 0),),
                )
            output_manager._commit_if_needed("ACM_SensorCorrelations")
        except Exception as del_ex:
            Console.debug(f"ACM_SensorCorrelations cleanup skipped: {del_ex}", component="OUTPUT")

        result = output_manager.write_sql_table(
            table_name="ACM_SensorCorrelations",
            df=df,
            artifact_name="sensor_correlations",
            required=False,
        )
        return int(result.get("inserted", 0))
    except Exception as e:
        Console.warn(f"write_sensor_correlations failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_sensor_correlations_from_raw_service(output_manager: Any, raw_score: Optional[pd.DataFrame]) -> int:
    """Build and persist sensor correlation matrix from raw sensor frame."""
    if raw_score is None or not hasattr(raw_score, "corr") or raw_score.shape[1] < 2:
        return 0
    try:
        sensor_cols = output_manager._get_numeric_sensor_columns(raw_score)
        if len(sensor_cols) < 2:
            return 0
        sensor_cols_with_variance = output_manager._filter_low_variance_columns(
            raw_score,
            sensor_cols,
            min_variance=1e-10,
        )
        if len(sensor_cols_with_variance) < 2:
            return 0

        sensor_corr = raw_score[sensor_cols_with_variance].corr(method="pearson")
        return write_sensor_correlations_service(output_manager, sensor_corr, corr_type="pearson")
    except Exception:
        return 0


def write_anomaly_events_service(
    output_manager: Any,
    df_events: pd.DataFrame,
    run_id: str,
    confidence_enabled: bool = True,
) -> int:
    """Write anomaly events to ACM_Anomaly_Events."""
    if not output_manager._can_write_dataframe(df_events):
        return 0
    try:
        df = df_events.copy()
        df["RunID"] = run_id
        if "EquipID" not in df.columns:
            df["EquipID"] = int(output_manager.equip_id or 0)

        col_map = {
            "start_ts": "StartTime",
            "end_ts": "EndTime",
            "severity": "Severity",
            "Detector": "DetectorType",
            "Score": "PeakScore",
            "ContributorsJSON": "ContributorsJSON",
        }
        for old, new in col_map.items():
            if old in df.columns and new not in df.columns:
                df[new] = df[old]

        if confidence_enabled:
            try:
                maturity_state = getattr(output_manager, "maturity_state", "COLDSTART")
                start_col = "StartTime" if "StartTime" in df.columns else "start_ts"
                end_col = "EndTime" if "EndTime" in df.columns else "end_ts"

                if start_col in df.columns and end_col in df.columns:
                    start_times = pd.to_datetime(df[start_col], errors="coerce")
                    end_times = pd.to_datetime(df[end_col], errors="coerce")
                    duration_seconds = (end_times - start_times).dt.total_seconds().fillna(3600).values
                else:
                    duration_seconds = np.full(len(df), 3600.0)

                if "PeakScore" in df.columns:
                    peak_z = pd.to_numeric(df["PeakScore"], errors="coerce").fillna(3.0).values
                elif "Score" in df.columns:
                    peak_z = pd.to_numeric(df["Score"], errors="coerce").fillna(3.0).values
                else:
                    peak_z = np.full(len(df), 3.0)

                maturity_base = {
                    "COLDSTART": 0.4,
                    "LEARNING": 0.6,
                    "CONVERGED": 0.8,
                    "DEPRECATED": 0.65,
                }.get(maturity_state, 0.5)
                duration_conf = np.minimum(duration_seconds / 3600.0, 1.0) * 0.2
                peak_conf = np.minimum(np.abs(peak_z) / 8.0, 1.0) * 0.3
                raw_conf = maturity_base * 0.5 + duration_conf + peak_conf
                df["Confidence"] = np.round(np.clip(raw_conf, 0.2, 0.95), 3)
            except Exception as e:
                Console.warn(f"Failed to compute episode confidence: {e}", component="EPISODES")

        return _write_optional_contract_table(
            output_manager=output_manager,
            table_name="ACM_Anomaly_Events",
            df=df,
            artifact_name="anomaly_events",
        )
    except Exception as e:
        Console.warn(f"write_anomaly_events failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_regime_episodes_service(output_manager: Any, df_reg: pd.DataFrame, run_id: str) -> int:
    """Write regime episodes to ACM_Regime_Episodes."""
    if not output_manager._can_write_dataframe(df_reg):
        return 0
    try:
        df = df_reg.copy()
        df["RunID"] = run_id
        if "EquipID" not in df.columns:
            df["EquipID"] = int(output_manager.equip_id or 0)
        return _write_optional_contract_table(
            output_manager=output_manager,
            table_name="ACM_Regime_Episodes",
            df=df,
            artifact_name="regime_episodes",
        )
    except Exception as e:
        Console.warn(f"write_regime_episodes failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_pca_model_service(output_manager: Any, model_row: Dict[str, Any]) -> int:
    """Write PCA model metadata to ACM_PCA_Models."""
    if not output_manager._can_write_payload(model_row):
        return 0
    try:
        model_version_str = str(model_row.get("ModelVersion", "1"))
        version_token = model_version_str.lstrip("v").split(".")[0]
        model_version = int(version_token) if version_token.isdigit() else 1

        var_json = model_row.get("VarExplainedJSON", "[]")
        explained_var_ratio = None
        try:
            var_list = json.loads(var_json) if isinstance(var_json, str) else var_json
            explained_var_ratio = float(sum(var_list)) if var_list else None
        except (json.JSONDecodeError, TypeError, ValueError):
            explained_var_ratio = None

        try:
            n_components = int(model_row.get("NComponents", 0))
        except (TypeError, ValueError):
            n_components = 0

        row = {
            "RunID": output_manager.run_id,
            "EquipID": output_manager.equip_id or 0,
            "ModelVersion": model_version,
            "NComponents": n_components,
            "ExplainedVarianceRatio": explained_var_ratio,
            "TrainSamples": None,
            "TrainFeatures": None,
            "ScalerMeanJson": None,
            "ScalerScaleJson": model_row.get("ScalingSpecJSON"),
            "ComponentsJson": None,
        }
        return _write_optional_contract_table(
            output_manager=output_manager,
            table_name="ACM_PCA_Models",
            df=pd.DataFrame([row]),
            artifact_name="pca_model",
        )
    except Exception as e:
        Console.warn(f"write_pca_model failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_detector_correlation_service(
    output_manager: Any, detector_correlations: Dict[str, Dict[str, float]]
) -> int:
    """Write detector correlation matrix to ACM_DetectorCorrelation."""
    if not output_manager._can_write_payload(detector_correlations):
        return 0
    try:
        run_id = output_manager.run_id
        equip_id = output_manager.equip_id or 0
        rows = [
            {
                "RunID": run_id,
                "EquipID": equip_id,
                "Detector1": d1,
                "Detector2": d2,
                "Correlation": float(corr) if not pd.isna(corr) else 0.0,
            }
            for d1, correlations in detector_correlations.items()
            for d2, corr in correlations.items()
        ]
        if not rows:
            return 0
        return _write_optional_contract_table(
            output_manager=output_manager,
            table_name="ACM_DetectorCorrelation",
            df=pd.DataFrame(rows),
            artifact_name="detector_correlation",
        )
    except Exception as e:
        Console.warn(f"write_detector_correlation failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_detector_correlation_from_scores_service(output_manager: Any, scores_df: pd.DataFrame) -> int:
    """Build detector correlation matrix from score frame and persist it."""
    if scores_df is None or scores_df.empty:
        return 0
    try:
        z_cols = [c for c in scores_df.columns if c.endswith("_z") and c not in ["drift_z"]]
        if len(z_cols) < 2:
            return 0

        z_df = scores_df[z_cols].dropna(how="all")
        if len(z_df) <= 10:
            return 0

        z_variances = z_df.var()
        z_cols_with_variance = z_variances[z_variances > 1e-10].index.tolist()
        if len(z_cols_with_variance) < 2:
            return 0

        corr_matrix = z_df[z_cols_with_variance].corr(method="pearson")
        det_corr = {
            d1: {d2: corr_matrix.loc[d1, d2] for d2 in corr_matrix.columns}
            for d1 in corr_matrix.index
        }
        return write_detector_correlation_service(output_manager, det_corr)
    except Exception as e:
        Console.warn(
            f"write_detector_correlation_from_scores failed: {e}",
            component="OUTPUT",
            equip_id=output_manager.equip_id,
            run_id=output_manager.run_id,
            error_type=type(e).__name__,
            error=str(e)[:200],
        )
        return 0


def write_drift_series_service(output_manager: Any, drift_df: pd.DataFrame) -> int:
    """Write drift detection time series to ACM_DriftSeries."""
    if not output_manager._can_write_dataframe(drift_df):
        return 0
    try:
        df = drift_df.copy()
        df["RunID"] = output_manager.run_id
        df["EquipID"] = output_manager.equip_id or 0
        if "DriftZ" in df.columns and "DriftValue" not in df.columns:
            df["DriftValue"] = df["DriftZ"]
        return _write_optional_contract_table(
            output_manager=output_manager,
            table_name="ACM_DriftSeries",
            df=df,
            artifact_name="drift_series",
        )
    except Exception as e:
        Console.warn(f"write_drift_series failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_feature_drop_log_service(output_manager: Any, dropped_features: List[Dict[str, Any]]) -> int:
    """Write dropped features log to ACM_FeatureDropLog."""
    if not output_manager._can_write_payload(dropped_features):
        return 0
    try:
        df = pd.DataFrame(dropped_features)
        df["RunID"] = output_manager.run_id
        df["EquipID"] = output_manager.equip_id or 0
        return _write_optional_contract_table(
            output_manager=output_manager,
            table_name="ACM_FeatureDropLog",
            df=df,
            artifact_name="feature_drop_log",
        )
    except Exception as e:
        Console.warn(f"write_feature_drop_log failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_calibration_summary_service(output_manager: Any, calibration_data: List[Dict[str, Any]]) -> int:
    """Write detector calibration summary to ACM_CalibrationSummary."""
    if not output_manager._can_write_payload(calibration_data):
        return 0
    try:
        df = pd.DataFrame(calibration_data)
        df["RunID"] = output_manager.run_id
        df["EquipID"] = output_manager.equip_id or 0
        return _write_optional_contract_table(
            output_manager=output_manager,
            table_name="ACM_CalibrationSummary",
            df=df,
            artifact_name="calibration_summary",
        )
    except Exception as e:
        Console.warn(f"write_calibration_summary failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_regime_occupancy_service(output_manager: Any, occupancy_data: List[Dict[str, Any]]) -> int:
    """Write regime occupancy stats to ACM_RegimeOccupancy."""
    if not output_manager._can_write_payload(occupancy_data):
        return 0
    try:
        df = pd.DataFrame(occupancy_data)
        df["RunID"] = output_manager.run_id
        df["EquipID"] = output_manager.equip_id or 0
        return _write_optional_contract_table(
            output_manager=output_manager,
            table_name="ACM_RegimeOccupancy",
            df=df,
            artifact_name="regime_occupancy",
        )
    except Exception as e:
        Console.warn(f"write_regime_occupancy failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_regime_transitions_service(
    output_manager: Any, transition_matrix: Dict[str, Dict[str, int]]
) -> int:
    """Write regime transition matrix to ACM_RegimeTransitions."""
    if not output_manager._can_write_payload(transition_matrix):
        return 0
    try:
        run_id = output_manager.run_id
        equip_id = output_manager.equip_id or 0
        rows: List[Dict[str, Any]] = []
        for from_r, transitions in transition_matrix.items():
            total = float(sum(transitions.values()))
            for to_r, count in transitions.items():
                rows.append(
                    {
                        "RunID": run_id,
                        "EquipID": equip_id,
                        "FromRegime": str(from_r),
                        "ToRegime": str(to_r),
                        "TransitionCount": int(count),
                        "TransitionProbability": (float(count) / total) if total > 0 else 0.0,
                    }
                )
        if not rows:
            return 0
        return _write_optional_contract_table(
            output_manager=output_manager,
            table_name="ACM_RegimeTransitions",
            df=pd.DataFrame(rows),
            artifact_name="regime_transitions",
        )
    except Exception as e:
        Console.warn(f"write_regime_transitions failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_contribution_timeline_service(output_manager: Any, contributions_df: pd.DataFrame) -> int:
    """Write detector contribution timeline to ACM_ContributionTimeline."""
    if not output_manager._can_write_dataframe(contributions_df):
        return 0
    try:
        df = contributions_df.copy()
        df["RunID"] = output_manager.run_id
        df["EquipID"] = output_manager.equip_id or 0
        return _write_optional_contract_table(
            output_manager=output_manager,
            table_name="ACM_ContributionTimeline",
            df=df,
            artifact_name="contribution_timeline",
        )
    except Exception as e:
        Console.warn(f"write_contribution_timeline failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_contribution_timeline_from_frame_service(
    output_manager: Any,
    frame: pd.DataFrame,
    fusion_weights: Optional[Dict[str, float]],
    equip: str = "",
) -> int:
    """Build and persist detector contribution timeline from score frame."""
    if not fusion_weights:
        Console.warn(
            "ContributionTimeline skipped: detector fusion weights are empty. "
            "This table requires at least one active detector with a non-zero weight.",
            component="CONTRIB",
        )
        return 0
    try:
        # Normalize: ensure Timestamp is a column (frame index is a DatetimeIndex throughout the pipeline)
        if "Timestamp" not in frame.columns and isinstance(frame.index, pd.DatetimeIndex):
            frame = frame.reset_index().rename(columns={frame.index.name or "index": "Timestamp"})
        contrib_df = build_contribution_timeline(frame, fusion_weights)
        if not output_manager._is_non_empty_dataframe(contrib_df):
            Console.warn(
                "ContributionTimeline skipped: build_contribution_timeline() returned no rows. "
                "Check that the score frame contains valid detector z-score columns (ar1_z, pca_spe_z, etc.).",
                component="CONTRIB",
            )
            return 0
        return write_contribution_timeline_service(output_manager, contrib_df)
    except Exception as e:
        Console.warn(
            f"Contribution timeline write failed: {e}",
            component="CONTRIB",
            equip=equip,
            error=str(e)[:200],
        )
        return 0


def write_regime_promotion_log_service(output_manager: Any, promotions: List[Dict[str, Any]]) -> int:
    """Write regime maturity promotions to ACM_RegimePromotionLog."""
    if not output_manager._can_write_payload(promotions):
        return 0
    try:
        df = pd.DataFrame(promotions)
        df["RunID"] = output_manager.run_id
        df["EquipID"] = output_manager.equip_id or 0
        return _write_optional_contract_table(
            output_manager=output_manager,
            table_name="ACM_RegimePromotionLog",
            df=df,
            artifact_name="regime_promotion_log",
        )
    except Exception as e:
        Console.warn(f"write_regime_promotion_log failed: {e}", component="OUTPUT", error=str(e)[:200])
        return 0


def write_sensor_normalized_ts_from_raw_service(
    output_manager: Any,
    raw_score: Optional[pd.DataFrame],
    max_total_rows: int = 10000,
) -> int:
    """Sample raw frame and persist normalized sensor time-series rows."""
    if raw_score is None or len(raw_score) == 0:
        return 0
    sensor_cols = output_manager._get_numeric_sensor_columns(raw_score)
    if not sensor_cols:
        return 0

    max_timestamps = max(100, int(max_total_rows) // len(sensor_cols))
    sample_frame = raw_score
    if len(raw_score) > max_timestamps:
        step = max(1, len(raw_score) // max_timestamps)
        sample_frame = raw_score.iloc[::step]

    return output_manager.write_sensor_normalized_ts(sample_frame, sensor_cols)


def write_seasonal_patterns_from_detected_service(
    output_manager: Any,
    seasonal_patterns: Optional[Dict[str, List[Any]]],
) -> int:
    """Flatten detected seasonal patterns and persist them to SQL."""
    if not seasonal_patterns:
        return 0
    pattern_list: List[Dict[str, Any]] = []
    for sensor_name, patterns in seasonal_patterns.items():
        for pattern in patterns:
            if not hasattr(pattern, "to_dict"):
                continue
            pattern_dict = pattern.to_dict()
            pattern_dict["SensorName"] = sensor_name
            pattern_dict["PatternType"] = pattern_dict.pop("period_type", "DAILY")
            pattern_dict["PeriodHours"] = pattern_dict.pop("period_hours", 24.0)
            pattern_dict["Amplitude"] = pattern_dict.pop("amplitude", 0.0)
            pattern_dict["PhaseShift"] = pattern_dict.pop("phase_shift", 0.0)
            pattern_dict["Confidence"] = pattern_dict.pop("confidence", 0.5)
            pattern_dict.pop("sensor", None)
            pattern_list.append(pattern_dict)
    if not pattern_list:
        return 0
    return output_manager.write_seasonal_patterns(pattern_list)


def persist_additional_artifacts_service(
    output_manager: Any,
    scores_df: pd.DataFrame,
    raw_score: Optional[pd.DataFrame],
    seasonal_patterns: Optional[Dict[str, List[Any]]],
    max_total_rows: int = 10000,
) -> Dict[str, int]:
    """Persist optional secondary artifacts derived from current run data."""
    return {
        "detector_correlation_rows": int(output_manager.write_detector_correlation_from_scores(scores_df)),
        "sensor_correlation_rows": int(output_manager.write_sensor_correlations_from_raw(raw_score)),
        "sensor_normalized_ts_rows": int(
            output_manager.write_sensor_normalized_ts_from_raw(
                raw_score,
                max_total_rows=max_total_rows,
            )
        ),
        "seasonal_pattern_rows": int(output_manager.write_seasonal_patterns_from_detected(seasonal_patterns)),
    }


def generate_all_analytics_with_context_service(
    output_manager: Any,
    scores_df: pd.DataFrame,
    cfg: Dict[str, Any],
    sensor_context: Optional[Dict[str, Any]],
    fusion_weights_used: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Persist analytics tables after optional fusion-weight injection into cfg."""
    if fusion_weights_used:
        cfg.setdefault("fusion", {})["weights"] = dict(fusion_weights_used)
    return output_manager.generate_all_analytics_tables(
        scores_df=scores_df,
        cfg=cfg,
        sensor_context=sensor_context,
    )


def release_persist_memory_service(
    raw_train: Optional[pd.DataFrame],
    raw_score: Optional[pd.DataFrame],
    iforest_detector: Optional[Any] = None,
    omr_detector: Optional[Any] = None,
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """Free large persist-phase objects after SQL writes are complete."""
    raw_train = None
    raw_score = None

    if iforest_detector is not None and hasattr(iforest_detector, "model"):
        iforest_detector.model = None

    if omr_detector is not None and hasattr(omr_detector, "model"):
        omr_detector.model = None

    gc.collect()
    return raw_train, raw_score


def persist_pipeline_outputs_service(
    output_manager: Any,
    scores_df: pd.DataFrame,
    episodes_df: Optional[pd.DataFrame],
    raw_train: Optional[pd.DataFrame],
    raw_score: Optional[pd.DataFrame],
    iforest_detector: Optional[Any],
    omr_detector: Optional[Any],
    seasonal_patterns: Optional[Dict[str, List[Any]]],
    cfg: Dict[str, Any],
    sensor_context: Optional[Dict[str, Any]],
    fusion_weights_used: Optional[Dict[str, float]],
    record_episode_fn: Optional[Callable[..., Any]] = None,
    equip: Optional[str] = None,
    max_total_rows: int = 10000,
) -> Dict[str, Any]:
    """Persist core and optional run artifacts, then release persist-phase memory."""
    core = output_manager.persist_core_outputs(
        scores_df=scores_df,
        episodes_df=episodes_df,
    )
    if core.episode_count > 0 and record_episode_fn is not None and equip:
        record_episode_fn(equip, count=core.episode_count, severity="info")

    # Persist anomaly events to ACM_Anomaly_Events
    if episodes_df is not None and len(episodes_df) > 0:
        try:
            output_manager.write_anomaly_events(
                df_events=episodes_df,
                run_id=output_manager.run_id,
            )
        except Exception as e:
            Console.warn(f"Anomaly events write failed: {e}", component="OUTPUT", error=str(e)[:200])

    output_manager.write_contribution_timeline_from_frame(
        frame=scores_df,
        fusion_weights=fusion_weights_used,
        equip=equip or "",
    )

    output_manager.persist_additional_artifacts(
        scores_df=scores_df,
        raw_score=raw_score,
        seasonal_patterns=seasonal_patterns,
        max_total_rows=max_total_rows,
    )

    raw_train, raw_score = output_manager.release_persist_memory(
        raw_train=raw_train,
        raw_score=raw_score,
        iforest_detector=iforest_detector,
        omr_detector=omr_detector,
    )

    analytics_result = output_manager.generate_all_analytics_with_context(
        scores_df=scores_df,
        cfg=cfg,
        sensor_context=sensor_context,
        fusion_weights_used=fusion_weights_used,
    )
    table_count = int(analytics_result.get("sql_tables", 0))
    sensor_context = None
    gc.collect()

    return {
        "rows_written_delta": int(core.rows_written_delta),
        "episode_count": int(core.episode_count),
        "analytics_table_count": int(table_count),
        "raw_train": raw_train,
        "raw_score": raw_score,
        "sensor_context": sensor_context,
    }


def run_persistence_stage_service(
    output_manager: Any,
    *,
    section_fn: Any,
    logger: Any,
    scores_df: pd.DataFrame,
    episodes_df: pd.DataFrame,
    train_df: pd.DataFrame,
    raw_train: Optional[pd.DataFrame],
    raw_score: Optional[pd.DataFrame],
    iforest_detector: Optional[Any],
    omr_detector: Optional[Any],
    seasonal_patterns: Optional[Dict[str, List[Any]]],
    cfg: Dict[str, Any],
    sensor_context: Optional[Dict[str, Any]],
    fusion_weights_used: Optional[Dict[str, float]],
    record_episode_fn: Optional[Callable[..., Any]],
    equip: str,
    pca_detector: Any,
    sql_client: Any,
    run_id: Optional[str],
    equip_id: int,
    meta: Any,
    win_start: Optional[pd.Timestamp],
    win_end: Optional[pd.Timestamp],
    rows_read: int,
    spe_p95_train: float,
    t2_p95_train: float,
    anomaly_count: int,
    timer: Any,
    culprit_writer_func: Optional[Callable[..., Any]] = None,
    max_total_rows: int = 10000,
) -> Dict[str, Any]:
    """Execute full persistence stage for pipeline outputs and SQL artifacts."""
    with section_fn("persist"):
        with output_manager.batched_transaction():
            with section_fn("persist.pipeline_outputs"):
                persist_result = output_manager.persist_pipeline_outputs(
                    scores_df=scores_df,
                    episodes_df=episodes_df,
                    raw_train=raw_train,
                    raw_score=raw_score,
                    iforest_detector=iforest_detector,
                    omr_detector=omr_detector,
                    seasonal_patterns=seasonal_patterns,
                    cfg=cfg,
                    sensor_context=sensor_context,
                    fusion_weights_used=fusion_weights_used,
                    record_episode_fn=record_episode_fn,
                    equip=equip,
                    max_total_rows=max_total_rows,
                )
                # analytics_builder already logs "Generated analytics tables (SQL written: N)"

    artifact_rows_written = output_manager._write_sql_artifacts(
        frame=scores_df,
        episodes=episodes_df,
        train=train_df,
        pca_detector=pca_detector,
        sql_client=sql_client,
        run_id=run_id,
        equip_id=equip_id,
        equip=equip,
        cfg=cfg,
        meta=meta,
        win_start=win_start,
        win_end=win_end,
        rows_read=rows_read,
        spe_p95_train=spe_p95_train,
        t2_p95_train=t2_p95_train,
        anomaly_count=anomaly_count,
        timer=timer,
        culprit_writer_func=culprit_writer_func,
    )
    rows_written = int(persist_result.rows_written_delta) + int(artifact_rows_written)

    return {
        "rows_written": rows_written,
        "analytics_table_count": int(persist_result.analytics_table_count),
        "raw_train": persist_result.raw_train,
        "raw_score": persist_result.raw_score,
        "sensor_context": persist_result.sensor_context,
    }


def prepare_persistence_inputs_service(
    output_manager: Any,
    *,
    section_fn: Any,
    raw_train: Optional[pd.DataFrame],
    raw_score: Optional[pd.DataFrame],
    frame: pd.DataFrame,
    omr_contributions_data: Optional[pd.DataFrame],
    regime_model: Any,
    cfg: Dict[str, Any],
    coldstart_complete: bool,
    build_sensor_analytics_context_fn: Any,
    logger: Any,
    equip: str,
) -> Dict[str, Any]:
    """Prepare persistence-stage inputs: baseline buffer update and sensor context."""
    with section_fn("baseline.buffer_write"):
        output_manager.update_baseline_buffer(
            score_numeric=raw_score,
            cfg=cfg,
            coldstart_complete=coldstart_complete,
        )

    with section_fn("sensor.context"):
        sensor_context = build_sensor_analytics_context_fn(
            raw_train=raw_train,
            raw_score=raw_score,
            frame=frame,
            omr_contributions_data=omr_contributions_data,
            regime_model=regime_model,
            logger=logger,
            equip=equip,
        )

    return {"sensor_context": sensor_context}

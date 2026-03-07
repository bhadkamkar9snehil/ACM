"""
SQL artifact writers extracted from OutputManager.

This module keeps artifact-level persistence helpers separate from the
OutputManager class so the manager can stay focused on table write primitives
and persistence orchestration.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple
import json

import numpy as np
import pandas as pd

from core.observability import Console


def write_pca_artifacts(
    output_manager: Any,
    pca_detector: Any,
    frame: pd.DataFrame,
    train: pd.DataFrame,
    run_id: Optional[str],
    equip_id: int,
    equip: str,
    spe_p95_train: float,
    t2_p95_train: float,
    cfg: Dict[str, Any],
) -> Tuple[int, int, int]:
    """Write PCA model, loadings, and metrics to SQL tables."""
    rows_pca_model = rows_pca_load = rows_pca_metrics = 0

    try:
        now_utc = pd.Timestamp.now()
        pca_model = getattr(pca_detector, "pca", None)

        var_ratio = getattr(pca_model, "explained_variance_ratio_", None)
        var_json = json.dumps(var_ratio.tolist()) if var_ratio is not None else "[]"

        scaler_name = pca_detector.scaler.__class__.__name__ if hasattr(pca_detector, "scaler") else "StandardScaler"
        scaler_params = {}
        if hasattr(pca_detector, "scaler"):
            scaler_params["with_mean"] = getattr(pca_detector.scaler, "with_mean", True)
            scaler_params["with_std"] = getattr(pca_detector.scaler, "with_std", True)
        else:
            scaler_params = {"with_mean": True, "with_std": True}

        scaling_spec = json.dumps({"scaler": scaler_name, **scaler_params})
        model_row = {
            "RunID": run_id or "",
            "EquipID": int(equip_id),
            "EntryDateTime": now_utc,
            "NComponents": int(getattr(pca_model, "n_components_", getattr(pca_model, "n_components", 0))),
            "TargetVar": json.dumps({"SPE_P95_train": spe_p95_train, "T2_P95_train": t2_p95_train}),
            "VarExplainedJSON": var_json,
            "ScalingSpecJSON": scaling_spec,
            "ModelVersion": cfg.get("runtime", {}).get("version", "v5.0.0"),
            "TrainStartEntryDateTime": train.index.min() if len(train.index) else None,
            "TrainEndEntryDateTime": train.index.max() if len(train.index) else None,
        }
        rows_pca_model = output_manager.write_pca_model(model_row)

        comps = getattr(pca_model, "components_", None)
        if comps is not None and hasattr(train, "columns"):
            # PCA may have been fitted on fewer features than current train columns
            # (feature set grew after refit). Use only the columns the PCA knows about.
            pca_feature_names = getattr(pca_model, "feature_names_in_", None)
            if pca_feature_names is not None:
                fit_columns = list(pca_feature_names)
            else:
                fit_columns = list(train.columns[: comps.shape[1]])
            load_rows = []
            for k in range(comps.shape[0]):
                for j, sensor in enumerate(fit_columns):
                    load_rows.append(
                        {
                            "RunID": run_id or "",
                            "EntryDateTime": now_utc,
                            "ComponentNo": int(k + 1),
                            "Sensor": str(sensor),
                            "Loading": float(comps[k, j]),
                        }
                    )
            df_load = pd.DataFrame(load_rows)
            rows_pca_load = output_manager.write_pca_loadings(df_load, run_id or "")

        spe_p95 = float(np.nanpercentile(frame["pca_spe"].to_numpy(dtype=np.float32), 95)) if "pca_spe" in frame.columns else None
        t2_p95 = float(np.nanpercentile(frame["pca_t2"].to_numpy(dtype=np.float32), 95)) if "pca_t2" in frame.columns else None

        var90_n = None
        if var_ratio is not None:
            csum = np.cumsum(var_ratio)
            var90_n = int(np.searchsorted(csum, 0.90) + 1)
        components_json = []
        if var_ratio is not None:
            cum = np.cumsum(var_ratio)
            for i, ratio in enumerate(var_ratio):
                components_json.append(
                    {
                        "name": f"PC{i + 1}",
                        "type": "variance_ratio",
                        "value": float(ratio),
                        "cumulative": float(cum[i]),
                    }
                )

        if var90_n is not None:
            components_json.append({"name": "PCA", "type": "var90_n", "value": float(var90_n)})
        if spe_p95 is not None:
            components_json.append({"name": "PCA", "type": "spe_p95_score", "value": float(spe_p95)})
        if t2_p95 is not None:
            components_json.append({"name": "PCA", "type": "t2_p95_score", "value": float(t2_p95)})

        explained_var_val = None
        if var_ratio is not None and len(var_ratio) > 0:
            explained_var_val = float(np.sum(var_ratio))

        df_metrics = pd.DataFrame(
            [
                {
                    "RunID": run_id or "",
                    "EquipID": int(equip_id),
                    "NComponents": int(getattr(pca_model, "n_components_", getattr(pca_model, "n_components", 0))),
                    "ExplainedVariance": explained_var_val,
                    "ComponentsJson": json.dumps(components_json) if components_json else None,
                    "MetricType": "pca_fit",
                    "TrainSamples": int(len(train)) if train is not None else None,
                    "TrainFeatures": int(train.shape[1]) if train is not None else None,
                }
            ]
        )
        rows_pca_metrics = output_manager.write_pca_metrics(df=df_metrics, run_id=run_id or "")
    except Exception as e:
        Console.warn(
            f"PCA artifacts write skipped: {e}",
            component="SQL",
            equip=equip,
            run_id=run_id,
            error=str(e)[:200],
        )

    return rows_pca_model, rows_pca_load, rows_pca_metrics


def write_sql_artifacts(
    output_manager: Any,
    frame: pd.DataFrame,
    episodes: pd.DataFrame,
    train: pd.DataFrame,
    pca_detector: Optional[Any],
    sql_client: Optional[Any],
    run_id: Optional[str],
    equip_id: int,
    equip: str,
    cfg: Dict[str, Any],
    meta: Any,
    win_start: Optional[pd.Timestamp],
    win_end: Optional[pd.Timestamp],
    rows_read: int,
    spe_p95_train: float,
    t2_p95_train: float,
    anomaly_count: int,
    T: Any,
    culprit_writer_func: Optional[Callable] = None,
) -> int:
    """
    Write SQL-specific artifacts: PCA artifacts, run stats, and episode culprits.
    """
    rows_written = 0

    with T.section("sql.pca"):
        rows_pca_model, rows_pca_load, rows_pca_metrics = write_pca_artifacts(
            output_manager=output_manager,
            pca_detector=pca_detector,
            frame=frame,
            train=train,
            run_id=run_id,
            equip_id=equip_id,
            equip=equip,
            spe_p95_train=spe_p95_train,
            t2_p95_train=t2_p95_train,
            cfg=cfg,
        )
        rows_written += int(rows_pca_model + rows_pca_load + rows_pca_metrics)

    with T.section("sql.run_stats"):
        try:
            if sql_client and run_id and win_start is not None and win_end is not None:
                drift_p95 = None
                if "drift_z" in frame.columns:
                    drift_p95 = float(np.nanpercentile(frame["drift_z"].to_numpy(dtype=np.float32), 95))
                sensors_kept = len(getattr(meta, "kept_cols", []))
                cadence_ok_pct = float(getattr(meta, "cadence_ok", 1.0)) * 100.0 if hasattr(meta, "cadence_ok") else None

                output_manager.write_run_stats(
                    {
                        "RunID": run_id,
                        "EquipID": int(equip_id),
                        "WindowStartEntryDateTime": win_start,
                        "WindowEndEntryDateTime": win_end,
                        "SamplesIn": rows_read,
                        "SamplesKept": rows_read,
                        "SensorsKept": sensors_kept,
                        "CadenceOKPct": cadence_ok_pct,
                        "DriftP95": drift_p95,
                        "ReconRMSE": None,
                        "AnomalyCount": anomaly_count,
                    }
                )
        except Exception as e:
            Console.warn(
                f"RunStats not recorded: {e}",
                component="RUN",
                equip=equip,
                run_id=run_id,
                error=str(e)[:200],
            )

    with T.section("sql.culprits"):
        try:
            if culprit_writer_func and sql_client and run_id and len(episodes) > 0:
                culprit_writer_func(
                    sql_client=sql_client,
                    run_id=run_id,
                    episodes=episodes,
                    scores_df=frame,
                    equip_id=equip_id,
                )
        except Exception as e:
            Console.warn(
                f"Failed to write ACM_EpisodeCulprits: {e}",
                component="CULPRITS",
                equip=equip,
                run_id=run_id,
                error=str(e),
            )

    return rows_written


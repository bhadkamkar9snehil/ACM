#!/usr/bin/env python3
"""
CARE-to-Compare benchmark for ACM's unsupervised ML core.

Validates the ONLY claim that matters: starting from t=0 with NO labels and NO
human intervention, does ACM raise an alarm before/during known faults and stay
quiet during normal operation?

Dataset: "Wind Turbine SCADA Data For Early Fault Detection"
         https://zenodo.org/records/15846963 (CARE_To_Compare)
Each <event_id>.csv holds ~1 year of unlabelled 10-minute SCADA history
(train_test == 'train') followed by a prediction window containing exactly one
event — either a real fault (anomaly) or normal behaviour. The training history
includes whatever issues actually occurred on the asset; nothing is cleaned.

Protocol per dataset (strictly unsupervised):
  1. Train  = all 'train' rows (raw history from t=0, faults included).
  2. Score  = all 'prediction' rows.
  3. Feature engineering, detector fitting, calibration and fusion use the
     exact production ML code (core.fast_features / detector_orchestrator /
     fuse) with the production config (configs/config_table.csv, EquipID=0).
     Labels (event_info.csv) are touched ONLY by the evaluator, never by the
     model.
  4. Alarm rule: fused z >= alert_z sustained for >= persist consecutive
     samples (default 3.0 sigma for 1 hour).

Metrics (event level, CARE-style):
  - anomaly event detected  = sustained alarm anywhere in the prediction window
  - lead time               = event_start - first sustained alarm
  - normal event clean      = no sustained alarm during normal operation
                              (status_type_id 0 or 2; alarms during service /
                              downtime are not counted as false positives)

Usage:
  python scripts/care_benchmark.py --data-dir "/path/CARE_To_Compare/Wind Farm A" \
      [--datasets 40 68] [--out results/care] [--alert-z 3.0] [--persist 6]

No SQL Server, no Grafana, no observability stack required.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import detector_orchestrator as orch          # noqa: E402
from core import fuse                                    # noqa: E402
from core.fast_features import build_features_for_pipeline  # noqa: E402
from utils.config_dict import ConfigDict                 # noqa: E402

META_COLS = {"time_stamp", "asset_id", "id", "train_test", "status_type_id"}
NORMAL_STATUS = {0, 2}  # Normal operation / idling per CARE README

# raw score column -> calibrated z column (must mirror detector_orchestrator)
Z_MAP = [
    ("ar1_raw", "ar1_z"),
    ("pca_spe", "pca_spe_z"),
    ("pca_t2", "pca_t2_z"),
    ("iforest_raw", "iforest_z"),
    ("gmm_raw", "gmm_z"),
    ("omr_raw", "omr_z"),
]


def load_config() -> dict:
    cfg = ConfigDict.from_csv(ROOT / "configs" / "config_table.csv", equip_id=0)
    return dict(cfg)


def load_event_info(farm_dir: Path) -> pd.DataFrame:
    info = pd.read_csv(farm_dir / "event_info.csv", sep=";")
    info["event_start"] = pd.to_datetime(info["event_start"])
    info["event_end"] = pd.to_datetime(info["event_end"])
    return info


def load_dataset(farm_dir: Path, event_id: int) -> pd.DataFrame:
    df = pd.read_csv(farm_dir / "datasets" / f"{event_id}.csv", sep=";")
    df["time_stamp"] = pd.to_datetime(df["time_stamp"])
    return df


def sensor_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Numeric sensor matrix indexed by timestamp (pipeline convention)."""
    cols = [c for c in df.columns if c not in META_COLS]
    out = df[cols].apply(pd.to_numeric, errors="coerce")
    out.index = pd.DatetimeIndex(df["time_stamp"], name="EntryDateTime")
    out = out.replace([np.inf, -np.inf], np.nan)
    # Drop channels that are entirely missing in this dataset
    out = out.dropna(axis=1, how="all")
    return out


def sustained_alarm_mask(fused: np.ndarray, alert_z: float, persist: int) -> np.ndarray:
    """True where fused >= alert_z has held for >= persist consecutive samples."""
    above = fused >= alert_z
    if persist <= 1:
        return above
    run = np.zeros(len(above), dtype=int)
    streak = 0
    for i, a in enumerate(above):
        streak = streak + 1 if a else 0
        run[i] = streak
    return run >= persist


def self_tune_alarm_rule(
    train_fused: Optional[np.ndarray],
    alert_z_floor: float,
    persist_floor: int,
    target_fp: float = 0.001,
) -> tuple[float, int]:
    """Derive the alarm operating point from the asset's OWN unlabelled history.

    Fully unsupervised: pick the smallest (threshold, persistence) pair such
    that the training period — which the model treats as the asset's normal
    life, faults and all — would never have raised a sustained alarm. No
    labels, no human tuning, and contamination in the history automatically
    makes the rule more conservative rather than poisoning it.
    """
    if train_fused is None or len(train_fused) < 100:
        return alert_z_floor, persist_floor
    tf = np.asarray(train_fused, dtype=np.float64)
    tf = tf[np.isfinite(tf)]
    if tf.size < 100:
        return alert_z_floor, persist_floor
    alert_z = max(alert_z_floor, float(np.quantile(tf, 1.0 - target_fp)))
    # Longest run at/above the chosen threshold in training; alarm requires
    # outlasting anything the history ever produced.
    above = tf >= alert_z
    longest = streak = 0
    for a in above:
        streak = streak + 1 if a else 0
        longest = max(longest, streak)
    persist = max(persist_floor, longest + 1)
    return alert_z, persist


def run_event(
    farm_dir: Path,
    event: pd.Series,
    cfg: dict,
    alert_z: float,
    persist: int,
    out_dir: Optional[Path],
) -> Dict:
    event_id = int(event["event_id"])
    label = str(event["event_label"])
    t0 = time.time()

    df = load_dataset(farm_dir, event_id)
    train_raw = sensor_frame(df[df["train_test"] == "train"])
    score_raw = sensor_frame(df[df["train_test"] == "prediction"])
    score_status = df.loc[df["train_test"] == "prediction", "status_type_id"].to_numpy()

    # --- ML core: features -> detectors -> calibration -> fusion ------------
    train_feat, score_feat = build_features_for_pipeline(train_raw, score_raw, cfg)

    # OUT-OF-SAMPLE CALIBRATION: detectors score their own training data
    # optimistically (in-sample bias), so calibrating z-scores on the fit data
    # inflates z on ALL future data — healthy periods included. Fit detectors
    # on the earlier slice, calibrate on the held-out tail they never saw.
    holdout_frac = float((cfg.get("thresholds", {}) or {}).get("calibration_holdout_frac", 0.2))
    n_fit = int(len(train_feat) * (1.0 - holdout_frac))
    fit_feat = train_feat.iloc[:n_fit]
    calib_feat = train_feat.iloc[n_fit:]

    det = orch.fit_all_detectors(
        train=fit_feat, cfg=cfg,
        ar1_enabled=True, pca_enabled=True, iforest_enabled=True,
        gmm_enabled=True, omr_enabled=True,
    )

    det_kwargs = dict(
        ar1_detector=det.get("ar1_detector"),
        pca_detector=det.get("pca_detector"),
        iforest_detector=det.get("iforest_detector"),
        gmm_detector=det.get("gmm_detector"),
        omr_detector=det.get("omr_detector"),
    )
    calib_frame, _ = orch.score_all_detectors(calib_feat, **det_kwargs,
                                              return_omr_contributions=False)
    score_frame, omr_contrib = orch.score_all_detectors(score_feat, **det_kwargs)

    cal_q = float((cfg.get("thresholds", {}) or {}).get("q", 0.98))
    self_tune_cfg = (cfg.get("thresholds", {}) or {}).get("self_tune", {}) or {}
    score_frame, calibrators = orch.calibrate_all_detectors(
        train_frame=calib_frame, score_frame=score_frame,
        cal_q=cal_q, self_tune_cfg=self_tune_cfg,
        fit_regimes=None, transform_regimes=None,
    )
    # Same calibrators applied to holdout scores (fusion threshold baseline)
    for raw_col, z_col in Z_MAP:
        cal = calibrators.get(z_col)
        if cal is not None and raw_col in calib_frame.columns:
            calib_frame[z_col] = cal.transform(calib_frame[raw_col].to_numpy(copy=False))

    fusion = fuse.run_fusion_pipeline(
        frame=score_frame, train_frame=calib_frame,
        score_data=score_feat, train_data=calib_feat,
        cfg=cfg, omr_contributions=omr_contrib,
    )
    fused = np.asarray(fusion.fused_scores, dtype=np.float64)

    # Self-tuned alarm operating point from the asset's own history (no labels)
    alert_z_eff, persist_eff = self_tune_alarm_rule(fusion.train_fused, alert_z, persist)

    # --- Evaluation (the ONLY place labels are used) -------------------------
    ts = score_frame.index
    alarm = sustained_alarm_mask(fused, alert_z_eff, persist_eff)
    normal_op = np.isin(score_status, list(NORMAL_STATUS))

    event_start = event["event_start"]
    event_end = event["event_end"]

    result: Dict = {
        "event_id": event_id,
        "asset": int(event["asset"]),
        "label": label,
        "description": event.get("event_description") if isinstance(event.get("event_description"), str) else "",
        "n_train": len(train_raw),
        "n_score": len(score_raw),
        "alert_z_eff": round(float(alert_z_eff), 2),
        "persist_eff": int(persist_eff),
        "fused_p50": float(np.nanmedian(fused)),
        "fused_max": float(np.nanmax(fused)),
        "alarm_frac": float(alarm.mean()),
        "runtime_s": 0.0,
    }

    if label == "anomaly":
        first_alarm = ts[alarm][0] if alarm.any() else None
        detected = bool(alarm.any())
        result.update({
            "detected": detected,
            "first_alarm": str(first_alarm) if first_alarm is not None else "",
            "event_start": str(event_start),
            "lead_time_h": (
                float((event_start - first_alarm).total_seconds() / 3600.0)
                if first_alarm is not None else np.nan
            ),
            # fused level inside the labelled fault window
            "fused_max_in_event": float(np.nanmax(
                fused[(ts >= event_start) & (ts <= event_end)]
            )) if ((ts >= event_start) & (ts <= event_end)).any() else np.nan,
            "false_alarm_frac_normal_op": np.nan,
        })
    else:
        # Normal event: any sustained alarm during normal operation = false positive
        fp = alarm & normal_op
        result.update({
            "detected": bool(fp.any()),  # for a normal event, detected == false alarm
            "first_alarm": str(ts[fp][0]) if fp.any() else "",
            "event_start": str(event_start),
            "lead_time_h": np.nan,
            "fused_max_in_event": np.nan,
            "false_alarm_frac_normal_op": float(fp.sum() / max(normal_op.sum(), 1)),
        })

    result["runtime_s"] = round(time.time() - t0, 1)

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        series = pd.DataFrame({
            "time_stamp": ts,
            "fused": fused,
            "alarm": alarm.astype(int),
            "status_type_id": score_status,
        })
        for _, z_col in Z_MAP:
            if z_col in score_frame.columns:
                series[z_col] = score_frame[z_col].to_numpy()
        series.to_csv(out_dir / f"event_{event_id}_scores.csv", index=False)
        if fusion.train_fused is not None:
            pd.DataFrame({"train_fused": np.asarray(fusion.train_fused)}).to_csv(
                out_dir / f"event_{event_id}_train_fused.csv", index=False)
        if fusion.episodes is not None and len(fusion.episodes) > 0:
            fusion.episodes.to_csv(out_dir / f"event_{event_id}_episodes.csv", index=False)

    return result


def summarize(results: List[Dict], alert_z: float, persist: int) -> Dict:
    res = pd.DataFrame(results)
    if res.empty or "label" not in res.columns:
        return {"error": "no successful events", "alert_z": alert_z, "persist_samples": persist}
    anomalies = res[res["label"] == "anomaly"]
    normals = res[res["label"] == "normal"]
    detected = anomalies["detected"].sum() if len(anomalies) else 0
    clean = (~normals["detected"]).sum() if len(normals) else 0
    early = anomalies[anomalies["lead_time_h"] > 0] if len(anomalies) else anomalies
    summary = {
        "alert_z": alert_z,
        "persist_samples": persist,
        "anomaly_events": int(len(anomalies)),
        "anomalies_detected": int(detected),
        "detection_rate": float(detected / len(anomalies)) if len(anomalies) else np.nan,
        "detected_before_event_start": int((anomalies["lead_time_h"] > 0).sum()) if len(anomalies) else 0,
        "median_lead_time_h": float(early["lead_time_h"].median()) if len(early) else np.nan,
        "normal_events": int(len(normals)),
        "normal_events_clean": int(clean),
        "false_alarm_event_rate": float(1 - clean / len(normals)) if len(normals) else np.nan,
    }
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True, help="Wind Farm directory (contains datasets/ and event_info.csv)")
    ap.add_argument("--datasets", nargs="*", type=int, default=None, help="Specific event IDs (default: all)")
    ap.add_argument("--out", default=None, help="Output directory for per-event score series + results")
    ap.add_argument("--alert-z", type=float, default=3.0)
    ap.add_argument("--persist", type=int, default=6, help="Consecutive samples above alert-z to raise alarm (6 = 1h)")
    args = ap.parse_args()

    farm_dir = Path(args.data_dir)
    out_dir = Path(args.out) if args.out else None
    cfg = load_config()
    info = load_event_info(farm_dir)
    if args.datasets:
        info = info[info["event_id"].isin(args.datasets)]

    results: List[Dict] = []
    for _, event in info.sort_values("event_id").iterrows():
        eid, lbl = int(event["event_id"]), event["event_label"]
        print(f"\n=== event {eid} ({lbl}: {event.get('event_description') or 'normal behaviour'}) ===", flush=True)
        try:
            r = run_event(farm_dir, event, cfg, args.alert_z, args.persist, out_dir)
        except Exception as e:  # keep the benchmark running; report the failure
            import traceback
            traceback.print_exc()
            r = {"event_id": eid, "label": lbl, "error": str(e)[:300]}
        results.append(r)
        if "error" not in r:
            tag = ("DETECTED" if r["detected"] else "MISSED") if lbl == "anomaly" else \
                  ("FALSE ALARM" if r["detected"] else "clean")
            lead = f" lead={r['lead_time_h']:+.1f}h" if lbl == "anomaly" and r["detected"] else ""
            print(f"--- event {eid}: {tag}{lead} fused_max={r['fused_max']:.2f} "
                  f"alarm_frac={r['alarm_frac']:.3f} ({r['runtime_s']}s)", flush=True)

    ok = [r for r in results if "error" not in r]
    summary = summarize(ok, args.alert_z, args.persist)

    print("\n================ CARE BENCHMARK SUMMARY ================")
    print(json.dumps(summary, indent=2))
    res_df = pd.DataFrame(results)
    cols = [c for c in ["event_id", "asset", "label", "description", "detected", "lead_time_h",
                        "alert_z_eff", "persist_eff", "fused_max", "alarm_frac",
                        "false_alarm_frac_normal_op", "runtime_s", "error"]
            if c in res_df.columns]
    print(res_df[cols].to_string(index=False))

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        res_df.to_csv(out_dir / "results.csv", index=False)
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        print(f"\nWritten: {out_dir}/results.csv, summary.json, per-event score series")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

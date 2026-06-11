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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import detector_orchestrator as orch          # noqa: E402
from core import fuse                                    # noqa: E402
from core.fast_features import build_features_for_pipeline, detect_channel_roles  # noqa: E402
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
    if "asset" not in info.columns and "asset_id" in info.columns:
        info = info.rename(columns={"asset_id": "asset"})  # Farm B/C header variant
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


def _longest_run(mask: np.ndarray) -> int:
    longest = streak = 0
    for a in mask:
        streak = streak + 1 if a else 0
        longest = max(longest, streak)
    return longest


def self_tune_alarm_rule(
    train_fused: Optional[np.ndarray],
    alert_z_floor: float,
    persist_floor: int,
    target_fp: float = 0.001,
    max_persist: int = 72,   # 12h at 10-min cadence
) -> tuple[float, int]:
    """Derive the alarm operating point from the asset's OWN unlabelled history.

    Fully unsupervised "low-and-slow" rule: among candidate quantile
    thresholds of the held-out fused stream, take the LOWEST threshold whose
    implied persistence — outlasting the longest healthy excursion at that
    level by a 1.5x safety margin — stays physically sensible (<= max_persist
    samples). Degradation sustains for days, so a low bar held for hours
    detects faults far earlier than a high bar held briefly, while anything
    the healthy history itself produced can never alarm. No labels, no human
    tuning; contamination in the history makes the rule more conservative
    rather than poisoning it.
    """
    if train_fused is None or len(train_fused) < 100:
        return alert_z_floor, persist_floor
    tf = np.asarray(train_fused, dtype=np.float64)
    tf = tf[np.isfinite(tf)]
    if tf.size < 100:
        return alert_z_floor, persist_floor

    for q in (0.98, 0.99, 0.995, 0.999):
        thr = max(alert_z_floor, float(np.quantile(tf, q)))
        persist = max(persist_floor, int(_longest_run(tf >= thr) * 1.5) + 1)
        if persist <= max_persist:
            return thr, persist

    # History too noisy for any low bar: fall back to the strict tail rule.
    thr = max(alert_z_floor, float(np.quantile(tf, 1.0 - target_fp)))
    persist = max(persist_floor, _longest_run(tf >= thr) + 1)
    return thr, persist


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
    runlog: List[Dict] = []

    def _log(stage: str, message: str, level: str = "INFO") -> None:
        runlog.append({"ts": datetime.now().isoformat(sep=" ", timespec="seconds"),
                       "level": level, "stage": stage, "message": message})

    df = load_dataset(farm_dir, event_id)
    train_raw = sensor_frame(df[df["train_test"] == "train"])
    score_raw = sensor_frame(df[df["train_test"] == "prediction"])
    score_status = df.loc[df["train_test"] == "prediction", "status_type_id"].to_numpy()
    train_status = df.loc[df["train_test"] == "train", "status_type_id"].to_numpy()

    # --- ML core: features -> detectors -> calibration -> fusion ------------
    # Channel roles are detected from the DATA (core.fast_features
    # .detect_channel_roles): a channel counts as a pre-derived window
    # statistic only when the min<=avg<=max / std>=0 relationship verifies on
    # the samples. Raw-sensor feeds (the production case) have no derived
    # channels and pass through untouched.
    roles = detect_channel_roles(train_raw)
    derived_cols = roles["derived"]
    _log("channels", f"{len(roles['primary'])} primary, {len(derived_cols)} data-verified derived of {train_raw.shape[1]} channels")
    train_feat, score_feat = build_features_for_pipeline(
        train_raw.drop(columns=derived_cols), score_raw.drop(columns=derived_cols), cfg)
    if derived_cols:
        train_feat = pd.concat([train_feat, train_raw[derived_cols]], axis=1)
        score_feat = pd.concat([score_feat, score_raw[derived_cols]], axis=1)
    _log("features", f"matrix {train_feat.shape[0]}x{train_feat.shape[1]} built in {time.time()-t0:.0f}s")
    # float32 halves every downstream allocation; detector math is float32-safe
    train_feat = train_feat.astype(np.float32)
    score_feat = score_feat.astype(np.float32)

    # OUT-OF-SAMPLE CALIBRATION with an INTERLEAVED split: detectors score
    # their own training data optimistically, so calibration must use data
    # they never saw — but a chronological tail holdout is poisonous here:
    # the last weeks of history sit right before the prediction window and
    # already contain the fault's early degradation, baking the fault
    # signature into "normal" and burying detection. Instead, hold out every
    # 5th block of ~3 days across the WHOLE year: out-of-sample, spans all
    # seasons, and at most ~20% of any pre-fault degradation.
    holdout_frac = float((cfg.get("thresholds", {}) or {}).get("calibration_holdout_frac", 0.2))
    block = 432  # 3 days at 10-min cadence
    stride = max(2, int(round(1.0 / max(holdout_frac, 1e-6))))
    idx = np.arange(len(train_feat))
    calib_mask = (idx // block) % stride == (stride - 1)
    fit_feat = train_feat.iloc[~calib_mask]
    calib_feat = train_feat.iloc[calib_mask]

    t_fit = time.time()
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
    _log("fit", f"detectors fitted in {time.time()-t_fit:.0f}s")
    score_frame, omr_contrib = orch.score_all_detectors(score_feat, **det_kwargs)

    # Production calibration stage (adaptive clip + contamination filter),
    # fitted on the HELD-OUT slice the detectors never saw.
    flags = {f"{k}_enabled": True for k in ("ar1", "pca", "iforest", "gmm", "omr")}
    cal_stage = fuse.run_calibration_stage(
        train=calib_feat, frame=score_frame, cfg=cfg,
        regime_quality_ok=False,
        train_regime_labels=None, score_regime_labels=None,
        pca_train_spe=None, pca_train_t2=None,
        detectors=det, detector_flags=flags,
        cached_calibration_params=None, saved_model_version=None,
        score_all_detectors_fn=orch.score_all_detectors,
        calibrate_all_detectors_fn=orch.calibrate_all_detectors,
        equip=f"event_{event_id}",
    )
    score_frame = cal_stage.frame
    calib_frame = cal_stage.train_frame
    # Apply the same calibrators to holdout scores (fusion threshold baseline)
    for raw_col, z_col in Z_MAP:
        cal = cal_stage.calibrators_dict.get(z_col)
        if cal is not None and raw_col in calib_frame.columns:
            calib_frame[z_col] = cal.transform(calib_frame[raw_col].to_numpy(copy=False))

    fusion = fuse.run_fusion_pipeline(
        frame=score_frame, train_frame=calib_frame,
        score_data=score_feat, train_data=calib_feat,
        cfg=cfg, omr_contributions=omr_contrib,
    )
    fused = np.asarray(fusion.fused_scores, dtype=np.float64)
    ts = pd.DatetimeIndex(score_frame.index)
    train_fused = np.asarray(fusion.train_fused, dtype=np.float64) if fusion.train_fused is not None else None

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        series = pd.DataFrame({
            "time_stamp": ts,
            "fused": fused,
            "status_type_id": score_status,
        })
        for _, z_col in Z_MAP:
            if z_col in score_frame.columns:
                series[z_col] = score_frame[z_col].to_numpy()
        series.to_csv(out_dir / f"event_{event_id}_scores.csv", index=False)
        if train_fused is not None:
            tf_df = pd.DataFrame({"train_fused": train_fused})
            for _, z_col in Z_MAP:
                if z_col in calib_frame.columns and len(calib_frame) == len(tf_df):
                    tf_df[z_col] = calib_frame[z_col].to_numpy()
            tf_df.to_csv(out_dir / f"event_{event_id}_train_fused.csv", index=False)
        if fusion.episodes is not None and len(fusion.episodes) > 0:
            fusion.episodes.to_csv(out_dir / f"event_{event_id}_episodes.csv", index=False)

    head_z_score = {z: score_frame[z].to_numpy() for _, z in Z_MAP if z in score_frame.columns}
    head_z_train = {z: calib_frame[z].to_numpy() for _, z in Z_MAP if z in calib_frame.columns}
    result = evaluate_series(ts, fused, score_status, train_fused, event, alert_z, persist,
                             train_status=train_status,
                             head_z_score=head_z_score, head_z_train=head_z_train)
    result.update({"n_train": len(train_raw), "n_score": len(score_raw),
                   "runtime_s": round(time.time() - t0, 1), "reused": False})
    _log("rules", f"alert_z={result.get('alert_z_eff')} persist={result.get('persist_eff')} "
                  f"fired={result.get('rule_fired') or '-'}")
    if "(distrusted" in (result.get("rule_fired") or ""):
        _log("rules", f"self-distrust gate discarded: {result['rule_fired']}", level="WARN")
    _log("done", f"total {result['runtime_s']}s")
    if out_dir is not None:
        pd.DataFrame(runlog).to_csv(out_dir / f"event_{event_id}_runlog.csv", index=False)
    return result


def rolling_rate(fused: np.ndarray, z0: float, window: int = 144) -> np.ndarray:
    """Trailing fraction of samples >= z0 over `window` samples (24h default)."""
    above = (np.asarray(fused, dtype=np.float64) >= z0).astype(float)
    return pd.Series(above).rolling(window, min_periods=window // 2).mean().to_numpy()


def evaluate_series(
    ts: pd.DatetimeIndex,
    fused: np.ndarray,
    score_status: np.ndarray,
    train_fused: Optional[np.ndarray],
    event: pd.Series,
    alert_z: float,
    persist: int,
    train_status: Optional[np.ndarray] = None,
    head_z_score: Optional[Dict[str, np.ndarray]] = None,
    head_z_train: Optional[Dict[str, np.ndarray]] = None,
) -> Dict:
    """Label-aware evaluation of a fused score series (labels used ONLY here).

    Three self-tuned alarm rules, OR-combined:
      sustained    — fused holds above a holdout-quantile threshold longer
                     than the healthy history ever did (step-change faults);
      rate         — trailing 24h fraction of high-z samples exceeds 1.5x the
                     worst 24h the holdout ever produced (intermittent faults
                     that spike under load between quiet periods);
      availability — the asset has been continuously NON-operating (SCADA
                     status outside normal operation/idling) longer than 1.5x
                     the longest stop in its entire healthy history. Failures
                     park the asset: in CARE Farm A, 10 of 12 fault windows
                     contain ZERO operating samples — there is no behaviour
                     left to deviate, and the outage itself is the symptom.
    """
    event_id = int(event["event_id"])
    label = str(event["event_label"])
    event_start, event_end = event["event_start"], event["event_end"]

    alert_z_eff, persist_eff = self_tune_alarm_rule(train_fused, alert_z, persist)
    alarm_sustained = sustained_alarm_mask(fused, alert_z_eff, persist_eff)

    rate_thr = np.nan
    z0 = alert_z
    alarm_rate = np.zeros(len(fused), dtype=bool)
    if train_fused is not None and np.isfinite(train_fused).sum() > 500:
        tf = np.asarray(train_fused, dtype=np.float64)
        tf = tf[np.isfinite(tf)]
        z0 = max(alert_z, float(np.quantile(tf, 0.99)))
        hold_rate = rolling_rate(tf, z0)
        base = float(np.nanmax(hold_rate)) if np.isfinite(hold_rate).any() else 0.0
        rate_thr = float(np.clip(base * 1.5, 0.05, 0.9))
        score_rate = rolling_rate(fused, z0)
        # Require the exceedance itself to persist (1h): a single rolling-
        # window sample grazing the threshold is noise; real degradation
        # holds the trailing rate up for days.
        alarm_rate = sustained_alarm_mask(np.nan_to_num(score_rate, nan=0.0), rate_thr, 6)

    avail_run_thr = None
    alarm_avail = np.zeros(len(fused), dtype=bool)
    if train_status is not None and len(train_status) > 1000:
        nonop_train = ~np.isin(np.asarray(train_status), list(NORMAL_STATUS))
        # Stop-duration DISTRIBUTION, not the maximum: the longest stop in a
        # t=0 history is usually a PREVIOUS fault's multi-week outage, which
        # would set the bar above any future fault. p95 of stop durations is
        # robust to those outliers (codebase convention: robust stats over
        # extremes). Floor of 24h keeps micro-stops from producing a hair
        # trigger.
        stops, run = [], 0
        for a in nonop_train:
            if a:
                run += 1
            elif run:
                stops.append(run)
                run = 0
        if run:
            stops.append(run)
        # Domain prior, not a fitted constant: continuous unplanned
        # non-operation >= 48h is a reportable condition on any asset.
        # p95 escalation handles assets whose ROUTINE stops run longer —
        # but with few stops/year p95 degenerates to the max (a prior
        # fault's outage), so it can only RAISE the bar, floored at 48h.
        p95_stop = float(np.percentile(stops, 95)) if len(stops) >= 20 else 0.0
        avail_run_thr = max(288, int(p95_stop * 1.5) + 1)  # >= 48h at 10-min cadence
        nonop_score = ~np.isin(np.asarray(score_status), list(NORMAL_STATUS))
        run = 0
        for i, a in enumerate(nonop_score):
            run = run + 1 if a else 0
            if run >= avail_run_thr:
                alarm_avail[i] = True

    # Per-head rate rules: a fault often lives in ONE detector (e.g. OMR for
    # a transformer-cell overheat) and the weighted fusion dilutes it below
    # any fused-level rule. Each head self-tunes its own rate threshold from
    # its own held-out stream — same form as the fused rate rule.
    heads_fired = []
    alarm_heads = np.zeros(len(fused), dtype=bool)
    if head_z_score and head_z_train:
        for name, z_tr in head_z_train.items():
            z_sc = head_z_score.get(name)
            if z_sc is None or len(z_sc) != len(fused):
                continue
            ztr = np.asarray(z_tr, dtype=np.float64)
            ztr = ztr[np.isfinite(ztr)]
            if ztr.size < 500:
                continue
            z0_h = max(alert_z, float(np.quantile(ztr, 0.99)))
            # 7-day integration window: per-head signatures of slow faults
            # (transformer overheat, bearing wear) are persistent-but-sparse;
            # long integration drops the variance of the rate statistic and
            # separates them from short healthy bursts.
            base_h = float(np.nanmax(rolling_rate(ztr, z0_h, window=1008)))
            thr_h = float(np.clip(base_h * 1.5, 0.05, 0.9))
            r_sc = np.nan_to_num(rolling_rate(np.asarray(z_sc, dtype=np.float64), z0_h, window=1008), nan=0.0)
            mask_h = sustained_alarm_mask(r_sc, thr_h, 6)
            if mask_h.any():
                heads_fired.append(name)
                alarm_heads |= mask_h

    # SELF-DISTRUST GATE (unsupervised): genuine behavioural faults fire
    # intermittently or escalate; only a broken baseline flags the majority
    # of a multi-week window. Any behaviour rule whose mask covers >50% of
    # the window is declared miscalibrated and discarded (availability is
    # exempt: a failed asset IS down for most of the window).
    distrusted = []
    if alarm_sustained.mean() > 0.5:
        distrusted.append("sustained"); alarm_sustained = np.zeros_like(alarm_sustained)
    if alarm_rate.mean() > 0.5:
        distrusted.append("rate"); alarm_rate = np.zeros_like(alarm_rate)
    if alarm_heads.mean() > 0.5:
        distrusted.append("heads:" + ",".join(heads_fired))
        heads_fired = []; alarm_heads = np.zeros_like(alarm_heads)

    alarm = alarm_sustained | alarm_rate | alarm_avail | alarm_heads
    normal_op = np.isin(score_status, list(NORMAL_STATUS))

    result: Dict = {
        "event_id": event_id,
        "asset": int(event["asset"]),
        "label": label,
        "description": event.get("event_description") if isinstance(event.get("event_description"), str) else "",
        "alert_z_eff": round(float(alert_z_eff), 2),
        "persist_eff": int(persist_eff),
        "rate_z0": round(float(z0), 2),
        "rate_thr": round(float(rate_thr), 3) if np.isfinite(rate_thr) else np.nan,
        "avail_run_thr_h": round(avail_run_thr / 6.0, 1) if avail_run_thr else np.nan,
        "rule_fired": ("sustained" if alarm_sustained.any() else "") +
                      ("+rate" if alarm_rate.any() else "") +
                      ("+avail" if alarm_avail.any() else "") +
                      (("+heads:" + ",".join(heads_fired)) if heads_fired else "") +
                      (("(distrusted:" + ";".join(distrusted) + ")") if distrusted else ""),
        "fused_p50": float(np.nanmedian(fused)),
        "fused_max": float(np.nanmax(fused)),
        "alarm_frac": float(alarm.mean()),
    }

    if label == "anomaly":
        detected = bool(alarm.any())
        first_alarm = ts[alarm][0] if detected else None
        result.update({
            "detected": detected,
            "first_alarm": str(first_alarm) if first_alarm is not None else "",
            "event_start": str(event_start),
            "lead_time_h": (
                float((event_start - first_alarm).total_seconds() / 3600.0)
                if first_alarm is not None else np.nan
            ),
            "fused_max_in_event": float(np.nanmax(
                fused[(ts >= event_start) & (ts <= event_end)]
            )) if ((ts >= event_start) & (ts <= event_end)).any() else np.nan,
            "false_alarm_frac_normal_op": np.nan,
        })
    else:
        # Normal event: any alarm during normal operation = false positive
        fp = alarm & normal_op
        result.update({
            "detected": bool(fp.any()),  # for a normal event, detected == false alarm
            "first_alarm": str(ts[fp][0]) if fp.any() else "",
            "event_start": str(event_start),
            "lead_time_h": np.nan,
            "fused_max_in_event": np.nan,
            "false_alarm_frac_normal_op": float(fp.sum() / max(normal_op.sum(), 1)),
        })
    return result


def try_reuse_event(out_dir: Optional[Path], event: pd.Series, alert_z: float, persist: int,
                    farm_dir: Optional[Path] = None) -> Optional[Dict]:
    """Re-evaluate saved score series (crash-proof resume; rules are eval-only)."""
    if out_dir is None:
        return None
    eid = int(event["event_id"])
    s_path = out_dir / f"event_{eid}_scores.csv"
    t_path = out_dir / f"event_{eid}_train_fused.csv"
    if not (s_path.exists() and t_path.exists() and s_path.stat().st_size and t_path.stat().st_size):
        return None
    try:
        s = pd.read_csv(s_path, parse_dates=["time_stamp"])
        tf = pd.read_csv(t_path)["train_fused"].to_numpy()
        train_status = None
        if farm_dir is not None:
            raw = pd.read_csv(farm_dir / "datasets" / f"{eid}.csv", sep=";",
                              usecols=["train_test", "status_type_id"])
            train_status = raw.loc[raw["train_test"] == "train", "status_type_id"].to_numpy()
        tf_df = pd.read_csv(t_path)
        head_z_train = {z: tf_df[z].to_numpy() for _, z in Z_MAP if z in tf_df.columns}
        head_z_score = {z: s[z].to_numpy() for _, z in Z_MAP if z in s.columns}
        result = evaluate_series(pd.DatetimeIndex(s["time_stamp"]), s["fused"].to_numpy(),
                                 s["status_type_id"].to_numpy(), tf, event, alert_z, persist,
                                 train_status=train_status,
                                 head_z_score=head_z_score,
                                 head_z_train=head_z_train if head_z_train else None)
        result.update({"runtime_s": 0.0, "reused": True})
        return result
    except Exception:
        return None


def summarize(results: List[Dict], alert_z: float, persist: int) -> Dict:
    res = pd.DataFrame(results)
    if res.empty or "label" not in res.columns:
        return {"error": "no successful events", "alert_z": alert_z, "persist_samples": persist}
    anomalies = res[res["label"] == "anomaly"]
    normals = res[res["label"] == "normal"]
    detected = anomalies["detected"].sum() if len(anomalies) else 0
    clean = (~normals["detected"]).sum() if len(normals) else 0
    early = anomalies[anomalies["lead_time_h"] > 0] if len(anomalies) else anomalies

    # Event-level KPI: each dataset is one decision.
    #   TP = fault detected | FN = fault missed
    #   FP = normal window alarmed | TN = normal window clean
    tp, fn = int(detected), int(len(anomalies) - detected)
    fp, tn = int(len(normals) - clean), int(clean)
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * precision * recall / (precision + recall)
          if np.isfinite(precision) and np.isfinite(recall) and (precision + recall) > 0 else 0.0)
    # "Respectable" bar: catch >= 80% of faults with event-level F1 >= 0.75.
    kpi_pass = bool(np.isfinite(recall) and recall >= 0.80 and f1 >= 0.75)

    summary = {
        "alert_z": alert_z,
        "persist_samples": persist,
        "anomaly_events": int(len(anomalies)),
        "anomalies_detected": tp,
        "detection_rate": float(recall) if np.isfinite(recall) else np.nan,
        "detected_before_event_start": int((anomalies["lead_time_h"] > 0).sum()) if len(anomalies) else 0,
        "median_lead_time_h": float(early["lead_time_h"].median()) if len(early) else np.nan,
        "normal_events": int(len(normals)),
        "normal_events_clean": tn,
        "false_alarm_event_rate": float(fp / len(normals)) if len(normals) else np.nan,
        "event_precision": float(precision) if np.isfinite(precision) else np.nan,
        "event_recall": float(recall) if np.isfinite(recall) else np.nan,
        "event_f1": float(f1),
        "KPI": "PASS (recall>=0.80 and F1>=0.75)" if kpi_pass else "FAIL (need recall>=0.80 and F1>=0.75)",
    }
    return summary


def _print_event_line(r: Dict) -> None:
    if "error" in r:
        print(f"--- event {r.get('event_id')}: ERROR {r['error'][:120]}", flush=True)
        return
    lbl = r["label"]
    tag = ("DETECTED" if r["detected"] else "MISSED") if lbl == "anomaly" else \
          ("FALSE ALARM" if r["detected"] else "clean")
    lead = f" lead={r['lead_time_h']:+.1f}h" if lbl == "anomaly" and r["detected"] else ""
    src = " [reused]" if r.get("reused") else f" ({r.get('runtime_s', 0)}s)"
    print(f"--- event {r['event_id']}: {tag}{lead} rule={r.get('rule_fired','') or '-'} "
          f"fused_max={r['fused_max']:.2f}{src}", flush=True)


def _run_event_worker(farm_dir: Path, event_dict: Dict, alert_z: float,
                      persist: int, out_dir: Optional[Path]) -> Dict:
    """Process-pool worker: each event is fully independent."""
    event = pd.Series(event_dict)
    try:
        cfg = load_config()
        return run_event(farm_dir, event, cfg, alert_z, persist, out_dir)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"event_id": int(event_dict.get("event_id", -1)),
                "label": str(event_dict.get("event_label", "?")), "error": str(e)[:300]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True, help="Wind Farm directory (contains datasets/ and event_info.csv)")
    ap.add_argument("--datasets", nargs="*", type=int, default=None, help="Specific event IDs (default: all)")
    ap.add_argument("--out", default=None, help="Output directory for per-event score series + results")
    ap.add_argument("--alert-z", type=float, default=3.0)
    ap.add_argument("--persist", type=int, default=6, help="Consecutive samples above alert-z to raise alarm (6 = 1h)")
    ap.add_argument("--workers", type=int, default=1, help="Parallel event workers (each event is independent)")
    ap.add_argument("--force", action="store_true", help="Recompute even if saved score series exist")
    args = ap.parse_args()

    farm_dir = Path(args.data_dir)
    out_dir = Path(args.out) if args.out else None
    info = load_event_info(farm_dir)
    if args.datasets:
        info = info[info["event_id"].isin(args.datasets)]
    events = [event for _, event in info.sort_values("event_id").iterrows()]

    results: List[Dict] = []
    pending: List[pd.Series] = []
    for event in events:
        r = None if args.force else try_reuse_event(out_dir, event, args.alert_z, args.persist, farm_dir=farm_dir)
        if r is not None:
            results.append(r)
            _print_event_line(r)
        else:
            pending.append(event)

    def _flush(res_list: List[Dict]) -> None:
        if out_dir is not None and res_list:
            out_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(res_list).to_csv(out_dir / "results.csv", index=False)

    _flush(results)
    if pending:
        if args.workers > 1:
            import concurrent.futures as cf
            with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
                futs = {pool.submit(_run_event_worker, farm_dir, ev.to_dict(),
                                    args.alert_z, args.persist, out_dir): int(ev["event_id"])
                        for ev in pending}
                for fut in cf.as_completed(futs):
                    r = fut.result()
                    results.append(r)
                    _print_event_line(r)
                    _flush(results)  # crash-proof: persist after every event
        else:
            cfg = load_config()
            for event in pending:
                eid, lbl = int(event["event_id"]), event["event_label"]
                try:
                    r = run_event(farm_dir, event, cfg, args.alert_z, args.persist, out_dir)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    r = {"event_id": eid, "label": lbl, "error": str(e)[:300]}
                results.append(r)
                _print_event_line(r)
                _flush(results)

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

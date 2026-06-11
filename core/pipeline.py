"""ACM scoring pipeline — the product's single ML entry point.

One call scores one asset's window against its own history, fully
unsupervised, identical for any tabular sensor data (wind, pumps, motors,
compressors — anything with a timestamp index and numeric channels):

    result = score_asset(train_raw, score_raw, train_status, score_status)

Stages (all self-contained, no SQL, no services):
  1. channel roles      data-verified pre-derived statistic detection
  2. features           Polars rolling features on primary channels (float32)
  3. interleaved split  detectors fit on ~80%, calibration on held-out blocks
                        distributed across the WHOLE history (a chronological
                        tail holdout bakes pre-fault degradation into "normal")
  4. detectors          AR1, PCA-SPE/T2, IForest, GMM, OMR
  5. calibration        production calibration stage (adaptive clip,
                        contamination filter) on the held-out blocks
  6. fusion             correlation-discounted weighted fusion, auto-tuned
  7. alarm rules        self-tuned sustained/rate/per-head/availability rules
                        with the self-distrust gate (core.alarm_rules)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from core import detector_orchestrator as orch
from core import fuse
from core.alarm_rules import AlarmDecision, apply_alarm_rules
from core.fast_features import build_features_for_pipeline, detect_channel_roles
from core.ml_defaults import ML_DEFAULTS

# raw score column -> calibrated z column
Z_MAP = [
    ("ar1_raw", "ar1_z"),
    ("pca_spe", "pca_spe_z"),
    ("pca_t2", "pca_t2_z"),
    ("iforest_raw", "iforest_z"),
    ("gmm_raw", "gmm_z"),
    ("omr_raw", "omr_z"),
]
Z_COLS = [z for _, z in Z_MAP]


@dataclass
class PipelineResult:
    """Everything downstream needs: timeline, per-head z, decision, log."""
    ts: pd.DatetimeIndex
    fused: np.ndarray
    scores: pd.DataFrame                 # per-head calibrated z (Z_COLS)
    train_fused: Optional[np.ndarray]
    head_z_train: Dict[str, np.ndarray]
    decision: AlarmDecision
    score_status: Optional[np.ndarray]
    runlog: List[Dict] = field(default_factory=list)
    runtime_s: float = 0.0


def score_asset(
    train_raw: pd.DataFrame,
    score_raw: pd.DataFrame,
    train_status: Optional[np.ndarray] = None,
    score_status: Optional[np.ndarray] = None,
    cfg: Optional[dict] = None,
    log: Optional[Callable[[str, str], None]] = None,
) -> PipelineResult:
    """Score one asset window against its own unlabelled history.

    train_raw/score_raw: numeric sensor frames with a DatetimeIndex.
    *_status: optional SCADA operating-status codes (0/2 = normal operation);
              enables the availability rule and status-aware evaluation.
    """
    t0 = time.time()
    cfg = cfg if cfg is not None else dict(ML_DEFAULTS)
    runlog: List[Dict] = []

    def _log(stage: str, message: str, level: str = "INFO") -> None:
        runlog.append({"ts": pd.Timestamp.now().isoformat(sep=" ", timespec="seconds"),
                       "level": level, "stage": stage, "message": message})
        if log:
            log(stage, message)

    # 1. channel roles (data-verified; raw feeds pass through untouched)
    roles = detect_channel_roles(train_raw)
    derived_cols = roles["derived"]
    _log("channels", f"{len(roles['primary'])} primary, {len(derived_cols)} "
                     f"data-verified derived of {train_raw.shape[1]} channels")

    # 2. features (engineer primary channels only; derived join raw; float32).
    # WARM-UP CONTEXT: rolling features on a fresh score window produce junk
    # for the first `window` samples (rolling stats over 1-2 points). Prepend
    # the train tail so every score sample has a full window behind it, then
    # slice the warm-up off.
    feat_win = int((cfg.get("features", {}) or {}).get("window", 16))
    warm = min(len(train_raw), feat_win * 2)
    score_ctx = pd.concat([train_raw.iloc[-warm:], score_raw])
    train_feat, score_feat = build_features_for_pipeline(
        train_raw.drop(columns=derived_cols), score_ctx.drop(columns=derived_cols), cfg)
    score_feat = score_feat.iloc[warm:]
    if derived_cols:
        train_feat = pd.concat([train_feat, train_raw[derived_cols]], axis=1)
        score_feat = pd.concat([score_feat, score_raw[derived_cols]], axis=1)
    train_feat = train_feat.astype(np.float32)
    score_feat = score_feat.astype(np.float32)
    _log("features", f"matrix {train_feat.shape[0]}x{train_feat.shape[1]} in {time.time()-t0:.0f}s")

    # 3. interleaved out-of-sample calibration split
    holdout_frac = float((cfg.get("thresholds", {}) or {}).get("calibration_holdout_frac", 0.2))
    stride = max(2, int(round(1.0 / max(holdout_frac, 1e-6))))
    # block size adapts so even short histories yield >= ~8 holdout blocks
    block = int(np.clip(len(train_feat) // (stride * 8), feat_win * 2, 432))
    idx = np.arange(len(train_feat))
    calib_mask = (idx // block) % stride == (stride - 1)
    fit_feat = train_feat.iloc[~calib_mask]
    calib_feat = train_feat.iloc[calib_mask]

    # 4. detectors
    t_fit = time.time()
    det = orch.fit_all_detectors(
        train=fit_feat, cfg=cfg,
        ar1_enabled=True, pca_enabled=True, iforest_enabled=True,
        gmm_enabled=True, omr_enabled=True,
    )
    _log("fit", f"detectors fitted in {time.time()-t_fit:.0f}s")
    det_kwargs = dict(
        ar1_detector=det.get("ar1_detector"), pca_detector=det.get("pca_detector"),
        iforest_detector=det.get("iforest_detector"), gmm_detector=det.get("gmm_detector"),
        omr_detector=det.get("omr_detector"),
    )
    score_frame, omr_contrib = orch.score_all_detectors(score_feat, **det_kwargs)

    # 5. production calibration on the held-out blocks
    flags = {f"{k}_enabled": True for k in ("ar1", "pca", "iforest", "gmm", "omr")}
    cal = fuse.run_calibration_stage(
        train=calib_feat, frame=score_frame, cfg=cfg,
        regime_quality_ok=False, train_regime_labels=None, score_regime_labels=None,
        pca_train_spe=None, pca_train_t2=None,
        detectors=det, detector_flags=flags,
        cached_calibration_params=None, saved_model_version=None,
        score_all_detectors_fn=orch.score_all_detectors,
        calibrate_all_detectors_fn=orch.calibrate_all_detectors,
    )
    score_frame, calib_frame = cal.frame, cal.train_frame
    for raw_col, z_col in Z_MAP:
        c = cal.calibrators_dict.get(z_col)
        if c is not None and raw_col in calib_frame.columns:
            calib_frame[z_col] = c.transform(calib_frame[raw_col].to_numpy(copy=False))

    # 6. fusion
    fusion = fuse.run_fusion_pipeline(
        frame=score_frame, train_frame=calib_frame,
        score_data=score_feat, train_data=calib_feat,
        cfg=cfg, omr_contributions=omr_contrib,
    )
    fused = np.asarray(fusion.fused_scores, dtype=np.float64)
    train_fused = np.asarray(fusion.train_fused, dtype=np.float64) \
        if fusion.train_fused is not None else None

    head_z_score = {z: score_frame[z].to_numpy() for _, z in Z_MAP if z in score_frame.columns}
    head_z_train = {z: calib_frame[z].to_numpy() for _, z in Z_MAP if z in calib_frame.columns}

    # 7. alarm rules (self-tuned, label-free)
    decision = apply_alarm_rules(
        fused=fused, train_fused=train_fused,
        score_status=score_status, train_status=train_status,
        head_z_score=head_z_score, head_z_train=head_z_train,
    )
    _log("rules", f"alert_z={decision.alert_z:.2f} persist={decision.persist} "
                  f"fired={decision.rule_fired or '-'}")
    if decision.distrusted:
        _log("rules", f"self-distrust gate discarded: {decision.distrusted}", level="WARN")

    scores = pd.DataFrame({z: head_z_score.get(z, np.full(len(fused), np.nan))
                           for z in Z_COLS}, index=score_frame.index)
    return PipelineResult(
        ts=pd.DatetimeIndex(score_frame.index), fused=fused, scores=scores,
        train_fused=train_fused, head_z_train=head_z_train, decision=decision,
        score_status=score_status, runlog=runlog, runtime_s=round(time.time() - t0, 1),
    )

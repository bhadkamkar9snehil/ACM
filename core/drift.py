# core/drift.py
"""
Change-point and drift detection module.

Implements online detectors to identify subtle but persistent shifts in a time series,
typically the fused anomaly score.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any, Dict
from pathlib import Path

from . import fuse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ---------- timestamp parsing helpers (no parse_dates; UTC-safe) ----------
def _to_datetime_mixed(s):
    try:
        # pandas >= 2.1: fast mixed-parser
        return pd.to_datetime(s, format="mixed", utc=True, errors="coerce")
    except TypeError:
        # Older pandas: fallback
        return pd.to_datetime(s, utc=True, errors="coerce")

def _read_scores_csv(p: Path) -> pd.DataFrame:
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, dtype={"timestamp": "string"})
    df["timestamp"] = _to_datetime_mixed(df["timestamp"])
    df = df.set_index("timestamp")
    return df[~df.index.isna()]


class CUSUMDetector:
    """
    Online change-point detection using the CUSUM algorithm.
    Detects small, sustained drifts from a baseline mean.
    """
    def __init__(self, threshold: float = 2.0, drift: float = 0.1):
        self.threshold = threshold
        self.drift = drift
        self.mean = 0.0
        self.std = 1.0
        self.sum_pos = 0.0
        self.sum_neg = 0.0

    def fit(self, x: np.ndarray) -> "CUSUMDetector":
        self.mean = np.nanmean(x)
        self.std = np.nanstd(x)
        if not np.isfinite(self.std) or self.std < 1e-9:
            self.std = 1.0
        return self

    def score(self, x: np.ndarray) -> np.ndarray:
        scores = np.zeros_like(x, dtype=np.float32)
        x_norm = (x - self.mean) / self.std
        for i, val in enumerate(x_norm):
            self.sum_pos = max(0.0, self.sum_pos + val - self.drift)
            self.sum_neg = max(0.0, self.sum_neg - val - self.drift)
            scores[i] = max(self.sum_pos, self.sum_neg)
        return scores


def compute(score_df: pd.DataFrame, score_out: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes drift and change-point scores on the fused anomaly score.
    """
    frame = score_out["frame"]
    if "fused" not in frame.columns:
        return score_out

    fused_score = frame["fused"].to_numpy(copy=False)

    # CUSUM detector for online change-point detection
    drift_cfg = cfg.get("drift", {}) or {}
    cusum_cfg = (drift_cfg.get("cusum", {}) or {})
    detector = CUSUMDetector(
        threshold=float(cusum_cfg.get("threshold", 2.0)),
        drift=float(cusum_cfg.get("drift", 0.1)),
    ).fit(fused_score)  # self-calibrates on the entire series for now

    frame["cusum_raw"] = detector.score(fused_score)

    # Calibrate the CUSUM score to a z-score for fusion/reporting
    cal_cusum = fuse.ScoreCalibrator(q=0.98).fit(frame["cusum_raw"].to_numpy(copy=False))
    frame["cusum_z"] = cal_cusum.transform(frame["cusum_raw"].to_numpy(copy=False))

    score_out["frame"] = frame
    return score_out


def run(ctx: Any) -> Dict[str, Any]:
    """
    Reporting hook for the drift module.
    Generates a plot of the CUSUM score over time.
    """
    sc_path = ctx.run_dir / "scores.csv"
    sc = _read_scores_csv(sc_path)
    if sc.empty:
        return {"module": "drift", "plots": [], "tables": [], "metrics": {}}

    plots = []
    # Corrected: The drift score is now named 'cusum_z' in scores.csv
    drift_col = "cusum_z" if "cusum_z" in sc.columns else "drift_z"
    if drift_col in sc.columns:
        try:
            fig, ax = plt.subplots(figsize=(12, 4))
            sc[drift_col].plot(ax=ax, linewidth=1)
            ax.set_title("CUSUM Drift Score (Z-score)")
            ax.set_xlabel("")
            ax.grid(alpha=0.3)
            plt.tight_layout()
            p = ctx.plots_dir / "drift_cusum_score.png"
            fig.savefig(p, dpi=144, bbox_inches="tight")
            plt.close(fig)
            plots.append({
                "title": "CUSUM Drift Score",
                "path": str(p),
                "caption": "CUSUM score on the fused anomaly signal."
            })
        except Exception:
            # Ignore plotting errors
            pass

    return {"module": "drift", "plots": plots, "tables": [], "metrics": {}}

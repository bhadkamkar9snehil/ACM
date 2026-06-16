"""Self-tuned alarm rules — ACM's decision layer.

Every threshold is derived from the asset's OWN unlabelled history; no labels,
no per-site tuning. Four OR-combined rules plus a self-distrust gate:

  sustained    fused z holds above a holdout-quantile level longer than the
               healthy history ever produced (step-change faults)
  rate         trailing-24h fraction of high-z samples exceeds 1.5x the worst
               healthy day (intermittent faults that spike under load)
  per-head     each detector self-tunes its own rate rule over a 7-day window
               (faults that live in a single head)
  availability continuous unplanned non-operation beyond 48h — a failed asset
               is parked; the outage IS the symptom
  distrust     any behaviour rule claiming the majority of a multi-week window
               is a broken baseline, not a detection: discarded

Validated against CARE-to-Compare (95 labelled wind-farm events) without ever
showing the rules a label.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

NORMAL_STATUS = {0, 2}  # normal operation / idling

ALERT_Z_FLOOR = 3.0
SAFETY = 1.5
DISTRUST_COVERAGE = 0.5

# Rule horizons are defined in TIME and converted to sample counts from the
# asset's own cadence. Sample-count constants silently broke semantics off
# the 10-minute SCADA cadence: at 1 Hz, a "24h" 144-sample window was 2.4
# minutes. Defaults reproduce the validated 10-min numbers exactly
# (persist 6, rate 144, head 1008, avail 288).
PERSIST_FLOOR_S = 3600.0          # 1h
RATE_WINDOW_S = 24 * 3600.0       # 24h
HEAD_RATE_WINDOW_S = 7 * 86400.0  # 7d
AVAIL_RUN_FLOOR_S = 48 * 3600.0   # 48h
MAX_PERSIST_S = 12 * 3600.0       # 12h cap for the sustained rule
DEFAULT_CADENCE_S = 600.0


def _samples(seconds: float, cadence_s: float, floor: int = 3) -> int:
    return max(floor, int(round(seconds / max(cadence_s, 1e-9))))


def longest_run(mask: np.ndarray) -> int:
    longest = streak = 0
    for a in mask:
        streak = streak + 1 if a else 0
        longest = max(longest, streak)
    return longest


def sustained_alarm_mask(values: np.ndarray, threshold: float, persist: int) -> np.ndarray:
    """True where values >= threshold has held for >= persist consecutive samples."""
    above = values >= threshold
    if persist <= 1:
        return above
    run = np.zeros(len(above), dtype=int)
    streak = 0
    for i, a in enumerate(above):
        streak = streak + 1 if a else 0
        run[i] = streak
    return run >= persist


def rolling_rate(values: np.ndarray, z0: float, window: int = 144) -> np.ndarray:
    """Trailing fraction of samples >= z0 over `window` samples."""
    above = (np.asarray(values, dtype=np.float64) >= z0).astype(float)
    return pd.Series(above).rolling(window, min_periods=window // 2).mean().to_numpy()


def self_tune_alarm_rule(
    train_fused: Optional[np.ndarray],
    alert_z_floor: float = ALERT_Z_FLOOR,
    persist_floor: int = 6,
    target_fp: float = 0.001,
    max_persist: int = 72,
) -> tuple[float, int]:
    """Lowest holdout-quantile threshold whose implied persistence (1.5x the
    longest healthy excursion) stays physically sensible. Contamination in the
    history makes the rule conservative, never poisoned."""
    if train_fused is None or len(train_fused) < 100:
        return alert_z_floor, persist_floor
    tf = np.asarray(train_fused, dtype=np.float64)
    tf = tf[np.isfinite(tf)]
    if tf.size < 100:
        return alert_z_floor, persist_floor
    for q in (0.98, 0.99, 0.995, 0.999):
        thr = max(alert_z_floor, float(np.quantile(tf, q)))
        persist = max(persist_floor, int(longest_run(tf >= thr) * SAFETY) + 1)
        if persist <= max_persist:
            return thr, persist
    thr = max(alert_z_floor, float(np.quantile(tf, 1.0 - target_fp)))
    return thr, max(persist_floor, longest_run(tf >= thr) + 1)


@dataclass
class AlarmDecision:
    """Label-free alarm decision for one scored window."""
    alarm: np.ndarray                      # combined mask
    alarm_sustained: np.ndarray
    alarm_rate: np.ndarray
    alarm_avail: np.ndarray
    alarm_heads: np.ndarray
    alert_z: float = ALERT_Z_FLOOR
    persist: int = 6
    rate_z0: float = ALERT_Z_FLOOR
    rate_thr: float = float("nan")
    avail_run_thr: Optional[int] = None
    heads_fired: List[str] = field(default_factory=list)
    distrusted: List[str] = field(default_factory=list)
    rules_diagnostic: Dict = field(default_factory=dict)

    @property
    def rule_fired(self) -> str:
        s = ("sustained" if self.alarm_sustained.any() else "") + \
            ("+rate" if self.alarm_rate.any() else "") + \
            ("+avail" if self.alarm_avail.any() else "") + \
            (("+heads:" + ",".join(self.heads_fired)) if self.heads_fired else "") + \
            (("(distrusted:" + ";".join(self.distrusted) + ")") if self.distrusted else "")
        return s


def apply_alarm_rules(
    fused: np.ndarray,
    train_fused: Optional[np.ndarray],
    score_status: Optional[np.ndarray] = None,
    train_status: Optional[np.ndarray] = None,
    head_z_score: Optional[Dict[str, np.ndarray]] = None,
    head_z_train: Optional[Dict[str, np.ndarray]] = None,
    alert_z_floor: float = ALERT_Z_FLOOR,
    cadence_s: float = DEFAULT_CADENCE_S,
) -> AlarmDecision:
    """Run all self-tuned rules over one scored window. Fully unsupervised.

    cadence_s: sampling interval of the data; all time-defined horizons are
    converted to sample counts with it.
    """
    n = len(fused)
    persist_floor = _samples(PERSIST_FLOOR_S, cadence_s)
    # Horizons longer than the scored window are structurally dead (all-NaN
    # rolling output). Cap to the data so the rules stay alive on short
    # windows; the 1h persistence floor — ACM's declared detection floor for
    # DEVELOPING faults — is never weakened.
    rate_window = min(_samples(RATE_WINDOW_S, cadence_s, floor=12), max(12, n // 4))
    head_window = min(_samples(HEAD_RATE_WINDOW_S, cadence_s, floor=24), max(24, n // 3))
    avail_floor = _samples(AVAIL_RUN_FLOOR_S, cadence_s, floor=12)
    max_persist = _samples(MAX_PERSIST_S, cadence_s, floor=persist_floor)
    alert_z, persist = self_tune_alarm_rule(train_fused, alert_z_floor, persist_floor,
                                            max_persist=max_persist)
    alarm_sustained = sustained_alarm_mask(fused, alert_z, persist)

    # z0 is the universal "clearly elevated" level on the CALIBRATED scale:
    # calibration already standardizes detectors, so re-deriving z0 from the
    # holdout's p99 (a 12th-largest-of-1200 statistic) was fragile double
    # tuning that blinded the rule whenever the holdout had a few odd hours.
    # Only the RATE threshold self-tunes.
    rate_thr, z0 = float("nan"), alert_z_floor
    alarm_rate = np.zeros(n, dtype=bool)
    rate_n = int(np.isfinite(train_fused).sum()) if train_fused is not None else 0
    diag: Dict = {"rate": {"active": rate_n > 500, "train_n": rate_n},
                  "per_head": {}}
    if rate_n > 500:
        tf = np.asarray(train_fused, dtype=np.float64)
        tf = tf[np.isfinite(tf)]
        base = float(np.nanmax(rolling_rate(tf, z0, window=rate_window)))
        # multiplicative margin alone gives no headroom when healthy base
        # rates are small (4% -> 6%): benign novelty grazes it. Additive +5pp
        # headroom; genuine faults run at 30-50%+ rates.
        rate_thr = float(np.clip(base * SAFETY + 0.05, 0.05, 0.9))
        score_rate = np.nan_to_num(rolling_rate(fused, z0, window=rate_window), nan=0.0)
        alarm_rate = sustained_alarm_mask(score_rate, rate_thr, persist_floor)
        diag["rate"]["thr"] = rate_thr

    avail_run_thr = None
    alarm_avail = np.zeros(n, dtype=bool)
    if train_status is not None and score_status is not None and len(train_status) > 1000:
        nonop_train = ~np.isin(np.asarray(train_status), list(NORMAL_STATUS))
        stops, run = [], 0
        for a in nonop_train:
            if a:
                run += 1
            elif run:
                stops.append(run); run = 0
        if run:
            stops.append(run)
        # p95 of stop durations only when estimable (>=20 stops); with few
        # stops the max IS the prior fault's outage and would poison the bar.
        p95_stop = float(np.percentile(stops, 95)) if len(stops) >= 20 else 0.0
        avail_run_thr = max(avail_floor, int(p95_stop * SAFETY) + 1)
        nonop_score = ~np.isin(np.asarray(score_status), list(NORMAL_STATUS))
        run = 0
        for i, a in enumerate(nonop_score):
            run = run + 1 if a else 0
            if run >= avail_run_thr:
                alarm_avail[i] = True

    heads_fired: List[str] = []
    alarm_heads = np.zeros(n, dtype=bool)
    if head_z_score and head_z_train:
        for name, z_tr in head_z_train.items():
            z_sc = head_z_score.get(name)
            if z_sc is None or len(z_sc) != n:
                continue
            ztr = np.asarray(z_tr, dtype=np.float64)
            ztr = ztr[np.isfinite(ztr)]
            if ztr.size < 500:
                diag["per_head"][name] = {"active": False, "train_n": int(ztr.size)}
                continue
            z0_h = alert_z_floor
            base_h = float(np.nanmax(rolling_rate(ztr, z0_h, window=head_window)))
            thr_h = float(np.clip(base_h * SAFETY + 0.05, 0.05, 0.9))
            r_sc = np.nan_to_num(rolling_rate(np.asarray(z_sc, dtype=np.float64), z0_h,
                                              window=head_window), nan=0.0)
            mask_h = sustained_alarm_mask(r_sc, thr_h, persist_floor)
            diag["per_head"][name] = {"active": True, "train_n": int(ztr.size), "thr": thr_h}
            if mask_h.any():
                heads_fired.append(name)
                alarm_heads |= mask_h

    # SELF-DISTRUST: a drifted baseline alarms from the very START of the
    # window; a genuine sustained fault has an ONSET (a quiet prefix).
    # Distrust a behaviour rule only when it claims the majority of the
    # window AND never left a quiet prefix. "Start" is each rule's first
    # EVALUABLE sample (rolling statistics cannot fire before their window
    # fills). Availability exempt: a failed asset IS down most of the window.
    def _broken_baseline(mask: np.ndarray, eval_start: int) -> bool:
        if mask.mean() <= DISTRUST_COVERAGE:
            return False
        first = int(np.argmax(mask))
        return first <= eval_start + max(1, int(0.05 * n))

    distrusted: List[str] = []
    if _broken_baseline(alarm_sustained, persist):
        distrusted.append("sustained"); alarm_sustained = np.zeros(n, dtype=bool)
    if _broken_baseline(alarm_rate, rate_window // 2 + persist_floor):
        distrusted.append("rate"); alarm_rate = np.zeros(n, dtype=bool)
    if _broken_baseline(alarm_heads, head_window // 2 + persist_floor):
        distrusted.append("heads:" + ",".join(heads_fired))
        heads_fired, alarm_heads = [], np.zeros(n, dtype=bool)

    return AlarmDecision(
        alarm=alarm_sustained | alarm_rate | alarm_avail | alarm_heads,
        alarm_sustained=alarm_sustained, alarm_rate=alarm_rate,
        alarm_avail=alarm_avail, alarm_heads=alarm_heads,
        alert_z=alert_z, persist=persist, rate_z0=z0, rate_thr=rate_thr,
        avail_run_thr=avail_run_thr, heads_fired=heads_fired, distrusted=distrusted,
        rules_diagnostic=diag,
    )

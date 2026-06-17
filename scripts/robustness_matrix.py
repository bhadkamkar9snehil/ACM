#!/usr/bin/env python3
"""
ACM robustness matrix — the ML-completeness instrument.

Definition under test: confidence in PRE-DETECTING abnormalities without
raising false alarms, across varied asset kinds, on RAW sensor data.

Asset archetypes (all raw channels, deliberately different physics):
  turbine         load-driven with daily cycle (temps, vibration, flow)
  compressor      suction/discharge pressures, discharge temp tracks ratio,
                  motor current, duty cycling
  heat_exchanger  inlet/outlet temps on two circuits, flows, weekly demand
  noisy_process   two-regime process with switching and heavy noise

Fault archetypes injected into the SCORE window (never the history):
  drift           one channel ramps away from its physics (bearing heat-up)
  corr_break      one channel stops following the others (coupling/sensor)
  intermittent    load-correlated spiking (looseness under stress)
  stuck           channel freezes at its last value (dead sensor)
  step            sudden persistent offset (calibration jump / partial fail)

Each (archetype x fault) runs over multiple seeds, plus clean runs per
archetype. Verdict: ML-COMPLETE requires detection >= 90% over fault runs
AND >= 90% of clean runs with alarm coverage < 2%.

Usage:
  python scripts/robustness_matrix.py [--seeds 3] [--workers 3] [--out matrix.csv]
"""
from __future__ import annotations

# Cap BLAS threads before numpy is imported anywhere in this process: forking
# a ProcessPoolExecutor worker while OpenBLAS holds a thread-pool lock in the
# parent can deadlock the child permanently. Must run before any numpy import.
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import argparse
import sys
from pathlib import Path
from typing import Callable, Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.pipeline import score_asset  # noqa: E402

TRAIN_N, SCORE_N = 6000, 1500  # ~6 weeks history + ~10 days scoring @10min


# ------------------------------------------------------------ archetypes --
def turbine(n: int, seed: int, phase0: int = 0) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    ph = (np.arange(n) + phase0) * 2 * np.pi / 144
    load = 50 + 30 * np.sin(ph) + rng.normal(0, 3, n)
    amb = 15 + 5 * np.sin(ph / 6) + rng.normal(0, 0.5, n)
    return pd.DataFrame({
        "load": load, "ambient": amb,
        "temp_a": 25 + amb + 0.5 * load + rng.normal(0, 1.5, n),
        "temp_b": 23 + amb + 0.48 * load + rng.normal(0, 1.5, n),
        "vibration": 1.0 + 0.01 * load + rng.normal(0, 0.08, n),
        "flow": 100 + 0.8 * load + rng.normal(0, 4, n),
    })


def compressor(n: int, seed: int, phase0: int = 0) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    duty = (np.sin((np.arange(n) + phase0) * 2 * np.pi / 36) > -0.3).astype(float)  # 6h cycles
    duty = pd.Series(duty).rolling(6, min_periods=1).mean().to_numpy()
    p_suc = 2.0 + 0.2 * duty + rng.normal(0, 0.05, n)
    p_dis = 8.0 + 3.0 * duty + rng.normal(0, 0.15, n)
    ratio = p_dis / np.maximum(p_suc, 0.5)
    return pd.DataFrame({
        "p_suction": p_suc, "p_discharge": p_dis,
        "t_discharge": 60 + 12 * ratio + rng.normal(0, 2.0, n),
        "motor_current": 20 + 25 * duty + rng.normal(0, 1.0, n),
        "oil_temp": 45 + 8 * duty + rng.normal(0, 1.0, n),
    })


def heat_exchanger(n: int, seed: int, phase0: int = 0) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    demand = 0.6 + 0.3 * np.sin((np.arange(n) + phase0) * 2 * np.pi / 1008) + rng.normal(0, 0.03, n)
    f_hot = 50 * demand + rng.normal(0, 1.5, n)
    t_hot_in = 90 + 5 * demand + rng.normal(0, 1.0, n)
    eff = 0.7
    t_hot_out = t_hot_in - eff * (t_hot_in - 30) + rng.normal(0, 1.0, n)
    return pd.DataFrame({
        "flow_hot": f_hot, "t_hot_in": t_hot_in, "t_hot_out": t_hot_out,
        "t_cold_in": 28 + rng.normal(0, 0.8, n),
        "t_cold_out": 28 + eff * (t_hot_in - 30) * 0.8 + rng.normal(0, 1.0, n),
        "dp": 0.4 + 0.01 * f_hot + rng.normal(0, 0.03, n),
    })


def noisy_process(n: int, seed: int, phase0: int = 0) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    # two operating regimes with random switching every ~2 days
    switches = np.cumsum(rng.exponential(288, size=n // 144 + 4)).astype(int)
    regime = np.zeros(n)
    state = 0
    prev = 0
    for s in switches:
        if s >= n:
            break
        regime[prev:s] = state
        state = 1 - state
        prev = s
    regime[prev:] = state
    base = np.where(regime > 0, 80.0, 50.0)
    x1 = base + rng.normal(0, 5, n)
    return pd.DataFrame({
        "feed": x1,
        "level": 0.5 * x1 + rng.normal(0, 4, n),
        "temp": 100 + 0.3 * x1 + rng.normal(0, 3, n),
        "conc": 12 - 0.05 * x1 + rng.normal(0, 1.0, n),
    })


ARCHETYPES: Dict[str, Callable] = {
    "turbine": turbine, "compressor": compressor,
    "heat_exchanger": heat_exchanger, "noisy_process": noisy_process,
}


# ----------------------------------------------------------------- faults --
def inject(df: pd.DataFrame, fault: str, rng: np.random.RandomState) -> pd.DataFrame:
    n = len(df)
    col = df.columns[2 % len(df.columns)]   # a mid-importance channel per archetype
    i = df.columns.get_loc(col)
    half = n // 2
    spread = float(df[col].std()) or 1.0
    if fault == "drift":
        df.iloc[half:, i] += np.linspace(0, 8 * spread, n - half)
    elif fault == "corr_break":
        df.iloc[half:, i] = float(df[col].median()) + rng.normal(0, spread, n - half)
    elif fault == "intermittent":
        driver = df.iloc[:, 0].to_numpy()
        high = driver > np.quantile(driver, 0.7)
        bump = np.where(high, 4 * spread, 0.0)
        df.iloc[half:, i] += bump[half:]
    elif fault == "stuck":
        df.iloc[half:, i] = float(df[col].iloc[half])
    elif fault == "step":
        df.iloc[half:, i] += 6 * spread
    return df


FAULTS = ["drift", "corr_break", "intermittent", "stuck", "step"]


# ------------------------------------------------------------------- runs --
def one_run(arch: str, fault: str, seed: int) -> Dict:
    gen = ARCHETYPES[arch]
    train = gen(TRAIN_N, seed)
    score = gen(SCORE_N, seed + 1000, phase0=TRAIN_N)
    idx0 = pd.Timestamp("2025-01-01")
    train.index = pd.date_range(idx0, periods=TRAIN_N, freq="10min")
    score.index = pd.date_range(train.index[-1] + pd.Timedelta(minutes=10),
                                periods=SCORE_N, freq="10min")
    rng = np.random.RandomState(seed + 5000)
    if fault != "clean":
        score = inject(score, fault, rng)
    res = score_asset(train_raw=train, score_raw=score)
    alarm = res.decision.alarm
    half = SCORE_N // 2
    return {
        "archetype": arch, "fault": fault, "seed": seed,
        "detected": bool(alarm[half:].any()) if fault != "clean" else bool(alarm.any()),
        "alarm_frac": float(alarm.mean()),
        "false_early": bool(alarm[: half // 2].any()) if fault != "clean" else None,
        "rule": res.decision.rule_fired,
        "culprits": ",".join(res.culprits),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    jobs = [(a, f, s) for a in ARCHETYPES for f in FAULTS + ["clean"]
            for s in range(args.seeds)]
    rows: List[Dict] = []
    if args.workers > 1:
        import concurrent.futures as cf
        with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = [pool.submit(one_run, *j) for j in jobs]
            for fut in cf.as_completed(futs):
                rows.append(fut.result())
                r = rows[-1]
                print(f"--- {r['archetype']:15s} {r['fault']:12s} seed={r['seed']} "
                      f"{'DETECTED' if r['detected'] else ('quiet' if r['fault']=='clean' else 'MISSED')} "
                      f"frac={r['alarm_frac']:.3f}", flush=True)
    else:
        for j in jobs:
            rows.append(one_run(*j))

    df = pd.DataFrame(rows)
    faults = df[df.fault != "clean"]
    clean = df[df.fault == "clean"]
    det_rate = faults.detected.mean()
    clean_ok = (clean.alarm_frac < 0.02).mean()
    print("\n=========== ROBUSTNESS MATRIX (detection rate) ===========")
    print(faults.pivot_table(index="archetype", columns="fault",
                             values="detected", aggfunc="mean").round(2).to_string())
    print(f"\nclean runs with alarm coverage < 2%: {clean_ok:.0%} "
          f"(max coverage {clean.alarm_frac.max():.1%})")
    print(f"overall fault detection: {det_rate:.0%} over {len(faults)} runs")
    verdict = det_rate >= 0.90 and clean_ok >= 0.90
    print(f"\nML-COMPLETE VERDICT: {'PASS' if verdict else 'FAIL'} "
          f"(need detection >= 90% and >= 90% clean runs quiet)")
    if args.out:
        df.to_csv(args.out, index=False)
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
SKAB (Skoltech Anomaly Benchmark) cross-dataset generality check for ACM.

ACM was designed and tuned ONLY against CARE-to-Compare (wind-farm SCADA).
SKAB is a different domain entirely (1 Hz rotor/pump/valve testbed, 8 sensor
channels, point + collective anomalies) with its own published comparison
table (see external_benchmarks/SKAB/README.md "Proposed Leaderboard"). Running
ACM here with ZERO per-dataset tuning (same core.ml_defaults.ML_DEFAULTS as
CARE) is the generality test: does the self-tuning design hold up off the
dataset it was built against?

Train/test convention matches SKAB's own reference notebooks exactly
(core/utils.py: preprocess_skab) for apples-to-apples comparability with the
published table: first 400 rows of each experiment file = train, remainder =
score. anomaly-free.csv is NOT used (the literature's own reference pipeline
discards it too -- see external_benchmarks/SKAB/core/utils.py:load_preprocess_skab).

Dataset: https://github.com/waico/SKAB (cloned to external_benchmarks/SKAB)

Usage:
  python scripts/skab_benchmark.py --data-dir external_benchmarks/SKAB/data --out results/skab/
      [--workers 2] [--override '{"...": ...}']

Metrics mirror SKAB's own leaderboard definitions: F1, FAR (false alarm rate
over normal points), MAR (missing alarm rate over anomalous points) -- pooled
across all experiment files, point-wise binary classification.
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

from core.ml_defaults import ML_DEFAULTS   # noqa: E402
from core.pipeline import Z_COLS, score_asset  # noqa: E402

TRAIN_SIZE = 400  # matches external_benchmarks/SKAB/core/utils.py: preprocess_skab
LABEL_COLS = {"anomaly", "changepoint"}


def _deep_merge(base: dict, patch: dict) -> dict:
    result = dict(base)
    for k, v in patch.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def find_experiment_files(data_dir: Path) -> List[Path]:
    files = sorted(p for p in data_dir.rglob("*.csv") if "anomaly-free" not in p.name)
    return files


def load_experiment(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime")
    return df


def run_experiment(path: Path, out_dir: Optional[Path], cfg: Optional[dict] = None) -> Dict:
    name = path.relative_to(path.parents[1]).as_posix()  # e.g. "valve1/0.csv"
    df = load_experiment(path)
    sensor_cols = [c for c in df.columns if c not in LABEL_COLS]

    train_raw = df[sensor_cols].iloc[:TRAIN_SIZE].astype(float)
    score_raw = df[sensor_cols].iloc[TRAIN_SIZE:].astype(float)
    truth = df[["anomaly", "changepoint"]].iloc[TRAIN_SIZE:]

    res = score_asset(train_raw=train_raw, score_raw=score_raw, cfg=cfg)
    alarm = res.decision.alarm
    y_true = truth["anomaly"].to_numpy().astype(bool)
    n = min(len(alarm), len(y_true))
    alarm, y_true = alarm[:n], y_true[:n]

    tp = int(np.sum(alarm & y_true))
    fp = int(np.sum(alarm & ~y_true))
    fn = int(np.sum(~alarm & y_true))
    tn = int(np.sum(~alarm & ~y_true))

    cp_idx = np.flatnonzero(truth["changepoint"].to_numpy()[:n])
    alarm_idx = np.flatnonzero(alarm)
    delays_s = []
    for cp in cp_idx:
        later = alarm_idx[alarm_idx >= cp]
        if len(later):
            delays_s.append(float((truth.index[later[0]] - truth.index[cp]).total_seconds()))

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        series = pd.DataFrame({"datetime": res.ts, "fused": res.fused, "alarm": alarm[:len(res.ts)],
                               "anomaly_true": y_true[:len(res.ts)]})
        for z in Z_COLS:
            if z in res.scores.columns:
                series[z] = res.scores[z].to_numpy()
        safe_name = name.replace("/", "_").replace(".csv", "")
        series.to_csv(out_dir / f"exp_{safe_name}_scores.csv", index=False)

    return {
        "file": name, "n_score": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "rule_fired": res.decision.rule_fired or "-",
        "changepoints": len(cp_idx), "changepoints_caught": len(delays_s),
        "mean_detection_delay_s": float(np.mean(delays_s)) if delays_s else np.nan,
        "runtime_s": res.runtime_s,
    }


def _worker(path_str: str, out_dir: Optional[Path], cfg: Optional[dict]) -> Dict:
    try:
        return run_experiment(Path(path_str), out_dir, cfg)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"file": Path(path_str).name, "error": str(e)[:300]}


def summarize(results: List[Dict]) -> Dict:
    ok = [r for r in results if "error" not in r]
    if not ok:
        return {"error": "no successful experiments"}
    tp, fp, fn, tn = (sum(r[k] for r in ok) for k in ("tp", "fp", "fn", "tn"))
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * precision * recall / (precision + recall)
          if np.isfinite(precision) and np.isfinite(recall) and (precision + recall) > 0 else 0.0)
    far = fp / (fp + tn) if (fp + tn) else float("nan")   # false alarm rate over normal points
    mar = fn / (fn + tp) if (fn + tp) else float("nan")   # missing alarm rate over anomalous points
    total_cp = sum(r["changepoints"] for r in ok)
    caught_cp = sum(r["changepoints_caught"] for r in ok)
    delays = [r["mean_detection_delay_s"] for r in ok if np.isfinite(r.get("mean_detection_delay_s", np.nan))]
    return {
        "experiments": len(ok), "errors": len(results) - len(ok),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "F1": float(f1), "precision": float(precision) if np.isfinite(precision) else np.nan,
        "recall": float(recall) if np.isfinite(recall) else np.nan,
        "FAR_pct": round(far * 100, 2) if np.isfinite(far) else np.nan,
        "MAR_pct": round(mar * 100, 2) if np.isfinite(mar) else np.nan,
        "changepoints_total": total_cp, "changepoints_caught": caught_cp,
        "changepoint_recall": round(caught_cp / total_cp, 3) if total_cp else np.nan,
        "mean_detection_delay_s": round(float(np.mean(delays)), 1) if delays else np.nan,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--override", default=None, metavar="JSON")
    args = ap.parse_args()

    cfg: Optional[dict] = None
    if args.override:
        patch = json.loads(args.override)
        cfg = _deep_merge(dict(ML_DEFAULTS), patch)
        print(f"[ablation] ML_DEFAULTS patched with: {args.override}")

    data_dir, out_dir = Path(args.data_dir), Path(args.out) if args.out else None
    files = find_experiment_files(data_dir)
    print(f"Found {len(files)} SKAB experiment files (excluding anomaly-free.csv)")

    results: List[Dict] = []

    def _flush() -> None:
        if out_dir is not None and results:
            out_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(results).to_csv(out_dir / "results.csv", index=False)

    t0 = time.time()
    if args.workers > 1:
        import concurrent.futures as cf
        with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = [pool.submit(_worker, str(f), out_dir, cfg) for f in files]
            for fut in cf.as_completed(futs):
                r = fut.result()
                results.append(r)
                print(f"--- {r.get('file')}: "
                      f"{'ERROR ' + r['error'][:100] if 'error' in r else r.get('rule_fired')}", flush=True)
                _flush()
    else:
        for f in files:
            r = _worker(str(f), out_dir, cfg)
            results.append(r)
            print(f"--- {r.get('file')}: "
                  f"{'ERROR ' + r['error'][:100] if 'error' in r else r.get('rule_fired')}", flush=True)
            _flush()

    summary = summarize(results)
    print(f"\n================ SKAB BENCHMARK SUMMARY ({time.time()-t0:.0f}s) ================")
    print(json.dumps(summary, indent=2))
    if out_dir is not None:
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

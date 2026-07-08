#!/usr/bin/env python3
"""SMD (Server Machine Dataset) cross-dataset generality check for ACM.

ACM was designed and tuned ONLY against CARE-to-Compare (wind-farm SCADA). SMD
is a different domain (28 server machines, 1-minute cadence, 38 metrics/machine,
~5 weeks/machine) but matches ACM's actual target shape much better than SKAB
did: each machine has ~12.5 days of continuous training history (>> the 500
calibration samples ACM's rate/per-head rules need to arm) and labelled anomaly
segments average ~90 minutes (long enough to clear ACM's declared 1h sustained-
detection floor for a meaningful share of cases) -- see CLAUDE.md "Cross-Dataset
Generality Testing" for why SKAB (400-row training convention, sub-15-minute
anomalies) was rejected as a benchmark target instead of being "fixed" by
loosening ACM's alarm-rule design.

Running ACM here with ZERO per-dataset tuning (same core.ml_defaults.ML_DEFAULTS
as CARE) is the generality test: do the same self-tuned detectors + alarm rules
that work on wind-farm SCADA also produce real signal on a structurally
different but still "long-history industrial-style telemetry" domain?

Dataset: https://github.com/NetManAIOps/OmniAnomaly (ServerMachineDataset/, MIT
licensed), cloned to external_benchmarks/OmniAnomaly. No real timestamps are
provided -- a synthetic 1-minute-cadence DatetimeIndex is assigned per the
dataset's own documented sampling interval (confirmed: ~50,601 rows/machine /
5 weeks => 1.00 min/row).

SMD's own convention: first half of each machine's recording = train, second
half = test (NetManAIOps/OmniAnomaly README: "we divide it into two parts of
equal length for training and testing").

Usage:
  python scripts/smd_benchmark.py --data-dir external_benchmarks/OmniAnomaly/ServerMachineDataset \
      --out results/smd/ [--workers 2] [--override '{"...": ...}']

Metrics: point-wise precision/recall/F1 (the honest, unadjusted number) AND
the point-adjusted F1 commonly reported in the literature (OmniAnomaly, USAD,
Anomaly Transformer, TranAD, etc. all use point-adjustment: if any point in a
true anomaly segment is flagged, the whole segment counts as detected). Both
are reported -- point-adjustment is known to inflate F1 (see Kim et al. 2022,
"Towards a Rigorous Evaluation of Time-Series Anomaly Detection") and is
included only for direct comparability with published SMD numbers, not as
ACM's primary claim.
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

CADENCE_S = 60.0  # SMD documented sampling interval: 1 minute


def _deep_merge(base: dict, patch: dict) -> dict:
    result = dict(base)
    for k, v in patch.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def find_machines(data_dir: Path) -> List[str]:
    return sorted(p.stem for p in (data_dir / "train").glob("machine-*.txt"))


def _load_txt(path: Path, start: pd.Timestamp) -> pd.DataFrame:
    arr = np.loadtxt(path, delimiter=",")
    idx = pd.date_range(start, periods=len(arr), freq=f"{int(CADENCE_S)}s")
    cols = [f"m{i:02d}" for i in range(arr.shape[1])]
    return pd.DataFrame(arr, index=idx, columns=cols)


def load_machine(data_dir: Path, name: str) -> Dict:
    train = _load_txt(data_dir / "train" / f"{name}.txt", pd.Timestamp("2020-01-01"))
    test_start = train.index[-1] + pd.Timedelta(seconds=CADENCE_S)
    score = _load_txt(data_dir / "test" / f"{name}.txt", test_start)
    labels = np.loadtxt(data_dir / "test_label" / f"{name}.txt", delimiter=",").astype(bool)
    n = min(len(score), len(labels))
    return {"train": train, "score": score.iloc[:n], "labels": labels[:n]}


def _segments(mask: np.ndarray) -> List[tuple]:
    """Contiguous True runs as (start, end_inclusive) index pairs."""
    segs = []
    start = None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            segs.append((start, i - 1)); start = None
    if start is not None:
        segs.append((start, len(mask) - 1))
    return segs


def point_adjust(alarm: np.ndarray, y_true: np.ndarray) -> np.ndarray:
    """Standard literature point-adjustment: any hit inside a true segment
    marks the whole segment detected. Inflates F1 -- reported only for
    comparability with published SMD numbers (see module docstring)."""
    adj = alarm.copy()
    for s, e in _segments(y_true):
        if adj[s:e + 1].any():
            adj[s:e + 1] = True
    return adj


def run_machine(data_dir: Path, name: str, out_dir: Optional[Path], cfg: Optional[dict] = None) -> Dict:
    d = load_machine(data_dir, name)
    res = score_asset(train_raw=d["train"], score_raw=d["score"], cfg=cfg)
    alarm = res.decision.alarm
    y_true = d["labels"]
    n = min(len(alarm), len(y_true))
    alarm, y_true = alarm[:n], y_true[:n]

    tp = int(np.sum(alarm & y_true)); fp = int(np.sum(alarm & ~y_true))
    fn = int(np.sum(~alarm & y_true)); tn = int(np.sum(~alarm & ~y_true))

    adj = point_adjust(alarm, y_true)
    tp_a = int(np.sum(adj & y_true)); fp_a = int(np.sum(adj & ~y_true))
    fn_a = int(np.sum(~adj & y_true)); tn_a = int(np.sum(~adj & ~y_true))

    segs = _segments(y_true)
    seg_hits = sum(1 for s, e in segs if alarm[s:e + 1].any())

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        series = pd.DataFrame({"fused": res.fused, "alarm": alarm[:len(res.fused)],
                               "anomaly_true": y_true[:len(res.fused)]}, index=res.ts)
        for z in Z_COLS:
            if z in res.scores.columns:
                series[z] = res.scores[z].to_numpy()
        series.to_csv(out_dir / f"{name}_scores.csv")

    return {
        "machine": name, "n_score": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "tp_adj": tp_a, "fp_adj": fp_a, "fn_adj": fn_a, "tn_adj": tn_a,
        "rule_fired": res.decision.rule_fired or "-",
        "segments_total": len(segs), "segments_caught": seg_hits,
        "runtime_s": res.runtime_s,
    }


def _worker(data_dir_str: str, name: str, out_dir: Optional[Path], cfg: Optional[dict]) -> Dict:
    try:
        return run_machine(Path(data_dir_str), name, out_dir, cfg)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"machine": name, "error": str(e)[:300]}


def _f1(tp: int, fp: int, fn: int) -> tuple:
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * precision * recall / (precision + recall)
          if np.isfinite(precision) and np.isfinite(recall) and (precision + recall) > 0 else 0.0)
    return precision, recall, f1


def summarize(results: List[Dict]) -> Dict:
    ok = [r for r in results if "error" not in r]
    if not ok:
        return {"error": "no successful machines"}
    tp, fp, fn, tn = (sum(r[k] for r in ok) for k in ("tp", "fp", "fn", "tn"))
    tp_a, fp_a, fn_a, tn_a = (sum(r[k] for r in ok) for k in ("tp_adj", "fp_adj", "fn_adj", "tn_adj"))
    precision, recall, f1 = _f1(tp, fp, fn)
    precision_a, recall_a, f1_a = _f1(tp_a, fp_a, fn_a)
    total_seg = sum(r["segments_total"] for r in ok)
    caught_seg = sum(r["segments_caught"] for r in ok)
    return {
        "machines": len(ok), "errors": len(results) - len(ok),
        "pointwise": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                      "precision": round(precision, 4) if np.isfinite(precision) else np.nan,
                      "recall": round(recall, 4) if np.isfinite(recall) else np.nan,
                      "F1": round(f1, 4)},
        "point_adjusted": {"tp": tp_a, "fp": fp_a, "fn": fn_a, "tn": tn_a,
                           "precision": round(precision_a, 4) if np.isfinite(precision_a) else np.nan,
                           "recall": round(recall_a, 4) if np.isfinite(recall_a) else np.nan,
                           "F1": round(f1_a, 4)},
        "segments_total": total_seg, "segments_caught": caught_seg,
        "segment_recall": round(caught_seg / total_seg, 3) if total_seg else np.nan,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--machines", nargs="*", default=None)
    ap.add_argument("--override", default=None, metavar="JSON")
    args = ap.parse_args()

    cfg: Optional[dict] = None
    if args.override:
        patch = json.loads(args.override)
        cfg = _deep_merge(dict(ML_DEFAULTS), patch)
        print(f"[ablation] ML_DEFAULTS patched with: {args.override}")

    data_dir, out_dir = Path(args.data_dir), Path(args.out) if args.out else None
    names = args.machines if args.machines else find_machines(data_dir)
    print(f"Found {len(names)} SMD machines")

    results: List[Dict] = []

    def _flush() -> None:
        if out_dir is not None and results:
            out_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(results).to_csv(out_dir / "results.csv", index=False)

    t0 = time.time()
    if args.workers > 1:
        import concurrent.futures as cf
        with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = [pool.submit(_worker, str(data_dir), n, out_dir, cfg) for n in names]
            for fut in cf.as_completed(futs):
                r = fut.result()
                results.append(r)
                print(f"--- {r.get('machine')}: "
                      f"{'ERROR ' + r['error'][:100] if 'error' in r else r.get('rule_fired')}", flush=True)
                _flush()
    else:
        for n in names:
            r = _worker(str(data_dir), n, out_dir, cfg)
            results.append(r)
            print(f"--- {r.get('machine')}: "
                  f"{'ERROR ' + r['error'][:100] if 'error' in r else r.get('rule_fired')}", flush=True)
            _flush()

    summary = summarize(results)
    print(f"\n================ SMD BENCHMARK SUMMARY ({time.time()-t0:.0f}s) ================")
    print(json.dumps(summary, indent=2))
    if out_dir is not None:
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

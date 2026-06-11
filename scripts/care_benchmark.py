#!/usr/bin/env python3
"""
CARE-to-Compare benchmark for ACM (core.pipeline).

Validates the ONLY claim that matters: starting from t=0 with NO labels and
NO human intervention, does ACM alarm on known faults and stay quiet on
normal behaviour? Labels (event_info.csv) are touched ONLY by the evaluator.

Dataset: https://zenodo.org/records/15846963 (CARE_To_Compare)
Download: python scripts/download_care_dataset.py --dest ./care_data --farms A

Usage:
  python scripts/care_benchmark.py --data-dir ".../Wind Farm A" --out results/A
      [--datasets 40 68] [--workers 3] [--force]

Event-level KPI: PASS requires recall >= 0.80 and F1 >= 0.75.
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

from core.alarm_rules import NORMAL_STATUS, apply_alarm_rules  # noqa: E402
from core.pipeline import Z_COLS, score_asset                  # noqa: E402

META_COLS = {"time_stamp", "asset_id", "id", "train_test", "status_type_id"}


# ---------------------------------------------------------------- loading --
def load_event_info(farm_dir: Path) -> pd.DataFrame:
    info = pd.read_csv(farm_dir / "event_info.csv", sep=";")
    if "asset" not in info.columns and "asset_id" in info.columns:
        info = info.rename(columns={"asset_id": "asset"})
    info["event_start"] = pd.to_datetime(info["event_start"])
    info["event_end"] = pd.to_datetime(info["event_end"])
    return info


def sensor_frame(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in df.columns if c not in META_COLS]
    out = df[cols].apply(pd.to_numeric, errors="coerce")
    out.index = pd.DatetimeIndex(df["time_stamp"], name="EntryDateTime")
    return out.replace([np.inf, -np.inf], np.nan).dropna(axis=1, how="all")


# ------------------------------------------------------------- evaluation --
def evaluate(
    ts: pd.DatetimeIndex,
    fused: np.ndarray,
    alarm: np.ndarray,
    rule_fired: str,
    score_status: np.ndarray,
    event: pd.Series,
    extra: Dict,
) -> Dict:
    """Label-aware evaluation — the ONLY place labels are used."""
    label = str(event["event_label"])
    normal_op = np.isin(score_status, list(NORMAL_STATUS))
    result = {
        "event_id": int(event["event_id"]), "asset": int(event["asset"]),
        "label": label,
        "description": event.get("event_description") if isinstance(event.get("event_description"), str) else "",
        "rule_fired": rule_fired,
        "fused_max": float(np.nanmax(fused)), "alarm_frac": float(alarm.mean()),
        **extra,
    }
    if label == "anomaly":
        detected = bool(alarm.any())
        first = ts[alarm][0] if detected else None
        result.update({
            "detected": detected,
            "lead_time_h": float((event["event_start"] - first).total_seconds() / 3600.0) if first is not None else np.nan,
            "false_alarm_frac_normal_op": np.nan,
        })
    else:
        fp = alarm & normal_op
        result.update({
            "detected": bool(fp.any()),
            "lead_time_h": np.nan,
            "false_alarm_frac_normal_op": float(fp.sum() / max(normal_op.sum(), 1)),
        })
    return result


# --------------------------------------------------------------- per-event --
def run_event(farm_dir: Path, event: pd.Series, out_dir: Optional[Path]) -> Dict:
    eid = int(event["event_id"])
    df = pd.read_csv(farm_dir / "datasets" / f"{eid}.csv", sep=";")
    df["time_stamp"] = pd.to_datetime(df["time_stamp"])
    tr, sc = df[df["train_test"] == "train"], df[df["train_test"] == "prediction"]

    res = score_asset(
        train_raw=sensor_frame(tr), score_raw=sensor_frame(sc),
        train_status=tr["status_type_id"].to_numpy(),
        score_status=sc["status_type_id"].to_numpy(),
    )

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        series = pd.DataFrame({"time_stamp": res.ts, "fused": res.fused,
                               "status_type_id": res.score_status})
        for z in Z_COLS:
            series[z] = res.scores[z].to_numpy()
        series.to_csv(out_dir / f"event_{eid}_scores.csv", index=False)
        tf = pd.DataFrame({"train_fused": res.train_fused})
        for z, v in res.head_z_train.items():
            if len(v) == len(tf):
                tf[z] = v
        tf.to_csv(out_dir / f"event_{eid}_train_fused.csv", index=False)
        pd.DataFrame(res.runlog).to_csv(out_dir / f"event_{eid}_runlog.csv", index=False)

    d = res.decision
    return evaluate(res.ts, res.fused, d.alarm, d.rule_fired, res.score_status, event,
                    {"alert_z_eff": round(d.alert_z, 2), "persist_eff": d.persist,
                     "runtime_s": res.runtime_s, "reused": False})


def try_reuse_event(out_dir: Optional[Path], farm_dir: Path, event: pd.Series) -> Optional[Dict]:
    """Re-evaluate saved score series (rules are eval-only; crash-proof resume)."""
    if out_dir is None:
        return None
    eid = int(event["event_id"])
    s_path, t_path = out_dir / f"event_{eid}_scores.csv", out_dir / f"event_{eid}_train_fused.csv"
    if not (s_path.exists() and t_path.exists() and s_path.stat().st_size and t_path.stat().st_size):
        return None
    try:
        s = pd.read_csv(s_path, parse_dates=["time_stamp"])
        tf_df = pd.read_csv(t_path)
        raw = pd.read_csv(farm_dir / "datasets" / f"{eid}.csv", sep=";",
                          usecols=["train_test", "status_type_id"])
        d = apply_alarm_rules(
            fused=s["fused"].to_numpy(),
            train_fused=tf_df["train_fused"].to_numpy(),
            score_status=s["status_type_id"].to_numpy(),
            train_status=raw.loc[raw["train_test"] == "train", "status_type_id"].to_numpy(),
            head_z_score={z: s[z].to_numpy() for z in Z_COLS if z in s.columns},
            head_z_train={z: tf_df[z].to_numpy() for z in Z_COLS if z in tf_df.columns} or None,
        )
        r = evaluate(pd.DatetimeIndex(s["time_stamp"]), s["fused"].to_numpy(), d.alarm,
                     d.rule_fired, s["status_type_id"].to_numpy(), event,
                     {"alert_z_eff": round(d.alert_z, 2), "persist_eff": d.persist,
                      "runtime_s": 0.0, "reused": True})
        return r
    except Exception:
        return None


# ------------------------------------------------------------------- main --
def summarize(results: List[Dict]) -> Dict:
    res = pd.DataFrame([r for r in results if "error" not in r])
    if res.empty or "label" not in res.columns:
        return {"error": "no successful events"}
    an, no = res[res["label"] == "anomaly"], res[res["label"] == "normal"]
    tp, fn = int(an["detected"].sum()), int((~an["detected"].astype(bool)).sum())
    fp, tn = int(no["detected"].sum()), int((~no["detected"].astype(bool)).sum())
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * precision * recall / (precision + recall)
          if np.isfinite(precision) and np.isfinite(recall) and (precision + recall) > 0 else 0.0)
    early = an[an["lead_time_h"] > 0]
    kpi = bool(np.isfinite(recall) and recall >= 0.80 and f1 >= 0.75)
    return {
        "anomaly_events": len(an), "anomalies_detected": tp,
        "detected_before_event_start": int(len(early)),
        "median_lead_time_h": float(early["lead_time_h"].median()) if len(early) else np.nan,
        "normal_events": len(no), "normal_events_clean": tn,
        "event_precision": float(precision) if np.isfinite(precision) else np.nan,
        "event_recall": float(recall) if np.isfinite(recall) else np.nan,
        "event_f1": float(f1),
        "KPI": "PASS (recall>=0.80 and F1>=0.75)" if kpi else "FAIL (need recall>=0.80 and F1>=0.75)",
    }


def _print_event_line(r: Dict) -> None:
    if "error" in r:
        print(f"--- event {r.get('event_id')}: ERROR {r['error'][:120]}", flush=True)
        return
    tag = ("DETECTED" if r["detected"] else "MISSED") if r["label"] == "anomaly" else \
          ("FALSE ALARM" if r["detected"] else "clean")
    lead = f" lead={r['lead_time_h']:+.1f}h" if r["label"] == "anomaly" and r["detected"] else ""
    src = " [reused]" if r.get("reused") else f" ({r.get('runtime_s', 0)}s)"
    print(f"--- event {r['event_id']}: {tag}{lead} rule={r.get('rule_fired') or '-'}{src}", flush=True)


def _worker(farm_dir: Path, event_dict: Dict, out_dir: Optional[Path]) -> Dict:
    try:
        return run_event(farm_dir, pd.Series(event_dict), out_dir)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"event_id": int(event_dict.get("event_id", -1)),
                "label": str(event_dict.get("event_label", "?")), "error": str(e)[:300]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--datasets", nargs="*", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    farm_dir, out_dir = Path(args.data_dir), Path(args.out) if args.out else None
    info = load_event_info(farm_dir)
    if args.datasets:
        info = info[info["event_id"].isin(args.datasets)]
    events = [ev for _, ev in info.sort_values("event_id").iterrows()]

    results: List[Dict] = []

    def _flush() -> None:
        if out_dir is not None and results:
            out_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(results).to_csv(out_dir / "results.csv", index=False)

    pending = []
    for ev in events:
        r = None if args.force else try_reuse_event(out_dir, farm_dir, ev)
        (results.append(r), _print_event_line(r)) if r else pending.append(ev)
    _flush()

    if pending and args.workers > 1:
        import concurrent.futures as cf
        with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = [pool.submit(_worker, farm_dir, ev.to_dict(), out_dir) for ev in pending]
            for fut in cf.as_completed(futs):
                results.append(fut.result()); _print_event_line(results[-1]); _flush()
    else:
        for ev in pending:
            results.append(_worker(farm_dir, ev.to_dict(), out_dir))
            _print_event_line(results[-1]); _flush()

    summary = summarize(results)
    print("\n================ CARE BENCHMARK SUMMARY ================")
    print(json.dumps(summary, indent=2))
    if out_dir is not None:
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Download additional PUBLIC labelled-fault datasets and convert them to
acm_run-ready CSVs (timestamp + numeric channels), with a known_events.csv
of labelled fault windows for evaluation. Deliberately different machines
and physics than the CARE wind farms:

  skab      Water-circulation rig with a pump (SKAB, github.com/waico/SKAB).
            1 Hz, 8 channels. 35 experiment files with labelled anomalies +
            one anomaly-free training file. Faults: valve closures, rotor
            imbalance, cavitation.
  metropt3  Metro-train air compressor APU (UCI dataset 791). 15 signals over
            6 months, documented failure periods (Davari et al., Sci. Data).
            Adapter downsamples 1 Hz -> 1 min.

Usage:
  python scripts/download_validation_datasets.py --dataset skab --dest ./validation_data
  python scripts/acm_run.py --csv validation_data/skab/asset_skab.csv \
      --timestamp-col timestamp --score-from "<see known_events.csv>" --report skab.html
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

SKAB_BASE = "https://raw.githubusercontent.com/waico/SKAB/master/data"
SKAB_GROUPS = {"valve1": 16, "valve2": 4, "other": 15}
METROPT3_URL = "https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip"
# Failure periods documented in the MetroPT paper (Davari et al. 2022)
METROPT3_EVENTS = [
    ("2020-04-18 00:00", "2020-04-18 23:59", "air leak failure"),
    ("2020-05-29 23:30", "2020-05-30 06:00", "air leak failure"),
    ("2020-06-05 10:00", "2020-06-07 14:30", "air leak failure"),
    ("2020-07-15 14:30", "2020-07-15 19:00", "air leak failure"),
]


def fetch(url: str) -> bytes:
    print(f"  GET {url}", flush=True)
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def download_skab(dest: Path) -> None:
    out = dest / "skab"
    out.mkdir(parents=True, exist_ok=True)

    # anomaly-free file = the unlabelled training history
    train = pd.read_csv(io.BytesIO(fetch(f"{SKAB_BASE}/anomaly-free/anomaly-free.csv")), sep=";")
    train = train.rename(columns={"datetime": "timestamp"})

    events, frames = [], [train.assign(anomaly=0.0)]
    t_cursor = pd.to_datetime(train["timestamp"]).max()
    for group, count in SKAB_GROUPS.items():
        for i in range(count):
            try:
                df = pd.read_csv(io.BytesIO(fetch(f"{SKAB_BASE}/{group}/{i}.csv")), sep=";")
            except Exception as e:
                print(f"  skip {group}/{i}.csv ({e})")
                continue
            df = df.rename(columns={"datetime": "timestamp"})
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            # stitch experiments onto a continuous timeline after the train file
            shift = (t_cursor + pd.Timedelta(seconds=60)) - df["timestamp"].iloc[0]
            df["timestamp"] = df["timestamp"] + shift
            t_cursor = df["timestamp"].max()
            a = df[df["anomaly"] == 1]
            if len(a):
                events.append({"event_start": str(a["timestamp"].iloc[0]),
                               "event_end": str(a["timestamp"].iloc[-1]),
                               "description": f"SKAB {group} experiment {i}"})
            frames.append(df.drop(columns=["changepoint"], errors="ignore"))

    full = pd.concat(frames, ignore_index=True)
    labels = full.pop("anomaly")  # labels NEVER enter the model input file
    full.to_csv(out / "asset_skab.csv", index=False)
    pd.DataFrame(events).to_csv(out / "known_events.csv", index=False)
    pd.DataFrame({"timestamp": full["timestamp"], "anomaly": labels}).to_csv(
        out / "labels.csv", index=False)
    score_from = str(pd.to_datetime(train["timestamp"]).max())
    print(f"SKAB ready: {out}/asset_skab.csv ({len(full)} rows, "
          f"{len(events)} labelled fault windows)")
    print(f"  run: python scripts/acm_run.py --csv {out}/asset_skab.csv "
          f"--timestamp-col timestamp --score-from \"{score_from}\"")


def download_metropt3(dest: Path) -> None:
    out = dest / "metropt3"
    out.mkdir(parents=True, exist_ok=True)
    raw = fetch(METROPT3_URL)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        df = pd.read_csv(z.open(name))
    ts_col = "timestamp" if "timestamp" in df.columns else df.columns[1]
    df[ts_col] = pd.to_datetime(df[ts_col])
    df = df.rename(columns={ts_col: "timestamp"}).drop(
        columns=[c for c in ("Unnamed: 0",) if c in df.columns])
    # 1 Hz -> 1 min mean keeps 6 months tractable on a laptop
    df = df.set_index("timestamp").resample("1min").mean().dropna(how="all").reset_index()
    df.to_csv(out / "asset_metropt3.csv", index=False)
    pd.DataFrame([{"event_start": s, "event_end": e, "description": d}
                  for s, e, d in METROPT3_EVENTS]).to_csv(out / "known_events.csv", index=False)
    print(f"MetroPT-3 ready: {out}/asset_metropt3.csv ({len(df)} rows, "
          f"{len(METROPT3_EVENTS)} documented failures)")
    print(f"  run: python scripts/acm_run.py --csv {out}/asset_metropt3.csv "
          f"--timestamp-col timestamp --score-from \"2020-04-01\"")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", choices=["skab", "metropt3", "all"], default="skab")
    ap.add_argument("--dest", default="./validation_data")
    args = ap.parse_args()
    dest = Path(args.dest)
    if args.dataset in ("skab", "all"):
        download_skab(dest)
    if args.dataset in ("metropt3", "all"):
        download_metropt3(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Download public validation datasets and adapt them to ACM-ready CSV files.

The adapted CSV contract is intentionally narrow:
  - one timestamp column named "timestamp"
  - numeric sensor/process columns only
  - labels and known fault windows are written separately, never into the
    model input file

This script does not change ACM ingestion or ML behavior. It prepares ordinary
CSV assets that can be used by existing ACM paths.

Examples:
  python scripts/download_validation_datasets.py --dataset metropt3
  python scripts/download_validation_datasets.py --dataset cmapss --max-assets 20
  python scripts/download_validation_datasets.py --dataset all --dest data/public_datasets
  python scripts/acm_run.py --csv data/public_datasets/adapted/metropt3/asset_metropt3.csv --timestamp-col timestamp
"""
from __future__ import annotations

import argparse
import io
import json
import math
import shutil
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST = ROOT / "data" / "public_datasets"
HTTP_HEADERS = {"User-Agent": "ACM-validation-dataset-downloader/1.0"}

SKAB_BASE = "https://raw.githubusercontent.com/waico/SKAB/master/data"
SKAB_GROUPS = {"valve1": 16, "valve2": 4, "other": 15}
METROPT3_URL = "https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip"
CMAPSS_URL = "https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip"
MILLING_URL = "https://phm-datasets.s3.amazonaws.com/NASA/3.+Milling.zip"
BEARING_URL = "https://phm-datasets.s3.amazonaws.com/NASA/4.+Bearings.zip"
SMD_URL = "https://github.com/NetManAIOps/OmniAnomaly/archive/refs/heads/master.zip"
AI4I_URL = "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip"
SECOM_URL = "https://archive.ics.uci.edu/static/public/179/secom.zip"
BATADAL_TRAIN1_URL = "https://www.batadal.net/data/BATADAL_dataset03.csv"
BATADAL_TRAIN2_URL = "https://www.batadal.net/data/BATADAL_dataset04.csv"
TEP_API = "https://dataverse.harvard.edu/api/datasets/:persistentId?persistentId=doi:10.7910/DVN/6C3JR1"
TEP_FILE_API = "https://dataverse.harvard.edu/api/access/datafile/{file_id}"

METROPT3_EVENTS = [
    ("2020-04-18 00:00", "2020-04-18 23:59", "air leak failure"),
    ("2020-05-29 23:30", "2020-05-30 06:00", "air leak failure"),
    ("2020-06-05 10:00", "2020-06-07 14:30", "air leak failure"),
    ("2020-07-15 14:30", "2020-07-15 19:00", "air leak failure"),
]

BATADAL_TRAIN2_ATTACKS = [
    ("2016-09-13 23:00", "2016-09-16 00:00", "attack 1"),
    ("2016-09-26 11:00", "2016-09-27 10:00", "attack 2 unlabeled in source"),
    ("2016-10-09 09:00", "2016-10-11 20:00", "attack 3"),
    ("2016-10-29 19:00", "2016-11-02 16:00", "attack 4 partially labeled"),
    ("2016-11-26 17:00", "2016-11-29 04:00", "attack 5 partially labeled"),
    ("2016-12-06 07:00", "2016-12-10 04:00", "attack 6"),
    ("2016-12-14 15:00", "2016-12-19 04:00", "attack 7 unlabeled in source"),
]

MANUAL_DATASETS = {
    "swat_wadi": (
        "Request access from SUTD iTrust. Use historian CSV files, not pcap files. "
        "After download, place CSVs under data/public_datasets/manual/swat_wadi/."
    ),
    "scania_component_x": (
        "Download from researchdata.se. It is a high-value truck component dataset, "
        "but schema mapping should be reviewed before ACM ingestion."
    ),
    "paderborn_bearing": (
        "Download selected bearing states from Paderborn. The full dataset is large "
        "and distributed as MATLAB/RAR files; adapt a small healthy plus damaged subset first."
    ),
    "nasa_bearing_full": (
        "Direct download is simple but large, about 1.08 GB. Run: "
        "python scripts/download_validation_datasets.py --dataset bearing --max-assets 3"
    ),
    "mimii_audio": (
        "Download from Zenodo only if audio feature extraction is in scope. ACM needs "
        "numeric time-series features, not raw WAV files."
    ),
}


@dataclass(frozen=True)
class Paths:
    root: Path
    raw: Path
    adapted: Path


def make_paths(dest: Path) -> Paths:
    raw = dest / "raw"
    adapted = dest / "adapted"
    raw.mkdir(parents=True, exist_ok=True)
    adapted.mkdir(parents=True, exist_ok=True)
    return Paths(dest, raw, adapted)


def download(url: str, path: Path, force: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        print(f"  exists {path}")
        return path
    print(f"  GET {url}")
    request = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(request, timeout=600) as response:
        with path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    return path


def fetch_bytes(url: str) -> bytes:
    print(f"  GET {url}")
    request = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(request, timeout=600) as response:
        return response.read()


def write_events(path: Path, events: list[dict]) -> None:
    pd.DataFrame(events, columns=["event_start", "event_end", "description"]).to_csv(path, index=False)


def write_manifest(out: Path, manifest: dict) -> None:
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def sanitize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        str(c).strip().replace(" ", "_").replace("[", "").replace("]", "").replace("/", "_")
        for c in df.columns
    ]
    return df


def segment_events(ts: pd.Series, labels: Iterable[bool], description: str) -> list[dict]:
    times = pd.to_datetime(ts).reset_index(drop=True)
    mask = pd.Series(list(labels), dtype=bool).reset_index(drop=True)
    events: list[dict] = []
    start = None
    for idx, value in enumerate(mask):
        if value and start is None:
            start = idx
        elif not value and start is not None:
            events.append({
                "event_start": str(times.iloc[start]),
                "event_end": str(times.iloc[idx - 1]),
                "description": description,
            })
            start = None
    if start is not None and len(mask):
        events.append({
            "event_start": str(times.iloc[start]),
            "event_end": str(times.iloc[len(mask) - 1]),
            "description": description,
        })
    return events


def adapt_skab(paths: Paths, force: bool = False, max_assets: int | None = None) -> None:
    del max_assets
    out = paths.adapted / "skab"
    out.mkdir(parents=True, exist_ok=True)

    train = pd.read_csv(io.BytesIO(fetch_bytes(f"{SKAB_BASE}/anomaly-free/anomaly-free.csv")), sep=";")
    train = train.rename(columns={"datetime": "timestamp"})

    events, frames = [], [train.assign(anomaly=0.0)]
    t_cursor = pd.to_datetime(train["timestamp"]).max()
    for group, count in SKAB_GROUPS.items():
        for i in range(count):
            try:
                df = pd.read_csv(io.BytesIO(fetch_bytes(f"{SKAB_BASE}/{group}/{i}.csv")), sep=";")
            except Exception as exc:
                print(f"  skip SKAB {group}/{i}.csv ({exc})")
                continue
            df = df.rename(columns={"datetime": "timestamp"})
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            shift = (t_cursor + pd.Timedelta(seconds=60)) - df["timestamp"].iloc[0]
            df["timestamp"] = df["timestamp"] + shift
            t_cursor = df["timestamp"].max()
            anomaly = df["anomaly"].eq(1)
            events.extend(segment_events(df["timestamp"], anomaly, f"SKAB {group} experiment {i}"))
            frames.append(df.drop(columns=["changepoint"], errors="ignore"))

    full = pd.concat(frames, ignore_index=True)
    labels = full.pop("anomaly")
    full.to_csv(out / "asset_skab.csv", index=False)
    pd.DataFrame({"timestamp": full["timestamp"], "anomaly": labels}).to_csv(out / "labels.csv", index=False)
    write_events(out / "known_events.csv", events)
    write_manifest(out, {
        "dataset": "skab",
        "asset_files": ["asset_skab.csv"],
        "timestamp_col": "timestamp",
        "notes": "SKAB is retained for stress testing, but ACM docs note it is not a canonical generality benchmark.",
    })
    print(f"SKAB ready: {out / 'asset_skab.csv'}")


def adapt_metropt3(paths: Paths, force: bool = False, max_assets: int | None = None) -> None:
    del max_assets
    out = paths.adapted / "metropt3"
    out.mkdir(parents=True, exist_ok=True)
    raw_zip = download(METROPT3_URL, paths.raw / "metropt3.zip", force)
    with zipfile.ZipFile(raw_zip) as zf:
        name = next(name for name in zf.namelist() if name.lower().endswith(".csv"))
        df = pd.read_csv(zf.open(name))

    ts_col = "timestamp" if "timestamp" in df.columns else df.columns[1]
    df[ts_col] = pd.to_datetime(df[ts_col])
    df = sanitize_columns(df.rename(columns={ts_col: "timestamp"}))
    df = df.drop(columns=[c for c in ("Unnamed:_0", "Unnamed: 0") if c in df.columns], errors="ignore")
    numeric_cols = [c for c in df.columns if c != "timestamp"]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    df = df.set_index("timestamp").resample("1min").mean().dropna(how="all").reset_index()
    df.to_csv(out / "asset_metropt3.csv", index=False)
    write_events(out / "known_events.csv", [
        {"event_start": start, "event_end": end, "description": desc}
        for start, end, desc in METROPT3_EVENTS
    ])
    write_manifest(out, {
        "dataset": "metropt3",
        "asset_files": ["asset_metropt3.csv"],
        "timestamp_col": "timestamp",
        "sampling": "raw 1 Hz, adapted to 1 minute mean",
    })
    print(f"MetroPT-3 ready: {out / 'asset_metropt3.csv'} ({len(df)} rows)")


def _open_nested_zip(path: Path) -> zipfile.ZipFile:
    outer = zipfile.ZipFile(path)
    nested = next(name for name in outer.namelist() if name.lower().endswith(".zip"))
    data = outer.read(nested)
    outer.close()
    return zipfile.ZipFile(io.BytesIO(data))


def adapt_cmapss(paths: Paths, force: bool = False, max_assets: int | None = None) -> None:
    out = paths.adapted / "cmapss"
    out.mkdir(parents=True, exist_ok=True)
    raw_zip = download(CMAPSS_URL, paths.raw / "cmapss.zip", force)
    asset_files: list[str] = []
    events: list[dict] = []
    labels_rows: list[dict] = []

    cols = ["unit", "cycle", "setting_1", "setting_2", "setting_3"] + [f"s{i:02d}" for i in range(1, 22)]
    written = 0
    with _open_nested_zip(raw_zip) as zf:
        train_files = sorted(name for name in zf.namelist() if name.startswith("train_FD") and name.endswith(".txt"))
        for train_name in train_files:
            fd = Path(train_name).stem.split("_")[1]
            df = pd.read_csv(zf.open(train_name), sep=r"\s+", header=None, names=cols)
            for unit, part in df.groupby("unit", sort=True):
                if max_assets is not None and written >= max_assets:
                    break
                part = part.reset_index(drop=True).copy()
                part["timestamp"] = pd.Timestamp("2020-01-01") + pd.to_timedelta(part["cycle"] - 1, unit="min")
                part = part[["timestamp"] + [c for c in cols if c != "unit"]]
                max_cycle = int(part["cycle"].max())
                event_len = max(20, int(math.ceil(max_cycle * 0.10)))
                threshold = max_cycle - event_len + 1
                degraded = part["cycle"].ge(threshold)
                asset_name = f"asset_cmapss_{fd}_unit{int(unit):03d}.csv"
                part.to_csv(out / asset_name, index=False)
                asset_files.append(asset_name)
                events.extend(segment_events(part["timestamp"], degraded, f"C-MAPSS {fd} unit {int(unit)} terminal degradation window"))
                labels_rows.extend({
                    "asset_file": asset_name,
                    "timestamp": ts,
                    "terminal_degradation": int(flag),
                } for ts, flag in zip(part["timestamp"], degraded))
                written += 1
            if max_assets is not None and written >= max_assets:
                break

    pd.DataFrame(labels_rows).to_csv(out / "labels.csv", index=False)
    write_events(out / "known_events.csv", events)
    write_manifest(out, {
        "dataset": "cmapss",
        "asset_files": asset_files,
        "timestamp_col": "timestamp",
        "notes": "Each training engine unit is one ACM asset. The label window is terminal degradation, not an original binary anomaly label.",
    })
    print(f"C-MAPSS ready: {out} ({len(asset_files)} asset CSVs)")


def _read_smd_txt(zf: zipfile.ZipFile, name: str, start: pd.Timestamp) -> pd.DataFrame:
    arr = np.loadtxt(io.StringIO(zf.read(name).decode("utf-8")), delimiter=",")
    idx = pd.date_range(start, periods=len(arr), freq="60s")
    return pd.DataFrame(arr, columns=[f"m{i:02d}" for i in range(arr.shape[1])]).assign(timestamp=idx)


def adapt_smd(paths: Paths, force: bool = False, max_assets: int | None = None) -> None:
    out = paths.adapted / "smd"
    out.mkdir(parents=True, exist_ok=True)
    raw_zip = download(SMD_URL, paths.raw / "smd_omni_anomaly.zip", force)
    asset_files: list[str] = []
    events: list[dict] = []
    labels_rows: list[dict] = []

    with zipfile.ZipFile(raw_zip) as zf:
        train_files = sorted(name for name in zf.namelist() if "/ServerMachineDataset/train/machine-" in name)
        if max_assets is not None:
            train_files = train_files[:max_assets]
        for train_name in train_files:
            machine = Path(train_name).stem
            base = train_name.rsplit("/train/", 1)[0]
            test_name = f"{base}/test/{machine}.txt"
            label_name = f"{base}/test_label/{machine}.txt"
            train = _read_smd_txt(zf, train_name, pd.Timestamp("2020-01-01"))
            test_start = pd.to_datetime(train["timestamp"]).max() + pd.Timedelta(minutes=1)
            test = _read_smd_txt(zf, test_name, test_start)
            test_labels = np.loadtxt(io.StringIO(zf.read(label_name).decode("utf-8")), delimiter=",").astype(int)
            test = test.iloc[:len(test_labels)].copy()
            labels = np.concatenate([np.zeros(len(train), dtype=int), test_labels])
            full = pd.concat([train, test], ignore_index=True)
            full = full[["timestamp"] + [c for c in full.columns if c != "timestamp"]]
            asset_name = f"asset_smd_{machine}.csv"
            full.to_csv(out / asset_name, index=False)
            asset_files.append(asset_name)
            pd.DataFrame({
                "asset_file": asset_name,
                "timestamp": full["timestamp"],
                "anomaly": labels,
            }).to_csv(out / f"labels_{machine}.csv", index=False)
            labels_rows.append({"asset_file": asset_name, "label_file": f"labels_{machine}.csv"})
            events.extend(segment_events(full["timestamp"], labels.astype(bool), f"SMD {machine} anomaly segment"))

    pd.DataFrame(labels_rows).to_csv(out / "labels_index.csv", index=False)
    write_events(out / "known_events.csv", events)
    write_manifest(out, {
        "dataset": "smd",
        "asset_files": asset_files,
        "timestamp_col": "timestamp",
        "sampling": "synthetic 1 minute cadence, matching SMD convention",
    })
    print(f"SMD ready: {out} ({len(asset_files)} asset CSVs)")


def adapt_ai4i(paths: Paths, force: bool = False, max_assets: int | None = None) -> None:
    del max_assets
    out = paths.adapted / "ai4i"
    out.mkdir(parents=True, exist_ok=True)
    raw_zip = download(AI4I_URL, paths.raw / "ai4i.zip", force)
    with zipfile.ZipFile(raw_zip) as zf:
        df = pd.read_csv(zf.open("ai4i2020.csv"))

    labels = df[["Machine failure", "TWF", "HDF", "PWF", "OSF", "RNF"]].copy()
    asset = df.drop(columns=["UDI", "Product ID", "Type", "Machine failure", "TWF", "HDF", "PWF", "OSF", "RNF"])
    asset = sanitize_columns(asset)
    asset.insert(0, "timestamp", pd.date_range("2020-01-01", periods=len(asset), freq="min"))
    asset.to_csv(out / "asset_ai4i.csv", index=False)
    labels.insert(0, "timestamp", asset["timestamp"])
    labels.to_csv(out / "labels.csv", index=False)
    write_events(out / "known_events.csv", segment_events(asset["timestamp"], labels["Machine failure"].astype(bool), "AI4I machine failure"))
    write_manifest(out, {
        "dataset": "ai4i",
        "asset_files": ["asset_ai4i.csv"],
        "timestamp_col": "timestamp",
        "notes": "Synthetic tabular predictive-maintenance data with generated 1 minute timestamps.",
    })
    print(f"AI4I ready: {out / 'asset_ai4i.csv'}")


def adapt_secom(paths: Paths, force: bool = False, max_assets: int | None = None) -> None:
    del max_assets
    out = paths.adapted / "secom"
    out.mkdir(parents=True, exist_ok=True)
    raw_zip = download(SECOM_URL, paths.raw / "secom.zip", force)
    with zipfile.ZipFile(raw_zip) as zf:
        data = pd.read_csv(zf.open("secom.data"), sep=r"\s+", header=None, na_values=["NaN"])
        labels = pd.read_csv(zf.open("secom_labels.data"), sep=r"\s+", header=None)

    data.columns = [f"f{i:03d}" for i in range(data.shape[1])]
    if labels.shape[1] == 2:
        labels.columns = ["pass_fail", "timestamp_raw"]
        ts = pd.to_datetime(labels["timestamp_raw"], format="%d/%m/%Y %H:%M:%S")
    else:
        labels = labels.iloc[:, :3]
        labels.columns = ["pass_fail", "date", "time"]
        ts = pd.to_datetime(
            labels["date"].astype(str).str.strip('"') + " " + labels["time"].astype(str).str.strip('"'),
            format="%d/%m/%Y %H:%M:%S",
        )
    asset = data.copy()
    asset.insert(0, "timestamp", ts)
    asset = asset.sort_values("timestamp").reset_index(drop=True)
    labels = labels.assign(timestamp=ts, failure=labels["pass_fail"].eq(1).astype(int))
    labels = labels.sort_values("timestamp").reset_index(drop=True)
    asset.to_csv(out / "asset_secom.csv", index=False)
    labels[["timestamp", "pass_fail", "failure"]].to_csv(out / "labels.csv", index=False)
    write_events(out / "known_events.csv", segment_events(asset["timestamp"], labels["failure"].astype(bool), "SECOM failed wafer"))
    write_manifest(out, {
        "dataset": "secom",
        "asset_files": ["asset_secom.csv"],
        "timestamp_col": "timestamp",
        "notes": "Semiconductor process snapshots sorted by provided timestamps. Sparse NaNs are preserved for ACM readiness checks.",
    })
    print(f"SECOM ready: {out / 'asset_secom.csv'}")


def adapt_batadal(paths: Paths, force: bool = False, max_assets: int | None = None) -> None:
    del max_assets
    out = paths.adapted / "batadal"
    out.mkdir(parents=True, exist_ok=True)
    train1_path = download(BATADAL_TRAIN1_URL, paths.raw / "BATADAL_dataset03.csv", force)
    train2_path = download(BATADAL_TRAIN2_URL, paths.raw / "BATADAL_dataset04.csv", force)

    asset_files = []
    all_events: list[dict] = []
    for name, path in [("train1", train1_path), ("train2", train2_path)]:
        df = pd.read_csv(path, skipinitialspace=True)
        df.columns = [c.strip() for c in df.columns]
        df["timestamp"] = pd.to_datetime(df["DATETIME"], format="%d/%m/%y %H")
        labels = df["ATT_FLAG"].fillna(0).astype(int)
        asset = df.drop(columns=["DATETIME", "ATT_FLAG", "timestamp"])
        asset.insert(0, "timestamp", df["timestamp"])
        asset_name = f"asset_batadal_{name}.csv"
        asset.to_csv(out / asset_name, index=False)
        pd.DataFrame({"timestamp": asset["timestamp"], "attack_flag": labels}).to_csv(out / f"labels_{name}.csv", index=False)
        asset_files.append(asset_name)
        all_events.extend(segment_events(asset["timestamp"], labels.eq(1), f"BATADAL {name} labeled attack"))

    all_events.extend({
        "event_start": start,
        "event_end": end,
        "description": desc,
    } for start, end, desc in BATADAL_TRAIN2_ATTACKS)
    write_events(out / "known_events.csv", all_events)
    write_manifest(out, {
        "dataset": "batadal",
        "asset_files": asset_files,
        "timestamp_col": "timestamp",
        "notes": "Training dataset 1 is normal. Training dataset 2 includes partial ATT_FLAG labels and documented attack windows.",
    })
    print(f"BATADAL ready: {out} ({len(asset_files)} asset CSVs)")


def adapt_milling(paths: Paths, force: bool = False, max_assets: int | None = None) -> None:
    del max_assets
    out = paths.adapted / "milling"
    out.mkdir(parents=True, exist_ok=True)
    raw_zip = download(MILLING_URL, paths.raw / "milling.zip", force)
    with _open_nested_zip(raw_zip) as zf:
        mat_bytes = zf.read("mill.mat")

    try:
        from scipy.io import loadmat
    except Exception as exc:
        raise RuntimeError("scipy is required to adapt NASA Milling mill.mat") from exc

    mat = loadmat(io.BytesIO(mat_bytes), squeeze_me=True, struct_as_record=False)
    rows = []
    labels = []
    base = pd.Timestamp("2020-01-01")
    cursor = base
    for rec in mat["mill"].flat:
        arrays = {
            "smcAC": np.asarray(rec.smcAC, dtype=float),
            "smcDC": np.asarray(rec.smcDC, dtype=float),
            "vib_table": np.asarray(rec.vib_table, dtype=float),
            "vib_spindle": np.asarray(rec.vib_spindle, dtype=float),
            "AE_table": np.asarray(rec.AE_table, dtype=float),
            "AE_spindle": np.asarray(rec.AE_spindle, dtype=float),
        }
        n = min(len(v) for v in arrays.values())
        timestamps = pd.date_range(cursor, periods=n, freq="100ms")
        cursor = timestamps[-1] + pd.Timedelta(seconds=1)
        part = pd.DataFrame({name: values[:n] for name, values in arrays.items()})
        part.insert(0, "timestamp", timestamps)
        part["case"] = int(rec.case)
        part["run"] = int(rec.run)
        part["DOC"] = float(rec.DOC)
        part["feed"] = float(rec.feed)
        part["material"] = int(rec.material)
        rows.append(part)
        labels.append(pd.DataFrame({
            "timestamp": timestamps,
            "case": int(rec.case),
            "run": int(rec.run),
            "VB": float(rec.VB),
        }))

    asset = pd.concat(rows, ignore_index=True)
    label_df = pd.concat(labels, ignore_index=True)
    wear_threshold = label_df["VB"].quantile(0.90)
    label_df["high_wear"] = label_df["VB"].ge(wear_threshold).astype(int)
    asset.to_csv(out / "asset_milling.csv", index=False)
    label_df.to_csv(out / "labels.csv", index=False)
    write_events(out / "known_events.csv", segment_events(label_df["timestamp"], label_df["high_wear"].astype(bool), "NASA Milling high wear top decile"))
    write_manifest(out, {
        "dataset": "milling",
        "asset_files": ["asset_milling.csv"],
        "timestamp_col": "timestamp",
        "sampling": "synthetic 100 ms cadence inside each run",
        "notes": "Wear VB is written only to labels.csv and excluded from model input.",
    })
    print(f"NASA Milling ready: {out / 'asset_milling.csv'} ({len(asset)} rows)")


def _bearing_timestamp(name: str, fallback: pd.Timestamp) -> pd.Timestamp:
    stem = Path(name).name
    for fmt in ("%Y.%m.%d.%H.%M.%S", "%Y.%m.%d.%H.%M"):
        try:
            return pd.to_datetime(stem, format=fmt)
        except ValueError:
            pass
    return fallback


def _bearing_group_name(name: str) -> str:
    parts = Path(name).parts
    for part in parts:
        lower = part.lower()
        if "test" in lower:
            return part.replace(" ", "_").replace(".", "_")
    return "bearing"


def _bearing_feature_row(zf: zipfile.ZipFile, name: str, timestamp: pd.Timestamp) -> dict:
    raw = zf.read(name)
    df = pd.read_csv(io.BytesIO(raw), sep=r"\s+", header=None)
    row: dict[str, float | str | pd.Timestamp] = {"timestamp": timestamp}
    for col in df.columns:
        values = pd.to_numeric(df[col], errors="coerce").dropna().to_numpy(dtype=float)
        prefix = f"ch{int(col) + 1:02d}"
        if len(values) == 0:
            row[f"{prefix}_mean"] = np.nan
            row[f"{prefix}_std"] = np.nan
            row[f"{prefix}_rms"] = np.nan
            row[f"{prefix}_min"] = np.nan
            row[f"{prefix}_max"] = np.nan
            continue
        row[f"{prefix}_mean"] = float(np.mean(values))
        row[f"{prefix}_std"] = float(np.std(values))
        row[f"{prefix}_rms"] = float(np.sqrt(np.mean(values * values)))
        row[f"{prefix}_min"] = float(np.min(values))
        row[f"{prefix}_max"] = float(np.max(values))
    return row


def adapt_bearing(paths: Paths, force: bool = False, max_assets: int | None = None) -> None:
    out = paths.adapted / "bearing"
    out.mkdir(parents=True, exist_ok=True)
    raw_zip = download(BEARING_URL, paths.raw / "nasa_bearing.zip", force)
    asset_files: list[str] = []
    events: list[dict] = []

    with zipfile.ZipFile(raw_zip) as zf:
        candidates = [
            name for name in zf.namelist()
            if not name.endswith("/") and Path(name).name[:4].isdigit()
        ]
        groups: dict[str, list[str]] = {}
        for name in candidates:
            groups.setdefault(_bearing_group_name(name), []).append(name)
        selected = sorted(groups.items())
        if max_assets is not None:
            selected = selected[:max_assets]
        for group, names in selected:
            rows = []
            fallback = pd.Timestamp("2020-01-01")
            for idx, name in enumerate(sorted(names)):
                ts = _bearing_timestamp(name, fallback + pd.Timedelta(minutes=idx))
                try:
                    rows.append(_bearing_feature_row(zf, name, ts))
                except Exception as exc:
                    print(f"  skip bearing file {name} ({exc})")
            if not rows:
                continue
            asset = pd.DataFrame(rows).sort_values("timestamp")
            asset_name = f"asset_nasa_bearing_{group}.csv"
            asset.to_csv(out / asset_name, index=False)
            asset_files.append(asset_name)
            cutoff = max(1, int(math.ceil(len(asset) * 0.10)))
            labels = pd.Series(False, index=asset.index)
            labels.iloc[-cutoff:] = True
            pd.DataFrame({
                "asset_file": asset_name,
                "timestamp": asset["timestamp"],
                "terminal_degradation": labels.astype(int),
            }).to_csv(out / f"labels_{group}.csv", index=False)
            events.extend(segment_events(asset["timestamp"], labels, f"NASA IMS Bearing {group} terminal degradation window"))

    write_events(out / "known_events.csv", events)
    write_manifest(out, {
        "dataset": "bearing",
        "asset_files": asset_files,
        "timestamp_col": "timestamp",
        "notes": "High-frequency vibration files are adapted to one statistical feature row per measurement file. Terminal degradation labels use the last 10 percent of each run.",
    })
    print(f"NASA Bearing ready: {out} ({len(asset_files)} asset CSVs)")


def download_tep(paths: Paths, force: bool = False, max_assets: int | None = None) -> None:
    del max_assets
    out = paths.adapted / "tep"
    out.mkdir(parents=True, exist_ok=True)
    metadata = json.loads(fetch_bytes(TEP_API).decode("utf-8"))
    files = metadata["data"]["latestVersion"]["files"]
    raw_dir = paths.raw / "tep"
    raw_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for item in files:
        file_id = item["dataFile"]["id"]
        filename = item["dataFile"]["filename"]
        target = raw_dir / filename
        download(TEP_FILE_API.format(file_id=file_id), target, force)
        downloaded.append(str(target))

    write_manifest(out, {
        "dataset": "tep",
        "raw_files": downloaded,
        "timestamp_col": "timestamp",
        "status": "raw_downloaded_only",
        "manual_step": "Install R or pyreadr, convert RData frames to CSV, then add timestamp and fault labels per run.",
    })
    print(f"TEP raw files downloaded to {raw_dir}")
    print("  Conversion was not attempted because TEP is published as RData.")


ADAPTERS = {
    "skab": adapt_skab,
    "metropt3": adapt_metropt3,
    "cmapss": adapt_cmapss,
    "smd": adapt_smd,
    "ai4i": adapt_ai4i,
    "secom": adapt_secom,
    "batadal": adapt_batadal,
    "milling": adapt_milling,
    "bearing": adapt_bearing,
    "tep": download_tep,
}


def print_manual_notes() -> None:
    print("Manual or review-first datasets:")
    for name, note in MANUAL_DATASETS.items():
        print(f"  {name}: {note}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", choices=sorted(ADAPTERS) + ["all"], default="metropt3")
    ap.add_argument("--dest", default=str(DEFAULT_DEST))
    ap.add_argument("--force", action="store_true", help="re-download raw archives even if they already exist")
    ap.add_argument("--max-assets", type=int, default=None,
                    help="limit multi-asset adapters such as C-MAPSS and SMD")
    ap.add_argument("--manual-notes", action="store_true", help="print datasets that require human download/review")
    args = ap.parse_args()

    paths = make_paths(Path(args.dest))
    selected = sorted(ADAPTERS) if args.dataset == "all" else [args.dataset]
    for name in selected:
        print(f"\n== {name} ==")
        ADAPTERS[name](paths, force=args.force, max_assets=args.max_assets)
    if args.manual_notes:
        print()
        print_manual_notes()
    return 0


if __name__ == "__main__":
    sys.exit(main())

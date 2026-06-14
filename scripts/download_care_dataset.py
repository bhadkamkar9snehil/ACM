#!/usr/bin/env python3
"""
Download the CARE_To_Compare wind-turbine SCADA dataset (or a subset) from
Zenodo using HTTP range requests — no need to download the full 5.5 GB zip.

Dataset: https://zenodo.org/records/15846963
  Wind Farm A: 22 datasets x ~36 MB  (~800 MB,  86 features)
  Wind Farm B: 37 datasets           (~1.5 GB, 257 features)
  Wind Farm C: 36 datasets           (~3.2 GB, 957 features)

Usage:
  python scripts/download_care_dataset.py --dest ./care_data --farms A
  python scripts/download_care_dataset.py --dest ./care_data --farms A B C
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ZENODO_URL = "https://zenodo.org/records/15846963/files/CARE_To_Compare.zip?download=1"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default="./care_data", help="Destination directory")
    ap.add_argument("--farms", nargs="+", default=["A"], choices=["A", "B", "C"],
                    help="Wind farms to download (default: A)")
    ap.add_argument("--count", type=int, default=None,
                    help="Maximum number of event CSVs to download per farm (default: all)")
    ap.add_argument("--sim-dir", default=None,
                    help="Also copy downloaded CSVs to this directory (e.g. sim_data/sample)")
    args = ap.parse_args()

    try:
        from remotezip import RemoteZip
    except ImportError:
        print("Installing remotezip ...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "remotezip"])
        from remotezip import RemoteZip

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    prefixes = [f"CARE_To_Compare/Wind Farm {f}/" for f in args.farms]

    with RemoteZip(ZENODO_URL) as z:
        names = [n for n in z.namelist()
                 if (any(n.startswith(p) for p in prefixes) or n.endswith("README.md"))
                 and not n.endswith("/")]
        if args.count:
            csv_names = [n for n in names if n.endswith(".csv")]
            other_names = [n for n in names if not n.endswith(".csv")]
            names = other_names + sorted(csv_names)[:args.count]
        total = len(names)
        print(f"Downloading {total} files for farm(s) {', '.join(args.farms)} -> {dest}")
        for i, n in enumerate(sorted(names), 1):
            target = dest / n
            if target.exists() and target.stat().st_size > 0:
                print(f"[{i}/{total}] {n} (cached)")
                continue
            z.extract(n, str(dest))
            print(f"[{i}/{total}] {n}", flush=True)

    for f in args.farms:
        farm_dir = dest / "CARE_To_Compare" / f"Wind Farm {f}"
        n_csv = len(list((farm_dir / "datasets").glob("*.csv"))) if (farm_dir / "datasets").exists() else 0
        print(f"Wind Farm {f}: {n_csv} event datasets at '{farm_dir}'")

    if args.sim_dir:
        import shutil
        sim_dir = Path(args.sim_dir)
        sim_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for farm_letter in args.farms:
            farm_datasets = dest / "CARE_To_Compare" / f"Wind Farm {farm_letter}" / "datasets"
            if not farm_datasets.exists():
                continue
            csvs = sorted(farm_datasets.glob("*.csv"))
            if args.count:
                csvs = csvs[:args.count]
            for i, csv_path in enumerate(csvs, 1):
                target = sim_dir / f"wind_turbine_farm{farm_letter}_{i:02d}.csv"
                if not target.exists():
                    shutil.copy2(csv_path, target)
                    print(f"  → {target.name}")
                copied += 1
        print(f"Copied {copied} file(s) to {sim_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

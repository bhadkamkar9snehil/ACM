#!/usr/bin/env python3
"""
Download the CARE_To_Compare wind-turbine SCADA dataset (or a subset) from
Zenodo using HTTP range requests — no need to download the full 5.5 GB zip.

Files are written directly to sim_data/sample/ (or --dest) with flat names:
  care_farmA_40.csv, care_farmA_50.csv, ...

These appear immediately in ACM's Simulate → Files tab and can be seeded as
monitored assets via:
  python scripts/acm_seed_demo.py --care-dir sim_data/sample --db acm_results.db

Dataset: https://zenodo.org/records/15846963
  Wind Farm A: 22 datasets x ~36 MB  (~800 MB,  86 features)
  Wind Farm B: 37 datasets           (~1.5 GB, 257 features)
  Wind Farm C: 36 datasets           (~3.2 GB, 957 features)

Usage:
  python scripts/download_care_dataset.py
  python scripts/download_care_dataset.py --farms A B --count 5
  python scripts/download_care_dataset.py --dest /custom/path --farms A
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZENODO_URL = "https://zenodo.org/records/15846963/files/CARE_To_Compare.zip?download=1"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default=None,
                    help="Destination directory (default: sim_data/sample inside ACM)")
    ap.add_argument("--farms", nargs="+", default=["A"], choices=["A", "B", "C"],
                    help="Wind farms to download (default: A)")
    ap.add_argument("--count", type=int, default=None,
                    help="Maximum number of event CSVs to download per farm (default: all)")
    args = ap.parse_args()

    try:
        from remotezip import RemoteZip
    except ImportError:
        print("Installing remotezip ...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "remotezip"])
        from remotezip import RemoteZip

    dest = Path(args.dest) if args.dest else ROOT / "sim_data" / "sample"
    dest.mkdir(parents=True, exist_ok=True)

    prefixes = [f"CARE_To_Compare/Wind Farm {f}/" for f in args.farms]

    with RemoteZip(ZENODO_URL) as z:
        all_names = z.namelist()
        csv_names = [
            n for n in all_names
            if any(n.startswith(p) for p in prefixes)
            and n.endswith(".csv")
            and not n.endswith("/")
        ]
        if args.count:
            csv_names = sorted(csv_names)[: args.count * len(args.farms)]

        total = len(csv_names)
        print(f"Downloading {total} file(s) for farm(s) {', '.join(args.farms)} -> {dest}")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for i, name in enumerate(sorted(csv_names), 1):
                # name = "CARE_To_Compare/Wind Farm A/datasets/40.csv"
                parts = name.split("/")
                farm_letter = parts[1].split()[-1]          # "A"
                original_stem = Path(parts[-1]).stem        # "40"
                flat_name = f"care_farm{farm_letter}_{original_stem}.csv"
                target = dest / flat_name

                if target.exists() and target.stat().st_size > 0:
                    print(f"[{i}/{total}] {flat_name} (cached)")
                    continue

                z.extract(name, str(tmp_path))
                extracted = tmp_path / name
                shutil.move(str(extracted), str(target))
                print(f"[{i}/{total}] {flat_name}", flush=True)

    for f in args.farms:
        n_csv = len(list(dest.glob(f"care_farm{f}_*.csv")))
        print(f"Wind Farm {f}: {n_csv} CSV(s) in '{dest}'")

    print(f"\nSeed as ACM assets:")
    print(f"  python scripts/acm_seed_demo.py --care-dir {dest} --db acm_results.db")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

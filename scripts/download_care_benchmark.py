#!/usr/bin/env python3
"""
Download CARE-to-Compare dataset in the structure expected by care_benchmark.py.

Output layout:
  <dest>/Wind Farm A/event_info.csv
  <dest>/Wind Farm A/datasets/40.csv
  <dest>/Wind Farm A/datasets/68.csv
  ...

Usage:
  python scripts/download_care_benchmark.py --dest care_data
  python scripts/download_care_benchmark.py --dest care_data --farms A B C
  python scripts/download_care_benchmark.py --dest care_data --farms A --count 5
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ZENODO_URL = "https://zenodo.org/records/15846963/files/CARE_To_Compare.zip?download=1"
ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default="care_data",
                    help="Destination directory (default: care_data inside ACM root)")
    ap.add_argument("--farms", nargs="+", default=["A"], choices=["A", "B", "C"],
                    help="Wind farms to download (default: A)")
    ap.add_argument("--count", type=int, default=None,
                    help="Max event CSVs per farm, not counting event_info.csv (default: all)")
    args = ap.parse_args()

    try:
        from remotezip import RemoteZip
    except ImportError:
        print("Installing remotezip...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "remotezip"])
        from remotezip import RemoteZip

    dest = Path(args.dest) if Path(args.dest).is_absolute() else ROOT / args.dest
    dest.mkdir(parents=True, exist_ok=True)

    with RemoteZip(ZENODO_URL) as z:
        all_names = z.namelist()

        for farm in args.farms:
            prefix = f"CARE_To_Compare/Wind Farm {farm}/"
            farm_dir = dest / f"Wind Farm {farm}"
            farm_dir.mkdir(parents=True, exist_ok=True)
            (farm_dir / "datasets").mkdir(exist_ok=True)

            # Separate event_info from dataset CSVs
            info_files = [n for n in all_names if n.startswith(prefix)
                          and n.endswith("event_info.csv")]
            data_files = sorted([
                n for n in all_names
                if n.startswith(prefix + "datasets/")
                and n.endswith(".csv")
                and not n.endswith("/")
            ])

            if args.count:
                data_files = data_files[:args.count]

            to_download = info_files + data_files
            print(f"\nFarm {farm}: {len(info_files)} metadata + {len(data_files)} event CSVs → {farm_dir}")

            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                for i, name in enumerate(to_download, 1):
                    # Determine output path, preserving datasets/ subdir
                    rel = name[len(prefix):]          # e.g. "event_info.csv" or "datasets/40.csv"
                    target = farm_dir / rel
                    target.parent.mkdir(parents=True, exist_ok=True)

                    if target.exists() and target.stat().st_size > 0:
                        print(f"  [{i}/{len(to_download)}] {rel} (cached)")
                        continue

                    z.extract(name, str(tmp_path))
                    extracted = tmp_path / name
                    shutil.move(str(extracted), str(target))
                    sz_mb = target.stat().st_size / 1_048_576
                    print(f"  [{i}/{len(to_download)}] {rel}  ({sz_mb:.1f} MB)", flush=True)

            print(f"Farm {farm} done → {farm_dir}")

    print(f"\nRun benchmark:")
    for farm in args.farms:
        print(f'  python scripts/care_benchmark.py --data-dir "{dest}/Wind Farm {farm}" '
              f'--out results/{farm.lower()}/ --workers 4')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

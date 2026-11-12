"""Download CARE-to-Compare data for ACM's evidence and live-demo paths.

Output layout::

    <dest>/Wind Farm A/event_info.csv
    <dest>/Wind Farm A/datasets/40.csv
    ...

Usage::

    uv run python -m evidence.download_care --dest care_data
    uv run python -m evidence.download_care --dest care_data --farms A B C
    uv run python -m evidence.download_care --dest care_data --farms A --count 5

The downloader uses HTTP range requests through remotezip so selecting a
small event subset does not require downloading the full archive first.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from remotezip import RemoteZip

ZENODO_URL = (
    "https://zenodo.org/records/15846963/files/"
    "CARE_To_Compare.zip?download=1"
)
REPO_ROOT = Path(__file__).resolve().parents[2]


def download_care(
    dest: Path,
    farms: list[str],
    count: int | None = None,
) -> list[Path]:
    """Download selected CARE farms and return their local directories."""
    dest.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []

    with RemoteZip(ZENODO_URL) as archive:
        names = archive.namelist()
        for farm in farms:
            prefix = f"CARE_To_Compare/Wind Farm {farm}/"
            farm_dir = dest / f"Wind Farm {farm}"
            (farm_dir / "datasets").mkdir(parents=True, exist_ok=True)

            metadata = [
                name
                for name in names
                if name.startswith(prefix) and name.endswith("event_info.csv")
            ]
            datasets = sorted(
                name
                for name in names
                if name.startswith(prefix + "datasets/")
                and name.endswith(".csv")
            )
            if count is not None:
                datasets = datasets[:count]

            selected = metadata + datasets
            print(
                f"\nFarm {farm}: {len(metadata)} metadata + "
                f"{len(datasets)} event CSVs -> {farm_dir}"
            )
            with tempfile.TemporaryDirectory() as temp_dir:
                temp = Path(temp_dir)
                for index, name in enumerate(selected, 1):
                    relative = name[len(prefix):]
                    target = farm_dir / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists() and target.stat().st_size > 0:
                        print(f"  [{index}/{len(selected)}] {relative} (cached)")
                        continue
                    archive.extract(name, str(temp))
                    shutil.move(str(temp / name), str(target))
                    size_mb = target.stat().st_size / 1_048_576
                    print(
                        f"  [{index}/{len(selected)}] {relative} "
                        f"({size_mb:.1f} MB)",
                        flush=True,
                    )
            downloaded.append(farm_dir)

    return downloaded


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dest",
        default="care_data",
        help="destination directory (default: care_data at repo root)",
    )
    parser.add_argument(
        "--farms",
        nargs="+",
        default=["A"],
        choices=["A", "B", "C"],
        help="wind farms to download (default: A)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="maximum event CSVs per farm (default: all)",
    )
    args = parser.parse_args()

    dest = Path(args.dest)
    if not dest.is_absolute():
        dest = REPO_ROOT / dest
    farms = download_care(dest, args.farms, args.count)

    print("\nEvidence replay:")
    for farm_dir in farms:
        print(
            "  uv run python -m evidence.care_replay "
            f"--farm-dir \"{farm_dir}\" --out results/{farm_dir.name.replace(' ', '_')}"
        )
    print("\nLive demo:")
    if farms:
        print(
            "  uv run python -m evidence.seed_demo "
            f"--farm-dir \"{farms[0]}\" --root acm_data"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

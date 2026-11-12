"""Seed a CARE-shaped farm directory into a LIVE ACM data root (#131).

This is the "see it working in the UI" path, distinct from
evidence.care_replay: care_replay runs a private, isolated replay per
event in its own throwaway store and scores it against labels for
regression evidence. This module instead appends each event's full,
continuous history (chronological order, no train/prediction split -
a live asset's raw history IS its whole life) into a shared data root
that a running `python -m service` picks up, onboards, and bootstraps
on its own, exactly as it would for a real plant asset.

Run:
    uv run python -m evidence.seed_demo \
        --farm-dir "care_data/Wind Farm A" --root acm_data

Then, in the same or another terminal:
    uv run python -m service --root acm_data --port 8899
"""

from __future__ import annotations

import argparse
from pathlib import Path

from evidence.care_replay import load_event_full_frame, load_event_info
from store.raw import RawStore


def seed_farm(farm_dir: Path, root: Path, prefix: str | None = None) -> list[str]:
    """Append every downloaded event in farm_dir as one asset each.
    Missing CSVs (partial downloads, the norm with --count) are skipped,
    never an error. Returns the asset keys seeded."""
    farm_dir = Path(farm_dir)
    prefix = prefix or farm_dir.name.lower().replace(" ", "-")
    store = RawStore(Path(root) / "raw")
    seeded: list[str] = []
    for event in load_event_info(farm_dir):
        event_id = event["event_id"]
        if not (farm_dir / "datasets" / f"{event_id}.csv").exists():
            continue
        frame = load_event_full_frame(farm_dir, event_id)
        key = f"{prefix}/{event_id}"
        store.append(key, frame)
        seeded.append(key)
        print(f"  seeded {frame.height:>6} rows -> {key}")
    return seeded


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--farm-dir", required=True,
        help="CARE farm directory (event_info.csv + datasets/<id>.csv)",
    )
    ap.add_argument(
        "--root", default="acm_data",
        help="ACM data root to seed into (default: acm_data)",
    )
    ap.add_argument(
        "--prefix", default=None,
        help="asset key prefix (default: derived from the farm dir name, "
        "e.g. 'Wind Farm A' -> 'wind-farm-a')",
    )
    args = ap.parse_args()

    seeded = seed_farm(Path(args.farm_dir), Path(args.root), args.prefix)
    if not seeded:
        print(f"no event CSVs found under {args.farm_dir}/datasets/")
        return 1
    print(f"done: {len(seeded)} asset(s) seeded into {args.root}")
    print("start the service against the same --root to see them live:")
    print(f"  uv run python -m service --root {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

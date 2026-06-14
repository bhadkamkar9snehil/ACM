#!/usr/bin/env python3
"""
Seed demo assets into the ACM SQLite DB — idempotent, no service required.

Usage:
  python scripts/acm_seed_demo.py --care-dir care_data --db acm_results.db
  python scripts/acm_seed_demo.py --opcua opc.tcp://localhost:4840/simulator --db acm_results.db
  python scripts/acm_seed_demo.py --care-dir care_data --opcua opc.tcp://localhost:4840/simulator
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--care-dir", metavar="PATH",
                    help="Root of downloaded CARE data (contains CARE_To_Compare/)")
    ap.add_argument("--opcua", metavar="ENDPOINT",
                    help="OPC UA endpoint to register, e.g. opc.tcp://localhost:4840/simulator")
    ap.add_argument("--db", default="acm_results.db",
                    help="SQLite DB path (default: acm_results.db)")
    ap.add_argument("--grp", default=None,
                    help="Group name for CARE assets (default: care_demo)")
    args = ap.parse_args()

    if not args.care_dir and not args.opcua:
        ap.error("Provide at least one of --care-dir or --opcua")

    from scripts.acm_store import Store
    store = Store("sqlite", db=args.db)

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    skipped = 0

    INSERT = (
        "INSERT OR IGNORE INTO monitored_assets "
        "(asset_key, grp, enabled, source_kind, source_ref, conn_ref, "
        "timestamp_col, status_col, added_at, state) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)"
    )

    if args.care_dir:
        care_root = Path(args.care_dir)
        grp = args.grp or "care_demo"
        dataset_dirs = sorted(care_root.glob("CARE_To_Compare/Wind Farm */datasets"))
        if not dataset_dirs:
            print(f"No datasets found under {care_root}/CARE_To_Compare/Wind Farm */datasets/")
            print("Make sure you ran: python scripts/download_care_dataset.py --dest care_data --farms A")
        for datasets_dir in dataset_dirs:
            farm_dir = datasets_dir.parent
            farm_letter = farm_dir.name.split()[-1]  # "Wind Farm A" -> "A"
            for csv_path in sorted(datasets_dir.glob("*.csv")):
                asset_key = f"care/{farm_letter}/{csv_path.stem}"
                store.execute(INSERT, (
                    asset_key, grp, 1, "csv", str(csv_path.resolve()),
                    None, "time_stamp", "status_type_id", now, "NEW",
                ))
                if store.con.total_changes > inserted + skipped:
                    inserted += 1
                else:
                    skipped += 1

        # count via a single query to get accurate inserted/skipped numbers
        # (total_changes counting above can drift; use DB query instead)
        care_rows = store.fetch(
            "SELECT COUNT(*) AS n FROM monitored_assets WHERE grp = ?", (grp,)
        )
        n_care = care_rows[0]["n"] if care_rows else 0
        print(f"CARE ({grp}): {n_care} asset(s) now registered")

    if args.opcua:
        asset_key = "simulator/opc_ua"
        before = store.fetch(
            "SELECT COUNT(*) AS n FROM monitored_assets WHERE asset_key = ?",
            (asset_key,),
        )[0]["n"]
        store.execute(INSERT, (
            asset_key, "simulator", 1, "opcua", args.opcua,
            None, "published_at", None, now, "NEW",
        ))
        after = store.fetch(
            "SELECT COUNT(*) AS n FROM monitored_assets WHERE asset_key = ?",
            (asset_key,),
        )[0]["n"]
        if after > before:
            print(f"OPC UA: registered '{asset_key}' -> {args.opcua}")
        else:
            print(f"OPC UA: '{asset_key}' already registered (no change)")

    store.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

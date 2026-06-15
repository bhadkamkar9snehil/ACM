#!/usr/bin/env python3
"""
Seed demo assets into the ACM SQLite DB — idempotent, no service required.

Usage:
  python scripts/acm_seed_demo.py --care-dir sim_data/sample --db acm_results.db
  python scripts/acm_seed_demo.py --fault-dir sim_data/sample --db acm_results.db
  python scripts/acm_seed_demo.py --opcua opc.tcp://localhost:4840/simulator --db acm_results.db
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
                    help="Directory containing CARE CSVs (care_farm*.csv or CARE_To_Compare/ nested)")
    ap.add_argument("--fault-dir", metavar="PATH",
                    help="Directory containing fault_*.csv files from generate_fault_dataset.py")
    ap.add_argument("--opcua", metavar="ENDPOINT",
                    help="OPC UA endpoint to register, e.g. opc.tcp://localhost:4840/simulator")
    ap.add_argument("--db", default="acm_results.db",
                    help="SQLite DB path (default: acm_results.db)")
    ap.add_argument("--grp", default=None,
                    help="Group name for CARE assets (default: care_demo)")
    args = ap.parse_args()

    if not args.care_dir and not args.fault_dir and not args.opcua:
        ap.error("Provide at least one of --care-dir, --fault-dir, or --opcua")

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
        import re
        care_root = Path(args.care_dir)
        grp = args.grp or "care_demo"

        # Flat layout: care_farmA_40.csv (produced by download_care_dataset.py)
        flat_csvs = sorted(care_root.glob("care_farm[ABC]_*.csv"))
        # Legacy nested layout: CARE_To_Compare/Wind Farm A/datasets/40.csv
        dataset_dirs = sorted(care_root.glob("CARE_To_Compare/Wind Farm */datasets"))

        if not flat_csvs and not dataset_dirs:
            print(f"No CARE CSVs found in {care_root}")
            print("Run: python scripts/download_care_dataset.py --farms A")

        for csv_path in flat_csvs:
            m = re.match(r"care_farm([A-C])_(.+)\.csv$", csv_path.name)
            if not m:
                continue
            farm_letter, original_stem = m.group(1), m.group(2)
            asset_key = f"care/{farm_letter}/{original_stem}"
            store.execute(INSERT, (
                asset_key, grp, 1, "csv", str(csv_path.resolve()),
                None, "time_stamp", "status_type_id", now, "NEW",
            ))

        for datasets_dir in dataset_dirs:
            farm_letter = datasets_dir.parent.name.split()[-1]
            for csv_path in sorted(datasets_dir.glob("*.csv")):
                asset_key = f"care/{farm_letter}/{csv_path.stem}"
                store.execute(INSERT, (
                    asset_key, grp, 1, "csv", str(csv_path.resolve()),
                    None, "time_stamp", "status_type_id", now, "NEW",
                ))

        care_rows = store.fetch(
            "SELECT COUNT(*) AS n FROM monitored_assets WHERE grp = ?", (grp,)
        )
        n_care = care_rows[0]["n"] if care_rows else 0
        print(f"CARE ({grp}): {n_care} asset(s) now registered")

    if args.fault_dir:
        fault_root = Path(args.fault_dir)
        grp = args.grp or "fault_demo"
        fault_csvs = sorted(fault_root.glob("fault_*.csv"))
        if not fault_csvs:
            print(f"No fault_*.csv files found in {fault_root}")
            print("Run: python scripts/generate_fault_dataset.py")
        for csv_path in fault_csvs:
            # fault_rotary_bearing.csv -> fault/rotary_bearing
            asset_key = f"fault/{csv_path.stem[len('fault_'):]}"
            store.execute(INSERT, (
                asset_key, grp, 1, "csv", str(csv_path.resolve()),
                None, "timestamp", None, now, "NEW",
            ))
        fault_rows = store.fetch(
            "SELECT COUNT(*) AS n FROM monitored_assets WHERE grp = ?", (grp,)
        )
        n_fault = fault_rows[0]["n"] if fault_rows else 0
        print(f"Fault ({grp}): {n_fault} asset(s) now registered")

    asset_key = "simulator/internal"
    before = store.fetch(
        "SELECT COUNT(*) AS n FROM monitored_assets WHERE asset_key = ?",
        (asset_key,),
    )[0]["n"]
    store.execute(INSERT, (
        asset_key, "simulator", 1, "mqtt", "",
        str(ROOT / "data_cache" / "mqtt_buffer.db"), "published_at", None, now, "NEW",
    ))
    after = store.fetch(
        "SELECT COUNT(*) AS n FROM monitored_assets WHERE asset_key = ?",
        (asset_key,),
    )[0]["n"]
    if after > before:
        print(f"Internal: registered '{asset_key}' -> mqtt_buffer.db")

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

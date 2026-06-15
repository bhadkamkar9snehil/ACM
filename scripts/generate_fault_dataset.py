#!/usr/bin/env python3
"""
Generate synthetic industrial datasets with known injected faults.

Uses ACM's built-in generators (same engine as the Simulate tab) to produce
CSVs that start with normal operation then transition into a labeled fault
condition at a documented time point. Written to sim_data/sample/ so they
appear immediately in Simulate → Files and can be onboarded as ACM assets
for anomaly detection validation.

Fault onset is at event_start_pct=40% by default, so the first 40% of rows
are clean normal data that ACM trains on; the remaining 60% carry the fault
signal that ACM should detect.

Usage:
  python scripts/generate_fault_dataset.py
  python scripts/generate_fault_dataset.py --domains rotary_equipment petroleum_pipeline
  python scripts/generate_fault_dataset.py --rows 5000 --hz 1

Produced files (in sim_data/sample/):
  fault_rotary_bearing.csv          — bearing fault (vibration + temp rise)
  fault_rotary_imbalance.csv        — rotor imbalance (1× RPM vibration)
  fault_pipeline_small_leak.csv     — gradual pressure/flow drop
  fault_pipeline_large_leak.csv     — rapid depressurisation
  fault_pipeline_pump_trip.csv      — sudden pump failure
  fault_pipeline_sensor_drift.csv   — slow sensor bias drift
  fault_power_load_rejection.csv    — sudden load shed
  fault_power_voltage_sag.csv       — sustained voltage sag

Each CSV contains a `state` column: NORMAL during normal operation, and the
fault label once the fault begins — making ground-truth evaluation trivial.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sim.models import GenerateRequest
from sim.generator_engine import generate_csv
from sim.csv_manager import SAMPLE_DIR, ensure_dirs


FAULT_SPECS = [
    # (domain_id, scenario, output_name, extra_params, description)
    ("rotary_equipment", "bearing_fault",    "fault_rotary_bearing.csv",
     {"duration_minutes": 120, "fault_severity": 0.7, "event_start_pct": 40},
     "Bearing fault — vibration and bearing temperatures rise after 40% mark"),

    ("rotary_equipment", "rotor_imbalance",  "fault_rotary_imbalance.csv",
     {"duration_minutes": 120, "fault_severity": 0.7, "event_start_pct": 40},
     "Rotor imbalance — 1× RPM vibration grows; both axes after 40% mark"),

    ("petroleum_pipeline", "small_leak",     "fault_pipeline_small_leak.csv",
     {"duration_minutes": 180, "fault_severity": 0.5, "event_start_pct": 40},
     "Small leak — gradual inlet pressure drop and flow divergence after 40% mark"),

    ("petroleum_pipeline", "large_leak",     "fault_pipeline_large_leak.csv",
     {"duration_minutes": 120, "fault_severity": 0.9, "event_start_pct": 40},
     "Large leak — rapid depressurisation and flow collapse after 40% mark"),

    ("petroleum_pipeline", "pump_trip",      "fault_pipeline_pump_trip.csv",
     {"duration_minutes": 120, "fault_severity": 0.8, "event_start_pct": 40},
     "Pump trip — sudden flow/pressure drop; system coasts down after 40% mark"),

    ("petroleum_pipeline", "sensor_drift",   "fault_pipeline_sensor_drift.csv",
     {"duration_minutes": 180, "fault_severity": 0.6, "event_start_pct": 40},
     "Sensor drift — slow bias creep in pressure reading after 40% mark"),

    ("power_plant", "tube_leak",             "fault_power_tube_leak.csv",
     {"duration_minutes": 120, "fault_severity": 0.8, "event_start_pct": 40},
     "Tube leak — condenser pressure rise and steam flow divergence after 40% mark"),

    ("power_plant", "condenser_fouling",     "fault_power_condenser_fouling.csv",
     {"duration_minutes": 180, "fault_severity": 0.6, "event_start_pct": 40},
     "Condenser fouling — gradual heat exchange degradation after 40% mark"),

    ("gas_pipeline", "compressor_trip",      "fault_gas_compressor_trip.csv",
     {"duration_minutes": 120, "fault_severity": 0.8, "event_start_pct": 40},
     "Compressor trip — sudden suction pressure rise and discharge drop after 40% mark"),

    ("gas_pipeline", "leak",                 "fault_gas_leak.csv",
     {"duration_minutes": 180, "fault_severity": 0.6, "event_start_pct": 40},
     "Gas leak — gradual line pressure loss and flow-balance divergence after 40% mark"),
]


def _available_scenarios(domain_id: str) -> list[str]:
    from sim.generator_registry import get_generator
    try:
        g = get_generator(domain_id)
        return [s.id for s in g.get_spec().scenarios]
    except Exception:
        return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domains", nargs="+", default=None,
                    help="Limit to specific domain IDs (default: all)")
    ap.add_argument("--rows", type=int, default=None,
                    help="Override duration to produce approximately this many rows")
    ap.add_argument("--hz", type=float, default=None,
                    help="Override sample_rate_hz")
    ap.add_argument("--dest", default=None,
                    help="Output directory (default: sim_data/sample)")
    args = ap.parse_args()

    dest = Path(args.dest) if args.dest else SAMPLE_DIR
    dest.mkdir(parents=True, exist_ok=True)
    ensure_dirs()

    specs = FAULT_SPECS
    if args.domains:
        specs = [s for s in specs if s[0] in args.domains]

    generated = []
    skipped = []

    for domain_id, scenario, filename, params, description in specs:
        available = _available_scenarios(domain_id)
        if scenario not in available:
            skipped.append((filename, f"scenario '{scenario}' not in {domain_id} ({available})"))
            continue

        p = dict(params)
        if args.hz is not None:
            p["sample_rate_hz"] = args.hz
        if args.rows is not None and "duration_minutes" in p and "sample_rate_hz" in p:
            hz = p.get("sample_rate_hz", args.hz or 1.0)
            p["duration_minutes"] = args.rows / (hz * 60.0)
        elif args.rows is not None:
            hz = p.get("sample_rate_hz", args.hz or 1.0)
            p["duration_minutes"] = args.rows / (hz * 60.0)

        req = GenerateRequest(
            scenario=scenario,
            output_filename=filename,
            parameters=p,
        )

        print(f"  generating {filename} ...", end=" ", flush=True)
        try:
            resp = generate_csv(domain_id, req)
        except Exception as exc:
            print(f"FAILED: {exc}")
            skipped.append((filename, str(exc)))
            continue

        # Move from generated/ to dest if different
        generated_path = ROOT / "sim_data" / "generated" / resp.filename
        target = dest / filename
        if generated_path.exists() and generated_path != target:
            import shutil
            shutil.move(str(generated_path), str(target))
        elif generated_path.exists():
            pass  # same file

        rows = resp.row_count
        cols = resp.column_count
        print(f"{rows:,} rows × {cols} cols")
        generated.append((filename, description, rows))

    print()
    if generated:
        print(f"Generated {len(generated)} fault dataset(s) in '{dest}':")
        for filename, description, rows in generated:
            print(f"  {filename:<45s} {rows:>6,} rows  —  {description}")
        print()
        print("Onboard as ACM assets:")
        print(f"  python scripts/acm_seed_demo.py --fault-dir {dest} --db acm_results.db")
        print()
        print("Or replay in Simulate tab → Files → select file → Load → Replay")

    if skipped:
        print(f"\nSkipped {len(skipped)} dataset(s):")
        for filename, reason in skipped:
            print(f"  {filename}: {reason}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        import traceback
        print(f"ERROR: {exc}", flush=True)
        traceback.print_exc()
        raise SystemExit(1)

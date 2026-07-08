"""Operational soak (evidence lane, issue #90): the implement-and-forget
proof. Runs the REAL service entrypoint as a subprocess against a
continuously-fed live buffer and watches it do everything unattended:
first-contact bootstrap, self-ticks, change declaration, governed
auto-absorption (#89), and fault detection - while sampling RSS and API
health the whole time.

Asset clock is time-compressed: the feeder writes one 10-minute-cadence
row per `--rows-per-second` wall second, so a 90-minute soak covers
about 37 asset-days.

Run:
    uv run python -m acm.evidence.soak --root results/soak1 --minutes 90

Phases (fractions of the fed rows):
    0.00-0.28  healthy continuation
    0.28-0.61  coordinated setpoint change (+2.5 on drivers) - must be
               declared change-not-fault and AUTO-ABSORBED once the
               plateau passes one anchor period of asset time
    0.61-1.00  local fault ramp on vib - must alarm

The final report checks each criterion and exits 1 on any failure, so a
soak is a gate, not a demo.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import polars as pl

from acm.store.raw import TIMESTAMP_COL, RawStore

UTC = timezone.utc
ASSET_KEY = "soak/1"
CADENCE_MIN = 10  # asset-clock minutes per row


def _row(rng, setpoint: float, fault: float) -> dict:
    temp = float(rng.normal()) + setpoint
    flow = float(rng.normal()) + setpoint
    press = float(rng.normal()) + setpoint
    return {
        "temp": temp,
        "vib": 0.8 * temp + 0.3 * float(rng.normal()) + fault,
        "press": press,
        "flow": flow,
        "load": 0.6 * temp + 0.4 * flow + 0.3 * float(rng.normal()),
        "power": 0.7 * flow + 0.3 * press + 0.3 * float(rng.normal()),
    }


def seed_history(store: RawStore, months: int = 6, seed: int = 21) -> datetime:
    """Backfill healthy history; returns the asset-clock 'now'."""
    rng = np.random.default_rng(seed)
    start = datetime(2025, 1, 1, tzinfo=UTC)
    n = 30 * 24 * 60 // CADENCE_MIN  # rows per month
    for m in range(months):
        t0 = start + timedelta(days=30 * m)
        rows = [_row(rng, 0.0, 0.0) for _ in range(n)]
        frame = pl.DataFrame(rows).with_columns(
            pl.Series(
                TIMESTAMP_COL,
                [t0 + timedelta(minutes=CADENCE_MIN * i) for i in range(n)],
                dtype=pl.Datetime("us", "UTC"),
            )
        )
        store.append(ASSET_KEY, frame)
    return start + timedelta(days=30 * months)


def _api(port: int, path: str):
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}{path}", timeout=5
    ) as r:
        return json.loads(r.read())


def _rss_mb(pid: int) -> float:
    try:
        parts = Path(f"/proc/{pid}/statm").read_text().split()
        return int(parts[1]) * 4096 / 1e6
    except OSError:
        return -1.0


def _healthy_after_change(samples: list[dict]) -> bool:
    """A healthy sample AFTER the first change-not-fault sample, still in
    the change phase = the plateau was absorbed and is the new normal."""
    seen_change = False
    for s in samples:
        if s.get("state") == "change-not-fault":
            seen_change = True
        elif (
            seen_change
            and s["phase"] == "change"
            and s.get("state") == "healthy"
        ):
            return True
    return False


def run_soak(
    root: Path,
    minutes: float,
    rows_per_second: float,
    port: int,
    tick_seconds: float,
) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    store = RawStore(root / "raw")
    asset_now = seed_history(store)
    buffer_db = root / "live_buffer.db"
    con = sqlite3.connect(buffer_db)
    con.execute(
        "CREATE TABLE IF NOT EXISTS mqtt_buffer "
        "(ts TEXT NOT NULL, payload_json TEXT NOT NULL)"
    )
    con.commit()

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "acm.service",
            "--root",
            str(root),
            "--port",
            str(port),
            "--tick-seconds",
            str(tick_seconds),
            "--live",
            f"{ASSET_KEY}={buffer_db}",
        ],
        stdout=(root / "service.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    total_rows = int(minutes * 60 * rows_per_second)
    ph_change, ph_fault = int(total_rows * 0.28), int(total_rows * 0.61)
    rng = np.random.default_rng(22)
    samples: list[dict] = []
    trace_path = root / "soak_trace.jsonl"
    started = time.monotonic()
    next_sample = started
    try:
        for i in range(total_rows):
            if proc.poll() is not None:
                break  # service died - the report will fail loudly
            ts = asset_now + timedelta(minutes=CADENCE_MIN * (i + 1))
            setpoint = 2.5 if i >= ph_change else 0.0
            fault = (
                4.0 * (i - ph_fault) / max(1, total_rows - ph_fault)
                if i >= ph_fault
                else 0.0
            )
            payload = {"published_at": ts.isoformat()}
            payload.update(_row(rng, setpoint, fault))
            con.execute(
                "INSERT INTO mqtt_buffer VALUES (?, ?)",
                (ts.isoformat(), json.dumps(payload)),
            )
            con.commit()
            now = time.monotonic()
            if now >= next_sample:
                next_sample = now + 30.0
                sample = {
                    "wall_s": round(now - started, 1),
                    "row": i,
                    "phase": (
                        "fault"
                        if i >= ph_fault
                        else "change" if i >= ph_change else "healthy"
                    ),
                    "rss_mb": round(_rss_mb(proc.pid), 1),
                }
                try:
                    detail = _api(port, f"/api/asset/{ASSET_KEY}")
                    sample.update(
                        state=detail.get("state"),
                        evidence=detail.get("evidence"),
                    )
                except Exception as exc:  # noqa: BLE001 - sampled, not fatal
                    sample["api_error"] = str(exc)[:120]
                samples.append(sample)
                with trace_path.open("a") as fh:
                    fh.write(json.dumps(sample) + "\n")
            time.sleep(1.0 / rows_per_second)
        time.sleep(2 * tick_seconds)  # let the last rows get ticked
        service_alive = proc.poll() is None
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        con.close()

    ledger_path = root / "ledger.json"
    episodes = (
        json.loads(ledger_path.read_text()) if ledger_path.exists() else []
    )
    by_phase: dict[str, set] = {"healthy": set(), "change": set(), "fault": set()}
    for s in samples:
        if "state" in s:
            by_phase[s["phase"]].add(s["state"])
    absorbed = [e for e in episodes if e["state"] == "change-not-fault"]
    rss = [s["rss_mb"] for s in samples if s.get("rss_mb", -1) > 0]

    criteria = {
        "service_alive_entire_soak": service_alive,
        "api_reachable_throughout": all("state" in s for s in samples[2:]),
        "healthy_phase_stays_healthy": by_phase["healthy"]
        <= {"healthy", "watch"},
        "change_declared": any(
            s.get("state") == "change-not-fault" for s in samples
        ),
        "change_auto_absorbed": len(absorbed) >= 1,
        "post_absorb_healthy_seen": _healthy_after_change(samples),
        "fault_phase_alarms": any(
            s.get("state") in ("alarm", "escalating")
            for s in samples
            if s["phase"] == "fault"
        ),
        "rss_bounded": bool(rss) and max(rss) < 2.5 * max(rss[0], 100.0),
    }
    report = {
        "minutes": minutes,
        "rows_fed": total_rows,
        "asset_days_covered": round(total_rows * CADENCE_MIN / 60 / 24, 1),
        "samples": len(samples),
        "rss_mb_first_last_max": (
            [rss[0], rss[-1], max(rss)] if rss else None
        ),
        "states_by_phase": {k: sorted(v) for k, v in by_phase.items()},
        "episodes": episodes,
        "criteria": criteria,
        "passed": all(criteria.values()),
    }
    (root / "soak_report.json").write_text(
        json.dumps(report, indent=1), encoding="utf-8"
    )
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", required=True)
    ap.add_argument("--minutes", type=float, default=90.0)
    ap.add_argument("--rows-per-second", type=float, default=1.0)
    ap.add_argument("--port", type=int, default=8901)
    ap.add_argument("--tick-seconds", type=float, default=20.0)
    args = ap.parse_args()
    report = run_soak(
        Path(args.root).resolve(),
        args.minutes,
        args.rows_per_second,
        args.port,
        args.tick_seconds,
    )
    print(json.dumps({k: v for k, v in report.items() if k != "episodes"}, indent=1))
    for name, ok in report["criteria"].items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

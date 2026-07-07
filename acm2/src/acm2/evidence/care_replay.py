"""CARE replay evidence runner (evidence lane, issue #86).

Replays CARE-to-Compare farm events through the PRODUCTION runtime path -
ingest -> onboard -> first-contact bootstrap -> chunked ticks - and checks
the verdicts against the farm's ground-truth labels. This is design-time
evidence (regression only, never tuning): results land in a gitignored out
dir and are summarized into the KB by hand.

Input layout (scripts/download_care_benchmark.py output, unchanged):
    <farm_dir>/event_info.csv
    <farm_dir>/datasets/{event_id}.csv

Run:
    uv run python -m acm2.evidence.care_replay \
        --farm-dir "../care_data/Wind Farm A" --events 40 68 \
        --out ../results/acm2_care_A

Adapter rules (the lab's hard-won ones, enforced here):
- CARE timestamps are naive strings; the DATASET's documentation defines
  them as UTC, so this adapter DECLARES the zone explicitly. The ingest
  rule "naive timestamps are rejected, never guessed" stays intact - the
  caller declares, ingest never guesses.
- Label and identity columns (status_type_id, train_test, id, asset_id)
  never enter the raw store; they are used for the split and the
  evaluation ONLY.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from acm2 import verdict as V
from acm2.runtime import Runtime
from acm2.store.raw import TIMESTAMP_COL, RawStore

# CARE meta/label columns - excluded from model input at the door.
META_COLS = ("time_stamp", "asset_id", "id", "train_test", "status_type_id")

# 2 days at CARE's 10-minute SCADA cadence. Small enough to give a usable
# detection-lag resolution, large enough that a full event replays in
# tens-to-hundreds of ticks (the production cadence class, not per-row).
DEFAULT_CHUNK_ROWS = 288

ALARMING = (V.STATE_ALARM, V.STATE_ESCALATING)


def load_event_info(farm_dir: Path) -> list[dict]:
    info = pl.read_csv(farm_dir / "event_info.csv")
    return info.to_dicts()


def load_event_frames(
    farm_dir: Path, event_id: object
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Read one event CSV, adapt to store shape, split train/prediction."""
    raw = pl.read_csv(
        farm_dir / "datasets" / f"{event_id}.csv", infer_schema_length=2000
    )
    if "train_test" not in raw.columns:
        raise ValueError(f"event {event_id}: no train_test column")
    raw = raw.with_columns(
        # naive-by-format, UTC-by-documentation: declared here, on purpose
        pl.col("time_stamp").str.to_datetime(time_unit="us", time_zone="UTC")
    ).rename({"time_stamp": TIMESTAMP_COL})
    drop = [c for c in META_COLS if c in raw.columns and c != "time_stamp"]
    keep_numeric = [
        c
        for c, dt in raw.schema.items()
        if c == TIMESTAMP_COL or (c not in drop and dt.is_numeric())
    ]
    train = raw.filter(pl.col("train_test") == "train").select(keep_numeric)
    predict = raw.filter(pl.col("train_test") == "prediction").select(
        keep_numeric
    )
    return train, predict


def _parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def replay_event(
    farm_dir: Path,
    event: dict,
    state_root: Path,
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
) -> dict:
    """One event through the production path; returns the evidence record."""
    event_id = event["event_id"]
    label = str(event["event_label"])
    key = f"care/{event_id}"
    train, predict = load_event_frames(farm_dir, event_id)

    data_root = state_root / f"event_{event_id}"
    store = RawStore(data_root / "raw")
    store.append(key, train)

    rt = Runtime(store=store, data_root=data_root)
    rt.onboard(key)
    rt.bootstrap_virgin()  # first contact, exactly as the service does

    ticks: list[dict] = []
    for start in range(0, predict.height, chunk_rows):
        chunk = predict.slice(start, chunk_rows)
        store.append(key, chunk)
        v = rt.tick(key)
        if v is not None:
            ticks.append(
                {
                    "at": str(v.at),
                    "state": v.state,
                    "evidence": float(v.evidence),
                }
            )

    event_start = _parse_utc(event["event_start"])
    states = [t["state"] for t in ticks]
    first_alarm = next(
        (t for t in ticks if t["state"] in ALARMING), None
    )
    detected = False
    lag_h = None
    if first_alarm is not None:
        first_at = _parse_utc(first_alarm["at"])
        # the tick's `at` is the chunk end; an alarm in the chunk that
        # CONTAINS event_start is a detection with ~zero lag, not early
        detected = first_at >= event_start
        if detected:
            lag_h = (first_at - event_start).total_seconds() / 3600.0
    record = {
        "event_id": event_id,
        "label": label,
        "asset_key": key,
        "train_rows": train.height,
        "predict_rows": predict.height,
        "ticks": len(ticks),
        "states_seen": sorted(set(states)),
        "insufficient": all(s == V.STATE_INSUFFICIENT for s in states)
        if states
        else True,
        "first_alarm_at": first_alarm["at"] if first_alarm else None,
        "event_start": str(event["event_start"]),
        "detected": detected,
        "lag_h": lag_h,
        "alarmed_at_all": first_alarm is not None,
        "change_not_fault_ticks": states.count(V.STATE_CHANGE),
        "tick_trace": ticks,
    }
    if label == "anomaly":
        record["outcome"] = "hit" if detected else "miss"
    else:
        record["outcome"] = (
            "false_alarm" if first_alarm is not None else "clean"
        )
    return record


def replay_farm(
    farm_dir: Path,
    out_dir: Path,
    events: list[str] | None = None,
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    info = load_event_info(farm_dir)
    if events:
        wanted = {str(e) for e in events}
        info = [e for e in info if str(e["event_id"]) in wanted]
        if not info:
            raise ValueError(f"no events matched {sorted(wanted)}")
    records = []
    skipped = []
    for event in info:
        if not (farm_dir / "datasets" / f"{event['event_id']}.csv").exists():
            # partial downloads are the norm (--count); absent CSVs are
            # skipped and reported, never an error
            skipped.append(event["event_id"])
            continue
        rec = replay_event(
            farm_dir, event, out_dir / "state", chunk_rows=chunk_rows
        )
        (out_dir / f"event_{rec['event_id']}.json").write_text(
            json.dumps(rec, indent=1), encoding="utf-8"
        )
        records.append(rec)
        print(
            f"  event {rec['event_id']:>4}  {rec['label']:<8} "
            f"-> {rec['outcome']:<11} "
            f"(lag_h={rec['lag_h'] if rec['lag_h'] is not None else '-'})"
        )
    anomalies = [r for r in records if r["label"] == "anomaly"]
    normals = [r for r in records if r["label"] != "anomaly"]
    summary = {
        "farm_dir": str(farm_dir),
        "chunk_rows": chunk_rows,
        "events": len(records),
        "skipped_no_csv": skipped,
        "anomalies": len(anomalies),
        "hits": sum(r["outcome"] == "hit" for r in anomalies),
        "misses": sum(r["outcome"] == "miss" for r in anomalies),
        "normals": len(normals),
        "clean": sum(r["outcome"] == "clean" for r in normals),
        "false_alarms": sum(r["outcome"] == "false_alarm" for r in normals),
        "records": [
            {k: r[k] for k in ("event_id", "label", "outcome", "lag_h")}
            for r in records
        ],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=1), encoding="utf-8"
    )
    print(
        f"summary: {summary['hits']}/{summary['anomalies']} anomalies hit, "
        f"{summary['false_alarms']}/{summary['normals']} normals "
        f"false-alarmed -> {out_dir / 'summary.json'}"
    )
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--farm-dir", required=True, help="CARE farm directory")
    ap.add_argument(
        "--events",
        nargs="*",
        default=None,
        help="event ids to replay (default: every event in event_info.csv)",
    )
    ap.add_argument("--out", required=True, help="output dir (gitignored)")
    ap.add_argument("--chunk-rows", type=int, default=DEFAULT_CHUNK_ROWS)
    args = ap.parse_args()
    replay_farm(
        Path(args.farm_dir),
        Path(args.out),
        events=args.events,
        chunk_rows=args.chunk_rows,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

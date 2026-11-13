"""Replay a case through a method and score the advisories it raised."""

from __future__ import annotations

import time
from collections import defaultdict

import numpy as np

from bench.cases import CADENCE_S, DAY, NEW_STATE, Case
from bench.methods import ROWS_PER_YEAR, Advisory, Method

# An advisory raised up to one day after an event ended still belongs to
# that event: a method may need time to accumulate evidence.
GRACE_ROWS = DAY


def replay(method: Method, case: Case, workdir) -> dict:
    ts = case.timestamps()
    method.start(case.columns, workdir)
    adv: list[Advisory] = []
    t0 = time.perf_counter()
    for s in range(0, case.n, method.chunk_rows):
        e = min(case.n, s + method.chunk_rows)
        adv.extend(method.step(s, ts[s:e], case.x[s:e]))
    secs = time.perf_counter() - t0
    method.close()
    return score_case(case, adv, secs)


def score_case(case: Case, adv: list[Advisory], secs: float = 0.0) -> dict:
    ev = case.event
    lo, hi = (ev.start, min(case.n, ev.end + GRACE_ROWS)) if ev else (case.n, case.n)
    inside = [a for a in adv if lo <= a.row < hi]
    # A "new operating state" notice on unlabelled data is not counted
    # against the false-advisory budget: a young asset really is
    # visiting states for the first time. It is reported separately.
    stray = [a for a in adv if not (lo <= a.row < hi)]
    outside = [a for a in stray if a.kind != NEW_STATE]
    rec = {
        "case": case.name, "asset_type": case.asset_type, "seed": case.seed,
        "rows": case.n, "seconds": secs,
        "healthy_rows": case.n - (hi - lo),
        "false_advisories": len(outside),
        "false_rows": [a.row for a in outside],
        "new_state_notices": len(stray) - len(outside),
    }
    if ev:
        if ev.kind == NEW_STATE:
            # the right answer is an advisory that says "new operating
            # state"; any other advisory here misreads a legitimate state
            named = [a for a in inside if a.kind == NEW_STATE]
            rec["misread"] = any(a.kind != NEW_STATE for a in inside)
            first = named[0] if named else None
        else:
            # a new-state notice does not count as finding a fault
            found = [a for a in inside if a.kind != NEW_STATE]
            first = found[0] if found else None
        rec.update({
            "kind": ev.kind, "shape": ev.shape, "stage": case.stage,
            "detected": first is not None,
            "delay_h": (first.row - ev.start) * CADENCE_S / 3600 if first else None,
            "reported_kind": ("none" if first is None
                              else first.kind or "unclassified"),
            "channel_hit": bool(first and set(first.channels) & set(ev.channels)),
        })
    return rec


def summarize(records: list[dict]) -> dict:
    healthy_rows = sum(r["healthy_rows"] for r in records)
    false = sum(r["false_advisories"] for r in records)
    years = healthy_rows / ROWS_PER_YEAR
    by = defaultdict(list)
    for r in records:
        if "kind" in r:
            by[(r["kind"], r["shape"], r["stage"])].append(r)
    detection = []
    for (kind, shape, stage), rs in sorted(by.items()):
        delays = [r["delay_h"] for r in rs if r["detected"]]
        detection.append({
            "kind": kind, "shape": shape, "stage": stage, "cases": len(rs),
            "detected": sum(r["detected"] for r in rs),
            "median_delay_h": float(np.median(delays)) if delays else None,
            "misread": sum(bool(r.get("misread")) for r in rs),
        })
    confusion: dict = defaultdict(lambda: defaultdict(int))
    for r in records:
        if "kind" in r:
            confusion[r["kind"]][r["reported_kind"]] += 1
    rows = sum(r["rows"] for r in records)
    return {
        "cases": len(records),
        "healthy_asset_years": years,
        "false_advisories": false,
        "false_per_asset_year": false / years if years > 0 else None,
        "new_state_notices": sum(r.get("new_state_notices", 0) for r in records),
        "false_first_week": sum(sum(x < 7 * DAY for x in r["false_rows"])
                                for r in records),
        "false_by_asset_type": {
            t: sum(r["false_advisories"] for r in records if r["asset_type"] == t)
            for t in sorted({r["asset_type"] for r in records})
        },
        "detection": detection,
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "microseconds_per_row": 1e6 * sum(r["seconds"] for r in records) / max(rows, 1),
    }


def render(name: str, split: str, s: dict) -> str:
    fy = s["false_per_asset_year"] or 0.0
    out = [
        f"### {name} on {split}",
        "",
        f"- cases: {s['cases']}; healthy exposure: "
        f"{s['healthy_asset_years']:.2f} asset-years",
        f"- false advisories: {s['false_advisories']} "
        f"({fy:.1f} per asset-year; budget 1.0) by type "
        f"{s['false_by_asset_type']}; {s['false_first_week']} of them in "
        f"an asset's first week",
        f"- new-state notices on unlabelled data: {s['new_state_notices']}",
        f"- cost: {s['microseconds_per_row']:.1f} microseconds per row",
        "",
        "| kind | shape | onset age | detected | median delay h | misread |",
        "|---|---|---|---|---|---|",
    ]
    for d in s["detection"]:
        md = "-" if d["median_delay_h"] is None else f"{d['median_delay_h']:.1f}"
        out.append(f"| {d['kind']} | {d['shape']} | {d['stage']} | "
                   f"{d['detected']}/{d['cases']} | {md} | {d['misread']} |")
    out += ["", "Reported kind per true kind: " + str(s["confusion"]), ""]
    return "\n".join(out)

"""ACM config spine (S0.5, D1).

The ENTIRE tunable surface of ACM is ALPHA_PER_ASSET_YEAR. Everything else
is a structural constant registered here with a written derivation. There is
deliberately no config file, no per-site table, no ml_defaults successor:
anything that looks like a tunable is either derived by the system from the
asset's own data or is a structural constant whose rationale is recorded in
this registry (implementation plan Section 6).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Constant:
    name: str
    value: object
    rationale: str


ALPHA_PER_ASSET_YEAR = 1.0
"""The one dial: promised false-alarm budget per asset per year (D1).

Ville's inequality converts this directly into the e-process alarm
threshold; it is a guarantee parameter, not a sensitivity tuning knob.
"""

REGISTRY: dict[str, Constant] = {
    c.name: c
    for c in [
        Constant(
            "ALPHA_PER_ASSET_YEAR",
            ALPHA_PER_ASSET_YEAR,
            "One false alarm per asset-year: industry-credible unattended "
            "rate, loose enough to preserve detection power (D1). The only "
            "exposed dial in ACM.",
        ),
        Constant(
            "REANCHORS_PER_YEAR",
            52,
            "Weekly rebuild/re-anchor cadence (D3). Converts the yearly "
            "false-alarm RATE dial into the per-anchor Ville PROBABILITY: "
            "alarms latch, so each anchor period contributes at most one "
            "false alarm, with probability <= ALPHA_PER_ASSET_YEAR / "
            "REANCHORS_PER_YEAR. Expected false alarms per year is then "
            "<= ALPHA_PER_ASSET_YEAR, which is the promised budget.",
        ),
        Constant(
            "RECENCY_CAP",
            0.20,
            "Maximum weight the recent window may hold in the definition of "
            "normal (D2). Bounds the boiling-frog failure mode "
            "arithmetically while allowing legitimate aging.",
        ),
        Constant(
            "RAW_STORE_PARTITION",
            "month",
            "Calendar-month parquet partitions: large enough for columnar "
            "efficiency at SCADA cadence, small enough that rewrite-on-"
            "append stays cheap (S0.2).",
        ),
        Constant(
            "EVIDENCE_WORKERS_MAX_LOW_RAM",
            2,
            "On hosts below 24GB RAM, evidence/benchmark runs cap at 2 "
            "workers with BLAS caps: the lab's measured OOM/fork-deadlock "
            "envelope on 15-16GB machines (CLAUDE.md mistakes #42/#44).",
        ),
        Constant(
            "CHANGE_ABSORB_ANCHOR_PERIODS",
            1.0,
            "A change-not-fault plateau that has held for this many ANCHOR "
            "periods (365.25d / REANCHORS_PER_YEAR each, about a week) is "
            "absorbed automatically - the governed execution of the "
            "verdict's own re-baseline proposal, required for unattended "
            "operation (#89). One anchor period is the system's own "
            "granularity of how long a definition of normal holds, and it "
            "spaces absorptions to at most one per anchor period per "
            "asset, keeping the alpha-per-anchor Ville accounting inside "
            "the declared budget: an absorb IS an anchor. Drift-shaped "
            "(escalating) episodes never absorb - the definition of "
            "normal does not move during accumulating evidence of "
            "degradation.",
        ),
    ]
}


def get(name: str) -> object:
    return REGISTRY[name].value

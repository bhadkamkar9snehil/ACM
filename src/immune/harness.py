"""The immune harness (S2): the referee that never trusts self-report.

Three checks, all label-free, all on the asset's own data:

1. SENSITIVITY PROFILE - inject canonical faults into held-out healthy data
   at a magnitude ladder; record which (class, magnitude) cells the monitor
   detects. A dead scorer (the OMR incident class) produces an all-miss
   profile and is flagged the day it dies, not months later.
2. CALIBRATION CONFORMANCE - clean held-out data must NOT alarm (the alpha
   guarantee, checked empirically per asset, continuously).
3. DEGENERACY - a scorer whose output has (near-)zero variance carries no
   information regardless of what the profile says.

The profile is per (asset, scorer, fault_class): the sensitivity FLOOR is
the smallest magnitude detected. Honest scope: the profile covers the
rehearsed fault manifold only (gem plan caveat) - the novelty engine covers
the rest from S5.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from immune.inject import FAULT_CLASSES, inject
from monitor import AssetMonitor
from verdict import STATE_ALARM

MAGNITUDE_LADDER = (0.5, 1.0, 2.0, 4.0)
DEGENERACY_MIN_STD = 1e-9
DEGENERACY_MIN_UNIQUE = 5


@dataclass
class ImmuneReport:
    asset_key: str
    conformance_ok: bool
    conformance_evidence: float
    degenerate: bool
    profile: dict[str, dict[float, bool]] = field(default_factory=dict)
    floors: dict[str, float | None] = field(default_factory=dict)

    @property
    def scorer_dead(self) -> bool:
        """OMR-class verdict: degenerate output OR an all-miss profile."""
        all_miss = all(
            not any(cells.values()) for cells in self.profile.values()
        )
        return self.degenerate or all_miss

    def to_dict(self) -> dict:
        return {
            "asset_key": self.asset_key,
            "conformance_ok": self.conformance_ok,
            "conformance_evidence": self.conformance_evidence,
            "degenerate": self.degenerate,
            "scorer_dead": self.scorer_dead,
            "floors": self.floors,
            "profile": {
                k: {str(m): v for m, v in cells.items()}
                for k, cells in self.profile.items()
            },
        }


def degeneracy_check(scores: np.ndarray) -> bool:
    """True = degenerate (constant/near-constant output, zero information)."""
    s = np.asarray(scores, dtype=np.float64)
    s = s[np.isfinite(s)]
    if s.size == 0:
        return True
    return float(np.std(s)) < DEGENERACY_MIN_STD or (
        np.unique(np.round(s, 12)).size < DEGENERACY_MIN_UNIQUE
    )


def sensitivity_profile(
    asset_key: str,
    healthy: pl.DataFrame,
    monitor_cls=AssetMonitor,
    fault_classes: tuple[str, ...] = FAULT_CLASSES,
    magnitudes: tuple[float, ...] = MAGNITUDE_LADDER,
    seed: int = 0,
) -> ImmuneReport:
    """Split healthy -> calib + holdout; rehearse every (class, magnitude)."""
    n = healthy.height
    calib, holdout = healthy.head(n // 2), healthy.slice(n // 2)

    # conformance + degeneracy on the clean holdout
    clean_mon = monitor_cls(asset_key)
    calibrated = clean_mon.calibrate(calib, seed=seed)
    if not calibrated:
        return ImmuneReport(
            asset_key, conformance_ok=False, conformance_evidence=0.0,
            degenerate=True,
        )
    clean_verdict = clean_mon.process(holdout)
    conformance_ok = clean_verdict.state != STATE_ALARM
    degenerate = degeneracy_check(clean_mon.scorer.score(holdout))

    profile: dict[str, dict[float, bool]] = {}
    floors: dict[str, float | None] = {}
    for fc in fault_classes:
        cells: dict[float, bool] = {}
        for mag in magnitudes:
            faulty, _col = inject(holdout, fc, magnitude=mag, seed=seed)
            mon = monitor_cls(asset_key)
            mon.calibrate(calib, seed=seed)
            verdict = mon.process(faulty)
            cells[mag] = verdict.state == STATE_ALARM
        profile[fc] = cells
        detected = [m for m, hit in cells.items() if hit]
        floors[fc] = min(detected) if detected else None

    return ImmuneReport(
        asset_key=asset_key,
        conformance_ok=conformance_ok,
        conformance_evidence=clean_verdict.evidence,
        degenerate=degenerate,
        profile=profile,
        floors=floors,
    )


def run_immune_check(store, asset_key: str, max_rows: int = 20000, seed: int = 0) -> ImmuneReport:
    """Runtime self-test entrypoint (scheduled from S6): uses the most
    recent max_rows of the asset's stored life as the healthy sample.
    Consumers must treat scorer_dead / not conformance_ok as first-class
    events: confidence drops and a rebuild is triggered."""
    frame = store.read(asset_key)
    if frame.height > max_rows:
        frame = frame.tail(max_rows)
    return sensitivity_profile(asset_key, frame, seed=seed)

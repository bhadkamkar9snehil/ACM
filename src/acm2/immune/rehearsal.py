"""Counterfactual rehearsal (gem C8): the dreaming immune system.

The model that has learned the machine's healthy couplings can IMAGINE the
machine degraded: seed a fault in one channel and propagate the response
through the learned coupling structure, so the synthesized telemetry is
PHYSICALLY COHERENT - followers respond the way the machine's own physics
says they would. Coherent faults are strictly harder to detect than naive
single-channel injections (the coupled response EXPLAINS part of the
deviation away), so the rehearsed manifold maps the honest detection
boundary, not a flattering one.

Output: a per-(channel, shape, propagation) sensitivity map with detection
floors - the measured lower bound on what this asset's current pipeline
can see. This is the missing half of the accuracy story: false alarms are
bounded by mathematics (Ville); missed detections are bounded by rehearsal
(measured, scoped to the rehearsed manifold - the novelty engine covers
the unknown unknowns beyond it).

Uses fresh e-process banks per cell over the SAME calibration scores the
live bank was built from, so a rehearsal cell answers exactly: 'would the
deployed decision layer alarm on this imagined fault?'
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from acm2.decision.eprocess import EProcessBank

MAGNITUDES = (0.5, 1.0, 2.0, 4.0)
SHAPES = ("drift", "step")
PROPAGATIONS = (0.0, 0.5)  # none (naive) and partial physical propagation
MAX_SEED_CHANNELS = 5  # rehearse the highest-coupling channels
REHEARSAL_ALPHA = 0.02  # per-cell bank budget (cells are independent
# thought experiments, not production alarms - this is a measurement
# instrument, so a fixed per-cell probability is the right semantics)


@dataclass
class RehearsalMap:
    floors: dict[str, float | None] = field(default_factory=dict)
    cells: dict[str, dict] = field(default_factory=dict)
    overall_floor: float | None = None
    detected_fraction: float = 0.0
    scope: str = ""

    def to_dict(self) -> dict:
        return {
            "floors": self.floors,
            "overall_floor": self.overall_floor,
            "detected_fraction": round(self.detected_fraction, 3),
            "scope": self.scope,
            "cells": self.cells,
        }


def _seed_channels(scorer) -> list[int]:
    """Rehearse the channels with the strongest couplings (where coherent
    propagation matters most), capped for cost."""
    coupling = np.abs(scorer.betas).sum(axis=0)
    order = np.argsort(coupling)[::-1]
    return list(order[:MAX_SEED_CHANNELS])


def rehearse(
    scorer,
    holdout: pl.DataFrame,
    calib_scores: np.ndarray,
    seed: int = 0,
) -> RehearsalMap:
    """Map the detection boundary of the CURRENT pipeline on self-imagined
    coherent faults. scorer must expose channels/betas/scales/_aligned
    matrix machinery (the conditional scorer and its successors do)."""
    z_cols = {ch: k for k, ch in enumerate(scorer.channels)}
    base = scorer._aligned_matrix(holdout)
    n, d = base.shape
    onset = int(n * 0.2)
    result = RehearsalMap(
        scope=(
            f"{len(_seed_channels(scorer))} seed channels x {SHAPES} x "
            f"{MAGNITUDES} x propagation {PROPAGATIONS} on {n} holdout rows"
        )
    )
    detected_cells, total_cells = 0, 0
    for ci in _seed_channels(scorer):
        ch = scorer.channels[ci]
        per_channel_detected: list[float] = []
        for shape in SHAPES:
            for prop in PROPAGATIONS:
                for mag in MAGNITUDES:
                    total_cells += 1
                    x = base.copy()
                    scale = scorer.scales[ci]
                    if shape == "drift":
                        delta = np.linspace(0.0, mag * scale, n - onset)
                    else:
                        delta = np.full(n - onset, mag * scale)
                    x[onset:, ci] += delta
                    if prop > 0.0:
                        # coherent response: followers move per the learned
                        # couplings (first order), scaled by propagation
                        response = np.outer(
                            delta / scale, scorer.betas[:, ci]
                        ) * prop
                        x[onset:, :] += response * scorer.scales
                    frame = pl.DataFrame(
                        {c: x[:, z_cols[c]] for c in scorer.channels}
                    )
                    scores = scorer.score(frame)
                    bank = EProcessBank(
                        calib_scores, alpha=REHEARSAL_ALPHA, seed=seed
                    )
                    alarmed = bank.update(scores[onset:]).alarmed
                    key = f"{ch}|{shape}|p{prop}"
                    cell = result.cells.setdefault(
                        key, {"detected_at": []}
                    )
                    if alarmed:
                        cell["detected_at"].append(mag)
                        detected_cells += 1
                        per_channel_detected.append(mag)
        result.floors[ch] = (
            min(per_channel_detected) if per_channel_detected else None
        )
    finite = [f for f in result.floors.values() if f is not None]
    result.overall_floor = min(finite) if finite else None
    result.detected_fraction = (
        detected_cells / total_cells if total_cells else 0.0
    )
    return result

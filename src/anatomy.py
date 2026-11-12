"""Learned anatomy (gem C6, classical Tier 0 form).

A machine's channels have a functional anatomy - which drive, which
follow, which move together. It is learnable from healthy data: the
conditional scorer's ridge coefficients ARE the dependence structure.
This module makes that structure first-class:

- STABILITY SELECTION (the anti-hallucination rule from the gem plan's
  caveats): the graph is fit on multiple half-samples; an edge exists only
  if it appears, strongly, in nearly all of them. Dense SCADA correlation
  produces spurious edges; only structure that survives resampling is
  trusted for root-cause claims.
- ORGANS: connected components of the stable graph - the machine's
  subsystems, discovered without an engineering drawing.
- PER-ORGAN SURPRISE: residual evidence aggregated per organ ("the pitch
  subsystem is degrading" is a different product than "channel 412 is
  anomalous").
- ORIGIN: over an episode, the organ whose elevation began FIRST is the
  root-cause candidate; everything later is symptom. Corroboration for
  attribution, never standalone proof (verdicts carry it with the onset
  order, not as a bare claim).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from scoring.surprise import ConditionalSurpriseScorer

EDGE_BETA_MIN = 0.15  # |standardized ridge weight| below this is noise
STABILITY_FRACTION = 0.8  # edge must appear in this share of half-fits
N_SUBSAMPLES = 5
ORGAN_ELEV_Z = 3.0  # organ counts as elevated above this mean residual z
ORGAN_ELEV_RUN = 8  # sustained rows required for an onset


@dataclass
class Anatomy:
    channels: list[str]
    organs: list[tuple[str, ...]] = field(default_factory=list)
    organ_of: dict[str, int] = field(default_factory=dict)
    # How many of N_SUBSAMPLES actually voted (channel-set-unstable
    # subsamples are dropped, see learn()). STABILITY_FRACTION is applied
    # against N_SUBSAMPLES regardless of this count, so a caller/test can
    # use it to tell "4/5 agreed" apart from "4/5 of only 4 usable agreed" -
    # previously invisible, silently weakening the stability guarantee.
    usable_subsamples: int = N_SUBSAMPLES

    @classmethod
    def learn(cls, frame: pl.DataFrame, seed: int = 0) -> "Anatomy":
        rng = np.random.default_rng(seed)
        n = frame.height
        votes: dict[tuple[int, int], int] = {}
        channels: list[str] | None = None
        usable = 0
        for s in range(N_SUBSAMPLES):
            idx = np.sort(
                rng.choice(n, size=max(200, n // 2), replace=False)
            )
            sub = frame[idx.tolist()]
            scorer = ConditionalSurpriseScorer().fit(sub)
            if channels is None:
                channels = scorer.channels
            elif scorer.channels != channels:
                continue  # channel set unstable on this subsample
            usable += 1
            b = np.abs(scorer.betas)
            sym = np.maximum(b, b.T)
            d = len(channels)
            for i in range(d):
                for j in range(i + 1, d):
                    if sym[i, j] > EDGE_BETA_MIN:
                        votes[(i, j)] = votes.get((i, j), 0) + 1
        assert channels is not None
        d = len(channels)
        parent = list(range(d))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        needed = int(np.ceil(STABILITY_FRACTION * N_SUBSAMPLES))
        for (i, j), v in votes.items():
            if v >= needed:
                parent[find(i)] = find(j)
        groups: dict[int, list[str]] = {}
        for i, ch in enumerate(channels):
            groups.setdefault(find(i), []).append(ch)
        anatomy = cls(channels=channels, usable_subsamples=usable)
        for members in sorted(groups.values(), key=len, reverse=True):
            organ_idx = len(anatomy.organs)
            anatomy.organs.append(tuple(members))
            for ch in members:
                anatomy.organ_of[ch] = organ_idx
        return anatomy

    def organ_surprise(
        self, scorer: ConditionalSurpriseScorer, frame: pl.DataFrame
    ) -> dict[tuple[str, ...], float]:
        """Mean |residual z| per organ over the frame's tail."""
        rz = np.abs(scorer._residual_z(frame.tail(min(frame.height, 512))))
        col_of = {ch: k for k, ch in enumerate(scorer.channels)}
        out = {}
        for organ in self.organs:
            cols = [col_of[ch] for ch in organ if ch in col_of]
            if cols:
                out[organ] = float(np.nanmean(rz[:, cols]))
        return out

    def origin(
        self, scorer: ConditionalSurpriseScorer, episode_frame: pl.DataFrame
    ) -> dict:
        """Root-cause candidate: onset ORDER of organ elevation across the
        episode. Returns organs with their onset row (None = never
        elevated); the earliest is the origin candidate."""
        rz = np.abs(scorer._residual_z(episode_frame))
        col_of = {ch: k for k, ch in enumerate(scorer.channels)}
        onsets: dict[tuple[str, ...], int | None] = {}
        for organ in self.organs:
            cols = [col_of[ch] for ch in organ if ch in col_of]
            if not cols:
                continue
            trace = np.nanmean(rz[:, cols], axis=1) > ORGAN_ELEV_Z
            onset = None
            run = 0
            for i, hot in enumerate(trace):
                run = run + 1 if hot else 0
                if run >= ORGAN_ELEV_RUN:
                    onset = i - ORGAN_ELEV_RUN + 1
                    break
            onsets[organ] = onset
        elevated = {o: s for o, s in onsets.items() if s is not None}
        origin_organ = (
            min(elevated, key=elevated.get) if elevated else None
        )
        return {
            "origin": origin_organ,
            "onsets": {
                ",".join(o): s for o, s in onsets.items()
            },
        }

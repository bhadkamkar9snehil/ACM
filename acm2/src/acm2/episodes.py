"""Episodic monitor (S5): episodes, signatures, re-anchoring - the loop
closes here.

Wraps AssetMonitor with the consumer-side logic the e-process layer
deliberately does not own:

- ALARM -> OPEN EPISODE: first alarm verdict opens a ledger episode
  carrying its signature (attributed channels + surprise shape + novelty).
- SIGNATURE MATCH: a new episode is compared against the asset's own past
  episodes (Jaccard on attributed channels + same shape) - case-based
  reasoning on the asset's own history, confidence reported, never gating.
- SHAPE: drift -> the alarm stands (fault-like). step-to-stable ->
  verdict becomes change-not-fault with a re-baseline proposal. The alarm
  evidence is NOT discarded (validity layer stays untouched); only the
  verdict WORD and the proposed action differ.
- REANCHOR: closes the episode into the ledger and recalibrates from
  ledger-masked lifetime memory - the one governed way wealth resets
  (matches the e-process latching contract).

Honest v1 scope: novelty enriches evidence and signatures; it does not
veto alarms (the recurrence whitelist needs never-alarmed bookkeeping that
matures with the ledger).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
import polars as pl

from acm2 import verdict as V
from acm2.memory.ledger import Episode, EpisodeLedger
from acm2.monitor import AssetMonitor
from acm2.novelty import NoveltyEngine, classify_shape
from acm2.store.raw import TIMESTAMP_COL

SIGNATURE_MATCH_MIN = 0.34  # Jaccard floor below which a match is not reported
CHANGE_CONCENTRATION_MAX = 0.4  # normalized; above = channel-local = fault


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


@dataclass
class EpisodicMonitor:
    monitor: AssetMonitor
    ledger: EpisodeLedger
    novelty: NoveltyEngine = field(default_factory=NoveltyEngine)
    open_episode_start: str = ""
    _episode_scores: list[np.ndarray] = field(default_factory=list)
    _episode_first_frame_ts: str = ""

    @property
    def asset_key(self) -> str:
        return self.monitor.asset_key

    def process(self, frame: pl.DataFrame) -> V.Verdict:
        scores = (
            self.monitor.scorer.score(frame)
            if self.monitor.scorer is not None
            else np.array([])
        )
        verdict = self.monitor.process(frame)

        if verdict.state == V.STATE_ALARM:
            if not self.open_episode_start:
                self.open_episode_start = self._first_ts(frame)
            self._episode_scores.append(scores)
            verdict = self._enrich_alarm(verdict, frame)
        else:
            # only healthy stretches feed the recurrence memory
            self.novelty.extend(scores)
        return verdict

    def _enrich_alarm(self, verdict: V.Verdict, frame: pl.DataFrame) -> V.Verdict:
        seg = np.concatenate(self._episode_scores)
        shape = classify_shape(seg)
        nov = self.novelty.novelty(seg)
        match_key, match_conf = self._signature_match(
            set(verdict.attribution), shape
        )
        trail = dict(verdict.evidence_trail)
        trail.update(
            {
                "episode_start": self.open_episode_start,
                "shape": shape,
                "novelty": round(nov, 3),
                "signature_match": (
                    {"episode": match_key, "confidence": round(match_conf, 2)}
                    if match_key
                    else None
                ),
            }
        )
        # step-shaped episodes need CORROBORATION (P2): shape alone cannot
        # separate a constant-severity fault from a setpoint change - both
        # plateau. The second axis is attribution concentration: a fault
        # is channel-local, an operating change is a coordinated move.
        conc = (
            self.monitor.scorer.concentration(frame)
            if hasattr(self.monitor.scorer, "concentration")
            else 1.0
        )
        trail["concentration"] = round(conc, 3)
        state = verdict.state
        falsifiable = verdict.falsifiable_by
        if shape == "step" and conc < CHANGE_CONCENTRATION_MAX:
            state = V.STATE_CHANGE
            falsifiable = (
                "re-baseline proposal: if the new plateau is a legitimate "
                "operating change, re-anchoring absorbs it; if surprise "
                "resumes growing post-re-anchor, this escalates to alarm"
            )
        elif shape == "drift":
            state = V.STATE_ESCALATING
            falsifiable = (
                "surprise trend flattening (Kendall tau below the drift "
                "threshold) downgrades this to a plain alarm"
            )
        return V.Verdict(
            asset_key=verdict.asset_key,
            at=verdict.at,
            state=state,
            confidence=verdict.confidence,
            evidence=verdict.evidence,
            evidence_trail=trail,
            attribution=verdict.attribution,
            model_epoch=verdict.model_epoch,
            coverage=verdict.coverage,
            falsifiable_by=falsifiable,
        )

    def _signature_match(
        self, channels: set[str], shape: str
    ) -> tuple[str | None, float]:
        best_key, best = None, 0.0
        for ep in self.ledger.episodes:
            if ep.asset_key != self.asset_key or not ep.note:
                continue
            try:
                sig = json.loads(ep.note)
            except json.JSONDecodeError:
                continue
            score = _jaccard(channels, set(sig.get("channels", [])))
            if sig.get("shape") == shape:
                score = 0.7 * score + 0.3
            if score > best:
                best_key, best = ep.start, score
        if best >= SIGNATURE_MATCH_MIN:
            return best_key, best
        return None, 0.0

    def reanchor(self, store, last_verdict: V.Verdict, cache_root=None) -> bool:
        """Close the open episode into the ledger, recalibrate from the
        ledger-masked lifetime, reset episode state. The governed reset."""
        if self.open_episode_start:
            seg = (
                np.concatenate(self._episode_scores)
                if self._episode_scores
                else np.array([])
            )
            self.ledger.add(
                Episode(
                    asset_key=self.asset_key,
                    start=self.open_episode_start,
                    end=self.monitor.last_ts,
                    state=(
                        "change-not-fault"
                        if last_verdict.state == V.STATE_CHANGE
                        else "alarm"
                    ),
                    note=json.dumps(
                        {
                            "channels": list(last_verdict.attribution),
                            "shape": classify_shape(seg) if seg.size else "noisy",
                            "peak_evidence": last_verdict.evidence,
                        }
                    ),
                )
            )
        self.open_episode_start = ""
        self._episode_scores = []
        return self.monitor.calibrate_from_lifetime(
            store, ledger=self.ledger, cache_root=cache_root
        )

    @staticmethod
    def _first_ts(frame: pl.DataFrame) -> str:
        return (
            str(frame.get_column(TIMESTAMP_COL).min())
            if not frame.is_empty()
            else ""
        )

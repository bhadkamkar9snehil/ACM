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
HEALTH_INDEX_CHUNK = 128  # rows per health-index sample (prognosis, S8)
HEALTH_INDEX_MAX = 4096  # cap: implement-and-forget must not leak memory


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
    _health_index: list[float] = field(default_factory=list)

    @property
    def asset_key(self) -> str:
        return self.monitor.asset_key

    def process(self, frame: pl.DataFrame) -> V.Verdict:
        scores = (
            self.monitor.scorer.score(frame)
            if self.monitor.scorer is not None
            else np.array([])
        )
        if scores.size:
            # health index: windowed-mean-surprise samples (chunked so the
            # prognosis trajectory has resolution regardless of frame size)
            for i in range(0, scores.size, HEALTH_INDEX_CHUNK):
                chunk = scores[i : i + HEALTH_INDEX_CHUNK]
                if chunk.size >= HEALTH_INDEX_CHUNK // 2:
                    self._health_index.append(float(np.mean(chunk)))
            if len(self._health_index) > HEALTH_INDEX_MAX:
                self._health_index = self._health_index[-HEALTH_INDEX_MAX:]
        verdict = self.monitor.process(frame)

        if verdict.state == V.STATE_ALARM:
            if not self.open_episode_start:
                self.open_episode_start = self._onset_ts(frame, scores)
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
        mon = self.monitor
        if (
            mon.anatomy is not None
            and hasattr(mon.scorer, "_residual_z")
            and not frame.is_empty()
        ):
            trail["anatomy"] = {
                "organ_surprise": {
                    ",".join(o): round(v, 2)
                    for o, v in mon.anatomy.organ_surprise(
                        mon.scorer, frame
                    ).items()
                },
                **mon.anatomy.origin(mon.scorer, frame),
            }
            trail["anatomy"]["origin"] = (
                ",".join(trail["anatomy"]["origin"])
                if trail["anatomy"]["origin"]
                else None
            )
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
            trail["horizon"] = self._compute_horizon().to_dict()
            match = self._trajectory_match()
            if match is not None:
                trail["trajectory_match"] = match
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

    def _compute_horizon(self):
        """Failure-time distribution from the health-index trajectory (S8).
        Healthy center/spread come from the bank's own calibration score
        distribution; critical level prefers the asset's own past episode
        onset levels (self-deriving), provisional structural default until
        the first episode exists."""
        from acm2.prognosis import Horizon, horizon

        bank = self.monitor.bank
        if bank is None or not self._health_index:
            return Horizon(False, "no calibration or trajectory")
        calib = bank.members[0]._calib_sorted
        center = float(np.median(calib))
        spread = 1.4826 * float(np.median(np.abs(calib - center)))
        onset_levels = []
        for ep in self.ledger.episodes:
            if ep.asset_key == self.asset_key and ep.state == "alarm" and ep.note:
                try:
                    lvl = json.loads(ep.note).get("onset_level")
                    if lvl is not None:
                        onset_levels.append(float(lvl))
                except json.JSONDecodeError:
                    pass
        return horizon(
            np.asarray(self._health_index),
            center,
            spread,
            ledger_onset_levels=onset_levels or None,
        )

    def _trajectory_match(self) -> dict | None:
        """Manifold prognosis (G4 ceiling): match the open episode's
        surprise TRAJECTORY against past episodes' stored curves - "you
        are N chunks along a path that took M chunks to its peak". The IG
        horizon is the model-based floor; this is the case-based estimate,
        reported alongside, never instead."""
        seg = (
            np.concatenate(self._episode_scores)
            if self._episode_scores
            else np.array([])
        )
        cur = [
            float(np.mean(seg[i : i + HEALTH_INDEX_CHUNK]))
            for i in range(0, seg.size, HEALTH_INDEX_CHUNK)
            if seg[i : i + HEALTH_INDEX_CHUNK].size >= HEALTH_INDEX_CHUNK // 2
        ]
        if len(cur) < 3:
            return None
        best = None
        for ep in self.ledger.episodes:
            if ep.asset_key != self.asset_key or not ep.note:
                continue
            try:
                curve = json.loads(ep.note).get("index_curve") or []
            except json.JSONDecodeError:
                continue
            if len(curve) <= len(cur):
                continue  # only past episodes we are PART-WAY along
            ref = np.array(curve[: len(cur)])
            c = np.array(cur)
            scale = max(float(np.std(ref)), 1e-9)
            dist = float(np.sqrt(np.mean((ref - c) ** 2))) / scale
            if best is None or dist < best["distance"]:
                best = {
                    "episode": ep.start,
                    "distance": round(dist, 3),
                    "position_chunks": len(cur),
                    "matched_length_chunks": len(curve),
                    "remaining_rows_estimate": (len(curve) - len(cur))
                    * HEALTH_INDEX_CHUNK,
                }
        if best is not None and best["distance"] < 2.0:
            return best
        return None

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
                            # health-index level at episode onset: calibrates
                            # this asset's critical level for future horizons
                            "onset_level": (
                                float(np.mean(seg[: HEALTH_INDEX_CHUNK]))
                                if seg.size
                                else None
                            ),
                            # trajectory memory (manifold prognosis): the
                            # episode's chunked surprise curve, capped
                            "index_curve": [
                                round(float(np.mean(seg[i : i + HEALTH_INDEX_CHUNK])), 4)
                                for i in range(
                                    0, min(seg.size, 64 * HEALTH_INDEX_CHUNK),
                                    HEALTH_INDEX_CHUNK,
                                )
                                if seg[i : i + HEALTH_INDEX_CHUNK].size
                                >= HEALTH_INDEX_CHUNK // 2
                            ],
                        }
                    ),
                )
            )
        self.open_episode_start = ""
        self._episode_scores = []
        # absorbing a CHANGE: the adjudicated plateau must enter the
        # calibration reference or the same episode re-opens forever;
        # closing a FAULT keeps the strict older-life-only reference
        return self.monitor.calibrate_from_lifetime(
            store,
            ledger=self.ledger,
            cache_root=cache_root,
            include_recent=last_verdict.state == V.STATE_CHANGE,
        )

    @staticmethod
    def _onset_ts(frame: pl.DataFrame, scores: np.ndarray) -> str:
        """Episode start = where the surprise ONSET is, not where the frame
        begins. Found by review: a first full-history tick opened the
        episode at row zero, so a later re-anchor masked the asset's
        ENTIRE life out of its own baseline. Onset = first sustained
        window above the frame's own robust bar; falls back to the frame
        start when the whole frame is hot."""
        if frame.is_empty():
            return ""
        ts = frame.get_column(TIMESTAMP_COL)
        if scores.size >= 128:
            w = 64
            k = scores.size // w
            wm = scores[: k * w].reshape(k, w).mean(axis=1)
            med = float(np.median(wm))
            mad = 1.4826 * float(np.median(np.abs(wm - med)))
            hot = np.nonzero(wm > med + 4.0 * max(mad, 1e-9))[0]
            if hot.size and hot[0] > 0:
                return str(ts[int(hot[0]) * w])
        return str(ts.min())

    @staticmethod
    def _first_ts(frame: pl.DataFrame) -> str:
        return (
            str(frame.get_column(TIMESTAMP_COL).min())
            if not frame.is_empty()
            else ""
        )

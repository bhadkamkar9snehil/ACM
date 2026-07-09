"""Service runtime: hosts any number of independent per-asset monitors.

Ties the spine together per asset - episodic monitor over lifetime memory,
verdict cache, governed rebuild scheduling - and keeps the multi-asset
construction principle: one asset's tick never touches another's state.
One asset is a fleet of one; there is no single-asset mode.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from acm import verdict as V
from acm.episodes import EpisodicMonitor
from acm.hardware import Governor, probe, record_asset_cost
from acm.memory.ledger import EpisodeLedger
from acm.monitor import AssetMonitor
from acm.store.raw import TIMESTAMP_COL, RawStore

REBUILD_EVERY_TICKS = 7 * 24  # weekly at hourly ticks (D3); staggered below
IMMUNE_EVERY_TICKS = 7 * 24  # weekly immune pass per asset; staggered
IMMUNE_SAMPLE_ROWS = 12000  # recent healthy rows used per immune pass


@dataclass
class Runtime:
    store: RawStore
    data_root: Path
    governor: Governor | None = None
    # evidence-lane override (#91): force a scorer class regardless of the
    # probed tier - verdict semantics are tier-free, so cross-tier
    # comparisons run the SAME runtime with only this swapped
    scorer_cls_override: type | None = None
    monitors: dict[str, EpisodicMonitor] = field(default_factory=dict)
    verdicts: dict[str, V.Verdict] = field(default_factory=dict)
    previous_verdicts: dict[str, V.Verdict] = field(default_factory=dict)
    immune_results: dict[str, dict] = field(default_factory=dict)
    live_sources: dict[str, object] = field(default_factory=dict)
    _last_seen: dict[str, object] = field(default_factory=dict)
    _tick_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.governor is None:
            self.governor = Governor.from_probe(probe())
        self.ledger = EpisodeLedger(Path(self.data_root) / "ledger.json")
        self.cache_root = Path(self.data_root) / "memcache"
        # durable first-contact record: {asset_key: iso_utc_completed_at}.
        # "Virgin" means "never bootstrapped", NOT "no ledger windows" -
        # a clean asset never gains windows, so a windows-based test would
        # re-run the full multi-pass bootstrap on EVERY service start
        # (found by test: the tick loop sat behind a redundant bootstrap).
        self._bootstrapped_path = Path(self.data_root) / "bootstrapped.json"
        self._bootstrapped: dict[str, str] = {}
        if self._bootstrapped_path.exists():
            self._bootstrapped = json.loads(
                self._bootstrapped_path.read_text(encoding="utf-8")
            )

    # ----------------------------------------------------------- assets
    def _select_scorer_cls(self):
        """Tier-aware scorer selection (implementation plan 1.1): the
        world model at T2/T2-S when torch is importable; the conditional
        ridge everywhere else. Verdict semantics identical across tiers -
        only power differs; the guarantee is tier-free."""
        if self.scorer_cls_override is not None:
            return self.scorer_cls_override
        if self.governor.tier in ("T2", "T2-S"):
            try:
                from acm.scoring.worldmodel import TorchWorldModel

                import torch  # noqa: F401

                return TorchWorldModel
            except ImportError:
                pass
        from acm.scoring.surprise import ConditionalSurpriseScorer

        return ConditionalSurpriseScorer

    def onboard(self, asset_key: str) -> bool:
        em = EpisodicMonitor(
            AssetMonitor(asset_key, scorer_cls=self._select_scorer_cls()),
            self.ledger,
        )
        ok = em.monitor.calibrate_from_lifetime(
            self.store, ledger=self.ledger, cache_root=self.cache_root
        )
        self.monitors[asset_key] = em
        self._tick_counts[asset_key] = 0
        if not ok:
            self.verdicts[asset_key] = em.process(pl.DataFrame())
        return ok

    def onboard_all(self) -> dict[str, bool]:
        return {key: self.onboard(key) for key in self.store.assets()}

    def bootstrap_virgin(self) -> dict[str, dict]:
        """First-contact cleaning for every never-bootstrapped asset:
        the detect->mask->re-detect loop (H1 fix: bootstrap existed but was
        never wired into the service path - contaminated first contact
        would never have been cleaned in production).

        Runs ONCE per asset lifetime, recorded in bootstrapped.json.
        Pre-marker data roots: existing ledger windows are accepted as
        evidence of a prior first contact (and back-filled into the
        marker), so old deployments are not re-bootstrapped either."""
        out = {}
        for key in self.monitors:
            if key in self._bootstrapped:
                continue
            if self.ledger.windows(key):
                self._mark_bootstrapped(key)
                continue
            out[key] = self.bootstrap(key)
        return out

    def _mark_bootstrapped(self, asset_key: str) -> None:
        self._bootstrapped[asset_key] = datetime.now(timezone.utc).isoformat()
        self._bootstrapped_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._bootstrapped_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._bootstrapped, indent=1), encoding="utf-8"
        )
        tmp.replace(self._bootstrapped_path)

    def reanchor(self, asset_key: str) -> bool:
        """Governed episode close + recalibration, exposed for the UI."""
        em = self.monitors[asset_key]
        v = self.verdicts.get(asset_key)
        if v is None:
            return False
        ok = em.reanchor(self.store, v, cache_root=self.cache_root)
        if ok:
            self.previous_verdicts[asset_key] = v
        return ok

    def health_series(self, asset_key: str) -> list[float]:
        em = self.monitors.get(asset_key)
        return list(em._health_index) if em is not None else []

    def domains(self, asset_key: str) -> dict:
        """Per-domain bank states for the UI evidence panel."""
        m = self.monitors[asset_key].monitor
        out = {}
        pairs = [
            ("magnitude", m.bank),
            ("availability", m.avail_bank),
            ("horizon-gap", m.gap_bank),
            ("predictability-band", m.band_bank),
            ("transient-response", m.trans_bank),
            ("dynamics-drift", m.dyn_bank),
        ]
        for name, bank in pairs:
            if bank is None:
                out[name] = {"enabled": False}
            else:
                st = bank.state()
                out[name] = {
                    "enabled": True,
                    "alarmed": st.alarmed,
                    "evidence": round(st.evidence, 4),
                }
        return out

    def attach_live_source(self, asset_key: str, db_path) -> None:
        """Attach a SQLite buffer (bridge/sim-fed) to an asset; drained
        on every tick before scoring."""
        from acm.ingest.buffer_source import BufferSource

        self.live_sources[asset_key] = BufferSource(
            db_path=db_path, asset_key=asset_key
        )

    # ------------------------------------------------------------ ticks
    def tick(self, asset_key: str) -> V.Verdict | None:
        """Score any new rows for one asset; returns the verdict if new
        data was seen. Rebuilds are staggered by asset-index offset so a
        fleet never rebuilds at once."""
        em = self.monitors[asset_key]
        started = time.monotonic()
        src = self.live_sources.get(asset_key)
        if src is not None:
            src.drain(self.store)  # live buffer -> immortal store, then read
        since = self._last_seen.get(asset_key)
        frame = self.store.read(asset_key, start=since)
        if since is not None and not frame.is_empty():
            frame = frame.filter(pl.col(TIMESTAMP_COL) > since)
        verdict = None
        if not frame.is_empty():
            self._last_seen[asset_key] = frame.get_column(TIMESTAMP_COL).max()
            verdict = em.process(frame)
            if asset_key in self.verdicts:
                self.previous_verdicts[asset_key] = self.verdicts[asset_key]
            self.verdicts[asset_key] = verdict
            if self._change_ripe_for_absorption(em, verdict):
                # governed auto-absorption (#89): the verdict's own
                # re-baseline proposal, executed - unattended operation
                # cannot wait for a human to click Re-anchor. Only while
                # the CURRENT classification is still change-not-fault;
                # a drift reclassification blocks it (the definition of
                # normal never moves during accumulating degradation).
                if em.reanchor(
                    store=self.store,
                    last_verdict=verdict,
                    cache_root=self.cache_root,
                ):
                    self.previous_verdicts[asset_key] = verdict
        self._tick_counts[asset_key] += 1
        stagger = hash(asset_key) % REBUILD_EVERY_TICKS
        if (
            self._tick_counts[asset_key] + stagger
        ) % REBUILD_EVERY_TICKS == 0 and em.open_episode_start == "":
            # governed rebuild: never while an episode is open (the
            # definition of normal does not move during accumulating
            # evidence of degradation)
            em.monitor.calibrate_from_lifetime(
                self.store, ledger=self.ledger, cache_root=self.cache_root
            )
        stagger_i = (hash(asset_key) // 7) % IMMUNE_EVERY_TICKS
        if (self._tick_counts[asset_key] + stagger_i) % IMMUNE_EVERY_TICKS == 0:
            self.immune_pass(asset_key)
        record_asset_cost(
            asset_key, time.monotonic() - started, frame.height
        )
        return verdict

    @staticmethod
    def _change_ripe_for_absorption(em, verdict: V.Verdict) -> bool:
        """True when an open change-not-fault episode's plateau has held
        for CHANGE_ABSORB_ANCHOR_PERIODS anchor periods (#89)."""
        if verdict.state != V.STATE_CHANGE or not em.open_episode_start:
            return False
        from acm.constants import get as const

        anchor_s = (
            365.25 * 24 * 3600.0 / float(const("REANCHORS_PER_YEAR"))
        ) * float(const("CHANGE_ABSORB_ANCHOR_PERIODS"))
        try:
            start = datetime.fromisoformat(em.open_episode_start)
            now = datetime.fromisoformat(str(verdict.at))
        except ValueError:
            return False
        return (now - start).total_seconds() >= anchor_s

    def tick_all(self) -> int:
        moved = 0
        for key in list(self.monitors):
            if self.tick(key) is not None:
                moved += 1
        return moved

    # -------------------------------------------------------- bootstrap
    @staticmethod
    def _scan_contamination(
        ts_col, scores, window: int = 256, mads: float = 4.0
    ) -> list[tuple[str, str]]:
        """Contiguous elevated blocks in the lifetime score trace.

        The e-process cannot detect contamination sitting INSIDE its own
        calibration reference. The discriminator (inherited from the lab's
        contamination-filter post-mortem): genuine contamination is a
        CONTIGUOUS block of elevated surprise; legitimate rare operation is
        scattered tail values. Percentile trimming is banned (it deletes
        healthy variance); block scanning flags only sustained runs.
        """
        import numpy as np

        s = np.asarray(scores, dtype=np.float64)
        n = s.size
        if n < 4 * window:
            return []
        k = n // window
        wm = s[: k * window].reshape(k, window).mean(axis=1)
        med = float(np.median(wm))
        mad = 1.4826 * float(np.median(np.abs(wm - med)))
        mad = max(mad, 1e-9)
        hot = wm > med + mads * mad
        regions, start = [], None
        for i, h in enumerate(hot):
            if h and start is None:
                start = i
            elif not h and start is not None:
                regions.append((start, i))
                start = None
        if start is not None:
            regions.append((start, k))
        out = []
        for a, b in regions:
            t0 = str(ts_col[a * window])
            t1 = str(ts_col[min(b * window, n - 1)])
            out.append((t0, t1))
        return out

    def bootstrap(self, asset_key: str, max_iters: int = 4) -> dict:
        """First contact with an asset's history: DETECT -> MASK ->
        RE-DETECT to convergence (rethink plan bootstrap requirement).

        Pass 1 calibrates on raw lifetime (possibly contaminated), replays
        the whole history, and ledgers any episodes found. Each further
        pass recalibrates on the ledger-MASKED lifetime - the baseline the
        previous pass could not have (its contamination is now excluded) -
        and replays again. Converged when a pass finds no new episodes.
        Every pass analyses the same data against a cleaner definition of
        normal; this is the multiple-run-throughs mechanism.
        """
        em = self.monitors[asset_key]
        history = self.store.read(asset_key)
        passes = []
        for it in range(max_iters):
            ok = em.monitor.calibrate_from_lifetime(
                self.store, ledger=self.ledger, cache_root=self.cache_root
            )
            if not ok:
                passes.append({"pass": it + 1, "status": "insufficient"})
                break
            em.open_episode_start = ""
            em._episode_scores = []
            episodes_before = len(self.ledger.episodes)

            # each pass analyses only the not-yet-explained life: rows
            # already inside ledger windows are excluded, so a pass can
            # only find NEW structure (this is what makes the loop
            # converge instead of re-finding the same fault forever)
            unexplained = self.ledger.mask(asset_key, history)
            if unexplained.is_empty():
                passes.append({"pass": it + 1, "new_episodes": 0})
                break

            # DETECT part 1 - contamination scan of the score trace
            # (catches faults sitting inside the calibration reference,
            # which the e-process structurally cannot)
            scores_full = em.monitor.scorer.score(unexplained)
            ts_col = unexplained.get_column(TIMESTAMP_COL).to_list()
            existing = self.ledger.windows(asset_key)
            for t0, t1 in self._scan_contamination(ts_col, scores_full):
                overlaps = any(
                    not (t1 < w0 or t0 > w1) for w0, w1 in existing
                )
                if not overlaps:
                    from acm.memory.ledger import Episode

                    self.ledger.add(
                        Episode(
                            asset_key=asset_key,
                            start=t0,
                            end=t1,
                            state="alarm",
                            note='{"source": "bootstrap-scan"}',
                        )
                    )

            # DETECT part 2 - e-process replay of the unexplained life
            last_verdict = None
            for chunk_start in range(0, unexplained.height, 4000):
                chunk = unexplained.slice(chunk_start, 4000)
                v = em.process(chunk)
                if v.state in (
                    V.STATE_ALARM,
                    V.STATE_ESCALATING,
                    V.STATE_CHANGE,
                ):
                    last_verdict = v
                elif em.open_episode_start and last_verdict is not None:
                    # evidence latched but state recovered -> close episode
                    em.reanchor(store=self.store, last_verdict=last_verdict,
                                cache_root=self.cache_root)
                    last_verdict = None
            if em.open_episode_start and last_verdict is not None:
                em.reanchor(store=self.store, last_verdict=last_verdict,
                            cache_root=self.cache_root)
            found = len(self.ledger.episodes) - episodes_before
            passes.append({"pass": it + 1, "new_episodes": found})
            if found == 0:
                break
        # leave the monitor calibrated on the final masked baseline; a
        # failure here means a DEAD monitor, so it is reported, not dropped
        final_ok = em.monitor.calibrate_from_lifetime(
            self.store, ledger=self.ledger, cache_root=self.cache_root
        )
        dropped: list[dict] = []
        if not final_ok:
            # SELF-REFUTING MASK guard (#92): a ledger mask that leaves
            # the calibration with nothing cannot be right - a baseline
            # must exist for "unhealthy" to mean anything (the #87 lesson
            # generalized to fault windows: the WM bootstrap ledgered a
            # full-life alarm and killed the monitor). Drop the WIDEST
            # bootstrap-created fault window and recalibrate, repeating
            # until calibration succeeds or none remain. Live-path
            # reanchor is untouched - this is first-contact-only repair.
            from acm.memory.ledger import FAULT_STATES

            def _span(e) -> float:
                try:
                    t0 = datetime.fromisoformat(e.start)
                    t1 = datetime.fromisoformat(
                        e.end or "9999-12-31T00:00:00+00:00"
                    )
                    return (t1 - t0).total_seconds()
                except ValueError:
                    return 0.0

            while not final_ok:
                candidates = [
                    e
                    for e in self.ledger.episodes
                    if e.asset_key == asset_key and e.state in FAULT_STATES
                ]
                if not candidates:
                    break  # genuinely thin data: insufficient is honest
                widest = max(candidates, key=_span)
                self.ledger.remove(widest)
                dropped.append(
                    {"start": widest.start, "end": widest.end}
                )
                final_ok = em.monitor.calibrate_from_lifetime(
                    self.store, ledger=self.ledger, cache_root=self.cache_root
                )
        self._last_seen[asset_key] = (
            history.get_column(TIMESTAMP_COL).max()
            if not history.is_empty()
            else None
        )
        self._mark_bootstrapped(asset_key)
        return {
            "asset": asset_key,
            "passes": passes,
            "final_calibration": bool(final_ok),
            "dropped_self_refuting_windows": dropped,
        }

    # ----------------------------------------------------- immune path
    def immune_pass(self, asset_key: str) -> dict:
        """Scheduled self-validation (S2 harness + PIT conformance), the
        unattended answer to 'is the detector still alive?'. Failures are
        first-class events: the finding is recorded, and a rebuild is
        triggered immediately (the governed response to a sick model)."""
        em = self.monitors[asset_key]
        # "healthy" here matches the baseline's definition: fault windows
        # excluded, absorbed change-not-fault regimes kept
        from acm.memory.ledger import FAULT_STATES

        frame = self.ledger.mask(
            asset_key, self.store.read(asset_key), states=FAULT_STATES
        )
        if frame.height > IMMUNE_SAMPLE_ROWS:
            frame = frame.tail(IMMUNE_SAMPLE_ROWS)

        from acm.immune import degeneracy_check, sensitivity_profile
        from acm.scoring.surprise import classify_pit_distortion

        report = sensitivity_profile(asset_key, frame)
        result = report.to_dict()

        # THE LIVE-INSTANCE CHECK: the harness profiles the pipeline RECIPE
        # (fresh monitors fit on the sample) - it cannot see a dead LIVE
        # scorer. Found by test: a zeroed deployed scorer passed the recipe
        # profile. The live scorer's own recent output is checked directly.
        live = self.monitors[asset_key].monitor.scorer
        live_dead = True
        if live is not None and frame.height > 0:
            live_dead = degeneracy_check(
                live.score(frame.tail(min(frame.height, 2000)))
            )
        result["live_degenerate"] = live_dead

        # PIT conformance is an immune signal ONLY while not alarmed
        # (during a real fault, coupled distortion is expected)
        current = self.verdicts.get(asset_key)
        not_alarmed = current is None or current.state in (
            V.STATE_HEALTHY,
            V.STATE_WATCH,
            V.STATE_INSUFFICIENT,
        )
        pit_verdict = "n/a"
        scorer = em.monitor.scorer
        if not_alarmed and scorer is not None and hasattr(scorer, "pit"):
            tail = frame.tail(min(frame.height, 4000))
            pits = scorer.pit(tail)
            pit_verdict, _ks = classify_pit_distortion(pits, scorer.channels)
        result["pit"] = pit_verdict

        # C8: rehearse the LIVE pipeline against self-imagined coherent
        # faults - the measured sensitivity floor, refreshed weekly
        live = self.monitors[asset_key].monitor.scorer
        bank = self.monitors[asset_key].monitor.bank
        if (
            live is not None
            and bank is not None
            and hasattr(live, "betas")
            and frame.height > 1000
        ):
            from acm.immune.rehearsal import rehearse

            rmap = rehearse(
                live,
                frame.tail(min(frame.height, 2500)),
                bank.members[0]._calib_sorted,
            )
            result["rehearsal"] = {
                "floors": rmap.floors,
                "overall_floor": rmap.overall_floor,
                "detected_fraction": round(rmap.detected_fraction, 3),
                "scope": rmap.scope,
            }

        # Conformance (like PIT) is an immune signal ONLY while the asset
        # is not alarmed: during an active episode the 'recent healthy
        # tail' assumption is violated by the fault itself, and a rebuild
        # here would move the definition of normal DURING accumulating
        # evidence - the exact thing the tick-path rebuild gate forbids.
        # Found by review: an actively-faulted pilot was being flagged
        # 'model sick' and rebuilt mid-episode.
        sick = report.scorer_dead or live_dead or (
            not_alarmed
            and (not report.conformance_ok or pit_verdict == "model")
        )
        result["sick"] = sick
        if not not_alarmed and (not report.conformance_ok):
            result["conformance_note"] = (
                "conformance failure observed during an ACTIVE episode - "
                "expected (the fault is in the sample); deferred to the "
                "post-reanchor pass"
            )
        result["action"] = "rebuild" if sick else "none"
        if sick:
            em.monitor.calibrate_from_lifetime(
                self.store, ledger=self.ledger, cache_root=self.cache_root
            )
        self.immune_results[asset_key] = result
        return result

    def narrative(self, asset_key: str) -> str | None:
        from acm.narrative import build_narrative

        v = self.verdicts.get(asset_key)
        if v is None:
            return None
        return build_narrative(
            v,
            previous=self.previous_verdicts.get(asset_key),
            immune=self.immune_results.get(asset_key),
        )

    # -------------------------------------------------------- aggregates
    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for v in self.verdicts.values():
            counts[v.state] = counts.get(v.state, 0) + 1
        worst_order = [
            V.STATE_ESCALATING,
            V.STATE_ALARM,
            V.STATE_CHANGE,
            V.STATE_WATCH,
            V.STATE_INSUFFICIENT,
            V.STATE_HEALTHY,
        ]
        rank = {s: i for i, s in enumerate(worst_order)}
        rows = sorted(
            (
                {
                    **v.to_dict(),
                    # a live-fed asset must be recognizable in the fleet
                    # view - a silent buffer otherwise looks exactly like
                    # a healthy quiet asset (#90 lesson)
                    "live": key in self.live_sources,
                }
                for key, v in self.verdicts.items()
            ),
            key=lambda d: (rank.get(d["state"], 99), -d["evidence"]),
        )
        immune_sick = sum(
            1 for r in self.immune_results.values() if r.get("sick")
        )
        return {
            "assets": len(self.monitors),
            "counts": counts,
            "tier": self.governor.tier,
            "immune": {
                "checked": len(self.immune_results),
                "sick": immune_sick,
            },
            "rows": rows,
        }

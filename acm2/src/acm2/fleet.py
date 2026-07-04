"""Fleet runtime (S6): 1 to 1000 assets, each an island, one machine.

Ties the spine together per asset - episodic monitor over lifetime memory,
verdict cache, governed rebuild scheduling - and keeps the multi-asset
construction principle: one asset's tick never touches another's state.
One asset is a fleet of one; there is no single-asset mode.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from acm2 import verdict as V
from acm2.episodes import EpisodicMonitor
from acm2.hardware import Governor, probe, record_asset_cost
from acm2.memory.ledger import EpisodeLedger
from acm2.monitor import AssetMonitor
from acm2.store.raw import TIMESTAMP_COL, RawStore

REBUILD_EVERY_TICKS = 7 * 24  # weekly at hourly ticks (D3); staggered below
IMMUNE_EVERY_TICKS = 7 * 24  # weekly immune pass per asset; staggered
IMMUNE_SAMPLE_ROWS = 12000  # recent healthy rows used per immune pass


@dataclass
class FleetRuntime:
    store: RawStore
    data_root: Path
    governor: Governor | None = None
    monitors: dict[str, EpisodicMonitor] = field(default_factory=dict)
    verdicts: dict[str, V.Verdict] = field(default_factory=dict)
    immune_results: dict[str, dict] = field(default_factory=dict)
    _last_seen: dict[str, object] = field(default_factory=dict)
    _tick_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.governor is None:
            self.governor = Governor.from_probe(probe())
        self.ledger = EpisodeLedger(Path(self.data_root) / "ledger.json")
        self.cache_root = Path(self.data_root) / "memcache"

    # ----------------------------------------------------------- assets
    def onboard(self, asset_key: str) -> bool:
        em = EpisodicMonitor(AssetMonitor(asset_key), self.ledger)
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

    # ------------------------------------------------------------ ticks
    def tick(self, asset_key: str) -> V.Verdict | None:
        """Score any new rows for one asset; returns the verdict if new
        data was seen. Rebuilds are staggered by asset-index offset so a
        fleet never rebuilds at once."""
        em = self.monitors[asset_key]
        started = time.monotonic()
        since = self._last_seen.get(asset_key)
        frame = self.store.read(asset_key, start=since)
        if since is not None and not frame.is_empty():
            frame = frame.filter(pl.col(TIMESTAMP_COL) > since)
        verdict = None
        if not frame.is_empty():
            self._last_seen[asset_key] = frame.get_column(TIMESTAMP_COL).max()
            verdict = em.process(frame)
            self.verdicts[asset_key] = verdict
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

    def tick_all(self) -> int:
        moved = 0
        for key in list(self.monitors):
            if self.tick(key) is not None:
                moved += 1
        return moved

    # ----------------------------------------------------- immune path
    def immune_pass(self, asset_key: str) -> dict:
        """Scheduled self-validation (S2 harness + PIT conformance), the
        unattended answer to 'is the detector still alive?'. Failures are
        first-class events: the finding is recorded, and a rebuild is
        triggered immediately (the governed response to a sick model)."""
        em = self.monitors[asset_key]
        frame = self.ledger.mask(asset_key, self.store.read(asset_key))
        if frame.height > IMMUNE_SAMPLE_ROWS:
            frame = frame.tail(IMMUNE_SAMPLE_ROWS)

        from acm2.immune import degeneracy_check, sensitivity_profile
        from acm2.scoring.surprise import classify_pit_distortion

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

        sick = (
            report.scorer_dead
            or live_dead
            or not report.conformance_ok
            or pit_verdict == "model"
        )
        result["sick"] = sick
        result["action"] = "rebuild" if sick else "none"
        if sick:
            em.monitor.calibrate_from_lifetime(
                self.store, ledger=self.ledger, cache_root=self.cache_root
            )
        self.immune_results[asset_key] = result
        return result

    # -------------------------------------------------------- aggregates
    def fleet_summary(self) -> dict:
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
            (v.to_dict() for v in self.verdicts.values()),
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

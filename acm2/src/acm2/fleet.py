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


@dataclass
class FleetRuntime:
    store: RawStore
    data_root: Path
    governor: Governor | None = None
    monitors: dict[str, EpisodicMonitor] = field(default_factory=dict)
    verdicts: dict[str, V.Verdict] = field(default_factory=dict)
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
        return {
            "assets": len(self.monitors),
            "counts": counts,
            "tier": self.governor.tier,
            "rows": rows,
        }

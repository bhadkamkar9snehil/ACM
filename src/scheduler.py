"""Fleet scheduler stub (S0.6): staggered async ticks over N assets.

Pattern salvaged (copied, per D9) from the lab's tick-scheduler shape.
Per-asset isolation is the multi-asset construction principle: one asset's
tick never touches another's state. Ticks are staggered across the interval
so fleet load stays flat.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

import polars as pl

from hardware import record_asset_cost
from store.raw import TIMESTAMP_COL, RawStore

TickHook = Callable[[str, pl.DataFrame], Awaitable[None]]


@dataclass
class TickRecord:
    asset_key: str
    at: float
    new_rows: int
    wall_s: float


@dataclass
class FleetScheduler:
    store: RawStore
    assets: list[str]
    hook: TickHook
    interval_s: float = 60.0
    ticks: list[TickRecord] = field(default_factory=list)
    _last_seen: dict[str, object] = field(default_factory=dict)
    _stop: asyncio.Event = field(default_factory=asyncio.Event)

    async def _tick_asset(self, asset_key: str) -> None:
        started = time.monotonic()
        since = self._last_seen.get(asset_key)
        frame = self.store.read(asset_key, start=since)
        if since is not None and not frame.is_empty():
            # start is inclusive in read(); drop the already-seen row
            frame = frame.filter(pl.col(TIMESTAMP_COL) > since)
        if not frame.is_empty():
            self._last_seen[asset_key] = frame.get_column(TIMESTAMP_COL).max()
            await self.hook(asset_key, frame)
        wall = time.monotonic() - started
        self.ticks.append(
            TickRecord(asset_key, time.time(), frame.height, wall)
        )
        record_asset_cost(asset_key, wall, frame.height)

    async def _loop_asset(self, index: int, asset_key: str) -> None:
        stagger = self.interval_s * index / max(1, len(self.assets))
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=stagger)
            return
        except asyncio.TimeoutError:
            pass
        while not self._stop.is_set():
            await self._tick_asset(asset_key)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_s)
            except asyncio.TimeoutError:
                continue

    async def run(self, duration_s: Optional[float] = None) -> None:
        tasks = [
            asyncio.create_task(self._loop_asset(i, a))
            for i, a in enumerate(self.assets)
        ]
        if duration_s is not None:
            await asyncio.sleep(duration_s)
            self._stop.set()
        await asyncio.gather(*tasks)

    def stop(self) -> None:
        self._stop.set()

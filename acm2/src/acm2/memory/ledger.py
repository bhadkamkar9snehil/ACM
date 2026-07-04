"""Episode ledger (S3 scaffolding, populated by episode logic at S5).

THE LOAD-BEARING PURPOSE: baseline hygiene. A lifetime healthy baseline is
only healthy if the unhealthy stretches are excluded; the ledger IS the
healthy/unhealthy partition of the asset's life. It is a derived cache
(P1): re-running the system over raw history regenerates it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import polars as pl

from acm2.store.raw import TIMESTAMP_COL


@dataclass(frozen=True)
class Episode:
    asset_key: str
    start: str  # ISO8601 UTC
    end: str  # ISO8601 UTC ("" = still open)
    state: str  # alarm | change-not-fault | intervention
    note: str = ""


class EpisodeLedger:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.episodes: list[Episode] = []
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.episodes = [Episode(**e) for e in data]

    def add(self, episode: Episode) -> None:
        self.episodes.append(episode)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([asdict(e) for e in self.episodes], indent=1),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def windows(self, asset_key: str) -> list[tuple[str, str]]:
        return [
            (e.start, e.end or "9999-12-31T00:00:00+00:00")
            for e in self.episodes
            if e.asset_key == asset_key
        ]

    def mask(self, asset_key: str, frame: pl.DataFrame) -> pl.DataFrame:
        """Drop rows inside any of the asset's episode windows."""
        for start, end in self.windows(asset_key):
            if frame.is_empty():
                break
            frame = frame.filter(
                ~(
                    (pl.col(TIMESTAMP_COL) >= pl.lit(start).str.to_datetime(time_zone="UTC"))
                    & (pl.col(TIMESTAMP_COL) <= pl.lit(end).str.to_datetime(time_zone="UTC"))
                )
            )
        return frame

"""Episode ledger (S3 scaffolding, populated by episode logic at S5).

THE LOAD-BEARING PURPOSE: baseline hygiene. A lifetime healthy baseline is
only healthy if the unhealthy stretches are excluded; the ledger IS the
healthy/unhealthy partition of the asset's life. It is a derived cache
(P1): re-running the system over raw history regenerates it.

Episode STATE decides what an episode means for the baseline:
- "alarm" / "intervention" are FAULT windows - excluded from the healthy
  baseline (that is the hygiene).
- "change-not-fault" is a regime move the baseline ABSORBS (the episode's
  own falsifiability text says re-anchoring absorbs the new plateau);
  masking it out would do the opposite. Found on real CARE data: a
  change-not-fault episode spanning the whole life masked 100% of history
  and left the monitor permanently insufficient.
Baseline consumers therefore mask with states=FAULT_STATES; the bootstrap
convergence mask keeps ALL states (a pass must not re-find the same
already-explained change forever).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import polars as pl

from acm.store.raw import TIMESTAMP_COL

# Episode states that mark the window as UNHEALTHY for baseline purposes.
FAULT_STATES = ("alarm", "intervention")


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
        self._save()

    def remove(self, episode: Episode) -> None:
        """Drop one episode (bootstrap's self-refuting-mask guard, #92).
        Episodes are frozen dataclasses, so identity is by value."""
        self.episodes.remove(episode)
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([asdict(e) for e in self.episodes], indent=1),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def windows(
        self, asset_key: str, states: tuple[str, ...] | None = None
    ) -> list[tuple[str, str]]:
        """Episode windows for an asset; states=None means every state,
        states=FAULT_STATES means fault windows only (baseline hygiene)."""
        return [
            (e.start, e.end or "9999-12-31T00:00:00+00:00")
            for e in self.episodes
            if e.asset_key == asset_key
            and (states is None or e.state in states)
        ]

    def mask(
        self,
        asset_key: str,
        frame: pl.DataFrame,
        states: tuple[str, ...] | None = None,
    ) -> pl.DataFrame:
        """Drop rows inside the asset's episode windows (see `windows`)."""
        for start, end in self.windows(asset_key, states=states):
            if frame.is_empty():
                break
            frame = frame.filter(
                ~(
                    (pl.col(TIMESTAMP_COL) >= pl.lit(start).str.to_datetime(time_zone="UTC"))
                    & (pl.col(TIMESTAMP_COL) <= pl.lit(end).str.to_datetime(time_zone="UTC"))
                )
            )
        return frame

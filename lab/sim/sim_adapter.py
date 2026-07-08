from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SIM_DATA_DIR = ROOT / "sim_data"


class SimAdapter:
    """Facade over the simulator engine for ACM's service layer."""

    def __init__(self) -> None:
        from sim.buffer_publisher import BufferPublisher
        from sim.protocol_adapter import DualProtocolAdapter
        from sim.simulator import SimulatorEngine

        self._buffer = BufferPublisher()
        self._dual = DualProtocolAdapter()
        self._engine = SimulatorEngine(self._buffer)
        self._publisher_mode = "buffer"

    def _ensure_sim_data(self) -> None:
        for sub in ("uploads", "generated", "sample"):
            (SIM_DATA_DIR / sub).mkdir(parents=True, exist_ok=True)

    async def set_publisher(self, mode: str) -> None:
        from sim.buffer_publisher import BufferPublisher
        from sim.protocol_adapter import DualProtocolAdapter
        from sim.simulator import SimulatorEngine

        self._publisher_mode = mode
        if mode == "buffer":
            publisher = self._buffer
        else:
            self._dual.protocol = mode if mode in ("opcua", "mqtt") else "both"
            publisher = self._dual
        self._engine = SimulatorEngine(publisher)

    async def start(self) -> None:
        self._ensure_sim_data()

    async def stop(self) -> None:
        await self._engine.stop()
        try:
            await self._dual.stop()
        except Exception:
            pass

    async def generate(self, domain_id: str, request: Any,
                       backdate: bool = True, backdate_days: int = 45) -> Any:
        self._ensure_sim_data()
        from sim.generator_engine import generate_csv
        resp = generate_csv(domain_id, request)
        if backdate and resp.filename:
            generated_path = SIM_DATA_DIR / "generated" / resp.filename
            _backdate_csv(generated_path, backdate_days)
        return resp

    async def configure_replay(self, config: Any, publisher_mode: str = "buffer") -> dict:
        await self.set_publisher(publisher_mode)
        return await self._engine.configure(config)

    async def start_replay(self) -> dict:
        return await self._engine.start()

    async def stop_replay(self) -> dict:
        return await self._engine.stop()

    async def restart_replay(self) -> dict:
        return await self._engine.restart()

    def get_status(self) -> dict:
        status = self._engine.get_status().model_dump()
        status["publisher_mode"] = self._publisher_mode
        return status

    def get_current_values(self) -> Any:
        return self._engine.get_current_values()


def _backdate_csv(path: Path, days: int) -> None:
    """Shift all timestamps in a CSV so the last row lands at ~now."""
    if not path.exists():
        return
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return
        ts_col = next((c for c in reader.fieldnames if c.lower() == "timestamp"), None)
        if not ts_col:
            return
        rows = list(reader)
        fieldnames = reader.fieldnames

    if not rows:
        return

    try:
        last_ts = datetime.fromisoformat(str(rows[-1][ts_col]).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        shift = now - last_ts
    except Exception:
        return

    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            try:
                t = datetime.fromisoformat(str(row[ts_col]).replace("Z", "+00:00"))
                row[ts_col] = (t + shift).isoformat().replace("+00:00", "Z")
            except Exception:
                pass
            writer.writerow(row)
    os.replace(tmp, path)

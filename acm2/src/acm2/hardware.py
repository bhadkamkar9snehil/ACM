"""Hardware probe, capability tier selection, resource governor (S0.4).

The system decides its own capability tier from what it finds at startup
(implementation plan 1.1); no hardware decision is delegated to anyone.
Verdict semantics are identical across tiers; only power differs.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

TIER_T0 = "T0"  # CPU, modest
TIER_T1 = "T1"  # CPU, strong
TIER_T2S = "T2-S"  # small GPU (~8GB VRAM)
TIER_T2 = "T2"  # full GPU

_BLAS_ENV_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


@dataclass(frozen=True)
class Probe:
    cpu_count: int
    ram_gb: float
    gpu_name: str | None
    gpu_vram_gb: float


def set_thread_caps(threads: int = 1) -> None:
    """Cap BLAS thread pools. MUST run at import time in every entrypoint,
    before numpy is imported and before any process pool is constructed
    (the lab's fork-deadlock lesson, CLAUDE.md mistake #44)."""
    for var in _BLAS_ENV_VARS:
        os.environ.setdefault(var, str(threads))


def _total_ram_gb() -> float:
    if sys.platform == "win32":
        class MemStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        stat = MemStatus()
        stat.dwLength = ctypes.sizeof(MemStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return stat.ullTotalPhys / (1024**3)
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return pages * page_size / (1024**3)
    except (ValueError, OSError):
        return 0.0


def _probe_gpu() -> tuple[str | None, float]:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None, 0.0
    try:
        out = subprocess.run(
            [smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
        first = out.splitlines()[0]
        name, vram_mb = (part.strip() for part in first.rsplit(",", 1))
        return name, float(vram_mb) / 1024.0
    except (subprocess.SubprocessError, ValueError, IndexError, OSError):
        return None, 0.0


def probe() -> Probe:
    gpu_name, vram = _probe_gpu()
    return Probe(
        cpu_count=os.cpu_count() or 1,
        ram_gb=_total_ram_gb(),
        gpu_name=gpu_name,
        gpu_vram_gb=vram,
    )


def select_tier(p: Probe) -> str:
    if p.gpu_vram_gb >= 16.0:
        return TIER_T2
    if p.gpu_vram_gb >= 6.0:
        return TIER_T2S
    if p.ram_gb >= 32.0 and p.cpu_count >= 8:
        return TIER_T1
    return TIER_T0


@dataclass(frozen=True)
class Governor:
    """Resource budgets derived from the probe, never from guesses."""

    tier: str
    evidence_workers: int
    blas_threads: int

    @classmethod
    def from_probe(cls, p: Probe) -> "Governor":
        workers = 2 if p.ram_gb < 24.0 else max(2, p.cpu_count // 4)
        return cls(tier=select_tier(p), evidence_workers=workers, blas_threads=1)


# Per-asset cost measurement hooks (S0.4: empty implementation is acceptable;
# the scheduler records into this at tick time and the governor will consume
# measured costs in S6).
MEASURED_COSTS: dict[str, dict[str, float]] = {}


def record_asset_cost(asset_key: str, wall_s: float, rows: int) -> None:
    MEASURED_COSTS[asset_key] = {"wall_s": wall_s, "rows": float(rows)}

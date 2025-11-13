"""
Rust bridge schema (stub).

If you are not using Rust for V5 yet, keep this stub so imports do not fail.
Later, replace with PyO3 bindings that expose e.g. fast FFT or filters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class SeriesSpec:
    name: str
    unit: str = ""
    scale: float = 1.0


def is_available() -> bool:
    """Return False to indicate native rust bridge is not loaded."""
    return False


def version() -> str:
    return "rust_bridge_stub/0.0.1"

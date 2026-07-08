"""D9 import boundary: acm may never import the legacy pipeline live.

Salvage means COPY, never import. This test is the CI enforcement of that
rule (docs/acm-implementation-plan.md Section 6).
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
FORBIDDEN = re.compile(
    r"^\s*(?:from|import)\s+(core|scripts|sim|static)\b", re.MULTILINE
)


def test_no_legacy_imports():
    offenders = []
    for py in SRC.rglob("*.py"):
        match = FORBIDDEN.search(py.read_text(encoding="utf-8"))
        if match:
            offenders.append(f"{py}: imports legacy module '{match.group(1)}'")
    assert not offenders, "\n".join(offenders)
